"""Round 48: Cycles preview stills of chase.cam (B0 variants, the slice, the range-wide build). Renders only; the .blend
is never saved. They catch placement mistakes (shapes, shelves, plants on walls, islands, falls), not web tells.

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<file>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r48.py -- \
        --label b0_b --shots 870,1103,870@30,1103@-25 [--samples 24] [--res 1280x720] [--zoom 1.0]

--shots: frame[@yaw degrees][~zoom], comma separated; holds and flights by name too ('holds' = the eleven hold frames,
'between' = 150,285,570,700,870,1040,1160,1300). The camera is chase.cam at that frame, turned yaw degrees about the
world's up axis (positive = left), its lens times zoom. Writes out/tmp/r48/stills/<label>_<frame>[_y<yaw>][_z<zoom>]
.png (rblender.py copies them back to the PC). Cycles on the GPU only (OptiX, else CUDA; it stops on the CPU) at
--samples with the denoiser, the web's clip planes (0.5 / 9000 m), the flyer and the volume puffs hidden (the web
draws its own mist). The first line it prints is 'PREVIEW cycles device <OPTIX|CUDA>'.
--at name=x,y,z:tx,ty,tz[:lens mm];...: extra stills from a free camera at x,y,z looking at tx,ty,tz (world
metres; e.g. a low look at a pillar's foot, or a near tree), written as <label>_at_<name>.png.
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

OUT = os.path.join(ROOT, "out", "tmp", "r48", "stills")
HOLDS = (93, 217, 352, 516, 619, 772, 974, 1103, 1208, 1380, 1647)
BETWEEN = (150, 285, 570, 700, 870, 1040, 1160, 1300)


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r48.py")
    ap.add_argument("--label", default="still")
    ap.add_argument("--shots", default="holds")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--zoom", type=float, default=1.0)
    ap.add_argument("--at", default="")
    return ap.parse_args(argv)


def shots(spec):
    out = []
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok == "holds":
            out += [(f, 0.0, 1.0) for f in HOLDS]
            continue
        if tok == "between":
            out += [(f, 0.0, 1.0) for f in BETWEEN]
            continue
        zoom = 1.0
        if "~" in tok:
            tok, z = tok.split("~")
            zoom = float(z)
        yaw = 0.0
        if "@" in tok:
            tok, y = tok.split("@")
            yaw = float(y)
        out.append((int(tok), yaw, zoom))
    return out


def setup(sc, samples, res):
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    dev = None
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == kind]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == kind
                dev = kind
                break
        except TypeError:
            continue
    if dev is None:
        raise SystemExit("preview_r48: no GPU device, refusing to render on the CPU")
    log("cycles device", dev)
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
    w, h = (int(x) for x in res.lower().split("x"))
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False
    vol = {m.name for m in bpy.data.materials
           if m.node_tree is not None and any(n.bl_idname.startswith("ShaderNodeVolume") for n in m.node_tree.nodes)}
    nh = 0
    for ob in sc.objects:
        if ob.hide_render or ob.type not in {"MESH", "CURVE", "SURFACE", "META", "FONT", "VOLUME"}:
            continue
        if ob.type == "VOLUME" or any(s.material is not None and s.material.name in vol for s in ob.material_slots):
            ob.hide_render = True
            nh += 1
    log("flyer hidden", EW.hide_flyer(sc), "volumes hidden", nh, "samples", samples, "res", res)


def main():
    a = args()
    sc = bpy.context.scene
    cam = bpy.data.objects[EW.CAMERA]
    setup(sc, a.samples, a.res)
    os.makedirs(OUT, exist_ok=True)
    shot_cam = bpy.data.objects.new("r48.preview.cam", cam.data.copy())
    sc.collection.objects.link(shot_cam)
    shot_cam.data.clip_start, shot_cam.data.clip_end = 0.5, 9000.0
    sc.camera = shot_cam
    lens0 = cam.data.lens
    t0 = time.time()
    for f, yaw, zoom in shots(a.shots):
        sc.frame_set(f)
        M = EW.sample_matrices(cam, [f])[0]
        loc = M.to_translation()
        R = Matrix.Rotation(math.radians(yaw), 4, 'Z')
        shot_cam.matrix_world = Matrix.Translation(loc) @ R @ Matrix.Translation(-loc) @ M
        shot_cam.data.lens = lens0 * zoom * a.zoom
        name = "%s_%04d%s%s.png" % (a.label, f, "_y%+d" % int(yaw) if yaw else "",
                                    "_z%g" % (zoom * a.zoom) if zoom * a.zoom != 1.0 else "")
        sc.render.filepath = os.path.join(OUT, name)
        t1 = time.time()
        bpy.ops.render.render(write_still=True)
        log("still", name, "%.1f s" % (time.time() - t1))
    n_at = 0
    for tok in [t for t in a.at.split(";") if t.strip()]:
        name, rest = tok.split("=", 1)
        parts = rest.split(":")
        pos = Vector([float(x) for x in parts[0].split(",")])
        tgt = Vector([float(x) for x in parts[1].split(",")])
        shot_cam.matrix_world = Matrix.Translation(pos) @ (tgt - pos).to_track_quat('-Z', 'Y').to_matrix().to_4x4()
        shot_cam.data.lens = float(parts[2]) if len(parts) > 2 else lens0
        nm = "%s_at_%s.png" % (a.label, name.strip())
        sc.render.filepath = os.path.join(OUT, nm)
        t1 = time.time()
        bpy.ops.render.render(write_still=True)
        log("still", nm, "%.1f s" % (time.time() - t1))
        n_at += 1
    log("done", len(shots(a.shots)) + n_at, "stills in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
