"""Cycles close-ups of the gate weapons (Heaven Sword 倚天剑 / Dragon Saber 屠龙刀, sect/areas/gate.py WEAPONS) in
out/sect_chase.blend, on the GPU at low samples (~1-2 min). Run on the cloud box after patch_gate_swords.py:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_gate_swords.py [-- --samples 24 --quick]

Writes out/preview/gate_swords_*.png (the wrapper copies new files under out/ back to the PC):
    gate_swords_hold.png              chase.cam at the gate's hold frame (export_web full profile, 93)
    gate_swords_approach.png          chase.cam at frame 75, climbing the stair (both silhouettes against the sky)
    gate_swords_<key>_full.png        the whole weapon from the inner front, three-quarter
    gate_swords_<key>_hilt.png        guard and hilt (winged guard + tassel / dragon head + ring pommel)
    gate_swords_<key>_name.png        the gold name on the blade
    gate_swords_<key>_blade.png       the blade's flat (the saber's dragon inlay), straight on
    gate_swords_<key>_plinth.png      the plinth: the name on the front, the saying on the inner side
(<key> heaven_sword, dragon_saber). Everything renders at the hold frame's lighting with the flyer hidden; volume
objects (cloud banks, haze) are hidden for speed unless --volumes. --quick: hold, approach and the two full views.
--keys dragon_saber / --shots full,hilt: only those weapons' / shots' close-ups; --no-cams: skip hold and approach.
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
from sect.areas import gate as G  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
PREFIX = "gate_swords"
APPROACH_FRAME = 75
CAM = "preview.gate_swords.cam"
# close-ups in each weapon's own frame: target (x, y, z) and camera offset (toward the gate's axis, toward the front,
# up) in metres, lens mm, resolution. The plinth view looks down from above the guardian lions (4.4 m tall, at
# x +-10.6, y -30), so their heads stay out of the shot.
SHOTS = (
    ("full", (0.0, 0.0, 8.2), (9.0, 24.0, 1.0), 50.0, (720, 960)),
    ("hilt", (0.0, 0.0, 12.9), (3.0, 7.5, 0.6), 50.0, (720, 960)),
    ("name", None, (0.8, 4.2, 0.3), 50.0, (800, 800)),
    ("blade", (0.25, 0.0, 6.0), (1.2, 12.5, 0.4), 50.0, (720, 960)),
    ("plinth", (0.0, -0.5, 1.5), (3.2, 6.5, 4.2), 40.0, (1100, 800)),
)


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--volumes", action="store_true", help="keep volume objects (slower)")
    ap.add_argument("--keys", default="", help="comma list of weapon keys for the close-ups (default all)")
    ap.add_argument("--shots", default="", help="comma list of close-up shot names (default all)")
    ap.add_argument("--no-cams", action="store_true", help="skip the hold and approach renders")
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
        return int(next(a["holdFrame"] for a in EW.AREAS if a["id"] == "gate"))
    except Exception as e:  # noqa: BLE001
        log("WARN hold frame from the timeline failed (%s); using 93" % e)
        return 93


def render(sc, name, res):
    sc.render.resolution_x, sc.render.resolution_y = res
    path = os.path.join(OUT, "%s_%s.png" % (PREFIX, name))
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
    weapons = []
    for spec in G.WEAPONS:
        ob = bpy.data.objects.get(spec["object"])
        if ob is None:
            raise RuntimeError("%s not found" % spec["object"])
        if ob.data.name != G.K + "." + spec["key"]:
            log("WARN", ob.name, "has mesh", ob.data.name, "- run sect/patch_gate_swords.py first")
        n = len(ob.data.polygons)
        lt = [0] * n
        ob.data.polygons.foreach_get("loop_total", lt)
        log(spec["key"], ob.name, "mesh", ob.data.name, "tris", sum(lt) - 2 * n,
            "slots", [s.material.name if s.material else None for s in ob.material_slots])
        weapons.append((spec, ob))
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    chase = bpy.data.objects.get(EW.CAMERA)
    if chase is None:
        raise RuntimeError(EW.CAMERA + " not found")
    # the real camera: hold and approach
    sc.camera = chase
    for name, f in (() if a.no_cams else (("hold", hold), ("approach", APPROACH_FRAME))):
        sc.frame_set(f)
        render(sc, name, (1280, 720))
    # close-ups at the hold frame's lighting
    sc.frame_set(hold)
    cd = bpy.data.cameras.new(CAM)
    cd.clip_start, cd.clip_end = 0.1, 5000.0
    cam = bpy.data.objects.new(CAM, cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    shots = SHOTS[:1] if a.quick else SHOTS
    if a.shots:
        shots = [s_ for s_ in shots if s_[0] in a.shots.split(",")]
    keys = a.keys.split(",") if a.keys else None
    try:
        for spec, ob in weapons:
            if keys and spec["key"] not in keys:
                continue
            M = ob.matrix_world
            inner = -spec["side"]
            for name, target, (o_in, o_front, o_up), lens, res in shots:
                if target is None:          # the blade name: its centre on the front face
                    if spec["kind"] == "jian":
                        target = (0.0, -0.2, sum(G.J_NAME[1]) / 2.0)
                    else:
                        target = (G.D_NAME[1], -0.2, sum(G.D_NAME[2]) / 2.0)
                loc = (target[0] + inner * o_in, target[1] - o_front, target[2] + o_up)
                cd.lens = lens
                look_at(cam, M @ Vector(loc), M @ Vector(target))
                render(sc, "%s_%s" % (spec["key"], name), res)
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(cd)
    log("done; the .blend was not saved")


main()
