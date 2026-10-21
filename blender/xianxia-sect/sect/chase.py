"""Third-person chase: the flyer flies the route nose-first, a smooth orbit camera follows.

Run on an assembled scene (with or without scenery; an older chase setup is replaced):
    blender -b out/sect_scenic.blend --python sect/chase.py -- [--stills 93,389] [--res-pct 150]
            [--blend out/sect_chase.blend] [--out out/previews/chase] [--dump out/tmp/chase/route.npz]

The planning lives in chase_plan.py (plain numpy, tunable offline); this file is the Blender
glue: read the route from the fly-through camera camera.py baked, plan, push the camera out of
geometry, bake the flyer and the chase camera, render stills.
"""
import argparse
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import camera as C  # noqa: E402
from sect import chase_plan as CP  # noqa: E402
from sect import flyer as F  # noqa: E402
from sect.lib import util as U  # noqa: E402

FLYER_MAX_PITCH = math.radians(25)


def _log(*a):
    print("CHASE", *a, flush=True)


def route_camera(scene):
    """The fly-through camera camera.py baked (the flyer's route), whatever the scene camera is."""
    ob = bpy.data.objects.get(getattr(C, "CAMERA_NAME", ""))
    return ob if ob is not None else scene.camera


def path_from_camera(cam, frames):
    fcs = {fc.array_index: fc for fc in C._fcurves_of(cam) if fc.data_path == "location"}
    return np.array([[fcs[i].evaluate(f) for i in range(3)] for f in frames], dtype=float)


def look_from_camera(cam, frames):
    fcs = {fc.array_index: fc for fc in C._fcurves_of(cam) if fc.data_path == "rotation_euler"}
    out = []
    for f in frames:
        e = [fcs[i].evaluate(f) for i in range(3)]
        m = Matrix.Rotation(e[2], 3, 'Z') @ Matrix.Rotation(e[1], 3, 'Y') @ Matrix.Rotation(e[0], 3, 'X')
        out.append(tuple(m @ Vector((0, 0, -1))))
    return CP.unit(np.array(out))


def route(scene):
    """(frames, route positions, designed look directions, hero frames) from the scene."""
    src = route_camera(scene)
    frames = np.arange(scene.frame_start, scene.frame_end + 1)
    pos = path_from_camera(src, frames)
    look0 = look_from_camera(src, frames)
    try:
        heroes = [s["hero_frame"] for s in json.loads(src["timeline"])["sections"]]
    except Exception:
        heroes = []
    return frames, pos, look0, heroes, src


def plan_orbit(pos, look0, frames, heroes, fps):
    """Kept for scenery.py: the planned (unpushed) chase, with 'cam' = camera positions."""
    return CP.plan(pos, look0, frames, heroes, fps)


def flyer_eulers(fwd, roll):
    out, prev = [], None
    for f, r in zip(fwd, roll):
        y = Vector(f).normalized()
        pitch = math.asin(max(-1.0, min(1.0, y.z)))
        if abs(pitch) > FLYER_MAX_PITCH:                 # keep a standing posture on steep climbs/dives
            h = Vector((y.x, y.y, 0.0)).normalized()
            y = (h * math.cos(FLYER_MAX_PITCH) + Vector((0, 0, math.copysign(math.sin(FLYER_MAX_PITCH), pitch)))).normalized()
        x0 = y.cross(Vector((0, 0, 1)))
        if x0.length < 1e-6:
            x0 = Vector((1, 0, 0))
        x0.normalize()
        z0 = x0.cross(y)
        q = Matrix.Rotation(-r, 3, y)                    # bank into the turn
        m = Matrix((q @ x0, y, q @ z0)).transposed()
        e = m.to_euler('XYZ', prev) if prev is not None else m.to_euler('XYZ')
        out.append(tuple(e))
        prev = e
    return np.array(out)


def push_camera(scene, pos, p):
    """Keep the camera out of geometry like camera.py (smooth bumps), then re-smooth."""
    try:
        bvh, owners, own_idx, _ = C.collect_bvh(scene, np.vstack([pos, p["cam"]]))
        if bvh is None:
            return
        d_route, _, _ = C.clearance(bvh, owners, own_idx, pos)
        exempt = CP.gauss((d_route < C.CLEARANCE + 1.0).astype(float), 8.0) > 0.05
        offs, d, who, _ = C.resolve_clearance(bvh, owners, own_idx, p["cam"], exempt)
        p["cam"] = CP.gauss(p["cam"] + offs, 4.0)
        _log("camera_push_max_m", round(float(np.linalg.norm(offs, axis=1).max()), 2),
             "min_clearance", round(float(d.min()), 2))
    except Exception as e:
        _log("clearance pass skipped:", e)


def build_chase(scene, dump=None):
    frames, pos, look0, heroes, src = route(scene)
    fps = scene.render.fps
    if dump:
        os.makedirs(os.path.dirname(os.path.abspath(dump)), exist_ok=True)
        extra = {}
        old = bpy.data.objects.get("chase.cam")
        if old is not None and old.animation_data:
            extra = dict(old_cam=path_from_camera(old, frames), old_look=look_from_camera(old, frames))
        np.savez(dump, frames=frames, pos=pos, look0=look0, heroes=np.array(heroes), fps=fps, **extra)
        _log("dumped", dump)
    p = CP.plan(pos, look0, frames, heroes, fps)
    push_camera(scene, pos, p)
    CP.finish(p)
    _log("heroes", heroes, "metrics", json.dumps(CP.metrics(p["cam"], p["look"], p["target"], p["cam_roll"], fps)))

    coll = U.get_collection("flyer", scene=scene)
    old = bpy.data.objects.get("flyer.root")
    if old is not None:
        U.delete_hierarchy(old)
    root = F.build(coll)
    C._bake(root, "location", p["fly"], frames)
    C._bake(root, "rotation_euler", flyer_eulers(p["fwd"], p["roll"]), frames)

    cam = bpy.data.objects.get("chase.cam")
    if cam is not None:
        bpy.data.objects.remove(cam, do_unlink=True)
    cam = bpy.data.objects.new("chase.cam", bpy.data.cameras.new("chase.cam"))
    U.link(cam, coll)
    cam.data.lens = CP.LENS
    cam.data.sensor_width = CP.SENSOR
    cam.data.clip_start = 0.1
    cam.data.clip_end = src.data.clip_end
    C._bake(cam, "location", p["cam"], frames)
    C._bake(cam, "rotation_euler", C.orientations(p["look"], p["cam_roll"]), frames)
    scene.camera = cam
    return cam, root


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", default="")
    ap.add_argument("--res-pct", type=int, default=100)
    ap.add_argument("--blend", default=os.path.join(ROOT, "out", "sect_chase.blend"))
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "previews", "chase"))
    ap.add_argument("--dump", default="")
    ap.add_argument("--dump-only", action="store_true")
    a = ap.parse_args(argv)
    scene = bpy.context.scene
    if a.dump_only:
        frames, pos, look0, heroes, _ = route(scene)
        extra = {}
        old = bpy.data.objects.get("chase.cam")
        if old is not None and old.animation_data:
            extra = dict(old_cam=path_from_camera(old, frames), old_look=look_from_camera(old, frames))
        os.makedirs(os.path.dirname(os.path.abspath(a.dump)), exist_ok=True)
        np.savez(a.dump, frames=frames, pos=pos, look0=look0, heroes=np.array(heroes), fps=scene.render.fps, **extra)
        _log("dumped", a.dump)
        return
    build_chase(scene, dump=a.dump or None)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.blend))
    _log("saved", a.blend)
    if a.stills:
        os.makedirs(a.out, exist_ok=True)
        scene.render.resolution_percentage = a.res_pct
        for f in [int(x) for x in a.stills.split(",") if x.strip()]:
            scene.frame_set(f)
            scene.render.filepath = os.path.abspath(os.path.join(a.out, "chase_%04d.png" % f))
            bpy.ops.render.render(write_still=True)
            _log("still", scene.render.filepath)


if __name__ == "__main__":
    main()
