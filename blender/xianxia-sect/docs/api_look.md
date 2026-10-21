# `sect/lib/look.py` — look-dev, render settings, preview harness

Owner: look. Blender 5.2.2, EEVEE (`BLENDER_EEVEE`) only. Everything is deterministic and
safe to call repeatedly (objects, materials, world and compositor are reused by name).

## Preview CLI (use this to test any module)

One line (works from any folder; the script puts the project root on `sys.path`):

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/lib/look.py -- --target sect.lib.arch:showcase --out E:/Github/PortfolioV5/blender/xianxia-sect/out/previews/arch --name arch --footprint 40 [--cams front_34,aerial] [--res 1280x720] [--blend path.blend]
```

Use absolute `--out` paths or run from the project root (relative paths are resolved
against the current folder).

A scratch target outside the `sect` package (e.g. in your `out/tmp/<you>/` folder) works
by putting its folder on `sys.path` first; Blender runs `--python-expr` before `--python`:

```
blender.exe --background --factory-startup --python-expr "import sys; sys.path.insert(0, 'E:/Github/PortfolioV5/blender/xianxia-sect/out/tmp/<you>')" --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/lib/look.py -- --target my_test:build --out ...
```

| flag | meaning |
|---|---|
| `--target module:function` | function is called with the build collection. `sect.areas.forge` or `sect.areas.forge:build` uses the area's `AREA['footprint']`, names files `<key>_<cam>.png` and defaults `--out` to `out/previews/<key>` |
| `--cams` | `auto` (default) or a comma list of camera names (see below) |
| `--res WxH` | default `1280x720`; keep previews at or below this |
| `--samples N` | TAA samples (default 32 preview, 96 final) |
| `--quality preview\|final` | final = 96 samples, motion blur, finer volumetrics, jittered sun shadows |
| `--blend path` | also save the preview scene |
| `--no-haze`, `--no-comp` | drop the haze volume / compositor |
| `--look-json '{"sun_strength": 9}'` | override `LOOK` values for a tuning run |

Output: one PNG per camera and one stdout line to grep:

```
PREVIEW_STATS {"name": "arch", "objects": 44, "triangles": 9072, "build_s": 0.03,
  "render_s": {"front_34": 1.12, "front": 0.35, ...}, "bbox": [[...],[...]], "files": [...]}
```

`objects` and `triangles` cover everything the build created (instances included, via the
evaluated depsgraph), not the plinth, sun, haze or cameras. Errors print `PREVIEW_ERROR`
and exit with code 1. The first render of a run includes shader compilation (1–3 s).

Built-in test targets: `sect.lib.look:showcase` (look-dev hall) and
`sect.lib.look:haze_showcase` (distance boxes, cameras `wide_n`, `wide_sun`).

## Constants

Compass azimuth: degrees clockwise from north. 0 = +Y, 90 = +X, 180 = −Y, 270 = −X.

| name | value | notes |
|---|---|---|
| `SUN_AZIMUTH`, `SUN_ELEVATION` | 252°, 7° | west, 18° south of due west, so −Y façades get a raking 30 % of the sun |
| `SUN_DIR` | (−0.944, −0.307, 0.122) | unit vector from the scene toward the sun |
| `MOON_AZIMUTH`, `MOON_ELEVATION` | 22.5°, 16° | north-north-east |
| `MOON_DIR` | (0.368, 0.888, 0.276) | unit vector toward the moon centre |
| `MOON_ANGULAR_SIZE` / `_DEG` | 0.2443 rad / 14° | full apparent diameter |
| `VOLUMETRIC_END` | 4000 m | EEVEE volume range (custom range enabled) |
| `CAMERA_CLIP_END` | 9000 m | used by `camera_look_at` |
| `LOOK` | dict | every tuned value below; edit here, not in callers |
| `QUALITY` | `preview` / `final` presets | samples, ray-trace res, shadow rays/steps/pool, volume tile/samples, motion blur |

`dir_from_az_el(az_deg, el_deg) -> Vector` builds such vectors.
`moon_placement(distance, origin=(0,0,0)) -> (centre, radius)` places a moon disc that
looks exactly `MOON_ANGULAR_SIZE` wide. Example: `c, r = look.moon_placement(6000)`.

## Tuned look (final values in `LOOK`)

| group | values | why |
|---|---|---|
| colour | AgX, look `AgX - Punchy`, exposure +0.25 | rich donghua contrast without clipping |
| sky | Sky Texture `MULTIPLE_SCATTERING`, strength 0.18, air 2.0, aerosol 2.5, ozone 4.0, altitude 300 m | orange around the sun, blue-violet north sky, deep blue zenith |
| sky knee | 1.0 → +1.5 | hue-preserving soft clip so the sunset glow stays orange under AgX |
| sun disc | 0.9° wide, radiance 24, halo 1.2 | painted in the world shader (EEVEE does not draw the sky's own disc); blooms |
| sun lamp | 8 W/m², colour (1.0, 0.52, 0.23), angle 1.2°, volume factor 1.8 | about 10× the sky's horizontal irradiance, so shadows read; extra in-scatter makes golden air |
| haze | density 0.00045 /m at `base_z`, falloff 120 m, colour (1.0, 0.92, 0.84), anisotropy 0.2 | see distances below |
| bloom | Glare `Bloom`, threshold 2.0 (scene-linear **luminance**), smoothness 0.35, strength 0.6, size 0.55, clamp 60 | sun-facing white marble peaks at luminance 1.3–1.5 (red channel ~2.3), so only emissives, glints and the sun bloom |
| grade | ASC-CDL slope (1.02, 1.0, 0.975), offset (−0.0015, 0, 0.0025); saturation 1.10; highlight saturation 1.25; shadow 1.05 | warm highlights, cool shadows; gives back colour AgX bleaches |
| vignette | 22 % at the corners, smoothstep from radius 0.55 to 1.45 | gentle |

Measured linear values (scene linear, before exposure; white albedo 0.78): sun-facing wall
(2.29, 1.32, 0.82), ground in sun luminance 0.36, ground in shadow 0.22 (blue), north sky
at 15° 0.33, sky beside the sun after the knee (2.4, 1.2, 0.5). So sunlit ground is about
1.7× its shadow, and a sunlit wall is about 5× a wall in shade.

Haze at the preview camera height (z ≈ 14 m), computed from the density function:
50 m → 4 % veiled, 200 m → 9 %, 600 m → 21 %, 1500 m → 38 %. Above `base_z` the air
clears (density halves every ~83 m), so the upper sky stays blue.

Emissive guidance: the Glare threshold is on luminance (0.21 R + 0.72 G + 0.07 B), not on
the brightest channel, so saturated warm glows bloom far less than their strength suggests.
Measured with the shared materials (foundation check, `out/previews/foundation_check/`):
`paper_lantern` 1.7–2.6 (faint bloom), `lantern_red` 0.8 (no bloom; set `obj["glow"] = 3`
for a halo), `rune_cyan` 2.9, `jade_glow` with `obj["glow"] = 3` 3.5, `molten` 3.5. Raise a
glow with `obj["glow"]`, not by lowering the threshold. Never above 30 (spec).

## Functions

### `setup_render(scene, quality='preview', resolution=(1280, 720)) -> scene`
EEVEE with screen-space ray tracing (denoised), fast GI, virtual shadow maps, volumetrics
+ volumetric shadows over 0.5–4000 m (tile 8 preview / 4 final), AgX + look + exposure,
filter 1.5 px, 3 % overscan, PNG 8-bit, TAA 32 / 96, motion blur only for `final`.
Stores `scene["sect_look_quality"]`. Every property is set through a checked setter that
prints `LOOK WARN ...` if a name does not exist.
Example: `look.setup_render(bpy.context.scene, 'final', (1920, 1080))`.

### `setup_lookdev(scene, haze=True, compositor=True, quality=None, cloud_floor=True) -> dict`
Runs `setup_render` first if it never ran, then `setup_world`, `add_sun`, `add_haze`
(optional) and `setup_compositor` (optional). Objects go in collection `look`.
Returns `dict(world, sun, haze, compositor)`.
Example: `look.setup_lookdev(scene)`.

### `setup_world(scene, name='look.world', cloud_floor=True) -> World`
Sky Texture + painted sun disc/halo. Below the horizon: a procedural sea of cloud
(`cloud_floor=True`, previews; billows embossed toward the sun, fading to the horizon
colour) or a flat hazy colour (`cloud_floor=False`, for world.py, which builds the real
cloud sea). Disables EEVEE's world-sun extraction (`sun_threshold = 0`) because the sun
lamp does the direct light.

### `add_sun(scene, collection=None, name='look.sun', quality='preview') -> Object`
Sun lamp aligned with `SUN_DIR` (shadows on; jittered soft shadows in `final`).

### `add_haze(scene, collection=None, name='look.haze', density=None, base_z=None, falloff=None, extent=None, z_min=None, z_max=3500) -> Object`
A box volume (default ±7 km, z from `haze_floor_z` = −140 to 3500) with Volume Scatter
density `density * exp(-(z - base_z) / falloff)`, capped at 4× density. A world volume is
not used: EEVEE treats world volumes as infinite, which blacks out the sky.
Example for the final scene: `look.add_haze(scene, base_z=150, falloff=250, z_min=15)`
(tune by eye; keep density at mean area height near 0.00045).

### `setup_compositor(scene, name='look.compositor', quality='preview') -> NodeTree`
Builds a `CompositorNodeTree`, assigns it to `scene.compositing_node_group` (the 5.x
API), chain: Render Layers → Glare (Bloom) → Color Balance (ASC-CDL) → Color Correction
(highlight saturation) → Hue/Sat → vignette multiply → Group Output `Image`.

### `camera_look_at(name, location, target, lens=35, collection=None) -> Object`
Creates or updates a camera aimed at `target` (Z up, sensor 36 mm, clip 0.1–9000 m).
Example: `look.camera_look_at('cam.hero', (0, -80, 10), (0, 0, 8), lens=35)`.

### `preview(build_fn, out_dir, name='preview', cameras='auto', resolution=(1280,720), footprint=40.0, samples=32, save_blend=None, quality='preview', haze=True, compositor=True) -> dict`
1. `reset_scene()` (in-place wipe of objects and data; see note).
2. `setup_render` + `setup_lookdev`.
3. `add_plinth`: neutral karst-pillar top, flat top at z = −0.4, radius footprint + 6 m,
   fluted sides 30 m deep, material `materials.get('rock_cliff')` (constant
   `PLINTH_MATERIAL`, the same rock world.py uses for pillars). If materials.py fails, a
   local rock is used and `LOOK WARN plinth: ...` is printed.
4. `build_fn(collection)` with collection `build.<name>`.
5. Frames cameras on the bbox of everything built (clamped to 1.6 × footprint in XY and
   −footprint…2 × footprint in Z, so a light pillar or a long stair does not shrink the
   shot), renders `<out_dir>/<name>_<cam>.png`, prints `PREVIEW_STATS`.

Cameras (`cameras='auto'`):

| name | where |
|---|---|
| `front_34` | from −X −Y, 25° up, lens 35 |
| `front` | on the −Y axis, eye height 10 m, lens 35 (the hero approach) |
| `aerial` | from the south-south-west, 55° up, lens 35 |
| `detail` | from −Y +X, 14° up, lens 50, at 45 % of the fitting distance on the bbox centre |

`cameras` may also be a comma string or list of those names, or a list of
`(name, location, target, lens)`. A build function can carry its own defaults:
`build.preview_cameras = [("hero", (0, -90, 12), (0, 0, 10), 35)]`; with `cameras='auto'`
these replace the four, and their names become valid for `--cams`.

### Also public
`add_plinth(collection, footprint=40, top_z=-0.4, depth=30, seed=11)`,
`auto_cameras(bbox, resolution)`, `build_bbox(scene, objects)`,
`count_triangles(scene, objects=None)`, `reset_scene()`, `ensure_collection(name, parent=None)`,
`hex_color('#rrggbb') -> linear RGBA`, `srgb_to_linear(c)`, `main(argv)`.

## Notes and 5.2 API facts found while building this

- `reset_scene()` removes all objects/meshes/materials/node groups in place. A lib cache
  that keeps datablock references must check them (`name in bpy.data.materials`) before
  reuse. Do not use `bpy.ops.wm.read_factory_settings` in background scripts: it tries to
  clean the user's extension folder.
- Sky Texture: `sun_rotation` equals the compass azimuth (0 = sun toward +Y, +90° toward
  +X). The `Vector` input is unavailable for the scattering sky types. EEVEE does not
  draw the sky's sun disc (Cycles only), hence the painted disc.
- `scene.eevee.volumetric_start/end` only apply with `use_volume_custom_range = True`.
- Glare node settings are input sockets in 5.x: `Type` = `'Bloom'`, `Quality` =
  `'High'|'Medium'|'Low'`, `Threshold`, `Smoothness`, `Clamp`, `Maximum`, `Strength`,
  `Saturation`, `Size`. Color Balance `Type` = `'Offset/Power/Slope (ASC-CDL)'`.
- AgX looks are `'AgX - Punchy'`, `'AgX - Base Contrast'`, `'AgX - Medium High Contrast'`, …
- For world.py: call `setup_render(scene, 'final', (1920, 1080))`, then
  `setup_lookdev(scene, haze=False, cloud_floor=False)` and your own `add_haze(...)` tuned
  for the real altitudes, and place the moon with `moon_placement`. Keep the moon's
  emission below the bloom clamp (≤ 30).
