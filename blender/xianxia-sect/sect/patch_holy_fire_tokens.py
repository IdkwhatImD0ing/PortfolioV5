"""Turn the scroll area's floating jade-slip stack in out/sect_chase.blend into the six Holy Fire Tokens 圣火令 of
sect/areas/scroll.py (TOKENS, fire_token_meshes) and save the .blend. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_holy_fire_tokens.py

In place: 'scroll.slips' gets the tokens' body mesh (iron body, molten fire windows and seams, rune_gold cores),
'scroll.slip_caps' the etched gold inlay (borders, dotted lines, arabesques) and the rune_gold cores. Same objects,
names, parent (the Empty
'scroll.slip_stack', untouched) and transforms; no object is added or removed. The old meshes are freed and the new
ones take their names. The object property 'glow' (it scales the emission of every material on its object) is set to
scroll.TOKEN_GLOW on scroll.slips (the jade slips' 1.6 washes the molten windows out to pink-white) and to
scroll.CORE_GLOW on scroll.slip_caps (the white-gold cores, brighter than the fire round them; gold ignores it). The
bake reads both live, so no cache depends on them.

Why nothing else re-runs: export_web keys every cache on the object name and boxes the pieces by their bound box. Both
objects keep their name, and each new local box sits inside the old one (checked here against the live meshes and
against the jade-slip boxes the caches were built with), so vis_cache.npz, chunks.npz / chunks.json and meta.json stay
valid: the script prints 'PATCH CACHES ok'. If it prints 'PATCH CACHES STALE' instead, run
'export_web.py -- chunks,meta --profile full' before the bake. Then re-bake the scroll chunk (and the backdrop: the
stack is 3.4 m across):

    python .../tools/rblender.py --background .../out/sect_chase.blend \
        --python .../sect/bake_web.py -- bakefull --profile full --chunks scroll,backdrop

Idempotent: every run builds both meshes fresh, swaps them in and frees the previous ones, so a second run leaves the
same objects, names and geometry. Refuses to save (and exits non-zero with --python-exit-code 1) when an object is
missing, a mesh is over scroll.TOKEN_TRI_BUDGET or the object count changes.
"""
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import scroll as SC  # noqa: E402

STACK = SC.K + ".slip_stack"
TARGETS = (SC.K + ".slips", SC.K + ".slip_caps")      # body, gold: the order of SC.fire_token_meshes()
# local boxes (slip_stack frame) of the jade-slip stack the export caches were built with (scroll.py before the tokens)
JADE_BOXES = {
    SC.K + ".slips": ((-1.913, -1.004, -0.223), (1.913, 1.004, 1.823)),
    SC.K + ".slip_caps": ((-1.904, -1.029, -0.259), (1.904, 1.029, 1.859)),
}


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


def inside(box, outer, tol=1e-3):
    return all(box[0][k] >= outer[0][k] - tol and box[1][k] <= outer[1][k] + tol for k in range(3))


def tris(me):
    n = len(me.polygons)
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def main():
    stack = bpy.data.objects.get(STACK)
    if stack is None:
        raise RuntimeError("%s not found; is this out/sect_chase.blend?" % STACK)
    obs = []
    for nm in TARGETS:
        ob = bpy.data.objects.get(nm)
        if ob is None or ob.type != 'MESH':
            raise RuntimeError("%s not found (or not a mesh); is this out/sect_chase.blend?" % nm)
        if ob.parent != stack:
            log("WARN", nm, "parent is", ob.parent.name if ob.parent else None, "not", STACK)
        if ob.modifiers:
            log("WARN", nm, "has modifiers; they now act on the new mesh:", [m.type for m in ob.modifiers])
        obs.append(ob)
    n_obj = len(bpy.data.objects)
    log("stack", STACK, "location", tuple(round(c, 3) for c in stack.location),
        "rotation z %.1f deg" % (stack.rotation_euler.z * 57.29578))
    before_local, before_world = {}, {}
    for ob in obs:
        before_local[ob.name] = local_box(ob.data)
        before_world[ob.name] = world_box(ob)
        log("before", ob.name, "mesh", ob.data.name, "users", ob.data.users, "tris", tris(ob.data), "slots",
            [s.material.name if s.material else None for s in ob.material_slots], "local box", before_local[ob.name],
            "world box", before_world[ob.name], "glow", ob.get("glow"))
    news = SC.fire_token_meshes(names=tuple(nm + ".new" for nm in TARGETS), log=log)
    for ob, me in zip(obs, news):
        old = ob.data
        ob.data = me
        for s in ob.material_slots:
            if s.link != 'DATA':
                s.link = 'DATA'
        if old is not me and old.users == 0:
            log("freed mesh", old.name)
            bpy.data.meshes.remove(old)
        elif old is not me:
            log("WARN old mesh", old.name, "still has", old.users, "users; kept")
        me.name = ob.name
        if me.name != ob.name:
            log("WARN mesh name taken: the new mesh is", me.name)
    for ob, glow in zip(obs, (SC.TOKEN_GLOW, SC.CORE_GLOW)):
        if ob.get("glow") != glow:
            log("glow on", ob.name, ob.get("glow"), "->", glow)
            ob["glow"] = glow
    bpy.context.view_layer.update()
    # checks: object count, budget, boxes (the web caches)
    if len(bpy.data.objects) != n_obj:
        raise RuntimeError("object count changed: %d -> %d" % (n_obj, len(bpy.data.objects)))
    stale = []
    for ob in obs:
        t = tris(ob.data)
        if t > SC.TOKEN_TRI_BUDGET:
            raise RuntimeError("%s has %d triangles > %d" % (ob.name, t, SC.TOKEN_TRI_BUDGET))
        lb = local_box(ob.data)
        wb = world_box(ob)
        ok_live = inside(lb, before_local[ob.name])
        ok_jade = inside(lb, JADE_BOXES[ob.name])
        if not (ok_live and ok_jade):
            stale.append((ob.name, lb, before_local[ob.name], JADE_BOXES[ob.name]))
        log("after", ob.name, "mesh", ob.data.name, "tris", t, "slots",
            [s.material.name if s.material else None for s in ob.material_slots], "local box", lb,
            "inside the old box", ok_live, "inside the jade-slip box", ok_jade, "world box", wb)
    if stale:
        log("CACHES STALE: a new box reaches outside the old one", stale,
            "- run export_web.py -- chunks,meta --profile full before the bake")
    else:
        log("CACHES ok: names unchanged and every new box inside the old one; vis_cache, chunks and meta stay valid")
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects))


main()
