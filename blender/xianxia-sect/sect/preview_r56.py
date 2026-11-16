"""Cycles stills of round 56's five changes (sect/patch_r56_form.py, docs/scene/form-r56.md), seen from the flight the
way the site shows it, on the GPU (OptiX, then CUDA; it refuses the CPU). Renders only: the .blend is never saved. Run
it on the copy before the patch (--tag before) and after it (--tag after), then compare:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r56.py -- --tag before [--samples 64] \
        [--shots rim_889,rim_889_close,...] [--retarget]

Shots (1600 x 900, the film's field of view; a framed hold as client framing.ts STOP_FRAMING has it):
    rim_889, rim_1069     a terrace's rim from the flight (part A: the teeth where the grass meets the cliff)
    lawn_193              the Heart-Mirror lawn's edge (part B)
    wall_121, wall_1500   a link stairway's side wall near the camera and far off (part C)
    sword_516, sword_469  the Heavy Iron Sword at the arena's hold and on the way in (part D)
    bridge_421, bridge_469  the plank bridge from the forge to the arena island (part E)
    <shot>_close          from the same camera place, a long lens fitted to a box round the thing itself: the rim
                          point, lawn lip point or wall point nearest the camera (or, for wall_1500, nearest the frame's
                          centre) that the camera sees, the sword's parts, the bridge's middle third
The close boxes are worked out on the first run and kept in <out>/targets.json, so the before and after stills frame
the same box (--retarget works them out again). The flyer and the volume objects (haze, cloud banks) are hidden, as in
the other previews. Writes out/tmp/r56/renders/r56_<tag>_<shot>.png (under out/: rblender copies it back to the PC).
"""
import argparse
import json
import math
import os
import re
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402
from sect import world as W  # noqa: E402
from sect.areas import mirror as MR  # noqa: E402
from sect.areas import scroll as SC  # noqa: E402
from sect.lib import refs_east as RE  # noqa: E402
from sect.lib import refs_west as RW  # noqa: E402

RES = (1600, 900)
CAM = "preview.r56.cam"
FILL = 0.85
OUT = os.path.join(ROOT, "out", "tmp", "r56", "renders")
FRAMING = dict(RE.SITE_FRAMING)
FRAMING.update(RW.SITE_FRAMING)
FRAMING[SC.HOLD_FRAME] = (SC.SITE_FRAMING[0], SC.SITE_FRAMING[1], 12)
# shot -> (frame, close target kind, nearest distance, farthest, pick)
SHOTS = dict(
    rim_889=(889, "rim", 25.0, 300.0, "nearest"),
    rim_1069=(1069, "rim", 25.0, 300.0, "nearest"),
    lawn_193=(193, "lawn", 15.0, 250.0, "nearest"),
    wall_121=(121, "wall", 8.0, 120.0, "nearest"),
    wall_1500=(1500, "wall", 60.0, 600.0, "centre"),
    sword_516=(516, "sword", 0.0, 1e9, None),
    sword_469=(469, "sword", 0.0, 1e9, None),
    bridge_421=(421, "bridge", 0.0, 1e9, None),
    bridge_469=(469, "bridge", 0.0, 1e9, None),
)
HALF = dict(rim=(7.0, -6.0, 1.5), lawn=(5.0, -1.0, 1.5), wall=(4.0, -3.0, 1.5))   # box half size, z below / above
WALL_RE = re.compile(r"^world\.link\.[a-z]+_[a-z]+\.(rails|foot_rail|rest_rail)$")
LAWN_LIP_R = 41.5              # m: where the mirror lawn's lip lands (between LAWN_EDGE's r 40 and 43)


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r56.py")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--tag", default="")
    ap.add_argument("--shots", default=",".join(s for k in SHOTS for s in (k, k + "_close")))
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--retarget", action="store_true")
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
        raise SystemExit("preview_r56: no OptiX or CUDA device: refusing to render on the CPU")
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
    hidden = []
    for ob in sc.objects:
        if ob.hide_render or ob.type not in {"MESH", "CURVE", "SURFACE", "META", "FONT", "VOLUME"}:
            continue
        if ob.type == "VOLUME" or any(s.material is not None and s.material.name in vol for s in ob.material_slots):
            ob.hide_render = True
            hidden.append(ob.name)
    return hidden


def site_view(sc, cam, frame):
    """chase.cam's world matrix as the page shows ``frame`` (FRAMING at a framed hold). Sets the scene frame."""
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
        xs.append(q.x / max(-q.z, 1e-3))
        ys.append(q.y / max(-q.z, 1e-3))
    aspect = RES[0] / RES[1]
    half = max(max(abs(x) for x in xs), max(abs(y) for y in ys) * aspect, 1e-4)
    data.sensor_fit = "HORIZONTAL"
    data.sensor_width = 36.0
    data.shift_x = data.shift_y = 0.0
    data.lens = min(18.0 * fill / half, 1200.0)
    cam.matrix_world = Mw
    return data.lens, (centre - eye).length


# ---------------------------------------------------------------------------------------------------- close targets

def rim_points(n=720):
    """Points on every terrace's rim (where the flat ends, Range.fields' rf), at the terrace's height."""
    an = W._norm_anchors(None)
    rng_ = W.Range(an, W._anchor_yaws(None), peak_mode="strata")
    th = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    out = []
    for k, (ax, ay, az, fp) in an.items():
        if k in W.FLOATING:
            continue
        bulge = 6.0 * np.maximum(0.0, rng_.noise(ax + 40.0 * np.cos(th), ay + 40.0 * np.sin(th), 1 / 30.0, o=6))
        rf = np.full(n, W.SUMMIT_FLAT_R) if k == "summit" else fp + W.TERRACE_PAD + bulge
        out.append(np.stack([ax + rf * np.cos(th), ay + rf * np.sin(th), np.full(n, az - 0.4)], axis=1))
    return np.concatenate(out)


def lawn_points(n=720):
    root = bpy.data.objects["mirror.root"]
    M = np.array(root.matrix_world)
    th = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    L = np.stack([LAWN_LIP_R * np.cos(th), LAWN_LIP_R * np.sin(th), np.full(n, MR.TERRACE_Z + 0.2), np.ones(n)],
                 axis=1)
    return (L @ M.T)[:, :3]


def wall_points(step=7):
    pts = []
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or not WALL_RE.match(ob.name):
            continue
        co = np.empty(len(ob.data.vertices) * 3, np.float32)
        ob.data.vertices.foreach_get("co", co)
        M = np.array(ob.matrix_world)
        w = co.reshape(-1, 3).astype(float) @ M[:3, :3].T + M[:3, 3]
        pts.append(w[::step])
    return np.concatenate(pts) if pts else np.zeros((0, 3))


def seen(sc, dg, eye, p, hidden):
    """Does a ray from ``eye`` reach ``p`` (within 1 m), passing through what the stills do not render (the hidden
    volumes, the flyer, anything hidden from renders)?"""
    d = Vector(p) - eye
    dist = d.length
    d.normalize()
    o = eye.copy()
    for _ in range(12):
        hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, o, d, distance=max(dist - (o - eye).length, 1e-3))
        if not hit or (loc - eye).length >= dist - 1.0:
            return True
        src = getattr(ob, "original", ob) if ob is not None else None
        if src is None or not (src.name in hidden or src.hide_render):
            return False
        o = loc + d * 0.05
    return False


def pick_point(sc, dg, Mw, data, pts, dmin, dmax, how, hidden):
    inv = np.array(Mw.inverted())
    eye = Mw.translation.copy()
    L = pts @ inv[:3, :3].T + inv[:3, 3]
    depth = -L[:, 2]
    tx = 0.5 * data.sensor_width / data.lens          # tan of half the horizontal field of view
    ty = tx * RES[1] / RES[0]
    ok = (depth > 1.0)
    ok &= np.abs(L[:, 0] / np.maximum(depth, 1e-3)) < 0.85 * tx
    ok &= np.abs(L[:, 1] / np.maximum(depth, 1e-3)) < 0.85 * ty
    dist = np.linalg.norm(pts - np.array(eye), axis=1)
    ok &= (dist >= dmin) & (dist <= dmax)
    idx = np.nonzero(ok)[0]
    if how == "centre":
        key = np.hypot(L[idx, 0] / depth[idx], L[idx, 1] / depth[idx])
    else:
        key = dist[idx]
    for i in idx[np.argsort(key)][:400]:
        if seen(sc, dg, eye, pts[i], hidden):
            return pts[i], float(dist[i])
    return None, None


def target_box(shot, sc, src, data, hidden):
    frame, kind, dmin, dmax, how = SHOTS[shot]
    Mw = site_view(sc, src, frame)
    data.lens, data.sensor_width = src.data.lens, src.data.sensor_width
    if kind == "sword":
        pts = []
        for ob in bpy.data.objects:
            if ob.name.startswith("arena.sword_") and ob.type == 'MESH':
                pts += [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        if not pts:
            return None
        P = np.array([list(p) for p in pts])
        return dict(lo=P.min(0).tolist(), hi=P.max(0).tolist(), how="the sword's parts")
    if kind == "bridge":
        rng_ = W.Range(W._norm_anchors(None), W._anchor_yaws(None), peak_mode="strata")
        pa, pb = W.port(rng_, "forge", "depart"), W.port(rng_, "arena", "arrival")
        p0, p1 = pa["p"], pb["p"]
        a, b = p0 + (p1 - p0) / 3.0, p0 + 2.0 * (p1 - p0) / 3.0
        sag = max(W.FORGE_ARENA_SAG, W.CHAIN_SAG)
        lo = np.minimum(a, b) - np.array([2.5, 2.5, sag + 1.5])
        hi = np.maximum(a, b) + np.array([2.5, 2.5, 2.5])
        return dict(lo=lo.tolist(), hi=hi.tolist(), how="the bridge's middle third (both sags)")
    pts = dict(rim=rim_points, lawn=lawn_points, wall=wall_points)[kind]()
    dg = bpy.context.evaluated_depsgraph_get()
    p, d = pick_point(sc, dg, Mw, data, pts, dmin, dmax, how, hidden)
    if p is None:
        return None
    h, zlo, zhi = HALF[kind]
    return dict(lo=[p[0] - h, p[1] - h, p[2] + zlo], hi=[p[0] + h, p[1] + h, p[2] + zhi],
                how="%s point %.1f m off (%s)" % (kind, d, how))


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
    hidden = set(hide_volumes(sc))
    log("volume objects hidden", len(hidden))
    tpath = os.path.join(a.out, "targets.json")
    targets = {}
    if os.path.isfile(tpath) and not a.retarget:
        with open(tpath, encoding="utf-8") as f:
            targets = json.load(f)
        log("close boxes from", tpath, sorted(targets))
    data = src.data.copy()
    cam = bpy.data.objects.new(CAM, data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    pre = "r56" + ("_" + a.tag if a.tag else "")
    made = []
    try:
        for shot in shots:
            base, close = (shot[:-6], True) if shot.endswith("_close") else (shot, False)
            if base not in SHOTS:
                log("WARN unknown shot", shot)
                continue
            frame = SHOTS[base][0]
            Mw = site_view(sc, src, frame)
            data.lens, data.sensor_width, data.sensor_height = src.data.lens, src.data.sensor_width, \
                src.data.sensor_height
            data.sensor_fit = src.data.sensor_fit
            data.shift_x, data.shift_y = src.data.shift_x, src.data.shift_y
            data.clip_start, data.clip_end = src.data.clip_start, src.data.clip_end
            if not close:
                cam.matrix_world = Mw
                info = "site framing %s" % (FRAMING.get(frame, (0.0, 0.0, 0)),)
            else:
                if base not in targets:
                    tb = target_box(base, sc, src, data, hidden)
                    if tb is None:
                        log("WARN no close target for", shot)
                        continue
                    targets[base] = tb
                    with open(tpath, "w", encoding="utf-8") as f:
                        json.dump(targets, f, indent=1)
                    Mw = site_view(sc, src, frame)
                tb = targets[base]
                lo, hi = tb["lo"], tb["hi"]
                pts = [Vector((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
                lens, dist = fit_close(cam, data, Mw.translation.copy(), pts)
                info = "%s; lens %.0f mm, %.1f m to the box's centre" % (tb["how"], lens, dist)
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
