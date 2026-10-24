"""Round 39, root fix 'rocks': every floating rock's tip merged into one vertex (world.tidy_rock, round 39), in an
existing out/sect_chase.blend, so it matches what a fresh build makes (world.build_islets, world._stepping_stones and
scenery.build_islands call tidy_rock on each rock they make). Run on the cloud box, on a copy first, AFTER
patch_r39_centre.py and BEFORE patch_r36_icefire.py:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r39_rocks.py [-- DRY_RUN=1]

Why (r36's diagnosis): round 12's tidy_rock moved the last four rings of every nature.floating_rock's cone onto one
point but never merged them (538 vertices and 480 zero-area faces on Ice-Fire Island). Blender's collapse decimation
cannot take such a tip below about 6 %: it threw the rock's top away instead. In the shipped backdrop 33 of the 43
rocks drawn in the area stand-ins had lost their tops (flat triangles, roots hanging in the air). r37's bake clean-up
(bake_web.degen_clean) works round it at bake time; this fixes the meshes.

What it does: world.tidy_rock on every rock (patch_r12_world.ROCK_RE: scenery.island*, world.islet*,
world.link.arena_mission.stone*): the stacked vertices become one tip vertex, the zero-area faces go, and the band over
them stays a fan of triangles round the tip, cut into strips in their own planes so the faces before the grassy top
keep their triangle count. Nothing moves: the surface is the same, and the plants (nature.scatter's Distribute Points
on Faces, which seeds each triangle by its index) stand exactly where they stood. Only the rock meshes change; no
object is added or removed.

Ice-Fire Island (scenery.island.009) is left alone: while it is round 7/12's island, patch_r36_icefire.py (run next)
replaces its mesh with one that already has a single tip vertex (its rehearsed digest needs the old rock as it is);
after that it is no floating rock any more.

State: each rock is 'old' (round 12's tip: the four rings stacked on the apex, not merged), 'r39' (merged: its mesh
carries rock_tip = 'merged') or, for island.009 only, 'icefire' (left alone). Anything else (a shared mesh, a rock
before round 12, a mesh that is no floating rock) stops the patch. Idempotent: on a patched file it prints 'PATCH
nothing changed: not saving' and the same DIGEST.

Checks (any failure stops the patch before saving; DRY_RUN=1 runs everything and never saves):
- tidy_rock's own: the faces from the grassy top on (the top and the spurs) keep their corners, order and materials
  exactly, and the faces before them their triangle count;
- each merged rock: no face under MIN_AREA, one vertex at the cone's tip (within TIP_TOL), no more open or
  non-manifold edges than before;
- the same surface: every vertex of the old mesh lies on the new one and every new vertex on the old one (SHAPE_TOL);
- the plants: every instance of every scatter that reads a rock (geometry nodes 'Surface') stands where it stood:
  the same objects, in the same order, with the same matrices (exactly);
- names and counts: objects and meshes the same, no scratch data left.
Prints 'PATCH CACHES needs audit' and 'PATCH DIGEST <md5>' of every rock mesh it owns (island.009 aside) and of the
plants' places.
"""
import collections
import hashlib
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
from sect.lib import nature as N  # noqa: E402

ROCK_RE = re.compile(r"^(scenery\.island|world\.islet|world\.link\.arena_mission\.stone)(\.\d{3})?$")
ICE = "scenery.island.009"     # scenery.ICEFIRE_ISLAND: patch_r36_icefire.py's
ICE_BUILD = "icefire_build"    # icefire_island.BUILD_PROP: set once round 36 rebuilt it
MIN_AREA = 1e-9                # m2
TIP_TOL = 1e-3                 # m
SHAPE_TOL = 1e-4               # m


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
            raise SystemExit("patch_r39_rocks: unknown option %r (DRY_RUN=1)" % a)
    return dry


class Fail(list):
    def add(self, msg):
        log("FAIL", msg)
        self.append(msg)


def arrays(me):
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    me.calc_loop_triangles()
    tv = np.empty(len(me.loop_triangles) * 3, np.int32)
    me.loop_triangles.foreach_get("vertices", tv)
    return co.reshape(-1, 3), tv.reshape(-1, 3)


def tip_of(me, lay, rings=W.ROCK_TIP_RINGS):
    """(the moved rings' vertex indices, the apex) as tidy_rock computes them."""
    idx = np.concatenate([lay["ring"](k) for k in range(lay["bands"] - rings + 1, lay["bands"] + 1)])
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    apex = np.concatenate([co[lay["ring"](lay["bands"] - rings)][:, :2].mean(0), [co[idx, 2].min()]])
    return idx, co, apex.astype(np.float32).astype(np.float64)


def rock_state(ob):
    me = ob.data
    if ob.name == ICE:
        return "icefire"
    if me.users != 1:
        return "shared mesh"
    if me.get(W.ROCK_TIP_PROP) == W.ROCK_TIP_MERGED:
        return "r39"
    lay = W.rock_rings(me)
    if lay is None:
        return "no floating rock"
    idx, co, apex = tip_of(me, lay)
    if (np.abs(co[idx] - apex).max(axis=1) > 0.0).any():
        return "before round 12"
    return "old"


def edge_counts(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    o = sum(1 for e in bm.edges if e.is_boundary)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return o, n


def readers(names):
    """Scatter objects whose geometry nodes read one of the rocks (an Object input), sorted."""
    out = set()
    for ob in bpy.data.objects:
        for mod in ob.modifiers:
            if mod.type != 'NODES' or mod.node_group is None:
                continue
            for it in mod.node_group.interface.items_tree:
                if getattr(it, "in_out", None) != 'INPUT' or getattr(it, "socket_type", "") != 'NodeSocketObject':
                    continue
                try:
                    v = N._get_mod_input(mod, it.identifier)
                except Exception:  # noqa: BLE001
                    continue
                if v is not None and v.name in names:
                    out.add(ob.name)
    return sorted(out)


def plants(scatters):
    """scatter -> [(instanced object, world matrix)] in depsgraph order."""
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    want = set(scatters)
    out = collections.defaultdict(list)
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent is not None and inst.parent.original.name in want:
            out[inst.parent.original.name].append((inst.object.original.name, np.array(inst.matrix_world, np.float64)))
    return out


def plants_sig(pl):
    h = hashlib.md5()
    for p in sorted(pl):
        h.update(p.encode())
        for nm, m in pl[p]:
            h.update(nm.encode())
            h.update(np.round(m, 5).tobytes())
    return h.hexdigest()


def mesh_sig(ob):
    me = ob.data
    h = hashlib.md5()
    h.update(("%s|%s|%s" % (ob.name, me.name, me.get(W.ROCK_TIP_PROP))).encode())
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    h.update(co.tobytes())
    for coll, attr, dt in ((me.loops, "vertex_index", np.int32), (me.polygons, "loop_total", np.int32),
                           (me.polygons, "material_index", np.int32)):
        a = np.empty(len(coll), dt)
        coll.foreach_get(attr, a)
        h.update(a.tobytes())
    v = me.attributes.get("nature_veg")
    if v is not None:
        a = np.empty(len(v.data), np.float32)
        v.data.foreach_get("value", a)
        h.update(a.tobytes())
    return h.hexdigest()


def digest(rocks, pl_sig):
    h = hashlib.md5()
    for ob in sorted(rocks, key=lambda o: o.name):
        h.update(mesh_sig(ob).encode())
    h.update(pl_sig.encode())
    return h.hexdigest()


def same_surface(V0, T0, V1, T1):
    """Largest distance from either mesh's vertices to the other's surface (m)."""
    worst = 0.0
    for Va, Vb, Tb in ((V0, V1, T1), (V1, V0, T0)):
        bvh = BVHTree.FromPolygons(Vb.tolist(), Tb.tolist(), all_triangles=True)
        for p in np.unique(Va, axis=0):
            d = bvh.find_nearest(Vector(tuple(p)))[3]
            worst = max(worst, d if d is not None else 1e9)
    return worst


def main():
    dry = options()
    t0 = time.time()
    fail = Fail()
    if bpy.data.objects.get("world.range") is None or bpy.data.objects.get(ICE) is None:
        log("NOT SAVED: no world.range or %s: is this out/sect_chase.blend?" % ICE)
        raise SystemExit(1)
    n_obj0, n_me0 = len(bpy.data.objects), len(bpy.data.meshes)
    rocks = sorted((o for o in bpy.data.objects if o.type == "MESH" and ROCK_RE.match(o.name)), key=lambda o: o.name)
    states = {o.name: rock_state(o) for o in rocks}
    cnt = collections.Counter(states.values())
    log("rocks %d: states %s (%.1f s)" % (len(rocks), dict(sorted(cnt.items())), time.time() - t0))
    bad = {n: s for n, s in states.items() if s not in ("old", "r39", "icefire")}
    if bad:
        log("NOT SAVED: rocks in a state this patch does not know: %s" % dict(list(bad.items())[:8]))
        raise SystemExit(1)
    ice_state = "round 36's island" if bpy.data.objects[ICE].get(ICE_BUILD) else "round 7/12's island"
    log("%s: left alone (%s; patch_r36_icefire.py gives it a single tip)" % (ICE, ice_state))
    own = [o for o in rocks if states[o.name] != "icefire"]
    todo = [o for o in own if states[o.name] == "old"]
    scat = readers({o.name for o in own})
    pl0 = plants(scat)
    log("plants: %d scatters read the rocks, %d instances" % (len(scat), sum(len(v) for v in pl0.values())))
    changed = []
    totals = collections.Counter()
    biggest = []
    for ob in todo:
        me = ob.data
        V0, T0 = arrays(me)
        e0 = edge_counts(me)
        lay = W.rock_rings(me)
        _idx, _co, apex = tip_of(me, lay)
        info = {}
        try:
            m = W.tidy_rock(ob, info=info)
        except RuntimeError as e:
            fail.add("%s: %s" % (ob.name, e))
            continue
        if m <= 0:
            fail.add("%s: tidy_rock changed nothing (%d)" % (ob.name, m))
            continue
        changed.append(ob.name)
        V1, T1 = arrays(me)
        a = np.empty(len(me.polygons))
        me.polygons.foreach_get("area", a)
        if (a < MIN_AREA).any():
            fail.add("%s: %d faces under %g m2" % (ob.name, int((a < MIN_AREA).sum()), MIN_AREA))
        at_tip = int((np.linalg.norm(V1.astype(np.float64) - apex, axis=1) <= TIP_TOL).sum())
        if at_tip != 1:
            fail.add("%s: %d vertices at the tip" % (ob.name, at_tip))
        e1 = edge_counts(me)
        if e1[0] > e0[0] or e1[1] > e0[1]:
            fail.add("%s: open / non-manifold edges %s -> %s" % (ob.name, e0, e1))
        d = same_surface(V0, T0, V1, T1)
        if d > SHAPE_TOL:
            fail.add("%s: the surface moved %.5f m" % (ob.name, d))
        totals["merged"] += info["merged"]
        totals["cuts"] += info["cuts"]
        totals["odd"] += info["odd"]
        totals["faces0"] += info["faces"][0]
        totals["faces1"] += info["faces"][1]
        totals["verts0"] += info["verts"][0]
        totals["verts1"] += info["verts"][1]
        totals["zero_area_gone"] += int((area_of(V0, T0) < MIN_AREA).sum())
        totals["shape_um"] = max(totals["shape_um"], int(round(d * 1e6)))
        biggest.append((info["merged"], ob.name, info))
    if todo:
        log("merged %d of %d rocks (%.1f s): %d stacked vertices into their tips, %d zero-area triangles gone, %d cuts "
            "on the fans' edges, %d fans with one triangle moved past the spurs; faces %d -> %d, vertices %d -> %d; "
            "surface moved at most %d um" % (
                len(changed), len(todo), time.time() - t0, totals["merged"], totals["zero_area_gone"], totals["cuts"],
                totals["odd"], totals["faces0"], totals["faces1"], totals["verts0"], totals["verts1"],
                totals["shape_um"]))
        for n_, nm, info in sorted(biggest, reverse=True)[:3]:
            log("  e.g. %s: %d segments round, %d vertices merged, %d cuts, faces %s, triangles before the top %d "
                "(kept)" % (nm, info["segs"], info["merged"], info["cuts"], info["faces"], info["tris_before_top"]))
    bpy.context.view_layer.update()
    pl1 = plants(scat)
    moved = []
    for p in sorted(set(pl0) | set(pl1)):
        a_, b_ = pl0.get(p, []), pl1.get(p, [])
        if [x[0] for x in a_] != [x[0] for x in b_] or \
                any(not np.array_equal(x[1], y[1]) for x, y in zip(a_, b_)):
            moved.append(p)
    log("plants: %d instances after, %d scatters with any instance moved or changed" % (
        sum(len(v) for v in pl1.values()), len(moved)))
    if moved:
        fail.add("plants moved on %s" % moved[:6])
    after = collections.Counter(rock_state(o) for o in rocks)
    log("after: states %s" % dict(sorted(after.items())))
    if after.get("old"):
        fail.add("%d rocks still old" % after["old"])
    n_obj1, n_me1 = len(bpy.data.objects), len(bpy.data.meshes)
    log("objects %d -> %d, meshes %d -> %d" % (n_obj0, n_obj1, n_me0, n_me1))
    if (n_obj1, n_me1) != (n_obj0, n_me0):
        fail.add("objects / meshes changed")
    log("changed: %d rock meshes" % len(changed))
    log("DIGEST", digest(own, plants_sig(pl1)))
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail[:20]:
            log("  -", f)
        raise SystemExit(1)
    if not changed:
        log("CACHES ok: nothing changed")
        log("nothing changed: not saving (%.1f s)" % (time.time() - t0))
        return
    log("CACHES needs audit: %d floating rocks' meshes (the tips merged; the surface and the plants as they were) - "
        "run export_web.py -- audit --profile full, then -- chunks,meta --profile full, then bake_web.py -- bakefull "
        "--profile full for every chunk and the backdrop (the rocks are in all of them and in the stand-ins), then "
        "pack; no trees bake (no plant moved), no water" % len(changed))
    if dry:
        log("DRY_RUN: checks passed, not saving (%.1f s)" % (time.time() - t0))
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "(%.1f s)" % (time.time() - t0))


def area_of(V, T):
    P = V[T].astype(np.float64)
    return 0.5 * np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1)


if __name__ == "__main__":
    main()
