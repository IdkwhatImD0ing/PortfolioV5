"""Cycles stills of round 39's centre lane (sect/patch_r39_centre.py: the Stele Forest, the Jade Slip Pavilion and
Ice-Fire Island), seen the way the site shows each stop, on the GPU (OptiX, then CUDA; it refuses the CPU). Renders
only: the .blend is never saved.

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r39_centre.py -- [--samples 64] \
        [--tag before] [--shots library,steles,scroll,steles_tokens,steles_master,steles_rows,scroll_tomb,library_island]

Shots (1600 x 900, the film's field of view):
    library, steles, scroll   the hold (772, 974, 1103) as the site frames it (client framing.ts STOP_FRAMING: the
                    scroll stands back 9 frames and turns 8 deg left and 2.5 down; the others plain)
    <stop>_<what>   from the same camera position, a long lens fitted to a fixed box (CLOSE_BOXES: in the area's frame,
                    or the world's for the island), the same box before and after
The flyer and the volume objects (haze, cloud banks) are hidden, as in the other previews (the page draws its own).
Writes out/tmp/r39_centre/renders/r39_centre_<tag>_<shot>.png (under out/: rblender copies it back to the PC).
"""
import argparse
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402
from sect.areas import scroll as SC  # noqa: E402
from sect.lib import refs_centre as RC  # noqa: E402

RES = (1600, 900)
CAM = "preview.r39_centre.cam"
FILL = 0.9
OUT = os.path.join(ROOT, "out", "tmp", "r39_centre", "renders")
HOLDS = dict(library=772, steles=974, scroll=1103)
FRAMING = {1103: SC.SITE_FRAMING}             # hold frame -> (yaw deg, pitch deg, back frames)
tx, ty, tz = RC.TOKENS_AT
mx, my = RC.TOMB_AT
CLOSE_BOXES = {                               # shot -> (frame: an area root's name or None = world, (min), (max))
    "steles_tokens": ("steles.root", (tx - 2.0, ty - 2.0, tz), (tx + 2.0, ty + 2.0, tz + 2.8)),
    "steles_master": ("steles.root", (-2.6, 20.5, 1.5), (2.6, 24.5, 10.6)),
    "steles_rows": ("steles.root", (-14.0, -21.0, 0.5), (-10.0, 7.0, 8.0)),
    "scroll_tomb": ("scroll.root", (mx - 3.6, my - 3.6, RC.LAWN_Z), (mx + 3.6, my + 3.6, RC.LAWN_Z + 5.2)),
    "library_island": (None, (275.0, 935.0, 215.0), (385.0, 1050.0, 315.0)),
}


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--tag", default="")
    ap.add_argument("--shots", default=",".join(["library", "steles", "scroll"] + list(CLOSE_BOXES)))
    ap.add_argument("--out", default=OUT)
    return ap.parse_args(argv)


def setup_cycles(sc, samples):
    """OptiX, then CUDA; denoised stills. Refuses the CPU."""
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
        raise SystemExit("preview_r39_centre: no OptiX or CUDA device: refusing to render on the CPU")
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
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False
    log("cycles device", device, [d.name for d in prefs.devices if d.use], "samples", samples)


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


def site_view(sc, cam, frame):
    yaw, pitch, back = FRAMING.get(frame, (0.0, 0.0, 0))
    sc.frame_set(frame - back)
    Mw = cam.matrix_world.copy()
    R = Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Mw.to_3x3().normalized() @ \
        Matrix.Rotation(math.radians(pitch), 3, 'X')
    out = R.to_4x4()
    out.translation = Mw.translation
    return out


def fit_close(cam, data, eye, pts, fill=FILL):
    """Aim from ``eye`` at the points' centre and set the lens so they span ``fill`` of the frame."""
    centre = sum(pts, Vector()) / len(pts)
    rot = (centre - eye).to_track_quat('-Z', 'Y').to_matrix()
    Mw = rot.to_4x4()
    Mw.translation = eye
    inv = Mw.inverted()
    xs, ys = [], []
    for p in pts:
        q = inv @ p
        xs.append(q.x / -q.z)
        ys.append(q.y / -q.z)
    aspect = RES[0] / RES[1]
    half = max(max(abs(x) for x in xs), max(abs(y) for y in ys) * aspect)
    data.sensor_fit = "HORIZONTAL"
    data.sensor_width = 36.0
    data.shift_x = data.shift_y = 0.0
    data.lens = 18.0 * fill / half
    cam.matrix_world = Mw
    return data.lens, (centre - eye).length


def main():
    a = args()
    sc = bpy.context.scene
    src = bpy.data.objects.get(EW.CAMERA)
    if src is None:
        raise RuntimeError("no %s" % EW.CAMERA)
    os.makedirs(a.out, exist_ok=True)
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.resolution_percentage = 100
    shots = [s.strip() for s in a.shots.split(",") if s.strip()]
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    log("volume objects hidden", hide_volumes(sc))
    data = src.data.copy()
    cam = bpy.data.objects.new(CAM, data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    pre = "r39_centre" + ("_" + a.tag if a.tag else "")
    made = []
    try:
        for shot in shots:
            stop, _, what = shot.partition("_")
            if stop not in HOLDS:
                log("WARN unknown shot", shot)
                continue
            Mw = site_view(sc, src, HOLDS[stop])
            data.lens, data.sensor_width, data.sensor_height = src.data.lens, src.data.sensor_width, \
                src.data.sensor_height
            data.sensor_fit = src.data.sensor_fit
            data.shift_x, data.shift_y = src.data.shift_x, src.data.shift_y
            data.clip_start, data.clip_end = src.data.clip_start, src.data.clip_end
            if not what:
                cam.matrix_world = Mw
                info = "site framing %s" % (FRAMING.get(HOLDS[stop], (0.0, 0.0, 0)),)
            else:
                fr, lo, hi = CLOSE_BOXES[shot]
                M = bpy.data.objects[fr].matrix_world if fr else Matrix.Identity(4)
                pts = [M @ Vector((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
                lens, dist = fit_close(cam, data, Mw.translation.copy(), pts)
                info = "lens %.0f mm, %.1f m to the box's centre" % (lens, dist)
            sc.render.filepath = os.path.join(a.out, "%s_%s.png" % (pre, shot))
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            made.append(sc.render.filepath)
            log("wrote", sc.render.filepath, "frame", sc.frame_current, info, "%.1f s" % (time.time() - t0))
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(data)
    log("done", len(made), "stills; the .blend was not saved")


main()
