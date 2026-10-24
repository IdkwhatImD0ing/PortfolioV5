"""Cycles stills of round 34's east lane (sect/patch_r34_east.py: the forge, the arena, the Mission Hall and the
formation), seen the way the site shows each stop, on the GPU (OptiX, then CUDA; it refuses the CPU). Renders only:
the .blend is never saved.

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r34_east.py -- [--samples 64] [--tag before] \
        [--shots forge,forge_corner,arena,arena_seats,mission,mission_dipper,formation,formation_altars,formation_chant] \
        [--out DIR] [--grid]

Shots (1600 x 900, the film's field of view):
    forge, arena, mission, formation   the hold (352, 516, 619, 1208) as the site frames it (client framing.ts
                    STOP_FRAMING: the mission turned yaw 8 deg, pitch 2 deg; the formation pitch -8 deg; the forge and
                    the arena plain; refs_east.site_view)
    <stop>_<what>   from the same camera position, a long lens fitted to a fixed box in the area's frame
                    (refs_east.CLOSE_BOXES), the same box before and after
--grid draws nothing in the scene; it writes <out>/r34_east_grid_<stop>.json: a 1 m floor grid of the area's frame
projected into the hold frame (for planning overlays). The flyer, the volume objects (haze, cloud banks) and the
formation's dome are hidden, as in the other previews (the page draws its own haze and barrier).
Writes <out>/r34_east_<tag>_<shot>.png (default out: /E:/Github/PortfolioV5/.playwright-mcp/r34/east on the box; fetch
them with scp).
"""
import argparse
import json
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
from sect.lib import refs_east as RE  # noqa: E402

RES = (1600, 900)
CAM = "preview.r34_east.cam"
FILL = 0.9
OUT = "/E:/Github/PortfolioV5/.playwright-mcp/r34/east" if os.name != "nt" else \
    "E:/Github/PortfolioV5/.playwright-mcp/r34/east"


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r34_east.py")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--tag", default="")
    ap.add_argument("--shots", default="forge,arena,mission,formation")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--grid", action="store_true")
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
        raise SystemExit("preview_r34_east: no OptiX or CUDA device: refusing to render on the CPU")
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


def write_grid(sc, src, stop, out):
    """A 1 m floor grid of the stop's area frame projected into its hold frame (planning overlays)."""
    frame = RE.HOLD_FRAMES[stop]
    Mw = RE.site_view(sc, src, frame)
    tmp = bpy.data.objects.new("~r34e.gridcam", src.data)
    sc.collection.objects.link(tmp)
    tmp.matrix_world = Mw
    bpy.context.view_layer.update()
    root = bpy.data.objects[stop + ".root"]
    (x0, x1), (y0, y1) = RE.GRID_RANGE[stop]
    pts = []
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            v = world_to_camera_view(sc, tmp, root.matrix_world @ Vector((x, y, 0.0)))
            pts.append([x, y, round(v.x * RES[0], 1), round((1 - v.y) * RES[1], 1), round(v.z, 2)])
    bpy.data.objects.remove(tmp, do_unlink=True)
    p = os.path.join(out, "r34_east_grid_%s.json" % stop)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(dict(stop=stop, frame=frame, points=pts), fh)
    log("wrote", p)


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
    if a.grid:
        for stop in sorted({s.split("_")[0] for s in shots}):
            write_grid(sc, src, stop, a.out)
        return
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    log("volume objects hidden", hide_volumes(sc))
    for ob in bpy.data.objects:
        if ob.name == "formation.dome" or ob.name.startswith("formation.dome."):
            ob.hide_render = True
    data = src.data.copy()
    cam = bpy.data.objects.new(CAM, data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    pre = "r34_east" + ("_" + a.tag if a.tag else "")
    made = []
    try:
        for shot in shots:
            stop, _, what = shot.partition("_")
            if stop not in RE.HOLD_FRAMES:
                log("WARN unknown shot", shot)
                continue
            Mw = RE.site_view(sc, src, RE.HOLD_FRAMES[stop])
            data.lens, data.sensor_width, data.sensor_height = src.data.lens, src.data.sensor_width, \
                src.data.sensor_height
            data.sensor_fit = src.data.sensor_fit
            data.shift_x, data.shift_y = src.data.shift_x, src.data.shift_y
            data.clip_start, data.clip_end = src.data.clip_start, src.data.clip_end
            if not what:
                cam.matrix_world = Mw
                info = "site framing %s" % (RE.SITE_FRAMING.get(RE.HOLD_FRAMES[stop], (0.0, 0.0)),)
            else:
                box = RE.CLOSE_BOXES.get(shot)
                if box is None:
                    log("WARN no close box for", shot)
                    continue
                root = bpy.data.objects[stop + ".root"]
                (x0, y0, z0), (x1, y1, z1) = box
                pts = [root.matrix_world @ Vector((x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
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
