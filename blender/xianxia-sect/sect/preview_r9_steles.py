"""Cycles stills of the Jin Yong stele manuals (sect/patch_r9_steles.py): the 974 hold and close views of a few
steles, to see the glyph columns read from the hold and every manual carved whole and legible up close. CPU (the GPU
may be baking), low samples. Renders only; the .blend is not saved.

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r9_steles.py [-- --samples 16 --tag after]

Writes out/preview/r9_steles[_<tag>]_<shot>.png (rblender copies them back):
    hold        chase.cam at the stele hold (974), 1600 x 900: what the reader sees
    approach    chase.cam at 950 (flying up the aisle)
    r0e         row 0 east inner stele (降龍十八掌), square on, whole face and crown
    r0w         row 0 west inner (打狗棒法)
    r0w2        row 0 west outer (天罡北斗陣: each star and its Quanzhen master)
    r4w2        row 4 west outer (沖靈劍法)
    r1w        row 1 west inner (乾坤大挪移)
    r1e2        row 1 east outer (黯然銷魂掌)
    r2e         row 2 east outer (獨孤九劍)
    r2w2        row 2 west outer (劍塚, the densest)
    master      the gold master stele under the pavilion (華山論劍)
    crown       the crown panel of r0e, close
    back        the back of r0e (the novel and the master)
Close views are placed in each stele's own frame (front = -Y, props.stele_glyph_plan), so they follow the stele; when
something stands between (a corner pavilion's roof in front of row 0) the camera moves in past it with a wider lens.
Options: --samples 16, --tag x, --shots hold,r0e,..., --threads 16 (CPU threads), --volumes (keep mist volumes).
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
from sect.areas import steles as ST  # noqa: E402
from sect.lib import look as L  # noqa: E402
from sect.lib import props as P  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
HOLD, APPROACH = 974, 950
CAM = "preview.r9_steles.cam"
SHOTS = ("hold", "approach", "r0e", "r0w", "r1w", "r1e2", "r2e", "r2w2", "master", "crown", "back")
# shot -> (instancer, view): face = whole front and crown, crown = title panel close, back = back face
CLOSE = {"r0e": ("steles.stele.r0.001", "face"), "r0w": ("steles.stele.r0", "face"),
         "r0w2": ("steles.stele.r0.002", "face"), "r4w2": ("steles.stele.r4.002", "face"),
         "r1w": ("steles.stele.r1", "face"), "r1e2": ("steles.stele.r1.003", "face"),
         "r2e": ("steles.stele.r2.003", "face"), "r2w2": ("steles.stele.r2.002", "face"),
         "master": ("steles.stele_master", "face"), "crown": ("steles.stele.r0.001", "crown"),
         "back": ("steles.stele.r0.001", "back")}


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r9_steles.py")
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--tag", default="")
    ap.add_argument("--shots", default=",".join(SHOTS))
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--volumes", action="store_true", help="keep volume objects (slower)")
    return ap.parse_args(argv)


def setup_cycles(sc, samples, threads):
    """CPU on purpose: the box's GPU may be running the bake."""
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
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
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False
    log("cycles CPU, threads", sc.render.threads, "samples", samples)


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


def manual_of(inst_name):
    """(manual, height) carved on a stele instancer, as steles.build hands them out."""
    by = {m["title"]: m for m in P.JIN_YONG_MANUALS}
    if inst_name == "steles.stele_master":
        return by[ST.MASTER_MANUAL], ST.MASTER_H
    ob = bpy.data.objects[inst_name]
    p = ob.parent.matrix_world.inverted() @ ob.matrix_world.translation
    r = min(range(len(ST.ROWS_Y)), key=lambda k: abs(p.y - ST.ROWS_Y[k]))
    c = min(range(len(ST.COLS_X)), key=lambda k: abs(abs(p.x) - ST.COLS_X[k]))
    return by[ST.STELE_MANUALS[r][c][0 if p.x < 0 else 1]], ST.ROW_H[r]


def close_view(inst_name, view):
    """(camera, target, lens, (w, h)) in world space for a close view of one stele."""
    ob = bpy.data.objects[inst_name]
    manual, h = manual_of(inst_name)
    plan = P.stele_glyph_plan(h, True, manual)
    M = ob.matrix_world
    face = [g for g in plan["glyphs"] if g["face"] == ("back" if view == "back" else "front")]
    crown = [g for g in plan["glyphs"] if g["face"] == "crown"]
    pts = face + (crown if view == "face" else [])
    if view == "crown":
        pts = crown
    zs = [g["centre"].z for g in pts]
    xs = [g["centre"].x for g in pts]
    pad = max(g["cell"] for g in pts)
    z0, z1 = min(zs) - pad, max(zs) + pad
    x0, x1 = min(xs) - pad, max(xs) + pad
    y = pts[0]["centre"].y
    nrm = pts[0]["normal"]
    tgt = Vector(((x0 + x1) / 2, y, (z0 + z1) / 2))
    lens = 50.0 if view == "face" else 60.0
    tall = max(z1 - z0, (x1 - x0) * 9 / 16) * (1.18 if view == "face" else 1.4)
    sensor_h = 36.0 * 9 / 16                  # sensor 36 mm wide, 16:9
    dist = tall / (sensor_h / lens)
    eye = tgt + nrm * dist + Vector((0, 0, 0.15 * dist if view == "face" else 0.0))
    eye_w, tgt_w = M @ eye, M @ tgt
    # something in the way (a corner pavilion's roof in front of row 0)? stand just this side of it, wider lens
    clear = free_distance(tgt_w, eye_w)
    if clear < (eye_w - tgt_w).length:
        k = max(0.25, (clear - 0.5) / (eye_w - tgt_w).length)
        eye_w = tgt_w + (eye_w - tgt_w) * k
        lens = max(14.0, lens * k)
        log("close", inst_name, "view blocked at %.1f m: camera moved in to %.0f %%, lens %.0f mm" % (clear, 100 * k, lens))
    log("close", inst_name, view, manual["title"], "dist %.1f m (world)" % (eye_w - tgt_w).length)
    return eye_w, tgt_w, lens, (1600, 900)


def free_distance(a, b):
    """Distance from ``a`` toward ``b`` to the first rendered surface (objects hidden from render are skipped)."""
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    d = (b - a)
    total = d.length
    d.normalize()
    o, travelled = a + d * 0.05, 0.05
    for _ in range(32):
        hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, o, d, distance=total - travelled)
        if not hit:
            return total
        travelled += (loc - o).length
        if ob is not None and not ob.original.hide_render:
            return travelled
        o = loc + d * 0.01
        travelled += 0.01
    return travelled


def main():
    a = args()
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    setup_cycles(sc, a.samples, a.threads)
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    pre = "r9_steles" + ("_" + a.tag if a.tag else "")
    made, tmp = [], None
    try:
        for shot in [s.strip() for s in a.shots.split(",") if s.strip()]:
            if shot in ("hold", "approach"):
                cam = bpy.data.objects.get(EW.CAMERA)
                if cam is None:
                    log("WARN no", EW.CAMERA)
                    continue
                frame, res = {"hold": HOLD, "approach": APPROACH}[shot], (1600, 900)
            elif shot in CLOSE:
                inst, view = CLOSE[shot]
                if bpy.data.objects.get(inst) is None:
                    log("WARN no", inst)
                    continue
                eye, tgt, lens, res = close_view(inst, view)
                if tmp is not None:
                    cd = tmp.data
                    bpy.data.objects.remove(tmp, do_unlink=True)
                    bpy.data.cameras.remove(cd)
                cam = tmp = L.camera_look_at(CAM, eye, tgt, lens=lens, collection=sc.collection)
                cam.data.clip_start = 0.05
                frame = HOLD
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
