"""Round 61: lit lanterns in the summit's hold frame, put into an existing out/sect_chase.blend so it matches what a
fresh build of sect/areas/summit.py makes (summit.lantern_places / place_lanterns). Run on the cloud box, on a copy
first:

    python E:/Github/PortfolioV5/.claude/worktrees/guide-accessibility-4c9cf8/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r61_lanterns.py [-- DRY_RUN=1]

Why: the night bake (bake_web.py --light night) lets lanterns light what is round them, but at the summit's hold only
the qin lamp in the pavilion's open bay was lit.

What it adds (collection instances under summit.root, in the summit collection; no new prototype, mesh or material):
- 'summit.hang_lantern.0' .. '.7': a round hanging lantern at each pavilion column head, just outside the column
  (summit.ring_radius()), hung from the first solid an upward ray meets there (the bracket band or the eave); the
  abode tea pavilion's lantern (summit.RING_LANTERN: the same prototype).
- 'summit.stair_lantern.w', '.e': stone lanterns on the top tier behind the pavilion (summit.STAIR_LANTERN_XY: the stair
  head's spot mirrored to the back, since the condor crag hides the stair head at the framed hold), outside the axis's
  walk width, inside the tier's rail, on the tier; the middle tier stair pair's prototype (2.4 m).
The four stone lanterns the summit already has ('summit.lantern', '.001' .. '.003') are not touched. A keep-list
compare (patch_r48_keep.py) allows exactly these ten names (LANTERN_NAMES), never the prefix 'summit.lantern'.

State: 'old' (none of the ten), 'new' (all ten where summit.lantern_places puts them, on the expected prototypes) or
'stale' (anything else: the ones there go and all ten are placed again). Idempotent: on a patched file it prints
'PATCH nothing changed: not saving' and the same DIGEST.

Checks (any failure stops the patch before saving; DRY_RUN=1 runs everything and never saves):
- prototypes: the ring instances the abode's round lantern collection, the pair a 2.4 m stone lantern collection the
  summit already instanced; no prototype collection or prototype object added (counted apart from the placed ones),
  no mesh, material or scene added;
- hung: each ring lantern's cord top (its origin) has a pavilion solid above it within HUNG_MAX;
- grounded: each stone lantern's lowest points stand 0 to STAND_MAX over the top tier (a downward ray each), the
  lantern outside the walk (summit.TOP_STAIR_W about the axis) and inside the tier's rail circle (summit.TOP_RAIL_R);
- clear: every new lantern keeps CLEAR_MIN from the columns, lattices, blinds (and the qin set), rails and stairs,
  and crosses nothing else, except a ring lantern's cord top in the solid it hangs from;
- flight: chase.cam (every frame) never nearer than CAM_MIN to any of them;
- visible: at the summit's hold as the page frames it (HOLD - HOLD_BACK, 1600 x 900), a ray from the camera reaches at
  least SEEN_RING_MIN ring lanterns and both stone lanterns inside the frame (the unframed hold is logged);
- names and counts: exactly the ten names added (or none on a no-op), nothing removed but stale copies of them.
Prints 'PATCH CACHES needs audit' when it changed the file, and 'PATCH DIGEST <md5>'.
"""
import hashlib
import os
import re
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402  (CAMERA)
from sect.areas import summit as SU  # noqa: E402
from sect.lib import util as U  # noqa: E402

RES = (1600, 900)
HOLD = 1647                 # the summit's hold
HOLD_BACK = 8               # client/src/lib/sect/framing.ts STOP_FRAMING.summit: 8 frames back, no turn
CLEAR_MIN = 0.02            # m from columns, lattices, blinds, rails and stairs
CAM_MIN = 3.0               # m from chase.cam on any frame
HUNG_MAX = 0.005            # m: a ring lantern's cord top to the solid over it
STAND_MAX = 0.005           # m: a stone lantern's lowest points over the tier
HANG_ZONE = 0.06            # m: a ring lantern may cross the solid it hangs from only this near its cord top
STAND_ZONE = 0.01           # m: a stone lantern may cross its tier only this near its lowest point
SEEN_RING_MIN = 4
SEEN_SAMPLES = 80           # points per lantern for the visibility rays
MATCH_TOL = 1e-3            # m: a lantern in the file counts as placed when this near summit.lantern_places' spot
NEAR = 0.3                  # m round a lantern's box where the clearance check looks
OBSTACLES = (               # owner name rules -> what the 2 cm rule calls them
    ("column", re.compile(r"^summit\.pavilion\.col(_up)?(\.\d{3})?$")),
    ("lattice", re.compile(r"^summit\.pavilion\.gualuo")),
    ("blinds", re.compile(r"^summit\.(blinds|qin)")),
    ("rail", re.compile(r"^summit\.(rim_bal|tier_bal|arch_wing)")),
    ("stairs", re.compile(r"^summit\.(tier_mid_stairs|tier_top_stairs|pavilion\.steps)")),
)
PASS_PREFIX = ("world.haze", "world.cloud", "world.moon_halo", "world.cirrus")   # visibility rays pass through these


def log(*a):
    print("PATCH", *a, flush=True)


def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    dry = False
    for a in argv:
        k, eq, v = a.partition("=")
        if k == "DRY_RUN" and eq:
            dry = v.strip().lower() not in ("", "0", "false", "no")
        else:
            raise SystemExit("patch_r61_lanterns: unknown option %r (DRY_RUN=1)" % a)
    return dry


class Fail(list):
    def add(self, msg):
        log("FAIL", msg)
        self.append(msg)


# ------------------------------------------------------------------------------------------------------ geometry

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
    return co.reshape(nv, 3)[tv.reshape(nt, 3)] if nt else np.zeros((0, 3, 3))


def near_tris(dg, root, lo, hi, skip=(), skip_prefix=()):
    """{owner: (n, 3, 3) triangles in ``root``'s frame} of every evaluated mesh with triangles in the box lo..hi (an
    instance counts as its instancer's), but owners in ``skip`` or starting with ``skip_prefix``."""
    Rinv = np.array(root.matrix_world.inverted(), float)
    cache, out = {}, {}
    pre = PASS_PREFIX + tuple(skip_prefix)
    for inst in dg.object_instances:
        o = inst.object
        if o.type != 'MESH':
            continue
        own = inst.parent.original.name if inst.is_instance and inst.parent else o.original.name
        if own in skip or own.startswith(pre):
            continue
        W = Rinv @ np.array(inst.matrix_world, float)
        bb = np.array(o.bound_box, float) @ W[:3, :3].T + W[:3, 3]
        if (bb.min(0) > hi).any() or (bb.max(0) < lo).any():
            continue
        key = (o.original.name, o.data.name)
        if key not in cache:
            cache[key] = local_tris(o.data)
        L = cache[key]
        if not len(L):
            continue
        T = L @ W[:3, :3].T + W[:3, 3]
        keep = ~((T.min(1) > hi).any(1) | (T.max(1) < lo).any(1))
        if keep.any():
            out.setdefault(own, []).append(T[keep])
    return {k: np.concatenate(v) for k, v in out.items()}


def obstacle(own):
    return next((kind for kind, rx in OBSTACLES if rx.match(own)), None)


def min_dist(TA, TB, bA, bB):
    """Smallest vertex-to-surface distance between two triangle sets, both ways (vertices sampled to ~4000)."""
    d = 9.0
    for V, tree in ((TB.reshape(-1, 3), bA), (TA.reshape(-1, 3), bB)):
        for p in V[::max(1, len(V) // 4000)]:
            h = tree.find_nearest(Vector(p))
            if h[0] is not None:
                d = min(d, h[3])
    return d


def sig(ob):
    h = hashlib.md5()
    h.update(ob.name.encode())
    h.update((ob.parent.name if ob.parent else "").encode())
    h.update(np.round(np.array(ob.matrix_basis), 4).tobytes())
    h.update((ob.instance_collection.name if ob.instance_collection else "").encode())
    return h.hexdigest()


def digest(names):
    h = hashlib.md5()
    for nm in sorted(names):
        ob = bpy.data.objects.get(nm)
        h.update(nm.encode())
        if ob is not None:
            h.update(sig(ob).encode())
    return h.hexdigest()


# ------------------------------------------------------------------------------------------------------ the view

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


def pass_through(sc):
    """Objects the visibility rays pass through: hidden from renders, volume-only, haze and clouds."""
    vol = {m.name for m in bpy.data.materials
           if m.node_tree is not None and any(n.bl_idname.startswith("ShaderNodeVolume") for n in m.node_tree.nodes)}
    out = set()
    for ob in sc.objects:
        if ob.hide_render or ob.name.startswith(PASS_PREFIX) or ob.type == 'VOLUME':
            out.add(ob.name)
        elif ob.material_slots and all(s.material is not None and s.material.name in vol for s in ob.material_slots):
            out.add(ob.name)
    return out


def first_hit(sc, dg, eye, p, skip):
    """(location, object) of the first thing a ray from ``eye`` toward ``p`` meets, passing through ``skip``."""
    d = Vector(p) - eye
    dist = d.length
    d.normalize()
    o = eye.copy()
    for _ in range(12):
        hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, o, d, distance=max(dist + 0.05 - (o - eye).length, 1e-3))
        if not hit:
            return None, None
        src = getattr(ob, "original", ob) if ob is not None else None
        if src is not None and src.name in skip:
            o = loc + d * 0.01
            continue
        return loc, src
    return None, None


def visibility(sc, cam, frame, lanterns, skip, label):
    """{name: (inside share, seen share, box, distance)} at ``frame`` (the camera as chase.cam is there, no turn)."""
    sc.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    Mw = cam.matrix_world.copy()
    proj = projector(sc, cam, Mw)
    eye = Mw.translation.copy()
    out = {}
    for nm, (pts, lo, hi, protos) in lanterns.items():
        step = max(1, len(pts) // SEEN_SAMPLES)
        sample = pts[::step]
        inside, seen, xy = 0, 0, []
        for p in sample:
            s = proj(p)
            if s is None or not (0.0 <= s[0] <= RES[0] and 0.0 <= s[1] <= RES[1]):
                continue
            inside += 1
            xy.append(s)
            loc, src = first_hit(sc, dg, eye, p, skip)
            if loc is not None and src is not None and src.name in protos and \
                    all(lo[i] - 0.05 <= loc[i] <= hi[i] + 0.05 for i in range(3)):
                seen += 1
        box = (min(x for x, _ in xy), max(x for x, _ in xy), min(y for _, y in xy), max(y for _, y in xy)) if xy else None
        dist = (Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2)) - eye).length
        out[nm] = (inside / max(1, len(sample)), seen / max(1, len(sample)), box, dist, seen)
        log("visible %s %s: %d of %d points in the frame, %d reached (%.0f%%), box %s, %.1f m" % (
            label, nm, inside, len(sample), seen, 100.0 * seen / max(1, len(sample)),
            [round(v) for v in box] if box else None, dist))
    return out


# ------------------------------------------------------------------------------------------------------------- main

def main():
    dry = options()
    t0 = time.time()
    fail = Fail()
    sc = bpy.context.scene
    keep_frame = sc.frame_current
    need = ["summit.root", "summit.pavilion", "summit.tier_top", EW.CAMERA]
    miss = [n for n in need if bpy.data.objects.get(n) is None]
    if miss:
        log("NOT SAVED: %s not found: is this out/sect_chase.blend?" % miss)
        raise SystemExit(1)
    root = bpy.data.objects["summit.root"]
    pav = bpy.data.objects["summit.pavilion"]
    tier = bpy.data.objects["summit.tier_top"]
    cam = bpy.data.objects[EW.CAMERA]
    coll = bpy.data.collections.get(SU.KEY)
    if coll is None or pav.name not in coll.objects:
        log("NOT SAVED: no '%s' collection holding %s" % (SU.KEY, pav.name))
        raise SystemExit(1)
    sx = root.matrix_world.to_scale()
    if max(abs(s - 1.0) for s in sx) > 1e-5:
        log("NOT SAVED: summit.root is scaled %s: the checks measure in its frame" % tuple(sx))
        raise SystemExit(1)
    # the prototypes the new lanterns must share
    ring_src = [o for o in bpy.data.objects if re.match(r"^abode\.lantern(\.\d{3})?$", o.name)
                and o.instance_collection is not None and "lantern_round" in o.instance_collection.name]
    ring_pc = {o.instance_collection.name for o in ring_src}
    old_stone = [o for o in coll.objects if re.match(r"^summit\.lantern(\.\d{3})?$", o.name)]
    stone_pc = {o.instance_collection.name for o in old_stone if o.instance_collection is not None
                and ".stone_lantern.2p4." in "." + o.instance_collection.name + "."}
    log("sources: ring radius %.3f m (%s, size %.2f, cord %.2f), gap %.2f, ray from %.1f m over the floor; stair pair at "
        "(+-%.2f, %.2f), %.1f m; abode round lanterns %s -> %s; summit stone lanterns %s -> 2.4 m %s" % (
            SU.ring_radius(), SU.RING_LANTERN["style"], SU.RING_LANTERN["size"], SU.RING_LANTERN["cord"], SU.RING_GAP,
            SU.RING_RAY_FROM, SU.STAIR_LANTERN_XY[0], SU.STAIR_LANTERN_XY[1], SU.STAIR_LANTERN_H,
            sorted(o.name for o in ring_src), sorted(ring_pc), sorted(o.name for o in old_stone), sorted(stone_pc)))
    if len(ring_pc) != 1 or len(stone_pc) != 1:
        log("NOT SAVED: want one abode round-lantern prototype (have %s) and one 2.4 m summit stone-lantern prototype "
            "(have %s)" % (sorted(ring_pc), sorted(stone_pc)))
        raise SystemExit(1)
    ring_pc, stone_pc = ring_pc.pop(), stone_pc.pop()
    want_pc = {nm: (ring_pc if nm in SU.RING_NAMES else stone_pc) for nm in SU.LANTERN_NAMES}
    names0 = {o.name for o in bpy.data.objects}
    protos_root = bpy.data.collections.get(U.PROTO_ROOT)
    proto_colls0 = sorted(c.name for c in protos_root.children_recursive) if protos_root else []
    proto_objs0 = sorted(o.name for o in protos_root.all_objects) if protos_root else []
    counts0 = (len(bpy.data.meshes), len(bpy.data.materials), sorted(s.name for s in bpy.data.scenes),
               len(bpy.data.collections))
    log("before: %d objects, %d prototype collections holding %d prototype objects, %d meshes, %d materials" % (
        len(names0), len(proto_colls0), len(proto_objs0), counts0[0], counts0[1]))

    # ---- where the lanterns go, and the file's state
    try:
        places = SU.lantern_places(root, pav, tier, log=lambda *a: log("place", *a))
    except RuntimeError as e:
        log("NOT SAVED: %s" % e)
        raise SystemExit(1)
    have = {nm: bpy.data.objects.get(nm) for nm in SU.LANTERN_NAMES}
    if not any(have.values()):
        state = "old"
    else:
        off = []
        for pl in places:
            ob = have[pl["name"]]
            if ob is None:
                off.append("%s missing" % pl["name"])
                continue
            d = (ob.matrix_basis.translation - Vector(pl["location"])).length
            turned = max(abs(a) for a in ob.matrix_basis.to_3x3().normalized().to_euler())
            if ob.parent != root or d > MATCH_TOL or turned > 1e-6 or ob.instance_collection is None or \
                    ob.instance_collection.name != want_pc[pl["name"]] or coll not in ob.users_collection:
                off.append("%s (%.4f m off, turned %.2g rad, parent %s, instances %s)" % (
                    pl["name"], d, turned, ob.parent.name if ob.parent else None,
                    ob.instance_collection.name if ob.instance_collection else None))
        state = "new" if not off else "stale"
        if off:
            log("differs:", "; ".join(off))
    log("state:", state)
    todo = state != "new"

    # ---- apply
    removed, added = [], []
    if todo:
        for nm, ob in have.items():
            if ob is not None:
                log("remove", nm, "(stale)")
                bpy.data.objects.remove(ob, do_unlink=True)
                removed.append(nm)
        try:
            made = SU.place_lanterns(coll, root, places)
        except RuntimeError as e:
            log("NOT SAVED: %s" % e)
            raise SystemExit(1)
        added = [o.name for o in made]
        log("placed:", ", ".join(added))
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    obs = {nm: bpy.data.objects.get(nm) for nm in SU.LANTERN_NAMES}

    # ---- prototypes and counts
    for nm, ob in obs.items():
        if ob is None:
            fail.add("%s missing" % nm)
        elif ob.instance_collection is None or ob.instance_collection.name != want_pc[nm]:
            fail.add("%s instances %s, want %s" % (nm, ob.instance_collection.name if ob.instance_collection else None,
                                                   want_pc[nm]))
    proto_colls1 = sorted(c.name for c in protos_root.children_recursive) if protos_root else []
    proto_objs1 = sorted(o.name for o in protos_root.all_objects) if protos_root else []
    counts1 = (len(bpy.data.meshes), len(bpy.data.materials), sorted(s.name for s in bpy.data.scenes),
               len(bpy.data.collections))
    log("after: %d prototype collections holding %d prototype objects (before %d / %d); meshes %d, materials %d, "
        "collections %d (before %d, %d, %d)" % (len(proto_colls1), len(proto_objs1), len(proto_colls0), len(proto_objs0),
                                                counts1[0], counts1[1], counts1[3], counts0[0], counts0[1], counts0[3]))
    if proto_colls1 != proto_colls0 or proto_objs1 != proto_objs0:
        fail.add("prototypes changed: collections +%s -%s, objects +%d -%d" % (
            sorted(set(proto_colls1) - set(proto_colls0)), sorted(set(proto_colls0) - set(proto_colls1)),
            len(set(proto_objs1) - set(proto_objs0)), len(set(proto_objs0) - set(proto_objs1))))
    if counts1 != counts0:
        fail.add("meshes / materials / scenes / collections changed: %s -> %s" % (counts0, counts1))
    names1 = {o.name for o in bpy.data.objects}
    came, gone = sorted(names1 - names0), sorted(names0 - names1)
    want_came = sorted(set(added) - set(removed))
    want_gone = sorted(set(removed) - set(added))
    log("placed objects: added %s, removed %s" % (came, gone))
    if came != want_came or gone != want_gone:
        fail.add("objects added %s / removed %s, expected %s / %s" % (came, gone, want_came, want_gone))

    # ---- geometry of the new lanterns (root frame) and what is round them
    places_by = {pl["name"]: pl for pl in places}
    Rinv = root.matrix_world.inverted()
    at = {nm: (Rinv @ ob.matrix_world).translation.copy() for nm, ob in obs.items() if ob is not None}
    own_T = {k: v for k, v in SU.owner_tris(dg, root, set(SU.LANTERN_NAMES)).items() if len(v)}
    for nm in SU.LANTERN_NAMES:
        if obs[nm] is not None and nm not in own_T:
            fail.add("%s: no evaluated geometry" % nm)
    if not own_T:
        log("NOT SAVED: no lantern geometry")
        raise SystemExit(1)
    allV = np.concatenate([T.reshape(-1, 3) for T in own_T.values()])
    lo_all, hi_all = allV.min(0), allV.max(0)
    # everything near them but the world's meshes (the range's terrain is metres under the tiers; its millions of
    # triangles would only cost time)
    around = near_tris(dg, root, lo_all - NEAR, hi_all + NEAR, skip=set(SU.LANTERN_NAMES), skip_prefix=("world.",))
    log("near the lanterns: %d owners, %d triangles (world.* left out)" % (
        len(around), sum(len(v) for v in around.values())))
    pav_set, tier_set = SU.subtree(pav), SU.subtree(tier)
    pav_T = [T for k, T in around.items() if k in pav_set]
    tier_T = [T for k, T in around.items() if k in tier_set]
    b_pav = SU.tri_bvh(np.concatenate(pav_T)) if pav_T else None
    b_tier = SU.tri_bvh(np.concatenate(tier_T)) if tier_T else None

    # ---- hung and grounded
    for nm, T in own_T.items():
        pl = places_by[nm]
        p = at[nm]                       # the lantern's origin as it stands (a ring lantern's cord top)
        if pl["kind"] == "ring":
            h = b_pav.ray_cast(p - Vector((0.0, 0.0, 0.002)), Vector((0.0, 0.0, 1.0)), 1.0) if b_pav else (None,) * 4
            gap = (h[0].z - p.z) if h[0] is not None else 9.0
            log("hung %s: the solid over its cord top %.4f m above it (%s)" % (nm, gap, pl.get("hung_on")))
            if not 0.0 <= gap <= HUNG_MAX:
                fail.add("%s: its cord top is %.4f m from the solid over it (want 0..%.3f)" % (nm, gap, HUNG_MAX))
        else:
            V = T.reshape(-1, 3)
            zmin = V[:, 2].min()
            sole = V[V[:, 2] < zmin + 0.002]
            gaps = []
            for q in sole[::max(1, len(sole) // 200)]:
                h = b_tier.ray_cast(Vector((q[0], q[1], q[2] + 0.5)), Vector((0.0, 0.0, -1.0)), 3.0) if b_tier \
                    else (None,) * 4
                gaps.append(9.0 if h[0] is None else q[2] - h[0].z)
            log("grounded %s: %d sole points %.4f..%.4f m over %s" % (nm, len(gaps), min(gaps), max(gaps), tier.name))
            if min(gaps) < 0.0 or max(gaps) > STAND_MAX:
                fail.add("%s: its sole is %.4f..%.4f m over the tier (want 0..%.3f)" % (nm, min(gaps), max(gaps),
                                                                                       STAND_MAX))
            # outside the walk (the top stair's width, on the axis x = 0), inside the tier's rail circle
            inner = float(np.abs(V[:, 0]).min())
            outer = float(np.hypot(V[:, 0], V[:, 1]).max())
            log("walk %s: %.3f m from the axis (the walk's edge at %.2f), %.3f m from the tier's centre (rail circle "
                "%.2f)" % (nm, inner, SU.TOP_STAIR_W / 2, outer, SU.TOP_RAIL_R))
            if inner < SU.TOP_STAIR_W / 2 + CLEAR_MIN:
                fail.add("%s reaches %.3f m from the axis, into the walk (edge %.2f)" % (nm, inner, SU.TOP_STAIR_W / 2))
            if outer > SU.TOP_RAIL_R - CLEAR_MIN:
                fail.add("%s reaches %.3f m from the tier's centre, past the rail circle %.2f" % (nm, outer,
                                                                                               SU.TOP_RAIL_R))

    # ---- clear
    for nm, T in own_T.items():
        pl = places_by[nm]
        lo, hi = T.reshape(-1, 3).min(0) - NEAR, T.reshape(-1, 3).max(0) + NEAR
        bA = SU.tri_bvh(T)
        rows = []
        for own, To in around.items():
            keep = ~((To.min(1) > hi).any(1) | (To.max(1) < lo).any(1))
            if not keep.any():
                continue
            To = To[keep]
            bB = SU.tri_bvh(To)
            pairs = bA.overlap(bB)
            d = min_dist(T, To, bA, bB)
            kind = obstacle(own)
            rows.append((d, own, len(pairs), kind))
            if kind is not None:
                if pairs or d < CLEAR_MIN:
                    fail.add("%s: %.3f m from %s %s (%d crossing triangle pairs), want %.2f" % (
                        nm, d, kind, own, len(pairs), CLEAR_MIN))
                continue
            if not pairs:
                continue
            if pl["kind"] == "ring" and own == pl.get("hung_on"):
                top = np.array(at[nm], float)
                far = [i for i, _j in pairs if np.linalg.norm(T[i].mean(0) - top) > HANG_ZONE]
                if far:
                    fail.add("%s crosses %s, the solid it hangs from, %d triangles away from its cord top" % (
                        nm, own, len(far)))
            elif pl["kind"] == "stair" and own in tier_set:
                zmin = T[:, :, 2].min()
                far = [i for i, _j in pairs if T[i][:, 2].max() > zmin + STAND_ZONE]
                if far:
                    fail.add("%s crosses its tier %s above its sole (%d triangles)" % (nm, own, len(far)))
            else:
                fail.add("%s crosses %s (%d triangle pairs)" % (nm, own, len(pairs)))
        rows.sort()
        log("clear %s: nearest %s" % (nm, ", ".join("%s%s %.3f m%s" % (o, " (%s)" % k if k else "", d,
                                                                      " (meets %d)" % n if n else "")
                                                     for d, o, n, k in rows[:6]) or "nothing within %.1f m" % NEAR))

    # ---- flight: chase.cam on every frame (its F-curves, checked against the scene at the hold; else frame by frame)
    trees = {nm: SU.tri_bvh(T) for nm, T in own_T.items()}
    frames = list(range(sc.frame_start, sc.frame_end + 1))
    pos = None
    try:
        pos = [M.translation.copy() for M in EW.sample_matrices(cam, frames)]
        sc.frame_set(HOLD)
        if HOLD in frames and (pos[frames.index(HOLD)] - cam.matrix_world.translation).length > 0.01:
            log("flight: chase.cam's F-curves miss its pose at %d: sampling frame by frame" % HOLD)
            pos = None
    except Exception as e:  # noqa: BLE001  (a parented or constrained camera)
        log("flight: sampling chase.cam frame by frame (%s)" % e)
        pos = None
    if pos is None:
        pos = []
        for f in frames:
            sc.frame_set(f)
            pos.append(cam.matrix_world.translation.copy())
    sc.frame_set(keep_frame)
    near = {}
    for f, pw in zip(frames, pos):
        p = Rinv @ pw
        for nm, tr in trees.items():
            h = tr.find_nearest(p)
            if h[0] is not None and (nm not in near or h[3] < near[nm][0]):
                near[nm] = (h[3], f)
    for nm in sorted(near, key=lambda n: near[n][0]):
        d, f = near[nm]
        log("flight %s: %.1f m from chase.cam at its nearest (frame %d)" % (nm, d, f))
        if d < CAM_MIN:
            fail.add("chase.cam passes %.2f m from %s (frame %d), want %.0f m" % (d, nm, f, CAM_MIN))

    # ---- visible at the hold, as the page frames it
    rx, ry, rp = sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES[0], RES[1], 100
    try:
        skip = pass_through(sc)
        Mr = np.array(root.matrix_world, float)
        lanterns = {}
        for nm, T in own_T.items():
            V = T.reshape(-1, 3)
            W = V @ Mr[:3, :3].T + Mr[:3, 3]
            pts = [Vector(p) for p in np.unique(np.round(W, 4), axis=0)]
            ob = obs[nm]
            protos = {o.name for o in ob.instance_collection.all_objects}
            lanterns[nm] = (pts, W.min(0), W.max(0), protos)
        framed = visibility(sc, cam, HOLD - HOLD_BACK, lanterns, skip, "%d (the hold, %d back)" % (HOLD, HOLD_BACK))
        visibility(sc, cam, HOLD, lanterns, skip, "%d (unframed, logged)" % HOLD)
    finally:
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, rp
        sc.frame_set(keep_frame)
    ring_seen = [nm for nm in SU.RING_NAMES if nm in framed and framed[nm][4] > 0]
    stair_seen = [nm for nm in SU.STAIR_LANTERN_NAMES if nm in framed and framed[nm][4] > 0]
    log("visible at %d: ring %d of %d (%s), stair pair %d of 2 (%s)" % (
        HOLD - HOLD_BACK, len(ring_seen), len(SU.RING_NAMES), ", ".join(ring_seen), len(stair_seen),
        ", ".join(stair_seen)))
    if len(ring_seen) < SEEN_RING_MIN:
        fail.add("only %d ring lanterns are seen at the hold (want %d)" % (len(ring_seen), SEEN_RING_MIN))
    if len(stair_seen) < 2:
        fail.add("only %d of the stair pair are seen at the hold" % len(stair_seen))

    # ---- report
    log("DIGEST", digest(SU.LANTERN_NAMES))
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail:
            log("  -", f)
        raise SystemExit(1)
    if not todo:
        log("CACHES ok: nothing changed")
        log("nothing changed: not saving (%.1f s)" % (time.time() - t0))
        return
    log("CACHES needs audit: new %s - run export_web.py -- audit --profile full, then -- chunks,meta --profile full, "
        "then bake_web.py -- bakefull --profile full --chunks summit (--light night), then the trees, then pack" % added)
    if dry:
        log("DRY_RUN: checks passed, not saving (%.1f s)" % (time.time() - t0))
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "(%.1f s)" % (time.time() - t0))


if __name__ == "__main__":
    main()
