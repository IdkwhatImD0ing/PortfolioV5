"""Scenery pass: forests, many more floating islands, many more waterfalls (blocking level).

Run on the assembled scene, before chase.py:
    blender -b out/sect.blend --python sect/scenery.py -- [--blend out/sect_scenic.blend]

What it adds on top of world.py:
- Forest on the range: dense far-LOD pine forest on the gentler slopes and tops, cliff pines on
  the steep rock, and groves of hero pines and peach blossom trees in a ring around each area.
- About 70 more floating islands, from small rocks to 30-70 m islands that carry their own trees
  (no buildings: none has a bridge, W8), and a waterfall pouring off the edge into the clouds.
- Waterfalls off the range's cliff edges around every area.
- The density pass (build_density): Huangshan pine crowns packed on every island and islet top
  with pines leaning out over the rim, denser cliff pines down to the near-vertical column walls,
  and a dense crown band under every peak's top. It only adds objects and range masks, each from
  its own generator, so nothing placed before it moves; sect/patch_density.py runs the same pass
  on a finished out/sect_chase.blend.

Everything stays clear of the flight: the flyer's route (the fly-through camera path) and the
chase camera's path (planned with chase.py's rig, before any of this exists), and nothing is
planted on an area's terrace. The density pass keeps its trees CARD_CLEAR m (plus their height)
off both, so the web build draws them as cheap far cards.
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
from mathutils import Vector, kdtree
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import chase as CH  # noqa: E402
from sect import world as W  # noqa: E402
from sect.lib import nature as N  # noqa: E402
from sect.lib import util as U  # noqa: E402

KEY = "scenery"
TREE_CLEAR = 24.0          # no tree within this distance (3D) of either flight path
CLIFF_TREE_CLEAR = 18.0
AREA_CLEAR = 14.0          # metres beyond an area's footprint kept free of trees
GROVE_RING = 70.0          # hero groves this far beyond the area clearance
FOREST_DENSITY = 0.012     # far pines per m2 on gentle slopes (world.py already has 0.0008)
GROVE_DENSITY = 0.006
CLIFF_DENSITY = 0.004
ISLANDS = 100
ISLAND_CLEAR = 30.0        # island edge to flight path
FALLS_PER_AREA = 3
FALL_CLEAR = 30.0
FALL_UNDER = 20.0          # island and range falls end this far under the cloud-sea top (no height cap)

# density pass (build_density; sect/patch_density.py takes overrides of these as KEY=value)
DENSITY_TAG = "sect_density"   # custom property on every object the pass makes (its category)
DENSITY_PARTS = ("range", "islands", "islets")
CHASE_CAM = "chase.cam"        # export_web.CAMERA: the camera the web build follows (once chase.py ran)
CARD_CLEAR = 70.0              # bake_trees --tree-near: a pine nearer the camera becomes a 3D mesh
FACE_SLACK = 20.0              # range masks test face centres: + tree height + half a tall wall face
CLIFF_DENSE = 0.008            # on the old cliff band, on top of CLIFF_DENSITY (0.012 per m2 in all)
WALL_DENSITY = 0.012           # near-vertical walls (normal z WALL_NZ-0.20) the old band skipped
WALL_NZ = 0.08
WALL_MAX_SLOPE = 86.0          # degrees from flat (scatter normal test 0.07 < WALL_NZ)
MASK_CELL = 5.0                # m: the range masks read face normals averaged over cells this size, the scale their
                               # densities were tuned on. (2026-10-21: on the 2.5 m range the 7 m crag and 11 m strata
                               # resolve into near-vertical flutes and ledges; tested face by face, a column wall seen
                               # at 830 kept 15 of its 54 wall pines)
CLIFF_SCATTER_SLOPE = 100.0    # degrees: the cliff scatters' own per-face test (cliffpines, .dense, .walls): a fluted
                               # wall's faces inside a masked cell stand up to 10 deg past vertical
CROWN_DEPTH = 22.0             # crown band: range faces this far under each peak's top
CROWN_DENSITY = 0.02           # on top of the forest / cliff pines there (~0.03 per m2 in all)
ISLAND_MIN = 11.0              # measured top width (~0.92 x floating_rock size: 12 m rocks) for a crown
ISLAND_DENSITY = 0.025         # crown pines per m2 of top
ISLAND_SPACING = (4.0, 6.0)    # trunk to trunk (m), drawn per island
ISLAND_TREE_H = (0.25, 0.4)    # crown pine height x island size
ISLAND_RIM_H = (0.3, 0.45)     # rim pine height x island size
ISLAND_TREE_MAX = 26.0
ISLAND_RIM_PINES = (2, 4)      # pines on the rim leaning out over the drop
ISLAND_FALL_HALF = 0.14        # half the widest island fall (build_islands: 0.16-0.26 x size) + slack
ISLAND_CROWN_R = 0.45          # crown reach x pine height (the lean side's long limbs)
RIM_BINS = 90
# composition (audit D2, 2026-10-21): islands moved off the hold views' focal lines, world offsets (m), applied after
# build_islands (sect/patch_r2_compose.py moves them in the finished scene). island.092 sat on the library pagoda's
# spire at 772 (it goes 50 m to that camera's right and 10 m up, into clear sky); island.052 stood between the summit
# pavilion's finial and the moon at 1647 (120 m to that camera's left and 70 m up, beside the moon; lower, it showed
# in the abode hold's open sky at 1380)
ISLAND_NUDGES = {"scenery.island.092": (19.1, -46.2, 10.0), "scenery.island.052": (-119.0, 14.8, 70.0)}
NUDGE_REACH = (3.0, 5.0, 40.0)  # an island's companions have their origin in its box plus this (sideways, down, up)
# Ice-Fire Island 冰火島 (Heaven Sword and Dragon Saber, round 7; rebuilt whole in round 36): the island the flight
# sees largest made half glacier, half volcano. island.009, the 70 m island with the waterfall at the library hold (772:
# 236 x 298 px of a 1600 x 900 frame, 90 % unoccluded; the most on-screen area of any island over the whole path).
# Round 36 (sect/lib/icefire_island.py): its rock mesh is replaced by one closed island (a single tip vertex, the lava
# sunk into it as faces of the rock, so the web's decimated stand-in stays whole) with a glacier cap, icicles,
# stalactites and a volcano as its children. The halves face the hold: the fire half's centre goes to one side of the
# hold camera's line, on the side that keeps the waterfall in the ice half, so a turned island (round 39's
# turn_icefire) still shows its lava. Runs after the density and life passes and after turn_icefire (it removes the
# island's plants and reads the rock's transform); sect/patch_r36_icefire.py does the same on a finished scene.
# (lib/icefire_props.py, the round-7 build, is no longer called.)
ICEFIRE_ISLAND = "scenery.island.009"


def _log(*a):
    print("SCENERY", *a, flush=True)


# ---- flight paths ----------------------------------------------------------------------------

def flight_paths(scene):
    """Flyer route + chase camera path as one KD tree (points every 2 frames)."""
    frames, pos, look0, heroes, _ = CH.route(scene)
    plan = CH.plan_orbit(pos, look0, frames, heroes, scene.render.fps)
    pts = np.vstack([pos[::2], plan["cam"][::2]])
    kd = kdtree.KDTree(len(pts))
    for i, p in enumerate(pts):
        kd.insert(Vector(p), i)
    kd.balance()
    return kd, pos


def path_dist(kd, p):
    return kd.find(Vector(p))[2]


# ---- forest ---------------------------------------------------------------------------------

def _face_data(me):
    n = len(me.polygons)
    centers = np.empty(n * 3)
    normals = np.empty(n * 3)
    mats = np.empty(n, dtype=np.int32)
    me.polygons.foreach_get("center", centers)
    try:
        me.polygons.foreach_get("normal", normals)
    except Exception:
        normals[:] = 0.0
        normals[2::3] = 1.0
    me.polygons.foreach_get("material_index", mats)
    return centers.reshape(-1, 3), normals.reshape(-1, 3), mats


def cell_nz(cw, nrm, area, top, cell=None):
    """Per face: the normal z of its MASK_CELL x MASK_CELL cell of the range (the area-weighted mean normal of the
    top faces whose centres fall in it); top faces only, others keep their own. On a 5 m range each top face is its
    own cell, so this is its own normal."""
    cell = MASK_CELL if cell is None else cell
    nz = nrm[:, 2].copy()
    i = np.nonzero(top)[0]
    if not len(i):
        return nz
    kx = np.floor((cw[i, 0] - W.EXTENT[0]) / cell + 1e-6).astype(np.int64)
    ky = np.floor((cw[i, 1] - W.EXTENT[2]) / cell + 1e-6).astype(np.int64)
    key = kx * 100003 + ky
    _, inv = np.unique(key, return_inverse=True)
    acc = np.zeros((inv.max() + 1, 3))
    np.add.at(acc, inv, nrm[i] * area[i, None])
    acc /= np.maximum(np.linalg.norm(acc, axis=1), 1e-12)[:, None]
    nz[i] = acc[inv, 2]
    return nz


def forest_masks(rng_obj, kd, anchors):
    me = rng_obj.data
    mw = np.array(rng_obj.matrix_world)
    c, nrm, mats = _face_data(me)
    cw = c @ mw[:3, :3].T + mw[:3, 3]
    top = mats != 2                                 # material 2 = underside rock
    area = np.empty(len(me.polygons))
    me.polygons.foreach_get("area", area)
    nz = cell_nz(cw, nrm, area, top)
    above_cloud = cw[:, 2] > W.CLOUD_SEA_Z + 12.0
    d_path = np.array([path_dist(kd, p) for p in cw])
    d_area = np.full(len(cw), 1e9)
    grove_band = np.zeros(len(cw), bool)
    for k, a in anchors.items():
        dx = np.hypot(cw[:, 0] - a[0], cw[:, 1] - a[1]) - (a[3] + AREA_CLEAR)
        d_area = np.minimum(d_area, dx)
        grove_band |= (dx > 0) & (dx < GROVE_RING) & (np.abs(cw[:, 2] - a[2]) < 45.0)
    clear = (d_area > 0) & above_cloud & top
    forest = clear & (nz > 0.70) & (d_path > TREE_CLEAR) & ~grove_band
    grove = clear & (nz > 0.72) & (d_path > TREE_CLEAR) & grove_band
    cliff = clear & (nz > 0.20) & (nz <= 0.70) & (d_path > CLIFF_TREE_CLEAR)
    for name, m in (("scenery_forest", forest), ("scenery_grove", grove), ("scenery_cliff", cliff)):
        at = me.attributes.get(name) or me.attributes.new(name, 'FLOAT', 'FACE')
        at.data.foreach_set("value", m.astype(np.float32))
    # no trees in the links' stair bodies, pier arcades, landings or bridges (world.link.*)
    _log("faces cleared near links", W.clear_mask_near(rng_obj, ["scenery_forest", "scenery_grove", "scenery_cliff"],
                                                        W.link_points()))
    area = lambda m: float(np.sum(m)) * W.GRID * W.GRID  # noqa: E731 (faces are ~GRID x GRID)
    _log("forest_m2", round(area(forest)), "grove_m2", round(area(grove)), "cliff_m2", round(area(cliff)))
    return area(forest), area(grove), area(cliff)


def clear_round34(rng_obj):
    """Round 34: no trees on world.range round 思過崖 on the cliff behind the mirror (sect/lib/refs_west.py
    siguoya_clear: the masks just made are zeroed there, as sect/patch_r34_west.py zeroes them in a built file)."""
    ob = bpy.data.objects.get("mirror.siguoya")
    root = bpy.data.objects.get("mirror.root")
    if ob is None or root is None:
        return
    from sect.lib import refs_west as RW
    RW.siguoya_clear(rng_obj, root, RW.local_matrix(ob, root), log=lambda *a: _log(*a))


def _blossom_protos():
    out = []
    for v in range(3):
        for lod in ("mid", "far", "hero"):
            try:
                out.append(N._blossom_proto("peach", v, lod))
                break
            except Exception:
                continue
    return out


def build_forest(coll, kd, anchors):
    rng_obj = bpy.data.objects["world.range"]
    a_forest, a_grove, a_cliff = forest_masks(rng_obj, kd, anchors)
    clear_round34(rng_obj)
    # pines only: at ~200 m the set's two shrubs were dropped or shrank to specks
    N.scatter_on(rng_obj, N.plant_prototypes("forest")[:6], density=FOREST_DENSITY, seed=31,
                 max_slope=math.radians(46), scale_range=(1.2, 2.4), mask_attribute="scenery_forest",
                 collection=coll, name="scenery.forest", align=0.1)
    grove_protos = N.plant_prototypes("pines") + _blossom_protos()
    N.scatter_on(rng_obj, grove_protos, density=GROVE_DENSITY, seed=37, max_slope=math.radians(44),
                 scale_range=(0.9, 1.6), mask_attribute="scenery_grove", collection=coll,
                 name="scenery.grove", align=0.05, min_distance=5.0)
    N.scatter_on(rng_obj, N.plant_prototypes("forest")[:6], density=CLIFF_DENSITY, seed=41,
                 max_slope=math.radians(CLIFF_SCATTER_SLOPE), scale_range=(0.8, 1.5), mask_attribute="scenery_cliff",
                 collection=coll, name="scenery.cliffpines", align=0.3)
    _log("trees_estimate", int(a_forest * FOREST_DENSITY + a_grove * GROVE_DENSITY + a_cliff * CLIFF_DENSITY))


# ---- floating islands -----------------------------------------------------------------------

def _range_bvh():
    ob = bpy.data.objects["world.range"]
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(ob, dg)
    return bvh, ob.matrix_world.copy(), ob.matrix_world.inverted()


def _existing_islets():
    out = []
    for ob in bpy.data.objects:
        if ob.name.startswith("world.islet") and ob.type == 'MESH' and ob.parent is None:
            s = max(ob.dimensions.x, ob.dimensions.y)
            out.append((ob.location.x, ob.location.y, ob.location.z, s))
    return out


def _fall(coll, lip, outward, height, width, seed, name):
    dx, dy = outward
    yaw = math.atan2(dx, -dy)       # local -Y (the pour direction) points outward
    N.waterfall(coll, height=height, width=width, seed=seed, sheets=2, mist=True, foam=False,
                name=name, location=lip, rotation=(0, 0, yaw))


_ISLAND_ROCK = re.compile(r"^scenery\.island(\.\d{3})?$")


def island_companions(rock):
    """Top-level objects that stand on or pour from ``rock`` without being its children: build_islands' top pines,
    blossoms and fall ('scenery.island.*') and the life pass's ('life.*'), whose origin lies in the box of the rock
    and its children, widened by NUDGE_REACH."""
    pts = []
    for x in [rock] + list(rock.children_recursive):
        if x.type in ('MESH', 'CURVE'):
            pts += [x.matrix_world @ Vector(c) for c in x.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    side, down, up = NUDGE_REACH
    out = []
    for o in bpy.data.objects:
        if o.parent is not None or o == rock or _ISLAND_ROCK.match(o.name):
            continue
        if not (o.name.startswith("scenery.island.") or o.name.startswith("life.")):
            continue
        p = o.matrix_world.translation
        if lo.x - side <= p.x <= hi.x + side and lo.y - side <= p.y <= hi.y + side and lo.z - down <= p.z <= hi.z + up:
            out.append(o)
    return out


def nudge_islands(nudges=None):
    """Move each island of ``nudges`` (default ISLAND_NUDGES) and its companions by its offset. Returns
    {island: [companion names]} for the islands found."""
    out = {}
    for name, off in (ISLAND_NUDGES if nudges is None else nudges).items():
        rock = bpy.data.objects.get(name)
        if rock is None:
            _log("WARN nudge: no", name)
            continue
        comp = island_companions(rock)
        for o in [rock] + comp:
            o.location += Vector(off)
        out[name] = sorted(o.name for o in comp)
        _log("nudged", name, off, "with", len(comp), "companions")
    return out


# Round 39 (the r31 references plan, as approved): Ice-Fire Island is the library stop's reference (Zhang Wuji's first
# school), but at the library hold (772) the frame's top cut it and its glacier faced the camera. It turns ICEFIRE_TURN
# degrees about its own vertical axis (through the rock's origin), so its fire half and lava face the hold, and drops
# ICEFIRE_DROP m, so it sits whole in the sky between the waterfall cliff and the pagoda. Its companions (its waterfall,
# any plants standing on it) turn and drop with it; its children follow the rock. Runs after nudge_islands and the life
# pass and before build_icefire (round 36's island reads the rock's transform); sect/patch_r39_centre.py turns it in a
# finished scene the same way.
ICEFIRE_TURN = 150.0
ICEFIRE_DROP = 25.0


def icefire_turn_matrix(rock):
    """The world matrix that turns ``rock`` ICEFIRE_TURN deg about the vertical through its origin and drops it."""
    from mathutils import Matrix
    o = rock.matrix_world.translation.copy()
    turn = Matrix.Rotation(math.radians(ICEFIRE_TURN), 4, 'Z')
    return Matrix.Translation(o + Vector((0.0, 0.0, -ICEFIRE_DROP))) @ turn @ Matrix.Translation(-o)


def turn_icefire(name=None):
    """Turn and drop ICEFIRE_ISLAND and its companions (see above). Returns the companions' names, or None."""
    rock = bpy.data.objects.get(name or ICEFIRE_ISLAND)
    if rock is None:
        _log("WARN icefire turn: no", name or ICEFIRE_ISLAND)
        return None
    comp = island_companions(rock)
    R = icefire_turn_matrix(rock)
    for o in [rock] + comp:
        o.matrix_world = R @ o.matrix_world
    bpy.context.view_layer.update()
    _log("icefire turned", ICEFIRE_TURN, "deg, dropped", ICEFIRE_DROP, "m, with", sorted(o.name for o in comp))
    return sorted(o.name for o in comp)


def build_islands(coll, kd, pos, anchors):
    r = U.rng(KEY, "islands")
    bvh, mw, mwi = _range_bvh()
    placed = _existing_islets()
    made = falls = 0
    tries = 0
    seg = np.linalg.norm(np.diff(pos, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    while made < ISLANDS and tries < 4000:
        tries += 1
        si = r.uniform(0.0, s[-1])
        i = int(np.searchsorted(s, si).clip(1, len(pos) - 1))
        p, t = pos[i], pos[i] - pos[i - 1]
        h = Vector((t[0], t[1], 0.0))
        if h.length < 1e-6:
            continue
        h.normalize()
        side = Vector((-h.y, h.x, 0.0)) * (1 if r.random() < 0.5 else -1)
        near = r.random() < 0.35
        dist = r.uniform(60.0, 220.0) if near else r.uniform(220.0, 950.0)
        roll = r.random()
        size = r.uniform(8.0, 16.0) if roll < 0.3 else (r.uniform(16.0, 30.0) if roll < 0.62 else r.uniform(30.0, 75.0))
        c = Vector(p) + side * dist + h * r.uniform(-60, 60)
        c.z = p[2] + r.uniform(-120.0, 90.0)
        if c.z - size * 1.1 < W.CLOUD_SEA_Z - 10.0:
            continue
        if path_dist(kd, c) < size * 0.9 + ISLAND_CLEAR:
            continue
        hit = bvh.find_nearest(mwi @ c)
        if hit[0] is not None and (mw @ hit[0] - c).length < size * 1.0 + 12.0:
            continue
        if any(math.hypot(c.x - a[0], c.y - a[1]) < a[3] + 40.0 + size for a in anchors.values()):
            continue
        if math.hypot(c.x - W.OPENING_BANK[0], c.y - W.OPENING_BANK[1]) < 100.0:
            continue
        if any(math.dist((c.x, c.y, c.z), q[:3]) < (size + q[3]) * 0.6 + 12.0 for q in placed):
            continue
        k = made
        placed.append((c.x, c.y, c.z, size))
        made += 1
        rock = N.floating_rock(coll, size=size, seed=900 + k, vegetation=True, roots=True,
                               pine_on_top=size < 30.0, name="scenery.island", location=tuple(c),
                               rotation=r.uniform(0, 2 * math.pi))
        W.tidy_rock(rock)          # round 12: the cone's bottom closes in one point (it stood as folded fins)
        top_r = size * 0.42
        if size >= 26.0:                            # a little forest (and maybe a pavilion) on top
            n_trees = int(size / 7.0)
            for j in range(n_trees):
                a = r.uniform(0, 2 * math.pi)
                rr = top_r * math.sqrt(r.uniform(0.05, 0.8))
                loc = (c.x + math.cos(a) * rr, c.y + math.sin(a) * rr, c.z + 0.05)
                if r.random() < 0.7:
                    N.pine(coll, height=r.uniform(7.0, 13.0), seed=1300 + k * 13 + j, style="huangshan", lod="mid",
                           name="scenery.island.pine", location=loc)
                else:
                    N.blossom_tree(coll, height=r.uniform(5.0, 8.0), seed=1700 + k * 13 + j, kind="peach",
                                   lod="far", name="scenery.island.blossom", location=loc)
            if r.random() < 0.25:
                # (W8: no pavilion; a building on an island with no bridge to it reads as
                # unreachable. The draw keeps the island sequence exactly as before.)
                r.uniform(0, 6.28)
        if size >= 18.0 and r.random() < 0.6:       # a waterfall pouring off the edge
            a = r.uniform(0, 2 * math.pi)
            out = (math.cos(a), math.sin(a))
            lip = (c.x + out[0] * top_r * 0.95, c.y + out[1] * top_r * 0.95, c.z - 0.25)
            # down into the cloud sea (FALL_UNDER m under its top): the old 260 m cap left the falls of the high
            # islands ending in mid-air (sect/patch_water.py extends those in a finished scene)
            height = max(40.0, lip[2] - (W.CLOUD_SEA_Z - FALL_UNDER))
            _fall(coll, lip, out, height, size * r.uniform(0.16, 0.26), 2100 + k, "scenery.island.fall")
            falls += 1
    _log("islands", made, "island_falls", falls, "tries", tries)


# ---- waterfalls off the range ------------------------------------------------------------------

def build_range_falls(coll, kd, anchors):
    r = U.rng(KEY, "falls")
    bvh, mw, mwi = _range_bvh()
    lips = []
    for k, a in anchors.items():
        if k in W.FLOATING:
            continue
        found = 0
        start = r.uniform(0, 2 * math.pi)
        for j in range(12):
            if found >= FALLS_PER_AREA:
                break
            ang = start + j * (2 * math.pi / 12)
            d = Vector((math.cos(ang), math.sin(ang), 0.0))
            prev = None
            for step in range(1, 90):
                q = Vector((a[0], a[1], 0)) + d * (a[3] + 12.0 + step * 4.0)
                src = Vector((q.x, q.y, a[2] + 160.0))
                hit = bvh.ray_cast(mwi @ src, Vector((0, 0, -1)), 600.0)
                z = (mw @ hit[0]).z if hit[0] is not None else None
                if prev is not None and (z is None or prev[2] - z > 30.0):
                    lip = prev
                    break
                prev = (q.x, q.y, z) if z is not None else prev
            else:
                continue
            if lip is None or lip[2] < W.CLOUD_SEA_Z + 30.0:
                continue
            if path_dist(kd, lip) < FALL_CLEAR:
                continue
            if any(math.dist(lip, o) < 45.0 for o in lips):
                continue
            lips.append(lip)
            found += 1
            height = max(40.0, lip[2] - (W.CLOUD_SEA_Z - FALL_UNDER))      # no 320 m cap: into the cloud sea
            _fall(coll, (lip[0], lip[1], lip[2] + 0.2), (d.x, d.y), height, r.uniform(12.0, 26.0),
                  3000 + len(lips), "scenery.fall")
    _log("range_falls", len(lips))


# ---- density pass: Huangshan crowns on the islands, the peaks and the steep rock -------------------

def density_paths(scene):
    """KD tree of the camera paths for the density pass: flight_paths' points, plus the baked chase
    camera (CHASE_CAM, the path the web build follows) every 2 frames when the scene has one."""
    frames, pos, look0, heroes, _ = CH.route(scene)
    plan = CH.plan_orbit(pos, look0, frames, heroes, scene.render.fps)
    pts = [pos[::2], plan["cam"][::2]]
    cam = bpy.data.objects.get(CHASE_CAM)
    if cam is not None and cam.animation_data is not None and cam.animation_data.action is not None:
        try:
            pts.append(CH.path_from_camera(cam, frames[::2]))
        except Exception as exc:                    # not keyed on location: the planned chase stands in
            _log("WARN", CHASE_CAM, "not sampled:", exc)
    used = len(pts) == 3
    pts = np.vstack(pts)
    kd = kdtree.KDTree(len(pts))
    for i, p in enumerate(pts):
        kd.insert(Vector(p), i)
    kd.balance()
    _log("density paths", len(pts), "points", "(route, planned chase%s)" % (", " + CHASE_CAM if used else ""))
    return kd


def _crown_band(cw, top, peaks, depth=None):
    """Faces within ``depth`` m (default CROWN_DEPTH) under the top of a peak (world.Range.peaks). The
    top is measured on the mesh around the peak's centre: strata, crag noise and a taller neighbour
    all move it."""
    depth = CROWN_DEPTH if depth is None else depth
    band = np.zeros(len(cw), bool)
    tops = 0
    for (px, py, _z, rad, _wall, cap) in peaks:
        d = np.hypot(cw[:, 0] - px, cw[:, 1] - py)
        near = top & (d < rad * 1.6 + 2.0 * W.GRID)
        core = near & (d < max(cap * rad, 2.5 * W.GRID))
        if not core.any():
            continue
        zt = float(cw[core, 2].max())
        band |= near & (cw[:, 2] >= zt - depth) & (cw[:, 2] <= zt + 1.0)
        tops += 1
    return band, tops


DENSITY_MASKS = ("scenery_cliff_dense", "scenery_cliff_wall", "scenery_crown")


def density_masks(rng_obj, kd, anchors):
    """range_density's three FACE masks on ``rng_obj`` (DENSITY_MASKS), cleared near the links. Also run on its own
    when world.range gets new faces (sect/patch_r2_range.py): its scatters then re-seed on the new mesh. Returns
    (masks [(name, bool per face)], face areas, crown band peaks)."""
    me = rng_obj.data
    mw = np.array(rng_obj.matrix_world)
    c, nrm, mats = _face_data(me)
    cw = c @ mw[:3, :3].T + mw[:3, 3]
    area = np.empty(len(me.polygons))
    me.polygons.foreach_get("area", area)
    top = mats != 2                                 # material 2 = underside rock
    nz = cell_nz(cw, nrm, area, top)
    d_area = np.full(len(cw), 1e9)
    for a in anchors.values():
        d_area = np.minimum(d_area, np.hypot(cw[:, 0] - a[0], cw[:, 1] - a[1]) - (a[3] + AREA_CLEAR))
    d_path = np.array([path_dist(kd, p) for p in cw])
    clear = (d_area > 0) & (cw[:, 2] > W.CLOUD_SEA_Z + 12.0) & top & (d_path > CARD_CLEAR + FACE_SLACK)
    steep = math.cos(math.radians(WALL_MAX_SLOPE))
    band, tops = _crown_band(cw, top, W.Range(W._norm_anchors(anchors)).peaks)
    masks = ((DENSITY_MASKS[0], clear & (nz > 0.20) & (nz <= 0.70)),
             (DENSITY_MASKS[1], clear & (nz > WALL_NZ) & (nz <= 0.20)),
             (DENSITY_MASKS[2], clear & (nz > steep) & band))
    for name, m in masks:
        at = me.attributes.get(name) or me.attributes.new(name, 'FLOAT', 'FACE')
        at.data.foreach_set("value", m.astype(np.float32))
    _log("density faces cleared near links", W.clear_mask_near(rng_obj, list(DENSITY_MASKS), W.link_points()))
    return masks, area, tops


def range_density(coll, kd, anchors):
    """Three more pine scatters on world.range, far-LOD Huangshan pines only, each on a new FACE mask
    (density_masks: the same exclusions as forest_masks, and CARD_CLEAR + FACE_SLACK m off the paths):
    scenery.cliffpines.dense (cliff band, + CLIFF_DENSE), scenery.cliffpines.walls (the column walls,
    normal z WALL_NZ-0.20, WALL_DENSITY) and scenery.crowns (CROWN_DEPTH m under every peak's top,
    + CROWN_DENSITY). Returns {name: expected instances}."""
    rng_obj = bpy.data.objects["world.range"]
    me = rng_obj.data
    masks, area, tops = density_masks(rng_obj, kd, anchors)
    clear_round34(rng_obj)
    out = {}
    pines = N.plant_prototypes("forest")[:6]
    for (mask, _), (name, dens, seed, scale, align, slope) in zip(masks, (
            ("scenery.cliffpines.dense", CLIFF_DENSE, 43, (0.8, 1.5), 0.3, CLIFF_SCATTER_SLOPE),
            ("scenery.cliffpines.walls", WALL_DENSITY, 47, (0.8, 1.5), 0.3, CLIFF_SCATTER_SLOPE),
            ("scenery.crowns", CROWN_DENSITY, 53, (0.8, 1.6), 0.15, WALL_MAX_SLOPE))):
        v = np.empty(len(me.polygons), np.float32)
        me.attributes[mask].data.foreach_get("value", v)
        ob = N.scatter_on(rng_obj, pines, density=dens, seed=seed, max_slope=math.radians(slope),
                          scale_range=scale, mask_attribute=mask, collection=coll, name=name, align=align)
        ob[DENSITY_TAG] = "range"
        out[ob.name] = int(float(area[v > 0.5].sum()) * dens)
        _log("density", ob.name, "mask m2", round(float(area[v > 0.5].sum())), "expected pines", out[ob.name])
    _log("density crown band: peaks", tops)
    return out


def _rocks(prefix):
    """Floating rocks named prefix, prefix.001, ... (not their children), by name."""
    pat = re.compile(r"^%s(\.\d{3})?$" % re.escape(prefix))
    return sorted((o for o in bpy.data.objects if o.type == 'MESH' and pat.match(o.name)), key=lambda o: o.name)


def _rock_top(rock):
    """Rock-local top of a nature.floating_rock (its material-1 faces, whichever way their normals
    point): rim radius per azimuth (RIM_BINS), top area (m2), highest top z and a BVH of the top
    faces alone (a ray that misses it is off the top). None when the rock has no top."""
    me = rock.data
    n = len(me.polygons)
    if n == 0:
        return None
    mats = np.empty(n, np.int32)
    me.polygons.foreach_get("material_index", mats)
    ti = np.nonzero(mats == 1)[0]
    if len(ti) < 3:
        return None
    area = np.empty(n)
    me.polygons.foreach_get("area", area)
    ls = np.empty(n, np.int32)
    lt = np.empty(n, np.int32)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    polys = [lv[ls[i]:ls[i] + lt[i]].tolist() for i in ti]
    tv = co[np.unique(np.concatenate(polys))]
    th = np.arctan2(tv[:, 1], tv[:, 0])
    b = np.floor((th + math.pi) / (2.0 * math.pi) * RIM_BINS).astype(int) % RIM_BINS
    rim = np.zeros(RIM_BINS)
    np.maximum.at(rim, b, np.hypot(tv[:, 0], tv[:, 1]))
    cen = (np.arange(RIM_BINS) + 0.5) * (2.0 * math.pi / RIM_BINS) - math.pi
    ok = rim > 0.0
    rim = np.interp(cen, cen[ok], rim[ok], period=2.0 * math.pi)
    return dict(rim=rim, cen=cen, area=float(area[ti].sum()), ztop=float(tv[:, 2].max()),
                zlow=float(tv[:, 2].min()), bvh=BVHTree.FromPolygons(co.tolist(), polys))


def _top_z(shp, x, y):
    """Height of the rock's top at rock-local (x, y), or None off the top. Cast down, and up from
    under it as well, so an inside-out top (reversed faces) is found either way."""
    for z0, dz in ((shp["ztop"] + 5.0, -1.0), (shp["zlow"] - 5.0, 1.0)):
        hit = shp["bvh"].ray_cast(Vector((x, y, z0)), Vector((0.0, 0.0, dz)), 60.0)[0]
        if hit is not None:
            return hit.z
    return None


def island_crowns(kd, prefix, tag):
    """Pine crowns on every floating rock named ``prefix`` (_rocks) whose measured top is at least
    ISLAND_MIN wide: ISLAND_RIM_PINES pines on the rim leaning outward (ISLAND_RIM_H x size), then
    far-LOD Huangshan pines packed toward the rim at ISLAND_DENSITY per m2 of top, ISLAND_SPACING
    apart (ISLAND_TREE_H x size). Each rock has its own generator (keyed by its name), so the
    islands' own draws are untouched. Keeps clear of the trees already there and the island
    waterfalls (a crown keeps half the widest fall, ISLAND_FALL_HALF x size, + ISLAND_CROWN_R x its
    height off a lip); every pine stays CARD_CLEAR m + its height off the paths. Pines are children
    of their rock (rock-local placement), tagged DENSITY_TAG = ``tag``. Returns counts."""
    old, lips = [], []
    lip_pat = re.compile(r"^%s\.fall(\.\d{3})?$" % re.escape(prefix))
    for o in bpy.data.objects:
        if not o.name.startswith(prefix + ".") or DENSITY_TAG in o:
            continue
        if o.instance_type == 'COLLECTION' and o.instance_collection is not None:
            old.append(U.world_matrix(o).translation)
        elif lip_pat.match(o.name):
            lips.append(U.world_matrix(o).translation)
    n = dict(rocks=0, crowned=0, small=0, rim=0, crown=0, near_path_rejects=0, fall_rejects=0)
    for rock in _rocks(prefix):
        n["rocks"] += 1
        if rock.name == ICEFIRE_ISLAND:             # glacier and volcano, no pines (a re-run of patch_density.py would
            continue                                # otherwise plant them back under the ice cap)
        shp = _rock_top(rock)
        if shp is None:
            continue
        size = 2.0 * (math.sqrt(shp["area"] / math.pi) + 0.6)    # the rim sits ~0.6 m outside the top
        if size < ISLAND_MIN:
            n["small"] += 1
            continue
        q = U.rng(KEY, "crown", rock.name)
        M = U.world_matrix(rock)
        Mi = M.inverted_safe()
        reach = float(shp["rim"].max()) + 3.0
        spacing = q.uniform(*ISLAND_SPACING)
        taken = []                                  # rock-local (x, y, keep-off radius)
        for p in old:
            lp = Mi @ p
            if math.hypot(lp.x, lp.y) < reach and abs(lp.z) < 6.0:
                taken.append((lp.x, lp.y, spacing))
        falls = [(lp.x, lp.y) for lp in (Mi @ p for p in lips) if math.hypot(lp.x, lp.y) < reach and abs(lp.z) < 6.0]
        coll = rock.users_collection[0] if rock.users_collection else None

        def rim_at(a):
            return float(np.interp(math.atan2(math.sin(a), math.cos(a)), shp["cen"], shp["rim"],
                                   period=2.0 * math.pi))

        def plant(x, y, h, seed, lean, nm):
            if any(math.hypot(x - a, y - b) < r for a, b, r in taken):
                return False
            if any(math.hypot(x - a, y - b) < ISLAND_FALL_HALF * size + ISLAND_CROWN_R * h for a, b in falls):
                n["fall_rejects"] += 1
                return False
            z = _top_z(shp, x, y)
            if z is None:
                return False
            if path_dist(kd, M @ Vector((x, y, z))) < CARD_CLEAR + h:
                n["near_path_rejects"] += 1
                return False
            ob = N.pine(coll, height=h, seed=seed, style="huangshan", lod="far", name=rock.name + nm,
                        location=(x, y, z - 0.05), parent=rock, lean_toward=lean)
            ob[DENSITY_TAG] = tag
            taken.append((x, y, spacing))
            return True
        a0 = q.uniform(0.0, 2.0 * math.pi)
        k = q.randint(*ISLAND_RIM_PINES)
        made = 0
        for j in range(k):
            a = a0 + 2.0 * math.pi * j / k + q.uniform(-0.4, 0.4)
            rr = rim_at(a) - q.uniform(0.5, 1.2)
            h = min(ISLAND_TREE_MAX, size * q.uniform(*ISLAND_RIM_H))
            seed = q.randrange(1, 1000000)
            if rr > 1.0 and plant(math.cos(a) * rr, math.sin(a) * rr, h, seed, a, ".rim_pine"):
                n["rim"] += 1
                made += 1
        want = int(round(shp["area"] * ISLAND_DENSITY))
        got = 0
        for _ in range(want * 30):
            if got >= want:
                break
            a = q.uniform(0.0, 2.0 * math.pi)
            rr = q.random() ** (1.0 / 3.0) * (rim_at(a) - 1.0)        # area density ~ r^2: toward the rim
            h = min(ISLAND_TREE_MAX, max(4.0, size * q.uniform(*ISLAND_TREE_H)))
            seed = q.randrange(1, 1000000)
            if rr > 0.0 and plant(math.cos(a) * rr, math.sin(a) * rr, h, seed, None, ".crown_pine"):
                got += 1
        n["crown"] += got
        n["crowned"] += 1 if made + got else 0
    _log("density", prefix, json.dumps(n))
    return n


def build_density(scene, coll, anchors, parts=None):
    """The density pass (after the islands and falls; nothing it adds moves anything else) over
    ``parts`` (default DENSITY_PARTS). The abode's cliff pines come from abode.dense_pines, the
    inside-out island tops from nature.floating_rock."""
    parts = DENSITY_PARTS if parts is None else parts
    kd = density_paths(scene)
    out = {}
    if "range" in parts:
        out["range"] = range_density(coll, kd, anchors)
    if "islands" in parts:
        out["islands"] = island_crowns(kd, "scenery.island", "island")
    if "islets" in parts:
        out["islets"] = island_crowns(kd, "world.islet", "islet")
    return out


def build_icefire(name=None):
    """Make ICEFIRE_ISLAND Ice-Fire Island (sect/lib/icefire_island.py, round 36). Idempotent."""
    from sect.lib import icefire_island as II
    rock = bpy.data.objects.get(name or ICEFIRE_ISLAND)
    if rock is None:
        _log("WARN icefire: no", name or ICEFIRE_ISLAND)
        return None
    return II.build(rock, log=_log)


# =====================================================================================================================
# round 48: the background with intent (scratchpad r45/plan_final.md P-0 .. P-4, C; r49/intent.md)
# =====================================================================================================================
# Wall plants out, shelf plants in, a broadleaf canopy instead of the trunk carpet, caps on every pillar, hero pines on
# the rims the holds see, and beyond the near band a canopy mass (hull clumps and a shell) instead of single trees.
# Every object these passes make carries R48_TAG = its part and lives in collection R48_COLL (under 'scenery', so the
# web export treats it as scenery). sect/patch_r48_green.py runs them on a finished scene; build_r48() on a fresh one.

R48_TAG = "sect_r48"
R48_COLL = "scenery.r48"
R48_HIDDEN = "r48_hidden"          # objects a round-48 part hid (hide_render): the part's undo shows them again
# the masks of the old range scatters (forest_masks, density_masks, world.build_forest): zeroed outside the keep zones
# (P-2); their values before are kept once in 'r48_bak_<name>' so the undo can put them back
OLD_RANGE_MASKS = ("scenery_forest", "scenery_cliff", "scenery_cliff_dense", "scenery_cliff_wall", "scenery_crown",
                   "world_veg")
CANOPY_NEAR = 90.0             # m from the camera path: nearer than this the canopy thins to CANOPY_NEAR_K (the bake
CANOPY_NEAR_K = 0.3            # draws trees within --tree-near as 3D meshes; keep that count close to today's)
CANOPY_DENSITY = 0.028         # broadleaf crowns per m2 at factor 1 (a closed canopy: ~1 per 30 m2)
SPIRE_DENSITY = 0.005          # Masson spires (10-25 % of a canopy, more on rims and crests)
PINE_DENSITY = 0.002           # Huangshan pines on convex crests only (under 15 %)
SCRUB_DENSITY = 0.035          # scrub on 37-60 deg slopes
ACCENT_DENSITY = 0.006         # spring-green accent crowns in clusters by buildings, falls and path turns
CANOPY_SCALE = (0.6, 1.2)      # x nature.CANOPY_HEIGHT (10 m): 6-12 m crowns (plan D11: not 12-24 m)
SPIRE_SCALE = (0.6, 1.4)
PINE_SCALE = (0.6, 1.0)
SCRUB_SCALE = (0.8, 2.0)
GROVE_SCALE = 45.0             # m: groves and clearings (2D noise)
GROVE_FLOOR = 0.2              # density factor in a clearing
CONCAVE_BLUR = 30.0            # m: concavity (gullies x2, ridges x0.4) against the terrain smoothed this wide
CONCAVE_K = 6.0                # m of hollow for a factor of 2
FOREST_MODE = "hull"           # P-4 (B0 picks): 'cards' (trees everywhere), 'shell150' (trees to 150 m, shell beyond),
                               # 'shell250', 'hull' (trees to CANOPY_NEAR, hull clumps to 250 m, shell beyond)
SHELL_CELL = 7.5               # m: the shell's grid
SHELL_LIFT = (6.0, 11.0)       # m over the ground (the crowns' height), lumpy
SHELL_TILE = 320.0             # m: one shell / hull object per tile (the export splits by chunk)
HULL_STEP = 21.0               # m between hull clumps (jittered), in groves only
HULL_R = (5.0, 10.0)           # clump radius
SHELF_DENSITY = 0.05           # shrubs per m2 of pillar shelf top
CRACK_DENSITY = 0.04           # ferns per m2 of pillar crack strip
CAP_DENSITY = 0.03             # broadleaf per m2 of pillar cap
CAP_RIM_SPIRE = 0.012          # spires per m2 on the cap's outer quarter
HERO_PINE_H = (7.0, 10.0)      # m (scaled by the pillar's size 0.8-1.3)
HERO_PX = 18.0                 # a pillar is a hero-pine candidate when its top is this many px wide at the hold


def r48_collection(scene=None):
    root = U.get_collection(KEY, scene=scene)
    return U.get_collection(R48_COLL, parent=root, scene=scene)


def r48_tagged(parts):
    parts = set(parts)
    return [o for o in bpy.data.objects if o.get(R48_TAG) in parts]


def r48_remove(parts):
    """Delete what earlier runs made for ``parts`` (R48_TAG), with their meshes."""
    obs = r48_tagged(parts)
    meshes = {o.data for o in obs if o.type == 'MESH' and o.data is not None}
    n = 0
    for o in obs:
        bpy.data.objects.remove(o, do_unlink=True)
        n += 1
    for me in meshes:
        if me.users == 0:
            bpy.data.meshes.remove(me)
    return n


def r48_hide(obs, part):
    """Hide objects from the renders and the export (hide_render, hide_viewport), tagged R48_HIDDEN = part."""
    n = 0
    for o in obs:
        if not o.hide_render or o.get(R48_HIDDEN) != part:
            o.hide_render = True
            o.hide_viewport = True
            o[R48_HIDDEN] = part
            n += 1
    return n


def r48_unhide(part):
    n = 0
    for o in bpy.data.objects:
        if o.get(R48_HIDDEN) == part:
            o.hide_render = False
            o.hide_viewport = False
            del o[R48_HIDDEN]
            n += 1
    return n


def _range_faces(rng_obj):
    me = rng_obj.data
    mw = np.array(rng_obj.matrix_world)
    c, nrm, mats = _face_data(me)
    cw = c @ mw[:3, :3].T + mw[:3, 3]
    area = np.empty(len(me.polygons))
    me.polygons.foreach_get("area", area)
    top = mats != 2
    nz = cell_nz(cw, nrm, area, top)
    return cw, nz, top, area


def _path_dist(kd, cw, sel=None):
    d = np.full(len(cw), 1e9)
    idx = np.arange(len(cw)) if sel is None else np.nonzero(sel)[0]
    for i in idx:
        d[i] = kd.find(Vector(cw[i]))[2]
    return d


def _kd2(pts):
    kd = kdtree.KDTree(max(1, len(pts)))
    for i, p in enumerate(pts):
        kd.insert((float(p[0]), float(p[1]), 0.0), i)
    kd.balance()
    return kd


def r48_exclusion(rng_obj, cw, anchors, hold_views, star, path_d):
    """Faces of world.range no new plant may stand on (P-0): area terraces + AREA_CLEAR, the gate stair ramp, links
    (world.LINK_TREE_CLEAR), shrine terraces + 6 m and the chain bridge, the keep zones (60 m of a hold camera in its
    frame, + 15 m), each hold's sight cone to its star, the cleared cliff of 思過崖, the flight corridor (TREE_CLEAR)."""
    from sect.lib import r48 as R
    n = len(cw)
    ex = np.zeros(n, bool)
    why = {}
    for a in anchors.values():
        ex |= np.hypot(cw[:, 0] - a[0], cw[:, 1] - a[1]) < a[3] + AREA_CLEAR
    why["areas"] = int(ex.sum())
    if "gate" in anchors:
        g = anchors["gate"]
        ex |= (np.abs(cw[:, 0] - g[0]) < 25.0) & (cw[:, 1] < g[1] - 30.0) & (cw[:, 1] > g[1] - 150.0)
    lp = W.link_points()
    if len(lp):
        kd = _kd2(lp)
        near = np.array([kd.find((float(x), float(y), 0.0))[2] < W.LINK_TREE_CLEAR for x, y in cw[:, :2]])
        ex |= near
        why["links"] = int(near.sum())
    for o in bpy.data.objects:
        if o.type != 'MESH' or not o.name.startswith(("life.shrine.", "life.span")):
            continue
        bb = np.array([list(o.matrix_world @ Vector(p)) for p in o.bound_box])
        lo, hi = bb.min(0) - 6.0, bb.max(0) + 6.0
        m = (cw[:, 0] > lo[0]) & (cw[:, 0] < hi[0]) & (cw[:, 1] > lo[1]) & (cw[:, 1] < hi[1]) & \
            (cw[:, 2] > lo[2] - 20.0) & (cw[:, 2] < hi[2] + 2.0)
        ex |= m
    keep = R.keep_zone_mask(cw, hold_views, r=R.KEEP_R, pad=R.KEEP_PAD)
    ex |= keep
    why["keep_zones"] = int(keep.sum())
    n_under = 0
    for o in bpy.data.objects:          # the plinth under a round-48 pillar: no tree inside its rock
        if "r48_peak" in o.keys() and "nature_top_z" in o.keys():
            p = o.matrix_world.translation
            rb = float(o.get("nature_bottom_radius", 1.6 * float(o.get("nature_top_radius", 10.0))))
            m = np.hypot(cw[:, 0] - p.x, cw[:, 1] - p.y) < rb * 1.1 + 3.0
            n_under += int(m.sum())
            ex |= m
    why["under_pillars"] = n_under
    for v in hold_views:
        sb = (star or {}).get(v.name)
        if sb is None:
            continue
        u, vv, d = v.project(cw)
        cone = (d > 0) & (d < sb["depth"] + 30.0) & (u > sb["u0"] - 0.03) & (u < sb["u1"] + 0.03) & \
            (vv > sb["v_top"] - 0.03) & (vv < 1.05)
        ex |= cone
        why["sight_" + v.name] = int(cone.sum())
    ob = bpy.data.objects.get("mirror.siguoya")
    root = bpy.data.objects.get("mirror.root")
    if ob is not None and root is not None:
        from sect.lib import refs_west as RW
        idx = RW.siguoya_clear_faces(rng_obj, root, RW.local_matrix(ob, root))
        ex[idx] = True
        why["siguoya"] = int(len(idx))
    ex |= path_d < TREE_CLEAR
    _log("r48 exclusion", int(ex.sum()), "faces", json.dumps(why))
    return ex


def _grid_concavity(cw, top):
    """Per face: (terrain smoothed CONCAVE_BLUR wide) - (its own height), on the 2.5 m grid of the top faces (> 0 in
    gullies and saddles, < 0 on ridges and crests)."""
    g = W.GRID
    i = np.floor((cw[:, 0] - W.EXTENT[0]) / g).astype(np.int64)
    j = np.floor((cw[:, 1] - W.EXTENT[2]) / g).astype(np.int64)
    nx = int((W.EXTENT[1] - W.EXTENT[0]) / g) + 2
    ny = int((W.EXTENT[3] - W.EXTENT[2]) / g) + 2
    Z = np.zeros((ny, nx))
    Wt = np.zeros((ny, nx))
    t = np.nonzero(top)[0]
    np.add.at(Z, (j[t], i[t]), cw[t, 2])
    np.add.at(Wt, (j[t], i[t]), 1.0)
    have = Wt > 0
    Zm = np.where(have, Z / np.maximum(Wt, 1), 0.0)
    k = max(1, int(CONCAVE_BLUR / g / 3.0))

    def box(a):
        for ax in (0, 1):
            c = np.cumsum(np.pad(a, [(k + 1, k) if q == ax else (0, 0) for q in (0, 1)], mode="edge"), axis=ax)
            if ax == 0:
                a = (c[2 * k + 1:] - c[:-2 * k - 1]) / (2 * k + 1)
            else:
                a = (c[:, 2 * k + 1:] - c[:, :-2 * k - 1]) / (2 * k + 1)
        return a
    num, den = Zm * have, have.astype(float)
    for _ in range(3):
        num, den = box(num), box(den)
    S = num / np.maximum(den, 1e-6)
    lap = np.zeros(len(cw))
    lap[t] = S[j[t], i[t]] - cw[t, 2]
    return lap


def r48_canopy_masks(rng_obj, scene, anchors, hold_views, star, scope=None):
    """Writes the round-48 FACE masks and density factors on world.range and returns their stats:
    r48_excl (P-0), r48_canopy (normal z >= 0.78: crowns), r48_slope (0.5-0.78: scrub), r48_crest (convex, for spires
    and pines), r48_accent (clusters by buildings, links and falls), r48_shell (the far canopy mass's faces) and the
    factors r48_f (groves x concavity, thinned near the path), r48_f_crest. ``scope``: XY discs (lib.r48.scope)."""
    from sect.lib import r48 as R
    cw, nz, top, area = _range_faces(rng_obj)
    kd = density_paths(scene)
    above = cw[:, 2] > W.CLOUD_SEA_Z + 12.0
    cand = top & above & (nz > 0.5)
    t0 = time.time()
    path_d = _path_dist(kd, cw, cand)
    _log("r48 path distances for %d faces in %.1f s" % (int(cand.sum()), time.time() - t0))
    ex = r48_exclusion(rng_obj, cw, anchors, hold_views, star, path_d)
    insc = R.in_scope(scope, cw[:, :2])
    noise = W._VNoise(4801)
    grove = noise.fbm(cw[:, 0], cw[:, 1], 1.0 / GROVE_SCALE, 3, o=2)
    f_grove = GROVE_FLOOR + (1.0 - GROVE_FLOOR) * W._smooth(-0.35, 0.05, grove)
    lap = _grid_concavity(cw, top)
    f_conc = np.clip(1.0 + lap / CONCAVE_K, 0.4, 2.0)
    f = f_grove * f_conc * np.where(path_d < CANOPY_NEAR, CANOPY_NEAR_K, 1.0)
    f_crest = f_grove * np.clip(1.0 - lap / CONCAVE_K, 0.3, 2.5)
    shell_start = dict(cards=1e9, shell150=150.0, shell250=250.0, hull=250.0)[FOREST_MODE]
    tree_end = dict(cards=1e9, shell150=150.0, shell250=250.0, hull=CANOPY_NEAR)[FOREST_MODE]
    ok = cand & ~ex & insc
    canopy = ok & (nz >= 0.78) & (path_d < tree_end)
    slope = ok & (nz < 0.78) & (path_d < tree_end)
    crest = (canopy | slope) & (lap < -1.5)
    feats = [a[:2] for a in anchors.values()] + [p for p in (W.link_points()[::40] if len(W.link_points()) else [])]
    kdf = _kd2(np.array(feats, float))
    dfeat = np.array([kdf.find((float(x), float(y), 0.0))[2] for x, y in cw[:, :2]])
    clus = noise(cw[:, 0], cw[:, 1], 1.0 / 18.0, o=7)
    accent = canopy & (dfeat > 40.0) & (dfeat < 160.0) & (clus > 0.45)
    shell = ok & (path_d >= shell_start)
    hull = ok & (path_d >= tree_end) & (path_d < shell_start) & (FOREST_MODE == "hull")
    out = {}
    for name, m in (("r48_excl", ex), ("r48_canopy", canopy), ("r48_slope", slope), ("r48_crest", crest),
                    ("r48_accent", accent), ("r48_shell", shell), ("r48_hull", hull)):
        R.face_attr(rng_obj, name, m.astype(np.float32))
        out[name] = round(float(area[m].sum()))
    R.face_attr(rng_obj, "r48_f", np.where(canopy | slope, f, 0.0).astype(np.float32))
    R.face_attr(rng_obj, "r48_f_crest", np.where(crest, f_crest, 0.0).astype(np.float32))
    _log("r48 masks (m2)", json.dumps(out), "forest mode", FOREST_MODE)
    return dict(area_m2=out, path_d=path_d, cw=cw, nz=nz, top=top, lap=lap, f=f, scope=insc)


def r48_walls_out(rng_obj, hold_views, scope=None):
    """P-2: every old range scatter mask (OLD_RANGE_MASKS: forest, cliff, dense cliff, near-vertical walls, crown band,
    world.range.forest) zeroed outside the keep zones (in ``scope``); their trees there stay exactly where they are.
    The life.ledge trees and shrubs outside the keep zones are hidden (r48_hidden 'walls'). Returns counts."""
    from sect.lib import r48 as R
    cw, _nz, _top, _area = _range_faces(rng_obj)
    keep = R.keep_zone_mask(cw, hold_views, r=R.KEEP_R, pad=R.KEEP_PAD)
    insc = R.in_scope(scope, cw[:, :2])
    out = {}
    for name in OLD_RANGE_MASKS:
        v = R.face_attr(rng_obj, name)
        if v is None:
            continue
        bak = "r48_bak_" + name
        if R.face_attr(rng_obj, bak) is None:
            R.face_attr(rng_obj, bak, v)
        v0 = R.face_attr(rng_obj, bak)
        nv = np.where(insc & ~keep, 0.0, v0).astype(np.float32)
        R.face_attr(rng_obj, name, nv)
        out[name] = dict(faces_before=int((v0 > 0.5).sum()), faces_after=int((nv > 0.5).sum()))
    ledge = [o for o in bpy.data.objects if o.get("sect_life") == "ledge"]
    P = np.array([list(o.matrix_world.translation) for o in ledge]) if ledge else np.zeros((0, 3))
    hide = []
    if len(P):
        kz = R.keep_zone_mask(P, hold_views)
        sc = R.in_scope(scope, P[:, :2])
        hide = [o for o, k, s in zip(ledge, kz, sc) if s and not k]
    out["life_ledge_hidden"] = r48_hide(hide, "walls")
    out["life_ledge_kept"] = len(ledge) - len(hide)
    _log("r48 walls out", json.dumps(out))
    return out


def r48_walls_undo(rng_obj):
    from sect.lib import r48 as R
    n = 0
    for name in OLD_RANGE_MASKS:
        v0 = R.face_attr(rng_obj, "r48_bak_" + name)
        if v0 is not None:
            R.face_attr(rng_obj, name, v0)
            n += 1
    return dict(masks_restored=n, unhidden=r48_unhide("walls"))


def r48_range_canopy(rng_obj, coll):
    """P-3: the range's canopy as range-only scatters (nature.rscatter_on, density x the 'r48_f' factor): broadleaf
    crowns on the gentle ground, Masson spires and a few Huangshan pines on crests, scrub on 37-60 deg slopes,
    spring-green accents in clusters. Returns {scatter: name}."""
    made = {}
    specs = (
        ("scenery.r48.broadleaf", N.canopy_prototypes("broadleaf"), CANOPY_DENSITY, "r48_canopy", "r48_f",
         CANOPY_SCALE, 40.0, 4811),
        ("scenery.r48.spire", N.canopy_prototypes("spire"), SPIRE_DENSITY, "r48_crest", "r48_f_crest", SPIRE_SCALE,
         60.0, 4813),
        ("scenery.r48.pine", N.plant_prototypes("forest")[:6], PINE_DENSITY, "r48_crest", "r48_f_crest", PINE_SCALE,
         60.0, 4817),
        ("scenery.r48.scrub", N.canopy_prototypes("scrub"), SCRUB_DENSITY, "r48_slope", "r48_f", SCRUB_SCALE,
         61.0, 4819),
        ("scenery.r48.accent", N.canopy_prototypes("accent"), ACCENT_DENSITY, "r48_accent", "r48_f", CANOPY_SCALE,
         40.0, 4823),
    )
    for name, protos, dens, mask, fac, scale, slope, seed in specs:
        ob = N.rscatter_on(rng_obj, protos, density=dens, seed=seed, max_slope=math.radians(slope),
                           scale_range=scale, collection=coll, name=name, align=0.08, mask_attribute=mask,
                           factor_attribute=fac)
        ob[R48_TAG] = "canopy"
        made[name] = ob.name
    return made


def _pillars(scope=None):
    from sect.lib import r48 as R
    out = [o for o in bpy.data.objects if o.type == 'MESH' and "r48_peak" in o.keys() and "nature_top_z" in o.keys()]
    if scope is None:
        return out
    return [o for o in out if R.in_scope(scope, [tuple(o.matrix_world.translation)[:2]])[0]]


def r48_pillar_plants(coll, scope=None):
    """P-2 / P-3 on every round-48 pillar (world.peak.*): a broadleaf cap with spires on its rim, shrub clumps on the
    shelves, ferns and small shrubs in the crack strips (shared nature.scatter group, version 3: unchanged)."""
    n = dict(pillars=0)
    for ob in _pillars(scope):
        me = ob.data
        tr = float(ob.get("nature_top_radius", 10.0))
        ks = max(0.6, min(1.2, tr / 15.0))
        rim = me.attributes.get("r48_rim")
        if rim is None:
            c = np.empty(len(me.polygons) * 3)
            me.polygons.foreach_get("center", c)
            c = c.reshape(-1, 3)
            cap = np.zeros(len(me.polygons), np.float32)
            at = me.attributes.get("nature_cap")
            if at is not None:
                at.data.foreach_get("value", cap)
            rr = np.hypot(c[:, 0], c[:, 1])
            v = ((cap > 0.5) & (rr > 0.72 * tr)).astype(np.float32)
            a2 = me.attributes.new("r48_rim", 'FLOAT', 'FACE')
            a2.data.foreach_set("value", v)
            me.update()
        seed = int(ob.get("r48_peak", 0)) * 13 + 4900
        for nm, protos, dens, mask, scale, slope, align in (
                (".cap", N.canopy_prototypes("broadleaf"), CAP_DENSITY, "nature_cap", (0.55 * ks, 1.0 * ks), 50.0, 0.1),
                (".cap_spire", N.canopy_prototypes("spire"), CAP_RIM_SPIRE, "r48_rim", (0.5 * ks, 1.1 * ks), 60.0,
                 0.05),
                (".shelf", N.canopy_prototypes("shelf"), SHELF_DENSITY, "nature_shelf", (1.2, 2.4), 60.0, 0.2),
                (".crack", N.canopy_prototypes("fern"), CRACK_DENSITY, "nature_crack", (0.45, 0.9), 84.0, 0.5)):
            s = N.scatter_on(ob, protos, density=dens, seed=seed, max_slope=math.radians(slope), scale_range=scale,
                             collection=coll, name=ob.name + nm, align=align, mask_attribute=mask)
            s[R48_TAG] = "shelves"
            seed += 1
        n["pillars"] += 1
    _log("r48 pillar plants", json.dumps(n))
    return n


def r48_hero_pines(coll, hold_views, intent, scope=None, log=None):
    """Rule 7: per hold, intent's hero_pines lone Huangshan pines on the rims of the biggest pillars it shows (their
    tops in frame, HERO_PX wide or more, 120-700 m off), each on the rim point at the pillar's silhouette edge away
    from the frame's centre, leaning out over the drop, so it stands against sky or mist."""
    log = log or _log
    pillars = _pillars(scope)
    if not pillars:
        return 0
    used = set()
    made = 0
    dg = bpy.context.evaluated_depsgraph_get()
    for v in hold_views:
        want = int(intent["holds"].get(v.name, {}).get("hero_pines", 0))
        if not want:
            continue
        cands = []
        for ob in pillars:
            if ob.name in used:
                continue
            p = np.array(ob.matrix_world.translation)
            tz, tr = float(ob["nature_top_z"]), float(ob["nature_top_radius"])
            u, vv, d = v.project([(p[0], p[1], tz)])
            u, vv, d = float(u[0]), float(vv[0]), float(d[0])
            px = float(v.px(2 * tr, d))
            if 120.0 < d < 700.0 and 0.03 < u < 0.97 and 0.02 < vv < 0.9 and px >= HERO_PX:
                cands.append((px, ob, u, d))
        cands.sort(key=lambda c: -c[0])
        for px, ob, u, d in cands[:want]:
            p = np.array(ob.matrix_world.translation)
            tz, tr = float(ob["nature_top_z"]), float(ob["nature_top_radius"])
            dirv = p[:2] - v.pos[:2]
            th0 = math.atan2(dirv[1], dirv[0])
            side = 1.0 if u > 0.5 else -1.0                      # the edge away from the frame centre
            th = th0 - side * math.pi / 2.0
            r = U.rng(KEY, "hero", ob.name, v.name)
            th += r.uniform(-0.25, 0.25)
            q = (p[0] + math.cos(th) * (tr * 0.82), p[1] + math.sin(th) * (tr * 0.82))
            bvh = BVHTree.FromObject(ob, dg)
            mwi = ob.matrix_world.inverted()
            hit = bvh.ray_cast(mwi @ Vector((q[0], q[1], tz + 60.0)), Vector((0, 0, -1)), 200.0)[0]
            if hit is None:
                log("WARN hero pine: no cap under", ob.name, "for", v.name)
                continue
            z = (ob.matrix_world @ hit).z
            h = r.uniform(*HERO_PINE_H) * max(0.8, min(1.3, tr / 15.0))
            pn = N.pine(coll, height=h, seed=r.randrange(1, 10 ** 6), style="huangshan", lod="mid",
                        name="scenery.r48.hero_pine", location=(q[0], q[1], z - 0.3), lean_toward=th)
            pn[R48_TAG] = "hero"
            pn["r48_hold"] = v.name
            used.add(ob.name)
            made += 1
            log("hero pine", v.name, ob.name, "height %.1f at %s, %.0f px" % (h, [round(c, 1) for c in q], px))
    return made


def _tiles(xy):
    return np.floor((xy - np.array([W.EXTENT[0], W.EXTENT[2]])) / SHELL_TILE).astype(np.int64)


def r48_shell(rng_obj, coll, masks):
    """P-4: the far canopy as one lumpy mass per SHELL_TILE tile over the r48_shell faces: a SHELL_CELL grid, each
    cell on when most of its range faces are, lifted SHELL_LIFT with 4-10 m lumps, its outline sunk into the ground
    (so it grows out of the forest floor). Material nature_canopy_mass, baked like terrain. Returns objects."""
    cw, top = masks["cw"], masks["top"]
    m = R48_face(rng_obj, "r48_shell") > 0.5
    if not m.any():
        return []
    c = SHELL_CELL
    ix = np.floor((cw[:, 0] - W.EXTENT[0]) / c).astype(np.int64)
    iy = np.floor((cw[:, 1] - W.EXTENT[2]) / c).astype(np.int64)
    nx, ny = int((W.EXTENT[1] - W.EXTENT[0]) / c) + 2, int((W.EXTENT[3] - W.EXTENT[2]) / c) + 2
    on_n = np.zeros((ny, nx))
    all_n = np.zeros((ny, nx))
    zs = np.full((ny, nx), -1e9)
    t = np.nonzero(top)[0]
    np.add.at(all_n, (iy[t], ix[t]), 1.0)
    s = np.nonzero(m)[0]
    np.add.at(on_n, (iy[s], ix[s]), 1.0)
    np.maximum.at(zs, (iy[t], ix[t]), cw[t, 2])
    on = (on_n >= 0.6 * np.maximum(all_n, 1)) & (all_n > 0)
    # node heights: the highest ground of the cells round it; lift where all 4 cells are on, sunk at the outline
    pad = np.pad(on, 1)
    zp = np.pad(zs, 1, constant_values=-1e9)
    n_on = pad[:-1, :-1].astype(int) + pad[1:, :-1] + pad[:-1, 1:] + pad[1:, 1:]
    zn = np.maximum.reduce([zp[:-1, :-1], zp[1:, :-1], zp[:-1, 1:], zp[1:, 1:]])
    gx = W.EXTENT[0] + c * np.arange(nx + 1)
    gy = W.EXTENT[2] + c * np.arange(ny + 1)
    GX, GY = np.meshgrid(gx, gy)
    noise = W._VNoise(4837)
    lump = 0.5 + 0.5 * noise.fbm(GX, GY, 1.0 / 7.0, 2, o=3)
    lift = SHELL_LIFT[0] + (SHELL_LIFT[1] - SHELL_LIFT[0]) * lump
    Zn = np.where(n_on == 4, zn + lift, zn - 1.5)
    cells = np.argwhere(on)
    tiles = {}
    for (j, i) in cells:
        tk = (int(i * c // SHELL_TILE), int(j * c // SHELL_TILE))
        tiles.setdefault(tk, []).append((j, i))
    out = []
    for tk, cl in sorted(tiles.items()):
        vid = {}
        verts, faces = [], []

        def vtx(jj, ii):
            if (jj, ii) not in vid:
                vid[(jj, ii)] = len(verts)
                verts.append((float(GX[jj, ii]), float(GY[jj, ii]), float(Zn[jj, ii])))
            return vid[(jj, ii)]
        for (j, i) in cl:
            faces.append((vtx(j, i), vtx(j, i + 1), vtx(j + 1, i + 1), vtx(j + 1, i)))
        ob = U.mesh_from_pydata("world.canopy_shell", verts, faces, coll, materials=["nature_canopy_mass"],
                                smooth=True)
        ob[R48_TAG] = "forest"
        ob["r48_tile"] = list(tk)
        out.append(ob)
    _log("r48 shell: %d cells in %d tiles (%d triangles)" % (len(cells), len(out), 2 * len(cells)))
    return out


def R48_face(ob, name):
    from sect.lib import r48 as R
    v = R.face_attr(ob, name)
    return np.zeros(len(ob.data.polygons), np.float32) if v is None else v


def r48_hulls(rng_obj, coll, masks):
    """P-4 (FOREST_MODE 'hull'): low-poly crown clumps (nature.hull_clumps_bm, 150-400 triangles each) every
    HULL_STEP m over the r48_hull faces (CANOPY_NEAR to 250 m from the path), in groves, each at its own ground
    height; one object per SHELL_TILE tile, material nature_canopy_mass. Returns objects."""
    m = R48_face(rng_obj, "r48_hull") > 0.5
    if not m.any():
        return []
    cw = masks["cw"]
    f = masks["f"]
    r = U.rng(KEY, "hulls")
    key = np.floor(cw[m, :2] / HULL_STEP).astype(np.int64)
    idx = np.nonzero(m)[0]
    _u, first = np.unique(key[:, 0] * 100003 + key[:, 1], return_index=True)
    clumps = []
    for i in idx[first]:
        if r.random() > min(1.0, 0.35 + 0.5 * float(f[i])):
            continue
        x, y, z = cw[i]
        clumps.append((float(x) + r.uniform(-4, 4), float(y) + r.uniform(-4, 4), float(z) - 0.6,
                       r.uniform(*HULL_R)))
    tiles = {}
    for cl in clumps:
        tk = tuple(_tiles(np.array(cl[:2]))[:2])
        tiles.setdefault(tk, []).append(cl)
    out = []
    for k, (tk, cl) in enumerate(sorted(tiles.items())):
        bm = N.hull_clumps_bm(cl, seed=k)
        ob = U.mesh_from_bmesh("world.canopy_hull", bm, coll, materials=["nature_canopy_mass"], smooth=None)
        ob[R48_TAG] = "forest"
        out.append(ob)
    _log("r48 hulls: %d clumps in %d tiles" % (len(clumps), len(out)))
    return out


def r48_island_caps(kd, prefixes=("scenery.island", "world.islet"), keep=None):
    """C (rule 8): every kept floating island and islet gets a canopy cap instead of its crowd of pines: the pines
    the density pass packed on it (DENSITY_TAG island / islet) and build_islands' top pines are hidden (r48_hidden
    'isles'), and a broadleaf scatter on its top (its 'nature_veg' mask) with spires and 1-3 rim pines leaning out
    is added. ``keep``: rock names to cap (None: all). Returns counts."""
    n = dict(rocks=0, hidden=0)
    for prefix in prefixes:
        for rock in _rocks(prefix):
            if rock.name == ICEFIRE_ISLAND or (keep is not None and rock.name not in keep):
                continue
            if rock.data.attributes.get("nature_veg") is None:
                continue
            olds = [o for o in rock.children if o.instance_type == 'COLLECTION' and
                    (o.get(DENSITY_TAG) or o.name.startswith(rock.name + ".pine"))]
            olds += [o for o in island_companions(rock) if o.name.startswith(prefix + ".pine")]
            n["hidden"] += r48_hide(olds, "isles")
            shp = _rock_top(rock)
            size = 2.0 * (math.sqrt(shp["area"] / math.pi) + 0.6) if shp else 10.0
            ks = max(0.35, min(1.0, size / 30.0))
            coll = rock.users_collection[0] if rock.users_collection else None
            for nm, protos, dens, scale, seed in ((".r48_cap", N.canopy_prototypes("broadleaf"), 0.03,
                                                  (0.55 * ks, 1.0 * ks), 11),
                                                 (".r48_cap_spire", N.canopy_prototypes("spire"), 0.004,
                                                  (0.5 * ks, 1.1 * ks), 13)):
                s = N.scatter_on(rock, protos, density=dens, seed=U.seed_from(rock.name, seed) % 100000,
                                 max_slope=math.pi if N._top_down(rock) else math.radians(35), scale_range=scale,
                                 collection=coll, name=rock.name + nm, align=0.0, mask_attribute="nature_veg",
                                 z_range=(-0.5, 1e4))
                s[R48_TAG] = "isles"
            n["rocks"] += 1
    _log("r48 island caps", json.dumps(n))
    return n


# ---- round 48, C: islands and islets, falls, horizon -------------------------------------------------------------

R48_FALL_W = (0.3, 0.5)        # island fall width x island size (was 0.16-0.26)
R48_RANGE_FALL_W = (12.0, 22.0)


def _tree_box(obs):
    pts = []
    for x in obs:
        if x.type in ('MESH', 'CURVE'):
            pts += [list(x.matrix_world @ Vector(c)) for c in x.bound_box]
    return np.array(pts) if pts else None


def r48_isle_records():
    """(rocks, records) of every floating island and islet: name, centre, size (largest horizontal extent of the rock
    and its children), kind ('island' / 'islet'), protected (Ice-Fire Island)."""
    rocks, recs = [], []
    for prefix, kind in (("scenery.island", "island"), ("world.islet", "islet")):
        for rock in _rocks(prefix):
            if rock.hide_render:
                continue
            bb = _tree_box([rock] + [c for c in rock.children_recursive if c.type == 'MESH'])
            if bb is None:
                continue
            lo, hi = bb.min(0), bb.max(0)
            rocks.append(rock)
            recs.append(dict(name=rock.name, c=((lo + hi) / 2).tolist(), size=float(max(hi[0] - lo[0], hi[1] - lo[1])),
                             kind=kind, protected=rock.name == ICEFIRE_ISLAND))
    return rocks, recs


def r48_isles(intent, hold_views, star, log=None):
    """Rule 8 / intent 3.3.4: cull the islands with lib.compose.cull_islands over the hold views and chase.cam every
    flight_default.every frames (plus the listed flights); the culled rocks, their children and companions are hidden
    (r48_hidden 'isles': the export and the bake skip them; patch_r48_isles UNDO=1 shows them again). Returns
    dict(kept, gone {name: reason}, counts)."""
    from sect.lib import compose as C
    from sect.lib import r48 as R
    log = log or _log
    rocks, recs = r48_isle_records()
    fv = R.flight_sample(int(intent.get("flight_default", {}).get("every", 6)))
    listed = [v for v in R.views(intent, flights=True) if v.name not in intent["holds"]]
    names = {v.name for v in listed}
    views = list(hold_views) + listed + [v for v in fv if v.name not in names]
    gone, vis = C.cull_islands(recs, views, intent, star, log=log)
    hid = 0
    for i in gone:
        rock = rocks[i]
        objs = [rock] + list(rock.children_recursive)
        for comp in island_companions(rock):
            objs += [comp] + list(comp.children_recursive)
        hid += r48_hide(objs, "isles")
    kept = [r["name"] for i, r in enumerate(recs) if i not in gone]
    per_hold = {v.name: sum(1 for x in vis.get(v.name, []) if x[0] not in gone) for v in hold_views}
    worst = max((sum(1 for x in vis.get(v.name, []) if x[0] not in gone), v.name) for v in views)
    log("r48 isles: kept %d (islands %d, islets %d), hid %d objects; per hold %s; most in one sampled frame: %d (%s)"
        % (len(kept), sum(1 for i, r in enumerate(recs) if i not in gone and r["kind"] == "island"),
           sum(1 for i, r in enumerate(recs) if i not in gone and r["kind"] == "islet"), hid, json.dumps(per_hold),
           worst[0], worst[1]))
    return dict(kept=kept, gone={recs[i]["name"]: why for i, why in gone.items()}, per_hold=per_hold,
                worst_frame=list(worst))


def r48_unhide_isles():
    return r48_unhide("isles")


def _fall_roots():
    """[(root, kind, island rock name or None)] of the range falls (world.waterfall*, scenery.fall*) and the island
    falls (scenery.island.fall*), visible ones only."""
    out = []
    for o in bpy.data.objects:
        if o.type != 'EMPTY' or o.parent is not None or o.hide_render or o.get(R48_TAG):
            continue
        nm = o.name
        if re.match(r"^world\.waterfall(\.\d{3})?$", nm) or re.match(r"^scenery\.fall(\.\d{3})?$", nm):
            out.append((o, "range", None))
        elif re.match(r"^scenery\.island\.fall(\.\d{3})?$", nm):
            out.append((o, "island", None))
    rocks = _rocks("scenery.island")
    for i, (o, kind, _r) in enumerate(out):
        if kind != "island":
            continue
        p = o.matrix_world.translation
        best = min(rocks, key=lambda r: (r.matrix_world.translation - p).length) if rocks else None
        out[i] = (o, kind, best.name if best is not None else None)
    return out


def r48_falls(intent, hold_views, kept_islands, log=None):
    """Rule 9 / intent 3.3.7: falls culled with lib.compose.cull_falls (none in the arena, mission, library, steles
    and scroll holds; about one kept island in four keeps its fall; Ice-Fire Island's stays as it is). Every fall
    that stays is rebuilt shorter and arcing (nature.waterfall, world.FALL_MAX_H, FALL_EXIT, FALL_SPREAD; island falls
    R48_FALL_W x the island) with its spray chain (world.fall_mist); the old ones are hidden (r48_hidden 'falls').
    Returns counts."""
    from sect.lib import compose as C
    from sect.lib import r48 as R
    log = log or _log
    roots = _fall_roots()
    ice = bpy.data.objects.get(ICEFIRE_ISLAND)
    ice_comp = {o.name for o in island_companions(ice)} if ice is not None else set()
    recs = []
    for o, kind, rock in roots:
        lip = np.array(o.matrix_world.translation)
        ft = o.get("foot")
        foot = np.array(o.matrix_world @ Vector(tuple(ft))) if ft is not None else lip - np.array([0.0, 0.0, 150.0])
        recs.append(dict(name=o.name, lip=lip.tolist(), foot=foot.tolist(), island=rock,
                         location=o.name in ice_comp, kind=kind))
    views = list(hold_views) + [v for v in R.views(intent, flights=True) if v.name not in intent["holds"]]
    gone, keep = C.cull_falls(recs, views, intent, kept_islands, log=log)
    coll = U.get_collection("world.water")
    sizes = {x["name"]: x["size"] for x in r48_isle_records()[1]}
    made = hidden = 0
    for i, (o, kind, rock) in enumerate(roots):
        rec = recs[i]
        if rec["location"]:
            continue
        hidden += r48_hide([o] + list(o.children_recursive), "falls")
        if i in gone:
            continue
        r = U.rng(KEY, "r48_fall", o.name)
        lip = rec["lip"]
        yaw = float(o.matrix_world.to_euler().z)
        h = min(W.FALL_MAX_H, max(40.0, lip[2] - rec["foot"][2]))
        if kind == "island" and rock is not None:
            size = sizes.get(rock, 20.0)
            w = size * r.uniform(*R48_FALL_W)
        else:
            w = r.uniform(*R48_RANGE_FALL_W)
        fr = N.waterfall(coll, height=h, width=w, seed=U.seed_from(o.name) % 100000, sheets=2, mist=True,
                         foam=False, name=o.name.split(".")[0] + ".r48_fall", location=tuple(lip),
                         rotation=(0.0, 0.0, yaw), exit_speed=r.uniform(*W.FALL_EXIT),
                         spread=r.uniform(*W.FALL_SPREAD))
        fr[R48_TAG] = "falls"
        for c in fr.children_recursive:
            c[R48_TAG] = "falls"
        for p in W.fall_mist(coll, lip, yaw, h, w, U.seed_from(o.name, "mist") % 100000):
            p[R48_TAG] = "falls"
        made += 1
    log("r48 falls: %d rebuilt (shorter, arcing, spray chains), %d gone, %d objects hidden, Ice-Fire's kept"
        % (made, len(gone), hidden))
    return dict(rebuilt=made, gone={recs[i]["name"]: why for i, why in gone.items()}, hidden=hidden)


def r48_horizon(scene, log=None):
    """D9: the 14 backdrop massifs hidden (r48_hidden 'horizon'), world.BACKDROP_R48's pillar families and mesas
    built (tagged 'horizon')."""
    log = log or _log
    old = [o for o in bpy.data.objects if o.name.startswith("world.backdrop") and not o.get(R48_TAG)]
    hid = r48_hide(old + [c for o in old for c in o.children_recursive], "horizon")
    r48_remove(("horizon",))
    coll = U.get_collection("world.range", scene=scene)
    made = W.build_backdrop(coll)
    for o in made:
        o[R48_TAG] = "horizon"
    log("r48 horizon: %d massifs hidden, %d pillars and mesas built" % (hid, len(made)))
    return dict(hidden=hid, built=len(made))


def build(scene):
    anchors = {k: tuple(v)[:4] for k, v in W.ANCHORS.items()}
    coll = U.get_collection(KEY, scene=scene)
    kd, pos = flight_paths(scene)
    build_forest(coll, kd, anchors)
    build_islands(coll, kd, pos, anchors)
    nudge_islands()
    build_range_falls(coll, kd, anchors)
    build_density(scene, coll, anchors)
    __import__("sect.life", fromlist=["build"]).build(scene)
    turn_icefire()
    build_icefire()
    build_r48(scene)
    _log("triangles", U.evaluated_triangle_count(coll))


def build_r48(scene, parts=("isles", "walls", "canopy", "shelves", "hero", "forest"), scope=None):
    """Round 48 on a fresh build (sect/patch_r48_isles.py and patch_r48_green.py do the same on a finished scene):
    the islands and falls culled to the holds' intent (lib.compose), canopy caps on the kept ones, the old range
    scatters zeroed outside the keep zones, the broadleaf canopy, shelf / crack / cap plants on the pillars, hero
    pines, and the far canopy mass (FOREST_MODE). Needs chase.cam (the hold views); without it, it is skipped."""
    from sect.lib import compose as C
    from sect.lib import r48 as R
    if bpy.data.objects.get(R.CAMERA) is None or bpy.data.objects[R.CAMERA].animation_data is None:
        _log("WARN round 48 skipped: no keyed", R.CAMERA, "(run it again after chase.py: patch_r48_green, _isles)")
        return None
    intent = C.load_intent()
    an = R.anchors()
    hv = R.views(intent, flights=False)
    star = R.star_boxes(hv, an)
    rng_obj = bpy.data.objects["world.range"]
    coll = r48_collection(scene)
    out = {}
    if "isles" in parts:
        kd = density_paths(scene)
        out["isles"] = r48_isles(intent, hv, star)
        out["caps"] = r48_island_caps(kd, keep=set(out["isles"]["kept"]))
        out["falls"] = r48_falls(intent, hv, set(out["isles"]["kept"]))
        out["horizon"] = r48_horizon(scene)
    if "walls" in parts:
        out["walls"] = r48_walls_out(rng_obj, hv, scope)
    masks = None
    if any(p in parts for p in ("canopy", "forest")):
        masks = r48_canopy_masks(rng_obj, scene, an, hv, star, scope)
    if "canopy" in parts:
        r48_remove(("canopy",))
        out["canopy"] = r48_range_canopy(rng_obj, coll)
    if "shelves" in parts:
        r48_remove(("shelves",))
        out["shelves"] = r48_pillar_plants(coll, scope)
    if "hero" in parts:
        r48_remove(("hero",))
        out["hero"] = r48_hero_pines(coll, hv, intent, scope)
    if "forest" in parts:
        r48_remove(("forest",))
        wc = U.get_collection("world.range", scene=scene)
        out["forest"] = len(r48_shell(rng_obj, wc, masks)) + len(r48_hulls(rng_obj, wc, masks))
    _log("round 48", json.dumps(out, default=str))
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", default=os.path.join(ROOT, "out", "sect_scenic.blend"))
    a = ap.parse_args(argv)
    build(bpy.context.scene)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.blend))
    _log("saved", a.blend)


if __name__ == "__main__":
    main()
