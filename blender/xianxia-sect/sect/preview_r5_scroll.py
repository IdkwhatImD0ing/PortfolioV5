"""Cycles stills of the Jade Slip Pavilion (sect/areas/scroll.py) after sect/patch_r5_scroll.py: the jade scroll in its
standing frame (posts, sill, top rail, sun and moon finials) and the six Holy Fire Tokens on their lacquer stand, plus
the other props of the stop (desk, scholar rocks). GPU, low samples. Renders only; the .blend is not saved.

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r5_scroll.py [-- --samples 20 --tag r1]

Writes out/preview/r5_scroll[_<tag>]_<shot>.png (rblender copies them back):
    hold        chase.cam at the scroll hold (1103), 1280 x 720: what the reader sees
    pass        chase.cam at 1123 (gliding past the scroll's face)
    approach    chase.cam at 1080 (flying in toward the hold, the scroll ahead)
    scroll      the whole scroll and its frame, from in front of its right half
    base        the right post's foot: plinth, clamping stones, iron bands
    top         the top rail and the right post's finial (the moon), close
    sun         the left post's finial (the sun), close
    sill        the sill beam under the slips and its post bracket, close
    tokens      the token stand three-quarter, ~9 m
    tokface     the middle tokens' faces, ~4 m
    stand_top   the stand's post heads: the small sun and moon
    rock        the scholar rock by the back rail (scroll.rock.2) on its pedestal
    desk        the stone desk, close
    lantern     the left eave-corner lantern of the pavilion and the soffit its cord runs into
Shots are given in scroll.root's frame (z 0 = the terrace top), so they follow the area wherever world.py puts it.
Options: --samples 20, --tag r1, --shots hold,tokens,... , --res 960x540 (close-ups; chase.cam shots are 1280 x 720),
--volumes (keep mist/cloud volumes; slower).
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
from sect.areas import scroll as SC  # noqa: E402
from sect.lib import look as L  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
HOLD, PASS, APPROACH = 1103, 1123, 1080
CAM = "preview.r5_scroll.cam"
SHOTS = ("hold", "approach", "pass", "scroll", "base", "top", "sun", "sill", "tokens", "tokface", "stand_top", "rock",
         "desk", "lantern")


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r5_scroll.py")
    ap.add_argument("--samples", type=int, default=20)
    ap.add_argument("--tag", default="")
    ap.add_argument("--shots", default=",".join(SHOTS))
    ap.add_argument("--res", default="960x540")
    ap.add_argument("--volumes", action="store_true", help="keep volume objects (slower)")
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
    sc.render.film_transparent = False
    log("cycles", device, "samples", samples)


def hide_volumes(sc):
    """Hide objects whose material is a volume shader (mist, haze, cloud banks): Cycles volumes dominate a preview."""
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


def close_ups():
    """{shot: (camera, target, lens)} in scroll.root's frame, from the module's own layout numbers."""
    fp = SC.frame_points()
    tk = SC.token_stand_points()
    (lx, ly), (rx, ry) = fp["post_l"], fp["post_r"]
    zt = fp["top_z"]
    sx, sy = tk["centre"]
    fx, fy = tk["front"]                      # unit vector the stand faces
    px, py = -fy, fx                          # along the row
    rk = bpy.data.objects.get(SC.K + ".rock.2")
    rkp = rk.matrix_local.translation if rk is not None else Vector((-2.0, 21.5, 0.0))
    cx, cy, cz = SC.SCROLL_C
    la = bpy.data.objects.get(SC.K + ".lantern")
    lan = la.matrix_local.translation if la is not None else Vector((8.3, 23.1, 5.9))
    return {
        "scroll": ((cx + 12.0, cy - 30.0, 9.5), (cx + 0.5, cy, 8.0), 28.0),
        "base": ((rx + 1.5, ry - 7.5, 2.6), (rx, ry, 1.2), 35.0),
        "top": ((rx + 1.0, ry - 9.0, zt - 1.0), (rx - 1.5, ry, zt - 1.5), 40.0),
        "sun": ((lx + 2.5, ly - 8.0, zt - 0.5), (lx, ly, zt + 0.5), 45.0),
        "sill": ((rx - 2.0, ry - 9.0, fp["sill_z"] - 2.5), (rx - 3.0, ry, fp["sill_z"]), 40.0),
        "tokens": ((sx + 9.0 * fx + 2.0 * px, sy + 9.0 * fy + 2.0 * py, 4.2), (sx, sy, 1.9), 35.0),
        "tokface": ((sx + 4.0 * fx + 0.6 * px, sy + 4.0 * fy + 0.6 * py, 2.8), (sx, sy, 2.4), 40.0),
        "stand_top": ((sx + 6.0 * fx, sy + 6.0 * fy, 3.6), (sx, sy, 3.0), 45.0),
        "rock": ((rkp.x + 2.0, rkp.y - 8.0, 2.8), (rkp.x, rkp.y, 1.4), 35.0),
        "desk": ((SC.DESK[0] + 3.5, SC.DESK[1] - 4.5, 2.6), (SC.DESK[0], SC.DESK[1], 0.6), 35.0),
        "lantern": ((lan[0] - 2.2, lan[1] - 3.6, lan[2] - 0.9), (lan[0], lan[1], lan[2] + 0.3), 40.0),
    }


def main():
    a = args()
    sc = bpy.context.scene
    root = bpy.data.objects.get(SC.K + ".root")
    if root is None:
        raise RuntimeError("scroll.root not found")
    os.makedirs(OUT, exist_ok=True)
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    w, h = (int(x) for x in a.res.split("x"))
    views = close_ups()
    pre = "r5_scroll" + ("_" + a.tag if a.tag else "")
    made = []
    tmp = None
    M = root.matrix_world
    try:
        for shot in [s.strip() for s in a.shots.split(",") if s.strip()]:
            if shot in ("hold", "pass", "approach"):
                cam = bpy.data.objects.get(EW.CAMERA)
                if cam is None:
                    log("WARN no", EW.CAMERA)
                    continue
                frame, res = {"hold": HOLD, "pass": PASS, "approach": APPROACH}[shot], (1280, 720)
            elif shot in views:
                loc, tgt, lens = views[shot]
                cam = tmp = L.camera_look_at(CAM, M @ Vector(loc), M @ Vector(tgt), lens=lens,
                                             collection=sc.collection)
                cam.data.clip_start = 0.05
                frame, res = HOLD, (w, h)
            else:
                log("WARN unknown shot", shot)
                continue
            sc.camera = cam
            sc.frame_set(frame)
            sc.render.resolution_x, sc.render.resolution_y = res
            sc.render.filepath = os.path.join(OUT, "%s_%s.png" % (pre, shot))
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            made.append(sc.render.filepath)
            log("wrote", sc.render.filepath, "frame", frame, "%.1f s" % (time.time() - t0))
    finally:
        if tmp is not None:
            cd = tmp.data
            bpy.data.objects.remove(tmp, do_unlink=True)
            bpy.data.cameras.remove(cd)
    log("done", len(made), "stills; the .blend was not saved")


main()
