"""Round 34, lane 'east': the Jin Yong references at the forge, the arena, the Mission Hall and the formation get their
new staging (the r31 references plan, as approved), in an existing out/sect_chase.blend, so it matches what a fresh
build of areas/forge.py, arena.py, mission.py and formation.py (with sect/lib/refs_east.py) makes. Run on the cloud
box, on a copy first, AFTER patch_r28_lions.py and patch_r29_forge.py:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r34_east.py [-- DRY_RUN=1] [SCAN=0]

Why (owner, 2026-10-23, the r31 plan): each reference stands at the stop whose story it shares, where such a thing
would be kept, in the part of the hold's frame the page's panel leaves open; the hover cards describe the item itself.

What it does:
- forge (hold 352): Dugu Qiubai's Sword Tomb ('forge.sword_tomb' and its five meshes) goes (it now stands at the Jade
  Slip Pavilion, another lane's patch). The Golden Wheel Lama's five wheels ('forge.five_wheels'), the anvil
  'forge.anvil' and quench trough 0 ('forge.trough.0', 'forge.trough_water.0') leave the yard's west, where the
  Projects panel covered them, for the tomb's spot: forge.py's smith's corner (SMITH_AT, SMITH_YAW: square to the
  hold camera, left of the voice button). The rack and the anvil keep their objects and meshes (moved); the trough's
  two meshes are rebuilt by forge._quench_trough (each object at its place, turned).
- arena (516): four bronze seat plates of the Five Greats 華山論劍 in the bagua ring round the taiji, at the arena's
  north, east, south and west (the sword's side is north): 'arena.seats' with 'arena.seat.north' 北丐, '.east' 東邪,
  '.south' 南帝, '.west' 西毒 (refs_east.build_seats: the gold set into the bronze), each in the place of that point's
  trigram, which comes out of the ring's mesh ('arena.bagua' gets its own mesh 'arena.bagua.seats',
  refs_east.clear_seat_trigrams; the four diagonal trigrams stay). Flush inlays, nothing stands on the floor. No plants
  grow on the island's top under the platform any more (arena.clear_plants_under_platform: its 'nature_veg' mask):
  some were taller than the 1.3 m to the floor and their tips showed through it, two of them inside the seats.
- mission (619): both holy-fire altars ('mission.holy_fire', '.001', their ten meshes and two lights) go. The
  Quanzhen Big Dipper 天罡北斗陣 comes in: seven star drums 'mission.dipper.<pinyin>' (each an Empty with '.drum':
  stone, a bronze top, the star's name in gold) and the gold lines 'mission.dipper.lines' in the open apron
  (refs_east.build_dipper).
- formation (1208): the Big Dipper's seven star-stones ('formation.dipper.<pinyin>' and their 28 meshes) and
  'formation.dipper.lines' go (their shared meshes with them). The two holy-fire altars come in, flanking the front
  paifang: 'formation.holy_fire' (east), '.001' (west), with their lights (mission.holy_fire at formation.ALTARS,
  flames turned formation.ALTAR_FRONT). The chant ring is recut in traditional characters (formation.CHANT) and set
  into the ink band: 'formation.chant' and the band 'formation.floor_band' get formation.chant_bm's meshes (the band
  cut away under every character). 'formation.chant_dots' is rebuilt the same way (same places), and
  'formation.moss' from formation._moss_spots (the star-stones' moss rings gone, none under the altars).

State: each part is 'old' (the file before round 34: the tomb, the altars at the mission, the formation's Dipper, the
simplified chant), 'r34' (exactly this build: every new or rebuilt object compared face by face, order-free, with a
scratch build of the same code) or 'stale' (round 34's objects there but not this build: rebuilt). Anything else (a
part half there) stops the patch. Idempotent: on this build's file it prints 'PATCH nothing changed: not saving' and
the same DIGEST.

Checks (any failure stops the patch before saving; DRY_RUN=1 runs everything and never saves):
- grounded: every new or moved free-standing piece's foot is on its own level, sunk 0-8 cm (rays down onto the floor
  meshes only); the star drums each wholly on one level (the apron walk or the plaza), the gold lines on theirs;
- clear: nothing new crosses or comes within CLEAR_MIN of anything but the floor it is set into (ALLOW), nor of the
  other new pieces; the forge's corner stays RUNE_GAP clear of the rune ring; no moss under an altar;
- carved: rays from each gold face straight down meet no face of its host (the plate's, the drum top's, the ink
  band's) within the gold's depth; every point of the holes' rims lies inside the gold (rays up and down meet it);
- the bagua: only whole trigram bars came out (every removed face's connected piece removed whole), four trigrams'
  worth, at the four seats;
- reading: each hold as the site frames it (refs_east.site_view, 1600 x 900): every new item wholly in frame, at least
  READ_SEEN of it unhidden, none of it under the stop's panel or the voice button (refs_east.UI_RECTS); every
  character's size is logged (seats, star names, the chant's front arc);
- flight: chase.cam (every frame) never comes nearer a new piece than CAM_MIN;
- hotspots: the touched areas' click boxes (export_web._subtree_box of the area, role, hackathon and station
  hotspots) unchanged;
- coplanar scan (SCAN=1): parallel same-facing faces within 5 mm and 5-12 mm, every new or rebuilt piece against
  itself and everything near it; at most NEW_MAX m2 gained per piece (a moved piece against its own before);
- names and counts: objects change by exactly what was removed and added; no scratch data, scene or orphan light left.
Prints 'PATCH CACHES needs audit' (objects added, removed and moved: export_web audit, then chunks,meta, then
bake_web bakefull for the forge, arena, mission and formation chunks and the backdrop, and the trees bake for the
arena chunk (its island's plants under the platform are gone), then pack) and 'PATCH DIGEST <md5>' of every object the
round touches (names, transforms, meshes face by face, slots, tags, lights) and of the arena island's plant mask.
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
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402
from sect.areas import arena as AR  # noqa: E402
from sect.areas import forge as F  # noqa: E402
from sect.areas import formation as FO  # noqa: E402
from sect.areas import mission as MI  # noqa: E402
from sect.lib import array_props as AP  # noqa: E402
from sect.lib import props as P  # noqa: E402
from sect.lib import refs_east as RE  # noqa: E402
from sect.lib import util as U  # noqa: E402

SCRATCH = "~r34e"
RES = (1600, 900)
PLACE_TOL = 1e-4
CLEAR_MIN = 0.02           # m
RUNE_GAP = 0.3             # m: the forge corner from the rune ring
CAM_MIN = 10.0             # m: chase.cam from any new piece (the arena flight passes ~12 m over the floor)
READ_SEEN = 0.9            # share of an item's points a ray from the hold camera reaches
FOOT_SINK = (0.0, 0.08)    # m: a foot this far under its level's top (0 = on it)
CARVE_DEPTH = 0.06         # m: under a gold face, no host face within this
RIM_PTS = 3
RIM_IN = 0.0005             # m: a rim point is tested this far into its hole (the gold's wall stands on the rim)
SCAN_TOL, SCAN_TOL12, SCAN_PAR = 0.0055, 0.0125, 0.985
SCAN_STEP = 0.05           # m between samples
NEW_MAX = 0.02             # m2 of same-facing parallel faces (both bands) a piece may gain
SKIP = ("world.haze", "world.range", "world.roots", "world.stream", "world.cloud")
SEE_THROUGH = ("formation.dome", "world.haze", "world.cloud", "world.mist", "world.fog")

OLD_FW = ((-24.0, -15.5), 0.96)          # the rack, the anvil and trough 0 until round 33
OLD_ANVIL = ((-13.0, -18.0), 0.4)
OLD_TROUGH = (-18.0, -15.0)
TOMB = "forge.sword_tomb"
OLD_DIPPER = ("yaoguang", "kaiyang", "yuheng", "tianquan", "tianji", "tianxuan", "tianshu")
SEAT_KEYS = [k for k, _t, _d in RE.SEATS]
BAGUA_KEY = "props.rune_ring.trigram.%s.%s.%d.v%d" % (P._k(RE.SEAT_RING[0]), P._k(RE.SEAT_RING[1]), 3,
                                                      P.RUNE_KEY_VERSION)
# what each new piece may touch: the floor it is set into
ALLOW = dict(forge=("forge.paving",), arena=("arena.platform",),
             mission=("mission.plaza", "mission.apron_front", "mission.axis"),
             formation=("formation.floor", "formation.floor_band"))


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
            raise SystemExit("patch_r34_east: unknown option %r (DRY_RUN=1, SCAN=0)" % a)
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
    """Order-free fingerprint: every face as its rounded corners (cyclic from the smallest) and material name, the
    'edge' attribute's sum, and the counts."""
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
    a = me.attributes.get(U.EDGE_ATTR)
    if a is not None and a.domain == 'FACE':
        vals = np.zeros(len(me.polygons))
        a.data.foreach_get("value", vals)
        h.update(("%.3f" % float(vals.sum())).encode())
    return h.hexdigest()


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


def tree(ob):
    return [ob] + list(ob.children_recursive)


def world_tris(dg, owners=None, near=None, skip=()):
    """{owner: (n, 3, 3) world triangles} of the evaluated scene's meshes (instances under their instancer's name):
    these owners, or those whose box meets the box ``near`` (lo, hi)."""
    out = {}
    for inst in dg.object_instances:
        o = inst.object
        if o.type != 'MESH':
            continue
        own = inst.parent.original.name if inst.is_instance and inst.parent else o.original.name
        if (owners is not None and own not in owners) or own in skip or own.startswith(SKIP):
            continue
        W = np.array(inst.matrix_world)
        if near is not None:
            bb = np.array(o.bound_box) @ W[:3, :3].T + W[:3, 3]
            if (bb.min(0) > near[1]).any() or (bb.max(0) < near[0]).any():
                continue
        L = local_tris(o.data)
        if not len(L):
            continue
        T = L @ W[:3, :3].T + W[:3, 3]
        if near is not None:
            keep = ~((T.min(1) > near[1]).any(1) | (T.max(1) < near[0]).any(1))
            T = T[keep]
            if not len(T):
                continue
        out.setdefault(own, []).append(T)
    return {k: np.concatenate(v) for k, v in out.items()}


def obj_tris(dg, names):
    T = world_tris(dg, owners=set(names))
    return np.concatenate(list(T.values())) if T else np.zeros((0, 3, 3))


def props_of(ob):
    out = {}
    for k in sorted(ob.keys()):
        if k.startswith("_"):
            continue
        v = ob[k]
        if isinstance(v, str):
            pass
        elif isinstance(v, (int, float)):
            v = round(float(v), 5)
        else:
            try:
                v = [round(float(x), 5) for x in v]
            except (TypeError, ValueError):
                v = repr(v)
        out[k] = v
    return out


def ob_sig(ob, strip=None):
    """Fingerprint of an object: (name with ``strip`` removed, local transform, parent, mesh faces / light, slots,
    props)."""
    nm = ob.name.replace(strip, "", 1) if strip else ob.name
    par = ob.parent.name.replace(strip, "", 1) if (strip and ob.parent) else (ob.parent.name if ob.parent else None)
    h = hashlib.md5()
    h.update(nm.encode())
    h.update(np.round(np.array(ob.matrix_basis), 5).tobytes())
    h.update(repr(par).encode())
    if ob.type == 'MESH':
        h.update(faces_sig(ob.data).encode())
        h.update(repr([s.material.name if s.material else None for s in ob.material_slots]).encode())
        h.update(repr(ob.data.get(RE.TAG)).encode())
    elif ob.type == 'LIGHT':
        d = ob.data
        h.update(repr((d.type, round(d.energy, 3), tuple(round(c, 4) for c in d.color), round(d.shadow_soft_size, 4),
                       bool(d.use_shadow))).encode())
    elif ob.type == 'EMPTY' and ob.instance_type == 'COLLECTION' and ob.instance_collection:
        h.update(ob.instance_collection.name.encode())
    h.update(repr(props_of(ob)).encode())
    return nm, h.hexdigest()


def sigs(obs, strip=None):
    return dict(ob_sig(o, strip) for o in obs)


def delete_tree(ob, removed):
    """Delete ``ob`` and its children (meshes and lights with no user left too); their names go to ``removed``."""
    obs = tree(ob)
    removed += [o.name for o in obs]
    lights = {o.data for o in obs if o.type == 'LIGHT'}
    U.delete_hierarchy(ob)
    for d in lights:
        if d.users == 0:
            bpy.data.lights.remove(d)


class Scratch:
    """A scratch collection for builds compared with the file's objects (removed with everything in it)."""

    def __init__(self):
        self.coll = bpy.data.collections.new(SCRATCH + ".coll")
        bpy.context.scene.collection.children.link(self.coll)

    def drop(self):
        for ob in list(self.coll.all_objects):
            d = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if d is not None and d.users == 0:
                if isinstance(d, bpy.types.Mesh):
                    bpy.data.meshes.remove(d)
                elif isinstance(d, bpy.types.Light):
                    bpy.data.lights.remove(d)
        bpy.data.collections.remove(self.coll)


def transplant(src, dst):
    """Give object ``dst`` the mesh of the scratch object ``src`` (the old mesh freed, the name kept)."""
    old = dst.data
    name = old.name
    me = src.data
    src.data = bpy.data.meshes.new(SCRATCH + ".empty")
    dst.data = me
    for s in dst.material_slots:
        if s.link != 'DATA':
            s.link = 'DATA'
    if old.users == 0:
        bpy.data.meshes.remove(old)
    me.name = name


# ------------------------------------------------------------------------------------------------------- the parts

def near(a, b, tol=PLACE_TOL):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def obj(name):
    return bpy.data.objects.get(name)


# ---- forge

def forge_scratch(sc_):
    """Trough 0 as forge.py builds it now (scratch objects) -> {'forge.trough.0': sig, 'forge.trough_water.0': sig}."""
    root = obj("forge.root")
    keep = set(o.name for o in bpy.data.objects)
    F._quench_trough(root, sc_.coll, 0, *F.smith_place("trough"))
    made = [o for o in bpy.data.objects if o.name not in keep]
    out = {}
    for o in made:
        base = "forge.trough_water.0" if "trough_water" in o.name else "forge.trough.0"
        out[base] = (faces_sig(o.data), tuple(round(v, 5) for v in o.location), round(o.rotation_euler.z, 5))
    return out


def forge_state(sc_, fail):
    fw, anv, tr, tw = (obj(n) for n in ("forge.five_wheels", "forge.anvil", "forge.trough.0", "forge.trough_water.0"))
    if None in (fw, anv, tr, tw):
        fail.add("forge: five wheels / anvil / trough 0 missing")
        return "unknown", {}
    want = forge_scratch(sc_)
    ax, ay, arz = F.smith_place("anvil")
    fw_new = near(fw.location, (F.FW_LOC[0], F.FW_LOC[1], 0.0)) and abs(fw.rotation_euler.z - F.FW_ROT_Z) < 1e-5
    fw_old = near(fw.location, (OLD_FW[0][0], OLD_FW[0][1], 0.0)) and abs(fw.rotation_euler.z - OLD_FW[1]) < 1e-5
    an_new = near(anv.location, (ax, ay, 0.0)) and abs(anv.rotation_euler.z - arz) < 1e-5
    an_old = near(anv.location, (OLD_ANVIL[0][0], OLD_ANVIL[0][1], 0.0)) and abs(anv.rotation_euler.z -
                                                                                  OLD_ANVIL[1]) < 1e-5
    tr_new = all((faces_sig(o.data), tuple(round(v, 5) for v in o.location), round(o.rotation_euler.z, 5)) ==
                 want[n] for n, o in (("forge.trough.0", tr), ("forge.trough_water.0", tw)))
    co = np.array([v.co for v in tr.data.vertices])
    tr_old = near(tr.location, (0.0, 0.0, 0.0)) and abs(tr.rotation_euler.z) < 1e-6 and \
        near(((co[:, 0].min() + co[:, 0].max()) / 2, (co[:, 1].min() + co[:, 1].max()) / 2), OLD_TROUGH, 1e-3)
    tomb = obj(TOMB) is not None
    log("forge: tomb %s; five wheels at %s turned %.4f (%s); anvil at %s turned %.4f (%s); trough 0 %s" % (
        "present" if tomb else "gone", tuple(round(v, 3) for v in fw.location), fw.rotation_euler.z,
        "new" if fw_new else "old" if fw_old else "?", tuple(round(v, 3) for v in anv.location), anv.rotation_euler.z,
        "new" if an_new else "old" if an_old else "?", "new" if tr_new else "old" if tr_old else "?"))
    if tomb and fw_old and an_old and tr_old:
        return "old", want
    if not tomb and fw_new and an_new and tr_new:
        return "r34", want
    if not tomb and fw_new and an_new and not tr_new:
        return "stale", want
    fail.add("forge: a state this patch does not know (tomb %s, wheels %s, anvil %s, trough %s)" % (
        tomb, fw_new or ("old" if fw_old else "?"), an_new or ("old" if an_old else "?"),
        tr_new or ("old" if tr_old else "?")))
    return "unknown", want


def forge_apply(state, removed, added):
    root = obj("forge.root")
    coll = root.users_collection[0]
    if obj(TOMB) is not None:
        n = len(tree(obj(TOMB)))
        delete_tree(obj(TOMB), removed)
        log("forge: removed the Sword Tomb (%d objects)" % n)
    fw = obj("forge.five_wheels")
    fw.location = (F.FW_LOC[0], F.FW_LOC[1], 0.0)
    fw.rotation_euler = (0.0, 0.0, F.FW_ROT_Z)
    ax, ay, arz = F.smith_place("anvil")
    anv = obj("forge.anvil")
    anv.location = (ax, ay, 0.0)
    anv.rotation_euler = (0.0, 0.0, arz)
    for n in ("forge.trough.0", "forge.trough_water.0"):
        delete_tree(obj(n), removed)
    keep = set(o.name for o in bpy.data.objects)
    F._quench_trough(root, coll, 0, *F.smith_place("trough"))
    new = [o.name for o in bpy.data.objects if o.name not in keep]
    added += new
    log("forge: five wheels at %s turned %.4f, anvil at %s turned %.4f, trough 0 rebuilt %s at %s turned %.4f" % (
        tuple(round(v, 3) for v in fw.location), F.FW_ROT_Z, (round(ax, 3), round(ay, 3)), arz, new,
        tuple(round(v, 3) for v in F.smith_place("trough")[:2]), F.smith_place("trough")[2]))


# ---- arena

def bagua_scratch(sc_):
    """The bagua's cleared mesh as a fresh build makes it: (sig, faces removed, the shared mesh)."""
    me0 = bpy.data.meshes.get(BAGUA_KEY)
    made = False
    if me0 is None:
        flat = P._build_rune_ring(RE.SEAT_RING[0], RE.SEAT_RING[1], "trigram", 3)
        me0 = U.shared_mesh(BAGUA_KEY, lambda: P._rune_band(flat()))
        made = True
    if not len(me0.materials):
        U.set_materials(me0, ["rune_cyan"])
    tmp = bpy.data.objects.new(SCRATCH + ".bagua", me0)
    sc_.coll.objects.link(tmp)
    n = RE.clear_seat_trigrams(tmp, name=SCRATCH + ".bagua.seats")
    sig = faces_sig(tmp.data)
    me0 = bpy.data.meshes.get(BAGUA_KEY)          # (clear_seat_trigrams frees it once nothing uses it)
    if made and me0 is not None and me0.users == 0:
        bpy.data.meshes.remove(me0)
    return sig, n


def arena_scratch(sc_):
    root = obj("arena.root")
    emp = RE.build_seats(sc_.coll, root, prefix=SCRATCH + ".arena")
    return sigs(tree(emp), SCRATCH + ".")


def veg_under_platform():
    """Faces of the island's top under the platform (wholly within arena.PLATFORM_CLEAR_R) where plants may grow."""
    rock = obj("arena.island")
    me = rock.data
    at = me.attributes.get("nature_veg")
    m = rock.matrix_parent_inverse @ rock.matrix_basis
    rr = [math.hypot(p.x, p.y) for p in (m @ v.co for v in me.vertices)]
    vals = [0.0] * len(me.polygons)
    at.data.foreach_get("value", vals)
    return sum(1 for i, p in enumerate(me.polygons) if vals[i] > 0.5 and
               max(rr[k] for k in p.vertices) <= AR.PLATFORM_CLEAR_R)


def arena_state(sc_, fail):
    bag = obj("arena.bagua")
    seats = obj(RE.SEAT_ROOT)
    want = arena_scratch(sc_)
    want_bag, _n = bagua_scratch(sc_)
    bag_tag = bag.data.get(RE.TAG)
    have = sigs(tree(seats)) if seats is not None else {}
    veg = veg_under_platform()
    log("arena: bagua mesh %s (%s, %d faces), seats %s, %d island faces under the platform may grow plants" % (
        bag.data.name, bag_tag or "untouched", len(bag.data.polygons), sorted(have) if have else "none", veg))
    if seats is None and bag_tag is None and bag.data.name.startswith(BAGUA_KEY):
        return "old", want
    if seats is not None and bag_tag == "arena.bagua":
        if have == want and faces_sig(bag.data) == want_bag and not veg:
            return "r34", want
        return "stale", want
    fail.add("arena: a state this patch does not know (seats %s, bagua %s)" % (seats is not None, bag_tag))
    return "unknown", want


def arena_apply(state, removed, added):
    root = obj("arena.root")
    coll = root.users_collection[0]
    bag = obj("arena.bagua")
    if state == "stale":
        delete_tree(obj(RE.SEAT_ROOT), removed)
        flat = P._build_rune_ring(RE.SEAT_RING[0], RE.SEAT_RING[1], "trigram", 3)
        me0 = U.shared_mesh(BAGUA_KEY, lambda: P._rune_band(flat()))
        if not len(me0.materials):
            U.set_materials(me0, ["rune_cyan"])
        old = bag.data
        bag.data = me0
        if old.users == 0:
            bpy.data.meshes.remove(old)
    keep = set(o.name for o in bpy.data.objects)
    n = RE.clear_seat_trigrams(bag)
    if obj(RE.SEAT_ROOT) is None:
        RE.build_seats(coll, root, "arena")
    new = [o.name for o in bpy.data.objects if o.name not in keep]
    added += new
    nv = AR.clear_plants_under_platform(obj("arena.island"))
    log("arena: %d faces of the bagua's four cardinal trigrams taken out (mesh %s, %d faces left); built %s; plants "
        "cleared from %d island faces under the platform" % (n, bag.data.name, len(bag.data.polygons), new, nv))


# ---- mission

def stair_foot():
    st = obj("mission.wall.stairs")
    return MI.WALL_Y - MI.WALL_BASE_D / 2 - float(st["arch_run"])


def dipper_objs():
    out = []
    for py, _n, _x, _y in RE.DIPPER:
        o = obj("mission.dipper." + py)
        if o is not None:
            out += tree(o)
    if obj("mission.dipper.lines") is not None:
        out.append(obj("mission.dipper.lines"))
    return out


def mission_scratch(sc_):
    root = obj("mission.root")
    keep = set(o.name for o in bpy.data.objects)
    RE.build_dipper(sc_.coll, root, stair_foot(), prefix=SCRATCH + ".mission")
    made = [o for o in bpy.data.objects if o.name not in keep]
    return sigs(made, SCRATCH + ".")


def mission_state(sc_, fail):
    hf = [obj(n) for n in ("mission.holy_fire", "mission.holy_fire.001")]
    dp = dipper_objs()
    want = mission_scratch(sc_)
    log("mission: holy-fire altars %s; Dipper objects %d (this build %d)" % (
        [o.name for o in hf if o is not None], len(dp), len(want)))
    if all(o is not None for o in hf) and not dp:
        return "old", want
    if not any(hf) and dp:
        return ("r34" if sigs(dp) == want else "stale"), want
    fail.add("mission: a state this patch does not know (altars %s, Dipper objects %d)" % (
        [o is not None for o in hf], len(dp)))
    return "unknown", want


def mission_apply(state, removed, added):
    root = obj("mission.root")
    coll = root.users_collection[0]
    for n in ("mission.holy_fire", "mission.holy_fire.001"):
        if obj(n) is not None:
            delete_tree(obj(n), removed)
    if state == "stale":
        for py, _n, _x, _y in RE.DIPPER:
            if obj("mission.dipper." + py) is not None:
                delete_tree(obj("mission.dipper." + py), removed)
        if obj("mission.dipper.lines") is not None:
            delete_tree(obj("mission.dipper.lines"), removed)
    keep = set(o.name for o in bpy.data.objects)
    RE.build_dipper(coll, root, stair_foot(), "mission")
    new = [o.name for o in bpy.data.objects if o.name not in keep]
    added += new
    log("mission: removed the holy-fire altars and their lights; built the Big Dipper (%d objects)" % len(new))


# ---- formation

REBUILT = ("formation.floor_band", "formation.chant", "formation.chant_dots", "formation.moss")


def altar_objs():
    out = []
    for n in ("formation.holy_fire", "formation.holy_fire.001"):
        if obj(n) is not None:
            out += tree(obj(n))
    return out


def formation_scratch(sc_):
    """Scratch builds: the altars (sigs) and the four rebuilt meshes ({name: scratch object})."""
    root = obj("formation.root")
    keep = set(o.name for o in bpy.data.objects)
    for x, y in FO.ALTARS:
        hf = MI.holy_fire(sc_.coll, root, x, y, key=SCRATCH + ".formation", front=FO.ALTAR_FRONT)
        for o in tree(hf):
            RE.tag(o, "formation")
    made = [o for o in bpy.data.objects if o.name not in keep]
    want = sigs(made, SCRATCH + ".")
    band = AP.mk(SCRATCH + ".floor_band", FO._floor_band_bm(), sc_.coll, [AP.M_INK], parent=root, smooth=False)
    gbm, dots = FO.chant_bm(band.data)
    chant = AP.mk(SCRATCH + ".chant", gbm, sc_.coll, [AP.M_GOLD], parent=root, smooth=False)
    bm = bmesh.new()
    AP.dots(bm, dots, FO.CHANT_R)
    cdots = AP.mk(SCRATCH + ".chant_dots", bm, sc_.coll, [AP.M_BRONZE], parent=root, smooth=math.radians(40))
    bm = bmesh.new()
    AP.moss_patches(bm, FO._moss_spots(), 77)
    moss = AP.mk(SCRATCH + ".moss", bm, sc_.coll, ["moss"], parent=root, smooth=False)
    meshes = {"formation.floor_band": band, "formation.chant": chant, "formation.chant_dots": cdots,
              "formation.moss": moss}
    return want, meshes


def formation_state(sc_, fail):
    dp = [obj("formation.dipper." + s) for s in OLD_DIPPER] + [obj("formation.dipper.lines")]
    alt = altar_objs()
    want, meshes = formation_scratch(sc_)
    same = {n: faces_sig(obj(n).data) == faces_sig(meshes[n].data) for n in REBUILT}
    log("formation: Dipper objects %d of 8; altars %d objects (this build %d); chant / band / dots / moss as this "
        "build: %s" % (sum(o is not None for o in dp), len(alt), len(want), same))
    if all(o is not None for o in dp) and not alt:
        return "old", (want, meshes)
    if not any(o is not None for o in dp) and alt:
        return ("r34" if sigs(alt) == want and all(same.values()) else "stale"), (want, meshes)
    fail.add("formation: a state this patch does not know (Dipper %d of 8, altars %d)" % (
        sum(o is not None for o in dp), len(alt)))
    return "unknown", (want, meshes)


def formation_apply(state, meshes, removed, added):
    root = obj("formation.root")
    coll = root.users_collection[0]
    for s in OLD_DIPPER:
        if obj("formation.dipper." + s) is not None:
            delete_tree(obj("formation.dipper." + s), removed)
    if obj("formation.dipper.lines") is not None:
        delete_tree(obj("formation.dipper.lines"), removed)
    for n in ("formation.holy_fire", "formation.holy_fire.001"):
        if obj(n) is not None:
            delete_tree(obj(n), removed)
    keep = set(o.name for o in bpy.data.objects)
    FO._altars(coll, root)
    new = [o.name for o in bpy.data.objects if o.name not in keep]
    added += new
    for n in REBUILT:
        transplant(meshes[n], obj(n))
    gone = [m.name for m in bpy.data.meshes if m.name.startswith(("formation.star_platform", "formation.star_stone"))]
    log("formation: removed the Big Dipper (shared meshes left: %s); built the altars %s; rebuilt %s" % (
        gone or "none", new, list(REBUILT)))


# ------------------------------------------------------------------------------------------------------------ checks

def floor_bvh(dg, names):
    T = world_tris(dg, owners=set(names))
    out = {}
    for n, t in T.items():
        out[n] = (bvh(t), t)
    return out


def level_under(floors, p, top=5.0):
    """(owner, z) of the highest floor face under the point p (x, y), or (None, None)."""
    best = (None, None)
    for n, (tr, _t) in floors.items():
        loc, nrm, idx, d = tr.ray_cast(Vector((p[0], p[1], p[2] + top)), Vector((0.0, 0.0, -1.0)), top + 10.0)
        if loc is not None and (best[1] is None or loc.z > best[1]):
            best = (n, loc.z)
    return best


def foot_points(T, band=0.005):
    """World points on the foot ring of triangles T: their vertices within ``band`` of the lowest, at most 64."""
    V = T.reshape(-1, 3)
    zmin = V[:, 2].min()
    F_ = V[V[:, 2] < zmin + band]
    if len(F_) > 64:
        F_ = F_[np.linspace(0, len(F_) - 1, 64).astype(int)]
    return F_, zmin


def check_grounded(dg, label, names, floors, fail, want_level=None):
    T = obj_tris(dg, names)
    pts, zmin = foot_points(T)
    levels, worst = set(), 0.0
    for p in pts:
        n, z = level_under(floors, p)
        if n is None:
            fail.add("%s: no floor under its foot at %s" % (label, tuple(round(v, 2) for v in p)))
            return
        sink = z - p[2]
        levels.add((n, round(z, 3)))
        worst = max(worst, abs(sink))
        if not (FOOT_SINK[0] - 1e-4 <= sink <= FOOT_SINK[1]):
            fail.add("%s: foot at z %.3f, its floor %s at %.3f (sunk %.3f m, want %.2f..%.2f)" % (
                label, p[2], n, z, sink, FOOT_SINK[0], FOOT_SINK[1]))
            return
    if want_level is not None and len({z for _n, z in levels}) != 1:
        fail.add("%s: its foot stands on more than one level %s" % (label, sorted(levels)))
    log("grounded %s: %d foot points on %s, sunk at most %.3f m" % (label, len(pts), sorted(levels), worst))


def check_clear(dg, label, names, allow, fail, extra=None, below=None):
    """Nothing but ``allow`` (the floor it is set into) crosses the piece or comes within CLEAR_MIN; ``extra`` {name:
    gap} wants more room; ``below`` {name: z}: that neighbour may touch only under the floor's top z (geometry hidden
    under the floor, e.g. the island's plants under the arena's platform)."""
    own = set(names)
    T = obj_tris(dg, own)
    lo, hi = T.reshape(-1, 3).min(0) - 0.5, T.reshape(-1, 3).max(0) + 0.5
    tw = bvh(T)
    V = T.reshape(-1, 3)[::5]
    rows = []
    for o, To in world_tris(dg, near=(lo, hi), skip=own).items():
        if o.startswith(SCRATCH):
            continue
        to = bvh(To)
        touch = len(tw.overlap(to))
        d = min(min(to.find_nearest(Vector(p))[3] for p in V), min(tw.find_nearest(Vector(p))[3]
                                                                     for p in To.reshape(-1, 3)[::5]))
        rows.append((d, o, touch))
        ok = any(o == a or o.startswith(a + ".") or o == a for a in allow)
        if below and o in below and (touch or d < CLEAR_MIN):
            box_lo, box_hi = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
            inb = To[((To[:, :, 0].max(1) >= box_lo[0]) & (To[:, :, 0].min(1) <= box_hi[0]) &
                      (To[:, :, 1].max(1) >= box_lo[1]) & (To[:, :, 1].min(1) <= box_hi[1]))]
            ztop = float(inb[:, :, 2].max()) if len(inb) else -1e9
            log("clear %s: %s touches it only %.3f m under the floor's top (hidden)" % (label, o, below[o] - ztop)
                if ztop <= below[o] + 1e-3 else "clear %s: %s rises %.3f m over the floor inside it" % (
                    label, o, ztop - below[o]))
            ok = ztop <= below[o] + 1e-3
        if not ok and (touch or d < CLEAR_MIN):
            fail.add("%s: %s is %.3f m from it (%d crossing triangle pairs)" % (label, o, d, touch))
        if extra and o in extra and d < extra[o]:
            fail.add("%s: %s is %.3f m from it, want %.2f m" % (label, o, d, extra[o]))
    rows.sort()
    log("clear %s: nearest %s" % (label, ", ".join("%s %.3f m%s" % (o, d, " (allowed)" if any(
        o == a or o.startswith(a + ".") for a in allow) else "") for d, o, _t in rows[:5]) or "nothing"))


def screen_pts(sc, cam, P_):
    xs, ys, zs = [], [], []
    for p in P_:
        v = world_to_camera_view(sc, cam, Vector(p))
        xs.append(v.x * RES[0])
        ys.append((1 - v.y) * RES[1])
        zs.append(v.z)
    return np.array(xs), np.array(ys), np.array(zs)


def seen_share(sc, dg, cam, P_, names, lift=0.02, n=60):
    cw = cam.matrix_world.translation.copy()
    k, seen = 0, 0
    for p in P_[::max(1, len(P_) // n)]:
        q = Vector(p) + Vector((0.0, 0.0, lift))
        d = q - cw
        o = cw.copy()
        for _ in range(6):                       # past the page-drawn barrier and the haze (the bake leaves them out)
            hit, loc, nrm, idx, hob, _ = sc.ray_cast(dg, o, d.normalized(), distance=(q - o).length + 0.05)
            if not hit or not getattr(hob, "original", hob).name.startswith(SEE_THROUGH):
                break
            o = loc + d.normalized() * 0.01
        k += 1
        if not hit:
            seen += 1
            continue
        hn = getattr(hob, "original", hob).name
        top = hob
        while top is not None and top.name not in names:
            top = top.parent
        seen += bool(hn in names or top is not None or (loc - q).length < 0.05)
    return seen / max(k, 1)


def check_reading(sc, dg, cam, stop, label, P_, names, fail, need=True):
    """An item's points (world) on screen at the stop's hold as the site frames it: in frame, unhidden, clear of the
    stop's panel and the voice button."""
    xs, ys, zs = screen_pts(sc, cam, P_)
    inside = float(np.mean((xs >= 0) & (xs <= RES[0]) & (ys >= 0) & (ys <= RES[1]) & (zs > 0)))
    box = (xs.min(), xs.max(), ys.min(), ys.max())
    hit_ui = []
    for nm, (x0, y0, x1, y1) in RE.UI_RECTS.get(stop, ()) + RE.UI_COMMON:
        if not (box[1] < x0 or box[0] > x1 or box[3] < y0 or box[2] > y1):
            hit_ui.append(nm)
    seen = seen_share(sc, dg, cam, P_, names)
    log("read %s %s: x %.0f..%.0f y %.0f..%.0f px, %.0f%% in frame, %.0f%% unhidden%s" % (
        stop, label, box[0], box[1], box[2], box[3], 100 * inside, 100 * seen,
        ("; under " + ", ".join(hit_ui)) if hit_ui else ""))
    if need and (inside < 1.0 or seen < READ_SEEN or hit_ui):
        fail.add("%s %s does not read at the hold (%.0f%% in frame, %.0f%% unhidden, under %s)" % (
            stop, label, 100 * inside, 100 * seen, hit_ui or "nothing"))
    return box


def gold_faces(ob, mat="gold", up=True):
    """World triangles of an object's gold faces (upward ones when ``up``)."""
    me = ob.data
    me.calc_loop_triangles()
    mats = [m.name if m else "" for m in me.materials]
    W = np.array(ob.matrix_world)
    L = local_tris(me)
    mi = np.empty(len(me.loop_triangles), np.int64)
    me.loop_triangles.foreach_get("material_index", mi)
    sel = np.array([mats[i].endswith(mat) if i < len(mats) else False for i in mi])
    T = L[sel] @ W[:3, :3].T + W[:3, 3]
    if up and len(T):
        n, _a = tri_normals(T)
        T = T[n[:, 2] > 0.99]
    return T


def tri_points(T, k=1):
    """Centroids (and k-1 more random points) of triangles T."""
    rng = np.random.default_rng(34)
    out = [T.mean(1)]
    for _ in range(k - 1):
        u, v = rng.random(len(T)), rng.random(len(T))
        f = u + v > 1
        u[f], v[f] = 1 - u[f], 1 - v[f]
        out.append(T[:, 0] + u[:, None] * (T[:, 1] - T[:, 0]) + v[:, None] * (T[:, 2] - T[:, 0]))
    return np.concatenate(out)


def check_carved(label, gold_T, host_T, host_rims, fail):
    """No upward host face under the gold's face within CARVE_DEPTH; every hole rim point inside the gold."""
    hb = bvh(host_T) if len(host_T) else None
    hn, _a = tri_normals(host_T) if len(host_T) else (None, None)
    under, n_s = 0, 0
    for p in tri_points(gold_T, 2):
        n_s += 1
        if hb is None:
            continue
        loc, nrm, fi, d = hb.ray_cast(Vector(p) - Vector((0, 0, 1e-4)), Vector((0, 0, -1)), CARVE_DEPTH)
        if loc is not None and hn[fi][2] > 0.9:
            under += 1
    gb = bvh(gold_all_T[label]) if label in gold_all_T else None
    shown, n_r = 0, 0
    for a, b, h in host_rims:
        for t in (np.arange(RIM_PTS) + 0.5) / RIM_PTS:
            p = Vector(a).lerp(Vector(b), float(t)) + h * RIM_IN
            n_r += 1
            up_ = gb.ray_cast(p + Vector((0, 0, 1e-5)), Vector((0, 0, 1)), 0.2) if gb else (None,)
            dn = gb.ray_cast(p - Vector((0, 0, 1e-5)), Vector((0, 0, -1)), 0.2) if gb else (None,)
            if up_[0] is None or dn[0] is None:
                shown += 1
    log("carved %s: %d of %d points of the gold's face have a host face under them; %d of %d hole-rim points not "
        "inside the gold" % (label, under, n_s, shown, n_r))
    if not n_s or under > 0.01 * n_s:
        fail.add("%s: %d of %d points of the gold have a host face under them (not cut)" % (label, under, n_s))
    if n_r and shown > 0.01 * n_r:
        fail.add("%s: %d of %d points on the holes' rims are not inside the gold" % (label, shown, n_r))


gold_all_T = {}


def host_rims(ob, z, tol=2e-4, keep=None):
    """World (a, b, h) of every open edge of ``ob``'s mesh lying in the plane z (world) - its hole rims - with h the
    unit vector across the edge into the hole (away from its one face); ``keep(local midpoint)`` filters (a sheet's
    own outline is open too)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    W = ob.matrix_world
    out = []
    for e in bm.edges:
        if len(e.link_faces) == 1:
            a, b = W @ e.verts[0].co, W @ e.verts[1].co
            if abs(a.z - z) < tol and abs(b.z - z) < tol and (keep is None or keep(0.5 * (e.verts[0].co +
                                                                                          e.verts[1].co))):
                c = W @ e.link_faces[0].calc_center_median()
                d = (b - a).normalized()
                h = Vector((-d.y, d.x, 0.0))
                if h.dot(c - 0.5 * (a + b)) > 0:
                    h = -h
                out.append((a, b, h))
    bm.free()
    return out


def all_T(ob):
    W = np.array(ob.matrix_world)
    return local_tris(ob.data) @ W[:3, :3].T + W[:3, 3]


def char_cells(T, n, axis):
    """Split triangles T into n characters along ``axis`` (a unit 2D vector): the n-1 widest gaps between runs."""
    u = T[:, :, :2] @ np.array(axis)
    lo, hi = u.min(1), u.max(1)
    order = np.argsort(lo)
    runs = []
    for i in order:
        if runs and lo[i] <= runs[-1][1] + 1e-6:
            runs[-1][1] = max(runs[-1][1], hi[i])
        else:
            runs.append([lo[i], hi[i]])
    if len(runs) < n:
        return [np.ones(len(T), bool)]
    gaps = sorted(range(len(runs) - 1), key=lambda k: -(runs[k + 1][0] - runs[k][1]))[:n - 1]
    cuts = sorted(0.5 * (runs[k][1] + runs[k + 1][0]) for k in gaps)
    c = T.mean(1)[:, :2] @ np.array(axis)
    bounds = [-np.inf] + cuts + [np.inf]
    return [(c > bounds[k]) & (c < bounds[k + 1]) for k in range(n)]


def chars_px(sc, cam, T, n, axis):
    """[(width px, height px)] of n characters (triangles T split along ``axis``) at the camera."""
    out = []
    for m in char_cells(T, n, axis):
        xs, ys, _z = screen_pts(sc, cam, T[m].reshape(-1, 3))
        out.append((xs.max() - xs.min(), ys.max() - ys.min()))
    return out


def check_bagua(fail):
    """The bagua's removed faces are whole trigram bars: compare the shared mesh's connected pieces with the cleared
    mesh's."""
    me0 = bpy.data.meshes.get(BAGUA_KEY)
    made = me0 is None
    if made:
        flat = P._build_rune_ring(RE.SEAT_RING[0], RE.SEAT_RING[1], "trigram", 3)
        me0 = U.shared_mesh(BAGUA_KEY, lambda: P._rune_band(flat()))
    bm = bmesh.new()
    bm.from_mesh(me0)
    bm.verts.ensure_lookup_table()
    pieces = []
    seen = set()
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, comp = [v], []
        seen.add(v.index)
        while stack:
            w = stack.pop()
            comp.append(w)
            for e in w.link_edges:
                o = e.other_vert(w)
                if o.index not in seen:
                    seen.add(o.index)
                    stack.append(o)
        pieces.append(comp)
    r0, r1, half = RE.SEAT_CLEAR
    whole, partial = 0, 0
    for comp in pieces:
        inside = []
        for f in {f for w in comp for f in w.link_faces}:
            c = f.calc_center_median()
            r = math.hypot(c.x, c.y)
            a = math.degrees(math.atan2(c.y, c.x))
            inside.append(r0 <= r <= r1 and any(abs((a - d + 180.0) % 360.0 - 180.0) <= half
                                                  for _k, _t, d in RE.SEATS))
        if all(inside):
            whole += 1
        elif any(inside):
            partial += 1
    bm.free()
    if made and me0.users == 0:
        bpy.data.meshes.remove(me0)
    log("bagua: %d connected pieces; %d wholly at the seats (taken out), %d partly (must be 0)" % (
        len(pieces), whole, partial))
    if partial:
        fail.add("bagua: %d pieces only partly under the seats" % partial)
    if whole < 4:
        fail.add("bagua: only %d pieces at the seats (four trigrams' bars expected)" % whole)
    return whole


def check_camera(sc, cam, label, names, fail):
    T = world_tris(bpy.context.evaluated_depsgraph_get(), owners=set(names))
    if not T:
        return
    V = np.concatenate([t.reshape(-1, 3) for t in T.values()])
    lo, hi = V.min(0), V.max(0)
    frames = list(range(sc.frame_start, sc.frame_end + 1))
    best, bf = 1e9, 0
    for f, M in zip(frames, EW.sample_matrices(cam, frames)):
        p = np.array(M.translation)
        d = float(np.linalg.norm(np.maximum(0.0, np.maximum(lo - p, p - hi))))
        if d < best:
            best, bf = d, f
    log("flight %s: chase.cam comes within %.1f m (frame %d)" % (label, best, bf))
    if best < CAM_MIN:
        fail.add("%s: chase.cam comes within %.1f m (frame %d)" % (label, best, bf))


def scan(dg, names, label):
    """{piece: [same <=5 mm, same 5-12 mm, back-to-back <=5 mm]} m2 of parallel faces against itself and every mesh
    whose box meets its own (patch_r32_plaque's scan, without the 12-20 mm band)."""
    t0 = time.time()
    rows = {}
    for nm in names:
        ob = bpy.data.objects[nm]
        rng = np.random.default_rng(zlib.crc32(nm.encode()))
        T = all_T(ob)
        if not len(T):
            continue
        lo, hi = T.reshape(-1, 3).min(0) - 0.03, T.reshape(-1, 3).max(0) + 0.03
        others, oid = [], []
        for own, To in world_tris(dg, near=(lo, hi), skip={nm}).items():
            if own.startswith(SCRATCH):
                continue
            others.append(To)
            oid += [own] * len(To)
        tn = bvh(np.concatenate(others)) if others else None
        ts = bvh(T)
        nrm, ar = tri_normals(T)
        tot = [0.0, 0.0, 0.0]
        who = {}
        for t in np.nonzero(ar > 1e-9)[0]:
            k = int(min(60, max(1, round(ar[t] / (SCAN_STEP * SCAN_STEP)))))
            u, v = rng.random(k), rng.random(k)
            f = u + v > 1.0
            u[f], v[f] = 1.0 - u[f], 1.0 - v[f]
            n = Vector(nrm[t])
            w = ar[t] / k
            for p in T[t, 0] + np.outer(u, T[t, 1] - T[t, 0]) + np.outer(v, T[t, 2] - T[t, 0]):
                p = Vector(p)
                for sgn in (-1.0, 1.0):
                    for tr, ids in ((ts, None), (tn, oid)):
                        if tr is None:
                            continue
                        loc, hn, fi, _d = tr.ray_cast(p + n * (sgn * 1e-4), n * sgn, SCAN_TOL12)
                        if loc is None:
                            continue
                        c = hn.dot(n)
                        g = abs((loc - p).dot(n))
                        if abs(c) < SCAN_PAR or g > SCAN_TOL12:
                            continue
                        o = "<self>" if ids is None else ids[fi]
                        if c < 0.0:
                            if g <= SCAN_TOL:
                                tot[2] += w
                                who.setdefault(o, [0.0, 0.0, 0.0])[2] += w
                            continue
                        b = 0 if g <= SCAN_TOL else 1
                        tot[b] += w
                        who.setdefault(o, [0.0, 0.0, 0.0])[b] += w
        rows[nm] = (tot, who)
        top = sorted(who.items(), key=lambda kv: -sum(kv[1]))[:3]
        log("scan %s %s: same-facing within 5 mm %.3f m2, 5-12 mm %.3f m2; back-to-back within 5 mm %.3f m2%s" % (
            label, nm, tot[0], tot[1], tot[2], "".join("; %s %.3f + %.3f / %.3f" % (o, a, b, c_)
                                                       for o, (a, b, c_) in top if a + b + c_ >= 0.001)))
    log("scan %s: %d pieces, %.1f s" % (label, len(rows), time.time() - t0))
    return rows


def hotspot_boxes():
    """{hotspot id: world box} of the touched areas' click targets."""
    defs = [(h, n) for h, _l, n in EW.AREA_HOTSPOTS if h.split("-")[0] in ("forge", "arena", "mission", "formation")]
    defs += [("role:%d" % i, ["mission.role_tablet" + ("" if i == 0 else ".%03d" % i)]) for i in range(7)]
    defs += [("arch:%d" % k, ["formation.pillar.%d" % k]) for k in range(8)]
    defs += [("hackathon:%d" % i, ["arena.banner" + ("" if i == 0 else ".%03d" % i)]) for i in range(0, 40, 13)]
    out = {}
    for h, names in defs:
        b = EW._subtree_box(names)
        out[h] = None if b is None else (tuple(round(v, 4) for v in b[0]), tuple(round(v, 4) for v in b[1]))
    return out


# ------------------------------------------------------------------------------------------------------------- main

def touched():
    """The objects the round touches, for the DIGEST, and the names that must be absent."""
    names = ["forge.five_wheels", "forge.anvil", "forge.trough.0", "forge.trough_water.0", "arena.bagua"]
    obs = []
    for n in names:
        if obj(n) is not None:
            obs += tree(obj(n))
    for n in (RE.SEAT_ROOT, "formation.holy_fire", "formation.holy_fire.001"):
        if obj(n) is not None:
            obs += tree(obj(n))
    obs += dipper_objs()
    obs += [obj(n) for n in REBUILT if obj(n) is not None]
    absent = [TOMB, "mission.holy_fire", "mission.holy_fire.001", "formation.dipper.lines"] + \
        ["formation.dipper." + s for s in OLD_DIPPER]
    return obs, absent


def digest():
    obs, absent = touched()
    h = hashlib.md5()
    for nm, s in sorted(sigs(obs).items()):
        h.update(nm.encode())
        h.update(s.encode())
    for n in absent:
        h.update(("%s:%s" % (n, obj(n) is not None)).encode())
    at = obj("arena.island").data.attributes.get("nature_veg")
    vals = np.zeros(len(at.data))
    at.data.foreach_get("value", vals)
    h.update(np.round(vals, 4).tobytes())
    return h.hexdigest()


def run_checks(sc, fail, do_scan, scan0):
    dg = bpy.context.evaluated_depsgraph_get()
    src = bpy.data.objects[EW.CAMERA]
    cam = bpy.data.objects.new(SCRATCH + ".cam", src.data)
    sc.collection.objects.link(cam)
    keep_frame = sc.frame_current
    try:
        # ---- forge
        corner = {"rack": tree(obj("forge.five_wheels")), "anvil": [obj("forge.anvil")],
                  "trough": [obj("forge.trough.0"), obj("forge.trough_water.0")]}
        floors = floor_bvh(dg, ["forge.paving"])
        for k, obs in corner.items():
            names = [o.name for o in obs]
            check_grounded(dg, "forge " + k, names, floors, fail)
            check_clear(dg, "forge " + k, names, ALLOW["forge"], fail, extra={"forge.rune_ring": RUNE_GAP})
        allc = [o.name for obs in corner.values() for o in obs]
        cam.matrix_world = RE.site_view(sc, src, RE.HOLD_FRAMES["forge"])
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        P_ = obj_tris(dg, allc).reshape(-1, 3)[::3]
        check_reading(sc, dg, cam, "forge", "smith's corner", P_, set(allc), fail)
        for w in ("gold", "silver", "copper", "iron", "lead"):
            o = obj("forge.five_wheels." + w)
            check_reading(sc, dg, cam, "forge", "wheel " + w, all_T(o).reshape(-1, 3)[::7], {o.name}, fail,
                          need=False)
        check_camera(sc, src, "forge corner", allc, fail)
        # ---- arena
        dg = bpy.context.evaluated_depsgraph_get()
        floors = floor_bvh(dg, ["arena.platform"])
        seats = [obj("arena.seat." + k) for k in SEAT_KEYS]
        cam.matrix_world = RE.site_view(sc, src, RE.HOLD_FRAMES["arena"])
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        for o in seats:
            check_grounded(dg, o.name, [o.name], floors, fail)
            check_clear(dg, o.name, [o.name], ALLOW["arena"], fail,
                        below={"arena.island.plants": obj("arena.root").matrix_world.translation.z})
            zmax = all_T(o)[:, :, 2].max() - obj("arena.root").matrix_world.translation.z
            if zmax > 0.07:
                fail.add("%s stands %.3f m over the floor" % (o.name, zmax))
            g = gold_faces(o)
            gold_all_T[o.name] = gold_faces(o, up=False)
            host = all_T(o)
            hn, _a = tri_normals(host)
            plate = host[(hn[:, 2] > 0.99)]
            plate_top = plate[np.abs(plate[:, :, 2].mean(1) - (obj("arena.root").matrix_world.translation.z +
                                                                RE.SEAT_TOP)) < 1e-3]
            check_carved(o.name, g, plate_top, host_rims(o, obj("arena.root").matrix_world.translation.z +
                                                          RE.SEAT_TOP), fail)
            check_reading(sc, dg, cam, "arena", o.name, all_T(o).reshape(-1, 3)[::3], {o.name}, fail)
            # the characters: gold faces inside the fillet (in the seat's frame)
            Li = np.array(o.matrix_world.inverted())
            gl = g.reshape(-1, 3) @ Li[:3, :3].T + Li[:3, 3]
            gl = gl.reshape(-1, 3, 3)
            ix = 0.5 * RE.SEAT_SIZE[0] - RE.SEAT_FRAME[0] - RE.SEAT_FRAME[1] - 1e-3
            iy = 0.5 * RE.SEAT_SIZE[1] - RE.SEAT_FRAME[0] - RE.SEAT_FRAME[1] - 1e-3
            inner = (np.abs(gl[:, :, 0]).max(1) < ix) & (np.abs(gl[:, :, 1]).max(1) < iy)
            px = chars_px(sc, cam, g[inner], 2, (math.cos(obj("arena.root").matrix_world.to_euler().z),
                                                 math.sin(obj("arena.root").matrix_world.to_euler().z)))
            log("read arena %s %s: characters %s px (w x h)" % (o.name, o["seat_title"],
                                                               ", ".join("%.0f x %.0f" % c for c in px)))
        check_bagua(fail)
        check_camera(sc, src, "arena seats", [o.name for o in seats], fail)
        # ---- mission
        dg = bpy.context.evaluated_depsgraph_get()
        floors = floor_bvh(dg, ["mission.plaza", "mission.apron_front", "mission.axis", "mission.axis.001"])
        cam.matrix_world = RE.site_view(sc, src, RE.HOLD_FRAMES["mission"])
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        root = obj("mission.root")
        for py, name, x, y in RE.DIPPER:
            e = obj("mission.dipper." + py)
            d = obj(e.name + ".drum")
            check_grounded(dg, e.name, [d.name], floors, fail, want_level=True)
            check_clear(dg, e.name, [d.name], ALLOW["mission"], fail)
            g = gold_faces(d)
            gold_all_T[d.name] = gold_faces(d, up=False)
            host = all_T(d)
            hn, _a = tri_normals(host)
            ztop = (root.matrix_world @ Vector((x, y, e.location.z + RE.DRUM_PROFILE[-1][1]))).z
            top = host[(hn[:, 2] > 0.99) & (np.abs(host[:, :, 2].mean(1) - ztop) < 1e-3)]
            check_carved(d.name, g, top, host_rims(d, ztop), fail)
            check_reading(sc, dg, cam, "mission", "%s %s" % (e.name, name), host.reshape(-1, 3)[::3], {d.name}, fail)
            ax = e.matrix_world.to_3x3() @ Vector((1.0, 0.0, 0.0))
            px = chars_px(sc, cam, g[np.abs(g[:, :, 2].mean(1) - g[:, :, 2].max()) < 1e-3], 2, (ax.x, ax.y))
            log("read mission %s %s: characters %s px (w x h)" % (e.name, name, ", ".join("%.0f x %.0f" % c
                                                                                         for c in px)))
        ln = obj("mission.dipper.lines")
        check_clear(dg, ln.name, [ln.name], ALLOW["mission"], fail)
        # each line piece on its level: its top face LINE_TOP over the floor under it
        T = all_T(ln)
        tn, _a = tri_normals(T)
        bad, lv = 0, {}
        for c in T[tn[:, 2] > 0.99].mean(1):
            n, z = level_under(floors, c)
            if n is None or abs(c[2] - (z + RE.LINE_TOP)) > 1e-3:
                bad += 1
            else:
                lv[n] = lv.get(n, 0) + 1
        log("mission lines: %d triangles; top faces over %s; %d not LINE_TOP over their floor" % (len(T), lv, bad))
        if bad:
            fail.add("mission lines: %d top faces not %.2f m over the floor under them" % (bad, RE.LINE_TOP))
        check_reading(sc, dg, cam, "mission", "Dipper lines", T.reshape(-1, 3)[::5], {ln.name}, fail)
        dn = [obj("mission.dipper." + py) for py, _n, _x, _y in RE.DIPPER]
        check_camera(sc, src, "mission Dipper", [o.name for e in dn for o in tree(e)] + [ln.name], fail)
        # ---- formation
        dg = bpy.context.evaluated_depsgraph_get()
        floors = floor_bvh(dg, ["formation.floor"])
        cam.matrix_world = RE.site_view(sc, src, RE.HOLD_FRAMES["formation"])
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        cw = cam.matrix_world.translation
        for n in ("formation.holy_fire", "formation.holy_fire.001"):
            hf = obj(n)
            parts = [o.name for o in tree(hf) if o.type == 'MESH']
            check_grounded(dg, n, [hf.name + ".plinth"], floors, fail)
            check_clear(dg, n, parts, ALLOW["formation"], fail)
            check_reading(sc, dg, cam, "formation", n, obj_tris(dg, parts).reshape(-1, 3)[::9], set(parts), fail)
            side = 1.0 if hf.location.x >= 0 else -1.0
            a = -0.5 * math.pi + FO.ALTAR_FRONT
            fx, fy = math.cos(a), math.sin(a)
            if side < 0:
                fx = -fx
            Rw = hf.matrix_world.to_3x3()
            fw = Rw @ Vector((fx, fy, 0.0))
            to = (cw - hf.matrix_world.translation)
            to.z = 0.0
            ang = math.degrees(fw.to_2d().angle(to.to_2d().normalized()))
            log("formation %s: flame's broad side %.1f deg off the hold camera" % (n, ang))
            if ang > 10.0:
                fail.add("%s: the flame's broad side is %.1f deg off the hold camera" % (n, ang))
        check_camera(sc, src, "formation altars", [o.name for n in ("formation.holy_fire", "formation.holy_fire.001")
                                                   for o in tree(obj(n))], fail)
        ch = obj("formation.chant")
        band = obj("formation.floor_band")
        froot = obj("formation.root")
        z0 = froot.matrix_world.translation.z
        g = gold_faces(ch)
        gold_all_T["formation.chant"] = all_T(ch)
        bt = all_T(band)
        bn, _a = tri_normals(bt)
        bc = bt.mean(1) - np.array(froot.matrix_world.translation)
        ring = bt[(bn[:, 2] > 0.99) & (np.abs(bt[:, :, 2].mean(1) - z0) < 1e-3)]
        check_carved("formation.chant", g, ring, host_rims(band, z0, keep=lambda c: FO.R_CHANT[0] + 0.005 < math.hypot(
            c.x, c.y) < FO.R_CHANT[1] - 0.005 and abs(c.x) > FO.STRIP_HW + 0.005), fail)
        bad = [c for c in FO.CHANT if c in "残躯圣欢为恶乐归尘怜忧实"]
        n_ch = len([c for c in FO.CHANT if c not in "，。？！、；：,.?!"])
        log("formation chant: %d characters, traditional (simplified left: %s)" % (n_ch, bad or "none"))
        if bad:
            fail.add("chant: simplified characters left %s" % bad)
        # the chant on screen, and the size of a character at the ring's front (the hold sees those best)
        gtop = g[np.abs(g[:, :, 2].mean(1) - g[:, :, 2].max()) < 1e-3]
        xs, ys, zs = screen_pts(sc, cam, gtop.reshape(-1, 3))
        log("read formation chant: gold faces x %.0f..%.0f y %.0f..%.0f px" % (xs.min(), xs.max(), ys.min(), ys.max()))
        for deg in (-100.0, -135.0, 180.0):
            t = math.radians(deg)
            c, s = math.cos(t), math.sin(t)
            h = 0.5 * FO.CHANT_H
            sq = [froot.matrix_world @ Vector(((FO.CHANT_R + dr) * c - dt * s, (FO.CHANT_R + dr) * s + dt * c, 0.03))
                  for dr in (-h, h) for dt in (-h, h)]
            xs, ys, _z = screen_pts(sc, cam, sq)
            log("read formation chant: a character at %.0f deg spans %.0f x %.0f px" % (deg, np.ptp(xs), np.ptp(ys)))
        moss = obj("formation.moss")
        for n in ("formation.holy_fire", "formation.holy_fire.001"):
            c = obj(n).matrix_world.translation
            mt = all_T(moss)
            d = np.linalg.norm(mt.mean(1)[:, :2] - np.array(c[:2]), axis=1).min()
            log("formation moss: nearest moss to %s's centre %.2f m (plinth corners at 3.25)" % (n, d))
            if d < 3.3:
                fail.add("moss under %s (%.2f m from its centre)" % (n, d))
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        sc.frame_set(keep_frame)
    if do_scan:
        dg = bpy.context.evaluated_depsgraph_get()
        names = ["forge.trough.0", "forge.trough_water.0", "forge.five_wheels.stand"] + \
            ["arena.seat." + k for k in SEAT_KEYS] + ["arena.bagua"] + \
            ["mission.dipper.%s.drum" % py for py, _n, _x, _y in RE.DIPPER] + ["mission.dipper.lines"] + \
            ["formation.holy_fire.plinth", "formation.holy_fire.001.plinth", "formation.chant", "formation.chant_dots"]
        rows = scan(dg, names, "after")
        for nm, (tot, _who) in rows.items():
            was = scan0.get(nm, ([0.0, 0.0, 0.0], {}))[0] if scan0 else [0.0, 0.0, 0.0]
            if tot[0] + tot[1] > was[0] + was[1] + NEW_MAX:
                fail.add("same-facing overlap on %s: %.3f + %.3f m2 (was %.3f + %.3f)" % (nm, tot[0], tot[1],
                                                                                        was[0], was[1]))


def main():
    dry, do_scan = options()
    t0 = time.time()
    fail = Fail()
    sc = bpy.context.scene
    for n in ("forge.root", "arena.root", "mission.root", "formation.root", EW.CAMERA):
        if obj(n) is None:
            log("NOT SAVED: %s not found: is this out/sect_chase.blend?" % n)
            raise SystemExit(1)
    if obj("forge.fire.ding") is None or not any(o.name.startswith("props.lion.scan") for o in bpy.data.objects):
        log("NOT SAVED: run patch_r28_lions.py and patch_r29_forge.py first (forge.fire.ding / props.lion.scan.*)")
        raise SystemExit(1)
    FO._materials()                 # the formation's registered materials (its ink band, bronze, moss)
    rx, ry, rp = sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES[0], RES[1], 100
    n_obj0 = len(bpy.data.objects)
    scenes0 = sorted(s.name for s in bpy.data.scenes)
    had_eval = bpy.data.scenes.get(P._EVAL_SCENE) is not None
    log("refs_east: seats %s (plate %s m, characters %.2f m), Dipper %d drums / %d lines, formation altars %s (front "
        "%.1f deg), chant %d characters; forge corner at %s turned %.2f deg" % (
            [t for _k, t, _d in RE.SEATS], RE.SEAT_SIZE, RE.SEAT_GLYPH, len(RE.DIPPER), len(RE.DIPPER_LINKS),
            FO.ALTARS, math.degrees(FO.ALTAR_FRONT), len(FO.CHANT), F.SMITH_AT, math.degrees(F.SMITH_YAW)))
    hs0 = hotspot_boxes()
    sc_ = Scratch()
    try:
        t1 = time.time()
        st_f, _w = forge_state(sc_, fail)
        st_a, _w = arena_state(sc_, fail)
        st_m, _w = mission_state(sc_, fail)
        st_o, (want_o, meshes_o) = formation_state(sc_, fail)
        log("states: forge %s, arena %s, mission %s, formation %s (%.1f s)" % (st_f, st_a, st_m, st_o,
                                                                               time.time() - t1))
        if fail:
            log("NOT SAVED: the file is not in a state this patch knows (%d problems)" % len(fail))
            raise SystemExit(1)
        todo = any(s != "r34" for s in (st_f, st_a, st_m, st_o))
        scan0 = None
        if todo and do_scan:
            dg = bpy.context.evaluated_depsgraph_get()
            scan0 = scan(dg, [n for n in ("forge.trough.0", "forge.trough_water.0", "forge.five_wheels.stand",
                                          "arena.bagua", "formation.chant", "formation.chant_dots")
                              if obj(n) is not None], "before")
        removed, added = [], []
        if st_f != "r34":
            forge_apply(st_f, removed, added)
        if st_a != "r34":
            arena_apply(st_a, removed, added)
        if st_m != "r34":
            mission_apply(st_m, removed, added)
        if st_o != "r34":
            formation_apply(st_o, meshes_o, removed, added)
    finally:
        sc_.drop()
    if not had_eval:
        s_ = bpy.data.scenes.get(P._EVAL_SCENE)
        if s_ is not None and s_ != sc and not len(s_.objects):
            bpy.data.scenes.remove(s_)
    for m in list(bpy.data.meshes):
        if m.users == 0 and m.name.startswith(SCRATCH):
            bpy.data.meshes.remove(m)
    bpy.context.view_layer.update()
    # after: the build matches the scratch build (the same code)
    sc2 = Scratch()
    try:
        st = (forge_state(sc2, fail)[0], arena_state(sc2, fail)[0], mission_state(sc2, fail)[0],
              formation_state(sc2, fail)[0])
    finally:
        sc2.drop()
    if not had_eval:
        s_ = bpy.data.scenes.get(P._EVAL_SCENE)
        if s_ is not None and s_ != sc and not len(s_.objects):
            bpy.data.scenes.remove(s_)
    for m in list(bpy.data.meshes):
        if m.users == 0 and m.name.startswith(SCRATCH):
            bpy.data.meshes.remove(m)
    log("after: states %s" % (st,))
    if any(s != "r34" for s in st):
        fail.add("after the patch the file is not this build: %s" % (st,))
    run_checks(sc, fail, do_scan and todo, scan0)
    hs1 = hotspot_boxes()
    changed = [h for h in hs0 if hs0[h] != hs1.get(h)]
    log("hotspots: %d boxes of the touched areas, %d changed%s" % (len(hs0), len(changed),
                                                                    (" " + str(changed)) if changed else ""))
    if changed:
        fail.add("hotspot boxes changed: %s" % changed)
    n_obj1 = len(bpy.data.objects)
    log("objects %d -> %d (removed %d, added %d)" % (n_obj0, n_obj1, len(removed), len(added)))
    if n_obj1 != n_obj0 - len(removed) + len(added):
        fail.add("objects %d -> %d, want %d - %d + %d" % (n_obj0, n_obj1, n_obj0, len(removed), len(added)))
    left = [o.name for o in bpy.data.objects if o.name.startswith(SCRATCH)] + \
        [m.name for m in bpy.data.meshes if m.name.startswith(SCRATCH)] + \
        [c.name for c in bpy.data.collections if c.name.startswith(SCRATCH)] + \
        [d.name for d in bpy.data.lights if d.users == 0 and "holy_fire" in d.name]
    if left:
        fail.add("scratch data or orphan lights left: %s" % left[:8])
    scenes1 = sorted(s.name for s in bpy.data.scenes)
    if scenes1 != scenes0:
        fail.add("scenes %s -> %s" % (scenes0, scenes1))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, rp
    log("removed: %s" % (", ".join(sorted(removed)) or "nothing"))
    log("added: %s" % (", ".join(sorted(added)) or "nothing"))
    log("DIGEST", digest())
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail:
            log("  -", f)
        raise SystemExit(1)
    if not todo:
        log("CACHES ok: nothing changed")
        log("nothing changed: not saving (%.1f s)" % (time.time() - t0))
        return
    log("CACHES needs audit: objects added (arena.seats, mission.dipper.*, formation.holy_fire*), removed "
        "(forge.sword_tomb, mission.holy_fire*, formation.dipper.*) and moved (forge.five_wheels, forge.anvil, "
        "forge.trough.0) and meshes rebuilt (arena.bagua, formation.floor_band / chant / chant_dots / moss) - run "
        "export_web.py -- audit --profile full, then -- chunks,meta --profile full (the lore boxes: five-wheels moves, "
        "sword-tomb leaves the forge, mount-hua is new, big-dipper-array moves to the mission, holy-fire-altar to the "
        "formation), then bake_web.py -- bakefull --profile full --chunks forge,arena,mission,formation,backdrop, and "
        "bake_trees.py -- build for the arena chunk (the island's plants under the platform are gone: arena.island's "
        "'nature_veg' mask), then pack")
    if dry:
        log("DRY_RUN: checks passed, not saving (%.1f s)" % (time.time() - t0))
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "(%.1f s)" % (time.time() - t0))


if __name__ == "__main__":
    main()
