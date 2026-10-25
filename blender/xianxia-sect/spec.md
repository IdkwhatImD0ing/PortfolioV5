# The Sun Moon Divine Sect (日月神教) — xianxia fly-through proof of concept

The portfolio site at art3m1s.me is one long scroll. This scene turns that scroll into a
flight through a cultivation sect on floating karst peaks. Every website section maps to one
sect area, in scroll order. The camera flies a single continuous path past all of them,
starting in the sea of clouds and ending at the summit under a colossal moon
(art3m1s → Artemis → moon).

The sect is the Sun Moon Divine Sect (日月神教) of Jin Yong's *The Smiling, Proud Wanderer*.
Until round 32 (October 2026) it was the Ming Sect (明教) of *Heaven Sword and Dragon Saber*;
the owner renamed it. The reasons: 日月 is sun and moon and 神 is divine, so the moon and a
goddess (Artemis) are in the name; the English name reads plainly to visitors who don't know
Chinese; and the orthodox sects of the novel call it unorthodox, a nod to the owner's own
unorthodox education. The gate's two blade monoliths stay the Heaven Sword 倚天剑 and the
Dragon Saber 屠龙刀 of *Heaven Sword and Dragon Saber*, and the novel's Ming Sect still lends
the scene its holy fire, Holy Fire Tokens and Five Element Banners, as the Ming Sect's.

This file is the contract every module author follows. Read all of it before writing code.

## 0. UPDATE: this is a blocking pass for AI video (overrides anything below)

The Blender scene is **not** the final image. It is the *blocking* (layout + camera) for
an AI video model (Seedance via Higgsfield), following this workflow: block the scene in
Blender → render the fly-through → Claude writes a second-by-second prompt from it → the
video model generates the final look, using the blocking as its guide. So:

- **Shape and outline only.** What matters: the silhouette and massing of each area,
  recognisable building types (hall, pagoda, gate, pavilion, stele...), correct scale
  relationships, the focal object of each area (mirror, cauldron + artifact ring, jade
  tablets, giant scroll, formation rings...), clear colour coding (red columns, teal roofs,
  white marble, grey rock, green trees, cyan glow), and a clean camera path.
- **No polish.** Do not spend time on fine ornament, texture detail, bevels, tile courses,
  or material subtlety. The library parts (`sect/lib`) are already more detailed than
  needed; use them as-is. Simple primitives are fine for anything the library lacks.
- **Time box:** an area should take about 20–30 minutes: build, render the camera-hint
  views 2–3 times, fix what is obviously wrong (scale, clipping, missing focal object,
  unreadable composition), stop.
- **The world is a celestial realm: a mountain range floating in the sky.** One
  continuous chain of steep Huangshan/Zhangjiajie-flavoured peaks and ridges, high above
  an endless cloud sea; no ground is ever visible. The range's underside breaks up into
  inverted craggy rock and hanging roots that dissolve into cloud; smaller floating islets
  (some with a pine or a tiny pavilion) drift around it, and waterfalls pour off its edges
  into the void. The sect's areas sit on its peaks, shoulders and terraces, linked by
  stairways and bridges. The flight goes up the range from its lowest end (the gate) to
  its highest peak (the summit). The arena floats on its own over a gap in the range.
  Heavenly mood: vast sky, layered clouds, god rays, the colossal moon.
- **Clips:** the video model generates clips of at most ~12 s, and credits are limited.
  The camera path is planned as consecutive segments of ≤ 12 s, each starting where the
  previous one ended, so each segment can be generated separately and joined.

## 1. Paths and tools

```
ROOT = E:/Github/PortfolioV5/blender/xianxia-sect
ROOT/spec.md                      this file
ROOT/sect/__init__.py             empty
ROOT/sect/lib/__init__.py         empty
ROOT/sect/lib/util.py             mesh/object/collection/instancing helpers, seeded RNG
ROOT/sect/lib/materials.py        every shared procedural material, by name
ROOT/sect/lib/look.py             look-dev lighting + render settings + preview harness
ROOT/sect/lib/arch.py             Chinese architecture primitives
ROOT/sect/lib/props.py            props: lanterns, plaques, banners, cauldrons, statues, chains, bridges...
ROOT/sect/lib/nature.py           pines, blossom trees, bamboo, rocks, water, waterfalls, lotus, scatter
ROOT/sect/areas/<key>.py          one module per sect area (section 4)
ROOT/sect/world.py                sky, sun, moon, cloud sea, rock pillars, backdrop karst forest, connectors
ROOT/sect/camera.py               the fly-through camera path + section timeline
ROOT/sect/assemble.py             builds the full scene and saves out/sect.blend
ROOT/docs/api_<module>.md         API notes written by each lib module author
ROOT/out/previews/<module>/       preview PNGs (each author writes only into their own folder)
ROOT/out/tmp/<module>/            scratch .blend files etc. (own folder only)
ROOT/out/frames/, ROOT/out/video/ final render (assembly stage only)
```

Blender: `"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"`, version 5.2.2 LTS.

- Run Blender **only in background mode**:
  `blender.exe --background --factory-startup --python <script.py> -- <args>`.
  Blender's stdout is noisy; print your own results with a unique prefix and grep for it.
- **Never** call the `mcp__blender__execute_blender_code` tool or anything else that touches
  the user's open Blender window. **Never** use Higgsfield or any paid generation service.
- The only render engine id is `BLENDER_EEVEE` (EEVEE Next: ray tracing, volumetrics,
  virtual shadow maps). Cycles with OptiX also works on the RTX 5080, but use EEVEE for
  previews; it renders 1080p in about 1 s for simple scenes.
- Sky texture `sky_type` enum: `SINGLE_SCATTERING`, `MULTIPLE_SCATTERING`, `PREETHAM`,
  `HOSEK_WILKIE`. (The old `NISHITA` id is gone.)
- The 5.x Python API differs from 3.x/4.x in places (compositor node trees, EEVEE settings,
  sky, mesh attributes, node socket names). When unsure, introspect `bl_rna.properties` or
  socket names at runtime instead of guessing. The `mcp__blender__search_api_docs` and
  `mcp__blender__search_manual_docs` tools search the bundled 5.x docs and do not need the
  live Blender.
- Fonts for calligraphy: `C:/Windows/Fonts/simkai.ttf` (KaiTi, preferred for plaques),
  `C:/Windows/Fonts/msyh.ttc` (YaHei, fallback).
- Images: you can look at your own preview PNGs with the Read tool. Do it. Every module
  must be judged by looking at renders, not just by "the script ran".
- Several authors run Blender at the same time on one GPU. Keep previews at
  1280×720 or smaller, EEVEE only, and do not leave long renders running.

## 2. World conventions

- Meters, Z up. **+Y is the direction of travel** (roughly north). The camera starts at the
  south end in the clouds and flies north while climbing.
- Human scale: a disciple is 1.75 m. A hall column is 5–7 m tall and 0.5–0.7 m thick.
  Doors 3.5–4.5 m tall. Stair risers 0.15–0.18 m.
- Time of day: golden hour. The sun is low in the west (azimuth pointing from −X, elevation
  about 6–8°), warm. A colossal full moon (about 14° wide, stylised, far bigger than real)
  hangs in the north-north-east sky at about 16° elevation. The sky in the north is a
  cooler blue-violet; the west glows amber. Lanterns are already lit.
- The cloud sea fills everything below z ≈ 20 m. Nothing below z = 0 is visible except
  through thinning cloud.

## 3. Art direction

References (from memory): donghua like *A Record of a Mortal's Journey to Immortality* and
*Soul Land*; Genshin Impact's Liyue and Jueyun Karst; the Zhangjiajie sandstone pillars;
Huangshan's pines over a sea of clouds; Wudang mountain temples.

Palette:

| Use | Colour (sRGB approx.) |
|---|---|
| Lacquered columns, doors | vermilion `#9b1c1c` → `#b32a1f`, satin |
| Main-hall glazed roof tiles | deep teal-green `#1f4f4b` (glossy, slightly bluish highlights) |
| Minor buildings' roof tiles | charcoal grey-black `#2a2c30` |
| Summit / moon buildings | moon-white glaze `#d9dde6` with silver |
| Bracket band (dougong) paint | blue-green `#2f6f73` / `#3d8a7a` with gold `#c9a24a` edge lines |
| Trims, ridge ornaments, finials | gold `#d4af37`, metallic |
| Bronze (cauldrons, mirrors, bells) | `#7a5a2e` with verdigris `#4f8a7a` in crevices |
| Terraces, balustrades, stairs | white marble (hanbaiyu) `#e8e4da`, slightly warm, subtle veining |
| Cliffs, pillars | sandstone/grey `#8a8172` → `#5e5a52`, with moss `#4b6b3a` on ledges |
| Spiritual energy, runes, glows | jade-cyan `#6fffd8` (primary), moon-silver `#cfe3ff`, gold `#ffd27a` (rare) |
| Lantern light | warm `#ffb46b`, emissive paper |

Architecture rules (this is what makes it read as Chinese rather than generic fantasy):

1. Every important building stands on a raised stone platform (xumizuo, with stepped
   mouldings) reached by stairs, often with a central carved ramp (yubu) between flights.
2. The roof dominates the silhouette: it is 40–55 % of total building height. Roof slopes
   are concave (steeper near the ridge, flatter near the eave). Eave corners sweep upward
   and outward (qiao jiao). Eaves overhang a lot (2–4 m beyond the columns).
3. Main ridge ends carry chiwen ornaments; hip ridges carry a row of small beast figures
   ending in a raised tip. Tiles show as ridged rows (alternating convex/concave courses)
   with a row of round end-caps along the eave.
4. Under the eave there is a visible bracket band (dougong) between the column tops and the
   roof, painted blue-green with gold.
5. Red columns are set back under the deep eaves, so façades sit in shadow and the roof
   edges catch the sun.
6. Doors and windows are lattice panels, never plain glass. Hanging plaques (dark blue board,
   gold border, gold calligraphy) sit centred under the upper eave.
7. Lanterns hang from eave corners and line paths; stone lanterns flank stairs.
8. Composition: symmetry along the main axis for formal halls; organic placement for
   gardens, rocks, trees.

Magic layer (sparingly, so the architecture stays the star): jade-cyan rune circles, floating
artifacts, floating scrolls, light pillars, spirit motes. Glows should be emissive surfaces
picked up by the compositor's bloom, not flat white blobs. Keep the brightest emissive
values below about 30 so bloom stays controlled.

Quality bar: this is the "production ready" hero asset of the PoC. Bevel visible hard edges
(bevel modifier, 2–3 segments, or bmesh bevel). No default grey materials. No z-fighting.
No floating objects unless they are meant to float. No interpenetrating junk. Silhouettes
should read at a distance; detail density goes up near the camera path.

Performance: repeated elements (tiles, columns, brackets, balustrade posts, lanterns, trees,
rocks, banners, steles) must be linked duplicates, collection instances or geometry-node
instances, never unique copies. Budget: whole scene under about 15 M evaluated triangles;
each area under about 1.5 M. All geometry deterministic (fixed seeds), all materials
procedural (the only external asset is the font).

## 4. Section → area map (scroll order)

`anchor` is the world position of the area's local origin (centre of its plateau top);
`yaw` is decided by assembly so the area's front faces the incoming camera.
`footprint` is the radius (m) the area must fit inside in XY.

| # | Site section id | Area key | Sect area | Plaque | Anchor (x, y, z) | Footprint |
|---|---|---|---|---|---|---|
| 1 | `hero` | `gate` | Mountain Gate | 日月神教 | (0, 0, 40) | 40 (stairs may extend south past it) |
| 2 | `about` | `mirror` | Heart-Mirror Terrace | 心镜台 | (−95, 185, 70) | 45 |
| 3 | `projects` | `forge` | Artifact Forge Peak | 炼器峰 | (115, 335, 95) | 50 |
| 4 | `hackathons` | `arena` | Sword-Discussion Arena (floating) | 论剑台 | (−35, 485, 120) | 48 |
| 5 | `experience` | `mission` | Mission Hall | 任务殿 | (−150, 625, 140) | 50 |
| 6 | `education` | `library` | Scripture Pavilion | 藏经阁 | (125, 765, 165) | 42 |
| 7 | `skills` | `steles` | Stele Forest of Techniques | 碑林 | (5, 905, 185) | 50 |
| 8 | `resume` | `scroll` | Jade Slip Pavilion | 玉简阁 | (−125, 1045, 205) | 40 |
| 9 | `architecture` | `formation` | Grand Sect-Protecting Formation | 护宗大阵 | (65, 1195, 220) | 58 |
| 10 | `personal` | `abode` | Cave Abode | 洞府 | (185, 1335, 250) | 45 (builds its own cliff) |
| 11 | `footer` (and the end of the scroll) | `summit` | Moon-Gazing Summit | 望月台 | (0, 1500, 320) | 40 |

Portfolio facts the areas echo (use them as counts, never as readable English text):
15 projects, ~40 hackathons, 7 roles in the experience timeline, 3 schools
(Lynbrook → UCSC → USC), skills grouped into categories.

### Area briefs and what the camera will do

The camera is the audience. Put the most detail where it looks.

1. **gate — Mountain Gate 山门 (hero).** A colossal five-bay paifang gate (about 34 m wide,
   24 m tall) with stepped glazed teal roofs over each bay, red columns on white marble
   bases, gold plaque 日月神教 above the centre bay. In front (south, −Y) a grand white
   marble stairway descends steeply about 60 m down the cliff into the cloud sea
   (it may extend to y ≈ −130, z ≈ −60 local), with landings every ~20 steps, balustrades,
   and paired stone lanterns. A pair of guardian beasts (stylised qilin or lions on plinths)
   and two blade-shaped stone monoliths flank the top: the Heaven Sword 倚天剑 and the Dragon
   Saber 屠龙刀. Banners on tall poles.
   **Camera:** rises out of the clouds up the stair axis, then flies through the centre bay
   about 9 m above the plateau. Centre bay clear opening must be at least 12 m wide and
   15 m tall.
2. **mirror — Heart-Mirror Terrace 心镜台 (about: who I am).** A still reflecting pond with
   a hexagonal open pavilion (ting) on a marble platform, reached by a zig-zag bridge. In
   the pavilion's view line stands a giant round bronze mirror (about 7 m) on a carved stand,
   its face polished and reflective. Lotus pads and flowers, a weeping willow or blossom tree,
   rocks, an incense burner with thin smoke. Calm and personal.
   **Camera:** sweeping arc past at 12–20 m altitude; the mirror catches the sun.
3. **forge — Artifact Forge Peak 炼器峰 (projects).** A two-tier forge hall (charcoal
   tiles, soot-darkened wood) whose open front reveals a colossal bronze ding cauldron (about
   8 m) glowing molten orange from inside, with ember sparks. Furnace chimneys trail thin
   smoke. Around the cauldron, **11 forged artifacts**, one per prize-winning project and chosen
   for it, biggest win first (a command flag, a treasure bowl of gold, an alarm bell, bamboo
   slips, a lotus lamp, a self-writing brush, peaches of immortality, prayer beads, a jade bi
   disc, paper cranes, a wind fire wheel), float in a slow orbiting ring, each with a faint
   glow. Anvils, quench troughs, weapon racks, ore piles.
   **Camera:** passes close in front; the artifact ring and cauldron glow are the shot.
4. **arena — Sword-Discussion Arena 论剑台 (hackathons).** A floating island (no rock
   pillar under it; it builds its own underside). The top is a 60 m circular stone dueling
   platform with concentric rings and a taiji/bagua inlay in the centre. Around the rim
   stand **~40 banner poles**, one per hackathon, cloth banners in varied colours. A
   spectator tier ring on one side, a giant stone sword statue (about 30 m) piercing the
   island at the back. The underside is an inverted rocky cone with hanging roots and small
   floating rocks orbiting. Massive chains run off to the sides (they may end loose).
   **Camera:** flies across low over the platform (about 12 m up), banners sliding past.
5. **mission — Mission Hall 任务殿 (experience).** A grand double-eave hall (xieshan roof,
   teal tiles) on a tall platform with a broad plaza. In front of it stands the mission
   wall: a tall carved frame from which **7 large glowing jade tablets** (the roles) hang on
   red cords with tassels, plus dozens of small wooden tablets. A bell tower and drum tower
   flank the plaza; side corridors.
   **Camera:** frontal approach along the axis, then rises over the hall roof.
6. **library — Scripture Pavilion 藏经阁 (education).** A tall octagonal pagoda library
   (7 tiers, about 45 m) beside a lotus pool. **3 of its floors glow** warmly (the three
   schools). Bookshelves are visible through open lattice windows on the lit floors. Glowing
   scrolls and books drift in a slow spiral around the pagoda. Small study pavilions nearby.
   **Camera:** curves around the pagoda while rising, the floating scrolls passing close.
7. **steles — Stele Forest of Techniques 碑林 (skills).** A terraced courtyard with rows of
   tall stone steles on turtle (bixi) bases, each carved with glowing glyph columns; glow
   colour varies by skill category. A larger central stele at the far end under a small
   open pavilion. Covered corridors (lang) frame the courtyard.
   **Camera:** low glide down the central aisle at about 4 m height. Central aisle at least
   12 m wide; steles no taller than 8 m; nothing over the aisle below 14 m.
8. **scroll — Jade Slip Pavilion 玉简阁 (resume).** An elegant two-storey pavilion on the
   cliff edge with a stone desk, brush and inkstone on its terrace. Floating in front of
   it, a colossal unrolled jade bamboo-slip scroll (about 22 m wide, 9 m tall, slightly
   curved) with glowing calligraphy columns, plus a small stack of floating jade slips.
   **Camera:** passes in front of the floating scroll, almost reading it.
9. **formation — Grand Sect-Protecting Formation 护宗大阵 (architecture: the system
   design).** A vast circular plaza (about 100 m across) engraved with concentric glowing
   rune rings (a trigram ring, a sigil ring, an outer script ring). **8 array-flag pillars**
   stand at the nodes, linked by beams of light that form a network diagram, like a system
   architecture of services and connections. A floating array core (jade disk or
   octahedron) at the centre sends a light pillar into the sky. A faint translucent dome
   suggests the protective shield.
   **Camera:** high overhead pass looking down, so the whole circuit reads as a diagram.
10. **abode — Cave Abode 洞府 (personal).** The private dwelling carved into a cliff face
    (this module builds its own cliff, about 60 m tall, rising behind the plateau). A round
    moon-gate entrance in the rock, a wooden balcony with a tea table and cushions, a
    waterfall cascading beside it into a misty pool with koi, a peach blossom tree, a bamboo
    grove, wind chimes, a resting crane. Warm, lived-in.
    **Camera:** swings past the waterfall and balcony.
11. **summit — Moon-Gazing Summit 望月台 (footer: the end).** The highest peak: a circular
    white marble terrace with a single elegant round two-tier pavilion (moon-white tiles,
    silver finial), a lone ancient pine leaning over the edge, and a crescent-moon arch.
    Beyond it the colossal full moon fills the sky.
    **Camera:** ascends past the terrace and tilts up so the last frames are mostly moon.

## 5. Module contracts

### Lib (`sect/lib/*.py`)

- Pure functions that create objects. They take a `collection` (or create objects in a
  given collection), a `name` prefix, a `seed` where randomness matters, and dimensions in
  meters. They return the root object they created (an Empty parent, or a single object).
- Every lib builder places its result at the local origin with its front facing −Y unless
  the function takes a matrix/location argument.
- Every lib function is safe to call many times in one scene (unique names, shared
  materials and shared mesh data reused through caches).
- `materials.get(name)` returns a shared material, creating it on first use. Unknown names
  raise KeyError listing valid names. `materials.NAMES` lists them all.
- `look.setup_lookdev(scene)` sets render settings and a sky + sun + haze close to the
  final look, so previews match the final scene. `world.py` builds on the same functions.
- `look.preview(build_fn, out_dir, cameras=..., resolution=(1280,720))` is the harness:
  fresh scene, look-dev lighting, a neutral rock plinth under z=0, calls `build_fn(collection)`,
  renders the given cameras to PNGs, and prints a stats line (object count, evaluated
  triangle count, build time). Area and lib authors use it to test.
- Each lib module author documents their public functions in `docs/api_<module>.md`
  (signature, what it builds, size, one-line example).

### Areas (`sect/areas/<key>.py`)

```python
AREA = dict(key="forge", section_id="projects", title_en="Artifact Forge Peak",
            title_zh="炼器峰", footprint=50.0)

def build(collection):
    """Build the whole area at the local origin. Return the root Empty."""

# Where the fly-through camera should pass, in LOCAL coordinates (front = -Y).
# 2-4 hints, ordered along the flight. The camera stage stitches these into one path.
CAMERA_HINTS = [
    dict(name="approach", location=(0, -90, 18), target=(0, 0, 10), lens=28),
    dict(name="hero",     location=(25, -30, 12), target=(0, 5, 8),  lens=24),
]
```

- `CAMERA_HINTS` must be views that look great (render them and check), must not clip
  through geometry, and must be consistent with the camera brief in section 4. Keep the
  hero view at least 6 m from any geometry so a moving camera has room.

- Local frame: origin = centre of the plateau top. z = 0 is the walkable surface. The
  area's front (main façade, entry stairs, the side the camera arrives from) faces −Y.
- Everything is parented (directly or indirectly) to the returned root Empty
  (named `<key>.root`) and linked into `collection` or its child collections. Object
  names start with `<key>.`.
- Stay inside the footprint radius in XY, except: vertical elements, things hanging off the
  edge (chains, roots, waterfalls), and the exceptions in the area brief.
- Do not build the mountain under the plateau: `world.py` builds the mountain-range
  terrain with a flat terrace at z = −0.4 local, radius footprint + 6 m, under every anchor
  (except arena), falling away as mountain slopes beyond that. Build your own
  paving/terrace from z = 0 down to at most z = −3. Exceptions: `arena` builds its own
  floating island underside; `abode` builds its own cliff face behind the plateau (extend it
  down to local z = −40 so it merges into the terrain slope); `gate` builds its descending
  stairway down the mountainside (it will be partly buried in the slope, which is fine).
- Do not change world, scene or render settings. Do not touch other modules' objects.
- Deterministic, idempotent, no external files except the font.
- At least one hanging plaque with the area's `title_zh` via the props plaque function.
- Local lights: emissive materials first; at most 8 point/spot lights per area.

### World, camera, assembly

- `world.build(scene, anchors)` builds sky, sun, moon, haze, cloud sea, pillars under each
  anchor, backdrop, connectors. `anchors` is a dict key → (x, y, z, footprint, yaw).
- `camera.build(scene, anchors)` builds the camera and its path, sets the frame range, and
  writes `out/section_timeline.json`:
  `[{"section_id": "hero", "area": "gate", "frame_start": 1, "frame_end": 120, "hero_frame": 90}, ...]`.
- `assemble.py` builds everything into one scene and saves `out/sect.blend`.

## 6. Render target (blocking)

Blocking render: 1280×720 (or 1920×1080 if cheap), 24 fps, EEVEE preview quality, one
MP4 per camera segment plus the full fly-through, plus a still of the first and last frame
of every segment (start/end frame references for the video model). The original
production target below is kept only for reference.

## 6b. Original production render target (superseded)

1920×1080, 24 fps, about 45 s (≈1080 frames), EEVEE with ray tracing, volumetrics and
volumetric shadows, motion blur, AgX view transform, compositor bloom (Glare node), subtle
vignette. Output PNG frames, then an H.264 MP4 for viewing plus an all-keyframe MP4 for
scroll-scrubbing on the website.

## 7. Web light bake (/sect)

The website's scene is light-baked in Cycles on the rented cloud GPU, never on the PC. A full
render batch, in order: `sect/export_web.py -- audit --profile full` (visibility, ~40 min),
`-- chunks,meta --profile full`, `sect/bake_web.py -- bakefull,water --profile full` (areas +
backdrop, water), `sect/bake_trees.py -- plan,build` (vegetation), `sect/export_web.py -- clouds
--profile full` (the Blender puffs: Ice-Fire's steam, the falls' spray chains; skipping it lets
`mist.py` copy stale puffs back), then on the PC `sect/mist.py` and `tools/sect_pack.py --profile
full`. A changed export or bake script needs `PIPELINE_CHANGED_OK=1` in the round's run sheet.

- `--quality dev` (the default) is the fast bake for development: atlas 160 samples,
  vertex colours 256, trees 128 / sprites 48. About 47 min (areas) + 39 min (trees,
  30 of them sun ray casts that are cached on the box) on one RTX 5090.
- `--quality production` is for one final bake once the content is final. It changes
  only noise: atlas 768, vertex colours 1024, trees 512 / sprites 192, denoiser guide
  passes 4x, adaptive sampling off, denoisers pinned to High. Same files, sizes, chunk
  plan and brightness. About 1 h 40 min (areas; worst case 3.5 h) + 30-60 min (trees).
- One table, `BAKE_QUALITY` in `bake_web.py`, holds both. `--samples` / `--vc-samples`
  still override. Each run logs `BAKE quality ...` first and each chunk's JSON records it.
  `sect_pack.py --quality` is unrelated (WebP quality).
