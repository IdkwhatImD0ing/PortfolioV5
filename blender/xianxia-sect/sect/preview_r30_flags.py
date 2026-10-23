"""Cycles stills of the formation's Five Element Banners 五行旗 for round 30 (sect/patch_r30_flags.py), seen the way the
site shows the stop, on the GPU (OptiX, then CUDA; it refuses the CPU). Renders only: the .blend is never saved.

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r30_flags.py -- [--samples 64] [--tag before] \
        [--shots hold,close,front] [--trials A,B] [--exposure 1.2] [--out DIR]

Shots (frame 1208, the formation's hold):
    hold    chase.cam with the site's stop framing (client framing.ts STOP_FRAMING.formation: pitch -8 deg, no yaw, no
            step back), 1600 x 900, the film's field of view (16:9 is the film's own aspect)
    close   from the same camera position, a long lens fitted to the five flags' cloths (1600 x 900)
    front   each cloth alone, orthographic, from the side its normal points to (the side a bake lights), 600 x 600
--trials renders the listed shots once per named trial palette (TRIALS: the candidates round 30 compared; the
choice is lib/element_flags.py, trial N's earth with D's wood), each flag's cloth slots pointed at temporary materials;
nothing is saved. --exposure 1.2 matches the bake's post (bake_web.py --exposure), for the 'front' tiles, which pass
through a copy of the site's grade (client look.ts gradeLinear) to show what the page will draw. The flyer, volume
objects (haze, cloud banks) and the formation's dome are hidden, as in the other previews (the page draws its own haze
and barrier). Writes <out>/r30_flags_<tag>_<shot>[_<trial>].png (default out: out/preview; front: one per flag).
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
from sect.lib import element_flags as EF  # noqa: E402
from sect.lib import materials as M  # noqa: E402
from sect.lib import util as U  # noqa: E402

HOLD = 1208
PITCH = -8.0            # client/src/lib/sect/framing.ts STOP_FRAMING.formation (yaw 0, no back)
RES = (1600, 900)
CAM = "preview.r30_flags.cam"
FILL = 0.86             # close: the five cloths span this share of the frame's width (or height)

# trial palettes: element -> (cloth hex, translucency, sheen, teeth, character); teeth / character: a registered
# material name or a hex (a temporary cloth). Used only with --trials.
GOLD, INK, MOON, INDIGO = "cloth_gold", "banner_7", "banner_5", "banner_4"
TRIALS = {
    "A": {"wood": ("#2a7f3f", 0.34, 0.5, GOLD, GOLD), "fire": ("#b0261b", 0.38, 0.5, GOLD, GOLD),
          "earth": ("#e0ae12", 0.38, 0.5, INK, INK), "metal": ("#e4e2da", 0.38, 0.5, INK, INK),
          "water": ("#151a24", 0.15, 0.5, GOLD, GOLD)},
    "B": {"wood": ("#1f7a3a", 0.34, 0.5, GOLD, GOLD), "fire": ("#c0301c", 0.38, 0.5, GOLD, GOLD),
          "earth": ("#f0c020", 0.38, 0.5, INK, INK), "metal": ("#ecebe6", 0.38, 0.5, INK, INK),
          "water": ("#10141c", 0.15, 0.5, MOON, MOON)},
    "C": {"wood": ("#3a8c2c", 0.34, 0.5, GOLD, GOLD), "fire": ("#a8231c", 0.38, 0.5, GOLD, GOLD),
          "earth": ("#d9a40c", 0.38, 0.5, INK, INK), "metal": ("#e3ddd0", 0.38, 0.5, INK, INK),
          "water": ("#0e1420", 0.15, 0.5, INDIGO, MOON)},
    "D": {"wood": ("#2e8b57", 0.34, 0.5, GOLD, GOLD), "fire": ("#b0261b", 0.38, 0.5, GOLD, GOLD),
          "earth": ("#e8b923", 0.38, 0.5, INK, INK), "metal": ("#e4e2da", 0.38, 0.5, INK, INK),
          "water": ("#151a24", 0.15, 0.5, "#151a24", GOLD)},
}
_BASE = {"wood": ("#2e8b57", 0.34, 0.5, GOLD, GOLD), "fire": ("#a8231c", 0.38, 0.5, GOLD, GOLD),
         "metal": ("#ecebe6", 0.38, 0.5, INK, INK), "water": ("#10141c", 0.15, 0.5, INDIGO, GOLD)}
for _t, _e in (("E", "#e6b800"), ("F", "#d9b000"), ("G", "#f2c200"), ("H", "#e8b000"), ("I", "#c9a000")):
    TRIALS[_t] = dict(_BASE, earth=(_e, 0.38, 0.5, INK, INK))
for _t, _e, _tr, _sh in (("J", "#d4c000", 0.38, 0.5), ("K", "#c8b400", 0.38, 0.5), ("L", "#d9b000", 0.2, 0.3),
                          ("M", "#d4c000", 0.2, 0.3), ("N", "#dcc800", 0.25, 0.3), ("O", "#e0c800", 0.3, 0.4)):
    TRIALS[_t] = dict(_BASE, earth=(_e, _tr, _sh, INK, INK))


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r30_flags.py")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--tag", default="")
    ap.add_argument("--shots", default="hold,close")
    ap.add_argument("--trials", default="")
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "preview"))
    ap.add_argument("--exposure", type=float, default=None, help="view exposure (the bake's post uses 1.2)")
    return ap.parse_args(argv)


def facing(cam_loc):
    """Per flag: the cloth's mean world normal (its faces' +Z side, the side a bake lights) and whether the hold camera
    sees that side."""
    out = {}
    dg = bpy.context.evaluated_depsgraph_get()
    for key in EF.ORDER:
        ob = cloth_of(key)
        me = ob.evaluated_get(dg).to_mesh()
        n = Vector()
        c = Vector()
        for p in me.polygons:
            n += p.normal * p.area
            c += p.center * p.area
        a = sum(p.area for p in me.polygons)
        ob.evaluated_get(dg).to_mesh_clear()
        R = ob.matrix_world.to_3x3()
        nw = (R @ n).normalized()
        cw = ob.matrix_world @ (c / a)
        out[key] = (nw, cw, nw.dot((cam_loc - cw).normalized()))
    return out


def front_tiles(sc, cam, data, a, pre, trial, face):
    """Each cloth on its own from the side its normal points to (the side the bake lights): an orthographic camera
    9 m out along the normal, near clip at 7.4 m so nothing behind the cloth hides it (the light is the scene's).
    Writes one tile per flag (600 x 600, 7.2 m across)."""
    paths = []
    data.type = 'ORTHO'
    data.ortho_scale = 7.2
    data.clip_start, data.clip_end = 7.4, 12.0
    data.shift_x = data.shift_y = 0.0
    keep = sc.render.resolution_x, sc.render.resolution_y
    sc.render.resolution_x, sc.render.resolution_y = 600, 600
    try:
        for key in EF.ORDER:
            nw, cw, _d = face[key]
            eye = cw + nw * 9.0
            rot = (cw - eye).to_track_quat('-Z', 'Y').to_matrix().to_4x4()
            rot.translation = eye
            cam.matrix_world = rot
            p = os.path.join(a.out, "%s_front_%s%s.png" % (pre, key, "_" + trial if trial else ""))
            sc.render.filepath = p
            bpy.ops.render.render(write_still=True)
            paths.append(p)
            log("wrote", p, "orthographic from the normal side")
    finally:
        data.type = 'PERSP'
        sc.render.resolution_x, sc.render.resolution_y = keep
    return paths


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
        raise SystemExit("preview_r30_flags: no OptiX or CUDA device: refusing to render on the CPU")
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


def cloth_of(key):
    root = bpy.data.objects.get("formation.flag." + key)
    if root is None:
        raise RuntimeError("formation.flag.%s not found" % key)
    cl = [c for c in root.children if c.name.startswith(root.name + ".cloth")]
    if len(cl) != 1:
        raise RuntimeError("formation.flag.%s has %d cloths" % (key, len(cl)))
    return cl[0]


def trial_mat(trial, key, part, spec, tr=0.38, sheen=0.5):
    if not spec.startswith("#"):
        return M.get(spec)
    name = "r30trial_%s_%s_%s" % (trial, key, part)
    if not M.has(name):
        M.register(name, M._cloth, colour=spec, translucency=tr, sheen=sheen)
    return M.get(name)


def apply_trial(trial):
    pal = TRIALS[trial]
    for key in EF.ORDER:
        col, tr, sheen, teeth, char = pal[key]
        cl = cloth_of(key)
        U.set_object_material(cl, trial_mat(trial, key, "cloth", col, tr, sheen), 0)
        U.set_object_material(cl, trial_mat(trial, key, "teeth", teeth), 1)
        U.set_object_material(cl, trial_mat(trial, key, "char", char), 2)
    log("trial", trial, " ".join("%s %s/%s/%s" % (k, pal[k][0], pal[k][3], pal[k][4]) for k in EF.ORDER))


def hold_view(src):
    """chase.cam's world matrix at the current frame turned by the stop framing (free-look.ts composeLook: yaw about
    world up, then pitch about the camera's own right axis)."""
    Mw = src.matrix_world.copy()
    loc = Mw.translation.copy()
    R = Mw.to_3x3().normalized() @ Matrix.Rotation(math.radians(PITCH), 3, 'X')
    out = R.to_4x4()
    out.translation = loc
    return out


def fit_close(cam, data, sc, eye):
    """Aim from ``eye`` at the five cloths' world boxes and set the lens so they span FILL of the frame."""
    pts = []
    for key in EF.ORDER:
        ob = cloth_of(key)
        pts += [ob.matrix_world @ Vector(c) for c in ob.bound_box]
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
    data.lens = 18.0 * FILL / half
    cam.matrix_world = Mw
    return data.lens, (centre - eye).length


def main():
    a = args()
    sc = bpy.context.scene
    src = bpy.data.objects.get(EW.CAMERA)
    if src is None:
        raise RuntimeError("no %s" % EW.CAMERA)
    os.makedirs(a.out, exist_ok=True)
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    log("volume objects hidden", hide_volumes(sc))
    for ob in bpy.data.objects:
        if ob.name == "formation.dome" or ob.name.startswith("formation.dome."):
            ob.hide_render = True
    for key in EF.ORDER:
        cl = cloth_of(key)
        log("flag", key, "slots", [s.material.name if s.material else None for s in cl.material_slots])
    if a.exposure is not None:
        sc.view_settings.exposure = a.exposure
        log("view exposure", a.exposure)
    data = src.data.copy()
    cam = bpy.data.objects.new(CAM, data)
    sc.collection.objects.link(cam)
    sc.frame_set(HOLD)
    face = facing(src.matrix_world.translation.copy())
    for key in EF.ORDER:
        nw, cw, d = face[key]
        log("facing", key, "normal %s, centre %s, cos to the hold camera %.3f (%s side seen)" % (
            tuple(round(v, 3) for v in nw), tuple(round(v, 2) for v in cw), d, "front (+Z)" if d > 0 else "back (-Z)"))
    shots = [s.strip() for s in a.shots.split(",") if s.strip()]
    trials = [t.strip() for t in a.trials.split(",") if t.strip()] or [None]
    pre = "r30_flags" + ("_" + a.tag if a.tag else "")
    made = []
    try:
        sc.frame_set(HOLD)
        sc.camera = cam
        sc.render.resolution_x, sc.render.resolution_y = RES
        for trial in trials:
            if trial is not None:
                apply_trial(trial)
            for shot in shots:
                data.shift_x, data.shift_y = src.data.shift_x, src.data.shift_y
                data.clip_start, data.clip_end = src.data.clip_start, src.data.clip_end
                if shot == "front":
                    made += front_tiles(sc, cam, data, a, pre, trial, face)
                    continue
                if shot == "hold":
                    data.lens, data.sensor_width, data.sensor_height = src.data.lens, src.data.sensor_width, \
                        src.data.sensor_height
                    data.sensor_fit = src.data.sensor_fit
                    cam.matrix_world = hold_view(src)
                    info = "pitch %.1f deg, lens %.1f mm" % (PITCH, data.lens)
                elif shot == "close":
                    lens, dist = fit_close(cam, data, sc, src.matrix_world.translation.copy())
                    info = "lens %.0f mm, %.1f m to the flags' centre" % (lens, dist)
                else:
                    log("WARN unknown shot", shot)
                    continue
                sc.render.filepath = os.path.join(a.out, "%s_%s%s.png" % (pre, shot, "_" + trial if trial else ""))
                t0 = time.time()
                bpy.ops.render.render(write_still=True)
                made.append(sc.render.filepath)
                log("wrote", sc.render.filepath, "frame", HOLD, "%dx%d" % RES, info, "%.1f s" % (time.time() - t0))
    finally:
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(data)
    log("done", len(made), "stills; the .blend was not saved")


main()
