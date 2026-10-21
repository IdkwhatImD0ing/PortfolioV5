"""Cycles stills of the arena's Heavy Iron Sword 玄铁重剑 (sect/areas/arena.py, heavy_sword_meshes) in
out/sect_chase.blend, on the GPU at low samples (~1 min). Run on the cloud box after patch_heavy_iron_sword.py:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_heavy_iron_sword.py [-- --samples 24]

Writes out/preview/heavy_sword_<tag>_*.png (the wrapper copies new files under out/ back to the PC):
    hold.png        chase.cam at the arena's hold frame (export_web full profile, 516): the sword centre frame
    approach.png    chase.cam at frame 458: the island from below, the round tip under it
    pass.png        chase.cam at frame 560: the close pass off the sword's west side (it leaves the frame by 569)
    hilt.png        guard, wrapped grip, disc pommel and cord, three-quarter from the front-west
    blade.png       the blade above the island, front-west (light rims, facets, ember seams)
    edge.png        close-up of the west edge and the front face (rounded blunt edge, hammer facets, a seam)
    tip.png         the half-dome tip, from behind/below the island
Close-ups are framed in the sword's own frame (the Empty 'arena.sword') at the hold frame's lighting with the flyer
hidden; volume objects (cloud banks, haze) are hidden for speed unless --volumes. --shots hilt,tip: only those;
--no-cams: skip the chase-camera frames; --tag: file name tag (default 'r'). --bakelike: render every material with
Metallic and Transmission at 0, as bake_web bakes them (the web shows the base colours lit diffusely: iron dark grey,
the 'edge' rims lighter), in memory only. Does not save the .blend.
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
from sect.areas import arena as A  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
PREFIX = "heavy_sword"
CAM_FRAMES = (("approach", 458), ("pass", 560))
CAM = "preview.heavy_sword.cam"
SWORD = A.K + ".sword"
# close-ups in the sword's frame: name, target (x, y, z), camera position (x, y, z), lens mm, resolution
SHOTS = (
    ("hilt", (0.3, -0.5, 7.6), (-7.5, -17.0, 9.5), 50.0, (720, 960)),
    ("blade", (0.0, -0.9, -12.0), (-15.0, -26.0, -6.0), 40.0, (720, 960)),
    ("edge", (-2.2, -0.8, -9.5), (-8.0, -8.5, -7.5), 50.0, (800, 800)),
    ("tip", (0.0, 0.0, -62.5), (-14.0, 24.0, -58.0), 40.0, (800, 800)),
)


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--volumes", action="store_true", help="keep volume objects (slower)")
    ap.add_argument("--shots", default="", help="comma list of close-up shot names (default all)")
    ap.add_argument("--no-cams", action="store_true", help="skip the chase-camera frames")
    ap.add_argument("--tag", default="r", help="file name tag")
    ap.add_argument("--bakelike", action="store_true", help="Metallic / Transmission 0 everywhere, as the bake")
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


def bakelike():
    """bake_web.bake_material's Principled rule, in memory: Metallic and Transmission Weight unlinked and 0."""
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


def hold_frame():
    try:
        EW.use_profile("full")
        return int(next(a["holdFrame"] for a in EW.AREAS if a["id"] == "arena"))
    except Exception as e:  # noqa: BLE001
        log("WARN hold frame from the timeline failed (%s); using 516" % e)
        return 516


def render(sc, tag, name, res):
    sc.render.resolution_x, sc.render.resolution_y = res
    path = os.path.join(OUT, "%s_%s_%s.png" % (PREFIX, tag, name))
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
    sroot = bpy.data.objects.get(SWORD)
    if sroot is None:
        raise RuntimeError(SWORD + " not found")
    for part in A.HS_PARTS:
        ob = bpy.data.objects.get(A.K + "." + part)
        if ob is None:
            raise RuntimeError("%s.%s not found" % (A.K, part))
        if ob.data.get("sect_heavy_sword") != part:
            log("WARN", ob.name, "has mesh", ob.data.name, "- run sect/patch_heavy_iron_sword.py first")
        n = len(ob.data.polygons)
        lt = [0] * n
        ob.data.polygons.foreach_get("loop_total", lt)
        log(part, ob.name, "mesh", ob.data.name, "tris", sum(lt) - 2 * n,
            "slots", [s.material.name if s.material else None for s in ob.material_slots])
    log("plaque", "present" if bpy.data.objects.get(A.K + ".plaque_sword") else "removed")
    setup_cycles(sc, a.samples)
    if a.bakelike:
        log("bake-like: Principled BSDFs set non-metallic", bakelike())
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    chase = bpy.data.objects.get(EW.CAMERA)
    if chase is None:
        raise RuntimeError(EW.CAMERA + " not found")
    sc.camera = chase
    for name, f in (() if a.no_cams else (("hold", hold),) + CAM_FRAMES):
        sc.frame_set(f)
        render(sc, a.tag, name, (1280, 720))
    sc.frame_set(hold)
    M = sroot.matrix_world.copy()
    cd = bpy.data.cameras.new(CAM)
    cd.clip_start, cd.clip_end = 0.1, 5000.0
    cam = bpy.data.objects.new(CAM, cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    shots = [s_ for s_ in SHOTS if not a.shots or s_[0] in a.shots.split(",")]
    try:
        for name, target, loc, lens, res in shots:
            cd.lens = lens
            look_at(cam, M @ Vector(loc), M @ Vector(target))
            render(sc, a.tag, name, res)
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(cd)
    log("done; the .blend was not saved")


main()
