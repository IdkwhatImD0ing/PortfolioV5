"""Area 9: Grand Sect-Protecting Formation 护宗大阵 (site section 'architecture').

Round 6 (2026-10-21): the array is carved stone and cast bronze with the light inside it, not light drawn on top of
the world. A 100 m round plaza of weathered bluestone with bronze and jade set into it:

- the floor: aged bluestone slabs; round the dais a polished ink-stone band with the eight trigrams cast in bronze
  (a warm glow leaks from under each bar); a recessed jade channel ring; from it a short glowing channel between
  stone curbs runs to each brazier; the Ming Sect's chant 焚我残躯，熊熊圣火... carved in gold round a black band;
  moss at the rim, round the plinths and in the cracks;
- eight array-eye stations 陣眼 (formation.pillar.0-7, prototype formation.p.station; the page's arch:k hotspots):
  huabiao columns with a coiling stone dragon, a cloud plate, a lotus dew plate and a jade eye held in bronze claws
  (sect/lib/array_props.py), each with its trigram on a bronze plaque;
- a bronze tripod holy-fire brazier 圣火盆 in front of each station (formation.brazier.0-7), with the area's eight
  warm point lights;
- the bronze armillary sphere 浑天仪 on the dais (formation.armillary, static: pedestal, four dragon pillars, horizon
  and meridian rings, the sect's sun-and-moon finial) and its turning rings round the sun-fire core
  (formation.core, the 'formation' hotspot, turned by the page and by a driver);
- the Ming Sect's Five Element Banners 五行旗 on the east rim (formation.flag.<wood|fire|earth|metal|water>, front to
  back in the generating order 木火土金水) on carved stone drums with the sect's emblem;
- the Quanzhen Big Dipper array 天罡北斗阵: seven star-stones on the west side (formation.dipper.<star>) joined by
  inlaid silver lines;
- stone lanterns along the axis walk, a censer before the front dais stair, a marble balustrade round the rim, a
  three-bay paifang with the 护宗大阵 plaque at the front (-Y) and a one-bay rear gate.
The protective barrier and the soft light shafts are drawn by the page (the bake leaves the dome out); no light
beams are built here.

Walking route (docs/architecture-audit.md 1.9 and 4): the stair from the scroll ends at the arrival (0, -62) on the
terrace grass; three low steps climb onto a paved front apron flanked by two stone lanterns, which runs to the plaza
rim and the paifang. A white paved strip on the axis crosses the floor to the core dais, which has three short flights
(one per tier, the tier tops are the landings) at each compass point; on the top tier the walk goes round the
armillary's pedestal between its dragon pillars. Behind the dais the strip runs on to a one-bay rear gate in a 12 m
opening of the balustrade, then a rear apron and three steps down to the depart point (0, 62), where the stair to the
abode starts. The two aprons reach about 4 m past the footprint radius, still well inside world.py's terrace
(footprint + TERRACE_PAD). Nothing new stands on the axis strip (|x| <= 2) except the censer, which the walk passes.

Local frame: origin = plaza centre, z = 0 walkable top, front faces -Y.
"""

import math

import bmesh
import bpy
from mathutils import Vector

from sect.lib import util as U
from sect.lib import materials as M
from sect.lib import arch as A
from sect.lib import props as P
from sect.lib import array_props as AP

# arrival / depart: where the incoming and outgoing connector stairs meet this area, as
# (x, y, z, heading) in the local frame. z is the stair's end step level (terrace grass, -0.4);
# heading is the walking direction in radians, counter-clockwise from local +X (pi/2 = +Y), so
# world heading = heading + anchor yaw. Values from docs/architecture-audit.md 1.9 (W1).
AREA = dict(key="formation", section_id="architecture", title_en="Grand Sect-Protecting Formation",
            title_zh="护宗大阵", footprint=58.0,
            arrival=(0.0, -62.0, -0.4, math.pi / 2),
            depart=(0.0, 62.0, -0.4, math.pi / 2))

KEY = "formation"

# Where the fly-through camera should pass (LOCAL, front = -Y), ordered along the flight:
# a rising approach from the south, a high oblique, then the overhead shot.
CAMERA_HINTS = [
    dict(name="approach", location=(0.0, -135.0, 42.0), target=(0.0, 0.0, 10.0), lens=28),
    dict(name="high", location=(0.0, -92.0, 92.0), target=(0.0, 2.0, 0.0), lens=24),
    dict(name="overhead", location=(0.0, -40.0, 150.0), target=(0.0, 4.0, 0.0), lens=24),
]

# ---------------------------------------------------------------------------- layout
R_PLAZA = 50.0          # plaza radius (100 m across)
R_DARK = 46.0           # inner floor radius (the gold inlay ring and the white rim beyond it)
R_DAIS = 11.0           # core dais bottom tier
R_STATION = 29.0        # ring of the 8 array-eye stations
R_BRAZIER = 24.6        # each station's brazier, on its inward side
R_BAGUA = (12.5, 17.65)       # polished ink-stone band with the bronze trigrams
R_CHANNEL = (17.65, 18.85)    # recessed jade channel ring
CHANNEL_DEPTH = 0.15
R_CHANT = (20.5, 23.5)        # black band with the chant
CHANT_R, CHANT_H = 22.0, 1.7
R_RADIAL = (18.9, 23.6)       # radial channels from the jade ring to each brazier
AXIS_CLEAR = 2.3        # half width round the axis walk kept free of inlays and moss
GATE_Y = -46.5          # paifang position on the front axis
REAR_GATE_Y = 46.5      # one-bay rear gate on the back axis
APRON_Y = 61.0          # outer edge of the front / rear aprons (top z 0); steps go down to +-62
APRON_HW = (7.0, 6.0)   # half widths of the front and rear aprons
STRIP_HW = 2.0          # half width of the white axis strip across the floor
STRIP_Z = 0.004

# station k sits at angle 22.5 + 45 k degrees (from +X, counter-clockwise), so the front axis
# (-Y, 270 deg) falls in the gap between stations 5 and 6. Its trigram (bagua bars, plaque) in this order.
STATION_ANGLES = [math.radians(22.5 + 45.0 * k) for k in range(8)]
TRIGRAMS = ["兑", "乾", "巽", "坎", "艮", "坤", "震", "离"]
PILLAR_ANGLES = STATION_ANGLES                       # older name (export docs)

CHANT = "焚我残躯，熊熊圣火。生亦何欢，死亦何苦？为善除恶，惟光明故。喜乐悲愁，皆归尘土。怜我世人，忧患实多！"

# The Ming Sect's Five Element Banners 五行旗 (倚天屠龙记): (element, flag character, angle on the rim in degrees,
# banner cloth index, brigade name). Front to back in the generating order 木 -> 火 -> 土 -> 金 -> 水; the angles keep
# every flag clear of the stations, the armillary and the rear gate on screen at the hold (frame 1208).
R_FLAGS = 45.0
ELEMENT_FLAGS = [
    ("wood", "木", 10.0, 2, "巨木旗"),     # jade
    ("fire", "火", 24.0, 0, "烈火旗"),     # vermilion
    ("earth", "土", 38.0, 1, "厚土旗"),    # imperial gold, ink trim
    ("metal", "金", 52.0, 5, "锐金旗"),    # moon white, ink trim
    ("water", "水", 66.0, 7, "洪水旗"),    # ink black (the water banner is black), gold trim
]

# The Quanzhen Big Dipper array 天罡北斗阵 (射雕英雄传): seven star-stones on the west side, (pinyin, name, x, y);
# the ladle's bowl on the left, its handle rising toward the rear gate (layout search: every star at least 7.8 m
# from any station, nothing covers a star at the hold).
DIPPER = [
    ("yaoguang", "摇光", -22.0, 38.0),     # Alkaid, the handle tip
    ("kaiyang", "开阳", -24.3, 29.1),      # Mizar
    ("yuheng", "玉衡", -26.9, 23.7),       # Alioth
    ("tianquan", "天权", -30.8, 19.1),     # Megrez
    ("tianji", "天玑", -36.5, 21.3),       # Phecda
    ("tianxuan", "天璇", -41.7, 14.8),     # Merak
    ("tianshu", "天枢", -36.6, 9.4),       # Dubhe
]
DIPPER_LINKS = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 3)]

AXIS_LANTERNS = [(sx * 3.6, sy * y) for sy in (-1.0, 1.0) for y in (26.0, 37.0) for sx in (-1.0, 1.0)]
CENSER_Y = -15.2

CORE_Z = AP.ARM_Z       # the turning core's centre (formation.core)
CORE_SPEED = 0.0025     # rad per frame (the page: 0.06 rad/s at 24 fps)

R6_MATERIALS = ("formation_paving_bluestone", "formation_paving_ink", "formation_marble_aged",
                "formation_stone_carved", "formation_rune_goldleak", "formation_rune_jade", "formation_rune_star",
                "formation_rune_sun", "formation_jade_glow_eye")


def _materials():
    # M.variant() cannot override a builder parameter called 'base' (it clashes with variant's
    # own 'base' argument), so register the paving builder directly.
    builder, p = M._REGISTRY["marble_paving"]
    p = dict(p)
    p.update(base="#5f5d58", alt="#55534e", grout="#2b2926", slab=(1.8, 1.2), joint=0.014)
    M.register("formation_paving_bluestone", builder, **p)
    # polished ink stone for the trigram and chant bands ('paving' in the name: walkable for the walk check)
    builder, p = M._REGISTRY["stone_dark"]
    p = dict(p)
    p.update(c1="#34322f", c2="#292725", speck="#121110", rough=(0.2, 0.36), bump=0.05, light="#4d4943",
             light_amt=0.18)
    M.register("formation_paving_ink", builder, **p)
    M.variant("formation_marble_aged", "marble_white", grime=0.5, veins=0.25)
    M.variant("formation_stone_carved", "stone_grey", c1="#8d8a82", moss=0.35)
    # glows: soft, warm or pale, never fully saturated (bake classes: rune_gold, formation_rune, jade_glow)
    M.variant("formation_rune_goldleak", "rune_gold", colour="#ffbe63", core="#fff0c8", strength=1.0)
    M.variant("formation_rune_jade", "rune_cyan", colour="#6fd9b4", core="#d6fff0", strength=1.2)
    M.variant("formation_rune_star", "rune_silver", colour="#c8d8ff", core="#f4f8ff", strength=1.6)
    M.variant("formation_rune_sun", "rune_gold", colour="#ffcf80", core="#fff4dc", strength=3.0)
    M.variant("formation_jade_glow_eye", "jade_glow", strength=0.9)
    M.variant("formation_shield", "glass_shield", strength=0.4, cell=14.0)


# ---------------------------------------------------------------------------- bmesh helpers

def _annulus(bm, r0, r1, z, segs):
    """Flat ring facing +Z."""
    a = [2.0 * math.pi * i / segs for i in range(segs)]
    v0 = [bm.verts.new((r0 * math.cos(t), r0 * math.sin(t), z)) for t in a]
    v1 = [bm.verts.new((r1 * math.cos(t), r1 * math.sin(t), z)) for t in a]
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((v0[i], v1[i], v1[j], v0[j]))


def _wall(bm, r, z_top, z_bot, segs):
    """Vertical cylinder wall facing outward."""
    a = [2.0 * math.pi * i / segs for i in range(segs)]
    b = [bm.verts.new((r * math.cos(t), r * math.sin(t), z_bot)) for t in a]
    t_ = [bm.verts.new((r * math.cos(t), r * math.sin(t), z_top)) for t in a]
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((b[i], b[j], t_[j], t_[i]))


def _obj(name, bm, coll, mat, parent, smooth=False, glow=None, shadow=True, **kw):
    ob = U.mesh_from_bmesh(name, bm, coll, materials=[mat], smooth=smooth, parent=parent, **kw)
    if glow is not None:
        ob["glow"] = glow
    if not shadow:
        U.set_visibility(ob, shadow=False)
    return ob


def _axis_gap(r, half=AXIS_CLEAR):
    return math.asin(min(1.0, half / r))


# ---------------------------------------------------------------------------- floor

def _floor(coll, root):
    """Bluestone plaza, the polished ink-stone bands (trigrams, chant) and the recessed jade channel ring, which
    stops either side of the axis walk (plain ink stone there, under the walk)."""
    bm = bmesh.new()
    rings = [(R_DAIS - 0.5, R_BAGUA[0]), (R_CHANNEL[1], R_CHANT[0])]
    rs = [R_CHANT[1] + 3.0 * i for i in range(8)] + [R_DARK]
    rs = sorted(set(r for r in rs if r <= R_DARK))
    rings += list(zip(rs[:-1], rs[1:]))
    for r0, r1 in rings:
        _annulus(bm, r0, r1, 0.0, 192)
    AP.mk(U.name(KEY, "floor"), bm, coll, [AP.M_BLUE], parent=root, smooth=False)

    g = _axis_gap(0.5 * sum(R_CHANNEL))
    bm = bmesh.new()
    _annulus(bm, R_BAGUA[0], R_BAGUA[1], 0.0, 192)
    _annulus(bm, R_CHANT[0], R_CHANT[1], 0.0, 192)
    for ac in (math.pi / 2, 1.5 * math.pi):
        P._annulus(bm, R_CHANNEL[0], R_CHANNEL[1], 6, 0.0, ac - g, ac + g)
    AP.mk(U.name(KEY, "floor_band"), bm, coll, [AP.M_INK], parent=root, smooth=False)

    arcs = [(math.pi / 2 + g, 1.5 * math.pi - g), (-math.pi / 2 + g, math.pi / 2 - g)]
    bm_glow, bm_wall = bmesh.new(), bmesh.new()
    AP.jade_channel(bm_glow, bm_wall, R_CHANNEL[0], R_CHANNEL[1], CHANNEL_DEPTH, arcs)
    AP.mk(U.name(KEY, "channel"), bm_glow, coll, [AP.M_JADE], parent=root, smooth=False, glow=1.0, shadow=False)
    AP.mk(U.name(KEY, "channel_walls"), bm_wall, coll, [AP.M_INK], parent=root, smooth=False)


def _inlays(coll, root):
    """Bronze trigrams with their gold leak, diamond studs, radial channels, the chant ring and the moss."""
    bm_bar, bm_leak = bmesh.new(), bmesh.new()
    AP.bagua(bm_bar, bm_leak, STATION_ANGLES, TRIGRAMS)
    AP.studs(bm_bar, [math.radians(45.0 * k) for k in range(8) if k not in (2, 6)])
    AP.mk(U.name(KEY, "bagua"), bm_bar, coll, [AP.M_BRONZE], parent=root, smooth=False, bevel=0.02)
    AP.mk(U.name(KEY, "bagua_leak"), bm_leak, coll, [AP.M_LEAK], parent=root, smooth=False, glow=1.0,
          shadow=False)

    bm_glow, bm_curb, bm_collar = bmesh.new(), bmesh.new(), bmesh.new()
    for t in STATION_ANGLES:
        AP.radial_channel(bm_glow, bm_curb, bm_collar, t, R_RADIAL[0], R_RADIAL[1])
    AP.mk(U.name(KEY, "radial_channels"), bm_glow, coll, [AP.M_JADE], parent=root, smooth=False, glow=0.85,
          shadow=False)
    AP.mk(U.name(KEY, "radial_curbs"), bm_curb, coll, [AP.M_MARBLE], parent=root, smooth=False, bevel=0.025)
    AP.mk(U.name(KEY, "radial_collars"), bm_collar, coll, [AP.M_BRONZE], parent=root, smooth=False, bevel=0.015)

    # the chant, clockwise from the rear axis, tops of the glyphs outward; it skips the channels and the walk
    gaps = [(t, math.radians(3.8)) for t in STATION_ANGLES] + \
           [(math.pi / 2, math.radians(7.7)), (1.5 * math.pi, math.radians(7.7))]
    placed, dots, _pitch = AP.chant_layout(CHANT, gaps, start=math.pi / 2 - math.radians(7.7))
    bm = bmesh.new()
    AP.chant_glyphs(bm, placed, CHANT_R, CHANT_H)
    AP.mk(U.name(KEY, "chant"), bm, coll, [AP.M_GOLD], parent=root, smooth=False)
    bm = bmesh.new()
    AP.dots(bm, dots, CHANT_R)
    AP.mk(U.name(KEY, "chant_dots"), bm, coll, [AP.M_BRONZE], parent=root, smooth=math.radians(40))

    bm = bmesh.new()
    AP.moss_patches(bm, _moss_spots(), 77)
    AP.mk(U.name(KEY, "moss"), bm, coll, ["moss"], parent=root, smooth=False)


def _moss_spots():
    """Moss patches (x, y, size): thick at the rim foot and the balustrade foot, round every plinth, star-stone and
    flag drum, a few in the paving cracks; never on the axis walk, the channels or the bands."""
    r = U.rng("formation_moss_r6")
    spots = []

    def ok(x, y, s):
        if abs(x) < AXIS_CLEAR + 0.5 * s:
            return False
        rr = math.hypot(x, y)
        if rr < R_CHANT[1] + 0.4 + 0.5 * s and rr > R_DAIS - 0.5:
            return False
        a = math.atan2(y, x)
        for t in STATION_ANGLES:                         # brazier and its channel
            d = (a - t + math.pi) % (2 * math.pi) - math.pi
            if abs(d) * rr < 1.6 and rr < R_BRAZIER + 1.4:
                return False
        for _k, _c, deg, _m, _b in ELEMENT_FLAGS:       # drums
            t = math.radians(deg)
            if math.hypot(x - R_FLAGS * math.cos(t), y - R_FLAGS * math.sin(t)) < 1.0 + 0.4 * s:
                return False
        for _p, _n, sx, sy in DIPPER:
            if math.hypot(x - sx, y - sy) < 1.25:
                return False
        for lx, ly in AXIS_LANTERNS:
            if math.hypot(x - lx, y - ly) < 0.6:
                return False
        return True

    def add(x, y, s):
        if ok(x, y, s):
            spots.append((x, y, s))

    for _ in range(70):                                  # rim foot
        a = r.uniform(0, 2 * math.pi)
        rr = r.uniform(44.2, 45.75)
        add(rr * math.cos(a), rr * math.sin(a), r.uniform(0.5, 1.9))
    for t in STATION_ANGLES:                             # round the station plinths
        for _ in range(7):
            a = t + r.uniform(-0.55, 0.55)
            rr = r.uniform(25.95, 26.6) if abs(a - t) < 0.12 else R_STATION + r.uniform(3.3, 3.9) * \
                (1 if r.random() < 0.6 else -1)
            add(rr * math.cos(a), rr * math.sin(a), r.uniform(0.4, 1.3))
    for _p, _n, sx, sy in DIPPER:                        # round the star platforms
        for _ in range(3):
            a = r.uniform(0, 2 * math.pi)
            d = r.uniform(1.4, 1.8)
            add(sx + d * math.cos(a), sy + d * math.sin(a), r.uniform(0.3, 0.8))
    for _ in range(26):                                  # in the paving cracks
        a = r.uniform(0, 2 * math.pi)
        rr = r.uniform(24.5, 43.5)
        add(rr * math.cos(a), rr * math.sin(a), r.uniform(0.3, 0.7))
    return spots


# ---------------------------------------------------------------------------- dais

def _dais(coll, root):
    """Three stepped round marble tiers under the armillary."""
    bm = bmesh.new()
    tiers = [(R_DAIS, 0.5), (R_DAIS - 1.4, 1.0), (R_DAIS - 2.6, 1.5)]
    for r, h in tiers:
        _wall(bm, r, h, -0.3, 96)
    _obj(U.name(KEY, "dais_sides"), bm, coll, AP.M_MARBLE, root)
    bm = bmesh.new()
    for r, h in tiers:
        _annulus(bm, max(0.5, r - 1.4) if r != tiers[-1][0] else 0.5, r, h, 96)
    # close the very centre of the top tier
    v = [bm.verts.new((0.5 * math.cos(2 * math.pi * i / 96), 0.5 * math.sin(2 * math.pi * i / 96), 1.5))
         for i in range(96)]
    bm.faces.new(v)
    _obj(U.name(KEY, "dais_top"), bm, coll, "marble_paving", root)
    _dais_stairs(coll, root, tiers)
    return tiers[-1][1]


def _dais_stairs(coll, root, tiers):
    """A flight at each compass point, like the Circular Mound Altar: per tier, three 0.167 m
    risers up to that tier's edge, so every tier top is the landing between flights (9 risers in
    all). One flight per tier instead of one 1.5 m flight through all three tiers: a single
    flight's treads at z 0.5 and 1.0 would lie in the same plane as the tier tops and z-fight."""
    i = 0
    for phi in (-math.pi / 2, math.pi / 2, 0.0, math.pi):      # front, back, east, west
        for r, h in tiers:
            A.stairs(U.name(KEY, "dais_stairs", i), coll, 3.0, 0.5, ramp=False, balustrade=False,
                     parent=root, location=(r * math.cos(phi), r * math.sin(phi), h - 0.5),
                     rotation_z=phi + math.pi / 2)
            i += 1


def _arc_slab(name, coll, root, hw, r_arc, y_end, sign, top, bottom=None,
              mats=("marble_white", "marble_paving")):
    """Slab x -hw..hw between the circle r_arc (that edge follows the arc, so it meets a round
    edge without overlapping it) and the straight edge y = sign * y_end. Top face at ``top`` gets
    mats[1]; bottom=None builds only the top face (a floor inlay)."""
    xs = [-hw + 2.0 * hw * i / 16 for i in range(17)]
    ring = [(x, sign * math.sqrt(r_arc * r_arc - x * x)) for x in xs] + [(hw, sign * y_end), (-hw, sign * y_end)]
    area = sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1]
               for i in range(len(ring)))
    if area < 0:
        ring.reverse()
    n = len(ring)
    verts = [(x, y, top) for x, y in ring]
    faces = [tuple(range(n))]
    mi = [1]
    if bottom is not None:
        verts += [(x, y, bottom) for x, y in ring]
        faces.append(tuple(n + k for k in reversed(range(n))))
        mi.append(0)
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((k, n + k, n + k2, k2))
            mi.append(0)
    return U.mesh_from_pydata(U.name(KEY, name), verts, faces, coll, materials=list(mats),
                              material_indices=mi, smooth=False, parent=root)


def _route(coll, root):
    """Front approach and rear exit on the axis, plus the white strip across the floor."""
    # front: paved apron from the plaza edge to y -61, three low steps down to the arrival
    _arc_slab("arrival_apron", coll, root, APRON_HW[0], R_PLAZA, APRON_Y, -1.0, 0.0, -1.2)
    A.stairs(U.name(KEY, "arrival_steps"), coll, 8.0, 0.4, ramp=False, balustrade=False, parent=root,
             location=(0.0, -APRON_Y, -0.4))
    for sx in (-1.0, 1.0):
        P.lantern_stone(coll, name=U.name(KEY, "lantern"), parent=root, location=(sx * 5.0, -59.5, 0.0))
    # rear: apron behind the rear gate and three steps down to the depart point
    _arc_slab("depart_apron", coll, root, APRON_HW[1], R_PLAZA, APRON_Y, 1.0, 0.0, -1.2)
    A.stairs(U.name(KEY, "depart_steps"), coll, 8.0, 0.4, ramp=False, balustrade=False, parent=root,
             location=(0.0, APRON_Y, -0.4), rotation_z=math.pi)
    # white strip on x 0 from the floor's edge to the foot of each dais flight (0.99 m run
    # from the bottom tier at r 11); the rim beyond R_DARK is already white paving
    foot = R_DAIS + 0.9
    for sign in (-1.0, 1.0):
        _arc_slab("axis_walk", coll, root, STRIP_HW, R_DARK, foot, sign, STRIP_Z,
                  mats=("marble_paving", "marble_paving"))


# ---------------------------------------------------------------------------- armillary and core

def _set_core_driver(core):
    if core.animation_data is not None:
        for fc in list(core.animation_data.drivers):
            if fc.data_path == "rotation_euler":
                core.animation_data.drivers.remove(fc)
    fc = core.driver_add("rotation_euler", 2)
    fc.driver.type = 'SCRIPTED'
    fc.driver.expression = "frame*%s" % CORE_SPEED


def _core(coll, root, dais_top):
    """The bronze armillary sphere on the dais: static frame under 'formation.armillary' (pedestal, four dragon
    pillars, horizon and meridian rings, the sun-and-moon finial) and the turning set under 'formation.core' (the
    'formation' hotspot; reused when it exists): equatorial, ecliptic and declination rings, polar axis and the
    sun-fire core. Driver: rotation z = frame * CORE_SPEED."""
    arm = AP.tag(U.empty(U.name(KEY, "armillary"), coll, parent=root, display_size=3))
    bm_b, bm_v = bmesh.new(), bmesh.new()
    AP.armillary_static(bm_b, bm_v, dais_top)
    P._outward(bm_b)
    P._outward(bm_v)
    AP.mk(U.name(KEY, "armillary.bronze"), bm_b, coll, [AP.M_BRONZE, AP.M_GOLD], parent=arm, smooth=math.radians(40))
    AP.mk(U.name(KEY, "armillary.dragons"), bm_v, coll, [AP.M_VERD, AP.M_GOLD], parent=arm, smooth=math.radians(50))
    fin = P.sunmoon_finial(coll, R=0.5, name=U.name(KEY, "armillary.finial"), parent=arm,
                           location=(0.0, 0.0, AP.ARM_Z + AP.ARM_R + 0.225))
    AP.tag_tree(fin)

    core = bpy.data.objects.get(KEY + ".core")
    if core is None:
        core = U.empty(KEY + ".core", coll, parent=root, display_size=3)
    U.parent(core, root, keep_transform=False)
    core.location = (0.0, 0.0, CORE_Z)
    core.rotation_euler = (0.0, 0.0, 0.0)
    _set_core_driver(core)
    bm_b, bm_c = bmesh.new(), bmesh.new()
    AP.armillary_turning(bm_b, bm_c)
    P._outward(bm_b)
    AP.mk(U.name(KEY, "core.rings"), bm_b, coll, [AP.M_BRONZE, AP.M_GOLD], parent=core, smooth=math.radians(40))
    AP.mk(U.name(KEY, "core.sun"), bm_c, coll, [AP.M_SUN], parent=core, smooth=True, glow=1.0)
    return core


# ---------------------------------------------------------------------------- stations and braziers

def _stations(coll, root):
    """The eight array-eye stations (instances 'formation.pillar.k' of 'formation.p.station', reused when they exist:
    they are the page's arch:k hotspots), each station's trigram plaque, and its brazier."""
    pc = U.proto_collection(KEY + ".p.station")
    if len(pc.all_objects) == 0:
        AP.station_proto(pc)
    out = []
    for k, t in enumerate(STATION_ANGLES):
        loc = (R_STATION * math.cos(t), R_STATION * math.sin(t), 0.0)
        nm = "%s.pillar.%d" % (KEY, k)
        ob = bpy.data.objects.get(nm)
        if ob is None:
            ob = U.collection_instance(pc, nm, coll, location=loc, rotation=(0.0, 0.0, t), parent=root)
        else:
            ob.instance_type = 'COLLECTION'
            ob.instance_collection = pc
            U.parent(ob, root, keep_transform=False)
            U.set_transform(ob, loc, (0.0, 0.0, t))
        AP.station_plaque(coll, nm + ".trigram", ob, TRIGRAMS[k])
        AP.brazier(coll, "%s.brazier.%d" % (KEY, k), root,
                   (R_BRAZIER * math.cos(t), R_BRAZIER * math.sin(t), 0.0), t)
        out.append(ob)
    return out


# ---------------------------------------------------------------------------- Five Element Banners, Big Dipper

def _flags(coll, root):
    """The Ming Sect's Five Element Banners on the east rim: tall qi flags (one character each), all flying toward
    -X (one wind; the cloth faces the camera), on carved drums whose centre-facing side carries the sect's emblem."""
    for k, (key, ch, deg, mat, brigade) in enumerate(ELEMENT_FLAGS):
        t = math.radians(deg)
        x, y = R_FLAGS * math.cos(t), R_FLAGS * math.sin(t)
        AP.flag_drum(coll, "%s.flag_base.%s" % (KEY, key), root, (x, y, 0.0), (-math.cos(t), -math.sin(t)), brigade)
        b = P.banner(coll, height=10.0, width=3.3, material=mat, style="qi", seed=k, text_zh=ch,
                     name="%s.flag.%s" % (KEY, key), parent=root, location=(x, y, AP.DRUM_H),
                     rotation=(0.0, 0.0, math.pi), scale=1.4)
        AP.tag_tree(b)


def _dipper(coll, root):
    """The Quanzhen Big Dipper: seven star-stones joined by inlaid silver lines on the floor."""
    bm = bmesh.new()
    for a, b in DIPPER_LINKS:
        pa = Vector((DIPPER[a][2], DIPPER[a][3], 0.0))
        pb = Vector((DIPPER[b][2], DIPPER[b][3], 0.0))
        d = (pb - pa).normalized()
        n = Vector((-d.y, d.x, 0.0)) * 0.225
        p0, p1 = pa + d * 1.3, pb - d * 1.3
        z = Vector((0.0, 0.0, 0.02))
        bm.faces.new([bm.verts.new(v + z) for v in (p0 - n, p1 - n, p1 + n, p0 + n)])
    AP.mk(U.name(KEY, "dipper.lines"), bm, coll, [AP.M_STAR], parent=root, smooth=False, glow=0.6, shadow=False)
    for i, (py, zh, x, y) in enumerate(DIPPER):
        L = math.hypot(x, y)
        AP.star_stone(coll, "%s.dipper.%s" % (KEY, py), root, (x, y, 0.0), (-x / L, -y / L), zh, variant=i % 3)


# ---------------------------------------------------------------------------- rim, gates, ritual details

def _rim(coll, root):
    """Aged marble balustrade around the rim in two arcs: open at the front for the paifang (11.9 deg
    each side, so it meets the outer columns without a slot) and at the back for the rear gate
    (83 to 97 deg: a 12 m opening at x -6..6)."""
    front = math.radians(11.9)
    back = math.radians(7.0)
    r = R_PLAZA - 0.7
    arcs = [(-math.pi / 2 + front, math.pi / 2 - back), (math.pi / 2 + back, 3 * math.pi / 2 - front)]
    for j, (a0, a1) in enumerate(arcs):
        n = max(8, int((a1 - a0) * r / 2.4))
        pts = [(r * math.cos(a0 + (a1 - a0) * i / n), r * math.sin(a0 + (a1 - a0) * i / n), 0.0)
               for i in range(n + 1)]
        A.balustrade(U.name(KEY, "balustrade", j), coll, pts, height=1.1, post_spacing=2.6,
                     end_drum="both", mat=AP.M_MARBLE, parent=root)


def _gate(coll, root):
    """Three-bay paifang on the front axis carrying the area plaque."""
    g = A.paifang(U.name(KEY, "paifang"), coll, bays=3, width=22.0, height=17.0, parent=root,
                  location=(0, GATE_Y, 0))
    anchor = bpy.data.objects.get(g.get("plaque_anchor", "")) if "plaque_anchor" in g else None
    pw = 4.6
    if "plaque_size" in g:
        pw = min(pw, float(g["plaque_size"][0]))
    if anchor is not None:
        P.plaque(coll, AREA["title_zh"], pw, rtl=True, name=U.name(KEY, "plaque"), parent=anchor)
    else:
        P.plaque(coll, AREA["title_zh"], pw, rtl=True, name=U.name(KEY, "plaque"), parent=g,
                 location=(0, -0.8, 11.0))
    # one-bay rear gate in the balustrade opening, facing out (+Y) where the stair to the abode starts
    A.paifang(U.name(KEY, "rear_gate"), coll, bays=1, width=10.0, height=11.0, parent=root,
              location=(0.0, REAR_GATE_Y, 0.0), rotation_z=math.pi)
    return g


def _ritual(coll, root):
    """Stone lanterns along the axis walk and a bronze censer before the front dais stair."""
    for x, y in AXIS_LANTERNS:
        AP.tag_tree(P.lantern_stone(coll, 2.4, lit=True, name=U.name(KEY, "lantern_axis"), parent=root,
                                    location=(x, y, 0.0)))
    AP.tag_tree(P.incense_burner(coll, 1.8, name=U.name(KEY, "censer"), parent=root, location=(0.0, CENSER_Y, 0.0)))


def build_array(coll, root, dais_top):
    """Everything round-6 adds (sect/patch_r6_formation.py calls this on an existing formation)."""
    _floor(coll, root)
    _inlays(coll, root)
    _core(coll, root, dais_top)
    _stations(coll, root)
    _flags(coll, root)
    _dipper(coll, root)
    _ritual(coll, root)


def _plaza(coll, root):
    """The white marble rim beyond the floor, the gold dividing inlay and the outer wall."""
    bm = bmesh.new()
    _annulus(bm, R_DARK + 0.35, R_DARK + 2.0, 0.0, 192)
    _annulus(bm, R_DARK + 2.0, R_PLAZA, 0.0, 192)
    _obj(U.name(KEY, "floor_rim"), bm, coll, "marble_paving", root)

    bm = bmesh.new()
    _annulus(bm, R_DARK, R_DARK + 0.35, 0.004, 192)
    _obj(U.name(KEY, "inlay_gold"), bm, coll, "gold", root)

    bm = bmesh.new()
    _wall(bm, R_PLAZA, 0.0, -1.0, 192)
    _annulus(bm, R_PLAZA, R_PLAZA + 1.2, -1.0, 192)
    _wall(bm, R_PLAZA + 1.2, -1.0, -2.8, 192)
    _obj(U.name(KEY, "plaza_edge"), bm, coll, AP.M_MARBLE, root)


def build(collection):
    """Build the whole formation at the local origin. Returns the root Empty 'formation.root'."""
    _materials()
    root = U.empty(U.name(KEY, "root"), collection, display_size=4)
    _plaza(collection, root)
    top = _dais(collection, root)
    _rim(collection, root)
    _gate(collection, root)
    _route(collection, root)
    build_array(collection, root, top)
    # the barrier: the page draws its own (createDomeMaterial); the bake leaves this additive dome out. No glowing
    # base ring (it baked as a neon line round the rim).
    P.shield_dome(collection, radius=R_PLAZA - 0.1, height=50.0, material="formation_shield", ring=False,
                  name=U.name(KEY, "dome"), parent=root)
    return root


build.preview_cameras = [(h["name"], h["location"], h["target"], h["lens"]) for h in CAMERA_HINTS]
