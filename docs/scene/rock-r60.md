# Round 60: a new base photo for the rock, or marble three times bigger, judged blind

Status on 2026-11-13: run and baked. The mountainside tile (`mtn8`) won the blind stills review, was baked for
production and is in the page's files. A blind test of page screenshots was positive but small, and the owner saw no
difference, so no more rock tuning followed. Results are in "How it ran". The rest of this file is the plan as it
was written before the run.

What was built on the PC before the run:

- `tools/make_rock_tile.py` and its test: a seamless cliff tile cut from Poly Haven's mountainside model skin. Both
  tiles it made pass all 12 of its gates.
- `PHOTO_SWAP=1` in `sect/patch_r59_rock.py`, so a stills copy can read another photo.
- `tools/review_stills.py` and its test: the blind review kit, which builds the reviewers' folders and scores their
  answers against the rule below.
- One line in `assets/CREDITS.md` for the derived tile.
- An Opus check of all of it (same day) looked at the tile, traced the six patch argument strings through the patch's
  own parser, and ran the kit on round 59's stills. Its fixes: reviewer folders get copies instead of hard links, the
  kit refuses a stage 1 score with a reviewer missing and an `answers.json` filed under the wrong folder, the patch
  logs `PATCH PAGE WARN` for any change to `rock_cliff`'s photo, tile or contrast, and the run sheet got an absolute
  log folder, a destroy rule for every exit and the right `big3` patch lines.

Before renting, two things were still open (both were settled before the run: the tile was approved as built):

- The lead approves the tile's seam gate as built ("The seam gate"), or sends the tile back to the tool (decision 7).
  The Opus check saw no seam at 1:1 or at 4 x in colour or height, and a third measure agrees (below), so it
  recommends approving.
- Step 0's folders and its copy of `targets.json` (run sheet) were not made yet.

Results are in "How it ran".

## Why

Round 59 (`rock-r59.md`) tried a rebuilt rock material and real ledges, and neither shipped. In every version, every
reviewer, blind or not, named the same strongest tell: the rock photo's web of small crack cells reads as dried mud or
crazy paving. That round's first lesson was "a better base rock photo first".

The photo is `marble_cliff_06` at an 8.14 m tile. Measured on it:

- Its thin dark cracks join into closed polygon cells 0.41 m across on average (most fall between 0.18 and 0.94 m),
  with about 6.7 m of crack line per square metre. Its darkest 1 % of pixels sit at 0.07 of its mean brightness.
- Almost none of its brightness variation is larger than 1 m (about 1 %; 55 % is finer than 12 cm). A 100 m wall
  shows the same crackle 12 times, plus an 8 m grid where the tile repeats. One dark grime streak per tile makes that
  grid show as columns.

The page draws the same web a second time. `detail.webp`'s R channel is the photo's 12 cm crack web, laid on all rock
out to 150 m at gain 2.0. Its B channel is the photo's 0.12 to 1 m band, drawn from 20 to 500 m
(`client/src/lib/sect/detail.ts:104`, `:140-149`). Round 59's stills were Blender renders and showed neither layer. So
whatever the bake changes, the page has to change with it ("Page work").

## What the mapping found

### The rock textures on disk

Nothing new may be downloaded without the owner, so the round works with what is in
`E:/Github/PortfolioV5/blender/xianxia-sect/assets`. "Clean" below means inside one UV island, clear of the smeared
fill between islands. The seam ratio is the jump across the wrap edge over the step between neighbouring pixels
inside, so about 1 means the image tiles.

| Asset | Kind | Tiles? | Verdict |
|---|---|---|---|
| `marble_cliff_06` (Poly Haven) | texture, 4096 px, 8.14 m square | yes (seam ratio 0.83) | today's photo. Real rock up close; its closed crack web is the tell |
| `Rock063` (ambientCG) | texture, 4096 x 2048, taken as 4 x 2 m | yes (1.14) | a mossy forest ledge with leaves, a fern and white lichen. Tiled, it turns into green stripes every 2 m, and it would trip the page's moss gates. It stays on the undersides (`world_rock_under`) |
| `mountainside` (Poly Haven model) | glTF skin, 83 UV islands, about 252 px a metre at 4k | no (5.4) | the most cliff-like surface on disk: angular cleaved faces running one way, stepped ledges, about 2.0 m of crack per square metre and no closed cells. Against it: dark red-brown (mean brightness 0.115 against marble's 0.239), baked facet shading, a fern and dry grass in parts, lichen. The largest clean square is 2.9 m. The only skin worth cutting a tile from |
| `rock_face_01` | glTF skin, 13 islands | no (8.4) | blue-grey slate with rust. The clean pieces are 1.46 m after a wrap, so an 8 m tile would magnify them 5.6 times |
| `rock_face_02` | glTF skin, 51 islands | no (6.3) | fine layering with bark-like cracks; clean pieces under 1 m |
| `boulder_01` | glTF skin, 146 islands | no (6.8) | reads as a boulder; clean pieces 0.7 m |

Nothing else on disk is rock: the lion statues, two elevation TIFFs, `Moss001` and `Foliage008`.

### How the bake lays the photo on the rock

- `materials._rock_scan` reads `ROCK_SCANS[scan]` through a world triplanar. That is three flat projections on the
  world (y, z), (x, z) and (x, y) planes, each divided by the tile and shifted by its own offset in tiles: (0, 0),
  (0.37, 0.61) and (0.71, 0.13). They are blended by |normal| to the 4th power. On vertical faces 30 to 60 degrees off
  an axis, two copies overlap.
- The photo is divided by its own mean brightness (`scan_mean`), so a darker photo does not darken the rock.
  `_photo_mix` (`ROCK_SCAN_MIX` 0.6, `ROCK_SCAN_CONTRAST` 1.0, `ROCK_SCAN_HUE` 0.55) passes 73 % of the photo's
  brightness variation and a third of its own hue into the albedo. The height map feeds the last Bump: strength
  `ROCK_SCAN_BUMP` 0.4, distance relief x scan scale.
- Which rock tags read which photo:

| Tag | Photo | Tile today |
|---|---|---|
| `rock_cliff`, `world_pier_stone`, `forge_tomb_rock` | `marble_cliff_06` | 8.14 m, relief 0.3 m |
| `nature_rock_small` (its variants `forge_cairn_rock` and `flute_qingshi` too, but no material in the scene carries those two) | `marble_cliff_06` at `ROCK_SMALL_SCAN_SCALE` 0.5 | 4.07 m, relief 0.15 m |
| `world_rock_under` | `rock063` | 4.0 x 2.0 m, relief 0.15 m |

- A patch can override every `ROCK_SCAN_*` constant and the whole `ROCK_SCANS` dict. The override replaces the whole
  dict, so it must list both keys. `rock_cliff` is registered with `scan="marble_cliff_06"` (`materials.py:2358`) and
  every rock variant copies its scan, so one override of the marble key swaps the photo on all six marble tags at once.
- Two things stopped a photo swap in round 59's patch. It refused to save unless `rock_cliff` still read
  `marble_cliff_06_diff.jpg` (its `PHOTO` check). And a scan named only in an override, and missing on the box, would
  have been dropped without a word (`scan_image` returns None). This round's patch change fixes both (below).

### What the page reads

- `detail.webp` is 1024 px, cut by `tools/prep_textures.mjs` from the 4k source. R is the 12 cm high-pass of marble's
  log brightness at 8.14 m. G is leafy grass. B is marble's 0.12 to 1.0 m band, normalised by `bandK` 0.2951. The
  page reads R and B at the bake's own triplanar coordinates (`ROCK_SCAN` in `detail.ts`). R is read a second time,
  turned 36.9 degrees and 3.2 times bigger, at weight 0.5, out to 150 m.
- The marble plazas read R as their slab grain, so a new photo also changes the plazas.
- The moss gates and the stand-in rock gates read the baked colour (`detail.ts:336-363`), so a greener or yellower
  photo would switch them on over plain rock.
- The tests read the code as text. `detail.test.ts` wants the scan name, a square tile, the diff file named after the
  key, prep's sources under `polyhaven/<scan>/`, and `rockMid.gain` 2.0 with its full gain 0.732 / `bandK` near 2.48.
  `tools/test_rock_struct.py` pins marble's tile at (8.14, 8.14). No test reads `detail.webp`'s pixels, so a photo
  swapped only through box overrides passes every page test while the bake shows another photo.
- If a new bake ships with today's `detail.webp`, the page draws marble's crack web out to 150 m and its blotches from
  20 to 500 m over the new rock.

## The variants

One box session renders the same 18 stills for seven tags, each on its own copy of the round 56 scene. Two families
compete. The main bet is a new base photo: a seamless tile cut from the mountainside skin, which has no closed crack
web. The second family keeps `marble_cliff_06` and makes it three times bigger. That is cheap, but the design's
attack showed it keeps the polygon net and brings back a 24 m wallpaper repeat on far rock. A placebo measures how
noisy the reviewers and the brightness gate are.

| Tag | What it is | Patch arguments (after `--`) |
|---|---|---|
| `before` | today's rock. The patch with no override only rebuilds the forge's tomb rock, which is older than today's graph in the shipped file. Every variant's patch rebuilds it too, so the photo is the only difference | none |
| `mtn8` | the main candidate. The mountainside tile from `make_rock_tile.py --flatten 8,1` at gain 1.0, at today's 8.14 m tile (3.67 times its real size) | `PHOTO_SWAP=1 "ROCK_SCANS={'marble_cliff_06': {'diff': 'mtn_cliff_diff.jpg', 'disp': 'mtn_cliff_disp.jpg', 'tile': (8.14, 8.14), 'relief': 0.3}, 'rock063': {'diff': 'rock063_color.jpg', 'disp': 'rock063_disp.jpg', 'tile': (4.0, 2.0), 'relief': 0.15}}"` |
| `mtn8hc` | the same with its log brightness spread 1.35 times wider, against a flat plaster read (taking the light out leaves the tile at 60 % of marble's contrast). It has the same flatten as `mtn8`, so the two differ only in contrast | `PHOTO_SWAP=1 "ROCK_SCANS={'marble_cliff_06': {'diff': 'mtn_cliff_hc_diff.jpg', 'disp': 'mtn_cliff_disp.jpg', 'tile': (8.14, 8.14), 'relief': 0.3}, 'rock063': {'diff': 'rock063_color.jpg', 'disp': 'rock063_disp.jpg', 'tile': (4.0, 2.0), 'relief': 0.15}}"` |
| `mtn12` | `mtn8`'s files at a 12.21 m tile (5.50 times): a wall shows 1.5 times fewer repeats, aimed at `mtn8`'s likeliest failure. It may look coarse in the 20 to 28 m close boxes | `PHOTO_SWAP=1 "ROCK_SCANS={'marble_cliff_06': {'diff': 'mtn_cliff_diff.jpg', 'disp': 'mtn_cliff_disp.jpg', 'tile': (12.21, 12.21), 'relief': 0.45}, 'rock063': {'diff': 'rock063_color.jpg', 'disp': 'rock063_disp.jpg', 'tile': (4.0, 2.0), 'relief': 0.15}}" ROCK_SMALL_SCAN_SCALE=0.33333333` |
| `big3` | the control with no new file: marble at 24.42 m, three times today's tile. Cells grow from 0.41 to about 1.2 m. It answers whether scale alone kills the dried-mud read, and it is the cheapest to ship | `"ROCK_SCANS={'marble_cliff_06': {'diff': 'marble_cliff_06_diff.jpg', 'disp': 'marble_cliff_06_disp.jpg', 'tile': (24.42, 24.42), 'relief': 0.9}, 'rock063': {'diff': 'rock063_color.jpg', 'disp': 'rock063_disp.jpg', 'tile': (4.0, 2.0), 'relief': 0.15}}" ROCK_SMALL_SCAN_SCALE=0.16666667` |
| `big3soft` | `big3` with 30 % less photo contrast and half the photo bump, so the thin dark lines, the block-edge shading and the far repeat all fade | `"ROCK_SCANS={'marble_cliff_06': {'diff': 'marble_cliff_06_diff.jpg', 'disp': 'marble_cliff_06_disp.jpg', 'tile': (24.42, 24.42), 'relief': 0.9}, 'rock063': {'diff': 'rock063_color.jpg', 'disp': 'rock063_disp.jpg', 'tile': (4.0, 2.0), 'relief': 0.15}}" ROCK_SMALL_SCAN_SCALE=0.16666667 ROCK_SCAN_CONTRAST=0.7 ROCK_SCAN_BUMP=0.2` |
| `p830` | the placebo: today's marble at 8.30 m. It looks the same, but the pattern sits elsewhere (at the abode cliff it shifts 0.2 to 0.6 of a tile). It cannot win. It sets the noise floor of stage 1, catches reviewers who pick sides by chance in stage 2, and sets the brightness gate's bar | `"ROCK_SCANS={'marble_cliff_06': {'diff': 'marble_cliff_06_diff.jpg', 'disp': 'marble_cliff_06_disp.jpg', 'tile': (8.3, 8.3), 'relief': 0.3}, 'rock063': {'diff': 'rock063_color.jpg', 'disp': 'rock063_disp.jpg', 'tile': (4.0, 2.0), 'relief': 0.15}}"` |

What each one changes:

- Every variant changes `rock_cliff`, `world_pier_stone` and `forge_tomb_rock` (the marble key at its tile) and
  `nature_rock_small` (the same photo at the tile times `ROCK_SMALL_SCAN_SCALE`). The boulders stay at 4.07 m in
  every variant except the placebo (4.15 m, which is part of the placebo), and their relief stays 0.15 m (relief x
  scale). So on `big3` the boulders do not change at all: same file, tile, relief and contrast, and the patch leaves
  their material alone. `world_rock_under` keeps Rock063, except in `big3soft`: contrast and bump reach every rock tag.
- `PHOTO_SWAP=1` is needed only on the `mtn` tags, where `rock_cliff`'s diff file changes. On `big3`, `big3soft` and
  `p830` the file stays marble, so the patch's usual photo check passes.
- `mtn8hc` does not use `ROCK_SCAN_CONTRAST` above 1: `_photo_mix` extrapolates without a clamp there
  (`materials.py:893`). Its contrast is in the file.
- Relief: the tool measures the tile's whole height range at 0.334 m for the 8.14 m tile (0.091 m of real rock, 3.67
  times). The overrides keep the plan's 0.3, and 0.45 at 12.21 m, where 0.50 would match. So the bump is about 10 %
  softer than the height it came from. A change would be a new constant fixed before the stills.

## The tile (`tools/make_rock_tile.py`)

PC only, with PIL, numpy and scipy. It never runs Blender. It sets its own priority to below normal on Windows, takes
about 10 seconds, and a rerun writes the same bytes (it leaves a file alone when the bytes match). From
`blender/xianxia-sect`:

```
python tools/make_rock_tile.py --flatten 8,1
python tools/make_rock_tile.py --gain 1.35 --name mtn_cliff_hc
```

| Option | Default | Use |
|---|---|---|
| `--assets` | `E:/Github/PortfolioV5/blender/xianxia-sect/assets` | the downloaded sources; `derived/` is written here |
| `--web-out` | this checkout's `assets/web` | the 2048 px box copies (what `rblender.py` uploads) |
| `--out-dir` | this checkout's `out/tmp/r60/tile` | the report and the sheets |
| `--gain` | 1.0 | log contrast gain (1.35 for the `_hc` tile) |
| `--name` | `mtn_cliff` | file stem of the colour tile |
| `--disp-name` | `mtn_cliff` | file stem of the height tile, shared by every gain |
| `--flatten` | `5,0.85` | tile divisor of the flatten's blur, and its strength |

Inputs, under `--assets`: `polyhaven/mountainside/textures/mountainside_diff_4k.jpg` and `mountainside_nor_gl_4k.jpg`,
`polyhaven/mountainside/mountainside_4k.gltf` with its `.bin`, and `marble_cliff_06_diff_4k.jpg` as the reference for
two gates. The crop is fixed in the code (`CROP`): 4k pixels (2432, 1648) to (3136, 2352), 704 px inside one UV island.

What it does, in order:

1. **The mesh in the crop** (`raster_mesh`). It puts the glTF mesh's normals and its metres per pixel into the crop's
   pixels. glTF +Y is up; the tool stops if the mesh node is rotated or scaled. 5,727 triangles cover the whole crop.
2. **The light taken out** (`delight`). It fits log brightness on the mesh normals and divides that out. The fit
   explained 10.1 % of the crop's log brightness before and 0.02 % after. The crop's half-tile gaps fell from 0.41 to
   0.19 stops left to right and from 0.23 to 0.16 top to bottom.
3. **Height from the normal map** (`green_sign`, `height_from_normals`). The green sign with the lower curl residual
   wins: GL 0.89 against DX 1.72, so the map is GL as named (the tool exits 1 otherwise). Frankot-Chellappa integrates
   the crop mirrored into a 2 x 2 block, so the crop's own edges add no ripple. The height is high-passed at tile/5 and
   clamped at the 1st and 99th percentiles.
4. **Which way is up** (`measure_up`, `pick_turn`, `turn`). Real up sits 54.3 degrees clockwise of image up (the median;
   10 % of pixels below 34.1, 10 % above 81.2). One quarter turn counter-clockwise leaves 35.7 degrees, so the beds dip
   about 36 degrees. Colour, height and the mesh normals turn together. The normal map itself is never turned.
5. **The wrap** (`wrap_mincut`). The last 117 px (a sixth) are laid over the first along a min-cut, across and then
   down, leaving a 587 px tile. The second cut is cyclic, so it meets itself across the left-right edge. One cut serves
   colour, height and the mesh normals, found on a guide made of colour and height.
6. **Flatten, green, contrast** (`flatten`, `despeckle_green`, `log_gain`). A wrap-around blur of linear luminance at
   tile/5 and strength 0.85 takes out what is larger than a fifth of the tile (0.44 m of real rock, 1.6 m on an
   8.14 m tile), keeping the mean. Green and grey-green
   pixels are pulled to the local rock hue, ramping in as R/G falls from 1.2 to 1.0, which takes the lichen band too;
   their brightness stays. Then the log spread is scaled by `--gain`. If the repeat score is over marble's, the tool
   tries once more at tile/8 and strength 1.0 and logs `TILE RETRY`.
7. **Enlarge and write** (`upscale_wrap`, `write_box_copy`). Wrap padding and Lanczos to 4096 px, the 4k sources as
   JPEG q95, then the box copies by `prep_textures.mjs`'s rules: an exact 2 x shrink with wrap padding, JPEG q90
   stepping down by 4 to q70 until under 5 MB, 4:2:0, the height as one grey channel.

The tile's 587 px hold 2.22 m of real rock (264.5 px a metre on the mesh), so it carries about 72 px of real detail a
metre at 8.14 m and 48 at 12.21 m. The 4k and 2048 px files are enlargements of it.

| Output | Where |
|---|---|
| 4k sources | `<assets>/derived/mtn_cliff/mtn_cliff_diff_4k.jpg` and `mtn_cliff_disp_4k.jpg`, `<assets>/derived/mtn_cliff_hc/mtn_cliff_hc_diff_4k.jpg` |
| box copies | the worktree's `blender/xianxia-sect/assets/web/mtn_cliff_diff.jpg`, `mtn_cliff_hc_diff.jpg`, `mtn_cliff_disp.jpg` |
| report | `out/tmp/r60/tile/<name>_report.json`: crop, turn and leftover angle, light fit, curl, flatten used, green, colour, bands, `bandK`, seams by both measures, relief in metres, md5s and sizes, every gate |
| sheets | `out/tmp/r60/tile/<name>_2x2.jpg`, `_3x3.jpg`, `_wall60m.jpg` (a 60 m flat wall through an emulation of `materials._photo_mix`), `mtn_cliff_disp_2x2.jpg`, `marble_wall60m.jpg` |

Both `assets/web` and `assets/derived` are git-ignored in both checkouts (`assets/.gitignore` ignores everything but
itself and `CREDITS.md`). The tile is rebuilt from the fixed crop (decision 6).

### Gates (exit 1 if any fails)

| Gate | Limit | `mtn_cliff` (gain 1.0) | `mtn_cliff_hc` (gain 1.35) |
|---|---|---|---|
| normal map reads as GL | curl GL below DX | 0.893 against 1.724 | the same |
| seam, 4k colour (across, down) | 1.2 or less | 1.085, 1.009 | 1.077, 1.012 |
| seam, colour box copy | 1.2 or less | 1.064, 1.035 | 1.082, 1.040 |
| seam, 4k height | 1.2 or less | 1.126, 0.821 | the same file |
| seam, height box copy | 1.2 or less | 1.151, 0.864 | the same file |
| repeat score: std of a tile/4 wrap-around blur of log brightness | marble's 0.0473 or less | 0.0358 | 0.0235 (0.0482 before the retry) |
| half-tile gap, left to right | 0.17 stops or less (marble's) | 0.081 | 0.045 |
| half-tile gap, top to bottom | 0.17 stops or less | -0.002 | 0.021 |
| light fit R2 on the finished tile | 0.02 or less | 0.003 | 0.0068 |
| green share of the colour box copy | under 0.1 % | 0 | 0 |
| colour box copy size | under 5 MB | 0.64 MB | 0.73 MB |
| height box copy size | under 5 MB | 0.30 MB | the same file |

Both runs pass 12 of 12. After them the lead rebuilt the plain tile with the harder flatten
(`python tools/make_rock_tile.py --flatten 8,1`): its repeat score fell from 0.036 to 0.0176 (marble's is 0.0473), its
half-tile gaps to 0.034 and 0.016 stops, and it passes 12 of 12 again. The table's first column is the earlier run.
The box copies' md5s now: `mtn_cliff_diff.jpg` `8f61591f08dfd417f6ac528b292d5f04`,
`mtn_cliff_hc_diff.jpg` `6cfe32354f908b7c1a86e41a02897bf5`, `mtn_cliff_disp.jpg` `f1601c13da05cb88a1ee2f9b2bfc43b9`.

Other numbers from the reports:

- The darkest 1 % of the colour box copy sits at 0.24 of its mean (`_hc`: 0.14). Marble's sits at 0.07, so the
  near-black crack net is gone.
- Total log spread 0.63 stops (`_hc` 0.81), against marble's 1.04.
- Colour over the mean luminance, R, G, B: 1.30, 0.95, 0.59. It is red-brown; a third of that hue reaches the albedo.
- The page's band: `bandK` 0.378 (`_hc` 0.296, marble 0.294). So the page's full gain for B would be 0.732 / 0.378 =
  1.94, under today's `rockMid.gain` 2.0 ("Page work").

### What the builder saw in the sheets

- It reads as ledged, cleaved, bedded cliff rock, with the beds dipping about 36 degrees.
- No closed crack web: only short hairline cracks on the faces.
- No seam at 1:1 on the tile's corner, in colour or height. The height lines up with the colour: correlation 0.186,
  against 0.185 in the raw crop and about 0 when shifted.
- The repeat shows. Each tile has a darker band at its top and a redder band at its bottom, so the 3 x 3 sheet and the
  60 m wall show rows of dark blobs. The gated gap uses the tile's own halves and passes. The worst top-to-bottom gap
  over every split is 0.24 stops, about marble's 0.23. It is a lattice of blobs where marble shows columns, and about
  as easy to spot. The harder flatten weakens it and does not remove it.
- A soft grey lichen patch sits at the left edge of every tile, and one smooth, smeared patch from the source photo
  sits near a corner.

### The seam gate

The plan named the seam gate (1.2) but not its formula. The design's formula divides the step across the wrap edge by
the mean of every neighbouring step in the tile. By it the tile fails across: 4k colour 1.37, colour box copy 1.39, 4k
height 1.48, height box copy 1.52. The builder traced that to a steep patch of rock at the edge, to JPEG steps at the
8 px block edges (about 27 % bigger at q90, and the tile's edge is always a block edge) and to the enlargement's
phase. The step profile through the edge was smooth, with no spike. Today's marble height box copy, made by prep,
scores 1.39 and 2.00 by that formula.

The gate as built (`seam_ratio`) compares the step across the edge with the step pairs 1/64 to 1/16 of the tile in
from each edge, in the same rows; on a JPEG it counts only pairs on the 8 px block grid. Calibration: a clamped
enlargement scores about 5.2, a tile missing one column 1.67, and today's marble height box copy 0.80 and 1.22. The
design's number is still printed and stored in the report (`seams.<file>.global_mean`), ungated. This is the open item
the lead approves before renting.

A third measure, from the Opus check (scratch code, not in the tool): the step across the edge over the mean step at
every 8 px block boundary in the tile, so JPEG block steps sit on both sides. Across, the box copies score 1.19
(colour), 1.23 (`_hc`) and 1.24 (height), and the 4k files 1.21 and 1.20; down, 0.75 to 1.08. About 6 to 8 % of the
block-boundary columns step harder than the edge does, so the edge is a little steep but not an outlier; a real seam
would top them all. Today's marble height box copy scores 1.45 down by the same measure.

### Where the tool departs from the plan

- The second (downward) cut is cyclic. The prototype's was not, and that broke the across seam to 1.46 in colour and
  2.08 in height.
- The height is integrated from the crop mirrored into a 2 x 2 block. Without it the test crop's error is 25 %
  instead of 0.1 %.
- The light-fit gate is measured on the finished tile, with the mesh normals carried through the same turn and cut.
- The gap gate uses the tile's own halves; the worst gap over every split is reported, ungated.
- `--out-dir` and `--disp-name` are extra options.
- **Both tiles use the harder flatten.** At gain 1.35 the `_hc` tile's repeat score was 0.0482, just over marble's, so
  the tool's retry rebuilt it with the harder flatten (blur of tile/8, strength 1.0). The lead then rebuilt the
  plain tile the same way (`--flatten 8,1`, repeat score 0.0176), because the flat 60 m sheet showed less of the
  blob lattice with it. `mtn8` and `mtn8hc` now differ only in contrast.

### Test

`python -P tools/test_make_rock_tile.py` prints `test_make_rock_tile ok` in under a second. Seven checks on synthetic
images: the wrap of a periodic image is seamless, colour and height get the same cut, a sine surface's GL normals
integrate back within 2 %, the curl check picks the right green sign, `flatten` keeps the mean, `log_gain` scales the
spread by its factor, and `turn` moves colour and height by the same step.

## The patch option (`PHOTO_SWAP=1`)

Round 60's changes to `sect/patch_r59_rock.py`. Without `PHOTO_SWAP` it behaves as before, apart from extra log lines
and one new stop.

- `PHOTO_SWAP=1`: the photo check after the rebuild wants the diff file that `ROCK_SCANS` names for `rock_cliff`'s
  scan key, instead of `PHOTO`. The run then logs
  `PATCH PHOTO SWAP rock_cliff reads <file>: detail.webp is cut from marble_cliff_06; do not ship this bake without the page change`.
  A bad key stops before the build: `PATCH NOT SAVED: PHOTO_SWAP: no ROCK_SCANS diff for rock_cliff's scan key (...)`.
- After the overrides, the missing-scan check runs again:
  `PATCH NOT SAVED: after the overrides, scans missing in <SCAN_DIR>: [...]`. It runs with or without `PHOTO_SWAP`, and
  can only stop a run whose `ROCK_SCANS` override names a missing file. Before, that photo was quietly dropped.
- The JSON on the `PATCH round 59 rock: ROCK_STRUCT False; {...}` line now also holds `ROCK_SCANS`,
  `ROCK_SCAN_CONTRAST`, `ROCK_SCAN_BUMP` and `ROCK_SMALL_SCAN_SCALE`.
- After the rebuild it logs `PATCH photo mapping rock_cliff <material>: tile and offsets [...]`. The filter now shows
  tiles up to 50 m (it was about 20 m), so `big3`'s 24.42 m shows.
- Any override that changes `rock_cliff`'s photo, its tile or `ROCK_SCAN_CONTRAST`, with or without `PHOTO_SWAP`, logs
  `PATCH PAGE WARN rock_cliff's photo is <file> at <tile> m, contrast <c>; the page's detail.webp is cut from <file>
  at <tile> m, contrast <c>: do not ship this bake without the page change`. Every variant but `before` prints it,
  `big3` and `big3soft` included: their file is still marble, but the page cuts its layers at 8.14 m and full
  contrast, so a 24.42 m bake would ship out of step with the page just as quietly. It only logs.

The new image loads while the patch builds the asked graph, before its snapshot, so the "no image appeared" check
still passes. It was checked by reading and `py_compile` only. The first box run on a copy is its test.

## The blind review (`tools/review_stills.py`)

PC only, with PIL and numpy. Three commands: `prepare`, `pairs` and `score`. Every number of the rule below is a
constant in the script, fixed before any still is seen, and the key file records them. Run it from
`blender/xianxia-sect`. The kit goes in `out/r60kit`: git-ignored, and outside `out/tmp`, so `rblender.py` does not
upload its JSON files to the box.

### Prepare

```
python -P tools/review_stills.py prepare out/tmp/r60/renders --out out/r60kit --before before --tags mtn8,mtn8hc,mtn12,big3,big3soft --placebo p830 --seed <n> --logs out/tmp/r60/logs
```

Pick `<n>` at that moment. It lands in the key; it is not written here, so a reviewer with the repo cannot rebuild the
shuffles. `prepare` refuses to write over a kit (`--force` builds it again). Stills are read as
`r59_<tag>_<shot>.png`: `preview_r59.py` keeps its own prefix.

It writes:

- `out/r60kit/lead/KEY_do_not_show.json`: which crop and side is which tag, the tables, the windows, the rule's
  numbers.
- `out/r60kit/lead/summary.txt`: what it printed (the counted set, the brightness table and the time table).
- `out/r60kit/lead/crops/<shot>__<tag>.png`: the labelled 1:1 crops, for the lead's own look.
- `out/r60kit/lead/windows/<shot>.jpg`: before at half size, the changed pixels tinted red, the window in yellow.
- `out/r60kit/stage1/r1/` and `r2/`: one folder per stage 1 reviewer, with `README.txt` and
  `answers_template.json`.

No reviewer folder names a tag. Crops are `a.png` to `g.png` in folders `s01`, `s02` and so on, in a shuffle of its
own per reviewer. Every picture is written fresh, without Blender's PNG text (its "File" entry would name the
`.blend`, such as `r60_mtn8.blend`). Reviewer folders hold plain copies of the files under `lead/`, written in
letter order (or A then B), so their dates follow the random letters and sides. They used to be hard links, which
save disk, but a link count shows in `ls -l`, and `before`'s files are linked into more folders than any other tag's
(every stage 2 pair, and twice on the placebo shots), so the count would point at `before`.

The blind rests on the reviewers keeping to their folder. Nothing stops an agent that looks around: `lead/` sits two
levels up, and the stills in `out/tmp/r60/renders` carry their tags in their names. Brief every reviewer to open
nothing outside its folder.

### The counted set

For each of the 18 shots, a change mask of each real variant against `before`: a pixel changed when any channel moves
more than 8 of 255. The five masks are unioned; the placebo's is not in it. One 800 x 450 window (1:1) goes where the
union is densest, the one nearest the frame's centre when several tie. A shot counts when 10 % or more of its window
changed.

- **Close set:** the counted shots among `abode_1380`, `abode_1380_close`, `steles_974_close`, `mirror_217`,
  `mirror_217_close`, `library_772_close`, `forge_352_close`, `mission_619_close` and `arena_516_close`.
- **Far set:** the counted shots among `forge_352`, `library_772`, `steles_974`, `gate_93`, `mission_619`, `arena_516`,
  `scroll_1103`, `formation_1208` and `summit_1647`.

### The tells, used in both stages

| Id | Tell |
|---|---|
| `crack_web` | crack web of any cell size (dried mud, crazy paving, flagstones, crackle, polygon net, the same small pattern printed all over) |
| `repeat` | repeat, grid or wallpaper |
| `plaster` | plaster, smear or blur |
| `ink_lines` | drawn ink lines |
| `wrong_light` | light from the wrong side, or painted shading |
| `masonry` | masonry |
| `tilted_grain` | tilted grain |
| `green_stripes` | green stripes |

### Stage 1, the screen

Start two fresh reviewers (Opus), one per folder. Give each only its folder's path and this brief: follow
`README.txt` in the folder, and do not open anything outside it. For each counted shot a reviewer sees seven
unlabelled crops (before, `p830` and the five real variants). It ranks them 1 to 7 by which reads more like real cliff
rock at this size, with no ties, and ticks every tell it sees on each. It saves `answers.json` in its folder (or
returns the JSON, which the lead saves there). Then:

```
python -P tools/review_stills.py score out/r60kit out/r60kit/stage1/r1 out/r60kit/stage1/r2
```

The rule:

- Ranks are averaged over both reviewers and every counted shot.
- Today's score is the mean of before's and `p830`'s mean ranks. Noise is the gap between those two.
- A real variant advances if its mean rank beats today's by at least max(0.75, 2 x noise).
- Advanced variants go to stage 2 one at a time, best first. The second goes only if the first fails and the second
  is within 0.5 of the best.
- Equal means are ordered by fewer `crack_web` ticks, then fewer other ticks, then `big3soft`, `big3`, `mtn8`,
  `mtn12`, `mtn8hc` (the tie-break below).
- If none advances: stop, no bake.

It prints each tag's mean rank and ticks, today's score, the noise, the bar, who advances and the queue
(`VERDICT stage 1: queue <tag>...` or `VERDICT stage 1: nothing advances`), and writes
`out/r60kit/lead/score_stage1.json`.

### Stage 2, the gate

```
python -P tools/review_stills.py pairs out/r60kit --candidate <tag>
```

It prints the candidate's neutral id `cN` and writes `out/r60kit/stage2/cN/r1`, `r2` and `r3` (`r3` only for a third
reviewer), the stills without PNG text under `lead/full/cN/`, and the key `lead/KEY_stage2_cN.json`. Each counted shot
is one pair: the full 1600 x 900 still plus the same 1:1 crop, A and B as separate files. Mixed in are 4 hidden
placebo pairs: `p830` against before on `abode_1380_close`, `steles_974_close`, `mirror_217_close` and
`library_772_close`. Sides are random for `r1`, flipped for `r2`, and random again for `r3`.

Start two different fresh reviewers on `r1` and `r2`, as in stage 1. For each pair a reviewer answers A, B or same,
and ticks tells on each side. Then:

```
python -P tools/review_stills.py score out/r60kit out/r60kit/stage2/cN/r1 out/r60kit/stage2/cN/r2
```

With N counted pairs, the candidate passes only if all of these hold:

- **(a)** Each reviewer gives it at least ceil(0.6 N) wins, and at least 2.5 times as many wins as losses. "Same" counts
  as neither.
- **(b)** No shot among `abode_1380_close`, `steles_974_close` and `mirror_217_close` is lost with both reviewers.
- **(c)** On the far set, each reviewer gives it at least as many wins as losses. And `repeat` is ticked on it by both
  reviewers in at most 1 far shot where no reviewer ticked `repeat` on before.
- **(d)** `crack_web` ticks on it, summed over the reviewers, are at most half of before's.
- **(e)** No other tell (`repeat` included) is ticked on it by both reviewers in 3 or more shots where no reviewer
  ticked that tell on before.
- **(f)** On every counted close shot, its mean linear luminance over the shot's changed pixels is within
  max(5 %, |`p830`'s deviation over the same pixels| + 2 %) of before's. The pixels are the union mask above, so every
  still of a shot is measured on the same pixels.
- **(g)** Its render seconds on `abode_1380_close`, `steles_974_close` and `mirror_217_close` add up to at most 1.3 times
  before's. The seconds come from the logs' `PREVIEW wrote ... N s` lines, or from the PNGs' RenderTime when the logs
  lack one of the six numbers; one source for the whole gate.
- **(h)** `big3` and `big3soft` only (decision 5): each reviewer gives it more wins than losses on the close set and on
  the far set. An empty set fails.

The placebo and the third reviewer:

- A reviewer who picks a side on 3 or 4 of the 4 placebo pairs is replaced once. If the replacement does too, the
  stage is inconclusive and nothing is baked.
- If the two reviewers split on (a), a third fresh reviewer judges the same pairs in `r3`. Then (a), (b), (c) and (h)
  need two of the three, and "both" in (c) to (e) means two of three.

It prints each item PASS or FAIL and one verdict line, `VERDICT <tag> (cN): ...`, and writes
`lead/score_stage2_cN.json`:

- **PASS:** next is the bake check.
- **FAIL:** if the queue has a second candidate, run `pairs` for it and start stage 2 again.
- **REPLACE:** move that reviewer's `answers.json` out of its folder (to `out/r60kit/lead/answers/`, say), start a fresh
  reviewer on the same folder, and score again with the moved file first:
  `score out/r60kit <moved file> out/r60kit/stage2/cN/r1 out/r60kit/stage2/cN/r2`.
- **INCONCLUSIVE:** nothing is baked.
- **NEED THIRD:** start a fresh reviewer on `stage2/cN/r3` and score again with all three folders.

Exit code 2 means a bad answers file. The message lists every problem, so the reviewer can be asked to fix it.

Where the rule was unclear, the kit chose: "where before has no such tick" means no reviewer ticked it on before; (e)
covers every tell but `crack_web`, so it includes `repeat`; with fewer than 4 placebo pairs, a reviewer is replaced at
ceil(0.75 x pairs) picks.

### The bake check, the last gate

The passing candidate's dev test bake of the abode and the steles
(`out/r60look_<tag>/bake/verify/hold_1380.png` and `hold_974.png`) is compared with
`out/r59look/bake/verify/hold_1380.png` and `hold_974.png`: today's material with the texel floor, on the same scene.
One fresh reviewer (Opus) sees each pair blind as A and B, with 1:1 and 2 x crops of the cliffs, and the lead looks
too. It fails if it loses both renders, or shows a crack web, grid or light blotch at the texel scale that today's
lacks. If it fails, the next advanced candidate gets stage 2 and its own test bake, if one is left; otherwise there is
no bake. `review_stills.py` does not build this pair: the lead cuts the crops at the same boxes on both renders and
names the sides at random.

### Tie-break and no winner

When two candidates end up equal on the evidence: fewer `crack_web` ticks first, then fewer other tells, then `big3`
or `big3soft` over `mtn` (they need no derived asset), and within a family `mtn8` over `mtn12` over `mtn8hc`, and
`big3soft` over `big3`.

If nothing passes: no bake, and marble stays. Write it up here. The next rock round then needs either a tile
synthesised from several mountainside islands or a new photo the owner approves.

### Test, and a try on round 59's stills

`python -P tools/test_review_stills.py` prints `test_review_stills ok (... s)` in about 2 seconds. On synthetic stills it checks the
mask threshold (8 is not a change, 9 is), window placement, log parsing (CRLF, retried runs, the first still of a
run), the RenderTime fallback, the counted set, brightness, the 1:1 crops, the seeded shuffles, the stripped PNG text,
file dates, plain copies with no second link, stage 1's bar, noise and queue, a stage 1 score with one reviewer
missing (refused), an `answers.json` whose `"kit"` names another folder (refused), the side flips, and every stage 2
item with REPLACE, INCONCLUSIVE and NEED THIRD.

The kit also ran on round 59's stills, with `after` and `after3` as variants, `after2` standing in for the placebo,
and seed 59. `prepare` took 5.6 s and counted 13 of 18 shots: 9 close and 4 far. It left out `steles_974` (6.9 % of
its window changed), `mission_619` (8.5 %), `gate_93` (9.1 %), `scroll_1103` (1.5 %) and `summit_1647` (2.3 %). Two
window previews were checked by eye, and the windows sat on the changed rock. `pairs` built 13 counted pairs and 4
placebo pairs. Dummy answers (not a review) scored on both stages. The try took 383 MB with plain copies (93 MB with
the hard links it first used). Round 60's kit, with seven tags and about 16 counted shots, should take under 1 GB.

The Opus check ran it again (seed 7) with made-up answers whose outcome it worked out by hand first. Stage 1 gave
the expected means (1.00, 2.50, 3.00, 3.50), noise 1.00, bar 2.00 and queue. Stage 2 gave the expected wins and
losses and items (a) to (e), and failed `after` on (f) at `steles_974_close` (+75.4 % against a bar of 75.0 %, set
by round 59's `after2`, which is not a real placebo). Three placebo picks gave REPLACE. A file with a duplicate
letter, a tell for a missing letter, a missing pair, a pick "C" or the tell "mud" exits 2 with every problem
listed. No reviewer file had a tag in its name or text, PNG text, or a second link. Two fixes came out of it:
`score` now refuses stage 1 with one reviewer missing (it used to warn and still print a verdict), and refuses an
`answers.json` whose `"kit"` names another folder than the one it sits in.

## Run sheet

One list, top to bottom. Each box step gives its minutes and its cost at 0.81 US dollars an hour (1.35 cents a minute;
round 59's box cost 0.694). Never run Blender on the PC. The run sheet carries `PIPELINE_CHANGED_OK=1` (`spec.md`):
round 59's `bake_web.py` and `bake_rules.py` changes (the texel floor and its refit) have not shipped in a bake yet.

Git Bash, at the worktree root `E:/Github/PortfolioV5/.claude/worktrees/saltline-game-architecture-ae3e16`:

```
set -o pipefail
RB="python E:/Github/PortfolioV5/.claude/worktrees/saltline-game-architecture-ae3e16/blender/xianxia-sect/tools/rblender.py"
P=E:/Github/PortfolioV5/blender/xianxia-sect
L=E:/Github/PortfolioV5/.claude/worktrees/saltline-game-architecture-ae3e16/blender/xianxia-sect/out/tmp/r60/logs
```

`L` is absolute because steps 0 and 6 run from `blender/xianxia-sect` and the rest from the worktree root: a relative
`L` would make `tee` lose a log without stopping anything.

**Every exit destroys the box.** Destroy the instance `vast_rent.py` printed (in the Vast console or CLI) and confirm
the instance list is empty, whenever the session ends: after step 9, after P5, and at any stop this sheet does not
cover. That includes `before` or `p830` stopping twice in steps 4 and 5 (the review needs both), a P1 digest that does
not match step 5's, a P2 diff other than 0, and a production bake that stops. Sort the cause out on the PC
afterwards; the box bills by the minute.

`$RB` sends this branch's `sect/`, `docs/`, `assets/web/` (only files whose md5 differs) and the small text files
under `out/tmp/` to the box, and runs Blender 5.2.2 there. `$P` is the path the box uses after `-b` and `--python`:
the box keeps the project at the main checkout's path. What a run writes under `out/` comes back to the worktree's
`blender/xianxia-sect/out/` (a `.blend` only with `--fetch-blend`). Pipe every Blender call through
`2>&1 | tee $L/<step>.log`: gate (g) and the retry rule read these logs. Name them `.log`: `rblender.py` uploads
`.txt` files under `out/tmp` to the box on every run, and the kit reads both.

0. **PC, no box.** From `blender/xianxia-sect`, one at a time:
   ```
   python -m py_compile sect/patch_r59_rock.py tools/make_rock_tile.py tools/review_stills.py
   python -P tools/test_make_rock_tile.py
   python -P tools/test_review_stills.py
   python -P tools/test_rock_struct.py
   python -P tools/test_bake_rules.py
   python -P tools/test_relief_rules.py
   python tools/make_rock_tile.py --flatten 8,1
   python tools/make_rock_tile.py --gain 1.35 --name mtn_cliff_hc
   mkdir -p out/tmp/r60/renders out/tmp/r60/logs
   cp out/tmp/r59/renders/targets.json out/tmp/r60/renders/
   md5sum assets/web/mtn_cliff_diff.jpg assets/web/mtn_cliff_hc_diff.jpg assets/web/mtn_cliff_disp.jpg
   ```
   The tests print `test_make_rock_tile ok`, `test_review_stills ok (... s)`, `test_rock_struct ok`,
   `test_bake_rules ok` and `test_relief_rules ok`. Each tile run ends `TILE 12 of 12 gates pass`; the `_hc` run also
   prints a `TILE RETRY` line. The md5s are the three above. Look at the sheets in `out/tmp/r60/tile` at full size.
   `targets.json` holds round 59's 7 close boxes (`abode_1380`, `arena_516`, `forge_352`, `library_772`, `mirror_217`,
   `mission_619`, `steles_974`), so every round 60 still frames round 59's rock. Gate: a failed tile gate means no
   renting; the tile is fixed first (decision 7).

1. **Rent and set up (15 min, 0.20 dollars).** One RTX 5090; skip host 366851; 346497 was fast.
   ```
   python blender/xianxia-sect/tools/box/vast_rent.py <offer id> r60
   bash blender/xianxia-sect/tools/box/box_up.sh <host> <port>
   ```
   `vast_rent.py` reads `VAST_API_KEY` from the environment and prints the instance id. `box_up.sh` writes
   `tools/remote.json`, starts the box's setup, uploads the round 56 scene with its caches, the camera and the fonts,
   and prints the scene's md5 and the end of the setup log. Gates: the setup log ends with `cuda init ok` and
   `SETUP_OK`;
   `$RB --sh "python3 -c \"import ctypes; print(ctypes.CDLL('libcuda.so.1').cuInit(0))\""` prints 0 (for 804, see
   `rock-r59.md` step 1); `$RB --sh "nvidia-smi"` names the RTX 5090;
   `$RB --sh "md5sum out/sect_chase.blend"` prints `03b2fd96917412d869129f1da0605a71`. Otherwise destroy the box and
   rent another.

2. **Inspect, keep-list and upload check (5 min, 0.07 dollars).**
   ```
   $RB -b $P/out/sect_chase.blend --python-exit-code 1 --python $P/sect/patch_r59_rock.py -- MODE=inspect 2>&1 | tee $L/02_inspect.log
   $RB -b $P/out/sect_chase.blend --python-exit-code 1 --python $P/sect/patch_r48_keep.py -- MODE=dump LABEL=r60_before 2>&1 | tee $L/02_keep.log
   $RB --sh "md5sum assets/web/mtn_cliff_diff.jpg assets/web/mtn_cliff_hc_diff.jpg assets/web/mtn_cliff_disp.jpg out/tmp/r60/renders/targets.json"
   ```
   Inspect: `PATCH INSPECT rock_cliff M.rock_cliff: ... equals today's graph` with tile and offsets
   `(8.14, 8.14, 0.0, 0.0), (8.14, 8.14, 0.37, 0.61), (8.14, 8.14, 0.71, 0.13)`, and `equals today's graph` for
   `world_rock_under`, `nature_rock_small` and `world_pier_stone`. `forge_tomb_rock` says `equals neither`
   (expected). Then `PATCH inspect done`. Keep-list: `PATCH KEEP dump: 4844 location objects`;
   `out/tmp/r48/keep_r60_before.json` comes back to the PC and P2 sends it back. It is only used if production
   follows, which decision 1 allows. The first Blender run uploads `assets/web` and `out/tmp/r60/renders/targets.json`,
   so the md5s must match the PC's.

3. **Seven copies (1 min, 0.01 dollars).** Single quotes, so `$t` expands on the box:
   ```
   $RB --sh 'for t in before mtn8 mtn8hc mtn12 big3 big3soft p830; do cp out/sect_chase.blend out/r60_$t.blend; done'
   $RB --sh 'ls -la out/r60_*.blend'
   ```
   Seven files of about 178 MB.

4. **Before (7 min, 0.09 dollars).** The patch with no override, then the stills:
   ```
   $RB -b $P/out/r60_before.blend --python-exit-code 1 --python $P/sect/patch_r59_rock.py 2>&1 | tee $L/04_before_patch.log
   $RB -b $P/out/r60_before.blend --python-exit-code 1 --python $P/sect/preview_r59.py -- --tag before --out $P/out/tmp/r60/renders 2>&1 | tee $L/04_before_stills.log
   ```
   Patch: `PATCH round 59 rock: ROCK_STRUCT False; {...}` with today's `ROCK_SCANS`; `forge_tomb_rock` `differs`, then
   `forge_tomb_rock: expected, no earlier patch rebuilt it (STALE_OK)`; every other tag `old (as asked)`; one
   `PATCH forge_tomb_rock rebuilt ...` line and no other `rebuilt`; `PATCH photo mapping rock_cliff ...` with the three
   8.14 m entries; `PATCH objects N, unchanged N` (the same N); `PATCH DIGEST <md5>`; `PATCH saved ...`. Stills:
   `PREVIEW cycles device OPTIX ...`; `PREVIEW close boxes from E:/Github/PortfolioV5/blender/xianxia-sect/out/tmp/r60/renders/targets.json`
   with the 7 names; 18 `PREVIEW wrote` lines; `PREVIEW done 18 stills; the .blend was not saved`. Never pass
   `--retarget`: the stills must frame round 59's boxes.

5. **Six variants (about 7 min each, 42 min, 0.57 dollars).** In this order, the patch and then the stills:
   ```
   $RB -b $P/out/r60_mtn8.blend --python-exit-code 1 --python $P/sect/patch_r59_rock.py -- PHOTO_SWAP=1 "ROCK_SCANS={'marble_cliff_06': {'diff': 'mtn_cliff_diff.jpg', 'disp': 'mtn_cliff_disp.jpg', 'tile': (8.14, 8.14), 'relief': 0.3}, 'rock063': {'diff': 'rock063_color.jpg', 'disp': 'rock063_disp.jpg', 'tile': (4.0, 2.0), 'relief': 0.15}}" 2>&1 | tee $L/05_mtn8_patch.log
   $RB -b $P/out/r60_mtn8.blend --python-exit-code 1 --python $P/sect/preview_r59.py -- --tag mtn8 --out $P/out/tmp/r60/renders 2>&1 | tee $L/05_mtn8_stills.log
   $RB -b $P/out/r60_mtn8hc.blend --python-exit-code 1 --python $P/sect/patch_r59_rock.py -- PHOTO_SWAP=1 "ROCK_SCANS={'marble_cliff_06': {'diff': 'mtn_cliff_hc_diff.jpg', 'disp': 'mtn_cliff_disp.jpg', 'tile': (8.14, 8.14), 'relief': 0.3}, 'rock063': {'diff': 'rock063_color.jpg', 'disp': 'rock063_disp.jpg', 'tile': (4.0, 2.0), 'relief': 0.15}}" 2>&1 | tee $L/05_mtn8hc_patch.log
   $RB -b $P/out/r60_mtn8hc.blend --python-exit-code 1 --python $P/sect/preview_r59.py -- --tag mtn8hc --out $P/out/tmp/r60/renders 2>&1 | tee $L/05_mtn8hc_stills.log
   $RB -b $P/out/r60_mtn12.blend --python-exit-code 1 --python $P/sect/patch_r59_rock.py -- PHOTO_SWAP=1 "ROCK_SCANS={'marble_cliff_06': {'diff': 'mtn_cliff_diff.jpg', 'disp': 'mtn_cliff_disp.jpg', 'tile': (12.21, 12.21), 'relief': 0.45}, 'rock063': {'diff': 'rock063_color.jpg', 'disp': 'rock063_disp.jpg', 'tile': (4.0, 2.0), 'relief': 0.15}}" ROCK_SMALL_SCAN_SCALE=0.33333333 2>&1 | tee $L/05_mtn12_patch.log
   $RB -b $P/out/r60_mtn12.blend --python-exit-code 1 --python $P/sect/preview_r59.py -- --tag mtn12 --out $P/out/tmp/r60/renders 2>&1 | tee $L/05_mtn12_stills.log
   $RB -b $P/out/r60_big3.blend --python-exit-code 1 --python $P/sect/patch_r59_rock.py -- "ROCK_SCANS={'marble_cliff_06': {'diff': 'marble_cliff_06_diff.jpg', 'disp': 'marble_cliff_06_disp.jpg', 'tile': (24.42, 24.42), 'relief': 0.9}, 'rock063': {'diff': 'rock063_color.jpg', 'disp': 'rock063_disp.jpg', 'tile': (4.0, 2.0), 'relief': 0.15}}" ROCK_SMALL_SCAN_SCALE=0.16666667 2>&1 | tee $L/05_big3_patch.log
   $RB -b $P/out/r60_big3.blend --python-exit-code 1 --python $P/sect/preview_r59.py -- --tag big3 --out $P/out/tmp/r60/renders 2>&1 | tee $L/05_big3_stills.log
   $RB -b $P/out/r60_big3soft.blend --python-exit-code 1 --python $P/sect/patch_r59_rock.py -- "ROCK_SCANS={'marble_cliff_06': {'diff': 'marble_cliff_06_diff.jpg', 'disp': 'marble_cliff_06_disp.jpg', 'tile': (24.42, 24.42), 'relief': 0.9}, 'rock063': {'diff': 'rock063_color.jpg', 'disp': 'rock063_disp.jpg', 'tile': (4.0, 2.0), 'relief': 0.15}}" ROCK_SMALL_SCAN_SCALE=0.16666667 ROCK_SCAN_CONTRAST=0.7 ROCK_SCAN_BUMP=0.2 2>&1 | tee $L/05_big3soft_patch.log
   $RB -b $P/out/r60_big3soft.blend --python-exit-code 1 --python $P/sect/preview_r59.py -- --tag big3soft --out $P/out/tmp/r60/renders 2>&1 | tee $L/05_big3soft_stills.log
   $RB -b $P/out/r60_p830.blend --python-exit-code 1 --python $P/sect/patch_r59_rock.py -- "ROCK_SCANS={'marble_cliff_06': {'diff': 'marble_cliff_06_diff.jpg', 'disp': 'marble_cliff_06_disp.jpg', 'tile': (8.3, 8.3), 'relief': 0.3}, 'rock063': {'diff': 'rock063_color.jpg', 'disp': 'rock063_disp.jpg', 'tile': (4.0, 2.0), 'relief': 0.15}}" 2>&1 | tee $L/05_p830_patch.log
   $RB -b $P/out/r60_p830.blend --python-exit-code 1 --python $P/sect/preview_r59.py -- --tag p830 --out $P/out/tmp/r60/renders 2>&1 | tee $L/05_p830_stills.log
   ```
   Patch log gates, each run:
   - `PATCH override ROCK_SCANS = {...}` with the variant's files and tile (and one `override` line per other
     constant).
   - `PATCH state rock_cliff: M.rock_cliff old`.
   - `rebuilt` lines for `rock_cliff`, `world_pier_stone` and `forge_tomb_rock`, and for `nature_rock_small` on every
     tag but `big3`. On `big3` the boulders keep a 4.07 m tile and 0.15 m relief (24.42 x 0.16666667, 0.9 x
     0.16666667), so their graph equals today's to the fingerprint's 4 decimals: `state nature_rock_small: ... old
     (as asked)` and no `rebuilt` line is right there. `world_rock_under` is rebuilt on `big3soft` only. On the `mtn`
     tags the images listed are the `mtn_cliff` files.
   - On the `mtn` tags only: `PATCH PHOTO SWAP rock_cliff reads mtn_cliff_diff.jpg: ...` (`mtn_cliff_hc_diff.jpg` on
     `mtn8hc`).
   - On every variant: `PATCH PAGE WARN rock_cliff's photo is ...` naming the variant's file, tile and contrast.
   - `PATCH photo mapping rock_cliff ...` with the new tile: 8.14 on `mtn8` and `mtn8hc`, 12.21 on `mtn12`, 24.42 on
     `big3` and `big3soft`, 8.3 on `p830`.
   - `PATCH objects N, unchanged N`, `PATCH DIGEST <md5>` and `PATCH saved ...`. Keep each digest: P1 checks it.

   The stills logs as in step 4. A stop gets one retry. A stopped patch saves nothing, so run it again; if it is in
   doubt whether the copy was saved, make a fresh one first (`$RB --sh 'cp out/sect_chase.blend out/r60_<tag>.blend'`).
   A stop in the stills needs only the stills again. Give a retry its own log name (`..._2.log`): the kit takes the
   last `PREVIEW wrote` line for a still. Round 59 had two first-try stops. Never `FORCE=1`. A real variant that stops
   twice drops out: leave its tag out of `--tags` in step 6 (`prepare` leaves out every shot that lacks a still for a
   tag it is given). `before` or `p830` stopping twice ends the session (destroy).

6. **Prepare and stage 1 (2 min of box idle, 0.03 dollars).** The stills came back with each run. From
   `blender/xianxia-sect`, `ls out/tmp/r60/renders/*.png | wc -l` must print 126 (7 tags x 18 shots). Then the
   `prepare` command above. Read its counted set, its brightness table (an `!` marks a still over the bar) and its time
   table (`OVER` marks a tag over 1.3 times). Start the two stage 1 reviewers.

7. **While stage 1 runs, a test bake of `mtn8` (8 min, 0.11 dollars).** It is the likeliest leader.
   ```
   $RB -b $P/out/r60_mtn8.blend --python-exit-code 1 --python $P/sect/bake_web.py -- bakefull --profile full --quality dev --chunks abode,steles --out-dir r60look_mtn8 2>&1 | tee $L/07_bake_mtn8.log
   $RB --background --factory-startup --python-exit-code 1 --python $P/sect/bake_web.py -- verify --profile full --chunks abode,steles --out-dir r60look_mtn8 --ref-frames 1380,974 2>&1 | tee $L/07_verify_mtn8.log
   ```
   Look for `BAKE rock floor on`, `BAKE relief off` and `BAKE cycles device OPTIX`, and run `$RB --sh "nvidia-smi"`
   within 3 minutes to see the GPU busy. Then two `BAKE CHUNK DONE` lines (round 59: abode 143 s, steles 252 s). The
   renders come back as `out/r60look_mtn8/bake/verify/hold_1380.png` and `hold_974.png`.

8. **When stage 1 names the leader (8 min, 0.11 dollars, plus about 15 min of box idle, 0.20 dollars).** If the
   leader is not `mtn8`, run step 7's two commands for it, with `r60_<tag>.blend` and `--out-dir r60look_<tag>`.
   Stage 2 runs on the PC meanwhile (`pairs`, two reviewers, `score`), then the bake check.

9. **Decide (1 to 2 min, 0.03 dollars).** If a candidate passes stage 2 and the bake check, go on to P1 in the same
   session (decision 1). Otherwise destroy the box and confirm the instance list is empty. The stills session comes to
   about 15 + 5 + 1 + 7 + 42 + 2 + 8 + 8 + 15 + 2 = 105 box minutes. Reviewer time is box time: a slow stage costs
   1.35 cents a minute.

P1. **The main file (6 min, 0.08 dollars).**
   ```
   $RB --fetch-blend -b $P/out/sect_chase.blend --python-exit-code 1 --python $P/sect/patch_r59_rock.py -- <the winner's exact arguments from step 5> 2>&1 | tee $L/P1_patch_main.log
   ```
   The repo's `materials.py` still says marble, so the states read `old` and no `FORCE` is needed. `PATCH DIGEST` must
   equal the winner's from step 5; if it does not, destroy and stop. The patched file comes back as the worktree's
   `blender/xianxia-sect/out/sect_chase.blend`: copy it to `out/sect_chase.r60.blend` and note its md5.
   The log says `PATCH PAGE WARN ...` (and `PATCH PHOTO SWAP ...` for an `mtn` winner). From here on, this file and
   everything baked from it carry rock the page's `detail.webp` does not match. Nothing from P3 to P5 is packed,
   committed or pushed until the page work below is done and passes its own gate. No code enforces that: this line
   and the patch log are the only guard.

P2. **Keep-list compare (2 min, 0.03 dollars).**
   ```
   $RB -b $P/out/sect_chase.blend --python-exit-code 1 --python $P/sect/patch_r48_keep.py -- MODE=compare LABEL=r60_after REF=out/tmp/r48/keep_r60_before.json 2>&1 | tee $L/P2_keep.log
   ```
   It must print `PATCH KEEP diff 0`. Any other number: the patch touched an object, which it must not; do not bake
   this file, destroy the box and stop.

P3. **Production bake (145 min, 1.96 dollars).**
   ```
   $RB -b $P/out/sect_chase.blend --python-exit-code 1 --python $P/sect/bake_web.py -- bakefull --profile full --quality production --live --chunks gate,mirror,forge,arena,mission,library,steles,scroll,formation,abode,summit,backdrop 2>&1 | tee $L/P3_bake.log
   ```
   First lines: `BAKE rock floor on` and `BAKE relief off`, then `BAKE cycles device OPTIX`. Run
   `$RB --sh "nvidia-smi"` within 3 minutes of the first chunk. If `BAKE gate baked atlases in N s` passes 600 s, the
   host is slow: stop, destroy, re-rent and run steps 1, P1, P2 and P3 again (the stills results stay valid). Each
   chunk logs its `ROCK FLOOR` line, and `ROCK FLOOR refit` where it needs one (round 59's steles did). The texel floor
   ships with this bake.

P4. **Live maps (10 min, 0.14 dollars).** As `rock-r59.md` step 14:
   ```
   for c in gate mirror forge arena mission library steles scroll formation abode summit; do $RB --background --python-exit-code 1 --python $P/sect/live_calib.py -- $c; done 2>&1 | tee $L/P4_calib.log
   $RB --background --python-exit-code 1 --python $P/sect/live_bounce.py -- gate mirror forge arena mission library steles scroll formation abode summit 2>&1 | tee $L/P4_bounce.log
   ```
   Each `live_calib` run prints its share, about 0.318 (`docs/sect/live-gate.md`).

P5. **Fetch, check and destroy (10 min, 0.14 dollars).** Check the raw GLBs with
   `$RB --sh "md5sum out/web/full/raw/*.glb"` against the PC's copies, and pull anything missing with
   `$RB --pull <path>`. Destroy the box and confirm the instance list is empty. Production comes to about 173 box
   minutes.

Then the page work below, on the PC.

## The lead's decisions on the open questions (2026-11-12)

1. **Bake in the same session?** Yes. If every gate passes, the production bake (P1 to P5) runs in the same box
   session. That saves about 15 minutes of setup and a second rental.
2. **The plazas.** Both families change what the marble plazas read from `detail.webp` R. Their slab grain is judged
   on the GPU after the bake ("Page work"). If it fails, paving gets its own copy of today's marble fine layer.
3. **A page trial before the bake?** No. The page is first judged after the bake.
4. **The tile's tilt.** The turned tile keeps about 36 degrees of tilt. It is accepted, and the blind review judges it
   (the `tilted_grain` tell).
5. **A 24 m repeat on far rock.** `big3` or `big3soft` ships only if it wins both the close and the far set. That is
   item (h) of stage 2.
6. **Where the derived tile lives.** It stays git-ignored, and `make_rock_tile.py` rebuilds it from its fixed crop.
7. **If the tile fails its seam or repeat gates.** It is fixed before any renting. It passes all 12 gates now, with
   the seam formula as built still to be approved ("The seam gate").
8. **Reviewer budget.** Fine: about 5 to 7 Opus reviewers in all (2 in stage 1, 2 to 4 in stage 2, 1 for the bake
   check).

## Page work if a variant wins

Only after a variant passes every gate and the production bake is fetched. The bake and the page ship in one commit:
if a new bake ships with today's `detail.ts` and `detail.webp`, the page draws marble's R crack web out to 150 m and
its B blotches from 20 to 500 m over the new rock (`detail.ts:104`, `:140-149`). Line numbers are as of 2026-11-12.

**If an `mtn` variant won:**

- The repo must build the same graph the shipped file holds, or later patches read the file as `differs`. The
  patch's fingerprint names images by file name, so the repo key must name the files P1 used.
- `mtn8` or `mtn12`: in `materials.py`, add `ROCK_SCANS` key `mtn_cliff=dict(diff="mtn_cliff_diff.jpg",
  disp="mtn_cliff_disp.jpg", tile=(T, T), relief=R)` with T = 8.14 and R = 0.3 for `mtn8`, or T = 12.21 and R = 0.45
  for `mtn12`. Keep the marble entry.
- `mtn8hc`: the plan said to rebuild its tile under the `mtn_cliff` name. That would rename the image the shipped file
  reads (`mtn_cliff_hc_diff.jpg`), so the repo build would differ from the file. Keep its own name instead: key
  `mtn_cliff_hc=dict(diff="mtn_cliff_hc_diff.jpg", disp="mtn_cliff_disp.jpg", tile=(8.14, 8.14), relief=0.3)`. Below,
  read `mtn_cliff_hc` for the scan name and the colour files; the height stays `mtn_cliff_disp`. The page test's
  pattern (`<scan>_diff.jpg`) still holds. This is a change from the plan, for the lead to confirm.
- `materials.py:2358`: `R("rock_cliff", _rock, scan="mtn_cliff")`. For `mtn12` also `ROCK_SMALL_SCAN_SCALE =
  0.33333333` (`:60`).
- The comment at `nature.py:414`.
- `patch_r59_rock.py`: `PHOTO = "mtn_cliff_diff.jpg"` (or the `_hc` file).
- `tools/test_rock_struct.py:77`: assert the new key's tile too.

**If `big3` or `big3soft` won:**

- `materials.py:49-50`: marble's tile (24.42, 24.42) and relief 0.9. `:60`: `ROCK_SMALL_SCAN_SCALE = 0.16666667`.
- `big3soft` also: `:54` `ROCK_SCAN_CONTRAST = 0.7` and `:58` `ROCK_SCAN_BUMP = 0.2`.
- `tools/test_rock_struct.py:77`: the new tile.

**`tools/prep_textures.mjs`:**

- `mtn`: `JPGS` entries for the `derived/mtn_cliff/*_4k.jpg` files (`:86-96`), so later bakes rebuild the box copies
  by the usual route. Point the DETAIL R and B `src` at `derived/mtn_cliff/mtn_cliff_diff_4k.jpg` and set their
  `tileM` (`:116`, `:118`). The copies prep makes are not byte for byte the ones `make_rock_tile.py` wrote and the
  round 60 bake read: the diff's 1 / mean brightness (as PIL reads it) is 9.0877 against 9.0889, and
  `patch_r59_rock.py`'s fingerprint keeps 4 decimals. To match a file baked from the round 60 copies, rebuild them
  with `make_rock_tile.py --flatten 8,1`.
- `big3`: `tileM` 24.42 only. `big3soft`: also `BAKE_SCAN_SHARE` (`:112`) times the contrast, 0.512.
- A new `--keep-g` option: `--keep-rg` throws when R changes.
- Rebuild `detail.webp` in the worktree only:
  `node blender/xianxia-sect/tools/prep_textures.mjs E:/Github/PortfolioV5/blender/xianxia-sect/assets E:/Github/PortfolioV5/.claude/worktrees/saltline-game-architecture-ae3e16/blender/xianxia-sect/out/web/full/site/detail.webp --detail-only`.
  Never use the main checkout's stale copy (hash `c6d13f278c9a313e`).

**`client/src/lib/sect/detail.ts`:**

- `ROCK_SCAN.scan` (`:57`), `tileM` (`:58`), and `bandK` (`:66`) from prep's new print.
- A rock-only second-layer setting (for example `DETAIL_LOOK.rockLayer2`), used at `:1162` when the kind is rock.
  `layer2` (`:226`) is shared with the ground and the paving and stays as it is for them. For `mtn`: angle 0, because a
  copy turned 36.9 degrees of a one-way grain draws crossed grain out to 150 m. For `big3`: weight 0, because the
  second copy would become a 78 m crackle.

**`client/src/lib/sect/detail.test.ts`:**

- `:68`, the tile literal, if T changes.
- `:936-952`: allow a `derived/<scan>/` path beside `polyhaven/`.
- `:961-962`: the `BAKE_SCAN_SHARE` text, with the contrast for `big3soft`.
- `:965-974`: the gain pin. Loosen it to 0 <= gain <= full, so the GPU look can pick a low gain or 0. (`mtn8`'s full
  gain is 1.84 by prep's print, `bandK` 0.3985, under today's 2.0.)
- `:1017-1024` and the read counts at `:152-167`, if the rock's second layer changes or is skipped.
- Then `pnpm lint`, `pnpm typecheck` and `pnpm test` in `client/`, at limited parallelism.

**The plazas** (decision 2). Paving reads R as slab grain (`detail.ts:1088-1098`). With `mtn` the plazas get cleaved
rock grain; with `big3` the grain mostly goes and hairlines stay. Look at them on the GPU. If they fail, paving gets
its own copy of today's marble fine layer.

**Pack** on the PC from the worktree, at below-normal priority: `python blender/xianxia-sect/tools/sect_live.py --chunk
<id>` for the eleven areas, then `python blender/xianxia-sect/tools/sect_pack.py --profile full --workers 2`. That
updates `manifest.json`'s rev (`manifest-rev.test.ts:33-61`).

**GPU look** at round 58's six cliffs (the abode's near cliff, the library spire, the steles pillar, the summit spire,
the gate's shaded cliff, the mirror's cliff). The texel floor bakes in the same run, so `rock-r59.md`'s page item 5 is
judged here too.

- `rockMid.gain` (`:141`): try 0, 0.5 x full and 0.8 x full, with full = 0.732 / the new `bandK`.
- `DETAIL_LOOK.rock.gain` (`:104`): try 2.0, 1.0, 0.5 and 0. For `mtn`, R sharpens enlarged data, so expect about 1.0.
- The rock second layer's weight: 0 or 0.5.
- The moss gates (`greenRock` hue 0.72 to 0.92, `rockMid.mossHue`) and the stand-in rock gates, which read the baked
  colour (`detail.ts:336-363`).

**The last page gate:** a blind A/B of page screenshots at the eleven holds, the live site against the local build,
with stage 2's counting rule. If it fails, do not ship. The old atlases stay live, and only the bake money is lost.

**Docs in the same commit:** this page (results), `docs/sect/surfaces.md` (what `detail.webp`'s channels hold now),
`assets/CREDITS.md` (done), and a dated entry in `docs/decisions/`.

## Cost

| Part | Box minutes | At 0.70 dollars an hour | At 0.81 dollars an hour |
|---|---|---|---|
| Stills session (steps 1 to 9) | about 105 | 1.23 | 1.42 |
| Production (P1 to P5) | about 173 | 2.02 | 2.34 |
| Both in one session (decision 1) | about 278 | 3.24 | 3.75 |

The credit stood at 9.70 dollars after round 59. A variant retry adds about 7 minutes (0.09 dollars). A slow host in
P3 adds a new rental plus P1 to P3 again. Downloads: none. The tile's box copies add about 1.7 MB to the upload.

## How it ran

Run on 2026-11-12 and 13. One box, about three hours. The box's own bill was 2.41 dollars. The credit went from
9.70 to 7.21 dollars, a drop of 2.49; the other 0.08 dollars was not traced (most likely storage and transfer
charges that settled after the box was destroyed).

**The box.** Vast instance 60460403 (host 619223, a Ryzen 9 9950X, 0.80 dollars an hour). The setup script tries
the Berkeley mirror first (since round 59) and checks the official sha256. The checksum list could not be reached
on this box, so the installed binary was checked against checksums that four mirrors agreed on. The box was destroyed at 01:30 on the 13th and the instance list was empty afterwards.

**Stills (22:32 to 22:45).** The before stills and the six variants, each patched onto a copy and rendered at 18
shots (17 of them counted). One fault: Blender turns an `E:/...` output path into `/e/...` on the box, so the stills landed outside the
mirrored folder and did not come back by themselves. They were copied by hand, and `preview_r59.py` now runs `--out`
through `EW.fix_path`.

**Stage 1, the blind ranking.** Two reviewers, 17 shots, mean rank from 1 (best) to 7 (worst):

| Variant | Mean rank |
|---|---|
| `mtn8` | 2.41 |
| `mtn8hc` | 2.76 |
| `mtn12` | 3.00 |
| `big3soft` | 4.38 |
| `p830` (the placebo) | 5.09 |
| `big3` | 5.12 |
| before (today's rock) | 5.24 |

The placebo sat 0.15 from today's rock, so that is the noise. All three mountainside tiles beat it clearly. Marble
three times bigger did not: scale alone does not remove the dried-mud read. Reviewers ticked the crack web once on
`mtn8` and 24 times on today's rock.

**Stage 2, pairs.** `mtn8` against today's rock, 17 pairs, two fresh blind reviewers: 11 wins, 0 losses, 6 same, and
12 wins, 0 losses, 5 same. Every gate from (a) to (g) passed. One new tell showed in 2 shots: the grain runs at a
slant.

**The bake check.** A dev bake of the abode and the steles ran clean. A blind look at it picked `mtn8` on the abode
cliff: softer, and no crack web.

**Production (23:11 to 01:28).** The main file was patched with `mtn8`'s exact arguments (patch digest
`1fba906ed72fba2fd2eb5b066bcef36d`, the same as the stills'), the keep-list compare showed no difference, and the
production bake ran with the texel floor of round 59 on: 12 chunks in 119 minutes of bake time. Then the live maps
of the eleven stops and the bounce. All 12 raw files came back and match the box by md5. The scene file is
`out/sect_chase.r60.blend`. The scene before it is kept as `out/sect_chase.pre_r60.blend`, and the page's files
before the bake as `out/web/full/pre_r60/`.

**Page work.** `materials.py` names the tile `mtn_cliff`. The page's detail texture was rebuilt from it, the detail
band's constant is 0.3985, the mid-distance rock gain is 1.47 (0.8 of the new photo's full gain, the share round 58
picked for the old photo), and the second rock layer no longer turns. The pack built with no problems at 128.55 MB
(it was 127.2 MB).

**The page gate.** A blind A/B of 33 real page screenshots, before against after, two reviewers, with 4 placebo pairs
that neither reviewer picked a side on:

| Reviewer | New rock wins | Loses | Same | Realism after | Realism before |
|---|---|---|---|---|---|
| 1 | 12 | 5 | 16 | 4.97 | 4.72 |
| 2 | 16 | 7 | 10 | 4.98 | 4.77 |

The new rock wins about twice as often as it loses, and the crack web is almost gone (1 tick against 9; colour
blotches 2 against 18). That is short of the bar set beforehand (2.5 wins for each loss). Two views lost with both
reviewers, the mission hall turned left and the formation, where mid-distance rock reads softer. A dial lab of the
mid-distance gain was captured to tune it.

**Where it stopped.** Before any tuning, the owner looked at the before and after sheet and the local page and said:
"Tbh after all this 60 rounds I dont see any differences tbh um". The rock tuning stopped there. The new photo stays
as built, because it is a measured gain with no known loss a visitor would notice, and the work moved to changes of
the whole frame (see "Looks and the journey" in [`../sect/lux.md`](../sect/lux.md)).

**Lessons.**

- Only blind reviewers at twice the page's size could find the gain, and the owner could not see it. Show a
  full-frame before and after at page size before spending a bake.
- The mountainside tile was the right fix for the tell every reviewer named. Stage 1's placebo and noise measure
  made the ranking trustworthy, and are worth keeping for any later stills review.
- The texel floor of round 59 is now baked in. Its effect at page size is small.

## Left out of this round

- **Blend's "two" and "zones"** (a second, bigger read of the marble photo, and noise zones): they need the most new
  `materials.py` code, and they keep the marble web at half strength, which is the tell itself. The attack's sim
  showed "two" turning far rock into a mud-crack web at 4 texels a metre, where 71 to 80 % of hold rock sits. The
  zones preset was never simulated, and its in-zone contrast of 0.9 risks ink lines.
- **Blend's tuning pass:** an unblind tuning step biases the review and costs 9 box minutes. Stage 1's ranking does
  that job.
- **Remap's `big2`** (16.28 m): a step between today and `big3`. If `big3` fails on the polygon net, `big2`'s 0.82 m
  cells are flagstone size and fail too. If `big3` fails on the far repeat, `big2` still repeats at 16 m.
- **Remap's "wide"** (24.42 x 12.21 m): the page would need per-axis GLSL and prep blur code. It stretches the boulders
  and keeps the same net.
- **The unturned mountainside tile:** the turned one is closer to upright with everything else equal, and it reads as
  bedded rock.
- **The mountainside tile with its baked light kept:** the attack measured that light as the cause of the left-right
  blob that repeats in the far sims.
- **Marble with its cracks filled:** the sims show a plaster dapple.
- **Rock063 as the base photo:** it turns into green moss stripes and would trip the page's moss gates.
- **The `rock_face_01`, `rock_face_02` and `boulder_01` skins:** their clean pieces are too small (above).
- **`ROCK_SCAN_SHARP` 12:** hard to see at 60 m. It also changes the moss photo's blend and breaks page tests pinned
  at 4.
- **Stochastic or hex tiling, per-plane rotation, a 30 to 60 m macro layer, and a tile synthesised from several
  mountainside islands:** these fix the repeat rather than the web, and need new GLSL and Blender code. The
  synthesised tile is the next round if `mtn` wins the stills but shows a grid.
- **A "no photo" control** (`ROCK_SCAN_CONTRAST` 0 and `ROCK_SCAN_BUMP` 0): likely round 58's plaster. Its slot went to
  the placebo.
- **A patch dry run before each variant:** a failed check already saves nothing, and every copy is throwaway.
- **Real relief and finer cliff meshes** (round 59's second lesson): a separate round.
- **Any new photo download:** not allowed without the owner.

## Known limits

The tile:

- The repeat shows on the sheets: rows of dark blobs, with a worst top-to-bottom gap of 0.24 stops (marble 0.23). The
  60 m sheets are flat walls showing colour only. Real cliffs are curved and mix three offset projections, so the
  scene should show less repeat than a sheet. Not checked.
- About 36 degrees of tilt on every cliff, the same way everywhere: the triplanar keeps image up along world up on the
  vertical planes.
- A soft grey lichen patch at the left edge of every tile, and one smeared patch near a corner.
- It carries about 72 px of real detail a metre at 8.14 m (48 at 12.21 m). The box copies are enlargements, so
  close-ups may read soft (the `plaster` tell).
- The relief overrides (0.3 and 0.45 m) are about 10 % under the height the tool measured (0.334 and 0.50 m).
- The seam gate's formula is the builder's; the design's formula fails across ("The seam gate").
- PIL's box copies were not compared with what `prep_textures.mjs` (sharp) would make from the same 4k files. If an
  `mtn` variant ships, later bakes get prep's copies, which may differ by a few levels.
- Nothing has shown the tile lit in Cycles, with bump, in a bake or on the page.
- The page's moss and stand-in rock gates, which read the baked colour, were not checked against the new rock. The
  tile's own green share is 0.

The review:

- Gate (f) measures brightness over the changed pixels only. On round 59's stills that gave `after` +38.5 % at
  `abode_1380_close`, where round 59's doc measured +6.1 % over the whole still. Round 59's material changed few
  pixels (its drawn cracks), so the mean over them moved a lot. A photo swap changes nearly every rock pixel, so the
  measure comes close to the mean over all rock, but the 5 % bar is still stricter than round 59's whole-still check.
- On the 4 placebo shots, before's still appears in two pairs of the same stage 2 folder (the real pair and the
  placebo pair). A reviewer could spot it as the shared side. This comes from the placebo-pair design.
- The stills show only the bake material, none of the page's layers. The page gets its own blind A/B after the bake
  (the last page gate).
- The time parser was tested only on synthetic log lines shaped like `preview_r59.py`'s. No round 59 box logs are on
  disk, so the try on round 59's stills used the PNGs' RenderTime.
- The READMEs and templates have not been tried by a real reviewer.
- The blind holds only while each reviewer keeps to its folder (see "Prepare").
- The bake check's A/B is made by hand.

The patch and the page:

- The `PHOTO_SWAP` branch, the second missing-scan check and the new log lines were checked by reading and
  `py_compile` only. Step 5's first `mtn` run is their test.
- `nature_rock_small` reads the photo at 4.07 m, but the page reads every rock class at the rock tile, so the page's
  layers do not land on the boulders' photo. That is so today too. Rock063 on the undersides is out of line the same
  way.
