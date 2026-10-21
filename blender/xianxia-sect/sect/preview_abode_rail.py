"""Close-ups of the Cave Abode's stone rim rail (sect/patch_abode_rail.py, areas/abode.py _rim_spans) in GPU Cycles at
low samples. Renders only; the .blend is not saved. Run on the cloud box, after the patch:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_abode_rail.py [-- --tag after]

Writes out/preview/abode_rail_<tag>_<view>.png (rblender copies them back):
    hold   chase.cam at the abode's hold frame (export_web.HOLD_OVERRIDES, else out/section_timeline.json's hero frame)
    west   the west span from outside and above, where the old rail stood over the cliff's first slope
    gap    the arrival landing from above the formation stair: the rail ends at the landing's sides
    east   the east span (the hold camera's side) from outside and above
    low    eye level on the lawn, along the west span: the posts' feet in the grass
    edge   from just outside the lawn, low: the lawn edge in front of the rail
Every view renders at the hold frame with the flyer hidden. Options: --tag (default 'after'; run it on the unpatched
blend with --tag before for a side-by-side), --samples 24, --res 960x540 (the hold view at 1280x720), --views
hold,west,... . Also logs, per span, how far each post's foot is under the lawn (abode.ground's evaluated mesh).
About a minute on one GPU: the scene's BVH is built once (persistent data).
"""
import argparse
import json
import math
import os
import sys
import time

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import bake_web as BW  # noqa: E402  (setup_cycles)
from sect import export_web as EW  # noqa: E402  (CAMERA, HOLD_OVERRIDES, TIMELINE, hide_flyer)
from sect.areas import abode as AB  # noqa: E402
from sect.lib import look as L  # noqa: E402
from sect.lib import util as U  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
SPANS = ("abode.rim_rail", "abode.rim_rail.001")


def log(*a):
    print("PREVIEW", *a, flush=True)


def polar(r, deg, z):
    return (r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg)), z)


# close-ups in abode.root's frame: name -> (camera, target, lens). The rail is an arc at AB.RIM_R from 200 to 340 deg
# (0 = +x, the cliff is to +y), open over the arrival landing at x = GATE_X +- 4.
def views():
    R, G = AB.RIM_R, AB.GATE_X
    return {
        "west": (polar(R + 11.5, 222.0, 7.0), polar(R, 228.0, 0.3), 35.0),
        "gap": ((G, -64.0, 9.0), (G, -47.5, 0.2), 32.0),
        "east": (polar(R + 13.5, 296.0, 6.0), polar(R, 300.0, 0.3), 35.0),
        "low": (polar(R - 3.0, 236.0, 1.4), polar(R, 250.0, 0.3), 30.0),
        "edge": (polar(R + 3.5, 285.0, 0.9), polar(R, 279.0, 0.2), 30.0),
    }


def hold_frame():
    f = EW.HOLD_OVERRIDES.get("abode")
    if f:
        return int(f)
    with open(EW.TIMELINE, encoding="utf-8") as fh:
        tl = json.load(fh)
    return int(next(s["hero_frame"] for s in tl["sections"] if s["area"] == "abode"))


def feet_report(root):
    """Per span: the lawn height under each post less its foot (m), from abode.ground's evaluated mesh."""
    ground = bpy.data.objects.get("abode.ground")
    if ground is None:
        log("WARN no abode.ground")
        return
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ground.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        m = U.world_matrix(root).inverted() @ U.world_matrix(ground)
        bvh = BVHTree.FromPolygons([m @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    finally:
        ev.to_mesh_clear()
    W = U.world_matrix(root).inverted()
    for nm in SPANS:
        ob = bpy.data.objects.get(nm + ".posts")
        if ob is None:
            log("WARN no", nm + ".posts")
            continue
        rel = W @ U.world_matrix(ob)
        co = [0.0] * (3 * len(ob.data.vertices))
        ob.data.vertices.foreach_get("co", co)
        dev, rr, miss = [], [], 0
        for i in range(0, len(co), 3):
            p = rel @ Vector(co[i:i + 3])
            rr.append(math.hypot(p.x, p.y))
            hit = bvh.ray_cast(Vector((p.x, p.y, p.z + 20.0)), Vector((0.0, 0.0, -1.0)))
            if hit[0] is None:
                miss += 1
            else:
                dev.append(hit[0].z - p.z)
        log(nm, "posts", len(rr), "r %.2f..%.2f m" % (min(rr), max(rr)),
            "lawn over the feet %.3f..%.3f m" % (min(dev), max(dev)) if dev else "", "OFF THE LAWN %d" % miss if miss else "")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_abode_rail.py")
    ap.add_argument("--tag", default="after")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--res", default="960x540")
    ap.add_argument("--views", default="hold,west,gap,east,low,edge")
    a = ap.parse_args(argv)
    scene = bpy.context.scene
    root = bpy.data.objects.get("abode.root")
    if root is None:
        raise RuntimeError("no abode.root: is this out/sect_chase.blend?")
    feet_report(root)
    frame = hold_frame()
    scene.frame_set(frame)
    log("hold frame", frame, "flyer objects hidden", EW.hide_flyer(scene))
    BW.setup_cycles(scene, a.samples)
    scene.cycles.use_denoising = True
    r = scene.render
    r.use_persistent_data = True
    r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"
    r.film_transparent = False
    os.makedirs(OUT, exist_ok=True)
    w, h = (int(x) for x in a.res.split("x"))
    W = U.world_matrix(root)
    vw = views()
    made = []
    for name in [v.strip() for v in a.views.split(",") if v.strip()]:
        if name == "hold":
            cam = bpy.data.objects.get(EW.CAMERA)
            if cam is None:
                log("WARN no", EW.CAMERA)
                continue
            r.resolution_x, r.resolution_y = 1280, 720
        elif name in vw:
            loc, tgt, lens = vw[name]
            cam = L.camera_look_at("preview.abode_rail." + name, W @ Vector(loc), W @ Vector(tgt), lens=lens,
                                   collection=scene.collection)
            r.resolution_x, r.resolution_y = w, h
        else:
            log("WARN unknown view", name)
            continue
        scene.camera = cam
        scene.frame_set(frame)
        r.filepath = os.path.join(OUT, "abode_rail_%s_%s.png" % (a.tag, name))
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        made.append(r.filepath)
        log(name, r.filepath, "%.1f s" % (time.time() - t0))
    log("done", len(made), "stills in", OUT)


main()
