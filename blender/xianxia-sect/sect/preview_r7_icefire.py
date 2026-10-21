"""Cycles stills of Ice-Fire Island 冰火島 (sect/lib/icefire_props.py, scenery.ICEFIRE_ISLAND) in a copy of
out/sect_chase.blend, on the GPU at low samples. Run on the cloud box after sect/patch_r7_icefire.py (or before it, for
the 'before' set):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r7_icefire.py [-- --samples 24 --tag after]

Writes out/preview/icefire_<tag>_<shot>.png (the wrapper copies new files under out/ back to the PC):
    hold772.png     chase.cam at the library hold (772): the island at the top left, beside the pagoda
    pass<f>.png     chase.cam at the frames of --frames (default 813: the island crosses the top of the frame)
    front.png       the island from the hold's side (rock-local azimuth -130, 18 deg below), closer (~170 m)
    under.png       from under the ice/fire seam, close (~95 m): icicles and lava veins
    top.png         three-quarter from above (never on the flight path; checks the glacier cap, volcano, steam)
Close-ups are framed in the island's own frame at the hold frame's lighting, with the flyer hidden. Volume objects are
hidden for speed except the island's steam puffs (icefire_props.STEAM_PREFIX) unless --volumes keeps them all.
--shots front,top: only those; --no-cams: skip the chase-camera frames; --web-steam: the steam puffs drawn roughly as
the page draws cloud puffs (warm white sprites; a Cycles volume puff in the low sun turns brown). Does not save the
.blend.
"""
import argparse
import math
import os
import sys
import time

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402
from sect import scenery as S  # noqa: E402
from sect.lib import icefire_props as IF  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
PREFIX = "icefire"
CAM = "preview.icefire.cam"
HOLD = 772
# close-ups in the island's frame: name, camera (azimuth deg, elevation deg, distance m), target (x, y, z), lens, res
SHOTS = (
    ("front", (-130.0, -18.0, 170.0), (0.0, 0.0, -22.0), 50.0, (1280, 960)),
    ("under", (-118.0, -32.0, 95.0), (-4.0, -2.0, -30.0), 35.0, (1280, 960)),
    ("top", (-150.0, 32.0, 150.0), (0.0, 0.0, 2.0), 45.0, (1280, 960)),
)


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--volumes", action="store_true", help="keep every volume object (slower)")
    ap.add_argument("--shots", default="", help="comma list of close-up shot names (default all)")
    ap.add_argument("--frames", default="813", help="extra chase.cam frames, comma list ('' for none)")
    ap.add_argument("--no-cams", action="store_true", help="skip the chase-camera frames")
    ap.add_argument("--tag", default="r", help="file name tag")
    ap.add_argument("--res", type=float, default=1.0, help="resolution factor")
    ap.add_argument("--web-steam", action="store_true",
                    help="draw the steam puffs roughly as the page does (warm white sprites), in memory only")
    return ap.parse_args(argv)


def web_steam(prefix):
    """The page draws world.cloud.* as camera-facing sprites shaded between look.ts puffs.shade (#d4b6a8) and lit
    (#fff0dc), never darker; a Cycles volume puff in the low sun turns brown-grey. Give the steam puffs a scattering +
    softly emitting volume in those colours (memory only) so the stills show what the page shows."""
    m = bpy.data.materials.new("preview.icefire_steam")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (1.0, 0.87, 0.72, 1.0)
    vol.inputs["Emission Color"].default_value = (0.66, 0.47, 0.39, 1.0)
    vol.inputs["Emission Strength"].default_value = 0.9
    gen = nt.nodes.new("ShaderNodeTexCoord")
    sub = nt.nodes.new("ShaderNodeVectorMath")
    sub.operation = 'SUBTRACT'
    sub.inputs[1].default_value = (0.5, 0.5, 0.5)
    ln = nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = 'LENGTH'
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs[1].default_value, ramp.inputs[2].default_value = 0.5, 0.15
    att = nt.nodes.new("ShaderNodeAttribute")
    att.attribute_type, att.attribute_name = 'OBJECT', "density"
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = 'MULTIPLY'
    nt.links.new(gen.outputs["Generated"], sub.inputs[0])
    nt.links.new(sub.outputs["Vector"], ln.inputs[0])
    nt.links.new(ln.outputs["Value"], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], mul.inputs[0])
    nt.links.new(att.outputs["Fac"], mul.inputs[1])
    nt.links.new(mul.outputs[0], vol.inputs["Density"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    n = 0
    for ob in bpy.data.objects:
        if ob.name.startswith(prefix) and ob.type == 'MESH':
            ob.data = ob.data.copy()
            ob.data.materials.clear()
            ob.data.materials.append(m)
            n += 1
    return n


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
    sc.cycles.volume_bounces = 0
    sc.cycles.sample_clamp_indirect = 4.0
    sc.render.use_persistent_data = True
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    log("cycles", device, "samples", samples)


def hide_volumes(sc, keep_prefix):
    """Hide objects whose material is a volume shader (cloud banks, haze), except names starting with keep_prefix."""
    vol = set()
    for m in bpy.data.materials:
        if m.node_tree is not None and any(n.bl_idname.startswith("ShaderNodeVolume") for n in m.node_tree.nodes):
            vol.add(m.name)
    n = 0
    for ob in sc.objects:
        if ob.hide_render or ob.type not in {"MESH", "CURVE", "SURFACE", "META", "FONT", "VOLUME"}:
            continue
        if ob.name.startswith(keep_prefix):
            continue
        if ob.type == "VOLUME" or any(s.material is not None and s.material.name in vol for s in ob.material_slots):
            ob.hide_render = True
            n += 1
    return n


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
    rock = bpy.data.objects.get(S.ICEFIRE_ISLAND)
    if rock is None:
        raise RuntimeError(S.ICEFIRE_ISLAND + " not found")
    ours = IF.our_objects(rock)
    log("island", rock.name, "icefire objects", len(ours), sorted(o.name for o in ours)[:40])
    log("rock slots", [s.material.name if s.material else None for s in rock.material_slots])
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc, IF.STEAM_PREFIX))
    if a.web_steam:
        log("steam puffs drawn page-like", web_steam(IF.STEAM_PREFIX))
    k = a.res
    chase = bpy.data.objects.get(EW.CAMERA)
    if chase is None:
        raise RuntimeError(EW.CAMERA + " not found")
    sc.camera = chase
    frames = [] if a.no_cams else [("hold772", HOLD)] + [("pass%d" % int(f), int(f)) for f in a.frames.split(",") if f]
    for name, f in frames:
        sc.frame_set(f)
        render(sc, a.tag, name, (int(1280 * k), int(720 * k)))
    sc.frame_set(HOLD)
    M = rock.matrix_world.copy()
    cd = bpy.data.cameras.new(CAM)
    cd.clip_start, cd.clip_end = 0.5, 8000.0
    cam = bpy.data.objects.new(CAM, cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    shots = [s_ for s_ in SHOTS if not a.shots or s_[0] in a.shots.split(",")]
    try:
        for name, (az, el, dist), target, lens, res in shots:
            cd.lens = lens
            t = Vector(target)
            loc = t + dist * Vector((math.cos(math.radians(el)) * math.cos(math.radians(az)),
                                     math.cos(math.radians(el)) * math.sin(math.radians(az)),
                                     math.sin(math.radians(el))))
            look_at(cam, M @ loc, M @ t)
            render(sc, a.tag, name, (int(res[0] * k), int(res[1] * k)))
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(cd)
    log("done; the .blend was not saved")


main()
