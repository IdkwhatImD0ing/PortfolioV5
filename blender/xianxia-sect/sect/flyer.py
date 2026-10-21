"""The flyer: a cultivator riding a flying sword (blocking level).

build(collection) -> root Empty 'flyer.root'. Local frame: +Y is the direction of flight,
+Z up, origin at the sword's balance point. The figure stands on the sword, about 1.8 m
tall including the topknot, leaning slightly into the wind, hands clasped behind the back.
Cloth (sleeves, robe tails, sash ribbons, hair and hair ribbons) flutters on its own over
frames through Wave modifiers weighted toward the free ends, and the sword trails a thin
cyan light streak. The camera sees the flyer mostly from behind, so the back carries the
detail: a flowing violet robe, lilac sash ribbons, black hair with silver ribbons.
Purple theme (the user's choice), matching the portfolio site's purple accents.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from sect.lib import materials as M
from sect.lib import util as U

KEY = "flyer"
LEAN_DEG = -8.0          # forward lean of the body (negative X rotation tips +Z toward +Y)


def _n(*parts):
    return U.name(KEY, *parts)


def _skin():
    mat = bpy.data.materials.get("flyer.skin")
    if mat is None:
        mat = bpy.data.materials.new("flyer.skin")
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (0.80, 0.60, 0.50, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.55
    return mat


def _robe_materials():
    """Purple robe palette: violet outer robe, lilac trims and sash (close to the site's #c084fc)."""
    M.variant("flyer_robe", "cloth_white", colour="#5b2d94", translucency=0.3, sheen=0.6)
    M.variant("flyer_trim", "cloth_white", colour="#b98ae8", translucency=0.4, sheen=0.7)
    return M.get("flyer_robe"), M.get("flyer_trim")


def _flutter(obj, weights, height=0.10, width=0.9, speed=0.07, narrow=1.5, axis='Y', offset=0.0):
    """Wave modifier that ripples the mesh along its normal, scaled per vertex by weights."""
    vg = obj.vertex_groups.new(name="flutter")
    for i, w in enumerate(weights):
        vg.add([i], max(0.0, min(1.0, w)), 'REPLACE')
    m = obj.modifiers.new("flutter", 'WAVE')
    m.use_x = axis == 'X'
    m.use_y = axis == 'Y'
    m.use_normal = True
    m.height = height
    m.width = width
    m.speed = speed
    m.narrowness = narrow
    m.time_offset = offset
    m.vertex_group = vg.name
    return m


def _strip(name, coll, pts, width, side, mat, parent, seg=6, taper=0.3, flutter=None):
    """Ribbon of cloth along a smooth curve through pts. width tapers to width*taper at the end.
    side: direction of the ribbon's width. flutter: kwargs for _flutter (weights grow along it)."""
    path = U.catmull_rom([tuple(p) for p in pts], seg)
    s = Vector(side).normalized()
    bm = bmesh.new()
    rows = []
    last = len(path) - 1
    for i, p in enumerate(path):
        t = i / last
        c = Vector(p[:3])
        w = width * (1.0 - (1.0 - taper) * t) * p[3]
        rows.append((bm.verts.new(c - s * (w * 0.5)), bm.verts.new(c + s * (w * 0.5))))
    for i in range(last):
        a, b = rows[i]
        c, d = rows[i + 1]
        bm.faces.new((a, b, d, c))
    obj = U.mesh_from_bmesh(name, bm, coll, materials=[mat], smooth=True, parent=parent)
    if flutter is not None:
        weights = []
        for i in range(len(path)):
            t = (i / last) ** 1.3
            weights += [t, t]
        _flutter(obj, weights, **flutter)
    return obj


def _lathe_obj(name, coll, profile, mat, parent, segments=20, matrix=None, deform=None, flutter=None):
    bm = bmesh.new()
    U.bm_lathe(bm, profile, segments=segments, cap_start=False, cap_end=False)
    weights = None
    if deform is not None:
        bm.verts.index_update()
        weights = [0.0] * len(bm.verts)
        for v in bm.verts:
            weights[v.index] = deform(v.co)
    if matrix is not None:
        U.bm_transform(bm, matrix)
    obj = U.mesh_from_bmesh(name, bm, coll, materials=[mat], smooth=True, parent=parent)
    if flutter is not None and weights is not None:
        _flutter(obj, weights, **flutter)
    return obj


def _sphere(name, coll, radius, center, mat, parent, scale=(1, 1, 1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=radius)
    for v in bm.verts:
        v.co = Vector((v.co.x * scale[0], v.co.y * scale[1], v.co.z * scale[2])) + Vector(center)
    return U.mesh_from_bmesh(name, bm, coll, materials=[mat], smooth=True, parent=parent)


def _sword(coll, root):
    """Flying sword along +Y: blade, glowing fuller, gold guard, wrapped hilt, red tassel."""
    bm = bmesh.new()
    stations = [(-0.90, 0.075, 0.014), (0.6, 0.07, 0.013), (1.22, 0.05, 0.010)]
    rings = []
    for y, hw, ht in stations:
        rings.append([bm.verts.new((-hw, y, 0)), bm.verts.new((0, y, ht)),
                      bm.verts.new((hw, y, 0)), bm.verts.new((0, y, -ht))])
    tip = bm.verts.new((0, 1.48, 0))
    for a, b in zip(rings, rings[1:]):
        for k in range(4):
            bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
    for k in range(4):
        bm.faces.new((rings[-1][k], rings[-1][(k + 1) % 4], tip))
    bm.faces.new(list(reversed(rings[0])))
    blade = U.mesh_from_bmesh(_n("sword_blade"), bm, coll, materials=[M.get("silver")], smooth=False, parent=root)

    bm = bmesh.new()
    U.bm_box(bm, size=(0.018, 1.95, 0.006), center=(0, 0.25, 0.012))
    fuller = U.mesh_from_bmesh(_n("sword_fuller"), bm, coll, materials=[M.get("jade_glow")], parent=root)

    bm = bmesh.new()
    U.bm_box(bm, size=(0.34, 0.07, 0.06), center=(0, -0.93, 0))
    U.mesh_from_bmesh(_n("sword_guard"), bm, coll, materials=[M.get("gold")], parent=root)

    rot = Matrix.Rotation(math.radians(90), 4, 'X')
    bm = bmesh.new()
    U.bm_cylinder(bm, radius=0.024, depth=0.30, segments=10, matrix=Matrix.Translation((0, -1.11, 0)) @ rot)
    U.mesh_from_bmesh(_n("sword_hilt"), bm, coll, materials=[M.get("cloth_teal")], smooth=True, parent=root)
    bm = bmesh.new()
    U.bm_cylinder(bm, radius=0.04, depth=0.05, segments=10, matrix=Matrix.Translation((0, -1.28, 0)) @ rot)
    U.mesh_from_bmesh(_n("sword_pommel"), bm, coll, materials=[M.get("gold")], smooth=True, parent=root)
    _strip(_n("sword_tassel"), coll, [(0, -1.30, 0), (0.02, -1.55, -0.03), (-0.02, -1.85, -0.02), (0.03, -2.1, -0.05)],
           0.05, (1, 0, 0), M.get("cloth_red"), root, taper=0.6,
           flutter=dict(height=0.05, width=0.5, speed=0.09))

    # Sword qi: a soft glow under the blade and a fading light streak behind it.
    glow = _sphere(_n("sword_aura"), coll, 1.0, (0, 0.2, -0.02), M.get("light_beam"), root, scale=(0.16, 1.25, 0.05))
    U.set_visibility(glow, shadow=False)
    for k, (w, z) in enumerate(((0.10, 0.0), (0.035, 0.012))):   # soft wide streak + bright core
        trail = _strip(_n("sword_trail"), coll, [(0, -1.3, z), (0, -3.5, z + 0.02), (0, -6.0, z + 0.05), (0, -8.5, z + 0.08)],
                       w, (1, 0, 0), M.get("light_beam" if k == 0 else "jade_glow"), root, taper=0.05,
                       flutter=dict(height=0.04, width=1.6, speed=0.15))
        U.set_visibility(trail, shadow=False)

    light = bpy.data.lights.new(_n("sword_light"), 'POINT')
    light.energy = 60.0
    light.color = (0.45, 1.0, 0.85)
    light.shadow_soft_size = 0.3
    lo = bpy.data.objects.new(_n("sword_light"), light)
    U.link(lo, coll)
    lo.parent = root
    lo.location = (0, 0.1, -0.25)
    return blade, fuller


def _figure(coll, root):
    """The cultivator, standing on the sword with feet around y 0..0.25."""
    body = U.empty(_n("body"), coll, location=(0, 0.08, 0.02), parent=root,
                   rotation=(math.radians(LEAN_DEG), 0, 0), display_size=0.3)
    white, teal = _robe_materials()          # names kept: white = the robe, teal = trims and sash
    ink, silver = M.get("ink"), M.get("silver")

    for x in (-0.09, 0.09):
        bm = bmesh.new()
        U.bm_box(bm, size=(0.09, 0.24, 0.07), center=(x, 0.06, 0.035))
        U.mesh_from_bmesh(_n("shoe"), bm, coll, materials=[M.get("cloth_black")], parent=body)

    def hem(co):  # skirt: the hem blows back and widens; weight = how free the cloth is
        f = max(0.0, (1.02 - co.z) / 1.0) ** 1.6
        co.y -= 0.50 * f
        co.x *= 1.0 + 0.18 * f
        return f
    _lathe_obj(_n("robe_skirt"), coll, [(0.31, 0.05), (0.28, 0.32), (0.22, 0.62), (0.175, 0.92), (0.165, 1.03)],
               white, body, deform=hem, flutter=dict(height=0.035, width=0.45, speed=0.08, axis='Y'))
    _lathe_obj(_n("torso"), coll, [(0.165, 1.0), (0.19, 1.18), (0.205, 1.34), (0.19, 1.45), (0.085, 1.52), (0.055, 1.57)],
               white, body)
    _lathe_obj(_n("sash"), coll, [(0.175, 0.99), (0.182, 1.02), (0.182, 1.09), (0.176, 1.11)], teal, body)
    # Collar trim (the crossed collar reads as a teal V from the side).
    _strip(_n("collar"), coll, [(-0.12, 0.10, 1.47), (-0.03, 0.17, 1.30), (0.02, 0.16, 1.18)], 0.035, (0, 0, 1), teal, body,
           taper=1.0)

    # Head and hair (topknot with a silver pin, long hair and two silver ribbons streaming back).
    _sphere(_n("head"), coll, 0.105, (0, 0.01, 1.665), _skin(), body)
    _sphere(_n("hair_cap"), coll, 0.112, (0, -0.012, 1.675), ink, body, scale=(1.0, 1.0, 1.02))
    _sphere(_n("topknot"), coll, 0.052, (0, -0.02, 1.795), ink, body)
    bm = bmesh.new()
    U.bm_cylinder(bm, radius=0.007, depth=0.20, segments=6,
                  matrix=Matrix.Translation((0, -0.02, 1.80)) @ Matrix.Rotation(math.radians(90), 4, 'Y'))
    U.mesh_from_bmesh(_n("hairpin"), bm, coll, materials=[silver], parent=body)
    _strip(_n("hair"), coll, [(0, -0.09, 1.70), (0, -0.26, 1.55), (0, -0.55, 1.42), (0.02, -0.90, 1.36)],
           0.15, (1, 0, 0), ink, body, taper=0.25, flutter=dict(height=0.04, width=0.5, speed=0.07))
    for x in (-0.03, 0.03):
        _strip(_n("hair_ribbon"), coll,
               [(x, -0.05, 1.80), (x * 2, -0.40, 1.74), (x * 3, -0.85, 1.70), (x * 4, -1.35, 1.66)],
               0.03, (1, 0, 0), silver, body, taper=0.6, flutter=dict(height=0.06, width=0.55, speed=0.1, offset=x * 40))

    # Arms with hands clasped behind the back, and wide sleeves streaming back.
    for side in (-1, 1):
        sh, el, ha = Vector((0.21 * side, 0.0, 1.42)), Vector((0.26 * side, -0.12, 1.16)), Vector((0.07 * side, -0.24, 1.02))
        U.tube_mesh(_n("arm"), [tuple(sh) + (1.0,), tuple(el) + (0.95,), tuple(ha) + (0.8,)], 0.05, coll,
                    material=white, sides=10, parent=body)
        # Wide hanfu sleeve: a broad cloth panel hanging from the forearm, blown back and down.
        _strip(_n("sleeve"), coll,
               [tuple(el + Vector((0.02 * side, 0.04, 0.0))), tuple(el + Vector((0.05 * side, -0.30, -0.16))),
                tuple(el + Vector((0.07 * side, -0.62, -0.26))), tuple(el + Vector((0.08 * side, -0.95, -0.30)))],
               0.34, (0, 0.25, 1), white, body, taper=0.7,
               flutter=dict(height=0.07, width=0.6, speed=0.09, offset=side * 7))
    _sphere(_n("hands"), coll, 0.06, (0, -0.25, 1.02), _skin(), body, scale=(1.4, 0.9, 0.9))

    # Outer robe tails and long sash ribbons: the big flowing shapes the chase camera sees.
    for side in (-1, 1):
        _strip(_n("robe_tail"), coll,
               [(0.09 * side, -0.16, 1.02), (0.13 * side, -0.55, 0.78), (0.17 * side, -1.05, 0.62), (0.20 * side, -1.55, 0.58)],
               0.24, (1, 0, 0), white, body, taper=0.55,
               flutter=dict(height=0.09, width=0.8, speed=0.08, offset=side * 11))
        _strip(_n("sash_ribbon"), coll,
               [(0.10 * side, -0.18, 1.05), (0.22 * side, -0.70, 0.98), (0.30 * side, -1.40, 1.05),
                (0.38 * side, -2.10, 0.96), (0.46 * side, -2.80, 1.02)],
               0.075, (1, 0, 0), teal, body, taper=0.5,
               flutter=dict(height=0.12, width=0.9, speed=0.11, offset=side * 5))
    return body


def build(collection):
    """Build the flyer at the origin, flying toward +Y. Returns 'flyer.root'."""
    root = U.empty(_n("root"), collection, display_size=1.0, display_type='ARROWS')
    _sword(collection, root)
    _figure(collection, root)
    return root


def showcase(collection):
    """Preview target: the flyer on a small plinth-free stage, seen from behind and the side."""
    root = build(collection)
    root.location = (0, 0, 4.0)
    return root
