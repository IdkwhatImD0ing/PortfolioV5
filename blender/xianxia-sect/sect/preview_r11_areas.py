"""Stills for round 11, lane 'areas' (sect/patch_r11_areas.py): the yubu ramp bodies, the summit's dark channel ring,
the formation's flush axis strip and the mirror terrace's full rim rail, in GPU Cycles at low samples. Renders only;
the .blend is not saved. Run on the cloud box, on the unpatched file (--tag before) and after the patch (--tag after):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/r11_areas_test.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r11_areas.py -- --tag before

Writes out/preview/r11_areas_<tag>_<view>.png (rblender copies them back). Views (--views, comma separated):
    mirror_hold, mirror_f180, mirror_f160   chase.cam at those frames (217 is the mirror's hold; the stair top at 180)
    mirror_nw     from outside the north-west rim, over the terrace toward the south-east
    mirror_w      low, along the west rim, where no rail stood before
    mirror_top    straight down on the whole terrace
    mirror_e      from outside the east rim: the depart opening and the north-east arc, where the rail steps in to
                  r 50.5 (mirror.rim_radius) to stay on the flat terrace
    summit_hold   chase.cam at the summit's hold (1647)
    summit_band   low oblique onto the trigram ring and its dark channel, south-east of the pavilion
    formation_hold  chase.cam at the formation's hold (1208)
    formation_axis  low along the front axis strip where it crosses the ink bands
    gate_f30      chase.cam at frame 30 (the grand stair's carved ramps from far away)
    gate_ramp     close to the first gate flight's carved ramp, from its foot
    summit_ramp   close to the summit's middle tier ramp
Options: --tag (default 'after'), --samples 16, --res 1280x720, --views (default all), --volumes (keep the mist).
"""
import argparse
import json
import math
import os
import sys
import time

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import bake_web as BW  # noqa: E402  (setup_cycles)
from sect import export_web as EW  # noqa: E402  (CAMERA, HOLD_OVERRIDES, TIMELINE, hide_flyer)
from sect.lib import look as L  # noqa: E402

OUT = os.path.join(ROOT, "out", "preview")
ALL = ("mirror_hold", "mirror_f180", "mirror_f160", "mirror_nw", "mirror_w", "mirror_top", "mirror_e", "summit_hold",
       "summit_band", "formation_hold", "formation_axis", "gate_f30", "gate_ramp", "summit_ramp")


def log(*a):
    print("PREVIEW", *a, flush=True)


def polar(r, deg, z):
    return (r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg)), z)


def hold_frame(area):
    f = EW.HOLD_OVERRIDES.get(area)
    if f:
        return int(f)
    with open(EW.TIMELINE, encoding="utf-8") as fh:
        tl = json.load(fh)
    return int(next(s["hero_frame"] for s in tl["sections"] if s["area"] == area))


def ramp_view(stairs_name, side=3.0, back=5.0, up=1.6, lens=30.0):
    """(eye, target) in world space looking up a stairs() flight's carved ramp from beside its foot."""
    st = bpy.data.objects[stairs_name]
    L_, n, riser = float(st["arch_run"]), int(st["arch_steps"]), float(st["arch_riser"])
    h = n * riser
    M = st.matrix_world
    return M @ Vector((side, -L_ - back, up)), M @ Vector((0.0, -0.45 * L_, 0.45 * h)), lens


def local_view(area, eye, tgt, lens):
    M = bpy.data.objects[area + ".root"].matrix_world
    return M @ Vector(eye), M @ Vector(tgt), lens


def view(name):
    """('chase', frame) or ('look', eye, target, lens, frame)."""
    if name == "mirror_hold":
        return ("chase", hold_frame("mirror"))
    if name == "mirror_f180":
        return ("chase", 180)
    if name == "mirror_f160":
        return ("chase", 160)
    if name == "summit_hold":
        return ("chase", hold_frame("summit"))
    if name == "formation_hold":
        return ("chase", hold_frame("formation"))
    if name == "gate_f30":
        return ("chase", 30)
    if name == "mirror_nw":
        return ("look",) + local_view("mirror", polar(88.0, 118.0, 30.0), polar(18.0, -62.0, 0.0), 28.0) + \
            (hold_frame("mirror"),)
    if name == "mirror_w":
        return ("look",) + local_view("mirror", polar(47.0, 212.0, 2.2), polar(52.0, 168.0, 0.2), 28.0) + \
            (hold_frame("mirror"),)
    if name == "mirror_top":
        return ("look",) + local_view("mirror", (0.0, -0.5, 160.0), (0.0, 0.0, 0.0), 30.0) + (hold_frame("mirror"),)
    if name == "mirror_e":
        return ("look",) + local_view("mirror", polar(72.0, 40.0, 16.0), polar(46.0, 18.0, 0.0), 28.0) +             (hold_frame("mirror"),)
    if name == "summit_band":
        return ("look",) + local_view("summit", polar(37.0, -128.0, 3.2), polar(29.5, -95.0, 0.0), 32.0) + \
            (hold_frame("summit"),)
    if name == "formation_axis":
        return ("look",) + local_view("formation", (6.0, -47.0, 3.2), (0.0, -24.0, 0.0), 30.0) + \
            (hold_frame("formation"),)
    if name == "gate_ramp":
        return ("look",) + ramp_view("gate.stair") + (hold_frame("gate"),)
    if name == "summit_ramp":
        return ("look",) + ramp_view("summit.tier_mid_stairs", side=2.5, back=4.0, up=1.5) + (hold_frame("summit"),)
    raise KeyError(name)


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


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r11_areas.py")
    ap.add_argument("--tag", default="after")
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--views", default=",".join(ALL))
    ap.add_argument("--volumes", action="store_true")
    a = ap.parse_args(argv)
    sc = bpy.context.scene
    if not a.volumes:
        log("volumes hidden:", hide_volumes(sc))
    log("flyer objects hidden", EW.hide_flyer(sc))
    BW.setup_cycles(sc, a.samples)
    sc.cycles.use_denoising = True
    r = sc.render
    r.use_persistent_data = True
    r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"
    r.film_transparent = False
    r.resolution_x, r.resolution_y = (int(x) for x in a.res.split("x"))
    os.makedirs(OUT, exist_ok=True)
    chase = bpy.data.objects.get(EW.CAMERA)
    made = []
    for name in [v.strip() for v in a.views.split(",") if v.strip()]:
        v = view(name)
        if v[0] == "chase":
            frame = v[1]
            sc.camera = chase
        else:
            _, eye, tgt, lens, frame = v
            sc.camera = L.camera_look_at("preview.r11." + name, eye, tgt, lens=lens, collection=sc.collection)
        sc.frame_set(frame)
        r.filepath = os.path.join(OUT, "r11_areas_%s_%s.png" % (a.tag, name))
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        made.append(r.filepath)
        log(name, "frame", frame, r.filepath, "%.1f s" % (time.time() - t0))
    log("done", len(made), "stills in", OUT)


main()
