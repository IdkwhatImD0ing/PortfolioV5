"""Put the Golden Wheel Lama's five wheels (金轮法王 金银铜铁铅五轮, sect/areas/forge.py _five_wheels) in out/sect_chase.blend
in place of the weapon rack forge.weapon_rack.001, and save the .blend. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_five_wheels.py

What it does:
- deletes the collection instance forge.weapon_rack.001 (the one rack readable at the forge hold) and its prototype
  collection (props.rack.2p6.1.v4, seed-unique) when nothing else instances it;
- adds, in the 'forge' collection under forge.root: the Empty forge.five_wheels at the rack's place (forge.FW_LOC,
  turned forge.FW_ROT_Z) and its six meshes forge.five_wheels.stand / .gold / .silver / .copper / .iron / .lead;
- checks every new mesh: closed (every edge shared by two faces, bake_web's rule), consistently wound, at most
  forge.FW_TRI_CAP triangles, existing materials only, nothing ember or molten (the page's forge fire FX centres on
  the '.glow.ember' meshes); then saves.
Racks .000/.002/.003 keep their names (forge.py now numbers them explicitly), so their cache rows stay valid.

These are NEW object names: the web caches (vis_cache.npz, chunks.npz) do not know them, so before the forge bake run
export_web.py -- audit, then -- chunks,meta (or a cache_add step for just these names), see the report.

Idempotent: a second run finds no rack (logs it), deletes its own previous forge.five_wheels hierarchy and meshes,
and builds them again with the same names.
"""
import os
import sys

import bmesh
import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import forge as F  # noqa: E402
from sect.lib import materials as M  # noqa: E402
from sect.lib import util as U  # noqa: E402

OLD_RACK = "forge.weapon_rack.001"
ROOT_EMPTY = "forge.root"
COLL = "forge"
BANNED = ("ember", "molten")


def log(*a):
    print("PATCH", *a, flush=True)


def tris(me):
    n = len(me.polygons)
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def world_box(ob):
    M = ob.matrix_world
    pts = [M @ Vector(c) for c in ob.bound_box]
    return (tuple(round(min(p[k] for p in pts), 3) for k in range(3)),
            tuple(round(max(p[k] for p in pts), 3) for k in range(3)))


def mesh_checks(ob):
    """(open edges, non-contiguous edges) of the object's mesh: both must be 0."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    open_e = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    bad = sum(1 for e in bm.edges if len(e.link_faces) == 2 and not e.is_contiguous)
    bm.free()
    return open_e, bad


def ours(ob):
    return ob.name == F.FW_NAME or ob.name.startswith(F.FW_NAME + ".")


def main():
    root = bpy.data.objects.get(ROOT_EMPTY)
    if root is None:
        raise RuntimeError("%s not found; is this out/sect_chase.blend?" % ROOT_EMPTY)
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        raise RuntimeError("collection %r not found" % COLL)
    n0 = len(bpy.data.objects)
    loc = F.FW_LOC
    # 1. this patch's previous output
    prev = [o for o in bpy.data.objects if ours(o)]
    if prev:
        names = sorted(o.name for o in prev)
        tops = [o.name for o in prev if o.parent is None or not ours(o.parent)]
        for nm in tops:
            ob = bpy.data.objects.get(nm)
            if ob is not None:
                U.delete_hierarchy(ob)
        for nm in names:                     # anything left (a child moved elsewhere)
            ob = bpy.data.objects.get(nm)
            if ob is not None:
                bpy.data.objects.remove(ob, do_unlink=True)
        log("removed the previous run's", len(names), "objects", names)
    for m in list(bpy.data.meshes):
        if (m.name == F.FW_NAME or m.name.startswith(F.FW_NAME + ".")) and m.users == 0:
            bpy.data.meshes.remove(m)
    # 2. the old rack and its prototype collection
    rack = bpy.data.objects.get(OLD_RACK)
    removed = []
    if rack is None:
        log(OLD_RACK, "not found (already replaced); building at forge.FW_LOC", loc)
    else:
        proto = rack.instance_collection if rack.instance_type == 'COLLECTION' else None
        log("old", rack.name, "type", rack.type, "instance", proto.name if proto else None, "parent",
            rack.parent.name if rack.parent else None, "location", tuple(round(c, 3) for c in rack.location),
            "rot z %.3f" % rack.rotation_euler[2], "collections", [c.name for c in rack.users_collection],
            "children", len(rack.children), "world box", world_box(rack))
        if rack.parent != root:
            log("WARN", rack.name, "parent is not", ROOT_EMPTY)
        if (Vector((loc[0], loc[1], 0.0)) - rack.location).length > 1e-3:
            log("WARN", rack.name, "location", tuple(rack.location), "differs from forge.FW_LOC", loc,
                "- building at the rack's")
            loc = (rack.location[0], rack.location[1])
        if rack.users_collection and coll not in rack.users_collection:
            log("WARN", rack.name, "is not in", COLL, "- the wheels go to", COLL, "anyway")
        removed.append(rack.name)
        U.delete_hierarchy(rack)
        if proto is not None:
            users = [o.name for o in bpy.data.objects if o.instance_type == 'COLLECTION' and o.instance_collection == proto]
            if users:
                log("kept prototype", proto.name, "still instanced by", users[:5])
            else:
                pobs = list(proto.all_objects)
                datas = {o.data for o in pobs if o.data is not None}
                for o in pobs:
                    removed.append(o.name)
                    bpy.data.objects.remove(o, do_unlink=True)
                for d in datas:
                    if isinstance(d, bpy.types.Mesh) and d.users == 0:
                        bpy.data.meshes.remove(d)
                pname = proto.name
                bpy.data.collections.remove(proto)
                log("removed prototype collection", pname, "and its", len(pobs), "objects")
    # 3. build
    emp = F._five_wheels(coll, root, loc[0], loc[1])
    # the wheel metals forge.py registers itself (forge_lead, forge_copper): materials.get reuses a material that is
    # already in the .blend as it is, so rebuild them in place and a re-run picks up colour edits
    for nm in sorted({m for _, m, _ in F.FW_WHEELS if m.startswith("forge_")}):
        M.rebuild(nm)
        log("material", nm, "rebuilt")
    bpy.context.view_layer.update()
    added = [emp] + sorted(emp.children, key=lambda o: o.name)
    total = 0
    for ob in added:
        if ob.type != 'MESH':
            log("added", ob.name, "Empty, parent", ob.parent.name, "location", tuple(round(c, 3) for c in ob.location),
                "rot z %.3f" % ob.rotation_euler[2], "world", tuple(round(c, 2) for c in ob.matrix_world.translation))
            continue
        t = tris(ob.data)
        total += t
        mats = [s.material.name if s.material else None for s in ob.material_slots]
        open_e, bad = mesh_checks(ob)
        log("added", ob.name, "tris", t, "verts", len(ob.data.vertices), "materials", mats, "open edges", open_e,
            "flipped edges", bad, "world box", world_box(ob))
        if open_e or bad:
            raise RuntimeError("%s is not closed / consistently wound (%d open, %d flipped)" % (ob.name, open_e, bad))
        if t > F.FW_TRI_CAP:
            raise RuntimeError("%s has %d triangles > %d" % (ob.name, t, F.FW_TRI_CAP))
        for m in mats:
            if m is None or any(b in m for b in BANNED):
                raise RuntimeError("%s uses material %r" % (ob.name, m))
        if [c.name for c in ob.users_collection] != [COLL]:
            raise RuntimeError("%s collections %s" % (ob.name, [c.name for c in ob.users_collection]))
    n1 = len(bpy.data.objects)
    log("SUMMARY removed", len(removed), "objects", removed[:3] + (["..."] if len(removed) > 3 else []),
        "| added", len(added), "objects", [o.name for o in added], "| tris", total,
        "| objects %d -> %d" % (n0, n1))
    log("NEW NAMES: the web caches do not know them; run export_web audit + chunks,meta (or cache_add) before the "
        "forge bake")
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


main()
