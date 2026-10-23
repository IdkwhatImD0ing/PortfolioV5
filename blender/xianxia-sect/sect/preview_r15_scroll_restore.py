"""Cycles stills of the Jade Slip Pavilion after sect/patch_r15_scroll_restore.py, seen the way the site shows the stop:
chase.cam's own view (r15: no stop framing at the scroll) with the client's field of view for the screen
(camera-path.ts fovForAspect) and, on a phone, the picture shifted up (scene.tsx PORTRAIT_SHIFT). GPU (OptiX, then
CUDA; it refuses the CPU), low samples, denoised. Renders only; the .blend is not saved.

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r15_scroll_restore.py [-- --samples 32]

Writes out/preview/r15_scroll_restore[_<tag>]_<shot>.png (rblender copies them back):
    hold        frame 1103, 1600 x 900 (the owner's screenshots were taken at this size)
    phone       frame 1103, 390 x 844 at 2x (780 x 1688): vertical FOV 70 deg, the picture shifted up 20 %, no turn
    a1060 .. a1100   the approach, every 10 frames, 960 x 540
    d1110 .. d1160   the departure, every 10 frames, 960 x 540
Options: --samples 32, --tag, --shots hold,phone,a1060,...
"""
import argparse
import math
import os
import sys
import time

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import scroll as SC  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
CAM = "preview.r15_scroll_restore.cam"
FILM_CAM = "chase.cam"            # export_web.CAMERA
FLYER_COLL = "flyer"              # export_web.FLYER_COLL: the flyer rig, hidden as export_web.hide_flyer does
PORTRAIT_SHIFT = 0.2
MAX_FOV_Y = 70.0
SHOTS = {"hold": (SC.HOLD_FRAME, (1600, 900), 1)}
SHOTS["phone"] = (SC.HOLD_FRAME, (390, 844), 2)
for _f in range(1060, 1101, 10):
    SHOTS["a%d" % _f] = (_f, (960, 540), 1)
for _f in range(1110, 1161, 10):
    SHOTS["d%d" % _f] = (_f, (960, 540), 1)


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r15_scroll_restore.py")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--tag", default="")
    ap.add_argument("--shots", default=",".join(SHOTS))
    return ap.parse_args(argv)


def setup_cycles(sc, samples):
    """OptiX, then CUDA; denoised low-sample stills. Refuses the CPU."""
    sc.render.engine = "CYCLES"
    device = "CPU"
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
    if device == "CPU":
        raise SystemExit("preview_r15_scroll_restore: no OptiX or CUDA device: refusing to render on the CPU")
    sc.cycles.device = "GPU"
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
    log("cycles device", device, [d.name for d in prefs.devices if d.use], "samples", samples)


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


def hide_flyer():
    coll = bpy.data.collections.get(FLYER_COLL)
    n = 0
    for ob in list(coll.all_objects) if coll is not None else []:
        if ob is not None and ob.name != FILM_CAM:
            ob.hide_render = True
            n += 1
    return n


def main():
    a = args()
    sc = bpy.context.scene
    src = bpy.data.objects.get(FILM_CAM)
    if src is None:
        raise RuntimeError("no %s" % FILM_CAM)
    if tuple(SC.HOLD_TURN) != (0.0, 0.0):
        raise RuntimeError("scroll.HOLD_TURN is %s: this preview shows the unturned view" % (SC.HOLD_TURN,))
    os.makedirs(OUT, exist_ok=True)
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", hide_flyer())
    log("volume objects hidden", hide_volumes(sc))
    data = src.data.copy()
    tmp = bpy.data.objects.new(CAM, data)
    sc.collection.objects.link(tmp)
    pre = "r15_scroll_restore" + ("_" + a.tag if a.tag else "")
    film = 1600.0 / 900.0
    tx_film = src.data.sensor_width / 2.0 / src.data.lens
    made = []
    try:
        for shot in [s.strip() for s in a.shots.split(",") if s.strip()]:
            if shot not in SHOTS:
                log("WARN unknown shot", shot)
                continue
            frame, (w, h), k = SHOTS[shot]
            sc.frame_set(frame)
            tmp.matrix_world = src.matrix_world.copy()
            aspect = w / h
            ty = min(max(tx_film / aspect, tx_film / film), max(tx_film / film, math.tan(math.radians(MAX_FOV_Y / 2))))
            data.sensor_fit = "VERTICAL"
            data.sensor_height = 24.0
            data.lens = 12.0 / ty
            data.shift_x = 0.0
            # scene.tsx setViewOffset(w, h, 0, 0.2 h): the window moves down the full picture, so its content moves up;
            # Blender's shift is in units of the larger side (the height on a portrait screen)
            data.shift_y = -PORTRAIT_SHIFT * h / max(w, h) if h > w * 1.15 else 0.0
            data.clip_start, data.clip_end = src.data.clip_start, src.data.clip_end
            sc.camera = tmp
            sc.render.resolution_x, sc.render.resolution_y = w * k, h * k
            sc.render.filepath = os.path.join(OUT, "%s_%s.png" % (pre, shot))
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            made.append(sc.render.filepath)
            log("wrote", sc.render.filepath, "frame", frame, "%dx%d" % (w * k, h * k), "vertical fov %.1f deg" % (
                2 * math.degrees(math.atan(ty))), "shift_y %.2f" % data.shift_y, "%.1f s" % (time.time() - t0))
    finally:
        bpy.data.objects.remove(tmp, do_unlink=True)
        bpy.data.cameras.remove(data)
    log("done", len(made), "stills; the .blend was not saved")


main()
