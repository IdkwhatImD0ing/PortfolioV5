"""Round 62: the abode waterfall's notch as a turned cleft, put into an existing out/sect_chase.blend so it matches what
a fresh build of sect/areas/abode.py makes. Run on the cloud box, on a copy first:

    python E:/Github/PortfolioV5/.claude/worktrees/abode-waterfall-quality-3e4da2/blender/xianxia-sect/tools/rblender.py \
        -b E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r62_notch.py [-- DRY_RUN=1]

Why: abode._top cut the notch as a smooth Gaussian dip that ran straight back through the cliff top, so its two sides
were plain ramps of the cliff's coarse top rows. The flight sees the notch from its right, and the light comes from
the front left: the left side showed as one flat dark slab and the right rim as one straight diagonal. The new shape
is in abode.py at NOTCH_R62: the cleft turns left as it goes back, so its left side faces away from every view, and it
ends in a stepped head a few metres behind the lip.

What it does, to abode.cliff only (no object is added, removed or moved):
- every vertex moves by the difference between abode._cliff_verts() with the old Gaussian notch (abode.NOTCH_R62 =
  False) and with the turned cleft (True). Only that difference is applied, so what earlier patches did to the cliff
  stays. Same vertices, same faces. Sharp edges are worked out again from the 50 degree angle on the edges whose
  vertices moved (as a fresh build's U.auto_smooth does), kept elsewhere.
- abode.cliff_split: the quads of the top rows by the cleft that Blender would split across the turned wall start one
  corner later, so they are split along it.

State: the cliff is 'old' (the file's moving vertices sit on the old analytic grid), 'new' (on the new one) or 'stale'
(neither: the patch stops). Objects of round 62's earlier tries ('abode.notch_crag.*', 'abode.notch_rock.*') must not
be in the file. Idempotent: on a patched file it prints 'PATCH nothing changed: not saving' and the same DIGEST.

Checks (any failure stops the patch before saving; DRY_RUN=1 runs everything and never saves):
- the cliff: its vertex count is the analytic grid's; the file's cliff against the old analytic one is logged; it has
  no modifier or shape key; its other per-vertex data is logged (the rock material maps by object and world position,
  materials._rock, so no UVs to redo); nothing moves past |dx| abode.NOTCH_STRIP;
- the quads: at most SPLIT_LONG_MAX of the cleft's quads are still split along their longer diagonal;
- the channel: the lip's front-edge vertices with |dx| <= CHANNEL_HALF are level at the lip (within FLOOR_TOL), none
  rose, the level floor is at least 2 x CHANNEL_HALF wide, and the channel keeps that width through the rows nearer
  than CHANNEL_BACK to the front edge; no moved cliff vertex rises into the page's water at its crest (|dx| <
  POUR_HALF, lip < z <= lip + POUR_TOP, within POUR_BACK of the chute plane) where it was not before;
- names and counts: nothing added, removed or moved; no mesh, material, collection, scene, node group or image added;
- pines: where the cliff under a pine's foot ('abode.*pine*') moved, the foot stays PINE_ROOT in the ground and sinks
  no more than PINE_SINK;
- flight: chase.cam (every frame) never nearer than CAM_MIN to a moved cliff vertex.
Logged, not failed: the channel row by row, and every object over the changed strip (|dx| < STRIP_DX, above lip - 1)
that the new cliff leaves buried more than BURIED_MAX or floating more than FLOAT_MAX (with its gap before).
Prints 'PATCH CACHES needs bakefull abode ...' when it changed the file, and 'PATCH DIGEST <md5>'.
"""
import hashlib
import math
import os
import re
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402  (CAMERA, sample_matrices)
from sect.areas import abode as AB  # noqa: E402
from sect.areas import summit as SU  # noqa: E402  (owner_tris, tri_bvh)

RES = (1600, 900)
CAM_MIN = 4.0               # m from chase.cam on any frame
GRID_TOL = 2e-3             # m: the file's moving cliff vertices count as on the old / new analytic grid within this
MOVE_EPS = 1e-4             # m: a cliff vertex moves when its analytic positions differ by more
SHARP_DEG = 50.0            # abode._cliff's auto smooth angle
CHANNEL_HALF = 1.6          # m: the page's water needs a level channel at least 3.2 m wide at the lip
FLOOR_TOL = 0.05            # m over the lip that still counts as level
POUR_HALF = 1.97            # m: the page's pour at the lip, 2.94 x 0.5 + 0.5
POUR_TOP = 2.2              # m over the lip the page's water stands at most (pour.ts: level)
POUR_BACK = 1.0             # m behind the chute plane the pour's crest reaches (pour.ts: crestOut - back = -0.75)
CHANNEL_Z = 1.5             # m over the lip: a top-row vertex under this is the channel's floor
CHANNEL_BACK = 2.0          # m behind the front edge: the rows nearer than this must keep the channel's width
SPLIT_LONG_MAX = 6          # quads by the cleft that Blender may still split along the longer diagonal
STRIP_DX, BURIED_MAX, FLOAT_MAX = 13.5, 1.5, 0.2   # the changed strip, and the object gaps the log calls out
PINE_ROOT = 0.3             # m a pine's foot must stay in the ground where the cliff under it moved
PINE_SINK = 0.5             # m deeper, at most, that it may stand in the ground
PINE_RE = re.compile(r"^abode\..*pine")
OLD_TRY_RE = re.compile(r"^abode\.notch_(crag|rock)\.")
TWILIGHT = "twilight,key_color=0.72/0.82/1.0,sky_lobe=0.3,lamp_boost=600,lantern_boost=192,boost_near=0.6,boost_far=2.5"
# the page's views of the notch (client/out/wf/shoot.ps1): frame, free-look yaw (deg, left +), pitch (deg, up +)
VIEWS = dict(hold=(1380, -17.9, 22.2), front=(1428, -57.0, 38.7), arrive=(1352, -9.7, 13.0), plain=(1380, 0.0, 0.0),
             close=(1404, -24.4, 33.4), left=(1452, -80.4, 28.9))
# client/src/lib/sect/free-look.ts FREE_LOOK (degrees): the tilt limits and turnLevel's leveling
FREE = dict(max_pitch=60.0, max_view_pitch=80.0, level_pitch=-4.0, level_from=30.0, level_to=110.0)
# position-free per-vertex / per-edge / per-face data a cliff may carry
SAFE_ATTRS = {"position", ".edge_verts", ".corner_vert", ".corner_edge", ".select_vert", ".select_edge", ".select_poly",
              "sharp_edge", "sharp_face", "material_index", ".hide_vert", ".hide_edge", ".hide_poly"}


def log(*a):
    print("PATCH", *a, flush=True)


def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    dry = False
    for a in argv:
        k, eq, v = a.partition("=")
        if k == "DRY_RUN" and eq:
            dry = v.strip().lower() not in ("", "0", "false", "no")
        else:
            raise SystemExit("patch_r62_notch: unknown option %r (DRY_RUN=1)" % a)
    return dry


class Fail(list):
    def add(self, msg):
        log("FAIL", msg)
        self.append(msg)


# ------------------------------------------------------------------------------------------------------ the page's view

def page_view(sc, cam, frame, yaw_deg, pitch_deg):
    """chase.cam's world matrix at ``frame`` turned as the page turns it (free-look.ts composeLook: yaw about world up,
    then pitch about the camera's own right axis; clampLook's limits and turnLevel's leveling). Sets the scene frame.
    No stop framing: the abode has none (framing.ts STOP_FRAMING), and no other stop reaches 1352..1452.
    sect/preview_r62.py renders from it."""
    sc.frame_set(frame)
    Mw = cam.matrix_world.copy()
    R0 = Mw.to_3x3().normalized()
    fwd = R0 @ Vector((0.0, 0.0, -1.0))
    pp = math.degrees(math.asin(max(-1.0, min(1.0, fwd.z))))
    hi = max(0.0, min(FREE["max_pitch"], FREE["max_view_pitch"] - pp))
    lo = min(0.0, max(-FREE["max_pitch"], -FREE["max_view_pitch"] - pp))
    pitch = max(lo, min(hi, pitch_deg))
    up = pp - FREE["level_pitch"]
    lev = 0.0
    if up > 0.0:
        a = abs((yaw_deg + 180.0) % 360.0 - 180.0)
        t = max(0.0, min(1.0, (a - FREE["level_from"]) / (FREE["level_to"] - FREE["level_from"])))
        lev = -up * t * t * (3.0 - 2.0 * t) if t > 0.0 else 0.0
    R = Matrix.Rotation(math.radians(yaw_deg), 3, 'Z') @ R0 @ Matrix.Rotation(math.radians(pitch + lev), 3, 'X')
    out = R.to_4x4()
    out.translation = Mw.translation
    return out


# ------------------------------------------------------------------------------------------------------ what changed

def sig(ob):
    h = hashlib.md5()
    h.update(ob.name.encode())
    h.update((ob.parent.name if ob.parent else "").encode())
    h.update(np.round(np.array(ob.matrix_basis), 4).tobytes())
    if ob.type == 'MESH':
        h.update(ob.data.name.encode())
        co = np.empty(len(ob.data.vertices) * 3)
        ob.data.vertices.foreach_get("co", co)
        h.update(np.round(co, 3).tobytes())
        h.update("|".join(s.material.name if s.material else "" for s in ob.material_slots).encode())
    return h.hexdigest()


def digest(names):
    h = hashlib.md5()
    for nm in sorted(names):
        ob = bpy.data.objects.get(nm)
        h.update(nm.encode())
        if ob is not None:
            h.update(sig(ob).encode())
    return h.hexdigest()


def snapshot():
    """{name: (parent, matrix_basis, data)} of every object, to tell what moved."""
    return {o.name: (o.parent.name if o.parent else "", np.round(np.array(o.matrix_basis), 5).tobytes(),
                     o.data.name if o.data is not None else "") for o in bpy.data.objects}


def counts():
    return dict(meshes=len(bpy.data.meshes), materials=len(bpy.data.materials),
                collections=len(bpy.data.collections), scenes=sorted(s.name for s in bpy.data.scenes),
                node_groups=len(bpy.data.node_groups), images=len(bpy.data.images))


# ------------------------------------------------------------------------------------------------------ the cliff

def analytic_cliff(new):
    """abode._cliff_verts() with the old (new=False) or the round-62 notch, plus the two end-cap centres abode._cliff
    appends, as an (n, 3) array in abode.root's frame."""
    keep = AB.NOTCH_R62
    AB.NOTCH_R62 = bool(new)
    try:
        verts = AB._cliff_verts()
    finally:
        AB.NOTCH_R62 = keep
    ncol = AB.NZ + 1 + AB.NT + AB.NB
    for i in (0, AB.NX):
        a = i * ncol
        verts.append(sum((verts[a + j] for j in range(ncol)), Vector()) / ncol)
    return np.array([tuple(v) for v in verts], float)


def cliff_part(cliff, root, fail):
    """Where abode.cliff moves from the old analytic notch to the turned cleft (delta only). Returns (state, moved
    index array, old analytic positions, new analytic positions, the file's positions) in abode.root's frame."""
    me = cliff.data
    n = len(me.vertices)
    log("cliff: %d vertices, %d faces; modifiers %s, shape keys %s, uv maps %s, custom normals %s" % (
        n, len(me.polygons), [m.type for m in cliff.modifiers], bool(me.shape_keys), [u.name for u in me.uv_layers],
        me.has_custom_normals))
    attrs = sorted("%s(%s,%s)" % (a.name, a.domain, a.data_type) for a in me.attributes)
    extra = [a for a in me.attributes if a.name not in SAFE_ATTRS]
    log("cliff attributes: %s" % ", ".join(attrs))
    if cliff.modifiers or me.shape_keys:
        fail.add("abode.cliff has modifiers or shape keys: the vertex move would not be what renders")
    if extra:
        log("WARN cliff attributes beyond position and edge flags: %s (the rock material reads object and world "
            "position, materials._rock; these are kept as they are)" % [a.name for a in extra])
    if me.uv_layers:
        log("WARN cliff has uv maps %s: the rock material does not read them (object / world triplanar), so they are "
            "left as they are" % [u.name for u in me.uv_layers])
    old = analytic_cliff(False)
    new = analytic_cliff(True)
    if len(old) != n:
        log("NOT SAVED: abode.cliff has %d vertices, the analytic grid %d" % (n, len(old)))
        raise SystemExit(1)
    M = np.array(root.matrix_world.inverted() @ cliff.matrix_world, float)
    log("cliff in abode.root's frame: off identity by %.2g (world coordinates past 1000 m round)" % (
        np.abs(M - np.eye(4)).max()))
    if np.abs(M - np.eye(4)).max() > 1e-3:          # round 56's ROOT_TOL: 1 mm
        log("NOT SAVED: abode.cliff is not at abode.root's frame (%s)" % np.round(M, 4).tolist())
        raise SystemExit(1)
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    P = co.reshape(n, 3)
    d_old = np.linalg.norm(P - old, axis=1)
    log("cliff against the old analytic grid: max %.4f m, mean %.5f m, %d vertices over 1 mm" % (
        d_old.max(), d_old.mean(), int((d_old > 1e-3).sum())))
    delta = new - old
    mv = np.nonzero(np.linalg.norm(delta, axis=1) > MOVE_EPS)[0]
    on_old = np.linalg.norm(P[mv] - old[mv], axis=1)
    on_new = np.linalg.norm(P[mv] - new[mv], axis=1)
    if (on_new <= GRID_TOL).all():
        state = "new"
    elif (on_old <= GRID_TOL).all():
        state = "old"
    else:
        state = "stale"
    dm = np.linalg.norm(delta[mv], axis=1)
    dx = old[mv, 0] - AB.FALL_X
    log("cliff state: %s; %d vertices move (dx %+.2f..%+.2f), by up to %.2f m (mean %.2f), %d up, %d down" % (
        state, len(mv), dx.min() if len(mv) else 0.0, dx.max() if len(mv) else 0.0,
        dm.max() if len(mv) else 0.0, dm.mean() if len(mv) else 0.0, int((delta[mv, 2] > 1e-3).sum()),
        int((delta[mv, 2] < -1e-3).sum())))
    dxa = old[:, 0] - AB.FALL_X
    outside = (dxa < -AB.NOTCH_STRIP[-1]) | (dxa > AB.NOTCH_STRIP[1])
    out_move = float(np.linalg.norm(delta[outside], axis=1).max()) if outside.any() else 0.0
    log("cliff outside dx %+.1f..%+.1f moves at most %.6f m" % (-AB.NOTCH_STRIP[-1], AB.NOTCH_STRIP[1], out_move))
    if out_move > 1e-3:
        fail.add("the cliff moves %.4f m outside the strip dx %+.1f..%+.1f" % (out_move, -AB.NOTCH_STRIP[-1],
                                                                              AB.NOTCH_STRIP[1]))
    if state == "stale":
        log("NOT SAVED: the cliff's moving vertices are on neither grid (old max %.4f, new max %.4f m)" % (
            on_old.max(), on_new.max()))
        raise SystemExit(1)
    return state, mv, old, new, P


def sharp_from_angle(me, moved):
    """Edges with a moved vertex get abode._cliff's auto-smooth rule again (sharp past SHARP_DEG); others keep theirs."""
    ne = len(me.edges)
    at = me.attributes.get("sharp_edge")
    keep = np.zeros(ne, bool)
    if at is not None:
        at.data.foreach_get("value", keep)
    me.set_sharp_from_angle(angle=math.radians(SHARP_DEG))
    at = me.attributes.get("sharp_edge")
    ang = np.zeros(ne, bool)
    if at is not None:
        at.data.foreach_get("value", ang)
    ev = np.empty(ne * 2, np.int64)
    me.edges.foreach_get("vertices", ev)
    mset = np.zeros(len(me.vertices), bool)
    mset[moved] = True
    touched = mset[ev.reshape(ne, 2)].any(1)
    out = np.where(touched, ang, keep)
    if at is None:
        at = me.attributes.new("sharp_edge", 'BOOLEAN', 'EDGE')
    at.data.foreach_set("value", out)
    log("cliff sharp edges: %d before, %d after (%d edges touch a moved vertex: %d sharp before, %d now)" % (
        int(keep.sum()), int(out.sum()), int(touched.sum()), int(keep[touched].sum()), int(out[touched].sum())))


def ground_gaps(objs, b_cliff, root):
    """{name: gap} for each object's origin in abode.root's frame: its height over the cliff surface a downward ray
    finds under it (negative: buried), None where the ray finds no cliff."""
    Rinv = root.matrix_world.inverted()
    out = {}
    for o in objs:
        p = Rinv @ o.matrix_world.translation
        h = b_cliff.ray_cast(Vector((p.x, p.y, p.z + 40.0)), Vector((0.0, 0.0, -1.0)), 200.0)
        out[o.name] = None if h[0] is None else p.z - h[0].z
    return out


# ------------------------------------------------------------------------------------------------------------- main

def main():
    dry = options()
    t0 = time.time()
    fail = Fail()
    sc = bpy.context.scene
    keep_frame = sc.frame_current
    need = ["abode.root", "abode.cliff", "abode.waterfall", EW.CAMERA]
    miss = [n for n in need if bpy.data.objects.get(n) is None]
    if miss:
        log("NOT SAVED: %s not found: is this out/sect_chase.blend?" % miss)
        raise SystemExit(1)
    root = bpy.data.objects["abode.root"]
    cliff = bpy.data.objects["abode.cliff"]
    cam = bpy.data.objects[EW.CAMERA]
    sx = root.matrix_world.to_scale()
    if max(abs(s - 1.0) for s in sx) > 1e-5:
        log("NOT SAVED: abode.root is scaled %s: the checks measure in its frame" % tuple(sx))
        raise SystemExit(1)
    if not AB.NOTCH_R62:
        log("NOT SAVED: abode.NOTCH_R62 is False: nothing to patch")
        raise SystemExit(1)
    old_tries = sorted(o.name for o in bpy.data.objects if OLD_TRY_RE.match(o.name))
    if old_tries:
        log("NOT SAVED: objects of round 62's earlier tries are in the file: %s" % old_tries)
        raise SystemExit(1)
    lip, yc, fx = AB._lip_z(), AB._y_chute(), AB.FALL_X
    log("round 62: lip z %.3f, chute plane y %.3f, FALL_X %.1f (abode.root's frame); risers %s over %s m, wander %s, "
        "bump %s, strip %s; bend %s, head %s (run %.2f, wander %.1f, saddle %.1f)" % (
            lip, yc, fx, AB.NOTCH_RISERS, AB.NOTCH_W, AB.NOTCH_WANDER, AB.NOTCH_BUMP, AB.NOTCH_STRIP, AB.NOTCH_BEND,
            AB.NOTCH_HEAD, AB.NOTCH_HEAD_RUN, AB.NOTCH_HEAD_WANDER, AB.NOTCH_SADDLE))

    # ---- the cliff's state
    c_state, mv, old, new, P0 = cliff_part(cliff, root, fail)
    log("state: cliff %s" % c_state)
    todo = c_state != "new"

    # ---- what stands over the changed strip, before
    strip = []
    Rinv = root.matrix_world.inverted()
    for o in bpy.data.objects:
        if o.name in (cliff.name, root.name) or o.name.startswith(("world.", "flyer")) or o.type in ('CAMERA', 'LIGHT'):
            continue
        p = Rinv @ o.matrix_world.translation
        if abs(p.x - fx) < STRIP_DX and p.z > lip - 1.0 and p.y > yc - 3.0:
            strip.append(o)
    dg = bpy.context.evaluated_depsgraph_get()
    b_old = SU.tri_bvh(SU.owner_tris(dg, root, {cliff.name})[cliff.name])
    gaps0 = ground_gaps(strip, b_old, root)

    # ---- apply
    snap0 = snapshot()
    counts0 = counts()
    log("before: %d objects, %s; %d objects over the changed strip" % (len(snap0), counts0, len(strip)))
    if c_state == "old":
        P1 = P0.copy()
        P1[mv] += (new - old)[mv]
        cliff.data.vertices.foreach_set("co", P1.reshape(-1))
        sharp_from_angle(cliff.data, mv)
        cliff.data.update()
        log("cliff: moved %d vertices by the delta" % len(mv))
    n_quads, n_turned, split_md5, n_long = AB.cliff_split(cliff.data)
    log("cliff quads: %d top-row quads by the cleft, %d turned now to split along their shorter diagonal; Blender "
        "splits %d of them along the longer one" % (n_quads, n_turned, n_long))
    if n_long > SPLIT_LONG_MAX:
        fail.add("%d of the cleft's quads are still split along their longer diagonal (at most %d)" % (
            n_long, SPLIT_LONG_MAX))
    todo = todo or n_turned > 0
    bpy.context.view_layer.update()

    # ---- names, counts, nothing else moved
    snap1 = snapshot()
    counts1 = counts()
    came, gone = sorted(set(snap1) - set(snap0)), sorted(set(snap0) - set(snap1))
    log("objects: added %s, removed %s" % (came, gone))
    if came or gone:
        fail.add("objects added %s / removed %s: the patch moves the cliff's vertices only" % (came, gone))
    moved = [nm for nm in set(snap0) & set(snap1) if snap0[nm] != snap1[nm]]
    if moved:
        fail.add("%d objects changed parent, place or data: %s" % (len(moved), sorted(moved)[:12]))
    log("after: %s" % counts1)
    if counts1 != counts0:
        fail.add("data counts %s, expected %s" % (counts1, counts0))

    dg = bpy.context.evaluated_depsgraph_get()
    b_cliff = SU.tri_bvh(SU.owner_tris(dg, root, {cliff.name})[cliff.name])
    co = np.empty(len(cliff.data.vertices) * 3)
    cliff.data.vertices.foreach_get("co", co)
    Pc = co.reshape(-1, 3)

    # ---- the channel at the lip, and nothing rising into the pour
    ncol = AB.NZ + 1 + AB.NT + AB.NB
    edge = np.array([i * ncol + AB.NZ for i in range(AB.NX + 1)])
    E, E0 = Pc[edge], P0[edge]
    edx = E[:, 0] - fx
    ch = np.abs(edx) <= 9.0
    level = np.abs(edx) <= CHANNEL_HALF
    log("channel: front-edge columns (dx: z - lip (change)) %s" % ", ".join(
        "%+.2f:%+.2f(%+.2f)" % (a, b, b - b0) for a, b, b0 in zip(edx[ch], E[ch, 2] - lip, E0[ch, 2] - lip)))
    on_floor = edx[np.abs(E[:, 2] - lip) <= FLOOR_TOL]
    near = on_floor[np.abs(on_floor) < 6.0]
    if not len(near):
        near = np.array([0.0])
    log("channel: level floor (within %.2f m of the lip) from dx %+.3f to %+.3f: %.2f m wide" % (
        FLOOR_TOL, near.min(), near.max(), near.max() - near.min()))
    if (np.abs(E[level, 2] - lip) > FLOOR_TOL).any():
        fail.add("the channel's front edge is not level at the lip for |dx| <= %.1f: %s" % (
            CHANNEL_HALF, np.round(E[level, 2] - lip, 3).tolist()))
    if (E[level, 2] > E0[level, 2] + 0.01).any():
        fail.add("the channel's front edge rose")
    if near.max() - near.min() < 2.0 * CHANNEL_HALF:
        fail.add("the level floor is %.2f m wide, want %.1f" % (near.max() - near.min(), 2.0 * CHANNEL_HALF))
    # the channel behind the lip, row by row: where its floor is (the columns under lip + CHANNEL_Z), how wide, and
    # how far its middle stands from FALL_X (the cleft turns: abode.NOTCH_BEND). In the mouth (the rows nearer than
    # CHANNEL_BACK m to the front edge) it must stay 2 x CHANNEL_HALF wide for the page's water.
    cols = [i for i in range(AB.NX + 1) if abs(edx[i]) <= 13.6]
    for j in range(1, AB.NT + 1):
        row = np.array([i * ncol + AB.NZ + j for i in cols])
        Q = Pc[row]
        back = float(np.mean(Q[:, 1] - Pc[[i * ncol + AB.NZ for i in cols], 1]))
        low = Q[:, 2] < lip + CHANNEL_Z
        if not low.any():
            log("channel row %d (%.1f m back): no floor under lip + %.1f: lowest lip %+.2f at dx %+.2f" % (
                j, back, CHANNEL_Z, float(Q[:, 2].min() - lip), float(Q[np.argmin(Q[:, 2]), 0] - fx)))
            continue
        fdx = Q[low, 0] - fx
        log("channel row %d (%.1f m back): floor dx %+.2f..%+.2f (%.2f m wide, middle %+.2f), lip %+.2f..%+.2f; "
            "rims lip %+.1f (left) %+.1f (right)" % (
                j, back, fdx.min(), fdx.max(), fdx.max() - fdx.min(), 0.5 * (fdx.min() + fdx.max()),
                float(Q[low, 2].min() - lip), float(Q[low, 2].max() - lip), float(Q[0, 2] - lip), float(Q[-1, 2] - lip)))
        if back < CHANNEL_BACK and fdx.max() - fdx.min() < 2.0 * CHANNEL_HALF - 0.85:   # a column either way
            fail.add("the channel is %.2f m wide %.1f m behind the lip, want %.1f" % (
                fdx.max() - fdx.min(), back, 2.0 * CHANNEL_HALF))

    def pour_zone(Q):       # the page's pour at its crest: over the lip and the first metre behind it
        return (np.abs(Q[:, 0] - fx) < POUR_HALF) & (Q[:, 2] > lip + FLOOR_TOL) & (Q[:, 2] <= lip + POUR_TOP) & \
            (Q[:, 1] < yc + POUR_BACK)
    in0, in1 = pour_zone(P0[mv]), pour_zone(Pc[mv])
    log("pour: moved cliff vertices inside the page's pour at the lip (|dx| < %.2f, lip < z <= lip + %.1f): %d before, "
        "%d after" % (POUR_HALF, POUR_TOP, int(in0.sum()), int(in1.sum())))
    if (in1 & ~in0).any():
        fail.add("%d cliff vertices rose into the pour" % int((in1 & ~in0).sum()))

    # ---- what stands over the changed strip, after
    gaps1 = ground_gaps(strip, b_cliff, root)
    flagged = 0
    for o in sorted(strip, key=lambda o: o.name):
        g0, g1 = gaps0.get(o.name), gaps1.get(o.name)
        if g1 is None:
            continue
        p = Rinv @ o.matrix_world.translation
        bad = g1 < -BURIED_MAX or g1 > FLOAT_MAX
        changed = g0 is None or abs(g1 - g0) > 0.01
        if PINE_RE.match(o.name) and g0 is not None and abs(g1 - g0) > 0.01 and (
                g1 > max(g0, -PINE_ROOT) or g1 < g0 - PINE_SINK):
            fail.add("the cliff under %s moved: its foot is now %.2f m over the cliff (before %.2f; it must stay %.2f "
                     "m in the ground and sink no more than %.2f m)" % (o.name, g1, g0, PINE_ROOT, PINE_SINK))
        if bad or changed:
            if bad:
                flagged += 1
            log("%s %s (%s) at dx %+.1f, z lip %+.1f: %.2f m over the cliff (before %s)%s" % (
                "WARN ground" if bad else "ground", o.name, o.type, p.x - fx, p.z - lip, g1,
                "%.2f" % g0 if g0 is not None else "no cliff under it",
                "" if not bad else (" - buried" if g1 < 0 else " - floating")))
    log("ground: %d objects over the changed strip, %d moved relative to the cliff, %d buried > %.1f m or floating "
        "> %.1f m" % (len(strip), sum(1 for o in strip if gaps1.get(o.name) is not None and gaps0.get(o.name) is not None
                                     and abs(gaps1[o.name] - gaps0[o.name]) > 0.01), flagged, BURIED_MAX, FLOAT_MAX))

    # ---- flight: chase.cam on every frame, against the moved cliff vertices
    frames = list(range(sc.frame_start, sc.frame_end + 1))
    pos = None
    try:
        pos = [M.translation.copy() for M in EW.sample_matrices(cam, frames)]
        sc.frame_set(1380)
        if 1380 in frames and (pos[frames.index(1380)] - cam.matrix_world.translation).length > 0.01:
            log("flight: chase.cam's F-curves miss its pose at 1380: sampling frame by frame")
            pos = None
    except Exception as e:  # noqa: BLE001  (a parented or constrained camera)
        log("flight: sampling chase.cam frame by frame (%s)" % e)
        pos = None
    if pos is None:
        pos = []
        for f in frames:
            sc.frame_set(f)
            pos.append(cam.matrix_world.translation.copy())
    kd = KDTree(max(1, len(mv)))
    for k, i in enumerate(mv):
        kd.insert(Vector(Pc[i]), k)
    kd.balance()
    near_c = (9e9, None)
    for f, pw in zip(frames, pos):
        if len(mv):
            _co, _i, d = kd.find(Rinv @ pw)
            if d < near_c[0]:
                near_c = (d, f)
    log("flight cliff: the moved vertices are %.1f m from chase.cam at its nearest (frame %s)" % near_c)
    if near_c[0] < CAM_MIN:
        fail.add("chase.cam passes %.2f m from the moved cliff (frame %s)" % near_c)
    sc.frame_set(keep_frame)

    # ---- report
    log("DIGEST", hashlib.md5((digest([cliff.name]) + split_md5).encode()).hexdigest())
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail:
            log("  -", f)
        raise SystemExit(1)
    if not todo:
        log("CACHES ok: nothing changed")
        log("nothing changed: not saving (%.1f s)" % (time.time() - t0))
        return
    log("CACHES needs bakefull abode: the cliff moved (no object was added, so the audit and the chunk plan stand) - "
        "run bake_web.py -- bakefull --profile full --quality production --live --chunks abode --light %s, then "
        "live_calib / live_bounce, sect_live and the pack" % TWILIGHT)
    if dry:
        log("DRY_RUN: checks passed, not saving (%.1f s)" % (time.time() - t0))
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "(%.1f s)" % (time.time() - t0))


if __name__ == "__main__":
    main()
