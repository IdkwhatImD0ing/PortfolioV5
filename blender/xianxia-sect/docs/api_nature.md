# sect.lib.nature

Pines, blossom trees, willows, bamboo, shrubs, grass, rocks, karst pillars, floating rocks,
ground, ponds, waterfalls, lotus, cloud puffs and banks, and a geometry-nodes scatter helper.
Blender 5.2.2, EEVEE. Deterministic (seeded) and idempotent: the same call gives the same
geometry, and a rebuild after `look.reset_scene()` gives identical names, triangle counts and
vertex positions (tested: two showcase builds in one session hash the same).

```python
from sect.lib import nature as N

N.pine(coll, height=9, seed=3, location=(4, 2, 0), name="summit.pine", parent=root)
N.rock_pillar(coll, height=200, top_radius=46, bottom_radius=38, seed=7, top_z=-0.4)
```

## Conventions

- Every builder takes `collection` first. Common keywords: `seed`, `name` (object-name prefix,
  e.g. `"mirror.willow"`, made unique), `location`, `rotation` (a Z angle in radians **or** an
  XYZ Euler tuple; omitted = seeded random yaw for trees and rocks), `parent` (placement is in
  the parent's local space).
- Objects sit on z = 0 at their origin. Front faces -Y where it matters (cliff pines grow toward
  -Y, waterfalls pour toward -Y, ledges overhang toward -Y).
- Every builder returns the root object it made: a collection-instance Empty (trees), a mesh
  object (rocks, pillars) or an Empty with children (pond, waterfall, lotus, bamboo, cloud bank).
- Repeated things are prototypes, built once per session in excluded `_protos/nature.proto.*`
  collections, then placed as collection instances, linked duplicates or GN instances. Calling
  `pine()` 200 times builds at most 6 meshes.
- Triangle counts below are measured with `util.evaluated_triangle_count` (instances counted
  per instance, as the renderer does).

## Trees and plants

| Function | What it builds | Tris (measured) |
|---|---|---|
| `pine(collection, height=9, seed=0, style="huangshan", lod="hero", name, location, rotation, parent, spread=None)` | Huangshan pine: curving leaning trunk with root flare and buttress roots, 3-4 tiers of long near-horizontal limbs (favouring the lean side, one long "welcoming" arm), each carrying a broad flat cloud-like foliage plate with a needle-tuft fringe, flat umbrella crown. Plates use envelope normals, so each tier shades as one soft cloud. `style`: `"huangshan"` (6 variants), `"cliff"` (4: grows out of a wall toward -Y, then up; put its origin on a cliff face and yaw it with `rotation`), `"ancient"` (3: thick, strongly leaning, long arm, a bare snag; the summit pine). `seed % variants` picks the variant. `spread` scales the crown in XY (default seeded 0.92-1.08). | hero 23k (ancient 30k, cliff 16k), `lod="mid"` 2.4k, `lod="far"` 0.7k |
| `blossom_tree(collection, height=6, seed=0, kind="peach", lod="hero", ...)` | `"peach"`: short trunk, 3-4 spreading limbs, a full pink cloud crown (clusters along twigs + a shell over the crown). `"plum"`: dark angular zig-zag branches studded with discrete five-petal white/pink flowers (ink-painting plum). 4 variants each. | peach 11.6k (far 3.8k), plum 15k |
| `willow(collection, height=8, seed=0, lod="hero", ...)` | Weeping willow: short thick leaning trunk, arching limbs, a soft dome, ~480 combed strands hugging the dome and ~500 skirt strands falling to 0.6-3 m above the ground. 4 variants. | hero 31k, far 2.8k |
| `bamboo_clump(collection, count=12, height=8, seed=0, radius=None, ...)` | `count` culms (6 culm prototypes, waxy `bamboo_stalk` culm with node rings, side branches with drooping leaf fans) leaning outward, plus young short culms filling the base. Root Empty. | 37k for 12 (about 2.2k per culm) |
| `shrub(collection, size=1.6, seed=0, kind="green", ...)` | Rounded garden shrub (width `size`, height ~0.65 x size). `kind="azalea"` flowers pink-red. 6 variants each. | 480 |
| `grass_tuft(collection, size=0.5, seed=0, ...)` | Tuft of 28-36 curved blades (UV gradient root to tip). 4 variants. | 130 |
| `plant_prototypes(kind="ledge")` | Prototype collections for `scatter_on`: `"ledge"` (low-poly shrubs + grass), `"grass"`, `"garden"` (green + azalea shrubs + grass), `"forest"` (far pines + low shrubs, for pillar tops), `"pines"` (hero huangshan pines). | |

LOD guide for trees: `hero` within ~60 m of the camera path, `mid` 60-250 m, `far` beyond (and for
forests on backdrop pillar tops).

## Rocks, pillars, ground

| Function | What it builds | Tris |
|---|---|---|
| `rock(collection, size=1.5, seed=0, kind="boulder", ..., material=None)` | `"boulder"`: faceted weathered boulder, `size` = width, ~0.6 x size tall, 8 shared meshes (linked duplicates). `"scholar"`: taihu scholar stone, `size` = **height**: sinuous, pierced by smooth-lipped through-holes and hollows (metaball body, Boolean tunnels, voxel remesh, smoothing, ridged wrinkles), 6 shared variants. `"ledge"`: layered sandstone outcrop, `size` = width, 0.45-0.6 x size tall, 3-5 slabs with their own outlines, cracks, upper slabs overhang toward -Y; unique per seed; sets `obj["lip"]` (local x, y, z of the top slab's front lip; place a waterfall there) and `obj["top_z"]`. `material` overrides per object. | boulder 320, scholar 8.7k, ledge 2k |
| `rock_pillar(collection, height=120, top_radius=20, bottom_radius=None, seed=0, top_flat=True, top_z=0, lod="hero", pines=True, vegetation=True, ..., segments=None)` | Zhangjiajie sandstone pillar from `top_z` down to `top_z - height`. Radius field: taper, buttress lobes, 5-9 deep major fissures splitting it into columns, fine vertical fluting (hero), blocky strata where hard beds stick out as flat shelves, rounded bed shoulders and undercuts. Material `rock_cliff` (moss on ledges from its normal mask). `top_flat=True`: flat cap at `top_z` whose radius never drops below `top_radius - 2.5` (the area sits on it); `False`: vegetated soil dome with a far-pine forest. `vegetation=True`: GN-scattered low shrubs and grass on ledges and on the outer 3 m rim of a flat top only (face attribute `nature_veg`). `pines=True` (hero): 2-4 cliff pines on the upper walls. Sets `obj["nature_top_z"]`, `obj["nature_top_radius"]`. Returns the rock mesh; plants and pines are its children. | 46 m x 200 m hero: 91k rock + 47k plants (1.4-1.8 s). 8 m x 40 m hero dome: 68k. Far 30 m x 260 m: 17k bare, 36k with dome forest (0.2-0.3 s) |
| `floating_rock(collection, size=12, seed=0, depth=None, vegetation=True, roots=True, pine_on_top=None, ...)` | Flat grassy top at z = 0 (radius ~size/2) over an inverted craggy cone (depth 0.9-1.2 x size) with grooves, strata steps, stalactite spurs, hanging roots, shrubs and grass on top, a pine if size >= 8. | 31k (size 12) |
| `ground_patch(collection, radius=20, seed=0, height=0.5, holes=(), material="grass", edge_drop=0.6, ...)` | Gently undulating lawn disc at z ~ 0 with a soil rim dropping `edge_drop` m; `holes=[(x, y, r, depth)]` digs smooth basins for ponds; steep faces get `soil`. | 7.7k (r 20) |

### world.py usage

```python
# plateau under every area (anchor = area origin, which is z = 0 local; the area paves from z = 0)
N.rock_pillar(coll, height=anchor_z + 120, top_radius=footprint + 6, bottom_radius=(footprint + 6) * 0.85,
              seed=U.seed_from(key), top_z=-0.4, location=anchor, name="world.pillar." + key)
# backdrop karst forest (100+): unique cheap meshes, dome tops carry pine forests
N.rock_pillar(coll, height=h, top_radius=r, seed=i, top_flat=(i % 3 == 0), top_z=z, lod="far",
              location=(x, y, 0), name="world.backdrop")
```

Budget: 11 hero plateaus ~1.5M tris; 100 far pillars 1.7-3.6M (pass `vegetation=False` for the
farthest ones: 17k each). The hero lower wall (below max(25 m, 1.2 x radius) from the top) is
built coarser because the cloud sea hides it.

## Water

| Function | What it builds | Tris |
|---|---|---|
| `pond(collection, radius=6, seed=0, points=None, depth=1.2, water_level=-0.18, rim_stones=True, reeds=True, ...)` | Organic outline (or `points=[(x, y), ...]` counter-clockwise), still water surface at `water_level` (material `nature_pond_water`: `water_pond` with a slightly lighter deep colour so it is not a black hole from above), soil basin to `-depth`, a ring of half-sunk rim stones of varied size (linked duplicates, `nature_rim_stone`), reed tufts. Leave the hole open in your paving/ground (`ground_patch(holes=...)`). Root has `["outline"]`, `["water_level"]`. | 24k (r 6, about 60 stones) |
| `waterfall(collection, height=20, width=4, seed=0, sheets=3, mist=True, foam=True, ...)` | Origin = centre of the lip; water slides over the lip, leaves toward -Y on a ballistic arc and falls `height` m. 3 layered transparent sheets (`nature_waterfall`: foam streaks flowing down, driven by `frame`, speed 0.22 m/frame x `obj["flow"]`, each sheet a different speed), a churning foam disc and splash lumps (`nature_foam`, `nature_splash`, frame-driven), a mist volume (`mist_volume`, `obj["density"]=2.2`). Root `["foot"]` = local landing point. | 3k |
| `lotus_patch(collection, radius=3, count=24, seed=0, flowers=None, buds=None, ...)` | Place the root at water level. `count` round lotus leaves (70 % floating with wavy upturned rims, 30 % cupped on stems), `flowers` (default count/5) open lotus with 3 petal rings and a seed pod on stems, `buds` (count/7). All shared meshes / prototype instances. | 10k (24) |

## Clouds

| Function | What it builds |
|---|---|
| `cloud_puff(collection, size=20, seed=0, density=1.0, flatten=0.62, ...)` | Volumetric cumulus for EEVEE: an icosphere domain (`size` wide, `flatten` x as tall, 80 tris) with `nature_cloud_puff`: ellipsoid falloff of the domain box, pushed by billowy noise and round voronoi lobes (cauliflower top), flatter base, soft rim; different per object (Object Info Random). `obj["density"] = density * 14 / size`, so any size has a dense core. Best at 20 m and up, or seen from more than 60 m (smaller, nearer puffs blur into soft balls at EEVEE's preview volume resolution). |
| `cloud_bank(collection, size=120, seed=0, density=1.0, depth=None, puffs=None, ...)` | A wide flat bank: `puffs` (size/10, 6-30) overlapping flattened puffs along X, biggest in the middle, over a thin base layer. Root Empty. |

## scatter_on (geometry nodes)

`scatter_on(surface_obj, prototypes, density=0.5, seed=0, max_slope=radians(30), scale_range=(0.8, 1.2), collection=None, name=None, align=0.0, mask_attribute=None, z_range=None, min_distance=0.0)`

Creates an object (child of `surface_obj`, identity transform, so it follows the surface) with a
`NatureScatter` Geometry Nodes modifier using the shared group `nature.scatter.random` (or
`.poisson` when `min_distance > 0`): Object Info (Relative) → Distribute Points on Faces →
Instance on Points (Collection Info, Separate + Reset Children, random Pick Instance) with a
random Z spin, optional alignment to the face normal (`align` 0..1, Align Rotation to Vector),
random uniform scale. Faces are kept where normal.z ≥ cos(`max_slope`), z (surface local) is in
`z_range`, and the float attribute `mask_attribute` is > 0.5 (ignored if the mesh lacks it).
`prototypes` = Objects and/or Collections (e.g. `plant_prototypes("garden")`); they are linked
into a set collection under `_protos`. Instances stay instances. Density is per m² in the
surface's world scale.

```python
lawn = N.ground_patch(coll, radius=20, seed=1, name="mirror.lawn", parent=root)
N.scatter_on(lawn, N.plant_prototypes("garden"), density=0.08, seed=4, max_slope=math.radians(25))
```

Blender 5.2 API facts used here: node idnames `GeometryNodeDistributePointsOnFaces`
(`distribute_method` RANDOM/POISSON), `GeometryNodeInstanceOnPoints`, `GeometryNodeCollectionInfo`,
`FunctionNodeAlignRotationToVector`, `FunctionNodeEulerToRotation`, `FunctionNodeRandomValue`;
interface sockets via `node_group.interface.new_socket(...)`. **Modifier inputs are no longer
ID properties in 5.x**: set them with `mod.properties.inputs.<Socket_N>.value = ...`
(`mod["Socket_N"] = ...` raises "id properties not supported"). `nature._set_mod_input` wraps this.

## Materials registered (all `nature_*`, via `materials.register` / `variant`)

`nature_pine_pad`, `nature_pine_pad_far` (needle mass: noise clumps, fibrous needle streaks, warm
sunlit tops, dark undersides), `nature_blossom_peach`, `nature_blossom_plum`, `nature_flower_plum`
(UV five-petal flowers), `nature_willow`, `nature_shrub`, `nature_shrub_azalea`, `nature_bamboo_leaf`,
`nature_grass_blade`, `nature_lotus_stem` (UV leaf cards: v base→tip, midrib), `nature_lotus_pod`,
`nature_bark_pine`, `nature_bark_blossom` (greyer, darker barks), `nature_rock_small` (rock_cliff at
boulder scale), `nature_taihu`, `nature_rim_stone`, `nature_pond_water`, `nature_soil_moss`,
`nature_cloud_puff`, `nature_waterfall`, `nature_foam`, `nature_splash`.

Per-object controls: `obj["density"]` (cloud puffs, mist), `obj["flow"]` (waterfall sheet speed
multiplier), `obj["glow"]` (waterfall foam emission).

## Important: EEVEE volumes and the look.py haze

With `look.add_haze()` present (a 14 km box), EEVEE's single volume grid must cover the whole
0.5-4000 m range, and small or near object volumes **disappear**: a 12 m cloud puff 30 m from the
camera and the waterfall mist are invisible, and a 40 m puff at 120 m renders at about half
strength. Without the haze box, or with `volumetric_end` around 300 m, they render (see
`out/previews/nature/nature_nohaze_*.png` vs `nature_*.png`). Changing the material's
`volume_intersection_method` does not help. This is a look.py / world.py decision (for example
haze in the world shader or the compositor instead of a volume object, or a shorter range); the
nature volumes are correct.

## Previews

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/lib/look.py -- --target sect.lib.nature:showcase --out E:/Github/PortfolioV5/blender/xianxia-sect/out/previews/nature --name nature --footprint 40
```

Cameras on `showcase`: `hero`, `front`, `pond`, `pillar`, `aerial`. Other targets:
`sect.lib.nature:board_trees` (cams `front`, `close`), `board_rocks` (`wide`, `rocks`),
`board_clouds` (`front`; add `--no-haze`). Showcase: about 239 objects, 420k tris, 5.5 s build.
