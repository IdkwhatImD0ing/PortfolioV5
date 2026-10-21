"""Cycles stills of the abode's grounded Wanderer duet (the qin table scene by the koi pool, sect/areas/abode.py _duet,
sect/patch_r5_duet.py) and of the cliff above the moon gate, on the GPU at low samples. Renders only; the .blend is
not saved. Run on the cloud box on a test copy (never the main file):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<lane>_test.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r5_duet.py -- --tag after --samples 24

Writes out/preview/r5_duet[_<tag>]_<shot>.png (rblender copies them back):
    hold      chase.cam at the abode's hold frame (1380), 1280x720: the scene against the pool and the falling water
    pass      chase.cam at frame 1418, the flight's closest pass, 1280x720
    smear     the hold camera's position, long lens on the cliff above the moon gate (the shelf the moss covered)
    top       straight-ish down on the pool's south rim: footprint against the water, the path and the plants
    close     from the hold camera's side, close: table, qin, xiao, stools, huqin
    low       eye level from the south-west: the stools, the table's feet on the lawn, the huqin against the table
    table     the qin on the table top from above the player's seat
Every still renders at the hold frame's lighting with the flyer hidden; volume objects (mist, haze, cloud banks) are
hidden for speed unless --volumes. Options: --samples 24, --tag r1, --shots hold,close,... , --res 960x540 (the
close-ups; the chase.cam shots are 1280x720).
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
HOLD, PASS = 1380, 1418
CAM = "preview.r5_duet.cam"
SHOTS = ("hold", "pass", "smear", "top", "close", "low", "table")


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r5_duet.py")
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


def views():
    """{shot: (camera, target, lens)} in abode.root's frame, around the duet set (AB.DUET_LOC, AB.DUET_YAW)."""
    cx, cy = AB.DUET_LOC[0], AB.DUET_LOC[1]
    cz = 0.0
    a = AB.DUET_YAW
    ux, uy = math.cos(a), math.sin(a)            # the table's long axis
    vx, vy = -uy, ux                             # away from the hold camera (the pool side)
    return {
        "smear": ((44.66, -41.75, 25.21), (2.0, 27.0, 19.0), 85.0),
        "top": ((cx - 1.0, cy - 6.0, cz + 26.0), (cx, cy + 1.5, cz), 35.0),
        "close": ((cx - vx * 7.5 + ux * 2.0, cy - vy * 7.5 + uy * 2.0, cz + 4.2), (cx, cy, cz + 0.6), 40.0),
        "low": ((cx - vx * 4.2 - ux * 4.0, cy - vy * 4.2 - uy * 4.0, cz + 1.3),
                (cx + ux * 0.3, cy + uy * 0.3, cz + 0.6), 40.0),
        "table": ((cx - vx * 2.2, cy - vy * 2.2, cz + 3.4), (cx + vx * 0.1, cy + vy * 0.1, cz + 0.9), 40.0),
    }


def main():
    a = args()
    sc = bpy.context.scene
    root = bpy.data.objects.get("abode.root")
    if root is None:
        raise RuntimeError("abode.root not found: is this a copy of out/sect_chase.blend?")
    em = bpy.data.objects.get(AB.DUET)
    if em is not None:
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
    vs = views()
    pre = "r5_duet" + ("_" + a.tag if a.tag else "")
    made = []
    tmp = None
    M = root.matrix_world
    try:
        for shot in [s.strip() for s in a.shots.split(",") if s.strip()]:
            if shot in ("hold", "pass"):
                cam = bpy.data.objects.get(EW.CAMERA)
                if cam is None:
                    log("WARN no", EW.CAMERA)
                    continue
                frame, res = (HOLD if shot == "hold" else PASS), (1280, 720)
            elif shot in vs:
                loc, tgt, lens = vs[shot]
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
