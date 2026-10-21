"""Mission Hall 任务殿 (site section 'experience').

Blocking for the AI video pass: a broad white-marble plaza, the mission wall on the axis with
7 large white-jade role boards (the 7 roles of the experience timeline, each lettered with its employer;
see _role_boards) and small wooden tablets in its lower corners, a grand double-eave hall (teal
xieshan roofs) on a tall terrace behind it, a bell tower
(east, +X) and a drum tower (west, -X) flanking the plaza, raised side galleries joining each
tower to the hall terrace, stone lanterns and pines. Front (entry, camera approach) faces -Y;
z = 0 is the plaza top.

Route (architecture audit 1.5 and 4): the stepping stones from the arena land on a railed
arrival landing in front of the plaza (y -58 to -44, on the axis). A white axis walk runs from
it to a 22 m stair onto the mission wall's base, splits round the wall on paved aprons and side
strips, and continues to the terrace stair and the hall doors. Each tower has its front stair
and a gallery at terrace height to the terrace. The way out to the library is a side gate in
the east railing at y -15 to -9, a paved spur along y -12 and a landing whose steps end at the
declared depart point.

Holy-fire altars 圣火坛 (the Ming Sect of Heaven Sword and Dragon Saber worships the holy fire): a symmetric pair on the
open paving east and west of the mission wall (HOLY_FIRE), each a Sasanian hourglass fire altar in bronze on an
octagonal stone plinth with a burning flame crown and a warm point light; see _holy_fire().
"""
import math
import os
import zlib

import bmesh
import bpy
from mathutils import Matrix, Vector

from sect.lib import util as U
from sect.lib import arch as A
from sect.lib import props as P
from sect.lib import nature as N
from sect.lib import materials as MAT

# arrival / depart: (x, y, z, heading) in the local frame, where world.py's connectors land / start
# (architecture audit 1.5 and W1). z is the landing top the first / last step sits flush with;
# heading is the direction of travel in radians from +x (pi/2 = +y).
AREA = dict(key="mission", section_id="experience", title_en="Mission Hall",
            title_zh="任务殿", footprint=50.0,
            arrival=(0.0, -58.0, 0.0, math.pi / 2),    # front edge of the arrival landing, on the axis, heading +y
            depart=(54.0, -12.0, -0.4, 0.0))           # foot of the depart landing's east steps, heading +x

K = AREA["key"]

# ---------------------------------------------------------------- layout (local metres)
PLAZA = [(-21, -44), (21, -44), (38, -30), (38, 28), (24, 43), (-24, 43), (-38, 28), (-38, -30)]
RAIL_INSET = 0.6          # plaza / landing balustrades sit this far inside the slab edge
WALL_Y = -30.0            # mission wall centre line (moved forward so the terrace and stairs show)
WALL_W = 26.0             # mission wall frame width
WALL_BASE_H = 1.0
WALL_BASE_D = 4.0
WALL_TOP = 8.4            # top of the frieze (the small roof sits on it)
WALL_STAIR_W = 22.0       # stair up onto the wall base, on its front
TABLET_HANG = 7.0         # the wall's beam has its underside at TABLET_HANG + 0.25 (arch.beam takes its bottom line)
WOOD_RAILS = (3.3, 2.15)  # z of the two small-tablet rails (in the wall's lower corners, beside the lower role row)

# ---------------------------------------------------------------- role boards (the 7 roles)
# One white-jade board per job in the owner's EXPERIENCE list (client/src/lib/portfolio-data/experience.ts), in
# that order: hotspot role:i is the instancer 'mission.role_tablet' + ('' | '.00i') (export_web.build_hotspot_defs),
# and the client labels it '<role> · <company>' from the same list. Each board says its employer in large dark
# serif letters (readable at the 619 hold: the wall stands 43 m from the camera, ~35 px a metre on a 1600 x 900
# screen, the capitals come out ~15 px tall) over a red line with the years, flanked by a cinnabar sun disc in a
# gold ring and a gold crescent moon (日 + 月 = 明, the sect's name; silver vanished on the pale jade). The face
# does not glow (the old jade_glow body and cyan halos washed the text out under the bloom); only a thin gold rim
# line glows, which the client's idle wave runs along (idle.ts GLOWS.mission).
ROLE_BOARDS = (
    ("Pinterest", "2026 \u2013 Now"),
    ("Scale AI", "2025 \u2013 2026"),
    ("RingCentral", "2023 \u2013 2025"),
    ("Dispatch AI", "2024"),
    ("SlugLoop", "2023 \u2013 2024"),
    ("X-Camp", "2022 \u2013 2023"),
    ("Hackathons", "36 wins"),
)
ROLE_W, ROLE_H, ROLE_T = 5.2, 2.2, 0.14     # board width, height, thickness (m)
ROLE_PITCH = 5.8                             # centre spacing in a row
RAIL_Z = 4.4                                 # axis of the lower row's rail (0.12 square, post to post)
ROLE_ROWS = ((4, TABLET_HANG + 0.25), (3, RAIL_Z - 0.06))   # (boards, suspension z: the beam's underside, the rail's)
ROLE_Y = -0.3                                # board centre plane (under the beam axis; the board face is y +0.2)
ROLE_CORD = 0.40                             # cord from the suspension point down to the board's top edge
ROLE_CORD_X = ROLE_W / 2 - 0.55              # the two cords' x on the board
ROLE_NOTCH = 0.16                            # concave quarter-round corners (wei jiao)
ROLE_FRAME = (0.05, 0.13, 0.012)             # gold frame: outer inset, inner inset, height above the face
ROLE_RIM = (0.165, 0.19, 0.004)              # glowing rim line: outer inset, inner inset, height above the face
ROLE_RIM_GLOW = 0.6                          # obj['glow'] on the rim (rune_gold strength x this in Cycles)
ROLE_TEXT_W = 4.3                            # the longest employer name spans this (one size for all seven)
ROLE_YEAR_CAP = 0.28                         # cap height of the years line
ROLE_LINE_GAP = 0.36                         # employer baseline -> years cap line
ROLE_RELIEF = 0.008                          # letter relief above the face
# Georgia Bold: a large x-height drawn for small sizes on screens. Palatino Bold for the years: lining figures
# (Georgia's are old-style). On the render box both are copied to the font mirror /C:/Windows/Fonts/.
ROLE_FONT = "C:/Windows/Fonts/georgiab.ttf"
ROLE_FONT_YEARS = "C:/Windows/Fonts/palab.ttf"
ROLE_JADE = MAT.variant("mission_jade_white", "jade", deep="#a3bd9f", pale="#e9f0dc", sss=0.35, veins=0.1)
ROLE_REV = 2                                 # bump when the board design changes (part of the prototype key)
RAIL_Y = -0.3                                # the lower row's rail (same plane as the boards)
RAIL_BRACKETS = (-8.6, -2.9, 2.9, 8.6)       # x of its brackets (between the lower boards and at their ends)
WOOD_X = (8.75, 11.45)                       # |x| span of the small wooden tablets in each lower corner
WOOD_PITCH = 0.385
TERRACE_H = 3.0           # tall terrace under the hall (the hall adds its own 2 m xumizuo)
TERRACE_BACK = 41.5       # y of the terrace's back edge
HALL_PLAT_H = 2.0
TERRACE_MARGIN = 7.0     # terrace width = hall platform width + this
TOWER_X, TOWER_Y = 25.0, -1.0
TOWER_SIZE = 10.0
CORRIDOR_X = 33.5
GALLERY_Y = 22.0          # where each gallery meets the terrace side
TOWER_RAIL_GAP = (-2.0, 2.0)      # opening in each tower's outer railing (plaza y), for the gallery
TERRACE_RAIL_GAP = (20.4, 23.6)   # opening in the terrace side railings, for the gallery
# arrival landing (stepping stones from the arena land on its front, at x 0)
ARR_X = 10.0
ARR_Y0, ARR_Y1 = -58.0, -44.0
ARR_GAP = 3.0             # half-width of the front opening where the last stone touches
# paved aprons round the mission wall
APRON_X = 17.0
APRON_D = 4.0
STRIP_X, STRIP_W = 16.0, 4.0
# side gate to the library (east railing) and its spur
GATE_Y0, GATE_Y1 = -15.0, -9.0
SPUR_Y, SPUR_W = -12.0, 5.0
LAND_X0, LAND_X1 = 49.0, 53.0     # landing at the spur's end; its steps end at depart x = 54

CAMERA_HINTS = [
    dict(name="approach", location=(0, -105, 24), target=(0, -6, 10), lens=30),
    dict(name="wall", location=(0, -58, 7.5), target=(0, -30, 5.5), lens=28),
    dict(name="rise", location=(0, -30, 31), target=(0, 26, 13), lens=26),
    dict(name="over_hall", location=(-8, 2, 36), target=(0, 34, 20), lens=22),
]


# ---------------------------------------------------------------- small helpers
def _fix_font_paths():
    """Cloud-box workaround: on Linux the lib's 'C:/Windows/Fonts/...' path passes os.path.exists
    (it resolves against cwd '/' to the font mirror) but bpy.data.fonts.load rejects it. Hand the lib
    the absolute mirror path instead. No-op on Windows or when the path is already absolute."""
    if os.name == "nt":
        return
    for attr in ("FONT_KAITI", "FONT_YAHEI"):
        p = getattr(U, attr, None)
        if p and not os.path.isabs(p) and os.path.exists(p):
            setattr(U, attr, os.path.abspath(p))


def _box_obj(name, size, center, coll, mat, parent):
    bm = bmesh.new()
    U.bm_box(bm, size, center)
    return U.mesh_from_bmesh(U.name(K, name), bm, coll, materials=[mat], smooth=False, parent=parent)


def _walk(name, x0, x1, y0, y1, coll, root):
    """Raised white marble route strip (top 0.08) over the paving, like the axis walk."""
    return _box_obj(name, (x1 - x0, y1 - y0, 0.1), ((x0 + x1) / 2, (y0 + y1) / 2, 0.03), coll,
                    "marble_white", root)


def _poly_slab(name, pts, z0, z1, coll, top_mat, side_mat, parent):
    """Prism over a convex polygon, top face subdivided into strips (no sliver fans)."""
    bm = bmesh.new()
    n = len(pts)
    bot = [bm.verts.new((x, y, z0)) for x, y in pts]
    top = [bm.verts.new((x, y, z1)) for x, y in pts]
    for k in range(n):
        f = bm.faces.new((bot[k], bot[(k + 1) % n], top[(k + 1) % n], top[k]))
        f.material_index = 1
    fb = bm.faces.new(list(reversed(bot)))
    fb.material_index = 1
    ft = bm.faces.new(top)
    ft.material_index = 0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # cut the top into ~4 m strips both ways so the paving bump never sees long slivers
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    for axis, lo, hi in ((0, min(xs), max(xs)), (1, min(ys), max(ys))):
        v = lo + 4.0
        while v < hi - 0.5:
            no = (1, 0, 0) if axis == 0 else (0, 1, 0)
            co = (v, 0, 0) if axis == 0 else (0, v, 0)
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no)
            v += 4.0
    return U.mesh_from_bmesh(U.name(K, name), bm, coll, materials=[top_mat, side_mat], smooth=False,
                             parent=parent)


def _rect_slab(name, x0, x1, y0, y1, z0, z1, coll, root):
    return _poly_slab(name, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1, coll, "marble_paving",
                      "marble_white", root)


def _inset_poly(pts, d):
    """Inset a convex CCW polygon by d (simple vertex offset along the bisector)."""
    out = []
    n = len(pts)
    for k in range(n):
        p = Vector(pts[k])
        a = (p - Vector(pts[k - 1])).normalized()
        b = (Vector(pts[(k + 1) % n]) - p).normalized()
        na = Vector((-a.y, a.x))
        nb = Vector((-b.y, b.x))
        bis = (na + nb).normalized()
        s = d / max(0.2, bis.dot(na))
        q = p + bis * s
        out.append((q.x, q.y))
    return out


# ---------------------------------------------------------------- parts
def _plaza(coll, root, axis_end, wall_stair_foot):
    """Plaza slab, the white route on the axis (split round the mission wall) and the perimeter
    balustrade, open at the front (arrival landing) and at the east side gate."""
    _poly_slab("plaza", PLAZA, -0.6, 0.0, coll, "marble_paving", "marble_white", root)
    # imperial axis walk (shendao) from the arrival landing's front edge to the wall's apron ...
    apron_front = wall_stair_foot - APRON_D
    _walk("axis", -3.5, 3.5, ARR_Y0, apron_front, coll, root)
    # ... paved aprons in front of the wall stair and behind the wall, side strips round its ends ...
    wall_back = WALL_Y + WALL_BASE_D / 2
    _walk("apron_front", -APRON_X, APRON_X, apron_front, wall_stair_foot, coll, root)
    _walk("apron_back", -APRON_X, APRON_X, wall_back, wall_back + APRON_D, coll, root)
    for sx in (-1, 1):
        x0, x1 = sorted((sx * (STRIP_X - STRIP_W / 2), sx * (STRIP_X + STRIP_W / 2)))
        _walk("wall_strip", x0, x1, wall_stair_foot, wall_back, coll, root)
    # ... and on from the back apron to the foot of the terrace stair
    _walk("axis", -3.5, 3.5, wall_back + APRON_D, axis_end, coll, root)
    # perimeter balustrade: open across the arrival landing (x +-ARR_X inset) and at the side gate
    ring = _inset_poly(PLAZA, RAIL_INSET)
    y0 = ring[0][1]
    gx = ARR_X - RAIL_INSET
    xe = ring[2][0]                       # inset east edge (x 37.4)
    east = [(gx, y0, 0.0)] + [(x, y, 0.0) for x, y in ring[1:3]] + [(xe, GATE_Y0, 0.0)]
    rest = ([(xe, GATE_Y1, 0.0)] + [(x, y, 0.0) for x, y in ring[3:]] +
            [(ring[0][0], y0, 0.0), (-gx, y0, 0.0)])
    A.balustrade(U.name(K, "plaza_rail"), coll, east, height=1.05, post_spacing=2.2, no_post="end", parent=root)
    A.balustrade(U.name(K, "plaza_rail"), coll, rest, height=1.05, post_spacing=2.2, no_post="start",
                 parent=root)


def _arrival(coll, root):
    """Arrival landing in front of the plaza, where the stepping stones from the arena land
    (audit 1.5 item 1): marble paving flush with the plaza, railed on its sides and front with a
    6 m opening on the axis. Its side rails turn into the plaza's front rail."""
    _rect_slab("arrival", -ARR_X, ARR_X, ARR_Y0, ARR_Y1, -1.0, 0.0, coll, root)
    xi, yf, yb = ARR_X - RAIL_INSET, ARR_Y0 + RAIL_INSET, ARR_Y1 + RAIL_INSET
    for sx in (-1, 1):
        A.balustrade(U.name(K, "arrival_rail"), coll,
                     [(sx * ARR_GAP, yf, 0.0), (sx * xi, yf, 0.0), (sx * xi, yb, 0.0)],
                     height=1.05, post_spacing=2.2, end_drum="start", no_post="end", parent=root)


def _side_gate(coll, root):
    """Way out to the library (audit 1.5 item 2): a one-bay gate in the east railing, a 5 m paved
    spur along y -12 and a landing with three steps down its east edge to the stair head."""
    xe = PLAZA[2][0] - RAIL_INSET
    gw = GATE_Y1 - GATE_Y0
    # one-bay gate whose columns stand on the railing ends (column span = gw), front to the plaza
    A.paifang(U.name(K, "side_gate"), coll, bays=1, width=gw + 1.6, height=6.5, parent=root,
              location=(xe, (GATE_Y0 + GATE_Y1) / 2, 0.0), rotation_z=-math.pi / 2)
    x_edge = PLAZA[2][0]
    _rect_slab("side_walk", x_edge, LAND_X0, SPUR_Y - SPUR_W / 2, SPUR_Y + SPUR_W / 2, -0.6, 0.0, coll, root)
    _rect_slab("depart_landing", LAND_X0, LAND_X1, GATE_Y0, GATE_Y1, -0.6, 0.0, coll, root)
    st = A.stairs(U.name(K, "depart_steps"), coll, SPUR_W, 0.4, ramp=False, balustrade=False, parent=root,
                  location=(LAND_X1, SPUR_Y, -0.4), rotation_z=math.pi / 2)
    return LAND_X1 + st["arch_run"]


# ---------------------------------------------------------------- role boards
def _font_path(path):
    """Absolute font path (on the Linux box 'C:/...' resolves against cwd '/' to the font mirror). Raises when the
    file is missing: a silent fallback to YaHei would letter the boards in the wrong face."""
    p = path if os.name == "nt" else os.path.abspath(path)
    if not os.path.exists(p):
        raise RuntimeError("font %s not found (on the render box copy it to /C:/Windows/Fonts/)" % path)
    return p


def _line_mesh(body, font):
    """Mesh (cached) of one line of text at size 1 in ``font``, extruded +-0.5, lying in XY (readable from +Z),
    centred on x with its baseline on y = 0."""
    sig = "%s|%s|v1" % (body, os.path.basename(font))
    key = "mission.txt.%08x" % (zlib.crc32(sig.encode("utf-8")) & 0xFFFFFFFF)
    me = bpy.data.meshes.get(key)
    if me is not None and me.get("mission_txt") == sig and len(me.vertices):
        return me
    cu = bpy.data.curves.new("mission_tmp_text", 'FONT')
    cu.body = body
    cu.font = bpy.data.fonts.load(_font_path(font), check_existing=True)
    cu.size = 1.0
    cu.resolution_u = 5
    cu.extrude = 0.5
    cu.align_x = 'CENTER'
    cu.align_y = 'BOTTOM_BASELINE'
    ob = bpy.data.objects.new("mission_tmp_text", cu)
    me = P._evaluate_temp(ob)
    bpy.data.curves.remove(cu)
    if me.name != key:
        old = bpy.data.meshes.get(key)
        if old is not None and old is not me and old.users == 0:
            bpy.data.meshes.remove(old)
        me.name = key
    me["mission_txt"] = sig
    return me


def _mesh_box2(me):
    """(x0, x1, y0, y1) of a text mesh."""
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    return min(xs), max(xs), min(ys), max(ys)


def role_text_scale():
    """Size (m per unit font size) that fits the widest employer name to ROLE_TEXT_W; the same for all seven."""
    widest = max(_mesh_box2(_line_mesh(lab, ROLE_FONT))[1] - _mesh_box2(_line_mesh(lab, ROLE_FONT))[0]
                 for lab, _ in ROLE_BOARDS)
    return ROLE_TEXT_W / widest


def _notched(w, h, z_top, r, d, n=5):
    """Outline (x, z) of a w x h board (top at z_top) with concave quarter-round corners of radius r, inset by d:
    BR, TR, TL, BL corners in turn, n + 1 points each (the same count at every inset, so loops pair up)."""
    R = r + d
    f0 = math.asin(min(1.0, d / R))
    pts = []
    for sx, sz, first_h in ((1, -1, True), (1, 1, False), (-1, 1, True), (-1, -1, False)):
        cx, cz = sx * w / 2, (z_top if sz > 0 else z_top - h)
        for k in range(n + 1):
            t = k / n
            phi = f0 + (math.pi / 2 - 2 * f0) * (t if first_h else 1.0 - t)
            pts.append((cx - sx * R * math.cos(phi), cz - sz * R * math.sin(phi)))
    return pts


def _ring_prism(bm, outer, inner, y0, y1, mat=0):
    """Closed band between two paired outlines (x, z), from y0 (front) to y1 (back)."""
    n = len(outer)
    fo = [bm.verts.new((x, y0, z)) for x, z in outer]
    bo = [bm.verts.new((x, y1, z)) for x, z in outer]
    fi = [bm.verts.new((x, y0, z)) for x, z in inner]
    bi = [bm.verts.new((x, y1, z)) for x, z in inner]
    for i in range(n):
        j = (i + 1) % n
        for q in ((fo[i], fo[j], fi[j], fi[i]), (bo[j], bo[i], bi[i], bi[j]), (fo[j], fo[i], bo[i], bo[j]),
                  (fi[i], fi[j], bi[j], bi[i])):
            bm.faces.new(q).material_index = mat
    return fo + bo + fi + bi


def _disc_pts(cx, cz, r, n=24, a0=0.0, a1=2 * math.pi):
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cz + r * math.sin(a0 + (a1 - a0) * k / n))
            for k in range(n + (0 if abs(a1 - a0 - 2 * math.pi) < 1e-9 else 1))]


def _crescent_pts(cx, cz, r, n=16):
    """Crescent moon (horns to the right, away from the years), outer radius r: the outer arc over the left side and
    the arc of a circle shifted right."""
    ri, off = 0.78 * r, 0.42 * r
    # outer arc on the right from the top horn to the bottom horn; horns where the two circles cross
    xh = (r * r - ri * ri + off * off) / (2 * off)
    zh = math.sqrt(max(r * r - xh * xh, 1e-9))
    a_top = math.atan2(zh, xh)
    outer = [(cx + r * math.cos(a), cz + r * math.sin(a))
             for a in [a_top + (2 * math.pi - 2 * a_top) * k / n for k in range(n + 1)]]
    b_bot = math.atan2(-zh, xh - off)
    b_top = math.atan2(zh, xh - off)
    inner = [(cx + off + ri * math.cos(b), cz + ri * math.sin(b))
             for b in [b_bot - (b_bot + 2 * math.pi - b_top) * k / n for k in range(1, n)]]
    return outer + inner


def _flat_prism(bm, outline, y_face, h, mat=0):
    """Raised plate of ``outline`` (x, z) from 3 mm inside the face at y_face up to h above it (toward -y)."""
    return P._prism(bm, outline, h + 0.003, y0=y_face - h, mat=mat)


def _role_build(pc, label, years, scale):
    """Prototype of one role board: origin = the suspension point (beam or rail underside), the board hangs below
    it on two cords; front faces -Y."""
    W, H, T = ROLE_W, ROLE_H, ROLE_T
    z_top = -ROLE_CORD
    yf = -T / 2                                         # front face
    # white jade body, concave corners, bevelled edges
    bm = bmesh.new()
    P._prism(bm, _notched(W, H, z_top, ROLE_NOTCH, 0.0), T, y0=yf)
    P._outward(bm)
    P._mk(P._nm("role.board"), bm, pc, [ROLE_JADE], smooth=False, bevel=0.015)
    # gold: raised frame on the front, cord eyes on the top edge, hook plates at the suspension point, the sun's ring
    # and the crescent moon; cinnabar (slot 1): the sun disc
    o, i_, fh = ROLE_FRAME
    bm = bmesh.new()
    _ring_prism(bm, _notched(W, H, z_top, ROLE_NOTCH, o), _notched(W, H, z_top, ROLE_NOTCH, i_), yf - fh, yf + 0.003)
    for sx in (-1, 1):
        x = sx * ROLE_CORD_X
        P._torus(bm, 0.055, 0.016, 16, 6, matrix=Matrix.Translation((x, 0.0, z_top + 0.02)) @ P.ROT_XZ)
        P._box(bm, (0.16, 0.16, 0.025), (x, 0.0, -0.0125))
    # lettering: employer (ink) and years (cinnabar, slot 1)
    me1 = _line_mesh(label, ROLE_FONT)
    me2 = _line_mesh(years, ROLE_FONT_YEARS)
    me_h = _line_mesh("H", ROLE_FONT)
    me_h2 = _line_mesh("H", ROLE_FONT_YEARS)
    cap1 = _mesh_box2(me_h)[3] * scale
    s2 = ROLE_YEAR_CAP / _mesh_box2(me_h2)[3]
    block = cap1 + ROLE_LINE_GAP + ROLE_YEAR_CAP
    zc = z_top - H / 2
    base1 = zc + block / 2 - cap1
    base2 = base1 - ROLE_LINE_GAP - ROLE_YEAR_CAP
    bt = bmesh.new()
    rot = Matrix.Rotation(math.pi / 2, 4, 'X')          # XY text (normal +Z) -> XZ plane facing -Y
    for me, s, base, mat in ((me1, scale, base1, 0), (me2, s2, base2, 1)):
        m = Matrix.Translation((0.0, yf - ROLE_RELIEF / 2 + 0.0015, base)) @ rot @ \
            Matrix.Diagonal((s, s, ROLE_RELIEF + 0.003, 1.0))
        P._add_mesh(bt, me, m, mat)
    # sun (left) and moon (right) flanking the years: 日 + 月 = 明
    x0, x1, _, _ = _mesh_box2(me2)
    half = 0.5 * (x1 - x0) * s2
    rz = base2 + ROLE_YEAR_CAP / 2
    rr = 0.6 * ROLE_YEAR_CAP
    _flat_prism(bm, _disc_pts(-half - 0.3, rz, rr), yf, 0.010, mat=1)
    _ring_prism(bm, _disc_pts(-half - 0.3, rz, rr * 1.55), _disc_pts(-half - 0.3, rz, rr * 1.32), yf - 0.008,
                yf + 0.003)
    _flat_prism(bm, _crescent_pts(half + 0.3, rz, rr * 1.4), yf, 0.012)
    P._outward(bm)
    P._mk(P._nm("role.gold"), bm, pc, ["gold", "lacquer_red"], smooth=False)
    P._mk(P._nm("role.glyphs"), bt, pc, ["ink", "lacquer_red"], smooth=False)
    # thin glowing rim line inside the frame (the only glow on the board)
    o, i_, rh = ROLE_RIM
    bm = bmesh.new()
    _ring_prism(bm, _notched(W, H, z_top, ROLE_NOTCH, o), _notched(W, H, z_top, ROLE_NOTCH, i_), yf - rh, yf + 0.002)
    P._outward(bm)
    g = P._mk(P._nm("role.glyph_rim"), bm, pc, ["rune_gold"], smooth=False, glow=ROLE_RIM_GLOW)
    U.set_visibility(g, shadow=False)
    # red cords from the hook plates to the eyes
    bm = bmesh.new()
    for sx in (-1, 1):
        x = sx * ROLE_CORD_X
        P._tube(bm, [(x, 0.0, -0.02), (x, 0.0, z_top + 0.06)], 0.018, 6, 1, smooth_path=False)
    P._mk(P._nm("role.cord"), bm, pc, ["cloth_red"], smooth=True)


def role_proto(i, scale=None):
    """Prototype collection of role board i (built once per text and layout)."""
    label, years = ROLE_BOARDS[i]
    scale = role_text_scale() if scale is None else scale
    sig = "%s|%s|%.4f|%r|%r|%r|%r|%r|%r|%r|%r|%s|%s|%d" % (
        label, years, scale, (ROLE_W, ROLE_H, ROLE_T), ROLE_CORD, ROLE_CORD_X, ROLE_NOTCH, ROLE_FRAME, ROLE_RIM,
        ROLE_RIM_GLOW, (ROLE_YEAR_CAP, ROLE_LINE_GAP, ROLE_RELIEF), ROLE_FONT, ROLE_FONT_YEARS, ROLE_REV)
    key = "mission.role.%08x" % (zlib.crc32(sig.encode("utf-8")) & 0xFFFFFFFF)
    return P._proto(key, lambda pc: _role_build(pc, label, years, scale))


def role_slots():
    """[(i, x, z)]: role i's suspension point in the wall's frame (rows left to right, top row first)."""
    out, i = [], 0
    for n, z in ROLE_ROWS:
        for k in range(n):
            out.append((i, (k - (n - 1) / 2) * ROLE_PITCH, z))
            i += 1
    return out


def _role_boards(coll, wall):
    """The 7 role boards on the wall: Empties 'mission.role_tablet[.00i]' instancing role_proto(i)."""
    scale = role_text_scale()
    out = []
    for i, x, z in role_slots():
        out.append(U.collection_instance(role_proto(i, scale), U.name(K, "role_tablet"), coll,
                                         location=(x, ROLE_Y, z), parent=wall, display_size=0.5))
    return out


def wood_proto(coll, wall):
    """The small wooden tablet (also the first one on the west corner's upper rail)."""
    bm = bmesh.new()
    U.bm_box(bm, (0.26, 0.04, 0.58), (0, 0, -0.18 - 0.29))
    U.bm_box(bm, (0.018, 0.018, 0.2), (0, 0, -0.09))
    U.bm_box(bm, (0.05, 0.03, 0.22), (0, 0, -0.18 - 0.58 - 0.11))
    for f in bm.faces:
        f.material_index = 0 if abs(f.calc_center_median().z + 0.47) < 0.3 else 1
    return U.mesh_from_bmesh(U.name(K, "wood_tablet"), bm, coll, materials=["wood_light", "cloth_red"],
                             smooth=False, parent=wall, location=(-WOOD_X[1], -0.12, WOOD_RAILS[0]))


def _wall_rails(coll, wall, board_front=0.2):
    """The lower role row's rail (post to post, bracketed back to the board) and, in each lower corner, two short
    rails (from the post to a bracket) hung with small wooden tablets. Returns the wooden tablet count."""
    post_in = WALL_W / 2 - 0.55                         # rails end inside the posts (r 0.42 at x +-12.5)
    _box_obj("wall.board_rail", (2 * post_in, 0.12, 0.12), (0, RAIL_Y, RAIL_Z), coll, "lacquer_red", wall)
    for x in RAIL_BRACKETS:
        d = board_front - (RAIL_Y - 0.06) + 0.02
        _box_obj("wall.bracket", (0.1, d, 0.1), (x, RAIL_Y - 0.06 + d / 2, RAIL_Z), coll, "gold", wall)
    proto = wood_proto(coll, wall)
    r = U.rng(K, "wood_tablets")
    count = 1
    n = int(round((WOOD_X[1] - WOOD_X[0]) / WOOD_PITCH)) + 1
    for sx in (-1, 1):
        x_in, x_out = sx * (WOOD_X[0] - 0.15), sx * post_in
        for row, z in enumerate(WOOD_RAILS):
            _box_obj("wall.rail", (abs(x_out - x_in), 0.08, 0.08), ((x_in + x_out) / 2, -0.12, z + 0.02), coll,
                     "lacquer_red", wall)
            d = board_front - (-0.16) + 0.02
            _box_obj("wall.bracket", (0.08, d, 0.08), (x_in, -0.16 + d / 2, z + 0.02), coll, "gold", wall)
            for k in range(n):
                x = sx * (WOOD_X[1] - k * WOOD_PITCH)
                if sx < 0 and row == 0 and k == 0:
                    continue                            # the prototype itself hangs there
                if r.random() < 0.12:
                    continue
                U.instance(proto, U.name(K, "wood_tablet"), coll, location=(x, -0.12, z),
                           rotation=(0, 0, r.uniform(-0.12, 0.12)), parent=wall)
                count += 1
    return count


def _mission_wall(coll, root):
    """The focal point: a tall carved frame on a marble base, dark board, 7 white-jade role boards on red cords
    (two rows: four under the beam, three on a rail), small wooden tablets in the lower corners, small teal roof
    on top, and a broad stair up onto the base. Returns (wall Empty, y of the wall stair's foot)."""
    wall = U.empty(U.name(K, "wall"), coll, location=(0, WALL_Y, 0), parent=root, display_size=2.0)
    base_h = WALL_BASE_H
    A.platform(U.name(K, "wall.base"), coll, WALL_W + 2.0, WALL_BASE_D, base_h, parent=wall)
    ws = A.stairs(U.name(K, "wall.stairs"), coll, WALL_STAIR_W, base_h, ramp=False, balustrade=False,
                  parent=wall, location=(0.0, -WALL_BASE_D / 2, 0.0))
    stair_foot = WALL_Y - WALL_BASE_D / 2 - ws["arch_run"]
    # red posts at both ends
    for x in (-WALL_W / 2 + 0.5, WALL_W / 2 - 0.5):
        A.column(U.name(K, "wall.post"), coll, WALL_TOP - base_h, 0.42, parent=wall,
                 location=(x, 0.0, base_h))
    # dark board behind the tablets
    bw = WALL_W - 2.2
    _box_obj("wall.board", (bw, 0.5, WALL_TOP - base_h - 0.9), (0, 0.45, base_h + (WALL_TOP - base_h - 0.9) / 2),
             coll, "lacquer_black", wall)
    # gold border on the board face
    for cx, cz, sx, sz in ((0, base_h + 0.08, bw, 0.16), (0, WALL_TOP - 0.98, bw, 0.16),
                           (-bw / 2 + 0.08, (base_h + WALL_TOP - 0.9) / 2, 0.16, WALL_TOP - base_h - 0.9),
                           (bw / 2 - 0.08, (base_h + WALL_TOP - 0.9) / 2, 0.16, WALL_TOP - base_h - 0.9)):
        _box_obj("wall.trim", (sx, 0.08, sz), (cx, 0.17, cz), coll, "gold", wall)
    # top beam (painted) from which the tablets hang, and a red frieze above it
    A.beam(U.name(K, "wall.beam"), coll, (-WALL_W / 2, -0.25, TABLET_HANG + 0.25),
           (WALL_W / 2, -0.25, TABLET_HANG + 0.25), width=0.55, height=0.6, mat="arch_beam_paint", parent=wall)
    _box_obj("wall.frieze", (WALL_W + 0.2, 1.1, WALL_TOP - TABLET_HANG - 0.55),
             (0, 0.25, (TABLET_HANG + 0.55 + WALL_TOP) / 2), coll, "arch_paint_red", wall)
    # small hip roof capping the wall
    A.roof(U.name(K, "wall.roof"), coll, WALL_W + 0.4, 1.4, "wudian", tile_mat="roof_tile_teal",
           overhang=1.3, detail="low", parent=wall, location=(0, 0.25, WALL_TOP))
    # plaque hung in front of the beam, above the centre tablet
    P.plaque(coll, "任务榜", 3.0, name=U.name(K, "wall.plaque"), parent=wall,
             location=(0, -0.85, TABLET_HANG + 0.45), tilt=math.radians(4))

    # 7 white-jade role boards (the roles; hotspots role:0..6), four under the beam and three on the rail
    _role_boards(coll, wall)
    # the lower row's rail and the small wooden tablets in the two lower corners
    wall["wood_tablets"] = _wall_rails(coll, wall, board_front=0.45 - 0.25)
    return wall, stair_foot


def _hall(coll, root):
    """Double-eave hall on its own xumizuo, standing on a tall terrace with grand ramped stairs.
    The terrace side railings open where the galleries arrive. Returns (hall root, y of the
    terrace stair foot)."""
    hall = A.hall(U.name(K, "hall"), coll, bays_w=7, bays_d=4, bay=5.0, column_h=6.5, double_eave=True,
                  platform_h=HALL_PLAT_H, lit=True, parent=root)
    Wp, Dp = hall["arch_platform"]
    st = bpy.data.objects.get(hall.name + ".stairs")
    run_h = st["arch_run"] if st is not None and "arch_run" in st.keys() else 4.0
    yh = TERRACE_BACK - 3.0 - Dp / 2
    hall.location = (0.0, yh, TERRACE_H)
    # terrace
    tw = Wp + TERRACE_MARGIN
    t_front = yh - Dp / 2 - run_h - 2.5
    td = TERRACE_BACK - t_front
    A.platform(U.name(K, "terrace"), coll, tw, td, TERRACE_H, parent=root,
               location=(0, (TERRACE_BACK + t_front) / 2, 0))
    sw = 14.0
    ts = A.stairs(U.name(K, "terrace_stairs"), coll, sw, TERRACE_H, ramp=True, balustrade=True, bal_extend=0.35,
                  parent=root, location=(0, t_front, 0))
    run_t = ts["arch_run"] if "arch_run" in ts.keys() else TERRACE_H / 0.17 * 0.33
    e = 0.35
    hw, gx = tw / 2 - e, sw / 2 - 0.25
    yf, yb = t_front + e, TERRACE_BACK - e
    g0, g1 = TERRACE_RAIL_GAP
    z = TERRACE_H
    for pts, np_ in (([(-gx, yf, z), (-hw, yf, z), (-hw, g0, z)], "start"),
                     ([(-hw, g1, z), (-hw, yb, z), (hw, yb, z), (hw, g1, z)], None),
                     ([(hw, g0, z), (hw, yf, z), (gx, yf, z)], "end")):
        A.balustrade(U.name(K, "terrace_rail"), coll, pts, height=1.0, no_post=np_, parent=root)
    # plaque 任务殿 under the upper eave
    anchor = bpy.data.objects[hall["plaque_anchor"]]
    pw = min(6.5, max(4.0, hall["plaque_size"][0] * 1.4))
    P.plaque(coll, AREA["title_zh"], pw, name=U.name(K, "plaque"), parent=anchor, location=(0, 0, 0), tilt=0.0)
    # palace lanterns under the lower eave, flanking the doors
    for sx in (-1, 1):
        P.lantern_hanging(coll, "palace", 1.2, cord=0.6, name=U.name(K, "hall_lantern"), parent=hall,
                          location=(sx * 6.5, -Dp / 2 + 2.4, HALL_PLAT_H + 6.5 - 0.2))
    return hall, t_front - run_t


def _towers(coll, root):
    """Bell (east) and drum (west) towers, their base at terrace height so the galleries run level.
    Each tower's outer railing opens at plaza y TOWER_RAIL_GAP for its gallery."""
    out = []
    for kind, sx in (("bell", 1), ("drum", -1)):
        # open the outer railing where the gallery docks (tower-local y = plaza y - TOWER_Y)
        gap = ("+x" if sx > 0 else "-x", TOWER_RAIL_GAP[0] - TOWER_Y, TOWER_RAIL_GAP[1] - TOWER_Y)
        t = A.tower(U.name(K, kind + "_tower"), coll, kind=kind, size=TOWER_SIZE, base_h=TERRACE_H, column_h=4.6,
                    parent=root, location=(sx * TOWER_X, TOWER_Y, 0), bal_gaps=(gap,))
        out.append(t)
    return out


def _corridors(coll, root, terrace_hw):
    """Raised galleries (audit 4): from each tower's outer side (x +-30), out to x +-CORRIDOR_X,
    along the plaza side and in to the terrace side (x +-terrace_hw = 23.1), floor at terrace
    height the whole way."""
    for sx in (-1, 1):
        lang = A.corridor(U.name(K, "lang"), coll,
                          [(sx * (TOWER_X + TOWER_SIZE / 2), 0.0), (sx * CORRIDOR_X, 0.0),
                           (sx * CORRIDOR_X, GALLERY_Y), (sx * terrace_hw, GALLERY_Y)],
                          width=3.2, height=3.4, bay=4.2, platform_h=TERRACE_H, parent=root)
        # arch._wall_box winds the floor box inside out (its walking top faces down), which hides the
        # gallery floor from walkcheck; recalculating outward normals is a no-op once the lib is fixed
        for ob in lang.children:
            if ".floor" in ob.name and ob.type == 'MESH':
                bm = bmesh.new()
                bm.from_mesh(ob.data)
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
                bm.to_mesh(ob.data)
                bm.free()


# ---------------------------------------------------------------- holy-fire altars 圣火坛
# The Ming Sect (明教, Heaven Sword and Dragon Saber) worships the holy fire 圣火 and came from Persia, so each altar is
# a Sasanian hourglass fire altar cast in Chinese bronze: stepped square base, chamfered octagonal shaft with a
# mid-band, inverted stepped crown with Persian stepped merlons on its corners, a round fire bowl with a gold rim, a
# glowing ember bed and a stylised flame crown. Gold flame-and-cloud relief on the mid-band and the crown.
# Everything below is plain Python geometry (no bpy) in the altar's own frame (z = 0 the plaza top), so a checker can
# build it without Blender; _holy_fire() turns it into objects.
HOLY_FIRE = ((25.0, -27.0), (-25.0, -27.0))   # Empty positions; east first, so it gets the bare names
HF_FRONT = math.radians(-28.4)   # east altar: yaw turning the flame's broad side to the 619 hold camera (local
                                 # (0.1, -73, 15.4)); the west altar is the mirror image
HF_FLAME_Z = 3.15                # flame and ember bed base (inside the bowl)
HF_FLAME_H = 1.8                 # flame height cap (the central tongue)
HF_RIM_Z = 3.30                  # top of the gold bowl rim
HF_LIGHT = dict(energy=1800.0, color=(1.0, 0.55, 0.22), soft=0.8, z=4.0, shadow=False)
HF_TRI_BUDGET = 8000             # per object (export LOD leaves pieces this small alone)
HF_PARTS = ("plinth", "altar", "relief", "coals", "flame")
# plinth (stone_grey), octagonal, (half across flats, z) bottom to top: three 0.17 m steps with 0.3 m treads and
# chamfered nosings, a 2 cm kerb round the 4.2 m top panel at z 0.51; the foot sits 6 cm into the paving
HF_PLINTH = ((3.0, -0.06), (3.0, 0.145), (2.975, 0.17), (2.7, 0.17), (2.7, 0.315), (2.675, 0.34), (2.4, 0.34),
             (2.4, 0.505), (2.375, 0.53), (2.1, 0.53), (2.1, 0.51))
# altar (bronze): (half width, z) rows of chamfered-square / octagonal sections
HF_CORNER = 0.035                # corner chamfer of the square tiers
HF_BASE = ((1.10, 0.50), (1.10, 0.68), (1.12, 0.695), (1.12, 0.715), (1.10, 0.725), (1.06, 0.76),   # 2.2 m tier
           (0.95, 0.76), (0.95, 0.93), (0.97, 0.945), (0.97, 0.965), (0.95, 0.975), (0.91, 1.01),    # 1.9 m tier
           (0.80, 1.01), (0.80, 1.18), (0.82, 1.195), (0.82, 1.215), (0.80, 1.225), (0.76, 1.26))    # 1.6 m tier
HF_OCT = 0.4                     # shaft chamfer as a fraction of the half width (main faces wider than chamfers)
HF_SHAFT = ((0.63, 1.24), (0.63, 1.30), (0.55, 1.34), (0.43, 2.58), (0.50, 2.62), (0.50, 2.68))
HF_BAND = ((0.49, 1.85), (0.545, 1.88), (0.545, 2.04), (0.47, 2.07))   # mid-band (vertical main faces)
HF_CROWN = ((0.61, 2.66), (0.65, 2.70), (0.67, 2.71), (0.67, 2.73), (0.65, 2.745), (0.65, 2.80),    # 1.3 m
            (0.785, 2.80), (0.825, 2.84), (0.845, 2.85), (0.845, 2.87), (0.825, 2.885), (0.825, 2.96),  # 1.65 m
            (0.96, 2.96), (1.0, 3.0), (1.0, 3.13), (0.97, 3.16))                                    # 2.0 m tier
HF_CROWN_TOP = 13                # HF_CROWN row of the top tier's flat face (the flame frieze)
HF_MERLON = ((0.13, 3.14), (0.13, 3.22), (0.09, 3.22), (0.09, 3.29), (0.05, 3.29), (0.05, 3.36))
HF_MERLON_XY = 0.84
HF_BOWL = ((0.0, 3.15), (0.86, 3.15), (0.93, 3.22), (0.955, 3.26), (0.90, 3.29), (0.84, 3.235), (0.0, 3.20))
HF_BOWL_SEGS = 32
HF_RIM = (0.925, 0.042, HF_RIM_Z - 0.042, 32, 6)    # gold rim torus: ring radius, tube radius, z, segments, sides
HF_RELIEF = (0.02, 0.004)        # relief: raised above the face, sunk into it
HF_KNOT = (0.475, 2.44, 2.52)    # gold tie round the top of the shaft (half width, z0, z1)
# Sasanian ribbons (the fillets tied to the altars on Sasanian coins), cast and gilt: a pair hangs on each side face
# (+-x, the silhouette edges from the hold) and flutters out past the mid-band. (x, y, z) for the +x side, y sway.
HF_RIBBON = ((0.475, 0.03, 2.48), (0.51, 0.04, 2.30), (0.59, 0.07, 2.12), (0.655, 0.11, 1.96),
             (0.715, 0.15, 1.80), (0.79, 0.17, 1.70), (0.84, 0.165, 1.66))      # +y tail; the -y tail mirrors it
HF_RIBBON_W = (0.10, 0.016, 70.0)   # width, thickness, twist along the tail (deg)
HF_COALS = ((0.80, 3.15), (0.80, 3.21), (0.66, 3.29), (0.44, 3.36), (0.20, 3.41), (0.0, 3.43))


def _hf_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _hf_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _hf_mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _hf_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _hf_cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _hf_unit(a):
    n = math.sqrt(_hf_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else (0.0, 0.0, 1.0)


def _hf_spin(v, k, ang):
    """Rotate v about the unit axis k by ang (Rodrigues)."""
    c, s = math.cos(ang), math.sin(ang)
    return _hf_add(_hf_add(_hf_mul(v, c), _hf_mul(_hf_cross(k, v), s)), _hf_mul(k, _hf_dot(k, v) * (1.0 - c)))


def _hf_spline(ctrl, per):
    """Catmull-Rom through the control points, ``per`` samples per span, both ends kept."""
    n, out = len(ctrl), []
    for i in range(n - 1):
        p0, p1, p2, p3 = ctrl[max(i - 1, 0)], ctrl[i], ctrl[i + 1], ctrl[min(i + 2, n - 1)]
        for s in range(per):
            t = s / per
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * b + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (3 * b - a - 3 * c + d) * t3)
                             for a, b, c, d in zip(p0, p1, p2, p3)))
    out.append(tuple(ctrl[-1]))
    return out


class _HFGeo:
    """Plain-Python mesh: vertices, polygons, a material slot and an edge-wear value ('edge' face attribute, read by
    the metals and lightened by the bake) per polygon. Every part is a closed solid; end() turns it outward by its
    signed volume."""

    def __init__(self):
        self.verts, self.faces, self.mat, self.edge = [], [], [], []
        self._f0 = 0

    def v(self, p):
        self.verts.append((float(p[0]), float(p[1]), float(p[2])))
        return len(self.verts) - 1

    def f(self, idx, mat=0, edge=0.0):
        self.faces.append(tuple(idx))
        self.mat.append(int(mat))
        self.edge.append(float(edge))

    def begin(self):
        self._f0 = len(self.faces)

    def end(self):
        if self.volume(self._f0, len(self.faces)) < 0.0:
            for i in range(self._f0, len(self.faces)):
                self.faces[i] = tuple(reversed(self.faces[i]))

    def volume(self, f0=0, f1=None):
        V, vol = self.verts, 0.0
        for fc in self.faces[f0:len(self.faces) if f1 is None else f1]:
            a = V[fc[0]]
            for k in range(1, len(fc) - 1):
                vol += _hf_dot(a, _hf_cross(V[fc[k]], V[fc[k + 1]]))
        return vol / 6.0

    def tris(self):
        return sum(len(fc) - 2 for fc in self.faces)

    def loft(self, rings, mat=0, edge=0.0):
        """Closed part from rings (lists of points, equal length) joined by quads; a one-point ring is a pole
        (triangle fan), a first / last ring of several points gets an n-gon cap. mat / edge: value or f(row, col)
        for the band between ring row and row + 1 (caps: mat of the nearest band, edge 0)."""
        self.begin()
        ids = [[self.v(p) for p in ring] for ring in rings]
        n = max(len(r) for r in ids)
        for r in range(len(ids) - 1):
            a, b = ids[r], ids[r + 1]
            for c in range(n):
                c2 = (c + 1) % n
                m = mat(r, c) if callable(mat) else mat
                e = edge(r, c) if callable(edge) else edge
                if len(a) == 1:
                    self.f((a[0], b[c2], b[c]), m, e)
                elif len(b) == 1:
                    self.f((a[c], a[c2], b[0]), m, e)
                else:
                    self.f((a[c], a[c2], b[c2], b[c]), m, e)
        if len(ids[0]) > 1:
            self.f(tuple(reversed(ids[0])), mat(0, 0) if callable(mat) else mat)
        if len(ids[-1]) > 1:
            self.f(tuple(ids[-1]), mat(len(ids) - 2, 0) if callable(mat) else mat)
        self.end()
        return ids

    def torus(self, R, r, z, segs, sides, mat=0):
        """Ring in the XY plane at height z; one tube vertex row sits on the very top (z + r)."""
        self.begin()
        tube = [(math.cos(math.pi / 2 + 2 * math.pi * k / sides), math.sin(math.pi / 2 + 2 * math.pi * k / sides))
                for k in range(sides)]
        ids = [[self.v(((R + r * c) * math.cos(2 * math.pi * i / segs), (R + r * c) * math.sin(2 * math.pi * i / segs),
                        z + r * s)) for c, s in tube] for i in range(segs)]
        for i in range(segs):
            a, b = ids[i], ids[(i + 1) % segs]
            for k in range(sides):
                k2 = (k + 1) % sides
                self.f((a[k], b[k], b[k2], a[k2]), mat)
        self.end()

    def xform(self, fn, v0=0):
        """Map vertices v0.. through fn (point -> point)."""
        for i in range(v0, len(self.verts)):
            self.verts[i] = fn(self.verts[i])

    def mirror_x(self):
        self.xform(lambda p: (-p[0], p[1], p[2]))
        self.faces = [tuple(reversed(fc)) for fc in self.faces]


def _hf_csq(a, d, z):
    """Chamfered square section (half width a, corner chamfer d) at height z, 8 points CCW from the +x face's
    start; columns 0, 2, 4, 6 are the main faces (+x, +y, -x, -y), 1, 3, 5, 7 the corner chamfers."""
    return [(a, -a + d, z), (a, a - d, z), (a - d, a, z), (-a + d, a, z), (-a, a - d, z), (-a, -a + d, z),
            (-a + d, -a, z), (a - d, -a, z)]


def _hf_rows_edge(rows, corner):
    """Edge wear for a stack of section rows: 1 on bevelled bands (both the width and the height change) and, when
    ``corner``, on the corner-chamfer columns."""
    def e(r, c):
        (a0, z0), (a1, z1) = rows[r], rows[r + 1]
        if abs(a1 - a0) > 1e-6 and abs(z1 - z0) > 1e-6:
            return 1.0
        return 1.0 if corner and c % 2 == 1 else 0.0
    return e


def _hf_octagon(af, z):
    """Regular octagon (half across flats af, flats facing +-x and +-y) at height z."""
    R = af / math.cos(math.pi / 8)
    return [(R * math.cos(math.pi / 8 + k * math.pi / 4), R * math.sin(math.pi / 8 + k * math.pi / 4), z)
            for k in range(8)]


def _hf_plinth():
    g = _HFGeo()
    g.loft([_hf_octagon(a, z) for a, z in HF_PLINTH], edge=_hf_rows_edge(HF_PLINTH, False))
    return g


def _hf_lathe(g, profile, segs, mat=0, edge=0.0):
    """Round lathe of (r, z) rows; r = 0 rows are poles."""
    rings = []
    for r, z in profile:
        rings.append([(0.0, 0.0, z)] if r <= 1e-9 else
                     [(r * math.cos(2 * math.pi * k / segs), r * math.sin(2 * math.pi * k / segs), z)
                      for k in range(segs)])
    return g.loft(rings, mat=mat, edge=edge)


def _hf_altar():
    """Sasanian hourglass in bronze: stepped base, tapered octagonal shaft with collars and a mid-band, inverted
    stepped crown, four stepped merlons on its corners, the round fire bowl."""
    g = _HFGeo()
    g.loft([_hf_csq(a, HF_CORNER, z) for a, z in HF_BASE], edge=_hf_rows_edge(HF_BASE, True))
    g.loft([_hf_csq(a, HF_OCT * a, z) for a, z in HF_SHAFT], edge=_hf_rows_edge(HF_SHAFT, False))
    g.loft([_hf_csq(a, HF_OCT * a, z) for a, z in HF_BAND], edge=_hf_rows_edge(HF_BAND, False))
    g.loft([_hf_csq(a, HF_CORNER, z) for a, z in HF_CROWN], edge=_hf_rows_edge(HF_CROWN, True))
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        cx, cy = sx * HF_MERLON_XY, sy * HF_MERLON_XY
        g.loft([[(cx + a, cy - a, z), (cx + a, cy + a, z), (cx - a, cy + a, z), (cx - a, cy - a, z)]
                for a, z in HF_MERLON], edge=lambda r, c: 1.0 if r % 2 == 1 else 0.0)     # step treads
    _hf_lathe(g, HF_BOWL, HF_BOWL_SEGS)
    return g


def _hf_face_map(k, a):
    """Point map for relief on main face k (0 +x, 1 +y, 2 -x, 3 -y) at half width a: (u right as seen from
    outside, v = z, w out of the face) -> local point."""
    nx, ny = ((1, 0), (0, 1), (-1, 0), (0, -1))[k]
    return lambda u, v, w: (nx * (a + w) - ny * u, ny * (a + w) + nx * u, v)


def _hf_prism(g, outline, fmap, mat=0):
    """Raised relief: a simple polygon (u, v) extruded from HF_RELIEF[1] under the face to HF_RELIEF[0] above it."""
    up, down = HF_RELIEF
    g.loft([[fmap(u, v, -down) for u, v in outline], [fmap(u, v, up) for u, v in outline]], mat=mat, edge=1.0)


def _hf_cloud_strip(half, v0, bar, lobes, segs):
    """Rolling-cloud strip: a bar with ruyi lobes (3/4 circles pinched where they meet the bar)."""
    top = v0 + bar
    pts = [(-half, v0), (half, v0), (half, top)]
    for (c, r), m in sorted(zip(lobes, segs), key=lambda q: -q[0][0]):      # right to left
        cy = top + 0.5 * r
        for i in range(m + 1):
            th = math.radians(-30.0 + 240.0 * i / m)
            pts.append((c + r * math.cos(th), cy + r * math.sin(th)))
    pts.append((-half, top))
    return pts


def _hf_flame_strip(half, v0, bar, tongues, w, h):
    """Flame frieze: a bar with flame tongues (tips leaning right)."""
    top = v0 + bar
    pts = [(-half, v0), (half, v0), (half, top)]
    for c in sorted(tongues, reverse=True):                                   # right to left
        pts += [(c + 0.5 * w, top), (c + 0.3 * w, top + 0.5 * h), (c + 0.1 * w, top + h),
                (c - 0.3 * w, top + 0.55 * h), (c - 0.5 * w, top)]
    pts.append((-half, top))
    return pts


def _hf_relief():
    """Gold: the bowl rim, fillets above and below the mid-band, rolling clouds on the mid-band's main faces and a
    flame frieze on the top crown tier's main faces."""
    g = _HFGeo()
    R, r, z, segs, sides = HF_RIM
    g.torus(R, r, z, segs, sides)
    for a, z0, z1 in ((0.53, 1.82, 1.85), (0.51, 2.07, 2.10)):
        g.loft([_hf_csq(a, HF_OCT * a, z0), _hf_csq(a, HF_OCT * a, z1)], edge=1.0)
    clouds = _hf_cloud_strip(0.30, 1.895, 0.028, ((-0.19, 0.055), (0.0, 0.07), (0.19, 0.055)), (6, 7, 6))
    flames = _hf_flame_strip(0.90, 3.008, 0.022, (-0.72, -0.24, 0.24, 0.72), 0.20, 0.09)
    for k in range(4):
        _hf_prism(g, clouds, _hf_face_map(k, HF_BAND[1][0]))
        _hf_prism(g, flames, _hf_face_map(k, HF_CROWN[HF_CROWN_TOP][0]))
    a, z0, z1 = HF_KNOT
    g.loft([_hf_csq(a, HF_OCT * a, z0), _hf_csq(a, HF_OCT * a, z1)], edge=1.0)
    w, t, tw = HF_RIBBON_W
    for sx in (1.0, -1.0):
        for sy in (1.0, -1.0):                           # a V pair of tails on each side face
            _hf_strip(g, [(sx * x, sy * y, z) for x, y, z in HF_RIBBON], w, t, math.radians(tw) * sx * sy)
    return g


def _hf_strip(g, ctrl, width, thick, twist=0.0, per=2):
    """Closed flat ribbon along a Catmull-Rom spine: rectangular section, broad face toward the outside (its width
    lies across the spine, horizontal at the root), twisting by ``twist`` to the free end, flat ends."""
    path = _hf_spline(ctrl, per)
    m = len(path)
    rings = []
    for i, p in enumerate(path):
        T = _hf_unit(_hf_sub(path[min(i + 1, m - 1)], path[max(i - 1, 0)]))
        W = _hf_unit(_hf_cross((0.0, 0.0, 1.0), (p[0], p[1], 0.0)))           # horizontal, across the shaft
        W = _hf_unit(_hf_sub(W, _hf_mul(T, _hf_dot(W, T))))
        W = _hf_spin(W, T, twist * (i / (m - 1)) ** 1.5)
        N = _hf_cross(T, W)
        hw, ht = 0.5 * width, 0.5 * thick
        rings.append([_hf_add(p, _hf_add(_hf_mul(W, su * hw), _hf_mul(N, sv * ht)))
                      for su, sv in ((1, 1), (-1, 1), (-1, -1), (1, -1))])
    g.loft(rings, edge=lambda r, c: 1.0 if c % 2 else 0.0)


_HF_ICO = None


def _hf_ico():
    """Unit icosahedron (12 vertices, 20 faces)."""
    global _HF_ICO
    if _HF_ICO is None:
        t = (1.0 + math.sqrt(5.0)) / 2.0
        vs = [_hf_unit(p) for p in ((-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t),
                                    (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1))]
        fs = ((0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
              (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11),
              (6, 2, 10), (8, 6, 7), (9, 8, 1))
        _HF_ICO = (vs, fs)
    return _HF_ICO


def _hf_bed_z(r):
    """Height of the ember bed's top at radius r (HF_COALS profile)."""
    prof = sorted(HF_COALS[1:], key=lambda q: q[0])
    if r <= prof[0][0]:
        return prof[0][1]
    for (r0, z0), (r1, z1) in zip(prof, prof[1:]):
        if r <= r1:
            return z0 + (z1 - z0) * (r - r0) / (r1 - r0)
    return prof[-1][1]


def _hf_coals():
    """Ember bed (molten, slot 0) heaped in the bowl, dark iron ash lumps (slot 1) and a few loose embers on it."""
    import random
    rnd = random.Random(61920)
    g = _HFGeo()
    segs = 20
    rings = []
    for i, (r, z) in enumerate(HF_COALS):
        if r <= 1e-9:
            rings.append([(0.0, 0.0, z + 0.02)])
            continue
        ring = []
        for k in range(segs):
            a = 2 * math.pi * k / segs
            rr, zz = r, z
            if 0 < i:                                     # lumpy top (the bottom ring stays round in the bowl)
                rr *= 1.0 + 0.05 * math.sin(3 * a + i) + rnd.uniform(-0.03, 0.03)
                zz += 0.025 * math.sin(5 * a + 2 * i) + rnd.uniform(-0.015, 0.015)
            ring.append((rr * math.cos(a), rr * math.sin(a), zz))
        rings.append(ring)
    g.loft(rings, mat=0)
    vs, fs = _hf_ico()

    def lump(cx, cy, size, flat, mat):
        z = _hf_bed_z(math.hypot(cx, cy)) - 0.3 * size * flat
        yaw = rnd.uniform(0, 2 * math.pi)
        c, s = math.cos(yaw), math.sin(yaw)
        g.begin()
        ids = []
        for p in vs:
            k = size * rnd.uniform(0.8, 1.2)
            x, y = p[0] * k, p[1] * k * rnd.uniform(0.75, 1.0)
            ids.append(g.v((cx + c * x - s * y, cy + s * x + c * y, z + p[2] * k * flat)))
        for fc in fs:
            g.f(tuple(ids[i] for i in fc), mat)
        g.end()

    for i in range(22):                                   # iron ash lumps, mostly round the rim where they show
        a = 2 * math.pi * (i + rnd.uniform(-0.3, 0.3)) / 22
        rr = rnd.uniform(0.42, 0.72) if i % 3 else rnd.uniform(0.25, 0.45)
        lump(rr * math.cos(a), rr * math.sin(a), rnd.uniform(0.08, 0.15), 0.6, 1)
    for i in range(8):                                    # loose glowing embers
        a = 2 * math.pi * (i + 0.5 + rnd.uniform(-0.3, 0.3)) / 8
        rr = rnd.uniform(0.45, 0.70)
        lump(rr * math.cos(a), rr * math.sin(a), rnd.uniform(0.05, 0.09), 0.8, 0)
    return g


def _hf_shape(t):
    """Flame tongue width along its length (t 0 base .. 1 tip): a slight belly low down, a long taper."""
    return (1.0 - t) ** 1.15 * (1.0 + 1.7 * t)


def _hf_tongue(g, ctrl, width, thick, sides, per, twist, wref, shape=_hf_shape, pole_base=False):
    """Closed lofted tongue along a Catmull-Rom spine: lens section (``width`` across, ``thick`` x that through),
    its broad axis starting along ``wref`` and twisting by ``twist`` to the tip, which is a single point."""
    path = _hf_spline(ctrl, per)
    m = len(path)
    lens = [(math.cos(2 * math.pi * k / sides),
             thick * math.sin(2 * math.pi * k / sides) * (0.55 + 0.45 * abs(math.sin(2 * math.pi * k / sides))))
            for k in range(sides)]
    rings = []
    for i, p in enumerate(path):
        t = i / (m - 1)
        if i == m - 1 or (pole_base and i == 0):
            rings.append([p])
            continue
        T = _hf_unit(_hf_sub(path[min(i + 1, m - 1)], path[max(i - 1, 0)]))
        W = _hf_spin(wref, T, twist * t)
        W = _hf_unit(_hf_sub(W, _hf_mul(T, _hf_dot(W, T))))
        D = _hf_cross(T, W)
        hw = 0.5 * width * shape(t)
        rings.append([_hf_add(p, _hf_add(_hf_mul(W, hw * cu), _hf_mul(D, hw * sv))) for cu, sv in lens])
    g.loft(rings)


def _hf_slim(t):
    """Side tongue width: less belly, a quicker taper."""
    return (1.0 - t) ** 1.3 * (1.0 + 1.2 * t)


# side tongues: azimuth (deg from +x; -90 is the front, toward the hold camera), height, base width, twist (deg),
# wiggle phase (deg); heights 0.9-1.3 m, uneven so the crown is not a flower
HF_SIDE_TONGUES = ((-52.0, 1.25, 0.56, 28.0, 0.0), (-128.0, 1.08, 0.54, -26.0, 140.0), (12.0, 0.92, 0.50, 22.0, 70.0),
                   (168.0, 1.02, 0.52, -24.0, 210.0), (88.0, 1.30, 0.58, 30.0, 300.0))


def _hf_flame():
    """Stylised flame crown in the canonical frame (broad side to -y, x to its right): a broad low body filling the
    bowl, a central S-curved tongue twisting 40 deg, five wavy side tongues rising round it and leaning a little out,
    a short core tongue and two detached licks. Every tongue is a closed lofted lens tube ending in a point."""
    g = _HFGeo()
    z0 = HF_FLAME_Z
    H = HF_FLAME_H
    # body: the fire's mass over the coals, so the tongues read as one blaze rather than separate petals
    _hf_tongue(g, [(0.0, 0.0, z0), (0.05, 0.0, z0 + 0.32), (0.0, 0.02, z0 + 0.64), (-0.06, 0.03, z0 + 0.95)],
               1.25, 0.62, 12, 2, math.radians(15.0), (1.0, 0.0, 0.0))
    ctrl = [(0.0, 0.0, 0.0), (0.07, 0.01, 0.30), (0.11, 0.03, 0.62), (0.02, 0.05, 0.95), (-0.10, 0.06, 1.22),
            (-0.08, 0.06, 1.50), (0.06, 0.05, H)]
    _hf_tongue(g, [(x, y, z0 + z) for x, y, z in ctrl], 0.85, 0.50, 10, 2, math.radians(40.0), (1.0, 0.0, 0.0))
    for az, h, w, tw, ph in HF_SIDE_TONGUES:
        a, ph = math.radians(az), math.radians(ph)
        u, tau = (math.cos(a), math.sin(a), 0.0), (-math.sin(a), math.cos(a), 0.0)
        r0 = 0.40
        pts = []
        for t in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
            o = r0 + h * (0.22 * t - 0.05 * t * t)                    # leans out ~12 deg at the foot, then rises
            c = 0.07 * math.sin(1.8 * math.pi * t + ph) * min(1.0, 3.0 * t)   # S wiggle, none at the foot
            pts.append((u[0] * o + tau[0] * c, u[1] * o + tau[1] * c, z0 + h * t))
        _hf_tongue(g, pts, w, 0.45, 8, 2, math.radians(tw), tau, shape=_hf_slim)
    # short inner core, broad axis across the central tongue's
    _hf_tongue(g, [(0.0, 0.03, z0), (0.03, 0.0, z0 + 0.3), (-0.02, -0.03, z0 + 0.58), (0.02, -0.02, z0 + 0.8)],
               0.50, 0.55, 8, 2, math.radians(30.0), (0.0, 1.0, 0.0))
    # two licks torn off the top (spindles with both ends pointed)
    for (x, y, z, h, w, lean) in ((0.30, -0.04, 1.20, 0.24, 0.10, 0.06), (-0.26, 0.02, 1.46, 0.20, 0.08, -0.05)):
        _hf_tongue(g, [(x, y, z0 + z), (x + 0.4 * lean, y, z0 + z + 0.5 * h), (x + lean, y, z0 + z + h)],
                   w, 0.5, 6, 2, 0.0, (1.0, 0.0, 0.0), shape=lambda t: math.sin(math.pi * t) ** 0.7, pole_base=True)
    # turn the broad side to the hold camera (canonical -y -> HF_FRONT)
    c, s = math.cos(HF_FRONT), math.sin(HF_FRONT)
    g.xform(lambda p: (c * p[0] - s * p[1], s * p[0] + c * p[1], p[2]))
    return g


def holy_fire_geo(side=1.0):
    """{part: (_HFGeo, materials, smooth, glow, casts_shadow)} for one altar in its Empty's frame; side -1 (west)
    is the mirror image of side +1 (east)."""
    coals = _hf_coals()
    c, s = math.cos(HF_FRONT), math.sin(HF_FRONT)
    coals.xform(lambda p: (c * p[0] - s * p[1], s * p[0] + c * p[1], p[2]))
    parts = dict(plinth=(_hf_plinth(), ["stone_grey"], False, None, True),
                 altar=(_hf_altar(), ["bronze"], math.radians(35.0), None, True),
                 relief=(_hf_relief(), ["gold"], math.radians(65.0), None, True),
                 coals=(coals, ["molten", "iron"], math.radians(30.0), 1.5, True),
                 # fire casts no shadow (renders; the bake's joined mesh drops the flag, the light is unshadowed)
                 flame=(_hf_flame(), ["props_flame"], True, 1.0, False))
    if side < 0:
        for geo, *_ in parts.values():
            geo.mirror_x()
    return parts


def _holy_fire(coll, root, x, y):
    """One holy-fire altar 圣火坛 at local (x, y): Empty 'mission.holy_fire[.001]' with the children .plinth, .altar,
    .relief, .coals and .flame, and the warm point light 'mission.holy_fire_light[.001]' over the bowl (the bake
    pools its light on the plinth and the paving). Returns the Empty."""
    hf = U.empty(U.name(K, "holy_fire"), coll, location=(x, y, 0.0), parent=root, display_size=1.5)
    parts = holy_fire_geo(1.0 if x >= 0 else -1.0)
    for key in HF_PARTS:
        geo, mats, smooth, glow, shadow = parts[key]
        ob = U.mesh_from_pydata(U.name(K, hf.name + "." + key), geo.verts, geo.faces, coll, materials=mats,
                                smooth=smooth, material_indices=geo.mat, parent=hf)
        me = ob.data
        if any(geo.edge) and len(me.polygons) == len(geo.edge):
            at = me.attributes.get(U.EDGE_ATTR) or me.attributes.new(U.EDGE_ATTR, 'FLOAT', 'FACE')
            at.data.foreach_set("value", geo.edge)
        if glow is not None:
            ob["glow"] = float(glow)
        if not shadow:
            U.set_visibility(ob, shadow=False)
    ld = bpy.data.lights.new(U.name(K, "holy_fire_light", pool=bpy.data.lights), 'POINT')
    ld.energy = HF_LIGHT["energy"]
    ld.color = HF_LIGHT["color"]
    ld.shadow_soft_size = HF_LIGHT["soft"]
    # no shadows: the light sits inside the flame crown, and bake_web joins the chunk into one mesh (the flame's
    # visible_shadow=False is lost there), so a shadowing light would be boxed in by the flame; the crown would
    # also shade the whole plinth. Unshadowed it pools on the plinth and paving as the fire's glow.
    ld.use_shadow = HF_LIGHT["shadow"]
    lo = bpy.data.objects.new(U.name(K, "holy_fire_light"), ld)
    coll.objects.link(lo)
    lo.parent = hf
    lo.location = (0.0, 0.0, HF_LIGHT["z"])
    return hf


def _props(coll, root):
    # stone lanterns lining the axis, in front of and behind the mission wall
    for y in (-40.0, -20.0):
        for sx in (-1, 1):
            P.lantern_stone(coll, 2.6, name=U.name(K, "stone_lantern"), parent=root, location=(sx * 5.2, y, 0))
    # bronze censer between the wall and the hall stairs
    P.incense_burner(coll, 1.8, name=U.name(K, "censer"), parent=root, location=(0, -5.0, 0))
    # the Ming Sect's holy-fire altars 圣火坛, a symmetric pair on the open paving beside the mission wall
    for x, y in HOLY_FIRE:
        _holy_fire(coll, root, x, y)
    # tall sect banners at the plaza front corners
    for i, sx in enumerate((-1, 1)):
        P.banner(coll, 9.0, 1.3, material=3 if i else 0, seed=40 + i, name=U.name(K, "banner"), parent=root,
                 location=(sx * 16.0, -40.0, 0), rotation=(0, 0, math.pi if sx > 0 else 0.0))
    # pines in the back corners and beside the hall
    for i, (x, y, h) in enumerate(((-31.0, 33.0, 13.0), (31.0, 33.0, 12.0), (-31.0, -33.0, 10.0),
                                   (31.0, -33.0, 10.5))):
        N.pine(coll, height=h, seed=i + 3, lod="mid", name=U.name(K, "pine"), parent=root, location=(x, y, 0))


# ---------------------------------------------------------------- entry point
def build(collection):
    """Build the Mission Hall at the local origin. Returns the root Empty 'mission.root'."""
    _fix_font_paths()
    root = U.empty(U.name(K, "root"), collection, display_size=4.0)
    wall, wall_stair_foot = _mission_wall(collection, root)
    hall, stair_foot = _hall(collection, root)
    _plaza(collection, root, stair_foot, wall_stair_foot)
    _arrival(collection, root)
    depart_x = _side_gate(collection, root)
    _towers(collection, root)
    _corridors(collection, root, (hall["arch_platform"][0] + TERRACE_MARGIN) / 2)
    _props(collection, root)
    root["hall_height"] = TERRACE_H + hall["arch_height"]
    root["wall_tablets"] = 7
    print("MISSION_INFO", dict(hall_platform=tuple(hall["arch_platform"]), hall_height=TERRACE_H + hall["arch_height"],
                                hall_y=hall.location.y, stair_foot=stair_foot, wall_stair_foot=wall_stair_foot,
                                depart_steps_foot_x=round(depart_x, 3), arrival=AREA["arrival"],
                                depart=AREA["depart"], wood_tablets=wall["wood_tablets"]), flush=True)
    return root


build.preview_cameras = [(c["name"], c["location"], c["target"], c["lens"]) for c in CAMERA_HINTS]
