"""Add the Divine Condor 神雕 of sect/areas/summit.py (divine_condor, step 6b of build) to out/sect_chase.blend and save
it. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_divine_condor.py [-- --style statue]

Adds six NEW objects to the 'summit' collection (logged as 'PATCH add ...'):
    summit.condor_rock        nature boulder (shared mesh nature.boulder.v4), child of summit.root
    summit.condor             Empty on the rock top, child of summit.root (beak toward the moon)
    summit.condor.body        metaball body              props_feather_black
    summit.condor.feathers    ~220 closed feather slabs  props_feather_black, props_cover_ochre
    summit.condor.head        bald neck, skull, hooked beak, blood-red lump
                              props_cover_brown, props_crane_crown, props_horn, props_feather_black
    summit.condor.legs        scaly legs, toes, talons   props_leg, props_horn
Nothing existing is moved, renamed or changed. Existing materials only (the run fails if a new one appears).
--style statue builds the fallback (weathered stone_grey statue, red lump kept).

Idempotent: a re-run first removes its own previous output (objects tagged sect_item = divine_condor, or named
summit.condor*, and their unshared meshes), then builds again from the same seeds, so the names, the object count
and the geometry come out the same.

New names are not in the web caches, so before the bake run (see build_divine_condor.md):
    export_web.py -- audit --profile full      (or a cache_add for these owners), then -- chunks,meta --profile full
    bake_web.py -- bakefull --profile full --chunks summit,backdrop
The bake log must show no 'WARN cache misses' / 'WARN chunk misses'.
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import summit as S  # noqa: E402
from sect.lib import props as P  # noqa: E402

ROOT_EMPTY = "summit.root"
COLL = "summit"
HOLD_FRAME = 1647
CAMERA = "chase.cam"


def log(*a):
    print("PATCH", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default=S.CONDOR_STYLE, choices=sorted(S.CONDOR_MATS))
    ap.add_argument("--dry", action="store_true", help="build and check, do not save")
    a, _rest = ap.parse_known_args(argv)
    return a


def ours(ob):
    n = ob.name
    return (ob.get(S.CONDOR_TAG) == S.CONDOR_ITEM or n == "summit.condor" or n.startswith("summit.condor.")
            or n.startswith("summit.condor_rock"))


def remove_previous():
    obs = [o for o in bpy.data.objects if ours(o)]
    meshes = set()
    for o in obs:
        if o.type == 'MESH' and o.data is not None and o.data.get("sect_shared") is None:
            meshes.add(o.data.name)
        log("remove previous", o.name, o.type)
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        if (m.name in meshes or m.name.startswith("summit.condor")) and m.users == 0:
            bpy.data.meshes.remove(m)
    return len(obs)


def tris(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def mesh_checks(me):
    """(boundary edges, non-manifold edges, sliver faces by bake_web.clean_mesh's rule)."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    nonman = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    sliver = 0
    for f in bm.faces:
        per = sum(e.calc_length() for e in f.edges)
        a = f.calc_area()
        if a < 1e-4 * per * per or a < 1e-8:
            sliver += 1
    bm.free()
    return boundary, nonman, sliver


def world_box(ob):
    M = ob.matrix_world
    pts = [M @ Vector(c) for c in ob.bound_box]
    return (tuple(round(min(p[k] for p in pts), 2) for k in range(3)),
            tuple(round(max(p[k] for p in pts), 2) for k in range(3)))


def main():
    a = args()
    root = bpy.data.objects.get(ROOT_EMPTY)
    coll = bpy.data.collections.get(COLL)
    if root is None or coll is None:
        raise RuntimeError("%s / collection %s not found; is this out/sect_chase.blend?" % (ROOT_EMPTY, COLL))
    had_eval = bpy.data.scenes.get(P._EVAL_SCENE) is not None
    removed = remove_previous()
    n_obj = len(bpy.data.objects)
    n_mat = len(bpy.data.materials)
    emp = S.divine_condor(coll, root, style=a.style, log=lambda *x: log("condor", *x))
    if not had_eval:
        sc = bpy.data.scenes.get(P._EVAL_SCENE)
        if sc is not None and sc != bpy.context.scene:
            bpy.data.scenes.remove(sc)
            log("removed the metaball evaluation scene", P._EVAL_SCENE)
    bpy.context.view_layer.update()
    new = [o for o in bpy.data.objects if ours(o)]
    added = len(bpy.data.objects) - n_obj
    if added != 6 or len(new) != 6:
        raise RuntimeError("expected 6 new objects, got %d (%s)" % (added, [o.name for o in new]))
    if len(bpy.data.materials) != n_mat:
        raise RuntimeError("new materials appeared: %d -> %d" % (n_mat, len(bpy.data.materials)))
    total = 0
    for o in sorted(new, key=lambda o: o.name):
        if o.type == 'MESH':
            t = tris(o.data)
            total += t
            b, nm, sl = mesh_checks(o.data)
            slots = [s.material.name if s.material else None for s in o.material_slots]
            log("add", o.name, "mesh", o.data.name, "tris", t, "boundary edges", b, "non-manifold", nm, "slivers", sl,
                "slots", slots, "parent", o.parent.name if o.parent else None, "world box", world_box(o))
            if None in slots:
                raise RuntimeError("%s has an empty material slot" % o.name)
            if t > S.CONDOR_TRI_CAP and o.name != "summit.condor_rock":
                raise RuntimeError("%s has %d triangles > %d" % (o.name, t, S.CONDOR_TRI_CAP))
            if b:
                log("WARN", o.name, "is open (%d boundary edges): look-around views may bake its back faces dark" % b)
        else:
            log("add", o.name, o.type, "parent", o.parent.name if o.parent else None, "location",
                tuple(round(x, 3) for x in o.location), "rotation z %.1f deg" % math.degrees(o.rotation_euler.z))
    # distance from the contact hold's camera (full detail for <= 8k-triangle pieces of the area within 95 m)
    sc = bpy.context.scene
    cam = bpy.data.objects.get(CAMERA)
    if cam is not None:
        f0 = sc.frame_current
        sc.frame_set(HOLD_FRAME)
        c = emp.matrix_world @ Vector((0.0, 0.0, 2.4))
        log("hold %d camera distance to the condor %.1f m" % (HOLD_FRAME, (c - cam.matrix_world.translation).length))
        sc.frame_set(f0)
    log("removed", removed, "previous objects; added 6 objects:", sorted(o.name for o in new), "triangles", total,
        "objects now", len(bpy.data.objects))
    if a.dry:
        log("dry run: not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


main()
