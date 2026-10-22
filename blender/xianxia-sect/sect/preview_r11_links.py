"""Cycles stills of the link stairways for round 11, lane 'links' (sect/patch_r11_links.py): before / after crops at the
diagnosis frames. Renders only; the .blend is not saved.

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r11_links.py [-- --tag before --samples 24]

Writes out/preview/r11_links[_<tag>]_<shot>.png (rblender copies them back), 1280 x 720:
    f120 f140 f180   chase.cam on the gate -> mirror stair: the rest landing (120, 140), the stair top at the terrace (180)
    f240             chase.cam past the mirror: the parapets round the bend of the mirror -> forge stair
    f1066 f1201 f1546  chase.cam at the steles -> scroll, scroll -> formation and abode -> summit rest landings
    rest_gm          close: the gate -> mirror rest landing from outside (slab, walls, parapet ends)
    top_gm           close: the top treads of the gate -> mirror stair where they meet the mirror terrace
    foot_mf          close: the mirror -> forge foot landing and its walls, from the side
    mirror_nw        the mirror terrace from the north-west, the arrival stair beyond it
Options: --samples 24, --tag x, --shots f120,..., --cpu (CPU even when a GPU is there), --threads 16, --volumes.
"""
import argparse
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402
from sect import world as W  # noqa: E402
from sect.lib import look as L  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
CAM = "preview.r11_links.cam"
FRAMES = {"f120": 120, "f140": 140, "f180": 180, "f240": 240, "f1066": 1066, "f1201": 1201, "f1546": 1546}
CLOSE = ("rest_gm", "top_gm", "foot_mf", "mirror_nw")
SHOTS = tuple(FRAMES) + CLOSE
RES = (1280, 720)


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r11_links.py")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--tag", default="")
    ap.add_argument("--shots", default=",".join(SHOTS))
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--volumes", action="store_true", help="keep volume objects (slower)")
    return ap.parse_args(argv)


def setup_cycles(sc, samples, cpu, threads):
    sc.render.engine = "CYCLES"
    dev = "CPU"
    if not cpu:
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            for kind in ("OPTIX", "CUDA"):
                try:
                    prefs.compute_device_type = kind
                    prefs.get_devices()
                    gpus = [d for d in prefs.devices if d.type == kind]
                    if gpus:
                        for d in prefs.devices:
                            d.use = d.type == kind
                        dev = "GPU"
                        log("GPU", kind, [d.name for d in gpus])
                        break
                except TypeError:
                    continue
        except Exception as e:
            log("WARN no GPU:", e)
    sc.cycles.device = dev
    if dev == "CPU":
        sc.render.threads_mode = "FIXED"
        sc.render.threads = max(1, threads)
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except TypeError:
        pass
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
    log("cycles", dev, "samples", samples)
    return dev


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


def verts_w(name):
    ob = bpy.data.objects[name]
    co = np.empty(len(ob.data.vertices) * 3)
    ob.data.vertices.foreach_get("co", co)
    M = np.array(ob.matrix_world)
    return co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]


def close_view(shot, rng_):
    """(eye, target, lens) in world space."""
    if shot == "rest_gm":
        slab = verts_w("world.link.gate_mirror.rest_landing")
        st = verts_w("world.link.gate_mirror.stairs")
        c = 0.5 * (slab.min(0) + slab.max(0))
        near = st[np.argmin(np.linalg.norm(st[:, :2] - c[:2], axis=1))]
        out = (c - near)[:2]
        out /= np.linalg.norm(out)
        along = np.array([-out[1], out[0]])
        tgt = Vector((c[0] - out[0] * 2.0, c[1] - out[1] * 2.0, slab[:, 2].max() - 0.6))
        eye = tgt + Vector((out[0] * 17.0 + along[0] * 9.0, out[1] * 17.0 + along[1] * 9.0, 3.5))
        return eye, tgt, 30.0
    if shot == "top_gm":
        pb = W.port(rng_, "mirror", "arrival")
        p, h = pb["p"], pb["h"]
        tgt = Vector((p[0] - h[0] * 5.0, p[1] - h[1] * 5.0, p[2]))
        side = np.array([-h[1], h[0]])
        eye = Vector((p[0] - h[0] * 20.0 + side[0] * 6.0, p[1] - h[1] * 20.0 + side[1] * 6.0, p[2] + 2.5))
        return eye, tgt, 32.0
    if shot == "foot_mf":
        pa = W.port(rng_, "mirror", "depart")
        p, h = pa["p"], pa["h"]
        side = np.array([-h[1], h[0]])
        tgt = Vector((p[0] + h[0] * 4.0, p[1] + h[1] * 4.0, p[2] - 1.0))
        eye = Vector((p[0] + h[0] * 2.0 + side[0] * 18.0, p[1] + h[1] * 2.0 + side[1] * 18.0, p[2] + 4.0))
        return eye, tgt, 30.0
    if shot == "mirror_nw":
        ax, ay, az, _ = W.ANCHORS["mirror"]
        return Vector((ax - 70.0, ay + 70.0, az + 38.0)), Vector((ax + 8.0, ay - 30.0, az - 2.0)), 30.0
    raise KeyError(shot)


def main():
    a = args()
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    setup_cycles(sc, a.samples, a.cpu, a.threads)
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    rng_ = W.Range(W._norm_anchors(None), W._anchor_yaws(None))
    pre = "r11_links" + ("_" + a.tag if a.tag else "")
    made, tmp = [], None
    try:
        for shot in [s.strip() for s in a.shots.split(",") if s.strip()]:
            if shot in FRAMES:
                cam = bpy.data.objects.get(EW.CAMERA)
                frame = FRAMES[shot]
            elif shot in CLOSE:
                eye, tgt, lens = close_view(shot, rng_)
                if tmp is not None:
                    cd = tmp.data
                    bpy.data.objects.remove(tmp, do_unlink=True)
                    bpy.data.cameras.remove(cd)
                cam = tmp = L.camera_look_at(CAM, eye, tgt, lens=lens, collection=sc.collection)
                cam.data.clip_start = 0.1
                frame = 217
                log("close", shot, "eye", [round(v, 1) for v in eye], "target", [round(v, 1) for v in tgt])
            else:
                log("WARN unknown shot", shot)
                continue
            sc.camera = cam
            sc.frame_set(frame)
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
