r"""Before / after stills for round 12, lane 'libs' (sect/patch_r12_libs.py): close views of the pieces whose faces lay
within a few mm of each other, seen from the side the camera path sees them from. Renders only; the .blend is never
saved.

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<unpatched copy>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r12_libs.py -- --tag before
    python .../rblender.py -b E:/.../out/<patched copy>.blend --python-exit-code 1 \
        --python E:/.../sect/preview_r12_libs.py -- --tag after

Each shot looks at a target (an object's bounding-box centre, or one vertex of a mesh) from DIST metres, along the line
to where the chase camera passes nearest to it (its frame is set too, so waving cloth matches between runs). Cycles on
the GPU (refuses the CPU), --samples 24, 1280 x 720, clip 0.5 / 9000 m like the web. For every shot the patch's scanner
also looks at the faces within RADIUS of the target and the run writes a _mark copy with a magenta dot on every spot
where two faces lie within 12 mm of each other and the camera sees it: the after stills should have none or few.
Output: out/preview/r12_libs_<tag>_<id>.png and _mark.png, and out/preview/r12_libs_<tag>.json (seen overlap per shot).

Options: --shots id,id (default all), --no-render (marks and counts only), --samples N, --replan (work the views
out again; else the first run's out/preview/r12_libs_shots.json is reused, so before and after match).
"""
import argparse
import json
import math
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
from sect import patch_r12_libs as PL  # noqa: E402
from sect.lib import look as L  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
RES = (1280, 720)

# id: (target, distance m, scan radius m, lens mm, highest view elevation in degrees or None). target "obj"
# (bounding-box centre; for an instance its instanced meshes) or "vert:obj:i" (vertex i of obj's mesh, world space).
# The view looks from the side of the camera path's nearest point, tipped down to the elevation cap (walls, beams and
# lanterns are seen from the side).
SHOTS = {
    "gate_ring": ("vert:gate.rune_ring:0", 7.0, 2.5, 35.0, None),
    "summit_ring": ("vert:summit.ring:0", 8.0, 3.0, 35.0, None),
    "formation_leak": ("vert:formation.bagua_leak:0", 8.0, 3.0, 35.0, None),
    "steles_corner": ("vert:steles.lang.floor.001:4", 7.0, 3.0, 35.0, None),
    "steles_post": ("vert:steles.lang.floor.001:5", 6.0, 2.5, 35.0, None),
    "gate_paifang": ("gate.paifang", 30.0, 9.0, 35.0, 20.0),
    "mission_hall": ("mission.hall.frieze", 16.0, 6.0, 35.0, 20.0),
    "forge_hall": ("forge.hall.walls", 18.0, 6.0, 35.0, 30.0),
    "library_pagoda": ("library.pagoda.walls", 26.0, 7.0, 35.0, 30.0),
    "study_door": ("library.study_east", 12.0, 5.0, 35.0, 15.0),
    "arena_banner": ("arena.banner.001.cloth", 6.0, 2.5, 35.0, 20.0),
    "library_book": ("library.book", 2.5, 1.0, 35.0, None),
    "scroll_slips": ("scroll.slips", 4.0, 2.0, 35.0, None),
    "gate_lantern": ("gate.lantern", 5.0, 2.0, 35.0, 20.0),
    "gate_lion": ("gate.lion", 6.0, 2.5, 35.0, 20.0),
    "forge_anvil": ("forge.anvil", 3.0, 1.2, 35.0, None),
    "library_scroll": ("library.scroll", 3.0, 1.2, 35.0, None),
}
SHOTS_JSON = os.path.join(OUT, "r12_libs_shots.json")


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r12_libs.py")
    ap.add_argument("--tag", default="before")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--shots", default=",".join(SHOTS))
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--replan", action="store_true", help="work the views out again (else reuse %s)" % SHOTS_JSON)
    return ap.parse_args(argv)


_CAM = None


def camera_path():
    """chase.cam positions over the web timeline (export_web's full profile) and their frames."""
    global _CAM
    if _CAM is None:
        EW.use_profile("full")
        cam = bpy.data.objects[EW.CAMERA]
        fr = list(range(EW.FRAMES[0], EW.FRAMES[1] + 1))
        mats = EW.sample_matrices(cam, fr)
        _CAM = (np.array([[m[0][3], m[1][3], m[2][3]] for m in mats]), np.array(fr))
    return _CAM


def target_point(spec, dg):
    if spec.startswith("vert:"):
        _v, name, i = spec.split(":")
        ob = bpy.data.objects[name]
        return np.array(ob.matrix_world @ ob.data.vertices[int(i)].co)
    ob = bpy.data.objects[spec]
    pts = []
    for inst in dg.object_instances:
        o = inst.object
        par = inst.parent.original if (inst.is_instance and inst.parent) else None
        if not ((inst.is_instance and par is not None and par.name == ob.name) or
                (not inst.is_instance and o.original.name == ob.name)):
            continue
        M = np.array(inst.matrix_world)
        pts.append(np.array([tuple(c) for c in o.bound_box]) @ M[:3, :3].T + M[:3, 3])
    if not pts:
        lo, hi = PL.world_box(ob)
        return 0.5 * (lo + hi)
    P = np.concatenate(pts)
    return 0.5 * (P.min(0) + P.max(0))


def setup(sc, samples):
    sc.render.engine = "CYCLES"
    dev = "CPU"
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
                break
        except TypeError:
            continue
    sc.cycles.device = dev
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = True
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
    vol = {m.name for m in bpy.data.materials
           if m.node_tree is not None and any(n.bl_idname.startswith("ShaderNodeVolume") for n in m.node_tree.nodes)}
    nh = 0
    for ob in sc.objects:
        if ob.hide_render or ob.type not in {"MESH", "CURVE", "SURFACE", "META", "FONT", "VOLUME"}:
            continue
        if ob.type == "VOLUME" or any(s.material is not None and s.material.name in vol for s in ob.material_slots):
            ob.hide_render = True
            nh += 1
    log("cycles", dev, samples, "flyer hidden", EW.hide_flyer(sc), "volumes hidden", nh)
    return dev


def seen_overlaps(dg, tgt, radius, eye):
    """Sample points of visible overlaps (two faces within 12 mm) within radius of tgt that the eye sees."""
    lo, hi = tgt - radius, tgt + radius
    T, lab = PL.gather_world(dg, [(lo, hi)], pad=0.0)
    if not len(T):
        return [], 0.0
    S = PL.Scene3(T, lab)
    c = T.mean(1)
    subj = np.all(np.abs(c - tgt) <= radius, axis=1)
    res, bands = PL.scan(S, subj, step=0.01, max_samples=150000, details=True)
    pts = []
    area = 0.0
    for (a, b, kind, band), v in res.items():
        if band > 1:
            continue
        area += v[0]
        for p, g, n in v[2]:
            p = np.asarray(p, float)
            d = p - eye
            dist = float(np.linalg.norm(d))
            if dist < 1e-6:
                continue
            hit = S.bvh.ray_cast(Vector(eye), Vector(d / dist), dist - 0.02)
            if hit[0] is None:
                pts.append(p)
    return pts, area


def mark(path, pix, out_path):
    im = bpy.data.images.load(path)
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
    yy, xx = np.mgrid[0:h, 0:w]
    dot = np.zeros((h, w), bool)
    for x, y in pix:
        x0, x1, y0, y1 = int(max(0, x - 4)), int(min(w, x + 5)), int(max(0, y - 4)), int(min(h, y + 5))
        if x0 >= x1 or y0 >= y1:
            continue
        sub = (xx[y0:y1, x0:x1] - x) ** 2 + (yy[y0:y1, x0:x1] - y) ** 2 <= 9.0
        dot[y0:y1, x0:x1] |= sub
    a[dot] = (1.0, 0.0, 1.0, 1.0)
    im.pixels[:] = a.reshape(-1)
    im.filepath_raw = out_path
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def main():
    from bpy_extras.object_utils import world_to_camera_view
    a = args()
    ids = [x.strip() for x in a.shots.split(",") if x.strip()]
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    if not a.no_render:
        if setup(sc, a.samples) != "GPU":
            raise SystemExit("preview_r12_libs: no GPU, refusing to render on the CPU")
    plans = {}
    if not a.replan and os.path.exists(SHOTS_JSON):
        with open(SHOTS_JSON) as f:
            plans = json.load(f)
    summary = {}
    cam_ob = None
    for sid in ids:
        t0 = time.time()
        spec, dist, radius, lens, el_max = SHOTS[sid]
        if sid not in plans:
            cam_path, frames = camera_path()
            dg = bpy.context.evaluated_depsgraph_get()
            tgt = target_point(spec, dg)
            k = int(np.argmin(np.linalg.norm(cam_path - tgt, axis=1)))
            fr = int(frames[k])
            sc.frame_set(fr)
            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            tgt = target_point(spec, dg)
            v = cam_path[k] - tgt
            v = v / max(np.linalg.norm(v), 1e-9)
            if el_max is not None and math.asin(max(-1.0, min(1.0, v[2]))) > math.radians(el_max):
                h = np.array([v[0], v[1], 0.0])
                h = h / max(np.linalg.norm(h), 1e-9)
                v = h * math.cos(math.radians(el_max)) + np.array([0.0, 0.0, math.sin(math.radians(el_max))])
            plans[sid] = dict(frame=fr, target=tgt.tolist(), eye=(tgt + v * dist).tolist(),
                              path_dist=float(np.linalg.norm(cam_path[k] - tgt)))
            with open(SHOTS_JSON, "w") as f:
                json.dump(plans, f, indent=1)
        pl = plans[sid]
        fr = int(pl["frame"])
        sc.frame_set(fr)
        bpy.context.view_layer.update()
        tgt = np.array(pl["target"], float)
        eye = np.array(pl["eye"], float)
        if cam_ob is not None:
            cd = cam_ob.data
            bpy.data.objects.remove(cam_ob, do_unlink=True)
            bpy.data.cameras.remove(cd)
        cam_ob = L.camera_look_at("r12l.shot.cam", Vector(eye), Vector(tgt), lens=lens, collection=sc.collection)
        cam_ob.data.clip_start = 0.5
        cam_ob.data.clip_end = 9000.0
        sc.camera = cam_ob
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        pts, area = seen_overlaps(dg, tgt, radius, eye)
        pix = []
        for p in pts:
            q = world_to_camera_view(sc, cam_ob, Vector(p))
            if q.z > 0 and 0 <= q.x <= 1 and 0 <= q.y <= 1:
                pix.append((q.x * RES[0], q.y * RES[1]))
        summary[sid] = dict(target=spec, frame=fr, path_dist=pl["path_dist"], overlap_m2=round(area, 4),
                            seen_points=len(pix))
        if not a.no_render:
            path = os.path.join(OUT, "r12_libs_%s_%s.png" % (a.tag, sid))
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)
            mark(path, pix, path.replace(".png", "_mark.png"))
        log("shot", sid, "frame", fr, "path %.0f m" % summary[sid]["path_dist"], "overlap within %.1f m: %.3f m2" %
            (radius, area), "seen dots", len(pix), "%.0f s" % (time.time() - t0))
    if cam_ob is not None:
        cd = cam_ob.data
        bpy.data.objects.remove(cam_ob, do_unlink=True)
        bpy.data.cameras.remove(cd)
    with open(os.path.join(OUT, "r12_libs_%s.json" % a.tag), "w") as f:
        json.dump(summary, f, indent=1)
    log("done; the .blend was not saved")


main()
