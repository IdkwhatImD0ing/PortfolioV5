"""Round 34, east lane: the Jin Yong references at the arena, the Mission Hall and the formation get their new staging
(sect/patch_r34_east.py patches an existing file; areas/arena.py, mission.py and formation.py call the same builders in a
fresh build). The forge's smith's corner is areas/forge.py's own (SMITH_*).

- arena: the seats of the Five Greats 五絕 of the Mount Hua contests 華山論劍 (Legend of the Condor Heroes): four
  bronze plates set into the bagua ring round the taiji at the arena's north, east, south and west (the sword stands to
  the north, the entrance to the south), carrying 北丐 東邪 南帝 西毒 in glowing gold (as the arena's outer script ring)
  inside a gold fillet, each character SEAT_GLYPH tall; the taiji itself is the Centre seat (中神通, Wang Chongyang of
  the Daoist Quanzhen sect). Each plate takes the place of the bagua's trigram at that point (clear_seat_trigrams: the
  four diagonal trigrams stay). Nothing stands on the duelling floor: the plates are inlays as high as the rune ring's
  own (props.RUNE_TOP).
- mission: the Quanzhen Big Dipper array 天罡北斗陣 (Legend of the Condor Heroes, ch. 25: seven masters, one per star):
  seven low stone star drums in the open apron before the role wall, a bronze top on each with the star's name in
  glowing gold, joined by glowing gold inlay lines (as the role boards' rims) in the Dipper's shape: the bowl (天樞 天璇
  天璣 天權) on the left, the handle (玉衡 開陽 搖光) sweeping right and toward the visitor, so the bowl's four answer the
  wall's top row of four role boards and the handle's three its bottom row of three.
- formation: the gold of the holy-fire chant ring is set into the ink band (inlay: the band is cut away under every
  character, so no face is left under the gold), now in traditional characters (formation.CHANT).

Everything any builder makes carries the custom property TAG (its part), so the patch can find, compare and rebuild it.
Lettering is cut the round-12 way (inlay): the host face is cut away under each character (props._imprint, holes) and
the gold's straight walls pass through the cut, its face standing a little proud.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from sect.lib import array_props as AP
from sect.lib import props as P
from sect.lib import util as U

TAG = "sect_r34_east"          # object (and mesh) property: the part that built it

# ---------------------------------------------------------------- the site's view of a stop
# client/src/lib/sect/framing.ts STOP_FRAMING: at a framed hold the page shows the camera's pose of frame (hold - back),
# turned yaw about world up, then pitch about the camera's own right axis (free-look.ts composeLook). The forge and the
# arena have no framing (the plain chase.cam at the frame).
HOLD_FRAMES = {"forge": 352, "arena": 516, "mission": 619, "formation": 1208}
SITE_FRAMING = {619: (8.0, 2.0, 0), 1208: (0.0, -8.0, 0)}     # hold frame -> (yaw deg, pitch deg, back frames)
# the page's panels and buttons at 1600 x 900 (px: x0, y0, x1, y1), measured on the r31 audit's hold shots: nothing new
# may sit under them
UI_RECTS = {
    "forge": (("panel", (65, 577, 377, 808)),),
    "arena": (("panel", (1100, 82, 1487, 314)),),
    "mission": (("panel", (1115, 82, 1487, 314)),),
    "formation": (("panel", (65, 590, 495, 808)),),
}
UI_COMMON = (("voice", (1500, 800, 1580, 880)), ("header", (20, 15, 378, 95)), ("map", (1485, 15, 1577, 110)))
# close-up boxes (area frame: (min), (max)) for the preview's long-lens shots, the same before and after
CLOSE_BOXES = {
    "forge_corner": ((8.0, -5.0, 0.0), (21.0, 6.0, 3.0)),
    "forge_west": ((-27.0, -20.0, 0.0), (-11.0, -12.0, 2.5)),
    "arena_seats": ((-13.0, -13.0, 0.0), (13.0, 13.0, 0.4)),
    "arena_north": ((-2.5, 9.0, 0.0), (2.5, 12.5, 0.2)),
    "mission_dipper": ((-15.0, -42.5, 0.0), (15.0, -33.0, 1.0)),
    "mission_bowl": ((-13.5, -40.0, 0.0), (-1.0, -34.0, 0.5)),
    "mission_east": ((21.0, -31.0, 0.0), (29.0, -23.0, 5.0)),
    "formation_altars": ((-20.0, -46.0, 0.0), (20.0, -33.0, 6.0)),
    "formation_chant": ((-24.0, -14.0, 0.0), (-14.0, 14.0, 0.1)),
    "formation_chantback": ((-12.0, 17.0, 0.0), (12.0, 24.0, 0.1)),
    "formation_dipper": ((-43.0, 7.0, 0.0), (-20.0, 40.0, 2.5)),
}
GRID_RANGE = {"forge": ((-30, 30), (-30, 20)), "arena": ((-16, 16), (-16, 16)), "mission": ((-22, 22), (-50, -28)),
              "formation": ((-26, 26), (-50, -16))}


def site_view(sc, cam, frame):
    """chase.cam's world matrix as the page shows ``frame`` (SITE_FRAMING at a framed hold). Sets the scene frame."""
    yaw, pitch, back = SITE_FRAMING.get(frame, (0.0, 0.0, 0))
    sc.frame_set(frame - back)
    Mw = cam.matrix_world.copy()
    loc = Mw.translation.copy()
    R = Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Mw.to_3x3().normalized() @ \
        Matrix.Rotation(math.radians(pitch), 3, 'X')
    out = R.to_4x4()
    out.translation = loc
    return out


def tag(ob, part):
    ob[TAG] = part
    if ob.type == 'MESH' and ob.data is not None:
        ob.data[TAG] = part
    return ob


# ================================================================ lettering: gold set into a host face

def glyphs_bm(chars, size, place, depth, sink, mat=0):
    """BMesh of KaiTi characters lying in XY (readable from +Z, glyph up +Y): ``place(i)`` -> (x, y, z_face, yaw) of
    character i's centre on its host face; each scaled so its larger side is ``size``; the gold's face ``depth`` - ``sink``
    proud of z_face and its back ``sink`` under it (straight walls, no bevel). Returns (bm, z_face of each)."""
    bm = bmesh.new()
    for i, ch in enumerate(chars):
        x, y, z, yaw = place(i)
        # text_glyph extrudes +-extrude about the glyph's plane: centre it so the walls run z - sink .. z + depth - sink
        e = 0.5 * depth
        m = Matrix.Translation((x, y, z + e - sink)) @ Matrix.Rotation(yaw, 4, 'Z')
        AP.text_glyph(bm, ch, size, m, mat=mat, extrude=e)
    return bm


def face_regions(bm, z, tol=1e-5):
    """The upward faces of ``bm`` lying at height z: [(polygon [(x, y)], 'gold')] (the glyphs' faces, for _imprint)."""
    out = []
    for f in bm.faces:
        f.normal_update()
        if f.normal.z > 0.9999 and all(abs(v.co.z - z) < tol for v in f.verts):
            out.append(([(v.co.x, v.co.y) for v in f.verts], "gold"))
    return out


def cut_under(host_bm, faces, regions, z):
    """Cut ``regions`` out of the flat upward ``faces`` (at height z) of ``host_bm``: holes. Returns the number of
    triangles taken out."""
    faces = [f for f in faces if f.is_valid]
    if not faces or not regions:
        raise RuntimeError("cut_under: %d host faces, %d regions" % (len(faces), len(regions)))
    got = P._imprint(host_bm, faces, lambda c: (c.x, c.y), lambda x, y: Vector((x, y, z)), regions, holes=True)
    n = sum(len(v) for v in got.values())
    if not n:
        raise RuntimeError("cut_under: nothing was cut (%d host faces, %d regions)" % (len(faces), len(regions)))
    return n


def mark_edges(me, flags):
    """Set the 'edge' wear face attribute (U.EDGE_ATTR) from per-face flags."""
    a = me.attributes.get(U.EDGE_ATTR) or me.attributes.new(U.EDGE_ATTR, 'FLOAT', 'FACE')
    a.data.foreach_set("value", [float(v) for v in flags])


# ================================================================ arena: the seats of the Five Greats 華山論劍

SEAT_RING = (10.7, 4.2)        # arena.bagua: props.rune_ring radius and width (arena._build_platform)
SEATS = (("north", "北丐", 90.0), ("east", "東邪", 0.0), ("south", "南帝", 270.0), ("west", "西毒", 180.0))
SEAT_SIZE = (3.4, 1.9)         # m: the plate along x (the two characters side by side, read from the hold) and y
SEAT_TOP = 0.04                # the plate's top over the floor: the rune ring's own (props.RUNE_TOP)
SEAT_SINK = 0.02               # its sides reach this far under the floor (props.RUNE_SINK)
SEAT_CHAMFER = 0.025
SEAT_GLYPH = 1.4               # m: each character's larger side
SEAT_PITCH = 1.58              # m between the two characters' centres
SEAT_GOLD = (0.04, 0.02)       # the gold: walls this tall, this much of them under the plate's top (2 cm proud)
SEAT_FRAME = (0.08, 0.05)      # gold fillet round the plate's top: inset from its edge, width
SEAT_CLEAR = (9.25, 12.2, 8.0)  # the trigram under a plate: its bars' faces within this radius band and +- deg
SEAT_MATS = ("props_bronze_aged", "gold", "rune_gold")   # the plate, its fillet, the characters (glowing gold, as the
                                                        # arena's outer script ring)
SEAT_GLOW = 0.8                # obj['glow'] on a seat (rune_gold's strength x this in Cycles)
SEAT_ROOT = "arena.seats"


def seat_centre(deg):
    r = SEAT_RING[0]
    return r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg))


def _plate(bm, hx, hy, top, bottom, ch):
    """Closed bronze plate (material 0): x +-hx, y +-hy, from ``bottom`` to ``top`` with its top edges chamfered by
    ``ch``. Returns (top face, chamfer faces)."""
    def ring(dx, z):
        return [bm.verts.new((sx * dx[0], sy * dx[1], z)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    lo = ring((hx, hy), bottom)
    mid = ring((hx, hy), top - ch)
    hi = ring((hx - ch, hy - ch), top)
    bm.faces.new(list(reversed(lo)))
    cham = []
    for k in range(4):
        k2 = (k + 1) % 4
        bm.faces.new((lo[k], lo[k2], mid[k2], mid[k]))
        cham.append(bm.faces.new((mid[k], mid[k2], hi[k2], hi[k])))
    topf = bm.faces.new(hi)
    return topf, cham


def _frame_bars(hx, hy, inset, w):
    """The gold fillet round the plate's top as four bars that tile the ring (top and bottom full length, the sides
    between them): [polygon [(x, y)]]."""
    ox, oy = hx - inset, hy - inset
    ix, iy = ox - w, oy - w
    return [[(-ox, -oy), (ox, -oy), (ox, -iy), (-ox, -iy)], [(-ox, iy), (ox, iy), (ox, oy), (-ox, oy)],
            [(-ox, -iy), (-ix, -iy), (-ix, iy), (-ox, iy)], [(ix, -iy), (ox, -iy), (ox, iy), (ix, iy)]]


def _rect_ring(bm, ox, oy, ix, iy, z0, z1, mat=0):
    """Closed rectangular ring (the gold fillet): outside x +-ox, y +-oy, inside x +-ix, y +-iy, from z0 to z1."""
    def loop(hx, hy, z):
        return [bm.verts.new((sx * hx, sy * hy, z)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    ol, oh, il, ih = loop(ox, oy, z0), loop(ox, oy, z1), loop(ix, iy, z0), loop(ix, iy, z1)
    fs = []
    for k in range(4):
        k2 = (k + 1) % 4
        fs.append(bm.faces.new((ol[k], ol[k2], oh[k2], oh[k])))          # outer wall, out
        fs.append(bm.faces.new((il[k2], il[k], ih[k], ih[k2])))          # inner wall, in
        fs.append(bm.faces.new((oh[k], oh[k2], ih[k2], ih[k])))          # top
        fs.append(bm.faces.new((ol[k2], ol[k], il[k], il[k2])))          # bottom
    for f in fs:
        f.material_index = mat
    return fs


def _prism_poly(bm, poly, z0, z1, mat=0):
    """Closed vertical prism of a simple polygon from z0 to z1."""
    if P._area2(poly) < 0:
        poly = list(reversed(poly))
    lo = [bm.verts.new((x, y, z0)) for x, y in poly]
    hi = [bm.verts.new((x, y, z1)) for x, y in poly]
    fs = [bm.faces.new(list(reversed(lo))), bm.faces.new(hi)]
    n = len(poly)
    for k in range(n):
        k2 = (k + 1) % n
        fs.append(bm.faces.new((lo[k], lo[k2], hi[k2], hi[k])))
    for f in fs:
        f.material_index = mat
    return fs


def seat_bm(text):
    """One seat in its own frame (origin on the floor at the plate's centre, x along the reading, +y away from the
    hold): the bronze plate (slot 0) with its top cut away under the gold: the fillet (slot 1, gold) and the two
    characters (slot 2, glowing gold). Returns (bm, per-face edge-wear flags)."""
    hx, hy = 0.5 * SEAT_SIZE[0], 0.5 * SEAT_SIZE[1]
    bm = bmesh.new()
    lay = bm.faces.layers.int.new("e")
    topf, cham = _plate(bm, hx, hy, SEAT_TOP, -SEAT_SINK, SEAT_CHAMFER)
    for f in cham:
        f[lay] = 1
    depth, sink = SEAT_GOLD
    gb = glyphs_bm(text, SEAT_GLYPH, lambda i: ((i - 0.5 * (len(text) - 1)) * SEAT_PITCH, 0.0, SEAT_TOP, 0.0),
                   depth, sink, mat=2)
    regions = face_regions(gb, SEAT_TOP - sink + depth)
    inset, w = SEAT_FRAME
    bars = _frame_bars(hx, hy, inset, w)
    cut_under(bm, [topf], regions + [(b, "gold") for b in bars], SEAT_TOP)
    _rect_ring(gb, hx - inset, hy - inset, hx - inset - w, hy - inset - w, SEAT_TOP - sink, SEAT_TOP - sink + depth,
               mat=1)
    me = bpy.data.meshes.new("~r34e.seat.tmp")
    gb.to_mesh(me)
    gb.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    lay = bm.faces.layers.int.get("e")
    flags = [f[lay] if lay is not None else 0 for f in bm.faces]
    if lay is not None:
        bm.faces.layers.int.remove(lay)
    return bm, flags


def build_seats(coll, root, prefix="arena"):
    """The four seats under an Empty '<prefix>.seats' (child of ``root``, the arena's frame): '<prefix>.seat.<dir>'
    meshes (bronze, gold). Returns the Empty."""
    emp = tag(U.empty(U.unique_name(prefix + ".seats"), coll, parent=root, display_size=2.0), "arena")
    for key, text, deg in SEATS:
        bm, flags = seat_bm(text)
        x, y = seat_centre(deg)
        nm = "%s.seat.%s" % (prefix, key)
        ob = U.mesh_from_bmesh(U.unique_name(nm), bm, coll, materials=list(SEAT_MATS), smooth=False, parent=emp,
                               location=(x, y, 0.0))
        mark_edges(ob.data, flags)
        ob["seat_title"] = text
        ob["glow"] = SEAT_GLOW
        tag(ob, "arena")
    return emp


def clear_seat_trigrams(ob, name="arena.bagua.seats"):
    """Take the trigrams at the four seats out of the bagua ring ``ob`` (props.rune_ring 'trigram': one trigram every
    45 degrees from +Y): every face of its bars within SEAT_CLEAR of north, east, south and west goes, so the plates
    take those places and the four diagonal trigrams stay. The ring's shared mesh is left as it is: ``ob`` gets a copy
    of its own, named ``name``. Returns the number of faces taken out (0 when ``ob`` has the cleared mesh already)."""
    me = ob.data
    if me.get(TAG) == "arena.bagua":
        return 0
    new = me.copy()
    new.name = name
    for k in list(new.keys()):
        if k == "sect_shared":
            del new[k]
    r0, r1, half = SEAT_CLEAR
    bm = bmesh.new()
    bm.from_mesh(new)
    kill = []
    for f in bm.faces:
        c = f.calc_center_median()
        r = math.hypot(c.x, c.y)
        if not (r0 <= r <= r1):
            continue
        a = math.degrees(math.atan2(c.y, c.x))
        if any(abs((a - deg + 180.0) % 360.0 - 180.0) <= half for _k, _t, deg in SEATS):
            kill.append(f)
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(new)
    bm.free()
    new.update()
    new[TAG] = "arena.bagua"
    ob.data = new
    if me.users == 0:
        bpy.data.meshes.remove(me)
    return len(kill)


# ================================================================ mission: the Big Dipper 天罡北斗陣

MISSION_HOLD_CAM = (0.13, -73.0)       # chase.cam at the mission hold (619), mission-local (x, y); z 15.4
# (pinyin, name, x, y): the bowl 斗魁 (天樞 Dubhe, 天璇 Merak, 天璣 Phecda, 天權 Megrez), then the handle 斗柄 (玉衡 Alioth,
# 開陽 Mizar, 搖光 Alkaid), in the order of the role boards they answer (the wall's top row of four, left to right, then
# its bottom row of three). The shape is the sky's (the bowl left with its open side up, the handle curving down to
# the right) scaled about 1 : 1 across and 1 : 2 in depth, each drum then nudged (at most 0.6 m) so it stands wholly on
# one level: the apron walk in front of the wall stair (0.08 m up) or the plaza paving, never across the apron's edge,
# and at least 0.6 m from a lantern
DIPPER = (
    ("tianshu", "天樞", -10.6, -34.9),
    ("tianxuan", "天璇", -12.55, -37.15),
    ("tianji", "天璣", -6.5, -38.8),
    ("tianquan", "天權", -1.83, -37.14),
    ("yuheng", "玉衡", 3.81, -37.15),
    ("kaiyang", "開陽", 8.43, -38.8),
    ("yaoguang", "搖光", 13.3, -40.75),
)
DIPPER_LINKS = ((0, 1), (1, 2), (2, 3), (3, 0), (3, 4), (4, 5), (5, 6))
# the drum: a low stone drum (stone_dark) on a base ring, a bronze top (props_bronze_aged) with the star's name in gold;
# (r, z) bottom to top, z from the level it stands on
DRUM_PROFILE = ((0.66, -0.02), (0.66, 0.03), (0.635, 0.055), (0.585, 0.055), (0.6, 0.11), (0.615, 0.18), (0.6, 0.25),
                (0.585, 0.295), (0.61, 0.295), (0.61, 0.325), (0.59, 0.345))
DRUM_SEGS = 40
DRUM_BRONZE_R = 0.53           # the bronze top inside the stone lip
DRUM_EDGE_ROWS = (1, 2, 8, 9)  # profile bands flagged as worn edges (the base ring's lip, the top lip)
DRUM_GLYPH = 0.42              # m: each character of the star's name
DRUM_PITCH = 0.47
DRUM_GOLD = (0.03, 0.015)      # gold walls, how much of them under the bronze (1.5 cm proud)
DRUM_MATS = ("stone_dark", "props_bronze_aged", "rune_gold")   # the name glows gold, as the role boards' rims
DIPPER_GLOW = 0.6              # obj['glow'] on the drums and the lines (mission.ROLE_RIM_GLOW)
LINE_W = 0.16                  # gold inlay line width
LINE_TOP, LINE_SINK = 0.04, 0.02   # over / under the level it lies on (array_props.INLAY_TOP / INLAY_SINK)
LINE_END = 0.03                # a line stops this far outside a drum's base ring
LINE_STEP_IN, LINE_STEP_OUT = 0.03, 0.015   # where a line meets a raised walk: on the walk it stops this far inside its
                                            # edge, on the paving this far short of the walk's side
APRON_X, AXIS_X = 17.0, 3.5    # mission.APRON_X, the axis walk's half width (mission._plaza)
WALK_TOP = 0.08                # mission._walk: the raised walks' top


def dipper_levels(stair_foot, apron_d=4.0):
    """[(x0, x1, y0, y1, top)] of the raised walks the Dipper meets in the mission's frame (mission._plaza): the apron
    in front of the wall stair and the axis walk up to it. Anywhere else the plaza paving's top is z 0."""
    front = stair_foot - apron_d
    return [(-APRON_X, APRON_X, front, stair_foot, WALK_TOP), (-AXIS_X, AXIS_X, -58.0, front, WALK_TOP)]


def level_at(levels, x, y):
    for x0, x1, y0, y1, top in levels:
        if x0 <= x <= x1 and y0 <= y <= y1:
            return top
    return 0.0


def drum_yaw(x, y):
    """Turn of a drum whose name reads upright from the hold camera (its +y away from it)."""
    return math.atan2(y - MISSION_HOLD_CAM[1], x - MISSION_HOLD_CAM[0]) - 0.5 * math.pi


def drum_bm(name):
    """One star drum in its own frame (origin on its level at the centre, +y away from the hold): stone (slot 0) with a
    bronze top (slot 1) cut under the name, and the name in gold (slot 2). Returns (bm, edge flags)."""
    bm = bmesh.new()
    lay = bm.faces.layers.int.new("e")           # (before any face: a layer added later loses the faces' handles)
    segs = DRUM_SEGS
    rings = []
    for r, z in DRUM_PROFILE:
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * k / segs), r * math.sin(2 * math.pi * k / segs), z))
                      for k in range(segs)])
    flags = []
    f = bm.faces.new(list(reversed(rings[0])))
    flags.append(0)
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(segs):
            k2 = (k + 1) % segs
            bm.faces.new((a[k], a[k2], b[k2], b[k]))
            flags.append(1 if i in DRUM_EDGE_ROWS else 0)
    z_top = DRUM_PROFILE[-1][1]
    inner = [bm.verts.new((DRUM_BRONZE_R * math.cos(2 * math.pi * k / segs),
                           DRUM_BRONZE_R * math.sin(2 * math.pi * k / segs), z_top)) for k in range(segs)]
    top = rings[-1]
    for k in range(segs):
        k2 = (k + 1) % segs
        bm.faces.new((top[k], top[k2], inner[k2], inner[k]))
        flags.append(0)
    disc = bm.faces.new(inner)
    disc.material_index = 1
    flags.append(0)
    depth, sink = DRUM_GOLD
    gb = glyphs_bm(name, DRUM_GLYPH, lambda i: ((i - 0.5 * (len(name) - 1)) * DRUM_PITCH, 0.0, z_top, 0.0),
                   depth, sink, mat=2)
    regions = face_regions(gb, z_top - sink + depth)
    for fc, fl in zip(bm.faces, flags):
        fc[lay] = fl
    cut_under(bm, [disc], regions, z_top)
    me = bpy.data.meshes.new("~r34e.drum.tmp")
    gb.to_mesh(me)
    gb.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    flags = [fc[lay] for fc in bm.faces]
    bm.faces.layers.int.remove(lay)
    return bm, flags


def _clip(poly, a, b, c):
    """Sutherland-Hodgman: the part of convex ``poly`` [(x, y)] where a x + b y <= c."""
    out = []
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        dp, dq = a * p[0] + b * p[1] - c, a * q[0] + b * q[1] - c
        if dp <= 0:
            out.append(p)
        if (dp < 0 < dq) or (dq < 0 < dp):
            t = dp / (dp - dq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out if len(out) >= 3 and abs(P._area2(out)) > 1e-8 else []


def _hull(pts):
    """Convex hull (counter-clockwise, collinear points dropped) of 2D points."""
    pts = sorted(set((round(x, 9), round(y, 9)) for x, y in pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 1e-12:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 1e-12:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def line_pieces(levels, p, q, w=LINE_W):
    """The gold line from star p to star q as convex pieces, each on one level: [(polygon, top of its level)]. The
    strip (``w`` wide, LINE_END outside both drums' base rings) is cut along every walk's edges; a piece on a walk
    stops LINE_STEP_IN inside its edges, a piece on the paving LINE_STEP_OUT short of a walk's side."""
    px, py = p
    qx, qy = q
    L = math.hypot(qx - px, qy - py)
    ux, uy = (qx - px) / L, (qy - py) / L
    nx, ny = -uy * 0.5 * w, ux * 0.5 * w
    e = DRUM_PROFILE[0][0] + LINE_END
    a = (px + ux * e, py + uy * e)
    b = (qx - ux * e, qy - uy * e)
    cells = [[(a[0] - nx, a[1] - ny), (b[0] - nx, b[1] - ny), (b[0] + nx, b[1] + ny), (a[0] + nx, a[1] + ny)]]
    cuts = []
    for x0, x1, y0, y1, _t in levels:
        cuts += [(1.0, 0.0, x0), (1.0, 0.0, x1), (0.0, 1.0, y0), (0.0, 1.0, y1)]
    for ca, cb, cc in cuts:
        nxt = []
        for poly in cells:
            for part in (_clip(poly, ca, cb, cc), _clip(poly, -ca, -cb, -cc)):
                if part:
                    nxt.append(part)
        cells = nxt
    groups = {}
    for poly in cells:
        cx = sum(v[0] for v in poly) / len(poly)
        cy = sum(v[1] for v in poly) / len(poly)
        host = None
        for lv in levels:
            x0, x1, y0, y1, _t = lv
            if x0 < cx < x1 and y0 < cy < y1:
                host = lv
        groups.setdefault(host, []).append(poly)
    merged = []
    for host, polys in groups.items():               # cells of one level that tile a convex piece of the strip: one
        hull = _hull([v for p in polys for v in p])  # polygon (a cut line that only another level needs splits none)
        if abs(abs(P._area2(hull)) - sum(abs(P._area2(p)) for p in polys)) < 1e-6:
            merged.append((host, hull))
        else:
            merged += [(host, p) for p in polys]
    out = []
    for host, poly in merged:
        cx = sum(v[0] for v in poly) / len(poly)
        cy = sum(v[1] for v in poly) / len(poly)
        if host is not None:                         # on a walk: stay LINE_STEP_IN inside its edges
            x0, x1, y0, y1, top = host
            for ca, cb, cc in ((-1, 0, -(x0 + LINE_STEP_IN)), (1, 0, x1 - LINE_STEP_IN),
                               (0, -1, -(y0 + LINE_STEP_IN)), (0, 1, y1 - LINE_STEP_IN)):
                poly = _clip(poly, ca, cb, cc) if poly else []
            if poly:
                out.append((poly, top))
            continue
        for x0, x1, y0, y1, _t in levels:            # on the paving: stop short of any walk's side it borders
            outside = [(cx < x0, (1, 0, x0 - LINE_STEP_OUT)), (cx > x1, (-1, 0, -(x1 + LINE_STEP_OUT))),
                       (cy < y0, (0, 1, y0 - LINE_STEP_OUT)), (cy > y1, (0, -1, -(y1 + LINE_STEP_OUT)))]
            sides = [h for o, h in outside if o]
            if len(sides) == 1 and poly:
                poly = _clip(poly, *sides[0])
        if poly:
            out.append((poly, 0.0))
    return out


def dipper_lines_bm(levels, stars=DIPPER, links=DIPPER_LINKS):
    """The Dipper's gold lines (closed prisms, LINE_TOP over their level, LINE_SINK into it) in the mission's frame."""
    bm = bmesh.new()
    for i, j in links:
        for poly, top in line_pieces(levels, stars[i][2:4], stars[j][2:4]):
            _prism_poly(bm, poly, top - LINE_SINK, top + LINE_TOP)
    return bm


def build_dipper(coll, root, stair_foot, prefix="mission"):
    """The seven star drums ('<prefix>.dipper.<pinyin>': an Empty on its level, turned so the name reads from the
    hold, with '.drum': stone, a bronze top, the name in glowing gold) and the gold lines '<prefix>.dipper.lines'. Returns the
    Empties."""
    levels = dipper_levels(stair_foot)
    out = []
    for py, name, x, y in DIPPER:
        z = level_at(levels, x, y)
        emp = tag(U.empty(U.unique_name("%s.dipper.%s" % (prefix, py)), coll, location=(x, y, z), parent=root,
                          rotation=(0.0, 0.0, drum_yaw(x, y)), display_size=0.8), "mission")
        emp["star"] = name
        bm, flags = drum_bm(name)
        ob = U.mesh_from_bmesh(U.unique_name(emp.name + ".drum"), bm, coll, materials=list(DRUM_MATS), smooth=False,
                               parent=emp)
        mark_edges(ob.data, flags)
        ob["glow"] = DIPPER_GLOW
        tag(ob, "mission")
        out.append(emp)
    ln = U.mesh_from_bmesh(U.unique_name(prefix + ".dipper.lines"), dipper_lines_bm(levels), coll,
                           materials=["rune_gold"], smooth=False, parent=root)
    ln["glow"] = DIPPER_GLOW
    tag(ln, "mission")
    return out


# ================================================================ formation: the chant set into the ink band

def chant_inlay(band_me, glyph_bm, z_face, z_gold, r_band):
    """Cut the chant's characters out of the ink band's top (``band_me``: formation.floor_band, its chant ring the
    upward faces at z_face between the radii ``r_band``): holes exactly under the gold's face (``glyph_bm``'s upward
    faces at z_gold). Returns the number of triangles taken out."""
    regions = face_regions(glyph_bm, z_gold)
    bm = bmesh.new()
    bm.from_mesh(band_me)
    faces = []
    for f in bm.faces:
        c = f.calc_center_median()
        if f.normal.z > 0.999 and abs(c.z - z_face) < 1e-5 and r_band[0] - 1e-4 <= math.hypot(c.x, c.y) <= \
                r_band[1] + 1e-4:
            faces.append(f)
    n = cut_under(bm, faces, regions, z_face)
    bm.to_mesh(band_me)
    bm.free()
    band_me.update()
    return n
