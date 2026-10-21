"""Ice-Fire Island 冰火島 (Heaven Sword and Dragon Saber): one of the scenery's floating islands made half glacier, half
volcano. Zhang Cuishan, Yin Susu and Xie Xun drift to it through the polar sea, and Zhang Wuji is born there.

    from sect.lib import icefire_props as IF
    IF.build(bpy.data.objects["scenery.island.009"])    # idempotent: removes its own earlier output first

Everything is built in the rock's own frame (a nature.floating_rock: flat top at z ~ 0, inverted craggy cone below),
as children of the rock with identity local transforms, so their object coordinates are the rock's:
- the island's plants go: its crown / rim pines, ledge-plant scatter and hanging roots (children), and the top pines,
  blossoms and life-pass peaches standing on it (top-level companions). Its waterfall stays: glacier meltwater.
- the rock's two material slots become icefire_rock (cone) and icefire_ground (top): one object-space split (ICE_AZ,
  seam()) into glacier ice (white to deep blue with depth, strata, crevasse lines, snow on up-facing faces) and black
  columnar basalt (ash on up-facing faces), with a wavy, jagged seam down the middle of the underside
- <rock>.icefire_glacier: a glacier cap over the ice half of the top, overhanging the rim (the waterfall now pours from
  under its edge), a snout cliff facing the volcano and clusters of ice shards (seracs) along its rim and snout
- <rock>.icefire_icicles: icicles under the cap's overhang; <rock>.icefire_stalactites: ice stalactites under the ice
  half of the cone
- <rock>.icefire_volcano: a volcanic cone on the basalt half, a molten lava pool in its crater (slot 1: molten)
- <rock>.icefire_lava_flow: two lava streams from crater notches, one down to the glacier snout, one to the rim
- <rock>.icefire_lava_veins: glowing fissures down the basalt underside, one continuing the second stream over the rim
- world.cloud.icefire_steam(.NNN): a thin steam plume where the lava meets the ice (nature.cloud_puff domains; the web
  draws world.cloud.* as soft cloud sprites, export_web.py clouds)
Every mesh is closed (bake_web.fix_normals points closed pieces outward) and touches its support: the icicles and
stalactites start inside the cap or rock, the lava ribbons are slabs sunk into the surface they lie on, the cap and the
cone sit 0.6-1.2 m into the top. Each object is tagged obj[TAG] = part; the lava pieces carry obj['glow'].
"""
import math
import random

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from . import materials as M
from . import nature as N
from . import util as U

KEY = "icefire"
TAG = "sect_icefire"                 # obj[TAG] = part name on every object this module makes
STEAM_PREFIX = "world.cloud.icefire_steam"
PARTS = ("glacier", "icicles", "stalactites", "volcano", "lava_flow", "lava_veins")
ICE_AZ = 168.0                       # rock-local azimuth (deg) of the ice half's centre; the basalt faces ICE_AZ-180.
#                                      The library hold (772) sees the rock from azimuth VIEW_AZ, 18 deg under it: the
#                                      seam's front then sits ~30 deg right of the view line, clear of the waterfall
#                                      (azimuth -147 +- 22), so the hold sees ice left and right of the fall, then
#                                      the basalt face beyond the seam
VIEW_AZ = -130.0                     # rock-local azimuth of the hold camera (probe: -128..-134 over frames 705-849)
# the seam: d - sum(A sin(ka a + kz z + ph)) = 0, d along the ice direction, a along the seam (toward ICE_AZ - 270)
SEAM_WAVES = ((2.4, 0.09, 0.06, 0.8), (1.0, 0.23, 0.17, 2.3), (0.7, 0.52, 0.37, 4.1))
SEAM_JAG = 1.1                       # m: the shader's extra noise on the seam (geometry keeps SEAM_CLEAR off it)
SEAM_CLEAR = 2.8                     # m: icicles / lava veins keep this far on their own side of the seam
GLACIER = dict(snout=4.5, height=(4.5, 7.5), snout_h=3.4, edge_h=(2.6, 3.8), overhang=(1.3, 2.7), droop=(1.2, 2.6),
               sink=0.7, na=64, nt=18, seracs=19, snout_seracs=6)
ICICLES = dict(step=0.85, skip=0.1, short=(1.4, 3.6), long=(4.5, 10.0), long_share=0.32, sides=6, fall_margin=3.0)
STALACTITES = dict(count=34, spacing=3.4, length=(5.0, 18.0), radius=(0.45, 1.3), min_down=0.4, sides=6)
VOLCANO = dict(d=-13.0, a=8.5, base_r=12.0, top_r=3.9, height=17.0, crater=3.4, pool_r=2.3, segs=56, rings=15,
               sink=1.2, notch_flow=1.6, notch_rim=1.0)
STEAM_A = 12.0                       # m along the seam (toward the hold camera) where the first stream meets the snout
STEAM = dict(puffs=16, wisps=3, drift_az=105.0, size=(2.6, 0.95), overlap=0.42, density=(0.6, 0.03))
# the crack network on the basalt underside: mains from under the rim (rock-local azimuths, deg; plus one under the
# second lava stream), forks off them at 35-75 deg, short cracks off the forks, a few cross cracks along the strata
VEINS = dict(mains=(-90.0, -72.0, -38.0, -14.0, 20.0), length=(30.0, 52.0), width=(1.3, 1.9), step=0.9,
             mid=((-88.0, -24.0), (-66.0, -36.0), (-30.0, -20.0)), forks=(2, 4), fork_len=(5.0, 13.0), fork_w=0.5,
             twigs=(0, 2), twig_len=(2.5, 5.0), twig_w=0.32, cross=3, sigma=22.0,
             tri_budget=5600)                # a vein of n sections is 8n - 4 triangles; veins past this are dropped
LAVA_GLOW = 1.6                      # obj['glow'] on the lava pieces (molten: emission 7 x glow x heat^1.5)
LIFT, SINK = 0.12, 0.4               # lava slabs: top this far over the surface, keel this far under it
TRI_CAP = 6000                       # per piece: bake_web's island LOD floor keeps at most ISLAND_FLOOR_HI triangles


def _log(*a):
    print("ICEFIRE", *a, flush=True)


def _dirs(az=ICE_AZ):
    t = math.radians(az)
    return (math.cos(t), math.sin(t)), (-math.sin(t), math.cos(t))


EI, EB = _dirs()


def seam(x, y, z):
    """Signed distance-like seam coordinate at rock-local (x, y, z): > 0 on the ice half, < 0 on the basalt half (the
    shader's split without its SEAM_JAG noise)."""
    d = x * EI[0] + y * EI[1]
    a = x * EB[0] + y * EB[1]
    return d - sum(A * math.sin(ka * a + kz * z + ph) for A, ka, kz, ph in SEAM_WAVES)


def seam_d0(a, z=0.0):
    """d (along EI) of the seam at seam coordinate a and height z."""
    return sum(A * math.sin(ka * a + kz * z + ph) for A, ka, kz, ph in SEAM_WAVES)


def to_xy(a, d):
    return (a * EB[0] + d * EI[0], a * EB[1] + d * EI[1])


# ---- materials ----------------------------------------------------------------------------------

def _icefire_surface(g, mode="split", top=False, ice_az=ICE_AZ):
    """Glacier ice / black basalt in rock-local object coordinates. mode 'split' (the island body: seam()), 'ice'
    (cap, icicles, seracs) or 'basalt' (the volcano). top: the island's top faces (snow / cinder ground)."""
    ei, eb = _dirs(ice_az)
    p = g.coord("object")
    px, py, pz = g.sep(p)
    nz = g.sep(g.geometry("Normal"))[2]
    fine = g.noise(p, 0.55, detail=4.0, roughness=0.6)
    # ice: pale blue-white at the top to deep blue far under, wavy strata, long vertical melt streaks (deeper blue
    # runs), snow on what faces up
    depth = g.maprange(pz, 1.0, -58.0, 0.0, 1.0)
    strata = g.wave(p, scale=0.09, distortion=4.0, detail=3.0, kind='BANDS', direction='Z')
    streak = g.noise(g.mapping(p, scale=(1.0, 1.0, 0.07)), 0.45, detail=3.0, roughness=0.55)
    t_ice = g.add(g.mul(depth, 0.8), g.mul(g.math('SUBTRACT', strata, 0.5), 0.22))
    t_ice = g.add(t_ice, g.mul(g.math('SUBTRACT', streak, 0.5), 0.5))
    t_ice = g.add(t_ice, g.mul(g.math('SUBTRACT', fine, 0.5), 0.12))
    ice = g.ramp(t_ice, [(0.0, "#e6f2f8"), (0.25, "#cbe6f2"), (0.5, "#a0d0e6"), (0.75, "#6db4d6"),
                         (1.0, "#468fbe")])
    breakup = g.smooth(g.noise(p, 0.3, detail=3.0), 0.38, 0.58)
    snow_k = g.mul(g.smooth(nz, 0.05 if top else 0.3, 0.35 if top else 0.6), g.mixf(0.6, 1.0, breakup))
    ice = g.mix(ice, "#f2f7fa", snow_k)
    ice_h = g.add(g.mul(strata, 0.5), g.mul(streak, 0.8))
    # basalt: dark columns (voronoi cells stretched along z), black joints, rusty scoria patches, grey ash on top
    pc = g.mapping(p, scale=(1.0, 1.0, 0.22))
    cellv = g.sep(g.voronoi(pc, 0.55, out="Color"))[0]
    edge = g.voronoi(pc, 0.55, feature='DISTANCE_TO_EDGE')
    joint = g.math('SUBTRACT', 1.0, g.smooth(edge, 0.0, 0.05))
    bas = g.ramp(g.add(g.mul(cellv, 0.6), g.mul(fine, 0.4)), [(0.0, "#181514"), (0.5, "#28231f"), (1.0, "#3b3430")])
    bas = g.mix(bas, "#0a0807", g.mul(joint, 0.75))
    warm = g.smooth(g.noise(p, 0.05, detail=2.0), 0.56, 0.74)
    bas = g.mix(bas, "#3d1a0f", g.mul(warm, 0.55))
    ash_k = g.mul(g.smooth(nz, 0.1 if top else 0.4, 0.45 if top else 0.75), g.smooth(g.noise(p, 0.35), 0.3, 0.6))
    bas = g.mix(bas, "#4b4744" if not top else "#3a3633", g.mul(ash_k, 0.85))
    if mode == "split":
        d = g.add(g.mul(px, ei[0]), g.mul(py, ei[1]))
        a = g.add(g.mul(px, eb[0]), g.mul(py, eb[1]))
        w = None
        for A, ka, kz, ph in SEAM_WAVES:
            arg = g.add(g.add(g.mul(a, ka), g.mul(pz, kz)), ph)
            term = g.mul(g.math('SINE', arg), A)
            w = term if w is None else g.add(w, term)
        jag = g.mul(g.math('SUBTRACT', g.noise(p, 0.2, detail=4.0, roughness=0.65), 0.5), 2.0 * SEAM_JAG)
        s = g.add(g.math('SUBTRACT', d, w), jag)
        f = g.smooth(s, -0.3, 0.3)
        # the seam itself: soot-grey ice on its ice side, rime frost (frozen steam) speckling the basalt side
        soot = g.math('SUBTRACT', 1.0, g.smooth(s, 0.2, 2.4))
        ice = g.mix(ice, "#7d8790", g.mul(soot, 0.55))
        frost = g.mul(g.math('SUBTRACT', 1.0, g.smooth(g.math('MULTIPLY', s, -1.0), 0.3, 3.2)),
                      g.smooth(g.noise(p, 0.8, detail=3.0), 0.5, 0.62))
        bas = g.mix(bas, "#c8d5dc", g.mul(frost, 0.85))
    else:
        f = 1.0 if mode == "ice" else 0.0
    col = g.mix(bas, ice, f) if mode == "split" else (ice if mode == "ice" else bas)
    rough = g.mixf(0.85, 0.3, f) if mode == "split" else (0.3 if mode == "ice" else 0.85)
    hgt = g.mixf(g.mul(joint, -1.0), ice_h, f) if mode == "split" else (
        ice_h if mode == "ice" else g.mul(joint, -1.0))
    g.viewport("#cfe6f1" if mode == "ice" else ("#1c1918" if mode == "basalt" else "#7f8a90"), 0.5)
    g.output(g.principled(base_color=col, roughness=rough, normal=g.bump(hgt, 0.35, 0.08)))


M.register("icefire_rock", _icefire_surface, mode="split", top=False)
M.register("icefire_ground", _icefire_surface, mode="split", top=True)
M.register("icefire_ice", _icefire_surface, mode="ice", top=False)
M.register("icefire_basalt", _icefire_surface, mode="basalt", top=False)
MATERIALS = ("icefire_rock", "icefire_ground", "icefire_ice", "icefire_basalt")


# ---- the rock ---------------------------------------------------------------------------------------

RIM_BINS = 180


class Rock:
    """The rock's local geometry: BVH, rim radius and height per azimuth, top height lookups."""

    def __init__(self, ob):
        me = ob.data
        n = len(me.vertices)
        co = np.empty(n * 3)
        me.vertices.foreach_get("co", co)
        self.co = co.reshape(-1, 3)
        self.polys = [list(p.vertices) for p in me.polygons]
        self.bvh = BVHTree.FromPolygons(self.co.tolist(), self.polys)
        up = self.co[self.co[:, 2] > -1.0]
        th = np.arctan2(up[:, 1], up[:, 0])
        b = np.floor((th + math.pi) / (2 * math.pi) * RIM_BINS).astype(int) % RIM_BINS
        r = np.hypot(up[:, 0], up[:, 1])
        rim = np.zeros(RIM_BINS)
        np.maximum.at(rim, b, r)
        # max over each bin and its neighbours: a spoke of top-ring vertices on a bin edge splits across two bins
        # (floating point), and a bin holding only its inner-ring vertex read the rim at 14 m instead of 31 m
        rim = np.maximum(rim, np.maximum(np.roll(rim, 1), np.roll(rim, -1)))
        cen = (np.arange(RIM_BINS) + 0.5) * (2 * math.pi / RIM_BINS) - math.pi
        ok = rim > 0
        self.rim = np.interp(cen, cen[ok], rim[ok], period=2 * math.pi)
        self.cen = cen
        self.ztop = float(self.co[:, 2].max())
        self.zlow = float(self.co[:, 2].min())
        self.rmax = float(self.rim.max())

    def rim_at(self, th):
        return float(np.interp(math.atan2(math.sin(th), math.cos(th)), self.cen, self.rim, period=2 * math.pi))

    def top_z(self, x, y):
        hit = self.bvh.ray_cast(Vector((x, y, self.ztop + 20.0)), Vector((0, 0, -1)), 60.0)[0]
        return None if hit is None else hit.z

    def cone_hit(self, th, z):
        """Outer surface point and outward normal at azimuth th, height z (a ray from outside toward the axis)."""
        o = Vector((math.cos(th) * (self.rmax + 30.0), math.sin(th) * (self.rmax + 30.0), z))
        hit, nrm, _i, _d = self.bvh.ray_cast(o, Vector((-math.cos(th), -math.sin(th), 0.0)), self.rmax + 60.0)
        if hit is None:
            return None, None
        if nrm.dot(o - hit) < 0:
            nrm = -nrm
        return hit, nrm


def _support_bvh(meshes):
    """One BVH over several (verts, polys) lists in the rock's frame."""
    vs, ps = [], []
    for co, polys in meshes:
        off = len(vs)
        vs.extend(co)
        ps.extend([[i + off for i in p] for p in polys])
    return BVHTree.FromPolygons(vs, ps)


def _mesh_lists(ob):
    me = ob.data
    return [tuple(v.co) for v in me.vertices], [list(p.vertices) for p in me.polygons]


# ---- removal --------------------------------------------------------------------------------------

VEG_WORDS = ("pine", "blossom", "peach", "shrub", "bamboo", "willow", "grass", "lotus")


def our_objects(rock):
    """This module's objects on ``rock`` (tagged children) and the steam puffs."""
    out = [o for o in rock.children_recursive if o.get(TAG)]
    out += [o for o in bpy.data.objects if o.name.startswith(STEAM_PREFIX) and o not in out]
    return out


def _plant_children(rock):
    out = []
    for o in rock.children:
        if o.get(TAG):
            continue
        ic = o.instance_collection
        if o.name in (rock.name + ".plants", rock.name + ".roots", rock.name + ".pine"):
            out.append(o)
        elif ic is not None and any(w in ic.name for w in VEG_WORDS):
            out.append(o)
    return out


def _plant_companions(rock, R=None):
    """Top-level plants standing on the rock's top: build_islands' top pines and blossoms, the life pass's peaches
    (origin inside the top's rim + 1.5 m, within 3 m of the top's height). Falls and anything else stay."""
    R = R or Rock(rock)
    Mi = rock.matrix_world.inverted()
    out = []
    for o in bpy.data.objects:
        if o.parent is not None or o == rock:
            continue
        if not (o.name.startswith("scenery.island.") or o.name.startswith("life.")):
            continue
        if ".fall" in o.name:
            continue
        ic = o.instance_collection
        veg = (ic is not None and any(w in ic.name for w in VEG_WORDS)) or any(
            ("." + w) in o.name for w in VEG_WORDS)
        if not veg:
            continue
        lp = Mi @ o.matrix_world.translation
        if math.hypot(lp.x, lp.y) < R.rim_at(math.atan2(lp.y, lp.x)) + 1.5 and -3.0 < lp.z < R.ztop + 3.0:
            out.append(o)
    return out


def _delete(objs):
    datas = []
    for o in objs:
        for x in [o] + list(o.children_recursive):
            if x.data is not None:
                datas.append(x.data)
    names = []
    for o in objs:
        if o.name not in bpy.data.objects:
            continue
        for x in reversed([o] + list(o.children_recursive)):
            names.append(x.name)
            bpy.data.objects.remove(x, do_unlink=True)
    for d in datas:
        try:
            if d.users == 0:
                if isinstance(d, bpy.types.Mesh):
                    bpy.data.meshes.remove(d)
                elif isinstance(d, bpy.types.Curve):
                    bpy.data.curves.remove(d)
        except ReferenceError:
            pass
    return names


def strip_plants(rock, R=None, log=_log):
    """Remove the island's plants and roots (see the module doc). Returns the deleted object names."""
    gone = _delete(_plant_children(rock) + _plant_companions(rock, R))
    log("plants removed", len(gone), gone[:12], "..." if len(gone) > 12 else "")
    return gone


def clear(rock, log=_log):
    gone = _delete(our_objects(rock))
    if gone:
        log("previous icefire output removed", len(gone))
    return gone


# ---- mesh helpers ---------------------------------------------------------------------------------

def _new_obj(rock, part, bm, materials, smooth=None, glow=None):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    coll = rock.users_collection[0] if rock.users_collection else None
    ob = U.mesh_from_bmesh("%s.icefire_%s" % (rock.name, part), bm, coll, materials=materials, smooth=smooth,
                           parent=rock)
    ob[TAG] = part
    if glow is not None:
        ob["glow"] = float(glow)
    return ob


def _grid_shell(bm, top, bot, smooth_top=True):
    """Closed shell from two (na, nt) vertex grids: top and bottom surfaces and the four walls."""
    na, nt = len(top), len(top[0])
    for i in range(na - 1):
        for j in range(nt - 1):
            f = bm.faces.new((top[i][j], top[i + 1][j], top[i + 1][j + 1], top[i][j + 1]))
            f.smooth = smooth_top
            bm.faces.new((bot[i][j + 1], bot[i + 1][j + 1], bot[i + 1][j], bot[i][j]))
    for i in range(na - 1):
        for j in (0, nt - 1):
            bm.faces.new((top[i][j], bot[i][j], bot[i + 1][j], top[i + 1][j]))
    for i in (0, na - 1):
        for j in range(nt - 1):
            bm.faces.new((top[i][j], top[i][j + 1], bot[i][j + 1], bot[i][j]))


def _hull(bm, pts):
    """Closed convex hull of pts into bm (seracs): flat-shaded faces; points inside the hull are removed."""
    vs = [bm.verts.new(p) for p in pts]
    res = bmesh.ops.convex_hull(bm, input=vs, use_existing_faces=False)
    for f in res["geom"]:
        if isinstance(f, bmesh.types.BMFace):
            f.smooth = False
    junk = list({v for v in res["geom_interior"] + res["geom_unused"]
                 if isinstance(v, bmesh.types.BMVert) and not v.link_faces})
    if junk:
        bmesh.ops.delete(bm, geom=junk, context='VERTS')


def _icicle(bm, top, length, radius, rnd, sides=6):
    """A closed, slightly bent icicle hanging from ``top`` (its top ring sits 0.5 m above, inside the support)."""
    rings = (0.0, 0.18, 0.42, 0.7) if length < 4.0 else (0.0, 0.12, 0.3, 0.5, 0.72, 0.88)
    sway = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.0)) * length * 0.06
    ph = rnd.uniform(0, 6.28)
    loops = []
    for u in rings:
        r = radius * (1.0 - u) ** 1.25 * (1.0 + 0.12 * math.sin(u * 17.0 + ph))
        c = Vector(top) + Vector((0, 0, 0.5 - (length + 0.5) * u)) + sway * u * u
        loops.append([bm.verts.new(c + Vector((math.cos(2 * math.pi * k / sides + ph) * r,
                                                  math.sin(2 * math.pi * k / sides + ph) * r, 0.0)))
                      for k in range(sides)])
    tip = bm.verts.new(Vector(top) + Vector((0, 0, -length)) + sway)
    for a, b in zip(loops, loops[1:]):
        for k in range(sides):
            f = bm.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]))
            f.smooth = True
    for k in range(sides):
        f = bm.faces.new((loops[-1][k], loops[-1][(k + 1) % sides], tip))
        f.smooth = True
    bm.faces.new(list(reversed(loops[0])))


def _slab(bm, bvh, pts, nrms, widths, lift=LIFT, sink=SINK):
    """A closed lava slab along a path on a surface: per section three top points across the width (each projected
    onto the surface, then lifted along the path normal) and a keel sunk under the centre. pts / nrms / widths: per
    section, in the frame of ``bvh``."""
    n = len(pts)
    if n < 2:
        return 0
    secs = []
    for i in range(n):
        p, nrm = Vector(pts[i]), Vector(nrms[i]).normalized()
        t = Vector(pts[min(i + 1, n - 1)]) - Vector(pts[max(i - 1, 0)])
        t = (t - nrm * t.dot(nrm))
        if t.length < 1e-6:
            t = nrm.orthogonal()
        t.normalize()
        b = nrm.cross(t).normalized()
        row = []
        for c in (-0.5, 0.0, 0.5):
            q = p + b * c * widths[i]
            hit = bvh.find_nearest(q)[0]
            q = hit if hit is not None else q
            row.append(bm.verts.new(q + nrm * lift))
        row.append(bm.verts.new(p - nrm * sink))
        secs.append(row)
    for s0, s1 in zip(secs, secs[1:]):
        for k in range(4):
            f = bm.faces.new((s0[k], s1[k], s1[(k + 1) % 4], s0[(k + 1) % 4]))
            f.smooth = k < 2
    bm.faces.new((secs[0][0], secs[0][1], secs[0][2], secs[0][3]))
    bm.faces.new((secs[-1][3], secs[-1][2], secs[-1][1], secs[-1][0]))
    return n


# ---- glacier cap ------------------------------------------------------------------------------------

def fall_ranges(rock, R, margin_deg=0.0):
    """(centre azimuth, half width) in radians, rock-local, of each waterfall pouring off this rock: build_islands'
    falls ('scenery.island.fall*' Empties with their sheets as children) whose lip lies on the rock's top. The fall
    keeps pouring from under the glacier's edge (meltwater); icicles and seracs keep out of its sheet."""
    Mi = rock.matrix_world.inverted()
    out = []
    for o in bpy.data.objects:
        if o.parent is not None or not o.name.startswith("scenery.island.fall") or o.type != 'EMPTY':
            continue
        lp = Mi @ o.matrix_world.translation
        if math.hypot(lp.x, lp.y) > R.rmax + 2.0 or abs(lp.z) > 3.0:
            continue
        ths = []
        for ch in o.children_recursive:
            if ch.type != 'MESH':
                continue
            Mc = Mi @ ch.matrix_world
            for c in ch.bound_box:
                q = Mc @ Vector(c)
                if q.z > -12.0:
                    ths.append(math.atan2(q.y, q.x))
        th0 = math.atan2(lp.y, lp.x)
        half = max([_ang(t, th0) for t in ths] + [math.radians(4.0)])
        out.append((th0, half + math.radians(margin_deg)))
    return out


def _in_fall(th, falls):
    return any(_ang(th, c) < h for c, h in falls)


def _ang(a, b):
    return abs(math.atan2(math.sin(a - b), math.cos(a - b)))


class Cap:
    """Glacier cap over the ice half: a heightfield over (a, t), a along the seam, t from the snout (0) to the rim
    (1, the overhang edge)."""

    def __init__(self, R, rnd):
        G = GLACIER
        self.R, self.G = R, G
        self.ph = [rnd.uniform(0, 6.28) for _ in range(8)]
        self._far = {}
        span = []
        a = -R.rmax
        while a <= R.rmax:
            d0 = self.d0(a)
            df = self.d_far(a, d0)
            if df is not None and df - d0 >= 2.2:
                span.append(a)
            a += 0.25
        self.a0, self.a1 = min(span) + 0.4, max(span) - 0.4

    def d0(self, a):
        return GLACIER["snout"] + seam_d0(a, 0.0)

    def overhang(self, th):
        G = self.G
        u = 0.5 + 0.5 * math.sin(3.0 * th + self.ph[0]) * math.cos(5.0 * th + self.ph[1])
        return G["overhang"][0] + (G["overhang"][1] - G["overhang"][0]) * u

    def d_far(self, a, d0):
        key = round(a, 5)
        if key not in self._far:
            self._far[key] = self._d_far(a, d0)
        return self._far[key]

    def _d_far(self, a, d0):
        d = d0
        while d < self.R.rmax + 10.0:
            x, y = to_xy(a, d)
            th = math.atan2(y, x)
            if math.hypot(x, y) > self.R.rim_at(th) + self.overhang(th):
                return d
            d += 0.2
        return None

    def point(self, a, t):
        """(x, y, top z, bottom z, inside the rock rim) of the cap at (a, t)."""
        G, R = self.G, self.R
        d0 = self.d0(a)
        df = self.d_far(a, d0) or (d0 + 2.2)
        L = df - d0
        x, y = to_xy(a, d0 + t * L)
        th = math.atan2(y, x)
        r = math.hypot(x, y)
        rim = R.rim_at(th)
        zt = R.top_z(x, y) if r < rim - 0.3 else None
        z0 = zt if zt is not None else -0.3
        s = t * L
        hmax = G["height"][0] + (G["height"][1] - G["height"][0]) * (0.5 + 0.5 * math.sin(0.13 * a + self.ph[2]))
        eh = G["edge_h"][0] + (G["edge_h"][1] - G["edge_h"][0]) * (0.5 + 0.5 * math.sin(0.31 * a + self.ph[3]))
        eh += 0.9 * U.fbm((x, y, 0.0), 0.27, 2, seed=813)          # a ragged ice cliff, not a ruled lid
        h = G["snout_h"] + (hmax - G["snout_h"]) * _smooth(s, 0.0, 9.0)
        h += (eh - h) * _smooth(s, L - 5.0, L)
        h -= 0.9 * _smooth(s, L - 1.2, L)                          # the edge rounds over before it drops
        end = _smooth(min(a - self.a0, self.a1 - a), 0.0, 7.0)
        h *= 0.4 + 0.6 * end
        h += 0.55 * U.fbm((x, y, 0.0), 0.11, 3, seed=811) + 0.35 * U.fbm((x, y, 0.0), 0.33, 2, seed=812)
        h -= 0.7 * max(0.0, math.sin(0.62 * a + 0.25 * s + self.ph[4])) ** 10 * _smooth(s, 2.0, 6.0)   # crevasses
        top = z0 + max(1.0, h)
        if r < rim - 0.3:
            bot = z0 - G["sink"]
            inside = True
        else:
            dr = G["droop"][0] + (G["droop"][1] - G["droop"][0]) * (0.5 + 0.5 * math.sin(2.0 * th + self.ph[5]))
            dr = max(0.6, dr + 0.9 * U.fbm((x, y, 0.0), 0.3, 2, seed=814))   # a lumpy hanging lip
            k = _smooth(r, rim - 0.3, rim + 0.6)
            bot = (1 - k) * (z0 - G["sink"]) + k * (-0.35 - dr)
            inside = False
        return x, y, top, bot, inside


def _smooth(v, e0, e1):
    if e1 == e0:
        return 1.0 if v >= e1 else 0.0
    t = max(0.0, min(1.0, (v - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def _shard(bm, base, w, hh, rnd, lean):
    """An ice shard (closed convex hull, flat facets): an irregular 5-6 point base ring 1.3 m under ``base`` (sunk in
    the cap), a narrower shoulder ring and one or two apex points, leaning by ``lean`` (m at the top)."""
    nb = rnd.choice((5, 6))
    yaw = rnd.uniform(0, 6.28)
    pts = []
    for c in range(nb):
        ang = yaw + c * 2 * math.pi / nb + rnd.uniform(-0.3, 0.3)
        rr = w * 0.5 * rnd.uniform(0.7, 1.0)
        pts.append(Vector(base) + Vector((math.cos(ang) * rr, math.sin(ang) * rr * 0.75, -1.3)))
    for c in range(3):
        ang = yaw + c * 2 * math.pi / 3 + rnd.uniform(-0.4, 0.4)
        rr = w * 0.5 * rnd.uniform(0.35, 0.6)
        pts.append(Vector(base) + Vector((math.cos(ang) * rr, math.sin(ang) * rr, hh * rnd.uniform(0.45, 0.65)))
                   + lean * 0.55)
    pts.append(Vector(base) + Vector((rnd.uniform(-0.2, 0.2) * w, rnd.uniform(-0.2, 0.2) * w, hh)) + lean)
    if rnd.random() < 0.5:
        pts.append(Vector(base) + Vector((rnd.uniform(-0.35, 0.35) * w, rnd.uniform(-0.35, 0.35) * w,
                                          hh * rnd.uniform(0.7, 0.85))) + lean * 0.8)
    _hull(bm, pts)


def build_glacier(rock, R, rnd, log=_log):
    G = GLACIER
    falls = fall_ranges(rock, R, margin_deg=4.0)
    cap = Cap(R, rnd)
    bm = bmesh.new()
    na, nt = G["na"], G["nt"]
    ts = [0.0, 0.02] + [0.04 + 0.96 * (j / (nt - 3)) ** 0.9 for j in range(nt - 2)]
    ts = sorted(set(min(1.0, t) for t in ts))
    top, bot, edge = [], [], []
    for i in range(na):
        a = cap.a0 + (cap.a1 - cap.a0) * i / (na - 1)
        rt, rb = [], []
        for j, t in enumerate(ts):
            x, y, zt, zb, inside = cap.point(a, t)
            rt.append(bm.verts.new((x, y, zt)))
            rb.append(bm.verts.new((x, y, zb)))
            if j == len(ts) - 1:
                edge.append((a, x, y, zb, inside))
        top.append(rt)
        bot.append(rb)
    _grid_shell(bm, top, bot)
    # seracs: ice shards along the front rim (leaning out over the drop, in clusters) and the snout (leaning toward
    # the volcano). They stand on the cap's top, so the rim over the waterfall gets them too.
    nser = 0
    k = 0
    while k < G["seracs"] + G["snout_seracs"]:
        snout = k >= G["seracs"]
        k += 1
        a = rnd.uniform(cap.a0 + 3.0, cap.a1 - 3.0)
        t = rnd.uniform(0.05, 0.16) if snout else rnd.uniform(0.82, 0.95)
        x, y, zt, _zb, _in = cap.point(a, t)
        th = math.atan2(y, x)
        out =Vector((math.cos(th), math.sin(th), 0.0)) if not snout else Vector((-EI[0], -EI[1], 0.0))
        for _c in range(rnd.choice((1, 2, 2, 3))):
            w = rnd.uniform(1.3, 2.8)
            hh = rnd.uniform(3.0, 8.0) if not snout else rnd.uniform(2.2, 4.5)
            j = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.0)) * 1.6
            lean = out * hh * rnd.uniform(0.08, 0.3) + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.0)) * 0.4
            _shard(bm, Vector((x, y, zt)) + j, w, hh, rnd, lean)
            nser += 1
    ob = _new_obj(rock, "glacier", bm, ["icefire_ice"], smooth=math.radians(42))
    log("glacier", ob.name, "a", round(cap.a0, 1), round(cap.a1, 1), "falls (az deg, half deg)",
        [(round(math.degrees(c), 1), round(math.degrees(h), 1)) for c, h in falls], "shards", nser,
        "tris", _tris(ob.data))
    return ob, cap, edge, falls


def build_icicles(rock, R, edge, falls, sup, rnd, log=_log):
    """Icicles under the cap's overhang edge: every ICICLES['step'] m along it (some skipped; none in front of the
    waterfall), short and long ones, shortened so they never reach into the rock below."""
    C = ICICLES
    falls = [(c, h + math.radians(C["fall_margin"])) for c, h in falls]
    bm = bmesh.new()
    n = 0
    acc = 0.0
    prev = None
    for (a, x, y, zb, inside) in edge:
        if prev is not None:
            acc += math.hypot(x - prev[0], y - prev[1])
        prev = (x, y)
        if inside or acc < C["step"]:
            continue
        acc = 0.0
        th = math.atan2(y, x)
        if _in_fall(th, falls):
            continue
        if rnd.random() < C["skip"]:
            continue
        for _ in range(2 if rnd.random() < 0.35 else 1):
            lng = rnd.random() < C["long_share"]
            L = rnd.uniform(*(C["long"] if lng else C["short"]))
            r_out = rnd.uniform(-0.6, -0.15)          # a little inward of the edge, under the overhang
            px = x + math.cos(th) * r_out + rnd.uniform(-0.3, 0.3)
            py = y + math.sin(th) * r_out + rnd.uniform(-0.3, 0.3)
            up = sup.ray_cast(Vector((px, py, zb - 3.0)), Vector((0, 0, 1)), 6.0)[0]   # the cap's real underside
            if up is None:
                continue
            pt = Vector((px, py, up.z))
            hit = sup.ray_cast(pt + Vector((0, 0, -0.6)), Vector((0, 0, -1)), L + 1.0)[0]
            if hit is not None:
                L = min(L, (pt.z - hit.z) - 0.8)
            if L < 1.0:
                continue
            _icicle(bm, pt, L, max(0.14, L * 0.085 + rnd.uniform(0.0, 0.12)), rnd, C["sides"])
            n += 1
    ob = _new_obj(rock, "icicles", bm, ["icefire_ice"])
    log("icicles", ob.name, "count", n, "tris", _tris(ob.data))
    return ob


def build_stalactites(rock, R, falls, sup, rnd, log=_log):
    """Ice stalactites under the ice half of the cone: from faces that lean down (outward normal z < -min_down),
    SEAM_CLEAR m inside the ice side and clear of the waterfall, spread at least `spacing` m apart, hanging straight
    down clear of the rock; faces turned toward the hold camera (VIEW_AZ) are picked first."""
    C = STALACTITES
    me = rock.data
    falls = [(c, h + math.radians(6.0)) for c, h in falls]
    va = math.radians(VIEW_AZ)
    cand = []
    for p in me.polygons:
        c = p.center
        if c.z > -2.0 or c.z < R.zlow + 6.0:
            continue
        if seam(c.x, c.y, c.z) < SEAM_CLEAR + 0.5:
            continue
        if _in_fall(math.atan2(c.y, c.x), falls):
            continue
        nrm = p.normal.copy()
        if nrm.dot(Vector((c.x, c.y, 0.0))) < 0:
            nrm = -nrm
        if nrm.z > -C["min_down"]:
            continue
        face = 0.25 + max(0.0, math.cos(math.atan2(nrm.y, nrm.x) - va))
        cand.append((c.copy(), nrm, p.area * face))
    rnd.shuffle(cand)
    cand.sort(key=lambda e: -e[2] * rnd.uniform(0.5, 1.5))
    bm = bmesh.new()
    placed = []
    for c, nrm, _a in cand:
        if len(placed) >= C["count"]:
            break
        if any((c - q).length < C["spacing"] for q in placed):
            continue
        L = rnd.uniform(*C["length"]) * (0.6 + 0.4 * min(1.0, -c.z / 30.0))
        start = c + nrm * 0.15
        hit = sup.ray_cast(start + Vector((0, 0, -0.3)), Vector((0, 0, -1)), L + 1.5)[0]
        if hit is not None:
            L = min(L, start.z - hit.z - 1.0)
        if L < 2.5:
            continue
        top = c - nrm * 0.35
        rad = min(C["radius"][1], max(C["radius"][0], L * 0.07))
        _icicle(bm, top, L, rad, rnd, C["sides"])
        placed.append(c)
    ob = _new_obj(rock, "stalactites", bm, ["icefire_ice"])
    log("stalactites", ob.name, "count", len(placed), "of", len(cand), "candidates", "tris", _tris(ob.data))
    return ob


# ---- volcano ----------------------------------------------------------------------------------------

def build_volcano(rock, R, rnd, steam_xy, log=_log):
    """A volcanic cone (closed) on the basalt half: noisy concave flanks with gullies, a jagged rim with two low
    notches (toward the steam point and toward the rim), a crater wall down to a molten pool (material slot 1)."""
    V = VOLCANO
    cx, cy = to_xy(V["a"], V["d"])
    zc = R.top_z(cx, cy) or 0.0
    segs, rings, H = V["segs"], V["rings"], V["height"]
    th_flow = math.atan2(steam_xy[1] - cy, steam_xy[0] - cx)
    th_rim = math.atan2(cy, cx)                      # outward: toward the island rim
    ph = [rnd.uniform(0, 6.28) for _ in range(6)]
    bm = bmesh.new()
    loops = []
    for k in range(rings + 1):
        u = k / rings
        h = H * u
        row = []
        for s in range(segs):
            th = 2 * math.pi * s / segs
            r = V["top_r"] + (V["base_r"] - V["top_r"]) * (1.0 - u) ** 1.7
            r *= 1.0 + (0.07 * math.sin(7 * th + ph[0] + 2.0 * u) + 0.04 * math.sin(13 * th + ph[1])) * (1.0 - u * 0.6)
            r *= 1.0 + 0.08 * U.fbm((math.cos(th) * 2.0, math.sin(th) * 2.0, u * 2.0), 1.0, 3, seed=821)
            x, y = cx + math.cos(th) * r, cy + math.sin(th) * r
            if k == 0:
                z = (R.top_z(x, y) or zc) - V["sink"]
            else:
                z = zc + h
                if k == rings:
                    z += 0.7 * math.sin(5 * th + ph[2]) + 0.4 * math.sin(11 * th + ph[3])
                    z -= V["notch_flow"] * math.exp(-(_ang(th, th_flow) / 0.28) ** 2)
                    z -= V["notch_rim"] * math.exp(-(_ang(th, th_rim) / 0.3) ** 2)
            row.append(bm.verts.new((x, y, z)))
        loops.append(row)
    rim = loops[-1]
    # crater: inner wall rings down to the pool, each under the rim above it (the notches dip 1.6 m + the jag)
    zr = zc + H
    zpool = zr - V["crater"]
    inner = []
    for k, (rf, dz) in enumerate(((0.92, 0.5), (0.78, 1.2), (0.66, None))):
        row = []
        for s in range(segs):
            th = 2 * math.pi * s / segs
            r = V["top_r"] * rf * (1.0 + 0.05 * math.sin(7 * th + ph[4]))
            z = zpool + 0.4 if dz is None else max(zpool + 0.6 + 0.4 * (1 - k), rim[s].co.z - dz)
            row.append(bm.verts.new((cx + math.cos(th) * r, cy + math.sin(th) * r, z)))
        inner.append(row)
    seq = loops + inner
    for a, b in zip(seq, seq[1:]):
        for s in range(segs):
            f = bm.faces.new((a[s], a[(s + 1) % segs], b[(s + 1) % segs], b[s]))
            f.smooth = True
    # the pool: a slightly domed molten disc closing the crater
    pc = bm.verts.new((cx, cy, zpool + 0.55))
    last = inner[-1]
    for s in range(segs):
        f = bm.faces.new((last[s], last[(s + 1) % segs], pc))
        f.material_index = 1
        f.smooth = True
    bc = bm.verts.new((cx, cy, zc - V["sink"] - 0.5))
    for s in range(segs):
        bm.faces.new((loops[0][(s + 1) % segs], loops[0][s], bc))
    ob = _new_obj(rock, "volcano", bm, ["icefire_basalt", "molten"])
    ob["glow"] = LAVA_GLOW
    log("volcano", ob.name, "centre", (round(cx, 1), round(cy, 1), round(zc, 2)), "tris", _tris(ob.data))
    return ob, (cx, cy, zc), th_flow, th_rim


# ---- lava -----------------------------------------------------------------------------------------

def _down_path(sup, xy_pts, z_hint):
    """Project xy points straight down onto the support; returns (points, up normals)."""
    pts, nrms = [], []
    for x, y in xy_pts:
        hit, nrm, _i, _d = sup.ray_cast(Vector((x, y, z_hint + 40.0)), Vector((0, 0, -1)), 120.0)
        if hit is None:
            continue
        if nrm.z < 0:
            nrm = -nrm
        pts.append(hit)
        nrms.append(nrm)
    return pts, nrms


def build_lava_flow(rock, R, cap, vc, th_flow, th_rim, steam_xy, sup, rnd, log=_log):
    """Two streams from the crater's notches: one down the flank and across the black ground to the glacier snout
    (ending at the steam point), one down the outer flank to the island's rim."""
    V = VOLCANO
    cx, cy, zc = vc
    bm = bmesh.new()
    lens = []
    # stream 1: crater notch -> flank -> snout
    sx, sy = steam_xy
    x0, y0 = cx + math.cos(th_flow) * V["top_r"] * 0.8, cy + math.sin(th_flow) * V["top_r"] * 0.8
    L1 = math.hypot(sx - x0, sy - y0)
    n1 = max(8, int(L1 / 0.6))
    side = Vector((-math.sin(th_flow), math.cos(th_flow)))
    xy = []
    for i in range(n1 + 1):
        u = i / n1
        m = 1.1 * math.sin(u * 7.0 + 0.6) * math.sin(math.pi * u)
        xy.append((x0 + (sx - x0) * u + side.x * m, y0 + (sy - y0) * u + side.y * m))
    pts, nrms = _down_path(sup, xy, zc + V["height"])
    w = [1.3 + 1.6 * _smooth(i / max(1, len(pts) - 1), 0.3, 1.0) for i in range(len(pts))]
    w = [wi * min(1.0, (i + 1) / 3.0) for i, wi in enumerate(w)]
    lens.append(_slab(bm, sup, pts, nrms, w))
    # stream 2: crater notch -> outer flank -> rim
    rim_r = R.rim_at(th_rim) - 0.4
    x0, y0 = cx + math.cos(th_rim) * V["top_r"] * 0.8, cy + math.sin(th_rim) * V["top_r"] * 0.8
    xe, ye = math.cos(th_rim) * rim_r, math.sin(th_rim) * rim_r
    L2 = math.hypot(xe - x0, ye - y0)
    n2 = max(8, int(L2 / 0.6))
    side = Vector((-math.sin(th_rim), math.cos(th_rim)))
    xy = []
    for i in range(n2 + 1):
        u = i / n2
        m = 0.9 * math.sin(u * 9.0 + 1.9) * math.sin(math.pi * u)
        xy.append((x0 + (xe - x0) * u + side.x * m, y0 + (ye - y0) * u + side.y * m))
    pts2, nrms2 = _down_path(sup, xy, zc + V["height"])
    w2 = [(1.2 + 0.6 * math.sin(i * 0.4)) * min(1.0, (i + 1) / 3.0) for i in range(len(pts2))]
    lens.append(_slab(bm, sup, pts2, nrms2, w2))
    ob = _new_obj(rock, "lava_flow", bm, ["molten"], glow=LAVA_GLOW)
    log("lava flow", ob.name, "sections", lens, "tris", _tris(ob.data))
    return ob, (pts2[-1] if pts2 else None), th_rim


def _vein_walk(R, rnd, th0, z0, length, width, step, heading=None, sigma=None, relax=0.5, taper_in=False):
    """A zigzag fissure over the cone from (th0, z0): straight runs of 2.5-5.5 m, each turned by a random angle
    (sigma) from the last heading pulled back toward the fall line by `relax` (heading 0 = straight down, +-pi/2 =
    sideways), stepped every `step` m, each point found on the outer surface. Stops at the seam (SEAM_CLEAR) or on a
    jump (a spur in the way). Returns [(point, normal, width)]."""
    sigma = math.radians(VEINS["sigma"]) if sigma is None else sigma
    out = []
    th, z = th0, z0
    r_prev = None
    walked = 0.0
    hd = rnd.gauss(0.0, sigma) if heading is None else heading
    ph = rnd.uniform(0, 6.28)
    first = True
    while walked < length:
        if not first:
            hd = relax * hd + rnd.gauss(0.0, sigma)
        first = False
        hd = max(-1.45, min(1.45, hd))
        seg = rnd.uniform(2.5, 5.5)
        k = 0.0
        while k < seg and walked < length:
            hit, nrm = R.cone_hit(th, z)
            if hit is None:
                return out
            r = math.hypot(hit.x, hit.y)
            if r_prev is not None and abs(r - r_prev) > 2.8:
                return out
            if seam(hit.x, hit.y, hit.z) > -SEAM_CLEAR:
                return out
            u = walked / length
            wk = width * (1.0 - 0.6 * u) * (1.0 + 0.18 * math.sin(walked * 0.7 + ph))
            if taper_in:
                wk *= min(1.0, (walked + step) / 3.0)
            wk *= min(1.0, (length - walked) / 2.5 + 0.12)
            out.append((hit, nrm, max(0.2, wk)))
            r_prev = r
            th += math.sin(hd) * step / max(4.0, r)
            z -= math.cos(hd) * step
            k += step
            walked += step
    return out


def build_lava_veins(rock, R, rim_end, th_rim, rnd, log=_log):
    """The crack network on the basalt underside: main fissures from just under the rim (VEINS['mains'], rock-local
    azimuths, plus one under the second lava stream's end), forks leaving them at 35-75 deg, short twigs off the forks,
    and a few cross cracks running along the strata near the rim."""
    C = VEINS
    bm = bmesh.new()
    counts = dict(mains=0, forks=0, twigs=0, cross=0)
    secs = 0

    def lay(path, kind):
        nonlocal secs
        if len(path) < 3 or 8 * (secs + len(path)) > C["tri_budget"]:
            return False
        secs += _slab(bm, R.bvh, [p for p, _, _ in path], [n for _, n, _ in path], [w for _, _, w in path])
        counts[kind] += 1
        return True

    def side_heading():
        return rnd.choice((-1, 1)) * math.radians(rnd.uniform(35.0, 75.0))

    mains = [(math.radians(t), -0.7, 1.0, False) for t in C["mains"]] + [(th_rim, -0.7, 1.0, False)]
    mains += [(math.radians(t), z, 0.7, True) for t, z in C["mid"]]       # lower down, where the rim mains thin out
    for th0, z0, k, mid in mains:
        L = rnd.uniform(*C["length"]) * k
        path = _vein_walk(R, rnd, th0, z0, L, rnd.uniform(*C["width"]) * (0.8 if mid else 1.0), C["step"],
                          taper_in=mid)
        if not lay(path, "mains"):
            continue
        for _f in range(rnd.randint(*C["forks"])):
            i = rnd.randint(int(len(path) * 0.15), max(int(len(path) * 0.15), int(len(path) * 0.85) - 1))
            p, _n, w = path[i]
            fork = _vein_walk(R, rnd, math.atan2(p.y, p.x), p.z, rnd.uniform(*C["fork_len"]), w * C["fork_w"],
                              C["step"] * 0.8, heading=side_heading(), relax=0.7)
            if not lay(fork, "forks"):
                continue
            for _t in range(rnd.randint(*C["twigs"])):
                j = rnd.randint(1, len(fork) - 1)
                q, _n, _w = fork[j]
                twig = _vein_walk(R, rnd, math.atan2(q.y, q.x), q.z, rnd.uniform(*C["twig_len"]),
                                  rnd.uniform(0.85, 1.15) * C["twig_w"], C["step"] * 0.7, heading=side_heading(),
                                  relax=0.8)
                lay(twig, "twigs")
    for _c in range(C["cross"]):
        th0 = math.radians(rnd.uniform(-105.0, 10.0))
        lay(_vein_walk(R, rnd, th0, rnd.uniform(-3.0, -9.0), rnd.uniform(6.0, 12.0), rnd.uniform(0.5, 0.75),
                       C["step"] * 0.8, heading=rnd.choice((-1, 1)) * 1.3, sigma=math.radians(9.0), relax=0.97,
                       taper_in=True), "cross")
    ob = _new_obj(rock, "lava_veins", bm, ["molten"], glow=LAVA_GLOW)
    log("lava veins", ob.name, counts, "sections", secs, "tris", _tris(ob.data))
    return ob


# ---- steam -----------------------------------------------------------------------------------------

def build_steam(rock, steam_pt, rnd, log=_log):
    """A thin plume of cloud puffs rising from where the lava meets the snout, drifting toward STEAM['drift_az'], and
    a few low wisps along the snout."""
    C = STEAM
    coll = rock.users_collection[0] if rock.users_collection else None
    t = math.radians(C["drift_az"])
    drift = Vector((math.cos(t), math.sin(t), 0.0))
    base = Vector(steam_pt) + Vector((0, 0, 1.2))
    obs = []
    h = 0.0
    for k in range(C["puffs"]):
        size = C["size"][0] + C["size"][1] * k
        if k:
            h += C["overlap"] * size                # each puff overlaps the one under it by more than half
        loc = base + Vector((0, 0, h)) + drift * (0.035 * h ** 1.5) + Vector(
            (rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.0)) * size * 0.1
        dens = max(0.16, C["density"][0] - C["density"][1] * k)
        ob = N.cloud_puff(coll, size=size, seed=9100 + k, density=dens, flatten=rnd.uniform(0.8, 1.0),
                          name=STEAM_PREFIX, location=tuple(loc), parent=rock)
        ob[TAG] = "steam"
        obs.append(ob)
    for k in range(C["wisps"]):
        a = STEAM_A + rnd.uniform(-9.0, -2.0) * (1 if k % 2 else -0.6)
        x, y = to_xy(a, GLACIER["snout"] + seam_d0(a) - 0.6)
        loc = Vector((x, y, steam_pt[2] + rnd.uniform(1.5, 3.0)))
        ob = N.cloud_puff(coll, size=rnd.uniform(3.5, 5.5), seed=9200 + k, density=0.32, flatten=0.6,
                          name=STEAM_PREFIX, location=tuple(loc), parent=rock)
        ob[TAG] = "steam"
        obs.append(ob)
    log("steam", len(obs), "puffs from", tuple(round(v, 1) for v in steam_pt), "top",
        tuple(round(v, 1) for v in obs[C["puffs"] - 1].location))
    return obs


# ---- build ------------------------------------------------------------------------------------------

def _tris(me):
    n = len(me.polygons)
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def apply_materials(rock, log=_log):
    """The rock's two slots (cone, top) -> icefire_rock / icefire_ground, rebuilt from this module's builders."""
    for nm in MATERIALS:
        M.rebuild(nm)
    me = rock.data
    want = [M.get("icefire_rock"), M.get("icefire_ground")]
    if len(me.materials) < 2:
        raise RuntimeError("%s has %d material slots, expected 2 (rock, top)" % (rock.name, len(me.materials)))
    old = [m.name if m else None for m in me.materials]
    for i, m in enumerate(want):
        me.materials[i] = m
    for s in rock.material_slots:
        if s.link != 'DATA':
            s.link = 'DATA'
    log("rock slots", old, "->", [m.name for m in me.materials])


def build(rock, log=_log):
    """Make ``rock`` (a nature.floating_rock) Ice-Fire Island. Idempotent. Returns {part: object or list}."""
    if rock is None or rock.type != 'MESH':
        raise RuntimeError("icefire: no rock mesh")
    rnd = random.Random(U.seed_from(KEY, rock.name))
    clear(rock, log)
    R = Rock(rock)                                  # the rock's mesh is never changed: one analysis serves all
    strip_plants(rock, R, log)
    apply_materials(rock, log)
    log("rock", rock.name, "rim max", round(R.rmax, 1), "top", round(R.ztop, 2), "low", round(R.zlow, 1))
    glacier, cap, edge, falls = build_glacier(rock, R, rnd, log)
    gl = _mesh_lists(glacier)
    sup_cap = _support_bvh([(R.co.tolist(), R.polys), gl])
    icicles = build_icicles(rock, R, edge, falls, sup_cap, rnd, log)
    stal = build_stalactites(rock, R, falls, sup_cap, rnd, log)
    sa = STEAM_A
    sx, sy = to_xy(sa, cap.d0(sa) - 0.5)
    volcano, vc, th_flow, th_rim = build_volcano(rock, R, rnd, (sx, sy), log)
    sup = _support_bvh([(R.co.tolist(), R.polys), _mesh_lists(volcano)])
    flow, rim_end, th_rim = build_lava_flow(rock, R, cap, vc, th_flow, th_rim, (sx, sy), sup, rnd, log)
    veins = build_lava_veins(rock, R, rim_end, th_rim, rnd, log)
    sz = R.top_z(sx, sy) or 0.0
    steam = build_steam(rock, (sx, sy, sz), rnd, log)
    out = dict(glacier=glacier, icicles=icicles, stalactites=stal, volcano=volcano, lava_flow=flow, lava_veins=veins,
               steam=steam)
    for k, ob in out.items():
        if k != "steam" and _tris(ob.data) > TRI_CAP:
            log("WARN", ob.name, "has", _tris(ob.data), "triangles >", TRI_CAP)
    return out
