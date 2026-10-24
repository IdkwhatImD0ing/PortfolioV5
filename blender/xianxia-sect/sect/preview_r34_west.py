"""Cycles stills of round 34's west lane (sect/patch_r34_west.py: the mirror, the abode and the summit), seen the way
the site shows each stop, on the GPU (OptiX, then CUDA; it refuses the CPU). Renders only: the .blend is never saved.

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r34_west.py -- [--samples 64] [--tag before] \
        [--shots mirror,mirror_flute,mirror_cliff,abode,abode_duet,summit,summit_1625,summit_condor,summit_blinds] \
        [--out DIR]

Shots (1600 x 900, the film's field of view):
    mirror          frame 217 as the site frames it (client framing.ts STOP_FRAMING.mirror: the pose of frame 217 - 13,
                    turned yaw 4 deg, pitch -3 deg; refs_west.site_view)
    abode           frame 1380 (no stop framing)
    summit          frame 1647 (no stop framing)
    summit_1625     frame 1625, the approach
    <stop>_<what>   from the same camera position as <stop>, a long lens fitted to what (refs_west.CLOSE_TARGETS: the
                    objects' world boxes, or a fixed world box when none of them is in the file)
The flyer and the volume objects (haze, cloud banks) are hidden, as in the other previews (the page draws its own haze).
Writes <out>/r34_west_<tag>_<shot>.png (default out: out/tmp/r34_west/renders).
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
from sect.lib import refs_west as RW  # noqa: E402

RES = (1600, 900)
CAM = "preview.r34_west.cam"
FILL = 0.8


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r34_west.py")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--tag", default="")
    ap.add_argument("--shots", default="mirror,abode,summit,summit_1625")
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "tmp", "r34_west", "renders"))
    ap.add_argument("--exposure", type=float, default=None)
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
        raise SystemExit("preview_r34_west: no OptiX or CUDA device: refusing to render on the CPU")
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
    log("cycles device", device, [d.name for d in prefs.devices if d.use], "samples", samples,
        "view", sc.view_settings.view_transform, sc.view_settings.look, sc.view_settings.exposure)


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


def target_points(spec):
    """World points of a close target: the boxes of the named objects (and their children) that exist, else the
    fixed box."""
    names, box = spec[0], spec[1]
    pts = []
    for nm in names:
        ob = bpy.data.objects.get(nm)
        if ob is None:
            continue
        for o in [ob] + list(ob.children_recursive):
            if o.type == 'MESH':
                pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    if not pts and box is not None:
        lo, hi = box
        pts = [Vector((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    return pts


def fit_close(cam, data, eye, pts, fill=FILL):
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
    half = max(max(abs(x) for x in xs), max(abs(y) for y in ys) * aspect, 1e-4)
    data.sensor_fit = "HORIZONTAL"
    data.sensor_width = 36.0
    data.shift_x = data.shift_y = 0.0
    data.lens = min(2000.0, 18.0 * fill / half)
    cam.matrix_world = Mw
    return data.lens, (centre - eye).length


def main(a=None):
    a = a or args()
    sc = bpy.context.scene
    src = bpy.data.objects.get(EW.CAMERA)
    if src is None:
        raise RuntimeError("no %s" % EW.CAMERA)
    os.makedirs(a.out, exist_ok=True)
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    log("volume objects hidden", hide_volumes(sc))
    if a.exposure is not None:
        sc.view_settings.exposure = a.exposure
    data = src.data.copy()
    cam = bpy.data.objects.new(CAM, data)
    sc.collection.objects.link(cam)
    pre = "r34_west" + ("_" + a.tag if a.tag else "")
    made = []
    try:
        sc.camera = cam
        sc.render.resolution_x, sc.render.resolution_y = RES
        for shot in [s.strip() for s in a.shots.split(",") if s.strip()]:
            stop, _, what = shot.partition("_")
            if stop not in RW.SHOT_FRAMES:
                log("WARN unknown shot", shot)
                continue
            frame = RW.SHOT_FRAMES[stop] if not what.isdigit() else int(what)
            Mw = RW.site_view(sc, src, frame)
            data.clip_start, data.clip_end = src.data.clip_start, src.data.clip_end
            if not what or what.isdigit():
                data.lens, data.sensor_width, data.sensor_height = src.data.lens, src.data.sensor_width, \
                    src.data.sensor_height
                data.sensor_fit = src.data.sensor_fit
                data.shift_x, data.shift_y = src.data.shift_x, src.data.shift_y
                cam.matrix_world = Mw
                info = "site view, lens %.1f mm" % data.lens
            else:
                spec = RW.CLOSE_TARGETS.get(shot)
                if spec is None:
                    log("WARN no close target for", shot)
                    continue
                pts = target_points(spec)
                if not pts:
                    log("WARN nothing to aim at for", shot)
                    continue
                lens, dist = fit_close(cam, data, Mw.translation.copy(), pts, spec[2] if len(spec) > 2 else FILL)
                info = "lens %.0f mm, %.1f m to the target" % (lens, dist)
            sc.render.filepath = os.path.join(a.out, "%s_%s.png" % (pre, shot))
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            made.append(sc.render.filepath)
            log("wrote", sc.render.filepath, "frame", frame, "%dx%d" % RES, info, "%.1f s" % (time.time() - t0))
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(data)
    log("done", len(made), "stills; the .blend was not saved")


if __name__ == "__main__":
    main()
