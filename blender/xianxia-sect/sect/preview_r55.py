"""Cycles stills of round 55's prop moves (sect/patch_r55_placement.py: the forge, the Mission Hall, the Jade Slip
Pavilion and the Heart-Mirror Terrace), seen the way the site shows each stop, on the GPU (OptiX, then CUDA; it refuses
the CPU). Renders only: the .blend is never saved. Run it on the dry run's copy, after the patch (and on the file
before it with --tag before, to compare):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r55.py -- [--samples 64] [--tag before] \
        [--shots forge,mission,scroll,mirror,forge_west,forge_porch,forge_ore,mission_lanterns,scroll_walk,mirror_boulder]

Shots (1600 x 900, the film's field of view):
    forge, mission, scroll, mirror   the hold (352, 619, 1103, 217) as the site frames it (client framing.ts
                    STOP_FRAMING: the forge plain; the mission turned yaw 8, pitch 2; the scroll stands back 12 frames and
                    turns yaw 8, pitch -2.5; the mirror stands back 13 and turns yaw 4, pitch -3). The default.
    <stop>_<what>   from the same camera place, a long lens fitted to a box round that group's new places (close_boxes,
                    from the area modules' round-55 tables), the same box before and after
The flyer and the volume objects (haze, cloud banks) are hidden, as in the other previews (the page draws its own).
Writes out/tmp/r55/renders/r55_<tag>_<shot>.png (under out/: rblender copies it back to the PC).
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
from sect.areas import forge as F  # noqa: E402
from sect.areas import mirror as MR  # noqa: E402
from sect.areas import mission as MI  # noqa: E402
from sect.areas import scroll as SC  # noqa: E402
from sect.lib import refs_east as RE  # noqa: E402
from sect.lib import refs_west as RW  # noqa: E402

RES = (1600, 900)
CAM = "preview.r55.cam"
FILL = 0.9
OUT = os.path.join(ROOT, "out", "tmp", "r55", "renders")
HOLDS = dict(forge=RE.HOLD_FRAMES["forge"], mission=RE.HOLD_FRAMES["mission"], scroll=SC.HOLD_FRAME,
             mirror=RW.SHOT_FRAMES["mirror"])
# hold frame -> (yaw deg, pitch deg, back frames), as client/src/lib/sect/framing.ts STOP_FRAMING has them. The scroll
# stands back 12 frames there (the owner's 2026-10-24 "slightly back"); scroll.SITE_FRAMING still has round 33's 9.
SCROLL_BACK = 12
FRAMING = dict(RE.SITE_FRAMING)
FRAMING.update(RW.SITE_FRAMING)
FRAMING[SC.HOLD_FRAME] = (SC.SITE_FRAMING[0], SC.SITE_FRAMING[1], SCROLL_BACK)
PAD = 2.5                     # m round a close-up group's places


def close_boxes():
    """shot -> (area, (min), (max)) in the area's frame: a group's new places (the area modules' round-55 tables) with
    PAD round them, from the floor to over its tallest piece."""
    groups = dict(
        forge_west=("forge", [F.west_place(k)[:2] for k in ("rack", "anvil", "trough")], 3.0),
        forge_porch=("forge", [F.RACKS[2][:2], F.RACKS[3][:2], F.ORE[2][:2]], 3.0),
        forge_ore=("forge", [F.ORE[i][:2] for i in (0, 1, 4)], 2.5),
        mission_lanterns=("mission", [xy for xy, _was in MI.lantern_moves().values()], 3.2),
        scroll_walk=("scroll", [xy for xy, _was in SC.r55_moves().values()], 5.0),
        mirror_boulder=("mirror", [xy for xy, _was in MR.boulder_moves().values()], 3.5),
    )
    out = {}
    for shot, (area, pts, top) in groups.items():
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        out[shot] = (area, (min(xs) - PAD, min(ys) - PAD, 0.0), (max(xs) + PAD, max(ys) + PAD, top))
    return out


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r55.py")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--tag", default="")
    ap.add_argument("--shots", default=",".join(HOLDS))
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
        raise SystemExit("preview_r55: no OptiX or CUDA device: refusing to render on the CPU")
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
    """chase.cam's world matrix as the page shows ``frame`` (refs_east / refs_west.site_view, on FRAMING). Sets the
    scene frame."""
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
    boxes = close_boxes()
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    log("volume objects hidden", hide_volumes(sc))
    data = src.data.copy()
    cam = bpy.data.objects.new(CAM, data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    pre = "r55" + ("_" + a.tag if a.tag else "")
    made = []
    try:
        for shot in shots:
            stop, _, what = shot.partition("_")
            if stop not in HOLDS or (what and shot not in boxes):
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
                area, lo, hi = boxes[shot]
                M = bpy.data.objects[area + ".root"].matrix_world
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
