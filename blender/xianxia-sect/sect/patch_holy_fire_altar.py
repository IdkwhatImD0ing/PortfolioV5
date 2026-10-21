"""Add the Ming Sect's holy-fire altars 圣火坛 (sect/areas/mission.py HOLY_FIRE, _holy_fire) to the mission plaza in
out/sect_chase.blend and save the .blend. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_holy_fire_altar.py

Adds (nothing existing is replaced or renamed; mission.censer and the rest of the plaza are left alone), all in the
'mission' collection under mission.root:
    mission.holy_fire          Empty at local (25, -27, 0), east, in the 619 hold
    mission.holy_fire.001      Empty at local (-25, -27, 0), west (behind the wall at the hold; plaza symmetry)
    <empty>.plinth .altar .relief .coals .flame   five meshes per altar (stone_grey, bronze, gold, molten + iron,
                               props_flame), children of their Empty
    mission.holy_fire_light / mission.holy_fire_light.001   POINT 1800 W lights 4 m over each bowl
= 14 new objects. The script logs every name, its triangles and world position.

Idempotent: a re-run first removes its own previous output (the objects named mission.holy_fire*, their mesh and
light data) and builds both altars again, so the names and the object count come out the same.

These are new names, so the web caches do not know them yet: run export_web.py -- audit and -- chunks,meta (or the
proposed cache_add.py) before bakefull, or the bake drops them ('WARN cache misses'). See the run report.
"""
import os
import sys

import bpy
import bmesh
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import mission as M  # noqa: E402

PREFIX = M.K + ".holy_fire"              # Empties and their parts
LIGHT = M.K + ".holy_fire_light"         # the lights
COLL = M.K
ROOT_EMPTY = M.K + ".root"
PAIR_BUDGET = 12000


def log(*a):
    print("PATCH", *a, flush=True)


def ours(name):
    return name == PREFIX or name.startswith(PREFIX + ".") or name == LIGHT or name.startswith(LIGHT + ".")


def tris(me):
    n = len(me.polygons)
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def closed_and_out(me):
    """(boundary edges, faces bake_web.fix_normals would flip): both 0 for a closed, outward mesh."""
    bm = bmesh.new()
    bm.from_mesh(me)
    nb = sum(1 for e in bm.edges if e.is_boundary)
    before = [f.normal.copy() for f in bm.faces]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    flips = sum(1 for f, n in zip(bm.faces, before) if f.normal.dot(n) < 0.0)
    bm.free()
    return nb, flips


def remove_previous():
    obs = [o for o in bpy.data.objects if ours(o.name)]
    datas = [o.data for o in obs if o.data is not None]
    if obs:
        log("removing the previous run's", len(obs), "objects:", sorted(o.name for o in obs))
    for o in obs:
        bpy.data.objects.remove(o, do_unlink=True)
    for d in datas:
        if d.users == 0:
            (bpy.data.lights if isinstance(d, bpy.types.Light) else bpy.data.meshes).remove(d)
    for pool in (bpy.data.meshes, bpy.data.lights):
        for d in list(pool):
            if ours(d.name) and d.users == 0:
                log("freed orphan", d.name)
                pool.remove(d)
    return len(obs)


def main():
    coll = bpy.data.collections.get(COLL)
    root = bpy.data.objects.get(ROOT_EMPTY)
    if coll is None or root is None:
        raise RuntimeError("collection %r / %r not found; is this out/sect_chase.blend?" % (COLL, ROOT_EMPTY))
    censer = bpy.data.objects.get(M.K + ".censer")
    censer_mx = censer.matrix_world.copy() if censer else None
    removed = remove_previous()
    n0 = len(bpy.data.objects)
    log("objects before", n0 + removed, "after removing our own", n0)
    for x, y in M.HOLY_FIRE:
        hf = M._holy_fire(coll, root, x, y)
        log("built", hf.name, "at local", (x, y))
    bpy.context.view_layer.update()
    new = sorted((o for o in bpy.data.objects if ours(o.name)), key=lambda o: o.name)
    added = len(bpy.data.objects) - n0
    want = len(M.HOLY_FIRE) * (2 + len(M.HF_PARTS))
    if added != want or len(new) != want:
        raise RuntimeError("expected %d new objects, got %d (%d named %s*)" % (want, added, len(new), PREFIX))
    pair = 0
    for o in new:
        if [c.name for c in o.users_collection] != [COLL]:
            raise RuntimeError("%s is in %s, not only %r" % (o.name, [c.name for c in o.users_collection], COLL))
        loc = tuple(round(c, 2) for c in o.matrix_world.translation)
        if o.type == 'MESH':
            t = tris(o.data)
            pair += t
            nb, flips = closed_and_out(o.data)
            if t > M.HF_TRI_BUDGET:
                raise RuntimeError("%s has %d triangles > %d" % (o.name, t, M.HF_TRI_BUDGET))
            if nb or flips:
                raise RuntimeError("%s is not closed / outward: %d boundary edges, %d faces flip" % (o.name, nb, flips))
            M_ = o.matrix_world
            zs = [(M_ @ Vector(c)).z for c in o.bound_box]
            log("added", o.name, "mesh", o.data.name, "tris", t, "slots",
                [s.material.name if s.material else None for s in o.material_slots],
                "glow", o.get("glow"), "shadow", o.visible_shadow, "edge attr", M.U.EDGE_ATTR in o.data.attributes,
                "world z %.2f..%.2f" % (min(zs), max(zs)), "parent", o.parent.name)
        elif o.type == 'LIGHT':
            log("added", o.name, "light", o.data.type, o.data.energy, "W colour", tuple(round(c, 3) for c in o.data.color),
                "soft", round(o.data.shadow_soft_size, 3), "shadow", o.data.use_shadow, "world", loc,
                "parent", o.parent.name)
        else:
            log("added", o.name, o.type, "world", loc, "parent", o.parent.name if o.parent else None)
    if pair > PAIR_BUDGET:
        raise RuntimeError("the pair has %d triangles > %d" % (pair, PAIR_BUDGET))
    if censer is not None and censer.matrix_world != censer_mx:
        raise RuntimeError("mission.censer moved")
    log("pair triangles", pair, "(budget %d)" % PAIR_BUDGET)
    log("ADDED %d objects (%d Empties, %d meshes, %d lights); nothing existing replaced or renamed" %
        (added, sum(o.type == 'EMPTY' for o in new), sum(o.type == 'MESH' for o in new),
         sum(o.type == 'LIGHT' for o in new)))
    log("NEW NAMES: the web caches do not know them yet: export_web audit + chunks,meta (or cache_add) before bakefull")
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects))


main()
