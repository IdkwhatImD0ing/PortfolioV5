"""Chinese architecture primitives for the Moonlit Sect (spec.md sections 3 and 5).

    from sect.lib import arch as A
    root = A.hall("mission.hall", coll, bays_w=5, bays_d=3, double_eave=True)
    root["plaque_anchor"]           # name of the Empty where a plaque should hang

Everything is built procedurally at the local origin, front facing -Y, meters, Z up.
Repeated parts (tile end caps, drip tiles, rafter ends, beasts, chiwen, brackets, columns,
balustrade posts and panels, lattice bars) are prototypes in excluded ``_protos``
collections, instanced either by collection-instance Empties or by one geometry-nodes
"scatter" object per kind (a point cloud whose FLOAT4X4 attribute ``arch_xf`` holds each
instance's full matrix, so sheared panels on stair slopes work too).

Roofs are analytic: the top surface height is a concave profile of the distance to the eave
polygon (straight-skeleton roof), so hips, ridges and pyramids fall out of one function. A
smooth corner field then lifts and pushes the eave corners (qiao jiao). Tile courses are real
corrugated geometry (round tube tiles over concave pan tiles); tile laps and lip shadows come
from a UV-driven bump added on top of the shared tile material (``tile_material``).
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import materials as M
from . import util as U

__all__ = [
    "roof", "roof_shape", "double_eave_roofs", "tile_material", "scatter",
    "column", "bracket_band", "beam",
    "lattice_panel", "platform", "stairs", "balustrade",
    "hall", "pagoda", "pavilion", "paifang", "corridor", "wall", "moon_gate", "tower",
    "band_height_for", "paint_layers", "tag_piece", "showcase",
]

TAU = 2.0 * math.pi
Z = Vector((0.0, 0.0, 1.0))


# ======================================================================== small helpers

def _smooth01(x):
    x = 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)
    return x * x * (3.0 - 2.0 * x)


def _lerp(a, b, t):
    return a + (b - a) * t


def _clamp(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


def _r(x, nd=3):
    """Rounded value for cache keys."""
    return round(float(x), nd)


def _root(name, collection, parent=None, location=(0, 0, 0), rotation_z=0.0, size=1.0):
    """Root Empty for a builder (its name is the prefix of every child)."""
    return U.empty(U.name(name), collection, location=location, rotation=(0, 0, rotation_z),
                   parent=parent, display_size=size)


def _child(root, part):
    return U.name(root.name, part)


def _frame(x_axis, y_axis, origin, scale=(1.0, 1.0, 1.0)):
    """4x4 matrix from an X and an (approximate) Y axis: Z = X x Y, Y re-orthogonalised."""
    x = Vector(x_axis).normalized()
    z = x.cross(Vector(y_axis))
    if z.length < 1e-9:
        z = Z.copy()
    z.normalize()
    y = z.cross(x)
    m = Matrix((x * scale[0], y * scale[1], z * scale[2])).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


def _upright(forward, origin, scale=1.0):
    """Matrix with local +X along the horizontal part of ``forward``, Z up."""
    f = Vector((forward[0], forward[1], 0.0))
    if f.length < 1e-9:
        f = Vector((1.0, 0.0, 0.0))
    s = (scale, scale, scale) if isinstance(scale, (int, float)) else scale
    return _frame(f, Z.cross(f.normalized()), origin, s)


# ======================================================================== materials

_ARCH_MATS = dict(
    # matte paint for soffit boards / fascia, teal rafter paint, red plaster walls
    arch_paint_red=("lacquer_red", dict(c1="#7d2217", c2="#92291d", rough=(0.55, 0.7), coat=0.05)),
    arch_paint_teal=("lacquer_red", dict(c1="#1f5557", c2="#2a6a63", rough=(0.5, 0.65), coat=0.05)),
    arch_plaster_red=("lacquer_red", dict(c1="#7e271e", c2="#8f2f23", rough=(0.82, 0.93), coat=0.0)),
    # garden walls (moon gates): lime-washed white plaster
    arch_plaster_white=("lacquer_red", dict(c1="#ddd7cb", c2="#e8e3d8", rough=(0.85, 0.92), coat=0.0)),
    # carved boards on gates: deep Qing blue behind gold carving
    arch_paint_blue=("lacquer_red", dict(c1="#1b2f52", c2="#22395f", rough=(0.5, 0.65), coat=0.05)),
)


def _box_space(g):
    """Distances (m) to the faces of each painted piece's own box, from the mesh attributes
    arch_gen (0-1 position inside the piece's box) and arch_dims (box size). Unlike the shared
    bracket_paint (object bounding box + 'dimensions'), this survives instancing and merging."""
    gen = g.attr("arch_gen", out="Vector")
    dims = g.attr("arch_dims", out="Vector")
    inv = g.vmath('SUBTRACT', (1.0, 1.0, 1.0), gen)
    dmin = g.vmath('MULTIPLY', g.vmath('MINIMUM', gen, inv), dims)
    return gen, dims, dmin


def _piece_rand(g):
    return g.math('FRACT', g.add(g.attr("arch_rand"), g.obj_random()))


def _box_paint(g, greens=("#2f6f73", "#3d8a7a", "#2b5f86"), gold="#c9a24a", line=0.03):
    """Dougong paint per box piece: blue-green field (picked per piece), gold border line, thin
    dark and white lines inside it (same look as materials.bracket_paint)."""
    v = g.coord("object")
    rnd = _piece_rand(g)
    field = g.ramp(rnd, [(0.0, greens[0]), (0.45, greens[0]), (0.5, greens[1]), (0.82, greens[1]),
                         (0.86, greens[2]), (1.0, greens[2])], interp='CONSTANT')
    fade = g.noise(v, 3.0, detail=4.0, roughness=0.6)
    field = g.mix(field, g.hsv(field, 0.5, 0.75, 1.2), g.maprange(fade, 0.45, 0.8, 0.0, 0.5))
    _, _, dmin = _box_space(g)
    dx, dy, dz = g.sep(dmin)
    lo = g.math('MINIMUM', g.math('MINIMUM', dx, dy), dz)
    hi = g.math('MAXIMUM', g.math('MAXIMUM', dx, dy), dz)
    mid = g.math('SUBTRACT', g.math('SUBTRACT', g.add(g.add(dx, dy), dz), lo), hi)
    gold_m = g.smooth(mid, line, line * 0.8)
    dark_m = g.mul(g.smooth(mid, line * 1.55, line * 1.35), g.math('SUBTRACT', 1.0, gold_m))
    white_m = g.mul(g.smooth(mid, line * 2.1, line * 1.9),
                    g.math('SUBTRACT', 1.0, g.smooth(mid, line * 1.6, line * 1.5)))
    col = g.mix(field, "#e6dfcc", g.mul(white_m, 0.85))
    col = g.mix(col, "#10171a", dark_m)
    col = g.mix(col, gold, gold_m)
    g.viewport(greens[0], 0.6)
    g.output(g.principled(base_color=col, roughness=g.mixf(0.62, 0.32, gold_m), metallic=g.mul(gold_m, 0.85),
                          normal=g.bump(g.noise(v, 30.0, detail=3.0, roughness=0.6), 0.05, 0.003)))


def _beam_paint(g, green="#2f6f73", blue="#265a7c", gold="#c9a24a", line=0.026):
    """Qing hexi-style beam painting on box beams (needs arch_gen / arch_dims, x along the
    beam): gold border, gold bands near the ends (gutou), gold chevrons (zaotou) and a central
    panel (fangxin) with a pointed gold outline; blue and green swap per beam."""
    v = g.coord("object")
    rnd = _piece_rand(g)
    gen, dims, dmin = _box_space(g)
    gx, gy, gz = g.sep(gen)
    Lx, Ly, Lz = g.sep(dims)
    _, dy, dz = g.sep(dmin)
    side = g.math('LESS_THAN', dy, dz)                 # 1 on the long vertical faces
    acr = g.mixf(gy, gz, side)
    H = g.mixf(Ly, Lz, side)
    s = g.mul(gx, Lx)
    azc = g.math('ABSOLUTE', g.mul(g.math('SUBTRACT', acr, 0.5), H))
    d_end = g.math('MINIMUM', s, g.math('SUBTRACT', Lx, s))
    halfH = g.mul(H, 0.5)

    def lt(a, b):
        return g.math('LESS_THAN', a, b)

    def near(x, c, w):
        return lt(g.math('ABSOLUTE', g.math('SUBTRACT', x, c)), w)

    border = lt(g.math('MINIMUM', d_end, g.math('SUBTRACT', halfH, azc)), line)
    band1 = near(d_end, g.mul(H, 0.5), g.mul(H, 0.045))
    band2 = near(d_end, g.mul(H, 0.74), g.mul(H, 0.025))
    inner = lt(azc, g.mul(H, 0.4))
    chev = g.mul(near(d_end, g.add(g.mul(H, 1.05), g.mul(azc, 0.95)), line * 1.3), inner)
    chev2 = g.mul(near(d_end, g.add(g.mul(H, 1.35), g.mul(azc, 0.95)), line * 0.9), inner)
    dc = g.math('ABSOLUTE', g.math('SUBTRACT', s, g.mul(Lx, 0.5)))
    ph = g.add(g.mul(Lx, 0.17), g.mul(g.math('SUBTRACT', g.mul(H, 0.4), azc), 0.9))
    inside = g.mul(lt(dc, ph), inner)
    pedge = g.math('MAXIMUM', g.mul(near(dc, ph, line), inner),
                   g.mul(near(azc, g.mul(H, 0.4), line), lt(dc, ph)))
    alt = g.math('GREATER_THAN', rnd, 0.5)
    c_out = g.mix(green, blue, alt)
    c_in = g.mix(blue, green, alt)
    ends = lt(d_end, g.mul(H, 0.74))
    col = g.mix(c_out, c_in, g.math('MAXIMUM', inside, ends))
    fade = g.noise(v, 2.0, detail=4.0, roughness=0.6)
    col = g.mix(col, g.hsv(col, 0.5, 0.8, 1.15), g.maprange(fade, 0.45, 0.8, 0.0, 0.45))
    gold_m = g.math('MINIMUM', g.add(g.add(g.add(border, band1), g.add(band2, chev)), g.add(chev2, pedge)), 1.0)
    col = g.mix(col, gold, gold_m)
    g.viewport(green, 0.6)
    g.output(g.principled(base_color=col, roughness=g.mixf(0.6, 0.3, gold_m), metallic=g.mul(gold_m, 0.85),
                          normal=g.bump(g.noise(v, 30.0, detail=3.0, roughness=0.6), 0.05, 0.003)))


_ARCH_BUILDERS = dict(
    arch_paint_box=(_box_paint, dict(line=0.03)),
    arch_paint_box_fine=(_box_paint, dict(line=0.011)),
    arch_beam_paint=(_beam_paint, dict()),
)


def _init_materials():
    for name, (base, params) in _ARCH_MATS.items():
        if not M.has(name):
            M.variant(name, base, **params)
    for name, (builder, params) in _ARCH_BUILDERS.items():
        if not M.has(name):
            M.register(name, builder, **params)


def _paint_layers(bm):
    """Create the arch paint attribute layers on a fresh BMesh (before adding geometry: adding
    a layer later invalidates vertex references). Returns the BMesh."""
    for nm in ("arch_gen", "arch_dims"):
        if bm.verts.layers.float_vector.get(nm) is None:
            bm.verts.layers.float_vector.new(nm)
    if bm.verts.layers.float.get("arch_rand") is None:
        bm.verts.layers.float.new("arch_rand")
    return bm


def _tag_piece(bm, verts, rand=0.0):
    """Write arch_gen / arch_dims / arch_rand on ``verts`` (one box-like piece, in its own
    axis-aligned frame) so the arch paint materials can draw its border lines."""
    lg = bm.verts.layers.float_vector["arch_gen"]
    ld = bm.verts.layers.float_vector["arch_dims"]
    lr = bm.verts.layers.float["arch_rand"]
    lo = Vector((min(v.co.x for v in verts), min(v.co.y for v in verts), min(v.co.z for v in verts)))
    hi = Vector((max(v.co.x for v in verts), max(v.co.y for v in verts), max(v.co.z for v in verts)))
    d = Vector((max(hi.x - lo.x, 1e-6), max(hi.y - lo.y, 1e-6), max(hi.z - lo.z, 1e-6)))
    for v in verts:
        v[lg] = ((v.co.x - lo.x) / d.x, (v.co.y - lo.y) / d.y, (v.co.z - lo.z) / d.z)
        v[ld] = d
        v[lr] = rand


def _tile_builder(base):
    """(builder, params) of a materials.py material, with the builder's defaults filled in.
    materials.py has no public accessor for builders, so this reads its registry, through a
    public ``builder()`` if one ever appears."""
    acc = getattr(M, "builder", None)
    builder, params = acc(base) if callable(acc) else M._REGISTRY[base]
    full = {}
    try:
        import inspect
        for k, p in inspect.signature(builder).parameters.items():
            if p.default is not inspect.Parameter.empty:
                full[k] = p.default
    except (TypeError, ValueError):
        pass
    full.update(params)
    return builder, full


def _srgb_lum(hexcol):
    """Perceptual (sRGB-space) luminance 0-1 of a '#rrggbb' colour."""
    try:
        h = hexcol.lstrip("#")
        r, g_, b = (int(h[k:k + 2], 16) / 255.0 for k in (0, 2, 4))
        return 0.2126 * r + 0.7152 * g_ + 0.0722 * b
    except (AttributeError, ValueError, IndexError):
        return 0.3


def _principled_of(g):
    links = g.out.inputs["Surface"].links
    if not links:
        return None
    bsdf = links[0].from_node
    return bsdf if bsdf.type == 'BSDF_PRINCIPLED' else None


def _soft_glaze(g, base="roof_tile_teal", rough_min=0.0, rough_add=0.0, coat_max=0.5, coat_rough=0.2,
                value=1.0):
    """Builder: the shared tile material ``base`` with a softer glaze. Raises the base roughness
    (at least ``rough_min``, plus ``rough_add``), caps the clear coat at ``coat_max`` with at least
    ``coat_rough`` coat roughness, and scales the colour value by ``value``. Used for ridges, roof
    figures and end caps, whose long smooth curves otherwise flash clipped white highlights."""
    builder, params = _tile_builder(base)
    params = dict(params)
    r = params.get("rough")
    if isinstance(r, (tuple, list)) and len(r) == 2:
        params["rough"] = (min(max(r[0] + rough_add, rough_min), 0.95),
                           min(max(r[1] + rough_add, rough_min + 0.12), 0.98))
    if "coat" in params:
        params["coat"] = min(float(params["coat"]), coat_max)
    builder(g, **params)
    bsdf = _principled_of(g)
    if bsdf is None:
        return
    cr = bsdf.inputs.get("Coat Roughness")
    if cr is not None and not cr.links:
        cr.default_value = max(cr.default_value, coat_rough)
    if abs(value - 1.0) > 1e-6:
        bc = bsdf.inputs["Base Color"]
        src = bc.links[0].from_socket if bc.links else tuple(bc.default_value)
        g.set(bc, g.hsv(src, 0.5, 1.05, value))
    return bsdf


def _lapped_tile(g, base="roof_tile_teal"):
    """Builder: the shared tile material ``base`` plus UV-driven tile laps.

    UV u = tile-course coordinate (integers are tube-tile crests), v = lap coordinate along the
    slope (integers are tile lips). Adds a soft lip step bump, a soft shadow just under each lip
    and a dark crease where tube tiles sit on the pan tiles. The shadows scale down on bright
    glazes (moon-white gets about 40 % of the darkening), so pale roofs read as polished glaze,
    not clumped snow. The clear coat is softened (coat <= 0.5, coat roughness 0.2) so curved
    corners and tile lips do not sparkle when the camera moves."""
    _, params = _tile_builder(base)
    bsdf = _soft_glaze(g, base, coat_max=0.5, coat_rough=0.2)
    if bsdf is None:
        return              # unknown tile shader layout: keep the plain tile material
    k = _clamp(1.0 - 0.75 * _srgb_lum(params.get("c1", "#1f4f4b")), 0.3, 1.0)
    bc = bsdf.inputs["Base Color"]
    src = bc.links[0].from_socket if bc.links else tuple(bc.default_value)
    nin = bsdf.inputs["Normal"]
    nsrc = nin.links[0].from_socket if nin.links else None
    u, v, _ = g.sep(g.coord("uv"))
    fu = g.math('ABSOLUTE', g.math('SUBTRACT', g.math('FRACT', g.add(u, 0.5)), 0.5))
    fv = g.math('FRACT', v)
    lip = g.smooth(fv, 0.80, 0.985)
    crease = g.mul(g.smooth(fu, 0.17, 0.215), g.math('SUBTRACT', 1.0, g.smooth(fu, 0.24, 0.38)))
    dark = g.math('MINIMUM', g.add(g.mul(lip, 0.5 * k), g.mul(crease, 0.45 * k)), 1.0)
    col = g.mix(src, g.hsv(src, 0.5, 1.05, 0.42), dark)
    g.set(bc, col)
    height = g.mul(g.math('SUBTRACT', 1.0, fv), g.smooth(fv, 0.0, 0.15))
    nrm = g.bump(height, 0.25 * (0.5 + 0.5 * k), 0.012, normal=nsrc)
    g.set(nin, nrm)
    for nm in ("Coat Normal",):
        s = bsdf.inputs.get(nm)
        if s is not None:
            g.set(s, nrm)


def tile_material(base="roof_tile_teal"):
    """Material for corrugated roof surfaces: ``base`` (a materials.py tile name) plus tile laps
    driven by the roof mesh UVs. Registered as 'arch_tiles_<base>'. Returns the Material."""
    _init_materials()
    name = "arch_tiles_" + base
    if not M.has(name):
        M.register(name, _lapped_tile, base=base)
    return M.get(name)


def ridge_material(base="roof_tile_teal", kind="ridge"):
    """Softer glaze of tile ``base`` for ridges, roof figures and end caps (no clipped glints).
    kind: 'ridge' (ridges, beasts, chiwen: roughness >= 0.45, coat <= 0.25), 'band' (the darker
    recessed band of a main ridge) or 'cap' (eave end caps: roughness + 0.15, coat <= 0.3).
    Registered as 'arch_<kind>_<base>'. Returns the Material."""
    _init_materials()
    name = "arch_%s_%s" % (kind, base)
    if not M.has(name):
        if kind == "cap":
            M.register(name, _soft_glaze, base=base, rough_add=0.15, coat_max=0.3, coat_rough=0.25)
        elif kind == "band":
            M.register(name, _soft_glaze, base=base, rough_min=0.5, coat_max=0.2, coat_rough=0.3,
                       value=0.6)
        else:
            M.register(name, _soft_glaze, base=base, rough_min=0.45, coat_max=0.25, coat_rough=0.3)
    return M.get(name)


def _mat(name):
    _init_materials()
    return M.get(name)


def paint_layers(bm):
    """Public: create the arch paint attribute layers on a fresh BMesh (call before adding
    geometry). Use with :func:`tag_piece` for pieces painted with arch_paint_box /
    arch_paint_box_fine / arch_beam_paint, which keep their gold lines when instanced."""
    return _paint_layers(bm)


def tag_piece(bm, verts, rand=0.0):
    """Public: tag one box-like piece (its verts, in the piece's own axis-aligned frame) for the
    arch paint materials. ``rand`` (0-1) picks the field colour."""
    return _tag_piece(bm, verts, rand)


# ======================================================================== prototypes + scatter

def _proto(key, build):
    """Prototype collection 'arch.p.<key>' (excluded from view layers), built once by
    ``build(col)``; survives look.reset_scene() by re-validating."""
    cname = "arch.p." + key
    col = bpy.data.collections.get(cname)
    if col is not None and col.get("arch_ok") and len(col.objects):
        return col
    col = U.proto_collection(cname)
    for o in list(col.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    build(col)
    col["arch_ok"] = 1
    return col


def _proto_obj(col, part, bm, materials, smooth=math.radians(40), bevel=None):
    """Object for a prototype collection from a BMesh."""
    ob = U.mesh_from_bmesh(U.name(col.name, part), bm, col, materials=materials, smooth=smooth)
    if bevel:
        U.bevel_mesh(ob, bevel[0], bevel[1])
    return ob


def _scatter_group(proto):
    gname = "arch.gn." + proto.name
    ng = bpy.data.node_groups.get(gname)
    if ng is not None:
        ci = ng.nodes.get("arch_ci")
        if ci is not None and ci.inputs["Collection"].default_value == proto:
            return ng
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new(gname, 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi = N.new("NodeGroupInput")
    go = N.new("NodeGroupOutput")
    ci = N.new("GeometryNodeCollectionInfo")
    ci.name = "arch_ci"
    ci.transform_space = 'ORIGINAL'
    ci.inputs["Collection"].default_value = proto
    iop = N.new("GeometryNodeInstanceOnPoints")
    na = N.new("GeometryNodeInputNamedAttribute")
    na.data_type = 'FLOAT4X4'
    na.inputs["Name"].default_value = "arch_xf"
    sit = N.new("GeometryNodeSetInstanceTransform")
    L.new(gi.outputs[0], iop.inputs["Points"])
    L.new(ci.outputs[0], iop.inputs["Instance"])
    L.new(iop.outputs[0], sit.inputs["Instances"])
    L.new(na.outputs[0], sit.inputs["Transform"])
    L.new(sit.outputs[0], go.inputs[0])
    for i, n in enumerate((gi, ci, na, iop, sit, go)):
        n.location = (200 * i, 0)
    return ng


def scatter(name, collection, proto, matrices, parent=None):
    """Instance prototype collection ``proto`` once per 4x4 matrix (parent-local space) with a
    geometry-nodes point cloud. Returns the scatter object (None if no matrices)."""
    matrices = list(matrices)
    if not matrices:
        return None
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(matrices))
    co = []
    flat = []
    for m in matrices:
        t = m.translation
        co.extend((t.x, t.y, t.z))
        for c in range(4):
            for r in range(4):
                flat.append(m[r][c])
    me.vertices.foreach_set("co", co)
    at = me.attributes.new("arch_xf", 'FLOAT4X4', 'POINT')
    at.data.foreach_set("value", flat)
    me.update()
    ob = U.object_from_mesh(name, me, collection, parent=parent)
    mod = ob.modifiers.new("arch_scatter", 'NODES')
    mod.node_group = _scatter_group(proto)
    return ob


# ---------------------------------------------------------------- bmesh shape helpers

def _bm_ellipsoid(bm, center, radii, segs=10, rings=6, rot=None):
    """Ellipsoid (a lathed half circle, so the face order is deterministic, unlike
    bmesh.ops.create_uvsphere). Returns its verts."""
    prof = [(math.sin(math.pi * k / rings), -math.cos(math.pi * k / rings)) for k in range(rings + 1)]
    prof[0] = (0.0, -1.0)
    prof[-1] = (0.0, 1.0)
    vs = U.bm_lathe(bm, prof, segments=segs)
    m = Matrix.Translation(Vector(center))
    if rot is not None:
        m = m @ rot.to_4x4()
    m = m @ Matrix.Diagonal((radii[0], radii[1], radii[2], 1.0))
    bmesh.ops.transform(bm, matrix=m, verts=vs)
    return vs


def _bm_cone(bm, base, tip, r1, r2=0.0, segs=8):
    base, tip = Vector(base), Vector(tip)
    d = tip - base
    res = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs,
                                radius1=r1, radius2=max(r2, 1e-4), depth=d.length)
    m = Matrix.Translation((base + tip) * 0.5) @ U.align_z(d).to_4x4()
    bmesh.ops.transform(bm, matrix=m, verts=res["verts"])
    return res["verts"]


def _bm_prism(bm, outline, y0, y1):
    """Extrude a CCW outline [(x, z), ...] (as seen from -Y) along Y from y0 to y1."""
    vf = [bm.verts.new((x, y0, z)) for x, z in outline]
    vb = [bm.verts.new((x, y1, z)) for x, z in outline]
    bm.faces.new(vf)
    bm.faces.new(list(reversed(vb)))
    n = len(outline)
    for k in range(n):
        k2 = (k + 1) % n
        bm.faces.new((vf[k], vb[k], vb[k2], vf[k2]))
    return vf + vb


def _bm_tube(bm, pts, r, sides=6, taper=None):
    """Simple tube through points (no caps). ``taper`` multiplies r per point."""
    pts = [Vector(p) for p in pts]
    rings = []
    for i, p in enumerate(pts):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, len(pts) - 1)]
        rot = U.align_z(b - a)
        rr = r * (taper[i] if taper else 1.0)
        ring = []
        for k in range(sides):
            ang = TAU * k / sides
            ring.append(bm.verts.new(p + rot @ Vector((math.cos(ang) * rr, math.sin(ang) * rr, 0.0))))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
    return rings


def _sweep(verts, faces, path, profile, scales=None, cap=True, closed_path=False, profiles=None):
    """Append a swept closed ``profile`` [(side, up), ...] (counter-clockwise) along ``path``
    (list of Vectors) to pydata lists (``profiles``: one profile per path point, same vertex
    count, overrides it). Frames: side = tangent x Z (horizontal), up = side x tangent.
    Faces point outward."""
    n = len(path)
    m = len(profile)
    base = len(verts)
    for i in range(n):
        if closed_path:
            a, b = path[(i - 1) % n], path[(i + 1) % n]
        else:
            a, b = path[max(i - 1, 0)], path[min(i + 1, n - 1)]
        t = (b - a)
        t = t.normalized() if t.length > 1e-9 else Vector((1, 0, 0))
        s = t.cross(Z)
        if s.length < 1e-6:
            s = Vector((1, 0, 0))
        s.normalize()
        up = s.cross(t).normalized()
        sc = scales[i] if scales else 1.0
        for (px, py) in (profiles[i] if profiles else profile):
            verts.append(tuple(path[i] + s * (px * sc) + up * (py * sc)))
    rings = n if closed_path else n - 1
    for i in range(rings):
        i2 = (i + 1) % n
        for k in range(m):
            k2 = (k + 1) % m
            faces.append((base + i * m + k, base + i2 * m + k, base + i2 * m + k2, base + i * m + k2))
    if cap and not closed_path:
        faces.append(tuple(base + k for k in range(m)))
        faces.append(tuple(base + (n - 1) * m + k for k in reversed(range(m))))


def _mirror_profile(half):
    """Closed profile from its right half [(x>=0, y), ...] listed bottom to top."""
    left = [(-x, y) for x, y in reversed(half) if x > 1e-9]
    return list(half) + left


# ---------------------------------------------------------------- roof ornament prototypes

def _p_cap(tile_mat):
    """Round tile end cap (wadang), unit radius, facing local -Y."""
    def build(col):
        bm = bmesh.new()
        prof = [(0.0, -0.15), (1.0, -0.15), (1.0, 0.25), (0.78, 0.19), (0.0, 0.28)]
        U.bm_lathe(bm, prof, segments=8)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
        bmesh.ops.rotate(bm, verts=bm.verts[:], matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        _proto_obj(col, "cap", bm, [tile_material(tile_mat)], smooth=math.radians(50))
    return _proto("cap." + tile_mat, build)


def _p_drip(tile_mat):
    """Pointed drip tile (dishui), unit width, hanging down from z=0, facing -Y."""
    def build(col):
        bm = bmesh.new()
        out = [(-0.5, 0.0), (-0.47, -0.16), (-0.33, -0.31), (-0.15, -0.42), (0.0, -0.5),
               (0.15, -0.42), (0.33, -0.31), (0.47, -0.16), (0.5, 0.0)]
        out = list(reversed(out))   # CCW seen from -Y
        _bm_prism(bm, out, -0.07, 0.03)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        _proto_obj(col, "drip", bm, [tile_material(tile_mat)], smooth=math.radians(35))
    return _proto("drip." + tile_mat, build)


def _p_rafter_end(w, h):
    """Painted flying-rafter end plate (bracket_paint, gold rim), true size w x h, facing -Y."""
    key = "rafter_end.%d_%d" % (round(w * 1000), round(h * 1000))

    def build(col):
        bm = _paint_layers(bmesh.new())
        vs = U.bm_box(bm, (w, 0.03, h), (0.0, -0.015, 0.0))
        _tag_piece(bm, vs, 0.1)
        _proto_obj(col, "plate", bm, [_mat("arch_paint_box_fine")], smooth=False)
    return _proto(key, build)


def _p_beast(tile_mat):
    """Seated roof beast (zoushou), unit height, facing local +X, base at z=0 (buried to -0.2):
    haunches, chest, maned head with snout, horns, ears and a raised tail; bevelled."""
    def build(col):
        bm = bmesh.new()
        U.bm_box(bm, (0.5, 0.34, 0.30), (0.0, 0.0, -0.05))                                 # seat block
        _bm_ellipsoid(bm, (-0.09, 0, 0.27), (0.21, 0.155, 0.18), 12, 7)                      # haunches
        _bm_ellipsoid(bm, (0.06, 0, 0.45), (0.13, 0.135, 0.24), 12, 7, rot=Matrix.Rotation(-0.35, 3, 'Y'))
        for sy in (-1, 1):                                                                   # forelegs
            U.bm_box(bm, (0.07, 0.07, 0.34), (0.15, 0.07 * sy, 0.19))
        _bm_ellipsoid(bm, (0.08, 0, 0.66), (0.15, 0.15, 0.12), 12, 6)                        # mane
        _bm_ellipsoid(bm, (0.13, 0, 0.78), (0.13, 0.115, 0.125), 12, 7)                      # head
        _bm_ellipsoid(bm, (0.25, 0, 0.75), (0.08, 0.075, 0.06), 10, 5)                       # snout
        _bm_cone(bm, (0.08, 0.0, 0.88), (-0.06, 0.0, 1.0), 0.05, 0.0, 8)                    # horn
        for s in (-1, 1):
            _bm_cone(bm, (0.08, 0.07 * s, 0.86), (0.03, 0.11 * s, 0.97), 0.032, 0.0, 6)     # ears
        _bm_cone(bm, (-0.24, 0.0, 0.34), (-0.31, 0.0, 0.68), 0.065, 0.012, 8)               # tail
        _proto_obj(col, "beast", bm, [tile_material(tile_mat)], smooth=math.radians(50),
                   bevel=(0.012, 2))
    return _proto("beast." + tile_mat, build)


def _p_immortal(tile_mat):
    """Immortal riding a phoenix (xianren), leads the beast row; unit height, faces +X. The
    rider has a flared robe, folded arms, a round head and a flat official's hat."""
    def build(col):
        bm = bmesh.new()
        U.bm_box(bm, (0.5, 0.3, 0.3), (0.0, 0.0, -0.08))
        _bm_ellipsoid(bm, (0.02, 0, 0.24), (0.25, 0.14, 0.12), 12, 6)                    # bird body
        _bm_cone(bm, (0.16, 0, 0.26), (0.30, 0, 0.42), 0.065, 0.04, 8)                   # neck
        _bm_ellipsoid(bm, (0.32, 0, 0.45), (0.065, 0.05, 0.05), 10, 5)                   # bird head
        _bm_cone(bm, (0.36, 0, 0.45), (0.43, 0, 0.43), 0.025, 0.0, 6)                    # beak
        for s in (-1, 1):                                                                # wings
            _bm_ellipsoid(bm, (-0.02, 0.13 * s, 0.28), (0.18, 0.035, 0.07), 10, 5,
                          rot=Matrix.Rotation(0.3, 3, 'Y'))
        _bm_cone(bm, (-0.18, 0, 0.26), (-0.38, 0, 0.50), 0.09, 0.02, 8)                  # tail
        bm2 = bmesh.new()
        robe = [(0.0, 0.30), (0.135, 0.30), (0.125, 0.36), (0.095, 0.48), (0.085, 0.58),
                (0.10, 0.63), (0.075, 0.67), (0.035, 0.69), (0.0, 0.69)]
        vs = U.bm_lathe(bm2, robe, segments=12)
        bmesh.ops.scale(bm2, vec=(1.0, 1.15, 1.0), verts=vs)
        U.bm_box(bm2, (0.10, 0.17, 0.06), (0.08, 0.0, 0.56))                              # folded arms
        _bm_ellipsoid(bm2, (0.01, 0, 0.745), (0.06, 0.058, 0.068), 10, 6)                  # head
        U.bm_box(bm2, (0.10, 0.17, 0.018), (0.0, 0.0, 0.815))                             # hat brim
        U.bm_box(bm2, (0.075, 0.08, 0.07), (-0.005, 0.0, 0.855))                          # hat crown
        bmesh.ops.remove_doubles(bm2, verts=bm2.verts[:], dist=1e-5)
        _proto_obj(col, "bird", bm, [tile_material(tile_mat)], smooth=math.radians(50), bevel=(0.01, 2))
        _proto_obj(col, "rider", bm2, ["gold"], smooth=math.radians(50), bevel=(0.006, 2))
    return _proto("immortal." + tile_mat, build)


# Chiwen side outlines (x, z), unit height, mouth toward -X, CCW seen from -Y. Three relief
# layers: the full outline (thin, carries snout, jaws and crest), the head and body (thicker)
# and a core block (thickest), so the ornament reads as carved volume from any angle. The open
# mouth (z ~0.13-0.40) swallows the main ridge, whose top sits at z ~0.35.
_CHIWEN_OUT = [(-0.36, 0.00), (0.34, 0.00), (0.38, 0.22), (0.41, 0.46), (0.45, 0.64), (0.46, 0.76),
               (0.41, 0.85), (0.31, 0.91), (0.18, 0.93), (0.08, 0.89), (-0.02, 0.84), (-0.12, 0.79),
               (-0.24, 0.73), (-0.36, 0.67), (-0.46, 0.63), (-0.53, 0.57), (-0.53, 0.48), (-0.46, 0.42),
               (-0.30, 0.405), (-0.18, 0.37), (-0.17, 0.20), (-0.25, 0.135), (-0.40, 0.13),
               (-0.45, 0.085), (-0.43, 0.02)]
_CHIWEN_MID = [(-0.30, 0.0), (0.30, 0.0), (0.34, 0.22), (0.37, 0.46), (0.40, 0.64), (0.40, 0.74),
               (0.34, 0.82), (0.24, 0.86), (0.12, 0.84), (0.0, 0.79), (-0.14, 0.72), (-0.28, 0.665),
               (-0.40, 0.61), (-0.46, 0.545), (-0.44, 0.475), (-0.30, 0.44), (-0.155, 0.40),
               (-0.14, 0.20), (-0.21, 0.155), (-0.36, 0.145), (-0.38, 0.07), (-0.34, 0.02)]
_CHIWEN_CORE = [(-0.22, 0.0), (0.26, 0.0), (0.30, 0.30), (0.32, 0.58), (0.27, 0.72), (0.12, 0.76),
                (-0.04, 0.71), (-0.18, 0.64), (-0.29, 0.58), (-0.31, 0.51), (-0.12, 0.45),
                (-0.10, 0.18)]


def _poly_area_signed(poly):
    a = 0.0
    for i in range(len(poly)):
        x0, z0 = poly[i]
        x1, z1 = poly[(i + 1) % len(poly)]
        a += x0 * z1 - x1 * z0
    return a * 0.5


def _ccw(poly):
    return list(poly) if _poly_area_signed(poly) > 0 else list(reversed(poly))


def _p_chiwen(tile_mat):
    """Chiwen ridge-end ornament (zhengwen), unit height, mouth toward local -X, base at z=0.

    Layered relief body (outline +-0.075, head/body +-0.125, core +-0.17) with an open jaw that
    bites the main ridge, upper fangs, a scalloped back fin, a tapered tail curling outward over
    the top, a small beast head on its back, gold eyes and a thick gold sword handle."""
    def build(col):
        bm = bmesh.new()
        for outline, t in ((_CHIWEN_OUT, 0.075), (_CHIWEN_MID, 0.125), (_CHIWEN_CORE, 0.17)):
            _bm_prism(bm, _ccw(outline), -t, t)
        # scalloped back fin along the outer edge
        fin = [(0.36, 0.14)]
        for k in range(6):
            z0 = 0.18 + k * 0.085
            x0 = 0.385 + 0.07 * (z0 - 0.14)
            fin += [(x0 + 0.06, z0 + 0.02), (x0 + 0.075, z0 + 0.05), (x0 + 0.03, z0 + 0.075)]
        fin += [(0.43, 0.70), (0.36, 0.70)]
        _bm_prism(bm, _ccw(fin), -0.045, 0.045)
        # tail curling outward over the top: a tapered tube on a shrinking spiral
        pts, tap = [], []
        for k in range(26):
            t = k / 25.0
            ang = math.radians(150.0 - 470.0 * t)
            rr = 0.115 * (1.0 - 0.72 * t)
            pts.append((0.355 + math.cos(ang) * rr, 0.0, 0.83 + math.sin(ang) * rr))
            tap.append(1.0 - 0.72 * t)
        rings = _bm_tube(bm, pts, 0.075, 10, taper=tap)
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
        # upper fangs
        for sy in (-1, 1):
            _bm_cone(bm, (-0.43, 0.045 * sy, 0.43), (-0.42, 0.05 * sy, 0.33), 0.026, 0.0, 6)
        # small beast head (beishou) on the back, looking inward
        _bm_ellipsoid(bm, (-0.06, 0.0, 0.83), (0.085, 0.09, 0.075), 10, 6)
        _bm_ellipsoid(bm, (-0.14, 0.0, 0.82), (0.06, 0.06, 0.045), 10, 5)
        for sy in (-1, 1):
            _bm_cone(bm, (-0.04, 0.05 * sy, 0.88), (0.05, 0.07 * sy, 0.95), 0.026, 0.0, 6)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        _proto_obj(col, "body", bm, [tile_material(tile_mat)], smooth=math.radians(35), bevel=(0.011, 2))
        g = bmesh.new()
        for s in (-1, 1):
            _bm_ellipsoid(g, (-0.355, 0.125 * s, 0.575), (0.045, 0.03, 0.04), 10, 6)        # eyes
            _bm_ellipsoid(g, (-0.07, 0.085 * s, 0.85), (0.018, 0.012, 0.016), 8, 4)         # back-beast eyes
        # sword handle (jianba): grip, cross guard and pommel, thick enough to read from the side
        _bm_prism(g, _ccw([(0.02, 0.76), (0.10, 0.76), (0.10, 0.95), (0.13, 0.95), (0.13, 0.985),
                           (0.10, 0.985), (0.10, 1.04), (0.075, 1.07), (0.045, 1.07), (0.02, 1.04),
                           (0.02, 0.985), (-0.01, 0.985), (-0.01, 0.95), (0.02, 0.95)]), -0.055, 0.055)
        bmesh.ops.recalc_face_normals(g, faces=g.faces[:])
        _proto_obj(col, "gold", g, ["gold"], smooth=math.radians(45), bevel=(0.006, 2))
    return _proto("chiwen2." + tile_mat, build)


def _p_finial(kind="gourd", metal="gold"):
    """Roof-top finial (baoding), unit height, base at z=0."""
    def build(col):
        bm = bmesh.new()
        if kind == "pearl":
            prof = [(0.0, 0.0), (0.34, 0.0), (0.36, 0.08), (0.30, 0.12), (0.42, 0.22), (0.30, 0.32),
                    (0.14, 0.36), (0.30, 0.48), (0.34, 0.60), (0.28, 0.74), (0.12, 0.82),
                    (0.06, 0.90), (0.0, 1.0)]
        else:
            prof = [(0.0, 0.0), (0.30, 0.0), (0.32, 0.06), (0.26, 0.10), (0.36, 0.17), (0.24, 0.25),
                    (0.11, 0.29), (0.21, 0.38), (0.25, 0.47), (0.19, 0.56), (0.08, 0.61),
                    (0.15, 0.68), (0.16, 0.75), (0.10, 0.82), (0.04, 0.86), (0.035, 0.94),
                    (0.0, 1.0)]
        U.bm_lathe(bm, prof, segments=20)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        _proto_obj(col, "finial", bm, [metal], smooth=math.radians(40))
    return _proto("finial.%s.%s" % (kind, metal), build)


def _p_stud():
    """Gold door / bargeboard stud, unit radius hemisphere facing -Y."""
    def build(col):
        bm = bmesh.new()
        U.bm_lathe(bm, [(0.0, 0.0), (1.0, 0.0), (0.82, 0.55), (0.0, 1.0)], segments=8)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
        bmesh.ops.rotate(bm, verts=bm.verts[:], matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        _proto_obj(col, "stud", bm, ["gold"], smooth=math.radians(60))
    return _proto("stud", build)


# ======================================================================== roof shape

KINDS = ("xieshan", "wudian", "xuanshan", "yingshan", "pyramid", "round", "skirt")

# tile profile across one course: offsets (in pitches) of the column samples, crest at 0
_U_OFF = (-0.5, -0.21, -0.12, 0.0, 0.12, 0.21)
_U_OFF_LOW = (-0.5, -0.19, 0.0, 0.19)          # detail='low': 4 samples per course
_TUBE_W = 0.21       # tube tile half-width (in pitches)


class RoofShape:
    """Analytic roof surface. Build with :func:`roof_shape`.

    Plan: an eave polygon (rectangle, regular n-gon or circle). For a point at distance d inside
    eave edge i, the top (tile) surface is at ``z_top(d)`` = concave profile (steep at the ridge,
    flat at the eave). Corners get a smooth lift + outward push (``warp``). Panel i is
    parameterised by (a, d): a along the edge from its midpoint, d inward from the eave.
    The roof's local z = 0 is the rafter underside at the column line (where it sits on the
    bracket band); eaves droop below it.

    ``round_top`` > 0 rolls the top of a gable roof into a smooth crest (juanpeng): over the last
    ``round_top`` m of each slope the profile bends to horizontal, so the two slopes and their
    tile courses run over the top without a ridge. ``rot90`` is set by roof_shape when a deep
    footprint was swapped: roof() then turns the built roof by 90 degrees."""

    def __init__(self, kind, width, depth, sides, overhang, rise, curve, lift, push, sweep,
                 gable_inset, cut, tile_pitch, thickness, side_overhang=None, detail="high",
                 corner_k=2.2, round_top=0.0):
        self.kind = kind
        self.rot90 = False
        self.rt = 0.0
        self.detail = detail
        self.sides = sides
        self.ov = ov = overhang
        self.curve = curve
        poly = None
        if kind == "round" or (kind == "skirt" and sides == 0):
            self.base = "round"
            self.rc = width * 0.5
            self.rho = self.rc + ov
            self.span = self.rho
        elif sides >= 5 and kind in ("pyramid", "skirt"):
            self.base = "poly"
            rc = width * 0.5
            self.rc = rc
            ac = rc * math.cos(math.pi / sides)
            self.rho = ac + ov
            R = self.rho / math.cos(math.pi / sides)
            poly = [(R * math.cos(-math.pi / 2 - math.pi / sides + TAU * k / sides),
                     R * math.sin(-math.pi / 2 - math.pi / sides + TAU * k / sides)) for k in range(sides)]
            self.span = self.rho
        else:
            self.base = {"wudian": "hip", "xieshan": "xieshan", "xuanshan": "gable", "yingshan": "gable",
                         "pyramid": "hip", "skirt": "hip"}[kind]
            self.wc, self.dc = width * 0.5, depth * 0.5
            sov = ov if side_overhang is None or self.base != "gable" else side_overhang
            self.We, self.De = self.wc + sov, self.dc + ov
            poly = [(-self.We, -self.De), (self.We, -self.De), (self.We, self.De), (-self.We, self.De)]
            self.span = min(self.We, self.De)
            self.rho = self.span
        self.poly = poly
        self.cut = cut
        if cut is not None:
            self.span = cut
        self.rise = rise
        if round_top > 0 and self.base == "gable":
            self.rt = min(round_top, 0.6 * (self.span - ov))
        self.d1 = self.span - self.rt
        self.pitch = tile_pitch
        self.t_board = thickness[0]
        self.rib = thickness[1]
        self.T = self.t_board + self.rib
        self.z_off = self.T - self.F(ov)
        self.lift, self.push, self.S = lift, push, max(sweep, 1e-3)
        self.K = corner_k
        # edges
        self.edges = []
        if poly is not None:
            n = len(poly)
            for i in range(n):
                v0, v1 = Vector(poly[i]), Vector(poly[(i + 1) % n])
                t = (v1 - v0)
                h = t.length * 0.5
                t.normalize()
                nrm = Vector((t.y, -t.x))
                self.edges.append(dict(v0=v0, v1=v1, mid=(v0 + v1) * 0.5, t=t, n=nrm, h=h))
            # interior angle factors at each vertex (cot of half exterior... tan(alpha/2))
            self.tan_half = []
            self.bis = []
            for k in range(n):
                e0, e1 = self.edges[k - 1], self.edges[k]
                cosang = -(e0["t"].dot(e1["t"]))
                alpha = math.acos(_clamp(cosang, -1.0, 1.0))
                self.tan_half.append(math.tan(alpha * 0.5))
                b = (e0["n"] + e1["n"]).normalized()
                self.bis.append((b, math.sin(alpha * 0.5)))
        # per-edge depth limits and gable
        self.G = None
        self.dg = None
        if self.base == "xieshan":
            self.dg = gable_inset
            self.G = self.We - self.dg
        self.corners = self.base in ("hip", "xieshan", "poly") and lift is not None and \
            (lift > 0 or push > 0)

    # ---- profile
    def _F(self, d):
        q = d / self.span if self.span > 0 else 0.0
        c = self.curve
        if q < 0:
            return self.rise * (1.0 - c) * q
        return self.rise * ((1.0 - c) * q + c * q ** 2.4)

    def _dF(self, d):
        q = max(d, 0.0) / self.span
        c = self.curve
        return self.rise / self.span * ((1.0 - c) + 2.4 * c * q ** 1.4)

    def F(self, d):
        """Profile height (no offset) at inward distance d."""
        if self.rt > 0 and d > self.d1:
            x = min(d, self.span) - self.d1
            return self._F(self.d1) + self._dF(self.d1) * (x - x * x / (2.0 * self.rt))
        return self._F(d)

    def dF(self, d):
        if self.rt > 0 and d > self.d1:
            x = min(d, self.span) - self.d1
            return self._dF(self.d1) * (1.0 - x / self.rt)
        return self._dF(d)

    def z_top(self, d):
        """Tile-surface height (local z) at inward distance d from the eave line."""
        return self.F(d) + self.z_off

    def slope_len(self, d, steps=48):
        """Arc length of the profile from the eave to d (for UVs)."""
        if d <= 0:
            return 0.0
        s = 0.0
        h = d / steps
        for k in range(steps):
            x = (k + 0.5) * h
            s += math.sqrt(1.0 + self.dF(x) ** 2) * h
        return s

    # ---- panels
    def panel_ids(self):
        if self.base == "round":
            return [0]
        if self.base == "gable":
            return [0, 2]
        return list(range(len(self.edges)))

    def d_max(self, i):
        if self.base == "round":
            dm = self.rho * 0.94
        elif self.base == "xieshan":
            dm = self.De if i in (0, 2) else self.dg
        else:
            dm = self.span if self.cut is None else self.cut
            dm = min(dm, self.rho)
        if self.cut is not None:
            dm = min(dm, self.cut)
        return dm

    def a_range(self, i):
        """Eave extent of panel i (a from -h to h); round: the full circumference."""
        if self.base == "round":
            return (-math.pi * self.rho, math.pi * self.rho)
        h = self.edges[i]["h"]
        return (-h, h)

    def d_end(self, i, a):
        """Depth where the tile course at a ends (hip, gable rake, ridge or skirt top)."""
        dm = self.d_max(i)
        if self.base in ("round", "gable"):
            return dm
        h = self.edges[i]["h"]
        if self.base == "xieshan" and i in (0, 2) and abs(a) <= self.G + 1e-6:
            return dm
        n = len(self.edges)
        lo = (a + h) * self.tan_half[i]
        hi = (h - a) * self.tan_half[(i + 1) % n]
        return max(0.0, min(dm, lo, hi))

    def plan(self, i, a, d):
        """Unwarped plan point of panel i at (a, d)."""
        if self.base == "round":
            th = -math.pi / 2 + a / self.rho
            r = self.rho - d
            return Vector((r * math.cos(th), r * math.sin(th)))
        e = self.edges[i]
        return e["mid"] + e["t"] * a - e["n"] * d

    def warp(self, x, y, z):
        """Corner sweep: lift and push near eave corners (smooth, continuous everywhere)."""
        if not self.corners:
            return Vector((x, y, z))
        p = Vector((x, y))
        ds = [(e["v0"] - p).dot(e["n"]) for e in self.edges]
        S, K = self.S, self.K
        lift = 0.0
        push = Vector((0.0, 0.0))
        n = len(self.edges)
        for k in range(n):
            e1, e2 = max(ds[k - 1], 0.0), max(ds[k], 0.0)
            if e1 >= S or e2 >= S:
                continue
            c = (1.0 - e1 / S) ** K * (1.0 - e2 / S) ** K
            lift += self.lift * c
            push += self.bis[k][0] * (self.push * c)
        return Vector((x + push.x, y + push.y, z + lift))

    def pt(self, i, a, d, dz=0.0):
        """Warped 3D point on panel i at (a, d), ``dz`` above the tile surface."""
        q = self.plan(i, a, d)
        return self.warp(q.x, q.y, self.z_top(d) + dz)

    def hip_pt(self, k, d, dz=0.0):
        """Warped point on the hip line at polygon vertex k, depth d."""
        b, s = self.bis[k]
        q = self.edges[k]["v0"] - b * (d / s)
        return self.warp(q.x, q.y, self.z_top(d) + dz)

    # ---- tiles
    def corr(self, a):
        """Tile-course height offset at a (in meters): tube crest / pan channel."""
        p = self.pitch
        u = a / p
        u -= round(u)
        au = abs(u)
        if au <= _TUBE_W:
            return 0.22 * p * math.sqrt(max(0.0, 1.0 - (au / _TUBE_W) ** 2))
        return -0.06 * p * math.sin(math.pi * (au - _TUBE_W) / (1.0 - 2.0 * _TUBE_W))

    def rows(self, dm, extra=()):
        """Row depths from the eave to dm: dense near the eave (corner sweep), sparse higher up."""
        s0 = _clamp(0.065 * self.span, 0.16, 0.28)
        s1 = _clamp(0.1 * self.span, 0.26, 0.75)
        if self.detail == "low":
            s0, s1 = s0 * 1.6, s1 * 1.5
        out = [0.0]
        d = 0.0
        while d < dm - 1e-6:
            d += _lerp(s0, s1, _smooth01(d / max(dm, 1e-6) * 1.4))
            out.append(min(d, dm))
        for e in extra:
            if 0.0 < e < dm:
                out.append(e)
        out = sorted(set(round(v, 5) for v in out))
        return out

    def a_samples(self, i, extra=()):
        lo, hi = self.a_range(i)
        p = self.pitch
        out = []
        k0 = int(math.floor(lo / p)) - 1
        k1 = int(math.ceil(hi / p)) + 1
        offs = _U_OFF_LOW if self.detail == "low" else _U_OFF
        for k in range(k0, k1 + 1):
            for u in offs:
                a = (k + u) * p
                if lo + 1e-6 < a < hi - 1e-6:
                    out.append(a)
        out += [lo, hi] + [e for e in extra if lo < e < hi]
        out = sorted(set(round(v, 6) for v in out))
        return out


def roof_shape(width, depth=None, kind="xieshan", sides=4, rise=None, overhang=None, curve=0.5,
               corner_lift=None, corner_push=None, sweep=None, gable_inset=None, top_inset=None,
               tile_pitch=None, thickness=None, side_overhang=None, detail="high"):
    """Compute a :class:`RoofShape` (no objects). Same parameters as :func:`roof`; composites
    use it to plan heights before building. See roof() for the meaning of each parameter."""
    if kind not in KINDS:
        raise ValueError("roof kind %r not in %s" % (kind, KINDS))
    depth = width if depth is None else depth
    if kind in ("pyramid", "round"):
        depth = width
    if kind == "round":
        sides = 0
    rect = not (kind in ("round", "pyramid") or (kind == "skirt" and sides != 4))
    if rect and kind in ("xieshan", "wudian", "xuanshan", "yingshan") and depth > width:
        raise ValueError("roof: width must be >= depth (rotate the roof instead)")
    small = min(width, depth) * 0.5
    polygonal = kind in ("pyramid", "round") or (kind == "skirt" and sides != 4)
    if polygonal:
        small = width * 0.5 * (math.cos(math.pi / sides) if sides >= 3 else 1.0)
    if overhang is None:
        overhang = _clamp(0.85 + 0.23 * small, 0.9, 3.6)
    span_c = small
    span = span_c + overhang
    cut = None
    if kind == "skirt":
        inset = top_inset if top_inset is not None else 0.5 * span_c
        cut = overhang + inset
    if rise is None:
        if kind == "skirt":
            rise = 0.48 * cut
        elif kind in ("pyramid", "round"):
            rise = 0.95 * span
        else:
            rise = 0.62 * span
    if tile_pitch is None:
        tile_pitch = _clamp(0.2 + 0.02 * span, 0.24, 0.44)
    if kind == "round" or (kind == "skirt" and sides == 0):
        n = max(8, round(TAU * span / tile_pitch))      # whole number of courses around
        tile_pitch = TAU * span / n
    if thickness is None:
        tb = _clamp(0.1 + 0.014 * span, 0.12, 0.3)
        thickness = (tb, _clamp(0.42 * tile_pitch, 0.1, 0.2))
    hipped = kind in ("xieshan", "wudian", "pyramid", "skirt")
    if corner_lift is None:
        corner_lift = 0.55 * overhang if hipped else 0.0
    if corner_push is None:
        corner_push = 0.32 * overhang if hipped else 0.0
    if sweep is None:
        sweep = 1.35 * overhang + 0.12 * span_c
    if kind == "xieshan" and gable_inset is None:
        gable_inset = overhang + 0.14 * span_c
    if gable_inset is not None:
        gable_inset = min(gable_inset, 0.8 * span)
    if kind == "yingshan" and side_overhang is None:
        side_overhang = 0.35
    return RoofShape(kind, width, depth, sides, overhang, rise, curve, corner_lift, corner_push,
                     sweep, gable_inset, cut, tile_pitch, thickness, side_overhang, detail)


# ======================================================================== roof meshes

def _roof_top_mesh(sh, name, collection, parent, tile_mat, fascia_mat):
    """Corrugated tile surface + fascia strip (+ rake closures). Returns the object."""
    verts, faces, mats, uvs_v = [], [], [], []
    lap = 0.78 * sh.pitch
    fade_len = 0.4 * max(sh.pitch / 0.35, 0.6)
    for i in sh.panel_ids():
        dm = sh.d_max(i)
        extra = [sh.G, -sh.G] if (sh.base == "xieshan" and i in (0, 2)) else []
        cols_a = sh.a_samples(i, extra)
        rows = sh.rows(dm, [sh.dg] if sh.dg else [])
        s_rows = {d: sh.slope_len(d) for d in rows}
        cols = []
        bottoms = []
        lo, hi = sh.a_range(i)
        flatten_ends = sh.base in ("hip", "xieshan", "poly")
        for a in cols_a:
            de = sh.d_end(i, a)
            ds = [d for d in rows if d < de - 1e-4] + [de] if de > 1e-4 else [0.0]
            clipped = de < dm - 1e-4
            ids = []
            for d in ds:
                f = 1.0
                if clipped:
                    f = _smooth01((de - d) / fade_len)
                if sh.base == "round":
                    f *= (sh.rho - d) / sh.rho
                if flatten_ends and (abs(a - lo) < 1e-6 or abs(a - hi) < 1e-6):
                    f = 0.0
                dz = sh.corr(a) * f
                ids.append(len(verts))
                verts.append(tuple(sh.pt(i, a, d, dz)))
                s = s_rows.get(d)
                if s is None:
                    s = sh.slope_len(d)
                uvs_v.append((a / sh.pitch, s / lap))
            cols.append(ids)
            # fascia bottom vertex (board underside at the eave)
            bottoms.append(len(verts))
            verts.append(tuple(sh.pt(i, a, 0.0, -sh.t_board)))
            uvs_v.append((a / sh.pitch, -0.5))
        ncol = len(cols)
        closed = sh.base == "round"
        for c in range(ncol if closed else ncol - 1):
            A, B = cols[c], cols[(c + 1) % ncol]
            if closed and c == ncol - 1:
                continue  # round: first and last sample coincide (a_range is a full circle)
            n = min(len(A), len(B))
            for j in range(n - 1):
                faces.append((A[j], B[j], B[j + 1], A[j + 1]))
                mats.append(0)
            if len(A) > n:
                ap = B[n - 1]
                for j in range(n - 1, len(A) - 1):
                    faces.append((A[j], ap, A[j + 1]))
                    mats.append(0)
            elif len(B) > n:
                ap = A[n - 1]
                for j in range(n - 1, len(B) - 1):
                    faces.append((ap, B[j], B[j + 1]))
                    mats.append(0)
            # fascia
            faces.append((A[0], bottoms[c], bottoms[(c + 1) % ncol], B[0]))
            mats.append(1)
        # rake closures (gable edges, xieshan gable edges)
        rakes = []
        if sh.base == "gable":
            rakes = [(0, -1), (ncol - 1, 1)]
        elif sh.base == "xieshan" and i in (0, 2):
            for c, a in enumerate(cols_a):
                if abs(abs(a) - sh.G) < 1e-6:
                    rakes.append((c, 1 if a > 0 else -1))
        for c, sgn in rakes:
            a = cols_a[c]
            ids = cols[c]
            d_list = [d for d in rows if d < sh.d_end(i, a) - 1e-4] + [sh.d_end(i, a)]
            if sh.base == "xieshan":
                # only the part above the gable foot is an open edge
                keep = [k for k, d in enumerate(d_list) if d >= sh.dg - 1e-4]
                if keep:
                    keep = [max(keep[0] - 1, 0)] + keep
            else:
                keep = list(range(len(d_list)))
            low = []
            for k in keep:
                low.append(len(verts))
                verts.append(tuple(sh.pt(i, a, d_list[k], -sh.T)))
                uvs_v.append((a / sh.pitch, 0.0))
            # rake direction: panel 0 a>0 faces +x; panel 2 is mirrored (its +a is -x)
            flip = (sgn < 0)
            for k in range(len(keep) - 1):
                t0, t1 = ids[keep[k]], ids[keep[k + 1]]
                b0, b1 = low[k], low[k + 1]
                f = (t0, b0, b1, t1)
                faces.append(tuple(reversed(f)) if flip else f)
                mats.append(1)
    uvs = [uvs_v[v] for f in faces for v in f]
    ob = U.mesh_from_pydata(name, verts, faces, collection, materials=[tile_mat, fascia_mat],
                            smooth=math.radians(52), material_indices=mats, uvs=uvs, parent=parent)
    return ob


def _roof_soffit_mesh(sh, name, collection, parent, board_mat, rafter_mat):
    """Underside: boards with rafter ribs (two paints), rib ends at the eave. Returns
    (object, rafter_end_frames)."""
    verts, faces, mats = [], [], []
    p = sh.pitch
    wr = 0.24 * p
    ends = []
    for i in sh.panel_ids():
        dm = sh.d_max(i)
        lo, hi = sh.a_range(i)
        extra = [sh.G, -sh.G] if (sh.base == "xieshan" and i in (0, 2)) else []
        # columns: (a, is_rib)
        cols_spec = [(lo, False)]
        k0 = int(math.floor(lo / p)) - 1
        k1 = int(math.ceil(hi / p)) + 1
        ribs = []
        for k in range(k0, k1 + 1):
            ac = (k + 0.5) * p
            if sh.detail != "low" and lo + wr + 0.02 < ac < hi - wr - 0.02:
                ribs.append(ac)
        if sh.detail == "low":
            nseg = max(1, int((hi - lo) / 0.4))
            cols_spec += [(lo + (hi - lo) * j / nseg, False) for j in range(1, nseg)]
        for ac in ribs:
            cols_spec += [(ac - wr, False), (ac - wr, True), (ac + wr, True), (ac + wr, False)]
        for e in extra:
            cols_spec.append((e, False))
        cols_spec.append((hi, False))
        cols_spec.sort(key=lambda c: (c[0], 0 if not c[1] else 1))
        # reorder so the left wall of each rib goes board->rib and the right wall rib->board
        fixed = []
        k = 0
        while k < len(cols_spec):
            a, r = cols_spec[k]
            if k + 1 < len(cols_spec) and abs(cols_spec[k + 1][0] - a) < 1e-9:
                pair = [cols_spec[k], cols_spec[k + 1]]
                prev_rib = fixed[-1][1] if fixed else False
                pair.sort(key=lambda c: c[1] == prev_rib, reverse=True)
                fixed += pair
                k += 2
            else:
                fixed.append((a, r))
                k += 1
        rows = sh.rows(dm, [sh.dg] if sh.dg else [])
        rows = rows[::2] + ([rows[-1]] if (len(rows) - 1) % 2 else [])
        cols = []
        for a, rib in fixed:
            de = sh.d_end(i, a)
            ds = [d for d in rows if d < de - 1e-4] + [de] if de > 1e-4 else [0.0]
            dz = -sh.t_board - (sh.rib if rib else 0.0)
            ids = []
            for d in ds:
                ids.append(len(verts))
                verts.append(tuple(sh.pt(i, a, d, dz)))
            cols.append((ids, rib, a))
        for c in range(len(cols) - 1):
            (A, ra, aa), (B, rb, ab) = cols[c], cols[c + 1]
            mi = 1 if (ra or rb or sh.detail == "low") else 0
            n = min(len(A), len(B))
            for j in range(n - 1):
                faces.append((A[j + 1], B[j + 1], B[j], A[j]))
                mats.append(mi)
            if len(A) > n:
                ap = B[n - 1]
                for j in range(n - 1, len(A) - 1):
                    faces.append((A[j + 1], ap, A[j]))
                    mats.append(mi)
            elif len(B) > n:
                ap = A[n - 1]
                for j in range(n - 1, len(B) - 1):
                    faces.append((B[j + 1], B[j], ap))
                    mats.append(mi)
        # rib end faces at the eave + painted end plates
        for c in range(len(cols) - 3):
            (A, ra, aa), (B, rb, ab), (C, rc_, ac_), (D, rd, ad) = cols[c:c + 4]
            if (not ra) and rb and rc_ and (not rd) and abs(aa - ab) < 1e-9 and abs(ac_ - ad) < 1e-9:
                faces.append((A[0], B[0], C[0], D[0]))
                mats.append(1)
                amid = 0.5 * (ab + ac_)
                de = sh.d_end(i, amid)
                if de > 0.3:
                    ends.append((i, amid))
    ob = U.mesh_from_pydata(name, verts, faces, collection, materials=[board_mat, rafter_mat],
                            smooth=math.radians(40), material_indices=mats, parent=parent)
    return ob, ends


# ---------------------------------------------------------------- ridges & ornaments

def _ridge_dims(sh, ridge_h=None):
    span = sh.span if sh.cut is None else sh.rho
    h = ridge_h if ridge_h is not None else _clamp(0.075 * span + 0.12, 0.28, 1.25)
    return dict(h=h, w=0.5 * h + 0.12, hh=0.62 * h, hw=0.38 * h + 0.12)


def _main_profile(w, h, drop):
    half = [(0.5 * w, -drop), (0.5 * w, 0.10 * h), (0.43 * w, 0.14 * h), (0.43 * w, 0.62 * h),
            (0.5 * w, 0.66 * h), (0.5 * w, 0.75 * h), (0.38 * w, 0.79 * h), (0.36 * w, 0.87 * h),
            (0.27 * w, 0.95 * h), (0.14 * w, 0.99 * h), (0.0, 1.0 * h)]
    return _mirror_profile(half)


def _hip_profile(w, h, drop):
    half = [(0.5 * w, -drop), (0.5 * w, 0.30 * h), (0.42 * w, 0.36 * h), (0.42 * w, 0.62 * h),
            (0.36 * w, 0.72 * h), (0.31 * w, 0.84 * h), (0.2 * w, 0.95 * h), (0.0, 1.0 * h)]
    return _mirror_profile(half)


def _sample_line(p0, p1, step):
    n = max(1, int(math.ceil((p1 - p0).length / step)))
    return [p0.lerp(p1, k / n) for k in range(n + 1)]


def _path_len(path):
    return sum((path[k + 1] - path[k]).length for k in range(len(path) - 1))


def _path_at(path, s):
    """Point and unit tangent at arc length s along a polyline (clamped)."""
    acc = 0.0
    for k in range(len(path) - 1):
        seg = path[k + 1] - path[k]
        L = seg.length
        if acc + L >= s or k == len(path) - 2:
            t = 0.0 if L < 1e-9 else _clamp((s - acc) / L, 0.0, 1.0)
            return path[k].lerp(path[k + 1], t), (seg.normalized() if L > 1e-9 else Vector((1, 0, 0)))
        acc += L
    return path[-1], Vector((1, 0, 0))


class _Ornaments:
    """Collects instance matrices per prototype and the ridge mesh pydata of one roof
    (``rm``: material index per ridge face, 0 = glaze, 1 = gold trim)."""

    def __init__(self):
        self.mats = {}
        self.rv, self.rf, self.rm = [], [], []
        self.tips = []          # (corner point, outward direction) of every hip tip

    def add(self, proto, m):
        self.mats.setdefault(proto.name, (proto, []))[1].append(m)

    def sweep(self, path, profile, mi=0, **kw):
        self.rm.extend([0] * (len(self.rf) - len(self.rm)))
        n0 = len(self.rf)
        _sweep(self.rv, self.rf, path, profile, **kw)
        self.rm.extend([mi] * (len(self.rf) - n0))

    def faces_mi(self):
        """Material index per ridge face (faces swept directly with _sweep count as glaze)."""
        return self.rm + [0] * (len(self.rf) - len(self.rm))


def _hip_ridge(sh, orn, path_in, dims, beasts, protos, tip=True):
    """Hip ridge along ``path_in`` (from the corner inward), with an upturned tip, an immortal,
    ``beasts`` small beasts and a larger beast head (chuishou) behind them."""
    hw, hh = dims["hw"], dims["hh"]
    path = list(path_in)
    if tip and len(path) >= 2:
        p0 = path[0]
        t = (path[0] - path[min(3, len(path) - 1)]).normalized()
        ext = 0.9 * hw + 0.25
        tipp = []
        for k in range(4, 0, -1):
            u = k / 4.0
            tipp.append(p0 + t * (ext * u) + Z * (ext * 0.75 * u * u))
        path = tipp + path
        scales = [1.0 - 0.32 * (k / 4.0) for k in range(4, 0, -1)] + [1.0] * len(path_in)
    else:
        scales = None
    drop = min(hw * 0.5 * 0.8 + 0.05, 0.85 * sh.t_board)
    profs = None
    if tip and len(path) > len(path_in):
        # the up-swept tip hangs past the eave: no buried keel under it
        ntip = len(path) - len(path_in)
        profs = [_hip_profile(hw, hh, 0.02 + (drop - 0.02) * (k / ntip) ** 2) for k in range(ntip)] + \
                [_hip_profile(hw, hh, drop)] * len(path_in)
    orn.sweep(path, _hip_profile(hw, hh, drop), scales=scales, profiles=profs)
    if not beasts or protos is None:
        return
    # walk inward from the corner (index of the original corner point = 4 if tipped)
    start = path_in[0]
    inward = list(path_in)
    L = _path_len(inward)
    bh = _clamp(1.25 * hh, 0.25, 1.1)
    spacing = 1.05 * bh * 0.62 + 0.08
    s = 0.15 * bh
    items = [("immortal", 1.05)] + [("beast", 1.0)] * beasts
    for kind, scl in items:
        if s > L * 0.82:
            break
        p, t = _path_at(inward, s)
        out_dir = -t
        m = _upright(out_dir, p + Z * (hh * 0.92), bh * scl)
        orn.add(protos[kind], m)
        s += spacing * (1.15 if kind == "immortal" else 1.0)
    s += spacing * 0.6
    if s < L * 0.92:
        p, t = _path_at(inward, s)
        orn.add(protos["beast"], _upright(-t, p + Z * (hh * 0.9), bh * 1.55))
    return start


def _eave_items(sh, orn, protos, rafter_ends, dims):
    """Tile end caps, drip tiles and painted rafter-end plates along every eave."""
    p = sh.pitch
    rcap = 0.245 * p
    for i in sh.panel_ids():
        lo, hi = sh.a_range(i)
        margin = 0.0 if sh.base == "gable" else max(0.55 * dims["hw"] + 0.1, 0.6 * p)
        if sh.base == "round":
            margin = 0.0
            lo, hi = lo + 0.5 * p, hi - 0.5 * p
        k0 = int(math.ceil((lo + margin) / p))
        k1 = int(math.floor((hi - margin) / p))
        for k in range(k0, k1 + 1):
            items = (("cap", k * p),) if sh.detail == "low" else (("cap", k * p), ("drip", (k + 0.5) * p))
            for kind, a in items:
                if not (lo + margin <= a <= hi - margin):
                    continue
                P0 = sh.pt(i, a, 0.0)
                T = sh.pt(i, a, 0.12) - P0
                E = sh.pt(i, a + 0.05, 0.0) - sh.pt(i, a - 0.05, 0.0)
                if kind == "cap":
                    m = _frame(E, T, P0 - T.normalized() * 0.01, (rcap, rcap, rcap))
                    orn.add(protos["cap"], m)
                else:
                    w = 0.62 * p
                    N = E.cross(T).normalized()
                    org = P0 + N * (-0.05 * p) - T.normalized() * 0.012
                    orn.add(protos["drip"], _frame(E, T, org, (w, w, w)))
    # rafter end plates
    if rafter_ends:
        wr = 0.24 * sh.pitch
        proto = _p_rafter_end(round(2 * wr * 0.86, 3), round(sh.rib * 0.84, 3))
        for i, a in rafter_ends:
            P0 = sh.pt(i, a, 0.0, -sh.t_board - sh.rib * 0.5)
            P1 = sh.pt(i, a, 0.1, -sh.t_board - sh.rib * 0.5)
            inward = P1 - P0
            E = sh.pt(i, a + 0.05, 0.0) - sh.pt(i, a - 0.05, 0.0)
            E.z = 0.0
            inward.z = 0.0
            orn.add(proto, _frame(E, inward, P0 - inward.normalized() * 0.004))


def _roof_ridges(sh, orn, dims, tile_base, ornaments, beasts, finial):
    """Main ridge + chiwen, hips with beasts, xieshan rakes/boji, skirt top ridge, finial."""
    full = ornaments != "none"
    protos = None
    if full:
        protos = dict(beast=_p_beast(tile_base), immortal=_p_immortal(tile_base))
    h, w = dims["h"], dims["w"]
    step = 0.5
    if sh.base in ("hip", "xieshan", "gable") and sh.cut is None:
        zr = sh.z_top(sh.De)
        if sh.base == "hip":
            xr = sh.We - sh.De
        elif sh.base == "xieshan":
            xr = sh.G
        else:
            xr = sh.We
        drop = sh.dF(sh.De) * w * 0.5 + 0.15 + 0.22 * sh.pitch
        if xr > 0.05:
            ext = 0.0 if sh.base == "hip" else -0.02
            path = _sample_line(Vector((-xr - ext, 0, zr)), Vector((xr + ext, 0, zr)), 2.0)
            orn.sweep(path, _main_profile(w, h, drop))
            if full and ornaments in ("full", "chiwen"):
                ch = _p_chiwen(tile_base)
                hc = 2.05 * h
                xc = xr - 0.12 * hc if sh.base != "hip" else xr + 0.05 * hc
                for sgn in (-1, 1):
                    m = Matrix.Translation((sgn * xc, 0, zr - 0.02)) @ \
                        Matrix.Rotation(0.0 if sgn > 0 else math.pi, 4, 'Z') @ Matrix.Scale(hc, 4)
                    orn.add(ch, m)
            elif full:
                # simple upturned ridge-end curls
                for sgn in (-1, 1):
                    p0 = Vector((sgn * xr, 0, zr + h * 0.5))
                    pts = [p0 + Vector((sgn * 0.3 * h * u, 0, 0.9 * h * u * u)) for u in (0.0, 0.5, 1.0)]
                    orn.sweep(pts, _hip_profile(w * 0.8, h * 0.6, h * 0.3),
                           scales=[1.0, 0.85, 0.6])
    if sh.base == "hip":
        n = len(sh.edges)
        top = sh.d_max(0) if sh.cut is None else sh.cut
        for k in range(n):
            if sh.cut is None:
                dend = min(sh.De, sh.We)
            else:
                dend = sh.cut
            ds = [dend * (j / 14.0) ** 1.4 for j in range(15)]
            path = [sh.hip_pt(k, d) for d in ds]
            _hip_ridge(sh, orn, path, dims, beasts, protos)
        if sh.cut is not None:
            _skirt_top_ridge(sh, orn, dims)
    elif sh.base == "poly":
        n = len(sh.edges)
        dend = sh.rho * 0.97 if sh.cut is None else sh.cut
        for k in range(n):
            ds = [dend * (j / 12.0) ** 1.4 for j in range(13)]
            path = [sh.hip_pt(k, d) for d in ds]
            _hip_ridge(sh, orn, path, dims, beasts, protos)
        if sh.cut is not None:
            _skirt_top_ridge(sh, orn, dims)
    elif sh.base == "xieshan":
        for k in range(4):
            ds = [sh.dg * (j / 10.0) ** 1.3 for j in range(11)]
            path = [sh.hip_pt(k, d) for d in ds]
            _hip_ridge(sh, orn, path, dims, beasts, protos)
        # rake ridges (chuiji) along x = +-G from the ridge down to the gable foot
        yv = sh.De - sh.dg
        vw = dims["hw"] * 1.05
        drop = min(vw * 0.5 * 0.8 + 0.12, 0.85 * sh.t_board + 0.05)
        for sx in (-1, 1):
            for sy in (-1, 1):
                pts = []
                for j in range(13):
                    yy = yv * j / 12.0
                    d = sh.De - yy
                    q = sh.warp(sx * (sh.G - 0.5 * vw), sy * yy, sh.z_top(d))
                    pts.append(q)
                pts.reverse()  # from the foot up to the ridge
                orn.sweep(pts, _hip_profile(vw, dims["hh"] * 1.1, drop))
                if full:
                    # chuishou beast head at the foot of the rake ridge
                    tdir = Vector((0, sy, 0))
                    orn.add(protos["beast"], _upright(tdir, pts[0] + Z * (dims["hh"] * 0.95),
                                                      _clamp(1.25 * dims["hh"], 0.25, 1.1) * 1.5))
        # boji: small ridge where the side slope meets the gable
        for sx in (-1, 1):
            zz = sh.z_top(sh.dg)
            pts = [sh.warp(sx * (sh.G + 0.06), y, zz) for y in (-yv, 0.0, yv)]
            orn.sweep(pts, _hip_profile(dims["hw"] * 0.75, dims["hh"] * 0.55, 0.25))
    elif sh.base == "gable":
        vw = dims["hw"] * 1.05
        drop = vw * 0.5 * 0.8 + 0.12
        for sx in (-1, 1):
            for sy in (-1, 1):
                pts = []
                for j in range(15):
                    yy = sh.De * j / 14.0
                    pts.append(sh.warp(sx * (sh.We - 0.5 * vw), sy * yy, sh.z_top(sh.De - yy)))
                pts.reverse()
                _hip_ridge(sh, orn, pts, dims, min(beasts, 3) if beasts else 0, protos, tip=True)
    elif sh.base == "round" and sh.cut is not None:
        _skirt_top_ridge(sh, orn, dims)
    # finial on pyramids / round roofs
    if finial and sh.cut is None and sh.base in ("poly", "round") or \
            (finial and sh.cut is None and sh.base == "hip" and sh.We - sh.De < 0.05):
        zt = sh.z_top(sh.rho if sh.base != "hip" else sh.De)
        fh = _clamp(0.32 * sh.rho + 0.4, 0.8, 4.5)
        orn.add(_p_finial("gourd", finial if isinstance(finial, str) else "gold"),
                Matrix.Translation((0, 0, zt - 0.05 * fh)) @ Matrix.Scale(fh, 4))


def _skirt_top_ridge(sh, orn, dims):
    """Ridge running around the top edge of a skirt roof where it meets the wall (weiji)."""
    d = sh.cut
    if sh.base == "round":
        r = sh.rho - d + 0.05
        pts = [Vector((r * math.cos(TAU * k / 48), r * math.sin(TAU * k / 48), sh.z_top(d)))
               for k in range(48)]
    else:
        pts = []
        for k in range(len(sh.edges)):
            pts.append(sh.hip_pt(k, d - 0.02))
        dense = []
        for k in range(len(pts)):
            a, b = pts[k], pts[(k + 1) % len(pts)]
            dense += _sample_line(a, b, 2.0)[:-1]
        pts = dense
    hw, hh = dims["hw"] * 0.85, dims["hh"] * 0.8
    orn.sweep(pts, _hip_profile(hw, hh, 0.3), closed_path=True)


def _gable_parts(sh, root, collection, dims, mode="full"):
    """Xieshan gable triangle (red with gold medallion), bargeboards with gold studs.
    mode: 'full', 'board' (bargeboards only) or 'none'."""
    objs = []
    if sh.base not in ("xieshan", "gable") or mode == "none":
        return objs
    if sh.base == "xieshan":
        xg = sh.G - 0.22
        yv = sh.De - sh.dg
    else:
        xg = sh.wc
        yv = sh.dc
    verts, faces = [], []
    stud_m = []
    for sx in (-1, 1):
        # gable infill wall
        base = len(verts)
        n = 16
        zf = sh.z_top(sh.dg) - 0.25 if sh.base == "xieshan" else -0.02
        top = []
        for j in range(n + 1):
            y = -yv + 2 * yv * j / n
            dd = sh.De - abs(y)
            top.append(sh.warp(sx * xg, y, sh.z_top(dd) - sh.t_board))
        bot = [sh.warp(sx * xg, -yv + 2 * yv * j / n, zf) for j in range(n + 1)]
        for j in range(n + 1):
            verts.append(tuple(bot[j]))
            verts.append(tuple(top[j]))
        for j in range(n):
            a0, a1, b0, b1 = base + 2 * j, base + 2 * j + 1, base + 2 * j + 2, base + 2 * j + 3
            faces.append((a0, b0, b1, a1) if sx > 0 else (a0, a1, b1, b0))
    gable_obj = None
    if verts and mode == "full":
        gable_obj = U.mesh_from_pydata(_child(root, "gable"), verts, faces, collection,
                                       materials=[_mat("arch_paint_red")], smooth=False, parent=root)
        objs.append(gable_obj)
    # bargeboards along the rakes
    bv, bf = [], []
    bh = _clamp(0.9 * sh.T + 0.25 * dims["h"], 0.3, 1.0)
    xb = (sh.G + 0.03) if sh.base == "xieshan" else (sh.We + 0.03)
    yb = yv if sh.base == "xieshan" else sh.De
    for sx in (-1, 1):
        for sy in (-1, 1):
            pts = []
            n = 14
            for j in range(n + 1):
                yy = yb * j / n
                pts.append(sh.warp(sx * xb, sy * yy, sh.z_top(sh.De - yy) + 0.04))
            # rectangle profile hanging down: (side, up)
            prof = [(-0.04, -bh), (0.04, -bh), (0.04, 0.0), (-0.04, 0.0)]
            _sweep(bv, bf, pts, prof)
            # gold studs in quincunx clusters along the board
            L = _path_len(pts)
            s = 0.9
            while s < L - 0.5:
                p, t = _path_at(pts, s)
                outward = Vector((sx, 0, 0))
                updir = (t.cross(outward)).normalized()
                if updir.z < 0:
                    updir = -updir
                c = p - updir * (bh * 0.5) + outward * 0.045
                r = bh * 0.07
                for ox, oy in ((0, 0), (-1, -1), (1, -1), (-1, 1), (1, 1)):
                    q = c + t * (ox * bh * 0.16) + updir * (oy * bh * 0.16)
                    stud_m.append(_frame(t if sx > 0 else -t, -outward, q, (r, r, r)))
                s += max(1.2, bh * 2.4)
    if bv:
        objs.append(U.mesh_from_pydata(_child(root, "bargeboard"), bv, bf, collection,
                                       materials=[_mat("arch_paint_red")], smooth=False, parent=root))
    if stud_m:
        objs.append(scatter(_child(root, "studs"), collection, _p_stud(), stud_m, parent=root))
    # gold medallion on the xieshan gable
    if sh.base == "xieshan":
        zc = sh.z_top(sh.dg) + 0.55 * (sh.z_top(sh.De) - sh.z_top(sh.dg))
        r = _clamp(0.12 * yv, 0.25, 1.0)
        mats = []
        for sx in (-1, 1):
            mats.append(Matrix.Translation((sx * (xg + 0.02), 0, zc)) @
                        Matrix.Rotation(sx * math.pi / 2, 4, 'Z') @ Matrix.Scale(r, 4))
        objs.append(scatter(_child(root, "medallion"), collection, _p_medallion(), mats, parent=root))
    return objs


def _p_medallion():
    """Gold gable ornament: a round boss with ribbon tails, unit radius, facing -Y."""
    def build(col):
        bm = bmesh.new()
        U.bm_lathe(bm, [(0.0, 0.0), (1.0, 0.0), (0.95, 0.12), (0.7, 0.16), (0.62, 0.1),
                        (0.3, 0.12), (0.0, 0.22)], segments=20)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
        bmesh.ops.rotate(bm, verts=bm.verts[:], matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
        for s in (-1, 1):
            pts = [(s * (0.9 + 0.5 * t), -0.05, -0.2 - 0.9 * t * t + 0.25 * math.sin(t * 5)) for t in
                   (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)]
            _bm_tube(bm, pts, 0.09, 6)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        _proto_obj(col, "medallion", bm, ["gold"], smooth=math.radians(45))
    return _proto("medallion", build)


# ======================================================================== roof()

def roof(name, collection, width, depth=None, kind="xieshan", sides=4, rise=None, overhang=None,
         curve=0.5, corner_lift=None, corner_push=None, sweep=None, tile_mat="roof_tile_teal",
         tile_pitch=None, thickness=None, ridge_h=None, beasts=None, ornaments="full",
         gable_inset=None, top_inset=None, side_overhang=None, finial="gold",
         fascia_mat="arch_paint_red", board_mat="arch_paint_red", rafter_mat="arch_paint_teal",
         gable_parts="full", detail="high", parent=None, location=(0, 0, 0), rotation_z=0.0):
    """Chinese roof over a ``width`` x ``depth`` column footprint (for 'pyramid'/'round':
    ``width`` = diameter of the column circle). Local z = 0 is the rafter underside at the
    column line, i.e. place the root on top of the bracket band; the eaves droop below it.

    kind: 'xieshan' (hip-and-gable), 'wudian' (hip), 'xuanshan' (overhanging gable),
    'yingshan' (flush gable), 'pyramid' (``sides`` >= 3; 4 = square), 'round' (conical), or
    'skirt' (lower eave of a double roof: a ring from the eave up to ``top_inset`` inside the
    column line; ``sides`` 4 = rectangle, >= 5 polygon, 0 = round).
    rise: eave-to-ridge height (auto ~0.62 x half-span); overhang: eave beyond the columns
    (auto 0.9-3.4 m); curve: concavity 0-1; corner_lift / corner_push / sweep: qiao jiao corner
    sweep (height, outward push, length along the eave); tile_mat: materials.py tile name;
    tile_pitch: tube-tile spacing; ridge_h: main ridge height; beasts: beasts per hip (auto);
    ornaments: 'full' (chiwen, beasts), 'simple' (curled ridge ends, beasts), 'none'.
    gable_parts (gable / xieshan kinds): 'full' (red gable infill + studded bargeboards),
    'board' (bargeboards only, e.g. corridors) or 'none' (wall copings).
    detail: 'high' (6 samples per tile course, drip tiles, ribbed rafter soffit) or 'low' (about
    half the triangles: 4 samples per course, coarser rows, no drip tiles, plain soffit).
    Returns the root Empty; custom props: arch_ridge_z, arch_eave_z (eave edge mid), arch_corner_z,
    arch_eave_w, arch_eave_d, arch_overhang, arch_top_z (incl. ornaments), arch_soffit_col_z (0)."""
    sh = roof_shape(width, depth, kind, sides, rise, overhang, curve, corner_lift, corner_push, sweep,
                    gable_inset, top_inset, tile_pitch, thickness, side_overhang, detail)
    _init_materials()
    root = _root(name, collection, parent, location, rotation_z, size=max(1.0, 0.1 * width))
    dims = _ridge_dims(sh, ridge_h)
    if beasts is None:
        beasts = int(_clamp(round(sh.span / 2.2), 1, 9))
        beasts = beasts if beasts % 2 else beasts + 1
        beasts = min(beasts, 9)
    if ornaments == "none":
        beasts = 0
    tmat = tile_material(tile_mat)
    _roof_top_mesh(sh, _child(root, "tiles"), collection, root, tmat, _mat(fascia_mat))
    _soffit, rafter_ends = _roof_soffit_mesh(sh, _child(root, "soffit"), collection, root,
                                            _mat(board_mat), _mat(rafter_mat))
    orn = _Ornaments()
    protos = dict(cap=_p_cap(tile_mat), drip=_p_drip(tile_mat))
    _eave_items(sh, orn, protos, rafter_ends, dims)
    _roof_ridges(sh, orn, dims, tile_mat, ornaments, beasts, finial)
    if orn.rv:
        U.mesh_from_pydata(_child(root, "ridges"), orn.rv, orn.rf, collection,
                           materials=[M.get(tile_mat)], smooth=math.radians(50), parent=root)
    for pname, (proto, mats) in sorted(orn.mats.items()):
        tag = pname.replace("arch.p.", "").split(".")[0]
        scatter(_child(root, tag), collection, proto, mats, parent=root)
    _gable_parts(sh, root, collection, dims, gable_parts)
    # metrics
    if sh.base in ("hip", "xieshan", "gable"):
        root["arch_eave_w"] = sh.We * 2
        root["arch_eave_d"] = sh.De * 2
    else:
        root["arch_eave_w"] = root["arch_eave_d"] = sh.rho * 2
    top_d = sh.cut if sh.cut is not None else (sh.d_max(0) if sh.base != "round" else sh.rho)
    root["arch_ridge_z"] = sh.z_top(top_d) + (dims["h"] if sh.cut is None and sh.base in
                                              ("hip", "xieshan", "gable") else 0.0)
    root["arch_eave_z"] = sh.z_top(0.0) - sh.t_board
    corner = sh.pt(0, sh.a_range(0)[1], 0.0) if sh.base != "round" else sh.pt(0, 0.0, 0.0)
    root["arch_corner_z"] = corner.z
    root["arch_overhang"] = sh.ov
    root["arch_top_z"] = root["arch_ridge_z"] + (1.05 * dims["h"] if ornaments == "full" else 0.0)
    root["arch_kind"] = kind
    return root


def double_eave_roofs(name, collection, width, depth=None, kind="xieshan", sides=4, gap=None,
                      skirt_inset=None, upper_width=None, upper_depth=None, tile_mat="roof_tile_teal",
                      parent=None, location=(0, 0, 0), **kw):
    """Double eave (chong yan) as two stacked roofs: a skirt roof over the ``width`` x ``depth``
    footprint and the main roof above it on an inner footprint (``upper_width`` x
    ``upper_depth``, default inset by ``skirt_inset``). ``gap`` is the height from the skirt's base
    to the upper roof's base (room for a short wall / bracket band). Returns (root, skirt, upper)
    where the upper roof's root is at z = gap."""
    depth = width if depth is None else depth
    if kind in ("pyramid", "round"):
        depth = width
    inset = skirt_inset if skirt_inset is not None else 0.22 * min(width, depth) * 0.5
    uw = upper_width if upper_width is not None else width - 2 * inset
    ud = upper_depth if upper_depth is not None else depth - 2 * inset
    skirt_sides = 0 if kind == "round" else sides
    sk_shape = roof_shape(width, depth, "skirt", sides=skirt_sides, top_inset=inset)
    if gap is None:
        gap = sk_shape.z_top(sk_shape.cut) + 0.4 + 0.12 * min(uw, ud)
    root = _root(name, collection, parent, location)
    sk = roof(_child(root, "skirt"), collection, width, depth, "skirt", sides=skirt_sides,
              top_inset=inset, tile_mat=tile_mat, parent=root)
    up = roof(_child(root, "upper"), collection, uw, ud, kind, sides=sides, tile_mat=tile_mat,
              parent=root, location=(0, 0, gap), **kw)
    root["arch_gap"] = gap
    root["arch_top_z"] = gap + up["arch_top_z"]
    return root, sk, up


# ======================================================================== columns, brackets, beams

class _BoxAttrs:
    """Collects per-vertex arch_gen / arch_dims / arch_rand for pydata box meshes."""

    def __init__(self):
        self.gen, self.dims, self.rand = [], [], []
        self.cur = (1.0, 1.0, 1.0)
        self.n = 0

    def start(self, dx, dy, dz):
        self.cur = (max(dx, 1e-6), max(dy, 1e-6), max(dz, 1e-6))
        self.n += 1

    def vert(self, gx, gy, gz):
        self.gen.extend((gx, gy, gz))
        self.dims.extend(self.cur)
        self.rand.append((self.n * 0.618034) % 1.0)

    def write(self, me):
        for nm, typ, data, key in (("arch_gen", 'FLOAT_VECTOR', self.gen, "vector"),
                                   ("arch_dims", 'FLOAT_VECTOR', self.dims, "vector"),
                                   ("arch_rand", 'FLOAT', self.rand, "value")):
            a = me.attributes.get(nm) or me.attributes.new(nm, typ, 'POINT')
            a.data.foreach_set(key, data)
        me.update()


def _recalc_normals(ob):
    """Make face normals of a closed mesh point outward (bmesh recalc)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return ob


def _bm_loft(bm, rings, center=(0.0, 0.0), cap=True):
    """Loft axis-aligned rectangles [(half_x, half_y, z), ...] (bottom to top) into a closed
    solid. Returns the verts."""
    cx, cy = center
    loops = []
    for hx, hy, z in rings:
        loops.append([bm.verts.new((cx + x, cy + y, z)) for x, y in
                      ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))])
    for a, b in zip(loops[:-1], loops[1:]):
        for k in range(4):
            k2 = (k + 1) % 4
            bm.faces.new((a[k], a[k2], b[k2], b[k]))
    if cap:
        bm.faces.new(list(reversed(loops[0])))
        bm.faces.new(loops[-1])
    return [v for lp in loops for v in lp]


def _p_column(height, radius, mat="lacquer_red", base_mat="marble_white", ring_mat="gold"):
    """Column prototype: square marble plinth with a drum (guzheng) top, tapered lacquer shaft
    with a gold foot ring. Origin at floor level (z = 0)."""
    key = "column.%d_%d.%s" % (round(height * 100), round(radius * 1000), mat)

    def build(col):
        r = radius
        bm = bmesh.new()
        # square plinth slab, mostly sunk into the floor
        _bm_loft(bm, [(1.32 * r, 1.32 * r, -0.12), (1.32 * r, 1.32 * r, 0.05),
                      (1.22 * r, 1.22 * r, 0.07)])
        # drum (gu jing): bulging round
        drum = [(0.0, 0.07), (1.18 * r, 0.07), (1.28 * r, 0.07 + 0.12 * r), (1.30 * r, 0.07 + 0.24 * r),
                (1.24 * r, 0.07 + 0.38 * r), (1.08 * r, 0.07 + 0.5 * r), (0.0, 0.07 + 0.5 * r)]
        U.bm_lathe(bm, drum, segments=16)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
        _proto_obj(col, "base", bm, [base_mat], smooth=math.radians(35))
        z0 = 0.07 + 0.5 * r
        sh = bmesh.new()
        prof = [(0.0, z0 - 0.02), (r, z0 - 0.02)]
        steps = 6
        for k in range(1, steps + 1):
            t = k / steps
            z = z0 + (height - z0) * t
            rr = r * (1.0 - 0.07 * t + 0.015 * math.sin(math.pi * t))
            prof.append((rr, z))
        prof.append((0.0, height))
        U.bm_lathe(sh, prof, segments=16)
        bmesh.ops.remove_doubles(sh, verts=sh.verts[:], dist=1e-5)
        _proto_obj(col, "shaft", sh, [mat], smooth=math.radians(40))
        rg = bmesh.new()
        U.bm_lathe(rg, [(0.0, z0 - 0.01), (1.035 * r, z0 - 0.01), (1.05 * r, z0 + 0.05),
                        (1.04 * r, z0 + 0.11), (1.0 * r, z0 + 0.13), (0.0, z0 + 0.13)], segments=16)
        bmesh.ops.remove_doubles(rg, verts=rg.verts[:], dist=1e-5)
        _proto_obj(col, "ring", rg, [ring_mat], smooth=math.radians(50))
    return _proto(key, build)


def column(name, collection, height=6.0, radius=0.32, mat="lacquer_red", base_mat="marble_white",
           parent=None, location=(0, 0, 0)):
    """One column: marble drum base (guzheng) on a square plinth, slightly tapered red lacquer
    shaft, gold foot ring. Origin at the floor. Returns a collection-instance Empty of a shared
    prototype (cached per height/radius/material)."""
    proto = _p_column(height, radius, mat, base_mat)
    return U.collection_instance(proto, U.name(name), collection, location=location, parent=parent)


def _arm_outline(L, h, c=None):
    """Bracket-arm side outline (x along the arm, z up) with rolled-off lower ends (juansha)."""
    c = 0.3 * L if c is None else c
    hl = L * 0.5
    return [(-hl + c, 0.0), (hl - c, 0.0), (hl - 0.45 * c, 0.16 * h), (hl - 0.14 * c, 0.42 * h),
            (hl, 0.7 * h), (hl, h), (-hl, h), (-hl, 0.7 * h), (-hl + 0.14 * c, 0.42 * h),
            (-hl + 0.45 * c, 0.16 * h)]


def _p_dougong(hs, corner=False):
    """One dougong bracket set of height ``hs`` (u = hs/10): seat block, three tiers of
    crossing arms, a cantilever (ang) with a beak, a mask head and small blocks, merged into one
    mesh whose pieces are tagged for arch_paint_box_fine (blue-green fields, gold lines).
    Local: x along the wall, -y outward, z = 0 at the plate top. ``corner``: the set points along
    the diagonal and also carries the projecting members of both sides."""
    key = "dougong.%d%s" % (round(hs * 1000), ".c" if corner else "")

    def build(col):
        u = hs / 10.0
        bm = _paint_layers(bmesh.new())
        count = [0]

        def tag(vs):
            count[0] += 1
            _tag_piece(bm, vs, (count[0] * 0.618034) % 1.0)

        def block(x, y, z, s=1.6, h=1.0):
            tag(_bm_loft(bm, [(0.36 * s * u, 0.36 * s * u, z * u),
                              (0.5 * s * u, 0.5 * s * u, (z + 0.45 * h) * u),
                              (0.5 * s * u, 0.5 * s * u, (z + h) * u)], center=(x * u, y * u)))

        def arm_x(L, x, y, z, h=1.4, w=1.0):
            out = [(px + x * u, pz + z * u) for px, pz in _arm_outline(L * u, h * u)]
            tag(_bm_prism(bm, out, (y - 0.5 * w) * u, (y + 0.5 * w) * u))

        def arm_y(y_in, y_out, z, h=1.4, w=1.0, beak=False, mask=False, rots=(0.0,)):
            """Projecting member along -y from y_in (inside, > 0) to y_out (< 0)."""
            Li, Lo = y_in * u, -y_out * u
            hh = h * u
            if beak:
                out = [(-Li, 0.0), (Lo - 0.6 * hh, 0.0), (Lo + 0.25 * hh, -0.55 * hh), (Lo, 0.3 * hh),
                       (Lo - 0.2 * hh, hh), (-Li, hh)]
            elif mask:
                out = [(-Li, 0.0), (Lo - 0.5 * hh, 0.0), (Lo, 0.45 * hh), (Lo - 0.5 * hh, hh), (-Li, hh)]
            else:
                out = _arm_outline(Li + Lo, hh)
                off = 0.5 * (Lo - Li)
                out = [(px + off, pz) for px, pz in out]
            out = [(px, pz + z * u) for px, pz in out]
            for r in rots:
                vs = _bm_prism(bm, out, -0.5 * w * u, 0.5 * w * u)
                tag(vs)
                # outline x' -> -Y, then optional extra turn (corner sets)
                bmesh.ops.rotate(bm, verts=vs, matrix=Matrix.Rotation(-math.pi / 2 + r, 3, 'Z'))

        rots = (0.0, math.pi / 4, -math.pi / 4) if corner else (0.0,)
        # seat block (ludou)
        tag(_bm_loft(bm, [(1.15 * u, 1.15 * u, 0.0), (1.6 * u, 1.6 * u, 0.8 * u), (1.6 * u, 1.6 * u, 2.0 * u)]))
        # tier 1
        arm_x(6.2, 0, 0, 2.0)
        arm_y(1.6, -3.1, 2.0, rots=rots)
        for x, y in ((-2.6, 0), (2.6, 0), (0, -2.6)):
            block(x, y, 3.4)
        # tier 2
        arm_x(9.2, 0, 0, 4.4)
        arm_x(6.2, 0, -2.6, 4.4)
        arm_y(1.6, -5.6, 4.4, beak=True, rots=rots)
        for x, y in ((-4.1, 0), (4.1, 0), (-2.6, -2.6), (2.6, -2.6), (0, -5.0)):
            block(x, y, 5.8)
        # tier 3
        arm_x(9.2, 0, -2.6, 6.8)
        arm_x(6.2, 0, -5.0, 6.8)
        arm_y(1.6, -7.2, 6.8, mask=True, rots=rots)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        _proto_obj(col, "set", bm, [_mat("arch_paint_box_fine")], smooth=False)
    return _proto(key, build)


def beam(name, collection, p0, p1, width=0.4, height=0.6, mat="bracket_paint", parent=None,
         bevel=0.02):
    """Box beam from p0 to p1 (centre line of its bottom face), ``width`` x ``height``, bevelled.
    The beam's local X runs along it. Returns the object."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    L = d.length
    bm = bmesh.new()
    U.bm_box(bm, (L, width, height), (L * 0.5, 0.0, height * 0.5))
    side = Z.cross(d) if abs(d.normalized().z) < 0.99 else Vector((0, 1, 0))
    m = _frame(d, side, p0)
    mm = _mat(mat) if mat.startswith("arch_") else mat
    ob = U.mesh_from_bmesh(U.name(name), bm, collection, materials=[mm], smooth=False,
                           parent=parent, matrix=m)
    if bevel:
        U.bevel_mesh(ob, bevel, 1)
    return ob


def _side_frames(width, depth, sides):
    """Wall-line sides of a footprint: list of (start, end) 2D points, CCW, front first.
    Rectangle: ``width`` x ``depth``; polygon: ``width`` = column circumradius x 2."""
    if sides == 4:
        w, d = width * 0.5, depth * 0.5
        pts = [(-w, -d), (w, -d), (w, d), (-w, d)]
    else:
        R = width * 0.5
        pts = [(R * math.cos(-math.pi / 2 - math.pi / sides + TAU * k / sides),
                R * math.sin(-math.pi / 2 - math.pi / sides + TAU * k / sides)) for k in range(sides)]
    n = len(pts)
    return [(Vector(pts[k]), Vector(pts[(k + 1) % n])) for k in range(n)]


def band_height_for(width):
    """Suggested bracket-band height (column top to roof seat) for a building ``width`` m wide."""
    return _clamp(0.55 + 0.03 * width, 0.7, 1.7)


def bracket_band(name, collection, width, depth=None, sides=4, height=None, bays=None,
                 spacing=None, architrave=True, grid=None, parent=None, location=(0, 0, 0)):
    """Dougong band around a footprint, sitting on the column tops (local z = 0 = column top).

    Builds the double architrave with a red frieze below the column tops, the plate, a bracket
    set over every column (corner sets on the diagonals), intermediate sets about 11.5 bracket
    units apart, the red panels between sets and the continuous beams on top.
    ``height``: column top to roof seat (default ``band_height_for(width)``); ``bays``: (nx, ny)
    bays along the width / depth of a rectangle (column positions), default 1 per side;
    ``grid``: (xs, ys) explicit column-line coordinates of a rectangle (overrides ``bays``).
    Root props: arch_top_z (roof seat height), arch_projection (how far the sets reach out),
    arch_architrave_z (bottom of the architrave, below the column tops)."""
    depth = width if depth is None else depth
    H = height if height is not None else band_height_for(width)
    hs = H / 1.2
    u = hs / 10.0
    zb = 0.2 * hs
    root = _root(name, collection, parent, location)
    sides_list = _side_frames(width, depth, sides)
    nx, ny = bays if bays else (1, 1)
    target = spacing if spacing is not None else max(11.5 * u, 1.2)
    m_set, m_corner = [], []
    bv, bf, bmi = [], [], []
    attrs = _BoxAttrs()
    mats = [_mat("arch_beam_paint"), _mat("arch_paint_red"), _mat("arch_paint_box")]

    def box(p0, p1, y0, y1, z0, z1, mi, n):
        """Beam box along a side from p0 to p1 (2D); y0..y1 measured outward along n."""
        base = len(bv)
        corners = ((p0, y0, 0, 0), (p1, y0, 1, 0), (p1, y1, 1, 1), (p0, y1, 0, 1))
        attrs.start((p1 - p0).length, abs(y1 - y0), z1 - z0)
        for zi, z in enumerate((z0, z1)):
            for pp, yy, gx, gy in corners:
                q = pp + n * yy
                bv.append((q.x, q.y, z))
                attrs.vert(gx, gy, zi)
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            bf.append(tuple(base + k for k in f))
            bmi.append(mi)

    for si, (a, b) in enumerate(sides_list):
        t = (b - a).normalized()
        n = Vector((t.y, -t.x))                       # outward normal
        L = (b - a).length
        if grid is not None and sides == 4:
            gx, gy = grid
            line = [x - gx[0] for x in gx] if si % 2 == 0 else [y - gy[0] for y in gy]
            if si >= 2:
                line = [L - c for c in reversed(line)]
            cuts = line
        else:
            nb_ = (nx if si % 2 == 0 else ny) if sides == 4 else 1
            cuts = [L * k / nb_ for k in range(nb_ + 1)]
        nb = len(cuts) - 1
        xs = []
        for k in range(nb):
            s0, s1 = cuts[k], cuts[k + 1]
            if k > 0:
                xs.append(s0)                         # column-head set
            cnt = max(1, int(round((s1 - s0) / target)))
            for j in range(1, cnt):
                xs.append(s0 + (s1 - s0) * j / cnt)
        for s in xs:
            p = a + t * s
            m_set.append(_frame(Vector((t.x, t.y, 0)), Vector((-n.x, -n.y, 0)), (p.x, p.y, zb)))
        # corner set at vertex a, pointing out along the bisector
        pa_, pb_ = sides_list[si - 1]
        tp = (pb_ - pa_).normalized()
        npv = Vector((tp.y, -tp.x))
        bis = (n + npv).normalized()
        xb = Vector((-bis.y, bis.x))
        m_corner.append(_frame(Vector((xb.x, xb.y, 0)), Vector((-bis.x, -bis.y, 0)), (a.x, a.y, zb)))
        # beams run a little past the corners so neighbouring sides meet
        e = 0.6 * u
        pa, pb = a - t * e, b + t * e
        if architrave:
            # one painted beam per bay (each carries the full hexi pattern), red frieze between
            for k in range(nb):
                qa, qb = a + t * cuts[k], a + t * cuts[k + 1]
                box(qa, qb, -0.27 * hs, 0.27 * hs, -0.55 * hs, -0.02 * hs, 0, n)  # big architrave
                box(qa, qb, -0.23 * hs, 0.23 * hs, -1.08 * hs, -0.75 * hs, 0, n)  # small architrave
            box(pa, pb, -0.12 * hs, 0.12 * hs, -0.75 * hs, -0.55 * hs, 1, n)     # red frieze
        box(pa, pb, -0.38 * hs, 0.38 * hs, 0.0, zb, 2, n)                        # plate
        box(a, b, -0.18 * u, 0.18 * u, zb + 2.0 * u, zb + 5.8 * u, 1, n)         # red panels
        box(pa, pb, -0.5 * u, 0.5 * u, zb + 5.8 * u, zb + 10.0 * u, 2, n)        # wall-line beams
        box(pa - t * 2.4 * u, pb + t * 2.4 * u, 2.1 * u, 3.1 * u, zb + 8.2 * u, zb + 9.1 * u, 2, n)
        box(pa - t * 4.8 * u, pb + t * 4.8 * u, 4.5 * u, 5.5 * u, zb + 7.0 * u, zb + 8.2 * u, 2, n)
    beams_ob = U.mesh_from_pydata(_child(root, "beams"), bv, bf, collection, materials=mats,
                                  material_indices=bmi, smooth=False, parent=root)
    _recalc_normals(beams_ob)
    attrs.write(beams_ob.data)
    scatter(_child(root, "sets"), collection, _p_dougong(hs), m_set, parent=root)
    scatter(_child(root, "corner_sets"), collection, _p_dougong(hs, corner=True), m_corner, parent=root)
    root["arch_top_z"] = H
    root["arch_projection"] = 7.2 * u
    root["arch_architrave_z"] = -1.08 * hs if architrave else 0.0
    return root


# ======================================================================== lattice panels

def _clip_segment(p0, p1, x0, x1, z0, z1):
    """Liang-Barsky clip of segment p0-p1 (2D tuples) to the rectangle; None if outside."""
    dx, dz = p1[0] - p0[0], p1[1] - p0[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, p0[0] - x0), (dx, x1 - p0[0]), (-dz, p0[1] - z0), (dz, z1 - p0[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return None
    return ((p0[0] + dx * t0, p0[1] + dz * t0), (p0[0] + dx * t1, p0[1] + dz * t1))


def _poly_area(poly):
    a = 0.0
    for i in range(len(poly)):
        x0, z0 = poly[i]
        x1, z1 = poly[(i + 1) % len(poly)]
        a += x0 * z1 - x1 * z0
    return abs(a) * 0.5


def _split_convex(poly, p, d):
    """Split a convex polygon by the line through p with direction d. Returns (a, b, chord)."""
    nrm = (-d[1], d[0])
    side = [(v[0] - p[0]) * nrm[0] + (v[1] - p[1]) * nrm[1] for v in poly]
    a, b, chord = [], [], []
    n = len(poly)
    for i in range(n):
        v, w = poly[i], poly[(i + 1) % n]
        sv, sw = side[i], side[(i + 1) % n]
        (a if sv >= 0 else b).append(v)
        if (sv >= 0) != (sw >= 0):
            t = sv / (sv - sw)
            q = (v[0] + (w[0] - v[0]) * t, v[1] + (w[1] - v[1]) * t)
            a.append(q)
            b.append(q)
            chord.append(q)
    if len(chord) != 2 or len(a) < 3 or len(b) < 3:
        return None
    return a, b, (chord[0], chord[1])


def _lattice_segments(pattern, x0, x1, z0, z1, sp, seed):
    """Bar centre lines [(p0, p1, layer)] for a lattice pattern inside the rectangle."""
    segs = []
    w, h = x1 - x0, z1 - z0
    cx, cz = 0.5 * (x0 + x1), 0.5 * (z0 + z1)
    if pattern == "grid":
        nx = max(1, int(round(w / sp)))
        nz = max(1, int(round(h / sp)))
        for k in range(1, nx):
            x = x0 + w * k / nx
            segs.append(((x, z0), (x, z1), 0))
        for k in range(1, nz):
            z = z0 + h * k / nz
            segs.append(((x0, z), (x1, z), 1))
    elif pattern == "diamond":
        step = sp * math.sqrt(2.0)
        R = w + h
        k0 = int(math.floor(-R / step)) - 1
        for k in range(k0, -k0 + 1):
            c = k * step
            for layer, (dx, dz) in enumerate(((1.0, 1.0), (1.0, -1.0))):
                p0 = (cx + c - dx * R, cz - dz * R)
                p1 = (cx + c + dx * R, cz + dz * R)
                cl = _clip_segment(p0, p1, x0, x1, z0, z1)
                if cl and math.dist(cl[0], cl[1]) > 0.02:
                    segs.append((cl[0], cl[1], layer))
    elif pattern == "ice":
        r = U.rng(seed, "ice", round(w, 3), round(h, 3))
        polys = [[(x0, z0), (x1, z0), (x1, z1), (x0, z1)]]
        n = max(3, int(w * h / (sp * sp * 2.6)))
        for i in range(n):
            polys.sort(key=_poly_area, reverse=True)
            poly = polys[0]
            ccx = sum(v[0] for v in poly) / len(poly)
            ccz = sum(v[1] for v in poly) / len(poly)
            ang = r.uniform(0.0, math.pi)
            p = (ccx + r.uniform(-0.15, 0.15) * sp, ccz + r.uniform(-0.15, 0.15) * sp)
            res = _split_convex(poly, p, (math.cos(ang), math.sin(ang)))
            if res is None:
                continue
            a, b, chord = res
            polys = polys[1:] + [a, b]
            segs.append((chord[0], chord[1], i % 2))
    else:
        raise ValueError("lattice pattern %r not in ('grid', 'diamond', 'ice')" % pattern)
    return segs


def _bar_box(verts, faces, p0, p1, bw, y0, y1):
    """Box bar in the XZ plane from p0 to p1 (2D x,z), width bw, depth y0..y1."""
    dx, dz = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dz)
    if L < 1e-6:
        return
    nx, nz = -dz / L * bw * 0.5, dx / L * bw * 0.5
    ex, ez = dx / L * bw * 0.5, dz / L * bw * 0.5        # extend half a bar so joints close
    q = [(p0[0] - ex - nx, p0[1] - ez - nz), (p1[0] + ex - nx, p1[1] + ez - nz),
         (p1[0] + ex + nx, p1[1] + ez + nz), (p0[0] - ex + nx, p0[1] - ez + nz)]
    base = len(verts)
    for y in (y0, y1):
        for x, z in q:
            verts.append((x, y, z))
    for f in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        faces.append(tuple(base + k for k in f))


def _p_lattice(width, height, pattern, kind, lit, seed, frame_mat, paper):
    key = "lattice.%d_%d.%s.%s.%s.%d.%s%s" % (round(width * 100), round(height * 100), pattern, kind,
                                            "lit" if lit else "dim", seed, frame_mat, "" if paper else ".open")

    def build(col):
        w, h = width, height
        t = _clamp(0.04 * min(w, h) + 0.04, 0.06, 0.12)          # frame depth
        fw = _clamp(0.05 * min(w, h) + 0.02, 0.05, 0.12)         # frame member width
        bw = _clamp(0.018 * min(w, h) + 0.012, 0.02, 0.04)       # lattice bar width
        sp = _clamp(0.085 * min(w, h) + 0.05, 0.1, 0.22)         # lattice spacing
        verts, faces, mi = [], [], []

        def add_box(x0, x1, z0, z1, y0, y1, m=0):
            n0 = len(faces)
            _bar_box(verts, faces, ((x0 + x1) * 0.5, z0), ((x0 + x1) * 0.5, z1), x1 - x0, y0, y1) \
                if (z1 - z0) >= (x1 - x0) else \
                _bar_box(verts, faces, (x0, (z0 + z1) * 0.5), (x1, (z0 + z1) * 0.5), z1 - z0, y0, y1)
            mi.extend([m] * (len(faces) - n0))

        hx = w * 0.5
        # outer frame (stiles and rails)
        add_box(-hx, -hx + fw, 0.0, h, -t / 2, t / 2)
        add_box(hx - fw, hx, 0.0, h, -t / 2, t / 2)
        if kind == "door":
            rails = [0.0, 0.27 * h, 0.33 * h, 0.9 * h, h - fw]
        else:
            rails = [0.0, h - fw]
        for z in rails:
            add_box(-hx + fw, hx - fw, z, z + fw, -t / 2, t / 2)
        # lattice heart
        if kind == "door":
            lz0, lz1 = 0.33 * h + fw, 0.9 * h
        else:
            lz0, lz1 = fw, h - fw
        lx0, lx1 = -hx + fw, hx - fw
        segs = _lattice_segments(pattern, lx0, lx1, lz0, lz1, sp, seed)
        bd = 0.6 * t
        for p0, p1, layer in segs:
            n0 = len(faces)
            off = 0.002 * layer
            _bar_box(verts, faces, p0, p1, bw, -bd / 2 - off, bd / 2 - off)
            mi.extend([0] * (len(faces) - n0))
        # solid boards (door skirt, bands), set back a little
        boards = []
        if kind == "door":
            boards = [(fw, 0.27 * h), (0.27 * h + fw, 0.33 * h), (0.9 * h + fw, h - fw)]
        for z0, z1 in boards:
            add_box(lx0, lx1, z0, z1, -t * 0.15, t * 0.35)
        # gold corner plates on the lattice heart + a gold medallion on the skirt board
        g = 0.055 * min(w, 2.0)
        for x in (lx0, lx1 - g):
            for z in (lz0, lz1 - g):
                add_box(x, x + g, z, z + g, -t / 2 - 0.006, -t / 2 + 0.004, 1)
        if kind == "door":
            zc = 0.5 * (fw + 0.27 * h)
            mw, mh = 0.42 * (lx1 - lx0), 0.45 * (0.27 * h - fw)
            n0 = len(faces)
            ring = []
            base = len(verts)
            for k in range(16):
                a = TAU * k / 16
                ring.append((0.5 * mw * math.cos(a), zc + 0.5 * mh * math.sin(a)))
            for x, z in ring:
                verts.append((x, -t * 0.15 - 0.012, z))
            for x, z in ring:
                verts.append((x, -t * 0.15 + 0.002, z))
            faces.append(tuple(base + k for k in range(16)))
            faces.append(tuple(base + 16 + k for k in reversed(range(16))))
            for k in range(16):
                k2 = (k + 1) % 16
                faces.append((base + k, base + k2, base + 16 + k2, base + 16 + k))
            mi.extend([1] * (len(faces) - n0))
        # paper backing behind the lattice heart
        if paper:
            n0 = len(faces)
            base = len(verts)
            yp = bd / 2 + 0.004
            for x, z in ((lx0, lz0), (lx1, lz0), (lx1, lz1), (lx0, lz1)):
                verts.append((x, yp, z))
            faces.append((base, base + 1, base + 2, base + 3))
            mi.append(2)
        mats = [frame_mat, "gold", "paper_screen_lit" if lit else "paper_screen"]
        ob = U.mesh_from_pydata(U.name(col.name, "panel"), verts, faces, col, materials=mats,
                                material_indices=mi, smooth=False)
        _recalc_normals_open(ob)
    return _proto(key, build)


def _recalc_normals_open(ob):
    """Consistent outward normals for meshes made of closed boxes plus open quads."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def lattice_panel(name, collection, width, height, pattern="grid", kind="window", lit=False,
                  seed=0, frame_mat="lacquer_red", paper=True, parent=None, location=(0, 0, 0),
                  rotation_z=0.0):
    """Lattice door or window leaf in the XZ plane, facing -Y, origin at its bottom centre.

    pattern: 'grid' (square), 'diamond' (diagonal), 'ice' (ice-crack, seeded). kind: 'window'
    (lattice fills the frame) or 'door' (gexiang: lattice heart above a carved skirt board with a
    gold medallion). Real bar geometry, gold corner plates, paper backing (paper_screen, or
    paper_screen_lit when ``lit``). Returns a collection-instance Empty of a cached prototype."""
    proto = _p_lattice(width, height, pattern, kind, lit, seed, frame_mat, paper)
    return U.collection_instance(proto, U.name(name), collection, location=location,
                                 rotation=(0, 0, rotation_z), parent=parent)


# ======================================================================== platform, stairs, balustrade

# xumizuo profile: (outward offset in units of s, z as a fraction of the height), bottom to top
_XUMIZUO = [(0.55, 0.0), (0.55, 0.11), (0.38, 0.11), (0.38, 0.25), (0.30, 0.28), (0.16, 0.32),
            (0.02, 0.35), (-0.12, 0.37), (-0.12, 0.61), (0.02, 0.63), (0.16, 0.66), (0.28, 0.70),
            (0.34, 0.74), (0.34, 0.94), (0.20, 0.97), (0.0, 1.0)]
_PLAIN = [(0.35, 0.0), (0.35, 0.82), (0.25, 0.86), (0.25, 0.94), (0.0, 1.0)]


def _offset_poly(pts, off):
    """Offset a convex CCW polygon outward by ``off`` (mitred corners)."""
    n = len(pts)
    out = []
    for k in range(n):
        a, b, c = Vector(pts[k - 1]), Vector(pts[k]), Vector(pts[(k + 1) % n])
        t0 = (b - a).normalized()
        t1 = (c - b).normalized()
        n0 = Vector((t0.y, -t0.x))
        n1 = Vector((t1.y, -t1.x))
        bis = (n0 + n1).normalized()
        cosh = max(bis.dot(n0), 0.2)
        out.append(b + bis * (off / cosh))
    return out


def _footprint(width, depth, sides):
    if sides == 4:
        w, d = width * 0.5, depth * 0.5
        return [Vector((-w, -d)), Vector((w, -d)), Vector((w, d)), Vector((-w, d))]
    R = width * 0.5
    return [Vector((R * math.cos(-math.pi / 2 - math.pi / sides + TAU * k / sides),
                    R * math.sin(-math.pi / 2 - math.pi / sides + TAU * k / sides))) for k in range(sides)]


def _p_waist_post(h, w):
    key = "waistpost.%d_%d" % (round(h * 1000), round(w * 1000))

    def build(col):
        bm = bmesh.new()
        U.bm_box(bm, (w, w * 0.5, h), (0, -w * 0.25, h * 0.5))
        _proto_obj(col, "post", bm, ["marble_white"], smooth=False, bevel=(min(0.01, w * 0.1), 1))
    return _proto(key, build)


def platform(name, collection, width, depth=None, height=1.5, style="xumizuo", sides=4,
             mat="marble_white", top_mat="marble_paving", sink=0.6, parent=None, location=(0, 0, 0),
             rotation_z=0.0):
    """Raised stone platform. Footprint ``width`` x ``depth`` at the top edge (``sides`` >= 5:
    regular polygon, ``width`` = circumscribed diameter). Origin on the ground at the centre;
    the walkable top is at z = ``height``; a footing continues ``sink`` m below ground so it never
    floats on uneven terrain. style 'xumizuo': plinth, bands, lotus mouldings and a recessed
    waist with carved posts; 'plain': a base with a simple cap moulding.
    Root prop: arch_top_z."""
    depth = width if depth is None else depth
    root = _root(name, collection, parent, location, rotation_z)
    base = _footprint(width, depth, sides)
    prof = _XUMIZUO if style == "xumizuo" else _PLAIN
    s = _clamp(0.16 * height, 0.06, 0.32)
    verts, faces, mi = [], [], []
    n = len(base)
    rings = []
    prof = [(prof[0][0], -sink / max(height, 1e-3))] + list(prof)
    for o, zf in prof:
        ring = []
        for p in _offset_poly(base, o * s):
            ring.append(len(verts))
            verts.append((p.x, p.y, zf * height))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((a[k], a[k2], b[k2], b[k]))
            mi.append(0)
    faces.append(tuple(rings[-1]))
    mi.append(1)
    faces.append(tuple(reversed(rings[0])))
    mi.append(0)
    U.mesh_from_pydata(_child(root, "body"), verts, faces, collection, materials=[mat, top_mat],
                       material_indices=mi, smooth=math.radians(35), parent=root)
    if style == "xumizuo" and height >= 0.5:
        # carved posts in the recessed waist
        z0, z1 = 0.37 * height, 0.61 * height
        pw = _clamp(0.1 * height, 0.08, 0.22)
        proto = _p_waist_post(round(z1 - z0, 3), round(pw, 3))
        mats = []
        ring = _offset_poly(base, -0.12 * s)
        for k in range(n):
            a, b = ring[k], ring[(k + 1) % n]
            L = (b - a).length
            t = (b - a).normalized()
            nrm = Vector((t.y, -t.x))
            cnt = max(1, int(round(L / max(1.6, 2.2 * height))))
            for j in range(cnt + 1):
                p = a + t * (L * j / cnt)
                if j in (0, cnt):
                    p = p + t * (pw * (0.6 if j == 0 else -0.6))
                mats.append(_frame(Vector((t.x, t.y, 0)), Vector((-nrm.x, -nrm.y, 0)), (p.x, p.y, z0)))
        scatter(_child(root, "waist_posts"), collection, proto, mats, parent=root)
    root["arch_top_z"] = height
    return root


# ---------------------------------------------------------------- balustrade prototypes

def _p_post(h, mat="marble_white"):
    """Baluster post (wangzhu): square shaft with a carved lotus-cloud cap, origin at its foot."""
    key = "post.%d.%s" % (round(h * 1000), mat)

    def build(col):
        w = 0.17 * h
        bm = bmesh.new()
        sh = 0.74 * h
        _bm_loft(bm, [(0.5 * w, 0.5 * w, -0.05), (0.5 * w, 0.5 * w, sh), (0.42 * w, 0.42 * w, sh + 0.02 * h)])
        cap = [(0.0, sh), (0.46 * w, sh), (0.46 * w, sh + 0.04 * h), (0.58 * w, sh + 0.07 * h),
               (0.62 * w, sh + 0.11 * h), (0.52 * w, sh + 0.15 * h), (0.40 * w, sh + 0.16 * h),
               (0.50 * w, sh + 0.19 * h), (0.52 * w, sh + 0.22 * h), (0.38 * w, sh + 0.25 * h),
               (0.16 * w, sh + 0.26 * h), (0.0, sh + 0.26 * h)]
        U.bm_lathe(bm, cap, segments=8)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
        _proto_obj(col, "post", bm, [mat], smooth=math.radians(40), bevel=None)
    return _proto(key, build)


def _p_panel(h, mat="marble_white"):
    """Balustrade panel (lanban) of unit length along +X (scaled/sheared per span), height h:
    sill, carved lower board, three vase supports, round handrail."""
    key = "panel.%d.%s" % (round(h * 1000), mat)

    def build(col):
        t = 0.13 * h
        bm = bmesh.new()
        U.bm_box(bm, (1.0, t * 1.15, 0.09 * h), (0.5, 0, 0.045 * h - 0.04))           # sill (buried a bit)
        U.bm_box(bm, (1.0, t, 0.37 * h), (0.5, 0, 0.09 * h + 0.185 * h - 0.04))       # lower board
        # raised border of the carved field on both faces
        for sy in (-1, 1):
            y = sy * (t * 0.5 + 0.006)
            for x0, x1, z0, z1 in ((0.06, 0.94, 0.12 * h, 0.15 * h), (0.06, 0.94, 0.37 * h, 0.40 * h),
                                   (0.06, 0.09, 0.12 * h, 0.40 * h), (0.91, 0.94, 0.12 * h, 0.40 * h)):
                U.bm_box(bm, (x1 - x0, 0.016, z1 - z0), ((x0 + x1) * 0.5, y, (z0 + z1) * 0.5 - 0.04))
        # vase supports (jingping)
        vz0, vz1 = 0.42 * h, 0.82 * h
        vh = vz1 - vz0
        for x in (0.18, 0.5, 0.82):
            prof = [(0.0, 0.0), (0.07, 0.0), (0.11, 0.42), (0.05, 0.78), (0.11, 1.0), (0.0, 1.0)]
            vs = U.bm_lathe(bm, [(r * vh * 1.4, z * vh) for r, z in prof], segments=6)
            bmesh.ops.scale(bm, vec=(1.0, 0.75, 1.0), verts=vs)
            bmesh.ops.translate(bm, vec=(x, 0, vz0 - 0.04), verts=vs)
        # handrail
        prof = [(0.0, -0.5), (0.35, -0.42), (0.5, 0.0), (0.35, 0.42), (0.0, 0.5), (-0.35, 0.42),
                (-0.5, 0.0), (-0.35, -0.42)]
        rr = 0.075 * h
        ring_a = [bm.verts.new((0.0, py * rr * 2, vz1 + 0.5 * rr * 2 + pz * rr * 2 - 0.04)) for py, pz in prof]
        ring_b = [bm.verts.new((1.0, py * rr * 2, vz1 + 0.5 * rr * 2 + pz * rr * 2 - 0.04)) for py, pz in prof]
        for k in range(len(prof)):
            k2 = (k + 1) % len(prof)
            bm.faces.new((ring_a[k], ring_a[k2], ring_b[k2], ring_b[k]))
        bm.faces.new(ring_a)
        bm.faces.new(list(reversed(ring_b)))
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        _proto_obj(col, "panel", bm, [mat], smooth=math.radians(40))
    return _proto(key, build)


def _p_drum_stone(h, mat="marble_white"):
    """Drum stone (baogushi) ending a stair balustrade; faces +X (down the stair), unit = h."""
    key = "drum.%d.%s" % (round(h * 1000), mat)

    def build(col):
        t = 0.15 * h
        bm = bmesh.new()
        # stepped base block
        U.bm_box(bm, (1.0 * h, t * 1.2, 0.3 * h), (0.05 * h, 0, 0.15 * h - 0.04))
        U.bm_box(bm, (0.75 * h, t * 1.05, 0.12 * h), (0.0, 0, 0.36 * h - 0.04))
        # the drum: a disc facing sideways (axis along Y)
        prof = [(0.0, -0.5 * t), (0.30 * h, -0.5 * t), (0.33 * h, -0.42 * t), (0.34 * h, 0.0),
                (0.33 * h, 0.42 * t), (0.30 * h, 0.5 * t), (0.0, 0.5 * t)]
        vs = U.bm_lathe(bm, prof, segments=20)
        bmesh.ops.rotate(bm, verts=vs, matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
        bmesh.ops.translate(bm, verts=vs, vec=(0.05 * h, 0.0, 0.72 * h - 0.04))
        # scroll under the drum
        vs = U.bm_lathe(bm, [(0.0, -0.45 * t), (0.13 * h, -0.45 * t), (0.13 * h, 0.45 * t), (0.0, 0.45 * t)],
                        segments=12)
        bmesh.ops.rotate(bm, verts=vs, matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
        bmesh.ops.translate(bm, verts=vs, vec=(0.42 * h, 0.0, 0.42 * h - 0.04))
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        _proto_obj(col, "drum", bm, [mat], smooth=math.radians(40))
    return _proto(key, build)


def _p_rail_post(h, mat):
    """Wooden railing post (wood style), origin at its foot."""
    key = "railpost.%d.%s" % (round(h * 1000), mat)

    def build(col):
        w = 0.1 * h
        bm = bmesh.new()
        _bm_loft(bm, [(0.5 * w, 0.5 * w, -0.05), (0.5 * w, 0.5 * w, h * 1.02), (0.35 * w, 0.35 * w, h * 1.1),
                      (0.12 * w, 0.12 * w, h * 1.16)])
        _proto_obj(col, "post", bm, [mat], smooth=False)
    return _proto(key, build)


def _p_rail_panel(h, mat):
    """Wooden railing span (xunzhang langan) of unit length along +X: top rail, mid rail, sill,
    thin balusters."""
    key = "railpanel.%d.%s" % (round(h * 1000), mat)

    def build(col):
        bm = bmesh.new()
        t = 0.06 * h
        for z, hh in ((0.0, 0.07 * h), (0.42 * h, 0.05 * h), (0.9 * h, 0.08 * h)):
            U.bm_box(bm, (1.0, t * (1.4 if z > 0.5 * h else 1.0), hh), (0.5, 0, z + hh * 0.5))
        for k in range(1, 8):
            U.bm_box(bm, (0.025, t * 0.6, 0.83 * h), (k / 8.0, 0, 0.07 * h + 0.415 * h))
        _proto_obj(col, "panel", bm, [mat], smooth=False)
    return _proto(key, build)


def balustrade(name, collection, points, height=1.1, post_spacing=1.8, mat="marble_white",
               closed=False, end_drum=None, no_post=None, style="marble", parent=None, location=(0, 0, 0)):
    """White marble balustrade along ``points`` [(x, y, z), ...] (z = foot level; segments may
    slope, e.g. along stairs: panels are sheared so posts stay vertical). Posts with carved caps at
    every point and every <= ``post_spacing`` m; panels with vase supports and a round handrail
    between them, all instanced. ``closed`` joins the last point to the first. ``end_drum``:
    'start', 'end' or 'both' puts a drum stone at that end instead of a post; ``no_post`` the
    same values leave that end without a post (to join another balustrade's post).
    style: 'marble' (carved posts, vase panels) or 'wood' (light painted railing, e.g. pagoda
    balconies; pass mat='lacquer_red').
    Returns the root Empty."""
    root = _root(name, collection, parent, location)
    pts = [Vector(p) for p in points]
    if closed:
        pts = pts + [pts[0]]
    hp = height * 0.86
    if style == "wood":
        post = _p_rail_post(round(height, 3), mat)
        panel = _p_rail_panel(round(height * 0.95, 3), mat)
    else:
        post = _p_post(round(height * 1.22, 3), mat)
        panel = _p_panel(round(hp, 3), mat)
    m_post, m_panel, m_drum = [], [], []
    drum_ends = set()
    if end_drum in ("start", "both"):
        drum_ends.add(0)
    if end_drum in ("end", "both"):
        drum_ends.add(len(pts) - 1)
    pw = 0.17 * height * 1.22 if style != "wood" else 0.1 * height
    posts_at = []
    for k in range(len(pts) - 1):
        a, b = pts[k], pts[k + 1]
        d = b - a
        Lh = math.hypot(d.x, d.y)
        if Lh < 1e-6:
            continue
        cnt = max(1, int(math.ceil(Lh / post_spacing)))
        side = Vector((-d.y, d.x, 0.0)).normalized()
        for j in range(cnt):
            p0 = a + d * (j / cnt)
            p1 = a + d * ((j + 1) / cnt)
            posts_at.append((k, j, p0, d))
            # panel spans between post faces
            fwd = Vector((d.x, d.y, 0.0)).normalized()
            q0 = p0 + fwd * (pw * 0.5) + Vector((0, 0, d.z / Lh * pw * 0.5))
            q1 = p1 - fwd * (pw * 0.5) - Vector((0, 0, d.z / Lh * pw * 0.5))
            X = q1 - q0
            m = Matrix((X, side, Vector((0, 0, 1.0)))).transposed().to_4x4()
            m.translation = q0
            m_panel.append(m)
    # posts (and drums)
    last = len(pts) - 1
    for idx, p in enumerate(pts):
        if closed and idx == last:
            break
        k = min(idx, len(pts) - 2)
        d = pts[k + 1] - pts[k]
        if no_post and ((idx == 0 and no_post in ("start", "both")) or
                        (idx == last and no_post in ("end", "both"))):
            continue
        if idx in drum_ends:
            fwd = (pts[0] - pts[1]) if idx == 0 else (pts[-1] - pts[-2])
            m_drum.append(_upright(fwd, p, height * 0.95))
            continue
        m_post.append(_upright(d, p))
    for k, j, p0, d in posts_at:
        if j > 0:
            m_post.append(_upright(d, p0))
    scatter(_child(root, "posts"), collection, post, m_post, parent=root)
    scatter(_child(root, "panels"), collection, panel, m_panel, parent=root)
    if m_drum:
        drum = _p_drum_stone(1.0, mat)
        scatter(_child(root, "drums"), collection, drum, m_drum, parent=root)
    return root


_balustrade = balustrade     # stairs() has a parameter named balustrade


def _ramp_relief(n_x, n_y, w, L):
    """Height field (0-1) of carved cloud scrolls and a dragon-like ridge for the yubu ramp."""
    out = []
    for j in range(n_y + 1):
        row = []
        for i in range(n_x + 1):
            x = (i / n_x - 0.5) * w
            y = j / n_y * L
            v = 0.0
            # sinuous central body
            cx = 0.22 * w * math.sin(y / L * TAU * 2.2)
            v += math.exp(-((x - cx) / (0.09 * w)) ** 2) * 0.9
            # cloud scroll bumps
            for k in range(int(L / (0.55 * w)) + 2):
                yy = (k + 0.5) * 0.55 * w
                for sx in (-1, 1):
                    xx = sx * 0.3 * w
                    r = math.hypot(x - xx, y - yy) / (0.16 * w)
                    if r < 1.6:
                        ang = math.atan2(y - yy, x - xx)
                        v += 0.55 * max(0.0, math.cos(r * 3.2 + ang * sx)) * max(0.0, 1.0 - r / 1.6)
            row.append(min(v, 1.2))
        out.append(row)
    return out


def stairs(name, collection, width, height, run_per_step=0.33, ramp=True, balustrade=True,
           ramp_width=None, stringer=0.5, max_riser=0.17, mat="marble_white", bal_height=1.0,
           bal_extend=0.0, parent=None, location=(0, 0, 0), rotation_z=0.0):
    """Marble stairs climbing toward +Y to a landing at z = ``height`` (y = 0 is the top edge,
    where they meet a platform; they descend toward -Y). Risers <= ``max_riser`` (0.15-0.17 m),
    treads ``run_per_step``. ``ramp``: a carved imperial ramp (yubu) between two flights;
    side stringers (chuidai) on the outer edges (and beside the ramp); ``balustrade``: sloped
    balustrades on the outer stringers ending in drum stones (``bal_extend``: run them that far
    onto the landing to meet a platform balustrade). Origin on the ground under the top
    edge's centre. Root props: arch_run (horizontal length), arch_steps, arch_riser."""
    root = _root(name, collection, parent, location, rotation_z)
    n = max(1, int(math.ceil(height / max_riser - 1e-6)))
    riser = height / n
    run = run_per_step
    L = n * run
    w = width
    sw = stringer
    rw = (ramp_width if ramp_width is not None else _clamp(0.3 * w, 1.2, 4.5)) if ramp else 0.0
    verts, faces = [], []

    def step_prism(x0, x1):
        prof = [(-L, 0.0)]
        for k in range(n):
            y0 = -(n - k) * run
            prof += [(y0, (k + 1) * riser), (y0 + run, (k + 1) * riser)]
        prof += [(0.0, 0.0)]
        # dedupe consecutive
        clean = [prof[0]]
        for p in prof[1:]:
            if abs(p[0] - clean[-1][0]) > 1e-7 or abs(p[1] - clean[-1][1]) > 1e-7:
                clean.append(p)
        base = len(verts)
        m = len(clean)
        for x in (x0, x1):
            for y, z in clean:
                verts.append((x, y, z))
        faces.append(tuple(base + k for k in range(m)))
        faces.append(tuple(base + m + k for k in reversed(range(m))))
        for k in range(m):
            k2 = (k + 1) % m
            faces.append((base + k, base + m + k, base + m + k2, base + k2))

    def sloped_block(x0, x1, top_off, y_start=-L):
        """Stringer / ramp body: sloped top along the nosing line (+top_off), flat at the top."""
        def ztop(y):
            if y >= -run:
                return height + top_off
            return riser + top_off + (height - riser) * (y + L) / (L - run)
        prof = [(y_start, 0.0), (0.0, 0.0), (0.0, ztop(0.0)), (-run, ztop(-run)), (y_start, ztop(y_start))]
        base = len(verts)
        m = len(prof)
        for x in (x0, x1):
            for y, z in prof:
                verts.append((x, y, z))
        faces.append(tuple(base + k for k in range(m)))
        faces.append(tuple(base + m + k for k in reversed(range(m))))
        for k in range(m):
            k2 = (k + 1) % m
            faces.append((base + k, base + m + k, base + m + k2, base + k2))
        return ztop

    hw = w * 0.5
    if ramp:
        hr = rw * 0.5
        step_prism(-hw + sw, -hr - sw * 0.6)
        step_prism(hr + sw * 0.6, hw - sw)
        sloped_block(-hr - sw * 0.6, -hr, 0.06)
        sloped_block(hr, hr + sw * 0.6, 0.06)
    else:
        step_prism(-hw + sw, hw - sw)
    ztop = sloped_block(-hw, -hw + sw, 0.08)
    sloped_block(hw - sw, hw, 0.08)
    ob = U.mesh_from_pydata(_child(root, "steps"), verts, faces, collection, materials=[mat],
                            smooth=False, parent=root)
    _recalc_normals(ob)
    U.bevel_mesh(ob, 0.012, 1)
    if ramp:
        # carved ramp slab: a sloped grid with relief, plus its thickness
        nx_, ny_ = 22, max(10, int(L / 0.12))
        rel = _ramp_relief(nx_, ny_, rw - 0.16, L - run)
        rv, rf = [], []
        hr = rw * 0.5
        for j in range(ny_ + 1):
            y = -L + (L - run) * j / ny_
            for i in range(nx_ + 1):
                x = -hr + 0.08 + (rw - 0.16) * i / nx_
                edge = min(i, nx_ - i, j, ny_ - j)
                lift = 0.1 if edge <= 1 else 0.13 * rel[j][i]
                rv.append((x, y, ztop(y) - 0.06 + lift))
        for j in range(ny_):
            for i in range(nx_):
                a = j * (nx_ + 1) + i
                rf.append((a, a + 1, a + nx_ + 2, a + nx_ + 1))
        ramp_ob = U.mesh_from_pydata(_child(root, "ramp"), rv, rf, collection, materials=[mat],
                                     smooth=math.radians(60), parent=root)
        # body under the relief (sloped block between the inner stringers)
        verts.clear()
        faces.clear()
        sloped_block(-hr, hr, 0.015)
        U.mesh_from_pydata(_child(root, "ramp_body"), verts, faces, collection, materials=[mat],
                           smooth=False, parent=root)
    if balustrade:
        for sx in (-1, 1):
            x = sx * (hw - sw * 0.5)
            y0 = -L + 0.35 * bal_height
            pts = [(x, y0, ztop(y0)), (x, -run, ztop(-run)), (x, max(0.0, bal_extend), height)]
            _balustrade(_child(root, "bal"), collection, pts, height=bal_height, end_drum="start",
                        parent=root)
    root["arch_run"] = L
    root["arch_steps"] = n
    root["arch_riser"] = riser
    return root


# ======================================================================== composite buildings

_roof = roof          # hall() / pagoda() have parameters named roof and stairs
_stairs = stairs

def _grid(n, bay, center=1.18, ends=0.94, ring=None):
    """Column-line coordinates (centred) for ``n`` bays of nominal width ``bay``: a wider centre
    bay, slightly narrower end bays; ``ring`` fixes the width of the two end bays (double-eave
    halls need equal corridor widths all round)."""
    if n == 1:
        return [-bay * 0.5, bay * 0.5]
    f = []
    for i in range(n):
        d = abs(i - (n - 1) * 0.5)
        f.append(center if d < 0.6 else (ends if i in (0, n - 1) and n >= 4 else 1.0))
    total = bay * n
    w = [total * x / sum(f) for x in f]
    if ring is not None and n >= 3:
        inner = total - 2 * ring
        fi = f[1:-1]
        w = [ring] + [inner * x / sum(fi) for x in fi] + [ring]
    xs = [-total * 0.5]
    for x in w:
        xs.append(xs[-1] + x)
    return xs


def _wall_box(verts, faces, mats, p0, p1, thick, z0, z1, mi=0):
    """Vertical wall slab along p0->p1 (2D), centred on the line."""
    d = (p1 - p0)
    L = d.length
    if L < 1e-6:
        return
    t = d / L
    # left normal: the corners run counter-clockwise from above, so every face points outward
    # (with the right normal the box came out inside out and floors built with it faced down)
    n = Vector((-t.y, t.x)) * (thick * 0.5)
    base = len(verts)
    for z in (z0, z1):
        for q in (p0 - n, p1 - n, p1 + n, p0 + n):
            verts.append((q.x, q.y, z))
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        faces.append(tuple(base + k for k in f))
        mats.append(mi)


def _facade(root, collection, xs, y, z0, h_open, cr, lit, pattern, seed, door_bays, sill=0.9,
            frame_mat="lacquer_red"):
    """Lattice doors / windows filling the bays between columns xs at line y (facing -Y), from
    floor z0 up to z0 + h_open, with a lattice transom band. Returns nothing."""
    n = len(xs) - 1
    for i in range(n):
        bw = xs[i + 1] - xs[i] - 2 * cr * 0.92
        xc = 0.5 * (xs[i] + xs[i + 1])
        leaves = 4 if bw < 5.6 else 6
        lw = bw / leaves
        door = i in door_bays
        h_leaf = h_open * (0.8 if door else 0.8 - sill / max(h_open, 1e-3))
        zl = z0 if door else z0 + sill
        for k in range(leaves):
            x = xc - bw * 0.5 + lw * (k + 0.5)
            lattice_panel(_child(root, "leaf"), collection, round(lw - 0.01, 3), round(h_leaf, 3),
                          pattern, "door" if door else "window", lit=lit, seed=seed + k % 2,
                          frame_mat=frame_mat, parent=root, location=(x, y, zl))
        # transom (hengpi) band above the leaves
        zt = zl + h_leaf
        ht = z0 + h_open - zt
        if ht > 0.25:
            tl = 3 if bw > 3 else 2
            for k in range(tl):
                x = xc - bw * 0.5 + bw / tl * (k + 0.5)
                lattice_panel(_child(root, "transom"), collection, round(bw / tl - 0.01, 3), round(ht, 3),
                              "grid", "window", lit=lit, seed=seed, frame_mat=frame_mat, parent=root,
                              location=(x, y, zt))
        if not door:
            # sill wall (kanqiang) under the windows
            v, f, m = [], [], []
            _wall_box(v, f, m, Vector((xs[i] + cr * 0.6, y + 0.05)), Vector((xs[i + 1] - cr * 0.6, y + 0.05)),
                      0.36, z0 - 0.02, z0 + sill, 0)
            U.mesh_from_pydata(_child(root, "sill"), v, f, collection, materials=["stone_grey"],
                               smooth=False, parent=root)


def hall(name, collection, bays_w=5, bays_d=3, bay=5.0, column_h=6.0, roof="xieshan",
         double_eave=False, platform_h=1.5, stairs=True, lit=False, roof_mat="roof_tile_teal",
         column_r=None, porch=True, lattice="diamond", balustrade=None, seed=0, parent=None,
         back_stairs=False,
         location=(0, 0, 0), rotation_z=0.0):
    """Formal hall facing -Y on a xumizuo platform with front stairs (central carved ramp when the
    platform is >= 1.2 m), red columns on marble drum bases, painted architraves and a dougong
    band, lattice doors in the central bays and windows over sill walls elsewhere (front porch one
    bay deep when bays_d >= 3), red plaster side/back walls, and the roof (``roof`` kind, or a
    double eave: skirt roof + an inner frieze + the upper roof on the inner columns).

    bays_w x bays_d bays of nominal ``bay`` m (centre bay wider); ``column_h`` outer column
    height; ``lit``: lattice paper glows. Returns the root Empty; root['plaque_anchor'] is the
    name of an Empty (child of the root) centred under the (upper) eave on the front, its -Y axis
    facing out: hang a plaque of about root['plaque_size'] (w, h) there. Other props:
    arch_height (ridge top incl. ornaments), arch_eave_z, arch_platform (w, d).
    ``back_stairs``: also a plain flight centred on the back edge, with a gap in the balustrade
    (for a rear apron that side walkways cannot reach)."""
    root = _root(name, collection, parent, location, rotation_z, size=2.0)
    ring = 0.82 * bay if (double_eave and bays_w >= 3 and bays_d >= 3) else None
    xs = _grid(bays_w, bay, ring=ring)
    ys = _grid(bays_d, bay * 0.9, center=1.0, ends=1.0, ring=ring)
    W, D = xs[-1] - xs[0], ys[-1] - ys[0]
    cr = column_r if column_r is not None else _clamp(0.045 * column_h + 0.04, 0.22, 0.48)
    z0 = platform_h
    H1 = band_height_for(W) * (0.85 if double_eave else 1.0)
    hs1 = H1 / 1.2
    if double_eave:
        sk = roof_shape(W, D, "skirt", top_inset=ring if ring else 0.3 * bay)
        ov = sk.ov
    else:
        sh = roof_shape(W, D, roof)
        ov = sh.ov
    # ---------------- platform, stairs, balustrade
    mx = max(1.6, 0.72 * ov)
    Wp, Dp = W + 2 * mx, D + 2 * mx
    platform(_child(root, "platform"), collection, Wp, Dp, platform_h, parent=root)
    st_w = 0.0
    if stairs:
        ci = len(xs) // 2 - (1 if len(xs) % 2 == 0 else 0)
        cbw = xs[ci + 1] - xs[ci] if bays_w % 2 else bay
        st_w = min(cbw + 1.2, Wp - 2.0)
        _stairs(_child(root, "stairs"), collection, st_w, platform_h, ramp=platform_h >= 1.2,
                balustrade=platform_h >= 0.9, bal_extend=0.35, parent=root, location=(0, -Dp / 2, 0))
    sb_w = 0.0
    if back_stairs:
        # a plain flight down the back edge, centred (reaches the rear apron when something
        # stands across the side walkways)
        ci = len(xs) // 2 - (1 if len(xs) % 2 == 0 else 0)
        sb_w = min((xs[ci + 1] - xs[ci] if bays_w % 2 else bay) + 1.2, Wp - 2.0)
        _stairs(_child(root, "stairs_back"), collection, sb_w, platform_h, ramp=False,
                balustrade=platform_h >= 0.9, bal_extend=0.35, parent=root, location=(0, Dp / 2, 0),
                rotation_z=math.pi)
    use_bal = balustrade if balustrade is not None else platform_h >= 0.9
    if use_bal:
        e = 0.35
        hw, hd = Wp / 2 - e, Dp / 2 - e
        gx = st_w / 2 - 0.25 if stairs else 0.0
        gb = sb_w / 2 - 0.25
        if back_stairs:
            for side in (-1, 1):
                pts = [(side * gx, -hd, z0), (side * hw, -hd, z0), (side * hw, hd, z0), (side * gb, hd, z0)]
                if not stairs:
                    pts = [(0.0, -hd, z0)] + pts[1:]
                _balustrade(_child(root, "balustrade"), collection, pts, height=1.0, parent=root,
                            no_post="both" if stairs else "end")
        else:
            pts = [(-gx, -hd, z0), (-hw, -hd, z0), (-hw, hd, z0), (hw, hd, z0), (hw, -hd, z0), (gx, -hd, z0)]
            if not stairs:
                pts = pts[1:-1] + [pts[1]]
            _balustrade(_child(root, "balustrade"), collection, pts, height=1.0, parent=root,
                        no_post="both" if stairs else None)
    # ---------------- columns
    col_pts = []
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            if i in (0, len(xs) - 1) or j in (0, len(ys) - 1):
                col_pts.append((x, y))
    face_row = 1 if (porch and bays_d >= 3 and not double_eave) else (1 if ring else 0)
    inner_pts = []
    if ring:
        xi, yi = xs[1:-1], ys[1:-1]
        for i, x in enumerate(xi):
            for j, y in enumerate(yi):
                if i in (0, len(xi) - 1) or j in (0, len(yi) - 1):
                    inner_pts.append((x, y))
    elif face_row == 1:
        for x in xs[1:-1]:
            col_pts.append((x, ys[1]))
    for x, y in col_pts:
        column(_child(root, "col"), collection, column_h, cr, parent=root, location=(x, y, z0))
    # ---------------- walls (sides and back) and the facade
    zt_wall = column_h + (-1.08 * hs1)                       # under the small architrave
    wv, wf, wm = [], [], []
    wt = 2.0 * cr * 0.9
    yf = ys[face_row]
    xa, xb = xs[0], xs[-1]
    if ring:
        xa, xb = xs[1], xs[-2]
        wall_back = ys[-2]
    else:
        wall_back = ys[-1]
    for p0, p1 in (((xa, ys[0] if not ring else yf), (xa, wall_back)), ((xa, wall_back), (xb, wall_back)),
                   ((xb, wall_back), (xb, ys[0] if not ring else yf))):
        a, b = Vector(p0), Vector(p1)
        _wall_box(wv, wf, wm, a, b, wt, z0 - 0.02, z0 + 1.0, 1)
        _wall_box(wv, wf, wm, a, b, wt * 0.94, z0 + 1.0, z0 + zt_wall + (0.0 if not ring else 0.0), 0)
    U.mesh_from_pydata(_child(root, "walls"), wv, wf, collection, materials=[_mat("arch_plaster_red"), "stone_grey"],
                       material_indices=wm, smooth=False, parent=root)
    nb = len(xs) - 1
    c = (nb - 1) / 2.0
    door_bays = [i for i in range(nb) if abs(i - c) <= (1.01 if nb >= 5 else 0.01)]
    fx = xs if not ring else xs[1:-1]
    if ring:
        door_bays = [i - 1 for i in door_bays if 1 <= i <= nb - 2]
    _facade(root, collection, fx, yf + 0.0, z0, zt_wall, cr, lit, lattice, seed, door_bays)
    # ---------------- bracket band(s), roof(s)
    zb1 = z0 + column_h
    bracket_band(_child(root, "band"), collection, W, D, height=H1, grid=(xs, ys), parent=root,
                 location=(0, 0, zb1))
    if not double_eave:
        r = _roof(_child(root, "roof"), collection, W, D, roof, tile_mat=roof_mat, parent=root,
                              location=(0, 0, zb1 + H1))
        top = zb1 + H1 + r["arch_top_z"]
        eave_z = zb1 + H1 + r["arch_eave_z"]
        plaque_y = ys[0] - 0.72 * hs1 - 0.12
        plaque_z = zb1 + 0.25 * H1
        plaque_w = 0.62 * (xs[len(xs) // 2] - xs[len(xs) // 2 - 1] if nb % 2 == 0 else
                           xs[nb // 2 + 1] - xs[nb // 2])
        plaque_h = _clamp(1.5 * H1, 1.0, 2.6)
    else:
        skirt = _roof(_child(root, "skirt"), collection, W, D, "skirt",
                                  top_inset=ring if ring else 0.3 * bay, tile_mat=roof_mat, parent=root,
                                  location=(0, 0, zb1 + H1))
        skirt_top = zb1 + H1 + sk.z_top(sk.cut)
        Wi, Di = xs[-2] - xs[1], ys[-2] - ys[1]
        H2 = band_height_for(Wi)
        hs2 = H2 / 1.2
        frieze = 0.55 + 0.03 * Wi
        z_ut = skirt_top + 0.35 + frieze + 1.08 * hs2              # inner column top
        for x, y in inner_pts:
            column(_child(root, "col_in"), collection, z_ut - z0, cr * 0.95, parent=root, location=(x, y, z0))
        # frieze wall between the skirt and the upper architrave, with small lattice windows
        fv, ff, fm = [], [], []
        xi, yi = xs[1:-1], ys[1:-1]
        quad = [(xi[0], yi[0]), (xi[-1], yi[0]), (xi[-1], yi[-1]), (xi[0], yi[-1])]
        for k in range(4):
            a, b = Vector(quad[k]), Vector(quad[(k + 1) % 4])
            _wall_box(fv, ff, fm, a, b, wt * 0.6, skirt_top - 0.6, z_ut - 1.0 * hs2, 0)
        U.mesh_from_pydata(_child(root, "frieze"), fv, ff, collection, materials=[_mat("arch_paint_red")],
                           smooth=False, parent=root)
        fh = frieze * 0.62
        for i in range(len(xi) - 1):
            bw = xi[i + 1] - xi[i] - 2 * cr
            for sy, yy in ((-1, yi[0] - wt * 0.3 - 0.02), (1, yi[-1] + wt * 0.3 + 0.02)):
                lattice_panel(_child(root, "frieze_win"), collection, round(bw * 0.8, 3), round(fh, 3), "grid",
                              "window", lit=lit, seed=seed, parent=root,
                              location=(0.5 * (xi[i] + xi[i + 1]), yy, skirt_top + 0.35 + (frieze - fh) * 0.5),
                              rotation_z=0.0 if sy < 0 else math.pi)
        bracket_band(_child(root, "band_up"), collection, Wi, Di, height=H2, grid=(xi, yi), parent=root,
                     location=(0, 0, z_ut))
        up_ov = max(roof_shape(Wi, Di, roof).ov, 0.62 * (ring if ring else bay), 0.75 * sk.ov)
        up = _roof(_child(root, "roof"), collection, Wi, Di, roof, tile_mat=roof_mat, overhang=up_ov,
                   parent=root, location=(0, 0, z_ut + H2))
        top = z_ut + H2 + up["arch_top_z"]
        eave_z = zb1 + H1 + skirt["arch_eave_z"]
        plaque_y = yi[0] - 0.72 * hs2 - 0.15
        plaque_z = z_ut - 0.1 * H2
        plaque_w = 0.55 * (xi[len(xi) // 2] - xi[len(xi) // 2 - 1]) if len(xi) % 2 == 0 else \
            0.55 * (xi[len(xi) // 2 + 1] - xi[len(xi) // 2])
        plaque_h = _clamp(1.1 * frieze + 0.6 * H2, 1.2, 3.2)
    anchor = U.empty(_child(root, "plaque_anchor"), collection, location=(0, plaque_y, plaque_z),
                     rotation=(math.radians(-6), 0, 0), parent=root, display_size=0.6,
                     display_type='SINGLE_ARROW')
    root["plaque_anchor"] = anchor.name
    root["plaque_size"] = (round(plaque_w, 3), round(plaque_h, 3))
    root["arch_height"] = top
    root["arch_eave_z"] = eave_z
    root["arch_platform"] = (Wp, Dp)
    root["arch_columns"] = (W, D)
    return root


def _p_spire(metal="gold"):
    """Pagoda finial spire (tasha), unit height: lotus seat, seven stacked rings (xianglun) on a
    pole, a canopy (baogai) and a gourd with a pearl on top."""
    def build(col):
        prof = [(0.0, 0.0), (0.30, 0.0), (0.33, 0.025), (0.40, 0.07), (0.36, 0.10), (0.20, 0.12),
                (0.08, 0.13)]
        z = 0.15
        for k in range(7):
            rr = 0.21 - 0.012 * k
            prof += [(0.06, z), (rr, z + 0.004), (rr + 0.01, z + 0.018), (rr, z + 0.032), (0.06, z + 0.036)]
            z += 0.058
        prof += [(0.05, 0.57), (0.30, 0.585), (0.27, 0.605), (0.08, 0.62), (0.045, 0.66),
                 (0.10, 0.70), (0.13, 0.75), (0.09, 0.80), (0.05, 0.82), (0.085, 0.86),
                 (0.07, 0.90), (0.02, 0.95), (0.0, 1.0)]
        bm = bmesh.new()
        U.bm_lathe(bm, prof, segments=16)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        _proto_obj(col, "spire", bm, [metal], smooth=math.radians(40))
    return _proto("spire." + metal, build)


def _poly_pts(radius, sides):
    return [Vector((radius * math.cos(-math.pi / 2 - math.pi / sides + TAU * k / sides),
                    radius * math.sin(-math.pi / 2 - math.pi / sides + TAU * k / sides)))
            for k in range(sides)]


def _poly_width(radius, sides):
    """``platform`` width for a regular ``sides``-gon of circumradius ``radius``. platform() reads
    the width as the circumscribed diameter for 5+ sides but as the side length for 4, so a square
    needs 2 * radius * cos(pi / 4); its front edge then sits at the apothem, where the stairs go."""
    return 2.0 * radius * (math.cos(math.pi / 4) if sides == 4 else 1.0)


def _face_rot(a, b):
    """rotation_z that turns a -Y-facing panel to face outward from polygon edge a->b (CCW)."""
    t = (b - a).normalized()
    n = Vector((t.y, -t.x))
    return math.atan2(n.y, n.x) + math.pi / 2


def _polygon_body(root, collection, pts, z0, body_h, cr, arch_z, lit, pattern, seed, door_face=None,
                  open_faces=(), wall_mat="arch_plaster_red"):
    """Walls of a polygonal storey: per face a red plaster wall with a lattice opening in the middle
    (a door on ``door_face``), closed above the lattice up to ``arch_z`` (architrave bottom)."""
    wv, wf, wm = [], [], []
    n = len(pts)
    for k in range(n):
        a, b = pts[k], pts[(k + 1) % n]
        if k in open_faces:
            continue
        t = (b - a).normalized()
        fl = (b - a).length - 2 * cr
        c = (a + b) * 0.5
        door = k == door_face
        lw = fl * (0.62 if door else 0.56)
        lh = (arch_z - 0.15) * (0.82 if door else 0.62)
        zl = 0.0 if door else (arch_z - 0.15) * 0.22
        wt = 2 * cr * 0.85
        for p0, p1 in ((a + t * cr * 0.7, c - t * lw * 0.5), (c + t * lw * 0.5, b - t * cr * 0.7)):
            _wall_box(wv, wf, wm, p0, p1, wt, z0 - 0.02, z0 + arch_z, 0)
        # above and below the opening
        _wall_box(wv, wf, wm, c - t * lw * 0.5, c + t * lw * 0.5, wt * 0.9, z0 + zl + lh, z0 + arch_z, 0)
        if zl > 0:
            _wall_box(wv, wf, wm, c - t * lw * 0.5, c + t * lw * 0.5, wt * 0.9, z0 - 0.02, z0 + zl, 0)
        leaves = 2 if lw < 2.6 else 4
        rot = _face_rot(a, b)
        nrm = Vector((t.y, -t.x))
        for j in range(leaves):
            p = c - t * (lw * 0.5) + t * (lw / leaves * (j + 0.5)) + nrm * 0.0
            lattice_panel(_child(root, "leaf"), collection, round(lw / leaves - 0.01, 3), round(lh, 3),
                          pattern, "door" if door else "window", lit=lit, seed=seed + j % 2, parent=root,
                          location=(p.x, p.y, z0 + zl), rotation_z=rot)
    if wv:
        U.mesh_from_pydata(_child(root, "walls"), wv, wf, collection, materials=[_mat(wall_mat)],
                           smooth=False, parent=root)


def pagoda(name, collection, tiers=7, sides=8, radius=9.0, tier_h=5.5, taper=0.065, lit_floors=(),
           roof_mat="roof_tile_teal", platform_h=1.6, balcony=1.1, stairs=True, lattice="diamond",
           seed=0, parent=None, location=(0, 0, 0), rotation_z=0.0):
    """Multi-storey pagoda facing -Y: xumizuo base with front stairs; per storey red columns on the
    polygon corners, plaster walls with lattice windows (a door on the ground-floor front, and on
    each upper storey's front when ``balcony`` > 0, opening onto the deck at floor level), a
    dougong band and a skirt roof whose top tucks under the next storey's balcony (wooden deck
    with a red railing); the top storey has a pyramid roof and a tall gold spire.

    ``radius``: ground-floor column circumradius; each storey shrinks by ``taper`` x radius;
    ``tier_h``: floor-to-floor height; ``lit_floors``: storey indices (0 = ground) whose lattice
    paper glows. Root props: arch_height (spire tip), arch_floors (list of floor z)."""
    root = _root(name, collection, parent, location, rotation_z, size=2.0)
    n = sides
    cosn = math.cos(math.pi / n)
    ov0 = _clamp(0.8 + 0.18 * radius, 1.2, 3.2)
    pr = (radius * cosn + ov0 * 0.8) / cosn
    platform(_child(root, "platform"), collection, _poly_width(pr, n), sides=n, height=platform_h, parent=root)
    if stairs:
        _stairs(_child(root, "stairs"), collection, _clamp(0.5 * pr, 2.0, 5.0), platform_h,
                ramp=platform_h >= 1.2, balustrade=platform_h >= 0.9, parent=root,
                location=(0, -pr * cosn, 0))
    z = platform_h
    floors = []
    top_z = z
    for k in range(tiers):
        r = radius * (1.0 - taper * k)
        r_next = radius * (1.0 - taper * (k + 1))
        ap = r * cosn
        cr = _clamp(0.028 * r + 0.17, 0.2, 0.42)
        Hb = band_height_for(2 * r) * 0.78
        hs = Hb / 1.2
        ov = _clamp(0.8 + 0.18 * r, 1.1, 3.2)
        top = k == tiers - 1
        floors.append(z)
        if not top:
            bal_ap = r_next * cosn + balcony
            inset = max(0.7, ap - bal_ap + 0.45)
            shp = roof_shape(2 * r, kind="skirt", sides=n, top_inset=inset, overhang=ov)
            rise_z = shp.z_top(shp.cut)
            body_h = tier_h - Hb - rise_z - 0.55
        else:
            body_h = tier_h * 0.62
        if k == 0:
            body_h += 0.6
        body_h = max(body_h, 2.4)
        pts = _poly_pts(r, n)
        for p in pts:
            column(_child(root, "col"), collection, body_h, cr, parent=root, location=(p.x, p.y, z))
        arch_z = body_h - 1.08 * hs
        # upper storeys open onto their balcony through a front door at deck level
        _polygon_body(root, collection, pts, z, body_h, cr, arch_z, k in lit_floors, lattice, seed + k,
                      door_face=0 if (k == 0 or balcony > 0) else None)
        bracket_band(_child(root, "band"), collection, 2 * r, sides=n, height=Hb, spacing=max(1.6, 1.15 * Hb),
                     parent=root, location=(0, 0, z + body_h))
        zr = z + body_h + Hb
        det = "high" if k < 2 else "low"
        if not top:
            _roof(_child(root, "eave"), collection, 2 * r, kind="skirt", sides=n, top_inset=inset,
                  overhang=ov, tile_mat=roof_mat, detail=det, parent=root, location=(0, 0, zr))
            z_next = zr + rise_z + 0.55
            # balcony (pingzuo): wooden deck with a red railing
            bal_r = bal_ap / cosn
            platform(_child(root, "balcony"), collection, _poly_width(bal_r, n), sides=n, height=0.42, style="plain",
                     mat=_mat("arch_paint_red"), top_mat="wood_dark", sink=0.0,
                     parent=root, location=(0, 0, z_next - 0.42))
            rail = [Vector(p) for p in _poly_pts((bal_ap - 0.18) / cosn, n)]
            _balustrade(_child(root, "rail"), collection, [(p.x, p.y, z_next) for p in rail], height=0.95,
                        post_spacing=1.6, mat="lacquer_red", closed=True, style="wood", parent=root)
            z = z_next
        else:
            rf = _roof(_child(root, "top"), collection, 2 * r, kind="pyramid", sides=n, overhang=ov,
                       tile_mat=roof_mat, finial=None, detail=det, parent=root, location=(0, 0, zr))
            zt = zr + rf["arch_ridge_z"]
            sp_h = _clamp(1.15 * tier_h, 3.0, 9.0)
            scatter(_child(root, "spire"), collection, _p_spire("gold"),
                    [Matrix.Translation((0, 0, zt - 0.08 * sp_h)) @ Matrix.Scale(sp_h, 4)], parent=root)
            top_z = zt + 0.92 * sp_h
    root["arch_height"] = top_z
    root["arch_floors"] = floors
    return root


def _p_seat(length, depth=0.42, h=0.46, mat="lacquer_red"):
    """Pavilion bench with a goose-neck backrest (meirenkao), length along X, facing -Y (the
    inside), backrest leaning outward (+Y)."""
    key = "seat.%d.%s" % (round(length * 100), mat)

    def build(col):
        bm = bmesh.new()
        U.bm_box(bm, (length, depth, 0.07), (0, 0, h))                       # seat board
        U.bm_box(bm, (length, 0.08, h), (0, depth * 0.4, h * 0.5))           # skirt under the seat
        # backrest: lattice of slats leaning outward
        nb = max(4, int(length / 0.16))
        for k in range(nb + 1):
            x = -length * 0.5 + length * k / nb
            pts = [(x, depth * 0.45, h + 0.03), (x, depth * 0.55 + 0.12, h + 0.3), (x, depth * 0.5 + 0.3, h + 0.55)]
            _bm_tube(bm, pts, 0.018, 4)
        for zz, yy in ((h + 0.3, depth * 0.55 + 0.12), (h + 0.56, depth * 0.5 + 0.3)):
            U.bm_box(bm, (length, 0.05, 0.05), (0, yy, zz))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        _proto_obj(col, "seat", bm, [mat], smooth=math.radians(35))
    return _proto(key, build)


def pavilion(name, collection, sides=6, radius=3.2, height=3.4, roof="pyramid", double=False,
             roof_mat="roof_tile_teal", platform_h=0.6, seats=True, hanging=True, lattice="ice",
             seed=0, parent=None, location=(0, 0, 0), rotation_z=0.0):
    """Open pavilion (ting) facing -Y: low polygonal xumizuo platform with front steps, ``sides``
    red columns on a circle of ``radius`` (column height ``height``), a painted bracket ring,
    hanging lattice fascias (gualuo) between the column heads, goose-neck benches on every face
    but the front, and a ``roof`` 'pyramid' or 'round' (``double``: two eaves).
    Root props: arch_height, arch_floor_z."""
    root = _root(name, collection, parent, location, rotation_z, size=1.0)
    n = sides
    cosn = math.cos(math.pi / n)
    cr = _clamp(0.04 * height + 0.06, 0.15, 0.32)
    W = 2 * radius
    if double:
        ov = roof_shape(W, kind="skirt", sides=0 if roof == "round" else n).ov
    else:
        ov = roof_shape(W, kind=roof, sides=n).ov
    pr = (radius * cosn + max(0.9, 0.55 * ov)) / cosn
    if platform_h > 0.05:
        # front edge at the apothem pr * cosn for every side count, so the steps meet it
        platform(_child(root, "platform"), collection, _poly_width(pr, n), sides=n, height=platform_h,
                 parent=root)
        _stairs(_child(root, "steps"), collection, _clamp(0.9 * radius, 1.4, 3.0), platform_h, ramp=False,
                balustrade=False, stringer=0.3, parent=root, location=(0, -pr * cosn, 0))
    z0 = platform_h
    pts = _poly_pts(radius, n)
    for p in pts:
        column(_child(root, "col"), collection, height, cr, parent=root, location=(p.x, p.y, z0))
    Hb = _clamp(0.16 * height + 0.15, 0.55, 1.0)
    hs = Hb / 1.2
    bracket_band(_child(root, "band"), collection, W, sides=n, height=Hb, parent=root,
                 location=(0, 0, z0 + height))
    arch_z = height - 1.08 * hs
    for k in range(n):
        a, b = pts[k], pts[(k + 1) % n]
        t = (b - a).normalized()
        nrm = Vector((t.y, -t.x))
        c = (a + b) * 0.5
        fl = (b - a).length - 2 * cr
        rot = _face_rot(a, b)
        if hanging:
            gh = _clamp(0.12 * height, 0.3, 0.55)
            lattice_panel(_child(root, "gualuo"), collection, round(fl, 3), round(gh, 3), lattice, "window",
                          paper=False, seed=seed, parent=root, location=(c.x, c.y, z0 + arch_z - gh),
                          rotation_z=rot)
        if seats and k != 0:
            q = c - nrm * 0.12
            U.collection_instance(_p_seat(round(fl, 2)), _child(root, "seat"), collection,
                                  location=(q.x, q.y, z0), rotation=(0, 0, rot), parent=root)
    zr = z0 + height + Hb
    if not double:
        r = _roof(_child(root, "roof"), collection, W, kind=roof, sides=n, tile_mat=roof_mat, parent=root,
                  location=(0, 0, zr))
        top = zr + r["arch_top_z"]
    else:
        skirt_sides = 0 if roof == "round" else n
        inset = 0.38 * radius * cosn
        sk = roof_shape(W, kind="skirt", sides=skirt_sides, top_inset=inset)
        _roof(_child(root, "skirt"), collection, W, kind="skirt", sides=skirt_sides, top_inset=inset,
              tile_mat=roof_mat, parent=root, location=(0, 0, zr))
        r_in = radius - inset / cosn
        z_sk = zr + sk.z_top(sk.cut)
        fr = 0.25 + 0.12 * height
        # short drum (frieze) between the eaves
        fv, ff, fm = [], [], []
        ip = _poly_pts(r_in, n)
        for k in range(n):
            _wall_box(fv, ff, fm, ip[k], ip[(k + 1) % n], 0.25, z_sk - 0.4, z_sk + fr, 0)
        U.mesh_from_pydata(_child(root, "drum"), fv, ff, collection, materials=[_mat("arch_paint_red")],
                           smooth=False, parent=root)
        for p in ip:
            column(_child(root, "col_up"), collection, fr + 0.4, cr * 0.85, parent=root,
                   location=(p.x, p.y, z_sk - 0.4))
        Hb2 = Hb * 0.8
        bracket_band(_child(root, "band_up"), collection, 2 * r_in, sides=n, height=Hb2, architrave=False,
                     parent=root, location=(0, 0, z_sk + fr))
        up = _roof(_child(root, "roof"), collection, 2 * r_in, kind=roof, sides=n, tile_mat=roof_mat,
                   overhang=max(0.9 * ov, roof_shape(2 * r_in, kind=roof, sides=n).ov), parent=root,
                   location=(0, 0, z_sk + fr + Hb2))
        top = z_sk + fr + Hb2 + up["arch_top_z"]
    root["arch_height"] = top
    root["arch_floor_z"] = z0
    return root


def _painted_beams(name, collection, parent, beams):
    """Horizontal box beams tagged for the arch paint materials, as one mesh.
    ``beams``: [(p0, p1, width, height, mat_index)], p0/p1 = bottom-centre end points (3D).
    Material slots: 0 arch_beam_paint (hexi beams), 1 arch_paint_box, 2 arch_paint_red."""
    bv, bf, bmi = [], [], []
    attrs = _BoxAttrs()
    for p0, p1, w, h, mi in beams:
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        L = d.length
        if L < 1e-6:
            continue
        t = d / L
        nrm = Vector((t.y, -t.x, 0.0))
        if nrm.length < 1e-6:
            nrm = Vector((0.0, 1.0, 0.0))
        nrm.normalize()
        attrs.start(L, w, h)
        base = len(bv)
        corners = ((p0, -0.5 * w, 0, 0), (p1, -0.5 * w, 1, 0), (p1, 0.5 * w, 1, 1), (p0, 0.5 * w, 0, 1))
        for zi, z in enumerate((0.0, h)):
            for pp, off, gx, gy in corners:
                q = pp + nrm * off + Z * z
                bv.append(tuple(q))
                attrs.vert(gx, gy, zi)
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            bf.append(tuple(base + k for k in f))
            bmi.append(mi)
    ob = U.mesh_from_pydata(name, bv, bf, collection,
                            materials=[_mat("arch_beam_paint"), _mat("arch_paint_box"), _mat("arch_paint_red")],
                            material_indices=bmi, smooth=False, parent=parent)
    _recalc_normals(ob)
    attrs.write(ob.data)
    return ob


def _p_queti(length, height, thick):
    """Sparrow brace (queti) under a beam end: carved bracket hanging from the beam, attached to
    the column at x = 0, reaching +X along the beam; top at z = 0."""
    key = "queti.%d_%d_%d" % (round(length * 100), round(height * 100), round(thick * 100))

    def build(col):
        L, H = length, height
        out = [(0.0, 0.0), (L, 0.0), (0.93 * L, -0.1 * H), (0.78 * L, -0.16 * H), (0.62 * L, -0.3 * H),
               (0.5 * L, -0.34 * H), (0.36 * L, -0.5 * H), (0.22 * L, -0.66 * H), (0.12 * L, -0.86 * H),
               (0.0, -H)]
        bm = _paint_layers(bmesh.new())
        vs = _bm_prism(bm, list(reversed(out)), -thick / 2, thick / 2)
        _tag_piece(bm, vs, 0.37)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        _proto_obj(col, "queti", bm, [_mat("arch_paint_box")], smooth=False)
    return _proto(key, build)


def paifang(name, collection, bays=5, width=34.0, height=24.0, roofs=True, roof_mat="roof_tile_teal",
            column_r=None, center_frac=None, seed=0, parent=None, location=(0, 0, 0), rotation_z=0.0):
    """Ceremonial gate (paifang) facing -Y, ``bays`` bays (odd: 1, 3, 5...) about ``width`` m wide
    and ``height`` m tall (to the top of the centre roof's ornaments). Red columns on tall marble
    plinths clamped by drum stones, painted double architraves with a plaque zone between them
    (the centre one is left for the plaque), carved boards in the side bays, sparrow braces, a
    bracket row and a hip roof over every bay; the centre bay is widest and tallest, side bays step
    down. With the defaults (34 x 24) the centre opening is about 12.3 m wide and 15.4 m tall.
    Root props: plaque_anchor (Empty name, -Y facing, centred in the centre bay's plaque zone),
    plaque_size (w, h), arch_center_opening (w, h)."""
    root = _root(name, collection, parent, location, rotation_z, size=2.0)
    nb = max(1, bays | 1)
    cr = column_r if column_r is not None else _clamp(0.018 * width + 0.05, 0.2, 0.75)
    # bay widths: centre gets center_frac of the column span, the rest falls off outward
    span = width - 2.0 * (cr + _clamp(0.06 * height, 0.6, 1.8))
    if nb == 1:
        widths = [span]
    else:
        cf = center_frac if center_frac is not None else (0.45 if nb >= 5 else 0.5)
        rest = (1.0 - cf) * span / 2.0
        k = nb // 2
        ws = [1.0 - 0.18 * i for i in range(k)]                  # inner -> outer
        tot = sum(ws)
        side = [rest * w / tot for w in ws]
        widths = list(reversed(side)) + [cf * span] + side
    xs = [-span / 2.0]
    for w in widths:
        xs.append(xs[-1] + w)
    H = height
    # per bay: opening height (bottom of the beam stack), as a fraction of H
    def open_frac(i):
        d = abs(i - nb // 2)
        return [0.64, 0.48, 0.37, 0.31][min(d, 3)]
    a1, zone_c, zone_s, a2 = 0.035 * H, 0.11 * H, 0.07 * H, 0.045 * H
    Hb = _clamp(0.05 * H, 0.6, 1.5)
    d_band = _clamp(0.07 * H, 0.8, 2.0)
    bw = 2.0 * cr * 0.8                                            # beam thickness
    tops = []
    beams = []
    for i in range(nb):
        x0, x1 = xs[i], xs[i + 1]
        zo = open_frac(i) * H
        zone = zone_c if i == nb // 2 else zone_s
        z_a1 = zo
        z_zone = z_a1 + a1
        z_a2 = z_zone + zone
        z_band = z_a2 + a2
        tops.append(z_band)
        beams.append(((x0, 0, z_a1), (x1, 0, z_a1), bw, a1, 0))
        beams.append(((x0, 0, z_a2), (x1, 0, z_a2), bw * 1.08, a2, 0))
        beams.append(((x0, 0, z_zone), (x1, 0, z_zone), bw * 0.35, zone, 2))   # board behind plaque / carving
        if i != nb // 2:
            lattice_panel(_child(root, "carving"), collection, round(x1 - x0 - 2 * cr, 3), round(zone * 0.86, 3),
                          "ice", "window", paper=False, seed=seed + i, frame_mat="lacquer_red", parent=root,
                          location=(0.5 * (x0 + x1), -bw * 0.18 - 0.03, z_zone + zone * 0.07))
        # sparrow braces under the small architrave
        lq = _clamp(0.16 * (x1 - x0), 0.6, 2.6)
        q = _p_queti(round(lq, 2), round(lq * 0.55, 2), round(bw * 0.6, 2))
        for side, xx in ((1, x0 + cr * 0.9), (-1, x1 - cr * 0.9)):
            U.collection_instance(q, _child(root, "queti"), collection, location=(xx, 0, z_a1),
                                  rotation=(0, 0, 0.0 if side > 0 else math.pi), parent=root)
        # bracket row and roof over the bay
        bracket_band(_child(root, "band"), collection, (x1 - x0) + 2 * cr, d_band, height=Hb, architrave=False,
                     parent=root, location=(0.5 * (x0 + x1), 0, z_band))
        if roofs:
            dr = d_band
            ov = _clamp(0.5 * dr + 0.06 * (x1 - x0), 0.8, 2.6)
            # lower roofs stop at the taller neighbour's column on their inner side
            xa, xb = x0 - cr - 0.2, x1 + cr + 0.2
            if i < nb // 2:
                xb = x1 - ov + 0.15
            elif i > nb // 2:
                xa = x0 + ov - 0.15
            rw = max(xb - xa, dr + 0.2)
            rr = _roof(_child(root, "roof"), collection, rw, dr, "wudian", overhang=ov,
                       rise=0.85 * (dr * 0.5 + ov), ridge_h=_clamp(0.028 * H, 0.3, 0.9),
                       tile_mat=roof_mat, parent=root, location=(0.5 * (xa + xb), 0, z_band + Hb))
            tops[-1] = z_band + Hb + rr["arch_top_z"]
    _painted_beams(_child(root, "beams"), collection, root, beams)
    # columns: each rises to the higher band of its two bays
    plinth_h = _clamp(0.085 * H, 0.8, 2.4)
    drum = _p_drum_stone(1.0)
    m_drum = []
    for j, x in enumerate(xs):
        zl = [open_frac(i) * H + a1 + (zone_c if i == nb // 2 else zone_s) + a2 for i in (j - 1, j)
              if 0 <= i < nb]
        ch = max(zl) + Hb * 0.5
        column(_child(root, "col"), collection, ch, cr, parent=root, location=(x, 0, 0))
        # tall marble plinth (jiagan shi) and drum stones front and back
        bm = bmesh.new()
        U.bm_box(bm, (2.6 * cr, 2.6 * cr, plinth_h + 0.3), (x, 0, (plinth_h - 0.3) * 0.5))
        U.mesh_from_bmesh(_child(root, "plinth"), bm, collection, materials=["marble_white"], smooth=False,
                          parent=root)
        for sy in (-1, 1):
            m_drum.append(_upright(Vector((0, sy, 0)), Vector((x, sy * 1.3 * cr, 0.0)), plinth_h * 1.25))
    scatter(_child(root, "drums"), collection, drum, m_drum, parent=root)
    c = nb // 2
    zc = open_frac(c) * H + a1
    anchor = U.empty(_child(root, "plaque_anchor"), collection, location=(0, -bw * 0.5 - 0.06, zc + zone_c * 0.5),
                     parent=root, display_size=0.6, display_type='SINGLE_ARROW')
    root["plaque_anchor"] = anchor.name
    root["plaque_size"] = (round(0.42 * widths[c], 3), round(0.86 * zone_c, 3))
    root["arch_center_opening"] = (round(widths[c] - 2 * cr, 3), round(open_frac(c) * H, 3))
    root["arch_height"] = max(tops)
    root["arch_columns_x"] = xs
    return root


def _seg_frame(a, b):
    """(unit tangent, outward normal, length) of a 2D segment."""
    d = Vector((b[0] - a[0], b[1] - a[1]))
    L = d.length
    t = d / L if L > 1e-9 else Vector((1, 0))
    return t, Vector((t.y, -t.x)), L


def corridor(name, collection, points, width=3.0, height=3.0, bay=3.3, roof_mat="roof_tile_black",
             platform_h=0.45, seats=True, hanging=True, lattice="grid", detail="low", seed=0, parent=None,
             location=(0, 0, 0)):
    """Covered walkway (lang) along a 2D polyline ``points`` [(x, y), ...]: low stone floor, pairs
    of red posts every <= ``bay`` m, painted beams, hanging lattice fascias, low bench rails, and a
    gable roof (charcoal tiles) per segment; a small pyramid roof covers each corner.
    ``width``: post-to-post width, ``height``: post height; ``detail``: roof detail ('low' default,
    'high' for hero close-ups). Returns the root Empty."""
    root = _root(name, collection, parent, location)
    pts = [Vector((p[0], p[1])) for p in points]
    cr = _clamp(0.035 * height + 0.05, 0.12, 0.22)
    hw = width * 0.5
    beams = []
    zt = platform_h + height
    for si in range(len(pts) - 1):
        a, b = pts[si], pts[si + 1]
        t, n, L = _seg_frame(a, b)
        if L < 0.5:
            continue
        rot = math.atan2(t.y, t.x)
        # floor strip
        e0 = hw if si > 0 else 0.4
        e1 = hw if si < len(pts) - 2 else 0.4
        fa, fb = a - t * e0, b + t * e1
        fv, ff, fm = [], [], []
        _wall_box(fv, ff, fm, fa, fb, width + 0.9, -0.5, platform_h, 0)
        U.mesh_from_pydata(_child(root, "floor"), fv, ff, collection, materials=["stone_grey", "marble_paving"],
                           material_indices=[1 if k == 1 else 0 for k in range(len(ff))], smooth=False,
                           parent=root)
        cnt = max(1, int(math.ceil(L / bay)))
        for k in range(cnt + 1):
            if k == 0 and si > 0:
                continue
            p = a + t * (L * k / cnt)
            for s in (-1, 1):
                q = p + n * (s * hw)
                column(_child(root, "post"), collection, height, cr, parent=root, location=(q.x, q.y, platform_h))
            beams.append(((p.x - n.x * hw, p.y - n.y * hw, zt - 0.32), (p.x + n.x * hw, p.y + n.y * hw, zt - 0.32),
                          0.18, 0.3, 1))
        for s in (-1, 1):
            q0, q1 = a + n * (s * hw), b + n * (s * hw)
            beams.append(((q0.x, q0.y, zt - 0.38), (q1.x, q1.y, zt - 0.38), 0.2, 0.38, 0))
            for k in range(cnt):
                pa = a + t * (L * k / cnt) + n * (s * hw)
                pb = a + t * (L * (k + 1) / cnt) + n * (s * hw)
                c = (pa + pb) * 0.5
                fl = (pb - pa).length - 2 * cr
                frot = rot + (0.0 if s < 0 else math.pi)
                if hanging:
                    gh = _clamp(0.12 * height, 0.28, 0.45)
                    lattice_panel(_child(root, "gualuo"), collection, round(fl, 3), round(gh, 3), lattice, "window",
                                  paper=False, seed=seed, parent=root, location=(c.x, c.y, zt - 0.38 - gh),
                                  rotation_z=frot)
                if seats:
                    U.collection_instance(_p_bench_rail(round(fl, 2)), _child(root, "bench"), collection,
                                          location=(c.x, c.y, platform_h), rotation=(0, 0, frot), parent=root)
        # gable roof over the segment
        r_len = L + (0.0 if si > 0 else 0.3) + (0.0 if si < len(pts) - 2 else 0.3)
        mid = (a + b) * 0.5 + t * ((0.15 if si == 0 else 0.0) * -1 + (0.15 if si == len(pts) - 2 else 0.0))
        _roof(_child(root, "roof"), collection, max(r_len, width + 0.1), width, "xuanshan", tile_mat=roof_mat,
              ornaments="simple", side_overhang=0.45, gable_parts="board", detail=detail, parent=root,
              location=(mid.x, mid.y, zt), rotation_z=rot)
    # corner roofs
    for k in range(1, len(pts) - 1):
        p = pts[k]
        t0, _, _ = _seg_frame(pts[k - 1], p)
        _roof(_child(root, "corner_roof"), collection, width, kind="pyramid", sides=4, tile_mat=roof_mat,
              ornaments="simple", overhang=_clamp(0.35 * width, 0.8, 1.4), finial="gold", detail=detail,
              parent=root, location=(p.x, p.y, zt + 0.12), rotation_z=math.atan2(t0.y, t0.x))
    if beams:
        _painted_beams(_child(root, "beams"), collection, root, beams)
    return root


def _p_bench_rail(length, mat="lacquer_red"):
    """Low bench rail (zuodeng langan) between corridor posts, length along X."""
    key = "bench.%d.%s" % (round(length * 100), mat)

    def build(col):
        bm = bmesh.new()
        U.bm_box(bm, (length, 0.36, 0.06), (0, 0, 0.47))
        U.bm_box(bm, (length, 0.06, 0.4), (0, 0.12, 0.24))
        n = max(3, int(length / 0.22))
        for k in range(n + 1):
            x = -length * 0.5 + length * k / n
            U.bm_box(bm, (0.04, 0.04, 0.4), (x, -0.05, 0.24))
        _proto_obj(col, "bench", bm, [mat], smooth=False)
    return _proto(key, build)


def wall(name, collection, points, height=4.0, thickness=0.7, cap_mat="roof_tile_black",
         mat="arch_plaster_red", base_mat="stone_grey", closed=False, parent=None, location=(0, 0, 0)):
    """Courtyard wall along 2D ``points``: stone dado, red plaster body and a tiled coping (a small
    gable roof with tube tiles, end caps and a ridge) on top. Returns the root Empty."""
    root = _root(name, collection, parent, location)
    pts = [Vector((p[0], p[1])) for p in points]
    if closed:
        pts.append(pts[0])
    wv, wf, wm = [], [], []
    cap_h = 0.25
    zc = height - cap_h
    for si in range(len(pts) - 1):
        a, b = pts[si], pts[si + 1]
        t, n, L = _seg_frame(a, b)
        if L < 0.2:
            continue
        ea = thickness * 0.5 if (si > 0 or closed) else 0.0
        eb = thickness * 0.5 if (si < len(pts) - 2 or closed) else 0.0
        a2, b2 = a - t * ea, b + t * eb
        _wall_box(wv, wf, wm, a2, b2, thickness + 0.08, -0.4, 0.8, 1)
        _wall_box(wv, wf, wm, a2, b2, thickness, 0.8, zc, 0)
        mid = (a2 + b2) * 0.5
        _roof(_child(root, "coping"), collection, (b2 - a2).length + 0.05, thickness, "xuanshan",
              overhang=_clamp(0.4 * thickness, 0.22, 0.45), side_overhang=0.15, tile_mat=cap_mat,
              ornaments="simple", beasts=0, rise=0.38 * (0.5 * thickness + 0.3), gable_parts="none",
              detail="low", parent=root, location=(mid.x, mid.y, zc), rotation_z=math.atan2(t.y, t.x))
    U.mesh_from_pydata(_child(root, "body"), wv, wf, collection, materials=[_mat(mat), base_mat],
                       material_indices=wm, smooth=False, parent=root)
    return root


def moon_gate(name, collection, radius=1.6, wall_width=7.0, height=None, thickness=0.7,
              cap_mat="roof_tile_black", mat="arch_plaster_red", frame_mat="marble_white", parent=None,
              location=(0, 0, 0), rotation_z=0.0):
    """Wall panel ``wall_width`` m long (along X) with a round moon gate of ``radius``, a carved
    marble ring frame, stone dado and tiled coping; passage along Y. Root prop: arch_height."""
    root = _root(name, collection, parent, location, rotation_z)
    h = height if height is not None else max(2 * radius + 1.4, 3.6)
    zc_c = radius * 0.94
    zt = h - 0.25
    hw = wall_width * 0.5
    N = 48
    verts, faces = [], []
    ht = thickness * 0.5
    # ring of the opening and the matching boundary points of the wall rectangle
    for side, y in ((0, -ht), (1, ht)):
        for k in range(N):
            a = TAU * k / N - math.pi / 2
            c, s = math.cos(a), math.sin(a)
            p = Vector((radius * c, zc_c + radius * s))
            # ray to the rectangle [-hw, hw] x [0, zt] from the circle centre
            tx = (hw if c > 0 else -hw) / c if abs(c) > 1e-9 else 1e9
            tz = ((zt - zc_c) if s > 0 else (-zc_c)) / s if abs(s) > 1e-9 else 1e9
            tt = min(abs(tx), abs(tz))
            q = Vector((c * tt, zc_c + s * tt))
            q.y = max(q.y, 0.0)
            verts.append((p.x, y, max(p.y, -0.0)))
            verts.append((q.x, y, q.y))
    def vi(side, k, outer):
        return side * 2 * N + 2 * (k % N) + (1 if outer else 0)
    for k in range(N):
        faces.append((vi(0, k, 0), vi(0, k, 1), vi(0, k + 1, 1), vi(0, k + 1, 0)))
        faces.append((vi(1, k, 0), vi(1, k + 1, 0), vi(1, k + 1, 1), vi(1, k, 1)))
        faces.append((vi(0, k, 0), vi(0, k + 1, 0), vi(1, k + 1, 0), vi(1, k, 0)))     # inner tube
        faces.append((vi(0, k, 1), vi(1, k, 1), vi(1, k + 1, 1), vi(0, k + 1, 1)))     # outer rim
    body = U.mesh_from_pydata(_child(root, "wall"), verts, faces, collection, materials=[_mat(mat)],
                              smooth=False, parent=root)
    _recalc_normals(body)
    # dado
    dv, df, dm = [], [], []
    _wall_box(dv, df, dm, Vector((-hw, 0)), Vector((-radius * 1.02, 0)), thickness + 0.08, -0.4, 0.7, 0)
    _wall_box(dv, df, dm, Vector((radius * 1.02, 0)), Vector((hw, 0)), thickness + 0.08, -0.4, 0.7, 0)
    U.mesh_from_pydata(_child(root, "dado"), dv, df, collection, materials=["stone_grey"], smooth=False,
                       parent=root)
    # marble ring frame (both faces) and threshold
    bm = bmesh.new()
    fw = _clamp(0.12 * radius, 0.14, 0.3)
    prof = [(radius - 0.02, -ht - 0.06), (radius + fw, -ht - 0.06), (radius + fw, ht + 0.06),
            (radius - 0.02, ht + 0.06)]
    rings = []
    for k in range(N):
        a = TAU * k / N
        rings.append([bm.verts.new((r * math.cos(a), y, zc_c + r * math.sin(a))) for r, y in prof])
    for k in range(N):
        A_, B_ = rings[k], rings[(k + 1) % N]
        for j in range(4):
            j2 = (j + 1) % 4
            bm.faces.new((A_[j], B_[j], B_[j2], A_[j2]))
    bm.normal_update()
    U.bm_box(bm, (2 * radius * 0.86, thickness + 0.14, 0.14), (0, 0, 0.0))
    # cut the ring below the threshold
    for v in list(bm.verts):
        if v.co.z < -0.05:
            v.co.z = -0.05
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    U.mesh_from_bmesh(_child(root, "frame"), bm, collection, materials=[frame_mat], smooth=math.radians(40),
                      parent=root)
    _roof(_child(root, "coping"), collection, wall_width + 0.1, thickness, "xuanshan",
          overhang=_clamp(0.4 * thickness, 0.22, 0.45), side_overhang=0.15, tile_mat=cap_mat, ornaments="simple",
          beasts=0, rise=0.38 * (0.5 * thickness + 0.3), gable_parts="none", detail="low", parent=root,
          location=(0, 0, zt))
    root["arch_height"] = h + 0.4
    return root


def _p_bell(h):
    """Bronze temple bell, unit = height h, hanging from z = 0 down to -h."""
    key = "bell.%d" % round(h * 100)

    def build(col):
        prof = [(0.0, -1.0), (0.42, -1.0), (0.44, -0.96), (0.40, -0.9), (0.37, -0.6), (0.33, -0.3),
                (0.3, -0.12), (0.22, -0.04), (0.08, -0.02), (0.06, 0.0), (0.0, 0.0)]
        bm = bmesh.new()
        U.bm_lathe(bm, [(r * h, z * h) for r, z in prof], segments=24)
        for zz in (-0.86, -0.55, -0.3):
            r = 0.4 * h if zz < -0.8 else (0.36 * h if zz < -0.5 else 0.33 * h)
            vs = U.bm_lathe(bm, [(0.0, zz * h - 0.015 * h), (r + 0.012 * h, zz * h - 0.015 * h),
                                 (r + 0.012 * h, zz * h + 0.015 * h), (0.0, zz * h + 0.015 * h)], segments=24)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        _proto_obj(col, "bell", bm, ["bronze_verdigris"], smooth=math.radians(40))
    return _proto(key, build)


def _p_drum(d):
    """Great drum, diameter d, axis along Y, centred at the origin; red body, skin faces, gold studs."""
    key = "drum.%d" % round(d * 100)

    def build(col):
        r = d * 0.5
        L = d * 0.75
        prof = [(0.0, -L / 2), (r * 0.92, -L / 2), (r * 0.98, -L / 4), (r, 0.0), (r * 0.98, L / 4),
                (r * 0.92, L / 2), (0.0, L / 2)]
        bm = bmesh.new()
        U.bm_lathe(bm, prof, segments=28)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
        bmesh.ops.rotate(bm, verts=bm.verts[:], matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        body = _proto_obj(col, "body", bm, ["lacquer_red", "paper_aged"], smooth=math.radians(30))
        # skins: faces whose normal is along Y
        me = body.data
        idx = [1 if abs(p.normal.y) > 0.95 else 0 for p in me.polygons]
        me.polygons.foreach_set("material_index", idx)
        g = bmesh.new()
        for sy in (-1, 1):
            for k in range(20):
                a = TAU * k / 20
                U.bm_cylinder(g, 0.025 * d, 0.03 * d, 6, center=(r * 0.92 * math.cos(a), sy * L / 2 * 0.98,
                                                                    r * 0.92 * math.sin(a)),
                              matrix=None)
        _proto_obj(col, "studs", g, ["gold"], smooth=False)
    return _proto(key, build)


_GAP_SIDES = ("-x", "+x", "-y", "+y")


def _open_gaps(points, gaps, min_len=0.4):
    """Cut openings out of an open 2D polyline that runs along the sides of a centred square.
    Each gap (side, lo, hi), side '-x', '+x', '-y' or '+y', removes the part of every segment on
    that side whose coordinate along the side (y for the x sides, x for the y sides) lies in lo..hi.
    Returns [(points, keeps_first, keeps_last)]: keeps_first/keeps_last say whether the piece still
    ends at the polyline's own first/last point. Pieces shorter than ``min_len`` are dropped."""
    for g in gaps:
        if g[0] not in _GAP_SIDES:
            raise ValueError("gap side %r: use one of %s" % (g[0], ", ".join(_GAP_SIDES)))
    pts = [Vector((p[0], p[1])) for p in points]
    raw = []
    cur, cur_first = [pts[0]], True
    for a, b in zip(pts[:-1], pts[1:]):
        d = b - a
        if d.length < 1e-6:
            continue
        if abs(d.x) < abs(d.y):
            side, u0, u1 = ("+x" if a.x > 0 else "-x"), a.y, b.y
        else:
            side, u0, u1 = ("+y" if a.y > 0 else "-y"), a.x, b.x
        cuts = []
        for s, lo, hi in gaps:
            if s != side:
                continue
            t0, t1 = sorted(((lo - u0) / (u1 - u0), (hi - u0) / (u1 - u0)))
            t0, t1 = max(t0, 0.0), min(t1, 1.0)
            if t1 > t0:
                cuts.append((t0, t1))
        t = 0.0
        for t0, t1 in sorted(cuts):
            if t1 <= t:
                continue
            if t0 > t:
                cur.append(a + d * t0)
            raw.append((cur, cur_first, False))
            cur, cur_first = [a + d * t1], False
            t = t1
        if t < 1.0:
            cur.append(b)
    raw.append((cur, cur_first, True))
    out = []
    for piece, first, last in raw:
        clean = [piece[0]]
        for p in piece[1:]:
            if (p - clean[-1]).length > 1e-6:
                clean.append(p)
        if len(clean) >= 2 and sum((q - p).length for p, q in zip(clean[:-1], clean[1:])) >= min_len:
            out.append((clean, first, last))
    return out


def tower(name, collection, kind="bell", size=9.0, base_h=3.2, column_h=4.0, roof_mat="roof_tile_teal",
          lit=False, seed=0, parent=None, location=(0, 0, 0), rotation_z=0.0, bal_gaps=()):
    """Bell tower or drum tower facing -Y: a tall xumizuo base with front stairs and a marble
    balustrade, an open 3x3-bay pavilion with hanging lattice fascias, a double-eave xieshan roof,
    and a bronze bell (``kind`` 'bell') or a great red drum on a stand ('drum') inside.
    ``size``: base width. ``bal_gaps``: openings in the base balustrade, e.g. where a raised
    corridor docks at floor height ``base_h``; each (side, lo, hi) with side '-x', '+x', '+y' or
    '-y' in the tower's own frame (before ``rotation_z``) and lo..hi the opening along that side in
    local metres (y for the x sides, x for the y sides). The front is already open over the stairs.
    Example: bal_gaps=(('+x', -2.0, 2.0),) opens 4 m in the middle of the +X side.
    Root props: arch_height, arch_floor_z."""
    root = _root(name, collection, parent, location, rotation_z, size=1.5)
    platform(_child(root, "base"), collection, size, size, base_h, parent=root)
    _stairs(_child(root, "stairs"), collection, _clamp(0.32 * size, 1.8, 3.6), base_h, ramp=False,
            balustrade=True, bal_extend=0.3, parent=root, location=(0, -size / 2, 0))
    W = size - 2.6
    z0 = base_h
    hw = size / 2 - 0.3
    sw = _clamp(0.32 * size, 1.8, 3.6) / 2 - 0.25
    # both ends meet the stair balustrades' last posts (no post of their own); a gap's edges get posts
    path = [(-sw, -hw), (-hw, -hw), (-hw, hw), (hw, hw), (hw, -hw), (sw, -hw)]
    for pts, keeps_first, keeps_last in _open_gaps(path, tuple(bal_gaps or ())):
        no_post = ("both" if keeps_first and keeps_last else
                   "start" if keeps_first else "end" if keeps_last else None)
        _balustrade(_child(root, "bal"), collection, [(p.x, p.y, z0) for p in pts], height=1.0,
                    no_post=no_post, parent=root)
    xs = _grid(3, W / 3, center=1.15, ends=1.0)
    cr = _clamp(0.03 * column_h + 0.12, 0.18, 0.32)
    for i, x in enumerate(xs):
        for j, y in enumerate(xs):
            if i in (0, 3) or j in (0, 3):
                column(_child(root, "col"), collection, column_h, cr, parent=root, location=(x, y, z0))
    H1 = band_height_for(W) * 0.85
    bracket_band(_child(root, "band"), collection, W, W, height=H1, grid=(xs, xs), parent=root,
                 location=(0, 0, z0 + column_h))
    arch = column_h - 1.08 * H1 / 1.2
    for k, (a, b) in enumerate(_side_frames(W, W, 4)):
        for i in range(3):
            pa = a + (b - a) * (i / 3.0)
            pb = a + (b - a) * ((i + 1) / 3.0)
            c = (pa + pb) * 0.5
            fl = (pb - pa).length - 2 * cr
            gh = 0.45
            lattice_panel(_child(root, "gualuo"), collection, round(fl, 3), gh, "diamond", "window", paper=False,
                          parent=root, location=(c.x, c.y, z0 + arch - gh), rotation_z=_face_rot(a, b))
    zr = z0 + column_h + H1
    inset = 0.24 * W
    sk = roof_shape(W, W, "skirt", top_inset=inset)
    _roof(_child(root, "skirt"), collection, W, W, "skirt", top_inset=inset, tile_mat=roof_mat, parent=root,
          location=(0, 0, zr))
    z_sk = zr + sk.z_top(sk.cut)
    Wi = W - 2 * inset
    fr = 0.5 + 0.05 * W
    fv, ff, fm = [], [], []
    q = [Vector((-Wi / 2, -Wi / 2)), Vector((Wi / 2, -Wi / 2)), Vector((Wi / 2, Wi / 2)), Vector((-Wi / 2, Wi / 2))]
    for k in range(4):
        _wall_box(fv, ff, fm, q[k], q[(k + 1) % 4], 0.3, z_sk - 0.5, z_sk + fr, 0)
    U.mesh_from_pydata(_child(root, "frieze"), fv, ff, collection, materials=[_mat("arch_paint_red")],
                       smooth=False, parent=root)
    for p in q:
        column(_child(root, "col_up"), collection, fr + 0.5, cr * 0.9, parent=root, location=(p.x, p.y, z_sk - 0.5))
    H2 = band_height_for(Wi) * 0.8
    bracket_band(_child(root, "band_up"), collection, Wi, Wi, height=H2, architrave=False, parent=root,
                 location=(0, 0, z_sk + fr))
    up = _roof(_child(root, "roof"), collection, Wi, Wi - 0.001, "xieshan", tile_mat=roof_mat,
               overhang=max(0.75 * sk.ov, 1.2), parent=root, location=(0, 0, z_sk + fr + H2))
    # contents, hung from a beam frame under the band
    zh = z0 + column_h - 0.2
    if kind == "bell":
        bh = _clamp(0.42 * column_h, 1.2, 2.6)
        _painted_beams(_child(root, "bell_beam"), collection, root,
                       [((-W / 2, 0, zh - 0.35), (W / 2, 0, zh - 0.35), 0.3, 0.35, 0)])
        U.collection_instance(_p_bell(round(bh, 2)), _child(root, "bell"), collection,
                              location=(0, 0, zh - 0.35), parent=root)
    else:
        dd = _clamp(0.42 * column_h, 1.2, 2.4)
        st = bmesh.new()
        for sx in (-1, 1):
            U.bm_box(st, (0.14, dd * 0.8, dd * 0.55), (sx * dd * 0.42, 0, dd * 0.27))
        U.bm_box(st, (dd * 0.98, dd * 0.7, 0.1), (0, 0, dd * 0.12))
        U.mesh_from_bmesh(_child(root, "drum_stand"), st, collection, materials=["lacquer_red_worn"],
                          smooth=False, parent=root, location=(0, 0, z0))
        U.collection_instance(_p_drum(round(dd, 2)), _child(root, "drum"), collection,
                              location=(0, 0, z0 + dd * 0.55 + dd * 0.42), parent=root)
    root["arch_height"] = z_sk + fr + H2 + up["arch_top_z"]
    root["arch_floor_z"] = z0
    return root


# ======================================================================== showcase

def showcase(collection):
    """Preview courtyard: a 5-bay paifang at the entrance, a paved axis to a double-eave hall on a
    xumizuo terrace with ramped stairs and balustrades, a 7-storey pagoda back right, a hexagonal
    pavilion front left and a covered corridor down the left side. Returns the root Empty."""
    root = _root("arch.showcase", collection, size=3.0)
    # paved court (preview only; areas build their own paving)
    v, f, m = [], [], []
    _wall_box(v, f, m, Vector((0, -44)), Vector((0, 40)), 74.0, -0.45, 0.0, 0)
    court = U.mesh_from_pydata(_child(root, "court"), v, f, collection, materials=["marble_paving"],
                               smooth=False, parent=root)
    v, f, m = [], [], []
    _wall_box(v, f, m, Vector((0, -40)), Vector((0, 4.5)), 7.0, -0.2, 0.06, 0)
    U.mesh_from_pydata(_child(root, "axis"), v, f, collection, materials=["marble_white"], smooth=False,
                       parent=root)
    hall(_child(root, "hall"), collection, bays_w=5, bays_d=3, bay=4.6, column_h=5.4, double_eave=True,
         platform_h=1.7, lit=True, parent=root, location=(0, 15.0, 0))
    paifang(_child(root, "gate"), collection, bays=5, width=24.0, height=16.0, parent=root,
            location=(0, -34.0, 0))
    pagoda(_child(root, "pagoda"), collection, tiers=7, sides=8, radius=4.2, tier_h=4.1,
           lit_floors=(2, 4), platform_h=1.2, parent=root, location=(26.0, 22.0, 0))
    pavilion(_child(root, "pavilion"), collection, sides=6, radius=2.9, height=3.3, parent=root,
             location=(-18.0, -15.0, 0), rotation_z=math.radians(20))
    corridor(_child(root, "corridor"), collection, [(-30.0, -30.0), (-30.0, 20.0), (-16.0, 31.0)],
             width=3.0, height=3.1, parent=root)
    return root


showcase.preview_cameras = [
    ("front_34", (-52.0, -78.0, 26.0), (2.0, 4.0, 8.0), 35),
    ("front", (0.0, -70.0, 5.0), (0.0, 10.0, 10.0), 35),
    ("aerial", (-34.0, -66.0, 62.0), (2.0, 4.0, 2.0), 35),
    ("detail", (-12.0, -9.0, 4.0), (-1.0, 6.0, 9.5), 35),
    ("pagoda", (12.0, -4.0, 3.0), (25.0, 20.0, 15.0), 35),
]
