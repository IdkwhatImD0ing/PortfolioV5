"""Round 11, lane 'areas': three geometry fixes from the stairs / flicker diagnosis (items 5, 6 and 7), brought into an
existing out/sect_chase.blend so it matches what a fresh build of the current source makes. Run on the cloud box, on a
copy first:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r11_areas.py [-- DRY_RUN=1] [PARTS=ramps,mirror]

Why (owner, 2026-10-22): "Some of the stairs still flicker/have some weird textures/shadows, the fence at the mirror
pool only goes across half the mountain?" Every baked material renders double-sided on the web, so two surfaces a few
mm apart z-fight once the camera is far enough away (24-bit depth, near 0.5 m: 4 mm fights beyond ~180 m).

Parts (PARTS=..., default all four; each is idempotent and reports 'unchanged' when the file already has it):
- ramps      (item 5) every carved yubu ramp body ('<stairs>.ramp_body', 21 in the sect: the gate's 12 grand-stair
             flights, the mirror dais, mission hall and terrace, library pagoda, steles terrace, scroll pavilion, forge
             hall and the summit's two tiers). Its top lay 1.5 cm over the nosing line, 5 mm under the flat parts of
             the carved relief ('<stairs>.ramp'), and the two z-fought beyond ~180 m. The top now runs 2 cm under the
             nosing line (arch.RAMP_BODY_TOP), at least 4 cm under the relief: the patch lowers the body's top
             vertices by 3.5 cm (same object, mesh and vertex order). The bodies were also inside out (stairs() never
             recalculated their normals; the bake shades a face from its normal side): the patch turns them right side
             out, as stairs() now does. The steps, stringers and relief are untouched.
- summit     (item 6) the trigram ring's dark groove sheet ('summit.ring.groove', stone_dark, 1916 quads) lay 3 mm over
             the terrace paving over ~350 m2. The groove is removed and the terrace ('summit.terrace', same object)
             gets its mesh from summit._terrace_bm: one ring of its own top faces under the rune band is dark stone
             (summit.CHANNEL_R, third material slot stone_dark), so the rune ring (8 mm up) lies over one surface.
             The same mesh has no top under the abode stair's last tread (summit._arrival_cut, |x| < 2.5 m, y < -38.5):
             the tread lay flat on the paving there (2.3 m2, 0 mm), z-fought and baked a dark band across it.
- formation  (item 6) the white axis strip ('formation.axis_walk', '.001') lay 4 mm over the bluestone floor and the
             ink bands over ~270 m2. The floor and the bands ('formation.floor', 'formation.floor_band', same objects)
             get their meshes from formation._floor_bm / _floor_band_bm, which cut them away under the strip, and the
             strips get formation._axis_walk_geom: flush at z 0, their outer end on the floor's 192-gon edge, so the
             strip fills the hole exactly.
- mirror     (item 7) areas/mirror.py built the rim rail only from -135 to 45 deg (RIM_ARC), half the circle: the
             north and west rim had no rail and the flat terrace runs out to an open drop there. The rail now runs
             right round (mirror.rim_spans), open only where the two connector stairs cross it (6 m). The flat terrace
             follows world.py's 2.5 m terrain grid and comes in to 50.8 m east and north-east of the centre, where
             the half rail's feet hung up to 0.4 m over the lip, so the rail steps in from r 52 to r 50.5 over -20..56
             deg (mirror.rim_radius). On the depart side the south-east span stops against the south wall of the forge
             stair's foot landing (mirror._foot_wall_end): run on to the 6 m opening's edge it crossed that wall and
             stood 3 m of rail on the landing (the half rail ran through the gate's south column there). The half
             rail's three spans ('mirror.rim_rail', '.001', '.002') are removed with their point clouds and the ring
             is built with arch.balustrade (the same prototypes) as two spans: north / west 'mirror.rim_rail' (18.3 ->
             261.2 deg, 179 posts) and south-east 'mirror.rim_rail.001' (-92.2 -> 8.4 deg).

Checks (any failure stops the patch before saving; DRY_RUN=1 runs everything and never saves):
- coplanar-overlap scan, before and after, of every rebuilt piece against the ground and everything near it:
  samples every SCAN_STEP m on the piece's faces and looks along the face normal for a parallel face of another
  object within SCAN_TOL (5 mm); logs the area per neighbour, same-facing (fights on the web) and opposite-facing
  (contact under a solid, hidden). After the patch the overlaps a part removes must be gone (SCAN_TARGET_MAX) and no
  rebuilt piece may gain same-facing overlap with anything (SCAN_NEW_MAX); what is left (another lane's, or older)
  is logged;
- ramps: the body's top lies 4 cm or more under the relief everywhere, its bottom stays on the ground;
- summit: the terrace's top is one surface at z 0 from r 22 to 38.9 (no hole, no step) except under the abode stair's
  last tread, where it is gone and the tread covers the whole cut at z 0; the whole rune band (both border rings) lies
  on dark stone, nothing else of the terrace is dark;
- formation: inside the floor (r 10.5..46) every point has at most one floor surface (floor, band or strip), exactly
  one outside the recessed jade channel ring, all at z 0; the walk on the axis from each apron to the dais foot is
  flush (no step over 2 mm);
- mirror: no post or panel foot hangs over air (its buried bottom stays in world.range over its whole footprint;
  the half rail's are logged for comparison); the two spans and two openings close the circle, the arrival opening's
  chord is RIM_GAP (+-5 cm), the north / west span starts RIM_GAP / 2 from where the forge stair crosses the rail,
  the south-east span's end post stands against that stair's foot-landing wall and no post stands on the landing;
  at each opening, level rays along the connector stair (centre and +-2.3 m, 0.35 and
  0.9 m up) meet no rail; the ring cuts into nothing the half rail did not (both meet the same stair walls at the
  openings); no prototype or node group was duplicated;
- names: no '.001' clash (every rebuilt or new object has its expected name), the object count changes by exactly
  what the parts remove and add.

Caches: ramps, summit and formation keep every name and keep each world box within 1 cm of its old one (the groove's
rows are simply ignored), so on their own they print 'PATCH CACHES ok' and only the bake re-runs. The mirror ring is a
new set of instances under the half rail's names ('mirror.rim_rail.posts|...|0.0.<i>' meant the old spans' posts), so
with it the patch prints 'PATCH CACHES needs audit': run the export_web audit, then chunks,meta, then bakefull the
touched chunks (the log lists them, and the backdrop), then the pack. A re-run over its own output prints
'unchanged' for every part, 'PATCH CACHES ok' and does not save.

Options after "--": DRY_RUN=1, PARTS=ramps,summit,formation,mirror.
"""
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

from sect.areas import formation as FO  # noqa: E402
from sect.areas import mirror as MI  # noqa: E402
from sect.areas import summit as SU  # noqa: E402
from sect.lib import arch as A  # noqa: E402
from sect.lib import util as U  # noqa: E402

PARTS_ALL = ("ramps", "summit", "formation", "mirror")
SCAN_TOL = 0.0055          # m: parallel faces within 5 mm (5.5 so a 5.0 mm pair counts despite float noise)
SCAN_STEP = 0.1            # m: sample spacing on the scanned faces (coarser on very large pieces, see scan())
SCAN_MAX_SAMPLES = 400000
SCAN_PAR = 0.985           # |cos| between two faces counted as parallel (~10 deg)
SCAN_NEW_MAX = 0.5         # m2: a rebuilt piece may not gain more same-facing overlap than this with any neighbour
SCAN_TARGET_MAX = 0.05     # m2: what may be left (either facing) of the overlaps each part removes
BOX_TOL = 0.01             # m: a box within this of its old one keeps the export caches valid
RAMP_RE = re.compile(r"\.ramp_body$")
RAMP_COUNT = 21
RAMP_MIN_GAP = 0.039       # m: relief over the lowered body, at least (the relief's lowest point is nosing + 0.02)
SUMMIT_OLD_FACES = 1536
FORMATION_OLD = {"formation.floor": 1920, "formation.floor_band": 396}
STRIP_OLD_Z = 0.004
MIRROR_SPANS = ("mirror.rim_rail", "mirror.rim_rail.001")      # build order: north / west, then south-east
MIRROR_OLD = ("mirror.rim_rail", "mirror.rim_rail.001", "mirror.rim_rail.002")   # the half rail's three spans
MIRROR_OLD_POSTS = {"mirror.rim_rail": 29, "mirror.rim_rail.001": 77, "mirror.rim_rail.002": 21}
POST_PROTO, PANEL_PROTO = "arch.p.post.1220.marble_white", "arch.p.panel.860.marble_white"
TERRACE_Z = -0.4
POST_HALF, POST_SINK = 0.5 * 0.17 * 1.22, 0.05      # arch._p_post(1.22): shaft 0.207 m square, foot 5 cm in the ground
SILL_HALF, SILL_SINK = 0.5 * 0.13 * 0.86 * 1.15, 0.04   # arch._p_panel(0.86): sill 0.129 m thick, 4 cm in the ground
EXPOSE_MAX = 0.02          # m: air allowed under the edge of a post's or a panel's foot (2 cm: world.py's round-11
                           # sink under the link stairs may lower the ground by up to 5 cm right beside the openings)
GAP_TOL = 0.05             # m: the openings' chord may differ this much from mirror.RIM_GAP
FOOT_WALL_ALONG = (0.3, 4.7)   # m along the forge stair from its depart point: where the south-east span's end post
                               # may meet the foot landing's south wall (world.py: REVEAL .. FOOT_FLAT - REVEAL, 0.02..4.98)
FOOT_LANDING_IN = (0.15, 4.85, 5.45)   # the foot landing (world.py: FOOT_FLAT 5 m along, 5.6 m either side) less a
                               # post's half width: no rail post may stand inside it
MIRROR_SOFT = ("grass", "flower", "clover", "moss", "fern", "shrub", "reed", "petal", "lawn", "ground")


def log(*a):
    print("PATCH", *a, flush=True)


def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    dry, parts = False, list(PARTS_ALL)
    for a in argv:
        k, eq, v = a.partition("=")
        if k == "DRY_RUN" and eq:
            dry = v.strip().lower() not in ("", "0", "false", "no")
        elif k == "PARTS" and eq:
            parts = [p.strip() for p in v.split(",") if p.strip()]
            bad = [p for p in parts if p not in PARTS_ALL]
            if bad:
                raise SystemExit("patch_r11_areas: unknown parts %s (known: %s)" % (bad, ",".join(PARTS_ALL)))
        else:
            raise SystemExit("patch_r11_areas: unknown option %r (DRY_RUN=1, PARTS=%s)" % (a, ",".join(PARTS_ALL)))
    return dry, parts


class Fail(list):
    def add(self, msg):
        log("FAIL", msg)
        self.append(msg)


# ---------------------------------------------------------------------------------------------------- geometry utils

def mesh_tris(me, M=None):
    """(n, 3, 3) triangles of mesh ``me`` (numpy), under matrix M (4x4 numpy) when given."""
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
    if M is not None:
        co = co @ M[:3, :3].T + M[:3, 3]
    tv = np.empty(nt * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", tv)
    return co[tv.reshape(nt, 3)]


def owner_of(inst):
    return inst.parent.original.name if inst.is_instance and inst.parent else inst.object.original.name


def hidden(inst):
    o = inst.parent.original if inst.is_instance and inst.parent else inst.object.original
    return bool(o.hide_render)


def gather(dg, owners=None, boxes=None, skip=(), pad=0.05):
    """{owner: (n, 3, 3) world triangles} as rendered, in one pass over the depsgraph's instances (an instancer's
    instances count as the instancer). owners: only these owners, every triangle; boxes: [(min, max)], only the
    triangles touching one of them (+pad), of every owner but ``skip``."""
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


def world_tris(names, dg):
    return gather(dg, owners=names)


def tris_box(T):
    return T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)


def in_box(T, box, pad):
    lo, hi = np.asarray(box[0]) - pad, np.asarray(box[1]) + pad
    tmin, tmax = T.min(1), T.max(1)
    return T[~((tmin > hi).any(1) | (tmax < lo).any(1))]


def bvh_of(T):
    n = len(T)
    verts = [Vector(p) for p in T.reshape(-1, 3)]
    return BVHTree.FromPolygons(verts, [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(n)], all_triangles=True)


def scan(label, names, dg, tol=SCAN_TOL):
    """Coplanar-overlap scan of the pieces ``names`` (owners) against everything rendered near each of them (the other
    pieces included). Returns {piece: {neighbour: [same_m2, opp_m2]}} and logs it."""
    t0 = time.time()
    pieces = world_tris(names, dg)
    pboxes = {k: tris_box(v) for k, v in pieces.items()}
    near = gather(dg, boxes=list(pboxes.values()), pad=2 * tol)
    area_all = sum(float(np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1).sum()) * 0.5
                   for T in pieces.values())
    step = max(SCAN_STEP, math.sqrt(area_all / SCAN_MAX_SAMPLES)) if area_all > 0 else SCAN_STEP
    rnd = np.random.default_rng(11)
    res, nsamp = {}, 0
    for pk, T in pieces.items():
        rows = {}
        res[pk] = rows
        others = {}
        for o, TT in near.items():
            if o == pk:
                continue
            TT = in_box(TT, pboxes[pk], 2 * tol)
            if len(TT):
                others[o] = TT
        if not others:
            continue
        e1, e2 = T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
        cr = np.cross(e1, e2)
        ar = np.linalg.norm(cr, axis=1) * 0.5
        ok = ar > 1e-8
        T, e1, e2, cr, ar = T[ok], e1[ok], e2[ok], cr[ok], ar[ok]
        nrm = cr / (2.0 * ar[:, None])
        k = np.maximum(1, np.round(ar / (step * step))).astype(int)
        tmin, tmax = T.min(1) - tol, T.max(1) + tol
        idx = np.repeat(np.arange(len(T)), k)
        u, v = rnd.random(len(idx)), rnd.random(len(idx))
        flip = u + v > 1.0
        u[flip], v[flip] = 1.0 - u[flip], 1.0 - v[flip]
        P = T[idx, 0] + e1[idx] * u[:, None] + e2[idx] * v[:, None]
        Nn = nrm[idx]
        W = (ar / k)[idx]
        nsamp += len(idx)
        for o, TT in others.items():
            lo, hi = tris_box(TT)
            hitmask = ~((tmin > hi).any(1) | (tmax < lo).any(1))
            sel = np.nonzero(hitmask[idx])[0]
            if not len(sel):
                continue
            tree = bvh_of(TT)
            same = opp = 0.0
            for s in sel:
                p, n = Vector(P[s]), Vector(Nn[s])
                loc, hn, fi, d = tree.ray_cast(p + n * (1.2 * tol), -n, 2.4 * tol)
                if loc is None:
                    continue
                c = hn.dot(n)
                if abs(c) < SCAN_PAR or abs((loc - p).dot(n)) > tol:
                    continue
                if c > 0:
                    same += W[s]
                else:
                    opp += W[s]
            if same > 0 or opp > 0:
                rows[o] = [same, opp]
    for pk, rows in res.items():
        tot_s = sum(r[0] for r in rows.values())
        tot_o = sum(r[1] for r in rows.values())
        top = sorted(rows.items(), key=lambda kv: -(kv[1][0] + 0.01 * kv[1][1]))[:6]
        log("scan %s %s: same-facing %.1f m2, opposite (contact) %.1f m2%s" % (
            label, pk, tot_s, tot_o, "".join("; %s %.1f/%.1f" % (o, s, q) for o, (s, q) in top if s + q >= 0.05)))
    log("scan %s: %d pieces, %d samples (%.2f m apart), %.1f s" % (label, len(pieces), nsamp, step, time.time() - t0))
    return res, {k: v for k, v in pboxes.items()}


def same_total(res):
    return sum(r[0] for rows in res.values() for r in rows.values())


def box_inside(new, old, tol=BOX_TOL):
    return bool((np.asarray(new[0]) >= np.asarray(old[0]) - tol).all() and
                (np.asarray(new[1]) <= np.asarray(old[1]) + tol).all())


def remove_tree(ob):
    """Remove ``ob`` and everything under it, and their meshes when nothing else uses them. Returns names."""
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


def local_co(ob):
    n = len(ob.data.vertices)
    co = np.empty(n * 3)
    ob.data.vertices.foreach_get("co", co)
    return co.reshape(n, 3)


def signed_volume(ob):
    """Signed volume of a closed mesh: positive when its faces point outward."""
    T = mesh_tris(ob.data)
    return float(np.einsum("ij,ij->i", T[:, 0], np.cross(T[:, 1], T[:, 2])).sum() / 6.0)


def bm_co(bm):
    return np.array([tuple(v.co) for v in bm.verts])


def same_points(a, b, tol=1e-4):
    if a.shape != b.shape:
        return False
    ka = np.lexsort(np.round(a / tol).T[::-1])
    kb = np.lexsort(np.round(b / tol).T[::-1])
    return bool(np.abs(a[ka] - b[kb]).max() <= 2 * tol) if len(a) else True


def write_bm(me, bm, smooth):
    """Replace mesh ``me``'s geometry with ``bm`` (frees it), keep its material slots and ID properties."""
    bm.to_mesh(me)
    bm.free()
    U._apply_smooth(me, smooth)
    me.update()


# ------------------------------------------------------------------------------------------------------------ ramps

def ramp_bodies():
    return sorted((o for o in bpy.data.objects if o.type == 'MESH' and RAMP_RE.search(o.name)), key=lambda o: o.name)


def nosing_fn(stairs_root):
    L, n, riser = float(stairs_root["arch_run"]), int(stairs_root["arch_steps"]), float(stairs_root["arch_riser"])
    run, height = L / n, n * riser

    def nos(y):
        return np.where(y >= -run, height, riser + (height - riser) * (y + L) / (L - run))
    return nos


class Ramps:
    name = "ramps"

    def plan(self, fail):
        obs = ramp_bodies()
        if len(obs) != RAMP_COUNT:
            fail.add("ramps: %d '*.ramp_body' objects, expected %d" % (len(obs), RAMP_COUNT))
        self.todo, self.done, self.flip, self.obs = [], [], [], obs
        for o in obs:
            p = o.parent
            if p is None or "arch_run" not in p:
                fail.add("ramps: %s has no arch.stairs root parent" % o.name)
                continue
            if len(o.data.vertices) != 10 or len(o.data.polygons) != 7:
                fail.add("ramps: %s is not a sloped block (%d verts, %d faces)" % (
                    o.name, len(o.data.vertices), len(o.data.polygons)))
                continue
            if o.data.users != 1:
                fail.add("ramps: %s's mesh is shared (%d users)" % (o.name, o.data.users))
                continue
            co = local_co(o)
            top = co[:, 2] > 1e-4
            off = co[top, 2] - nosing_fn(p)(co[top, 1])
            if np.abs(off - A.RAMP_BODY_TOP_OLD).max() < 1e-4:
                self.todo.append(o)
            elif np.abs(off - A.RAMP_BODY_TOP).max() < 1e-4:
                self.done.append(o)
            else:
                fail.add("ramps: %s's top is %s over the nosing line, neither the old %.3f nor the new %.3f" % (
                    o.name, sorted(set(np.round(off, 4).tolist())), A.RAMP_BODY_TOP_OLD, A.RAMP_BODY_TOP))
            if signed_volume(o) < 0:
                self.flip.append(o)
        log("ramps: %d bodies, %d to lower by %.3f m, %d already lowered; %d inside out (arch.stairs never "
            "recalculated their normals), to turn right side out" % (
                len(obs), len(self.todo), A.RAMP_BODY_TOP_OLD - A.RAMP_BODY_TOP, len(self.done), len(self.flip)))
        return bool(self.todo or self.flip)

    def scan_names(self):
        return [o.name for o in self.obs]

    def apply(self):
        d = A.RAMP_BODY_TOP - A.RAMP_BODY_TOP_OLD
        for o in self.todo:
            co = local_co(o)
            co[co[:, 2] > 1e-4, 2] += d
            o.data.vertices.foreach_set("co", co.ravel())
            o.data.update()
        for o in self.flip:
            A._recalc_normals(o)
        log("ramps: lowered %d bodies' tops by %.3f m, turned %d right side out" % (len(self.todo), -d, len(self.flip)))

    def check(self, fail, dg):
        worst = None
        for o in self.obs:
            p = o.parent
            rel = bpy.data.objects.get(p.name + ".ramp")
            if rel is None:
                fail.add("ramps: no relief %s.ramp" % p.name)
                continue
            co = local_co(o)
            if co[:, 2].min() < -1e-6 or co[co[:, 2] > 1e-4, 2].min() < 0.05:
                fail.add("ramps: %s's body leaves the ground or gets too thin" % o.name)
            if signed_volume(o) <= 0:
                fail.add("ramps: %s is still inside out" % o.name)
            nos = nosing_fn(p)
            rv = local_co(rel)     # the relief and the body share the stairs root's frame (both parented, identity)
            if rel.matrix_parent_inverse != o.matrix_parent_inverse or rel.matrix_basis != o.matrix_basis:
                fail.add("ramps: %s and its relief are not in the same frame" % o.name)
                continue
            gap = rv[:, 2] - (nos(rv[:, 1]) + A.RAMP_BODY_TOP)
            g = float(gap.min())
            worst = g if worst is None else min(worst, g)
            if g < RAMP_MIN_GAP:
                fail.add("ramps: %s's relief comes %.3f m over the body (needs %.3f)" % (o.name, g, RAMP_MIN_GAP))
        if worst is not None:
            log("ramps: relief over the lowered bodies: at least %.3f m (was 0.005)" % worst)

    def caches(self):
        return [o.name for o in self.obs], [], []

    def targets(self):
        return [(o.name, o.parent.name + ".ramp") for o in self.obs]


# ----------------------------------------------------------------------------------------------------------- summit

def _old_terrace_bm():
    """The terrace as summit.py built it before round 11 (to recognise an unpatched file)."""
    bm = bmesh.new()
    R = SU.TERRACE_R
    prof = [(R - 0.9, -SU.TERRACE_DEPTH), (R - 0.45, -SU.TERRACE_DEPTH + 0.35), (R - 0.45, -0.55),
            (R - 0.15, -0.42), (R, -0.3), (R, 0.0)]
    r = R - 1.5
    while r > SU.MID_R - 1.5:
        prof.append((r, 0.0))
        r -= 2.5
    prof.append((SU.MID_R - 2.0, 0.0))
    U.bm_lathe(bm, prof, segments=128, cap_start=False, cap_end=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    return bm


class Summit:
    name = "summit"
    TERRACE, RING, GROOVE = "summit.terrace", "summit.ring", "summit.ring.groove"
    STAIR = "world.link.abode_summit.stairs"
    NAMES = {"summit.terrace": ["summit.terrace"], "summit.ring": ["summit.ring"]}

    def plan(self, fail):
        self.ter = bpy.data.objects.get(self.TERRACE)
        ring = bpy.data.objects.get(self.RING)
        self.groove = bpy.data.objects.get(self.GROOVE)
        if self.ter is None or ring is None or self.ter.type != 'MESH':
            fail.add("summit: no %s / %s" % (self.TERRACE, self.RING))
            return False
        me = self.ter.data
        mats = [m.get("sect_material") if m else None for m in me.materials]
        new_bm = SU._terrace_bm()
        new_co = bm_co(new_bm)
        new_n = len(new_bm.faces)
        new_bm.free()
        self.state = None
        if len(me.polygons) == new_n and same_points(local_co(self.ter), new_co) and mats == SU.TERRACE_MATS:
            self.state = "new"
        else:
            ob = _old_terrace_bm()
            if len(me.polygons) == SUMMIT_OLD_FACES and same_points(local_co(self.ter), bm_co(ob)) and \
                    mats == SU.TERRACE_MATS[:2]:
                self.state = "old"
            ob.free()
        if self.state is None:
            fail.add("summit: %s is neither the old terrace (%d faces, 2 materials) nor the new one (%d faces, %s): "
                     "%d faces, %s" % (self.TERRACE, SUMMIT_OLD_FACES, new_n, SU.TERRACE_MATS, len(me.polygons), mats))
            return False
        if self.groove is not None and (self.groove.parent != ring or self.groove.children):
            fail.add("summit: %s is not the ring's childless groove" % self.GROOVE)
        if self.state == "new" and self.groove is not None:
            log("summit: the terrace is new but the groove is still there: removing it")
        log("summit: terrace %s (%d faces), groove %s" % (self.state, len(me.polygons),
                                                         "present" if self.groove else "gone"))
        return self.state == "old" or self.groove is not None

    def scan_names(self):
        return [self.TERRACE] + ([self.GROOVE] if bpy.data.objects.get(self.GROOVE) else [])

    def apply(self):
        if self.state == "old":
            me = self.ter.data
            bm = SU._terrace_bm()
            write_bm(me, bm, SU.TERRACE_SMOOTH)
            U.set_materials(me, SU.TERRACE_MATS)
            log("summit: terrace rebuilt: %d faces, %d dark channel faces" % (
                len(me.polygons), sum(1 for p in me.polygons if p.material_index == 2)))
        if self.groove is not None:
            gone = remove_tree(self.groove)
            self.delta = -len(gone)
            log("summit: removed", gone)
            self.groove = None

    def check(self, fail, dg):
        me = self.ter.data
        V = local_co(self.ter)
        tree = BVHTree.FromPolygons([Vector(v) for v in V], [tuple(p.vertices) for p in me.polygons])
        mi = [p.material_index for p in me.polygons]
        c0, c1 = SU.CHANNEL_R
        hw, ay = SU.ARRIVAL_HW, SU.AREA["arrival"][1]
        bad_z = bad_mat = holes = 0
        n = 0
        for k in range(720):
            a = 2.0 * math.pi * (k + 0.5) / 720
            for r10 in range(221, 390, 2):
                r = r10 / 10.0
                if abs(r * math.cos(a)) < hw + 0.01 and r * math.sin(a) < ay + 0.01:
                    continue                    # under the abode stair's last tread: cut away (checked below)
                n += 1
                loc, nor, fi, d = tree.ray_cast(Vector((r * math.cos(a), r * math.sin(a), 1.0)), Vector((0, 0, -1)))
                if loc is None:
                    holes += 1
                    continue
                if abs(loc.z) > 1e-4:
                    bad_z += 1
                want = 2 if c0 + 0.01 < r < c1 * math.cos(math.pi / SU.TERRACE_SEGS) - 0.01 else \
                    (1 if (r < c0 - 0.01 or r > c1 + 0.01) else mi[fi])
                if mi[fi] != want:
                    bad_mat += 1
        if holes or bad_z or bad_mat:
            fail.add("summit: terrace top over r 22.1..38.9: %d holes, %d off z 0, %d wrong material (of %d)" % (
                holes, bad_z, bad_mat, n))
        rr = (SU.RING_R - SU.RING_W / 2, SU.RING_R + SU.RING_W / 2)
        off = 0
        for r in (rr[0], rr[0] + 0.05, rr[1] - 0.05, rr[1]):
            for k in range(4000):
                a = 2.0 * math.pi * k / 4000
                loc, nor, fi, d = tree.ray_cast(Vector((r * math.cos(a), r * math.sin(a), 1.0)), Vector((0, 0, -1)))
                if loc is None or mi[fi] != 2:
                    off += 1
        if off:
            fail.add("summit: %d samples of the rune band (r %.2f..%.2f) not over dark stone" % (off, rr[0], rr[1]))
        log("summit: terrace top one surface at z 0 (%d samples), rune band r %.2f..%.2f on dark stone%s" % (
            n, rr[0], rr[1], "" if not off else " EXCEPT %d" % off))
        # the cut under the abode stair's last tread: no terrace top left there, and the tread covers all of it at z 0
        W = self.ter.matrix_world
        Wi = W.inverted()
        sc = bpy.context.scene
        left = uncovered = m = 0
        for i in range(-12, 13):
            x = i * (hw - 0.05) / 12.0
            for j in range(1, 12):
                y = ay - 0.05 * j                       # 5 cm steps out from the arrival line
                if math.hypot(x, y) > SU.TERRACE_R * math.cos(math.pi / SU.TERRACE_SEGS) - 0.01:
                    continue
                m += 1
                loc = tree.ray_cast(Vector((x, y, 1.0)), Vector((0, 0, -1)), 2.0)[0]
                if loc is not None and loc.z > -0.01:   # (the skirt below the rim is not the top)
                    left += 1
                hit, loc, nor, fi, ob, mx = sc.ray_cast(dg, W @ Vector((x, y, 3.0)), Vector((0, 0, -1)), distance=4.0)
                if not hit or not ob.original.name.startswith(self.STAIR) or abs((Wi @ loc).z) > 0.002:
                    uncovered += 1
        if not m or left or uncovered:
            fail.add("summit: under the abode stair's last tread (%d points): %d still have terrace top, %d are not "
                     "covered by %s at z 0" % (m, left, uncovered, self.STAIR))
        log("summit: the terrace top is cut away under the abode stair's last tread, which covers the cut at z 0 "
            "(%d points)" % m)
        if bpy.data.objects.get(self.GROOVE) is not None:
            fail.add("summit: the groove is still there")

    def caches(self):
        return [self.TERRACE], [self.GROOVE], []

    def targets(self):
        # the stair: only its tread on the paving must go; its end face stays 0-5 mm in front of the terrace's lower
        # wall (r 38.55) near x +-1.9, face to face in a slot closed by the tread, the paving and the parapets
        return [(self.TERRACE, self.GROOVE), (self.TERRACE, self.STAIR, "same")]


# -------------------------------------------------------------------------------------------------------- formation

class Formation:
    name = "formation"
    FLOOR, BAND = "formation.floor", "formation.floor_band"
    STRIPS = {"formation.axis_walk": -1.0, "formation.axis_walk.001": 1.0}
    NAMES = {"formation.floor": ["formation.floor"], "formation.floor_band": ["formation.floor_band"],
             "formation.axis_walk": ["formation.axis_walk", "formation.axis_walk.001"]}

    def plan(self, fail):
        self.obs = {n: bpy.data.objects.get(n) for n in [self.FLOOR, self.BAND] + list(self.STRIPS)}
        miss = [n for n, o in self.obs.items() if o is None or o.type != 'MESH']
        if miss:
            fail.add("formation: missing %s" % miss)
            return False
        self.todo = {}
        # floor and bands: new = formation._floor_bm / _floor_band_bm; old = the same rings uncut
        keep = FO._axis_cut
        for nm, fn in ((self.FLOOR, FO._floor_bm), (self.BAND, FO._floor_band_bm)):
            o = self.obs[nm]
            bm = fn()
            new = (len(bm.faces), bm_co(bm))
            bm.free()
            FO._axis_cut = lambda bm, *a, **k: 0
            try:
                bm = fn()
                old = (len(bm.faces), bm_co(bm))
                bm.free()
            finally:
                FO._axis_cut = keep
            have = (len(o.data.polygons), local_co(o))
            if have[0] == new[0] and same_points(have[1], new[1]):
                st = "new"
            elif have[0] == old[0] == FORMATION_OLD[nm] and same_points(have[1], old[1]):
                st = "old"
                self.todo[nm] = fn
            else:
                fail.add("formation: %s is neither the uncut (%d faces) nor the cut floor (%d faces): %d faces" % (
                    nm, old[0], new[0], have[0]))
                continue
            log("formation: %s %s (%d faces; cut: %d)" % (nm, st, have[0], new[0]))
        for nm, sign in self.STRIPS.items():
            o = self.obs[nm]
            v_new, f_new, _ = FO._axis_walk_geom(sign)
            v_old, f_old, _ = FO._arc_slab_geom(FO.STRIP_HW, FO.R_DARK, FO.STRIP_FOOT, sign, STRIP_OLD_Z, None)
            have = local_co(o)
            if same_points(have, np.array(v_new)) and len(o.data.polygons) == len(f_new):
                st = "new"
            elif same_points(have, np.array(v_old)) and len(o.data.polygons) == len(f_old):
                st = "old"
                self.todo[nm] = sign
            else:
                fail.add("formation: %s is neither the old strip (z %.3f) nor the new one" % (nm, STRIP_OLD_Z))
                continue
            log("formation: %s %s (%d verts, z %.3f)" % (nm, st, len(have), float(have[:, 2].max())))
        return bool(self.todo)

    def scan_names(self):
        return list(self.obs)

    def apply(self):
        for nm, what in self.todo.items():
            me = self.obs[nm].data
            if callable(what):
                write_bm(me, what(), False)
            else:
                verts, faces, mi = FO._axis_walk_geom(what)
                me.clear_geometry()
                me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
                me.validate(verbose=False)
                me.polygons.foreach_set("material_index", list(mi))
                U._apply_smooth(me, False)
                me.update()
            log("formation: rebuilt %s: %d verts, %d faces" % (nm, len(me.vertices), len(me.polygons)))

    def check(self, fail, dg):
        trees = {}
        for nm, o in self.obs.items():
            trees[nm] = BVHTree.FromPolygons([Vector(v) for v in local_co(o)],
                                             [tuple(p.vertices) for p in o.data.polygons])
        ch0, ch1 = FO.R_CHANNEL
        gx = FO.R_CHANNEL[1] * math.sin(FO._axis_gap(0.5 * sum(FO.R_CHANNEL)))
        r_out = FO.R_DARK * math.cos(math.pi / FO.FLOOR_SEGS) - 0.01
        hw, ft = FO.STRIP_HW, FO.STRIP_FOOT
        pts = [(x / 4.0, y / 4.0) for x in range(-186, 187) for y in range(-186, 187)]
        for x0 in (-hw, hw):                               # both sides of the strip's long edges
            pts += [(x0 + d, y / 8.0) for d in (-0.004, -0.001, 0.001, 0.004) for y in range(-372, 373)]
        for y0 in (-ft, ft):                               # and of its ends at the dais foot
            pts += [(x / 16.0, y0 + d) for d in (-0.004, -0.001, 0.001, 0.004) for x in range(-48, 49)]
        dbl = none = offz = n = 0
        bad = []
        for x, y in pts:
            r = math.hypot(x, y)
            if r < FO.R_DAIS - 0.5 + 0.01 or r > r_out:
                continue
            if abs(abs(x) - hw) < 5e-4 or abs(abs(y) - ft) < 5e-4:
                continue                                   # on the strip's edge: a ray there touches both sides
            n += 1
            hits = 0
            for nm, t in trees.items():
                loc, nor, fi, d = t.ray_cast(Vector((x, y, 1.0)), Vector((0, 0, -1)), 2.0)
                if loc is not None:
                    hits += 1
                    if abs(loc.z) > 1e-4:
                        offz += 1
            channel = ch0 - 0.01 <= r <= ch1 + 0.01
            # the recessed jade channel ring has no floor; beside the axis the ink stone (and the strip) cross it
            need = not channel or (abs(x) < gx - 0.01 and ch0 + 0.01 < r < ch1 - 0.01)
            if hits > 1:
                dbl += 1
                bad.append((round(x, 3), round(y, 3), hits))
            elif hits == 0 and need:
                none += 1
                bad.append((round(x, 3), round(y, 3), 0))
        if dbl or none or offz:
            fail.add("formation: floor r %.1f..%.1f: %d points with two surfaces, %d with none, %d off z 0 (of %d): %s"
                     % (FO.R_DAIS - 0.5, FO.R_DARK, dbl, none, offz, n, bad[:12]))
        log("formation: floor, bands and strip: one surface at z 0 at %d points (%d doubled, %d holes)" % (
            n, dbl, none))
        # the walk on the axis, apron -> paifang -> strip -> dais foot, is flush (scene rays; things standing on the
        # walk, like the censer, a gate's sill or the gold inlay ring's 4 mm, are allowed)
        root = bpy.data.objects["formation.root"]
        W = root.matrix_world
        Wi = W.inverted()
        sc = bpy.context.scene
        worst, n = 0.0, 0
        for sign in (-1.0, 1.0):
            for k in range(int((FO.APRON_Y - 0.1 - ft - 0.3) / 0.1) + 1):
                y = sign * (ft + 0.3 + 0.1 * k)
                for x in (-1.5, 0.0, 1.5):
                    if abs(y - FO.CENSER_Y) < 1.6 and abs(x) < 1.6:
                        continue
                    hit, loc, nor, fi, ob, mx = sc.ray_cast(dg, W @ Vector((x, y, 3.0)), Vector((0, 0, -1)),
                                                            distance=4.0)
                    n += 1
                    if not hit:
                        fail.add("formation: no floor under the axis walk at (%.1f, %.1f)" % (x, y))
                        continue
                    z = (Wi @ loc).z
                    if abs(z) > 0.05:
                        continue        # something standing on the walk, not the floor
                    worst = max(worst, abs(z))
                    if abs(z) > 0.005:
                        fail.add("formation: a %.3f m step in the axis walk at (%.1f, %.1f) (%s)" % (z, x, y, ob.name))
        log("formation: the axis walk from each apron to the dais foot is flush: %d rays, worst %.4f m off z 0" % (
            n, worst))

    def caches(self):
        return list(self.obs), [], []

    def targets(self):
        out = []
        for st in self.STRIPS:
            for f in (self.FLOOR, self.BAND):
                out += [(st, f), (f, st)]
        return out


# ----------------------------------------------------------------------------------------------------------- mirror

def span_points(root_name):
    """Post foot points (mirror.root frame) of a rim span's posts point cloud, and its panel count."""
    posts = bpy.data.objects.get(root_name + ".posts")
    panels = bpy.data.objects.get(root_name + ".panels")
    if posts is None or panels is None:
        return None, None
    return local_co(posts), len(panels.data.vertices)


def expected_posts(a0, a1):
    """The post points arch.balustrade puts on mirror.rim_points(a0, a1) (2D, its posts at the points and between)."""
    pts = [Vector(p) for p in MI.rim_points(a0, a1)]
    out = [tuple(p) for p in pts]
    for k in range(len(pts) - 1):
        d = pts[k + 1] - pts[k]
        cnt = max(1, int(math.ceil(math.hypot(d.x, d.y) / 1.8)))
        for j in range(1, cnt):
            out.append(tuple(pts[k] + d * (j / cnt)))
    return np.array(out)


class Mirror:
    name = "mirror"
    NAMES = {"mirror.rim_rail": [n + x for n in MIRROR_SPANS for x in ("", ".posts", ".panels")]}

    def plan(self, fail):
        self.root = bpy.data.objects.get("mirror.root")
        if self.root is None:
            fail.add("mirror: no mirror.root")
            return False
        self.spans = MI.rim_spans()
        (nw0, nw1), (se0, se1) = self.spans
        log("mirror: rim spans %.1f -> %.1f deg (north / west) and %.1f -> %.1f deg (south-east, to the forge stair's "
            "foot-landing wall), r %.1f (%.1f over %s deg), openings %.1f m at the stairs" % (
                math.degrees(nw0), math.degrees(nw1), math.degrees(se0), math.degrees(se1), MI.RIM_R, MI.RIM_R_EAST,
                MI.RIM_EAST, MI.RIM_GAP))
        self.rails = self.rails_now()
        have = {n: span_points(n) for n in self.rails}
        counts = {n: (None if h[0] is None else len(h[0])) for n, h in have.items()}
        self.state = None
        if tuple(self.rails) == MIRROR_SPANS and all(
                have[n][0] is not None and same_points(have[n][0], expected_posts(*sp), 1e-3)
                for n, sp in zip(MIRROR_SPANS, self.spans)):
            self.state = "new"
        elif tuple(self.rails) == MIRROR_OLD and counts == MIRROR_OLD_POSTS:
            self.state = "old"
        else:
            fail.add("mirror: rim rail spans %s are neither the half rail (%s) nor the full ring (%s, %s posts)" % (
                counts, MIRROR_OLD_POSTS, MIRROR_SPANS, [len(expected_posts(*sp)) for sp in self.spans]))
            return False
        log("mirror: rail %s: %s" % (self.state, counts))
        return self.state == "old"

    def rails_now(self):
        return tuple(sorted(o.name for o in self.root.children
                            if o.type == 'EMPTY' and o.name.startswith("mirror.rim_rail")))

    def rail_owners(self, rails=None):
        out = []
        for n in (rails if rails is not None else self.rails_now()):
            out += [n + ".posts", n + ".panels"]
        return out

    def scan_names(self):
        return self.rail_owners()

    def apply(self):
        coll = bpy.data.objects[MIRROR_OLD[0]].users_collection[0]
        ng0, col0 = len(bpy.data.node_groups), len(bpy.data.collections)
        gone = []
        for n in MIRROR_OLD:
            ob = bpy.data.objects.get(n)
            if ob is not None:
                gone += remove_tree(ob)
        log("mirror: removed the half rail:", gone)
        self.dup, made = [], 0
        for want, (a0, a1) in zip(MIRROR_SPANS, self.spans):
            r = A.balustrade(MI._n("rim_rail"), coll, MI.rim_points(a0, a1), height=1.0, parent=self.root)
            kids = sorted(c.name for c in r.children)
            made += 1 + len(kids)
            log("mirror: built %s (%s): %d posts, %d panels" % (
                r.name, kids, len(bpy.data.objects[r.name + ".posts"].data.vertices),
                len(bpy.data.objects[r.name + ".panels"].data.vertices)))
            if r.name != want or kids != [want + ".panels", want + ".posts"]:
                self.dup.append("names %s %s (wanted %s)" % (r.name, kids, want))
            for k in kids:
                o = bpy.data.objects[k]
                if o.data.name != k:
                    self.dup.append("mesh %s" % o.data.name)
                gname = o.modifiers[0].node_group.name if o.modifiers and o.modifiers[0].node_group else None
                if gname not in ("arch.gn." + POST_PROTO, "arch.gn." + PANEL_PROTO):
                    self.dup.append("node group %s" % gname)
        self.delta = made - len(gone)
        if len(bpy.data.node_groups) != ng0 or len(bpy.data.collections) != col0:
            self.dup.append("node groups %d -> %d, collections %d -> %d" % (
                ng0, len(bpy.data.node_groups), col0, len(bpy.data.collections)))

    def terrain(self, dg):
        W = self.root.matrix_world
        c = np.array(tuple(W.translation))
        box = (c - (75.0, 75.0, 40.0), c + (75.0, 75.0, 40.0))
        tt = gather(dg, owners=["world.range"], boxes=[box]).get("world.range")
        return None if tt is None else bvh_of(tt)

    def exposure(self, tree, span):
        """[(angle deg, air under the foot m, 'post' | 'panel')] for every post and panel of ``span`` (from its posts
        point cloud): the highest gap between the foot's buried bottom and world.range over the footprint."""
        W = self.root.matrix_world
        Wi = W.inverted()
        pts, _ = span_points(span)
        pts = sorted((tuple(p) for p in pts), key=lambda p: math.atan2(p[1], p[0]) % (2 * math.pi)
                     if span == MIRROR_SPANS[0] else math.atan2(p[1], p[0]))
        out = []

        def ground(x, y):
            loc, nor, fi, d = tree.ray_cast(W @ Vector((x, y, 5.0)), Vector((0, 0, -1)), 40.0)
            return None if loc is None else (Wi @ loc).z

        def worst(samples, bottom):
            g = [ground(x, y) for x, y in samples]
            return 99.0 if None in g else max(bottom - z for z in g)

        for k, p in enumerate(pts):
            ang = math.atan2(p[1], p[0])
            t = Vector((-math.sin(ang), math.cos(ang)))
            rr = Vector((math.cos(ang), math.sin(ang)))
            sm = [Vector((p[0], p[1])) + rr * i * POST_HALF + t * j * POST_HALF for i in (-1, 0, 1) for j in (-1, 0, 1)]
            out.append((math.degrees(ang), worst([(v.x, v.y) for v in sm], p[2] - POST_SINK), "post"))
            if k + 1 < len(pts):
                q = pts[k + 1]
                a_, b_ = Vector((p[0], p[1])), Vector((q[0], q[1]))
                if (b_ - a_).length > 2.0:      # not neighbours (the two ends of a span)
                    continue
                n_ = (b_ - a_).normalized()
                side = Vector((-n_.y, n_.x))
                sm = [a_ + (b_ - a_) * f + side * j * SILL_HALF
                      for f in (0.2, 0.35, 0.5, 0.65, 0.8) for j in (-1, 0, 1)]
                mid = math.atan2((a_.y + b_.y) * 0.5, (a_.x + b_.x) * 0.5)
                out.append((math.degrees(mid), worst([(v.x, v.y) for v in sm], p[2] - SILL_SINK), "panel"))
        return out

    def overlaps(self, dg, owners):
        """(hard, soft) owners the rail pieces ``owners`` cut into (world.range, where the feet are buried, is left
        out)."""
        mine = world_tris(owners, dg)
        if not mine:
            return set(), set()
        T = np.concatenate(list(mine.values()))
        nb = gather(dg, boxes=[tris_box(T)], skip=set(self.rail_owners()) | set(owners), pad=0.05)
        mt = bvh_of(T)
        hard, soft = set(), set()
        for own, TT in nb.items():
            if own == "world.range":
                continue
            if mt.overlap(bvh_of(TT)):
                (soft if any(w in own.lower() for w in MIRROR_SOFT) else hard).add(own)
        return hard, soft

    def before(self, dg):
        """The half rail's footing and what it cuts into, to compare the full ring with."""
        tree = self.terrain(dg)
        self.expose0 = []
        if tree is not None:
            for n in self.rails:
                self.expose0 += [(n, a, e, k) for a, e, k in self.exposure(tree, n)]
        self.hard0, soft0 = self.overlaps(dg, self.rail_owners(self.rails))
        bad = [(n, round(a), round(e, 2)) for n, a, e, k in self.expose0 if e > EXPOSE_MAX]
        log("mirror: the half rail: %d of %d feet over air (worst %.3f m) %s; it cuts into %s" % (
            len(bad), len(self.expose0), max((e for _, _, e, _ in self.expose0), default=0.0), bad[:12],
            sorted(self.hard0)))

    def check(self, fail, dg):
        for d in getattr(self, "dup", []):
            fail.add("mirror: duplicated / unexpected datablock: %s" % d)
        W = self.root.matrix_world
        tree = self.terrain(dg)
        if tree is None:
            fail.add("mirror: no world.range under the terrace")
            return
        # 1. footing: every post and panel foot wholly on the flat terrace (no air under its buried bottom)
        exp = []
        for n in MIRROR_SPANS:
            exp += [(n, a, e, k) for a, e, k in self.exposure(tree, n)]
        bad = [(n, round(a, 1), round(e, 3), k) for n, a, e, k in exp if e > EXPOSE_MAX]
        if bad:
            fail.add("mirror: %d feet over air: %s" % (len(bad), bad[:10]))
        was = getattr(self, "expose0", None)
        log("mirror: footing: %d posts and panels, worst air under a foot %.3f m (allowed %.3f)%s" % (
            len(exp), max(e for _, _, e, _ in exp), EXPOSE_MAX, "" if not was else
            "; the half rail: %d of %d over air, worst %.3f m" % (sum(1 for x in was if x[2] > EXPOSE_MAX), len(was),
                                                                 max(x[2] for x in was))))
        rad = [math.hypot(p[0], p[1]) for n in MIRROR_SPANS for p in span_points(n)[0]]
        log("mirror: posts at r %.2f..%.2f m" % (min(rad), max(rad)))
        # 2. coverage: two spans and two openings close the circle. The arrival opening is RIM_GAP (the chord between
        # the spans' end posts); on the depart side the north / west span starts RIM_GAP / 2 from where the forge
        # stair crosses the rail, and the south-east span ends against the south wall of that stair's foot landing
        # (mirror._foot_wall_end), with no rail on the landing
        ends = []
        for n, (a0, a1) in zip(MIRROR_SPANS, self.spans):
            pts = MI.rim_points(a0, a1)
            ends.append((Vector(pts[0][:2]), Vector(pts[-1][:2])))
        g_dep = (ends[1][1] - ends[0][0]).length        # south-east end -> north / west start (the depart side)
        g_arr = (ends[0][1] - ends[1][0]).length        # north / west end -> south-east start (the arrival side)
        (nw0, nw1), (se0, se1) = self.spans
        tot = math.degrees((nw1 - nw0) + (se1 - se0) + (se0 + 2 * math.pi - nw1) + (nw0 - se1))
        px, py, _, ph = MI.AREA["depart"]
        fwd, rgt = Vector((math.cos(ph), math.sin(ph))), Vector((math.sin(ph), -math.cos(ph)))
        dep = MI._rim_crossing(px, py, ph)
        rd = MI.rim_radius(dep)
        half_n = (ends[0][0] - Vector((rd * math.cos(dep), rd * math.sin(dep)))).length
        e = ends[1][1] - Vector((px, py))
        e_along, e_right = e.dot(fwd), e.dot(rgt)
        want_right = MI.DEPART_FOOT_WALL + MI.RIM_END_EMBED
        if abs(tot - 360.0) > 1e-6 or abs(g_arr - MI.RIM_GAP) > GAP_TOL or \
                abs(half_n - 0.5 * MI.RIM_GAP) > GAP_TOL or abs(e_right - want_right) > 0.01 or \
                not FOOT_WALL_ALONG[0] < e_along < FOOT_WALL_ALONG[1]:
            fail.add("mirror: spans and openings do not close the circle as planned (%.4f deg; arrival opening "
                     "%.3f m; depart: north half %.3f m, south-east end %.3f m along / %.3f m right of the stair)" % (
                         tot, g_arr, half_n, e_along, e_right))
        on = []
        for n in MIRROR_SPANS:
            for p in span_points(n)[0]:
                q = Vector((p[0], p[1])) - Vector((px, py))
                if FOOT_LANDING_IN[0] < q.dot(fwd) < FOOT_LANDING_IN[1] and abs(q.dot(rgt)) < FOOT_LANDING_IN[2]:
                    on.append((n, round(p[0], 2), round(p[1], 2)))
        if on:
            fail.add("mirror: %d rail posts stand on the forge stair's foot landing: %s" % (len(on), on[:6]))
        log("mirror: two spans and two openings close the circle; arrival opening %.2f m; depart opening %.2f m from "
            "the north / west span's start to the south-east span's end post, %.2f m right of the stair line against "
            "its foot-landing wall (%.2f m along it); no post on the landing" % (g_arr, g_dep, e_right, e_along))
        # 3. the openings let the connector stairs through: level rays along each stair's end run
        rails = world_tris(self.rail_owners(), dg)
        rtree = bvh_of(np.concatenate(list(rails.values())))
        for key, sgn in (("arrival", -1.0), ("depart", 1.0)):
            x, y, z, h = MI.AREA[key]
            d = Vector((math.cos(h), math.sin(h), 0.0)) * sgn       # walking outward, off the terrace
            side = Vector((-d.y, d.x, 0.0))
            blocked = []
            for lat in (-2.3, 0.0, 2.3):
                for up in (0.35, 0.9):
                    o = Vector((x, y, z + up)) + side * lat - d * 3.0
                    loc, nor, fi, dist = rtree.ray_cast(W @ o, (W.to_3x3() @ d).normalized(), 12.0)
                    if loc is not None:
                        blocked.append((lat, up, round(dist, 2)))
            if blocked:
                fail.add("mirror: the rail blocks the %s stair: %s" % (key, blocked))
            else:
                log("mirror: the %s stair passes the rail (rays at -2.3 / 0 / 2.3 m, 0.35 / 0.9 m up)" % key)
        # 4. the ring cuts into nothing the half rail did not (its ends meet the same stair walls)
        hard, soft = self.overlaps(dg, self.rail_owners())
        was = getattr(self, "hard0", None)
        extra = sorted(hard - was) if was is not None else []
        log("mirror: the ring touches %s (soft: %s); the half rail touched %s" % (
            sorted(hard), sorted(soft)[:6], "?" if was is None else sorted(was)))
        if extra:
            fail.add("mirror: the ring cuts into %s, which the half rail did not" % extra)

    def caches(self):
        new = self.rail_owners() if self.state == "old" else []
        return self.rail_owners(), ["mirror.rim_rail.002.posts", "mirror.rim_rail.002.panels"], new

    def targets(self):
        return []


# ------------------------------------------------------------------------------------------------------------- main

def area_of(name):
    ob = bpy.data.objects.get(name)
    while ob is not None and ob.parent is not None:
        ob = ob.parent
    return ob.name.split(".")[0] if ob is not None else name.split(".")[0]


def main():
    dry, parts = options()
    t0 = time.time()
    fail = Fail()
    sc = bpy.context.scene
    keep_frame = sc.frame_current
    lib = {"ramps": Ramps, "summit": Summit, "formation": Formation, "mirror": Mirror}
    P = [lib[p]() for p in parts]
    todo = {}
    for p in P:
        todo[p.name] = p.plan(fail)
    if fail:
        log("NOT SAVED: the file is not in a state this patch knows (%d problems)" % len(fail))
        raise SystemExit(1)
    if not any(todo.values()):
        log("every part unchanged:", ", ".join(p.name for p in P))
    dg = bpy.context.evaluated_depsgraph_get()
    n_obj0 = len(bpy.data.objects)
    for p in P:
        if todo[p.name] and hasattr(p, "before"):
            p.before(dg)
    before_scan, before_box = {}, {}
    for p in P:
        if todo[p.name]:
            before_scan[p.name], before_box[p.name] = scan("before", p.scan_names(), dg)
        else:
            before_box[p.name] = {k: tris_box(v) for k, v in world_tris(p.scan_names(), dg).items()}
    for p in P:
        if todo[p.name]:
            p.apply()
    bpy.context.view_layer.update()
    sc.frame_set(keep_frame)
    dg = bpy.context.evaluated_depsgraph_get()
    for p in P:
        p.check(fail, dg)
        if todo[p.name]:
            res, _ = scan("after", p.scan_names(), dg)
            bef = before_scan[p.name]
            sb, sa = same_total(bef), same_total(res)
            ob_ = sum(r[1] for rows in bef.values() for r in rows.values())
            oa_ = sum(r[1] for rows in res.values() for r in rows.values())
            log("%s: overlap within 5 mm: same-facing (z-fights) %.1f m2 -> %.1f m2; opposite-facing (contact, hidden) "
                "%.1f m2 -> %.1f m2" % (p.name, sb, sa, ob_, oa_))
            for t in p.targets():
                a_, b_ = t[:2]
                k = slice(0, 1) if t[2:] == ("same",) else slice(0, 2)     # "same": only the visible kind must go
                was = sum(bef.get(a_, {}).get(b_, [0.0, 0.0])[k])
                now = sum(res.get(a_, {}).get(b_, [0.0, 0.0])[k])
                if now > SCAN_TARGET_MAX:
                    fail.add("%s: %s / %s still overlap within 5 mm%s: %.2f m2 (was %.2f)" % (
                        p.name, a_, b_, " (same-facing)" if k.stop == 1 else "", now, was))
            gone = sum(sum(bef.get(t[0], {}).get(t[1], [0.0, 0.0])[slice(0, 1) if t[2:] == ("same",) else slice(0, 2)])
                       for t in p.targets())
            log("%s: the overlaps this part removes: %.1f m2 before" % (p.name, gone))
            left = []
            for pk, rows in res.items():
                for o, (s_, q_) in rows.items():
                    was = bef.get(pk, {}).get(o, [0.0, 0.0])[0]
                    if s_ > was + SCAN_NEW_MAX:
                        fail.add("%s: new same-facing overlap %s / %s: %.2f m2 (was %.2f)" % (p.name, pk, o, s_, was))
                    elif s_ > SCAN_NEW_MAX:
                        left.append("%s / %s %.1f m2" % (pk, o, s_))
            if left:
                log("%s: same-facing overlaps left as they were (not this part's): %s" % (p.name, "; ".join(left)))
    # names and counts: every rebuilt or new object has its expected name, nothing else appeared or vanished
    n_obj1 = len(bpy.data.objects)
    want_delta = sum(getattr(p, "delta", 0) for p in P)
    if n_obj1 - n_obj0 != want_delta:
        fail.add("names: objects %d -> %d, expected %+d" % (n_obj0, n_obj1, want_delta))
    for p in P:
        for prefix, names in getattr(p, "NAMES", {}).items():
            have = sorted(o.name for o in bpy.data.objects if o.name == prefix or o.name.startswith(prefix + "."))
            if have != sorted(names):
                fail.add("names: %s* are %s, expected %s" % (prefix, have, sorted(names)))
    if sum(1 for o in bpy.data.objects if RAMP_RE.search(o.name)) != RAMP_COUNT:
        fail.add("names: the ramp bodies changed in number")
    log("objects %d -> %d (expected %+d)" % (n_obj0, n_obj1, want_delta))
    # caches
    dg = bpy.context.evaluated_depsgraph_get()
    stale, new_names, removed, chunks = [], [], [], set()
    for p in P:
        kept, gone, new = p.caches()
        removed += [g for g in gone if g in before_box[p.name] and bpy.data.objects.get(g) is None]
        new_names += new
        if todo[p.name]:
            chunks.add(p.name if p.name != "ramps" else "")
            if p.name == "ramps":
                chunks |= {area_of(o.name) for o in p.todo}
        now = {k: tris_box(v) for k, v in world_tris(kept, dg).items()}
        for k, b in now.items():
            if k in new:
                continue
            old = before_box[p.name].get(k)
            if old is None:
                new_names.append(k)
            elif not box_inside(b, old):
                stale.append(k)
    chunks.discard("")
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail:
            log("  -", f)
        raise SystemExit(1)
    if new_names or stale:
        log("CACHES needs audit: %d new instance sets %s, %d boxes grew %s (removed, ignored by the caches: %s) - run "
            "export_web.py -- audit --profile full, then chunks,meta, then bake_web.py bakefull for %s and the "
            "backdrop, then tools/sect_pack.py" % (len(new_names), new_names, len(stale), stale, removed,
                                                   ",".join(sorted(chunks))))
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
