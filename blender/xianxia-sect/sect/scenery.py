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
# Ice-Fire Island 冰火島 (Heaven Sword and Dragon Saber, round 7): the island the flight sees largest made half glacier,
# half volcano (sect/lib/icefire_props.py). island.009, the 70 m island with the waterfall at the library hold (772:
# 236 x 298 px of a 1600 x 900 frame, 90 % unoccluded; the most on-screen area of any island over the whole path). Its
# rock-local ICE_AZ puts the ice on the hold's left (the sunlit side, with the waterfall as meltwater) and the basalt
# and lava on its right. Runs after the density and life passes (it removes the island's plants);
# sect/patch_r7_icefire.py does the same on a finished scene.
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
        N.floating_rock(coll, size=size, seed=900 + k, vegetation=True, roots=True,
                        pine_on_top=size < 30.0, name="scenery.island", location=tuple(c),
                        rotation=r.uniform(0, 2 * math.pi))
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
    """Make ICEFIRE_ISLAND Ice-Fire Island (sect/lib/icefire_props.py). Idempotent."""
    from sect.lib import icefire_props as IF
    rock = bpy.data.objects.get(name or ICEFIRE_ISLAND)
    if rock is None:
        _log("WARN icefire: no", name or ICEFIRE_ISLAND)
        return None
    return IF.build(rock, log=_log)


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
    build_icefire()
    _log("triangles", U.evaluated_triangle_count(coll))


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
