"""Shared helpers for every Moonlit Sect module.

Small, dependency-free building blocks: names, collections, objects, meshes,
instancing, bevel/smoothing, seeded randomness, noise, tubes, text and stats.

Conventions (see spec.md section 2): meters, Z up, a builder's front faces -Y.
Every function here is deterministic. Anything that takes ``parent=`` interprets
``location`` / ``rotation`` / ``scale`` / ``matrix`` in the parent's local space.
Materials may be passed as ``bpy.types.Material`` objects or as names understood
by :func:`sect.lib.materials.get`.
"""

import math
import os
import random
import zlib

import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector
from mathutils import noise as _mnoise

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).replace("\\", "/")
FONT_KAITI = "C:/Windows/Fonts/simkai.ttf"
FONT_YAHEI = "C:/Windows/Fonts/msyh.ttc"
PROTO_ROOT = "_protos"
EDGE_ATTR = "edge"          # face attribute written by bevel_mesh(); materials read it for edge wear

__all__ = [
    "ROOT", "FONT_KAITI", "FONT_YAHEI", "PROTO_ROOT", "EDGE_ATTR",
    "out_path", "unique_name", "name",
    "get_collection", "link", "unlink_all", "clear_collection", "delete_hierarchy",
    "trs", "set_transform", "world_matrix", "parent", "empty", "object_from_mesh",
    "set_materials", "set_object_material", "mesh_from_pydata", "mesh_from_bmesh", "shared_mesh",
    "instance", "proto_collection", "collection_instance",
    "auto_smooth", "shade_flat", "bevel", "bevel_mesh", "apply_modifiers",
    "set_visibility",
    "seed_from", "rng", "noise3", "fbm", "noise_vec", "jitter",
    "catmull_rom", "tube_mesh", "curve_tube",
    "bm_box", "bm_cylinder", "bm_lathe", "bm_transform",
    "load_font", "text", "align_z", "evaluated_triangle_count",
]


# ---------------------------------------------------------------- paths & names

def out_path(*parts, make_dirs=True):
    """Absolute path under ROOT/out/; creates the parent folder. out_path('previews','arch','a.png')."""
    path = "/".join([ROOT, "out"] + [str(p).strip("/") for p in parts])
    if make_dirs:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


_NAME_COUNTERS = {}


def unique_name(base, pool=None):
    """Return ``base`` if no datablock in ``pool`` (default bpy.data.objects) uses it,
    else ``base.001``, ``base.002``, ... (first free)."""
    pool = bpy.data.objects if pool is None else pool
    if pool.get(base) is None:
        return base
    # stable key (id() of the temporary bpy collection wrapper changes between calls), and a
    # cached counter only counts if its name still exists (after look.reset_scene() it does
    # not), so a rebuild in the same session gets the same names
    key = (getattr(getattr(pool, "bl_rna", None), "identifier", None) or type(pool).__name__, base)
    n = _NAME_COUNTERS.get(key, 0)
    if n and pool.get("%s.%03d" % (base, n)) is None:
        n = 0
    while True:
        n += 1
        cand = "%s.%03d" % (base, n)
        if pool.get(cand) is None:
            _NAME_COUNTERS[key] = n
            return cand


def name(prefix, *parts, pool=None):
    """Unique, prefixed object name: name('gate', 'column', 3) -> 'gate.column.3' (or '.001' if taken).
    Parts already starting with the prefix are not double-prefixed."""
    bits = [str(p) for p in parts if p not in (None, "")]
    base = ".".join(bits)
    if prefix:
        if not (base == prefix or base.startswith(prefix + ".")):
            base = prefix + "." + base if base else prefix
    return unique_name(base, pool)


# ---------------------------------------------------------------- collections

def _scene(scene=None):
    return scene or bpy.context.scene


def _as_collection(col, scene=None):
    if col is None:
        return _scene(scene).collection
    if isinstance(col, str):
        return get_collection(col, scene=scene)
    return col


def get_collection(name, parent=None, scene=None):
    """Return collection ``name``, creating it if needed.

    ``parent`` is a Collection, a collection name, or None (the scene's master collection).
    An existing collection is linked under an explicit ``parent`` if it is not already;
    with ``parent=None`` it is only linked if it is not in the scene at all."""
    sc = _scene(scene)
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    if parent is not None:
        pcol = _as_collection(parent, sc)
        if pcol.children.get(col.name) is None:
            pcol.children.link(col)
    else:
        master = sc.collection
        if master.children.get(col.name) is None and col not in master.children_recursive:
            master.children.link(col)
    return col


def link(obj, collection, exclusive=False):
    """Link ``obj`` into ``collection`` (Collection or name). ``exclusive`` unlinks it elsewhere. Returns obj."""
    col = _as_collection(collection)
    if exclusive:
        for c in list(obj.users_collection):
            if c != col:
                c.objects.unlink(obj)
    if col.objects.get(obj.name) is None:
        col.objects.link(obj)
    return obj


def unlink_all(obj):
    """Remove ``obj`` from every collection it is in (the object itself survives)."""
    for c in list(obj.users_collection):
        c.objects.unlink(obj)


def delete_hierarchy(obj):
    """Delete ``obj`` and all its descendants. Mesh data with no remaining users is removed too."""
    stack, todo = [obj], []
    while stack:
        o = stack.pop()
        todo.append(o)
        stack.extend(o.children)
    datas = {o.data for o in todo if o.data is not None}
    for o in todo:
        bpy.data.objects.remove(o, do_unlink=True)
    for d in datas:
        if d.users == 0:
            if isinstance(d, bpy.types.Mesh):
                bpy.data.meshes.remove(d)
            elif isinstance(d, bpy.types.Curve):
                bpy.data.curves.remove(d)


def clear_collection(collection, recursive=True):
    """Delete every object in ``collection`` (and child collections if ``recursive``)."""
    col = _as_collection(collection)
    objs = list(col.all_objects) if recursive else list(col.objects)
    for o in objs:
        if o.name in bpy.data.objects:
            bpy.data.objects.remove(o, do_unlink=True)


# ---------------------------------------------------------------- transforms

def _rot_matrix(rotation):
    if rotation is None:
        return Matrix.Identity(4)
    if isinstance(rotation, Quaternion):
        return rotation.to_matrix().to_4x4()
    if isinstance(rotation, Matrix):
        return rotation.to_4x4()
    return Euler(rotation, 'XYZ').to_matrix().to_4x4()


def trs(location=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1)):
    """Compose a 4x4 matrix from location, rotation (XYZ Euler radians, Quaternion or Matrix) and scale."""
    if isinstance(scale, (int, float)):
        scale = (scale, scale, scale)
    s = Matrix.Diagonal((scale[0], scale[1], scale[2], 1.0))
    return Matrix.Translation(Vector(location)) @ _rot_matrix(rotation) @ s


def set_transform(obj, location=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1), matrix=None):
    """Set ``obj.matrix_basis`` from ``matrix`` if given, else from location/rotation/scale."""
    if matrix is not None:
        obj.matrix_basis = Matrix(matrix)
    else:
        obj.matrix_basis = trs(location, rotation, scale)
    return obj


def world_matrix(obj):
    """World matrix computed from the parent chain (no depsgraph update needed;
    ignores constraints and bone/vertex parenting)."""
    m = obj.matrix_parent_inverse @ obj.matrix_basis if obj.parent else obj.matrix_basis.copy()
    if obj.parent:
        m = world_matrix(obj.parent) @ m
    return m


def parent(child, parent_obj, keep_transform=True):
    """Parent ``child`` to ``parent_obj`` (None un-parents).

    keep_transform=True keeps the child's current world placement (its local
    matrix is recomputed; matrix_parent_inverse is reset to identity, so child.location is
    always relative to the parent). keep_transform=False keeps the local values as they are."""
    w = world_matrix(child) if keep_transform else None
    child.parent = parent_obj
    child.matrix_parent_inverse = Matrix.Identity(4)
    if keep_transform:
        pw = world_matrix(parent_obj) if parent_obj else Matrix.Identity(4)
        child.matrix_basis = pw.inverted_safe() @ w
    return child


def _place(obj, collection, location, rotation, scale, parent_obj, matrix):
    if collection is not None:
        link(obj, collection)
    if parent_obj is not None:
        obj.parent = parent_obj
        obj.matrix_parent_inverse = Matrix.Identity(4)
    set_transform(obj, location, rotation, scale, matrix)
    return obj


def empty(name, collection, location=(0, 0, 0), parent=None, display_size=1.0,
          display_type='PLAIN_AXES', rotation=(0, 0, 0), scale=(1, 1, 1), matrix=None):
    """Create an Empty (e.g. an area root '<key>.root'). Returns the object."""
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = display_size
    ob.empty_display_type = display_type
    return _place(ob, collection, location, rotation, scale, parent, matrix)


def align_z(direction, up=(0, 0, 1)):
    """3x3 rotation whose local +Z points along ``direction`` (X stays as horizontal as possible)."""
    z = Vector(direction).normalized()
    upv = Vector(up)
    if abs(z.dot(upv)) > 0.999:
        upv = Vector((0, 1, 0)) if abs(z.y) < 0.9 else Vector((1, 0, 0))
    x = upv.cross(z).normalized()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed()


def set_visibility(obj, camera=True, shadow=True, diffuse=True, glossy=True,
                   transmission=True, volume_scatter=True):
    """Per-object ray visibility (e.g. light beams: shadow=False). Returns obj."""
    obj.visible_camera = camera
    obj.visible_shadow = shadow
    obj.visible_diffuse = diffuse
    obj.visible_glossy = glossy
    obj.visible_transmission = transmission
    obj.visible_volume_scatter = volume_scatter
    return obj


# ---------------------------------------------------------------- meshes

def _resolve_material(m):
    if m is None or isinstance(m, bpy.types.Material):
        return m
    from . import materials  # lazy: materials does not import util
    return materials.get(m)


def set_materials(target, materials):
    """Replace the material slots of a Mesh/Curve (or an object's data) with ``materials``
    (Materials or material names; a single value is accepted). Per-face material indices
    already on a mesh (from a BMesh or ``material_indices``) are kept."""
    data = target.data if isinstance(target, bpy.types.Object) else target
    if materials is None:
        return target
    if isinstance(materials, (str, bpy.types.Material)):
        materials = [materials]
    # Blender's materials.clear() also resets every face's material_index; save and restore them
    idx = None
    if isinstance(data, bpy.types.Mesh) and len(data.polygons):
        idx = [0] * len(data.polygons)
        data.polygons.foreach_get("material_index", idx)
        if not any(idx):
            idx = None
    data.materials.clear()
    for m in materials:
        data.materials.append(_resolve_material(m))
    if idx is not None:
        data.polygons.foreach_set("material_index", idx)
    return target


def set_object_material(obj, material, slot=0):
    """Override one material slot on the *object* (not the shared mesh), so linked duplicates
    can share geometry but differ in material (e.g. banners of different colours)."""
    data = obj.data
    while len(data.materials) <= slot:
        data.materials.append(None)
    ms = obj.material_slots[slot]
    ms.link = 'OBJECT'
    ms.material = _resolve_material(material)
    return obj


def auto_smooth(target, angle=math.radians(30)):
    """Shade smooth but keep edges sharper than ``angle`` (radians) hard.
    Blender 5.x: sets every face smooth, then Mesh.set_sharp_from_angle(). Accepts Object or Mesh."""
    me = target.data if isinstance(target, bpy.types.Object) else target
    n = len(me.polygons)
    if n:
        me.polygons.foreach_set("use_smooth", [True] * n)
    me.set_sharp_from_angle(angle=angle)
    return target


def shade_flat(target):
    """Flat-shade every face of an Object or Mesh."""
    me = target.data if isinstance(target, bpy.types.Object) else target
    n = len(me.polygons)
    if n:
        me.polygons.foreach_set("use_smooth", [False] * n)
    return target


def _apply_smooth(me, smooth):
    if smooth is True:
        n = len(me.polygons)
        if n:
            me.polygons.foreach_set("use_smooth", [True] * n)
    elif smooth is False:
        shade_flat(me)
    elif isinstance(smooth, (int, float)):
        auto_smooth(me, float(smooth))


def object_from_mesh(name, mesh, collection, location=(0, 0, 0), rotation=(0, 0, 0),
                     scale=(1, 1, 1), parent=None, matrix=None):
    """Wrap existing mesh data in a new object (data is shared, not copied)."""
    ob = bpy.data.objects.new(name, mesh)
    return _place(ob, collection, location, rotation, scale, parent, matrix)


def mesh_from_pydata(name, verts, faces, collection, materials=None, smooth=False, edges=(),
                     material_indices=None, uvs=None, location=(0, 0, 0), rotation=(0, 0, 0),
                     scale=(1, 1, 1), parent=None, matrix=None):
    """Build a mesh object from vertex/face lists.

    smooth: False (flat), True (smooth) or an angle in radians (auto smooth).
    material_indices: one slot index per face. uvs: one (u, v) per face corner, in face order."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], list(edges), [tuple(f) for f in faces])
    me.validate(verbose=False)
    if material_indices is not None and len(material_indices) == len(me.polygons):
        me.polygons.foreach_set("material_index", list(material_indices))
    if uvs is not None:
        uvl = me.uv_layers.new(name="UVMap")
        flat = [c for uv in uvs for c in uv]
        if len(flat) == 2 * len(me.loops):
            uvl.data.foreach_set("uv", flat)
    _apply_smooth(me, smooth)
    set_materials(me, materials)
    me.update()
    return object_from_mesh(name, me, collection, location, rotation, scale, parent, matrix)


def mesh_from_bmesh(name, bm, collection, materials=None, smooth=None, free=True,
                    location=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1), parent=None, matrix=None):
    """Write a BMesh into a new mesh object. ``smooth`` None keeps the BMesh face flags.
    The BMesh is freed unless free=False."""
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    if free:
        bm.free()
    _apply_smooth(me, smooth)
    set_materials(me, materials)
    me.update()
    return object_from_mesh(name, me, collection, location, rotation, scale, parent, matrix)


def shared_mesh(key, build):
    """Mesh cache: return the mesh tagged ``key`` if it exists, else call ``build()``
    (returning a Mesh or a BMesh) once and tag the result. Use for prototypes reused many times."""
    me = bpy.data.meshes.get(key)
    if me is not None and me.get("sect_shared") == key:
        return me
    res = build()
    if isinstance(res, bmesh.types.BMesh):
        me = bpy.data.meshes.new(key)
        res.to_mesh(me)
        res.free()
    else:
        me = res
        me.name = key
    me["sect_shared"] = key
    return me


# ---------------------------------------------------------------- instancing

def instance(src_obj, name, collection, location=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1),
             parent=None, matrix=None):
    """Linked duplicate (Alt+D): a new object sharing ``src_obj``'s data, modifiers and
    material slots. Apply modifiers on the prototype first so all copies share one evaluated mesh."""
    ob = src_obj.copy()
    ob.name = name
    ob.parent = None
    return _place(ob, collection, location, rotation, scale, parent, matrix)


def _layer_collections(lc):
    yield lc
    for ch in lc.children:
        yield from _layer_collections(ch)


def _exclude_everywhere(col):
    for sc in bpy.data.scenes:
        for vl in sc.view_layers:
            for lc in _layer_collections(vl.layer_collection):
                if lc.collection == col and not lc.exclude:
                    lc.exclude = True


def proto_collection(name, scene=None):
    """Collection for instancing sources. It lives under ``_protos``, which is excluded from
    every view layer, so its objects never render directly; collection_instance() still shows them.
    Build prototypes at the origin."""
    sc = _scene(scene)
    root = get_collection(PROTO_ROOT, scene=sc)
    col = get_collection(name, parent=root, scene=sc)
    _exclude_everywhere(root)
    return col


def collection_instance(src_collection, name, collection, location=(0, 0, 0), rotation=(0, 0, 0),
                        scale=(1, 1, 1), parent=None, matrix=None, display_size=0.5):
    """Empty that instances ``src_collection`` (Collection or name)."""
    src = bpy.data.collections[src_collection] if isinstance(src_collection, str) else src_collection
    ob = bpy.data.objects.new(name, None)
    ob.instance_type = 'COLLECTION'
    ob.instance_collection = src
    ob.empty_display_size = display_size
    return _place(ob, collection, location, rotation, scale, parent, matrix)


# ---------------------------------------------------------------- bevel / modifiers

def bevel(obj, width=0.02, segments=2, angle_limit=math.radians(30), harden_normals=True,
          profile=0.5, limit_method='ANGLE', clamp=True, apply=False):
    """Add (or update) a Bevel modifier named 'Bevel'. With harden_normals the faces are set
    smooth so flat faces stay flat and the rounded edges catch highlights.
    apply=True bakes it into the mesh (affects every object sharing the mesh). Returns the modifier
    (or None when applied)."""
    mod = obj.modifiers.get("Bevel") or obj.modifiers.new("Bevel", 'BEVEL')
    mod.width = width
    mod.segments = segments
    mod.limit_method = limit_method
    if limit_method == 'ANGLE':
        mod.angle_limit = angle_limit
    mod.profile = profile
    mod.use_clamp_overlap = clamp
    mod.harden_normals = harden_normals
    if harden_normals and obj.type == 'MESH':
        n = len(obj.data.polygons)
        if n:
            obj.data.polygons.foreach_set("use_smooth", [True] * n)
    if apply:
        apply_modifiers(obj)
        return None
    return mod


def bevel_mesh(target, width=0.02, segments=2, angle_limit=math.radians(30), mark=EDGE_ATTR):
    """Bevel a mesh in place with bmesh (no modifier) and write a FACE float attribute ``mark``
    (1 on the new bevel faces, 0 elsewhere). Normals are hardened (flat faces stay flat, bevels
    round). Materials such as lacquer_red_worn, gold, bronze use the attribute for edge wear.
    Accepts an Object or a Mesh; affects every user of the mesh. Returns the mesh."""
    me = target.data if isinstance(target, bpy.types.Object) else target
    bm = bmesh.new()
    bm.from_mesh(me)
    layer = bm.faces.layers.float.get(mark) or bm.faces.layers.float.new(mark)
    edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > angle_limit]
    if edges:
        res = bmesh.ops.bevel(bm, geom=edges, offset=width, offset_type='OFFSET', segments=segments,
                              profile=0.5, affect='EDGES', clamp_overlap=True, material=-1,
                              loop_slide=True)
        for f in res["faces"]:
            f[layer] = 1.0
    for f in bm.faces:
        f.smooth = True
    bm.normal_update()
    # hardened custom normals: ordinary faces are smooth-by-angle among themselves (flat walls
    # stay flat, cylinders stay round); bevel faces take the normal of the ordinary faces they
    # touch, so the whole strip reads as one rounded edge
    areas = {f: max(f.calc_area(), 1e-12) for f in bm.faces}
    loop_normals = []
    for f in bm.faces:
        is_bevel = f[layer] >= 0.5
        for lp in f.loops:
            v = lp.vert
            n = Vector((0, 0, 0))
            if not is_bevel:
                for g in v.link_faces:
                    if g[layer] < 0.5 and f.normal.angle(g.normal, 0.0) <= angle_limit:
                        n += g.normal * areas[g]
            else:
                for g in v.link_faces:
                    if g[layer] < 0.5:
                        n += g.normal * areas[g]
                if n.length < 1e-9:
                    for g in v.link_faces:
                        n += g.normal * areas[g]
            loop_normals.append(n.normalized() if n.length > 1e-9 else f.normal.copy())
    bm.to_mesh(me)
    bm.free()
    me.normals_split_custom_set([tuple(n) for n in loop_normals])
    me.update()
    return me


def apply_modifiers(obj):
    """Bake the object's modifier stack into new mesh data for this object only (other users
    of the old mesh keep it). Works for objects outside the view layer (e.g. in a proto collection)."""
    if obj.type != 'MESH' or not obj.modifiers:
        return obj
    sc = bpy.context.scene
    temp = obj.name not in bpy.context.view_layer.objects
    if temp:
        sc.collection.objects.link(obj)
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = obj.evaluated_get(dg)
    new_me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    old = obj.data
    keep_name = old.name
    obj.modifiers.clear()
    obj.data = new_me
    if old.users == 0:
        old.name = keep_name + "~old"
        new_me.name = keep_name
    if temp:
        sc.collection.objects.unlink(obj)
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return obj


# ---------------------------------------------------------------- randomness & noise

def seed_from(*parts):
    """Stable 31-bit seed from any values (unlike hash(), identical across Python runs)."""
    return zlib.crc32("|".join(str(p) for p in parts).encode("utf-8")) & 0x7FFFFFFF


def rng(seed=0, *salt):
    """random.Random seeded deterministically from ``seed`` (and optional salt values)."""
    return random.Random(seed_from(seed, *salt) if salt or not isinstance(seed, int) else seed)


def _offset(seed):
    if not seed:
        return Vector((0.0, 0.0, 0.0))
    r = random.Random(seed_from("noise", seed))
    return Vector((r.uniform(-300, 300), r.uniform(-300, 300), r.uniform(-300, 300)))


def noise3(p, scale=1.0, seed=0):
    """Perlin noise in [-1, 1] at point ``p`` (frequency ``scale`` per meter, seed shifts the field)."""
    return _mnoise.noise(Vector(p) * scale + _offset(seed), noise_basis='PERLIN_NEW')


def fbm(p, scale=1.0, octaves=4, lacunarity=2.0, gain=0.5, seed=0):
    """Fractal (fBm) Perlin noise, roughly in [-1, 1]."""
    q = Vector(p) * scale + _offset(seed)
    amp, total, norm, freq = 1.0, 0.0, 0.0, 1.0
    for _ in range(max(1, octaves)):
        total += amp * _mnoise.noise(q * freq, noise_basis='PERLIN_NEW')
        norm += amp
        amp *= gain
        freq *= lacunarity
    return total / norm


def noise_vec(p, scale=1.0, seed=0):
    """Vector-valued Perlin noise (each component roughly in [-1, 1])."""
    return _mnoise.noise_vector(Vector(p) * scale + _offset(seed), noise_basis='PERLIN_NEW')


def jitter(r, amount, axes=(1, 1, 1)):
    """Random offset vector from random.Random ``r``: each axis uniform in [-amount, amount] * axes."""
    return Vector(tuple(r.uniform(-amount, amount) * a for a in axes))


# ---------------------------------------------------------------- curves & tubes

def catmull_rom(points, samples_per_segment=8, closed=False):
    """Uniform Catmull-Rom resampling through ``points`` (the curve passes through every point).
    Points may be (x, y, z) or (x, y, z, w); w (e.g. a radius factor) is interpolated too.
    Returns a list of 4-tuples (x, y, z, w)."""
    pts = [tuple(p) + (1.0,) if len(p) == 3 else tuple(p) for p in points]
    n = len(pts)
    if n < 2:
        return pts
    out = []
    seg_count = n if closed else n - 1
    for i in range(seg_count):
        p0 = pts[(i - 1) % n] if (closed or i > 0) else pts[0]
        p1 = pts[i % n]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (closed or i + 2 < n) else pts[n - 1]
        steps = samples_per_segment
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2
                                    + (-a + 3 * b - 3 * c + d) * t3)
                             for a, b, c, d in zip(p0, p1, p2, p3)))
    if not closed:
        out.append(pts[-1])
    return out


def tube_mesh(name, points, radius, collection, material=None, sides=8, samples_per_segment=6,
              closed=False, caps=True, smooth=True, parent=None, location=(0, 0, 0), rotation=(0, 0, 0)):
    """Mesh tube swept along a smooth Catmull-Rom spline through ``points`` (cheaper and
    more controllable than a curve object; no depsgraph needed). ``points`` may carry a 4th value
    that multiplies the radius (taper). Uses parallel-transport frames, so no twisting."""
    path = catmull_rom(points, samples_per_segment, closed)
    cs =[Vector(p[:3]) for p in path]
    ws = [p[3] for p in path]
    m = len(cs)
    tangents = []
    for i in range(m):
        a = cs[(i - 1) % m] if (closed or i > 0) else cs[i]
        b = cs[(i + 1) % m] if (closed or i < m - 1) else cs[i]
        t = b - a
        tangents.append(t.normalized() if t.length > 1e-9 else Vector((0, 0, 1)))
    # parallel transport
    ref = Vector((0, 0, 1)) if abs(tangents[0].z) < 0.9 else Vector((1, 0, 0))
    nrm = tangents[0].cross(ref).normalized()
    frames = []
    for i in range(m):
        if i > 0:
            axis = tangents[i - 1].cross(tangents[i])
            if axis.length > 1e-9:
                ang = tangents[i - 1].angle(tangents[i])
                nrm = Quaternion(axis.normalized(), ang) @ nrm
        bin_ = tangents[i].cross(nrm).normalized()
        frames.append((nrm.copy(), bin_))
    verts, faces = [], []
    for i in range(m):
        n_, b_ = frames[i]
        r = radius * ws[i]
        for k in range(sides):
            a = 2 * math.pi * k / sides
            verts.append(tuple(cs[i] + (n_ * math.cos(a) + b_ * math.sin(a)) * r))
    rings = m if closed else m - 1
    for i in range(rings):
        i2 = (i + 1) % m
        for k in range(sides):
            k2 = (k + 1) % sides
            faces.append((i * sides + k, i * sides + k2, i2 * sides + k2, i2 * sides + k))
    if caps and not closed:
        faces.append(tuple(reversed(range(0, sides))))
        faces.append(tuple(range((m - 1) * sides, m * sides)))
    ob = mesh_from_pydata(name, verts, faces, collection, materials=material,
                          smooth=math.radians(60) if smooth else False,
                          parent=parent, location=location, rotation=rotation)
    return ob


def curve_tube(name, points, radius, collection, material=None, resolution=4, bevel_resolution=2,
               smooth=True, closed=False, caps=True, parent=None, location=(0, 0, 0), rotation=(0, 0, 0)):
    """Curve object with a round bevel (ropes, cords, roots, chain guide paths).

    points: (x, y, z) or (x, y, z, radius_factor). smooth=True makes an auto-handle Bezier through
    the points, False a poly line. radius=0 gives a bare guide curve (no geometry).
    resolution is the curve's U resolution per segment."""
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.resolution_u = resolution
    cu.render_resolution_u = resolution
    cu.bevel_depth = radius
    cu.bevel_resolution = bevel_resolution
    cu.use_fill_caps = caps
    pts = [tuple(p) + (1.0,) if len(p) == 3 else tuple(p) for p in points]
    if smooth:
        sp = cu.splines.new('BEZIER')
        sp.bezier_points.add(len(pts) - 1)
        for bp, p in zip(sp.bezier_points, pts):
            bp.co = p[:3]
            bp.handle_left_type = bp.handle_right_type = 'AUTO'
            bp.radius = p[3]
    else:
        sp = cu.splines.new('POLY')
        sp.points.add(len(pts) - 1)
        for pt, p in zip(sp.points, pts):
            pt.co = (p[0], p[1], p[2], 1.0)
            pt.radius = p[3]
    sp.use_cyclic_u = closed
    if material is not None:
        cu.materials.append(_resolve_material(material))
    ob = bpy.data.objects.new(name, cu)
    return _place(ob, collection, location, rotation, (1, 1, 1), parent, None)


# ---------------------------------------------------------------- bmesh primitives

def bm_transform(bm, matrix, verts=None):
    """Transform ``verts`` (default: all) of ``bm`` by a 4x4 matrix."""
    bmesh.ops.transform(bm, matrix=Matrix(matrix), verts=list(bm.verts) if verts is None else verts)


def bm_box(bm, size=(1, 1, 1), center=(0, 0, 0), matrix=None):
    """Add an axis-aligned box (size in meters) to ``bm``; optional extra 4x4 ``matrix``. Returns its verts."""
    if isinstance(size, (int, float)):
        size = (size, size, size)
    res = bmesh.ops.create_cube(bm, size=1.0)
    vs = res["verts"]
    m = Matrix.Translation(Vector(center)) @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))
    if matrix is not None:
        m = Matrix(matrix) @ m
    bm_transform(bm, m, vs)
    return vs


def bm_cylinder(bm, radius=0.5, depth=1.0, segments=16, center=(0, 0, 0), cap=True, radius_top=None, matrix=None):
    """Add a Z-aligned cylinder/cone centred at ``center``. Returns its verts."""
    r2 = radius if radius_top is None else radius_top
    res = bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segments,
                                radius1=radius, radius2=r2, depth=depth)
    vs = res["verts"]
    m = Matrix.Translation(Vector(center))
    if matrix is not None:
        m = Matrix(matrix) @ m
    bm_transform(bm, m, vs)
    return vs


def bm_lathe(bm, profile, segments=24, cap_start=True, cap_end=True, matrix=None, angle=2 * math.pi):
    """Revolve a profile [(radius, z), ...] (bottom to top) around Z. Points with radius 0 become
    poles. Open ends are capped with n-gons if requested. Faces point outward. Returns the verts."""
    full = abs(angle - 2 * math.pi) < 1e-6
    cols = segments if full else segments + 1
    rings, made = [], []
    for r, z in profile:
        if r <= 1e-7:
            v = bm.verts.new((0.0, 0.0, z))
            rings.append([v])
            made.append(v)
            continue
        ring = []
        for j in range(cols):
            a = angle * j / segments
            v = bm.verts.new((r * math.cos(a), r * math.sin(a), z))
            ring.append(v)
            made.append(v)
        rings.append(ring)
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(segments):
            j2 = (j + 1) % cols
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                bm.faces.new((a[0], b[j2], b[j]))
            elif len(b) == 1:
                bm.faces.new((a[j], a[j2], b[0]))
            else:
                bm.faces.new((a[j], a[j2], b[j2], b[j]))
    if full:
        if cap_start and len(rings[0]) > 1:
            bm.faces.new(list(reversed(rings[0])))
        if cap_end and len(rings[-1]) > 1:
            bm.faces.new(rings[-1])
    if matrix is not None:
        bm_transform(bm, matrix, made)
    return made


# ---------------------------------------------------------------- text

def load_font(path=FONT_KAITI):
    """Load (once) and return a font datablock. Falls back to YaHei, then Blender's built-in font."""
    for p in (path, FONT_YAHEI):
        if p and os.path.exists(p):
            # abspath: on the Linux render box 'C:/...' is relative to cwd '/', which Blender's loader rejects.
            return bpy.data.fonts.load(os.path.abspath(p), check_existing=True)
    return bpy.data.fonts.get("Bfont Regular") or None


def text(name, body, collection, size=1.0, font_path=FONT_KAITI, extrude=0.0, bevel_depth=0.0,
         align_x='CENTER', align_y='CENTER', material=None, vertical=False, spacing=1.0,
         location=(0, 0, 0), rotation=(math.pi / 2, 0, 0), parent=None):
    """Text object. Default rotation stands it up in the XZ plane, readable from -Y (the front).
    vertical=True stacks characters top to bottom (traditional plaques/steles)."""
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = "\n".join(body) if vertical else body
    f = load_font(font_path)
    if f is not None:
        cu.font = f
    cu.size = size
    cu.extrude = extrude
    cu.bevel_depth = bevel_depth
    cu.align_x = align_x
    cu.align_y = align_y
    cu.space_character = spacing
    if vertical:
        cu.space_line = spacing
    if material is not None:
        cu.materials.append(_resolve_material(material))
    ob = bpy.data.objects.new(name, cu)
    return _place(ob, collection, location, rotation, (1, 1, 1), parent, None)


# ---------------------------------------------------------------- stats

def _collect_targets(target):
    if target is None:
        return None
    if isinstance(target, bpy.types.Collection):
        objs = set(target.all_objects)
    elif isinstance(target, bpy.types.Object):
        objs = {target}
        stack = list(target.children)
        while stack:
            o = stack.pop()
            objs.add(o)
            stack.extend(o.children)
    else:
        objs = set()
        for t in target:
            objs |= _collect_targets(t)
    return objs


def evaluated_triangle_count(target=None, depsgraph=None):
    """Triangles after modifiers and instancing. ``target``: None (whole scene), a Collection
    (recursive, including what its instancers instance), an Object (with descendants), or an
    iterable of those. Counts each instance separately, as the renderer does."""
    targets = _collect_targets(target)
    names = None if targets is None else {o.name for o in targets}
    dg = depsgraph or bpy.context.evaluated_depsgraph_get()
    cache = {}
    total = 0
    for inst in dg.object_instances:
        ob = inst.object
        if names is not None:
            owner = inst.parent if inst.is_instance else ob
            owner_name = owner.original.name if owner is not None else ob.original.name
            if owner_name not in names and ob.original.name not in names:
                continue
        if ob.type not in {'MESH', 'CURVE', 'FONT', 'SURFACE', 'META'}:
            continue
        key = (ob.type, ob.data.name if ob.data else ob.name, ob.name)
        key = key if ob.type != 'MESH' else ('MESH', ob.data.as_pointer())
        tris = cache.get(key)
        if tris is None:
            if ob.type == 'MESH':
                me = ob.data
            else:
                try:
                    me = ob.to_mesh()
                except RuntimeError:
                    me = None
            if me is None:
                tris = 0
            else:
                n = len(me.polygons)
                if n:
                    lt = [0] * n
                    me.polygons.foreach_get("loop_total", lt)
                    tris = sum(lt) - 2 * n
                else:
                    tris = 0
                if ob.type != 'MESH':
                    ob.to_mesh_clear()
            cache[key] = tris
        total += tris
    return total
