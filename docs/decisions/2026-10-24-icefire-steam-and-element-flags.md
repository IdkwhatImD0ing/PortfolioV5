# Ice-Fire steam and the Five Element flags (round 42, 2026-10-24)

The owner reported two problems on the live site:

- "The smoke from the ice and fire island isnt matched to the volcano"
- "The flags at the formation seem very low quality and blurry"

## 1. The steam was stale data

**What was wrong.** The site drew an old steam plume. It came from round 7, before round 34 turned the island
150 degrees and before round 36 rebuilt it with a volcano. The plume's lowest puff hung about 13 m to the side of
the crater and 10.5 m above the molten pool, so the smoke floated in the air next to the volcano.

**Why.** Blender's cloud puffs reach the site only through one export step, `export_web.py -- clouds --profile
full`. No render batch had run that step since round 7. `mist.py` keeps whatever Blender puffs that step last
wrote and copies them to the site, so the old plume shipped again with every batch.

**How we know.** The 19 steam puffs in the shipped `clouds.json` were identical, to the centimetre, before and after
the round-36 rebuild. Each puff's turn matches the island's old yaw of 352.2 degrees exactly (the island now stands
at 142.2 degrees). The crater's position comes from the molten pool in the shipped library chunk.

**The fix (live now, no Blender needed).** `blender/xianxia-sect/tools/icefire_steam_clouds.py` rewrites the
island's steam in `client/public/sect/full/clouds.json`. It writes round 36's own steam recipe: a 10-puff plume from
the crater and 5 puffs where the lava stream meets the glacier. The only things it makes up are small random wobbles
of each puff's position and shape. A test (`client/src/lib/sect/clouds.test.ts`, "installed Ice-Fire steam") fails
if the steam ever floats above the island again.

**Next render batch.** Run the `clouds` step. It writes the same plume straight from the Blender file, which
replaces this data patch.

## 2. The flags had too few texels

**What was wrong.** Each flag's picture is baked into its area's shared texture. Texture detail is measured in
texels (texture pixels) per metre of cloth.

| Surface | Texels per metre |
|---|---|
| Wood, fire and earth flags (formation chunk) | 7.4 to 8 |
| Metal and water flags (abode chunk) | 3.9 |
| Gate banners | 16 to 30 |
| Arena hackathon banners | 11 to 29 |

So a 4.6 m flag was only about 37 texels wide, and the metal and water flags were about 18. Their characters
turned into blobs.

**Why.**

1. The bake gives each piece texels based on how close the camera ever gets. The flight never comes nearer than
   82 m to the flags, so they got about 8 texels per metre.
2. The export put the metal and water flags into the abode's chunk. That chunk asks for 4.6 times its texture budget,
   so everything in it was scaled down to 46% detail.
3. The rule that stops the bake from simplifying banner geometry only covers pieces within 80 m, so it never
   protected the flags.

High quality was already serving the full-size textures there, so this was not a quality-setting problem.

**Why not a client-only fix.** The page cannot sharpen texels that were never baked. Drawing new flag artwork in the
browser would fight the baked lighting and the character shapes, and the next bake would replace it anyway.

**The fix (needs a bake).**

- `export_web.py`: all five flags go to the formation chunk (`LORE_CHUNKS`).
- `bake_web.py`: flags get 3 times the texel density (`DETAIL_FULL`). They are also never simplified within 250 m
  (`NO_DECIMATE_FAR`).
- Expected result: about 21 to 25 texels per metre for all five flags, in line with the gate and arena banners. That
  adds about 80,000 texels to a chunk that has room for 11.5 million and uses 5.7 million.

**Bake needed.** Run `chunks,meta`, then `bakefull --chunks formation,abode,backdrop`. The bake takes about 8 to 9
minutes of GPU time on the last box. After that, run mist, pack and install. The client's `FLAG_FLIES.abode` entry
then finds no flag cloth and can be removed.
