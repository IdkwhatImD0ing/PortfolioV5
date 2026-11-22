# Round 62: the notch above the abode's waterfall

Status on 2026-11-22: the scene is patched, the abode is baked again and installed in
`client/public/sect/full`, and the page's water is fitted to the new notch. Waiting for the owner's eye.

The water's own story (the pour, its sides) is in [`../sect/waterfall-pour.md`](../sect/waterfall-pour.md).

## What the owner saw

After the water was fixed: "Unfortunately the sides still look very abrupt", and then "I mean like the sides of
the mountain above the waterfall". The sides of the notch the water comes out of.

## What was wrong

The cliff's top is a grid: columns 0.8 m apart across, rows 1.2 m apart going back. The notch was a smooth dip
in the front edge (11 m deep, about 9 m wide at the top) that ran straight back through the whole top. So each
side of it was one plain ramp, as long as the cliff top is deep.

Two facts about the flight made that ramp ugly. Both were measured from `camera.json`, in the abode's own frame:

| Frame | Where the camera stands, seen from the notch | It looks up by |
|---|---|---|
| 1380 (the stop) | 23 degrees right of straight in front, 76 m away | 16 degrees |
| 1392 | 29 degrees right | 23 degrees |
| 1404 | 27 degrees right | 31 degrees |
| 1428 | straight in front | 35 degrees |
| 1452 | 27 degrees left | 27 degrees |

- The camera is on the right for the stop and the fly-past, so it looks at the notch's left side.
- The abode's light (the afterglow, round 61) comes from the front left. A side that faces right gets none.

So the left side was in view and in shadow for its whole length: one flat dark slab beside the water. The right
side was one straight diagonal edge.

## What was tried first

Each of these was rendered on the box before anything was baked.

1. **Four thin rock towers beside the notch.** `N.rock_pillar` under 5 m across reads as a stack of discs. They
   looked like posts, and the slab still showed between them and the water.
2. **A stepped cleft, and one large tower.** Steps looked right from the front and the left. From the right the
   left wall was still one dark blade: steps that all face right stack into one shape. The tower had to stand so
   far back to hide its base that it read as a stub.
3. **Smaller steps, uneven rims, boulders on the benches.** The same blade. The boulders sank into the steps.
4. **The cleft turned, with a sheer left wall.** This hid the wall (see below), but its top stood up as a thin
   spike, and the last straight stretch of it showed dark again.
5. **A deeper turned cleft with a knob left under a pine.** The cleft passed under the pine
   `abode.dense_top_pine.007`. Keeping a knob of old ground under it gave the knob a side that faced right: a new
   dark blade. Moving the pine would have meant baking the tree file again.
6. **A turned cleft with a steeper left slope (4.8 m across), baked once.** On the stills it looked done. On the
   page a crack 1.3 m wide and 5 m tall stayed beside the water, nearly black under the night grade. It was not
   the slope: it was the slope's shadow. The light comes over the left shoulder, and a steep shoulder shades the
   pocket behind it. Turning the left side faster changed nothing. A gentler shoulder did.

The lessons: nothing that faces right can be lit there, so dressing the wall does not help. It has to face
another way. And what stands on the light's side of the cleft has to be low enough to let the light in.

## The shape now

`blender/xianxia-sect/sect/areas/abode.py`, at `NOTCH_R62`.

- **The cleft turns.** Going back from the front edge its centre line moves left: one column for every row, which
  is 34 degrees. That is past the 29 degrees of the camera's furthest stand on the right. So the left side faces
  back and to the right, away from the camera at every frame of the flight: from the right, the front and the left
  alike. What shows on the left is the front face's own edge, lit, sloping down to the lip.
- **The left side is one long slope**, 11 m up over 7 m across. Since it is hidden wherever the camera goes, it
  does not have to be a wall. A slope gives the front edge a natural line, and a gentle one lets the light reach
  the rock behind it: the shadow in the mouth is now a pocket about 1 m wide and 4 m tall at the lip.
- **The right side** climbs in four risers with level benches, as in the stepped tries. It turns the same way, so
  it faces the front and the light. Its rims wander a little going back.
- **The floor at the lip is level for 4.0 m** (the page's water needs 3.2 m), and the lip is where it was.
- **The cleft has a head.** It climbs back out in two steps, 2.3 to 4.6 m behind the front edge, to a saddle
  1.2 m deep. That is short of the pine. A channel that went on straight would show its left wall through the mouth, and one that went on
  turning would pass under the pine. From below, the head is lit rock behind the water where the slab and the sky
  were.
- **The grid is split along the slope.** Blender cuts every four-sided face from its first corner to its third.
  Across a slope that moves one column per row, that cut made a row of teeth, each with a face to the right (the
  first stood at the front edge as a thin fin with a dark side). `abode.cliff_split` starts those faces one corner
  later, so each is cut along the slope's own line. 63 faces are turned. One is still cut the long way (Blender
  cuts a folded face its own way) and does not show.

Nothing changes more than 11 m left or 7.3 m right of the fall. No object is added, moved or removed, and the
ground under every pine is where it was.

## The patch

`sect/patch_r62_notch.py` puts the shape into a finished scene. It moves the cliff's vertices by the difference
between the old and the new analytic cliff (2,861 of 16,543 move, by up to 10.8 m), works the sharp edges out again
where vertices moved, and runs `cliff_split`. It checks the lip, the channel's width behind it, that nothing
rises into the water at its crest, that no other object or datablock changed, that every pine near the change is
still rooted, and that the camera never comes within 4 m of the moved rock. Run twice, it says nothing changed.
The patched scene's digest is `4641038cc7c5f437f31ad9cf5c4d5528`.

`sect/preview_r62.py` renders the notch from the flight's camera, turned as the page turns it and lit as the
abode's bake. A round of patch and six stills takes under a minute on the box, so shapes were judged on stills,
not on paper.

Because no object changed, the visibility audit and the chunk plan stand: the patch needs only the abode's bake.

## How it ran and what it cost

Two sessions on rented RTX 5090 boxes, 1.64 dollars in all. Both boxes were destroyed.

- 2026-11-21: three preview rounds (tries 1 to 3). 0.86 dollars. Nothing baked.
- 2026-11-22: nine preview rounds, two bakes of the abode at 768 samples (775 s each), the live calibration and
  the bounced light. 0.78 dollars. The first bake had the steeper left slope (try 6) and was replaced.

Installed: `abode.glb.gz`, `low/abode.glb.gz`, the abode's live maps and live index, and the abode's entry in
`manifest.json` (bytes, triangles, revisions). `meta.json`, the other ten stops, the backdrop and every tree and
water file are unchanged. Logs and stills: `blender/xianxia-sect/out/tmp/r62/` and `client/out/wf/` (not in git).
The patched scene is `out/sect_chase.r62.blend` in the worktree that ran it (not in git either).

## How to run it again

On a rented RTX 5090 set up with `tools/box/box_up.sh` and the round 61 scene:

1. `sect/patch_r62_notch.py` on a copy with `DRY_RUN=1`, then on `out/sect_chase.blend` with `--fetch-blend`.
   Run it once more: it must say nothing changed and print the same digest.
2. `bake_web.py -- bakefull --profile full --quality production --live --chunks abode --light "<the abode's
   twilight light>"` (the light is in [`night-r61.md`](night-r61.md)), then `sect/live_calib.py -- abode` and
   `sect/live_bounce.py -- abode`. No audit and no `chunks,meta`: no object changed.
3. On the PC: `tools/sect_live.py --chunk abode` and `tools/sect_pack.py --profile full --only abode`.

One trap in step 3. `--only` installs nothing unless the other areas' raw files and packed files are beside the
new one (it prints "partial run"), and that run overwrites `pack_stats.json` with the one file it packed. In a
fresh worktree, copy `out/web/full/bake/pack_stats.json` and `bake/packtmp/site/` from the worktree of the last
bake, and link or copy its `raw/` files. Check first that those packed files are the installed ones (this time
all 48 were, byte for byte).

## What the page does with it

The water is fitted to the new notch (`client/src/lib/sect/pour.ts`; the pour itself is explained in
[`../sect/waterfall-pour.md`](../sect/waterfall-pour.md)):

- The water level is 0.9 m above the lip point (it was 2.2 m, where the old V was wide enough to hold it). That is
  half a metre of water over the lip.
- The crest is 5.05 m wide (it was 2.9 m), as wide as the level lip, and sits 0.76 m left of the lip point.
- The strip of water inside the notch follows the turn (its middle moves 0.37 m left for each metre back), is
  5.3 m wide and ends under the head, 3.3 m behind the lip point.

## How it was checked

- The patch's own checks (above), twice, with the same digest.
- The 14 files of each bake had the same checksums on the box and on the PC.
- The pack's checks: 0 problems (validator, decoded triangles, node boxes, hotspots, textures).
- The page at 1600 x 900, before and after, from six views: arriving (frame 1352), the stop as it is (1380), the
  stop looking up at the notch, flying past (1404), straight in front (1428) and from the left (1452). High,
  Medium and Low. No page or shader errors. The stop's own view does not show the top of the fall and did not
  change.
- 2,775 unit tests, the type check and the lint pass.

## Limits

- The cliff top is still a coarse grid. The head's steps and the right side's risers are facets a metre across.
- A dark pocket about 1 m wide stays at the left of the lip. It is the left shoulder's shadow, and it is where
  the water comes out.
- From below, the notch no longer opens to the sky. The moon shows over the head, not through a V.
- No water runs down the head. The water wells up at its foot.
- A fresh build of the abode makes the same cliff, but would seed the cliff-top pines on the new ground. The
  patched scene is the one that was baked.
