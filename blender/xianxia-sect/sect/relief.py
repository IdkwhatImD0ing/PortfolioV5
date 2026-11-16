"""Round 59 bake-time rock relief (docs/scene/rock-r59.md, "Shape"): sect/relief_rules.py's rules applied in Blender to
copies of the rock that already has a fine mesh and is seen close:

    abode.cliff                    the abode's hero cliff (a 0.8 m grid): beds, soft-bed recesses, joint blocks, lost
                                   blocks, and the in-block folds flattened toward each block's plane
    world.peak.NNN, abode.pinnacle(.NNN), summit.condor_crag
                                   karst columns (lathes): wide flat faces along the two joint sets, steps at the bed
                                   joints the lathe already has, a few missing-block notches; inward only
    arena.island, scenery.island(.NNN), world.islet(.NNN)
                                   floating rocks (0.5-1.9 m segments, 0.7 m rings): soft-bed recesses ring the cone,
                                   blocks break its smooth facets

No new vertex or face anywhere and nothing on the range heightfield (attack_0). Only faces whose material is rock_cliff
move (Ice-Fire Island's own materials, the boulders and the forge rocks are left alone).

bake_web.full_ctx calls relieve_bases on the bake's captured meshes (bake_web.capture: evaluated copies), so the scene
file never changes: no object is added, renamed or moved, the visibility audit and the keep-list stay valid, and the
plants scattered on these meshes by face index stay where they are in the scene. In exchange the relief is 0 near
every plant origin, hall, stair, bridge, plaque, lawn and rock prop that is not relieved (their boxes), near every
waterfall sheet and hanging root (their surfaces, sampled every RR.SAMPLE_STEP m), next to every face that is not
rock_cliff (a column's cap: over RR.COL_CAP; a column's shelf cushions do not pin, attack_0), near the mesh's open
edges, on the abode's dressed rock, slope cap, inscription panel and water chute, and at a column's foot, each fading in
over a few metres. Each relieved mesh gets the POINT float attribute 'geo_w' (1 where fully relieved, 0 where pinned),
which the round 59 rock material reads to turn its own beds and joints off (materials.ROCK_GEO_ATTR), and logs one line:

    RELIEF <name> <kind>: <verts> verts, <moved> moved, mean <m> m, max <m> m, pinned <p> %, <tris> tris, <s> s

preview_r59.py --relief on|off applies the same in memory to copies for the stills. apply_overrides takes KEY=value
for any upper-case constant of sect/relief_rules.py or of this file.
"""
import ast
import collections
import json
import math
import re
import sys
import time
import zlib

import bpy
import numpy as np
from mathutils import Vector, kdtree
from mathutils.bvhtree import BVHTree

from sect import export_web as EW
from sect import relief_rules as RR

RELIEF_OWNER_RE = re.compile(r"^(abode\.cliff|world\.peak\.\d{3}|abode\.pinnacle(\.\d{3})?|summit\.condor_crag"
                             r"|arena\.island|scenery\.island(\.\d{3})?|world\.islet(\.\d{3})?)$")
COLUMN_RE = re.compile(r"^(world\.peak\.\d{3}|abode\.pinnacle(\.\d{3})?|summit\.condor_crag)$")
CLIFF_RE = re.compile(r"^abode\.cliff$")
RELIEF_MAT = "rock_cliff"      # the only material whose faces move (its sect_material tag)
SHELF_MAT = "nature_canopy_mass"   # nature.SHELF_GREEN_MAT: a peak pillar's shelf cushions move with the rock round them
MAT_TAG = "sect_material"      # materials.TAG
GEO_ATTR = "geo_w"             # materials.ROCK_GEO_ATTR, bake_web.COPY_ATTRS
PLANT_PREFIX = "nature.proto." # every instance of a nature prototype is a plant (pinned by its origin)
FALL_WORDS = ("waterfall", "water_fall")   # bake_web.is_fall's material words
SPLIT_NAMES = ("world.range", "world.roots")   # the split terrain: never a structure box (it is everywhere)
ROOT_RE = re.compile(r"(\.roots(\.\d{3})?$|\.roots\.|\.root(\.\d{3})?$|^world\.roots)")   # hanging roots: a floating
                               # rock's '<name>.roots', the arena's own 'arena.root.NNN' tubes, the range's world.roots
# the abode cliff's pinned zones, in its mesh frame (abode.root's: x across, y into the rock, z up). The rectangles and
# blends are the literals of abode._face_y (the dressed rock round the gate and balcony, the inscription panel, the
# water chute); the slope cap and the front edge come from abode's constants (sect.areas.abode CAP_*, YG, _top)
ABODE_RECT = (-16.0, 10.0, -2.0, 5.0)    # x0, x1, z0 and its blend (m); z1 is abode.CAP_Z1
ABODE_INSC = (3.5, 18.5, 41.0, 3.0)      # half width about abode.INSC_X, z0, z1, blend (m)
ABODE_CHUTE = 6.5                        # m either side of abode.FALL_X where the chute's blend ends
ABODE_CAP_TOL = 1.0                      # m: a vertex this near the slope cap's line (or behind it) lies on the cap
ABODE_TOP = 1.5                          # m under the front edge (abode._top) where the relief stops


def _log(*a):
    print("RELIEF", *a, flush=True)


def apply_overrides(items, log=None):
    """KEY=value for any upper-case constant of relief_rules or of this module (a Python literal; a dict merges into
    the constant's keys, a string replaces a compiled pattern). Returns the applied ones."""
    log = log or _log
    done = []
    me = sys.modules[__name__]
    for it in items or ():
        if "=" not in it:
            raise SystemExit("relief override %r: not KEY=value" % it)
        k, v = (s.strip() for s in it.split("=", 1))
        mod = RR if hasattr(RR, k) else (me if hasattr(me, k) else None)
        if mod is None or not k.isupper():
            raise SystemExit("relief override %r: no such constant in relief_rules or relief" % k)
        cur = getattr(mod, k)
        val = ast.literal_eval(v)
        if isinstance(cur, dict) and isinstance(val, dict):
            bad = sorted(set(val) - set(cur))
            if bad:                     # a misspelt key would be added and silently do nothing
                raise SystemExit("relief override %r: %s has no key %s (it has %s)" % (it, k, bad, sorted(cur)))
            new = dict(cur)
            new.update(val)
            val = new
        elif isinstance(cur, re.Pattern) and isinstance(val, str):
            val = re.compile(val)
        setattr(mod, k, val)
        done.append("%s=%r" % (k, val.pattern if isinstance(val, re.Pattern) else val))
    if done:
        log("overrides:", "; ".join(done))
    return done


def kind_of(name):
    """'column', 'cliff' or 'island'."""
    if COLUMN_RE.match(name):
        return "column"
    if CLIFF_RE.match(name):
        return "cliff"
    return "island"


def _tag(m):
    if m is None:
        return None
    t = m.get(MAT_TAG)
    if t:
        return str(t)
    nm = m.name[2:] if m.name.startswith("M.") else m.name
    base, dot, suf = nm.rpartition(".")
    return base if dot and suf.isdigit() else nm


def _is_root(name):
    return bool(ROOT_RE.search(name))


# ---- the context: what every relieved mesh is pinned to -----------------------------------------------------------

def build_context(R, bases, grp=None, ex=None, mat_class=None, only=None, log=None):
    """Targets and pin sources from the gathered records R (export_web.gather) and the captured meshes `bases` (tkey ->
    mesh). grp (bake_web.full_ctx's per-record group): only records baked into an area chunk (grp >= 0) are relieved;
    None relieves every target found. ex: export_web.export_mask (computed when None). mat_class(name, tag) -> 'rock',
    'ground' or None (bake_web.detail_class). only: a regex the target's name must also match (--relief-only). A
    target that is not relieved here (not captured, or left out by `only`) is not a pin either, so the pins, and with
    them every relieved shape, are the same in every session."""
    log = log or _log
    t0 = time.time()
    n = len(R)
    if mat_class is None:
        from sect import bake_web as BW     # noqa: E402  (the preview: bake_web is loaded there already)
        mat_class = BW.detail_class
    if ex is None:
        used = set()
        for t in R.tinfo.values():
            used.update(m for m in t[2] if m)
        minfo = {m: EW.material_info(bpy.data.materials[m]) for m in used if m in bpy.data.materials}
        ex = EW.export_mask(R, minfo)
    ex = np.asarray(ex, bool)
    ccache = {}

    def cls(m):
        if m not in ccache:
            mat = bpy.data.materials.get(m)
            ccache[m] = mat_class(m, mat.get(MAT_TAG) if mat is not None else None)
        return ccache[m]

    tki = {}
    for tk, (_t, _per, mats) in R.tinfo.items():
        ms = [m for m in mats if m]
        tki[tk] = (any(w in m for m in ms for w in FALL_WORDS), any(cls(m) == "rock" for m in ms))
    fall = np.array([tki[t][0] for t in R.tkey], bool)
    rocky = np.array([tki[t][1] for t in R.tkey], bool)
    inst = np.asarray(R.inst, bool)
    plant = inst & np.array([t.startswith(PLANT_PREFIX) for t in R.tkey], bool)
    root = np.array([_is_root(nm) for nm in R.name], bool) & ~plant
    split = np.array([nm.startswith(SPLIT_NAMES) for nm in R.name], bool)
    if grp is not None:
        split |= np.asarray(grp) == -3
    count = collections.Counter(R.tkey)
    ox = re.compile(only) if only else None
    targets, skipped = [], collections.Counter()
    elsewhere = []                 # targets this session does not relieve: their chunk was not asked for (not
    #                                captured) or --relief-only leaves them out. They never pin the others either, so
    #                                an object's relief does not depend on which chunks a session bakes
    for i in np.nonzero(~inst)[0].tolist():
        nm = R.name[i]
        if not RELIEF_OWNER_RE.match(nm):
            continue
        tk = R.tkey[i]
        if grp is not None and int(grp[i]) < 0:
            skipped["not in an area chunk"] += 1
            continue
        if ex[i]:
            skipped["not exported"] += 1
            continue
        if count[tk] != 1:
            skipped["mesh shared"] += 1
            continue
        mats = bases[tk].materials if tk in bases else [bpy.data.materials.get(m) for m in R.tinfo[tk][2] if m]
        if not any(_tag(m) == RELIEF_MAT for m in mats):
            skipped["no rock_cliff slot"] += 1
            continue
        if ox is not None and not ox.search(nm):
            elsewhere.append(i)
            skipped["not --relief-only"] += 1
            continue
        if tk not in bases:
            elsewhere.append(i)
            skipped["not captured"] += 1
            continue
        targets.append(i)
    tmask = np.zeros(n, bool)
    tmask[targets] = True
    tmask[elsewhere] = True
    side = R.hi - R.lo
    diag = np.linalg.norm(side, axis=1)
    smax = side.max(1)
    smid = np.median(side, axis=1)
    cand = ~ex & ~plant & ~fall & ~root & ~tmask & ~split & (~rocky | (diag <= RR.ROCK_PROP_MAX_DIAG))
    long_ = cand & (smax > RR.STRUCT_POINTS[0]) & (smax > RR.STRUCT_POINTS[1] * np.maximum(smid, 1e-3))
    struct = cand & ~long_ & (diag <= RR.STRUCT_MAX_DIAG)
    mw = np.asarray(R.mw, float)
    C = dict(R=R, bases=bases, targets=targets, skipped=dict(skipped),
             plants=mw[plant][:, :3, 3].copy() if plant.any() else np.zeros((0, 3)),
             slo=R.lo[struct], shi=R.hi[struct], long=np.nonzero(long_)[0],
             falls=np.nonzero(fall & ~ex)[0], roots=np.nonzero(root & ~ex)[0], pts={}, log=log)
    log("context: %d targets %s; pins: %d plants, %d structure boxes, %d long structures, %d water records, "
        "%d root records; %.1f s"
        % (len(targets), json.dumps(dict(collections.Counter(kind_of(R.name[i]) for i in targets))),
           len(C["plants"]), int(struct.sum()), len(C["long"]), len(C["falls"]), len(C["roots"]), time.time() - t0),
        ("skipped %s" % json.dumps(dict(skipped))) if skipped else "")
    return C


def _record_points(C, i):
    """World points on record i's surface (vertices and edge samples), memoized; empty when it cannot be read."""
    if i in C["pts"]:
        return C["pts"][i]
    R = C["R"]
    me = C["bases"].get(R.tkey[i])
    own = False
    pts = np.zeros((0, 3))
    if me is None:
        ob = bpy.data.objects.get(R.name[i])
        if ob is not None:
            try:
                dg = bpy.context.evaluated_depsgraph_get()
                me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=False,
                                                     depsgraph=dg)
                own = True
            except Exception as e:
                C["log"]("WARN cannot read", R.name[i], "for the pins:", repr(e))
                me = None
    if me is not None:
        nv, ne = len(me.vertices), len(me.edges)
        co = np.empty(nv * 3, np.float32)
        me.vertices.foreach_get("co", co)
        ed = np.empty(ne * 2, np.int32)
        me.edges.foreach_get("vertices", ed)
        M = np.asarray(R.mw[i], float)
        P = co.reshape(nv, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]
        pts = RR.edge_samples(P, ed.reshape(ne, 2), RR.SAMPLE_STEP)
        if own:
            bpy.data.meshes.remove(me)
    C["pts"][i] = pts
    return pts


def _near_rows(lo, hi, a_lo, a_hi, reach):
    """Rows of boxes (a_lo, a_hi) that come within `reach` m of the box lo, hi."""
    if not len(a_lo):
        return np.zeros(0, np.int64)
    return np.nonzero(np.all(a_lo <= hi + reach, axis=1) & np.all(a_hi >= lo - reach, axis=1))[0]


def _dist(src, q, reach):
    """Distance from each point q to the nearest src point, inf where none lies within `reach` m (voxel filter first,
    then a KD tree)."""
    d = np.full(len(q), np.inf)
    src = np.asarray(src, float).reshape(-1, 3)
    if not len(src) or not len(q):
        return d
    lo, hi = q.min(0) - reach, q.max(0) + reach
    src = src[np.all((src >= lo) & (src <= hi), axis=1)]
    if not len(src):
        return d
    cand = np.nonzero(RR.near_voxels(q, src, reach))[0]
    if not len(cand):
        return d
    kd = kdtree.KDTree(len(src))
    for k, p in enumerate(src.tolist()):
        kd.insert(tuple(p), k)           # tuples, as patch_r11_links and scenery.py pass them
    kd.balance()
    d[cand] = [kd.find(tuple(p))[2] for p in q[cand].tolist()]
    return d


def _mesh_arrays(me):
    nv, nl, npl, ne = len(me.vertices), len(me.loops), len(me.polygons), len(me.edges)
    co = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get("co", co)
    vi = np.empty(nl, np.int32)
    me.loops.foreach_get("vertex_index", vi)
    ls = np.empty(npl, np.int32)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(npl, np.int32)
    me.polygons.foreach_get("loop_total", lt)
    mi = np.empty(npl, np.int32)
    me.polygons.foreach_get("material_index", mi)
    fn = np.empty(npl * 3, np.float32)
    me.polygons.foreach_get("normal", fn)
    ar = np.empty(npl, np.float32)
    me.polygons.foreach_get("area", ar)
    ed = np.empty(ne * 2, np.int32)
    me.edges.foreach_get("vertices", ed)
    ed = ed.reshape(ne, 2).astype(np.int64)
    # each loop's edge from the vertex pairs (the repo reads no loop 'edge_index' anywhere; these two calls it does)
    le = RR.loop_edges(vi, ls, lt, ed, nv)
    return dict(nv=nv, ne=ne, co=co.reshape(nv, 3).astype(np.float64), vi=vi.astype(np.int64),
                le=le, ls=ls, lt=lt, mi=mi, fn=fn.reshape(npl, 3).astype(np.float64),
                ar=ar.astype(np.float64), ed=ed, lf=np.repeat(np.arange(npl), lt))


def _unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)


def _abode_zone(co):
    """abode_zone on the abode cliff's own vertices (its mesh frame)."""
    from sect.areas import abode as AB     # noqa: E402  (imported only when the cliff is relieved)
    x = co[:, 0]
    ux, inv = np.unique(np.round(x, 3), return_inverse=True)
    top = np.array([AB._top(float(v)) for v in ux])[inv.reshape(-1)]
    cx = AB.CAP_X
    Z = dict(rect=(ABODE_RECT[0], ABODE_RECT[1], ABODE_RECT[2], AB.CAP_Z1, ABODE_RECT[3]),
             insc=(AB.INSC_X - ABODE_INSC[0], AB.INSC_X + ABODE_INSC[0], ABODE_INSC[1], ABODE_INSC[2], ABODE_INSC[3]),
             chute=(AB.FALL_X, ABODE_CHUTE),
             cap=(cx[0], cx[1], cx[2], cx[3], AB.CAP_Z1, AB.CAP_SLOPE, AB.YG, ABODE_CAP_TOL),
             top=ABODE_TOP)
    return RR.abode_zone(x, co[:, 1], co[:, 2], top, Z)


# ---- one mesh -----------------------------------------------------------------------------------------------------

def relieve_mesh(me, M, name, C, geo, log=None):
    """Relieve mesh `me` (object-local, world matrix M) of the object `name` in place. Returns its numbers."""
    log = log or C["log"]
    t0 = time.time()
    kind = kind_of(name)
    A = _mesh_arrays(me)
    nv = A["nv"]
    co, vi, lf, ed = A["co"], A["vi"], A["lf"], A["ed"]
    info = dict(name=name, kind=kind, verts=nv, tris=int((A["lt"] - 2).sum()), moved=0, mean=0.0, max=0.0,
                pinned=0.0, seconds=0.0)
    if nv == 0 or not len(A["ls"]):
        return info
    tags = [_tag(m) for m in me.materials] or [None]
    rock_slot = np.array([t == RELIEF_MAT for t in tags], bool)
    shelf_slot = np.array([t == SHELF_MAT for t in tags], bool) if kind == "column" else np.zeros(len(tags), bool)
    k = np.clip(A["mi"], 0, len(tags) - 1)
    f_rock = rock_slot[k]
    f_pin = ~f_rock & ~shelf_slot[k]
    v_rock = np.zeros(nv, bool)
    v_rock[vi[f_rock[lf]]] = True
    v_pin = np.zeros(nv, bool)
    v_pin[vi[f_pin[lf]]] = True
    # a column's shelf cushions are bands of its lathe: they move with the rings round them. A ring between two
    # cushion bands (a hero shelf whose rounded shoulder is a shelf face too) has no rock face, and left out it stood
    # out as a flange
    v_lathe = v_rock.copy()
    v_lathe[vi[shelf_slot[k][lf]]] = True
    L = np.asarray(M, float)[:3, :3]
    tr = np.asarray(M, float)[:3, 3]
    Linv = np.linalg.inv(L)
    P = co @ L.T + tr
    # normals out of the rock whatever the winding (some floating rocks are inside out)
    sgn = RR.outward_sign(co, vi, A["ls"], A["fn"], A["ar"], ed)
    wn = A["fn"] * (A["ar"] * sgn)[:, None]
    vn = np.stack([np.bincount(vi, wn[lf, c], minlength=nv) for c in range(3)], 1)
    info["inside_out"] = int((sgn < 0).sum())
    ns = _unit(RR.mesh_smooth(_unit(vn @ Linv), ed, RR.NRM_ITERS, nv=nv))
    steep = RR.smoothstep(RR.RELIEF_STEEP[0], RR.RELIEF_STEEP[1], np.abs(ns[:, 2]))

    # ---- pins (world space) ----
    lo, hi = P.min(0), P.max(0)
    w_pin = np.ones(nv)
    if v_pin.any():
        fade = RR.COL_CAP if kind == "column" else RR.PIN_NONROCK
        w_pin *= RR.pin(_dist(P[v_pin], P, fade[1]), fade)
    w_pin *= RR.pin(_dist(C["plants"], P, RR.PIN_VEG[1]), RR.PIN_VEG)
    rows = _near_rows(lo, hi, C["slo"], C["shi"], RR.PIN_STRUCT[1])
    if len(rows):
        w_pin *= RR.pin(RR.box_dist(P, C["slo"][rows], C["shi"][rows]), RR.PIN_STRUCT)
    R = C["R"]
    for recs, fade in ((C["falls"], RR.PIN_WATER), (C["roots"], RR.PIN_ROOT), (C["long"], RR.PIN_STRUCT)):
        near = recs[_near_rows(lo, hi, R.lo[recs], R.hi[recs], fade[1])] if len(recs) else recs
        if len(near):
            src = np.concatenate([_record_points(C, int(i)) for i in near] + [np.zeros((0, 3))])
            w_pin *= RR.pin(_dist(src, P, fade[1]), fade)
    cnt = np.bincount(A["le"], minlength=A["ne"])
    bnd = np.unique(ed[cnt == 1].ravel())
    if len(bnd):
        w_pin *= RR.pin(_dist(P[bnd], P, RR.PIN_EDGE[1]), RR.PIN_EDGE)
    zone = _abode_zone(co) if kind == "cliff" else np.ones(nv)

    # ---- the move ----
    tops = np.zeros(0)
    scale = 1.0
    if kind == "column":
        ob = bpy.data.objects.get(name)
        kx = ky = 0.0
        dip = ob.get("nature_dip") if ob is not None else None
        if dip is not None and len(dip) >= 2:
            kd_ = math.tan(math.radians(float(dip[0])))
            kx, ky = kd_ * math.cos(float(dip[1])), kd_ * math.sin(float(dip[1]))
        x, y, z = co[:, 0], co[:, 1], co[:, 2]
        z0 = z - kx * x - ky * y
        r = np.hypot(x, y)
        theta = np.arctan2(y, x)
        wall = v_lathe & (r > 0.05)
        plinth = ob.get("r48_plinth") if ob is not None else None
        if plinth is not None:
            base = float(plinth) - float(tr[2])
        else:
            base = float(z0[wall].min()) + RR.COL_FOOT_SINK if wall.any() else float(z0.min())
        foot = RR.smoothstep(base + RR.COL_FOOT[0], base + RR.COL_FOOT[1], z0)
        # no steep weight here: the move is radial, so a shelf's two rings move together and the shelf keeps its
        # width. Weighted by steepness, a shelf's lip kept the old radius and stood out as a flange 1-2 m past the
        # shaved face round it (a stack of drums). The dome is pinned as a non-rock face, the foot by `foot`
        w = w_pin * zone * foot * v_lathe
        radial = np.stack([np.cos(theta), np.sin(theta), np.zeros(nv)], 1)
        D = np.zeros(nv)
        if wall.any():
            r_env, Rz = RR.envelope(theta[wall], z0[wall], r[wall])
            tops = RR.column_bed_tops(z0[wall], r=r[wall], theta=theta[wall])
            yaw = math.atan2(L[1, 0], L[0, 0])
            planes = RR.column_planes(zlib.crc32(name.encode()) & 0x7FFFFFFF,
                                      (math.radians(RR.GEO_JOINT_A["az"]) - yaw,
                                       math.radians(RR.GEO_JOINT_B["az"]) - yaw))
            tl = np.stack([-np.sin(theta), np.cos(theta), np.zeros(nv)], 1)
            _hz, ht = RR.vertex_spacing(co, ed, tl)
            w_th = RR.lp_width(ht[wall]) / np.maximum(r[wall], 0.5)
            D[wall] = RR.column_field(theta[wall], z0[wall], r_env, Rz, tops,
                                      zlib.crc32(name.encode()) & 0x7FFFFFFF, planes, w_th)
        d = ((w * D)[:, None] * radial) @ L.T
        u_out = _unit(radial @ L.T)
        info["tops"] = int(len(tops))
    else:
        nh = ns.copy()
        nh[:, 2] = 0.0
        hl = np.linalg.norm(nh, axis=1)
        ok = hl >= 0.2
        dvec = nh / np.maximum(hl, 1e-9)[:, None] * ok[:, None]
        w = steep * w_pin * zone * v_rock * ok
        tdir = np.stack([-dvec[:, 1], dvec[:, 0], np.zeros(nv)], 1)
        D = np.zeros(nv)
        key = np.full(nv, -1, np.int64)
        act = w > 0.0
        if act.any():
            hz, ht = RR.vertex_spacing(P, ed, tdir)
            Da, ka = geo.field(P[act], tdir[act], RR.lp_width(hz[act]), RR.lp_width(ht[act]))
            D[act], key[act] = Da, ka
        rad = 0.5 * max(float(hi[0] - lo[0]), float(hi[1] - lo[1]))
        scale = RR.object_scale(rad)
        D *= scale
        pl = RR.planarize(P, dvec, key, w, RR.PLANARIZE.get(kind, 0.0))
        pl = RR.mesh_smooth(pl, ed, RR.PLANAR_LP_ITERS, nv=nv)
        d = (w * D)[:, None] * dvec + w[:, None] * pl
        u_out = dvec
        info["scale"] = round(scale, 3)
    d = RR.cap_moves(d)                 # the field and the flattening together: at most MOVE_MAX m

    # ---- thin rock: no fold-through ----
    m = (d * u_out).sum(1)
    need = np.nonzero(np.abs(m) > 0.01)[0]
    thin = 0
    if len(need):
        polys = [A["vi"][s:s + n].tolist() for s, n in zip(A["ls"].tolist(), A["lt"].tolist())]
        bvh = BVHTree.FromPolygons(P.tolist(), polys)
        t = np.full(nv, RR.RELIEF_THICK[2])
        o = P - 0.02 * u_out
        for j in need.tolist():
            hit = bvh.ray_cast(Vector(o[j].tolist()), Vector((-u_out[j]).tolist()), RR.RELIEF_THICK[2])
            if hit[0] is not None:
                t[j] = hit[3]
        m2 = RR.guard_move(m, t)
        d = d + (m2 - m)[:, None] * u_out
        thin = int((t[need] < RR.RELIEF_THICK[1]).sum())

    # ---- write back ----
    mv = np.linalg.norm(d, axis=1)
    if (mv > 1e-4).any():
        co2 = (P + d - tr) @ Linv.T
        me.vertices.foreach_set("co", co2.astype(np.float32).ravel())
        me.update()
        a = me.attributes.get("custom_normal")
        if a is not None:
            me.attributes.remove(a)
        _sharpen(me, A, w)
    a = me.attributes.get(GEO_ATTR)
    if a is not None and (a.domain != "POINT" or a.data_type != "FLOAT"):
        me.attributes.remove(a)
        a = None
    if a is None:
        a = me.attributes.new(GEO_ATTR, "FLOAT", "POINT")
    a.data.foreach_set("value", w.astype(np.float32))
    me.update()
    on = v_rock & ((foot > 0.0) if kind == "column" else (steep > 0.0))   # the rock the relief may move at all
    moved = mv > 0.01
    info.update(moved=int(moved.sum()), mean=round(float(mv[moved].mean()) if moved.any() else 0.0, 3),
                max=round(float(mv.max()), 3),
                pinned=round(float(((w_pin * zone)[on] < 0.5).mean()) if on.any() else 0.0, 3), thin=thin,
                geo_w=round(float(w[v_rock].mean()) if v_rock.any() else 0.0, 3), seconds=round(time.time() - t0, 2))
    log("RELIEF %s %s: %d verts, %d moved, mean %.2f m, max %.2f m, pinned %.0f %%, %d tris, %.1f s%s%s"
        % (name, kind, nv, info["moved"], info["mean"], info["max"], 100.0 * info["pinned"], info["tris"],
           info["seconds"], ("; %d bed tops" % info["tops"]) if kind == "column" else "; scale %.2f" % scale,
           ("; %d faces inside out" % info["inside_out"]) if info["inside_out"] else ""))
    return info


def _sharpen(me, A, w):
    """Edges the relief folded past RR.RELIEF_SHARP_DEG (and by RR.RELIEF_SHARP_GAIN more than before), both ends
    relieved (w > 0.5), shade sharp: the new bed steps and column corners read as edges, not as soft bulges. Other edges
    keep what they had."""
    if not RR.RELIEF_SHARP_DEG:
        return 0
    ne = A["ne"]
    npl = len(A["ls"])
    fn2 = np.empty(npl * 3, np.float32)
    me.polygons.foreach_get("normal", fn2)
    fn2 = fn2.reshape(npl, 3).astype(np.float64)
    le, lf = A["le"], A["lf"]
    cnt = np.bincount(le, minlength=ne)
    order = np.argsort(le, kind="stable")
    first = np.searchsorted(le[order], np.arange(ne))
    two = np.nonzero(cnt == 2)[0]
    if not len(two):
        return 0
    fa, fb = lf[order][first[two]], lf[order][first[two] + 1]
    after = RR.fold_deg(fn2[fa], fn2[fb])
    before = RR.fold_deg(A["fn"][fa], A["fn"][fb])
    ends = A["ed"][two]
    new = ((after > RR.RELIEF_SHARP_DEG) & (after > before + RR.RELIEF_SHARP_GAIN)
           & (w[ends[:, 0]] > 0.5) & (w[ends[:, 1]] > 0.5))
    if not new.any():
        return 0
    cur = np.zeros(ne, bool)
    a = me.attributes.get("sharp_edge")
    if a is not None and (a.domain != "EDGE" or a.data_type != "BOOLEAN"):
        me.attributes.remove(a)
        a = None
    if a is None:
        a = me.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
    else:
        a.data.foreach_get("value", cur)
    cur[two[new]] = True
    a.data.foreach_set("value", cur)
    return int(new.sum())


# ---- all of them --------------------------------------------------------------------------------------------------

def relieve_bases(ctx, bases):
    """Relieve every target among the captured meshes `bases` (tkey -> mesh, changed in place). ctx: R (records),
    grp, ex, mat_class, only (see build_context), overrides (KEY=value list), log. Returns dict(objects: tkey ->
    numbers, records: record index -> kind, summary). Raises on any failure: a bake must not go on half relieved."""
    log = ctx.get("log") or _log
    t0 = time.time()
    if ctx.get("overrides"):
        apply_overrides(ctx["overrides"], log)
    R = ctx["R"]
    C = build_context(R, bases, grp=ctx.get("grp"), ex=ctx.get("ex"), mat_class=ctx.get("mat_class"),
                      only=ctx.get("only"), log=log)
    geo = RR.Geo()
    objs, recs = {}, {}
    for i in C["targets"]:
        tk = R.tkey[i]
        try:
            info = relieve_mesh(bases[tk], np.asarray(R.mw[i], float), R.name[i], C, geo, log)
        except Exception:
            log("FAILED on", R.name[i])
            raise
        objs[tk] = info
        recs[int(i)] = info["kind"]
    vals = list(objs.values())
    moved = sum(v["moved"] for v in vals)
    by = collections.Counter(v["kind"] for v in vals)
    summary = dict(objects=len(vals), kinds=dict(by), verts=sum(v["verts"] for v in vals), moved=moved,
                   mean=round(sum(v["mean"] * v["moved"] for v in vals) / moved, 3) if moved else 0.0,
                   max=max([v["max"] for v in vals] or [0.0]),
                   pinned=round(sum(v["pinned"] * v["verts"] for v in vals) / max(1, sum(v["verts"] for v in vals)), 3),
                   largest=[[v["name"], v["max"]] for v in sorted(vals, key=lambda v: -v["max"])[:5]],
                   skipped=C["skipped"], seconds=round(time.time() - t0, 1))
    log("relief:", json.dumps(summary))
    return dict(objects=objs, records=recs, summary=summary)
