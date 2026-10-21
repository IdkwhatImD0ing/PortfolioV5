# sect.lib.arch

Chinese architecture primitives: roofs, columns, dougong brackets, beams, lattice, platforms,
stairs, balustrades, and composite buildings (hall, pagoda, pavilion, paifang, corridor, wall,
moon gate, bell/drum tower). Tested in Blender 5.2.2. Previews: `out/previews/arch/`.

```python
from sect.lib import arch as A
root = A.hall("mission.hall", coll, bays_w=5, bays_d=3, double_eave=True)
anchor = bpy.data.objects[root["plaque_anchor"]]       # hang the plaque here
```

Preview:

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/lib/look.py -- --target sect.lib.arch:showcase --out E:/Github/PortfolioV5/blender/xianxia-sect/out/previews/arch --name arch --footprint 45
```

## Conventions

- Every builder takes `(name, collection, ...)` and returns a **root Empty** named `name`
  (or `name.001` if taken). Children are named `<root name>.<part>`, parented to the root.
- Front faces **-Y**. Origin on the ground (z = 0) at the centre, unless noted.
  Most builders also take `parent=`, `location=` and `rotation_z=` (radians).
- Deterministic and safe to call many times in one scene. Two builds after
  `look.reset_scene()` give identical names and transforms (checked: 1,341 objects, all equal).
- Facts about the build are stored as custom properties on the root, e.g. `root["arch_height"]`.
- Repeated parts are prototypes in excluded `_protos/arch.p.*` collections, placed either by
  collection-instance Empties or by one geometry-nodes **scatter** object per kind (see
  `scatter`). Prototypes are cached by parameters, so a second hall reuses the first one's.

## Roofs

### `roof(name, collection, width, depth=None, kind="xieshan", **options) -> root`

A complete roof over a `width` x `depth` **column footprint** (the eave overhang is added).
For `pyramid` and `round`, `width` is the diameter of the column circle.

**Local z = 0 is the rafter underside at the column line.** Put the root on top of the
bracket band; the eaves droop below 0 and the corners sweep up.

| kind | what |
|---|---|
| `xieshan` | Hip-and-gable, the formal hall roof. Red gable with a gold medallion, studded bargeboards, rake ridges, boji. |
| `wudian` | Hip roof. |
| `xuanshan` | Gable with overhanging ends (bargeboards). |
| `yingshan` | Flush gable. |
| `pyramid` | `sides` >= 3 (4 = square). Hips meet at a gold finial. |
| `round` | Conical, with tile courses converging to a finial. |
| `skirt` | Lower eave of a double roof: a ring from the eave up to `top_inset` inside the column line. `sides` 4 = rectangle, >= 5 polygon, 0 = round. Has a ridge along its top edge. |

The rectangular kinds need `width >= depth`. For a deep building, rotate the root.

What every roof has:

- Concave slopes: steep at the ridge, flat at the eave.
- Corner sweep (qiao jiao): the eave corners lift and push outward smoothly.
- Real corrugated tile courses: round tube tiles over concave pan tiles. Tile laps and lip
  shadows come from UV bump on `tile_material(tile_mat)`.
- Round end caps, pointed drip tiles and painted rafter-end plates along every eave.
- Red fascia, and a ribbed underside with teal rafters on red boards.
- Main ridge with chiwen at both ends. Hip ridges with an upturned tip, a gold-riding immortal,
  a row of beasts and a larger beast head behind them.

Options:

| option | default | meaning |
|---|---|---|
| `rise` | 0.62 x half-span (pyramid/round 0.95, skirt 0.48 x depth) | eave-to-ridge height |
| `overhang` | 0.85 + 0.23 x half-depth, clamped 0.9-3.6 m | eave beyond the columns |
| `curve` | 0.5 | how concave the slopes are, 0-1 |
| `corner_lift`, `corner_push`, `sweep` | 0.55 x overhang, 0.32 x overhang, 1.35 x overhang + 0.12 x half-span | corner sweep: height, outward push, length along the eave (hipped kinds only) |
| `tile_mat` | `"roof_tile_teal"` | any materials.py tile name (`roof_tile_black`, `roof_tile_moon`) |
| `tile_pitch` | 0.24-0.44 m by size | tube-tile spacing |
| `ridge_h` | 0.075 x half-span + 0.12 | main ridge height; chiwen are about 2 x this |
| `beasts` | odd number by size, 1-9 | beasts per hip |
| `ornaments` | `"full"` | `full` (chiwen), `simple` (curled ridge ends), `none` |
| `gable_parts` | `"full"` | gable and xieshan kinds: `full`, `board` (bargeboards only), `none` |
| `detail` | `"high"` | `low` costs about half: 4 samples per course, coarser rows, no drip tiles, plain teal underside |
| `gable_inset`, `top_inset`, `side_overhang`, `sides`, `thickness`, `finial` | | see the docstring |

Root props: `arch_ridge_z`, `arch_top_z` (including ornaments), `arch_eave_z` (eave underside at
mid-edge), `arch_corner_z`, `arch_eave_w`, `arch_eave_d`, `arch_overhang`, `arch_kind`.

Cost: a 20 x 12 xieshan is about 81k triangles; an 8 m pyramid about 34k.

```python
A.roof("t.roof", coll, 25, 15, "xieshan", location=(0, 0, 9.2))
```

### `roof_shape(width, depth, kind, ...) -> RoofShape`

The same maths with no objects, for planning heights. `sh.ov`, `sh.z_top(d)` (tile height at
distance d in from the eave), `sh.cut`, `sh.pt(panel, a, d)`.

### `double_eave_roofs(name, collection, width, depth, kind="xieshan", gap=None, skirt_inset=None, ...) -> (root, skirt, upper)`

Stacks a skirt roof and an upper roof. The upper roof sits at z = `gap` on an inset footprint.
You build what goes between them. hall(), pavilion() and tower() do this for you.

### `tile_material(base="roof_tile_teal") -> Material`

Returns `arch_tiles_<base>`: the shared tile material plus UV-driven laps. Only meaningful on
arch roof meshes, whose UVs are (tile course, lap).

## Structure

| function | builds | size / cost |
|---|---|---|
| `column(name, coll, height=6, radius=0.32, mat="lacquer_red", base_mat="marble_white")` | Square marble plinth with a drum (guzheng) base, slightly tapered lacquer shaft, gold foot ring. Returns a collection instance. | 532 tris |
| `bracket_band(name, coll, width, depth=None, sides=4, height=None, bays=None, grid=None, spacing=None, architrave=True)` | Dougong band sitting on the column tops (z = 0 = column top). Painted double architrave with a red frieze below z = 0, a plate, a set over each column, diagonal corner sets, intermediate sets at least 1.2 m apart, red panels and the top beams. `grid=(xs, ys)` aligns sets and per-bay beams to uneven column lines. | 15 x 9 m: 18k tris. Props: `arch_top_z` (roof seat height), `arch_projection` (how far the sets reach out), `arch_architrave_z` |
| `band_height_for(width)` | Suggested band height, 0.7-1.7 m. | |
| `beam(name, coll, p0, p1, width=0.4, height=0.6, mat="bracket_paint")` | Bevelled box beam from p0 to p1. | 44 tris |

```python
A.column("h.col", coll, 6.0, 0.31, location=(x, y, 1.5))
A.bracket_band("h.band", coll, 25, 13.5, grid=(xs, ys), location=(0, 0, 7.5))
```

## Lattice

`lattice_panel(name, coll, width, height, pattern="grid", kind="window", lit=False, seed=0, frame_mat="lacquer_red", paper=True)`

A door or window leaf in the XZ plane, facing -Y, origin at its bottom centre. The bars are
real geometry.

- `pattern`: `grid`, `diamond`, or `ice` (ice-crack, seeded).
- `kind`: `window`, or `door` (a lattice heart above a carved skirt board with a gold medallion).
- Gold corner plates. Paper backing uses `paper_screen`, or `paper_screen_lit` when `lit`.
- `paper=False` gives open fretwork, e.g. hanging fascias (gualuo).
- Returns a cached collection instance. About 350-600 tris.

## Platform, stairs, balustrade

| function | builds |
|---|---|
| `platform(name, coll, width, depth=None, height=1.5, style="xumizuo", sides=4, sink=0.6)` | Xumizuo terrace: plinth, bands, lotus mouldings, recessed waist with carved posts, `marble_paving` top. The top is at z = `height`. A footing runs `sink` m below ground so it never floats. `sides` >= 5 makes a polygon. `style="plain"` gives a simple base. Prop: `arch_top_z`. |
| `stairs(name, coll, width, height, run_per_step=0.33, ramp=True, balustrade=True, max_riser=0.17, bal_extend=0)` | Steps climb toward +Y to a landing at z = `height`. The origin is on the ground under the top edge, and they descend toward -Y. With `ramp`, a carved imperial ramp (yubu) sits between two flights. Side stringers, and sloped balustrades ending in drum stones. Props: `arch_run`, `arch_steps`, `arch_riser`. |
| `balustrade(name, coll, points, height=1.1, post_spacing=1.8, mat="marble_white", closed=False, end_drum=None, no_post=None, style="marble")` | Posts with carved caps and panels with vase supports and a round handrail, all instanced. `points` are 3D foot points. Sloped segments shear the panels, so posts stay vertical. `style="wood"` gives a light painted railing; use it with `mat="lacquer_red"`. |

```python
A.platform("h.plat", coll, 30, 19, 1.5)
A.stairs("h.st", coll, 6.4, 1.5, location=(0, -9.5, 0))
A.balustrade("h.bal", coll, [(-3, -9, 1.5), (-14.6, -9, 1.5), (-14.6, 9, 1.5)])
```

## Buildings (all face -Y)

| function | builds | measured |
|---|---|---|
| `hall(name, coll, bays_w=5, bays_d=3, bay=5, column_h=6, roof="xieshan", double_eave=False, platform_h=1.5, stairs=True, lit=False, roof_mat="roof_tile_teal", porch=True, lattice="diamond")` | Formal hall on a xumizuo terrace. The centre bay is wider. Front stairs get a ramp when the platform is >= 1.2 m. Red columns, painted band, lattice doors in the central bays and windows over sill walls elsewhere. Front porch one bay deep, red plaster side and back walls. Double eave adds an open colonnade, a skirt roof, a red frieze with small windows, inner columns and the upper roof. | 5x3 single: 15.7 m tall, roof 48% of the height, 180k tris. Double: 18.3 m, 249k tris |
| `pagoda(name, coll, tiers=7, sides=8, radius=9, tier_h=5.5, taper=0.065, lit_floors=(), roof_mat, platform_h=1.6, balcony=1.1)` | Xumizuo base with stairs. Each storey: corner columns, plaster walls with lattice (a door on the ground floor), a bracket band, and a skirt roof tucked under the next storey's balcony (wood deck, red railing). Top: pyramid roof and a tall gold spire. Storeys 0-1 are high detail, the rest low. | Default: 479k tris. radius 4.2 / tier_h 4.1: about 32 m tall |
| `pavilion(name, coll, sides=6, radius=3.2, height=3.4, roof="pyramid", double=False, roof_mat, platform_h=0.6, seats=True, hanging=True, lattice="ice")` | Open ting: polygonal platform with steps, columns, painted bracket ring, hanging lattice fascias, goose-neck benches on all faces but the front. `roof="round"` makes a conical roof; `double` adds a second eave. | 6-sided: 50k tris. Round double: 85k |
| `paifang(name, coll, bays=5, width=34, height=24, roofs=True, roof_mat, center_frac=None)` | Ceremonial gate: red columns on tall marble plinths with drum stones, painted double architraves, a plaque zone (left empty in the centre bay), carved boards and sparrow braces in the side bays, a bracket row and a hip roof per bay. The centre bay is tallest and the lower roofs tuck against it. | 34 x 24: centre opening 12.1 m wide x 15.4 m tall, 192k tris |
| `corridor(name, coll, points, width=3, height=3, bay=3.3, roof_mat="roof_tile_black", detail="low")` | Lang along a 2D polyline: stone floor, post pairs, painted beams, hanging lattice, bench rails, a gable roof per segment and a pyramid roof at each corner. | 20 m + 13 m: 89k tris |
| `wall(name, coll, points, height=4, thickness=0.7, cap_mat="roof_tile_black", closed=False)` | Stone dado, red plaster body, tiled coping (low-detail gable roof). | about 0.9k tris per m |
| `moon_gate(name, coll, radius=1.6, wall_width=7, height=None, thickness=0.7)` | Wall panel with a round opening, marble ring frame and threshold, dado, coping. You walk through it along Y. | 8.5k tris |
| `tower(name, coll, kind="bell", size=9, base_h=3.2, column_h=4)` | Tall xumizuo base with stairs and balustrade, an open 3x3-bay pavilion with fretwork, and a double-eave xieshan roof. Inside: a bronze bell (`bell`) or a red drum on a stand (`drum`). | about 113k tris |
| `showcase(collection)` | Preview courtyard: paifang, paved axis, double-eave hall, pagoda, hexagonal pavilion, corridor. Comes with `preview_cameras` (front_34, front, aerial, detail, pagoda). | 888k tris, builds in 2 s |

Root props on buildings:

- All buildings: `arch_height` (top including ornaments).
- `hall` and `paifang`:
  - `plaque_anchor`: the **name** of an Empty, a child of the root. Its -Y faces out (the
    hall's is tilted 6 deg forward). It sits centred under the (upper) eave on the hall, and in
    the plaque zone on the paifang.
  - `plaque_size` (w, h): the suggested plaque size.
- `hall` also has `arch_eave_z`, `arch_platform` (w, d) and `arch_columns` (W, D).
- `pagoda` has `arch_floors` (the z of each storey). `pavilion` and `tower` have `arch_floor_z`.
- `paifang` has `arch_center_opening` (w, h) and `arch_columns_x`.

```python
gate = A.paifang("gate.paifang", coll, bays=5, width=34, height=24, location=(0, 8, 0))
lib = A.pagoda("library.pagoda", coll, tiers=7, sides=8, radius=7, tier_h=5.5, lit_floors=(1, 3, 5))
A.pavilion("mirror.ting", coll, sides=6, radius=3.0, location=(10, 4, 0))
A.corridor("steles.lang", coll, [(-20, -30), (-20, 30)], width=3.2)
```

## Instancing helper

`scatter(name, collection, proto_collection, matrices, parent=None) -> object`

One mesh point per instance. The point attribute `arch_xf` (FLOAT4X4) holds the full matrix,
so shear and non-uniform scale work. A per-prototype geometry-nodes group does
Instance on Points, then Set Instance Transform. Matrices are in the parent's space.

Note: Blender 5.2 node modifiers have no IDProperty inputs (`mod["Socket_2"]` is gone), so
each prototype collection gets its own small node group, `arch.gn.<collection>`.

## Materials registered by arch

All come from `materials.register` or `variant`, so look them up by name with `materials.get`.

| name | what |
|---|---|
| `arch_tiles_<tile>` | Tile material plus UV laps, lip shadows and crease darkening (roof meshes only). |
| `arch_paint_red` | Matte vermilion paint: soffit boards, fascia, gables, frieze. |
| `arch_paint_teal` | Teal rafter paint. |
| `arch_plaster_red` | Matte red plaster walls. |
| `arch_paint_box` / `arch_paint_box_fine` | The dougong look of `bracket_paint` (blue-green fields, gold, dark and white edge lines) with 30 mm or 11 mm lines. It reads mesh attributes, so it **works on instances and on merged meshes**. |
| `arch_beam_paint` | Qing hexi beam painting: gold border, end bands, chevrons, pointed central panel; blue and green swap per beam. |

The `arch_paint_*` materials need the point attributes `arch_gen`, `arch_dims` and
`arch_rand` (described under "Bracket paint on instances" below). Create them with:

```python
bm = A.paint_layers(bmesh.new())          # before adding geometry
vs = U.bm_box(bm, (0.4, 0.2, 0.2))
A.tag_piece(bm, vs, rand=0.3)             # in the piece's own axis-aligned frame
U.mesh_from_bmesh("x.block", bm, coll, materials=["arch_paint_box"])
```

## Notes and gotchas

- **Bracket paint on instances.** The shared `bracket_paint` reads the object attribute
  `dimensions`. On every instanced copy (collection instance or geometry nodes) that reads 0, so
  the whole piece renders solid gold. arch works around it:
  - arch never instances `bracket_paint`.
  - It uses `arch_paint_box*` instead. These read three mesh attributes:
    - `arch_gen`: each vertex's 0-1 position inside its piece's box.
    - `arch_dims`: the box size.
    - `arch_rand`: picks the piece's field colour.
- Adding a BMesh layer invalidates the BMVert references you already hold. That is why
  `paint_layers` must run first.
- Close up, tile courses flatten within about 0.4 m of a hip line. The hip ridge covers this.
- The main ridge's buried part can poke below the underside at the apex. You only see it from
  inside an open xieshan hall, looking straight up.
- The pagoda derives each storey's wall height from `tier_h`. Below about 3.5 m the walls clamp
  to 2.4 m and the storeys get taller than `tier_h`.
- Triangle budget per area is 1.5M. A 7-storey radius-9 pagoda is 479k. Use `detail="low"` on
  background roofs.
