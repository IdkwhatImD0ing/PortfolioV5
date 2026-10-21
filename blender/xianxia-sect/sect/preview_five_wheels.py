"""Cycles previews of the Golden Wheel Lama's five wheels (sect/areas/forge.py _five_wheels) in a .blend patched by
sect/patch_five_wheels.py, on the GPU at low samples. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_five_wheels.py [-- --samples 24]

Writes out/preview/five_wheels_<shot>.png (the wrapper copies new files under out/ back to the PC):
    hold      chase.cam at the forge hold (352), 1600x900: the stand sits low in the left corner
    pass      chase.cam at frame 392 (the pass, 380-398), 1600x900: the payoff, lower frame
    hold_zoom / pass_zoom   the same frames cropped round the stand at the real pixel size (1600x900 frame), then
              blown up 4x nearest-neighbour: how the item reads on the page
    stand     the whole stand from the hold camera's side, 3/4 front
    gold      gold and silver wheels close up: band, petals, windows and balls, the honed edge
    side      from the gold end, low: the lean against the rail and the cradles
--bakelook: render every material the way bake_web bakes it (Metallic and Transmission unlinked and 0, so metals show
their base colour; file names get '_bk'), closer to the page than Cycles' reflective metals. --shots hold,gold,pass_zoom:
only those. --tag x: file names five_wheels_<tag>_<shot>.png. Lighting is the hold frame's for the
close-ups; the flyer and (unless --volumes) volume objects are hidden. Does not save the .blend.
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
from sect.areas import forge as F  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
CAM = "preview.five_wheels.cam"
HOLD = 352
PASS = 392
# close-ups in the stand's frame (forge.five_wheels: x along the row, gold at +x, front -Y): camera, target, lens, res
SHOTS = (
    ("stand", (1.2, -6.9, 3.0), (0.1, 0.0, 1.15), 35.0, (1280, 800)),
    ("gold", (2.15, -1.95, 1.55), (1.45, 0.0, 1.22), 50.0, (1000, 800)),
    ("side", (3.6, -1.7, 1.0), (0.6, 0.05, 1.2), 35.0, (1100, 800)),
)


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--volumes", action="store_true", help="keep volume objects (slower)")
    ap.add_argument("--shots", default="", help="comma list of shots (hold, pass, stand, gold, side)")
    ap.add_argument("--tag", default="", help="file name tag")
    ap.add_argument("--bakelook", action="store_true", help="metals as base colour, like the bake")
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


def bake_look():
    """bake_web.rewrite_material's metal rule on every material (not saved): a bake keeps only diffuse light, so it
    bakes metals as their base colour."""
    n = 0
    for m in bpy.data.materials:
        if m.node_tree is None:
            continue
        for nd in m.node_tree.nodes:
            if nd.bl_idname != "ShaderNodeBsdfPrincipled":
                continue
            for nm in ("Metallic", "Transmission Weight"):
                sock = nd.inputs.get(nm)
                if sock is None:
                    continue
                for lk in list(sock.links):
                    m.node_tree.links.remove(lk)
                sock.default_value = 0.0
            n += 1
    return n


def render(sc, name, res, tag):
    sc.render.resolution_x, sc.render.resolution_y = res
    path = os.path.join(OUT, "five_wheels_%s%s.png" % (tag + "_" if tag else "", name))
    sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    log("wrote", path, "%.1f s" % (time.time() - t0))


def stand_border(sc, cam, emp, pad=0.35):
    """Render region (x0, x1, y0, y1 in 0..1) round the stand and wheels in ``cam``'s view, padded by ``pad``."""
    pts = []
    for ob in emp.children:
        if ob.type == 'MESH':
            pts += [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    ndc = [world_to_camera_view(sc, cam, p) for p in pts]
    x0, x1 = min(p.x for p in ndc), max(p.x for p in ndc)
    y0, y1 = min(p.y for p in ndc), max(p.y for p in ndc)
    dx, dy = (x1 - x0) * pad, (y1 - y0) * pad
    return (max(0.0, x0 - dx), min(1.0, x1 + dx), max(0.0, y0 - dy), min(1.0, y1 + dy))


def blow_up(path, k=4):
    """Scale a PNG up k times, nearest-neighbour, in place (Blender's Image.scale would blur the real pixels)."""
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    src = [0.0] * (w * h * 4)
    img.pixels.foreach_get(src)
    out = [0.0] * (w * k * h * k * 4)
    for y in range(h * k):
        sy = (y // k) * w
        row = y * w * k
        for x in range(w * k):
            si = (sy + x // k) * 4
            di = (row + x) * 4
            out[di:di + 4] = src[si:si + 4]
    big = bpy.data.images.new(img.name + ".big", w * k, h * k, alpha=True)
    big.pixels.foreach_set(out)
    big.filepath_raw = path
    big.file_format = 'PNG'
    big.save()
    bpy.data.images.remove(img)
    bpy.data.images.remove(big)
    return w, h


def zoom(sc, cam, emp, name, frame, tag):
    sc.frame_set(frame)
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    x0, x1, y0, y1 = stand_border(sc, cam, emp)
    r = sc.render
    r.use_border, r.use_crop_to_border = True, True
    r.border_min_x, r.border_max_x, r.border_min_y, r.border_max_y = x0, x1, y0, y1
    try:
        render(sc, name, (1600, 900), tag)
    finally:
        r.use_border, r.use_crop_to_border = False, False
    path = sc.render.filepath
    w, h = blow_up(path)
    log("blew up", path, "from %dx%d (frame pixels x %.0f..%.0f, y %.0f..%.0f from the top)" % (
        w, h, x0 * 1600, x1 * 1600, (1 - y1) * 900, (1 - y0) * 900))


def look_at(ob, loc, target):
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()


def main():
    a = args()
    want = set(a.shots.split(",")) if a.shots else None
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    emp = bpy.data.objects.get(F.FW_NAME)
    if emp is None:
        raise RuntimeError("%s not found - run sect/patch_five_wheels.py first" % F.FW_NAME)
    for ob in sorted(emp.children, key=lambda o: o.name):
        n = len(ob.data.polygons)
        lt = [0] * n
        ob.data.polygons.foreach_get("loop_total", lt)
        log(ob.name, "tris", sum(lt) - 2 * n, "slots", [s.material.name if s.material else None for s in ob.material_slots])
    setup_cycles(sc, a.samples)
    if a.bakelook:
        log("bake look: principled nodes set to metallic 0:", bake_look())
        a.tag = (a.tag + "_" if a.tag else "") + "bk"
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    chase = bpy.data.objects.get(EW.CAMERA)
    if chase is None:
        raise RuntimeError(EW.CAMERA + " not found")
    sc.camera = chase
    for name, f in (("hold", HOLD), ("pass", PASS)):
        if want is None or name in want:
            sc.frame_set(f)
            render(sc, name, (1600, 900), a.tag)
        if want is None or name + "_zoom" in want:
            zoom(sc, chase, emp, name + "_zoom", f, a.tag)
    sc.frame_set(HOLD)
    cd = bpy.data.cameras.new(CAM)
    cd.clip_start, cd.clip_end = 0.05, 5000.0
    cam = bpy.data.objects.new(CAM, cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    M = emp.matrix_world
    try:
        for name, loc, target, lens, res in SHOTS:
            if want is not None and name not in want:
                continue
            cd.lens = lens
            look_at(cam, M @ Vector(loc), M @ Vector(target))
            render(sc, name, res, a.tag)
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(cd)
    log("done; the .blend was not saved")


main()
