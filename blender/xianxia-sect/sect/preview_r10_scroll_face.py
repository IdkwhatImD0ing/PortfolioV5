"""Cycles stills of the Jade Slip Pavilion's scroll after sect/patch_r10_scroll_face.py, seen the way the site shows the
stop: chase.cam turned by the client's stop framing (scroll.hold_turn, client framing.ts STOP_FRAMING.scroll: 6 deg left
at the hold, easing in over the 48 frames before it and out after). GPU, low samples. Renders only; the .blend is not
saved.

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r10_scroll_face.py [-- --samples 24 --tag r10]

Writes out/preview/r10_scroll_face[_<tag>]_<shot>.png (rblender copies them back), 1280 x 720:
    hold        frame 1103, the full turn
    approach    frame 1080 (turn eased in part way)
    near        frame 1095
    depart      frame 1110
    unturned    frame 1103 without the turn (the film's own frame)
Options: --samples 24, --tag r10, --shots hold,approach,...; --res 1280x720.
"""
import argparse
import math
import os
import sys
import time

import bpy
from mathutils import Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402
from sect.areas import scroll as SC  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
CAM = "preview.r10_scroll_face.cam"
SHOTS = {"hold": (SC.HOLD_FRAME, True), "approach": (1080, True), "near": (1095, True), "depart": (1110, True),
         "unturned": (SC.HOLD_FRAME, False)}


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r10_scroll_face.py")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--tag", default="")
    ap.add_argument("--shots", default="hold,approach,near,depart,unturned")
    ap.add_argument("--res", default="1280x720")
    return ap.parse_args(argv)


def setup_cycles(sc, samples):
    """OptiX, then CUDA, then CPU; denoised low-sample stills (preview_r5_scroll.setup_cycles)."""
    sc.render.engine = "CYCLES"
    device = "CPU"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
            except TypeError:
                continue
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == kind
                device = kind
                break
    except Exception as e:  # noqa: BLE001
        log("WARN GPU setup failed:", e)
    sc.cycles.device = "GPU" if device != "CPU" else "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 4
    sc.cycles.diffuse_bounces = 2
    sc.cycles.glossy_bounces = 2
    sc.cycles.transmission_bounces = 2
    sc.cycles.sample_clamp_indirect = 4.0
    sc.render.use_persistent_data = True
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False
    log("cycles", device, "samples", samples)


def hide_volumes(sc):
    """Hide volume-shader objects (mist, haze, cloud banks): Cycles volumes dominate a preview."""
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


def main():
    a = args()
    sc = bpy.context.scene
    src = bpy.data.objects.get(EW.CAMERA)
    if src is None:
        raise RuntimeError("no %s" % EW.CAMERA)
    os.makedirs(OUT, exist_ok=True)
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    log("volume objects hidden", hide_volumes(sc))
    sc.render.resolution_x, sc.render.resolution_y = (int(x) for x in a.res.split("x"))
    data = src.data.copy()
    tmp = bpy.data.objects.new(CAM, data)
    sc.collection.objects.link(tmp)
    pre = "r10_scroll_face" + ("_" + a.tag if a.tag else "")
    made = []
    try:
        for shot in [s.strip() for s in a.shots.split(",") if s.strip()]:
            if shot not in SHOTS:
                log("WARN unknown shot", shot)
                continue
            frame, turned = SHOTS[shot]
            sc.frame_set(frame)
            M = src.matrix_world
            yaw, pitch = SC.hold_turn(frame) if turned else (0.0, 0.0)
            R = Matrix.Rotation(yaw, 3, 'Z') @ M.to_3x3().normalized() @ Matrix.Rotation(pitch, 3, 'X')
            tmp.matrix_world = Matrix.Translation(M.translation) @ R.to_4x4()
            data.lens, data.sensor_width, data.sensor_fit = src.data.lens, src.data.sensor_width, src.data.sensor_fit
            data.clip_start, data.clip_end = src.data.clip_start, src.data.clip_end
            sc.camera = tmp
            sc.render.filepath = os.path.join(OUT, "%s_%s.png" % (pre, shot))
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            made.append(sc.render.filepath)
            log("wrote", sc.render.filepath, "frame", frame, "turn %.1f deg" % math.degrees(yaw), "%.1f s" % (
                time.time() - t0))
    finally:
        bpy.data.objects.remove(tmp, do_unlink=True)
        bpy.data.cameras.remove(data)
    log("done", len(made), "stills; the .blend was not saved")


main()
