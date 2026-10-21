"""Scripture Pavilion 藏经阁 (site section 'education').

Blocking layout: a tall 7-storey octagonal pagoda library (about 46 m) on a marble plaza, with
3 glowing floors (the three schools), a lotus pool on its south-west side, two small study
pavilions, pines, bamboo and stone lanterns. Glowing hand scrolls and books drift in a slow
spiral around the pagoda: one parent Empty rotating with linear keyframes over frames 1-1500.

Route (docs/architecture-audit.md 1.6): the stair from the Mission Hall tops out on an arrival
landing on the axis at the south rim, under a three-bay entrance gate; three low steps lead up
to the axis walkway and the pagoda plaza. The way out to the Stele Forest is a paved path from
the plaza's south-west face, north of the lotus pool, ending in four low steps down to the
stair head at the west rim. Both stair heads have rim balustrades with a gap for the stair.

Local frame: origin = plateau centre, z = 0 walkable, front faces -Y.
"""
import math

import bmesh
import bpy

from sect.lib import util as U
from sect.lib import arch as A
from sect.lib import props as P
from sect.lib import nature as N
from sect.lib import materials as M

# Connector ends for world.py (local frame): (x, y, z, heading). heading = walking direction in
# radians, counter-clockwise from +X (atan2 convention, like world.py yaws): pi/2 is +Y.
# arrival: the stair from the Mission Hall tops out here on the axis, walking +Y onto the landing.
# depart: the stair to the Stele Forest starts here, at the foot of the west path's steps, and
# leaves straight along that path's line (bearing ~195.8 deg; the steles lie at ~193.6 deg).
DEPART_PATH_START = (-10.0, -1.0)     # plaza south-west face
DEPART_XY = (-44.7, -10.8)
DEPART_HEADING = math.atan2(DEPART_XY[1] - DEPART_PATH_START[1], DEPART_XY[0] - DEPART_PATH_START[0])

AREA = dict(key="library", section_id="education", title_en="Scripture Pavilion",
            title_zh="藏经阁", footprint=42.0,
            arrival=(0.0, -49.0, -0.25, math.pi / 2),
            depart=(DEPART_XY[0], DEPART_XY[1], -0.4, DEPART_HEADING))

KEY = AREA["key"]

# Layout (local metres)
PAGODA_XY = (0.0, 8.0)        # pagoda centre
PLAZA_TOP = 0.15              # marble plaza / path top
PLAZA_R = 14.0                # octagonal plaza circumradius around the pagoda
POND_XY = (-21.0, -15.0)
POND_R = 7.5
PAGODA_RADIUS = 7.0
PAGODA_TIER_H = 5.5
LIT_FLOORS = (1, 3, 5)        # three schools: Lynbrook, UCSC, USC

# Route geometry (audit 1.6 and section 4)
TERRACE_Z = -0.4              # world.py terrace (grass) level under the area
ARRIVAL_TOP = -0.25           # arrival landing top
DEPART_W = 3.0                # west path / steps width
DEPART_STEP_H = PLAZA_TOP - TERRACE_Z     # 0.55: path top down to the stair head
STEP_RUN = 0.33               # arch.stairs default tread
RIM_RAIL_R = 50.0             # rim rail radius (the world terrace edge is at r = 51 here)
RIM_RAIL_LEN = 8.0            # rail length on each side of a stair head
RIM_GAP_HALF = 3.5            # half the opening left for a 5 m connector stair (its rails at ~2.9)

# Scroll spiral
SPIRAL_FRAMES = (1, 1500)
SPIRAL_TURNS = 1.0            # parent rotation over the frame range (slow)
N_SCROLLS = 26

# Where the fly-through camera should pass (local, front = -Y). Ordered along the flight:
# arrive from the south, curve round the west side of the pagoda while rising through the
# scroll spiral, leave high on the west-north-west.
CAMERA_HINTS = [
    dict(name="approach", location=(-10.0, -80.0, 13.0), target=(0.0, 8.0, 20.0), lens=30),
    dict(name="sweep", location=(-20.0, -14.0, 22.0), target=(0.0, 8.0, 24.0), lens=24),
    dict(name="rise", location=(-27.0, 14.0, 36.0), target=(0.0, 8.0, 32.0), lens=26),
    dict(name="depart", location=(-42.0, 36.0, 54.0), target=(0.0, 8.0, 30.0), lens=26),
]


def _n(*parts):
    return U.name(KEY, *parts)


# ----------------------------------------------------------------------------- ground

def _slab(name, coll, root, x0, x1, y0, y1, top=PLAZA_TOP, bottom=-0.5, mat="marble_paving"):
    bm = bmesh.new()
    U.bm_box(bm, (x1 - x0, y1 - y0, top - bottom), ((x0 + x1) / 2, (y0 + y1) / 2, (top + bottom) / 2))
    return U.mesh_from_bmesh(name, bm, coll, materials=[mat], parent=root)


def _ground(coll, root):
    # lawn with the pond basin dug into it
    N.ground_patch(coll, radius=40.0, seed=61, height=0.12, edge_drop=0.5,
                   holes=[(POND_XY[0], POND_XY[1], POND_R + 1.2, 1.3)],
                   name=_n("lawn"), parent=root)
    # octagonal marble plaza round the pagoda
    A.platform(_n("plaza"), coll, 2 * PLAZA_R, sides=8, height=0.45, style="plain", sink=0.3,
               parent=root, location=(PAGODA_XY[0], PAGODA_XY[1], PLAZA_TOP - 0.45))
    ap = PLAZA_R * math.cos(math.pi / 8)
    front_y = PAGODA_XY[1] - ap
    # main axis path from the south edge to the plaza
    _slab(_n("path_main"), coll, root, -4.0, 4.0, -40.0, front_y + 0.5)
    # side paths to the two study pavilions
    _slab(_n("path_east"), coll, root, 3.5, 19.0, -11.5, -8.5)
    _slab(_n("path_west"), coll, root, -21.0, PAGODA_XY[0] - ap + 0.5, 9.0, 12.0)
    _arrival(coll, root)
    _depart(coll, root)


def _strip(name, coll, root, p0, p1, width, top, bottom, mat="marble_paving"):
    """Straight paved strip ``width`` wide from p0 to p1 (XY), top at ``top``."""
    (x0, y0), (x1, y1) = p0, p1
    length = math.hypot(x1 - x0, y1 - y0)
    m = U.trs(((x0 + x1) / 2, (y0 + y1) / 2, 0.0), (0.0, 0.0, math.atan2(y1 - y0, x1 - x0)))
    bm = bmesh.new()
    U.bm_box(bm, (length, width, top - bottom), (0.0, 0.0, (top + bottom) / 2), matrix=m)
    return U.mesh_from_bmesh(name, bm, coll, materials=[mat], parent=root)


def _arrival(coll, root):
    """Arrival from the Mission Hall (audit 1.6 item 2): landing on the axis, entrance gate,
    three low steps up to the axis walkway, and a rim balustrade either side of the stair head."""
    x, y0, z, _ = AREA["arrival"]
    _slab(_n("arrival_landing"), coll, root, -6.0, 6.0, y0, -41.0, top=ARRIVAL_TOP, bottom=-0.6)
    A.stairs(_n("arrival_steps"), coll, 8.0, PLAZA_TOP - ARRIVAL_TOP, ramp=False, balustrade=False,
             parent=root, location=(0.0, -40.0, ARRIVAL_TOP))
    gate = A.paifang(_n("arrival_gate"), coll, bays=3, width=12.0, height=9.0, parent=root,
                     location=(0.0, -42.5, ARRIVAL_TOP))
    anchor = bpy.data.objects[gate["plaque_anchor"]]
    w, h = (float(v) for v in gate["plaque_size"])
    P.plaque(coll, AREA["title_zh"], min(w, h * 2.6), tilt=0.0, name=_n("gate_plaque"), parent=anchor)
    # landing's south edge, carried on along the rim: 8 m each side of the 7 m stair opening;
    # it steps down off the landing (top -0.25) onto the terrace grass (-0.4)
    yb = y0 + 0.2
    for sx in (-1, 1):
        x0 = x + sx * RIM_GAP_HALF
        A.balustrade(_n("arrival_rail"), coll,
                     [(x0, yb, ARRIVAL_TOP), (sx * 5.7, yb, ARRIVAL_TOP), (sx * 6.3, yb, TERRACE_Z),
                      (x0 + sx * RIM_RAIL_LEN, yb, TERRACE_Z)],
                     height=1.0, end_drum="start", parent=root)


def _ray_circle(p, heading, r):
    """Point where the ray from p (inside the circle) along ``heading`` leaves radius r."""
    dx, dy = math.cos(heading), math.sin(heading)
    b = p[0] * dx + p[1] * dy
    s = -b + math.sqrt(b * b - (p[0] ** 2 + p[1] ** 2 - r * r))
    return p[0] + s * dx, p[1] + s * dy


def _depart(coll, root):
    """Way out to the Stele Forest (audit 1.6 item 3): a 3 m paved path from the plaza's
    south-west face, north of the lotus pool, then four low steps down to the stair head, all on
    one straight line along the depart heading; rim balustrade either side of the stair."""
    hd = DEPART_HEADING
    dx, dy = math.cos(hd), math.sin(hd)
    run = math.ceil(DEPART_STEP_H / 0.17 - 1e-6) * STEP_RUN      # arch.stairs' horizontal run
    top_edge = (DEPART_XY[0] - dx * run, DEPART_XY[1] - dy * run)
    # start 2.5 m back inside the plaza so the diagonal end is covered; 4 mm under the plaza top
    start = (DEPART_PATH_START[0] - dx * 2.5, DEPART_PATH_START[1] - dy * 2.5)
    _strip(_n("depart_path", "walk"), coll, root, start, top_edge, DEPART_W, PLAZA_TOP - 0.004, -0.6)
    A.stairs(_n("depart_steps"), coll, DEPART_W, DEPART_STEP_H, ramp=False, balustrade=False,
             parent=root, location=(top_edge[0], top_edge[1], TERRACE_Z), rotation_z=hd + math.pi / 2)
    # rim rail: arcs on r = RIM_RAIL_R either side of where the outgoing stair crosses it
    cx, cy = _ray_circle(DEPART_XY, hd, RIM_RAIL_R)
    ac = math.atan2(cy, cx)
    a_gap = math.asin(RIM_GAP_HALF / RIM_RAIL_R)
    a_len = RIM_RAIL_LEN / RIM_RAIL_R
    n = max(2, int(math.ceil(RIM_RAIL_LEN / 1.8)))
    for sgn in (-1, 1):
        pts = []
        for i in range(n + 1):
            a = ac + sgn * (a_gap + a_len * i / n)
            pts.append((RIM_RAIL_R * math.cos(a), RIM_RAIL_R * math.sin(a), TERRACE_Z))
        A.balustrade(_n("depart_rail"), coll, pts, height=1.0, end_drum="start", parent=root)


# ----------------------------------------------------------------------------- pagoda

COS8 = math.cos(math.pi / 8)

M.variant("library_lamplight", "paper_screen_lit", lit="#ffa94d", strength=26.0, translucency=0.0)
M.variant("library_scroll_halo", "props_flare", colour="#ffb347", core="#fff0c8", strength=2.2)
_COVERS = ["banner_4", "cloth_teal", "props_cover_ochre", "props_cover_brown", "cloth_red"]


def _oct_ring(r):
    """Octagon corners matching arch.pagoda (face 0 centred on -Y)."""
    return [(r * math.cos(-math.pi / 2 - math.pi / 8 + 2 * math.pi * k / 8),
             r * math.sin(-math.pi / 2 - math.pi / 8 + 2 * math.pi * k / 8)) for k in range(8)]


def _prism(apothem, z0, z1):
    ring = _oct_ring(apothem / COS8)
    verts = [(x, y, z0) for x, y in ring] + [(x, y, z1) for x, y in ring]
    faces = [tuple(range(7, -1, -1)), tuple(range(8, 16))]
    faces += [(k, (k + 1) % 8, 8 + (k + 1) % 8, 8 + k) for k in range(8)]
    return verts, faces


def _lit_storey(coll, pag, k, z0, band_z):
    """Open the lattice of a lit storey and fill it with a warm glowing core ringed by bookshelves."""
    r = PAGODA_RADIUS * (1.0 - 0.065 * k)
    ap = r * COS8
    cr = min(max(0.028 * r + 0.17, 0.2), 0.42)
    wt = 2 * cr * 0.85
    hb = A.band_height_for(2 * r) * 0.78
    body_h = band_z - z0
    arch_z = body_h - 1.08 * hb / 1.2
    zl = (arch_z - 0.15) * 0.22
    lh = (arch_z - 0.15) * 0.62
    # remove the paper lattice leaves of this storey (open windows)
    for o in [o for o in pag.children if o.name.startswith(pag.name + ".leaf")
              and z0 - 0.05 <= o.location.z < band_z]:
        U.delete_hierarchy(o)
    inner = ap - wt / 2
    # glowing core (lamplight behind the shelves)
    v, f = _prism(inner - 1.5, z0 + 0.02, z0 + arch_z)
    core = U.mesh_from_pydata(_n("lit_core", k), v, f, coll, materials=["library_lamplight"], parent=pag)
    core["glow"] = 1.0
    # bookshelves in front of each window: uprights + planks + book blocks
    bm = bmesh.new()
    fl = 2 * r * math.sin(math.pi / 8) - 2 * cr
    sw = fl * 0.56 + 0.2
    sh = lh * 0.55 + 0.1    # low bookcases: the glowing core shows above them
    planks = 3
    rng = U.rng(KEY, "shelf", k)
    mats = ["wood_dark"] + _COVERS
    for face in range(8):
        a = -math.pi / 2 + 2 * math.pi * face / 8
        m = U.trs(((inner - 0.55) * math.cos(a), (inner - 0.55) * math.sin(a), z0 + zl - 0.1),
                  (0, 0, a + math.pi / 2))
        for sx in (-0.5, 0.5):
            U.bm_box(bm, (0.1, 0.4, sh), (sx * sw, 0, sh / 2), matrix=m)
        for p in range(planks):
            zz = 0.05 + p * (sh - 0.1) / (planks - 1)
            U.bm_box(bm, (sw, 0.4, 0.06), (0, 0, zz), matrix=m)
            if p == planks - 1:
                continue
            x = -sw / 2 + 0.1
            gap = (sh - 0.1) / (planks - 1)
            while x < sw / 2 - 0.25:
                bw = rng.uniform(0.12, 0.3)
                vs = U.bm_box(bm, (bw, 0.3, gap * rng.uniform(0.55, 0.8)),
                              (x + bw / 2, 0, zz + 0.03 + gap * 0.33), matrix=m)
                mi = 1 + rng.randrange(len(_COVERS))
                for fc in {fc for vv in vs for fc in vv.link_faces}:
                    fc.material_index = mi
                x += bw + rng.uniform(0.0, 0.06)
    U.mesh_from_bmesh(_n("shelves", k), bm, coll, materials=mats, parent=pag)
    # warm light spilling out of the windows onto the balcony
    ld = bpy.data.lights.new(_n("lit_light", k), 'POINT')
    ld.energy = 4000.0
    ld.color = (1.0, 0.62, 0.3)
    ld.shadow_soft_size = 0.8
    lo = bpy.data.objects.new(_n("lit_light", k), ld)
    coll.objects.link(lo)
    lo.parent = pag
    lo.location = (0.0, 0.0, z0 + arch_z * 0.6)


def _pagoda(coll, root):
    pag = A.pagoda(_n("pagoda"), coll, tiers=7, sides=8, radius=PAGODA_RADIUS, tier_h=PAGODA_TIER_H,
                   lit_floors=(), roof_mat="roof_tile_teal", platform_h=1.6,
                   parent=root, location=(PAGODA_XY[0], PAGODA_XY[1], PLAZA_TOP))
    floors = list(pag["arch_floors"])
    bands = sorted((o for o in pag.children if o.name.startswith(pag.name + ".band")),
                   key=lambda o: o.location.z)
    band_zs = [b.location.z for b in bands]
    for k in LIT_FLOORS:
        _lit_storey(coll, pag, k, floors[k], band_zs[k])
    # plaque: centred on the ground-floor front, hung in front of the architrave under the first eave
    ap = PAGODA_RADIUS * COS8
    P.plaque(coll, AREA["title_zh"], 3.4, name=_n("plaque"), parent=pag,
             location=(0.0, -(ap + 0.75), band_zs[0] - 0.55))
    return pag


# ----------------------------------------------------------------------------- garden

SETTLE_SINK = 0.04            # props on the lawn sink this far under the lowest ground below their foot
LANTERN_FOOT_R = 0.45         # stone lantern plinth (1.04 m across)
TRUNK_FOOT_R = 0.25           # peach trunk base
BOULDER_FOOT_R = 0.5          # the 1.8 m boulder's bearing patch
BOULDER_SINK = 0.12           # rocks are bedded in, a little deeper than built props
FINIAL_SINK = 0.06            # a roof finial's foot sinks this far into the roof tiles at the apex
FINIAL_REACH = 0.6            # ... measured on the tiles within this radius of its axis


def _local(ob):
    """``ob``'s matrix in its parent's frame, from its own transform (valid before the depsgraph evaluates a fresh
    build, unlike matrix_local)."""
    return ob.matrix_parent_inverse @ ob.matrix_basis


def _lawn_bvh(lawn):
    """BVH of the lawn in the area root's frame (the lawn is a direct child of the root)."""
    from mathutils.bvhtree import BVHTree
    mw = _local(lawn)
    verts = [mw @ v.co for v in lawn.data.vertices]
    return BVHTree.FromPolygons(verts, [tuple(p.vertices) for p in lawn.data.polygons])


def _ground_z(lawn_bvh, x, y, r=0.0, n=8):
    """Lowest ground under a foot of radius ``r`` at (x, y), root frame: per sample the lawn, or the world terrace
    (TERRACE_Z) where the lawn's rim drops under it. A prop set at this height rests on the low side of the foot
    and sinks into the high side, so no part of it hovers (round 5 float scan: the lanterns, the boulder and the
    rim peach stood 0.17-0.43 m over the undulating lawn)."""
    from mathutils import Vector
    pts = [(x, y)] + [(x + r * math.cos(2 * math.pi * k / n), y + r * math.sin(2 * math.pi * k / n))
                      for k in range(n if r > 0 else 0)]
    zs = []
    for px, py in pts:
        hit = lawn_bvh.ray_cast(Vector((px, py, 20.0)), Vector((0.0, 0.0, -1.0)), 100.0)
        zs.append(max(hit[0].z if hit[0] is not None else TERRACE_Z, TERRACE_Z))
    return min(zs)


def _settle(ob, lawn_bvh, r, sink=SETTLE_SINK):
    """Drop (or lift) ``ob`` (a child of the root) so its origin, the foot of every prop used here, sits SINK m
    under the lowest ground below its foot."""
    x, y = ob.location.x, ob.location.y
    ob.location.z = _ground_z(lawn_bvh, x, y, r) - sink
    return ob


def _seat_finial(pav):
    """Lower a round-roofed pavilion's finial onto its roof (arch.pavilion leaves the finial's foot 0.33 m over the
    tiles' top lip on these small 'round' roofs, visibly floating): the foot (the finial mesh's instancing point,
    the bottom of the geometry-nodes finial) goes FINIAL_SINK under the highest tile within FINIAL_REACH of its
    axis (the lip round the apex opening). Works on the built objects, so a fresh build and patch_r5_float.py
    agree. Returns the gap it closed (m), or None."""
    roof = next((c for c in pav.children if c.name == pav.name + ".roof"), None)
    if roof is None:
        return None
    fin = next((c for c in roof.children if c.name.startswith(roof.name + ".finial")), None)
    tiles = next((c for c in roof.children if c.name.startswith(roof.name + ".tiles")), None)
    if fin is None or tiles is None or fin.type != 'MESH' or not fin.data.vertices:
        return None
    # everything in the roof's frame: the finial's foot and the tiles near its axis
    foot = [_local(fin) @ v.co for v in fin.data.vertices]
    fz = min(p.z for p in foot)
    ax = sum(p.x for p in foot) / len(foot)
    ay = sum(p.y for p in foot) / len(foot)
    top = None
    mt = _local(tiles)
    for v in tiles.data.vertices:
        p = mt @ v.co
        if (p.x - ax) ** 2 + (p.y - ay) ** 2 <= FINIAL_REACH ** 2:
            top = p.z if top is None else max(top, p.z)
    if top is None:
        return None
    gap = fz - top
    fin.location.z -= gap + FINIAL_SINK
    return gap


def _garden(coll, root):
    lawn = bpy.data.objects.get(KEY + ".lawn")
    lawn_bvh = _lawn_bvh(lawn) if lawn is not None else None
    # lotus pool
    N.pond(coll, radius=POND_R, seed=17, depth=1.2, name=_n("pond"), parent=root,
           location=(POND_XY[0], POND_XY[1], 0.0))
    N.lotus_patch(coll, radius=POND_R * 0.7, count=30, seed=5, name=_n("lotus"), parent=root,
                  location=(POND_XY[0] + 0.6, POND_XY[1] - 0.4, -0.18))

    # study pavilions (round roofs): east on the side path, west on the pond's north bank
    for nm, rad, h, loc, rot in (("study_east", 3.0, 3.3, (22.5, -10.0, 0.0), -90),
                                 ("study_west", 2.8, 3.2, (-24.5, 10.5, 0.0), 90)):
        pav = A.pavilion(_n(nm), coll, sides=8, radius=rad, height=h, roof="round",
                         roof_mat="roof_tile_black", parent=root, location=loc, rotation_z=math.radians(rot))
        _seat_finial(pav)

    # stone lanterns flanking the axis path and the pagoda stairs, on the lawn beside the path (not at the
    # path's top: the lawn undulates 0.0-0.15 m under it)
    for i, y in enumerate((-34.0, -18.0)):
        for sx in (-1, 1):
            ln = P.lantern_stone(coll, 2.6, name=_n("lantern_stone"), parent=root,
                                 location=(sx * 5.4, y, PLAZA_TOP))
            if lawn_bvh is not None:
                _settle(ln, lawn_bvh, LANTERN_FOOT_R)

    # trees
    for i, (x, y, h) in enumerate(((31.0, 22.0, 12.0), (-33.0, 26.0, 11.0), (14.0, 34.0, 10.0),
                                   (33.0, -24.0, 9.5), (-36.0, -2.0, 10.5))):
        N.pine(coll, height=h, seed=40 + i, name=_n("pine"), parent=root, location=(x, y, 0.0))
    for h, seed, x, y in ((6.5, 3, -9.5, -30.0), (6.0, 6, -31.0, -24.0)):
        bt = N.blossom_tree(coll, height=h, seed=seed, kind="peach", lod="mid", name=_n("blossom"), parent=root,
                            location=(x, y, 0.0))
        if lawn_bvh is not None:      # the second stands on the lawn's rim, where it drops under the terrace
            _settle(bt, lawn_bvh, TRUNK_FOOT_R)
    N.bamboo_clump(coll, count=10, height=8.0, seed=9, name=_n("bamboo"), parent=root,
                   location=(-31.0, 14.0, 0.0))
    N.rock(coll, 2.6, seed=4, kind="scholar", name=_n("taihu"), parent=root, location=(-12.0, -8.5, 0.0))
    bd = N.rock(coll, 1.8, seed=8, kind="boulder", name=_n("boulder"), parent=root, location=(-13.5, -22.0, 0.0))
    if lawn_bvh is not None:          # on the pond basin's slope: bedded in, not perched
        _settle(bd, lawn_bvh, BOULDER_FOOT_R, sink=BOULDER_SINK)


# ----------------------------------------------------------------------------- scroll spiral

def _channel_fcurves(action):
    """All F-curves of an action (legacy `action.fcurves` or 5.x layered channel bags)."""
    out = []
    try:
        out.extend(action.fcurves)
    except (AttributeError, TypeError):
        pass
    if out:
        return out
    for layer in getattr(action, "layers", ()):
        for strip in getattr(layer, "strips", ()):
            for cb in getattr(strip, "channelbags", ()):
                out.extend(cb.fcurves)
    return out


def _spin(obj, frames=SPIRAL_FRAMES, turns=SPIRAL_TURNS):
    f0, f1 = frames
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.keyframe_insert(data_path="rotation_euler", index=2, frame=f0)
    obj.rotation_euler = (0.0, 0.0, 2 * math.pi * turns)
    obj.keyframe_insert(data_path="rotation_euler", index=2, frame=f1)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    act = obj.animation_data.action
    act.name = obj.name + ".action"
    for fc in _channel_fcurves(act):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'


def _halo_mesh():
    def build():
        bm = bmesh.new()
        vs = [bm.verts.new((x, y, 0.0)) for x, y in ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5))]
        bm.faces.new(vs)
        return bm
    return U.shared_mesh("library.halo_quad", build)


def _halo(coll, parent, w, h, z=0.0):
    """Soft additive gold glow card standing behind a scroll (local +Y), so it reads as glowing."""
    o = U.object_from_mesh(_n("halo"), _halo_mesh(), coll, parent=parent,
                           location=(0.0, 0.35, z), rotation=(math.pi / 2, 0.0, 0.0), scale=(w, h, 1.0))
    U.set_materials(o, ["library_scroll_halo"])
    U.set_visibility(o, shadow=False)
    return o


# spiral pattern: open scroll, closed scroll, open, book stack, open, closed
_SPIRAL_KINDS = ("open", "closed", "open", "book", "open", "closed")


def _scrolls(coll, root, pagoda_height):
    spiral = U.empty(_n("scroll_spiral"), coll, parent=root,
                     location=(PAGODA_XY[0], PAGODA_XY[1], PLAZA_TOP), display_size=3.0)
    rng = U.rng(KEY, "scrolls")
    z0, z1 = 6.0, pagoda_height - 7.0
    r0, r1 = 16.0, 10.5
    turns = 3.0
    for i in range(N_SCROLLS):
        t = i / (N_SCROLLS - 1)
        a = 2 * math.pi * turns * t + rng.uniform(-0.1, 0.1)
        r = r0 + (r1 - r0) * t + rng.uniform(-0.5, 0.5)
        z = z0 + (z1 - z0) * t + rng.uniform(-0.8, 0.8)
        loc = (r * math.cos(a), r * math.sin(a), z)
        face = a + math.pi / 2          # local -Y faces outward
        rot = (rng.uniform(-0.2, 0.2), rng.uniform(-0.25, 0.25), face + rng.uniform(-0.3, 0.3))
        kind = _SPIRAL_KINDS[i % len(_SPIRAL_KINDS)]
        if kind == "closed":
            w = 3.0
            o = P.floating_scroll(coll, w, open=False, seed=i, name=_n("scroll"), parent=spiral,
                                  location=loc, rotation=(rot[0], 0.55 * (1 if i % 2 else -1), rot[2]))
            _halo(coll, o, w * 1.3, w * 0.55)
        elif kind == "book":
            o = P.book_stack(coll, 4, seed=i, name=_n("book"), parent=spiral, location=loc,
                             rotation=rot, scale=5.5)
            _halo(coll, o, 0.5, 0.45, z=0.12)
        else:
            w = 4.6 if i % 2 else 3.8
            o = P.floating_scroll(coll, w, open=True, glow=True, seed=i, name=_n("scroll"),
                                  parent=spiral, location=loc, rotation=rot)
            _halo(coll, o, w * 1.45, w * 0.36 * 2.0)
    _spin(spiral)
    # spirit motes drifting around the pagoda (jade-cyan dust)
    P.spirit_motes(coll, 260, ((-17.0, -9.0, 3.0), (17.0, 25.0, pagoda_height - 4.0)), seed=21,
                   size=0.09, drift=0.4, name=_n("motes"), parent=root)
    return spiral


# ----------------------------------------------------------------------------- build

def _abs_fonts():
    """util.load_font checks the font with os.path (cwd-relative) but hands the same string to
    bpy.data.fonts.load, which does not resolve it against cwd. On the Linux render box the
    fonts live at '/C:/Windows/Fonts/...', so 'C:/Windows/...' is relative there and the load
    fails. Make the paths absolute for the duration of this build; returns the old values."""
    import os
    old = (U.FONT_KAITI, U.FONT_YAHEI)
    for attr in ("FONT_KAITI", "FONT_YAHEI"):
        p = getattr(U, attr)
        if p and not os.path.isabs(p) and os.path.exists(p):
            setattr(U, attr, os.path.abspath(p))
    return old


def build(collection):
    """Build the Scripture Pavilion at the local origin. Return the root Empty 'library.root'."""
    old_fonts = _abs_fonts()
    try:
        root = U.empty(KEY + ".root", collection, display_size=4.0)
        _ground(collection, root)
        pag = _pagoda(collection, root)
        _garden(collection, root)
        _scrolls(collection, root, float(pag.get("arch_height", 46.0)))
    finally:
        U.FONT_KAITI, U.FONT_YAHEI = old_fonts
    return root


# look.py preview harness: render the camera hints by name (and with --cams auto)
build.preview_cameras = [(c["name"], c["location"], c["target"], c["lens"]) for c in CAMERA_HINTS]
