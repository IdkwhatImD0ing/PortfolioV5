"""Huang Yaoshi's jade flute 玉簫 for the Heart-Mirror pond (sect/areas/mirror.py _flute, sect/patch_r7_flute.py).

The Legend of the Condor Heroes: Huang Yaoshi 黄药师, the Eastern Heretic 东邪 and master of Peach Blossom Island 桃花岛,
carries a jade xiao (end-blown flute) and plays 碧海潮生曲 ("The Tide Rises on the Blue Sea") on it; his island is a
maze of peach trees laid out on the eight trigrams. Here the pale jade flute lies on a flat dark slate at the pond's
east rim (pale on dark: the one contrast that still reads at the 217 hold's 52 m), its empty red brocade bag 簫囊 beside
it with a gold drawstring, its gold cord, knot, jade bead and tassel hanging over the stone's front edge, and fallen
peach petals on the stone, the lawn, the bank and the water. Nothing floats: the stone is sunk into the lawn, the bag
and the flute rest on it, the cord and tassel hang against it, the petals lie on whatever is under them (or float on
the pond). No text.

Every builder here returns a BMesh in the SET frame: origin on the nominal ground at the stone's centre, +x along the
flute (its foot end +x), -y toward the 217 hold camera (the stone's front, where the tassel hangs), z up. Every piece is
a closed solid with outward faces (bake_web's closed-piece rule). Scale: the flute is 1.9 m (about 2.5x a real
xiao, like the abode's Wanderer xiao) so it is ~55 px long in the hold at 1600 px; petals and cord follow that scale.
"""
import math

import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from sect.lib import materials as M
from sect.lib import nature as _N  # noqa: F401  (registers nature_rock_small, STONE's base)
from sect.lib import util as U

# ---------------------------------------------------------------- materials (registered here, built on first use)
JADE = M.variant("flute_jade", "jade", deep="#5ca87e", pale="#c4ebcf", sss=0.25, veins=0.14)  # pale green nephrite
# 青石: dark blue-grey layered stone; the boulders' scan-based rock, toned down so the pale flute reads on it
STONE = M.variant("flute_qingshi", "nature_rock_small", light="#606366", mid="#45484b", dark="#2b2d30",
                  warm="#59534b", cool="#454e57", moss_amt=0.35, strata=0.3, stain=0.5, joints=0.4)
SILK = M.variant("flute_silk", "cloth_red", colour="#7a0f1a", sheen=0.4, translucency=0.1)     # the flute bag
TRIM = "cloth_gold"           # the bag's drawstring band, the cord, the knot and the tassel
HOLE = "lacquer_black"        # finger holes and the bore
PETAL = M.variant("flute_petal", "foliage_blossom", colours=[(0.1, "#f0889f"), (0.45, "#f6b0c0"), (0.8, "#fbd5de"),
                                                           (1.0, "#ffeef2")], scale=14.0)    # peach petals

# ---------------------------------------------------------------- stone 青石
ROCK_A, ROCK_B, ROCK_N = 1.32, 0.74, 2.6   # superellipse half-length (x), half-depth (y), exponent
ROCK_TOP = 0.555                           # top centre (set frame z)
ROCK_SEG = 72
# side rings (outline scale, z) bottom to the top's rim: the foot at -0.34 (sunk 0.2-0.3 m into the lawn and the bank,
# clear of world.py's terrace rock at -0.4), widest at mid height, a rounded upper edge
ROCK_RINGS = ((0.955, -0.34), (0.968, -0.27), (0.98, -0.19), (0.99, -0.1), (0.996, -0.02), (1.0, 0.06),
              (1.0, 0.13), (1.0, 0.2), (0.998, 0.27), (0.993, 0.33), (0.985, 0.385), (0.972, 0.43),
              (0.952, 0.47), (0.915, 0.503), (0.865, 0.524))
ROCK_TOP_RINGS = (0.76, 0.66, 0.55, 0.43, 0.30, 0.16)  # flat top (outline scale); z from rock_top_z

# ---------------------------------------------------------------- flute bag 簫囊 (the flute's empty brocade sleeve)
BAG_LEN, BAG_W = 1.5, 0.29    # flattened sleeve; closed end -x, mouth +x
BAG_C = (0.02, 0.2)           # centre on the stone top (set frame), behind the flute
BAG_YAW = math.radians(-8.0)  # laid at a slant to the flute, its mouth toward the front: two shapes, not one stripe
BAG_THK = 0.015               # soft middle; the side seams pinch to nothing
BAG_GAP = 0.004               # under the bag
BAG_CINCH = (0.86, 0.90)      # the gold drawstring band (fraction of the length from the closed end)
BAG_MOUTH = 0.07              # half-width where the drawstring gathers it
BAG_NU, BAG_NV = 64, 10

# ---------------------------------------------------------------- flute 玉簫 (flute frame: axis +x from the blowing end)
XL = 1.90                     # length
XR = 0.048                    # outer radius (1:20)
XB = 0.027                    # bore radius
XS = 24                       # sides (a 2 x 2 quad patch is 2.3 cm: room for a round hole)
NOTCH = 0.017                 # U notch 吹口 cut into the blowing end's rim (top), depth along the axis
NOTCH_HALF = math.radians(36.0)
BANDS = ((0.030, 0.050), (0.066, 0.074), (XL - 0.074, XL - 0.066), (XL - 0.050, XL - 0.030))   # carved raised rings
BAND_H = 0.0032
HOLES = ((1.00, 0.0), (1.10, 0.0), (1.20, 0.0), (1.31, 0.0), (1.42, 0.0), (1.72, -90.0), (1.72, 90.0))
# (x from the blowing end, angle deg round the axis: 0 = up, -90 = toward the front) five finger holes on top, the
# two vent holes near the foot (the thumb hole underneath faces the stone and is not cut)
HOLE_R = 0.0095               # hole radius on the surface (inside the 2 x 2 patch round its centre vertex)
HOLE_DEPTH = 0.012
FLUTE_Y = -0.14               # the flute's axis line (set y): the front half of the top, on dark stone, in front
                              # of the bag (on the back rim it merged with the rim's highlight from the hold)
FLUTE_ROLL = math.radians(-18.0)   # turns the finger holes a little toward the hold camera

# ---------------------------------------------------------------- cord and tassel
CORD_R = 0.0065
CORD_HANG = 0.06              # cord over the rim down to the knot
KNOT_H, KNOT_W, KNOT_T = 0.08, 0.072, 0.022
BEAD_R = 0.022
TASSEL_CAP, TASSEL_LEN = 0.032, 0.24  # a full silk tassel: a gold mark on the dark stone from the hold
TASSEL_R0, TASSEL_R1 = 0.02, 0.046

# ---------------------------------------------------------------- petals
PETAL_LEN = (0.042, 0.066)
PETAL_WID = (0.80, 0.95)      # x length
PETAL_THK = 0.0035
PETAL_LIFT = 0.0008           # bottom face over the surface it lies on
PETAL_SPACING = 0.034


# ================================================================ stone

def rock_outline(th):
    """Outline point (outline scale 1) at angle ``th``: a superellipse with a slow, irregular wobble."""
    c, s = math.cos(th), math.sin(th)
    e = 2.0 / ROCK_N
    x = ROCK_A * math.copysign(abs(c) ** e, c)
    y = ROCK_B * math.copysign(abs(s) ** e, s)
    f = 1.0 + 0.045 * math.sin(3 * th + 1.1) + 0.03 * math.sin(5 * th + 2.3) + 0.018 * math.sin(9 * th + 0.4)
    return x * f, y * f


def rock_top_z(s, x, y):
    """Height of the flat top at outline scale ``s`` (0 centre .. ROCK_RINGS[-1][0] rim), a faint dome and ripple."""
    return ROCK_TOP + 0.008 * (1.0 - (s / 0.84) ** 2) + 0.004 * U.noise3((x, y, 0.0), 1.9, seed=71)


def _rock_lump(x, y, z):
    """Lumps and layered ledges on the sides (radial, metres), fading out over the rounded edge."""
    w = max(0.0, min(1.0, (0.47 - z) / 0.2))
    lump = 0.045 * U.fbm((x * 1.8, y * 1.8, z * 2.2), 1.0, octaves=4, seed=73)
    ledge = 0.008 * math.sin(z * 31.0 + 2.5 * U.noise3((x, y, 0.0), 1.1, seed=74))
    return w * (lump + ledge)


def _cut_outline(pts):
    """Clip the outline points by ROCK_CUTS half-planes (each scaled toward the centre to sit on its plane), then one
    smoothing pass so the cuts' corners stay a little rounded."""
    cut = []
    for x, y in pts:
        k = 1.0
        for deg, share in ROCK_CUTS:
            nx, ny = math.cos(math.radians(deg)), math.sin(math.radians(deg))
            reach = max(px * nx + py * ny for px, py in pts) * share
            d = x * nx + y * ny
            if d > reach:
                k = min(k, reach / d)
        cut.append((x * k, y * k))
    n = len(cut)
    return [((cut[i - 1][0] + 2 * cut[i][0] + cut[(i + 1) % n][0]) / 4,
             (cut[i - 1][1] + 2 * cut[i][1] + cut[(i + 1) % n][1]) / 4) for i in range(n)]


RIM_CHIP = {0.385: 0.3, 0.43: 0.6, 0.47: 1.0, 0.503: 1.0, 0.524: 0.6}    # ring z -> share of the rim's uneven height
# straight cleavage faces cut into the outline (direction deg, share of the outline's reach that way): a split slab,
# not a pebble
ROCK_CUTS = ((14.0, 0.93), (70.0, 0.9), (118.0, 0.94), (163.0, 0.91), (208.0, 0.92), (262.0, 0.95), (318.0, 0.9))


def _rim_chip(th):
    """Uneven height of the top's rounded rim (metres) round the outline: a worn, chipped edge."""
    return 0.011 * math.sin(7 * th + 0.5) + 0.006 * math.sin(13 * th + 2.0) + 0.004 * math.sin(23 * th + 0.3)


def rock_bm():
    """The flat blue-grey stone: ROCK_RINGS round the wobbly outline, a domed top, a bottom cap. Material 0."""
    bm = bmesh.new()
    rings = []
    ths = [2 * math.pi * j / ROCK_SEG for j in range(ROCK_SEG)]
    outl = _cut_outline([rock_outline(t) for t in ths])
    for s, z in ROCK_RINGS:
        ring = []
        chip = RIM_CHIP.get(z, 0.0)
        for th, (ox, oy) in zip(ths, outl):
            x, y = s * ox, s * oy
            k = 1.0 + _rock_lump(x, y, z) / max(0.2, math.hypot(x, y))
            ring.append(bm.verts.new((x * k, y * k, z + chip * _rim_chip(th))))
        rings.append(ring)
    for s in ROCK_TOP_RINGS:
        ring = []
        chip = 0.2 if s == ROCK_TOP_RINGS[0] else 0.0
        for th, (ox, oy) in zip(ths, outl):
            x, y = s * ox, s * oy
            ring.append(bm.verts.new((x, y, rock_top_z(s, x, y) + chip * _rim_chip(th))))
        rings.append(ring)
    top = bm.verts.new((0.0, 0.0, rock_top_z(0.0, 0.0, 0.0)))
    bot = bm.verts.new((0.0, 0.0, ROCK_RINGS[0][1] - 0.02))
    n = ROCK_SEG
    for a, b in zip(rings[:-1], rings[1:]):
        for j in range(n):
            bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
    for j in range(n):
        bm.faces.new((rings[-1][j], rings[-1][(j + 1) % n], top))
        bm.faces.new((rings[0][(j + 1) % n], rings[0][j], bot))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def bvh_of(bms):
    """One BVHTree over several BMeshes (their current coordinates)."""
    verts, polys = [], []
    for bm in bms:
        base = len(verts)
        bm.verts.index_update()
        verts.extend(v.co.copy() for v in bm.verts)
        polys.extend(tuple(base + v.index for v in f.verts) for f in bm.faces)
    return BVHTree.FromPolygons(verts, polys)


def _down(bvh, x, y, z0=3.0):
    h = bvh.ray_cast(Vector((x, y, z0)), Vector((0.0, 0.0, -1.0)), 10.0)
    return h if h[0] is not None else None


def _front_y(bvh, x, z):
    """Front-most (least y) surface point of the stone at (x, z): a ray from the camera side toward +y."""
    h = bvh.ray_cast(Vector((x, -4.0, z)), Vector((0.0, 1.0, 0.0)), 8.0)
    return h[0].y if h[0] is not None else None


# ================================================================ flute bag

def _bag_half_width(t):
    """Half-width of the flattened bag at t (0 closed end .. 1 mouth): a rounded closed end, the straight sleeve,
    the gather into the drawstring, a short frill past it."""
    w = BAG_W * 0.5
    c0, c1 = BAG_CINCH
    if t < 0.05:
        return w * max(0.3, math.sqrt(max(0.0, 1.0 - ((0.05 - t) / 0.05) ** 2)))
    if t < c0 - 0.07:
        return w
    if t < c0:
        k = (t - (c0 - 0.07)) / 0.07
        return w + (BAG_MOUTH - w) * (k * k * (3 - 2 * k))
    if t <= c1:
        return BAG_MOUTH
    k = (t - c1) / (1.0 - c1)
    return BAG_MOUTH + (w * 0.8 - BAG_MOUTH) * math.sqrt(k)


def _bag_thick(t, v):
    """Thickness at (t, v in -1..1): a soft pillow, pinched at the seams, the closed end and the mouth's frill."""
    c0, c1 = BAG_CINCH
    end = min(1.0, t / 0.035, (1.0 - t) / 0.02)
    gather = 1.25 if c0 <= t <= c1 else (0.45 if t > c1 else 1.0)
    return BAG_THK * gather * max(0.0, end) * math.sqrt(max(0.0, 1.0 - v * v))


def bag_bm(rock_bvh):
    """The empty red brocade flute bag lying flat on the stone behind the flute: a closed pillow-like shell (its
    top and bottom surfaces meet at the seams and the ends), crumpled a little, the bottom BAG_GAP over the stone.
    Material 0 silk, 1 the gold drawstring band."""
    ca, sa = math.cos(BAG_YAW), math.sin(BAG_YAW)
    bm = bmesh.new()
    top, bot = {}, {}
    for i in range(BAG_NU + 1):
        t = i / BAG_NU
        u = (t - 0.5) * BAG_LEN
        hw = _bag_half_width(t)
        wob = 0.012 * math.sin(u * 3.1 + 0.4)              # the sleeve is not laid quite straight
        for j in range(BAG_NV + 1):
            v = -1.0 + 2.0 * j / BAG_NV
            lx, ly = u, wob + v * hw * (1.0 + 0.04 * math.sin(u * 11.0 + j))
            x = BAG_C[0] + ca * lx - sa * ly
            y = BAG_C[1] + sa * lx + ca * ly
            h = _down(rock_bvh, x, y)
            if h is None:
                raise RuntimeError("flute bag: no stone under (%.2f, %.2f)" % (x, y))
            zb = h[0].z + BAG_GAP
            th = _bag_thick(t, v)
            crumple = th * (0.3 * math.sin(u * 7.0 + v * 2.0) + 0.15 * math.sin(u * 19.0 - v * 3.0))
            edge = i in (0, BAG_NU) or j in (0, BAG_NV)
            b = bm.verts.new((x, y, zb))
            bot[i, j] = b
            top[i, j] = b if edge else bm.verts.new((x, y, zb + th + crumple))
    c0, c1 = BAG_CINCH
    for i in range(BAG_NU):
        t = (i + 0.5) / BAG_NU
        m = 1 if c0 <= t <= c1 else 0
        for j in range(BAG_NV):
            f = bm.faces.new((top[i, j], top[i + 1, j], top[i + 1, j + 1], top[i, j + 1]))
            g = bm.faces.new((bot[i, j + 1], bot[i + 1, j + 1], bot[i + 1, j], bot[i, j]))
            f.material_index = g.material_index = m
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


# ================================================================ flute

def _notch(th):
    """Axial cut of the blowing end's rim at angle th (0 = top): a U, deepest at the top."""
    a = abs(math.atan2(math.sin(th), math.cos(th)))
    if a >= NOTCH_HALF:
        return 0.0
    t = a / NOTCH_HALF
    return NOTCH * (1.0 - t * t) ** 0.5


def _flute_rings():
    """[(x, radius)] stations of the outer surface, blowing end to foot, with extra stations round every hole."""
    xs = {0.0: XR - 0.001, XL - 0.006: XR, XL: XR - 0.0015}     # (no station inside the notch's depth)
    for a, b in BANDS:
        xs[a] = XR
        xs[a + 0.003] = XR + BAND_H
        xs[b - 0.003] = XR + BAND_H
        xs[b] = XR
    step = 2 * math.pi * XR / XS
    for hx, _ in HOLES:
        for k in (-1, 0, 1):
            xs[round(hx + k * step, 6)] = XR
    # even fill so long runs stay smooth in the bake (every ~0.09 m)
    keys = sorted(xs)
    for a, b in zip(keys[:-1], keys[1:]):
        n = int((b - a) / 0.09)
        for k in range(1, n + 1):
            xs.setdefault(round(a + (b - a) * k / (n + 1), 6), XR)
    out = []
    for x in sorted(xs):
        if out and x - out[-1][0] < 0.0015:
            continue
        out.append((x, xs[x]))
    return out


def flute_bm():
    """The jade xiao in its own frame (axis +x, blowing end at x 0, hole angle 0 = +z). Material 0 jade, 1 dark."""
    bm = bmesh.new()
    st = _flute_rings()
    ths = [2 * math.pi * j / XS for j in range(XS)]

    def p(x, r, th):
        return Vector((x, r * math.sin(th), r * math.cos(th)))

    rings = []
    for x, r in st:
        ring = []
        for th in ths:
            xx = x + (_notch(th) if x == 0.0 else 0.0)
            ring.append(bm.verts.new(p(xx, r, th)))
        rings.append(ring)
    n = XS
    for a, b in zip(rings[:-1], rings[1:]):
        for j in range(n):
            bm.faces.new((a[j], b[j], b[(j + 1) % n], a[(j + 1) % n]))
    # ends: rim annulus -> bore -> bore floor
    dark = []
    for end, rim in ((0, rings[0]), (1, rings[-1])):
        x0 = 0.0 if end == 0 else XL
        depth = 0.05 if end == 0 else 0.06
        sgn = 1.0 if end == 0 else -1.0
        bore_top = [bm.verts.new(p(x0 + (_notch(th) if end == 0 else 0.0), XB, th)) for th in ths]
        bore_bot = [bm.verts.new(p(x0 + sgn * depth, XB, th)) for th in ths]
        floor = bm.verts.new(Vector((x0 + sgn * (depth + 0.004), 0.0, 0.0)))
        for j in range(n):
            j2 = (j + 1) % n
            bm.faces.new((rim[j2], bore_top[j2], bore_top[j], rim[j]) if end == 0 else
                         (rim[j], bore_top[j], bore_top[j2], rim[j2]))
            dark.append(bm.faces.new((bore_top[j], bore_top[j2], bore_bot[j2], bore_bot[j]) if end == 0 else
                                     (bore_top[j2], bore_top[j], bore_bot[j], bore_bot[j2])))
            dark.append(bm.faces.new((bore_bot[j], bore_bot[j2], floor) if end == 0 else
                                     (bore_bot[j2], bore_bot[j], floor)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # finger and vent holes: the 2 x 2 quads round each hole's centre vertex, cut round and sunk
    bm.verts.ensure_lookup_table()
    xs_ = [x for x, _ in st]
    for hx, hdeg in HOLES:
        i = min(range(len(xs_)), key=lambda k: abs(xs_[k] - hx))
        th0 = math.radians(hdeg)
        j = min(range(XS), key=lambda k: abs(math.atan2(math.sin(ths[k] - th0), math.cos(ths[k] - th0))))
        c = rings[i][j]
        faces = [f for f in c.link_faces]
        if len(faces) != 4:
            raise RuntimeError("flute hole at %.3f: centre vertex has %d faces" % (hx, len(faces)))
        res = bmesh.ops.inset_region(bm, faces=faces, thickness=0.0012, depth=0.0, use_even_offset=True)
        rim_v = {v for f in faces for v in f.verts if v is not c}
        cx = c.co.x
        for v in rim_v:                            # round the inner ring on the surface
            a = math.atan2(v.co.y, v.co.z)
            dx, da = v.co.x - cx, math.atan2(math.sin(a - th0), math.cos(a - th0)) * XR
            ln = math.hypot(dx, da) or 1.0
            dx, da = dx / ln * HOLE_R, da / ln * HOLE_R
            v.co = p(cx + dx, XR, th0 + da / XR)
        res2 = bmesh.ops.inset_region(bm, faces=faces, thickness=0.0004, depth=0.0, use_even_offset=True)
        for f in res2["faces"]:
            dark.append(f)
        for v in {v for f in faces for v in f.verts}:
            a = math.atan2(v.co.y, v.co.z)
            r = math.hypot(v.co.y, v.co.z) - HOLE_DEPTH
            v.co = Vector((v.co.x, r * math.sin(a), r * math.cos(a)))
        dark.extend(faces)
    for f in dark:
        if f.is_valid:
            f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def flute_matrix(rest_bvh):
    """Flute frame -> set frame: the axis over y = FLUTE_Y, rolled FLUTE_ROLL, resting on the stone (the upper convex
    hull of the surface under the axis, the segment under the flute's middle: it touches at two points)."""
    pts = []
    for k in range(97):
        x = -XL / 2 + XL * k / 96
        h = _down(rest_bvh, x, FLUTE_Y)
        if h is None:
            raise RuntimeError("flute: no stone under x %.2f" % x)
        r = XR + (BAND_H if any(a <= x + XL / 2 <= b for a, b in BANDS) else 0.0)
        pts.append((x, h[0].z + r))
    hull = []
    for q in pts:                                    # upper hull, left to right (monotone chain)
        while len(hull) >= 2 and ((hull[-1][0] - hull[-2][0]) * (q[1] - hull[-2][1]) -
                                  (hull[-1][1] - hull[-2][1]) * (q[0] - hull[-2][0])) >= 0:
            hull.pop()
        hull.append(q)
    seg = None
    for a, b in zip(hull[:-1], hull[1:]):
        if a[0] <= 0.0 <= b[0]:
            seg = (a, b)
    if seg is None:
        raise RuntimeError("flute: no resting segment under the middle")
    (xa, za), (xb, zb) = seg
    slope = (zb - za) / (xb - xa)
    z0 = za + slope * (0.0 - xa) + 0.0004
    pitch = math.atan(slope)
    rest = (round(xa, 3), round(xb, 3))
    m = (Matrix.Translation((0.0, FLUTE_Y, z0)) @ Matrix.Rotation(-pitch, 4, 'Y') @
         Matrix.Translation((-XL / 2, 0.0, 0.0)) @ Matrix.Rotation(-FLUTE_ROLL, 4, 'X'))
    return m, rest


def hole_point(m, hx, hdeg, out=0.0):
    """Set-frame point at a hole's centre (``out`` metres along its outward normal; negative = into the hole)."""
    th = math.radians(hdeg)
    r = XR + out
    return m @ Vector((hx, r * math.sin(th), r * math.cos(th)))


# ================================================================ cord and tassel

def _tube(bm, pts, radius, sides=8):
    """Closed tube along pts (Vectors) with flat end caps; radius a float or one per point."""
    rr = radius if isinstance(radius, (list, tuple)) else [radius] * len(pts)
    rings = []
    prev_n = None
    for k, c in enumerate(pts):
        t = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
        if prev_n is None:
            up = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            nrm = (up - t * up.dot(t)).normalized()
        else:
            nrm = (prev_n - t * prev_n.dot(t)).normalized()
        prev_n = nrm
        bi = t.cross(nrm)
        rings.append([bm.verts.new(c + (nrm * math.cos(2 * math.pi * j / sides) +
                                         bi * math.sin(2 * math.pi * j / sides)) * rr[k]) for j in range(sides)])
    for a, b in zip(rings[:-1], rings[1:]):
        for j in range(sides):
            bm.faces.new((a[j], a[(j + 1) % sides], b[(j + 1) % sides], b[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])


def _lathe_z(bm, profile, centre, segments=16, squash_y=1.0, ridges=0.0):
    """Closed solid of revolution round a vertical axis through ``centre``; profile [(r, dz)] top to bottom (dz <= 0),
    r 0 = a pole. squash_y flattens it front to back; ridges adds tassel-strand fluting."""
    rings = []
    for r, dz in profile:
        if r <= 1e-7:
            rings.append([bm.verts.new(centre + Vector((0.0, 0.0, dz)))])
            continue
        ring = []
        for j in range(segments):
            a = 2 * math.pi * j / segments
            rj = r * (1.0 + (ridges if j % 2 else -ridges))
            ring.append(bm.verts.new(centre + Vector((rj * math.cos(a), rj * math.sin(a) * squash_y, dz))))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for j in range(segments):
            j2 = (j + 1) % segments
            if len(a) == 1:
                bm.faces.new((a[0], b[j2], b[j]))
            elif len(b) == 1:
                bm.faces.new((a[j], a[j2], b[0]))
            else:
                bm.faces.new((a[j], a[j2], b[j2], b[j]))
    if len(rings[0]) > 1:
        bm.faces.new(rings[0])
    if len(rings[-1]) > 1:
        bm.faces.new(list(reversed(rings[-1])))


def _hang_y(bvh, x, z, y_prev, r):
    """y of a hanging piece's axis at height z: against the front-most surface (minus r), never back in."""
    yf = _front_y(bvh, x, z)
    y = y_prev if yf is None else min(y_prev, yf - r)
    return y


def _clear(bvh, p, r):
    """Push point p out of the surface along the nearest-surface direction until it is r away (resting on it)."""
    for _ in range(4):
        h = bvh.find_nearest(p)
        if h[0] is None or h[3] >= r - 1e-5:
            return p
        d = p - h[0]
        n = d.normalized() if d.length > 1e-7 else h[1]
        if n.dot(h[1]) < 0:            # inside: leave along the face normal
            n = h[1]
        p = h[0] + n * r
    return p


def _densify(pts, step):
    out = [pts[0]]
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int(math.ceil((b - a).length / step)))
        out.extend(a.lerp(b, k / n) for k in range(1, n + 1))
    return out


def _settle(piece, bvh, direction, step=0.0012, tries=60):
    """Move a separate BMesh piece along ``direction`` in small steps until it no longer overlaps ``bvh`` (it then
    rests within one step of the surface). Returns the distance moved."""
    moved = 0.0
    for _ in range(tries):
        if not BVHTree.FromBMesh(piece).overlap(bvh):
            return moved
        bmesh.ops.translate(piece, vec=direction * step, verts=piece.verts)
        moved += step
    raise RuntimeError("flute tassel: a piece still intersects the stone or the bag after %.3f m" % moved)


def _append(dst, src, mat):
    """Copy BMesh ``src`` into ``dst`` with material index ``mat``; frees src."""
    vmap = {v: dst.verts.new(v.co) for v in src.verts}
    for f in src.faces:
        dst.faces.new([vmap[v] for v in f.verts]).material_index = mat
    src.free()


def tassel_bm(m_flute, both_bvh):
    """Gold cord from the front vent hole, across the stone (and the bag), over the stone's front rim and hanging
    against its face: a gold 盘长 knot, a jade bead, a gold tassel, each resting against the stone. Materials 0
    gold, 1 jade. Returns (bm, lowest z, tassel top centre)."""
    hx, hdeg = HOLES[5]
    p0 = hole_point(m_flute, hx, hdeg, -0.008)
    p1 = hole_point(m_flute, hx, hdeg, 0.014)
    x = p1.x + 0.04
    rc = CORD_R + 0.0012
    pts = [p0, p1]
    # across the top toward the front, on the stone and the bag
    y = p1.y - 0.04
    z_last = None
    while True:
        h = _down(both_bvh, x, y)
        if h is None or h[1].z < 0.6:
            break
        z_last = h[0].z
        pts.append(Vector((x, y, h[0].z + rc)))
        y -= 0.025
        x += 0.004
    if z_last is None:
        raise RuntimeError("flute cord: no stone in front of the vent hole")
    # over the rim and down, against the front-most surface
    yc = pts[-1].y
    z = z_last - 0.008
    z_knot = z_last - CORD_HANG
    while z > z_knot:
        yc = _hang_y(both_bvh, x, z, yc, rc)
        pts.append(Vector((x, yc, z)))
        z -= 0.015
    yc = _hang_y(both_bvh, x, z_knot, yc, rc)
    pts.append(Vector((x, yc, z_knot)))
    # dense, every point pushed clear of the stone and the bag (the start stays inside the vent hole)
    pts = pts[:2] + [_clear(both_bvh, q, rc) for q in _densify(pts[1:], 0.012)[1:]]
    bm = bmesh.new()
    cord = bmesh.new()
    _tube(cord, pts, CORD_R, sides=8)
    _settle(cord, both_bvh, Vector((0.0, -0.6, 0.8)).normalized())
    _append(bm, cord, 0)
    end = pts[-1]
    # knot: a flat diamond hanging under the cord's end, against the stone
    zk0 = end.z + 0.003
    knot = bmesh.new()
    _lathe_z(knot, [(0.0, 0.0), (KNOT_W * 0.25, -KNOT_H * 0.18), (KNOT_W * 0.5, -KNOT_H * 0.5),
                    (KNOT_W * 0.25, -KNOT_H * 0.82), (0.0, -KNOT_H)], Vector((end.x, end.y, zk0)), segments=12,
             squash_y=KNOT_T / KNOT_W)
    yk = end.y - _settle(knot, both_bvh, Vector((0.0, -1.0, 0.0)))
    _append(bm, knot, 0)
    # jade bead under the knot
    zb = zk0 - KNOT_H - 0.012
    bead = bmesh.new()
    prof = [(0.0, 0.0)] + [(BEAD_R * math.sin(math.pi * k / 8), BEAD_R * math.cos(math.pi * k / 8) - BEAD_R)
                           for k in range(1, 8)] + [(0.0, -2 * BEAD_R)]
    _lathe_z(bead, prof, Vector((end.x, yk, zb)), segments=14)
    yb = yk - _settle(bead, both_bvh, Vector((0.0, -1.0, 0.0)))
    _append(bm, bead, 1)
    link = bmesh.new()
    _tube(link, [Vector((end.x, yk, zk0 - KNOT_H + 0.006)), Vector((end.x, yb, zb - 0.003))], CORD_R * 0.8, sides=6)
    _settle(link, both_bvh, Vector((0.0, -1.0, 0.0)))
    _append(bm, link, 0)
    # tassel: cap and fluted strands
    zt = zb - 2 * BEAD_R - 0.006
    tas = bmesh.new()
    _lathe_z(tas, [(0.0, 0.0), (TASSEL_R0 * 0.8, -0.004), (TASSEL_R0, -0.012), (TASSEL_R0 * 1.05, -TASSEL_CAP),
                   (TASSEL_R0 * 0.92, -TASSEL_CAP - 0.004), (TASSEL_R0 * 1.15, -TASSEL_CAP - 0.02),
                   (TASSEL_R1 * 0.8, -TASSEL_CAP - TASSEL_LEN * 0.55), (TASSEL_R1, -TASSEL_CAP - TASSEL_LEN * 0.92),
                   (TASSEL_R1 * 0.85, -TASSEL_CAP - TASSEL_LEN), (0.0, -TASSEL_CAP - TASSEL_LEN - 0.004)],
             Vector((end.x, yb, zt)), segments=18, ridges=0.06)
    yt = yb - _settle(tas, both_bvh, Vector((0.0, -1.0, 0.0)))
    _append(bm, tas, 0)
    link = bmesh.new()
    _tube(link, [Vector((end.x, yb, zb - 2 * BEAD_R + 0.004)), Vector((end.x, yt, zt - 0.004))], CORD_R * 0.8,
          sides=6)
    _settle(link, both_bvh, Vector((0.0, -1.0, 0.0)))
    _append(bm, link, 0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    low = min(v.co.z for v in bm.verts)
    return bm, low, Vector((end.x, yt, zt))


# ================================================================ petals

def petal_outline(length, width):
    """Peach petal (u along its length from the base, v across): base, sides, two tip lobes and the notch between."""
    L, W = length, width
    return [(-0.5 * L, 0.0), (0.0, -0.5 * W), (0.5 * L, -0.22 * W), (0.4 * L, 0.0), (0.5 * L, 0.22 * W),
            (0.0, 0.5 * W)]


def add_petal(bm, centre, normal, yaw, length, width, cup=0.16):
    """A closed, cupped petal prism lying on a surface: bottom face PETAL_LIFT over ``centre`` along ``normal``."""
    n = Vector(normal).normalized()
    ref = Vector((math.cos(yaw), math.sin(yaw), 0.0))
    u = (ref - n * ref.dot(n))
    if u.length < 1e-6:
        u = Vector((1, 0, 0)) - n * n.x
    u.normalize()
    v = n.cross(u)
    ol = petal_outline(length, width)
    bot, top = [], []
    for (pu, pv) in ol:
        lift = cup * width * (pv / (0.5 * width)) ** 2 + 0.08 * width * max(0.0, pu / (0.5 * length)) ** 2
        base = Vector(centre) + u * pu + v * pv + n * (PETAL_LIFT + lift)
        bot.append(bm.verts.new(base))
        top.append(bm.verts.new(base + n * PETAL_THK))
    k = len(ol)
    # fan from the base vertex (the outline is star-shaped from it)
    for i in range(1, k - 1):
        bm.faces.new((top[0], top[i], top[i + 1]))
        bm.faces.new((bot[0], bot[i + 1], bot[i]))
    for i in range(k):
        j = (i + 1) % k
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    return [Vector(centre) + u * pu + v * pv for (pu, pv) in ol]


def scatter_petals(rng, sampler, centre, count_top, count_ground, inside_rock, top_sampler, keep_off=None):
    """Petal placements [(point, normal, yaw, length, width, where)] in the set frame.

    sampler(x, y) -> (point, normal, kind) or None: the scene under a set-frame (x, y) ('ground', 'path', 'stone',
    'water' or 'set' for the flute set). top_sampler(x, y) -> (point, normal) on the stone/bag or None.
    inside_rock(x, y) -> True under the stone; keep_off(x, y) -> True where no petal may lie on the top (the cord).
    Each petal is accepted only when the surface under all its outline
    points is the same kind and within a few millimetres of the petal's plane."""
    out = []
    grid = {}

    def free(p):
        gx, gy = int(math.floor(p.x / PETAL_SPACING)), int(math.floor(p.y / PETAL_SPACING))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for q in grid.get((gx + dx, gy + dy), ()):
                    if (q - p).length < PETAL_SPACING:
                        return False
        return True

    def take(p):
        grid.setdefault((int(math.floor(p.x / PETAL_SPACING)), int(math.floor(p.y / PETAL_SPACING))), []).append(p)

    def flat_ok(pt, nrm, L, W, yaw, sample, want):
        n = Vector(nrm).normalized()
        ref = Vector((math.cos(yaw), math.sin(yaw), 0.0))
        u = (ref - n * ref.dot(n)).normalized()
        v = n.cross(u)
        for (pu, pv) in petal_outline(L, W):
            q = pt + u * pu + v * pv
            s = sample(q.x, q.y)
            if s is None or (want is not None and s[2] != want):
                return False
            d = (s[0] - q).dot(n)          # the surface must stay under the petal, at most 6 mm under it
            if d > 0.0004 or d < -0.006:
                return False
        return True

    def one(where, x, y):
        L = rng.uniform(*PETAL_LEN)
        W = L * rng.uniform(*PETAL_WID)
        yaw = rng.uniform(0.0, 2 * math.pi)
        if where == "set":
            s = top_sampler(x, y)
            if s is None or s[1].z < 0.9:
                return False
            pt, nrm = s
            kind = None

            def samp(qx, qy):
                r = top_sampler(qx, qy)
                return None if r is None or r[1].z < 0.85 else (r[0], r[1], None)
        else:
            s = sampler(x, y)
            if s is None:
                return False
            pt, nrm, kind = s
            if where == "water" and kind != "water":
                return False
            if where == "ground" and kind not in ("ground", "path", "stone"):
                return False
            samp = sampler
        if not free(pt) or not flat_ok(pt, nrm, L, W, yaw, samp, kind):
            return False
        take(pt)
        out.append((pt, Vector(nrm), yaw, L, W, where if where != "ground" else kind))
        return True

    cx, cy = centre
    # on the stone and the bag
    n, tries = 0, 0
    while n < count_top and tries < count_top * 40:
        tries += 1
        x, y = rng.uniform(-ROCK_A * 0.95, ROCK_A * 0.95), rng.uniform(-ROCK_B * 0.9, ROCK_B * 0.9)
        if abs(y - FLUTE_Y) < XR + 0.05 and abs(x) < XL / 2 + 0.06:
            continue
        if keep_off is not None and keep_off(x, y):
            continue
        n += one("set", x, y)
    # ground drift: a soft blob round the stone (heavier toward the pond and the front) plus a band hugging its foot
    n, tries = 0, 0
    while n < count_ground and tries < count_ground * 60:
        tries += 1
        if rng.random() < 0.55:          # drifted against the stone's foot
            th = rng.uniform(0.0, 2 * math.pi)
            ox, oy = rock_outline(th)
            k = 1.0 + 0.3 * rng.random() ** 1.6
            x, y = cx + ox * k, cy + oy * k
        else:                            # thinning out round it, more toward the pond and the front
            x = cx + rng.gauss(-0.45, 1.05)
            y = cy + rng.gauss(-0.3, 0.8)
        if inside_rock(x, y):
            continue
        n += one("ground", x, y)
    return out


def scatter_water(rng, sampler, box, count):
    """Petals floating on the pond inside ``box`` (set frame x0, x1, y0, y1): drifted along the shore."""
    out = []
    n, tries = 0, 0
    x0, x1, y0, y1 = box
    grid = {}
    while n < count and tries < count * 80:
        tries += 1
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        s = sampler(x, y)
        if s is None or s[2] != "water":
            continue
        L = rng.uniform(*PETAL_LEN)
        W = L * rng.uniform(*PETAL_WID)
        yaw = rng.uniform(0.0, 2 * math.pi)
        ok = True
        for (pu, pv) in petal_outline(L, W):
            q = sampler(x + pu * math.cos(yaw) - pv * math.sin(yaw), y + pu * math.sin(yaw) + pv * math.cos(yaw))
            if q is None or q[2] != "water":
                ok = False
                break
        if not ok:
            continue
        key = (int(x // PETAL_SPACING), int(y // PETAL_SPACING))
        if any((Vector((x, y, 0)) - q).length < PETAL_SPACING for dx in (-1, 0, 1) for dy in (-1, 0, 1)
               for q in grid.get((key[0] + dx, key[1] + dy), ())):
            continue
        grid.setdefault(key, []).append(Vector((x, y, 0)))
        out.append((s[0], Vector((0, 0, 1)), yaw, L, W, "water"))
        n += 1
    return out
