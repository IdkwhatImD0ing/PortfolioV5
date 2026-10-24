"""Life on the mountains (pass 2): pines and big shrubs clinging to the 11 m rock layers of every peak in tiers
(the Huangshan look), pink peach-blossom clusters on those tiers and on the floating islands, and signs of the sect
living out there: small shrines and pagodas with glowing lanterns on distant peak tops that the hold cameras see,
and a chain bridge between two of them.

Complements pass 1 (scenery.build_density / sect/patch_density.py: denser cliff and wall pines, a crown band 22 m
under every peak's measured top, packed pine crowns on the islands): the ledge tiers stop LEDGE_TOP_CLEAR m under
each peak's measured top (the same measure as pass 1's crown band), and every new tree keeps TRUNK_CLEAR m from
the trees already in the scene, so run this after pass 1.

The tiers: world.py shapes every peak wall with _strata(h, 11.0), flat ledges at z = 11 k. The 5 m terrain grid
cannot show a ledge that narrow, so the tiers come from the peaks' analytic shape (world.Range.peaks): for every
ledge level k, the ring where the peak's wall crosses z = 11 k, broken into clumps by a smooth noise (LEDGE_COVER of
its length), a tree every LEDGE_STEP m (jittered) and a big shrub between some of them. Each site is snapped onto
the real mesh by a horizontal ray, kept only if no path point is nearer than CARD_CLEAR m + its height (so the web
draws it as a cheap card) and if some chase-camera frame within VIEW_MAX m sees it (facing + ray test against the
range), and kept clear of the area terraces, the links, the crown bands and the bridge.

Rules (as patch_nature_look.py / scenery.build_density): build() only adds objects, all in collection COLL (a child
of 'scenery', so the web export treats them as scenery), each with custom property TAG = its part; every random
draw comes from its own generator (U.rng(KEY, part, peak or rock)), so nothing placed before moves. Vegetation uses
only prototypes already in the scene (Huangshan '.far' and cliff '.hero' pines, peach '.far', green '.low' and
azalea shrubs; a missing one is skipped with a warning, never built) through the usual collection-instance Empties
(nature.pine / nature.blossom_tree / util.collection_instance), so bake_web / bake_trees take them as vegetation
records and no new tree family (card sprite) appears. Shrines are plain low-poly meshes (about 1-2.5k triangles)
for the atlas bake; lanterns are sect.lib.props.lantern_hanging instances (their silk glows in the web build);
the bridge is world._chain_bridge (planks, posts, chain rails).

clear() removes everything a previous run made (idempotent re-runs). sect/patch_life.py is the entry point.
The pure parts (tier_candidates, crown_mask, the shrine geometry builders) take plain numbers, so they can be
checked without Blender.
"""
import math
import time

import bmesh
import bpy
import numpy as np
from mathutils import Vector, kdtree
from mathutils.bvhtree import BVHTree

from sect import world as W
from sect.lib import nature as N
from sect.lib import util as U

KEY = "life"
COLL = "scenery.life"          # child of PARENT_COLL; the export's top collection stays 'scenery'
PARENT_COLL = "scenery"
TAG = "sect_life"              # custom property on every object this module makes: 'ledge', 'island', 'shrine', ...
CHASE_CAM = "chase.cam"        # export_web.CAMERA: the camera the web build follows
HOLD_FRAMES = dict(gate=93, mirror=217, forge=352, arena=516, mission=619, library=772, steles=974, scroll=1103,
                   formation=1208, abode=1380, summit=1647)
PARTS = ("shrines", "ledges", "islands")
PART_TAGS = dict(shrines=("shrine", "bridge"), ledges=("ledge",), islands=("island",))

# ---- ledge tiers ---------------------------------------------------------------------------------------------
LAYER = 11.0                   # world.py: _strata(h, 11.0) on every peak wall, flat ledges at z = 11 k
LEDGE_TOP_CLEAR = 25.0         # no tier this near a peak's measured top (pass 1's crown band is 22 m)
LEDGE_MIN_Z = W.CLOUD_SEA_Z + 14.0
LEDGE_STEP = 5.5               # mean trunk spacing along a tier (m), drawn x0.6-1.4 per gap
LEDGE_COVER = 0.55             # share of each tier's ring that carries trees (clumps and gaps, not a necklace)
RING_DS = 1.0                  # ring sample spacing (m)
RING_TOL = 2.5                 # the ring point must be on the exposed surface (|T - z| below this)
LEDGE_SNAP = 7.0               # the mesh wall may sit this far (XY) from the analytic ring point
CROWN_R = (1.6, 10.0)          # crown band reach: rad x 1.6 + 10 m (scenery._crown_band: rad * 1.6 + 2 * GRID)
PINE_H = (6.5, 13.0)           # ledge pine heights (m)
CLIFF_SHARE = dict(col=0.12, cone=0.06)   # share of ledge pines in the 'cliff' style (out of the wall, then up)
SHRUB_P = 0.5                  # chance of a big shrub halfway between two tier trees
SHRUB_SIZE = (2.0, 4.0)        # m wide: survives as a card (>= 3 px) out to ~1 km
SHRUB_PROTO_W = 1.7            # width (m) of a green '.low' shrub prototype at scale 1
BLOSSOM_SHARE = 0.12           # of the tier trees, as peach clusters
BLOSSOM_CLUSTER = (4, 9)       # trees per cluster
BLOSSOM_RADIUS = 18.0          # m: cluster members within this of its centre (3D)
BLOSSOM_H = (4.5, 7.5)
AZALEA_P = 0.5                 # shrubs inside a blossom cluster that are pink azaleas
CARD_CLEAR = 70.0              # bake_trees --tree-near: nearer trees become 3D meshes (+ the tree height)
SHRUB_CLEAR = 40.0             # bake_trees --shrub-near is 25 m
AREA_CLEAR = 14.0              # scenery.AREA_CLEAR: metres beyond an area's footprint kept free
LINK_CLEAR = 8.0               # world.LINK_TREE_CLEAR
TRUNK_CLEAR = 1.6              # from any tree already in the scene (m, 3D)
VIEW_MAX = 900.0               # export_web.MID_MAX
VIEW_EVERY = 6                 # chase.cam frames sampled for the visibility test
FACING = 0.15                  # wall normal . direction to the camera above this
VIS_RAYS = (3, 3)              # nearest facing frames, then random facing frames, tried per site
BRIDGE_KEEP = (8.0, 16.0)      # no ledge tree within 8 m (XY) of a bridge deck and less than 16 m under it

# ---- islands -------------------------------------------------------------------------------------------------
ISLAND_PREFIXES = ("scenery.island", "world.islet")
ISLAND_MIN = 12.0              # measured top width (m)
ISLAND_P = 0.55                # chance an island gets a blossom cluster
ISLAND_PEACH = (2, 5)
ISLAND_AZALEA = (0, 3)
ISLAND_PEACH_H = (0.2, 0.3)    # x island size, clamped to ISLAND_PEACH_HMAX
ISLAND_PEACH_HMAX = (4.0, 9.0)
ISLAND_SPOT = 0.3              # cluster spread (x top radius)

# ---- shrines -------------------------------------------------------------------------------------------------
# One per distant peak top a hold camera (or the fly-through) sees 150-600 m off, on the peak's measured cap.
# xy = world.Range.peaks centre (the nearest peak within PEAK_MATCH m is used; else skipped with a warning).
# The front (stair, landing) turns to the bridge partner's peak (partner=id) or to the camera of hold=area.
SHRINES = (
    dict(id="gate_e", xy=(-232.62, 399.36), kind="pavilion", n=6, partner="gate_w", roof="roof_tile_teal"),
    dict(id="gate_w", xy=(-358.93, 438.88), kind="pavilion", n=6, partner="gate_e", double=True, roof="roof_tile_teal"),
    dict(id="forge", xy=(234.54, 681.65), kind="pagoda", n=8, tiers=3, hold="forge", roof="roof_tile_black"),
    dict(id="arena", xy=(-218.98, 917.16), kind="pagoda", n=8, tiers=5, hold="arena", roof="roof_tile_teal"),
    dict(id="mission", xy=(-264.24, 773.67), kind="pavilion", n=8, hold="mission", double=True,
         roof="roof_tile_black"),
    dict(id="library", xy=(297.0, 958.92), kind="pagoda", n=6, tiers=3, hold="library", roof="roof_tile_teal"),
    dict(id="library_far", xy=(520.0, 1050.0), kind="pavilion", n=8, hold="library", double=True,
         roof="roof_tile_teal"),
    dict(id="formation", xy=(371.88, 1533.64), kind="pavilion", n=6, hold="formation", roof="roof_tile_black"),
    dict(id="summit", xy=(200.53, 1651.59), kind="pagoda", n=8, tiers=5, hold="summit", roof="roof_tile_teal"),
    dict(id="abode", xy=(330.0, 1760.0), kind="pavilion", n=8, hold="abode", double=True, roof="roof_tile_teal"),
)
BRIDGES = (("gate_e", "gate_w"),)     # chain bridge between the two terraces' front edges
PEAK_MATCH = 3.0
SHRINE_PATH_MIN = 150.0        # warn when a shrine stands nearer the camera path
SHRINE_SCALE = 1.0
TERRACE = dict(hx=5.5, front=7.0, back=4.8, rail_h=0.9, rail_t=0.25, body_max=12.0)
TERRACE_SMALL = dict(hx=4.4, front=5.8, back=4.4)   # on caps narrower than SMALL_CAP m (radius)
SMALL_CAP = 11.0
LANTERN_SIZE = 2.0             # props.lantern_hanging 'round' (body about 1.0 m tall, 1.2 m wide): ~3.5 px at 400 m
LANTERN_CORD = 0.35
BRIDGE_SAG = 4.5
BRIDGE_W = 2.4
BRIDGE_PLANK = 0.7             # plank spacing (m); world.CHAIN_PLANK is 0.35 for the walkable arena bridge
BRIDGE_LEVEL = 2.5
BRIDGEHEAD_RELIEF = 4.0        # m of ground relief a bridgehead terrace may span (its front edge stays at the rim)
SHRINE_MATS = ("marble_white", "stone_grey", "lacquer_red", "ROOF", "gold", "wood_dark")
MI_MARBLE, MI_STONE, MI_RED, MI_ROOF, MI_GOLD, MI_WOOD = range(6)


def _log(*a):
    print("LIFE", *a, flush=True)


# =============================================================================================================
# pure geometry: low-poly shrines (lists of verts / faces / material indices, local frame: front = -Y, z up)
# =============================================================================================================

_BOX_FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


class Geo:
    """Vertex / face / material-index lists (outward winding; recalc_face_normals fixes any slip)."""

    def __init__(self):
        self.v, self.f, self.m = [], [], []

    def vert(self, p):
        self.v.append((float(p[0]), float(p[1]), float(p[2])))
        return len(self.v) - 1

    def face(self, idx, mat):
        self.f.append(tuple(idx))
        self.m.append(int(mat))

    def tris(self):
        return sum(len(f) - 2 for f in self.f)

    def box(self, x0, x1, y0, y1, z0, z1, mat, top_mat=None):
        """Axis-aligned box; top_mat (if given) for the top face."""
        b = len(self.v)
        for z in (z0, z1):
            for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
                self.vert((x, y, z))
        for k, fc in enumerate(_BOX_FACES):
            self.face([b + i for i in fc], top_mat if (k == 1 and top_mat is not None) else mat)

    def obox(self, p0, p1, width, z0, z1, mat):
        """Box from p0 to p1 (XY), ``width`` across, z0..z1."""
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy)
        if L < 1e-6:
            return
        ux, uy = dx / L, dy / L
        nx, ny = -uy * width * 0.5, ux * width * 0.5
        b = len(self.v)
        for z in (z0, z1):
            for x, y in ((p0[0] - nx, p0[1] - ny), (p1[0] - nx, p1[1] - ny), (p1[0] + nx, p1[1] + ny),
                         (p0[0] + nx, p0[1] + ny)):
                self.vert((x, y, z))
        for fc in _BOX_FACES:
            self.face([b + i for i in fc], mat)

    def prism(self, n, r, z0, z1, phase, mat, r_top=None, cx=0.0, cy=0.0):
        """Closed n-gon prism (circumradius r, optional top radius)."""
        rt = r if r_top is None else r_top
        bot, top = [], []
        for i in range(n):
            a = phase + 2 * math.pi * i / n
            bot.append(self.vert((cx + r * math.cos(a), cy + r * math.sin(a), z0)))
            top.append(self.vert((cx + rt * math.cos(a), cy + rt * math.sin(a), z1)))
        for i in range(n):
            j = (i + 1) % n
            self.face((bot[i], bot[j], top[j], top[i]), mat)
        self.face(top, mat)
        self.face(list(reversed(bot)), mat)

    def lathe(self, prof, segs, mat, phase=0.0):
        """Closed surface of revolution from [(r, z), ...] bottom to top; r = 0 ends are single vertices."""
        rings = []
        for r, z in prof:
            if r <= 1e-6:
                rings.append([self.vert((0.0, 0.0, z))])
            else:
                rings.append([self.vert((r * math.cos(phase + 2 * math.pi * i / segs),
                                         r * math.sin(phase + 2 * math.pi * i / segs), z)) for i in range(segs)])
        for a, b in zip(rings[:-1], rings[1:]):
            for i in range(segs):
                j = (i + 1) % segs
                if len(a) == 1 and len(b) == 1:
                    continue
                if len(a) == 1:
                    self.face((a[0], b[j], b[i]), mat)
                elif len(b) == 1:
                    self.face((a[i], a[j], b[0]), mat)
                else:
                    self.face((a[i], a[j], b[j], b[i]), mat)
        if len(rings[0]) > 1:
            self.face(list(reversed(rings[0])), mat)
        if len(rings[-1]) > 1:
            self.face(rings[-1], mat)

    def roof(self, n, phase, r_eave, z_eave, rise, r_wall, mat, under_mat, lift=0.5, flare=0.08, thick=0.25,
             r_top=0.0, sub=4, rings=None):
        """Closed Chinese roof slab over an n-gon: concave slopes (flat at the eave, steep at the top), corners
        swept up by ``lift`` and pushed out by ``flare``, a fascia ``thick`` deep and a flat soffit back to the
        wall (r_wall). r_top = 0: pyramid to an apex (returns its z); r_top > 0: a skirt (lower eave of a
        pagoda tier or a double roof) ending in a level ring at r_top, closed down to the wall by an inner band.
        Returns the z of the apex / top ring."""
        outline = []
        for s in range(n):
            a0 = phase + 2 * math.pi * s / n
            a1 = a0 + 2 * math.pi / n
            c0, c1 = (math.cos(a0), math.sin(a0)), (math.cos(a1), math.sin(a1))
            for i in range(sub):
                t = i / sub
                outline.append((c0[0] * (1 - t) + c1[0] * t, c0[1] * (1 - t) + c1[1] * t, abs(2 * t - 1) ** 4))
        m = len(outline)
        apex = r_top <= 1e-6
        nr = rings or (4 if apex else 3)
        k_top = 1.0 if apex else (1.0 - r_top / r_eave)

        def ring(s, z_off=0.0, scale=None, warp=True):
            out = []
            for ux, uy, w in outline:
                e = (1.0 - s) ** 2 if warp else 0.0
                rho = (1.0 - s * k_top) if scale is None else scale
                k = r_eave * rho * (1.0 + flare * w * e)
                out.append(self.vert((ux * k, uy * k, z_eave + rise * (s ** 1.6) + lift * w * e + z_off)))
            return out
        if apex:
            levels = [k / nr for k in range(nr)]
        else:
            levels = [k / (nr - 1) for k in range(nr)]
        top = [ring(s) for s in levels]
        for a, b in zip(top[:-1], top[1:]):
            for i in range(m):
                j = (i + 1) % m
                self.face((a[i], a[j], b[j], b[i]), mat)
        if apex:
            z_ap = z_eave + rise
            ap = self.vert((0.0, 0.0, z_ap))
            last = top[-1]
            for i in range(m):
                self.face((last[i], last[(i + 1) % m], ap), mat)
        else:
            z_ap = z_eave + rise
        eave_bot = ring(0.0, z_off=-thick)
        e0 = top[0]
        for i in range(m):
            j = (i + 1) % m
            self.face((eave_bot[i], eave_bot[j], e0[j], e0[i]), under_mat)
        soff = ring(0.0, z_off=-thick * 0.5, scale=r_wall / r_eave, warp=False)
        for i in range(m):
            j = (i + 1) % m
            self.face((soff[i], soff[j], eave_bot[j], eave_bot[i]), under_mat)
        if apex:
            c = self.vert((0.0, 0.0, z_eave - thick * 0.5))
            for i in range(m):
                self.face((soff[(i + 1) % m], soff[i], c), under_mat)
        else:
            last = top[-1]
            for i in range(m):
                j = (i + 1) % m
                self.face((last[i], last[j], soff[j], soff[i]), under_mat)
        return z_ap

    def finial(self, z0, h, mat, segs=6):
        k = h / 2.3
        self.lathe([(0.0, z0), (0.28 * k, z0), (0.3 * k, z0 + 0.25 * k), (0.17 * k, z0 + 0.5 * k),
                    (0.3 * k, z0 + 0.8 * k), (0.12 * k, z0 + 1.2 * k), (0.06 * k, z0 + 2.0 * k), (0.0, z0 + h)],
                   segs, mat)


def _front_phase(n):
    """n-gon phase with a flat side facing -Y."""
    return -math.pi / 2 + math.pi / n


def _stair(g, apothem, z_top, width, rise=0.18, tread=0.34, r12=True):
    """Front stair (toward -Y) from a platform edge at y = -apothem, top z_top, down to z = 0. Each step is a block
    under its own tread (the top one reaching 5 cm into the platform); round 12: they ran from their nosing all the
    way back into the platform, one inside the other, and the sides of every pair lay in one plane (z-fighting on
    both sides of each shrine stair). ``r12`` False: the old blocks (patch_r12_world's guard)."""
    steps = max(1, int(math.ceil(z_top / rise - 1e-6)) - 1)
    rz = z_top / (steps + 1)
    for i in range(steps):
        zt = z_top - rz * (i + 1)
        back = -apothem + 0.05 if (i == 0 or not r12) else -apothem - tread * i
        g.box(-width / 2, width / 2, -apothem - tread * (i + 1), back, 0.0, zt, MI_MARBLE)


def _hooks(n, phase, r, z):
    """The two eave corners beside the front side (lantern hooks), local coordinates."""
    a = [phase + 2 * math.pi * i / n for i in range(n)]
    pts = sorted(((r * math.cos(t), r * math.sin(t)) for t in a), key=lambda p: p[1])[:2]
    return [(x, y, z) for x, y in pts]


def pavilion_geo(n=6, s=1.0, double=False, r12=True):
    """Open pavilion (ting) on a marble platform with a front stair: n red columns, a beam ring, one or two
    swept roofs and a gold finial. Returns (Geo, dict(hooks=[...], height, apothem))."""
    g = Geo()
    ph = _front_phase(n)
    rcol, col_h, plat_h, band_h = 3.0 * s, 3.3 * s, 0.7, 0.45 * s
    r_plat = rcol + 0.8 * s
    g.prism(n, r_plat, 0.0, plat_h, ph, MI_MARBLE)
    ap = r_plat * math.cos(math.pi / n)
    _stair(g, ap, plat_h, 2.2 * s, r12=r12)
    z_b = plat_h + col_h
    for i in range(n):
        a = ph + 2 * math.pi * i / n
        g.prism(8, 0.2 * s, plat_h, z_b, 0.0, MI_RED, cx=rcol * math.cos(a), cy=rcol * math.sin(a))
    corners = [(rcol * math.cos(ph + 2 * math.pi * i / n), rcol * math.sin(ph + 2 * math.pi * i / n)) for i in range(n)]
    for i in range(n):
        g.obox(corners[i], corners[(i + 1) % n], 0.32 * s, z_b, z_b + band_h, MI_RED)
    z_e = z_b + band_h
    r_e = rcol * 1.55
    lift = 0.6 * s
    if not double:
        z_top = g.roof(n, ph, r_e, z_e, r_e * 0.55, rcol, MI_ROOF, MI_RED, lift=lift, thick=0.28 * s)
    else:
        r_in = rcol * 0.7
        rise_s = (r_e - r_in) * 0.42
        z_sk = g.roof(n, ph, r_e, z_e, rise_s, rcol, MI_ROOF, MI_RED, lift=lift, thick=0.28 * s, r_top=r_in)
        z_d0, z_d1 = z_sk - 0.15, z_sk + 1.0 * s
        g.prism(n, r_in, z_d0, z_d1, ph, MI_RED)
        r_e2 = r_in * 1.6
        z_top = g.roof(n, ph, r_e2, z_d1, r_e2 * 0.6, r_in, MI_ROOF, MI_RED, lift=lift * 0.8, thick=0.24 * s)
    g.finial(z_top - 0.1, 2.0 * s, MI_GOLD)
    return g, dict(hooks=_hooks(n, ph, r_e * 0.9, z_e + lift * 0.45), height=z_top + 1.9 * s, apothem=ap)


def pagoda_geo(n=8, tiers=3, s=1.0, body_mat=MI_RED, r12=True):
    """Small pagoda (ta) on a marble platform with a front stair: ``tiers`` storeys tapering up, a swept eave
    over each, a pyramid roof and a tall gold spire; a dark door on the ground storey's front."""
    g = Geo()
    ph = _front_phase(n)
    r0, h0, h, taper = 2.7 * s, 3.0 * s, 2.4 * s, 0.1
    plat_r, plat_h = r0 + 1.4 * s, 0.9
    g.prism(n, plat_r, 0.0, plat_h, ph, MI_MARBLE)
    ap = plat_r * math.cos(math.pi / n)
    _stair(g, ap, plat_h, 2.0 * s, r12=r12)
    ap0 = r0 * math.cos(math.pi / n)
    g.box(-0.6 * s, 0.6 * s, -ap0 - 0.12, -ap0 + 0.05, plat_h, plat_h + 2.2 * s, MI_WOOD)
    z = plat_h
    hooks = None
    z_top = z
    for i in range(tiers):
        r_i = r0 * (1.0 - taper * i)
        h_i = h0 if i == 0 else h
        g.prism(n, r_i, z - 0.05, z + h_i, ph, body_mat)
        z_e = z + h_i
        r_e = r_i * 1.6
        lift = 0.45 * s
        if i == 0:
            hooks = _hooks(n, ph, r_e * 0.9, z_e + lift * 0.45)
        if i < tiers - 1:
            r_n = r0 * (1.0 - taper * (i + 1))
            rise = (r_e - r_n) * 0.45
            z = g.roof(n, ph, r_e, z_e, rise, r_i, MI_ROOF, MI_RED, lift=lift, thick=0.22 * s, r_top=r_n)
        else:
            z_top = g.roof(n, ph, r_e * 1.05, z_e, r_e * 0.8, r_i, MI_ROOF, MI_RED, lift=lift, thick=0.22 * s)
    g.finial(z_top - 0.1, 3.4 * s, MI_GOLD)
    return g, dict(hooks=hooks, height=z_top + 3.3 * s, apothem=ap)


def terrace_geo(g, depth, opening=0.0, hx=None, front=None, back=None, rail_h=None, rail_t=None, r12=True):
    """Stone terrace under a shrine (top at z = 0, marble top, grey body ``depth`` m deep) with a parapet on
    every edge; ``opening`` > 0 leaves a gap that wide in the middle of the front (-Y) edge for a bridge. The side
    parapets run the terrace's full depth and the front and back ones between them (round 12: all four ended on the
    corner points, so at each corner two overlapped in a square with their tops in one plane, and the outer corner
    square was missing; ``r12`` False: that old layout, patch_r12_world's guard)."""
    T = TERRACE
    hx = T["hx"] if hx is None else hx
    front = T["front"] if front is None else front
    back = T["back"] if back is None else back
    rh = T["rail_h"] if rail_h is None else rail_h
    rt = T["rail_t"] if rail_t is None else rail_t
    g.box(-hx, hx, -front, back, -depth, 0.0, MI_STONE, top_mat=MI_MARBLE)
    x0, x1, y0, y1 = -hx + rt / 2, hx - rt / 2, -front + rt / 2, back - rt / 2
    if r12:
        e = rt / 2
        segs = [((x0 + e, y1), (x1 - e, y1)), ((x0, y0 - e), (x0, y1 + e)), ((x1, y0 - e), (x1, y1 + e))]
        if opening > 0:
            segs += [((x0 + e, y0), (-opening / 2, y0)), ((opening / 2, y0), (x1 - e, y0))]
        else:
            segs.append(((x0 + e, y0), (x1 - e, y0)))
    else:
        segs = [((x0, y1), (x1, y1)), ((x0, y0), (x0, y1)), ((x1, y0), (x1, y1))]
        if opening > 0:
            segs += [((x0, y0), (-opening / 2, y0)), ((opening / 2, y0), (x1, y0))]
        else:
            segs.append(((x0, y0), (x1, y0)))
    for p0, p1 in segs:
        g.obox(p0, p1, rt, 0.0, rh, MI_MARBLE)
    return dict(front=front, back=back, hx=hx)


def terrace_dims(cap_r):
    """Terrace size for a peak cap of radius cap_r: TERRACE, or TERRACE_SMALL on a needle peak."""
    T = TERRACE_SMALL if cap_r < SMALL_CAP else TERRACE
    return dict(hx=T["hx"], front=T["front"], back=T["back"])


def shrine_geo(spec, depth, opening=0.0, dims=None, r12=True):
    """Terrace + pavilion / pagoda for a SHRINES entry. Returns (Geo, info). ``r12`` False: as built before round 12
    (patch_r12_world's guard)."""
    s = SHRINE_SCALE * spec.get("scale", 1.0)
    if spec["kind"] == "pagoda":
        g, info = pagoda_geo(spec.get("n", 8), spec.get("tiers", 3), s, r12=r12)
    else:
        g, info = pavilion_geo(spec.get("n", 6), s, spec.get("double", False), r12=r12)
    info.update(terrace_geo(g, depth, opening, r12=r12, **(dims or {})))
    return g, info


# =============================================================================================================
# pure placement math (numpy; rng_ is a world.Range)
# =============================================================================================================

def peak_kind(peak):
    return "col" if peak[4] > 5.0 else "cone"


def crown_mask(pts, peaks, tops, clear=None):
    """True where a point (n, 3) lies in some peak's crown band: within rad x CROWN_R[0] + CROWN_R[1] m (XY) of
    the peak and higher than its measured top - ``clear``."""
    clear = LEDGE_TOP_CLEAR if clear is None else clear
    pts = np.asarray(pts, float)
    out = np.zeros(len(pts), bool)
    for (px, py, _z, rad, _w, _c), zt in zip(peaks, tops):
        if zt is None:
            continue
        d = np.hypot(pts[:, 0] - px, pts[:, 1] - py)
        out |= (d < rad * CROWN_R[0] + CROWN_R[1]) & (pts[:, 2] >= zt - clear)
    return out


def area_mask(pts, anchors=None):
    """True where a point is outside every area's footprint + AREA_CLEAR (XY)."""
    pts = np.asarray(pts, float)
    ok = np.ones(len(pts), bool)
    for a in (anchors or W.ANCHORS).values():
        ok &= np.hypot(pts[:, 0] - a[0], pts[:, 1] - a[1]) > a[3] + AREA_CLEAR
    return ok


def tier_candidates(rng_, tops, rand=None):
    """Ledge-tier sites on every peak: [dict(x, y, z, th, pi, k, kind ('tree' | 'shrub'))]. For ledge level k
    (z = LAYER k, LEDGE_MIN_Z up to the peak's measured top - LEDGE_TOP_CLEAR), the ring where the peak's wall
    crosses z (world.Range.fields' peak formula solved for the distance, crag noise included), kept where that
    ring is the exposed surface, broken into clumps by a smooth noise (LEDGE_COVER of its length); a tree every
    LEDGE_STEP m (x0.6-1.4), and with SHRUB_P a shrub halfway to the next. ``rand(*salt)`` -> random.Random
    (default U.rng)."""
    rand = rand or (lambda *salt: U.rng(KEY, *salt))
    nz = rng_.noise
    out = []
    for pi, (cx, cy, top, rad, wall, cap) in enumerate(rng_.peaks):
        zt = tops[pi]
        if zt is None:
            continue
        rc, hc = cap * rad, (0.14 if wall < 5.0 else 0.09) * rad
        k0 = int(math.ceil(LEDGE_MIN_Z / LAYER))
        k1 = int(math.floor((zt - LEDGE_TOP_CLEAR) / LAYER))
        for k in range(k0, k1 + 1):
            z = LAYER * k
            d0 = rc + (top - hc - z) / wall
            if d0 <= 1.0:
                continue
            n = max(16, int(2 * math.pi * d0 / RING_DS))
            th = np.linspace(0.0, 2 * math.pi, n, endpoint=False)
            d = np.full(n, d0)
            for _ in range(3):
                xs, ys = cx + d * np.cos(th), cy + d * np.sin(th)
                crag = 1.0 + 0.22 * nz(xs, ys, 1 / 22.0, o=5) + 0.12 * nz(xs, ys, 1 / 7.0, o=11)
                d = d0 / crag
            xs, ys = cx + d * np.cos(th), cy + d * np.sin(th)
            f = rng_.fields(xs, ys)
            ok = (np.abs(f["T"] - z) < RING_TOL) & (f["F"] > 3.0)
            if not ok.any():
                continue
            r = rand("tier", pi, k)
            ph = [r.uniform(0.0, 2 * math.pi) for _ in range(3)]
            fq = [r.randint(2, 6) for _ in range(3)]
            nv = sum(np.sin(q * th + p) for q, p in zip(fq, ph)) / 3.0
            ok &= nv >= np.quantile(nv, 1.0 - LEDGE_COVER)
            arc = d0 * th
            nxt = r.uniform(0.0, LEDGE_STEP)
            shrub_at = None
            for j in np.nonzero(ok)[0]:
                a = arc[j]
                if shrub_at is not None and a >= shrub_at:
                    out.append(dict(x=float(xs[j]), y=float(ys[j]), z=z, th=float(th[j]), pi=pi, k=k, kind="shrub"))
                    shrub_at = None
                if a >= nxt:
                    out.append(dict(x=float(xs[j]), y=float(ys[j]), z=z, th=float(th[j]), pi=pi, k=k, kind="tree"))
                    gap = LEDGE_STEP * r.uniform(0.6, 1.4)
                    nxt = a + gap
                    shrub_at = a + 0.5 * gap if r.random() < SHRUB_P else None
    return out


def assign_species(sites, peaks, rand=None):
    """Per peak: peach clusters (BLOSSOM_SHARE of its tier trees, BLOSSOM_CLUSTER trees within BLOSSOM_RADIUS of
    a seeded centre), azaleas among the shrubs inside a cluster (AZALEA_P), cliff-style pines (CLIFF_SHARE),
    Huangshan pines for the rest. Sets s['species'] in place."""
    rand = rand or (lambda *salt: U.rng(KEY, *salt))
    by = {}
    for s in sites:
        by.setdefault(s["pi"], []).append(s)
    for pi, ss in sorted(by.items()):
        r = rand("species", pi)
        trees = [s for s in ss if s["kind"] == "tree"]
        P = np.array([[s["px"], s["py"], s["pz"]] for s in ss]) if ss else np.zeros((0, 3))
        centres = []
        mean = 0.85 * 0.5 * (BLOSSOM_CLUSTER[0] + BLOSSOM_CLUSTER[1]) * 0.8   # members a cluster really gets
        want = BLOSSOM_SHARE * len(trees) / mean
        ncl = int(want) + (1 if r.random() < want - int(want) else 0)
        for _ in range(ncl):
            if not trees:
                break
            c = r.choice(trees)
            cp = np.array([c["px"], c["py"], c["pz"]])
            centres.append(cp)
            cand = sorted(trees, key=lambda t: (t["px"] - cp[0]) ** 2 + (t["py"] - cp[1]) ** 2 + (t["pz"] - cp[2]) ** 2)
            for t in cand[:r.randint(*BLOSSOM_CLUSTER)]:
                if math.dist((t["px"], t["py"], t["pz"]), cp) < BLOSSOM_RADIUS and r.random() < 0.85:
                    t["species"] = "peach"
        cliff = CLIFF_SHARE[peak_kind(peaks[pi])]
        for i, s in enumerate(ss):
            if s.get("species"):
                continue
            if s["kind"] == "shrub":
                inside = any(math.dist(P[i], c) < BLOSSOM_RADIUS for c in centres)
                s["species"] = "azalea" if inside and r.random() < AZALEA_P else "shrub"
            else:
                s["species"] = "cliff" if r.random() < cliff else "pine"
    return sites


# =============================================================================================================
# Blender glue
# =============================================================================================================

def _proto_ok(key):
    col = bpy.data.collections.get("nature.proto." + key)
    return col is not None and col.get("nature_proto") == key and len(col.all_objects) > 0


def available_protos():
    """Variants of every prototype this module plants that already exist in the scene (never built here)."""
    av = dict(pine=[v for v in range(N.PINE_VARIANTS["huangshan"]) if _proto_ok("pine.huangshan.v%d.far" % v)],
              cliff=[v for v in range(N.PINE_VARIANTS["cliff"]) if _proto_ok("pine.cliff.v%d.hero" % v)],
              peach=[v for v in range(4) if _proto_ok("blossom.peach.v%d.far" % v)],
              shrub=[v for v in range(4) if _proto_ok("shrub.green.v%d.low" % v)],
              azalea=[v for v in range(2) if _proto_ok("shrub.azalea.v%d" % v)])
    for k, v in av.items():
        if not v:
            _log("WARN no prototype in the scene for", k, "- that species is skipped")
    return av


def clear(parts=None):
    """Remove what a previous run made for ``parts`` (default all: every object tagged TAG and anything else left
    in COLL), then the orphan meshes named 'life.*'."""
    parts = PARTS if parts is None else tuple(parts)
    tags = {t for p in parts for t in PART_TAGS[p]}
    obs = {o for o in bpy.data.objects if o.get(TAG) in tags}
    col = bpy.data.collections.get(COLL)
    if col is not None and set(parts) >= set(PARTS):
        obs |= set(col.all_objects)
    n = 0
    for ob in obs:
        bpy.data.objects.remove(ob, do_unlink=True)
        n += 1
    m = 0
    for me in [me for me in bpy.data.meshes if me.users == 0 and me.name.startswith("life.")]:
        bpy.data.meshes.remove(me)
        m += 1
    _log("cleared", n, "objects,", m, "meshes from a previous run")
    return n


class Surface:
    """Ray casts against one mesh object in world space (BVH of its evaluated mesh)."""

    def __init__(self, ob):
        dg = bpy.context.evaluated_depsgraph_get()
        self.bvh = BVHTree.FromObject(ob, dg)
        self.mw = ob.matrix_world.copy()
        self.mwi = self.mw.inverted()
        self.r3 = self.mw.to_3x3()
        self.r3i = self.mwi.to_3x3()

    def ray(self, o, d, dist):
        o = Vector(o)
        ld = self.r3i @ Vector(d)
        if ld.length < 1e-9:
            return None
        hit, nrm, _i, _d = self.bvh.ray_cast(self.mwi @ o, ld.normalized(), dist)
        if hit is None:
            return None
        hw = self.mw @ hit
        return hw, (self.r3 @ nrm).normalized(), (hw - o).length

    def down(self, x, y, z_from, dist=800.0):
        return self.ray((x, y, z_from), (0.0, 0.0, -1.0), dist)


def _kd(pts):
    pts = np.asarray(pts, float).reshape(-1, 3)
    kd = kdtree.KDTree(max(1, len(pts)))
    for i, p in enumerate(pts):
        kd.insert(Vector(p), i)
    kd.balance()
    return kd, len(pts)


def camera_paths(scene):
    """(path KD tree, chase.cam positions every VIEW_EVERY frames, hold camera positions {id: xyz}). The KD
    tree holds the flyer's route, the planned chase and chase.cam every 2 frames, as scenery.density_paths."""
    from sect import chase as CH
    frames, pos, look0, heroes, _ = CH.route(scene)
    plan = CH.plan_orbit(pos, look0, frames, heroes, scene.render.fps)
    pts = [np.asarray(pos)[::2], np.asarray(plan["cam"])[::2]]
    cams = None
    cam = bpy.data.objects.get(CHASE_CAM)
    if cam is not None and cam.animation_data is not None and cam.animation_data.action is not None:
        try:
            cams = np.asarray(CH.path_from_camera(cam, frames), float)
            pts.append(cams[::2])
        except Exception as exc:
            _log("WARN", CHASE_CAM, "not sampled:", exc)
    if cams is None:
        _log("WARN no keyed", CHASE_CAM, "- the planned chase stands in for the visibility test")
        cams = np.asarray(plan["cam"], float)
    kd, n = _kd(np.vstack(pts))
    f0 = int(frames[0])
    holds = {k: cams[int(np.clip(f - f0, 0, len(cams) - 1))] for k, f in HOLD_FRAMES.items()}
    _log("paths", n, "points; visibility frames", len(cams[::VIEW_EVERY]))
    return kd, cams[::VIEW_EVERY], holds


def veg_points():
    """Trunk bases of every tree already in the scene (depsgraph instances of nature.proto pines, blossoms,
    willows and bamboo), for TRUNK_CLEAR."""
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for inst in dg.object_instances:
        if not inst.is_instance:
            continue
        nm = inst.object.original.name
        if nm.startswith("nature.proto.") and any(w in nm for w in ("pine", "blossom", "willow", "bamboo")):
            pts.append(tuple(inst.matrix_world.translation))
    _log("trees already in the scene", len(pts))
    return pts


def link_kd():
    lp = W.link_points()
    return _kd(np.column_stack([lp, np.zeros(len(lp))]) if len(lp) else np.zeros((0, 3)))


def measured_tops(rng_obj, peaks):
    """Each peak's top measured on the mesh like scenery._crown_band: the highest top-face centre within
    max(cap x rad, 2.5 grid cells) of the peak, among faces within rad x 1.6 + 2 cells (None if none)."""
    me = rng_obj.data
    n = len(me.polygons)
    c = np.empty(n * 3)
    me.polygons.foreach_get("center", c)
    mats = np.empty(n, np.int32)
    me.polygons.foreach_get("material_index", mats)
    mw = np.array(rng_obj.matrix_world)
    cw = (c.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3])[mats != 2]
    out = []
    for (px, py, _z, rad, _w, cap) in peaks:
        d = np.hypot(cw[:, 0] - px, cw[:, 1] - py)
        core = (d < rad * 1.6 + 2.0 * W.GRID) & (d < max(cap * rad, 2.5 * W.GRID))
        out.append(float(cw[core, 2].max()) if core.any() else None)
    return out


def _seg_dist(p, a, b):
    a, b, p = np.asarray(a[:2], float), np.asarray(b[:2], float), np.asarray(p[:2], float)
    ab = b - a
    t = float(np.clip(np.dot(p - a, ab) / max(float(ab @ ab), 1e-9), 0.0, 1.0))
    return float(np.linalg.norm(p - (a + t * ab))), t


class Ctx:
    """Everything the parts share: the range, its mesh surface, tops, paths, existing trees, prototypes."""

    def __init__(self, scene):
        self.scene = scene
        self.rng_ = W.Range(W._norm_anchors(None), W._anchor_yaws(None))
        self.range_ob = bpy.data.objects["world.range"]
        self.surf = Surface(self.range_ob)
        self.tops = measured_tops(self.range_ob, self.rng_.peaks)
        self.path_kd, self.cams, self.holds = camera_paths(scene)
        vp = veg_points()
        self.veg_kd, _ = _kd(vp if vp else np.zeros((0, 3)))
        self.n_veg = len(vp)
        self.link_kd, self.n_links = link_kd()
        self.protos = available_protos()
        self.bridges = []           # [(p0, p1)] world deck ends, for BRIDGE_KEEP
        root = U.get_collection(PARENT_COLL, scene=scene)
        self.coll = U.get_collection(COLL, parent=root, scene=scene)
        self.counts = {}

    def path_dist(self, p):
        return self.path_kd.find(Vector(p))[2] if len(self.cams) else 1e9

    def tree_clear(self, p, r=None):
        r = TRUNK_CLEAR if r is None else r
        if self.n_veg and self.veg_kd.find(Vector(p))[2] < r:
            return False
        return True

    def visible(self, p, nrm, rand):
        """Some chase.cam frame within VIEW_MAX m in front of the wall (FACING) sees p past the range."""
        v = self.cams - np.asarray(p)
        dd = np.linalg.norm(v, axis=1)
        c = (v @ np.asarray(nrm)) / np.maximum(dd, 1e-6)
        cand = np.nonzero((c > FACING) & (dd < VIEW_MAX))[0]
        if not len(cand):
            return False
        pick = list(cand[np.argsort(dd[cand])[:VIS_RAYS[0]]])
        pick += [int(cand[rand.randrange(len(cand))]) for _ in range(VIS_RAYS[1])]
        src = Vector(p) + Vector(nrm) * 2.0 + Vector((0.0, 0.0, 3.0))
        for j in pick:
            d = Vector(self.cams[j]) - src
            L = d.length
            if L < 1.0:
                return True
            if self.surf.ray(src, d / L, L - 1.0) is None:
                return True
        return False

    def count(self, k, n=1):
        self.counts[k] = self.counts.get(k, 0) + n


def _tag(ob, part):
    ob[TAG] = part
    return ob


def _yaw_of(dx, dy):
    """Rotation z that turns local -Y (a builder's front) to the direction (dx, dy)."""
    return math.atan2(dx, -dy)


def _seed(variants, n_all, *salt):
    """A nature.pine / blossom_tree seed whose variant (seed % n_all) is one of ``variants``."""
    h = U.seed_from(KEY, *salt)
    return (h % 9973) * n_all + variants[h % len(variants)]


# ---- ledges -------------------------------------------------------------------------------------------------

def build_ledges(ctx):
    """Tier pines, peach clusters and big shrubs on every peak's ledge levels. Returns counts."""
    t0 = time.perf_counter()
    cands = tier_candidates(ctx.rng_, ctx.tops)
    pts = np.array([[c["x"], c["y"], c["z"]] for c in cands]) if cands else np.zeros((0, 3))
    keep = area_mask(pts) & ~crown_mask(pts, ctx.rng_.peaks, ctx.tops) if len(pts) else np.zeros(0, bool)
    rej = dict(candidates=len(cands), area_or_crown=int((~keep).sum()), link=0, bridge=0, path=0, snap=0,
               facing_or_hidden=0, near_tree=0, near_new=0)
    sites = []
    vis_r = {}
    taken = {}                  # 2 m cells -> new site positions (where two peaks' rings cross, both are exposed)

    def near_new(p, r):
        i, j, k = int(math.floor(p.x / 2.0)), int(math.floor(p.y / 2.0)), int(math.floor(p.z / 2.0))
        return any((q - p).length < r for di in (-1, 0, 1) for dj in (-1, 0, 1) for dk in (-1, 0, 1)
                   for q in taken.get((i + di, j + dj, k + dk), ()))
    for c, ok in zip(cands, keep):
        if not ok:
            continue
        x, y, z = c["x"], c["y"], c["z"]
        if ctx.n_links and ctx.link_kd.find(Vector((x, y, 0.0)))[2] < LINK_CLEAR:
            rej["link"] += 1
            continue
        if any(_seg_dist((x, y), a, b)[0] < BRIDGE_KEEP[0] and z > min(a[2], b[2]) - BRIDGE_SAG - BRIDGE_KEEP[1]
               for a, b in ctx.bridges):
            rej["bridge"] += 1
            continue
        tree = c["kind"] == "tree"
        need = (CARD_CLEAR + PINE_H[1]) if tree else SHRUB_CLEAR
        if ctx.path_dist((x, y, z)) < need:
            rej["path"] += 1
            continue
        ux, uy = math.cos(c["th"]), math.sin(c["th"])
        hit = ctx.surf.ray((x + ux * 12.0, y + uy * 12.0, z + 0.6), (-ux, -uy, 0.0), 30.0)
        if hit is None or math.hypot(hit[0].x - x, hit[0].y - y) > LEDGE_SNAP:
            rej["snap"] += 1
            continue
        hp, hn = hit[0], hit[1]
        if ctx.path_dist(hp) < need:         # the snap moves the site up to LEDGE_SNAP m: test where it stands
            rej["path"] += 1
            continue
        nh = Vector((hn.x, hn.y, 0.0))
        if nh.length < 0.2 or nh.x * ux + nh.y * uy < 0.0:
            nh = Vector((ux, uy, 0.0))
        nh.normalize()
        r = vis_r.setdefault(c["pi"], U.rng(KEY, "vis", c["pi"]))
        if not ctx.visible(hp, nh, r):
            rej["facing_or_hidden"] += 1
            continue
        if not ctx.tree_clear(hp, TRUNK_CLEAR if tree else 1.0):
            rej["near_tree"] += 1
            continue
        if near_new(hp, TRUNK_CLEAR if tree else 1.0):
            rej["near_new"] += 1
            continue
        taken.setdefault((int(math.floor(hp.x / 2.0)), int(math.floor(hp.y / 2.0)), int(math.floor(hp.z / 2.0))),
                         []).append(Vector(hp))
        c.update(px=hp.x, py=hp.y, pz=hp.z, nx=nh.x, ny=nh.y)
        sites.append(c)
    assign_species(sites, ctx.rng_.peaks)
    av = ctx.protos
    made = {}
    for i, s in enumerate(sites):
        sp = s["species"]
        out = Vector((s["nx"], s["ny"], 0.0))
        yaw_out = math.atan2(out.y, out.x)
        hp = Vector((s["px"], s["py"], s["pz"]))
        r = U.rng(KEY, "plant", s["pi"], s["k"], round(s["th"], 4), s["kind"])
        salt = (s["pi"], s["k"], round(s["th"], 4))
        if sp == "cliff" and not av["cliff"]:
            sp = "pine"
        if sp == "peach" and not av["peach"]:
            sp = "pine"
        if sp == "azalea" and not av["azalea"]:
            sp = "shrub"
        if sp == "pine" and av["pine"]:
            h = r.uniform(*PINE_H)
            loc = hp - out * 0.35 - Vector((0.0, 0.0, 0.3))
            ob = N.pine(ctx.coll, height=h, seed=_seed(av["pine"], N.PINE_VARIANTS["huangshan"], "pine", *salt),
                        style="huangshan", lod="far", name="life.ledge.pine", location=tuple(loc),
                        lean_toward=yaw_out + r.uniform(-0.5, 0.5))
        elif sp == "cliff":
            h = r.uniform(*PINE_H) * 0.85
            ob = N.pine(ctx.coll, height=h, seed=_seed(av["cliff"], N.PINE_VARIANTS["cliff"], "cliff", *salt),
                        style="cliff", lod="hero", name="life.ledge.cliffpine",
                        location=tuple(hp - Vector((0.0, 0.0, 0.2))),
                        lean_toward=yaw_out + r.uniform(-0.35, 0.35))
        elif sp == "peach":
            h = r.uniform(*BLOSSOM_H)
            loc = hp + out * 0.5 - Vector((0.0, 0.0, 0.4))
            ob = N.blossom_tree(ctx.coll, height=h, seed=_seed(av["peach"], 4, "peach", *salt), kind="peach",
                                lod="far", name="life.ledge.peach", location=tuple(loc))
        elif sp in ("shrub", "azalea") and av[sp]:
            size = r.uniform(*SHRUB_SIZE)
            v = av[sp][r.randrange(len(av[sp]))]
            key = ("shrub.green.v%d.low" % v) if sp == "shrub" else ("shrub.azalea.v%d" % v)
            sc = size / SHRUB_PROTO_W
            loc = hp + out * 0.3 - Vector((0.0, 0.0, 0.3))
            ob = U.collection_instance(bpy.data.collections["nature.proto." + key],
                                       U.unique_name("life.ledge." + sp), ctx.coll, location=tuple(loc),
                                       rotation=(0.0, 0.0, r.uniform(0, 2 * math.pi)),
                                       scale=(sc, sc, sc * r.uniform(0.85, 1.1)), display_size=size * 0.3)
        else:
            continue
        _tag(ob, "ledge")
        made[sp] = made.get(sp, 0) + 1
    for k, v in made.items():
        ctx.count("ledge." + k, v)
    peaks_used = len({s["pi"] for s in sites})
    _log("ledges", made, "on", peaks_used, "peaks; rejected", rej, "in", round(time.perf_counter() - t0, 1), "s")
    return made


# ---- islands ------------------------------------------------------------------------------------------------

def _rocks(prefix):
    import re
    pat = re.compile(r"^%s(\.\d{3})?$" % re.escape(prefix))
    return sorted((o for o in bpy.data.objects if o.type == 'MESH' and pat.match(o.name)), key=lambda o: o.name)


def build_islands(ctx):
    """A peach-blossom cluster (and a few azaleas) on ISLAND_P of the floating rocks whose top is at least
    ISLAND_MIN m wide, between the trees already there. Returns counts."""
    av = ctx.protos
    made = dict(peach=0, azalea=0, islands=0)
    if not av["peach"]:
        return made
    for prefix in ISLAND_PREFIXES:
        for rock in _rocks(prefix):
            me = rock.data
            n = len(me.polygons)
            if not n:
                continue
            mats = np.empty(n, np.int32)
            me.polygons.foreach_get("material_index", mats)
            cen = np.empty(n * 3)
            me.polygons.foreach_get("center", cen)
            cen = cen.reshape(-1, 3)
            ti = np.nonzero(mats == 1)[0]
            if not len(ti):
                continue
            rr = np.hypot(cen[ti, 0], cen[ti, 1])
            R = float(rr.max())
            if 2.0 * R < ISLAND_MIN:
                continue
            q = U.rng(KEY, "island", rock.name)
            if q.random() > ISLAND_P:
                continue
            inner = ti[rr < 0.55 * R]
            if not len(inner):
                continue
            c = cen[inner[q.randrange(len(inner))]]
            verts = [v.co.copy() for v in me.vertices]
            bvh = BVHTree.FromPolygons(verts, [tuple(p.vertices) for p in me.polygons])
            mw = rock.matrix_world
            size = 2.0 * R
            got = []

            def spot():
                for _ in range(14):
                    a = q.uniform(0, 2 * math.pi)
                    d = R * ISLAND_SPOT * math.sqrt(q.random())
                    x, y = c[0] + math.cos(a) * d, c[1] + math.sin(a) * d
                    if math.hypot(x, y) > 0.8 * R:
                        continue
                    hit = bvh.ray_cast(Vector((x, y, R + 5.0)), Vector((0.0, 0.0, -1.0)), 3.0 * R + 10.0)
                    if hit[0] is None or hit[2] is None or mats[hit[2]] != 1:
                        continue
                    w = mw @ hit[0]
                    if not ctx.tree_clear(w, 2.2) or any((w - g).length < 2.0 for g in got):
                        continue
                    return w
                return None
            n_p, n_a = q.randint(*ISLAND_PEACH), q.randint(*ISLAND_AZALEA)
            placed = 0
            for j in range(n_p):
                h = max(ISLAND_PEACH_HMAX[0], min(ISLAND_PEACH_HMAX[1], size * q.uniform(*ISLAND_PEACH_H)))
                w = spot()
                if w is None or ctx.path_dist(w) < CARD_CLEAR + h:
                    continue
                ob = N.blossom_tree(ctx.coll, height=h, seed=_seed(av["peach"], 4, "isl", rock.name, j), kind="peach",
                                    lod="far", name="life.island.peach", location=tuple(w - Vector((0, 0, 0.1))))
                _tag(ob, "island")
                got.append(w)
                made["peach"] += 1
                placed += 1
            for j in range(n_a if av["azalea"] else 0):
                w = spot()
                if w is None or ctx.path_dist(w) < SHRUB_CLEAR:
                    continue
                size_s = q.uniform(*SHRUB_SIZE)
                v = av["azalea"][q.randrange(len(av["azalea"]))]
                sc = size_s / SHRUB_PROTO_W
                ob = U.collection_instance(bpy.data.collections["nature.proto.shrub.azalea.v%d" % v],
                                           U.unique_name("life.island.azalea"), ctx.coll,
                                           location=tuple(w - Vector((0, 0, 0.05))),
                                           rotation=(0.0, 0.0, q.uniform(0, 2 * math.pi)), scale=(sc, sc, sc),
                                           display_size=size_s * 0.3)
                _tag(ob, "island")
                got.append(w)
                made["azalea"] += 1
            made["islands"] += 1 if placed else 0
    ctx.count("island.peach", made["peach"])
    ctx.count("island.azalea", made["azalea"])
    _log("islands", made)
    return made


# ---- shrines and the bridge ----------------------------------------------------------------------------------

def _nearest_peak(peaks, xy):
    d = [math.hypot(p[0] - xy[0], p[1] - xy[1]) for p in peaks]
    i = int(np.argmin(d))
    return i, d[i]


def _footprint(origin, yaw, info, step=1.5):
    """World XY sample points over a terrace (local rectangle hx x (front + back)) at origin, turned by yaw."""
    cy, sy = math.cos(yaw), math.sin(yaw)
    pts = []
    for lx in np.arange(-info["hx"], info["hx"] + 1e-6, step):
        for ly in np.arange(-info["front"], info["back"] + 1e-6, step):
            pts.append((origin[0] + lx * cy - ly * sy, origin[1] + lx * sy + ly * cy))
    return pts


def _site_score(ctx, origin, yaw, info, face, peak_c):
    """(score, ground zs, trunks inside) of a terrace at origin."""
    zs = []
    for x, y in _footprint(origin, yaw, info):
        hit = ctx.surf.down(x, y, origin[2] + 60.0, 200.0)
        zs.append(hit[0].z if hit is not None else -1e4)
    zs = np.array(zs)
    on = zs > -1e3
    if on.mean() < 0.6:
        return -1e9, zs, 99
    trunks = 0
    reach = math.hypot(info["hx"], max(info["front"], info["back"])) + 1.0   # the whole rectangle, corners too
    hits = ctx.veg_kd.find_range(Vector((origin[0], origin[1], float(zs[on].max()))), reach) if ctx.n_veg else []
    for co, _i, _d in hits:
        lx = (co.x - origin[0]) * math.cos(yaw) + (co.y - origin[1]) * math.sin(yaw)
        ly = -(co.x - origin[0]) * math.sin(yaw) + (co.y - origin[1]) * math.cos(yaw)
        if abs(lx) < info["hx"] and -info["front"] < ly < info["back"]:
            trunks += 3 if math.hypot(lx, ly) < 4.0 else 1
    relief = float(zs[on].max() - zs[on].min())
    rim = math.hypot(origin[0] - peak_c[0], origin[1] - peak_c[1])
    score = -4.0 * trunks - 1.5 * relief - 8.0 * (1.0 - on.mean()) + 0.15 * rim
    return score, zs, trunks


def build_shrines(ctx):
    """SHRINES on their peaks' caps (with lanterns), then BRIDGES between terrace fronts. Returns counts."""
    from sect.lib import props as P
    peaks = ctx.rng_.peaks
    specs = {s["id"]: s for s in SHRINES}
    bridged = {a for ab in BRIDGES for a in ab}
    made = {}
    tris = 0
    for spec in SHRINES:
        pi, dmatch = _nearest_peak(peaks, spec["xy"])
        if dmatch > PEAK_MATCH:
            _log("WARN shrine", spec["id"], "no peak within", PEAK_MATCH, "m of", spec["xy"],
                 "(nearest", round(dmatch, 1), ") - skipped")
            continue
        cx, cy, _top, rad, _wall, cap = peaks[pi]
        rc = cap * rad
        zt = ctx.tops[pi] if ctx.tops[pi] is not None else _top
        if spec.get("partner") in specs:
            tgt = specs[spec["partner"]]["xy"]
        else:
            tgt = tuple(ctx.holds[spec.get("hold", "summit")][:2])
        fx, fy = tgt[0] - cx, tgt[1] - cy
        L = math.hypot(fx, fy)
        if L < 1.0:
            _log("WARN shrine", spec["id"], "faces its own peak; turned to -Y")
            fx, fy, L = 0.0, -1.0, 1.0
        fx, fy = fx / L, fy / L
        dims = terrace_dims(rc)
        _g, info = shrine_geo(spec, 1.0, dims=dims)
        if spec["id"] in bridged:          # slide along the bridge line: front edge as near the rim as the cap allows
            offs = np.arange(-4.0, rc - 0.5 - info["front"] + 1e-6, 0.75)
            cands = [(cx + fx * off, cy + fy * off, _yaw_of(fx, fy)) for off in (offs if len(offs) else [0.0])]
        else:
            cands = []
            for r_ in np.arange(-3.0, max(rc - info["front"] + 2.5, -2.0) + 1e-6, 1.5):
                for da in np.radians(np.arange(-60.0, 60.1, 15.0)):
                    ca, sa = math.cos(da), math.sin(da)
                    dx, dy = fx * ca - fy * sa, fx * sa + fy * ca
                    cands.append((cx + dx * r_, cy + dy * r_, _yaw_of(dx, dy)))
        scored = []
        for x, y, yaw in cands:
            sc, zs, trunks = _site_score(ctx, (x, y, zt), yaw, info, (fx, fy), (cx, cy))
            on_ = zs > -1e3
            relief = float(zs[on_].max() - zs[on_].min()) if on_.any() else 1e9
            scored.append((sc, x, y, yaw, zs, trunks, relief))
        if spec["id"] in bridged:          # the outermost spot whose ground is flat enough, else the best score
            flat = [c for c in scored if c[0] > -1e8 and c[6] <= BRIDGEHEAD_RELIEF]
            best = flat[-1] if flat else max(scored, key=lambda c: c[0])
        else:
            best = max(scored, key=lambda c: c[0])
        sc, x, y, yaw, zs, trunks, _relief = best
        on = zs > -1e3
        if not on.any():
            _log("WARN shrine", spec["id"], "found no cap under its terrace - skipped")
            continue
        ztop = float(zs[on].max()) + 0.35
        depth = float(min(TERRACE["body_max"], max(1.5, ztop - float(zs[on].min()) + 1.2)))
        gap = ztop - float(zs[on].min()) - depth
        if gap > 0.0:
            _log("WARN shrine", spec["id"], "terrace body (%.1f m) ends %.1f m over the ground on its low side"
                 % (depth, gap))
        if on.mean() < 1.0:
            _log("WARN shrine", spec["id"], "%d%% of the terrace has no ground within 140 m under it"
                 % round(100 * (1.0 - on.mean())))
        g, info = shrine_geo(spec, depth, opening=(BRIDGE_W + 0.8) if spec["id"] in bridged else 0.0, dims=dims)
        mats = [spec.get("roof", "roof_tile_teal") if m == "ROOF" else m for m in SHRINE_MATS]
        nm = U.unique_name("life.shrine." + spec["id"])
        ob = U.mesh_from_pydata(nm, g.v, g.f, ctx.coll, materials=mats, smooth=False, material_indices=g.m,
                                location=(x, y, ztop), rotation=(0.0, 0.0, yaw))
        if len(ob.data.polygons) != len(g.f):
            # mesh.validate() dropped faces, so util.mesh_from_pydata skipped the material indices (all marble)
            raise RuntimeError("shrine %s: %d faces built, %d after validate; material indices lost"
                               % (spec["id"], len(g.f), len(ob.data.polygons)))
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(ob.data)
        bm.free()
        ob.data.update()
        _tag(ob, "shrine")
        ob["life_peak"] = pi
        for k, hk in enumerate(info["hooks"]):
            lt = P.lantern_hanging(ctx.coll, style="round", size=LANTERN_SIZE, cord=LANTERN_CORD,
                                   name="life.shrine.%s.lantern" % spec["id"], parent=ob, location=hk)
            _tag(lt, "shrine")
        front = (x + math.sin(yaw) * info["front"], y - math.cos(yaw) * info["front"], ztop)
        # the terrace is a sword-flight landing (sect-architecture rule 12): mark it as an intended end of the
        # walk graph for walk_sect (Empties are not exported)
        _tag(U.empty(U.unique_name("landmark.life." + spec["id"]), ctx.coll, location=(0.0, -info["front"] * 0.6, 0.0),
                     parent=ob, display_size=2.0), "shrine")
        dpath = ctx.path_dist((x, y, ztop + 4.0))
        made[spec["id"]] = dict(ob=ob, front=front, dir=(fx, fy), ztop=ztop, peak=pi)
        tris += g.tris()
        _log("shrine", spec["id"], spec["kind"], "peak", pi, "at", [round(float(v), 1) for v in (x, y, ztop)],
             "terrace depth", round(depth, 1), "trunks on terrace", trunks, "path m", int(dpath),
             "tris", g.tris(), "lanterns", len(info["hooks"]))
        if dpath < SHRINE_PATH_MIN:
            _log("WARN shrine", spec["id"], "is", int(dpath), "m from the camera path (<", SHRINE_PATH_MIN, ")")
    nb = 0
    for i, (a, b) in enumerate(BRIDGES):
        if a not in made or b not in made:
            _log("WARN bridge", a, b, "skipped: a shrine is missing")
            continue
        A, B = made[a], made[b]
        u = np.array(B["front"][:2]) - np.array(A["front"][:2])
        u /= np.linalg.norm(u)
        p0 = (A["front"][0] - u[0] * 1.2, A["front"][1] - u[1] * 1.2, A["ztop"])
        p1 = B["front"]
        objs, rep, geo = W._chain_bridge(ctx.rng_, ctx.coll, p0, p1, "life.span%d.bridge" % (i + 1), sag=BRIDGE_SAG,
                                         width=BRIDGE_W, steps=True, level=BRIDGE_LEVEL, spacing=BRIDGE_PLANK)
        for o in objs:
            _tag(o, "bridge")
            o["life_p0"] = [float(v) for v in p0]
            o["life_p1"] = [float(v) for v in p1]
        ctx.bridges.append((p0, p1))
        # clearance over the real mesh along the free span (world._chain_bridge reports the analytic one); the
        # level ends lie on the bridgehead terraces
        clr = []
        span = float(np.hypot(p1[0] - p0[0], p1[1] - p0[1]))
        for (xx, yy), zz in zip(geo["xy"][::3], geo["z"][::3]):
            q = float(np.hypot(xx - p0[0], yy - p0[1]))
            if q < BRIDGE_LEVEL + 1.2 or q > span - BRIDGE_LEVEL:
                continue
            hit = ctx.surf.down(float(xx), float(yy), float(zz) + 50.0, 450.0)   # from above: a deck in rock < 0
            clr.append(float(zz) - hit[0].z if hit is not None else 400.0)
        lo = min(clr) if clr else None
        nb += 1
        _log("bridge", a, "-", b, json_safe(rep), "mesh clearance min", None if lo is None else round(lo, 1))
        if lo is not None and lo < 2.0:
            _log("WARN bridge", a, b, "passes", round(lo, 1), "m over the rock")
    ctx.count("shrines", len(made))
    ctx.count("bridges", nb)
    ctx.count("shrine_tris", tris)
    return made


def json_safe(d):
    return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in d.items()}


# ---- entry ------------------------------------------------------------------------------------------------------

def build(scene=None, parts=PARTS):
    """Clear a previous run, then build ``parts`` (shrines first: the ledges keep off the bridge). Returns the
    counts per category."""
    t0 = time.perf_counter()
    scene = scene or bpy.context.scene
    parts = tuple(p for p in PARTS if p in parts)
    clear(parts)
    ctx = Ctx(scene)
    if "shrines" not in parts:          # the bridge stays: keep the new ledge trees off it all the same
        ctx.bridges = sorted({(tuple(o["life_p0"]), tuple(o["life_p1"])) for o in bpy.data.objects
                              if o.get(TAG) == "bridge" and "life_p0" in o.keys()})
    _log("peaks", len(ctx.rng_.peaks), "measured tops", sum(t is not None for t in ctx.tops),
         "prototypes", {k: len(v) for k, v in ctx.protos.items()}, "links", ctx.n_links)
    if "shrines" in parts:
        build_shrines(ctx)
    if "ledges" in parts:
        build_ledges(ctx)
    if "islands" in parts:
        build_islands(ctx)
    n_obj = sum(1 for o in bpy.data.objects if o.get(TAG))
    ctx.counts["objects"] = n_obj
    ctx.counts["seconds"] = round(time.perf_counter() - t0, 1)
    _log("counts", ctx.counts)
    return ctx.counts


# ---- round 48: life in the range (plan r45 C, critique P13: signs of the sect living out there) ---------------------
# Two plank walkways 栈道 climbing round two of the round-48 pillars that the holds see 200-650 m off, each from the
# forested plinth at the pillar's foot (ground the range carries: reachable) up about a third of the pillar to a deck
# with a small pavilion tucked against the wall, and one more pavilion at the foot of a third pillar. Low-poly (seen
# from 200 m and more), wood and the shrines' materials, all in COLL tagged TAG = 'r48path'. Each walkway's both ends
# connect (sect-architecture: the foot stands on the plinth, the top ends on its deck). sect/patch_r48_life.py runs it.
PATH_PILLARS = 2               # pillars with a walkway
PATH_FOOT_ROOFS = 1            # more pavilions at a pillar's foot
PATH_D = (200.0, 650.0)        # m from the nearest hold camera
PATH_W = 1.8                   # walkway width (m)
PATH_GRADE = 0.18              # rise per metre along it
PATH_DS = 1.5                  # m between samples along it
PATH_RISE = (0.3, 45.0)        # it climbs this share of the pillar's height over its plinth, at most this many m
PATH_TAG = "r48path"
PATH_AWAY = 150.0              # m: nothing of a walkway or pavilion nearer the camera path (phase C: two pavilions
                               # stood 129 and 150 m off it; candidates now keep their whole reach this far away)


def _pillar_objects():
    return [o for o in bpy.data.objects if o.type == 'MESH' and "r48_peak" in o.keys() and "nature_top_z" in o.keys()
            and not o.hide_render]


def path_candidates(hold_views):
    """[(score, pillar, hold, azimuth facing that hold)]: round-48 pillars a hold shows whole-ish, PATH_D m off."""
    from sect.lib import r48 as R
    out = []
    path = R.path_points(2)
    for ob in _pillar_objects():
        p = np.array(ob.matrix_world.translation)
        tz = float(ob["nature_top_z"])
        reach = float(ob["nature_top_radius"]) * 1.7 + 14.0          # the foot pavilion's ring, plus its deck
        if len(path) and float(np.hypot(path[:, 0] - p[0], path[:, 1] - p[1]).min()) < PATH_AWAY + reach:
            continue
        best = None
        for v in hold_views:
            d = float(np.linalg.norm(p[:2] - v.pos[:2]))
            if not PATH_D[0] <= d <= PATH_D[1]:
                continue
            u, vv, dd = v.project([(p[0], p[1], tz), (p[0], p[1], float(ob.get("r48_plinth", tz - 60.0)))])
            if (dd <= 0).any() or not (0.08 < u[0] < 0.92) or vv[0] < 0.02 or vv[1] > 1.1:
                continue
            sc = float(v.px(2 * float(ob["nature_top_radius"]), dd[0]))
            if best is None or sc > best[0]:
                az = math.atan2(v.pos[1] - p[1], v.pos[0] - p[0])
                best = (sc, ob, v.name, az)
        if best is not None:
            out.append(best)
    out.sort(key=lambda b: -b[0])
    return out


def _wall_hit(bvh, mw, mwi, axis, th, z, reach):
    """World point where a horizontal ray from outside toward the pillar's axis at height z, azimuth th, meets it."""
    d = Vector((math.cos(th), math.sin(th), 0.0))
    src = Vector((float(axis[0]), float(axis[1]), z)) + d * reach
    hit = bvh.ray_cast(mwi @ src, (mwi.to_3x3() @ -d).normalized(), reach * 1.5)[0]
    return None if hit is None else mw @ hit


def _walkway_geo(g, pts, outs):
    """Planks, outer rail posts and rail, and a brace under every other post, along samples pts (wall points) with
    outward unit vectors outs. Geo in world coordinates; materials MI_WOOD / MI_RED."""
    n = len(pts)
    for i in range(n - 1):
        a, b = pts[i], pts[i + 1]
        oa, ob_ = outs[i], outs[i + 1]
        base = len(g.v)
        for p, o in ((a, oa), (b, ob_)):
            for w in (0.15, PATH_W):
                for dz in (0.0, -0.18):
                    g.vert((p[0] + o[0] * w, p[1] + o[1] * w, p[2] + dz))
        # per end: (in, top) (in, bottom) (out, top) (out, bottom); end a = base .. base+3, end b = base+4 .. base+7
        A, B = base, base + 4
        for q in ((A, A + 2, B + 2, B), (A + 1, B + 1, B + 3, A + 3), (A + 2, A + 3, B + 3, B + 2),
                  (A, B, B + 1, A + 1)):
            g.face(q, MI_WOOD)
        if i % 2 == 0:
            x, y = a[0] + oa[0] * (PATH_W - 0.1), a[1] + oa[1] * (PATH_W - 0.1)
            g.box(x - 0.07, x + 0.07, y - 0.07, y + 0.07, a[2], a[2] + 1.0, MI_RED)
            g.obox((a[0] + oa[0] * 0.2, a[1] + oa[1] * 0.2), (a[0] + oa[0] * (PATH_W - 0.2), a[1] + oa[1] * (PATH_W - 0.2)),
                   0.14, a[2] - 1.4, a[2] - 0.2, MI_WOOD)
    for i in range(0, n - 2, 2):
        a, b = pts[i], pts[i + 2]
        oa, ob_ = outs[i], outs[i + 2]
        g.obox((a[0] + oa[0] * (PATH_W - 0.1), a[1] + oa[1] * (PATH_W - 0.1)),
               (b[0] + ob_[0] * (PATH_W - 0.1), b[1] + ob_[1] * (PATH_W - 0.1)), 0.08,
               (a[2] + b[2]) * 0.5 + 0.9, (a[2] + b[2]) * 0.5 + 1.0, MI_RED)


def _pavilion_obj(coll, name, loc, yaw, s=0.55, deck=None):
    """A small pavilion (pavilion_geo) at loc, its front (-Y) turned to yaw; deck = (depth, width) adds a wooden
    deck under it reaching back toward the wall. Returns the object."""
    g, _info = pavilion_geo(6, s, False)
    if deck is not None:
        dep, wid = deck
        g.box(-wid / 2, wid / 2, -dep / 2, dep / 2 + 2.5, -0.5, 0.0, MI_WOOD, top_mat=MI_WOOD)
    mats = ["roof_tile_black" if m == "ROOF" else m for m in SHRINE_MATS]
    ob = U.mesh_from_pydata(U.unique_name(name), g.v, g.f, coll, materials=mats, smooth=False,
                            material_indices=g.m, location=loc, rotation=(0.0, 0.0, yaw))
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return ob


def build_paths(scene, hold_views, log=None):
    """Round 48 (see PATH_*): walkways round PATH_PILLARS pillars, each ending at a deck pavilion, and PATH_FOOT_ROOFS
    pavilions at the foot of the next pillars. Removes an earlier run's first. Returns counts and per-path facts."""
    log = log or _log
    root = U.get_collection(PARENT_COLL, scene=scene)
    coll = U.get_collection(COLL, parent=root, scene=scene)
    for o in [o for o in bpy.data.objects if o.get(TAG) == PATH_TAG]:
        bpy.data.objects.remove(o, do_unlink=True)
    cands = path_candidates(hold_views)
    surf = Surface(bpy.data.objects["world.range"])
    dg = bpy.context.evaluated_depsgraph_get()
    facts = []
    made = 0
    used = set()
    for sc, ob, hold, az in cands:
        if sum(1 for f in facts if f["kind"] == "walkway") >= PATH_PILLARS:
            break
        p = np.array(ob.matrix_world.translation)
        tz = float(ob["nature_top_z"])
        tr = float(ob["nature_top_radius"])
        plinth = float(ob.get("r48_plinth", tz - 60.0))
        ground = surf.down(p[0] + math.cos(az) * (tr * 1.6 + 6.0), p[1] + math.sin(az) * (tr * 1.6 + 6.0), tz + 50.0,
                           900.0)
        if ground is None:
            continue
        z0 = float(ground[0].z) + 0.35
        rise = min(PATH_RISE[1], PATH_RISE[0] * (tz - plinth))
        if rise < 12.0:
            continue
        bvh = BVHTree.FromObject(ob, dg)
        mw = ob.matrix_world.copy()
        mwi = mw.inverted()
        reach = tr * 3.0 + 30.0
        th = az - 0.6                                       # start a little left of the face the hold sees
        z = z0
        pts, outs = [], []
        ok = True
        while z < z0 + rise:
            h = _wall_hit(bvh, mw, mwi, p, th, z + 0.6, reach)
            if h is None:
                ok = False
                break
            o = (math.cos(th), math.sin(th))
            pts.append((h.x + o[0] * 0.1, h.y + o[1] * 0.1, z))
            outs.append(o)
            th += PATH_DS / max(4.0, math.hypot(h.x - p[0], h.y - p[1]))
            z += PATH_DS * PATH_GRADE
        if not ok or len(pts) < 8:
            log("WARN walkway on", ob.name, "lost the wall; skipped")
            continue
        g = Geo()
        _walkway_geo(g, pts, outs)
        wk = U.mesh_from_pydata(U.unique_name("life.r48.walkway"), g.v, g.f, coll,
                                materials=["roof_tile_black" if m == "ROOF" else m for m in SHRINE_MATS],
                                smooth=False, material_indices=g.m)
        bm = bmesh.new()
        bm.from_mesh(wk.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(wk.data)
        bm.free()
        wk.data.update()
        _tag(wk, PATH_TAG)
        top = pts[-1]
        o = outs[-1]
        yaw = math.atan2(o[0], -o[1])                       # the pavilion's front (-Y) faces out of the wall
        pv = _pavilion_obj(coll, "life.r48.pavilion", (top[0] + o[0] * 3.2, top[1] + o[1] * 3.2, top[2]), yaw,
                           deck=(6.0, 6.5))
        _tag(pv, PATH_TAG)
        made += 2
        used.add(ob.name)
        facts.append(dict(kind="walkway", pillar=ob.name, hold=hold, px=round(sc, 1),
                          foot=[round(c, 1) for c in pts[0]], top=[round(c, 1) for c in top],
                          length=round(len(pts) * PATH_DS, 1), tris=g.tris()))
        log("walkway", ob.name, "seen from", hold, "%.0f px; %.0f m long, %.1f -> %.1f m" % (
            sc, len(pts) * PATH_DS, pts[0][2], top[2]))
    for sc, ob, hold, az in cands:
        if sum(1 for f in facts if f["kind"] == "foot") >= PATH_FOOT_ROOFS:
            break
        if ob.name in used:
            continue
        p = np.array(ob.matrix_world.translation)
        r0 = float(ob["nature_top_radius"]) * 1.7 + 7.0
        q = (p[0] + math.cos(az) * r0, p[1] + math.sin(az) * r0)
        hit = surf.down(q[0], q[1], float(ob["nature_top_z"]) + 50.0, 900.0)
        if hit is None or hit[1].z < 0.85:
            continue
        pv = _pavilion_obj(coll, "life.r48.pavilion", (q[0], q[1], float(hit[0].z) - 0.05),
                           math.atan2(math.cos(az), -math.sin(az)), s=0.6)
        _tag(pv, PATH_TAG)
        made += 1
        used.add(ob.name)
        facts.append(dict(kind="foot", pillar=ob.name, hold=hold, at=[round(q[0], 1), round(q[1], 1)]))
        log("foot pavilion at", ob.name, "seen from", hold)
    return dict(objects=made, paths=facts)
