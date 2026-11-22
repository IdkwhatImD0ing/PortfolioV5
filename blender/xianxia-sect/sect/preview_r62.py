"""Round 62 stills: the abode waterfall's notch before and after sect/patch_r62_notch.py, from the flight camera
chase.cam turned as the page turns it, lit and graded as the abode's bake (the twilight light of round 61), Cycles on
the box GPU (OptiX, then CUDA; it refuses the CPU). Renders only: the .blend is never saved.

    python <worktree>/blender/xianxia-sect/tools/rblender.py -b E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r62.py -- --tag before \
        [--views hold,front,arrive,plain,hold_zoom,front_zoom] [--samples 128] [--bake-light <spec>|day|film]

Views (patch_r62_notch.VIEWS; client/out/wf/shoot.ps1 takes the same page screenshots):
    hold     frame 1380, yaw -17.9, pitch 22.2 (client/out/wf/sides4/top-f1380.png)
    front    frame 1428, yaw -57.0, pitch 38.7
    arrive   frame 1352, yaw -9.7, pitch 13.0
    plain    frame 1380, no turn
    close    frame 1404, yaw -24.4, pitch 33.4
    left     frame 1452, yaw -80.4, pitch 28.9
    <view>_zoom   the same eye aimed at the notch (FALL_X, the chute plane, the lip + 3 m) with ZOOM x the lens
Writes out/tmp/r62/renders/r62_<tag>_<view>.png.
"""
import argparse
import json
import os
import sys
import time

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import bake_web as BW  # noqa: E402
from sect import export_web as EW  # noqa: E402
from sect import patch_r62_notch as PN  # noqa: E402
from sect.areas import abode as AB  # noqa: E402

RES = PN.RES
CAM = "preview.r62.cam"
ZOOM = 3.0
OUT = os.path.join(ROOT, "out", "tmp", "r62", "renders")
ALL = ("hold", "close", "front", "left", "arrive", "plain", "hold_zoom")


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r62.py")
    ap.add_argument("--samples", type=int, default=128)
    ap.add_argument("--tag", default="")
    ap.add_argument("--views", default=",".join(ALL))
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--bake-light", default=PN.TWILIGHT,
                    help="a bake_web --light spec (default: the abode's twilight bake light), 'day' (today's "
                         "BAKE_LIGHT) or 'film' (the scene's own light and the film's view)")
    a = ap.parse_args(argv)
    a.out = EW.fix_path(a.out)          # 'E:/...' -> '/E:/...' on the box, so the stills come back
    return a


def setup_cycles(sc, samples):
    """OptiX, then CUDA; denoised stills. Refuses the CPU (preview_r59.setup_cycles)."""
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
        raise SystemExit("preview_r62: no OptiX or CUDA device: refusing to render on the CPU")
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
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False
    log("cycles device", device, [d.name for d in prefs.devices if d.use], "samples", samples)


def bake_view(sc):
    """The bake's post grade (preview_r59.bake_view): AgX, AgX - Punchy, exposure POST_EXPOSURE, the look.py CDL grade
    and highlight / shadow saturation, then saturation POST_SAT. Replaces the film's compositor in memory."""
    from sect.lib import look as LK
    LOOK = LK.LOOK
    vs = sc.view_settings
    vs.view_transform = LOOK["view_transform"]
    vs.look = LOOK["look"]
    vs.exposure = BW.POST_EXPOSURE
    vs.gamma = 1.0
    sc.display_settings.display_device = "sRGB"
    ng = bpy.data.node_groups.new("preview.bake_grade", "CompositorNodeTree")
    ng.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    N, Lk = ng.nodes, ng.links
    rl = N.new("CompositorNodeRLayers")
    rl.scene = sc
    grade = N.new("CompositorNodeColorBalance")
    LK._inp(grade, "Type").default_value = "Offset/Power/Slope (ASC-CDL)"
    grade.inputs["Factor"].default_value = 1.0
    sl, of, pw = LOOK["grade_slope"], LOOK["grade_offset"], LOOK["grade_power"]
    for sock in grade.inputs:
        if sock.identifier == "Color Slope":
            sock.default_value = (sl[0], sl[1], sl[2], 1.0)
        elif sock.identifier == "Color Offset":
            sock.default_value = (of[0], of[1], of[2], 1.0)
        elif sock.identifier == "Color Power":
            sock.default_value = (pw[0], pw[1], pw[2], 1.0)
    Lk.new(rl.outputs["Image"], grade.inputs["Image"])
    cc = N.new("CompositorNodeColorCorrection")
    for sock in cc.inputs:
        if sock.identifier == "Highlights Saturation":
            sock.default_value = LOOK["grade_highlight_saturation"]
        elif sock.identifier == "Shadows Saturation":
            sock.default_value = LOOK["grade_shadow_saturation"]
    Lk.new(grade.outputs["Image"], cc.inputs["Image"])
    hs = N.new("CompositorNodeHueSat")
    hs.inputs["Saturation"].default_value = BW.POST_SAT
    Lk.new(cc.outputs["Image"], hs.inputs["Image"])
    go = N.new("NodeGroupOutput")
    Lk.new(hs.outputs["Image"], go.inputs["Image"])
    sc.compositing_node_group = ng
    sc.render.use_compositing = True


def bake_light_setup(sc, spec):
    """The scene lit as the bake lights it (preview_r59.bake_light_setup): set_bake_light, night_scene, hide_for_bake,
    bake_lighting, the bake's bounces and indirect clamp, graded as the bake's post grades. In memory only."""
    if spec != "day":
        BW.set_bake_light(spec)
    info = BW.night_scene(sc)
    n = BW.hide_for_bake(sc)
    BW.bake_lighting(sc)
    B = BW.BAKE_BOUNCES
    sc.cycles.max_bounces = B["max"]
    sc.cycles.diffuse_bounces = B["diffuse"]
    sc.cycles.glossy_bounces = B["glossy"]
    sc.cycles.transmission_bounces = B["transmission"]
    sc.cycles.transparent_max_bounces = B["transparent"]
    sc.cycles.sample_clamp_indirect = BW.BAKE_CLAMP_INDIRECT
    bake_view(sc)
    log("bake light %r: night %s, %d more objects hidden as the bake hides them; bounces %s, clamp %.1f; light %s" % (
        spec, "on" if info else "off", n, B, BW.BAKE_CLAMP_INDIRECT, json.dumps(BW.BAKE_LIGHT)))


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


def main():
    a = args()
    sc = bpy.context.scene
    src = bpy.data.objects.get(EW.CAMERA)
    root = bpy.data.objects.get("abode.root")
    if src is None or root is None:
        raise RuntimeError("no %s or abode.root" % EW.CAMERA)
    os.makedirs(a.out, exist_ok=True)
    views = [v.strip() for v in a.views.split(",") if v.strip()]
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    log("volume objects hidden", hide_volumes(sc))
    if a.bake_light != "film":
        bake_light_setup(sc, a.bake_light)
    notch = root.matrix_world @ Vector((AB.FALL_X, AB._y_chute(), AB._lip_z() + 3.0))
    data = src.data.copy()
    cam = bpy.data.objects.new(CAM, data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    pre = "r62" + ("_" + a.tag if a.tag else "")
    made = []
    try:
        for view in views:
            base = view[:-5] if view.endswith("_zoom") else view
            if base not in PN.VIEWS:
                log("WARN unknown view", view)
                continue
            frame, yaw, pitch = PN.VIEWS[base]
            Mw = PN.page_view(sc, src, frame, yaw, pitch)
            for k in ("lens", "sensor_width", "sensor_height", "sensor_fit", "shift_x", "shift_y", "clip_start",
                      "clip_end"):
                setattr(data, k, getattr(src.data, k))
            if view.endswith("_zoom"):
                eye = Mw.translation.copy()
                rot = (notch - eye).to_track_quat('-Z', 'Y').to_matrix()
                M = rot.to_4x4()
                M.translation = eye
                cam.matrix_world = M
                data.lens = src.data.lens * ZOOM
                info = "aimed at the notch %s, lens %.1f mm (x%.0f), %.1f m off" % (
                    [round(c, 1) for c in notch], data.lens, ZOOM, (notch - eye).length)
            else:
                cam.matrix_world = Mw
                info = "page view yaw %.1f pitch %.1f, lens %.1f mm" % (yaw, pitch, data.lens)
            sc.render.filepath = os.path.join(a.out, "%s_%s.png" % (pre, view))
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            made.append(sc.render.filepath)
            log("wrote", sc.render.filepath, "frame", sc.frame_current, info, "%.1f s" % (time.time() - t0))
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(data)
    log("done", len(made), "stills; the .blend was not saved")


if __name__ == "__main__":
    main()
