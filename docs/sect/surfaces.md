# Surfaces: wear, dirt and rock beds

Status on 2026-11-12: on the branch. Part of the pull request opened on 2026-11-14.

## Why

Three reviews of live light ([`live-gate.md`](live-gate.md)) ended the same way: light was no longer
what held the picture back. What read as fake was in the baked and the live picture alike, and at
seven of the eleven stops the same four things led the list:

- plazas and marble spotless, one slab pattern with no wear or dirt,
- paint on walls and pillars flat and clean,
- lawns one even green,
- cliffs with no rock structure.

The owner, asked whether to start a round on the models and textures: "Yes, start it".

This first round is the part the page can do on its own, with no new model and no bake: the detail
layers in `client/src/lib/sect/detail.ts`. They already drew joints, grime, grass clumps and far
rock noise, but so gently that nobody saw them.

## What it does

All of it is in the page's shaders, baked or live.

1. **Paving** (`DETAIL_LOOK.paving`), on the tiers that have the detail layers.
   - One slab in twenty is a replaced stone: a little greyer, lighter or darker.
   - Warm, light stains a few metres across, and dust over tens of metres.
   - One slab in ten has a crack across it (close up).
   - The grime along slab edges is darker.
   - Under the live lamps each slab sits a touch unevenly and its edges are bevelled into the
     joint (`LIVE_LOOK.paving`), so the low sun catches a rim.
2. **Weathering** (`DETAIL_LOOK.weather`, `weatherGlsl`), on the same tiers. Every baked surface
   with no detail class and no reflective class of its own (walls, pillars, marble bases and
   rails, stairs, statues) gets:
   - smooth patches of tone, about 3 m and 0.7 m across,
   - sparse, soft rain streaks down steep faces, about a fifth of a wall, a quarter as strong on
     near-white stone,
   - a fine grain close up.

   The patterns are the ground noise's smooth fields, read from above and from the two upright
   sides and weighted by the way the face looks, so a wall that faces between two axes has no
   direction along which the pattern stands still. They are fixed in the world, so they are not
   put on hotspot pieces (some of them move), on cloth that sways, on cards, trees or water.
3. **Lawns** (`DETAIL_LOOK.macro`, `clump.patchy`). The colour drifts a little more from place to
   place, and the strength of the grass clumps varies gently.
4. **Rock** (`DETAIL_LOOK.rockBeds`). Steep rock faces lie in level beds about 2.9 m thick, of
   uneven thickness, each a little lighter or darker and eased into the next, with a thin dark
   line along about a third of the boundaries.

## The first version, and what two reviewers said

The first version was shot at all eleven stops and compared with the pictures from before (55
pairs, two reviewers). Verdict: about even. Plazas and paths were a little better; walls and rock
were worse, because the new layers drew regular, man-made patterns.

| Seen | Cause | Fix |
|---|---|---|
| Hard vertical bars on white parapets and stand walls, "piano keys" and "barcodes" | Rain streaks as value noise stretched the full height, cut by a sharp threshold | Streaks from a smooth field, sparse and soft, a quarter as strong on near-white stone |
| Khaki rectangles on stair treads and marble bases | Value noise's blobs line up with its grid | Patches from the smooth fields |
| Spires like stacked rings, cliffs like ruled paper or plaid | Rock beds of even thickness, hard tone steps, a line at every boundary | Uneven thickness, eased steps, a line at a third of the boundaries, less tone |
| Far plaza joints as dotted lines | Joints drawn out to 130 m | Back to 100 m |
| Stains like cloud shadows | A cool grey tint | Warm and light |
| The near lawn a blur with no tufts | The clumps' strength fell to 0.3 in places | Never under 0.65 |
| The gate's stair treads as a chequer of sunlit blocks | A slab tilt of 0.02 under a 7 degree sun | Tilt 0.007 |
| Dashes of grime and moss on stair treads | The grime band was widened by the pixel's size and not thinned, so at a low angle it covered whole slabs (an old flaw the darker grime made visible) | Thinned by as much as it is widened |

The test pass also caught three things no picture showed: on the Low tier the weathering had
landed on rock and lawns too (it tested for the detail patch, not the material's class), it was
on metal and the mirror, and on a wall facing exactly between two axes the patches would have
been bands.

## The reworked version, and the second review

The reworked version was shot again (55 pairs) and went through a review in three steps: four
reviewers compared before and after, a second reviewer tried to refute every "got worse" claim on
crops of both pictures, and a last one merged the result. Report:
`.playwright-mcp/survey/review_surf2.md` on the PC that ran it.

- The bars, the rectangles and the ruled rock were gone. Nobody reported them again.
- The reviewers' score for how real the surfaces read went from 4.36 to 4.45 on average, on a
  scale of 0 to 10 where 10 would pass for a AAA game screenshot. That is a gain of a tenth of a
  point: real, and too small to see without the two pictures side by side. The arena and the
  mission hall gained half a point each; the forge lost half a point.
- 15 flaws were claimed and all 15 confirmed. 12 were one thing: the plaza stains, tan blobs a few
  metres wide that crossed the joints and read as camouflage or as a second shadow. Two were far
  joints breaking into dots. One was a hairline along a rock bed.

| Seen | Cause | Fix |
|---|---|---|
| Tan blotches on the forge, scroll, steles and mission plazas | A stain tint that darkened blue by a third, drawn as a blob across the joints | Stains go by the slab (the field read at each slab's middle) and are at most a tenth darker |
| Far joints as dots | Joints a little darker than before | Back to the old tone |
| Hairlines across a cliff | The line where two beds meet | No line |

After these the plazas read like the old ones with more variety from slab to slab, and no stop is
worse than before. The lesson of the round: the page's shaders can add variety, but they cannot
add what the reviewers ask for next. Their list after this round is the same at every stop: the
rock is a smeared, stretched texture; lawns end in a hard cut line; near paving has no relief and
the grand stair's texture is stretched. Those are models, materials and UVs: a Blender round.

## The rock's middle band (round 58)

Reviewers still called the cliffs a smeared blur. The bake draws rock with a photo
(marble_cliff_06 then; since round 60 the mountainside tile `mtn_cliff`; one tile every 8.14 m), but seen from 60 to 400 m its texels are 12 to 100 cm,
so the photo's cracks and blocks smear out. The page's fine layer is 12 cm grain and gone by
150 m, so nothing put that size back.

- `detail.webp`'s blue channel held moss that nothing read. It now holds the same photo's middle
  band: its log brightness blurred at 0.12 m minus blurred at 1.0 m, so features about 0.25 to
  2.5 m across. Red and green have the same pixel values as before.
- Rock reads it where the bake read the photo: the same world triplanar mapping, tile, plane
  offsets and blend exponent as `materials.py` (`triplanar`, `_rock_scan`), in `detail.ts`
  `ROCK_SCAN` and `rockScanUv`. So the band lands on the bake's own soft cracks and sharpens them.
  Read anywhere else, it would draw a second set of cracks beside them and the rock would look
  muddy. The fine layer's three own-size reads moved onto the same coordinates, so one read gives
  both: no extra read near the camera and no new texture unit (a live rock stays at 15).
- It fades in from 20 to 70 m, where the bake starts to lose it, and out from 400 to 500 m.
  Never on the far set or the stand-ins, which have no photo. Medium and High only, like the rest
  of the detail. Low is unchanged.
- Strength: `DETAIL_LOOK.rockMid.gain`, 1.47 stops per unit since round 60, a little less in
  shade (its own floor since the review, below). The bake holds the photo's brightness at about
  0.73 of full strength. For `mtn_cliff` (`bandK` 0.3985) that works out to a full gain of 1.84,
  and 1.47 is 0.8 of it. 0.8 is the share round 58 picked for the marble photo: 2.0 of 2.48, after
  starting at half (1.24) and raising it after the review (below). The new value was not tuned on
  the GPU (see [`../scene/rock-r60.md`](../scene/rock-r60.md)). It is a uniform, so
  it can be tuned in the console with `?debug=1`: `window.__sect.ctx.detail.uSectRockMid.value`
  (0 turns it off).

Tests read `materials.py` and `prep_textures.mjs` as text and check the photo, tile, offsets,
exponent and band against `ROCK_SCAN`. If the bake's rock material changes, they fail until both
sides match and `detail.webp` is rebuilt.

To rebuild `detail.webp` (seconds on this PC, no Blender):

```
node blender/xianxia-sect/tools/prep_textures.mjs E:/Github/PortfolioV5/blender/xianxia-sect/assets \
  blender/xianxia-sect/out/web/full/site/detail.webp --detail-only --keep-rg client/public/sect/full/detail.webp
```

`--keep-rg` takes red and green from the shipped file bit for bit, after checking they are the
bands the script makes, and writes the file lossless (1.33 MB in round 58, 1.19 MB before). Round
60 changed the rock photo, so it kept only green (`--keep-g`), and the file is 1.52 MB. Without it the file
is made near-lossless from the photos (0.87 MB) and red and green move by up to 8 levels. Then
copy it to `client/public/sect/full/` and update its rev in `manifest.json` (or run
`sect_pack.py`, which does both): the page fetches it by that rev. `sect_pack.py` copies
`detail.webp` from `out/web/full/site/`, so after a box pull check that copy still has the band
(its sha256 starts `654948a579773d03` since round 60). An older copy there would quietly put the moss back.

Not checked yet: how it looks. The first look should set the gain to 6 at a hold and check that
the sharp lines sit on the bake's soft ones. Doubled lines would mean the shipped `.blend` maps
the photo differently from `materials.py`. Browsers without `createImageBitmap` load the texture
turned over (`assets.ts`), which would break the match there.

### What the round 58 review found

The round 58 review shot every stop before and after and checked each "worse" claim on crops
(report: `.playwright-mcp/survey/review_r58_page.md` on the PC that ran it). The band is a small
real gain. It breaks up the blocky texels on pale sunlit faces at 7 of the 11 stops, with no
repeats, no seams where two faces meet and no line where it fades in or out. It caused 5 of the
round's 48 confirmed flaws, all rated low. Three faults:

- It never showed on shaded faces, at any stop. It was scaled by the fine layer's shadow factor
  (`DETAIL_LOOK.dark`: 0.4 below a luminance of 0.015, rising to 1 at 0.15), and shaded range
  rock sits low on that ramp, so it kept as little as 40% of its strength there.
- It read as one even pattern. On the abode's near cliff the cracks formed same-size cells, like
  crazy paving or dried mud. On the library and summit spires it was an even plaster or stucco
  dapple.
- It landed on moss once (a yellow-green patch at the library). The moss test ran after the band.

It was also too weak on most big sunlit cliffs. That is the gain's job, tuned on the page.

Three changes followed, all in `detail.ts`:

1. Shade: the band has its own floor, `rockMid.darkFloor` 0.85, on the same luminance ramp. In
   deep shade it keeps 85% of its strength. The fine layer still keeps 40%.
2. Moss: the moss test (`sectGr`) now runs before the band, and the band is scaled by 1 minus
   it, so full moss gets none. The test reads only the texel from before any layer, so moving it
   up changes nothing else.
3. Patches: the band's strength runs from 0.45 to 1.3 times with one smooth field of the ground
   noise (B), blobs about 9 m across (`rockMid.patch`), so it comes and goes over a few metres.
   The field is read from the two upright sides and from above and blended by the face with the
   band's own weights, like the weathering's patches, so a patch does not stretch down a cliff.
   That is three reads of a small texture rock already binds: no new texture unit.

The field is even from 0 to 1, so the patches average (0.45 + 1.3) / 2 = 0.875. At the same gain
the band is about an eighth weaker on the whole. The far set and the stand-ins still have no band.

Then the gain was picked on the GPU. Six cliff views were shot at four strengths (0, 1.24, 2.0 and
2.8; `.playwright-mcp/survey/r58_rock/`). At 2.0 the summit's spire stops being a smooth smeared
cone and shows stone grain, and the gate's shaded cliff shows structure for the first time. At 2.8
the abode's near cliff turns into a net of cracks. So the gain is 2.0. The cliff under the mirror
hall barely changes at any strength: what it lacks is shape, and no band can add that.

### The last review of round 58, and the texel gate

The whole round was reviewed once more against the pictures from before it (55 views, four
reviewers, each "got worse" claim checked by a second agent on crops;
`.playwright-mcp/survey/review_r58_final.md`). The scene went from 4.50 to 4.68 out of 10. The rock
band helped at five stops and hurt at two, and it was behind every fault a viewer sees without
zooming: lumps like crazy paving on the abode's lit cliff columns, sponge blotches on the library's
main spire and on a near pillar at the steles, blotches on the yellow moss rim at the library.

The cause is one thing. The band is meant to give back what the bake lost, but it was laid on at
the same strength everywhere. Near rock is baked fine enough to hold the band already (the abode's
cliff has 7 to 14 texels a metre), so there it was added twice. Three terms fix it, all in
`DETAIL_LOOK.rockMid`:

1. `texelM: [0.1, 0.3]`. The shader works out the size of one baked texel at the pixel, in metres,
   from how far the world position and the atlas coordinate move across the pixel. Under 10 cm the
   band is off. From 30 cm up it is fully on. So the abode's near cliff gets none, and a far spire
   at 1 to 3 texels a metre gets all of it. Materials with no map (the far set, the stand-ins) have
   no band anyway.
2. `pale: { lo: 0.35, hi: 0.8, keep: 0.6 }`. On bright lit faces the same stops read as blotches,
   so the band keeps 60 % there.
3. `mossHue: [0.55, 0.78]`. The band's own moss gate uses a wider hue than the green-rock gate, so
   yellow moss counts as moss.

Checked on the GPU at twelve views (`.playwright-mcp/survey/r58_c1/tri_a.jpg` and `tri_b.jpg`, each
row: before the round, the band at 2.0 everywhere, the band with the gate). The abode's columns and
the library's moss rim are back to how they were. The library's spire and the steles pillar keep a
milder mottle. The summit's spire keeps its stone grain and the gate's shaded cliff its structure.
This last change has not been through a review round of its own.

## Not done

- Rock is still the bake's shapes and material, with beds and the photo's middle band on top.
  The cliffs and spires need new shapes and a new material, which is a Blender job.
- Trees, the waterfall, the flames and the moon are models. Nothing here touches them.
- The weathering does not know how high a wall stands, so there is no dirt at the foot of a wall
  and streaks do not start under a ledge.
- Stairs share the paving's slab grid: a tread still shows a strip of it.
- The Low tier has none of this (it has no detail layers).
