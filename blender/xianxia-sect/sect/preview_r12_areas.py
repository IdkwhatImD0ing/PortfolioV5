"""Stills for round 12, lane 'areas' (sect/patch_r12_areas.py): crops of every place the patch changes, from the camera
path (chase.cam at the frame given, zoomed onto the piece), in GPU Cycles at low samples. Renders only; the .blend is
not saved. Run on the cloud box on a copy, before the patch (--tag before) and after it (--tag after):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/r12_areas.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r12_areas.py -- --tag before

Writes out/preview/r12_areas_<tag>_<view>.png (rblender copies them back). Cycles shows the geometry (a hole, a lip,
a floating piece, the look of a carved inscription); it does not show the web's depth-buffer flicker.
Options: --tag (default 'after'), --samples 16, --res 1280x720, --views (comma separated, default all), --engine
(CYCLES or BLENDER_EEVEE).
"""
import argparse
import os
import sys
import time

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import bake_web as BW  # noqa: E402  (setup_cycles)
from sect import export_web as EW  # noqa: E402  (CAMERA, hide_flyer)
from sect.lib import look as L  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
# view: (frame of the path position, target: object names (their box centre) or (area root, local point), field m)
VIEWS = {
    "inscription": (1463, ["abode.inscription"], 16.0),
    "scroll_ring": (1137, ["scroll.ring"], 24.0),
    "scroll_ring_low": (1103, ("scroll.root", (-8.0, 4.5, 0.0)), 14.0),
    "library_lawn": (829, ("library.root", (-30.0, -25.0, -0.3)), 16.0),
    "library_paths": (827, ("library.root", (0.0, -4.9, 0.15)), 14.0),
    "library_depart": (870, ("library.root", (-12.0, -3.0, 0.15)), 16.0),
    "library_arrival_steps": (799, ["library.arrival_steps.steps"], 12.0),
    "mirror_arrival_steps": (210, ["mirror.arrival_steps.steps"], 9.0),
    "mirror_depart_steps": (253, ["mirror.depart_steps.steps"], 9.0),
    "mirror_lotus": (228, ["mirror.lotus"], 8.0),
    "steles_corner": (981, ("steles.root", (13.5, -34.5, 0.17)), 10.0),
    "steles_aisle": (994, ("steles.root", (7.5, -10.0, 0.06)), 10.0),
    "abode_cave": (1437, ("abode.root", (-8.0, 24.0, 6.0)), 12.0),
    "abode_ribbon": (1435, ["abode.ribbon_silk"], 6.0),
    "forge_arrival": (395, ("forge.root", (0.0, -47.0, 0.0)), 16.0),
    "forge_bridgehead": (435, ("forge.root", (-47.0, -8.0, 0.0)), 14.0),
    "arena_front": (531, ["arena.steps.steps"], 14.0),
    "arena_rear": (568, ["arena.rear_landing.body"], 12.0),
    "mission_gallery": (696, ("mission.root", (-30.0, 0.0, 3.0)), 12.0),
    "mission_roles": (639, ["mission.role_tablet.001"], 8.0),
    "gate_saber": (119, ["gate.sword_monolith.001"], 7.0),
    "gate_sword": (119, ["gate.sword_monolith"], 7.0),
    "gate_ridge": (40, ("gate.root", (15.0, -139.0, -67.0)), 30.0),
    "formation_arrival": (1213, ["formation.arrival_steps.steps"], 14.0),
    # close looks from beside the pieces (area root, eye, target in its frame, lens): the step blocks' sides and feet
    "side_library_arrival": ("look", "library.root", (-8.5, -40.4, 0.9), (-3.6, -40.5, -0.15), 30.0),
    "side_mirror_arrival": ("look", "mirror.root", (-11.5, -48.6, 1.7), (-7.3, -51.1, 0.1), 32.0),
    "side_mirror_depart": ("look", "mirror.root", (49.8, 7.7, 1.7), (47.3, 10.4, 0.1), 32.0),
    "side_formation_arrival": ("look", "formation.root", (-7.5, -61.4, 0.8), (-3.8, -61.3, -0.25), 30.0),
    "side_mission_depart": ("look", "mission.root", (53.5, -17.0, 0.9), (53.5, -14.4, -0.2), 30.0),
    "side_arena_front": ("look", "arena.root", (-9.5, -34.8, -0.4), (-4.4, -34.6, -0.9), 30.0),
    "side_library_depart": ("look", "library.root", (-40.5, -15.5, 1.0), (-43.0, -11.4, -0.2), 30.0),
    "mission_gallery_end": ("look", "mission.root", (-31.5, -7.0, 4.2), (-30.0, 0.0, 3.0), 35.0),
    "steles_corridor_start": ("look", "steles.root", (16.0, -40.0, 1.6), (14.6, -34.5, 0.17), 35.0),
    "library_lawn_top": ("look", "library.root", (-10.0, -55.0, 30.0), (-12.0, -15.0, -0.3), 30.0),
    "mirror_lawn_top": ("look", "mirror.root", (0.0, -70.0, 30.0), (0.0, -25.0, -0.4), 30.0),
    "gate_ridge_side": ("look", "gate.root", (-25.0, -128.0, -30.0), (0.0, -108.0, -42.4), 35.0),
    "mission_board_close": ("look", "mission.role_tablet.004", (3.0, -7.0, -1.0), (0.0, 0.0, -1.5), 40.0),
    "mission_board_oblique": ("look", "mission.role_tablet.004", (6.0, -3.5, -1.5), (0.0, 0.0, -1.5), 40.0),
    "gate_saber_front": ("look", "gate.root", (14.0, -34.0, 7.0), (16.0, -25.2, 6.0), 50.0),
    "gate_saber_couplet": ("look", "gate.root", (22.8, -26.5, 1.6), (18.1, -25.4, 1.4), 35.0),
    "gate_sword_name": ("look", "gate.root", (-14.5, -33.5, 9.0), (-16.0, -25.2, 8.8), 60.0),
}


def log(*a):
    print("PREVIEW", *a, flush=True)


def hide_volumes(sc):
    vol = {m.name for m in bpy.data.materials
           if m.node_tree is not None and any(n.bl_idname.startswith("ShaderNodeVolume") for n in m.node_tree.nodes)}
    n = 0
    for ob in sc.objects:
        if ob.hide_render or ob.type not in {"MESH", "CURVE", "SURFACE", "META", "FONT", "VOLUME"}:
            continue
        if ob.type == "VOLUME" or any(s.material is not None and s.material.name in vol for s in ob.material_slots):
            ob.hide_render = True
            n += 1
    return n


def target_of(t):
    if isinstance(t, tuple):
        root, p = t
        return bpy.data.objects[root].matrix_world @ Vector(p)
    pts = []
    dg = bpy.context.evaluated_depsgraph_get()
    for name in t:
        ob = bpy.data.objects.get(name)
        if ob is None:
            continue
        ev = ob.evaluated_get(dg)
        pts += [ev.matrix_world @ Vector(c) for c in ev.bound_box]
        for c in ob.children_recursive:
            if c.type == 'MESH':
                pts += [c.matrix_world @ Vector(k) for k in c.bound_box]
    if not pts:
        raise KeyError(t)
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return (lo + hi) * 0.5


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r12_areas.py")
    ap.add_argument("--tag", default="after")
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--views", default=",".join(VIEWS))
    ap.add_argument("--engine", default="CYCLES")
    a = ap.parse_args(argv)
    sc = bpy.context.scene
    log("volumes hidden:", hide_volumes(sc))
    log("flyer objects hidden", EW.hide_flyer(sc))
    if a.engine == "CYCLES":
        BW.setup_cycles(sc, a.samples)
        sc.cycles.use_denoising = True
    else:
        sc.render.engine = a.engine
    r = sc.render
    r.use_persistent_data = True
    r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"
    r.film_transparent = False
    r.resolution_x, r.resolution_y = (int(x) for x in a.res.split("x"))
    os.makedirs(OUT, exist_ok=True)
    chase = bpy.data.objects.get(EW.CAMERA)
    made = []
    cam = None
    for name in [v.strip() for v in a.views.split(",") if v.strip()]:
        v = VIEWS[name]
        if v[0] == "look":
            _l, root, e_, t_, lens = v
            frame = sc.frame_current
            M = bpy.data.objects[root].matrix_world
            eye, t = M @ Vector(e_), M @ Vector(t_)
            dist = (t - eye).length
        else:
            frame, tgt, field = v
            sc.frame_set(frame)
            eye = chase.matrix_world.translation.copy()
            t = target_of(tgt)
            dist = (t - eye).length
            lens = max(18.0, min(400.0, 36.0 * dist / field))
        if cam is not None:
            cd = cam.data
            bpy.data.objects.remove(cam, do_unlink=True)
            bpy.data.cameras.remove(cd)
        cam = L.camera_look_at("preview.r12." + name, eye, t, lens=lens, collection=sc.collection)
        cam.data.clip_start = 0.5
        cam.data.clip_end = 9000.0
        sc.camera = cam
        r.filepath = os.path.join(OUT, "r12_areas_%s_%s.png" % (a.tag, name))
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        made.append(r.filepath)
        log(name, "frame", frame, "dist %.1f m lens %.0f" % (dist, lens), r.filepath, "%.1f s" % (time.time() - t0))
    log("done", len(made), "stills in", OUT)


main()
