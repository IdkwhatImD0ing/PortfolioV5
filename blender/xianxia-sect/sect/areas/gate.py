"""Mountain Gate (山门) - site section 'hero', the opening of the fly-through.

Blocking pass (spec section 0): a colossal five-bay paifang with the 明教 plaque on a white
marble plaza at the cliff edge, guardian lions and two colossal legendary weapons (the Heaven
Sword 倚天剑 and the Dragon Saber 屠龙刀, blade-down in carved plinths) flanking the top
of a steep white marble stairway that dives about 56 m down the mountainside into the cloud
sea, with a landing every 24 steps (a stone lantern pair on each, tall banner pairs on landings
1 and 3) and a paved forecourt joining the stair top to the plaza. Behind the plaza's back
opening a 12 x 12 m railed landing on the axis (y 24 to 36) is where the stair to the
Heart-Mirror Terrace starts (AREA['depart']); AREA['arrival'] is the grand stair's foot.
The sect's sun-and-moon emblem (明 = 日 + 月) marks the paifang: a gilt finial on the top ridge and a sun and a moon
medallion either side of the plaque (_sun_moon); every banner here carries it as its roundel (props.banner default).

Local frame: origin = plaza centre, z = 0 walkable, front (stairs, arriving camera) faces -Y.
The stairway leaves the footprint toward -Y (allowed by the brief) and ends near y = -131,
z = -56. The camera rises out of the clouds up the stair axis (x = 0) and flies through the
centre bay (clear opening about 12.1 m wide x 15.4 m tall) about 9 m above the plaza.
"""

import math
import os

import bmesh
import bpy

from sect.lib import util as U
from sect.lib import arch as A
from sect.lib import props as P

AREA = dict(key="gate", section_id="hero", title_en="Mountain Gate", title_zh="明教",
            footprint=40.0)

K = AREA["key"]

# ---- layout (local metres) ---------------------------------------------------------------
GATE_Y = -12.0                 # paifang centre line
GATE_W, GATE_H = 34.0, 24.0
PLAZA_X = 20.0                 # plaza half width
PLAZA_Y0, PLAZA_Y1 = -34.0, 24.0   # plaza front / back edge
HEAD_X = 10.0                  # stair-head forecourt half width (bridges the terrace rim)
# stair top. world.py's flat terrace (radius footprint + TERRACE_PAD 9 m, plus bulges) reaches
# about 50.5 m out here, past this line; world.py carves a notch in it for the stair (audit 1.1).
STAIR_Y0 = -46.0
STAIR_W = 14.0                 # flight width (incl. stringers)
STAIR_RUN = 0.22               # tread
STAIR_RISER = 0.18
STEPS_PER_FLIGHT = 24
FLIGHT_H = STEPS_PER_FLIGHT * STAIR_RISER          # 4.32 m per flight
FLIGHT_L = STEPS_PER_FLIGHT * STAIR_RUN            # 5.28 m run per flight
LANDING_L = 2.2
N_FLIGHTS = 12
SUB_W = 10.0                   # half width of the stair masonry body (landings, cheek strips)
STAIR_FOOT_Y = STAIR_Y0 - (N_FLIGHTS - 1) * (FLIGHT_L + LANDING_L) - FLIGHT_L   # -133.56
STAIR_FOOT_Z = -N_FLIGHTS * FLIGHT_H                                            # -51.84
DEPART_X, DEPART_Y1 = 6.0, 36.0    # axis landing behind the plaza (x +-6, y PLAZA_Y1 .. 36)

# Connector ends (audit W1), local (x, y, z, heading). heading = walking direction in radians,
# measured like world.py's yaw, atan2(dy, dx): +x = 0, +y = pi/2, -x = pi.
# arrival: the foot of the grand stair (no connector arrives; it stays hidden in the cloud bank).
# depart: the far edge of the axis landing behind the plaza, where the stair to the mirror starts
# flush at z 0 (audit 1.1 item 2).
AREA["arrival"] = (0.0, round(STAIR_FOOT_Y, 2), round(STAIR_FOOT_Z, 2), math.pi / 2)
AREA["depart"] = (0.0, DEPART_Y1, 0.0, math.pi / 2)

# Fly-through hints, LOCAL coordinates, ordered along the flight (spec section 5).
CAMERA_HINTS = [
    # just above the cloud-sea top (local z ~ -20): the stairway climbs out of the clouds
    # toward the gate silhouetted against the sky
    dict(name="rise", location=(0.0, -112.0, -15.0), target=(0.0, -14.0, 11.0), lens=28),
    # halfway up the visible stairs: lantern/banner landings slide under, gate looms
    dict(name="climb", location=(0.0, -66.0, -2.0), target=(0.0, -12.0, 12.0), lens=24),
    # over the stair top between the lions and sword monoliths, lined up on the centre bay
    dict(name="gate", location=(0.0, -31.0, 8.5), target=(0.0, 6.0, 10.0), lens=22),
    # just through the centre bay, 9 m above the plaza, heading on north and turning slightly
    # toward the next area (mirror lies ~27 deg west of north). Pins the path to the bay centre so
    # the stitched spline does not cut a corner through the side bays. In the area preview this
    # view is mostly sky; in the full scene it looks up the range.
    dict(name="through", location=(0.0, 2.0, 9.0), target=(-15.0, 60.0, 13.0), lens=24),
]


# ---- small mesh helpers -------------------------------------------------------------------

def _recalc(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return obj


def _grid_slab(name, coll, root, x0, x1, y0, y1, z0, z1, cell=3.0,
               top_mat="marble_paving", side_mat="marble_white"):
    """Box whose top is a grid of quads (paving bump breaks on long sliver triangles)."""
    nx = max(1, int(round((x1 - x0) / cell)))
    ny = max(1, int(round((y1 - y0) / cell)))
    verts, faces, mats = [], [], []

    def vid(layer, i, j):
        return layer * (nx + 1) * (ny + 1) + j * (nx + 1) + i

    for layer, z in ((0, z1), (1, z0)):
        for j in range(ny + 1):
            for i in range(nx + 1):
                verts.append((x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny, z))
    for j in range(ny):
        for i in range(nx):
            faces.append((vid(0, i, j), vid(0, i + 1, j), vid(0, i + 1, j + 1), vid(0, i, j + 1)))
            mats.append(0)
            faces.append((vid(1, i, j + 1), vid(1, i + 1, j + 1), vid(1, i + 1, j), vid(1, i, j)))
            mats.append(1)
    ring = ([(i, 0) for i in range(nx)] + [(nx, j) for j in range(ny)]
            + [(i, ny) for i in range(nx, 0, -1)] + [(0, j) for j in range(ny, 0, -1)])
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        faces.append((vid(0, *a), vid(1, *a), vid(1, *b), vid(0, *b)))
        mats.append(1)
    ob = U.mesh_from_pydata(U.name(K, name), verts, faces, coll, materials=[top_mat, side_mat],
                            material_indices=mats, parent=root)
    return _recalc(ob)


def _prism_yz(name, coll, root, profile, half_w, material):
    """Extrude a (y, z) polygon across x = -half_w .. +half_w."""
    m = len(profile)
    verts = [(-half_w, y, z) for y, z in profile] + [(half_w, y, z) for y, z in profile]
    faces = [tuple(range(m)), tuple(range(2 * m - 1, m - 1, -1))]
    for k in range(m):
        k2 = (k + 1) % m
        faces.append((k, k2, m + k2, m + k))
    ob = U.mesh_from_pydata(U.name(K, name), verts, faces, coll, materials=[material], parent=root)
    return _recalc(ob)


# ---- stairway geometry ---------------------------------------------------------------------

def _flight_top(k):
    """(y, z) of the top edge of flight k (k = 0 meets the plaza)."""
    return STAIR_Y0 - k * (FLIGHT_L + LANDING_L), -k * FLIGHT_H


def _stair_end():
    y, z = _flight_top(N_FLIGHTS - 1)
    return y - FLIGHT_L, z - FLIGHT_H


def _avg_z(y):
    """Straight line from the stair top to the stair foot (used for the body and the ridge)."""
    ye, ze = _stair_end()
    t = (y - STAIR_Y0) / (ye - STAIR_Y0)
    return max(t, 0.0) * ze


def _stairway(coll, root):
    # flights (arch.stairs: top edge at the origin, descending to -Y)
    # (flights k >= 1 run their balustrades across the landing above them, so every landing
    # has side rails; audit section 4)
    for k in range(N_FLIGHTS):
        yt, zt = _flight_top(k)
        A.stairs(U.name(K, "stair"), coll, STAIR_W, FLIGHT_H, run_per_step=STAIR_RUN,
                 max_riser=STAIR_RISER + 1e-4, ramp=True, balustrade=True, bal_height=1.0,
                 bal_extend=(LANDING_L if k else 0.0),
                 parent=root, location=(0.0, yt, zt - FLIGHT_H))

    # masonry body: top follows the nosing line 0.3 m low on flights, flat at landings
    top = [(PLAZA_Y0, -0.6), (STAIR_Y0, -0.6)]
    for k in range(N_FLIGHTS):
        yt, zt = _flight_top(k)
        yb, zb = yt - FLIGHT_L, zt - FLIGHT_H
        if k:
            top.append((yt, zt - 0.3))
        top.append((yb, zb - 0.3))
        top.append((yb, zb))
        y_next = yb - (LANDING_L if k < N_FLIGHTS - 1 else 4.0)
        top.append((y_next, zb))
    ye, ze = top[-1]
    depth = 7.0
    bottom = [(ye, _avg_z(ye) - depth), (PLAZA_Y0, -depth)]
    _prism_yz("stair_body", coll, root, top + bottom, SUB_W, "marble_white")

    # stone lantern pair on every landing (and on the foot platform)
    for k in range(N_FLIGHTS):
        yt, zt = _flight_top(k)
        yb, zb = yt - FLIGHT_L, zt - FLIGHT_H
        yl = yb - (LANDING_L if k < N_FLIGHTS - 1 else 4.0) * 0.5
        for s in (-1, 1):
            P.lantern_stone(coll, 3.2, name=U.name(K, "landing_lantern"), parent=root,
                            location=(s * 8.5, yl, zb))
        # tall banner pairs on landings 1 and 3 (above the cloud top, outside the climb view)
        if k in (1, 3):
            for s in (-1, 1):
                P.banner(coll, 12.0, 1.5, material=(3 if k == 1 else 0), seed=70 + k * 2 + (s > 0),
                         name=U.name(K, "landing_banner"), parent=root,
                         location=(s * 9.5, yl + 0.6, zb), rotation=(0, 0, 0.0 if s < 0 else math.pi))


def _ridge(coll, root):
    """Craggy rock spine under the stairway, so it reads as built down a mountainside (world.py's
    slope will partly bury it). Flat-shaded, rock_cliff."""
    section = [(-9, 0), (-4.5, 0.3), (0, 0.4), (4.5, 0.3), (9, 0), (13, -5), (17, -13), (18, -22),
               (13, -31), (6, -37), (0, -40), (-6, -37), (-13, -31), (-18, -22), (-17, -13), (-13, -5)]
    ye, _ = _stair_end()
    y_start, y_end = PLAZA_Y0 - 2.0, ye - 8.0
    n = 18
    verts, faces = [], []
    m = len(section)
    for i in range(n + 1):
        y = y_start + (y_end - y_start) * i / n
        ztop = _avg_z(y) - 6.0
        grow = 0.75 + 0.35 * i / n
        for j, (sx, sz) in enumerate(section):
            x, z = sx * grow, ztop + sz * grow
            if j > 4 and j < m:            # keep the top edge tucked under the stair body
                nv = U.noise_vec((x, y, z), scale=0.09, seed=17)
                x += nv.x * 3.0
                z += nv.z * 2.5
                yy = y + nv.y * 1.5
            else:
                yy = y
            verts.append((x, yy, z))
    for i in range(n):
        for j in range(m):
            a, b = i * m + j, i * m + (j + 1) % m
            faces.append((a, b, b + m, a + m))
    faces.append(tuple(range(m)))
    faces.append(tuple(n * m + j for j in range(m)))
    ob = U.mesh_from_pydata(U.name(K, "stair_ridge"), verts, faces, coll, materials=["rock_cliff"],
                            parent=root)
    _recalc(ob)
    U.shade_flat(ob)
    return ob


# ---- the gate weapons: Heaven Sword 倚天剑 and Dragon Saber 屠龙刀 ----------------------------
#
# The two monoliths flanking the stair top are the legendary pair of Jin Yong's 倚天屠龙记. Guo Jing and Huang Rong
# had them forged from Yang Guo's Black Iron Heavy Sword (玄铁重剑, black, with a dark red glint) and Western gold
# essence (西方精金): the Dragon Saber black, broad and over a hundred jin heavy (east, x +16: the dragon's side), the
# Heaven Sword a slender, keen straight jian (west, x -16). Each stands blade-down in a sumeru plinth (须弥座) with
# its name in raised gold (倚天 / 屠龙) on the front and, on the sides, its half of the jianghu saying
# 武林至尊，宝刀屠龙，号令天下，莫敢不从；倚天不出，谁与争锋 (columns read right to left). The site's cyan rune glow:
# the jian's ridge inlay, guard and pommel gems; the saber's groove (血槽), dragon eyes and the pearl in its ring.
#
# Web-pipeline contract (sect/patch_gate_swords.py rebuilds both in out/sect_chase.blend): the objects keep the
# names 'gate.sword_monolith' (sword) and 'gate.sword_monolith.001' (saber) and each mesh's local bound box is
# exactly x, y -2.7..2.7, z 0..15.6, as the old stone monolith's. export_web's visibility cache, chunk plan and the
# 'gate-swords' hotspot box key on those names and (rotated) boxes, so they stay valid without a new audit.
# The geometry is built as plain Python lists (_Geo, no bpy) so tests can check it without Blender; only the
# glyph outlines (props._text_mesh) and the final mesh (_geo_to_mesh) need Blender.

WEAPON_HALF = 2.7              # local bound box half width (x and y): the plinth's base slab
WEAPON_TOP = 15.6              # local bound box top: the pommel
WEAPON_X, WEAPON_Y = 16.0, -25.0
WEAPON_YAW = math.radians(12.0)
WEAPON_FACE_IN = True          # True: the fronts turn 12 deg toward the axis, to the arriving camera (the old monoliths
                               # turned 12 deg away from it); the world box is the same either way (square local box)
WEAPON_TRI_BUDGET = 15000      # per weapon including its plinth; over it the couplet drops to res 1, then goes
WEAPON_COUPLET = True          # the saying on the plinth sides
COUPLET_RES = 1                # its glyphs' curve resolution (0.2 m characters: res 1 reads, res 2 doubles them)
BLADE_NAME_BACK = False        # the blade's name on the back face too (+1.0-1.3k triangles; the path and the
                               # hold see the fronts, only a look-around from the plaza sees the backs)
WEAPON_SMOOTH = math.radians(35.0)   # edges sharper than this stay hard; ridge and hone lines are marked hard anyway
WEAPONS = (
    dict(key="heaven_sword", kind="jian", side=-1, object="gate.sword_monolith", name="倚天",
         couplet=(("倚天不出",), ("谁与争锋",)),          # (inner face, outer face) columns, right to left
         materials=dict(stone="stone_grey", panel="stone_dark", blade="steel", gold="gold", rune="rune_cyan",
                        wrap="cloth_teal", tassel="cloth_red")),
    dict(key="dragon_saber", kind="dao", side=1, object="gate.sword_monolith.001", name="屠龙",
         couplet=(("武林至尊", "宝刀屠龙"), ("号令天下", "莫敢不从")),
         materials=dict(stone="stone_grey", panel="stone_dark", blade="iron", gold="gold", rune="rune_cyan",
                        wrap="cloth_red", hone="steel")),
)
PLINTH_PROFILE = (             # (z, half width, chamfer) of the sumeru plinth, bottom to top: a regular octagon base
    (0.00, 2.70, 1.58), (0.30, 2.70, 1.58),   # slab (flats at +-2.7: the box) that steps into the chamfered-square
    (0.40, 2.58, 1.36), (0.50, 2.58, 1.36),   # waist, every row inside the one below (2w - c never grows); turned
    (0.62, 2.40, 1.00), (0.72, 2.30, 0.80),   # 12 deg, the base's corners stay 0.6 m off the plaza balustrade
    (0.72, 2.14, 0.50), (2.02, 2.14, 0.50),   # waist
    (2.02, 2.28, 0.62), (2.12, 2.40, 0.72), (2.26, 2.52, 0.80), (2.44, 2.52, 0.80), (2.56, 2.40, 0.74))   # cap
PLINTH_TOP = 2.56
DIE = (0.72, 2.02, 2.14)       # the plinth's waist (束腰): z0, z1, half width (flat faces +-1.64 wide); the
                               # inscription panels sit on it
PANEL_Z = (0.80, 1.96)         # panel frame (outer) z range; plate inside it
NAME_CELL = 0.92               # m per character of the name on the front panel
COUPLET_CELL = 0.235           # m per character of the saying on the side panels
J_Z0, J_ZTOP = 2.35, 11.25     # jian blade: buried tip end, top (inside the guard)
J_GUARD_Z = 11.50
D_Z0, D_ZTOP = 2.35, 11.40     # dao blade: buried point end, top (inside the disc guard)


def _lerp(a, b, t):
    return a + (b - a) * t


def _ss(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else (0.0, 0.0, 0.0)


def _newell(pts):
    """Unnormalised polygon normal (Newell's method; robust for concave planar polygons)."""
    nx = ny = nz = 0.0
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return (nx, ny, nz)


def _frame(right, up, normal, origin):
    """Point map p -> origin + p.x * right + p.y * up + p.z * normal."""
    def f(p):
        return (origin[0] + p[0] * right[0] + p[1] * up[0] + p[2] * normal[0],
                origin[1] + p[0] * right[1] + p[1] * up[1] + p[2] * normal[1],
                origin[2] + p[0] * right[2] + p[1] * up[2] + p[2] * normal[2])
    return f


class _Geo:
    """Mesh as plain Python lists: verts, faces (vertex index tuples) with a material role, an edge-wear value
    (the 'edge' face attribute metals read) and a smooth flag, explicit hard edges, and parts (closed solids get
    outward winding from their signed volume; one-sided pieces such as flat glyphs keep the winding given)."""

    def __init__(self):
        self.verts, self.faces, self.mat, self.edge, self.smooth = [], [], [], [], []
        self.sharp = set()
        self.parts = []                 # (name, first face, end face, closed)
        self.glyph_tris = 0
        self._cur = None

    def v(self, p):
        self.verts.append((float(p[0]), float(p[1]), float(p[2])))
        return len(self.verts) - 1

    def face(self, idx, mat, edge=0.0, smooth=True):
        self.faces.append(tuple(idx))
        self.mat.append(mat)
        self.edge.append(float(edge))
        self.smooth.append(bool(smooth))

    def hard(self, a, b):
        self.sharp.add((a, b) if a < b else (b, a))

    def begin(self, name, closed=True):
        self._cur = (name, len(self.faces), closed)

    def end(self):
        name, f0, closed = self._cur
        f1 = len(self.faces)
        if closed and self.volume(f0, f1) < 0.0:
            for i in range(f0, f1):
                self.faces[i] = tuple(reversed(self.faces[i]))
        self.parts.append((name, f0, f1, closed))
        self._cur = None

    def volume(self, f0, f1):
        vol = 0.0
        V = self.verts
        for f in self.faces[f0:f1]:
            a = V[f[0]]
            for k in range(1, len(f) - 1):
                vol += _dot(a, _cross(V[f[k]], V[f[k + 1]]))
        return vol / 6.0

    def tris(self):
        return sum(len(f) - 2 for f in self.faces)

    # ---- primitives (every one is a closed part unless noted)
    def loft(self, name, rings, mat, edge=0.0, smooth=True, caps=(True, True), cap_mat=None, hard_cols=(),
             hard_rows=()):
        """Quads between consecutive closed rings of equal length. mat / edge: value or f(row, col); row r joins
        ring r and r + 1, col c joins point c and c + 1. Caps are n-gons (cap_mat or the first/last row's mat)."""
        self.begin(name)
        ids = [[self.v(p) for p in ring] for ring in rings]
        n = len(rings[0])
        for r in range(len(ids) - 1):
            a, b = ids[r], ids[r + 1]
            for c in range(n):
                c2 = (c + 1) % n
                self.face((a[c], a[c2], b[c2], b[c]), mat(r, c) if callable(mat) else mat,
                          edge(r, c) if callable(edge) else edge, smooth)
        if caps[0]:
            self.face(tuple(reversed(ids[0])), cap_mat or (mat(0, 0) if callable(mat) else mat), 0.0, smooth)
        if caps[1]:
            last = len(ids) - 2
            self.face(tuple(ids[-1]), cap_mat or (mat(last, 0) if callable(mat) else mat), 0.0, smooth)
        for c in hard_cols:
            for r in range(len(ids) - 1):
                self.hard(ids[r][c], ids[r + 1][c])
        for r in hard_rows:
            for c in range(n):
                self.hard(ids[r][c], ids[r][(c + 1) % n])
        self.end()
        return ids

    def loft_loop(self, name, rings, mat, edge=0.0, smooth=True):
        """Quads between consecutive closed rings, the last joined back to the first: a closed tube (a ring) with
        no caps. mat / edge: value or f(row, col) as in loft."""
        self.begin(name)
        ids = [[self.v(p) for p in ring] for ring in rings]
        n, m = len(rings[0]), len(ids)
        for r in range(m):
            a, b = ids[r], ids[(r + 1) % m]
            for c in range(n):
                c2 = (c + 1) % n
                self.face((a[c], a[c2], b[c2], b[c]), mat(r, c) if callable(mat) else mat,
                          edge(r, c) if callable(edge) else edge, smooth)
        self.end()
        return ids

    def lathe(self, name, profile, segments, mat, center=(0.0, 0.0), xf=None, edge=0.0, phase=0.0, smooth=True):
        """Revolve rows (r, z[, sy]) around a z axis through ``center``; r = 0 at either end makes a pole.
        sy squashes a ring along y (oval grips). mat / edge: value or f(row). xf maps every point (orientation)."""
        self.begin(name)
        cx, cy = center
        rings = []
        for row in profile:
            r, z = row[0], row[1]
            sy = row[2] if len(row) > 2 else 1.0
            if r <= 1e-7:
                p = (cx, cy, z)
                rings.append([self.v(xf(p) if xf else p)])
                continue
            ring = []
            for k in range(segments):
                a = phase + 2.0 * math.pi * k / segments
                p = (cx + r * math.cos(a), cy + r * sy * math.sin(a), z)
                ring.append(self.v(xf(p) if xf else p))
            rings.append(ring)
        for i in range(len(rings) - 1):
            a, b = rings[i], rings[i + 1]
            m = mat(i) if callable(mat) else mat
            e = edge(i) if callable(edge) else edge
            for k in range(segments):
                k2 = (k + 1) % segments
                if len(a) == 1 and len(b) == 1:
                    continue
                if len(a) == 1:
                    self.face((a[0], b[k2], b[k]), m, e, smooth)
                elif len(b) == 1:
                    self.face((a[k], a[k2], b[0]), m, e, smooth)
                else:
                    self.face((a[k], a[k2], b[k2], b[k]), m, e, smooth)
        if len(rings[0]) > 1:
            self.face(tuple(reversed(rings[0])), mat(0) if callable(mat) else mat, 0.0, smooth)
        if len(rings[-1]) > 1:
            self.face(tuple(rings[-1]), mat(len(rings) - 2) if callable(mat) else mat, 0.0, smooth)
        self.end()
        return rings

    def sphere(self, name, c, r, mat, nu=8, nv=5, scale=(1.0, 1.0, 1.0)):
        prof = [(0.0, -1.0)] + [(math.sin(math.pi * k / nv), -math.cos(math.pi * k / nv)) for k in range(1, nv)] + \
            [(0.0, 1.0)]
        sx, sy, sz = scale

        def xf(p):
            return (c[0] + p[0] * r * sx, c[1] + p[1] * r * sy, c[2] + p[2] * r * sz)
        return self.lathe(name, prof, nu, mat, xf=xf)

    def tube(self, name, pts, sides, mat, edge=0.0):
        """Swept tube through (x, y, z, radius) points (parallel-transport frames). A last radius of 0 ends in a
        point; otherwise both ends are capped."""
        self.begin(name)
        P = [p[:3] for p in pts]
        n = len(P)
        tans = []
        for i in range(n):
            a, b = P[max(i - 1, 0)], P[min(i + 1, n - 1)]
            tans.append(_norm(_sub(b, a)))
        ref = (0.0, 0.0, 1.0) if abs(tans[0][2]) < 0.9 else (1.0, 0.0, 0.0)
        u = _norm(_cross(tans[0], ref))
        rings = []
        for i in range(n):
            t = tans[i]
            u = _norm(_sub(u, tuple(t[k] * _dot(u, t) for k in range(3))))
            w = _cross(t, u)
            r = pts[i][3]
            if r <= 1e-6:
                rings.append([self.v(P[i])])
                continue
            ring = []
            for k in range(sides):
                a = 2.0 * math.pi * k / sides
                ca, sa = math.cos(a) * r, math.sin(a) * r
                ring.append(self.v(tuple(P[i][j] + u[j] * ca + w[j] * sa for j in range(3))))
            rings.append(ring)
        for i in range(n - 1):
            a, b = rings[i], rings[i + 1]
            for k in range(sides):
                k2 = (k + 1) % sides
                if len(b) == 1:
                    self.face((a[k], a[k2], b[0]), mat, edge)
                else:
                    self.face((a[k], a[k2], b[k2], b[k]), mat, edge)
        self.face(tuple(reversed(rings[0])), mat)
        if len(rings[-1]) > 1:
            self.face(tuple(rings[-1]), mat)
        self.end()
        return rings

    def torus(self, name, c, R, r, mat, nu=18, nv=6):
        """Ring in the XZ plane (hole along y) around ``c``; a vertex sits at its very top (c.z + R + r)."""
        self.begin(name)
        ids = []
        for i in range(nu):
            a = math.pi / 2 + 2.0 * math.pi * i / nu
            d = (math.cos(a), 0.0, math.sin(a))
            ring = []
            for j in range(nv):
                b = 2.0 * math.pi * j / nv
                k = R + r * math.cos(b)
                ring.append(self.v((c[0] + d[0] * k, c[1] + r * math.sin(b), c[2] + d[2] * k)))
            ids.append(ring)
        for i in range(nu):
            a, b = ids[i], ids[(i + 1) % nu]
            for j in range(nv):
                j2 = (j + 1) % nv
                self.face((a[j], b[j], b[j2], a[j2]), mat)
        self.end()

    def box(self, name, c, size, mat, edge=0.0, rot_y=0.0, smooth=False):
        hx, hy, hz = size[0] / 2.0, size[1] / 2.0, size[2] / 2.0
        ca, sa = math.cos(rot_y), math.sin(rot_y)

        def p(x, y, z):
            return (c[0] + x * ca + z * sa, c[1] + y, c[2] - x * sa + z * ca)
        ring0 = [p(hx, -hy, -hz), p(hx, hy, -hz), p(-hx, hy, -hz), p(-hx, -hy, -hz)]
        ring1 = [p(hx, -hy, hz), p(hx, hy, hz), p(-hx, hy, hz), p(-hx, -hy, hz)]
        return self.loft(name, [ring0, ring1], mat, edge=edge, smooth=smooth)

    def glyph_solid(self, verts, faces, place, mat, depth, sink, name="glyphs"):
        """Closed glyph solid from a flat text fill (XY, readable from +Z): the fill welded and turned to +Z, then
        thickened from z = -sink (back, sunk into the surface it sits on) to depth - sink (front), with walls along
        the fill's net boundary chain. ``place`` maps it (local z = the surface's outward normal). Closed by
        construction even for overlapping font contours (every edge in >= 2 faces), which bake_web needs: its
        facing_flip only lets look-around views protect faces of closed pieces, and a piece counts as closed only
        when every one of its edges is. Returns the triangles added."""
        ids, pos = {}, []
        remap = []
        for p in verts:
            k = (round(p[0] * 1e5), round(p[1] * 1e5))
            if k not in ids:
                ids[k] = len(pos)
                pos.append((p[0], p[1]))
            remap.append(ids[k])
        fill, seen = [], set()
        for f in faces:
            idx = []
            for i in f:
                if remap[i] not in idx:
                    idx.append(remap[i])
            if len(idx) < 3 or frozenset(idx) in seen:
                continue
            a2 = sum(pos[idx[k]][0] * pos[idx[(k + 1) % len(idx)]][1] - pos[idx[(k + 1) % len(idx)]][0] *
                     pos[idx[k]][1] for k in range(len(idx)))
            if abs(a2) < 1e-12:
                continue
            seen.add(frozenset(idx))
            fill.append(tuple(idx) if a2 > 0 else tuple(reversed(idx)))
        net = {}
        for f in fill:
            for k in range(len(f)):
                a, b = f[k], f[(k + 1) % len(f)]
                if a < b:
                    net[(a, b)] = net.get((a, b), 0) + 1
                else:
                    net[(b, a)] = net.get((b, a), 0) - 1
        used = sorted({i for f in fill for i in f})
        if not used:
            return 0
        o = place((0.0, 0.0, 0.0))
        ax = [_sub(place(e), o) for e in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))]
        if _dot(ax[0], _cross(ax[1], ax[2])) <= 0.0:
            raise ValueError("glyph frame is mirrored: the text would read backwards")
        self.begin(name)
        top = {i: self.v(place((pos[i][0], pos[i][1], depth - sink))) for i in used}
        bot = {i: self.v(place((pos[i][0], pos[i][1], -sink))) for i in used}
        n = 0
        for f in fill:
            self.face(tuple(top[i] for i in f), mat, 0.0, smooth=False)
            self.face(tuple(bot[i] for i in reversed(f)), mat, 0.0, smooth=False)
            n += 2 * (len(f) - 2)
        for (a, b), c in net.items():              # one wall per edge on the fill's boundary chain (net != 0),
            if c == 0:                             # on the right of a -> b (the fill lies to its left); |net| > 1
                continue                           # (overlapping contours) still leaves every edge in >= 2 faces
            if c < 0:
                a, b = b, a
            self.face((bot[a], bot[b], top[b], top[a]), mat, 0.0, smooth=False)
            n += 2
        self.end()
        self.glyph_tris += n
        return n


def _chamfer_rect(cx, cy, hx, hy, c, z):
    """8 points (counter-clockwise from +Z) of a rectangle with 45 deg chamfered corners. Sides between points:
    0 +X face, 1 chamfer, 2 +Y (back), 3 chamfer, 4 -X face, 5 chamfer, 6 -Y (front), 7 chamfer."""
    return [(cx + hx, cy - hy + c, z), (cx + hx, cy + hy - c, z), (cx + hx - c, cy + hy, z),
            (cx - hx + c, cy + hy, z), (cx - hx, cy + hy - c, z), (cx - hx, cy - hy + c, z),
            (cx - hx + c, cy - hy, z), (cx + hx - c, cy - hy, z)]


# ---- plinth --------------------------------------------------------------------------------

def _plinth_faces():
    """(name, right, up, normal, plane) of the waist's four flat faces; 'plane' = signed coordinate of the face."""
    w = DIE[2]
    return (("front", (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0), w),
            ("back", (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0), w),
            ("east", (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), w),
            ("west", (0.0, -1.0, 0.0), (0.0, 0.0, 1.0), (-1.0, 0.0, 0.0), w))


def _w_plinth(g, collar):
    """Sumeru plinth on z 0: base slab, mouldings, waist, cap; a framed dark panel on each waist face; a socket
    collar (cx, hx, hy) on top that the blade comes out of."""
    rings = [_chamfer_rect(0.0, 0.0, w, w, c, z) for z, w, c in PLINTH_PROFILE]
    bevel_rows = {1, 3, 10, 11}
    g.loft("plinth", rings, "stone", edge=lambda r, c: 1.0 if r in bevel_rows else 0.0, smooth=True)
    # panels: dark plate in a raised frame, on every waist face (front: the name, sides: the saying, back: plain)
    z0, z1 = PANEL_Z
    bw, half = 0.10, 1.56
    for _nm, right, up, nrm, plane in _plinth_faces():
        o = (nrm[0] * plane, nrm[1] * plane, 0.0)
        f = _frame(right, up, nrm, o)

        def box(cu, cv, su, sv, d0, d1, mat):
            # box in face coordinates: u along right, v = z, depth d0..d1 out of the face
            pts = [(u, v, d) for u in (cu - su / 2, cu + su / 2) for v in (cv - sv / 2, cv + sv / 2) for d in (d0, d1)]
            w_ = [f(p) for p in pts]
            lo = [min(p[k] for p in w_) for k in range(3)]
            hi = [max(p[k] for p in w_) for k in range(3)]
            g.box("panel", [(lo[k] + hi[k]) / 2 for k in range(3)], [hi[k] - lo[k] for k in range(3)], mat)
        zc = (z0 + z1) / 2.0
        box(0.0, z1 - bw / 2, 2 * half, bw, -0.01, 0.06, "stone")
        box(0.0, z0 + bw / 2, 2 * half, bw, -0.01, 0.06, "stone")
        box(-half + bw / 2, zc, bw, z1 - z0 - 2 * bw, -0.01, 0.06, "stone")
        box(half - bw / 2, zc, bw, z1 - z0 - 2 * bw, -0.01, 0.06, "stone")
        box(0.0, zc, 2 * (half - bw), z1 - z0 - 2 * bw, -0.01, 0.03, "panel")
    # socket collar
    cx, hx, hy = collar
    rows = ((PLINTH_TOP - 0.06, 0.16), (PLINTH_TOP + 0.10, 0.16), (PLINTH_TOP + 0.20, 0.04), (PLINTH_TOP + 0.30, -0.04))
    g.loft("collar", [_chamfer_rect(cx, 0.0, hx + d, hy + d, 0.14, z) for z, d in rows], "panel",
           edge=lambda r, c: 1.0 if r == 1 else 0.0)


def _w_inscriptions(g, spec, glyph, couplet=True, couplet_res=COUPLET_RES):
    """The name (gold relief 3 cm proud, front panel) and the saying (gold inlay 4 mm proud, side panels)."""
    zc = sum(PANEL_Z) / 2.0
    face_d = DIE[2] + 0.03                         # the plate's outer face
    # name: two characters side by side
    size = NAME_CELL * 0.88
    n = len(spec["name"])
    for k, ch in enumerate(spec["name"]):
        u = (k - (n - 1) / 2.0) * NAME_CELL * 1.08
        vs, fs = glyph(ch, size, 3)
        g.glyph_solid(vs, fs, _frame((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0), (u, -face_d, zc)), "gold",
                      depth=0.034, sink=0.004)
    if not couplet:
        return
    # saying: vertical columns read right to left (as the viewer sees the face), top to bottom
    inner = -spec["side"]                          # local x sign of the face toward the gate's axis
    for cols, sgn in zip(spec["couplet"], (inner, -inner)):
        right = (0.0, float(sgn), 0.0)             # viewer at +x sign: +y is to the right (and the mirror)
        nrm = (float(sgn), 0.0, 0.0)
        nc = len(cols)
        pitch = COUPLET_CELL * 1.8
        for ci, col in enumerate(cols):
            u = ((nc - 1) / 2.0 - ci) * pitch      # first column on the right
            for r, ch in enumerate(col):
                v = zc + ((len(col) - 1) / 2.0 - r) * COUPLET_CELL
                vs, fs = glyph(ch, COUPLET_CELL * 0.86, couplet_res)
                g.glyph_solid(vs, fs, _frame(right, (0.0, 0.0, 1.0), nrm, (sgn * face_d, u * sgn, v)), "gold",
                              depth=0.007, sink=0.003)


# ---- Heaven Sword (jian) ---------------------------------------------------------------------

J_PLATE = (7.75, 8.05, 9.55, 9.85)   # the blade's name cartouche on the ridge: ramp in, flat plate, ramp out (z)
J_PLATE_W = 0.28                     # its half width
J_NAME = (0.52, (9.18, 8.42))        # blade name: character size, centres (top first); ~19 px tall at the hold
D_NAME = (0.60, 0.08, (9.66, 8.98))  # saber blade name: character size, x on the broad flat, centres (top first)


def _jian_T(z):
    return 0.15 + 0.04 * (z - J_Z0) / (J_ZTOP - J_Z0)


def _jian_inlay(z):
    """Half width of the glowing ridge inlay: grows in above the plinth, tapers into the name cartouche and grows
    out of it again, narrows under the guard."""
    a, _b, _c, d = J_PLATE
    away = min(max(1.0 - _ss((z - (a - 0.55)) / 0.55) + _ss((z - d) / 0.45), 0.0), 1.0)
    return 0.004 + 0.081 * _ss((z - 3.5) / 0.9) * away * (1.0 - 0.4 * _ss((z - 10.5) / 0.75))


def _jian_section(z):
    """12 points: edge, hone line, inlay, ridge, ... (counter-clockwise). Hone faces: cols 0, 5, 6, 11; the glowing
    ridge inlay: cols 2, 3, 8, 9 (flush with the flats). In the cartouche (J_PLATE) cols 2, 3, 8, 9 widen into a
    flat plate at the ridge's height that carries the name."""
    t = (z - J_Z0) / (J_ZTOP - J_Z0)
    W = 0.52 + 0.16 * t ** 0.8
    T = _jian_T(z)
    b, te = 0.13, 0.035
    a, b_, c_, d = J_PLATE
    p = _ss((z - a) / (b_ - a)) * (1.0 - _ss((z - c_) / (d - c_)))
    fo = _lerp(_jian_inlay(z), J_PLATE_W, p)
    ti = _lerp(T - (T - te) * fo / (W - b), T, p)
    pts = ((W, 0.0), (W - b, te), (fo, ti), (0.0, T), (-fo, ti), (-(W - b), te), (-W, 0.0), (-(W - b), -te),
           (-fo, -ti), (0.0, -T), (fo, -ti), (W - b, -te))
    return [(x, y, z) for x, y in pts]


J_RINGS = (2.35, 2.95, 3.5, 4.4, 5.6, 6.5, 7.2, 7.75, 8.05, 9.55, 9.85, 10.3, 10.75, 11.0, 11.25)
J_GUARD = (                    # right half of the guard outline (x, z about J_GUARD_Z), top centre to bottom centre
    (0.0, 0.40), (0.45, 0.38), (0.85, 0.30), (1.18, 0.15), (1.42, -0.06), (1.56, -0.30), (1.60, -0.50),
    (1.52, -0.64), (1.38, -0.66), (1.30, -0.56), (1.22, -0.40), (1.02, -0.27), (0.75, -0.22), (0.50, -0.26),
    (0.30, -0.32), (0.12, -0.38), (0.0, -0.40))


def _offset_outline(pts, d):
    """Closed polygon (x, z) offset inward by d (mitred, clamped)."""
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    sgn = 1.0 if area > 0 else -1.0                # counter-clockwise: inward normal of edge (dx, dz) is (-dz, dx)
    out = []
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]

        def nrm(a, b):
            dx, dz = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dz) or 1.0
            return (-dz / ln * sgn, dx / ln * sgn)
        n0, n1 = nrm(p0, p1), nrm(p1, p2)
        m = (n0[0] + n1[0], n0[1] + n1[1])
        ml = math.hypot(*m) or 1.0
        m = (m[0] / ml, m[1] / ml)
        cosh = max(m[0] * n1[0] + m[1] * n1[1], 0.5)
        out.append((p1[0] + m[0] * d / cosh, p1[1] + m[1] * d / cosh))
    return out


def _w_jian(g, spec, glyph):
    # blade (tip end buried in the plinth): hard edge, hone, ridge and cartouche lines; the ridge inlay glows except
    # where it narrows into the cartouche
    rings = [_jian_section(z) for z in J_RINGS]
    hone = {0, 5, 6, 11}
    inlay = {2, 3, 8, 9}

    def glow(z):
        return z >= 3.5 and not (J_PLATE[0] <= z < J_PLATE[3])
    g.loft("blade", rings, lambda r, c: "rune" if (c in inlay and glow(J_RINGS[r])) else "blade",
           edge=lambda r, c: 1.0 if c in hone else 0.0, hard_cols=tuple(range(12)))
    # the name inlaid in gold on the cartouche, top to bottom, on the front (and the back: BLADE_NAME_BACK)
    size, zs = J_NAME
    for sgn in ((-1.0, 1.0) if BLADE_NAME_BACK else (-1.0,)):
        for ch, z in zip(spec["name"], zs):
            vs, fs = glyph(ch, size, 2)
            g.glyph_solid(vs, fs, _frame((-sgn, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, sgn, 0.0),
                                         (0.0, sgn * _jian_T(z), z)), "gold", depth=0.006, sink=0.003,
                          name="blade_glyphs")
    # winged guard: pillow-extruded outline (bevelled faces), gold; a cyan gem on each face
    full = list(J_GUARD) + [(-x, z) for x, z in reversed(J_GUARD[1:-1])]
    inset = _offset_outline(full, 0.07)
    zc = J_GUARD_Z
    rings = [[(x, y, zc + z) for x, z in (o)] for o, y in ((inset, -0.30), (full, -0.22), (full, 0.22), (inset, 0.30))]
    g.loft("guard", rings, "gold", edge=lambda r, c: 1.0 if r != 1 else 0.6)
    gem = [(0.17, -0.01), (0.15, 0.035), (0.09, 0.065), (0.0, 0.08)]
    for sgn in (-1.0, 1.0):                        # dome along the face normal (_Geo.end fixes the winding)
        g.lathe("guard_gem", gem, 10, "rune",
                xf=_frame((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, sgn, 0.0), (0.0, sgn * 0.30, zc - 0.02)))
    # hilt: gold ferrule, cord-wrapped oval grip (ridges), gold ferrule, ruyi-mushroom pommel (gold), one lathe
    prof = [(0.0, 11.80, 0.78), (0.31, 11.80, 0.78), (0.31, 11.98, 0.78), (0.285, 12.05, 0.78)]
    mats = ["gold", "gold", "gold"]
    n_wrap = 32
    for k in range(1, n_wrap + 1):
        z = _lerp(12.05, 14.00, k / n_wrap)
        prof.append((0.265 if k % 2 == 0 else 0.29, z, 0.78))
        mats.append("wrap")
    tail = [(0.31, 14.07, 0.76), (0.31, 14.22, 0.74), (0.23, 14.30, 0.70), (0.30, 14.42, 0.66), (0.46, 14.62, 0.63),
            (0.57, 14.88, 0.62), (0.60, 15.10, 0.62), (0.53, 15.33, 0.62), (0.37, 15.50, 0.62), (0.16, 15.585, 0.62),
            (0.0, WEAPON_TOP, 0.62)]
    prof += tail
    mats += ["gold"] * len(tail)
    g.lathe("hilt", prof, 12, lambda i: mats[i], edge=lambda i: 0.4 if mats[i] == "gold" else 0.0)
    # cyan gems on the pommel's flat faces
    pgem = [(0.13, -0.02), (0.11, 0.025), (0.06, 0.05), (0.0, 0.06)]
    for sgn in (-1.0, 1.0):
        g.lathe("pommel_gem", pgem, 10, "rune",
                xf=_frame((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, sgn, 0.0), (0.0, sgn * 0.355, 15.0)))
    # silk tassel (剑穗): cord from the pommel, knot, gold bead, fringe bundle hanging beside the grip (static)
    g.tube("tassel_cord", [(0.30, 0.0, 15.05, 0.05), (0.62, -0.04, 14.98, 0.05), (0.80, -0.08, 14.72, 0.048),
                           (0.87, -0.10, 14.35, 0.046), (0.89, -0.10, 13.95, 0.045)], 6, "tassel")
    g.sphere("tassel_knot", (0.89, -0.10, 13.86), 0.12, "tassel", nu=8, nv=5, scale=(1.0, 1.0, 1.15))
    g.lathe("tassel_bead", [(0.0, 13.60), (0.08, 13.60), (0.11, 13.64), (0.11, 13.70), (0.07, 13.76), (0.0, 13.76)],
            10, "gold", center=(0.89, -0.10))
    ts = (0.0, 0.12, 0.3, 0.5, 0.7, 0.88, 1.0)
    rings = []
    for t in ts:
        c = (0.89 + 0.05 * t * t, -0.10 - 0.02 * t, 13.62 - 1.40 * t)
        R = 0.075 + 0.13 * t ** 0.7
        rings.append([(c[0] + (R if k % 2 == 0 else 0.82 * R) * math.cos(2 * math.pi * k / 14),
                       c[1] + (R if k % 2 == 0 else 0.82 * R) * math.sin(2 * math.pi * k / 14), c[2])
                      for k in range(14)])
    rings.reverse()                                # bottom to top, like every other loft
    g.loft("tassel_fringe", rings, "tassel")


# ---- Dragon Saber (dao) ----------------------------------------------------------------------
# A broad black-iron dao planted point-down. Seen from the front (-y) the spine (-x, toward the gate's axis) is thick
# and gently curved; the edge (+x) runs almost parallel to it under the guard (~1.3 m wide), then sweeps out to a
# ~2.3 m belly just above the plinth and turns back in where the point dives into the stone. The honed bevel is
# bright steel against the dark iron flat; a lighter fuller (血槽) runs along the spine; 屠龙 is inlaid in gold under
# the collar and a cyan line-art dragon rises up the flat (thin inlay strips laid on the blade mesh's own surface).
# Fittings: a gold cloud-point collar (吞口) wrapping the blade root, a begonia-shaped iron disc guard (海棠护手)
# with gold rim lines, a red cord-wrapped grip, a gold ring pommel (环首) and a red silk tassel on the inner side.

D_RINGS = tuple(round(D_Z0 + (D_ZTOP - D_Z0) * k / 32, 5) for k in range(33))   # dense, so inlays sit flush
D_SPINE = (-0.64, -0.18)       # spine x = a + b * s^2 (s = 0 at the blade top, 1 at the buried point end)
D_EDGE = ((0.0, 0.64), (0.15, 0.66), (0.32, 0.76), (0.50, 0.95), (0.66, 1.18), (0.78, 1.36), (0.87, 1.47),
          (0.94, 1.46), (1.0, 1.38))   # (s, edge x): the belly peaks just above the collar, then turns in
D_COLLAR = (0.33, 1.24, 0.40)  # plinth socket collar (cx, hx, hy) around the blade's foot
D_TUNKOU = (10.30, 11.30, 0.07, 0.24, 0.29)   # cloud-point collar: z of the point, z top, wrap past the spine
                                               # and edge, half thickness of the outline, of the bevelled faces
D_TUNKOU_HALF = (              # right half of its outline (x, z) normalised (x * half width, z from the point up)
    (1.00, 1.00), (1.00, 0.70), (1.05, 0.62), (1.03, 0.54), (0.94, 0.47), (0.82, 0.45), (0.71, 0.48), (0.63, 0.54),
    (0.56, 0.51), (0.49, 0.42), (0.40, 0.29), (0.27, 0.16), (0.13, 0.06), (0.0, 0.0))
D_GUARD = ((0.80, 11.20, "blade"), (0.96, 11.25, "gold"), (1.00, 11.31, "blade"), (1.00, 11.45, "gold"),
           (0.96, 11.51, "blade"), (0.84, 11.56, None))   # (scale, z, material of the band above) of the guard
D_GUARD_R = (1.00, 0.66, 0.07)  # half x, half y, lobe depth of the begonia outline
D_RING = (14.825, 0.46, 0.50, 0.095, 0.12)   # ring pommel: centre z, half width, half height, band half thickness
                                             # (radial), band half depth (y); top of the band at z 15.42
D_INLAY = (0.008, 0.004)       # inlay strips: top above the blade surface, bottom sunk into it


def _spline1(pts, x):
    """Catmull-Rom through (x, y) points (x increasing), clamped at the ends."""
    n = len(pts)
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    i = max(k for k in range(n - 1) if pts[k][0] <= x)
    t = (x - pts[i][0]) / (pts[i + 1][0] - pts[i][0])
    p0, p1, p2, p3 = pts[max(i - 1, 0)][1], pts[i][1], pts[i + 1][1], pts[min(i + 2, n - 1)][1]
    return 0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                  + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3)


def _curve(ctrl, step=0.04):
    """Catmull-Rom through control points (u, v, w) sampled about every ``step`` m (the width w interpolated too)."""
    n = len(ctrl)
    out = []
    for i in range(n - 1):
        p0, p1, p2, p3 = ctrl[max(i - 1, 0)], ctrl[i], ctrl[i + 1], ctrl[min(i + 2, n - 1)]
        m = max(1, int(math.ceil(math.hypot(p2[0] - p1[0], p2[1] - p1[1]) / step)))
        for j in range(m):
            t = j / m
            out.append(tuple(0.5 * (2 * p1[k] + (p2[k] - p0[k]) * t
                                    + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t * t
                                    + (3 * p1[k] - p0[k] - 3 * p2[k] + p3[k]) * t ** 3) for k in range(3)))
    out.append(tuple(ctrl[-1][:3]))
    return out


def _dao_s(z):
    return (D_ZTOP - z) / (D_ZTOP - D_Z0)


def _dao_body(z):
    """(xs, xe, Ts, c, b, te, yb) of the saber blade at z: spine x, edge x, half spine thickness, spine chamfer,
    hone width, half thickness at the hone line, and yb(x) = the flat's half thickness (spine shoulder to hone line)."""
    s = _dao_s(z)
    xs = D_SPINE[0] + D_SPINE[1] * s * s
    xe = _spline1(D_EDGE, s)
    Ts = 0.20 - 0.05 * s           # heavy spine, thinning toward the point
    c, te = 0.045, 0.05
    b = 0.15 + 0.12 * s            # the honed bevel widens with the belly

    def yb(x):
        return Ts + (te - Ts) * (x - (xs + c)) / ((xe - b) - (xs + c))
    return xs, xe, Ts, c, b, te, yb


def _dao_fuller(z):
    """(x0, x1, wall inset, depth) of the fuller along the spine; it runs out above the collar."""
    xs = _dao_body(z)[0]
    x0 = xs + 0.045 + 0.07
    return x0, x0 + 0.17, 0.035, 0.045 * _ss((z - 3.25) / 0.75)


def _dao_section(z):
    """15 points (counter-clockwise from +z): edge (+x), hone line, fuller, spine shoulder and chamfers (-x), then
    the front (-y) side. Faces (col c joins points c and c + 1): hone 0, 14; flat 1, 13; fuller 2-4, 10-12; flat by
    the spine 5, 9; spine chamfers 6, 8; spine 7."""
    xs, xe, Ts, c, b, te, yb = _dao_body(z)
    xg0, xg1, w, depth = _dao_fuller(z)
    y0, y1 = yb(xg0), yb(xg1)
    yb0, yb1 = yb(xg0 + w) - depth, yb(xg1 - w) - depth
    pts = ((xe, 0.0), (xe - b, te), (xg1, y1), (xg1 - w, yb1), (xg0 + w, yb0), (xg0, y0), (xs + c, Ts), (xs, Ts - c),
           (xs, -(Ts - c)), (xs + c, -Ts), (xg0, -y0), (xg0 + w, -yb0), (xg1 - w, -yb1), (xg1, -y1), (xe - b, -te))
    return [(x, y, z) for x, y in pts]


_DAO_FRONT = (8, 9, 10, 11, 12, 13, 14, 0)     # section points along the front face, spine to edge


def _dao_surface(u, v):
    """Half thickness of the blade mesh at x = u, z = v: its loft quads between D_RINGS as built (ring points lerped
    in z, then linear in x along the face), so inlays laid on it sit flush however the profile curves."""
    rz = D_RINGS
    i = 0
    while i < len(rz) - 2 and v > rz[i + 1]:
        i += 1
    t = min(max((v - rz[i]) / (rz[i + 1] - rz[i]), 0.0), 1.0)
    a, b = _dao_section(rz[i]), _dao_section(rz[i + 1])
    pts = [(_lerp(a[k][0], b[k][0], t), _lerp(a[k][1], b[k][1], t)) for k in _DAO_FRONT]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 - 1e-9 <= u <= x1 + 1e-9 and x1 > x0:
            return -_lerp(y0, y1, (u - x0) / (x1 - x0))
    return -(pts[0][1] if u < pts[0][0] else pts[-1][1])     # off the blade (glyph_solid's frame probe): clamp


def _dao_flat(z, margin=0.0):
    """(x0, x1) of the broad flat between the fuller and the hone line at z: inlays stay inside it."""
    _xs, xe, _Ts, _c, b, _te, _yb = _dao_body(z)
    return _dao_fuller(z)[1] + margin, xe - b - margin


def _dao_place(u0, v0, sgn=-1.0):
    """glyph_solid frame on a blade face (sgn -1: the front, +1: the back): local (a, b, h) -> x = u0 -/+ a,
    z = v0 + b, h above the mesh surface. Follows the surface, so a flat glyph bends with the blade."""
    def f(p):
        u, v = u0 - sgn * p[0], v0 + p[1]
        return (u, sgn * (_dao_surface(u, v) + p[2]), v)
    return f


def _w_stroke(g, pts, mat, sgn=-1.0, top=None, name="dragon"):
    """Closed inlay strip along (u, v, width) points on a blade face (sgn as _dao_place), from D_INLAY[1] below
    the surface to ``top`` (D_INLAY[0]) above it."""
    top = D_INLAY[0] if top is None else top
    sink = D_INLAY[1]

    def at(u, v, d):
        return (u, sgn * (_dao_surface(u, v) + d), v)
    rings = []
    n = len(pts)
    for i, (u, v, w) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        du, dv = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(du, dv) or 1.0
        nu, nv = -dv / ln * 0.5 * w, du / ln * 0.5 * w
        rings.append([at(u + nu, v + nv, -sink), at(u - nu, v - nv, -sink), at(u - nu, v - nv, top),
                      at(u + nu, v + nv, top)])
    g.loft(name, rings, mat, smooth=False)


D_DRAGON_BODY = (              # centre line of the dragon's body, from the neck (behind the head, low on the
    (0.74, 4.00, 0.15), (0.84, 4.40, 0.185), (0.74, 4.82, 0.195),     # blade's broad belly) up to the tail under
    (0.46, 5.12, 0.19), (0.12, 5.42, 0.18), (-0.06, 5.84, 0.17),      # the name: (x, z, width) on the front flat
    (0.06, 6.26, 0.155), (0.38, 6.58, 0.14), (0.52, 6.96, 0.125), (0.36, 7.34, 0.11), (0.08, 7.62, 0.09),
    (-0.04, 7.92, 0.07), (0.04, 8.20, 0.05), (0.18, 8.40, 0.03))
D_DRAGON_DORSAL = 1.0          # the body's back: +1 on the right of its neck-to-tail direction (fins), belly opposite
D_DRAGON_HEAD = (0.66, 3.60, math.radians(168.0), 1.0, -1.0)   # back of the skull (x, z), snout direction (it looks
                                                                # toward the spine, the gate's axis), scale, mirror
D_DRAGON_HEAD_STROKES = (      # head frame: X along the snout, Y to the top of the head
    ("skull", ((-0.10, 0.06, 0.10), (0.00, 0.07, 0.26), (0.18, 0.08, 0.34), (0.38, 0.07, 0.28), (0.58, 0.05, 0.21),
               (0.76, 0.07, 0.21), (0.90, 0.10, 0.25), (0.99, 0.08, 0.15), (1.03, 0.06, 0.05))),
    ("jaw", ((0.16, -0.12, 0.16), (0.40, -0.20, 0.13), (0.64, -0.28, 0.09), (0.82, -0.31, 0.06), (0.92, -0.25, 0.03))),
    ("fang", ((0.78, -0.03, 0.06), (0.80, -0.12, 0.035), (0.81, -0.17, 0.014))),
    ("fang", ((0.66, -0.25, 0.055), (0.67, -0.17, 0.03), (0.68, -0.12, 0.014))),
    ("brow", ((0.48, 0.20, 0.06), (0.38, 0.27, 0.10), (0.24, 0.32, 0.08), (0.12, 0.33, 0.03))),
    ("antler", ((0.22, 0.22, 0.10), (0.12, 0.40, 0.08), (-0.02, 0.55, 0.06), (-0.18, 0.64, 0.04),
                (-0.32, 0.64, 0.016))),
    ("antler", ((0.04, 0.52, 0.05), (0.10, 0.64, 0.032), (0.20, 0.70, 0.014))),
    ("mane", ((0.14, 0.04, 0.26), (-0.06, 0.14, 0.24), (-0.22, 0.30, 0.17), (-0.30, 0.48, 0.09), (-0.26, 0.62, 0.02))),
    ("mane", ((0.10, -0.10, 0.16), (-0.10, -0.12, 0.13), (-0.28, -0.04, 0.08), (-0.38, 0.10, 0.02))),
    ("whisker", ((0.97, 0.18, 0.05), (0.93, 0.36, 0.042), (0.76, 0.46, 0.036), (0.56, 0.50, 0.03), (0.40, 0.60, 0.024),
                 (0.34, 0.74, 0.016))),
    ("whisker", ((0.95, 0.00, 0.05), (1.04, -0.18, 0.044), (0.96, -0.36, 0.038), (0.76, -0.42, 0.032),
                 (0.52, -0.42, 0.026), (0.34, -0.48, 0.018))),
    ("beard", ((0.48, -0.30, 0.10), (0.42, -0.42, 0.07), (0.32, -0.48, 0.02))),
)
D_DRAGON_EYE = ((0.36, 0.11, 0.075), (0.45, 0.12, 0.06))   # head frame; dark iron set on top of the skull
D_DRAGON_STEP = dict(body=0.08, body_back=1.0, body_belly=1.0, fin=1.0, leg=1.0, claw=1.0, tail=1.0, fang=1.0)
                               # stroke sampling (m; 1.0: through the control points only); else 0.045
D_DRAGON_GAP = 0.045           # the dark line between the body's back and belly strips, at the neck


def _dao_dragon():
    """The dragon as strokes [(name, [(x, z, width) control points])] on the front flat: the head low on the broad
    belly of the blade looking toward the spine (the gate's axis), the serpentine body rising from it in S-curves,
    thick at the chest and tapering to a flame-tipped tail under the name; dorsal fins on its back and two legs with
    three claws on its belly (both laid out along the body curve)."""
    out = _dragon_body_strips()
    pts = _curve(D_DRAGON_BODY, 0.02)
    acc = [0.0]
    for a, b in zip(pts, pts[1:]):
        acc.append(acc[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = acc[-1]

    def at(frac):
        """(point, tangent toward the tail, dorsal normal) on the body at an arc-length fraction."""
        d = frac * total
        i = min(max(k for k in range(len(acc)) if acc[k] <= d), len(pts) - 2)
        a, b = pts[i], pts[i + 1]
        t = (d - acc[i]) / max(acc[i + 1] - acc[i], 1e-9)
        p = (_lerp(a[0], b[0], t), _lerp(a[1], b[1], t), _lerp(a[2], b[2], t))
        ln = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        tg = ((b[0] - a[0]) / ln, (b[1] - a[1]) / ln)
        return p, tg, (D_DRAGON_DORSAL * tg[1], -D_DRAGON_DORSAL * tg[0])

    def rot(v, ang):
        c, s_ = math.cos(ang), math.sin(ang)
        return (v[0] * c - v[1] * s_, v[0] * s_ + v[1] * c)
    # dorsal fins: swept toward the tail, shrinking along the body
    f = 0.10
    while f < 0.86:
        p, tg, dn = at(f)
        sz = 1.0 - 0.55 * f
        base = (p[0] + dn[0] * p[2] * 0.42, p[1] + dn[1] * p[2] * 0.42)
        d = (dn[0] * 0.73 + tg[0] * 0.68, dn[1] * 0.73 + tg[1] * 0.68)   # swept back toward the tail
        ln = 0.19 * sz
        out.append(("fin", ((base[0], base[1], 0.085 * sz),
                             (base[0] + d[0] * ln * 0.55, base[1] + d[1] * ln * 0.55, 0.045 * sz),
                             (base[0] + d[0] * ln, base[1] + d[1] * ln, 0.016))))
        f += 0.055
    # legs (front at the chest, rear before the tail) with three claws
    for frac, ln in ((0.10, 1.2), (0.52, 1.0)):
        p, tg, dn = at(frac)
        bn = (-dn[0], -dn[1])                   # belly side
        up = (-tg[0], -tg[1])                   # toward the head
        a0 = (p[0], p[1])
        a1 = (a0[0] + (bn[0] * 0.8 + up[0] * 0.5) * 0.24 * ln, a0[1] + (bn[1] * 0.8 + up[1] * 0.5) * 0.24 * ln)
        a2 = (a1[0] + (bn[0] * 0.5 + tg[0] * 0.8) * 0.18 * ln, a1[1] + (bn[1] * 0.5 + tg[1] * 0.8) * 0.18 * ln)
        out.append(("leg", ((a0[0], a0[1], 0.09 * ln), (a1[0], a1[1], 0.07 * ln), (a2[0], a2[1], 0.05 * ln))))
        dirn = ((a2[0] - a1[0]), (a2[1] - a1[1]))
        dl = math.hypot(*dirn) or 1.0
        dirn = (dirn[0] / dl, dirn[1] / dl)
        for ang in (-0.7, 0.0, 0.7):
            c = rot(dirn, ang)
            tip = (a2[0] + c[0] * 0.10 * ln, a2[1] + c[1] * 0.10 * ln)
            hook = rot(c, 0.6 if ang >= 0 else -0.6)
            out.append(("claw", ((a2[0], a2[1], 0.035 * ln), (tip[0], tip[1], 0.026 * ln),
                                 (tip[0] + hook[0] * 0.04 * ln, tip[1] + hook[1] * 0.04 * ln, 0.014))))
    # tail fin: three flames at the tail tip
    p, tg, dn = at(0.985)
    for ang, ln in ((0.5, 0.16), (0.0, 0.2), (-0.5, 0.15)):
        c = rot(tg, ang)
        out.append(("tail", ((p[0], p[1], 0.04), (p[0] + c[0] * ln * 0.6, p[1] + c[1] * ln * 0.6, 0.03),
                             (p[0] + c[0] * ln, p[1] + c[1] * ln, 0.014))))
    # head
    for nm, ctrl in D_DRAGON_HEAD_STROKES:
        out.append((nm, _dragon_head_pts(ctrl)))
    return out


def _dragon_body_strips():
    """The body drawn as line art: two strips along its back and its belly with a dark gap between them that
    closes toward the tail (where the strips merge into one). Sampled points, so step 1 keeps them as they are."""
    pts = _curve(D_DRAGON_BODY, D_DRAGON_STEP["body"])
    n = len(pts)
    back, belly = [], []
    for i, (u, v, w) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        du, dv = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(du, dv) or 1.0
        nu, nv = D_DRAGON_DORSAL * dv / ln, -D_DRAGON_DORSAL * du / ln     # toward the back
        gap = D_DRAGON_GAP * max(0.0, 1.0 - i / (0.8 * (n - 1)))
        sw = 0.5 * (w - gap)
        off = 0.5 * (gap + sw)
        back.append((u + nu * off, v + nv * off, sw))
        belly.append((u - nu * off, v - nv * off, sw))
    return [("body_back", tuple(back)), ("body_belly", tuple(belly))]


def _dragon_head_pts(ctrl):
    """Head-frame control points (X along the snout, Y to the top of the head, width) -> blade (x, z, width)."""
    hx, hz, ang, sc, mirror = D_DRAGON_HEAD
    X, Y = (math.cos(ang), math.sin(ang)), (-mirror * math.sin(ang), mirror * math.cos(ang))
    return tuple((hx + sc * (a * X[0] + b * Y[0]), hz + sc * (a * X[1] + b * Y[1]), sc * w) for a, b, w in ctrl)


def _w_dao(g, spec, glyph):
    # blade: hard lines everywhere; bright honed bevel, lighter fuller, dark flat
    rings = [_dao_section(z) for z in D_RINGS]
    hone, fuller = (0, 14), (2, 3, 4, 10, 11, 12)
    g.loft("blade", rings, lambda r, c: "hone" if c in hone else "blade",
           edge=lambda r, c: 1.0 if c in hone or c in fuller else (0.6 if c in (6, 8) else (0.3 if c == 7 else 0.0)),
           hard_cols=tuple(range(15)))
    # the name inlaid in gold under the collar, top to bottom, on the front (and the back: BLADE_NAME_BACK)
    size, xn, zs = D_NAME
    for sgn in ((-1.0, 1.0) if BLADE_NAME_BACK else (-1.0,)):
        for ch, z in zip(spec["name"], zs):
            vs, fs = glyph(ch, size, 2)
            g.glyph_solid(vs, fs, _dao_place(xn, z, sgn), "gold", depth=0.007, sink=0.003, name="blade_glyphs")
    # the dragon, cyan inlay strips on the front flat
    for nm, ctrl in _dao_dragon():
        _w_stroke(g, _curve(ctrl, D_DRAGON_STEP.get(nm, 0.045)), "rune", name="dragon")
    _w_stroke(g, _curve(_dragon_head_pts(D_DRAGON_EYE)), "blade", top=D_INLAY[0] + 0.004, name="dragon_eye")
    # cloud-point collar (吞口): pillow-extruded outline wrapping the blade root, gold
    zp, zt, wrap, t0, t1 = D_TUNKOU
    xs, xe = _dao_body(zt - 0.5)[:2]
    cx, hw = 0.5 * (xs + xe), 0.5 * (xe - xs) + wrap
    right = [(cx + x * hw, zp + z * (zt - zp)) for x, z in D_TUNKOU_HALF]
    full = right + [(2 * cx - x, z) for x, z in reversed(right[:-1])]
    inset = _offset_outline(full, 0.05)
    g.loft("tunkou", [[(x, y, z) for x, z in o] for o, y in ((inset, -t1), (full, -t0), (full, t0), (inset, t1))],
           "gold", edge=lambda r, c: 1.0 if r != 1 else 0.5)
    # begonia disc guard (海棠护手): iron, gold rim lines
    rx, ry, lobe = D_GUARD_R
    gr = []
    for k, z, _m in D_GUARD:
        gr.append([(rx * k * (1 + lobe * math.cos(4 * a)) * math.cos(a), ry * k * (1 + lobe * math.cos(4 * a)) *
                    math.sin(a), z) for a in (2 * math.pi * j / 32 for j in range(32))])
    gm = [m for _k, _z, m in D_GUARD[:-1]]
    g.loft("guard", gr, lambda r, c: gm[r], edge=lambda r, c: 1.0 if gm[r] == "gold" else 0.2, cap_mat="blade",
           smooth=True)
    # two-handed grip: gold ferrule, red cord wrap with ridges, gold ferrule and neck into the ring
    prof = [(0.0, 11.50, 0.8), (0.36, 11.50, 0.8), (0.385, 11.60, 0.8), (0.385, 11.72, 0.8), (0.34, 11.78, 0.8)]
    mats = ["gold", "gold", "gold", "gold"]
    n_wrap = 26
    for k in range(1, n_wrap + 1):
        prof.append((0.30 if k % 2 == 0 else 0.325, _lerp(11.78, 14.02, k / n_wrap), 0.8))
        mats.append("wrap")
    tail = [(0.35, 14.06, 0.8), (0.37, 14.12, 0.8), (0.37, 14.22, 0.8), (0.30, 14.28, 0.8), (0.21, 14.34, 0.8),
            (0.0, 14.38, 0.8)]
    prof += tail
    mats += ["gold"] * len(tail)
    g.lathe("grip", prof, 12, lambda i: mats[i], edge=lambda i: 0.4 if mats[i] == "gold" else 0.0)
    # ring pommel (环首): an oval gold ring in the blade's plane, chamfered band, a bud finial on top
    cz, ra, rb, rr, yd = D_RING
    ch, bead = 0.03, 0.03
    sec = ((rr, -yd + ch), (rr, yd - ch), (rr - ch, yd), (0.4 * rr, yd), (0.0, yd + bead), (-0.4 * rr, yd),
           (-rr + ch, yd), (-rr, yd - ch), (-rr, -yd + ch), (-rr + ch, -yd), (-0.4 * rr, -yd), (0.0, -yd - bead),
           (0.4 * rr, -yd), (rr - ch, -yd))     # chamfered band, a raised bead ridge along both faces
    loop = []
    for j in range(20):
        a = math.pi / 2 + 2.0 * math.pi * j / 20
        nx, nz = rb * math.cos(a), ra * math.sin(a)
        ln = math.hypot(nx, nz)
        nx, nz = nx / ln, nz / ln
        loop.append([(ra * math.cos(a) + r * nx, y, cz + rb * math.sin(a) + r * nz) for r, y in sec])
    g.loft_loop("ring_pommel", loop, "gold", edge=lambda r, c: 0.6 if c in (3, 4, 10, 11) else 0.2)
    g.lathe("finial", [(0.0, 15.38), (0.075, 15.38), (0.105, 15.44), (0.09, 15.505), (0.045, 15.565),
                       (0.0, WEAPON_TOP)], 10, "gold", edge=0.4)
    # red silk tassel (刀穗) tied to the ring's inner side, hanging beside the grip (static)
    tx, ty = -0.90, -0.10
    g.tube("tassel_cord", [(-0.43, 0.0, 14.70, 0.05), (-0.64, -0.04, 14.63, 0.05), (-0.81, -0.08, 14.42, 0.048),
                           (-0.88, ty, 14.08, 0.046), (tx, ty, 13.72, 0.045)], 6, "wrap")
    g.sphere("tassel_knot", (tx, ty, 13.62), 0.12, "wrap", nu=8, nv=5, scale=(1.0, 1.0, 1.15))
    g.lathe("tassel_bead", [(0.0, 13.36), (0.08, 13.36), (0.11, 13.40), (0.11, 13.46), (0.07, 13.52), (0.0, 13.52)],
            10, "gold", center=(tx, ty))
    ts = (0.0, 0.12, 0.3, 0.5, 0.7, 0.88, 1.0)
    rings = []
    for t in ts:
        c = (tx - 0.05 * t * t, ty - 0.02 * t, 13.38 - 1.40 * t)
        R = 0.075 + 0.13 * t ** 0.7
        rings.append([(c[0] + (R if k % 2 == 0 else 0.82 * R) * math.cos(2 * math.pi * k / 14),
                       c[1] + (R if k % 2 == 0 else 0.82 * R) * math.sin(2 * math.pi * k / 14), c[2])
                      for k in range(14)])
    rings.reverse()
    g.loft("tassel_fringe", rings, "wrap")


def weapon_geo(spec, glyph, couplet=None, couplet_res=COUPLET_RES):
    """The whole weapon with its plinth as a _Geo (local frame: z up from the plaza, front -Y). glyph(ch, size, res)
    -> (verts, faces) of a character's flat fill (blender_glyph; tests pass a stand-in)."""
    g = _Geo()
    if spec["kind"] == "jian":
        _w_plinth(g, (0.0, 0.95, 0.42))
        _w_jian(g, spec, glyph)
    else:
        _w_plinth(g, D_COLLAR)
        _w_dao(g, spec, glyph)
    _w_inscriptions(g, spec, glyph, WEAPON_COUPLET if couplet is None else couplet, couplet_res)
    return g


def weapon_geo_budget(spec, glyph, log=None):
    """weapon_geo within WEAPON_TRI_BUDGET: the couplet at COUPLET_RES, else res 1, else without it."""
    tries = [(WEAPON_COUPLET, r) for r in sorted({COUPLET_RES, 1}, reverse=True)] + [(False, 1)]
    for couplet, res in tries:
        g = weapon_geo(spec, glyph, couplet, res)
        if g.tris() <= WEAPON_TRI_BUDGET or (couplet, res) == tries[-1]:
            if log:
                log(spec["key"], "triangles", g.tris(), "glyphs", g.glyph_tris, "couplet", couplet, "res", res)
            return g
        if log:
            log(spec["key"], "over budget:", g.tris(), "> %d" % WEAPON_TRI_BUDGET, "(couplet res %d)" % res)
    return g


def _font_path():
    """KaiTi as an absolute path that both os.path and bpy.data.fonts.load accept (on the render box the fonts are
    mirrored at '/C:/Windows/Fonts/' and Blender runs in '/')."""
    for p in (U.FONT_KAITI, U.FONT_YAHEI):
        for c in (p, "/" + p if p and not p.startswith("/") else None):
            if c and os.path.isfile(c):
                return os.path.abspath(c)
    return U.FONT_KAITI


def blender_glyph(ch, size, res):
    """(verts, faces) of one KaiTi character's flat fill from props._text_mesh (XY plane, readable from +Z,
    centred on its box); _Geo.glyph_solid thickens it."""
    me = P._text_mesh(ch, size, res, font=_font_path())
    if not len(me.polygons):
        raise RuntimeError("glyph %r has no faces (font %s not loaded?)" % (ch, _font_path()))
    return [tuple(v.co) for v in me.vertices], [tuple(p.vertices) for p in me.polygons]


def _geo_to_mesh(g, name, materials):
    """Write a _Geo into a new mesh: material slots in ``materials`` order (role -> material name), the FACE float
    attribute 'edge', smooth faces with hard edges (marked, sharper than WEAPON_SMOOTH, between materials, open)."""
    roles = list(materials)
    slot = {r: i for i, r in enumerate(roles)}
    bm = bmesh.new()
    layer = bm.faces.layers.float.new(U.EDGE_ATTR)
    vs = [bm.verts.new(p) for p in g.verts]
    bm.verts.index_update()
    skipped = 0
    for idx, m, e, sm in zip(g.faces, g.mat, g.edge, g.smooth):
        try:
            f = bm.faces.new([vs[i] for i in idx])
        except ValueError:                         # a glyph mesh's duplicate face: keep the first
            skipped += 1
            continue
        f.material_index = slot[m]
        f[layer] = e
        f.smooth = sm
    bm.normal_update()
    for e in bm.edges:
        lf = e.link_faces
        a, b = e.verts[0].index, e.verts[1].index
        key = (a, b) if a < b else (b, a)
        e.smooth = not (len(lf) != 2 or key in g.sharp or lf[0].material_index != lf[1].material_index
                        or e.calc_face_angle(math.pi) > WEAPON_SMOOTH)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    U.set_materials(me, [materials[r] for r in roles])
    me.update()
    me["gate_weapon_skipped_faces"] = skipped
    return me


def weapon_mesh(spec, fresh=False, log=None):
    """Mesh 'gate.<key>' (tagged sect_shared). fresh=True builds a new one even when it exists; the old one is
    renamed '<key>.old' for the caller to free."""
    key = K + "." + spec["key"]
    me = bpy.data.meshes.get(key)
    if me is not None and me.get("sect_shared") == key and not fresh:
        return me
    g = weapon_geo_budget(spec, blender_glyph, log=log)
    new = _geo_to_mesh(g, key + ".new", spec["materials"])
    if me is not None:
        me.name = key + ".old"
    new.name = key
    new["sect_shared"] = key
    new["gate_weapon_tris"] = g.tris()
    return new


def weapon_transform(spec):
    """(location, rotation) under gate.root: at x = side * 16, y -25, turned 12 deg (toward the axis with
    WEAPON_FACE_IN)."""
    s = spec["side"]
    yaw = (-s if WEAPON_FACE_IN else s) * WEAPON_YAW
    return (s * WEAPON_X, WEAPON_Y, 0.0), (0.0, 0.0, yaw)


# ---- plaza --------------------------------------------------------------------------------

def _plaza(coll, root):
    # paving (front part up to the gate, back part to the plateau edge)
    _grid_slab("plaza", coll, root, -PLAZA_X, PLAZA_X, PLAZA_Y0, PLAZA_Y1, -0.6, 0.0)
    # stair-head forecourt: bridges the terrace rim between the stair top and the plaza
    _grid_slab("forecourt", coll, root, -HEAD_X, HEAD_X, STAIR_Y0, PLAZA_Y0, -0.6, 0.0)
    # depart landing: 12 x 12 m on the axis behind the back opening; the stair to the mirror
    # starts flush at its far edge (AREA['depart'])
    _grid_slab("depart_landing", coll, root, -DEPART_X, DEPART_X, PLAZA_Y1, DEPART_Y1, -0.6, 0.0)

    # balustrades: from the stair top along the forecourt, then front (open for the stairs),
    # sides, back (open for the depart landing), then along both sides of the landing (open at
    # its far end for the stair north)
    zb = 0.0
    xi = STAIR_W / 2 + 0.6
    xo = PLAZA_X - 0.4
    xd = DEPART_X - 0.4
    yf, yk = PLAZA_Y0 + 0.4, PLAZA_Y1 - 0.4
    for s in (-1, 1):
        A.balustrade(U.name(K, "balustrade"), coll,
                     [(s * xi, STAIR_Y0 + 0.3, zb), (s * xi, yf, zb), (s * xo, yf, zb),
                      (s * xo, yk, zb), (s * xd, yk, zb), (s * xd, DEPART_Y1 - 0.4, zb)],
                     height=1.1, post_spacing=2.4, parent=root)

    # guardian lions flanking the stair top (male +X, female -X; paws toward the axis)
    P.guardian_lion(coll, 2.0, mirror=False, name=U.name(K, "lion"), parent=root, location=(10.6, -30.0, 0))
    P.guardian_lion(coll, 2.0, mirror=True, name=U.name(K, "lion"), parent=root, location=(-10.6, -30.0, 0))

    # the legendary weapons, blade-down in their plinths: Heaven Sword (west, 'gate.sword_monolith') and Dragon Saber
    # (east, 'gate.sword_monolith.001'); the names and the local box are the web pipeline's (see WEAPONS)
    for spec in WEAPONS:
        loc, rot = weapon_transform(spec)
        U.object_from_mesh(U.name(K, "sword_monolith"), weapon_mesh(spec), coll, parent=root,
                           location=loc, rotation=rot)

    # banners along the plaza sides, cloth hanging toward the axis
    for i, y in enumerate((-30.0, -20.0, 0.0, 14.0)):
        for s in (-1, 1):
            P.banner(coll, 14.0, 1.7, material=(0 if i % 2 == 0 else 3), seed=40 + i * 2 + (s > 0),
                     name=U.name(K, "banner"), parent=root, location=(s * 19.4, y, 0.0),
                     rotation=(0, 0, 0.0 if s < 0 else math.pi))

    # stone lanterns along the axis path
    for y in (-20.0, 2.0, 14.0):
        for s in (-1, 1):
            P.lantern_stone(coll, 3.2, name=U.name(K, "lantern"), parent=root, location=(s * 8.0, y, 0.0))

    # glowing trigram circle in front of the gate (magic layer, sparing)
    P.rune_ring(coll, 5.0, 0.7, "trigram", name=U.name(K, "rune_ring"), parent=root,
                location=(0.0, -23.0, 0.0))


PLAQUE_DESIGN_CHARS = 3   # the paifang's plaque zone was sized for a 3-character name


def plaque_width(pw, text):
    """Plaque width for ``text``. props.plaque's height follows the character size, so a name shorter than
    PLAQUE_DESIGN_CHARS gets a narrower board at the height the plaque zone was designed for (3 characters at
    width ``pw``), instead of a taller board that would crowd the beams."""
    n = max(1, len(text))
    if n >= PLAQUE_DESIGN_CHARS:
        return pw
    return pw * (n * 1.12 + 0.95) / (PLAQUE_DESIGN_CHARS * 1.12 + 0.95)


def _gate(coll, root):
    g = A.paifang(U.name(K, "paifang"), coll, bays=5, width=GATE_W, height=GATE_H, seed=3,
                  parent=root, location=(0.0, GATE_Y, 0.0))
    anchor = bpy.data.objects[g["plaque_anchor"]]
    pw = float(g["plaque_size"][0])
    # On the Linux render box the fonts are mirrored at "/C:/Windows/Fonts/"; Python finds the
    # relative "C:/..." path from cwd "/", but bpy.data.fonts.load does not. Use the absolute
    # form for this call only (the lib reads U.FONT_KAITI at call time), then restore it.
    saved = U.FONT_KAITI
    if os.name != "nt" and os.path.exists(os.path.abspath(saved)):
        U.FONT_KAITI = os.path.abspath(saved)
    try:
        plaque = P.plaque(coll, AREA["title_zh"], plaque_width(pw, AREA["title_zh"]), name=U.name(K, "plaque"),
                          parent=anchor)
    finally:
        U.FONT_KAITI = saved
    _sun_moon(coll, g, anchor, plaque)
    return g


# ---- the sect's sun-and-moon emblem 日月 on the paifang (明 = 日 sun + 月 moon) -------------------------------
# A gilt ridge finial 日月宝顶 (props.sunmoon_finial: the emblem in the round, a crescent cradling a rayed sun) in the
# middle of the top roof's main ridge, against the sky in the 93 hold; and two lacquered medallions
# (props.sunmoon_medallion) on the plaque zone either side of the 明教 plaque that spell the name out: the sun 日 on
# the viewer's left, the moon 月 on the right with its horns turned toward the plaque.
FINIAL_R = 1.3                 # the finial's emblem unit radius (m): a 2.2 m wide moon, 2.6 m above the ridge
MEDAL_R = 0.38                 # medallion radius / the plaque zone's height (2.64 m zone -> 1.0 m)
FINIAL_NAME, SUN_NAME, MOON_NAME = "sunmoon_finial", "sun_medallion", "moon_medallion"


def _mw(ob):
    """World matrix from the parent chain (valid right after creation, before any depsgraph update)."""
    m = ob.matrix_basis.copy()
    while ob.parent is not None:
        m = ob.matrix_parent_inverse @ m
        ob = ob.parent
        m = ob.matrix_basis @ m
    return m


def _mesh_pts(ob):
    mw = _mw(ob)
    return [mw @ v.co for v in ob.data.vertices]


def sun_moon_layout(paifang, anchor, plaque):
    """Where the gate's emblem pieces go, from the built paifang (root props and its top ridge) and plaque.
    {'finial': (R, parent, local location), 'medallions': [(part, radius, parent, local location, name), ...]}.
    The finial stands on the highest '.ridges' mesh's top, on the paifang's centre line. The medallions hang on
    the plaque zone's board (arch.paifang: a beam bw * 0.35 deep behind the anchor at y = -bw / 2 - 0.06, zone
    height = plaque_size h / 0.86), centred between the plaque's frame and the centre bay's columns."""
    from mathutils import Vector
    ridges = [o for o in paifang.children_recursive if o.type == 'MESH' and o.name.endswith(".ridges")]
    if not ridges:
        raise RuntimeError("%s has no '.ridges' meshes" % paifang.name)
    z_top = max(p.z for o in ridges for p in _mesh_pts(o))
    pmw = _mw(paifang)
    top_local = pmw.inverted() @ Vector((pmw.translation.x, pmw.translation.y, z_top))
    zone_h = float(paifang["plaque_size"][1]) / 0.86
    open_half = 0.5 * float(paifang["arch_center_opening"][0])
    ya = anchor.location.y
    bw = 2.0 * (-ya - 0.06)
    face_dy = -0.175 * bw - ya                           # the zone board's front face, from the anchor
    ax = _mw(anchor).translation.x
    frame_half = max(abs(p.x - ax) for o in plaque.children_recursive if o.type == 'MESH' for p in _mesh_pts(o))
    xm = 0.5 * (frame_half + open_half)
    rm = MEDAL_R * zone_h
    return dict(finial=(FINIAL_R, paifang, (0.0, 0.0, round(top_local.z, 4))),
                medallions=[("sun", rm, anchor, (-xm, face_dy, 0.0), SUN_NAME),
                            ("moon", rm, anchor, (xm, face_dy, 0.0), MOON_NAME)])


def _sun_moon(coll, paifang, anchor, plaque):
    lay = sun_moon_layout(paifang, anchor, plaque)
    R, parent, loc = lay["finial"]
    P.sunmoon_finial(coll, R, name=U.name(K, FINIAL_NAME), parent=parent, location=loc)
    for part, rm, parent, loc, nm in lay["medallions"]:
        P.sunmoon_medallion(coll, rm, part, name=U.name(K, nm), parent=parent, location=loc)


def build(collection):
    old = bpy.data.objects.get(K + ".root")
    if old is not None:
        U.delete_hierarchy(old)
    root = U.empty(K + ".root", collection, display_size=4.0)
    _plaza(collection, root)
    _gate(collection, root)
    _stairway(collection, root)
    _ridge(collection, root)
    return root


# look.py preview harness: render the camera hints by name (plus the auto cameras via --cams)
build.preview_cameras = [(h["name"], h["location"], h["target"], h["lens"]) for h in CAMERA_HINTS]
