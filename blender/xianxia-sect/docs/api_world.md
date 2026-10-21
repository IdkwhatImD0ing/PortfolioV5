# sect.world — the celestial realm

Builds everything around the sect areas: sky, sun, haze, the moon, the floating mountain range,
clouds, islets, waterfalls, backdrop spires and the connectors between areas. Blocking pass
(spec section 0): shape, scale and colour coding, not detail. Deterministic; about 2.7 s to build
on the cloud box, about 1.6 M evaluated triangles.

```python
from sect import world as W
L.setup_render(scene, "preview", (1280, 720))   # assembly sets quality first (optional)
root = W.build(scene, anchors)                  # anchors: key -> (x, y, z, footprint[, yaw])
```

`anchors=None` uses `W.ANCHORS`. The world never touches area objects.

## Public names

| name | what |
|---|---|
| `build(scene=None, anchors=None) -> Object` | Builds into collection `world` (children `world.sky`, `world.range`, `world.clouds`, `world.islets`, `world.water`, `world.links`). Returns Empty `world.root` with `build_s` and `times` props. Calls `look.setup_lookdev(haze=False, cloud_floor=True)` (render settings only if `setup_render` never ran; the sun lamp goes in collection `look`) and adds its own haze `world.haze`. |
| `ANCHORS` | spec section 4 table: key -> (x, y, z, footprint) |
| `ORDER` | flight order of the keys |
| `FLOATING` | `("arena",)`: no terrace, a gap in the range under it |
| `PREVIEW_CAMERAS` | (name, location, target, lens): `south` (0,-200,30) up the range, `overview` from the SW, `formation` mid-route looking NE, `moon` from (0,1500,330) |
| `Range(anchors)` | the range as analytic fields. `fields(x, y)` on numpy arrays returns `T` (top height), `F` (= T - rim, > 0 inside the mass), `rim`, `flat` (terrace mask), `dmin` (distance to the corridor), `zl` (corridor line height). `underside(x, y, F, rim)`, `top_at(x, y) -> (T, F)`, `seg_point(seg, t, lateral)`. Use it to put things on the terrain. |
| `clearance_report(anchors=None)` | {"a-b": (min clearance m, t)} between each anchor-to-anchor line and the terrain, outside the terraces |
| `build_sky`, `build_moon`, `build_terrain`, `build_forest`, `build_roots`, `build_cloud_sea`, `build_clouds`, `build_islets`, `build_backdrop`, `build_waterfalls`, `build_connectors` | the steps `build` runs, callable on their own |

## What it builds (world metres, +Y north)

| part | facts |
|---|---|
| Sky | `look` sky texture + painted sun + world cloud floor below the horizon (beyond 9 km), sun lamp, compositor. Haze: density 0.0003 at z = 100, falloff 220 m, box from z = -120. |
| Moon `world.moon` | Sphere with `moon_surface` (`["glow"] = 1.25`), placed with `look.moon_placement(5000, MOON_VIEW)`: exactly 14° wide, azimuth 22.5°, elevation 16° seen from (0, 1500, 330); radius 614 m, centre about (1840, 5940, 1710). Seen from the gate it is about 10.5° wide. Halo `world.moon_halo`: an additive disc behind it facing the summit. No shadows. |
| Range `world.range` | One closed heightfield mesh, 5 m grid, 214k tris: top surface plus an inverted craggy underside (cellular stalactite spikes) meeting at a knife-edge rim 75 m under the corridor. Material slots: `rock_cliff`, `nature_soil_moss` (flat tops and terraces), `world_rock_under`. Face attribute `world_veg` drives the pine scatter `world.range.forest` (far pines, 0.0008 per m², ~580k tris). Roots: `world.roots`. |
| Terraces | Under every anchor except the arena: flat at anchor z - 0.4, radius footprint + 9 (up to +15 in bulges), then a 3.6:1 cliff for 12 m and 1.3:1 slopes below. |
| Ridges | Between consecutive anchors with mass: a meandering crest at line - 33 - 22·sin(πt) (+ noise), capped at line - 25 within 120 m of the corridor. library→steles has a deep notch (the arched bridge spans it). Forge→arena→mission has no mass: a gap ~100 m around the arena. |
| Peaks | 3-4 per segment plus fingers and 6 outliers: half Zhangjiajie columns (6.5:1 walls, broad cap), half Huangshan cones (3.4:1). Anything taller than line - 25 stands > 120 m off the corridor (most at 160-400 m), giving the canyon. |
| Gate slope | South of the gate: a 0.66 slope 1.8 m under gate.py's stair line, 26 m wide, down to the rim near y = -157. |
| Cloud sea `world.cloud_sea` | Billowy grid ±9 km (denser near the range) at z ≈ -60 with `world_cloud_sea` (opaque, warm tops, fades to the horizon colour with view distance). `world.cloud_fog`: a volume box from z = -90 to +20 whose density grows from +15 down to -85, so the underside and waterfalls dissolve into cloud. |
| Cloud banks | `world.cloud.opening`: the bank around (0, -260, 15) that the camera starts inside (fully white there), clear by about y = -225. `world.cloud.stairfoot`: puffs around the gate stair foot. About 8 mid-level banks (320-460 m) 190-320 m off the corridor, 45-80 m below it; one in the arena gap; 12 wisps on the cloud sea. Three faint additive cirrus sheets at z 1700-2400. |
| Islets | 30 `nature.floating_rock` islets, 6-26 m, 55-620 m off the corridor (never within 90 m of it at camera height); most carry a mid-LOD pine. No buildings (audit W8: a pavilion with no bridge reads as unreachable). |
| Backdrop | 14 far-LOD karst massifs on a 1.4-3.5 km ring, rising from the cloud sea, kept out of the moon's line of sight from the summit. |
| Waterfalls | 5 (mirror W, library E, abode E, scroll W, forge SE): a water strip from the terrace edge down to the range's rim, then a 12-18 m wide ballistic sheet falling into the fog. Material `nature_waterfall`. |
| Connectors | `world.link.<a>_<b>.*` (audit W1-W6), each from the leaving area's `AREA['depart']` to the next area's `AREA['arrival']` ((x, y, z, heading) in the area frame; heading in radians from local +x; `PORTS` holds the plan's values as a fallback). Marble stairways 5 m wide: 15 m straight at both ends, equal risers <= 0.17 m, flights of at most 18 with landings between, parapets from the first flight on, stone piers and arcades where they stand > 4 m over the ground; a 5 m foot landing with a one-bay archway (railed on its sides when it stands over a drop; none at the steles, scroll and formation departs, which have their own gates) and a rest pavilion halfway on stairs > 100 m. library→steles: a level arched bridge over the notch. forge→arena: a stepped plank chain bridge (sag 2 m, level 4 m at both ends). arena→mission: 21 flat-topped floating stones, 1.07 m up per hop, edge gaps <= 0.4 m. `build_connectors` prints one `WORLD LINK {json}` line per link. Walkability: `.claude/skills/sect-architecture/scripts/walk_sect.py` (W9). |

## Clearance (corridor line vs terrain)

`clearance_report()` gives at least 25 m on every segment except abode→summit (22 m). That
low point is the summit terrace's own cliff edge, about 10 m beyond its flat top, where the
line climbs steeply into the terrace. The camera is at least 10 m above the terrace there
anyway.

## Materials registered (`world_*`)

`world_cloud_sea`, `world_cloud_fog` (volume), `world_cirrus` (additive), `world_moon_halo`
(additive, object coords with moon radius = 1), `world_rock_under` (darker `rock_cliff`).

## Preview

```
python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background --factory-startup --python E:/Github/PortfolioV5/blender/xianxia-sect/out/tmp/world/preview_world.py -- [--cams south,moon] [--tag name] [--extra '[["n",[x,y,z],[tx,ty,tz],lens]]']
```

The preview script adds coloured stand-in blocks at every anchor and prints `WORLD_STATS`,
`WORLD_TRIS` and `WORLD_CLEARANCE`. Renders are in `out/previews/world/` (`final_*.png`; the
`v4_opening/gap/arch.png` files are check views of the opening bank, the arena gap connectors and
the arched bridge).

Speed (EEVEE preview quality, 1280×720, cloud RTX 5090, with stand-ins): build 2.7 s. About
0.6-0.9 s per frame. The first frame of a run takes 1.6 s, or up to 4 s on a cold shader
cache.

## Gotchas found

- On the cloud box, Blender turns a render path like `E:/...` into `/e/...`. Build output
  paths from `__file__` (which resolves to the `/E:/...` mirror) so the wrapper copies the
  files back.
- EEVEE's volume grid covers 0.5-4000 m. Cloud puffs under ~60 m vanish past a few hundred
  metres, so mid-level banks use 320 m+ banks with density 2.2.
- `nature.rock_pillar(vegetation=True)` on a wide dome top scatters about 800 far pines (about
  0.5 M tris). The backdrop uses `vegetation=False`.
- `nature.floating_rock` puts a hero-LOD pine (23k tris) on islets of size 8 m or more unless
  `pine_on_top=False`. The islets add their own mid-LOD pine.
