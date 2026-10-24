"""Moon-Gazing Summit 望月台 (site section 'footer', the end of the flight).

Blocking pass (spec section 0): the highest peak of the floating range. A circular white
marble terrace (radius 39 m) with a raised round inner tier, a single round double-eave
pavilion with moon-white tiles and a silver finial, a lone ancient pine on a rock knob at the
north-east rim leaning out over the void, and a crescent-moon arch (horns down, 27 m wide,
20 m tall) as the entry gate on the front (-Y) rim carrying the 望月台 plaque. A moon-silver
trigram ring is inlaid in the paving around the inner tier.

Local frame: origin = centre of the terrace top, z = 0 walkable, front (arch, entry) faces -Y.
The last camera hint looks up past the pavilion at the moon; the moon's local azimuth comes
from the yaw assembly is expected to use (see MOON_AZ_LOCAL_DEG and moon_hint()).
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from sect.lib import util as U
from sect.lib import arch as A
from sect.lib import props as P
from sect.lib import nature as N

# Connector landing (architecture-audit 1.11 / W1), local (x, y, z, heading). heading is the
# walking direction in radians, measured like world.py's yaw: atan2(dy, dx), so +Y = pi/2.
# The stair from the abode tops out on the marble rim at y -38.5, inside the 6 m front
# balustrade gap, 6.5 m in front of the crescent arch, on the arch's centre line. The summit
# is the end of the route: no depart.
AREA = dict(key="summit", section_id="footer", title_en="Moon-Gazing Summit",
            title_zh="望月台", footprint=40.0,
            arrival=(0.0, -38.5, 0.0, math.pi / 2))

KEY = AREA["key"]

# --- layout (local metres) -------------------------------------------------------------
TERRACE_R = 39.0          # marble terrace radius (footprint 40)
TERRACE_DEPTH = 2.8       # skirt goes down to z = -2.8 (world terrace top is at -0.4)
MID_R = 24.0              # middle round tier (circular-mound-altar style, three white tiers)
MID_H = 1.0
INNER_R = 14.0            # top round tier under the pavilion
INNER_H = 1.2             # height above the middle tier
PAV_RADIUS = 7.0          # pavilion column circle
PAV_COL_H = 6.8
ARCH_Y = -32.0            # crescent arch plane
ARCH_R = 13.5             # outer radius of the crescent (27 m wide, 20 m tall)
ARCH_T = 4.0              # thickness at the crown
ARCH_TIP_T = 0.3          # thickness at the horn tips
ARCH_PHI = math.radians(116)   # half sweep from the crown (> 90: horns curl in)
ARCH_DEPTH = 1.5          # thickness along Y
ARCH_PLINTH_H = 1.0
PINE_AZ = math.radians(50)     # pine position (angle from +X) on the rim: left of the moon line
PINE_R = 36.5
TERRACE_SEGS = 128        # the terrace lathe's segments
# moon-silver trigram ring inlaid in the outer paving (props.rune_ring: band 29.6..31.4, 8 mm over the floor) and the
# dark stone channel under it. The channel is a ring of the terrace's own top (stone_dark faces), not a separate
# groove sheet: rune_ring(groove=True) laid one 3 mm over the paving, and the two z-fought over ~290 m2 on the web
# (round 11). The channel's edges are TERRACE_SEGS-gons, so its radii keep the rune band (and its border rings) on
# dark stone even at the chord midpoints (31.45 * cos(pi / 128) = 31.44).
RING_R, RING_W = 30.5, 1.8
CHANNEL_R = (29.57, 31.45)
# The stair from the abode (world.py: STAIR_W 5 m walkway, its parapets outside it) tops out at AREA['arrival'] with
# its last tread flat on the rim, 0.5 m onto the terrace. The terrace's top is cut away under that tread (|x| < 2.5,
# y < -38.5), so the tread is the only surface there and meets the paving edge to edge at the arrival line (round 11:
# the two lay in one plane over 2.3 m2, z-fought on the web and baked a dark band across the tread).
ARRIVAL_HW = 2.5

# --- moon -----------------------------------------------------------------------------
# world.py puts the moon at compass azimuth 22.5 deg, elevation 16 deg (look.MOON_AZIMUTH).
# Assembly yaws each area so its front (local -Y) faces the incoming camera, i.e. local +Y
# points along the flight from the previous anchor (abode, spec section 4) to this one. With
# that yaw the moon sits at about local azimuth 71 deg (front-right, past the pavilion).
# CAMERA_HINTS are built for that. If assembly uses another yaw, moon_hint(yaw) returns a
# final hint that still ends on the moon.
MOON_EL_DEG = 16.0
MOON_AZ_WORLD_DEG = 22.5
_PREV_ANCHOR = (185.0, 1335.0)    # abode
_ANCHOR = (0.0, 1500.0)           # summit
EXPECTED_YAW = math.atan2(-(_ANCHOR[0] - _PREV_ANCHOR[0]), _ANCHOR[1] - _PREV_ANCHOR[1])  # ~0.84
MOON_AZ_LOCAL_DEG = MOON_AZ_WORLD_DEG + math.degrees(EXPECTED_YAW)                         # ~70.8


def _dir(az_deg, el_deg):
    """Unit vector, azimuth clockwise from local +Y, elevation above the horizon."""
    a, e = math.radians(az_deg), math.radians(el_deg)
    return Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)))


def _r3(v):
    return (round(v[0], 2), round(v[1], 2), round(v[2], 2))


# final shot: on the far side of the pavilion from the moon, a little above the roofs' base,
# looking up at the moon so the round roof, finial and the pine sit at the bottom of the frame
FINAL_DIST = 62.0
FINAL_Z = 9.0
FINAL_EL = 12.0
FINAL_LENS = 50


def moon_hint(yaw=None, dist=FINAL_DIST, z=FINAL_Z, el=FINAL_EL, lens=FINAL_LENS):
    """Final camera hint aimed at the moon for an area yaw (radians, the rotation assembly
    applies about Z, counter-clockwise seen from above). yaw=None uses the expected yaw
    (front faces the abode). Returns a CAMERA_HINTS-style dict in LOCAL coordinates."""
    az = MOON_AZ_LOCAL_DEG if yaw is None else MOON_AZ_WORLD_DEG + math.degrees(yaw)
    h = _dir(az, 0.0)
    loc = Vector((0.0, 0.0, z)) - h * dist
    tgt = loc + _dir(az, el) * 300.0
    return dict(name="moon", location=_r3(loc), target=_r3(tgt), lens=lens)


# Where the fly-through camera should pass, in LOCAL coordinates (front = -Y).
CAMERA_HINTS = [
    # rising out of the haze below the rim: crescent arch frames the pavilion
    dict(name="approach", location=(0.0, -112.0, 2.0), target=(0.0, 0.0, 10.0), lens=30),
    # climbing past the arch on the left, terrace disc, pavilion and pine read in 3/4,
    # already turning right toward the moon
    dict(name="rise", location=(-46.0, -58.0, 8.0), target=(4.0, 2.0, 8.0), lens=28),
    # past the west rim, tilted up: pavilion roof and the pine at the bottom, mostly moon
    moon_hint(),
]


# --------------------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------------------

TERRACE_MATS = ["marble_white", "marble_paving", "stone_dark"]
TERRACE_SMOOTH = math.radians(35)


def _arrival_cut(bm):
    """Cut the terrace's top away under the abode stair's last tread (ARRIVAL_HW, AREA['arrival']): bisect the top
    faces near the arrival along x = +-ARRIVAL_HW and the arrival line, then delete the faces under the tread.
    Returns how many faces were deleted."""
    ay = AREA["arrival"][1]

    def top(f):
        return f.normal.z > 0.9 and f.calc_center_median().z > -0.01

    for co, no in (((ARRIVAL_HW, 0.0, 0.0), (1.0, 0.0, 0.0)), ((-ARRIVAL_HW, 0.0, 0.0), (1.0, 0.0, 0.0)),
                   ((0.0, ay, 0.0), (0.0, 1.0, 0.0))):
        fs = [f for f in bm.faces if top(f) and abs(f.calc_center_median().x) < ARRIVAL_HW + 2.0
              and f.calc_center_median().y < ay + 2.0]
        geom = list({v for f in fs for v in f.verts}) + list({e for f in fs for e in f.edges}) + fs
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, dist=1e-5)
        bm.normal_update()                      # the faces the cut made have no normal yet
    kill = [f for f in bm.faces if top(f) and abs(f.calc_center_median().x) < ARRIVAL_HW
            and f.calc_center_median().y < ay]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    return len(kill)


def _terrace_bm():
    """BMesh of the round marble terrace: paving annulus (quads, concentric rings), the dark stone channel ring under
    the rune ring (CHANNEL_R, material 2), a moulded skirt (material 0), and no top under the abode stair's last
    tread (_arrival_cut)."""
    bm = bmesh.new()
    R = TERRACE_R
    c0, c1 = CHANNEL_R
    prof = [(R - 0.9, -TERRACE_DEPTH), (R - 0.45, -TERRACE_DEPTH + 0.35), (R - 0.45, -0.55),
            (R - 0.15, -0.42), (R, -0.3), (R, 0.0)]
    rings = []
    r = R - 1.5
    while r > MID_R - 1.5:
        rings.append(r)
        r -= 2.5
    rings.append(MID_R - 2.0)
    rings = sorted([x for x in rings if not c0 - 1e-6 <= x <= c1 + 1e-6] + [c0, c1], reverse=True)
    prof += [(x, 0.0) for x in rings]
    U.bm_lathe(bm, prof, segments=TERRACE_SEGS, cap_start=False, cap_end=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        c = f.calc_center_median()
        top = f.normal.z > 0.9 and c.z > -0.01
        f.material_index = (2 if c0 < math.hypot(c.x, c.y) < c1 else 1) if top else 0
    _arrival_cut(bm)
    return bm


def _terrace(coll, root):
    """Round marble terrace (_terrace_bm)."""
    return U.mesh_from_bmesh(U.name(KEY, "terrace"), _terrace_bm(), coll, materials=TERRACE_MATS,
                             smooth=TERRACE_SMOOTH, parent=root)


def _crescent_mesh(name, coll, root):
    """Crescent standing in the XZ plane, horns down (an arch you walk through along Y)."""
    n = 48
    cz = ARCH_PLINTH_H - (ARCH_R - ARCH_TIP_T * 0.5) * math.cos(ARCH_PHI) - 0.15
    outer, inner = [], []
    for i in range(n + 1):
        u = -1.0 + 2.0 * i / n
        phi = u * ARCH_PHI
        t = math.cos(u * math.pi * 0.5) ** 1.3
        th = ARCH_TIP_T + (ARCH_T - ARCH_TIP_T) * t
        s, c = math.sin(phi), math.cos(phi)
        outer.append((ARCH_R * s, cz + ARCH_R * c))
        inner.append(((ARCH_R - th) * s, cz + (ARCH_R - th) * c))
    bm = bmesh.new()
    h = ARCH_DEPTH * 0.5
    fo = [bm.verts.new((x, -h, z)) for x, z in outer]
    fi = [bm.verts.new((x, -h, z)) for x, z in inner]
    bo = [bm.verts.new((x, h, z)) for x, z in outer]
    bi = [bm.verts.new((x, h, z)) for x, z in inner]
    for i in range(n):
        j = i + 1
        bm.faces.new((fo[i], fo[j], fi[j], fi[i]))      # front
        bm.faces.new((bo[i], bi[i], bi[j], bo[j]))      # back
        bm.faces.new((fo[i], bo[i], bo[j], fo[j]))      # outer curve
        bm.faces.new((fi[i], fi[j], bi[j], bi[i]))      # inner curve
    for k in (0, n):
        bm.faces.new((fo[k], fi[k], bi[k], bo[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = U.mesh_from_bmesh(name, bm, coll, materials=["marble_white"], smooth=math.radians(40),
                           parent=root, location=(0, ARCH_Y, 0))
    return ob, cz, outer, inner


def _crescent_arch(coll, root):
    body, cz, outer, inner = _crescent_mesh(U.name(KEY, "arch"), coll, root)
    # glowing moon-silver line along the inner curve, both faces; silver bead on the outer curve
    h = ARCH_DEPTH * 0.5 + 0.02
    for side in (-1, 1):
        pts = [(x * 0.995, side * h, z - 0.04) for x, z in inner[2:-2]]
        U.tube_mesh(U.name(KEY, "arch_glow"), pts, 0.11, coll, material="rune_silver", sides=6,
                    samples_per_segment=2, parent=root, location=(0, ARCH_Y, 0))
        pts = [(x, side * h, z) for x, z in outer[1:-1]]
        U.tube_mesh(U.name(KEY, "arch_bead"), pts, 0.13, coll, material="silver", sides=6,
                    samples_per_segment=2, parent=root, location=(0, ARCH_Y, 0))
    # plinths under the horn tips
    tip_x = (ARCH_R - ARCH_TIP_T * 0.5) * math.sin(ARCH_PHI)
    for sx in (-1, 1):
        bm = bmesh.new()
        U.bm_box(bm, (2.0, 2.4, ARCH_PLINTH_H * 0.75), center=(0, 0, ARCH_PLINTH_H * 0.375))
        U.bm_box(bm, (1.6, 2.0, ARCH_PLINTH_H * 0.25), center=(0, 0, ARCH_PLINTH_H * 0.875))
        U.mesh_from_bmesh(U.name(KEY, "arch_plinth"), bm, coll, materials=["marble_white"],
                          parent=root, location=(sx * tip_x, ARCH_Y, 0))
    # plaque hanging from the crown's underside, front face
    inner_top = cz + ARCH_R - ARCH_T
    pw = 5.0
    ph = 1.66 * pw / (3 * 1.12 + 0.95)
    P.plaque(coll, AREA["title_zh"], pw, name=U.name(KEY, "plaque"), parent=root,
             location=(0, ARCH_Y - 0.25, inner_top - 0.15 - ph * 0.5))
    return body, cz


def _silver_finial(pav_root):
    """The lib pavilion always gets a gold finial; swap its instancer to a silver one.
    The lib also seats a round roof's finial ~0.5 m above the tile apex (it floats against the
    moon in the last shot), so drop the finial instancer onto the apex."""
    try:
        silver = A._scatter_group(A._p_finial("gourd", "silver"))
    except Exception as exc:  # private helpers may change; the gold finial is acceptable
        print("SUMMIT WARN silver finial:", exc)
        silver = None
    fin, tiles = None, None
    stack = [pav_root]
    while stack:
        ob = stack.pop()
        stack.extend(ob.children)
        if ob.parent and ob.parent.name.endswith(".roof") and ob.name.endswith(".tiles"):
            tiles = ob
        for m in ob.modifiers:
            if m.type == 'NODES' and m.node_group and ".finial." in m.node_group.name:
                fin = ob
                if silver is not None and m.node_group.name.endswith("finial.gourd.gold"):
                    m.node_group = silver
    if fin is None or tiles is None:
        return
    try:
        bpy.context.view_layer.update()
        top = max((tiles.matrix_world @ Vector(c)).z for c in tiles.bound_box)
        dg = bpy.context.evaluated_depsgraph_get()
        bases = [inst.matrix_world.translation.z for inst in dg.object_instances
                 if inst.is_instance and inst.parent and inst.parent.original == fin]
        shift = (min(bases) - top + 0.1) if bases else 0.0
    except Exception as exc:
        print("SUMMIT WARN finial seat:", exc)
        return
    if 0.0 < shift < 3.0:
        fin.location.z -= shift


def _rim_points(radius, z, a0, a1, step_deg=4.0):
    n = max(2, int(abs(a1 - a0) / math.radians(step_deg)) + 1)
    return [(radius * math.cos(a0 + (a1 - a0) * i / (n - 1)),
             radius * math.sin(a0 + (a1 - a0) * i / (n - 1)), z) for i in range(n)]


# --------------------------------------------------------------------------------------
# the Divine Condor 神雕 (The Return of the Condor Heroes)
# --------------------------------------------------------------------------------------
# Ch. 23: taller than a man, ugly in the extreme, a hooked beak, very thick legs, and it walks with its head held
# high. Dugu Qiubai's companion; it teaches Yang Guo the heavy sword (the arena's Heavy Iron Sword). Ch. 40 ends on
# Mount Hua under the bright moon, the condor standing with folded wings, proud (收翅凝立，神情傲然), and the site
# ends on the moon.
#
# Round 7: the procedural bird read as fake, and it stood on the terrace. The bird is now a prepared, real-looking
# vulture (sect/lib/condor_props.py: Pigcraft's "Dark Vulture" on Sketchfab, CC-BY 4.0, credited in
# assets/CREDITS.md), standing with folded wings on a rock crag that rises out of the summit cliff beyond the rail: a
# small karst column (nature.rock_pillar, dome top, leaning a little outward) whose foot runs down into the summit
# cliff, with a flat capstone boulder (the bird's perch) and two small boulders. Static; not a hotspot.
#
# Round 34 (r31 proposal, approved): the crag stood west of the terrace, 100% under the Contact panel at the hold
# (frame 1647), so its card could not be reached there. It now rises right of the pavilion, below the moon: at
# CONDOR_SITE (local r 43.8, outside the terrace's 39 m rim off the south-west rail), the bird at about x 1350-1450,
# y 650-730 of 1600 x 900 at the hold, 31 m off, at CONDOR_SCALE of the model (1.45 m: ~60 px tall), clear of the
# voice button and 12 m from the camera path at its nearest (sect/patch_r34_west.py checks it). A slimmer column
# than round 7's (CONDOR_CRAG top_r 2.7), so on the approach (frame 1625), where it stands in front of the pavilion's
# lower half, it hides as little of it as it can. The bird faces CONDOR_HEADING (local atan2): in profile at the hold,
# beak toward the pavilion and the moon (收翅凝立, ch. 40). Xiaolongnü's golden-bell ribbon lies coiled on the
# capstone beside it (sect/lib/refs_west.py coil).
#
# Model frame of the bird ('summit.condor_bird'): origin between the feet, beak toward -Y, z up.

CONDOR_SITE = (43.8, math.radians(-146.0))   # crag centre, local polar (r, atan2 angle): right of the pavilion at 1647
CONDOR_CRAG = dict(top=7.6, top_r=2.7, bottom_r=3.9, depth=40.0, seed=31, lean=math.radians(4.0))
CONDOR_CAP = dict(size=2.8, seed=4, sink=0.3)    # boulder variant 4 (the flattest top); its yaw is searched so the
                                                 # rock under the toes is as level as it gets
CONDOR_ROCKS = 2                             # small boulders on the crag's dome beside the capstone
CONDOR_HEADING = math.radians(95.0)          # beak direction (local atan2): in profile at the hold, toward the pavilion
CONDOR_SCALE = 0.85                          # of the prepared bird (condor_props.BIRD_HEIGHT 1.7 m -> 1.45 m)
CONDOR_TAG = "sect_item"                     # object property; sect/patch_r34_west.py moves what carries it
CONDOR_ITEM = "divine_condor"
CONDOR_MAX_TOE_GAP = 0.06                    # m: no toe may stand higher than this above the capstone
# round 7's place (sect/patch_r34_west.py recognises the old crag by it)
CONDOR_SITE_R7 = (46.0, math.radians(-173.0))
CONDOR_CRAG_R7 = dict(top=6.5, top_r=3.6, bottom_r=6.5, depth=45.0, seed=31, lean=math.radians(6.0))
CONDOR_CAP_R7 = dict(size=3.2, seed=4, sink=0.35)
CONDOR_HEADING_R7 = math.radians(-35.0)
CONDOR_SCALE_R7 = 1.0


def _local_tree(ob):
    """BVH of ``ob``'s mesh in its parent's (summit-local) frame."""
    M = ob.matrix_parent_inverse @ ob.matrix_basis
    me = ob.data
    return BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])


def _down(tree, x, y, z0):
    """Height of the first surface of ``tree`` straight below (x, y, z0), or None."""
    h = tree.ray_cast(Vector((x, y, z0)), Vector((0.0, 0.0, -1.0)))
    return None if h[0] is None else h[0].z


def divine_condor(collection, root, log=None, nm=None, site=None, crag=None, cap=None, heading=None, scale=None):
    """The Divine Condor on its crag (see the block comment above): 'summit.condor_crag' (karst column),
    'summit.condor_crag_rock' x CONDOR_ROCKS and 'summit.condor_cap' (boulders), and the bird 'summit.condor_bird'
    (sect/lib/condor_props.py, scaled CONDOR_SCALE; raises when its prepared files are missing from assets/web). Every
    object carries obj[CONDOR_TAG] = CONDOR_ITEM. nm(base) -> object name (default U.name(KEY, base));
    site / crag / cap / heading / scale default to the CONDOR_* constants (sect/patch_r34_west.py rebuilds round 7's
    with the _R7 ones to recognise it). Returns the bird."""
    from sect.lib import condor_props as CP
    say = log or (lambda *a: print("SUMMIT condor", *a, flush=True))
    nm = nm or (lambda base: U.name(KEY, base))
    r0, a0 = site or CONDOR_SITE
    cg = crag or CONDOR_CRAG
    cp = cap or CONDOR_CAP
    head = CONDOR_HEADING if heading is None else heading
    s = CONDOR_SCALE if scale is None else scale
    cx, cy = r0 * math.cos(a0), r0 * math.sin(a0)
    lean = (-cg["lean"] * math.sin(a0), cg["lean"] * math.cos(a0), cg.get("yaw", 0.0))   # the top leans outward
    crag_ob = N.rock_pillar(collection, height=cg["top"] + cg["depth"], top_radius=cg["top_r"],
                            bottom_radius=cg["bottom_r"], seed=cg["seed"], top_flat=False, top_z=cg["top"], lod="hero",
                            pines=False, vegetation=False, name=nm("condor_crag"), parent=root,
                            location=(cx, cy, 0.0), rotation=lean)
    made = [crag_ob]
    ctree = _local_tree(crag_ob)
    z_top = _down(ctree, cx, cy, cg["top"] + 30.0)
    if z_top is None:
        raise RuntimeError("condor crag: no top found under its centre")
    # two small boulders on the dome, each sunk to the lowest point under its footprint (no edge hovers); one whose
    # footprint runs off the dome's edge is pulled in toward the centre until it sits wholly on the top
    r = U.rng("summit.condor_crag", 7)
    for i in range(CONDOR_ROCKS):
        th = 2.0 * math.pi * i / CONDOR_ROCKS + r.uniform(-0.5, 0.5)
        d0 = cg["top_r"] * r.uniform(0.45, 0.75)
        size = r.uniform(1.4, 2.2) * (cg["top_r"] / 3.6)
        seed = r.randint(0, 7)
        rot = r.uniform(0.0, 2.0 * math.pi)
        while True:
            px, py = cx + d0 * math.cos(th), cy + d0 * math.sin(th)
            hs = [_down(ctree, px + 0.45 * size * math.cos(k * math.pi / 3),
                        py + 0.45 * size * math.sin(k * math.pi / 3), cg["top"] + 30.0) for k in range(6)]
            hs.append(_down(ctree, px, py, cg["top"] + 30.0))
            if (None not in hs and max(hs) - min(hs) < 0.6) or d0 < 0.3:
                break
            d0 -= 0.2
        hs = [h for h in hs if h is not None]
        made.append(N.rock(collection, size, seed=seed, kind="boulder", name=nm("condor_crag_rock"),
                           parent=root, location=(px, py, min(hs) - 0.1), rotation=rot))
    # the capstone: the yaw (of 24) with the most level rock under the toes
    cap_ob = N.rock(collection, cp["size"], seed=cp["seed"], kind="boulder", name=nm("condor_cap"),
                    parent=root, location=(cx, cy, z_top - cp["sink"]), rotation=0.0)
    made.append(cap_ob)
    yaw = head + math.pi / 2                                  # the model faces -Y
    C = Matrix.Translation((cx, cy, 0.0)) @ Matrix.Rotation(yaw, 4, 'Z')
    toes = [C @ Vector((x * s, y * s, 0.0)) for x, y in CP.toe_points()]
    best = None
    for k in range(24):
        cap_ob.rotation_euler = (0.0, 0.0, 2.0 * math.pi * k / 24)
        tree = _local_tree(cap_ob)
        hs = [_down(tree, p.x, p.y, z_top + 10.0) for p in toes]
        if any(h is None for h in hs):
            continue
        hs.sort()
        spread = hs[-1] - hs[0]
        if best is None or spread < best[0] - 1e-6:
            best = (spread, k, hs[len(hs) // 2], hs[0], hs[-1])
    if best is None:
        raise RuntimeError("condor capstone: the toes overhang every capstone yaw")
    cap_ob.rotation_euler = (0.0, 0.0, 2.0 * math.pi * best[1] / 24)
    z_bird = best[2]                                          # median: toes over higher rock sink in a little
    if z_bird - best[3] > CONDOR_MAX_TOE_GAP:
        say("WARN a toe stands %.3f m above the capstone" % (z_bird - best[3]))
    bird = CP.bird(collection, nm("condor_bird"), location=(cx, cy, z_bird), rotation=(0.0, 0.0, yaw),
                   parent=root)
    if abs(s - 1.0) > 1e-9:
        bird.scale = (s, s, s)
    made.append(bird)
    for ob in made:
        ob[CONDOR_TAG] = CONDOR_ITEM
    say("crag", crag_ob.name, "centre (%.2f, %.2f) top %.2f" % (cx, cy, z_top), "capstone yaw %d/24" % best[1],
        "toe rock spread %.3f m, highest toe gap %.3f m, deepest toe %.3f m" % (best[0], z_bird - best[3],
                                                                            best[4] - z_bird),
        "bird at z %.3f yaw %.1f deg scale %.2f" % (z_bird, math.degrees(yaw), s),
        "triangles", {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in made})
    return bird


def condor_rocks(bird):
    """The crag's pieces the ribbon may lie on, found by the bird's own name: [capstone, crag, its boulders]."""
    base = bird.name[:-len("condor_bird")]
    obs = [bpy.data.objects.get(base + n) for n in ("condor_cap", "condor_crag", "condor_crag_rock",
                                                     "condor_crag_rock.001")]
    return [o for o in obs if o is not None]


# --------------------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------------------

def build(collection):
    root = U.empty(KEY + ".root", collection, display_size=4.0)

    # 1. circular marble terrace + rim balustrade (gaps: entry arch at -Y, pine knob at NE).
    #    The rim is the cliff edge (world.py W7), so the balustrade is the cliff rail: the front
    #    gap is only the arriving stair's width (6 m), the pine gap is closed by its boulders.
    _terrace(collection, root)
    bal_r = TERRACE_R - 0.6
    gap_front = math.asin(3.0 / bal_r)
    gap_pine = math.radians(3.0)
    front = -math.pi / 2
    A.balustrade(U.name(KEY, "rim_bal_a"), collection,
                 _rim_points(bal_r, 0.0, front + gap_front, PINE_AZ - gap_pine),
                 end_drum="both", parent=root)
    A.balustrade(U.name(KEY, "rim_bal_b"), collection,
                 _rim_points(bal_r, 0.0, PINE_AZ + gap_pine, front + 2 * math.pi - gap_front),
                 end_drum="both", parent=root)

    # 2. two raised round tiers (circular-mound-altar style) with front stairs and balustrades
    cs = math.cos(math.pi / 48)
    A.platform(U.name(KEY, "tier_mid"), collection, 2 * MID_R, sides=48, height=MID_H, parent=root)
    A.stairs(U.name(KEY, "tier_mid_stairs"), collection, 8.0, MID_H, ramp=True, balustrade=False,
             parent=root, location=(0, -MID_R * cs + 0.05, 0))
    z1 = MID_H
    A.platform(U.name(KEY, "tier_top"), collection, 2 * INNER_R, sides=48, height=INNER_H, parent=root,
               location=(0, 0, z1))
    A.stairs(U.name(KEY, "tier_top_stairs"), collection, 6.0, INNER_H, ramp=True, balustrade=False,
             parent=root, location=(0, -INNER_R * cs + 0.05, z1))
    for r, z, half in ((MID_R - 0.45, MID_H, 4.6), (INNER_R - 0.4, z1 + INNER_H, 3.6)):
        g = math.asin(half / r)
        A.balustrade(U.name(KEY, "tier_bal"), collection,
                     _rim_points(r, z, front + g, front + 2 * math.pi - g, step_deg=6.0),
                     end_drum="both", parent=root)
    z2 = z1 + INNER_H

    # 3. the round double-eave pavilion, moon-white tiles, silver finial
    pav = A.pavilion(U.name(KEY, "pavilion"), collection, sides=8, radius=PAV_RADIUS, height=PAV_COL_H,
                     roof="round", double=True, roof_mat="roof_tile_moon", platform_h=0.7,
                     lattice="ice", seed=3, parent=root, location=(0, 0, z2))
    _silver_finial(pav)
    # stone table for moon-gazing inside
    P.stone_table(collection, 1.3, stools=4, name=U.name(KEY, "table"), parent=root,
                  location=(0, 0.6, z2 + 0.7))
    # 綠竹巷 (round 34): bamboo blinds on the bays the hold faces, the middle one rolled up over a qin and a lamp
    # (sect/lib/refs_west.py blinds); that bay's bench makes way for them
    from sect.lib import refs_west as RW
    bench = RW.bench_on(pav, RW.BLIND_OPEN)
    if bench is not None:
        bpy.data.objects.remove(bench, do_unlink=True)
    RW.blinds(collection, pav)

    # 4. crescent-moon arch: the entry gate with the plaque. Balustrade wings run from each
    #    horn's plinth to the rim rail, so the path goes through the arch, not round it.
    _crescent_arch(collection, root)
    wing_x = math.sqrt(bal_r ** 2 - ARCH_Y ** 2)       # where y = ARCH_Y meets the rim rail
    for sx in (-1, 1):
        A.balustrade(U.name(KEY, "arch_wing"), collection,
                     [(sx * 13.0, ARCH_Y, 0.0), (sx * wing_x, ARCH_Y, 0.0)],
                     end_drum="start", parent=root)

    # 5. moon-silver trigram ring inlaid in the outer paving, over the terrace's dark channel ring (no groove sheet)
    P.rune_ring(collection, radius=RING_R, width=RING_W, kind="trigram", material="rune_silver", seed=2,
                groove=False, name=U.name(KEY, "ring"), parent=root)

    # 6. lone ancient pine on a rock knob at the NE rim, leaning out over the void
    px, py = PINE_R * math.cos(PINE_AZ), PINE_R * math.sin(PINE_AZ)
    N.rock(collection, 4.5, seed=5, kind="boulder", name=U.name(KEY, "pine_rock"), parent=root,
           location=(px - 0.8, py - 0.6, -0.4), rotation=0.6)
    N.rock(collection, 3.0, seed=11, kind="boulder", name=U.name(KEY, "pine_rock"), parent=root,
           location=(px + 1.6, py + 1.2, -0.5), rotation=2.1)
    N.rock(collection, 2.2, seed=17, kind="boulder", name=U.name(KEY, "pine_rock"), parent=root,
           location=(px - 2.6, py + 1.0, -0.4), rotation=4.0)
    N.pine(collection, height=19.0, seed=1, style="ancient", lod="hero", name=U.name(KEY, "pine"),
           parent=root, location=(px, py, 0.6), lean_toward=PINE_AZ + math.radians(8))

    # 6b. the Divine Condor 神雕 on its crag right of the pavilion below the moon, in profile to the hold, and
    #     Xiaolongnü's golden-bell ribbon 金鈴索 coiled on its rock beside it (round 34, sect/lib/refs_west.py coil)
    from sect.lib import refs_west as RW
    bird = divine_condor(collection, root)
    rocks = condor_rocks(bird)
    RW.coil(collection, root, rocks[0], bird, rocks)

    # 7. stone lanterns: flanking the arch and the tier stairs
    for sx in (-1, 1):
        P.lantern_stone(collection, 2.8, name=U.name(KEY, "lantern"), parent=root,
                        location=(sx * 15.6, ARCH_Y - 1.2, 0))
        P.lantern_stone(collection, 2.4, name=U.name(KEY, "lantern"), parent=root,
                        location=(sx * 6.4, -MID_R - 2.4, 0))

    # 8. two cranes flying toward the moon (silhouette cue for the last frames): placed on
    #    the final camera's line of sight, beside the moon disc, heading toward it
    cam = Vector(CAMERA_HINTS[-1]["location"])
    for size, daz, el, dist in ((1.3, -9.0, 22.0, 75.0), (1.1, -5.5, 25.0, 95.0)):
        az = MOON_AZ_LOCAL_DEG + daz
        p = cam + _dir(az, el) * dist
        P.crane(collection, "flying", size, name=U.name(KEY, "crane"), parent=root,
                location=_r3(p), rotation=(0.15, 0, math.pi - math.radians(az + 6.0)))

    return root


# preview: the look.py harness renders these when asked by name (--cams approach,rise,moon)
build.preview_cameras = [(h["name"], h["location"], h["target"], h["lens"]) for h in CAMERA_HINTS]
