"""Re-letter the gate plaque in out/sect_chase.blend with gate.AREA['title_zh'] (明教, the Ming Sect) and save.
Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_gate_plaque.py

In place: a fresh plaque is built with props.plaque (same text, width from gate.plaque_width so the board keeps the
height the paifang's plaque zone was designed for) into a temporary collection, and its board, frame, relief and
text meshes replace the meshes of the existing 'gate.plaque.board/.frame/.relief/.text' objects. Same objects,
names, parents and transforms; no object is added or removed (the temporary ones are deleted again).

Why nothing else re-runs: export_web keys its caches on object names and boxes pieces by their bound box. The new
board is narrower than the old 3-character one and no taller, so every world box shrinks or stays the same (the
script checks and prints 'PATCH CACHES ok', or 'PATCH CACHES GREW' if a box got bigger). Then re-bake the gate.

Idempotent: every run rebuilds all four meshes from scratch and frees the replaced ones.
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
from sect.lib import util as U  # noqa: E402

PLAQUE = "gate.plaque"
PAIFANG = "gate.paifang"
PARTS = ("board", "frame", "relief", "text")
TMP = "_tmp_plaque"


def log(*a):
    print("PATCH", *a, flush=True)


def world_box(ob):
    M = ob.matrix_world
    pts = [M @ Vector(c) for c in ob.bound_box]
    return (tuple(min(p[k] for p in pts) for k in range(3)), tuple(max(p[k] for p in pts) for k in range(3)))


def parts_of(root):
    pivot = next((c for c in root.children if c.name.startswith(root.name + ".pivot")), None)
    if pivot is None:
        raise RuntimeError("%s has no pivot child; children %s" % (root.name, [c.name for c in root.children]))
    found = {}
    for k in PARTS:
        ob = next((c for c in pivot.children if c.name.startswith(root.name + "." + k)), None)
        if ob is None or ob.type != 'MESH':
            raise RuntimeError("%s.%s not found under %s; children %s"
                               % (root.name, k, pivot.name, [c.name for c in pivot.children]))
        found[k] = ob
    return pivot, found


def main():
    root = bpy.data.objects.get(PLAQUE)
    paifang = bpy.data.objects.get(PAIFANG)
    if root is None or paifang is None:
        raise RuntimeError("%s or %s not found; is this out/sect_chase.blend?" % (PLAQUE, PAIFANG))
    pivot, old = parts_of(root)
    text = G.AREA["title_zh"]
    pw = float(paifang["plaque_size"][0])
    width = G.plaque_width(pw, text)
    n_obj = len(bpy.data.objects)
    had_eval = bpy.data.scenes.get(P._EVAL_SCENE) is not None
    before = {k: world_box(ob) for k, ob in old.items()}
    log("text", text, "paifang plaque width", round(pw, 3), "-> board width", round(width, 3))

    tmp = bpy.data.collections.new(TMP)
    bpy.context.scene.collection.children.link(tmp)
    saved = U.FONT_KAITI                   # same font-path dance as gate._gate (absolute on the Linux box)
    if os.name != "nt" and os.path.exists(os.path.abspath(saved)):
        U.FONT_KAITI = os.path.abspath(saved)
    try:
        new_root = P.plaque(tmp, text, width, name=TMP + ".plaque")
    finally:
        U.FONT_KAITI = saved
    new_pivot, new = parts_of(new_root)
    if abs(new_pivot.rotation_euler.x - pivot.rotation_euler.x) > 1e-4:
        log("WARN pivot tilt differs:", pivot.rotation_euler.x, "->", new_pivot.rotation_euler.x, "(kept the file's)")

    for k in PARTS:
        ob, src = old[k], new[k]
        if (src.matrix_local.to_translation() - ob.matrix_local.to_translation()).length > 1e-4:
            log("WARN", ob.name, "local offset differs from a fresh plaque's; meshes assume the same offset")
        prev = ob.data
        me = src.data
        src.data = bpy.data.meshes.new(TMP + ".empty")
        me.name = prev.name + ".new"
        ob.data = me
        for s in ob.material_slots:
            if s.link != 'DATA':
                s.link = 'DATA'
        if prev.users == 0:
            bpy.data.meshes.remove(prev)
        me.name = ob.name
        log(k, "->", ob.name, "verts", len(me.vertices), "faces", len(me.polygons),
            "slots", [s.material.name if s.material else None for s in ob.material_slots])

    for ob in list(tmp.all_objects):
        me = ob.data if ob.type == 'MESH' else None
        bpy.data.objects.remove(ob, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    bpy.data.collections.remove(tmp)
    if not had_eval:
        sc = bpy.data.scenes.get(P._EVAL_SCENE)
        if sc is not None and sc != bpy.context.scene:
            bpy.data.scenes.remove(sc)
            log("removed the glyph evaluation scene", P._EVAL_SCENE)
    bpy.context.view_layer.update()

    if len(bpy.data.objects) != n_obj:
        raise RuntimeError("object count changed: %d -> %d" % (n_obj, len(bpy.data.objects)))
    if not len(old["text"].data.polygons):
        raise RuntimeError("plaque text has no faces (font not loaded?)")
    grew = []
    for k, ob in old.items():
        a, b = before[k], world_box(ob)
        if any(y < x - 2e-3 for x, y in zip(a[0], b[0])) or any(y > x + 2e-3 for x, y in zip(a[1], b[1])):
            grew.append((ob.name, a, b))
        log("box", ob.name, tuple(round(v, 3) for v in b[0]), tuple(round(v, 3) for v in b[1]))
    if grew:
        log("CACHES GREW: a world box got bigger", grew, "- run export_web.py -- chunks,meta --profile full before the bake")
    else:
        log("CACHES ok: names unchanged and every world box the same or smaller")
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects))


main()
