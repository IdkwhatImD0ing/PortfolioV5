"""Round 55: prop placement with intent (docs/scene/placement-r55.md), in an existing out/sect_chase.blend, so it
matches what a fresh build of areas/forge.py, mission.py, scroll.py and mirror.py makes. Every place comes from those
modules (their round-55 tables and the round-54 ones they replaced), never from this file. Run on the cloud box, on a
copy first:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r55_placement.py -- [DRY_RUN=1] \
        [PARTS=forge,mission,scroll,mirror]

Why (owner, 2026-11-09): "some of the objects in the scene are haphazardly placed". Yard dressing that was typed in one
spot at a time now follows a rule: a formal place is symmetric on its axis and keeps one spacing along a walk, working
things stand in groups that make sense as a workplace, and fewer pieces, each with a reason.

What it does (PARTS, default all four):
- forge (hold 352): the yard becomes two smith's bays. The west bay is the east one (the smith's corner) mirrored across
  the axis (forge.west_place): 'forge.weapon_rack', 'forge.anvil.002' and quench trough 1. Trough 1 was the round-12
  build (its boxes baked at forge.TROUGH_1_R54), so 'forge.trough.1' and 'forge.trough_water.1' are rebuilt by
  forge._quench_trough under the same names, each object at its place, turned. 'forge.weapon_rack.002' and '.003'
  flank the east workshop's porch; 'forge.ore.002' goes to the east workshop's hall-side corner, '.001' and '.004'
  join 'forge.ore' by the bridge gate (forge.yard_moves). 'forge.anvil.001' is removed (forge.YARD_GONE).
- mission (619): the front pair of stone lanterns ('mission.stone_lantern', '.001') leaves the Big Dipper's drums
  for the arrival landing, marking the way in (mission.lantern_moves).
- scroll (1103): the stair's lantern pair ('scroll.lantern_stone', '.001') joins the walk's 9 m beat; the three scholar
  rocks with their pedestals ('scroll.rock.<i>', 'scroll.rock_pedestal.<i>') move to the walk's right: two flank the
  way to the side steps, the tall one stands by the peach (scroll.r55_moves).
- mirror (217): 'mirror.boulder.003' moves to the foot of the west scholar's rock (mirror.boulder_moves).
Moved objects keep their names, meshes, height and (unless the table turns them) their turn.

State: each part is 'old' (every piece at its round-54 place, trough 1 the round-12 build, forge.anvil.001 there) or
'r55' (every piece at its new place, trough 1 as a scratch build of forge._quench_trough makes it, the anvil gone:
nothing to do). Anything else stops the patch before it changes anything. Idempotent: on a patched file it prints
'PATCH nothing changed: not saving' and the same DIGEST.

Checks (any failure stops the patch before saving; DRY_RUN=1 runs everything and never saves):
- grounded: each moved piece's foot points (its lowest vertices) have their floor under them (FLOORS, rays down onto
  the floor meshes only; a scholar rock's floor is its own pedestal), sunk 0 to SINK_MAX (or up to SINK_FLOAT over it), and as deep as at its old
  place when this run moved it (SINK_TOL: each builder sets a piece's height for its floor, so a flat floor gives the
  same sink anywhere; the mirror's lawn undulates);
- clear: nothing but the floor it stands on and its own companions (trough and water, rock and pedestal) crosses a
  moved piece or comes within CLEAR_MIN of it; the nearest five neighbours are logged;
- gone: 'forge.anvil.001' and any mesh only it used are gone;
- still: no other object's world matrix changed and none vanished;
- names and counts: objects change by exactly minus the removed pieces (the trough pair comes back under its own
  names); no scratch data, no new scene.
Prints 'PATCH CACHES needs chunks,meta; bakefull <the changed parts>,backdrop' and 'PATCH DIGEST <md5>' of the touched
objects' names and world matrices (and trough 1's meshes, which are rebuilt).
"""
import hashlib
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import forge as F  # noqa: E402
from sect.areas import mirror as MR  # noqa: E402
from sect.areas import mission as MI  # noqa: E402
from sect.areas import scroll as SC  # noqa: E402
from sect.lib import util as U  # noqa: E402

PARTS = ("forge", "mission", "scroll", "mirror")
SCRATCH = "~r55"
PLACE_TOL = 1e-4           # m
TURN_TOL = 1e-5            # rad
STILL_TOL = 1e-5           # world matrix entries: every other object stays put
CLEAR_MIN = 0.02           # m
FOOT_BAND = 0.005          # m: a piece's foot points are its vertices this close to its lowest
SINK_MAX = 0.3             # m: no foot point deeper under its floor (a scholar rock sits 0.12-0.17 into its pedestal)
SINK_FLOAT = 0.005         # m: ... nor higher over it (the racks' and stone lanterns' feet are built 3 mm up)
SINK_TOL = dict(flat=0.003, lawn=0.1)   # m: the new sink against the old one (the mirror's lawn undulates 0.08)
SKIP = ("world.haze", "world.range", "world.roots", "world.stream", "world.cloud")
# what each part's pieces stand on (an object, or anything named '<it>.<...>')
# (the mission's arrival landing is one slab, 'mission.arrival', level with the plaza; its rail is 'mission.arrival_rail')
FLOORS = dict(forge=("forge.paving",), mission=("mission.plaza", "mission.arrival"), scroll=("scroll.terrace",),
              mirror=("mirror.lawn",))


def log(*a):
    print("PATCH", *a, flush=True)


def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    dry, parts = False, PARTS
    for a in argv:
        k, eq, v = a.partition("=")
        if k == "DRY_RUN" and eq:
            dry = v.strip().lower() not in ("", "0", "false", "no")
        elif k == "PARTS" and eq:
            parts = tuple(p.strip() for p in v.split(",") if p.strip())
            bad = [p for p in parts if p not in PARTS]
            if bad or not parts:
                raise SystemExit("patch_r55_placement: unknown parts %s (known: %s)" % (bad, ",".join(PARTS)))
        else:
            raise SystemExit("patch_r55_placement: unknown option %r (DRY_RUN=1, PARTS=%s)" % (a, ",".join(PARTS)))
    return dry, parts


class Fail(list):
    def add(self, msg):
        log("FAIL", msg)
        self.append(msg)


# ---------------------------------------------------------------------------------------------- what moves (tables)

def moves(part):
    """{name: ((x, y, rz or None) now, (x, y, rz or None) until round 54)} of the part's moved objects, from its area
    module (rz None: the patch leaves the turn alone)."""
    if part == "forge":
        return dict(F.yard_moves())
    tab = {"mission": MI.lantern_moves, "scroll": SC.r55_moves, "mirror": MR.boulder_moves}[part]()
    return {n: ((a[0], a[1], None), (b[0], b[1], None)) for n, (a, b) in tab.items()}


def groups(part):
    """[(label, names, feet)]: each moved piece with its companions (built as a pair at one place by its builder);
    feet [(names, floors, floor kind)] say what stands on what."""
    mv = moves(part)
    fl = FLOORS[part]
    out = []
    if part == "scroll":
        for i in range(len(SC.ROCKS)):
            rock, ped = SC.rock_names(i)
            if rock in mv or ped in mv:
                out.append(("rock %d" % i, [rock, ped], [([ped], fl, "flat"), ([rock], (ped,), "flat")]))
    taken = {n for _l, names, _f in out for n in names}
    kind = "lawn" if part == "mirror" else "flat"
    out += [(n, [n], [([n], fl, kind)]) for n in sorted(mv) if n not in taken]
    if part == "forge":
        tr, tw = F.trough_names(1)
        out.append(("trough 1", [tr, tw], [([tr], fl, "flat")]))
    return out


def touched(parts):
    """Every object name this round may move, rebuild or remove in ``parts`` (with anything parented under them)."""
    names = set()
    for p in parts:
        names |= set(moves(p))
        if p == "forge":
            names |= set(F.trough_names(1)) | set(F.YARD_GONE)
    for n in list(names):
        if obj(n) is not None:
            names |= {o.name for o in tree(obj(n))}
    return names


# ---------------------------------------------------------------------------------------------------- object helpers

def obj(name):
    return bpy.data.objects.get(name)


def tree(ob):
    return [ob] + list(ob.children_recursive)


def resolve(prefixes):
    """Names of the objects called one of ``prefixes`` or '<prefix>.<anything>'."""
    return sorted(o.name for o in bpy.data.objects if any(o.name == p or o.name.startswith(p + ".") for p in prefixes))


def ang(a, b):
    return abs((a - b + math.pi) % (2.0 * math.pi) - math.pi)


def at(ob, place):
    x, y, rz = place
    return abs(ob.location.x - x) <= PLACE_TOL and abs(ob.location.y - y) <= PLACE_TOL and \
        (rz is None or ang(ob.rotation_euler.z, rz) <= TURN_TOL)


def where(ob):
    return "(%.3f, %.3f) turned %.2f deg" % (ob.location.x, ob.location.y, math.degrees(ob.rotation_euler.z))


def in_frame(ob, part, fail):
    """The piece is placed in its area's frame (parented straight to the root, no parent inverse, Euler turn), so its
    location is the module's (x, y)."""
    root = obj(part + ".root")
    ok = ob.parent == root and ob.rotation_mode == 'XYZ' and \
        np.allclose(np.array(ob.matrix_parent_inverse), np.eye(4), atol=1e-6)
    if not ok:
        fail.add("%s: not placed in %s's frame (parent %s, rotation mode %s)" % (
            ob.name, root.name if root else part, ob.parent.name if ob.parent else None, ob.rotation_mode))
    return ok


def delete_tree(ob, removed):
    """Delete ``ob`` and its children (and meshes left with no user); their names go to ``removed``."""
    removed += [o.name for o in tree(ob)]
    U.delete_hierarchy(ob)


def faces_sig(me):
    """Order-free fingerprint of a mesh: every face as its rounded corners (cyclic from the smallest) and material."""
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


class Scratch:
    """A scratch collection for builds compared with the file's objects (dropped with everything in it)."""

    def __init__(self):
        self.coll = bpy.data.collections.new(SCRATCH + ".coll")
        bpy.context.scene.collection.children.link(self.coll)

    def drop(self):
        for ob in list(self.coll.all_objects):
            d = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if isinstance(d, bpy.types.Mesh) and d.users == 0:
                bpy.data.meshes.remove(d)
        bpy.data.collections.remove(self.coll)


# ------------------------------------------------------------------------------------------------- trough 1 (forge)

def trough_sig(ob):
    return faces_sig(ob.data), tuple(round(v, 4) for v in ob.location), round(ob.rotation_euler.z, 5)


def trough_scratch(sc_):
    """{name: trough_sig} of trough 1 as forge._quench_trough builds it now (scratch objects)."""
    keep = set(o.name for o in bpy.data.objects)
    F._quench_trough(obj("forge.root"), sc_.coll, 1, *F.TROUGH_1)
    tr, tw = F.trough_names(1)
    return {(tw if o.name.startswith(tw) else tr): trough_sig(o) for o in bpy.data.objects if o.name not in keep}


def trough_old():
    """Trough 1 as the round-12 build made it: each object at the area's origin, unturned, its box centred on
    forge.TROUGH_1_R54."""
    for n in F.trough_names(1):
        ob = obj(n)
        co = np.empty(len(ob.data.vertices) * 3)
        ob.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        c = 0.5 * (co[:, :2].min(0) + co[:, :2].max(0))
        if ob.location.length > PLACE_TOL or ang(ob.rotation_euler.z, 0.0) > TURN_TOL or \
                np.abs(c - np.array(F.TROUGH_1_R54)).max() > 1e-3:
            return False
    return True


# ------------------------------------------------------------------------------------------------------------ states

def part_state(part, sc_, fail):
    """'old', 'r55' or 'unknown' (logged, and a failure)."""
    new, old, rows = [], [], []
    for n, (now, was) in sorted(moves(part).items()):
        ob = obj(n)
        if ob is None:
            fail.add("%s: %s is missing" % (part, n))
            return "unknown"
        if not in_frame(ob, part, fail):
            return "unknown"
        new.append(at(ob, now))
        old.append(at(ob, was))
        rows.append("%s %s %s" % (n, where(ob), "new" if new[-1] else "old" if old[-1] else "?"))
    if part == "forge":
        for n, was in sorted(F.YARD_GONE.items()):
            ob = obj(n)
            new.append(ob is None)
            old.append(ob is not None and at(ob, was))
            rows.append("%s %s" % (n, "gone" if ob is None else where(ob) + (" old" if old[-1] else " ?")))
        names = F.trough_names(1)
        if any(obj(n) is None or obj(n).type != 'MESH' for n in names):
            fail.add("forge: %s missing or not meshes" % (names,))
            return "unknown"
        want = trough_scratch(sc_)
        t_new = all(trough_sig(obj(n)) == want.get(n) for n in names)
        t_old = trough_old()
        new.append(t_new)
        old.append(t_old)
        rows.append("trough 1 %s" % ("as this build" if t_new else "the round-12 build" if t_old else "?"))
    log("%s: %s" % (part, "; ".join(rows)))
    if all(old):
        return "old"
    if all(new):
        return "r55"
    fail.add("%s: a state this patch does not know (%s)" % (part, "; ".join(r for r in rows if r.endswith("?"))))
    return "unknown"


def part_apply(part, removed, added, gone, fail):
    for n, (now, _was) in sorted(moves(part).items()):
        ob = obj(n)
        ob.location.x, ob.location.y = now[0], now[1]
        if now[2] is not None:
            ob.rotation_euler.z = now[2]
        kids = [o.name for o in tree(ob)[1:]]
        log("%s: %s now %s%s" % (part, n, where(ob), (" with %s" % kids) if kids else ""))
    if part != "forge":
        return
    for n in sorted(F.YARD_GONE):
        ob = obj(n)
        own = [o.data.name for o in tree(ob) if o.type == 'MESH' and o.data.users == 1]
        inst = ob.instance_collection.name if ob.instance_type == 'COLLECTION' and ob.instance_collection else None
        names = [o.name for o in tree(ob)]
        delete_tree(ob, removed)
        gone.append((names, own))
        log("forge: removed %s (%d objects; own meshes %s; instanced %s)" % (n, len(names), own or "none", inst))
    names = F.trough_names(1)
    coll = obj(names[0]).users_collection[0]
    for n in names:
        delete_tree(obj(n), removed)
    keep = set(o.name for o in bpy.data.objects)
    F._quench_trough(obj("forge.root"), coll, 1, *F.TROUGH_1)
    made = sorted(o.name for o in bpy.data.objects if o.name not in keep)
    added += made
    if made != sorted(names):
        fail.add("forge: trough 1 came back as %s, not %s" % (made, sorted(names)))
    x, y, rz = F.TROUGH_1
    log("forge: trough 1 rebuilt %s at (%.3f, %.3f) turned %.2f deg (the east bay's trough 0 mirrored)" % (
        made, x, y, math.degrees(rz)))


# ------------------------------------------------------------------------------------------------- geometry helpers

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


def bvh(T):
    return BVHTree.FromPolygons([Vector(p) for p in T.reshape(-1, 3)], [(3 * i, 3 * i + 1, 3 * i + 2)
                                                                       for i in range(len(T))], all_triangles=True)


def world_tris(dg, owners=None, near=None):
    """{owner: (n, 3, 3) world triangles} of the evaluated scene's meshes (instances under their instancer's name):
    these owners, or those whose box meets the box ``near`` (lo, hi). Objects hidden from renders are left out."""
    out = {}
    for inst in dg.object_instances:
        o = inst.object
        if o.type != 'MESH':
            continue
        own = inst.parent.original.name if inst.is_instance and inst.parent else o.original.name
        if (owners is not None and own not in owners) or own.startswith(SKIP) or own.startswith(SCRATCH):
            continue
        src = bpy.data.objects.get(own)
        if src is not None and src.hide_render:
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
            T = T[~((T.min(1) > near[1]).any(1) | (T.max(1) < near[0]).any(1))]
            if not len(T):
                continue
        out.setdefault(own, []).append(T)
    return {k: np.concatenate(v) for k, v in out.items()}


def obj_tris(dg, names):
    T = world_tris(dg, owners=set(names))
    return np.concatenate(list(T.values())) if T else np.zeros((0, 3, 3))


# ------------------------------------------------------------------------------------------------------------ checks

def feet(dg, names, floor_names):
    """(min sink, max sink, foot points without a floor under them, floors met, points) of ``names``: its foot points
    (vertices within FOOT_BAND of its lowest, at most 64) against the highest face of ``floor_names`` under each."""
    V = obj_tris(dg, names).reshape(-1, 3)
    if not len(V):
        return None, None, 0, [], 0
    P_ = np.unique(np.round(V[V[:, 2] < V[:, 2].min() + FOOT_BAND], 6), axis=0)
    if len(P_) > 64:
        P_ = P_[np.linspace(0, len(P_) - 1, 64).astype(int)]
    trees = {n: bvh(t) for n, t in world_tris(dg, owners=set(floor_names)).items()}
    sinks, miss, met = [], 0, set()
    for p in P_:
        best = None
        for n, tr in trees.items():
            loc, _nrm, _i, _d = tr.ray_cast(Vector((p[0], p[1], p[2] + 5.0)), Vector((0.0, 0.0, -1.0)), 15.0)
            if loc is not None and (best is None or loc.z > best[1]):
                best = (n, loc.z)
        if best is None:
            miss += 1
            continue
        sinks.append(best[1] - p[2])
        met.add(best[0])
    return (min(sinks) if sinks else None), (max(sinks) if sinks else None), miss, sorted(met), len(P_)


def part_feet(dg, part):
    """{(label, k): feet()} of every foot of the part's groups."""
    out = {}
    for label, _names, fts in groups(part):
        for k, (names, fl, _kind) in enumerate(fts):
            out[(label, k)] = feet(dg, names, resolve(fl))
    return out


def check_grounded(dg, part, before, fail):
    for label, _names, fts in groups(part):
        for k, (names, fl, kind) in enumerate(fts):
            lo, hi, miss, met, n = feet(dg, names, resolve(fl))
            was = before.get((label, k)) if before else None
            log("grounded %s %s: %d foot points on %s, sunk %s..%s m%s" % (
                part, "+".join(names), n, met, "%.3f" % lo if lo is not None else "-",
                "%.3f" % hi if hi is not None else "-",
                (" (at its old place %.3f..%.3f)" % (was[0], was[1])) if was and was[0] is not None else ""))
            if lo is None or miss:
                fail.add("%s %s: %d of %d foot points have no floor (%s) under them" % (part, label, miss, n, fl))
                continue
            if lo < -SINK_FLOAT or hi > SINK_MAX:
                fail.add("%s %s: its foot is sunk %.3f..%.3f m under %s (want %.3f..%.2f)" % (
                    part, label, lo, hi, met, -SINK_FLOAT, SINK_MAX))
            if was and was[0] is not None and (abs(lo - was[0]) > SINK_TOL[kind] or abs(hi - was[1]) > SINK_TOL[kind]):
                fail.add("%s %s: sunk %.3f..%.3f m, at its old place %.3f..%.3f (want within %.3f)" % (
                    part, label, lo, hi, was[0], was[1], SINK_TOL[kind]))


def check_clear(part, fail):
    """Per group: nothing but its floor and its own companions crosses it or comes within CLEAR_MIN."""
    dg = bpy.context.evaluated_depsgraph_get()
    gs = groups(part)
    own_all = {n for _l, names, _f in gs for n in names}
    V = obj_tris(dg, own_all).reshape(-1, 3)
    if not len(V):
        fail.add("%s: the moved pieces have no geometry" % part)
        return
    near = world_tris(dg, near=(V.min(0) - 1.0, V.max(0) + 1.0))
    floors = set(resolve(FLOORS[part]))
    for label, names, _f in gs:
        own = set(names)
        if not any(n in near for n in names):
            fail.add("%s %s: no geometry" % (part, label))
            continue
        T = np.concatenate([near[n] for n in names if n in near])
        lo, hi = T.reshape(-1, 3).min(0) - 0.5, T.reshape(-1, 3).max(0) + 0.5
        tw = bvh(T)
        Vs = np.unique(T.reshape(-1, 3), axis=0)
        rows = []
        for o, To in near.items():
            if o in own:
                continue
            To = To[~((To.min(1) > hi).any(1) | (To.max(1) < lo).any(1))]
            if not len(To):
                continue
            to = bvh(To)
            touch = len(tw.overlap(to))
            if o in floors:
                rows.append((0.0, o, touch, True))
                continue
            Vo = np.unique(To.reshape(-1, 3), axis=0)
            d = min(min(to.find_nearest(Vector(p))[3] for p in Vs), min(tw.find_nearest(Vector(p))[3] for p in Vo))
            rows.append((d, o, touch, False))
            if touch or d < CLEAR_MIN:
                fail.add("%s %s: %s is %.3f m from it (%d crossing triangle pairs)" % (part, label, o, d, touch))
        rows.sort(key=lambda r: (r[3], r[0]))
        log("clear %s %s: nearest %s" % (part, label, ", ".join(
            "%s %s" % (o, "(its floor)" if fl else "%.3f m" % d) for d, o, _t, fl in rows[:5]) or "nothing"))


def digest():
    """md5 of the round's objects (all four parts): names and world matrices, trough 1's meshes, the gone anvil."""
    h = hashlib.md5()
    names = sorted({n for p in PARTS for n in moves(p)} | set(F.trough_names(1)))
    for n in names:
        ob = obj(n)
        h.update(n.encode())
        if ob is None:
            h.update(b"absent")
            continue
        h.update((np.round(np.array(ob.matrix_world), 5) + 0.0).tobytes())
        if n in F.trough_names(1) and ob.type == 'MESH':
            h.update(faces_sig(ob.data).encode())
    for n in sorted(F.YARD_GONE):
        h.update(("%s:%s" % (n, obj(n) is not None)).encode())
    return h.hexdigest()


# -------------------------------------------------------------------------------------------------------------- main

def main():
    dry, parts = options()
    t0 = time.time()
    fail = Fail()
    for p in parts:
        if obj(p + ".root") is None:
            log("NOT SAVED: %s.root not found: is this out/sect_chase.blend?" % p)
            raise SystemExit(1)
    ax, ay, arz = F.west_place("anvil")
    rx, ry, rrz = F.west_place("rack")
    log("round 55: parts %s; the forge's west bay is the smith's corner (SMITH_AT %s, turned %.2f deg) mirrored: rack "
        "(%.2f, %.2f) %.2f deg, anvil (%.2f, %.2f) %.2f deg, trough 1 (%.2f, %.2f) %.2f deg" % (
            ",".join(parts), F.SMITH_AT, math.degrees(F.SMITH_YAW), rx, ry, math.degrees(rrz), ax, ay,
            math.degrees(arz), F.TROUGH_1[0], F.TROUGH_1[1], math.degrees(F.TROUGH_1[2])))
    bpy.context.view_layer.update()
    n_obj0 = len(bpy.data.objects)
    scenes0 = sorted(s.name for s in bpy.data.scenes)
    sc_ = Scratch()
    try:
        states = {p: part_state(p, sc_, fail) for p in parts}
    finally:
        sc_.drop()
    log("states: %s (%.1f s)" % (", ".join("%s %s" % kv for kv in states.items()), time.time() - t0))
    if fail:
        log("NOT SAVED: the file is not in a state this patch knows (%d problems)" % len(fail))
        raise SystemExit(1)
    todo = [p for p in parts if states[p] == "old"]
    dg = bpy.context.evaluated_depsgraph_get()
    before = {p: part_feet(dg, p) for p in todo}
    keep = touched(parts)
    still0 = {o.name: np.array(o.matrix_world) for o in bpy.data.objects if o.name not in keep}
    removed, added, gone = [], [], []
    for p in todo:
        part_apply(p, removed, added, gone, fail)
    bpy.context.view_layer.update()
    # after: every part is this build
    sc2 = Scratch()
    try:
        after = {p: part_state(p, sc2, fail) for p in parts}
    finally:
        sc2.drop()
    bpy.context.view_layer.update()
    log("after: states %s" % ", ".join("%s %s" % kv for kv in after.items()))
    if any(s != "r55" for s in after.values()):
        fail.add("after the patch the file is not this build: %s" % after)
    dg = bpy.context.evaluated_depsgraph_get()
    for p in parts:
        if after.get(p) != "r55":
            continue
        check_grounded(dg, p, before.get(p), fail)
        check_clear(p, fail)
    if "forge" in parts:
        for n in F.YARD_GONE:
            if obj(n) is not None:
                fail.add("%s is still there" % n)
        for names, own in gone:
            left = [m for m in own if bpy.data.meshes.get(m) is not None]
            if left:
                fail.add("meshes of %s left: %s" % (names[0], left))
    moved = [n for n, m in still0.items() if obj(n) is not None and
             not np.allclose(np.array(obj(n).matrix_world), m, atol=STILL_TOL)]
    vanished = [n for n in still0 if obj(n) is None]
    log("still: %d other objects, %d moved, %d gone%s" % (len(still0), len(moved), len(vanished), (
        " (e.g. %s)" % (moved + vanished)[:6]) if moved or vanished else ""))
    if moved or vanished:
        fail.add("other objects changed: moved %s, gone %s" % (moved[:8], vanished[:8]))
    n_gone = sum(len(names) for names, _own in gone)
    n_obj1 = len(bpy.data.objects)
    log("objects %d -> %d (removed %d, rebuilt %d: %d gone for good)" % (n_obj0, n_obj1, len(removed), len(added),
                                                                          n_gone))
    if n_obj1 != n_obj0 - n_gone or len(removed) - len(added) != n_gone:
        fail.add("objects %d -> %d, want %d - %d" % (n_obj0, n_obj1, n_obj0, n_gone))
    left = [o.name for o in bpy.data.objects if o.name.startswith(SCRATCH)] + \
        [m.name for m in bpy.data.meshes if m.name.startswith(SCRATCH)] + \
        [c.name for c in bpy.data.collections if c.name.startswith(SCRATCH)]
    if left:
        fail.add("scratch data left: %s" % left[:8])
    scenes1 = sorted(s.name for s in bpy.data.scenes)
    if scenes1 != scenes0:
        fail.add("scenes %s -> %s" % (scenes0, scenes1))
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
    log("CACHES needs chunks,meta; bakefull %s,backdrop" % ",".join(todo))
    if dry:
        log("DRY_RUN: checks passed, not saving (%.1f s)" % (time.time() - t0))
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "(%.1f s)" % (time.time() - t0))


if __name__ == "__main__":
    main()
