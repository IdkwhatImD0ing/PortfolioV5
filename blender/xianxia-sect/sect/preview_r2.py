"""Cycles previews for the round-2 geometry patches (sect/patch_r2_*.py), on the GPU at low samples: chase.cam at
path frames, and side views of the link stairways. Run on the cloud box, on the patched .blend (or the unpatched one
with another --tag, for a before / after pair):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<file>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r2.py -- --tag after \
        [--frames 93,135,974,1208,1450] [--links gate_mirror:0.55,abode_summit:0.4] [--samples 20] [--res 960x540]

Writes out/preview/r2_<tag>_f<frame>.png and r2_<tag>_<link>_<t>.png (the wrapper copies new files under out/ back
to the PC). A link view stands SIDE m off the stairway's chord at fraction t of it, on the side the camera path is
not, a little under the treads, looking at the stair there. Volume objects (cloud banks, fog) are hidden for speed
unless --volumes; the flyer is hidden. Does not save the .blend.
"""
import argparse
import json
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
CAM = "preview.r2.cam"
SIDE = 70.0
DROP = 12.0


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="r2")
    ap.add_argument("--frames", default="93,135,974,1208,1450")
    ap.add_argument("--links", default="", help="comma list of <a>_<b>:<t> link side views")
    ap.add_argument("--samples", type=int, default=20)
    ap.add_argument("--res", default="960x540")
    ap.add_argument("--lens", type=float, default=30.0, help="link views' lens (mm)")
    ap.add_argument("--volumes", action="store_true", help="keep volume objects (slower)")
    return ap.parse_args(argv)


def setup_cycles(sc, samples):
    """OptiX, then CUDA, then CPU; denoised low-sample stills (as preview_holy_fire_altar.py)."""
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
    log("cycles", device, "samples", samples)


def hide_volumes(sc):
    vol = set()
    for m in bpy.data.materials:
        if m.node_tree is not None and any(n.bl_idname.startswith("ShaderNodeVolume") for n in m.node_tree.nodes):
            vol.add(m.name)
    n = 0
    for ob in sc.objects:
        if ob.hide_render or ob.type not in {"MESH", "CURVE", "SURFACE", "META", "FONT", "VOLUME"}:
            continue
        if ob.type == "VOLUME" or any(s.material is not None and s.material.name in vol for s in ob.material_slots):
            ob.hide_render = True
            n += 1
    return n


def render(sc, tag, name, res):
    sc.render.resolution_x, sc.render.resolution_y = res
    path = os.path.join(OUT, "r2_%s_%s.png" % (tag, name))
    sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    log("wrote", path, "%.1f s" % (time.time() - t0))


def look_at(ob, loc, target):
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()


def link_view(sc, chase, key, t):
    """(camera location, target) beside link ``key`` at chord fraction t, on the side away from the camera path."""
    reps = {r["link"].replace("-", "_"): r for r in json.loads(bpy.data.objects["world.root"]["links"])}
    r = reps[key]
    a, b = np.asarray(r["depart"]["world"], float), np.asarray(r["arrival"]["world"], float)
    p = a + (b - a) * t
    d = (b - a)[:2] / max(np.linalg.norm((b - a)[:2]), 1e-6)
    n = np.array([-d[1], d[0]])
    # the camera path's side at the stair: chase.cam's mean position over the frames nearest p
    best = None
    for f in range(sc.frame_start, sc.frame_end + 1, 8):
        sc.frame_set(f)
        c = np.asarray(chase.matrix_world.translation)
        dd = np.linalg.norm(c[:2] - p[:2])
        if best is None or dd < best[0]:
            best = (dd, c)
    side = -1.0 if best is not None and float(np.dot(best[1][:2] - p[:2], n)) > 0 else 1.0
    loc = p + np.r_[n * side * SIDE - d * 15.0, -DROP]
    return tuple(loc), tuple(p + np.array([0.0, 0.0, -6.0]))


def main():
    a = args()
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    res = tuple(int(v) for v in a.res.split("x"))
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    chase = bpy.data.objects.get(EW.CAMERA)
    if chase is None:
        raise RuntimeError(EW.CAMERA + " not found")
    sc.camera = chase
    for f in [int(x) for x in a.frames.split(",") if x.strip()]:
        sc.frame_set(f)
        render(sc, a.tag, "f%d" % f, res)
    if a.links:
        cd = bpy.data.cameras.new(CAM)
        cd.clip_start, cd.clip_end = 0.1, 8000.0
        cd.lens = a.lens
        cam = bpy.data.objects.new(CAM, cd)
        sc.collection.objects.link(cam)
        try:
            for spec in a.links.split(","):
                key, _, t = spec.partition(":")
                t = float(t or 0.5)
                loc, tgt = link_view(sc, chase, key, t)
                sc.frame_set(EW.SCENE_FRAME if isinstance(EW.SCENE_FRAME, int) else 352)
                look_at(cam, loc, tgt)
                sc.camera = cam
                render(sc, a.tag, "%s_%02d" % (key, int(round(t * 100))), res)
        finally:
            sc.camera = chase
            bpy.data.objects.remove(cam, do_unlink=True)
            bpy.data.cameras.remove(cd)
    log("done; the .blend was not saved")


try:
    main()
except Exception:
    import traceback
    traceback.print_exc()
    sys.exit(1)
