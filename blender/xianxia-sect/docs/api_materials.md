# sect.lib.materials

Every shared procedural material, by name. All procedural except the photo-scan layers of the
rock and ground materials (see "Photo-scan layers" below), built for EEVEE 5.2 under the
golden-hour look in `look.py` (sun 7 deg WSW, AgX `AgX - Punchy`, exposure +0.25,
bloom threshold 2.0 on **luminance**). Swatch boards: `out/previews/materials/swatch_*.png`; real-scale test:
`scale_far.png`, `scale_near.png`; backlit cloth: `backlit_thin.png`.

```python
from sect.lib import materials as M

mat = M.get("lacquer_red")      # built on first use, then shared (cached by name)
M.NAMES                         # every registered name (list, updated by register)
M.banner_cloth(i)               # banner colour i (wraps around 8)
M.PALETTE["jade_cyan"]          # spec palette as sRGB hex, for lights etc.
M.get("nope")                   # KeyError listing every valid name
```

`util` functions accept material names directly (`materials=["marble_white", "gold"]`).

## Rules every module should know

- **Texture space is meters on the object's own axes** (object coords x object scale). Patterns
  stick to moving or instanced objects and keep their size when an object is scaled.
  Exceptions: `cloud_volume` and the photo-scan layers use world coordinates (so in the film the
  scans slide over moving objects, e.g. about 4 cm a frame on arena's orbiting islets; the web
  bake is static); lanterns, light
  beams, lotus flowers and volumes also use the object's bounding box (generated coords) for
  gradients/fades.
- **Bump only**, no displacement.
- **Per-object controls** (custom properties, all optional):
  - `obj["glow"] = 2.0` multiplies emission of glowing materials (runes, jade_glow, jade_slip,
    lanterns, paper_screen_lit, molten, ember, light_beam, glass_shield, moon_surface, water_fall).
  - `obj["density"] = 3.0` multiplies the density of `smoke_volume`, `mist_volume`, `cloud_volume`.
  - Every object / instance gets a subtle colour shift from Object Info > Random, so repeated
    tiles, planks, banners and leaves never look identical.
- **Edge wear**: meshes processed with `util.bevel_mesh()` carry a face attribute `edge`; gold,
  silver, bronze, bronze_verdigris, iron, steel and lacquer_red_worn brighten / chip there.
  Without it they still look right, just without worn edges. (EEVEE has no Pointiness and AO
  "inside" does nothing in EEVEE, hence the attribute.)
- **Grain direction**: `wood_*` grain and `bamboo_stalk` nodes run along local **Z**. Model
  columns/posts upright; for beams along X/Y the ring pattern still reads as wood.
- **Emission**: all strengths stay well under 30. AgX turns bright saturated emission white, so
  glows use deep, saturated colours at moderate strength (runes 4, lanterns 2.6 to 3, molten 7,
  ember 24 on tiny sparks). Raise per object with `obj["glow"]` instead of new materials.
  Bloom keys on luminance (0.21 R + 0.72 G + 0.07 B), so warm glows bloom less than cyan ones.
  Measured peak luminance under look.py: `paper_lantern` 1.7–2.6 (faint halo), `lantern_red` 0.8
  (no halo unless `obj["glow"]` is about 3), `rune_cyan` 2.9, `molten` 3.5; bloom starts at 2.0.
- **Animated** materials use `frame` drivers (simple expressions, no Python needed): water_fall
  streaks flow down (0.12 m/frame), water_pond ripples drift, smoke/mist rise, light_beam streaks
  rise, molten churns, glass_shield shimmers.

## Names

Spec names (all present) plus extras marked *.

| Name | What it is / where to use it |
|---|---|
| `lacquer_red` | Vermilion satin lacquer, brush streaks, light clear coat. Columns, doors, railings. |
| `lacquer_red_worn` | Sun-faded vermilion with dust on top faces, fine craquelure, flakes showing grey putty and wood (more on `edge` faces and low down). Old buildings, forge, abode. |
| `lacquer_black`* | Black lacquer. Furniture, tea tables, frames. |
| `plaque_board` | Dark blue lacquered board for hanging plaques (gold border/text are separate). |
| `wood_dark` | Dark brown timber, grain along Z. Lattice, beams, shelves. |
| `wood_light` | Weathered light timber. Balconies, decks, racks, tea houses. |
| `wood_soot` | Soot-blackened, charred patches. Forge hall. |
| `roof_tile_teal` | Glossy deep teal-green glaze, bluish coat highlights, kiln variation, faint streaks. Main halls. |
| `roof_tile_black` | Unglazed charcoal clay tiles. Minor buildings, forge. |
| `roof_tile_moon` | Moon-white pearly glaze. Summit / moon buildings. |
| `bracket_paint` | Dougong paint: blue-green fields (teal / green / blue chosen per piece) with a **gold border line, thin dark and white lines along the edges of each box-like piece** (uses the object's bounding box, so model each bracket arm/block as its own object or instance). |
| `gold` | Rich polished gold leaf, slight tarnish, bright on `edge`. Trims, finials, plaque borders, text. |
| `silver` | Satin silver. Summit finial, artifacts. |
| `bronze` | Dark olive bronze. Bells, mirrors, statues. |
| `bronze_verdigris` | Bronze with pale green verdigris in crevices (screen-space AO) and patches, crusty bump. Cauldrons, old bells, censers. |
| `iron`* | Dark forged iron. Anvils, chains, hinges. |
| `steel`* | Polished blade steel. Swords. |
| `jade` | Deep green nephrite: soft clouds, faint veins, glassy coat, subsurface. Artifacts, ruyi, seals. |
| `jade_glow` | Jade with an inner jade-cyan glow. Mission tablets, array core. |
| `jade_slip`* | Paler, softer glowing jade. Bamboo-slip scroll, floating slips. |
| `ceramic_celadon`* | Pale green celadon glaze. Tea sets, vases. |
| `marble_white` | Hanbaiyu: warm white, faint veins, slight subsurface. Platforms, balustrades, stairs, statues. |
| `marble_paving` | Marble slabs 1.2 x 0.8 m (running bond in local X/Y) with grout grooves, per-slab tone. Floors, plazas, terraces (top faces). |
| `stone_grey` | Grey granite-like stone with specks. Stone lanterns, plinths, steles. |
| `stone_dark` | Dark polished stone. Steles, bixi turtles, inkstones. |
| `rock_cliff` | Grey-tan sandstone: uneven sediment layers along local Z, sparse vertical joints with dark seep (steep faces only, so flat pillar tops stay clean), water-stain streaks, lichen, moss on up-facing ledges. Tuned for 10 to 100 m pillars and cliffs. Also look.py's preview plinth. Photo layer: marble_cliff_06 (variants: `nature_rock_small` at half tile, `world_rock_under` Rock063). |
| `moss` | Velvety moss. |
| `grass` | Grass ground with dry patches. Photo layer: leafy_grass + sparse_grass tufts. |
| `soil` | Soil with pebbles. |
| `foliage_pine` | Dark blue-green needles, mild translucency. |
| `foliage_blossom` | Peach/cherry pink to white, translucent. |
| `foliage_willow` | Yellow-green willow, translucent. |
| `foliage_bamboo` | Fresh bamboo leaves, translucent. |
| `bark_pine` | Plated reddish pine bark with deep fissures. |
| `bark_dark` | Dark fissured bark (blossom tree, willow). |
| `bamboo_stalk` | Waxy green-yellow culm with node rings every 0.42 m along local Z; per-stalk yellowing. |
| `lotus_leaf` | Radial veins from the object origin, lighter centre, waxy sheen, slight browning at the rim. Model pads as discs centred on their origin. |
| `lotus_flower` | Cream base to pink tips along the object's height, translucent petals. |
| `koi` | Kohaku-style white/red (some with black spots), scales, wet coat; pattern differs per fish. |
| `ink` | Wet black ink. |
| `paper_screen` | Rice paper for lattice windows, translucent (glows when backlit). |
| `paper_screen_lit` | Paper lit from inside, warm emission. Lit library floors. |
| `paper_aged`* | Aged paper with foxing. Scrolls, books. |
| `paper_lantern` | Glowing amber paper lantern: brighter core, darker ribs (14 over its height), dim caps. |
| `lantern_red`* | Glowing red silk lantern. |
| `cloth_red`, `cloth_gold`, `cloth_white`, `cloth_teal`, `cloth_black` | Silk/cotton with sheen and translucency (glows when backlit by the low sun). |
| `banner_0` ... `banner_7`* | Banner colours via `banner_cloth(i)`: vermilion, imperial gold, jade, teal, indigo, moon white, plum, ink black. |
| `rune_cyan`, `rune_gold`, `rune_silver` | Emissive strokes (strength ~4, blooms). Rune circles, glyphs, sigils. |
| `light_beam` | Additive transparent beam for a tall cylinder/cone: fades at the silhouette and upward along its height, rising streaks. Casts no shadow. |
| `glass_shield` | Faint additive dome: fresnel rim glow, faint energy-cell lines, slight gloss. Casts no shadow. |
| `water_pond` | Dark reflective still water with slow ripples (needs ray tracing for reflections). |
| `water_fall` | Falling sheet with foam streaks along local -Z, semi-transparent, fades at its top edge. Model as a plane/strip hanging down. |
| `molten` | Churning molten metal: hot yellow-orange cracks, darker cooling crust. |
| `ember` | Hot spark (use on tiny spheres/quads). |
| `smoke_volume` | Grey rising smoke. Default density suits 2 to 20 m domains (chimneys, censers). |
| `mist_volume` | Bright low mist, denser at the bottom. Suits 5 to 40 m domains (ponds, waterfall foot). |
| `cloud_volume` | Cloud sea in **world** coordinates (~45 m features), billowy top, thins upward. Suits domains 20 to 60 m thick and hundreds of m wide. |
| `moon_surface` | Self-lit stylised moon: maria, crater rims, limb darkening (use on a sphere; strength 2.2, raise with `obj["glow"]`). |

Volumes: put the material on a box/cylinder; density fades to zero toward the bounding box
(radial in XY, top and bottom fades), so the domain shape never shows. Use `obj["density"]`
for small or large domains (the 1 m swatches use 4x, clouds 30x).

## Adding module-specific materials

`register(name, builder, overwrite=False, **params)` registers `builder(g, **params)`, where `g`
is a `Graph` on a fresh material. `variant(name, base, **params)` reuses a built-in builder with
different parameters. Both return the name; then use `M.get(name)` as usual.

```python
M.variant("lacquer_blue", "lacquer_red", c1="#1b2a4a", c2="#24365c")
M.variant("rune_violet", "rune_cyan", colour="#b070ff", core="#efe0ff")
M.variant("cloud_puff", "cloud_volume", space="object", scale=0.2, density=0.6)

def _incense_ash(g):
    v = g.coord("object")
    n = g.noise(v, 30.0, detail=4.0)
    g.output(g.principled(base_color=g.ramp(n, [(0.3, "#4a4744"), (0.8, "#9a958e")]), roughness=0.95,
                          normal=g.bump(n, 0.3, 0.002)))

M.register("incense_ash", _incense_ash)
```

Built-in builders and their main parameters (for `variant`):
`_lacquer(c1, c2, worn, rough, coat)`, `_wood(c1, c2, grain, rough, soot)`,
`_tile(c1, c2, rough, coat, coat_tint, grime, glazed)`, `_bracket_paint(greens, gold, line)`,
`_metal(base, dark, rough, tarnish, edge_col, verdigris, verdigris_amt, scale)`,
`_jade(deep, pale, glow, strength, sss, veins)`, `_marble(base, vein, warm, rough, veins, grime)`,
`_paving(base, alt, grout, slab, joint)`, `_stone(c1, c2, speck, rough, bump, scale, moss)`,
`_rock(light, mid, dark, warm, cool, moss, strata, moss_amt, stain, joints, scan, scan_scale)`,
`_organic(colours, rough, sheen, translucency, scale, bump, transl_col, speckle, scan)`,
`_cloth(colour, sheen, translucency, rough)`, `_lantern(paper, glow, hot, strength, ribs, silk)`,
`_paper(base, fibre, lit, strength, translucency, aged)`, `_rune(colour, core, strength)`,
`_light_beam(colour, core, strength, speed)`, `_glass_shield(colour, strength, cell)`,
`_volume(colour, density, anisotropy, scale, contrast, space, rise, soft, height_bias)`,
`_moon(base, maria, strength)`.

### Graph helper (inside builders)

Every helper returns an output socket. Inputs accept sockets, numbers, tuples or `"#hex"` sRGB
colours.

| Method | Purpose |
|---|---|
| `coord(space="object", scale, offset, rotation)` | `object` (meters on object axes), `object_raw`, `world`, `generated`, `uv`, `normal` |
| `mapping(vec, scale, offset, rotation)` / `flow(vec, velocity)` | Mapping; `flow` animates by `velocity * frame` |
| `noise(vec, scale, detail, roughness, lacunarity, distortion, dims, ntype, w, color)` | Noise texture (Fac or Color); `dims='1D'` with `w` for layered bands |
| `voronoi(vec, scale, feature, distance, randomness, out, dims, w)` / `wave(...)` | Voronoi / wave textures |
| `ramp(fac, [(pos, colour), ...], interp)` | Colour ramp |
| `math(op, a, b, c)`, `mul`, `add`, `vmath`, `sep`, `comb`, `maprange`, `smooth` | Math (`smooth` = smoothstep) |
| `mix(a, b, fac, blend)`, `mixf(a, b, fac)`, `hsv(...)`, `tint_per_object(colour, hue, sat, val)` | Colour/float mixing, per-object variation |
| `bump(height, strength, distance, normal, invert)` | Chainable bump |
| `image(img, vec, out)` | Image Texture (FLAT, repeat) at `vec`; `vec` is required (UV-less meshes bake one texel otherwise) |
| `triplanar(images, tile, sharp)` | World-space triplanar: lookups of world (y,z), (x,z), (x,y) / `tile` m blended by \|normal\|^`sharp`; one colour socket per image |
| `principled(**inputs)` | Principled BSDF, snake_case socket names (`base_color`, `coat_weight`, `emission_strength`...) |
| `volume(**inputs)`, `emission`, `transparent`, `translucent`, `add_shader`, `mix_shader`, `output(surface, volume)` | Shaders and output |
| `geometry(out)`, `obj_random()`, `obj_rand3()`, `attr(name, kind, out)`, `obj_prop(name, default)`, `edge()`, `layer_weight`, `fresnel`, `ao(distance)` | Inputs |
| `blended(shadows=False)`, `viewport(colour, roughness, metallic)` | Material settings (forward transparency; solid-view colour) |

Other functions: `has(name)`, `rebuild(name)` (rebuild in place), `get_all()`, `rgb("#hex")`
(linear RGBA), `scan_image(fname, data)`, `scan_mean(img, weight)`, `scan_files()`, `PALETTE`,
`BANNER_COLOURS`, `REQUIRED`.

## Photo-scan layers

CC0 scans (2048 px JPGs in `assets/web`, `SCAN_DIR`, uploaded by `tools/rblender.py`) give the
rock and ground materials photo colour and structure. The bake stores only about 3 to 20 texels
per metre, so at web scale they read as natural colour and banding; the client's tiling detail
texture adds the fine detail.

| Material | Scan (tile) | Projection |
|---|---|---|
| `rock_cliff` | marble_cliff_06 diff + disp (8.14 m) | world triplanar |
| `nature_rock_small` | same, tile x `ROCK_SMALL_SCAN_SCALE` (0.5) | world triplanar |
| `world_rock_under` | Rock063 colour + disp (4 x 2 m) | world triplanar |
| `grass` | leafy_grass, with sparse_grass tufts where its mask is set (2 m) | top-down |
| `nature_soil_moss` | grass_ground (2.51 m), Moss001 (1.5 m) where the procedural ramp is green; flat faces only | top-down |

- **Brightness stays procedural.** The photo is divided by its mean luminance (measured from the
  pixels, logged as `scan mean luminance`) and multiplied by the procedural colour's luminance,
  then mixed in by `*_SCAN_MIX` (0.6). Large tonal zones, strata, stains and patches keep their
  brightness; the photo brings hue and fine structure. `*_SCAN_CONTRAST` (1.0) scales the
  photo's own light and dark: at 0 only its hue is left. Lichen, moss and the per-object tint are
  applied on top. The scan height (rock) or photo luminance (ground) joins the bump chain.
- **Coordinates** are Geometry Position / Normal, world space in the film and in the web bake's
  joined mesh (`bake_web.rewrite_material` redirects object coordinates, not these).
- **Tuning**: module constants `ROCK_SCANS` (files, tiles, relief), `ROCK_SCAN_MIX`,
  `ROCK_SCAN_CONTRAST`, `ROCK_SCAN_BUMP`, `ROCK_SCAN_SHARP`, `ROCK_SMALL_SCAN_SCALE`, `LAWN_*`,
  `GROUND_*`, `MOSS_TILE`. A mistyped override is skipped with a `PATCH WARN skipped argument` line.
- **Missing files**: a builder prints a warning and keeps its procedural look.
- **Patching a saved .blend** (rebuilds each of the five materials in place with its own
  parameters, checks the files, saves; constants can be overridden after `--`):

```
python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
    E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
    --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_nature_look.py [-- ROCK_SCAN_MIX=0.5]
```

## Caching

`get()` caches by name and re-validates, so it survives `look.reset_scene()` and file reloads
(it finds materials by the `sect_material` custom property, datablock name `M.<name>`).
Building all 71 materials and compiling their EEVEE shaders takes about 7 s the first time.
