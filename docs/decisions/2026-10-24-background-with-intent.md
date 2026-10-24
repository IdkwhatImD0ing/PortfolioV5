# The background with intent (round 48, 2026-10-24)

The owner's feedback on the scenery around the halls:

- "There is trees growing out of cliff faces, there is no ledges with grass. there is a lot of trunks, not enough
  grenery. In real life, people just see green, they dont see the trunk"
- "the individual locations are good, just the overall background and vibe of the scene don't quite have enough
  intent yet"
- On the study and plan: "i approve of the new background", "I trust you"
- On intent: "The best thing to research mightb e intent, like what makes something look like it was designed with
  intent and purpose"

## What intent means here

Every view has one star (the hall or its hero prop), one background shape built around it (the host), a few
framing masses, and quiet sky. Every element has a reason to be there or it goes. The per-stop plan is data:
[`blender/xianxia-sect/sect/holds_intent.json`](../../blender/xianxia-sect/sect/holds_intent.json) (story, reading
order, host, quiet sky, islets, falls, mist heights for each of the eleven stops and the flights between).

## What changes in the scene

| Problem | Change | Where |
|---|---|---|
| Trees on sheer walls | The cliff, wall and crown pine scatters and the ledge tiers are switched off everywhere except within 60 m of a stop's camera, where every tree stays as it was. The Cave Abode cliff's 29 face pines go; two pines stand on one rock shelf instead, with fern strips in the joints and vines from the rim | `scenery.r48_walls_out`, `areas/abode.r48_dress` |
| No ledges with grass | About 70 of the range's peaks become karst pillars with their own uneven rock beds, real shelves with green tops and clumps of shrubs, fissures with ferns, and a forest cap whose rim crowns lean out over the edge | `world.Range` (peak mode `pillars`), `lib/nature.peak_pillar` |
| Trunks, not green | A broadleaf canopy (rounded crowns that hide their trunks, six variants in three greens) with slim Masson pine spires and scrub replaces the one see-through pine copied 31,000 times. Beyond the near band the forest is a solid canopy mass, not single trees | `lib/nature.canopy_tree`, `scenery.r48_range_canopy`, `r48_shell`, `r48_hulls` |
| Confetti islands, light-beam falls | Islands are cut to 0-3 per stop (about 40 islands and 12 islets in all, at most 7 in any frame); the ones that stay get canopy caps. Falls are shorter, arc and break into spray; none at the arena, mission, library, steles or scroll stops | `lib/compose.cull_islands`, `cull_falls`, `scenery.r48_isles`, `r48_falls` |
| A row of cakes on the horizon | Three pillar families and two low mesas, placed from the stops' cameras | `world.BACKDROP_R48` |
| Views with no plan | Pillar tops are cut where a stop needs clear sky: the moon at the gate, the poster and the summit, the forge's smoke column, the library's empty right half | `lib/compose.peak_limits` |
| Orange rock that outshines the halls | The rock material keeps less of the photo scan's warm hue; damp undersides are darker | `lib/materials.py` (`ROCK_*`) |
| A sect with no life outside its halls | Two plank walkways climb two pillars to small pavilions, and one more pavilion stands at a pillar's foot | `life.build_paths` |

Every hall, prop, stair, bridge, shrine, plaque and inscription stays exactly as it is. A keep-list check
(`sect/patch_r48_keep.py`) compares them, and every plant within 60 m of a stop camera, before and after.

## What the first test changed (B0 and the slice, 2026-10-24)

Three test builds were baked for the f870 wall and the scroll hillside. The pick: sandstone pillars on every cut
peak (granite gave smooth walls with no ledges) and "hull" canopy clumps for the mid distance (a smooth shell reads as
a lawn). Changes before the slice:

- No fringe strips over the shelf lips. They baked as flat paper and black sticks, and a few of their faces marked
  the page's "built" mask over most of a pillar, so the paler range rock never reached it and the pillar stayed orange.
- Broadleaf trees reach 250 m from the camera path (was 90 m), with fewer bare clearings; the canopy shell starts
  beyond. The hull clumps were packed closer first (11 m apart), but under each chunk's triangle budget they baked as
  small pyramids, while the trees' cards read as round green crowns.
- The bake keeps more triangles on each pillar a stop sees (a floor by its size on screen, extra to the chunk's
  budget): the 185 m pillar at f870 had been cut to 1,142 triangles and its shelves were gone.
- Shelf shrubs four times as dense, in clumps; caps twice as dense, with rim crowns leaning out; on the pillars near a
  stop, shelves stick out about 2 m; some rock beds are 2-3 times thicker, so the beds are not equal drums.
- A denser canopy with bigger crowns (7-14 m), so it closes instead of showing single trees; scrub on the steep slopes
  in patches and fern strips in vertical runs, so neither reads as a scatter of dots; the crowns' sunlit tops are a
  little greener and darker. (Denser, bigger scrub everywhere closed the slopes too, but doubled the 3D bushes the
  bake makes, so the scrub keeps its old amount, gathered into patches.)
- The page turns far range ground (the hull clumps bake as ground) canopy green from 90-180 m (was 150-260 m).

## Phase C: range-wide, after the slice critic

The slice critic (standing in for the owner) said the method was right but the look was not designed yet: pillars
like stacked drums, a forest like pale cabbages on plates, and the green on the rock as evenly spaced dots. What
changed before the range-wide build:

- Shelves are broken arcs: each one stands out over 30-60 % of the way round, in one or two arcs, and fades into the
  wall elsewhere. Plain bed joints keep half their groove, so only real shelves read as lines. Shelf tops are a dark
  green cushion (the canopy-mass material) instead of the soil moss, whose dry grass read as a straw line on every lip.
- Sandstone columns under 30 m across the top taper sooner (their foot at least 1.35 times the top, and the flare in
  the part above the mist), with stronger lobes and two or three deep clefts. A slim pillar's cap spills more crowns
  over its rim. The far pillar families over the cloud sea get wider feet too. Before, they read as chimneys.
- Shelf plants come in 2-4 clumps per shelf run, big, medium and small, with crowns hanging over the lip, more of
  them on the shaded side. Crack plants come in fewer, denser vertical runs, never single dots.
- Masson spires stand in loose groves of 3-7 through the valley canopy (about a tenth of the crowns).
- The flat-pad pines in the ring round each area (the ridge above the jade slip) go outside the keep zones: one forest
  style.
- The area cakes lost their cliff pines, so their lips get shrub clumps and small crowns leaning out (clear of
  anything built and of the hold cameras), and their 49-degree aprons get scrub all over plus small crowns.
- The streams that fed the range falls are hidden where they now hang in the air (a cut peak) or their fall is gone.
  One was the long diagonal "beam" at f870 turned 30 degrees.
- The abode's fern strips grow in runs of 2-3 plants abreast with bare joint between, not one plant every 1.8 m.
- A culled islet's own top pines are hidden with it, and so are island pines with no rock under them (three
  stood in the sky at f150).
- On the page: the canopy tint gain drops from 2.0 to 1.0 (the new crowns bake brighter than the old pine pads); near
  sunlit range rock is darkened to 0.78 within 140-320 m, so the f870 wall no longer outshines the formation; patches
  of crowns 24 m across vary in value and warmth; tree sprite cards fade their flat top quad near level and their
  upright pair from about 22-37 degrees above, so no disc shows under a crown and no X from above.

## How it is built

Patches on the finished scene, rehearsed on a copy first, each with a digest and a dry run:
`patch_r48_range.py` (pillars), `patch_r48_isles.py` (islands, falls, horizon), `patch_r48_green.py` (wall plants
out, canopy, shelves, hero pines, canopy mass, rock, the abode), `patch_r48_life.py` (walkways). The same changes are
in the builders, so a rebuild matches. The run sheets and the author's notes are in the round-48 scratchpad.

## The final bake

The owner: "once everything is done, we can do the full hd render and use that as the final version for now and
call it." After the round-48 build, the web bake runs once at production quality (with the Five Element flags and the
cloud export from the round-42 decision), and that is the version that ships.
