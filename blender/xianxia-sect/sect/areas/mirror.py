"""Heart-Mirror Terrace 心镜台 (site section 'about').

Blocking layout (local frame, front = -Y, z = 0 walkable):
  - lawn terrace (radius 43) with a still pond (radius 16) in the middle
  - hexagonal teal-roofed pavilion (ting) on a marble island in the pond; the 心镜台 plaque
    hangs on its front architrave
  - white marble zig-zag bridge from the south shore to the island; entry path lined with
    paired stone lanterns, a second path around the east shore up to the mirror dais
  - at the back, on a marble dais with stairs and a balustrade: a giant round bronze
    mirror (7 m) held by red lacquer cloud arms in a gilt lotus cradle, with a cyan trigram
    ring on its polished face, turned 18 deg toward the low western sun; it reflects in the pond
  - one big peach blossom tree beside the dais, three Huangshan pines on the rim, two taihu
    scholar rocks, lotus, incense burner

Walking route (architecture-audit.md 1.2 and section 4): the stair from the gate tops out at
the foot of three marble steps up to a 7 m arrival strip on the entry path's axis (x -5); the
path runs north past paired lanterns to three low steps onto the zig-zag bridge, which lands on
a railed island (3 m gap at the bridge) in front of the pavilion's own steps. The east path
leaves the main path, rounds the pond and ends on a shore walk at the foot of the dais stair.
A branch off the east path runs to a 6 x 6 m landing on the east rim, with three steps down to
where the stair to the forge starts. A rail runs right round the rim, open at both stairs.
"""

import math

import bmesh
import bpy
from mathutils import Vector

from sect.lib import util as U
from sect.lib import materials as M
from sect.lib import arch as A
from sect.lib import props as P
from sect.lib import nature as N

# arrival / depart: where the incoming and outgoing connector stairs meet this area, as
# (x, y, z, heading) in the local frame (architecture-audit.md 1.2 and W1). z is the ground the
# connector's end step sits flush with (world.py's terrace, -0.4). heading is the walking
# direction in radians, like world.py's yaw = atan2(dy, dx): 0 = +x, pi/2 = +y.
AREA = dict(key="mirror", section_id="about", title_en="Heart-Mirror Terrace",
            title_zh="心镜台", footprint=45.0,
            arrival=(-5.0, -51.5, -0.4, math.pi / 2),   # foot of the arrival steps, on the path axis
            depart=(48.5, 13.0, -0.4, 0.0))             # past the foot of the east landing's steps

KEY = AREA["key"]

# Where the fly-through camera should pass (local, front = -Y): a sweeping arc from the
# south-west, across the front of the pond (mirror face on), out to the east (toward forge).
CAMERA_HINTS = [
    dict(name="approach", location=(-24.0, -78.0, 20.0), target=(2.0, 8.0, 5.0), lens=30),
    dict(name="hero", location=(10.0, -34.0, 13.0), target=(2.0, 16.0, 6.0), lens=26),
    dict(name="depart", location=(46.0, -6.0, 16.0), target=(0.0, 14.0, 5.0), lens=28),
]

# ---------------------------------------------------------------- layout constants
POND_C = (-3.0, -3.0)        # pond centre
POND_R = 16.0
WATER_Z = -0.18
ISLE_C = (-9.0, -1.0)        # pavilion island centre
ISLE_W = 13.5                # hexagon circumscribed diameter (a flat apron between bridge and steps)
DECK_Z = 0.55                # bridge deck / island top
SHRINE_C = (5.0, 23.0)       # mirror dais centre
SHRINE_YAW = math.radians(-18.0)   # front turned toward the low western sun
DAIS_W, DAIS_D, DAIS_H = 18.0, 11.0, 1.5
MIRROR_R = 3.5               # 7 m mirror
MIRROR_TILT = math.radians(6.0)
PATH_Z = 0.12                # top of every paved path, walk and landing


def _shrine_pt(x, y):
    """Shrine-local (x, y) -> area-local (x, y)."""
    c, s = math.cos(SHRINE_YAW), math.sin(SHRINE_YAW)
    return (SHRINE_C[0] + c * x - s * y, SHRINE_C[1] + s * x + c * y)


# zig-zag bridge centreline (x, y): land stub, four 90-degree legs, then straight onto the
# island's south face (y = ISLE_C.y - 0.866 * ISLE_W / 2 = -6.85)
BRIDGE = [(-5.0, -25.0), (-5.0, -21.0), (-9.0, -17.0), (-5.0, -13.0), (-9.0, -9.0), (-9.0, -6.75)]
ISLE_RAIL_GAP = 3.0          # opening in the island rail where the bridge lands

# paved marble paths (all top PATH_Z). Entry: from the arrival strip north to the foot of the
# bridge steps. East: off the entry path, round the east shore, into the shore walk at the foot
# of the dais stair. Forge: off the east path to the east landing (its last point runs 2 m into
# the landing so the path's slanted end leaves no gap).
ARRIVAL = [(-5.0, -50.5), (-5.0, -43.0)]        # 7 m arrival strip; steps down at its south end
PATH_MAIN = [(-5.0, -43.0), (-5.0, -26.0)]
SHORE_Y, SHORE_X = -9.5, 6.0                     # shrine-local: 12 x 2 m walk, y -10.5 to -8.5
PATH_EAST = [(-5.0, -29.0), (10.0, -26.0), (19.5, -11.0), (18.0, 6.0), _shrine_pt(5.0, SHORE_Y)]
PATH_FORGE = [(18.5, 0.0), (30.0, 5.0), (41.0, 11.0), (43.0, 12.1)]
# 6 x 6 m depart landing, centred on the depart line (y 13) so the stair to the forge leaves on
# the steps' axis (the audit centred it on y 12, 1 m off its own depart point)
DEPART_LANDING = (44.0, 13.0, 6.0)
# rail on world.py's -0.4 terrace right round the rim, with a gap where each connector stair
# crosses it. (Until round 11 it ran only along the south and east rim, -135 to 45 deg, and the
# north and west rim behind the dais was an open drop.) The flat terrace follows world.py's
# 2.5 m terrain grid, so its edge wanders from 50.8 to 57.4 m from the centre (measured on
# world.range, round 11): r 52 stays on it except east and north-east of the centre, where the
# edge comes in to 50.8-51.9 m and the half rail's feet hung up to 0.4 m over the lip. There the
# rail steps in to RIM_R_EAST over RIM_EAST (degrees, atan2 convention), with cosine ramps
# RIM_RAMP degrees wide either side, so every foot stands at least 0.24 m inside the flat.
RIM_R, RIM_GAP = 52.0, 6.0
RIM_R_EAST, RIM_EAST, RIM_RAMP = 50.5, (-20.0, 56.0), 8.0
# The stair to the forge starts on world.py's foot landing: FOOT_FLAT (5 m) along the stair from
# the depart point, FOOT_GATE width / 2 + 0.6 (5.6 m) either side of the depart line, walled
# along both sides REVEAL (2 cm) in from the slab. The rail circle runs into that landing through
# its south wall, 3 m before the depart opening's edge, so the south-east span stops against the
# wall: its end post stands RIM_END_EMBED outside the wall's outer face, its shaft 4 cm into the
# wall (no shared face). (Round 11: run on to the opening's edge, it crossed the wall and stood
# 3 m of rail on the landing beside the gate's south column.)
DEPART_FOOT_WALL = 10.0 * 0.5 + 0.6 - 0.02     # that wall's outer face, from the depart line (m)
RIM_END_EMBED = 0.06
# Round 12 (web flicker: every face is drawn double-sided with a 24-bit depth buffer, so surfaces a few mm apart fight
# beyond ~100-200 m, and anything closer than ~2-4 cm within the area's ~400 m draw range):
TERRACE_Z = -0.4             # world.py's flat terrace under the area
LAWN_CLEAR = 0.04            # the lawn keeps at least this much over the terrace or dives LAWN_SINK under it
LAWN_SINK = 0.2              # (seat_lawn: round the pond basin it crossed the terrace's plane 0-12 mm off it; 0.2,
                             # the basin's own depth under it, so the lawn's box stays as it was)
STEP_SINK = 0.12             # the arrival / depart steps' blocks reach this far into the terrace (round 11 sank the
                             # range under the link stairs: they stood up to 6 cm over it)
LOTUS_LIFT = 0.04            # the lotus pads float this much higher (their rims dipped into the water: 0-8 mm)
DRUM_PLINTH = (0.30, 0.05, 0.04)   # stone plinth under each stair balustrade's drum stone: width, reach past the
                             # drum's front, how far the drum's base sits in it. The 1 m drums at the foot of these
                             # 3-step stairs stood on the sloping stringer's top with a wedge of air under their front
                             # half, their front 0.2 m past the stair's foot, 0.4 m over the ground


def _mirror_face_builder(g):
    """Polished gold-bronze mirror face: low roughness metal with a soft warm inner light, so
    it reads as a sun-catching disc from any angle of the camera arc."""
    v = g.coord("object")
    n = g.noise(v, 0.6, detail=3.0)
    base = g.ramp(n, [(0.3, "#f0cf8a"), (0.75, "#d6a95e")])
    rough = g.maprange(n, 0.0, 1.0, 0.06, 0.14)
    g.output(g.principled(base_color=base, metallic=1.0, roughness=rough,
                          emission_color="#ffc06a", emission_strength=1.4))


M.register("mirror_face", _mirror_face_builder)


def _n(*parts):
    return U.name(KEY, *parts)


# ---------------------------------------------------------------- geometry helpers

def _miter(pts, width):
    """Left/right offset polylines (mitred) of a 2D polyline."""
    P2 = [Vector((x, y)) for x, y in pts]
    n = len(P2)
    L, R = [], []
    for i in range(n):
        if i == 0:
            d = (P2[1] - P2[0]).normalized()
            m, k = Vector((-d.y, d.x)), 1.0
        elif i == n - 1:
            d = (P2[i] - P2[i - 1]).normalized()
            m, k = Vector((-d.y, d.x)), 1.0
        else:
            d0 = (P2[i] - P2[i - 1]).normalized()
            d1 = (P2[i + 1] - P2[i]).normalized()
            n0, n1 = Vector((-d0.y, d0.x)), Vector((-d1.y, d1.x))
            m = (n0 + n1).normalized()
            k = 1.0 / max(0.3, m.dot(n0))
        L.append(P2[i] + m * (0.5 * width * k))
        R.append(P2[i] - m * (0.5 * width * k))
    return L, R


def _strip(name, coll, pts, width, z_top, z_bot, mat, parent):
    """Flat prism along a 2D polyline (paths, bridge deck)."""
    L, R = _miter(pts, width)
    bm = bmesh.new()
    lt = [bm.verts.new((p.x, p.y, z_top)) for p in L]
    rt = [bm.verts.new((p.x, p.y, z_top)) for p in R]
    lb = [bm.verts.new((p.x, p.y, z_bot)) for p in L]
    rb = [bm.verts.new((p.x, p.y, z_bot)) for p in R]
    n = len(L)
    for i in range(n - 1):
        bm.faces.new((lt[i], rt[i], rt[i + 1], lt[i + 1]))
        bm.faces.new((lb[i + 1], rb[i + 1], rb[i], lb[i]))
        bm.faces.new((lt[i + 1], lb[i + 1], lb[i], lt[i]))
        bm.faces.new((rt[i], rb[i], rb[i + 1], rt[i + 1]))
    bm.faces.new((lt[0], lb[0], rb[0], rt[0]))
    bm.faces.new((rt[-1], rb[-1], lb[-1], lt[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return U.mesh_from_bmesh(name, bm, coll, materials=[mat], smooth=False, parent=parent)


def _lathe_obj(name, coll, profile, mat, parent, segments=48, location=(0, 0, 0), rotation=(0, 0, 0),
               caps=True):
    """caps=False for ring-shaped (torus) profiles: a cap there would fill the whole hole."""
    bm = bmesh.new()
    U.bm_lathe(bm, profile, segments=segments, cap_start=caps, cap_end=caps)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return U.mesh_from_bmesh(name, bm, coll, materials=[mat], smooth=math.radians(40), parent=parent,
                             location=location, rotation=rotation)


def _box_obj(name, coll, size, center, mat, parent, rotation=(0, 0, 0), location=(0, 0, 0)):
    bm = bmesh.new()
    U.bm_box(bm, size, center)
    return U.mesh_from_bmesh(name, bm, coll, materials=[mat], smooth=False, parent=parent,
                             rotation=rotation, location=location)


# ---------------------------------------------------------------- pieces

def seat_lawn(lawn, floor_z=TERRACE_Z, clear=LAWN_CLEAR, sink=LAWN_SINK):
    """Keep the lawn off the world terrace's plane (floor_z, flat under the area): every vertex less than ``clear``
    over it goes ``sink`` under it (or stays where it is if it is deeper already), so the lawn meets the terrace at a
    steep angle with no surface within ``clear`` of it. Works on the built object (sect/patch_r12_areas.py seats a
    built file's lawn the same way). Round 12 verify: the lawn is first cut along z = floor_z + clear (bisect), so
    its lip follows the lawn's own smooth contour there; moving whole vertices left a zigzag of the 0.8 m grid along
    the edge. The lip's top edge is sharp and its steep faces are soil, as ground_patch makes steep faces. Returns
    the number of vertices moved (0 when the lawn is seated already)."""
    me = lawn.data
    zc, zs = floor_z + clear, floor_z - sink
    if not any(zs + 1e-6 < v.co.z < zc - 1e-6 for v in me.vertices):
        return 0
    bm = bmesh.new()
    bm.from_mesh(me)
    cut = [f for f in bm.faces
           if min(v.co.z for v in f.verts) < zc - 1e-6 and max(v.co.z for v in f.verts) > zc + 1e-6]
    if cut:
        geom = list({v for f in cut for v in f.verts}) + list({e for f in cut for e in f.edges}) + cut
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=(0.0, 0.0, zc), plane_no=(0.0, 0.0, 1.0))
    moved = set()
    for v in bm.verts:
        if zs + 1e-6 < v.co.z < zc - 1e-6:
            v.co.z = zs
            moved.add(v)
    bm.normal_update()
    for f in {f for v in moved for f in v.link_faces}:
        if f.normal.z <= 0.8:
            f.material_index = 1                    # soil (slot 1 of ground_patch's lawn)
    for e in bm.edges:
        if all(abs(v.co.z - zc) < 1e-6 for v in e.verts) and any(w in moved for f in e.link_faces for w in f.verts):
            e.smooth = False                        # the lawn's top keeps its own normals at the lip
    bm.to_mesh(me)
    bm.free()
    me.update()
    return len(moved)


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


def drum_plinths(st, sink=STEP_SINK):
    """A stone plinth under each drum stone of an arch.stairs flight's balustrades, added to its '.steps' mesh: a box
    DRUM_PLINTH[0] wide (inside the stringer, clear of its faces), from DRUM_PLINTH[1] past the drum's front to where
    the stringer's sloping top climbs past it, its top DRUM_PLINTH[2] over the drum's base (the drum sits in it),
    its bottom ``sink`` under the stair's foot. Reads the drums from the balustrades' point clouds (in the stairs'
    frame) and arch.drum_stone's proportions (1.0 x bal height long, centred 0.05 x ahead of its point, base 0.04
    under it). Works on the built object (sect/patch_r12_areas.py adds them to a built file's). Returns the
    number of plinths added (0 when the mesh has them)."""
    steps = bpy.data.objects[st.name + ".steps"]
    me = steps.data
    if me.get("drum_plinths"):
        return 0
    run, n, riser = float(st["arch_run"]), int(st["arch_steps"]), float(st["arch_riser"])
    height = n * riser
    step_run = run / n

    def ztop(y):                     # the outer stringer's top (arch.stairs' sloped_block, top_off 0.08)
        if y >= -step_run:
            return height + 0.08
        return riser + 0.08 + (height - riser) * (y + run) / (run - step_run)
    w, reach, embed = DRUM_PLINTH
    boxes = []
    for bal in sorted((c for c in st.children if c.name.startswith(st.name + ".bal")), key=lambda o: o.name):
        drums = bpy.data.objects.get(bal.name + ".drums")
        if drums is None:
            continue
        for v in drums.data.vertices:
            x, y0, z0 = v.co
            front = y0 - 0.55               # the drum faces down the stair: its base runs 0.45 back, 0.55 forward
            top = z0 - 0.04 + embed
            # back end: where the stringer's top has climbed DRUM_PLINTH[1] over the plinth's top
            yb = y0
            while yb < 0.0 and ztop(yb) < top + reach:
                yb += 0.01
            boxes.append((x - 0.5 * w, x + 0.5 * w, front - reach, yb, -sink, top))
    if not boxes:
        return 0
    bm = bmesh.new()
    bm.from_mesh(me)
    for x0, x1, ya, yb, za, zb in boxes:
        vs = [bm.verts.new((x, y, z)) for z in (za, zb) for y in (ya, yb) for x in (x0, x1)]
        for f in ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (1, 3, 7, 5), (3, 2, 6, 7), (2, 0, 4, 6)):
            face = bm.faces.new([vs[i] for i in f])
            face.smooth = False
    bm.to_mesh(me)
    bm.free()
    me["drum_plinths"] = len(boxes)
    me.update()
    return len(boxes)


def _ground(coll, root):
    # edge_drop 0.2 (was 0.5): the lawn rim stays above the paths' -0.35 bottoms, so no path
    # hovers over a dip near the rim. Round 12: kept off the terrace's plane round the pond (seat_lawn)
    lawn = N.ground_patch(coll, radius=43.0, seed=5, height=0.08,
                          holes=[(POND_C[0], POND_C[1], POND_R - 0.8, 0.6)], edge_drop=0.2,
                          name=_n("lawn"), parent=root)
    seat_lawn(lawn)
    _strip(_n("path_main"), coll, PATH_MAIN, 3.0, PATH_Z, -0.35, "marble_paving", root)
    _strip(_n("path_east"), coll, PATH_EAST, 2.4, PATH_Z, -0.35, "marble_paving", root)
    _strip(_n("path_forge"), coll, PATH_FORGE, 2.4, PATH_Z, -0.35, "marble_paving", root)
    return lawn


def _landings(coll, root):
    """Where the connector stairs meet the area (AREA arrival / depart), on world.py's -0.4
    terrace. Three 0.173 m steps (max_riser 0.18 keeps the audit's three steps) climb from the
    terrace to each paved landing, so the connector's end step lands flush at their foot."""
    rise = PATH_Z + 0.4
    # arrival: 7 m strip from the path's south end out to y -50.5, steps down to y -51.5
    _strip(_n("arrival"), coll, ARRIVAL, 7.0, PATH_Z, -0.6, "marble_paving", root)
    st = A.stairs(_n("arrival_steps"), coll, 5.0, rise, ramp=False, max_riser=0.18, parent=root,
                  location=(ARRIVAL[0][0], ARRIVAL[0][1], TERRACE_Z))
    # (round 12: each block reaches STEP_SINK into the terrace, and its balustrades' drum stones stand on plinths)
    sink_steps(st, STEP_SINK)
    drum_plinths(st)
    # depart: 6 x 6 m landing on the east rim, steps down its east edge (heading +x)
    cx, cy, s = DEPART_LANDING
    _strip(_n("depart_landing"), coll, [(cx - s / 2, cy), (cx + s / 2, cy)], s, PATH_Z, -0.6,
           "marble_paving", root)
    st = A.stairs(_n("depart_steps"), coll, 5.0, rise, ramp=False, max_riser=0.18, parent=root,
                  location=(cx + s / 2, cy, TERRACE_Z), rotation_z=math.pi / 2)
    sink_steps(st, STEP_SINK)
    drum_plinths(st)


def rim_radius(a):
    """The rail's radius at angle ``a`` (radians, atan2 convention): RIM_R, RIM_R_EAST over
    RIM_EAST, cosine ramps between."""
    lo, hi = RIM_EAST
    half = 0.5 * (hi - lo)
    x = abs((math.degrees(a) - 0.5 * (lo + hi) + 180.0) % 360.0 - 180.0)
    if x <= half:
        return RIM_R_EAST
    if x >= half + RIM_RAMP:
        return RIM_R
    t = (x - half) / RIM_RAMP
    return RIM_R_EAST + (RIM_R - RIM_R_EAST) * (0.5 - 0.5 * math.cos(math.pi * t))


def _rim_crossing(x, y, heading):
    """Angle where a straight line from (x, y) along ``heading`` crosses the rail (rim_radius)."""
    dx, dy = math.cos(heading), math.sin(heading)
    r, a = RIM_R, None
    for _ in range(12):
        b = x * dx + y * dy
        c = x * x + y * y - r * r
        t = -b + math.sqrt(max(0.0, b * b - c))
        a = math.atan2(y + t * dy, x + t * dx)
        r2 = rim_radius(a)
        if abs(r2 - r) < 1e-9:
            break
        r = r2
    return a


def _foot_wall_end(a1):
    """Angle <= a1 where a span ending at the depart opening meets the south wall of the forge
    stair's foot landing: the rail point DEPART_FOOT_WALL + RIM_END_EMBED to the right of the
    depart line (looking along the stair). a1 itself when the span already stops short of it."""
    px, py, _, ph = AREA["depart"]
    want = -(DEPART_FOOT_WALL + RIM_END_EMBED)

    def lateral(a):
        r = rim_radius(a)
        return -(r * math.cos(a) - px) * math.sin(ph) + (r * math.sin(a) - py) * math.cos(ph)

    if lateral(a1) <= want:
        return a1
    lo, hi = a1 - 0.3, a1
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if lateral(mid) > want:
            hi = mid
        else:
            lo = mid
    return lo


def rim_spans():
    """[(a0, a1), ...] radians, counter-clockwise: the rim rail's spans, one from each connector
    opening to the next. The openings (RIM_GAP wide) are centred where each connector stair's
    straight end run crosses the rail; on the depart side the south-east span stops earlier,
    against the forge stair's foot-landing wall (_foot_wall_end). Built in this order: the
    north / west span from the depart opening round to the arrival opening ('mirror.rim_rail'),
    then the south-east span from the arrival opening to that wall ('mirror.rim_rail.001')."""
    ax, ay, _, ah = AREA["arrival"]
    px, py, _, ph = AREA["depart"]
    dep = _rim_crossing(px, py, ph)
    gaps = sorted([_rim_crossing(ax, ay, ah + math.pi), dep])
    spans = []
    for g0, g1 in zip(gaps, gaps[1:] + [gaps[0] + 2.0 * math.pi]):
        a0, a1 = g0 + 0.5 * RIM_GAP / rim_radius(g0), g1 - 0.5 * RIM_GAP / rim_radius(g1)
        if abs(math.remainder(g1 - dep, 2.0 * math.pi)) < 1e-12:
            a1 = _foot_wall_end(a1)
        spans.append((a0, a1))
    return spans[1:] + spans[:1]


def rim_points(a0, a1):
    """Post points (x, y, -0.4) of one rim span, on rim_radius, about 2.5 m apart (arch.balustrade
    adds a post at least every 1.8 m between them)."""
    n = max(2, int(math.ceil((a1 - a0) * RIM_R / 2.5)) + 1)
    out = []
    for i in range(n):
        a = a0 + (a1 - a0) * i / (n - 1)
        r = rim_radius(a)
        out.append((r * math.cos(a), r * math.sin(a), -0.4))
    return out


def _rim_rails(coll, root):
    """Stone rail on the terrace (-0.4) right round the rim (rim_spans), open where each
    connector stair crosses it. One span per pair of openings, so no post is doubled where a
    full circle would close on itself."""
    for a0, a1 in rim_spans():
        A.balustrade(_n("rim_rail"), coll, rim_points(a0, a1), height=1.0, parent=root)


def _pond(coll, root):
    pond = N.pond(coll, radius=POND_R, seed=3, depth=1.4, water_level=WATER_Z, reeds=True,
                  name=_n("pond"), parent=root, location=(POND_C[0], POND_C[1], 0.0), rotation=0.0)
    for k, (x, y, r, cnt) in enumerate(((6.0, -7.0, 3.2, 20), (-14.0, -12.0, 2.2, 12),
                                        (3.0, 7.0, 2.4, 12))):
        N.lotus_patch(coll, radius=r, count=cnt, seed=11 + k, name=_n("lotus"), parent=root,
                      location=(x, y, WATER_Z + LOTUS_LIFT))
    return pond


def _pavilion(coll, root):
    A.platform(_n("isle"), coll, ISLE_W, sides=6, height=0.75, sink=1.4, parent=root,
               location=(ISLE_C[0], ISLE_C[1], DECK_Z - 0.75))
    # rail round the island, 0.35 m in from its edge, open ISLE_RAIL_GAP wide where the bridge
    # lands on the south face (corners from the south-east one round to the south-west one)
    r = ISLE_W / 2 - 0.35 / math.cos(math.pi / 6)
    ys = ISLE_C[1] - r * math.cos(math.pi / 6)
    gx = BRIDGE[-1][0]
    pts = [(gx + ISLE_RAIL_GAP / 2, ys)]
    pts += [(ISLE_C[0] + r * math.cos(math.radians(a)), ISLE_C[1] + r * math.sin(math.radians(a)))
            for a in (-60, 0, 60, 120, 180, -120)]
    pts.append((gx - ISLE_RAIL_GAP / 2, ys))
    A.balustrade(_n("isle_rail"), coll, [(x, y, DECK_Z) for x, y in pts], height=0.75,
                 post_spacing=1.7, parent=root)
    ting = A.pavilion(_n("ting"), coll, sides=6, radius=3.2, height=3.6, roof="pyramid",
                      roof_mat="roof_tile_teal", platform_h=0.45, parent=root,
                      location=(ISLE_C[0], ISLE_C[1], DECK_Z))
    # the area's plaque 心镜台, hung under the front eave over the entry face (front face is flat, -Y)
    z0 = DECK_Z + 0.45
    # (on the architrave, below the bracket band, so the deep eave does not hide it from above)
    P.plaque(coll, AREA["title_zh"], 2.2, name=_n("plaque"), parent=root,
             location=(ISLE_C[0], ISLE_C[1] - (3.2 * math.cos(math.pi / 6) + 0.35), z0 + 3.6 - 0.3))
    # a pair of red silk lanterns at the pavilion's front eave corners, the cord's top in the eave soffit (round 5
    # float scan: hung from column top + 0.2 m they dangled 0.19 m under the soffit, from nothing)
    r_eave = 3.2 + 1.2
    for s in (-1, 1):
        a = -math.pi / 2 + s * math.pi / 6
        x, y = ISLE_C[0] + r_eave * math.cos(a), ISLE_C[1] + r_eave * math.sin(a)
        z = _soffit_z(ting, root, x, y, DECK_Z + 0.45 + 3.6, DECK_Z + 0.45 + 3.6 + 0.2)
        P.lantern_hanging(coll, "round", 0.8, cord=0.3, name=_n("ting_lantern"), parent=root,
                          location=(x, y, z + LANTERN_HOOK_IN))
    return ting


LANTERN_HOOK_IN = 0.02        # a hanging lantern's suspension point sits this far up inside the soffit it hangs from


def _soffit_z(building, root, x, y, z_from, fallback):
    """Height (root frame) of the underside of ``building``'s roof straight above (x, y), cast up from z_from;
    ``fallback`` if the ray misses."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    best = None
    for ob in building.children_recursive:
        if ob.type != 'MESH' or ".roof" not in ob.name[len(building.name):]:
            continue
        M = ob.matrix_parent_inverse @ ob.matrix_basis      # local matrices from the transforms themselves: valid
        p = ob.parent                                         # before the depsgraph has evaluated a fresh build
        while p is not None and p != root:
            M = p.matrix_parent_inverse @ p.matrix_basis @ M
            p = p.parent
        bvh = BVHTree.FromPolygons([M @ v.co for v in ob.data.vertices], [tuple(f.vertices) for f in ob.data.polygons])
        hit = bvh.ray_cast(Vector((x, y, z_from)), Vector((0.0, 0.0, 1.0)), 10.0)
        if hit[0] is not None and (best is None or hit[0].z < best):
            best = hit[0].z
    return fallback if best is None else best


def _bridge(coll, root):
    # 1 cm under the island top, so the end that overlaps the island face never z-fights
    deck = _strip(_n("bridge_deck"), coll, BRIDGE, 2.2, DECK_Z - 0.01, DECK_Z - 0.32, "marble_white", root)
    # three 0.14 m risers from the entry path (ends at y -26) up to the deck's land end
    A.stairs(_n("bridge_steps"), coll, 2.2, DECK_Z - 0.01 - PATH_Z, ramp=False, balustrade=False,
             stringer=0.25, parent=root, location=(BRIDGE[0][0], BRIDGE[0][1], PATH_Z))
    bm = bmesh.new()
    for x, y in BRIDGE[1:-1]:
        U.bm_box(bm, (0.9, 0.9, 1.6), (x, y, DECK_Z - 0.32 - 0.8))
    U.mesh_from_bmesh(_n("bridge_piers"), bm, coll, materials=["stone_grey"], smooth=False, parent=root)
    L, R = _miter(BRIDGE[1:], 1.85)
    for side, pts in (("l", L), ("r", R)):
        A.balustrade(_n("bridge_rail_" + side), coll, [(p.x, p.y, DECK_Z) for p in pts], height=0.75,
                     post_spacing=1.7, parent=root)
    return deck


def _mirror(coll, shrine):
    """Giant round bronze mirror held upright in a gilt lotus cradle by two red lacquer cloud
    arms, on a marble plinth (shrine-local, origin on the dais top)."""
    z0 = DAIS_H
    st = U.empty(_n("mirror_stand"), coll, location=(0.0, 0.8, z0), parent=shrine)
    A.platform(_n("mirror_plinth"), coll, 7.4, 3.8, height=1.0, sink=0.2, parent=st)
    zb = 1.0
    R = MIRROR_R
    # bronze vase-shaped pedestal and a gilt lotus cup
    _lathe_obj(_n("mirror_pedestal"), coll, [(0, 0), (1.6, 0), (1.6, 0.22), (1.15, 0.38), (0.78, 0.95),
                                             (0.66, 1.4), (0.95, 1.7), (0, 1.7)], "bronze_verdigris", st,
               segments=32, location=(0, 0, zb))
    _lathe_obj(_n("mirror_cradle"), coll, [(0, 0), (0.95, 0), (1.7, 0.25), (2.35, 0.75), (2.05, 0.86),
                                           (1.3, 0.55), (0, 0.55)], "gold", st, segments=32,
               location=(0, 0, zb + 1.6))
    zc = zb + 1.6 + 0.4 + R                  # disc centre
    # the disc frame: local Z = mirror normal (faces -Y, tilted back), local Y ~ up
    disc = U.empty(_n("mirror_disc"), coll, location=(0, 0, zc), rotation=(math.pi / 2 - MIRROR_TILT, 0, 0),
                   parent=st)
    _lathe_obj(_n("mirror_back"), coll, [(0, -0.55), (0.55, -0.55), (0.7, -0.3), (R - 0.1, -0.3), (R - 0.1, 0.1),
                                         (0, 0.1)], "bronze_verdigris", disc, segments=64)
    _lathe_obj(_n("mirror_face"), coll, [(0, 0.08), (R - 0.12, 0.08), (R - 0.12, 0.2), (0, 0.2)],
               "mirror_face", disc, segments=64)
    # closed ring cross-section (first point repeated), no caps: the rim must not cover the face
    _lathe_obj(_n("mirror_rim"), coll, [(R - 0.2, -0.36), (R + 0.14, -0.32), (R + 0.3, -0.05), (R + 0.22, 0.26),
                                        (R - 0.05, 0.36), (R - 0.2, 0.32), (R - 0.2, -0.36)], "gold", disc,
               segments=72, caps=False)
    P.rune_ring(coll, R - 0.62, 0.55, "trigram", material="rune_cyan", seed=2, name=_n("mirror_runes"),
                parent=disc, location=(0, 0, 0.205))
    # two cloud arms rising from the cradle and hugging the rim, ending in gold pearls
    ra = R + 0.62
    for s in (-1, 1):
        pts = []
        for deg in (-78, -60, -40, -20, 0, 20, 38, 52):
            a = math.radians(deg)
            pts.append((s * ra * math.cos(a), ra * math.sin(a), -0.05))
        a = math.radians(62)
        pts.append((s * (ra + 0.25) * math.cos(a), (ra + 0.25) * math.sin(a), -0.05, 0.8))
        U.tube_mesh(_n("mirror_arm"), pts, 0.24, coll, material="lacquer_red", sides=10, parent=disc)
        a = math.radians(64)
        _lathe_obj(_n("mirror_pearl"), coll, [(0, -0.4), (0.3, -0.3), (0.4, 0.0), (0.3, 0.3), (0, 0.4)], "gold", disc,
                   segments=16, location=(s * (ra + 0.3) * math.cos(a), (ra + 0.3) * math.sin(a), -0.05))
    # flaming-pearl crest on top of the rim
    _lathe_obj(_n("mirror_crest"), coll, [(0, 0), (0.55, 0.1), (0.75, 0.45), (0.55, 0.9), (0.25, 1.3), (0, 1.75)],
               "gold", disc, segments=20, location=(0, R + 0.2, -0.05), rotation=(-math.pi / 2, 0, 0))
    st["mirror_center_z"] = zc
    return st


def _shrine(coll, root):
    sh = U.empty(_n("shrine"), coll, location=(SHRINE_C[0], SHRINE_C[1], 0.0), rotation=(0, 0, SHRINE_YAW),
                 parent=root)
    A.platform(_n("dais"), coll, DAIS_W, DAIS_D, height=DAIS_H, parent=sh)
    A.stairs(_n("dais_stairs"), coll, 7.0, DAIS_H, ramp=True, parent=sh, location=(0, -DAIS_D / 2, 0))
    hw, hd = DAIS_W / 2 - 0.35, DAIS_D / 2 - 0.35
    A.balustrade(_n("dais_rail"), coll, [(-3.9, -hd, DAIS_H), (-hw, -hd, DAIS_H), (-hw, hd, DAIS_H),
                                         (hw, hd, DAIS_H), (hw, -hd, DAIS_H), (3.9, -hd, DAIS_H)],
                 height=1.0, parent=sh)
    _mirror(coll, sh)
    P.incense_burner(coll, 1.5, smoke=True, name=_n("censer"), parent=sh, location=(0, -3.2, DAIS_H))
    # lanterns tucked beside the stair against the dais face, clear of the walk in front
    for s in (-1, 1):
        P.lantern_stone(coll, 2.6, name=_n("lantern"), parent=sh, location=(s * 4.6, -DAIS_D / 2 - 0.6, 0))
    # shore walk: flat paving in front of the dais stair, where the east path ends (built in the
    # root's space like the paths, so overlapping paving shades identically)
    _strip(_n("shore_walk"), coll, [_shrine_pt(-SHORE_X, SHORE_Y), _shrine_pt(SHORE_X, SHORE_Y)], 2.0,
           PATH_Z, -0.35, "marble_paving", root)
    return sh


def _garden(coll, root):
    # one big peach tree beside the mirror dais (east), clear of the pavilion silhouette
    N.blossom_tree(coll, height=12.0, seed=1, kind="peach", name=_n("blossom"), parent=root,
                   location=(21.5, 29.0, 0.0), rotation=math.radians(200))
    # Huangshan pines on the west rim frame the garden against the cloud sea
    for k, (x, y, h) in enumerate(((-30.0, 21.0, 12.5), (-35.0, -5.0, 10.0), (31.0, -22.0, 10.5))):
        N.pine(coll, height=h, seed=2 + k, name=_n("pine"), parent=root, location=(x, y, 0.0))
    # paired stone lanterns line the entry path to the bridge (second pair south of the east
    # path's branch at y -29)
    for y in (-38.0, -32.0):
        for s in (-1, 1):
            P.lantern_stone(coll, 2.2, name=_n("path_lantern"), parent=root, location=(-5.0 + s * 2.8, y, 0.0))
    N.rock(coll, size=4.2, seed=2, kind="scholar", name=_n("taihu"), parent=root, location=(12.5, -13.0, 0.0),
           rotation=math.radians(200))
    N.rock(coll, size=3.0, seed=4, kind="scholar", name=_n("taihu"), parent=root, location=(-22.5, -2.0, 0.0),
           rotation=math.radians(40))
    for k, (x, y, s) in enumerate(((-14.5, 15.0, 1.6), (-21.0, 17.5, 1.2), (15.5, -12.5, 1.4), (-21.5, -9.5, 1.1))):
        N.rock(coll, size=s, seed=20 + k, kind="boulder", name=_n("boulder"), parent=root, location=(x, y, -0.1))
    for k, (x, y) in enumerate(((-12.0, 18.5), (17.0, 14.0), (-22.0, 10.0))):
        N.shrub(coll, size=2.2, seed=k, kind="azalea" if k % 2 else "green", name=_n("shrub"), parent=root,
                location=(x, y, 0.0))


# ---------------------------------------------------------------- Huang Yaoshi's jade flute 玉簫 (round 7)
# The Legend of the Condor Heroes: Huang Yaoshi 黄药师, the Eastern Heretic and master of Peach Blossom Island 桃花岛,
# plays 碧海潮生曲 on his jade xiao; his island's peach maze is laid out on the eight trigrams, like the mirror's ring. Here
# he has just put it down by the peach-garden pond: a flat dark slate 青石 at the east rim, the pale jade flute (finger
# holes up, U notch at the blowing end) lying on it, pale on dark so it still reads from the hold, its empty red
# brocade bag 簫囊 beside it with a gold drawstring, its gold cord, knot, jade bead and tassel hanging over the stone's
# front edge, a small peach tree 桃 just behind the stone leaning over it, and its fallen petals on the stone, the lawn,
# the bank and the water. (A red cloth draped over the whole stone read as a red chest from the hold, so the bag lies
# flat behind the flute; the small tree is what pulls the eye to the stone from the hold and makes the pond read as a
# peach garden.) Builders: sect/lib/flute_props.py (set frame: +x along the flute, -y toward the
# hold camera). Every piece rests on what is under it (the stone sunk 0.3-0.45 m into the lawn); static, no hotspot.
#
# Placement: the 217 hold camera (mirror.root (8.4, -48.6, 18.5), lens 32) sees the pond's east rim ~51 m off, lower
# middle of the frame; the flute (1.9 m, ~2.5x a real xiao like the abode's) is ~55 px long there at 1600 px. The
# pavilion's long shadow (sun 7 deg above the west) lies on the rim from y -9 to -2, so the set sits just north of it,
# in sun, on the lawn between the pond bank (rim stones to x 14.1) and the east path (west edge x 17.35), turned
# FLUTE_YAW so the flute lies square to the hold camera's line of sight. Objects FLUTE and FLUTE + '_' + part, every
# one tagged obj['sect_item'] = FLUTE_ITEM (sect/patch_r7_flute.py finds them by it).
FLUTE = KEY + ".flute"
FLUTE_ITEM = "jade_flute"
FLUTE_LOC = (15.75, -0.25)
FLUTE_YAW = math.radians(-6.0)
FLUTE_TRI_CAP = 8000                    # per object
FLUTE_PARTS = ("rock", "bag", "xiao", "tassel", "petals")       # meshes FLUTE + '_' + part, children of FLUTE
FLUTE_TREE = FLUTE + "_peach"            # the small peach tree: an instance of the peach v3 'mid' prototype (already
                                         # in the sect: the abode's and the library's peaches), no new prototype
FLUTE_TREE_AT = (16.3, 2.5)              # mirror.root (x, y): on the lawn 2.7 m behind the stone, clear of the east path
FLUTE_TREE_H, FLUTE_TREE_SEED, FLUTE_TREE_ROT = 4.2, 3, math.radians(205.0)   # its height, variant, world heading
FLUTE_PETALS = (24, 170, 60, 70)        # on the stone and bag, round the stone, on the pond, under the tree
FLUTE_WATER_BOX = (-3.9, -2.15, -1.3, 2.6)     # set frame (x0, x1, y0, y1): the pond along the bank west of the stone
# what the petals may lie on: object name prefix under mirror.root -> kind
FLUTE_GROUND = (("lawn", "ground"), ("pond.basin", "ground"), ("pond.stone", "stone"), ("pond.water", "water"),
                ("path_", "path"), ("shore_walk", "path"))


def flute_names():
    return [FLUTE] + ["%s_%s" % (FLUTE, p) for p in FLUTE_PARTS] + [FLUTE_TREE]


def flute_matrix():
    """The set frame in mirror.root's frame."""
    from mathutils import Matrix
    return Matrix.Translation((FLUTE_LOC[0], FLUTE_LOC[1], 0.0)) @ Matrix.Rotation(FLUTE_YAW, 4, 'Z')


def _root_local(ob, root):
    """ob's matrix in root's frame from the transforms themselves (valid before a fresh build's depsgraph update)."""
    M_ = ob.matrix_parent_inverse @ ob.matrix_basis
    p = ob.parent
    while p is not None and p != root:
        M_ = p.matrix_parent_inverse @ p.matrix_basis @ M_
        p = p.parent
    return M_


def flute_scene(root):
    """[(object name, kind, set-frame vertices, polygons)] of the scene pieces the petals may lie on."""
    import bpy
    Si = flute_matrix().inverted()
    out = []
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or not ob.name.startswith(KEY + "."):
            continue
        tail = ob.name[len(KEY) + 1:]
        kind = next((k for pre, k in FLUTE_GROUND if tail.startswith(pre)), None)
        if kind is None:
            continue
        q = ob
        while q is not None and q != root:
            q = q.parent
        if q is None:
            continue
        T = Si @ _root_local(ob, root)
        out.append((ob.name, kind, [T @ v.co for v in ob.data.vertices], [tuple(p.vertices) for p in ob.data.polygons]))
    return out


def _flute(coll, root):
    """Huang Yaoshi's jade flute set: Empty FLUTE under ``root`` at FLUTE_LOC (z 0) turned FLUTE_YAW, and its five
    meshes (stone, bag, flute, cord and tassel, petals), every object tagged obj['sect_item'] = FLUTE_ITEM.
    Returns the Empty."""
    import bmesh as _bm
    from mathutils import Vector as V3
    from mathutils.bvhtree import BVHTree
    from sect.lib import flute_props as FP

    rock = FP.rock_bm()
    bag = FP.bag_bm(FP.bvh_of([rock]))
    set_bvh = FP.bvh_of([rock, bag])
    m, _rest = FP.flute_matrix(set_bvh)
    xiao = FP.flute_bm()
    _bm.ops.transform(xiao, matrix=m, verts=xiao.verts)
    tassel, _low, _tc = FP.tassel_bm(m, set_bvh)
    all_bvh = FP.bvh_of([rock, bag, xiao, tassel])

    # the scene under the set (set frame) + the set's own pieces as kind 'set'
    verts, polys, kinds = [], [], []
    for _nm, kind, vs, ps in flute_scene(root):
        base = len(verts)
        verts.extend(vs)
        polys.extend(tuple(base + i for i in p) for p in ps)
        kinds.extend([kind] * len(ps))
    for bm in (rock, bag, xiao, tassel):
        bm.verts.index_update()
        base = len(verts)
        verts.extend(v.co.copy() for v in bm.verts)
        polys.extend(tuple(base + v.index for v in f.verts) for f in bm.faces)
        kinds.extend(["set"] * len(bm.faces))
    scene_bvh = BVHTree.FromPolygons(verts, polys)

    def sampler(x, y):
        h = scene_bvh.ray_cast(V3((x, y, 4.0)), V3((0.0, 0.0, -1.0)), 12.0)
        if h[0] is None:
            return None
        n = h[1] if h[1].z >= 0 else -h[1]
        return h[0], n, kinds[h[2]]

    def top_sampler(x, y):
        a = all_bvh.ray_cast(V3((x, y, 3.0)), V3((0.0, 0.0, -1.0)), 6.0)
        b = set_bvh.ray_cast(V3((x, y, 3.0)), V3((0.0, 0.0, -1.0)), 6.0)
        if b[0] is None or a[0] is None or a[0].z > b[0].z + 1e-4:     # missed, or the flute / cord is on top
            return None
        return b[0], (b[1] if b[1].z >= 0 else -b[1])

    cord_x = (FP.hole_point(m, *FP.HOLES[5]).x - 0.08, FP.hole_point(m, *FP.HOLES[5]).x + 0.16)

    def keep_off(x, y):
        return cord_x[0] <= x <= cord_x[1] and y < FP.FLUTE_Y + 0.06

    # the small peach tree behind the stone (set frame), its trunk base on the ground under it
    tp = flute_matrix().inverted() @ V3((FLUTE_TREE_AT[0], FLUTE_TREE_AT[1], 0.0))
    tg = sampler(tp.x, tp.y)
    if tg is None or tg[2] != "ground":
        raise RuntimeError("flute: the peach tree's spot (%.2f, %.2f) is not on the lawn" % FLUTE_TREE_AT)
    tp.z = tg[0].z

    rng = U.rng("mirror.flute.petals", 7)
    n_top, n_ground, n_water, n_tree = FLUTE_PETALS
    spots = FP.scatter_petals(rng, sampler, (0.0, 0.0), n_top, n_ground,
                              lambda x, y: ((sampler(x, y) or (None, None, "set"))[2] == "set"
                                            or (x - tp.x) ** 2 + (y - tp.y) ** 2 < 0.3 ** 2),
                              top_sampler, keep_off, extra=((tp.x, tp.y, 1.0, 0.8, n_tree),))
    spots += FP.scatter_water(rng, sampler, FLUTE_WATER_BOX, n_water)
    # hard surfaces (rim stones, paving, water, the set itself): a petal that clips one anywhere is dropped (the lawn
    # and the bank are soft ground, a petal may dip into them by a hair)
    hard = BVHTree.FromPolygons(verts, [p for p, k in zip(polys, kinds) if k != "ground"])
    petals = _bm.new()
    kept = 0
    for pt, nrm, yaw, L, W, _where in spots:
        one = _bm.new()
        FP.add_petal(one, pt, nrm, yaw, L, W)
        if BVHTree.FromBMesh(one).overlap(hard):
            one.free()
            continue
        one.free()
        FP.add_petal(petals, pt, nrm, yaw, L, W)
        kept += 1
    _bm.ops.recalc_face_normals(petals, faces=petals.faces[:])

    em = U.empty(FLUTE, coll, location=(FLUTE_LOC[0], FLUTE_LOC[1], 0.0), rotation=(0.0, 0.0, FLUTE_YAW),
                 parent=root, display_size=1.0)
    em["sect_item"] = FLUTE_ITEM
    parts = (("rock", rock, [FP.STONE], math.radians(50)), ("bag", bag, [FP.SILK, FP.TRIM], math.radians(70)),
             ("xiao", xiao, [FP.JADE, FP.HOLE], math.radians(40)), ("tassel", tassel, [FP.TRIM, FP.JADE],
                                                                    math.radians(50)),
             ("petals", petals, [FP.PETAL], math.radians(60)))
    for part, bm, mats, smooth in parts:
        ob = U.mesh_from_bmesh("%s_%s" % (FLUTE, part), bm, coll, materials=mats, smooth=smooth, parent=em)
        ob["sect_item"] = FLUTE_ITEM
    tree = N.blossom_tree(coll, height=FLUTE_TREE_H, seed=FLUTE_TREE_SEED, kind="peach", lod="mid", name=FLUTE_TREE,
                          parent=em,
                          location=(tp.x, tp.y, tp.z), rotation=FLUTE_TREE_ROT - FLUTE_YAW)
    tree["sect_item"] = FLUTE_ITEM
    em["petals"] = kept
    em["petals_dropped"] = len(spots) - kept
    return em


def build(collection):
    """Build the Heart-Mirror Terrace at the local origin. Returns 'mirror.root'."""
    root = U.empty("%s.root" % KEY, collection, display_size=4.0)
    _ground(collection, root)
    _landings(collection, root)
    _rim_rails(collection, root)
    _pond(collection, root)
    _pavilion(collection, root)
    _bridge(collection, root)
    _shrine(collection, root)
    _garden(collection, root)
    # Huang Yaoshi's jade flute on its stone at the pond's east rim (after the lawn, pond and paths it lies on)
    _flute(collection, root)
    root["area_key"] = KEY
    root["title_zh"] = AREA["title_zh"]
    return root


# preview harness: lets look.py --cams name the CAMERA_HINTS views
build.preview_cameras = [(h["name"], h["location"], h["target"], h["lens"]) for h in CAMERA_HINTS]
