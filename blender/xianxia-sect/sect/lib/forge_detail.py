"""Artifact Forge Peak, round 29: the two chimney towers behind the forge hall and the three furnaces inside it, built
in full (owner, 2026-10-23: "The two pillars behind the artifact forge peak look a bit low detail i think, same with
the furnaces, and i wish they had animated flames inside of them").

What the round-12 file had: each chimney an eight-sided tapered stone stack (128 triangles), two iron hoops, eight red
posts round a glowing box and a small tiled roof; each furnace three plain boxes (a dark stone block, a block on top
and a glowing square on its face, 36 triangles).

This build (same places, sizes and silhouettes; the hall, the flues and the smoke plumes are not touched):

- chimney tower (x +-10, y 39, as forge.py's _chimney): a square kiln stack of coursed dark ashlar (forge_ashlar: big
  blocks, soot darkening up the top third), on a granite footing and a battered base with a weathered cornice; light
  granite corner quoins (long and short in turn, 5 cm proud) up the whole shaft; two granite string courses split it
  into three stages, each with a bronze strap band and corner plates over it; on the top stage a framed medallion on
  the front and the east-facing side, the silver moon 月 on the west tower and the gold sun 日 on the east (together
  明); a corbelled cornice (two brick steps, a dentil course, two granite steps) with a gilt beast head out of each
  corner (gold on the sun tower, silver on the moon tower); then the fire storey: corner piers, a central mullion and
  two arched openings on the front and both sides (the back is solid), bronze grilles in the openings, the walls lined
  inside with forge_ember_wall (glowing fire-brick, bright at the bed, dark under the ceiling), a blackened-iron fire
  tray of coals on a molten bed, a red-lacquered ring beam, and a square tiled pyramid roof in place of the
  eight-sided one. About 12.7k triangles a tower, roof included.
- furnaces (x 0 and +-7.5, against the hall's back wall, as forge.py's _furnaces): fire-brick kilns (forge_firebrick)
  on a granite plinth, with an arched fire mouth framed by granite voussoirs, a keystone, jamb stones and a hearth
  sill; behind the mouth a real firebox (side walls, a floor and a back wall lined with forge_ember_wall) with a domed
  bed of embers and coals; an arched ash pit under the hearth glowing faintly, ash spilling onto the floor; two
  blackened-iron doors swung wide open; a stepped granite cornice; a bronze hood and an iron flue pipe on top (the
  side furnaces' pipes elbow back into the wall); a bronze beast mask with a ring over the great furnace's mouth;
  pokers and tongs leaning by the mouths; two box bellows (wood and iron) between the furnaces piping air into both
  neighbours; tool racks on the side walls; a coal heap. 1.5-1.8k triangles a furnace.
- flame anchors: Empties tagged obj[FIRE_TAG] = kind ('furnace', 'chimney', 'cauldron') at the foot of every fire, with
  fire_size (width, height, depth in the anchor's axes: x across, z up, y into the firebox), the fire mouth's size and
  where its plane is, for a furnace the plane the page draws its fire box on (fire_opening: just inside the firebox),
  and how many sides are open. export_web.py writes them to meta.json fires[] (pending diff) in the page's format
  (client/src/lib/sect/forge-flames.ts fireSourcesFromAnchors) so it draws live flames inside each firebox, each
  chimney's fire storey and over the cauldron.

New in round 29: areas/forge.py does not import it yet (r29/pending_forge.diff wires build_chimney / build_furnaces /
fire anchors in place of _chimney / _furnaces). sect/patch_r29_forge.py puts this build into an existing
out/sect_chase.blend. Every object and mesh this module makes carries obj[TAG] = 1.

The geometry is plain math (class Geo: vertex and face lists) so an offline check can count and measure it without
Blender; Blender is needed only where Geo becomes a mesh (Geo.to_bmesh) and where objects, materials and the roof are
made (build_*). Frames: the forge's local frame (front = -Y, z = 0 the courtyard paving); a chimney's own frame has its
origin on the paving at the tower's centre; a furnace's own frame has its origin on the hall floor (z 1.5) at the
middle of its front face, +y into the furnace.
"""

import math
import random

TAU = 2.0 * math.pi
KEY = "forge"
TAG = "forge_r29"                 # obj[TAG] = 1 on every object and mesh made here
FIRE_TAG = "sect_fire"            # obj[FIRE_TAG] = kind on the flame anchors (export_web meta.fires[])

# ------------------------------------------------------------------ placement (= areas/forge.py)
HALL_Y = 24.0
CHIMNEY_Y = HALL_Y + 15.0
FLOOR_Z = 1.5                     # the hall platform's top (forge._furnaces z0)
CHIMNEYS = ((0, -10.0, "moon"), (1, 10.0, "sun"))   # (index, x, medallion): west the moon 月, east the sun 日 -> 明
FURNACE_FRONT_Y = HALL_Y          # the old boxes' front face (y HALL_Y + 1.6 - 1.6)

# ------------------------------------------------------------------ materials (registered by register_materials)
M_ASHLAR = "forge_ashlar"         # the towers' coursed dark stone, soot up the top
M_DRESS = "forge_dressing"        # granite quoins, string courses, voussoirs, plinths
M_BRICK = "forge_firebrick"       # the furnaces' fire brick
M_EMBER = "forge_ember_wall"      # firebox / fire-storey lining: glows at the bed, dark under the ceiling ('ember':
                                  # bake_web GLOW_CLASSES)
M_COAL = "forge_coal"
M_ASH = "forge_ash"
M_MOLTEN = "molten"               # beds of embers (materials.py)
M_IRONB = "forge_iron"            # blackened forge iron: doors, pipes, tools, the fire trays
M_BRONZE, M_IRON, M_GOLD, M_SILVER = "bronze", "iron", "gold", "silver"
M_RED, M_WOOD = "lacquer_red", "wood_dark"
ROOF_TILE = "roof_tile_black"

# ------------------------------------------------------------------ chimney tower (chimney frame)
ROW = 0.55                        # ashlar course height (forge_ashlar Row Height) and quoin courses
FOOT = (-0.05, 0.38, 0.46, 3.20, 3.12)     # footing: z bottom, z edge, z top, half-width, top half-width (chamfer)
BASE = (0.40, 3.20, 2.95, 2.72)            # battered base: z0, z1, half-width at z0, at z1
BASE_CORNICE = ((2.76, 3.10), (2.86, 3.25), (2.86, 3.42), (2.20, 3.75))   # (half-width, z): weathered ledge
SHAFT = (3.50, 24.0, 2.30, 1.75)           # z0, z1, half-width at z0, at z1
STRINGS = (10.2, 17.2)            # granite string courses (bottom z)
STRING_SEC = ((-0.12, 0.0), (0.02, 0.0), (0.20, 0.12), (0.20, 0.30), (0.04, 0.40), (-0.12, 0.40))   # (d, dz)
BANDS = ((10.72, 11.02), (17.72, 18.02))   # bronze straps (z0, z1) just over the string courses
BAND_PROUD = 0.06
PLATE = (0.50, 0.10, 0.08)        # bronze corner plates: leg length, proud, overhang above/below the band
QUOIN = (0.85, 0.50, 0.05, 0.20, 0.025)    # long leg, short leg, proud, depth into the wall, joint
QUOIN_SKIP = ((10.1, 11.1), (17.1, 18.1))  # no quoins behind the string courses and bands
MEDAL_Z = 22.55                   # medallion centre (top stage; the west tower shows only above z ~22 over the hall)
MEDAL_FRAME = (0.95, 0.80, 0.07, 0.08)     # outer half, inner half, proud, into the wall
MEDAL_FACES = (0, 1)              # front (-Y) and the east-facing side (+X): the hold camera stands south-east
FRAME_FACES = (0, 1, 3)           # frames (without a medallion on -X)
CORBEL_H = 1.75                   # = SHAFT top half-width
CORBEL_SEC = ((-0.20, 24.0), (0.10, 24.0), (0.10, 24.28), (0.20, 24.28), (0.20, 24.86), (0.38, 24.86),
              (0.38, 25.14), (0.52, 25.14), (0.52, 25.5), (-0.20, 25.5))   # (d, z), closed
CORBEL_MAT = (0, 0, 0, 0, 0, 1, 1, 1, 1, 0)   # per section edge: brick steps ashlar, the top two granite
DENTIL = (24.56, 24.86, 0.20, 0.42, 0.10, 0.36)   # z0, z1, width, pitch, d0, d1
BEAST_Z = 24.71
BEAST_LEN = 1.25
# fire storey
ZL0, ZS, ZA, ARCH_RISE, ZT, ZB = 25.5, 25.85, 26.95, 0.32, 27.6, 27.95
HL = 2.17                         # outer half-width of the fire storey
TW = 0.47                         # wall thickness (= corner pier size)
HI = HL - TW                      # inner half-width
MULLION = 0.18                    # half-width of the central mullion
OPEN_FACES = (0, 1, 3)            # faces with two arched openings (the back is solid)
GRILLE = (0.25, 0.04, 26.42)      # bars: offset from the opening's centre, half-thickness, the cross bar's z
TRAY = (0.95, 0.30, 0.07)          # fire tray: half-width, height, wall thickness
ROOF = dict(rise=2.75, overhang=0.72)
LANTERN_GLOW = 3.0                # obj['glow'] on the fire storey (only forge_ember_wall reads it)
FIRE_GLOW = 3.0                   # on the fire tray's molten bed (as the old chimney_fire box)
CHIMNEY_FIRE = (1.6, 1.5, 1.6)    # flame volume at the chimney anchor (w, h, d)

# ------------------------------------------------------------------ furnaces (furnace frame)
# key: (x, W, H, D, tF, fd, mw, zs, jamb, aw, a_sp, mask): width, height, depth (into the wall), front wall thickness,
# firebox depth, mouth width (= 2 x arch radius), hearth (sill) height, jamb height, ash-pit width and spring height
FURNACES = (
    dict(i=0, x=0.0, W=5.0, H=4.6, D=3.2, tF=0.5, fd=1.65, mw=2.24, zs=0.90, jamb=0.95, aw=0.80, a_sp=0.42,
         mask=True, hood=(3.4, 2.0, 1.3, 1.1, 1.3), pipe=(0.40, 9.6), elbow=False),
    dict(i=1, x=-7.5, W=3.6, H=3.4, D=3.2, tF=0.45, fd=1.45, mw=1.60, zs=0.82, jamb=0.68, aw=0.62, a_sp=0.34,
         mask=False, hood=(2.4, 1.8, 1.0, 0.9, 0.9), pipe=(0.30, 5.6), elbow=True),
    dict(i=2, x=7.5, W=3.6, H=3.4, D=3.2, tF=0.45, fd=1.45, mw=1.60, zs=0.82, jamb=0.68, aw=0.62, a_sp=0.34,
         mask=False, hood=(2.4, 1.8, 1.0, 0.9, 0.9), pipe=(0.30, 5.6), elbow=True),
)
PLINTH = (0.12, 0.30, 0.04)       # proud, height, top chamfer
CORNICE_SEC = ((-0.15, 0.0), (0.06, 0.0), (0.06, 0.14), (0.14, 0.14), (0.14, 0.32), (0.24, 0.32), (0.24, 0.55),
               (-0.15, 0.55))     # (d, dz above Hb), closed
CORNICE_H = 0.55
VOUSSOIRS = 9
VOUSSOIR = (0.40, 0.08, 0.016, 0.12, 0.06)   # ring depth, proud, joint (rad), keystone extra out, extra proud
DOOR_OPEN = math.radians(150.0)
DOOR_T = 0.07
BODY_GLOW = 1.3                   # obj['glow'] on the furnace body (its firebox lining)
BED_GLOW = 2.5                    # on the beds (as the old furnace mouths)
OPENING_INSET = 0.03              # the page's fire-box plane: this far into the firebox past the stone mouth passage
PAGE_MOUTH_LIFT = 0.025           # forge-flames.ts FLAMES.mouthLift: the page's quad stands this far in front of that
                                  # plane (so 5 mm inside the firebox) and traces its box from there
DING_FLAME = 1.25                 # cauldron flame height per surface radius (forge-flames.ts FLAMES.cauldronHeight)
BELLOWS = ((-4.10, 25.35), (4.10, 25.35))    # forge-local centres, between the great furnace and the side ones
BELLOWS_SIZE = (0.70, 1.90, 0.85)            # x, y, z (body)
RACKS = ((-10.30, 22.4), (10.30, 22.4))      # forge-local, against the side walls (inner faces x +-10.6)
COAL_HEAP = (-3.55, 23.0)                   # forge-local, in front of the gap left of the great furnace

TRI_BUDGET = dict(chimney=26000, furnace=9000, extras=4000)   # per tower (all its pieces), per furnace, the rest


# ------------------------------------------------------------------ small vector maths (no mathutils offline)

def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    L = math.sqrt(_dot(a, a))
    return (a[0] / L, a[1] / L, a[2] / L) if L > 1e-12 else (0.0, 0.0, 1.0)


def _lerp(a, b, t):
    return a + (b - a) * t


def _rotz(p, ang, c=(0.0, 0.0, 0.0)):
    s, co = math.sin(ang), math.cos(ang)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + co * x - s * y, c[1] + s * x + co * y, p[2])


class Frame:
    """Orthonormal frame: p(x, y, z) = o + x*X + y*Y + z*Z."""

    def __init__(self, o, X, Y, Z):
        self.o, self.X, self.Y, self.Z = o, X, Y, Z

    def p(self, x, y, z):
        return _add(self.o, _add(_mul(self.X, x), _add(_mul(self.Y, y), _mul(self.Z, z))))

    def v(self, x, y, z):
        return _add(_mul(self.X, x), _add(_mul(self.Y, y), _mul(self.Z, z)))


def frame_fwd(o, fwd, up=(0.0, 0.0, 1.0)):
    """Frame with X along ``fwd``, Z as near ``up`` as possible."""
    X = _norm(fwd)
    Y = _norm(_cross(up, X))
    Z = _cross(X, Y)
    return Frame(o, X, Y, Z)


# ------------------------------------------------------------------ Geo: an object's pieces as plain lists

class Geo:
    """Pieces of one object. A 'solid' piece is closed: Geo.to_bmesh turns its faces outward. A 'sheet' is open and
    keeps the winding given (each sheet here is wound to face where it should)."""

    def __init__(self):
        self.pieces = []          # (verts, faces, mats, kind)

    def add(self, verts, faces, mats, kind="solid"):
        if isinstance(mats, int):
            mats = [mats] * len(faces)
        assert len(mats) == len(faces)
        self.pieces.append((list(verts), [tuple(f) for f in faces], list(mats), kind))

    def extend(self, other):
        self.pieces.extend(other.pieces)

    def tris(self):
        return sum(len(f) - 2 for _v, fs, _m, _k in self.pieces for f in fs)

    def bounds(self):
        vs = [v for vv, _f, _m, _k in self.pieces for v in vv]
        return (tuple(min(v[k] for v in vs) for k in range(3)), tuple(max(v[k] for v in vs) for k in range(3)))

    def transformed(self, fn):
        g = Geo()
        for vs, fs, ms, kind in self.pieces:
            g.pieces.append(([fn(v) for v in vs], fs, ms, kind))
        return g

    def open_edges(self):
        """Edges of solid pieces not in exactly two faces (0 for a clean build)."""
        n = 0
        for vs, fs, _m, kind in self.pieces:
            if kind != "solid":
                continue
            cnt = {}
            for f in fs:
                for k in range(len(f)):
                    e = (min(f[k], f[(k + 1) % len(f)]), max(f[k], f[(k + 1) % len(f)]))
                    cnt[e] = cnt.get(e, 0) + 1
            n += sum(1 for c in cnt.values() if c != 2)
        return n

    def to_bmesh(self):
        """BMesh of every piece (solids recalculated outward, one piece at a time)."""
        import bmesh
        bm = bmesh.new()
        for vs, fs, ms, kind in self.pieces:
            tb = bmesh.new()
            tv = [tb.verts.new(v) for v in vs]
            for f, m in zip(fs, ms):
                bf = tb.faces.new([tv[i] for i in f])
                bf.material_index = m
            tb.normal_update()
            if kind == "solid":
                bmesh.ops.recalc_face_normals(tb, faces=tb.faces[:])
            tb.verts.index_update()
            mv = [bm.verts.new(v.co) for v in tb.verts]
            for bf in tb.faces:
                nf = bm.faces.new([mv[v.index] for v in bf.verts])
                nf.material_index = bf.material_index
                nf.smooth = False
            tb.free()
        bm.normal_update()
        return bm


# ------------------------------------------------------------------ primitives (all return (verts, faces, mats))

def hexa(pts, mats=0):
    """Closed hexahedron: pts = 4 bottom corners (in order round), then the 4 top corners above them. mats: one index
    or (bottom, top, side 0..3) where side k runs from corner k to corner k+1."""
    faces = [(3, 2, 1, 0), (4, 5, 6, 7)] + [(k, (k + 1) % 4, 4 + (k + 1) % 4, 4 + k) for k in range(4)]
    if isinstance(mats, int):
        mats = [mats] * 6
    return list(pts), faces, list(mats)


def box(c, s, mats=0):
    x0, x1 = c[0] - s[0] / 2, c[0] + s[0] / 2
    y0, y1 = c[1] - s[1] / 2, c[1] + s[1] / 2
    z0, z1 = c[2] - s[2] / 2, c[2] + s[2] / 2
    return hexa([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                 (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], mats)


def box_fr(F, x0, x1, y0, y1, z0, z1, mats=0):
    """Box in frame F (side 0 at y0, 1 at x1, 2 at y1, 3 at x0)."""
    P = F.p
    return hexa([P(x0, y0, z0), P(x1, y0, z0), P(x1, y1, z0), P(x0, y1, z0),
                 P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)], mats)


def loft(rings, cap0=True, cap1=True, mats=0, closed=True):
    """Rings of equal length (each closed round) stacked into a tube; caps as n-gons. mats: one index or one per
    ring-to-ring segment (then caps take the first / last)."""
    n = len(rings[0])
    verts = [p for r in rings for p in r]
    faces, fm = [], []
    for s in range(len(rings) - 1):
        m = mats if isinstance(mats, int) else mats[s]
        for k in range(n if closed else n - 1):
            k2 = (k + 1) % n
            faces.append((s * n + k, s * n + k2, (s + 1) * n + k2, (s + 1) * n + k))
            fm.append(m)
    if cap0:
        faces.append(tuple(reversed(range(n))))
        fm.append(mats if isinstance(mats, int) else mats[0])
    if cap1:
        b = (len(rings) - 1) * n
        faces.append(tuple(range(b, b + n)))
        fm.append(mats if isinstance(mats, int) else mats[-1])
    return verts, faces, fm


def sweep_rect(section, hx, hy, cx=0.0, cy=0.0, mats=0, hfn=None):
    """Closed section [(d, z)] swept round a rectangle (half-widths hx, hy, centre cx, cy; hfn(z) -> extra
    half-width for a battered wall): a ring of mitred corners, closed both ways (no caps). mats per section edge."""
    rings = []
    for d, z in section:
        e = hfn(z) if hfn else 0.0
        X, Y = hx + d + e, hy + d + e
        rings.append([(cx - X, cy - Y, z), (cx + X, cy - Y, z), (cx + X, cy + Y, z), (cx - X, cy + Y, z)])
    n, S = 4, len(rings)
    verts = [p for r in rings for p in r]
    faces, fm = [], []
    for s in range(S):
        s2 = (s + 1) % S
        m = mats if isinstance(mats, int) else mats[s]
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((s * n + k, s * n + k2, s2 * n + k2, s2 * n + k))
            fm.append(m)
    return verts, faces, fm


def prism_fr(F, outline, y0, y1, mats=0, stations=None, edge_mats=None, cap_mats=None):
    """Polygon ``outline`` [(x, z)] in frame F's XZ plane extruded along F.Y from y0 to y1 (or through ``stations``,
    a list of y). edge_mats[k][s]: material of the side face on outline edge k in segment s; cap_mats: (first, last)."""
    ys = stations if stations is not None else [y0, y1]
    n = len(outline)
    rings = [[F.p(x, y, z) for x, z in outline] for y in ys]
    verts = [p for r in rings for p in r]
    faces, fm = [], []
    for s in range(len(ys) - 1):
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((s * n + k, s * n + k2, (s + 1) * n + k2, (s + 1) * n + k))
            fm.append(edge_mats[k][s] if edge_mats else mats)
    faces.append(tuple(reversed(range(n))))
    faces.append(tuple(range((len(ys) - 1) * n, len(ys) * n)))
    cm = cap_mats if cap_mats else (mats, mats)
    fm += [cm[0], cm[1]]
    return verts, faces, fm


def tube(path, radii, sides=8, mats=0, caps=True, up=(0.0, 0.0, 1.0)):
    """Tube through path points with a radius per point (parallel-transported frames)."""
    if isinstance(radii, (int, float)):
        radii = [radii] * len(path)
    n = len(path)
    tans = []
    for i in range(n):
        a, b = path[max(i - 1, 0)], path[min(i + 1, n - 1)]
        tans.append(_norm(_sub(b, a)))
    ref = up if abs(_dot(up, tans[0])) < 0.95 else (1.0, 0.0, 0.0)
    u = _norm(_cross(tans[0], ref))
    rings = []
    for i in range(n):
        t = tans[i]
        u = _norm(_sub(u, _mul(t, _dot(u, t))))
        w = _cross(t, u)
        r = radii[i]
        rings.append([_add(path[i], _add(_mul(u, r * math.cos(TAU * k / sides)),
                                         _mul(w, r * math.sin(TAU * k / sides)))) for k in range(sides)])
    return loft(rings, caps, caps, mats)


def icosa(c, r, rnd, squash=(1.0, 1.0, 1.0), jitter=0.18, mats=0):
    """Rough lump: a jittered icosahedron (20 triangles)."""
    t = (1.0 + 5 ** 0.5) / 2.0
    base = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
            (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
             (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11),
             (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    a = rnd.uniform(0, TAU)
    verts = []
    for p in base:
        q = _norm(p)
        k = r * (1.0 + rnd.uniform(-jitter, jitter))
        q = (q[0] * k * squash[0], q[1] * k * squash[1], q[2] * k * squash[2])
        q = _rotz(q, a)
        verts.append(_add(c, q))
    return verts, faces, [mats] * 20 if isinstance(mats, int) else mats


def sheet_grid(xs, ys, zfn, mats=0, flip=False):
    """Open height-field sheet over the grid xs x ys facing up (z = zfn(x, y))."""
    nx, ny = len(xs), len(ys)
    verts = [(x, y, zfn(x, y)) for y in ys for x in xs]
    faces = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a, b = j * nx + i, j * nx + i + 1
            c, d = (j + 1) * nx + i + 1, (j + 1) * nx + i
            faces.append((a, b, c, d) if not flip else (d, c, b, a))
    return verts, faces, [mats] * len(faces)


def arch_pts(cx, zc, r, a0, a1, n):
    """Points on a circle arc in XZ (angles in radians, inclusive)."""
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), zc + r * math.sin(a0 + (a1 - a0) * k / n))
            for k in range(n + 1)]


# ------------------------------------------------------------------ chimney tower

FACE_N = ((0.0, -1.0), (1.0, 0.0), (0.0, 1.0), (-1.0, 0.0))   # face 0 front (-Y), 1 +X, 2 back, 3 -X


def shaft_hw(z):
    z0, z1, h0, h1 = SHAFT
    return _lerp(h0, h1, min(max((z - z0) / (z1 - z0), 0.0), 1.0))


def face_frame(f, dist):
    """Frame on tower face f: X along the face (counter-clockwise seen from above), Y outward, Z up; origin on the
    axis plane at distance ``dist`` out (so p(u, d, z) = a point u along the face, d out from dist, at height z)."""
    n = (FACE_N[f][0], FACE_N[f][1], 0.0)
    t = (-n[1], n[0], 0.0)
    return Frame(_mul(n, dist), t, n, (0.0, 0.0, 1.0))


def _sq(h, z):
    return [(-h, -h, z), (h, -h, z), (h, h, z), (-h, h, z)]


def tower_masonry(flue_dir=None):
    """The tower's stone: footing, base, base cornice, shaft, string courses, corbel cornice, dentils, quoins,
    medallion frames, the flue inlet surround (slots: 0 forge_ashlar, 1 forge_dressing)."""
    g = Geo()
    zb, ze, zt, hf, ht = FOOT
    g.add(*loft([_sq(hf, zb), _sq(hf, ze), _sq(ht, zt)], mats=1))
    z0, z1, h0, h1 = BASE
    g.add(*loft([_sq(h0, z0), _sq(h1, z1)], mats=0))
    g.add(*loft([_sq(h, z) for h, z in BASE_CORNICE], mats=1))
    z0, z1, h0, h1 = SHAFT
    g.add(*loft([_sq(shaft_hw(z0), z0), _sq(shaft_hw(z1), z1)], mats=0))
    for zc in STRINGS:
        sec = [(d, zc + dz) for d, dz in STRING_SEC]
        g.add(*sweep_rect(sec, 0.0, 0.0, mats=1, hfn=shaft_hw))
    g.add(*sweep_rect(CORBEL_SEC, CORBEL_H, CORBEL_H, mats=list(CORBEL_MAT)))
    hc = CORBEL_H + CORBEL_SEC[0][0]                       # the corbel's core: fills its ring, its top the storey floor
    g.add(*box((0.0, 0.0, (SHAFT[1] - 0.1 + ZL0) / 2), (2 * hc, 2 * hc, ZL0 - SHAFT[1] + 0.1), mats=1))
    # dentils on the four faces (between the brick steps and the granite steps)
    dz0, dz1, dw, pitch, d0, d1 = DENTIL
    span = CORBEL_H + 0.20 - 0.30
    nd = int(span * 2 / pitch)
    for f in range(4):
        F = face_frame(f, CORBEL_H)
        for k in range(nd + 1):
            u = -span + k * (2 * span / nd)
            g.add(*box_fr(F, u - dw / 2, u + dw / 2, d0, d1, dz0, dz1, mats=1))
    # quoins: long and short legs in turn, following the batter
    Lx, Ly, proud, depth, joint = QUOIN
    z = math.ceil(SHAFT[0] / ROW - 1e-9) * ROW            # on the ashlar's courses (rows from z 0)
    c = 0
    while z + ROW <= SHAFT[1] - 0.05:
        za, zb2 = z, z + ROW - joint
        if not any(a - 0.02 < zb2 and za < b + 0.02 for a, b in QUOIN_SKIP):
            for k, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
                lx, ly = (Lx, Ly) if (c + k) % 2 == 0 else (Ly, Lx)
                rings = []
                for zz in (za, zb2):
                    h = shaft_hw(zz)
                    o = h + proud
                    pts = [(o, o), (o, o - ly), (h - depth, o - ly), (h - depth, h - depth), (o - lx, h - depth),
                           (o - lx, o)]
                    if sx * sy < 0:
                        pts = list(reversed(pts))
                    rings.append([(sx * x, sy * y, zz) for x, y in pts])
                g.add(*loft(rings, mats=1))
        z += ROW
        c += 1
    # medallion frames: four granite bars round a square field on the face
    oh, ih, fp, fd = MEDAL_FRAME
    for f in FRAME_FACES:
        F = face_frame(f, shaft_hw(MEDAL_Z))
        for (u0, u1, z0_, z1_) in ((-oh, oh, MEDAL_Z - oh, MEDAL_Z - ih), (-oh, oh, MEDAL_Z + ih, MEDAL_Z + oh),
                                   (-oh, -ih, MEDAL_Z - ih, MEDAL_Z + ih), (ih, oh, MEDAL_Z - ih, MEDAL_Z + ih)):
            g.add(*box_fr(F, u0, u1, -fd, fp, z0_, z1_, mats=1))
    # the flue inlet: two jamb stones and a lintel round the flue where it meets the base (on the front face)
    if flue_dir is not None:
        ux = flue_dir                             # u on the front face where the flue's axis crosses it
        F = face_frame(0, BASE[2] - 0.12)
        for s in (-1.0, 1.0):
            a, b = sorted((ux + s * 0.76, ux + s * 1.10))
            g.add(*box_fr(F, a, b, -0.25, 0.30, 0.0, 2.95, mats=1))
        g.add(*box_fr(F, ux - 1.16, ux + 1.16, -0.25, 0.34, 2.95, 3.35, mats=1))
    return g


def _sun(F):
    g = Geo()
    n = 20
    disc = [(0.40 * math.cos(TAU * k / n), MEDAL_Z + 0.40 * math.sin(TAU * k / n)) for k in range(n)]
    g.add(*prism_fr(F, disc, -0.06, 0.10))
    boss = [(0.18 * math.cos(TAU * k / n), MEDAL_Z + 0.18 * math.sin(TAU * k / n)) for k in range(n)]
    g.add(*prism_fr(F, boss, 0.05, 0.16))
    for k in range(12):
        a = TAU * k / 12 + math.pi / 2
        L = 0.70 if k % 2 == 0 else 0.60
        ca, sa = math.cos(a), math.sin(a)
        tri = [(0.44 * ca - 0.09 * sa, MEDAL_Z + 0.44 * sa + 0.09 * ca), (L * ca, MEDAL_Z + L * sa),
               (0.44 * ca + 0.09 * sa, MEDAL_Z + 0.44 * sa - 0.09 * ca)]
        g.add(*prism_fr(F, tri, -0.04, 0.07))
    return g


def _moon(F):
    """A crescent opening to the upper right (the outer circle less an offset inner one) and a four-pointed star."""
    g = Geo()
    R0, R1, c1 = 0.58, 0.47, (0.19, 0.11)
    L = math.hypot(*c1)
    phi = math.atan2(c1[1], c1[0])
    d = (R0 * R0 + L * L - R1 * R1) / (2 * L)                # the crossing points' projection on the centres' line
    w = math.acos(d / R0)
    t0, t1 = phi + w, phi - w + TAU                          # outer arc, counter-clockwise the long way round
    p0 = (R0 * math.cos(t0), R0 * math.sin(t0))
    p1 = (R0 * math.cos(t1), R0 * math.sin(t1))
    b1 = math.atan2(p0[1] - c1[1], p0[0] - c1[0])            # inner circle angles of the two crossings
    b0 = math.atan2(p1[1] - c1[1], p1[0] - c1[0])
    while b0 < b1:
        b0 += TAU
    out = [(R0 * math.cos(t0 + (t1 - t0) * k / 30), R0 * math.sin(t0 + (t1 - t0) * k / 30)) for k in range(31)]
    out += [(c1[0] + R1 * math.cos(b0 + (b1 - b0) * k / 16), c1[1] + R1 * math.sin(b0 + (b1 - b0) * k / 16))
            for k in range(1, 16)]
    g.add(*prism_fr(F, [(x, MEDAL_Z + z) for x, z in out], -0.06, 0.10))
    star = []
    for k in range(8):
        a = TAU * k / 8 + math.pi / 2
        r = 0.16 if k % 2 == 0 else 0.055
        star.append((0.28 + r * math.cos(a), MEDAL_Z + 0.22 + r * math.sin(a)))
    g.add(*prism_fr(F, star, -0.05, 0.08))
    return g


def beast_head(F, s=1.0, mat=0):
    """Low-poly bronze corner beast (chiwen) in frame F: +X the snout, +Z up, the back embedded at x < 0."""
    g = Geo()

    def bx(x0, x1, y0a, y1a, z0a, z1a, y0b=None, y1b=None, z0b=None, z1b=None):
        y0b = y0a if y0b is None else y0b
        y1b = y1a if y1b is None else y1b
        z0b = z0a if z0b is None else z0b
        z1b = z1a if z1b is None else z1b
        P = lambda x, y, z: F.p(x * s, y * s, z * s)   # noqa: E731
        g.add(*hexa([P(x0, y0a, z0a), P(x1, y0b, z0b), P(x1, y1b, z0b), P(x0, y1a, z0a),
                     P(x0, y0a, z1a), P(x1, y0b, z1b), P(x1, y1b, z1b), P(x0, y1a, z1a)], mat))
    bx(-0.28, 0.30, -0.17, 0.17, -0.15, 0.17, -0.15, 0.15, -0.12, 0.16)          # skull
    bx(0.28, 0.82, -0.13, 0.13, -0.07, 0.12, -0.09, 0.09, -0.03, 0.13)           # snout
    bx(0.78, 0.92, -0.06, 0.06, 0.02, 0.15, -0.05, 0.05, 0.04, 0.16)             # nose knob
    bx(0.18, 0.74, -0.11, 0.11, -0.24, -0.12, -0.07, 0.07, -0.33, -0.24)         # open lower jaw
    for sy in (-1.0, 1.0):
        bx(0.10, 0.36, sy * 0.07, sy * 0.19, 0.13, 0.22)                         # brows
        g.add(*tube([F.p(0.0, sy * 0.09 * s, 0.14 * s), F.p(-0.22 * s, sy * 0.17 * s, 0.34 * s),
                     F.p(-0.50 * s, sy * 0.23 * s, 0.46 * s), F.p(-0.70 * s, sy * 0.22 * s, 0.44 * s)],
                    [0.055 * s, 0.045 * s, 0.03 * s, 0.012 * s], sides=5, mats=mat))  # horns
        g.add(*tube([F.p(0.80 * s, sy * 0.07 * s, -0.02 * s), F.p(0.80 * s, sy * 0.07 * s, -0.13 * s)],
                    [0.025 * s, 0.006 * s], sides=4, mats=mat))                  # fangs
    fin = [(-0.30, -0.08), (0.06, 0.12), (-0.08, 0.42), (-0.40, 0.34), (-0.58, 0.06)]
    Ff = Frame(F.o, F.X, F.Y, F.Z)
    g.add(*prism_fr(Ff, [(x * s, z * s) for x, z in fin], -0.035 * s, 0.035 * s, mats=mat))   # mane fin
    return g


def tower_bronze(emblem):
    """Bronze straps and corner plates, the medallions and the corner beasts (gilt), the fire storey's grilles (slots:
    0 bronze, 1 gold or silver)."""
    g = Geo()
    for z0, z1 in BANDS:
        sec = [(-0.05, z0), (BAND_PROUD, z0), (BAND_PROUD, z1), (-0.05, z1)]
        g.add(*sweep_rect(sec, 0.0, 0.0, mats=0, hfn=shaft_hw))
        L, p, ov = PLATE
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            rings = []
            for zz in (z0 - ov, z1 + ov):
                h = shaft_hw(zz)
                o = h + p
                pts = [(o, o), (o, o - L), (h - 0.09, o - L), (h - 0.09, h - 0.09), (o - L, h - 0.09), (o - L, o)]
                if sx * sy < 0:
                    pts = list(reversed(pts))
                rings.append([(sx * x, sy * y, zz) for x, y in pts])
            g.add(*loft(rings, mats=0))
    for f in MEDAL_FACES:
        F = face_frame(f, shaft_hw(MEDAL_Z))
        e = _sun(F) if emblem == "sun" else _moon(F)
        for vs, fs, ms, kind in e.pieces:
            g.add(vs, fs, [1] * len(fs), kind)
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        c = (sx * (CORBEL_H + 0.20), sy * (CORBEL_H + 0.20), BEAST_Z)
        F = frame_fwd(c, (sx, sy, 0.12))
        g.extend(beast_head(F, s=BEAST_LEN, mat=1))
    # grilles: two uprights and a cross bar in each opening of the fire storey
    off, ht, zc = GRILLE
    for f in OPEN_FACES:
        F = face_frame(f, 0.0)
        dmid = HL - 0.17
        for uc in (-(HI + MULLION) / 2, (HI + MULLION) / 2):
            for du in (-off, off):
                u = uc + du
                ztop = _arch_z(u, uc) + 0.04
                g.add(*box_fr(F, u - ht, u + ht, dmid - ht, dmid + ht, ZS - 0.03, ztop, mats=0))
            a = (HI - MULLION) / 2
            g.add(*box_fr(F, uc - a - 0.03, uc + a + 0.03, dmid - ht * 0.6, dmid + ht * 0.6, zc - ht, zc + ht,
                          mats=0))
    return g


def _arch(uc):
    """The segmental arch over an opening centred at u = uc: (centre z, radius, half-width)."""
    a = (HI - MULLION) / 2
    h = ARCH_RISE
    R = (a * a + h * h) / (2 * h)
    return ZA + h - R, R, a


def _arch_z(u, uc):
    zc, R, a = _arch(uc)
    du = u - uc
    return zc + math.sqrt(max(R * R - du * du, 0.0))


def tower_lantern():
    """The fire storey: corner piers, sills, mullions, the arched spandrels, the solid back wall, the ceiling and the
    red ring beam (slots: 0 forge_ashlar, 1 forge_dressing, 2 forge_ember_wall, 3 lacquer_red)."""
    g = Geo()
    A, D, E, R = 0, 1, 2, 3
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        x0, x1 = sorted((sx * HI, sx * HL))
        y0, y1 = sorted((sy * HI, sy * HL))
        # sides: 0 at y0, 1 at x1, 2 at y1, 3 at x0; outer where |coordinate| = HL, else jamb (dressing)
        sides = [A if abs(y0) > HL - 1e-6 else D, A if abs(x1) > HL - 1e-6 else D,
                 A if abs(y1) > HL - 1e-6 else D, A if abs(x0) > HL - 1e-6 else D]
        g.add(*hexa([(x0, y0, ZL0), (x1, y0, ZL0), (x1, y1, ZL0), (x0, y1, ZL0),
                     (x0, y0, ZT), (x1, y0, ZT), (x1, y1, ZT), (x0, y1, ZT)], [A, A] + sides))
    for f in range(4):
        F = face_frame(f, 0.0)
        # face frame sides: 0 at y=d0 (inner), 1 at x=u1, 2 at y=d1 (outer), 3 at x=u0
        if f not in OPEN_FACES:
            g.add(*box_fr(F, -HI, HI, HI, HL, ZL0, ZT, mats=[A, A, E, D, A, D]))
            continue
        g.add(*box_fr(F, -HI, HI, HI, HL, ZL0, ZS, mats=[A, D, E, D, A, D]))                  # sill
        g.add(*box_fr(F, -MULLION, MULLION, HI, HL, ZS, ZA, mats=[A, A, E, D, A, D]))         # mullion
        out = [(-HI, ZA)]
        for uc in (-(HI + MULLION) / 2, (HI + MULLION) / 2):
            zc, Rr, a = _arch(uc)
            a0 = math.pi - math.acos(a / Rr)
            a1 = math.acos(a / Rr)
            pts = arch_pts(uc, zc, Rr, a0, a1, 8)
            out += pts[0 if uc > 0 else 1:]
        out += [(HI, ZT), (-HI, ZT)]
        # de-duplicate the joints (mullion top corners are arch end points)
        clean = []
        for p in out:
            if not clean or abs(p[0] - clean[-1][0]) > 1e-6 or abs(p[1] - clean[-1][1]) > 1e-6:
                clean.append(p)
        if abs(clean[0][0] - clean[-1][0]) < 1e-6 and abs(clean[0][1] - clean[-1][1]) < 1e-6:
            clean.pop()
        Fz = Frame(F.o, F.X, F.Y, F.Z)
        # prism along the face's outward axis: frame with X = u, Y = outward, Z = up -> outline in (u, z)
        n = len(clean)
        edge_mats = [[D] for _ in range(n)]
        g.add(*prism_fr(Fz, clean, HI, HL, edge_mats=edge_mats, cap_mats=(E, A)))
    g.add(*box((0.0, 0.0, ZT - 0.10), (2 * HI, 2 * HI, 0.20), mats=E))                       # ceiling
    sec = [(-0.36, ZT), (0.06, ZT), (0.06, ZB), (-0.36, ZB)]
    g.add(*sweep_rect(sec, HL, HL, mats=R))                                                   # ring beam
    return g


def tower_fire(seed):
    """The fire tray on the storey's floor: an iron tray, a domed molten bed and coal lumps (slots: 0 iron, 1 molten,
    2 forge_coal)."""
    g = Geo()
    h, th, w = TRAY
    z0 = ZL0 - 0.02
    g.add(*box((0.0, 0.0, z0 + 0.04), (2 * h, 2 * h, 0.08), mats=0))
    for (cx, cy, sx, sy) in ((0.0, -h + w / 2, 2 * h, w), (0.0, h - w / 2, 2 * h, w),
                             (-h + w / 2, 0.0, w, 2 * h - 2 * w), (h - w / 2, 0.0, w, 2 * h - 2 * w)):
        g.add(*box((cx, cy, z0 + th / 2), (sx, sy, th), mats=0))
    rnd = random.Random(seed)
    k = h - w - 0.01
    xs = [-k + 2 * k * i / 6 for i in range(7)]

    def bed(x, y):
        r = max(abs(x), abs(y)) / k
        return z0 + 0.22 + 0.14 * (1.0 - r * r) + 0.02 * math.sin(7 * x + 3 * y)
    g.add(*sheet_grid(xs, xs, bed, mats=1), kind="sheet")
    for i in range(22):
        x, y = rnd.uniform(-k * 0.9, k * 0.9), rnd.uniform(-k * 0.9, k * 0.9)
        r = rnd.uniform(0.08, 0.15)
        g.add(*icosa((x, y, bed(x, y) + 0.02), r, rnd, squash=(1.0, 1.0, 0.7), mats=2 if i % 4 else 1))
    return g


def chimney_fire_anchor_local():
    """(location in the chimney frame, size (w, h, d))."""
    return (0.0, 0.0, ZL0 + 0.30), CHIMNEY_FIRE


def chimney_geos(emblem, flue_u=None, seed=0):
    return dict(masonry=tower_masonry(flue_u), bronze=tower_bronze(emblem), lantern=tower_lantern(),
                fire=tower_fire(seed))


# ------------------------------------------------------------------ furnaces

def _mouth(fz):
    """Mouth geometry of a furnace dict: (r, z spring, z crown)."""
    r = fz["mw"] / 2
    zsp = fz["zs"] + fz["jamb"]
    return r, zsp, zsp + r


def _ash(fz):
    ar = fz["aw"] / 2
    return ar, fz["a_sp"], fz["a_sp"] + ar


def furnace_body(fz):
    """Plinth, the two halves of the body (front wall with the mouth and the ash pit, the firebox's side walls and
    floor), the block behind the firebox (its front is the firebox's back wall), the cornice, the voussoirs, keystone,
    jamb stones and the hearth sill (slots: 0 forge_firebrick, 1 forge_dressing, 2 forge_ember_wall)."""
    g = Geo()
    B, D, E = 0, 1, 2
    W, H, Dp, tF, fd = fz["W"], fz["H"], fz["D"], fz["tF"], fz["fd"]
    Hb = H - CORNICE_H
    pr, ph, pc = PLINTH
    x0, x1, y0, y1 = -W / 2 - pr, W / 2 + pr, -pr, Dp
    g.add(*hexa([(x0, y0, -0.06), (x1, y0, -0.06), (x1, y1, -0.06), (x0, y1, -0.06),
                 (x0 + pc, y0 + pc, ph), (x1 - pc, y0 + pc, ph), (x1 - pc, y1, ph), (x0 + pc, y1, ph)], D))
    r, zsp, zcr = _mouth(fz)
    ar, asp, acr = _ash(fz)
    zs = fz["zs"]
    na, nm = 4, 8
    # left half outline (x <= 0), counter-clockwise in (x, z); edge kinds for materials
    pts, kinds = [], []

    def P(p, kind):
        pts.append(p)
        kinds.append(kind)
    P((-W / 2, ph), "out")
    P((-ar, ph), "ash")
    for p in arch_pts(0.0, asp, ar, math.pi, math.pi / 2, na):
        P(p, "ash")
    kinds[-1] = "mid"
    P((0.0, zs), "sill")
    P((-r, zs), "mouth")
    for p in arch_pts(0.0, zsp, r, math.pi, math.pi / 2, nm):
        P(p, "mouth")
    kinds[-1] = "mid"
    P((0.0, Hb + CORNICE_H), "out")
    P((-W / 2, Hb + CORNICE_H), "out")
    # edge k runs from pts[k] to pts[k+1]; its kind is kinds[k]
    st = [0.0, tF, tF + fd]

    def emats(kind):
        if kind == "mouth":
            return [D, E]
        if kind == "sill":
            return [D, E]
        if kind == "ash":
            return [D, B]
        return [B, B]
    F = Frame((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    left = (pts, [emats(k) for k in kinds])
    # the right half: mirrored and reversed, so its edge k is the mirror of the left's edge n-2-k
    n = len(pts)
    right_pts = [(-x, z) for x, z in reversed(pts)]
    rk = [kinds[(n - 2 - k) % n] for k in range(n)]
    for outline, em in (left, (right_pts, [emats(k) for k in rk])):
        g.add(*prism_fr(F, outline, 0.0, 0.0, stations=st, edge_mats=em, cap_mats=(B, B)))
    # behind the firebox, full width; its front face is the firebox's back wall
    g.add(*hexa([(-W / 2, tF + fd, ph), (W / 2, tF + fd, ph), (W / 2, Dp, ph), (-W / 2, Dp, ph),
                 (-W / 2, tF + fd, H), (W / 2, tF + fd, H), (W / 2, Dp, H), (-W / 2, Dp, H)],
                [B, B, E, B, B, B]))
    # stepped cornice round the top (its back runs into the hall's wall)
    sec = [(d, Hb + dz) for d, dz in CORNICE_SEC]
    g.add(*sweep_rect(sec, W / 2, Dp / 2, 0.0, Dp / 2, mats=D))
    # voussoirs round the mouth (in front of the face), the keystone bigger and prouder
    ring, proud, joint, kx, kp = VOUSSOIR
    nv = VOUSSOIRS
    for k in range(nv):
        a0 = math.pi - k * math.pi / nv - (joint / 2 if k else 0.0)
        a1 = math.pi - (k + 1) * math.pi / nv + (joint / 2 if k < nv - 1 else 0.0)
        key = k == nv // 2
        ro = r + ring + (kx if key else 0.0)
        yp = -(proud + (kp if key else 0.0))
        q = [(r * math.cos(a0), zsp + r * math.sin(a0)), (r * math.cos(a1), zsp + r * math.sin(a1)),
             (ro * math.cos(a1), zsp + ro * math.sin(a1)), (ro * math.cos(a0), zsp + ro * math.sin(a0))]
        g.add(*hexa([(q[i][0], yp, q[i][1]) for i in range(4)] + [(q[i][0], 0.0, q[i][1]) for i in range(4)], D))
    # jamb stones (two a side, wide and narrow in turn) and the hearth sill
    for s in (-1.0, 1.0):
        zz = [zs, zs + (zsp - zs) * 0.5, zsp]
        for k in range(2):
            w = 0.42 if (k == 0) == (s < 0) else 0.28
            xa, xb = sorted((s * r, s * (r + w)))
            g.add(*box(((xa + xb) / 2, -0.03, (zz[k] + zz[k + 1]) / 2 + 0.0),
                       (xb - xa, 0.06, zz[k + 1] - zz[k] - 0.016), D))
    sx = r + 0.32
    g.add(*hexa([(-sx, -0.22, zs - 0.16), (sx, -0.22, zs - 0.16), (sx, 0.0, zs - 0.16), (-sx, 0.0, zs - 0.16),
                 (-sx, -0.18, zs), (sx, -0.18, zs), (sx, 0.0, zs), (-sx, 0.0, zs)], D))
    return g


def furnace_bed(fz, seed):
    """The firebox's bed of embers and coals, and the ash pit's dull embers (slots: 0 molten, 1 forge_coal)."""
    g = Geo()
    r, _zsp, _zcr = _mouth(fz)
    tF, fd, zs = fz["tF"], fz["fd"], fz["zs"]
    ar, _asp, _acr = _ash(fz)
    rnd = random.Random(seed)
    xa = r - 0.06
    xs = [-xa + 2 * xa * i / 6 for i in range(7)]
    ys = [tF - 0.10 + (fd + 0.04) * j / 5 for j in range(6)]

    def bed(x, y):
        t = (y - tF) / fd
        return zs + 0.035 + 0.16 * (1.0 - (x / xa) ** 2) * min(1.0, 0.4 + t) + 0.015 * math.sin(9 * x + 5 * y)
    g.add(*sheet_grid(xs, ys, bed, mats=0), kind="sheet")
    for i in range(18):
        x, y = rnd.uniform(-xa * 0.85, xa * 0.85), rnd.uniform(tF + 0.1, tF + fd - 0.15)
        rr = rnd.uniform(0.07, 0.13)
        g.add(*icosa((x, y, bed(x, y) + 0.01), rr, rnd, squash=(1.0, 1.0, 0.7), mats=1 if i % 3 else 0))
    xs = [-ar + 0.05 + (2 * ar - 0.10) * i / 3 for i in range(4)]
    ys = [0.10 + (tF + fd - 0.25) * j / 3 for j in range(4)]
    g.add(*sheet_grid(xs, ys, lambda x, y: PLINTH[1] + 0.035 + 0.02 * math.sin(11 * x + 7 * y), mats=0),
          kind="sheet")
    return g


def furnace_iron(fz, seed):
    """Two iron doors swung wide, their straps, pokers and tongs leaning by the mouth, and (great furnace) the bronze
    beast mask with its ring over the keystone (slots: 0 iron, 1 bronze)."""
    g = Geo()
    r, zsp, zcr = _mouth(fz)
    zs = fz["zs"]
    for s in (-1.0, 1.0):
        hinge = (s * (r + 0.06), -0.15, 0.0)              # in front of the jamb stones (5 cm proud)
        w = r + 0.06
        rr = r + 0.06
        # closed leaf outline in (u, z): u from the hinge (0) to the free edge (w), the top following the arch
        outline = [(0.0, zs + 0.02), (w, zs + 0.02)]
        for k in range(7):
            u = w - w * k / 6
            x = -(rr - u)                                 # x of the closed leaf relative to the mouth centre
            outline.append((u, zsp + math.sqrt(max(rr * rr - x * x, 0.0))))
        ang = -DOOR_OPEN if s < 0 else DOOR_OPEN
        X = _rotz((-s, 0.0, 0.0), ang)                   # leaf direction from the hinge (closed: toward the centre)
        X = (X[0], X[1], 0.0)
        Y = _rotz((0.0, 1.0, 0.0), ang)
        F = Frame(hinge, X, (Y[0], Y[1], 0.0), (0.0, 0.0, 1.0))
        g.add(*prism_fr(F, outline, -DOOR_T, 0.0, mats=0))
        for zz in (zs + 0.30, zs + 0.95, zsp + 0.35):
            umin = 0.05
            if zz + 0.08 > zsp:                           # over the spring the leaf narrows toward the hinge
                umin = rr - math.sqrt(max(rr * rr - (zz + 0.08 - zsp) ** 2, 0.0)) + 0.03
            for yy in (-DOOR_T - 0.025, 0.0):
                g.add(*box_fr(F, umin, w - 0.04, yy, yy + 0.025, zz - 0.05, zz + 0.05, mats=0))
        g.add(*tube([F.p(-0.05, -DOOR_T / 2, zs + 0.1), F.p(-0.05, -DOOR_T / 2, zsp - 0.05)], 0.045, sides=6,
                    mats=0))
    # a poker (left) and tongs (right) leaning on the face near its corners, outside the doors' swing
    rnd = random.Random(seed)
    W = fz["W"]
    s = -1.0
    xb = s * (W / 2 - 0.12)
    top = (xb, -0.05, zs + 1.45 + rnd.uniform(-0.1, 0.1))
    foot = (xb + s * 0.28, -0.62, 0.0)
    g.add(*tube([foot, top], 0.03, sides=5, mats=0))
    g.add(*tube([foot, (foot[0] + 0.02, foot[1] - 0.14, 0.12)], 0.028, sides=5, mats=0))
    s = 1.0
    xb = s * (W / 2 - 0.16)
    t0, t1 = (xb + s * 0.30, -0.60, 0.0), (xb, -0.04, zs + 1.15)
    g.add(*tube([t0, t1], 0.024, sides=4, mats=0))
    g.add(*tube([(t0[0] - 0.12, t0[1] - 0.06, t0[2]), (t1[0] + 0.06, t1[1] - 0.06, t1[2])], 0.024, sides=4, mats=0))
    if fz["mask"]:
        g.extend(beast_mask(fz))
    return g


def beast_mask(fz):
    """Bronze pushou mask with a hanging ring, above the keystone (slot 1)."""
    g = Geo()
    _r, _zsp, zcr = _mouth(fz)
    ring, proud, _j, kx, kp = VOUSSOIR
    zc = zcr + ring + kx + 0.26
    F = Frame((0.0, -(proud + kp) - 0.02, zc), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0))
    face = [(0.30 * math.cos(a), 0.24 * math.sin(a)) for a in (TAU * k / 10 + math.pi / 10 for k in range(10))]
    g.add(*prism_fr(Frame(F.o, F.X, F.Y, F.Z), face, -0.10, 0.06, mats=1))
    for s in (-1.0, 1.0):
        a, b = sorted((s * 0.04, s * 0.24))
        g.add(*box_fr(F, a, b, 0.04, 0.11, 0.06, 0.13, mats=1))                             # brows
        g.add(*tube([F.p(s * 0.12, 0.08, 0.02), F.p(s * 0.12, 0.13, 0.02)], [0.055, 0.03], sides=6, mats=1))  # eyes
        g.add(*tube([F.p(s * 0.22, 0.04, 0.16), F.p(s * 0.34, 0.06, 0.30), F.p(s * 0.26, 0.06, 0.40)],
                    [0.04, 0.03, 0.012], sides=5, mats=1))                                # horns
    g.add(*box_fr(F, -0.06, 0.06, 0.04, 0.14, -0.12, 0.0, mats=1))                       # nose
    # the ring through the mouth
    n = 14
    pts = [F.p(0.20 * math.sin(TAU * k / n), 0.10, -0.30 - 0.20 * math.cos(TAU * k / n)) for k in range(n)]
    rings = []
    for k in range(n):
        c = pts[k]
        t = _norm(_sub(pts[(k + 1) % n], pts[k - 1]))
        u = _norm(_sub(c, F.p(0.0, 0.10, -0.30)))
        w = _cross(t, u)
        rings.append([_add(c, _add(_mul(u, 0.03 * math.cos(TAU * j / 5)), _mul(w, 0.03 * math.sin(TAU * j / 5))))
                      for j in range(5)])
    verts = [p for rr in rings for p in rr]
    faces = []
    for k in range(n):
        k2 = (k + 1) % n
        for j in range(5):
            j2 = (j + 1) % 5
            faces.append((k * 5 + j, k * 5 + j2, k2 * 5 + j2, k2 * 5 + j))
    g.add(verts, faces, 1)
    return g


def furnace_top(fz):
    """The bronze hood on the cornice and the iron flue pipe with its bands; the side furnaces' pipes elbow back into
    the hall's wall (slots: 0 bronze, 1 iron)."""
    g = Geo()
    H, Dp = fz["H"], fz["D"]
    bw, bd, tw, td, hh = fz["hood"]
    yc = Dp / 2 + 0.25
    z0, z1 = H - 0.02, H + hh
    g.add(*hexa([(-bw / 2, yc - bd / 2, z0), (bw / 2, yc - bd / 2, z0), (bw / 2, yc + bd / 2, z0),
                 (-bw / 2, yc + bd / 2, z0), (-tw / 2, yc - td / 2, z1), (tw / 2, yc - td / 2, z1),
                 (tw / 2, yc + td / 2, z1), (-tw / 2, yc + td / 2, z1)], 0))
    g.add(*hexa([(-bw / 2 - 0.05, yc - bd / 2 - 0.05, z0), (bw / 2 + 0.05, yc - bd / 2 - 0.05, z0),
                 (bw / 2 + 0.05, yc + bd / 2 + 0.05, z0), (-bw / 2 - 0.05, yc + bd / 2 + 0.05, z0),
                 (-bw / 2 - 0.03, yc - bd / 2 - 0.03, z0 + 0.14), (bw / 2 + 0.03, yc - bd / 2 - 0.03, z0 + 0.14),
                 (bw / 2 + 0.03, yc + bd / 2 + 0.03, z0 + 0.14), (-bw / 2 - 0.03, yc + bd / 2 + 0.03, z0 + 0.14)], 0))
    pr, ztop = fz["pipe"]
    if not fz["elbow"]:
        path = [(0.0, yc, z1 - 0.1), (0.0, yc, ztop)]
        g.add(*tube(path, pr, sides=10, mats=1))
        for zz in (z1 + 0.5, z1 + 2.2, ztop - 1.2):
            if zz < ztop - 0.3:
                g.add(*tube([(0.0, yc, zz - 0.07), (0.0, yc, zz + 0.07)], pr + 0.04, sides=10, mats=1))
    else:
        zb = ztop - 0.6
        path = [(0.0, yc, z1 - 0.1), (0.0, yc, zb - 0.3), (0.0, yc + 0.18, zb), (0.0, yc + 0.6, zb + 0.15),
                (0.0, Dp + 0.35, zb + 0.15)]
        g.add(*tube(path, pr, sides=10, mats=1))
        g.add(*tube([(0.0, yc, z1 + 0.30), (0.0, yc, z1 + 0.44)], pr + 0.04, sides=10, mats=1))
    return g


def furnace_ash(fz, seed):
    """Ash spilling out of the ash pit over the plinth onto the floor (an open sheet, slot 0 forge_ash)."""
    g = Geo()
    ar, _a, _c = _ash(fz)
    pr, ph, _pc = PLINTH
    wx = ar + 0.32
    xs = [-wx + 2 * wx * i / 6 for i in range(7)]
    ys = [-0.85, -0.6, -0.38, -pr - 0.10, -pr + 0.07, 0.12, 0.30]
    rnd = random.Random(seed)
    jit = {(i, j): rnd.uniform(-0.03, 0.03) for i in range(7) for j in range(7)}

    def h(x, y):
        fx = max(0.0, 1.0 - (x / wx) ** 2)
        if y >= -pr:
            base, bump = ph + 0.03, 0.05 * fx
        else:
            base = 0.02
            t = (y - ys[0]) / (-pr - ys[0])
            bump = (0.03 + 0.20 * t * t) * fx
        return base + bump
    verts = []
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            verts.append((x, y, h(x, y) + (jit[(i, j)] if 0 < i < 6 and 0 < j < 6 else 0.0)))
    nx = len(xs)
    faces = []
    for j in range(len(ys) - 1):
        for i in range(nx - 1):
            faces.append((j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i))
    g.add(verts, faces, 0, kind="sheet")
    return g


def furnace_anchor_local(fz):
    """(foot of the flame in the furnace frame, size (w, h, d), mouth (centre, w, h) in the furnace frame, opening
    (bottom centre, w, h, depth) in the furnace frame). The opening is where the page draws its fire box
    (forge-flames.ts OpeningFire: a quad FLAMES.mouthLift = 2.5 cm in front of it that traces a box `depth` deep behind
    it): just inside the firebox, behind the stone mouth passage, so the arch's soffit hides the quad's corners and
    the traced box matches the real firebox (2r wide, up to the crown, fd deep)."""
    r, zsp, zcr = _mouth(fz)
    tF, fd, zs = fz["tF"], fz["fd"], fz["zs"]
    loc = (0.0, tF + fd * 0.5, zs + 0.15)
    size = (round(2 * r * 0.85, 3), round((zcr - zs) * 0.85, 3), round(fd * 0.8, 3))
    mouth = ((0.0, 0.0, (zs + zcr) / 2), 2 * r, zcr - zs)
    opening = ((0.0, tF + OPENING_INSET, zs), 2 * r, zcr - zs, fd - OPENING_INSET + PAGE_MOUTH_LIFT)
    return loc, size, mouth, opening


def bellows(seed=0):
    """A box bellows (feng xiang): wooden box on stubby legs, iron corner bands, the push-pull rod and T grip out of
    the front, air pipes out of both sides near the back (slots: 0 wood_dark, 1 iron). Frame: origin on the floor at
    the box's centre, +y the back (toward the wall)."""
    g = Geo()
    bx, by, bz = BELLOWS_SIZE
    z0 = 0.12
    g.add(*box((0.0, 0.0, z0 + bz / 2), (bx, by, bz), 0))
    for sx in (-1, 1):
        for sy in (-1, 1):
            g.add(*box((sx * (bx / 2 - 0.07), sy * (by / 2 - 0.07), z0 / 2 + 0.005), (0.10, 0.10, z0 + 0.01), 0))
    for yy in (-by / 2 + 0.18, by / 2 - 0.18):
        sec = [(-0.02, z0 - 0.0), (0.025, z0), (0.025, z0 + bz), (-0.02, z0 + bz)]
        g.add(*sweep_rect([(d, z) for d, z in sec], bx / 2, 0.05, 0.0, yy, mats=1))
    zr = z0 + bz * 0.55
    g.add(*tube([(0.0, -by / 2 + 0.05, zr), (0.0, -by / 2 - 0.62, zr)], 0.035, sides=6, mats=0))
    g.add(*tube([(-0.30, -by / 2 - 0.62, zr), (0.30, -by / 2 - 0.62, zr)], 0.04, sides=6, mats=0))
    return g


def bellows_pipes(cx, cy, targets):
    """Air pipes from the bellows at forge-local (cx, cy) to furnace side faces: targets [(x face, y)] forge-local;
    built in forge-local coordinates on the hall floor (z FLOOR_Z) (slot 1 iron)."""
    g = Geo()
    bx, by, bz = BELLOWS_SIZE
    z = FLOOR_Z + 0.12 + bz * 0.35
    for xf, yf in targets:
        s = 1.0 if xf > cx else -1.0
        p0 = (cx + s * (bx / 2 - 0.05), cy + by / 2 - 0.35, z)
        p1 = (cx + s * (bx / 2 + 0.25), cy + by / 2 - 0.35, z)
        p2 = (xf - s * 0.30, yf, FLOOR_Z + 0.58)
        p3 = (xf + s * 0.10, yf, FLOOR_Z + 0.58)
        g.add(*tube([p0, p1, p2, p3], 0.075, sides=8, mats=1))
        g.add(*tube([(xf - s * 0.12, yf, FLOOR_Z + 0.58), (xf - s * 0.02, yf, FLOOR_Z + 0.58)], 0.11, sides=8,
                    mats=1))
    return g


def tool_rack(side, seed=0):
    """Wall rack against a side wall: two posts, two rails, tongs, hammers and a poker hanging (slots: 0 wood_dark,
    1 iron). Frame: origin on the floor at the rack's centre, +x toward the wall for side +1 (mirrored for -1)."""
    g = Geo()
    rnd = random.Random(seed)
    L = 2.0
    for yy in (-L / 2, L / 2):
        g.add(*box((0.12 * side, yy, 1.05), (0.10, 0.10, 2.1), 0))
    for zz in (0.95, 1.95):
        g.add(*box((0.04 * side, 0.0, zz), (0.08, L + 0.24, 0.08), 0))
    for k in range(5):
        y = -L / 2 + 0.25 + k * (L - 0.5) / 4
        kind = k % 3
        top = (0.0, y, 1.92)
        if kind == 0:      # tongs
            g.add(*tube([top, (-0.02 * side, y - 0.07, 0.95)], 0.022, sides=4, mats=1))
            g.add(*tube([(top[0] - 0.06 * side, top[1], top[2] - 0.04), (-0.08 * side, y + 0.07, 0.95)], 0.022,
                        sides=4, mats=1))
        elif kind == 1:    # hammer
            g.add(*tube([top, (-0.03 * side, y, 1.30)], 0.03, sides=5, mats=0))
            g.add(*box((-0.03 * side, y, 1.26), (0.10, 0.24, 0.10), 1))
        else:              # poker
            g.add(*tube([top, (-0.02 * side, y + rnd.uniform(-0.05, 0.05), 0.35)], 0.024, sides=4, mats=1))
    return g


def coal_heap(seed=0):
    """A heap of coal on the floor (slot 0 forge_coal). Frame: origin on the floor at its centre."""
    g = Geo()
    rnd = random.Random(seed)
    placed = []
    tries = 0
    while len(placed) < 26 and tries < 600:
        tries += 1
        a = rnd.uniform(0, TAU)
        rr = 0.55 * math.sqrt(rnd.random())
        x, y = rr * math.cos(a), 0.75 * rr * math.sin(a)
        hz = 0.36 * (1.0 - (rr / 0.6) ** 2)
        s = rnd.uniform(0.09, 0.16)
        c = (x, y, max(hz, s * 0.5))
        if any(math.dist(c, q) < 0.8 * (s + r) for q, r in placed):
            continue
        placed.append((c, s))
        g.add(*icosa(c, s, rnd, squash=(1.0, 1.0, 0.75), mats=0))
    return g


def furnace_geos(fz, seed=0):
    return dict(body=furnace_body(fz), bed=furnace_bed(fz, seed), iron=furnace_iron(fz, seed), top=furnace_top(fz),
                ash=furnace_ash(fz, seed))


def flue_u(x_chim):
    """Where the forge.py flue's axis crosses the tower's front face, as u along it (face 0's u runs along +x)."""
    sx = 1.0 if x_chim > 0 else -1.0
    ax, ay = sx * 7.5, HALL_Y + 1.6 + 1.6
    bx_, by_ = sx * 10.0, CHIMNEY_Y - 3.4
    yface = CHIMNEY_Y - BASE[2]
    t = (yface - ay) / (by_ - ay)
    return ax + (bx_ - ax) * t - x_chim


def offline_report():
    """Triangle counts, bounds and open edges of every piece (pure python; no Blender)."""
    out = {}
    for i, x, emb in CHIMNEYS:
        gs = chimney_geos(emb, flue_u(x), seed=17 + i)
        out["chimney.%d" % i] = {k: (g.tris(), g.bounds(), g.open_edges()) for k, g in gs.items()}
    for fz in FURNACES:
        gs = furnace_geos(fz, seed=29 + fz["i"])
        out["furnace.%d" % fz["i"]] = {k: (g.tris(), g.bounds(), g.open_edges()) for k, g in gs.items()}
    out["bellows"] = bellows().tris()
    out["rack"] = tool_rack(1).tris()
    out["coal"] = coal_heap().tris()
    return out


# ------------------------------------------------------------------ Blender side

def _ashlar(g, c1="#3b3834", c2="#45413c", c3="#504b44", mortar="#25221f", block=(1.1, 0.55), joint=0.022,
            soot=(13.0, 24.5), soot_col="#181614", rough=(0.55, 0.85), streaks=True, wrap=True):
    """Coursed blocks in object space: rows by z, blocks along x + y (so the bond wraps the corners), a per-block
    tone, mottling, dark joints, soot rising toward the top (object z soot[0] -> soot[1]) with vertical streaks."""
    v = g.coord("object")
    x, y, z = g.sep(v)
    u = g.add(x, y) if wrap else x
    uv = g.comb(u, z, 0.0)
    b = g.node("ShaderNodeTexBrick", {"Vector": uv, "Color1": (0, 0, 0, 1), "Color2": (1, 1, 1, 1),
                                      "Mortar": (0, 0, 0, 1), "Scale": 1.0, "Mortar Size": joint,
                                      "Mortar Smooth": 0.25, "Bias": 0.0, "Brick Width": block[0],
                                      "Row Height": block[1]}, offset=0.5, offset_frequency=2)
    per = g.sep(b.outputs["Color"])[0]
    mortar_m = b.outputs[1]
    col = g.ramp(per, [(0.0, c1), (0.5, c2), (1.0, c3)])
    n1 = g.noise(v, 1.1, detail=5.0, roughness=0.6)
    n2 = g.noise(v, 6.5, detail=3.0)
    col = g.mix(col, g.hsv(col, 0.5, 1.0, 0.8), g.mul(g.smooth(n1, 0.45, 0.75), 0.55))
    if soot:
        s = g.smooth(z, soot[0], soot[1])
        if streaks:
            st = g.noise(g.comb(g.mul(u, 2.4), g.mul(z, 0.08), 0.0), 1.0, detail=2.0)
            s = g.mul(s, g.maprange(st, 0.35, 0.7, 0.55, 1.0))
        col = g.mix(col, soot_col, g.mul(s, 0.85))
    col = g.mix(col, mortar, g.smooth(mortar_m, 0.5, 0.95))
    col = g.tint_per_object(col, hue=0.004, sat=0.05, val=0.04)
    r = g.mixf(g.maprange(n2, 0.3, 0.7, rough[0], rough[1]), 0.95, mortar_m)
    nrm = g.bump(mortar_m, 0.45, 0.01, invert=True)
    nrm = g.bump(n2, 0.12, 0.004, nrm)
    g.viewport(c2, rough[1])
    g.output(g.principled(base_color=col, roughness=r, normal=nrm))


def _ember_wall(g, dark="#1e120c", colour="#ff4a06", hot="#ff9a2c", strength=7.0, power=2.6, brick=(0.30, 0.12)):
    """Fire-brick lining of a firebox: courses of small bricks glowing orange near the bed (generated z = 0), each
    brick a little brighter or duller, the joints darker, fading to nothing under the ceiling (z = 1); strength x
    obj['glow']."""
    z = g.sep(g.coord("generated"))[2]
    f = g.math('POWER', g.math('SUBTRACT', 1.0, z), power)
    v = g.coord("object")
    x, y, zo = g.sep(v)
    b = g.node("ShaderNodeTexBrick", {"Vector": g.comb(g.add(x, y), zo, 0.0), "Color1": (0, 0, 0, 1),
                                      "Color2": (1, 1, 1, 1), "Mortar": (0, 0, 0, 1), "Scale": 1.0,
                                      "Mortar Size": 0.012, "Mortar Smooth": 0.3, "Bias": 0.0, "Brick Width": brick[0],
                                      "Row Height": brick[1]}, offset=0.5, offset_frequency=2)
    per = g.sep(b.outputs["Color"])[0]
    joint = g.math('SUBTRACT', 1.0, g.mul(g.smooth(b.outputs[1], 0.3, 0.9), 0.8))
    n = g.noise(v, 3.0, detail=3.0)
    col = g.mix(colour, hot, g.mul(f, f))
    k = g.obj_prop("glow", 1.0)
    var = g.mul(g.maprange(per, 0.0, 1.0, 0.55, 1.15), g.maprange(n, 0.3, 0.7, 0.8, 1.15))
    em = g.mul(g.mul(g.mul(g.mul(f, var), joint), strength), k)
    g.viewport(colour, 0.6)
    g.output(g.principled(base_color=dark, roughness=0.8, emission_color=col, emission_strength=em))


def register_materials():
    """Register (and rebuild in place, so a re-run applies changed parameters) this module's materials."""
    from sect.lib import materials as M

    def variant(name, src, **params):          # (not 'base': _metal has a parameter called base)
        builder, p = M._REGISTRY[src]
        merged = dict(p)
        merged.update(params)
        M.register(name, builder, overwrite=True, **merged)
    M.register(M_ASHLAR, _ashlar, overwrite=True)
    M.register(M_BRICK, _ashlar, overwrite=True, c1="#4e281d", c2="#5c3123", c3="#6c3b2a", mortar="#241b17",
               block=(0.48, 0.22), joint=0.012, soot=(1.9, 4.4), soot_col="#1e1714", rough=(0.6, 0.9), streaks=True)
    M.register(M_EMBER, _ember_wall, overwrite=True)
    variant(M_DRESS, "stone_grey", c1="#7a756b", c2="#635f57", speck="#3a3833", light="#948e83", light_amt=0.25)
    variant(M_COAL, "stone_dark", c1="#23211e", c2="#141312", speck="#4a443c", rough=(0.3, 0.55), bump=0.3,
            light="#3a3632", light_amt=0.3)
    variant(M_IRONB, "iron", base="#2e2c2a", dark="#1b1918", rough=(0.55, 0.8), tarnish=0.5, edge_col="#5e5a55")
    variant(M_ASH, "stone_grey", c1="#5e5a54", c2="#46423d", speck="#2a2826", rough=(0.9, 0.98), bump=0.3,
            light="#7c776f", light_amt=0.35)


def _obj(name, geo, coll, mats, parent, location=(0.0, 0.0, 0.0), glow=None, shadow=True):
    from sect.lib import util as U
    import bpy
    if bpy.data.objects.get(name) is not None or bpy.data.meshes.get(name) is not None:
        raise RuntimeError("forge_detail: %s already exists" % name)
    ob = U.mesh_from_bmesh(name, geo.to_bmesh(), coll, materials=mats, smooth=False, parent=parent,
                           location=location)
    if glow is not None:
        ob["glow"] = float(glow)
    if not shadow:
        U.set_visibility(ob, shadow=False)
    ob[TAG] = 1
    ob.data[TAG] = 1
    return ob


def _n(*parts):
    return ".".join([KEY] + [str(p) for p in parts])


def fire_anchor(coll, root, name, kind, location, size, mouth=None, open_sides=0, rotation_z=0.0, opening=None):
    """Flame anchor Empty: the foot of the flame at ``location`` (forge-local), its local -Y the way the fire faces
    (out of a furnace's mouth); custom props for export_web's meta.fires[]. ``opening`` (furnaces): (bottom centre in
    the anchor's local frame, width, height, depth) of the plane the page draws its fire box on."""
    from sect.lib import util as U
    import bpy
    if bpy.data.objects.get(name) is not None:
        raise RuntimeError("forge_detail: %s already exists" % name)
    ob = U.empty(name, coll, location=location, parent=root, display_size=max(size) * 0.5,
                 display_type='CUBE' if kind != "cauldron" else 'CIRCLE', rotation=(0.0, 0.0, rotation_z))
    ob[FIRE_TAG] = kind
    ob["fire_size"] = [float(v) for v in size]                 # (w, h, d): x across, z up, y depth (local)
    if mouth is not None:
        c, w, h = mouth
        ob["fire_mouth"] = [float(w), float(h)]                # width, height of the opening
        ob["fire_mouth_at"] = [float(v) for v in c]            # its centre, in the anchor's local frame
    if opening is not None:
        c, w, h, d = opening
        ob["fire_opening"] = [float(w), float(h), float(d)]    # the page's fire box: width, height, depth
        ob["fire_opening_at"] = [float(v) for v in c]          # its plane's bottom centre, in the anchor's local frame
    ob["fire_open_sides"] = int(open_sides)
    ob[TAG] = 1
    return ob


def build_chimney(coll, root, i, x, y, emblem):
    """One tower at forge-local (x, y): masonry, bronze, fire storey, fire tray, roof and the flame anchor. Returns
    the new top-level objects (the roof's Empty stands for its children)."""
    from sect.lib import arch as A
    register_materials()
    gs = chimney_geos(emblem, flue_u(x), seed=17 + i)
    loc = (x, y, 0.0)
    obs = [
        _obj(_n("chimney", i), gs["masonry"], coll, [M_ASHLAR, M_DRESS], root, loc),
        _obj(_n("chimney_bronze", i), gs["bronze"], coll, [M_BRONZE, M_GOLD if emblem == "sun" else M_SILVER],
             root, loc),
        _obj(_n("chimney_lantern", i), gs["lantern"], coll, [M_ASHLAR, M_DRESS, M_EMBER, M_RED], root, loc,
             glow=LANTERN_GLOW),
        _obj(_n("chimney_fire", i), gs["fire"], coll, [M_IRONB, M_MOLTEN, M_COAL], root, loc, glow=FIRE_GLOW),
    ]
    roof = A.roof(_n("chimney_roof", i), coll, 2 * HL, kind="pyramid", sides=4, rise=ROOF["rise"],
                  overhang=ROOF["overhang"], tile_mat=ROOF_TILE, detail="low", parent=root, location=(x, y, ZB))
    roof[TAG] = 1
    for c in roof.children_recursive:
        c[TAG] = 1
        if c.data is not None:
            c.data[TAG] = 1
    obs.append(roof)
    lo, size = chimney_fire_anchor_local()
    obs.append(fire_anchor(coll, root, _n("fire", "chimney", i), "chimney", (x + lo[0], y + lo[1], lo[2]), size,
                           open_sides=len(OPEN_FACES)))
    return obs


def build_furnaces(coll, root, z0=FLOOR_Z):
    """The three furnaces, their beds, irons, hoods, ash, the bellows, racks, the coal heap and the three flame
    anchors. Returns the new objects."""
    register_materials()
    obs = []
    for fz in FURNACES:
        k = fz["i"]
        gs = furnace_geos(fz, seed=29 + k)
        loc = (fz["x"], FURNACE_FRONT_Y, z0)
        obs += [
            _obj(_n("furnace", k), gs["body"], coll, [M_BRICK, M_DRESS, M_EMBER], root, loc, glow=BODY_GLOW),
            _obj(_n("furnace_mouth", k), gs["bed"], coll, [M_MOLTEN, M_COAL], root, loc, glow=BED_GLOW),
            _obj(_n("furnace_iron", k), gs["iron"], coll, [M_IRONB, M_BRONZE], root, loc),
            _obj(_n("furnace_top", k), gs["top"], coll, [M_BRONZE, M_IRONB], root, loc),
            _obj(_n("furnace_ash", k), gs["ash"], coll, [M_ASH], root, loc),
        ]
        lo, size, (mc, mw, mh), (oc, ow, oh, od) = furnace_anchor_local(fz)
        at = (loc[0] + lo[0], loc[1] + lo[1], loc[2] + lo[2])
        mouth_rel = (mc[0] - lo[0], mc[1] - lo[1], mc[2] - lo[2])
        open_rel = (oc[0] - lo[0], oc[1] - lo[1], oc[2] - lo[2])
        obs.append(fire_anchor(coll, root, _n("fire", "furnace", k), "furnace", at, size, (mouth_rel, mw, mh),
                               open_sides=1, opening=(open_rel, ow, oh, od)))
    side = {fz["i"]: fz for fz in FURNACES}
    for j, (cx, cy) in enumerate(BELLOWS):
        s = 1.0 if cx > 0 else -1.0
        g = bellows(seed=j)
        obs.append(_obj(_n("furnace_bellows", j), g, coll, [M_WOOD, M_IRONB], root, (cx, cy, z0)))
        sf = side[2 if s > 0 else 1]
        tg = [(sf["x"] - s * sf["W"] / 2, cy + 0.6), (s * side[0]["W"] / 2, cy + 0.6)]
        obs.append(_obj(_n("furnace_pipes", j), bellows_pipes(cx, cy, tg), coll, [M_WOOD, M_IRONB], root))
    for j, (cx, cy) in enumerate(RACKS):
        s = 1.0 if cx > 0 else -1.0
        obs.append(_obj(_n("furnace_rack", j), tool_rack(s, seed=j), coll, [M_WOOD, M_IRONB], root, (cx, cy, z0)))
    obs.append(_obj(_n("furnace_coal"), coal_heap(seed=5), coll, [M_COAL], root, (COAL_HEAP[0], COAL_HEAP[1], z0)))
    return obs


def ding_molten_points(ding):
    """World-space bounding-box corners of the cauldron's molten surface: the instanced collection's objects whose
    name has 'molten', through the instance's matrix (and the collection's offset)."""
    from mathutils import Vector
    coll = ding.instance_collection
    if coll is None:
        return []
    off = Vector(coll.instance_offset)
    pts = []
    for o in coll.all_objects:
        if "molten" not in o.name or o.type != 'MESH':
            continue
        for c in o.bound_box:
            pts.append(ding.matrix_world @ (o.matrix_world @ Vector(c) - off))
    return pts


def build_ding_anchor(coll, root, ding):
    """The cauldron's flame anchor on its molten surface (forge-local; measured in the forge's frame), or None. The
    flame is as wide as the surface and DING_FLAME x its radius tall: what the page draws without anchors (forge-flames
    reads the round-19 bake's molten disc, radius 2.83 m, flames 3.5 m), so its tuned look does not change. Needed:
    once meta.fires has entries for the forge the page draws only those, so without this anchor the cauldron would
    lose its flames."""
    pts = ding_molten_points(ding)
    if not pts:
        return None
    Minv = root.matrix_world.inverted()
    L = [Minv @ p for p in pts]
    lo = [min(p[k] for p in L) for k in range(3)]
    hi = [max(p[k] for p in L) for k in range(3)]
    w = max(hi[0] - lo[0], hi[1] - lo[1])
    loc = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, hi[2])
    return fire_anchor(coll, root, _n("fire", "ding"), "cauldron", loc,
                       (round(w, 3), round(DING_FLAME * w / 2, 3), round(w, 3)), open_sides=0)
