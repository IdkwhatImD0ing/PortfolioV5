"""Cave Abode 洞府 (site section 'personal').

A private dwelling carved into its own ~60 m cliff behind the plateau: a round moon-gate
cave entrance with a warm lit screen inside, a wooden balcony (stilts, red railing, small
tea pavilion with a low tea table, cushions and wind chimes) reached by a marble stair on
the gate axis, a waterfall pouring through a notch in the cliff into a misty koi pool beside
the balcony, peach blossom trees, bamboo groves, cliff pines, a big red cliff inscription
and a resting crane, and the Smiling, Proud Wanderer duet just after it ended (_duet): a stone qin table on the open
lawn west of the koi pool with the qin and the xiao on it, two stone stools and Mo Da's huqin leaning on the table.
(Xiaolongnü's golden-bell ribbon hung from the tea pavilion's eave until round 34; it now lies coiled on the condor's
rock at the summit, sect/lib/refs_west.py coil. _ribbon stays for the older patches.)
Blocking pass: shape, scale and colour coding over detail.

Route: the stair from the formation tops out on a paved arrival landing at the front rim (on
the gate axis), two low steps lead onto the paved path to the balcony stair (two flights of 18
risers with a landing at half height), and the moon gate opens onto the balcony at deck level.
A west branch runs to a depart landing at the west rim, where the stair to the summit starts;
flagstones lead from the path to a stone ledge at the koi pool. A stone rail stands on the lawn along
its south rim, open where the arrival landing crosses it.

Local frame: origin = centre of the plateau top, z = 0 walkable, front faces -Y.
"""

import math

import bmesh
import bpy
from mathutils import Vector

from sect.lib import util as U
from sect.lib import arch as A
from sect.lib import materials as M
from sect.lib import props as P
from sect.lib import nature as N

AREA = dict(key="abode", section_id="personal", title_en="Cave Abode", title_zh="洞府",
            footprint=45.0,
            # where world.py's connectors meet this area: (x, y, z, heading), local frame; heading
            # = direction of travel in radians (math.atan2(dy, dx)), so +y = pi/2 and -x = pi
            arrival=(-8.0, -51.0, -0.4, math.pi / 2),   # front edge of the arrival landing, on the gate axis
            depart=(-52.0, 0.0, -0.4, math.pi))         # west rim, past the depart landing, clear of the cliff's end

K = "abode"

# --- layout -------------------------------------------------------------------------------
CLIFF_R = 66.0      # plan radius of the concave cliff face (centre at (0, CLIFF_C))
CLIFF_C = -40.0
CLIFF_X = 47.0      # half width of the cliff
CLIFF_DEPTH = 28.0  # how far the rock mass goes back from the face
LEAN = 0.06         # the natural face leans back this many m per m of height
Z_BOT = -40.0       # cliff continues down into the terrain slope
GATE_X = -8.0       # moon gate axis
DECK_Z = 6.0        # balcony floor
GATE_R = 3.2        # moon-gate opening radius
GATE_ZC = DECK_Z + 3.0
RING_OUT = 4.25     # outer radius of the marble ring frame
DECK_BACK = 0.6     # the deck runs this far past the gate plane (YG) into the cave; the cave floor starts there
CAVE_FLOOR_Y0_OLD = -1.0   # before round 12 the cave floor started at YG - 1.0, on the deck (patch_r12_areas.py)
FALL_X = 15.0       # waterfall chute
INSC_X = -27.0      # cliff inscription column
STAIR_W = 3.6       # balcony stair: two flights of 18 risers with a 2 m landing at half height
STAIR_RUN = 0.33
FLIGHT_H = DECK_Z * 0.5
FLIGHT_L = math.ceil(FLIGHT_H / 0.17 - 1e-6) * STAIR_RUN   # same riser rule as arch.stairs
MID_LANDING = 2.0
PATH_W = 3.4        # paved walks
LAWN_R = 50.0       # the round lawn (N.ground_patch); the bare terrace around it ends 1-4 m further out at the cliff
RIM_R = 48.5        # stone rim rail: radius, on the lawn 1.5 m inside its edge (at 53 m it stood on the rock lip
                    # past the lawn, in places over the cliff's first slope), arc (degrees, from +x), gap at a landing
RIM_ARC = (200.0, 340.0)
RIM_GAP = 8.5       # the arrival landing (8 m wide) crosses the rail: the opening spans it plus 0.25 m a side
RIM_SEGS = (20, 26) # segments per span (west / east of the gap), 2 panels each: the web export keys every post and
                    # panel by its index, so sect/patch_abode_rail.py moves the rail without a new audit
RIM_SINK = 0.02     # the rail's feet sit this far into the lawn (its posts and sills reach 4-5 cm lower by design)
KOI_FROM = (-6.3, 2.0)    # flagstones from the path's east edge ...
KOI_LEDGE = (6.0, 12.0)   # ... to a 3 x 2 m stone ledge at the koi pool
KOI_STONES = 8

NX = 118            # cliff grid columns
NZ = 120            # front-face rows
NT = 12             # top rows
NB = 6              # back rows

# hand-placed pines: (x, z, height) out of the face, (x, m back from the front edge) on the top
FACE_PINES = ((-34.0, 18.0, 7.0), (27.0, 34.0, 8.0), (-17.0, 44.0, 7.5), (6.0, 30.0, 6.0))
TOP_PINES = ((-22.0, 4.0), (-6.0, 7.0), (24.0, 5.0), (36.0, 3.0))
PINNACLES = ((-21.0, 38.0, 90.0, 11.0, 55.0), (29.0, 34.0, 79.0, 8.5, 44.0))   # x, y, top z, radius, height

# density pass (dense_pines): Huangshan pines all over the face and the cliff top. Own generator, so
# every other piece of the abode stays exactly where it was; sect/patch_density.py adds the same to a
# finished out/sect_chase.blend (objects tagged DENSE_TAG, replaced on a re-run).
DENSE_TAG = "sect_density"      # = scenery.DENSITY_TAG
# Round 48 (plan r45 D1 + the abode variant; the main session applied it for the sleeping owner, 2026-10-24): no pine
# grows out of the cliff face any more (the 25 dense face pines, the 4 FACE_PINES and the pinnacles' wall pines). In
# their place (r48_dress): two hero pines on one rock shelf right of the inscription, fern and shrub strips in three
# joints, vines hanging from the rim and a shrub shelf left of the fall. A finished scene gets the same through
# sect/patch_r48_green.py PARTS=abode (the old pines hidden, not deleted: PARTS=abode_undo shows them again).
ABODE_R48 = True
R48_DRESS = False              # phase D (range critic M4): r48_dress builds nothing. Its sawn-slab shelf with two flat
                               # pines, the shrub-shelf slab, the vines (black strips) and the fern strips (bead
                               # ladders) read as man-made; with the face pines gone the cliff reads as one mass
                               # (intent 3.1 abode). The code stays for a later, better-placed dressing
R48_TOP_X = 33.0               # round 48: no cliff-top pine past |x| 33 m. There _top's shoulders drop the top edge to
                               # 4 m, so a top pine stands on the falling flank and reads as growing out of the face
                               # (range critic M4: f1380 x 315-395, the formation's view of the right flank)
R48_TAG = "sect_r48"            # = scenery.R48_TAG
R48_SHELF = (INSC_X + 9.5, 31.0, 9.0)          # hero-pine shelf: x, z (its top), width
R48_SHELF_PINES = ((-0.24, 8.5, 3), (0.2, 6.6, 8))   # (along the shelf (x width), height m, seed)
R48_SHRUB_SHELF = (10.0, 26.0, 5.5)            # left of the fall (the hold sees +x on its right)
R48_FERN_X = (3.0, 23.0, 37.0)                 # joints with fern and shrub strips
R48_FERN_STEP = 1.8                            # m between strip plants (40 % gaps)
R48_FERN_RUN = (5.0, 11.0)                     # m: a run of strip plants (phase C: strips, not dotted lines)
R48_FERN_GAP = (5.0, 12.0)                     # m of bare joint between runs
R48_VINE_X = (-44.0, 44.0, 6.5)                # vines from the rim: from, to, spacing (jittered)
R48_VINE_LEN = (4.0, 8.0)
DENSE_FACE_PINES = 25           # cliff pines out of the face (round 48: drawn, never built; see ABODE_R48)
DENSE_FACE_H = (10.0, 16.0)
DENSE_TOP_DENSITY = 0.025       # Huangshan pines per m2 of the cliff top rows the pinnacles leave free
DENSE_TOP_H = (9.0, 14.0)
DENSE_SPACING = 6.0             # trunk to trunk (face: in x/z; top: in plan)


def _smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def _yb(x):
    """Plan curve of the face (concave toward -Y)."""
    return CLIFF_C + math.sqrt(CLIFF_R * CLIFF_R - x * x)


def _top(x):
    """Height of the cliff's front edge."""
    h = 58.0 + 6.0 * math.exp(-((x + 14.0) / 12.0) ** 2) + 3.0 * math.exp(-((x - 30.0) / 6.0) ** 2)
    h += 3.0 * U.fbm(Vector((x * 0.07, 2.3, 0.0)), octaves=3, seed=5)
    h += 7.0 * (abs(U.noise3(Vector((x * 0.09, 5.1, 0.0)), seed=12)) - 0.3)   # crags and pinnacles
    shoulder = 1.0 - _smooth(31.0, CLIFF_X, abs(x))
    h = 4.0 + (h - 4.0) * shoulder
    h -= 11.0 * math.exp(-((x - FALL_X) / 4.0) ** 2) * shoulder   # notch for the waterfall
    return h


YG = _yb(GATE_X) + LEAN * GATE_ZC                 # dressed rock plane around the gate
Y_DECK = YG - 8.0                                  # balcony front edge (top of the stair)
Y_FOOT = Y_DECK - 2 * FLIGHT_L - MID_LANDING       # foot of the balcony stair, end of the path


def _lip_z():
    return _top(FALL_X)


def _y_chute():
    return _yb(FALL_X) + LEAN * _lip_z() + 0.8


def _rect_w(x, z, x0, x1, z0, z1, blend):
    ex = max(0.0, x0 - x, x - x1)
    ez = max(0.0, z0 - z, z - z1)
    return 1.0 - _smooth(0.0, blend, math.hypot(ex, ez))


def _soft_excess(u, k):
    """0 for u <= 0, u - k / 2 for u >= k, C1 in between: subtracted from y it clamps y softly to at most cap + k / 2
    and never moves a point that is already in front of the cap."""
    if u <= 0.0:
        return 0.0
    if u >= k:
        return u - 0.5 * k
    return u * u / (2.0 * k)


# Slope cap over the dressed rock. The natural face above the dressed zone stands 1-5.5 m behind its plane (YG), and the
# 5 m blend between them made a shelf at z 17-22 m right over the moon gate (world normal z up to 0.84) that the rock
# material's moss (materials._rock_life: moss on up-facing rock) painted as one big green smear in the 1380 hold. From
# the dressed zone's top edge (CAP_Z1) the rock may now lean back from the dressed plane no faster than CAP_SLOPE m per
# m up (normal z ~0.25-0.35 with its texture, about the natural face's strata, under the moss threshold at this
# altitude), meeting the natural face again 10-20 m higher; a little fluting and strata keep it rock-like. Points in
# front of the cap never move, so the dressed panel, the gate and the plaque stay exactly where they were.
# CAP_X: where it applies (x0, x1) and its fade-out widths left and right (the right one ends at x 11, short of the
# waterfall sheet at x >= 11.3, which falls 1.5 m in front of the dressed plane anyway).
CAP_Z1 = 17.0          # = the dressed rect's top (_face_y)
CAP_SLOPE = 0.25
CAP_X = (-16.0, 8.5, 5.0, 2.5)
CAP_K = 0.25           # soft-clamp corner (m)


def _cap_w(x, z):
    x0, x1, bl, br = CAP_X
    if x < x0:
        wx = 1.0 - _smooth(0.0, bl, x0 - x)
    elif x > x1:
        wx = 1.0 - _smooth(0.0, br, x - x1)
    else:
        wx = 1.0
    return wx * _smooth(CAP_Z1 - 1.5, CAP_Z1 - 0.5, z)


def _face_y(x, z):
    """y of the cliff face at (x, z): natural rock with dressed zones, the slope cap over the dressed rock and the
    water chute."""
    p = Vector((x, 0.0, z))
    d = 3.0 * U.fbm(p, scale=0.03, octaves=3, seed=11)
    n1 = U.noise3(Vector((x * 0.11, 7.7, z * 0.012)), seed=3)
    d += 4.0 * (1.0 - abs(n1)) ** 4 - 1.2 * abs(n1)                        # deep clefts, rock columns
    flute = U.noise3(Vector((x * 0.3, 2.7, z * 0.02)), seed=13)
    strata = U.noise3(Vector((x * 0.02, 1.3, z * 0.30)), seed=4)
    d += 1.0 * flute                                                        # fine vertical fluting
    d += 0.7 * strata                                                       # strata bands
    y = _yb(x) + LEAN * z + d
    # dressed (carved smooth) rock around the gate, balcony and plaque
    yd = YG + 0.12 * U.noise3(p, scale=0.4, seed=6)
    w = _rect_w(x, z, -16.0, 10.0, -2.0, CAP_Z1, 5.0)
    y = y + (yd - y) * w
    # the slope cap over it (see CAP_*)
    w = _cap_w(x, z)
    if w > 0.0:
        tex = _smooth(CAP_Z1, CAP_Z1 + 6.0, z) * (0.4 * flute + 0.2 * strata + 0.2 * (n1 * n1 - 0.25))
        cap = yd + CAP_SLOPE * max(0.0, z - CAP_Z1) + tex
        y -= w * _soft_excess(y - cap, CAP_K)
    # flat panel for the cliff inscription
    w = _rect_w(x, z, INSC_X - 3.5, INSC_X + 3.5, 18.5, 41.0, 3.0)
    y = y + (_yb(x) + LEAN * 30.0 - y) * w
    # water-cut chute behind the waterfall
    w = 1.0 - _smooth(3.0, 6.5, abs(x - FALL_X))
    y = y + (_y_chute() + 0.25 * U.noise3(p, scale=0.3, seed=8) - y) * w
    return y


def _face_point(x, z):
    return Vector((x, _face_y(x, z), z))


def _face_yaw(x):
    """Yaw that turns a -Y facing object to face out of the cliff at x."""
    dx, dy = -x, -(_yb(x) - CLIFF_C)
    return math.atan2(dx, -dy)


def _top_point(x, s):
    """Point of the cliff's top surface at x: s = 0 at the front edge, 1 where the back rows start
    (the surface _cliff builds through its top rows)."""
    top = _top(x)
    yt = _face_y(x, top)
    yb = min(_yb(x) + CLIFF_DEPTH, math.sqrt(max(0.0, 50.0 ** 2 - x * x)))
    yb = max(yb, yt + 8.0)
    y = yt + s * (yb - 5.0 - yt)
    z = top + 2.0 * math.sin(math.pi * s) - 9.0 * s * s
    z += 2.5 * U.noise3(Vector((x * 0.08, y * 0.08, 0.5)), seed=9)
    return Vector((x, y, z))


# --- builders -----------------------------------------------------------------------------

def _cliff_verts():
    """The cliff's vertex grid: (NX + 1) column profiles of NZ + 1 + NT + NB vertices each (front face bottom to top,
    top surface going back, back face down), in abode.root's frame. sect/patch_r5_duet.py moves a finished file's
    abode.cliff onto it."""
    verts = []
    for i in range(NX + 1):
        x = -CLIFF_X + 2.0 * CLIFF_X * i / NX
        top = _top(x)
        # front face, bottom to top
        for j in range(NZ + 1):
            z = Z_BOT + (top - Z_BOT) * j / NZ
            verts.append(_face_point(x, z))
        yt = verts[-1].y
        yb = min(_yb(x) + CLIFF_DEPTH, math.sqrt(max(0.0, 50.0 ** 2 - x * x)))
        yb = max(yb, yt + 8.0)
        # top surface going back (rounded, noisy)
        for j in range(1, NT + 1):
            s = j / NT
            y = yt + s * (yb - 5.0 - yt)
            z = top + 2.0 * math.sin(math.pi * s) - 9.0 * s * s
            z += 2.5 * U.noise3(Vector((x * 0.08, y * 0.08, 0.5)), seed=9)
            verts.append(Vector((x, y, z)))
        zb = verts[-1].z
        for j in range(1, NB + 1):
            s = j / NB
            verts.append(Vector((x, yb, zb + (Z_BOT - zb) * s)))
    return verts


def _cliff(coll, root):
    faces = []
    ncol = NZ + 1 + NT + NB          # vertices per column profile
    verts = _cliff_verts()
    gx, gz = GATE_X, GATE_ZC
    hole = GATE_R + 0.3
    for i in range(NX):
        a, b = i * ncol, (i + 1) * ncol
        for j in range(ncol - 1):
            if j < NZ:
                c = (verts[a + j] + verts[a + j + 1] + verts[b + j] + verts[b + j + 1]) * 0.25
                if math.hypot(c.x - gx, c.z - gz) < hole:
                    continue        # the moon-gate opening
            faces.append((a + j, b + j, b + j + 1, a + j + 1))
    # end caps (fans), so the cliff reads as a solid from the side
    for i, flip in ((0, True), (NX, False)):
        a = i * ncol
        c = sum((verts[a + j] for j in range(ncol)), Vector()) / ncol
        ci = len(verts)
        verts.append(c)
        for j in range(ncol - 1):
            f = (a + j, a + j + 1, ci)
            faces.append(f[::-1] if flip else f)
    ob = U.mesh_from_pydata(K + ".cliff", [tuple(v) for v in verts], faces, coll,
                            materials=["rock_cliff"], smooth=math.radians(50), parent=root)
    me = ob.data
    # make the face normals point out of the rock (toward -Y on the front)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.faces.ensure_lookup_table()
    f0 = bm.faces[NZ // 2]
    f0.normal_update()
    if f0.normal.y > 0:
        for f in bm.faces:
            f.normal_flip()
    bm.to_mesh(me)
    bm.free()
    U.auto_smooth(ob, math.radians(50))
    return ob


def _annulus(name, coll, root, r_in, r_out, y0, y1, center, mat, segs=48):
    """Ring around the Y axis (moon-gate frame), from y0 to y1."""
    cx, cz = center
    verts, faces = [], []
    for k in range(segs):
        t = 2 * math.pi * k / segs
        c, s = math.cos(t), math.sin(t)
        for r, y in ((r_in, y0), (r_out, y0), (r_out, y1), (r_in, y1)):
            verts.append((cx + r * c, y, cz + r * s))
    for k in range(segs):
        a, b = 4 * k, 4 * ((k + 1) % segs)
        for q in range(4):
            q1 = (q + 1) % 4
            faces.append((a + q, b + q, b + q1, a + q1))
    ob = U.mesh_from_pydata(name, verts, faces, coll, materials=[mat], smooth=math.radians(40),
                            parent=root)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    U.auto_smooth(ob, math.radians(40))
    return ob


def _cave(coll, root):
    """Tunnel behind the moon gate, floor, lit screen, warm light, ring frame, plaque."""
    y0, y1 = YG - 0.4, YG + 7.5
    segs = 40
    verts, faces = [], []
    for y in (y0, y1):
        for k in range(segs):
            t = 2 * math.pi * k / segs
            verts.append((GATE_X + GATE_R * math.cos(t), y, GATE_ZC + GATE_R * math.sin(t)))
    for k in range(segs):
        k1 = (k + 1) % segs
        faces.append((k, k1, segs + k1, segs + k))             # normals point inward
    faces.append(tuple(segs + k for k in range(segs)))      # back wall, faces -Y
    U.mesh_from_pydata(K + ".cave_tunnel", verts, faces, coll, materials=["rock_cliff"],
                       smooth=math.radians(50), parent=root)
    # floor through the gate into the cave, from the deck's back edge (YG + DECK_BACK) to the back wall. Round 12: it
    # started 1 m in front of the gate, on the deck, both tops at DECK_Z: 7 m2 of light and dark wood z-fighting on the
    # web. Now the two meet edge to edge
    yd = YG + DECK_BACK
    bm = bmesh.new()
    U.bm_box(bm, (2 * GATE_R, y1 - yd, 0.4), center=(GATE_X, (yd + y1) * 0.5, DECK_Z - 0.2))
    U.mesh_from_bmesh(K + ".cave_floor", bm, coll, materials=["wood_dark"], parent=root)
    # warm lit screen at the back of the cave
    A.lattice_panel(K + ".cave_screen", coll, 3.6, 4.6, pattern="diamond", kind="window", lit=True,
                    parent=root, location=(GATE_X, y1 - 0.15, DECK_Z))
    ld = bpy.data.lights.new(K + ".cave_light", "POINT")
    ld.energy = 1500.0
    ld.color = (1.0, 0.62, 0.32)
    ld.shadow_soft_size = 1.0
    lo = bpy.data.objects.new(K + ".cave_light", ld)
    coll.objects.link(lo)
    U.parent(lo, root, keep_transform=False)
    lo.location = (GATE_X, YG + 3.0, GATE_ZC + 0.5)
    # marble ring frame (covers the jagged hole edge)
    _annulus(K + ".gate_ring", coll, root, GATE_R - 0.05, RING_OUT, YG - 0.45, YG + 0.6,
             (GATE_X, GATE_ZC), "marble_white")
    _annulus(K + ".gate_ring_gold", coll, root, GATE_R - 0.12, GATE_R + 0.12, YG - 0.55, YG - 0.2,
             (GATE_X, GATE_ZC), "gold")
    # plaque above the gate
    P.plaque(coll, AREA["title_zh"], 4.2, name=K + ".plaque", parent=root,
             location=(GATE_X, YG - 0.5, GATE_ZC + RING_OUT + 1.15))
    # stone lanterns flanking the gate on the balcony
    for i, dx in enumerate((-5.4, 5.4)):
        P.lantern_stone(coll, 2.0, name=K + ".gate_lantern", parent=root,
                        location=(GATE_X + dx, YG - 1.4, DECK_Z))


def _box(name, coll, root, size, center, mat):
    bm = bmesh.new()
    U.bm_box(bm, size, center=center)
    return U.mesh_from_bmesh(name, bm, coll, materials=[mat], parent=root)


def _balcony(coll, root):
    x0, x1 = -14.5, 9.0
    yf = Y_DECK
    _box(K + ".deck", coll, root, (x1 - x0, YG + DECK_BACK - yf, 0.45),
         ((x0 + x1) * 0.5, (yf + YG + DECK_BACK) * 0.5, DECK_Z - 0.225), "wood_light")
    # front beam and cantilever joists (dark wood) under the deck
    _box(K + ".deck_beam", coll, root, (x1 - x0, 0.5, 0.6), ((x0 + x1) * 0.5, yf + 0.3, DECK_Z - 0.75),
         "wood_dark")
    for k, x in enumerate((-14.0, -10.6, -5.4, -0.6, 4.2, 8.5)):
        _box(K + ".joist", coll, root, (0.4, YG + 0.8 - yf, 0.55), (x, (yf + YG + 0.8) * 0.5, DECK_Z - 0.72),
             "wood_dark")
    # stilts down to the plateau, with diagonal braces into the cliff
    me = U.shared_mesh("abode.stilt", _stilt_bm)
    if not me.materials:
        U.set_materials(me, ["lacquer_red_worn"])
    for k, x in enumerate((-14.0, -10.6, -5.4, -0.6, 4.2, 7.0)):     # corner stilt kept out of the pool
        U.object_from_mesh(U.name(K, "stilt"), me, coll, location=(x, yf + 0.35, -0.5), parent=root)
        if k in (0, 2, 4, 5):
            U.tube_mesh(U.name(K, "brace"), [(x, yf + 0.4, DECK_Z - 3.6), (x, YG - 0.2, DECK_Z - 0.9)],
                        0.16, coll, material="wood_dark", sides=6, parent=root)
    # red wooden railing, open at the stairs, running right back to the rock
    zr = DECK_Z
    A.balustrade(K + ".rail_l", coll, [(GATE_X - 2.0, yf + 0.2, zr), (x0 + 0.2, yf + 0.2, zr),
                                         (x0 + 0.2, YG - 0.05, zr)],
                 height=1.0, post_spacing=1.7, style="wood", mat="lacquer_red", parent=root)
    A.balustrade(K + ".rail_r", coll, [(GATE_X + 2.0, yf + 0.2, zr), (x1 - 0.2, yf + 0.2, zr),
                                         (x1 - 0.2, YG - 0.05, zr)],
                 height=1.0, post_spacing=1.7, style="wood", mat="lacquer_red", parent=root)
    # marble stair from the plateau up to the balcony, on the gate axis: two flights of 18 risers
    # with a 2 m landing at half height, on a solid marble pier
    y_land = yf - FLIGHT_L                      # back edge of the mid landing (foot of the upper flight)
    y_low = y_land - MID_LANDING                # top edge of the lower flight
    _box(K + ".stairs_pier", coll, root, (STAIR_W, yf - y_low, FLIGHT_H + 0.3),
         (GATE_X, (yf + y_low) * 0.5, (FLIGHT_H - 0.3) * 0.5), "marble_white")
    A.stairs(K + ".stairs", coll, STAIR_W, FLIGHT_H, run_per_step=STAIR_RUN, ramp=False, balustrade=True,
             parent=root, location=(GATE_X, yf, FLIGHT_H))
    A.stairs(K + ".stairs_low", coll, STAIR_W, FLIGHT_H, run_per_step=STAIR_RUN, ramp=False, balustrade=True,
             bal_extend=MID_LANDING, parent=root, location=(GATE_X, y_low, 0.0))
    # tea pavilion on the balcony's waterfall end
    tx, ty = 4.2, YG - 4.2
    pav = A.pavilion(K + ".tea_pavilion", coll, sides=4, radius=2.6, height=3.0, roof="pyramid",
                     roof_mat="roof_tile_teal", platform_h=0.0, seats=False, hanging=True,
                     parent=root, location=(tx, ty, DECK_Z))
    # low tea table, tea set, cushions
    _box(K + ".tea_table", coll, root, (1.3, 0.8, 0.08), (tx, ty, DECK_Z + 0.38), "lacquer_black")
    for sx in (-0.55, 0.55):
        for sy in (-0.3, 0.3):
            _box(K + ".tea_leg", coll, root, (0.07, 0.07, 0.34), (tx + sx, ty + sy, DECK_Z + 0.17),
                 "lacquer_black")
    P.tea_set(coll, name=K + ".tea_set", parent=root, location=(tx, ty, DECK_Z + 0.42))
    for dx in (-1.05, 1.05):
        P.cushion(coll, 0.62, "square", name=K + ".cushion", parent=root,
                  location=(tx + dx, ty, DECK_Z))
    # wind chimes and lanterns at the pavilion eave corners
    corner = _roof_corner(pav)
    for k, (sx, sy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
        loc = (tx + sx * corner[0], ty + sy * corner[0], DECK_Z + corner[1])
        if sy < 0:
            P.lantern_hanging(coll, "round", 0.8, cord=0.3, name=K + ".lantern", parent=root, location=loc)
        else:
            P.wind_chime(coll, 1.4, name=K + ".wind_chime", parent=root, location=loc)
    # extra wind chimes and red lanterns along the deck front
    for k, x in enumerate((-12.0, -4.0)):
        P.wind_chime(coll, 1.4, name=K + ".wind_chime", parent=root, location=(x, yf + 0.2, DECK_Z + 1.0))


def _stilt_bm():
    bm = bmesh.new()
    U.bm_cylinder(bm, 0.24, DECK_Z - 0.55 + 0.5, segments=12,
                  center=(0, 0, (DECK_Z - 0.55 + 0.5) * 0.5))
    return bm


def _roof_corner(pav):
    """(diagonal half extent, z) of the pavilion's eave corner, from the roof root props."""
    for ob in [pav] + list(pav.children_recursive):
        if "arch_corner_z" in ob.keys():
            half = float(ob.get("arch_eave_w", 7.0)) * 0.5
            return half * 0.97, ob.location.z + float(ob["arch_corner_z"]) - 0.1
    return 3.2, 4.6


def _water(coll, root):
    zl = _lip_z()
    lip = (FALL_X, _y_chute() - 0.4, zl)
    wf = N.waterfall(coll, height=zl, width=6.0, seed=3, name=K + ".waterfall", parent=root,
                     location=lip)
    foot = Vector(wf["foot"]) + Vector(lip)
    pc = (foot.x - 0.5, foot.y - 3.0)
    N.pond(coll, radius=7.0, seed=4, name=K + ".pool", parent=root, location=(pc[0], pc[1], 0.0))
    for k in range(6):
        a = 2.1 * k + 0.4
        P.koi(coll, seed=k, length=0.6, name=K + ".koi", parent=root,
              location=(pc[0] + 3.2 * math.cos(a), pc[1] - 1.0 + 2.6 * math.sin(a), -0.32),
              rotation=(0, 0, a + 1.3))
    return pc


def _pave(name, coll, root, x0, x1, y0, y1, top, bottom, rects):
    """Axis-aligned paving slab from (x0, y0) to (x1, y1), top at ``top``; records its rect."""
    _box(name, coll, root, (x1 - x0, y1 - y0, top - bottom), ((x0 + x1) * 0.5, (y0 + y1) * 0.5,
                                                               (top + bottom) * 0.5), "marble_paving")
    rects.append((x0, x1, y0, y1, top))


def _rect_d(x, y, r):
    return math.hypot(max(r[0] - x, 0.0, x - r[1]), max(r[2] - y, 0.0, y - r[3]))


def _routes(coll, root):
    """Walking routes on the lawn. Returns [(x0, x1, y0, y1, top)] of everything paved or built on
    the lawn (the lawn is pressed below these, and kept free of scattered plants)."""
    rects = []
    hw = PATH_W * 0.5
    # arrival landing where the stair from the formation tops out, then two low steps up onto the
    # paved path that runs on the gate axis to the foot of the balcony stair
    _pave(K + ".arrival", coll, root, GATE_X - 4.0, GATE_X + 4.0, -51.0, -45.0, -0.2, -0.6, rects)
    A.stairs(K + ".arrival_steps", coll, PATH_W + 0.5, 0.3, run_per_step=0.33, ramp=False, balustrade=False,
             stringer=0.25, parent=root, location=(GATE_X, -45.0, -0.2))
    _pave(K + ".path", coll, root, GATE_X - hw, GATE_X + hw, -45.0, Y_FOOT, 0.1, -0.3, rects)
    # west branch from the path to the depart landing at the west rim (stops at the main path's
    # edge, so the two slabs do not overlap at the same height)
    _pave(K + ".path_west", coll, root, -46.0, GATE_X - hw, -1.5, 1.5, 0.1, -0.3, rects)
    _pave(K + ".depart", coll, root, -50.0, -44.0, -3.0, 3.0, -0.1, -0.5, rects)
    # two low steps down the landing's west edge to a paved apron at terrace level, which reaches
    # the declared depart point where the summit stair starts
    dx_, dy_, dz_ = AREA["depart"][:3]
    A.stairs(K + ".depart_steps", coll, 5.0, -0.1 - dz_, run_per_step=0.33, ramp=False, balustrade=False,
             stringer=0.25, parent=root, location=(-50.0, dy_, dz_), rotation_z=-math.pi / 2)
    _pave(K + ".depart_apron", coll, root, dx_, -50.6, dy_ - 2.5, dy_ + 2.5, dz_ + 0.02, dz_ - 0.2, rects)
    rects.append((-50.7, -50.0, dy_ - 2.5, dy_ + 2.5, dz_))           # under the depart steps
    rects.append((GATE_X - STAIR_W * 0.5, GATE_X + STAIR_W * 0.5, Y_FOOT, Y_DECK, 0.0))   # balcony stair
    # stone lanterns: a pair flanking the balcony stair's foot (clear of the koi-pool flagstones),
    # a pair halfway down the path
    for dx in (-2.8, 2.8):
        P.lantern_stone(coll, 2.6, name=K + ".path_lantern", parent=root, location=(GATE_X + dx, Y_FOOT + 1.0, 0.0))
    for dx in (-3.4, 3.4):
        P.lantern_stone(coll, 2.6, name=K + ".path_lantern", parent=root, location=(GATE_X + dx, Y_FOOT - 18.0, 0.0))
    return rects


def _koi_layout():
    """Flagstone centres (x, y), the walk direction, and the ledge's near-edge centre."""
    sx, sy = KOI_FROM
    lx, ly = KOI_LEDGE
    d = math.hypot(lx - sx, ly - sy)
    ux, uy = (lx - sx) / d, (ly - sy) / d
    first, last = 0.75, d - 1.0 - 0.75           # stop a stride short of the ledge's near edge
    pts = [(sx + ux * (first + (last - first) * i / (KOI_STONES - 1)),
            sy + uy * (first + (last - first) * i / (KOI_STONES - 1))) for i in range(KOI_STONES)]
    return pts, (ux, uy)


def _koi_walk(coll, root, gz):
    """Flagstones across the lawn from the path to a stone ledge at the koi pool."""
    pts, (ux, uy) = _koi_layout()
    yaw = math.atan2(uy, ux) - math.pi / 2       # local +Y along the walk
    r = U.rng("abode.flagstones")
    for i, (x, y) in enumerate(pts):
        a = yaw + r.uniform(-0.15, 0.15)
        sl, sw = r.uniform(1.0, 1.15), r.uniform(0.9, 1.05)
        ca, sa = math.cos(a), math.sin(a)
        corners = [(x + ca * px - sa * py, y + sa * px + ca * py)
                   for px in (-sw * 0.5, sw * 0.5) for py in (-sl * 0.5, sl * 0.5)]
        top = max(gz(cx, cy, 0.0) for cx, cy in corners + [(x, y)]) + 0.04
        bm = bmesh.new()
        U.bm_box(bm, (sw, sl, 0.25), center=(0.0, 0.0, -0.125))
        U.mesh_from_bmesh(U.name(K, "flagstone"), bm, coll, materials=["stone_grey"], parent=root,
                          location=(x, y, top), rotation=(0.0, 0.0, a))
    # the ledge: 3 m across the walk, 2 m along it, top a step above the lawn, dipping into the pool
    lx, ly = KOI_LEDGE
    top = gz(lx - ux, ly - uy, 0.0) + 0.12
    bm = bmesh.new()
    U.bm_box(bm, (3.0, 2.0, top + 0.7), center=(0.0, 0.0, -(top + 0.7) * 0.5))
    U.mesh_from_bmesh(K + ".koi_ledge", bm, coll, materials=["stone_grey"], parent=root,
                      location=(lx, ly, top), rotation=(0.0, 0.0, yaw))


def _seat_lawn(ground, rects, under=0.08, slope=0.2):
    """Press the lawn down under paving (``under`` below its top), rising gently away from it, so
    no grass pokes through a slab and every slab edge stands clear of the lawn."""
    me = ground.data
    for v in me.vertices:
        z = v.co.z
        for r in rects:
            d = _rect_d(v.co.x, v.co.y, r)
            if d < 2.0:
                z = min(z, r[4] - under + slope * d)
        v.co.z = z
    me.update()


def _garden_mask(ground, rects, clear=0.8):
    """Point attribute 'garden_mask': 0 on and near paths (no scattered plants there), else 1."""
    me = ground.data
    att = me.attributes.get("garden_mask") or me.attributes.new("garden_mask", 'FLOAT', 'POINT')
    att.data.foreach_set("value", [0.0 if any(_rect_d(v.co.x, v.co.y, r) < clear for r in rects) else 1.0
                                   for v in me.vertices])


def _lawn_sampler(ground):
    """gz(x, y, default): lawn height at (x, y), local frame."""
    from mathutils.bvhtree import BVHTree
    me = ground.data
    bvh = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    down = Vector((0.0, 0.0, -1.0))

    def gz(x, y, default=-0.4):
        hit = bvh.ray_cast(Vector((x, y, 20.0)), down)
        return hit[0].z if hit[0] is not None else default
    return gz


def _rim_spans(gz):
    """Polylines [(x, y, z), ...] of the stone rail along the lawn's open south rim, one per span: an arc
    at RIM_R over RIM_ARC with a RIM_GAP opening wherever a landing (arrival / depart) lies inside the
    arc, centred on the landing's x or y; RIM_SEGS[k] segments in span k. z = the lawn under each point
    (gz, _lawn_sampler) less RIM_SINK, so every post stands on the grass."""
    a0, a1 = (math.radians(a) for a in RIM_ARC)
    cuts = []
    for p in (AREA["arrival"], AREA["depart"]):
        a = math.atan2(p[1], p[0]) % (2 * math.pi)
        if not a0 < a < a1:
            continue
        h = RIM_GAP * 0.5
        if abs(math.sin(a)) > abs(math.cos(a)):          # landing on the south rim: gap in x
            ends = [math.atan2(-math.sqrt(RIM_R ** 2 - (p[0] + s * h) ** 2), p[0] + s * h) for s in (-1, 1)]
        else:
            ends = [math.atan2(p[1] + s * h, math.copysign(math.sqrt(RIM_R ** 2 - (p[1] + s * h) ** 2), p[0]))
                    for s in (-1, 1)]
        ends = sorted(e % (2 * math.pi) for e in ends)
        cuts.append(tuple(ends))
    spans, s = [], a0
    for c0, c1 in sorted(cuts):
        spans.append((s, c0))
        s = c1
    spans.append((s, a1))
    out = []
    for i, (b0, b1) in enumerate(spans):
        n = RIM_SEGS[i] if i < len(RIM_SEGS) else max(1, int(math.ceil((b1 - b0) / math.radians(3.0))))
        pts = []
        for k in range(n + 1):
            x, y = RIM_R * math.cos(b0 + (b1 - b0) * k / n), RIM_R * math.sin(b0 + (b1 - b0) * k / n)
            pts.append((x, y, gz(x, y, -0.4) - RIM_SINK))
        out.append(pts)
    return out


def _rim_rail(coll, root, gz):
    """Stone rail on the lawn along its open south rim (_rim_spans), one balustrade per span."""
    for pts in _rim_spans(gz):
        A.balustrade(U.name(K, "rim_rail"), coll, pts, height=1.0, mat="stone_grey", parent=root)


def _ground(coll, root, pool):
    g = N.ground_patch(coll, radius=LAWN_R, seed=7, height=0.3, edge_drop=0.2,
                       holes=[(pool[0], pool[1], 7.7, 1.3)], name=K + ".ground", parent=root)
    rects = _routes(coll, root)
    _seat_lawn(g, rects)
    gz = _lawn_sampler(g)
    _koi_walk(coll, root, gz)
    pts, (ux, uy) = _koi_layout()
    lx, ly = KOI_LEDGE
    keep_clear = rects + [(x - 0.6, x + 0.6, y - 0.6, y + 0.6, 0.0) for x, y in pts] + \
        [(lx - 1.8, lx + 1.8, ly - 1.8, ly + 1.8, 0.0)] + duet_keep_clear()
    _garden_mask(g, keep_clear)
    N.scatter_on(g, N.plant_prototypes("garden"), density=0.012, seed=5, max_slope=math.radians(25),
                 collection=coll, name=K + ".garden_scatter", mask_attribute="garden_mask")
    # two stone lanterns at the depart landing's outer corners
    for sy in (-3.4, 3.4):
        P.lantern_stone(coll, 2.6, name=K + ".depart_lantern", parent=root, location=(-49.0, sy, gz(-49.0, sy)))
    _rim_rail(coll, root, gz)


def _top_pine_points():
    """Bases of the hand-placed cliff-top pines (TOP_PINES), 0.6 m into the ground."""
    out = []
    for x, back in TOP_PINES:
        top = _top(x)
        y = _face_y(x, top) + back
        s = back / (CLIFF_DEPTH - 6.0)
        z = top + 2.0 * math.sin(math.pi * s) - 9.0 * s * s
        z += 2.5 * U.noise3(Vector((x * 0.08, y * 0.08, 0.5)), seed=9) - 0.6
        out.append((x, y, z))
    return out


def _face_free(x, z, h=DENSE_FACE_H[1]):
    """May a dense face pine of height ``h`` grow at (x, z)? Not on or under the inscription panel,
    the dressed rock around the gate and balcony (with the stair and the cave), the waterfall chute,
    or the cliff's ends. A cliff pine reaches ~0.45 h out of the face and the concave face turns
    that toward the centre (_face_yaw: out = (-x, ..) / CLIFF_R), so the inscription and the fall
    are kept clear of its crown (~0.3 h across), not only of its foot."""
    if abs(x) > CLIFF_X - 5.0 or z < 12.0 or z > _top(x) - 4.0:
        return False
    cx = x * (1.0 - 0.45 * h / CLIFF_R)            # crown centre x
    if abs(cx - INSC_X) < 4.0 + 0.3 * h and z < 47.0:
        return False
    if -21.0 < x < 15.0 and z < 23.0:
        return False
    return abs(cx - FALL_X) >= 4.5 + 0.3 * h


def _top_free(x, y):
    """May a dense top pine grow at (x, y)? Not in the waterfall's notch and stream or in a pinnacle."""
    if abs(x) > CLIFF_X - 7.0 or abs(x - FALL_X) < 7.0:
        return False
    return all(math.hypot(x - px, y - py) >= pr + 3.0 for px, py, _, pr, _ in PINNACLES)


def dense_pines(coll, root):
    """The density pass on the cliff: DENSE_FACE_PINES cliff pines (DENSE_FACE_H) out of the face and
    Huangshan pines (DENSE_TOP_H) over the top rows at DENSE_TOP_DENSITY, at least DENSE_SPACING
    from each other and the hand-placed pines (_face_free, _top_free). Own generator; every object is
    tagged DENSE_TAG. Returns (face pines, top pines)."""
    r = U.rng(K, "dense_pines")
    taken = [(x, z) for x, z, _ in FACE_PINES]
    face = 0
    for _ in range(DENSE_FACE_PINES * 30):
        if face >= DENSE_FACE_PINES:
            break
        x = r.uniform(-CLIFF_X, CLIFF_X)
        z = 12.0 + (_top(x) - 16.0) * r.random() ** 0.8          # leaning toward the upper face
        h = r.uniform(*DENSE_FACE_H)
        seed = r.randrange(1, 100000)
        if not _face_free(x, z, h) or any(math.hypot(x - a, z - b) < DENSE_SPACING for a, b in taken):
            continue
        taken.append((x, z))
        p = _face_point(x, z)
        if not ABODE_R48:           # (round 48: the draws stay, so the top pines below stand where they stood)
            ob = N.pine(coll, h, seed=seed, style="cliff", name=K + ".dense_cliff_pine", parent=root,
                        location=(p.x, p.y + 0.6, p.z), rotation=_face_yaw(x))
            ob[DENSE_TAG] = "abode"
        face += 1
    # the top rows: the free part of their area (1 m strips, s 0.1-0.9) sets the count
    xs = [x + 0.5 for x in range(-int(CLIFF_X) + 7, int(CLIFF_X) - 7)]
    area = sum((_top_point(x, 0.9) - _top_point(x, 0.1)).length for x in xs if _top_free(x, _top_point(x, 0.5).y))
    want = int(round(area * DENSE_TOP_DENSITY))
    taken = [(x, y) for x, y, _ in _top_pine_points()]
    top = 0
    for _ in range(want * 40):
        if top >= want:
            break
        p = _top_point(r.uniform(-CLIFF_X, CLIFF_X), r.uniform(0.1, 0.9))
        h = r.uniform(*DENSE_TOP_H)
        seed = r.randrange(1, 100000)
        if not _top_free(p.x, p.y) or any(math.hypot(p.x - a, p.y - b) < DENSE_SPACING for a, b in taken):
            continue
        taken.append((p.x, p.y))
        if not (ABODE_R48 and abs(p.x) > R48_TOP_X):     # (the draw stays, so the others stand where they stood)
            ob = N.pine(coll, h, seed=seed, style="huangshan", lod="far", name=K + ".dense_top_pine", parent=root,
                        location=(p.x, p.y, p.z - 0.6))
            ob[DENSE_TAG] = "abode"
        top += 1
    print("ABODE dense pines: face %d of %d, top %d of %d (top rows %.0f m2)"
          % (face, DENSE_FACE_PINES, top, want, area), flush=True)
    return face, top


def _out_dir(x):
    """Unit (x, y) out of the cliff face at x (abode.root's frame): the direction _face_yaw turns -Y to."""
    a = _face_yaw(x)
    return math.sin(a), -math.cos(a)


def r48_old_face_pines():
    """The objects round 48 takes off the cliff face (sect/patch_r48_green.py PARTS=abode hides them): the dense face
    pines, the hand-placed FACE_PINES and the pinnacles' wall pines, and (phase D) the cliff-top pines on the
    shoulders, past |x| R48_TOP_X in abode.root's frame."""
    out = []
    root = bpy.data.objects.get(K + ".root")
    inv = root.matrix_world.inverted() if root is not None else None
    for o in bpy.data.objects:
        nm = o.name
        if nm.startswith(K + ".dense_cliff_pine") or nm.startswith(K + ".cliff_pine") or \
                (nm.startswith(K + ".pinnacle") and ".pine" in nm and o.instance_type == 'COLLECTION'):
            out.append(o)
        elif inv is not None and nm.startswith((K + ".top_pine", K + ".dense_top_pine")) and \
                abs((inv @ o.matrix_world.translation).x) > R48_TOP_X:
            out.append(o)
    return out


def r48_dress(coll, root):
    """Round 48's dressing of the cliff (see ABODE_R48): a rock shelf right of the inscription with two hero
    Huangshan pines leaning out over the drop, fern and shrub strips in R48_FERN_X's joints (only where a plant may
    grow: _face_free), vines from the rim (one mesh, material nature_vine, kept off the inscription and the fall)
    and a shrub shelf left of the fall. Everything is a child of ``root``, named abode.r48_*, tagged R48_TAG =
    'abode'. Returns the objects."""
    if not R48_DRESS:
        print("ABODE round 48 dressing: none (R48_DRESS off; the cliff stays one mass)", flush=True)
        return []
    r = U.rng(K, "r48_dress")
    made = []

    def tag(o):
        o[R48_TAG] = "abode"
        made.append(o)
        return o

    def shelf(x, z_top, width, seed, nm):
        ox, oy = _out_dir(x)
        p = _face_point(x, z_top)
        ob = N.rock(coll, size=width, seed=seed, kind="ledge", name=K + nm, parent=root,
                    location=(p.x - ox * 0.4, p.y - oy * 0.4, z_top), rotation=_face_yaw(x))
        ob.location.z = z_top - float(ob.get("top_z", 0.0))
        return tag(ob), (ox, oy)

    # hero shelf and its two pines
    x, z, w = R48_SHELF
    sh, (ox, oy) = shelf(x, z, w, 48, ".r48_shelf")
    yaw = _face_yaw(x)
    ca, sa = math.cos(yaw), math.sin(yaw)
    depth = w * 0.62
    for along, h, seed in R48_SHELF_PINES:
        lx, ly = along * w, -0.22 * depth                   # on the protruding part of the shelf (local -Y = out)
        px = sh.location.x + ca * lx - sa * ly
        py = sh.location.y + sa * lx + ca * ly
        tag(N.pine(coll, h, seed=seed, style="huangshan", lod="hero", name=K + ".r48_shelf_pine", parent=root,
                   location=(px, py, z - 0.2), lean_toward=math.atan2(oy, ox) + r.uniform(-0.35, 0.35)))
    # the shrub shelf left of the fall
    x2, z2, w2 = R48_SHRUB_SHELF
    sh2, (ox2, oy2) = shelf(x2, z2, w2, 49, ".r48_shrub_shelf")
    yaw2 = _face_yaw(x2)
    c2, s2 = math.cos(yaw2), math.sin(yaw2)
    for k in range(7):
        lx, ly = r.uniform(-0.4, 0.4) * w2, -r.uniform(0.0, 0.3) * w2 * 0.62
        tag(N.shrub(coll, r.uniform(1.4, 2.4), seed=4800 + k, kind="azalea" if k % 3 == 0 else "green",
                    name=K + ".r48_shelf_shrub", parent=root,
                    location=(sh2.location.x + c2 * lx - s2 * ly, sh2.location.y + s2 * lx + c2 * ly, z2 - 0.15)))
    # fern and shrub strips in the joints: runs R48_FERN_RUN m long of 2-3 plants abreast, gaps between them (phase C
    # quick stills: one plant every 1.8 m read as a dotted line up the face, not a green strip)
    for xj in R48_FERN_X:
        z = 13.0 + r.uniform(0.0, 6.0)
        while z < _top(xj) - 6.0:
            run_end = z + r.uniform(*R48_FERN_RUN)
            while z < min(run_end, _top(xj) - 6.0):
                for k in range(r.randint(2, 3)):
                    x = xj + r.uniform(-1.3, 1.3)
                    if _face_free(x, z, h=2.0):
                        p = _face_point(x, z)
                        ox, oy = _out_dir(x)
                        tag(N.shrub(coll, r.uniform(1.1, 2.3), seed=r.randrange(1, 10 ** 5), kind="green",
                                    name=K + ".r48_fern", parent=root,
                                    location=(p.x + ox * 0.15, p.y + oy * 0.15, z + r.uniform(-0.3, 0.3))))
                z += R48_FERN_STEP * r.uniform(0.6, 0.9)
            z += r.uniform(*R48_FERN_GAP)
    # vines from the rim
    bm = bmesh.new()
    x = R48_VINE_X[0]
    n_v = 0
    while x < R48_VINE_X[1]:
        if abs(x - INSC_X) > 7.0 and abs(x - FALL_X) > 7.0 and r.random() > 0.25:
            L = r.uniform(*R48_VINE_LEN)
            w = r.uniform(0.9, 1.8)
            zt = _top(x) - 0.3
            prev = None
            for k in range(5):
                q = k / 4.0
                zz = zt - L * q
                hw = 0.5 * w * (1.0 - 0.7 * q)
                ox, oy = _out_dir(x)
                sx, sy = -oy, ox
                cy = _face_y(x, zz)
                cur = (bm.verts.new((x + sx * hw + ox * 0.35, cy + sy * hw + oy * 0.35, zz)),
                       bm.verts.new((x - sx * hw + ox * 0.35, cy - sy * hw + oy * 0.35, zz)))
                if prev is not None:
                    f = bm.faces.new((prev[0], prev[1], cur[1], cur[0]))
                    f.smooth = True
                prev = cur
            n_v += 1
        x += R48_VINE_X[2] * r.uniform(0.7, 1.3)
    if len(bm.faces):
        tag(U.mesh_from_bmesh(K + ".r48_vines", bm, coll, materials=["nature_vine"], smooth=None, parent=root))
    else:
        bm.free()
    print("ABODE round 48 dressing: %d objects (2 shelf pines, %d vines)" % (len(made), n_v), flush=True)
    return made


def _plants(coll, root, pool):
    # peach blossom trees: a big hero tree beside the balcony stair, smaller ones around the lawn
    N.blossom_tree(coll, 10.0, seed=1, kind="peach", lod="hero", name=K + ".peach", parent=root,
                   location=(-21.5, 11.0, 0))
    N.blossom_tree(coll, 7.5, seed=2, kind="peach", lod="mid", name=K + ".peach", parent=root,
                   location=(pool[0] + 10.0, pool[1] - 5.0, 0))
    N.blossom_tree(coll, 6.0, seed=3, kind="peach", lod="mid", name=K + ".peach", parent=root, location=(-16.0, -12.0, 0))
    N.blossom_tree(coll, 7.0, seed=4, kind="peach", lod="mid", name=K + ".peach", parent=root, location=(16.0, -10.0, 0))
    N.blossom_tree(coll, 6.5, seed=5, kind="peach", lod="mid", name=K + ".peach", parent=root, location=(-1.0, -26.0, 0))
    N.blossom_tree(coll, 6.0, seed=6, kind="peach", lod="mid", name=K + ".peach", parent=root, location=(-15.0, -30.0, 0))
    # bamboo groves framing the plateau left and right
    N.bamboo_clump(coll, 18, 13.0, seed=1, name=K + ".bamboo", parent=root, location=(-33.0, 14.0, 0))
    N.bamboo_clump(coll, 14, 11.0, seed=2, name=K + ".bamboo", parent=root, location=(-28.0, -8.0, 0))
    N.bamboo_clump(coll, 12, 10.0, seed=4, name=K + ".bamboo", parent=root, location=(-25.0, 22.0, 0))
    N.bamboo_clump(coll, 14, 12.0, seed=3, name=K + ".bamboo", parent=root, location=(32.0, 4.0, 0))
    N.bamboo_clump(coll, 10, 10.0, seed=5, name=K + ".bamboo", parent=root, location=(37.0, -18.0, 0))
    # cliff pines growing out of the face (round 48: none, ABODE_R48), pines on the cliff top
    for k, (x, z, h) in enumerate(() if ABODE_R48 else FACE_PINES):
        p = _face_point(x, z)
        N.pine(coll, h, seed=k, style="cliff", name=K + ".cliff_pine", parent=root,
               location=(p.x, p.y + 0.6, p.z), rotation=_face_yaw(x))
    for k, (x, y, z) in enumerate(_top_pine_points()):
        if ABODE_R48 and abs(x) > R48_TOP_X:
            continue
        N.pine(coll, 10.0 + 2.0 * (k % 2), seed=k + 2, style="huangshan", name=K + ".top_pine", parent=root,
               location=(x, y, z))
    dense_pines(coll, root)
    # rocks and shrubs (kept off the west path and the koi-pool flagstones)
    for k, (x, y, s) in enumerate(((pool[0] - 7.5, pool[1] + 1.0, 2.6), (pool[0] + 6.5, pool[1] + 3.5, 3.2),
                                    (-13.0, 11.0, 2.0), (-2.0, -0.5, 1.6), (20.0, -10.0, 2.2))):
        N.rock(coll, s, seed=k, name=K + ".rock", parent=root, location=(x, y, -0.1))
    N.rock(coll, 3.2, seed=1, kind="scholar", name=K + ".scholar_rock", parent=root, location=(-14.0, -3.0, 0))
    for k, (x, y) in enumerate(((-12.0, 4.0), (-4.0, -3.0), (-22.0, -5.0), (pool[0] - 8.0, pool[1] - 4.0),
                                 (12.0, -6.0))):
        N.shrub(coll, 1.8, seed=k, kind="azalea" if k % 2 else "green", name=K + ".shrub", parent=root,
                location=(x, y, 0))


# --- The Smiling, Proud Wanderer duet 笑傲江湖 ----------------------------------------------------
# Wanderer ch. 7 授谱: by a waterfall at night (its roar hides the music) Qu Yang 曲洋 of the Sun Moon Holy Sect plays a
# seven-string qin and Liu Zhengfeng 刘正风 of Hengshan an end-blown xiao: the duet the novel is named for. Mo Da 莫大
# steps out playing his mournful huqin, kills with the thin sword he keeps inside it and walks off playing. Here the
# duet has just ended and the players have walked off: a low stone qin table 琴台 on the lawn at the koi pool's west
# rim with the black Zhongni-style guqin resting on it (its pegs and tassels over the right end, its goose feet over
# the left end, as a qin lies on its table), the aged-bamboo xiao laid across its strings, two stone drum stools where
# the two men sat (the qin player's in front of the table facing the pool and the falls, the xiao player's at the
# left end), and Mo Da's huqin leaning on the table's front edge, its bow hanging from the strings to the lawn and a
# sword hilt where the neck enters the box. The table's front apron carries the sect's sun-and-moon 日月 (明) emblem: a
# gold sun disc and a white-jade crescent. Everything stands on the lawn (abode._lawn_sampler, bases sunk a few cm),
# nothing floats. Static, no hotspot.
#
# Scale: the instruments are modelled at 2.5x life (the huqin 2.4x, shown at HQ_SCALE of that) and the table and
# stools at the same 2.5x of a low floor-sitting qin table (life 0.8 x 0.4 x 0.42 m); DUET_SCALE 1.25 on top makes the
# set a large white-marble garden table with drum stools (2.5 x 1.25 x 1.3 m, stools 0.75 m) and the qin 3.75 m long:
# ~80 px wide in the 1380 hold at 1600x900. At 1.0 the grey-stone set read as a small dark block under the balcony.
# White marble (the balcony stair's) is what reads there against the dark lawn, with the black qin on top.
#
# Placement: the only lawn by the pool that the 1380 hold camera shows is its west side (the south rim lies along the
# frame's bottom edge, behind the foreground peach). Round 34 (r31 proposal, approved): the set is the object of the
# personal fact 'Plays drums and piano' (export_web ABODE_FACTS[3]), so it grows from DUET_SCALE 1.25 to 1.5 and
# steps 2 m out from under the balcony onto the open lawn, along the koi flagstones' line toward the path (it keeps
# its distance from them, 1.4 m and more from the stones and the ledge, 2 m from the plunge mist's box
# abode.waterfall.mist x 6.6..23.4, y 13.5..29.9 m, 2 m from the stilts), on flat lawn (z 0.01-0.07), ~74 m from the
# hold camera with nothing in between; and DUET_YAW turns it 10 deg more to the camera (its front about 4 deg off square
# to the camera's line of sight; it was 12). Round 5's place: DUET_LOC_R5, DUET_YAW_R5, DUET_SCALE_R5
# (sect/patch_r34_west.py recognises the old set by them).
#
# Every part is a closed solid with outward winding (bake_web.facing_flip / _closed_faces treat the pieces as
# closed), built as plain lists (_DGeo) so a plain-Python check can test it without Blender.
#
# Frame of the empty abode.duet (DUET_LOC, z 0, turned DUET_YAW): x = the table's long axis (the qin's head end +x, to
# the hold camera's right), y = away from the camera (toward the balcony stilts), z up.
DUET = K + ".duet"
DUET_ITEM = "wanderer_duet"           # obj['sect_item'] on every object of the group (sect/patch_r5_duet.py)
DUET_LOC = (-0.2, 13.29)              # in abode.root's frame; the empty sits at z 0
DUET_YAW = math.radians(35.0)
DUET_SCALE = 1.5                      # uniform scale of the abode.duet empty
DUET_LOC_R5, DUET_YAW_R5, DUET_SCALE_R5 = (1.35, 14.55), math.radians(25.0), 1.25   # rounds 5-33
DUET_TRI_CAP = 8000                   # per object (export keeps full detail up to here inside the hold's reach)
DUET_SMOOTH = math.radians(35.0)      # edges sharper than this stay hard
DUET_CLEAR = (-2.4, 2.3, -1.75, 0.65)  # duet frame (x0, x1, y0, y1) round every part: the garden scatter keeps off it

QIN_LEN = 3.0
QIN_EDGE = 0.06                       # side wall height where the arched top starts; flat back at z = 0
QIN_OUTLINE = ((0.0, 0.196), (0.008, 0.212), (0.025, 0.22), (0.30, 0.22), (0.32, 0.205), (0.46, 0.205),
               (0.48, 0.222), (0.55, 0.236), (0.62, 0.244), (0.70, 0.249), (0.80, 0.25), (1.30, 0.246),
               (1.90, 0.236), (1.92, 0.21), (2.20, 0.21), (2.22, 0.229), (2.40, 0.228), (2.80, 0.226),
               (2.95, 0.225), (2.975, 0.219), (2.992, 0.21), (3.0, 0.195))   # (u from the head end, half width):
                                      # Zhongni 仲尼式 squared recesses at the neck 项 and the waist 腰
QIN_CROWN = ((0.0, 0.150), (0.5, 0.160), (2.4, 0.160), (3.0, 0.148))       # (u, top of the arch)
QIN_TAIL_U = 2.95                     # dark hardwood tail piece 焦尾 from here to the end
QIN_BRIDGE_U, QIN_BRIDGE_H = 0.125, 0.035   # 岳山: the raised bridge at the head, apex u and height over the top
QIN_GUM_U, QIN_GUM_H = 2.93, 0.025          # 龙龈: the dragon gums at the tail
QIN_STR_R = (0.008, 0.0077, 0.0073, 0.007, 0.0066, 0.0063, 0.006)   # silk string radii, first (thickest) to seventh
QIN_STR_HEAD, QIN_STR_TAIL = 0.13, 0.09     # half span of the seven strings at the bridge / at the gums
QIN_HUI = (1 / 8, 1 / 6, 1 / 5, 1 / 4, 1 / 3, 2 / 5, 1 / 2, 3 / 5, 2 / 3, 3 / 4, 4 / 5, 5 / 6, 7 / 8)
QIN_HUI_R = 0.035                     # 徽: white jade studs, outside the first string (the far side, +y)
QIN_PEG_U = 0.085                     # 琴轸 under the head, one per string, each with a short red tassel
QIN_FOOT_U = 2.28                     # 雁足: the two goose-feet pegs under the tail half

XIAO_LEN, XIAO_R, XIAO_SIDES = 2.0, 0.05, 12  # 1:20 slender (a fatter tube read as a bamboo pole)
XIAO_NODES = (0.16, 0.58, 1.00, 1.42, 1.84)   # from the blowing end: object z = 0.84, 0.42, 0, ... (bamboo_stalk
                                               # paints its node rings every 0.42 m of object z; these sit on them)
XIAO_HOLES = ((1.06, 6), (1.12, 0), (1.23, 0), (1.34, 0), (1.52, 0), (1.63, 0))   # (s, ring column): five finger
                                               # holes facing the qin's top, the thumb hole on the back
XIAO_BORE = 0.034
# aged honey bamboo for the xiao (bamboo_stalk's node rings and streaks, the live green/yellow swapped for the brown
# of an old instrument: the lime of a fresh stalk made it look like a plastic tube)
DUET_XIAO_MAT = M.variant("abode_xiao_bamboo", "bamboo_stalk", green="#7a5530", yellow="#a8804a")
XIAO_CROSS = math.radians(20.0)       # to the qin's long axis: blowing end to the back right, tassel end to the front
XIAO_C = (-0.15, 0.0)                 # (qin frame) where its axis crosses the qin's: it lies on the strings there
XIAO_RIDGE = 0.008                    # its raised nodes stand this far out of the tube (kept clear of the strings)

# Mo Da's huqin leans on the table's front edge right of the qin player's stool, its neck tilted HQ_LEAN back onto
# the edge, its box (skin to the left) clear of the table, its bow hanging from the strings down to the lawn
HQ_SCALE = 0.85                       # of the modelled huqin: 2.2 m tall in the duet frame, 2.5x life like the qin
HQ_AT_X = 0.88                        # duet x where its neck meets the table's front edge
HQ_LEAN = math.radians(14.0)          # from the vertical, toward the table
HQ_FOOT_SINK = 0.01                   # its foot's lowest corner this far into the lawn
HQ_BOW_REST = 0.004                   # the bow's lowest point this far above the lawn (resting on the grass)
HQ_BOX_R = 0.35 / math.sqrt(3.0)      # hexagon circumradius (0.35 m across the flats)
HQ_BOX_L = 0.42
HQ_NECK_Y, HQ_NECK_R = 0.10, 0.026    # the neck pierces the box behind its centre (the skin is at -y)

# stone qin table 琴台 (white marble), duet frame, centred on the origin: top slab with an ice-plate edge, two tapered
# end-slab legs on plinths, front and back aprons; the qin's frame origin (middle of its flat back) sits on the top at
# TABLE_QIN, so its pegs (x +1.10) clear the right end and its goose feet (x -1.10) the left end by 7 cm
TABLE_L, TABLE_D, TABLE_H, TABLE_T = 2.0, 1.0, 1.05, 0.2   # top: length, depth, height over the lawn, thickness
TABLE_LEG_X, TABLE_LEG_T, TABLE_LEG_D = 0.72, 0.22, 0.84   # leg slabs: centre |x|, thickness (x), depth (y), at the top
TABLE_PLINTH = (0.36, 0.96, 0.12)    # leg plinths: x, y, height (half of it under the lawn)
TABLE_APRON_H, TABLE_APRON_T, TABLE_APRON_IN = 0.2, 0.07, 0.08   # aprons: height, thickness, inset from the top's edge
TABLE_SINK = 0.06                     # legs and plinths reach this far under the lawn's lowest point beneath them
TABLE_QIN = (-0.32, 0.08)
EMBLEM_X, EMBLEM_R = 0.36, 0.058      # sun-and-moon emblem on the front apron: centre x, sun radius (moon right of it),
EMBLEM_INLAY = (0.36, 0.15)           # on a dark slate inlay (length, height) so it reads on the marble
# stone drum stools 石鼓墩 (white marble): (x, y) in the duet frame
SEAT_R, SEAT_H, SEAT_SINK = 0.47, 0.6, 0.05
SEAT_QIN = (-0.22, -1.13)             # in front of the qin's middle, facing the pool
SEAT_XIAO = (-1.8, -0.42)             # at the left end, beside the qin player


def _dsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dadd(a, b, s=1.0):
    return (a[0] + b[0] * s, a[1] + b[1] * s, a[2] + b[2] * s)


def _ddot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _dcross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dnorm(a):
    n = math.sqrt(_ddot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else (0.0, 0.0, 1.0)


def _drot(axis, a):
    """3x3 rotation (rows) about 'x', 'y' or 'z'."""
    c, s = math.cos(a), math.sin(a)
    if axis == "x":
        return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))
    if axis == "y":
        return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))
    return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))


def _dmm(A, B):
    return tuple(tuple(sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def _dmv(A, v):
    return tuple(A[i][0] * v[0] + A[i][1] * v[1] + A[i][2] * v[2] for i in range(3))


def _dT(A):
    return tuple(tuple(A[j][i] for j in range(3)) for i in range(3))


def _dcols(cx, cy, cz):
    """3x3 matrix (rows) with these columns (images of the local x, y, z axes)."""
    return tuple((cx[i], cy[i], cz[i]) for i in range(3))


def _dframe(origin, axis, ref=(1.0, 0.0, 0.0)):
    """Point map for a part built about its own z axis: local z -> ``axis``, local x -> ``ref`` made square to it."""
    a = _dnorm(axis)
    x = _dsub(ref, tuple(a[k] * _ddot(ref, a) for k in range(3)))
    if math.sqrt(_ddot(x, x)) < 1e-6:
        x = _dsub((0.0, 1.0, 0.0), tuple(a[k] * a[1] for k in range(3)))
    x = _dnorm(x)
    y = _dcross(a, x)

    def f(p):
        return tuple(origin[k] + x[k] * p[0] + y[k] * p[1] + a[k] * p[2] for k in range(3))
    return f


def _table(tab, u):
    """Piecewise-linear lookup in ((u, value), ...)."""
    if u <= tab[0][0]:
        return tab[0][1]
    for (u0, v0), (u1, v1) in zip(tab[:-1], tab[1:]):
        if u <= u1:
            return v0 + (v1 - v0) * (u - u0) / (u1 - u0) if u1 > u0 else v1
    return tab[-1][1]


class _DGeo:
    """Mesh as plain lists (no bpy): vertices, faces with a material role and a smooth flag, and parts. Each part is a
    closed solid; end() turns its faces outward from its signed volume."""

    def __init__(self):
        self.verts, self.faces, self.mat, self.smooth = [], [], [], []
        self.parts = []                  # (name, first face, end face)
        self._cur = None

    def v(self, p):
        self.verts.append((float(p[0]), float(p[1]), float(p[2])))
        return len(self.verts) - 1

    def face(self, idx, mat, smooth=True):
        """A face; a quad bent more than 0.5 mm out of plane (the xiao's notched rim) is split along its shorter
        diagonal, so Blender's own triangulation cannot pick the other one."""
        if len(idx) == 4:
            P = [self.verts[i] for i in idx]
            n = _dcross(_dsub(P[2], P[0]), _dsub(P[3], P[1]))
            ln = math.sqrt(_ddot(n, n))
            if ln > 1e-12 and max(abs(_ddot(_dsub(p, P[0]), n)) / ln for p in P) > 5e-4:
                a, b, c, d = idx
                if _ddot(_dsub(P[2], P[0]), _dsub(P[2], P[0])) <= _ddot(_dsub(P[3], P[1]), _dsub(P[3], P[1])):
                    tris = ((a, b, c), (a, c, d))
                else:
                    tris = ((a, b, d), (b, c, d))
                for t in tris:
                    self.faces.append(t)
                    self.mat.append(mat)
                    self.smooth.append(bool(smooth))
                return
        self.faces.append(tuple(idx))
        self.mat.append(mat)
        self.smooth.append(bool(smooth))

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
        V, vol = self.verts, 0.0
        for f in self.faces[f0:f1]:
            a = V[f[0]]
            for k in range(1, len(f) - 1):
                vol += _ddot(a, _dcross(V[f[k]], V[f[k + 1]]))
        return vol / 6.0

    def tris(self):
        return sum(len(f) - 2 for f in self.faces)

    def loft(self, rings, mat, caps=(True, True), cap_mat=(None, None), smooth=True, skip=()):
        """Quads between consecutive closed rings of equal length (row r joins ring r and r + 1, column c joins point
        c and c + 1), n-gon caps. mat: role or f(row, col). skip: {(row, col)} quads left for the caller (holes).
        Returns the ring vertex ids. The caller brackets it with begin()/end()."""
        ids = [[self.v(p) for p in ring] for ring in rings]
        n = len(rings[0])
        for r in range(len(ids) - 1):
            a, b = ids[r], ids[r + 1]
            for c in range(n):
                if (r, c) in skip:
                    continue
                c2 = (c + 1) % n
                self.face((a[c], a[c2], b[c2], b[c]), mat(r, c) if callable(mat) else mat, smooth)
        first = mat(0, 0) if callable(mat) else mat
        last = mat(len(ids) - 2, 0) if callable(mat) else mat
        if caps[0]:
            self.face(tuple(reversed(ids[0])), cap_mat[0] or first, smooth)
        if caps[1]:
            self.face(tuple(ids[-1]), cap_mat[1] or last, smooth)
        return ids

    def solid(self, name, rings, mat, **kw):
        self.begin(name)
        ids = self.loft(rings, mat, **kw)
        self.end()
        return ids

    def lathe(self, name, rows, segs, mat, xf, phase=0.0, smooth=True):
        """Revolve rows (r, h[, sy]) about the local z axis; xf maps local points. r = 0 on the first or last row is a
        pole, otherwise that end is capped. mat: role or f(row)."""
        self.begin(name)
        rings = []
        for row in rows:
            r, h = row[0], row[1]
            sy = row[2] if len(row) > 2 else 1.0
            if r <= 1e-9:
                rings.append([self.v(xf((0.0, 0.0, h)))])
                continue
            rings.append([self.v(xf((r * math.cos(phase + 2 * math.pi * k / segs),
                                     r * sy * math.sin(phase + 2 * math.pi * k / segs), h))) for k in range(segs)])
        for i in range(len(rings) - 1):
            a, b = rings[i], rings[i + 1]
            m = mat(i) if callable(mat) else mat
            for k in range(segs):
                k2 = (k + 1) % segs
                if len(a) == 1 and len(b) == 1:
                    continue
                if len(a) == 1:
                    self.face((a[0], b[k2], b[k]), m, smooth)
                elif len(b) == 1:
                    self.face((a[k], a[k2], b[0]), m, smooth)
                else:
                    self.face((a[k], a[k2], b[k2], b[k]), m, smooth)
        if len(rings[0]) > 1:
            self.face(tuple(reversed(rings[0])), mat(0) if callable(mat) else mat, smooth)
        if len(rings[-1]) > 1:
            self.face(tuple(rings[-1]), mat(len(rings) - 2) if callable(mat) else mat, smooth)
        self.end()
        return rings

    def tube(self, name, pts, sides, mat, smooth=True):
        """Tube through (x, y, z, r) points, straight between them (parallel-transport frames), both ends capped."""
        P = [tuple(p[:3]) for p in pts]
        n = len(P)
        tans = []
        for i in range(n):
            if i == 0:
                t = _dsub(P[1], P[0])
            elif i == n - 1:
                t = _dsub(P[-1], P[-2])
            else:
                t = _dadd(_dnorm(_dsub(P[i], P[i - 1])), _dnorm(_dsub(P[i + 1], P[i])))
            tans.append(_dnorm(t))
        ref = (0.0, 0.0, 1.0) if abs(tans[0][2]) < 0.9 else (1.0, 0.0, 0.0)
        u = _dnorm(_dcross(tans[0], ref))
        rings = []
        for i in range(n):
            t = tans[i]
            u = _dnorm(_dsub(u, tuple(t[k] * _ddot(u, t) for k in range(3))))
            w = _dcross(t, u)
            r = pts[i][3]
            rings.append([tuple(P[i][k] + (u[k] * math.cos(2 * math.pi * j / sides) +
                                          w[k] * math.sin(2 * math.pi * j / sides)) * r for k in range(3))
                          for j in range(sides)])
        return self.solid(name, rings, mat, smooth=smooth)

    def torus(self, name, R, r, nu, nv, mat, xf, phase=0.0):
        """Ring round the local z axis (in the local xy plane); xf maps local points."""
        rings = []
        for i in range(nu):
            a = 2 * math.pi * i / nu
            d = (math.cos(a), math.sin(a))
            rings.append([xf((d[0] * (R + r * math.cos(phase + 2 * math.pi * j / nv)),
                              d[1] * (R + r * math.cos(phase + 2 * math.pi * j / nv)),
                              r * math.sin(phase + 2 * math.pi * j / nv))) for j in range(nv)])
        self.begin(name)
        ids = [[self.v(p) for p in ring] for ring in rings]
        for i in range(nu):
            a, b = ids[i], ids[(i + 1) % nu]
            for j in range(nv):
                j2 = (j + 1) % nv
                self.face((a[j], b[j], b[j2], a[j2]), mat)
        self.end()

    def box(self, name, c, size, mat, xf=None, smooth=False):
        hx, hy, hz = size[0] / 2.0, size[1] / 2.0, size[2] / 2.0
        f = xf or (lambda p: p)

        def p(x, y, z):
            return f((c[0] + x, c[1] + y, c[2] + z))
        rings = [[p(hx, -hy, -hz), p(hx, hy, -hz), p(-hx, hy, -hz), p(-hx, -hy, -hz)],
                 [p(hx, -hy, hz), p(hx, hy, hz), p(-hx, hy, hz), p(-hx, -hy, hz)]]
        return self.solid(name, rings, mat, smooth=smooth)


def _qin_hw(u):
    return _table(QIN_OUTLINE, u)


def _qin_top_wz(w, zc, y):
    a = w - 0.016
    t = min(1.0, abs(y) / a)
    return QIN_EDGE + 0.004 + (zc - QIN_EDGE - 0.004) * (1.0 - t * t)


def qin_top(u, y):
    """Height of the qin's arched top at (u from the head end, y)."""
    return _qin_top_wz(_qin_hw(u), _table(QIN_CROWN, u), y)


def _qin_x(u):
    return QIN_LEN * 0.5 - u


def _qin_ring(u):
    """Cross-section at u: flat back, rounded side walls, arched top (19 points, around from the bottom left)."""
    w, zc = _qin_hw(u), _table(QIN_CROWN, u)
    side = [(-w + 0.018, 0.0), (-w + 0.004, 0.005), (-w, 0.02), (-w, QIN_EDGE - 0.012), (-w + 0.005, QIN_EDGE - 0.002)]
    a = w - 0.016
    top = [(-a + 2.0 * a * k / 8, _qin_top_wz(w, zc, -a + 2.0 * a * k / 8)) for k in range(9)]
    pts = side + top + [(-y, z) for y, z in reversed(side)]
    return [(_qin_x(u), y, z) for y, z in pts]


def qin_strings():
    """[(bridge (u, y, z), gums (u, y, z))] of the seven strings' centre lines where they rest, first string (+y,
    the far side) first."""
    out = []
    for i in range(7):
        yb = QIN_STR_HEAD - i * 2.0 * QIN_STR_HEAD / 6.0
        yg = QIN_STR_TAIL - i * 2.0 * QIN_STR_TAIL / 6.0
        r = QIN_STR_R[i]
        out.append(((QIN_BRIDGE_U, yb, qin_top(QIN_BRIDGE_U, yb) + QIN_BRIDGE_H + r),
                    (QIN_GUM_U, yg, qin_top(QIN_GUM_U, yg) + QIN_GUM_H + r)))
    return out


def duet_down():
    """World down in the duet frame (tassels hang along it; the group stands level)."""
    return (0.0, 0.0, -1.0)


def duet_qin_geo():
    """Zhongni-style guqin 古琴, 2.5x: 3 m long, head end at +x, top +z, origin at the middle of its flat back."""
    g = _DGeo()
    us = sorted({u for u, _ in QIN_OUTLINE} | {u for u, _ in QIN_CROWN})
    g.solid("body", [_qin_ring(u) for u in us],
            lambda r, c: "trim" if us[r] >= QIN_TAIL_U - 1e-9 else "body", cap_mat=("body", "trim"))
    # 岳山 bridge and 龙龈 dragon gums: hardwood ridges across the top, sunk into it, following its arch
    for name, u0, half, n, sect in (
            ("bridge", QIN_BRIDGE_U, 0.20, 9, ((-0.030, -0.02), (-0.025, 0.022), (-0.015, 0.033), (0.0, QIN_BRIDGE_H),
                                              (0.013, 0.028), (0.02, -0.02))),
            ("gums", QIN_GUM_U, 0.13, 7, ((-0.03, -0.02), (-0.024, 0.015), (-0.01, QIN_GUM_H), (0.0, QIN_GUM_H),
                                         (0.012, 0.018), (0.02, -0.02)))):
        rings = []
        for j in range(n):
            y = -half + 2.0 * half * j / (n - 1)
            z0 = qin_top(u0, y)
            rings.append([(_qin_x(u0 + du), y, z0 + dz) for du, dz in sect])
        g.solid(name, rings, "trim")
    # seven silk strings: from the string holes behind the bridge, over the bridge and the gums, into the tail
    for i, (b, c) in enumerate(qin_strings()):
        a = (0.065, b[1], qin_top(0.065, b[1]) - 0.006)
        d = (2.975, c[1], qin_top(2.975, c[1]) - 0.006)
        g.tube("string.%d" % i, [(_qin_x(p[0]), p[1], p[2], QIN_STR_R[i]) for p in (a, b, c, d)], 6, "string")
    # thirteen hui 徽: jade studs set into the top outside the first string, at the harmonic nodes of the strings
    (ub, yb0, _), (ug, yg0, _) = qin_strings()[0]
    e = 0.002
    for k, f in enumerate(QIN_HUI):
        u = ub + f * (ug - ub)
        ys1 = yb0 + (yg0 - yb0) * (u - ub) / (ug - ub)
        w = _qin_hw(u)
        y = min(0.5 * (ys1 + w), w - 0.05)
        zx = -(qin_top(u + e, y) - qin_top(u - e, y)) / (2 * e)      # x = QIN_LEN / 2 - u
        zy = (qin_top(u, y + e) - qin_top(u, y - e)) / (2 * e)
        n_ = _dnorm((-zx, -zy, 1.0))
        g.lathe("hui.%d" % k, ((QIN_HUI_R, -0.006), (QIN_HUI_R, 0.003)), 8, "hui",
                _dframe((_qin_x(u), y, qin_top(u, y)), n_), phase=math.pi / 8)
    # 琴轸 tuning pegs under the head, one per string, each with a short red tassel hanging straight down (world)
    down = duet_down()
    for i, (b, _c) in enumerate(qin_strings()):
        x, y = _qin_x(QIN_PEG_U), b[1]
        g.lathe("peg.%d" % i, ((0.016, -0.006), (0.02, 0.05), (0.016, 0.075), (0.0, 0.08)), 6, "trim",
                _dframe((x, y, 0.0), (0.0, 0.0, -1.0)))
        g.lathe("tassel.%d" % i, ((0.006, -0.012), (0.006, 0.045), (0.016, 0.06), (0.010, 0.076), (0.02, 0.19),
                                  (0.0, 0.2)), 6, "tassel", _dframe((x, y, -0.074), down))
    # 雁足 the two goose-feet pegs under the tail half
    for i, y in enumerate((-0.075, 0.075)):
        g.lathe("goose_foot.%d" % i, ((0.028, -0.006), (0.03, 0.02), (0.022, 0.065), (0.03, 0.095), (0.0, 0.1)), 8,
                "trim", _dframe((_qin_x(QIN_FOOT_U), y, 0.0), (0.0, 0.0, -1.0)))
    return g


def _xiao_radius(s):
    """Outer radius of the xiao at s (m from its blowing end): the tube, its raised nodes and the thicker bottom end."""
    pts = [(0.0, XIAO_R)]
    for n in XIAO_NODES:
        pts += [(n - 0.012, XIAO_R), (n, XIAO_R + XIAO_RIDGE), (n + 0.012, XIAO_R)]
    pts += [(1.93, XIAO_R + 0.002), (XIAO_LEN, XIAO_R + 0.005)]
    return _table(sorted(pts), s)


def xiao_rest_z():
    """Height (qin frame) of the xiao's axis lying across the strings at XIAO_CROSS through XIAO_C: the tube's lowest
    edge (a 12-gon: cos 15 deg of its radius under the axis) on the highest string where it crosses one."""
    cx, cy = XIAO_C
    dx, dy = math.cos(XIAO_CROSS), math.sin(XIAO_CROSS)
    best = -1e9
    for ((ub, yb, zb), (ug, yg, zg)), r in zip(qin_strings(), QIN_STR_R):
        bx, gx = _qin_x(ub), _qin_x(ug)
        ex, ey = gx - bx, yg - yb                       # string direction (plan), bridge to gums
        wx, wy = bx - cx, yb - cy
        det = -dx * ey + dy * ex
        t = (-wx * ey + wy * ex) / det                  # along the xiao from XIAO_C
        u = (dx * wy - dy * wx) / det                   # along the string from the bridge (0..1)
        if not 0.0 <= u <= 1.0:
            continue
        zs = zb + (zg - zb) * u + r                     # top of the string there
        s_x = XIAO_LEN * 0.5 - t                        # m from the blowing end (local +z = the blowing end)
        best = max(best, zs + _xiao_radius(s_x) * math.cos(math.pi / XIAO_SIDES))
    return best


def duet_xiao_geo():
    """Bamboo xiao 洞箫, 2.5x: 2 m long along local z (blowing end +z), finger holes facing local +x, the U-notch
    mouthpiece cut on the same side, raised nodes on the painted node rings (abode_xiao_bamboo, a bamboo_stalk
    variant: same 0.42 m spacing), open bores at both ends, a red
    silk tassel on a cord loop near the bottom end."""
    g = _DGeo()
    n = XIAO_SIDES
    phis = [-math.pi / n + 2 * math.pi * k / n for k in range(n)]    # column 0 is centred on +x, column n/2 on -x

    def z_of(s):
        return XIAO_LEN * 0.5 - s

    def ring(s, r, notch=False):
        out = []
        for phi in phis:
            ds = 0.0
            if notch:               # U-notch 吹口 in the rim over the front (+x): two vertices deep, two shallow
                c = math.cos(phi)
                ds = 0.045 if c > 0.95 else (0.014 if c > 0.6 else 0.0)
            out.append((r * math.cos(phi), r * math.sin(phi), z_of(s + ds)))
        return out
    stations = [(0.0, XIAO_R)]
    for s in XIAO_NODES:
        stations += [(s - 0.012, XIAO_R), (s, XIAO_R + 0.008), (s + 0.012, XIAO_R)]
    for s, _c in XIAO_HOLES:
        stations += [(s - 0.016, XIAO_R), (s + 0.016, XIAO_R)]
    stations += [(1.93, XIAO_R + 0.002), (XIAO_LEN, XIAO_R + 0.005)]
    stations.sort()
    top_bore = [ring(0.30, XIAO_BORE), ring(0.07, XIAO_BORE), ring(0.0, XIAO_BORE, notch=True)]
    outer = [ring(s, r, notch=(s == 0.0)) for s, r in stations]
    bot_bore = [ring(XIAO_LEN, XIAO_BORE), ring(XIAO_LEN - 0.07, XIAO_BORE), ring(XIAO_LEN - 0.2, XIAO_BORE)]
    rings = top_bore + outer + bot_bore
    off = len(top_bore)
    holes = []
    for s, col in XIAO_HOLES:
        r = off + next(i for i, (s_, _r) in enumerate(stations) if abs(s_ - (s - 0.016)) < 1e-9)
        holes.append((r, col))
    g.begin("tube")
    ids = g.loft(rings, "body", skip=set(holes))
    for r, c in holes:              # round finger holes: an octagon in the skipped quad, a pocket into the wall
        a, b = ids[r], ids[r + 1]
        p = [a[c], a[(c + 1) % n], b[(c + 1) % n], b[c]]
        P = [g.verts[i] for i in p]
        cen = tuple(sum(q[k] for q in P) / 4.0 for k in range(3))
        rad = _dnorm((cen[0], cen[1], 0.0))

        def at(s, t):               # bilinear point of the (flat) quad: s from p0 to p1, t from p0 to p3
            lo = _dadd(P[0], _dsub(P[1], P[0]), s)
            hi = _dadd(P[3], _dsub(P[2], P[3]), s)
            return _dadd(lo, _dsub(hi, lo), t)
        e = [g.v(at(0.5 + 0.38 * math.cos(math.radians(-135 + 45 * k)),
                    0.5 + 0.38 * math.sin(math.radians(-135 + 45 * k)))) for k in range(8)]
        d = [g.v(_dadd(g.verts[i], rad, -(0.03 + _ddot(_dsub(g.verts[i], cen), rad)))) for i in e]
        for i in range(4):          # rim: a quad along each side of the quad, a triangle at each corner
            g.face((p[i], p[(i + 1) % 4], e[(2 * i + 2) % 8], e[2 * i + 1]), "body")
            g.face((p[i], e[2 * i + 1], e[2 * i]), "body")
        for k in range(8):
            g.face((e[k], e[(k + 1) % 8], d[(k + 1) % 8], d[k]), "body")
        g.face(tuple(d), "body")
    g.end()
    # red silk tassel: a cord loop round the tube near the bottom end, the tassel hanging straight down (world)
    zl = z_of(1.90)
    g.torus("loop", XIAO_R + 0.006, 0.006, 12, 3, "tassel", lambda p: (p[0], p[1], zl + p[2]))
    dn = _dmv(_dT(xiao_rotation()), duet_down())
    side = _dnorm((dn[0], dn[1], 0.0))
    start = (side[0] * (XIAO_R + 0.008), side[1] * (XIAO_R + 0.008), zl)
    g.lathe("tassel", ((0.008, -0.012), (0.007, 0.07), (0.022, 0.09), (0.013, 0.11), (0.04, 0.30), (0.0, 0.31)),
            6, "tassel", _dframe(start, dn))
    return g


def xiao_rotation():
    """xiao object rotation in the duet frame: its axis (local z) along the qin's top at XIAO_CROSS to the qin, its
    finger holes (local +x) facing the qin's top (+z)."""
    cz = (math.cos(XIAO_CROSS), math.sin(XIAO_CROSS), 0.0)
    cx = (0.0, 0.0, 1.0)
    return _dcols(cx, _dcross(cz, cx), cz)


def _flat(x, y):
    return 0.0


def huqin_rotation():
    """huqin object rotation in the duet frame: its neck (local z) leaning HQ_LEAN back toward the table (+y), its box
    axis (local y, bow side) along +x, so the skin (local -y) faces left and the pegs stick out to the left."""
    s, c = math.sin(HQ_LEAN), math.cos(HQ_LEAN)
    return _dcols((0.0, -c, s), (1.0, 0.0, 0.0), (0.0, s, c))


def _hq_neck_r(s):
    return _table(((0.18, HQ_NECK_R), (1.0, 0.024), (1.9, 0.022)), s)


def huqin_place(lawn=None):
    """(location, rotation) of the huqin in the duet frame: its foot's lowest corner HQ_FOOT_SINK into the lawn, its
    neck resting on the table's front edge (the top slab's upright face ends 3.5 cm under its top) at x HQ_AT_X."""
    lawn = lawn or _flat
    k, ny = HQ_SCALE, HQ_NECK_Y
    s, c = math.sin(HQ_LEAN), math.cos(HQ_LEAN)
    z_e = lawn(0.0, 0.0) + TABLE_H - 0.035
    y_e = -TABLE_D * 0.5
    ox = HQ_AT_X - k * ny
    foot = (HQ_AT_X, y_e - 0.3)
    oy = oz = 0.0
    for _ in range(4):
        oz = lawn(*foot) - HQ_FOOT_SINK + k * (0.0375 * s + 0.36 * c)
        sc = (z_e - oz) / (k * c)
        oy = y_e - k * _hq_neck_r(sc) / c - k * sc * s
        foot = (ox + k * ny, oy - 0.36 * k * s)
    return (ox, oy, oz), huqin_rotation()


def _hq_to_duet(loc, rot):
    k = HQ_SCALE

    def f(p):
        q = _dmv(rot, p)
        return (loc[0] + k * q[0], loc[1] + k * q[1], loc[2] + k * q[2])
    return f


def huqin_bow_droop(lawn=None):
    """Angle (rad) the bow hangs down from the strings so its far end rests HQ_BOW_REST above the lawn (bisection)."""
    lawn = lawn or _flat
    loc, rot = huqin_place(lawn)
    f = _hq_to_duet(loc, rot)

    def clearance(beta):
        g = duet_huqin_geo(beta)
        ids = set()
        for name, f0, f1 in g.parts:
            if name.startswith("bow_"):
                for fc in g.faces[f0:f1]:
                    ids.update(fc)
        return min(p[2] - lawn(p[0], p[1]) for p in (f(g.verts[i]) for i in ids)) - HQ_BOW_REST
    lo, hi = 0.0, math.radians(70.0)
    if clearance(lo) <= 0.0:
        return lo
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        if clearance(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    return lo


def duet_xforms(lawn=None):
    """{part: (location, 3x3 rotation)} in the duet frame (the huqin's object also scales by HQ_SCALE: duet_layout)."""
    return {k: (v[0], v[1]) for k, v in duet_layout(lawn).items()}


def duet_layout(lawn=None):
    """{part: (location, 3x3 rotation, uniform scale)} in the duet frame. lawn(x, y): the lawn's height under a point
    of the duet frame (duet_lawn: abode._lawn_sampler through the Empty); None = flat at 0."""
    lawn = lawn or _flat
    I = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    z_top = lawn(0.0, 0.0) + TABLE_H
    qx, qy = TABLE_QIN
    out = dict(table=((0.0, 0.0, 0.0), I, 1.0),
               qin=((qx, qy, z_top), I, 1.0),
               xiao=((qx + XIAO_C[0], qy + XIAO_C[1], z_top + xiao_rest_z()), xiao_rotation(), 1.0))
    for key, (sx, sy) in (("seat_qin", SEAT_QIN), ("seat_xiao", SEAT_XIAO)):
        zmin = min([lawn(sx + SEAT_R * math.cos(a), sy + SEAT_R * math.sin(a))
                    for a in [2 * math.pi * i / 12 for i in range(12)]] + [lawn(sx, sy)])
        out[key] = ((sx, sy, zmin - SEAT_SINK), I, 1.0)
    loc, rot = huqin_place(lawn)
    out["huqin"] = (loc, rot, HQ_SCALE)
    return out


def duet_huqin_geo(droop=0.0):
    """Mo Da's huqin 胡琴, 2.4x: origin at the sound box centre, neck along local z, skin at -y. A worn hexagonal box
    with a python-skin face and a carved back window, a long neck through it ending in a curled head, two front pegs,
    two strings over the bridge, held by the 千斤 loop, a horsehair bow threaded between them (hanging ``droop`` rad
    down from the strings about the point where it crosses them, as a bow does when the huqin is set down), and the
    steel hilt and black-wrapped grip of the thin sword hidden inside it, rising out of the box where the neck goes
    in."""
    g = _DGeo()
    R = HQ_BOX_R
    hl = HQ_BOX_L * 0.5

    def hexring(y, s):
        return [(s * R * math.cos(math.pi / 3 * k), y, s * R * math.sin(math.pi / 3 * k)) for k in range(6)]
    g.solid("box", [hexring(-hl, 0.86), hexring(-hl, 0.95), hexring(-hl + 0.012, 1.0), hexring(hl - 0.012, 1.0),
                    hexring(hl, 0.95), hexring(hl, 0.80), hexring(hl - 0.025, 0.80)],
            "wood", cap_mat=("skin", "wrap"))
    ny = HQ_NECK_Y
    g.tube("neck", [(0.0, ny, -0.30, 0.024), (0.0, ny, -0.17, HQ_NECK_R), (0.0, ny, 0.18, HQ_NECK_R), (0.0, ny, 1.0, 0.024),
                    (0.0, ny, 1.90, 0.022), (0.0, ny, 2.06, 0.022), (0.0, ny + 0.02, 2.15, 0.024),
                    (0.0, ny + 0.07, 2.21, 0.026), (0.0, ny + 0.13, 2.235, 0.026), (0.0, ny + 0.17, 2.22, 0.022),
                    (0.0, ny + 0.185, 2.18, 0.016), (0.0, ny + 0.17, 2.15, 0.011)], 8, "wood")
    g.box("foot", (0.0, ny, -0.33), (0.075, 0.07, 0.06), "wood")
    # two pegs 琴轴 through the neck, sticking out to the front (the skin's side)
    pz = (1.98, 1.80)
    for i, z in enumerate(pz):
        g.lathe("peg.%d" % i, ((0.010, -0.045), (0.012, 0.03), (0.014, 0.065), (0.03, 0.085), (0.032, 0.15),
                               (0.022, 0.175), (0.0, 0.18)), 6, "light",
                _dframe((0.0, ny, z), (-0.25, -1.0, 0.0), ref=(0.0, 0.0, 1.0)))
    # bridge 琴码 on the skin; two strings from the pegs, through the 千斤 loop, over the bridge, under the box
    yb = -hl - 0.034
    g.box("bridge", (0.0, -hl - 0.016, -0.02), (0.06, 0.034, 0.03), "light")
    zq = 1.55
    for i, (x, z) in enumerate(((-0.011, pz[0]), (0.011, pz[1]))):
        g.tube("string.%d" % i, [(x, ny - 0.01, z, 0.005), (x, ny - 0.036, zq, 0.005), (x, yb - 0.005, -0.02, 0.005),
                                 (x, -hl + 0.006, -0.135, 0.005)], 5, "steel")
    g.torus("qianjin", 0.036, 0.005, 10, 3, "wrap", lambda p: (p[0], ny - 0.006 + p[1], zq + p[2]))
    # the bow: horsehair threaded between the strings just above the box (it runs along the box's axis, the skin
    # facing the player's right, and passes beside the neck), the bamboo stick arched up and out past the second
    # string, frog end in front of the skin
    zh, ys, k = 0.322, _huqin_string_y(0.322), 0.25

    def bx(y):
        return (y - ys) * k
    cd, sd = math.cos(droop), math.sin(droop)

    def hang(p):                    # about the local x axis through (ys, zh): the far (+y) end goes down
        dy, dz = p[1] - ys, p[2] - zh
        return (p[0], ys + dy * cd + dz * sd, zh - dy * sd + dz * cd)
    y0, y1 = ys - 0.35, ys + 1.55
    g.box("bow_hair", (0.0, 0.0, 0.0), (0.004, y1 - y0, 0.02), "hair",
          xf=lambda p: hang((bx(p[1] + 0.5 * (y0 + y1)) + p[0], p[1] + 0.5 * (y0 + y1), zh + p[2])))
    pts = []
    for j in range(11):
        t = j / 10.0
        y = y0 - 0.02 + (y1 - y0 + 0.04) * t
        a = math.sin(math.pi * t)
        pts.append(hang((bx(y) + 0.065 * a, y, zh + 0.012 + 0.03 * a)) + (0.012 - 0.004 * t,))
    g.tube("bow_stick", pts, 6, "light")
    # Mo Da's sword, drawn a hand's width out of the box top in front of the neck: a sliver of thin blade, the guard,
    # the black-wrapped grip and the pommel (0.35 m out of the box); the rest of the blade is hidden inside
    top = R * math.sin(math.pi / 3)
    hf = _dframe((-0.04, -0.05, top), (0.0, math.sin(math.radians(10.0)), math.cos(math.radians(10.0))))
    g.box("blade", (0.0, 0.0, 0.015), (0.006, 0.03, 0.07), "steel", xf=hf)
    rows = [(0.016, 0.042, 1.0), (0.036, 0.046, 0.55), (0.036, 0.058, 0.55), (0.02, 0.062), (0.02, 0.074),
            (0.0185, 0.078), (0.0145, 0.112), (0.0185, 0.146), (0.0145, 0.18), (0.0185, 0.214), (0.0145, 0.248),
            (0.0185, 0.282), (0.021, 0.292), (0.024, 0.31), (0.018, 0.338), (0.0, 0.35)]
    mats = ["steel"] * 4 + ["wrap"] * 7 + ["steel"] * 4
    g.lathe("hilt", rows, 8, lambda i: mats[i], hf)
    return g


def _huqin_string_y(z):
    """y of the strings' centre line between the bridge and the 千斤 at height z (huqin frame)."""
    hl = HQ_BOX_L * 0.5
    y0, z0 = -hl - 0.034 - 0.005, -0.02
    y1, z1 = HQ_NECK_Y - 0.036, 1.55
    return y0 + (y1 - y0) * (z - z0) / (z1 - z0)


def _rrect(hx, hy, rc, z, n=3):
    """Rounded rectangle ring (counter-clockwise from +x), corner radius rc, n segments a corner."""
    out = []
    for cx, cy, a0 in ((hx - rc, hy - rc, 0.0), (-hx + rc, hy - rc, 90.0), (-hx + rc, -hy + rc, 180.0),
                       (hx - rc, -hy + rc, 270.0)):
        for i in range(n + 1):
            a = math.radians(a0 + 90.0 * i / n)
            out.append((cx + rc * math.cos(a), cy + rc * math.sin(a), z))
    return out


def _crescent(g, name, cx, y_front, y_back, cz, r, mat):
    """Crescent moon on the apron's front face (y_front < y_back), horns to the left (toward the sun): the disc of
    radius r at (cx, cz) less a disc of 0.88 r shifted 0.42 r left. A strip of quads between the two arcs, closed."""
    ri, off, n = 0.88 * r, 0.42 * r, 12
    xt = (ri * ri - r * r - off * off) / (2.0 * off)                   # the horns' x (from the centre)
    zt = math.sqrt(max(r * r - xt * xt, 0.0))
    ao = math.atan2(zt, xt)
    ai = math.atan2(zt, xt + off)
    outer = [(r * math.cos(ao - 2 * ao * j / n), r * math.sin(ao - 2 * ao * j / n)) for j in range(n + 1)]
    inner = [(-off + ri * math.cos(ai - 2 * ai * j / n), ri * math.sin(ai - 2 * ai * j / n)) for j in range(n + 1)]
    loop = outer + inner[n - 1:0:-1]                                    # the horns are outer[0] and outer[n]

    def idx_i(j):
        return 0 if j == 0 else (n if j == n else 2 * n - j)
    g.begin(name)
    F = [g.v((cx + x, y_front, cz + z)) for x, z in loop]
    B = [g.v((cx + x, y_back, cz + z)) for x, z in loop]
    m = len(loop)
    for j in range(n):
        q = []
        for v in (j, j + 1, idx_i(j + 1), idx_i(j)):
            if v not in q:
                q.append(v)                                             # the horn quads are triangles
        g.face(tuple(F[i] for i in q), mat, smooth=False)
        g.face(tuple(B[i] for i in reversed(q)), mat, smooth=False)
    for i in range(m):
        i2 = (i + 1) % m
        g.face((F[i2], F[i], B[i], B[i2]), mat, smooth=False)
    g.end()


def duet_table_geo(lawn=None):
    """Stone qin table 琴台 in the duet frame (origin on the lawn's datum under its centre): a top slab with an ice-plate
    edge 冰盘沿 (TABLE_*), two tapered end-slab legs on plinths sunk TABLE_SINK under the lawn's lowest point beneath
    them, front and back aprons, and the sun-and-moon emblem on the front apron (a domed gold sun disc, a white-jade
    crescent to its right, horns toward it)."""
    lawn = lawn or _flat
    g = _DGeo()
    z_top = lawn(0.0, 0.0) + TABLE_H
    hx, hy, T = TABLE_L * 0.5, TABLE_D * 0.5, TABLE_T
    rings = [_rrect(hx - i, hy - i, max(0.06 - i, 0.015), z) for i, z in
             ((0.045, z_top - T), (0.0, z_top - T + 0.06), (0.0, z_top - 0.035), (0.018, z_top))]
    g.solid("top", rings, "stone", smooth=False)
    px, py, ph = TABLE_PLINTH
    lt, ld = TABLE_LEG_T * 0.5, TABLE_LEG_D * 0.5
    for i, sx in enumerate((-1.0, 1.0)):
        x = sx * TABLE_LEG_X
        zl = min(lawn(x + dx * px * 0.5, dy * py * 0.5) for dx in (-1, 0, 1) for dy in (-1, 0, 1))
        zb = zl - TABLE_SINK
        zt = zl + ph * 0.5
        g.box("plinth.%d" % i, (x, 0.0, 0.5 * (zb + zt)), (px, py, zt - zb), "stone")
        z0, z1 = zt - 0.01, z_top - T + 0.005
        corners = ((1, -1), (1, 1), (-1, 1), (-1, -1))
        g.solid("leg.%d" % i, [[(x + a * (lt + 0.025), b * (ld + 0.03), z0) for a, b in corners],
                               [(x + a * lt, b * ld, z1) for a, b in corners]], "stone", smooth=False)
    ax = TABLE_LEG_X - lt + 0.01
    ay = hy - TABLE_APRON_IN - TABLE_APRON_T * 0.5
    az = z_top - T - TABLE_APRON_H * 0.5 + 0.005
    for i, sy in enumerate((-1.0, 1.0)):
        g.box("apron.%d" % i, (0.0, sy * ay, az), (2.0 * ax, TABLE_APRON_T, TABLE_APRON_H + 0.01), "stone")
    # 日月: the sun disc and, to its right, the crescent moon, on a slate inlay on the front apron's face
    yf = -(hy - TABLE_APRON_IN)
    il, ih = EMBLEM_INLAY
    ring = [(EMBLEM_X + p[0], p[1], az + p[2]) for p in
            [(q[0], q[2], q[1]) for q in _rrect(il * 0.5, ih * 0.5, 0.035, 0.0)]]
    g.solid("inlay", [[(x, yf + 0.004, z) for x, _y, z in ring], [(x, yf - 0.008, z) for x, _y, z in ring]], "inlay",
            smooth=False)
    yf -= 0.008
    r = EMBLEM_R
    sun_x, moon_x = EMBLEM_X - 0.75 * r, EMBLEM_X + 0.95 * r
    g.lathe("sun", ((0.0, -0.004), (r, -0.004), (r, 0.010), (0.9 * r, 0.016), (0.0, 0.018)), 24, "sun",
            _dframe((sun_x, yf, az), (0.0, -1.0, 0.0), ref=(1.0, 0.0, 0.0)))
    _crescent(g, "moon", moon_x, yf - 0.014, yf + 0.004, az, 0.98 * r, "moon")
    return g


def duet_seat_geo():
    """Stone drum stool 石鼓墩, base at z 0 (SEAT_SINK under the lawn), SEAT_H over the lawn: a bellied drum with a
    rolled rim and a raised band near either end (where a drum's heads are tacked), 24-sided."""
    k = SEAT_R / 0.47
    hk = (SEAT_SINK + SEAT_H) / 0.65
    rows = [(0.0, 0.0), (0.37, 0.0), (0.37, 0.05), (0.385, 0.07), (0.40, 0.085), (0.412, 0.10), (0.405, 0.115),
            (0.43, 0.15), (0.455, 0.21), (0.468, 0.29), (0.468, 0.37), (0.452, 0.46), (0.43, 0.51), (0.437, 0.525),
            (0.425, 0.54), (0.405, 0.57), (0.395, 0.60), (0.41, 0.615), (0.405, 0.64), (0.385, 0.65), (0.0, 0.65)]
    g = _DGeo()
    g.lathe("drum", [(r * k, h * hk) for r, h in rows], 24, "stone", lambda p: p)
    return g


DUET_PARTS = (    # (key, object name, geometry(lawn), ((role, material), ...)) - slot order = this order
    ("table", K + ".duet_table", duet_table_geo, (("stone", "marble_white"), ("inlay", "stone_dark"), ("sun", "gold"),
                                                  ("moon", "props_jade_white"))),
    ("seat_qin", K + ".duet_seat_qin", lambda lawn=None: duet_seat_geo(), (("stone", "marble_white"),)),
    ("seat_xiao", K + ".duet_seat_xiao", lambda lawn=None: duet_seat_geo(), (("stone", "marble_white"),)),
    ("qin", K + ".duet_qin", lambda lawn=None: duet_qin_geo(),
     (("body", "lacquer_black"), ("string", "cloth_white"), ("hui", "props_jade_white"), ("trim", "wood_dark"),
      ("tassel", "cloth_red"))),
    ("xiao", K + ".duet_xiao", lambda lawn=None: duet_xiao_geo(), (("body", DUET_XIAO_MAT), ("tassel", "cloth_red"))),
    ("huqin", K + ".duet_huqin", lambda lawn=None: duet_huqin_geo(huqin_bow_droop(lawn)),
     (("wood", "wood_dark"), ("skin", "props_drum_skin"), ("light", "wood_light"), ("hair", "props_feather_white"),
      ("steel", "steel"), ("wrap", "cloth_black"))),
)


def duet_matrix():
    """abode.root frame <- duet frame (the Empty): (origin, x axis (plan), y axis (plan), uniform scale)."""
    c, s = math.cos(DUET_YAW), math.sin(DUET_YAW)
    return (DUET_LOC[0], DUET_LOC[1], 0.0), (c, s), (-s, c), DUET_SCALE


def duet_lawn(gz):
    """lawn(x, y) in the duet frame from gz(x, y, default) in abode.root's frame (abode._lawn_sampler)."""
    (ox, oy, _oz), (ux, uy), (vx, vy), S = duet_matrix()

    def lawn(x, y):
        return gz(ox + S * (x * ux + y * vx), oy + S * (x * uy + y * vy), 0.0) / S
    return lawn


def duet_keep_clear():
    """[(x0, x1, y0, y1, top)] in abode.root's frame: the box round DUET_CLEAR, for _garden_mask (no scattered plants
    on or within its clearance of the duet set)."""
    (ox, oy, _oz), (ux, uy), (vx, vy), S = duet_matrix()
    x0, x1, y0, y1 = DUET_CLEAR
    pts = [(ox + S * (x * ux + y * vx), oy + S * (x * uy + y * vy)) for x in (x0, x1) for y in (y0, y1)]
    return [(min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts), 0.0)]


def _duet_mesh(name, g, roles):
    """A _DGeo as a new mesh: material slots in ``roles`` order, smooth faces with hard edges between materials, at
    open edges and sharper than DUET_SMOOTH."""
    slot = {r: i for i, (r, _m) in enumerate(roles)}
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in g.verts]
    bm.verts.index_update()
    for idx, m, sm in zip(g.faces, g.mat, g.smooth):
        f = bm.faces.new([vs[i] for i in idx])
        f.material_index = slot[m]
        f.smooth = sm
    bm.normal_update()
    for e in bm.edges:
        lf = e.link_faces
        e.smooth = not (len(lf) != 2 or lf[0].material_index != lf[1].material_index
                        or e.calc_face_angle(math.pi) > DUET_SMOOTH)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    U.set_materials(me, [m for _r, m in roles])
    me.update()
    return me


def _duet(coll, root, gz=None):
    """The Wanderer duet: Empty 'abode.duet' under ``root`` at DUET_LOC (turned DUET_YAW, scaled DUET_SCALE) and its
    six meshes (DUET_PARTS) set on the lawn (gz: abode._lawn_sampler of abode.ground; None = sample it here), every
    object tagged obj['sect_item'] = DUET_ITEM. Returns the Empty."""
    from mathutils import Matrix
    if gz is None:
        gz = _lawn_sampler(bpy.data.objects[K + ".ground"])
    lawn = duet_lawn(gz)
    (ox, oy, oz), _u, _v, S = duet_matrix()
    em = U.empty(DUET, coll, location=(ox, oy, oz), rotation=(0.0, 0.0, DUET_YAW), scale=(S,) * 3,
                 parent=root, display_size=1.5)
    em["sect_item"] = DUET_ITEM
    lay = duet_layout(lawn)
    for key, name, geo, roles in DUET_PARTS:
        g = geo(lawn)
        me = _duet_mesh(name, g, roles)
        loc, rot, sc = lay[key]
        m = Matrix.Translation(loc) @ Matrix(rot).to_4x4() @ Matrix.Diagonal((sc, sc, sc, 1.0))
        ob = U.object_from_mesh(name, me, coll, parent=em, matrix=m)
        ob["sect_item"] = DUET_ITEM
    return em


# --- Xiaolongnü's golden-bell silk ribbon 金铃索 --------------------------------------------------------------------
# Return of the Condor Heroes: Xiaolongnü 小龙女 fights with a long band of white silk 白绸带 that ends in a small
# golden ball with a bell inside it, ringing as it flies (金铃索). She has left it on the tea pavilion's front-left
# flying eave, right over the duet's qin table: the gathered silk is wrapped round the upturned tip of the hip ridge,
# just outboard of the immortal rider (which keeps it from sliding down the ridge), and pulled down into a knot under
# the tip; its two tails hang past the balcony's front in the breeze off the falls (RIBBON_WIND), each ending in a
# gold cap with a golden bell ball on a ring (a crotal bell: a raised band round its middle, a slot across its lower
# half). The long tail falls ~9 m to a bell ~0.8 m over the lawn west of the table; the short one ends about level
# with the deck. The ribbon touches nothing but the ridge tip it is tied round (sect/patch_r8_ribbon.py checks it).
# Static: the breeze is in the shape (the abode's export carries no cloth motion): the tails lean with it and twist
# as silk does, the long one straightening under its bell.
#
# Scale: 0.36 m wide (about 2.5x a real ribbon, like the duet's instruments) with 0.24 m bells, so the 1380 hold
# (~77 m off) shows a white ribbon ~5 px wide from the eave corner down to just left of the qin table, gold at its ends.
#
# The loop is fitted to the ridge mesh in the file (ribbon_section: the convex hull of its cross-section round the
# loop's plane, RIBBON_LOOP_*), so it hugs the tip RIBBON_LOOP_GAP off it. Frame: abode.root's; the Empty
# abode.ribbon sits at the knot (no rotation), its two meshes in its frame. Every part is a closed solid (_DGeo) with
# outward winding (bake_web treats closed pieces as closed: both faces of the silk bake).
RIBBON = K + ".ribbon"
RIBBON_ITEM = "golden_bell_ribbon"    # obj['sect_item'] on every object of the group (sect/patch_r8_ribbon.py)
RIBBON_SILK = K + ".ribbon_silk"
RIBBON_BELLS = K + ".ribbon_bells"
RIBBON_TRI_CAP = DUET_TRI_CAP         # per object
RIBBON_PAVILION = K + ".tea_pavilion"
RIBBON_CORNER = (-1.0, -1.0)          # (sx, sy) of the pavilion's eave corner: front-left, over the qin table
RIBBON_LOOP_D = 6.125                 # the loop's plane: m out along the corner's diagonal from the pavilion's axis,
RIBBON_LOOP_DZ = 4.355                # m over its floor (where the ridge tip turns up, outboard of the immortal),
RIBBON_LOOP_TILT = math.radians(50.0)  # and how far the tip's axis (the plane's normal) rises out of plan there
RIBBON_SLAB = 0.08                    # the ridge's section is taken this far either side of the plane (covers the knot)
RIBBON_LOOP_W = 0.08                  # the gathered silk's width round the tip
RIBBON_LOOP_GAP = 0.012               # its inner face off the section's convex hull
RIBBON_KNOT_DROP = 0.09               # the knot pulls the loop into a teardrop: apex this far below the section
RIBBON_W = 0.36                       # open width of the silk
RIBBON_T = 0.02                       # its thickness (a closed band). Round 12: 0.012 with lens-shaped tails whose
                                      # edges thinned to nothing: front and back faces 2-12 mm apart, and the web
                                      # (every face double-sided, 24-bit depth) let the back show through the front
                                      # beyond ~90-220 m. Now 2 cm everywhere, with square edges (_RIB_X / _RIB_Y)
RIBBON_T_OLD = 0.012                  # before round 12 (sect/patch_r12_areas.py recognises the old silk by it)
RIBBON_DS = 0.06                      # m between a tail's cross-sections
RIBBON_WIND = (-0.8, -0.6)            # the breeze off the falls, plan (abode.root): away from the falls and the cliff
RIBBON_TAILS = (   # (name, control points (m along the wind, toward the hold camera, up) from the knot, start offset
                   # toward the hold camera, twist amplitude deg, its wavelength m, phase rad)
    # the long tail hangs from the knot, bellies out in the breeze half way down and straightens under its bell
    ("long", ((0.0, 0.0, 0.0), (0.02, 0.0, -0.7), (0.12, 0.05, -1.8), (0.55, 0.12, -3.0), (1.35, 0.2, -4.1),
              (2.15, 0.22, -5.0), (2.75, 0.2, -6.0), (3.05, 0.22, -7.1), (3.15, 0.25, -8.1), (3.12, 0.25, -8.7),
              (3.1, 0.25, -9.0)),
     -0.022, 40.0, 3.2, 0.0),
    # the short one is lifted by it, streaming out before its bell pulls it down
    ("short", ((0.0, 0.0, 0.0), (0.1, 0.08, -0.6), (0.45, 0.25, -1.3), (1.0, 0.4, -1.85), (1.6, 0.48, -2.25),
               (2.1, 0.5, -2.75), (2.35, 0.5, -3.3), (2.4, 0.5, -3.6)),
     0.022, 55.0, 2.4, 0.6),
)
RIBBON_BELL_R = 0.12                  # golden bell ball (about 5x a real one: a gold glint at the hold)
RIBBON_MAT = M.variant("abode_ribbon_silk", "cloth_white", colour="#f3f0e8", sheen=0.85, rough=0.5,
                       translucency=0.2, weave=False)   # white silk: smoother and brighter than the woven cloth
RIBBON_KNOT = (((0.0, 0.0, 0.0), (0.06, 0.065, 0.06)),          # the knot's lumps: offset (across the tip, along
               ((0.012, 0.045, 0.02), (0.042, 0.045, 0.04)),     # it, down in the loop's plane) from its centre,
               ((-0.01, -0.04, 0.015), (0.04, 0.042, 0.045)))    # and radii
RIBBON_PARTS = ((RIBBON_SILK, (("silk", RIBBON_MAT),)),
                (RIBBON_BELLS, (("gold", "gold"), ("slot", "lacquer_black"))))
_RIB_X = (1.0, 1.0, 0.33, -0.33, -1.0, -1.0, -0.33, 0.33)  # a tail's cross-section: x of its half width,
_RIB_Y = (-1.0, 1.0, 1.0, 1.0, 1.0, -1.0, -1.0, -1.0)      # y of its half thickness: square edges (round 12; the
                                                           # cup still bends it across its width)
_RIB_X_OLD = (1.0, 0.62, 0.0, -0.62, -1.0, -0.62, 0.0, 0.62)   # before round 12: thin edges at +-x
_RIB_Y_OLD = (0.0, 1.0, 1.0, 1.0, 0.0, -1.0, -1.0, -1.0)


def _rib_basis():
    """(along the wind, toward the hold camera, up): RIBBON_WIND in plan, its left normal (the hold camera's side of
    the tails) and +z, unit vectors in abode.root's frame."""
    w = _dnorm((RIBBON_WIND[0], RIBBON_WIND[1], 0.0))
    return w, (-w[1], w[0], 0.0), (0.0, 0.0, 1.0)


def _lerp3(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def ribbon_plane(pav_loc):
    """The loop's plane round the hip ridge's upturned tip at RIBBON_CORNER of the pavilion standing at ``pav_loc``
    (abode.root's frame): (centre, n = the tip's axis (out and up), u across it (plan), v = n x u, dn = world down
    in the plane)."""
    out = _dnorm((RIBBON_CORNER[0], RIBBON_CORNER[1], 0.0))
    c = (pav_loc[0] + out[0] * RIBBON_LOOP_D, pav_loc[1] + out[1] * RIBBON_LOOP_D, pav_loc[2] + RIBBON_LOOP_DZ)
    ct, st = math.cos(RIBBON_LOOP_TILT), math.sin(RIBBON_LOOP_TILT)
    n = (out[0] * ct, out[1] * ct, st)
    u = _dnorm(_dcross((0.0, 0.0, 1.0), out))
    return c, n, u, _dcross(n, u), _dnorm(_dadd((0.0, 0.0, -1.0), n, st))


def ribbon_section(verts, edges, plane):
    """(u, v) points of a mesh's cross-section in the slab |n.(p - centre)| <= RIBBON_SLAB round the loop's plane:
    its vertices there and its edges' crossings of the slab's two faces and middle plane, within 0.6 m of the
    centre. verts: [(x, y, z)] in abode.root's frame; edges: [(i, j)]."""
    c, n, u, v, _dn = plane
    rel = [_dsub(p, c) for p in verts]
    h = [_ddot(d, n) for d in rel]
    near = [_ddot(d, d) < 0.36 for d in rel]
    pts = [(_ddot(d, u), _ddot(d, v)) for d, hp, nr in zip(rel, h, near) if nr and abs(hp) <= RIBBON_SLAB]
    for i, j in edges:
        if not (near[i] or near[j]):
            continue
        for lv in (-RIBBON_SLAB, 0.0, RIBBON_SLAB):
            a, b = h[i] - lv, h[j] - lv
            if a * b < 0.0:
                d = _lerp3(rel[i], rel[j], a / (a - b))
                pts.append((_ddot(d, u), _ddot(d, v)))
    return pts


def _hull2d(pts):
    """Convex hull of 2D points, counter-clockwise (Andrew's monotone chain)."""
    p = sorted(set((round(x, 6), round(y, 6)) for x, y in pts))
    if len(p) < 3:
        return p

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for q in p:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], q) <= 0.0:
            lo.pop()
        lo.append(q)
    for q in reversed(p):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], q) <= 0.0:
            hi.pop()
        hi.append(q)
    return lo[:-1] + hi[:-1]


def _offset_closed(hull, r, step=math.radians(12.0)):
    """The curve r outside a counter-clockwise convex polygon: its edges pushed out by r, joined by arcs of radius r
    round its corners (a point every ``step`` or less)."""
    out = []
    m = len(hull)
    for i in range(m):
        p0, p1, p2 = hull[i - 1], hull[i], hull[(i + 1) % m]
        a0 = math.atan2(-(p1[0] - p0[0]), p1[1] - p0[1])      # outward normal of the edge into p1
        a1 = math.atan2(-(p2[0] - p1[0]), p2[1] - p1[1])      # ... and of the edge out of it
        da = (a1 - a0) % (2.0 * math.pi)
        k = max(1, int(math.ceil(da / step)))
        out.extend((p1[0] + r * math.cos(a0 + da * j / k), p1[1] + r * math.sin(a0 + da * j / k)) for j in range(k + 1))
    return out


def _resample_closed(pts, n):
    """n points evenly spaced by arc length round a closed 2D polyline."""
    m = len(pts)
    seg = [math.dist(pts[i], pts[(i + 1) % m]) for i in range(m)]
    L = sum(seg)
    out, i, acc = [], 0, 0.0
    for k in range(n):
        s = L * k / n
        while i < m - 1 and acc + seg[i] < s:
            acc += seg[i]
            i += 1
        t = (s - acc) / seg[i] if seg[i] > 1e-12 else 0.0
        a, b = pts[i], pts[(i + 1) % m]
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def ribbon_loop(section, plane, n=28):
    """The silk loop round the ridge tip: ([(point, outward)] round its inner face (abode.root's frame), the knot's
    apex). The convex hull of the section and of an apex RIBBON_KNOT_DROP below its lowest point in the plane (the
    knot pulls the loop down into a teardrop), pushed out RIBBON_LOOP_GAP, n points round."""
    c, _n, u, v, dn = plane
    d2 = (_ddot(dn, u), _ddot(dn, v))
    hull = _hull2d(section)
    if len(hull) < 3:
        raise RuntimeError("ribbon: the ridge's section round the loop has %d hull points" % len(hull))
    low = max(hull, key=lambda p: p[0] * d2[0] + p[1] * d2[1])
    apex = (low[0] + d2[0] * RIBBON_KNOT_DROP, low[1] + d2[1] * RIBBON_KNOT_DROP)
    ring = _resample_closed(_offset_closed(_hull2d(hull + [apex]), RIBBON_LOOP_GAP), n)
    out = []
    for i, (x, y) in enumerate(ring):
        a, b = ring[i - 1], ring[(i + 1) % n]
        tx, ty = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tx, ty) or 1.0
        out.append((_dadd(_dadd(c, u, x), v, y), _dnorm(_dadd(_dadd((0.0, 0.0, 0.0), u, ty / ln), v, -tx / ln))))
    return out, _dadd(_dadd(c, u, apex[0]), v, apex[1])


def _centripetal(pts, per=16):
    """Centripetal Catmull-Rom through 3D points (no loops or cusps where the spacing changes), ``per`` samples a
    span, the ends extended straight."""
    P = [_dadd(pts[0], _dsub(pts[0], pts[1]))] + [tuple(p) for p in pts] + [_dadd(pts[-1], _dsub(pts[-1], pts[-2]))]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        t1 = math.sqrt(max(math.dist(p0, p1), 1e-9))
        t2 = t1 + math.sqrt(max(math.dist(p1, p2), 1e-9))
        t3 = t2 + math.sqrt(max(math.dist(p2, p3), 1e-9))
        for k in range(per):
            t = t1 + (t2 - t1) * k / per
            a1 = _lerp3(p0, p1, t / t1)
            a2 = _lerp3(p1, p2, (t - t1) / (t2 - t1))
            a3 = _lerp3(p2, p3, (t - t2) / (t3 - t2))
            b1, b2 = _lerp3(a1, a2, t / t2), _lerp3(a2, a3, (t - t1) / (t3 - t1))
            out.append(_lerp3(b1, b2, (t - t1) / (t2 - t1)))
    out.append(P[-2])
    return out


def _resample_path(pts, ds):
    """(points every ~ds by arc length along a 3D polyline, its length)."""
    cum = [0.0]
    for a, b in zip(pts[:-1], pts[1:]):
        cum.append(cum[-1] + math.dist(a, b))
    L = cum[-1]
    n = max(2, int(math.ceil(L / ds)))
    out, j = [], 0
    for k in range(n + 1):
        s = L * k / n
        while j < len(pts) - 2 and cum[j + 1] < s:
            j += 1
        seg = cum[j + 1] - cum[j]
        out.append(_lerp3(pts[j], pts[j + 1], min(1.0, max(0.0, (s - cum[j]) / seg)) if seg > 1e-12 else 0.0))
    return out, L


def ribbon_tail(start, ctrl, twist, wave, phase):
    """A tail's cross-sections from the knot to its end, every ~RIBBON_DS: [(centre, tangent, width direction, face
    normal, half width, cup)]. ctrl: control points (along the wind, toward the hold camera, up) from ``start``. The
    width starts along the wind (the face to the hold camera), is carried down the tail without turning about it
    (parallel transport) and twisted by up to ``twist`` deg (wavelength ``wave`` m) away from the knot and the bell;
    the silk opens from the knot to RIBBON_W over 0.75 m, gathers into the bell's cap over its last 0.4 m and cups a
    little across its width."""
    w, c, z = _rib_basis()
    pts = [_dadd(_dadd(_dadd(start, w, p[0]), c, p[1]), z, p[2]) for p in ctrl]
    path, L = _resample_path(_centripetal(pts), RIBBON_DS)
    m = len(path)
    out, e = [], w
    for i, p in enumerate(path):
        s = L * i / (m - 1)
        t = _dnorm(_dsub(path[min(i + 1, m - 1)], path[max(i - 1, 0)]))
        e = _dnorm(_dsub(e, tuple(t[k] * _ddot(e, t) for k in range(3))))
        ramp = _smooth(0.6, 1.6, s) * (1.0 - _smooth(L - 1.2, L - 0.4, s))
        tau = math.radians(twist) * math.sin(2.0 * math.pi * s / wave + phase) * ramp
        et = _dadd(tuple(e[k] * math.cos(tau) for k in range(3)), _dcross(t, e), math.sin(tau))
        hw = 0.5 * RIBBON_W * (0.12 + 0.88 * _smooth(0.0, 0.75, s)) * (1.0 - 0.75 * _smooth(L - 0.4, L - 0.06, s))
        cup = 0.035 * math.sin(2.0 * math.pi * s / (0.8 * wave) + 2.0 * phase + 1.0) * ramp
        out.append((p, t, et, _dcross(t, et), hw, cup))
    return out


def _tail_rings(secs):
    ht = 0.5 * RIBBON_T
    return [[_dadd(_dadd(p, e, fx * hw), nrm, fy * ht + cup * (1.0 - fx * fx)) for fx, fy in zip(_RIB_X, _RIB_Y)]
            for p, _t, e, nrm, hw, cup in secs]


def _ribbon_bell(g, name, end, tan):
    """At a tail's end (``end``, its last tangent ``tan``): a gold cap over the gathered silk, a gold ring through the
    cap's foot and the golden bell ball hanging from it by its own loop (the two interlocked like chain links): a
    crotal bell with a raised band round its middle and a dark slot across its lower half. Returns the bell's
    lowest point."""
    R = RIBBON_BELL_R
    w, c, z = _rib_basis()
    cap0 = _dadd(end, tan, -0.07)
    g.lathe(name + ".cap", ((0.0, 0.0), (0.052, 0.0), (0.062, 0.018), (0.066, 0.06), (0.06, 0.1), (0.04, 0.126),
                            (0.016, 0.14), (0.0, 0.145)), 12, "gold", _dframe(cap0, tan))
    rc = _dadd(_dadd(cap0, tan, 0.145), z, -0.02)          # the ring (in the plane of z and toward the camera)
    g.torus(name + ".ring", 0.03, 0.008, 12, 6, "gold", lambda p: _dadd(_dadd(_dadd(rc, c, p[0]), z, p[1]), w, p[2]))
    rl = _dadd(rc, z, -0.032)                               # the bell's loop (plane of z and the wind) through it:
    bc = _dadd(rl, z, -(R + 0.012))                         # 2 cm clear of the ring where they cross, sunk in the bell
    g.torus(name + ".loop", 0.024, 0.0065, 12, 6, "gold", lambda p: _dadd(_dadd(_dadd(rl, w, p[0]), z, p[1]), c, p[2]))
    g.lathe(name + ".ball", [(R * math.cos(a), R * math.sin(a)) for a in
                             (math.radians(-90.0 + 15.0 * k) for k in range(13))], 16, "gold", _dframe(bc, z))
    g.torus(name + ".band", R, 0.007, 24, 6, "gold", lambda p: _dadd(_dadd(_dadd(bc, w, p[0]), c, p[1]), z, p[2]))
    rings = []
    for k in range(15):
        f = math.radians(-70.0 + 10.0 * k)                  # from the bottom pole toward the camera side and back
        d = _dadd(tuple(c[i] * math.sin(f) for i in range(3)), z, -math.cos(f))
        rings.append([_dadd(_dadd(bc, d, R + dr), w, dw) for dr, dw in
                      ((-0.004, -0.011), (-0.004, 0.011), (0.0025, 0.011), (0.0025, -0.011))])
    g.solid(name + ".slot", rings, "slot", smooth=False)
    return _dadd(bc, z, -R)


def ribbon_geo(pav_loc, verts, edges):
    """The ribbon as plain lists in abode.root's frame: (silk _DGeo, bells _DGeo, info), its loop fitted to the ridge
    mesh (verts in abode.root's frame, edges) round the tip at RIBBON_CORNER of the pavilion standing at pav_loc.
    info: plane, section, apex, knot (the Empty's place), tails [(name, sections, bell's lowest point)]."""
    plane = ribbon_plane(pav_loc)
    _c, nn, u, _v, dn = plane
    sec = ribbon_section(verts, edges, plane)
    loop, apex = ribbon_loop(sec, plane)
    silk, bells = _DGeo(), _DGeo()
    hb = 0.5 * RIBBON_LOOP_W
    silk.begin("loop")                     # a band of rectangular section round the tip
    ids = []
    for q, o in loop:
        qo = _dadd(q, o, RIBBON_T)
        ids.append([silk.v(_dadd(q, nn, -hb)), silk.v(_dadd(q, nn, hb)), silk.v(_dadd(qo, nn, hb)),
                    silk.v(_dadd(qo, nn, -hb))])
    for i in range(len(ids)):
        a, b = ids[i], ids[(i + 1) % len(ids)]
        for k in range(4):
            silk.face((a[k], b[k], b[(k + 1) % 4], a[(k + 1) % 4]), "silk")
    silk.end()
    knot = _dadd(apex, dn, 0.015)
    rows = [(math.cos(a), math.sin(a)) for a in (math.radians(-90.0 + 22.5 * k) for k in range(9))]
    for i, ((ou, on, od), (ru, rn, rd)) in enumerate(RIBBON_KNOT):     # lumps of silk round the crossing
        kc = _dadd(_dadd(_dadd(knot, u, ou), nn, on), dn, od)
        silk.lathe("knot.%d" % i, rows, 12, "silk",
                   lambda p, kc=kc, ru=ru, rn=rn, rd=rd: _dadd(_dadd(_dadd(kc, u, p[0] * ru), nn, p[1] * rn), dn,
                                                               -p[2] * rd))
    w, c, _z = _rib_basis()
    top = _dadd(knot, dn, 0.035)
    tails = []
    for name, ctrl, side, twist, wave, phase in RIBBON_TAILS:
        secs = ribbon_tail(_dadd(top, c, side), ctrl, twist, wave, phase)
        silk.solid("tail." + name, _tail_rings(secs), "silk")
        low = _ribbon_bell(bells, "bell." + name, secs[-1][0], secs[-1][1])
        tails.append((name, secs, low))
    return silk, bells, dict(plane=plane, section=sec, apex=apex, knot=knot, tails=tails)


def ribbon_ridge(root):
    """(pavilion location, ridge mesh vertices, its edges, the ridge object) in abode.root's frame: the tea pavilion's
    roof ridges (one mesh: the main and hip ridges with their upturned tips), read from the file through the parent
    chain (no depsgraph update needed)."""
    pav = next((o for o in root.children if o.name == RIBBON_PAVILION), None)
    if pav is None:
        raise RuntimeError("ribbon: no %s under %s" % (RIBBON_PAVILION, root.name))
    ridges = [o for o in pav.children_recursive if o.type == 'MESH' and o.name.endswith(".roof.ridges")]
    if len(ridges) != 1:
        raise RuntimeError("ribbon: %d '*.roof.ridges' meshes under %s" % (len(ridges), pav.name))
    wi = U.world_matrix(root).inverted()
    mr = wi @ U.world_matrix(ridges[0])
    verts = [tuple(mr @ v.co) for v in ridges[0].data.vertices]
    return tuple((wi @ U.world_matrix(pav)).translation), verts, [tuple(e.vertices) for e in ridges[0].data.edges], \
        ridges[0]


def _ribbon(coll, root):
    """Xiaolongnü's ribbon: Empty 'abode.ribbon' under ``root`` at the knot and its two meshes (RIBBON_PARTS), tied
    round the tip of the tea pavilion's front-left hip ridge (fitted to the file's ridge mesh), every object tagged
    obj['sect_item'] = RIBBON_ITEM. Returns the Empty."""
    pav_loc, verts, edges, _ob = ribbon_ridge(root)
    silk, bells, info = ribbon_geo(pav_loc, verts, edges)
    k = info["knot"]
    em = U.empty(RIBBON, coll, location=k, parent=root, display_size=0.5)
    em["sect_item"] = RIBBON_ITEM
    for (name, roles), g in zip(RIBBON_PARTS, (silk, bells)):
        g.verts = [_dsub(p, k) for p in g.verts]
        ob = U.object_from_mesh(name, _duet_mesh(name, g, roles), coll, parent=em)
        ob["sect_item"] = RIBBON_ITEM
    return em


INSCRIPTION = K + ".inscription"


def text_to_mesh(ob):
    """Turn the text (FONT) object ``ob`` into a mesh object in place (Blender's Convert to Mesh): the same object
    and name, parent, transform, collections and properties, its evaluated text as new mesh data with the curve's
    materials. The curve is freed. Returns ``ob``. sect/patch_r12_areas.py converts a built file's text with it."""
    if ob.type == 'MESH':
        return ob
    vl = bpy.context.view_layer
    temp = vl.objects.get(ob.name) is None       # (a collection not linked to the scene: link it for the operator)
    if temp:
        bpy.context.scene.collection.objects.link(ob)
        vl.update()
    cu = ob.data
    act = vl.objects.active
    sel = [o for o in vl.objects if o.select_get()]
    for o in sel:
        o.select_set(False)
    ob.select_set(True)
    vl.objects.active = ob
    try:
        bpy.ops.object.convert(target='MESH', keep_original=False)
    finally:
        ob.select_set(False)
        for o in sel:
            if o.name in vl.objects:
                o.select_set(True)
        vl.objects.active = act
        if temp:
            bpy.context.scene.collection.objects.unlink(ob)
    if ob.type != 'MESH':
        raise RuntimeError("text_to_mesh: %s is still a %s" % (ob.name, ob.type))
    if cu is not None and cu.users == 0:
        bpy.data.curves.remove(cu)
    ob.data.name = ob.name
    return ob


def _inscription(collection, root):
    """The cliff inscription 洞天福地 as one mesh object 'abode.inscription' (round 12: it was a text object, and
    export_web.gather keeps a text object and its evaluated mesh as two records, so the web drew the characters twice
    in one place: 55 m2 z-fighting on the cliff at the abode). Returns the object."""
    xi = INSC_X
    yi = _yb(xi) + LEAN * 30.0
    ob = U.text(INSCRIPTION, "洞天福地", collection, size=4.6, extrude=0.18, material="lacquer_red",
                vertical=True, location=(xi, yi - 0.12, 29.8), rotation=(math.pi / 2, 0, _face_yaw(xi)),
                parent=root)
    return text_to_mesh(ob)


def build(collection):
    """Build the Cave Abode at the local origin. Returns the root Empty 'abode.root'."""
    root = U.empty(K + ".root", collection, display_size=4.0)
    _cliff(collection, root)
    _cave(collection, root)
    _balcony(collection, root)
    pool = _water(collection, root)
    _ground(collection, root, pool)
    _plants(collection, root, pool)
    # cliff inscription 洞天福地 ("grotto heaven, blessed land"), red paint in carved strokes
    _inscription(collection, root)
    # the resting crane on the lawn beside the stair foot (1.7 m tall), and two cranes in flight
    P.crane(collection, "standing", 1.1, name=K + ".crane", parent=root,
            location=(-1.0, 7.0, 0.0), rotation=(0, 0, math.radians(-30)))
    for k, (loc, yaw) in enumerate((((-3.0, 4.0, 27.0), 80.0), ((5.0, -1.0, 31.5), 65.0))):
        P.crane(collection, "flying", 1.2, name=K + ".crane_flying", parent=root, location=loc,
                rotation=(0, math.radians(-12), math.radians(yaw)))
    # karst peaks rising behind the cliff top (Zhangjiajie silhouette)
    for k, (x, y, zt, r, h) in enumerate(PINNACLES):
        N.rock_pillar(collection, height=h, top_radius=r, seed=21 + k, top_flat=False, top_z=zt,
                      pines=not ABODE_R48, name=K + ".pinnacle", parent=root, location=(x, y, 0.0))
    if ABODE_R48:
        r48_dress(collection, root)
    # the Smiling, Proud Wanderer duet, just left: the qin table scene on the open lawn by the koi pool (round 34:
    # Xiaolongnü's ribbon no longer hangs from the tea pavilion's eave; it lies coiled at the summit)
    _duet(collection, root)
    return root


# Flight: arrive from the south-west seeing the whole cliff, swing past the balcony, then past
# the waterfall and up its fall line.
CAMERA_HINTS = [
    dict(name="approach", location=(-40, -112, 30), target=(2, 15, 32), lens=26),
    dict(name="balcony", location=(-20, -16, 13), target=(0, 20, 9), lens=24),
    dict(name="waterfall", location=(32, -8, 16), target=(6, 22, 14), lens=24),
    dict(name="rise", location=(38, -26, 50), target=(2, 22, 22), lens=28),
]

build.preview_cameras = [(h["name"], h["location"], h["target"], h["lens"]) for h in CAMERA_HINTS]
