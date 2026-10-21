"""Cycles previews of the Ming Sect's holy-fire altars 圣火坛 (sect/areas/mission.py _holy_fire) in a .blend patched
by sect/patch_holy_fire_altar.py, on the GPU at low samples. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_holy_fire_altar.py [-- --samples 24 --quick]

Writes out/preview/holy_fire_*.png (the wrapper copies new files under out/ back to the PC):
    holy_fire_hold.png      chase.cam at the mission hold frame (export_web full profile, 619)
    holy_fire_flight.png    chase.cam at frame 634, where the flight passes the east altar (~46 m)
    holy_fire_full.png      the east altar whole, three-quarter from the hold camera's side
    holy_fire_crown.png     crown, merlons, gold rim and relief, ember bed and the flame crown
    holy_fire_base.png      stepped base, shaft, mid-band clouds and the plinth steps
    holy_fire_top.png       down into the bowl: ember bed and ash lumps under the flame
    holy_fire_west.png      the west altar whole, from its own camera side (the mirror image)
Everything renders at the hold frame's lighting with the flyer hidden; volume objects (cloud banks, haze) are hidden
for speed unless --volumes. --quick: hold and full only; --shots a,b: only those; --no-cams: skip hold and flight.
Session-only comparisons (suffix on the file names): --bakelike renders metals as their base colour, the way
bake_web bakes them (the web look; Cycles' metal reflections make bronze look like gold); --altar-mat <name> tries
another registered material on the .altar meshes; --light-scale <k> scales the two lights (0 = off).
Logs where the east altar's foot and flame tip land in the hold frame (pixels in a 1600 px wide frame, the site's
screenshot size). Does not save the .blend.
"""
import argparse
import math
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
from sect.areas import mission as M  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
PREFIX = "holy_fire"
FLIGHT_FRAME = 634
CAM = "preview.holy_fire.cam"
EAST, WEST = M.K + ".holy_fire", M.K + ".holy_fire.001"
# close-ups in the altar Empty's frame: (name, empty, target (x, y, z), distance toward the hold camera's side,
# sideways offset (to the camera's right), height of the camera, lens mm, resolution)
SHOTS = (
    ("full", EAST, (0.0, 0.0, 2.45), 13.0, 3.0, 3.6, 40.0, (900, 1100)),
    ("crown", EAST, (0.0, 0.0, 3.75), 4.6, 1.2, 4.4, 40.0, (1000, 1000)),
    ("base", EAST, (0.0, 0.0, 1.35), 5.2, -1.6, 1.9, 35.0, (1000, 1000)),
    ("top", EAST, (0.0, 0.0, 3.3), 2.6, 0.6, 6.4, 30.0, (1000, 1000)),
    ("west", WEST, (0.0, 0.0, 2.45), 13.0, -3.0, 3.6, 40.0, (900, 1100)),
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
    ap.add_argument("--no-cams", action="store_true", help="skip the hold and flight renders")
    ap.add_argument("--bakelike", action="store_true",
                    help="metals as their base colour, as bake_web bakes them (files get a _bake suffix)")
    ap.add_argument("--altar-mat", default="", help="try another registered material on the .altar meshes "
                    "(this session only; files get a _<name> suffix)")
    ap.add_argument("--light-scale", type=float, default=1.0,
                    help="scale the two holy-fire lights for this session (0 = off; files get a _lightX suffix)")
    return ap.parse_args(argv)


def bakelike_metals(objs):
    """bake_web's lightmap convention for the altars' materials: Metallic 0, so bronze and gold render as their
    painted base colour the way the web shows them. Only this session (the .blend is not saved)."""
    mats = {s.material for o in objs for s in o.material_slots if s.material is not None}
    n = 0
    for m in mats:
        if m.node_tree is None:
            continue
        for nd in m.node_tree.nodes:
            if nd.bl_idname == "ShaderNodeBsdfPrincipled":
                sock = nd.inputs.get("Metallic")
                for l in list(sock.links):
                    m.node_tree.links.remove(l)
                sock.default_value = 0.0
                n += 1
    return sorted(m.name for m in mats), n


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
        return int(next(a["holdFrame"] for a in EW.AREAS if a["id"] == "mission"))
    except Exception as e:  # noqa: BLE001
        log("WARN hold frame from the timeline failed (%s); using 619" % e)
        return 619


SUFFIX = []


def render(sc, name, res):
    sc.render.resolution_x, sc.render.resolution_y = res
    path = os.path.join(OUT, "%s_%s%s.png" % (PREFIX, name, "".join(SUFFIX)))
    sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    log("wrote", path, "%.1f s" % (time.time() - t0))


def look_at(ob, loc, target):
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()


def report_hold(sc, cam, east):
    """Where the east altar's foot and flame tip land in the hold frame, in a 1600 x 900 frame."""
    M_ = east.matrix_world
    for nm, p in (("foot", (0.0, 0.0, 0.0)), ("rim", (0.0, 0.0, M.HF_RIM_Z)),
                  ("flame tip", (0.0, 0.0, M.HF_FLAME_Z + M.HF_FLAME_H))):
        ndc = world_to_camera_view(sc, cam, M_ @ Vector(p))
        log("hold", nm, "at px (%.0f, %.0f) of 1600 x 900, depth %.1f m" % (ndc.x * 1600, (1 - ndc.y) * 900, ndc.z))


def main():
    a = args()
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    hold = hold_frame()
    empties = {}
    for nm in (EAST, WEST):
        ob = bpy.data.objects.get(nm)
        if ob is None:
            raise RuntimeError("%s not found - run sect/patch_holy_fire_altar.py first" % nm)
        empties[nm] = ob
        for ch in sorted(ob.children, key=lambda o: o.name):
            if ch.type == 'MESH':
                n = len(ch.data.polygons)
                lt = [0] * n
                ch.data.polygons.foreach_get("loop_total", lt)
                log(ch.name, "tris", sum(lt) - 2 * n, "slots", [s.material.name if s.material else None
                                                                for s in ch.material_slots])
    for nm in (M.K + ".holy_fire_light", M.K + ".holy_fire_light.001"):
        lo = bpy.data.objects.get(nm)
        if lo is not None and a.light_scale != 1.0:
            lo.data.energy *= a.light_scale
        log(nm, "missing" if lo is None else "%s %.0f W shadow %s" % (lo.data.type, lo.data.energy, lo.data.use_shadow))
    if a.light_scale != 1.0:
        SUFFIX.append("_light%g" % a.light_scale)
    if a.altar_mat:
        from sect.lib import materials as MAT
        mat = MAT.get(a.altar_mat)
        for e in empties.values():
            for c in e.children:
                if c.name.endswith(".altar"):
                    c.data.materials[0] = mat
        SUFFIX.append("_" + a.altar_mat)
        log("altar material for this session:", mat.name)
    if a.bakelike:
        SUFFIX.append("_bake")
        log("bake-like metals", *bakelike_metals([c for e in empties.values() for c in e.children]))
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    chase = bpy.data.objects.get(EW.CAMERA)
    if chase is None:
        raise RuntimeError(EW.CAMERA + " not found")
    sc.camera = chase
    sc.frame_set(hold)
    report_hold(sc, chase, empties[EAST])
    for name, f in (() if a.no_cams else (("hold", hold), ("flight", FLIGHT_FRAME))):
        sc.frame_set(f)
        render(sc, name, (1280, 720))
    sc.frame_set(hold)
    cd = bpy.data.cameras.new(CAM)
    cd.clip_start, cd.clip_end = 0.05, 5000.0
    cam = bpy.data.objects.new(CAM, cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    shots = SHOTS[:1] if a.quick else SHOTS
    if a.shots:
        shots = [s_ for s_ in SHOTS if s_[0] in a.shots.split(",")]
    try:
        for name, emp, target, dist, side, height, lens, res in shots:
            e = empties[emp]
            mirror = -1.0 if emp == WEST else 1.0
            # toward the hold camera in the Empty's frame (canonical -y turned by HF_FRONT, mirrored for the west)
            fx, fy = math.sin(M.HF_FRONT) * mirror, -math.cos(M.HF_FRONT)
            rx, ry = -fy, fx                         # to the camera's right when it looks back at the altar
            loc = (target[0] + fx * dist + rx * side * mirror, target[1] + fy * dist + ry * side * mirror, height)
            cd.lens = lens
            look_at(cam, e.matrix_world @ Vector(loc), e.matrix_world @ Vector(target))
            render(sc, name, res)
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(cd)
    log("done; the .blend was not saved")


main()
