"""Round 34, west lane: the Jin Yong references at the Heart-Mirror Terrace, the Cave Abode and the Moon-Gazing Summit,
re-staged so each sits where such a thing would be kept, at the stop whose story it shares (scratchpad r31
proposal.md, approved with one change: the hover cards describe the item, they do not justify its place). Builders for
sect/areas/mirror.py, sect/areas/summit.py and sect/patch_r34_west.py (the patch builds the same pieces into a finished
file); the abode's changes are constants in sect/areas/abode.py.

Mirror 217 ('about'):
- 玉簫 Huang Yaoshi's jade flute (Legend of the Condor Heroes) leaves its slate by the pond: it lies on a black-lacquer
  stand in the pond pavilion, facing the mirror across the pond, where the hold sees it through the open front.
  flute_set(): Empty 'mirror.flute' under 'mirror.ting' (so the Pond Pavilion hotspot carries it), its stand, the
  flute (sect/lib/flute_props.py, scaled FLUTE_SCALE) and its cord and tassel hanging over the stand's front edge.
- 思過崖 the Cliff of Reflection (The Smiling, Proud Wanderer ch. 7-10: the bare cliff on Mount Hua where Linghu Chong
  was sent to face the wall for his faults, and where Feng Qingyang taught him the Nine Swords of Dugu): three ~5 m
  characters top to bottom, carved into a dressed face on the bare cliff behind and above the mirror and filled with
  ink. siguoya(): one mesh 'mirror.siguoya' under 'mirror.root', a pale dressed stone face standing out of the range's
  rock (world.range) with the characters cut 0.25 m into it (walls and floors ink; no face left under the ink),
  its sides falling back into the rock. siguoya_clear(): the range's tree masks are zeroed round it and in the
  hold's line of sight to it, so the cliff there is bare (寸草不生).

Summit 1647 ('footer', contact): the condor's crag moves right of the pavilion (sect/areas/summit.py); coil():
Xiaolongnü's golden-bell ribbon 金鈴索 (Return of the Condor Heroes) coiled on the condor's rock with one bell over
the edge; blinds(): 綠竹巷 (The Smiling, Proud Wanderer ch. 13) bamboo blinds half down with pale gauze on the
pavilion's front bays, the middle one rolled up over a qin and a lit lamp.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from sect.lib import materials as M
from sect.lib import util as U

# ---------------------------------------------------------------- the site's view of a stop
# client/src/lib/sect/framing.ts STOP_FRAMING: at a framed hold the page shows the camera's pose of frame (hold - back),
# turned yaw about world up, then pitch about the camera's own right axis (free-look.ts composeLook). The abode and
# the summit have no framing (the plain chase.cam at the frame).
SITE_FRAMING = {217: (4.0, -3.0, 13)}        # hold frame -> (yaw deg, pitch deg, back frames)
SHOT_FRAMES = {"mirror": 217, "abode": 1380, "summit": 1647, "gate": 93, "forge": 352}   # (gate, forge: what else sees 思過崖)
CLOSE_TARGETS = {                             # preview shot -> ([object names], fixed world box or None[, fill])
    "mirror_pavilion": (["mirror.ting"], None, 0.8),
    "mirror_flute": (["mirror.flute"], ((-106.2, 180.0, 71.0), (-102.0, 184.0, 72.6)), 0.75),
    "mirror_eastrim": ([], ((-83.4, 189.5, 69.6), (-78.4, 194.5, 73.5)), 0.8),     # round 7's flute set's place
    "mirror_cliff": ([], ((-142.0, 394.0, 71.0), (-128.0, 402.0, 99.0)), 0.75),     # where 思過崖 goes
    "abode_lawn": ([], ((189.5, 1341.0, 249.8), (199.5, 1349.5, 252.5)), 0.8),     # the duet's old and new places
    "summit_right": ([], ((-9.0, 1453.0, 326.0), (-3.0, 1460.0, 331.0)), 0.6),     # the condor's new place
    "abode_duet": (["abode.duet"], None, 0.55),
    "abode_eave": (["abode.tea_pavilion"], None, 0.8),
    "summit_condor": (["summit.condor_cap", "summit.condor_bird"], None, 0.6),
    "summit_blinds": (["summit.pavilion"], None, 0.85),
    "summit_crag": (["summit.condor_crag"], None, 0.7),
    "summit_qin": (["summit.qin_table", "summit.qin", "summit.qin_lamp"], None, 0.7),
    "summit_coil": (["summit.ribbon"], None, 0.7),
}


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


# ---------------------------------------------------------------- shared helpers

def local_matrix(ob, root):
    """``ob``'s matrix in ``root``'s frame from the transforms themselves (valid before a fresh build's depsgraph
    has evaluated anything)."""
    m = ob.matrix_parent_inverse @ ob.matrix_basis
    p = ob.parent
    while p is not None and p != root:
        m = p.matrix_parent_inverse @ p.matrix_basis @ m
        p = p.parent
    return m


def world_matrix(ob):
    """``ob``'s world matrix from its transforms (as local_matrix with no root)."""
    return local_matrix(ob, None)


def instance_tris(ob, M_to):
    """(verts, polys) of what Empty ``ob`` instances (its collection's meshes), in the frame ``M_to`` @ world."""
    verts, polys = [], []
    ic = ob.instance_collection
    if ic is None:
        return verts, polys
    base = world_matrix(ob) @ Matrix.Translation(-Vector(ic.instance_offset))
    for o in ic.all_objects:
        if o.type != 'MESH':
            continue
        Mo = M_to @ base @ local_matrix(o, None)
        b = len(verts)
        verts.extend(Mo @ v.co for v in o.data.vertices)
        polys.extend(tuple(b + i for i in p.vertices) for p in o.data.polygons)
    return verts, polys


def mesh_tris(ob, M_to):
    """(verts, polys) of mesh object ``ob`` in the frame ``M_to`` @ world (from its transforms)."""
    Mo = M_to @ world_matrix(ob)
    return [Mo @ v.co for v in ob.data.vertices], [tuple(p.vertices) for p in ob.data.polygons]


def bvh_of(parts):
    verts, polys = [], []
    for vs, ps in parts:
        b = len(verts)
        verts.extend(vs)
        polys.extend(tuple(b + i for i in p) for p in ps)
    return BVHTree.FromPolygons(verts, polys) if polys else None


def bm_part(bm, name=None):
    """A fresh BMesh (for parts built separately and appended)."""
    return bmesh.new()


def bm_append(dst, src, mat=0, matrix=None):
    """Copy BMesh ``src`` into ``dst`` (faces get material ``mat``; ``matrix`` transforms the copy). Frees src."""
    vmap = {}
    for v in src.verts:
        vmap[v] = dst.verts.new(matrix @ v.co if matrix is not None else v.co)
    for f in src.faces:
        nf = dst.faces.new([vmap[v] for v in f.verts])
        nf.material_index = mat if mat is not None else f.material_index
        nf.smooth = f.smooth
    src.free()


def bm_prism(bm, outline, y0, y1, mat=0, smooth=False):
    """Closed prism: the (x, z) polygon ``outline`` (counter-clockwise seen from -y) extruded from y0 to y1."""
    a = [bm.verts.new((x, y0, z)) for x, z in outline]
    b = [bm.verts.new((x, y1, z)) for x, z in outline]
    n = len(outline)
    out = [bm.faces.new(list(reversed(a))), bm.faces.new(b)]
    for i in range(n):
        j = (i + 1) % n
        out.append(bm.faces.new((a[i], a[j], b[j], b[i])))
    for f in out:
        f.material_index = mat
        f.smooth = smooth
    return out


def bm_box(bm, lo, hi, mat=0):
    """Closed axis box from corner lo to corner hi."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    return bm_prism(bm, [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], y0, y1, mat)


def closed_report(me):
    """(edges in fewer than two faces, edges in more than two) of a mesh."""
    bm = bmesh.new()
    bm.from_mesh(me)
    lo = sum(1 for e in bm.edges if len(e.link_faces) < 2)
    hi = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    bm.free()
    return lo, hi


def mesh_object(name, bm, coll, mats, parent, matrix=None, smooth=None, tag=None):
    """Mesh object ``name`` from ``bm`` (normals recalculated, freed) with material slots ``mats``."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = U.mesh_from_bmesh(name, bm, coll, materials=mats, smooth=smooth, parent=parent,
                           matrix=matrix if matrix is not None else Matrix.Identity(4))
    if tag is not None:
        ob["sect_item"] = tag
    return ob


# ================================================================ mirror: the jade flute in the pond pavilion
# The pond pavilion (mirror.ting, arch.pavilion: six faces, radius 3.2) stands on its island with its open front
# (face 0, the steps) toward the bridge and the 217 hold, which looks in through it from 57-66 m. Its goose-neck
# benches lean their backrests inward, so from the hold every bench's seat is either behind its backrest's slats (the
# back ones) or seen end-on (the front two): the flute stands on its own black-lacquer stand on the pavilion's floor
# instead, a low table with two notched cradles on its top, set FLUTE_OFFSET from the pavilion's middle toward the
# mirror and turned to face it (its front, where the cord hangs, toward the mirror across the pond). The hold sees it
# through the open front against the back bench, the pale jade lying across the black stand. The flute
# (sect/lib/flute_props.py: 2.09 m, 2.8x a real xiao, sized for the pond rim at 52 m) rests in the cradles, its cord
# running from the front vent hole across the stand's top and over its front edge, the knot, jade bead and gold
# tassel hanging against it. The whole set is shown at FLUTE_SCALE (the flute 1.67 m, ~35 px at the hold), the stand
# built in the same set frame (flute_props' units: +x along the flute, -y the front, z up from the floor).
FLUTE = "mirror.flute"
FLUTE_ITEM = "jade_flute"                 # obj['sect_item'] of every object of the set (as the round-7 set)
FLUTE_SCALE = 0.8
FLUTE_OFFSET = 0.55                       # m from the pavilion's middle toward the mirror
FLUTE_STAND = "mirror.flute_stand"
FLUTE_XIAO = "mirror.flute_xiao"
FLUTE_TASSEL = "mirror.flute_tassel"
FLUTE_NAMES = (FLUTE, FLUTE_STAND, FLUTE_XIAO, FLUTE_TASSEL)
FLUTE_OLD = ("mirror.flute", "mirror.flute_rock", "mirror.flute_bag", "mirror.flute_xiao", "mirror.flute_tassel",
             "mirror.flute_petals", "mirror.flute_peach")      # the round-7 set at the pond's east rim
FLUTE_MIRROR = "mirror.mirror_stand"      # what the stand faces
STAND_MATS = ("lacquer_black",)
# the stand, set frame (before FLUTE_SCALE): a table top over the flute's whole length, end-slab legs on cloud feet,
# front and back aprons, and two cradles on the top whose semicircular notches take the flute
STAND_TOP = (1.12, 0.17, 0.60, 0.65)      # half length (about the flute's middle), half depth (about its line), z0, z1
STAND_LEG_X = 0.92                        # the legs' centres from the middle
STAND_LEG = (0.05, 0.15)                  # half thickness (x), half depth (y)
STAND_FOOT = (0.09, 0.19, 0.06)           # the feet: half x, half y, height (from z -STAND_SINK)
STAND_SINK = 0.012                        # the feet reach this far under the floor
STAND_APRON = (0.035, 0.07, 0.06)         # inset from the top's edge, height under the top, thickness
STAND_POST_X = 0.6                        # the cradles' x from the flute's middle (inside the flute's carved bands)
STAND_HEAD = (0.045, 0.10, 0.10)          # cradle: half x, half y, height over the top
STAND_NOTCH = 0.006                       # the notch is this much wider than the flute's radius


def stand_bm(FP):
    """The black-lacquer flute stand in the set frame: table top, end-slab legs on cloud feet (sunk STAND_SINK into the
    floor), front and back aprons under the top, two notched cradles on the top."""
    bm = bmesh.new()
    cx, cy = FP.FLUTE_X, FP.FLUTE_Y
    hl, hd, t0, t1 = STAND_TOP
    bm_box(bm, (cx - hl, cy - hd, t0), (cx + hl, cy + hd, t1))
    lx, ly = STAND_LEG
    fx, fy, fh = STAND_FOOT
    for s in (-1.0, 1.0):
        x = cx + s * STAND_LEG_X
        bm_box(bm, (x - lx, cy - ly, fh - STAND_SINK - 0.01), (x + lx, cy + ly, t0 + 0.01))
        # cloud foot: a low block with an arch cut under it (a profile in y, z extruded along x)
        prof = [(cy - fy, -STAND_SINK), (cy - fy * 0.55, -STAND_SINK)]
        for k in range(1, 8):
            a = math.pi * k / 8
            prof.append((cy - fy * 0.55 * math.cos(a), -STAND_SINK + 0.03 * math.sin(a)))
        prof += [(cy + fy * 0.55, -STAND_SINK), (cy + fy, -STAND_SINK), (cy + fy * 0.9, fh - STAND_SINK),
                 (cy - fy * 0.9, fh - STAND_SINK)]
        a_ = [bm.verts.new((x - fx, yy, zz)) for yy, zz in prof]
        b_ = [bm.verts.new((x + fx, yy, zz)) for yy, zz in prof]
        n = len(prof)
        bm.faces.new(a_)
        bm.faces.new(list(reversed(b_)))
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a_[j], a_[i], b_[i], b_[j]))
    ins, ah, at = STAND_APRON
    for s in (-1.0, 1.0):
        y = cy + s * (hd - ins - at / 2)
        bm_box(bm, (cx - STAND_LEG_X + lx - 0.01, y - at / 2, t0 - ah),
               (cx + STAND_LEG_X - lx + 0.01, y + at / 2, t0 + 0.01))
    r = FP.XR + STAND_NOTCH
    hx, hy, hh = STAND_HEAD
    for s in (-1.0, 1.0):
        x = cx + s * STAND_POST_X
        top = t1 + hh
        prof = [(cy - hy, t1 - 0.01), (cy + hy, t1 - 0.01), (cy + hy, top)]
        for k in range(13):                      # the notch, from its +y rim down round to its -y rim
            a = math.pi * k / 12
            prof.append((cy + r * math.cos(a), top - r * math.sin(a)))
        prof.append((cy - hy, top))
        a_ = [bm.verts.new((x - hx, yy, zz)) for yy, zz in prof]
        b_ = [bm.verts.new((x + hx, yy, zz)) for yy, zz in prof]
        n = len(prof)
        bm.faces.new(a_)
        bm.faces.new(list(reversed(b_)))
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a_[j], a_[i], b_[i], b_[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def flute_frame(ting, mirror_stand):
    """The set frame -> the pavilion's frame: on its floor (arch_floor_z), FLUTE_OFFSET from its middle toward the
    mirror, its front (-y) facing the mirror, scaled FLUTE_SCALE. Returns (matrix, the mirror's plan direction)."""
    T = local_matrix(ting, None).inverted() @ local_matrix(mirror_stand, None)
    d = T.translation.xy.normalized()
    az = math.atan2(d.y, d.x)
    floor = float(ting.get("arch_floor_z", 0.45))
    m = Matrix.Translation((d.x * FLUTE_OFFSET, d.y * FLUTE_OFFSET, floor)) @ \
        Matrix.Rotation(az + math.pi / 2, 4, 'Z') @ Matrix.Diagonal((FLUTE_SCALE, FLUTE_SCALE, FLUTE_SCALE, 1.0))
    return m, az


def flute_set(coll, root, ting, names=FLUTE_NAMES, log=None):
    """The jade flute on its lacquer stand in the pond pavilion, facing the mirror (see the block comment above):
    Empty names[0] under ``ting`` and the stand, flute and tassel meshes (names[1:]) under it, all tagged sect_item
    FLUTE_ITEM. Returns the Empty."""
    from sect.lib import flute_props as FP
    m_set, az = flute_frame(ting, bpy.data.objects[FLUTE_MIRROR])
    stand = stand_bm(FP)
    stand.verts.index_update()
    sv = [v.co.copy() for v in stand.verts]
    sp = [tuple(v.index for v in f.verts) for f in stand.faces]
    support = bvh_of([(sv, sp)])
    m_fl, rest = FP.flute_matrix(support)                  # it rests in the two cradles
    xiao = FP.flute_bm()
    bmesh.ops.transform(xiao, matrix=m_fl, verts=xiao.verts)
    tassel, low, _tc = FP.tassel_bm(m_fl, support)
    em = U.empty(names[0], coll, parent=ting, matrix=m_set, display_size=0.5)
    em["sect_item"] = FLUTE_ITEM
    mesh_object(names[1], stand, coll, list(STAND_MATS), em, smooth=math.radians(35), tag=FLUTE_ITEM)
    mesh_object(names[2], xiao, coll, [FP.JADE, FP.HOLE], em, smooth=math.radians(40), tag=FLUTE_ITEM)
    mesh_object(names[3], tassel, coll, [FP.TRIM, FP.JADE], em, smooth=math.radians(50), tag=FLUTE_ITEM)
    if log:
        log("flute: on the pond pavilion's floor %.2f m toward the mirror (plan %.1f deg), scale %.2f; rests on x %s; "
            "tassel down to z %.3f (set frame)" % (FLUTE_OFFSET, math.degrees(az), FLUTE_SCALE, rest, low))
    return em


# ================================================================ mirror: 思過崖 on the cliff behind the mirror
# Placement (mirror.root frame; the 217 hold as the site frames it, chase.cam at 204 turned 4 / -3 deg): the cliff of
# world.range 277 m off, right of and above the mirror, where the range shows a bare grey face between its pines
# (screen about x 900-950, y 100-230 of 1600 x 900, clear of the About panel and of the mirror's crest). SIGUOYA_AT is
# a point near the rock there; the face's normal SIGUOYA_AZ (plan, atan2 in the mirror's frame) lies between the
# rock's own (-117..-127 deg) and the hold's direction (-104): 12 deg off square to the hold. The rock there is
# fluted (the range's columns stand +-2-3 m out of their mean plane), so the dressed face stands SIGUOYA_PROUD in
# front of the rock's most forward point under it and its sides fall back into the rock, widening as a buttress does,
# to SIGUOYA_BURY behind its deepest point. The characters: KaiTi, SIGUOYA_CELL tall cells top to bottom with
# SIGUOYA_GAP between them, cut SIGUOYA_CUT deep; the walls and the floor of every stroke are ink, so the stroke reads
# black on pale stone and no face is left under it (round 12's flicker rule).
SIGUOYA = "mirror.siguoya"
SIGUOYA_ITEM = "cliff_of_reflection"
SIGUOYA_TEXT = "思過崖"
SIGUOYA_AT = (62.0, 208.2, 16.0)          # mirror.root frame: the face's centre (on the rock, before standing out)
SIGUOYA_AZ = math.radians(-112.0)        # the face's normal, plan direction in mirror.root's frame
SIGUOYA_CELL = 6.0                        # m: a character's cell (its ink 4.5-5 m)
SIGUOYA_GAP = 0.6                         # m between cells
SIGUOYA_MARGIN = (1.0, 1.2)               # m: ink to the face's edge, across and top / bottom
SIGUOYA_PROUD = 0.25                      # m: the face in front of the rock's most forward point under it
SIGUOYA_BURY = 1.5                        # m: the sides reach this far behind the rock's deepest point
SIGUOYA_FLARE = 0.3                       # m out per m back: the sides widen into the rock
SIGUOYA_CUT = 0.25                        # m: the strokes' depth
SIGUOYA_RES = 3                           # font curve resolution
SIGUOYA_FACE = M.variant("siguoya_face", "stone_grey", c1="#b3ac9e", c2="#9d9588", speck="#6e675c",
                         light="#c9c2b5", light_amt=0.3, rough=(0.7, 0.9), bump=0.12)   # dressed, weathered pale stone
SIGUOYA_INK = "ink"
SIGUOYA_ROCK = "rock_cliff"               # the sides (the range's own rock where none is found under the face)
# trees cleared round it (the face's frame: x across, z up, d out of the face toward the viewer): every world.range
# face whose centre lies within CLEAR_BOX, or in the hold's line of sight to the face (the line from SIGUOYA_EYE
# through it meets the face's plane within CLEAR_SIGHT of the face's outline, in front of the face)
SIGUOYA_EYE = (-4.92, -61.82, 19.26)      # mirror.root frame: the 217 hold's camera (as the site frames it)
CLEAR_BOX = (9.0, 20.0, 6.0, 20.0, 32.0)   # m: beyond the sides, below, above; behind and in front of the face
CLEAR_SIGHT = 3.0                         # m
CLEAR_ATTRS = ("scenery_forest", "scenery_grove", "scenery_cliff", "scenery_cliff_dense", "scenery_cliff_wall",
               "scenery_crown", "world_veg")


def siguoya_axes():
    """(n, right, up) of the dressed face in mirror.root's frame: n out of the face (toward the viewer), right the
    viewer's right, up +z."""
    n = Vector((math.cos(SIGUOYA_AZ), math.sin(SIGUOYA_AZ), 0.0))
    return n, Vector((-n.y, n.x, 0.0)), Vector((0.0, 0.0, 1.0))


def siguoya_size():
    """(half width, half height) of the dressed face."""
    nch = len(SIGUOYA_TEXT)
    h = nch * SIGUOYA_CELL + (nch - 1) * SIGUOYA_GAP + 2 * SIGUOYA_MARGIN[1]
    w = SIGUOYA_CELL + 2 * SIGUOYA_MARGIN[0]
    return 0.5 * w, 0.5 * h


def range_bvh(rng, to_root):
    """BVH of world.range in mirror.root's frame (to_root: world -> mirror.root), with its faces' material names."""
    me = rng.data
    Mr = to_root @ world_matrix(rng)
    bvh = BVHTree.FromPolygons([Mr @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    mats = [s.material.name if s.material else None for s in rng.material_slots]
    return bvh, [mats[p.material_index] if p.material_index < len(mats) else None for p in me.polygons]


def siguoya_frame(rng, root):
    """The dressed face's frame (face -> mirror.root: x right, y into the rock, z up, origin at the face's centre on
    its front plane) and what the rock under it is: dict(matrix, front, deep, rock_mat, samples)."""
    to_root = world_matrix(root).inverted()
    bvh, fmats = range_bvh(rng, to_root)
    n, right, up = siguoya_axes()
    hw, hh = siguoya_size()
    at = Vector(SIGUOYA_AT)
    ds, mats = [], {}
    grid = 0.5
    nu, nv = int(2 * (hw + 0.6) / grid) + 1, int(2 * (hh + 0.6) / grid) + 1
    for i in range(nu):
        for j in range(nv):
            u = -hw - 0.6 + i * grid
            v = -hh - 0.6 + j * grid
            p0 = at + right * u + up * v + n * 30.0
            hit = bvh.ray_cast(p0, -n, 80.0)
            if hit[0] is None:
                raise RuntimeError("siguoya: no rock under the face at (%.1f, %.1f)" % (u, v))
            ds.append((hit[0] - at).dot(n))
            mats[fmats[hit[2]]] = mats.get(fmats[hit[2]], 0) + 1
    front = max(ds) + SIGUOYA_PROUD
    deep = min(ds)
    o = at + n * front
    R = Matrix((right, -n, up)).transposed()          # columns: x = right, y = into the rock (-n), z = up
    m = Matrix.Translation(o) @ R.to_4x4()
    rock = max(mats.items(), key=lambda kv: kv[1])[0] or SIGUOYA_ROCK

    def rock_at(x, z):
        """Depth behind the face's plane (face frame y) of the rock's surface at (x, z), or None (no rock within
        28 m behind it)."""
        p = o + right * x + up * z + n * 2.0
        hit = bvh.ray_cast(p, -n, 30.0)
        return None if hit[0] is None else (o - hit[0]).dot(n)
    return dict(matrix=m, front=front, deep=deep, rock_mat=rock, samples=len(ds),
                spread=max(ds) - min(ds), rock_at=rock_at)


def _glyph_regions(FONT):
    """[(polygon [(x, z)], 'ink')] of the characters on the face (face frame, x right, z up), top to bottom, centred
    in their cells; and the cells' (x0, x1, z0, z1) ink boxes."""
    from sect.lib import props as P
    regions, boxes = [], []
    nch = len(SIGUOYA_TEXT)
    total = nch * SIGUOYA_CELL + (nch - 1) * SIGUOYA_GAP
    for k, ch in enumerate(SIGUOYA_TEXT):
        me = P._text_mesh(ch, SIGUOYA_CELL, SIGUOYA_RES, font=FONT)
        if not len(me.polygons):
            raise RuntimeError("siguoya: glyph %r has no faces (font %s)" % (ch, FONT))
        zc = total / 2 - SIGUOYA_CELL / 2 - k * (SIGUOYA_CELL + SIGUOYA_GAP)
        co = [(v.co.x, v.co.y) for v in me.vertices]
        xs, ys = [c[0] for c in co], [c[1] for c in co]
        boxes.append((min(xs), max(xs), zc + min(ys), zc + max(ys)))
        for p in me.polygons:
            regions.append(([(co[i][0], zc + co[i][1]) for i in p.vertices], "ink"))
    return regions, boxes


SIGUOYA_CORNERS = (1.1, 1.6, 0.8, 1.3)   # m: the corners' radii (bottom right, top right, top left, bottom left)
SIGUOYA_WANDER = (0.3, 0.32)              # m, 1/m: how far the dressed edge wanders in and out, and how fast


def _outline(hw, hh, corners=SIGUOYA_CORNERS, seed=7):
    """The dressed face's outline (x, z), counter-clockwise seen from the front: a rectangle with unequal rounded
    corners whose edges wander in and out (rough-dressed, not a board)."""
    pts = []
    cs = [(hw, -hh, -math.pi / 2), (hw, hh, 0.0), (-hw, hh, math.pi / 2), (-hw, -hh, math.pi)]
    centres = []
    for (x, z, a0), r in zip(cs, corners):
        sx = -1.0 if x > 0 else 1.0
        sz = -1.0 if z > 0 else 1.0
        centres.append((x + sx * r, z + sz * r, a0, r))
    for (cx, cz, a0, r), (nx, nz, _a, nr) in zip(centres, centres[1:] + centres[:1]):
        for k in range(7):
            a = a0 + (math.pi / 2) * k / 6
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
        ex, ez = cx + r * math.cos(a0 + math.pi / 2), cz + r * math.sin(a0 + math.pi / 2)
        fx, fz = nx + nr * math.cos(a0 + math.pi / 2), nz + nr * math.sin(a0 + math.pi / 2)
        ln = math.hypot(fx - ex, fz - ez)
        m = max(1, int(ln / 0.8))
        for k in range(1, m):
            t = k / m
            pts.append((ex + (fx - ex) * t, ez + (fz - ez) * t))
    out = []
    amp, freq = SIGUOYA_WANDER
    n = len(pts)
    for i, (x, z) in enumerate(pts):
        (xa, za), (xb, zb) = pts[i - 1], pts[(i + 1) % n]
        tx, tz = xb - xa, zb - za
        ln = math.hypot(tx, tz) or 1.0
        w = amp * U.noise3((x * freq, z * freq, 0.0), 1.0, seed=seed)
        out.append((x + tz / ln * w, z - tx / ln * w))
    return out


def siguoya_bm(fr, FONT):
    """The dressed face with the characters cut into it, in the face frame (fr: siguoya_frame). Materials: 0 face,
    1 rock (its sides), 2 ink. Returns (bm, info)."""
    from sect.lib import props as P
    hw, hh = siguoya_size()
    outline = _outline(hw, hh)
    depth = fr["front"] - fr["deep"] + SIGUOYA_BURY
    rock_at = fr["rock_at"]
    bm = bmesh.new()
    front = [bm.verts.new((x, 0.0, z)) for x, z in outline]
    face = bm.faces.new(front)
    face.material_index = 0
    # the sides: a short chamfer, then back into the rock, widening
    rings = [front]
    n = len(outline)
    outward = []
    for i in range(n):
        (xa, za), (xb, zb) = outline[i - 1], outline[(i + 1) % n]
        tx, tz = xb - xa, zb - za
        ln = math.hypot(tx, tz) or 1.0
        outward.append((tz / ln, -tx / ln))               # counter-clockwise outline: (tz, -tx) points out
    deep, flare = [], []
    for (x, z), (ox, oz) in zip(outline, outward):
        # where the flared side meets the rock, then BURY past it (at the jittered place the end ring will have); less
        # flare where the flared point finds no rock behind it (past the rock's edge), none at the last
        jit = 1.0 + 0.25 * U.noise3((x * 0.4, z * 0.4, 0.2), 1.0, seed=11)
        for f in (1.0, 0.6, 0.3, 0.0):
            d = 0.5
            hit = True
            for _ in range(4):
                g = (0.2 + SIGUOYA_FLARE * f * d) * jit
                r = rock_at(x + ox * g, z + oz * g)
                hit = r is not None
                d = max(0.5, r if hit else depth) + SIGUOYA_BURY
            if hit and d <= depth:                         # not out into a gully beside the face
                break
        deep.append(min(d, depth + 6.0))
        flare.append(f)
    for k, (dy0, grow0) in enumerate(((0.12, 0.10), (0.5, 0.2), (None, None))):
        ring = []
        for (x, z), (ox, oz), d, f in zip(outline, outward, deep, flare):
            dy = d if dy0 is None else dy0
            grow = 0.2 + SIGUOYA_FLARE * f * d if grow0 is None else grow0
            jit = 1.0 + 0.25 * U.noise3((x * 0.4, z * 0.4, 0.1 * k), 1.0, seed=11)
            ring.append(bm.verts.new((x + ox * grow * jit, dy, z + oz * grow * jit)))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            f = bm.faces.new((a[i], b[i], b[j], a[j]))
            f.material_index = 1
    # the back: a fan to a point behind the deepest of the ring (inside the rock), so the cap need not be flat
    tip = bm.verts.new((0.0, max(deep) + 0.5, 0.0))
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((rings[-1][j], rings[-1][i], tip))
        f.material_index = 1
    bm.normal_update()
    if face.normal.y > 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.normal_update()
    # the characters: holes in the face, walls and floors of ink
    regions, boxes = _glyph_regions(FONT)
    got = P._imprint(bm, [face], lambda co: (co.x, co.z), lambda x, z: Vector((x, 0.0, z)), regions, holes=True)
    holes = got.get("ink", [])
    if not holes:
        raise RuntimeError("siguoya: no character cut into the face")
    key = lambda p: (round(p.x, 7), round(p.z, 7))               # noqa: E731
    back_of = {}

    def bv(p):
        k = key(p)
        w = back_of.get(k)
        if w is None:
            w = back_of[k] = bm.verts.new((p.x, SIGUOYA_CUT, p.z))
        return w
    front_v = {key(v.co): v for v in bm.verts if abs(v.co.y) < 1e-6}
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
        f.smooth = False
    info = dict(rim_edges=len(rim), floors=floors, holes=len(holes), boxes=boxes, depth=depth,
                front_verts=len(front_v))
    return bm, info


def font_path():
    """KaiTi as a path both os.path and bpy.data.fonts.load accept (on the render box the fonts are mirrored at
    '/C:/Windows/Fonts/' and Blender runs in '/')."""
    import os
    for p in (U.FONT_KAITI, U.FONT_YAHEI):
        for c in (p, "/" + p if p and not p.startswith("/") else None):
            if c and os.path.isfile(c):
                return os.path.abspath(c)
    return U.FONT_KAITI


def siguoya(coll, root, name=SIGUOYA, log=None):
    """思過崖 on the cliff behind the mirror (see the block comment above): mesh ``name`` under ``root``, tagged
    sect_item SIGUOYA_ITEM. Needs world.range in the file. Returns the object."""
    rng = bpy.data.objects.get("world.range")
    if rng is None:
        raise RuntimeError("siguoya: world.range not found")
    fr = siguoya_frame(rng, root)
    bm, info = siguoya_bm(fr, font_path())
    rock = bpy.data.materials.get(fr["rock_mat"]) or SIGUOYA_ROCK      # the range's own material, as it is
    ob = mesh_object(name, bm, coll, [SIGUOYA_FACE, rock, SIGUOYA_INK], root, matrix=fr["matrix"],
                     smooth=False, tag=SIGUOYA_ITEM)
    ob["front"] = round(fr["front"], 4)
    ob["deep"] = round(fr["deep"], 4)
    if log:
        log("siguoya: %s, face %.2f m in front of SIGUOYA_AT (rock %.2f..%.2f m about it, %d samples, spread %.2f m), "
            "sides back %.2f m, rock material %s; %d rim edges, %d floor triangles; ink boxes %s" % (
                SIGUOYA_TEXT, fr["front"], fr["deep"], fr["front"] - SIGUOYA_PROUD, fr["samples"], fr["spread"],
                info["depth"], fr["rock_mat"], info["rim_edges"], info["floors"],
                ["%.2f..%.2f x %.2f..%.2f" % b for b in info["boxes"]]))
    return ob


def siguoya_clear_faces(rng, root, face_matrix):
    """Indices of world.range's faces to clear of trees round the dressed face (CLEAR_BOX, CLEAR_SIGHT); face_matrix:
    the face frame -> mirror.root (siguoya_frame()['matrix'])."""
    import numpy as np
    me = rng.data
    to_face = face_matrix.inverted() @ world_matrix(root).inverted() @ world_matrix(rng)
    n = len(me.polygons)
    c = np.empty(n * 3)
    me.polygons.foreach_get("center", c)
    c = c.reshape(n, 3)
    T = np.array(to_face)
    f = c @ T[:3, :3].T + T[:3, 3]                     # face frame: x right, y into the rock, z up
    hw, hh = siguoya_size()
    sx, below, above, back, front = CLEAR_BOX
    box = (np.abs(f[:, 0]) <= hw + sx) & (f[:, 2] >= -hh - below) & (f[:, 2] <= hh + above) & \
        (f[:, 1] >= -front) & (f[:, 1] <= back)
    # in the hold's line of sight: the line from the eye through the face centre meets the plane y = 0 inside the
    # outline grown by CLEAR_SIGHT, with the centre in front of the plane (between it and the eye)
    E = np.array(face_matrix.inverted() @ Vector(SIGUOYA_EYE))
    d = f - E
    with np.errstate(divide="ignore", invalid="ignore"):
        t = -E[1] / d[:, 1]
    q = E + d * t[:, None]
    sight = (f[:, 1] < 0.0) & (t > 1.0) & (np.abs(q[:, 0]) <= hw + CLEAR_SIGHT) & \
        (np.abs(q[:, 2]) <= hh + CLEAR_SIGHT)
    return np.nonzero(box | sight)[0]


def siguoya_clear(rng, root, face_matrix, log=None):
    """Zero CLEAR_ATTRS on the faces siguoya_clear_faces picks. Returns {attribute: faces changed}."""
    import numpy as np
    idx = siguoya_clear_faces(rng, root, face_matrix)
    me = rng.data
    out = {}
    for a in CLEAR_ATTRS:
        at = me.attributes.get(a)
        if at is None or at.domain != 'FACE':
            continue
        v = np.empty(len(me.polygons), np.float32)
        at.data.foreach_get("value", v)
        was = int((v[idx] > 0.5).sum())
        v[idx] = 0.0
        at.data.foreach_set("value", v)
        out[a] = was
    me.update()
    if log:
        log("siguoya: tree masks cleared on %d range faces (%s faces had trees)" % (
            len(idx), ", ".join("%s %d" % kv for kv in out.items())))
    return out


# ================================================================ shared shapes (bmesh)

def bm_lathe(bm, rows, segs, matrix, mat=0, smooth=True, phase=0.0):
    """Closed solid of revolution about local z: rows [(r, z)] bottom to top; r 0 on the first / last row is a pole,
    otherwise that end is capped. ``matrix`` places it."""
    rings = []
    for r, z in rows:
        if r <= 1e-9:
            rings.append([bm.verts.new(matrix @ Vector((0.0, 0.0, z)))])
        else:
            rings.append([bm.verts.new(matrix @ Vector((r * math.cos(phase + 2 * math.pi * k / segs),
                                                         r * math.sin(phase + 2 * math.pi * k / segs), z)))
                          for k in range(segs)])
    faces = []
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(segs):
            k2 = (k + 1) % segs
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                faces.append(bm.faces.new((a[0], b[k2], b[k])))
            elif len(b) == 1:
                faces.append(bm.faces.new((a[k], a[k2], b[0])))
            else:
                faces.append(bm.faces.new((a[k], a[k2], b[k2], b[k])))
    if len(rings[0]) > 1:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
    if len(rings[-1]) > 1:
        faces.append(bm.faces.new(rings[-1]))
    for f in faces:
        f.material_index = mat
        f.smooth = smooth
    return faces


def frame_rings(secs, prof):
    """Cross-section rings along a path: secs [(centre, tangent, width dir, half width, half thickness)], prof the
    section's corners as (fraction of the half width, fraction of the half thickness)."""
    out = []
    for p, t, e, hw, ht in secs:
        f = t.cross(e).normalized()
        out.append([p + e * (fx * hw) + f * (fy * ht) for fx, fy in prof])
    return out


def bm_loft(bm, rings, mat=0, smooth=True, caps=True):
    vs = [[bm.verts.new(p) for p in ring] for ring in rings]
    n = len(rings[0])
    faces = []
    for a, b in zip(vs[:-1], vs[1:]):
        for i in range(n):
            j = (i + 1) % n
            faces.append(bm.faces.new((a[i], a[j], b[j], b[i])))
    if caps:
        faces.append(bm.faces.new(list(reversed(vs[0]))))
        faces.append(bm.faces.new(vs[-1]))
    for f in faces:
        f.material_index = mat
        f.smooth = smooth
    return faces


def bm_tube(bm, pts, radius, sides=8, mat=0, smooth=True):
    """Closed tube along pts (Vectors), parallel-transport frames, capped."""
    n = len(pts)
    tans = []
    for i in range(n):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        tans.append((b - a).normalized())
    ref = Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((1, 0, 0))
    u = tans[0].cross(ref).normalized()
    rings = []
    for p, t in zip(pts, tans):
        u = (u - t * u.dot(t)).normalized()
        w = t.cross(u)
        rings.append([p + (u * math.cos(2 * math.pi * k / sides) + w * math.sin(2 * math.pi * k / sides)) * radius
                      for k in range(sides)])
    return bm_loft(bm, rings, mat, smooth)


def frame_at(origin, z_axis, x_hint=Vector((1.0, 0.0, 0.0))):
    """4x4 matrix: origin, local z along ``z_axis``, local x as near ``x_hint`` as it can be."""
    z = Vector(z_axis).normalized()
    x = Vector(x_hint) - z * Vector(x_hint).dot(z)
    if x.length < 1e-6:
        x = Vector((0.0, 1.0, 0.0)) - z * z.y
    x.normalize()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


# ================================================================ summit: the condor's crag and the golden-bell ribbon
# Return of the Condor Heroes ends on Mount Hua under the moon (ch. 40 華山之巔): Yang Guo and Xiaolongnü leave with
# the condor. Her white silk ribbon with its golden bells (金鈴索) lies coiled on the condor's rock beside it, one tail
# run off the coil over the rock's edge toward the hold, a gold bell hanging from it. coil(): a flat spiral of silk
# (COIL_TURNS turns, COIL_W wide, laid flat on the rock: every section sits on the highest rock under its width, so
# nothing sinks in), placed on the capstone where its footprint is most level, clear of the bird's feet and on the
# hold's side of the bird; the tail runs straight to the rock's edge, over it and down the rock's face, ending in a
# bell (gold ball, band and slot, a cap where the silk gathers). Objects: Empty 'summit.ribbon' under summit.root, its
# meshes 'summit.ribbon_silk' (the silk) and 'summit.ribbon_bells' (the bell), tagged sect_item RIBBON_ITEM.
RIBBON = "summit.ribbon"
RIBBON_SILK = "summit.ribbon_silk"
RIBBON_BELLS = "summit.ribbon_bells"
RIBBON_NAMES = (RIBBON, RIBBON_SILK, RIBBON_BELLS)
RIBBON_ITEM = "golden_bell_ribbon"
RIBBON_MATS = ("abode_ribbon_silk", "gold", "lacquer_black")   # the abode's silk (sect/areas/abode.py RIBBON_MAT)
SUMMIT_EYE = (-67.34, -31.15, 8.63)        # summit.root frame: the 1647 hold's camera
COIL_W, COIL_T = 0.16, 0.02                # m: the silk's width and thickness (square edges, as round 12's tails)
COIL_R0, COIL_GAP, COIL_TURNS = 0.1, 0.022, 1.75
COIL_DS = 0.045                            # m between sections
COIL_LIFT = 0.012                          # m: the silk's underside over the highest rock under it
COIL_RING = (0.5, 2.2)                     # m from the bird's feet: where the coil's centre may go
COIL_LEVEL = 0.35                          # m: the most the rock may rise and fall under the coil
TAIL_HANG = 0.6                            # m the tail hangs below the rock's edge
BELL_R = 0.1
_SECT = ((1.0, -1.0), (1.0, 1.0), (0.33, 1.0), (-0.33, 1.0), (-1.0, 1.0), (-1.0, -1.0), (-0.33, -1.0), (0.33, -1.0))


def _rock_sampler(rocks, root):
    """(bvh, owners) of the rock objects in root's frame; down(x, y, z0) -> (z, normal, owner) or None."""
    parts, owner = [], []
    for ob in rocks:
        vs, ps = mesh_tris(ob, world_matrix(root).inverted())
        parts.append((vs, ps))
        owner += [ob.name] * len(ps)
    bvh = bvh_of(parts)

    def down(x, y, z0):
        h = bvh.ray_cast(Vector((x, y, z0)), Vector((0.0, 0.0, -1.0)), 40.0)
        if h[0] is None:
            return None
        return h[0].z, h[1], owner[h[2]]
    return bvh, down


def _coil_radius():
    return COIL_R0 + COIL_TURNS * (COIL_W + COIL_GAP) + COIL_W * 0.5


def coil_site(cap, bird, rocks, root):
    """Where the coil's centre goes (summit.root frame): the most level spot in COIL_RING round the bird's feet whose
    whole footprint lies on the capstone or the crag's top (not on its small boulders), clear of the bird (the parts
    of it lower than 0.3 m over the coil), the hold's side preferred. Returns (centre Vector (z = the highest rock under it), the plan direction to the hold, info)."""
    bvh, down = _rock_sampler(rocks, root)
    Mb = world_matrix(root).inverted() @ world_matrix(bird)
    feet = Mb.translation
    bz = [Mb @ v.co for v in bird.data.vertices]
    eye = Vector(SUMMIT_EYE)
    to_eye = Vector((eye.x - feet.x, eye.y - feet.y, 0.0)).normalized()
    Rc = _coil_radius()
    z0 = feet.z + 6.0
    best = None
    allowed = {cap.name} | {o.name for o in rocks if o.name.endswith("condor_crag")}
    why = {}
    for ri in range(8):
        rr = COIL_RING[0] + (COIL_RING[1] - COIL_RING[0]) * ri / 7
        for ai in range(36):
            a = 2 * math.pi * ai / 36
            c = Vector((feet.x + rr * math.cos(a), feet.y + rr * math.sin(a), 0.0))
            zs, ok = [], True
            for rk in (0.0, 0.5 * Rc, Rc + 0.04):
                for k in range(16 if rk else 1):
                    t = 2 * math.pi * k / 16
                    h = down(c.x + rk * math.cos(t), c.y + rk * math.sin(t), z0)
                    if h is None or h[2] not in allowed or h[1].z < 0.55:
                        ok = False
                        why["off the rock or steep"] = why.get("off the rock or steep", 0) + 1
                        break
                    zs.append(h[0])
                if not ok:
                    break
            if not ok:
                continue
            if max(zs) - min(zs) > COIL_LEVEL:
                why["not level"] = why.get("not level", 0) + 1
                continue
            near = [p for p in bz if p.z < max(zs) + 0.3]
            clear = (min(((p.x - c.x) ** 2 + (p.y - c.y) ** 2) ** 0.5 for p in near) - Rc) if near else 9.0
            if clear < 0.08:
                why["under the bird"] = why.get("under the bird", 0) + 1
                continue
            side = (c - Vector((feet.x, feet.y, 0.0))).normalized().dot(to_eye)
            score = (max(zs) - min(zs)) - 0.25 * side
            if best is None or score < best[0]:
                best = (score, Vector((c.x, c.y, max(zs))), dict(ring=rr, angle=math.degrees(a), level=max(zs) - min(zs),
                                                                  clear=clear, side=side))
    if best is None:
        raise RuntimeError("ribbon: no level spot on %s for a %.2f m coil clear of the bird (%s)" % (
            cap.name, Rc, ", ".join("%s %d" % kv for kv in sorted(why.items()))))
    return best[1], to_eye, best[2]


def coil_path(centre, to_eye, bvh, down, edge_dir=None):
    """The silk's sections [(centre, tangent, width dir, half width, half thickness)] in summit.root's frame: the flat
    spiral (inner end first) and the tail over the edge, and the tail's last direction."""
    hw, ht = 0.5 * COIL_W, 0.5 * COIL_T
    pitch = COIL_W + COIL_GAP
    th_end = 2 * math.pi * COIL_TURNS
    # start the spiral so its outer end leaves toward the hold
    a_end = math.atan2(to_eye.y, to_eye.x) - math.pi / 2
    a0 = a_end - th_end
    pts = []
    th = 0.0
    while th <= th_end + 1e-9:
        r = COIL_R0 + pitch * th / (2 * math.pi)
        a = a0 + th
        pts.append(Vector((centre.x + r * math.cos(a), centre.y + r * math.sin(a), 0.0)))
        th += COIL_DS / max(r, 0.05)
    # the tail: straight on toward the hold from the spiral's end, to the edge
    D = (edge_dir or to_eye).copy()
    D.z = 0.0
    D.normalize()
    p = pts[-1].copy()
    z_hi = centre.z + 4.0
    prev = None
    run = []
    for k in range(200):
        q = p + D * (COIL_DS * (k + 1))
        h = down(q.x, q.y, z_hi)
        if h is None or h[1].z < 0.5 or (prev is not None and h[0] < prev - 0.12):
            break
        prev = h[0]
        run.append(q)
    pts += run
    edge = pts[-1].copy()

    def top(q):
        """Highest rock under a section's width (and a little round it)."""
        e = Vector((-D.y, D.x, 0.0))
        zs = []
        for s in (-1.0, -0.5, 0.0, 0.5, 1.0):
            for dd in (-0.02, 0.02):
                h = down(q.x + e.x * s * hw + D.x * dd, q.y + e.y * s * hw + D.y * dd, z_hi)
                if h is not None:
                    zs.append(h[0])
        return max(zs) if zs else None
    # heights on the coil and the run: every section on the highest rock under it (the whole width), running max of 3
    flat = []
    for i, q in enumerate(pts):
        if i < len(pts) - len(run):
            r = (q - Vector((centre.x, centre.y, 0.0))).length
            e = (q - Vector((centre.x, centre.y, 0.0))).normalized()
            zs = []
            for s in (-1.0, -0.5, 0.0, 0.5, 1.0):
                h = down(q.x + e.x * s * hw, q.y + e.y * s * hw, z_hi)
                if h is not None:
                    zs.append(h[0])
            flat.append(max(zs) if zs else centre.z)
            _ = r
        else:
            flat.append(top(q) or flat[-1])
    zz = [max(flat[max(0, i - 1):i + 2]) + ht + COIL_LIFT for i in range(len(flat))]
    path = [Vector((q.x, q.y, z)) for q, z in zip(pts, zz)]
    # over the edge and down: the tail hangs plumb from the lip, as far out as the rock's face below it reaches
    # (the front-most rock along D from the lip down past the bell) plus the bell's radius and a little air
    zt = zz[-1]
    e_side = Vector((-D.y, D.x, 0.0))
    reach = 0.0
    k = 0
    while True:
        z = zt - 0.04 * k
        if z < zt - TAIL_HANG - 2.0 * BELL_R - 0.2:
            break
        for s in (-1.5, -1.0, 0.0, 1.0, 1.5):
            o = edge + D * 4.0 + e_side * (s * max(hw, BELL_R))
            o.z = z
            hit = bvh.ray_cast(o, -D, 8.0)
            if hit[0] is not None:
                reach = max(reach, (hit[0] - edge).dot(D))
        k += 1
    hang_d = reach + BELL_R + 0.03
    out_pts = []
    for k in range(1, 60):
        z = zt - 0.05 * k
        if z < zt - TAIL_HANG:
            break
        out_pts.append(edge + D * hang_d + Vector((0.0, 0.0, z - edge.z)))
    # round the lip: a short arc from the last flat section to the first hanging one
    if out_pts:
        a, b = path[-1], out_pts[0]
        c = Vector((b.x, b.y, a.z))
        arc = [a.lerp(c, t) * (1 - t) + c.lerp(b, t) * t for t in (0.35, 0.65)]
        path += arc + out_pts
    secs = []
    e = None
    n = len(path)
    for i, q in enumerate(path):
        t = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
        # the silk's width stays level (a flat ribbon laid on the rock, hanging plumb off it): across the plan tangent
        h = Vector((-t.y, t.x, 0.0))
        if h.length > 1e-3:
            h.normalize()
            if e is not None and h.dot(e) < 0.0:
                h = -h
            if e is None and h.dot(q - Vector((centre.x, centre.y, q.z))) < 0.0:
                h = -h
            e = h
        e = (e - t * e.dot(t)).normalized()
        s_end = sum((path[j + 1] - path[j]).length for j in range(i, n - 1))
        w = hw * (0.35 + 0.65 * min(1.0, s_end / 0.25))           # gathers into the bell's cap
        secs.append((q, t, e, w, ht))
    return secs, D, dict(edge=edge, run=len(run), hang=len(out_pts))


def bell_bm(top, D):
    """The golden bell hanging from ``top`` (the silk's end), in summit.root's frame: a gold cap where the silk
    gathers, the ball with a raised band, a dark slot across its lower half facing D. Materials 0 gold, 1 slot."""
    bm = bmesh.new()
    z = Vector((0.0, 0.0, 1.0))
    cap = frame_at(top + Vector((0.0, 0.0, 0.02)), -z, D)
    bm_lathe(bm, [(0.0, -0.02), (0.03, -0.015), (0.045, 0.02), (0.05, 0.06), (0.04, 0.085), (0.0, 0.09)], 12, cap)
    bc = top - Vector((0.0, 0.0, 0.07 + BELL_R))
    ball = frame_at(bc, z, D)
    rows = [(BELL_R * math.sin(math.radians(a)), -BELL_R * math.cos(math.radians(a))) for a in range(0, 181, 15)]
    rows[0] = (0.0, rows[0][1])
    rows[-1] = (0.0, rows[-1][1])
    bm_lathe(bm, rows, 16, ball)
    bm_lathe(bm, [(BELL_R - 0.004, -0.007), (BELL_R + 0.006, -0.004), (BELL_R + 0.006, 0.004),
                  (BELL_R - 0.004, 0.007)], 24, ball)
    side = Vector((-D.y, D.x, 0.0)).normalized()
    rings = []
    for k in range(13):
        f = math.radians(-60.0 + 10.0 * k)
        dd = D * math.sin(f) - z * math.cos(f)
        rings.append([bc + dd * (BELL_R + dr) + side * dw for dr, dw in
                      ((-0.004, -0.009), (-0.004, 0.009), (0.003, 0.009), (0.003, -0.009))])
    bm_loft(bm, rings, mat=1, smooth=False)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm, bc.z - BELL_R


def coil(coll, root, cap, bird, rocks, names=RIBBON_NAMES, log=None):
    """Xiaolongnü's golden-bell ribbon coiled on the condor's capstone (see the block comment above). Returns the
    Empty."""
    from sect.areas import abode  # noqa: F401  (registers the ribbon's silk material, abode.RIBBON_MAT)
    bvh, down = _rock_sampler(rocks, root)
    centre, to_eye, info = coil_site(cap, bird, rocks, root)
    secs, D, pinfo = coil_path(centre, to_eye, bvh, down)
    silk = bmesh.new()
    bm_loft(silk, frame_rings(secs, _SECT), mat=0, smooth=True)
    bmesh.ops.recalc_face_normals(silk, faces=silk.faces[:])
    end = secs[-1][0]
    bells, low = bell_bm(end, D)
    em = U.empty(names[0], coll, parent=root, location=centre, display_size=0.5)
    em["sect_item"] = RIBBON_ITEM
    inv = Matrix.Translation(-centre)
    bmesh.ops.transform(silk, matrix=inv, verts=silk.verts)
    bmesh.ops.transform(bells, matrix=inv, verts=bells.verts)
    mesh_object(names[1], silk, coll, [RIBBON_MATS[0]], em, smooth=math.radians(50), tag=RIBBON_ITEM)
    mesh_object(names[2], bells, coll, [RIBBON_MATS[1], RIBBON_MATS[2]], em, smooth=math.radians(45),
                tag=RIBBON_ITEM)
    if log:
        log("ribbon: coiled on %s at (%.2f, %.2f, %.2f), %.2f m from the bird's feet at %.0f deg (rock %.3f m out of "
            "level, %.2f m clear of the bird, hold side %.2f); %d sections, %d on the run to the edge, %d hanging; "
            "bell down to z %.2f" % (cap.name, centre.x, centre.y, centre.z, info["ring"], info["angle"], info["level"],
                                     info["clear"], info["side"], len(secs), pinfo["run"], pinfo["hang"], low))
    return em


# ================================================================ summit: 綠竹巷 bamboo blinds, gauze, qin and lamp
# The Smiling, Proud Wanderer ch. 13 學琴: in Green Bamboo Lane 綠竹巷, Ren Yingying taught Linghu Chong the qin from
# behind a bamboo blind, and he poured out his heart to a voice he never saw. The summit pavilion (summit.pavilion:
# eight faces, radius 7, 6.8 m columns on a 0.7 m platform) gets bamboo blinds on the bays the 1647 hold faces: the two
# side bays (BLIND_HALF) let down half way, rolled at the bottom and tied, a pale gauze curtain hanging behind each a
# metre lower; the middle bay (BLIND_OPEN) rolled right up under its lattice, its bench gone, so the hold sees in to a
# low wooden qin table with a black qin (the abode's guqin, sect/areas/abode.py duet_qin_geo, at QIN_SCALE) and a
# lit paper lamp on a bronze stand beside it. Everything hangs from rods under the bays' hanging lattices (gualuo) and
# stands on the platform; the pieces are children of the Empty 'summit.blinds' under summit.pavilion (the 'summit'
# hotspot's subtree), tagged sect_item BLIND_ITEM.
BLINDS = "summit.blinds"
BLIND_ITEM = "green_bamboo"
BLIND_HALF = (6, 0)
BLIND_OPEN = 7
PAV_SIDES, PAV_R, PAV_H, PAV_PLAT = 8, 7.0, 6.8, 0.7      # summit.py's A.pavilion call
BLIND_IN = -0.1                            # m inside the face line: the blinds hang just outside the lattice's line,
GAUZE_IN = 0.15                            # the gauze just inside it, their rods' ends set into the columns
BLIND_W = 4.5                              # m
BLIND_DROP = 0.5                           # share of the opening (lattice to floor) the half-let-down blinds cover
GAUZE_EXTRA = 1.1                          # m: the gauze hangs this much lower than its blind's roll
BLIND_T = 0.025                            # m: the blind's and the gauze's thickness (round 12: >= 2 cm)
GAUZE_T = 0.025
ROLL_R, ROLL_UP_R = 0.1, 0.14              # m: the roll of a half-down blind, of a rolled-up one
ROD_R = 0.035
TIE_R = 0.012
QIN_SCALE = 0.8
QIN_TABLE = (0.8, 0.31, 0.74, 0.07)        # half length, half depth, top height over the platform, top thickness
QIN_TABLE_IN = 1.3                         # m inside the face line
QIN_SINK = 0.004                           # m: the qin's flat back sits this far into the table top (no face on face)
LAMP_AT = 1.45                             # m from the table's middle along the bay, to the hold's right
QIN_TABLE_MAT = "wood_light"               # warm wood under the black qin (on black lacquer the qin did not read)
BLIND_MAT = "r34_bamboo_blind"
GAUZE_MAT = M.variant("r34_gauze", "cloth_white", colour="#f3f0e7", translucency=0.6, sheen=0.3)
LAMP_SHADE = "paper_lantern"


def _bamboo_blind(g, base="#b59a64", dark="#6a5233", slat=0.05):
    """Split-bamboo blind: warm tan slats across (local z), a dark line between them, each slat's tone a little
    different."""
    v = g.coord("object")
    _x, _y, z = g.sep(v)
    f = g.math('FRACT', g.math('DIVIDE', z, slat))
    gap = g.add(g.smooth(f, 0.14, 0.0), g.smooth(f, 0.86, 1.0))
    tone = g.noise(g.mapping(v, scale=(0.4, 0.4, 1.0 / slat)), 1.0, detail=1.0)
    col = g.mix(base, g.hsv(base, 0.5, 0.92, 0.8), g.maprange(tone, 0.3, 0.7, 0.0, 1.0))
    streak = g.noise(g.mapping(v, scale=(30.0, 30.0, 0.5)), 1.0, detail=2.0)
    col = g.mix(col, g.hsv(base, 0.5, 1.0, 1.12), g.mul(g.smooth(streak, 0.55, 0.75), 0.4))
    col = g.mix(col, dark, g.mul(gap, 0.85))
    g.viewport(base, 0.6)
    g.output(g.principled(base_color=col, roughness=0.62, normal=g.bump(gap, 0.25, 0.004)))


M.register(BLIND_MAT, _bamboo_blind)


def pav_face(k):
    """(normal, tangent, face-middle distance) of pavilion face ``k`` in its own frame (arch.pavilion: face k runs
    from corner k to k + 1, corner angles -90 - 180/n + 360 k / n)."""
    a0 = -math.pi / 2 - math.pi / PAV_SIDES
    pa = Vector((PAV_R * math.cos(a0 + 2 * math.pi * k / PAV_SIDES), PAV_R * math.sin(a0 + 2 * math.pi * k / PAV_SIDES),
                 0.0))
    pb = Vector((PAV_R * math.cos(a0 + 2 * math.pi * (k + 1) / PAV_SIDES),
                 PAV_R * math.sin(a0 + 2 * math.pi * (k + 1) / PAV_SIDES), 0.0))
    t = (pb - pa).normalized()
    n = Vector((t.y, -t.x, 0.0))
    return n, t, ((pa + pb) * 0.5).length


def pav_bay():
    """(floor z, the lattice's underside z, the clear width between columns) of the pavilion's bays (arch.pavilion's
    proportions for PAV_H)."""
    clamp = lambda v, a, b: max(a, min(b, v))           # noqa: E731
    cr = clamp(0.04 * PAV_H + 0.06, 0.15, 0.32)
    hb = clamp(0.16 * PAV_H + 0.15, 0.55, 1.0)
    arch_z = PAV_H - 1.08 * (hb / 1.2)
    gh = clamp(0.12 * PAV_H, 0.3, 0.55)
    side = 2 * PAV_R * math.sin(math.pi / PAV_SIDES)
    return PAV_PLAT, PAV_PLAT + arch_z - gh, side - 2 * cr


def bench_on(pav, k):
    """The bench instance under ``pav`` on face ``k`` (nearest that face's middle), or None."""
    n, _t, d = pav_face(k)
    seats = [c for c in pav.children if ".seat" in c.name[len(pav.name):] and c.instance_collection is not None]
    if not seats:
        return None
    best = min(seats, key=lambda c: (c.matrix_basis.translation.xy - (n * d).xy).length)
    return best if (best.matrix_basis.translation.xy - (n * d).xy).length < 1.0 else None


def _blind_bay(bm_b, bm_g, bm_t, k, open_):
    """One bay's rod, blind (or its roll when open_), ties and (half-down bays) gauze with its rod."""
    n, t, d = pav_face(k)
    floor, z_top, clear = pav_bay()
    c = n * (d - BLIND_IN)
    rod_z = z_top - ROD_R - 0.03
    half = 0.5 * clear + 0.2                        # the rods' ends run into the columns
    rod = [c + t * (-half) + Vector((0, 0, rod_z)), c + t * half + Vector((0, 0, rod_z))]
    bm_tube(bm_b, rod, ROD_R, sides=10, mat=1)
    hw = 0.5 * BLIND_W
    if open_:
        zr = rod_z - ROD_R - ROLL_UP_R + 0.02
        roll_r = ROLL_UP_R
    else:
        zr = rod_z - BLIND_DROP * (rod_z - floor)
        roll_r = ROLL_R
        # the blind: a thin slab from the rod down into the roll
        e = n * (BLIND_T / 2)
        corners = [c + t * (-hw) + Vector((0, 0, zr)), c + t * hw + Vector((0, 0, zr)),
                   c + t * hw + Vector((0, 0, rod_z)), c + t * (-hw) + Vector((0, 0, rod_z))]
        a = [bm_b.verts.new(p - e) for p in corners]
        b = [bm_b.verts.new(p + e) for p in corners]
        fs = [bm_b.faces.new(a), bm_b.faces.new(list(reversed(b)))]
        for i in range(4):
            j = (i + 1) % 4
            fs.append(bm_b.faces.new((a[j], a[i], b[i], b[j])))
        for f in fs:
            f.material_index = 0
            f.smooth = False
        # the gauze behind it, hanging GAUZE_EXTRA lower, softly gathered in folds
        cg = n * (d - GAUZE_IN)
        g_top = rod_z
        g_bot = zr - GAUZE_EXTRA
        bm_tube(bm_b, [cg + t * (-half) + Vector((0, 0, g_top)), cg + t * half + Vector((0, 0, g_top))],
                ROD_R * 0.7, sides=8, mat=1)
        cols = 48
        ring_lo, ring_hi = [], []
        gt = GAUZE_T
        for side in (-1.0, 1.0):
            for i in range(cols + 1):
                u = -hw + 2 * hw * i / cols
                fold = 0.06 * math.sin(u * 2 * math.pi / 0.45)
                p = cg + t * u + n * (fold + side * gt / 2)
                (ring_lo if side < 0 else ring_hi).append((p + Vector((0, 0, g_bot)), p + Vector((0, 0, g_top - 0.02))))
        lo = [(bm_g.verts.new(p0), bm_g.verts.new(p1)) for p0, p1 in ring_lo]
        hi = [(bm_g.verts.new(p0), bm_g.verts.new(p1)) for p0, p1 in ring_hi]
        gf = []
        for i in range(cols):
            gf.append(bm_g.faces.new((lo[i][0], lo[i + 1][0], lo[i + 1][1], lo[i][1])))
            gf.append(bm_g.faces.new((hi[i][1], hi[i + 1][1], hi[i + 1][0], hi[i][0])))
            gf.append(bm_g.faces.new((lo[i][0], hi[i][0], hi[i + 1][0], lo[i + 1][0])))
            gf.append(bm_g.faces.new((lo[i + 1][1], hi[i + 1][1], hi[i][1], lo[i][1])))
        gf.append(bm_g.faces.new((lo[0][0], lo[0][1], hi[0][1], hi[0][0])))
        gf.append(bm_g.faces.new((hi[-1][0], hi[-1][1], lo[-1][1], lo[-1][0])))
        for f in gf:
            f.smooth = True
    # the roll: a cylinder of rolled slats along the bay
    m = frame_at(c + Vector((0, 0, zr)), t, Vector((0, 0, 1)))
    bm_lathe(bm_b, [(roll_r * 0.96, -hw - 0.02), (roll_r, -hw), (roll_r, hw), (roll_r * 0.96, hw + 0.02)], 14, m,
             mat=0, smooth=True)
    # two ties: down the front from the rod, under the roll, up the back
    for s in (-1.0, 1.0):
        u = s * hw * 0.62
        base = c + t * u
        rr = roll_r + TIE_R + 0.008
        pts = [base + n * (BLIND_T / 2 + TIE_R + 0.01) + Vector((0, 0, rod_z))]
        for j in range(13):
            a = math.pi * j / 12
            pts.append(base + n * (rr * math.cos(a)) + Vector((0, 0, zr - rr * math.sin(a))))
        pts.append(base - n * (BLIND_T / 2 + TIE_R + 0.01) + Vector((0, 0, rod_z)))
        bm_tube(bm_t, pts, TIE_R, sides=6, mat=0)


def qin_table_bm(m):
    """Wooden qin table (its frame: x along it, z up from the platform), legs sunk 1 cm."""
    bm = bmesh.new()
    hl, hd, zt, tt = QIN_TABLE
    bm_box(bm, (-hl, -hd, zt - tt), (hl, hd, zt))
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            x, y = sx * (hl - 0.09), sy * (hd - 0.07)
            bm_box(bm, (x - 0.035, y - 0.035, -0.01), (x + 0.035, y + 0.035, zt - tt + 0.005))
    for sy in (-1.0, 1.0):
        y = sy * (hd - 0.05)
        bm_box(bm, (-hl + 0.12, y - 0.02, zt - tt - 0.09), (hl - 0.12, y + 0.02, zt - tt + 0.005))
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts)
    return bm


def lamp_bm(m):
    """Bronze lamp stand with a lit paper shade (its frame: z up from the platform). Materials 0 bronze, 1 shade."""
    bm = bmesh.new()
    bm_lathe(bm, [(0.0, -0.01), (0.24, -0.01), (0.24, 0.04), (0.16, 0.07), (0.05, 0.1), (0.035, 0.14),
                  (0.03, 1.22), (0.05, 1.25), (0.14, 1.28), (0.15, 1.31), (0.0, 1.31)], 16, m, mat=0)
    bm_lathe(bm, [(0.0, 1.29), (0.17, 1.29), (0.19, 1.45), (0.19, 1.62), (0.16, 1.68), (0.0, 1.68)], 16, m, mat=1)
    bm_lathe(bm, [(0.0, 1.675), (0.07, 1.675), (0.05, 1.73), (0.0, 1.76)], 10, m, mat=0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def blinds(coll, pav, names=None, log=None):
    """The 綠竹巷 bay furnishings in the summit pavilion (see the block comment above): the Empty and its meshes
    (names: dict role -> name; default BLIND_NAMES). The middle bay's bench is the caller's to remove
    (bench_on(pav, BLIND_OPEN)). Returns the Empty."""
    from sect.areas import abode as AB
    names = names or BLIND_NAMES
    em = U.empty(names["root"], coll, parent=pav, display_size=1.0)
    em["sect_item"] = BLIND_ITEM
    bm_b, bm_g, bm_t = bmesh.new(), bmesh.new(), bmesh.new()
    for k in BLIND_HALF:
        _blind_bay(bm_b, bm_g, bm_t, k, False)
    _blind_bay(bm_b, bm_g, bm_t, BLIND_OPEN, True)
    mesh_object(names["blinds"], bm_b, coll, [BLIND_MAT, "lacquer_red"], em, smooth=math.radians(40), tag=BLIND_ITEM)
    mesh_object(names["gauze"], bm_g, coll, [GAUZE_MAT], em, smooth=math.radians(60), tag=BLIND_ITEM)
    mesh_object(names["ties"], bm_t, coll, ["cloth_red"], em, smooth=math.radians(50), tag=BLIND_ITEM)
    # the qin table, the qin and the lamp in the open bay
    n, t, d = pav_face(BLIND_OPEN)
    floor, _zt, _clear = pav_bay()
    ct = n * (d - QIN_TABLE_IN) + Vector((0.0, 0.0, floor))
    yaw = math.atan2(t.y, t.x)
    mt = Matrix.Translation(ct) @ Matrix.Rotation(yaw, 4, 'Z')
    mesh_object(names["table"], qin_table_bm(mt), coll, [QIN_TABLE_MAT], em, smooth=False, tag=BLIND_ITEM)
    g = AB.duet_qin_geo()
    roles = next(r for key, _nm, _geo, r in AB.DUET_PARTS if key == "qin")
    me = AB._duet_mesh(names["qin"], g, roles)
    qoff = 0.5 * ((AB.QIN_LEN / 2 - AB.QIN_PEG_U) + (AB.QIN_LEN / 2 - AB.QIN_FOOT_U)) * QIN_SCALE
    mq = mt @ Matrix.Translation((-qoff, 0.0, QIN_TABLE[2] - QIN_SINK)) @ \
        Matrix.Diagonal((QIN_SCALE, QIN_SCALE, QIN_SCALE, 1.0))
    q = U.object_from_mesh(names["qin"], me, coll, parent=em, matrix=mq)
    q["sect_item"] = BLIND_ITEM
    ml = Matrix.Translation(ct + t * LAMP_AT)
    mesh_object(names["lamp"], lamp_bm(ml), coll, ["bronze", LAMP_SHADE], em, smooth=math.radians(40),
                tag=BLIND_ITEM)
    if log:
        floor, z_top, clear = pav_bay()
        rod_z = z_top - ROD_R - 0.03
        zr = rod_z - BLIND_DROP * (rod_z - floor)
        log("blinds: bays %.2f m clear, lattice underside z %.2f; half down on faces %s (roll at z %.2f, gauze down to "
            "%.2f), rolled up on face %d; qin table at %s (pavilion frame), lamp %.2f m along" % (
                clear, z_top, BLIND_HALF, zr, zr - GAUZE_EXTRA, BLIND_OPEN, tuple(round(v, 2) for v in ct), LAMP_AT))
    return em


BLIND_NAMES = dict(root=BLINDS, blinds="summit.blinds_bamboo", gauze="summit.blinds_gauze", ties="summit.blinds_ties",
                   table="summit.qin_table", qin="summit.qin", lamp="summit.qin_lamp")
