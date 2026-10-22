"""Area 7 'steles' -- Stele Forest of Techniques 碑林 (site section 'skills').

Blocking layout (local frame, front = -Y, z = 0 walkable):

- A 15 m wide white-marble central aisle runs from the open front (y = -37) to the stairs of a
  raised pavilion terrace (y = 9..12). Nothing stands over it.
- Two raised stele fields (low xumizuo platforms, top z = 0.5) flank the aisle. Each holds
  5 rows x 2 columns of tall steles on bixi turtle bases, angled 30 deg toward the aisle so
  their glowing glyph columns face the oncoming camera. One glow colour per row = one skill
  category (cyan, blue, violet, crimson, amber); steles grow taller toward the back (5 -> 7 m).
  Each stele is a martial-arts manual from Jin Yong's four novels (STELE_MANUALS): the art's name in
  the crown panel, its moves or mnemonic on the front, the novel and its master on the back; the
  master stele carves the Five Greats of the Mount Hua contests (華山論劍).
- Stone lanterns line the aisle between the rows.
- At the far end, a xumizuo terrace (top z = 1.5) carries a square double-eave stele pavilion
  over the larger gold-glyph master stele (8 m), with the 碑林 plaque on its upper drum.
- Covered corridors (lang, one step up) frame the courtyard on both sides: each starts at a small
  square corner pavilion at the front (x +-12) and runs along the side, then turns along the back
  wall to end beside a small one-bay gate in it (x +-15). Two pines rise behind the wall.

Walking route (architecture audit 1.7 / 4): the stair from the library lands on a paved
forecourt (AREA['arrival'], y -56), passes through a three-bay paifang (y -50) and climbs three
low steps onto the aisle. Three-step flights lead up into each stele field. From the aisle's back
end a marble walk runs west (and east) along y 9..12, then north to the rear gates; outside them a
paved walk behind the wall leads to the stair head landing (AREA['depart'], x -15, y 44), where
the stair to the Jade Slip Pavilion starts.
"""

import math

from sect.lib import util as U
from sect.lib import materials as M
from sect.lib import arch as A
from sect.lib import props as P
from sect.lib import nature as N

AREA = dict(key="steles", section_id="skills", title_en="Stele Forest of Techniques",
            title_zh="碑林", footprint=50.0)

KEY = "steles"

# Connector ends (audit W1), local (x, y, z, heading). heading = walking direction in radians,
# measured like world.py's yaw, atan2(dy, dx): +x = 0, +y = pi/2, -x = pi.
# arrival: on the paved forecourt in front of the entrance paifang (audit 1.7 item 2).
# depart: the far edge of the stair-head landing behind the left rear gate (audit 1.7 item 1).
AREA["arrival"] = (0.0, -56.0, -0.34, math.pi / 2)
AREA["depart"] = (-15.0, 44.0, -0.34, math.pi / 2)

# ---------------------------------------------------------------- layout constants (m)
AISLE_HW = 7.5                 # aisle half width -> 15 m aisle
COURT_X = 29.5                 # base paving half width
COURT_Y0, COURT_Y1 = -37.5, 37.0
FIELD_X0, FIELD_X1 = 7.5, 24.5  # stele field platform, |x| range
FIELD_Y0, FIELD_Y1 = -32.0, 9.0
FIELD_H = 0.5
ROWS_Y = (-27.0, -19.0, -11.0, -3.0, 5.0)
ROW_H = (5.0, 5.5, 6.0, 6.5, 7.0)   # stele heights per row (top <= 7.5 m incl. field)
COLS_X = (12.0, 19.0)
STELE_YAW = math.radians(30)
TERRACE_Y0, TERRACE_Y1 = 12.0, 31.0
TERRACE_HW = 13.0
TERRACE_H = 1.5
PAV_Y = 22.0
PAV_R = 6.5                    # column circle radius (square: 9.2 m column square)
PAV_COL_H = 9.5
PAV_PLAT_H = 0.6
MASTER_H = 8.0
CORR_X = 27.0
CORR_Y_BACK = 33.0             # corridor's back return runs along this line ...
CORR_BACK_END_X = 18.0         # ... and ends here, beside the rear gate
# -34.5, not the audit's -35: at -35 the corner pavilion's front step hangs 0.4 m past the
# court paving's front edge (y -37.5)
CORR_Y_FRONT = -34.5
CORNER_X = 12.0                # small square corner pavilion closing each corridor's front end
CORNER_R = 2.4
CORR_H = 3.4
CORR_PLAT_H = 0.17             # one step up from the court
WALL_Y = 35.5
WALL_X = 28.6
REAR_GATE_X = 15.0             # one-bay gates in the back wall, at x -15 (route) and +15
REAR_GATE_W, REAR_GATE_H = 5.0, 6.0
WALK_HW = 1.5                  # 3 m marble walks
WALK_TOP = 0.06                # same level as the aisle
WALK_Y0, WALK_Y1 = 9.0, 12.0   # cross walk between the stele fields and the terrace
OUT_TOP = -0.34                # paving laid on the world terrace (grass at -0.4)
BACK_Y0, BACK_Y1 = COURT_Y1, 40.0  # walk behind the back wall, joining both rear gates
FORE_X = 9.0                   # arrival forecourt half width
FORE_Y0 = -56.0                # its outer edge: the arrival line (AREA['arrival'] y). Round 11: it ran 1 m further
                               # out, under the library stair's last tread (world.py lands the stair at the arrival
                               # point), and the two lay in one plane over 5 m2: they z-fought on the web and baked a
                               # dark band across that tread. Now the tread meets the paving edge to edge
ENTRY_GATE_Y = -50.0
FLIGHT_YS = (-15.0, 1.0)       # three-step flights from the aisle up into each stele field
FLIGHT_W = 3.0

# glyph colour per skill category (one per row), master stele gold
ROW_GLYPHS = ("rune_cyan", "steles_rune_blue", "steles_rune_violet", "steles_rune_crimson",
              "steles_rune_amber")
MASTER_GLYPH = "rune_gold"

# Jin Yong manuals carved on the steles (round 9; props.JIN_YONG_MANUALS, by title). Per row, per column (inner x 12,
# outer x 19): (west, east), a pair facing each other across the aisle that belong together. The east inner stele of
# row 0 is the one nearest the camera at the 974 hold.
STELE_MANUALS = (
    (("打狗棒法", "降龍十八掌"),    # Hong Qigong's two Beggar Clan arts
     ("天罡北斗陣", "桃花島")),     # the Quanzhen array and Huang Yaoshi, who fought it
    (("乾坤大挪移", "吸星大法"),    # two great methods of drawing and turning another's force
     ("空明拳", "黯然銷魂掌")),     # Zhou Botong and Yang Guo traded these two
    (("九陰真經", "九陽神功"),      # yin and yang
     ("劍塚", "獨孤九劍")),         # Dugu Qiubai's swords and his nine swords
    (("太極拳", "太極劍"),          # Zhang Sanfeng
     ("七傷拳", "龍爪手")),         # both met on Bright Peak
    (("古墓派", "玉女心經"),        # the Ancient Tomb
     ("沖靈劍法", "華山劍法")),     # Linghu Chong
)
MASTER_MANUAL = "華山論劍"          # the Five Greats of the first and third Mount Hua contests


def _register_materials():
    M.variant("steles_rune_blue", "rune_cyan", colour="#2f7bff", core="#cfe0ff", strength=6.0)
    M.variant("steles_rune_violet", "rune_cyan", colour="#9a4dff", core="#e6d6ff", strength=6.0)
    M.variant("steles_rune_crimson", "rune_cyan", colour="#ff2440", core="#ffc4cc", strength=8.0)
    M.variant("steles_rune_amber", "rune_cyan", colour="#ff7a1a", core="#ffd9b0", strength=6.0)
    # variant() cannot pass the paving builder's own 'base' parameter (name clash), so register
    # the builder directly
    M.register("steles_paving_grey", M._paving, base="#9a968e", alt="#8a867e", grout="#55524c")


def _box(name, coll, parent, x0, x1, y0, y1, z0, z1, mats, top_mat_index=1):
    """Axis-aligned slab; the top face gets material index ``top_mat_index``."""
    return _boxes(name, coll, parent, [(x0, x1, y0, y1)], z0, z1, mats, top_mat_index)


def _boxes(name, coll, parent, rects, z0, z1, mats, top_mat_index=1):
    """One mesh of axis-aligned slabs, one per (x0, x1, y0, y1) in ``rects`` (e.g. the two legs
    of an L-shaped walk, so it is one connector object); tops get ``top_mat_index``."""
    v, f, mi = [], [], []
    for x0, x1, y0, y1 in rects:
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        b = len(v)
        v += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
              (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        f += [tuple(b + i for i in q) for q in
              ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))]
        mi += [0, top_mat_index, 0, 0, 0, 0]
    return U.mesh_from_pydata(U.name(KEY, name), v, f, coll, materials=mats, material_indices=mi,
                              smooth=False, parent=parent)


def _drum_front(pav):
    """(front y, bottom z, top z) of the pavilion's upper drum (frieze between the eaves), in the
    pavilion's local space, read from the drum mesh (built in parent space). None if not found."""
    for ch in pav.children:
        if ch.type == "MESH" and "drum" in ch.name.split("."):
            vs = [v.co for v in ch.data.vertices]
            if vs:
                return (min(v.y for v in vs), min(v.z for v in vs), max(v.z for v in vs))
    return None


def build(collection):
    """Build the stele forest at the local origin. Returns the root Empty 'steles.root'."""
    _register_materials()
    coll = collection
    root = U.empty(KEY + ".root", coll, display_size=4.0)

    # ------------------------------------------------------------ ground
    # base courtyard paving (grey slabs), z = 0 top, 0.8 m thick
    _box("paving", coll, root, -COURT_X, COURT_X, COURT_Y0, COURT_Y1, -0.8, 0.0,
         ["stone_grey", "steles_paving_grey"])
    # white marble spirit-way aisle, a 6 cm kerb above the court
    _box("aisle", coll, root, -AISLE_HW, AISLE_HW, COURT_Y0, 9.4, -0.3, 0.06,
         ["marble_white", "marble_paving"])

    # ------------------------------------------------------------ stele fields
    fw = FIELD_X1 - FIELD_X0
    fd = FIELD_Y1 - FIELD_Y0
    for side in (-1, 1):
        cx = side * (FIELD_X0 + FIELD_X1) * 0.5
        A.platform(U.name(KEY, "field", "w" if side < 0 else "e"), coll, fw, fd, FIELD_H,
                   top_mat="steles_paving_grey", sink=0.3, parent=root,
                   location=(cx, (FIELD_Y0 + FIELD_Y1) * 0.5, 0.0))

    # rows of steles on turtles, angled toward the aisle; one glow colour per row (category); each carves one Jin
    # Yong manual (STELE_MANUALS)
    manuals = {m["title"]: m for m in P.JIN_YONG_MANUALS}
    for r, (y, h, glyph) in enumerate(zip(ROWS_Y, ROW_H, ROW_GLYPHS)):
        for c, x in enumerate(COLS_X):
            for side in (-1, 1):
                seed = r * 2 + c + (0 if side < 0 else 3)
                P.stele(coll, h, glyph, turtle_base=True, seed=seed,
                        name=U.name(KEY, "stele", "r%d" % r), parent=root,
                        location=(side * x, y, FIELD_H),
                        rotation=(0, 0, -side * STELE_YAW),
                        manual=manuals[STELE_MANUALS[r][c][0 if side < 0 else 1]])

    # stone lanterns between rows 0/1 and 2/3, at the aisle edge of each field (each lantern is
    # about 22 k triangles, so only two pairs line the aisle itself)
    lantern_ys = [(ROWS_Y[0] + ROWS_Y[1]) * 0.5, (ROWS_Y[2] + ROWS_Y[3]) * 0.5]
    for y in lantern_ys:
        for side in (-1, 1):
            P.lantern_stone(coll, 2.4, name=U.name(KEY, "lantern"), parent=root,
                            location=(side * (FIELD_X0 + 0.9), y, FIELD_H))
    # three-step flights from the aisle (top 0.06) up into each stele field (top 0.5), between
    # rows; they take 1 m off each side, so the aisle stays 13 m clear (audit 4)
    for k, y in enumerate(FLIGHT_YS):
        for side in (-1, 1):
            A.stairs(U.name(KEY, "steps", "field_%s%d" % ("w" if side < 0 else "e", k)), coll,
                     FLIGHT_W, FIELD_H - WALK_TOP, ramp=False,
                     balustrade=False, parent=root, location=(side * FIELD_X0, y, WALK_TOP),
                     rotation_z=-side * math.pi / 2)

    _arrival(coll, root)

    # ------------------------------------------------------------ pavilion terrace
    tcy = (TERRACE_Y0 + TERRACE_Y1) * 0.5
    A.platform(U.name(KEY, "terrace"), coll, 2 * TERRACE_HW, TERRACE_Y1 - TERRACE_Y0, TERRACE_H,
               parent=root, location=(0, tcy, 0))
    A.stairs(U.name(KEY, "terrace_stairs"), coll, 2 * AISLE_HW - 1.0, TERRACE_H, ramp=True,
             balustrade=True, parent=root, location=(0, TERRACE_Y0, 0))
    e = 0.35
    xi = AISLE_HW - 0.5
    A.balustrade(U.name(KEY, "terrace_bal"), coll,
                 [(-xi, TERRACE_Y0 + e, TERRACE_H), (-TERRACE_HW + e, TERRACE_Y0 + e, TERRACE_H),
                  (-TERRACE_HW + e, TERRACE_Y1 - e, TERRACE_H), (TERRACE_HW - e, TERRACE_Y1 - e, TERRACE_H),
                  (TERRACE_HW - e, TERRACE_Y0 + e, TERRACE_H), (xi, TERRACE_Y0 + e, TERRACE_H)],
                 parent=root)

    # square double-eave stele pavilion (bei ting)
    pav = A.pavilion(U.name(KEY, "pavilion"), coll, sides=4, radius=PAV_R, height=PAV_COL_H,
                     roof="pyramid", double=True, roof_mat="roof_tile_teal", platform_h=PAV_PLAT_H,
                     seats=False, hanging=True, parent=root, location=(0, PAV_Y, TERRACE_H))
    floor_z = TERRACE_H + PAV_PLAT_H
    # the larger master stele under it, gold glyphs (all skills)
    # (widened 1.3x so it reads as the larger monument; height stays 8 m)
    P.stele(coll, MASTER_H, MASTER_GLYPH, turtle_base=True, seed=5, name=U.name(KEY, "stele_master"),
            parent=root, location=(0, PAV_Y + 0.4, floor_z), scale=(1.3, 1.1, 1.0),
            manual=manuals[MASTER_MANUAL])

    # plaque 碑林 centred on the upper drum, under the upper eave (classic double-eave spot)
    drum = _drum_front(pav)
    if drum is not None:
        dy, dz0, dz1 = drum
        # the skirt roof hides the drum's lowest 0.4 m: centre on the visible part
        pz = TERRACE_H + 0.5 * (dz0 + 0.4 + dz1)
        py = PAV_Y + dy - 0.22
        width = min(2.8, 1.9 * (dz1 - dz0 - 0.4))
    else:   # fallback: hang it in front of the lower bracket band
        half = PAV_R * math.cos(math.pi / 4)
        py, pz, width = PAV_Y - half - 1.6, floor_z + PAV_COL_H + 0.4, 2.6
    P.plaque(coll, AREA["title_zh"], width, name=U.name(KEY, "plaque"), parent=root,
             location=(0, py, pz))

    # flanking lanterns on the terrace
    for side in (-1, 1):
        P.lantern_stone(coll, 3.0, name=U.name(KEY, "lantern_terrace"), parent=root,
                        location=(side * 9.5, 14.5, TERRACE_H))

    # ------------------------------------------------------------ corridors (lang) + back wall
    # two corridors one step up (0.17 m): each starts at a small square corner pavilion at the
    # front, runs along the side and turns along the back wall to end beside a rear gate
    # (audit 4). The corridor starts on the pavilion's inner column line, not its centre, so no
    # corridor post stands in the middle of the pavilion's open faces.
    corner_in = CORNER_R * math.cos(math.pi / 4)
    for side in (-1, 1):
        A.pavilion(U.name(KEY, "corner_pav"), coll, sides=4, radius=CORNER_R, height=CORR_H,
                   roof_mat="roof_tile_black", platform_h=CORR_PLAT_H, seats=False, hanging=False,
                   parent=root, location=(side * CORNER_X, CORR_Y_FRONT, 0.0))
        pts = [(side * (CORNER_X + corner_in), CORR_Y_FRONT), (side * CORR_X, CORR_Y_FRONT),
               (side * CORR_X, CORR_Y_BACK), (side * CORR_BACK_END_X, CORR_Y_BACK)]
        A.corridor(U.name(KEY, "lang"), coll, pts, width=3.2, height=CORR_H, bay=4.2,
                   platform_h=CORR_PLAT_H, seats=False, hanging=False, parent=root)
    # back wall in three pieces, open at both rear gates
    g0, g1 = REAR_GATE_X - REAR_GATE_W * 0.5, REAR_GATE_X + REAR_GATE_W * 0.5
    for x0, x1 in ((-WALL_X, -g1), (-g0, g0), (g1, WALL_X)):
        A.wall(U.name(KEY, "wall_back"), coll, [(x0, WALL_Y), (x1, WALL_Y)],
               height=3.6, thickness=0.7, parent=root)

    _rear_exit(coll, root)

    # ------------------------------------------------------------ pines behind the back wall
    # moved out from (+-17, 41.5): the left one stood on the new path to the stair (audit 1.7)
    for side, seed in ((-1, 2), (1, 5)):
        N.pine(coll, height=12.0, seed=seed, name=U.name(KEY, "pine"), parent=root,
               location=(side * 27.0, 46.0, -0.4))

    return root


def _arrival(coll, root):
    """Arrival from the library (audit 1.7 item 2): paved forecourt on the terrace, three-bay
    entrance paifang, three low steps onto the aisle, and the entrance lantern pair."""
    _box("arrival", coll, root, -FORE_X, FORE_X, FORE_Y0, COURT_Y0, -0.8, OUT_TOP,
         ["stone_grey", "marble_paving"])
    # 0.40 m from the forecourt to the aisle top: three risers of about 0.13 m
    A.stairs(U.name(KEY, "steps", "aisle"), coll, 2 * AISLE_HW, WALK_TOP - OUT_TOP, ramp=False,
             balustrade=False, parent=root, location=(0.0, COURT_Y0, OUT_TOP))
    A.paifang(U.name(KEY, "gate"), coll, bays=3, width=34.0, height=24.0, seed=7, parent=root,
              location=(0.0, ENTRY_GATE_Y, OUT_TOP))
    # the entrance lanterns used to stand at (+-9.6, -34), where the corner pavilions now are;
    # they now flank the walk from the paifang to the aisle steps, in line with its inner columns
    for side in (-1, 1):
        P.lantern_stone(coll, 3.0, name=U.name(KEY, "lantern_gate"), parent=root,
                        location=(side * 7.0, -42.0, OUT_TOP))


def _rear_exit(coll, root):
    """Way out to the Jade Slip Pavilion (audit 1.7 item 1): marble walks from the aisle's back
    end to two one-bay gates in the back wall, a paved walk behind the wall joining them, and the
    stair-head landing at AREA['depart'] (-15, 44)."""
    mats = ["marble_white", "marble_paving"]
    for side in (-1, 1):
        sfx = "w" if side < 0 else "e"
        # one L-shaped walk per side: west (east) between the stele field and the terrace from
        # the aisle edge, then north beside the terrace, through the gate to the court's back edge
        _boxes("walk.rear_" + sfx, coll, root,
               [(side * FIELD_X0, side * (REAR_GATE_X + WALK_HW), WALK_Y0, WALK_Y1),
                (side * (REAR_GATE_X - WALK_HW), side * (REAR_GATE_X + WALK_HW), WALK_Y1, BACK_Y0)],
               -0.3, WALK_TOP, mats)
        A.paifang(U.name(KEY, "gate_rear"), coll, bays=1, width=REAR_GATE_W, height=REAR_GATE_H,
                  roof_mat="roof_tile_black", seed=11, parent=root,
                  location=(side * REAR_GATE_X, WALL_Y, 0.0))
        # down 0.40 m from the gate threshold to the walk behind the wall (three ~0.13 m risers)
        A.stairs(U.name(KEY, "steps", "rear_" + sfx), coll, 2 * WALK_HW, WALK_TOP - OUT_TOP, ramp=False,
                 balustrade=False, parent=root, location=(side * REAR_GATE_X, BACK_Y0, OUT_TOP),
                 rotation_z=math.pi)
    # behind the wall, on the terrace: one walk joining both gates ...
    _box("walk.back", coll, root, -(REAR_GATE_X + WALK_HW), REAR_GATE_X + WALK_HW, BACK_Y0, BACK_Y1,
         -0.7, OUT_TOP, ["stone_grey", "marble_paving"])
    # ... and the stair-head landing, 6 m wide for the 5 m world stairway, ending at the depart
    dx, dy = AREA["depart"][0], AREA["depart"][1]
    _box("depart", coll, root, dx - 3.0, dx + 3.0, BACK_Y1, dy, -0.7, OUT_TOP,
         ["stone_grey", "marble_paving"])


# Where the fly-through camera should pass (LOCAL coords, front = -Y), ordered along the flight.
# The glide stays on the aisle axis at 4 m; the exit rises toward -X (the next area, scroll, lies
# to the north-west).
CAMERA_HINTS = [
    dict(name="approach", location=(0.0, -100.0, 18.0), target=(0.0, 0.0, 6.0), lens=30),
    dict(name="aisle_entry", location=(0.0, -46.0, 4.0), target=(0.0, 20.0, 6.0), lens=24),
    dict(name="aisle_mid", location=(0.0, -22.0, 4.0), target=(0.0, 24.0, 7.5), lens=24),
    dict(name="pavilion_rise", location=(-18.0, -6.0, 19.0), target=(0.0, 22.0, 9.5), lens=24),
]

# look.py preview harness: makes the hint views available by name (--cams approach,...)
build.preview_cameras = [(h["name"], h["location"], h["target"], h["lens"]) for h in CAMERA_HINTS]
