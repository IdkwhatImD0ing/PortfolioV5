r"""Round 12, lane 'libs': bring a finished out/sect_chase.blend (round 11 patched) up to the round-12 shared libraries
(sect/lib/arch.py, props.py, array_props.py) so that it matches a fresh build, without a rebuild. The fixes remove
faces that lay within a few mm of another face (on the web every material is double-sided, far plane 9000 m, 24-bit
depth: such pairs flicker). Rule: two faces stand at least 2 cm apart, or they become one surface (an exact boolean
union of a piece's own parts, or a decal cut into its host face as a hole filled edge to edge).

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r12_libs.py [-- DRY_RUN=1] [SCAN=0] [PARTS=a,b]

Each part (see PART_CLASSES; a part's docstring says what it fixes and which round-12 item it is) first recognises
what it changes: it rebuilds the piece with the OLD settings (OLD_ARCH / OLD_PROPS / OLD_AP: the source's knobs as
they were) and requires the file's piece to equal it (or to equal the NEW build: then it is done already), so the patch
refuses a file it does not know. It then puts in the new build's mesh (same object and mesh names), or post-processes
the existing mesh exactly as the source now does. Idempotent: a second run finds every part done, changes nothing and
prints the same DIGEST.

Checks before saving (any failure: "NOT SAVED", exit code 1, nothing written): every part's own checks (corridor floors
meet edge to edge with their tops where they were, the formation inlays sit on the floor with nothing floating, the
cut decals fill their holes, ...); SCAN=1 (default) scans what each part touched and everything standing round it for
visible same-facing or back-to-back faces within 20 mm, before and after (m2 per band: <=5 / 5-12 / 12-20 mm), and fails
when an overlap is left (more than 0.05 m2 or a quarter of what was there within 12 mm) or grows; the object count must
not change. Then it prints "CACHES ok" (names kept, every box within 1 cm: re-bake the chunks it lists) or "CACHES
needs audit" (a box grew: export_web audit first), and DIGEST (md5 of every mesh it owns). DRY_RUN=1 does everything
but save. The scans are slow (about 2.5 hours in one process, the bracket bands and the roofs about 40 minutes each;
PARTS= runs a subset, so groups can run side by side as dry runs); SCAN=0 runs in about 4.5 minutes.
"""
import math
import os
import re
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SCAN_TOL = 0.0205          # m: parallel faces this close are reported (2 cm rule; bands <=5, 5-12, 12-20 mm)
SCAN_PAR = 0.98            # |cos| between two faces counted as parallel
BANDS = (0.0055, 0.0125, 0.0205)
BAND_NAMES = ("<=5mm", "5-12mm", "12-20mm")
PROBE = 0.003              # m: how far off a pair the scan looks for open air (inside a solid there: hidden)
TOUCH = 0.0005             # m: opposite faces of two closed solids this close touch (neither can be seen)


def log(*a):
    print("PATCH", *a, flush=True)


# ============================================================================================ triangles

def mesh_tris(me, M=None):
    """(n, 3, 3) triangles of mesh ``me`` (numpy float64) under 4x4 matrix M, and the polygon index of each."""
    me.calc_loop_triangles()
    nv, nt = len(me.vertices), len(me.loop_triangles)
    if not nt:
        return np.zeros((0, 3, 3)), np.zeros(0, np.int64)
    co = np.empty(nv * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(nv, 3)
    if M is not None:
        M = np.asarray(M, float)
        co = co @ M[:3, :3].T + M[:3, 3]
    tv = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", tv)
    pi = np.empty(nt, np.int64)
    me.loop_triangles.foreach_get("polygon_index", pi)
    return co[tv.reshape(nt, 3)], pi


def eval_tris(ob, dg, M=None):
    """Triangles of object ``ob`` as evaluated (modifiers), under M (default: identity, local space)."""
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        if me is None:
            return np.zeros((0, 3, 3)), np.zeros(0, np.int64)
        return mesh_tris(me, M)
    finally:
        ev.to_mesh_clear()


def proto_of(ob):
    """The prototype collection an instanced object belongs to ('arch.p.*' / 'props.*' under _protos), or None."""
    for c in ob.users_collection:
        if c.name.startswith(("arch.p.", "props.")):
            return c
    return None


def instances(dg):
    """{proto collection name: [(instancer owner name, 4x4 numpy world matrix, proto object name)]} of every rendered
    instance in the depsgraph, and {owner: [(world matrix, object name)]} of the instancers' sources by owner."""
    out = {}
    for inst in dg.object_instances:
        if not inst.is_instance or inst.object.type != 'MESH':
            continue
        src = inst.object.original
        pc = proto_of(src)
        if pc is None:
            continue
        par = inst.parent.original if inst.parent else None
        if par is not None and par.hide_render:
            continue
        out.setdefault(pc.name, []).append((par.name if par else "?", np.array(inst.matrix_world), src.name))
    return out


CLOSED = {}                # scan label -> its mesh is a closed solid (every edge between exactly two faces)
WHOLE = 200000             # objects up to this many triangles go into a scan whole (bigger ones: what is in its box)
CUT = set()                # scan labels of objects cut to the scan's box (left out of the inside test)


def mesh_closed(me):
    """Is every edge of mesh ``me`` shared by exactly two faces once points in one place count as one (a closed solid,
    however many parts; a mesh split along its paint seams still counts)?"""
    nv, nl, npl = len(me.vertices), len(me.loops), len(me.polygons)
    if not nv or not npl:
        return False
    co = np.empty(nv * 3)
    me.vertices.foreach_get("co", co)
    _u, wid = np.unique(np.round(co.reshape(nv, 3), 6), axis=0, return_inverse=True)
    wid = wid.reshape(-1)
    lv = np.empty(nl, np.int64)
    me.loops.foreach_get("vertex_index", lv)
    ls = np.empty(npl, np.int64)
    lt = np.empty(npl, np.int64)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    nxt = np.arange(nl) + 1
    ends = ls + lt - 1
    nxt[ends] = ls
    a, b = wid[lv], wid[lv[nxt]]
    keep = a != b
    e = np.sort(np.stack([a[keep], b[keep]], 1), axis=1)
    _k, cnt = np.unique(e, axis=0, return_counts=True)
    return bool((cnt == 2).all())


_VOL = {}


def _volume_only(ob):
    """Is every material of ``ob`` a volume shader (the haze and mist boxes)?"""
    key = ob.name
    if key not in _VOL:
        mats = [s.material for s in ob.material_slots if s.material is not None]
        _VOL[key] = bool(mats) and all(m.node_tree is not None and any(n.bl_idname.startswith("ShaderNodeVolume")
                                                                        for n in m.node_tree.nodes) for m in mats)
    return _VOL[key]


def gather_world(dg, boxes, pad=0.05, skip_owner=()):
    """World triangles of everything rendered whose triangles touch one of ``boxes`` [(lo, hi)] (+pad):
    (T (n,3,3), labels (n,) of 'owner' or 'owner>proto object')."""
    B = np.array([[np.asarray(b[0], float), np.asarray(b[1], float)] for b in boxes])
    lo, hi = B[:, 0] - pad, B[:, 1] + pad
    cache, Ts, Ls = {}, [], []
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type != 'MESH':
            continue
        if inst.is_instance:
            par = inst.parent.original if inst.parent else None
            own = (par.name if par else "?") + ">" + ob.original.name
            if par is not None and par.hide_render:
                continue
            base_own = par.name if par else "?"
        else:
            if ob.original.hide_render:
                continue
            own = base_own = ob.original.name
        if base_own in skip_owner:
            continue
        if _volume_only(ob.original):
            continue                               # a fog / haze volume: no surface to flicker, encloses nothing
        M = np.array(inst.matrix_world)
        bb = np.array([tuple(c) for c in ob.bound_box]) @ M[:3, :3].T + M[:3, 3]
        hb = ~((bb.min(0) > hi).any(1) | (bb.max(0) < lo).any(1))
        if not hb.any():
            continue
        key = ob.data.as_pointer() if inst.is_instance else ("o", ob.original.name)
        L = cache.get(key)
        if L is None:
            if inst.is_instance:
                L = mesh_tris(ob.data)[0]
                cl = mesh_closed(ob.data)
            else:
                ev = ob
                me = ev.to_mesh()
                L = mesh_tris(me)[0] if me is not None else np.zeros((0, 3, 3))
                cl = mesh_closed(me) if me is not None else False
                ev.to_mesh_clear()
            cache[key] = L
            cache[("closed", key)] = cl
        CLOSED[own] = cache[("closed", key)]
        if not len(L):
            continue
        T = L @ M[:3, :3].T + M[:3, 3]
        if len(T) <= WHOLE:
            keep = np.ones(len(T), bool)           # whole: the inside test needs every closed solid complete
            CUT.discard(own)
        else:
            tmin, tmax = T.min(1), T.max(1)
            keep = np.zeros(len(T), bool)
            for j in np.nonzero(hb)[0]:
                keep |= ~((tmin > hi[j]).any(1) | (tmax < lo[j]).any(1))
            CUT.add(own)                           # cut to the box: no longer a whole solid
        if keep.any():
            Ts.append(T[keep])
            Ls.append(np.full(int(keep.sum()), own, dtype=object))
    if not Ts:
        return np.zeros((0, 3, 3)), np.zeros(0, dtype=object)
    return np.concatenate(Ts), np.concatenate(Ls)


# ============================================================================================ overlap scan

_DIRS = None


def _dirs():
    global _DIRS
    if _DIRS is None:
        d = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
        d += [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
        _DIRS = [Vector(v).normalized() for v in d]
    return _DIRS


class Scene3:
    """Triangles (n, 3, 3) with labels, as one BVH, face normals and areas."""

    def __init__(self, T, labels, poly=None):
        self.T = np.asarray(T, float)
        self.labels = np.asarray(labels, dtype=object)
        self.poly = poly
        n = len(self.T)
        e1, e2 = self.T[:, 1] - self.T[:, 0], self.T[:, 2] - self.T[:, 0]
        cr = np.cross(e1, e2)
        self.area = 0.5 * np.linalg.norm(cr, axis=1)
        self.n = cr / np.maximum(2.0 * self.area[:, None], 1e-15)
        self.scale = float(np.abs(self.T).max()) if n else 1.0
        # an object cut to the scan's box (a terrain) is left out of the inside test: what is left of it encloses
        # nothing
        self.solid = np.array([lab not in CUT for lab in self.labels], bool) if n else np.zeros(0, bool)
        self.bvh = BVHTree.FromPolygons(self.T.reshape(-1, 3).tolist(), [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(n)],
                                        all_triangles=True, epsilon=0.0) if n else None

    def _crosses(self, j, o, d, t, tol):
        """Does the ray o + s d cross triangle j at s within tol of t (Moller-Trumbore, edges included)? Returns
        (crossed, near an edge)."""
        a, b, c = self.T[j]
        e1, e2 = b - a, c - a
        pv = np.cross(d, e2)
        det = float(e1 @ pv)
        if abs(det) < 1e-14:
            return False, False
        inv = 1.0 / det
        tv = o - a
        u = float(tv @ pv) * inv
        if u < -1e-7 or u > 1 + 1e-7:
            return False, False
        qv = np.cross(tv, e1)
        v = float(d @ qv) * inv
        if v < -1e-7 or u + v > 1 + 1e-7:
            return False, False
        s = float(e2 @ qv) * inv
        if abs(s - t) > tol:
            return False, False
        return True, min(u, v, 1.0 - u - v) < 1e-5

    def winding(self, p, d, max_hits=400):
        """Exits minus entries of the ray from p along d (unit): the number of closed, outward-facing solids that
        contain p (overlapping solids add up; faces lying in one place are each counted once). None when the ray
        passes over an edge between faces facing different ways (ambiguous: try another ray)."""
        o = np.array(p, float)
        dd = np.array(d, float)
        eps = 2e-6 * max(1.0, self.scale)
        t0, count = 0.0, 0
        for _ in range(max_hits):
            loc, nrm, i, dist = self.bvh.ray_cast(Vector(o + dd * t0), Vector(dd), 1e5)
            if loc is None:
                break
            t = t0 + dist
            here, edge = {}, False
            for _l, _n, j, _d in self.bvh.find_nearest_range(loc, 4 * eps):
                if not self.solid[j]:
                    continue
                hit, near = self._crosses(j, o, dd, t, 8 * eps)
                if not hit and j != i:
                    continue
                edge = edge or near
                dn = float(self.n[j] @ dd)
                if abs(dn) > 1e-9:       # one count per facing direction at this spot (a ray on a shared edge
                    here[tuple(np.round(self.n[j], 2))] = 1 if dn > 0 else -1     # meets two triangles of one face)
            if edge and len(here) > 1 and len({v for v in here.values()}) == 1:
                return None              # over an edge between two faces both entered (or both left): ambiguous
            count += sum(here.values())
            t0 = t + 10 * eps
        return count

    def inside(self, p):
        """True when p lies inside some closed solid: the winding number is at least 1 along most of 14 rays (the
        six axes and the eight cube diagonals, skewed so no ray runs along a face; an ambiguous ray is retried with
        another skew)."""
        if self.bvh is None:
            return False
        votes = n = 0
        D = _dirs()
        skews = ((0.0123, -0.0071, 0.0049), (-0.0217, 0.0133, 0.0091), (0.0071, 0.0193, -0.0157))
        for k, d in enumerate(D):
            w = None
            for sk in skews:
                dd = Vector(d) + Vector(sk)
                dd.normalize()
                w = self.winding(p, dd)
                if w is not None:
                    break
            if w is None:
                continue
            n += 1
            if w >= 1:
                votes += 1
            if votes * 2 > len(D):              # a majority of all the rays already: decided
                return True
            if (n - votes) * 2 >= len(D):
                return False
        return n > 0 and votes * 2 > n


def _bary_inside(T, q, margin=1e-9):
    a, b, c = T
    v0, v1, v2 = b - a, c - a, q - a
    d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1
    d20, d21 = v2 @ v0, v2 @ v1
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-30:
        return False
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    u = 1.0 - v - w
    return min(u, v, w) > margin


def scan(S, subject, tol=SCAN_TOL, step=0.02, max_samples=250000, seed=12, kmax=400, par=SCAN_PAR, details=False):
    """Coplanar overlap scan of the triangles ``subject`` (bool mask or index array into S) against every triangle of
    S (the subject's own included, the same triangle excluded). A sample point on a subject face counts against a
    partner face when the partner is parallel (|cos| >= par), within ``tol`` along the normal and the point projects
    strictly inside it. Kinds:
      'same'  both face the same way: the one behind bleeds through the one in front (visible unless the space in
              front of both is inside a solid);
      'thin'  back to back (the partner behind, facing away), or the two coincide facing opposite ways: a thin solid
              or a double-sided sheet, visible when either outer side is open;
      (facing each other, the partner in front facing back: two solids touching or an air gap - never visible.)
    Returns {(label_a, label_b, kind, band): [area m2, n samples, [sample points]]} with visible (open) samples only,
    and the totals per band."""
    idx = np.nonzero(subject)[0] if np.asarray(subject).dtype == bool else np.asarray(subject)
    if not len(idx) or S.bvh is None:
        return {}, [0.0, 0.0, 0.0]
    ar = S.area[idx]
    tot = float(ar.sum())
    step = max(step, math.sqrt(tot / max_samples)) if tot > 0 else step
    rnd = np.random.default_rng(seed)
    res = {}
    bands = [0.0, 0.0, 0.0]
    for i in idx:
        a = S.area[i]
        if a < 1e-10:
            continue
        k = int(min(kmax, max(1, round(a / (step * step)))))
        Ti = S.T[i]
        ni = S.n[i]
        c = Ti.mean(0)
        r1, r2 = rnd.random(k), rnd.random(k)
        f = r1 + r2 > 1.0
        r1[f], r2[f] = 1.0 - r1[f], 1.0 - r2[f]
        P = Ti[0] + np.outer(r1, Ti[1] - Ti[0]) + np.outer(r2, Ti[2] - Ti[0])
        P = c + 0.96 * (P - c)
        w = a / k
        for p in P:
            best = {}
            for loc, nrm, j, d in S.bvh.find_nearest_range(Vector(p), tol):
                if j == i:
                    continue
                cj = float(S.n[j] @ ni)
                if abs(cj) < par:
                    continue
                dv = np.array(loc) - p
                g = float(dv @ ni)
                if abs(g) > tol or np.linalg.norm(dv - g * ni) > 3e-4:
                    continue
                if not _bary_inside(S.T[j], p + g * ni):
                    continue
                if cj > 0:
                    kind = "same"
                elif g < -1e-4 or abs(g) <= 1e-4:
                    kind = "thin"
                    if g > -TOUCH and S.labels[j] != S.labels[i] and CLOSED.get(S.labels[i]) and                             CLOSED.get(S.labels[j]):
                        continue                  # two closed solids face to face: they touch, both faces hidden
                else:
                    continue                      # facing each other: contact or an air gap
                lab = S.labels[j]
                if lab not in best or abs(g) < abs(best[lab][1]):
                    best[lab] = (kind, g, j)
            if not best:
                continue
            for lab, (kind, g, j) in best.items():
                pv = Vector(p)
                nv = Vector(ni)
                # the probes stand PROBE off the faces (further, a probe near a thin part's edge leaves it)
                if kind == "same":
                    vis = not S.inside(pv + nv * (max(g, 0.0) + PROBE))
                else:
                    vis = (not S.inside(pv + nv * PROBE)) or (not S.inside(pv + nv * (min(g, 0.0) - PROBE)))
                if not vis:
                    continue
                band = 0 if abs(g) <= BANDS[0] else (1 if abs(g) <= BANDS[1] else 2)
                key = (S.labels[i], lab, kind, band)
                rec = res.setdefault(key, [0.0, 0, []])
                rec[0] += w
                rec[1] += 1
                if details and len(rec[2]) < 6:
                    rec[2].append((tuple(round(float(x), 4) for x in p), round(g * 1000, 2), tuple(round(float(x), 3)
                                                                                                for x in ni)))
                bands[band] += w
    return res, bands


def summarize(res, top=8):
    rows = sorted(res.items(), key=lambda kv: -kv[1][0])
    return ["%s / %s %s %s: %.3f m2 (%d)" % (a, b, kind, BAND_NAMES[band], v[0], v[1])
            for (a, b, kind, band), v in rows[:top]]


# ============================================================================================ patch machinery

from sect.lib import arch as A  # noqa: E402
from sect.lib import props as P  # noqa: E402
from sect.lib import array_props as AP  # noqa: E402
from sect.lib import util as U  # noqa: E402

# the settings the source had before round 12 (each part builds the old piece with them to recognise it)
OLD_ARCH = dict(COLUMN_SHAFT_ON_RING=False, DOUGONG_UNION=False, BAND_UNION=False, BAND_BEAM2_Z=(7.0, 8.2),
                CORNER_ARM_W=None,
                BEAMS_UNION=False, LATTICE_UNION=False, LATTICE_LAYER_OFF=0.002, LATTICE_PAPER_GAP=0.004,
                PANEL_UNION=False, SEAT_SKIRT_INSET=None, GABLE_UNION=False, CHIWEN_LIFT=(0.0, 0.0, 0.0),
                CHIWEN_FIN_T=0.045, CHIWEN_HANDLE_T=0.055, CHIWEN_GUARD_TOP=0.985, DRUM_SCROLL_T=0.45,
                RAIL_SPLIT=False, CORRIDOR_MITRE=False, LATTICE_EXACT=False, ROOF_KEEL_CLEAR=None, BARGE_IN=None,
                PAIFANG_PLINTH=2.6, PAIFANG_PLINTH_PAD=0.0, CORRIDOR_CORNER_LIFT=0.12, CORRIDOR_BENCH_DROP=None,
                BENCH_UNION=False, FRIEZE_RIDGE_GAP=None, FRIEZE_HOLES=False, WALLS_UNION=False)
OLD_PROPS = dict(STELE_CUT=False, SCROLL_CUT=False, SLIPS_CUT=False, BANNER_REGIONS=False, BOOKS_SOLID=False,
                 ANVIL_OPEN_STUMP=False, DING_MOLTEN_CAP=True, LANTERN_UNION=False, LION_UNION=False)
OLD_AP = dict(INLAY_SOLID=False)
TOL = 2e-5                 # m: a rebuilt piece matches the file's within this (float32 coordinates, recovered sizes)
BOX_TOL = 0.01             # m: a box that grows more than this needs the export audit
MAX_AFTER = {0: 0.05, 1: 0.05, 2: 0.25}   # m2 per piece left after a part, per band (visible kinds), before it fails


class Fail(list):
    def add(self, msg):
        log("FAIL", msg)
        self.append(msg)


class knobs:
    """Temporarily set module attributes (a builder's round-12 settings)."""

    def __init__(self, mod, values):
        self.mod, self.values = mod, values

    def __enter__(self):
        self.old = {k: getattr(self.mod, k) for k in self.values}
        for k, v in self.values.items():
            setattr(self.mod, k, v)

    def __exit__(self, *a):
        for k, v in self.old.items():
            setattr(self.mod, k, v)


_TMP = [0]


def build_arch_proto(fn, *args, old=False, **kw):
    """Build an arch prototype (fn = A._p_*) into a new temporary collection with the new (or old) settings and return
    {part: object} ('part' = the object name after the collection name)."""
    _TMP[0] += 1
    col = bpy.data.collections.new("_r12tmp%d" % _TMP[0])
    keep = A._proto

    def fake(key, build):
        build(col)
        return col
    A._proto = fake
    try:
        if old:
            with knobs(A, OLD_ARCH):
                fn(*args, **kw)
        else:
            fn(*args, **kw)
    finally:
        A._proto = keep
    return col, {o.name[len(col.name) + 1:]: o for o in col.all_objects}


def build_props_proto(fn, *args, old=False, **kw):
    """Run a props prototype builder (fn(pc, ...)) into a new temporary collection: {part: object}, the part being the
    object name without its 'props.' prefix and '.NNN' suffix."""
    _TMP[0] += 1
    col = bpy.data.collections.new("_r12tmp%d" % _TMP[0])
    if old:
        with knobs(P, OLD_PROPS):
            fn(col, *args, **kw)
    else:
        fn(col, *args, **kw)
    return col, {part_of(o.name): o for o in col.all_objects}


def part_of(name):
    return re.sub(r"\.\d{3}$", "", name)


def free_temp(col):
    for o in list(col.all_objects):
        data = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)
    bpy.data.collections.remove(col)


def coords(me):
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def same_geo(a, b, tol=TOL):
    """Same vertex count, face count and vertex positions (in order, or as sets) within tol."""
    if len(a.vertices) != len(b.vertices) or len(a.polygons) != len(b.polygons):
        return False
    ca, cb = coords(a), coords(b)
    if not len(ca):
        return True
    if np.abs(ca - cb).max() <= tol:
        return True
    if tol <= 0.0:
        return False
    ka = np.lexsort(np.round(ca / (4 * tol)).T[::-1])
    kb = np.lexsort(np.round(cb / (4 * tol)).T[::-1])
    return bool(np.abs(ca[ka] - cb[kb]).max() <= 4 * tol)


def swap_mesh(objs, new_me):
    """Give ``objs`` (every user of one mesh) the mesh ``new_me``; the old mesh's name and ID properties go to the new
    one and the old one is removed."""
    old = objs[0].data
    name = old.name
    for k in old.keys():
        if k not in new_me.keys():
            new_me[k] = old[k]
    for o in objs:
        o.data = new_me
    if old.users == 0:
        bpy.data.meshes.remove(old)
        new_me.name = name
    return new_me


def users_of(me):
    return [o for o in bpy.data.objects if o.type == 'MESH' and o.data == me]


def area_of(ob):
    while ob.parent is not None:
        ob = ob.parent
    return ob.name.split(".")[0]


def world_box(ob):
    M = np.array(ob.matrix_world)
    bb = np.array([tuple(c) for c in ob.bound_box]) @ M[:3, :3].T + M[:3, 3]
    return bb.min(0), bb.max(0)


def local_box(me):
    c = coords(me)
    return (c.min(0), c.max(0)) if len(c) else (np.zeros(3), np.zeros(3))


def grew(old, new, tol=BOX_TOL):
    return bool((np.asarray(new[0]) < np.asarray(old[0]) - tol).any() or (np.asarray(new[1]) > np.asarray(old[1]) + tol).any())


def proto_owners(dg):
    """{proto collection name: set of area prefixes of its instancers}, and instance counts."""
    out, cnt = {}, {}
    for pcn, lst in instances(dg).items():
        for own, M, src in lst:
            o = bpy.data.objects.get(own)
            out.setdefault(pcn, set()).add(area_of(o) if o else own.split(".")[0])
            cnt[pcn] = cnt.get(pcn, 0) + 1
    return out, cnt


def scan_proto(pc, dg, inst):
    """Coplanar overlap of a prototype's own parts, scaled like its typical instance (the median of the instances'
    smallest scale: balustrade panels are scaled and sheared to their span, and a few short spans squash a panel's
    stiles to a few mm): per-band m2 per instance and the pair list (local scan: what other objects stand around each
    instance is not counted)."""
    lst = inst.get(pc.name, [])
    L = np.eye(4)
    if lst:
        srt = sorted(lst, key=lambda r: np.linalg.svd(r[1][:3, :3], compute_uv=False).min())
        L[:3, :3] = srt[len(srt) // 2][1][:3, :3]
    Ts, labs = [], []
    for ob in pc.all_objects:
        if ob.type != 'MESH':
            continue
        T, _ = eval_tris(ob, dg, L @ np.array(ob.matrix_world))
        if len(T):
            Ts.append(T)
            labs.append(np.full(len(T), part_of(ob.name), dtype=object))
            CLOSED[part_of(ob.name)] = mesh_closed(ob.data) and not ob.modifiers
    if not Ts:
        return [0.0, 0.0, 0.0], {}
    T = np.concatenate(Ts)
    S = Scene3(T, np.concatenate(labs))
    res, bands = scan(S, np.ones(len(T), bool), step=0.01, max_samples=30000)
    return bands, res


def scan_object(ob, dg, pad=0.03, step=0.03, max_samples=40000):
    """Coplanar overlap of a placed object against itself and everything rendered around it (world space)."""
    ev = ob.evaluated_get(dg)
    lo, hi = world_box(ev)
    T, lab = gather_world(dg, [(lo, hi)], pad=pad)
    if not len(T):
        return [0.0, 0.0, 0.0], {}
    S = Scene3(T, lab)
    res, bands = scan(S, lab == ob.name, step=step, max_samples=max_samples)
    return bands, res


def fmt(b):
    return "%.3f / %.3f / %.3f" % tuple(b)


def mesh_digest(h, me, name):
    h.update(name.encode())
    h.update(np.round(coords(me), 5).tobytes())
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    h.update(lv.tobytes())
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", mi)
    h.update(mi.tobytes())


# ============================================================================================ parts

class Part:
    """One fix. plan(fail) -> bool (work to do); apply(); check(fail, dg); subjects (what the scans look at):
    self.protos (collection names) and self.objects (object names); self.touched: mesh owners for the digest
    ([(label, mesh)]); caches(): (box growth list, chunk names)."""
    name = "?"
    item = ""
    SCOPE = None           # regex (or a test of both labels): the before / after scans count only the pairs with a
                           # piece this part changes
    LEFT = 0.25            # share of the old overlap (within 12 mm) a piece may keep before the part fails
    ABS = 0.05             # m2 a piece may keep (or gain) whatever its old overlap (sampling noise)

    def __init__(self):
        self.protos, self.objects, self.todo, self.done, self.grown, self.chunks = [], [], [], [], [], set()

    def digest_meshes(self):
        out = []
        for pcn in self.protos:
            pc = bpy.data.collections.get(pcn)
            if pc is not None:
                out += [(o.name, o.data) for o in pc.all_objects if o.type == 'MESH']
        for n in self.objects:
            o = bpy.data.objects.get(n)
            if o is not None and o.type == 'MESH':
                out.append((o.name, o.data))
        return out


def protos_matching(rx):
    return sorted(c.name for c in bpy.data.collections if re.match(rx, c.name) and len(c.all_objects))


class ArchProtoPart(Part):
    """Rebuild arch prototypes whose collection name matches RX: params(pc) -> (fn, args, kw) or None (skip);
    the file's piece must equal the old build, then every part is replaced by the new build's. TAGGED: a prototype
    whose meshes all carry that R12_TAG is new already (its parameters can no longer be read off it)."""
    RX = None
    TAGGED = None

    def params(self, pc):
        raise NotImplementedError

    def plan(self, fail):
        self.jobs = []
        for pcn in protos_matching(self.RX):
            pc = bpy.data.collections[pcn]
            have = {o.name[len(pcn) + 1:]: o for o in pc.all_objects if o.type == 'MESH'}
            if self.TAGGED and all(o.data.get(A.R12_TAG) == self.TAGGED for o in have.values()):
                self.protos.append(pcn)
                self.done.append(pcn)
                continue
            try:
                prm = self.params(pc)
            except Exception as e:     # noqa: BLE001
                fail.add("%s: %s: cannot read its parameters (%s)" % (self.name, pcn, e))
                continue
            if prm is None:
                continue
            fn, args, kw = prm
            colN, new = build_arch_proto(fn, *args, **kw)
            state = "new" if self.match(have, new) else None
            if state is None:
                colO, old = build_arch_proto(fn, *args, old=True, **kw)
                if self.match(have, old):
                    state = "old"
                free_temp(colO)
            if state is None:
                fail.add("%s: %s is neither the old nor the new build of %s%s" % (self.name, pcn, fn.__name__, args))
                free_temp(colN)
                continue
            self.protos.append(pcn)
            if state == "old":
                self.jobs.append((pcn, have, colN, new))
                self.todo.append(pcn)
            else:
                self.done.append(pcn)
                free_temp(colN)
        log("%s: %d prototypes, %d to rebuild, %d already new" % (self.name, len(self.protos), len(self.todo),
                                                                 len(self.done)))
        return bool(self.todo)

    def match(self, have, built):
        if sorted(have) != sorted(k for k, o in built.items() if o.type == 'MESH'):
            return False
        return all(same_geo(have[k].data, built[k].data) for k in have)

    def apply(self):
        for pcn, have, col, new in self.jobs:
            for k, o in have.items():
                nm = new[k].data
                if same_geo(o.data, nm, 0.0) and len(o.data.polygons) == len(nm.polygons):
                    continue
                box0 = local_box(o.data)
                swap_mesh([o], nm)            # (the temporary object still uses it: free_temp leaves it)
                if grew(box0, local_box(o.data)):
                    self.grown.append(o.name)
            free_temp(col)
        log("%s: rebuilt %d prototypes" % (self.name, len(self.jobs)))

    def check(self, fail, dg):
        for pcn in self.protos:
            pc = bpy.data.collections[pcn]
            have = {o.name[len(pcn) + 1:]: o for o in pc.all_objects if o.type == 'MESH'}
            if self.TAGGED:
                if not all(o.data.get(A.R12_TAG) == self.TAGGED for o in have.values()):
                    fail.add("%s: %s not rebuilt" % (self.name, pcn))
                continue
            prm = self.params(pc)
            col, new = build_arch_proto(prm[0], *prm[1], **prm[2])
            if not self.match(have, new):
                fail.add("%s: %s is not the new build after the patch" % (self.name, pcn))
            free_temp(col)


def _mat_of(me, i=0):
    """A mesh's material (the builders take Material objects as well as names; area variants such as
    formation_marble_aged are registered only while their area builds)."""
    return me.materials[i] if len(me.materials) > i else None


class Column(ArchProtoPart):
    """#11: the column's shaft starts on its foot ring (A.COLUMN_SHAFT_ON_RING): it ran down through the ring, 8-10 mm
    inside the ring's faces (steles and mission corridors, link pavilions, every hall)."""
    name, item = "column", "#11"
    RX = r"^arch\.p\.column\.\d+_\d+\.[A-Za-z0-9_]+$"

    def params(self, pc):
        parts = {o.name[len(pc.name) + 1:]: o for o in pc.all_objects}
        base, shaft, ring = parts["base"].data, parts["shaft"].data, parts["ring"].data
        r = float(np.abs(coords(base)[:, :2]).max()) / 1.32
        height = float(coords(shaft)[:, 2].max())
        return A._p_column, (height, r, _mat_of(shaft), _mat_of(base), _mat_of(ring)), {}


class Lattice(ArchProtoPart):
    """#13, #21: lattice doors, windows and hanging fascias: frame, bars, boards, medallion and gold plates joined into
    one surface (the crossing bars of a pattern lay 0 or 2 mm apart, the bars ran into the frame 10-24 mm inside its
    faces, the gold plates and the medallion were boxes half sunk into the frame), and the paper 2.5 cm behind the bars
    (was 4 mm)."""
    name, item = "lattice", "#13"
    TAGGED = "union"
    RX = r"^arch\.p\.lattice\."
    KEY = re.compile(r"^arch\.p\.lattice\.(\d+)_(\d+)\.(grid|diamond|ice)\.(window|door)\.(lit|dim)\.(\d+)\."
                     r"([A-Za-z0-9_]+?)(\.open)?$")

    def params(self, pc):
        m = self.KEY.match(pc.name)
        if m is None:
            raise ValueError("unknown lattice key")
        w, h = lattice_size(pc)
        return A._p_lattice, (w, h, m.group(3), m.group(4), m.group(5) == "lit", int(m.group(6)), m.group(7),
                              m.group(8) is None), {}


def lattice_size(pc):
    """(width, height) of a lattice prototype, read off its left stile (the first box): x -w/2 .. -w/2 + fw and z
    -fw/2 .. h + fw/2 when it was built as a bar (before round 12), 0 .. h as an exact box; the key's centimetres pick
    which."""
    m = Lattice.KEY.match(pc.name)
    o = [o for o in pc.all_objects if o.type == 'MESH'][0]
    c = coords(o.data)[:8]
    fw = float(c[:, 0].max() - c[:, 0].min())
    w = round(-2.0 * float(c[:, 0].min()), 3)
    for h in (round(float(c[:, 2].max()) - fw / 2.0, 3), round(float(c[:, 2].max()), 3)):
        if round(w * 100) == int(m.group(1)) and round(h * 100) == int(m.group(2)):
            return w, h
    raise ValueError("size %.3f x ? does not fit the key" % w)


class Panel(ArchProtoPart):
    """#25: the balustrade panel (sill, board, carved border, vases, handrail) joined into one surface (the border's
    stiles and rails overlapped at 0 mm, the border stood 14 mm over the board on a face 2 mm inside it); the wooden
    railing's balusters stop at its mid rail (they ran through it, 11 mm inside its faces) and the drum stone's scroll
    is thinner (its faces lay 11 mm inside the base block's)."""
    name, item = "panel", "#25"
    TAGGED = None
    RX = r"^arch\.p\.(panel|railpanel|drum)\.\d+\.[A-Za-z0-9_]+$"

    def params(self, pc):
        kind, hmm, mat = re.match(r"^arch\.p\.(panel|railpanel|drum)\.(\d+)\.([A-Za-z0-9_]+)$", pc.name).groups()
        h = int(hmm) / 1000.0
        fn = {"panel": A._p_panel, "railpanel": A._p_rail_panel, "drum": A._p_drum_stone}[kind]
        me = [o for o in pc.all_objects if o.type == 'MESH'][0].data
        return fn, (h, _mat_of(me)), {}


class Seat(ArchProtoPart):
    """#39: the pavilion bench's skirt stands 2.5 cm in from the seat board's back and ends and stops at its underside
    (its back lay 2 mm behind the board's, its ends in the board's end faces)."""
    name, item = "seat", "#39"
    RX = r"^arch\.p\.seat\.\d+\.[A-Za-z0-9_]+$"

    def params(self, pc):
        lcm, mat = re.match(r"^arch\.p\.seat\.(\d+)\.([A-Za-z0-9_]+)$", pc.name).groups()
        me = [o for o in pc.all_objects if o.type == 'MESH'][0].data
        return A._p_seat, (int(lcm) / 100.0,), dict(mat=_mat_of(me))


class Chiwen(ArchProtoPart):
    """#32: the chiwen's three relief layers step up at the bottom (their bottoms lay in one plane), the back fin and
    the sword handle are thinner (30 and 20 mm inside the outline layer's faces) and the guard taller (35 mm thin)."""
    name, item = "chiwen", "#32"
    RX = r"^arch\.p\.chiwen2\.[A-Za-z0-9_]+$"

    def params(self, pc):
        return A._p_chiwen, (pc.name.split(".")[-1],), {}


class Dougong(Part):
    """#15: every dougong bracket set joined into one surface (A.DOUGONG_UNION): the crossing arms of a tier had their
    tops and bottoms in one plane (corner sets: three members crossing). The corner sets are rebuilt from the source
    (verify round): their two tier-3 arms along the side lines are A.CORNER_ARM_W wide; at 1.0 their faces lay in the
    faces of the bracket band's wall-line beams (same facing, 0 mm) at every corner of a band. A corner set's size (hs)
    is read off its mesh (its top is 8.2 bracket units); the file's set must equal the old build, or the joined one the
    first version of this patch made (R12A), or the new build (done)."""
    name, item = "dougong", "#15"
    R12A = dict(DOUGONG_UNION=True, CORNER_ARM_W=None)

    def plan(self, fail):
        self.jobs = []
        for pcn in protos_matching(r"^arch\.p\.dougong\.\d+(\.c)?$"):
            pc = bpy.data.collections[pcn]
            obs = [o for o in pc.all_objects if o.type == 'MESH']
            if len(obs) != 1 or not obs[0].name.endswith(".set"):
                fail.add("dougong: %s is not one '.set' object" % pcn)
                continue
            me = obs[0].data
            self.protos.append(pcn)
            if pcn.endswith(".c"):
                hs = float(coords(me)[:, 2].max()) / 0.82
                have = {"set": obs[0]}
                colN, new = build_arch_proto(A._p_dougong, hs, corner=True)
                if ArchProtoPart.match(self, have, new):
                    self.done.append(pcn)
                    free_temp(colN)
                    continue
                colO, old = build_arch_proto(A._p_dougong, hs, corner=True, old=True)
                state = "old" if ArchProtoPart.match(self, have, old) else None
                free_temp(colO)
                if state is None:
                    with knobs(A, self.R12A):
                        colR, r12a = build_arch_proto(A._p_dougong, hs, corner=True)
                    state = "joined" if ArchProtoPart.match(self, have, r12a) else None
                    free_temp(colR)
                if state is None:
                    fail.add("dougong: %s is neither the old, the joined nor the new corner set (hs %.4f)" % (pcn, hs))
                    free_temp(colN)
                    continue
                self.jobs.append((obs[0], colN, new["set"].data))
                self.todo.append(pcn)
                log("dougong: %s (hs %.4f) is the %s corner set: rebuild" % (pcn, hs, state))
                continue
            if me.get(A.R12_TAG) == "union":
                self.done.append(pcn)
                continue
            # the old set: closed boxes and prisms, nothing joined (each part its own island)
            if len(me.vertices) % 1 or len(me.polygons) < 40:
                fail.add("dougong: %s does not look like the old set" % pcn)
                continue
            self.todo.append(pcn)
        log("dougong: %d sets, %d to join or rebuild, %d done already" % (len(self.protos), len(self.todo),
                                                                       len(self.done)))
        return bool(self.todo)

    def apply(self):
        rebuilt = set()
        for o, col, nm in self.jobs:
            box0 = local_box(o.data)
            n0 = len(o.data.polygons)
            swap_mesh([o], nm)
            free_temp(col)
            if grew(box0, local_box(o.data)):
                self.grown.append(o.name)
            rebuilt.add(o.users_collection[0].name)
            log("dougong: rebuilt %s: %d -> %d faces" % (o.name, n0, len(o.data.polygons)))
        for pcn in self.todo:
            if pcn in rebuilt:
                continue
            o = [o for o in bpy.data.collections[pcn].all_objects if o.type == 'MESH'][0]
            n0 = len(o.data.polygons)
            A._self_union(o.data)
            log("dougong: joined %s: %d -> %d faces" % (pcn, n0, len(o.data.polygons)))

    def check(self, fail, dg):
        for pcn in self.protos:
            o = [o for o in bpy.data.collections[pcn].all_objects if o.type == 'MESH'][0]
            if o.data.get(A.R12_TAG) != "union":
                fail.add("dougong: %s not joined" % pcn)
            if pcn.endswith(".c"):
                hs = float(coords(o.data)[:, 2].max()) / 0.82
                col, new = build_arch_proto(A._p_dougong, hs, corner=True)
                if not ArchProtoPart.match(self, {"set": o}, new):
                    fail.add("dougong: %s is not the new corner set after the patch" % pcn)
                free_temp(col)


def band_roots():
    """Bracket-band roots (A.bracket_band: custom props arch_top_z, arch_projection) with their '.beams' child."""
    out = []
    for o in bpy.data.objects:
        if o.type == 'EMPTY' and "arch_projection" in o and "arch_top_z" in o:
            b = bpy.data.objects.get(o.name + ".beams")
            if b is not None and b.parent == o:
                out.append((o, b))
    return sorted(out, key=lambda r: r[0].name)


class Band(Part):
    """#15: the bracket band's beams: the outer purlin beam rests on the dougong sets' outer tier-3 arms
    (A.BAND_BEAM2_Z: it was flush with their sides and top) and every beam box is joined into one surface
    (A.BAND_UNION: they crossed at each corner, the frieze and architraves met face to face). Also the paifang and
    corridor painted beams (A.BEAMS_UNION)."""
    name, item = "band", "#15"

    @staticmethod
    def SCOPE(a, b):       # beams and bracket sets against each other (not a corridor beam's top, level with the
        return all(".beams" in x or "dougong" in x for x in (a, b))    # post tops under the roof)

    def plan(self, fail):
        self.bands, self.painted = [], []
        for root, beams in band_roots():
            me = beams.data
            self.objects.append(beams.name)
            if me.get(A.R12_TAG) == "union":
                self.done.append(beams.name)
                continue
            H = float(root["arch_top_z"])
            hs = H / 1.2
            u = hs / 10.0
            zb = 0.2 * hs
            z0, z1 = zb + OLD_ARCH["BAND_BEAM2_Z"][0] * u, zb + OLD_ARCH["BAND_BEAM2_Z"][1] * u
            c = coords(me)
            if len(c) % 8 or len(me.polygons) != len(c) // 8 * 6:
                fail.add("band: %s is not a set of boxes (%d verts, %d faces)" % (beams.name, len(c), len(me.polygons)))
                continue
            hit = []
            for k in range(len(c) // 8):
                zz = c[8 * k:8 * k + 8, 2]
                if np.abs(zz[:4] - z0).max() < 1e-4 and np.abs(zz[4:] - z1).max() < 1e-4:
                    hit.append(k)
            if len(hit) < 3:
                fail.add("band: %s: %d outer purlin boxes at z %.4f..%.4f (want one per side)" % (beams.name, len(hit),
                                                                                                    z0, z1))
                continue
            nz0, nz1 = zb + A.BAND_BEAM2_Z[0] * u, zb + A.BAND_BEAM2_Z[1] * u
            self.bands.append((beams, hit, nz0, nz1))
            self.todo.append(beams.name)
        for o in bpy.data.objects:
            if o.type != 'MESH' or not o.name.endswith(".beams") or o.name in self.objects:
                continue
            mats = [m.name if m else None for m in o.data.materials]
            if mats[:3] != [A._mat("arch_beam_paint").name, A._mat("arch_paint_box").name,
                            A._mat("arch_paint_red").name]:
                continue
            self.objects.append(o.name)
            if o.data.get(A.R12_TAG) == "union":
                self.done.append(o.name)
                continue
            self.painted.append(o)
            self.todo.append(o.name)
        log("band: %d bracket bands, %d painted beam sets; %d to join, %d joined already" % (
            len(band_roots()), len(self.objects) - len(band_roots()), len(self.todo), len(self.done)))
        return bool(self.todo)

    def apply(self):
        for beams, hit, nz0, nz1 in self.bands:
            me = beams.data
            c = coords(me)
            for k in hit:
                c[8 * k:8 * k + 4, 2] = nz0
                c[8 * k + 4:8 * k + 8, 2] = nz1
            me.vertices.foreach_set("co", c.ravel())
            me.update()
            box0 = world_box(beams)
            n0 = len(me.polygons)
            A._self_union(me)
            if grew(box0, world_box(beams)):
                self.grown.append(beams.name)
            self.chunks.add(area_of(beams))
            log("band: %s: purlin raised on %d sides, joined: %d -> %d faces" % (beams.name, len(hit), n0,
                                                                                 len(me.polygons)))
        for o in self.painted:
            n0 = len(o.data.polygons)
            A._self_union(o.data)
            self.chunks.add(area_of(o))
            log("band: %s joined: %d -> %d faces" % (o.name, n0, len(o.data.polygons)))

    def check(self, fail, dg):
        for n in self.objects:
            if bpy.data.objects[n].data.get(A.R12_TAG) != "union":
                fail.add("band: %s not joined" % n)


RUNE_MESH = re.compile(r"^props\.rune_ring\.(trigram|sigil|script)\.([^.]+)\.([^.]+)\.(\d+)\.v(\d+)$")


class Rune(Part):
    """#2: every rune ring (props.rune_ring: summit.ring, arena.bagua, arena.script_ring, forge.rune_ring,
    gate.rune_ring, scroll.ring, scroll.ring_in, mirror.mirror_runes) becomes a raised inlay: its flat pattern, a sheet
    8 mm over the floor, now stands 4 cm high with sides 2 cm down into the floor and no bottom (P._rune_band); the
    object drops the 8 mm lift where its origin still stands that high over the floor (floor_z). Children
    (scroll.ring.groove, until lane A removes it) keep their place."""
    name, item = "rune", "#2"

    def plan(self, fail):
        self.meshes = {}
        for o in bpy.data.objects:
            if o.type != 'MESH':
                continue
            m = RUNE_MESH.match(o.data.name)
            if m is None:
                continue
            self.objects.append(o.name)
            ver = int(m.group(5))
            if ver == P.RUNE_KEY_VERSION:
                self.done.append(o.name)
                continue
            if ver != 4 or np.abs(coords(o.data)[:, 2]).max() > 1e-6:
                fail.add("rune: %s's mesh %s is not the old flat ring" % (o.name, o.data.name))
                continue
            self.meshes.setdefault(o.data.name, []).append(o)
            self.todo.append(o.name)
        log("rune: %d rings (%s), %d to raise, %d raised already" % (len(self.objects), ", ".join(self.objects),
                                                                       len(self.todo), len(self.done)))
        return bool(self.todo)

    @staticmethod
    def floor_z(o, dg):
        """Median height, in ring ``o``'s own frame, of what lies under its band (rays straight down through the band's
        middle radius at 72 angles, passing through the ring and its children), or None."""
        sc = bpy.context.scene
        c = coords(o.data)
        r = np.hypot(c[:, 0], c[:, 1])
        rm = 0.5 * (float(r.min()) + float(r.max()))
        skip = {o.name} | {k.name for k in o.children_recursive}
        W = o.matrix_world
        Wi = W.inverted()
        d = (W.to_3x3() @ Vector((0, 0, -1))).normalized()
        zs = []
        for k in range(72):
            a = 2.0 * math.pi * k / 72
            p = W @ Vector((rm * math.cos(a), rm * math.sin(a), 0.5))
            left = 1.0
            for _ in range(20):
                hit, loc, nor, fi, ob, mx = sc.ray_cast(dg, p, d, distance=left)
                if not hit:
                    break
                if ob.original.name not in skip:
                    zs.append((Wi @ loc).z)
                    break
                left -= (loc - p).length + 1e-4
                p = loc + d * 1e-4
                if left <= 0:
                    break
        return float(np.median(zs)) if len(zs) >= 36 else None

    def apply(self):
        moved = []
        # verify round: a ring is lowered by the old lift only where its origin still stands that far over the floor
        # (scroll.ring and scroll.ring_in already had their origins on the paving: lowered too, their band stood 3.2 cm
        # proud, not 4, and where the areas patch ran first the two patches' results differed)
        dg = bpy.context.evaluated_depsgraph_get()
        floors = {o.name: self.floor_z(o, dg) for obs in self.meshes.values() for o in obs}
        for mname, obs in sorted(self.meshes.items()):
            old = bpy.data.meshes[mname]
            key = re.sub(r"\.v4$", ".v%d" % P.RUNE_KEY_VERSION, mname)
            bm = bmesh.new()
            bm.from_mesh(old)
            P._rune_band(bm)
            new = bpy.data.meshes.new(key)
            bm.to_mesh(new)
            bm.free()
            new["sect_shared"] = key
            for m in old.materials:
                new.materials.append(m)
            log("rune: %s -> %s: %d -> %d faces" % (mname, new.name, len(old.polygons), len(new.polygons)))
            for o in obs:
                moved.append((o, [(c, c.matrix_world.copy()) for c in o.children]))
                o.data = new
                fz = floors[o.name]
                lift = fz is None or fz < -0.5 * P.RUNE_LIFT_OLD
                if lift:
                    o.location.z -= P.RUNE_LIFT_OLD
                log("rune: %s: the floor under it at %s in its frame: %s" % (
                    o.name, "?" if fz is None else "%.4f" % fz, "lowered %.3f m" % P.RUNE_LIFT_OLD if lift else
                    "its origin is on the floor already, kept"))
                self.grown.append(o.name)
                self.chunks.add(area_of(o))
            if old.users == 0:
                bpy.data.meshes.remove(old)
        bpy.context.view_layer.update()
        for o, kids in moved:
            for c, mw in kids:
                c.matrix_world = mw
                log("rune: %s keeps its place under %s" % (c.name, o.name))
        bpy.context.view_layer.update()

    def check(self, fail, dg):
        sc = bpy.context.scene
        for n in self.objects:
            o = bpy.data.objects[n]
            if not o.data.name.endswith(".v%d" % P.RUNE_KEY_VERSION):
                fail.add("rune: %s still has %s" % (n, o.data.name))
                continue
            c = coords(o.data)
            zr = (float(c[:, 2].min()), float(c[:, 2].max()))
            if abs(zr[0] + P.RUNE_SINK) > 1e-5 or abs(zr[1] - P.RUNE_TOP) > 1e-5:
                fail.add("rune: %s spans z %.4f..%.4f" % (n, zr[0], zr[1]))
            # the floor under the band: rays down the ring's own axis just outside its outer edge
            r_out = float(np.hypot(c[:, 0], c[:, 1]).max())
            W = o.matrix_world
            Wi = W.inverted()
            zl, miss = [], 0
            for k in range(72):
                a = 2.0 * math.pi * k / 72
                p = Vector(((r_out + 0.01) * math.cos(a), (r_out + 0.01) * math.sin(a), 0.5))
                q = Vector(((r_out + 0.01) * math.cos(a), (r_out + 0.01) * math.sin(a), -0.5))
                pw, qw = W @ p, W @ q
                d = (qw - pw)
                hit, loc, nor, fi, ob, mx = sc.ray_cast(dg, pw, d.normalized(), distance=d.length)
                if not hit:
                    miss += 1
                    continue
                zl.append((Wi @ loc).z)
            zl = np.array(zl) if zl else np.zeros(0)
            bad = int(((zl < -P.RUNE_SINK + 0.002) | (zl > P.RUNE_TOP - 0.02)).sum()) if len(zl) else 0
            log("rune: %s: band z %.3f..%.3f; the floor just outside it %s (%d of 72 rays hit)" % (
                n, zr[0], zr[1], "at %.4f..%.4f" % (zl.min(), zl.max()) if len(zl) else "not found", len(zl)))
            if len(zl) < 36 or bad > 2:
                fail.add("rune: %s: the floor next to the band is not between %.3f and %.3f (%d bad, %d misses)" % (
                    n, -P.RUNE_SINK + 0.002, P.RUNE_TOP - 0.02, bad, miss))


def corridor_floors():
    """{corridor root: [floor objects in build order]} for every A.corridor (its '.floor', '.floor.001', ... children,
    8-vertex boxes)."""
    out = {}
    for o in bpy.data.objects:
        if o.type != 'MESH' or o.parent is None:
            continue
        m = re.match(r"^(.*)\.floor(\.(\d{3}))?$", o.name)
        if m is None or m.group(1) != o.parent.name or len(o.data.vertices) != 8:
            continue
        if bpy.data.objects.get(o.parent.name + ".beams") is None:
            continue
        out.setdefault(o.parent, []).append((int(m.group(3) or 0), o))
    return {r: [o for _k, o in sorted(v)] for r, v in out.items()}


def _floor_old_frame(me):
    """(fa, fb, half width, top z, bottom z) of an old floor box (A._wall_box order: start right, end right, end left,
    start left at the bottom, then the top)."""
    c = coords(me)
    v0, v1, v2, v3 = (Vector(c[i][:2]) for i in range(4))
    fa, fb = (v0 + v3) * 0.5, (v1 + v2) * 0.5
    return fa, fb, (v3 - v0).length * 0.5, float(c[4, 2]), float(c[0, 2])


def _inside_quad(q, p):
    for i in range(4):
        a, b = q[i], q[(i + 1) % 4]
        if (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) < -1e-9:
            return False
    return True


class Corridor(Part):
    """#3: corridor floors (steles.lang, mission.lang, both sides): each segment's strip now ends on the bisector of
    its joint (A.CORRIDOR_MITRE), so the strips meet edge to edge. They ran half the width past every inner joint and
    overlapped over the corner square at 0 mm (and left a notch at its outer side). The floor's top stays where it was."""
    name, item = "corridor", "#3"

    @staticmethod
    def SCOPE(a, b):       # floor against floor (a floor's contact with the terrace or a pavilion is the area's)
        return ".floor" in a and ".floor" in b

    def plan(self, fail):
        self.jobs = []
        cf = corridor_floors()
        for root, floors in sorted(cf.items(), key=lambda kv: kv[0].name):
            n = len(floors)
            frames = [_floor_old_frame(f.data) for f in floors]
            half = frames[0][2]
            hw = half - 0.45
            ph, z0 = frames[0][3], frames[0][4]
            state, pts = None, None
            # the polyline, read off the old strips (each ran hw past an inner joint, 0.4 m past a free end)
            p_try = []
            for si, (fa, fb, h_, ph_, z0_) in enumerate(frames):
                t = (fb - fa).normalized()
                a = fa + t * (hw if si > 0 else 0.4)
                b = fb - t * (hw if si < n - 1 else 0.4)
                if si == 0:
                    p_try.append(a)
                elif (p_try[-1] - a).length > 1e-3:
                    p_try = None
                    break
                p_try.append(b)
            if p_try is not None:
                pts = p_try
            else:
                # mitred strips (start right, end right, end left, start left): an inner joint is the middle of the
                # strip's mitre edge, a free end lies 0.4 m in from the strip's straight end
                pts = []
                for si, f in enumerate(floors):
                    c = coords(f.data)
                    ar, br, bl, al = (Vector(c[i][:2]) for i in range(4))
                    t = (br - ar).normalized()
                    if si == 0:
                        pts.append((ar + al) * 0.5 + t * 0.4)
                    pts.append((br + bl) * 0.5 - (t * 0.4 if si == n - 1 else Vector((0.0, 0.0))))
            if pts is not None and len(pts) == n + 1:
                oldq, newq = [], []
                for si in range(n):
                    a, b = pts[si], pts[si + 1]
                    t = (b - a).normalized()
                    fa, fb = a - t * (hw if si > 0 else 0.4), b + t * (hw if si < n - 1 else 0.4)
                    v, f, m = [], [], []
                    A._wall_box(v, f, m, fa, fb, 2 * half, z0, ph, 0)
                    oldq.append(np.array(v))
                    v, f, m = [], [], []
                    A._quad_box(v, f, m, A._corridor_floor_quad(pts, si, half), z0, ph, 0)
                    newq.append(np.array(v))
                have = [coords(f.data) for f in floors]
                if all(np.abs(h - q).max() < TOL for h, q in zip(have, oldq)):
                    state = "old"
                elif all(np.abs(h - q).max() < TOL for h, q in zip(have, newq)):
                    state = "new"
            if state is None:
                fail.add("corridor: %s's %d floors are neither the old nor the new strips of one polyline" % (
                    root.name, n))
                continue
            self.objects += [f.name for f in floors]
            if state == "new":
                self.done += [f.name for f in floors]
                continue
            self.todo += [f.name for f in floors]
            self.jobs.append((root, floors, newq, pts))
            log("corridor: %s: %d floors over %d points, width %.2f, top z %.3f" % (root.name, n, len(pts),
                                                                                   2 * half - 0.9, ph))
        log("corridor: %d corridors, %d floors to mitre, %d mitred already" % (len(cf), len(self.todo),
                                                                               len(self.done)))
        return bool(self.todo)

    def apply(self):
        for root, floors, newq, pts in self.jobs:
            for f, q in zip(floors, newq):
                box0 = world_box(f)
                f.data.vertices.foreach_set("co", q.ravel())
                f.data.update()
                if grew(box0, world_box(f)):
                    self.grown.append(f.name)
                self.chunks.add(area_of(f))

    def check(self, fail, dg):
        # every point inside the strips' outlines has exactly one floor top over it, at the strips' height
        for root, floors in corridor_floors().items():
            if not any(f.name in self.objects for f in floors):
                continue
            trees = [BVHTree.FromPolygons([Vector(v) for v in coords(f.data)], [tuple(p.vertices) for p in
                                                                                 f.data.polygons]) for f in floors]
            ph = max(float(coords(f.data)[:, 2].max()) for f in floors)
            quads = [coords(f.data)[4:, :2] for f in floors]
            co = np.concatenate(quads)
            lo, hi = co.min(0), co.max(0)
            n = dbl = gap = offz = 0
            for x in np.arange(lo[0] + 0.0371, hi[0], 0.1003):      # (off any edge: a ray there can miss both
                for y in np.arange(lo[1] + 0.0529, hi[1], 0.0997):  # strips or meet both)
                    if not any(_inside_quad(q, (x, y)) for q in quads):
                        continue
                    n += 1
                    hits = 0
                    for t in trees:
                        loc = t.ray_cast(Vector((x, y, ph + 1.0)), Vector((0, 0, -1)), 2.0)[0]
                        if loc is not None and abs(loc.z - ph) < 1e-4:
                            hits += 1
                        elif loc is not None and loc.z > ph - 0.01:
                            offz += 1
                    if hits > 1:
                        dbl += 1
                    elif hits == 0:
                        gap += 1
            log("corridor: %s: %d points inside its floors: %d under two floor tops, %d under none, %d off z %.3f" % (
                root.name, n, dbl, gap, offz, ph))
            # (a point on a shared mitre edge meets both strips: allow a line of them)
            if gap or offz or dbl > 0.02 * n:
                fail.add("corridor: %s: %d doubled, %d without a floor top, %d off its height" % (root.name, dbl, gap,
                                                                                                  offz))


class Inlays(Part):
    """#14, #10: the formation floor's glow round the bronze trigram bars (formation.bagua_leak, a sheet 4 mm up) and
    its moss (formation.moss, sheets 8 mm up, overlapping one another) become closed solids 4 cm high with sides 2 cm
    into the floor (AP.INLAY_SOLID); the moss patches are joined into one outline first."""
    name, item = "inlays", "#14 #10"
    NAMES = (("formation.bagua_leak", "leak"), ("formation.moss", "moss"))

    def plan(self, fail):
        from sect.areas import formation as FO
        self.FO = FO
        self.jobs = []
        for nm, kind in self.NAMES:
            o = bpy.data.objects.get(nm)
            if o is None or o.type != 'MESH':
                fail.add("inlays: no %s" % nm)
                continue
            self.objects.append(nm)
            new = self.build(kind, False)
            if same_geo(o.data, new):
                self.done.append(nm)
                bpy.data.meshes.remove(new)
                continue
            old = self.build(kind, True)
            ok = same_geo(o.data, old)
            bpy.data.meshes.remove(old)
            if not ok:
                fail.add("inlays: %s is neither the old nor the new %s" % (nm, kind))
                bpy.data.meshes.remove(new)
                continue
            self.jobs.append((o, new))
            self.todo.append(nm)
            log("inlays: %s: %d faces -> %d" % (nm, len(o.data.polygons), len(new.polygons)))
        return bool(self.todo)

    def build(self, kind, old):
        bm = bmesh.new()
        with knobs(AP, OLD_AP if old else {}):
            if kind == "leak":
                bar = bmesh.new()
                AP.bagua(bar, bm, self.FO.STATION_ANGLES, self.FO.TRIGRAMS)
                bar.free()
            else:
                AP.moss_patches(bm, self.FO._moss_spots(), 77)
        me = bpy.data.meshes.new("_r12_" + kind)
        bm.to_mesh(me)
        bm.free()
        U.shade_flat(me)
        return me

    def apply(self):
        for o, new in self.jobs:
            for m in o.data.materials:
                new.materials.append(m)
            box0 = world_box(o)
            swap_mesh([o], new)
            if grew(box0, world_box(o)):
                self.grown.append(o.name)
            self.chunks.add(area_of(o))

    def check(self, fail, dg):
        sc = bpy.context.scene
        for nm, kind in self.NAMES:
            o = bpy.data.objects[nm]
            c = coords(o.data)
            if abs(c[:, 2].min() + AP.INLAY_SINK) > 1e-5 or abs(c[:, 2].max() - AP.INLAY_TOP) > 1e-5:
                fail.add("inlays: %s spans z %.4f..%.4f" % (nm, c[:, 2].min(), c[:, 2].max()))
            # its walls reach into the floor: rays just outside every outline vertex find the floor at z 0 (2 mm)
            W = o.matrix_world
            Wi = W.inverted()
            bm = bmesh.new()
            bm.from_mesh(o.data)
            rim = [e for e in bm.edges if len(e.link_faces) == 2 and any(abs(f.normal.z) < 0.5 for f in e.link_faces)
                   and all(v.co.z > AP.INLAY_TOP - 1e-6 for v in e.verts)]
            bad = n = 0
            for e in rim[::max(1, len(rim) // 400)]:
                f = next(f for f in e.link_faces if abs(f.normal.z) < 0.5)
                mid = (e.verts[0].co + e.verts[1].co) * 0.5
                p = mid + f.normal * 0.01
                hit, loc, nor, fi, ob, mx = sc.ray_cast(dg, W @ Vector((p.x, p.y, 0.3)), Vector((0, 0, -1)),
                                                       distance=0.6)
                if hit and (Wi @ loc).z > 0.002:
                    continue                # something stands on the floor there (the bronze bar over the leak)
                n += 1
                if not hit or abs((Wi @ loc).z) > 0.002:
                    bad += 1
            bm.free()
            log("inlays: %s: z %.3f..%.3f; the floor beside its outline at z 0 at %d of %d points" % (
                nm, c[:, 2].min(), c[:, 2].max(), n - bad, n))
            if bad > 0.05 * max(n, 1):
                fail.add("inlays: %s: %d of %d points beside it are not on the floor" % (nm, bad, n))


def stele_parts(pc):
    return {part_of(o.name): o for o in pc.all_objects if o.type == 'MESH'}


class Stele(Part):
    """#26: the stele glyphs (the Jin Yong manuals, 3-4 mm in front of the slab and the crown) are cut into the slab's
    faces and the crown's front: the slab and crown get holes, the glyphs fill them in the same plane
    (P._stele_cut); the key-fret border's strokes get holes under them too."""
    name, item = "stele", "#26"
    NEED = ("props.stele.slab", "props.stele.glyphs", "props.stele.crown", "props.stele.border")
    SCOPE = r"props\.stele\.(slab|glyphs|border)$"

    def plan(self, fail):
        for pcn in protos_matching(r"^props\.stele\."):
            pc = bpy.data.collections[pcn]
            parts = stele_parts(pc)
            if any(k not in parts for k in self.NEED):
                fail.add("stele: %s lacks %s" % (pcn, [k for k in self.NEED if k not in parts]))
                continue
            self.protos.append(pcn)
            g = parts["props.stele.glyphs"].data
            if g.get(P.R12_TAG) == "cut":
                self.done.append(pcn)
                continue
            slab, crown = parts["props.stele.slab"].data, parts["props.stele.crown"].data

            def plane(me, ny):
                p = max((p for p in me.polygons if p.normal.y * ny > 0.9999), key=lambda p: p.area)
                return me.vertices[p.vertices[0]].co.y
            yf, yb, yc = plane(slab, -1.0), plane(slab, 1.0), plane(crown, -1.0)
            s = (yb - yf) / 0.32
            want = np.array([yf - 0.003 * s, yb + 0.003 * s, yc - 0.004 * s])
            y = coords(g)[:, 1]
            off = np.abs(y[:, None] - want[None, :]).min(1)
            if off.max() > 1e-4:
                fail.add("stele: %s's glyphs are not the old layout (3 / 4 mm x s off the slab and crown: %.5f)" % (
                    pcn, off.max()))
                continue
            self.todo.append(pcn)
        log("stele: %d steles, %d to cut, %d cut already" % (len(self.protos), len(self.todo), len(self.done)))
        return bool(self.todo)

    def apply(self):
        for pcn in self.todo:
            parts = stele_parts(bpy.data.collections[pcn])
            g = parts["props.stele.glyphs"].data
            n0 = len(g.polygons)
            P._stele_cut(parts["props.stele.slab"].data, parts["props.stele.crown"].data, g,
                         parts["props.stele.border"].data)
            log("stele: %s: glyphs %d faces -> %d triangles in the slab's and crown's planes" % (pcn, n0,
                                                                                               len(g.polygons)))

    def check(self, fail, dg):
        for pcn in self.protos:
            parts = stele_parts(bpy.data.collections[pcn])
            g = parts["props.stele.glyphs"].data
            if g.get(P.R12_TAG) != "cut" or not len(g.polygons):
                fail.add("stele: %s not cut" % pcn)


class Gable(Part):
    """#34: the bargeboards of every gable roof joined into one surface (A.GABLE_UNION): the two boards of a gable
    overlapped under its apex."""
    name, item = "gable", "#34"

    def plan(self, fail):
        for o in bpy.data.objects:
            if o.type == 'MESH' and re.search(r"\.bargeboard(\.\d{3})?$", o.name) and o.parent is not None:
                self.objects.append(o.name)
                (self.done if o.data.get(A.R12_TAG) == "union" else self.todo).append(o.name)
        log("gable: %d bargeboard sets, %d to join" % (len(self.objects), len(self.todo)))
        return bool(self.todo)

    def apply(self):
        for n in self.todo:
            o = bpy.data.objects[n]
            n0 = len(o.data.polygons)
            A._self_union(o.data)
            self.chunks.add(area_of(o))
            log("gable: %s joined: %d -> %d faces" % (n, n0, len(o.data.polygons)))

    def check(self, fail, dg):
        for n in self.objects:
            if bpy.data.objects[n].data.get(A.R12_TAG) != "union":
                fail.add("gable: %s not joined" % n)


BANNER_MESH = re.compile(r"^props\.banner_cloth\.(fan|qi)\.([^.]+)\.([^.]+)\.(\d)\.([^.]+)\.([0-9a-f]{8})\.([a-z]+)"
                         r"\.v4$")


def _unk(s):
    return float(s.replace("p", ".").replace("m", "-"))


class Banner(Part):
    """#9: banner and flag cloth: the characters, the sun-and-moon emblem and its ring are material regions of the
    cloth (P.BANNER_REGIONS), cut into it before it is bent; they were extra layers 3-5 mm off both faces. Seen from
    behind, the characters now read mirrored, as on real cloth."""
    name, item = "banner", "#9"

    def plan(self, fail):
        import zlib
        from sect.areas import formation as FO
        cands = {"": None}
        for f in getattr(FO, "ELEMENT_FLAGS", ()):
            cands[f[1]] = f[1]
        self.jobs = []
        meshes = {}
        for o in bpy.data.objects:
            if o.type == 'MESH' and BANNER_MESH.match(o.data.name):
                meshes.setdefault(o.data.name, []).append(o)
        for mname, obs in sorted(meshes.items()):
            style, Wk, Lk, seed, windk, tkey, emblem = BANNER_MESH.match(mname).groups()
            self.objects += [o.name for o in obs]
            me = bpy.data.meshes[mname]
            if me.get(P.R12_TAG) == "regions":
                self.done += [o.name for o in obs]
                continue
            text = None
            for t in cands:
                if "%08x" % (zlib.crc32(t.encode("utf-8")) & 0xFFFFFFFF) == tkey:
                    text = cands[t]
                    break
            else:
                fail.add("banner: %s: text %s unknown" % (mname, tkey))
                continue
            wind = _unk(windk)
            loc = obs[0].location
            if style == "fan" and abs(loc.y) < 1e-6 and loc.x > 0.7:
                W = (loc.x - 0.75) / 0.6
                height = loc.z + 0.41
                L = height * 0.6
                L = max(0.8, min(L, height - 0.35 - 0.06 - 0.4))
                L = max(0.5 * W + 0.3, L)
            elif style == "qi":
                W = _unk(Wk)
                height = loc.z + 0.32
                L = max(0.3, min(0.8 * W, height - 1.2))
            else:
                W, L = _unk(Wk), _unk(Lk)
            if P._k(W) != Wk or P._k(L) != Lk:
                fail.add("banner: %s: width %.4f / length %.4f do not fit the key" % (mname, W, L))
                continue
            em = None if emblem == "none" else emblem
            with knobs(P, OLD_PROPS):
                old = P._banner_cloth_mesh(W, L, int(seed), wind, style, text, em, fresh=True)
            ok = same_geo(me, old)
            bpy.data.meshes.remove(old)
            if not ok:
                fail.add("banner: %s is not the old cloth of width %.3f, length %.3f" % (mname, W, L))
                continue
            new = P._banner_cloth_mesh(W, L, int(seed), wind, style, text, em, fresh=True)
            self.jobs.append((obs, new))
            self.todo += [o.name for o in obs]
            log("banner: %s (%d banners): %d faces -> %d" % (mname, len(obs), len(me.polygons), len(new.polygons)))
        log("banner: %d cloths, %d to redo, %d done already" % (len(self.objects), len(self.todo), len(self.done)))
        return bool(self.todo)

    def apply(self):
        for obs, new in self.jobs:
            old = obs[0].data
            for m in old.materials:
                new.materials.append(m)
            new[P.R12_TAG] = "regions"
            boxes = [world_box(o) for o in obs]
            swap_mesh(obs, new)
            # the wave modifier's 'flutter' weights live on the mesh: write them for the new vertices
            vg = obs[0].vertex_groups.get("flutter")
            if vg is not None:
                for i, w in enumerate(new.get("props_weights", [])):
                    if w > 0:
                        vg.add([i], float(w), 'REPLACE')
            for o, b0 in zip(obs, boxes):
                if grew(b0, world_box(o)):
                    self.grown.append(o.name)
                self.chunks.add(area_of(o))

    def check(self, fail, dg):
        for n in self.objects:
            o = bpy.data.objects[n]
            me = o.data
            if me.get(P.R12_TAG) != "regions":
                fail.add("banner: %s's cloth was not redone" % n)
                continue
            if len(me.get("props_weights", [])) != len(me.vertices):
                fail.add("banner: %s: %d weights for %d vertices" % (n, len(me.get("props_weights", [])),
                                                                     len(me.vertices)))
            vg = o.vertex_groups.get("flutter")
            if vg is not None:
                nw = sum(1 for v in me.vertices if any(g.group == vg.index for g in v.groups))
                want = sum(1 for w in me["props_weights"] if w > 0)
                if nw != want:
                    fail.add("banner: %s: %d vertices in 'flutter', want %d" % (n, nw, want))


class Slips(Part):
    """#20: the jade bamboo-slip scroll's script (1.5 mm in front of each slip) is cut into the slips' fronts
    (P._slips_cut). (scroll.slips / scroll.slip_caps, the fire tokens, are areas/scroll.py's: lane A.)"""
    name, item = "slips", "#20"

    def plan(self, fail):
        self.pairs = []
        for o in bpy.data.objects:
            if o.type != 'MESH' or not o.name.endswith(".slips") or o.parent is None:
                continue
            base = o.name[:-len(".slips")]
            sc_ = bpy.data.objects.get(base + ".script")
            if sc_ is None or bpy.data.objects.get(base + ".cords") is None:
                continue
            self.objects += [o.name, sc_.name]
            if sc_.data.get(P.R12_TAG) == "cut":
                self.done.append(o.name)
                continue
            self.pairs.append((o, sc_))
            self.todo.append(o.name)
        log("slips: %d slip scrolls, %d to cut" % (len(self.objects) // 2, len(self.todo)))
        return bool(self.todo)

    def apply(self):
        for sl, sc_ in self.pairs:
            n0 = len(sc_.data.polygons)
            P._slips_cut(sl.data, sc_.data)
            self.chunks.add(area_of(sl))
            log("slips: %s: script %d faces -> %d in the slips' planes" % (sl.name, n0, len(sc_.data.polygons)))

    def check(self, fail, dg):
        for n in self.objects[1::2]:
            if bpy.data.objects[n].data.get(P.R12_TAG) != "cut":
                fail.add("slips: %s not cut" % n)


class PropsProtoPart(Part):
    """Rebuild props prototypes (collections matching RX): params(pc) -> (builder(pc, ...), args) or None; the file's
    parts must equal the old build; changed parts get the new build's meshes."""
    RX = None

    def plan(self, fail):
        self.jobs = []
        for pcn in protos_matching(self.RX):
            pc = bpy.data.collections[pcn]
            have = {part_of(o.name): o for o in pc.all_objects if o.type == 'MESH'}
            prm = self.params(pc)
            if prm is None:
                fail.add("%s: %s: unknown parameters" % (self.name, pcn))
                continue
            fn, args = prm
            colN, new = build_props_proto(fn, *args)
            st = "new" if self.match(have, new) else None
            if st is None:
                colO, old = build_props_proto(fn, *args, old=True)
                st = "old" if self.match(have, old) else None
                free_temp(colO)
            if st is None:
                fail.add("%s: %s is neither the old nor the new build" % (self.name, pcn))
                free_temp(colN)
                continue
            self.protos.append(pcn)
            if st == "new":
                self.done.append(pcn)
                free_temp(colN)
                continue
            self.todo.append(pcn)
            self.jobs.append((have, colN, new))
        log("%s: %d prototypes, %d to rebuild, %d new already" % (self.name, len(self.protos), len(self.todo),
                                                                  len(self.done)))
        return bool(self.todo)

    def match(self, have, built):
        b = {k: o for k, o in built.items() if o.type == 'MESH'}
        return sorted(have) == sorted(b) and all(same_geo(have[k].data, b[k].data) for k in have)

    def apply(self):
        for have, col, new in self.jobs:
            for k, o in have.items():
                nm = new[k].data
                if same_geo(o.data, nm, 0.0):
                    continue
                b0 = local_box(o.data)
                swap_mesh([o], nm)
                if grew(b0, local_box(o.data)):
                    self.grown.append(o.name)
                log("%s: %s rebuilt (%d faces)" % (self.name, o.name, len(o.data.polygons)))
            free_temp(col)

    def check(self, fail, dg):
        pass


class Books(PropsProtoPart):
    """#17: each book is one box: covers, slip, ink marks and stitching are regions of its faces (P.BOOKS_SOLID). The
    1.5 mm cover boxes, the 0.4-0.6 mm slips and the 1 mm stitches lay 1-8 mm from the page block's faces at the
    library's 5.5x scale."""
    name, item = "books", "#17"
    RX = r"^props\.books\.\d+\.\d+\.v\d+$"

    def params(self, pc):
        n, seed = re.match(r"^props\.books\.(\d+)\.(\d+)\.v\d+$", pc.name).groups()
        return P._build_books, (int(n), int(seed))


class Anvil(PropsProtoPart):
    """#31: the anvil's stump has no top cap and its end-grain disc is one-sided on the stump's rim
    (P.ANVIL_OPEN_STUMP): the cap and a two-sided disc lay in one plane."""
    name, item = "anvil", "#31"
    RX = r"^props\.anvil\.[^.]+\.v\d+$"

    def params(self, pc):
        kb = re.match(r"^props\.anvil\.([^.]+)\.v\d+$", pc.name).group(1)
        for k in range(-8, 9):
            b = math.sqrt(2.0) ** k
            if P._k(b) == kb:
                return P._build_anvil, (b,)
        return None


class Lantern(PropsProtoPart):
    """#16: the stone lantern's chamber (walls, corner posts, relief windows, cap) is one solid (P.LANTERN_UNION): its
    wall boxes crossed at the corners and the relief windows' frame bars overlapped at 0 mm and stood 5-15 mm over
    the faces under them."""
    name, item = "lantern", "#16"
    RX = r"^props\.stone_lantern\.[^.]+\.[^.]+\.[01]\.v\d+$"
    SCOPE = r"stone_lantern\.chamber"
    LEFT = 0.4             # the bevel after the union leaves slivers of 1-2 cm2 a lantern where the frame bars met

    def params(self, pc):
        kb, _mn, lit = re.match(r"^props\.stone_lantern\.([^.]+)\.([^.]+)\.([01])\.v\d+$", pc.name).groups()
        ch = [o for o in pc.all_objects if o.type == 'MESH' and part_of(o.name) == "props.stone_lantern.chamber"]
        if not ch:
            return None
        for k in range(-8, 9):
            b = 2.4 * math.sqrt(2.0) ** k
            if P._k(b) == kb:
                return P._build_stone_lantern, (b, _mat_of(ch[0].data), lit == "1")
        return None


class Lion(PropsProtoPart):
    """gate.lion (#43 group): the guardian lion's body, mane curls, eyes, ball and ribbons are one solid
    (P.LION_UNION): curls and ribbons lay 1-4 mm off the body's surface."""
    name, item = "lion", "#43"
    RX = r"^props\.lion\.[^.]+\.[01]\..+\.v\d+$"

    def params(self, pc):
        kb, fem = re.match(r"^props\.lion\.([^.]+)\.([01])\..+\.v\d+$", pc.name).groups()
        have = {part_of(o.name): o for o in pc.all_objects if o.type == 'MESH'}
        if "props.lion.body" not in have or "props.lion.plinth" not in have:
            return None
        for k in range(-8, 9):
            b = math.sqrt(2.0) ** k
            if P._k(b) == kb:
                return P._build_lion, (b, fem == "1", _mat_of(have["props.lion.body"].data),
                                       _mat_of(have["props.lion.plinth"].data))
        return None


class Ding(Part):
    """#43: the ding's molten (or ash) surface loses the flat cap under it (P.DING_MOLTEN_CAP): it lay 3-4 mm under the
    surface's rim."""
    name, item = "ding", "#43"

    def plan(self, fail):
        self.jobs = []
        for pcn in protos_matching(r"^props\.ding[34]\."):
            for o in bpy.data.collections[pcn].all_objects:
                if o.type != 'MESH' or part_of(o.name) not in ("props.ding.molten", "props.ding.ash"):
                    continue
                self.protos.append(pcn)
                caps = [p.index for p in o.data.polygons if len(p.vertices) >= 24 and p.normal.z < -0.999]
                if not caps:
                    self.done.append(pcn)
                elif len(caps) == 1:
                    self.jobs.append((o, caps[0]))
                    self.todo.append(pcn)
                else:
                    fail.add("ding: %s has %d flat caps" % (o.name, len(caps)))
        log("ding: %d surfaces, %d caps to remove" % (len(self.protos), len(self.todo)))
        return bool(self.todo)

    def apply(self):
        for o, fi in self.jobs:
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[bm.faces[fi]], context='FACES_ONLY')
            bm.to_mesh(o.data)
            bm.free()
            o.data.update()
            log("ding: %s: cap removed" % o.name)

    def check(self, fail, dg):
        for pcn in self.protos:
            for o in bpy.data.collections[pcn].all_objects:
                if o.type == 'MESH' and part_of(o.name) in ("props.ding.molten", "props.ding.ash"):
                    if any(len(p.vertices) >= 24 and p.normal.z < -0.999 for p in o.data.polygons):
                        fail.add("ding: %s still has its cap" % o.name)


class HandScroll(Part):
    """#36: the open hand scroll's text (2 mm in front of the paper) and seal (a 2 mm box) are cut into the paper, on its
    S-wave (P._scroll_cut)."""
    name, item = "scroll", "#36"

    def plan(self, fail):
        for pcn in protos_matching(r"^props\.scroll\.[^.]+\.1\.\d\.\d\.v\d+$"):
            parts = {part_of(o.name): o for o in bpy.data.collections[pcn].all_objects if o.type == 'MESH'}
            if not all(k in parts for k in ("props.scroll.paper", "props.scroll.text", "props.scroll.seal")):
                fail.add("scroll: %s lacks paper / text / seal" % pcn)
                continue
            self.protos.append(pcn)
            (self.done if parts["props.scroll.text"].data.get(P.R12_TAG) == "cut" else self.todo).append(pcn)
        log("scroll: %d open hand scrolls, %d to cut" % (len(self.protos), len(self.todo)))
        return bool(self.todo)

    def apply(self):
        for pcn in self.todo:
            parts = {part_of(o.name): o for o in bpy.data.collections[pcn].all_objects if o.type == 'MESH'}
            P._scroll_cut(parts["props.scroll.paper"].data, parts["props.scroll.text"].data,
                          parts["props.scroll.seal"].data)
            log("scroll: %s cut: text %d triangles, seal %d" % (pcn, len(parts["props.scroll.text"].data.polygons),
                                                               len(parts["props.scroll.seal"].data.polygons)))

    def check(self, fail, dg):
        for pcn in self.protos:
            parts = {part_of(o.name): o for o in bpy.data.collections[pcn].all_objects if o.type == 'MESH'}
            if parts["props.scroll.text"].data.get(P.R12_TAG) != "cut":
                fail.add("scroll: %s not cut" % pcn)


def roof_roots():
    """Roof roots (A.roof: custom prop arch_kind) with their '.ridges', '.soffit', '.bargeboard', '.studs' children."""
    out = []
    for o in bpy.data.objects:
        if o.type == 'EMPTY' and "arch_kind" in o and "arch_eave_z" in o:
            kids = {c.name[len(o.name) + 1:]: c for c in o.children if c.name.startswith(o.name + ".")}
            out.append((o, kids))
    return sorted(out, key=lambda r: r[0].name)


class Roof(Part):
    """#19, #34: every roof's ridge keels (but a pyramid's, A.KEEL_KEEP) stop at least 4 cm over its soffit
    (A._clear_keels: gable rakes and hips ran their buried keels within mm of the soffit's underside or through it),
    and every bargeboard set (with its studs) moves 2 cm in toward the roof's middle (A.BARGE_IN: the board's inner
    face lay 1 cm inside the tiles' rake closure) and is joined into one surface (A.GABLE_UNION: the two boards of a
    gable overlapped under the apex)."""
    name, item = "roof", "#19 #34"
    ABS = 0.3              # the hips of pyramid roofs (pagoda tops, rest pavilions; A.KEEL_KEEP) keep their ridge
                           # faces near the soffit by the corner: 0.03-0.25 m2 a roof, as before

    @staticmethod
    def SCOPE(a, b):       # keel against soffit, bargeboard against tiles / ridges / bargeboard (its own fixes)
        ka = re.search(r"\.(ridges|soffit|tiles|bargeboard)(\.\d{3})?$", a)
        kb = re.search(r"\.(ridges|soffit|tiles|bargeboard)(\.\d{3})?$", b)
        if ka is None or kb is None:
            return False
        k = {ka.group(1), kb.group(1)}
        return k == {"ridges", "soffit"} or ("bargeboard" in k and k <= {"bargeboard", "tiles", "ridges"})

    def plan(self, fail):
        self.ridges, self.boards = [], []
        for root, kids in roof_roots():
            rg, so = kids.get("ridges"), kids.get("soffit")
            if rg is not None and so is not None:
                self.objects.append(rg.name)
                if rg.data.get(A.R12_TAG) == "keels":
                    self.done.append(rg.name)
                else:
                    self.ridges.append((rg, so, root.get("arch_kind") not in A.KEEL_KEEP))
                    self.todo.append(rg.name)
            bb = kids.get("bargeboard")
            if bb is not None:
                self.objects.append(bb.name)
                if bb.data.get(A.R12_TAG) == "union":
                    self.done.append(bb.name)
                    continue
                st = kids.get("studs")
                if st is not None and (st.type != 'MESH' or st.data.attributes.get("arch_xf") is None):
                    fail.add("roof: %s is not a stud point cloud" % st.name)
                    continue
                c = coords(bb.data)
                if (np.abs(c[:, 0]) < 0.05).any():
                    fail.add("roof: %s has board vertices near the roof's middle" % bb.name)
                    continue
                self.boards.append((bb, st))
                self.todo.append(bb.name)
        log("roof: %d roofs: %d ridge sets to clear, %d bargeboard sets to move and join; %d done already" % (
            len(roof_roots()), len(self.ridges), len(self.boards), len(self.done)))
        return bool(self.todo)

    def apply(self):
        moved = 0
        for rg, so, lift in self.ridges:
            n = A._clear_keels(rg.data, so.data) if lift else 0
            rg.data[A.R12_TAG] = "keels"
            moved += n
            if n:
                self.chunks.add(area_of(rg))
        log("roof: lifted %d keel vertices to %.0f cm over their soffits" % (moved, 100 * A.ROOF_KEEL_CLEAR))
        for bb, st in self.boards:
            c = coords(bb.data)
            c[:, 0] -= np.copysign(A.BARGE_IN, c[:, 0])
            bb.data.vertices.foreach_set("co", c.ravel())
            bb.data.update()
            n0 = len(bb.data.polygons)
            A._self_union(bb.data)
            self.chunks.add(area_of(bb))
            if st is not None:
                me = st.data
                sc_ = coords(me)
                sc_[:, 0] -= np.copysign(A.BARGE_IN, sc_[:, 0])
                me.vertices.foreach_set("co", sc_.ravel())
                at = me.attributes["arch_xf"]
                xf = np.empty(len(at.data) * 16)
                at.data.foreach_get("value", xf)
                xf = xf.reshape(-1, 16)
                xf[:, 12] -= np.copysign(A.BARGE_IN, xf[:, 12])
                at.data.foreach_set("value", xf.ravel())
                me.update()
            log("roof: %s moved %.0f cm in and joined (%d -> %d faces)%s" % (
                bb.name, 100 * A.BARGE_IN, n0, len(bb.data.polygons), ", studs with it" if st is not None else ""))

    def check(self, fail, dg):
        for root, kids in roof_roots():
            rg, so = kids.get("ridges"), kids.get("soffit")
            if rg is not None and so is not None and root.get("arch_kind") not in A.KEEL_KEEP:
                if A._clear_keels(rg.data.copy(), so.data) != 0:
                    fail.add("roof: %s still has keel vertices under %.0f cm over the soffit" % (
                        rg.name, 100 * A.ROOF_KEEL_CLEAR))
            bb = kids.get("bargeboard")
            if bb is not None and bb.data.get(A.R12_TAG) != "union":
                fail.add("roof: %s not joined" % bb.name)
        for me in [m for m in bpy.data.meshes if m.users == 0 and ".ridges" in m.name]:
            bpy.data.meshes.remove(me)


class Plinth(Part):
    """#21 (foot gates) and every paifang: the marble plinth round each column is 2.64 x the column radius + 5 cm (was
    2.6 x: the column's own base plinth, 2.64 x, stood 13 mm out of it on all four sides; now 2.5 cm inside)."""
    name, item = "plinth", "#21"

    def plan(self, fail):
        self.jobs = []
        for o in bpy.data.objects:
            if o.type != 'MESH' or o.parent is None or not re.match(r"^%s\.plinth(\.\d{3})?$" % re.escape(o.parent.name),
                                                                    o.name):
                continue
            if "arch_center_opening" not in o.parent:
                continue
            c = coords(o.data)
            if len(c) != 8:
                fail.add("plinth: %s is not a box" % o.name)
                continue
            self.objects.append(o.name)
            if o.data.get(A.R12_TAG) == "plinth":
                self.done.append(o.name)
                continue
            self.jobs.append(o)
            self.todo.append(o.name)
        log("plinth: %d paifang plinths, %d to widen" % (len(self.objects), len(self.todo)))
        return bool(self.todo)

    def apply(self):
        for o in self.jobs:
            c = coords(o.data)
            mid = 0.5 * (c.min(0) + c.max(0))
            side0 = float(c[:, 0].max() - c[:, 0].min())
            cr = side0 / OLD_ARCH["PAIFANG_PLINTH"]          # the column radius the old plinth was made for
            k = (A.PAIFANG_PLINTH * cr + 2.0 * A.PAIFANG_PLINTH_PAD) / side0
            c[:, :2] = mid[:2] + (c[:, :2] - mid[:2]) * k
            o.data.vertices.foreach_set("co", c.ravel())
            o.data[A.R12_TAG] = "plinth"
            o.data.update()
            self.chunks.add(area_of(o))

    def check(self, fail, dg):
        pass


class Walls(Part):
    """The plaster walls of halls (and towers) and of pagoda storeys joined into one solid (A.WALLS_UNION): the boxes
    of two sides crossed at every corner with their tops and bottoms in one plane, the upper and lower courses met face
    to face."""
    name, item = "walls", "#13"

    @staticmethod
    def SCOPE(a, b):       # the wall boxes against each other (their contact with columns and frames is unchanged)
        return ".walls" in a and ".walls" in b

    def plan(self, fail):
        for o in bpy.data.objects:
            if o.type != 'MESH' or o.parent is None or not re.match(r"^%s\.walls(\.\d{3})?$" % re.escape(o.parent.name),
                                                                    o.name):
                continue
            if "arch_height" not in o.parent:            # A.hall / A.pagoda roots (their walls: A._wall_box boxes)
                continue
            self.objects.append(o.name)
            if o.data.get(A.R12_TAG) == "union":
                self.done.append(o.name)
                continue
            if len(o.data.vertices) % 8 or len(o.data.polygons) != len(o.data.vertices) // 8 * 6:
                fail.add("walls: %s is not a set of wall boxes" % o.name)
                continue
            self.todo.append(o.name)
        log("walls: %d wall sets, %d to join" % (len(self.objects), len(self.todo)))
        return bool(self.todo)

    def apply(self):
        for n in self.todo:
            o = bpy.data.objects[n]
            n0 = len(o.data.polygons)
            A._self_union(o.data)
            self.chunks.add(area_of(o))
            log("walls: %s joined: %d -> %d faces" % (n, n0, len(o.data.polygons)))

    def check(self, fail, dg):
        for n in self.objects:
            if bpy.data.objects[n].data.get(A.R12_TAG) != "union":
                fail.add("walls: %s not joined" % n)


class Bench(Part):
    """Corridor bench rails (arch.p.bench): seat board, back board and balusters joined into one surface
    (A.BENCH_UNION: the boards' end faces lay in one plane)."""
    name, item = "bench", "#21"

    def plan(self, fail):
        for pcn in protos_matching(r"^arch\.p\.bench\.\d+\.[A-Za-z0-9_]+$"):
            obs = [o for o in bpy.data.collections[pcn].all_objects if o.type == 'MESH']
            if len(obs) != 1:
                fail.add("bench: %s is not one object" % pcn)
                continue
            self.protos.append(pcn)
            (self.done if obs[0].data.get(A.R12_TAG) == "union" else self.todo).append(pcn)
        log("bench: %d bench prototypes, %d to join" % (len(self.protos), len(self.todo)))
        return bool(self.todo)

    def apply(self):
        for pcn in self.todo:
            o = [o for o in bpy.data.collections[pcn].all_objects if o.type == 'MESH'][0]
            A._self_union(o.data)

    def check(self, fail, dg):
        for pcn in self.protos:
            o = [o for o in bpy.data.collections[pcn].all_objects if o.type == 'MESH'][0]
            if o.data.get(A.R12_TAG) != "union":
                fail.add("bench: %s not joined" % pcn)


def _boxes(me):
    """[(p0, p1, half thickness, z0, z1)] of a mesh made of A._wall_box boxes (8 vertices each, in order)."""
    c = coords(me)
    out = []
    for k in range(len(c) // 8):
        b = c[8 * k:8 * k + 8]
        v0, v1, v2, v3 = (Vector(b[i][:2]) for i in range(4))
        out.append(((v0 + v3) * 0.5, (v1 + v2) * 0.5, (v3 - v0).length * 0.5, float(b[0, 2]), float(b[4, 2])))
    return out


class CornerRoof(Part):
    """#19 (corridors): each corridor's corner pyramid roof sits 25 cm over the post tops (A.CORRIDOR_CORNER_LIFT, was
    12 cm): its soffit and tiles crossed the two segment roofs' at a shallow angle, within 5 mm of them on a band about
    1 m2 a corner. The roof (with everything on it) moves up 13 cm; nothing else changes."""
    name, item = "corner", "#19"

    @staticmethod
    def SCOPE(a, b):       # the corner roof against the rest (the segment roofs)
        return ("corner_roof" in a) != ("corner_roof" in b)

    def plan(self, fail):
        self.jobs = []
        for root in sorted(corridor_floors(), key=lambda r: r.name):
            beams = bpy.data.objects.get(root.name + ".beams")
            zt = float(coords(beams.data)[:, 2].max())          # the post tops (the side beams' tops)
            for o in sorted(root.children, key=lambda o: o.name):
                if not re.match(r"^%s\.corner_roof(\.\d{3})?$" % re.escape(root.name), o.name):
                    continue
                self.objects.append(o.name)
                lift = o.location.z - zt
                if abs(lift - A.CORRIDOR_CORNER_LIFT) < 1e-4:
                    self.done.append(o.name)
                elif abs(lift - OLD_ARCH["CORRIDOR_CORNER_LIFT"]) < 1e-4:
                    self.todo.append(o.name)
                    self.jobs.append(o)
                else:
                    fail.add("corner: %s sits %.4f m over the post tops (want %.2f or %.2f)" % (
                        o.name, lift, OLD_ARCH["CORRIDOR_CORNER_LIFT"], A.CORRIDOR_CORNER_LIFT))
        log("corner: %d corridor corner roofs, %d to raise" % (len(self.objects), len(self.todo)))
        return bool(self.todo)

    def apply(self):
        dz = A.CORRIDOR_CORNER_LIFT - OLD_ARCH["CORRIDOR_CORNER_LIFT"]
        for o in self.jobs:
            o.location.z += dz
            self.grown.append(o.name)                # it moved: its chunk's export records change
            self.chunks.add(area_of(o))
            log("corner: %s raised %.2f m" % (o.name, dz))

    def check(self, fail, dg):
        pass


class Crossing(Part):
    """Corridor bench rails (steles and mission corridors): at an inner corner the side lines of the two segments run
    past each other and the last bench of one and the first of the next crossed, their seat boards in one plane over a
    36 x 36 cm square. The later one of each crossing pair now sits 2.5 cm lower (A.CORRIDOR_BENCH_DROP,
    A.benches_crossed)."""
    name, item = "crossing", "#21"

    @staticmethod
    def SCOPE(a, b):       # bench against bench
        return ".bench" in a and ".bench" in b

    def plan(self, fail):
        self.jobs = []
        floors = corridor_floors()
        for root in sorted(floors, key=lambda r: r.name):
            top = max(float(coords(f.data)[:, 2].max()) for f in floors[root])
            bs = []
            for o in root.children:
                m = re.match(r"^%s\.bench(\.(\d{3}))?$" % re.escape(root.name), o.name)
                if m and o.instance_type == 'COLLECTION':
                    bs.append((int(m.group(2) or 0), o))
            bs = [o for _k, o in sorted(bs, key=lambda kv: kv[0])]
            crossed = A.benches_crossed(bs)
            for o in bs:
                dz = o.location.z - top
                want_new = -A.CORRIDOR_BENCH_DROP if o in crossed else 0.0
                if abs(dz - want_new) < 1e-4:
                    if o in crossed:
                        self.objects.append(o.name)
                        self.done.append(o.name)
                elif o in crossed and abs(dz) < 1e-4:
                    self.objects.append(o.name)
                    self.todo.append(o.name)
                    self.jobs.append(o)
                else:
                    fail.add("crossing: %s sits %.4f m off the floor top" % (o.name, dz))
        log("crossing: %d crossing corridor benches, %d to lower" % (len(self.objects), len(self.todo)))
        return bool(self.todo)

    def apply(self):
        for o in self.jobs:
            o.location.z -= A.CORRIDOR_BENCH_DROP
            self.grown.append(o.name)                # it moved: its chunk's export records change
            self.chunks.add(area_of(o))
            log("crossing: %s lowered %.3f m" % (o.name, A.CORRIDOR_BENCH_DROP))

    def check(self, fail, dg):
        pass


class Frieze(Part):
    """#12: the frieze walls over the skirt roofs of double-eave halls and towers are made thinner, so that both their
    faces stand at least 2.5 cm from every vertical face of the skirt's top ridge, which runs along the wall's foot,
    wider than it, stepped and tapering toward the corners (A.frieze_clear_half, measured on the ridge mesh; the faces
    lay 0-6 mm from the wall's), and the halls' frieze windows sit in openings in the wall, in its middle (they hung
    2 cm in front of it, their frames' backs 5 mm off it). The walls are joined into one solid. Runs after the roof
    part, which may trim the ridge keels."""
    name, item = "frieze", "#12"

    def plan(self, fail):
        self.jobs = []
        for o in bpy.data.objects:
            if o.type != 'MESH' or o.parent is None:
                continue
            root = o.parent
            if o.name != root.name + ".frieze":
                continue
            skirt = bpy.data.objects.get(root.name + ".skirt")
            if skirt is None:
                continue
            self.objects.append(o.name)
            if o.data.get(A.R12_TAG) == "frieze":
                self.done.append(o.name)
                continue
            boxes = _boxes(o.data)
            if len(boxes) < 3 or len(o.data.vertices) != 8 * len(boxes):
                fail.add("frieze: %s is not a ring of wall boxes" % o.name)
                continue
            half0 = boxes[0][2]
            if A._ridges_of(skirt, root)[0] is None:
                fail.add("frieze: %s has no ridges" % skirt.name)
                continue
            wins = []
            if len(boxes) == 4:
                for w in bpy.data.objects:
                    if w.parent == root and re.match(r"^%s\.frieze_win(\.\d{3})?$" % re.escape(root.name), w.name):
                        pc = w.instance_collection
                        prm = Lattice().params(pc)[1]
                        side = -1 if abs(w.rotation_euler.z) < 1e-6 else 1
                        wins.append((w, side, w.location.x, prm[0], prm[1], w.location.z))
            # the wall's thickness is worked out in apply(), after the roof part trimmed the ridge keels
            self.jobs.append((o, root, skirt, boxes, wins))
            self.todo.append(o.name)
            log("frieze: %s: wall %.3f thick, %d windows" % (o.name, 2 * half0, len(wins)))
        log("frieze: %d frieze walls, %d to redo" % (len(self.objects), len(self.todo)))
        return bool(self.todo)

    def apply(self):
        for o, root, skirt, boxes, wins in self.jobs:
            half0 = boxes[0][2]
            z0, z1 = boxes[0][3], boxes[0][4]
            corners = [b[0] for b in boxes]
            rme, rM = A._ridges_of(skirt, root)
            half = A.frieze_clear_half(half0, rme, rM, [(c.x, c.y) for c in corners], z0, z1)
            if wins:
                quad = [(c.x, c.y) for c in corners]
                fv, ff, fm = A.hall_frieze_geo(quad, half, z0, z1, [w[1:] for w in wins], holes=True)
                ys = (quad[0][1], quad[2][1])
            else:
                fv, ff, fm = [], [], []
                for a, b, _h, _z0, _z1 in boxes:
                    A._wall_box(fv, ff, fm, a, b, 2.0 * half, z0, z1, 0)
                ys = None
            log("frieze: %s: wall %.3f thick (was %.3f)" % (o.name, 2 * half, 2 * half0))
            me = bpy.data.meshes.new("_r12_frieze")
            me.from_pydata([tuple(v) for v in fv], [], [tuple(f) for f in ff])
            me.validate(verbose=False)
            for m in o.data.materials:
                me.materials.append(m)
            U.shade_flat(me)
            me.update()
            A._self_union(me)
            me[A.R12_TAG] = "frieze"
            b0 = world_box(o)
            swap_mesh([o], me)
            if grew(b0, world_box(o)):
                self.grown.append(o.name)
            self.chunks.add(area_of(o))
            for w, side, x, ww, wh, z in wins:
                w.location.y = ys[0] if side < 0 else ys[1]
                self.chunks.add(area_of(w))
            log("frieze: %s rebuilt (%d faces)%s" % (o.name, len(o.data.polygons), "; %d windows set in it" % len(wins)
                                                    if wins else ""))

    def check(self, fail, dg):
        for n in self.objects:
            if bpy.data.objects[n].data.get(A.R12_TAG) != "frieze":
                fail.add("frieze: %s not redone" % n)


# ============================================================================================ main

PART_CLASSES = [Rune, Corridor, Inlays, Stele, Band, Dougong, Roof, CornerRoof, Crossing, Frieze, Walls, Lattice,
                Column, Panel, Seat, Chiwen, Bench, Plinth, Banner, Slips, Books, Anvil, Lantern, Lion, Ding,
                HandScroll]


def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    names = [c.name for c in PART_CLASSES]
    opt = dict(DRY_RUN=False, SCAN=True, PARTS=names)
    for a in argv:
        k, eq, v = a.partition("=")
        if k in ("DRY_RUN", "SCAN") and eq:
            opt[k] = v.strip().lower() not in ("", "0", "false", "no")
        elif k == "PARTS" and eq:
            want = [p.strip() for p in v.split(",") if p.strip()]
            bad = [p for p in want if p not in names]
            if bad:
                raise SystemExit("patch_r12_libs: unknown parts %s (known: %s)" % (bad, ",".join(names)))
            opt["PARTS"] = want
        else:
            raise SystemExit("patch_r12_libs: unknown option %r (DRY_RUN=1, SCAN=0, PARTS=%s)" % (a, ",".join(names)))
    return opt


def _scoped(b, res, scope):
    """Band totals of the pairs with a label matching ``scope`` (all pairs when None), leaving out the thickness of a
    piece's own slender parts (back-to-back faces of one piece 5-20 mm apart: a lattice bar, a petal, a fin; such a
    part is under a pixel wherever its two faces could swap in a 24-bit depth buffer)."""
    res = {k: v for k, v in res.items() if not (k[2] == "thin" and k[0] == k[1] and k[3] >= 1)}
    if callable(scope):
        res = {k: v for k, v in res.items() if scope(k[0], k[1])}
    elif scope is not None:
        res = {k: v for k, v in res.items() if re.search(scope, k[0]) or re.search(scope, k[1])}
    b = [0.0, 0.0, 0.0]
    for k, v in res.items():
        b[k[3]] += v[0]
    return b, res


def scan_group(root, dg):
    """Coplanar overlap of an Empty's whole family (its meshes, its children's, and what they instance) against
    itself and everything rendered around it."""
    names = set()
    stack = [root]
    while stack:
        o = stack.pop()
        names.add(o.name)
        stack.extend(o.children)
    boxes = []
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type != 'MESH':
            continue
        own = inst.parent.original.name if (inst.is_instance and inst.parent) else ob.original.name
        if own not in names:
            continue
        M = np.array(inst.matrix_world)
        bb = np.array([tuple(c) for c in ob.bound_box]) @ M[:3, :3].T + M[:3, 3]
        boxes.append((bb.min(0), bb.max(0)))
    if not boxes:
        return [0.0, 0.0, 0.0], {}
    lo = np.min([b[0] for b in boxes], axis=0)
    hi = np.max([b[1] for b in boxes], axis=0)
    T, lab = gather_world(dg, [(lo, hi)], pad=0.03)
    if not len(T):
        return [0.0, 0.0, 0.0], {}
    S = Scene3(T, lab)
    subj = np.array([l.split(">")[0] in names for l in lab])
    res, bands = scan(S, subj, step=0.03, max_samples=40000)
    return bands, res


def scan_part(p, dg, inst, cnt):
    """{subject: [m2 <=5, 5-12, 12-20 mm]} (prototypes: per instance x instances), and the top pairs."""
    out, pairs = {}, {}
    for pcn in p.protos:
        pc = bpy.data.collections.get(pcn)
        if pc is None:
            continue
        b, res = _scoped(*scan_proto(pc, dg, inst), p.SCOPE)
        k = max(1, cnt.get(pcn, 0) // max(1, len([o for o in pc.all_objects if o.type == 'MESH'])))
        out[pcn] = [x * k for x in b]
        pairs[pcn] = summarize(res, 3)
    for n in p.objects:
        o = bpy.data.objects.get(n)
        if o is None:
            continue
        if o.type == 'MESH':
            b, res = _scoped(*scan_object(o, dg), p.SCOPE)
        elif o.type == 'EMPTY':
            b, res = _scoped(*scan_group(o, dg), p.SCOPE)
        else:
            continue
        out[n] = list(b)
        pairs[n] = summarize(res, 3)
    return out, pairs


def digest(parts):
    import hashlib
    h = hashlib.md5()
    seen = set()
    for p in parts:
        for name, me in sorted(p.digest_meshes(), key=lambda r: r[0]):
            if name in seen:
                continue
            seen.add(name)
            mesh_digest(h, me, name)
    for p in parts:
        if p.name == "rune":
            for n in p.objects:
                o = bpy.data.objects[n]
                h.update(np.round(np.array(o.matrix_world), 6).tobytes())
    return h.hexdigest()


def main():
    opt = options()
    t0 = time.time()
    fail = Fail()
    had_eval = bpy.data.scenes.get(A._EVAL_SCENE) is not None
    n_obj0 = len(bpy.data.objects)
    parts = [c() for c in PART_CLASSES if c.name in opt["PARTS"]]
    log("parts:", ", ".join("%s (%s)" % (p.name, p.item) for p in parts))
    todo = {}
    for p in parts:
        t1 = time.time()
        todo[p.name] = p.plan(fail)
        log("%s: planned in %.1f s" % (p.name, time.time() - t1))
    if fail:
        log("NOT SAVED: the file is not in a state this patch knows (%d problems)" % len(fail))
        raise SystemExit(1)
    dg = bpy.context.evaluated_depsgraph_get()
    inst = instances(dg)
    owners, cnt = proto_owners(dg)
    before = {}
    if opt["SCAN"]:
        for p in parts:
            if todo[p.name]:
                t1 = time.time()
                before[p.name] = scan_part(p, dg, inst, cnt)
                log("%s: scanned before in %.0f s" % (p.name, time.time() - t1))
    for p in parts:
        if todo[p.name]:
            t1 = time.time()
            p.apply()
            log("%s: applied in %.1f s" % (p.name, time.time() - t1))
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    for p in parts:
        t1 = time.time()
        p.check(fail, dg)
        log("%s: checked in %.1f s" % (p.name, time.time() - t1))
    totals = {}
    if opt["SCAN"]:
        inst = instances(dg)
        for p in parts:
            if not todo[p.name]:
                continue
            t1 = time.time()
            after, pairs = scan_part(p, dg, inst, cnt)
            b0, a0 = before[p.name][0], after
            sb = [sum(v[i] for v in b0.values()) for i in range(3)]
            sa = [sum(v[i] for v in a0.values()) for i in range(3)]
            totals[p.name] = (sb, sa)
            log("%s (%s): visible overlap of what it touched and what stands round it, <=5 / 5-12 / 12-20 mm: "
                "%s m2 -> %s m2 (%.0f s)" % (p.name, p.item, fmt(sb), fmt(sa), time.time() - t1))
            for k in sorted(a0, key=lambda k: -sum(b0.get(k, [0, 0, 0]))):
                bb, aa = b0.get(k, [0.0, 0.0, 0.0]), a0[k]
                if sum(bb) + sum(aa) >= 0.01:
                    log("    %s: %s -> %s%s" % (k, fmt(bb), fmt(aa), "" if sum(aa) < 0.05 else "  (left: %s)" %
                                                  "; ".join(pairs.get(k, [])[:2])))
                # the fix must not leave the old overlap, nor add any
                if aa[0] + aa[1] > max(p.ABS, p.LEFT * (bb[0] + bb[1])) or sum(aa) > sum(bb) + max(0.1, p.ABS):
                    fail.add("%s: %s still overlaps: %s m2 (was %s)" % (p.name, k, fmt(aa), fmt(bb)))
    n_obj1 = len(bpy.data.objects)
    if n_obj1 != n_obj0:
        fail.add("objects %d -> %d: the patch adds or removes none" % (n_obj0, n_obj1))
    # caches
    grown, chunks = [], set()
    for p in parts:
        if not todo[p.name]:
            continue
        grown += p.grown
        chunks |= p.chunks
        for pcn in p.todo:
            if pcn in owners:
                chunks |= owners[pcn]
    chunks = sorted(c for c in chunks if c and c not in ("_protos",))
    if not had_eval and bpy.data.scenes.get(A._EVAL_SCENE) is not None:
        bpy.data.scenes.remove(bpy.data.scenes[A._EVAL_SCENE])
    for me in [m for m in bpy.data.meshes if m.users == 0 and m.name.startswith(("_r12", "_book_tmp"))]:
        bpy.data.meshes.remove(me)
    dig = digest(parts)
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail:
            log("  -", f)
        log("DIGEST", dig)
        raise SystemExit(1)
    if any(todo.values()):
        if grown:
            log("CACHES needs audit: %d object or prototype boxes grew more than %.0f cm (%s%s) - run export_web.py -- "
                "audit --profile full, then chunks,meta, then bake_web.py bakefull for %s and the backdrop, then "
                "tools/sect_pack.py" % (len(grown), BOX_TOL * 100, ", ".join(grown[:12]),
                                        " ..." if len(grown) > 12 else "", ",".join(chunks)))
        else:
            log("CACHES ok: names kept, every box within %.0f cm; re-bake %s and the backdrop, then pack" % (
                BOX_TOL * 100, ",".join(chunks)))
    else:
        log("CACHES ok: nothing changed")
    log("DIGEST", dig)
    if not any(todo.values()):
        log("every part unchanged: not saving (%.0f s)" % (time.time() - t0))
        return
    if opt["DRY_RUN"]:
        log("DRY_RUN: checks passed, not saving (%.0f s)" % (time.time() - t0))
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "(%.0f s)" % (time.time() - t0))


if __name__ == "__main__":
    main()
