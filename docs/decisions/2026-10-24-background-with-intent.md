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
| No ledges with grass | About 70 of the range's peaks become karst pillars with their own uneven rock beds, real shelves with green tops, a green fringe pouring over each shelf lip, fissures with ferns, and a forest cap | `world.Range` (peak mode `pillars`), `lib/nature.peak_pillar` |
| Trunks, not green | A broadleaf canopy (rounded crowns that hide their trunks, six variants in three greens) with slim Masson pine spires and scrub replaces the one see-through pine copied 31,000 times. Beyond the near band the forest is a solid canopy mass, not single trees | `lib/nature.canopy_tree`, `scenery.r48_range_canopy`, `r48_shell`, `r48_hulls` |
| Confetti islands, light-beam falls | Islands are cut to 0-3 per stop (about 40 islands and 12 islets in all, at most 7 in any frame); the ones that stay get canopy caps. Falls are shorter, arc and break into spray; none at the arena, mission, library, steles or scroll stops | `lib/compose.cull_islands`, `cull_falls`, `scenery.r48_isles`, `r48_falls` |
| A row of cakes on the horizon | Three pillar families and two low mesas, placed from the stops' cameras | `world.BACKDROP_R48` |
| Views with no plan | Pillar tops are cut where a stop needs clear sky: the moon at the gate, the poster and the summit, the forge's smoke column, the library's empty right half | `lib/compose.peak_limits` |
| Orange rock that outshines the halls | The rock material keeps less of the photo scan's warm hue; damp undersides are darker | `lib/materials.py` (`ROCK_*`) |
| A sect with no life outside its halls | Two plank walkways climb two pillars to small pavilions, and one more pavilion stands at a pillar's foot | `life.build_paths` |

Every hall, prop, stair, bridge, shrine, plaque and inscription stays exactly as it is. A keep-list check
(`sect/patch_r48_keep.py`) compares them, and every plant within 60 m of a stop camera, before and after.

## How it is built

Patches on the finished scene, rehearsed on a copy first, each with a digest and a dry run:
`patch_r48_range.py` (pillars), `patch_r48_isles.py` (islands, falls, horizon), `patch_r48_green.py` (wall plants
out, canopy, shelves, hero pines, canopy mass, rock, the abode), `patch_r48_life.py` (walkways). The same changes are
in the builders, so a rebuild matches. The run sheets and the author's notes are in the round-48 scratchpad.

## The final bake

The owner: "once everything is done, we can do the full hd render and use that as the final version for now and
call it." After the round-48 build, the web bake runs once at production quality (with the Five Element flags and the
cloud export from the round-42 decision), and that is the version that ships.
