"""Cycles previews of the Divine Condor 神雕 (sect/areas/summit.py divine_condor) in out/sect_chase.blend, on the GPU at
low samples (about 1-2 min). Run on the cloud box after patch_divine_condor.py:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_divine_condor.py [-- --samples 24 --quick]

Writes out/preview/divine_condor_*.png (the wrapper copies new files under out/ back to the PC):
    divine_condor_hold.png      chase.cam at the contact hold (frame 1647), 1600 x 900 like the site's screenshots:
                                the bird is the ~80 px profile left of the pine (judge it at 1:1)
    divine_condor_zoom.png      the same camera position and frame with a 6x lens aimed at the bird (what the hold
                                shows, magnified)
    divine_condor_approach.png  chase.cam at frame 1620 (arriving: the bird mid-frame, 104 m)
    divine_condor_side.png      close-up from the hold's side (the bird's right), whole bird and rock
    divine_condor_front.png     three-quarter front (beak, lump, chest, ruff)
    divine_condor_back.png      three-quarter back from the other side (folded wings crossing over the tail)
    divine_condor_head.png      the head: hooked beak, brow, eye, lump, wrinkled neck
    divine_condor_feet.png      legs, toes and talons gripping the rock
Everything renders at the hold frame's lighting with the flyer hidden; volume objects (cloud banks, haze) are hidden
for speed unless --volumes. --quick: hold, zoom and side only. --shots side,head: only those close-ups; --no-cams:
skip hold, zoom and approach; --tag X: names become divine_condor_X_*.png. Does not save the .blend.
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
PREFIX = "divine_condor"
EMPTY = "summit.condor"
APPROACH_FRAME = 1620
ZOOM = 6.0
CAM = "preview.divine_condor.cam"
# close-ups in the condor's own frame (facing -Y, z up from the rock top; the hold sees its right side, -X):
# (name, target, camera offset from the target, lens mm, resolution)
SHOTS = (
    ("side", (0.0, 0.15, 2.2), (-10.0, -0.8, 0.8), 50.0, (960, 1100)),
    ("front", (0.0, -0.3, 2.5), (-5.5, -7.0, 1.2), 50.0, (960, 1100)),
    ("back", (0.0, 0.5, 2.0), (6.5, 8.0, 2.2), 50.0, (960, 1100)),
    ("head", (0.0, -0.95, 4.25), (-2.6, -2.2, 0.5), 50.0, (1000, 900)),
    ("feet", (0.0, -0.15, 0.45), (-3.0, -3.0, 1.1), 50.0, (1100, 800)),
)


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--volumes", action="store_true", help="keep volume objects (slower)")
    ap.add_argument("--shots", default="", help="comma list of close-up shot names (default all)")
    ap.add_argument("--no-cams", action="store_true", help="skip the hold, zoom and approach renders")
    ap.add_argument("--tag", default="", help="file name tag (divine_condor_<tag>_*.png)")
    a, _rest = ap.parse_known_args(argv)
    return a


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
    log("cycles", device, "samples", samples)


def hide_volumes(sc):
    """Hide objects whose material is a volume shader (cloud banks, haze): Cycles volumes dominate a preview."""
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
        return int(next(a["holdFrame"] for a in EW.AREAS if a["id"] == "summit"))
    except Exception as e:  # noqa: BLE001
        log("WARN hold frame from the timeline failed (%s); using 1647" % e)
        return 1647


def render(sc, name, res, tag):
    sc.render.resolution_x, sc.render.resolution_y = res
    path = os.path.join(OUT, "%s_%s%s.png" % (PREFIX, tag + "_" if tag else "", name))
    sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    log("wrote", path, "%.1f s" % (time.time() - t0))


def look_at(ob, loc, target):
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()


def main():
    a = args()
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    hold = hold_frame()
    emp = bpy.data.objects.get(EMPTY)
    if emp is None:
        raise RuntimeError("%s not found - run sect/patch_divine_condor.py first" % EMPTY)
    for ob in sorted(emp.children, key=lambda o: o.name):
        n = len(ob.data.polygons) if ob.type == 'MESH' else 0
        lt = [0] * n
        if n:
            ob.data.polygons.foreach_get("loop_total", lt)
        log(ob.name, "tris", sum(lt) - 2 * n, "slots", [s.material.name if s.material else None for s in ob.material_slots])
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    chase = bpy.data.objects.get(EW.CAMERA)
    if chase is None:
        raise RuntimeError(EW.CAMERA + " not found")
    cd = bpy.data.cameras.new(CAM)
    cd.clip_start, cd.clip_end = 0.1, 5000.0
    cam = bpy.data.objects.new(CAM, cd)
    sc.collection.objects.link(cam)
    try:
        if not a.no_cams:
            sc.camera = chase
            sc.frame_set(hold)
            render(sc, "hold", (1600, 900), a.tag)
            # the same viewpoint, magnified on the bird
            bpy.context.view_layer.update()
            M = emp.matrix_world
            cd.lens = chase.data.lens * ZOOM
            cd.sensor_width, cd.sensor_fit = chase.data.sensor_width, chase.data.sensor_fit
            look_at(cam, chase.matrix_world.translation.copy(), M @ Vector((0.0, 0.1, 2.3)))
            sc.camera = cam
            render(sc, "zoom", (800, 800), a.tag)
            if not a.quick:
                sc.camera = chase
                sc.frame_set(APPROACH_FRAME)
                render(sc, "approach", (1600, 900), a.tag)
        sc.frame_set(hold)
        bpy.context.view_layer.update()
        M = emp.matrix_world
        sc.camera = cam
        cd.sensor_width, cd.sensor_fit = 36.0, 'AUTO'
        shots = SHOTS[:1] if a.quick else SHOTS
        if a.shots:
            shots = [s_ for s_ in SHOTS if s_[0] in a.shots.split(",")]
        for name, target, off, lens, res in shots:
            cd.lens = lens
            look_at(cam, M @ (Vector(target) + Vector(off)), M @ Vector(target))
            render(sc, name, res, a.tag)
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(cd)
    log("done; the .blend was not saved")


main()
