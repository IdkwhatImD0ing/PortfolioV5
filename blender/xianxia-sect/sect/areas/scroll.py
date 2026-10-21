"""Area 8 - Jade Slip Pavilion (玉简阁), site section 'resume'.

Blocking pass (spec section 0): shape, scale, colour coding and camera matter, not detail.

Layout (local frame, front = -Y, z = 0 walkable top):
- a white marble terrace on the plateau, balustrade along the back (cliff) edge;
- a two-storey hexagonal pavilion (ge) at the back right, on its own platform at the cliff
  edge just behind the terrace, plaque 玉简阁
  under its upper eave, stone lanterns at its stairs, lanterns at the front eave corners;
- a stone desk with brush, inkstone and an open scroll on the terrace, left of the axis, and a
  path of stone lanterns leading from the terrace front to the pavilion stairs;
- the walking route (arrival -> door): a paved approach walk on the lawn from the arrival
  landing (between two stone lanterns) to three front steps onto the terrace, then a grey stone
  walk on the pavilion axis (x 12) to the foot of the pavilion's front stair;
- the way out: side steps off the terrace's right edge, a paved exit walk east through a
  one-bay gate to the depart point where the stair to the formation starts;
- the focal object: a colossal unrolled jade bamboo-slip scroll (22 x 9 m at 0.9x, slightly
  curved, glowing script) left of the axis, turned 40 deg toward the 1103 hold camera, held high
  in a standing frame (round 2026-10-21 r5: it used to float with nothing holding it): two
  vermilion posts behind it, clamped at the foot by stone slabs with iron bands, a curved sill
  under the slips and a top rail over them, and the Ming Sect's 日 + 月 = 明 on the post heads
  (a gold sun on the left post, a silver crescent moon on the right); a glowing script ring on
  the paving under it, the posts standing between its two bands. Its slips carry Jin Yong
  (props.JIN_YONG_VERSES, r8): from the right end, one passage after another, each from the top
  of a new slip, then a blank slip and the verses again (sect/patch_r8_scrolltext.py);
- the six Holy Fire Tokens of the Ming Sect (圣火令), black tablets with fire inside, standing
  upright in a row in the slots of a black-lacquer stand on a low stone plinth, leaning on its
  back rail, against the right rail of the terrace (they used to float in a fanned stack);
- an ancient pine leaning over the back edge, bamboo and a blossom tree for colour, scholar rocks
  on low stone pedestals.
The camera glides along the scroll's face (almost reading it), then passes its right end
toward the pavilion.
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from sect.lib import util as U
from sect.lib import arch as A
from sect.lib import props as P
from sect.lib import nature as N

# arrival / depart: where the incoming and outgoing connector stairs meet this area, as
# (x, y, z, heading) in the local frame. z is the landing's top (the stair's end step sits flush
# with it). heading is the walking direction in radians, measured like world.py's
# yaw = atan2(dy, dx): 0 = +x, pi/2 = +y. (architecture-audit.md 1.8 and W1)
AREA = dict(key="scroll", section_id="resume", title_en="Jade Slip Pavilion",
            title_zh="玉简阁", footprint=40.0,
            arrival=(12.0, -44.0, -0.35, math.pi / 2),   # front end of the approach walk, heading +y
            depart=(44.0, -3.5, -0.35, 0.0))             # east end of the exit walk, heading +x

K = "scroll"

# key positions (local)
PAV = (12.0, 29.5)            # two-storey pavilion centre: back right, on the cliff edge (r ~ 39 m)
PAV_R = 5.8                   # pavilion column circumradius (its platform reaches ~7.5 m)
LANTERN_LIFT = 0.16           # the eave-corner lanterns' lift (r5): cord top 3 cm into the lower eave's soffit
SCROLL_C = (-4.0, 6.0, 13.0)  # centre of the scroll (held by its frame, sect/patch_r5_scroll.py)
SCROLL_W, SCROLL_H = 22.0, 9.0
SCROLL_CURVE = 0.08           # bow of the scroll in plan (props.bamboo_slip_scroll curve: ends come 0.08 W forward)
SCROLL_SCALE = 0.9            # (audit D2, 2026-10-21: at (-10, -4), full size and square to the axis, 49 % of it
SCROLL_YAW = math.radians(-40.0)   # lay off the left edge of the 1103 hold. Turned 40 deg toward that camera's left,
                              # 0.9x, 6 m right and 10 m back it is all in frame, left of the pavilion, its face 47 deg
                              # off the view, and the flight passes it 21 m off instead of 18)
SCROLL_TEXT = P.JIN_YONG_VERSES   # what the slips say (r8): Jin Yong, each passage from the top of a new slip
DESK = (4.0, 14.0)            # stone desk on the terrace, left of the axis walk (keeps x 12 clear)
STAND_C = (23.2, 8.0)         # the Holy Fire Tokens' stand on the terrace: right of the axis walk, against the right
                              # rail, faces -Y (27 deg off the 1103 hold camera); clear of the route to the side
                              # steps (y -6 .. -1) and 3.8 m in front of the peach (r5: the stack floated at (21, -3, 6.5))
RING_C = (SCROLL_C[0], SCROLL_C[1] + 1.0)   # the rune rings on the paving under the scroll
RING_SCRIPT, RING_TRIGRAM = (9.0, 0.9), (6.4, 0.45)   # (radius to the band's centre, band width)

TERRACE_X = (-27.0, 27.0)
TERRACE_Y = (-19.0, 24.0)     # the pavilion's own platform stands behind the back edge

# Where the fly-through camera should pass (local, front = -Y), ordered along the flight.
CAMERA_HINTS = [
    dict(name="approach", location=(-4.0, -72.0, 15.0), target=(0.0, 6.0, 11.0), lens=30),
    dict(name="read_left", location=(-24.0, -21.0, 13.0), target=(-6.0, -3.0, 12.5), lens=28),
    dict(name="read", location=(0.0, -22.0, 13.5), target=(-9.0, -4.0, 12.8), lens=24),
    dict(name="exit", location=(25.0, -4.0, 14.0), target=(12.0, 27.0, 10.0), lens=28),
]


def _n(*parts):
    return U.name(K, *parts)


def _terrace(coll, root):
    """Marble terrace (top at z = 0) with a balustrade along the back and side edges."""
    x0, x1 = TERRACE_X
    y0, y1 = TERRACE_Y
    w, d = x1 - x0, y1 - y0
    h = 0.6
    A.platform(_n("terrace"), coll, w, d, height=h, style="plain", sink=0.8, parent=root,
               location=((x0 + x1) / 2, (y0 + y1) / 2, -h))
    e = 0.6
    # back rail is split where the pavilion platform meets the terrace (its front face spans
    # PAV.x +- 3.75 m at the back edge)
    gap = 4.4
    yb = y1 - e
    left = [(x0 + e, y0 + 8.0, 0.0), (x0 + e, yb, 0.0), (PAV[0] - gap, yb, 0.0)]
    # the right rail stops at y 0, leaving the right edge open for the side steps to the exit
    right = [(PAV[0] + gap, yb, 0.0), (x1 - e, yb, 0.0), (x1 - e, 0.0, 0.0)]
    A.balustrade(_n("rail"), coll, left, height=1.1, post_spacing=2.2, parent=root)
    A.balustrade(_n("rail"), coll, right, height=1.1, post_spacing=2.2, parent=root)
    # route on the terrace: a grey stone walk on the pavilion axis, from the front steps (y -19)
    # to the foot of the pavilion's front stair (y 20)
    A.platform(_n("walk"), coll, 4.0, 39.0, height=0.03, style="plain", mat="stone_grey",
               top_mat="stone_grey", sink=0.03, parent=root, location=(PAV[0], 0.5, 0.0))


def _approach(coll, root):
    """Arrival from the stele forest: a paved walk on the lawn (top z -0.35) from the arrival
    landing to three front steps up onto the terrace, on the pavilion axis."""
    px = PAV[0]
    y0 = TERRACE_Y[0]
    A.platform(_n("approach"), coll, 6.0, 25.0, height=0.05, style="plain", sink=0.3, parent=root,
               location=(px, -31.5, -0.4))                       # y -44 .. -19
    for sx in (-1, 1):
        P.lantern_stone(coll, 2.4, name=_n("lantern_arrival"), parent=root,
                        location=(px + sx * 4.0, -42.0, -0.35))
    A.stairs(_n("front_steps"), coll, 6.0, 0.35, ramp=False, balustrade=False, parent=root,
             location=(px, y0, -0.35))


def _exit(coll, root):
    """Way out to the formation: side steps down off the terrace's right edge, a paved exit
    walk east (top z -0.35) through a one-bay gate to the depart point."""
    x1 = TERRACE_X[1]
    A.stairs(_n("side_steps"), coll, 5.0, 0.35, ramp=False, balustrade=False, parent=root,
             location=(x1, -3.5, -0.35), rotation_z=math.pi / 2)
    A.platform(_n("exit_walk"), coll, 17.0, 5.0, height=0.05, style="plain", sink=0.3, parent=root,
               location=(35.5, -3.5, -0.4))                      # x 27 .. 44
    A.paifang(_n("exit_gate"), coll, bays=1, width=7.0, height=7.0, parent=root,
              location=(41.0, -3.5, -0.35), rotation_z=-math.pi / 2)


def _pavilion(coll, root):
    """Two-storey hexagonal pavilion (ge) with a balcony, built from the library pagoda."""
    px, py = PAV
    rad, tier_h, taper = PAV_R, 6.4, 0.08
    pav = A.pagoda(_n("pavilion"), coll, tiers=2, sides=6, radius=rad, tier_h=tier_h, taper=taper,
                   lit_floors=(0, 1), platform_h=1.5, balcony=1.1, parent=root, location=(px, py, 0.0))
    floors = list(pav["arch_floors"])
    # a pavilion, not a pagoda: shrink the tall tasha spire to a modest gold finial
    top = bpy.data.objects.get(pav.name + ".top")
    spire = bpy.data.objects.get(pav.name + ".spire")
    if top is not None and spire is not None and "arch_ridge_z" in top:
        sp_h = min(max(1.15 * tier_h, 3.0), 9.0)
        zb = top.location.z + top["arch_ridge_z"] - 0.08 * sp_h
        s = 0.4
        spire.scale = (s, s, s)
        spire.location = (0.0, 0.0, zb * (1.0 - s))
    # plaque under the upper eave, on the front face of the upper storey
    r2 = rad * (1.0 - taper)
    ap2 = r2 * math.cos(math.pi / 6)
    P.plaque(coll, AREA["title_zh"], 2.9, name=_n("plaque"), parent=root,
             location=(px, py - ap2 - 0.45, floors[1] + 2.9))
    # stone lanterns flanking the pavilion stairs, then lining the path to the terrace front
    for sx in (-1, 1):
        P.lantern_stone(coll, 2.4, name=_n("lantern_stone"), parent=root,
                        location=(px + sx * 3.6, py - 10.4, 0.0))
        for y in (-13.0, -4.0, 5.0):
            P.lantern_stone(coll, 2.4, name=_n("lantern_path"), parent=root,
                            location=(px + sx * 4.2, y, 0.0))
    # hanging lanterns at the two front corners of the lower eave (r5: lifted LANTERN_LIFT so the cord's top runs 3 cm
    # into the eave soffit; at floors[1] - 1.7 it stopped 13 cm short and the lantern hung from nothing)
    for k in (0, 1):
        a = -math.pi / 2 - math.pi / 6 + k * math.pi / 3
        r = rad + 1.6
        P.lantern_hanging(coll, "palace", 1.1, cord=0.5, name=_n("lantern"), parent=root,
                          location=(px + r * math.cos(a), py + r * math.sin(a), floors[1] - 1.7 + LANTERN_LIFT))
    return pav


def _desk(coll, root):
    """Stone desk with inkstone, brush rest, brushes and an open paper scroll."""
    dx, dy = DESK
    bm = bmesh.new()
    U.bm_box(bm, (2.8, 1.2, 0.2), (0, 0, 0.78))                 # top slab
    for sx in (-1, 1):
        U.bm_box(bm, (0.28, 1.0, 0.68), (sx * 1.15, 0, 0.34))   # end supports
    U.bm_box(bm, (2.1, 0.12, 0.25), (0, 0.35, 0.52))            # back apron
    desk = U.mesh_from_bmesh(_n("desk"), bm, coll, materials=["stone_grey"], parent=root,
                             location=(dx, dy, 0.0))
    U.bevel_mesh(desk, 0.02, 2)
    bm = bmesh.new()
    U.bm_box(bm, (0.42, 0.28, 0.07), (0.85, 0.15, 0.915))       # inkstone
    U.mesh_from_bmesh(_n("inkstone"), bm, coll, materials=["stone_dark"], parent=desk)
    bm = bmesh.new()
    U.bm_cylinder(bm, 0.11, 0.24, 12, center=(-0.9, 0.3, 1.0))   # brush pot
    U.mesh_from_bmesh(_n("brush_pot"), bm, coll, materials=["ceramic_celadon"], parent=desk)
    bm = bmesh.new()
    for x, y in ((-0.93, 0.27), (-0.86, 0.33), (-0.9, 0.36)):     # brushes standing in the pot
        U.bm_cylinder(bm, 0.014, 0.42, 8, center=(x, y, 1.2))
    U.mesh_from_bmesh(_n("brush"), bm, coll, materials=["wood_dark"], parent=desk)
    P.floating_scroll(coll, 1.3, open=True, glow=False, seed=1, name=_n("desk_scroll"), parent=desk,
                      location=(-0.05, -0.12, 0.89), rotation=(-math.pi / 2, 0, 0))
    P.cushion(coll, 0.7, "square", name=_n("cushion"), parent=root, location=(dx, dy + 1.2, 0.0))
    return desk


def _scroll(coll, root):
    """The colossal jade bamboo-slip scroll in its standing frame, and its ground ring."""
    cx, cy, cz = SCROLL_C
    sc = P.bamboo_slip_scroll(coll, SCROLL_W, SCROLL_H, curve=SCROLL_CURVE, glow=True, seed=3, rolled=True,
                              name=_n("jade_scroll"), parent=root, location=(cx, cy, cz),
                              rotation=(0.0, 0.0, SCROLL_YAW), passages=SCROLL_TEXT)
    sc.scale = (SCROLL_SCALE,) * 3
    scroll_frame(coll, root)
    # glowing script ring on the paving under it, and motes rising toward it
    P.rune_ring(coll, RING_SCRIPT[0], RING_SCRIPT[1], "script", seed=8, spin=0.02, groove=True, name=_n("ring"),
                parent=root, location=(RING_C[0], RING_C[1], 0.0))
    P.rune_ring(coll, RING_TRIGRAM[0], RING_TRIGRAM[1], "trigram", seed=9, spin=-0.03, name=_n("ring_in"),
                parent=root, location=(RING_C[0], RING_C[1], 0.0))
    P.spirit_motes(coll, 260, ((cx - 12, cy - 4, 0.6), (cx + 12, cy + 4, cz + 6)), seed=5, size=0.07,
                   rise=0.15, name=_n("motes"), parent=root)
    return sc


# ---- the scroll's standing frame (r5) --------------------------------------------------------------------------------
# The scroll used to hang in the air. Now it stands in a frame like a great screen: two round vermilion posts behind
# it, a curved sill under the slips and a top rail over them (both bowed with the scroll, joined to the posts' fronts
# with gold bands), round cradles under and over the rolled end, and the posts' feet clamped between pairs of stone
# slabs bound with iron (jiagan shi, as at a temple's flagpoles), on stone plinths. The post heads carry the Ming
# Sect's 日 + 月 = 明: a gold sun on the left post, a silver crescent moon on the right, the scroll between them.
# Everything is built in the scroll's own frame (the Empty scroll.scroll_frame shares jade_scroll's place, turn and
# 0.9 scale; numbers below are in those unscaled units, front = -Y, the slips' arc through the origin). The posts
# stand in the paving between the two rune rings (RING_TRIGRAM's outer edge 6.63 m, RING_SCRIPT's inner 8.55 m from
# RING_C), which fixes how far out along the arc each one is (frame_points).
FRAME = K + ".scroll_frame"
FRAME_ITEM = "r5_scroll_frame"     # obj['sect_item'] on every frame object (patch_r5_scroll.py finds them by it)
FRAME_RING_R = 7.59                # m (root frame) from RING_C to each post's centre: midway between the two ring bands
FRAME_POST_R = 0.42                # post radius at its foot (tapers 7 % to its head): 0.76 m across at 0.9 x
FRAME_POST_GAP = 0.22              # slips' centre line -> the post's front face (the binding cords reach 0.14 back)
FRAME_SILL = (-0.26, 0.30, 0.48)   # sill under the slips: radial front, back (+ = behind the slips) and height
FRAME_TOP = (-0.20, 0.28, 0.40)    # top rail over them
FRAME_OVER = 0.35                  # both rails run this far past the right end's outermost slip
FRAME_POST_HEAD = 0.70             # the posts rise this far above the top rail; the finial (cap, stem, emblem) on top
FRAME_PLINTH = (1.40, 2.30, 0.45, 0.12)  # stone plinth: along the scroll, along its normal, height, sunk into the paving
FRAME_CLAMP = (0.52, 1.15, 2.6, 0.42)    # clamping stones (front, back): thickness, width, height, top corner radius
FRAME_BANDS = (0.75, 1.75)         # iron bands round each pair: heights above the plinth top
FRAME_SUN = (0.64, 1.22, 0.94, 12)       # sun: disc radius, long / short ray tip radius, ray count (2.2 m across)
FRAME_MOON = 1.70                  # crescent moon: outer radius (horns up), 3.1 m across. The moon leads the sect's
                                   # 日 + 月 (owner, r5): its crescent is the larger shape, ~1.4x the sun's area
                                   # (verify r5: at 2.7 m sun / 2.3 m moon the gold sun outweighed it)
FRAME_CRADLE_PROUD = 0.04          # the roll's cradle discs stand this far proud of the rails' top and bottom faces
                                   # (verify r5: flush, the rail ends' faces lay in the cradle faces and rendered black)
FRAME_EMBLEM_T = 0.16              # emblem thickness
FRAME_BRACE = (1.5, 0.80, (0.04, 0.42))   # sparrow braces under the sill each side of a post: length along the
                                   # sill, height at the post, radial range (they run into the post's front)
FRAME_SEGS = 48                    # stations along each bowed rail


def _arc():
    """(radius, half angle) of the scroll's plan arc (props.bamboo_slip_scroll's frame_at)."""
    d = SCROLL_CURVE * SCROLL_W
    R = (SCROLL_W * SCROLL_W / 4.0 + d * d) / (2.0 * d)
    return R, math.asin(min(1.0, SCROLL_W / 2.0 / R))


def _arc_xy(a, off=0.0):
    """Scroll frame: the point at angle a on the slips' plan arc (0 = its middle, + toward its right end, the end
    nearer the pavilion), ``off`` m behind the slips (+ = back, away from the reader)."""
    R, _ = _arc()
    return ((R + off) * math.sin(a), (R + off) * math.cos(a) - R)


def scroll_to_root(p):
    """Scroll frame (unscaled) -> scroll.root's frame."""
    x, y, z = p
    s, c, sn = SCROLL_SCALE, math.cos(SCROLL_YAW), math.sin(SCROLL_YAW)
    return (SCROLL_C[0] + s * (x * c - y * sn), SCROLL_C[1] + s * (x * sn + y * c), SCROLL_C[2] + s * z)


def _ground_z():
    """The terrace top (root z 0) in the scroll frame."""
    return -SCROLL_C[2] / SCROLL_SCALE


def _post_angle(side):
    """Arc angle of the post on ``side`` (-1 left, +1 right) whose centre is FRAME_RING_R from RING_C (bisection: the
    distance grows with |a| on both sides)."""
    _, ha = _arc()
    off = FRAME_POST_GAP + FRAME_POST_R

    def dist(a):
        x, y = _arc_xy(a, off)
        X, Y, _ = scroll_to_root((x, y, 0.0))
        return math.hypot(X - RING_C[0], Y - RING_C[1])
    lo, hi = 0.0, 1.2 * ha
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if dist(side * mid) < FRAME_RING_R:
            lo = mid
        else:
            hi = mid
    return side * 0.5 * (lo + hi)


def _roll_axis():
    """Scroll frame (x, y) of the rolled end's axis and its outer radius (props.bamboo_slip_scroll rolled=True)."""
    R, ha = _arc()
    n = max(8, int(round(SCROLL_W / (SCROLL_H * 0.075))))
    pitch = SCROLL_W / n
    c0 = (R * math.sin(-ha), -R + R * math.cos(-ha))
    return (c0[0] - pitch * 1.4, c0[1] - pitch * 0.6), pitch * (0.55 + 0.13 * 0.6 * 11) + 0.44 * pitch


def _frame_levels():
    """Scroll-frame heights: sill bottom/top, top rail bottom/top, post head, finial stem top."""
    h2 = SCROLL_H / 2.0
    s0, s1 = -h2 - FRAME_SILL[2], -h2
    t0, t1 = h2, h2 + FRAME_TOP[2]
    head = t1 + FRAME_POST_HEAD
    return dict(sill=(s0, s1), top=(t0, t1), head=head, stem=head + 0.62)


def frame_points():
    """Root-frame layout of the frame, for checks and previews: post angles, post centres (x, y), the sill's and the
    emblems' heights (z)."""
    off = FRAME_POST_GAP + FRAME_POST_R
    lv = _frame_levels()
    out = dict(a_l=_post_angle(-1), a_r=_post_angle(1))
    for k, a in (("post_l", out["a_l"]), ("post_r", out["a_r"])):
        x, y = _arc_xy(a, off)
        out[k] = scroll_to_root((x, y, 0.0))[:2]
    out["sill_z"] = scroll_to_root((0.0, 0.0, 0.5 * sum(lv["sill"])))[2]
    out["top_z"] = scroll_to_root((0.0, 0.0, lv["stem"] + FRAME_MOON))[2]
    return out


def _faces_mat(bm, n0, idx):
    """Material index ``idx`` on the faces made since bm had n0 faces."""
    bm.faces.ensure_lookup_table()
    for f in bm.faces[n0:]:
        f.material_index = idx


def _basis(u, v, w, origin):
    """4x4 matrix with columns u, v, w (local x, y, z) and the translation ``origin``."""
    M = Matrix.Identity(4)
    for k, col in enumerate((u, v, w)):
        for r in range(3):
            M[r][k] = col[r]
    M.translation = Vector(origin)
    return M


def _loft_arc(bm, a0, a1, off0, off1, z0, z1, n):
    """Closed bowed beam along the slips' arc from angle a0 to a1: radial offsets off0 (front) .. off1, z0 .. z1."""
    rings = []
    for k in range(n + 1):
        a = a0 + (a1 - a0) * k / n
        ring = []
        for off, z in ((off0, z0), (off1, z0), (off1, z1), (off0, z1)):
            x, y = _arc_xy(a, off)
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)
    for k in range(n):
        A, B = rings[k], rings[k + 1]
        for c in range(4):
            c2 = (c + 1) % 4
            bm.faces.new((A[c], A[c2], B[c2], B[c]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])


def _prism_yz(bm, outline, x0, x1, M):
    """Closed prism: the 2D outline [(y, z), ...] (simple polygon) extruded along local x from x0 to x1, placed by
    the 4x4 matrix M."""
    a = [bm.verts.new(M @ Vector((x0, y, z))) for y, z in outline]
    b = [bm.verts.new(M @ Vector((x1, y, z))) for y, z in outline]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[j], a[i], b[i], b[j]))


def _plate(bm, outline, t, M):
    """Closed flat plate: the convex 2D outline [(u, v), ...] in the local xy-plane, t thick along local z (centred),
    placed by M."""
    a = [bm.verts.new(M @ Vector((u, v, -t / 2.0))) for u, v in outline]
    b = [bm.verts.new(M @ Vector((u, v, t / 2.0))) for u, v in outline]
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))


def _disc(r, n=32, cx=0.0, cy=0.0):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def _sun(bm, R_disc, r_long, r_short, rays, t, M):
    """Sun emblem in local xy (face along local z): a disc with a raised boss, ringed by ``rays`` pointed rays
    alternately long and short."""
    _plate(bm, _disc(R_disc, 36), t, M)
    _plate(bm, _disc(0.62 * R_disc, 28), t + 0.06, M)          # boss, proud of both faces
    half = math.pi / rays * 0.55
    for k in range(rays):
        th = 2 * math.pi * k / rays + math.pi / 2
        tip = r_long if k % 2 == 0 else r_short
        r0 = R_disc * 0.94
        _plate(bm, [(r0 * math.cos(th - half), r0 * math.sin(th - half)), (tip * math.cos(th), tip * math.sin(th)),
                    (r0 * math.cos(th + half), r0 * math.sin(th + half))], t * 0.6, M)


def _crescent(bm, R, t, M, n=24):
    """Crescent moon in local xy (face along local z), horns up, its lowest point at (0, -R): outer arc from horn tip
    to horn tip through the bottom, inner arc on a circle shifted up through the same tips. A closed solid."""
    a0, a1 = math.radians(150.0), math.radians(390.0)            # outer arc: left horn .. bottom .. right horn
    outer = [(R * math.cos(a0 + (a1 - a0) * k / n), R * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]
    cy = 0.28 * R                                                 # inner circle centre (0, cy) through both tips
    r2 = math.hypot(outer[0][0], outer[0][1] - cy)
    b0 = math.atan2(outer[0][1] - cy, outer[0][0])
    b1 = math.atan2(outer[-1][1] - cy, outer[-1][0]) + 2 * math.pi
    inner = [(r2 * math.cos(b0 + (b1 - b0) * k / n), cy + r2 * math.sin(b0 + (b1 - b0) * k / n)) for k in range(n + 1)]
    sides = []
    for z in (-t / 2.0, t / 2.0):
        tip0 = bm.verts.new(M @ Vector((outer[0][0], outer[0][1], z)))
        tip1 = bm.verts.new(M @ Vector((outer[-1][0], outer[-1][1], z)))
        o = [tip0] + [bm.verts.new(M @ Vector((x, y, z))) for x, y in outer[1:-1]] + [tip1]
        i = [tip0] + [bm.verts.new(M @ Vector((x, y, z))) for x, y in inner[1:-1]] + [tip1]
        sides.append((o, i))
        for k in range(n):
            if k == 0:
                bm.faces.new((o[0], o[1], i[1]))
            elif k == n - 1:
                bm.faces.new((o[k], o[k + 1], i[k]))
            else:
                bm.faces.new((o[k], o[k + 1], i[k + 1], i[k]))
    (oa, ia), (ob, ib) = sides
    for k in range(n):
        bm.faces.new((oa[k], ob[k], ob[k + 1], oa[k + 1]))
        bm.faces.new((ia[k + 1], ib[k + 1], ib[k], ia[k]))


def _finial_cap(bm, r, z, cx, cy, stem_r=0.13, h=0.62):
    """Gold cap on a post head at height z, with a short stem: profile lathe."""
    U.bm_lathe(bm, [(0.0, 0.0), (1.12 * r, 0.0), (1.22 * r, 0.10), (1.0 * r, 0.22), (0.55 * r, 0.36),
                    (stem_r, 0.42), (stem_r, h), (0.0, h)], segments=20,
               matrix=Matrix.Translation((cx, cy, z)))


def scroll_frame(coll, root):
    """Build the scroll's standing frame under the Empty scroll.scroll_frame (same place, turn and scale as
    scroll.jade_scroll). Objects: .posts (lacquer_red, gold), .rails (lacquer_red, gold), .bases (stone_grey, iron),
    .emblems (gold, silver). Returns the Empty."""
    grp = U.empty(FRAME, coll, location=SCROLL_C, parent=root, rotation=(0.0, 0.0, SCROLL_YAW),
                  scale=(SCROLL_SCALE,) * 3, display_size=2.0)
    grp["sect_item"] = FRAME_ITEM
    R, ha = _arc()
    zg = _ground_z()
    lv = _frame_levels()
    r = FRAME_POST_R
    pl_w, pl_d, pl_h, pl_sink = FRAME_PLINTH
    zp = zg + pl_h - pl_sink                    # plinth top
    ct, cw, ch, cr = FRAME_CLAMP
    off = FRAME_POST_GAP + r
    posts = []
    for side in (-1, 1):
        a = _post_angle(side)
        x, y = _arc_xy(a, off)
        tang = Vector((math.cos(a), -math.sin(a), 0.0))         # along the scroll, toward its right end
        back = Vector((math.sin(a), math.cos(a), 0.0))           # away from the reader
        posts.append((side, a, x, y, tang, back))

    # posts: lacquer shafts (slot 0) and gold bands, head caps and stems (slot 1)
    bm = bmesh.new()
    for side, a, x, y, tang, back in posts:
        n0 = len(bm.faces)
        prof = [(0.0, zp - 0.05), (r, zp - 0.05)]
        for k in range(1, 9):
            t = k / 8.0
            prof.append((r * (1.0 - 0.07 * t), zp - 0.05 + (lv["head"] - zp + 0.05) * t))
        prof.append((0.0, lv["head"]))
        U.bm_lathe(bm, prof, segments=20, matrix=Matrix.Translation((x, y, 0.0)))
        # sparrow braces (queti) under the sill on both sides of the post: a cove-curved bracket from the post's front
        # to the sill's underside, so the joint reads as carpentry and the sill's overhang as carried
        bl, bh, (b0, b1) = FRAME_BRACE
        zs = lv["sill"][0]
        ax, ay = _arc_xy(a, 0.0)
        M = _basis(back, tang, Vector((0.0, 0.0, 1.0)), (ax, ay, 0.0))
        for s in (-1, 1):
            outline = [(0.0, zs + 0.02)] + [(s * bl * (1.0 - math.sin(math.radians(10.0 * k))),
                                              zs + 0.02 - (bh + 0.02) * (1.0 - math.cos(math.radians(10.0 * k))))
                                             for k in range(10)]
            _prism_yz(bm, outline, b0, b1, M)
        _faces_mat(bm, n0, 0)
        n0 = len(bm.faces)
        rb = r * 0.985
        bands = [(zp + ch - 0.02, zp + ch + 0.16)]                       # where the shaft leaves the clamping stones
        for z0, z1 in (lv["sill"], lv["top"]):
            bands.append((z0 - 0.10, z1 + 0.10))                         # where the rails meet the post
        for z0, z1 in bands:
            rr = rb * (1.0 - 0.07 * (z0 - zp) / (lv["head"] - zp)) + 0.03
            U.bm_lathe(bm, [(0.0, z0), (rr, z0), (rr + 0.02, z0 + 0.03), (rr + 0.02, z1 - 0.03), (rr, z1), (0.0, z1)],
                       segments=20, matrix=Matrix.Translation((x, y, 0.0)))
        _finial_cap(bm, r * 0.93, lv["head"], x, y, stem_r=0.16)
        _faces_mat(bm, n0, 1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = U.mesh_from_bmesh(_n("scroll_frame", "posts"), bm, coll, materials=["lacquer_red", "gold"], smooth=None,
                           parent=grp)
    U.auto_smooth(ob, math.radians(40))
    ob["sect_item"] = FRAME_ITEM

    # rails: the bowed sill and top rail with the cradles of the rolled end (slot 0), gold strips and end caps (1)
    bm = bmesh.new()
    a1 = ha + FRAME_OVER / R
    (rx, ry), rr = _roll_axis()
    a0 = math.atan2(rx, ry + R) + 0.02                             # the rails' left ends: inside the roll's cradles
    for (f0, f1, h), (z0, z1) in ((FRAME_SILL, lv["sill"]), (FRAME_TOP, lv["top"])):
        _loft_arc(bm, a0, a1, f0, f1, z0, z1, FRAME_SEGS)
        U.bm_cylinder(bm, rr + 0.12, z1 - z0 + 2.0 * FRAME_CRADLE_PROUD, 32, center=(rx, ry, 0.5 * (z0 + z1)))
    _faces_mat(bm, 0, 0)
    old = set(bm.faces)    # (verify r5) not a face count: bm_cylinder's seam weld frees faces and the gold faces made
                           # below refill those slots, so they are not all at the end (the top cradle came out gold)
    for (f0, f1, h), (z0, z1) in ((FRAME_SILL, lv["sill"]), (FRAME_TOP, lv["top"])):
        zm = 0.5 * (z0 + z1)
        _loft_arc(bm, a0, a1 - 0.002, f0 - 0.015, f0 + 0.02, zm - 0.035, zm + 0.035, FRAME_SEGS)   # gold line
        # gold cap over the right end
        x, y = _arc_xy(a1, 0.5 * (f0 + f1))
        M = _basis((math.cos(a1), -math.sin(a1), 0.0), (math.sin(a1), math.cos(a1), 0.0), (0.0, 0.0, 1.0), (x, y, zm))
        U.bm_box(bm, (0.06, f1 - f0 + 0.06, z1 - z0 + 0.06), (0.0, 0.0, 0.0), matrix=M)
        U.bm_lathe(bm, [(0.0, zm - 0.05), (rr + 0.135, zm - 0.05), (rr + 0.145, zm), (rr + 0.135, zm + 0.05),
                        (0.0, zm + 0.05)], segments=32, matrix=Matrix.Translation((rx, ry, 0.0)))
    for f in bm.faces:
        if f not in old:
            f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = U.mesh_from_bmesh(_n("scroll_frame", "rails"), bm, coll, materials=["lacquer_red", "gold"], smooth=False,
                           parent=grp)
    U.bevel_mesh(ob, 0.025, 2)
    ob["sect_item"] = FRAME_ITEM

    # bases: plinths and clamping stones (stone_grey, slot 0), iron bands (iron, slot 1)
    bm = bmesh.new()
    for side, a, x, y, tang, back in posts:
        M = _basis(tang, back, Vector((0.0, 0.0, 1.0)), (x, y, 0.0))
        n0 = len(bm.faces)
        U.bm_box(bm, (pl_w, pl_d, pl_h), (0.0, 0.0, zg - pl_sink + pl_h / 2.0), matrix=M)
        for s in (-1, 1):                                       # front (-1) and back (+1) stones
            y0, y1 = r - 0.01, r - 0.01 + ct
            arc = [(y1 - cr + cr * math.cos(math.radians(90.0 * k / 6)), ch - cr + cr * math.sin(math.radians(90.0 * k / 6)))
                   for k in range(7)]
            outline = [(y0, 0.0), (y1, 0.0)] + arc + [(y0, ch)]
            outline = [(s * yy, zp + zz) for yy, zz in outline]
            if s < 0:
                outline.reverse()
            _prism_yz(bm, outline, -cw / 2.0, cw / 2.0, M)
        _faces_mat(bm, n0, 0)
        n0 = len(bm.faces)
        ex, ey, bt, bh = cw / 2.0 + 0.035, r - 0.01 + ct + 0.035, 0.035, 0.14
        for zb in FRAME_BANDS:
            zc = zp + zb
            for s in (-1, 1):
                U.bm_box(bm, (2 * ex, bt, bh), (0.0, s * (ey - bt / 2.0), zc), matrix=M)
                U.bm_box(bm, (bt, 2 * ey - 2 * bt, bh), (s * (ex - bt / 2.0), 0.0, zc), matrix=M)
        _faces_mat(bm, n0, 1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = U.mesh_from_bmesh(_n("scroll_frame", "bases"), bm, coll, materials=["stone_grey", "iron"], smooth=False,
                           parent=grp)
    U.bevel_mesh(ob, 0.03, 2)
    ob["sect_item"] = FRAME_ITEM

    # emblems on the post heads, facing the reader: 日 the gold sun (left), 月 the silver moon (right)
    bm = bmesh.new()
    for side, a, x, y, tang, back in posts:
        front = -back
        n0 = len(bm.faces)
        if side < 0:
            zc = lv["stem"] + FRAME_SUN[1] - 0.04
            M = _basis(tang, Vector((0.0, 0.0, 1.0)), front, (x, y, zc))
            _sun(bm, FRAME_SUN[0], FRAME_SUN[1], FRAME_SUN[2], FRAME_SUN[3], FRAME_EMBLEM_T, M)
            _faces_mat(bm, n0, 0)
        else:
            zc = lv["stem"] + FRAME_MOON - 0.04
            M = _basis(tang, Vector((0.0, 0.0, 1.0)), front, (x, y, zc))
            _crescent(bm, FRAME_MOON, FRAME_EMBLEM_T, M)
            _faces_mat(bm, n0, 1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = U.mesh_from_bmesh(_n("scroll_frame", "emblems"), bm, coll, materials=["gold", "silver"], smooth=False,
                           parent=grp)
    U.bevel_mesh(ob, 0.012, 1)
    ob["sect_item"] = FRAME_ITEM
    return grp


# ---- the six Holy Fire Tokens 圣火令 -------------------------------------------------------------------------------
# Heaven Sword and Dragon Saber ch. 29, 30, 39: the Ming Sect's regalia, cast in Persia. Six black tablets about two
# chi long, like iron rulers with no edge or blade, each a different size, "seemingly transparent yet not, with flames
# seeming to leap inside", covered in etched script and flower patterns. Built about 5x canon size so they read from
# the hold. Same Empty (scroll.slip_stack) and objects as the old jade-slip stack (scroll.slips: iron body, molten fire
# windows and edge seams; scroll.slip_caps: the etched gold inlay and the rune_gold cores). The cores sit on slip_caps so
# they get their own 'glow': one value per object scales every emissive material on it, and the white-gold core has to
# outshine the orange fire around it.
# r5 (2026-10-21): they no longer float. They stand upright in a row in the slots of a black-lacquer stand
# (scroll.token_stand: base beam with gilt slot rims, end posts with spandrels, a back rail they lean on, the sun and
# the moon on the post heads) on a low grey stone plinth (scroll.token_plinth), the longest in the middle. The Empty
# sits on the terrace at STAND_C, unturned: the stand faces -Y, its row runs along +X.
# Token frame: x along the length, y across, z out of the front face (the one the cameras see).
TOKENS = ((3.40, 0.50), (3.15, 0.46), (2.95, 0.44), (2.75, 0.41), (2.55, 0.38), (2.40, 0.35))   # L x W, bottom first
TOKEN_T = 0.12                 # thickness of every token
TOKEN_CHAMFER = 0.025          # chamfer round both faces' rims (face attribute 'edge' = 1: the iron's lighter wear rim)
TOKEN_END_R = 0.6              # plan corner radius / half width: softly rounded ends, no point, no blade
TOKEN_ARC = 6                  # segments per rounded corner
TOKEN_ORDER = (5, 3, 1, 0, 2, 4)   # TOKENS indices left to right along the stand: the longest in the middle
TOKEN_GAP = 0.20               # between neighbours in the row
TOKEN_LEAN = math.radians(10.0)   # back (toward +Y) from upright, resting on the stand's back rail: the hold camera
                                  # looks down 14 deg on the stand, so the faces tip toward it
STAND_PLINTH = ((5.0, 1.60, -0.06, 0.08), (4.70, 1.30, 0.08, 0.32), (4.90, 1.50, 0.32, 0.42))
                               # grey stone plinth, sunk 6 cm: foot, waist, top slab (x size, y size, z0, z1)
STAND_BEAM = (4.40, 0.86, 0.42, 0.74)   # black-lacquer base beam: x size, y size, z0, z1; the slots are cut in its top
SLOT_DEPTH = 0.14              # each token's lower end sits this deep in its slot
SLOT_Y = -0.08                 # the slots' line (stand frame y), a little in front of the beam's middle
STAND_RAIL_H = 1.55            # the back rail touches the tokens' backs this far above the slot bottoms
STAND_RAIL = 0.15              # back rail section (square)
STAND_POST = 0.17              # end posts (square); they stand STAND_POST_OUT outside the row's ends
STAND_POST_OUT = 0.26
STAND_EMBLEM = 0.24            # sun disc radius on the left post head (rays to 1.75x), crescent radius 1.5x on the right
STAND_STEM = 0.62              # post finial: gold bud and stem height; the emblems stand on the stem, clear above the
                               # outer tokens' tops (verify r5: at 0.22 the sun's rays and the moon cut into tokens 5 / 4)
TOKEN_SEAM = 0.010             # half height of the molten seam along the middle of each long side face
FIRE_LEN, FIRE_W = 0.70, 0.34  # flame window: share of the token's length, of its width (at the tongue tips;
                               # narrow, so each token reads black with fire inside, not as an orange bar)
FIRE_PROUD, FIRE_SINK = 0.006, 0.003
CORE_W, CORE_LEN = 0.25, 0.86  # core line: share of the window's width, of its length
CORE_PROUD = 0.0085
GOLD_PROUD, GOLD_SINK = 0.010, 0.002
GOLD_REF_W = 0.50              # the gold layout below is for the widest token; the others scale it by W / GOLD_REF_W
BORDER = (0.05, 0.04)          # border line: inset of its outer edge from the token's edge, width
BORDER_ARC = 3                 # segments per rounded corner of the border line
DOTS = (0.115, 0.011, 0.13)    # dotted line inside it: inset of the dots' centre line, dot half size, spacing
ARAB_GAP = 0.03                # end panel: starts this far beyond the fire window's tip ...
ARAB_MARGIN = 0.135            # ... and stays this far inside the token's edge (inside the dotted line)
TOKEN_BACK_DOTS = False        # dotted line on the back faces too (+1.9k triangles): the backs face the rail and +Y
TOKEN_BACK_ARABESQUES = False  # arabesques there too (+3.0k): every camera passes in front of the stand (-Y side)
TOKEN_SMOOTH = math.radians(35.0)   # edges sharper than this (and material borders) stay hard
TOKEN_TRI_BUDGET = 8000        # per object; over it the export's LOD would start to simplify the piece
TOKEN_GLOW = 0.22              # object property 'glow' on scroll.slips (molten emission scale; the jade slips had 1.6,
                               # which washes the molten windows out to pink-white; r5: 0.5 -> 0.22, a subtle fire
                               # inside black tablets now that they stand on the terrace)
CORE_GLOW = 0.9                # object property 'glow' on scroll.slip_caps (the rune_gold cores; gold ignores it)

# the flame window's upper right quarter in (u along, v across) units of its half length / half width: cubic Bezier
# spans (control 1, control 2, end, samples) from the centre notch to the pointed tip. Each tongue swells out of its
# notch and runs into a thin tip that overlaps the next tongue and hooks back, so the tongues lick toward the ends, the
# way flames stream in a draught; mirrored into the other three quarters (4 tongues per side + the 2 pointed tips).
FLAME_N0 = (0.0, 0.62)
FLAME_Q = (
    ((0.03, 0.95), (0.20, 1.04), (0.47, 0.97), 4),     # first tongue, out of the centre notch
    ((0.43, 0.80), (0.42, 0.62), (0.36, 0.50), 2),     # its tip hooks back into the next notch
    ((0.42, 0.78), (0.58, 0.90), (0.80, 0.78), 4),     # second tongue
    ((0.76, 0.62), (0.75, 0.50), (0.70, 0.40), 2),
    ((0.78, 0.56), (0.92, 0.40), (1.00, 0.00), 3),     # the end tongue: the window's pointed tip on the axis
)
CORE_U = (0.0, 0.4, 0.75, 1.0)          # core spindle stations (share of its half length)
# arabesque: an S-curved stem that springs from beside the fire's tip, swings out over the panel and back, and swells
# into a leaf (a boteh / half-palmette) that points at the token's end corner. Stem points in end panel units (U 0 at
# the panel's window side .. 1 at its end; V 0 on the axis .. 1 at its long edge) with the stroke width in metres
# (widest token); the lower scroll of each pair is the mirror image.
ARAB_STEM = ((0.00, 0.10, 0.000), (0.13, 0.50, 0.012), (0.33, 0.79, 0.017), (0.55, 0.72, 0.016),
             (0.66, 0.46, 0.018), (0.75, 0.31, 0.030), (0.87, 0.31, 0.050), (0.95, 0.46, 0.040),
             (0.98, 0.66, 0.000))
ARAB_SUB = 2                   # Catmull-Rom samples per stem span


def token_row_x():
    """Stand-frame x of each token's centre line (indexed like TOKENS), in TOKEN_ORDER from left to right."""
    widths = [TOKENS[i][1] for i in TOKEN_ORDER]
    x = -0.5 * (sum(widths) + TOKEN_GAP * (len(widths) - 1))
    out = [0.0] * len(TOKENS)
    for i, w in zip(TOKEN_ORDER, widths):
        out[i] = x + w / 2.0
        x += w + TOKEN_GAP
    return out


def token_xf(i):
    """Point map token i's frame -> the slip_stack Empty's (the stand's) frame: the token stands with its length up,
    leaning TOKEN_LEAN back, its front face toward -Y, its lower end SLOT_DEPTH deep in its slot. Token x (length) ->
    up the lean, token y (across) -> -X, token z (front) -> the front normal (right-handed)."""
    L = TOKENS[i][0]
    cl, sl = math.cos(TOKEN_LEAN), math.sin(TOKEN_LEAN)
    z_bot = STAND_BEAM[3] - SLOT_DEPTH
    cx, cy, cz = token_row_x()[i], SLOT_Y + sl * L / 2.0, z_bot + cl * L / 2.0

    def f(p):
        x, y, z = p
        return (cx - y, cy + x * sl - z * cl, cz + x * cl + z * sl)
    return f


def stand_rail():
    """(y, z) of the stand's back rail centre (stand frame): its front face touches every token's back face at
    STAND_RAIL_H above the slot bottoms."""
    cl, sl = math.cos(TOKEN_LEAN), math.sin(TOKEN_LEAN)
    z_bot = STAND_BEAM[3] - SLOT_DEPTH
    # back face of a token, s up its length from the bottom end: (SLOT_Y + sl s + cl T/2, z_bot + cl s - sl T/2)
    s = (STAND_RAIL_H + sl * TOKEN_T / 2.0) / cl
    y = SLOT_Y + sl * s + cl * TOKEN_T / 2.0 + STAND_RAIL / 2.0
    return y, z_bot + STAND_RAIL_H


def token_stand_points():
    """Root-frame layout of the stand, for checks and previews: centre (x, y), the direction it faces, top z."""
    top = STAND_BEAM[3] - SLOT_DEPTH + max(L for L, _ in TOKENS) * math.cos(TOKEN_LEAN)
    return dict(centre=STAND_C, front=(0.0, -1.0), top_z=top)


class _TokGeo:
    """Mesh as plain lists (no bpy, so tests can build it): verts, faces with a material role, an 'edge' value and a
    smooth flag, and parts. Every part is a closed solid; end() turns its faces outward by its signed volume."""

    def __init__(self):
        self.verts, self.faces, self.mat, self.edge, self.smooth = [], [], [], [], []
        self.parts = []
        self._f0 = 0

    def v(self, p):
        self.verts.append((float(p[0]), float(p[1]), float(p[2])))
        return len(self.verts) - 1

    def face(self, idx, mat, edge=0.0, smooth=False):
        self.faces.append(tuple(idx))
        self.mat.append(mat)
        self.edge.append(float(edge))
        self.smooth.append(bool(smooth))

    def begin(self):
        self._f0 = len(self.faces)

    def end(self, name):
        f0, f1 = self._f0, len(self.faces)
        if self.volume(f0, f1) < 0.0:
            for k in range(f0, f1):
                self.faces[k] = tuple(reversed(self.faces[k]))
        self.parts.append((name, f0, f1))

    def volume(self, f0, f1):
        V, vol = self.verts, 0.0
        for f in self.faces[f0:f1]:
            a = V[f[0]]
            for k in range(1, len(f) - 1):
                b, c = V[f[k]], V[f[k + 1]]
                vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) + a[1] * (b[2] * c[0] - b[0] * c[2]) +
                        a[2] * (b[0] * c[1] - b[1] * c[0]))
        return vol / 6.0

    def tris(self):
        return sum(len(f) - 2 for f in self.faces)

    def loft(self, name, rings, mat, edge, smooth, caps=True, cap_mat=None, loop=False):
        """Quads between consecutive rings of equal length (mat / edge / smooth: f(row, col)); n-gon caps on the
        first and last ring, or (loop) the last ring joined back to the first: a closed band."""
        self.begin()
        ids = [[self.v(p) for p in ring] for ring in rings]
        n, m = len(ids[0]), len(ids)
        for r in range(m if loop else m - 1):
            a, b = ids[r], ids[(r + 1) % m]
            for c in range(n):
                c2 = (c + 1) % n
                self.face((a[c], a[c2], b[c2], b[c]), mat(r, c), edge(r, c), smooth(r, c))
        if caps and not loop:
            self.face(tuple(reversed(ids[0])), cap_mat, 0.0, False)
            self.face(tuple(ids[-1]), cap_mat, 0.0, False)
        self.end(name)

    def prism(self, name, outline, z0, z1, xf, mat, edge_top=0.0, edge_wall=1.0):
        """A flat inlay: the 2D outline (simple polygon) from z0 (sunk into the surface below) to z1."""
        ring0 = [xf((x, y, z0)) for x, y in outline]
        ring1 = [xf((x, y, z1)) for x, y in outline]
        self.loft(name, [ring0, ring1], lambda r, c: mat, lambda r, c: edge_wall, lambda r, c: True, cap_mat=mat)
        f1 = self.parts[-1][2]                  # the loft's last two faces are its caps
        self.edge[f1 - 2] = self.edge[f1 - 1] = float(edge_top)

    def stud(self, name, c, t, hs, z0, z1, xf, mat):
        """Square pyramid stud: a diamond base (corners along the line's tangent t and across it), apex at z1."""
        tx, ty = t
        base = [(c[0] + tx * hs, c[1] + ty * hs), (c[0] - ty * hs, c[1] + tx * hs),
                (c[0] - tx * hs, c[1] - ty * hs), (c[0] + ty * hs, c[1] - tx * hs)]
        self.begin()
        bs = [self.v(xf((x, y, z0))) for x, y in base]
        ap = self.v(xf((c[0], c[1], z1)))
        self.face(tuple(reversed(bs)), mat, 0.0, False)
        for k in range(4):
            self.face((bs[k], bs[(k + 1) % 4], ap), mat, 1.0, False)
        self.end(name)


def _rrect(a, b, r, n=TOKEN_ARC):
    """Rounded rectangle |x| <= a, |y| <= b, corner radius r: 4 (n + 1) points counter-clockwise, starting at the
    (+x, -y) corner arc. The same n gives point-to-point matching rings (chamfers, bands)."""
    pts = []
    for cx, cy, a0 in ((a - r, -(b - r), -90.0), (a - r, b - r, 0.0), (-(a - r), b - r, 90.0),
                       (-(a - r), -(b - r), 180.0)):
        for k in range(n + 1):
            t = math.radians(a0 + 90.0 * k / n)
            pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return pts


def _inset(a, b, r, d, n=TOKEN_ARC, r_min=0.012):
    return _rrect(a - d, b - d, max(r - d, r_min), n)


def _cbez(p0, p1, p2, p3, n):
    """n points of a cubic Bezier (t = 1/n .. 1; p0 left out)."""
    out = []
    for k in range(1, n + 1):
        t = k / float(n)
        s = 1.0 - t
        out.append(tuple(s * s * s * p0[d] + 3 * s * s * t * p1[d] + 3 * s * t * t * p2[d] + t * t * t * p3[d]
                         for d in range(2)))
    return out


def _mirror4(q):
    """Closed outline from its upper right quarter q (from (0, v0) on the minor axis to (1, 0) on the major one)."""
    upper = [(-u, v) for u, v in reversed(q[1:])] + list(q)          # left tip .. centre .. right tip
    lower = [(u, -v) for u, v in reversed(upper[1:-1])]             # back along the lower side, tips not repeated
    return list(reversed(upper + lower))                            # counter-clockwise


def flame_outline(X, H):
    """The fire window: half length X, half width H at the tongue tips."""
    q = [FLAME_N0]
    for c1, c2, e, k in FLAME_Q:
        q += _cbez(q[-1], c1, c2, e, k)
    return [(u * X, v * H) for u, v in _mirror4(q)]


def core_outline(X, H):
    """The white-gold core: a spindle of half length X, half width H."""
    q = [(u, (1.0 - min(u, 1.0) ** 2) ** 0.75) for u in CORE_U]
    return [(u * X, v * H) for u, v in _mirror4(q)]


def _catmull(pts, k):
    """Catmull-Rom through pts (tuples, any length >= 2), k samples per span; the ends are kept."""
    out = [pts[0]]
    P = [pts[0]] + list(pts) + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for j in range(1, k + 1):
            t = j / float(k)
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[d] + (-p0[d] + p2[d]) * t + (2 * p0[d] - 5 * p1[d] + 4 * p2[d] - p3[d]) * t2 +
                                    (-p0[d] + 3 * p1[d] - 3 * p2[d] + p3[d]) * t3) for d in range(len(p1))))
    return out


def arabesque_outline(x0, x1, yh, s, sub=ARAB_SUB):
    """One S-scroll ending in its leaf, in the +x end panel x0..x1, 0..yh (upper half; mirror y for the lower one).
    s scales the stroke. A simple polygon: from the stem's pointed start along its left side to the leaf's pointed
    tip, back along its right side."""
    cl = _catmull([(x0 + u * (x1 - x0), v * yh, w * s) for u, v, w in ARAB_STEM], sub)
    left, right = [], []
    for i in range(1, len(cl) - 1):
        x, y, w = cl[i]
        w = max(w, 0.0)
        a, b = cl[i - 1], cl[i + 1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / d, dx / d
        left.append((x + nx * w / 2, y + ny * w / 2))
        right.append((x - nx * w / 2, y - ny * w / 2))
    return [cl[0][:2]] + left + [cl[-1][:2]] + list(reversed(right))


def token_layout(L, W):
    """2D layout of one token's face (token frame, metres): dict of outlines and the dotted line's dots."""
    a, b = L / 2.0, W / 2.0
    r = TOKEN_END_R * b
    s = W / GOLD_REF_W
    X, H = FIRE_LEN * L / 2.0, FIRE_W * W / 2.0
    lay = dict(a=a, b=b, r=r, s=s)
    lay["fire"] = flame_outline(X, H)
    lay["core"] = core_outline(CORE_LEN * X, CORE_W * H)
    lay["border"] = (_inset(a, b, r, BORDER[0] * s, n=BORDER_ARC),
                     _inset(a, b, r, (BORDER[0] + BORDER[1]) * s, n=BORDER_ARC))
    # dots: even arc-length spacing round the dotted line's rounded rectangle
    loop = _inset(a, b, r, DOTS[0] * s, n=8)
    seg = [math.hypot(loop[(k + 1) % len(loop)][0] - p[0], loop[(k + 1) % len(loop)][1] - p[1])
           for k, p in enumerate(loop)]
    per = sum(seg)
    nd = max(8, int(round(per / (DOTS[2] * s))))
    dots, k, acc = [], 0, 0.0
    for j in range(nd):
        t = per * j / nd
        while acc + seg[k] < t:
            acc += seg[k]
            k += 1
        p, q = loop[k], loop[(k + 1) % len(loop)]
        f = (t - acc) / seg[k]
        tx, ty = (q[0] - p[0]) / seg[k], (q[1] - p[1]) / seg[k]
        dots.append(((p[0] + f * (q[0] - p[0]), p[1] + f * (q[1] - p[1])), (tx, ty)))
    lay["dots"] = dots
    # the end panels' arabesque pairs
    x0, x1, yh = X + ARAB_GAP * s, a - ARAB_MARGIN * s, b - ARAB_MARGIN * s
    up = arabesque_outline(x0, x1, yh, s)
    arab = []
    for sx in (1.0, -1.0):
        for sy in (1.0, -1.0):
            pts = [(sx * x, sy * y) for x, y in up]
            arab.append(pts if sx * sy > 0 else list(reversed(pts)))
    lay["arabesques"] = arab
    return lay


def fire_token_geo(back_dots=None, back_arabesques=None):
    """(body, gold) _TokGeo of all six tokens in the slip_stack Empty's frame. body (scroll.slips): roles iron, molten;
    gold (scroll.slip_caps): roles gold, rune_gold (the cores)."""
    back_dots = TOKEN_BACK_DOTS if back_dots is None else back_dots
    back_arab = TOKEN_BACK_ARABESQUES if back_arabesques is None else back_arabesques
    body, gold = _TokGeo(), _TokGeo()
    h, c, n = TOKEN_T / 2.0, TOKEN_CHAMFER, TOKEN_ARC
    long_cols = {2 * n + 1, 4 * n + 3}          # _rrect columns of the two long straight sides
    for i, (L, W) in enumerate(TOKENS):
        xf = token_xf(i)
        lay = token_layout(L, W)
        a, b, r = lay["a"], lay["b"], lay["r"]
        rows = ((c, -h), (0.0, -h + c), (0.0, -TOKEN_SEAM), (0.0, TOKEN_SEAM), (0.0, h - c), (c, h))
        rings = [[xf((x, y, z)) for x, y in _rrect(a - d, b - d, r - d, n)] for d, z in rows]
        body.loft("token%d.body" % i, rings,
                  lambda row, col: "molten" if row == 2 and col in long_cols else "iron",
                  lambda row, col: 1.0 if row in (0, 4) else 0.0,
                  lambda row, col: True, cap_mat="iron")
        for side in (1.0, -1.0):                # front face (+z, toward the cameras), back face
            tag = "token%d.%s" % (i, "front" if side > 0 else "back")

            def zf(z, side=side):
                return side * z
            body.prism(tag + ".fire", lay["fire"], zf(h - FIRE_SINK), zf(h + FIRE_PROUD), xf, "molten", 0.0, 0.0)
            gold.prism(tag + ".core", lay["core"], zf(h + FIRE_PROUD - 0.002), zf(h + CORE_PROUD), xf, "rune_gold",
                       0.0, 0.0)
            z0, z1 = zf(h - GOLD_SINK), zf(h + GOLD_PROUD)
            outer, inner = lay["border"]
            gold.loft(tag + ".border", [[xf((x, y, z0)) for x, y in outer], [xf((x, y, z1)) for x, y in outer],
                                        [xf((x, y, z1)) for x, y in inner], [xf((x, y, z0)) for x, y in inner]],
                      lambda row, col: "gold", lambda row, col: 1.0 if row in (0, 2) else 0.0,
                      lambda row, col: row in (0, 2), loop=True)
            if side > 0 or back_dots:
                for k, (p, t) in enumerate(lay["dots"]):
                    gold.stud(tag + ".dot%d" % k, p, t, DOTS[1] * lay["s"], z0, z1, xf, "gold")
            if side > 0 or back_arab:
                for k, pts in enumerate(lay["arabesques"]):
                    gold.prism(tag + ".arabesque%d" % k, pts, z0, z1, xf, "gold", 0.0, 1.0)
    return body, gold


def _token_mesh(g, name, roles):
    """Write a _TokGeo into a new mesh: material slots in ``roles`` order, the FACE float attribute 'edge', smooth
    faces where flagged with hard edges (sharper than TOKEN_SMOOTH, between materials, or open)."""
    slot = {m: k for k, m in enumerate(roles)}
    bm = bmesh.new()
    layer = bm.faces.layers.float.new(U.EDGE_ATTR)
    vs = [bm.verts.new(p) for p in g.verts]
    for idx, m, e, sm in zip(g.faces, g.mat, g.edge, g.smooth):
        f = bm.faces.new([vs[k] for k in idx])
        f.material_index = slot[m]
        f[layer] = e
        f.smooth = sm
    bm.normal_update()
    for e in bm.edges:
        lf = e.link_faces
        e.smooth = not (len(lf) != 2 or lf[0].material_index != lf[1].material_index
                        or e.calc_face_angle(math.pi) > TOKEN_SMOOTH)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    U.set_materials(me, list(roles))
    me.update()
    me["sect_tris"] = g.tris()
    return me


FIRE_TOKEN_ROLES = (("iron", "molten"), ("gold", "rune_gold"))


def fire_token_meshes(names=(K + ".slips", K + ".slip_caps"), log=None):
    """New meshes (body, gold) of the six tokens, named ``names`` (Blender adds .001 when taken)."""
    geos = fire_token_geo()
    out = []
    for g, nm, roles in zip(geos, names, FIRE_TOKEN_ROLES):
        if g.tris() > TOKEN_TRI_BUDGET:
            raise RuntimeError("%s: %d triangles > %d" % (nm, g.tris(), TOKEN_TRI_BUDGET))
        if log:
            log(nm, "parts", len(g.parts), "faces", len(g.faces), "triangles", g.tris())
        out.append(_token_mesh(g, nm, roles))
    return tuple(out)


STAND_ITEM = "r5_token_stand"     # obj['sect_item'] on the stand's two objects (patch_r5_scroll.py finds them by it)


def token_stand(coll, grp):
    """The tokens' stand under the slip_stack Empty (its frame: z 0 the terrace top, faces -Y, row along +X):
    scroll.token_plinth (stone_grey: foot, waist, top slab) and scroll.token_stand (lacquer_black: base beam, end posts,
    spandrels, back rail; gold: the beam's front line, slot rims, post caps, the sun; silver: the moon). Returns both."""
    xs = token_row_x()
    half = max(abs(x) + TOKENS[i][1] / 2.0 for i, x in enumerate(xs))
    px = half + STAND_POST_OUT
    ry, rz = stand_rail()
    bx, by, bz0, bz1 = STAND_BEAM
    cl, sl = math.cos(TOKEN_LEAN), math.sin(TOKEN_LEAN)
    # plinth
    bm = bmesh.new()
    for sx_, sy_, z0, z1 in STAND_PLINTH:
        U.bm_box(bm, (sx_, sy_, z1 - z0), (0.0, 0.0, 0.5 * (z0 + z1)))
    plinth = U.mesh_from_bmesh(_n("token_plinth"), bm, coll, materials=["stone_grey"], smooth=False, parent=grp)
    U.bevel_mesh(plinth, 0.02, 2)
    plinth["sect_item"] = STAND_ITEM
    # lacquer stand (slot 0), gold (1), silver (2)
    bm = bmesh.new()
    U.bm_box(bm, (bx, by, bz1 - bz0), (0.0, 0.0, 0.5 * (bz0 + bz1)))                     # base beam
    post_h = rz + 0.30 - bz1
    for s in (-1, 1):
        U.bm_box(bm, (STAND_POST, STAND_POST, post_h + 0.02), (s * px, ry, bz1 - 0.02 + post_h / 2.0))   # end post
        # spandrel in front of the post's foot: a cove-curved bracket 0.30 deep, 0.42 tall, 5 cm thick
        y0 = ry - STAND_POST / 2.0 + 0.01
        prof = [(y0, bz1 - 0.005)] + [(y0 - 0.30 * (1.0 - math.sin(math.radians(15.0 * k))),
                                       bz1 - 0.005 + 0.42 * (1.0 - math.cos(math.radians(15.0 * k)))) for k in range(7)]
        _prism_yz(bm, prof, s * px - 0.025, s * px + 0.025, Matrix.Identity(4))
    U.bm_box(bm, (2.0 * px, STAND_RAIL, STAND_RAIL), (0.0, ry, rz))                        # back rail
    _faces_mat(bm, 0, 0)
    n0 = len(bm.faces)
    U.bm_box(bm, (bx + 0.012, 0.024, 0.035), (0.0, -by / 2.0, bz1 - 0.07))                # gold line on the front
    U.bm_box(bm, (bx + 0.012, 0.024, 0.035), (0.0, -by / 2.0, bz0 + 0.06))
    for i, x in enumerate(xs):                                                           # slot rims (gilt frames)
        W = TOKENS[i][1]
        yc = SLOT_Y + sl * SLOT_DEPTH / cl
        dy = TOKEN_T / cl
        for (w_, d_, ox, oy) in ((W + 0.12, 0.05, 0.0, -(dy / 2 + 0.035)), (W + 0.12, 0.05, 0.0, dy / 2 + 0.035),
                                 (0.05, dy + 0.02, -(W / 2 + 0.035), 0.0), (0.05, dy + 0.02, W / 2 + 0.035, 0.0)):
            U.bm_box(bm, (w_, d_, 0.02), (x + ox, yc + oy, bz1 + 0.006))
    zc = rz + 0.30
    for s in (-1, 1):
        _finial_cap(bm, STAND_POST * 0.62, zc, s * px, ry, stem_r=0.035, h=STAND_STEM)
    E = STAND_EMBLEM
    Ms = _basis((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0), (-px, ry, zc + STAND_STEM + 1.75 * E - 0.01))
    _sun(bm, E, 1.75 * E, 1.42 * E, 12, 0.045, Ms)
    _faces_mat(bm, n0, 1)
    n0 = len(bm.faces)
    Mm = _basis((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0), (px, ry, zc + STAND_STEM + 1.5 * E - 0.01))
    _crescent(bm, 1.5 * E, 0.045, Mm)
    _faces_mat(bm, n0, 2)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    stand = U.mesh_from_bmesh(_n("token_stand"), bm, coll, materials=["lacquer_black", "gold", "silver"], smooth=False,
                              parent=grp)
    U.bevel_mesh(stand, 0.012, 2)
    stand["sect_item"] = STAND_ITEM
    return plinth, stand


def _fire_tokens(coll, root):
    """The six Holy Fire Tokens standing in a row on their lacquer stand at STAND_C (the Empty scroll.slip_stack keeps
    the old stack's name)."""
    grp = U.empty(_n("slip_stack"), coll, location=(STAND_C[0], STAND_C[1], 0.0), parent=root)
    me_body, me_gold = fire_token_meshes()
    slips = U.object_from_mesh(_n("slips"), me_body, coll, parent=grp)
    slips["glow"] = TOKEN_GLOW
    caps = U.object_from_mesh(_n("slip_caps"), me_gold, coll, parent=grp)
    caps["glow"] = CORE_GLOW
    token_stand(coll, grp)
    return grp


def _nature(coll, root):
    # ancient pine on the rock beyond the back rail, leaning out over the cliff
    N.pine(coll, height=11, seed=2, style="ancient", name=_n("pine"), parent=root,
           location=(-19.0, 29.0, -0.3), rotation=math.radians(150))
    N.bamboo_clump(coll, count=10, height=8, seed=4, name=_n("bamboo"), parent=root,
                   location=(25.0, 26.0, -0.3))
    N.blossom_tree(coll, height=6.5, seed=1, kind="peach", name=_n("peach"), parent=root,
                   location=(22.0, 12.0, 0.0))
    # scholar rocks, each on a low marble pedestal (r5: on bare paving the tall dark rock by the back rail read as a
    # stray figure); the right-front rock sits at (22, -14), clear of the side steps' walking line at y -3.5
    for i, (x, y, s) in enumerate(ROCKS):
        rock_pedestal(coll, root, i, x, y, s)
        N.rock(coll, s, seed=i, kind="scholar", name=_n("rock", i), parent=root,
               location=(x, y, ROCK_PEDESTAL[1] - ROCK_PEDESTAL[2]))


ROCKS = ((-23.0, 14.0, 4.2), (22.0, -14.0, 2.8), (-2.0, 21.5, 3.0))   # scholar rocks: x, y, height
ROCK_PEDESTAL = (0.30, 0.36, 0.05)   # octagonal pedestal: radius per metre of rock height, height, sunk into the paving
ROCK_ITEM = "r5_rock_pedestal"       # obj['sect_item'] on each pedestal


def rock_pedestal(coll, root, i, x, y, size):
    """Low octagonal marble pedestal (foot, recessed waist, top slab) under scholar rock i: scroll.rock_pedestal.<i>.
    The rock stands on it, its base sunk into the top slab (N.rock sinks a scholar rock's base 0.12 - 0.17 m)."""
    rp = ROCK_PEDESTAL[0] * size
    z0 = -ROCK_PEDESTAL[2]
    z3 = ROCK_PEDESTAL[1] - ROCK_PEDESTAL[2]
    z1, z2 = z0 + 0.47 * (z3 - z0), z0 + 0.72 * (z3 - z0)
    bm = bmesh.new()
    for r_, a, b in ((1.0, z0, z1), (0.86, z1 - 0.01, z2 + 0.01), (0.95, z2, z3)):
        oct_ = [(rp * r_ * math.cos(math.pi / 8 + math.pi / 4 * k), rp * r_ * math.sin(math.pi / 8 + math.pi / 4 * k))
                for k in range(8)]
        _plate(bm, oct_, b - a, Matrix.Translation((0.0, 0.0, 0.5 * (a + b))))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = U.mesh_from_bmesh(_n("rock_pedestal", i), bm, coll, materials=["marble_white"], smooth=False, parent=root,
                           location=(x, y, 0.0))
    U.bevel_mesh(ob, 0.02, 2)
    ob["sect_item"] = ROCK_ITEM
    return ob


def build(collection):
    """Build the Jade Slip Pavilion at the local origin. Returns the root Empty 'scroll.root'."""
    root = U.empty("scroll.root", collection, display_size=4.0)
    _terrace(collection, root)
    _approach(collection, root)
    _exit(collection, root)
    _pavilion(collection, root)
    _desk(collection, root)
    _scroll(collection, root)
    _fire_tokens(collection, root)
    _nature(collection, root)
    return root


# preview cameras for the look.py harness (named hints; auto cams still available via --cams)
build.preview_cameras = [(h["name"], h["location"], h["target"], h["lens"]) for h in CAMERA_HINTS]
