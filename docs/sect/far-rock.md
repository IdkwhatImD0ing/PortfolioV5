# Far spires that read as rock

Status on 2026-11-10: on the branch, every tier that draws detail. Part of the pull request opened on 2026-11-14.

## Why

A review of the whole flight on 2026-11-10 put this first: far rock spires looked like smooth tan
tubes, in about two thirds of the frames. The owner had said the same in his own words: "far away
objects show up as blocks which breaks the immersion".

The cause is how far things are stored. The always-loaded backdrop holds the far peaks (`far.c<n>`)
and a reduced stand-in of every area (`proxy.<area>`). It is baked as one colour per point, with no
texture and no detail class, so the page drew it with nothing on top. The near cliffs get a rock
layer from the page; it fades out by 700 m, and the spires stand 0.5 to 3 km off.

## What changed

- **The far peaks are rock.** `prepare.ts` gives the far set a copy of the backdrop's material
  tagged as rock (`baked.vc.far.rock`), so it takes the range's rock colour like the near cliffs.
- **A rock layer at the size of a spire.** With `SECT_FAR_SET` the rock layer is read again with no
  distance fade (`detail.ts` `DETAIL_LOOK.rockFarSet`): once enlarged (50 and 160 m noise), once
  squeezed along the height for vertical flutes, once at its own size for strata, plus level ledge
  lines 13 m apart.
- **Stand-ins get it on their rock only.** A stand-in holds an area's buildings too. With
  `SECT_STANDIN` the layers are kept only where the baked colour is rock-like (warm with red ahead
  of green ahead of blue, not lacquer red, not marble white, or grey, dark and steep). Walls, roofs
  and paving get their baked colour back.

- **A stand-in does not read the built mask (2026-11-15).** Rock on the range is pale with dark
  streaks, except under anything built. That mask fills as each area's set loads, so a stand-in
  lost its range look once its own area had been loaded and went back to a smooth tube. Now it
  looks the same whatever has loaded. See [`background-fill.md`](background-fill.md).

One trap on the way: the loader strips the dots from node names, so `far.c0` arrives as `farc0`
under `backdropfar`. `isFarSetMesh` accepts both.

## Not done

- The spires are still the low-polygon shapes they were. The layer changes their surface, not their
  outline.
- A flat disc of a mesa stands in the cloud sea west of the summit and reads as a pie dish from the
  abode and the summit's side views. It is part of the far set and needs a change in the scene.
