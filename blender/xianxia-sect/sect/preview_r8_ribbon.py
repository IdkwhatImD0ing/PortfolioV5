"""Cycles stills of Xiaolongnü's golden-bell silk ribbon on the abode's tea pavilion (sect/areas/abode.py _ribbon,
sect/patch_r8_ribbon.py), on the GPU at low samples. Renders only; the .blend is not saved. Run on the cloud box on a
test copy (never the main file):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<lane>_test.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r8_ribbon.py -- --tag a1 --samples 24

Writes out/preview/r8_ribbon[_<tag>]_<shot>.png (rblender copies them back):
    hold      chase.cam at the abode's hold frame (1380), 1280x720
    zoom      the hold camera's place and aim moved onto the ribbon, 4x the lens: what the hold shows, magnified
    pass      chase.cam at frame 1418, the flight's closest pass, 1280x720
    knot      close on the loop round the hip ridge's tip and the knot under it
    side      from the west along the balcony's front: the tails clear of the deck, the railing and the stilts
    bell      close on the long tail's gold cap and bell
    low       from the lawn south-west of the qin table, looking up the ribbon to the eave
Every still renders at the hold frame's lighting with the flyer hidden; volume objects are hidden for speed unless
--volumes. Options: --samples 24, --tag a1, --shots hold,zoom,... , --res 960x540 (the close-ups).
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
from sect.areas import abode as AB  # noqa: E402
from sect.lib import look as L  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
HOLD, PASS = 1380, 1418
CAM = "preview.r8_ribbon.cam"
SHOTS = ("hold", "zoom", "pass", "knot", "side", "bell", "low")


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r8_ribbon.py")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--tag", default="")
    ap.add_argument("--shots", default=",".join(SHOTS))
    ap.add_argument("--res", default="960x540")
    ap.add_argument("--volumes", action="store_true", help="keep volume objects (slower)")
    return ap.parse_args(argv)


def setup_cycles(sc, samples):
    """OptiX, then CUDA, then CPU; denoised low-sample stills."""
    sc.render.engine = "CYCLES"
    device = "CPU"
    try:
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
    except Exception as e:  # noqa: BLE001
        log("WARN GPU setup failed:", e)
    sc.cycles.device = "GPU" if device != "CPU" else "CPU"
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
    log("cycles", device, "samples", samples)


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


def views(root):
    """{shot: (camera, target, lens)} in abode.root's frame, round the ribbon (abode.ribbon_geo's knot and tails)."""
    pav, verts, edges, _r = AB.ribbon_ridge(root)
    _s, _b, info = AB.ribbon_geo(pav, verts, edges)
    k = Vector(info["knot"])
    tails = {nm: secs for nm, secs, _low in info["tails"]}
    mid = Vector(tails["long"][len(tails["long"]) // 2][0])
    end = Vector(tails["long"][-1][0])
    w, c, _z = AB._rib_basis()
    w, c = Vector(w), Vector(c)
    return {
        "knot": (k + c * 2.2 + w * 1.0 + Vector((0, 0, -1.2)), k + Vector((0, 0, 0.08)), 45.0),
        "side": (k + w * 9.0 + c * 1.0 + Vector((0, 0, -4.5)), mid + w * -0.5 + Vector((0, 0, 0.8)), 35.0),
        "bell": (end + c * 1.6 + w * 0.6 + Vector((0, 0, 0.1)), end + Vector((0, 0, -0.2)), 45.0),
        "low": (end + c * 6.5 + w * 3.0 + Vector((0, 0, -0.6)), mid + Vector((0, 0, 0.5)), 26.0),
    }, mid


def main():
    a = args()
    sc = bpy.context.scene
    root = bpy.data.objects.get("abode.root")
    if root is None:
        raise RuntimeError("abode.root not found: is this a copy of out/sect_chase.blend?")
    em = bpy.data.objects.get(AB.RIBBON)
    if em is None:
        raise RuntimeError("no %s: run sect/patch_r8_ribbon.py on this copy first" % AB.RIBBON)
    for ob in em.children_recursive:
        if ob.type == 'MESH':
            n = len(ob.data.polygons)
            lt = [0] * n
            ob.data.polygons.foreach_get("loop_total", lt)
            log(ob.name, "tris", sum(lt) - 2 * n, "slots", [s.material.name if s.material else None
                                                            for s in ob.material_slots])
    os.makedirs(OUT, exist_ok=True)
    setup_cycles(sc, a.samples)
    log("flyer objects hidden", EW.hide_flyer(sc))
    if not a.volumes:
        log("volume objects hidden", hide_volumes(sc))
    w, h = (int(x) for x in a.res.split("x"))
    vs, mid = views(root)
    pre = "r8_ribbon" + ("_" + a.tag if a.tag else "")
    made = []
    tmp = None
    M = root.matrix_world
    try:
        for shot in [s.strip() for s in a.shots.split(",") if s.strip()]:
            if shot in ("hold", "pass"):
                cam = bpy.data.objects.get(EW.CAMERA)
                if cam is None:
                    log("WARN no", EW.CAMERA)
                    continue
                frame, res = (HOLD if shot == "hold" else PASS), (1280, 720)
            elif shot == "zoom":
                hc = bpy.data.objects.get(EW.CAMERA)
                sc.frame_set(HOLD)
                eye = hc.matrix_world.translation.copy()
                cam = tmp = L.camera_look_at(CAM, eye, M @ (mid + Vector((0, 0, 1.0))), lens=hc.data.lens * 4.0,
                                             collection=sc.collection)
                frame, res = HOLD, (1280, 720)
            elif shot in vs:
                loc, tgt, lens = vs[shot]
                cam = tmp = L.camera_look_at(CAM, M @ loc, M @ tgt, lens=lens, collection=sc.collection)
                cam.data.clip_start = 0.05
                frame, res = HOLD, (w, h)
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
