# sect.lib.util

Small, solid helpers every module uses. Deterministic, no external files, no depsgraph
needed except where noted. Tested in Blender 5.2.2 (`out/tmp/materials/util_test.py`, 17/17 checks).

```python
from sect.lib import util as U
```

Conventions:

- Meters, Z up, a builder's front faces -Y.
- Any function with `parent=` places the new object in the **parent's local space**
  (`location`/`rotation`/`scale`/`matrix` are local; `matrix_parent_inverse` is identity).
- `rotation` is an XYZ Euler in radians, or a `Quaternion` / `Matrix`.
- `materials=` / `material=` take `bpy.types.Material` objects or material **names**
  (resolved through `sect.lib.materials.get`).

## Constants

| Name | Value |
|---|---|
| `ROOT` | `E:/Github/PortfolioV5/blender/xianxia-sect` |
| `FONT_KAITI` / `FONT_YAHEI` | `C:/Windows/Fonts/simkai.ttf` / `msyh.ttc` |
| `PROTO_ROOT` | `"_protos"` (excluded collection holding all prototype collections) |
| `EDGE_ATTR` | `"edge"` (face attribute written by `bevel_mesh`, read by materials for edge wear) |

## Paths and names

| Function | What it does |
|---|---|
| `out_path(*parts, make_dirs=True)` | Absolute path under `ROOT/out/`, parent folder created. `U.out_path("previews", "arch", "a.png")` |
| `unique_name(base, pool=None)` | `base` if free in `pool` (default `bpy.data.objects`), else `base.001`, `base.002`... Deterministic: a rebuild after `look.reset_scene()` in the same session gets the same names. |
| `name(prefix, *parts, pool=None)` | Unique prefixed name. `U.name("gate", "column", 3)` -> `"gate.column.3"`; parts already starting with the prefix are not double-prefixed. |

## Collections

| Function | What it does |
|---|---|
| `get_collection(name, parent=None, scene=None)` | Get or create. `parent` = Collection, name, or None (scene master collection). Idempotent. |
| `link(obj, collection, exclusive=False)` | Link into a collection (or name); `exclusive` unlinks from others. Returns obj. |
| `unlink_all(obj)` | Remove from every collection. |
| `clear_collection(collection, recursive=True)` | Delete every object in it. |
| `delete_hierarchy(obj)` | Delete obj and all descendants; orphaned mesh/curve data removed. Use for idempotent rebuilds. |

## Objects and transforms

| Function | What it does |
|---|---|
| `trs(location, rotation, scale)` | 4x4 Matrix. `scale` may be a float. |
| `set_transform(obj, location, rotation, scale, matrix=None)` | Sets `matrix_basis`. |
| `world_matrix(obj)` | World matrix from the parent chain, **without** a depsgraph update (ignores constraints). |
| `parent(child, parent_obj, keep_transform=True)` | Parent; `keep_transform` keeps the world placement and rewrites the local matrix (parent inverse stays identity, so `child.location` is always parent-relative). |
| `empty(name, collection, location=(0,0,0), parent=None, display_size=1, display_type='PLAIN_AXES', rotation, scale, matrix)` | Empty, e.g. an area root `"<key>.root"`. |
| `align_z(direction, up=(0,0,1))` | 3x3 rotation whose +Z points along `direction` (for chains, beams, cords). |
| `set_visibility(obj, camera=True, shadow=True, diffuse, glossy, transmission, volume_scatter)` | Ray visibility, e.g. `shadow=False` for light beams. |

## Meshes

| Function | What it does |
|---|---|
| `mesh_from_pydata(name, verts, faces, collection, materials=None, smooth=False, edges=(), material_indices=None, uvs=None, location, rotation, scale, parent, matrix)` | Object from lists. `smooth`: False, True, or an angle in radians (auto smooth). `material_indices`: one slot per face. `uvs`: one (u, v) per face corner. |
| `mesh_from_bmesh(name, bm, collection, materials=None, smooth=None, free=True, ...)` | Object from a BMesh (freed by default). `smooth=None` keeps the BMesh face flags. |
| `object_from_mesh(name, mesh, collection, ...)` | New object around existing (shared) mesh data. |
| `shared_mesh(key, build)` | Mesh cache: returns the mesh tagged `key` or calls `build()` (returning Mesh or BMesh) once. Use for prototypes. |
| `set_materials(target, materials)` | Replace the slots of a mesh/curve (or an object's data). Keeps per-face material indices already on the mesh (Blender's `materials.clear()` resets them; util saves and restores them), so `mesh_from_bmesh` with `face.material_index` set and `mesh_from_pydata(material_indices=...)` both work. |
| `set_object_material(obj, material, slot=0)` | Object-level slot override, so linked duplicates share geometry but differ in material (banners of 8 colours from one mesh). |

### bmesh primitives (add into an existing BMesh)

| Function | What it does |
|---|---|
| `bm_box(bm, size=(1,1,1), center=(0,0,0), matrix=None)` | Axis-aligned box; size in meters (float ok). Returns verts. |
| `bm_cylinder(bm, radius=0.5, depth=1, segments=16, center=(0,0,0), cap=True, radius_top=None, matrix=None)` | Z-aligned cylinder / cone, centred on `center`. |
| `bm_lathe(bm, profile, segments=24, cap_start=True, cap_end=True, matrix=None, angle=2*pi)` | Revolve `[(radius, z), ...]` (bottom to top) around Z. Radius 0 makes a pole. Faces point outward. Columns, bases, lanterns, vases, finials, cauldrons. Run `bmesh.ops.remove_doubles` if the profile repeats points. |
| `bm_transform(bm, matrix, verts=None)` | Transform verts in place. |

Example (column with base):

```python
bm = bmesh.new()
U.bm_lathe(bm, [(0, 0), (0.42, 0), (0.42, 0.18), (0.32, 0.25), (0.30, 6.0), (0, 6.0)], segments=32)
col = U.mesh_from_bmesh(U.name("gate", "column"), bm, coll, materials=["lacquer_red"],
                        smooth=math.radians(35), parent=root)
U.bevel_mesh(col, 0.015, 2)
```

## Smoothing, bevels, modifiers

| Function | What it does |
|---|---|
| `auto_smooth(target, angle=radians(30))` | Blender 5.x auto smooth: every face smooth, then `Mesh.set_sharp_from_angle(angle)`. Object or Mesh. |
| `shade_flat(target)` | Flat shading. |
| `bevel(obj, width=0.02, segments=2, angle_limit=radians(30), harden_normals=True, profile=0.5, limit_method='ANGLE', clamp=True, apply=False)` | Adds/updates a Bevel **modifier** named "Bevel" (harden normals, faces set smooth). `apply=True` bakes it. |
| `bevel_mesh(target, width=0.02, segments=2, angle_limit=radians(30), mark="edge")` | Bevels the mesh **data** with bmesh (affects all users, ideal for prototypes), writes face attribute `edge` = 1 on bevel faces and sets hardened custom normals (flat faces flat, curved faces smooth by angle, bevels round). Materials use `edge` for edge wear (gold, bronze, lacquer_red_worn, iron...). |
| `apply_modifiers(obj)` | Bakes the modifier stack into new mesh data for this object only. Works on objects in excluded proto collections (temporarily links them). Needs a depsgraph evaluation, so do it once per prototype, not per instance. |

## Instancing (performance rule from spec section 2)

| Function | What it does |
|---|---|
| `instance(src_obj, name, collection, location, rotation, scale, parent=None, matrix=None)` | Linked duplicate (Alt+D): shares mesh data, copies modifiers and slot overrides. Apply modifiers on the prototype first so all copies share one evaluated mesh. |
| `proto_collection(name, scene=None)` | Collection under `_protos`, which is excluded from every view layer: its objects never render directly. Build prototypes at the origin. Idempotent. |
| `collection_instance(src_collection, name, collection, location, rotation, scale, parent=None, matrix=None, display_size=0.5)` | Empty instancing a collection (Collection or name). |

```python
proto = U.proto_collection("props.lantern_stone")
...build the lantern parts into proto at the origin...
for i, x in enumerate((-6, 6)):
    U.collection_instance(proto, U.name("gate", "lantern", i), coll, location=(x, -12, 0), parent=root)
```

## Randomness and noise (all deterministic)

| Function | What it does |
|---|---|
| `seed_from(*parts)` | Stable 31-bit int from any values (crc32; unlike `hash()`, identical across runs). |
| `rng(seed=0, *salt)` | `random.Random`. `U.rng(7)`, `U.rng("gate", "lanterns")`. |
| `noise3(p, scale=1, seed=0)` | Perlin in [-1, 1]; `scale` = frequency per meter; `seed` shifts the field. |
| `fbm(p, scale=1, octaves=4, lacunarity=2, gain=0.5, seed=0)` | Fractal noise, roughly [-1, 1]. |
| `noise_vec(p, scale=1, seed=0)` | Vector noise (each axis ~[-1, 1]), for displacing vertices. |
| `jitter(r, amount, axes=(1,1,1))` | Random offset Vector from a `random.Random`. |

## Curves and tubes

| Function | What it does |
|---|---|
| `catmull_rom(points, samples_per_segment=8, closed=False)` | Smooth resample through points; returns `(x, y, z, w)` tuples (w interpolated, e.g. radius). Use to place chain links along a sag. |
| `tube_mesh(name, points, radius, collection, material=None, sides=8, samples_per_segment=6, closed=False, caps=True, smooth=True, parent=None, location, rotation)` | Mesh tube along a Catmull-Rom spline with parallel-transport frames (no twist). Points may have a 4th value multiplying the radius (taper). Ropes, cords, tassel strings, roots. |
| `curve_tube(name, points, radius, collection, material=None, resolution=4, bevel_resolution=2, smooth=True, closed=False, caps=True, parent=None, location, rotation)` | Curve object with round bevel; Bezier with auto handles (`smooth=True`) or poly. `radius=0` gives a bare guide curve (e.g. a path for chains). |

```python
U.tube_mesh(U.name("mission", "cord", i), [(0, 0, 4), (0.05, 0, 3.2), (0, 0, 2.5, 0.6)], 0.012,
            coll, material="cloth_red", sides=6, parent=root)
```

## Text

| Function | What it does |
|---|---|
| `load_font(path=FONT_KAITI)` | Loads once (`check_existing`), falls back to YaHei then Blender's font. |
| `text(name, body, collection, size=1, font_path=FONT_KAITI, extrude=0, bevel_depth=0, align_x='CENTER', align_y='CENTER', material=None, vertical=False, spacing=1, location, rotation=(pi/2,0,0), parent=None)` | Text object standing in the XZ plane, readable from -Y. `vertical=True` stacks characters top to bottom (steles, vertical plaques). |

```python
U.text(U.name("gate", "plaque_text"), "明教", coll, size=1.4, extrude=0.03, material="gold",
       location=(0, -0.08, 0), parent=plaque)
```

## Stats

| Function | What it does |
|---|---|
| `evaluated_triangle_count(target=None, depsgraph=None)` | Triangles after modifiers and instancing, counting each instance like the renderer. `target`: None (scene), a Collection (recursive, including what its instancers instance), an Object (with descendants) or an iterable. Example: `U.evaluated_triangle_count(area_collection)` must stay under 1.5 M. |
