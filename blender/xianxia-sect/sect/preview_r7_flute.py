"""Cycles stills of Huang Yaoshi's jade flute set at the Heart-Mirror pond (sect/areas/mirror.py _flute,
sect/lib/flute_props.py, sect/patch_r7_flute.py), on the GPU at low samples. Renders only; the .blend is not saved. Run
on the cloud box on a test copy (never the main file):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/r7_flute_test.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r7_flute.py -- --tag after --samples 32

Writes out/preview/r7_flute[_<tag>]_<shot>.png (rblender copies them back):
    hold    chase.cam at the mirror's hold frame (217), 1600x900 like the live shots
    zoom    the hold camera's own position, lens x4 on the set: how the hold sees it, magnified
    close   from the hold camera's side, ~6 m off: the rock, the cloth, the flute, the tassel, the petals
    low     eye level from the south-east, along the bank
    pond    from across the pond (west), the water in front of the rock
    top     from above
Every still renders at the hold frame's lighting with the flyer hidden; volume objects (mist, haze, cloud banks) are
hidden for speed unless --volumes. Options: --samples 32, --tag r1, --shots hold,zoom,... , --res 1280x720 (all but
hold), --at x,y (mirror.root frame; default mirror.FLUTE_LOC).
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
from sect.areas import mirror as MI  # noqa: E402
from sect.lib import look as L  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
HOLD = 217
CAM = "preview.r7_flute.cam"
SHOTS = ("hold", "zoom", "close", "low", "pond", "top")


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r7_flute.py")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--tag", default="")
    ap.add_argument("--shots", default=",".join(SHOTS))
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--at", default="")
    ap.add_argument("--zoom", type=float, default=4.0)
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


def views(cx, cy, cz, cam_local):
    """{shot: (camera, target, lens)} in mirror.root's frame, around the set at (cx, cy, cz)."""
    dx, dy = cx - cam_local.x, cy - cam_local.y
    d = math.hypot(dx, dy)
    fx, fy = dx / d, dy / d                       # hold camera -> set, horizontal
    rx, ry = fy, -fx                              # to the hold camera's right
    t = (cx, cy, cz + 0.45)
    return {
        "close": ((cx - fx * 5.2 + rx * 1.4, cy - fy * 5.2 + ry * 1.4, cz + 2.6), t, 40.0),
        "low": ((cx - fx * 3.0 + rx * 4.2, cy - fy * 3.0 + ry * 4.2, cz + 1.0), (cx, cy, cz + 0.5), 38.0),
        "pond": ((cx - 9.5, cy + 1.2, cz + 2.2), (cx + 0.3, cy, cz + 0.5), 40.0),
        "top": ((cx - fx * 1.0, cy - fy * 1.0, cz + 9.0), (cx, cy, cz), 35.0),
    }


def main():
    a = args()
    sc = bpy.context.scene
    root = bpy.data.objects.get("mirror.root")
    if root is None:
        raise RuntimeError("mirror.root not found: is this a copy of out/sect_chase.blend?")
    if a.at:
        cx, cy = (float(v) for v in a.at.split(","))
    else:
        cx, cy = MI.FLUTE_LOC[0], MI.FLUTE_LOC[1]
    cz = 0.0
    em = bpy.data.objects.get(getattr(MI, "FLUTE", "mirror.flute"))
    if em is not None:
        for ob in [em] + list(em.children_recursive):
            if ob.type == 'MESH':
                n = len(ob.data.polygons)
                lt = [0] * n
                ob.data.polygons.foreach_get("loop_total", lt)
                log(ob.name, "tris", sum(lt) - 2 * n, "slots", [s.material.name if s.material else None
                                                                for s in ob.material_slots])
    else:
        log("no flute set in this file (a 'before' still)")
    os.makedirs(OUT, exist_ok=True)
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    w, h = (int(x) for x in a.res.split("x"))
    hold_cam = bpy.data.objects.get(EW.CAMERA)
    if hold_cam is None:
        raise RuntimeError("no %s" % EW.CAMERA)
    sc.frame_set(HOLD)
    M = root.matrix_world
    cam_local = M.inverted() @ hold_cam.matrix_world.translation
    vs = views(cx, cy, cz, cam_local)
    pre = "r7_flute" + ("_" + a.tag if a.tag else "")
    made = []
    tmp = None
    try:
        for shot in [s.strip() for s in a.shots.split(",") if s.strip()]:
            if shot == "hold":
                cam, res = hold_cam, (1600, 900)
            elif shot == "zoom":
                cam = tmp = L.camera_look_at(CAM, hold_cam.matrix_world.translation.copy(),
                                             M @ Vector((cx, cy, cz + 0.4)), lens=hold_cam.data.lens * a.zoom,
                                             collection=sc.collection)
                cam.data.clip_start = 0.1
                res = (w, h)
            elif shot in vs:
                loc, tgt, lens = vs[shot]
                cam = tmp = L.camera_look_at(CAM, M @ Vector(loc), M @ Vector(tgt), lens=lens,
                                             collection=sc.collection)
                cam.data.clip_start = 0.05
                res = (w, h)
            else:
                log("WARN unknown shot", shot)
                continue
            sc.camera = cam
            sc.frame_set(HOLD)
            sc.render.resolution_x, sc.render.resolution_y = res
            sc.render.filepath = os.path.join(OUT, "%s_%s.png" % (pre, shot))
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            made.append(sc.render.filepath)
            log("wrote", sc.render.filepath, "frame", HOLD, "%.1f s" % (time.time() - t0))
    finally:
        if tmp is not None:
            cd = tmp.data
            bpy.data.objects.remove(tmp, do_unlink=True)
            bpy.data.cameras.remove(cd)
    log("done", len(made), "stills; the .blend was not saved")


main()
