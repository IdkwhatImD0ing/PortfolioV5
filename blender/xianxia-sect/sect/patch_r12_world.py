"""Round 12, lane 'world': bring the world pieces of an existing out/sect_chase.blend to what sect/world.py, scenery.py,
life.py and lib/icefire_props.py now build, so nothing they own z-fights on the web (every baked face is drawn
double-sided there, near 0.5 m / far 9000 m, 24-bit depth: two faces within a few mm flicker). Run on the cloud box,
on a copy first:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r12_world.py [-- DRY_RUN=1] [PARTS=range,roots,...]

What it changes (same object names; PARTS: range, roots, rocks, veins, links, shrines):
1. world.range (world.terrain_data): the knife-edge rim. The outline's vertices were the top's and the underside's at
   once, so wherever a grid cell had three of them its top and underside triangle were one triangle twice (438 m2), and
   next to the outline the two lay within mm-cm where the top barely cleared the rim. Now the underside starts
   RIM_LIP (0.5 m) under the rim and meets the top through a vertical lip under the outline (6,382 quads, material
   world_rock_under), and each outline vertex stands at the rim's height of its own crossing (it stood at its grid
   node's, up to 2.5 m away: rim triangles stood on edge as slivers, in the lip's plane). The top's faces, their order
   and attributes stay (scenery masks, world_veg); the 44 vertices round 11 sank under the stairs stay sunk. The
   range's waterfalls (scenery.fall.*, which build_range_falls stood 0.2 m over the mesh at a cliff's lip) follow the
   ground at their lip.
2. world.roots (world.build_roots): the same paths, rings carried along each tube (twist_free) instead of
   to_track_quat's, which spun freely about a hanging root and twisted its quads into folded bow ties. (The scene's
   roots hang from the 5 m grid the range had when they were built; a fresh build hangs them from the 2.5 m one.)
3. Every nature.floating_rock (scenery.island*, world.islet*, world.link.arena_mission.stone*; world.tidy_rock): the
   cone's last ROCK_TIP_RINGS rings close in one point (the bottom line stood as vertical fins, folded); vertices only.
4. scenery.island.009.icefire_lava_veins (icefire_props._lay_veins): the same drawn network laid so no two tops lie on
   each other and every top keeps VEIN_CLEAR over the basalt (see icefire_props). The other icefire parts are built
   again on the tidied rock and must come out as they are.
5. world.link.<a>_<b>.stairs, .piers and .arch (world._stairway): no tread ends within TREAD_GAP (2 cm) of a riser;
   the corbel courses follow the stair's curve and the shaft's top stays CORBEL_GAP inside the lowest one; a bridge
   arch's sides stand ARCH_REVEAL (8 cm, was REVEAL 2 cm) inside the parapets' outer faces. Every other link piece
   must come out as it is.
6. life.shrine.<id> (life.shrine_geo): each front step a block under its own tread; side parapets the terrace's full
   depth, front and back ones between them.

Guards (nothing is saved when one fails): each piece is either already the new recipe (a re-run) or exactly the old
one (world.range's top vertices but the 44 sunk ones, faces and underside; the roots; the links' pieces; the shrines'
vertices; the veins); every rock is a floating_rock with its own mesh; the links' ports are where the build put them.

Checks (no save when one fails): an exact coplanar scan (faces within 5 and 12 mm, |cos| >= 0.98, the r12 scan's) of
what it touched and what is near it, before and after, with line of sight from chase.cam's path (frames 1-1729) for
"seen"; the stairs' walk (rays every 0.1 m: levels, risers <= RISER, headroom, landings, both ends) and parapets;
nothing standing on the range's moved rim faces left more than 2 cm over them; scatter instances on the range (trees)
counted before and after; the veins closed; boxes of every touched mesh. Prints CACHES ok or needs audit, TREES and
WATER when those bakes must run again, and a DIGEST of every mesh it can touch: a second run changes nothing and
prints the same digest.
"""
import json
import math
import os
import re
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import world as W  # noqa: E402

TOL = 0.005                    # m: two parallel faces this close over each other z-fight (the r12 scan's first band)
TOL_FAR = 0.012                # m: its second band (clean only to about 220 m)
PAR = 0.98                     # |cos| of two faces that count as parallel (the r12 scan's)
STEP_A = 0.04                  # m2 of face per candidate sample (0.2 m spacing), at most KMAX per face
KMAX = 12
LOS_OFF = 0.003                # m: line-of-sight rays start this far past the outer face of a pair
LOS_PTS = 6                    # line-of-sight points per cluster (object pair, facing, 3 m cell) at most
CELL = 3.0


def log(*a):
    print("PATCH", *a, flush=True)


# ---- triangle soup ------------------------------------------------------------------------------------------------

def obj_tris(ob, dg, lo=None, hi=None):
    """World-space triangles of a (rendered) mesh object as evaluated: (T (m, 3, 3), poly (m,), mat (m,), vid (m, 3))
    or None; cropped to the box [lo, hi] when given (a triangle is kept when its box meets it)."""
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        if me is None or not len(me.polygons):
            return None
        me.calc_loop_triangles()
        nv, nt = len(me.vertices), len(me.loop_triangles)
        co = np.empty(nv * 3)
        me.vertices.foreach_get("co", co)
        tv = np.empty(nt * 3, np.int64)
        me.loop_triangles.foreach_get("vertices", tv)
        pi = np.empty(nt, np.int64)
        me.loop_triangles.foreach_get("polygon_index", pi)
        mi = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get("material_index", mi)
    finally:
        ev.to_mesh_clear()
    M = np.array(ev.matrix_world)
    co = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    tv = tv.reshape(-1, 3)
    T = co[tv]
    if np.linalg.det(M[:3, :3]) < 0:
        T = T[:, ::-1]
        tv = tv[:, ::-1]
    keep = np.ones(len(T), bool)
    if lo is not None:
        keep = np.all(T.max(1) >= lo, axis=1) & np.all(T.min(1) <= hi, axis=1)
    if not keep.any():
        return None
    return T[keep], pi[keep], mi[pi[keep]], tv[keep]


class Soup:
    """Triangles of several objects in one array with a BVH: T (n, 3, 3), own (n,) object index, poly, mat, vid (global
    vertex ids, per object), unit normals n and areas."""

    def __init__(self, objs, lo=None, hi=None, crop=None):
        dg = bpy.context.evaluated_depsgraph_get()
        Ts, own, poly, mat, vid = [], [], [], [], []
        self.names = []
        base = 0
        for ob in objs:
            c = crop.get(ob.name) if crop else None
            blo, bhi = c if c else (lo, hi)
            if blo is not None:
                M = np.array(ob.matrix_world)
                bb = np.array([tuple(v) for v in ob.bound_box]) @ M[:3, :3].T + M[:3, 3]
                if np.any(bb.max(0) < blo) or np.any(bb.min(0) > bhi):
                    continue
            got = obj_tris(ob, dg, blo, bhi)
            if got is None:
                continue
            T, pi, mi, tv = got
            Ts.append(T)
            own.append(np.full(len(T), len(self.names), np.int32))
            poly.append(pi)
            mat.append(mi)
            vid.append(tv + base)
            base += int(tv.max()) + 1
            self.names.append(ob.name)
        if not Ts:
            self.T = np.zeros((0, 3, 3))
            self.own = self.poly = self.mat = np.zeros(0, np.int64)
            self.vid = np.zeros((0, 3), np.int64)
            self.n = np.zeros((0, 3))
            self.area = np.zeros(0)
            self.bvh = None
            return
        self.T = np.concatenate(Ts)
        self.own = np.concatenate(own)
        self.poly = np.concatenate(poly)
        self.mat = np.concatenate(mat)
        self.vid = np.concatenate(vid)
        cr = np.cross(self.T[:, 1] - self.T[:, 0], self.T[:, 2] - self.T[:, 0])
        L = np.linalg.norm(cr, axis=1)
        self.area = 0.5 * L
        self.n = cr / np.maximum(L, 1e-15)[:, None]
        V = self.T.reshape(-1, 3)
        self.bvh = BVHTree.FromPolygons(V.tolist(), np.arange(len(V)).reshape(-1, 3).tolist(), all_triangles=True,
                                        epsilon=0.0)

    def __len__(self):
        return len(self.T)

    def name(self, i):
        return self.names[int(self.own[i])]


# ---- exact overlap of two triangles (the r12 scan's clip, out/tmp/r12scan/cand.py) ----------------------------------

def _clip(P, a, b, c):
    out = []
    n = len(P)
    for i in range(n):
        x1, y1 = P[i]
        x2, y2 = P[(i + 1) % n]
        f1 = a * x1 + b * y1 + c
        f2 = a * x2 + b * y2 + c
        if f1 <= 0.0:
            out.append((x1, y1))
        if (f1 <= 0.0) != (f2 <= 0.0):
            t = f1 / (f1 - f2)
            out.append((x1 + t * (x2 - x1), y1 + t * (y2 - y1)))
    return out


def _parea(P):
    s = 0.0
    n = len(P)
    for i in range(n):
        x1, y1 = P[i]
        x2, y2 = P[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return 0.5 * s


def overlap(A, B, na, tol):
    """Part of triangle B over triangle A (3x3) within tol of A's plane: (area, hmin, hmax, centroid, poly3d) or None."""
    o = A[0]
    e = A[1] - o
    u = e / np.linalg.norm(e)
    v = np.cross(na, u)
    A2 = [(float((p - o) @ u), float((p - o) @ v)) for p in A]
    B2 = [(float((p - o) @ u), float((p - o) @ v)) for p in B]
    Bh = [float((p - o) @ na) for p in B]
    if min(Bh) > tol or max(Bh) < -tol:
        return None
    sb = _parea(B2)
    if abs(sb) < 1e-10:
        return None
    if sb < 0:
        B2, Bh = B2[::-1], Bh[::-1]
    P = A2[::-1] if _parea(A2) < 0 else A2
    for i in range(3):
        x1, y1 = B2[i]
        x2, y2 = B2[(i + 1) % 3]
        a, b = (y2 - y1), -(x2 - x1)
        P = _clip(P, a, b, -(a * x1 + b * y1))
        if len(P) < 3:
            return None
    (x0, y0), (x1, y1), (x2, y2) = B2
    det = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if abs(det) < 1e-12:
        return None
    ha = ((Bh[1] - Bh[0]) * (y2 - y0) - (Bh[2] - Bh[0]) * (y1 - y0)) / det
    hb = ((x1 - x0) * (Bh[2] - Bh[0]) - (x2 - x0) * (Bh[1] - Bh[0])) / det
    hc = Bh[0] - ha * x0 - hb * y0
    P = _clip(P, ha, hb, hc - tol)
    if len(P) < 3:
        return None
    P = _clip(P, -ha, -hb, -hc - tol)
    if len(P) < 3:
        return None
    ar = abs(_parea(P))
    if ar < 1e-6:
        return None
    hs = [ha * x + hb * y + hc for x, y in P]
    cx = sum(x for x, _ in P) / len(P)
    cy = sum(y for _, y in P) / len(P)
    P3 = [o + x * u + y * v for x, y in P]
    return ar, min(hs), max(hs), o + cx * u + cy * v, P3, (ha * cx + hb * cy + hc)


def find_overlaps(S, src, tol=TOL_FAR, seed=11):
    """Overlaps of the source triangles (bool mask over S) with any parallel face of S within tol: list of
    dict(i, j, area, hmin, hmax, cen, same, h, poly). Candidates come from points sampled on the source faces (one per
    STEP_A m2, at most KMAX, the r12 scan's), each pair clipped exactly."""
    rng = np.random.default_rng(seed)
    q = tol + 0.0005
    cand = set()
    idx = np.nonzero(src)[0]
    k = np.clip(np.ceil(S.area[idx] / STEP_A), 1, KMAX).astype(np.int64)
    k[S.area[idx] < 1e-9] = 0
    for t, kk in zip(idx.tolist(), k.tolist()):
        if kk == 0:
            continue
        X = S.T[t]
        c = X.mean(0)
        if kk == 1:
            pts = c[None]
        else:
            r1, r2 = rng.random(kk - 1), rng.random(kk - 1)
            f = r1 + r2 > 1.0
            r1[f], r2[f] = 1.0 - r1[f], 1.0 - r2[f]
            pts = X[0] + np.outer(r1, X[1] - X[0]) + np.outer(r2, X[2] - X[0])
            pts = np.vstack([c[None], c + 0.98 * (pts - c)])
        nt = S.n[t]
        for p in pts:
            for _loc, _n, j, _d in S.bvh.find_nearest_range(Vector(p), q):
                if j is None or j == t:
                    continue
                if abs(float(S.n[j] @ nt)) < PAR:
                    continue
                cand.add((t, j) if t < j else (j, t))
    out = []
    for (i, j) in cand:
        r = overlap(S.T[i], S.T[j], S.n[i], tol)
        if r is None:
            continue
        ar, hmin, hmax, cen, P3, h = r
        out.append(dict(i=i, j=j, area=ar, hmin=hmin, hmax=hmax, cen=cen, same=bool(S.n[i] @ S.n[j] > 0), h=h,
                        poly=P3))
    return out


# ---- line of sight from the camera path ---------------------------------------------------------------------------

_CAM = None


def camera_path():
    """chase.cam positions over the web timeline (export_web's full profile), with their frames."""
    global _CAM
    if _CAM is None:
        from sect import export_web as EW
        EW.use_profile("full")
        cam = bpy.data.objects[EW.CAMERA]
        fr = list(range(EW.FRAMES[0], EW.FRAMES[1] + 1))
        mats = EW.sample_matrices(cam, fr)
        _CAM = (np.array([[m[0][3], m[1][3], m[2][3]] for m in mats]), np.array(fr))
    return _CAM


_p = list(range(16))
while _p[-1] < 1728:
    _p.append(int(_p[-1] * 1.15) + 1)
PICK = np.array(_p)


def seen_from_path(occ, p, n, h=0.0):
    """Nearest camera-path distance (and frame) from which point p of a pair with normal n (B at height h over A) can
    be seen past the pair on either side, through the occluder BVH occ; (inf, -1) when none (the r12 scan's los.py)."""
    cam, fr = camera_path()
    best = (math.inf, -1)
    for s in (1.0, -1.0):
        qp = p + n * (s * LOS_OFF + (max(h, 0.0) if s > 0 else min(h, 0.0)))
        dv = cam - qp
        on = (dv @ (s * n)) > 0.02
        if not on.any():
            continue
        ix = np.nonzero(on)[0]
        d = np.linalg.norm(dv[ix], axis=1)
        o = ix[np.argsort(d)]
        qv = Vector(qp)
        for kk in PICK:
            if kk >= len(o):
                break
            c = o[kk]
            dd = float(np.linalg.norm(cam[c] - qp))
            if dd >= best[0]:
                break
            dirv = Vector((cam[c] - qp) / dd)
            if all(b.ray_cast(qv, dirv, dd - 0.3)[0] is None for b in occ):
                best = (dd, int(fr[c]))
                break
    return best


def occluders(objs):
    """BVHs over the evaluated triangles of objs (the line-of-sight blockers), one per object."""
    out = []
    for ob in objs:
        S = Soup([ob])
        if S.bvh is not None:
            out.append(S.bvh)
    return out


def summarize(S, ovs, occ, label, tol_near=TOL, group=None, pts_per=LOS_PTS, seed=5):
    """Clusters (object pair, facing, CELL m cell); each cluster's points tested for line of sight from the camera
    path. Returns dict(rows=[...], tot) with areas split <= tol_near / tol_near..TOL_FAR, all and seen."""
    rng = np.random.default_rng(seed)
    cl = {}
    for o in ovs:
        a, b = S.name(o["i"]), S.name(o["j"])
        if group is not None:
            a, b = group(a), group(b)
        a, b = (a, b) if a <= b else (b, a)
        near = max(abs(o["hmin"]), abs(o["hmax"])) <= tol_near + 1e-9
        gap = min(abs(o["hmin"]), abs(o["hmax"])) if o["hmin"] * o["hmax"] > 0 else 0.0
        k = (a, b, o["same"], tuple(np.floor(o["cen"] / CELL).astype(int).tolist()))
        c = cl.setdefault(k, dict(a=a, b=b, same=o["same"], a5=0.0, a12=0.0, ovs=[], gaps=[]))
        c["a5" if near else "a12"] += o["area"]
        c["ovs"].append(o)
        c["gaps"].append(gap)
    rows = []
    for k, c in cl.items():
        ov = c["ovs"]
        w = np.array([o["area"] for o in ov])
        pick = rng.choice(len(ov), size=min(pts_per, len(ov)), replace=False, p=w / w.sum()) if len(ov) > 1 else [0]
        seen, dmin, fmin = 0, math.inf, -1
        for q in pick:
            o = ov[int(q)]
            d, f = seen_from_path(occ, np.asarray(o["cen"], float), S.n[o["i"]], o["h"]) if occ is not None else (0.0, -1)
            if d < math.inf:
                seen += 1
                if d < dmin:
                    dmin, fmin = d, f
        frac = seen / len(pick)
        rows.append(dict(a=c["a"], b=c["b"], same=c["same"], a5=c["a5"], a12=c["a12"], v5=c["a5"] * frac,
                         v12=c["a12"] * frac, d=dmin, f=fmin, cen=np.round(np.mean([o["cen"] for o in ov], 0), 2).tolist(),
                         gap=float(np.median(c["gaps"])), n=len(ov)))
    tot = dict(a5=sum(r["a5"] for r in rows), a12=sum(r["a12"] for r in rows), v5=sum(r["v5"] for r in rows),
               v12=sum(r["v12"] for r in rows),
               v5same=sum(r["v5"] for r in rows if r["same"]), v12same=sum(r["v12"] for r in rows if r["same"]))
    log("SCAN %s: within %.0f mm %.2f m2 (seen %.2f, same-facing seen %.2f); %.0f-%.0f mm %.2f m2 (seen %.2f, same-facing "
        "seen %.2f); %d clusters" % (label, tol_near * 1000, tot["a5"], tot["v5"], tot["v5same"], tol_near * 1000,
                                     TOL_FAR * 1000, tot["a12"], tot["v12"], tot["v12same"], len(rows)))
    return dict(rows=rows, tot=tot)


def print_rows(res, label, top=12):
    by = {}
    for r in res["rows"]:
        k = (r["a"], r["b"], r["same"])
        x = by.setdefault(k, [0.0, 0.0, 0.0, 0.0, math.inf, -1, 0])
        x[0] += r["a5"]
        x[1] += r["a12"]
        x[2] += r["v5"]
        x[3] += r["v12"]
        if r["d"] < x[4]:
            x[4], x[5] = r["d"], r["f"]
        x[6] += r["n"]
    for k, x in sorted(by.items(), key=lambda kv: -(kv[1][2] + kv[1][3]))[:top]:
        log("    %s %s ~ %s %s: <=5mm %.2f (seen %.2f) 5-12mm %.2f (seen %.2f) closest %s f%d, %d pieces"
            % (label, k[0], k[1], "same" if k[2] else "opp", x[0], x[2], x[1], x[3],
               ("%.0f m" % x[4]) if x[4] < math.inf else "-", x[5], x[6]))


# ---- small helpers -------------------------------------------------------------------------------------------------

def coords(me):
    a = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


def loops(me):
    """(loop totals, flat corner vertex indices) of a mesh."""
    lt = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_total", lt)
    cv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", cv)
    return lt, cv


def quads(me):
    lt, cv = loops(me)
    if len(lt) and (lt != 4).any():
        raise RuntimeError("%s: not all quads" % me.name)
    return cv.reshape(-1, 4)


def same_mesh(a, b, tol=1e-4, faces=True):
    """Same vertices (within tol, same order) and, with ``faces``, the same polygons (loop totals and corners)."""
    ca, cb = coords(a), coords(b)
    if ca.shape != cb.shape:
        return False, "vertices %d vs %d" % (len(ca), len(cb))
    d = float(np.abs(ca - cb).max()) if len(ca) else 0.0
    if d > tol:
        return False, "max vertex offset %.4f m" % d
    if faces:
        la, ca_ = loops(a)
        lb, cb_ = loops(b)
        if la.shape != lb.shape or (la != lb).any() or ca_.shape != cb_.shape or (ca_ != cb_).any():
            return False, "faces differ (%d vs %d)" % (len(la), len(lb))
    return True, "max vertex offset %.5f m" % d


def world_box(ob):
    c = coords(ob.data)
    if not len(c):
        return None
    M = np.array(ob.matrix_world)
    w = c @ M[:3, :3].T + M[:3, 3]
    return w.min(0), w.max(0)


def swap(ob, new_ob):
    """Give ``ob`` the mesh of ``new_ob`` (its name, object, collections, props and material slots stay)."""
    if any(s.link != 'DATA' for s in ob.material_slots):
        raise RuntimeError("%s has object-linked material slots" % ob.name)
    if ob.data.users != 1:
        raise RuntimeError("%s's mesh has %d users" % (ob.name, ob.data.users))
    slots0 = [m.name if m else None for m in ob.data.materials]
    slots1 = [m.name if m else None for m in new_ob.data.materials]
    if slots0 != slots1:
        raise RuntimeError("%s: material slots %s, rebuilt %s" % (ob.name, slots0, slots1))
    old_me, me = ob.data, new_ob.data
    name = old_me.name
    for k in old_me.keys():
        me[k] = old_me[k]
    bpy.data.objects.remove(new_ob, do_unlink=True)
    ob.data = me
    bpy.data.meshes.remove(old_me)
    me.name = name


def drop(objs):
    for o in list(objs):
        if o is None or o.name not in bpy.data.objects:
            continue
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if isinstance(me, bpy.types.Mesh) and me.users == 0:
            bpy.data.meshes.remove(me)


def hanging_loose(rock, hung):
    """How many connected pieces of ``hung`` (in the rock's frame: a child with an identity local transform) no longer
    overlap the rock."""
    def bvh_of(me, sel=None):
        co = coords(me)
        lt, cv = loops(me)
        ls = np.concatenate([[0], np.cumsum(lt)[:-1]])
        polys = [cv[a:a + n].tolist() for a, n in zip(ls, lt)]
        if sel is not None:
            polys = [polys[i] for i in sel]
        return BVHTree.FromPolygons(co.tolist(), polys), polys
    rb, _ = bvh_of(rock.data)
    me = hung.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    seen, loose = set(), 0
    for f in bm.faces:
        if f.index in seen:
            continue
        comp, stack = [], [f]
        seen.add(f.index)
        while stack:
            g = stack.pop()
            comp.append(g.index)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        cb, _ = bvh_of(me, comp)
        if not cb.overlap(rb):
            loose += 1
    bm.free()
    return loose


def mesh_digest(h, ob):
    me = ob.data
    h.update(ob.name.encode())
    h.update(np.round(coords(me), 5).tobytes())
    lt, cv = loops(me)
    h.update(lt.tobytes())
    h.update(cv.tobytes())
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", mi)
    h.update(mi.tobytes())


# ---- 1. the range: a lip along the outline ---------------------------------------------------------------------------

def outline_verts(q_t):
    """Vertices on the edges only one top quad uses (the top's outline, and where the mass meets the grid's edge)."""
    e = np.stack([q_t, np.roll(q_t, -1, axis=1)], axis=2).reshape(-1, 2)
    key = np.sort(e, axis=1)
    big = int(e.max()) + 1
    _u, inv, cnt = np.unique(key[:, 0] * big + key[:, 1], return_inverse=True, return_counts=True)
    out = cnt[inv.ravel()] == 1
    return np.unique(e[out].ravel())


def terrain_plan(rng_, r_obj):
    """('old' | 'new', d_old, d_new, z of the top vertices to keep): world.range as world.py built it before round 12
    (knife edge) or now (lip), the 44 vertices sink_under_links lowered (round 11) being the only ones off the recipe.
    Anything else raises."""
    if not np.allclose(np.array(r_obj.matrix_world), np.eye(4)):
        raise RuntimeError("world.range has a transform")
    d_old = W.terrain_data(rng_, lip=None)
    d_new = W.terrain_data(rng_)
    me = r_obj.data
    co = coords(me)
    f4 = quads(me)
    nt, nq = d_old["n_top"], d_old["n_qt"]
    if f4.shape == d_new["faces"].shape and (f4 == d_new["faces"]).all():
        state, d = "new", d_new
    elif f4.shape == d_old["faces"].shape and (f4 == d_old["faces"]).all():
        state, d = "old", d_old
    else:
        raise RuntimeError("world.range's faces are neither the old recipe's (%d) nor the new one's (%d): %d"
                           % (len(d_old["faces"]), len(d_new["faces"]), len(f4)))
    if len(co) != len(d["verts"]):
        raise RuntimeError("world.range: %d vertices, the %s recipe has %d" % (len(co), state, len(d["verts"])))
    dxy = float(np.abs(co[:nt, :2] - d_old["verts"][:nt, :2]).max())
    if dxy > 1e-3:
        raise RuntimeError("world.range: top vertices moved %.4f m sideways off the recipe" % dxy)
    zt = co[:nt, 2]
    on_old = np.abs(zt - d_old["verts"][:nt, 2]) <= 1e-3
    on_new = np.abs(zt - d_new["verts"][:nt, 2]) <= 1e-3
    sunk = ~(on_old | on_new)
    outl = np.zeros(nt, bool)
    outl[outline_verts(d_old["faces"][:nq])] = True
    if (sunk & outl).any():
        raise RuntimeError("world.range: %d outline vertices are off both recipes" % int((sunk & outl).sum()))
    dz = zt[sunk] - d_old["verts"][:nt, 2][sunk]
    if len(dz) and (dz.max() > 1e-3 or dz.min() < -(W.SINK + W.SINK_UP + 1e-3)):
        raise RuntimeError("world.range: %d top vertices off the recipe by %.3f..%.3f m (more than sink_under_links)"
                           % (len(dz), float(dz.min()), float(dz.max())))
    du = float(np.abs(co[nt:] - d["verts"][nt:]).max()) if len(co) > nt else 0.0
    if du > 1e-3:
        raise RuntimeError("world.range: underside vertices %.4f m off the %s recipe" % (du, state))
    keep = np.where(sunk, zt, np.nan)
    log("RANGE state %s: %d vertices, %d faces; %d top vertices sunk under the stairs (round 11) kept, %d outline "
        "vertices" % (state, len(co), len(f4), int(sunk.sum()), int(outl.sum())))
    return state, d_old, d_new, keep


def terrain_apply(r_obj, d_new, keep, tmp):
    """world.range from terrain_data's new recipe: the faces' attributes copied from the scene's mesh (the top's; the
    underside's are all 0 there), sharp edges from the analytic surface as build_terrain marks them, then the top
    vertices sink_under_links lowered put back."""
    me0 = r_obj.data
    nq = d_new["n_qt"]
    attrs = []
    for a in me0.attributes:
        if a.domain != "FACE" or a.name.startswith(".") or a.name in ("material_index", "sharp_face"):
            continue
        if a.data_type != "FLOAT":
            raise RuntimeError("world.range: face attribute %s is %s" % (a.name, a.data_type))
        v = np.zeros(len(me0.polygons), np.float32)
        a.data.foreach_get("value", v)
        if (v[nq:] != 0).any():
            raise RuntimeError("world.range: face attribute %s is set on the underside" % a.name)
        attrs.append((a.name, v[:nq].copy()))
    new = W._mesh_np("patch_r12.range", tmp, d_new["verts"], d_new["faces"], list(me0.materials),
                     mat_idx=d_new["mats"])
    me = new.data
    if len(me.polygons) != len(d_new["faces"]) or len(me.vertices) != len(d_new["verts"]):
        raise RuntimeError("world.range: validate changed the rebuilt mesh")
    for name, v in attrs:
        at = me.attributes.new(name, "FLOAT", "FACE")
        full = np.zeros(len(me.polygons), np.float32)
        full[:nq] = v
        at.data.foreach_set("value", full)
    me.set_sharp_from_angle(angle=math.radians(55))
    co = coords(me)
    nt = len(keep)
    m = ~np.isnan(keep)
    co[:nt][m, 2] = keep[m]
    me.vertices.foreach_set("co", co.ravel())
    me.update()
    swap(r_obj, new)


def range_rim_sources(S, cell=6.0):
    """Range triangles near the outline (cells of ``cell`` m round its vertices): where it changes."""
    me = bpy.data.objects["world.range"].data
    f4 = quads(me)
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", mi)
    ov = outline_verts(f4[mi != 2])
    xy = coords(me)[ov, :2]
    keys = set()
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            k = np.floor(xy / cell).astype(np.int64) + (dx, dy)
            keys.update((k[:, 0] * 100000 + k[:, 1]).tolist())
    c = S.T.mean(1)[:, :2]
    k = np.floor(c / cell).astype(np.int64)
    return np.isin(k[:, 0] * 100000 + k[:, 1], np.array(sorted(keys), np.int64))


# ---- 2. roots, 3. rocks, 4. veins -----------------------------------------------------------------------------------

ROCK_RE = re.compile(r"^(scenery\.island|world\.islet|world\.link\.arena_mission\.stone)(\.\d{3})?$")
FALL_RE = re.compile(r"^scenery\.fall(\.\d{3})?$")
ICE = "scenery.island.009"
ICE_PARTS = ("glacier", "icicles", "stalactites", "volcano", "lava_flow", "lava_veins")


def roots_plan(rng_, tmp):
    """('old' | 'new', rebuilt object): world.roots hangs from the 5 m grid's underside (world.GRID was 5 when it was
    built; the range was regridded since): old = to_track_quat rings, new = twist-free rings, same paths."""
    ob = bpy.data.objects["world.roots"]
    g_old = W.terrain_data(rng_, grid=5.0, lip=None)["grid"]
    g_new = W.terrain_data(rng_, grid=5.0)["grid"]
    a = W.build_roots(g_old, tmp, twist_free=False)
    b = W.build_roots(g_new, tmp, twist_free=True)
    ok_new, why_new = same_mesh(ob.data, b.data)
    ok_old, why_old = same_mesh(ob.data, a.data)
    drop([a])
    if ok_new:
        drop([b])
        return "new", None
    if ok_old:
        return "old", b
    raise RuntimeError("world.roots is neither the old tubes (%s) nor the new ones (%s)" % (why_old, why_new))


def icefire_rebuild(rock):
    """Every icefire part of ``rock`` built again in a temporary state (icefire_props.build's order and random draws,
    without clearing, stripping or the steam): {part: new object}."""
    from sect.lib import icefire_props as IF
    from sect.lib import util as U
    import random
    before = set(bpy.data.objects.keys())
    try:
        rnd = random.Random(U.seed_from(IF.KEY, rock.name))
        R = IF.Rock(rock)
        quiet = lambda *a: None
        glacier, cap, edge, falls = IF.build_glacier(rock, R, rnd, log=quiet)
        sup_cap = IF._support_bvh([(R.co.tolist(), R.polys), IF._mesh_lists(glacier)])
        icicles = IF.build_icicles(rock, R, edge, falls, sup_cap, rnd, log=quiet)
        stal = IF.build_stalactites(rock, R, falls, sup_cap, rnd, log=quiet)
        sx, sy = IF.to_xy(IF.STEAM_A, cap.d0(IF.STEAM_A) - 0.5)
        volcano, vc, th_flow, th_rim = IF.build_volcano(rock, R, rnd, (sx, sy), log=quiet)
        sup = IF._support_bvh([(R.co.tolist(), R.polys), IF._mesh_lists(volcano)])
        flow, rim_end, th_rim = IF.build_lava_flow(rock, R, cap, vc, th_flow, th_rim, (sx, sy), sup, rnd, log=quiet)
        veins = IF.build_lava_veins(rock, R, rim_end, th_rim, rnd, log=log)
    except Exception:
        drop([bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before])
        raise
    return dict(glacier=glacier, icicles=icicles, stalactites=stal, volcano=volcano, lava_flow=flow, lava_veins=veins)


def veins_old(rock, R_rock_mesh_state=None):
    """The lava veins as built before round 12 (laid whole), for the guard: only the veins object, in a temp state."""
    from sect.lib import icefire_props as IF
    orig = IF.build_lava_veins
    try:
        IF.build_lava_veins = lambda *a, **k: orig(*a, **dict(k, r12=False))
        parts = icefire_rebuild(rock)
    finally:
        IF.build_lava_veins = orig
    v = parts.pop("lava_veins")
    drop(parts.values())
    return v


# ---- 5. links: treads 2 cm clear of the risers, corbels along the curve ----------------------------------------------

LINK_PARTS = ("stairs", "rails", "piers", "arch", "foot_landing", "foot_rail", "rest_landing", "rest_rail", "rest_pier")
LINK_CHANGED = ("stairs", "piers", "arch")


def links_plan(rng_, tmp):
    """Per stairway: the rebuilt pieces (round 12 and round 11 recipes) and the guard states."""
    root = bpy.data.objects.get("world.root")
    by = {r["link"]: r for r in json.loads(root["links"])} if root is not None and "links" in root else {}
    out = []
    for seg in rng_.segs:
        if not seg["mass"]:
            continue
        ka, kb = seg["ka"], seg["kb"]
        nm = "world.link.%s_%s" % (ka, kb)
        pa, pb = W.port(rng_, ka, "depart"), W.port(rng_, kb, "arrival")
        rep0 = by.get("%s-%s" % (ka, kb))
        if pa is None or pb is None or rep0 is None:
            raise RuntimeError("%s: no ports or no report" % nm)
        for end, p in (("depart", pa), ("arrival", pb)):
            off = float(np.abs(np.asarray(rep0[end]["world"], float) - p["p"]).max())
            if off > 0.02:
                raise RuntimeError("%s %s moved %.3f m since the build" % (nm, end, off))
        objs, rep, geo = W._stairway(rng_, tmp, seg, nm, pa, pb, arch_extras=False)
        objs_old, _r, _g = W._stairway(rng_, tmp, seg, nm, pa, pb, arch_extras=False, r11=True)
        new = {o.name[len(nm) + 1:].split(".")[0]: o for o in objs}
        old = {o.name[len(nm) + 1:].split(".")[0]: o for o in objs_old}
        states = {}
        for part in LINK_PARTS:
            ob = bpy.data.objects.get(nm + "." + part)
            if (ob is None) != (part not in new):
                raise RuntimeError("%s.%s: in the scene %s, rebuilt %s" % (nm, part, ob is not None, part in new))
            if ob is None:
                continue
            ok_new, why_new = same_mesh(ob.data, new[part].data)
            if ok_new:
                states[part] = "new"
                continue
            ok_old, why_old = same_mesh(ob.data, old[part].data)
            if part in LINK_CHANGED and ok_old:
                states[part] = "old"
                continue
            raise RuntimeError("%s.%s is neither round 11's (%s) nor round 12's (%s)" % (nm, part, why_old, why_new))
        drop(objs_old)
        P = W._plan_stairway(rng_, seg, pa, pb)
        plan = geo["plan"]
        rest_span = None
        if plan["rest_k"] is not None:
            k = plan["rest_k"]
            mid = 0.5 * (plan["sr"][k] + plan["sr"][k + 1])
            rest_span = (mid - W.REST_LANDING * 0.5 + 0.5, mid + W.REST_LANDING * 0.5 - 0.5)
        out.append(dict(nm=nm, key="%s-%s" % (ka, kb), new=new, geo=geo, rep=rep, states=states,
                        foot=P["foot"] if P["gate"] else 0.0, z0=float(pa["p"][2]), z1=float(pb["p"][2]),
                        side=1.0 if P["info"]["meander"] >= 0.0 else -1.0, rest_span=rest_span))
    return out


def tread_gaps(geo, foot):
    """Shortest tread next to a riser or the foot (the new stations' rule)."""
    s, sr = geo["s"], geo["plan"]["sr"]
    L = float(s[-1])
    fixed = np.concatenate([sr, [foot] if foot else []])
    s_cut = s[np.abs(s[:, None] - fixed[None, :]).min(axis=1) > W.TREAD_GAP] if len(fixed) else s
    c = np.unique(np.concatenate([[0.0, L], s_cut, fixed]))
    c = c[np.concatenate([[True], np.diff(c) > 1e-4])]
    return float(np.diff(c).min())


# ---- walk checks (patch_r11_links.py's, on a Soup) ------------------------------------------------------------------

def down(S, x, y, z, reach=3.0):
    loc, nrm, i, d = S.bvh.ray_cast(Vector((x, y, z)), Vector((0.0, 0.0, -1.0)), reach)
    return (None, None) if loc is None else (float(loc[2]), S.name(i))


def up_clear(S, x, y, z, reach=2.0):
    loc, nrm, i, d = S.bvh.ray_cast(Vector((x, y, z)), Vector((0.0, 0.0, 1.0)), reach)
    return loc is None, (None if loc is None else S.name(i))


def walk_check(S, nm, geo, z0, z1, foot, rest_span, side):
    """Rays down every 0.1 m along the stair (centre, 2 m each side) land on the link's floor at the plan's level
    (2 mm), risers at most world.RISER, 2 m clear overhead; the rest landing one floor across its opening; the foot
    landing one floor across; both ends' floors. Returns (fails, stats)."""
    fails, st = [], {}
    s, xy, yaw, plan = geo["s"], geo["xy"], geo["yaw"], geo["plan"]
    L = float(s[-1])
    sr = plan["sr"]
    q = np.arange(0.05, L - 0.05 + 1e-9, 0.1)
    bad_q = np.zeros(len(q), bool)
    for x in list(sr) + ([foot] if foot else []):
        bad_q |= np.abs(q - x) < 0.03
    q = q[~bad_q]
    c, nl, _ = W._frame(s, xy, yaw, q)
    exp = np.where(q <= foot, z0, W._level_at(plan, q)) if foot else W._level_at(plan, q)
    worst_rise, misses, low_head, wrong, off = 0.0, 0, [], [], []
    for lat in (-2.0, 0.0, 2.0):
        zs = []
        for k in range(len(q)):
            x, y = c[k] + nl[k] * lat
            z, ob = down(S, float(x), float(y), float(exp[k]) + 1.0)
            if z is None:
                misses += 1
                zs.append(np.nan)
                continue
            if not ob.startswith(nm + "."):
                wrong.append((round(float(q[k]), 2), lat, ob, round(z - float(exp[k]), 4)))
            elif abs(z - float(exp[k])) > 0.002:
                off.append((round(float(q[k]), 2), lat, ob, round(z - float(exp[k]), 4)))
            zs.append(z)
            ok, what = up_clear(S, float(x), float(y), z + 0.02)
            if not ok and len(low_head) < 5:
                low_head.append((round(float(q[k]), 1), lat, what))
        zs = np.array(zs)
        d = np.abs(np.diff(zs[~np.isnan(zs)]))
        worst_rise = max(worst_rise, float(d.max()) if len(d) else 0.0)
    st.update(samples=int(3 * len(q)), worst_riser=round(worst_rise, 3), misses=misses, n_other_floor=len(wrong),
              other_floor=wrong[:4], n_off_level=len(off), low_headroom=low_head)
    if misses:
        fails.append("%s: %d walk samples hit nothing" % (nm, misses))
    if off:
        fails.append("%s: %d walk samples off the plan's level, e.g. %s" % (nm, len(off), off[:3]))
    if worst_rise > W.RISER + 0.002:
        fails.append("%s: a %.3f m step on the walk" % (nm, worst_rise))
    if low_head:
        fails.append("%s: something within 2 m over the walk at %s" % (nm, low_head))
    h0 = np.array([math.cos(float(yaw[0])), math.sin(float(yaw[0]))])
    h1 = np.array([math.cos(float(yaw[-1])), math.sin(float(yaw[-1]))])
    ends = []
    for p, z in ((xy[0] - h0 * 0.3, z0), (xy[-1] + h1 * 0.3, z1)):
        zz, ob = down(S, float(p[0]), float(p[1]), z + 1.0)
        ends.append((None if zz is None else round(zz - z, 3), ob))
    st["ends"] = ends
    if rest_span:
        k = plan["rest_k"]
        zl = float(plan["lev"][k + 1])
        for qq in (rest_span[0] + 0.6, rest_span[1] - 0.6):
            cm, nm_, _ = W._frame(s, xy, yaw, [qq])
            for lat in np.arange(0.0, 3.2, 0.05):
                x, y = cm[0] + nm_[0] * side * lat
                z, ob = down(S, float(x), float(y), zl + 1.0)
                if z is None or abs(z - zl) > 0.002:
                    fails.append("%s: rest landing floor broken at station %.1f, %.2f m out (%s, %s)"
                                 % (nm, qq, lat, z, ob))
                    break
    if foot:
        cf, nf, _ = W._frame(s, xy, yaw, [1.0])
        for lat in np.arange(-4.0, 4.01, 0.1):
            x, y = cf[0] + nf[0] * lat
            z, ob = down(S, float(x), float(y), z0 + 1.0)
            if z is None or abs(z - z0) > 0.002 or not ob.endswith(".foot_landing"):
                fails.append("%s: foot landing floor broken at %.1f m across (%s, %s)" % (nm, lat, z, ob))
                break
    return fails, st


def parapet_check(S, nm, geo, z0, z1, foot, rest_span, side):
    """Rays down every 0.25 m along both parapets land on .rails RAIL_H - COPING / 2 over the nosing line."""
    s, xy, yaw, plan = geo["s"], geo["xy"], geo["yaw"], geo["plan"]
    L = float(s[-1])
    lm = 0.5 * (W.STAIR_W * 0.5 + W.STAIR_W * 0.5 + W.RAIL_W)
    q = np.arange((foot or 0.0) + 0.1, L - 0.1, 0.25)
    c, nl, _ = W._frame(s, xy, yaw, q)
    rest_open = (rest_span[0] - 0.5, rest_span[1] + 0.5) if rest_span else None
    keys = np.array([L] + ([foot] if foot else []) + (list(rest_open) if rest_open else []))
    st = np.unique(np.concatenate([s[np.abs(s[:, None] - keys[None, :]).min(axis=1) > 0.2], keys]))
    want = np.interp(q, st, W._nosing(plan, s, z0, z1, st)) + W.RAIL_H - 0.5 * W.COPING
    gaps, n = [], 0
    for sd in (-1.0, 1.0):
        for k in range(len(q)):
            if rest_open and sd == side and rest_open[0] - 0.05 < q[k] < rest_open[1] + 0.05:
                continue
            x, y = c[k] + nl[k] * sd * lm
            z, ob = down(S, float(x), float(y), float(want[k]) + 1.0, reach=2.0)
            n += 1
            if z is None or ob != nm + ".rails" or abs(z - float(want[k])) > 0.01:
                if len(gaps) < 5:
                    gaps.append((round(float(q[k]), 2), sd, ob, None if z is None else round(z - float(want[k]), 3)))
    return (["%s: parapet missing or off height at %s" % (nm, gaps)] if gaps else []), n


# ---- 6. shrines -------------------------------------------------------------------------------------------------------

def shrines_plan(tmp):
    """Per life.shrine.<id> mesh: the old and new Geo (depth, opening and terrace size read off the scene's mesh)."""
    from sect import life as LF
    from sect.lib import util as U
    specs = {s["id"]: s for s in LF.SHRINES}
    bridged = {a for ab in LF.BRIDGES for a in ab}
    out = []
    for ob in sorted(bpy.data.objects, key=lambda o: o.name):
        if ob.type != "MESH" or not ob.name.startswith("life.shrine.") or ob.name.count(".") != 2:
            continue
        sid = ob.name.split(".")[2]
        spec = specs.get(sid)
        if spec is None:
            raise RuntimeError("%s: no SHRINES entry" % ob.name)
        co = coords(ob.data)
        depth = -float(co[:, 2].min())
        opening = (LF.BRIDGE_W + 0.8) if sid in bridged else 0.0
        found = None
        for dims in (LF.terrace_dims(1e3), LF.terrace_dims(0.0)):
            for r12 in (True, False):
                g, info = LF.shrine_geo(spec, depth, opening, dims=dims, r12=r12)
                v = np.array(g.v, float)
                if v.shape == co.shape and float(np.abs(v - co).max()) < 2e-4:
                    found = (dims, "new" if r12 else "old")
                    break
            if found:
                break
        if found is None:
            raise RuntimeError("%s is not life.shrine_geo's (old or new) at depth %.3f" % (ob.name, depth))
        dims, state = found
        g, info = LF.shrine_geo(spec, depth, opening, dims=dims, r12=True)
        mats = [spec.get("roof", "roof_tile_teal") if m == "ROOF" else m for m in LF.SHRINE_MATS]
        new = None
        if state == "old":
            new = U.mesh_from_pydata("patch_r12." + ob.name, g.v, g.f, tmp, materials=mats, smooth=False,
                                     material_indices=g.m)
            if len(new.data.polygons) != len(g.f):
                raise RuntimeError("%s: rebuilt mesh lost faces in validate" % ob.name)
            bm = bmesh.new()
            bm.from_mesh(new.data)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            bm.to_mesh(new.data)
            bm.free()
            new.data.update()
        out.append(dict(ob=ob, sid=sid, state=state, new=new, depth=depth, dims=dims))
    return out


# ---- scans --------------------------------------------------------------------------------------------------------

def scan_range(occ, tag):
    r = bpy.data.objects["world.range"]
    S = Soup([r])
    src = range_rim_sources(S)
    ovs = find_overlaps(S, src)
    res = summarize(S, ovs, occ, "%s range rim (%d triangles near the outline)" % (tag, int(src.sum())))
    print_rows(res, tag, top=3)
    return res["tot"]


def scan_rocks(rocks, occ, tag):
    tot = dict(a5=0.0, a12=0.0, v5=0.0, v12=0.0, v5same=0.0, v12same=0.0)
    worst = []
    for ob in rocks:
        objs = [ob] + [c for c in ob.children if c.type == "MESH" and c.name.endswith(".roots")]
        S = Soup(objs)
        if not len(S):
            continue
        ovs = find_overlaps(S, np.ones(len(S), bool))
        if not ovs:
            continue
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            res = summarize(S, ovs, [S.bvh] + occ, ob.name, group=lambda n: n)
        for k in tot:
            tot[k] += res["tot"][k]
        worst.append((res["tot"]["v5"] + res["tot"]["v12"], ob.name, res["tot"]))
    log("SCAN %s rocks (%d islands, islets, stepping stones, with their roots): within 5 mm %.2f m2 (seen %.2f), "
        "5-12 mm %.2f m2 (seen %.2f)" % (tag, len(rocks), tot["a5"], tot["v5"], tot["a12"], tot["v12"]))
    for v, nm, t in sorted(worst, reverse=True)[:4]:
        log("    %s %s: seen %.2f + %.2f m2" % (tag, nm, t["v5"], t["v12"]))
    return tot


def scan_objs(label, objs, src_names, occ, tag, ctx_pad=None):
    S = Soup(objs)
    src = np.isin(S.own, [S.names.index(n) for n in src_names if n in S.names])
    ovs = find_overlaps(S, src)
    res = summarize(S, ovs, [S.bvh] + occ, "%s %s" % (tag, label), group=lambda n: n)
    print_rows(res, tag, top=4)
    return res["tot"]


def link_soup(L, pad=2.0):
    """The link's own pieces and everything rendered near them (cropped), for the scan and the walk checks."""
    nm = L["nm"]
    own = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(nm + ".") and not o.hide_render]
    mine = [o for o in own if o.name[len(nm) + 1:].split(".")[0] in LINK_PARTS]
    bb = [world_box(o) for o in mine]
    lo = np.min([b[0] for b in bb], 0) - pad
    hi = np.max([b[1] for b in bb], 0) + pad
    lo[2] -= 1e4
    ctx = [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render and o not in mine and
           not o.name.startswith(("world.cloud", "world.haze", "world.cirrus", "world.moon", "world.range.forest"))]
    return Soup(mine + ctx, lo=lo, hi=hi), mine


def scan_link(L, occ, tag):
    S, mine = link_soup(L)
    nm = L["nm"]
    src = np.isin(S.own, [S.names.index(o.name) for o in mine
                          if o.name in S.names and o.name[len(nm) + 1:].split(".")[0] in LINK_CHANGED])

    def grp(n):
        return n[len(nm) + 1:] if n.startswith(nm + ".") else n
    ovs = find_overlaps(S, src)
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        res = summarize(S, ovs, [S.bvh] + occ, nm, group=grp)
    same = [r for r in res["rows"] if r["same"]]
    t = dict(v5same=sum(r["v5"] for r in same), v12same=sum(r["v12"] for r in same), a5=res["tot"]["a5"],
             a12=res["tot"]["a12"], v5=res["tot"]["v5"], v12=res["tot"]["v12"])
    log("SCAN %s %s (treads and piers against everything near): same-facing seen %.2f (<=5 mm) + %.2f (5-12 mm) m2; "
        "all seen %.2f + %.2f m2" % (tag, L["key"], t["v5same"], t["v12same"], t["v5"], t["v12"]))
    by = {}
    for r in same:
        if r["v5"] + r["v12"] > 0.005:
            k = (r["a"], r["b"])
            by[k] = by.get(k, 0.0) + r["v5"] + r["v12"]
    for k, v in sorted(by.items(), key=lambda kv: -kv[1])[:4]:
        log("    %s %s ~ %s: %.2f m2 seen" % (tag, k[0], k[1], v))
    return t


# ---- floating checks --------------------------------------------------------------------------------------------------

def surface_bvh(co, faces, sel):
    tri = []
    for f in faces[sel]:
        tri.append((f[0], f[1], f[2]))
        tri.append((f[0], f[2], f[3]))
    return BVHTree.FromPolygons(co.tolist(), tri, all_triangles=True)


def rest_gaps(old_bvh, new_bvh, lo, hi, skip):
    """[(object, gap)]: every rendered mesh (not ``skip``) with a down-facing face that sat on the old surface (within
    3 cm over it, or in it) inside [lo, hi], and the largest gap that opened under it on the new one (m)."""
    dg = bpy.context.evaluated_depsgraph_get()
    rng = np.random.default_rng(3)
    out = []
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH" or ob.hide_render or ob.name.startswith(skip):
            continue
        M = np.array(ob.matrix_world)
        bb = np.array([tuple(c) for c in ob.bound_box]) @ M[:3, :3].T + M[:3, 3]
        if np.any(bb.max(0) < lo) or np.any(bb.min(0) > hi):
            continue
        got = obj_tris(ob, dg, lo, hi)
        if got is None:
            continue
        P = got[0]
        nrm = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        ar = 0.5 * np.linalg.norm(nrm, axis=1)
        dn = (nrm[:, 2] < -0.5 * np.linalg.norm(nrm, axis=1)) & (ar > 1e-6)
        worst, hit = 0.0, False
        for tri, a in zip(P[dn], ar[dn]):
            k = int(min(64, max(3, round(a / 0.02))))
            r1, r2 = rng.random(k), rng.random(k)
            f = r1 + r2 > 1.0
            r1[f], r2[f] = 1.0 - r1[f], 1.0 - r2[f]
            for q in tri[0] + np.outer(r1, tri[1] - tri[0]) + np.outer(r2, tri[2] - tri[0]):
                o = Vector((q[0], q[1], q[2] + 0.05))
                l0 = old_bvh.ray_cast(o, Vector((0.0, 0.0, -1.0)), 0.3)[0]
                if l0 is None or q[2] - l0[2] > 0.03:
                    continue
                l1 = new_bvh.ray_cast(o, Vector((0.0, 0.0, -1.0)), 5.0)[0]
                if l1 is None:
                    continue
                hit = True
                worst = max(worst, float(min(q[2], l0[2]) - l1[2]))
        if hit and worst > 1e-4:
            out.append((ob.name, round(worst, 3)))
    return sorted(out, key=lambda x: -x[1])


def scatter_positions(surface_names):
    """{instancer: (n, 3) world locations} of the GN scatter instances on these surfaces (trees, shrubs)."""
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for inst in dg.object_instances:
        if not inst.is_instance or inst.parent is None:
            continue
        par = inst.parent.original
        mod = par.modifiers.get("NatureScatter") if hasattr(par, "modifiers") else None
        if mod is None or mod.node_group is None:
            continue
        surf = None
        try:
            for it in mod.node_group.interface.items_tree:
                if getattr(it, "in_out", None) == "INPUT" and it.name == "Surface":
                    surf = getattr(mod.properties.inputs, it.identifier).value
        except Exception:
            surf = None
        if surf is None or surf.name not in surface_names:
            continue
        out.setdefault(par.name, []).append(tuple(inst.matrix_world.translation))
    return {k: np.array(v, float) for k, v in out.items()}


def scatter_moves(a, b):
    """Per scatter: (count before, count after, moved > 1 cm, largest move) matching each instance to the nearest one
    of the same scatter after."""
    from mathutils import kdtree
    out = {}
    for k in sorted(set(a) | set(b)):
        pa, pb = a.get(k, np.zeros((0, 3))), b.get(k, np.zeros((0, 3)))
        if not len(pa) or not len(pb):
            out[k] = (len(pa), len(pb), max(len(pa), len(pb)), float("inf"))
            continue
        kd = kdtree.KDTree(len(pb))
        for i, p in enumerate(pb):
            kd.insert(Vector(p), i)
        kd.balance()
        d = np.array([kd.find(Vector(p))[2] for p in pa])
        out[k] = (len(pa), len(pb), int((d > 0.01).sum()), float(d[d <= 1.0].max()) if (d <= 1.0).any() else 0.0,
                  int((d > 1.0).sum()))
    return out


# ---- main ---------------------------------------------------------------------------------------------------------------

def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opt = dict(DRY_RUN=False, PARTS="range,roots,rocks,veins,links,shrines")
    for a in argv:
        k, eq, v = a.partition("=")
        if k not in opt or not eq:
            raise SystemExit("patch_r12_world: unknown option %r (DRY_RUN=1, PARTS=range,roots,...)" % a)
        opt[k] = v
    dry = opt["DRY_RUN"].strip().lower() not in ("", "0", "false", "no") if isinstance(opt["DRY_RUN"], str) else False
    return dry, set(p.strip() for p in opt["PARTS"].split(",") if p.strip())


def main():
    t_start = time.time()
    dry, parts = options()
    fails = []

    if bpy.data.objects.get("world.range") is None or bpy.data.objects.get("world.root") is None:
        raise SystemExit("patch_r12_world: no world.range / world.root; is this out/sect_chase.blend?")
    rng_ = W.Range(W._norm_anchors(None), W._anchor_yaws(None))
    tmp = bpy.data.collections.new("patch_r12_world.tmp")
    bpy.context.scene.collection.children.link(tmp)
    r_obj = bpy.data.objects["world.range"]
    rocks = sorted((o for o in bpy.data.objects if o.type == "MESH" and ROCK_RE.match(o.name)), key=lambda o: o.name)
    touched = {}                                     # name -> world box before
    changed = []
    falls_moved = []
    res = {}
    try:
        # ---- guards and plans (nothing changes yet)
        if "range" in parts:
            t_state, d_old, d_new, keep = terrain_plan(rng_, r_obj)
        if "roots" in parts:
            roots_state, roots_new = roots_plan(rng_, tmp)
            log("ROOTS state", roots_state)
        if "rocks" in parts:
            bad = [o.name for o in rocks if W.rock_rings(o.data) is None or o.data.users != 1]
            if bad:
                raise RuntimeError("not floating_rock meshes (or shared): %s" % bad[:6])
        if "links" in parts:
            links = links_plan(rng_, tmp)
            for L in links:
                log("LINK", L["key"], "states", json.dumps(L["states"]), "shortest tread beside a riser now %.3f m"
                    % tread_gaps(L["geo"], L["foot"]))
        if "shrines" in parts:
            shrines = shrines_plan(tmp)
            log("SHRINES", [(s["sid"], s["state"]) for s in shrines])
        if "veins" in parts:
            ice = bpy.data.objects.get(ICE)
            if ice is None:
                raise RuntimeError("no %s" % ICE)
        for o in tmp.all_objects:                    # the rebuilt pieces wait here, out of every scan
            o.hide_render = True

        # ---- scans before
        occ = occluders([r_obj])
        if "range" in parts:
            res["range0"] = scan_range(occ, "before")
        if "rocks" in parts:
            res["rocks0"] = scan_rocks(rocks, occ, "before")
        if "roots" in parts:
            res["roots0"] = scan_objs("roots", [bpy.data.objects["world.roots"]], ["world.roots"], occ, "before")
        if "veins" in parts:
            ice_objs = [bpy.data.objects[ICE + ".icefire_" + p] for p in ICE_PARTS] + [ice]
            res["veins0"] = scan_objs("lava veins", ice_objs, [ICE + ".icefire_lava_veins"], occ, "before")
        if "links" in parts:
            res["links0"] = {L["key"]: scan_link(L, occ, "before") for L in links}
        if "shrines" in parts:
            res["shrines0"] = {s["sid"]: scan_objs("shrine " + s["sid"], [s["ob"]], [s["ob"].name], occ, "before")
                               for s in shrines}
        trees0 = scatter_positions({"world.range"}) if "range" in parts else {}

        # ---- apply
        if "range" in parts:
            me0 = r_obj.data
            co0 = coords(me0)
            f0 = quads(me0)
            nq0 = d_old["n_qt"]
            touched["world.range"] = world_box(r_obj)
            if t_state == "old":
                terrain_apply(r_obj, d_new, keep, tmp)
                changed.append("world.range")
                log("RANGE rebuilt with the lip: %d vertices (%d new under the outline), %d faces (%d lip quads)"
                    % (len(d_new["verts"]), d_new["n_rim"], len(d_new["faces"]), d_new["n_lip"]))
            co1 = coords(r_obj.data)
            f1 = quads(r_obj.data)
            nt = d_old["n_top"]
            dz = co1[:nt, 2] - co0[:nt, 2]
            mv = np.nonzero(np.abs(dz) > 1e-6)[0]
            log("RANGE outline vertices moved to the rim's height at their crossing: %d, by %s m (median %.3f, 95%% "
                "under %.3f)" % (len(mv), "%.3f..%.3f" % (dz.min(), dz.max()) if len(mv) else "0",
                                 float(np.median(np.abs(dz[mv]))) if len(mv) else 0.0,
                                 float(np.quantile(np.abs(dz[mv]), 0.95)) if len(mv) else 0.0))
            # the range's waterfalls (scenery.build_range_falls) stand 0.2 m over the mesh where their ray found the
            # cliff's lip: they follow the ground there (a fresh build finds the same lip on the new mesh)
            if len(mv):
                sb0 = surface_bvh(co0, f0, np.arange(nq0))
                sb1 = surface_bvh(coords(r_obj.data), quads(r_obj.data), np.arange(nq0))
                for o in bpy.data.objects:
                    if o.parent is None and FALL_RE.match(o.name):
                        for c in o.children_recursive:
                            if c.type == "MESH" and len(c.data.vertices):
                                touched.setdefault(c.name, world_box(c))
                        p = o.matrix_world.translation
                        a = sb0.ray_cast(Vector((p.x, p.y, p.z + 5.0)), Vector((0, 0, -1)), 30.0)[0]
                        b = sb1.ray_cast(Vector((p.x, p.y, p.z + 5.0)), Vector((0, 0, -1)), 30.0)[0]
                        if a is not None and b is not None and abs(b.z - a.z) > 1e-4:
                            o.location.z += b.z - a.z
                            falls_moved.append((o.name, round(b.z - a.z, 3)))
                log("RANGE waterfalls moved with the ground at their lip (m):", falls_moved if falls_moved else "none")
            # sink_under_links on the new range: it must find nothing more to sink
            made = [(L["nm"], "stairway", [], L["rep"], L["geo"]) for L in (links if "links" in parts else [])]
            if made:
                sk = W.sink_under_links(rng_, r_obj, made)
                log("RANGE sink_under_links again:", json.dumps(sk))
                if sk["vertices"] and float(np.abs(coords(r_obj.data)[:nt, 2] - co1[:nt, 2]).max()) > 1e-6:
                    fails.append("sink_under_links moved range vertices again: %s" % sk)
        if "roots" in parts:
            ob = bpy.data.objects["world.roots"]
            touched["world.roots"] = world_box(ob)
            if roots_state == "old":
                swap(ob, roots_new)
                changed.append("world.roots")
                log("ROOTS rebuilt twist-free (same paths, same vertex count)")
        if "rocks" in parts:
            moved = 0
            for ob in rocks:
                touched[ob.name] = world_box(ob)
                m = W.tidy_rock(ob)
                if m < 0:
                    raise RuntimeError("%s: not a floating_rock" % ob.name)
                if m:
                    changed.append(ob.name)
                moved += m
            log("ROCKS tidy_rock: %d of %d rocks closed at the bottom (%d vertices moved onto their apex)"
                % (sum(1 for o in rocks if o.name in changed), len(rocks), moved))
            # what hangs from a rock's cone must still start inside it: the ice-fire island's stalactites
            st_ob = bpy.data.objects.get(ICE + ".icefire_stalactites")
            if st_ob is not None:
                loose = hanging_loose(bpy.data.objects[ICE], st_ob)
                log("ROCKS %s: %s" % (st_ob.name, "every stalactite still starts inside the rock" if not loose else
                                      "%d stalactites no longer reach into the rock" % loose))
                if loose:
                    fails.append("%d stalactites of %s left hanging free of the rock" % (loose, ICE))
        if "veins" in parts:
            ice = bpy.data.objects[ICE]
            parts_new = icefire_rebuild(ice)
            try:
                for p in ICE_PARTS:
                    ex = bpy.data.objects[ICE + ".icefire_" + p]
                    ok, why = same_mesh(ex.data, parts_new[p].data)
                    if p != "lava_veins":
                        if not ok:
                            fails.append("%s rebuilt on the tidied rock differs from the scene's (%s)" % (ex.name, why))
                        continue
                    touched[ex.name] = world_box(ex)
                    if ok:
                        log("VEINS already the round-12 ones")
                        continue
                    vo = veins_old(ice)
                    ok_old, why_old = same_mesh(ex.data, vo.data)
                    drop([vo])
                    if not ok_old:
                        raise RuntimeError("%s is neither the old veins (%s) nor the new (%s)" % (ex.name, why_old, why))
                    keys = {k: ex[k] for k in ex.keys()}
                    swap(ex, parts_new.pop("lava_veins"))
                    for k, v in keys.items():
                        ex[k] = v
                    changed.append(ex.name)
                    log("VEINS rebuilt:", len(ex.data.vertices), "vertices,", len(ex.data.polygons), "faces")
            finally:
                drop(parts_new.values())
        if "links" in parts:
            for L in links:
                for part in LINK_CHANGED:
                    ob = bpy.data.objects.get(L["nm"] + "." + part)
                    if ob is None:
                        continue
                    touched[ob.name] = world_box(ob)
                    if L["states"][part] == "old":
                        swap(ob, L["new"].pop(part))
                        changed.append(ob.name)
                drop(L["new"].values())
            log("LINKS replaced:", [n for n in changed if n.startswith("world.link.") and ".stone" not in n])
        if "shrines" in parts:
            for s in shrines:
                touched[s["ob"].name] = world_box(s["ob"])
                if s["state"] == "old":
                    swap(s["ob"], s["new"])
                    changed.append(s["ob"].name)
            log("SHRINES replaced:", [s["sid"] for s in shrines if s["state"] == "old"])
        bpy.context.view_layer.update()

        # ---- scans after, checks
        occ = occluders([r_obj])
        if "range" in parts:
            res["range1"] = t1 = scan_range(occ, "after")
            if t1["v5"] > 0.5 or t1["v12"] > 1.0:
                fails.append("range rim: %.2f + %.2f m2 seen within 12 mm after" % (t1["v5"], t1["v12"]))
            # objects that sat on the top where its outline vertices moved
            mvf = np.nonzero(np.isin(f0[:nq0], mv).any(1))[0] if len(mv) else np.zeros(0, np.int64)
            if len(mvf):
                pts = co1[np.unique(f0[mvf])]
                lo, hi = pts.min(0) - 1.0, pts.max(0) + 1.0
                # (the range's waterfalls moved with the ground at their lip, above: their sheets keep their height
                # over it there; the rim beside a lip may have moved more or less)
                gaps = rest_gaps(surface_bvh(co0, f0, mvf), surface_bvh(co1, f1, mvf), lo, hi,
                                 ("world.range", "world.link.", "world.cloud", "world.waterfall", "scenery.fall"))
                log("RANGE objects that sat on the moved rim faces (largest new gap under them, m):",
                    gaps[:10] if gaps else "none")
                for n, g in gaps:
                    if g > 0.02:
                        fails.append("%s stands %.3f m over the moved rim" % (n, g))
                # world.waterfall stands on the analytic top (world.build_waterfalls): a fresh build puts it where
                # it is; how far the mesh under its sheets moved
                wf = rest_gaps(surface_bvh(co0, f0, mvf), surface_bvh(co1, f1, mvf), lo, hi,
                               tuple(o.name for o in bpy.data.objects if not o.name.startswith("world.waterfall")))
                log("RANGE world.waterfall sheets over the moved rim (analytic lips, unchanged; new gap, m):",
                    wf if wf else "none")
            sm = scatter_moves(trees0, scatter_positions({"world.range"}))
            for k, v in sm.items():
                log("TREES %s on the range: %d instances before, %d after; %d moved more than 1 cm (of them %d by "
                    "more than 1 m, i.e. gone or new; the largest move under 1 m %.2f m)" % (k, v[0], v[1], v[2], v[4],
                                                                                         v[3]))
            res["trees"] = (sum(v[0] for v in sm.values()), sum(v[1] for v in sm.values()),
                            sum(v[2] for v in sm.values()), max([v[3] for v in sm.values()] + [0.0]))
        if "rocks" in parts:
            res["rocks1"] = t1 = scan_rocks(rocks, occ, "after")
            if t1["v5"] > 1.5 or t1["v5"] > res["rocks0"]["v5"] + 1e-3 or t1["v12"] > res["rocks0"]["v12"] + 1e-3:
                fails.append("rocks: %.2f + %.2f m2 seen within 12 mm after (%.2f + %.2f before)"
                             % (t1["v5"], t1["v12"], res["rocks0"]["v5"], res["rocks0"]["v12"]))
        if "roots" in parts:
            res["roots1"] = t1 = scan_objs("roots", [bpy.data.objects["world.roots"]], ["world.roots"], occ, "after")
            if t1["a5"] > 0.05:
                fails.append("roots: %.2f m2 within 5 mm after" % t1["a5"])
        if "veins" in parts:
            ice_objs = [bpy.data.objects[ICE + ".icefire_" + p] for p in ICE_PARTS] + [bpy.data.objects[ICE]]
            res["veins1"] = t1 = scan_objs("lava veins", ice_objs, [ICE + ".icefire_lava_veins"], occ, "after")
            if t1["v5"] + t1["v12"] > 0.2:
                fails.append("lava veins: %.2f + %.2f m2 seen within 12 mm after" % (t1["v5"], t1["v12"]))
            v = bpy.data.objects[ICE + ".icefire_lava_veins"]
            bm = bmesh.new()
            bm.from_mesh(v.data)
            open_e = sum(1 for e in bm.edges if e.is_boundary)
            bm.free()
            if open_e:
                fails.append("lava veins: %d open edges (each slab must be closed)" % open_e)
        if "links" in parts:
            res["links1"] = {}
            for L in links:
                t1 = res["links1"][L["key"]] = scan_link(L, occ, "after")
                if t1["v5same"] + t1["v12same"] > 0.3:
                    fails.append("%s: %.2f m2 same-facing seen within 12 mm of the treads or piers after"
                                 % (L["key"], t1["v5same"] + t1["v12same"]))
                S, _mine = link_soup(L)
                f, st = walk_check(S, L["nm"], L["geo"], L["z0"], L["z1"], L["foot"], L["rest_span"], L["side"])
                f2, npar = parapet_check(S, L["nm"], L["geo"], L["z0"], L["z1"], L["foot"], L["rest_span"], L["side"])
                f += f2
                st["parapet_samples"] = npar
                for part in LINK_CHANGED:
                    ob = bpy.data.objects.get(L["nm"] + "." + part)
                    if ob is not None:
                        sm = np.zeros(len(ob.data.polygons), bool)
                        ob.data.polygons.foreach_get("use_smooth", sm)
                        if sm.any():
                            f.append("%s is not flat-shaded" % ob.name)
                log("WALK", L["key"], "PASS" if not f else "FAIL", json.dumps(st, default=str))
                fails += f
        if "shrines" in parts:
            res["shrines1"] = {}
            for s in shrines:
                t1 = res["shrines1"][s["sid"]] = scan_objs("shrine " + s["sid"], [s["ob"]], [s["ob"].name], occ,
                                                           "after")
                if t1["v5same"] + t1["v12same"] > 0.02:
                    fails.append("shrine %s: %.3f m2 same-facing seen after" % (s["sid"], t1["v5same"] + t1["v12same"]))
        # names, counts
        for n in changed:
            if bpy.data.objects.get(n) is None:
                fails.append("%s is gone" % n)
        # caches: boxes
        grew = []
        for n, b0 in touched.items():
            b1 = world_box(bpy.data.objects[n])
            g_ = float(max((b0[0] - b1[0]).max(), (b1[1] - b0[1]).max()))
            if g_ > 0.005:
                grew.append((n, round(g_, 3)))
        log("BOXES grown more than 5 mm past the old ones:", grew if grew else "none")
    finally:
        for o in list(tmp.all_objects):
            me = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if isinstance(me, bpy.types.Mesh) and me.users == 0:
                bpy.data.meshes.remove(me)
        bpy.data.collections.remove(tmp)
    if fails:
        for f in fails:
            log("FAIL", f)
        raise SystemExit("patch_r12_world: %d checks failed; not saved" % len(fails))
    log("CHANGED %d meshes:" % len(changed), changed[:12], "..." if len(changed) > 12 else "")
    if grew:
        log("CACHES needs audit: boxes grew %s - run the export_web audit, chunks,meta, then bakefull every area chunk "
            "and the backdrop, then the pack" % grew)
    else:
        log("CACHES ok: same names, every touched mesh's box inside its old one within 5 mm. Re-bake every area chunk "
            "and the backdrop (the range runs through all of them), then the pack")
    if "range" in parts and res.get("trees") and res["trees"][2]:
        log("TREES needed: %d scatter instances on the range's rim faces moved or changed (instances %d -> %d): re-run "
            "bake_trees (the audit too: instance indices after a changed one shift)" % (res["trees"][2], res["trees"][0],
                                                                                    res["trees"][1]))
    if falls_moved:
        log("WATER needed: %d range waterfalls followed the ground at their lip: re-run the water bake"
            % len(falls_moved))
    log("DIGEST", digest())
    log("done in %.0f s" % (time.time() - t_start))
    if dry:
        log("DRY_RUN: not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


def digest():
    """md5 of every mesh this patch can touch: equal after a first and a second run when it is idempotent."""
    import hashlib
    h = hashlib.md5()
    names = ["world.range", "world.roots", ICE + ".icefire_lava_veins"]
    names += sorted(o.name for o in bpy.data.objects if o.type == "MESH" and ROCK_RE.match(o.name))
    names += sorted(o.name for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("world.link.")
                    and o.name.split(".")[-1] in LINK_CHANGED)
    names += sorted(o.name for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("life.shrine.")
                    and o.name.count(".") == 2)
    for n in names:
        ob = bpy.data.objects.get(n)
        if ob is not None:
            mesh_digest(h, ob)
    for o in sorted((o for o in bpy.data.objects if o.parent is None and FALL_RE.match(o.name)), key=lambda o: o.name):
        h.update(o.name.encode())
        h.update(np.round(np.array(o.matrix_world), 5).tobytes())
    return h.hexdigest()


if __name__ == "__main__":
    main()
