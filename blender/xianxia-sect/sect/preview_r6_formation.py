"""Cycles previews of the round-6 formation (护宗大阵: carved stations, braziers, the armillary, the Five Element
Banners, the Big Dipper star-stones) in a .blend patched by sect/patch_r6_formation.py, on the GPU at low samples.
Run on the cloud box, one render at a time (the box is shared):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r6_formation.py [-- --samples 24 --shots a,b]

or right after the patch in the same session (nothing saved):

    ... out/<copy>.blend --python sect/patch_r6_formation.py --python sect/preview_r6_formation.py -- --no-save

Writes out/preview/r6form_<shot>[_tag].png (the wrapper copies new files under out/ back to the PC):
    hold      chase.cam at the formation hold frame (export_web full profile; 1208)
    approach  chase.cam at frame 1180 (the low approach: paifang, near stations)
    pass      chase.cam at frame 1240 (looking down over the rear half)
    close     from the hold camera's position, 50 mm on the armillary
    station   a rear station and its brazier from the floor 24 m away, 35 mm (the carving, the eye, the fire)
    eye       from the hold camera's position, 135 mm on the two rear stations (eyes, cradles, cloud plates)
    dipper    from the hold camera's position, 85 mm on the Big Dipper star-stones (west)
    flags     from the hold camera's position, 85 mm on the Five Element Banners (east rim)
    top       orthographic, straight down on the plaza (layout check)
Lit at the hold frame. The flyer is hidden, volume objects (cloud banks, haze) too unless --volumes, and the
formation's dome unless --dome (the page draws its own barrier; the bake leaves the dome out). --tag adds a suffix.
Does not save the .blend.
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

from sect import export_web as EW  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
PREFIX = "r6form"
CAM = "preview.r6form.cam"
HOLD = 1208
ALL = ("hold", "approach", "pass", "close", "station", "eye", "dipper", "flags", "top")
FRAMES = dict(approach=1180, **{"pass": 1240})


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--volumes", action="store_true")
    ap.add_argument("--dome", action="store_true")
    ap.add_argument("--shots", default="", help="comma list (default all): " + ",".join(ALL))
    ap.add_argument("--tag", default="")
    ap.add_argument("--res", default="1280x720")
    a, _rest = ap.parse_known_args(argv)
    return a


def setup_cycles(sc, samples):
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


def hold_frame():
    try:
        EW.use_profile("full")
        for a in EW.AREAS:
            if a["id"] == "formation":
                return int(a["holdFrame"])
    except Exception as e:  # noqa: BLE001
        log("WARN hold frame from the timeline failed (%s); using" % e, HOLD)
    return HOLD


def render(sc, name, res, tag):
    sc.render.resolution_x, sc.render.resolution_y = res
    path = os.path.join(OUT, "%s_%s%s.png" % (PREFIX, name, tag))
    sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    log("wrote", path, "%.1f s" % (time.time() - t0))


def look_at(ob, loc, target):
    ob.location = Vector(loc)
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()


def local(p):
    """A point in the formation's own frame (front -Y) -> world."""
    return bpy.data.objects["formation.root"].matrix_world @ Vector(p)


def main():
    a = args()
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    hf = hold_frame()
    want = [s for s in ALL if not a.shots or s in a.shots.split(",")]
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    if not a.dome:
        for ob in bpy.data.objects:
            if ob.name == "formation.dome" or ob.name.startswith("formation.dome."):
                ob.hide_render = True
    chase = bpy.data.objects.get(EW.CAMERA)
    cd = bpy.data.cameras.new(CAM)
    cd.clip_start, cd.clip_end = 0.05, 8000.0
    cam = bpy.data.objects.new(CAM, cd)
    sc.collection.objects.link(cam)
    tag = ("_" + a.tag) if a.tag else ""
    res = tuple(int(v) for v in a.res.split("x"))
    try:
        for shot in want:
            sc.frame_set(FRAMES.get(shot, hf))
            if shot in ("hold", "approach", "pass"):
                sc.camera = chase
                render(sc, shot, res, tag)
                continue
            sc.camera = cam
            cd.type = 'PERSP'
            ch = chase.matrix_world.translation.copy()
            r = res
            if shot == "close":
                cd.lens = 50.0
                look_at(cam, ch, local((0.0, 2.0, 8.5)))
            elif shot == "station":
                cd.lens = 35.0
                # station 1 (rear right, 67.5 deg) and its brazier, from the floor inside the plaza
                look_at(cam, local((0.0, 6.0, 4.5)), local((11.1, 26.8, 5.8)))
            elif shot == "eye":
                cd.lens = 135.0
                # from the hold camera: the two rear stations' tops (eyes, cradles, cloud plates)
                look_at(cam, ch, local((0.0, 26.8, 8.0)))
            elif shot == "dipper":
                cd.lens = 85.0
                look_at(cam, ch, local((-31.0, 23.0, 1.5)))
            elif shot == "flags":
                cd.lens = 85.0
                look_at(cam, ch, local((36.0, 22.0, 7.0)))
            elif shot == "top":
                cd.type = 'ORTHO'
                cd.ortho_scale = 112.0
                look_at(cam, local((0.0, 0.0, 400.0)), local((0.0, 0.0, 0.0)))
                cam.rotation_euler.z = bpy.data.objects["formation.root"].matrix_world.to_euler().z
                r = (1024, 1024)
            render(sc, shot, r, tag)
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(cd)
    log("done; the .blend was not saved")


main()
