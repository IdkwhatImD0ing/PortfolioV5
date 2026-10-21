"""Cycles previews of the mission wall's role boards (sect/areas/mission.py _role_boards) in a .blend patched by
sect/patch_r5_cards.py, on the GPU at low samples. Run on the cloud box on a patched copy (the .blend is not saved):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r5_cards.py [-- --samples 24 --shots a,b]

Writes out/preview/cards_*.png (the wrapper copies new files under out/ back to the PC):
    cards_hold.png        chase.cam at the mission hold frame (619), 1280 x 720
    cards_hold_px.png     the same frame at the site's 1600 x 900, cropped to the wall: the boards at the pixel size
                          a visitor sees them (the readability test)
    cards_wall.png        the whole wall face on from the axis walk
    cards_board.png       one board (RingCentral) close, a little from the side
    cards_low.png         the lower row (SlugLoop, X-Camp) close
    cards_corner.png      the west lower corner: rail into the post, brackets, wooden tablets
    cards_top.png         the top row's cords and hooks under the beam, from below
Logs, per board, where its employer line lands in the 1600 x 900 hold frame and how tall its capitals are in pixels.
--suffix <s> adds _<s> to the file names; --no-hold skips the two hold renders. Volume objects (cloud banks, haze) are
hidden for speed unless --volumes.
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
from sect.areas import mission as MI  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
PREFIX = "cards"
CAM = "preview.cards.cam"
# close-ups in the wall Empty's frame: (name, camera location, target, lens mm, resolution)
SHOTS = (
    ("wall", (0.0, -27.0, 5.0), (0.0, 0.0, 4.4), 40.0, (1280, 720)),
    ("board", (5.2, -8.5, 4.6), (2.9, -0.3, 5.75), 40.0, (1280, 720)),
    ("low", (-2.6, -9.5, 2.4), (-4.2, -0.3, 2.9), 40.0, (1280, 720)),
    ("corner", (-6.5, -6.0, 2.2), (-10.6, 0.0, 2.9), 35.0, (1000, 1000)),
    ("top", (-4.0, -3.2, 4.0), (-5.8, -0.3, 6.9), 35.0, (1000, 1000)),
)
HOLD_CROP = (0.0, 0.56, 0.22, 0.62)       # border of the 1600 x 900 hold frame: x0, x1, y0, y1 (Blender: y up)
SUFFIX = []


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--volumes", action="store_true", help="keep volume objects (slower)")
    ap.add_argument("--shots", default="", help="comma list of close-up shot names (default all)")
    ap.add_argument("--no-hold", action="store_true", help="skip the hold renders")
    ap.add_argument("--suffix", default="")
    return ap.parse_args(argv)


def setup_cycles(sc, samples):
    """preview_holy_fire_altar's setup: OptiX, then CUDA, then CPU; denoised low-sample stills."""
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
        return int(next(a["holdFrame"] for a in EW.AREAS if a["id"] == "mission"))
    except Exception as e:  # noqa: BLE001
        log("WARN hold frame from the timeline failed (%s); using 619" % e)
        return 619


def render(sc, name, res, border=None):
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.use_border = border is not None
    sc.render.use_crop_to_border = border is not None
    if border is not None:
        sc.render.border_min_x, sc.render.border_max_x, sc.render.border_min_y, sc.render.border_max_y = border
    path = os.path.join(OUT, "%s_%s%s.png" % (PREFIX, name, "".join(SUFFIX)))
    sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    log("wrote", path, "%.1f s" % (time.time() - t0))


def look_at(ob, loc, target):
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()


def report_hold(sc, cam, wall):
    """Employer line of each board in the 1600 x 900 hold frame: its centre and its capital height in pixels."""
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    scale = MI.role_text_scale()
    cap = MI._mesh_box2(MI._line_mesh("H", MI.ROLE_FONT))[3] * scale
    block = cap + MI.ROLE_LINE_GAP + MI.ROLE_YEAR_CAP
    for i, x, z in MI.role_slots():
        zc = z - MI.ROLE_CORD - MI.ROLE_H / 2
        base = zc + block / 2 - cap
        y = MI.ROLE_Y - MI.ROLE_T / 2
        p0 = world_to_camera_view(sc, cam, wall.matrix_world @ Vector((x, y, base)))
        p1 = world_to_camera_view(sc, cam, wall.matrix_world @ Vector((x, y, base + cap)))
        log("hold role:%d %-12s at px (%.0f, %.0f), caps %.1f px tall" % (
            i, MI.ROLE_BOARDS[i][0], p0.x * 1600, (1 - p0.y) * 900, (p1.y - p0.y) * 900))


def main():
    a = args()
    if a.suffix:
        SUFFIX.append("_" + a.suffix)
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    wall = bpy.data.objects.get(MI.K + ".wall")
    tab = bpy.data.objects.get(MI.K + ".role_tablet")
    if wall is None or tab is None or not tab.instance_collection.name.startswith("props.mission.role."):
        raise RuntimeError("mission wall not patched: run sect/patch_r5_cards.py on this copy first")
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    hold = hold_frame()
    chase = bpy.data.objects.get(EW.CAMERA)
    sc.camera = chase
    sc.frame_set(hold)
    report_hold(sc, chase, wall)
    if not a.no_hold:
        render(sc, "hold", (1280, 720))
        render(sc, "hold_px", (1600, 900), border=HOLD_CROP)
    cd = bpy.data.cameras.new(CAM)
    cd.clip_start, cd.clip_end = 0.05, 5000.0
    cam = bpy.data.objects.new(CAM, cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    shots = [s_ for s_ in SHOTS if not a.shots or s_[0] in a.shots.split(",")]
    try:
        for name, loc, target, lens, res in shots:
            cd.lens = lens
            look_at(cam, wall.matrix_world @ Vector(loc), wall.matrix_world @ Vector(target))
            render(sc, name, res)
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(cd)
    log("done; the .blend was not saved")


main()
