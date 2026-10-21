"""Artifact Forge Peak 炼器峰 (site section 'projects').

Blocking pass (spec section 0): shape, scale, colour coding and camera matter, not detail.

Layout (local frame, front = -Y, z = 0 walkable top, footprint 50 m):
- round white-marble courtyard (r 47.5) with a balustrade, open at the front (-Y) and at the
  bridge opening (189.5 deg, west-south-west)
- the walking route (architecture-audit.md 1.3): the stair from the mirror tops out on a 12 x 11 m
  arrival landing (y -58 .. -47, between two stone lanterns) on the axis, then the three-bay
  archway, the paved courtyard, the cauldron dais (stairs front and back) and the hall stair. The
  way out: across the courtyard to a one-bay archway in the balustrade opening and onto an
  8 x 10 m bridgehead terrace where the chain bridge to the arena starts
- the two-tier forge hall (double eave, charcoal tiles) at the back, its lattice front removed so
  the glowing furnaces inside show; plaque 炼器峰 under the upper eave
- two furnace chimneys behind the hall trailing smoke
- in front of the hall, on an octagonal dais: the colossal bronze ding (8 m) glowing molten,
  with ember sparks; around it a tilted ring of the 11 winning projects' artifacts (FORGE_RING), each
  made for its project, on a parent Empty that turns once, linearly, over frames 1-1500
- a jade rune ring on the paving under the orbit
- side workshops, anvils, quench troughs, weapon racks, ore piles, stone lanterns, banners
- on the west of the yard, facing the hold camera: the Golden Wheel Lama's five wheels (金轮法王 金银铜铁铅五轮, The
  Return of the Condor Heroes) in a graded row on a rosewood stand (_five_wheels), in place of a weapon rack
- on the open paving right of the dais, in front of the hall's east bays: Dugu Qiubai's Sword Tomb (独孤求败 剑冢, The
  Return of the Condor Heroes): a cairn on a natural rock outcrop, a bluestone slab with four socket stones, the keen
  steel sword and the rotted wooden sword planted in the outer two, the soft sword's and heavy sword's sockets empty
  (_sword_tomb)
"""

import math
import os
import random

import bmesh
import bpy

from sect.lib import arch as A
from sect.lib import materials as M
from sect.lib import nature  # noqa: F401  (registers nature_rock_small, nature_soil_moss: the tomb's cairn)
from sect.lib import props as P
from sect.lib import util as U


def _fix_font_paths():
    """On the Linux render box the project and fonts are mirrored at '/E:/...' and '/C:/...'.
    os.path.exists('C:/...') succeeds there (cwd is '/'), but Blender rewrites 'C:/x' to '/c/x'
    and fails to load the font. Point the lib at the absolute mirror path instead. No-op on
    Windows."""
    if os.name == "nt":
        return
    for attr in ("FONT_KAITI", "FONT_YAHEI"):
        p = getattr(U, attr, "")
        if len(p) > 2 and p[1] == ":" and os.path.exists("/" + p):
            setattr(U, attr, "/" + p)


_fix_font_paths()

# the chain bridge to the arena leaves along this direction (architecture-audit.md 1.3, W5)
BRIDGE_ANG = math.radians(189.5)

# arrival / depart: where the incoming stair and the outgoing chain bridge meet this area, as
# (x, y, z, heading) in the local frame. z is the landing's top. heading is the walking
# direction in radians, measured like world.py's yaw = atan2(dy, dx): 0 = +x, pi/2 = +y.
# (architecture-audit.md 1.3 and W1, W5)
AREA = dict(key="forge", section_id="projects", title_en="Artifact Forge Peak",
            title_zh="炼器峰", footprint=50.0,
            arrival=(0.0, -58.0, 0.0, math.pi / 2),    # front edge of the arrival landing, heading +y
            depart=(-53.3, -8.9, 0.0, BRIDGE_ANG))     # on the bridgehead, heading out along the bridge

KEY = "forge"

# Where the fly-through camera should pass (local coordinates, front = -Y), ordered along the
# flight: approach on the axis, close pass in front of the cauldron and artifact ring from the
# right, sweep across to the left, then rise looking down on the ring.
CAMERA_HINTS = [
    dict(name="approach", location=(0.0, -92.0, 27.0), target=(0.0, -6.0, 8.0), lens=28),
    dict(name="hero", location=(20.0, -34.0, 10.5), target=(0.0, -8.0, 8.0), lens=24),
    dict(name="pass", location=(-17.0, -32.0, 13.0), target=(2.0, -7.0, 7.5), lens=24),
    dict(name="rise", location=(-30.0, -40.0, 34.0), target=(0.0, -2.0, 5.0), lens=28),
]

# key positions (local)
TERRACE_R = 47.5
DAIS_C = (0.0, -9.0)          # cauldron dais centre
DAIS_H = 1.2
DING_SIZE = 8.0
RING_R = 13.0                 # artifact orbit radius
RING_Z = 9.5                  # orbit centre height
RING_TILT = math.radians(12)  # front of the ring dips toward the camera
ART_SIZE = 4.2
HOOP_R = 0.09                 # glowing orbit hoop through the artifacts
HALL_Y = 24.0
CHIMNEY_Y = HALL_Y + 15.0
SPIN_FRAMES = (1, 1500)
# the ring holds the projects that won, biggest win first (the order of client/src/lib/portfolio-data/hackathons.ts),
# each with an artifact chosen for it (client/src/lib/sect/artifacts.ts FORGE_RING tells the same story). CourtVision,
# SecWay, TalkTuahDuck and InstaRizz did not win and stay off the ring (their mirror, seal, duck censer and
# blossom fan are still in props.ARTIFACT_KINDS).
FORGE_RING = (("dispatchai", "command_flag"), ("talktuahbank", "treasure_bowl"), ("sentinelai", "bell"),
              ("adapted", "bamboo_slips"), ("soundsearch", "lotus_lamp"), ("vocalyze", "spirit_brush"),
              ("tft", "immortal_peaches"), ("slugmeditate", "bead_string"), ("splatnft", "jade_disc"),
              ("swarmaid", "paper_cranes"), ("slugloop", "fire_wheel"))
FORGE_ARTIFACTS = tuple(kind for _, kind in FORGE_RING)
RING_FRONT = math.radians(-135.0)  # ring angle (unturned) that faces the reader at the forge hold, frame 352
                                   # (export_web.FULL_SCENE_FRAME); measured from meta.json and camera.json
BRIDGE_GAP = math.radians(6.0)  # half-angle of the balustrade opening at the bridge (9.8 m)


def _n(*parts):
    return U.name(KEY, *parts)


# ------------------------------------------------------------------ materials

def _forge_smoke(g, colour="#8f8a84", opacity=0.6):
    """Coarse grey smoke for 20-30 m chimney plumes (props_smoke_wisp is tuned for incense)."""
    g.blended(shadows=False)
    z = g.sep(g.coord("generated"))[2]
    fade = g.mul(g.smooth(z, 0.0, 0.08), g.math('POWER', g.math('SUBTRACT', 1.0, z), 1.1))
    v = g.flow(g.coord("object"), (0, 0, -0.03))
    n = g.noise(g.mapping(v, scale=(0.32, 0.32, 0.12)), 1.0, detail=3.0, roughness=0.55)
    br = g.smooth(n, 0.28, 0.6)
    a = g.mul(g.mul(fade, br), opacity)
    g.viewport(colour, 1.0)
    g.output(g.principled(base_color=colour, roughness=1.0, alpha=a, specular_ior_level=0.0))


M.register("forge_smoke", _forge_smoke)


# ------------------------------------------------------------------ helpers

def _paving(root, coll):
    """Round courtyard slab: concentric quad rings (no centre fan, so marble_paving stays clean),
    top at z = 0, side down to z = -0.8."""
    segs = 96
    radii = [3.0, 8.0, 14.0, 20.0, 26.0, 32.0, 38.0, 43.0, TERRACE_R]
    verts, faces, mats = [], [], []

    def ring(r, z):
        base = len(verts)
        for k in range(segs):
            a = 2 * math.pi * k / segs
            verts.append((r * math.cos(a), r * math.sin(a), z))
        return base

    rings = [ring(r, 0.0) for r in radii]
    faces.append(tuple(rings[0] + k for k in range(segs)))
    mats.append(1)
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(segs):
            k2 = (k + 1) % segs
            faces.append((a + k, b + k, b + k2, a + k2))     # normals up (walkcheck reads floors by normal)
            mats.append(1)
    lip = ring(TERRACE_R, -0.25)
    low = ring(TERRACE_R - 0.4, -0.8)
    top = rings[-1]
    for a, b in ((top, lip), (lip, low)):
        for k in range(segs):
            k2 = (k + 1) % segs
            faces.append((a + k, b + k, b + k2, a + k2))
            mats.append(0)
    faces.append(tuple(low + k for k in reversed(range(segs))))
    mats.append(0)
    U.mesh_from_pydata(_n("paving"), verts, faces, coll, materials=["marble_white", "marble_paving"],
                       material_indices=mats, smooth=False, parent=root)


def _terrace_balustrade(root, coll):
    """Marble balustrade along the rim in two arcs: open over the front (-Y) where the stair
    arrives, and at BRIDGE_ANG where the chain bridge leaves (-76 .. 183.5 deg, 195.5 .. 256 deg)."""
    r = TERRACE_R - 0.8
    gap = math.radians(14)                      # half-angle of the front opening
    arcs = ((-math.pi / 2 + gap, BRIDGE_ANG - BRIDGE_GAP), (BRIDGE_ANG + BRIDGE_GAP, 1.5 * math.pi - gap))
    for i, (a0, a1) in enumerate(arcs):
        n = max(2, int(round(64 * (a1 - a0) / (2 * math.pi - 2 * gap))))
        pts = [(r * math.cos(a0 + (a1 - a0) * k / n), r * math.sin(a0 + (a1 - a0) * k / n), 0.0)
               for k in range(n + 1)]
        A.balustrade(_n("balustrade", i), coll, pts, height=1.1, post_spacing=2.2, parent=root)


def _arrival(root, coll):
    """Arrival landing on the axis outside the front archway: top flush with the paving, on the
    world terrace (z -0.4), where the stair from the mirror tops out (audit 1.3 item 2)."""
    A.platform(_n("arrival"), coll, 12.0, depth=11.0, height=0.4, style="plain", parent=root,
               location=(0.0, -52.5, -0.4))                     # y -58 .. -47
    for x in (-5.0, 5.0):
        P.lantern_stone(coll, 2.6, name=_n("lantern_arrival"), parent=root, location=(x, -56.0, 0.0))


def _bridgehead(root, coll):
    """Bridgehead terrace and a one-bay archway in the balustrade opening at BRIDGE_ANG, where the
    chain bridge to the arena starts (audit 1.3 item 3). The platform is named forge.bridgehead
    so walkcheck counts it as a landing."""
    rot = BRIDGE_ANG - math.pi / 2                              # 99.5 deg: depth runs radially
    A.platform(_n("bridgehead"), coll, 8.0, depth=10.0, height=0.4, style="plain", parent=root,
               location=(-51.3, -8.6, -0.4), rotation_z=rot)     # r 47 .. 57, top z 0
    A.paifang(_n("bridge_gate"), coll, bays=1, width=6.0, height=7.0, roof_mat="roof_tile_black",
              parent=root, location=(-46.0, -7.7, 0.0), rotation_z=rot)
    # lanterns flank the bridge foot, 3.4 m either side of the bridge line, so they stand on the
    # platform (the plan's (-52.0, -4.7) / (-50.6, -12.5) put their centres on its side edges)
    c = (-51.3, -8.6)
    t = (-math.sin(BRIDGE_ANG), math.cos(BRIDGE_ANG))
    for sd in (-1.0, 1.0):
        P.lantern_stone(coll, 2.6, name=_n("lantern_bridge"), parent=root,
                        location=(c[0] + sd * 3.4 * t[0], c[1] + sd * 3.4 * t[1], 0.0))


def _open_front(hall_root):
    """hall() always fills the front with lattice doors; a forge hall stands open, so delete the
    door/window leaves, transoms and sill walls of its facade."""
    pre = [hall_root.name + "." + p for p in ("leaf", "transom", "sill")]
    for ob in list(hall_root.children):
        if any(ob.name == p or ob.name.startswith(p + ".") for p in pre):
            U.delete_hierarchy(ob)


def _hang_plaque(building, text, name, min_w=0.0):
    """Hang a horizontal plaque at an arch building's plaque_anchor, sized to its plaque zone."""
    anchor = bpy.data.objects[building["plaque_anchor"]]
    w, h = (float(v) for v in building["plaque_size"])
    width = max(min_w, min(w, h * 2.6))
    return P.plaque(bpy.data.collections[building.users_collection[0].name], text, width, tilt=0.0,
                    name=name, parent=anchor)


def _box_obj(name, coll, size, center, material, parent):
    bm = bmesh.new()
    U.bm_box(bm, size, center=center)
    return U.mesh_from_bmesh(name, bm, coll, materials=[material], smooth=False, parent=parent)


def _furnaces(root, coll, z0):
    """Glowing brick furnaces inside the open hall (x, y local to the hall at HALL_Y)."""
    for i, (x, w, h) in enumerate(((0.0, 5.0, 4.6), (-7.5, 3.6, 3.4), (7.5, 3.6, 3.4))):
        y = HALL_Y + 1.6
        _box_obj(_n("furnace", i), coll, (w, 3.2, h), (x, y, z0 + h / 2), "stone_dark", root)
        _box_obj(_n("furnace_top", i), coll, (w * 0.55, 1.8, 1.4), (x, y, z0 + h + 0.7), "stone_dark", root)
        mouth = _box_obj(_n("furnace_mouth", i), coll, (w * 0.55, 0.12, h * 0.42),
                         (x, y - 1.62, z0 + h * 0.36), "molten", root)
        mouth["glow"] = 2.5
    light = bpy.data.lights.new(_n("furnace_light"), 'POINT')
    light.energy = 6000.0
    light.color = (1.0, 0.45, 0.15)
    light.shadow_soft_size = 1.5
    ob = bpy.data.objects.new(_n("furnace_light"), light)
    coll.objects.link(ob)
    ob.parent = root
    ob.location = (0.0, HALL_Y - 1.5, z0 + 3.0)


def _flues(root, coll, z0):
    """1.4 x 1.4 m stone flues from the back of the side furnaces (x +-7.5, y 27.2) through the
    hall's back wall to the chimney bases (x +-10, y 35.6) (audit section 4). The block runs down
    to the paving so it stands on the ground behind the hall platform; its ends tuck into the
    furnace and the chimney."""
    h = z0 + 1.4
    for i, sx in enumerate((-1.0, 1.0)):
        ax, ay = sx * 7.5, HALL_Y + 1.6 + 1.6                    # furnace back
        bx, by = sx * 10.0, CHIMNEY_Y - 3.4                      # chimney base edge
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        ux, uy = dx / L, dy / L
        e0, e1 = 0.4, 1.2                                        # overlap into furnace / chimney
        mx = (ax - ux * e0 + bx + ux * e1) * 0.5
        my = (ay - uy * e0 + by + uy * e1) * 0.5
        bm = bmesh.new()
        U.bm_box(bm, (L + e0 + e1, 1.4, h), center=(0.0, 0.0, h * 0.5))
        U.mesh_from_bmesh(_n("flue", i), bm, coll, materials=["stone_dark"], smooth=False, parent=root,
                          location=(mx, my, 0.0), rotation=(0.0, 0.0, math.atan2(dy, dx)))


def _chimney(root, coll, i, x, y, height=26.0):
    """Furnace kiln tower in the Chinese manner: octagonal tapered stone stack on a stepped base,
    an open vent storey of red posts with a glowing fire inside, a small eight-sided tiled
    pyramid roof on top, and a smoke plume rising through it and drifting sideways."""
    bm = bmesh.new()
    prof = [(0.0, 0.0), (3.4, 0.0), (3.4, 1.0), (3.0, 1.2), (3.0, 2.2), (2.6, 2.5), (1.9, height - 0.8),
            (2.3, height - 0.5), (2.3, height), (0.0, height)]
    U.bm_lathe(bm, prof, segments=8)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    U.mesh_from_bmesh(_n("chimney", i), bm, coll, materials=["stone_dark"], smooth=False, parent=root,
                      location=(x, y, 0.0))
    for k, z in enumerate((height * 0.38, height * 0.72)):     # iron hoops
        bm = bmesh.new()
        r = 2.6 - (2.6 - 1.9) * (z - 2.5) / (height - 3.3) + 0.1
        U.bm_cylinder(bm, radius=r, depth=0.6, segments=8, center=(0, 0, z))
        U.mesh_from_bmesh(_n("chimney_hoop", i, k), bm, coll, materials=["iron"], smooth=False, parent=root,
                          location=(x, y, 0.0))
    # vent storey: 8 red posts around a glowing fire box, then the roof
    vent_h = 2.4
    bm = bmesh.new()
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        U.bm_cylinder(bm, radius=0.16, depth=vent_h, segments=8,
                      center=(1.9 * math.cos(a), 1.9 * math.sin(a), height + vent_h / 2))
    U.mesh_from_bmesh(_n("chimney_posts", i), bm, coll, materials=["lacquer_red"], smooth=False, parent=root,
                      location=(x, y, 0.0))
    fire = _box_obj(_n("chimney_fire", i), coll, (2.0, 2.0, 1.4), (x, y, height + 0.7), "molten", root)
    fire["glow"] = 3.0
    A.roof(_n("chimney_roof", i), coll, 3.8, kind="pyramid", sides=8, tile_mat="roof_tile_black",
           detail="low", parent=root, location=(x, y, height + vent_h))
    s = 1 if x > 0 else -1
    z0 = height + 1.0
    pts = [(x, y, z0, 0.9), (x + 0.3 * s, y + 0.3, z0 + 6, 1.4),
           (x + 1.8 * s, y + 1.2, z0 + 12, 2.2), (x + 4.5 * s, y + 2.4, z0 + 18, 3.2),
           (x + 8.5 * s, y + 3.6, z0 + 24, 4.2), (x + 13.5 * s, y + 4.6, z0 + 29, 5.0)]
    sm = U.tube_mesh(_n("chimney_smoke", i), pts, 1.1, coll, material="forge_smoke", sides=12,
                     samples_per_segment=6, caps=False, parent=root)
    U.set_visibility(sm, shadow=False)


def _quench_trough(root, coll, i, x, y):
    _box_obj(_n("trough", i), coll, (1.5, 4.2, 0.9), (x, y, 0.45), "stone_grey", root)
    _box_obj(_n("trough_water", i), coll, (1.2, 3.9, 0.06), (x, y, 0.9), "water_pond", root)


# ------------------------------------------------------------------ the Golden Wheel Lama's five wheels
# Jinlun Fawang 金轮法王 (The Return of the Condor Heroes) fights with five wheels of gold, silver, copper, iron and
# lead (金银铜铁铅五轮), different in weight and shape, all cast with mantras; the gold wheel is about 1.5 chi across,
# hollow, with nine small balls inside that ring when it is shaken. Here the five stand in a graded row on a
# rosewood display stand (2x canon so they read), in place of the weapon rack forge.weapon_rack.001 (the one rack
# readable at the forge hold). The _fw_* geometry helpers use plain math only (an offline check runs them without
# Blender); _five_wheels() turns them into objects. Stand frame: x along the row (gold at +x, the reader's right),
# front -Y, z up, origin on the ground at the stand's centre. Each wheel is built around its axle (local Y), front
# face (the ornament band, windows and balls) toward -Y, then leant back against the rail. The novel's "different in
# shape" is the blade: four wheels have nine hooked teeth in the cutting edge (a flying wheel's saw), the soft lead one
# stays round and blunt (FW_TOOTH; all 0.0 gives the plain round edge).

FW_NAME = "forge.five_wheels"
FW_LOC = (-24.0, -15.5)            # local (x, y) of the rack it replaces
FW_ROT_Z = 0.96                    # front (-Y) faces local -35 deg: the hold camera (352) and the pass (380-398)
FW_WHEELS = (("gold", "gold", 1.00), ("silver", "silver", 0.92), ("copper", "forge_copper", 0.85),   # (key,
             ("iron", "iron", 0.78), ("lead", "forge_lead", 0.71))                                    # material, diameter m)
# the five metals must stay apart where the bake shows metals as flat base colour: the shared 'steel' baked near-white
# like the silver wheel and 'bronze' olive like a dull gold, so the row read white-dark-brown-white-gold. Lead is a dull
# matte blue-grey between iron and silver (its worn edges barely lighter: lead is soft), copper a red copper.
M.register("forge_lead", M._metal, base="#8a9098", dark="#646a72", rough=(0.55, 0.75), tarnish=0.5,
           edge_col="#a3a9b0")
M.register("forge_copper", M._metal, base="#a65f3a", dark="#62351f", rough=(0.3, 0.5), tarnish=0.45,
           edge_col="#d39468")
FW_RECESS_MAT = "lacquer_black"    # the dark floors of the windows in the ornament band
FW_STAND_MATS = ("wood_dark", "gold")
FW_PHASE = (0.0, 13.0, 26.0, 7.0, 19.0)   # deg each wheel is turned on its axle (a toothed wheel: so it stands on a
                                          # tooth's point, see _fw_layout)
FW_GAP = 0.08                      # between neighbouring wheels
FW_SEAT_Z = 0.75                   # wheel bottoms, in the cradles
FW_LEAN = math.radians(8.0)        # the gold wheel's lean; the others are solved so their backs rest on the rail
FW_RAIL = (0.085, 1.36, 0.025)     # back rail (y, z, radius): below the lead wheel's top (1.45), above every centre
FW_POST_X = 2.385                  # end post centres; posts 0.14 x 0.17, outer faces at +-2.455 (4.9 m wide)
FW_Y = -0.02                       # post / beam centre line
FW_TRI_CAP = 8000                  # per object: bake_web simplifies anything bigger
FW_SHARP = math.radians(15.0)      # creases sharper than this shade hard
# wheel cross-section, (radius, y) in units of R, a closed loop: front face (y < 0) out to the cutting edge, back face
# (flat, it rests on the rail) back to the bore. Thickness 0.12R; the ornament band (0.62-0.78R) stands 0.025R proud
# on the front; the bore is bevelled 0.05R wide; the outer 0.12R is the blade: a main bevel, then a honed edge.
FW_PROFILE = ((0.42, -0.035), (0.47, -0.06), (0.62, -0.06), (0.635, -0.085), (0.765, -0.085), (0.78, -0.06),
              (0.88, -0.06), (0.96, -0.03), (1.0, 0.0), (0.96, 0.03), (0.88, 0.06), (0.42, 0.06))
FW_BAND = 3                        # profile edge 3 -> 4 is the band top, where the windows are cut
FW_EDGE_FACES = (0, 2, 3, 4, 6, 7, 8, 9)   # profile edges flagged as worn (lighter tint of the metal): the bevelled
                                          # bore, the ornament band and the whole blade (the petals too), so the
                                          # wheel reads as a bright band and a bright cutting edge on its body
FW_WINDOWS = 9
FW_COLS_BAY = 7                    # lathe columns per window bay: 9 x 7 = 63 around (one column pair per window)
FW_WIN_HALF = 0.0929               # window half-angle (rad): 0.13R wide at the band's middle (0.70R), square
FW_WIN_DEPTH = 0.6 * 0.12          # recess depth: 60 % of the body thickness, from the band top
FW_BALL_R = 0.045                  # the nine balls (units of R)
FW_PETALS_BAY = 3                  # lotus-petal bosses between two windows (27 around)
FW_TOOTH = dict(gold=0.10, silver=0.10, copper=0.10, iron=0.10, lead=0.0)   # tooth depth (units of R), one tooth per
                                                                            # bay: the edge climbs over 6 columns, drops
                                                                            # in 1 (a hook)


def _fw_newell(vs):
    nx = ny = nz = 0.0
    for k in range(len(vs)):
        a, b = vs[k], vs[(k + 1) % len(vs)]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return nx, ny, nz


def _fw_volume(verts, faces):
    """Signed volume of a closed polygon soup (fan triangulation; exact for planar simple polygons)."""
    s = 0.0
    for f in faces:
        a = verts[f[0]]
        for k in range(1, len(f) - 1):
            b, c = verts[f[k]], verts[f[k + 1]]
            s += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                  + a[2] * (b[0] * c[1] - b[1] * c[0]))
    return s / 6.0


def _fw_convex(verts, faces):
    """Wind every face of a convex part so its normal points away from the part's centre."""
    n = float(len(verts))
    c = [sum(v[k] for v in verts) / n for k in range(3)]
    out = []
    for f in faces:
        vs = [verts[i] for i in f]
        nm = _fw_newell(vs)
        fc = [sum(v[k] for v in vs) / len(vs) for k in range(3)]
        out.append(tuple(f) if sum(nm[k] * (fc[k] - c[k]) for k in range(3)) >= 0 else tuple(reversed(f)))
    return out


def _fw_geo():
    return dict(v=[], f=[], m=[], e=[], soft=[], parts=0)


def _fw_add(g, verts, faces, mat=0, edge=None, soft=False):
    """Append one closed part (faces index ``verts``) to geometry ``g``; turn it inside out if its signed volume is
    negative, so every part points out (bake_web's fix_normals / facing_flip rely on that)."""
    faces = [tuple(f) for f in faces]
    if _fw_volume(verts, faces) < 0:
        faces = [tuple(reversed(f)) for f in faces]
    base = len(g["v"])
    g["v"].extend(tuple(float(c) for c in v) for v in verts)
    for k, f in enumerate(faces):
        g["f"].append(tuple(base + i for i in f))
        g["m"].append(mat[k] if isinstance(mat, (list, tuple)) else mat)
        g["e"].append(float(edge[k]) if isinstance(edge, (list, tuple)) else float(edge or 0.0))
        g["soft"].append(bool(soft))
    g["parts"] += 1


def _fw_box(g, c, size, ch=0.0, mat=0):
    """Box (size x, y, z at centre c), its edges chamfered by ``ch`` (the chamfers carry the edge-wear flag)."""
    h = [s * 0.5 for s in size]
    sg = (-1, 1)
    if ch <= 0.0:
        idx = {}
        verts = []
        for sx in sg:
            for sy in sg:
                for sz in sg:
                    idx[(sx, sy, sz)] = len(verts)
                    verts.append((c[0] + sx * h[0], c[1] + sy * h[1], c[2] + sz * h[2]))
        faces = []
        for a in range(3):
            b, d = (a + 1) % 3, (a + 2) % 3
            for s in sg:
                ring = []
                for pb, pd in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    k = [0, 0, 0]
                    k[a], k[b], k[d] = s, pb, pd
                    ring.append(idx[tuple(k)])
                faces.append(ring)
        _fw_add(g, verts, _fw_convex(verts, faces), mat, 0.0)
        return
    # chamfered: three vertices per corner, one on each of the corner's faces
    idx = {}
    verts = []
    for sx in sg:
        for sy in sg:
            for sz in sg:
                s = (sx, sy, sz)
                for a in range(3):
                    p = [c[k] + s[k] * (h[k] if k == a else h[k] - ch) for k in range(3)]
                    idx[(s, a)] = len(verts)
                    verts.append(tuple(p))
    faces, edge = [], []
    for a in range(3):                                  # main faces
        b, d = (a + 1) % 3, (a + 2) % 3
        for s in sg:
            ring = []
            for pb, pd in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                k = [0, 0, 0]
                k[a], k[b], k[d] = s, pb, pd
                ring.append(idx[(tuple(k), a)])
            faces.append(ring)
            edge.append(0.0)
    for a in range(3):                                  # chamfer strips along the edges parallel to axis a
        b, d = (a + 1) % 3, (a + 2) % 3
        for sb in sg:
            for sd in sg:
                k0, k1 = [0, 0, 0], [0, 0, 0]
                k0[a], k0[b], k0[d] = -1, sb, sd
                k1[a], k1[b], k1[d] = 1, sb, sd
                k0, k1 = tuple(k0), tuple(k1)
                faces.append([idx[(k0, b)], idx[(k1, b)], idx[(k1, d)], idx[(k0, d)]])
                edge.append(1.0)
    for sx in sg:                                       # corner triangles
        for sy in sg:
            for sz in sg:
                s = (sx, sy, sz)
                faces.append([idx[(s, 0)], idx[(s, 1)], idx[(s, 2)]])
                edge.append(1.0)
    _fw_add(g, verts, _fw_convex(verts, faces), mat, edge)


def _fw_strut(g, p0, p1, w, mat=0):
    """Square strut (w x w) from p0 to p1 in a plane x = const (its sides stay along x)."""
    ax = [p1[k] - p0[k] for k in range(3)]
    L = math.sqrt(sum(a * a for a in ax))
    ax = [a / L for a in ax]
    sv = (1.0, 0.0, 0.0)
    tv = (ax[1] * sv[2] - ax[2] * sv[1], ax[2] * sv[0] - ax[0] * sv[2], ax[0] * sv[1] - ax[1] * sv[0])
    verts = []
    for p in (p0, p1):
        for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            verts.append(tuple(p[k] + 0.5 * w * (a * sv[k] + b * tv[k]) for k in range(3)))
    faces = [(0, 1, 2, 3), (4, 5, 6, 7)] + [(k, (k + 1) % 4, 4 + (k + 1) % 4, 4 + k) for k in range(4)]
    _fw_add(g, verts, _fw_convex(verts, faces), mat, 0.0)


def _fw_rod(g, x0, x1, y, z, r, sides=8, mat=0):
    """Round rod along x."""
    verts = []
    for x in (x0, x1):
        for k in range(sides):
            a = 2 * math.pi * (k + 0.5) / sides
            verts.append((x, y + r * math.cos(a), z + r * math.sin(a)))
    faces = [tuple(range(sides)), tuple(range(sides, 2 * sides))]
    faces += [(k, (k + 1) % sides, sides + (k + 1) % sides, sides + k) for k in range(sides)]
    _fw_add(g, verts, _fw_convex(verts, faces), mat, 0.0)


def _fw_lathe_z(g, c, profile, segs, lobes=None, mat=0):
    """Solid of revolution around the vertical through c: profile [(r, dz)] bottom to top, r 0 = pole, the first
    ring capped. ``lobes`` {profile index: (count, depth)} scallops that ring into petals."""
    verts, rings = [], []
    for i, (r, dz) in enumerate(profile):
        if r <= 1e-9:
            rings.append([len(verts)])
            verts.append((c[0], c[1], c[2] + dz))
            continue
        ring = []
        for j in range(segs):
            a = 2 * math.pi * j / segs
            rr = r
            if lobes and i in lobes:
                n, dep = lobes[i]
                rr = r * (1.0 - dep * 0.5 * (1.0 - math.cos(n * a)))
            ring.append(len(verts))
            verts.append((c[0] + rr * math.cos(a), c[1] + rr * math.sin(a), c[2] + dz))
        rings.append(ring)
    faces = [tuple(reversed(rings[0]))]
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(segs):
            j2 = (j + 1) % segs
            if len(b) == 1:
                faces.append((a[j], a[j2], b[0]))
            else:
                faces.append((a[j], a[j2], b[j2], b[j]))
    _fw_add(g, verts, faces, mat, 0.0)


def _fw_prism_xz(g, outline, y0, y1, mat=0, edge=0.0):
    """Outline [(x, z)] (a simple polygon, may be concave) extruded along y from y0 to y1."""
    n = len(outline)
    verts = [(x, y0, z) for x, z in outline] + [(x, y1, z) for x, z in outline]
    faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    faces += [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    _fw_add(g, verts, faces, mat, edge)


def _fw_layout():
    """The five wheels on the stand: key, material, radius R, x, lean (rad), centre (x, y, z), phase (deg).
    Graded right to left (gold at +x) with FW_GAP between rims, the row centred. Each rim rests at FW_SEAT_Z on the
    cradle line y_c; its flat back touches the rail. With A = rail_y - y_c, B = rail_z - seat and K = half thickness +
    rail radius, the contact condition A cos(lean) - B sin(lean) = K does not depend on R otherwise, so the gold
    wheel's lean (FW_LEAN) fixes y_c and the others are solved."""
    ry, rz, rr = FW_RAIL
    B = rz - FW_SEAT_Z
    R0 = FW_WHEELS[0][2] * 0.5
    A = (0.06 * R0 + rr + B * math.sin(FW_LEAN)) / math.cos(FW_LEAN)
    yc = ry - A
    span = sum(d for _, _, d in FW_WHEELS) + FW_GAP * (len(FW_WHEELS) - 1)
    out = []
    x = span * 0.5
    bay = 2 * math.pi / FW_WINDOWS
    tip = FW_WIN_HALF + (FW_COLS_BAY - 3) * (bay - 2 * FW_WIN_HALF) / (FW_COLS_BAY - 2)   # a tooth's point, from
    for i, (key, mat, d) in enumerate(FW_WHEELS):                                       # its bay's window centre
        R = d * 0.5
        x -= R
        K = 0.06 * R + rr
        lean = math.acos(K / math.hypot(A, B)) - math.atan2(B, A)
        centre = (x, yc + R * math.sin(lean), FW_SEAT_Z + R * math.cos(lean))
        tooth = FW_TOOTH.get(key, 0.0)
        phase = FW_PHASE[i]
        if tooth > 0:       # a toothed wheel rests on a tooth's point: turn one to the bottom (-90 deg)
            phase = (180.0 - math.degrees(tip)) % math.degrees(bay)
        out.append(dict(key=key, mat=mat, R=R, x=x, lean=lean, centre=centre, phase=phase, tooth=tooth, yc=yc))
        x -= R + FW_GAP
    return out


def _fw_stand(lay):
    """Rosewood display stand (materials 0 wood_dark, 1 gold): two end posts on sled feet with braces, gold bands and
    gold lotus-bud finials, a top beam with through-tenon ends, a low base beam, the cradle beam (top at 0.68 m) on
    four short balusters, a carved U-cradle under each wheel and the back rail the wheels lean on. 4.9 x 0.7 x 2.35 m."""
    g = _fw_geo()
    px, y0 = FW_POST_X, FW_Y
    yc = lay[0]["yc"]
    for sx in (-1.0, 1.0):
        x = sx * px
        _fw_box(g, (x, y0, 0.05), (0.16, 0.70, 0.10), 0.02)                 # sled foot
        _fw_box(g, (x, y0, 1.11), (0.14, 0.17, 2.04), 0.012)                # post 0.09 .. 2.13 (sunk 1 cm into the foot)
        for ya, yb in ((-0.30, -0.06), (0.26, 0.05)):                       # braces, foot to post (ends buried)
            _fw_strut(g, (x, y0 + ya, 0.06), (x, y0 + yb, 0.40), 0.05)
        for z in (0.70, 1.92):                                              # gold bands at the beam joints
            _fw_box(g, (x, y0, z), (0.152, 0.182, 0.03), 0.0, mat=1)
        _fw_box(g, (x, y0, 2.14), (0.165, 0.195, 0.03), 0.004, mat=1)       # gold cap 2.125 .. 2.155
        _fw_lathe_z(g, (x, y0, 2.15), ((0.045, 0.0), (0.056, 0.017), (0.074, 0.037), (0.034, 0.055), (0.054, 0.093),
                                       (0.05, 0.133), (0.027, 0.173), (0.0, 0.2)), 10,
                    lobes={2: (5, 0.3), 1: (5, 0.12)}, mat=1)              # lotus bud finial, to 2.35
    _fw_box(g, (0.0, y0, 2.0), (2 * px + 0.16, 0.14, 0.12), 0.012)          # top beam, ends 1 cm proud
    for sx in (-1.0, 1.0):                                                  # gold caps on the beam ends
        _fw_box(g, (sx * (px + 0.0825), y0, 2.0), (0.015, 0.15, 0.13), 0.0, mat=1)
    _fw_box(g, (0.0, y0, 0.20), (2 * px - 0.04, 0.10, 0.10), 0.01)          # base beam 0.15 .. 0.25
    _fw_box(g, (0.0, y0, 0.62), (2 * px - 0.04, 0.14, 0.12), 0.012)         # cradle beam 0.56 .. 0.68
    for a, b in zip(lay[:-1], lay[1:]):                                     # balusters in the gaps
        _fw_box(g, ((a["x"] - a["R"] + b["x"] + b["R"]) * 0.5, y0, 0.405), (0.06, 0.06, 0.33), 0.0)
    ry, rz, rr = FW_RAIL
    _fw_rod(g, -px - 0.045, px + 0.045, ry, rz, rr)                         # back rail on the posts' backs
    for w in lay:                                                           # U-cradles: the rim sits in the notch
        R, x = w["R"], w["x"]
        hw = 0.5 * (0.42 * R + 0.10)
        top = 0.80
        arc = []
        for u in (0.8, 0.4, 0.0, -0.4, -0.8):
            ax = u * hw
            arc.append((x + ax, FW_SEAT_Z + R - math.sqrt((R + 0.004) ** 2 - ax * ax)))
        outline = [(x - hw, 0.675), (x + hw, 0.675), (x + hw, top)] + arc + [(x - hw, top)]   # sunk 5 mm into the beam
        _fw_prism_xz(g, outline, yc - 0.05, yc + 0.05)
    return g


def _fw_wheel(R, phase_deg=0.0, tooth=0.0):
    """One wheel of radius R around its axle (local Y), materials 0 = its metal, 1 = the dark window recesses. A lathe
    of FW_PROFILE with 63 columns (9 bays of 7: each window takes two columns), nine square windows cut through the
    band top into recesses 60 % of the thickness deep, a ball in each, and three lotus-petal bosses on the band between
    two windows. ``tooth`` > 0 cuts nine hooked teeth into the blade (its tip pulled in by up to ``tooth`` R). All
    closed parts."""
    g = _fw_geo()
    P = FW_PROFILE
    n = len(P)
    nb, cpb = FW_WINDOWS, FW_COLS_BAY
    nc = nb * cpb
    bay = 2 * math.pi / nb
    dl = FW_WIN_HALF
    step = (bay - 2 * dl) / (cpb - 2)
    th0 = math.pi / 2 + math.radians(phase_deg)          # a window at the top
    th = []
    for b in range(nb):
        c = th0 + b * bay
        th += [c - dl, c] + [c + dl + k * step for k in range(cpb - 2)]

    def V(i, j):
        return i * nc + j

    # tooth: per column, how far the blade tip (profile points 7-9) is pulled in; 0 at each bay's last column (the
    # tooth's point), ``tooth`` at its first (the gullet after the drop)
    pull = [tooth * (1.0 - (j % cpb) / (cpb - 1.0)) for j in range(nc)]
    shrink = {7: 0.7, 8: 1.0, 9: 0.7}
    verts = [(R * (r - shrink.get(i, 0.0) * pull[j]) * math.cos(t), R * y,
              R * (r - shrink.get(i, 0.0) * pull[j]) * math.sin(t))
             for i, (r, y) in enumerate(P) for j, t in enumerate(th)]
    faces, mats, edge = [], [], []
    win = set()
    for b in range(nb):
        win.update((b * cpb, b * cpb + 1))
    for i in range(n):
        i2 = (i + 1) % n
        for j in range(nc):
            if i == FW_BAND and j in win:
                continue
            j2 = (j + 1) % nc
            faces.append((V(i, j), V(i, j2), V(i2, j2), V(i2, j)))
            mats.append(0)
            edge.append(1.0 if i in FW_EDGE_FACES else 0.0)
    # recesses: the hole's rim loop (in the winding of the removed band faces), walls down, a tapered floor
    rc = 0.5 * (P[FW_BAND][0] + P[FW_BAND + 1][0])
    yb = P[FW_BAND][1] + FW_WIN_DEPTH
    i0, i1 = FW_BAND, FW_BAND + 1
    for b in range(nb):
        j = b * cpb
        c = th[j + 1]
        loop = [(i0, j), (i0, j + 1), (i0, j + 2), (i1, j + 2), (i1, j + 1), (i1, j)]
        floor = []
        for (i, jj) in loop:
            k = 0.86 if jj == j + 1 else 0.74
            r = rc + k * (P[i][0] - rc)
            t = c + k * (th[jj] - c)
            floor.append(len(verts))
            verts.append((R * r * math.cos(t), R * yb, R * r * math.sin(t)))
        for k in range(6):                                  # walls in the wheel's metal (dark by depth)
            a, bb = V(*loop[k]), V(*loop[(k + 1) % 6])
            fa, fb = floor[k], floor[(k + 1) % 6]
            faces.append((a, bb, fb, fa))
            mats.append(0)
            edge.append(0.0)
        faces.append(tuple(floor))                          # the dark floor: a black ring round the ball
        mats.append(1)
        edge.append(0.0)
    _fw_add(g, verts, faces, mats, edge)
    # the nine balls, resting on the recess floors and standing a little proud of the band
    rb = FW_BALL_R * R
    for b in range(nb):
        c = th[b * cpb + 1]
        _fw_ball(g, (R * rc * math.cos(c), R * yb - rb + 0.004 * R, R * rc * math.sin(c)), rb)
    # lotus-petal bosses on the band top, tips pointing out
    ytop = P[FW_BAND][1]
    L, h = 0.115 * R, 0.017 * R
    slot = (bay - 2 * dl) / FW_PETALS_BAY
    W = 0.78 * rc * R * slot
    for b in range(nb):
        for k in range(FW_PETALS_BAY):
            t = th0 + b * bay + dl + (k + 0.5) * slot
            _fw_petal(g, rc * R, t, L, W, h, R * ytop, 0.004 * R, edge=1.0)
    return g


def _fw_ball(g, c, r, u=6, v=3):
    """Small UV sphere (poles along y, 24 triangles: it is a few pixels on the page), smooth shaded."""
    verts = [(c[0], c[1] - r, c[2])]
    for i in range(1, v):
        p = math.pi * i / v
        for j in range(u):
            a = 2 * math.pi * j / u
            verts.append((c[0] + r * math.sin(p) * math.cos(a), c[1] - r * math.cos(p), c[2] + r * math.sin(p) * math.sin(a)))
    verts.append((c[0], c[1] + r, c[2]))
    top = len(verts) - 1
    faces = []
    for j in range(u):
        faces.append((0, 1 + (j + 1) % u, 1 + j))
    for i in range(v - 2):
        for j in range(u):
            a, b = 1 + i * u, 1 + (i + 1) * u
            faces.append((a + j, a + (j + 1) % u, b + (j + 1) % u, b + j))
    last = 1 + (v - 2) * u
    for j in range(u):
        faces.append((last + j, last + (j + 1) % u, top))
    _fw_add(g, verts, faces, 0, 0.0, soft=True)


def _fw_petal(g, rc, t, L, W, h, ytop, sink, edge=0.0):
    """Lotus-petal boss on the band top (y = ytop, front toward -y) at radius rc, angle t: a six-sided pointed oval
    (tip outward) raised to a ridge point by h, its floor sunk ``sink`` into the band."""
    ca, sa = math.cos(t), math.sin(t)

    def P(u, w, y):
        r, s = rc + u, w
        return (r * ca - s * sa, y, r * sa + s * ca)

    ol = ((0.5, 0.0), (0.12, 0.46), (-0.28, 0.46), (-0.5, 0.0), (-0.28, -0.46), (0.12, -0.46))
    verts = [P(u * L, w * W, ytop + sink) for u, w in ol] + [P(-0.15 * L, 0.0, ytop - h)]
    faces = [tuple(range(6))] + [(6, k, (k + 1) % 6) for k in range(6)]
    _fw_add(g, verts, _fw_convex(verts, faces), 0, edge)


def _fw_sharp_edges(g):
    """{(a, b): sharp} for every edge: creases over FW_SHARP shade hard, except between two soft faces (balls)."""
    nrm = []
    for f in g["f"]:
        nx, ny, nz = _fw_newell([g["v"][i] for i in f])
        ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        nrm.append((nx / ln, ny / ln, nz / ln))
    by_edge = {}
    for fi, f in enumerate(g["f"]):
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            by_edge.setdefault((min(a, b), max(a, b)), []).append(fi)
    cos_lim = math.cos(FW_SHARP)
    out = {}
    for e, fs in by_edge.items():
        if len(fs) != 2:
            out[e] = True
            continue
        a, b = fs
        if g["soft"][a] and g["soft"][b]:
            out[e] = False
            continue
        out[e] = sum(nrm[a][k] * nrm[b][k] for k in range(3)) < cos_lim or g["m"][a] != g["m"][b]
    return out


def _fw_object(name, coll, parent, g, materials, location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0)):
    """Mesh object from _fw geometry: material slots, the 'edge' face attribute (edge wear), smooth shading with
    sharp creases."""
    ob = U.mesh_from_pydata(U.unique_name(name), g["v"], g["f"], coll, materials=materials, smooth=True,
                            material_indices=g["m"], location=location, rotation=rotation, parent=parent)
    me = ob.data
    if len(me.polygons) != len(g["f"]) or len(me.vertices) != len(g["v"]):
        raise RuntimeError("%s: mesh validation changed the geometry (%d/%d faces, %d/%d verts)"
                           % (name, len(me.polygons), len(g["f"]), len(me.vertices), len(g["v"])))
    a = me.attributes.get(U.EDGE_ATTR) or me.attributes.new(U.EDGE_ATTR, 'FLOAT', 'FACE')
    a.data.foreach_set("value", g["e"])
    sharp = _fw_sharp_edges(g)
    ev = [0] * (2 * len(me.edges))
    me.edges.foreach_get("vertices", ev)
    flags = [sharp.get((min(ev[2 * k], ev[2 * k + 1]), max(ev[2 * k], ev[2 * k + 1])), True)
             for k in range(len(me.edges))]
    s = me.attributes.get("sharp_edge") or me.attributes.new("sharp_edge", 'BOOLEAN', 'EDGE')
    s.data.foreach_set("value", flags)
    me.update()
    return ob


def _five_wheels(coll, root, x, y):
    """The Golden Wheel Lama's five wheels on their stand at local (x, y): an Empty FW_NAME (turned FW_ROT_Z) holding
    FW_NAME.stand and one mesh per wheel, FW_NAME.<gold|silver|copper|iron|lead>. Returns the Empty."""
    emp = U.empty(U.unique_name(FW_NAME), coll, location=(x, y, 0.0), parent=root, rotation=(0.0, 0.0, FW_ROT_Z),
                  display_size=1.5)
    lay = _fw_layout()
    _fw_object(FW_NAME + ".stand", coll, emp, _fw_stand(lay), list(FW_STAND_MATS))
    for w in lay:
        _fw_object(FW_NAME + "." + w["key"], coll, emp, _fw_wheel(w["R"], w["phase"], w["tooth"]),
                   [w["mat"], FW_RECESS_MAT],
                   location=w["centre"], rotation=(-w["lean"], 0.0, 0.0))
    return emp



# ------------------------------------------------------------------ Dugu Qiubai's Sword Tomb
# 剑冢 (The Return of the Condor Heroes, ch. 26 神雕重剑). The Divine Condor leads Yang Guo to a heap of stones on a cliff
# top; under it, on a long bluestone, lie the swords of Dugu Qiubai 独孤求败, one place for each stage of his life: a keen
# blade flashing blue that he used before twenty; the place of the purple soft sword 紫薇软剑, empty because he threw it
# into a ravine after it hurt a good man; the heavy iron sword 玄铁重剑 (it stands in the arena here, so its place is empty
# too); and a wooden sword rotted with age (after forty, grass, wood, bamboo and stone can all be a sword). The forge,
# the smiths' yard, keeps it as a shrine to swords: a low natural outcrop left standing in the paving, a cairn of stones
# on its higher back ledge, and in front of the cairn a bluestone slab with four identical socket stones in a row. The
# keen steel sword is planted in the first and the wooden sword in the last; the two between stand empty (the soft
# sword's mortise a thin slit, the heavy sword's broad). Four sockets and two swords is what reads from the hold; there
# is no text. The swords are ~2x canon so they read (about 33 px a metre at the hold, 1600 x 900). The wooden sword has
# a short guard, a dark cord grip and a clear lean, so a plain upright stick with a crossbar never reads as a grave
# cross. Tomb frame: origin on the paving at the outcrop's centre, front -Y (the forge gate's side, 13 deg off the hold
# camera's line), +x to the reader's right at the hold. The _st_* geometry helpers are plain math (no bpy; an offline
# check runs them) and feed the five wheels' _fw_add / _fw_box / _fw_lathe_z / _fw_prism_xz / _fw_object.

ST_NAME = "forge.sword_tomb"
ST_LOC = (16.5, 1.5)               # local (x, y): the open paving right of the dais, in front of the hall's east bays
                                   # (an empty white sheet at the hold); 2 m outside the rune ring, 5 m from the east
                                   # workshop and quench trough 1, 6 m in front of the hall
ST_ROT_Z = 0.0                     # front -Y, like the hall; the hold camera (352) sees it from 13 deg east of front
ST_TRI_CAP = 8000                  # per object: bake_web simplifies anything bigger
# the outcrop, two closed layers: (centre x, y, half-size a (x), b (y), bottom z, top z, seed). The low front layer
# carries the slab, the higher back ledge the cairn; bottoms under the paving (z 0) so the rock grows out of it.
ST_ROCK = ((0.0, 0.0, 3.6, 2.85, -0.3, 0.36, 1), (0.0, 0.8, 2.75, 2.0, -0.05, 0.84, 2))
ST_ROCK_P = 2.6                    # superellipse exponent of the outlines (squarish)
ST_ROCK_SEGS = 48
ST_ROCK_SIDE = ((0.0, 0.93), (0.3, 1.0), (0.7, 1.025), (0.92, 1.0))   # (share of bottom..top, outline scale) up a side
ST_ROCK_CAP = (0.97, 0.88, 0.66, 0.4, 0.15)                            # outline scale of the top's rings, outer first
ST_ROCK_LIP = 0.05                 # the outer top ring sits this far under the top surface (a rounded lip)
ST_SLAB = (0.0, -1.65, 4.2, 1.05, 0.4, 0.035)     # bluestone: centre x, y, length (x), depth (y), thickness, chamfer
ST_SLAB_SINK = 0.05                # slab bottom this far under the lowest top of the low layer under its footprint
ST_SOCKET = (0.44, 0.34, 0.24, 0.025, 0.02)       # socket stones: length, depth, height, chamfer, sunk into the slab
# the four places, left to right at the hold: key, x on the slab, mortise length (x), width (y), depth
ST_SLOTS = (("sharp", -1.4, 0.17, 0.06, 0.2), ("soft", -0.47, 0.28, 0.04, 0.2),
            ("heavy", 0.47, 0.3, 0.13, 0.2), ("wood", 1.4, 0.26, 0.09, 0.2))
ST_CAIRN = (0.0, 0.95, 1.35, 1.65)                # centre x, y, base radius, height: lower than the swords' hilts
ST_CAIRN_SINK = 0.12               # the cairn's base under the ledge's top at its centre
# stone rings up the cairn: (height fraction, stone half-width, half-height): flat field stones; a flat cap stone on top
ST_CAIRN_RINGS = ((0.06, 0.34, 0.16), (0.26, 0.31, 0.15), (0.46, 0.28, 0.13), (0.65, 0.24, 0.12), (0.82, 0.2, 0.1))
ST_CAP_STONE = (0.44, 0.37, 0.12)
ST_CAIRN_FILL = 14                 # extra stones pushed in across the courses at random
# the stones taken off the swords, set down round the heap: (x, y, ST_ROCK layer they lie on, half-width); each inside
# its layer's level top (and the low ones off the ledge), clear of the slab and the heap
ST_LOOSE = ((-2.45, -0.5, 0, 0.27), (2.75, -0.8, 0, 0.24), (-1.85, 1.55, 1, 0.25), (1.95, 1.2, 1, 0.22))
ST_SEED_CAIRN = 3520               # the cairn's stones (sizes, turns, shapes)
ST_LEAN = dict(sharp=(0.0, -3.0, 0.0), wood=(2.0, 9.0, 8.0))   # planted swords: rotation (x, y, z) in degrees about the
                                                             # blade's foot on the mortise floor (both lean out; the
                                                             # rotted wood loose in its socket)
ST_SWORD_MATS = dict(sharp=["forge_qing_steel", "bronze", "cloth_black", "cloth_red"],
                     wood=["forge_old_wood", "cloth_black"])
ST_MATS = dict(rock="forge_tomb_rock", cairn=("forge_cairn_rock", "stone_dark"), slab="forge_bluestone")
# materials: the outcrop is the cliffs' sandstone with a fifth of the moss (a full share carpets a flat top) and closer
# beds; the cairn the boulders' finer sandstone, a shade darker than the outcrop, with a trace of moss and no banding
# across a stone (its earth core dark stone, so the gaps between stones read as shadow); the slab's bluestone 青石; the
# keen sword's blue-white steel 青光 (the bake keeps base colours: a mid blue-grey blade with near-white honed edges
# against the white paving); the rotted wood weathered pale grey-beige, so it stands out against the darker cairn behind
# it. (forge_tomb_rock / forge_cairn_rock are rock_cliff variants: the web's rock detail texture needs them in
# bake_web.DETAIL_CLASSES; without it they show only their baked texture)
M.variant("forge_tomb_rock", "rock_cliff", moss_amt=0.2, strata=0.5, joints=0.4, stain=0.4)
M.variant("forge_cairn_rock", "nature_rock_small", moss_amt=0.12, strata=1.5, light="#857f78", mid="#625e59",
          dark="#3f3c39")
M.register("forge_bluestone", M._stone, c1="#8a939a", c2="#4a5258", speck="#1f2326", rough=(0.55, 0.85), bump=0.9,
           scale=1.4, light="#aab1b6", light_amt=0.6, moss=0.35)
M.register("forge_qing_steel", M._metal, base="#9fb0bf", dark="#6a7886", rough=(0.12, 0.24), tarnish=0.18,
           edge_col="#eef5fb")
M.register("forge_old_wood", M._wood, c1="#9a8e7a", c2="#bdb09a", grain="#6a604f", rough=(0.72, 0.92))


def _st_hash(i, j, k, seed):
    h = ((i * 73856093) ^ (j * 19349663) ^ (k * 83492791) ^ (seed * 2654435761)) & 0xFFFFFFFF
    h = ((h ^ (h >> 15)) * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 3266489917) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFF) / float(0xFFFFFF) * 2.0 - 1.0


def _st_noise(x, y, z=0.0, seed=0):
    """Smooth value noise in [-1, 1]: a hashed integer lattice, trilinear with a quintic fade (the same on every
    machine, no mathutils)."""
    xi, yi, zi = math.floor(x), math.floor(y), math.floor(z)
    u, v, w = ((f * f * f * (f * (f * 6.0 - 15.0) + 10.0)) for f in (x - xi, y - yi, z - zi))

    def h(a, b, c):
        return _st_hash(xi + a, yi + b, zi + c, seed)

    def lerp(a, b, t):
        return a + (b - a) * t

    return lerp(lerp(lerp(h(0, 0, 0), h(1, 0, 0), u), lerp(h(0, 1, 0), h(1, 1, 0), u), v),
                lerp(lerp(h(0, 0, 1), h(1, 0, 1), u), lerp(h(0, 1, 1), h(1, 1, 1), u), v), w)


def _st_fbm(x, y, z=0.0, seed=0, octaves=3):
    s, a, n = 0.0, 1.0, 0.0
    for o in range(octaves):
        f = 2.03 ** o
        s += a * _st_noise(x * f, y * f, z * f, seed + 31 * o)
        n += a
        a *= 0.5
    return s / n


def _st_outline(t, a, b, seed):
    """(x, y) of an outcrop layer's outline at parameter angle t: a squarish superellipse a x b whose radius wanders
    with fbm and is nicked by a few narrow vertical cracks."""
    c, s = math.cos(t), math.sin(t)
    e = 2.0 / ST_ROCK_P
    k = (1.0 + 0.08 * _st_fbm(c * 1.4, s * 1.4, 0.0, seed, 3) + 0.03 * _st_noise(c * 4.5, s * 4.5, 2.3, seed + 9)
         - 0.07 * (1.0 - abs(_st_noise(c * 5.0, s * 5.0, 1.7, seed + 5))) ** 10)
    return a * math.copysign(abs(c) ** e, c) * k, b * math.copysign(abs(s) ** e, s) * k


def _st_rock_top(x, y, layer):
    """Height of a layer's top at (x, y), tomb frame: its top z, a low dome and fbm (a weathered top, never quite
    level)."""
    cx, cy, a, b, z0, z1, seed = layer
    q = min(1.0, ((x - cx) / a) ** 2 + ((y - cy) / b) ** 2)
    return z1 + 0.06 * (1.0 - q) + 0.05 * _st_fbm(x * 0.8, y * 0.8, 3.1, seed + 11, 3)


def _st_rock(g=None):
    """The outcrop (material 0 forge_tomb_rock): each ST_ROCK layer a closed ring-built slab, sides bulging a little
    and wandering with noise, a rounded lip, a weathered top at _st_rock_top, smooth shaded."""
    g = g or _fw_geo()
    segs = ST_ROCK_SEGS
    for layer in ST_ROCK:
        cx, cy, a, b, z0, z1, seed = layer
        ol = [_st_outline(2 * math.pi * i / segs, a, b, seed) for i in range(segs)]
        verts, rings = [], []
        for f, k in ST_ROCK_SIDE:
            ring = []
            for ox, oy in ol:
                kk = k * (1.0 + (0.03 * _st_noise(ox * 1.1, oy * 1.1, f * 3.0, seed + 3) if f > 0 else 0.0))
                x, y = cx + ox * kk, cy + oy * kk
                z = z0 + f * (z1 - z0) + (0.02 * _st_noise(x * 1.3, y * 1.3, 5.0 + f, seed + 4) if f > 0 else 0.0)
                ring.append(len(verts))
                verts.append((x, y, z))
            rings.append(ring)
        for ci, k in enumerate(ST_ROCK_CAP):
            ring = []
            for ox, oy in ol:
                x, y = cx + ox * k, cy + oy * k
                ring.append(len(verts))
                verts.append((x, y, _st_rock_top(x, y, layer) - (ST_ROCK_LIP if ci == 0 else 0.0)))
            rings.append(ring)
        pole = len(verts)
        verts.append((cx, cy, _st_rock_top(cx, cy, layer)))
        faces = [tuple(reversed(rings[0]))]
        for r0, r1 in zip(rings[:-1], rings[1:]):
            faces += [(r0[i], r0[(i + 1) % segs], r1[(i + 1) % segs], r1[i]) for i in range(segs)]
        last = rings[-1]
        faces += [(last[i], last[(i + 1) % segs], pole) for i in range(segs)]
        _fw_add(g, verts, faces, 0, 0.0, soft=True)
    return g


def _st_ico():
    """Unit icosphere with one subdivision: 42 vertices, 80 triangles."""
    t = (1.0 + 5 ** 0.5) / 2.0
    vs = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
          (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    fs = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
          (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
          (8, 6, 7), (9, 8, 1)]
    vs = [tuple(c / math.sqrt(sum(q * q for q in v)) for c in v) for v in vs]
    mid = {}

    def m(a, b):
        key = (min(a, b), max(a, b))
        if key not in mid:
            p = [(vs[a][k] + vs[b][k]) * 0.5 for k in range(3)]
            n = math.sqrt(sum(q * q for q in p))
            mid[key] = len(vs)
            vs.append(tuple(q / n for q in p))
        return mid[key]

    out = []
    for a, b, c in fs:
        ab, bc, ca = m(a, b), m(b, c), m(c, a)
        out += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
    return vs, out


def _st_basis(up, yaw):
    """Columns (x, y, z) of a frame whose z is ``up`` (normalised), turned ``yaw`` about it."""
    n = math.sqrt(sum(c * c for c in up))
    z = [c / n for c in up]
    x0 = [-z[1], z[0], 0.0]                                    # (0, 0, 1) x z: horizontal
    ln = math.sqrt(x0[0] ** 2 + x0[1] ** 2)
    x0 = [1.0, 0.0, 0.0] if ln < 1e-6 else [c / ln for c in x0]
    y0 = [z[1] * x0[2] - z[2] * x0[1], z[2] * x0[0] - z[0] * x0[2], z[0] * x0[1] - z[1] * x0[0]]
    c, s = math.cos(yaw), math.sin(yaw)
    x = [c * x0[k] + s * y0[k] for k in range(3)]
    y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]]
    return x, y, z


def _st_stone(g, centre, half, up, yaw, seed, mat=0):
    """One cairn stone, a split field stone: a lumpy icosphere (half-extents ``half``, the short one along ``up``) with
    a flat bed and a flat top (the faces it is stacked on) and three to five more facets knocked off its sides, turned
    ``yaw`` about ``up``. Closed, smooth shaded."""
    r = random.Random(seed)
    vs, fs = _st_ico()
    off = (r.uniform(-40, 40), r.uniform(-40, 40), r.uniform(-40, 40))
    planes = [((r.uniform(-0.12, 0.12), r.uniform(-0.12, 0.12), 1.0), r.uniform(0.62, 0.78)),
              ((r.uniform(-0.12, 0.12), r.uniform(-0.12, 0.12), -1.0), r.uniform(0.66, 0.8))]
    for _ in range(r.randint(3, 5)):
        a, el = r.uniform(0.0, 2 * math.pi), r.uniform(-0.35, 0.45)
        planes.append(((math.cos(a) * math.cos(el), math.sin(a) * math.cos(el), math.sin(el)), r.uniform(0.66, 0.84)))
    planes = [(tuple(c / math.sqrt(sum(q * q for q in n)) for c in n), cut) for n, cut in planes]
    bx, by, bz = _st_basis(up, yaw)
    out, onp = [], []
    for v in vs:
        k = (1.0 + 0.16 * _st_noise(v[0] * 1.6 + off[0], v[1] * 1.6 + off[1], v[2] * 1.6 + off[2], seed)
             + 0.06 * _st_noise(v[0] * 4.2 + off[0], v[1] * 4.2 + off[1], v[2] * 4.2 + off[2], seed + 1))
        p = [c * k for c in v]
        on = -1
        for pi, (n, cut) in enumerate(planes):
            h = sum(p[i] * n[i] for i in range(3))
            if h > cut:
                p = [p[i] - n[i] * (h - cut) for i in range(3)]
                on = pi
        onp.append(on)
        p = (p[0] * half[0], p[1] * half[1], p[2] * half[2])
        out.append(tuple(centre[i] + p[0] * bx[i] + p[1] * by[i] + p[2] * bz[i] for i in range(3)))
    f0 = len(g["f"])
    _fw_add(g, out, fs, mat, 0.0, soft=True)
    for k, f in enumerate(fs):        # a face wholly on one knocked-off facet shades flat: crisp split edges round it
        if onp[f[0]] >= 0 and onp[f[0]] == onp[f[1]] == onp[f[2]]:
            g["soft"][f0 + k] = False


def _st_dome_r(u):
    """The cairn's radius at height fraction u (0 foot, 1 top), in units of its base radius."""
    u = min(1.0, max(0.0, u))
    return (1.0 - u * u) ** 0.55 * (1.0 - 0.06 * u)


def _st_cairn(base_z, g=None):
    """The heap of stones (materials 0 forge_cairn_rock, 1 stone_dark): an earth dome (ST_CAIRN) laid round with
    courses of flat field stones, as a dry-stone heap is built: each stone lies nearly flat, its long side along the
    course, dipping outward a little more the higher it sits, its centre on the dome's surface (the inner half bedded in
    the earth), each course offset half a stone from the one below and every stone jostled; ST_CAIRN_FILL more stones
    pushed in across the courses so no course runs clean; a flat cap stone on top. The bottom course sinks under
    ``base_z``, the ledge's top. Then ST_LOOSE: the stones taken off the swords, set down on the outcrop round the
    heap, each bedded in the rock top. Returns the geometry."""
    g = g or _fw_geo()
    cx, cy, R0, H = ST_CAIRN
    prof = [(R0 * 0.93 * _st_dome_r(u), u * H) for u in (0.0, 0.15, 0.32, 0.5, 0.66, 0.8, 0.91)] + [(0.0, 0.97 * H)]
    _fw_lathe_z(g, (cx, cy, base_z), prof, 16, mat=1)
    r = random.Random(ST_SEED_CAIRN)

    def lay_stone(u, th, w, hz, inset=1.0):
        c, s = math.cos(th), math.sin(th)
        dip = 0.15 + 0.3 * u + r.uniform(-0.14, 0.14)                    # outward dip of the stone's top (rad)
        up = (c * math.sin(dip), s * math.sin(dip), math.cos(dip))
        rr = R0 * _st_dome_r(u) * inset
        centre = (cx + rr * c, cy + rr * s, base_z + u * H + r.uniform(-0.05, 0.05))
        _st_stone(g, centre, (w, w * r.uniform(0.62, 0.92), hz), up, r.uniform(-0.45, 0.45), r.randint(0, 10 ** 6))

    for j, (u, w, hz) in enumerate(ST_CAIRN_RINGS):
        n_st = max(3, int(round(2 * math.pi * R0 * _st_dome_r(u) / (1.7 * w))))
        for i in range(n_st):
            k = r.uniform(0.72, 1.3)
            lay_stone(u, 2 * math.pi * (i + 0.5 * (j % 2) + r.uniform(-0.3, 0.3)) / n_st, w * k,
                      hz * r.uniform(0.8, 1.2) * (0.6 + 0.4 * k))
    for _ in range(ST_CAIRN_FILL):
        u = r.uniform(0.12, 0.78)
        w = ST_CAIRN_RINGS[0][1] * (1.0 - 0.45 * u) * r.uniform(0.75, 1.1)
        lay_stone(u, r.uniform(0.0, 2 * math.pi), w, w * r.uniform(0.42, 0.55), inset=0.98)
    a, b, c3 = ST_CAP_STONE
    _st_stone(g, (cx, cy, base_z + H - 0.06), (a, b, c3), (0.06, -0.04, 1.0), r.uniform(0, 2 * math.pi),
              r.randint(0, 10 ** 6))
    for x, y, li, w in ST_LOOSE:
        layer = ST_ROCK[li]
        hz = w * r.uniform(0.45, 0.55)
        z = min(_st_rock_top(x + dx * w * 0.7, y + dy * w * 0.7, layer)
                for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)))
        up = (r.uniform(-0.08, 0.08), r.uniform(-0.08, 0.08), 1.0)
        _st_stone(g, (x, y, z + 0.4 * hz), (w, w * r.uniform(0.65, 0.85), hz), up, r.uniform(0, 2 * math.pi),
                  r.randint(0, 10 ** 6))
    return g


def _st_block(g, cx, cy, z0, L, D, H, ch, slots=(), mat=0):
    """A cut-stone block (centre cx, cy, bottom z0, L x D x H) with its top edges chamfered by ``ch`` (flagged as worn
    edges) and rectangular mortises in its top: slots [(x offset, length (x), width (y), depth)]. One closed part,
    every vertex used (the mesh validation would drop loose ones)."""
    def snap(v):
        return round(v, 6)

    xb = sorted({snap(cx - L / 2 + ch), snap(cx + L / 2 - ch)}
                | {snap(cx + sx + q * sl / 2) for sx, sl, sw, sd in slots for q in (-1, 1)})
    yb = sorted({snap(cy - D / 2 + ch), snap(cy + D / 2 - ch)} | {snap(cy + q * sw / 2) for sx, sl, sw, sd in slots
                                                                  for q in (-1, 1)})
    nx, ny = len(xb) - 1, len(yb) - 1
    verts, idx = [], {}

    def V(key, co):
        if key not in idx:
            idx[key] = len(verts)
            verts.append(co)
        return idx[key]

    top = z0 + H

    def T(i, j):
        return V(("t", i, j), (xb[i], yb[j], top))

    rects = []
    for sx, sl, sw, sd in slots:
        i0, i1 = xb.index(snap(cx + sx - sl / 2)), xb.index(snap(cx + sx + sl / 2))
        j0, j1 = yb.index(snap(cy - sw / 2)), yb.index(snap(cy + sw / 2))
        if not (0 < i0 < i1 < nx and 0 < j0 < j1 < ny):
            raise ValueError("a mortise touches the block's rim: %s" % ((sx, sl, sw, sd),))
        rects.append((i0, i1, j0, j1, top - sd))
    faces, edge = [], []

    def add(f, e=0.0):
        faces.append(f)
        edge.append(e)

    for i in range(nx):
        for j in range(ny):
            if any(i0 <= i < i1 and j0 <= j < j1 for i0, i1, j0, j1, _ in rects):
                continue
            add((T(i, j), T(i + 1, j), T(i + 1, j + 1), T(i, j + 1)))
    for k, (i0, i1, j0, j1, zf) in enumerate(rects):
        def F(i, j, k=k, zf=zf):
            return V(("f", k, i, j), (xb[i], yb[j], zf))
        for i in range(i0, i1):
            for j in range(j0, j1):
                add((F(i, j), F(i + 1, j), F(i + 1, j + 1), F(i, j + 1)))
        for j in range(j0, j1):
            add((T(i0, j + 1), T(i0, j), F(i0, j), F(i0, j + 1)))       # wall at the mortise's -x side
            add((T(i1, j), T(i1, j + 1), F(i1, j + 1), F(i1, j)))       # +x
        for i in range(i0, i1):
            add((T(i, j0), T(i + 1, j0), F(i + 1, j0), F(i, j0)))       # -y
            add((T(i + 1, j1), T(i, j1), F(i, j1), F(i + 1, j1)))       # +y
    # the top's rim, counter-clockwise from above (the way the top faces run along it), then chamfer, sides, bottom
    loop = ([(i, 0) for i in range(nx + 1)] + [(nx, j) for j in range(1, ny + 1)]
            + [(i, ny) for i in range(nx - 1, -1, -1)] + [(0, j) for j in range(ny - 1, 0, -1)])

    def out(i, j):
        x, y = xb[i], yb[j]
        x += -ch if i == 0 else (ch if i == nx else 0.0)
        y += -ch if j == 0 else (ch if j == ny else 0.0)
        return x, y

    C = [V(("c",) + p, out(*p) + (top - ch,)) for p in loop]
    B = [V(("b",) + p, out(*p) + (z0,)) for p in loop]
    tl = [T(*p) for p in loop]
    m = len(loop)
    for k in range(m):
        k2 = (k + 1) % m
        add((tl[k2], tl[k], C[k], C[k2]), 1.0)
        add((C[k2], C[k], B[k], B[k2]))
    add(tuple(reversed(B)))
    _fw_add(g, verts, faces, mat, edge)
    return g


def _st_slab(g=None):
    """The bluestone (material 0 forge_bluestone) in its own frame (centre on x, y 0, bottom z 0): the long chamfered
    slab and the four socket stones on it, each with its mortise (ST_SLOTS)."""
    g = g or _fw_geo()
    _, _, L, D, H, ch = ST_SLAB
    _st_block(g, 0.0, 0.0, 0.0, L, D, H, ch)
    sl, sd, sh, sch, sink = ST_SOCKET
    for key, x, ml, mw, md in ST_SLOTS:
        _st_block(g, x, 0.0, H - sink, sl, sd, sh, sch, [(0.0, ml, mw, md)])
    return g


def _st_lathe(g, prof, sides=8, mat=0, edge=0.0, soft=False, phase=0.0, centre=(0.0, 0.0)):
    """Closed solid of elliptical rings along z: prof [(rx, ry, z)] bottom to top; rx 0 makes a pole, else the end
    ring is capped flat."""
    verts, rings = [], []
    for rx, ry, z in prof:
        if rx <= 1e-9:
            rings.append([len(verts)])
            verts.append((centre[0], centre[1], z))
            continue
        ring = []
        for k in range(sides):
            a = 2 * math.pi * (k + phase) / sides
            ring.append(len(verts))
            verts.append((centre[0] + rx * math.cos(a), centre[1] + ry * math.sin(a), z))
        rings.append(ring)
    faces = []
    if len(rings[0]) > 1:
        faces.append(tuple(reversed(rings[0])))
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(sides):
            k2 = (k + 1) % sides
            if len(a) == 1:
                faces.append((a[0], b[k2], b[k]))
            elif len(b) == 1:
                faces.append((a[k], a[k2], b[0]))
            else:
                faces.append((a[k], a[k2], b[k2], b[k]))
    if len(rings[-1]) > 1:
        faces.append(tuple(rings[-1]))
    _fw_add(g, verts, faces, mat, edge, soft=soft)


def _st_blade(g, stations, section, mat=0, edge_segs=(), tip=None, jag=None, notch=None):
    """A blade along +z: ``section`` [(x, y)] around (counter-clockwise from above, units of half-width W and
    half-thickness T), stations [(z, W, T)] bottom to top, capped flat at the top. ``tip`` (z) closes the bottom to a
    point; ``jag`` (seed) instead breaks it off ragged (the bottom ring's heights vary, fanned to a point at z 0).
    ``notch`` (z0, z1, k): +x half narrowed by k between z0 and z1. Faces of ``edge_segs`` (section segments) are
    flagged as worn edges."""
    n = len(section)
    verts, rings = [], []
    for si, (z, W, T) in enumerate(stations):
        ring = []
        for k, (sx, sy) in enumerate(section):
            kx = 1.0
            if notch and sx > 0 and notch[0] <= z <= notch[1]:
                kx = 1.0 - notch[2]
            zz = z
            if jag is not None and si == 0:
                zz = z + 0.035 * (0.5 + 0.5 * _st_noise(k * 0.9, 0.3, 0.0, jag))
            ring.append(len(verts))
            verts.append((sx * W * kx, sy * T, zz))
        rings.append(ring)
    faces, edge = [], []
    if tip is not None or jag is not None:
        pole = len(verts)
        verts.append((0.0, 0.0, 0.0 if jag is not None else tip))
        r0 = rings[0]
        for k in range(n):
            faces.append((pole, r0[(k + 1) % n], r0[k]))
            edge.append(1.0 if tip is not None else 0.0)
    else:
        faces.append(tuple(reversed(rings[0])))
        edge.append(0.0)
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(n):
            faces.append((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
            edge.append(1.0 if k in edge_segs else 0.0)
    faces.append(tuple(rings[-1]))
    edge.append(0.0)
    _fw_add(g, verts, faces, mat, edge)


def _st_tube(g, p0, p1, r, sides=6, mat=0):
    """Round rod from p0 to p1, capped."""
    ax = [p1[k] - p0[k] for k in range(3)]
    L = math.sqrt(sum(a * a for a in ax))
    bx, by, bz = _st_basis(ax, 0.0)
    verts = []
    for p in (p0, p1):
        for k in range(sides):
            a = 2 * math.pi * k / sides
            verts.append(tuple(p[i] + r * (math.cos(a) * bx[i] + math.sin(a) * by[i]) for i in range(3)))
    faces = [tuple(reversed(range(sides))), tuple(range(sides, 2 * sides))]
    faces += [(k, (k + 1) % sides, sides + (k + 1) % sides, sides + k) for k in range(sides)]
    _fw_add(g, verts, faces, mat, 0.0)
    return L


def _st_sharp_sword():
    """The keen sword 青光利剑, point at the origin, hilt up +z (materials 0 forge_qing_steel, 1 bronze, 2 cloth_black,
    3 cloth_red): a 1.9 m blade of flattened-diamond section with honed edge bevels (flagged as worn: bright), a short
    point; a straight bronze guard, a silk-wrapped grip between bronze ferrules, a flattened onion pommel, and a red
    tassel on a cord from the pommel lying along the grip onto the guard."""
    g = _fw_geo()
    sec = ((1.0, 0.0), (0.86, 0.3), (0.0, 1.0), (-0.86, 0.3), (-1.0, 0.0), (-0.86, -0.3), (0.0, -1.0), (0.86, -0.3))
    st = ((0.02, 0.012, 0.003), (0.05, 0.024, 0.005), (0.09, 0.034, 0.0068), (0.13, 0.041, 0.0078),
          (0.17, 0.046, 0.0085), (0.85, 0.051, 0.010), (1.5, 0.055, 0.0112), (1.93, 0.058, 0.012))
    _st_blade(g, st, sec, 0, edge_segs=(0, 3, 4, 7), tip=0.0)
    gz = 1.9                                                   # guard bottom
    _fw_box(g, (0.0, 0.0, gz + 0.033), (0.30, 0.072, 0.066), 0.012, mat=1)
    _st_lathe(g, ((0.037, 0.031, gz + 0.058), (0.039, 0.033, gz + 0.08), (0.037, 0.031, gz + 0.105)), 8, 1)
    _st_lathe(g, ((0.031, 0.025, gz + 0.09), (0.034, 0.0275, gz + 0.3), (0.031, 0.025, gz + 0.52)), 8, 2)
    _st_lathe(g, ((0.036, 0.03, gz + 0.505), (0.038, 0.032, gz + 0.525), (0.036, 0.03, gz + 0.55)), 8, 1)
    _st_lathe(g, ((0.03, 0.022, gz + 0.545), (0.056, 0.034, gz + 0.57), (0.06, 0.036, gz + 0.595),
                  (0.05, 0.03, gz + 0.622), (0.022, 0.016, gz + 0.64)), 8, 1, soft=True)
    # tassel: cord from inside the pommel's +x rim to a knot, then the tassel resting on the guard beside the grip
    _st_tube(g, (0.04, 0.0, gz + 0.59), (0.072, -0.004, gz + 0.36), 0.007, 6, mat=3)
    _st_lathe(g, ((0.0, 0.0, gz + 0.335), (0.02, 0.02, gz + 0.345), (0.022, 0.022, gz + 0.358),
                  (0.016, 0.016, gz + 0.372), (0.0, 0.0, gz + 0.378)), 8, 3, soft=True, centre=(0.072, -0.004))
    _st_lathe(g, ((0.034, 0.03, gz + 0.064), (0.032, 0.028, gz + 0.12), (0.024, 0.021, gz + 0.24),
                  (0.012, 0.011, gz + 0.34)), 8, 3, soft=True, centre=(0.074, -0.004))
    return g


def _st_wood_sword():
    """The wooden sword 木剑, rotted with age, broken end at the origin, hilt up +z (materials 0 forge_old_wood,
    1 cloth_black): a 1.8 m blade of ridged lens section whose width wanders, with a bite out of its +x edge and a
    ragged broken end; a short jian guard tapering to its ends (barely wider than the blade, so the planted sword never
    reads as a cross), a grip wrapped in dark cord, a wooden ferrule and a knob pommel."""
    g = _fw_geo()
    sec = ((1.0, 0.0), (0.7, 0.7), (0.0, 1.0), (-0.7, 0.7), (-1.0, 0.0), (-0.7, -0.7), (0.0, -1.0), (0.7, -0.7))
    st = []
    for z in (0.04, 0.3, 0.62, 0.95, 1.22, 1.3, 1.36, 1.44, 1.52, 1.83):
        W = (0.056 + 0.006 * z / 1.8) * (1.0 + 0.06 * _st_noise(z * 2.3, 0.4, 0.0, 77))
        st.append((z, W, 0.021 * (1.0 + 0.05 * _st_noise(z * 2.9, 1.3, 0.0, 78))))
    _st_blade(g, st, sec, 0, jag=79, notch=(1.33, 1.45, 0.38))
    gz = 1.8
    _fw_prism_xz(g, ((-0.095, gz + 0.024), (-0.06, gz), (0.06, gz), (0.095, gz + 0.024), (0.06, gz + 0.052),
                     (-0.06, gz + 0.052)), -0.033, 0.033, mat=0, edge=1.0)
    _st_lathe(g, ((0.029, 0.026, gz + 0.045), (0.033, 0.03, gz + 0.24), (0.029, 0.026, gz + 0.42)), 8, 1)
    _st_lathe(g, ((0.031, 0.028, gz + 0.405), (0.034, 0.031, gz + 0.43), (0.031, 0.028, gz + 0.45)), 8, 0)
    _st_lathe(g, ((0.02, 0.02, gz + 0.445), (0.04, 0.038, gz + 0.47), (0.042, 0.04, gz + 0.495),
                  (0.03, 0.028, gz + 0.52), (0.0, 0.0, gz + 0.53)), 8, 0, soft=True)
    return g


def _st_layout():
    """Heights in the tomb frame: the slab's bottom (ST_SLAB_SINK under the lowest top of the low layer under its
    footprint), the socket stones' top, each mortise's floor (x, y, z) and the cairn's base."""
    sx, sy, L, D, H, ch = ST_SLAB
    low, high = ST_ROCK
    zs = [_st_rock_top(sx + L * (u / 8.0 - 0.5), sy + D * (v / 3.0 - 0.5), low) for u in range(9) for v in range(4)]
    slab_z = min(zs) - ST_SLAB_SINK
    sl, sd, sh, sch, sink = ST_SOCKET
    sock_top = slab_z + H - sink + sh
    floors = {key: (sx + x, sy, sock_top - md) for key, x, ml, mw, md in ST_SLOTS}
    cx, cy, R0, Hc = ST_CAIRN
    return dict(slab_z=slab_z, socket_top=sock_top, floors=floors,
                cairn_z=_st_rock_top(cx, cy, high) - ST_CAIRN_SINK)


def _sword_tomb(coll, root, x, y):
    """Dugu Qiubai's Sword Tomb at local (x, y): an Empty ST_NAME (turned ST_ROT_Z) holding ST_NAME.rock, .cairn,
    .slab, .sharp_sword and .wood_sword. Returns the Empty."""
    emp = U.empty(U.unique_name(ST_NAME), coll, location=(x, y, 0.0), parent=root, rotation=(0.0, 0.0, ST_ROT_Z),
                  display_size=2.0)
    lay = _st_layout()
    _fw_object(ST_NAME + ".rock", coll, emp, _st_rock(), [ST_MATS["rock"]])
    _fw_object(ST_NAME + ".cairn", coll, emp, _st_cairn(lay["cairn_z"]), list(ST_MATS["cairn"]))
    _fw_object(ST_NAME + ".slab", coll, emp, _st_slab(), [ST_MATS["slab"]],
               location=(ST_SLAB[0], ST_SLAB[1], lay["slab_z"]))
    for key, build, nm in (("sharp", _st_sharp_sword, "sharp_sword"), ("wood", _st_wood_sword, "wood_sword")):
        rx, ry, rz = (math.radians(a) for a in ST_LEAN[key])
        _fw_object(ST_NAME + "." + nm, coll, emp, build(), ST_SWORD_MATS[key], location=lay["floors"][key],
                   rotation=(rx, ry, rz))
    return emp


def _keyframe_spin(ob, f0, f1, turns=1.0):
    """Linear Z rotation 0 -> turns*2pi over [f0, f1], extrapolated linearly beyond."""
    ob.rotation_euler = (0.0, 0.0, 0.0)
    ob.keyframe_insert("rotation_euler", index=2, frame=f0)
    ob.rotation_euler = (0.0, 0.0, 2 * math.pi * turns)
    ob.keyframe_insert("rotation_euler", index=2, frame=f1)
    ob.rotation_euler = (0.0, 0.0, 0.0)
    ad = ob.animation_data
    act = ad.action
    act.name = ob.name + ".spin"
    fcurves = []
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot)
        if cb is not None:
            fcurves = list(cb.fcurves)
    except Exception:
        fcurves = []
    if not fcurves:
        fcurves = list(getattr(act, "fcurves", []) or [])
    for fc in fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
        fc.extrapolation = 'LINEAR'
        fc.update()
    return len(fcurves)


# ------------------------------------------------------------------ build

def build(collection):
    """Build the whole area at the local origin. Return the root Empty 'forge.root'."""
    coll = collection
    root = U.empty("forge.root", coll, display_size=4.0)

    # courtyard, arrival landing, bridgehead
    _paving(root, coll)
    _terrace_balustrade(root, coll)
    _arrival(root, coll)
    _bridgehead(root, coll)

    # main two-tier forge hall, open front
    # (back_stairs: the flues to the chimneys cross the rear apron and cut off its middle from the
    # side walkways; walkcheck found it unreachable, 105 m2)
    hall = A.hall(_n("hall"), coll, bays_w=5, bays_d=3, bay=6.5, column_h=7.0, double_eave=True,
                  platform_h=1.5, lit=True, roof_mat="roof_tile_black", parent=root, back_stairs=True,
                  location=(0.0, HALL_Y, 0.0))
    _open_front(hall)
    _furnaces(root, coll, 1.5)
    _flues(root, coll, 1.5)
    _hang_plaque(hall, "炼器殿", _n("hall_plaque"), min_w=3.6)

    # side workshops facing the courtyard
    for i, (x, rz) in enumerate(((-33.0, math.pi / 2), (33.0, -math.pi / 2))):
        A.hall(_n("workshop", i), coll, bays_w=3, bays_d=2, bay=4.6, column_h=5.0, roof="xuanshan",
               platform_h=0.9, lit=True, roof_mat="roof_tile_black", parent=root,
               location=(x, 4.0, 0.0), rotation_z=rz)

    # chimneys behind the hall
    for i, x in enumerate((-10.0, 10.0)):
        _chimney(root, coll, i, x, CHIMNEY_Y)

    # cauldron dais + colossal ding
    A.platform(_n("dais"), coll, 17.0, height=DAIS_H, sides=8, parent=root,
               location=(DAIS_C[0], DAIS_C[1], 0.0))
    A.stairs(_n("dais_stairs"), coll, 4.0, DAIS_H, ramp=False, balustrade=False, parent=root,
             location=(DAIS_C[0], DAIS_C[1] - 17.0 * 0.5 * math.cos(math.pi / 8), 0.0))
    # back stair, so the axis continues past the ding to the hall stair (audit section 4)
    A.stairs(_n("dais_stairs_back"), coll, 4.0, DAIS_H, ramp=False, balustrade=False, parent=root,
             location=(0.0, DAIS_C[1] + 17.0 * 0.5 * math.cos(math.pi / 8), 0.0), rotation_z=math.pi)
    P.cauldron_ding(coll, DING_SIZE, lit=True, light=True, sparks=True, name=_n("ding"), parent=root,
                    location=(DAIS_C[0], DAIS_C[1], DAIS_H))

    # jade rune ring on the paving under the orbit
    P.rune_ring(coll, RING_R, 1.2, "trigram", name=_n("rune_ring"), parent=root,
                location=(DAIS_C[0], DAIS_C[1], 0.0))

    # the winning projects' artifacts on a tilted, slowly turning ring
    tilt = U.empty(_n("ring_tilt"), coll, location=(DAIS_C[0], DAIS_C[1], RING_Z), parent=root,
                   rotation=(RING_TILT, 0.0, 0.0), display_size=2.0)
    spin = U.empty(_n("artifact_ring"), coll, parent=tilt, display_size=RING_R,
                   display_type='CIRCLE', rotation=(0.0, 0.0, 0.0))
    spin.empty_display_type = 'CIRCLE'
    place_artifacts(coll, spin)
    _keyframe_spin(spin, *SPIN_FRAMES)
    # thin glowing qi hoop along the orbit, so the ring reads as one ring in the blocking
    hoop_pts = [(RING_R * math.cos(2 * math.pi * k / 60), RING_R * math.sin(2 * math.pi * k / 60), 0.0)
                for k in range(60)]
    hoop = U.tube_mesh(_n("orbit_hoop"), hoop_pts, HOOP_R, coll, material="rune_cyan", sides=6,
                       samples_per_segment=1, closed=True, caps=False, parent=tilt)
    U.set_visibility(hoop, shadow=False)

    # forge yard props
    for i, (x, y, rz) in enumerate(((-13.0, -18.0, 0.4), (13.5, -17.0, -0.3), (-16.0, -24.0, 1.2))):
        P.anvil(coll, 1.5, name=_n("anvil"), parent=root, location=(x, y, 0.0), rotation=(0, 0, rz))
    for i, (x, y) in enumerate(((-18.0, -15.0), (18.0, -9.0))):   # trough 0 off the walk to the bridge
        _quench_trough(root, coll, i, x, y)
    for i, (x, y) in enumerate(((-21.0, -21.0), FW_LOC, (21.0, 10.0), (24.0, 15.5))):
        if i == 1:      # the one rack readable at the hold: the Golden Wheel Lama's five wheels instead
            _five_wheels(coll, root, x, y)
            continue
        # explicit numbers keep the other racks' names (forge.weapon_rack, .002, .003) and so their cache keys
        nm = _n("weapon_rack") if i == 0 else U.unique_name("forge.weapon_rack.%03d" % i)
        P.weapon_rack(coll, 2.6, seed=i, name=nm, parent=root, location=(x, y, 0.0),
                      rotation=(0, 0, 0.25 if x < 0 else -0.25))
    for i, (x, y, s) in enumerate(((-27.0, -24.0, 2.6), (-22.0, -30.0, 1.8), (26.0, -4.0, 2.4),
                                   (-25.0, 14.0, 2.0), (20.0, 26.0, 2.2))):
        P.ore_pile(coll, s, seed=i, name=_n("ore"), parent=root, location=(x, y, 0.0))
    # Dugu Qiubai's Sword Tomb 剑冢 on the open paving right of the dais, in front of the hall's east bays
    _sword_tomb(coll, root, *ST_LOC)

    # approach axis: stone lanterns and banners
    for y in (-30.0, -40.0):
        for x in (-6.5, 6.5):
            P.lantern_stone(coll, 2.6, name=_n("lantern"), parent=root, location=(x, y, 0.0))
    for i, x in enumerate((-13.0, 13.0)):
        P.banner(coll, 10.0, 1.5, material=0 if x < 0 else 7, seed=i, name=_n("banner"), parent=root,
                 location=(x, -37.0, 0.0), rotation=(0, 0, 0.0 if x < 0 else math.pi))

    # entrance gate over the front opening, carrying the area plaque 炼器峰
    gate = A.paifang(_n("gate"), coll, bays=3, width=17.0, height=12.0, roof_mat="roof_tile_black",
                     parent=root, location=(0.0, -45.0, 0.0))
    _hang_plaque(gate, AREA["title_zh"], _n("plaque"))
    return root


def place_artifacts(coll, spin):
    """The ring's artifacts (FORGE_ARTIFACTS) on the spinning ring Empty: the first faces the reader at the forge
    hold, and the ring's turn (+Z) brings the rest to the front in order."""
    for i, kind in enumerate(FORGE_ARTIFACTS):
        a = RING_FRONT - 2 * math.pi * i / len(FORGE_ARTIFACTS)
        bob = 0.45 * math.sin(3 * a + 0.7)
        P.artifact(coll, kind, ART_SIZE, name=_n("artifact", kind), parent=spin,
                   location=(RING_R * math.cos(a), RING_R * math.sin(a), bob),
                   rotation=(0.0, 0.0, a + math.pi / 2))


# preview harness: the camera hints become named preview cameras
build.preview_cameras = [(h["name"], h["location"], h["target"], h["lens"]) for h in CAMERA_HINTS]


def artifact_review(collection):
    """Review target: the ring artifacts (1 m each) floating in a 5-wide grid facing -Y, ring order left to
    right, bottom row first, over a marble floor. look.py --target sect.areas.forge:artifact_review"""
    c = collection
    root = U.empty("forge.review", c, display_size=1.0)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=8.0)
    U.mesh_from_bmesh("forge.review.floor", bm, c, materials=["marble_paving"], parent=root)
    for i, kind in enumerate(FORGE_ARTIFACTS):
        row, k = divmod(i, 5)
        P.artifact(c, kind, 1.0, name="forge.review.%s" % kind, parent=root,
                   location=((k - 2) * 1.35, 0.0, 0.8 + 1.3 * row))
    return root


artifact_review.preview_cameras = [
    ("all", (0.0, -8.6, 2.4), (0.0, 0.0, 2.1), 40),
    ("row0", (0.0, -5.8, 1.5), (0.0, 0.0, 0.8), 30),
    ("row1", (0.0, -5.8, 2.8), (0.0, 0.0, 2.1), 30),
    ("row2", (0.0, -5.8, 4.1), (0.0, 0.0, 3.4), 30),
    ("above", (2.0, -5.0, 5.6), (0.0, 0.0, 2.1), 35),
]
