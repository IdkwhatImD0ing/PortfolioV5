"""Round 32, lane 'plaque': the gate plaque says 日月神教 (the Sun Moon Divine Sect) instead of 明教, in an existing
out/sect_chase.blend, so it matches what a fresh build of sect/areas/gate.py makes. Run on the cloud box, on a copy
first, after the round-12 and round-24 patches:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r32_plaque.py [-- DRY_RUN=1] [SCAN=0]

Why (owner, 2026-10-23): the sect is renamed 明教 / the Ming Sect -> 日月神教 / the Sun Moon Divine Sect (Ren Woxing's
sect in 笑傲江湖; 日月 sun and moon, 神 divine). gate.AREA['title_zh'] is now 日月神教. Four characters, read left to
right as before, in the same KaiTi gold on the dark lacquer board. A name longer than the three characters the plaque
zone was designed for keeps its board gate.PLAQUE_LONG_H of the zone's height (2.0 m, as tall as the sun and moon
medallions) and grows wider (gate.plaque_width: 4.17 -> 6.56 m); the medallions re-centre between the wider board and
the centre bay's columns (gate.sun_moon_layout: 0.40 m from the board, 0.44 m from the columns), so the row reads sun,
name, moon with even gaps. The characters are gate.PLAQUE_TEXT_SCALE (1.2) larger across the board than props.plaque
sets them, so each reads 24-30 px tall at the hold (93, 1600 x 900; 日 was 20 px at props.plaque's size).

What it does:
- the plaque: a fresh gate.build_plaque (props.plaque of the new name, its text scaled, then gate.inlay_plaque_text) is
  built in a scratch collection and its board, frame, relief and text meshes replace the meshes of
  'gate.plaque.board/.frame/.relief/.text'.
  Same objects, names, parents, transforms and material slots; the old meshes are freed.
- the inlay (round 12's flicker rule): the gold characters are set into the board. props.plaque put them 1 mm in front of
  the board with the board's face whole under them; now the board's face is cut away under every character and the
  text sits back until the board's face crosses its straight walls. No face is left under the gold and no slit behind
  it (gate.inlay_plaque_text).
- the medallions: 'gate.sun_medallion' and 'gate.moon_medallion' move along x to gate.sun_moon_layout's places for the
  new board. Their meshes do not change (their radius follows the zone's height only).
No object is added or removed.

State: the plaque's four meshes must equal either the 明教 build (props.plaque at gate.plaque_width, not inlaid: what the
file has had since patch_gate_plaque) or this build, compared face by face (order-free), and each medallion must stand at
the old layout or the new one; anything else stops the patch. Idempotent: on this build's file it prints 'PATCH nothing
changed: not saving' and the same DIGEST.

Checks (any failure stops the patch before saving; DRY_RUN=1 runs everything and never saves):
- the text: four characters left to right, gold, in the board's middle; the board as tall as the medallions;
- inlaid: rays from the gold's face back into the board meet no front face of the board (cut under every character);
  every point of the holes' rims lies inside the gold (rays from it to the front and to the back both meet the text),
  so no hole shows; the board's only open edges are those rims, in its front plane; the text's back is behind the
  board's face;
- the medallions: at gate.sun_moon_layout, at least GAP_MIN from the plaque's frame and from the columns;
- clear: the plaque touches nothing but its own parts and stays CLEAR_MIN from everything else; the medallions touch
  nothing but the plaque zone's board they hang on ('gate.paifang.beams');
- coplanar scan (SCAN=1): parallel same-facing faces within 5 mm and 5-12 mm (12-20 mm and back-to-back within 5 mm
  logged), the plaque's parts and the medallions against themselves and everything near them, before and after; none
  may be gained (NEW_MAX);
- reading: chase.cam at the hold (93), 1600 x 900: every character wholly in the frame, at least READ_SEEN of it
  unhidden and at least READ_MIN_PX tall; the climb (READ_FRAMES) is logged;
- names and counts: same objects, names, parents and material slots; no scratch data left.
Prints 'PATCH CACHES ok' (world boxes kept) or 'PATCH CACHES needs audit' (the wider plaque and the moved medallions: the
'sun-moon' lore box moves; export_web audit, then chunks,meta, then bake_web bakefull for the gate chunk and the backdrop,
then pack), and 'PATCH DIGEST <md5>' of the plaque's parts and the medallions (order-free).
"""
import hashlib
import os
import sys
import time
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402  (CAMERA)
from sect.areas import gate as G  # noqa: E402
from sect.lib import props as P  # noqa: E402

PLAQUE = "gate.plaque"
PAIFANG = "gate.paifang"
OLD_TEXT = "明教"           # the name the file's plaque had until round 32
MEDALS = ("gate.sun_medallion", "gate.moon_medallion")
BEAMS = "gate.paifang.beams"   # the plaque zone's board the medallions hang on (their backs sink 2 cm into it)
TMP = "~r32"
BOX_TOL = 0.01             # m: a world box within this of its old one keeps the export caches valid
SCAN_TOL = 0.0055          # m: parallel faces within 5 mm (as patch_r12_areas / patch_r24_swords)
SCAN_TOL12 = 0.0125        # m: the far-only band out to 12 mm
SCAN_TOL20 = 0.0205        # m: logged band out to 20 mm (round 12's 2 cm rule)
SCAN_PAR = 0.985           # |cos| between two faces counted as parallel
SCAN_STEP = 0.03           # m between samples
NEW_MAX = 0.02             # m2: same-facing overlap (<= 12 mm) a piece may gain against anything
CARVE_DEPTH = 0.10         # m: behind the gold's face, no front face of the board within this (the gold is ~6 cm)
RIM_PTS = 4                # samples per open edge of the board (its hole rims)
GAP_MIN = 0.25             # m: each medallion this clear of the plaque's frame and of the centre bay's columns
TEXT_MARGIN = 0.05         # m: the gold this far inside the board's face on every side
CLEAR_MIN = 0.03           # m: the plaque this clear of everything but its own parts (the zone board 5-6 cm behind)
HOLD_FRAME = 93            # the gate's hold
READ_FRAMES = (75, 85)     # climb frames, logged
READ_MIN_PX = 20.0         # a character's height at the hold (this build: about 24 px)
READ_SEEN = 0.95           # share of a character's samples a ray from the camera reaches
RES = (1600, 900)
PLACE_TOL = 1e-4


def log(*a):
    print("PATCH", *a, flush=True)


def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    dry, scan = False, True
    for a in argv:
        k, eq, v = a.partition("=")
        if k == "DRY_RUN" and eq:
            dry = v.strip().lower() not in ("", "0", "false", "no")
        elif k == "SCAN" and eq:
            scan = v.strip().lower() not in ("", "0", "false", "no")
        else:
            raise SystemExit("patch_r32_plaque: unknown option %r (DRY_RUN=1, SCAN=0)" % a)
    return dry, scan


class Fail(list):
    def add(self, msg):
        log("FAIL", msg)
        self.append(msg)


# ------------------------------------------------------------------------------------------------------ mesh helpers

def tris(me):
    n = len(me.polygons)
    lt = np.zeros(n, np.int32)
    me.polygons.foreach_get("loop_total", lt)
    return int(lt.sum() - 2 * n)


def local_tris(me):
    """(n, 3, 3) local triangles and the material index of each."""
    try:
        me.calc_loop_triangles()
    except Exception:  # noqa: BLE001  (evaluated meshes have them already)
        pass
    nv, nt = len(me.vertices), len(me.loop_triangles)
    co = np.empty(nv * 3)
    me.vertices.foreach_get("co", co)
    tv = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", tv)
    mi = np.empty(nt, np.int64)
    me.loop_triangles.foreach_get("material_index", mi)
    return co.reshape(nv, 3)[tv.reshape(nt, 3)], mi


def faces_sig(me):
    """Order-free fingerprint of a mesh: every face as its rounded vertex coordinates (cyclic, from its smallest
    corner) and its material slot's material name, sorted; plus the counts."""
    nv = len(me.vertices)
    co = np.empty(nv * 3)
    me.vertices.foreach_get("co", co)
    q = np.round(co.reshape(nv, 3) * 1e4).astype(np.int64)
    mats = [m.name if m is not None else "" for m in me.materials]
    out = []
    for p in me.polygons:
        pts = [tuple(q[i]) for i in p.vertices]
        k = pts.index(min(pts))
        out.append((tuple(pts[k:] + pts[:k]), mats[p.material_index] if p.material_index < len(mats) else ""))
    out.sort()
    h = hashlib.md5()
    h.update(("%d %d" % (nv, len(me.polygons))).encode())
    for f, m in out:
        h.update(repr(f).encode())
        h.update(m.encode())
    return h.hexdigest()


def world_box(ob):
    M = ob.matrix_world
    pts = [M @ Vector(c) for c in ob.bound_box]
    return (np.array([min(p[k] for p in pts) for k in range(3)]), np.array([max(p[k] for p in pts) for k in range(3)]))


def tri_normals(T):
    cr = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    L = np.linalg.norm(cr, axis=1)
    ok = L > 1e-12
    n = np.zeros_like(cr)
    n[ok] = cr[ok] / L[ok, None]
    return n, 0.5 * L


def bvh(T):
    return BVHTree.FromPolygons([Vector(p) for p in T.reshape(-1, 3)], [(3 * i, 3 * i + 1, 3 * i + 2)
                                                                       for i in range(len(T))], all_triangles=True)


def open_edges(me):
    """(a, b) local coordinates of every edge in fewer or more than two faces."""
    bm = bmesh.new()
    bm.from_mesh(me)
    out = [(e.verts[0].co.copy(), e.verts[1].co.copy()) for e in bm.edges if len(e.link_faces) != 2]
    bm.free()
    return out


def medal_meshes(ob):
    return [c for c in sorted(ob.children, key=lambda o: o.name) if c.type == 'MESH']


# ----------------------------------------------------------------------------------------------------------- builds

def build_plaque(text, legacy, anchor, pf):
    """The plaque gate.py builds for ``text`` (legacy: as before round 32, props.plaque alone), in a scratch collection
    under ``anchor`` (so its world matrices are the file's). Returns (collection, root, {part: object})."""
    coll = bpy.data.collections.new(TMP + ".coll")
    bpy.context.scene.collection.children.link(coll)
    root = G.build_plaque(coll, text, float(pf["plaque_size"][0]), float(pf["plaque_size"][1]), TMP + ".plaque",
                          parent=anchor, legacy=legacy)
    _pivot, parts = G.plaque_parts(root)
    return coll, root, parts


def drop(coll):
    for ob in list(coll.all_objects):
        me = ob.data if ob.type == 'MESH' else None
        bpy.data.objects.remove(ob, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    bpy.data.collections.remove(coll)


def medal_layout(pf, anchor, plaque_root):
    """{object name: (part, radius, local location)} of the medallions for the plaque ``plaque_root``."""
    lay = G.sun_moon_layout(pf, anchor, plaque_root)
    return {G.K + "." + nm: (part, rm, loc) for part, rm, _parent, loc, nm in lay["medallions"]}


def place_state(ob, old, new):
    have = np.array(ob.location)
    if np.abs(have - np.array(new)).max() <= PLACE_TOL:
        return "new"
    if np.abs(have - np.array(old)).max() <= PLACE_TOL:
        return "old"
    return "unknown"


# ----------------------------------------------------------------------------------------------------------- checks

def char_split(T, n):
    """Split the gold's front triangles ``T`` (local, the plaque reads along +x) into ``n`` characters, left to right:
    the x-intervals of all triangles merged into runs of ink, cut at the n - 1 widest gaps between runs (the gaps
    between characters are wider than those inside one, e.g. 神's 礻 and 申). Returns [mask] or None (fewer runs)."""
    lo, hi = T[:, :, 0].min(1), T[:, :, 0].max(1)
    order = np.argsort(lo)
    runs = []
    for i in order:
        if runs and lo[i] <= runs[-1][1] + 1e-6:
            runs[-1][1] = max(runs[-1][1], hi[i])
        else:
            runs.append([lo[i], hi[i]])
    if len(runs) < n:
        return None
    gaps = sorted(range(len(runs) - 1), key=lambda k: -(runs[k + 1][0] - runs[k][1]))[:n - 1]
    cuts = sorted(0.5 * (runs[k][1] + runs[k + 1][0]) for k in gaps)
    c = T.mean(1)[:, 0]
    bounds = [-np.inf] + cuts + [np.inf]
    return [(c > bounds[k]) & (c < bounds[k + 1]) for k in range(n)]


def check_text(parts, medal_r, fail):
    """Four characters left to right in the board's middle, gold; the board as tall as the medallions."""
    text = parts["text"].data
    T, mi = local_tris(text)
    nrm, area = tri_normals(T)
    front = nrm[:, 1] < -0.99
    n = len(G.AREA["title_zh"])
    TF, AF = T[front], area[front]
    x0, x1 = float(TF[:, :, 0].min()), float(TF[:, :, 0].max())
    masks = char_split(TF, n)
    if masks is None:
        fail.add("text: fewer than %d separate characters on the gold's face" % n)
        masks = [np.ones(len(TF), bool)] * n
    cells = []
    for s in masks:
        cells.append((float(AF[s].sum()), float(TF[s][:, :, 2].min()) if s.any() else 0.0,
                      float(TF[s][:, :, 2].max()) if s.any() else 0.0,
                      float(TF[s][:, :, 0].min()) if s.any() else 0.0, float(TF[s][:, :, 0].max()) if s.any() else 0.0))
    board = parts["board"].data
    bco = np.array([v.co for v in board.vertices])
    bw, bh = float(bco[:, 0].max() - bco[:, 0].min()), float(bco[:, 2].max() - bco[:, 2].min())
    fco = np.array([v.co for v in parts["frame"].data.vertices])
    fw, fh = float(fco[:, 0].max() - fco[:, 0].min()), float(fco[:, 2].max() - fco[:, 2].min())
    mats = [m.name for m in text.materials]
    log("text %s: %d characters left to right at x %s m, gold face %s m2, %s m tall; the text %.3f m wide on a board "
        "%.3f x %.3f m, frame %.3f x %.3f m (the medallions %.3f m across); materials %s" % (
            G.AREA["title_zh"], n, " / ".join("%.3f..%.3f" % (c[3], c[4]) for c in cells),
            "/".join("%.3f" % c[0] for c in cells), "/".join("%.3f" % (c[2] - c[1]) for c in cells), x1 - x0, bw, bh,
            fw, fh, 2 * medal_r, mats))
    if any(c[0] < 0.02 or c[2] - c[1] < 0.5 for c in cells):
        fail.add("text: a character has too little gold face or height (%s)" % [(round(c[0], 3), round(c[2] - c[1], 3))
                                                                             for c in cells])
    tco = np.array([v.co for v in text.vertices])         # the whole gold, walls and bevels included
    tx, tz = float(np.abs(tco[:, 0]).max()), float(np.abs(tco[:, 2]).max())
    log("text: the gold reaches x +-%.3f, z +-%.3f m; the board's face x +-%.3f, z +-%.3f m (margins %.3f, %.3f m)" % (
        tx, tz, bw / 2, bh / 2, bw / 2 - tx, bh / 2 - tz))
    if abs(x0 + x1) > 0.05 or bw / 2 - tx < TEXT_MARGIN or bh / 2 - tz < TEXT_MARGIN:
        fail.add("text: not centred on the board with %.2f m to spare (x %.3f..%.3f, gold to +-%.3f / +-%.3f m)" % (
            TEXT_MARGIN, x0, x1, tx, tz))
    if mats != ["M.gold"]:
        fail.add("text: materials %s, want ['M.gold']" % mats)
    if abs(fh - 2 * medal_r) > 0.05:
        fail.add("plaque: %.3f m tall, the medallions %.3f m (gate.PLAQUE_LONG_H)" % (fh, 2 * medal_r))
    return cells


def check_inlay(parts, fail):
    """Carved: no front face of the board behind the gold's face; the holes' rims inside the gold; the board open only
    there; the text's back behind the board's face. Everything in the pivot's frame (all four parts share it)."""
    board, text = parts["board"].data, parts["text"].data
    Tb, _ = local_tris(board)
    Tt, _ = local_tris(text)
    nb, _ab = tri_normals(Tb)
    nt, at = tri_normals(Tt)
    tb, tt = bvh(Tb), bvh(Tt)
    tag_b, tag_t = board.get(G.PLAQUE_INLAY_TAG), text.get(G.PLAQUE_INLAY_TAG)
    if tag_b is None or tag_t is None or abs(tag_b - tag_t) > 1e-9:
        fail.add("inlay: tags %s / %s (gate.PLAQUE_INLAY_TAG)" % (tag_b, tag_t))
    yb = float(Tt[:, :, 1].max())
    yf = float(Tt[:, :, 1].min())
    if yb <= 0.0:
        fail.add("inlay: the text's back at y %.4f is not behind the board's face (y 0)" % yb)
    # carved: from the gold's front face straight back
    rng = np.random.default_rng(32)
    under, n_s = 0, 0
    for i in np.nonzero((nt[:, 1] < -0.99) & (at > 1e-9))[0]:
        k = int(min(6, max(1, round(at[i] / 0.0004))))
        u, v = rng.random(k), rng.random(k)
        f = u + v > 1.0
        u[f], v[f] = 1.0 - u[f], 1.0 - v[f]
        for p in Tt[i, 0] + np.outer(u, Tt[i, 1] - Tt[i, 0]) + np.outer(v, Tt[i, 2] - Tt[i, 0]):
            n_s += 1
            loc, hn, fi, d = tb.ray_cast(Vector(p) + Vector((0.0, 1e-4, 0.0)), Vector((0.0, 1.0, 0.0)), CARVE_DEPTH)
            if loc is not None and nb[fi][1] < -0.9:
                under += 1
    if not n_s or under > 0.01 * n_s:
        fail.add("inlay: %d of %d points of the gold have a board face behind them (not cut)" % (under, n_s))
    # the board's open edges: only the hole rims, in its front plane, each inside the gold
    rims = open_edges(board)
    off = [e for e in rims if abs(e[0].y) > 2e-5 or abs(e[1].y) > 2e-5]
    if off:
        fail.add("inlay: %d open edges of the board are not in its front plane (first %s)" % (len(off), off[0]))
    shown, n_r = 0, 0
    for a, b in rims:
        for t in (np.arange(RIM_PTS) + 0.5) / RIM_PTS:
            p = a.lerp(b, float(t))
            n_r += 1
            fwd = tt.ray_cast(p + Vector((0.0, -1e-5, 0.0)), Vector((0.0, -1.0, 0.0)), 1.0)
            back = tt.ray_cast(p + Vector((0.0, 1e-5, 0.0)), Vector((0.0, 1.0, 0.0)), 1.0)
            if fwd[0] is None or back[0] is None:
                shown += 1
    if not n_r or shown:
        fail.add("inlay: %d of %d points on the holes' rims are not inside the gold (a hole would show)" % (shown, n_r))
    log("inlay: the gold stands %.4f m proud of the board's face, its back %.4f m behind it (sunk %.4f m); %d of %d "
        "points of its face have no board face behind them; the board is open only along %d rim edges in its face, "
        "%d of %d rim points inside the gold" % (-yf, yb, tag_t or 0.0, n_s - under, n_s, len(rims), n_r - shown, n_r))


def world_tris(dg, owners=None, near=None, skip=()):
    """{owner: (n, 3, 3) world triangles} of the evaluated scene's meshes: these owners, or those whose box meets the
    box ``near`` (lo, hi)."""
    out = {}
    for inst in dg.object_instances:
        o = inst.object
        if o.type != 'MESH':
            continue
        own = inst.parent.original.name if inst.is_instance and inst.parent else o.original.name
        if (owners is not None and own not in owners) or own in skip:
            continue
        W = np.array(inst.matrix_world)
        if near is not None:
            bb = np.array(o.bound_box) @ W[:3, :3].T + W[:3, 3]
            if (bb.min(0) > near[1]).any() or (bb.max(0) < near[0]).any():
                continue
        L, _ = local_tris(o.data)
        if len(L):
            out.setdefault(own, []).append(L @ W[:3, :3].T + W[:3, 3])
    return {k: np.concatenate(v) for k, v in out.items()}


def nearest(Ta, Tb):
    """(distance, crossing triangle pairs) between two world triangle sets."""
    ta, tb = bvh(Ta), bvh(Tb)
    touch = len(ta.overlap(tb))
    d = min(min(tb.find_nearest(Vector(p))[3] for p in Ta.reshape(-1, 3)[::2]),
            min(ta.find_nearest(Vector(p))[3] for p in Tb.reshape(-1, 3)[::2]))
    return d, touch


def check_clear(dg, plaque_names, medal_names, pf, fail):
    """The plaque touches only its own parts and stays CLEAR_MIN from the rest; the medallions touch only the zone
    board, stay GAP_MIN from the plaque's frame and the columns."""
    own = set(plaque_names)
    T = np.concatenate(list(world_tris(dg, owners=own).values()))
    lo, hi = T.reshape(-1, 3).min(0) - 1.0, T.reshape(-1, 3).max(0) + 1.0
    rows = []
    for o, To in world_tris(dg, near=(lo, hi), skip=own).items():
        d, touch = nearest(T, To)
        rows.append((d, o, touch))
        if touch or d < CLEAR_MIN:
            fail.add("plaque: %s is %.3f m from it (%d crossing triangle pairs), want %.2f m" % (o, d, touch, CLEAR_MIN))
    rows.sort()
    log("plaque clear: nearest %s" % ", ".join("%s %.3f m" % (o, d) for d, o, _t in rows[:5]))
    frame = world_tris(dg, owners={PLAQUE + ".frame"})[PLAQUE + ".frame"]
    for root in medal_names:
        mine = {c.name for c in bpy.data.objects[root].children_recursive}
        Tm = np.concatenate(list(world_tris(dg, owners=mine).values()))
        lo, hi = Tm.reshape(-1, 3).min(0) - 1.0, Tm.reshape(-1, 3).max(0) + 1.0
        rows = []
        for o, To in world_tris(dg, near=(lo, hi), skip=mine).items():
            d, touch = nearest(Tm, To)
            rows.append((d, o, touch))
            if touch and o != BEAMS:
                fail.add("%s crosses %s (%d triangle pairs)" % (root, o, touch))
        rows.sort()
        d_frame, _t = nearest(Tm, frame)
        cols = [(d, o) for d, o, _t in rows if o.startswith("gate.paifang.col")]
        d_col = min(cols)[0] if cols else 9.0
        if d_frame < GAP_MIN or d_col < GAP_MIN:
            fail.add("%s: %.3f m from the plaque's frame, %.3f m from a column, want %.2f m" % (root, d_frame, d_col,
                                                                                            GAP_MIN))
        log("%s at x %.3f: %.3f m from the plaque's frame, %.3f m from the column (%s); nearest %s" % (
            root, bpy.data.objects[root].location.x, d_frame, d_col, min(cols)[1] if cols else "-",
            ", ".join("%s %.3f m" % (o, d) for d, o, _t in rows[:4])))


def chars_on_screen(sc, cam, parts, frame):
    """Where each character of the plaque lands at ``frame`` in a 1600 x 900 frame: (x0, x1, y0, y1) px, height px,
    share of its corners in the frame, share of up to 80 of its points a ray from the camera reaches, distance m."""
    from bpy_extras.object_utils import world_to_camera_view
    ob = parts["text"]
    T, _ = local_tris(ob.data)
    nrm, _a = tri_normals(T)
    T = T[nrm[:, 1] < -0.99]
    n = len(G.AREA["title_zh"])
    masks = char_split(T, n) or [np.ones(len(T), bool)] * n
    sc.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    M = ob.matrix_world
    R3 = M.to_3x3()
    cw = cam.matrix_world.translation.copy()
    out = []
    for s in masks:
        V = T[s].reshape(-1, 3)
        pts = [M @ Vector(p) for p in V]
        ndc = [world_to_camera_view(sc, cam, p) for p in pts]
        xs = np.array([v.x * RES[0] for v in ndc])
        ys = np.array([(1.0 - v.y) * RES[1] for v in ndc])
        inside = float(np.mean((xs >= 0) & (xs <= RES[0]) & (ys >= 0) & (ys <= RES[1])))
        seen, m = 0, 0
        for p in V[::max(1, len(V) // 80)]:
            q = M @ Vector(p) + R3 @ Vector((0.0, -0.01, 0.0))      # 1 cm in front of the gold
            d = q - cw
            hit, loc, hn, idx, hob, _ = sc.ray_cast(dg, cw, d.normalized(), distance=d.length + 0.05)
            m += 1
            seen += bool(hit and hob is not None and getattr(hob, "original", hob).name == ob.name)
        mid = M @ Vector(tuple(V.mean(0)))
        out.append(((xs.min(), xs.max(), ys.min(), ys.max()), ys.max() - ys.min(), inside, seen / max(m, 1),
                    (mid - cw).length))
    return out


# ------------------------------------------------------------------------------------------------- the coplanar scan

def scan(dg, names, label):
    """{piece: {other: [same <=5 mm, same 5-12 mm, same 12-20 mm, back-to-back <=5 mm]}} m2 of parallel faces, sampled
    on the piece's triangles against itself ('<self>') and every mesh whose box meets its own (as patch_r24_swords'
    scan, with the 12-20 mm and back-to-back bands logged)."""
    t0 = time.time()
    rows = {}
    for nm in names:
        rng = np.random.default_rng(zlib.crc32(nm.encode()))   # per piece: an unchanged piece samples the same points
        ob = bpy.data.objects[nm]
        oe = ob.evaluated_get(dg)
        me = oe.to_mesh()
        L, _mi = local_tris(me)
        oe.to_mesh_clear()
        M = np.array(ob.matrix_world)
        T = L @ M[:3, :3].T + M[:3, 3]
        lo, hi = T.reshape(-1, 3).min(0) - 0.03, T.reshape(-1, 3).max(0) + 0.03
        others, oid = [], []
        for inst in dg.object_instances:
            o = inst.object
            if o.type != 'MESH':
                continue
            own = inst.parent.original.name if inst.is_instance and inst.parent else o.original.name
            if own == nm:
                continue
            W = np.array(inst.matrix_world)
            bb = np.array(o.bound_box) @ W[:3, :3].T + W[:3, 3]
            if (bb.min(0) > hi).any() or (bb.max(0) < lo).any():
                continue
            Lo, _ = local_tris(o.data)
            if not len(Lo):
                continue
            To = Lo @ W[:3, :3].T + W[:3, 3]
            keep = ~((To.min(1) > hi).any(1) | (To.max(1) < lo).any(1))
            if keep.any():
                others.append(To[keep])
                oid += [own] * int(keep.sum())
        tn = bvh(np.concatenate(others)) if others else None
        ts = bvh(T)
        nrm, ar = tri_normals(T)
        r = rows.setdefault(nm, {})
        for t in np.nonzero(ar > 1e-9)[0]:
            k = int(min(200, max(1, round(ar[t] / (SCAN_STEP * SCAN_STEP)))))
            u, v = rng.random(k), rng.random(k)
            f = u + v > 1.0
            u[f], v[f] = 1.0 - u[f], 1.0 - v[f]
            n = Vector(nrm[t])
            w = ar[t] / k
            for p in T[t, 0] + np.outer(u, T[t, 1] - T[t, 0]) + np.outer(v, T[t, 2] - T[t, 0]):
                p = Vector(p)
                hits = []
                for sgn in (-1.0, 1.0):
                    loc, hn, fi, d = ts.ray_cast(p + n * (sgn * 1e-4), n * sgn, SCAN_TOL20)
                    if loc is not None:
                        hits.append(("<self>", loc, hn))
                    if tn is not None:
                        loc, hn, fi, d = tn.ray_cast(p + n * (sgn * 1e-4), n * sgn, SCAN_TOL20)
                        if loc is not None:
                            hits.append((oid[fi], loc, hn))
                for other, loc, hn in hits:
                    c = hn.dot(n)
                    g = abs((loc - p).dot(n))
                    if abs(c) < SCAN_PAR or g > SCAN_TOL20:
                        continue
                    row = r.setdefault(other, [0.0, 0.0, 0.0, 0.0])
                    if c < 0.0:
                        if g <= SCAN_TOL:
                            row[3] += w
                        continue
                    row[0 if g <= SCAN_TOL else (1 if g <= SCAN_TOL12 else 2)] += w
        tot = [sum(x[i] for x in r.values()) for i in range(4)]
        top = sorted(r.items(), key=lambda kv: -sum(kv[1]))[:5]
        log("scan %s %s: same-facing within 5 mm %.3f m2, 5-12 mm %.3f m2, 12-20 mm %.3f m2; back-to-back within 5 mm "
            "%.3f m2%s" % (label, nm, tot[0], tot[1], tot[2], tot[3], "".join(
                "; %s %.3f + %.3f + %.3f / %.3f" % (o, a, b, c_, d_) for o, (a, b, c_, d_) in top
                if a + b + c_ + d_ >= 0.001)))
    log("scan %s: %d pieces, %.1f s" % (label, len(names), time.time() - t0))
    return rows


# ------------------------------------------------------------------------------------------------------------- main

def digest(obs):
    h = hashlib.md5()
    for ob in sorted(obs, key=lambda o: o.name):
        h.update(ob.name.encode())
        h.update(np.round(np.array(ob.matrix_basis), 6).tobytes())
        if ob.type == 'MESH':
            h.update(ob.data.name.encode())
            h.update(faces_sig(ob.data).encode())
            h.update(repr([s.material.name if s.material else None for s in ob.material_slots]).encode())
    return h.hexdigest()


def main():
    dry, do_scan = options()
    t0 = time.time()
    fail = Fail()
    sc = bpy.context.scene
    keep_frame = sc.frame_current
    plaque = bpy.data.objects.get(PLAQUE)
    pf = bpy.data.objects.get(PAIFANG)
    medals = [bpy.data.objects.get(n) for n in MEDALS]
    if plaque is None or pf is None or None in medals:
        log("NOT SAVED: %s, %s or the medallions %s not found: is this out/sect_chase.blend?" % (PLAQUE, PAIFANG, MEDALS))
        raise SystemExit(1)
    anchor = bpy.data.objects[pf["plaque_anchor"]]
    for ob in [plaque] + medals:
        if ob.parent != anchor:
            fail.add("%s's parent is %s, not %s" % (ob.name, ob.parent.name if ob.parent else None, anchor.name))
    pivot, parts = G.plaque_parts(plaque)
    if fail:
        log("NOT SAVED: the file is not in a state this patch knows")
        raise SystemExit(1)
    text = G.AREA["title_zh"]
    pw, ph = float(pf["plaque_size"][0]), float(pf["plaque_size"][1])
    log("gate.py: title %s (%d characters), board %.3f m wide (plaque zone %.3f x %.3f m, PLAQUE_LONG_H %.2f), text "
        "scale %.2f, inlay %s (wall in %.3f m); the old name %s at %.3f m" % (
            text, len(text), G.plaque_width(pw, text, ph), pw, ph / 0.86, G.PLAQUE_LONG_H, G.PLAQUE_TEXT_SCALE,
            G.PLAQUE_INLAY, G.PLAQUE_WALL_IN, OLD_TEXT, G.plaque_width(pw, OLD_TEXT, ph)))
    if text == OLD_TEXT or not G.PLAQUE_INLAY:
        fail.add("gate.py is not the round-32 build (title %s, PLAQUE_INLAY %s)" % (text, G.PLAQUE_INLAY))
        raise SystemExit(1)
    n_obj0 = len(bpy.data.objects)
    scenes0 = sorted(s.name for s in bpy.data.scenes)
    had_eval = bpy.data.scenes.get(P._EVAL_SCENE) is not None
    plaque_names = [parts[k].name for k in G.PLAQUE_PARTS]
    medal_names = [m.name for ob in medals for m in medal_meshes(ob)]
    watched = [parts[k] for k in G.PLAQUE_PARTS] + medals + [m for ob in medals for m in medal_meshes(ob)]
    before = {}
    for ob in watched:
        before[ob.name] = dict(basis=np.array(ob.matrix_basis), parent=ob.parent.name if ob.parent else None,
                               mesh=ob.data.name if ob.type == 'MESH' else None,
                               slots=[s.material.name if s.material else None for s in ob.material_slots],
                               sig=faces_sig(ob.data) if ob.type == 'MESH' else None,
                               tris=tris(ob.data) if ob.type == 'MESH' else 0,
                               box=world_box(ob) if ob.type == 'MESH' else None)
    for k in G.PLAQUE_PARTS:
        ob = parts[k]
        log("before %s: mesh %s, %d triangles, slots %s, inlaid %s" % (
            ob.name, ob.data.name, tris(ob.data), before[ob.name]["slots"], ob.data.get(G.PLAQUE_INLAY_TAG)))
    for ob in medals:
        log("before %s: at %s" % (ob.name, tuple(round(v, 4) for v in ob.location)))
    dg = bpy.context.evaluated_depsgraph_get()
    scan0 = scan(dg, plaque_names + medal_names, "before") if do_scan else None
    # this round's plaque, and the old one to recognise the file's state
    t1 = time.time()
    new_coll, new_root, new_parts = build_plaque(text, False, anchor, pf)
    new_lay = medal_layout(pf, anchor, new_root)
    sig_new = {k: faces_sig(new_parts[k].data) for k in G.PLAQUE_PARTS}
    old_coll, old_root, old_parts = build_plaque(OLD_TEXT, True, anchor, pf)
    old_lay = medal_layout(pf, anchor, old_root)
    sig_old = {k: faces_sig(old_parts[k].data) for k in G.PLAQUE_PARTS}
    drop(old_coll)
    match = {k: ("new" if before[parts[k].name]["sig"] == sig_new[k] else
                 "old" if before[parts[k].name]["sig"] == sig_old[k] else "unknown") for k in G.PLAQUE_PARTS}
    states = set(match.values())
    p_state = states.pop() if len(states) == 1 else "mixed"
    log("plaque: state %s (%s); this build: %s; %.1f s" % (
        p_state, ", ".join("%s %s" % (k, match[k]) for k in G.PLAQUE_PARTS),
        ", ".join("%s %d triangles" % (k, tris(new_parts[k].data)) for k in G.PLAQUE_PARTS), time.time() - t1))
    if p_state not in ("old", "new"):
        fail.add("the plaque's meshes are neither the 明教 build nor this one (%s)" % match)
    m_state = {}
    for ob in medals:
        part, rm, loc = new_lay[ob.name]
        m_state[ob.name] = place_state(ob, old_lay[ob.name][2], loc)
        log("%s: place %s (file x %.4f; the 明教 layout x %.4f, this one x %.4f; radius %.3f m)" % (
            ob.name, m_state[ob.name], ob.location.x, old_lay[ob.name][2][0], loc[0], rm))
        if m_state[ob.name] == "unknown":
            fail.add("%s is neither at the 明教 layout nor at this one" % ob.name)
    if fail:
        drop(new_coll)
        log("NOT SAVED: the file is not in a state this patch knows (%d problems)" % len(fail))
        raise SystemExit(1)
    todo = p_state == "old" or any(s == "old" for s in m_state.values())
    # apply
    if p_state == "old":
        for k in G.PLAQUE_PARTS:
            ob, src = parts[k], new_parts[k]
            prev = ob.data
            name = prev.name
            me = src.data
            src.data = bpy.data.meshes.new(TMP + ".empty")
            ob.data = me
            for s in ob.material_slots:
                if s.link != 'DATA':
                    s.link = 'DATA'
            if prev.users == 0:
                bpy.data.meshes.remove(prev)
            me.name = name
            log("%s rebuilt: mesh %s, %d triangles (was %d), slots %s" % (
                ob.name, me.name, tris(me), before[ob.name]["tris"],
                [s.material.name if s.material else None for s in ob.material_slots]))
    else:
        log("plaque unchanged (日月神教, inlaid already)")
    for ob in medals:
        if m_state[ob.name] == "old":
            ob.location = new_lay[ob.name][2]
            log("%s moved to x %.4f" % (ob.name, ob.location.x))
    drop(new_coll)
    if not had_eval:
        s_ = bpy.data.scenes.get(P._EVAL_SCENE)
        if s_ is not None and s_ != sc and not len(s_.objects):
            bpy.data.scenes.remove(s_)
    for m in list(bpy.data.meshes):
        if m.users == 0 and m.name.startswith(TMP):
            bpy.data.meshes.remove(m)
    bpy.context.view_layer.update()
    # checks
    medal_r = new_lay[MEDALS[0]][1]
    check_text(parts, medal_r, fail)
    check_inlay(parts, fail)
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in medals:
        if np.abs(np.array(ob.location) - np.array(new_lay[ob.name][2])).max() > PLACE_TOL:
            fail.add("%s at %s, not at gate.sun_moon_layout's %s" % (ob.name, tuple(ob.location), new_lay[ob.name][2]))
    check_clear(dg, plaque_names, MEDALS, pf, fail)
    for ob in watched:
        b = before[ob.name]
        slots = [s.material.name if s.material else None for s in ob.material_slots]
        if slots != b["slots"]:
            fail.add("%s material slots %s, were %s" % (ob.name, slots, b["slots"]))
        if (ob.parent.name if ob.parent else None) != b["parent"]:
            fail.add("%s's parent changed" % ob.name)
        if ob.type == 'MESH' and ob.data.name != b["mesh"]:
            fail.add("%s's mesh is %s, was %s" % (ob.name, ob.data.name, b["mesh"]))
    if abs(pivot.rotation_euler.x - 0.13962634) > 1e-4:
        fail.add("the plaque's tilt is %.4f rad, want props.plaque's 8 deg" % pivot.rotation_euler.x)
    # reading: the hold (every character whole, unhidden, READ_MIN_PX) and the climb (logged)
    cam = bpy.data.objects.get(EW.CAMERA)
    if cam is None:
        fail.add("%s not found" % EW.CAMERA)
    else:
        rx, ry, rp = sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES[0], RES[1], 100
        try:
            for frame in (HOLD_FRAME,) + READ_FRAMES:
                for ch, r in zip(text, chars_on_screen(sc, cam, parts, frame)):
                    (x0, x1, y0, y1), h, inside, seen, dist = r
                    log("read frame %d %s: x %.0f..%.0f y %.0f..%.0f of %dx%d, %.0f px tall, %.0f%% in frame, "
                        "%.0f%% unhidden, %.1f m" % (frame, ch, x0, x1, y0, y1, RES[0], RES[1], h, 100 * inside,
                                                     100 * seen, dist))
                    if frame == HOLD_FRAME and (inside < 1.0 or seen < READ_SEEN or h < READ_MIN_PX):
                        fail.add("%s does not read at the hold %d (%.0f px, %.0f%% in frame, %.0f%% unhidden)"
                                 % (ch, frame, h, 100 * inside, 100 * seen))
        finally:
            sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, rp
            sc.frame_set(keep_frame)
    dg = bpy.context.evaluated_depsgraph_get()
    if do_scan:
        scan1 = scan(dg, plaque_names + medal_names, "after")
        for nm, rows in scan1.items():
            for other, (a, b, c_, d_) in rows.items():
                w = scan0.get(nm, {}).get(other, [0.0, 0.0, 0.0, 0.0])
                if a + b + c_ + d_ + sum(w) >= 0.001:
                    log("scan %s / %s: same-facing %.3f + %.3f (+ %.3f at 12-20 mm), back-to-back %.3f -> %.3f + %.3f "
                        "(+ %.3f), %.3f m2" % (nm, other, w[0], w[1], w[2], w[3], a, b, c_, d_))
                if a + b > w[0] + w[1] + NEW_MAX:
                    fail.add("new same-facing overlap %s / %s: %.3f + %.3f m2 (was %.3f + %.3f)" % (
                        nm, other, a, b, w[0], w[1]))
            for other, w in scan0.get(nm, {}).items():
                if other not in rows and sum(w) >= 0.001:
                    log("scan %s / %s: same-facing %.3f + %.3f (+ %.3f at 12-20 mm), back-to-back %.3f -> none" % (
                        nm, other, w[0], w[1], w[2], w[3]))
    # names and counts
    n_obj1 = len(bpy.data.objects)
    if n_obj1 != n_obj0:
        fail.add("objects %d -> %d" % (n_obj0, n_obj1))
    left = [o.name for o in bpy.data.objects if o.name.startswith(TMP)] + \
        [m.name for m in bpy.data.meshes if m.name.startswith(TMP)] + \
        [c.name for c in bpy.data.collections if c.name.startswith(TMP)] + \
        [m.name for m in bpy.data.meshes if m.name.startswith("~carve")]
    if left:
        fail.add("scratch data left: %s" % left[:8])
    scenes1 = sorted(s.name for s in bpy.data.scenes)
    if scenes1 != scenes0:
        fail.add("scenes %s -> %s" % (scenes0, scenes1))
    log("objects %d -> %d; scenes %s" % (n_obj0, n_obj1, scenes1))
    # caches: a world box that moved or grew (export_web's visibility cache, chunk plan and the sun-moon lore box place
    # records by them)
    stale = []
    for ob in watched:
        if ob.type != 'MESH':
            continue
        lo0, hi0 = before[ob.name]["box"]
        lo1, hi1 = world_box(ob)
        if np.abs(lo1 - lo0).max() > BOX_TOL or np.abs(hi1 - hi0).max() > BOX_TOL:
            stale.append("%s %s..%s -> %s..%s" % (ob.name, lo0.round(2), hi0.round(2), lo1.round(2), hi1.round(2)))
    log("DIGEST", digest(watched))
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail:
            log("  -", f)
        raise SystemExit(1)
    if stale:
        log("CACHES needs audit: world boxes moved or grew: %s - run export_web.py -- audit --profile full, then "
            "chunks,meta (the sun-moon lore box moves), then bake_web.py bakefull for gate and the backdrop, then "
            "pack" % "; ".join(stale))
    else:
        log("CACHES ok: names and world boxes kept%s" % (
            "; re-bake gate and the backdrop, then pack" if todo else "; nothing changed"))
    if not todo:
        log("nothing changed: not saving (%.1f s)" % (time.time() - t0))
        return
    if dry:
        log("DRY_RUN: checks passed, not saving (%.1f s)" % (time.time() - t0))
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "(%.1f s)" % (time.time() - t0))


if __name__ == "__main__":
    main()
