# Round 57: a key light for the bake, and a richer grade

Status on 2026-11-10: baked for all eleven stops and the backdrop, installed in the client on the
branch. Part of the pull request opened on 2026-11-14.

## Why

The owner, 2026-11-10, after round 56: "Hm still doesnt seem photorealistic though". Then, after a
test at one stop: "Yes, roll it out", and "Make sure to go through multiple rounds across all scenes
to imrpove the quality".

The look he means is his own set of approved style frames,
`blender/xianxia-sect/out/higgsfield/film/v2/kf_<stop>.png`: golden-hour light with clear shadows,
rich greens, lit cloud. The page's look was tuned toward them, but two things held it back.

1. **The bake had no shadows worth the name.** The scene's sun stands 7 degrees up, so flat ground
   gets an eighth of it. The bake made up for that with a soft fill light 110 degrees across and a
   brighter sky. The fill lit the ground more than the sun did and cast no shadow, so lawns and
   plazas baked evenly lit.
2. **The page's grade took the colour out.** It removed all of green's lead over red and blue, so
   grass came out olive, and it held saturation at 0.86.

## What changed

**The bake's light** (`bake_web.py` `BAKE_LIGHT`, used by `bake_trees.py` too):

| | Until round 56 | Round 57 |
|---|---|---|
| Sky | the film's sky x 1.4, warmed | the film's sky x 1.0, warmed |
| Second light | a fill, energy 1.6, 110 degrees across, 32 degrees up | a key, energy 2.4, 6 degrees across, 27 degrees up |

The key comes from the sun's side, so shadows fall the way the sun's do. It is what lights lawns and
plazas now and gives every shadow an edge. The old values are kept as `BAKE_LIGHT_R56`.
`--light k=v,...` on either bake overrides the values for one run, for look tests.

Two other lights were tried on the mirror terrace first and dropped. Lowering the fill and the sky
(fill 0.5, then 0.12) only made the picture darker: with a 7 degree sun there is still almost no
light on flat ground.

**The page's grade** (`client/src/lib/sect/look.ts` `SECT_LOOK.grade`):

| | Before | Now |
|---|---|---|
| exposure | 1.42 | 1.42 |
| contrast | 1.16 | 1.24 |
| saturation | 0.86 | 1.0 |
| greenTame (share of green's lead removed) | 1.0 | 0.45 |
| shoulder (where highlights start to roll off) | 0.9 | 0.74 |
| split (how far highlights lean warm) | 0.34 | 0.28 |

The sun's haze glow went from 0.2 to 0.3.

The first version of this grade had exposure 1.52 and saturation 1.06. A review of the whole flight the
same day found that it blew sunlit marble out to a flat cream ribbon (the summit stairway, frames 1441 to
1537) and turned sunlit cliffs rust orange. The lower shoulder keeps form in the brightest stone, and
the smaller split takes the orange down.

**Mist** (`createCloudPuffMaterial`, `SECT_LOOK.puffs`): a puff is at least 0.4 as tall as it is wide
(was 0.24), its noise is less stretched along the level (1.35, was 2.1), and its sunward relief is
stronger. Lit colour `#ffe9c8`, shade `#c6aeb4`. It reads as lit cloud more than as smears. Past
300 m a puff under 36 m across fades out: from that far it was a white disc stuck to its pillar.

## How it ran

Two rented boxes on 2026-11-10.

- **The test, 11:02 to 11:47, $0.51.** Three draft bakes of the mirror terrace with three lights, then
  the mirror, gate, forge and backdrop at production quality with the key, and those three areas'
  plants.
- **The rollout, 12:36 to 13:53, $1.07.** The other eight stops at production quality (63 minutes)
  and every area's plants (70 minutes, of which 47 were the sun ray casts for 56,035 plants), side by
  side on one GPU. `sect_pack.py` found 0 problems in all 24 files.

The scene file did not change: it is still `out/sect_chase.r56.blend`.

## What it did not fix

Light and colour were the cheap part. Against the style frames the page still lacks dense real
pines, a full blossom tree, sharper rock and a glowing mirror. Those need models. The far forest's
flat tree cards are replaced in the same round of work: see
[`../sect/veg-shells.md`](../sect/veg-shells.md).

## Running it again

As round 56's run sheet ([`form-r56.md`](form-r56.md)), without a patch step:

1. Rent one RTX 5090. Upload `out/sect_chase.r56.blend` as `out/sect_chase.blend`, the audit cache
   and chunk plan, the small files in `out/web/full`, and `out/section_timeline.json`.
2. `bake_web.py -- bakefull --profile full --quality production --chunks <all twelve>`. Confirm the
   GPU in the first minutes.
3. `bake_trees.py -- plan,build --quality production` beside it, then `bake_trees.py -- instances`.
4. Fetch, check md5, `sect_pack.py --profile full`, `tools/sect_veg.py`, client tests, a sweep of
   the flight. Destroy the box.
