"""Sword-Discussion Arena 论剑台 (site section 'hackathons').

A floating island over a gap in the range: a 60 m circular stone dueling platform with
concentric rings and a taiji + glowing bagua inlay in the centre (round 34: in the bagua ring at the arena's north,
east, south and west, where four of its trigrams were, the bronze seat plates of the Mount Hua contests' Five Greats
北丐 東邪 南帝 西毒, the taiji the Centre's; lib/refs_east.py), 40 banner poles around the
rim (one per hackathon), a stepped spectator tier with viewing pavilions on the east (+X)
side, the Heavy Iron Sword 玄铁重剑 (a colossal plain black iron sword, Dugu Qiubai's from Return of
the Condor Heroes, whose iron became the gate's Dragon Saber) piercing the island at the back (+Y;
its round tip pokes out of the underside), an inverted craggy rock cone with hanging roots
underneath, small floating islets around it and massive chains running off to both sides.

Circulation (docs/architecture-audit.md 1.4 and 4): the forge chain bridge lands on a bridgehead
slab on the front axis (AREA['arrival']), under a three-bay gate; a paved strip and the front
steps climb to the banner band. Aisle stairs climb the spectator tier to its three pavilions.
Behind the sword on the left, a short stair drops from the band to a rear landing and a short
pier at the island edge, where the stepping stones to the Mission Hall start (AREA['depart']).
Low balustrades run along the island edge beside both landings.

Blocking pass: shapes, scale, colour coding and camera matter; fine detail does not.
Local frame: z = 0 is the dueling floor, front (camera arrival) faces -Y. The grassy island top
falls from about -1.3 next to the platform to -2.1 at its edge.
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from sect.lib import util as U
from sect.lib import materials as M
from sect.lib import arch as A
from sect.lib import props as P
from sect.lib import nature as N
from sect.lib import refs_east as RE

# --- landings (local frame). The grass next to the platform is -1.35 to -1.45, so both landings
# sit at -1.3 (not -1.5 / -1.8 as first planned, which would put their paving under the grass).
FRONT_Z = -1.3                   # bridgehead top = foot of the front steps
BRIDGE_Y0, BRIDGE_Y1 = -45.0, -37.0   # bridgehead slab, 12 m wide; its outer edge is the arrival
GATE_Y = -44.5                   # three-bay gate on the bridgehead
REAR_A = math.radians(107.0)     # rear stair: between two banner poles, behind the sword's left
REAR_Z = -1.3                    # rear landing + pier top
LAND_R = (36.0, 42.0)            # rear landing, radial extent along REAR_A (5 m wide)
LAND_W = 5.0
PIER_R1 = 44.0                   # pier end, ~1 m inside the island edge (44.9 m at 107 deg)
PIER_W = 3.0
PIER_SINK = 0.65                 # the pier's footing reaches this far under its foot (the landing's: arch.platform's 0.6);
                                 # round 12: their footings' flared bottoms overlapped 2 mm apart where they meet
WEST_A = math.radians(175.6)     # second band stair (west), so the grass ring forms a loop

AREA = dict(key="arena", section_id="hackathons", title_en="Sword-Discussion Arena",
            title_zh="论剑台", footprint=48.0,
            # connector landings (x, y, z, heading): heading in radians CCW from +X, local frame
            arrival=(0.0, BRIDGE_Y0, FRONT_Z, math.pi / 2),      # bridgehead outer edge, on the axis
            depart=(round(PIER_R1 * math.cos(REAR_A), 2), round(PIER_R1 * math.sin(REAR_A), 2),
                    REAR_Z, REAR_A))                              # rear pier end, heading out

K = "arena"

# --- layout (meters, local) -------------------------------------------------------------
R_FLOOR = 30.0          # dueling floor radius (60 m platform)
R_BAND = 34.0           # outer banner band
Z_BAND = -0.35          # banner band top (one step below the floor)
BAND_STEP_DROP = 0.02   # the stairs off the band: their top tread (inside the band's rim) this far under the band's top
                        # (round 12: 5 mm, and the two z-fought on the web beyond ~140 m)
BAND_STEP_DROP_OLD = 0.005
FRONT_STEPS_Y = -33.695  # the front steps' top edge (y): 0.5 cm inside the band's rim at their corners (x +-4.5), and
                         # their first riser (0.33 m down) 2.5 cm outside the rim wall at the axis. Round 12: at -33.65
                         # that riser met the curved rim wall at a grazing angle 0.5-1.4 m either side of the axis, the
                         # two 0-12 mm apart (z-fighting 16 m from the camera)
FRONT_STEPS_Y_OLD = -33.65
R_BANNER = 32.2         # banner pole circle
N_BANNERS = 40          # ~40 hackathons
GAP_FRONT = math.radians(13.0)   # half-angle of the open entrance at -Y

ROCK_SIZE = 98.0        # floating rock top diameter (radius ~49)
ROCK_DEPTH = 70.0
ROCK_Z = -2.2           # rock origin: its grassy top sits ~1-2 m under the platform

TIER_A = math.radians(48.0)      # spectator tier half-angle around +X
TIER_R0 = 34.8
TIER_STEP_R = 1.3
TIER_STEP_Z = 0.85
TIER_STEPS = 3
TIER_BACK = 47.0                 # max back radius; the tier is trimmed to 0.5 m inside the island rim
TIER_AISLES = (-31.0, 0.0, 31.0)  # aisle stairs (degrees), one in front of each pavilion
TIER_BOTTOM = -4.2               # buried in the rock top (no white box hanging over the edge)

SWORD_POS = (0.0, 40.0)          # where the guard sits in XY
SWORD_GUARD_Z = 24.0             # guard height above the floor (~38 m to the pommel)
SWORD_BLADE = 66.0               # blade length below the guard (tip pokes out under the island)

SEG = 192


# ======================================================================================
# small bmesh helpers
# ======================================================================================

def _face(bm, verts, want, mat=0, smooth=False):
    """Face with its normal pointing along `want` (Vector)."""
    f = bm.faces.new(verts)
    f.normal_update()
    if f.normal.dot(want) < 0:
        f.normal_flip()
    f.material_index = mat
    f.smooth = smooth
    return f


def _ring(bm, r, z, angles):
    return [bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for a in angles]


def _annulus(bm, r0, r1, z, mat, segs=SEG, step=2.5):
    """Flat ring top (concentric quads, no centre fan) facing +Z."""
    angles = [2 * math.pi * i / segs for i in range(segs)]
    n = max(1, int(math.ceil((r1 - r0) / step)))
    rings = [_ring(bm, r0 + (r1 - r0) * k / n, z, angles) for k in range(n + 1)]
    up = Vector((0, 0, 1))
    for k in range(n):
        a, b = rings[k], rings[k + 1]
        for i in range(segs):
            j = (i + 1) % segs
            _face(bm, (a[i], b[i], b[j], a[j]), up, mat)


def _wall(bm, r, z0, z1, mat, segs=SEG, inward=False):
    """Vertical cylinder wall from z0 to z1 facing out (or in)."""
    angles = [2 * math.pi * i / segs for i in range(segs)]
    lo = _ring(bm, r, z0, angles)
    hi = _ring(bm, r, z1, angles)
    for i in range(segs):
        j = (i + 1) % segs
        a = (angles[i] + angles[j]) * 0.5 if j else angles[i] + math.pi / segs
        d = Vector((math.cos(a), math.sin(a), 0))
        _face(bm, (lo[i], lo[j], hi[j], hi[i]), -d if inward else d, mat)


def _radial(a, r, t=0.0):
    """Point r m out along angle a, shifted t m sideways (CCW)."""
    c, s = math.cos(a), math.sin(a)
    return (r * c - t * s, r * s + t * c)


def _slab(name, coll, root, center, size, z_top, z_bottom, mat="marble_paving", rot=0.0):
    """Paved box (size x, y) centred on `center`, turned `rot` about Z."""
    bm = bmesh.new()
    U.bm_box(bm, size=(size[0], size[1], z_top - z_bottom), center=(0.0, 0.0, (z_top + z_bottom) * 0.5))
    return U.mesh_from_bmesh(name, bm, coll, materials=[mat], parent=root,
                             location=(center[0], center[1], 0.0), rotation=(0.0, 0.0, rot))


def _disc(bm, r, z, mat, segs=64, centre=(0.0, 0.0)):
    cx, cy = centre
    vs = [bm.verts.new((cx + r * math.cos(2 * math.pi * i / segs), cy + r * math.sin(2 * math.pi * i / segs), z))
          for i in range(segs)]
    f = _face(bm, vs, Vector((0, 0, 1)), mat)
    return f


# ======================================================================================
# platform
# ======================================================================================

def _build_platform(coll, root):
    """The dueling platform: concentric stone rings, a low central dais, a stepped rim."""
    mats = ["marble_paving", "stone_dark", "marble_white", "gold", "stone_grey"]
    PAV, DARK, WHITE, GOLD, GREY = range(5)
    bm = bmesh.new()
    z_dais = 0.3
    # central dais (taiji sits on top of it), two 0.15 m risers
    _annulus(bm, 7.4, 8.2, z_dais, GOLD, step=1.0)
    _wall(bm, 8.2, z_dais * 0.5, z_dais, WHITE)
    _annulus(bm, 8.2, 8.6, z_dais * 0.5, WHITE, step=1.0)
    _wall(bm, 8.6, 0.0, z_dais * 0.5, WHITE)
    # floor bands
    for r0, r1, m in ((8.6, 13.2, DARK), (13.2, 13.8, GOLD), (13.8, 26.4, PAV), (26.4, 27.8, DARK),
                      (27.8, R_FLOOR, PAV)):
        _annulus(bm, r0, r1, 0.0, m)
    # two 0.175 m risers down to the banner band, then a moulded rim
    _wall(bm, R_FLOOR, Z_BAND * 0.5, 0.0, WHITE)
    _annulus(bm, R_FLOOR, R_FLOOR + 0.4, Z_BAND * 0.5, WHITE, step=1.0)
    _wall(bm, R_FLOOR + 0.4, Z_BAND, Z_BAND * 0.5, WHITE)
    _annulus(bm, R_FLOOR + 0.4, R_BAND, Z_BAND, GREY)
    _wall(bm, R_BAND, -1.1, Z_BAND, WHITE)
    _annulus(bm, R_BAND, R_BAND + 0.6, -1.1, WHITE, step=1.0)
    _wall(bm, R_BAND + 0.6, -3.4, -1.1, WHITE)
    plat = U.mesh_from_bmesh(U.name(K, "platform"), bm, coll, materials=mats, parent=root)

    # taiji: dark disc + white "fish" + two eyes
    bm = bmesh.new()
    Rt = 7.4
    _disc(bm, Rt, z_dais, 0, segs=96)
    U.mesh_from_bmesh(U.name(K, "taiji_yin"), bm, coll, materials=["stone_dark"], parent=root)
    bm = bmesh.new()
    n = 40
    pts = []
    for i in range(n + 1):                          # outer right half, top -> bottom
        a = math.pi / 2 - math.pi * i / n
        pts.append((Rt * math.cos(a), Rt * math.sin(a)))
    for i in range(1, n + 1):                       # lower small circle, left side, up to centre
        a = -math.pi / 2 - math.pi * i / n
        pts.append((Rt / 2 * math.cos(a), -Rt / 2 + Rt / 2 * math.sin(a)))
    for i in range(1, n):                           # upper small circle, right side, up to top
        a = -math.pi / 2 + math.pi * i / n
        pts.append((Rt / 2 * math.cos(a), Rt / 2 + Rt / 2 * math.sin(a)))
    vs = [bm.verts.new((x, y, z_dais + 0.02)) for x, y in pts]
    f = _face(bm, vs, Vector((0, 0, 1)), 0)
    bmesh.ops.triangulate(bm, faces=[f])
    _disc(bm, Rt * 0.16, z_dais + 0.02, 0, segs=32, centre=(0.0, Rt / 2))     # white eye in the yin head
    yang = U.mesh_from_bmesh(U.name(K, "taiji_yang"), bm, coll, materials=["marble_white"], parent=root)
    bm = bmesh.new()
    _disc(bm, Rt * 0.16, z_dais + 0.04, 0, segs=32, centre=(0.0, -Rt / 2))    # dark eye in the yang head
    U.mesh_from_bmesh(U.name(K, "taiji_eye"), bm, coll, materials=["stone_dark"], parent=root)

    # glowing bagua ring and an outer script ring (concentric rune bands)
    bagua = P.rune_ring(coll, RE.SEAT_RING[0], RE.SEAT_RING[1], "trigram", material="rune_cyan", seed=3,
                        name=U.name(K, "bagua"), parent=root)
    P.rune_ring(coll, 27.1, 1.1, "script", material="rune_gold", seed=5,
                name=U.name(K, "script_ring"), parent=root)
    # round 34: the seats of the Five Greats 華山論劍 in the bagua ring at north, east, south and west (the taiji is the
    # Centre's), each bronze plate in the place of that point's trigram
    RE.clear_seat_trigrams(bagua)
    RE.build_seats(coll, root, K)
    return plat


# ======================================================================================
# spectator tier (+X side) with viewing pavilions
# ======================================================================================

def _rim_radius(rock, bins=90):
    """Walkable rim radius of the island top per angle (root frame), as a function of angle."""
    me = rock.data
    rz = rock.rotation_euler.z
    rmax = [0.0] * bins
    for v in me.vertices:
        if v.co.z > 0.05:                                    # the grassy top ring (rim - 0.6 m)
            a = (math.atan2(v.co.y, v.co.x) + rz) % (2 * math.pi)
            b = int(a / (2 * math.pi) * bins) % bins
            rmax[b] = max(rmax[b], math.hypot(v.co.x, v.co.y))
    fill = min([r for r in rmax if r > 0] or [ROCK_SIZE / 2 - 4])
    rmax = [r if r > 0 else fill for r in rmax]

    def at(a):
        b = int((a % (2 * math.pi)) / (2 * math.pi) * bins) % bins
        return min(rmax[(b + d) % bins] for d in (-1, 0, 1))  # conservative: min of neighbours
    return at


def _ground(rock):
    """(z_at(x, y), edge(a)) of the island's grassy top, root frame: grass height under a point
    (or `default` off the island) and the true radius where the grass ends at angle a."""
    m = rock.matrix_parent_inverse @ rock.matrix_basis
    me = rock.data
    bvh = BVHTree.FromPolygons([m @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])

    def z_at(x, y, default=None):
        hit = bvh.ray_cast(Vector((x, y, 10.0)), Vector((0.0, 0.0, -1.0)))
        return default if hit[0] is None else hit[0].z

    def edge(a):
        c, s = math.cos(a), math.sin(a)
        last, r = 30.0, 30.0
        while r < ROCK_SIZE * 0.56:
            z = z_at(r * c, r * s)
            if z is not None and z > ROCK_Z + 0.05:      # grassy top (its rim ring is at ROCK_Z + 0.12)
                last = r
            r += 0.2
        return last
    return z_at, edge


def _clear_plants(rock, regions):
    """Keep shrubs and grass tufts from poking through paving and steps: zero the rock's
    'nature_veg' scatter mask on faces inside any (angle, half_angle, r0, r1) region (root frame).
    Returns the number of faces cleared."""
    me = rock.data
    at = me.attributes.get("nature_veg")
    if at is None:
        return 0
    m = rock.matrix_parent_inverse @ rock.matrix_basis
    pol = [(math.atan2(p.y, p.x), math.hypot(p.x, p.y)) for p in (m @ v.co for v in me.vertices)]
    vals = [0.0] * len(me.polygons)
    at.data.foreach_get("value", vals)
    n = 0
    for i, poly in enumerate(me.polygons):
        if vals[i] <= 0.5:
            continue
        rs = [pol[k][1] for k in poly.vertices]
        for a, half, r0, r1 in regions:
            ds = [(pol[k][0] - a + math.pi) % (2 * math.pi) - math.pi for k in poly.vertices]
            if (max(ds) - min(ds) < math.pi and min(ds) <= half and max(ds) >= -half
                    and min(rs) <= r1 and max(rs) >= r0):
                vals[i] = 0.0
                n += 1
                break
    at.data.foreach_set("value", vals)
    me.update()
    return n


PLATFORM_CLEAR_R = 33.5     # round 34: no plants on the island's top within this radius (all under the platform);
                            # some grew taller than the 1.3 m to its floor and their tips showed through the duelling
                            # floor, and in the seats of the Five Greats (lib/refs_east.py)


def clear_plants_under_platform(rock, r1=PLATFORM_CLEAR_R):
    """Zero the rock's 'nature_veg' scatter mask on every face wholly within ``r1`` of the arena's centre (root
    frame): nothing grows under the stone platform. Works on the built object (sect/patch_r34_east.py clears a built
    file's). Returns the number of faces cleared (0 when already clear)."""
    me = rock.data
    at = me.attributes.get("nature_veg")
    if at is None:
        return 0
    m = rock.matrix_parent_inverse @ rock.matrix_basis
    rr = [math.hypot(p.x, p.y) for p in (m @ v.co for v in me.vertices)]
    vals = [0.0] * len(me.polygons)
    at.data.foreach_get("value", vals)
    n = 0
    for i, poly in enumerate(me.polygons):
        if vals[i] > 0.5 and max(rr[k] for k in poly.vertices) <= r1:
            vals[i] = 0.0
            n += 1
    if n:
        at.data.foreach_set("value", vals)
        me.update()
    return n


def _rim_rail(coll, root, z_at, edge, a0, length=20.0, inset=1.0, height=0.9):
    """Low balustrade on the grass `inset` m inside the island edge, from angle a0 for `length` m
    (positive: counter-clockwise)."""
    da = length / 45.0
    n = max(2, int(math.ceil(abs(da) * 45.0 / 2.0)))
    pts = []
    for i in range(n + 1):
        a = a0 + da * i / n
        x, y = _radial(a, edge(a) - inset)
        pts.append((x, y, z_at(x, y, ROCK_Z)))
    return A.balustrade(U.name(K, "rim_rail"), coll, pts, height=height, end_drum="both", parent=root)


STEP_SINK = 0.12        # the band stairs' blocks reach this far under their foot (round 12 verify: the island's grass
                        # falls away under the front and rear flights near their foot, so their bottoms stood up to
                        # 8 and 10 cm over it, a dark slit along their sides seen from 16 m)


def sink_steps(st, depth):
    """Let an arch.stairs flight's block (its '.steps' mesh: the treads and stringers) reach ``depth`` below its foot:
    its bottom vertices (and the bevel ring just above them) move down. Works on the built object, so a fresh build
    and sect/patch_r12_areas.py agree. Returns the number of vertices moved (0 when already sunk)."""
    me = bpy.data.objects[st.name + ".steps"].data
    if min(v.co.z for v in me.vertices) < -1e-4:
        return 0
    n = 0
    for v in me.vertices:
        if v.co.z < 0.05:
            v.co.z -= depth
            n += 1
    me.update()
    return n


def _band_stair(coll, root, a, z_foot, part):
    """2.5 m stair from the banner band straight out and down to z_foot at angle a (its block sunk STEP_SINK)."""
    r_top = R_BAND - 0.15                       # top edge just inside the band's rim
    x, y = _radial(a, r_top)
    st = A.stairs(U.name(K, part), coll, 2.5, Z_BAND - z_foot - BAND_STEP_DROP, run_per_step=0.3, ramp=False,
                  balustrade=False, parent=root, location=(x, y, z_foot), rotation_z=a + math.pi / 2)
    sink_steps(st, STEP_SINK)
    return st


def _build_tier(coll, root, rim):
    segs = 48
    angles = [-TIER_A + 2 * TIER_A * i / segs for i in range(segs + 1)]
    radii = [TIER_R0 + TIER_STEP_R * k for k in range(TIER_STEPS + 1)]       # step fronts
    tops = [Z_BAND + TIER_STEP_Z * (k + 1) for k in range(TIER_STEPS + 1)]  # step tops
    backs = [min(TIER_BACK, rim(a) - 0.5) for a in angles]                  # never past the rim
    bm = bmesh.new()
    PAV, WHITE = 0, 1

    def ring(r, z):
        rs = r if isinstance(r, list) else [r] * len(angles)
        return [bm.verts.new((rr * math.cos(a), rr * math.sin(a), z)) for rr, a in zip(rs, angles)]

    up = Vector((0, 0, 1))
    for k in range(TIER_STEPS + 1):
        r0 = radii[k]
        r1 = radii[k + 1] if k < TIER_STEPS else backs
        z = tops[k]
        zb = tops[k - 1] if k else TIER_BOTTOM
        a_, b_ = ring(r0, z), ring(r1, z)
        lo = ring(r0, zb)
        for i in range(segs):
            am = (angles[i] + angles[i + 1]) / 2
            d = Vector((math.cos(am), math.sin(am), 0))
            _face(bm, (a_[i], b_[i], b_[i + 1], a_[i + 1]), up, PAV)          # tread
            _face(bm, (lo[i], lo[i + 1], a_[i + 1], a_[i]), -d, WHITE)        # riser faces the arena
    # back wall (low marble parapet above the rock rim)
    lo, hi = ring(backs, TIER_BOTTOM), ring(backs, tops[-1])
    for i in range(segs):
        am = (angles[i] + angles[i + 1]) / 2
        _face(bm, (lo[i], lo[i + 1], hi[i + 1], hi[i]), Vector((math.cos(am), math.sin(am), 0)), WHITE)
    # end caps: one stair-profile polygon each
    for (a, sgn), rb in (((angles[0], -1), backs[0]), ((angles[-1], 1), backs[-1])):
        prof = [(radii[0], TIER_BOTTOM)]
        for k in range(TIER_STEPS + 1):
            prof.append((radii[k], tops[k]))
            prof.append((radii[k + 1] if k < TIER_STEPS else rb, tops[k]))
        prof.append((rb, TIER_BOTTOM))
        vs = [bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for r, z in prof]
        n = Vector((-math.sin(a), math.cos(a), 0)) * sgn
        f = _face(bm, vs, n, WHITE)
        bmesh.ops.triangulate(bm, faces=[f])
    tier = U.mesh_from_bmesh(U.name(K, "tier"), bm, coll, materials=["marble_paving", "marble_white"],
                             parent=root)
    z_top = tops[-1]

    def r_pav(a):
        back = min(TIER_BACK, rim(a) - 0.5)
        return (radii[-1] + back) / 2 + 0.4

    # main judges' pavilion (double eave, teal) facing the arena (-X), side pavilions.
    # The judges' platform + steps fit the top tread (7.7 m deep at 0 deg). The viewing pavilions
    # stand straight on the top tread: at +31 deg the tread is only 5.6 m deep, too shallow for a
    # 6 m platform plus its steps, which would hang over the aisle stair.
    jr = 2.8
    main = A.pavilion(U.name(K, "judges"), coll, sides=4, radius=jr, height=4.2, roof="pyramid",
                      double=True, roof_mat="roof_tile_teal", platform_h=0.5, seats=False,
                      parent=root, location=(r_pav(0.0), 0.0, z_top), rotation_z=-math.pi / 2)
    for sgn in (-1, 1):
        a = sgn * math.radians(TIER_AISLES[-1])
        A.pavilion(U.name(K, "viewing"), coll, sides=6, radius=2.4, height=3.4, roof="pyramid",
                   roof_mat="roof_tile_black", platform_h=0.0,
                   parent=root, location=(r_pav(a) * math.cos(a), r_pav(a) * math.sin(a), z_top),
                   rotation_z=a - math.pi / 2)
    # plaque under the judges' pavilion front eave (pavilion local: front = -Y)
    P.plaque(coll, AREA["title_zh"], 3.2, name=U.name(K, "plaque"), parent=main,
             location=(0.0, -(jr * math.cos(math.pi / 4) + 0.42), 0.5 + 4.2 - 0.55))
    # aisle stairs from the banner band up the tier, centred on each pavilion (0.17 m risers)
    for deg in TIER_AISLES:
        a = math.radians(deg)
        A.stairs(U.name(K, "tier_aisle"), coll, 2.0, z_top - Z_BAND, run_per_step=0.26, ramp=False,
                 balustrade=True, stringer=0.3, parent=root,
                 location=(radii[-1] * math.cos(a), radii[-1] * math.sin(a), Z_BAND), rotation_z=a - math.pi / 2)
    print("ARENA tier top r %.1f, pavilion r: judges %.2f, viewing %.2f / %.2f, top tread depth %.1f-%.1f m"
          % (radii[-1], r_pav(0.0), r_pav(math.radians(-31)), r_pav(math.radians(31)),
             min(backs) - radii[-1], max(backs) - radii[-1]))
    return tier


# ======================================================================================
# the Heavy Iron Sword 玄铁重剑 (the giant sword, recast)
# ======================================================================================
# Return of the Condor Heroes ch. 26: the sword Yang Guo finds in Dugu Qiubai's Sword Tomb is dull black (黑黝黝),
# blunt on both edges (钝口), its tip round like a half-sphere (圆圆的似是个半球), with a faint red light deep in the
# black. Its iron was later recast into the Dragon Saber at the gate (true in every edition), so the flight shows the
# saber's ancestor. Plain on purpose (毫无异状): a black iron blade with fully rounded blunt edges (flagged 'edge', so
# they bake lighter and outline the slab) and hand-forged facets, hairline ember seams (molten) inside the black, a
# plain iron block guard, a black cord-wrapped grip between iron ferrules, a disc pommel with a ring, a short hemp
# cord. No inscription plaque.
# In place of the old stone jian: the Empty 'arena.sword' and the six object names stay, and every part's local box
# sits inside the old part's (HS_OLD_BOX), so export_web's caches (keyed on names, boxed by bound boxes) stay valid.
# The geometry is plain Python lists (_SGeo, no bpy) so it can be checked without Blender; heavy_sword_meshes() turns
# it into meshes for both a full build (_build_sword) and sect/patch_heavy_iron_sword.py (out/sect_chase.blend).
# Sword-local frame: origin at the guard, blade down -Z, width along X, front (the arriving camera) -Y.

HS_PARTS = ("sword_blade", "sword_glow", "sword_guard", "sword_grip", "sword_pommel", "sword_tassel")
HS_MATERIALS = dict(sword_blade=["iron"], sword_glow=["molten"], sword_guard=["iron"],
                    sword_grip=["iron", "cloth_black"], sword_pommel=["iron"], sword_tassel=["props_rope"])
HS_SMOOTH = dict(sword_blade=35.0, sword_glow=30.0, sword_guard=30.0, sword_grip=40.0, sword_pommel=40.0,
                 sword_tassel=60.0)          # degrees: edges sharper than this stay hard (marked lines always)
HS_OLD_BOX = dict(                           # the stone jian's local boxes (min, max): every new part stays inside
    sword_blade=((-3.2, -0.9, -66.0), (3.2, 0.9, -0.2)),
    sword_glow=((-0.22, -0.93, -47.52), (0.22, 0.93, -2.5)),
    sword_guard=((-8.51, -1.5, -1.43), (8.51, 1.5, 3.41)),
    sword_grip=((-1.25, -1.25, 2.9), (1.25, 1.25, 11.0)),
    sword_pommel=((-2.0, -2.0, 10.9), (2.0, 2.0, 14.1)),
    sword_tassel=((-0.2967, -2.6641, -3.0123), (3.7034, -0.0912, 13.2331)),   # measured in out/sect_chase.blend
)
HS_TRI_CAP = 8000              # per part: bake_web keeps pieces this small whole (no LOD collapse of the shapes)
HS_SEED = 26                   # chapter 26
# blade: a blunt lens slab, 3 facet bands per broad face, half-round edges, a half-dome tip
HS_TOP, HS_SHOULDER, HS_TIP = -0.2, -63.2, -66.0   # blade top (in the guard), tip semicircle start, the nub
HS_W = (6.4, 5.6)              # width at the top / at the shoulder (linear)
HS_T = (1.8, 1.5)              # spine thickness
HS_RE = 0.25                   # edge half-round radius (the edges are 0.5 m thick)
HS_EDGE_BAND = 0.35            # faces with |x| > W/2 - this are flagged 'edge' (the light rims)
HS_MID = 0.34                  # middle facet band half width / blade half width (three bands of about equal width)
HS_RINGS = 48                  # body ring intervals (top to shoulder)
HS_TIP_RINGS = 7               # dome rings between the shoulder and the pole
HS_ARC = 8                     # points on each edge's half-round
HS_HAMMER = 0.035              # hammer facets: per ring each facet line sinks by up to this x the band width
HS_WOBBLE = 0.03               # m: per ring the edges sit up to this much inside the straight taper (forged, uneven)
HS_JITTER = 0.06               # m: the facet lines wander sideways by up to this
# ember seams (molten): broken hairlines near the centre line of both faces
HS_GLOW = 0.45                 # obj['glow']: faint, a red glint deep in the black rather than a lit stripe
HS_SEAM_Z = (-3.0, -47.5)
HS_SEAMS = (4, 6)              # per face (back, front: the arriving camera's side)
HS_SEAM_BIAS = 1.35            # slot spacing grows downward: more seams on the blade above the island (z > -25)
HS_SEAM_LEN = (1.5, 4.0)
HS_SEAM_W = (0.10, 0.16)
HS_SEAM_SWAY = 0.15            # m either side of x = 0
HS_SEAM_HALF = 0.22            # m: |x| of every seam point stays inside this (the old fuller strip's box)
HS_SEAM_PROUD, HS_SEAM_SINK = 0.015, 0.01
HS_SEAM_STEP = 0.4
# guard: plain iron block, straight top, shallow V underside
HS_GUARD_X = 5.2               # half width
HS_GUARD_Z = (-0.7, 0.05, 3.2)  # underside at the centre, underside at the ends, top
HS_GUARD_D = (1.3, 0.8)        # half depth at the centre / at the ends
HS_GUARD_C = 0.2               # chamfer
# grip: cord wrap (cloth_black) between plain iron ferrules
HS_GRIP_Z = (2.9, 3.4, 10.4, 10.95)   # foot, wrap start, wrap end, top
HS_GRIP_R = (1.2, 1.0, 1.12)   # ferrule, the wrap's sunken diamonds, its cord crossings
HS_GRIP_ROWS = 21              # wrap rows: a diamond is 2 rows tall (0.67 m) and 2 columns wide (0.56 m)
HS_GRIP_SEGS = 24              # even (the checkerboard closes round the grip)
# pommel: flattened disc (axis -Y, facing the camera) on an oval neck, a ring loop on top
HS_POMMEL_R, HS_POMMEL_TOP = 1.15, 13.4
HS_POMMEL_DISC = ((0.0, 0.42), (0.7, 0.41), (0.9, 0.39), (1.02, 0.33), (1.11, 0.22), (1.15, 0.08))   # (rho, half y)
HS_RING = (13.48, 0.45, 0.12)  # torus centre z, R, r: its top at 14.05
# cord: short hemp cord from the pommel's face, a knot, three frayed tails
HS_CORD = ((0.0, -0.32, 13.1), (0.9, -1.15, 10.5), (1.3, -1.5, 7.5), (1.5, -1.6, 5.5))
HS_CORD_R = 0.16
HS_TAILS = (((1.42, -1.55, 5.15), (1.37, -1.52, 4.7), (1.33, -1.5, 4.2)),
            ((1.55, -1.68, 5.15), (1.6, -1.76, 4.68), (1.63, -1.8, 4.25)),
            ((1.6, -1.5, 5.15), (1.7, -1.46, 4.72), (1.77, -1.42, 4.3)))


def _hs_val(x, *a):
    return x(*a) if callable(x) else x


class _SGeo:
    """Mesh as plain Python lists: verts, faces (vertex index tuples) with a material slot, the 'edge' value (iron bakes
    lighter there) and a smooth flag, explicit hard edges, and parts. Every part is a closed solid; end() turns its
    faces outward by the sign of its volume."""

    def __init__(self):
        self.verts, self.faces, self.mat, self.edge, self.smooth = [], [], [], [], []
        self.sharp = set()
        self.parts = []                 # (name, first face, end face)
        self._cur = None

    def v(self, p):
        self.verts.append((float(p[0]), float(p[1]), float(p[2])))
        return len(self.verts) - 1

    def face(self, idx, mat=0, edge=0.0, smooth=True):
        self.faces.append(tuple(idx))
        self.mat.append(int(mat))
        self.edge.append(float(edge))
        self.smooth.append(bool(smooth))

    def hard(self, a, b):
        self.sharp.add((a, b) if a < b else (b, a))

    def begin(self, name):
        self._cur = (name, len(self.faces))

    def end(self):
        name, f0 = self._cur
        f1 = len(self.faces)
        if self.volume(f0, f1) < 0.0:
            for i in range(f0, f1):
                self.faces[i] = tuple(reversed(self.faces[i]))
        self.parts.append((name, f0, f1))
        self._cur = None

    def volume(self, f0=0, f1=None):
        V = self.verts
        vol = 0.0
        for f in self.faces[f0:f1]:
            a = V[f[0]]
            for k in range(1, len(f) - 1):
                b, c = V[f[k]], V[f[k + 1]]
                vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) + a[1] * (b[2] * c[0] - b[0] * c[2])
                        + a[2] * (b[0] * c[1] - b[1] * c[0]))
        return vol / 6.0

    def tris(self):
        return sum(len(f) - 2 for f in self.faces)

    def box(self):
        return (tuple(min(p[k] for p in self.verts) for k in range(3)),
                tuple(max(p[k] for p in self.verts) for k in range(3)))

    def rings(self, name, rings, mat=0, edge=0.0, smooth=True, caps=(True, True), cap_edge=0.0, cap_smooth=None,
              hard_cols=(), loop=False, split=None):
        """Closed solid from rings of equal length (a ring of one point is a pole: a fan). mat / edge / smooth: value
        or f(row, col); row r joins ring r and r + 1, col c joins point c and c + 1. Open end rings get n-gon caps;
        loop=True joins the last ring back to the first (a torus, no caps). hard_cols: lengthwise lines kept hard.
        split: f(row, col) -> None (a quad), 0 (two triangles split along a[c]-b[c+1]) or 1 (along a[c+1]-b[c])."""
        self.begin(name)
        ids = [[self.v(p) for p in ring] for ring in rings]
        n = max(len(r) for r in ids)
        m = len(ids)
        for r in range(m if loop else m - 1):
            a, b = ids[r], ids[(r + 1) % m]
            for c in range(n):
                c2 = (c + 1) % n
                if len(a) == 1 and len(b) == 1:
                    continue
                if len(a) == 1:
                    q = (a[0], b[c2], b[c])
                elif len(b) == 1:
                    q = (a[c], a[c2], b[0])
                else:
                    q = (a[c], a[c2], b[c2], b[c])
                fa = (_hs_val(mat, r, c), _hs_val(edge, r, c), _hs_val(smooth, r, c))
                sp = split(r, c) if (split is not None and len(q) == 4) else None
                if sp == 0:
                    self.face((a[c], a[c2], b[c2]), *fa)
                    self.face((a[c], b[c2], b[c]), *fa)
                elif sp == 1:
                    self.face((a[c], a[c2], b[c]), *fa)
                    self.face((a[c2], b[c2], b[c]), *fa)
                else:
                    self.face(q, *fa)
            if len(a) > 1 and len(b) > 1:
                for c in hard_cols:
                    self.hard(a[c], b[c])
        if not loop:
            cs = smooth if cap_smooth is None else cap_smooth
            if caps[0] and len(ids[0]) > 1:
                self.face(tuple(reversed(ids[0])), _hs_val(mat, 0, 0), cap_edge, _hs_val(cs, 0, 0))
            if caps[1] and len(ids[-1]) > 1:
                self.face(tuple(ids[-1]), _hs_val(mat, m - 2, 0), cap_edge, _hs_val(cs, m - 2, 0))
        self.end()
        return ids

    def lathe(self, name, rows, segs, xf=None, mat=0, edge=0.0, smooth=True, phase=0.0, centre=(0.0, 0.0)):
        """Revolve rows (r, z[, sy[, tilt]]) around a vertical axis through ``centre``; r = 0 makes a pole. sy squashes
        a ring along y, tilt leans its plane (z += tilt * x: a wrap's turns). mat / edge / smooth: value or f(row).
        xf maps every point (another axis)."""
        rings = []
        for row in rows:
            r, z = row[0], row[1]
            sy = row[2] if len(row) > 2 else 1.0
            tilt = row[3] if len(row) > 3 else 0.0
            if r <= 1e-7:
                pts = [(centre[0], centre[1], z)]
            else:
                pts = []
                for k in range(segs):
                    a = phase + 2.0 * math.pi * k / segs
                    x, y = r * math.cos(a), r * sy * math.sin(a)
                    pts.append((centre[0] + x, centre[1] + y, z + tilt * x))
            rings.append([xf(p) if xf else p for p in pts])
        return self.rings(name, rings, mat=lambda r, c: _hs_val(mat, r), edge=lambda r, c: _hs_val(edge, r),
                          smooth=lambda r, c: _hs_val(smooth, r))

    def tube(self, name, pts, radii, sides, edge=0.0, star=None):
        """Tube through points (parallel-transport frames), both ends capped. star: (out, in) radius factors of the
        last ring's alternate points (a frayed end)."""
        n = len(pts)
        tans = []
        for i in range(n):
            a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
            tans.append(_hs_norm(_hs_sub(b, a)))
        ref = (0.0, 0.0, 1.0) if abs(tans[0][2]) < 0.9 else (1.0, 0.0, 0.0)
        u = _hs_norm(_hs_cross(tans[0], ref))
        rings = []
        for i in range(n):
            t = tans[i]
            d = sum(u[k] * t[k] for k in range(3))
            u = _hs_norm(tuple(u[k] - t[k] * d for k in range(3)))
            w = _hs_cross(t, u)
            ring = []
            for k in range(sides):
                a = 2.0 * math.pi * k / sides
                r = radii[i]
                if star and i == n - 1:
                    r *= star[0] if k % 2 == 0 else star[1]
                ca, sa = math.cos(a) * r, math.sin(a) * r
                ring.append(tuple(pts[i][j] + u[j] * ca + w[j] * sa for j in range(3)))
            rings.append(ring)
        return self.rings(name, rings, edge=edge)

    def sphere(self, name, c, r, nu=8, nv=5, scale=(1.0, 1.0, 1.0), edge=0.0):
        rows = [(0.0, -1.0)] + [(math.sin(math.pi * k / nv), -math.cos(math.pi * k / nv)) for k in range(1, nv)] + \
            [(0.0, 1.0)]

        def xf(p):
            return (c[0] + p[0] * r * scale[0], c[1] + p[1] * r * scale[1], c[2] + p[2] * r * scale[2])
        return self.lathe(name, rows, nu, xf=xf, edge=edge)

    def torus(self, name, c, R, r, nu=14, nv=6, edge=0.0):
        """Ring in the XZ plane (hole along y) around c, with a vertex at its very top (c.z + R + r)."""
        rings = []
        for i in range(nu):
            a = math.pi / 2 + 2.0 * math.pi * i / nu
            d = (math.cos(a), math.sin(a))
            ring = []
            for j in range(nv):
                b = 2.0 * math.pi * j / nv
                k = R + r * math.cos(b)
                ring.append((c[0] + d[0] * k, c[1] + r * math.sin(b), c[2] + d[1] * k))
            rings.append(ring)
        return self.rings(name, rings, edge=edge, loop=True)


def _hs_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _hs_cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _hs_norm(a):
    n = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else (0.0, 0.0, 0.0)


def _hs_crom(pts, n):
    """Catmull-Rom through pts, n samples per segment (ends included once)."""
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for s in range(n):
            t = s / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3)
                             for a, b, c, d in zip(p0, p1, p2, p3)))
    out.append(tuple(pts[-1]))
    return out


# ---- blade --------------------------------------------------------------------------------------

HS_COLS = 2 * HS_ARC + 8       # ring points: right half-round, back face (4), left half-round, front face (4)
_A = HS_ARC
HS_EDGE_COLS = frozenset(list(range(0, _A)) + [_A + 3] + list(range(_A + 4, 2 * _A + 4)) + [2 * _A + 7])
HS_FLAT_COLS = frozenset((_A, _A + 1, _A + 2, 2 * _A + 4, 2 * _A + 5, 2 * _A + 6))   # the facet bands
HS_HARD_COLS = (_A, _A + 1, _A + 2, _A + 3, 2 * _A + 4, 2 * _A + 5, 2 * _A + 6, 2 * _A + 7)   # facet lines
HS_MID_COLS = ((_A + 1, _A + 2), (2 * _A + 6, 2 * _A + 5))   # (right, left) middle band points: back, front


def _hs_dims(z):
    """(half width, spine half thickness) of the blade body at z."""
    t = (z - HS_TOP) / (HS_SHOULDER - HS_TOP)
    return 0.5 * (HS_W[0] + (HS_W[1] - HS_W[0]) * t), 0.5 * (HS_T[0] + (HS_T[1] - HS_T[0]) * t)


def _hs_junction(x1, y1, c, re):
    """Angle (about the half-round's centre (c, 0), from +x) where the side facet from (x1, y1) meets the round
    tangentially."""
    vx, vy = x1 - c, y1
    return math.atan2(vy, vx) - math.acos(min(1.0, re / math.hypot(vx, vy)))


def _hs_section(a, b, d=None):
    """One blade ring: HS_COLS points (x, y), counter-clockwise from the right half-round's front junction. Each broad
    face is three flat facet bands (middle at +-b, side bands sloping to the round's tangent point), each edge a
    half-round of HS_RE. d: hammer marks {'mid': (back, front), 'band': ((back r, back l), (front r, front l)),
    'x1': (same)}: the middle band's and the band points' inward dents (<= 0) and the facet lines' x shifts."""
    re = HS_RE
    c = a - re
    xb = a - HS_EDGE_BAND
    side = {}
    for fi in (0, 1):                               # 0: back face (+y), 1: front face (-y), toward the camera
        ym = b + (d["mid"][fi] if d else 0.0)
        for si in (0, 1):                           # 0: right (+x), 1: left
            x1 = HS_MID * a + (d["x1"][fi][si] if d else 0.0)
            th = _hs_junction(x1, ym, c, re)
            xj, yj = c + re * math.cos(th), re * math.sin(th)
            yb = ym + (yj - ym) * (xb - x1) / (xj - x1) + (d["band"][fi][si] if d else 0.0)
            side[fi, si] = (x1, ym, yb, th)
    pts = []
    t0, t1 = side[1, 0][3], side[0, 0][3]           # right round: front junction up to the back junction
    for k in range(HS_ARC):
        ang = -t0 + (t0 + t1) * k / (HS_ARC - 1)
        pts.append((c + re * math.cos(ang), re * math.sin(ang)))
    x1r, ymr, ybr, _ = side[0, 0]
    x1l, yml, ybl, _ = side[0, 1]
    pts += [(xb, ybr), (x1r, ymr), (-x1l, yml), (-xb, ybl)]
    t0, t1 = side[0, 1][3], side[1, 1][3]           # left round: back junction down to the front junction
    for k in range(HS_ARC):
        ang = math.pi - t0 + (t0 + t1) * k / (HS_ARC - 1)
        pts.append((-c + re * math.cos(ang), re * math.sin(ang)))
    x1r, ymr, ybr, _ = side[1, 0]
    x1l, yml, ybl, _ = side[1, 1]
    pts += [(-xb, -ybl), (-x1l, -yml), (x1r, -ymr), (xb, -ybr)]
    return pts


def _hs_blade(g, rng):
    """The blade; returns (zs, mids): the body rings' z and the middle bands' surface |y| (back, front) per ring."""
    n = HS_RINGS
    step = (HS_SHOULDER - HS_TOP) / n
    zs, mids, rings = [], [], []
    for k in range(n + 1):
        z = HS_TOP + step * k
        d = None
        if 0 < k < n:                               # the top (in the guard) and the shoulder rings stay clean
            z += rng.uniform(-0.2, 0.2) * step
            a, _ = _hs_dims(z)
            dent = HS_HAMMER * 2.0 * HS_MID * a

            def dn():
                return -rng.uniform(0.0, dent)

            def jx():
                return rng.uniform(-HS_JITTER, HS_JITTER)
            d = dict(mid=(dn(), dn()), band=((dn(), dn()), (dn(), dn())), x1=((jx(), jx()), (jx(), jx())),
                     wobble=rng.uniform(0.0, HS_WOBBLE))
        a, b = _hs_dims(z)
        sec = _hs_section(a - (d["wobble"] if d else 0.0), b, d)
        zs.append(z)
        mids.append((sec[HS_MID_COLS[0][0]][1], -sec[HS_MID_COLS[1][0]][1]))
        rings.append([(x, y, z) for x, y in sec])
    R = HS_W[1] * 0.5
    if abs(HS_SHOULDER - R - HS_TIP) > 1e-6:
        raise ValueError("the tip's semicircle (r %.3f) must end at HS_TIP" % R)
    base = rings[-1]
    for i in range(1, HS_TIP_RINGS + 1):            # half dome: the shoulder ring scaled on the planform's semicircle
        phi = 0.5 * math.pi * i / (HS_TIP_RINGS + 1)
        s, z = math.cos(phi), HS_SHOULDER - R * math.sin(phi)
        rings.append([(x * s, y * s, z) for x, y, _ in base])
    rings.append([(0.0, 0.0, HS_TIP)])

    def edge(r, c):
        return 1.0 if c in HS_EDGE_COLS else 0.0

    def smooth(r, c):
        return r >= n or c not in HS_FLAT_COLS      # facets flat on the body, the dome and the rounds smooth
    g.rings("blade", rings, edge=edge, smooth=smooth, caps=(True, False), cap_smooth=False, hard_cols=HS_HARD_COLS)
    return zs, mids


def _hs_seams(g, zs, mids, rng):
    """Ember hairlines on both faces: HS_SEAMS broken, meandering crack-like strips per face (closed triangular
    prisms: a flat top HS_SEAM_PROUD above the middle band, the keel HS_SEAM_SINK into it; stations at every body ring
    they cross, so they follow the hammered face)."""
    def face_h(z, fi):
        for k in range(len(zs) - 1):
            if zs[k + 1] - 1e-9 <= z <= zs[k] + 1e-9:
                t = (zs[k] - z) / (zs[k] - zs[k + 1])
                return mids[k][fi] + (mids[k + 1][fi] - mids[k][fi]) * t
        raise ValueError("seam z %.3f outside the blade body" % z)
    z0, z1 = HS_SEAM_Z
    for fi, fy in ((0, 1.0), (1, -1.0)):
        ns = HS_SEAMS[fi]
        cuts = [z0 - (z0 - z1) * (j / ns) ** HS_SEAM_BIAS for j in range(ns + 1)]
        for j in range(ns):
            slot = cuts[j] - cuts[j + 1]
            L = min(rng.uniform(*HS_SEAM_LEN), slot - 0.5)
            top = cuts[j] - rng.uniform(0.0, slot - L)
            bot = top - L
            w = rng.uniform(*HS_SEAM_W)
            ph, ph2, x0 = rng.uniform(0.0, 2.0 * math.pi), rng.uniform(0.0, 2.0 * math.pi), rng.uniform(-0.05, 0.05)
            m = max(3, int(math.ceil(L / HS_SEAM_STEP)))
            ring_z = [z for z in zs if bot + 0.08 < z < top - 0.08]
            st = [top, bot] + [z for z in (top - L * i / m for i in range(1, m))
                               if all(abs(z - q) > 0.08 for q in ring_z)]
            rings = []
            for z in sorted(set(st + ring_z), reverse=True):
                t = min(1.0, max(0.0, (top - z) / L))
                hw = 0.5 * w * (0.35 + 0.65 * max(0.0, math.sin(math.pi * t)) ** 0.6)
                x = x0 + 0.075 * math.sin(2.2 * z + ph) + 0.045 * math.sin(5.7 * z + ph2)
                lim = min(HS_SEAM_SWAY, HS_SEAM_HALF - hw - 0.003)
                x = max(-lim, min(lim, x))
                h = face_h(z, fi)
                yt, yb = fy * (h + HS_SEAM_PROUD), fy * (h - HS_SEAM_SINK)
                rings.append([(x - hw, yt, z), (x + hw, yt, z), (x, yb, z)])
            g.rings("seam", rings, smooth=False)


# ---- hilt ---------------------------------------------------------------------------------------

def _hs_guard(g):
    """Plain block guard: straight top, shallow V underside (its lowest line covers the blade top at every x), depth
    tapering to the ends, 0.2 m chamfers on every edge (flagged 'edge')."""
    hx, c = HS_GUARD_X, HS_GUARD_C
    apex, zend, top = HS_GUARD_Z

    def zb(x):
        return apex + (zend - apex) * abs(x) / hx

    def hd(x):
        return HS_GUARD_D[0] + (HS_GUARD_D[1] - HS_GUARD_D[0]) * abs(x) / hx

    def sec(x, h, b, t, ch):
        return [(x, -h, b + ch), (x, -h + ch, b), (x, h - ch, b), (x, h, b + ch), (x, h, t - ch), (x, h - ch, t),
                (x, -h + ch, t), (x, -h, t - ch)]
    rings = [sec(-hx, hd(hx) - c, zb(hx) + c, top - c, 0.5 * c)]
    rings += [sec(x, hd(x), zb(x), top, c) for x in (-(hx - c), 0.0, hx - c)]
    rings.append(sec(hx, hd(hx) - c, zb(hx) + c, top - c, 0.5 * c))
    last = len(rings) - 2

    def edge(r, col):
        return 1.0 if (r in (0, last) or col % 2 == 0) else 0.0
    g.rings("guard", rings, edge=edge, smooth=False)


def _hs_grip(g):
    """Lathe: plain iron ferrules at both ends and between them a black diamond cord wrap (菱形缠绳): a checkerboard of
    raised cord crossings (HS_GRIP_R[2]) and sunken diamonds (HS_GRIP_R[1]), every quad split along its raised
    diagonal, so the cords run round the grip as two sets of crossing ridges."""
    z0, w0, w1, z1 = HS_GRIP_Z
    rf, rg, rc = HS_GRIP_R
    n, segs = HS_GRIP_ROWS, HS_GRIP_SEGS

    def ring(r, z, row=None):
        if r <= 1e-7:
            return [(0.0, 0.0, z)]
        out = []
        for k in range(segs):
            rr = rc if (row is not None and 0 < row < n and (row + k) % 2 == 0) else r
            a = 2.0 * math.pi * k / segs
            out.append((rr * math.cos(a), rr * math.sin(a), z))
        return out
    rings = [ring(0.0, z0), ring(rf, z0), ring(rf, w0 - 0.07), ring(rf - 0.06, w0)]
    i0 = len(rings)
    rings += [ring(rg, w0 + (w1 - w0) * j / n, j) for j in range(n + 1)]
    i1 = len(rings) - 1
    rings += [ring(rf - 0.06, w1), ring(rf, w1 + 0.07), ring(rf, z1), ring(0.0, z1)]
    chamfers = (2, i1 + 1)

    def split(r, c):
        if i0 <= r < i1:
            return 0 if (r - i0 + c) % 2 == 0 else 1
        return None
    g.rings("grip", rings, mat=lambda r, c: 1 if i0 <= r < i1 else 0,
            edge=lambda r, c: 1.0 if r in chamfers else 0.0, split=split)


def _hs_pommel(g):
    """Flattened iron disc facing the camera on an oval neck, a small ring loop on top; the disc's rim is flagged
    'edge' (a light outline)."""
    zc = HS_POMMEL_TOP - HS_POMMEL_R
    g.lathe("pommel_neck", [(0.0, HS_GRIP_Z[3] - 0.05), (0.95, HS_GRIP_Z[3] - 0.05, 1.0), (0.86, 11.06, 0.82),
                            (0.72, 11.26, 0.64), (0.6, 11.48, 0.54), (0.0, 11.48)], 16)
    prof = [(r, -y) for r, y in HS_POMMEL_DISC] + [(r, y) for r, y in reversed(HS_POMMEL_DISC)]
    rim = 0.89

    def xf(p):                                      # lathe axis -> y: the disc stands in the XZ plane
        return (p[0], p[2], zc + p[1])
    g.lathe("pommel_disc", prof, 20, xf=xf, edge=lambda r: 1.0 if min(prof[r][0], prof[r + 1][0]) > rim else 0.0)
    zr, R, r = HS_RING
    g.torus("pommel_ring", (0.0, 0.0, zr), R, r, edge=1.0)


def _hs_tassel(g):
    """Short hemp cord out of the pommel's face (a small binding where it leaves it) to a knot with a wrapped head and
    three frayed tails."""
    cord = _hs_crom(HS_CORD, 5)
    g.tube("cord", cord, [HS_CORD_R] * len(cord), 8)
    exit_pt = next(p for p in cord if p[1] < -(HS_POMMEL_DISC[2][1] + 0.08))   # just in front of the disc's face
    g.sphere("binding", exit_pt, 0.21, nu=8, nv=4, scale=(1.0, 0.8, 1.0))
    kx, ky, kz = HS_CORD[-1]
    g.sphere("knot", (kx, ky, kz), 0.3, nu=8, nv=5, scale=(1.0, 1.0, 0.85))
    g.lathe("tassel_head", [(0.0, 5.0), (0.2, 5.0), (0.23, 5.08), (0.23, 5.27), (0.2, 5.35), (0.0, 5.35)], 10,
            centre=(kx, ky))
    for tail in HS_TAILS:
        g.tube("tail", list(tail), [0.085, 0.075, 0.07], 6, star=(1.5, 0.8))


def heavy_sword_geo():
    """{part: _SGeo} of the Heavy Iron Sword in the sword's local frame (deterministic: seeded by HS_SEED)."""
    import random
    rng = random.Random(HS_SEED)
    geos = {p: _SGeo() for p in HS_PARTS}
    zs, mids = _hs_blade(geos["sword_blade"], rng)
    _hs_seams(geos["sword_glow"], zs, mids, rng)
    _hs_guard(geos["sword_guard"])
    _hs_grip(geos["sword_grip"])
    _hs_pommel(geos["sword_pommel"])
    _hs_tassel(geos["sword_tassel"])
    return geos


def _hs_mesh(g, name, materials, smooth_deg):
    """Write an _SGeo into a new mesh: material slots, the FACE float attribute 'edge' (U.EDGE_ATTR), face smooth
    flags, and hard edges (marked, sharper than smooth_deg, between materials or open)."""
    lim = math.radians(smooth_deg)
    bm = bmesh.new()
    layer = bm.faces.layers.float.new(U.EDGE_ATTR)
    vs = [bm.verts.new(p) for p in g.verts]
    bm.verts.index_update()
    for idx, m, e, sm in zip(g.faces, g.mat, g.edge, g.smooth):
        f = bm.faces.new([vs[i] for i in idx])
        f.material_index = m
        f[layer] = e
        f.smooth = sm
    bm.normal_update()
    for e in bm.edges:
        lf = e.link_faces
        a, b = e.verts[0].index, e.verts[1].index
        e.smooth = not (len(lf) != 2 or ((a, b) if a < b else (b, a)) in g.sharp
                        or lf[0].material_index != lf[1].material_index or e.calc_face_angle(math.pi) > lim)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    U.set_materials(me, materials)
    me.update()
    return me


def heavy_sword_meshes(log=None):
    """{part: new Mesh 'arena.<part>'} (tagged 'sect_heavy_sword'). A mesh already holding that name is renamed
    '<name>.old' first, for the caller to free once nothing uses it."""
    out = {}
    for part, g in heavy_sword_geo().items():
        nm = K + "." + part
        old = bpy.data.meshes.get(nm)
        if old is not None:
            old.name = nm + ".old"
        me = _hs_mesh(g, nm, HS_MATERIALS[part], HS_SMOOTH[part])
        me["sect_heavy_sword"] = part
        me["heavy_sword_tris"] = g.tris()
        out[part] = me
        if log:
            log(part, "mesh", me.name, "tris", g.tris(), "parts", len(g.parts), "materials", HS_MATERIALS[part])
    return out


def _build_sword(coll, root):
    """The Heavy Iron Sword 玄铁重剑, point down, piercing the island at the back. Origin = guard."""
    srot = Matrix.Rotation(math.radians(-6.0), 4, 'X') @ Matrix.Rotation(math.radians(3.0), 4, 'Y')
    sroot = U.empty(U.name(K, "sword"), coll, parent=root,
                    matrix=Matrix.Translation((SWORD_POS[0], SWORD_POS[1], SWORD_GUARD_Z)) @ srot)
    meshes = heavy_sword_meshes()
    for part in HS_PARTS:
        ob = U.object_from_mesh(U.name(K, part), meshes[part], coll, parent=sroot)
        if part == "sword_glow":
            ob["glow"] = HS_GLOW
            U.set_visibility(ob, shadow=False)
    # rubble where the blade enters the island
    r = U.rng(K, "rubble")
    for i in range(9):
        a = r.uniform(0, 2 * math.pi)
        d = r.uniform(3.0, 7.0)
        N.rock(coll, size=r.uniform(1.5, 3.6), seed=i, kind="boulder", name=U.name(K, "rubble"),
               location=(SWORD_POS[0] + d * math.cos(a), SWORD_POS[1] - 1.5 + 0.6 * d * math.sin(a), -1.5),
               parent=root)
    return sroot


# ======================================================================================
# island underside, roots, islets, chains
# ======================================================================================

def _build_island(coll, root):
    rock = N.floating_rock(coll, size=ROCK_SIZE, seed=48, depth=ROCK_DEPTH, vegetation=True, roots=True,
                           pine_on_top=False, name=U.name(K, "island"), location=(0.0, 0.0, ROCK_Z),
                           parent=root)
    # turn the rock so its widest sector carries the spectator tier (+X)
    rim0 = _rim_radius(rock)
    best = max(range(72), key=lambda i: min(rim0(2 * math.pi * i / 72 + TIER_A * (j / 4.0 - 1.0))
                                            for j in range(9)))
    rock.rotation_euler.z = -2 * math.pi * best / 72
    # extra hanging roots dangling off the rim into the void
    r = U.rng(K, "roots")
    bm_pts = []
    for i in range(26):
        a = 2 * math.pi * (i + r.uniform(-0.3, 0.3)) / 26
        rr = r.uniform(38.0, 42.0)
        L = r.uniform(10.0, 30.0)
        x0, y0, z0 = rr * math.cos(a), rr * math.sin(a), -2.5
        pts = [(x0, y0, z0, 1.0)]
        for j in range(1, 6):
            s = j / 5
            out = 1.5 * s
            pts.append((x0 + math.cos(a) * out + r.uniform(-0.8, 0.8),
                        y0 + math.sin(a) * out + r.uniform(-0.8, 0.8), z0 - L * s, 1.0 - 0.85 * s))
        U.tube_mesh(U.name(K, "root"), pts, r.uniform(0.25, 0.55), coll, material="nature_bark_blossom",
                    sides=6, samples_per_segment=3, parent=root)

    # small floating islets drifting around the island (parented to a slowly turning empty)
    orbit = U.empty(U.name(K, "orbit"), coll, parent=root)
    try:
        fc = orbit.driver_add("rotation_euler", 2)
        fc.driver.type = 'SCRIPTED'
        fc.driver.expression = "frame * 0.0006"
    except Exception:
        pass
    islets = [((-64, -34, -14), 9.0), ((-72, 22, -6), 6.0), ((-56, 62, -26), 11.0), ((66, -42, -22), 7.0),
              ((74, 34, -12), 10.0), ((26, 74, -18), 6.0), ((-24, 78, 2), 5.0), ((44, -66, -34), 8.0)]
    for i, ((x, y, z), s) in enumerate(islets):
        N.floating_rock(coll, size=s, seed=200 + i, depth=s * 1.1, vegetation=True, roots=True,
                        pine_on_top=(s >= 8), name=U.name(K, "islet"), location=(x, y, z),
                        rotation=r.uniform(0, 6.28), parent=orbit)

    # massive chains from the island flanks off to both sides (loose ends in the void)
    for p0, p1, sag in (((-40, -12, -6), (-165, -45, -48), 14.0),
                        ((-38, 22, -9), (-160, 70, -30), 10.0),
                        ((40, -18, -8), (165, -60, -52), 14.0),
                        ((39, 24, -10), (160, 80, -34), 10.0)):
        P.chain(coll, p0, p1, link_size=2.3, sag=sag, material="iron", name=U.name(K, "chain"), parent=root)
    return rock


# ======================================================================================
# banners, entrance
# ======================================================================================

def _build_banners(coll, root):
    r = U.rng(K, "banners")
    span = 2 * math.pi - 2 * GAP_FRONT
    a0 = -math.pi / 2 + GAP_FRONT
    last = -1
    for i in range(N_BANNERS):
        a = a0 + span * i / (N_BANNERS - 1)
        c = r.randrange(8)
        if c == last:
            c = (c + 1 + r.randrange(7)) % 8
        last = c
        h = 9.0 + r.uniform(-0.4, 0.4)
        if abs(a) < math.radians(1.0):          # stood 1.3 m in front of the centre aisle's foot
            a -= 2.0 / R_BANNER
        P.banner(coll, h, 1.3, material=M.banner_cloth(c), seed=i, name=U.name(K, "banner"), parent=root,
                 location=(R_BANNER * math.cos(a), R_BANNER * math.sin(a), Z_BAND),
                 rotation=(0.0, 0.0, a - math.pi / 2))


def _build_entrance(coll, root, z_at, edge):
    """Arrival from the forge chain bridge: a bridgehead slab on the axis under a three-bay gate,
    a paved strip and the front steps up to the banner band, stone lanterns, balustrades."""
    # front steps: top edge inside the band's rim across their whole width (no slot under it), their top tread
    # BAND_STEP_DROP under the band (round 12: 5 mm under it, the band's top and the tread z-fought on the web)
    st = A.stairs(U.name(K, "steps"), coll, 9.0, Z_BAND - FRONT_Z - BAND_STEP_DROP, ramp=False, balustrade=False,
                  parent=root, location=(0.0, FRONT_STEPS_Y, FRONT_Z))
    sink_steps(st, STEP_SINK)
    foot_y = FRONT_STEPS_Y - float(st["arch_run"])
    # bridgehead: 12 x 8 m, top flush with the steps' foot; the chain bridge lands on its outer edge
    A.platform(U.name(K, "bridgehead"), coll, 12.0, depth=BRIDGE_Y1 - BRIDGE_Y0, height=0.5, style="plain",
               parent=root, location=(0.0, (BRIDGE_Y0 + BRIDGE_Y1) * 0.5, FRONT_Z - 0.5))
    # paved strip from the bridgehead's edge to under the steps' foot (round 12: it started 0.15 m on the bridgehead,
    # 2 mm under its top: 1.3 m2 of z-fighting)
    _slab(U.name(K, "bridgehead_walk"), coll, root, (0.0, (BRIDGE_Y1 + foot_y + 0.05) * 0.5),
          (9.2, foot_y + 0.05 - BRIDGE_Y1), FRONT_Z - 0.002, FRONT_Z - 0.6)
    # three-bay gate (centre opening ~5.1 x 4.8 m clears the 3.2 m deck and its end posts), 7.5 m
    # tall so the 'rim' camera at z 12 passes ~6 m over it
    g = A.paifang(U.name(K, "bridge_gate"), coll, bays=3, width=11.0, height=7.5, center_frac=0.6, seed=7,
                  parent=root, location=(0.0, GATE_Y, FRONT_Z))
    anchor = bpy.data.objects.get(g.get("plaque_anchor", ""))
    if anchor is not None:
        P.plaque(coll, AREA["title_zh"], float(g["plaque_size"][0]), name=U.name(K, "plaque_gate"),
                 parent=anchor)
    for sx in (-1, 1):
        # side balustrades, returning at the front to the gate's outer columns
        A.balustrade(U.name(K, "bridgehead_rail"), coll,
                     [(sx * 5.25, BRIDGE_Y0 + 0.3, FRONT_Z), (sx * 5.75, BRIDGE_Y0 + 0.3, FRONT_Z),
                      (sx * 5.75, BRIDGE_Y1 - 0.25, FRONT_Z)], height=1.0, end_drum="end", parent=root)
        P.lantern_stone(coll, 2.6, name=U.name(K, "lantern"), parent=root,
                        location=(sx * 5.1, -38.0, FRONT_Z))
        # low rail along the island edge, 20 m each way from the bridgehead
        _rim_rail(coll, root, z_at, edge, -math.pi / 2 + sx * math.asin(6.4 / 45.4), length=sx * 20.0)
    under = [z_at(x, y, -9.0) for x in (-6.0, -3.0, 0.0, 3.0, 6.0)
             for y in (BRIDGE_Y0, -41.0, BRIDGE_Y1, foot_y)]
    print("ARENA front: steps foot y %.2f, highest grass under bridgehead %.2f (top %.2f), edge at -Y %.1f"
          % (foot_y, max(under), FRONT_Z, edge(-math.pi / 2)))


def _build_rear(coll, root, z_at, edge):
    """Way out to the Mission Hall: a stair from the banner band at REAR_A down to a paved landing
    and a short pier at the island edge, where the stepping stones start (AREA['depart'])."""
    rot = REAR_A - math.pi / 2                   # local +Y points out along REAR_A
    st = _band_stair(coll, root, REAR_A, REAR_Z, "rear_steps")
    r_foot = R_BAND - 0.15 + float(st["arch_run"])
    # (round 12: the walk ends at the landing's edge and the pier starts at it; they ran 0.15 and 0.2 m onto it,
    # 2 mm under its top: z-fighting on the web)
    _slab(U.name(K, "rear_walk"), coll, root, _radial(REAR_A, (r_foot - 0.1 + LAND_R[0]) * 0.5),
          (3.0, LAND_R[0] - (r_foot - 0.1)), REAR_Z - 0.002, REAR_Z - 0.6, rot=rot)
    A.platform(U.name(K, "rear_landing"), coll, LAND_W, depth=LAND_R[1] - LAND_R[0], height=0.5,
               style="plain", parent=root, location=_radial(REAR_A, sum(LAND_R) * 0.5) + (REAR_Z - 0.5,),
               rotation_z=rot)
    A.platform(U.name(K, "rear_pier"), coll, PIER_W, depth=PIER_R1 - LAND_R[1], height=0.5,
               style="plain", sink=PIER_SINK, parent=root,
               location=_radial(REAR_A, (LAND_R[1] + PIER_R1) * 0.5) + (REAR_Z - 0.502,),
               rotation_z=rot)
    # low rails along the island edge, 20 m each way, leaving room for the stones at the pier
    for sx in (-1, 1):
        _rim_rail(coll, root, z_at, edge, REAR_A + sx * 4.0 / 44.0, length=sx * 20.0)
    under = [z_at(*_radial(REAR_A, r, t), default=-9.0) for r in (r_foot, LAND_R[0], 39.0, LAND_R[1], PIER_R1)
             for t in (-LAND_W / 2, 0.0, LAND_W / 2)]
    print("ARENA rear: stair foot r %.2f, highest grass under landing %.2f (top %.2f), edge at %.0f deg %.1f, "
          "depart %s" % (r_foot, max(under), REAR_Z, math.degrees(REAR_A), edge(REAR_A), AREA["depart"]))
    # second band stair on the west, its foot on the grass
    x, y = _radial(WEST_A, R_BAND + 2.0)
    _band_stair(coll, root, WEST_A, z_at(x, y, -1.45) - 0.03, "west_steps")


# ======================================================================================
# entry points
# ======================================================================================

def build(collection):
    """Build the arena at the local origin. Returns the root Empty 'arena.root'."""
    root = U.empty("arena.root", collection, display_size=4.0)
    rock = _build_island(collection, root)
    z_at, edge = _ground(rock)
    _build_platform(collection, root)
    _build_banners(collection, root)
    _build_entrance(collection, root, z_at, edge)
    _build_rear(collection, root, z_at, edge)
    cleared = _clear_plants(rock, [(-math.pi / 2, math.radians(11.0), 33.0, 47.5),     # bridgehead + steps
                                   (REAR_A, math.radians(9.0), 33.0, 46.5),          # rear stair, landing, pier
                                   (WEST_A, math.radians(4.5), 33.0, 37.0)])         # west stair
    print("ARENA plants cleared from %d island faces under paving, %d under the platform" % (
        cleared, clear_plants_under_platform(rock)))
    rim = _rim_radius(rock)
    print("ARENA rim at +X %.1f m, tier arc min %.1f m" %
          (rim(0.0), min(rim(TIER_A * (j / 4.0 - 1.0)) for j in range(9))))
    _build_tier(collection, root, rim)
    _build_sword(collection, root)
    return root


# Fly-through hints, local coordinates, ordered along the flight (front = -Y).
CAMERA_HINTS = [
    # far approach slightly below the floor: the whole island floating, cone and roots, sword behind
    dict(name="approach", location=(-30.0, -150.0, 4.0), target=(0.0, 0.0, -6.0), lens=26),
    # crossing the rim low (12 m): banners sliding past both sides, sword ahead
    dict(name="rim", location=(-4.0, -46.0, 12.0), target=(0.0, 10.0, 9.0), lens=24),
    # over the platform: bagua below, tier and pavilions right, the sword towering ahead
    dict(name="hero", location=(-6.0, -18.0, 12.0), target=(2.0, 38.0, 17.0), lens=22),
    # leaving past the sword on its west side, looking back across the arena
    dict(name="exit", location=(-40.0, 56.0, 19.0), target=(6.0, 6.0, 4.0), lens=24),
]

build.preview_cameras = [(h["name"], h["location"], h["target"], h["lens"]) for h in CAMERA_HINTS]
