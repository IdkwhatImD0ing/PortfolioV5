"""Cycles stills of the Smiling, Proud Wanderer duet (sect/areas/abode.py _duet, sect/patch_wanderer_duet.py) on the
GPU at low samples. Renders only; the .blend is not saved. Run on the cloud box after the patch:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_wanderer_duet.py [-- --samples 24]

Writes out/preview/wanderer_duet[_<tag>]_<shot>.png (rblender copies them back):
    hold      chase.cam at the abode's hold frame (1380): the group against the falling water
    pass      chase.cam at frame 1398, the closest pass with the group in frame
    group     the whole group from the hold camera's side, close
    qin       the guqin from above: strings, hui, bridge, gums
    head      the qin's head end: the bridge, the pegs and their red tassels
    xiao      the xiao's finger holes and the red tassel
    mouth     the xiao's U-notch mouthpiece
    huqin     Mo Da's huqin three-quarter: skin, neck, pegs, bow
    hilt      the sword hilt rising out of the box beside the neck
Every still renders at the hold frame's lighting with the flyer hidden; volume objects (mist, haze, cloud banks) are
hidden for speed unless --volumes. Options: --samples 24, --tag r1, --shots hold,qin,... , --res 960x540 (close-ups;
the chase.cam shots are 1280x720).
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
from sect.areas import abode as AB  # noqa: E402
from sect.lib import look as L  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
HOLD, PASS = 1380, 1398
CAM = "preview.wanderer_duet.cam"
SHOTS = ("hold", "pass", "group", "qin", "head", "xiao", "mouth", "huqin", "hilt")


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_wanderer_duet.py")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--tag", default="")
    ap.add_argument("--shots", default=",".join(SHOTS))
    ap.add_argument("--res", default="960x540")
    ap.add_argument("--volumes", action="store_true", help="keep volume objects (slower)")
    return ap.parse_args(argv)


def setup_cycles(sc, samples):
    """bake_web.setup_cycles' device pick (OptiX), with CUDA then CPU as fallbacks; denoised low-sample stills."""
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
    """Hide objects whose material is a volume shader (mist, haze, cloud banks): Cycles volumes dominate a preview."""
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


def close_ups():
    """{shot: (object whose frame the numbers are in, camera, target, lens)}: the duet frame (x the qin's long axis,
    head +x; y away from the hold camera; z the qin's top) or the huqin's own frame (z its neck, skin at -y)."""
    xc, yc = AB.XIAO_C
    xz = AB.duet_xforms()["xiao"][0][2]
    ca, sa = math.cos(AB.XIAO_CROSS), math.sin(AB.XIAO_CROSS)

    def on_xiao(z_local, lift=0.0):
        return (xc + z_local * ca, yc + z_local * sa, xz + lift)
    holes = on_xiao(AB.XIAO_LEN * 0.5 - 1.35)
    mouth = on_xiao(AB.XIAO_LEN * 0.5 - 0.02)
    return {
        "group": (AB.DUET, (0.6, -6.2, 7.2), (0.6, 0.2, 0.6), 50.0),
        "qin": (AB.DUET, (0.0, -1.7, 2.7), (0.0, 0.02, 0.12), 35.0),
        "head": (AB.DUET, (2.55, -1.45, 0.42), (1.2, 0.0, -0.04), 45.0),
        "xiao": (AB.DUET, (holes[0] + 0.15, holes[1] - 0.75, holes[2] + 0.9), holes, 50.0),
        "mouth": (AB.DUET, (mouth[0] + 0.45, mouth[1] - 0.25, mouth[2] + 0.45), mouth, 60.0),
        "huqin": ("abode.duet_huqin", (3.4, -3.4, 1.5), (0.0, 0.1, 0.95), 35.0),
        "hilt": ("abode.duet_huqin", (0.85, -0.6, 0.55), (-0.03, -0.04, 0.33), 55.0),
    }


def main():
    a = args()
    sc = bpy.context.scene
    em = bpy.data.objects.get(AB.DUET)
    if em is None:
        raise RuntimeError("%s not found: run sect/patch_wanderer_duet.py first" % AB.DUET)
    for ob in [em] + list(em.children_recursive):
        if ob.type == 'MESH':
            n = len(ob.data.polygons)
            lt = [0] * n
            ob.data.polygons.foreach_get("loop_total", lt)
            log(ob.name, "tris", sum(lt) - 2 * n, "slots", [s.material.name if s.material else None
                                                            for s in ob.material_slots])
    os.makedirs(OUT, exist_ok=True)
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    w, h = (int(x) for x in a.res.split("x"))
    views = close_ups()
    pre = "wanderer_duet" + ("_" + a.tag if a.tag else "")
    made = []
    tmp = None
    try:
        for shot in [s.strip() for s in a.shots.split(",") if s.strip()]:
            if shot in ("hold", "pass"):
                cam = bpy.data.objects.get(EW.CAMERA)
                if cam is None:
                    log("WARN no", EW.CAMERA)
                    continue
                frame, res = (HOLD if shot == "hold" else PASS), (1280, 720)
            elif shot in views:
                frame_ob, loc, tgt, lens = views[shot]
                M = bpy.data.objects[frame_ob].matrix_world
                cam = tmp = L.camera_look_at(CAM, M @ Vector(loc), M @ Vector(tgt), lens=lens,
                                             collection=sc.collection)
                cam.data.clip_start = 0.05
                frame, res = HOLD, (w, h)
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
