# Round 61: the abode and the summit baked at night

Status on 2026-11-17: baked, installed in `client/public/sect/full`, tuned on the page and approved by the owner.
The page side (the moon look's new numbers and the warm keep) is in [`../sect/lux.md`](../sect/lux.md).

## Why

The flight runs from sunrise at the gate to night at the summit, by colour grading only (the journey,
`client/src/lib/sect/journey.ts`). Until this round every chunk was baked under the film's sunset sun (azimuth
252, 7 degrees up). So the last two stops were night frames lit by sunset light: shadows fell the sunset's way,
and the grade had to turn warm sunlit stone into blue night. Their lanterns glowed but lit almost nothing round
them. The owner approved re-baking the two stops.

## What changed in the bake scripts

All in `blender/xianxia-sect/`.

- `sect/bake_light.py` (new): the pure rules of a night bake, with no Blender in it. The night keys
  (`NIGHT_DEFAULTS`), the two presets (`night`, `twilight`), the parser for `--light`, the checks, the
  direction maths, which materials count as lamps and lanterns, the lamp boost factor and the night sky's
  colour. Tested offline by `tools/test_bake_light.py` (prints `test_bake_light ok`).
- `sect/bake_web.py`: `--light <preset,key=value,...>` sets the light for one run. With `night=1`,
  `night_scene` re-aims the scene's sun lamp to the night key (in memory only), turns the warm key lamp off,
  swaps the film's sky for a graded night sky and boosts the lamps' emission for light that reaches other
  surfaces (never for the camera or the lamp's own inside). Each chunk's bake meta records the light it was
  baked under, and the live index (`live/<stop>/index.json`) writes it: the sun is the night key as baked,
  the key lamp's strength is 0. A day light (`night=0`) bakes exactly as before.
- `sect/bake_trees.py`: `night_guard` refuses a night light unless it has its own cache folder
  (`--cache-dir`), writes only the chunks it is for and never runs `instances`. The trees were not re-baked
  this round.
- `sect/preview_r59.py`: `--bake-light <spec>` renders stills lit and graded as the bake would, to try a light
  before paying for a bake.
- `sect/areas/summit.py` and `sect/patch_r61_lanterns.py`: the summit's new lanterns (below).
- `tools/box/box_up.sh`: strips Windows line ends from the setup script before it goes to the box.

## The two lights

| Stop | Hold | Preset and changes | Key from | Key | Sky | Lamps |
|---|---|---|---|---|---|---|
| abode | 1380 | `twilight,key_color=0.72/0.82/1.0,sky_lobe=0.3,lamp_boost=600,lantern_boost=192,boost_near=0.6,boost_far=2.5` | azimuth 252, 28 degrees up | strength 2.5, colour 0.72/0.82/1.0, 40 degrees across (soft) | graded blue, a faint warm lobe low in the west | lamps x600, lanterns x192 |
| summit | 1647 | `night,key_az_deg=45,key_elev_deg=22,lamp_boost=400,lantern_boost=256,boost_near=0.6,boost_far=2.5` | azimuth 45, 22 degrees up (the moon's side) | strength 4, colour 0.8/0.88/1.0, 3 degrees across | graded night blue | lamps x400, lanterns x256 |

- The abode is blue hour: its own 60 m cliff hides the moon, so the light comes from the afterglow in the
  west. No sunset sun and no warm key.
- The summit is full moon: a cool white key from the moon's side.
- The bake is "day for night": the atlases are bright, and the page's grade makes them night.
- The boost skips rays shorter than 0.6 m and is whole from 2.5 m, so a stone lantern's paper core and its own
  stone housing do not wash white.

## The summit's new lanterns

At the summit's hold only the qin lamp in the pavilion's open bay was lit. Ten lanterns were added, all from
prototypes the scene already had:

- a ring of eight round hanging lanterns, one at each pavilion column head, hung from the bracket band or the
  eave (the abode tea pavilion's lantern);
- a pair of 2.4 m stone lanterns on the top tier behind the pavilion (the stair head's spot mirrored to the
  back, since the condor crag hides the stair head at the hold).

`sect/areas/summit.py` places them on a fresh build. `sect/patch_r61_lanterns.py` puts the same ten objects
into an existing `out/sect_chase.blend` and checks them: hung or standing, clear of columns, rails and stairs,
never in the camera's way, and in the hold's frame. The scene file of this round is
`out/sect_chase.r61.blend` (not in git). 42 pieces were added to the summit chunk.

## How it ran and what it cost

Two sessions on one rented RTX 5090, 1.89 dollars in all. Logs and stills: `out/tmp/r61/` (not in git).

- Abode at 768 samples: 832 s.
- Summit at 768 samples: 975 s. It was baked again at 2048 samples (2136 s) for less noise in the lantern
  pools, and that one is installed.
- Then on the box: the live calibration (`sect/live_calib.py`), the bounced light and soft shadow
  (`sect/live_bounce.py`) and the verify stills. On the PC: the live maps (`tools/sect_live.py`) and the pack
  (`tools/sect_pack.py`). The box was destroyed at the end.
- Installed: `abode.glb.gz`, `summit.glb.gz` and their `low/` copies, the live maps and live index of both
  stops, and the manifest's revisions. The other nine stops, the backdrop and every tree file are unchanged.

## How to run it again

For one stop, on a rented RTX 5090 set up as in [`light-r57.md`](light-r57.md), with the night light in quotes:

1. `bake_web.py -- bakefull --profile full --quality production --live --chunks summit --light "night,key_az_deg=45,key_elev_deg=22,lamp_boost=400,lantern_boost=256,boost_near=0.6,boost_far=2.5" --samples 2048`
   (the abode: `--chunks abode --light "twilight,key_color=0.72/0.82/1.0,sky_lobe=0.3,lamp_boost=600,lantern_boost=192,boost_near=0.6,boost_far=2.5"`, 768 samples).
2. `sect/live_calib.py -- <stop>` and `sect/live_bounce.py -- <stop>`, as in
   [`../sect/live-gate.md`](../sect/live-gate.md) ("Running it for a stop").
3. On the PC: `tools/sect_live.py --chunk <stop>` and `tools/sect_pack.py --profile full --only <stop>`.
   The live maps only fit the chunk file of the same bake run: always do both.

To try a light before baking, render stills with `sect/preview_r59.py --bake-light "<the same spec>"`.

## What the page does with it

The moon look was retuned for the new bake (`client/src/lib/sect/looks.ts`): lantern light keeps its amber
against the blue, the live light adds what the bake had, and sun shafts and cloud shade are off at night.

The two chunks are also seen from far off long before their stops, under a gold or day sky, beside chunks
still baked at sunset. There the night bake read as cool grey or dark slate (frames 880 and 1160 were the
worst). So up to the scroll the page pulls their texels back toward the old sunset bake, with a gain per
face fitted on the old atlases against the new ones (`client/src/lib/sect/night-bake.ts`). The pull fades
out between frames 1156 and 1191, so the formation, the abode and the summit look as tuned.

Numbers and checks for both in [`../sect/lux.md`](../sect/lux.md) ("The night re-bake").

## What the page-only test taught

Before the bake, a test lit the lanterns on the page alone (a post pass, behind a switch). It is gone, but it
taught four things the bake had to respect:

- Light added before the frame grade is turned grey-blue, or treated as a glow. That is why the grade got a warm
  keep.
- Blue stone times amber light reads pink.
- With no shadows, a lantern lights the roof above it.
- A lamp only shows where a lamp is in view: the abode read, the summit (one lantern in frame) did not.

## Limits

- The trees were not re-baked. Their cards and crowns still carry the sunset bake's light and direction.
- The abode's cave screen (inside the moon gate) and the summit's qin lamp are not boosted, so they light only
  as much as their plain emission does. The boost only lights more from pieces that carry a `glow` property
  (`bake_light.boost_factor`), and the qin lamp has none (`GLOW piece summit.qin_lamp glow=None` in the logs).
- The backdrop and the other nine chunks are unchanged. A night stop seen from the formation shows the new
  light; the formation itself is still lit by the sunset.
- The bake moves frames before the scroll too, where the two chunks are seen from far off. Against the site
  before, at 400 px wide: 619 0.3%, 720 4.0%, 880 4.1%, 974 0.9%, 1103 1.1%, 1160 8.2%. The page's pull
  toward the sunset bake brings their colour back (the summit's cone at 1160 from a dark slate 114, 111, 125
  to 171, 152, 146; it was 182, 160, 153), but it cannot move baked shadows, so the shares only drop to 0.2,
  3.6, 3.6, 1.0, 0.8 and 7.0%. The summit's lawns and the spires west of its cone stay a little darker than
  before. While the pull fades (1156 to 1191) the two stops show their night light under a still lavender
  sky: at 1180 the cone is a dark shape against the moon.
- The summit's rock beside the pavilion faces away from the moon, so it stays a dark shape (the page lifts it
  a little).
- A look cannot move a baked shadow: the night shadows are right only at these two stops.
