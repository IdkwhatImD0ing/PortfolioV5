"""Round 34, lane 'west': the Jin Yong references at the Heart-Mirror Terrace (217), the Cave Abode (1380) and the
Moon-Gazing Summit (1647) re-staged as the r31 references plan says (approved), in an existing out/sect_chase.blend, so
it matches what a fresh build of sect/areas/mirror.py, abode.py and summit.py makes (with sect/lib/refs_west.py, and
scratchpad r34/west/pending_scenery.diff for scenery.py's masks). Run on the cloud box, on a copy first, AFTER the round-28
lions and round-29 forge patches:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r34_west.py [-- DRY_RUN=1] [SCAN=0]

Why (owner, 2026-10-23, the r31 plan approved with one change: the cards describe the item, no line on why it is
there): each reference stands where such a thing would be kept, at the stop whose story it shares, in the part of the
hold's frame the panel leaves open.

What it does (each group is built in a scratch copy, compared with the file, and only then put in place):
- mirror, the flute: round 7's set at the pond's east rim (mirror.flute and its _rock, _bag, _xiao, _tassel,
  _petals, _peach) goes; Huang Yaoshi's jade flute 玉簫 lies on a black-lacquer stand in the pond pavilion, facing the
  mirror: 'mirror.flute' (Empty under mirror.ting, so the Pond Pavilion hotspot carries it), 'mirror.flute_stand',
  'mirror.flute_xiao', 'mirror.flute_tassel' (refs_west.flute_set).
- mirror, 思過崖: 'mirror.siguoya' under mirror.root, three ~5 m characters cut into a dressed face on the bare cliff
  behind and above the mirror, ink in the strokes (refs_west.siguoya); world.range's tree masks (refs_west.CLEAR_ATTRS)
  are zeroed on the faces round it and in the hold's line of sight to it (refs_west.siguoya_clear), so its pines go.
- abode: Xiaolongnü's ribbon ('abode.ribbon', '_silk', '_bells') comes off the tea pavilion's eave; the Wanderer duet
  ('abode.duet' and its six parts) is rebuilt at abode.DUET_LOC / DUET_YAW / DUET_SCALE (2 m onto the open lawn, 10 deg
  more to the camera, 1.25 -> 1.5) and abode.ground's 'garden_mask' is recomputed for its new place (abode._ground's
  rule), so abode.garden_scatter's plants keep off it and come back where it stood.
- summit: the condor's crag and bird ('summit.condor_crag', '_crag_rock', '_crag_rock.001', '_cap', '_bird') are
  rebuilt at summit.CONDOR_SITE (right of the pavilion below the moon, bird scale 0.85); the golden-bell ribbon lies
  coiled on its rock with one bell over the edge ('summit.ribbon', '_silk', '_bells'; refs_west.coil); the bench of
  the pavilion's middle front bay goes and 綠竹巷's bamboo blinds, gauze, qin table, qin and lamp come in
  ('summit.blinds' under summit.pavilion and its six meshes; refs_west.blinds).

State: each group is 'old' (what the round-12-and-later file has), 'new' (equal to this build: every face, order-free,
transforms, parents and material slots) or 'stale' (an earlier round-34 build that differs: rebuilt); anything else
stops the patch. Idempotent: on this build's file it prints 'PATCH nothing changed: not saving' and the same DIGEST.

Checks (any failure stops the patch before saving; DRY_RUN=1 runs everything and never saves):
- pieces: every new mesh closed (no edge in fewer than two faces), within TRI_CAP, its material slots filled;
- grounded: the stand's feet, the qin table's legs and the lamp's base on their floors (sunk, no gap), the flute in
  its cradles, the duet's bases on the lawn, the condor's toes and boulders on their rock, the ribbon on its rock
  (no section's underside more than COIL_GAP_MAX over the rock under it), the dressed face's sides in the rock;
- clear: each new piece touches only what it is meant to (ALLOW) and keeps CLEAR_MIN from everything else;
- readable: at each hold as the site frames it (1600 x 900): 思過崖's characters whole in the frame, each at least
  READ_MIN_PX tall and READ_SEEN unhidden (no pine in front); the flute, the duet, the bird, the ribbon and the blinds
  in the frame and at least partly seen (logged); the bird out from under the Contact panel and left of the voice
  button; frame 1625 logged (what the crag hides of the pavilion there);
- flight: chase.cam (every frame) never nearer than CAM_MIN to the crag and the bird, CAM_NEAR to anything else new;
- trees: world.range's scatters lose only instances on the cleared faces (every other instance where it was), none
  stands between the hold and the characters; abode.garden_scatter changes only round the duet's old and new places;
- coplanar scan (SCAN=1): parallel same-facing faces within 5 mm and 5-12 mm (12-20 mm and back-to-back within 5 mm
  logged) of every new piece against itself and everything near it; at most NEW_MAX m2 per pair;
- names and counts: the objects listed above and nothing else added or removed; no scratch data, no scene left.
Prints 'PATCH CACHES needs audit' with the chunks to re-bake, and 'PATCH DIGEST <md5>'.
"""
import hashlib
import math
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
from sect.areas import abode as AB  # noqa: E402
from sect.areas import summit as SU  # noqa: E402
from sect.lib import props as P  # noqa: E402
from sect.lib import refs_west as RW  # noqa: E402

TMP = "~r34w."
RES = (1600, 900)
TRI_CAP = 30000            # per new mesh (the bird 24k)
CLEAR_MIN = 0.01           # m
CAM_MIN = 12.0             # m: the crag and the bird (the plan's rule)
CAM_NEAR = 3.0             # m: anything else new
COIL_GAP_MAX = 0.12        # m: no ribbon section's underside this far over the rock under its middle (on the coil)
READ_MIN_PX = 18.0         # a character of 思過崖 at the hold
READ_SEEN = 0.9            # share of a character's samples a ray from the hold reaches
NEW_MAX = 0.02             # m2: same-facing overlap (<= 12 mm) a new piece may have against anything
SCAN_TOL, SCAN_TOL12, SCAN_TOL20, SCAN_PAR = 0.0055, 0.0125, 0.0205, 0.985
PANEL_SUMMIT = (63, 495, 560, 810)   # px: the Contact panel at 1647 (x0, x1, y0, y1; r31 audit)
VOICE_X = 1470             # px: the bird's box stays left of this (the voice button)
FLUTE_NEW = list(RW.FLUTE_NAMES)
SIG = RW.SIGUOYA
RIB_OLD = ("abode.ribbon", "abode.ribbon_silk", "abode.ribbon_bells")
DUET_NAMES = [AB.DUET] + [nm for _k, nm, _g, _r in AB.DUET_PARTS]
CONDOR_NAMES = ["summit.condor_crag", "summit.condor_crag_rock", "summit.condor_crag_rock.001", "summit.condor_cap",
                "summit.condor_bird"]
RIB_NEW = list(RW.RIBBON_NAMES)
BLIND_NEW = [RW.BLIND_NAMES[k] for k in ("root", "blinds", "gauze", "ties", "table", "qin", "lamp")]
# what each new piece may touch (names or prefixes; '*' = every new piece of the same group)
ALLOW = {
    "mirror.flute_stand": ("mirror.ting.platform", "mirror.flute_xiao", "mirror.flute_tassel"),
    "mirror.flute_xiao": ("mirror.flute_stand", "mirror.flute_tassel"),
    "mirror.flute_tassel": ("mirror.flute_stand", "mirror.flute_xiao"),
    "mirror.siguoya": ("world.range",),
    "summit.condor_crag": ("world.range", "summit.condor_cap", "summit.condor_crag_rock", "summit.condor_crag_rock.001",
                           "summit.ribbon_silk"),
    "summit.condor_cap": ("summit.condor_crag", "summit.condor_bird", "summit.condor_crag_rock",
                          "summit.condor_crag_rock.001", "summit.ribbon_silk"),
    "summit.condor_crag_rock": ("summit.condor_crag", "summit.condor_cap", "summit.condor_crag_rock.001"),
    "summit.condor_crag_rock.001": ("summit.condor_crag", "summit.condor_cap", "summit.condor_crag_rock"),
    "summit.condor_bird": ("summit.condor_cap",),
    "summit.ribbon_silk": ("summit.ribbon_bells", "summit.condor_crag", "summit.condor_cap"),   # it lies on them
    "summit.ribbon_bells": ("summit.ribbon_silk",),
    "summit.blinds_bamboo": ("summit.pavilion.col", "summit.blinds_ties", "summit.blinds_gauze"),
    "summit.blinds_gauze": ("summit.pavilion.col", "summit.blinds_bamboo"),
    "summit.blinds_ties": ("summit.blinds_bamboo",),
    "summit.qin_table": ("summit.pavilion.platform", "summit.qin"),
    "summit.qin": ("summit.qin_table",),
    "summit.qin_lamp": ("summit.pavilion.platform",),
}
for _nm in DUET_NAMES[1:]:
    ALLOW[_nm] = ("abode.ground",) + tuple(n for n in DUET_NAMES[1:] if n != _nm)
CLEAR_SKIP = ("world.haze", "world.cloud", "world.backdrop")
OPEN_OK = ("summit.condor_bird",)   # the prepared bird (condor_props) as round 7 placed it: 7 open edges in the scan
LAWN_REST = {"abode.duet_huqin": 0.015}   # m: the huqin's bow rests on the grass (abode.HQ_BOW_REST at the new scale)


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
            raise SystemExit("patch_r34_west: unknown option %r (DRY_RUN=1, SCAN=0)" % a)
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
    try:
        me.calc_loop_triangles()
    except Exception:  # noqa: BLE001
        pass
    nv, nt = len(me.vertices), len(me.loop_triangles)
    co = np.empty(nv * 3)
    me.vertices.foreach_get("co", co)
    tv = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", tv)
    return co.reshape(nv, 3)[tv.reshape(nt, 3)]


def faces_sig(me):
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


def obj_sig(ob, prefix=""):
    """Order-free fingerprint of an object as built: its name without ``prefix``, parent (likewise), transform,
    instance collection, mesh faces and material slots."""
    nm = ob.name[len(prefix):] if prefix and ob.name.startswith(prefix) else ob.name
    par = ob.parent.name if ob.parent else ""
    if prefix and par.startswith(prefix):
        par = par[len(prefix):]
    h = hashlib.md5()
    h.update(nm.encode())
    h.update(par.encode())
    h.update(np.round(np.array(ob.matrix_basis), 5).tobytes())
    h.update(np.round(np.array(ob.matrix_parent_inverse), 5).tobytes())
    h.update((ob.instance_collection.name if ob.instance_collection else "").encode())
    if ob.type == 'MESH':
        h.update(faces_sig(ob.data).encode())
        h.update(repr([s.material.name if s.material else None for s in ob.material_slots]).encode())
    return h.hexdigest()


def tri_normals(T):
    cr = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    L = np.linalg.norm(cr, axis=1)
    ok = L > 1e-12
    n = np.zeros_like(cr)
    n[ok] = cr[ok] / L[ok, None]
    return n, 0.5 * L


def bvh(T):
    return BVHTree.FromPolygons([Vector(p) for p in T.reshape(-1, 3)],
                                [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(T))], all_triangles=True)


def world_tris(dg, owners=None, near=None, skip=()):
    """{owner: (n, 3, 3) world triangles} of the evaluated scene's meshes (instances under their instancer's name)."""
    out = {}
    for inst in dg.object_instances:
        o = inst.object
        if o.type != 'MESH':
            continue
        own = inst.parent.original.name if inst.is_instance and inst.parent else o.original.name
        if (owners is not None and own not in owners) or own in skip or own.startswith(CLEAR_SKIP):
            continue
        W = np.array(inst.matrix_world)
        if near is not None:
            bb = np.array(o.bound_box) @ W[:3, :3].T + W[:3, 3]
            if (bb.min(0) > near[1]).any() or (bb.max(0) < near[0]).any():
                continue
        L = local_tris(o.data)
        if len(L):
            T = L @ W[:3, :3].T + W[:3, 3]
            if near is not None:
                keep = ~((T.min(1) > near[1]).any(1) | (T.max(1) < near[0]).any(1))
                T = T[keep]
            if len(T):
                out.setdefault(own, []).append(T)
    return {k: np.concatenate(v) for k, v in out.items()}


def open_edges(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    n = sum(1 for e in bm.edges if len(e.link_faces) < 2)
    bm.free()
    return n


def remove_objects(names, why):
    """Remove the named objects that exist and the meshes they leave unused. Returns the names removed."""
    gone = []
    meshes = set()
    for nm in sorted(set(names)):
        o = bpy.data.objects.get(nm)
        if o is None:
            continue
        if o.type == 'MESH' and o.data is not None:
            meshes.add(o.data.name)
        gone.append(nm)
        log("remove", nm, o.type, why)
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        if m.name in meshes and m.users == 0:
            bpy.data.meshes.remove(m)
    return gone


def take_names(scratch, prefix=TMP):
    """Rename scratch objects (and their meshes) to their names without ``prefix``. Raises when a name is taken."""
    for ob in scratch:
        nm = ob.name[len(prefix):]
        if bpy.data.objects.get(nm) is not None:
            raise RuntimeError("name %s is taken" % nm)
    for ob in scratch:
        nm = ob.name[len(prefix):]
        ob.name = nm
        if ob.name != nm:
            raise RuntimeError("could not name %s" % nm)
        if ob.type == 'MESH' and ob.data is not None and ob.data.name.startswith(prefix):
            ob.data.name = nm


def scratch_objects(prefix=TMP):
    return [o for o in bpy.data.objects if o.name.startswith(prefix)]


def compare(names, scratch, prefix=TMP):
    """'new' when the file's objects ``names`` equal the scratch build (same set, same signatures), else a list of the
    differing names."""
    have = {n: bpy.data.objects.get(n) for n in names}
    built = {o.name[len(prefix):]: o for o in scratch}
    if set(built) != set(names):
        return ["built %s, expected %s" % (sorted(built), sorted(names))]
    diff = [n for n in names if have[n] is None or obj_sig(have[n]) != obj_sig(built[n], prefix)]
    return "new" if not diff else diff


# ---------------------------------------------------------------------------------------------------- the groups

def build_flute(coll):
    root = bpy.data.objects["mirror.root"]
    ting = bpy.data.objects["mirror.ting"]
    em = RW.flute_set(coll, root, ting, names=[TMP + n for n in FLUTE_NEW], log=lambda *a: log(*a))
    return [em] + list(em.children)


def build_siguoya(coll):
    root = bpy.data.objects["mirror.root"]
    return [RW.siguoya(coll, root, name=TMP + SIG, log=lambda *a: log(*a))]


def build_duet(coll):
    """abode._duet into a scratch collection, its objects renamed TMP + name."""
    root = bpy.data.objects["abode.root"]
    sub = bpy.data.collections.new(TMP + "duet")
    bpy.context.scene.collection.children.link(sub)
    em = AB._duet(sub, root)
    obs = [em] + list(em.children)
    for o in obs:
        nm = o.name
        stem = nm[:-4] if len(nm) > 4 and nm[-4] == "." and nm[-3:].isdigit() else nm
        o.name = TMP + stem
        if o.type == 'MESH':
            o.data.name = TMP + stem
    for o in obs:
        coll.objects.link(o)
        sub.objects.unlink(o)
    bpy.data.collections.remove(sub)
    return obs


def build_condor(coll):
    root = bpy.data.objects["summit.root"]
    bird = SU.divine_condor(coll, root, log=lambda *a: log("condor", *a), nm=lambda b: TMP + "summit." + b)
    rocks = SU.condor_rocks(bird)
    return [bird] + rocks, bird, rocks


def build_ribbon(coll, bird, rocks):
    root = bpy.data.objects["summit.root"]
    em = RW.coil(coll, root, rocks[0], bird, rocks, names=[TMP + n for n in RIB_NEW], log=lambda *a: log(*a))
    return [em] + list(em.children)


def build_blinds(coll):
    pav = bpy.data.objects["summit.pavilion"]
    names = {k: TMP + v for k, v in RW.BLIND_NAMES.items()}
    em = RW.blinds(coll, pav, names=names, log=lambda *a: log(*a))
    return [em] + list(em.children)


# -------------------------------------------------------------------------------------------------- garden mask

def abode_rects():
    """abode._ground's keep-clear rects without building anything: the paved routes (abode._routes), the koi walk's
    flagstones and ledge, and the duet set (abode.duet_keep_clear)."""
    rects = []
    hw = AB.PATH_W * 0.5
    gx = AB.GATE_X
    rects.append((gx - 4.0, gx + 4.0, -51.0, -45.0, -0.2))
    rects.append((gx - hw, gx + hw, -45.0, AB.Y_FOOT, 0.1))
    rects.append((-46.0, gx - hw, -1.5, 1.5, 0.1))
    rects.append((-50.0, -44.0, -3.0, 3.0, -0.1))
    dx_, dy_, dz_ = AB.AREA["depart"][:3]
    rects.append((dx_, -50.6, dy_ - 2.5, dy_ + 2.5, dz_ + 0.02))
    rects.append((-50.7, -50.0, dy_ - 2.5, dy_ + 2.5, dz_))
    rects.append((gx - AB.STAIR_W * 0.5, gx + AB.STAIR_W * 0.5, AB.Y_FOOT, AB.Y_DECK, 0.0))
    pts, _u = AB._koi_layout()
    lx, ly = AB.KOI_LEDGE
    return rects + [(x - 0.6, x + 0.6, y - 0.6, y + 0.6, 0.0) for x, y in pts] + \
        [(lx - 1.8, lx + 1.8, ly - 1.8, ly + 1.8, 0.0)] + AB.duet_keep_clear()


def garden_mask_values(ground, rects, clear=0.8):
    return np.array([0.0 if any(AB._rect_d(v.co.x, v.co.y, r) < clear for r in rects) else 1.0
                     for v in ground.data.vertices], np.float32)


def duet_zone(loc, yaw, scale, clear=0.8):
    """Plan box (x0, x1, y0, y1) of the duet's keep-clear zone at a place, grown by ``clear``."""
    keep = AB.DUET_LOC, AB.DUET_YAW, AB.DUET_SCALE
    AB.DUET_LOC, AB.DUET_YAW, AB.DUET_SCALE = loc, yaw, scale
    try:
        r = AB.duet_keep_clear()[0]
    finally:
        AB.DUET_LOC, AB.DUET_YAW, AB.DUET_SCALE = keep
    return (r[0] - clear - 1.0, r[1] + clear + 1.0, r[2] - clear - 1.0, r[3] + clear + 1.0)


# ----------------------------------------------------------------------------------------------- scatter records

def instances_of(dg, names):
    """{scatter object name: (n, 3) instance positions} of the evaluated scatter objects."""
    out = {n: [] for n in names}
    for inst in dg.object_instances:
        if not inst.is_instance or inst.parent is None:
            continue
        p = inst.parent.original.name
        if p in out:
            out[p].append(tuple(inst.matrix_world.translation))
    return {k: np.array(v) if v else np.zeros((0, 3)) for k, v in out.items()}


def subset_report(before, after, tol=1e-3):
    """(kept, removed, added) instance counts: every 'after' position matched in 'before'."""
    if not len(after):
        return 0, len(before), 0
    if not len(before):
        return 0, 0, len(after)
    from mathutils import kdtree
    kd = kdtree.KDTree(len(before))
    for i, p in enumerate(before):
        kd.insert(p, i)
    kd.balance()
    added = sum(1 for p in after if kd.find(p)[2] > tol)
    return len(after) - added, len(before) - (len(after) - added), added


# ------------------------------------------------------------------------------------------------- view helpers

def projector(sc, cam, Mw):
    fr = cam.data.view_frame(scene=sc)
    tr, _br, bl, tl = fr
    inv = Mw.inverted()

    def proj(p):
        q = inv @ Vector(p)
        if q.z >= -1e-6:
            return None
        s = tl.z / q.z
        return ((q.x * s - tl.x) / (tr.x - tl.x) * RES[0], (q.y * s - tl.y) / (bl.y - tl.y) * RES[1])
    return proj


def screen_box(proj, pts):
    P = [proj(p) for p in pts]
    P = [p for p in P if p is not None]
    if not P:
        return None
    xs, ys = [p[0] for p in P], [p[1] for p in P]
    return min(xs), max(xs), min(ys), max(ys)


def mesh_world_pts(ob, step=1):
    M = ob.matrix_world
    vs = ob.data.vertices
    return [M @ vs[i].co for i in range(0, len(vs), step)]


def seen_share(sc, dg, eye, pts, own):
    """Share of world points ``pts`` a ray from ``eye`` reaches on an object of ``own`` (names) first."""
    seen = 0
    for p in pts:
        d = p - eye
        hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, eye, d.normalized(), distance=d.length + 0.05)
        seen += bool(hit and ob is not None and getattr(ob, "original", ob).name in own)
    return seen / max(1, len(pts))


# ----------------------------------------------------------------------------------------------- the coplanar scan

def scan(dg, pieces, label):
    """{piece: {other: [same <=5 mm, same 5-12 mm, same 12-20 mm, back-to-back <=5 mm]}} m2 of parallel faces of each
    (name, sample step) piece against itself and everything whose box meets its own (as patch_r32_plaque's scan)."""
    t0 = time.time()
    rows = {}
    for nm, step in pieces:
        ob = bpy.data.objects.get(nm)
        if ob is None or ob.type != 'MESH':
            continue
        rng = np.random.default_rng(zlib.crc32(nm.encode()))
        oe = ob.evaluated_get(dg)
        me = oe.to_mesh()
        L = local_tris(me)
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
            if own == nm or own.startswith(CLEAR_SKIP):
                continue
            W = np.array(inst.matrix_world)
            bb = np.array(o.bound_box) @ W[:3, :3].T + W[:3, 3]
            if (bb.min(0) > hi).any() or (bb.max(0) < lo).any():
                continue
            Lo = local_tris(o.data)
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
            k = int(min(200, max(1, round(ar[t] / (step * step)))))
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
        top = sorted(r.items(), key=lambda kv: -sum(kv[1]))[:4]
        log("scan %s %s: same-facing within 5 mm %.3f m2, 5-12 mm %.3f m2, 12-20 mm %.3f m2; back-to-back within 5 mm "
            "%.3f m2%s" % (label, nm, tot[0], tot[1], tot[2], tot[3], "".join(
                "; %s %.3f + %.3f + %.3f / %.3f" % (o, a, b, c_, d_) for o, (a, b, c_, d_) in top
                if a + b + c_ + d_ >= 0.001)))
    log("scan %s: %d pieces, %.1f s" % (label, len(rows), time.time() - t0))
    return rows


SCAN_STEPS = dict([("mirror.flute_stand", 0.02), ("mirror.flute_xiao", 0.01), ("mirror.flute_tassel", 0.008),
                   ("mirror.siguoya", 0.1), ("summit.condor_crag", 0.1), ("summit.condor_cap", 0.06),
                   ("summit.condor_crag_rock", 0.06), ("summit.condor_crag_rock.001", 0.06),
                   ("summit.condor_bird", 0.03), ("summit.ribbon_silk", 0.02), ("summit.ribbon_bells", 0.01),
                   ("summit.blinds_bamboo", 0.05), ("summit.blinds_gauze", 0.06), ("summit.blinds_ties", 0.02),
                   ("summit.qin_table", 0.03), ("summit.qin", 0.02), ("summit.qin_lamp", 0.02)] +
                  [(n, 0.03) for n in DUET_NAMES[1:]])


# ----------------------------------------------------------------------------------------------------------- checks

def check_pieces(names, fail):
    for nm in names:
        ob = bpy.data.objects.get(nm)
        if ob is None:
            fail.add("%s missing" % nm)
            continue
        if ob.type != 'MESH':
            continue
        t, oe = tris(ob.data), open_edges(ob.data)
        slots = [s.material.name if s.material else None for s in ob.material_slots]
        log("piece %s: %d triangles, %d open edges, slots %s, parent %s" % (nm, t, oe, slots,
                                                                         ob.parent.name if ob.parent else None))
        if t > TRI_CAP:
            fail.add("%s has %d triangles > %d" % (nm, t, TRI_CAP))
        if oe and nm not in OPEN_OK:
            fail.add("%s is not closed (%d open edges)" % (nm, oe))
        if not slots or None in slots:
            fail.add("%s has an empty material slot" % nm)


def allowed(nm, other):
    for a in ALLOW.get(nm, ()):
        if other == a or other.startswith(a + ".") or (a.endswith(".") and other.startswith(a)):
            return True
    return False


def check_clear(dg, names, fail):
    """Each piece touches only what ALLOW lets it and keeps CLEAR_MIN from everything else."""
    for nm in names:
        ob = bpy.data.objects.get(nm)
        if ob is None or ob.type != 'MESH':
            continue
        T = world_tris(dg, owners={nm}).get(nm)
        if T is None:
            continue
        lo, hi = T.reshape(-1, 3).min(0) - 0.3, T.reshape(-1, 3).max(0) + 0.3
        tA = bvh(T)
        rows = []
        for o, To in world_tris(dg, near=(lo, hi), skip={nm}).items():
            tB = bvh(To)
            touch = len(tA.overlap(tB))
            V = To.reshape(-1, 3)
            sub = V[::max(1, len(V) // 4000)]
            d = min(tA.find_nearest(Vector(p))[3] for p in sub) if len(sub) else 9.0
            VA = T.reshape(-1, 3)
            d = min(d, min(tB.find_nearest(Vector(p))[3] for p in VA[::max(1, len(VA) // 4000)]))
            rows.append((d, o, touch))
            if (touch or d < CLEAR_MIN) and not allowed(nm, o):
                fail.add("%s: %s is %.3f m from it (%d crossing triangle pairs)" % (nm, o, d, touch))
        rows.sort()
        log("clear %s: nearest %s" % (nm, ", ".join("%s %.3f m%s" % (o, d, " (meets %d)" % t if t else "")
                                                   for d, o, t in rows[:5]) or "nothing within 0.3 m"))


def down_hit(tree, p, up=0.5, far=2.0):
    h = tree.ray_cast(Vector(p) + Vector((0, 0, up)), Vector((0, 0, -1)), far)
    return None if h[0] is None else h[0].z


def check_floor(dg, nm, floor_owner, z_local_max, fail, sink_max=0.03, label=""):
    """Every vertex of ``nm`` within ``z_local_max`` of its lowest point stands on ``floor_owner`` (a ray down from
    just above it meets the floor between sink_max below and 2 mm above the point... the point is at or under the
    floor's top, no deeper than sink_max)."""
    ob = bpy.data.objects[nm]
    M = ob.matrix_world
    vs = [M @ v.co for v in ob.data.vertices]
    zmin = min(v.z for v in vs)
    sole = [v for v in vs if v.z < zmin + z_local_max]
    fo = bpy.data.objects.get(floor_owner)
    own = {floor_owner} | ({c.name for c in fo.children_recursive} if fo is not None else set())
    got = world_tris(dg, owners=own)
    if not got:
        fail.add("%s: no %s" % (nm, floor_owner))
        return
    tr = bvh(np.concatenate(list(got.values())))
    gaps = []
    for v in sole:
        z = down_hit(tr, v, up=0.6, far=3.0)
        gaps.append(9.0 if z is None else v.z - z)
    worst_hover, deepest = max(gaps), min(gaps)
    log("grounded %s%s: %d sole points on %s, highest %.4f m over it, deepest %.4f m in it" % (
        nm, label, len(sole), floor_owner, worst_hover, -deepest))
    if worst_hover > 0.002 or deepest < -sink_max:
        fail.add("%s: its sole is %.4f m over / %.4f m into %s" % (nm, worst_hover, -deepest, floor_owner))


def cleanup(sc, had_eval, meshes0):
    """Drop what the builders leave behind: props' private evaluation scene (when the file had none), its temporary
    text objects, and unused scratch / glyph meshes made in this run."""
    if not had_eval:
        s_ = bpy.data.scenes.get(P._EVAL_SCENE)
        if s_ is not None and s_ != sc:
            for o in list(s_.objects):
                if o.name.startswith("props_tmp"):
                    bpy.data.objects.remove(o, do_unlink=True)
            if not len(s_.objects):
                bpy.data.scenes.remove(s_)
    for m in list(bpy.data.meshes):
        if m.users == 0 and m.name not in meshes0 and (m.name.startswith(TMP) or m.name.startswith("props.txt.")):
            bpy.data.meshes.remove(m)


# ------------------------------------------------------------------------------------------------------------- main

def digest(names, extra=b""):
    h = hashlib.md5()
    for nm in sorted(names):
        ob = bpy.data.objects.get(nm)
        h.update(nm.encode())
        if ob is not None:
            h.update(obj_sig(ob).encode())
    h.update(extra)
    return h.hexdigest()


def main():
    dry, do_scan = options()
    t0 = time.time()
    fail = Fail()
    sc = bpy.context.scene
    keep_frame = sc.frame_current
    need = ["mirror.root", "mirror.ting", "mirror.mirror_stand", "world.range", "abode.root", "abode.ground",
            "summit.root", "summit.pavilion", EW.CAMERA]
    miss = [n for n in need if bpy.data.objects.get(n) is None]
    if miss:
        log("NOT SAVED: %s not found: is this out/sect_chase.blend?" % miss)
        raise SystemExit(1)
    from sect.lib import condor_props as CP
    if CP.missing_assets():
        log("NOT SAVED: condor assets missing: %s" % CP.missing_assets())
        raise SystemExit(1)
    colls = {k: bpy.data.collections.get(k) for k in ("mirror", "abode", "summit")}
    if None in colls.values():
        log("NOT SAVED: area collections missing: %s" % colls)
        raise SystemExit(1)
    n_obj0 = len(bpy.data.objects)
    names0 = {o.name for o in bpy.data.objects}
    scenes0 = sorted(s.name for s in bpy.data.scenes)
    had_eval = bpy.data.scenes.get(P._EVAL_SCENE) is not None
    meshes0 = {m.name for m in bpy.data.meshes}
    cam = bpy.data.objects[EW.CAMERA]
    rng = bpy.data.objects["world.range"]
    mroot = bpy.data.objects["mirror.root"]
    pav = bpy.data.objects["summit.pavilion"]
    ground = bpy.data.objects["abode.ground"]
    log("sources: flute scale %.2f offset %.2f; 思過崖 cell %.1f m at %s az %.1f deg; duet at %s yaw %.1f scale %.2f; "
        "condor at r %.1f, %.1f deg, top %.1f, bird x%.2f; coil %.2f m wide, %.2f turns; blinds on %s, open %d" % (
            RW.FLUTE_SCALE, RW.FLUTE_OFFSET, RW.SIGUOYA_CELL, RW.SIGUOYA_AT, math.degrees(RW.SIGUOYA_AZ),
            AB.DUET_LOC, math.degrees(AB.DUET_YAW), AB.DUET_SCALE, SU.CONDOR_SITE[0],
            math.degrees(SU.CONDOR_SITE[1]), SU.CONDOR_CRAG["top"], SU.CONDOR_SCALE, RW.COIL_W, RW.COIL_TURNS,
            RW.BLIND_HALF, RW.BLIND_OPEN))
    dg = bpy.context.evaluated_depsgraph_get()
    scatters = [o.name for o in rng.children if any(m.type == 'NODES' for m in o.modifiers)]
    garden = "abode.garden_scatter"
    inst0 = instances_of(dg, scatters + [garden])
    log("range scatters %s: %s instances; %s: %d" % (
        ", ".join(scatters), "/".join(str(len(inst0[s])) for s in scatters), garden, len(inst0[garden])))

    # ---- states: build every group in scratch and compare
    st = {}
    tb = time.time()
    sx_flute = build_flute(colls["mirror"])
    old_flute = [n for n in RW.FLUTE_OLD if bpy.data.objects.get(n) is not None]
    if bpy.data.objects.get("mirror.flute_rock") is not None:
        st["flute"] = "old"
    elif bpy.data.objects.get("mirror.flute_stand") is not None:
        c = compare(FLUTE_NEW, sx_flute)
        st["flute"] = "new" if c == "new" else "stale"
        if c != "new":
            log("flute differs: %s" % c)
    else:
        st["flute"] = "unknown"
    sx_sig = build_siguoya(colls["mirror"])
    if bpy.data.objects.get(SIG) is None:
        st["siguoya"] = "old"
    else:
        c = compare([SIG], sx_sig)
        st["siguoya"] = "new" if c == "new" else "stale"
    face_m = RW.local_matrix(sx_sig[0], mroot)
    idx = RW.siguoya_clear_faces(rng, mroot, face_m)
    me = rng.data
    mask_vals = {}
    for a in RW.CLEAR_ATTRS:
        at = me.attributes.get(a)
        if at is None or at.domain != 'FACE':
            continue
        v = np.empty(len(me.polygons), np.float32)
        at.data.foreach_get("value", v)
        mask_vals[a] = v
    live = {a: int((v[idx] > 0.5).sum()) for a, v in mask_vals.items()}
    st["masks"] = "old" if any(live.values()) else "new"
    log("range masks round 思過崖: %d faces; trees on them now %s" % (len(idx), live))
    st["ribbon_abode"] = "old" if any(bpy.data.objects.get(n) for n in RIB_OLD) else "new"
    duet = bpy.data.objects.get(AB.DUET)
    sx_duet = build_duet(colls["abode"])
    if duet is None:
        st["duet"] = "unknown"
    else:
        at_r5 = (abs(duet.location.x - AB.DUET_LOC_R5[0]) < 1e-4 and abs(duet.location.y - AB.DUET_LOC_R5[1]) < 1e-4
                 and abs(duet.rotation_euler.z - AB.DUET_YAW_R5) < 1e-5 and abs(duet.scale.x - AB.DUET_SCALE_R5) < 1e-6)
        if at_r5:
            st["duet"] = "old"
        else:
            c = compare(DUET_NAMES, sx_duet)
            st["duet"] = "new" if c == "new" else "stale"
            if c != "new":
                log("duet differs: %s" % c)
    rects = abode_rects()
    gm_new = garden_mask_values(ground, rects)
    gat = ground.data.attributes.get("garden_mask")
    gm_have = np.empty(len(ground.data.vertices), np.float32)
    gat.data.foreach_get("value", gm_have)
    st["garden"] = "new" if np.array_equal(gm_new, gm_have) else "old"
    z_old = duet_zone(AB.DUET_LOC_R5, AB.DUET_YAW_R5, AB.DUET_SCALE_R5)
    z_new = duet_zone(AB.DUET_LOC, AB.DUET_YAW, AB.DUET_SCALE)
    co = np.array([v.co[:2] for v in ground.data.vertices])

    def in_zone(z):
        return (co[:, 0] >= z[0]) & (co[:, 0] <= z[1]) & (co[:, 1] >= z[2]) & (co[:, 1] <= z[3])
    zones = in_zone(z_old) | in_zone(z_new)
    outside = int((gm_new[~zones] != gm_have[~zones]).sum())
    log("garden_mask: %d of %d vertices change (%d outside the duet's old and new places: abode._routes' rects "
        "rebuilt here must match the file's)" % (int((gm_new != gm_have).sum()), len(gm_new), outside))
    if outside:
        fail.add("garden_mask: %d vertices away from the duet differ from abode._ground's rule" % outside)
    crag = bpy.data.objects.get("summit.condor_crag")
    sx_condor, sx_bird, sx_rocks = build_condor(colls["summit"])
    sx_rib = build_ribbon(colls["summit"], sx_bird, sx_rocks)
    if crag is None:
        st["condor"] = "unknown"
    else:
        r7 = (SU.CONDOR_SITE_R7[0] * math.cos(SU.CONDOR_SITE_R7[1]), SU.CONDOR_SITE_R7[0] * math.sin(SU.CONDOR_SITE_R7[1]))
        if abs(crag.location.x - r7[0]) < 1e-3 and abs(crag.location.y - r7[1]) < 1e-3:
            st["condor"] = "old"
        else:
            c = compare(CONDOR_NAMES, sx_condor)
            st["condor"] = "new" if c == "new" else "stale"
            if c != "new":
                log("condor differs: %s" % c)
    if bpy.data.objects.get(RW.RIBBON) is None:
        st["ribbon"] = "old"
    else:
        c = compare(RIB_NEW, sx_rib)
        st["ribbon"] = "new" if c == "new" else "stale"
    bench = RW.bench_on(pav, RW.BLIND_OPEN)
    st["bench"] = "old" if bench is not None else "new"
    sx_bl = build_blinds(colls["summit"])
    if bpy.data.objects.get(RW.BLINDS) is None:
        st["blinds"] = "old"
    else:
        c = compare(BLIND_NEW, sx_bl)
        st["blinds"] = "new" if c == "new" else "stale"
    log("states: %s (scratch builds %.1f s)" % (", ".join("%s %s" % kv for kv in st.items()), time.time() - tb))
    if "unknown" in st.values():
        for o in scratch_objects():
            bpy.data.objects.remove(o, do_unlink=True)
        log("NOT SAVED: the file is not in a state this patch knows")
        raise SystemExit(1)
    todo = any(v != "new" for v in st.values())

    # ---- the coplanar scan of the pieces this patch rebuilds (the duet, the condor), as they are now
    scan0 = {}
    if do_scan:
        dg = bpy.context.evaluated_depsgraph_get()
        scan0 = scan(dg, [(n, SCAN_STEPS.get(n, 0.05)) for n in DUET_NAMES[1:] + CONDOR_NAMES
                          if bpy.data.objects.get(n) is not None], "before")
    duet_s0 = bpy.data.objects[AB.DUET].scale.x if bpy.data.objects.get(AB.DUET) else AB.DUET_SCALE

    # ---- apply
    removed, added = [], []

    def put(group, olds, scratch, finals):
        if st[group] == "new":
            for o in scratch:
                bpy.data.objects.remove(o, do_unlink=True)
            return
        removed.extend(remove_objects(olds, "(%s, %s)" % (group, st[group])))
        take_names(scratch)
        added.extend(finals)
        log("%s: built %s" % (group, ", ".join(finals)))
    put("flute", old_flute if st["flute"] == "old" else FLUTE_NEW, sx_flute, FLUTE_NEW)
    put("siguoya", [SIG], sx_sig, [SIG])
    if st["masks"] == "old":
        RW.siguoya_clear(rng, mroot, RW.local_matrix(bpy.data.objects[SIG], mroot), log=lambda *a: log(*a))
    if st["ribbon_abode"] == "old":
        removed.extend(remove_objects(RIB_OLD, "(the abode's ribbon)"))
    put("duet", DUET_NAMES, sx_duet, DUET_NAMES)
    if st["garden"] == "old":
        gat.data.foreach_set("value", gm_new)
        ground.data.update()
        log("garden_mask rewritten for the duet's place")
    # the ribbon stands on the condor's rock: both go in together
    if st["condor"] != "new" or st["ribbon"] != "new":
        st["condor"] = st["condor"] if st["condor"] != "new" else "stale"
        st["ribbon"] = st["ribbon"] if st["ribbon"] != "new" else "stale"
    put("condor", CONDOR_NAMES, sx_condor, CONDOR_NAMES)
    put("ribbon", RIB_NEW, sx_rib, RIB_NEW)
    if st["bench"] == "old":
        removed.extend(remove_objects([bench.name], "(the open bay's bench)"))
    put("blinds", BLIND_NEW, sx_bl, BLIND_NEW)
    left = scratch_objects()
    if left:
        fail.add("scratch objects left: %s" % [o.name for o in left][:6])
    cleanup(sc, had_eval, meshes0)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()

    # ---- checks
    new_meshes = [n for n in FLUTE_NEW + [SIG] + DUET_NAMES + CONDOR_NAMES + RIB_NEW + BLIND_NEW
                  if bpy.data.objects.get(n) is not None and bpy.data.objects[n].type == 'MESH']
    check_pieces(FLUTE_NEW + [SIG] + DUET_NAMES + CONDOR_NAMES + RIB_NEW + BLIND_NEW, fail)
    check_clear(dg, new_meshes, fail)
    # grounded
    check_floor(dg, "mirror.flute_stand", "mirror.ting.platform", 0.01, fail, sink_max=0.02)
    check_floor(dg, "summit.qin_table", "summit.pavilion.platform", 0.005, fail, sink_max=0.02)
    check_floor(dg, "summit.qin_lamp", "summit.pavilion.platform", 0.005, fail, sink_max=0.02)
    xiao = bpy.data.objects["mirror.flute_xiao"]
    stand = bpy.data.objects["mirror.flute_stand"]
    Ts = world_tris(dg, owners={stand.name})[stand.name]
    Tx = world_tris(dg, owners={xiao.name})[xiao.name]
    gap = min(bvh(Ts).find_nearest(Vector(p))[3] for p in Tx.reshape(-1, 3)[::3])
    log("flute: %.4f m from its stand at the nearest (rests in the cradles)" % gap)
    if gap > 0.004:
        fail.add("the flute floats %.4f m over its stand" % gap)
    bird = bpy.data.objects["summit.condor_bird"]
    cap = bpy.data.objects["summit.condor_cap"]
    Tc = bvh(world_tris(dg, owners={cap.name})[cap.name])
    Mb = bird.matrix_world
    toes = [Mb @ Vector((x, y, 0.0)) for x, y in CP.toe_points()]
    tg = [(p.z - (down_hit(Tc, p, 1.0, 3.0) or -99.0)) for p in toes]
    log("condor: %d toes, highest %.3f m over the capstone, deepest %.3f m in it" % (len(tg), max(tg), -min(tg)))
    if max(tg) > SU.CONDOR_MAX_TOE_GAP:
        fail.add("a toe floats %.3f m over the capstone" % max(tg))
    crag_t = bvh(world_tris(dg, owners={"summit.condor_crag"})["summit.condor_crag"])
    for nm in ("summit.condor_cap", "summit.condor_crag_rock", "summit.condor_crag_rock.001"):
        ob = bpy.data.objects[nm]
        Mw = ob.matrix_world
        zs = [v.co.z for v in ob.data.vertices]
        z0, z1 = min(zs), max(zs)
        sole = [Mw @ v.co for v in ob.data.vertices if v.co.z < z0 + 0.06 * (z1 - z0)]
        hov = [p.z - (down_hit(crag_t, p, 3.0, 8.0) or -99.0) for p in sole]
        log("grounded %s: %d sole points, highest %.3f m over the crag" % (nm, len(sole), max(hov)))
        if max(hov) > 0.08:
            fail.add("%s hovers %.3f m over the crag" % (nm, max(hov)))
    rocks = SU.condor_rocks(bird)
    rb = bvh(np.concatenate([world_tris(dg, owners={o.name})[o.name] for o in rocks]))
    silk = bpy.data.objects["summit.ribbon_silk"]
    Tsk = world_tris(dg, owners={silk.name})[silk.name]
    meet = len(bvh(Tsk).overlap(rb))
    Ms = silk.matrix_world
    under = []
    for v in silk.data.vertices:
        p = Ms @ v.co
        z = down_hit(rb, p, 0.002, 2.0)
        if z is not None:
            under.append((p, p.z - z))
    ce = bpy.data.objects[RW.RIBBON].matrix_world.translation
    rc = RW._coil_radius() + 0.05
    flat = [u for p, u in under if p.z > ce.z - 0.05 and (p.xy - ce.xy).length <= rc]
    log("ribbon: meets its rock in %d triangle pairs; the coil's underside %.3f..%.3f m over the rock below it "
        "(%d points)" % (meet, min(flat) if flat else 0.0, max(flat) if flat else 0.0, len(flat)))
    if meet:
        fail.add("the ribbon cuts into its rock (%d triangle pairs)" % meet)
    if not flat or max(flat) > COIL_GAP_MAX + RW.COIL_T:
        fail.add("the coil floats %.3f m over its rock" % (max(flat) if flat else 9.0))
    # the duet's bases on the lawn
    lawn = bvh(world_tris(dg, owners={"abode.ground"})["abode.ground"])
    for nm in ("abode.duet_table", "abode.duet_seat_qin", "abode.duet_seat_xiao", "abode.duet_huqin"):
        ob = bpy.data.objects[nm]
        Mw = ob.matrix_world
        vs = [Mw @ v.co for v in ob.data.vertices]
        zmin = min(v.z for v in vs)
        low = [v for v in vs if v.z < zmin + 0.03]
        gl = [(v.z - (down_hit(lawn, v, 1.0, 3.0) or -99.0)) for v in low]
        log("grounded %s: lowest points %.3f..%.3f m against the lawn" % (nm, min(gl), max(gl)))
        if max(gl) > LAWN_REST.get(nm, 0.01):
            fail.add("%s stands %.3f m over the lawn" % (nm, max(gl)))
    # the dressed face's sides reach into the rock all round
    sig = bpy.data.objects[SIG]
    rt = bvh(world_tris(dg, owners={"world.range"})["world.range"])
    Mg = sig.matrix_world
    ring = [Mg @ v.co for v in sig.data.vertices if v.co.y > 0.6]   # past the chamfer: the sides' buried ends
    into = Mg.to_3x3() @ Vector((0.0, 1.0, 0.0))
    outside = 0
    for p in ring:
        h = rt.ray_cast(p, -into, 30.0)                 # from the buried end toward the viewer: rock in between
        if h[0] is None:
            outside += 1
    log("siguoya: %d of %d points of its sides' buried ends have rock in front of them" % (len(ring) - outside,
                                                                                          len(ring)))
    if outside > 0.05 * len(ring):
        fail.add("siguoya: its sides end out of the rock at %d of %d points" % (outside, len(ring)))

    # ---- trees: only instances on the cleared faces go; none in front of the characters
    inst1 = instances_of(dg, scatters + [garden])
    for s in scatters:
        kept, gone, add = subset_report(inst0[s], inst1[s])
        log("trees %s: %d kept, %d gone, %d new" % (s, kept, gone, add))
        if add:
            fail.add("%s: %d instances moved or appeared" % (s, add))
    kept, gone, add = subset_report(inst0[garden], inst1[garden])
    log("trees %s: %d kept, %d gone, %d new (round the duet's old and new places)" % (garden, kept, gone, add))
    Ag = np.array(bpy.data.objects["abode.root"].matrix_world.inverted())
    for label, pts in (("gone", [p for p in inst0[garden] if not len(inst1[garden]) or
                                 np.min(np.linalg.norm(inst1[garden] - p, axis=1)) > 1e-3]),
                       ("new", [p for p in inst1[garden] if not len(inst0[garden]) or
                                np.min(np.linalg.norm(inst0[garden] - p, axis=1)) > 1e-3])):
        far = 0
        for p in pts:
            q = Ag[:3, :3] @ np.array(p) + Ag[:3, 3]
            if not ((z_old[0] <= q[0] <= z_old[1] and z_old[2] <= q[1] <= z_old[3]) or
                    (z_new[0] <= q[0] <= z_new[1] and z_new[2] <= q[1] <= z_new[3])):
                far += 1
        if far:
            fail.add("%s: %d %s instances away from the duet's places" % (garden, far, label))

    # ---- reading at the holds (as the site frames them)
    rx, ry, rp = sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES[0], RES[1], 100
    try:
        Mw = RW.site_view(sc, cam, 217)
        dg = bpy.context.evaluated_depsgraph_get()
        proj = projector(sc, cam, Mw)
        eye = Mw.translation.copy()
        regions, boxes = RW._glyph_regions(RW.font_path())
        Fm = sig.matrix_world
        for k, (ch, (x0, x1, z0, z1)) in enumerate(zip(RW.SIGUOYA_TEXT, boxes)):
            pts = [Fm @ Vector((x, RW.SIGUOYA_CUT - 0.01, z)) for poly, _t in regions
                   for x, z in [((sum(p[0] for p in poly) / len(poly)), (sum(p[1] for p in poly) / len(poly)))]
                   if z0 - 1e-6 <= sum(p[1] for p in poly) / len(poly) <= z1 + 1e-6][::3]
            corners = [Fm @ Vector((x, 0.0, z)) for x in (x0, x1) for z in (z0, z1)]
            bx = screen_box(proj, corners)
            seen = seen_share(sc, dg, eye, pts, {SIG})
            inside = bx is not None and bx[0] >= 0 and bx[1] <= RES[0] and bx[2] >= 0 and bx[3] <= RES[1]
            log("read 217 %s: x %.0f..%.0f y %.0f..%.0f, %.0f px tall, %.0f%% of %d points unhidden, %.1f m" % (
                ch, bx[0], bx[1], bx[2], bx[3], bx[3] - bx[2], 100 * seen, len(pts), (corners[0] - eye).length))
            if not inside or bx[3] - bx[2] < READ_MIN_PX or seen < READ_SEEN:
                fail.add("%s does not read at the mirror's hold (%.0f px, %.0f%% unhidden)" % (ch, bx[3] - bx[2],
                                                                                              100 * seen))
        for nm in ("mirror.flute_xiao", "mirror.flute_stand"):
            ob = bpy.data.objects[nm]
            pts = mesh_world_pts(ob, max(1, len(ob.data.vertices) // 120))
            bx = screen_box(proj, pts)
            seen = seen_share(sc, dg, eye, pts, {nm})
            log("read 217 %s: x %.0f..%.0f y %.0f..%.0f (%.0f x %.0f px), %.0f%% of %d points seen" % (
                nm, bx[0], bx[1], bx[2], bx[3], bx[1] - bx[0], bx[3] - bx[2], 100 * seen, len(pts)))
            if seen < 0.15:
                fail.add("%s is hidden at the mirror's hold (%.0f%% seen)" % (nm, 100 * seen))
        for frame, names_ in ((1380, DUET_NAMES[1:]), (1647, ["summit.condor_bird", "summit.ribbon_silk",
                                                            "summit.blinds_bamboo", "summit.blinds_gauze",
                                                            "summit.qin", "summit.qin_table", "summit.qin_lamp"]),
                              (1625, ["summit.condor_bird", "summit.condor_crag"])):
            Mw = RW.site_view(sc, cam, frame)
            dg = bpy.context.evaluated_depsgraph_get()
            proj = projector(sc, cam, Mw)
            eye = Mw.translation.copy()
            for nm in names_:
                ob = bpy.data.objects[nm]
                pts = mesh_world_pts(ob, max(1, len(ob.data.vertices) // 150))
                bx = screen_box(proj, pts)
                seen = seen_share(sc, dg, eye, pts, {nm})
                log("read %d %s: x %.0f..%.0f y %.0f..%.0f (%.0f x %.0f px), %.0f%% of %d points seen, %.1f m" % (
                    frame, nm, bx[0], bx[1], bx[2], bx[3], bx[1] - bx[0], bx[3] - bx[2], 100 * seen, len(pts),
                    (ob.matrix_world.translation - eye).length))
                if frame != 1625 and (bx[0] < 0 or bx[1] > RES[0] or bx[2] < 0 or bx[3] > RES[1] or seen < 0.1):
                    fail.add("%s is not seen at %d (box %s, %.0f%% seen)" % (nm, frame, [round(v) for v in bx],
                                                                          100 * seen))
                if frame == 1647 and nm == "summit.condor_bird":
                    px0, px1, py0, py1 = PANEL_SUMMIT
                    under = bx[0] < px1 and bx[1] > px0 and bx[2] < py1 and bx[3] > py0
                    if under or bx[1] > VOICE_X or bx[3] - bx[2] < 45:
                        fail.add("the bird at 1647: box %s (under the panel %s, %.0f px tall)" % (
                            [round(v) for v in bx], under, bx[3] - bx[2]))
            if frame == 1625:
                # how much of the pavilion the crag hides there
                pv = [p for o in [pav] + list(pav.children_recursive) if o.type == 'MESH'
                      for p in mesh_world_pts(o, max(1, len(o.data.vertices) // 40))]
                vis = 0
                hid = 0
                cr = {"summit.condor_crag", "summit.condor_cap", "summit.condor_bird", "summit.condor_crag_rock",
                      "summit.condor_crag_rock.001", "summit.ribbon_silk", "summit.ribbon_bells"}
                for p in pv:
                    d = p - eye
                    hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, eye, d.normalized(), distance=d.length + 0.05)
                    nmh = getattr(ob, "original", ob).name if hit and ob is not None else None
                    if nmh in cr:
                        hid += 1
                    elif nmh is not None:
                        vis += 1
                log("read 1625: the crag and bird hide %d of %d sampled points of the pavilion (%.0f%%)" % (
                    hid, len(pv), 100.0 * hid / max(1, len(pv))))
    finally:
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, rp
        sc.frame_set(keep_frame)
    # ---- flight clearance (every frame)
    near = {}
    trees_ = {}
    for nm in new_meshes:
        T = world_tris(dg, owners={nm}).get(nm)
        if T is not None:
            trees_[nm] = bvh(T)
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)
        p = cam.matrix_world.translation.copy()
        for nm, tr in trees_.items():
            h = tr.find_nearest(p)
            if h[0] is not None and (nm not in near or h[3] < near[nm][0]):
                near[nm] = (h[3], f)
    sc.frame_set(keep_frame)
    for nm in sorted(near, key=lambda n: near[n][0]):
        d, f = near[nm]
        lim = CAM_MIN if nm in CONDOR_NAMES else CAM_NEAR
        if d < lim + 25.0:
            log("flight: %s %.1f m from chase.cam at its nearest (frame %d)" % (nm, d, f))
        if d < lim:
            fail.add("chase.cam passes %.1f m from %s (frame %d), want %.0f m" % (d, nm, f, lim))
    log("flight: nearest of all %s" % (", ".join("%s %.1f m" % (n, near[n][0]) for n in
                                                  sorted(near, key=lambda n: near[n][0])[:4])))
    # ---- coplanar scan
    dg = bpy.context.evaluated_depsgraph_get()
    if do_scan:
        rows = scan(dg, [(n, SCAN_STEPS.get(n, 0.05)) for n in new_meshes], "after")
        k2 = (AB.DUET_SCALE / duet_s0) ** 2
        for nm, rr in rows.items():
            for other, (a, b, c_, d_) in rr.items():
                # what the piece may have: a rebuilt piece what it had (the duet's grown by its new scale squared;
                # the summit's qin what the duet's qin, the same geometry, had at its scale), a new one NEW_MAX
                if nm in DUET_NAMES:
                    w = scan0.get(nm, {}).get(other, [0.0] * 4)
                    have, key = (w[0] + w[1]) * k2, "%s before x %.2f" % (nm, k2)
                elif nm in CONDOR_NAMES:
                    w = scan0.get(nm, {}).get(other, [0.0] * 4)
                    have, key = w[0] + w[1], "%s before" % nm
                elif nm == "summit.qin" and other == "<self>":
                    w = scan0.get("abode.duet_qin", {}).get("<self>", [0.0] * 4)
                    have, key = (w[0] + w[1]) * (RW.QIN_SCALE / duet_s0) ** 2, "the duet's qin before"
                else:
                    have, key = 0.0, "new"
                if a + b + c_ + d_ >= 0.001 or have >= 0.001:
                    log("scan %s / %s: same-facing %.3f + %.3f (+ %.3f at 12-20 mm), back-to-back %.3f; may have "
                        "%.3f (%s)" % (nm, other, a, b, c_, d_, have, key))
                if a + b > have + NEW_MAX:
                    fail.add("same-facing overlap %s / %s: %.3f + %.3f m2 (may have %.3f)" % (nm, other, a, b, have))
    # ---- names and counts
    cleanup(sc, had_eval, meshes0)
    names1 = {o.name for o in bpy.data.objects}
    gone, came = sorted(names0 - names1), sorted(names1 - names0)
    log("objects %d -> %d: removed %s; added %s" % (n_obj0, len(bpy.data.objects), gone, came))
    want_gone = set(removed) - set(added)
    want_came = set(added) - set(removed)
    if set(gone) != want_gone or set(came) != want_came:
        fail.add("objects removed %s / added %s, expected %s / %s" % (gone, came, sorted(want_gone), sorted(want_came)))
    left = [o.name for o in bpy.data.objects if o.name.startswith(TMP)] + \
        [m.name for m in bpy.data.meshes if m.name.startswith(TMP)] + \
        [c.name for c in bpy.data.collections if c.name.startswith(TMP)]
    if left:
        fail.add("scratch data left: %s" % left[:8])
    scenes1 = sorted(s.name for s in bpy.data.scenes)
    if scenes1 != scenes0:
        fail.add("scenes %s -> %s" % (scenes0, scenes1))
    me = rng.data
    extra = b""
    for a in RW.CLEAR_ATTRS:
        at = me.attributes.get(a)
        if at is not None and at.domain == 'FACE':
            v = np.empty(len(me.polygons), np.float32)
            at.data.foreach_get("value", v)
            extra += a.encode() + np.round(v[idx], 4).tobytes()
    v = np.empty(len(ground.data.vertices), np.float32)
    ground.data.attributes["garden_mask"].data.foreach_get("value", v)
    extra += v.tobytes()
    extra += repr(sorted(n for n in RIB_OLD + tuple(RW.FLUTE_OLD) if bpy.data.objects.get(n) is not None)).encode()
    log("DIGEST", digest(FLUTE_NEW + [SIG] + DUET_NAMES + CONDOR_NAMES + RIB_NEW + BLIND_NEW, extra))
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail:
            log("  -", f)
        raise SystemExit(1)
    if todo:
        log("CACHES needs audit: new %s; moved %s; removed %s - run export_web.py -- audit --profile full, then "
            "-- chunks,meta --profile full (LORE and ABODE_FACTS[3] need the lore lane's names first), then "
            "bake_web.py -- bakefull --profile full --chunks mirror,abode,summit,backdrop, then the trees "
            "(bake_trees.py plan, build, verify: the mirror's sapling, the range's pines round 思過崖 and the abode's "
            "garden plants changed), then pack" % (
                [n for n in FLUTE_NEW + [SIG] + RIB_NEW + BLIND_NEW if n in added],
                [n for n in DUET_NAMES + CONDOR_NAMES if n in added], sorted(set(removed) - set(added))))
    else:
        log("CACHES ok: nothing changed")
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
