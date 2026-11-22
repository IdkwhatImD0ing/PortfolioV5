# The top of the abode's waterfall

Added 2026-11-20. Page only: no bake, no new file. On 2026-11-22 the notch itself was rebuilt in the
scene and baked (round 62), and the pour's numbers were fitted again: see "The notch itself" below. The
numbers in "What was wrong" and "What changed" are the ones of the old V-shaped notch.

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
2. **It narrows to the notch and fans out below.** At the crest the sheets keep half their width.
   They reach their full width 14 m down, most of it in the first few metres. The streaks keep
   their baked spacing, so they spread out of the notch with the water. The three layers of the
   fall are baked a little to one side of each other; at the crest each is gathered on the notch's
   centre line.
3. **It steps back to the cliff's edge.** The crest moves 0.65 m toward the cliff, so the water
   comes out of the notch's mouth and not out of the air in front of it.
4. **Water fills the notch.** A strip of water lies in the notch behind the crest. It is level for
   the last 3 m and sinks to the notch's floor 8.5 m back, where the walls close over it. A view
   from above sees water in the notch.
5. **A deep lip.** The moved water is flagged for the shader (`aPour`). Where it goes over the
   edge it hides what is behind it (92 percent) and its top is one clean line: the water's level.
   Below that it thins to the usual see-through water.

The other falls are untouched. So are the foam, the spray, the wet rock and the waterfall's
hotspot: they read the foot and the corners from `meta.json`, which did not move.

## The sides (2026-11-21)

The owner, on the first version: "Unfortunately the sides still look very abrupt".

The fall was dense white right up to both edges, then bare rock. The edge was torn by noise, but
it was still one line, and nearly straight from top to bottom. From the stop it read as a white
ribbon cut out of the cliff.

Falling water is not like that. It is thick in the middle and thin at the sides, where it breaks
into separate threads and then spray. So for a pour the sheet shader now does this:

- **The water thins toward its sides.** Over the outer three quarters of each half (less at the
  crest, where the notch's walls hold the water together) the water keeps less and less of its
  opacity, down to 40 percent at the very side. The rock shows through it.
- **It breaks into threads.** A noise stretched tens of metres down the fall decides where water
  is left. Near the middle all of it passes. Toward the side only the strongest threads do.
- **The line wanders.** Where the threads start moves in and out by up to a third of the half
  width down the fall, so the outline is not ruled.
- **A little spray.** A faint white haze (12 percent) lies over the thin sides once the water has
  broken. None at the crest.
- **The sheets are 20 percent wider, all the way down.** Thinning the baked width would have left
  a narrow core. The extra width is where the thin water goes; the dense middle is about as wide
  as it was.

The numbers are in `SHEET` in `waterfall.ts` (`pourThin`, `pourCut`, `pourEdge`, `pourWander`,
`pourFaint`, `pourHaze`) and `widen` in the pour's spec.

Two tries on the way. A wide thinning with soft threads read as a blur. A narrow thinning with
crisp threads still had a clean edge at full size. What worked was a wide thinning, real
see-through water in it, and wider sheets.

## The notch itself (2026-11-22)

The owner, on the softer sides: "I mean like the sides of the mountain above the waterfall". He had
meant the rock, not the water. The notch's left side was a flat dark slab from the stop, and its
right side one straight edge. Round 62 rebuilt the notch in the scene as a cleft that turns as it
goes back and ends in a rock step, and baked the abode again:
[`../scene/notch-r62.md`](../scene/notch-r62.md).

The new notch has a level lip 5 m wide where the V had a point. So the pour's numbers changed.
Measured on the new bake, in the same frame as the table above:

| What | Old notch | New notch |
|---|---|---|
| The notch's floor at the cliff's edge | 0.6 m up | 0.3 to 0.4 m up |
| The notch's width at the water's level | 3 m at 2.2 m up | 5.1 m at 0.9 m up |
| The water level (`level`) | 2.2 m | 0.9 m |
| The crest's share of the baked width (`neck`) | 0.5 (2.9 m) | 0.86 (5.05 m) |
| The notch's centre line (`centre`) | 0.08 m left | 0.76 m left |
| The strip of water in the notch | 6 m wide, straight, 8.5 m long | 5.3 m wide, 3.3 m long, turning 0.37 m left per metre back |

The strip is new in one way: its middle follows the notch (`stream.bend`, `stream.bendFrom`,
`streamMiddle`). It is as wide as the water at the cliff's edge and no wider. The cliff's face
falls back on the left there, so a wider strip stood out in front of the rock as a ledge of water
with no fall under it.

## Cost

One extra draw of 112 triangles, one more number per water vertex, and one more texture read per
water pixel. The reshaping runs once per load on the abode's 4,180 water vertices. The probe's
frame counter read 58 to 60 before and after.

## How it was checked

`client/scripts/render-probe.mjs` at five views, High, before and after: arriving (frame 1352), the
stop with the view turned up (1380), flying past (1404), straight in front (1428) and from the
left (1452). In every view the water now comes out of the notch and widens below it.

The sides were checked at twice the size (the probe's `--dsf 2`) from the stop and from the front,
top and middle of the fall, and at normal size in the stop's own view, arriving and flying past.

`pour.test.ts` holds the shape: rows never cross, the water only widens on the way down, and below
the fan a point keeps its height. One test reads the shipped `meta.json` and fails if a new export renames the
sheet or drops its lip, which would switch the pour off without a word.

## What is left

- **The dark wall beside the crest** is gone since round 62 (see above). A dark pocket about 1 m
  wide is left at the lip's left: the left shoulder's shadow.
- **The numbers are read off this bake.** They ride on the fall's own lip and corners, so moving
  the area keeps them. A new cliff shape needs them measured again (the table above says what).
- **The stand-in quads keep four corners.** A set with no water file draws each fall as one quad
  from `meta.json`. No set does that today: both profiles load `abode_water.glb.gz`.
