"""Cycles previews of the round-5 sun-and-moon emblem (props._sunmoon_flat banner roundels, gate._sun_moon's ridge
finial and plaque medallions) in a .blend patched by sect/patch_r5_sunmoon.py, on the GPU at low samples. Run on the
cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r5_sunmoon.py [-- --samples 24 --shots a,b]

Writes out/preview/sunmoon_<shot>.png (the wrapper copies new files under out/ back to the PC):
    gate_hold / arena_hold / mission_hold / forge_hold   chase.cam at each area's hold frame (export_web full profile)
    gate_zoom      from the gate hold camera, 105 mm on the plaque: medallions, plaque and the ridge finial
    finial         the ridge finial three-quarter from below-front, 50 mm
    medallion      the moon medallion and the plaque, oblique
    arena_zoom     from the arena hold camera, 85 mm on the nearest banners' roundels
    banner         one arena banner's roundel straight on, 2.4 m away
    gate_back      the finial from behind the gate (the depart side), 40 mm
Everything renders at the gate hold's lighting except the other holds (their own frames), flyer hidden, volume objects
(cloud banks, haze) hidden for speed unless --volumes. --tag adds a suffix to the file names. Does not save the .blend.
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
PREFIX = "sunmoon"
CAM = "preview.sunmoon.cam"
HOLDS = dict(gate=93, forge=352, arena=516, mission=619)
ALL = ("gate_hold", "gate_zoom", "finial", "medallion", "gate_back", "arena_hold", "arena_zoom", "banner",
       "mission_hold", "forge_hold")


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--volumes", action="store_true")
    ap.add_argument("--shots", default="", help="comma list (default all): " + ",".join(ALL))
    ap.add_argument("--tag", default="")
    return ap.parse_args(argv)


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


def holds():
    out = dict(HOLDS)
    try:
        EW.use_profile("full")
        for a in EW.AREAS:
            if a["id"] in out:
                out[a["id"]] = int(a["holdFrame"])
    except Exception as e:  # noqa: BLE001
        log("WARN hold frames from the timeline failed (%s); using" % e, HOLDS)
    return out


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


def wpos(name, local=(0.0, 0.0, 0.0)):
    ob = bpy.data.objects.get(name)
    if ob is None:
        raise RuntimeError(name + " not found - run sect/patch_r5_sunmoon.py on this file first")
    return ob.matrix_world @ Vector(local)


def main():
    a = args()
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    hf = holds()
    want = [s for s in ALL if not a.shots or s in a.shots.split(",")]
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    chase = bpy.data.objects.get(EW.CAMERA)
    cd = bpy.data.cameras.new(CAM)
    cd.clip_start, cd.clip_end = 0.05, 8000.0
    cam = bpy.data.objects.new(CAM, cd)
    sc.collection.objects.link(cam)
    tag = ("_" + a.tag) if a.tag else ""
    try:
        for shot in want:
            area = shot.split("_")[0] if shot.endswith("_hold") or shot.endswith("_zoom") else "gate"
            if shot in ("banner",):
                area = "arena"
            sc.frame_set(hf[area])
            if shot.endswith("_hold"):
                sc.camera = chase
                render(sc, shot, (1280, 720), tag)
                continue
            sc.camera = cam
            ch = chase.matrix_world.translation.copy()
            if shot == "gate_zoom":
                cd.lens = 105.0
                look_at(cam, ch, wpos("gate.plaque", (0.0, 0.0, 2.4)))
                res = (1280, 720)
            elif shot == "finial":
                cd.lens = 50.0
                f = wpos("gate.sunmoon_finial", (0.0, 0.0, 1.4))
                look_at(cam, f + Vector((5.5, -9.0, -2.5)), f)
                res = (960, 960)
            elif shot == "medallion":
                cd.lens = 50.0
                m = wpos("gate.moon_medallion")
                look_at(cam, m + Vector((-2.5, -9.0, -2.0)), m + Vector((-2.2, 0.0, 0.0)))
                res = (1280, 720)
            elif shot == "gate_back":
                cd.lens = 40.0
                f = wpos("gate.sunmoon_finial", (0.0, 0.0, 1.2))
                look_at(cam, f + Vector((-6.0, 22.0, -10.0)), f)
                res = (960, 960)
            elif shot == "arena_zoom":
                cd.lens = 85.0
                b = wpos("arena.banner.038.cloth") if bpy.data.objects.get("arena.banner.038.cloth") else \
                    wpos("arena.banner.cloth")
                look_at(cam, ch, b + Vector((0.0, 0.0, -1.0)))
                res = (1280, 720)
            elif shot == "banner":
                ob = bpy.data.objects["arena.banner.001.cloth"]
                cd.lens = 50.0
                c = ob.matrix_world @ Vector((0.0, -1.3, 0.0))      # the roundel, 1.3 m down the cloth
                fwd = ob.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))   # cloth +Z = its front
                look_at(cam, c + fwd.normalized() * 2.6, c)
                res = (720, 960)
            render(sc, shot, res, tag)
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(cd)
    log("done; the .blend was not saved")


main()
