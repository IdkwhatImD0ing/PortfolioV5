# The top of the abode's waterfall

Added 2026-11-20. Page only: no bake, no new file.

## What the owner saw

"The top of the waterfaw at the abode looks very low quality, cab we do something abou tit?"

## What was wrong

The cliff above the Cave Abode has a notch in its top for the waterfall. The notch is a V: about
9 m wide at the top and no width at all at its lowest point.

The water is baked as three flat sheets, each as wide as the whole fall (6 m). Their top row hung
level with the V's lowest point, half a metre in front of the cliff. So from the stop:

- 3 m of water on either side began on bare rock, along one ruled line.
- The notch above it was empty. Sky and trees showed through it. Nothing fed the fall.
- The first metre of water is drawn see-through (a glassy lip), so the ruled line was faint and
  dotted with the lip's highlights.

Measured on the baked cliff, in the fall's own frame (origin at the lip point in `meta.json`,
metres across, metres out of the cliff, metres up):

| What | Where |
|---|---|
| The notch's floor at the cliff's edge | 0.6 m up |
| The floor 2 to 8 m behind the edge | 0.1 to 0.4 m up, then it drops away (the back of the ridge) |
| The notch's opening at 2.0 m up | 2.8 m wide |
| The notch's opening at 2.4 m up | 3.3 m wide |
| The cliff's face under the notch | 0.55 m behind the lip point |
| The baked sheets' top row | 0.5 m up, 5.9 m wide |

## What changed

A "pour" reshapes the top of the fall when the page loads the water (`client/src/lib/sect/pour.ts`,
applied by `applyPours` in `assets.ts`).

1. **The water rises into the notch.** The sheets' top goes up 1.65 m, to a water level 2.2 m above
   the lip point. There the notch is about 3 m wide. The lift fades out over the first 6 m of the
   fall, so the foot and the pool are where they were.
2. **It narrows to the notch and fans out below.** At the crest the sheets keep 58 percent of their
   width. They are back to full width 14 m down, most of it in the first few metres. The streaks
   keep their baked spacing, so they spread out of the notch with the water. The three layers of
   the fall are baked a little to one side of each other; at the crest each is gathered on the
   notch's centre line.
3. **It steps back to the cliff's edge.** The crest moves 0.65 m toward the cliff, so the water
   comes out of the notch's mouth and not out of the air in front of it.
4. **Water fills the notch.** A strip of water lies in the notch behind the crest. It is level for
   the last 3 m and sinks to the notch's floor 8.5 m back, where the walls close over it. A view
   from above sees water in the notch.
5. **A deep lip.** The moved water is flagged for the shader (`aPour`). Where it goes over the
   edge it hides what is behind it (92 percent), its sides are whole for the first metre, and its
   top is one clean line: the water's level. Below that it thins to the usual see-through water.

The other falls are untouched. So are the foam, the spray, the wet rock and the waterfall's
hotspot: they read the foot and the corners from `meta.json`, which did not move.

## Cost

One extra draw of 112 triangles, and one more number per water vertex. The reshaping runs once per
load on the abode's 4,180 water vertices. The probe's frame counter read 60 before and after.

## How it was checked

`client/scripts/render-probe.mjs` at five views, High, before and after: arriving (frame 1352), the
stop with the view turned up (1380), flying past (1404), straight in front (1428) and from the
left (1452). In every view the water now comes out of the notch and widens below it.

`pour.test.ts` holds the shape: rows never cross, the water only widens on the way down, nothing
moves below the fan. One test reads the shipped `meta.json` and fails if a new export renames the
sheet or drops its lip, which would switch the pour off without a word.

## What is left

- **The dark wall beside the crest.** It is the notch's left side, in shadow in the night bake. It
  is flat and dark next to the lit rock. Only a bake changes it.
- **The numbers are read off this bake.** They ride on the fall's own lip and corners, so moving
  the area keeps them. A new cliff shape needs them measured again (the table above says what).
- **The stand-in quads keep four corners.** A set with no water file draws each fall as one quad
  from `meta.json`. No set does that today: both profiles load `abode_water.glb.gz`.
