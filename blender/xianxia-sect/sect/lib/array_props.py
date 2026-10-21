"""Props of the round-6 Grand Sect-Protecting Formation 护宗大阵 (sect/areas/formation.py).

The array is carved stone and cast bronze with the light inside it (in grooves, in fire bowls, in a jade eye):

- station_proto(pc): the array-eye station 陣眼, a huabiao column: octagonal plinth with a lotus die, an octagonal
  column with a stone dragon coiling up it, bronze bands, a cloud plate 云板 piercing it, a lotus dew plate 承露盘,
  a bronze four-claw cradle and the glowing jade eye. Origin on the floor, local +X outward (the instances turn it).
- station_plaque(...): the station's trigram on a bronze plaque on the column's inward face (one per station).
- brazier(...): bronze tripod holy-fire brazier 圣火盆 with coals, a lofted flame and a warm point light.
- armillary(...): the bronze armillary sphere 浑天仪 on four dragon pillars (static frame) and its turning rings with
  the sun-fire core (children of the turning Empty).
- flag_drum(...): the octagonal stone drum under each of the Five Element Banners 五行旗, with the sect's emblem.
- star_stone(...): a Big Dipper 天罡北斗 star-stone on a round two-step platform.
- floor inlays: bagua(), jade_channel(), radial_channels(), chant_ring(), moss().

Plain bmesh builders in the area's local frame (metres, z = 0 the plaza top, front -Y). Every object they make
carries the custom property TAG, and so does every mesh of their own, so sect/patch_r6_formation.py can remove a
previous run. props.py is not edited: its public builders and some of its geometry helpers are called as they are.
"""

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

from sect.lib import util as U
from sect.lib import props as P

TAU = 2.0 * math.pi
TAG = "formation_r6"
OCT = 1.0 / math.cos(math.pi / 8)       # octagon circumradius / apothem

# materials (registered by formation._materials)
M_MARBLE = "formation_marble_aged"
M_CARVED = "formation_stone_carved"
M_BLUE = "formation_paving_bluestone"
M_INK = "formation_paving_ink"
M_LEAK = "formation_rune_goldleak"
M_JADE = "formation_rune_jade"
M_STAR = "formation_rune_star"
M_SUN = "formation_rune_sun"
M_EYE = "formation_jade_glow_eye"
M_BRONZE = "props_bronze_aged"
M_VERD = "bronze_verdigris"
M_GOLD = "gold"
M_FLAME = "props_flame"

# ---------------------------------------------------------------- station layout (station frame, +X outward)
PLINTH_A = 3.0                         # apothem of the bottom step (circumradius 3.25)
PLINTH_TOP = 1.30
COL_Z0, COL_Z1 = 1.25, 8.85            # column shaft
COL_A0, COL_A1 = 1.15, 0.95            # apothem at the foot / top (2.3 m / 1.9 m across the flats)
CLOUD_Z = 7.0                          # cloud plate centre
DEW_Z = (8.66, 9.18)
EYE_Z, EYE_R = 10.6, 1.1
DRAGON_Z = (2.75, 6.0)                 # tail .. neck on the column
DRAGON_TURNS = 1.5
PLAQUE_Z = 2.25

TRIGRAM_LINES = {                      # bottom (inner) line first; 1 = yang (whole), 0 = yin (split)
    "乾": (1, 1, 1), "兑": (1, 1, 0), "离": (1, 0, 1), "震": (1, 0, 0),
    "巽": (0, 1, 1), "坎": (0, 1, 0), "艮": (0, 0, 1), "坤": (0, 0, 0),
}


# ================================================================ object helpers

def tag(ob):
    ob[TAG] = 1
    return ob


def tag_tree(ob):
    """Tag ``ob`` and everything parented under it (props.py builders' roots)."""
    tag(ob)
    for c in ob.children_recursive:
        tag(c)
    return ob


def _smooth(me, smooth):
    if smooth is True:
        me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    elif smooth is False:
        U.shade_flat(me)
    elif isinstance(smooth, (int, float)):
        U.auto_smooth(me, float(smooth))


def mk(name, bm, coll, mats, parent=None, smooth=None, glow=None, shadow=True, bevel=0.0, seg=2,
       angle=math.radians(30), **place):
    """BMesh -> a new tagged object (its own tagged mesh)."""
    ob = U.mesh_from_bmesh(name, bm, coll, materials=mats, smooth=smooth, parent=parent, **place)
    if bevel > 0:
        U.bevel_mesh(ob, bevel, seg, angle)
    if glow is not None:
        ob["glow"] = float(glow)
    if not shadow:
        U.set_visibility(ob, shadow=False)
    ob.data[TAG] = 1
    return tag(ob)


def shared(key, build, mats, smooth=None, bevel=0.0, seg=2, angle=math.radians(30)):
    """Mesh data ``key`` shared by several objects (braziers, star-stones, drums), built once by build() -> BMesh."""
    me = bpy.data.meshes.get(key)
    if me is not None and me.get("sect_shared") == key and me.get(TAG):
        return me
    bm = build()
    me = bpy.data.meshes.new(key)
    bm.to_mesh(me)
    bm.free()
    _smooth(me, smooth)
    U.set_materials(me, mats)
    if bevel > 0:
        U.bevel_mesh(me, bevel, seg, angle)
    me["sect_shared"] = key
    me[TAG] = 1
    return me


def obj(name, me, coll, parent=None, glow=None, shadow=True, **place):
    ob = U.object_from_mesh(name, me, coll, parent=parent, **place)
    if glow is not None:
        ob["glow"] = float(glow)
    if not shadow:
        U.set_visibility(ob, shadow=False)
    return tag(ob)


# ================================================================ geometry helpers

def frame(fwd, up=(0.0, 0.0, 1.0), pos=(0.0, 0.0, 0.0)):
    """4x4: local +X along ``fwd``, +Z as close to ``up`` as possible, +Y = Z x X (right-handed)."""
    f = Vector(fwd).normalized()
    u = Vector(up)
    s = u.cross(f)
    if s.length < 1e-6:
        s = Vector((0.0, 1.0, 0.0)).cross(f)
    s.normalize()
    u = f.cross(s).normalized()
    m = Matrix((f, s, u)).transposed().to_4x4()
    m.translation = Vector(pos)
    return m


def rect_section(w, h, c=0.0):
    """Closed section [(radial, axial)] of a w x h rectangle with chamfer c, counter-clockwise."""
    a, b = w / 2.0, h / 2.0
    if c <= 0:
        return [(a, -b), (a, b), (-a, b), (-a, -b)]
    return [(a, -b + c), (a, b - c), (a - c, b), (-a + c, b), (-a, b - c), (-a, -b + c), (-a + c, -b), (a - c, -b)]


def ring(bm, R, section, segs=96, matrix=None, mat=0, a0=0.0, a1=TAU):
    """Sweep a closed section [(dr, dz)] round a circle of radius R in XY (z up); then ``matrix``. Returns verts."""
    full = (a1 - a0) >= TAU - 1e-6
    cols = segs if full else segs + 1
    n = len(section)
    rings = []
    for i in range(cols):
        a = a0 + (a1 - a0) * i / segs
        c, s = math.cos(a), math.sin(a)
        rings.append([bm.verts.new(((R + dr) * c, (R + dr) * s, dz)) for dr, dz in section])
    for i in range(segs):
        A, B = rings[i], rings[(i + 1) % cols]
        for k in range(n):
            k2 = (k + 1) % n
            bm.faces.new((A[k], B[k], B[k2], A[k2]))
    if not full:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    vs = [v for r in rings for v in r]
    if matrix is not None:
        P._xf(bm, matrix, vs)
    if mat:
        for f in P._faces_of(vs):
            f.material_index = mat
    return vs


def lathe(bm, profile, segs=32, matrix=None, mat=0, rmod=None, zmod=None, caps=(True, True), phase=0.0):
    rs = P._lathe(bm, profile, segs, rmod=rmod, zmod=zmod, cap_start=caps[0], cap_end=caps[1], matrix=matrix,
                  phase=phase, mat=mat)
    return [v for r in rs for v in r]


def oct_lathe(bm, profile, matrix=None, mat=0, caps=(True, True)):
    """Octagonal-plan lathe, profile [(apothem, z)], flat sides facing +-X and +-Y."""
    return lathe(bm, [(a * OCT, z) for a, z in profile], 8, matrix=matrix, mat=mat, caps=caps, phase=math.pi / 8)


def tube(bm, pts, r, sides=8, samples=4, mat=0, caps=True):
    rs = P._tube(bm, pts, r, sides=sides, samples=samples, mat=mat, caps=caps)
    return [v for rr in rs for v in rr]


def cone(bm, base, tip, r, sides=5, mat=0):
    """Closed cone from a circle of radius r at ``base`` to a point at ``tip``."""
    base, tip = Vector(base), Vector(tip)
    m = frame(tip - base, (0, 0, 1) if abs((tip - base).normalized().z) < 0.95 else (1, 0, 0), base)
    ring_ = [bm.verts.new(m @ Vector((0.0, r * math.cos(TAU * k / sides), r * math.sin(TAU * k / sides))))
             for k in range(sides)]
    t = bm.verts.new(tip)
    for k in range(sides):
        f = bm.faces.new((ring_[k], ring_[(k + 1) % sides], t))
        f.material_index = mat
    f = bm.faces.new(list(reversed(ring_)))
    f.material_index = mat
    return ring_ + [t]


def prism_x(bm, outline, x0, x1, matrix=None, mat=0):
    """Extrude a 2D outline [(u, v)] (u -> local Y, v -> local Z) through X from x0 to x1."""
    a = [bm.verts.new((x0, u, v)) for u, v in outline]
    b = [bm.verts.new((x1, u, v)) for u, v in outline]
    n = len(outline)
    fa = bm.faces.new(a)
    fb = bm.faces.new(list(reversed(b)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], b[i], b[j], a[j]))
    vs = a + b
    if matrix is not None:
        P._xf(bm, matrix, vs)
    for f in P._faces_of(vs):
        f.material_index = mat
    del fa, fb
    return vs


def flat_poly(bm, pts, z, mat=0):
    """Flat ngon at height z facing +Z from 2D points (any winding)."""
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts)))
    if area < 0:
        pts = list(reversed(pts))
    f = bm.faces.new([bm.verts.new((x, y, z)) for x, y in pts])
    f.material_index = mat
    return f


def slab_poly(bm, pts, z0, z1, mat=0):
    """Closed prism of a 2D polygon from z0 to z1."""
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts)))
    if area < 0:
        pts = list(reversed(pts))
    lo = [bm.verts.new((x, y, z0)) for x, y in pts]
    hi = [bm.verts.new((x, y, z1)) for x, y in pts]
    n = len(pts)
    fs = [bm.faces.new(list(reversed(lo))), bm.faces.new(hi)]
    for i in range(n):
        j = (i + 1) % n
        fs.append(bm.faces.new((lo[i], lo[j], hi[j], hi[i])))
    for f in fs:
        f.material_index = mat
    return lo + hi


def text_glyph(bm, ch, height, matrix, mat=0, extrude=0.0, res=2):
    """One KaiTi glyph scaled so its larger side is ``height``, laid in XY (readable from +Z, glyph up +Y),
    centred on the origin, then ``matrix``."""
    me = P._text_mesh(ch, 1.0, res, extrude=extrude)
    d = P._mesh_dims(me)
    k = height / max(d.x, d.y, 1e-6)
    P._add_mesh(bm, me, Matrix(matrix) @ Matrix.Diagonal((k, k, 1.0, 1.0)), mat)


# ================================================================ dragon (shared by the station and the armillary)

def dragon_head(bm, M, s=1.0, mat=0, mat_eye=0):
    """Chinese dragon head in the frame M (+X the snout, +Z up), ``s`` scales (skull ~0.5 s wide): skull, brows,
    long snout with a nose pad, an open lower jaw, fangs, eyes, two antler horns, a flame mane, whiskers, beard."""
    S = M @ Matrix.Diagonal((s, s, s, 1.0))
    vs = []
    vs += P._rbox(bm, (0.26, 0.21, 0.19), (0.0, 0.0, 0.02), p=3.0, segs=14, rings=9)
    vs += P._rbox(bm, (0.11, 0.25, 0.06), (0.09, 0.0, 0.17), p=3.0, segs=10, rings=6)
    vs += P._rbox(bm, (0.30, 0.15, 0.10), (0.40, 0.0, 0.0), p=3.0, segs=14, rings=8)
    vs += P._rbox(bm, (0.08, 0.16, 0.08), (0.67, 0.0, 0.05), p=3.0, segs=10, rings=6)
    jaw = Matrix.Translation((0.12, 0.0, -0.10)) @ Matrix.Rotation(math.radians(14), 4, 'Y') @ \
        Matrix.Translation((-0.12, 0.0, 0.10))
    vs += P._rbox(bm, (0.26, 0.12, 0.05), (0.36, 0.0, -0.17), p=3.0, segs=12, rings=6, matrix=jaw)
    for sy in (-1.0, 1.0):
        vs += cone(bm, (0.62, sy * 0.09, -0.06), (0.64, sy * 0.09, -0.19), 0.03, 5)
        vs += cone(bm, jaw @ Vector((0.56, sy * 0.08, -0.13)), jaw @ Vector((0.57, sy * 0.08, -0.02)), 0.026, 5)
        ev = P._sphere(bm, 0.07, (0.15, sy * 0.175, 0.10), 12, 6, scale=(0.75, 0.6, 1.0), mat=mat_eye)
        vs += ev
        vs += tube(bm, [(0.02, sy * 0.10, 0.19), (0.14, sy * 0.19, 0.22), (0.25, sy * 0.20, 0.17)], 0.03, 6, 3)
        horn = [(-0.06, sy * 0.10, 0.17, 1.0), (-0.30, sy * 0.16, 0.34, 0.85), (-0.55, sy * 0.21, 0.42, 0.6),
                (-0.78, sy * 0.19, 0.40, 0.3)]
        vs += tube(bm, horn, 0.065, 6, 4)
        vs += tube(bm, [(-0.30, sy * 0.16, 0.34, 1.0), (-0.36, sy * 0.24, 0.53, 0.7), (-0.42, sy * 0.21, 0.63, 0.35)],
                   0.04, 6, 3)
        wh = [(0.64, sy * 0.13, 0.02, 1.0), (0.78, sy * 0.36, 0.02, 0.85), (0.70, sy * 0.62, -0.14, 0.6),
              (0.46, sy * 0.78, -0.10, 0.4), (0.30, sy * 0.80, 0.02, 0.2)]
        vs += tube(bm, wh, 0.024, 5, 4)
        vs += tube(bm, [(0.30, sy * 0.06, -0.22, 1.0), (0.22, sy * 0.08, -0.40, 0.7), (0.12, sy * 0.05, -0.52, 0.3)],
                   0.045, 6, 3)
        for k in range(3):                              # flame mane, swept back
            z = 0.12 - 0.12 * k
            y = sy * (0.12 + 0.05 * k)
            vs += tube(bm, [(-0.16, y, z, 1.0), (-0.42, y * 1.25, z + 0.08, 0.8), (-0.62, y * 1.4, z - 0.02, 0.5),
                            (-0.80, y * 1.3, z + 0.10, 0.15)], 0.07, 6, 3)
    vs += tube(bm, [(-0.10, 0.0, 0.18, 1.0), (-0.45, 0.0, 0.30, 0.8), (-0.75, 0.0, 0.22, 0.2)], 0.08, 6, 3)
    P._xf(bm, S, vs)
    if mat:
        for f in P._faces_of(vs):
            if f.material_index != mat_eye or mat_eye == 0:
                f.material_index = mat
    return vs


def dragon_body(bm, pts, radius, outward, spikes=(0.05, 0.93, 0.035), spike_h=0.14, mat=0, samples=5, sides=8):
    """Scaly body tube through control points (x, y, z, w) (w scales the radius) with a row of dorsal spikes on the
    side ``outward(p)`` -> unit vector. spikes = (start, end, spacing) in path fraction."""
    vs = tube(bm, pts, radius, sides, samples, mat=mat)
    path = U.catmull_rom(pts, samples)
    m = len(path)
    if spikes:
        s0, s1, ds = spikes
        t = s0
        while t <= s1:
            i = min(m - 2, max(1, int(t * (m - 1))))
            c = Vector(path[i][:3])
            w = path[i][3]
            tg = (Vector(path[i + 1][:3]) - Vector(path[i - 1][:3])).normalized()
            o = Vector(outward(c))
            o = (o - tg * o.dot(tg)).normalized()
            sd = tg.cross(o)
            r = radius * w
            b = c + o * (r * 0.7)
            h = spike_h * (0.6 + 0.4 * w)
            tip = c + o * (r + h) - tg * (0.5 * h)
            q = [bm.verts.new(b + tg * (0.6 * h)), bm.verts.new(b - tg * (0.3 * h) + sd * (0.22 * h)),
                 bm.verts.new(b - tg * (0.3 * h) - sd * (0.22 * h)), bm.verts.new(tip)]
            for f in ((q[0], q[1], q[3]), (q[1], q[2], q[3]), (q[2], q[0], q[3]), (q[0], q[2], q[1])):
                bm.faces.new(f).material_index = mat
            vs += q
            t += ds
    return vs


def dragon_leg(bm, shoulder, elbow, foot, toes, r, mat=0, mat_claw=0):
    """Leg tube shoulder -> elbow -> foot, then toes [(direction)], each with a talon."""
    vs = tube(bm, [tuple(shoulder) + (1.0,), tuple(elbow) + (0.8,), tuple(foot) + (0.65,)], r, 6, 4, mat=mat)
    f = Vector(foot)
    for d in toes:
        d = Vector(d)
        a = f + d * (r * 2.2)
        vs += tube(bm, [tuple(f) + (1.0,), tuple(f + d * (r * 1.2)) + (0.8,), tuple(a) + (0.6,)], r * 0.42, 5, 2,
                   mat=mat)
        vs += cone(bm, a, a + d * (r * 1.1) - Vector((0, 0, r * 0.5)), r * 0.24, 4, mat=mat_claw)
    return vs


# ================================================================ station 陣眼 (prototype)

def col_apothem(z):
    return COL_A0 + (COL_A1 - COL_A0) * (z - COL_Z0) / (COL_Z1 - COL_Z0)


def col_surface_r(theta, z):
    """Distance from the column axis to its octagonal surface at angle theta (flat faces at 45 k degrees)."""
    k = round(theta / (math.pi / 4))
    return col_apothem(z) / math.cos(theta - k * math.pi / 4)


def _rb(s):
    """Dragon body radius along the body (0 tail .. 1 neck)."""
    return 0.06 + 0.17 * min(1.0, s / 0.55) ** 0.8


def _station_dragon(bm):
    z0, z1 = DRAGON_Z
    pts = []
    n = 44
    for i in range(n + 1):
        s = i / n
        th = math.pi - DRAGON_TURNS * TAU * (1.0 - s)
        z = z0 + (z1 - z0) * s
        rho = col_surface_r(th, z) + 0.72 * _rb(s)
        pts.append((rho * math.cos(th), rho * math.sin(th), z, _rb(s) / 0.23))
    a = col_apothem(6.2)
    pts += [(-(a + 0.45), -0.10, 6.22, 0.95), (-(a + 0.78), -0.04, 6.38, 0.9)]
    out = lambda c: (c.x, c.y, 0.0)                 # noqa: E731  dorsal side: away from the column axis
    vs = dragon_body(bm, pts, 0.23, out, spikes=(0.06, 0.9, 0.022), spike_h=0.16)
    head = frame((-1.0, 0.0, -0.22), (0, 0, 1), (-(a + 1.02), -0.02, 6.42))
    vs += dragon_head(bm, head, 0.95)
    # legs: hind pair low on the body, fore pair below the neck; paws on the column surface
    path = U.catmull_rom(pts, 5)
    mm = len(path)
    for frac, side in ((0.30, 1.0), (0.40, -1.0), (0.80, 1.0), (0.88, -1.0)):
        i = int(frac * (mm - 1))
        c = Vector(path[i][:3])
        th = math.atan2(c.y, c.x)
        tg = (Vector(path[i + 1][:3]) - Vector(path[i - 1][:3])).normalized()
        zf = c.z - 0.42 * side
        thf = th - side * 0.32
        rf = col_surface_r(thf, zf) + 0.06
        foot = Vector((rf * math.cos(thf), rf * math.sin(thf), zf))
        rad = Vector((math.cos(th), math.sin(th), 0.0))
        elbow = c.lerp(foot, 0.5) + rad * 0.22
        shoulder = c + rad * 0.05
        fd = (foot - c).normalized()
        toes = [(fd + rad * 0.2 + tg * 0.5 * k).normalized() for k in (-1, 0, 1)]
        vs += dragon_leg(bm, shoulder, elbow, foot, toes, 0.075)
    return vs


def _cloud_spiral(cx, cy, r0, turns=1.4, n=16, sign=1.0):
    return [(cx + sign * r0 * (1 - 0.8 * i / n) * math.cos(TAU * turns * i / n),
             cy + r0 * (1 - 0.8 * i / n) * math.sin(TAU * turns * i / n)) for i in range(n + 1)]


def _face_surf(k, z_ref, dz=0.0):
    """Plane surface on the column's octagon face k (normal at 45 k degrees): (u along the face, v up, h out)."""
    th = k * math.pi / 4
    nrm = Vector((math.cos(th), math.sin(th), 0.0))
    tg = Vector((-math.sin(th), math.cos(th), 0.0))

    def surf(u, v, h):
        z = z_ref + v
        return nrm * (col_apothem(z) + h + dz) + tg * u + Vector((0, 0, z))
    return surf


def _column_clouds(bm):
    """Low cloud scrolls carved on the faces the dragon leaves bare."""
    vs = []
    z0, z1 = DRAGON_Z
    for z in (3.3, 4.4, 5.3, 7.75):
        # the dragon crosses height z at this angle; clouds go on the faces half a turn away
        s = min(1.0, max(0.0, (z - z0) / (z1 - z0)))
        th = math.pi - DRAGON_TURNS * TAU * (1.0 - s)
        for off in (math.pi * 0.75, math.pi * 1.25) if z < 7.5 else (0.0, math.pi / 2, math.pi, 1.5 * math.pi):
            k = round((th + off) / (math.pi / 4)) % 8
            surf = _face_surf(k, z)
            for sgn in (-1.0, 1.0):
                vs += P._relief(bm, _cloud_spiral(sgn * 0.17, 0.0, 0.16, 1.3, 12, sgn), 0.045, 0.03, surf, taper=0.7)
            vs += P._relief(bm, [(-0.33, -0.12), (-0.1, -0.17), (0.1, -0.17), (0.33, -0.12)], 0.045, 0.03, surf,
                            taper=0.7)
    return vs


def _cloud_outline(half=1.65, r0=0.44, band=0.26, n=22):
    """Cloud plate outline (u along the plate, v up): a wavy band ending in two lobed ruyi cloud heads."""
    top = [(u, band + 0.035 * math.sin(u * 3.6)) for u in [-half + 2 * half * i / 12 for i in range(13)]]
    head = []
    for i in range(n + 1):
        ph = math.radians(118.0 - 236.0 * i / n)
        r = r0 * (1.0 + 0.12 * math.cos(4.0 * ph))
        head.append((half + 0.18 + r * math.cos(ph), 0.02 + r * math.sin(ph)))
    bot = [(u, -band - 0.035 * math.sin(u * 3.6 + 1.0)) for u in [half - 2 * half * i / 12 for i in range(13)]]
    left = [(-u, v) for u, v in reversed(head)]
    pts = top[1:-1] + head + bot[1:-1] + left
    return pts


def station_proto(pc):
    """Build the station prototype objects into proto collection ``pc``."""
    # ---- plinth: two octagonal steps and a round lotus die (xumizuo)
    bm = bmesh.new()
    oct_lathe(bm, [(0, -0.05), (PLINTH_A, -0.05), (PLINTH_A, 0.30), (PLINTH_A - 0.05, 0.35), (2.62, 0.35),
                   (2.62, 0.65), (2.57, 0.70), (0.0, 0.70)])
    petal = lambda a: abs(math.cos(12.0 * a)) ** 0.55   # noqa: E731  24 petals round the die
    lathe(bm, [(0.0, 0.69), (2.22, 0.69), (2.22, 0.78), (2.14, 0.81), (2.07, 0.86), (1.97, 0.91), (1.88, 0.94),
               (1.88, 1.08), (1.97, 1.11), (2.07, 1.16), (2.15, 1.21), (2.22, 1.24), (2.22, 1.30), (0.0, 1.30)], 96,
          rmod=lambda a, i, r, z: r * (1.0 + (0.035 * (petal(a) - 0.5) if i in (3, 4, 5, 8, 9, 10) else 0.0)),
          zmod=lambda a, i, r, z: z + (0.025 * petal(a) ** 3 if i in (5, 8) else 0.0))
    P._outward(bm)
    mk("formation.p.station_plinth", bm, pc, [M_MARBLE], smooth=math.radians(40), bevel=0.02)

    # ---- column (octagonal, tapering) and its carving: the coiling dragon and cloud scrolls
    bm = bmesh.new()
    oct_lathe(bm, [(0.0, COL_Z0), (COL_A0, COL_Z0), (COL_A1, COL_Z1), (0.0, COL_Z1)])
    mk("formation.p.station_column", bm, pc, [M_CARVED], smooth=False, bevel=0.03)
    bm = bmesh.new()
    _station_dragon(bm)
    _column_clouds(bm)
    P._outward(bm)
    mk("formation.p.station_dragon", bm, pc, [M_CARVED], smooth=math.radians(50))

    # ---- bronze bands with gold bosses
    bm = bmesh.new()
    for z0, z1 in ((1.40, 1.85), (8.20, 8.62)):
        a = col_apothem(0.5 * (z0 + z1))
        prof = [(a - 0.05, z0), (a + 0.05, z0 + 0.02), (a + 0.08, z0 + 0.06), (a + 0.08, z1 - 0.06),
                (a + 0.05, z1 - 0.02), (a - 0.05, z1)]
        lathe(bm, [(r * OCT, z) for r, z in prof], 8, caps=(False, False), phase=math.pi / 8)
        lathe(bm, [((a + 0.08) * OCT, z0 + 0.12), ((a + 0.11) * OCT, z0 + 0.14), ((a + 0.11) * OCT, z0 + 0.17),
                   ((a + 0.08) * OCT, z0 + 0.19)], 8, caps=(False, False), phase=math.pi / 8)
        lathe(bm, [((a + 0.08) * OCT, z1 - 0.19), ((a + 0.11) * OCT, z1 - 0.17), ((a + 0.11) * OCT, z1 - 0.14),
                   ((a + 0.08) * OCT, z1 - 0.12)], 8, caps=(False, False), phase=math.pi / 8)
        for k in range(8):
            th = k * math.pi / 4
            nrm = Vector((math.cos(th), math.sin(th), 0.0))
            tg = Vector((-math.sin(th), math.cos(th), 0.0))
            zc = 0.5 * (z0 + z1)
            surf = (lambda nrm, tg, zc, a: lambda u, v, h: nrm * (a + 0.08 + h) + tg * u + Vector((0, 0, zc + v)))(
                nrm, tg, zc, a)
            P._boss(bm, surf, 0.0, 0.0, 0.075, 0.06, segs=10, rings=3, mat=1)
    P._outward(bm)
    mk("formation.p.station_bands", bm, pc, [M_BRONZE, M_GOLD], smooth=math.radians(40))

    # ---- cloud plate piercing the column (broad faces toward +-X), spiral relief on both faces
    bm = bmesh.new()
    out = _cloud_outline()
    prism_x(bm, out, -0.16, 0.16, matrix=Matrix.Translation((0.0, 0.0, CLOUD_Z)))
    for sx in (-1.0, 1.0):
        def surf(u, v, h, sx=sx):
            return Vector((sx * (0.16 + h), u, CLOUD_Z + v))
        for cu in (-1.83, 1.83):
            P._relief(bm, _cloud_spiral(cu, 0.02, 0.30, 1.5, 18, 1.0 if cu > 0 else -1.0), 0.06, 0.035, surf)
        P._relief(bm, [(-1.35 + 2.7 * i / 16, 0.035 * math.sin(i * 1.3)) for i in range(17)], 0.05, 0.03, surf)
    P._outward(bm)
    mk("formation.p.station_cloudplate", bm, pc, [M_MARBLE], smooth=math.radians(35), bevel=0.015)

    # ---- lotus dew plate
    bm = bmesh.new()
    pet = lambda a: abs(math.cos(12.0 * a))             # noqa: E731
    lathe(bm, [(0.0, DEW_Z[0]), (1.02, DEW_Z[0]), (1.12, 8.70), (1.30, 8.80), (1.47, 8.92), (1.58, 9.05),
               (1.62, 9.13), (1.55, 9.18), (1.40, 9.14), (1.18, 9.10), (0.0, 9.10)], 96,
          rmod=lambda a, i, r, z: r * (1.0 + (0.07 * (pet(a) ** 0.5 - 0.6) if 2 <= i <= 7 else 0.0)),
          zmod=lambda a, i, r, z: z + (0.10 * pet(a) ** 3 if i in (6, 7) else 0.0))
    P._outward(bm)
    mk("formation.p.station_dewplate", bm, pc, [M_MARBLE], smooth=math.radians(45))

    # ---- bronze cradle: a cup under the eye and four dragon-claw arms with gold talons
    bm = bmesh.new()
    lathe(bm, [(0.0, 9.06), (0.48, 9.06), (0.64, 9.24), (0.75, 9.55), (0.80, 9.80), (0.75, 9.85), (0.69, 9.78),
               (0.40, 9.56), (0.0, 9.50)], 32)
    lathe(bm, [(0.70, 9.30), (0.79, 9.33), (0.79, 9.40), (0.70, 9.43)], 32, caps=(False, False), mat=1)
    for k in range(4):
        ph = math.pi / 4 + k * math.pi / 2
        c, s = math.cos(ph), math.sin(ph)
        arm = [(0.68, 9.40, 1.0), (1.05, 9.56, 0.95), (1.30, 10.05, 0.85), (1.26, 10.66, 0.72), (1.08, 11.26, 0.6),
               (0.80, 11.56, 0.5)]
        tube(bm, [(r * c, r * s, z, w) for r, z, w in arm], 0.12, 8, 4)
        P._sphere(bm, 0.09, (0.80 * c, 0.80 * s, 11.56), 10, 6, mat=1)
        for dk in (-0.32, 0.0, 0.32):
            pa = ph + dk
            ca, sa = math.cos(pa), math.sin(pa)
            tal = [(0.80, 11.56, 1.0), (0.66, 11.66, 0.8), (0.48, 11.70, 0.55), (0.34, 11.66, 0.2)]
            tube(bm, [(r * (c if dk == 0 else ca), r * (s if dk == 0 else sa), z, w) for r, z, w in tal], 0.045, 6, 3,
                 mat=1)
        for z in (9.85, 10.35):                       # scale rings on the arm
            r = 1.18 if z < 10 else 1.30
            P._torus(bm, 0.12, 0.03, 10, 5, matrix=Matrix.Translation((r * c, r * s, z)) @
                     Matrix.Rotation(-ph, 4, 'Z').inverted() @ Matrix.Rotation(math.radians(60), 4, 'Y'))
    P._outward(bm)
    mk("formation.p.station_cradle", bm, pc, [M_BRONZE, M_GOLD], smooth=math.radians(45))

    # ---- the jade eye (the station's only glow; the page's idle wave pulses it)
    bm = bmesh.new()
    P._sphere(bm, EYE_R, (0.0, 0.0, EYE_Z), 48, 24)
    mk("formation.p.station_eye", bm, pc, [M_EYE], smooth=True, glow=1.0)


def station_plaque(coll, name, parent, trigram):
    """The station's trigram in gold on a bronze plaque on the column's inward (-X) face. Object in the station's
    frame (parent: the station instance)."""
    a = col_apothem(PLAQUE_Z)
    bm = bmesh.new()
    x0 = -(a - 0.01)
    P._box(bm, (0.07, 0.86, 0.62), (x0 - 0.035, 0.0, PLAQUE_Z))
    for sy in (-1.0, 1.0):                                 # frame
        P._box(bm, (0.04, 0.05, 0.62), (x0 - 0.09, sy * 0.405, PLAQUE_Z), mat=1)
    for sz in (-1.0, 1.0):
        P._box(bm, (0.04, 0.86, 0.05), (x0 - 0.09, 0.0, PLAQUE_Z + sz * 0.285), mat=1)
    lines = TRIGRAM_LINES[trigram]
    for i, yang in enumerate(lines):                       # bottom line lowest
        zc = PLAQUE_Z - 0.15 + 0.15 * i
        if yang:
            P._box(bm, (0.035, 0.56, 0.075), (x0 - 0.085, 0.0, zc), mat=1)
        else:
            for sy in (-1.0, 1.0):
                P._box(bm, (0.035, 0.22, 0.075), (x0 - 0.085, sy * 0.17, zc), mat=1)
    P._outward(bm)
    return mk(name, bm, coll, [M_BRONZE, M_GOLD], parent=parent, smooth=False, bevel=0.008)


# ================================================================ brazier 圣火盆

BRAZIER_RIM = 1.78
BRAZIER_BED = 1.70


def _flame_shape(t):
    return (1.0 - t) ** 1.15 * (1.0 + 1.7 * t)


def _slim(t):
    return (1.0 - t) ** 1.3 * (1.0 + 1.2 * t)


def tongue(bm, ctrl, width, thick, sides, per, twist, wref, shape=_flame_shape, mat=0):
    """Closed lofted flame tongue along a Catmull-Rom spine: lens section, broad axis starting along ``wref`` and
    twisting by ``twist`` to the tip, which is a single point."""
    path = [Vector(p[:3]) for p in U.catmull_rom(ctrl, per)]
    m = len(path)
    rings = []
    w0 = Vector(wref)
    for i, c in enumerate(path):
        t = i / (m - 1)
        tg = (path[min(i + 1, m - 1)] - path[max(i - 1, 0)]).normalized()
        b = w0 - tg * w0.dot(tg)
        if b.length < 1e-6:
            b = tg.orthogonal()
        b.normalize()
        b = Quaternion(tg, twist * t) @ b
        n = tg.cross(b)
        if i == m - 1:
            rings.append([bm.verts.new(c)])
            continue
        hw = 0.5 * width * shape(t)
        rings.append([bm.verts.new(c + b * (hw * math.cos(TAU * k / sides)) +
                                   n * (hw * thick * math.sin(TAU * k / sides) *
                                        (0.55 + 0.45 * abs(math.sin(TAU * k / sides)))))
                      for k in range(sides)])
    vs = [v for r in rings for v in r]
    bm.faces.new(list(reversed(rings[0]))).material_index = mat
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(sides):
            k2 = (k + 1) % sides
            if len(b) == 1:
                bm.faces.new((a[k], a[k2], b[0])).material_index = mat
            else:
                bm.faces.new((a[k], a[k2], b[k2], b[k])).material_index = mat
    return vs


def _flame(bm, z0, H, seed):
    rnd = random.Random(seed)
    tongue(bm, [(0.0, 0.0, z0), (0.04, 0.0, z0 + 0.22 * H), (0.0, 0.02, z0 + 0.42 * H), (-0.05, 0.02, z0 + 0.60 * H)],
           0.95, 0.62, 10, 2, math.radians(15.0), (1.0, 0.0, 0.0))
    ctrl = [(0.0, 0.0, 0.0), (0.06, 0.01, 0.24), (0.09, 0.02, 0.48), (0.02, 0.04, 0.70), (-0.08, 0.04, 0.86),
            (0.05, 0.03, 1.0)]
    tongue(bm, [(x * H, y * H, z0 + z * H) for x, y, z in ctrl], 0.62, 0.5, 8, 2, math.radians(40.0), (1.0, 0.0, 0.0))
    for k in range(5):
        az = TAU * k / 5 + rnd.uniform(-0.3, 0.3)
        h = H * rnd.uniform(0.55, 0.8)
        u = Vector((math.cos(az), math.sin(az), 0.0))
        tau = Vector((-math.sin(az), math.cos(az), 0.0))
        ph = rnd.uniform(0, TAU)
        pts = []
        for t in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
            o = 0.28 + h * (0.20 * t - 0.05 * t * t)
            c = 0.06 * math.sin(1.8 * math.pi * t + ph) * min(1.0, 3.0 * t)
            p = u * o + tau * c
            pts.append((p.x, p.y, z0 + h * t))
        tongue(bm, pts, 0.36, 0.45, 8, 2, math.radians(rnd.uniform(-30, 30)), tau, shape=_slim)
    for (x, y, z, h, w) in ((0.22, -0.03, 0.78, 0.18, 0.08), (-0.18, 0.02, 0.92, 0.15, 0.07)):
        tongue(bm, [(x * H, y, z0 + z * H), (x * H + 0.02, y, z0 + z * H + 0.5 * h), (x * H + 0.05, y, z0 + z * H + h)],
               w, 0.5, 6, 2, 0.0, (1.0, 0.0, 0.0), shape=lambda t: math.sin(math.pi * max(t, 0.02)) ** 0.7)


def _coals(bm, r_in, z_bed, seed):
    rnd = random.Random(seed)
    prof = [(r_in, z_bed - 0.06), (r_in, z_bed), (0.82 * r_in, z_bed + 0.05), (0.55 * r_in, z_bed + 0.10),
            (0.28 * r_in, z_bed + 0.13), (0.0, z_bed + 0.14)]
    segs = 20
    rings = []
    for i, (r, z) in enumerate(prof):
        if r <= 1e-9:
            rings.append([bm.verts.new((0.0, 0.0, z))])
            continue
        rr = []
        for k in range(segs):
            a = TAU * k / segs
            q, zz = r, z
            if i > 1:
                q *= 1.0 + 0.05 * math.sin(3 * a + i) + rnd.uniform(-0.03, 0.03)
                zz += 0.02 * math.sin(5 * a + 2 * i) + rnd.uniform(-0.012, 0.012)
            rr.append(bm.verts.new((q * math.cos(a), q * math.sin(a), zz)))
        rings.append(rr)
    bm.faces.new(list(reversed(rings[0])))
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(segs):
            k2 = (k + 1) % segs
            if len(b) == 1:
                bm.faces.new((a[k], a[k2], b[0]))
            else:
                bm.faces.new((a[k], a[k2], b[k2], b[k]))
    for i in range(16):                               # iron-dark ash lumps, mostly round the rim
        a = TAU * (i + rnd.uniform(-0.3, 0.3)) / 16
        rr = rnd.uniform(0.40, 0.62) if i % 3 else rnd.uniform(0.18, 0.36)
        sz = rnd.uniform(0.06, 0.11)
        z = z_bed + 0.13 * (1.0 - (rr / r_in) ** 2) - 0.02
        P._ico(bm, sz, (rr * math.cos(a), rr * math.sin(a), z), subdiv=1,
               scale=(1.0, rnd.uniform(0.7, 1.0), 0.6), mat=1)


def _brazier_bronze():
    bm = bmesh.new()
    bowl = [(0.0, 1.20), (0.30, 1.20), (0.48, 1.28), (0.62, 1.40), (0.71, 1.54), (0.75, 1.66), (0.80, 1.73),
            (0.81, BRAZIER_RIM), (0.74, BRAZIER_RIM), (0.69, 1.70), (0.58, 1.52), (0.32, 1.40), (0.0, 1.37)]
    lathe(bm, bowl, 48)
    for z in (1.44, 1.66):                              # cast ridges framing the mask band
        rr = P._prof_r(bowl[1:7], z) + 0.004
        P._torus(bm, rr, 0.016, 48, 6, matrix=Matrix.Translation((0, 0, z)))
    for k in range(3):                                  # taotie masks between the legs
        P._taotie(bm, math.pi / 3 + TAU * k / 3, 1.555, 0.735, 1.9)
    for sy in (-1.0, 1.0):                              # upright loop handles on the rim (tangential)
        pts = [(0.0, sy * 0.70, BRAZIER_RIM - 0.02), (0.10, sy * 0.72, BRAZIER_RIM + 0.10),
               (0.16, sy * 0.74, BRAZIER_RIM + 0.24), (0.0, sy * 0.76, BRAZIER_RIM + 0.31),
               (-0.16, sy * 0.74, BRAZIER_RIM + 0.24), (-0.10, sy * 0.72, BRAZIER_RIM + 0.10),
               (0.0, sy * 0.70, BRAZIER_RIM - 0.02)]
        tube(bm, pts, 0.028, 8, 3)
    for k in range(3):                                  # beast legs
        th = math.pi + TAU * k / 3
        c, s = math.cos(th), math.sin(th)
        leg = [(0.40, 1.30, 1.15), (0.58, 1.12, 1.25), (0.70, 0.86, 1.0), (0.64, 0.56, 0.85), (0.62, 0.30, 0.9),
               (0.66, 0.18, 1.05)]
        tube(bm, [(r * c, r * s, z, w) for r, z, w in leg], 0.085, 8, 4)
        P._sphere(bm, 0.15, (0.70 * c, 0.70 * s, 0.11), 12, 6, scale=(1.3, 1.1, 0.75))
        for dk in (-0.35, 0.0, 0.35):                   # toes
            a = th + dk * 0.6
            P._sphere(bm, 0.055, ((0.70 * c + 0.15 * math.cos(a)), (0.70 * s + 0.15 * math.sin(a)), 0.06), 8, 4,
                      scale=(1.4, 1.0, 0.8))
        P._taotie(bm, th, 1.18, 0.52, 1.2)              # beast mask where the leg meets the bowl
    P._merge(bm, 1e-6)
    P._outward(bm)
    return bm


def _brazier_step():
    bm = bmesh.new()
    oct_lathe(bm, [(0.0, -0.04), (0.82, -0.04), (0.82, 0.10), (0.79, 0.14), (0.0, 0.14)])
    return bm


def _brazier_coals():
    bm = bmesh.new()
    _coals(bm, 0.70, BRAZIER_BED, 7731)
    P._outward(bm)
    return bm


def _brazier_flame():
    bm = bmesh.new()
    _flame(bm, BRAZIER_BED + 0.04, 1.25, 4113)
    P._outward(bm)
    return bm


BRAZIER_LIGHT = dict(energy=750.0, color=(1.0, 0.55, 0.22), soft=0.5, z=2.6, shadow=False)


def brazier(coll, name, parent, location, rotation_z):
    """Holy-fire brazier: Empty ``name`` with children .step (marble), .bronze (bowl, taotie, beast legs), .coals
    (molten + iron), .flame (props_flame; casts no shadow) and the point light .light. Meshes are shared."""
    root = tag(U.empty(name, coll, location=location, rotation=(0.0, 0.0, rotation_z), parent=parent,
                       display_size=1.0))
    step = shared("formation.brazier_step.v1", _brazier_step, [M_MARBLE], smooth=False, bevel=0.012)
    bronze = shared("formation.brazier_bronze.v1", _brazier_bronze, [M_BRONZE], smooth=math.radians(45))
    coals = shared("formation.brazier_coals.v1", _brazier_coals, ["molten", "iron"], smooth=math.radians(30))
    flame = shared("formation.brazier_flame.v1", _brazier_flame, [M_FLAME], smooth=True)
    obj(name + ".step", step, coll, parent=root)
    obj(name + ".bronze", bronze, coll, parent=root)
    obj(name + ".coals", coals, coll, parent=root, glow=1.2)
    obj(name + ".flame", flame, coll, parent=root, glow=1.0, shadow=False)
    ld = bpy.data.lights.new(name + ".light", 'POINT')
    ld.energy = BRAZIER_LIGHT["energy"]
    ld.color = BRAZIER_LIGHT["color"]
    ld.shadow_soft_size = BRAZIER_LIGHT["soft"]
    # no shadows: the light sits inside the flame and the bake joins the chunk into one mesh (the flame's
    # visible_shadow=False is lost there), so a shadowing light would be boxed in by its own flame
    ld.use_shadow = BRAZIER_LIGHT["shadow"]
    ld[TAG] = 1
    lo = bpy.data.objects.new(name + ".light", ld)
    coll.objects.link(lo)
    lo.parent = root
    lo.location = (0.0, 0.0, BRAZIER_LIGHT["z"])
    tag(lo)
    return root


# ================================================================ armillary sphere 浑天仪

ARM_Z = 10.5                  # sphere centre
ARM_R = 7.0                   # horizon and meridian rings
DRAGON_FEET = [(sx * 5.0, sy * 5.0) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
POLAR_TILT = math.radians(35.0)


def polar_axis():
    """The turning set's polar axis: in the meridian (y-z) plane, POLAR_TILT up toward +Y."""
    return Vector((0.0, math.cos(POLAR_TILT), math.sin(POLAR_TILT)))


def _arm_pedestal(bm, z0):
    wave = lambda a: abs(math.cos(6.0 * a)) ** 0.7    # noqa: E731
    lathe(bm, [(0.0, z0 - 0.02), (2.40, z0 - 0.02), (2.40, z0 + 0.32), (2.30, z0 + 0.40), (2.05, z0 + 0.42),
               (2.05, z0 + 0.80), (1.95, z0 + 0.88), (1.70, z0 + 0.90), (1.60, z0 + 1.00), (1.42, z0 + 1.10),
               (1.40, z0 + 1.60), (1.55, z0 + 1.72), (1.62, z0 + 1.82), (1.62, z0 + 1.90), (0.0, z0 + 1.90)], 64,
          rmod=lambda a, i, r, z: r * (1.0 + (0.04 * (wave(a) - 0.5) if i in (2, 3, 5, 6) else 0.0)))
    top = z0 + 1.90
    # meridian cradle: two cheek plates either side of the ring's foot
    for sx in (-1.0, 1.0):
        P._box(bm, (0.12, 1.30, 0.80), (sx * 0.24, 0.0, top + 0.35))
        P._sphere(bm, 0.09, (sx * 0.31, 0.0, top + 0.55), 10, 6, mat=1)


def _arm_dragon(bm, fx, fy, z0):
    """A dragon pillar from its cloud base at (fx, fy, z0) up to the horizon ring, head turned outward under it."""
    phi = math.atan2(fy, fx)
    rad = Vector((math.cos(phi), math.sin(phi), 0.0))
    tg = Vector((-math.sin(phi), math.cos(phi), 0.0))
    rho0 = math.hypot(fx, fy)

    def P3(rho, t, z, w=1.0):
        p = rad * rho + tg * t + Vector((0, 0, z))
        return (p.x, p.y, p.z, w)
    # cloud base
    wave = lambda a: abs(math.cos(5.0 * a)) ** 0.6    # noqa: E731
    base = Matrix.Translation(rad * rho0 + Vector((0, 0, z0)))
    lathe(bm, [(0.0, -0.02), (0.92, -0.02), (0.95, 0.18), (0.80, 0.34), (0.60, 0.46), (0.42, 0.62), (0.0, 0.62)], 40,
          matrix=base, rmod=lambda a, i, r, z: r * (1.0 + (0.16 * (wave(a) - 0.5) if i in (2, 3, 4) else 0.0)))
    pts = [P3(rho0, 0.0, z0 + 0.35, 0.55), P3(rho0 - 0.15, 0.15, z0 + 1.4, 0.85), P3(rho0 - 0.55, 0.45, z0 + 3.0, 1.0),
           P3(rho0 - 0.25, 0.10, z0 + 4.7, 1.0), P3(rho0 + 0.35, -0.40, z0 + 6.2, 0.95),
           P3(rho0 + 0.30, -0.25, z0 + 7.6, 0.9), P3(ARM_R + 0.10, 0.10, ARM_Z - 0.55, 0.85),
           P3(ARM_R + 0.55, 0.40, ARM_Z - 0.75, 0.82)]
    outward = lambda c: (Vector((c.x, c.y, 0.0)).normalized() + Vector((0, 0, 0.3)))  # noqa: E731
    dragon_body(bm, pts, 0.27, outward, spikes=(0.1, 0.92, 0.03), spike_h=0.2, samples=6, sides=9)
    # cloud collar half way up
    cpos = Vector(pts[3][:3])
    for k in range(5):
        a = TAU * k / 5
        off = rad * (0.36 * math.cos(a)) + tg * (0.36 * math.sin(a))
        P._sphere(bm, 0.2, tuple(cpos + off), 10, 6, scale=(1.0, 1.0, 0.6))
    P._torus(bm, 0.34, 0.07, 24, 6, matrix=Matrix.Translation(cpos))
    # head, turned outward and down, just under the ring
    hp = Vector(pts[-1][:3]) + rad * 0.32 - Vector((0, 0, 0.05))
    dragon_head(bm, frame(rad - Vector((0, 0, 0.35)), (0, 0, 1), hp), 1.15, mat=0, mat_eye=1)
    # fore legs reaching up to grip the ring, hind legs on the body
    for side in (-1.0, 1.0):
        sh = Vector(pts[-2][:3]) + tg * (0.25 * side)
        grip = rad * (ARM_R + 0.18) + tg * (side * 0.65 + 0.2) + Vector((0, 0, ARM_Z - 0.32))
        elbow = sh.lerp(grip, 0.5) + rad * 0.35
        dragon_leg(bm, sh, elbow, grip, [(rad * -0.3 + Vector((0, 0, 1))).normalized(),
                                         (rad * 0.5 + Vector((0, 0, 0.6))).normalized(),
                                         (tg * side * 0.8 + Vector((0, 0, 0.5))).normalized()], 0.1, mat_claw=1)
        hip = Vector(pts[2][:3]) + tg * (0.2 * side)
        foot = hip + rad * 0.55 + tg * (0.35 * side) - Vector((0, 0, 0.6))
        dragon_leg(bm, hip, hip.lerp(foot, 0.5) + rad * 0.25, foot, [(rad + tg * 0.3 * k).normalized()
                                                                     for k in (-1, 0, 1)], 0.09, mat_claw=1)
    # the flaming pearl held up against the ring
    pearl = rad * (ARM_R + 0.55) + tg * 0.75 + Vector((0, 0, ARM_Z - 0.62))
    P._sphere(bm, 0.2, tuple(pearl), 14, 8, mat=1)


def armillary_static(bm_bronze, bm_verd, z0):
    """Static frame: pedestal (bronze), four dragon pillars (verdigris bronze), horizon ring with gold ticks and
    lunar-mansion studs, meridian ring with gold graduation."""
    _arm_pedestal(bm_bronze, z0)
    for fx, fy in DRAGON_FEET:
        _arm_dragon(bm_verd, fx, fy, z0)
    # horizon ring (0.40 radial x 0.30 tall), gold rim beads, 120 ticks and 28 studs on top
    ring(bm_bronze, ARM_R, rect_section(0.40, 0.30, 0.04), 160, matrix=Matrix.Translation((0, 0, ARM_Z)))
    for dr in (-0.20, 0.20):
        P._torus(bm_bronze, ARM_R + dr, 0.025, 160, 5, matrix=Matrix.Translation((0, 0, ARM_Z + 0.13)), mat=1)
    for i in range(120):
        a = TAU * i / 120
        L = 0.22 if i % 10 else 0.34
        P._box(bm_bronze, (L, 0.035, 0.03), (ARM_R - 0.03, 0.0, ARM_Z + 0.155), matrix=Matrix.Rotation(a, 4, 'Z'),
               mat=1)
    for i in range(28):
        a = TAU * (i + 0.5) / 28
        P._sphere(bm_bronze, 0.06, ((ARM_R + 0.13) * math.cos(a), (ARM_R + 0.13) * math.sin(a), ARM_Z + 0.15),
                  10, 5, scale=(1.0, 1.0, 0.7), mat=1)
    # meridian ring: N-S vertical plane (x = 0), 0.32 thick (x) x 0.45 radial
    mer = Matrix.Translation((0, 0, ARM_Z)) @ Matrix.Rotation(math.pi / 2, 4, 'Y')
    sec = [(dz, dx) for dx, dz in rect_section(0.32, 0.45, 0.04)]
    ring(bm_bronze, ARM_R, sec, 160, matrix=mer)
    for sx in (-1.0, 1.0):
        P._torus(bm_bronze, ARM_R, 0.022, 160, 5, matrix=mer @ Matrix.Translation((0, 0, sx * 0.165)), mat=1)


def armillary_turning(bm_bronze, bm_core):
    """Turning set about the core Empty's origin (the sphere centre): equatorial, ecliptic and declination rings,
    the polar axis rod with gold caps, and the sun-fire core in a cage of bronze hoops. Everything inside R 6.5."""
    tilt = frame(Vector((1.0, 0.0, 0.0)), polar_axis())               # ring normal (0,0,1) -> polar axis
    ring(bm_bronze, 6.2, rect_section(0.36, 0.28, 0.035), 128, matrix=tilt)
    for dz in (-0.13, 0.13):
        P._torus(bm_bronze, 6.2 + 0.18, 0.02, 128, 5, matrix=tilt @ Matrix.Translation((0, 0, dz)), mat=1)
    ecl = tilt @ Matrix.Rotation(math.radians(23.5), 4, 'X')
    ring(bm_bronze, 5.9, rect_section(0.30, 0.24, 0.03), 128, matrix=ecl)
    for i in range(24):                                  # gold zodiac marks on the ecliptic
        a = TAU * i / 24
        P._sphere(bm_bronze, 0.07, tuple(ecl @ Vector((6.06 * math.cos(a), 6.06 * math.sin(a), 0.0))), 8, 4, mat=1)
    axis = polar_axis()
    # declination ring: its plane contains the polar axis, turned 30 deg about it from the meridian plane
    n = Quaternion(axis, math.radians(30.0)) @ axis.cross(Vector((1.0, 0.0, 0.0))).normalized()
    ring(bm_bronze, 5.5, rect_section(0.26, 0.22, 0.03), 128, matrix=frame(axis, n))
    # polar axis rod (11 m) with gold caps and collars
    a0, a1 = axis * -5.5, axis * 5.5
    tube(bm_bronze, [tuple(a0), tuple(a1)], 0.09, 10, 1)
    for p in (a0, a1):
        P._sphere(bm_bronze, 0.17, tuple(p), 12, 6, mat=1)
    for d in (-1.0, 1.0):
        m = frame(axis.orthogonal(), axis)
        m.translation = axis * (d * 1.75)
        P._torus(bm_bronze, 0.13, 0.04, 16, 6, matrix=m, mat=1)
    # sun-fire core and its cage of six bronze hoops
    P._sphere(bm_core, 1.2, (0.0, 0.0, 0.0), 48, 24)
    for n in ((0, 0, 1), (1, 0, 0), (0, 1, 0), (0.7071, 0.7071, 0), (0.7071, -0.7071, 0), (0, 0.7071, 0.7071)):
        n = Vector(n)
        P._torus(bm_bronze, 1.45, 0.03, 48, 5, matrix=frame(n.orthogonal(), n))


# ================================================================ Five Element flag drum 五行旗

DRUM_A, DRUM_H = 0.82, 1.1


def _drum():
    bm = bmesh.new()
    oct_lathe(bm, [(0.0, -0.05), (DRUM_A + 0.06, -0.05), (DRUM_A + 0.06, 0.10), (DRUM_A, 0.16), (DRUM_A, 0.92),
                   (DRUM_A + 0.05, 0.98), (DRUM_A + 0.05, DRUM_H), (0.0, DRUM_H)])
    # carved bands of cloud scrolls round the drum (low relief on every face)
    for k in range(8):
        th = k * math.pi / 4
        nrm = Vector((math.cos(th), math.sin(th), 0.0))
        tg = Vector((-math.sin(th), math.cos(th), 0.0))

        def surf(u, v, h, nrm=nrm, tg=tg):
            return nrm * (DRUM_A + h) + tg * u + Vector((0, 0, v))
        for zc in (0.20, 0.92):
            P._relief(bm, [(-0.30 + 0.6 * i / 10, zc + 0.025 * math.sin(i * 1.6)) for i in range(11)], 0.035, 0.02,
                      surf)
    P._outward(bm)
    return bm


def flag_drum(coll, name, parent, location, face_dir, brigade):
    """Stone drum for a banner: Empty ``name`` at ``location`` with .drum (shared mesh, formation_stone_carved),
    the sect's sun-and-moon medallion on the face toward ``face_dir`` (unit XY) and the brigade name (e.g. 巨木旗)
    carved in gold on the two faces either side of it. Returns the Empty (the banner stands on its top)."""
    ang = math.atan2(face_dir[1], face_dir[0])
    k = round(ang / (math.pi / 4))
    ang = k * math.pi / 4                                     # the nearest face
    root = tag(U.empty(name, coll, location=location, rotation=(0.0, 0.0, 0.0), parent=parent, display_size=0.8))
    me = shared("formation.flag_drum.v1", _drum, [M_CARVED], smooth=False, bevel=0.012)
    obj(name + ".drum", me, coll, parent=root)
    nrm = Vector((math.cos(ang), math.sin(ang), 0.0))
    med = P.sunmoon_medallion(coll, radius=0.30, name=name + ".medallion", parent=root,
                              location=tuple(nrm * (DRUM_A - 0.0) + Vector((0, 0, 0.55))),
                              rotation=(0.0, 0.0, ang + math.pi / 2))
    tag_tree(med)
    bm = bmesh.new()
    for side in (-1, 1):
        a = ang + side * math.pi / 4
        n2 = Vector((math.cos(a), math.sin(a), 0.0))
        t2 = Vector((-math.sin(a), math.cos(a), 0.0))
        basis = Matrix((t2, Vector((0, 0, 1)), n2)).transposed()     # glyph x -> along the face, y -> up, z -> out
        for i, ch in enumerate(brigade):
            c = n2 * (DRUM_A + 0.004) + Vector((0, 0, 0.74 - 0.22 * i))
            text_glyph(bm, ch, 0.19, Matrix.Translation(c) @ basis.to_4x4(), extrude=0.006)
    mk(name + ".name", bm, coll, [M_GOLD], parent=root, smooth=False)
    return root


# ================================================================ Big Dipper star-stone 天罡北斗

def _star_poly(r_out, r_in, rays=7, rot=math.pi / 2):
    return [((r_out if i % 2 == 0 else r_in) * math.cos(rot + math.pi * i / rays),
             (r_out if i % 2 == 0 else r_in) * math.sin(rot + math.pi * i / rays)) for i in range(2 * rays)]


def _rough_stone(seed):
    """Rough-hewn standing stone (0.9 wide x 0.5 deep x 1.6 tall over the platform), its -Y face dressed flatter for
    the star. Origin at the platform top centre."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    vs = P._rbox(bm, (0.45, 0.25, 0.80), (0.0, 0.0, 0.80), p=5.0, segs=20, rings=14)
    cuts = [(Vector((rnd.uniform(-1, 1), rnd.uniform(-0.6, 0.6), rnd.uniform(0.4, 1.0))).normalized(),
             rnd.uniform(0.36, 0.5)) for _ in range(4)]
    for v in vs:
        p = v.co
        n = Vector((p.x / 0.45, p.y / 0.25, (p.z - 0.8) / 0.8))
        n.normalize()
        amp = 0.012 if p.y < -0.18 and 0.15 < p.z < 1.5 else 0.045
        d = U.fbm(p, 2.2, 3, seed=seed)
        p += n * (amp * d)
        p.x *= 1.0 - 0.12 * (p.z / 1.6)                # tapering a little
        for cn, cd in cuts:                           # chipped corners: planar cuts
            q = Vector((p.x / 0.45, p.y / 0.25, (p.z - 0.8) / 0.8))
            e = q.dot(cn) - cd * 2.2
            if e > 0:
                p -= Vector((cn.x * 0.45, cn.y * 0.25, cn.z * 0.8)) * (e * 0.35)
        v.co = p
    P._outward(bm)
    return bm


def _star_platform():
    bm = bmesh.new()
    lathe(bm, [(0.0, -0.04), (1.30, -0.04), (1.30, 0.21), (1.27, 0.25), (1.05, 0.25), (1.05, 0.46), (1.02, 0.50),
               (0.0, 0.50)], 40)
    P._outward(bm)
    return bm


def star_stone(coll, name, parent, location, face_dir, star_name, variant=0):
    """Big Dipper star-stone: Empty ``name`` at ``location`` turned so its carved face (local -Y) looks along
    ``face_dir`` (unit XY): .platform (bluestone), .stone (rough-hewn, mossy), .star (seven-ray star inlaid with
    silver glow) and .name (the star's name cut below it)."""
    ang = math.atan2(face_dir[1], face_dir[0]) + math.pi / 2
    root = tag(U.empty(name, coll, location=location, rotation=(0.0, 0.0, ang), parent=parent, display_size=0.8))
    obj(name + ".platform", shared("formation.star_platform.v1", _star_platform, [M_BLUE], smooth=math.radians(40),
                                   bevel=0.01), coll, parent=root)
    st = shared("formation.star_stone.v1.%d" % variant, lambda: _rough_stone(311 + 17 * variant), [M_CARVED],
                smooth=math.radians(55))
    obj(name + ".stone", st, coll, parent=root, location=(0.0, 0.0, 0.5))
    bm = bmesh.new()
    star = _star_poly(0.24, 0.10)
    vs = P._prism(bm, star, 0.03, y0=-0.29)
    P._xf(bm, Matrix.Translation((0.0, 0.0, 0.5 + 1.22)), vs)
    P._sphere(bm, 0.06, (0.0, -0.29, 0.5 + 1.22), 10, 5, scale=(1.0, 0.5, 1.0))
    P._outward(bm)
    mk(name + ".star", bm, coll, [M_STAR], parent=root, smooth=False, glow=1.0)
    bm = bmesh.new()
    basis = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))       # glyph up -> +Z, glyph front -> -Y
    for i, ch in enumerate(star_name):
        text_glyph(bm, ch, 0.17, Matrix.Translation((0.0, -0.262, 0.5 + 0.86 - 0.21 * i)) @ basis.to_4x4(),
                   extrude=0.008)
    mk(name + ".name", bm, coll, ["stone_dark"], parent=root, smooth=False)
    return root


# ================================================================ floor inlays

def bagua(bm_bar, bm_leak, angles, chars, r_lines=(13.6, 15.0, 16.4), length=4.2, depth=0.75, gap=0.7):
    """Bronze trigram bars (0.06 m proud) centred on each angle (bottom line innermost) and, under each bar, a flat
    strip 0.12 m wider all round: the glow leaking from under the bronze."""
    for t, ch in zip(angles, chars):
        rot = Matrix.Rotation(t, 4, 'Z')
        for r, yang in zip(r_lines, TRIGRAM_LINES[ch]):
            segs = [(-length / 2, length / 2)] if yang else [(-length / 2, -gap / 2), (gap / 2, length / 2)]
            for u0, u1 in segs:
                uc, L = 0.5 * (u0 + u1), u1 - u0
                P._box(bm_bar, (depth, L, 0.075), (r, uc, 0.0225), matrix=rot)
                hw, hl = depth / 2 + 0.12, L / 2 + 0.12
                iw, il = depth / 2 - 0.02, L / 2 - 0.02
                outer = [(r - hw, uc - hl), (r + hw, uc - hl), (r + hw, uc + hl), (r - hw, uc + hl)]
                inner = [(r - iw, uc - il), (r + iw, uc - il), (r + iw, uc + il), (r - iw, uc + il)]
                vo = [bm_leak.verts.new(rot @ Vector((x, y, 0.004))) for x, y in outer]
                vi = [bm_leak.verts.new(rot @ Vector((x, y, 0.004))) for x, y in inner]
                for i in range(4):
                    j = (i + 1) % 4
                    bm_leak.faces.new((vo[i], vo[j], vi[j], vi[i]))


def studs(bm, angles, r=15.0, size=0.8, h=0.08):
    """Bronze diamond studs (flat pyramids) between the trigrams."""
    for t in angles:
        c = Vector((r * math.cos(t), r * math.sin(t), 0.0))
        d = Vector((math.cos(t), math.sin(t), 0.0)) * (size / 2)
        e = Vector((-math.sin(t), math.cos(t), 0.0)) * (size / 2)
        base = [bm.verts.new(c + v + Vector((0, 0, -0.01))) for v in (d, e, -d, -e)]
        top = [bm.verts.new(c + v * 0.25 + Vector((0, 0, h * 0.7))) for v in (d, e, -d, -e)]
        apex = bm.verts.new(c + Vector((0, 0, h)))
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((base[i], base[j], top[j], top[i]))
            bm.faces.new((top[i], top[j], apex))
        bm.faces.new(list(reversed(base)))


def arc_band(bm, r0, r1, z, a0, a1, segs, mat=0):
    """Flat annular band (facing +Z) from angle a0 to a1."""
    return P._annulus(bm, r0, r1, segs, z, a0, a1, mat=mat)


def arc_wall(bm, r, z0, z1, a0, a1, segs, inward=False, mat=0):
    """Vertical cylindrical wall piece; faces outward (or inward)."""
    cols = segs + 1
    lo = [bm.verts.new((r * math.cos(a0 + (a1 - a0) * i / segs), r * math.sin(a0 + (a1 - a0) * i / segs), z0))
          for i in range(cols)]
    hi = [bm.verts.new((v.co.x, v.co.y, z1)) for v in lo]
    for i in range(segs):
        q = (lo[i], lo[i + 1], hi[i + 1], hi[i])
        f = bm.faces.new(tuple(reversed(q)) if inward else q)
        f.material_index = mat
    return lo + hi


def jade_channel(bm_glow, bm_wall, r0, r1, depth, arcs, segs_per_rad=40):
    """Recessed channel between radii r0 and r1, ``depth`` deep, along the given (a0, a1) arcs: a glowing floor and
    stone walls (inner, outer and the two end walls)."""
    for a0, a1 in arcs:
        n = max(8, int((a1 - a0) * segs_per_rad))
        arc_band(bm_glow, r0, r1, -depth, a0, a1, n)
        arc_wall(bm_wall, r0, -depth, 0.0, a0, a1, n, inward=False)
        arc_wall(bm_wall, r1, -depth, 0.0, a0, a1, n, inward=True)
        for a, sgn in ((a0, 1.0), (a1, -1.0)):
            c, s = math.cos(a), math.sin(a)
            q = [bm_wall.verts.new((r * c, r * s, z)) for r, z in ((r0, -depth), (r1, -depth), (r1, 0.0), (r0, 0.0))]
            f = bm_wall.faces.new(q if sgn > 0 else list(reversed(q)))
            f.normal_update()


def radial_channel(bm_glow, bm_curb, bm_collar, t, r0, r1, w=0.5, curb=0.22, curb_h=0.12):
    """A glowing strip between two raised stone curbs along the radius at angle t, ending in a bronze collar."""
    rot = Matrix.Rotation(t, 4, 'Z')
    L = r1 - r0
    vs = [bm_glow.verts.new(rot @ Vector(p)) for p in ((r0, -w / 2, 0.03), (r1, -w / 2, 0.03), (r1, w / 2, 0.03),
                                                         (r0, w / 2, 0.03))]
    bm_glow.faces.new(vs)
    for sy in (-1.0, 1.0):
        P._box(bm_curb, (L, curb, curb_h), (0.5 * (r0 + r1), sy * (w / 2 + curb / 2), curb_h / 2 - 0.01), matrix=rot)
    P._box(bm_collar, (0.30, w + 2 * curb + 0.16, 0.16), (r1 + 0.05, 0.0, 0.07), matrix=rot)
    P._box(bm_collar, (0.10, w + 2 * curb + 0.24, 0.10), (r1 - 0.13, 0.0, 0.11), matrix=rot)


def chant_layout(text, gaps, pitch_char=1.0, pitch_dot=0.5, group=4, start=None):
    """Angles for the chant's characters and pause dots round the ring, clockwise from ``start`` (radians), skipping
    the gap intervals ``gaps`` [(a_centre, half_width)] for item centres. Returns ([(angle, char)], [dot angles])
    with the largest pitch that fits."""
    chars = [c for c in text if not c.isspace() and c not in "，。？！、；：,.?!"]
    items = []
    for i, c in enumerate(chars):
        items.append(("c", c))
        if (i + 1) % group == 0:
            items.append(("d", None))

    def blocked(a):
        for ac, hw in gaps:
            d = (a - ac + math.pi) % TAU - math.pi
            if abs(d) < hw:
                return True
        return False

    def place(pitch):
        a = start
        out = []
        travelled = 0.0
        for kind, c in items:
            step = pitch * (pitch_char if kind == "c" else pitch_dot)
            a_try = a - step / 2
            while blocked(a_try):
                a -= math.radians(0.25)
                travelled += math.radians(0.25)
                a_try = a - step / 2
                if travelled > TAU:
                    return None
            out.append((a_try, kind, c))
            a -= step
            travelled += step
            if travelled > TAU:
                return None
        return out

    lo, hi = math.radians(1.0), math.radians(10.0)
    best = place(lo)
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        r = place(mid)
        if r is None:
            hi = mid
        else:
            lo, best = mid, r
    return [(a, c) for a, k, c in best if k == "c"], [a for a, k, c in best if k == "d"], lo


def chant_glyphs(bm, placed, r, height, z=0.015, extrude=0.015):
    """Gold glyphs (tops pointing outward) at radius r."""
    for a, ch in placed:
        m = Matrix.Translation((r * math.cos(a), r * math.sin(a), z)) @ Matrix.Rotation(a - math.pi / 2, 4, 'Z')
        text_glyph(bm, ch, height, m, extrude=extrude)


def dots(bm, angles, r, rad=0.24):
    for a in angles:
        P._cyl(bm, rad, 0.05, 16, center=(r * math.cos(a), r * math.sin(a), 0.015))


def moss_patches(bm, spots, seed):
    """Flat irregular moss patches [(x, y, size)] at z 0.008."""
    rnd = random.Random(seed)
    for x, y, s in spots:
        n = 9
        ph = rnd.uniform(0, TAU)
        pts = []
        for i in range(n):
            a = ph + TAU * i / n
            rr = 0.5 * s * (0.7 + 0.3 * math.sin(3 * a + rnd.uniform(0, 1)) + rnd.uniform(-0.12, 0.12))
            pts.append((x + rr * math.cos(a), y + rr * math.sin(a) * rnd.uniform(0.6, 1.0)))
        flat_poly(bm, pts, 0.008)
