# The flight sweep: looking at every half second of the film

On 2026-11-10 the whole flight was looked at frame by frame, twice, to find what still looked
cheap. This page says how, what changed in the page because of it, what was tried and taken back,
and what was left for Blender.

## How

1. One frame in every 12 of the 1729 (a frame every half second of film) was captured from the
   real page at 800 x 450, plus the views to the left, right and behind at each of the eleven stops.
   That is 177 frames and 33 turned views a pass.
2. Three readers went through the contact sheets and wrote down every flaw with its frame and
   place. They were told the style is deliberate and to list only what a careful viewer would call
   a fault.
3. Every claim was then checked on the full size frame before anything was changed. About a third
   did not hold up. A "missing roof" was a roofed gallery round a court. "Hard lines where cloud
   meets rock" were mostly dark ridges in front of bright cloud.
4. After the fixes the sweep was run again on different frames and read again.

The capture jobs are small JSON files run by one Playwright snippet. Comparing against the main
checkout's dev server (the scene before the change) on the same frame was the quickest test of
whether a change helped.

## What changed in the page

**Mist.** The puffs round the pillars read as stickers, and thin banks seen edge on read as tape.
The puffs now end in a wide soft rim, a puff is never less than a quarter as tall as it is wide,
and it is thinned by the height it gains. Big banks keep the smooth body they had. Getting here
took three tries: thinning the mist all the way through by the noise looked good on small rings
and blotchy on every bank near the camera. Code: `createCloudPuffMaterial` in
`client/src/app/sect/experience/materials.ts`.

**Turned views.** At the summit the film looks 12 degrees up at the moon. A visitor who turned
round kept that tilt and saw sky. Now a view that the film tilts up comes down to 4 degrees below
the horizon as it turns away, so behind the summit lies the whole sect. A film pitch that is level
or down is left alone. Code: `turnLevel` in `client/src/lib/sect/free-look.ts`.

**Light beams.** From a kilometre off a beam was two pixels wide and read as a scratch on the sky.
A beam is now never narrower than a small angle, and dimmer for the width it gains. Code:
`createBeamMaterial`.

**The summit.** At the stop the pavilion's finial touched the moon's lower edge. The stop now
stands 8 frames back, where the moon hangs clear. Code: `STOP_FRAMING.summit` in
`client/src/lib/sect/framing.ts`.

## Tried and taken back

- Drawing steep grass faces as stone, and breaking the baked moss into noise patches, to hide the
  teeth where grass meets cliff. Neither reached them: the teeth are in the scene's own geometry.
- A lower shoulder on the grade, to bring shading back into the white stair walls. They are flat
  white in the bake itself, so there was nothing to bring back.
- A soft top layer on the cloud sea and a height-based blend of rock into the sea's colour, to
  soften the sea's shores. No visible change: the hard edges people saw there are ridge outlines.
- A sideways step at the end of the film, to move the finial off the moon's centre line in the last
  frames. It changed the stop more than it helped the ending.

## Left for Blender

These were in the scene, so they needed a bake. Round 56 fixed them later the same day
([`../scene/form-r56.md`](../scene/form-r56.md)):

- teeth where a terrace's grass meets the cliff;
- a step ring round the mirror terrace's lawn (and the cave abode's);
- stair side walls that bake flat white;
- the arena sword's broad faces all one tone;
- the plank bridge to the arena island hanging only 2 m over 113 m.

Known and left alone: the sword and a hall roof cross the view in a few transit frames (the
film's own path), the stele forest's side views look at its gate pillars, and a far mesa shows as
a pale disc on the cloud sea from the summit.
