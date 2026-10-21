"""Cycles previews of the six Holy Fire Tokens 圣火令 (sect/areas/scroll.py TOKENS: scroll.slips + scroll.slip_caps under
the Empty scroll.slip_stack) in out/sect_chase.blend, on the GPU at low samples. Run on the cloud box after
patch_holy_fire_tokens.py:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_holy_fire_tokens.py [-- --samples 24]

Writes out/preview/holy_fire_tokens_*.png (the wrapper copies new files under out/ back to the PC):
    holy_fire_tokens_hold.png        chase.cam at the scroll hold (export_web full profile, 1103), 960 x 540
    holy_fire_tokens_hold_crop.png   the same camera at the site's 1600 x 900, cropped to the stack (compare with the
                                     page screenshot .playwright-mcp/bake2_1103_high.png)
    holy_fire_tokens_pass_crop.png   chase.cam at frame 1112 (the close pass), 1600 x 900, cropped to the stack
    holy_fire_tokens_near_crop.png   chase.cam at frame 1147 (the nearest path frame, ~15 m), cropped
    holy_fire_tokens_stack.png       the whole stack from the hold side, three-quarter, ~8 m
    holy_fire_tokens_fire.png        the top token's middle: the flame window and its white-gold core
    holy_fire_tokens_end.png         the top token's end panel: border, dotted line, the arabesque pair
    holy_fire_tokens_edge.png        low along the stack's front: the graded lengths, chamfers and molten seams
Everything renders at the hold frame's lighting with the flyer hidden; volume objects (cloud banks, haze) are hidden
for speed unless --volumes. --shots hold,stack,...: only those. Does not save the .blend.
"""
import argparse
import os
import sys
import time

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402
from sect.areas import scroll as SC  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
PREFIX = "holy_fire_tokens"
STACK = SC.K + ".slip_stack"
OBJECTS = (SC.K + ".slips", SC.K + ".slip_caps")
CAM = "preview.holy_fire_tokens.cam"
PASS_FRAME, NEAR_FRAME = 1112, 1147
SITE_RES = (1600, 900)
ALL_SHOTS = ("hold", "hold_crop", "pass_crop", "near_crop", "stack", "fire", "end", "edge")


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--volumes", action="store_true", help="keep volume objects (slower)")
    ap.add_argument("--shots", default="", help="comma list of shots (default all): " + ",".join(ALL_SHOTS))
    ap.add_argument("--tag", default="", help="suffix for the file names (before / after rounds)")
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
        return int(next(a["holdFrame"] for a in EW.AREAS if a["id"] == "scroll"))
    except Exception as e:  # noqa: BLE001
        log("WARN hold frame from the timeline failed (%s); using 1103" % e)
        return 1103


def render(sc, name, res, tag, border=None):
    sc.render.resolution_x, sc.render.resolution_y = res
    if border is not None:
        sc.render.use_border = True
        sc.render.use_crop_to_border = True
        sc.render.border_min_x, sc.render.border_min_y, sc.render.border_max_x, sc.render.border_max_y = border
    else:
        sc.render.use_border = False
    path = os.path.join(OUT, "%s_%s%s.png" % (PREFIX, name, tag))
    sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    sc.render.use_border = False
    log("wrote", path, "%.1f s" % (time.time() - t0))


def look_at(ob, loc, target):
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()


def stack_border(sc, cam, pts, margin=0.35):
    """Render region (min x, min y, max x, max y in 0..1) round the projected points, grown by ``margin`` of its size."""
    ndc = [world_to_camera_view(sc, cam, p) for p in pts]
    ndc = [v for v in ndc if v.z > 0]
    if not ndc:
        return None
    x0, x1 = min(v.x for v in ndc), max(v.x for v in ndc)
    y0, y1 = min(v.y for v in ndc), max(v.y for v in ndc)
    w, h = max(x1 - x0, 0.02), max(y1 - y0, 0.02)
    x0, x1, y0, y1 = x0 - margin * w, x1 + margin * w, y0 - margin * h, y1 + margin * h
    log("stack on screen: x %.3f..%.3f y %.3f..%.3f (of 1); %.0f x %.0f px at %d x %d" % (
        x0, x1, 1 - y1, 1 - y0, (x1 - x0) * sc.render.resolution_x, (y1 - y0) * sc.render.resolution_y,
        sc.render.resolution_x, sc.render.resolution_y))
    box = (max(0.0, x0), max(0.0, y0), min(1.0, x1), min(1.0, y1))
    if box[2] - box[0] < 0.01 or box[3] - box[1] < 0.01:
        log("the stack is off screen")
        return None
    return box


def main():
    a = args()
    shots = a.shots.split(",") if a.shots else ALL_SHOTS
    tag = ("_" + a.tag) if a.tag else ""
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    hold = hold_frame()
    stack = bpy.data.objects.get(STACK)
    if stack is None:
        raise RuntimeError(STACK + " not found")
    for nm in OBJECTS:
        ob = bpy.data.objects.get(nm)
        if ob is None:
            raise RuntimeError(nm + " not found")
        n = len(ob.data.polygons)
        lt = [0] * n
        ob.data.polygons.foreach_get("loop_total", lt)
        log(nm, "mesh", ob.data.name, "tris", sum(lt) - 2 * n, "slots",
            [s.material.name if s.material else None for s in ob.material_slots], "glow", ob.get("glow"))
    if all(s.material is None or "jade" not in s.material.name for s in bpy.data.objects[OBJECTS[0]].material_slots):
        log("tokens in place")
    else:
        log("WARN scroll.slips still has the jade material - run sect/patch_holy_fire_tokens.py first")
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    chase = bpy.data.objects.get(EW.CAMERA)
    if chase is None:
        raise RuntimeError(EW.CAMERA + " not found")
    sc.frame_set(hold)
    M = stack.matrix_world.copy()
    # the stack's corners (token frame boxes) for the crop regions
    pts = []
    for i, (L, W) in enumerate(SC.TOKENS):
        f = SC.token_xf(i)
        for sx in (-1, 1):
            for sy in (-1, 1):
                pts.append(M @ Vector(f((sx * L / 2, sy * W / 2, 0.0))))
    # the real camera: hold, close pass, nearest frame
    sc.camera = chase
    for name, f, res, crop in (("hold", hold, (960, 540), False), ("hold_crop", hold, SITE_RES, True),
                               ("pass_crop", PASS_FRAME, SITE_RES, True), ("near_crop", NEAR_FRAME, SITE_RES, True)):
        if name not in shots:
            continue
        sc.frame_set(f)
        sc.render.resolution_x, sc.render.resolution_y = res
        border = stack_border(sc, chase, pts) if crop else None
        if crop and border is None:
            log(name, "frame", f, "skipped: the stack is not in this camera's view")
            continue
        log(name, "frame", f, "camera at", tuple(round(c, 1) for c in chase.matrix_world.translation),
            "distance to the stack %.1f m" % (chase.matrix_world.translation - M.translation).length)
        render(sc, name, res, tag, border)
    # close-ups at the hold frame's lighting, from the hold side (-Y of the stack, above it)
    sc.frame_set(hold)
    cd = bpy.data.cameras.new(CAM)
    cd.clip_start, cd.clip_end = 0.05, 5000.0
    cam = bpy.data.objects.new(CAM, cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    top = len(SC.TOKENS) - 1
    ft = SC.token_xf(top)
    Lt, Wt = SC.TOKENS[top]
    lay = SC.token_layout(Lt, Wt)
    h = SC.TOKEN_T / 2
    x_end = (SC.FIRE_LEN * Lt / 2 + lay["a"]) / 2 + 0.05           # middle of the +x end panel
    closeups = (
        # name, target (stack frame), camera (stack frame), lens, resolution
        ("stack", (0.0, 0.0, 0.8), (-3.2, -7.2, 3.6), 50.0, (1200, 800)),
        ("fire", ft((0.15, 0.0, h)), ft((0.15, -0.55, h + 1.45)), 50.0, (1200, 700)),
        ("end", ft((x_end, 0.0, h)), ft((x_end - 0.12, -0.25, h + 0.95)), 50.0, (1000, 800)),
        ("edge", (0.0, -0.4, 0.7), (2.8, -4.6, 0.95), 40.0, (1200, 700)),
    )
    try:
        for name, target, loc, lens, res in closeups:
            if name not in shots:
                continue
            cd.lens = lens
            look_at(cam, M @ Vector(loc), M @ Vector(target))
            render(sc, name, res, tag)
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(cd)
    log("done; the .blend was not saved")


main()
