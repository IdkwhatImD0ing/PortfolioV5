"""Cycles previews of the round-7 Divine Condor 神雕 (sect/areas/summit.py divine_condor: the prepared bird on its
crag beyond the west rail), on the GPU at low samples. Run on the cloud box after sect/patch_r7_condor.py, on the
patched copy:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r7_condor.py [-- --samples 32 --volumes]

Writes out/preview/r7_condor/<name>.png (the wrapper copies new files under out/ back to the PC):
    hold        chase.cam at the contact hold (frame 1647), 1600 x 900 like the site's screenshots
    zoom        the same camera position and frame, 5x lens on the bird (what the hold shows, magnified)
    approach    chase.cam at frame 1620 (arriving), approach_early: frame 1599
    side        close-up in profile from the hold's side (whole bird and capstone)
    front       three-quarter front (beak, head, chest, feet on the rock)
    back        three-quarter back from the cliff side (folded wings, tail)
    crag        the whole crag from the hold's direction, 18 m out: the column, its dome, the boulders
Everything renders at the hold frame's lighting with the flyer hidden; volume objects (cloud banks, haze) are hidden
for speed unless --volumes. --shots a,b: only those. Does not save the .blend.
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

OUT = os.path.join(ROOT, "out", "preview", "r7_condor")
BIRD = "summit.condor_bird"
CRAG = "summit.condor_crag"
HOLD = 1647
ZOOM = 5.0
CAM = "preview.r7_condor.cam"
# close-ups in the bird's own frame (beak toward -Y, z up from the feet; the hold sees its right side, -X)
SHOTS = (
    ("side", (0.0, 0.2, 0.8), (-5.5, -0.4, 0.6), 50.0, (900, 900)),
    ("front", (0.0, -0.2, 0.9), (-3.2, -4.2, 0.9), 50.0, (900, 900)),
    ("back", (0.0, 0.4, 0.8), (3.6, 4.4, 1.6), 50.0, (900, 900)),
)


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--volumes", action="store_true", help="keep volume objects (slower)")
    ap.add_argument("--shots", default="", help="comma list (hold,zoom,approach,side,front,back,crag); default all")
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


def look_at(ob, loc, target):
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()


def main():
    a = args()
    want = set(a.shots.split(",")) if a.shots else None
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    bird = bpy.data.objects.get(BIRD)
    crag = bpy.data.objects.get(CRAG)
    if bird is None or crag is None:
        raise RuntimeError("%s / %s not found - run sect/patch_r7_condor.py first" % (BIRD, CRAG))
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    chase = bpy.data.objects[EW.CAMERA]
    cd = bpy.data.cameras.new(CAM)
    cd.clip_start, cd.clip_end = 0.1, 6000.0
    cam = bpy.data.objects.new(CAM, cd)
    sc.collection.objects.link(cam)

    def render(name, res):
        if want is not None and name.split("_")[0] not in want:
            return
        sc.render.resolution_x, sc.render.resolution_y = res
        sc.render.filepath = os.path.join(OUT, name + ".png")
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        log("wrote", sc.render.filepath, "%.1f s" % (time.time() - t0))

    try:
        sc.camera = chase
        sc.frame_set(HOLD)
        render("hold", (1600, 900))
        bpy.context.view_layer.update()
        M = bird.matrix_world
        cd.lens = chase.data.lens * ZOOM
        cd.sensor_width, cd.sensor_fit = chase.data.sensor_width, chase.data.sensor_fit
        look_at(cam, chase.matrix_world.translation.copy(), M @ Vector((0.0, 0.2, 0.8)))
        sc.camera = cam
        render("zoom", (800, 800))
        sc.camera = chase
        sc.frame_set(1620)
        render("approach", (1600, 900))
        sc.frame_set(1599)
        render("approach_early", (1600, 900))
        sc.frame_set(HOLD)
        bpy.context.view_layer.update()
        M = bird.matrix_world
        sc.camera = cam
        cd.sensor_width, cd.sensor_fit = 36.0, 'AUTO'
        for name, target, off, lens, res in SHOTS:
            cd.lens = lens
            look_at(cam, M @ (Vector(target) + Vector(off)), M @ Vector(target))
            render(name, res)
        c = M.translation.copy()
        to_cam = chase.matrix_world.translation - c
        to_cam.z = 0.0
        cd.lens = 28.0
        look_at(cam, c + to_cam.normalized() * 18.0 + Vector((0.0, 0.0, -2.0)), c + Vector((0.0, 0.0, -5.0)))
        render("crag", (900, 1100))
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(cd)
    log("done; the .blend was not saved")


main()
