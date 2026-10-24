"""Round 48: what the patch_r48_*.py scripts share (Blender side; run on the cloud box only).

- options(): KEY=value arguments after '--' (PARTS=a,b  DRY_RUN=1  SCOPE=b0|slice|all  VARIANT=...  plus any
  upper-case constant of the modules passed in, e.g. CANOPY_DENSITY=0.03).
- views(): chase.cam at every hold and listed flight frame of sect/holds_intent.json (lib.compose.View).
- star_boxes(): per hold, the star's screen box (the area's buildings standing on its terrace).
- keep_zone_mask(): world points within KEEP_R m of a hold camera and inside its frame (the keep-list's reach:
  plan rule 13, nothing there may change).
- scope(): the B0 / slice / all scope as XY discs round chase.cam positions.
- report(): JSON report under out/tmp/r48/ (rblender.py copies new files under out/ back to the PC).
"""
import ast
import hashlib
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

from sect import world as W
from sect.lib import compose as C

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "out", "tmp", "r48")
CAMERA = "chase.cam"
KEEP_R = 60.0                  # m: plan rule 13 (framing trees and everything within this of a hold camera stay)
KEEP_PAD = 15.0                # m more for face masks (a tree on a face this far out still reaches into the zone)
FRAME_PAD = 0.12               # frame widened by this share for 'inside its frame'
SCOPES = dict(                 # (frames whose chase.cam position centres a disc, disc radius m)
    b0=((870, 1103), 300.0),           # the f870 wall's peak family and the scroll hillside
    slice=((870, 974, 1103), 450.0),   # plan phase B: the chunks of the f870 wall and the scroll hillside
)


def log(*a):
    print("PATCH", *a, flush=True)


class Fail(list):
    def add(self, msg):
        log("FAIL", msg)
        self.append(msg)


def options(parts_all, defaults=None, modules=()):
    """dict(parts, dry, scope, + defaults' keys) from KEY=value args after '--'. Upper-case keys that name a
    constant of one of ``modules`` override it (literal_eval). Unknown keys stop the run."""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opt = dict(parts=tuple(parts_all), dry=False, scope="all")
    opt.update(defaults or {})
    for a in argv:
        k, eq, v = a.partition("=")
        if not eq:
            raise SystemExit("r48: not KEY=value: %r" % a)
        if k == "PARTS":
            opt["parts"] = tuple(p.strip() for p in v.split(",") if p.strip())
            bad = [p for p in opt["parts"] if p not in parts_all]
            if bad:
                raise SystemExit("r48: unknown parts %s (known: %s)" % (bad, ",".join(parts_all)))
        elif k == "DRY_RUN":
            opt["dry"] = v.strip().lower() not in ("", "0", "false", "no")
        elif k == "SCOPE":
            if v not in SCOPES and v != "all":
                raise SystemExit("r48: SCOPE must be one of %s or all" % sorted(SCOPES))
            opt["scope"] = v
        elif k.lower() in opt and k.isupper():
            opt[k.lower()] = v
        else:
            for mod in modules:
                if k.isupper() and hasattr(mod, k):
                    setattr(mod, k, ast.literal_eval(v))
                    log("override", mod.__name__ + "." + k, "=", getattr(mod, k))
                    break
            else:
                raise SystemExit("r48: unknown option %s" % k)
    return opt


def anchors():
    return W._norm_anchors(None)


def views(intent=None, flights=True):
    """lib.compose.View list: the holds (named by area) and, with ``flights``, the listed flight frames ('f<n>')."""
    intent = intent or C.load_intent()
    nf = [(k, h["frame"]) for k, h in intent["holds"].items()]
    if flights:
        nf += [("f%d" % f["frame"], f["frame"]) for f in intent["flights"]]
    return C.views_from_blend(nf, CAMERA)


def flight_sample(every=6):
    """Views of chase.cam every ``every`` frames over the whole film (named 'f<frame>')."""
    sc = bpy.context.scene
    fr = list(range(sc.frame_start, sc.frame_end + 1, every))
    return C.views_from_blend([("f%d" % f, f) for f in fr], CAMERA)


def cam_positions(frames):
    from sect import export_web as EW
    cam = bpy.data.objects[CAMERA]
    return np.array([np.array(m)[:3, 3] for m in EW.sample_matrices(cam, list(frames))], float)


def path_points(every=2):
    sc = bpy.context.scene
    return cam_positions(range(sc.frame_start, sc.frame_end + 1, every))


def scope(name):
    """None (everything) or [(x, y, r)] discs for SCOPES[name]."""
    if name in (None, "all"):
        return None
    frames, r = SCOPES[name]
    return [(float(p[0]), float(p[1]), r) for p in cam_positions(frames)]


def in_scope(discs, xy):
    """Bool mask of XY points (n, 2) inside any disc (all True for no discs)."""
    xy = np.atleast_2d(np.asarray(xy, float))
    if discs is None:
        return np.ones(len(xy), bool)
    m = np.zeros(len(xy), bool)
    for x, y, r in discs:
        m |= np.hypot(xy[:, 0] - x, xy[:, 1] - y) <= r
    return m


def star_boxes(hold_views, an=None, min_h=6.0):
    """{hold: dict(u0, u1, v_top, v_bot, depth)}: the screen box of the area's buildings (mesh objects of its
    collection whose box stands on the terrace, rises min_h m or more and centres within footprint + 25 m)."""
    an = an or anchors()
    out = {}
    for v in hold_views:
        a = an.get(v.name)
        coll = bpy.data.collections.get(v.name)
        if a is None or coll is None:
            continue
        boxes = []
        for ob in coll.all_objects:
            if ob.type != "MESH" or ob.name.startswith(("nature.", "scenery.", "life.")):
                continue
            mw = ob.matrix_world
            bb = np.array([list(mw @ Vector(p)) for p in ob.bound_box])
            c = bb.mean(0)
            if math.hypot(c[0] - a[0], c[1] - a[1]) > a[3] + 25.0:
                continue
            if bb[:, 2].max() - bb[:, 2].min() < min_h or bb[:, 2].min() < a[2] - 3.0 or \
                    bb[:, 2].max() < a[2] + min_h:
                continue
            u, vv, d = v.project(bb)
            if (d <= 1.0).any():
                continue
            boxes.append((float(u.min()), float(u.max()), float(vv.min()), float(vv.max()), float(d.mean())))
        if not boxes:
            continue
        b = np.array(boxes)
        inner = b[(b[:, 1] > 0.15) & (b[:, 0] < 0.85)]
        b = inner if len(inner) else b
        out[v.name] = dict(u0=max(0.0, float(b[:, 0].min())), u1=min(1.0, float(b[:, 1].max())),
                           v_top=max(0.0, float(b[:, 2].min())), v_bot=min(1.0, float(b[:, 3].max())),
                           depth=float(np.median(b[:, 4])), n=int(len(b)))
        log("star box", v.name, json.dumps({k: round(x, 3) if isinstance(x, float) else x
                                            for k, x in out[v.name].items()}))
    return out


def keep_zone_mask(pts, hold_views, r=KEEP_R, pad=0.0):
    """Bool per world point: within r + pad m of a hold camera and inside that camera's frame (widened by
    FRAME_PAD)."""
    pts = np.atleast_2d(np.asarray(pts, float))
    m = np.zeros(len(pts), bool)
    for v in hold_views:
        near = np.linalg.norm(pts - v.pos, axis=1) <= r + pad
        if not near.any():
            continue
        u, vv, d = v.project(pts[near])
        ins = (d > 0.0) & (u > -FRAME_PAD) & (u < 1 + FRAME_PAD) & (vv > -FRAME_PAD) & (vv < 1 + FRAME_PAD)
        idx = np.nonzero(near)[0]
        m[idx[ins]] = True
    return m


def face_centres(ob):
    me = ob.data
    n = len(me.polygons)
    c = np.empty(n * 3)
    me.polygons.foreach_get("center", c)
    nrm = np.empty(n * 3)
    me.polygons.foreach_get("normal", nrm)
    mw = np.array(ob.matrix_world)
    cw = c.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
    nw = nrm.reshape(-1, 3) @ mw[:3, :3].T
    nw /= np.maximum(np.linalg.norm(nw, axis=1), 1e-12)[:, None]
    return cw, nw


def face_attr(ob, name, values=None):
    """Read (values None) or write a FACE float attribute (created when missing)."""
    me = ob.data
    at = me.attributes.get(name)
    if values is None:
        if at is None:
            return None
        v = np.empty(len(me.polygons), np.float32)
        at.data.foreach_get("value", v)
        return v
    if at is not None and (at.domain != 'FACE' or at.data_type != 'FLOAT'):
        me.attributes.remove(at)
        at = None
    if at is None:
        at = me.attributes.new(name, 'FLOAT', 'FACE')
    at.data.foreach_set("value", np.asarray(values, np.float32))
    me.update()
    return at


def report(name, data):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, default=_json_default)
    log("report", p)
    return p


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (set, tuple)):
        return list(o)
    return str(o)


def mesh_sig(ob, decimals=3):
    me = ob.data
    h = hashlib.md5()
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", co)
    h.update(np.round(co, decimals).astype(np.float32).tobytes())
    lt = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_total", lt)
    h.update(lt.tobytes())
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", mi)
    h.update(mi.tobytes())
    return h.hexdigest()


def matrix_key(ob, decimals=4):
    return [round(float(x), decimals) for row in ob.matrix_world for x in row]


def remove_objects(obs):
    """Delete objects (and their meshes when nothing else uses them). Returns the count."""
    obs = [o for o in obs if o is not None]
    meshes = {o.data for o in obs if o.type == 'MESH' and o.data is not None}
    n = 0
    for o in obs:
        try:
            bpy.data.objects.remove(o, do_unlink=True)
            n += 1
        except ReferenceError:
            pass
    for me in meshes:
        try:
            if me.users == 0:
                bpy.data.meshes.remove(me)
        except ReferenceError:
            pass
    return n


def save_or_dry(dry, fail, digest, t0=None):
    """Print the digest, stop on failed checks (nothing saved), else save unless DRY_RUN."""
    log("DIGEST", digest)
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail[:20]:
            log("  -", f)
        raise SystemExit(1)
    if dry:
        log("DRY_RUN: checks passed, not saving")
        return False
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)
    return True
