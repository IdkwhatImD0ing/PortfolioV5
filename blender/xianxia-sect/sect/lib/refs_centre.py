"""Round 39, centre lane: the Jin Yong references at the Stele Forest and the Jade Slip Pavilion get the r31 plan's
staging (sect/patch_r39_centre.py patches an existing file; areas/steles.py and scroll.py call the same builders in a
fresh build). The steles' re-carved manuals are areas/steles.py's own (STELE_MANUALS, MASTER_MANUAL); the turn of
Ice-Fire Island is sect/scenery.py's (turn_icefire).

- steles (hold 974): the Ming Sect's six Holy Flame Tokens 聖火令 (Heaven Sword and Dragon Saber ch. 29-30) stand at
  the head of the agents row, at half size (1.2-1.7 m: in the novel an envoy carries four inside his robe; the
  terrace's were 2.4-3.4 m) on a waist-high stand: 'steles.tokens', under the agents row's front stele (TOKENS_HOST),
  so the row's hover label (hotspot skills:1) carries their name. Their builders are areas/scroll.py's (fire_tokens,
  TokenSpec): the tokens' inlays keep their full-size depths, the stand stands on a tall stone plinth.
- scroll (1103): Dugu Qiubai's Sword Tomb 劍塚 (Return of the Condor Heroes ch. 26) on the lawn right of the pavilion
  and the terrace, on grass: 'scroll.sword_tomb'. A boulder whose dressed front carries 劍塚 cut into the stone and
  painted red, and in front of it the bluestone slab with the four places in the novel's order, left to right as the
  hold sees them: the keen sword, a long stone strip where the soft sword lay (he threw it into a ravine), the heavy
  sword's place empty (it stands at the arena) and the wooden sword. The slab, its socket stones and the two swords are
  areas/forge.py's own builders (_st_slab, _st_sharp_sword, _st_wood_sword; the tomb stood at the forge until round
  34). No text under the swords: too small to read from the hold, the card carries the story.

Everything a builder here makes carries the custom property TAG (its part). The characters are cut the round-12 way:
the face is cut away under every stroke (props._imprint, holes) and the paint lines the cut's walls and floor, so no
face lies in front of another.
"""
import math

import bmesh
from mathutils import Matrix, Vector

from sect.lib import materials as M
from sect.lib import props as P
from sect.lib import util as U

TAG = "sect_r39_centre"        # object (and mesh) property: the part that built it


def tag(ob, part):
    ob[TAG] = part
    if ob.type == 'MESH' and ob.data is not None:
        ob.data[TAG] = part
    return ob


def local_matrix(ob, root):
    """``ob``'s matrix in ``root``'s frame, from the parent chain between them (so it does not depend on where the
    root stands: a fresh build, with the area at the origin, and a patched file give the same numbers)."""
    chain = []
    o = ob
    while o is not None and o != root:
        chain.append(o)
        o = o.parent
    if o is None:
        raise RuntimeError("local_matrix: %s is not under %s" % (ob.name, root.name))
    m = Matrix.Identity(4)
    for o in reversed(chain):
        m = m @ o.matrix_parent_inverse @ o.matrix_basis
    return m


# ================================================================ steles: the Holy Flame Tokens at the agents row
TOKENS_NAME = "steles.tokens"
TOKENS_NAMES = (TOKENS_NAME, TOKENS_NAME + ".body", TOKENS_NAME + ".gold", TOKENS_NAME + ".plinth",
                TOKENS_NAME + ".stand")
TOKENS_HOST = "steles.stele.r1"   # the agents row's front stele (west, inner: 吸星大法), hotspot skills:1's first object
TOKENS_K = 0.5                    # the tokens at half the terrace's size: 1.2-1.7 m
# the stone plinth (x size, y size, z0, z1): foot, a tall waist, top slab; the lacquer beam on it (0.16 m at k 0.5)
# puts the slots at waist height (0.86 m) and the longest token's top at 2.47 m over the field, under the front
# stele's carved columns as the hold sees them
TOKENS_PLINTH = ((2.50, 0.80, -0.03, 0.06), (2.34, 0.64, 0.06, 0.62), (2.44, 0.74, 0.62, 0.70))
# steles.root frame: on the west stele field (its top z 0.5), in front of the agents row's front stele (past its
# turtle's head) and left of the aisle lantern between rows 0 and 1 as the 974 hold sees them, turned like the west
# steles (steles.STELE_YAW): square to the hold camera within 6 deg
TOKENS_AT = (-10.4, -23.8, 0.5)
TOKENS_YAW = math.radians(30.0)


def token_spec():
    from sect.areas import scroll as SC
    return SC.TokenSpec(TOKENS_K, TOKENS_PLINTH)


def tokens_matrix(host, root):
    """The tokens' Empty's matrix_basis under ``host`` (the stele instance): TOKENS_AT / TOKENS_YAW in root's frame."""
    want = Matrix.Translation(Vector(TOKENS_AT)) @ Matrix.Rotation(TOKENS_YAW, 4, 'Z')
    return local_matrix(host, root).inverted() @ want


def steles_tokens(coll, root, host, names=TOKENS_NAMES):
    """The six tokens on their waist-high stand under ``host`` (see the module notes): an Empty names[0] holding
    names[1] (iron and fire), [2] (gold), [3] (plinth) and [4] (stand). Returns the Empty."""
    from sect.areas import scroll as SC
    grp = SC.fire_tokens(coll, host, names, token_spec(), matrix=tokens_matrix(host, root))
    grp.empty_display_size = 0.5
    for o in [grp] + list(grp.children):
        tag(o, "tokens")
    return grp


# ================================================================ scroll: Dugu Qiubai's Sword Tomb on the lawn
TOMB_NAME = "scroll.sword_tomb"
LAWN_Z = -0.40                 # the lawn's top round the Jade Slip Pavilion (world.range), in scroll.root's frame
TOMB_AT = (31.2, 17.8)         # scroll.root frame: on the lawn right of the terrace (its edge x 27) and the pavilion,
                               # in front of the forest edge, 10 m from the bamboo
TOMB_YAW = math.radians(-24.0) # its front (-Y) toward the 1103 hold as the site frames it (scroll.SITE_FRAMING)
# tomb frame: origin on the lawn at the boulder's foot, front -Y, +x to the reader's right at the hold, z 0 the lawn
TOMB_TEXT = "劍塚"
TOMB_CELL = 1.2                # m: a character's cell (its paint about 1.05 m: ~21 px at the hold)
TOMB_GAP = 0.1                 # m between the two cells
TOMB_TEXT_Z = 2.9              # m over the lawn: the column's middle (clear above the stone strip in front)
TOMB_TEXT_MARGIN = 0.12        # m: the paint stays this far inside the dressed face's outline
TOMB_CUT = 0.05                # m: the strokes' depth
TOMB_RES = 3                   # font curve resolution
TOMB_FACE = ((0.98, -0.45), (0.95, 1.0), (0.9, 3.7), (0.55, 4.3), (-0.15, 4.42), (-0.75, 4.2), (-0.92, 3.4),
             (-0.97, 1.0), (-1.0, -0.45))   # the dressed face's outline (x, z), counter-clockwise from its foot
TOMB_RINGS = ((0.12, 0.08), (0.70, 0.50), (1.15, 1.15), (0.95, 1.85), (0.45, 2.35))   # (outward, back) of each ring
TOMB_RISE = 0.45               # the rings grow upward this much less (a boulder lower than it is wide)
TOMB_SINK = 0.6                # and downward, under the lawn, this much less
TOMB_BACK = (0.0, 2.6, 2.0)    # the back's apex (x, y, z): the rings close on it
TOMB_WANDER = (0.07, 1.4)      # m, 1/m: how far the dressed edge wanders, and how fast
TOMB_LUMP = (0.12, 0.9)        # m, 1/m: the rock sides' lumps
SLAB_Y = -1.25                 # the bluestone's centre line, in front of the face (y 0); its back 0.7 m from the face
SLAB_SINK = 0.12               # its bottom this far under the lawn
STRIP = (0.24, 0.03, 1.30)     # the stone strip in the soft sword's place: width, thickness, length
STRIP_LEAN = (-3.0, 2.0)       # its lean (deg about x, about y)
TOMB_FACE_MAT = M.variant("sword_tomb_face", "stone_grey", c1="#a19c93", c2="#89847c", speck="#5d5952",
                          light="#bab4a9", light_amt=0.3, rough=(0.7, 0.9), bump=0.12)   # dressed, weathered pale stone
TOMB_PAINT = "lacquer_red_worn"  # the cut strokes' paint (red on the pale face)
TOMB_ROCK = "forge_tomb_rock"    # the boulder's rough sides: the forge tomb's outcrop rock (areas/forge.py)


def _face_outline():
    """The dressed face's outline (x, z), counter-clockwise seen from the front (-Y): TOMB_FACE resampled every 0.25 m,
    its edges wandering in and out (rough-dressed), the buried foot left straight."""
    pts = []
    n = len(TOMB_FACE)
    for i in range(n):
        (xa, za), (xb, zb) = TOMB_FACE[i], TOMB_FACE[(i + 1) % n]
        L = math.hypot(xb - xa, zb - za)
        m = max(1, int(round(L / 0.25)))
        for k in range(m):
            t = k / m
            pts.append((xa + (xb - xa) * t, za + (zb - za) * t))
    amp, freq = TOMB_WANDER
    out = []
    for i, (x, z) in enumerate(pts):
        if z < 0.0:
            out.append((x, z))
            continue
        (xa, za), (xb, zb) = pts[i - 1], pts[(i + 1) % len(pts)]
        tx, tz = xb - xa, zb - za
        ln = math.hypot(tx, tz) or 1.0
        w = amp * U.noise3((x * freq, z * freq, 0.3), 1.0, seed=39)
        out.append((x + tz / ln * w, z - tx / ln * w))
    return out


def _glyph_regions():
    """[(polygon [(x, z)], 'paint')] of 劍塚 on the face (tomb frame), top to bottom, centred on x 0; and each cell's
    ink box (x0, x1, z0, z1)."""
    regions, boxes = [], []
    n = len(TOMB_TEXT)
    total = n * TOMB_CELL + (n - 1) * TOMB_GAP
    font = _font()
    for k, ch in enumerate(TOMB_TEXT):
        me = P._text_mesh(ch, TOMB_CELL, TOMB_RES, font=font)
        if not len(me.polygons):
            raise RuntimeError("sword tomb: glyph %r has no faces (font %s)" % (ch, font))
        zc = TOMB_TEXT_Z + total / 2 - TOMB_CELL / 2 - k * (TOMB_CELL + TOMB_GAP)
        co = [(v.co.x, v.co.y) for v in me.vertices]
        xs, ys = [c[0] for c in co], [c[1] for c in co]
        boxes.append((min(xs), max(xs), zc + min(ys), zc + max(ys)))
        for p in me.polygons:
            regions.append(([(co[i][0], zc + co[i][1]) for i in p.vertices], "paint"))
    return regions, boxes


def _font():
    """KaiTi as a path both os.path and bpy.data.fonts.load accept (the render box mirrors the fonts at /C:/...)."""
    import os
    for p in (U.FONT_KAITI, U.FONT_YAHEI):
        for c in (p, "/" + p if p and not p.startswith("/") else None):
            if c and os.path.isfile(c):
                return os.path.abspath(c)
    return U.FONT_KAITI


def _inside(poly, x, z, margin):
    """(x, z) inside the polygon and at least ``margin`` from its edges."""
    n = len(poly)
    inside = False
    for i in range(n):
        (xa, za), (xb, zb) = poly[i], poly[(i + 1) % n]
        if (za > z) != (zb > z) and x < xa + (z - za) * (xb - xa) / (zb - za):
            inside = not inside
        ex, ez = xb - xa, zb - za
        L2 = ex * ex + ez * ez or 1e-12
        t = max(0.0, min(1.0, ((x - xa) * ex + (z - za) * ez) / L2))
        if math.hypot(x - xa - t * ex, z - za - t * ez) < margin:
            return False
    return inside


def boulder_bm():
    """The boulder in the tomb frame: its flat dressed face in the plane y 0 (material 0), the rough rock behind it
    (1: rings growing out and back from the face's outline, lumpy, closing on TOMB_BACK), 劍塚 cut TOMB_CUT into the
    face (2: the cut's walls and floor). One closed solid, its foot buried. Returns (bm, info)."""
    outline = _face_outline()
    n = len(outline)
    bm = bmesh.new()
    front = [bm.verts.new((x, 0.0, z)) for x, z in outline]
    face = bm.faces.new(front)
    face.material_index = 0
    outward = []
    for i in range(n):
        (xa, za), (xb, zb) = outline[i - 1], outline[(i + 1) % n]
        tx, tz = xb - xa, zb - za
        ln = math.hypot(tx, tz) or 1.0
        outward.append((tz / ln, -tx / ln))               # counter-clockwise outline: (tz, -tx) points out
    rings = [front]
    amp, freq = TOMB_LUMP
    for k, (grow, back) in enumerate(TOMB_RINGS):
        ring = []
        for (x, z), (ox, oz) in zip(outline, outward):
            j = 1.0 + (amp / max(grow, 0.1)) * U.noise3((x * freq, z * freq, 0.7 * k), 1.0, seed=40) if k else 1.0
            g = grow * j * (1.0 - TOMB_RISE * max(0.0, oz) - TOMB_SINK * max(0.0, -oz))
            y = back * (1.0 + 0.12 * U.noise3((x * freq, z * freq, 2.0 + k), 1.0, seed=41)) if k else back
            ring.append(bm.verts.new((x + ox * g, y, z + oz * g)))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            f = bm.faces.new((a[i], b[i], b[j], a[j]))
            f.material_index = 1
            f.smooth = True
    tip = bm.verts.new(TOMB_BACK)
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((rings[-1][j], rings[-1][i], tip))
        f.material_index = 1
        f.smooth = True
    bm.normal_update()
    if face.normal.y > 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.normal_update()
    # the characters: holes in the face, walls and floors of paint, every stroke inside the face's outline
    regions, boxes = _glyph_regions()
    out_pts = [(x, z) for poly, _t in regions for x, z in poly
               if not _inside(outline, x, z, TOMB_TEXT_MARGIN)]
    if out_pts:
        raise RuntimeError("sword tomb: %d points of 劍塚 lie within %.2f m of the face's edge or past it, e.g. %s" % (
            len(out_pts), TOMB_TEXT_MARGIN, out_pts[0]))
    got = P._imprint(bm, [face], lambda co: (co.x, co.z), lambda x, z: Vector((x, 0.0, z)), regions, holes=True)
    holes = got.get("paint", [])
    if not holes:
        raise RuntimeError("sword tomb: no character cut into the face")
    key = lambda p: (round(p.x, 7), round(p.z, 7))               # noqa: E731
    back_of = {}

    def bv(p):
        k_ = key(p)
        w = back_of.get(k_)
        if w is None:
            w = back_of[k_] = bm.verts.new((p.x, TOMB_CUT, p.z))
        return w
    rim = [e for e in bm.edges if len(e.link_faces) == 1 and all(abs(v.co.y) < 1e-6 for v in e.verts)]
    for e in rim:
        a, b = e.verts
        f = bm.faces.new((a, b, bv(b.co), bv(a.co)))
        f.material_index = 2
    floors = 0
    for p0, p1, p2, _nrm in holes:
        vs = [bv(p) for p in (p0, p1, p2)]
        if len(set(vs)) < 3:
            continue
        try:
            f = bm.faces.new(vs)
        except ValueError:
            continue
        f.material_index = 2
        floors += 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        if f.material_index != 1:
            f.smooth = False
    open_edges = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    return bm, dict(rim_edges=len(rim), floors=floors, holes=len(holes), boxes=boxes, open_edges=open_edges)


def tomb_layout():
    """Heights in the tomb frame (z 0 the lawn): the slab's bottom and centre y, the socket stones' top, each place's
    mortise floor (x, y, z), keyed like forge.ST_SLOTS (sharp, soft, heavy, wood)."""
    from sect.areas import forge as F
    _sx, _sy, L, D, H, ch = F.ST_SLAB
    slab_z = -SLAB_SINK
    sl, sd, sh, sch, sink = F.ST_SOCKET
    top = slab_z + H - sink + sh
    floors = {key: (x, SLAB_Y, top - md) for key, x, ml, mw, md in F.ST_SLOTS}
    return dict(slab_z=slab_z, socket_top=top, floors=floors, slab=(L, D, H))


def _strip_geo():
    """The long stone strip 長條石片 that lies in the soft sword's place, in its own frame (foot at the origin, up +z):
    a thin bluestone plank, its top broken off at a slant, its edges chamfered."""
    from sect.areas import forge as F
    g = F._fw_geo()
    w, t, h = STRIP
    F._fw_prism_xz(g, ((-w / 2, 0.0), (w / 2, 0.0), (w / 2, h - 0.03), (0.35 * w, h), (-0.1 * w, h - 0.05),
                       (-w / 2, h - 0.09)), -t / 2, t / 2, mat=0, edge=1.0)
    return g


def sword_tomb(coll, root, name=TOMB_NAME):
    """Dugu Qiubai's Sword Tomb on the lawn at TOMB_AT (see the module notes): an Empty ``name`` (turned TOMB_YAW) under
    ``root`` holding <name>.boulder, .slab, .sharp_sword, .strip and .wood_sword. Returns (the Empty, boulder info)."""
    from sect.areas import forge as F
    emp = U.empty(U.unique_name(name), coll, location=(TOMB_AT[0], TOMB_AT[1], LAWN_Z), parent=root,
                  rotation=(0.0, 0.0, TOMB_YAW), display_size=2.0)
    bm, info = boulder_bm()
    boulder = U.mesh_from_bmesh(U.unique_name(name + ".boulder"), bm, coll,
                                materials=[TOMB_FACE_MAT, TOMB_ROCK, TOMB_PAINT], smooth=None, parent=emp)
    boulder.data[P.R12_TAG] = "cut"     # the strokes are holes the paint lines: bake_web keeps such a mesh whole near a
                                        # view (its CUT_TAG rule), so the decimator cannot tear the characters
    lay = tomb_layout()
    F._fw_object(name + ".slab", coll, emp, F._st_slab(), [F.ST_MATS["slab"]], location=(0.0, SLAB_Y, lay["slab_z"]))
    for key, build, nm in (("sharp", F._st_sharp_sword, "sharp_sword"), ("wood", F._st_wood_sword, "wood_sword")):
        rx, ry, rz = (math.radians(a) for a in F.ST_LEAN[key])
        F._fw_object(name + "." + nm, coll, emp, build(), F.ST_SWORD_MATS[key], location=lay["floors"][key],
                     rotation=(rx, ry, rz))
    F._fw_object(name + ".strip", coll, emp, _strip_geo(), [F.ST_MATS["slab"]], location=lay["floors"]["soft"],
                 rotation=(math.radians(STRIP_LEAN[0]), math.radians(STRIP_LEAN[1]), 0.0))
    for o in [emp] + list(emp.children):
        tag(o, "sword_tomb")
    return emp, info
