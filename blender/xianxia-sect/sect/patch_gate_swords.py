"""Turn the gate's two stone sword monoliths in out/sect_chase.blend into the Heaven Sword 倚天剑 (west) and the
Dragon Saber 屠龙刀 (east) of sect/areas/gate.py (WEAPONS) and save the .blend. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_gate_swords.py

In place: 'gate.sword_monolith' gets the Heaven Sword's mesh ('gate.heaven_sword'), 'gate.sword_monolith.001' the
Dragon Saber's ('gate.dragon_saber'), each with its material slots (gate.WEAPONS materials). Same objects, names,
parent and location; the rotation is gate.weapon_transform's (fronts turned toward the axis with
gate.WEAPON_FACE_IN). No object is added or removed. The old shared mesh 'gate.sword_monolith' is freed.

Why nothing else re-runs: export_web keys every cache on the record key (the object name) and boxes the pieces by
their bound box; both weapons keep their name and the old monolith's local box (x, y -2.7..2.7, z 0..15.6; a square
box turned 12 deg either way gives the same world box). So vis_cache.npz, chunks.npz / chunks.json and the
'gate-swords' hotspot box in meta.json stay valid; the script checks the world boxes and prints 'PATCH CACHES ok'
(or 'PATCH CACHES STALE' with what changed). Then re-bake the gate chunk:

    python .../tools/rblender.py --background .../out/sect_chase.blend \
        --python .../sect/bake_web.py -- bakefull --profile full --chunks gate

Idempotent: every run builds both meshes fresh (gate.weapon_mesh(fresh=True)), swaps them in and frees the previous
ones, so a second run leaves the same objects, names and geometry. The glyph meshes props._text_mesh caches have no
users (not saved); its private evaluation scene is removed again when this run created it.
"""
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import gate as G  # noqa: E402
from sect.lib import props as P  # noqa: E402

OLD_SHARED = "gate.sword_monolith"     # the stone monoliths' shared mesh
ROOT_EMPTY = "gate.root"


def log(*a):
    print("PATCH", *a, flush=True)


def world_box(ob):
    M = ob.matrix_world
    pts = [M @ Vector(c) for c in ob.bound_box]
    return (tuple(round(min(p[k] for p in pts), 3) for k in range(3)),
            tuple(round(max(p[k] for p in pts), 3) for k in range(3)))


def local_box(me):
    if not len(me.vertices):
        return None
    cs = [v.co for v in me.vertices]
    return (tuple(round(min(c[k] for c in cs), 4) for k in range(3)),
            tuple(round(max(c[k] for c in cs), 4) for k in range(3)))


def tris(me):
    n = len(me.polygons)
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def main():
    targets = []
    for spec in G.WEAPONS:
        ob = bpy.data.objects.get(spec["object"])
        if ob is None or ob.type != 'MESH':
            raise RuntimeError("%s not found (or not a mesh); is this out/sect_chase.blend?" % spec["object"])
        targets.append((spec, ob))
    root = bpy.data.objects.get(ROOT_EMPTY)
    n_obj = len(bpy.data.objects)
    had_eval = bpy.data.scenes.get(P._EVAL_SCENE) is not None
    want_local = ((-G.WEAPON_HALF, -G.WEAPON_HALF, 0.0), (G.WEAPON_HALF, G.WEAPON_HALF, G.WEAPON_TOP))
    before = {}
    for spec, ob in targets:
        before[ob.name] = world_box(ob)
        log("before", ob.name, "mesh", ob.data.name, "users", ob.data.users, "tris", tris(ob.data),
            "world box", before[ob.name], "children", len(ob.children), "modifiers", [m.name for m in ob.modifiers])
        if ob.parent != root:
            log("WARN", ob.name, "parent is", ob.parent.name if ob.parent else None, "not", ROOT_EMPTY)
        if ob.modifiers:
            log("WARN", ob.name, "has modifiers; they now act on the new mesh:", [m.type for m in ob.modifiers])
    for spec, ob in targets:
        old = ob.data
        me = G.weapon_mesh(spec, fresh=True, log=log)
        ob.data = me
        for s in ob.material_slots:
            if s.link != 'DATA':
                s.link = 'DATA'
        loc, rot = G.weapon_transform(spec)
        if (Vector(loc) - ob.location).length > 1e-3:
            log("WARN", ob.name, "location", tuple(ob.location), "differs from gate.py's", loc, "- kept the file's")
        ob.rotation_mode = 'XYZ'
        ob.rotation_euler = rot
        if old is not me and old.users == 0:
            bpy.data.meshes.remove(old)
        log(spec["key"], "->", ob.name, "mesh", me.name, "tris", tris(me), "skipped faces",
            me.get("gate_weapon_skipped_faces"), "slots",
            [s.material.name if s.material else None for s in ob.material_slots], "yaw %.1f deg" % (rot[2] * 57.2958))
    for m in list(bpy.data.meshes):
        stale = m.name == OLD_SHARED or any(m.name.startswith(G.K + "." + s["key"] + ".old") for s in G.WEAPONS)
        if stale and m.users == 0:
            log("freed mesh", m.name)
            bpy.data.meshes.remove(m)
    if not had_eval:
        sc = bpy.data.scenes.get(P._EVAL_SCENE)
        if sc is not None and sc != bpy.context.scene:
            bpy.data.scenes.remove(sc)
            log("removed the glyph evaluation scene", P._EVAL_SCENE)
    bpy.context.view_layer.update()
    # checks: names, object count, local boxes, budget, world boxes (the web caches)
    if len(bpy.data.objects) != n_obj:
        raise RuntimeError("object count changed: %d -> %d" % (n_obj, len(bpy.data.objects)))
    stale = []
    for spec, ob in targets:
        lb = local_box(ob.data)
        if lb is None or any(abs(a - b) > 1e-3 for x, y in zip(lb, want_local) for a, b in zip(x, y)):
            raise RuntimeError("%s local box %s != %s" % (ob.name, lb, want_local))
        t = tris(ob.data)
        if t > G.WEAPON_TRI_BUDGET:
            raise RuntimeError("%s has %d triangles > %d" % (ob.name, t, G.WEAPON_TRI_BUDGET))
        after = world_box(ob)
        if any(abs(a - b) > 2e-3 for x, y in zip(after, before[ob.name]) for a, b in zip(x, y)):
            stale.append((ob.name, before[ob.name], after))
        log("after", ob.name, "mesh", ob.data.name, "tris", t, "local box", lb, "world box", after)
    if stale:
        log("CACHES STALE: world boxes changed", stale, "- run export_web.py -- chunks,meta --profile full before the bake")
    else:
        log("CACHES ok: names and world boxes unchanged; vis_cache, chunks and the gate-swords hotspot stay valid")
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects))


main()
