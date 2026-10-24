"""Ice-Fire Island 冰火島 (Heaven Sword and Dragon Saber), round 36: scenery.island.009 rebuilt whole as one
floating island, half glacier and half volcano. Zhang Cuishan, Yin Susu and Xie Xun drift to it through the polar
sea, and Zhang Wuji is born there.

    from sect.lib import icefire_island as II
    II.build(bpy.data.objects["scenery.island.009"])     # idempotent: removes its own (and icefire_props') output

Why (round 36): the round-7 island (lib/icefire_props.py) re-skinned a nature.floating_rock and laid its lava as
separate glowing slabs on it. On the web the backdrop's stand-in copy decimates every piece on its own: round 12's
tidy_rock had stacked 538 vertices on the cone's tip without merging them, so the collapse decimation kept only the
cone's bottom 59 m, the glacier cap floated with nothing under it and the lava slabs hung in the air like lightning.

What this builds (everything in the rock's own frame: the island can stand, turn or drop anywhere):
- the rock itself (the object keeps its name, transform and lore role; its mesh is replaced): one closed, manifold
  mesh with a single tip vertex and no zero-area faces. A flat top (a gentle dome, z 0 at the rim) over an inverted
  craggy cone DEPTH m deep, with a rounded lip, big buttress lobes, crags, vertical ice flutes on the ice half and
  basalt column facets and strata ledges on the fire half. The two halves meet along two wavy seams from the rim
  down to the tip (crisp: the seams are edges of the mesh). The underside is triangulated in its own (azimuth,
  depth) chart with mathutils.geometry.delaunay_2d_cdt, the seams and every lava outline as constraint edges.
- the lava runs IN the rock: the crack network, the lavafall over the rim and the two streams on the top are faces of
  the rock mesh (material 'molten'), each a V-groove sunk into the surface (its centre line pushed in), with a
  scorched band of rock around it. Simplified, they can thin or close, never float.
- <rock>.icefire_glacier: a glacier cap over the ice half of the top, overhanging the rim, an ice cliff (snout)
  facing the volcano, crevasses, serac shards along its crest and snout
- <rock>.icefire_icicles: icicles under the cap's overhang (none in front of the waterfall)
- <rock>.icefire_stalactites: ice stalactites under the ice half and basalt spurs under the fire half, from the rock
- <rock>.icefire_volcano: a small volcano on the fire half: crater with a molten pool, two notches, a lava channel
  down each flank (molten faces sunk into the flank) feeding the two streams on the top
- world.cloud.icefire_steam(.NNN): a steam plume over the crater and steam where the second stream reaches the ice
- the rock's plants go (crown / rim pines, ledge plants, roots, top pines and blossoms, life peaches)

Layout (layout()): the halves face the library hold. HOLD_CAM is the hold camera (chase.cam at frame 772, world
metres); in the rock's frame it sits at azimuth view_az. The fire half's centre goes FIRE_FROM_VIEW degrees to one
side of it (the lava faces the camera, the glacier shows beside it), on the side that keeps every waterfall pouring
off this rock within FALL_IN_ICE degrees of the ice half's centre (meltwater falls from the glacier); when no side
can, the halves turn the least that keeps the fall in the ice. So after a turn of the island (round 34 turns it
about 150 deg) a fresh build still puts the lava toward the camera. The waterfall (build_islands' fall Empty and its
sheets, not ours) pours through a gorge cut in the rim: the rock stays FALL_CLEAR m inside the sheets.

Every mesh is closed; the parts touch their support (the glacier and the volcano sink into the top, icicles and
stalactites start inside what they hang from). Every object is tagged obj[TAG] = part (the same tag as
icefire_props, so either module's clear() removes the other's output); the rock carries obj['glow'] (the molten
faces' emission) and obj[BUILD_PROP] = VERSION.
"""
import math
import random

import bmesh
import bpy
import numpy as np
from mathutils import Vector, kdtree
from mathutils import geometry as MG
from mathutils.bvhtree import BVHTree

from . import materials as M
from . import nature as N
from . import util as U

KEY = "icefire_island"
VERSION = "r36"
TAG = "sect_icefire"                 # obj[TAG] = part on every object this module makes (icefire_props' tag)
BUILD_PROP = "icefire_build"         # rock[BUILD_PROP] = VERSION once this module built it
STEAM_PREFIX = "world.cloud.icefire_steam"
PARTS = ("glacier", "icicles", "stalactites", "volcano")
HOLD_CAM = (41.52, 731.97, 179.66)   # world m: chase.cam at the library hold (frame 772), the view the halves face
FIRE_FROM_VIEW = 65.0                # deg: the fire half's centre this far to one side of the hold's line of sight
FALL_IN_ICE = 55.0                   # deg: a waterfall's centre at most this far from the ice half's centre
LAVA_GLOW = 1.6                      # obj['glow'] of the rock and the volcano (molten: emission 7 x glow x heat^1.5)

# ---- the rock's shape (rock-local metres; top at z ~ 0, tip at -DEPTH)
DEPTH = 64.0
R_REF = 34.0                         # the reference cone's rim radius (the chart's scale)
PROF_P, TIP_KNEE = 0.9, 0.86         # radius ~ (1 - t)^PROF_P down to t = TIP_KNEE, then straight to the tip
RIM_FOURIER = (34.125, -0.603, 0.402, 0.663, -0.412, 0.552, 0.702, 0.061, -0.222)   # the old rim's outline (a0,
#                                      a1, b1, a2, b2...): island.009's 69 m top, so the hold's framing holds
RIM_JAG = 0.9                        # m: the rim's own small wander
LIP, T_LIP = 0.45, 0.03              # the rim's lip bulges LIP m out over the first T_LIP of the depth
LOBE = 0.2                           # buttress lobes: +- this share of the local radius
MAJOR = 0.17                         # deep clefts that split the cone into buttresses: depth as a share of the radius
N_MAJOR = 11
BULB = 0.16                          # hanging bulges on the lower half: share of the radius
CRAG = 2.2                           # m: craggy noise (more toward the tip)
N_FLUTE, N_COL = 39, 67              # vertical ice flutes / basalt column facets round the island (whole numbers)
BEDS = (2.4, 6.0)                    # m: basalt beds (strata) thickness; some stick out as ledges
BED_AMP = (0.03, 0.085)              # share of the radius: a bed's wander / a ledge bed's stick-out
BED_LEDGE = 0.45                     # share of the beds that stick out as ledges
TIP_OFF = 3.5                        # m: the tip leans this far off the top's centre
SEAM_WAVE = (3.6, 1.7, 0.8)          # m: the seams' wander (two slow waves and a jag)
TOP_DOME, TOP_NOISE = 0.55, 0.18     # m: the top's dome and its unevenness
FALL_CLEAR = 1.0                     # m: the rock keeps this far inside a waterfall's sheets (the gorge)
FALL_DEPTH = 90.0                    # m: the sheets' depth that shapes the gorge

# ---- the chart and its triangles
C_X = 20.0                           # chart x = azimuth (rad, from the fire centre) x C_X; chart y = -depth along slant
H = 1.25                             # m: target edge length on the underside
H_RIM = 1.0                          # m: rim spacing
ROWS_TOP = (0.0, 0.45, 1.1, 2.0)     # m of slant: the rim and the lip rows (same azimuths as the rim)
TIP_STOP = 0.7                       # m: the last row's radius; then the tip vertex
TOP_H = 2.2                          # m: the top's point spacing (mostly under the glacier and the volcano)
PRUNE = 0.5                          # m: chart points this near a constraint line are left out

# ---- lava
CRACKS = dict(mains=(-74.0, -57.0, -40.0, -23.0, -6.0, 11.0, 28.0, 45.0, 62.0, 77.0), start=(1.8, 6.0),
              length=(22.0, 40.0), width=(1.2, 1.7), step=0.9, run=(2.5, 5.0), sigma=24.0, forks=(2, 3),
              fork_len=(6.0, 14.0), fork_w=0.55, cross=3, gap=1.4, seam_gap=2.6, tip_r=4.0, turn=70.0)
LAVAFALL = dict(width=(3.8, 2.0), length=24.0, tail=16.0, tail_w=0.9)
LAVA_RIM = 4                         # rim spacings (H_RIM m) the lavafall's mouth spans on the rim
HALO = 0.7                           # m: the scorched band each side of a crack or stream
INSET = dict(crack=0.42, lava=0.75, other=0.35)   # m: a groove's centre sunk this deep (scaled by width)
TOP_STREAM = dict(w1=(2.8, 3.8), w2=1.5, meander=0.9)

# ---- parts
GLACIER = dict(snout=3.5, height=(4.5, 7.5), snout_h=3.4, edge_h=(2.6, 3.8), overhang=(1.3, 2.7), droop=(1.2, 2.6),
               sink=0.7, na=64, nt=18, seracs=19, snout_seracs=6, fall_clear=0.6)
ICICLES = dict(step=0.85, skip=0.1, short=(1.4, 3.6), long=(4.5, 10.0), long_share=0.32, sides=6, fall_margin=4.0)
STALACTITES = dict(ice=24, basalt=11, spacing=4.0, ice_len=(5.0, 16.0), bas_len=(4.0, 11.0), ice_r=(0.45, 1.25),
                   bas_r=(0.8, 1.8), min_down=0.35, lava_clear=2.0, tips=3)
VOLCANO = dict(r=17.0, base_r=10.5, top_r=3.7, height=19.0, crater=3.3, segs=56, rings=15, sink=1.2, notch=1.5,
               chan_w=(1.5, 2.3), chan_inset=0.32)
STEAM = dict(plume=10, plume_size=(3.0, 0.75), snout=5, snout_size=(2.4, 0.6), overlap=0.45, drift_az=105.0,
             density=(0.55, 0.03))
TRI_CAP = 6000                       # per part (bake_web's island LOD floor keeps at most ISLAND_FLOOR_HI triangles)
ROCK_TRI_CAP = 22000

# material slots of the rock
ICE, BASALT, SNOW, CINDER, MOLTEN, SCORCH = range(6)
ROCK_MATS = ("icefire_isl_ice", "icefire_isl_basalt", "icefire_isl_snow", "icefire_isl_cinder", "molten",
             "icefire_isl_scorch")
SEED = 3607


def _log(*a):
    print("ICEFIRE", *a, flush=True)


def _wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


def _smooth(v, e0, e1):
    if e1 == e0:
        return 1.0 if v >= e1 else 0.0
    t = max(0.0, min(1.0, (v - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def _dir(a):
    return Vector((math.cos(a), math.sin(a), 0.0))


# ================================================================================================ materials

def _ice_surface(g, top=False):
    """Glacier ice in rock-local object coordinates: blue-white at the top to deep blue far under, long vertical melt
    streaks, strata, fracture lines, snow on what faces up."""
    p = g.coord("object")
    _px, _py, pz = g.sep(p)
    nz = g.sep(g.geometry("Normal"))[2]
    depth = g.maprange(pz, 6.0, -58.0, 0.0, 1.0)
    streak = g.noise(g.mapping(p, scale=(1.0, 1.0, 0.06)), 0.45, detail=3.0, roughness=0.55)
    run = g.noise(g.mapping(p, scale=(1.0, 1.0, 0.03)), 0.16, detail=2.0)       # long deep-blue melt runs
    strata = g.wave(p, scale=0.12, distortion=3.0, detail=2.0, kind='BANDS', direction='Z')
    fine = g.noise(p, 0.9, detail=3.0, roughness=0.6)
    frac = g.voronoi(g.mapping(p, scale=(1.0, 1.0, 0.12)), 0.22, feature='DISTANCE_TO_EDGE')   # long vertical fractures
    crack = g.math('SUBTRACT', 1.0, g.smooth(frac, 0.0, 0.035))
    t = g.add(g.mul(depth, 0.62), g.mul(g.math('SUBTRACT', streak, 0.5), 0.45))
    t = g.add(t, g.mul(g.smooth(run, 0.55, 0.72), 0.32))
    t = g.add(t, g.mul(g.math('SUBTRACT', strata, 0.5), 0.14))
    t = g.add(t, g.mul(g.math('SUBTRACT', fine, 0.5), 0.12))
    t = g.add(t, g.mul(crack, 0.14))
    col = g.ramp(t, [(0.0, "#f4f9fc"), (0.22, "#d9eff8"), (0.45, "#a9d7ee"), (0.68, "#6ab2da"), (0.88, "#3a82b8"),
                     (1.0, "#295f94")])
    brk = g.smooth(g.noise(p, 0.3, detail=3.0), 0.38, 0.58)
    snow = g.mul(g.smooth(nz, 0.05 if top else 0.3, 0.35 if top else 0.6), g.mixf(0.6, 1.0, brk))
    col = g.mix(col, "#f6f9fb", snow)
    hgt = g.add(g.mul(streak, 0.8), g.mul(crack, -0.4))
    g.viewport("#cfe6f1", 0.3)
    g.output(g.principled(base_color=col, roughness=g.mixf(0.22, 0.75, snow), normal=g.bump(hgt, 0.35, 0.08)))


def _basalt_surface(g, top=False, scorch=False):
    """Black columnar basalt: dark columns (voronoi cells stretched along z), black joints, rusty patches, grey ash
    on what faces up; scorch: the band round the lava, rust-red and darker."""
    p = g.coord("object")
    nz = g.sep(g.geometry("Normal"))[2]
    fine = g.noise(p, 0.55, detail=4.0, roughness=0.6)
    pc = g.mapping(p, scale=(1.0, 1.0, 0.22))
    cellv = g.sep(g.voronoi(pc, 0.5, out="Color"))[0]
    edge = g.voronoi(pc, 0.5, feature='DISTANCE_TO_EDGE')
    joint = g.math('SUBTRACT', 1.0, g.smooth(edge, 0.0, 0.05))
    bands = g.wave(p, scale=0.09, distortion=2.0, detail=2.0, kind='BANDS', direction='Z')      # strata tone
    t = g.add(g.add(g.mul(cellv, 0.5), g.mul(fine, 0.3)), g.mul(bands, 0.2))
    col = g.ramp(t, [(0.0, "#2b2521"), (0.45, "#40372f"), (0.8, "#584c42"), (1.0, "#6f6155")])
    col = g.mix(col, "#0f0c0a", g.mul(joint, 0.6))
    warm = g.smooth(g.noise(p, 0.06, detail=2.0), 0.55, 0.72)
    col = g.mix(col, "#5c2d17", g.mul(warm, 0.45))
    if scorch:
        hot = g.smooth(g.noise(p, 0.7, detail=3.0), 0.35, 0.7)
        col = g.mix(col, "#6e2410", g.mixf(0.5, 0.85, hot))
    ash = g.mul(g.smooth(nz, 0.1 if top else 0.4, 0.45 if top else 0.75), g.smooth(g.noise(p, 0.35), 0.3, 0.6))
    col = g.mix(col, "#6a645e" if top else "#6e6862", g.mul(ash, 0.75 if not scorch else 0.3))
    g.viewport("#5a1a0a" if scorch else "#2e2723", 0.85)
    g.output(g.principled(base_color=col, roughness=0.86, normal=g.bump(g.mul(joint, -1.0), 0.35, 0.08)))


M.register("icefire_isl_ice", _ice_surface, top=False)
M.register("icefire_isl_snow", _ice_surface, top=True)
M.register("icefire_isl_basalt", _basalt_surface, top=False)
M.register("icefire_isl_cinder", _basalt_surface, top=True)
M.register("icefire_isl_scorch", _basalt_surface, top=False, scorch=True)
MATERIALS = ("icefire_isl_ice", "icefire_isl_snow", "icefire_isl_basalt", "icefire_isl_cinder", "icefire_isl_scorch")


# ================================================================================================ layout

def view_from_hold(rock):
    """(azimuth, rock-local position) of HOLD_CAM in the rock's frame."""
    q = rock.matrix_world.inverted() @ Vector(HOLD_CAM)
    return math.atan2(q.y, q.x), q


def falls_of(rock, reach=45.0):
    """build_islands' waterfalls pouring off this rock ('scenery.island.fall*' Empties with their sheets as children,
    the lip on the rock's top), rock-local: [dict(name, az, half, z (descending), r: the sheets' least radius per
    z)]."""
    Mi = rock.matrix_world.inverted()
    out = []
    for o in sorted(bpy.data.objects, key=lambda x: x.name):
        if o.parent is not None or o.type != 'EMPTY' or not o.name.startswith("scenery.island.fall"):
            continue
        lp = Mi @ o.matrix_world.translation
        if math.hypot(lp.x, lp.y) > reach or abs(lp.z) > 3.0:
            continue
        pts = []
        for ch in sorted(o.children_recursive, key=lambda x: x.name):
            if ch.type != 'MESH' or not len(ch.data.vertices):
                continue
            co = np.empty(len(ch.data.vertices) * 3)
            ch.data.vertices.foreach_get("co", co)
            Mc = np.array(Mi @ ch.matrix_world)
            pts.append(co.reshape(-1, 3) @ Mc[:3, :3].T + Mc[:3, 3])
        if not pts:
            continue
        co = np.concatenate(pts)
        co = co[co[:, 2] > -FALL_DEPTH]
        th0 = math.atan2(lp.y, lp.x)
        ang = np.arctan2(co[:, 1], co[:, 0]) - th0
        ang = np.arctan2(np.sin(ang), np.cos(ang))
        rr = np.hypot(co[:, 0], co[:, 1])
        zs = np.arange(0.5, -FALL_DEPTH - 1.0, -1.0)
        rmin = []
        for z in zs:
            s = np.abs(co[:, 2] - z) < 0.75
            rmin.append(float(rr[s].min()) if s.any() else (rmin[-1] if rmin else float(rr.min())))
        out.append(dict(name=o.name, az=th0, half=max(float(np.abs(ang).max()), math.radians(4.0)), z=zs,
                        r=np.array(rmin), lip=tuple(lp)))
    return out


def layout(rock, falls=None):
    """Where the halves go (rock-local azimuths, radians): dict(view_az, fire_az, ice_az, side (+1: the fire half
    shows right of the camera's line, -1 left), turn (the extra turn a waterfall needed), lava_az (the lavafall's
    rim azimuth), volcano_az)."""
    view, q = view_from_hold(rock)
    falls = falls_of(rock) if falls is None else falls
    lim = math.radians(FALL_IN_ICE)
    best = None
    for side in (1, -1):
        ice0 = _wrap(view + math.radians(FIRE_FROM_VIEW) * side + math.pi)
        need = 0.0
        for f in falls:
            d = _wrap(f["az"] - ice0)
            if abs(d) > lim:
                n = d - math.copysign(lim, d)
                need = n if abs(n) > abs(need) else need
        if best is None or abs(need) < abs(best[1]) - 1e-9:
            best = (side, need, ice0)
    side, need, ice0 = best
    ice = _wrap(ice0 + need)
    fire = _wrap(ice + math.pi)
    toward = _wrap(view - fire)
    lava = _wrap(fire + 0.85 * max(-math.radians(45.0), min(math.radians(45.0), toward)))
    volc = _wrap(fire + 0.35 * max(-math.pi / 2, min(math.pi / 2, toward)))
    return dict(view_az=view, view_el=math.atan2(q.z, math.hypot(q.x, q.y)), view_d=q.length, fire_az=fire,
                ice_az=ice, side=side, turn=need, lava_az=lava, volcano_az=volc)


# ================================================================================================ shape

def _prof(t):
    if t <= TIP_KNEE:
        return (1.0 - t) ** PROF_P
    return (1.0 - TIP_KNEE) ** PROF_P * (1.0 - t) / (1.0 - TIP_KNEE)


class Shape:
    """The island's surfaces as functions: the rim, the top's height, the underside point at (azimuth, depth
    fraction t), the seams, and the chart's slant table."""

    def __init__(self, lay, falls):
        self.lay, self.falls = lay, falls
        self.fire = lay["fire_az"]
        a = math.radians(37.0) + self.fire
        self.tip = Vector((math.cos(a), math.sin(a), 0.0)) * TIP_OFF
        ts = np.linspace(0.0, 1.0, 4001)
        r0 = np.array([R_REF * _prof(t) for t in ts])
        z0 = -DEPTH * ts
        seg = np.hypot(np.diff(r0), np.diff(z0))
        self.ts, self.r0t = ts, r0
        self.s_of_t = np.concatenate([[0.0], np.cumsum(seg)])
        self.S = float(self.s_of_t[-1])
        self.seam_ph = (0.8, 2.3, 4.1, 1.7)
        # basalt beds, top down: (top z, bottom z, stick-out share)
        rb = random.Random(SEED + 11)
        self.beds = []
        z, base = 0.0, 0.0
        while z > -DEPTH - 2.0:
            th_ = rb.uniform(*BEDS)
            if rb.random() < BED_LEDGE:
                amp = base + rb.uniform(BED_AMP[1] * 0.6, BED_AMP[1])
            else:
                base = rb.uniform(-1.0, 1.0) * BED_AMP[0]
                amp = base
            self.beds.append((z, z - th_, amp))
            z -= th_

    def bed(self, z):
        """Stick-out share of the basalt bed at height z with a rounded shoulder at its top and an undercut at its
        foot (each bed's face is a ledge over the next)."""
        for (zt, zb, a) in self.beds:
            if z >= zb:
                h = zt - zb
                u = (zt - z) / h                       # 0 at the bed's top, 1 at its foot
                sh = _smooth(u, 0.0, 0.18)             # shoulder
                uc = 1.0 - 0.35 * _smooth(u, 0.82, 1.0)   # undercut
                return a * sh * uc
        return 0.0

    # -- chart
    def t_of_s(self, s):
        return float(np.interp(s, self.s_of_t, self.ts))

    def r0_s(self, s):
        return float(np.interp(s, self.s_of_t, self.r0t))

    # -- rim and gorge
    def cap(self, th, z):
        """The least radius the waterfalls allow at azimuth th, height z (inf away from them)."""
        best = 1e9
        for f in self.falls:
            d = abs(_wrap(th - f["az"]))
            w = 1.0 - _smooth(d, f["half"] + math.radians(2.0), f["half"] + math.radians(12.0))
            if w <= 0.0:
                continue
            rs = float(np.interp(-z, -f["z"], f["r"]))
            best = min(best, rs - FALL_CLEAR + (1.0 - w) * 40.0)
        return best

    def rim0(self, th):
        c = RIM_FOURIER
        r = c[0]
        for k in range(1, (len(c) - 1) // 2 + 1):
            r += c[2 * k - 1] * math.cos(k * th) + c[2 * k] * math.sin(k * th)
        r += RIM_JAG * U.fbm((math.cos(th) * 3.0, math.sin(th) * 3.0, 0.0), 1.0, 3, seed=SEED + 1)
        return r

    def rim(self, th):
        return min(self.rim0(th), self.cap(th, 0.0))

    def z_top(self, x, y):
        th = math.atan2(y, x)
        u = min(1.0, math.hypot(x, y) / max(1.0, self.rim(th)))
        k = 1.0 - u * u
        return TOP_DOME * k + TOP_NOISE * k * U.fbm((x * 0.08, y * 0.08, 0.0), 1.0, 3, seed=SEED + 2)

    # -- seams (azimuth from the fire centre, radians): the fire half is -seam_l(t) < a < seam_r(t)
    def seam_off(self, t, side):
        ph = self.seam_ph
        A1, A2, A3 = SEAM_WAVE
        o = 2 if side > 0 else 0
        w = (A1 * math.sin(math.pi * t * 1.6 + ph[o]) + A2 * math.sin(math.pi * t * 4.3 + ph[o + 1]) +
             A3 * math.sin(math.pi * t * 13.0 + 2.0 * ph[o]))
        w *= math.sin(math.pi * min(1.0, t / 0.1) * 0.5)          # 0 at the rim: the seams start on the rim's halves
        r = max(4.0, R_REF * _prof(t))
        return max(-0.4, min(0.4, w / r)) * (1.0 - t)

    def seam_at(self, t, side):
        """Chart azimuth (from the fire centre) of the right (side +1) or left (-1) seam at depth fraction t."""
        return side * (math.pi / 2 + self.seam_off(t, side))

    def into_ice(self, a, t):
        """Signed angle past the seam into the ice half (> 0: ice) at chart azimuth a."""
        side = 1 if a >= 0 else -1
        return abs(a) - abs(self.seam_at(t, side))

    # -- the underside
    def point(self, th, t):
        """Rock-local point of the underside at azimuth th, depth fraction t (t = 0: the rim)."""
        rim = self.rim(th)
        g = _prof(t)
        ramp = _smooth(t, 0.0, 0.05)
        c, s = math.cos(th), math.sin(th)
        z = -DEPTH * t
        Rl = rim * g
        a = _wrap(th - self.fire)
        wi = _smooth(self.into_ice(a, t), -0.08, 0.08)
        amp = min(1.0, Rl / 8.0) * ramp
        # buttress lobes and the deep clefts between them (as nature._PillarShape's major fissures)
        lob = U.fbm((c * 1.9, s * 1.9, z * 0.035), 1.0, 3, seed=SEED + 3)
        fm = N_MAJOR / (2 * math.pi) * 1.15
        w1 = 0.25 * U.noise3((c * 1.5, s * 1.5, z * 0.03), 1.0, seed=SEED + 8)
        g1 = 1.0 - abs(U.noise3((c * fm + w1, s * fm - w1, z * 0.6 / R_REF), 1.0, seed=SEED + 9))
        fade = 0.55 + 0.45 * U.noise3((c * 0.7, s * 0.7, z * 0.04), 1.0, seed=SEED + 10)
        major = MAJOR * (g1 ** 3) * max(0.0, fade) * 1.4
        bulb = BULB * max(0.0, U.noise3((c * 2.6, s * 2.6, z * 0.08), 1.0, seed=SEED + 12)) ** 1.5
        bulb *= _smooth(t, 0.15, 0.45) * (1.0 - _smooth(t, 0.8, 0.95))
        r = Rl * (1.0 + (LOBE * lob - major + bulb) * ramp)
        if t < T_LIP:
            r += LIP * math.sin(math.pi * t / T_LIP)
        # ice: rounded vertical flutes and long melt runs; basalt: column facets and beds with ledges
        fl = abs(math.sin(N_FLUTE * th / 2.0)) ** 0.6 - 0.62
        ice_d = 0.7 * fl + 0.8 * U.fbm((c * 6.0, s * 6.0, z * 0.05), 1.0, 3, seed=SEED + 4)
        ph = (N_COL * (th + math.pi) / (2 * math.pi)) % 1.0
        col = abs(ph - 0.5) * 2.0 - 0.5
        bas_d = 0.5 * col + Rl * self.bed(z) + 0.6 * U.fbm((c * 5.0, s * 5.0, z * 0.12), 1.0, 3, seed=SEED + 5)
        r += amp * (wi * ice_d + (1.0 - wi) * bas_d)
        r += amp * CRAG * (0.35 + t) * U.fbm((c * 2.4, s * 2.4, z * 0.09), 1.0, 3, seed=SEED + 6)
        z += amp * 0.35 * U.fbm((c * 3.0, s * 3.0, z * 0.1), 1.0, 2, seed=SEED + 7)
        r = max(0.04, min(r, self.cap(th, z)))
        o = self.tip * (t * t)
        return (o.x + r * c, o.y + r * s, z)


# ================================================================================================ lava network

class Network:
    """The lava in chart coordinates (a: azimuth from the fire centre, s: slant metres under the rim): per crack a
    centre line [(a, s, width)], its kind and parent; the lavafall first (its outline starts on rim vertices)."""

    def __init__(self, S, rnd, rim_a, lava_j):
        self.S, self.rnd = S, rnd
        self.cracks = []
        self.rim_a = rim_a
        self.lava_j = lava_j

    def metric(self, a, s, a2, s2):
        r = max(0.5, self.S.r0_s(0.5 * (s + s2)))
        return math.hypot((a - a2) * r, s - s2)

    def ok(self, a, s, w, skip=()):
        """A centre point clear of the seams, the tip and the other cracks."""
        S, C = self.S, CRACKS
        t = S.t_of_s(s)
        r = S.r0_s(s)
        if r < C["tip_r"] or s > S.S - 4.0:
            return False
        if -S.into_ice(a, t) * r < C["seam_gap"] + w * 0.5:
            return False
        for k, cr in enumerate(self.cracks):
            if k in skip:
                continue
            for (a2, s2, w2) in cr["pts"][::2]:
                if abs(s2 - s) > 6.0:
                    continue
                if self.metric(a, s, a2, s2) < C["gap"] + 0.5 * (w + w2) + HALO:
                    return False
        return True

    def walk(self, a, s, length, w0, w1, step, heading=0.0, sigma=None, relax=0.5, skip=(), taper_in=False,
             run=None):
        rnd, C = self.rnd, CRACKS
        sigma = math.radians(C["sigma"]) if sigma is None else sigma
        run = C["run"] if run is None else run
        pts = []
        hd = heading
        walked = 0.0
        turn = math.radians(C["turn"])
        first = True
        while walked < length:
            if not first:
                nh = relax * hd + rnd.gauss(0.0, sigma)
                nh = max(hd - turn, min(hd + turn, nh))
                hd = max(-1.2, min(1.2, nh))
            first = False
            seg = rnd.uniform(*run)
            k = 0.0
            while k < seg and walked < length:
                u = walked / length
                w = w0 + (w1 - w0) * u
                if taper_in:
                    w *= min(1.0, 0.25 + walked / 3.0)
                w *= min(1.0, (length - walked) / 2.5 + 0.18)
                w = max(0.22, w)
                if not self.ok(a, s, w, skip):
                    return pts
                pts.append((a, s, w))
                r = max(1.0, self.S.r0_s(s))
                a += math.sin(hd) * step / r
                s += math.cos(hd) * step
                k += step
                walked += step
        return pts

    def add(self, pts, kind, parent=None):
        if len(pts) < 3:
            return None
        self.cracks.append(dict(pts=pts, kind=kind, parent=parent))
        return len(self.cracks) - 1

    def build(self):
        S, rnd, C, L = self.S, self.rnd, CRACKS, LAVAFALL
        # the lavafall: from the rim between rim vertices lava_j - 1 and lava_j - 1 + LAVA_RIM, straight-ish down,
        # then a tail
        a_mid = 0.5 * (self.rim_a[self.lava_j - 1] + self.rim_a[self.lava_j - 1 + LAVA_RIM])
        pts = [(a_mid, 1.0, L["width"][0])]
        a, s = a_mid, 1.0
        n = int(L["length"] / C["step"])
        for i in range(1, n):
            u = i / n
            w = L["width"][0] + (L["width"][1] - L["width"][0]) * u
            r = max(1.0, S.r0_s(s))
            if i > 3:                                   # straight down off the rim, then a slow meander
                a += 0.5 * math.sin(i * 0.55 + 1.3) * C["step"] / r
            s += C["step"]
            if not self.ok(a, s, w):
                break
            pts.append((a, s, w))
        tail = self.walk(a, s + C["step"], L["tail"], L["width"][1], L["tail_w"], C["step"], heading=0.0,
                         relax=0.6)
        lf = self.add(pts + tail, "lava")
        mains = [lf] if lf is not None else []
        # the mains, from just under the rim (skipping the lavafall's own azimuth)
        for deg in C["mains"]:
            a0 = math.radians(deg) + rnd.uniform(-0.05, 0.05)
            if abs(_wrap(a0 - a_mid)) * R_REF < 7.0:
                rnd.random()
                continue
            s0 = rnd.uniform(*C["start"])
            pts = self.walk(a0, s0, rnd.uniform(*C["length"]), rnd.uniform(*C["width"]), 0.45, C["step"],
                            heading=rnd.gauss(0.0, 0.25), taper_in=True)
            k = self.add(pts, "main")
            if k is not None:
                mains.append(k)
        # forks off the mains (and the lavafall's tail), at 35-70 deg
        for k in list(mains):
            pts = self.cracks[k]["pts"]
            for _f in range(rnd.randint(*C["forks"])):
                i = rnd.randint(int(len(pts) * 0.25), max(int(len(pts) * 0.25), int(len(pts) * 0.8) - 1))
                a, s, w = pts[i]
                hd = rnd.choice((-1, 1)) * math.radians(rnd.uniform(35.0, 70.0))
                fk = self.walk(a, s, rnd.uniform(*C["fork_len"]), max(0.35, w * C["fork_w"]), 0.25, C["step"] * 0.8,
                               heading=hd, relax=0.75, skip=(k,))
                self.add(fk, "fork", parent=k)
        # cross cracks along the strata near the rim
        for _c in range(C["cross"]):
            a0 = rnd.uniform(-1.2, 1.2)
            pts = self.walk(a0, rnd.uniform(3.0, 7.0), rnd.uniform(6.0, 11.0), 0.6, 0.3, C["step"] * 0.8,
                            heading=rnd.choice((-1, 1)) * 1.25, sigma=math.radians(8.0), relax=0.97, taper_in=True)
            self.add(pts, "cross")
        return self


def _offset_line(pts, S, extra=0.0):
    """Left and right outlines (chart (a, s)) of a centre line [(a, s, w)] at w/2 + extra each side (metric
    perpendicular)."""
    L, R = [], []
    n = len(pts)
    for i in range(n):
        a, s, w = pts[i]
        a1, s1, _ = pts[min(i + 1, n - 1)]
        a0, s0, _ = pts[max(i - 1, 0)]
        r = max(0.6, S.r0_s(s))
        tx, ty = (a1 - a0) * r, (s1 - s0)
        ln = math.hypot(tx, ty) or 1.0
        tx, ty = tx / ln, ty / ln
        nx, ny = -ty, tx
        h = 0.5 * w + extra
        L.append((a + nx * h / r, max(0.6, s + ny * h)))       # never up to the rim row
        R.append((a - nx * h / r, max(0.6, s - ny * h)))
    return L, R


# ================================================================================================ the rock mesh

class Chart:
    """Points, constraint edges and faces for one delaunay_2d_cdt call."""

    def __init__(self):
        self.v = []                  # (x, y)
        self.meta = []               # per input vertex: dict or None
        self.edges = []
        self.faces = []
        self.face_kind = []

    def add(self, x, y, meta=None):
        self.v.append((x, y))
        self.meta.append(meta)
        return len(self.v) - 1

    def chain(self, idx, closed=False):
        for a, b in zip(idx, idx[1:]):
            if a != b:
                self.edges.append((a, b))
        if closed and len(idx) > 2:
            self.edges.append((idx[-1], idx[0]))

    def face(self, idx, kind):
        """A constraint face (its inside is marked in orig_faces): delaunay_2d_cdt takes a face's inside to be on the
        left of its edges, so every face goes in counter-clockwise."""
        idx = [i for k, i in enumerate(idx) if k == 0 or i != idx[k - 1]]
        if len(idx) > 2 and idx[0] == idx[-1]:
            idx = idx[:-1]
        if len(idx) >= 3:
            p = [self.v[i] for i in idx]
            a2 = sum(p[k][0] * p[(k + 1) % len(p)][1] - p[(k + 1) % len(p)][0] * p[k][1] for k in range(len(p)))
            if a2 < 0:
                idx = idx[::-1]
            self.faces.append(idx)
            self.face_kind.append(kind)

    def run(self, output_type):
        res = MG.delaunay_2d_cdt([Vector(p) for p in self.v], self.edges, self.faces, output_type, 1e-6, True)
        return res


def _resample(poly, step, metric):
    """Points along a polyline (list of (a, s)) every <= step metres (metric(p, q) the distance)."""
    out = [poly[0]]
    for p, q in zip(poly, poly[1:]):
        d = metric(p, q)
        n = max(1, int(math.ceil(d / step)))
        for k in range(1, n + 1):
            u = k / n
            out.append((p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u))
    return out


def build_rock_mesh(S, lay, rnd, log=_log):
    """The rock: underside chart + top chart, welded at the rim, the tip closed in one vertex, lava sunk in.
    Returns (bmesh, info)."""
    fire = S.fire
    info = {}
    # ---- the rim: azimuths from the fire centre (chart a), -pi first; the same vertices close the top
    n_rim = int(round(2 * math.pi * R_REF / H_RIM))
    rim_a = [-math.pi + 2 * math.pi * j / n_rim for j in range(n_rim)]
    lava_a = _wrap(lay["lava_az"] - fire)
    lava_j = min(range(1, n_rim - LAVA_RIM - 1),
                 key=lambda j: abs(rim_a[j - 1] + math.pi * LAVA_RIM / n_rim - lava_a))
    lava_jr = lava_j - 1 + LAVA_RIM
    seam_j = {sd: min(range(n_rim), key=lambda j: abs(_wrap(rim_a[j] - sd * math.pi / 2))) for sd in (1, -1)}
    net = Network(S, rnd, rim_a, lava_j).build()
    info["cracks"] = {k: sum(1 for c in net.cracks if c["kind"] == k) for k in ("lava", "main", "fork", "cross")}
    info["crack_len_m"] = round(sum(len(c["pts"]) for c in net.cracks) * CRACKS["step"], 1)

    def metric(p, q):
        r = max(0.6, S.r0_s(0.5 * (p[1] + q[1])))
        return math.hypot((p[0] - q[0]) * r, p[1] - q[1])

    # ---- underside chart
    U_ = Chart()
    rim_idx = [U_.add(a * C_X, 0.0, dict(rim=j, a=a, s=0.0)) for j, a in enumerate(rim_a)]
    rim_dup = U_.add(math.pi * C_X, 0.0, dict(rim=0, a=math.pi, s=0.0, dup=True))
    cons = []                                       # constraint sample points (a, s) for pruning
    vdepth = {}                                     # input vertex -> inset depth
    # seams: from the rim vertex at +-pi/2 down to the last row
    s_end = None
    rows = list(ROWS_TOP)
    s = ROWS_TOP[-1] + H
    while True:
        if S.r0_s(s) < TIP_STOP:
            break
        rows.append(s)
        s += H
    s_end = rows[-1]
    seam_idx = {}
    for sd in (1, -1):
        idx = [rim_idx[seam_j[sd]]]
        pts = []
        s = 0.9
        while s < s_end - 0.3:
            pts.append((S.seam_at(S.t_of_s(s), sd), s))
            s += 0.9
        for a, s in pts:
            idx.append(U_.add(a * C_X, -s, dict(a=a, s=s, seam=sd)))
            cons.append((a, s))
        seam_idx[sd] = idx
    # cracks: outline faces, halos, centre lines
    halos = []
    for ci, cr in enumerate(net.cracks):
        pts = cr["pts"]
        Lo, Ro = _offset_line(pts, S)
        rim_l = rim_r = None
        if cr["kind"] == "lava":
            # the lavafall's outline starts on two rim vertices 3 m apart; the rim between them is its top edge
            rim_l, rim_r = lava_j - 1, lava_jr
            if (Lo[0][0] - Ro[0][0]) * (rim_a[rim_l] - rim_a[rim_r]) < 0:
                rim_l, rim_r = rim_r, rim_l
        fidx = [rim_idx[rim_l]] if rim_l is not None else []
        for a, s in _resample(Lo, 0.8, metric) + list(reversed(_resample(Ro, 0.8, metric))):
            fidx.append(U_.add(a * C_X, -s, dict(a=a, s=s)))
            cons.append((a, s))
        if rim_r is not None:
            stp = 1 if rim_l > rim_r else -1
            fidx += [rim_idx[j] for j in range(rim_r, rim_l, stp)]
        U_.face(fidx, ("lava" if cr["kind"] == "lava" else "crack", ci))
        cidx = []
        for a, s, w in pts:
            k = U_.add(a * C_X, -s, dict(a=a, s=s, centre=ci))
            d = INSET["lava" if cr["kind"] == "lava" else "crack"] * min(1.0, w / 1.4)
            vdepth[k] = max(0.18, d)
            cidx.append(k)
            cons.append((a, s))
        U_.chain(cidx)
        # the halo, clear of the rim
        hp = [p for p in pts if p[1] > 1.8]
        if len(hp) >= 3:
            Lh, Rh = _offset_line(hp, S, HALO)
            hr = Lh + list(reversed(Rh))
            hr = _resample(hr + [hr[0]], 0.9, metric)[:-1]
            hidx = []
            for a, s in hr:
                hidx.append(U_.add(a * C_X, -s, dict(a=a, s=s)))
                cons.append((a, s))
            U_.face(hidx, ("halo", ci))
            halos.append(ci)
    # rows (after the constraints: pruned near them)
    kd = kdtree.KDTree(len(cons))
    for i, (a, s) in enumerate(cons):
        r = S.r0_s(s)
        kd.insert(Vector((r * math.cos(a), r * math.sin(a), -s)), i)
    kd.balance()
    row_ends = []
    n_pruned = 0
    for ri, s in enumerate(rows):
        if ri == 0:
            row_ends.append((rim_idx[0], rim_dup))
            continue
        r = S.r0_s(s)
        n = n_rim if ri < len(ROWS_TOP) else max(5, int(math.ceil(2 * math.pi * r / H)))
        first = last = None
        for j in range(n):
            a = -math.pi + 2 * math.pi * j / n
            ss = s
            if ri >= len(ROWS_TOP) and j:
                a += rnd.uniform(-0.22, 0.22) * 2 * math.pi / n
                ds = rnd.uniform(-0.12, 0.12) * H
                if ri < len(rows) - 1:          # the last row stays on one line: the chart's bottom edge
                    ss += ds
            if j and ri < len(rows) - 1:
                rr = S.r0_s(ss)
                if kd.find_range(Vector((rr * math.cos(a), rr * math.sin(a), -ss)), PRUNE):
                    n_pruned += 1
                    continue
            k = U_.add(a * C_X, -ss, dict(a=a, s=ss, row=ri))
            if j == 0:
                first = k
        last = U_.add(math.pi * C_X, -U_.meta[first]["s"], dict(a=math.pi, s=U_.meta[first]["s"], row=ri, dup=True))
        row_ends.append((first, last))
    # the seams end on the last row
    for sd in (1, -1):
        U_.chain(seam_idx[sd])
    info["chart_points"] = len(U_.v)
    info["pruned"] = n_pruned
    res = U_.run(0)
    ov, oe, of, oov, ooe, oof = res
    # ---- underside: map chart vertices to 3D
    out_meta = []
    for i, p in enumerate(ov):
        src = oov[i]
        m = U_.meta[src[0]] if src else None
        if m is not None:
            a, s = m["a"], m["s"]
        else:
            a, s = p.x / C_X, -p.y
        out_meta.append((a, s, m, src))
    # checks: no new vertex on the rim, the wrap lines or the last row
    bad = []
    for i, (a, s, m, src) in enumerate(out_meta):
        if not src and (s < 1e-4 or abs(abs(a) - math.pi) < 1e-6 or s > s_end - 1e-4):
            bad.append((round(a, 4), round(s, 4)))
    if bad:
        raise RuntimeError("icefire_island: the underside chart split a boundary edge at %s" % bad[:6])
    # ---- top chart (x, y), the rim polygon first
    T_ = Chart()
    rim_xy = []
    for j, a in enumerate(rim_a):
        p = S.point(fire + a, 0.0)
        rim_xy.append(p)
        T_.add(p[0], p[1], dict(rim=j))
    T_.face(list(range(n_rim)), ("top", -1))
    # the top seam: rim vertex seam_j[+1] to seam_j[-1], wavy, through the middle
    A = Vector(rim_xy[seam_j[1]][:2])
    B = Vector(rim_xy[seam_j[-1]][:2])
    ei = _dir(S.lay["ice_az"]).to_2d()
    tops = [seam_j[1]]
    seam_pts = [tuple(A)]
    nseg = int((B - A).length / 1.6)
    for k in range(1, nseg):
        u = k / nseg
        p = A.lerp(B, u) + ei * (2.2 * math.sin(math.pi * u) * math.sin(2.6 * math.pi * u + 0.7) +
                                 0.9 * math.sin(7.0 * math.pi * u + 2.0) * math.sin(math.pi * u))
        tops.append(T_.add(p.x, p.y, dict(seam=True)))
        seam_pts.append((p.x, p.y))
    tops.append(seam_j[-1])
    seam_pts.append(tuple(B))
    T_.chain(tops)
    S.top_seam = np.array(seam_pts)
    eb = Vector((-ei.y, ei.x))
    S.top_seam_ab = np.array([(Vector(p).dot(eb), Vector(p).dot(ei)) for p in seam_pts])
    order = np.argsort(S.top_seam_ab[:, 0])
    S.top_seam_ab = S.top_seam_ab[order]
    # streams on the top: from under the volcano to the lavafall's rim vertices, and to the glacier's snout
    V = VOLCANO
    vc = _dir(lay["volcano_az"]).to_2d() * V["r"]
    S.volcano_xy = vc
    rimL = Vector(rim_xy[lava_j - 1][:2])
    rimR = Vector(rim_xy[lava_jr][:2])
    rimM = (rimL + rimR) * 0.5
    end1 = rimM - rimM.normalized() * 0.8
    d1 = (end1 - vc).normalized()
    start1 = vc + d1 * (V["base_r"] - 1.8)
    S.flow1_az = math.atan2(d1.y, d1.x)
    # stream 2: toward the snout (the seam point nearest the volcano), ending inside the snout gap
    ab_v = (vc.dot(eb), vc.dot(ei))
    sd_v = float(np.interp(ab_v[0], S.top_seam_ab[:, 0], S.top_seam_ab[:, 1]))
    tgt = eb * ab_v[0] + ei * (sd_v + GLACIER["snout"] - 0.9)
    d2 = (tgt - vc).normalized()
    start2 = vc + d2 * (V["base_r"] - 1.8)
    S.flow2_az = math.atan2(d2.y, d2.x)
    S.stream2_end = tgt
    streams = []
    for name, p0, p1, w0, w1, rim_end in (("stream1", start1, end1, TOP_STREAM["w1"][0], TOP_STREAM["w1"][1], True),
                                          ("stream2", start2, tgt, TOP_STREAM["w2"], TOP_STREAM["w2"] * 0.85, False)):
        L = (p1 - p0).length
        n = max(4, int(L / 0.8))
        side = Vector((-(p1 - p0).y, (p1 - p0).x)).normalized()
        cl = []
        for k in range(n + 1):
            u = k / n
            m = TOP_STREAM["meander"] * math.sin(u * 6.0 + 0.4) * math.sin(math.pi * u)
            q = p0.lerp(p1, u) + side * m
            cl.append((q.x, q.y, w0 + (w1 - w0) * u))
        streams.append((name, cl, rim_end))
    for si, (name, cl, rim_end) in enumerate(streams):
        Lp, Rp = [], []
        for i, (x, y, w) in enumerate(cl):
            x1, y1, _ = cl[min(i + 1, len(cl) - 1)]
            x0, y0, _ = cl[max(i - 1, 0)]
            t2 = Vector((x1 - x0, y1 - y0)).normalized()
            nn = Vector((-t2.y, t2.x))
            Lp.append(Vector((x, y)) + nn * 0.5 * w)
            Rp.append(Vector((x, y)) - nn * 0.5 * w)
        ring_i = [T_.add(p.x, p.y, dict()) for p in (Lp[:-1] if rim_end else Lp)]
        if rim_end:
            # the outline ends on the lavafall's rim vertices (the left one is the one on the left of travel) and
            # runs along the rim between them
            tr = Vector((cl[-1][0] - cl[-2][0], cl[-1][1] - cl[-2][1]))
            left_is_L = (tr.x * (rimL - rimM).y - tr.y * (rimL - rimM).x) > 0
            jl, jr = (lava_j - 1, lava_jr) if left_is_L else (lava_jr, lava_j - 1)
            stp = 1 if jr > jl else -1
            ring_i += list(range(jl, jr + stp, stp))
        ring_i += [T_.add(p.x, p.y, dict()) for p in reversed(Rp[:-1] if rim_end else Rp)]
        T_.face(ring_i, ("lava", 100 + si))
        cidx = []
        for x, y, w in cl:
            k = T_.add(x, y, dict(centre=100 + si))
            cidx.append(k)
        T_.chain(cidx)
        for k, (_x, _y, w) in zip(cidx, cl):
            vdepth[("top", k)] = max(0.2, INSET["lava"] * min(1.0, w / 2.6))
        # the halo, clear of the rim
        hl = [c for c in cl if Vector(c[:2]).length < S.rim(math.atan2(c[1], c[0])) - 2.5]
        if len(hl) >= 3:
            Lh, Rh = [], []
            for i, (x, y, w) in enumerate(hl):
                x1, y1, _ = hl[min(i + 1, len(hl) - 1)]
                x0, y0, _ = hl[max(i - 1, 0)]
                t2 = Vector((x1 - x0, y1 - y0)).normalized()
                nn = Vector((-t2.y, t2.x))
                Lh.append(Vector((x, y)) + nn * (0.5 * w + HALO))
                Rh.append(Vector((x, y)) - nn * (0.5 * w + HALO))
            hidx = [T_.add(p.x, p.y, dict()) for p in Lh + list(reversed(Rh))]
            T_.face(hidx, ("halo", 100 + si))
    # interior points: a jittered grid inside the rim, clear of the constraints
    tc = [Vector((x, y, 0.0)) for (x, y) in T_.v[n_rim:]]
    kt = kdtree.KDTree(max(1, len(tc)))
    for i, p in enumerate(tc):
        kt.insert(p, i)
    kt.balance()
    R = R_REF + 4.0
    n_top = 0
    yv = -R
    row = 0
    while yv <= R:
        xv = -R + (TOP_H * 0.5 if row % 2 else 0.0)
        while xv <= R:
            x = xv + rnd.uniform(-0.2, 0.2) * TOP_H
            y = yv + rnd.uniform(-0.2, 0.2) * TOP_H
            th = math.atan2(y, x)
            if math.hypot(x, y) < S.rim(th) - 1.3 and not kt.find_range(Vector((x, y, 0.0)), 0.45 * TOP_H):
                T_.add(x, y, None)
                n_top += 1
            xv += TOP_H
        yv += TOP_H * 0.866
        row += 1
    resT = T_.run(1)
    tv, te, tf, tov, toe, tof = resT
    for i, src in enumerate(tov):
        if not src:
            p = tv[i]
            th = math.atan2(p.y, p.x)
            if math.hypot(p.x, p.y) > S.rim(th) - 0.05:
                raise RuntimeError("icefire_island: the top chart split the rim near %s" % (tuple(p),))
    rim_out_top = {}
    for i, src in enumerate(tov):
        for s_ in src:
            if s_ < n_rim:
                rim_out_top[i] = s_
    if len(set(rim_out_top.values())) != n_rim:
        raise RuntimeError("icefire_island: the top chart lost rim vertices (%d of %d)" % (
            len(set(rim_out_top.values())), n_rim))
    # ---- one bmesh
    bm = bmesh.new()
    rim_bv = {}
    under_bv = [None] * len(ov)
    left_col = {}
    for i, (a, s, m, src) in enumerate(out_meta):
        if m is not None and "rim" in m:
            j = m["rim"]
            if j not in rim_bv:
                p = S.point(fire + rim_a[j], 0.0)
                rim_bv[j] = bm.verts.new(p)
            under_bv[i] = rim_bv[j]
    # the wrap: the left column (a = -pi) owns its vertices; the right column (+pi) reuses them by depth
    for i, (a, s, m, src) in enumerate(out_meta):
        if under_bv[i] is None and abs(a + math.pi) < 1e-7:
            under_bv[i] = bm.verts.new(S.point(fire + a, S.t_of_s(s)))
            left_col[round(s, 6)] = under_bv[i]
    for i, (a, s, m, src) in enumerate(out_meta):
        if under_bv[i] is not None:
            continue
        if abs(a - math.pi) < 1e-7:
            v = left_col.get(round(s, 6))
            if v is None:
                raise RuntimeError("icefire_island: wrap vertex at s %.4f has no partner" % s)
            under_bv[i] = v
            continue
        under_bv[i] = bm.verts.new(S.point(fire + a, S.t_of_s(min(s, S.S))))
    kinds = U_.face_kind
    n_mat = [0] * 6
    for fi, f in enumerate(of):
        vs = [under_bv[k] for k in f]
        if len(set(vs)) < 3:
            continue
        ks = [kinds[x] for x in oof[fi]] if oof[fi] else []
        if any(k[0] in ("lava", "crack") for k in ks):
            mat = MOLTEN
        else:
            ca = sum(out_meta[k][0] for k in f) / 3.0
            cs = sum(out_meta[k][1] for k in f) / 3.0
            ice = S.into_ice(ca, S.t_of_s(cs)) > 0
            if any(k[0] == "halo" for k in ks) and not ice:
                mat = SCORCH
            else:
                mat = ICE if ice else BASALT
        try:
            bf = bm.faces.new(vs)
        except ValueError:
            continue
        bf.material_index = mat
        bf.smooth = True
        n_mat[mat] += 1
    # the tip: the last row's vertices round one point
    last = sorted([(out_meta[i][0], i) for i, (a, s, m, src) in enumerate(out_meta)
                   if m is not None and m.get("row") == len(rows) - 1])
    ring = []
    for a, i in last:
        v = under_bv[i]
        if not ring or ring[-1] is not v:
            ring.append(v)
    if ring and ring[0] is ring[-1]:
        ring = ring[:-1]
    tip = bm.verts.new(S.point(fire, 1.0))
    for k in range(len(ring)):
        f = bm.faces.new((ring[k], ring[(k + 1) % len(ring)], tip))
        a_k = _wrap(fire + last[min(k, len(last) - 1)][0] - fire)
        f.material_index = ICE if S.into_ice(a_k, 0.99) > 0 else BASALT
        f.smooth = True
    info["tip_ring"] = len(ring)
    # the top
    top_bv = [None] * len(tv)
    for i, p in enumerate(tv):
        if i in rim_out_top:
            top_bv[i] = rim_bv[rim_out_top[i]]
        else:
            top_bv[i] = bm.verts.new((p.x, p.y, S.z_top(p.x, p.y)))
    tkinds = T_.face_kind
    for fi, f in enumerate(tf):
        vs = [top_bv[k] for k in f]
        if len(set(vs)) < 3:
            continue
        ks = [tkinds[x] for x in tof[fi]] if tof[fi] else []
        cx = sum(tv[k].x for k in f) / len(f)
        cy = sum(tv[k].y for k in f) / len(f)
        if any(k[0] == "lava" for k in ks):
            mat = MOLTEN
        else:
            ab = Vector((cx, cy)).dot(eb), Vector((cx, cy)).dot(ei)
            ice = ab[1] > float(np.interp(ab[0], S.top_seam_ab[:, 0], S.top_seam_ab[:, 1]))
            if any(k[0] == "halo" for k in ks) and not ice:
                mat = SCORCH
            else:
                mat = SNOW if ice else CINDER
        try:
            bf = bm.faces.new(vs)
        except ValueError:
            continue
        bf.material_index = mat
        bf.smooth = True
        n_mat[mat] += 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    # sink the lava: a vertex whose every face is molten goes in along its normal
    vd_under = {}
    for i, (a, s, m, src) in enumerate(out_meta):
        for x in src:
            if x in vdepth:
                vd_under[under_bv[i]] = vdepth[x]
    for i, src in enumerate(tov):
        for x in src:
            if ("top", x) in vdepth:
                vd_under[top_bv[i]] = vdepth[("top", x)]
    moves = []
    n_sunk = 0
    for v in bm.verts:
        if not v.link_faces or any(f.material_index != MOLTEN for f in v.link_faces):
            continue
        d = vd_under.get(v, INSET["other"])
        moves.append((v, v.normal.copy() * d))
    for v, dv in moves:
        v.co -= dv
        n_sunk += 1
    # slivers where two constraint lines meet almost on a vertex: collapse them (the mesh stays closed)
    zero = [f for f in bm.faces if f.calc_area() < 1e-5]
    info["slivers"] = len(zero)
    info["sliver_at"] = [(tuple(round(c, 2) for c in f.calc_center_median()), round(min(e.calc_length()
                          for e in f.edges), 4), [f2.material_index for f2 in f.verts[0].link_faces][:6])
                         for f in zero[:6]]
    if zero:
        bmesh.ops.dissolve_degenerate(bm, dist=2e-3, edges=list({e for f in zero for e in f.edges}))
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.link_faces[0].material_index != e.link_faces[1].material_index:
            e.smooth = False
    bm.normal_update()
    info["sunk"] = n_sunk
    info["faces_by_mat"] = dict(zip(("ice", "basalt", "snow", "cinder", "molten", "scorch"), n_mat))
    info["rim_vertices"] = n_rim
    info["rows"] = len(rows)
    info["lava_j"] = lava_j
    S.rim_a = rim_a
    S.lava_rim = (rim_xy[lava_j - 1], rim_xy[lava_jr])
    return bm, info


def _bm_stats(bm):
    bad_e = sum(1 for e in bm.edges if not e.is_manifold)
    bnd = sum(1 for e in bm.edges if e.is_boundary)
    zero = sum(1 for f in bm.faces if f.calc_area() < 1e-6)
    return dict(verts=len(bm.verts), faces=len(bm.faces), tris=sum(len(f.verts) - 2 for f in bm.faces),
                open_edges=bnd, nonmanifold=bad_e, zero_area=zero)


# ================================================================================================ removal

VEG_WORDS = ("pine", "blossom", "peach", "shrub", "bamboo", "willow", "grass", "lotus")


def our_objects(rock):
    """This module's (and icefire_props') objects on ``rock``: the tagged children and the steam puffs."""
    out = [o for o in rock.children_recursive if o.get(TAG)]
    out += [o for o in bpy.data.objects if o.name.startswith(STEAM_PREFIX) and o not in out]
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


def clear(rock, log=_log):
    gone = _delete(our_objects(rock))
    if gone:
        log("previous icefire output removed", len(gone))
    return gone


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


def _plant_companions(rock, S=None):
    """Top-level plants standing on the rock's top: build_islands' top pines and blossoms, the life pass's peaches
    (origin inside the top's rim + 1.5 m, within 3 m of the top's height). Falls and anything else stay."""
    Mi = rock.matrix_world.inverted()
    me = rock.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    up = co[co[:, 2] > -1.0]
    rmax = float(np.hypot(up[:, 0], up[:, 1]).max()) if len(up) else 40.0
    ztop = float(co[:, 2].max()) if len(co) else 1.0
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
        if math.hypot(lp.x, lp.y) < rmax + 1.5 and -3.0 < lp.z < ztop + 3.0:
            out.append(o)
    return out


def strip_plants(rock, log=_log):
    gone = _delete(_plant_children(rock) + _plant_companions(rock))
    log("plants removed", len(gone), gone[:12], "..." if len(gone) > 12 else "")
    return gone


# ================================================================================================ parts

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
    vs = [bm.verts.new(p) for p in pts]
    res = bmesh.ops.convex_hull(bm, input=vs, use_existing_faces=False)
    for f in res["geom"]:
        if isinstance(f, bmesh.types.BMFace):
            f.smooth = False
    junk = list({v for v in res["geom_interior"] + res["geom_unused"]
                 if isinstance(v, bmesh.types.BMVert) and not v.link_faces})
    if junk:
        bmesh.ops.delete(bm, geom=junk, context='VERTS')


def _icicle(bm, top, length, radius, rnd, sides=6, mat=0, up=0.5):
    """A closed, slightly bent icicle (or rock spur) hanging from ``top`` (its top ring ``up`` m above, inside the
    support; a different height per icicle, so no two buried top caps lie in one plane)."""
    rings = (0.0, 0.18, 0.42, 0.7) if length < 4.0 else (0.0, 0.12, 0.3, 0.5, 0.72, 0.88)
    sway = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.0)) * length * 0.06
    ph = rnd.uniform(0, 6.28)
    loops = []
    for u in rings:
        r = radius * (1.0 - u) ** 1.25 * (1.0 + 0.12 * math.sin(u * 17.0 + ph))
        c = Vector(top) + Vector((0, 0, up - (length + up) * u)) + sway * u * u
        loops.append([bm.verts.new(c + Vector((math.cos(2 * math.pi * k / sides + ph) * r,
                                                  math.sin(2 * math.pi * k / sides + ph) * r, 0.0)))
                      for k in range(sides)])
    tip = bm.verts.new(Vector(top) + Vector((0, 0, -length)) + sway)
    for a, b in zip(loops, loops[1:]):
        for k in range(sides):
            f = bm.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]))
            f.smooth = True
            f.material_index = mat
    for k in range(sides):
        f = bm.faces.new((loops[-1][k], loops[-1][(k + 1) % sides], tip))
        f.smooth = True
        f.material_index = mat
    f = bm.faces.new(list(reversed(loops[0])))
    f.material_index = mat


def _in_fall(th, falls, margin=0.0):
    return any(abs(_wrap(th - f["az"])) < f["half"] + margin for f in falls)


class Cap:
    """Glacier cap over the ice half: a heightfield over (a, t), a along the seam (EB), t from the snout (0) to the
    outer edge (1, past the rim)."""

    def __init__(self, S, rnd):
        G = GLACIER
        self.S, self.G = S, G
        self.ei = _dir(S.lay["ice_az"]).to_2d()
        self.eb = Vector((-self.ei.y, self.ei.x))
        self.ph = [rnd.uniform(0, 6.28) for _ in range(8)]
        self._far = {}
        span = []
        a = -R_REF - 4.0
        while a <= R_REF + 4.0:
            d0 = self.d0(a)
            df = self.d_far(a, d0)
            if df is not None and df - d0 >= 2.2:
                span.append(a)
            a += 0.25
        self.a0, self.a1 = min(span) + 2.0, max(span) - 2.0     # the end walls stay off the rock's lip

    def seam_d(self, a):
        ab = self.S.top_seam_ab
        return float(np.interp(a, ab[:, 0], ab[:, 1]))

    def d0(self, a):
        return self.seam_d(a) + self.G["snout"]

    def xy(self, a, d):
        p = self.eb * a + self.ei * d
        return p.x, p.y

    def overhang(self, th):
        G = self.G
        u = 0.5 + 0.5 * math.sin(3.0 * th + self.ph[0]) * math.cos(5.0 * th + self.ph[1])
        return G["overhang"][0] + (G["overhang"][1] - G["overhang"][0]) * u

    def edge_r(self, th):
        r = self.S.rim(th) + self.overhang(th)
        for f in self.S.falls:
            if abs(_wrap(th - f["az"])) < f["half"] + math.radians(3.0):
                r = min(r, float(f["r"][0]) - self.G["fall_clear"])
        return r

    def d_far(self, a, d0):
        key = round(a, 5)
        if key not in self._far:
            d = d0
            res = None
            while d < R_REF + 12.0:
                x, y = self.xy(a, d)
                if math.hypot(x, y) > self.edge_r(math.atan2(y, x)):
                    res = d
                    break
                d += 0.2
            self._far[key] = res
        return self._far[key]

    def at(self, p):
        """(t, top z, bottom z) of the cap over the point p (x, y), or None off it."""
        a = Vector((p.x, p.y)).dot(self.eb)
        d = Vector((p.x, p.y)).dot(self.ei)
        if not self.a0 + 0.5 < a < self.a1 - 0.5:
            return None
        d0 = self.d0(a)
        df = self.d_far(a, d0) or (d0 + 2.2)
        t = (d - d0) / max(df - d0, 1e-6)
        if not 0.03 < t < 0.97:
            return None
        _x, _y, zt, zb, _in = self.point(a, t)
        return t, zt, zb

    def point(self, a, t):
        G, S = self.G, self.S
        d0 = self.d0(a)
        df = self.d_far(a, d0) or (d0 + 2.2)
        L = df - d0
        x, y = self.xy(a, d0 + t * L)
        th = math.atan2(y, x)
        r = math.hypot(x, y)
        rim = S.rim(th)
        inside = r < rim - 0.3
        z0 = S.z_top(x, y) if inside else 0.0
        s = t * L
        hmax = G["height"][0] + (G["height"][1] - G["height"][0]) * (0.5 + 0.5 * math.sin(0.13 * a + self.ph[2]))
        eh = G["edge_h"][0] + (G["edge_h"][1] - G["edge_h"][0]) * (0.5 + 0.5 * math.sin(0.31 * a + self.ph[3]))
        eh += 0.9 * U.fbm((x, y, 0.0), 0.27, 2, seed=813)
        h = G["snout_h"] + (hmax - G["snout_h"]) * _smooth(s, 0.0, 9.0)
        h += (eh - h) * _smooth(s, L - 5.0, L)
        h -= 0.9 * _smooth(s, L - 1.2, L)
        end = _smooth(min(a - self.a0, self.a1 - a), 0.0, 7.0)
        h *= 0.4 + 0.6 * end
        h += 0.55 * U.fbm((x, y, 0.0), 0.11, 3, seed=811) + 0.35 * U.fbm((x, y, 0.0), 0.33, 2, seed=812)
        h -= 0.7 * max(0.0, math.sin(0.62 * a + 0.25 * s + self.ph[4])) ** 10 * _smooth(s, 2.0, 6.0)
        top = z0 + max(1.0, h)
        if inside:
            bot = z0 - G["sink"]
        else:
            dr = G["droop"][0] + (G["droop"][1] - G["droop"][0]) * (0.5 + 0.5 * math.sin(2.0 * th + self.ph[5]))
            dr = max(0.6, dr + 0.9 * U.fbm((x, y, 0.0), 0.3, 2, seed=814))
            if _in_fall(th, S.falls, math.radians(3.0)):
                dr = 0.6
            k = _smooth(r, rim - 0.3, rim + 0.6)
            bot = (1 - k) * (z0 - G["sink"]) + k * (-0.35 - dr)
        return x, y, top, bot, inside


def _shard(bm, base, w, hh, rnd, lean, sink=1.3):
    """An ice shard (closed convex hull, flat facets): an uneven 5-6 point base ring about ``sink`` m under ``base``
    (in the cap), a narrower shoulder ring and one or two apex points, leaning by ``lean`` (m at the top)."""
    nb = rnd.choice((5, 6))
    yaw = rnd.uniform(0, 6.28)
    pts = []
    for c in range(nb):
        ang = yaw + c * 2 * math.pi / nb + rnd.uniform(-0.3, 0.3)
        rr = w * 0.5 * rnd.uniform(0.7, 1.0)
        pts.append(Vector(base) + Vector((math.cos(ang) * rr, math.sin(ang) * rr * 0.75,
                                          -sink * rnd.uniform(0.85, 1.0))))
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


def build_glacier(rock, S, rnd, log=_log):
    G = GLACIER
    cap = Cap(S, rnd)
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
    nser = 0
    k = 0
    shards = []
    while k < G["seracs"] + G["snout_seracs"]:
        snout = k >= G["seracs"]
        k += 1
        a = rnd.uniform(cap.a0 + 3.0, cap.a1 - 3.0)
        t = rnd.uniform(0.05, 0.16) if snout else rnd.uniform(0.8, 0.94)
        x, y, zt, zb, _in = cap.point(a, t)
        th = math.atan2(y, x)
        if not snout and _in_fall(th, S.falls, math.radians(3.0)):
            continue
        out = Vector((math.cos(th), math.sin(th), 0.0)) if not snout else Vector((-cap.ei.x, -cap.ei.y, 0.0))
        for _c in range(rnd.choice((1, 2, 2, 3))):
            w = rnd.uniform(1.3, 2.8)
            hh = rnd.uniform(3.0, 8.0) if not snout else rnd.uniform(2.2, 4.5)
            along = Vector((-out.y, out.x, 0.0))          # along the crest (or the snout), a little in from it
            j = along * rnd.uniform(-1.6, 1.6) - out * rnd.uniform(0.0, 0.6)
            lean = out * hh * rnd.uniform(0.08, 0.3) + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.0)) * 0.4
            q = Vector((x, y, zt)) + j
            at = cap.at(q)                                 # the cap where the shard stands
            if at is None or at[1] - at[2] < 1.2 or any((q - b).length < 0.6 * (w + wb) for b, wb in shards):
                continue                                   # off the cap, a thin edge, or on another shard
            q.z = at[1]
            shards.append((q, w))
            _shard(bm, q, w, hh, rnd, lean, sink=min(1.3, 0.55 * (at[1] - at[2])))
            nser += 1
    ob = _new_obj(rock, "glacier", bm, ["icefire_isl_ice"], smooth=math.radians(42))
    log("glacier", ob.name, "a", round(cap.a0, 1), round(cap.a1, 1), "shards", nser, "tris", _tris(ob.data))
    return ob, cap, edge


def build_icicles(rock, S, edge, sup, rnd, log=_log):
    C = ICICLES
    bm = bmesh.new()
    n = 0
    placed = []
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
        if _in_fall(th, S.falls, math.radians(C["fall_margin"])):
            continue
        if rnd.random() < C["skip"]:
            continue
        for _ in range(2 if rnd.random() < 0.35 else 1):
            lng = rnd.random() < C["long_share"]
            L = rnd.uniform(*(C["long"] if lng else C["short"]))
            r_out = rnd.uniform(-0.6, -0.15)
            px = x + math.cos(th) * r_out + rnd.uniform(-0.3, 0.3)
            py = y + math.sin(th) * r_out + rnd.uniform(-0.3, 0.3)
            up = sup.ray_cast(Vector((px, py, zb - 3.0)), Vector((0, 0, 1)), 6.0)[0]
            if up is None:
                continue
            pt = Vector((px, py, up.z))
            hit = sup.ray_cast(pt + Vector((0, 0, -0.6)), Vector((0, 0, -1)), L + 1.0)[0]
            if hit is not None:
                L = min(L, (pt.z - hit.z) - 0.8)
            if L < 1.0:
                continue
            rad = max(0.14, L * 0.085 + rnd.uniform(0.0, 0.12))
            if any(math.hypot(px - qx, py - qy) < 1.1 * (rad + qr) + 0.25 for qx, qy, qr in placed):
                continue                                  # two icicles in one place would share their faces
            placed.append((px, py, rad))
            _icicle(bm, pt, L, rad, rnd, C["sides"], up=rnd.uniform(0.9, 1.3))
            n += 1
    ob = _new_obj(rock, "icicles", bm, ["icefire_isl_ice"])
    log("icicles", ob.name, "count", n, "tris", _tris(ob.data))
    return ob


def build_stalactites(rock, S, sup, rnd, log=_log):
    """Ice stalactites under the ice half, basalt spurs under the fire half: from faces that lean down, clear of the
    lava, the seams and the waterfall, at least `spacing` apart, hanging straight down clear of the rock; faces
    turned toward the hold camera first. Plus a few spurs round the tip."""
    C = STALACTITES
    me = rock.data
    va = S.lay["view_az"]
    lava_pts = [p.center.copy() for p in me.polygons if p.material_index == MOLTEN]
    kl = kdtree.KDTree(max(1, len(lava_pts)))
    for i, c in enumerate(lava_pts):
        kl.insert(c, i)
    kl.balance()
    cand = {ICE: [], BASALT: []}
    for p in me.polygons:
        if p.material_index not in (ICE, BASALT):
            continue
        c = p.center
        if c.z > -6.0 or c.z < -DEPTH + 8.0:
            continue
        if _in_fall(math.atan2(c.y, c.x), S.falls, math.radians(6.0)):
            continue
        nrm = p.normal.copy()
        if nrm.z > -C["min_down"]:
            continue
        if lava_pts and kl.find_range(c, C["lava_clear"]):
            continue
        a = _wrap(math.atan2(c.y, c.x) - S.fire)
        t = min(1.0, -c.z / DEPTH)
        if abs(S.into_ice(a, t)) * max(2.0, math.hypot(c.x, c.y)) < 2.0:
            continue
        face = 0.25 + max(0.0, math.cos(math.atan2(nrm.y, nrm.x) - va))
        cand[p.material_index].append((c.copy(), nrm, p.area * face))
    bm = bmesh.new()
    placed = []
    counts = {}
    for mat, n_want, lens, rads, sides, mi in ((ICE, C["ice"], C["ice_len"], C["ice_r"], 6, 0),
                                               (BASALT, C["basalt"], C["bas_len"], C["bas_r"], 5, 1)):
        cl = cand[mat]
        rnd.shuffle(cl)
        cl.sort(key=lambda e: -e[2] * rnd.uniform(0.5, 1.5))
        got = 0
        for c, nrm, _a in cl:
            if got >= n_want:
                break
            if any((c - q).length < C["spacing"] for q in placed):
                continue
            L = rnd.uniform(*lens) * (0.6 + 0.4 * min(1.0, -c.z / 30.0))
            start = c + nrm * 0.15
            hit = sup.ray_cast(start + Vector((0, 0, -0.3)), Vector((0, 0, -1)), L + 1.5)[0]
            if hit is not None:
                L = min(L, start.z - hit.z - 1.0)
            if L < 2.5:
                continue
            top = c - nrm * 0.35
            rad = min(rads[1], max(rads[0], L * (0.07 if mat == ICE else 0.13)))
            _icicle(bm, top, L, rad, rnd, sides, mat=mi, up=rnd.uniform(0.4, 0.75))
            placed.append(c)
            got += 1
        counts["ice" if mat == ICE else "basalt"] = got
    # spurs round the tip: continue the point downward
    tip = min((v.co for v in me.vertices), key=lambda c: c.z)
    for k in range(C["tips"]):
        ang = S.fire + k * 2 * math.pi / C["tips"] + rnd.uniform(-0.4, 0.4)
        a = _wrap(ang - S.fire)
        ice = S.into_ice(a, 0.97) > 0
        p = Vector((tip.x + math.cos(ang) * 0.6, tip.y + math.sin(ang) * 0.6, tip.z + 2.2))
        L = rnd.uniform(5.0, 9.0) if k == 0 else rnd.uniform(2.5, 5.0)
        _icicle(bm, p, L, rnd.uniform(0.6, 0.9) if k == 0 else rnd.uniform(0.4, 0.6), rnd, 6 if ice else 5,
                mat=0 if ice else 1)
    counts["tip"] = C["tips"]
    ob = _new_obj(rock, "stalactites", bm, ["icefire_isl_ice", "icefire_isl_basalt"])
    log("stalactites", ob.name, counts, "candidates", {k: len(v) for k, v in cand.items()}, "tris", _tris(ob.data))
    return ob


def build_volcano(rock, S, rnd, log=_log):
    """A volcanic cone on the fire half: noisy concave flanks, a jagged rim with two notches (toward the two
    streams), a crater wall down to a molten pool, and a lava channel down each notch's flank: molten faces sunk
    into the flank, feeding the stream that starts under the cone's foot."""
    V = VOLCANO
    cx, cy = S.volcano_xy.x, S.volcano_xy.y
    zc = S.z_top(cx, cy)
    segs, rings, Hh = V["segs"], V["rings"], V["height"]
    flows = (S.flow1_az, S.flow2_az)
    ph = [rnd.uniform(0, 6.28) for _ in range(6)]
    bm = bmesh.new()
    loops = []
    radii = []
    for k in range(rings + 1):
        u = k / rings
        row = []
        rr = []
        for s in range(segs):
            th = 2 * math.pi * s / segs
            r = V["top_r"] + (V["base_r"] - V["top_r"]) * (1.0 - u) ** 1.7
            r *= 1.0 + (0.07 * math.sin(7 * th + ph[0] + 2.0 * u) + 0.04 * math.sin(13 * th + ph[1])) * (1.0 - u * 0.6)
            r *= 1.0 + 0.08 * U.fbm((math.cos(th) * 2.0, math.sin(th) * 2.0, u * 2.0), 1.0, 3, seed=821)
            x, y = cx + math.cos(th) * r, cy + math.sin(th) * r
            if k == 0:
                z = S.z_top(x, y) - V["sink"]
            else:
                z = zc + Hh * u
                if k == rings:
                    z += 0.7 * math.sin(5 * th + ph[2]) + 0.4 * math.sin(11 * th + ph[3])
                    for fa in flows:
                        z -= V["notch"] * math.exp(-(abs(_wrap(th - fa)) / 0.28) ** 2)
            row.append(bm.verts.new((x, y, z)))
            rr.append(r)
        loops.append(row)
        radii.append(rr)
    rim = loops[-1]
    zr = zc + Hh
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
    flank = set()
    for k in range(rings):
        u = (k + 0.5) / rings
        w = V["chan_w"][1] + (V["chan_w"][0] - V["chan_w"][1]) * u
        for s in range(segs):
            th = 2 * math.pi * (s + 0.5) / segs
            r = 0.5 * (radii[k][s] + radii[k + 1][s])
            for fi, fa in enumerate(flows):
                wf = w * (1.0 if fi == 0 else 0.75)
                c = fa + 0.08 * math.sin(u * 7.0 + fi * 2.0)
                if abs(_wrap(th - c)) * r < 0.5 * wf:
                    flank.add((k, s))
    nm = 0
    for ki, (a, b) in enumerate(zip(seq, seq[1:])):
        for s in range(segs):
            f = bm.faces.new((a[s], a[(s + 1) % segs], b[(s + 1) % segs], b[s]))
            f.smooth = True
            if (ki, s) in flank:
                f.material_index = 1
                nm += 1
    pc = bm.verts.new((cx, cy, zpool + 0.55))
    last = inner[-1]
    for s in range(segs):
        f = bm.faces.new((last[s], last[(s + 1) % segs], pc))
        f.material_index = 1
        f.smooth = True
    bc = bm.verts.new((cx, cy, zc - V["sink"] - 0.5))
    for s in range(segs):
        bm.faces.new((loops[0][(s + 1) % segs], loops[0][s], bc))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    moves = []
    for k in range(1, rings):
        for v in loops[k]:
            if all(f.material_index == 1 for f in v.link_faces):
                moves.append((v, v.normal.copy() * V["chan_inset"]))
    for v, d in moves:
        v.co -= d
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.link_faces[0].material_index != e.link_faces[1].material_index:
            e.smooth = False
    ob = _new_obj(rock, "volcano", bm, ["icefire_isl_basalt", "molten"], glow=LAVA_GLOW)
    log("volcano", ob.name, "centre", (round(cx, 1), round(cy, 1), round(zc, 2)), "flank faces", nm, "sunk",
        len(moves), "tris", _tris(ob.data))
    return ob, (cx, cy, zc)


def build_steam(rock, S, vc, rnd, log=_log):
    """A steam plume rising from the crater, drifting toward STEAM['drift_az'], and steam where the second stream
    meets the glacier's snout."""
    C = STEAM
    coll = rock.users_collection[0] if rock.users_collection else None
    t = math.radians(C["drift_az"])
    drift = Vector((math.cos(t), math.sin(t), 0.0))
    obs = []
    for (base, n, size0, dsize, seed0) in (
            (Vector((vc[0], vc[1], vc[2] + VOLCANO["height"] - VOLCANO["crater"] + 1.0)), C["plume"],
             C["plume_size"][0], C["plume_size"][1], 9100),
            (Vector((S.stream2_end.x, S.stream2_end.y, S.z_top(S.stream2_end.x, S.stream2_end.y) + 1.0)), C["snout"],
             C["snout_size"][0], C["snout_size"][1], 9200)):
        h = 0.0
        for k in range(n):
            size = size0 + dsize * k
            if k:
                h += C["overlap"] * size
            loc = base + Vector((0, 0, h)) + drift * (0.035 * h ** 1.5) + Vector(
                (rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.0)) * size * 0.1
            dens = max(0.16, C["density"][0] - C["density"][1] * k)
            ob = N.cloud_puff(coll, size=size, seed=seed0 + k, density=dens, flatten=rnd.uniform(0.8, 1.0),
                              name=STEAM_PREFIX, location=tuple(loc), parent=rock)
            ob[TAG] = "steam"
            obs.append(ob)
    log("steam", len(obs), "puffs")
    return obs


# ================================================================================================ build

def _tris(me):
    n = len(me.polygons)
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def _mesh_lists(ob):
    me = ob.data
    return [tuple(v.co) for v in me.vertices], [list(p.vertices) for p in me.polygons]


def _support_bvh(meshes):
    vs, ps = [], []
    for co, polys in meshes:
        off = len(vs)
        vs.extend(co)
        ps.extend([[i + off for i in p] for p in polys])
    return BVHTree.FromPolygons(vs, ps)


def replace_rock_mesh(rock, bm):
    """Give ``rock`` the mesh in ``bm`` (same mesh name, ROCK_MATS slots); the old mesh is freed."""
    old = rock.data
    name = old.name
    old.name = "~icefire.old"
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    U.set_materials(me, list(ROCK_MATS))
    me.update()
    rock.data = me
    for s in rock.material_slots:
        if s.link != 'DATA':
            s.link = 'DATA'
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return me


def build(rock, log=_log):
    """Make ``rock`` (scenery.island.009) Ice-Fire Island. Idempotent. Returns {part: object or list, 'info': dict}."""
    if rock is None or rock.type != 'MESH':
        raise RuntimeError("icefire_island: no rock mesh")
    rnd = random.Random(U.seed_from(KEY, rock.name))
    clear(rock, log)
    strip_plants(rock, log)
    for nm in MATERIALS + ("molten",):
        M.rebuild(nm) if nm in MATERIALS else M.get(nm)
    falls = falls_of(rock)
    lay = layout(rock, falls)
    log("layout: hold camera at azimuth %.1f deg, %.1f deg up, %.0f m; fire half at %.1f, ice half at %.1f (side %+d,"
        " extra turn %.1f deg); lavafall at %.1f, volcano at %.1f; falls %s" % (
            math.degrees(lay["view_az"]), math.degrees(lay["view_el"]), lay["view_d"], math.degrees(lay["fire_az"]),
            math.degrees(lay["ice_az"]), lay["side"], math.degrees(lay["turn"]), math.degrees(lay["lava_az"]),
            math.degrees(lay["volcano_az"]),
            [(f["name"], round(math.degrees(f["az"]), 1), round(math.degrees(f["half"]), 1)) for f in falls]))
    S = Shape(lay, falls)
    bm, info = build_rock_mesh(S, lay, rnd, log)
    st = _bm_stats(bm)
    info.update(st)
    replace_rock_mesh(rock, bm)
    rock["glow"] = LAVA_GLOW
    rock[BUILD_PROP] = VERSION
    log("rock", rock.name, info)
    glacier, cap, edge = build_glacier(rock, S, rnd, log)
    sup_cap = _support_bvh([_mesh_lists(rock), _mesh_lists(glacier)])
    icicles = build_icicles(rock, S, edge, sup_cap, rnd, log)
    stal = build_stalactites(rock, S, sup_cap, rnd, log)
    volcano, vc = build_volcano(rock, S, rnd, log)
    steam = build_steam(rock, S, vc, rnd, log)
    out = dict(glacier=glacier, icicles=icicles, stalactites=stal, volcano=volcano, steam=steam,
               info=dict(info, layout={k: (round(math.degrees(v), 2) if k.endswith("az") or k in ("turn", "view_el")
                                           else v) for k, v in lay.items()}))
    for k in PARTS:
        if _tris(out[k].data) > TRI_CAP:
            log("WARN", out[k].name, "has", _tris(out[k].data), "triangles >", TRI_CAP)
    if st["tris"] > ROCK_TRI_CAP:
        log("WARN", rock.name, "has", st["tris"], "triangles >", ROCK_TRI_CAP)
    return out
