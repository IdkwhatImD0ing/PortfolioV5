"""Cycles stills of round 59's rock (sect/patch_r59_rock.py, docs/scene/rock-r59.md), seen from the holds the way the
site shows them, on the GPU (OptiX, then CUDA; it refuses the CPU). Renders only: the .blend is never saved. Run it on
the copy before the patch (--tag before) and after it (--tag after), then compare:

    python E:/Github/PortfolioV5/.claude/worktrees/saltline-game-architecture-ae3e16/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r59.py -- --tag before [--samples 64] \
        [--shots abode_1380,abode_1380_close,...] [--retarget] [--relief none|off|on] [--relief-only <regex>] \
        [KEY=value ...]

Shots (1600 x 900, the film's field of view; a framed hold as client framing.ts STOP_FRAMING has it):
    abode_1380, _close        the abode's hold; close on its cliff (abode.cliff) near the frame's centre
    library_772, _close       the library's hold; close on steep rock near the frame's centre: the big tower left
                              of the pagoda, which is a kept cone of world.range (a column, world.peak.NNN, if one
                              is nearer the centre)
    steles_974, _close        the steles' hold; close on the cliff behind the pavilion (world.range near the centre)
    mirror_217, _close        the mirror's hold turned to the cliff under the hall (world.range's wall below the
                              terrace, on the camera's side); close on it
    forge_352, _close         the forge's hold: far rock 250 to 400 m off, where beds and joints could read as plaid;
                              close on the nearest column in the frame
    arena_516, _close         the arena's hold; close on the island's underside, or what the hold can see instead
                              (the 'alts' of the shot: the island's wall, then a floating rock in the frame)
    mission_619, _close       the mission hall's hold; close on the nearest column in the frame
    gate_93, scroll_1103, formation_1208, summit_1647    those holds as they are
A close-up's point is a rock face the camera sees: faces turned toward the camera are tried first, up to PICK_TRIES
rays, and a ray that stops on the shot's own rock within NEAR_SURF m of the point counts (a column's rendered surface
sits metres off its own mesh).
The close boxes and the mirror's aim point are worked out on the first run and kept in <out>/targets.json, so the
before and after stills frame the same thing (--retarget works them out again). The flyer and the volume objects (haze,
cloud banks) are hidden, as in the other previews. The floating rocks get the object property bake_web.ROCK_FLAT_PROP in
memory, as the bake gives their pieces (the round 59 material leaves its world beds off there); --no-flat skips it.
--relief (the round's bake-time rock relief, sect/relief.py): 'none' (default) renders the scene's own rock as before;
'off' and 'on' put an in-memory copy in place of every object the bake would relieve (named RELIEF_COPY + its name,
the original hidden for render only, so the scatters on it keep reading it and no plant moves): 'off' copies the shape
as it is, 'on' relieved exactly as bake_web does it, with the same pins. Run 'off' and 'on' with their own tags and
compare those two (both copies carry the same name, so the per-object tint matches; the 'none' stills differ by that
tint). --relief-only <regex> limits it to matching objects; KEY=value arguments override relief_rules / relief
constants for a tuning pass. Writes out/tmp/r59/renders/r59_<tag>_<shot>.png (under out/: rblender copies it back to
the PC).
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

from sect import bake_web as BW  # noqa: E402
from sect import export_web as EW  # noqa: E402
from sect import relief as RF  # noqa: E402
from sect import relief_rules as RR  # noqa: E402
from sect.areas import scroll as SC  # noqa: E402
from sect.lib import refs_east as RE  # noqa: E402
from sect.lib import refs_west as RW  # noqa: E402

RES = (1600, 900)
CAM = "preview.r59.cam"
FILL = 0.85
OUT = os.path.join(ROOT, "out", "tmp", "r59", "renders")
FRAMING = dict(RE.SITE_FRAMING)
FRAMING.update(RW.SITE_FRAMING)
FRAMING[SC.HOLD_FRAME] = (SC.SITE_FRAMING[0], SC.SITE_FRAMING[1], 12)
FRAMING.setdefault(1647, (0.0, 0.0, 8))       # framing.ts STOP_FRAMING.summit: back 8 frames
ROCK_TAGS = ("rock_cliff", "world_rock_under", "nature_rock_small", "world_pier_stone", "forge_tomb_rock",
             "forge_cairn_rock", "flute_qingshi")   # every material materials._rock builds
RELIEF_COPY = "r59relief."     # --relief off|on: the in-memory copy of a relieved object is named this + its name
RELIEF_HIDDEN = set()          # originals apply_relief hid for render (their shape still aims the close-ups)
POINTS_MAX = 40000             # candidate rock points per shot at most (evenly picked), for the visibility rays
PICK_TRIES = 3000              # visibility rays per close-up at most (faces turned toward the camera first)
NEAR_SURF = 12.0               # a ray that stops on the shot's own rock this near the point has seen it (m)
# shot -> frame, and for a close-up: the rock objects (name pattern), the distance band (m), how the point is picked
# ('centre': nearest the frame's centre; 'aim': nearest a point on the cliff under an anchor, on the camera's side), the
# box's half size (m: x, y, z), faces looking down only ('down'), steep faces only ('steep')
SHOTS = dict(
    abode_1380=dict(frame=1380, rock=r"^abode\.cliff$", dist=(30.0, 260.0), pick="centre", half=(10.0, 10.0, 12.0)),
    # the tower left of the pagoda is a kept cone of world.range, not a column: steep rock of either
    library_772=dict(frame=772, rock=r"^world\.(peak\.\d{3}|range)$", dist=(60.0, 450.0), pick="centre",
                     half=(14.0, 14.0, 20.0), steep=True),
    steles_974=dict(frame=974, rock=r"^world\.range$", dist=(60.0, 320.0), pick="centre", half=(10.0, 10.0, 10.0),
                    steep=True),
    mirror_217=dict(frame=217, rock=r"^world\.range$", dist=(25.0, 320.0), pick="aim", anchor="mirror.root",
                    aim=(70.0, -30.0), half=(12.0, 12.0, 12.0), steep=True),
    forge_352=dict(frame=352, rock=r"^world\.peak\.\d{3}$", dist=(40.0, 500.0), pick="centre",
                   half=(14.0, 14.0, 20.0), steep=True),
    gate_93=dict(frame=93),
    mission_619=dict(frame=619, rock=r"^world\.peak\.\d{3}$", dist=(40.0, 500.0), pick="centre",
                     half=(14.0, 14.0, 20.0), steep=True),
    scroll_1103=dict(frame=1103),
    formation_1208=dict(frame=1208),
    arena_516=dict(frame=516, rock=r"^arena\.island$", dist=(15.0, 320.0), pick="centre", half=(12.0, 12.0, 10.0),
                   down=True,
                   # the hold may not see the underside: then the island's wall, then any floating rock in the frame
                   alts=(dict(down=False, steep=True),
                         dict(rock=r"^(arena\.islet|scenery\.island)", down=False, steep=False))),
    summit_1647=dict(frame=1647),
)


def log(*a):
    print("PREVIEW", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="preview_r59.py")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--tag", default="")
    ap.add_argument("--shots", default=",".join(s for k, v in SHOTS.items()
                                                for s in ((k, k + "_close") if "rock" in v else (k,))))
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--retarget", action="store_true")
    ap.add_argument("--relief", default="none", choices=("none", "off", "on"),
                    help="the round's bake-time rock relief: none = the scene's rock; off / on = in-memory copies of "
                         "the objects the bake relieves, as they are / relieved (sect/relief.py)")
    ap.add_argument("--relief-only", default="", help="--relief off|on: only the objects whose name matches this too")
    ap.add_argument("--no-flat", action="store_true", help="do not flag the floating rocks rock_flat in memory")
    a, rest = ap.parse_known_args(argv)
    bad = [x for x in rest if "=" not in x or x.startswith("-")]
    if bad:
        ap.error("unrecognized arguments: %s" % " ".join(bad))
    a.overrides = rest                  # KEY=value: relief_rules / relief constants (RF.apply_overrides)
    a.out = EW.fix_path(a.out)          # 'E:/...' -> '/E:/...' on the box: Blender would write an E:/ path under /e/,
    #                                     outside the project mirror, and the stills would not come back (round 60)
    return a


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
        raise SystemExit("preview_r59: no OptiX or CUDA device: refusing to render on the CPU")
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


def flag_flat_rocks():
    """The floating rocks get bake_web.ROCK_FLAT_PROP = 1 in memory (never saved), as bake_web gives their bake
    pieces, so the stills show what the bake will hold."""
    n = 0
    for ob in bpy.data.objects:
        if ob.type == 'MESH' and BW.ROCK_FLAT_RE.match(ob.name):
            ob[BW.ROCK_FLAT_PROP] = 1.0
            n += 1
    return n


def apply_relief(sc, mode, only="", overrides=()):
    """--relief off|on: every object bake_web would relieve (sect/relief.py: the same records, the same captured
    evaluated mesh, the same pins) gets an in-memory copy RELIEF_COPY + name at the same matrix with the same custom
    properties, as it is ('off') or relieved ('on'); the original is hidden for render only, so the scatters on it keep
    reading it and no plant moves. Returns what undo_relief takes away (None for 'none')."""
    if mode == "none":
        return None
    t0 = time.time()
    if overrides:
        RF.apply_overrides(overrides, log)
    try:
        EW.use_profile("full")          # the bake's records: gathered at its frame, keyed as chunks.npz is
    except Exception as e:
        log("WARN no full profile (%s): records gathered as the scene stands" % e)
    R = EW.gather(sc)
    try:
        grp, _ids = EW.load_chunks(R)    # as bake_web: only pieces of an area chunk are relieved
    except Exception as e:
        log("WARN no chunk plan (%s): every target in the scene is relieved" % e)
        grp = None
    used = set()
    for t in R.tinfo.values():
        used.update(m for m in t[2] if m)
    minfo = {m: EW.material_info(bpy.data.materials[m]) for m in used if m in bpy.data.materials}
    ex = EW.export_mask(R, minfo)
    dg = bpy.context.evaluated_depsgraph_get()
    ox = re.compile(only) if only else None
    bases = {}
    for i in range(len(R)):
        nm = R.name[i]
        if R.inst[i] or not RF.RELIEF_OWNER_RE.match(nm) or (ox is not None and not ox.search(nm)):
            continue
        ob = bpy.data.objects.get(nm)
        if ob is None or ob.type != "MESH" or R.tkey[i] in bases:
            continue
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        EW._slot_materials(me, ob)          # what bake_web.capture does
        bases[R.tkey[i]] = me
    C = RF.build_context(R, bases, grp=grp, ex=ex, mat_class=BW.detail_class, only=only or None, log=log)
    geo = RR.Geo()
    keep = {R.tkey[i] for i in C["targets"]}
    for tk, me in list(bases.items()):
        if tk not in keep:
            bases.pop(tk)
            bpy.data.meshes.remove(me)
    state = dict(objects=[], meshes=[], hidden={})
    numbers = []
    for i in C["targets"]:
        nm = R.name[i]
        me = bases[R.tkey[i]]
        if mode == "on":
            numbers.append(RF.relieve_mesh(me, np.asarray(R.mw[i], float), nm, C, geo, log))
        src = bpy.data.objects[nm]
        cp = bpy.data.objects.new(RELIEF_COPY + nm, me)
        cp.matrix_world = Matrix(np.asarray(R.mw[i], float).tolist())
        for k in src.keys():
            if k.startswith("_") or k == "cycles":
                continue
            try:
                cp[k] = src[k]          # nature_top_radius, rock_flat ...: the material reads them (OBJECT attributes)
            except Exception:
                pass
        sc.collection.objects.link(cp)
        state["objects"].append(cp)
        state["meshes"].append(me)
        state["hidden"][nm] = src.hide_render
        src.hide_render = True
        RELIEF_HIDDEN.add(nm)
    moved = [n for n in numbers if n["moved"]]
    log("relief %s: %d objects copied%s in %.1f s" % (
        mode, len(state["objects"]),
        ("; relieved, mean %.2f m, max %.2f m" % (sum(n["mean"] for n in moved) / max(len(moved), 1),
                                                   max([n["max"] for n in moved] or [0.0]))) if mode == "on" else "",
        time.time() - t0))
    return state


def undo_relief(state):
    """Take away what apply_relief made: the copies and their meshes; the originals shown for render again."""
    if not state:
        return
    for cp in state["objects"]:
        bpy.data.objects.remove(cp, do_unlink=True)
    for me in state["meshes"]:
        if me.users == 0:
            bpy.data.meshes.remove(me)
    for nm, prev in state["hidden"].items():
        ob = bpy.data.objects.get(nm)
        if ob is not None:
            ob.hide_render = prev
    RELIEF_HIDDEN.clear()


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


def look_at(eye, target):
    """A level camera matrix at ``eye`` looking at ``target`` (its -Z toward it, Y up)."""
    rot = (Vector(target) - eye).to_track_quat('-Z', 'Y').to_matrix()
    Mw = rot.to_4x4()
    Mw.translation = eye
    return Mw


def fit_close(cam, data, eye, pts, fill=FILL):
    """Aim from ``eye`` at the points' centre and set the lens so they span ``fill`` of the frame."""
    centre = sum(pts, Vector()) / len(pts)
    Mw = look_at(eye, centre)
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

def rock_points(pattern, down=False, steep=False):
    """World centres and unit normals of the rock faces (a materials._rock material) of the mesh objects whose name
    matches ``pattern``: only faces looking down (down) or steep ones (steep) when asked; at most POINTS_MAX, evenly
    picked."""
    rx = re.compile(pattern)
    out, nrm = [], []
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or ob.data is None or (ob.hide_render and ob.name not in RELIEF_HIDDEN) \
                or not rx.match(ob.name):
            continue
        me = ob.data
        n = len(me.polygons)
        if not n:
            continue
        c = np.empty(n * 3)
        me.polygons.foreach_get("center", c)
        nr = np.empty(n * 3)
        me.polygons.foreach_get("normal", nr)
        mi = np.empty(n, np.int32)
        me.polygons.foreach_get("material_index", mi)
        rock = np.array([s.material is not None and s.material.get("sect_material") in ROCK_TAGS
                         for s in ob.material_slots] or [False], bool)
        ok = rock[np.clip(mi, 0, len(rock) - 1)]
        M = np.array(ob.matrix_world)
        L = M[:3, :3]
        w = c.reshape(n, 3) @ L.T + M[:3, 3]
        try:
            nw = nr.reshape(n, 3) @ np.linalg.inv(L)
        except np.linalg.LinAlgError:
            continue
        nw /= np.maximum(np.linalg.norm(nw, axis=1, keepdims=True), 1e-12)
        if down:
            ok &= nw[:, 2] < -0.3
        if steep:
            ok &= np.abs(nw[:, 2]) < 0.75
        out.append(w[ok])
        nrm.append(nw[ok])
    P = np.concatenate(out) if out else np.zeros((0, 3))
    N = np.concatenate(nrm) if nrm else np.zeros((0, 3))
    if len(P) > POINTS_MAX:
        keep = np.linspace(0, len(P) - 1, POINTS_MAX).astype(np.int64)
        P, N = P[keep], N[keep]
    return P, N


def seen(sc, dg, eye, p, hidden, rx=None):
    """The point a ray from ``eye`` toward ``p`` sees there, or None: ``p`` itself when the ray reaches it (within
    1 m), passing through what the stills do not render (the hidden volumes, the flyer, anything hidden from
    renders); the ray's own hit when it stops within NEAR_SURF m of ``p`` on a rock object whose name matches ``rx``
    (rock_points reads an object's own mesh, and a column's rendered surface sits metres off it)."""
    d = Vector(p) - eye
    dist = d.length
    d.normalize()
    o = eye.copy()
    for _ in range(12):
        hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, o, d, distance=max(dist - (o - eye).length, 1e-3))
        if not hit or (loc - eye).length >= dist - 1.0:
            return Vector(p)
        src = getattr(ob, "original", ob) if ob is not None else None
        if src is not None and rx is not None and (loc - Vector(p)).length < NEAR_SURF and \
                (rx.match(src.name) or (src.name.startswith(RELIEF_COPY) and rx.match(src.name[len(RELIEF_COPY):]))):
            return loc.copy()
        if src is None or not (src.name in hidden or src.hide_render):
            return None
        o = loc + d * 0.05
    return None


def pick(sc, dg, Mw, data, pts, nrm, spec, hidden):
    """The rock point a close-up frames: visible from the camera, within spec['dist'] m; 'centre' = nearest the
    frame's centre (in the frame), 'aim' = nearest a point aim[0] m from the anchor toward the camera, aim[1] m below
    it (the cliff under the terrace, on the camera's side), then the nearest visible one as a fallback."""
    eye = Mw.translation.copy()
    rx = re.compile(spec["rock"])
    dist = np.linalg.norm(pts - np.array(eye), axis=1)
    ok = (dist >= spec["dist"][0]) & (dist <= spec["dist"][1])
    if spec["pick"] == "aim":
        idx = np.nonzero(ok)[0]
        orders = []
        anchor = bpy.data.objects.get(spec["anchor"])
        if anchor is not None:
            a = np.array(anchor.matrix_world.translation)
            to_eye = np.array(eye)[:2] - a[:2]
            to_eye /= max(float(np.linalg.norm(to_eye)), 1e-6)
            t = np.array([a[0] + spec["aim"][0] * to_eye[0], a[1] + spec["aim"][0] * to_eye[1], a[2] + spec["aim"][1]])
            orders.append((idx[np.argsort(np.linalg.norm(pts[idx] - t, axis=1))],
                           "nearest the aim point %s" % np.round(t, 1).tolist()))
        else:
            log("WARN no", spec["anchor"], "object: aiming at the nearest visible rock")
        orders.append((idx[np.argsort(dist[idx])], "nearest the camera (nothing visible near the aim point)"))
    else:
        inv = np.array(Mw.inverted())
        L = pts @ inv[:3, :3].T + inv[:3, 3]
        depth = -L[:, 2]
        tx = 0.5 * data.sensor_width / data.lens          # tan of half the horizontal field of view
        ty = tx * RES[1] / RES[0]
        ok &= depth > 1.0
        ok &= np.abs(L[:, 0] / np.maximum(depth, 1e-3)) < 0.85 * tx
        ok &= np.abs(L[:, 1] / np.maximum(depth, 1e-3)) < 0.85 * ty
        idx = np.nonzero(ok)[0]
        key = np.hypot(L[idx, 0] / depth[idx], L[idx, 1] / depth[idx])
        # faces turned toward the camera first (a column's far side is never seen); the others after them, since
        # an inside-out rock's normals point the wrong way
        back = ((np.array(eye) - pts[idx]) * nrm[idx]).sum(axis=1) <= 0.0
        orders = [(idx[np.lexsort((key, back))], "nearest the frame's centre")]
    for order, how in orders:
        for i in order[:PICK_TRIES]:
            q = seen(sc, dg, eye, pts[i], hidden, rx)
            if q is not None:
                return np.array(q, dtype=float), float((q - eye).length), how
    return None, None, None


def target(base, sc, src, data, hidden):
    spec = SHOTS[base]
    Mw = site_view(sc, src, spec["frame"])
    data.lens, data.sensor_width = src.data.lens, src.data.sensor_width
    dg = bpy.context.evaluated_depsgraph_get()
    p = None
    for k, alt in enumerate(({},) + tuple(spec.get("alts", ()))):
        use = dict(spec, **alt)
        pts, nrm = rock_points(use["rock"], down=use.get("down", False), steep=use.get("steep", False))
        log("target", base, len(pts), "rock points" + (" (fallback %d: %s)" % (k, alt) if k else ""))
        if not len(pts):
            continue
        p, d, how = pick(sc, dg, Mw, data, pts, nrm, use, hidden)
        if p is not None:
            if k:
                how += "; fallback %d" % k
            break
    if p is None:
        return None
    hx, hy, hz = spec["half"]
    p = [float(x) for x in p]
    return dict(point=p, lo=[p[0] - hx, p[1] - hy, p[2] - hz], hi=[p[0] + hx, p[1] + hy, p[2] + hz],
                how="rock point %.1f m off (%s)" % (d, how))


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
    if not a.no_flat:
        log("floating rocks flagged %s in memory:" % BW.ROCK_FLAT_PROP, flag_flat_rocks())
    relief = apply_relief(sc, a.relief, a.relief_only, a.overrides)
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
    pre = "r59" + ("_" + a.tag if a.tag else "")
    made = []
    try:
        for shot in shots:
            base, close = (shot[:-6], True) if shot.endswith("_close") else (shot, False)
            if base not in SHOTS:
                log("WARN unknown shot", shot)
                continue
            spec = SHOTS[base]
            Mw = site_view(sc, src, spec["frame"])
            data.lens, data.sensor_width, data.sensor_height = src.data.lens, src.data.sensor_width, \
                src.data.sensor_height
            data.sensor_fit = src.data.sensor_fit
            data.shift_x, data.shift_y = src.data.shift_x, src.data.shift_y
            data.clip_start, data.clip_end = src.data.clip_start, src.data.clip_end
            if (close or spec.get("pick") == "aim") and "rock" in spec and base not in targets:
                tb = target(base, sc, src, data, hidden)
                if tb is None:
                    log("WARN no rock target for", shot)
                    continue
                targets[base] = tb
                with open(tpath, "w", encoding="utf-8") as f:
                    json.dump(targets, f, indent=1)
                Mw = site_view(sc, src, spec["frame"])
                data.lens, data.sensor_width = src.data.lens, src.data.sensor_width
            if close and base not in targets:
                log("WARN no close box for", shot)
                continue
            if close:
                tb = targets[base]
                lo, hi = tb["lo"], tb["hi"]
                pts = [Vector((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
                lens, dist = fit_close(cam, data, Mw.translation.copy(), pts)
                info = "%s; lens %.0f mm, %.1f m to the box's centre" % (tb["how"], lens, dist)
            elif spec.get("pick") == "aim":
                tb = targets[base]
                cam.matrix_world = look_at(Mw.translation.copy(), tb["point"])
                info = "turned to %s (%s), the film's lens" % (np.round(tb["point"], 1).tolist(), tb["how"])
            else:
                cam.matrix_world = Mw
                info = "site framing %s" % (FRAMING.get(spec["frame"], (0.0, 0.0, 0)),)
            sc.render.filepath = os.path.join(a.out, "%s_%s.png" % (pre, shot))
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            made.append(sc.render.filepath)
            log("wrote", sc.render.filepath, "frame", sc.frame_current, info, "relief", a.relief,
                "%.1f s" % (time.time() - t0))
    finally:
        undo_relief(relief)
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(data)
    log("done", len(made), "stills; the .blend was not saved")


main()
