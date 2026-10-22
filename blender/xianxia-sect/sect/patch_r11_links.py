"""Round 11, lane 'links': bring the link stairways of an existing out/sect_chase.blend, and the range under them, to
what sect/world.py now builds (diagnosis: stairs/diag.md S1, S2, S4, plus the pillow shading found while fixing them).
Run on the cloud box, on a copy first:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background         E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1         --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r11_links.py [-- DRY_RUN=1] [DEBUG=1]

Why (owner, 2026-10-22): "Some of the stairs still flicker/have some weird textures/shadows". The web draws every baked
face double-sided, so two faces in one plane z-fight whichever way they face, and in the bake each blocks the other's
light. What it changes, per stairway world.link.<a>_<b> (8 of them; same object names, new mesh data):
1. .rest_landing / .rest_rail (S1): the slab's top is flush with the treads and its inner edge meets them edge to edge,
   following the stair's side through every centreline sample (it ran straight 0.2 m in under them, 4 mm down). Its
   walls stand on it REVEAL (2 cm) in from its faces with their bottoms WALL_SINK (10 cm) down in it (they shared the
   slab's outer, end and bottom faces exactly), the end walls stopping at the side wall.
2. .stairs, .foot_landing, .foot_rail (S2): no treads over the foot landing; its slab's top is the floor up to the
   first riser, flush with the depart point and the first tread (the treads lay 4 mm over it). Its walls stand on it
   like the rest landing's. No tread a few mm long beside a riser (a sample within 1 cm of a riser made one: two riser
   faces mm apart).
3. .rails (S4): each parapet run is one continuous solid through every centreline sample, smooth along the run and
   sharp at its corners and ends (sharp_edge); it was a box every 2 samples. On the pavilion's side it stops exactly at
   the rest landing's ends (the boxes ran 0.5 m onto the slab, in the slab's plane, or stopped up to 1.1 m short).
4. .arch (library -> steles bridge): its sides stand REVEAL inside the parapets' outer faces (a 0.3 m band shared them).
   .piers: the footings' end faces stand REVEAL in from the treads' faces; the corbelled piers are unchanged.
5. Shading: every link box is flat-shaded (.rest_pier and the chain bridge's .deck, .boards, .posts in place, vertices
   untouched). world.py's _mesh_np never set smooth=False, and faces made through the mesh API are smooth in Blender 5:
   every tread, parapet box, landing, wall and pier shaded as a pillow, normals averaged round its 90 deg corners, and
   the bake gave each a light-to-dark ramp (the "scales" on the parapets).
6. world.range (S2): world.sink_under_links lowers it SINK (5 cm) inside the stairs' footprints wherever it lay at the
   treads' or landings' level (they lay in the terrace's plane where a stair rests on a terrace: the flicker there and
   the dark band baked across the top of the gate -> mirror stair). The stairs do not move, so their risers and joins
   to the areas stay as they are; the range is never floor for walkcheck.
7. steles.arrival (verifier, round 11): the steles forecourt box (areas/steles.py FORE_Y0) ran 1 m past the arrival
   line, under the library -> steles stair's last tread and in its plane (5 m2: z-fighting, and the same dark band the
   gate -> mirror stair top had). It now starts at the arrival line, where the tread meets it edge to edge (its 4 outer
   corners move 1 m in; nothing stands on the strip, checked). The summit's twin (summit.terrace under the abode stair)
   is patch_r11_areas.py's (summit._arrival_cut).
world.root['links'] gets the rebuilt reports.

Guards (nothing is saved when one fails): world.range on the 2.5 m grid with no transform; each link's ports where the
scene's report has them (2 cm); each rebuilt piece is either already the new one (vertex for vertex, 1 mm: a re-run)
or the scene's old piece as the old code built it from the same plan: the treads past the foot landing match one to
one (but the mm-long ones merged beside a riser), every old parapet vertex is a vertex of the new solid (but within
0.25 m of a run end that moved and over the rest opening), the arch is the old one 2 cm narrower each side, the piers
the old ones with only the footing end faces moved 2 cm, .rest_pier unchanged, and the landings and walls have the old
recipe's counts and heights; every replaced object keeps one user and its material slots; names stay exact and the
object count is unchanged.

Checks after the change (no save when one fails):
- coplanar overlap scan of every link piece against everything near it (the range, the areas' paving, the other link
  pieces): area of faces that have a parallel face within OVERLAP_D (5 mm) over them, split into same-facing and
  visible (a z-fight), same-facing but inside a solid (hidden), and opposite-facing (two solids touching: hidden);
  logged per link before and after with the worst partners. After: at most VISIBLE_MAX_LINK m2 visible per link among
  the pieces this patch rebuilt and the range. Logged, not failed: where a corbel of the (unchanged) piers crosses a
  curved parapet or tread face, and stair ends lying in an area's own slab (steles.arrival, summit.terrace: their files).
- walk: rays down every 0.1 m along each stairway (centre and 2 m to each side) land on the link's floor at the plan's
  level (2 mm), risers at most world.RISER, 2 m clear overhead; the rest landing is one floor with the treads across
  its opening, the parapet and its end walls standing beside it; the foot landing is one floor across; the floor just
  past both ends is what it was (the range there may dip, at most SINK); a ray every 0.25 m finds each parapet at its
  height along every run.
- the range: how many vertices moved, how far (at most SINK + SINK_UP), and every mesh object (not a link's) whose
  base sat on the moved range, with the gap that opened under it (at most GAP_MAX: the areas' steps at a stair's end).
- rails: every face smooth, sharp edges set; every other replaced piece flat.

Caches: the replaced meshes keep their names; their boxes stay inside the old ones but for the landings' tops, now
flush with the treads (4 mm higher). The range's box does not change. So it prints 'PATCH CACHES ok' when every new box
lies inside its old one within BOX_TOL (5 mm), else 'PATCH CACHES needs audit'. Either way re-bake every area chunk a
stairway or its sunk range passes (gate, mirror, forge, mission, library, steles, scroll, formation, abode, summit)
plus the backdrop (bake_web.py now keeps the link structure whole in the area proxies, S3), then the pack.
Idempotent: a second run finds the new pieces, sinks nothing more and saves the same file.
"""
import json
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils import kdtree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import world as W  # noqa: E402

TOL = 1e-3                     # m: rebuilt vertices must match the scene's this closely
PORT_TOL = 0.02                # m: the ports against world.root's report
BOX_TOL = 0.005                # m: a new box this far past its old one still counts as inside (CACHES ok)
OVERLAP_D = 0.005              # m: two parallel faces this close (along the normal) over each other overlap
SAMPLE_M2 = 0.1                # m2 of face per scan sample
VISIBLE_MAX_LINK = 0.5         # m2: visible same-facing overlap allowed per link after the patch
GAP_MAX = W.SINK + 0.002       # m: an object that sat on the range may stand at most this far over it afterwards.
                               # The range moves only inside the stairs' footprints, but a 2.5 m triangle with a corner
                               # just inside a stair's end tilts under the area's own steps beyond it: they get a gap of
                               # up to SINK, closing over the cell, shut on the stair's side by its end face. Logged
STELES_SLAB = "steles.arrival"   # areas/steles.py's forecourt box (_arrival)
STELES_Y0_OLD = -57.0          # its outer edge before round 11: 1 m past the arrival line, under the stair's last tread
REPLACE = ("stairs", "rails", "foot_landing", "foot_rail", "rest_landing", "rest_rail", "arch", "piers")
SAME = ("rest_pier",)
FLAT_ONLY = ("piers", "arch", "rest_pier", "bridge.deck", "bridge.boards", "bridge.posts")
SKIP_SCAN = ("world.haze", "world.cloud", "world.cirrus", "world.moon")


def log(*a):
    print("PATCH", *a, flush=True)


def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opt = dict(DRY_RUN=False, DEBUG=False)
    for a in argv:
        k, eq, v = a.partition("=")
        if k in opt and eq:
            opt[k] = v.strip().lower() not in ("", "0", "false", "no")
        else:
            raise SystemExit("patch_r11_links: unknown option %r (DRY_RUN=1, DEBUG=1)" % a)
    return opt["DRY_RUN"], opt["DEBUG"]


# ---- small helpers --------------------------------------------------------------------------------------------

def coords(me):
    a = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


def tris(me):
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def world_box(ob):
    c = coords(ob.data)
    if not len(c):
        return None
    M = np.array(ob.matrix_world)
    w = c @ M[:3, :3].T + M[:3, 3]
    return w.min(0), w.max(0)


def same_mesh(a, b, tol=TOL):
    ca, cb = coords(a), coords(b)
    if ca.shape != cb.shape or len(a.polygons) != len(b.polygons):
        return False, "vertices %d vs %d, faces %d vs %d" % (len(ca), len(cb), len(a.polygons), len(b.polygons))
    d = float(np.abs(ca - cb).max()) if len(ca) else 0.0
    return d <= tol, "max vertex offset %.4f m" % d


def range_grid(r):
    k = (coords(r.data)[:, 0] - W.EXTENT[0]) / 2.5
    kr = np.round(k)
    odd = (np.abs(k - kr) < 1e-4) & (kr % 2 == 1)
    return 2.5 if int(odd.sum()) > 1000 else 5.0


def swap(ob, new_ob):
    """Give ``ob`` the mesh of ``new_ob`` (its name, object, collections and props stay); drop both leftovers."""
    if any(s.link != 'DATA' for s in ob.material_slots):
        raise RuntimeError("%s has object-linked material slots" % ob.name)
    if ob.data.users != 1:
        raise RuntimeError("%s's mesh has %d users" % (ob.name, ob.data.users))
    old_me, me = ob.data, new_ob.data
    name = old_me.name
    bpy.data.objects.remove(new_ob, do_unlink=True)
    ob.data = me
    bpy.data.meshes.remove(old_me)
    me.name = name


def smooth_state(me):
    sm = np.zeros(len(me.polygons), bool)
    me.polygons.foreach_get("use_smooth", sm)
    return "smooth" if sm.all() else ("flat" if not sm.any() else "mixed")


def sharp_count(me):
    a = me.attributes.get("sharp_edge")
    if a is None:
        return 0
    v = np.zeros(len(me.edges), bool)
    a.data.foreach_get("value", v)
    return int(v.sum())


def stations_of(geo, pts):
    """Station (m along the centreline) of the nearest centreline point to each XY point."""
    s, xy = geo["s"], geo["xy"]
    q = np.linspace(0.0, float(s[-1]), int(s[-1] / 0.02) + 1)
    c = np.stack([np.interp(q, s, xy[:, 0]), np.interp(q, s, xy[:, 1])], axis=1)
    kd = kdtree.KDTree(len(q))
    for i, (x, y) in enumerate(c):
        kd.insert((float(x), float(y), 0.0), i)
    kd.balance()
    return np.array([q[kd.find((float(p[0]), float(p[1]), 0.0))[1]] for p in pts])


# ---- the old code's recipe, for the guards ----------------------------------------------------------------------

def old_cuts(geo):
    s, sr = geo["s"], geo["plan"]["sr"]
    c = np.unique(np.concatenate([s, sr]))
    return c[np.concatenate([[True], np.diff(c) > 1e-4])]


def new_cuts(geo, foot):
    """world._stairway's tread stations (round 11): samples within 1 cm of a riser or the foot dropped."""
    s, sr = geo["s"], geo["plan"]["sr"]
    L = float(s[-1])
    fixed = np.concatenate([sr, [foot] if foot else []])
    s_cut = s[np.abs(s[:, None] - fixed[None, :]).min(axis=1) > 0.01] if len(fixed) else s
    c = np.unique(np.concatenate([[0.0, L], s_cut, fixed]))
    return c[np.concatenate([[True], np.diff(c) > 1e-4])]


def guard_stairs(nm, old_me, new_me, geo, foot):
    """'new' when the scene already has the new treads; 'old' when every old tread past the foot landing (start at
    least foot + 0.9 m) is a new tread vertex for vertex, except the few mm-long ones beside a riser that the new
    stations merge into their neighbour."""
    ok, why = same_mesh(old_me, new_me)
    if ok:
        return "new", why
    co, cn = coords(old_me), coords(new_me)
    oc, nc = old_cuts(geo), new_cuts(geo, foot)
    n_old, n_new = len(oc) - 1, int((nc[1:] > foot + 1e-6).sum())
    if len(co) != 8 * n_old or len(cn) != 8 * n_new:
        raise RuntimeError("%s.stairs: %d / %d vertices for %d / %d treads (old / new plan)"
                           % (nm, len(co), len(cn), n_old, n_new))
    kept = nc[1:] > foot + 1e-6
    by_span = {(round(float(a), 6), round(float(b), 6)): j for j, (a, b) in enumerate(zip(nc[:-1][kept], nc[1:][kept]))}
    sr = geo["plan"]["sr"]
    worst, matched, skipped, merged = 0.0, 0, 0, 0
    for k in range(n_old):
        if oc[k] < foot + 0.9:
            skipped += 1
            continue
        j = by_span.get((round(float(oc[k]), 6), round(float(oc[k + 1]), 6)))
        if j is None:
            near_riser = min(float(np.abs(sr - oc[k]).min()), float(np.abs(sr - oc[k + 1]).min())) < 0.0101 \
                if len(sr) else False
            if not near_riser:
                raise RuntimeError("%s.stairs: old tread %d (%.3f-%.3f) has no new tread" % (nm, k, oc[k], oc[k + 1]))
            merged += 1
            continue
        worst = max(worst, float(np.abs(co[8 * k:8 * k + 8] - cn[8 * j:8 * j + 8]).max()))
        matched += 1
    if worst > TOL:
        raise RuntimeError("%s.stairs: the treads past the foot landing moved %.4f m: the plan changed" % (nm, worst))
    return "old", "%d treads match (worst %.4f m), %d beside a riser merged, %d at the foot replaced" % (
        matched, worst, merged, skipped)


def guard_rails(nm, old_me, new_me, geo, keys, opening=None):
    """'new' when equal; 'old' when every old parapet vertex is a vertex of the new solids within TOL, but those
    within 0.25 m of a run end that moved (keys: stations) and, on the pavilion's side, those over the rest landing's
    new opening (opening: (start, end, side); the old boxes ran 0.5 m onto the slab at each end)."""
    ok, why = same_mesh(old_me, new_me)
    if ok:
        return "new", why
    co, cn = coords(old_me), coords(new_me)
    if len(co) % 8:
        raise RuntimeError("%s.rails: %d vertices, not 8-corner boxes and not the new solids" % (nm, len(co)))
    kd = kdtree.KDTree(len(cn))
    for i, p in enumerate(cn):
        kd.insert(Vector(p), i)
    kd.balance()
    st = stations_of(geo, co[:, :2])
    near_key = np.abs(st[:, None] - np.asarray(keys)[None, :]).min(axis=1) < 0.25 if len(keys) else np.zeros(len(co), bool)
    if opening is not None:
        a, b, side = opening
        s, xy, yaw = geo["s"], geo["xy"], geo["yaw"]
        c, nl, _ = W._frame(s, xy, yaw, st)
        lat = ((co[:, :2] - c) * nl).sum(axis=1)
        near_key |= (st > a - 0.25) & (st < b + 0.25) & (lat * side > 0)
    d = np.array([kd.find(Vector(p))[2] for p in co])
    bad = (d > TOL) & ~near_key
    if bad.any():
        i = int(np.argmax(np.where(bad, d, 0)))
        raise RuntimeError("%s.rails: %d old parapet vertices off the new solids (worst %.4f m at %s, station %.2f)"
                           % (nm, int(bad.sum()), float(d[i]), np.round(co[i], 2).tolist(), float(st[i])))
    return "old", "%d old boxes' vertices on the new solids (%d near moved run ends skipped)" % (
        len(co) // 8, int(near_key.sum()))


def guard_arch(nm, old_me, new_me):
    """The bridge arch: 'new' when equal; 'old' when the same prisms stood REVEAL wider on each side (same heights)."""
    ok, why = same_mesh(old_me, new_me)
    if ok:
        return "new", why
    co, cn = coords(old_me), coords(new_me)
    if co.shape != cn.shape:
        raise RuntimeError("%s.arch: %d vertices, rebuilt %d" % (nm, len(co), len(cn)))
    dz = float(np.abs(co[:, 2] - cn[:, 2]).max())
    dxy = np.linalg.norm(co[:, :2] - cn[:, :2], axis=1)
    if dz > TOL or abs(float(dxy.max()) - W.REVEAL) > TOL or float(dxy.min()) < W.REVEAL - TOL:
        raise RuntimeError("%s.arch: not the old arch %.0f mm wider (heights off %.4f m, sides moved %.4f-%.4f m)"
                           % (nm, W.REVEAL * 1000, dz, float(dxy.min()), float(dxy.max())))
    return "old", "old arch, sides %.3f m in" % float(dxy.max())


def guard_piers(nm, old_me, new_me):
    """Piers and footings: 'new' when equal; 'old' when only the footings' end faces moved, REVEAL along the stair."""
    ok, why = same_mesh(old_me, new_me)
    if ok:
        return "new", why
    co, cn = coords(old_me), coords(new_me)
    if co.shape != cn.shape:
        raise RuntimeError("%s.piers: %d vertices, rebuilt %d" % (nm, len(co), len(cn)))
    d = cn - co
    moved = np.linalg.norm(d, axis=1) > 1e-6
    dxy = np.linalg.norm(d[moved, :2], axis=1)
    if moved.sum() % 4 or np.abs(d[moved, 2]).max(initial=0.0) > 1e-4 or             (len(dxy) and (dxy.min() < W.REVEAL - TOL or dxy.max() > W.REVEAL + TOL)):
        raise RuntimeError("%s.piers: more changed than the footings' end faces (%d vertices moved)" % (nm, moved.sum()))
    return "old", "old piers; %d footing end faces moved %.3f m in" % (int(moved.sum()) // 4, W.REVEAL)


def guard_box_piece(nm, part, old_me, new_me, n_old, top_old):
    """Landings and walls: 'new' when equal; 'old' when the old piece has the old recipe's vertex count and top."""
    ok, why = same_mesh(old_me, new_me)
    if ok:
        return "new", why
    co = coords(old_me)
    if len(co) != n_old:
        raise RuntimeError("%s.%s: %d vertices, the old recipe has %d" % (nm, part, len(co), n_old))
    if abs(float(co[:, 2].max()) - top_old) > TOL:
        raise RuntimeError("%s.%s: top at %.4f, the old recipe's at %.4f" % (nm, part, float(co[:, 2].max()), top_old))
    return "old", "old recipe (%d vertices, top %.3f)" % (n_old, top_old)


def steles_box(ST, y0):
    """The 8 corners areas/steles.py's _arrival -> _boxes builds for the forecourt, with its outer edge at y0."""
    x0, x1, y1, z0, z1 = -ST.FORE_X, ST.FORE_X, ST.COURT_Y0, -0.8, ST.OUT_TOP
    return np.array([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                     (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], float)


def guard_steles(ST):
    """(object, 'new' | 'old'): steles.arrival is the forecourt box from FORE_Y0 (now the arrival line) or from
    STELES_Y0_OLD (1 m further out, the old source). Anything else raises."""
    if abs(ST.FORE_Y0 - ST.AREA["arrival"][1]) > 1e-9:
        raise RuntimeError("areas/steles.py: FORE_Y0 %.3f is not the arrival line %.3f" % (ST.FORE_Y0, ST.AREA["arrival"][1]))
    ob = bpy.data.objects.get(STELES_SLAB)
    if ob is None or ob.type != "MESH" or len(ob.data.polygons) != 6 or ob.data.users != 1:
        raise RuntimeError("%s: not a one-user 6-face mesh" % STELES_SLAB)
    co = coords(ob.data)
    for state, y0 in (("new", ST.FORE_Y0), ("old", STELES_Y0_OLD)):
        if co.shape == (8, 3) and float(np.abs(co - steles_box(ST, y0)).max()) <= TOL:
            return ob, state
    raise RuntimeError("%s is neither areas/steles.py's forecourt box nor the old one: %s"
                       % (STELES_SLAB, np.round(co, 3).tolist()))


def steles_strip_standing(ob, ST):
    """Rendered pieces (instances too, but no link's and not the slab) with a down-facing face resting on the slab
    top (within 3 cm) over the strip the trim removes (|x| <= FORE_X, STELES_Y0_OLD..FORE_Y0): they would float."""
    M = ob.matrix_world
    strip = [M @ Vector((x, y, ST.OUT_TOP)) for x in (-ST.FORE_X, ST.FORE_X) for y in (STELES_Y0_OLD, ST.FORE_Y0)]
    lo = np.min([tuple(v) for v in strip], axis=0) - 0.05
    hi = np.max([tuple(v) for v in strip], axis=0) + 0.05
    Mi = M.inverted()
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for inst in dg.object_instances:
        o = inst.object
        base = inst.parent.original if (inst.is_instance and inst.parent is not None) else o.original
        if o.type != "MESH" or base.hide_render or base.name.startswith(("world.link.", "world.range", STELES_SLAB)):
            continue
        Mw = np.array(inst.matrix_world)
        bb = np.array([tuple(c) for c in o.bound_box]) @ Mw[:3, :3].T + Mw[:3, 3]
        if np.any(bb.max(0)[:2] < lo[:2]) or np.any(bb.min(0)[:2] > hi[:2]) or bb.min(0)[2] > hi[2] + 0.03 \
                or bb.max(0)[2] < lo[2] - 0.03:
            continue
        # the evaluated local mesh, placed by the instance's own matrix (instances share their prototype's object)
        me = o.to_mesh()
        try:
            if me is None or not len(me.polygons):
                continue
            me.calc_loop_triangles()
            cl = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", cl)
            tl = np.empty(len(me.loop_triangles) * 3, np.int32)
            me.loop_triangles.foreach_get("vertices", tl)
        finally:
            o.to_mesh_clear()
        v, t = cl.reshape(-1, 3) @ Mw[:3, :3].T + Mw[:3, 3], tl.reshape(-1, 3)
        P = v[t]
        n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        down = n[:, 2] < -0.5 * np.linalg.norm(n, axis=1)
        for tri in P[down]:
            c = tri.mean(0)
            loc = Mi @ Vector(c)
            if -ST.FORE_X <= loc.x <= ST.FORE_X and STELES_Y0_OLD <= loc.y <= ST.FORE_Y0 - 0.01 \
                    and abs(loc.z - ST.OUT_TOP) <= 0.03:
                out.append(base.name if not inst.is_instance else "%s>%s" % (base.name, o.original.name))
                break
    return sorted(set(out))


# ---- coplanar overlap scan ----------------------------------------------------------------------------------------

def _eval_tris(ob_eval, lo, hi):
    """World-space triangles of an evaluated mesh object whose box overlaps [lo, hi]: (verts (n, 3), tris (m, 3))."""
    me = ob_eval.to_mesh()
    try:
        if me is None or not len(me.polygons):
            return None
        me.calc_loop_triangles()
        nv, nt = len(me.vertices), len(me.loop_triangles)
        co = np.empty(nv * 3)
        me.vertices.foreach_get("co", co)
        M = np.array(ob_eval.matrix_world)
        co = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
        tv = np.empty(nt * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", tv)
        tv = tv.reshape(-1, 3)
    finally:
        ob_eval.to_mesh_clear()
    p = co[tv]
    keep = np.all(p.max(1) >= lo, axis=1) & np.all(p.min(1) <= hi, axis=1)
    if not keep.any():
        return None
    tv = tv[keep]
    used, inv = np.unique(tv, return_inverse=True)
    return co[used], inv.reshape(-1, 3)


class Scene3:
    """Every mesh near a link (non-instanced, rendered) as one BVH, with a triangle -> object map."""

    def __init__(self, lo, hi):
        dg = bpy.context.evaluated_depsgraph_get()
        verts, polys, owner, names = [], [], [], []
        base = 0
        for ob in bpy.context.scene.objects:
            if ob.type != "MESH" or ob.hide_render or ob.name.startswith(SKIP_SCAN):
                continue
            ev = ob.evaluated_get(dg)
            M = np.array(ev.matrix_world)
            bb = np.array([tuple(c) for c in ev.bound_box]) @ M[:3, :3].T + M[:3, 3]
            if np.any(bb.max(0) < lo) or np.any(bb.min(0) > hi):
                continue
            got = _eval_tris(ev, lo, hi)
            if got is None:
                continue
            v, t = got
            verts.append(v)
            polys.append(t + base)
            owner.append(np.full(len(t), len(names), np.int32))
            names.append(ob.name)
            base += len(v)
        self.names = names
        self.v = np.vstack(verts)
        self.t = np.vstack(polys)
        self.owner = np.concatenate(owner)
        self.bvh = BVHTree.FromPolygons(self.v.tolist(), self.t.tolist(), all_triangles=True, epsilon=0.0)
        e1 = self.v[self.t[:, 1]] - self.v[self.t[:, 0]]
        e2 = self.v[self.t[:, 2]] - self.v[self.t[:, 0]]
        cr = np.cross(e1, e2)
        self.area = 0.5 * np.linalg.norm(cr, axis=1)
        self.n = cr / np.maximum(2.0 * self.area[:, None], 1e-12)

    def obj(self, i):
        return self.names[self.owner[i]]


_DIRS = None


def _inside(S, p, n):
    """True when p (1 cm off a face, along its normal) is inside a closed solid: at least 12 of 14 rays (the axes and
    the cube diagonals) leave it first, through a back face. Where two solids touch face to face a front and a back
    face lie in one place and the BVH returns either, so a hit counts as leaving when any face at that spot faces
    along the ray."""
    global _DIRS
    if _DIRS is None:
        d = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
        d += [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
        _DIRS = [np.array(v, float) / np.linalg.norm(v) for v in d]

    def leaves(d):
        loc, nrm, i, dist = S.bvh.ray_cast(Vector(p), Vector(d), 1e4)
        if loc is None:
            return False
        if float(np.dot(S.n[i], d)) > 0.0:
            return True
        return any(float(np.dot(S.n[j], d)) > 0.0 and abs(float(np.dot(S.n[j], S.n[i]))) > 0.9
                   for _l, _n, j, _d in S.bvh.find_nearest_range(loc, 2e-4))
    # straight up and straight down both leaving through a back face: inside (the range is a closed heightfield
    # solid, but its slopes take the slanted rays out of the scan's crop)
    if leaves(_DIRS[4]) and leaves(_DIRS[5]):
        return True
    back = 0
    for k, d in enumerate(_DIRS):
        if leaves(d):
            back += 1
        if back + (len(_DIRS) - 1 - k) < 12:
            return False
    return back >= 12


def scan(S, sources, seed=7):
    """Overlap area (m2) of the source objects' faces: dict per source part -> {'visible': {partner: m2}, 'hidden':
    m2, 'touch': m2}, plus the visible sample points."""
    rng = np.random.default_rng(seed)
    src = [i for i in range(len(S.names)) if S.names[i] in sources]
    out = {}
    pts_vis = []
    for oi in src:
        nm = S.names[oi]
        part = nm.split(".", 3)[-1] if nm.startswith("world.link.") else nm
        rec = out.setdefault(part, dict(visible={}, hidden=0.0, touch=0.0, area=0.0))
        tri = np.nonzero(S.owner == oi)[0]
        A = S.area[tri]
        rec["area"] += float(A.sum())
        k = np.maximum(1, np.round(A / SAMPLE_M2)).astype(int)
        for ti, kk, a in zip(tri, k, A):
            if a < 1e-6:
                continue
            P = S.v[S.t[ti]]
            n = S.n[ti]
            r1, r2 = rng.random(kk), rng.random(kk)
            f = r1 + r2 > 1.0
            r1[f], r2[f] = 1.0 - r1[f], 1.0 - r2[f]
            c = P.mean(0)
            q = P[0] + np.outer(r1, P[1] - P[0]) + np.outer(r2, P[2] - P[0])
            q = c + 0.98 * (q - c)
            w = a / kk
            for p in q:
                best = None
                for loc, nrm, j, dist in S.bvh.find_nearest_range(Vector(p), OVERLAP_D + 1e-4):
                    if j == ti or j is None:
                        continue
                    dot = float(np.dot(S.n[j], n))
                    if abs(dot) < 0.98:
                        continue
                    dv = np.array(loc) - p
                    dn = float(dv @ n)
                    # (3e-4 m in the plane: the BVH stores float32, 1.2e-4 m apart at 1-2 km. More than that and a
                    # coplanar neighbour (the quad's other half, the next tread top on a landing) counts for every
                    # sample near the shared edge)
                    if abs(dn) > OVERLAP_D or np.linalg.norm(dv - dn * n) > 3e-4:
                        continue
                    if best is None or dot > best[0]:
                        best = (dot, j)
                if best is None:
                    continue
                if best[0] < 0.0:
                    rec["touch"] += w
                elif _inside(S, p + 0.01 * n, n):
                    rec["hidden"] += w
                else:
                    partner = S.obj(best[1])
                    rec["visible"][partner] = rec["visible"].get(partner, 0.0) + w
                    pts_vis.append((nm, partner, p, ti, best[1]))
    return out, pts_vis


def scan_summary(res):
    vis = sum(sum(r["visible"].values()) for r in res.values())
    hid = sum(r["hidden"] for r in res.values())
    tch = sum(r["touch"] for r in res.values())
    pairs = sorted(((part, partner, a) for part, r in res.items() for partner, a in r["visible"].items()),
                   key=lambda x: -x[2])
    return vis, hid, tch, pairs


def clusters(pts, cell=3.0):
    """Visible overlap samples grouped on a 3 m grid: [(source, partner, centre, samples)], biggest first."""
    g = {}
    first = {}
    for nm, partner, p, ti, tj in pts:
        k = (nm, partner, int(p[0] // cell), int(p[1] // cell), int(p[2] // cell))
        g.setdefault(k, []).append(p)
        first.setdefault(k, (ti, tj))
    rows = [(k[0], k[1], np.round(np.mean(v, axis=0), 1).tolist(), len(v), first[k]) for k, v in g.items()]
    return sorted(rows, key=lambda r: -r[3])


# ---- walk checks --------------------------------------------------------------------------------------------------

def down(S, x, y, z, reach=3.0):
    loc, nrm, i, d = S.bvh.ray_cast(Vector((x, y, z)), Vector((0.0, 0.0, -1.0)), reach)
    return (None, None) if loc is None else (float(loc[2]), S.obj(i))


def up_clear(S, x, y, z, reach=2.0):
    loc, nrm, i, d = S.bvh.ray_cast(Vector((x, y, z)), Vector((0.0, 0.0, 1.0)), reach)
    return loc is None, (None if loc is None else S.obj(i))


def walk_check(S, nm, geo, z0, z1, foot, rest_span, side, ends_before=None):
    """Fails (list of strings) and stats for one stairway's walking surface."""
    fails, st = [], {}
    s, xy, yaw, plan = geo["s"], geo["xy"], geo["yaw"], geo["plan"]
    L = float(s[-1])
    sr = plan["sr"]
    q = np.arange(0.05, L - 0.05 + 1e-9, 0.1)
    bad_q = np.zeros(len(q), bool)
    for x in list(sr) + ([foot] if foot else []):
        bad_q |= np.abs(q - x) < 0.03
    q = q[~bad_q]
    c, nl, _ = W._frame(s, xy, yaw, q)
    exp = np.where(q <= foot, z0, W._level_at(plan, q)) if foot else W._level_at(plan, q)
    worst_off, worst_rise, misses, low_head, wrong, off = 0.0, 0.0, 0, [], [], []
    for lat in (-2.0, 0.0, 2.0):
        zs = []
        for k in range(len(q)):
            x, y = c[k] + nl[k] * lat
            z, ob = down(S, float(x), float(y), float(exp[k]) + 1.0)
            if z is None:
                misses += 1
                zs.append(np.nan)
                continue
            if not ob.startswith(nm + "."):
                wrong.append((round(float(q[k]), 2), lat, ob, round(z - float(exp[k]), 4)))
            elif abs(z - float(exp[k])) > 0.002:
                off.append((round(float(q[k]), 2), lat, ob, round(z - float(exp[k]), 4)))
            worst_off = max(worst_off, abs(z - float(exp[k])))
            zs.append(z)
            ok, what = up_clear(S, float(x), float(y), z + 0.02)
            if not ok and len(low_head) < 5:
                low_head.append((round(float(q[k]), 1), lat, what))
        zs = np.array(zs)
        d = np.abs(np.diff(zs[~np.isnan(zs)]))
        worst_rise = max(worst_rise, float(d.max()) if len(d) else 0.0)
    st.update(samples=int(3 * len(q)), worst_level_off=round(worst_off, 4), worst_riser=round(worst_rise, 3),
              misses=misses, other_floor=wrong[:6], n_other_floor=len(wrong), off_level=off[:6], n_off_level=len(off),
              low_headroom=low_head)
    if misses:
        fails.append("%s: %d walk samples hit nothing" % (nm, misses))
    if off:
        fails.append("%s: %d walk samples off the plan's level, e.g. %s" % (nm, len(off), off[:3]))
    if worst_rise > W.RISER + 0.002:
        fails.append("%s: a %.3f m step on the walk" % (nm, worst_rise))
    if low_head:
        fails.append("%s: something within 2 m over the walk at %s" % (nm, low_head))
    # both ends: the floor just past them (the area's), as it was before the patch
    h0 = np.array([math.cos(float(yaw[0])), math.sin(float(yaw[0]))])
    h1 = np.array([math.cos(float(yaw[-1])), math.sin(float(yaw[-1]))])
    ends = []
    for p, z in ((xy[0] - h0 * 0.3, z0), (xy[-1] + h1 * 0.3, z1)):
        zz, ob = down(S, float(p[0]), float(p[1]), z + 1.0)
        ends.append((None if zz is None else round(zz - z, 3), ob))
    st["ends"] = ends
    if ends_before is not None:
        st["ends_before"] = ends_before
        for (a, oa), (b, ob_) in zip(ends_before, ends):
            # (the range past a stair's end may dip a little: a triangle with a sunk corner inside the stair)
            dip_ok = oa == ob_ == "world.range" and a is not None and b is not None and -W.SINK - 1e-3 <= b - a <= 0.0
            if ((a is None) != (b is None) or (a is not None and abs(a - b) > 0.002)) and not dip_ok:
                fails.append("%s: the floor past an end changed: %s -> %s" % (nm, (a, oa), (b, ob_)))
    # rest landing: one floor at its level from the stair's centre out across the opening, closed beside it
    if rest_span:
        k = plan["rest_k"]
        zl = float(plan["lev"][k + 1])
        worst = 0.0
        # (two stations 0.6 m inside the opening's ends: clear of the pavilion's front steps on its axis)
        for qq in (rest_span[0] + 0.6, rest_span[1] - 0.6):
            cm, nm_, _ = W._frame(s, xy, yaw, [qq])
            for lat in np.arange(0.0, 3.2, 0.05):
                x, y = cm[0] + nm_[0] * side * lat
                z, ob = down(S, float(x), float(y), zl + 1.0)
                if z is None or abs(z - zl) > 0.002:
                    fails.append("%s: rest landing floor broken at station %.1f, %.2f m out (%s, %s)"
                                 % (nm, qq, lat, z, ob))
                    break
                worst = max(worst, abs(z - zl))
        closed = 0
        # the parapet stops at the slab's ends (rest_span -/+ 0.5): 0.25 m before them it stands, and 0.2 m past them
        # the end walls do, 3.2 m out
        for qq, lat_, what in ((rest_span[0] - 0.75, 2.7, ".rails"), (rest_span[1] + 0.75, 2.7, ".rails"),
                               (rest_span[0] - 0.3, 3.2, ".rest_rail"), (rest_span[1] + 0.3, 3.2, ".rest_rail")):
            cc, nn, _ = W._frame(s, xy, yaw, [qq])
            x, y = cc[0] + nn[0] * side * lat_
            z, ob = down(S, float(x), float(y), zl + 3.0)
            if z is not None and z > zl + 0.5 and ob == nm + what:
                closed += 1
            else:
                fails.append("%s: no %s beside the rest landing at station %.2f (%s, %s)" % (nm, what, qq, z, ob))
        st["rest"] = dict(level=round(zl, 3), worst_off=round(worst, 4), parapet_ends=closed)
    # foot landing: one floor across, 1 m in (in front of the archway's plinths)
    if foot:
        cf, nf, _ = W._frame(s, xy, yaw, [1.0])
        for lat in np.arange(-4.0, 4.01, 0.1):
            x, y = cf[0] + nf[0] * lat
            z, ob = down(S, float(x), float(y), z0 + 1.0)
            if z is None or abs(z - z0) > 0.002 or not ob.endswith(".foot_landing"):
                fails.append("%s: foot landing floor broken at %.1f m across (%s, %s)" % (nm, lat, z, ob))
                break
    return fails, st


def parapet_check(S, nm, geo, z0, z1, foot, rest_span, side):
    """Rays down every 0.25 m along both parapets, 2.7 m out (the middle of the coping, which falls COPING m over
    RAIL_W): each lands on the parapet RAIL_H - COPING / 2 over the nosing line, except over the rest landing's
    opening. Returns (fails, worst deviation, samples)."""
    s, xy, yaw, plan = geo["s"], geo["xy"], geo["yaw"], geo["plan"]
    L = float(s[-1])
    lm = 0.5 * (W.STAIR_W * 0.5 + W.STAIR_W * 0.5 + W.RAIL_W)
    q = np.arange((foot or 0.0) + 0.1, L - 0.1, 0.25)
    c, nl, _ = W._frame(s, xy, yaw, q)
    # the solid's own stations (world._stairway): its top is straight between them, so it cuts the nosing line's
    # corners where a flight meets a landing (up to 0.11 m at 0.8 m apart; the boxes, 1.6 m apart, cut 0.23 m)
    rest_open = (rest_span[0] - 0.5, rest_span[1] + 0.5) if rest_span else None
    keys = np.array([L] + ([foot] if foot else []) + (list(rest_open) if rest_open else []))
    st = np.unique(np.concatenate([s[np.abs(s[:, None] - keys[None, :]).min(axis=1) > 0.2], keys]))
    want = np.interp(q, st, W._nosing(plan, s, z0, z1, st)) + W.RAIL_H - 0.5 * W.COPING
    worst, n, gaps = 0.0, 0, []
    for sd in (-1.0, 1.0):
        for k in range(len(q)):
            if rest_open and sd == side and rest_open[0] - 0.05 < q[k] < rest_open[1] + 0.05:
                continue
            x, y = c[k] + nl[k] * sd * lm
            z, ob = down(S, float(x), float(y), float(want[k]) + 1.0, reach=2.0)
            n += 1
            if z is None or ob != nm + ".rails" or abs(z - float(want[k])) > 0.01:
                if len(gaps) < 5:
                    gaps.append((round(float(q[k]), 2), sd, ob, None if z is None else round(z - float(want[k]), 3)))
                continue
            worst = max(worst, abs(z - float(want[k])))
    fails = ["%s: parapet missing or off height at %s" % (nm, gaps)] if gaps else []
    return fails, worst, n


def rest_gaps(rng_obj, co0, co1, moved):
    """[(object, gap)]: every rendered mesh (not a link's, not the range) with a down-facing face that sat on the range
    (within 3 cm over it, or in it) where the range moved, and the largest gap that opened under it (m)."""
    me = rng_obj.data
    me.calc_loop_triangles()
    tv = np.empty(len(me.loop_triangles) * 3, np.int32)
    me.loop_triangles.foreach_get("vertices", tv)
    tv = tv.reshape(-1, 3)
    mv = co0[moved]
    lo, hi = mv.min(0) - 3.0, mv.max(0) + 3.0
    lo[2], hi[2] = mv[:, 2].min() - 1.0, mv[:, 2].max() + 1.0
    p0 = co0[tv]
    keep = np.all(p0.max(1) >= lo, axis=1) & np.all(p0.min(1) <= hi, axis=1)
    tk = tv[keep]
    bvh0 = BVHTree.FromPolygons(co0.tolist(), tk.tolist(), all_triangles=True)
    bvh1 = BVHTree.FromPolygons(co1.tolist(), tk.tolist(), all_triangles=True)
    dg = bpy.context.evaluated_depsgraph_get()
    rng = np.random.default_rng(3)
    out = []
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH" or ob.hide_render or ob.name.startswith(("world.link.", "world.range")) \
                or ob.name.startswith(SKIP_SCAN):
            continue
        ev = ob.evaluated_get(dg)
        M = np.array(ev.matrix_world)
        bb = np.array([tuple(c) for c in ev.bound_box]) @ M[:3, :3].T + M[:3, 3]
        if np.any(bb.max(0) < lo) or np.any(bb.min(0) > hi):
            continue
        got = _eval_tris(ev, lo, hi)
        if got is None:
            continue
        v, t = got
        P = v[t]
        nrm = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        ar = 0.5 * np.linalg.norm(nrm, axis=1)
        down_ = (nrm[:, 2] < -0.5 * np.linalg.norm(nrm, axis=1)) & (ar > 1e-6)
        worst, hit = 0.0, False
        for tri, a in zip(P[down_], ar[down_]):
            k = int(min(64, max(3, round(a / 0.02))))
            r1, r2 = rng.random(k), rng.random(k)
            f = r1 + r2 > 1.0
            r1[f], r2[f] = 1.0 - r1[f], 1.0 - r2[f]
            pts = tri[0] + np.outer(r1, tri[1] - tri[0]) + np.outer(r2, tri[2] - tri[0])
            for q in pts:
                o = Vector((q[0], q[1], q[2] + 0.05))
                l0 = bvh0.ray_cast(o, Vector((0.0, 0.0, -1.0)), 0.3)[0]
                if l0 is None or q[2] - l0[2] > 0.03:
                    continue                                   # it did not sit on the range here
                l1 = bvh1.ray_cast(o, Vector((0.0, 0.0, -1.0)), 0.5)[0]
                if l1 is None:
                    continue
                hit = True
                # the new gap: from the face (or the old ground, where the face was sunk into it) down to the new one
                worst = max(worst, float(min(q[2], l0[2]) - l1[2]))
        if hit and worst > 1e-4:
            out.append((ob.name, round(worst, 3)))
    return sorted(out, key=lambda x: -x[1])


# ---- main ---------------------------------------------------------------------------------------------------------

def main():
    t_start = time.time()
    dry, debug = options()
    fails = []
    root = bpy.data.objects.get("world.root")
    rng_obj = bpy.data.objects.get("world.range")
    if root is None or "links" not in root or rng_obj is None or bpy.data.collections.get("world.links") is None:
        raise SystemExit("patch_r11_links: no world.root['links'] / world.range / world.links; is this out/sect_chase.blend?")
    if not np.allclose(np.array(rng_obj.matrix_world), np.eye(4)):
        raise SystemExit("patch_r11_links: world.range has a transform")
    g = range_grid(rng_obj)
    if abs(g - W.GRID) > 1e-6:
        raise SystemExit("patch_r11_links: world.range is on a %g m grid, world.GRID is %g (run patch_r2_range first)"
                         % (g, W.GRID))
    n_obj0 = len(bpy.data.objects)
    rng_ = W.Range(W._norm_anchors(None), W._anchor_yaws(None))
    reports = json.loads(root["links"])
    by_link = {r["link"]: r for r in reports}
    tmp = bpy.data.collections.new("patch_r11_links.tmp")       # not in the scene: built, compared, swapped, dropped
    plans, made = [], []
    boxes_old = {}
    try:
        # ---- 1. rebuild every stairway from the same plan, guard that it is the scene's
        for seg in rng_.segs:
            if not seg["mass"]:
                continue
            ka, kb = seg["ka"], seg["kb"]
            nm = "world.link.%s_%s" % (ka, kb)
            key = "%s-%s" % (ka, kb)
            pa, pb = W.port(rng_, ka, "depart"), W.port(rng_, kb, "arrival")
            old = by_link.get(key)
            if old is None or pa is None or pb is None:
                raise RuntimeError("%s: no report or no ports" % nm)
            for end, p in (("depart", pa), ("arrival", pb)):
                off = float(np.abs(np.asarray(old[end]["world"], float) - p["p"]).max())
                if off > PORT_TOL:
                    raise RuntimeError("%s %s moved %.3f m since the build" % (nm, end, off))
            objs, rep, geo = W._stairway(rng_, tmp, seg, nm, pa, pb, arch_extras=False)
            new = {o.name[len(nm) + 1:].split(".")[0]: o for o in objs}
            P = W._plan_stairway(rng_, seg, pa, pb)
            foot = P["foot"] if P["gate"] else 0.0
            plan = geo["plan"]
            side = 1.0 if P["info"]["meander"] >= 0.0 else -1.0
            rest_span = None
            if plan["rest_k"] is not None:
                k = plan["rest_k"]
                mid = 0.5 * (plan["sr"][k] + plan["sr"][k + 1])
                rest_span = (mid - W.REST_LANDING * 0.5 + 0.5, mid + W.REST_LANDING * 0.5 - 0.5)
            z0, z1 = float(pa["p"][2]), float(pb["p"][2])
            states = {}
            for part in REPLACE + SAME:
                o_old, o_new = bpy.data.objects.get(nm + "." + part), new.get(part)
                if (o_old is None) != (o_new is None):
                    raise RuntimeError("%s.%s: in the scene %s, rebuilt %s" % (nm, part, o_old is not None,
                                                                             o_new is not None))
                if o_old is None:
                    continue
                if part == "stairs":
                    states[part] = guard_stairs(nm, o_old.data, o_new.data, geo, foot)
                elif part == "rails":
                    opening = (rest_span[0] - 0.5, rest_span[1] + 0.5, side) if rest_span else None
                    keys = [float(geo["s"][-1])] + ([foot] if foot else []) + (list(opening[:2]) if opening else [])
                    states[part] = guard_rails(nm, o_old.data, o_new.data, geo, keys, opening)
                elif part == "arch":
                    states[part] = guard_arch(nm, o_old.data, o_new.data)
                elif part == "piers":
                    states[part] = guard_piers(nm, o_old.data, o_new.data)
                elif part in SAME:
                    ok, why = same_mesh(o_old.data, o_new.data)
                    if not ok:
                        raise RuntimeError("%s.%s does not match the rebuilt plan: %s" % (nm, part, why))
                    states[part] = ("same", why)
                elif part == "foot_landing":
                    states[part] = guard_box_piece(nm, part, o_old.data, o_new.data, 8, z0 - 0.004)
                elif part == "foot_rail":
                    states[part] = guard_box_piece(nm, part, o_old.data, o_new.data, 32, z0 + W.RAIL_H)
                elif part == "rest_landing":
                    zl = float(plan["lev"][plan["rest_k"] + 1])
                    states[part] = guard_box_piece(nm, part, o_old.data, o_new.data, 8, zl - 0.004)
                elif part == "rest_rail":
                    zl = float(plan["lev"][plan["rest_k"] + 1])
                    states[part] = guard_box_piece(nm, part, o_old.data, o_new.data, 24, zl + W.RAIL_H)
                if part in REPLACE:
                    boxes_old[nm + "." + part] = world_box(o_old)
            log("LINK", key, "guards:", json.dumps({k: v[0] + ": " + v[1] for k, v in states.items()}))
            plans.append(dict(nm=nm, key=key, new=new, rep=rep, geo=geo, foot=foot, z0=z0, z1=z1,
                              rest_span=rest_span, side=side, states=states))
            made.append((nm, rep["kind"], objs, rep, geo))
        if len(plans) != sum(1 for s in rng_.segs if s["mass"]):
            raise RuntimeError("only %d stairways rebuilt" % len(plans))
        # the steles forecourt (areas/steles.py FORE_Y0): it ran 1 m past the arrival line, under the library ->
        # steles stair's last tread, in its plane (5 m2: the dark band at that stair's top); now it starts there
        from sect.areas import steles as ST
        st_ob, st_state = guard_steles(ST)
        log("STELES %s: %s (outer edge at local y %.1f, the arrival line %.1f)"
            % (STELES_SLAB, st_state, ST.FORE_Y0 if st_state == "new" else STELES_Y0_OLD, ST.AREA["arrival"][1]))
        if st_state == "old":
            boxes_old[STELES_SLAB] = world_box(st_ob)

        # ---- 2. the scan before, per link
        link_lo, link_hi = {}, {}
        for p in plans:
            bb = [world_box(bpy.data.objects[p["nm"] + "." + part]) for part in REPLACE + SAME
                  if bpy.data.objects.get(p["nm"] + "." + part) is not None]
            link_lo[p["nm"]] = np.min([b[0] for b in bb], axis=0) - 1.0
            link_hi[p["nm"]] = np.max([b[1] for b in bb], axis=0) + 1.0

        def scan_all(tag):
            res = {}
            for p in plans:
                t0 = time.time()
                # (cropped in plan only, 5 m round the link: the range keeps its underside under the stair, so the
                # inside test sees it closed)
                pad = np.array([5.0, 5.0, 1e5])
                S = Scene3(link_lo[p["nm"]] - pad, link_hi[p["nm"]] + pad)
                srcs = {p["nm"] + "." + part for part in REPLACE + SAME}
                r, pts = scan(S, srcs)
                vis, hid, tch, pairs = scan_summary(r)
                res[p["nm"]] = dict(visible=vis, hidden=hid, touch=tch, pairs=pairs, clusters=clusters(pts), S=S)
                log("SCAN %s %s: visible same-facing overlap %.2f m2, hidden %.2f m2, touching %.2f m2 (%d objects, %d tris,"
                    " %.0f s)" % (tag, p["key"], vis, hid, tch, len(S.names), len(S.t), time.time() - t0))
                for part, partner, a in pairs[:8]:
                    log("    %s %s ~ %s: %.2f m2" % (tag, part, partner, a))
                for row in clusters(pts)[:6]:
                    log("    %s cluster %s ~ %s at %s: %d samples" % (tag, row[0].split(".", 3)[-1], row[1], row[2],
                                                                      row[3]))
                    if debug:
                        ti, tj = row[4]
                        log("      DEBUG source tri n %s v %s | partner tri n %s v %s"
                            % (np.round(S.n[ti], 3).tolist(), np.round(S.v[S.t[ti]], 3).tolist(),
                               np.round(S.n[tj], 3).tolist(), np.round(S.v[S.t[tj]], 3).tolist()))
            return res

        before = scan_all("before")
        ends_before = {}
        for p in plans:
            _f, st_ = walk_check(before[p["nm"]]["S"], p["nm"], p["geo"], p["z0"], p["z1"], 0.0, None, p["side"])
            ends_before[p["nm"]] = st_["ends"]

        # ---- 3. replace, flat-shade, sink the range
        tri0 = tri1 = 0
        for p in plans:
            nm = p["nm"]
            for part in REPLACE:
                o_old, o_new = bpy.data.objects.get(nm + "." + part), p["new"].get(part)
                if o_old is None:
                    continue
                slots0 = [s.material.name if s.material else None for s in o_old.material_slots]
                t0_, t1_ = tris(o_old.data), tris(o_new.data)
                tri0, tri1 = tri0 + t0_, tri1 + t1_
                swap(o_old, o_new)
                slots1 = [s.material.name if s.material else None for s in o_old.material_slots]
                if slots0 != slots1:
                    raise RuntimeError("%s: material slots %s -> %s" % (o_old.name, slots0, slots1))
                log("replaced", o_old.name, "tris %d -> %d" % (t0_, t1_), "(%s)" % p["states"][part][0])
        flat = 0
        for ob in bpy.data.collections["world.links"].all_objects:
            if ob.type != "MESH" or not ob.name.startswith("world.link."):
                continue
            part = ob.name.split(".", 3)[-1]
            if part in FLAT_ONLY:
                st0 = smooth_state(ob.data)
                if st0 == "mixed":
                    raise RuntimeError("%s has mixed shading; expected all smooth (old) or all flat (new)" % ob.name)
                if ob.data.users != 1:
                    raise RuntimeError("%s's mesh has %d users" % (ob.name, ob.data.users))
                if st0 == "smooth":
                    ob.data.polygons.foreach_set("use_smooth", np.zeros(len(ob.data.polygons), bool))
                    ob.data.update()
                    flat += 1
        log("flat-shaded", flat, "link meshes (piers, arch, rest piers, chain bridge deck/boards/posts) that shaded as "
            "pillows; vertices untouched")
        if st_state == "old":
            floating = steles_strip_standing(st_ob, ST)
            if floating:
                raise RuntimeError("%s: trimming it would leave %s floating" % (STELES_SLAB, floating))
            st_ob.data.vertices.foreach_set("co", steles_box(ST, ST.FORE_Y0).astype(np.float32).ravel())
            st_ob.data.update()
            log("STELES %s trimmed to start at the arrival line (y %.1f -> %.1f local); nothing stood on the strip"
                % (STELES_SLAB, STELES_Y0_OLD, ST.FORE_Y0))
        co0 = coords(rng_obj.data)
        sunk = W.sink_under_links(rng_, rng_obj, made)
        co1 = coords(rng_obj.data)
        dz = co1[:, 2] - co0[:, 2]
        moved = np.nonzero(np.abs(dz) > 1e-6)[0]
        log("RANGE sink_under_links", json.dumps(sunk), "| vertices moved now %d, lowest %.4f m, highest %+.4f m"
            % (len(moved), float(dz.min()) if len(dz) else 0.0, float(dz.max()) if len(dz) else 0.0))
        if len(moved) and (dz.max() > 1e-6 or dz.min() < -(W.SINK + W.SINK_UP + 0.001)):
            fails.append("the range moved up, or down by more than SINK + SINK_UP")

        # ---- 4. checks
        bpy.context.view_layer.update()            # the scan reads evaluated meshes: the range was edited in place
        after = scan_all("after")
        tot_b = sum(v["visible"] for v in before.values())
        tot_a = sum(v["visible"] for v in after.values())
        area_left = []
        for p in plans:
            b, a = before[p["nm"]], after[p["nm"]]
            # what this patch rebuilt (the link's pieces but the corbelled piers, and the range) against itself
            mine = lambda part, partner: part != "piers" and partner.startswith("world.") and                 not partner.endswith(".piers")
            own = sum(x for part, partner, x in a["pairs"] if mine(part, partner))
            rest_ = sum(x for part, partner, x in a["pairs"] if partner.startswith("world.") and not mine(part, partner))
            log("OVERLAP %s visible %.2f -> %.2f m2 (rebuilt pieces and the range %.2f m2, with the piers' corbels %.2f "
                "m2), hidden %.2f -> %.2f m2, touching %.2f -> %.2f m2" % (p["key"], b["visible"], a["visible"], own,
                                                                         rest_, b["hidden"], a["hidden"], b["touch"],
                                                                         a["touch"]))
            area_left += [(p["key"], part, partner, round(x, 2)) for part, partner, x in a["pairs"]
                          if not partner.startswith("world.")]
            if own > VISIBLE_MAX_LINK:
                fails.append("%s: %.2f m2 of visible coplanar overlap left among the rebuilt pieces and the range (%s)"
                             % (p["key"], own, [x for x in a["pairs"] if mine(x[0], x[1])][:4]))
        log("OVERLAP all stairways: visible same-facing within %.0f mm %.2f -> %.2f m2" % (OVERLAP_D * 1000, tot_b, tot_a))
        log("OVERLAP left with the areas' own pieces (their files, not this patch):", area_left if area_left else "none")
        if any(x[2] == STELES_SLAB for x in area_left):
            fails.append("%s still overlaps a stair: %s" % (STELES_SLAB, [x for x in area_left if x[2] == STELES_SLAB]))
        for p in plans:
            S = after[p["nm"]]["S"]
            f, st = walk_check(S, p["nm"], p["geo"], p["z0"], p["z1"], p["foot"], p["rest_span"], p["side"],
                               ends_before=ends_before[p["nm"]])
            f2, dev, npar = parapet_check(S, p["nm"], p["geo"], p["z0"], p["z1"], p["foot"], p["rest_span"], p["side"])
            f += f2
            st["parapet"] = dict(samples=npar, worst_off=round(dev, 4))
            me = bpy.data.objects[p["nm"] + ".rails"].data
            st["rails_shading"] = smooth_state(me)
            st["rails_sharp_edges"] = sharp_count(me)
            if st["rails_shading"] != "smooth" or st["rails_sharp_edges"] == 0:
                f.append("%s.rails: shading %s with %d sharp edges" % (p["nm"], st["rails_shading"], st["rails_sharp_edges"]))
            for part in REPLACE + SAME:
                ob = bpy.data.objects.get(p["nm"] + "." + part)
                if ob is not None and part != "rails" and smooth_state(ob.data) != "flat":
                    f.append("%s.%s is not flat-shaded" % (p["nm"], part))
            log("WALK", p["key"], "PASS" if not f else "FAIL", json.dumps(st, default=str))
            fails += f
        # anything (not a link's) that stood on the range where it moved: how far over it it stands now
        if len(moved):
            gaps = rest_gaps(rng_obj, co0, co1, moved)
            log("RANGE objects standing on the moved range (max new gap under them, m):", gaps if gaps else "none")
            for nmo, gap in gaps:
                if gap > GAP_MAX:
                    fails.append("%s now stands %.3f m over the sunk range" % (nmo, gap))
        # names and counts
        if len(bpy.data.objects) != n_obj0 + len(tmp.objects):
            fails.append("object count %d -> %d" % (n_obj0, len(bpy.data.objects) - len(tmp.objects)))
        tmp_names = {o.name for o in tmp.objects}
        for p in plans:
            for part in REPLACE + SAME:
                nx = p["nm"] + "." + part + ".001"
                if bpy.data.objects.get(nx) is not None and nx not in tmp_names:
                    fails.append("%s exists" % nx)
        # caches: boxes
        grew = []
        for name, (lo0, hi0) in boxes_old.items():
            lo1, hi1 = world_box(bpy.data.objects[name])
            g_ = float(max((lo0 - lo1).max(), (hi1 - hi0).max()))
            if g_ > 1e-6:
                grew.append((name, round(g_, 4)))
        worst_growth = max([g_ for _, g_ in grew], default=0.0)
        log("BOXES grown past the old ones:", grew if grew else "none")
        for p in plans:
            upd = {k: v for k, v in p["rep"].items() if k not in ("depart", "arrival", "link")}
            by_link[p["key"]].update(upd)
        log("triangles of the replaced meshes %d -> %d" % (tri0, tri1))
        log("link structure kept whole in the proxies (bake_web.proxy_whole):",
            sum(tris(o.data) for o in bpy.data.collections["world.links"].all_objects
                if o.type == "MESH" and _proxy_whole(o.name)), "tris")
    finally:
        for o in list(tmp.objects):
            me = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        bpy.data.collections.remove(tmp)
    if fails:
        for f in fails:
            log("FAIL", f)
        raise SystemExit("patch_r11_links: %d checks failed; not saved" % len(fails))
    root["links"] = json.dumps(reports)
    if worst_growth <= BOX_TOL:
        log("CACHES ok: same names; every replaced mesh's box inside its old one within %.0f mm (worst %.4f m: the "
            "landings' tops, now flush with the treads); the range's box unchanged; steles.arrival 1 m shorter. Re-bake the chunks the stairs and "
            "the sunk range pass (gate mirror forge mission library steles scroll formation abode summit) and the "
            "backdrop, then the pack" % (BOX_TOL * 1000, worst_growth))
    else:
        log("CACHES needs audit: boxes grew %s - run the export_web audit, chunks,meta, then bakefull the chunks the "
            "stairs pass and the backdrop, then the pack" % grew)
    log("DIGEST", digest())
    log("done in %.0f s" % (time.time() - t_start))
    if dry:
        log("DRY_RUN: not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


def digest():
    """md5 of every world.link mesh (vertices, faces, smooth flags, sharp edges) and of world.range's vertices: equal
    after a first and a second run when the patch is idempotent."""
    import hashlib
    h = hashlib.md5()
    obs = sorted((o for o in bpy.data.collections["world.links"].all_objects if o.type == "MESH"), key=lambda o: o.name)
    for o in obs + [bpy.data.objects["world.range"], bpy.data.objects[STELES_SLAB]]:
        me = o.data
        h.update(o.name.encode())
        h.update(np.round(coords(me), 5).tobytes())
        lv = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get("vertex_index", lv)
        h.update(lv.tobytes())
        if o.name.startswith("world.link."):
            sm = np.zeros(len(me.polygons), bool)
            me.polygons.foreach_get("use_smooth", sm)
            h.update(sm.tobytes())
            h.update(str(sharp_count(me)).encode())
    return h.hexdigest()


def _proxy_whole(name):
    """bake_web.proxy_whole without importing bake_web (it pulls in export_web)."""
    parts = ("stairs", "rails", "piers", "arch", "foot_landing", "foot_rail", "rest_landing", "rest_rail", "rest_pier",
             "bridge.deck", "bridge.boards", "bridge.posts")
    if not name.startswith("world.link."):
        return False
    link, _, part = name[len("world.link."):].partition(".")
    return "_" in link and part in parts


main()
