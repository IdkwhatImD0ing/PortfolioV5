"""Pure numpy rules behind bake_web.py's range decimation, range normals and LOD floors (no bpy, no mathutils, so
they are tested offline with stand-in data).

    border_vertices    vertices where a grass face meets a rock face: the decimation keeps them, so the grass/rock
                       border stays where world.py drew it instead of turning into a sawtooth along long triangles
    range_weights      Decimate vertex-group weights for the range (0 = keep, 1 = decimate freely), in 11 steps
    projected_px       largest on-screen size of boxes over a set of camera views (export_web.project's measure)
    island_mask        floating islands and islets (by name), not vegetation, roots or tiny pieces
    floor_ratios       LOD floor ratios: triangles = clip(k * px^2, lo, hi) / source triangles
    cap_floors         one common factor on floor ratios so that together they keep at most `cap` triangles (the
                       part above each floor's minimum goes first; floor_base: the minimum)
    island_floor       island_mask + floor_ratios + cap_floors
    level_ratio        the LOD level export_web.lod_levels picks for a floor ratio (the smallest level >= it)
    corner_face_angle  mean angle between corner normals and their face's normal (0 = flat shading)
    weld_corner_colours  one baked vertex colour per smooth point: the backdrop's corners at one place, on one side
                       of a crease, get the weighted mean of their samples (unset black corners left out), so the
                       per-triangle colour mosaic of a corner-domain vertex-colour bake turns into smooth shading
    smooth_corner_normals  angle-limited smooth corner normals from positions alone (weld_corner_colours' fallback
                       when a mesh carries no corner normals, e.g. a decoded GLB offline)
    fill_missing_corners  corners a vertex-colour bake left unsampled (buried in the floor) take their neighbours'
                       colour offline, so the page's fillMissingColors finds nothing to do on the areas' small props
    duplicate_faces    faces whose corners repeat an earlier face's (any order or winding): one copy is kept
    tiny_faces         faces under an area floor (zero-area triangles the exporter or the pack would drop anyway)
    sheet_project      planar UVs per connected sheet (a roof slope's corrugated tile surface): one big island per
                       slope instead of the 26-direction projection's strips 1-2 texels wide (the roof speckle)
    island_dims        long and short side of each UV island (principal axes), as pack_shelf lays them out
    group_vote         one decision per group (UV island, coplanar patch) by weighted majority
"""
import numpy as np

ISLAND_WORDS = ("islet", "island", "floating_rock")
ISLAND_MIN_TRIS = 200          # pieces at or under this keep the plain LOD rule (small rocks, spurs)
FILM = (1280.0, 720.0)         # export_web.project: on-screen size in pixels of the 16:9 film at 1280x720
FRUSTUM_MARGIN = 0.06          # export_web.FRUSTUM_MARGIN (NDC)
FAR_LIMIT = 9000.0             # export_web.project: boxes farther than this count as out of view


def _loops(faces):
    """(vertex index per corner, face index per corner) for an (m, k) face array or a (corner verts, loop
    starts) pair (a Blender mesh's loops.vertex_index and polygons.loop_start)."""
    if isinstance(faces, tuple):
        vi, ls = (np.asarray(x, np.int64) for x in faces)
        lt = np.diff(np.append(ls, len(vi)))
        return vi, np.repeat(np.arange(len(ls)), lt)
    f = np.asarray(faces, np.int64)
    return f.ravel(), np.repeat(np.arange(len(f)), f.shape[1])


def border_vertices(faces, mat_idx, grass=(1,), nv=None):
    """Per vertex: True when it is used by a grass face (material index in `grass`) and by any other face (world.range:
    0 rock, 1 grass, 2 underside)."""
    vi, fol = _loops(faces)
    nv = int(vi.max()) + 1 if nv is None else int(nv)
    g = np.isin(np.asarray(mat_idx), np.asarray(grass))[fol]
    on_g = np.zeros(nv, bool)
    on_o = np.zeros(nv, bool)
    on_g[vi[g]] = True
    on_o[vi[~g]] = True
    return on_g & on_o


def range_weights(d, border=None, near=150.0, far=1000.0, steps=10):
    """Decimate vertex-group weights from each vertex's nearest view distance d (inf = never in a frustum, decimated
    freely): 0 up to `near` m, rising to 1 at `far` m, 0 on `border` vertices, rounded to 1/steps (the vertex group
    is written one weight value at a time, so 11 steps keep that to 11 calls)."""
    d = np.asarray(d, float)
    w = np.clip((np.where(np.isfinite(d), d, far) - near) / (far - near), 0.0, 1.0)
    if border is not None:
        w = np.where(np.asarray(border, bool), 0.0, w)
    if steps:
        w = np.round(w * steps) / steps
    return w


def _box_corners(lo, hi):
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    sel = np.array([[(k >> a) & 1 for a in range(3)] for k in range(8)], bool)          # (8, 3)
    return np.where(sel[None], hi[:, None, :], lo[:, None, :])                          # (n, 8, 3)


def projected_px(lo, hi, view_mats, tan_v, aspect, dscale=None, vis=None, margin=FRUSTUM_MARGIN):
    """Per box (world lo / hi): the largest on-screen size over the views in film pixels at 1280x720 in the widened
    frame (export_web.project's measure), divided by each view's distance factor dscale (export_web.Views.dscale: a
    look-around view counts x1.5 or x2 farther, so its size counts 1/1.5 or 1/2). vis (boxes x views, optional): the
    views where each box was visible (the audit's depth test); the others count 0. aspect: the wide frame's aspect
    (export_web.DEPTH_RES).
    Boxes wholly in front of the camera are measured exactly as project() does. A box across the camera plane is
    measured by its bounding sphere (in view when the sphere reaches into the widened frustum, size = its angular
    diameter): project() counts it as filling the frame, and with look-around views turning every way at the holds
    nearly every island lies beside some view, so its px_eff reads ~1536 px wherever it is."""
    C = _box_corners(lo, hi)
    n = len(C)
    out = np.zeros(n)
    if n == 0:
        return out
    lo, hi = C.min(1), C.max(1)
    ctr = 0.5 * (lo + hi)
    rad = 0.5 * np.linalg.norm(hi - lo, axis=1)
    mats = np.asarray(view_mats, float).reshape(-1, 4, 4)
    ds = np.ones(len(mats)) if dscale is None else np.asarray(dscale, float)
    film_aspect = FILM[0] / FILM[1]
    px_cap = FILM[0] * aspect / film_aspect          # the widened frame's width in film pixels
    tx, ty = (1 + margin) * tan_v * aspect, (1 + margin) * tan_v
    for j, M in enumerate(mats):
        inv = np.linalg.inv(M)
        v = C @ inv[:3, :3].T + inv[:3, 3]
        z = -v[..., 2]
        front = z > 0.1
        allf = front.all(1)
        zc = np.maximum(z, 1e-3)
        nx = v[..., 0] / zc / (tan_v * aspect)
        ny = v[..., 1] / zc / tan_v
        x0, x1, y0, y1 = nx.min(1), nx.max(1), ny.min(1), ny.max(1)
        cam = M[:3, 3]
        d = np.linalg.norm(np.maximum(np.maximum(lo - cam, cam - hi), 0.0), axis=1)
        exact = allf & (x1 >= -1 - margin) & (x0 <= 1 + margin) & (y1 >= -1 - margin) & (y0 <= 1 + margin)
        px = np.maximum((np.clip(x1, -1, 1) - np.clip(x0, -1, 1)) * 0.5 * FILM[0] * aspect / film_aspect,
                        (np.clip(y1, -1, 1) - np.clip(y0, -1, 1)) * 0.5 * FILM[1])
        # across the camera plane: the bounding sphere against the four side planes and the camera plane
        c = ctr @ inv[:3, :3].T + inv[:3, 3]
        cz = -c[:, 2]
        reach = ((cz >= -rad)
                 & ((tx * cz - np.abs(c[:, 0])) / np.hypot(1.0, tx) >= -rad)
                 & ((ty * cz - np.abs(c[:, 1])) / np.hypot(1.0, ty) >= -rad))
        dc = np.linalg.norm(c, axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            ang = np.where(dc > rad * 1.0001, rad / np.sqrt(np.maximum(dc * dc - rad * rad, 1e-12)), np.inf)
        px_s = np.minimum(FILM[1] * ang / tan_v, px_cap)
        size = np.where(allf, np.where(exact, px, 0.0), np.where(reach, px_s, 0.0))
        size = np.where(d < FAR_LIMIT, size, 0.0)
        if vis is not None:
            size = np.where(np.asarray(vis)[:, j].astype(bool), size, 0.0)
        out = np.maximum(out, size / ds[j])
    return out


def island_mask(names, owners, tris, words=ISLAND_WORDS, exclude=(), min_tris=ISLAND_MIN_TRIS):
    """Records whose name or owner holds one of `words` (floating islands and islets) and neither holds one of
    `exclude` (vegetation, hanging roots), with more than min_tris triangles."""
    hit = np.array([any(w in n or w in o for w in words) and not any(x in n or x in o for x in exclude)
                    for n, o in zip(names, owners)], bool).reshape(-1)
    return hit & (np.asarray(tris, float).reshape(-1) > min_tris)


def level_ratio(ratio, levels):
    """The LOD ratio export_web.lod_levels picks for a floor ratio: the smallest of `levels` (descending) that is at
    least the ratio (the last level for a ratio below all of them). A zero floor counts 0 here (no floor)."""
    lv = np.asarray(levels, float)
    r = np.asarray(ratio, float)
    li = np.maximum((lv[None, :] >= r.reshape(-1)[:, None]).sum(1) - 1, 0)
    return np.where(r.reshape(-1) > 0, lv[li], 0.0).reshape(r.shape)


def floor_ratios(tris, px, mask, k, lo, hi):
    """Per record: clip(k * px^2, lo, hi) / source triangles, at most 1, where mask and px > 0; else 0."""
    tris = np.asarray(tris, float).reshape(-1)
    px = np.asarray(px, float).reshape(-1)
    m = np.asarray(mask, bool).reshape(-1) & (px > 0)
    want = np.clip(k * px ** 2, lo, hi)
    return np.where(m, np.minimum(want / np.maximum(tris, 1.0), 1.0), 0.0)


def cap_floors(r, tris, cap, levels=None, base=None):
    """Scale floor ratios r down by one common factor until together they keep at most `cap` triangles (counted at the
    level the LOD rule rounds each up to when `levels` is given). base (per record, <= r, optional): a minimum that is
    scaled only once the part of r above it is gone, so a cap takes triangles from the near islands' big floors before
    any island drops under its minimum. Returns (ratios, dict(n, tris, want, scale)); scale runs from 1 (r) through 0
    (base) to -1 (nothing)."""
    r = np.asarray(r, float).reshape(-1)
    tris = np.asarray(tris, float).reshape(-1)
    base = np.zeros(len(r)) if base is None else np.minimum(np.asarray(base, float).reshape(-1), r)

    def at(s):
        return base + s * (r - base) if s >= 0 else (1.0 + s) * base

    def kept(s):
        rr = at(s)
        return float((tris * (level_ratio(rr, levels) if levels is not None else rr)).sum())
    total = kept(1.0)
    s = 1.0
    if cap <= 0:
        s = -1.0
    elif total > cap:
        a, b = -1.0, 1.0
        for _ in range(50):
            mid = 0.5 * (a + b)
            if kept(mid) <= cap:
                a = mid
            else:
                b = mid
        s = a
    return at(s), dict(n=int((r > 0).sum()), tris=int(round(kept(s))), want=int(round(total)), scale=round(s, 4))


def island_floor(names, owners, tris, px, k, lo, hi, cap, mask=None, exclude=(), min_tris=ISLAND_MIN_TRIS,
                 levels=None):
    """LOD floor ratio per record: triangles = clip(k * px^2, lo, hi) / source triangles (at most 1) for the records
    of island_mask (or `mask`, with more than min_tris triangles) that are on screen (px > 0), 0 for the others, all
    scaled down by one factor so that together they keep at most `cap` triangles (cap_floors: the part above `lo`
    triangles goes first). Returns (ratios, info)."""
    tris = np.asarray(tris, float).reshape(-1)
    m = island_mask(names, owners, tris, exclude=exclude, min_tris=min_tris) if mask is None else (
        np.asarray(mask, bool).reshape(-1) & (tris > min_tris))
    r = floor_ratios(tris, px, m, k, lo, hi)
    return cap_floors(r, tris, cap, levels, base=floor_base(r, tris, lo))


def floor_base(r, tris, lo):
    """The `lo`-triangle part of floor ratios r (cap_floors' base): min(lo / triangles, r) where r > 0."""
    r = np.asarray(r, float).reshape(-1)
    return np.where(r > 0, np.minimum(lo / np.maximum(np.asarray(tris, float).reshape(-1), 1.0), r), 0.0)


def corner_face_angle(cn, fn, loop_face, weights=None):
    """Mean angle in degrees between each corner normal cn (corners x 3) and its face's normal fn[loop_face]
    (faces x 3), weighted by `weights` per corner (e.g. the face area) when given. 0 = flat shading."""
    a = np.asarray(cn, float)
    b = np.asarray(fn, float)[np.asarray(loop_face)]
    a = a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-12)
    b = b / np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-12)
    ang = np.degrees(np.arccos(np.clip((a * b).sum(1), -1.0, 1.0)))
    if len(ang) == 0:
        return 0.0
    w = np.ones(len(ang)) if weights is None else np.asarray(weights, float)
    return float((ang * w).sum() / max(w.sum(), 1e-12))


# ---- vertex-colour weld (the backdrop's corner-domain bake) ---------------------------------------------------

VC_WELD_TOL = 0.01             # m: corners whose vertices lie this close count as one point (concat keeps every item's
                               # own vertices, so the range's chunk cut lines and split_heavy cuts join only by position)
VC_WELD_DEG = 30.0             # deg: corners at one point whose corner normals lie within this of each other share one
                               # colour; a smooth fan has one normal, so only real creases (building corners, the
                               # range's >90 deg lips, flat caps, faces facing_flip turned round) keep their own colour
VC_CREASE_DEG = 60.0           # deg: smooth_corner_normals' crease angle (only when a mesh has no corner normals)
VC_MISSING = 1e-7              # linear radiance: a corner this dark in every channel was never sampled (Cycles left it 0)
VC_TILT_MIN = 0.05             # floor of a corner's tilt weight (see weld_corner_colours)
VC_FLAT_DEG = 0.25             # deg: given corner normals whose mean angle to their own faces is under this are flat (the
                               # bake mesh's custom normals did not survive): weld_corner_colours then rebuilds smooth
                               # ones from the positions, as the offline prediction did, instead of welding only faces
                               # within VC_WELD_DEG of each other (which would keep every 30-60 deg fold split)


def _corner_topology(vi, ls):
    """(face per corner, next corner, previous corner) for a Blender-style (corner verts, loop starts) mesh."""
    vi = np.asarray(vi, np.int64)
    ls = np.asarray(ls, np.int64)
    nl = len(vi)
    lt = np.diff(np.append(ls, nl))
    lf = np.repeat(np.arange(len(ls)), lt)
    k = np.arange(nl) - ls[lf]
    nxt = ls[lf] + (k + 1) % lt[lf]
    prv = ls[lf] + (k - 1) % lt[lf]
    return lf, nxt, prv


def poly_normals(co, vi, ls):
    """(unit normal, area) per polygon by Newell's method (any polygon size, winding as stored)."""
    co = np.asarray(co, np.float64)
    vi = np.asarray(vi, np.int64)
    lf, nxt, _ = _corner_topology(vi, ls)
    p, q = co[vi], co[vi[nxt]]
    t = np.stack([(p[:, 1] - q[:, 1]) * (p[:, 2] + q[:, 2]),
                  (p[:, 2] - q[:, 2]) * (p[:, 0] + q[:, 0]),
                  (p[:, 0] - q[:, 0]) * (p[:, 1] + q[:, 1])], 1)
    n = np.zeros((len(ls), 3))
    np.add.at(n, lf, t)
    ln = np.linalg.norm(n, axis=1)
    return n / np.maximum(ln, 1e-20)[:, None], 0.5 * ln


def corner_angles(co, vi, ls):
    """Interior angle (radians) of each corner's polygon at that corner."""
    co = np.asarray(co, np.float64)
    vi = np.asarray(vi, np.int64)
    _, nxt, prv = _corner_topology(vi, ls)
    a = co[vi[nxt]] - co[vi]
    b = co[vi[prv]] - co[vi]
    c = (a * b).sum(1) / np.maximum(np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1), 1e-20)
    return np.arccos(np.clip(c, -1.0, 1.0))


def point_ids(co, tol=VC_WELD_TOL):
    """Per vertex: the id of its point (positions rounded to `tol`)."""
    q = np.round(np.asarray(co, np.float64) / tol).astype(np.int64)
    _, inv = np.unique(q, axis=0, return_inverse=True)
    return inv.ravel()


def smooth_corner_normals(co, vi, ls, crease_deg=VC_CREASE_DEG, tol=VC_WELD_TOL, max_fan=64):
    """Angle-limited smooth normal per corner from positions only: the area- and angle-weighted mean of the face
    normals at the corner's point (positions welded at `tol`) that lie within crease_deg of the corner's own face.
    Points used by more than max_fan corners use the first max_fan of them."""
    vi = np.asarray(vi, np.int64)
    nl = len(vi)
    lf, _, _ = _corner_topology(vi, ls)
    fn, fa = poly_normals(co, vi, ls)
    ang = corner_angles(co, vi, ls)
    pid = point_ids(co, tol)[vi]
    o = np.argsort(pid, kind="stable")
    ks = pid[o]
    st = np.r_[True, ks[1:] != ks[:-1]]
    gs = np.nonzero(st)[0]
    gid = np.cumsum(st) - 1
    size = np.diff(np.append(gs, nl))
    gpos0 = np.empty(nl, np.int64)                     # position in o of each corner's group's first member
    gpos0[o] = gs[gid]
    gsize = np.empty(nl, np.int64)
    gsize[o] = size[gid]
    cos_c = np.cos(np.radians(crease_deg))
    own = fn[lf]
    acc = np.zeros((nl, 3))
    w_all = (fa[lf] * ang)[:, None] * own
    for j in range(int(min(gsize.max() if nl else 0, max_fan))):
        m = np.nonzero(gsize > j)[0]
        other = o[gpos0[m] + j]
        ok = (own[m] * own[other]).sum(1) >= cos_c
        acc[m[ok]] += w_all[other[ok]]
    ln = np.linalg.norm(acc, axis=1)
    return np.where(ln[:, None] > 1e-20, acc / np.maximum(ln, 1e-20)[:, None], own)


def normal_clusters(key, cn, deg=VC_WELD_DEG):
    """Per corner: the id (a member corner's index) of its cluster. Corners join a cluster when they share `key`
    (their point, and their face group) and their normal lies within `deg` of the cluster's first corner's normal
    (greedy: the first unassigned corner of each key seeds the next cluster)."""
    key = np.asarray(key, np.int64)
    n = np.asarray(cn, np.float64)
    n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-20)
    cos_d = np.cos(np.radians(deg))
    cl = np.full(len(key), -1, np.int64)
    un = np.arange(len(key))
    while len(un):
        k = key[un]
        o = np.argsort(k, kind="stable")
        ks = k[o]
        st = np.r_[True, ks[1:] != ks[:-1]]
        seed_of_group = un[o[st]]
        seed = np.empty(len(un), np.int64)
        seed[o] = seed_of_group[np.cumsum(st) - 1]
        ok = ((n[un] * n[seed]).sum(1) >= cos_d) | (un == seed)
        cl[un[ok]] = seed[ok]
        un = un[~ok]
    return cl


def weld_corner_colours(co, vi, ls, col, cn=None, group=None, tol=VC_WELD_TOL, deg=VC_WELD_DEG,
                        crease_deg=VC_CREASE_DEG, missing=VC_MISSING, tilt_min=VC_TILT_MIN, flat_deg=VC_FLAT_DEG):
    """One colour per smooth point for a corner-domain vertex-colour bake.

    A corner-domain bake samples every triangle corner on its own (the bake_web backdrop: 'bake_col', CORNER), and
    corners at one point disagree by 24-31 % (the sample sits at the vertex but is shaded with its own triangle's
    geometry), so every triangle showed its own three colours. Here the corners that share a point (positions within
    `tol`), a face group (`group` per face, e.g. glow faces apart) and a normal (within `deg`, normal_clusters) take
    the weighted mean of their colours. Weights: the corner's interior angle x max(dot(face normal, corner normal),
    tilt_min)^2, so sliver / fold triangles tilted away from the smooth surface count little; corners at or below
    `missing` in every channel (never sampled: Cycles left them black) count 0 and take the mean of the others; so do
    non-finite corners (a NaN would otherwise spread to its whole cluster; one left alone is written as 0). A
    cluster with no sampled corner stays black (the page's fillMissingColors fills it, as before).

    co: (nv, 3) vertex positions (world); vi: (nl,) corner vertex index; ls: (nf,) loop starts; col: (nl, 3 or 4)
    linear colours per corner (a 4th channel is passed through); cn: (nl, 3) corner normals or None
    (smooth_corner_normals with crease_deg). Given corner normals that are flat (mean angle to their faces under
    flat_deg: the custom normals were lost) are replaced the same way. Returns (colours (nl, k), info dict)."""
    col = np.asarray(col, np.float64)
    vi = np.asarray(vi, np.int64)
    nl = len(vi)
    info = dict(corners=int(nl))
    if nl == 0:
        return col.copy(), info
    lf, _, _ = _corner_topology(vi, ls)
    fn, _ = poly_normals(co, vi, ls)
    if cn is not None:
        cn = np.asarray(cn, np.float64).reshape(nl, 3)
        bad = ~np.isfinite(cn).all(1) | (np.linalg.norm(np.nan_to_num(cn), axis=1) < 1e-6)
        if bad.any():
            cn = cn.copy()
            cn[bad] = fn[lf[bad]]
        c0 = cn / np.maximum(np.linalg.norm(cn, axis=1, keepdims=True), 1e-20)
        given = float(np.degrees(np.arccos(np.clip((fn[lf] * c0).sum(1), -1, 1))).mean())
        info["given_corner_face_deg"] = round(given, 2)
        info["normals"] = "corner normals (%d zero -> face normal)" % int(bad.sum())
        if given < flat_deg:
            cn = None
            info["normals"] = "corner normals flat (%.2f deg) -> smooth_corner_normals %g deg" % (given, crease_deg)
    if cn is None:
        cn = smooth_corner_normals(co, vi, ls, crease_deg, tol)
        info.setdefault("normals", "smooth_corner_normals %g deg" % crease_deg)
    key = point_ids(co, tol)[vi]
    if group is not None:
        g = np.asarray(group, np.int64)[lf]
        _, key = np.unique(np.stack([key, g], 1), axis=0, return_inverse=True)
        key = key.ravel()
    cl = normal_clusters(key, cn, deg)
    fin = np.isfinite(col[:, :3]).all(1)
    rgb = np.where(fin[:, None], col[:, :3], 0.0)
    miss = (rgb <= missing).all(1)
    cnu = cn / np.maximum(np.linalg.norm(cn, axis=1, keepdims=True), 1e-20)
    tilt = np.maximum((fn[lf] * cnu).sum(1), tilt_min)
    w = corner_angles(co, vi, ls) * tilt * tilt
    w = np.where(miss, 0.0, np.maximum(w, 1e-12))
    sw = np.bincount(cl, w, minlength=nl)
    avg = np.stack([np.bincount(cl, w * rgb[:, k], minlength=nl) for k in range(3)], 1)
    have = sw > 0
    avg[have] /= sw[have][:, None]
    out = col.copy()
    out[:, :3] = np.where(have[cl][:, None], avg[cl], rgb)
    lum = np.array([0.2126, 0.7152, 0.0722])
    ok = ~miss
    rel = np.abs((out[:, :3] - rgb) @ lum)[ok] / np.maximum(rgb[ok] @ lum, 1e-6)
    npts = len(np.unique(key))
    ncl = len(np.unique(cl))
    # mean angle between corner and face normals: ~0 means the corner normals were flat (no smooth fans), so only the
    # deg limit (not the mesh's own smoothing) decided which corners joined
    info["corner_face_deg"] = round(float(np.degrees(np.arccos(np.clip((fn[lf] * cnu).sum(1), -1, 1))).mean()), 2)
    info.update(points=int(npts), clusters=int(ncl), split_points=int(ncl - npts), nonfinite=int((~fin).sum()),
                missing_before=int(miss.sum()), missing_after=int((out[:, :3] <= missing).all(1).sum()),
                filled=int((miss & have[cl]).sum()),
                rel_change_median=round(float(np.median(rel)), 4) if len(rel) else 0.0)
    return out, info


# ---- round 2 bake quality: small props as vertex colours, duplicates, roof sheets, flips by patch ---------------

VC_FILL_PASSES = 8             # rings of neighbours a sampled colour may spread over (fill_missing_corners)
VC_FILL_SHADE = 0.8            # a filled corner's colour x this: a corner left unsampled sits in a contact (a prop's
                               # foot in the floor, a bracket in the beam), where the atlas texels beside it are darker
DUP_TOL = 1e-4                 # m: corners this close count as one point for duplicate_faces
TINY_AREA = 1e-7               # m^2: faces under this (0.1 mm^2) never cover a pixel's centre at any reachable view


def fill_missing_corners(co, vi, ls, col, missing=VC_MISSING, passes=VC_FILL_PASSES, shade=VC_FILL_SHADE,
                         tol=VC_WELD_TOL):
    """Unsampled corners of a corner-domain vertex-colour bake (at or below `missing` in every channel, or not
    finite) take the mean of the sampled corners of their own face, then of the corners at their point (positions
    within `tol`, any normal), times `shade`; filled corners count as sampled in the next of up to `passes` passes.
    Corners no pass reaches stay as they are (the page's fillMissingColors gives them the mesh's median).
    co (nv, 3), vi (nl,), ls (nf,), col (nl, 3 or 4; a 4th channel is passed through). Returns (colours, info)."""
    col = np.asarray(col, np.float64)
    vi = np.asarray(vi, np.int64)
    nl = len(vi)
    out = col.copy()
    info = dict(corners=int(nl), missing=0, filled=0, left=0)
    if nl == 0:
        return out, info
    lf, _, _ = _corner_topology(vi, ls)
    rgb = out[:, :3]
    fin = np.isfinite(rgb).all(1)
    rgb[~fin] = 0.0
    known = ~((rgb <= missing).all(1))
    info["missing"] = int((~known).sum())
    if known.all() or not known.any():
        info["left"] = int((~known).sum())
        return out, info
    pid = point_ids(co, tol)[vi]
    _, pk = np.unique(pid, return_inverse=True)
    pk = pk.ravel()
    nf, npk = len(ls), int(pk.max()) + 1
    for _ in range(int(passes)):
        before = int(known.sum())
        for key, n in ((lf, nf), (pk, npk)):
            w = known.astype(float)
            sw = np.bincount(key, w, n)
            if not (sw > 0).any():
                continue
            s = np.stack([np.bincount(key, w * rgb[:, k], n) for k in range(3)], 1)
            take = ~known & (sw[key] > 0)
            if take.any():
                rgb[take] = s[key[take]] / sw[key[take]][:, None] * shade
                known |= take
        if int(known.sum()) == before:
            break
    info["filled"] = int(info["missing"] - (~known).sum())
    info["left"] = int((~known).sum())
    return out, info


def duplicate_faces(co, vi, ls, tol=DUP_TOL):
    """Per face: True when an earlier face has the same corners (positions within `tol`; any order, any winding).
    Exact copies (an object built twice in place, a twin panel with the other winding) z-fight on the page, baked a
    different shade each; the first one is kept."""
    vi = np.asarray(vi, np.int64)
    ls = np.asarray(ls, np.int64)
    nl, nf = len(vi), len(ls)
    out = np.zeros(nf, bool)
    if nf < 2:
        return out
    lt = np.diff(np.append(ls, nl))
    pid = point_ids(co, tol)[vi]
    for k in np.unique(lt):
        f = np.nonzero(lt == k)[0]
        if len(f) < 2:
            continue
        rows = np.sort(pid[ls[f][:, None] + np.arange(int(k))[None, :]], axis=1)
        _, first, inv = np.unique(rows, axis=0, return_index=True, return_inverse=True)
        out[f[first[inv.ravel()] != np.arange(len(f))]] = True
    return out


def tiny_faces(co, vi, ls, min_area=TINY_AREA):
    """Per face: True when its area (Newell) is under min_area."""
    _, a = poly_normals(co, vi, ls)
    return a < min_area


def sheet_project(co, vi, ls, comp, max_tilt_deg=85.0):
    """Planar UVs for sheets: every face with comp >= 0 (its sheet's id; -1 = not a sheet face) is projected onto
    its sheet's plane (normal = the area-weighted mean of the sheet's face normals) in that plane's own 2D basis, so a
    whole roof slope (one height field over its plane: arch.py's corrugated tile surfaces) becomes one island. A face
    tilted more than max_tilt_deg from its plane (the tube tiles' flanks, up to ~75 deg, and the fascia stay in), or
    whose projection turns over (its signed area against the sheet's), gets ok False for the caller's other
    projection. Steep faces get fewer texels across; pack_shelf scales each island to its true area.
    Returns (uv per corner (nl, 2) float64, zeros where not ok; ok per face)."""
    co = np.asarray(co, np.float64)
    vi = np.asarray(vi, np.int64)
    comp = np.asarray(comp, np.int64)
    nl, nf = len(vi), len(ls)
    uv = np.zeros((nl, 2))
    ok = np.zeros(nf, bool)
    on = comp >= 0
    if not on.any():
        return uv, ok
    lf, nxt, _ = _corner_topology(vi, ls)
    fn, fa = poly_normals(co, vi, ls)
    ids, cid = np.unique(comp[on], return_inverse=True)
    nc = len(ids)
    cf = np.full(nf, -1, np.int64)
    cf[on] = cid.ravel()
    acc = np.zeros((nc, 3))
    np.add.at(acc, cf[on], fn[on] * fa[on][:, None])
    ln = np.linalg.norm(acc, axis=1)
    n = acc / np.maximum(ln, 1e-20)[:, None]
    good_c = ln > 1e-12
    ref = np.where(np.abs(n[:, 2:3]) < 0.9, [[0.0, 0.0, 1.0]], [[1.0, 0.0, 0.0]])
    bu = np.cross(ref, n)
    bu /= np.maximum(np.linalg.norm(bu, axis=1, keepdims=True), 1e-20)
    bv = np.cross(n, bu)
    lc = cf[lf]
    m = lc >= 0
    p = co[vi[m]]
    uv[m, 0] = (p * bu[lc[m]]).sum(1)
    uv[m, 1] = (p * bv[lc[m]]).sum(1)
    tilt = np.full(nf, -1.0)
    tilt[on] = (fn[on] * n[cf[on]]).sum(1)
    # signed area of each face's projection (shoelace over its corners)
    cr = uv[:, 0] * uv[nxt, 1] - uv[nxt, 0] * uv[:, 1]
    sa = 0.5 * np.bincount(lf, cr, nf)
    ok = on & good_c[np.maximum(cf, 0)] & (tilt >= np.cos(np.radians(max_tilt_deg))) & (sa > 0)
    uv[~ok[lf]] = 0.0
    return uv, ok


def island_dims(u, isl, n=None):
    """Per island (isl: island id per corner): (long side, short side) of its corners u (corners x 2) along their
    principal axes (pack_shelf's layout, before its min_texels stretch). Returns an (n, 2) array."""
    u = np.asarray(u, np.float64)
    isl = np.asarray(isl, np.int64)
    n = (int(isl.max()) + 1 if len(isl) else 0) if n is None else int(n)
    out = np.zeros((n, 2))
    if len(isl) == 0:
        return out
    o = np.argsort(isl, kind="stable")
    ks = isl[o]
    st = np.nonzero(np.r_[True, ks[1:] != ks[:-1]])[0]
    gid = ks[st]
    cnt = np.diff(np.append(st, len(ks)))
    uu = u[o]
    mean = np.add.reduceat(uu, st) / cnt[:, None]
    g = np.repeat(np.arange(len(st)), cnt)
    d = uu - mean[g]
    cxx = np.add.reduceat(d[:, 0] * d[:, 0], st)
    cyy = np.add.reduceat(d[:, 1] * d[:, 1], st)
    cxy = np.add.reduceat(d[:, 0] * d[:, 1], st)
    th = 0.5 * np.arctan2(2 * cxy, cxx - cyy)
    c, s = np.cos(-th)[g], np.sin(-th)[g]
    r = np.stack([d[:, 0] * c - d[:, 1] * s, d[:, 0] * s + d[:, 1] * c], 1)
    wh = np.maximum.reduceat(r, st) - np.minimum.reduceat(r, st)
    out[gid] = np.stack([wh.max(1), wh.min(1)], 1)
    return out


def group_vote(group, flag, weight=None):
    """Per element: True when the weighted share of `flag` among the elements of its group is over one half."""
    g = np.asarray(group, np.int64)
    f = np.asarray(flag, bool)
    if len(g) == 0:
        return np.zeros(0, bool)
    w = np.ones(len(g)) if weight is None else np.asarray(weight, float)
    n = int(g.max()) + 1
    yes = np.bincount(g, w * f, n)
    tot = np.bincount(g, w, n)
    return (yes > 0.5 * tot)[g]
