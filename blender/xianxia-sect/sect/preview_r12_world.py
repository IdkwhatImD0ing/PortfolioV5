"""Before / after stills for round 12, lane 'world' (sect/patch_r12_world.py): crops of the flicker sources the patch
removes, seen from the camera path. Renders only; the .blend is never saved.

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<unpatched copy>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r12_world.py -- --plan --tag before
    python .../rblender.py --background E:/.../out/<patched copy>.blend --python-exit-code 1 \
        --python E:/.../sect/preview_r12_world.py -- --tag after

--plan (on the unpatched file) scans each item with the patch's scanner, picks its biggest cluster seen from the camera
path and writes out/preview/r12_world_shots.json: the camera stands where the path sees it nearest (that frame's
chase.cam position), looking at it through a lens that frames about 14 m there (a zoom from where the visitor is).
Every run renders those shots (Cycles, GPU, --samples 24, 1280 x 720, web clip planes 0.5 / 9000 m) to
out/preview/r12_world_<tag>_<id>.png, scans the items again on this file and writes a _mark copy with a magenta ring at
every overlap piece (two faces within 12 mm) the view holds: the after stills should have none or few.
Items: rim (world.range's outline), island, islet, roots, veins, piers (a bend of a link stair), shrine.
"""
import argparse
import contextlib
import io
import json

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
from sect import patch_r12_world as P  # noqa: E402
from sect.lib import look as L  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
SHOTS = os.path.join(OUT, "r12_world_shots.json")
RES = (1280, 720)
FRAME_W = 14.0                 # m framed at the target
CLOSE = dict(rim=35.0, island=45.0, islet=25.0, roots=40.0, veins=45.0, piers=14.0, shrine=12.0)   # close views (m)


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r12_world.py")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--tag", default="before")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--items", default="rim,island,islet,roots,veins,piers,shrine")
    ap.add_argument("--no-render", action="store_true")
    return ap.parse_args(argv)


def item_scan(item):
    """(Soup, overlap pieces, summary rows) of one item on the open file."""
    O = bpy.data.objects
    if item == "rim":
        S = P.Soup([O["world.range"]])
        src = P.range_rim_sources(S)
    elif item in ("island", "islet"):
        nm = "scenery.island.046" if item == "island" else "world.islet.013"
        S = P.Soup([O[nm]] + [c for c in O[nm].children if c.type == "MESH" and c.name.endswith(".roots")])
        src = np.ones(len(S), bool)
    elif item == "roots":
        S = P.Soup([O["world.roots"]])
        src = np.ones(len(S), bool)
    elif item == "veins":
        ice = "scenery.island.009"
        S = P.Soup([O[ice + ".icefire_lava_veins"], O[ice]])
        src = S.own == 0
    elif item == "piers":
        L_ = dict(nm="world.link.scroll_formation")
        S, mine = P.link_soup(L_)
        src = np.isin(S.own, [S.names.index(o.name) for o in mine if o.name.endswith((".piers", ".stairs"))
                              and o.name in S.names])
    elif item == "shrine":
        S = P.Soup([O["life.shrine.library"]])
        src = np.ones(len(S), bool)
    else:
        raise SystemExit("unknown item %r" % item)
    ovs = P.find_overlaps(S, src)
    occ = [S.bvh] + P.occluders([O["world.range"]])
    with contextlib.redirect_stdout(io.StringIO()):
        res = P.summarize(S, ovs, occ, item, group=lambda n: n)
    return S, ovs, res["rows"]


def plan(items):
    cam, fr = P.camera_path()
    shots = []
    for item in items:
        t0 = time.time()
        S, ovs, rows = item_scan(item)
        seen = [r for r in rows if r["v5"] + r["v12"] > 0 and r["f"] >= 0]
        if item == "piers":
            seen = [r for r in seen if "piers" in r["a"] + r["b"]] or seen
        if not seen:
            log("PLAN", item, "nothing seen")
            continue
        r = max(seen, key=lambda r: (r["v5"] + r["v12"]) / max(r["d"], 1.0) ** 0.5)
        tgt = np.array(r["cen"], float)
        eye = cam[int(np.nonzero(fr == r["f"])[0][0])]
        d = float(np.linalg.norm(tgt - eye))
        lens = float(np.clip(36.0 * d / FRAME_W, 24.0, 400.0))
        shots.append(dict(id=item, item=item, frame=int(r["f"]), eye=eye.tolist(), target=tgt.tolist(), lens=lens,
                          dist=d, a=r["a"], b=r["b"], seen=r["v5"] + r["v12"]))
        # from close by, square onto the faces that overlapped (on the path's side of them), to see the shapes
        dc = CLOSE[item]
        o = min(ovs, key=lambda o: float(np.linalg.norm(np.asarray(o["cen"]) - tgt)))
        nrm = np.asarray(S.n[o["i"]], float)
        if float(nrm @ (eye - tgt)) < 0:
            nrm = -nrm
        view = 0.7 * nrm + 0.3 * (eye - tgt) / max(d, 1e-6)
        eye_c = tgt + view / max(np.linalg.norm(view), 1e-9) * dc
        shots.append(dict(id=item + "_close", item=item, frame=int(r["f"]), eye=eye_c.tolist(), target=tgt.tolist(),
                          lens=35.0, dist=dc, a=r["a"], b=r["b"], seen=r["v5"] + r["v12"]))
        log("PLAN", item, "cluster %s ~ %s seen %.2f m2 from f%d at %.0f m, lens %.0f mm (%.0f s)"
            % (r["a"], r["b"], r["v5"] + r["v12"], r["f"], d, lens, time.time() - t0))
    os.makedirs(OUT, exist_ok=True)
    with open(SHOTS, "w") as f:
        json.dump(shots, f, indent=1)
    return shots


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


def mark(path, pix, out_path):
    im = bpy.data.images.load(path)
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
    yy, xx = np.mgrid[0:h, 0:w]
    ring = np.zeros((h, w), bool)
    for x, y in pix:
        d = np.hypot(xx - x, yy - y)
        ring |= (d >= 5.0) & (d <= 7.0)
    a[ring] = (1.0, 0.0, 1.0, 1.0)
    im.pixels[:] = a.reshape(-1)
    im.filepath_raw = out_path
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def render(shots, tag, samples, items):
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene
    dev = setup(sc, samples)
    if dev != "GPU":
        raise SystemExit("preview_r12_world: no GPU, refusing to render on the CPU")
    cam_ob = None
    scans = {}
    for s in shots:
        item = s.get("item", s["id"])
        if item not in items:
            continue
        t0 = time.time()
        if item not in scans:
            scans[item] = item_scan(item)
        _S, ovs, rows = scans[item]
        if cam_ob is not None:
            cd = cam_ob.data
            bpy.data.objects.remove(cam_ob, do_unlink=True)
            bpy.data.cameras.remove(cd)
        cam_ob = L.camera_look_at("r12w.shot.cam", Vector(s["eye"]), Vector(s["target"]), lens=float(s["lens"]),
                                  collection=sc.collection)
        cam_ob.data.clip_start = 0.5
        cam_ob.data.clip_end = 9000.0
        sc.camera = cam_ob
        sc.frame_set(int(s["frame"]))
        bpy.context.view_layer.update()
        path = os.path.join(OUT, "r12_world_%s_%s.png" % (tag, s["id"]))
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        pix = []
        seen = [r for r in rows if r["v5"] + r["v12"] > 0]
        for r in seen:                                  # one ring per cluster the camera path can see
            v = world_to_camera_view(sc, cam_ob, Vector(r["cen"]))
            if v.z > 0 and 0 <= v.x <= 1 and 0 <= v.y <= 1:
                pix.append((v.x * RES[0], v.y * RES[1]))
        mark(path, pix, path.replace(".png", "_mark.png"))
        log("wrote", os.path.basename(path), "frame", s["frame"], "seen overlap clusters in view", len(pix),
            "(of %d seen, %.2f m2)" % (len(seen), sum(r["v5"] + r["v12"] for r in seen)), "%.0f s" % (time.time() - t0))
    if cam_ob is not None:
        cd = cam_ob.data
        bpy.data.objects.remove(cam_ob, do_unlink=True)
        bpy.data.cameras.remove(cd)


def main():
    a = args()
    items = [x.strip() for x in a.items.split(",") if x.strip()]
    if a.plan:
        shots = plan(items)
    else:
        with open(SHOTS) as f:
            shots = json.load(f)
    if not a.no_render:
        render(shots, a.tag, a.samples, items)
    log("done; the .blend was not saved")


main()
