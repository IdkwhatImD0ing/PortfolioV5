"""Round 12, lane 'areas': the web flicker fixes in sect/areas/*.py, brought into an existing out/sect_chase.blend so it
matches what a fresh build of the current source makes. Run on the cloud box, on a copy first:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r12_areas.py [-- DRY_RUN=1] [PARTS=a,b] [SCAN=0]

Why (owner, round 11-12): "Some of the stairs still flicker". The web draws every baked face double-sided with a 24-bit
depth buffer (near 0.5 m, far 9000 m): two surfaces g apart fight beyond about sqrt(g * 4.2e6) m (4 mm: 130 m, 2 cm:
290 m, 4 cm: 410 m), and at 0 mm everywhere. Round 12's scan (scratchpad r12/scan.md) listed what is left; this lane
fixes the items built by areas/*.py. Parts (PARTS=..., default all; each is idempotent and says 'unchanged' when the
file has it already):
- inscription  #5  abode.inscription was a text (FONT) object: export_web.gather keeps a text object and its evaluated
                   mesh as two records, so the web drew 洞天福地 twice in one place (55 m2, 0 mm). abode.text_to_mesh
                   converts it in place (same object and name); one record is left
- scroll       #4  the script ring's groove sheet (scroll.ring.groove, 5 mm under the paving) is removed; the dark
                   channel is painted into scroll.terrace.body's own top (scroll.terrace_channel, as the summit's in
                   round 11). The two rings' origins stay on the paving top (scroll.RING_Z): props.rune_ring's band
                   stands on it (lane L's new band; until then they lie in it at 0 mm)
- lawns        #6  library.lawn and mirror.lawn crossed the world terrace's plane at a few degrees, 0-12 mm off it over
                   ~46 m2: every vertex less than LAWN_CLEAR (4 cm) over it now goes LAWN_SINK under it (seat_lawn).
                   The library's lawn-settled props (stone lanterns, peach trees, boulder) are settled again on it
- libpaths     #22 library.path_main / path_west stop at the plaza's edge, path_east starts at the main path's edge and
                   both side paths stop at the study pavilions' step feet (library.trim_path), the depart walk starts
                   on the plaza's edge, flush (library.depart_walk_geom)
- steles       #28 the corridor floors stop at the corner pavilions' platform edges (steles.trim_corridor_floor), the
                   aisle and the rear walks stop at the stele fields' plinth feet (steles.field_foot)
- cave         #29 abode.cave_floor starts at the deck's back edge (abode.DECK_BACK), not 1.6 m out on it
- forge        #30 forge.paving has no top under the arrival and bridgehead landings (forge._paving_bm, _cut_top)
- arena        #38/#16 the bridgehead walk and the rear walk end at their landings' edges, the rear pier starts at its
                   landing's edge and its footing reaches PIER_SINK (65 cm, 5 cm under the landing's); the three stairs
                   off the banner band drop their top tread BAND_STEP_DROP (2 cm) under the band (was 5 mm), the
                   front one stands at FRONT_STEPS_Y (4.5 cm further out: its risers grazed the rim wall), and their
                   blocks reach arena.STEP_SINK (12 cm) under their foot (verify: the grass fell away up to 8 and 10 cm
                   under the front and rear flights near their foot, an open slit along their sides)
- mission      #40/#18 the gallery floors stop at the tower bases' and the terrace's edges (mission.trim_corridor_floor);
                   the role boards' letters, rim line, gold frame and sun / moon stand ROLE_PROUD (4 cm) proud of the
                   jade (were 4-12 mm): the seven prototypes are rebuilt in place (same objects and names)
- gate         #27/#42 both weapons are rebuilt (gate.weapon_mesh): their inlays (blade names, the saber's dragon, the
                   plinth's saying) are carved into their hosts (gate.carve_inlays, exact boolean union); the stair
                   ridge's end caps are flat, its grid is split finer in place (RIDGE_SUB) and no ridge vertex stays
                   between RIDGE_SINK (25 cm) under and RIDGE_REACH (50 cm) over world.range's top
                   (gate.clear_ridge_of_range)
- lotus        #16 the lotus patches (mirror x3, library) float LOTUS_LIFT (4 cm) higher: their pads' rims dipped into
                   the water
- steps        #14 the area steps at the link stairs' ends reach STEP_SINK (12 cm) into the terrace (sink_steps; the
                   library's arrival steps from 15 cm higher): mirror arrival / depart, library arrival / depart, mission
                   depart, formation arrival. The mirror stairs' balustrade drum stones get plinths (mirror.drum_plinths)
- ribbon       #37 the abode's silk ribbon is 2 cm thick with square edges (abode.RIBBON_T, _RIB_X / _RIB_Y); its tails
                   thinned to nothing at their edges, front and back 2-12 mm apart

Checks (any failure stops the patch before saving; DRY_RUN=1 runs everything and never saves):
- every part recognises the file's state (the old build or the new one, piece by piece); unknown states fail;
- coplanar-overlap scan before and after of every touched piece against everything near it (vegetation left out) and
  against itself: parallel faces within SCAN_TOL (5 mm), area split into same-facing (z-fights; 'exposed' when a ray
  from just over the pair escapes) and opposite-facing (contact). The overlaps a part targets must go (TARGET_MAX); no
  touched piece may gain same-facing overlap (NEW_MAX);
- footing ('nothing floating'): the bottoms of the touched pieces and of what stands on them (the steps, their drum
  plinths and drums, the lawn props, the lotus pads) are buried or rest within FLOAT_MAX (2 cm) of what is under them;
- stairs: every touched flight is still walkable: rays down along it land on its treads (risers <= RISER_MAX), the
  foot on the floor beside it, the top on its landing; the sunk ones' treads are unchanged;
- part checks (the scroll channel's material ring, the forge paving's one top surface, the corridor floors meeting
  their hosts edge to edge, the lawn clear of the terrace, the role boards and weapons rebuilt, ...);
- names: no '.001' clash; the object count changes by exactly what the parts remove.
Prints 'PATCH CACHES ok' (names kept, every world box within BOX_TOL) or 'PATCH CACHES needs audit' (with the boxes
that grew and the chunks to re-bake), and 'PATCH DIGEST <md5>' of every touched mesh and transform: equal after a first
and a second run when the patch is idempotent.
Options after "--": DRY_RUN=1, PARTS=a,b,..., SCAN=0 (skip the slow coplanar scans; checks still run).
"""
import hashlib
import math
import os
import re
import sys
import time
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import abode as AB  # noqa: E402
from sect.areas import arena as AR  # noqa: E402
from sect.areas import forge as FG  # noqa: E402
from sect.areas import formation as FO  # noqa: E402
from sect.areas import gate as GT  # noqa: E402
from sect.areas import library as LI  # noqa: E402
from sect.areas import mirror as MI  # noqa: E402
from sect.areas import mission as MS  # noqa: E402
from sect.areas import scroll as SC  # noqa: E402
from sect.areas import steles as ST  # noqa: E402
from sect.lib import arch as A  # noqa: E402
from sect.lib import props as P  # noqa: E402
from sect.lib import util as U  # noqa: E402

PARTS_ALL = ("inscription", "scroll", "lawns", "libpaths", "steles", "cave", "forge", "arena", "mission", "gate",
             "lotus", "steps", "ribbon")
SCAN_TOL = 0.0055          # m: parallel faces within 5 mm (5.5: a 5.0 mm pair counts despite float noise)
SCAN_TOL12 = 0.0125        # m: and the far-only band out to 12 mm (fights beyond ~150-220 m)
SCAN_PAR = 0.985           # |cos| between two faces counted as parallel (~10 deg)
SCAN_STEP = 0.06           # m between samples (coarser on large pieces: at most SCAN_MAX per piece)
SCAN_MAX = 120000
EXPOSE_D = 6.0             # m: an exposure ray that meets nothing this far counts the pair as exposed
TARGET_MAX = 0.05          # m2: what may be left (same-facing) of an overlap a part removes
NEW_MAX = 0.10             # m2: a touched piece may not gain more same-facing overlap than this with any neighbour
                           # (or 15 % of what the pair had: the sampling's noise on large untouched pairs)
FLOAT_MAX = 0.02           # m: air allowed under a touched piece's bottom
RISER_MAX = 0.20           # m: highest step along a touched flight (arena band stairs: 0.152 + 0.02 at the band rim)
BOX_TOL = 0.01             # m: a box within this of its old one keeps the export caches valid
VEG = ("pine", "blossom", "bamboo", "willow", "reed", "fern", "shrub", "grass_", "nature.scatter", "flower", "clover",
       "moss_clump", "vine", "trees.")


def log(*a):
    print("PATCH", *a, flush=True)


def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    dry, parts, scan = False, list(PARTS_ALL), True
    for a in argv:
        k, eq, v = a.partition("=")
        if k == "DRY_RUN" and eq:
            dry = v.strip().lower() not in ("", "0", "false", "no")
        elif k == "SCAN" and eq:
            scan = v.strip().lower() not in ("", "0", "false", "no")
        elif k == "PARTS" and eq:
            parts = [p.strip() for p in v.split(",") if p.strip()]
            bad = [p for p in parts if p not in PARTS_ALL]
            if bad:
                raise SystemExit("patch_r12_areas: unknown parts %s (known: %s)" % (bad, ",".join(PARTS_ALL)))
        else:
            raise SystemExit("patch_r12_areas: unknown option %r (DRY_RUN=1, PARTS=..., SCAN=0)" % a)
    return dry, parts, scan


class Fail(list):
    def add(self, msg):
        log("FAIL", msg)
        self.append(msg)


# ---------------------------------------------------------------------------------------------------- geometry utils

def mesh_tris(me):
    try:
        me.calc_loop_triangles()
    except Exception:
        pass
    nv, nt = len(me.vertices), len(me.loop_triangles)
    if not nt:
        return np.zeros((0, 3, 3))
    co = np.empty(nv * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(nv, 3)
    tv = np.empty(nt * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", tv)
    return co[tv.reshape(nt, 3)]


def owner_of(inst):
    return inst.parent.original.name if inst.is_instance and inst.parent else inst.object.original.name


def hidden(inst):
    o = inst.parent.original if inst.is_instance and inst.parent else inst.object.original
    return bool(o.hide_render)


FX_WORDS = ("smoke", "mist", "cloud_puff", "haze", "heat", "cloud_fog", ".puff")   # export_web's FX_WORDS + the puffs
FX_OWNERS = ("world.cloud_sea", "world.moon", "world.moon_halo", "world.haze", "world.cloud_fog")
_FX = {}


def is_fx(own, ob):
    """True for what the web never draws as geometry (export_web: volumes, cloud puffs (sprites there), sky objects):
    by the owner's name ``own``, or by the materials of ``ob`` (its first mesh seen). Cached per owner (the scans see
    hundreds of thousands of instances)."""
    fx = _FX.get(own)
    if fx is None:
        fx = own in FX_OWNERS or own.startswith("world.cirrus") or any(w in own for w in FX_WORDS)
        if not fx:
            mats = [s.material for s in ob.material_slots if s.material is not None]
            fx = bool(mats) and all(volume_only(m) for m in mats)
        _FX[own] = fx
    return fx


def volume_only(m):
    if m.node_tree is None:
        return False
    outs = [n for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial"]
    return bool(outs) and all(not o.inputs["Surface"].is_linked and o.inputs["Volume"].is_linked for o in outs)


def is_veg(name):
    n = name.lower()
    return any(w in n for w in VEG)


def gather(dg, owners=None, boxes=None, skip=(), pad=0.05, veg=False):
    """{owner: (n, 3, 3) world triangles} as rendered, one pass over the depsgraph's instances (an instancer's instances
    count as the instancer). owners: only these, every triangle; boxes: only the triangles touching one of them."""
    want = set(owners) if owners is not None else None
    if boxes is not None:
        B = np.array([[np.asarray(b[0], float), np.asarray(b[1], float)] for b in boxes])
        lo, hi = B[:, 0] - pad, B[:, 1] + pad
    cache, out = {}, {}
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type != 'MESH':
            continue
        own = owner_of(inst)
        if (want is not None and own not in want) or own in skip or hidden(inst):
            continue
        if not veg and want is None and (is_veg(own) or is_veg(ob.original.name)):
            continue
        if is_fx(own, ob):
            continue
        M = np.array(inst.matrix_world)
        if boxes is not None:
            bb = np.array(ob.bound_box) @ M[:3, :3].T + M[:3, 3]
            hb = ~((bb.min(0) > hi).any(1) | (bb.max(0) < lo).any(1))
            if not hb.any():
                continue
        key = ob.data.as_pointer()
        L = cache.get(key)
        if L is None:
            L = cache[key] = mesh_tris(ob.data)
        if not len(L):
            continue
        T = L @ M[:3, :3].T + M[:3, 3]
        if boxes is not None:
            tmin, tmax = T.min(1), T.max(1)
            keep = np.zeros(len(T), bool)
            for j in np.nonzero(hb)[0]:
                keep |= ~((tmin > hi[j]).any(1) | (tmax < lo[j]).any(1))
            T = T[keep]
            if not len(T):
                continue
        out.setdefault(own, []).append(T)
    return {k: np.concatenate(v) for k, v in out.items()}


def tris_box(T):
    return T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)


def bvh_of(T):
    return BVHTree.FromPolygons([Vector(p) for p in T.reshape(-1, 3)],
                                [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(T))], all_triangles=True)


def local_co(ob):
    n = len(ob.data.vertices)
    co = np.empty(n * 3)
    ob.data.vertices.foreach_get("co", co)
    return co.reshape(n, 3)


def set_co(ob, co):
    ob.data.vertices.foreach_set("co", np.asarray(co, float).ravel())
    ob.data.update()


def same_points(a, b, tol=1e-4):
    """The same point sets within ``tol``: index by index (the usual case), else in any order (nearest neighbours
    both ways; sorting rounded coordinates mis-paired points lying on a rounding boundary)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.shape != b.shape:
        return False
    if not len(a):
        return True
    if np.abs(a - b).max() <= tol:
        return True
    from mathutils.kdtree import KDTree

    def covered(p, q):
        kd = KDTree(len(q))
        for i, c in enumerate(q):
            kd.insert(c, i)
        kd.balance()
        return all(kd.find(c)[2] <= 2 * tol for c in p)
    return covered(a, b) and covered(b, a)


def bm_co(bm):
    return np.array([tuple(v.co) for v in bm.verts])


def write_bm(me, bm, smooth=None):
    bm.to_mesh(me)
    bm.free()
    if smooth is not None:
        U._apply_smooth(me, smooth)
    me.update()


def remove_tree(ob):
    obs = [ob] + list(ob.children_recursive)
    meshes = {o.data for o in obs if o.type == 'MESH' and o.data is not None}
    names = [o.name for o in obs]
    for o in sorted(obs, key=lambda o: -len(o.children_recursive)):
        if o.name in bpy.data.objects:
            bpy.data.objects.remove(o, do_unlink=True)
    for me in meshes:
        if me.users == 0:
            bpy.data.meshes.remove(me)
    return names


def obj(name):
    return bpy.data.objects.get(name)


def rel_matrix(ob, root):
    """``ob``'s matrix in ``root``'s frame, from the parent chain (valid without a depsgraph update)."""
    m = ob.matrix_parent_inverse @ ob.matrix_basis
    p = ob.parent
    while p is not None and p != root:
        m = p.matrix_parent_inverse @ p.matrix_basis @ m
        p = p.parent
    return m


def area_of(name):
    ob = bpy.data.objects.get(name)
    while ob is not None and ob.parent is not None:
        ob = ob.parent
    return ob.name.split(".")[0] if ob is not None else name.split(".")[0]


def swap_mesh(ob, new_me):
    """Give ``ob`` the mesh ``new_me`` (renamed to the old mesh's name), free the old one if unused."""
    old = ob.data
    name = old.name
    ob.data = new_me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    new_me.name = name
    return ob


# ------------------------------------------------------------------------------------------------- the coplanar scan

class Scan:
    """Coplanar-overlap scan of owners against everything near them (vegetation left out) and against themselves."""

    def __init__(self, label):
        self.label = label
        # piece -> other -> [same, opp, same_exposed] within SCAN_TOL, then the same three for SCAN_TOL..SCAN_TOL12
        self.rows = {}

    def run(self, names, dg, tol=SCAN_TOL, tol12=SCAN_TOL12):
        t0 = time.time()
        rng = np.random.default_rng(12)
        pieces = gather(dg, owners=names, veg=True)
        nsamp = 0
        for pk in sorted(pieces):
            T = pieces[pk]
            lo, hi = tris_box(T)
            near = gather(dg, boxes=[(lo, hi)], skip={pk}, pad=tol12 + 0.01)
            owners = sorted(near)
            if owners:
                N = np.concatenate([near[o] for o in owners])
                oid = np.concatenate([np.full(len(near[o]), i) for i, o in enumerate(owners)])
                N, oid = self._prefilter(T, N, oid, tol12)
            else:
                N, oid = np.zeros((0, 3, 3)), np.zeros(0, int)
            tn = bvh_of(N) if len(N) else None
            ts = bvh_of(T)
            env = gather(dg, boxes=[(lo - EXPOSE_D, hi + EXPOSE_D)], pad=0.0)     # what could hide a pair
            ta = bvh_of(np.concatenate(list(env.values()))) if env else ts
            e1, e2 = T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
            cr = np.cross(e1, e2)
            ar = np.linalg.norm(cr, axis=1) * 0.5
            ok = ar > 1e-9
            area = float(ar[ok].sum())
            step = max(SCAN_STEP, math.sqrt(area / SCAN_MAX)) if area > 0 else SCAN_STEP
            rows = self.rows.setdefault(pk, {})
            nrm = np.zeros_like(cr)
            nrm[ok] = cr[ok] / (2.0 * ar[ok, None])
            for t in np.nonzero(ok)[0]:
                k = int(min(40, max(1, round(ar[t] / (step * step)))))
                u, v = rng.random(k), rng.random(k)
                f = u + v > 1.0
                u[f], v[f] = 1.0 - u[f], 1.0 - v[f]
                P_ = T[t, 0] + np.outer(u, e1[t]) + np.outer(v, e2[t])
                n = Vector(nrm[t])
                w = ar[t] / k
                nsamp += k
                for p in P_:
                    p = Vector(p)
                    hits = []
                    if tn is not None:
                        loc, hn, fi, d = tn.ray_cast(p + n * 2e-4, -n, 4e-4)      # in its plane
                        if loc is not None:
                            hits.append((owners[oid[fi]], loc, hn))
                        else:
                            for sgn in (-1.0, 1.0):                              # the nearest on either side
                                loc, hn, fi, d = tn.ray_cast(p + n * (sgn * 2e-4), n * sgn, tol12)
                                if loc is not None:
                                    hits.append((owners[oid[fi]], loc, hn))
                    for sgn in (-1.0, 1.0):
                        loc, hn, fi, d = ts.ray_cast(p + n * (sgn * 1e-4), n * sgn, tol12)
                        if loc is not None:
                            hits.append(("<self>", loc, hn))
                    for other, loc, hn in hits:
                        c = hn.dot(n)
                        g = (loc - p).dot(n)
                        if abs(c) < SCAN_PAR or abs(g) > tol12:
                            continue
                        r = rows.setdefault(other, [0.0] * 6)
                        b = 0 if abs(g) <= tol else 3
                        if c > 0:
                            r[b] += w
                            q = (loc if g > 0 else p) + n * 0.003
                            if self._exposed(ta, q, n):
                                r[b + 2] += w
                        else:
                            r[b + 1] += w
        for pk in sorted(pieces):
            rows = self.rows.get(pk, {})
            if not any(sum(r) >= 0.01 for r in rows.values()):
                continue
            top = sorted(rows.items(), key=lambda kv: -(kv[1][0] + kv[1][3] + 0.01 * kv[1][1]))[:6]
            log("scan %s %s: same-facing within 5 mm %.2f m2 (exposed %.2f), 5-12 mm %.2f (exposed %.2f); opposite "
                "(contact) %.2f + %.2f m2%s" % (
                    self.label, pk, sum(r[0] for r in rows.values()), sum(r[2] for r in rows.values()),
                    sum(r[3] for r in rows.values()), sum(r[5] for r in rows.values()),
                    sum(r[1] for r in rows.values()), sum(r[4] for r in rows.values()),
                    "".join("; %s %.2f/%.2f/%.2f + %.2f/%.2f" % (o, r[0], r[2], r[1], r[3], r[5]) for o, r in top
                            if r[0] + r[1] + r[3] >= 0.02)))
        log("scan %s: %d pieces, %d samples, %.1f s" % (self.label, len(pieces), nsamp, time.time() - t0))
        return self

    @staticmethod
    def _prefilter(T, N, oid, tol):
        """Keep the neighbour triangles whose box meets a 0.5 m voxel some piece triangle's box meets (the corners
        and centre of a neighbour's box are tested; neighbours over 4 m across are kept)."""
        c = 0.5
        off, K = 1 << 19, 1 << 20

        def enc(a):
            return ((a[:, 0] + off) * K + (a[:, 1] + off)) * K + (a[:, 2] + off)
        lo = np.floor((T.min(1) - tol - 0.01) / c).astype(np.int64)
        hi = np.floor((T.max(1) + tol + 0.01) / c).astype(np.int64)
        span = hi - lo
        big = (span > 80).any(1)
        lo, span = lo[~big], span[~big]
        keys = []
        if len(lo):
            mx = span.max(0)
            for dx in range(mx[0] + 1):
                for dy in range(mx[1] + 1):
                    for dz in range(mx[2] + 1):
                        sel = (span[:, 0] >= dx) & (span[:, 1] >= dy) & (span[:, 2] >= dz)
                        if sel.any():
                            keys.append(enc(lo[sel] + np.array([dx, dy, dz])))
        keys = np.unique(np.concatenate(keys)) if keys else np.zeros(0, np.int64)
        nlo, nhi = N.min(1), N.max(1)
        keep = ((nhi - nlo) > 4.0).any(1)
        for f in ((0, 0, 0), (1, 1, 1), (0.5, 0.5, 0.5), (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 0, 1),
                  (0, 1, 1)):
            p = nlo + (nhi - nlo) * np.array(f)
            keep |= np.isin(enc(np.floor(p / c).astype(np.int64)), keys)
        return N[keep], oid[keep]

    @staticmethod
    def _exposed(tree, q, n):
        t1 = n.orthogonal().normalized()
        t2 = n.cross(t1)
        for d in (n, (n + t1).normalized(), (n - t1).normalized(), (n + t2).normalized(), (n - t2).normalized()):
            if tree.ray_cast(q, d, EXPOSE_D)[0] is None:
                return True
        return False

    def _get(self, a, b, i):
        rows = self.rows.get(a, {})
        if b is None:
            return sum(r[i] for r in rows.values())
        return rows.get(b, [0.0] * 6)[i]

    def same(self, a, b=None, band=0):
        return self._get(a, b, band)

    def opp(self, a, b=None, band=0):
        return self._get(a, b, band + 1)

    def exposed(self, a, b=None, band=0):
        return self._get(a, b, band + 2)

    def pair(self, a, b, band=0):
        """Same-facing area of the pair, scanned from either side (the larger)."""
        return max(self.same(a, b, band), self.same(b, a, band))


# --------------------------------------------------------------------------------------------- footing and walking

def range_height(tree, x, y, top=1e4):
    hit = tree.ray_cast(Vector((x, y, top)), Vector((0.0, 0.0, -1.0)), 2 * top)
    return None if hit[0] is None else hit[0].z


class Ground:
    """world.range (top) and the scene near a box, for footing checks."""

    def __init__(self, dg, box, skip=(), pad=2.0):
        lo, hi = np.asarray(box[0]) - pad, np.asarray(box[1]) + pad
        rg = gather(dg, owners=["world.range"], veg=True).get("world.range")
        if rg is not None:
            keep = ~((rg.min(1) > hi).any(1) | (rg.max(1) < lo).any(1))
            rg = rg[keep]
        self.range = bvh_of(rg) if rg is not None and len(rg) else None
        near = gather(dg, boxes=[(lo, hi)], skip=set(skip) | {"world.range"})
        self.owners = sorted(near)
        if near:
            N = np.concatenate([near[o] for o in self.owners])
            self.oid = np.concatenate([np.full(len(near[o]), i) for i, o in enumerate(self.owners)])
            self.tree = bvh_of(N)
            self.each = {o: bvh_of(near[o]) for o in self.owners}
        else:
            self.tree, self.oid, self.each = None, None, {}
        self.top = float(hi[2]) + 50.0

    def gap(self, p):
        """Air under world point p: 0 when it is under world.range's top or inside something (the first face above it
        faces up: it is under that solid's or that ground's top), else the drop to the first up-facing surface (1.0
        when none within 1 m); and what it rests on."""
        if self.range is not None:
            h = range_height(self.range, p.x, p.y, self.top)
            if h is not None and p.z <= h + 1e-4:
                return 0.0, "world.range"
        for o, t in self.each.items():         # inside a piece (or under a ground sheet): its first face above faces up
            loc, nor, fi, d = t.ray_cast(p - Vector((0, 0, 0.0005)), Vector((0, 0, 1.0)), 2.0)
            if loc is not None and nor.z > 0.0:
                return 0.0, o
        cand = []
        if self.tree is not None:
            loc, nor, fi, d = self.tree.ray_cast(p + Vector((0, 0, 0.0005)), Vector((0, 0, -1.0)), 1.0)
            if loc is not None:
                cand.append((d, nor.z, self.owners[self.oid[fi]]))
        if self.range is not None:
            loc, nor, fi, d = self.range.ray_cast(p + Vector((0, 0, 0.0005)), Vector((0, 0, -1.0)), 1.0)
            if loc is not None:
                cand.append((d, nor.z, "world.range"))
        if not cand:
            return 1.0, None
        d, nz, own = min(cand)
        return (0.0 if nz < 0 else max(0.0, d - 0.0005)), own


def footing(dg, owners, skip_extra=(), step=0.05, foot=0.15):
    """{owner: (worst gap m, area over FLOAT_MAX m2, bottom area m2, what it rests on)} of the down-facing faces of the
    owners' rendered geometry within ``foot`` m of its lowest point (a lantern's base, a tree's trunk foot, a step
    block's bottom; not a canopy)."""
    rng = np.random.default_rng(7)
    pieces = gather(dg, owners=owners, veg=True)
    out = {}
    for pk, T in pieces.items():
        e1, e2 = T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
        cr = np.cross(e1, e2)
        L = np.linalg.norm(cr, axis=1)
        zmin = T[:, :, 2].min()
        dn = (cr[:, 2] < -0.7 * L) & (L > 2e-8) & (T[:, :, 2].max(1) <= zmin + foot)
        if not dn.any():
            continue
        g = Ground(dg, tris_box(T[dn]), skip={pk} | set(skip_extra))
        worst, over, tot, rest = 0.0, 0.0, 0.0, {}
        for t in np.nonzero(dn)[0]:
            ar = 0.5 * L[t]
            k = int(min(60, max(3, round(ar / (step * step)))))
            u, v = rng.random(k), rng.random(k)
            f = u + v > 1.0
            u[f], v[f] = 1.0 - u[f], 1.0 - v[f]
            for p in T[t, 0] + np.outer(u, e1[t]) + np.outer(v, e2[t]):
                gp, on = g.gap(Vector(p))
                tot += ar / k
                worst = max(worst, gp)
                if gp > FLOAT_MAX:
                    over += ar / k
                rest[on] = rest.get(on, 0) + 1
        out[pk] = (worst, over, tot, sorted(rest.items(), key=lambda kv: -kv[1])[:3])
    return out


def stair_walk(st, dg, land=None):
    """Walk rays down an arch.stairs flight (centre and 0.6 m in from each side) from 1 m past its top to 1 m past
    its foot, every 0.05 m, against what is built near it (vegetation left out): (worst riser, top floor offset range,
    foot floor offset range, misses) in the stairs' frame."""
    W = st.matrix_world
    Wi = W.inverted()
    run, n, riser = float(st["arch_run"]), int(st["arch_steps"]), float(st["arch_riser"])
    width = max(abs(v.co.x) for v in obj(st.name + ".steps").data.vertices) * 2.0
    corners = [W @ Vector((x, y, z)) for x in (-0.5 * width, 0.5 * width) for y in (1.2, -run - 1.2)
               for z in (-1.0, n * riser + 3.0)]
    box = (np.min([tuple(c) for c in corners], 0), np.max([tuple(c) for c in corners], 0))
    near = gather(dg, boxes=[box], pad=0.1)
    tree = bvh_of(np.concatenate(list(near.values())))
    down = (W.to_3x3() @ Vector((0, 0, -1))).normalized()
    worst, miss, top_off, foot_off = 0.0, 0, [], []
    for x in (-0.5 * width + 0.6, 0.0, 0.5 * width - 0.6):
        prev = None
        y = 1.0 - 0.013                       # (off the seams at y 0 and -run, where the treads' 12 mm bevel meets
        while y >= -run - 1.0:                # the next floor's sharp edge: a ray there slips into the V)
            o = W @ Vector((x, y, n * riser + 2.5))
            loc = tree.ray_cast(o, down, n * riser + 4.0)[0]
            if loc is None:
                miss += 1
                prev = None
            else:
                z = (Wi @ loc).z
                if prev is not None:
                    worst = max(worst, abs(z - prev))
                prev = z
                if y > 0.3:
                    top_off.append(z - n * riser)
                elif y < -run - 0.3:
                    foot_off.append(z)
            y -= 0.05
    return worst, (min(top_off), max(top_off)) if top_off else None, \
        (min(foot_off), max(foot_off)) if foot_off else None, miss


FLOOR_TOL = 0.06           # m: the floor past a touched flight's top / foot may be this far off its level (round 11
                           # sank the range up to 6 cm round the link stairs' ends; the arena band stands 2 cm over
                           # its stairs' hidden top tread)


# ------------------------------------------------------------------------------------------------------------ parts

class Part:
    name = "?"
    delta = 0                  # objects removed (negative) or added

    def __init__(self):
        self.todo = False
        self.touched = []      # object names whose geometry or transform this part changes
        self.removed = []

    def scan_names(self):
        return list(self.touched)

    def digest_names(self):
        """What DIGEST covers, read from the file as it is now (so a first and a second run hash the same set)."""
        return [n for n in self.touched if obj(n) is not None]

    def targets(self):
        return []              # [(a, b)]: same-facing overlaps that must go

    def floats(self):
        return []              # owners whose bottoms must rest (FLOAT_MAX)

    def stairs(self):
        return []              # stairs roots to walk

    def check(self, fail, dg):
        pass

    def cache_names(self):
        """Owners whose export records (world boxes) this part may change."""
        out = set()
        for n in self.touched:
            ob = obj(n)
            if ob is None:
                continue
            out.add(n)
            out |= {c.name for c in ob.children_recursive}
        return sorted(out)


# -- inscription (#5) -------------------------------------------------------------------------------------------------

def records(dg, owner):
    """export_web.gather's records of ``owner``: its geometry instances (any geometry type) with triangles."""
    n = 0
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type not in ("MESH", "CURVE", "SURFACE", "META", "FONT", "CURVES", "POINTCLOUD"):
            continue
        if owner_of(inst) != owner:
            continue
        try:
            me = ob.to_mesh()
            t = len(me.polygons) if me is not None else 0
            ob.to_mesh_clear()
        except Exception:
            t = 1
        n += t > 0
    return n


def eval_box(dg, name):
    T = gather(dg, owners=[name], veg=True).get(name)
    return None if T is None else tris_box(T)


class Inscription(Part):
    name = "inscription"
    OB = AB.INSCRIPTION

    def plan(self, fail):
        ob = obj(self.OB)
        if ob is None or ob.type not in ("FONT", "MESH"):
            fail.add("inscription: no text or mesh %s" % self.OB)
            return False
        self.todo = ob.type == "FONT"
        if ob.type == "MESH" and (not len(ob.data.vertices) or [m.name if m else None for m in ob.data.materials]
                                  != ["M.lacquer_red"]):
            fail.add("inscription: %s is a mesh but not the converted text" % self.OB)
        log("inscription: %s is a %s" % (self.OB, ob.type))
        self.touched = [self.OB]
        return self.todo

    def before(self, dg):
        self.rec0 = records(dg, self.OB)
        self.box0 = eval_box(dg, self.OB)

    def apply(self):
        AB.text_to_mesh(obj(self.OB))
        log("inscription: converted to a mesh: %d vertices, %d faces" % (len(obj(self.OB).data.vertices),
                                                                     len(obj(self.OB).data.polygons)))

    def check(self, fail, dg):
        ob = obj(self.OB)
        if ob.type != "MESH":
            fail.add("inscription: still a %s" % ob.type)
            return
        n = records(dg, self.OB)
        if n != 1:
            fail.add("inscription: %d export records, expected 1" % n)
        box = eval_box(dg, self.OB)
        b0 = getattr(self, "box0", None)
        if b0 is not None and (np.abs(box[0] - b0[0]).max() > 0.002 or np.abs(box[1] - b0[1]).max() > 0.002):
            fail.add("inscription: its box moved: %s -> %s" % (b0, box))
        log("inscription: one export record (was %s), box %s" % (getattr(self, "rec0", "?"),
                                                                 np.round(box[0], 2).tolist()))

    def scan_names(self):
        return []


# -- scroll (#4) ------------------------------------------------------------------------------------------------------

class Scroll(Part):
    name = "scroll"
    BODY, RING, RING_IN, GROOVE = "scroll.terrace.body", "scroll.ring", "scroll.ring_in", "scroll.ring.groove"

    def centre(self):
        root, body = obj("scroll.root"), obj(self.BODY)
        c = rel_matrix(body, root).inverted() @ Vector((SC.RING_C[0], SC.RING_C[1], 0.0))
        return c.x, c.y

    def plan(self, fail):
        body = obj(self.BODY)
        if body is None or obj(self.RING) is None or obj(self.RING_IN) is None:
            fail.add("scroll: missing the terrace or a ring")
            return False
        mats = [m.name if m else None for m in body.data.materials]
        dark = sum(1 for p in body.data.polygons if p.material_index == 2)
        self.painted = len(mats) == 3 and dark == SC.CHANNEL_SEGS
        if not self.painted and (len(body.data.polygons) != 22 or len(mats) != 2):
            fail.add("scroll: %s is neither the plain platform (22 faces, 2 materials) nor painted (%d faces, %s)" % (
                self.BODY, len(body.data.polygons), mats))
        self.groove = obj(self.GROOVE)
        self.ring_z = [obj(n).location.z for n in (self.RING, self.RING_IN)]
        log("scroll: terrace %s, groove %s, ring origins z %s" % (
            "painted" if self.painted else "plain", "present" if self.groove else "gone", self.ring_z))
        self.touched = [self.BODY, self.RING, self.RING_IN] + ([self.GROOVE] if self.groove else [])
        self.todo = (not self.painted) or self.groove is not None or any(abs(z - SC.RING_Z) > 1e-6 for z in self.ring_z)
        return self.todo

    def apply(self):
        if self.groove is not None:
            self.removed = remove_tree(self.groove)
            self.delta = -len(self.removed)
            log("scroll: removed", self.removed)
        if not self.painted:
            n = SC.terrace_channel(obj(self.BODY), self.centre())
            log("scroll: painted the channel into the terrace's top: %d dark faces, %d faces in all" % (
                n, len(obj(self.BODY).data.polygons)))
        for nm in (self.RING, self.RING_IN):
            obj(nm).location.z = SC.RING_Z

    def check(self, fail, dg):
        body = obj(self.BODY)
        V = local_co(body)
        tree = BVHTree.FromPolygons([Vector(v) for v in V], [tuple(p.vertices) for p in body.data.polygons])
        mi = [p.material_index for p in body.data.polygons]
        zt = V[:, 2].max()
        cx, cy = self.centre()
        c0, c1 = SC.channel_radii()
        cosh = math.cos(math.pi / SC.CHANNEL_SEGS)
        bad, holes, n = 0, 0, 0
        xs, ys = V[:, 0], V[:, 1]
        for k in range(1440):
            a = 2 * math.pi * (k + 0.5) / 1440
            for r in np.arange(0.3, c1 + 3.0, 0.07):
                x, y = cx + r * math.cos(a), cy + r * math.sin(a)
                if not (xs.min() + 0.05 < x < xs.max() - 0.05 and ys.min() + 0.05 < y < ys.max() - 0.05):
                    continue
                n += 1
                loc, nor, fi, d = tree.ray_cast(Vector((x, y, zt + 1.0)), Vector((0, 0, -1)), 2.0)
                if loc is None or abs(loc.z - zt) > 1e-4:
                    holes += 1
                    continue
                if c0 + 0.005 < r < c1 * cosh - 0.005:
                    bad += mi[fi] != 2
                elif r < c0 * cosh - 0.005 or r > c1 + 0.005:
                    bad += mi[fi] != 1
        if holes or bad:
            fail.add("scroll: terrace top: %d holes, %d samples with the wrong stone (of %d)" % (holes, bad, n))
        if obj(self.GROOVE) is not None:
            fail.add("scroll: the groove is still there")
        for nm in (self.RING, self.RING_IN):
            if abs(obj(nm).location.z - SC.RING_Z) > 1e-6:
                fail.add("scroll: %s's origin is at z %.4f, not %.4f" % (nm, obj(nm).location.z, SC.RING_Z))
        log("scroll: the terrace's top is one surface at its height (%d samples), dark stone exactly under r %.3f.."
            "%.3f round the rings' centre; groove gone; ring origins at z %.3f" % (n, c0, c1, SC.RING_Z))

    def targets(self):
        return [(self.BODY, self.GROOVE)]


# -- lawns (#6) -------------------------------------------------------------------------------------------------------

SETTLED = {   # library props _garden settles on the lawn: (name, foot radius, sink)
    "library.lantern_stone": (LI.LANTERN_FOOT_R, LI.SETTLE_SINK),
    "library.lantern_stone.001": (LI.LANTERN_FOOT_R, LI.SETTLE_SINK),
    "library.lantern_stone.002": (LI.LANTERN_FOOT_R, LI.SETTLE_SINK),
    "library.lantern_stone.003": (LI.LANTERN_FOOT_R, LI.SETTLE_SINK),
    "library.blossom": (LI.TRUNK_FOOT_R, LI.SETTLE_SINK),
    "library.blossom.001": (LI.TRUNK_FOOT_R, LI.SETTLE_SINK),
    "library.boulder": (LI.BOULDER_FOOT_R, LI.BOULDER_SINK),
}


class Lawns(Part):
    name = "lawns"
    LAWNS = (("library.lawn", LI.seat_lawn, LI.TERRACE_Z, LI.LAWN_CLEAR, LI.LAWN_SINK),
             ("mirror.lawn", MI.seat_lawn, MI.TERRACE_Z, MI.LAWN_CLEAR, MI.LAWN_SINK))

    def plan(self, fail):
        self.todo_lawns = []
        for nm, fn, fz, clear, sink in self.LAWNS:
            ob = obj(nm)
            if ob is None:
                fail.add("lawns: no %s" % nm)
                continue
            m = ob.matrix_parent_inverse @ ob.matrix_basis
            if any(abs(m[i][j] - (1.0 if i == j else 0.0)) > 1e-6 for i in range(4) for j in range(4)):
                fail.add("lawns: %s is not in its area root's frame" % nm)
            z = local_co(ob)[:, 2]
            n = int(((z < fz + clear - 1e-6) & (z > fz - sink + 1e-6)).sum())
            log("lawns: %s: %d of %d vertices within (%.2f, %.2f) of the terrace" % (nm, n, len(z), -sink, clear))
            if n:
                self.todo_lawns.append(nm)
        self.touched = [n for n, *_ in self.LAWNS] + [n for n in SETTLED if obj(n) is not None]
        self.todo = bool(self.todo_lawns)
        return self.todo

    def before(self, dg):
        # the range under the lawns must be the flat terrace seat_lawn assumes
        for nm, fn, fz, clear, sink in self.LAWNS:
            ob = obj(nm)
            root = ob.parent
            W = np.array(ob.matrix_world)
            co = local_co(ob)
            near = (co[:, 2] < fz + 0.2) & (co[:, 2] > fz - 0.4)
            wc = co[near] @ W[:3, :3].T + W[:3, 3]
            g = Ground(dg, (wc.min(0), wc.max(0)), pad=1.0)
            Ri = root.matrix_world.inverted()
            off = 0.0
            for p in wc[::7]:
                h = range_height(g.range, p[0], p[1], g.top)
                if h is not None:
                    off = max(off, abs((Ri @ Vector((p[0], p[1], h))).z - fz))
            self.flat_off = max(getattr(self, "flat_off", 0.0), off)
            log("lawns: world.range under %s's crossing is flat at %.2f to %.4f m" % (nm, fz, off))
        self.loc0 = {n: tuple(obj(n).location) for n in SETTLED if obj(n) is not None}

    def apply(self):
        for nm, fn, fz, clear, sink in self.LAWNS:
            if nm in self.todo_lawns:
                log("lawns: %s: %d vertices sunk under the terrace" % (nm, fn(obj(nm))))
        # the library props _garden settles on the lawn, settled again on the seated one
        lawn = obj("library.lawn")
        bvh = LI._lawn_bvh(lawn)
        moved = []
        for nm, (r, sink) in SETTLED.items():
            ob = obj(nm)
            if ob is None:
                continue
            z0 = ob.location.z
            LI._settle(ob, bvh, r, sink=sink)
            if abs(ob.location.z - z0) > 1e-5:
                moved.append("%s %+.3f" % (nm, ob.location.z - z0))
        log("lawns: library props settled again on the seated lawn:", moved or "none moved")

    def check(self, fail, dg):
        if getattr(self, "flat_off", 0.0) > 0.003:
            fail.add("lawns: world.range under the lawns is %.4f m off the flat terrace seat_lawn assumes" %
                     self.flat_off)
        for nm, fn, fz, clear, sink in self.LAWNS:
            z = local_co(obj(nm))[:, 2]
            n = int(((z < fz + clear - 1e-6) & (z > fz - sink + 1e-6)).sum())
            if n:
                fail.add("lawns: %s still has %d vertices within (%.2f, %.2f) of the terrace" % (nm, n, -sink, clear))
        missing = [n for n in SETTLED if obj(n) is None]
        if missing:
            fail.add("lawns: settled props missing: %s" % missing)
        log("lawns: no lawn vertex within (-%.2f, %.2f) m of the terrace" % (LI.LAWN_SINK, LI.LAWN_CLEAR))

    def scan_names(self):
        return [n for n, *_ in self.LAWNS]

    def targets(self):
        return [("library.lawn", "world.range"), ("mirror.lawn", "world.range")]

    def floats(self):
        return [n for n in SETTLED if obj(n) is not None]


# -- library paths (#22) ----------------------------------------------------------------------------------------------

def box_slab_co(x0, x1, y0, y1, z0, z1):
    return np.array([(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)])


class LibPaths(Part):
    name = "libpaths"

    def plan(self, fail):
        ap = LI.PLAZA_R * math.cos(math.pi / 8)
        front_y = LI.PAGODA_XY[1] - ap
        root = obj("library.root")
        self.feet = {}
        for side, nm in (("east", "library.study_east.steps"), ("west", "library.study_west.steps")):
            foot, _down = LI.steps_foot(obj(nm), root)
            self.feet[side] = foot.x
        t, b = LI.PLAZA_TOP, -0.5
        self.want = {
            "library.path_main": (box_slab_co(-4.0, 4.0, -40.0, front_y + 0.5, b, t), box_slab_co(-4.0, 4.0, -40.0,
                                                                                                front_y, b, t)),
            "library.path_east": (box_slab_co(3.5, 19.0, -11.5, -8.5, b, t),
                                  box_slab_co(4.0, min(19.0, self.feet["east"]), -11.5, -8.5, b, t)),
            "library.path_west": (box_slab_co(-21.0, LI.PAGODA_XY[0] - ap + 0.5, 9.0, 12.0, b, t),
                                  box_slab_co(max(-21.0, self.feet["west"]), LI.PAGODA_XY[0] - ap, 9.0, 12.0, b, t)),
        }
        # the depart walk: old = library._strip from 2.5 m back inside the plaza, 4 mm under its top
        hd = LI.DEPART_HEADING
        dx, dy = math.cos(hd), math.sin(hd)
        run = math.ceil(LI.DEPART_STEP_H / 0.17 - 1e-6) * LI.STEP_RUN
        top_edge = (LI.DEPART_XY[0] - dx * run, LI.DEPART_XY[1] - dy * run)
        start = (LI.DEPART_PATH_START[0] - dx * 2.5, LI.DEPART_PATH_START[1] - dy * 2.5)
        L = math.hypot(top_edge[0] - start[0], top_edge[1] - start[1])
        n = (-dy, dx)
        old = []
        for s in (-0.5 * L, 0.5 * L):
            for w in (-0.5 * LI.DEPART_W, 0.5 * LI.DEPART_W):
                for z in (-0.6, LI.PLAZA_TOP - 0.004):
                    cx, cy = (start[0] + top_edge[0]) / 2, (start[1] + top_edge[1]) / 2
                    old.append((cx + dx * s + n[0] * w, cy + dy * s + n[1] * w, z))
        newv, self.walk_faces = LI.depart_walk_geom()
        self.want["library.depart_path.walk"] = (np.array(old), np.array(newv))
        self.state = {}
        for nm, (o, nw) in self.want.items():
            ob = obj(nm)
            have = local_co(ob) if ob is not None else None
            if have is None:
                fail.add("libpaths: no %s" % nm)
                continue
            if same_points(have, nw, 2e-4):
                self.state[nm] = "new"
            elif same_points(have, o, 2e-4):
                self.state[nm] = "old"
            else:
                fail.add("libpaths: %s is neither the old nor the new slab: box %s" % (
                    nm, [have.min(0).round(3).tolist(), have.max(0).round(3).tolist()]))
        log("libpaths:", self.state, "study step feet x %.3f / %.3f" % (self.feet["east"], self.feet["west"]))
        self.touched = list(self.want)
        self.todo = any(s == "old" for s in self.state.values())
        return self.todo

    def apply(self):
        for nm, st in self.state.items():
            if st != "old":
                continue
            ob = obj(nm)
            if nm == "library.depart_path.walk":
                me = ob.data
                verts, faces = LI.depart_walk_geom()
                me.clear_geometry()
                me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
                me.validate(verbose=False)
                U.shade_flat(me)
                me.update()
            else:
                old, new = self.want[nm]
                co = local_co(ob)
                for i in range(3):
                    lo_o, hi_o, lo_n, hi_n = old[:, i].min(), old[:, i].max(), new[:, i].min(), new[:, i].max()
                    co[np.abs(co[:, i] - lo_o) < 1e-4, i] = lo_n
                    co[np.abs(co[:, i] - hi_o) < 1e-4, i] = hi_n
                set_co(ob, co)
            log("libpaths: %s rebuilt: box %s" % (nm, np.round(local_co(ob).min(0), 3).tolist() +
                                                  np.round(local_co(ob).max(0), 3).tolist()))

    def check(self, fail, dg):
        for nm, (o, nw) in self.want.items():
            if not same_points(local_co(obj(nm)), nw, 2e-4):
                fail.add("libpaths: %s is not the new slab" % nm)

    def scan_names(self):
        return list(self.want) + ["library.plaza.body"]

    def targets(self):
        return [("library.plaza.body", n) for n in self.want] + [
            ("library.path_east", "library.study_east.steps.steps"),
            ("library.path_west", "library.study_west.steps.steps"), ("library.path_east", "library.path_main")]


# -- steles (#28) -----------------------------------------------------------------------------------------------------

class Steles(Part):
    name = "steles"
    AISLE, WALKS = "steles.aisle", ("steles.walk.rear_w", "steles.walk.rear_e")
    LANGS = (("steles.lang", -1), ("steles.lang.001", 1))

    def floors(self):
        out = []
        for lang, side in self.LANGS:
            out += [o.name for o in obj(lang).children if o.type == 'MESH' and ".floor" in o.name[len(lang):]]
        return out

    def plan(self, fail):
        self.foot = ST.field_foot()
        hw = ST.AISLE_HW
        co = local_co(obj(self.AISLE))
        xm = np.abs(co[:, 0]).max()
        self.aisle = "new" if abs(xm - (hw - self.foot)) < 1e-4 else ("old" if abs(xm - hw) < 1e-4 else None)
        if self.aisle is None:
            fail.add("steles: the aisle's half width %.4f is neither %.3f nor %.4f" % (xm, hw, hw - self.foot))
        self.walk = {}
        for nm in self.WALKS:
            co = local_co(obj(nm))
            ax = np.sort(np.unique(np.round(np.abs(co[:, 0]), 4)))
            ys = np.sort(np.unique(np.round(co[:, 1], 4)))
            if abs(ax[0] - ST.FIELD_X0) < 1e-4 and abs(ys[0] - ST.WALK_Y0) < 1e-4:
                self.walk[nm] = "old"
            elif abs(ax[0] - (ST.FIELD_X0 - self.foot)) < 1e-4 and abs(ys[0] - (ST.WALK_Y0 + self.foot)) < 1e-4:
                self.walk[nm] = "new"
            else:
                fail.add("steles: %s's first leg starts at |x| %.4f, y %.4f: neither old nor new" % (nm, ax[0], ys[0]))
        self.cuts = {lang: ST.corridor_cut(side) for lang, side in self.LANGS}
        self.lang_todo = []
        for lang, side in self.LANGS:
            (px, py), (dx, dy) = self.cuts[lang]
            n = 0
            for f in obj(lang).children:
                if f.type != 'MESH' or ".floor" not in f.name[len(lang):]:
                    continue
                for v in f.data.vertices:
                    along = (v.co.x - px) * dx + (v.co.y - py) * dy
                    lat = -(v.co.x - px) * dy + (v.co.y - py) * dx
                    n += along > 1e-6 and abs(lat) <= 0.5 * ST.CORR_W + 0.5
            if n:
                self.lang_todo.append(lang)
        log("steles: plinth foot %.4f m; aisle %s, walks %s, corridor floors to trim %s" % (
            self.foot, self.aisle, self.walk, self.lang_todo))
        self.touched = [self.AISLE] + list(self.WALKS) + self.floors()
        self.todo = self.aisle == "old" or "old" in self.walk.values() or bool(self.lang_todo)
        return self.todo

    def apply(self):
        hw, f = ST.AISLE_HW, self.foot
        if self.aisle == "old":
            ob = obj(self.AISLE)
            co = local_co(ob)
            m = np.abs(np.abs(co[:, 0]) - hw) < 1e-4
            co[m, 0] = np.sign(co[m, 0]) * (hw - f)
            set_co(ob, co)
        for nm, st in self.walk.items():
            if st != "old":
                continue
            ob = obj(nm)
            co = local_co(ob)
            mx = np.abs(np.abs(co[:, 0]) - ST.FIELD_X0) < 1e-4
            co[mx, 0] = np.sign(co[mx, 0]) * (ST.FIELD_X0 - f)
            my = np.abs(co[:, 1] - ST.WALK_Y0) < 1e-4
            co[my, 1] = ST.WALK_Y0 + f
            set_co(ob, co)
        for lang, side in self.LANGS:
            if lang in self.lang_todo:
                log("steles: %s: %d floor vertices trimmed to the corner pavilion's edge" % (
                    lang, ST.trim_corridor_floor(obj(lang), [self.cuts[lang]], ST.CORR_W)))
        log("steles: aisle half width %.4f, rear walks from |x| %.4f, y %.4f" % (hw - f, ST.FIELD_X0 - f,
                                                                              ST.WALK_Y0 + f))

    def check(self, fail, dg):
        # the corridor floor meets the pavilion platform edge to edge: rays down along the corridor's axis from the
        # pavilion out land on one floor at the platform's height
        sc = bpy.context.scene
        root = obj("steles.root")
        W = root.matrix_world
        Wi = W.inverted()
        worst = 0.0
        for lang, side in self.LANGS:
            (px, py), _d = self.cuts[lang]
            for k in range(-20, 21):
                x = px + side * 0.01 * k
                for dy in (-1.2, 0.0, 1.2):
                    hit, loc, nor, fi, ob, mx = sc.ray_cast(dg, W @ Vector((x, py + dy, 3.0)), Vector((0, 0, -1)),
                                                            distance=4.0)
                    if not hit:
                        fail.add("steles: hole in the floor at the %s corridor's start (%.2f, %.2f)" % (lang, x, py + dy))
                        continue
                    z = (Wi @ loc).z
                    if abs(z - ST.CORR_PLAT_H) > 0.05:
                        continue            # a post or bench standing there
                    worst = max(worst, abs(z - ST.CORR_PLAT_H))
        if worst > 0.002:
            fail.add("steles: a %.4f m step where the corridor floors meet the pavilion platforms" % worst)
        log("steles: the corridor floors meet the corner pavilions' platforms flush (worst %.4f m)" % worst)

    def scan_names(self):
        return list(self.touched) + ["steles.corner_pav.platform.body", "steles.corner_pav.001.platform.body",
                                     "steles.field.e.body", "steles.field.w.body"]

    def targets(self):
        out = [(self.AISLE, "steles.field.e.body"), (self.AISLE, "steles.field.w.body"),
               ("steles.field.e.body", "steles.walk.rear_e"), ("steles.field.w.body", "steles.walk.rear_w")]
        for f in self.floors():
            out += [("steles.corner_pav.platform.body", f), ("steles.corner_pav.001.platform.body", f)]
        return out


# -- the abode's cave floor (#29) -------------------------------------------------------------------------------------

class Cave(Part):
    name = "cave"
    OB = "abode.cave_floor"

    def plan(self, fail):
        co = local_co(obj(self.OB))
        y0 = co[:, 1].min()
        self.old_y, self.new_y = AB.YG + AB.CAVE_FLOOR_Y0_OLD, AB.YG + AB.DECK_BACK
        self.state = "new" if abs(y0 - self.new_y) < 1e-4 else ("old" if abs(y0 - self.old_y) < 1e-4 else None)
        if self.state is None:
            fail.add("cave: %s starts at y %.4f, neither %.4f nor %.4f" % (self.OB, y0, self.old_y, self.new_y))
        log("cave: %s %s (starts at y %.3f)" % (self.OB, self.state, y0))
        self.touched = [self.OB]
        self.todo = self.state == "old"
        return self.todo

    def apply(self):
        ob = obj(self.OB)
        co = local_co(ob)
        co[np.abs(co[:, 1] - self.old_y) < 1e-4, 1] = self.new_y
        set_co(ob, co)

    def check(self, fail, dg):
        sc = bpy.context.scene
        root = obj("abode.root")
        W, Wi = root.matrix_world, root.matrix_world.inverted()
        worst = 0.0
        for k in range(-30, 31):
            y = self.new_y + 0.01 * k
            for x in (AB.GATE_X - 1.5, AB.GATE_X, AB.GATE_X + 1.5):
                hit, loc, nor, fi, ob, mx = sc.ray_cast(dg, W @ Vector((x, y, AB.DECK_Z + 1.5)), Vector((0, 0, -1)),
                                                        distance=3.0)
                if not hit:
                    fail.add("cave: hole in the floor at the gate (%.2f, %.2f)" % (x, y))
                    continue
                z = (Wi @ loc).z
                if abs(z - AB.DECK_Z) < 0.05:
                    worst = max(worst, abs(z - AB.DECK_Z))
        if worst > 0.002:
            fail.add("cave: a %.4f m step between the deck and the cave floor" % worst)
        log("cave: deck and cave floor meet flush at the moon gate (worst %.4f m)" % worst)

    def scan_names(self):
        return [self.OB, "abode.deck"]

    def targets(self):
        return [(self.OB, "abode.deck")]


# -- forge (#30) ------------------------------------------------------------------------------------------------------

class Forge(Part):
    name = "forge"
    OB = "forge.paving"

    def plan(self, fail):
        me = obj(self.OB).data
        bn, bo = FG._paving_bm(True), FG._paving_bm(False)
        new, old = (len(bn.faces), bm_co(bn)), (len(bo.faces), bm_co(bo))
        bn.free()
        bo.free()
        have = (len(me.polygons), local_co(obj(self.OB)))
        self.state = "new" if have[0] == new[0] and same_points(have[1], new[1]) else (
            "old" if have[0] == old[0] and same_points(have[1], old[1]) else None)
        if self.state is None:
            fail.add("forge: %s is neither the uncut (%d faces) nor the cut paving (%d faces): %d faces" % (
                self.OB, old[0], new[0], have[0]))
        log("forge: paving %s (%d faces; cut %d)" % (self.state, have[0], new[0]))
        self.touched = [self.OB]
        self.todo = self.state == "old"
        return self.todo

    def apply(self):
        me = obj(self.OB).data
        write_bm(me, FG._paving_bm(True), False)
        log("forge: paving rebuilt without a top under the two landings: %d faces" % len(me.polygons))

    def check(self, fail, dg):
        # over each landing: no paving top left, and the landing's own top at z 0 there
        root = obj("forge.root")
        Wi = root.matrix_world.inverted()
        ptree = BVHTree.FromPolygons([Vector(v) for v in local_co(obj(self.OB))],
                                     [tuple(p.vertices) for p in obj(self.OB).data.polygons])
        lt = gather(dg, owners=["forge.arrival.body", "forge.bridgehead.body"], veg=True)
        Wl = np.array(Wi)
        land = bvh_of(np.concatenate([T @ Wl[:3, :3].T + Wl[:3, 3] for T in lt.values()]))
        left = 0
        n = 0
        for (cx, cy), w, d, rot in (FG.ARRIVAL_PLAT, FG.BRIDGEHEAD_PLAT):
            ax, ay = Vector((math.cos(rot), math.sin(rot), 0)), Vector((-math.sin(rot), math.cos(rot), 0))
            for i in range(-10, 11):
                for j in range(-10, 11):
                    p = Vector((cx, cy, 0)) + ax * (i / 10.0 * (0.5 * w - 0.02)) + ay * (j / 10.0 * (0.5 * d - 0.02))
                    if math.hypot(p.x, p.y) > FG.TERRACE_R:
                        continue
                    n += 1
                    loc = ptree.ray_cast(Vector((p.x, p.y, 1.0)), Vector((0, 0, -1)), 1.5)[0]
                    if loc is not None and abs(loc.z) < 1e-4:
                        left += 1
                    loc = land.ray_cast(Vector((p.x, p.y, 1.0)), Vector((0, 0, -1)), 1.5)[0]
                    if loc is None or abs(loc.z) > 1e-4:
                        fail.add("forge: no landing top at z 0 at (%.2f, %.2f)" % (p.x, p.y))
        if left:
            fail.add("forge: the paving's top is still under the landings at %d of %d points" % (left, n))
        log("forge: no paving top under the arrival / bridgehead landings (%d points), the landings' tops are the "
            "floor there" % n)

    def scan_names(self):
        return [self.OB, "forge.arrival.body", "forge.bridgehead.body"]

    def targets(self):
        return [(self.OB, "forge.arrival.body"), (self.OB, "forge.bridgehead.body")]


# -- arena (#38, #16) -------------------------------------------------------------------------------------------------

def stairs_rebuild(root_name, width, height, run_per_step, fail):
    """Rebuild an arch.stairs flight's '.steps' mesh in place for a new ``height`` (no ramp, no balustrade): a
    temporary flight from the same call, its mesh moved over, its root props copied."""
    st = obj(root_name)
    coll = st.users_collection[0]
    tmp = A.stairs(root_name + "~tmp", coll, width, height, run_per_step=run_per_step, ramp=False, balustrade=False,
                   location=(0, 0, 0))
    steps_tmp = obj(tmp.name + ".steps")
    me = steps_tmp.data
    steps_tmp.data = bpy.data.meshes.new("~empty")
    swap_mesh(obj(root_name + ".steps"), me)
    for k in ("arch_run", "arch_steps", "arch_riser"):
        st[k] = tmp[k]
    for o in [steps_tmp, tmp]:
        d = o.data if o.type == 'MESH' else None
        bpy.data.objects.remove(o, do_unlink=True)
        if d is not None and d.users == 0:
            bpy.data.meshes.remove(d)


class Arena(Part):
    name = "arena"
    WALK, REAR_WALK, PIER = "arena.bridgehead_walk", "arena.rear_walk", "arena.rear_pier"
    STAIRS = ("arena.steps", "arena.rear_steps", "arena.west_steps")

    def plan(self, fail):
        run = float(obj("arena.steps")["arch_run"])
        foot0, foot1 = AR.FRONT_STEPS_Y_OLD - run, AR.FRONT_STEPS_Y - run      # the front steps' foot, old and new
        r_foot = AR.R_BAND - 0.15 + float(obj("arena.rear_steps")["arch_run"])
        rot = AR.REAR_A - math.pi / 2
        self.slabs = {
            # name: (old (centre, size), new (centre, size), rot)
            self.WALK: (((0.0, (AR.BRIDGE_Y1 - 0.15 + foot0 + 0.05) * 0.5), (9.2, foot0 + 0.05 - (AR.BRIDGE_Y1 - 0.15))),
                        ((0.0, (AR.BRIDGE_Y1 + foot1 + 0.05) * 0.5), (9.2, foot1 + 0.05 - AR.BRIDGE_Y1)), 0.0),
            self.REAR_WALK: ((AR._radial(AR.REAR_A, (r_foot - 0.1 + AR.LAND_R[0] + 0.15) * 0.5),
                              (3.0, AR.LAND_R[0] + 0.15 - (r_foot - 0.1))),
                             (AR._radial(AR.REAR_A, (r_foot - 0.1 + AR.LAND_R[0]) * 0.5),
                              (3.0, AR.LAND_R[0] - (r_foot - 0.1))), rot),
        }
        self.state = {}
        for nm, (old, new, r) in self.slabs.items():
            ob = obj(nm)
            co = local_co(ob)
            sy = co[:, 1].max() - co[:, 1].min()
            loc = (ob.location.x, ob.location.y)
            if abs(sy - new[1][1]) < 1e-4 and math.dist(loc, new[0]) < 1e-4:
                self.state[nm] = "new"
            elif abs(sy - old[1][1]) < 1e-4 and math.dist(loc, old[0]) < 1e-4:
                self.state[nm] = "old"
            else:
                fail.add("arena: %s (length %.4f at %s) is neither the old nor the new slab" % (nm, sy, loc))
        pier = obj(self.PIER)
        body = obj(self.PIER + ".body")
        d = local_co(body)[:, 1]
        depth = d.max() - d.min()
        new_d = AR.PIER_R1 - AR.LAND_R[1]
        loc_new = AR._radial(AR.REAR_A, (AR.LAND_R[1] + AR.PIER_R1) * 0.5)
        loc_old = AR._radial(AR.REAR_A, (AR.LAND_R[1] - 0.2 + AR.PIER_R1) * 0.5)
        pl = (pier.location.x, pier.location.y)
        zmin = float(local_co(body)[:, 2].min())          # the footing's bottom: -PIER_SINK new, -0.6 old
        if (math.dist(pl, loc_new) < 1e-4 and abs(depth - self._pier_depth(new_d)) < 1e-4
                and abs(zmin + AR.PIER_SINK) < 1e-4):
            self.state[self.PIER] = "new"
        elif (math.dist(pl, loc_old) < 1e-4 and abs(depth - self._pier_depth(new_d + 0.2)) < 1e-4
              and abs(zmin + 0.6) < 1e-4):
            self.state[self.PIER] = "old"
        else:
            fail.add("arena: %s (at %s, body depth %.4f, bottom %.4f) is neither the old nor the new pier"
                     % (self.PIER, pl, depth, zmin))
        self.stair_h = {}
        for nm in self.STAIRS:
            st = obj(nm)
            h = float(st["arch_steps"]) * float(st["arch_riser"])
            new_h = AR.Z_BAND - st.location.z - AR.BAND_STEP_DROP
            old_h = AR.Z_BAND - st.location.z - AR.BAND_STEP_DROP_OLD
            y_new, y_old = (AR.FRONT_STEPS_Y, AR.FRONT_STEPS_Y_OLD) if nm == "arena.steps" else (st.location.y,) * 2
            # (verify: the blocks also reach AR.STEP_SINK under their foot; 'unsunk' = the new flight, block not sunk)
            zmin = min(v.co.z for v in obj(nm + ".steps").data.vertices)
            sunk, flat = abs(zmin + AR.STEP_SINK) < 1e-4, abs(zmin) < 1e-4
            if abs(h - new_h) < 1e-4 and abs(st.location.y - y_new) < 1e-4 and (sunk or flat):
                self.state[nm] = "new" if sunk else "unsunk"
            elif abs(h - old_h) < 1e-4 and abs(st.location.y - y_old) < 1e-4 and flat:
                self.state[nm] = "old"
            else:
                fail.add("arena: %s is %.4f m tall at y %.4f, block bottom %.4f: neither %.4f at %.4f (bottom 0) nor "
                         "%.4f at %.4f (bottom 0 or %.4f)" % (nm, h, st.location.y, zmin, old_h, y_old, new_h, y_new,
                                                             -AR.STEP_SINK))
            self.stair_h[nm] = new_h
        log("arena:", self.state)
        self.touched = list(self.slabs) + [self.PIER, self.PIER + ".body"] + list(self.STAIRS) +             [s + ".steps" for s in self.STAIRS]
        self.todo = "old" in self.state.values() or "unsunk" in self.state.values()
        return self.todo

    @staticmethod
    def _pier_depth(depth):
        """arch.platform 'plain' body's y extent for a ``depth`` slab (its footing flares 0.35 x the moulding scale)."""
        s = min(max(0.16 * 0.5, 0.06), 0.32)
        return depth + 2 * 0.35 * s

    def apply(self):
        for nm, (old, new, r) in self.slabs.items():
            if self.state[nm] != "old":
                continue
            ob = obj(nm)
            co = local_co(ob)
            (cx, cy), (sx, sy) = new
            ys = co[:, 1]
            co[ys > 0, 1] = 0.5 * sy
            co[ys < 0, 1] = -0.5 * sy
            set_co(ob, co)
            ob.location.x, ob.location.y = cx, cy
        if self.state[self.PIER] == "old":
            pier = obj(self.PIER)
            coll = pier.users_collection[0]
            rot = AR.REAR_A - math.pi / 2
            tmp = A.platform(self.PIER + "~tmp", coll, AR.PIER_W, depth=AR.PIER_R1 - AR.LAND_R[1], height=0.5,
                             style="plain", sink=AR.PIER_SINK, location=(0, 0, 0), rotation_z=rot)
            tb = obj(tmp.name + ".body")
            me = tb.data
            tb.data = bpy.data.meshes.new("~empty")
            swap_mesh(obj(self.PIER + ".body"), me)
            for o in (tb, tmp):
                d = o.data if o.type == 'MESH' else None
                bpy.data.objects.remove(o, do_unlink=True)
                if d is not None and d.users == 0:
                    bpy.data.meshes.remove(d)
            x, y = AR._radial(AR.REAR_A, (AR.LAND_R[1] + AR.PIER_R1) * 0.5)
            pier.location.x, pier.location.y = x, y
        fails = Fail()
        for nm in self.STAIRS:
            if self.state[nm] == "old":
                stairs_rebuild(nm, 9.0 if nm == "arena.steps" else 2.5, self.stair_h[nm],
                               0.33 if nm == "arena.steps" else 0.3, fails)
                if nm == "arena.steps":
                    obj(nm).location.y = AR.FRONT_STEPS_Y
            if self.state[nm] in ("old", "unsunk"):
                AR.sink_steps(obj(nm), AR.STEP_SINK)
        log("arena: walks and pier end at their landings' edges; band stairs' top tread %.3f m under the band, their "
            "blocks %.2f m under their foot" % (AR.BAND_STEP_DROP, AR.STEP_SINK))

    def check(self, fail, dg):
        for nm in self.STAIRS:
            st = obj(nm)
            h = float(st["arch_steps"]) * float(st["arch_riser"])
            if abs(h - self.stair_h[nm]) > 1e-4:
                fail.add("arena: %s is %.4f m tall, not %.4f" % (nm, h, self.stair_h[nm]))
            zmin = min(v.co.z for v in obj(nm + ".steps").data.vertices)
            if abs(zmin + AR.STEP_SINK) > 1e-4:
                fail.add("arena: %s's block reaches %.4f, not %.4f" % (nm, zmin, -AR.STEP_SINK))

    def floats(self):
        return [s + ".steps" for s in self.STAIRS]

    def scan_names(self):
        return list(self.slabs) + [self.PIER + ".body", "arena.rear_landing.body", "arena.bridgehead.body",
                                   "arena.platform"] + [s + ".steps" for s in self.STAIRS]

    def targets(self):
        return [("arena.bridgehead.body", self.WALK), ("arena.rear_landing.body", self.PIER + ".body"),
                ("arena.rear_landing.body", self.REAR_WALK), ("arena.platform", "arena.steps.steps"),
                ("arena.platform", "arena.rear_steps.steps"), ("arena.platform", "arena.west_steps.steps")]

    def stairs(self):
        return list(self.STAIRS)


# -- mission (#40, #18) -----------------------------------------------------------------------------------------------

def role_key(label, years, scale, frame, rim, relief):
    sig = "%s|%s|%.4f|%r|%r|%r|%r|%r|%r|%r|%r|%s|%s|%d" % (
        label, years, scale, (MS.ROLE_W, MS.ROLE_H, MS.ROLE_T), MS.ROLE_CORD, MS.ROLE_CORD_X, MS.ROLE_NOTCH, frame,
        rim, MS.ROLE_RIM_GLOW, (MS.ROLE_YEAR_CAP, MS.ROLE_LINE_GAP, relief), MS.ROLE_FONT, MS.ROLE_FONT_YEARS,
        MS.ROLE_REV)
    return "props.mission.role.%08x.v%d" % (zlib.crc32(sig.encode("utf-8")) & 0xFFFFFFFF, P._VERSION)


ROLE_OLD = dict(frame=(0.05, 0.13, 0.012), rim=(0.165, 0.19, 0.004), relief=0.008)
ROLE_KINDS = ("props.role.board", "props.role.gold", "props.role.glyphs", "props.role.glyph_rim", "props.role.cord")


def role_kind(name):
    for k in ROLE_KINDS:
        if name == k or re.fullmatch(re.escape(k) + r"\.\d{3}", name):
            return k
    return None


class Mission(Part):
    name = "mission"

    def digest_names(self):
        out = [f.name for lang, _ in self.langs for f in obj(lang).children
               if f.type == 'MESH' and ".floor" in f.name[len(lang):]] + ["mission.depart_steps.steps"]
        for i, stt, c, new in self.roles:
            cn = bpy.data.collections.get(new)      # (the board's prototype as the file has it now)
            if cn is not None:
                out += [o.name for o in cn.all_objects if role_kind(o.name) in ROLE_KINDS[:4]]
        return out

    def plan(self, fail):
        hall = obj("mission.hall")
        self.terrace_hw = (float(hall["arch_platform"][0]) + MS.TERRACE_MARGIN) / 2
        self.langs = []
        for lang in ("mission.lang", "mission.lang.001"):
            ob = obj(lang)
            sx = -1 if any(v.co.x < 0 for f in ob.children if f.type == 'MESH' for v in f.data.vertices) else 1
            self.langs.append((lang, sx))
        self.lang_todo = []
        for lang, sx in self.langs:
            n = 0
            for (px, py), (dx, dy) in MS.corridor_cuts(sx, self.terrace_hw):
                for f in obj(lang).children:
                    if f.type != 'MESH' or ".floor" not in f.name[len(lang):]:
                        continue
                    for v in f.data.vertices:
                        along = (v.co.x - px) * dx + (v.co.y - py) * dy
                        lat = -(v.co.x - px) * dy + (v.co.y - py) * dx
                        n += along > 1e-6 and abs(lat) <= 0.5 * MS.CORRIDOR_W + 0.5
            if n:
                self.lang_todo.append(lang)
        # role boards: each instancer's collection is the old or the new prototype
        self.scale = MS.role_text_scale()
        self.roles = []
        for i, (label, years) in enumerate(MS.ROLE_BOARDS):
            old = role_key(label, years, self.scale, ROLE_OLD["frame"], ROLE_OLD["rim"], ROLE_OLD["relief"])
            new = role_key(label, years, self.scale, MS.ROLE_FRAME, MS.ROLE_RIM, MS.ROLE_RELIEF)
            c_old, c_new = bpy.data.collections.get(old), bpy.data.collections.get(new)
            if c_new is not None and c_old is None:
                self.roles.append((i, "new", c_new, new))
            elif c_old is not None and c_new is None:
                self.roles.append((i, "old", c_old, new))
            else:
                fail.add("mission: role board %d: prototype %s / %s: %s / %s" % (i, old, new, c_old, c_new))
        users = {}
        for o in bpy.data.objects:
            if o.instance_type == 'COLLECTION' and o.instance_collection is not None and \
                    o.instance_collection.name.startswith("props.mission.role."):
                users.setdefault(o.instance_collection.name, []).append(o.name)
        self.role_users = users
        self.sink =min(v.co.z for v in obj("mission.depart_steps.steps").data.vertices) > -1e-4
        log("mission: gallery floors to trim %s; role boards %s; depart steps %s" % (
            self.lang_todo, [r[1] for r in self.roles], "to sink" if self.sink else "sunk"))
        self.touched = [f.name for lang, _ in self.langs for f in obj(lang).children
                        if f.type == 'MESH' and ".floor" in f.name[len(lang):]] + ["mission.depart_steps.steps"]
        for i, stt, c, new in self.roles:
            self.touched += [o.name for o in c.all_objects if role_kind(o.name) in ROLE_KINDS[:4]]
        self.todo = bool(self.lang_todo) or any(r[1] == "old" for r in self.roles) or self.sink
        return self.todo

    def apply(self):
        for lang, sx in self.langs:
            if lang in self.lang_todo:
                log("mission: %s: %d floor vertices trimmed to the tower base's / terrace's edges" % (
                    lang, MS.trim_corridor_floor(obj(lang), MS.corridor_cuts(sx, self.terrace_hw), MS.CORRIDOR_W)))
        if self.sink:
            log("mission: depart steps sunk %.2f m (%d vertices)" % (
                MS.STEP_SINK, MS.sink_steps(obj("mission.depart_steps"), MS.STEP_SINK)))
        for i, stt, c, new in self.roles:
            if stt != "old":
                continue
            label, years = MS.ROLE_BOARDS[i]
            tmp = bpy.data.collections.new("~role_tmp")
            MS._role_build(tmp, label, years, self.scale)
            made = {role_kind(o.name): o for o in tmp.all_objects}
            for o in list(c.all_objects):
                k = role_kind(o.name)
                if k is None or k not in made:
                    raise RuntimeError("mission: role prototype %s: unknown object %s" % (c.name, o.name))
                t = made[k]
                me = t.data
                t.data = bpy.data.meshes.new("~empty")
                swap_mesh(o, me)
            for t in list(tmp.all_objects):
                d = t.data
                bpy.data.objects.remove(t, do_unlink=True)
                if d is not None and d.users == 0:
                    bpy.data.meshes.remove(d)
            bpy.data.collections.remove(tmp)
            c.name = new
            c[P._PROTO_TAG] = new[len(P.PREFIX) + 1:]
            log("mission: role board %d rebuilt in place -> %s" % (i, new))

    def check(self, fail, dg):
        for lang, sx in self.langs:
            for (px, py), (dx, dy) in MS.corridor_cuts(sx, self.terrace_hw):
                for f in obj(lang).children:
                    if f.type != 'MESH' or ".floor" not in f.name[len(lang):]:
                        continue
                    for v in f.data.vertices:
                        along = (v.co.x - px) * dx + (v.co.y - py) * dy
                        lat = -(v.co.x - px) * dy + (v.co.y - py) * dx
                        if along > 1e-6 and abs(lat) <= 0.5 * MS.CORRIDOR_W + 0.5:
                            fail.add("mission: %s still runs past its end into a host" % f.name)
                            break
        for i, stt, c, new in self.roles:
            cc = bpy.data.collections.get(new)
            if cc is None:
                fail.add("mission: role board %d has no prototype %s" % (i, new))
                continue
            g = [o for o in cc.all_objects if role_kind(o.name) == "props.role.glyphs"]
            b = [o for o in cc.all_objects if role_kind(o.name) == "props.role.board"]
            if len(g) != 1 or len(b) != 1:
                fail.add("mission: role board %d's prototype has %d glyph and %d board objects" % (i, len(g), len(b)))
                continue
            yf = local_co(b[0])[:, 1].min()
            gmin = local_co(g[0])[:, 1].min()
            if abs((yf - gmin) - MS.ROLE_PROUD) > 0.002:
                fail.add("mission: role board %d's letters stand %.4f m proud, not %.3f" % (i, yf - gmin, MS.ROLE_PROUD))
        # the gallery floor meets the terrace and the tower bases flush
        sc = bpy.context.scene
        root = obj("mission.root")
        W, Wi = root.matrix_world, root.matrix_world.inverted()
        worst = 0.0
        for lang, sx in self.langs:
            for (px, py), _d in MS.corridor_cuts(sx, self.terrace_hw):
                for k in range(-20, 21):
                    x = px + 0.01 * k
                    for dy in (-1.0, 0.0, 1.0):
                        hit, loc, nor, fi, ob, mx = sc.ray_cast(dg, W @ Vector((x, py + dy, MS.TERRACE_H + 2.0)),
                                                                Vector((0, 0, -1)), distance=3.0)
                        if not hit:
                            fail.add("mission: hole at the gallery end (%.2f, %.2f)" % (x, py + dy))
                            continue
                        z = (Wi @ loc).z
                        if abs(z - MS.TERRACE_H) < 0.05:
                            worst = max(worst, abs(z - MS.TERRACE_H))
        if worst > 0.002:
            fail.add("mission: a %.4f m step where the galleries meet the terrace / tower bases" % worst)
        log("mission: galleries meet the terrace and the tower bases flush (worst %.4f m); role boards' decals %.2f m "
            "proud" % (worst, MS.ROLE_PROUD))

    def scan_names(self):
        out = [n for n in self.touched if n.startswith("mission.lang")] + [
            "mission.terrace.body", "mission.drum_tower.base.body", "mission.bell_tower.base.body",
            "mission.depart_steps.steps"]
        out += [u for us in self.role_users.values() for u in us]
        return out

    def targets(self):
        out = []
        for n in self.touched:
            if n.startswith("mission.lang"):
                out += [("mission.terrace.body", n), ("mission.drum_tower.base.body", n),
                        ("mission.bell_tower.base.body", n)]
        return out

    def self_targets(self):
        return [u for us in self.role_users.values() for u in us]

    def cache_names(self):
        return sorted(set(Part.cache_names(self)) | set(self.self_targets()))

    def stairs(self):
        return ["mission.depart_steps"]

    def floats(self):
        return ["mission.depart_steps.steps"]


# -- gate (#27, #42) --------------------------------------------------------------------------------------------------

class Gate(Part):
    name = "gate"
    RIDGE = "gate.stair_ridge"
    SELF_OPP = (RIDGE,)        # its far end cap folded over the ring beside it (opposite faces 1-13 mm apart)

    def plan(self, fail):
        self.weapons = []
        for spec in GT.WEAPONS:
            ob = obj(spec["object"])
            if ob is None or ob.type != 'MESH':
                fail.add("gate: no %s" % spec["object"])
                continue
            carved = GT.PART_ATTR in ob.data.attributes
            self.weapons.append((spec, ob, carved))
        # the ridge: rebuild it from gate._ridge into a scratch collection and compare
        self.new_ridge = self._ridge_mesh()
        have = local_co(obj(self.RIDGE))
        newco = np.array([tuple(v.co) for v in self.new_ridge.vertices])
        self.ridge_new = len(have) == len(newco) and np.abs(have - newco).max() < 1e-4
        log("gate: weapons carved %s; ridge %s" % ([w[2] for w in self.weapons],
                                                   "new" if self.ridge_new else "old (to rebuild)"))
        self.touched = [w[1].name for w in self.weapons] + [self.RIDGE]
        self.todo = not all(w[2] for w in self.weapons) or not self.ridge_new
        return self.todo

    def _ridge_mesh(self):
        root = obj("gate.root")
        from sect import world as W
        want = Matrix.Translation(W.ANCHORS["gate"][:3])
        if any(abs(a - b) > 1e-4 for ra, rb in zip(root.matrix_world, want) for a, b in zip(ra, rb)):
            raise RuntimeError("gate: gate.root is not at the gate's anchor %s" % (W.ANCHORS["gate"][:3],))
        coll = bpy.data.collections.new("~gate_ridge_tmp")
        bpy.context.scene.collection.children.link(coll)
        tmp_root = U.empty("~gate_ridge_root", coll)
        ob = GT._ridge(coll, tmp_root)
        me = ob.data
        ob.data = bpy.data.meshes.new("~empty")
        for o in list(coll.all_objects):
            d = o.data if o.type == 'MESH' else None
            bpy.data.objects.remove(o, do_unlink=True)
            if d is not None and d.users == 0:
                bpy.data.meshes.remove(d)
        bpy.context.scene.collection.children.unlink(coll)
        bpy.data.collections.remove(coll)
        return me

    def apply(self):
        for spec, ob, carved in self.weapons:
            if carved:
                continue
            old = ob.data
            me = GT.weapon_mesh(spec, fresh=True, log=log)
            ob.data = me
            for s in ob.material_slots:
                if s.link != 'DATA':
                    s.link = 'DATA'
            if old is not me and old.users == 0:
                bpy.data.meshes.remove(old)
            log("gate: %s rebuilt with its inlays carved in: %d faces" % (ob.name, len(me.polygons)))
        for m in list(bpy.data.meshes):
            if any(m.name.startswith(GT.K + "." + s["key"] + ".old") for s in GT.WEAPONS) and m.users == 0:
                bpy.data.meshes.remove(m)
        if not self.ridge_new:
            swap_mesh(obj(self.RIDGE), self.new_ridge)
            self.new_ridge = None
            log("gate: stair ridge rebuilt (flat end caps, clear of world.range)")
        sc = bpy.data.scenes.get(P._EVAL_SCENE)
        if sc is not None and sc != bpy.context.scene and not len(sc.objects):
            bpy.data.scenes.remove(sc)

    def cleanup(self):
        if getattr(self, "new_ridge", None) is not None and self.new_ridge.users == 0:
            bpy.data.meshes.remove(self.new_ridge)
            self.new_ridge = None

    def check(self, fail, dg):
        for spec, ob, carved in self.weapons:
            me = ob.data
            n = len(me.polygons)
            lt = np.zeros(n, np.int32)
            me.polygons.foreach_get("loop_total", lt)
            t = int(lt.sum() - 2 * n)
            if t > GT.WEAPON_TRI_BUDGET:
                fail.add("gate: %s has %d triangles > %d" % (ob.name, t, GT.WEAPON_TRI_BUDGET))
            bm = bmesh.new()
            bm.from_mesh(me)
            nm = sum(1 for e in bm.edges if len(e.link_faces) != 2)
            bm.free()
            if nm:
                fail.add("gate: %s has %d non-manifold edges" % (ob.name, nm))
            co = local_co(ob)
            lb = (co.min(0), co.max(0))
            want = (np.array([-GT.WEAPON_HALF, -GT.WEAPON_HALF, 0.0]), np.array([GT.WEAPON_HALF, GT.WEAPON_HALF,
                                                                                GT.WEAPON_TOP]))
            if np.abs(lb[0] - want[0]).max() > 1e-3 or np.abs(lb[1] - want[1]).max() > 1e-3:
                fail.add("gate: %s's local box %s is not the monolith's %s" % (ob.name, lb, want))
            log("gate: %s: %d triangles, closed, local box kept" % (ob.name, t))
        # the ridge: no vertex between RIDGE_SINK under and RIDGE_REACH over the range's top
        ob = obj(self.RIDGE)
        rg = gather(dg, owners=["world.range"], veg=True)["world.range"]
        lo, hi = tris_box(gather(dg, owners=[self.RIDGE], veg=True)[self.RIDGE])
        rg = rg[~((rg.min(1) > hi + 2.0).any(1) | (rg.max(1) < lo - 2.0).any(1))]
        tree = bvh_of(rg)
        W = ob.matrix_world
        near = 0
        for v in ob.data.vertices:
            p = W @ v.co
            h = range_height(tree, p.x, p.y, hi[2] + 100.0)
            if h is not None and h - GT.RIDGE_SINK + 1e-3 < p.z < h + GT.RIDGE_REACH - 1e-3:
                near += 1
        if near:
            fail.add("gate: %d ridge vertices within (-%.2f, %.2f) m of world.range's top" % (
                near, GT.RIDGE_SINK, GT.RIDGE_REACH))
        log("gate: no stair ridge vertex within (-%.2f, %.2f) m of world.range's top" % (GT.RIDGE_SINK,
                                                                                       GT.RIDGE_REACH))

    def scan_names(self):
        return list(self.touched)

    def targets(self):
        # (the ridge's big flank faces still cross the slope where they come out of it: a line, ~0.3 m2 within 5 mm)
        return [("world.range", self.RIDGE, 0.6)]

    def self_targets(self):
        return list(self.touched)


# -- lotus (#16) ------------------------------------------------------------------------------------------------------

class Lotus(Part):
    name = "lotus"
    ROOTS = (("mirror.lotus", MI.WATER_Z, MI.LOTUS_LIFT), ("mirror.lotus.001", MI.WATER_Z, MI.LOTUS_LIFT),
             ("mirror.lotus.002", MI.WATER_Z, MI.LOTUS_LIFT), ("library.lotus", -0.18, LI.LOTUS_LIFT))

    def plan(self, fail):
        self.state = {}
        for nm, wz, lift in self.ROOTS:
            ob = obj(nm)
            if ob is None:
                fail.add("lotus: no %s" % nm)
                continue
            z = ob.location.z
            self.state[nm] = "new" if abs(z - (wz + lift)) < 1e-5 else ("old" if abs(z - wz) < 1e-5 else None)
            if self.state[nm] is None:
                fail.add("lotus: %s at z %.4f, neither %.3f nor %.3f" % (nm, z, wz, wz + lift))
        log("lotus:", self.state)
        self.touched = [nm for nm, *_ in self.ROOTS]
        self.todo = "old" in self.state.values()
        return self.todo

    def apply(self):
        for nm, wz, lift in self.ROOTS:
            if self.state.get(nm) == "old":
                obj(nm).location.z = wz + lift

    def pads(self):
        return [o.name for nm, *_ in self.ROOTS for o in obj(nm).children if ".pad" in o.name]

    def check(self, fail, dg):
        low = {}
        for inst in dg.object_instances:
            if inst.object.type != 'MESH':
                continue
            own = owner_of(inst)
            if ".pad" not in own:
                continue
            area = own.split(".")[0]
            M = np.array(inst.matrix_world)
            co = local_co(inst.object.original) @ M[:3, :3].T + M[:3, 3]
            low[area] = min(low.get(area, 1e9), float(co[:, 2].min()))
        for area, pond in (("mirror", "mirror.pond.water"), ("library", "library.pond.water")):
            wz = float(np.max(local_co(obj(pond)) @ np.array(obj(pond).matrix_world)[:3, :3].T +
                              np.array(obj(pond).matrix_world)[:3, 3], 0)[2])
            gap = low.get(area, 1e9) - wz
            if gap < 0.03:
                fail.add("lotus: %s's lowest pad point is %.4f m over the water (want >= 0.03)" % (area, gap))
            log("lotus: %s's pads at least %.4f m over the water" % (area, gap))

    def scan_names(self):
        return ["mirror.pond.water", "library.pond.water"]     # (the pads are their neighbours)

    def targets(self):
        return [(p, ("mirror" if p.startswith("mirror") else "library") + ".pond.water") for p in self.pads()]


# -- steps (#14) ------------------------------------------------------------------------------------------------------

STEPS = (("mirror.arrival_steps", MI.sink_steps, MI.STEP_SINK, True),
         ("mirror.depart_steps", MI.sink_steps, MI.STEP_SINK, True),
         ("library.arrival_steps", LI.sink_steps, LI.ARRIVAL_TOP - LI.TERRACE_Z + LI.STEP_SINK, False),
         ("library.depart_steps", LI.sink_steps, LI.STEP_SINK, False),
         ("formation.arrival_steps", FO.sink_steps, FO.STEP_SINK, False))


class Steps(Part):
    name = "steps"

    def plan(self, fail):
        self.state, self.co0 = {}, {}
        for nm, fn, depth, plinth in STEPS:
            me = obj(nm + ".steps").data
            if me.users != 1:
                fail.add("steps: %s's mesh is shared" % nm)
            zmin = min(v.co.z for v in me.vertices)
            sunk = abs(zmin + depth) < 1e-4
            if not sunk and abs(zmin) > 1e-4:
                fail.add("steps: %s's block reaches %.4f, neither 0 nor %.4f" % (nm, zmin, -depth))
            self.state[nm] = (sunk, bool(me.get("drum_plinths")))
            self.co0[nm] = local_co(obj(nm + ".steps")).copy()
        # the library's arrival landing runs to its steps' foot (it stopped 1 cm short: a crack to the terrace)
        y1 = local_co(obj(self.LANDING))[:, 1].max()
        self.landing = "new" if abs(y1 - LI.ARRIVAL_LANDING_Y1) < 1e-4 else (
            "old" if abs(y1 - LI.ARRIVAL_LANDING_Y1_OLD) < 1e-4 else None)
        if self.landing is None:
            fail.add("steps: %s ends at y %.4f, neither %.3f nor %.3f" % (self.LANDING, y1, LI.ARRIVAL_LANDING_Y1_OLD,
                                                                        LI.ARRIVAL_LANDING_Y1))
        log("steps: (sunk, plinths):", self.state, "; library arrival landing", self.landing)
        self.touched = [nm + ".steps" for nm, *_ in STEPS] + [self.LANDING]
        self.todo = any(not self.state[nm][0] or (plinth and not self.state[nm][1]) for nm, fn, depth, plinth in STEPS) \
            or self.landing == "old"
        return self.todo

    LANDING = "library.arrival_landing"

    def apply(self):
        for nm, fn, depth, plinth in STEPS:
            st = obj(nm)
            n = fn(st, depth)
            p = MI.drum_plinths(st) if plinth else 0
            log("steps: %s: %d bottom vertices sunk %.2f m%s" % (nm, n, depth, ", %d drum plinths" % p if p else ""))
        if self.landing == "old":
            ob = obj(self.LANDING)
            co = local_co(ob)
            co[np.abs(co[:, 1] - LI.ARRIVAL_LANDING_Y1_OLD) < 1e-4, 1] = LI.ARRIVAL_LANDING_Y1
            set_co(ob, co)
            log("steps: %s now runs to y %.3f, the arrival steps' foot" % (self.LANDING, LI.ARRIVAL_LANDING_Y1))

    def check(self, fail, dg):
        for nm, fn, depth, plinth in STEPS:
            co = local_co(obj(nm + ".steps"))
            me = obj(nm + ".steps").data
            if abs(co[:, 2].min() + depth) > 1e-4:
                fail.add("steps: %s's block reaches %.4f, not %.4f" % (nm, co[:, 2].min(), -depth))
            if plinth and int(me.get("drum_plinths", 0)) == 0:
                fail.add("steps: %s has no drum plinths" % nm)
            # the flight's own vertices come first (the plinths are appended): over 5 cm they did not move, under it
            # only straight down
            c0 = self.co0[nm]
            n0 = len(c0) - (8 * int(me.get("drum_plinths", 0)) if self.state[nm][1] else 0)
            c0, c1 = c0[:n0], co[:n0]
            hi = c0[:, 2] >= 0.05
            if np.abs(c1[hi] - c0[hi]).max() > 1e-6 or np.abs(c1[~hi, :2] - c0[~hi, :2]).max() > 1e-6:
                fail.add("steps: %s's treads or footprint moved" % nm)
        log("steps: treads unchanged; blocks reach their sink depth; mirror drum plinths in place")

    def floats(self):
        out = [nm + ".steps" for nm, *_ in STEPS]
        for nm, fn, depth, plinth in STEPS:
            if plinth:
                out += [c.name for b in obj(nm).children for c in b.children if c.name.endswith((".drums", ".posts",
                                                                                                ".panels"))]
        return out

    def stairs(self):
        return [nm for nm, *_ in STEPS]

    def scan_names(self):
        return [nm + ".steps" for nm, *_ in STEPS]

    def cache_names(self):
        return sorted(set(Part.cache_names(self)) | {c.name for nm, *_ in STEPS for c in obj(nm).children_recursive})


# -- ribbon (#37) -----------------------------------------------------------------------------------------------------

def ribbon_geo_with(thick, rx, ry):
    keep = (AB.RIBBON_T, AB._RIB_X, AB._RIB_Y)
    AB.RIBBON_T, AB._RIB_X, AB._RIB_Y = thick, rx, ry
    try:
        root = obj("abode.root")
        pav_loc, verts, edges, _ob = AB.ribbon_ridge(root)
        silk, bells, info = AB.ribbon_geo(pav_loc, verts, edges)
        k = info["knot"]
        silk.verts = [AB._dsub(p, k) for p in silk.verts]
        bells.verts = [AB._dsub(p, k) for p in bells.verts]
        return silk, bells
    finally:
        AB.RIBBON_T, AB._RIB_X, AB._RIB_Y = keep


class Ribbon(Part):
    name = "ribbon"
    SILK = AB.RIBBON_SILK
    SELF_OPP = (SILK,)         # its tails' front and back 2-12 mm apart at their thin edges

    def plan(self, fail):
        ob = obj(self.SILK)
        have = local_co(ob)
        new, _b = ribbon_geo_with(AB.RIBBON_T, AB._RIB_X, AB._RIB_Y)
        old, _b2 = ribbon_geo_with(AB.RIBBON_T_OLD, AB._RIB_X_OLD, AB._RIB_Y_OLD)
        self.geo = new
        if same_points(have, np.array(new.verts), 1e-4):
            self.state = "new"
        elif same_points(have, np.array(old.verts), 1e-4):
            self.state = "old"
        else:
            self.state = None
            fail.add("ribbon: %s is neither the old nor the new silk (%d vertices; old %d, new %d)" % (
                self.SILK, len(have), len(old.verts), len(new.verts)))
        log("ribbon: silk %s" % self.state)
        self.touched = [self.SILK]
        self.todo = self.state == "old"
        return self.todo

    def apply(self):
        roles = dict(AB.RIBBON_PARTS)[self.SILK]
        me = AB._duet_mesh(self.SILK + "~new", self.geo, roles)
        swap_mesh(obj(self.SILK), me)
        log("ribbon: silk rebuilt: %d vertices, %d faces, %.3f m thick" % (len(me.vertices), len(me.polygons),
                                                                         AB.RIBBON_T))

    def check(self, fail, dg):
        me = obj(self.SILK).data
        bm = bmesh.new()
        bm.from_mesh(me)
        nm = sum(1 for e in bm.edges if len(e.link_faces) != 2)
        bm.free()
        n = len(me.polygons)
        lt = np.zeros(n, np.int32)
        me.polygons.foreach_get("loop_total", lt)
        t = int(lt.sum() - 2 * n)
        if nm:
            fail.add("ribbon: the silk has %d open edges" % nm)
        if t > AB.RIBBON_TRI_CAP:
            fail.add("ribbon: the silk has %d triangles > %d" % (t, AB.RIBBON_TRI_CAP))
        log("ribbon: silk closed, %d triangles" % t)

    def self_targets(self):
        return [self.SILK]


# ------------------------------------------------------------------------------------------------------------- main

def digest(names):
    h = hashlib.md5()
    for n in sorted(set(names)):
        ob = obj(n)
        if ob is None:
            h.update(("gone:" + n).encode())
            continue
        h.update(n.encode())
        h.update(np.round(np.array(ob.matrix_basis), 6).tobytes())
        if ob.type == 'MESH':
            me = ob.data
            h.update(np.round(local_co(ob), 5).tobytes())
            lv = np.empty(len(me.loops), np.int32)
            me.loops.foreach_get("vertex_index", lv)
            h.update(lv.tobytes())
            mi = np.empty(len(me.polygons), np.int32)
            me.polygons.foreach_get("material_index", mi)
            h.update(mi.tobytes())
    return h.hexdigest()


def owners_boxes(dg, names):
    return {k: tris_box(v) for k, v in gather(dg, owners=names, veg=True).items()}


def main():
    dry, parts, do_scan = options()
    t0 = time.time()
    fail = Fail()
    sc = bpy.context.scene
    keep_frame = sc.frame_current
    lib = {"inscription": Inscription, "scroll": Scroll, "lawns": Lawns, "libpaths": LibPaths, "steles": Steles,
           "cave": Cave, "forge": Forge, "arena": Arena, "mission": Mission, "gate": Gate, "lotus": Lotus,
           "steps": Steps, "ribbon": Ribbon}
    P_ = [lib[p]() for p in parts]
    todo = {}
    for p in P_:
        todo[p.name] = p.plan(fail)
    if fail:
        for p in P_:
            if hasattr(p, "cleanup"):
                p.cleanup()
        log("NOT SAVED: the file is not in a state this patch knows (%d problems)" % len(fail))
        raise SystemExit(1)
    if not any(todo.values()):
        log("every part unchanged:", ", ".join(p.name for p in P_))
    dg = bpy.context.evaluated_depsgraph_get()
    n_obj0 = len(bpy.data.objects)
    touched = sorted({n for p in P_ for n in p.touched})
    box0 = owners_boxes(dg, sorted({n for p in P_ for n in p.cache_names()}))
    for p in P_:
        if todo[p.name] and hasattr(p, "before"):
            p.before(dg)
    scan0 = {}
    if do_scan:
        for p in P_:
            names = [n for n in p.scan_names() + (p.self_targets() if hasattr(p, "self_targets") else [])
                     if obj(n) is not None]
            if todo[p.name] and names:
                scan0[p.name] = Scan("before " + p.name).run(sorted(set(names)), dg)
    floats0 = {}
    for p in P_:
        if todo[p.name] and p.floats():
            floats0[p.name] = footing(dg, [n for n in p.floats() if obj(n) is not None])
    for p in P_:
        if todo[p.name]:
            p.apply()
        if hasattr(p, "cleanup"):
            p.cleanup()
    bpy.context.view_layer.update()
    sc.frame_set(keep_frame)
    dg = bpy.context.evaluated_depsgraph_get()
    summary = []
    for p in P_:
        p.check(fail, dg)
        # footing of the touched pieces and what stands on them
        if p.floats():
            fl = footing(dg, [n for n in p.floats() if obj(n) is not None])
            for k, (worst, over, tot, rest) in sorted(fl.items()):
                was = floats0.get(p.name, {}).get(k)
                log("%s: footing %s: worst air %.3f m, %.3f of %.2f m2 over %.0f cm, on %s%s" % (
                    p.name, k, worst, over, tot, FLOAT_MAX * 100, rest,
                    "" if was is None else " (was worst %.3f, %.3f m2 over)" % (was[0], was[1])))
                if over > 0.005 and worst > FLOAT_MAX:
                    fail.add("%s: %s floats: %.3f m2 more than %.0f cm over what is under it (worst %.3f m)" % (
                        p.name, k, over, FLOAT_MAX * 100, worst))
        for st in p.stairs():
            worst, top, foot, miss = stair_walk(obj(st), dg)
            log("%s: walk %s: worst step %.3f m, top landing %s, foot floor %s, %d misses" % (
                p.name, st, worst, None if top is None else tuple(round(x, 3) for x in top),
                None if foot is None else tuple(round(x, 3) for x in foot), miss))
            off = [abs(v) for r in (top, foot) if r is not None for v in r]
            if worst > RISER_MAX or miss or (off and max(off) > FLOOR_TOL):
                fail.add("%s: %s is not walkable: worst step %.3f m, floors past its ends %s / %s, %d rays met "
                         "nothing" % (p.name, st, worst, top, foot, miss))
        if todo[p.name] and do_scan and p.name in scan0:
            names = [n for n in p.scan_names() + (p.self_targets() if hasattr(p, "self_targets") else [])
                     if obj(n) is not None]
            s1 = Scan("after " + p.name).run(sorted(set(names)), dg)
            s0 = scan0[p.name]
            tot = [sum(s.same(k, band=b) for k in s.rows) for s in (s0, s1) for b in (0, 3)] + \
                [sum(s.exposed(k, band=b) for k in s.rows) for s in (s0, s1) for b in (0, 3)]
            log("%s: same-facing overlap of the scanned pieces: within 5 mm %.2f m2 (exposed %.2f) -> %.2f (%.2f); "
                "5-12 mm %.2f (%.2f) -> %.2f (%.2f)" % (p.name, tot[0], tot[4], tot[2], tot[6], tot[1], tot[5],
                                                        tot[3], tot[7]))
            summary.append((p.name,) + tuple(tot))
            for t_ in p.targets():
                a_, b_ = t_[:2]
                lim = t_[2] if len(t_) > 2 else TARGET_MAX
                was, now = s0.pair(a_, b_), s1.pair(a_, b_)
                was12, now12 = s0.pair(a_, b_, 3), s1.pair(a_, b_, 3)
                if was + was12 >= 0.01 or now + now12 >= 0.01:
                    log("%s: target %s / %s: within 5 mm %.2f -> %.2f m2, 5-12 mm %.2f -> %.2f m2" % (
                        p.name, a_, b_, was, now, was12, now12))
                if now > lim or now12 > lim:
                    fail.add("%s: %s / %s still overlap (same-facing): %.2f + %.2f m2 (was %.2f + %.2f)" % (
                        p.name, a_, b_, now, now12, was, was12))
            for a_ in (p.self_targets() if hasattr(p, "self_targets") else []):
                r0 = s0.rows.get(a_, {}).get("<self>", [0.0] * 6)
                r1 = s1.rows.get(a_, {}).get("<self>", [0.0] * 6)
                log("%s: self %s: same-facing %.2f -> %.2f m2 within 5 mm, %.2f -> %.2f at 5-12 mm (exposed %.2f + %.2f "
                    "-> %.2f + %.2f); opposite %.2f + %.2f -> %.2f + %.2f" % (
                        p.name, a_, r0[0], r1[0], r0[3], r1[3], r0[2], r0[5], r1[2], r1[5], r0[1], r0[4], r1[1], r1[4]))
                if r1[0] + r1[3] > max(TARGET_MAX, 0.2 * (r0[0] + r0[3])) and r1[0] + r1[3] > 0.02:
                    fail.add("%s: %s still overlaps itself: %.2f + %.2f m2 (was %.2f + %.2f)" % (
                        p.name, a_, r1[0], r1[3], r0[0], r0[3]))
                if a_ in getattr(p, "SELF_OPP", ()) and r1[1] + r1[4] > TARGET_MAX:
                    fail.add("%s: %s still folds over itself: %.2f m2 opposite-facing within 12 mm (was %.2f)" % (
                        p.name, a_, r1[1] + r1[4], r0[1] + r0[4]))
            for pk, rows in s1.rows.items():
                for o, r in rows.items():
                    w = [max(a, b) for a, b in zip(s0.rows.get(pk, {}).get(o, [0.0] * 6),
                                                   s0.rows.get(o, {}).get(pk, [0.0] * 6))]   # the pair, either side
                    # (both bands together: a pair whose gap sits near 5.5 mm moves between them with the sampling)
                    if r[0] + r[3] > w[0] + w[3] + max(NEW_MAX, 0.15 * (w[0] + w[3])):
                        fail.add("%s: new same-facing overlap %s / %s: %.2f + %.2f m2 (was %.2f + %.2f)" % (
                            p.name, pk, o, r[0], r[3], w[0], w[3]))
    # names and counts
    n_obj1 = len(bpy.data.objects)
    want_delta = sum(p.delta for p in P_)
    if n_obj1 - n_obj0 != want_delta:
        fail.add("names: objects %d -> %d, expected %+d" % (n_obj0, n_obj1, want_delta))
    clash = [o.name for o in bpy.data.objects if "~" in o.name]
    if clash:
        fail.add("names: scratch objects left: %s" % clash[:8])
    for n in touched:
        if obj(n) is None and not any(n in p.removed for p in P_):
            fail.add("names: %s vanished" % n)
    log("objects %d -> %d (expected %+d)" % (n_obj0, n_obj1, want_delta))
    # caches
    box1 = owners_boxes(dg, list(box0))
    stale, removed, chunks = [], [], set()
    for k, b in box0.items():
        nb = box1.get(k)
        if nb is None:
            removed.append(k)
            continue
        if (np.asarray(nb[0]) < np.asarray(b[0]) - BOX_TOL).any() or (np.asarray(nb[1]) > np.asarray(b[1]) +
                                                                       BOX_TOL).any():
            stale.append(k)
    for p in P_:
        if todo[p.name]:
            chunks |= {area_of(n) for n in p.touched if obj(n) is not None or n in p.removed}
    new_names = [k for k in box1 if k not in box0]
    log("DIGEST", digest(sorted({n for p in P_ for n in p.digest_names()})))
    log("SUMMARY same-facing overlap of the scanned pieces, within 5 mm and 5-12 mm, before -> after (exposed in "
        "brackets):", "; ".join("%s %.1f (%.1f) + %.1f (%.1f) -> %.1f (%.1f) + %.1f (%.1f)" % (
            s[0], s[1], s[5], s[2], s[6], s[3], s[7], s[4], s[8]) for s in summary) or "not scanned")
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail:
            log("  -", f)
        raise SystemExit(1)
    chunks.discard("")
    if stale or new_names:
        log("CACHES needs audit: %d boxes grew %s, new %s (removed, ignored by the caches: %s) - run export_web.py -- "
            "audit --profile full, then chunks,meta, then bake_web.py bakefull for %s and the backdrop, then "
            "tools/sect_pack.py" % (len(stale), stale[:40], new_names, removed, ",".join(sorted(chunks))))
    else:
        log("CACHES ok: names kept (removed: %s) and every box within %.0f cm of its old one%s" % (
            removed, BOX_TOL * 100, "; re-bake %s and the backdrop, then pack" % ",".join(sorted(chunks))
            if chunks else "; nothing changed"))
    if not any(todo.values()):
        log("nothing changed: not saving (%.1f s)" % (time.time() - t0))
        return
    if dry:
        log("DRY_RUN: checks passed, not saving (%.1f s)" % (time.time() - t0))
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "(%.1f s)" % (time.time() - t0))


if __name__ == "__main__":
    main()
