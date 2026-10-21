"""Cycles stills of the jade scroll's Jin Yong script (sect/patch_r8_scrolltext.py): the hold view and close views of
the slips, to see that the script reads as dense gold from the hold and that every glyph is a real KaiTi character
(no empty boxes) up close. GPU, low samples. Renders only; the .blend is not saved.

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r8_scrolltext.py [-- --samples 24 --tag after]

Writes out/preview/r8_scrolltext[_<tag>]_<shot>.png (rblender copies them back):
    hold        chase.cam at the scroll hold (1103), 1600 x 900: what the reader sees
    approach    chase.cam at 1080 (flying in toward the hold, the scroll ahead)
    right       the right half of the slips, square on (reading columns 0 .. ~12: the nine passages begin here)
    left        the left half, down to the roll (the second cycle and the blank slips)
    detail      the top of the first four reading columns, close
    detail2     the middle of reading columns 8 .. 12 (the Sword Tomb and Condor passages), close
Close views are placed in scroll.jade_scroll's own frame (props.bamboo_slip_scroll's slip arc), so they follow the
scroll wherever it stands. Options: --samples 24, --tag x, --shots hold,right,..., --volumes (keep mist volumes).
"""
import argparse
import math
import os
import sys
import time

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402
from sect.areas import scroll as SC  # noqa: E402
from sect.lib import look as L  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
HOLD, APPROACH = 1103, 1080
CAM = "preview.r8_scrolltext.cam"
SHOTS = ("hold", "approach", "right", "left", "detail", "detail2")


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r8_scrolltext.py")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--tag", default="")
    ap.add_argument("--shots", default=",".join(SHOTS))
    ap.add_argument("--volumes", action="store_true", help="keep volume objects (slower)")
    return ap.parse_args(argv)


def setup_cycles(sc, samples):
    """OptiX, then CUDA, then CPU; denoised low-sample stills (as preview_r5_scroll.py)."""
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


def slip_views():
    """{shot: (camera, target, lens, (w, h))} in scroll.jade_scroll's frame: square on to the slip arc at a reading
    column, at the height of the rows wanted."""
    W, H = SC.SCROLL_W, SC.SCROLL_H
    N = max(8, int(round(W / (H * 0.075))))
    cell = W / N * 0.88 * 0.80
    rows = int(H * 0.84 / cell)
    d = SC.SCROLL_CURVE * W
    R = (W * W / 4 + d * d) / (2 * d)
    half = math.asin(min(1.0, W / 2 / R))
    top = rows * cell / 2.0

    def at(col, z, dist, lens, res):
        i = N - 1 - col                                    # reading column -> slip index (0 = leftmost)
        a = -half + 2 * half * (i + 0.5) / N
        p = Vector((R * math.sin(a), -R + R * math.cos(a), z))
        out = Vector((-math.sin(a), -math.cos(a), 0.0))    # toward the reader
        return (tuple(p + out * dist), tuple(p), lens, res)
    return {
        "right": at(6.0, 0.0, 15.5, 35.0, (1920, 1080)),
        "left": at(N - 8.0, 0.0, 15.5, 35.0, (1920, 1080)),
        "detail": at(1.5, top - 2.0 * cell, 5.2, 50.0, (1600, 900)),
        "detail2": at(10.0, top - 4.5 * cell, 7.0, 50.0, (1600, 900)),
    }


def main():
    a = args()
    sc = bpy.context.scene
    js = bpy.data.objects.get(SC.K + ".jade_scroll")
    if js is None:
        raise RuntimeError("scroll.jade_scroll not found")
    os.makedirs(OUT, exist_ok=True)
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    views = slip_views()
    pre = "r8_scrolltext" + ("_" + a.tag if a.tag else "")
    M = js.matrix_world
    made, tmp = [], None
    try:
        for shot in [s.strip() for s in a.shots.split(",") if s.strip()]:
            if shot in ("hold", "approach"):
                cam = bpy.data.objects.get(EW.CAMERA)
                if cam is None:
                    log("WARN no", EW.CAMERA)
                    continue
                frame, res = {"hold": HOLD, "approach": APPROACH}[shot], (1600, 900)
            elif shot in views:
                loc, tgt, lens, res = views[shot]
                if tmp is not None:
                    cd = tmp.data
                    bpy.data.objects.remove(tmp, do_unlink=True)
                    bpy.data.cameras.remove(cd)
                cam = tmp = L.camera_look_at(CAM, M @ Vector(loc), M @ Vector(tgt), lens=lens, collection=sc.collection)
                cam.data.clip_start = 0.05
                frame = HOLD
            else:
                log("WARN unknown shot", shot)
                continue
            sc.camera = cam
            sc.frame_set(frame)
            sc.render.resolution_x, sc.render.resolution_y = res
            sc.render.filepath = os.path.join(OUT, "%s_%s.png" % (pre, shot))
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            made.append(sc.render.filepath)
            log("wrote", sc.render.filepath, "frame", frame, "%.1f s" % (time.time() - t0))
    finally:
        if tmp is not None:
            cd = tmp.data
            bpy.data.objects.remove(tmp, do_unlink=True)
            bpy.data.cameras.remove(cd)
    log("done", len(made), "stills; the .blend was not saved")


main()
