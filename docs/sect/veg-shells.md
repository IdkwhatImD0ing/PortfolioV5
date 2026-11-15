# Far trees as lit crowns

Status on 2026-11-12: on the branch, High tier only. Part of the pull request opened on 2026-11-14. Round 58 was reviewed
and partly taken back (below). What is left passes its tests but has not been seen in a capture yet.

## Why

The owner, 2026-11-10: "far away objects show up as blocks which breaks the immersion", and "we
might need to replace some of the models like grass trees etc ... see how saltline does it".

The blocks were the far trees. Each one was a baked card: three flat textured quads, one of them
lying flat on top. Most of the flight looks down on the forests, so the flat quads showed as green
plates. Saltline, the game the owner pointed at, loads no model files: it builds from code and
lights live. Far trees now work that way.

## How it works

1. **Where the trees are.** `bake_trees.py -- instances` writes
   `out/web/full/veg/instances.json`: every plant the web draws (56,035), with its place, height,
   radius, family, whether the bake draws it as a near mesh or a far card, and whether the low sun
   reaches it. It needs no bake, only the tree plan and the sun ray casts a tree build leaves in its
   cache.
2. **The page's files.** `blender/xianxia-sect/tools/sect_veg.py` (plain Python, on the PC) turns
   that into `client/public/sect/full/veg/<area>.veg` and `index.json`: 24 bytes a plant, 1.35 MB
   in all. It keeps pines, shrubs, bamboo and blossom trees and drops grass and lotus.
3. **The crowns.** For every plant the bake draws as a card, the page draws one or more instances
   of an 80-triangle shell (`lib/sect/veg.ts`): a rounded crown for broadleaf trees, shrubs and
   blossom, a spire for Masson pines, a plume for bamboo, and three to five flat pads for Huangshan
   pines. Each crown is made lumpy in the vertex shader by its own noise, and each has its own width
   (0.72 to 1.12 of the plant's radius), brightness and tilt of hue, so a forest is not a field of
   equal balls.
4. **The light.** The fragment shader lights each crown from the bake's key light, with the
   plant's own sun value on top, a cool sky tint in shade, darker undersides, and a glow at the edge
   when the view looks toward the sun. Boughs 1.3 to 3.4 m across change the light only: each has a
   lit side, a shaded side and a darker crease. Leaves are two fine brightness fields that fade out
   before they get smaller than a couple of pixels. The edge is eaten away by a fine noise so it is
   ragged. A crown sunk among taller neighbours, or shaded by one toward the sun, has a darker lower
   half. Then the scene's grade and haze, as the baked trees get.
5. **Cards near, crowns far.** A card has the baked detail and looks right from the side and close
   up, so the cards are kept and each tree is drawn by one or the other. The ground is cut into
   9 m cells. A cell's trees are crowns when the camera is farther than the cell's switch distance
   (150 to 230 m, each cell its own) or looks down on it more steeply than 11 to 19 degrees. The
   card's fragment shader and the crown's vertex shader run the same lines
   (`card-shading.ts` `farCutCellGlsl`), so one of the two always draws.

## Switches and numbers

- Quality: `vegShells`, on for High, off for Medium and Low (they keep the cards everywhere).
- URL: `?veg=0` forces the cards, `?veg=1` forces the crowns on any tier.
- Look: everything is in `VEG_LOOK` in `lib/sect/veg.ts` (round 58's parts: `boughs`, `depth`).
  The switch distances are in `CARD_LOOK.farCut`.
- `?debug=1` puts per-area counts on `window.__sectVeg`, and the boughs' strength on
  `window.__sectVegBough` (below).
- 48,915 card plants. The backdrop's 8,915 are always loaded.

## Round 58: boughs, bites and depth

Reviewers of round 57 called the far forests "a hazy mass of round blobs". Round 58 tried three
things, all in the page (`lib/sect/veg.ts`):

1. **Boughs as relief.** The bough field (1.5 to 3 m cells) was read with its slope
   (`sectVegNoiseD`, the value noise with its exact gradient, mirrored in TypeScript), on a lattice
   turned off the crown's axes (`VEG_BOUGH_TURN`) so the blobs do not line up in rings. The normal
   leaned down the slope (a median of 15 degrees) and the creases kept 70 % of their brightness.
2. **Bites.** The outline was cut by the same field, by up to a quarter of the projected radius
   where the boughs dip. Every crown was made 1.077 times larger to keep its area.
3. **Depth among crowns.** One number per crown, worked out in the page from the plant list when a
   chunk loads (the `.veg` file is unchanged): how far its top sits below neighbours within its
   radius, and how much of its lower half a neighbour toward the sun shades under the 7 degree sun.
   A deep crown's lower half loses 60 % of its sun and 20 % of its brightness. Over the twelve plant
   lists the median crown is 0.79 deep, and about a quarter are 0.

### What the review found

The review with crops (`.playwright-mcp/survey/review_r58_page.md`) found the round a small net
loss: the average stop score fell from 4.52 to 4.46 out of 10. Mirror, mission, scroll and
formation each lost 0.2 or 0.3; abode gained 0.3. The crowns were the cause:

- **The bites** caused 32 of the 48 confirmed regressions, and all 4 severe ones: holes through
  crowns, chips floating in the sky, straight cuts, and pads like flat lily pads.
- **The boughs** caused 8. They helped a little where a crown is far and small on screen, and hurt
  where it is near, large on screen or seen from above: "crumpled foil", "molten clay", "folded
  slabs".
- **Depth** caused 2: pine pads in the sun lost their lit tops.

The bites were wrong in the maths. They took the projected radius as rho = sqrt(1 - (N.V)^2), which
holds only on a sphere. On a flat or tall crown, and on a pine's flat pads, much of the inside has a
normal turned away from the view, so it counted as rim and was cut: a hole in the middle, or a
straight cut along a pad. Round 57's ragged edge (a fine noise with a threshold that rises toward
the edge) never cuts that deep, and reviewers did not flag it.

Depth went wrong the same way. It found the lower half by the direction from the crown's centre.
On a flat pad that direction is near level almost everywhere, so about a fifth of a pad's top (seen
from above) counted as lower half.

### What was taken back, and what was kept

1. **The bites are gone.** `VEG_LOOK.rim` and the 1.077 widening are out, so crowns are round 57's
   size again. Round 57's ragged edge is back as it was: noise cells of 0.45 m or 0.08 of the
   crown's radius, a threshold from 0.3 to 0.85 toward the edge, a soft cut with alpha to coverage
   on a multisampled buffer and a hard one without. It keeps about 0.9 of a crown's face-on disc.
2. **Boughs change the light only, and softer.** The lean is 0.45 (a median of about 10 degrees at
   full strength, was 15) and the deepest crease keeps 80 % (was 70 %). Both ease off to 35 % of
   themselves while a bough cell grows from 12 to 36 pixels on screen, and they still fade flat when
   a cell nears a couple of pixels. The crease eases toward its mean over the field, so a crown's
   brightness does not change with the strength. Cells are seeded from 1.3 to 3.4 m (was 1.5 to 3),
   so lumps differ more from crown to crown.
3. **Depth goes by the height on the shell.** The lower half is where the unit shell point (before
   the radii) is low, so a flat pad's top keeps its sun: about 1 % of a pad's top counts as lower
   half now, against about a fifth before. The underside's darkening still goes by the direction
   from the centre, as before.

The boughs' strength is one shared uniform, `uVegBough`: x the lean, y the deepest crease's
brightness (1 is no crease), z the share of both kept when a cell is large on screen. Every chunk's
material uses the same object. With `?debug=1` it is `window.__sectVegBough`, so it can be tuned
from the console, for example `__sectVegBough.set(0.6, 0.7, 0.5, 0)`. The page draws on demand, so
scroll a little to see the change.

Numbers:

- `light.gain` is still 1.22, round 57's. Round 58 kept it too and matched its crease's mean to
  round 57's gaps instead. Now the softer crease keeps 0.938 of the brightness on average, against
  0.910 for round 57's gaps (3.1 % brighter). Depth at the forests' mean depth (0.6) takes about
  2.9 % back seen from 10 to 70 degrees above. Together that is within 0.1 % of round 57.
- At that depth a round crown is about 3 % darker than round 57's seen nearly level and 4 % brighter
  from 70 degrees, and the same on average within about 1 %. Easing off or fading flat moves it by
  under 2 %.
- Noise per pixel: 40 hashes (round 57: 56, round 58: 24). Two more varyings: the unit shell point
  and the edge's cell size. Still one float per crown more than round 57.
- Building a chunk's crowns, depth included, takes 5 to 38 ms on the owner's PC, once per page.

Left out on purpose:

- Pixel-sized leaves and holes. They would shimmer while the camera moves.
- A leaf-sized fringe on the rim. It would be gone by 110 to 140 m, and the crowns start at 150 m.
- Stands of trees sharing a tone. Each crown's own variety would swamp it, and the cards would not
  match it at the switch.

### What the last review saw

The whole round was reviewed again after these fixes (`.playwright-mcp/survey/review_r58_final.md`).
None of the first review's crown faults came back: no holes, no foil, no pine pads without their lit
tops, no brightness step where the shells take over from the cards. But the reviewers also saw no
gain: "far crowns: no visible change at any stop", and far forests still read as smooth domes. So
the lumps are harmless and nearly invisible at their present strength. Making far forest read as
canopy needs real crown shapes (cards baked from the new leafy trees, or shells with gaps), which is
a Blender job, not more shader.

## Not done

- Near trees are still the baked models. From close up some read as low-polygon lumps.
- Crowns have no trunks and cast no shadows of their own.
- The changes after the review have not been captured. Worth looking at: the four stops that lost
  the most (mirror, mission, scroll, formation), crowns just past the 150 to 230 m switch and seen
  from above, pine pads in the sun, and High with MSAA off (a hard cut instead of the soft one).
  The bough strength is worth tuning live there before it is settled.
- The underside's darkening still goes by the direction from the crown's centre. On a flat pad that
  dims the top a little (a few percent).
- Depth sees only the crowns of its own chunk, so a crown at the edge of an area misses neighbours in
  the next one.
- Each plant's sun value is for the 7 degree sun. The key light reaches more of them, so the shader
  gives every crown a floor of light (`VEG_LOOK.light.floor`).
- The `.veg` files are not in the manifest's revision list. The page fetches them with
  `cache: "no-cache"`.
