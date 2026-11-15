# Round 56: form and edges

Status on 2026-11-10: baked and installed in the client on the branch. The owner said "Yes, run 56"
that morning. Part of the pull request opened on 2026-11-14.

## Why

The owner, 2026-11-09: "some of the objects in the scene are haphazardly placed and the quality is
not good enough".

Round 55 took care of the placing. On 2026-11-10 a sweep of the whole flight looked at every half
second of the film ([`../sect/flight-sweep.md`](../sect/flight-sweep.md)). It found five flaws that
live in the scene itself, so no change in the page can fix them:

1. Teeth where a terrace's grass meets the cliff.
2. A dark step ring round the mirror terrace's lawn, and the same at the cave abode.
3. Stair side walls that bake as flat white sheets.
4. The arena's Heavy Iron Sword reads as one dark slab.
5. The plank bridge to the arena island looks like a straight ramp.

Every part keeps every object's name. The web export keys everything on names, so no part needs the
slow audit.

## What changes

### A. Rim: grass ends on a level line

The range's top is a grid of 2.5 m squares, and each square is either grass or rock. Near a
terrace, a square was grass when two of its four corners (one diagonal) lay on the flat. The square
is drawn as two triangles split along that same diagonal. So a grass square that crossed the rim
kept its top edge on the flat and hung a green triangle over the cliff. Its far corner could sit up
to 1.8 m past the flat, and the cliff there drops 2.4 to 4 m for every metre out, so that corner
hung several metres down. The rock squares beside it poked up into the grass. Seen from the
flight, that alternation is a saw-tooth.

Now a square near a terrace is grass only when all four corners are on the flat
(`world.RIM_RULE`, in `terrain_data`). Every square that crosses the rim becomes rock. The rock's
own lip moss (`materials.ROCK_LIP_MOSS`) greens the top of those squares, so the edge reads as moss
rolling over the lip.

The change can only turn grass into rock, and only on squares that cross the rim. A check on a model
terrace confirmed that: 23 of 1,760 grass squares near its rim turned to rock, all of them crossing
it, and none went the other way. The patch logs the real counts for each terrace.

The patch changes the material of those faces and nothing else. It does not move a vertex, change
a face, or touch the tree mask (`world_veg`). It first rebuilds the range's mesh data with the same
settings the scene was built with (the round 48 record on `world.range`) and stops unless its faces
match the scene's exactly.

Re-bake: every area chunk and the backdrop, because the range has faces in all of them.

### B. Lawn: no step ring

The mirror lawn is a disc of radius 43 m whose edge stopped 0.15 to 0.25 m above the terrace, with
an open gap under it. That gap and its shadow made the dark ring. The abode's lawn
(radius 50 m) did the same, 0.02 to 0.38 m up.

Now each lawn's outer band dives under the terrace, as the library's lawn already does
(`mirror.lawn_edge`). Past a start radius the lawn bends smoothly down to 0.6 m under its own zero
at its edge. Then the existing `seat_lawn` cuts it 4 cm above the terrace and drops the rest out of
sight. What you see is a lawn ending in a 4 cm soil lip on the terrace.

At the mirror the dive starts at r 40 (`mirror.LAWN_EDGE`). Nothing that stands on the lawn is past
r 40: the pines stand at 35.4 to 38 m and the path lanterns reach 39.2 m. A model of the lawn's mesh
says the ground under the lanterns' outer feet moves by about 1 mm, and the lip lands at r 41.2 to
41.5. The two paths that cross the edge now reach 0.6 m down instead of 0.35 m
(`mirror.PATH_BOTTOM`), so their sides do not hang over the lowered lawn.

At the abode the dive starts at r 49.55 (`abode.LAWN_EDGE`), so only the lawn's outermost ring of
points moves. The first plan was r 49. The lawn's mesh is rings of points 0.73 m apart, each jittered
by up to 0.22 m, with one ring at r 48.55 just inside the rail and the next at r 49.28. Moving any
point past r 49 would have tilted the faces the rail's posts stand on by 2 to 6 cm. From r 49.55
nothing inside r 49.06 changes, and the new lip lands at r 49.2 to 49.8, at least 0.6 m outside the
rail.

These things stand past r 48.5, and none of them moves:

- the stone rail itself, at r 48.5, whose posts reach about r 48.6;
- the two stone lanterns at the depart landing, at r 49.1. Within 0.9 m of each the lawn stays as it
  is, and the dive comes back in over the next 0.8 m (`abode.LAWN_KEEP`);
- the arrival and depart landing slabs, which cross the rim. Both reach into the terrace (bottoms at
  -0.6 and -0.5), so they keep their footing;
- the depart steps and their apron, which stand on the terrace past the lawn;
- the garden scatter's plants, which can grow anywhere the mask allows, out to r 50.

The patch still stops if the ground under anything inside the start radius moves more than 2 cm,
which is how deep the rail sits in the lawn.

Re-bake: mirror, abode and the backdrop. The paths' boxes grow 0.25 m down, so `chunks,meta` runs
first.

### C. Stair walls: weathered white marble

The link stairways' side walls (`world.link.*.rails`, `.foot_rail`, `.rest_rail`) were in
`marble_white`. Its veins are under 2.5 cm wide and its warm patches barely change its value. The
bake gives these walls 3 to 20 texels a metre, so all of that vanished and the walls baked flat.

They now get their own material, `world_wall_marble` (`materials.wall_marble`). It keeps
`marble_white`'s colour, veins and tint and adds features that are 10 cm or wider:

- grime at the foot, up to 30 % toward a grey-brown, gone by half the wall's height, its top edge
  broken by patches about 1 m across;
- rain streaks hanging from under the top, 18 % darker, 0.5 to 1.9 m long and roughly 0.8 m apart;
- panel joints along the run, a 10 cm soft band with a 3 cm core, 25 % darker;
- one course line 0.3 m under the top, and a slight tone change per panel (3 % either way).

The joint spacing is the run length divided into equal panels near 2.2 m. A 30 m run gets 14
panels of 2.14 m and a 150 m run gets 68 of 2.21 m, so long runs land inside the 2.0 to 2.4 m
target. Short walls do not always fit: a 5 m wall gets two panels of 2.5 m.

To know where it is on a wall, the material reads two per-point attributes, `arch_gen` and
`arch_dims` (how far along the run, which face, how high, and the run's size). The bake already
copies both into its bake mesh. The patch writes them from each wall's own mesh with
`world.wall_coords`, after a strict check that the mesh is exactly what the stair builder lays down.
If any wall fails that check, the patch stops. `WALLS_MODE=A` is the fallback: it needs no
attributes, gives the walls grime and vertical streaks from world-space noise, and has no joints.
A fresh build writes the same attributes through `_prisms_obj`, so a fresh build and a patched
file match.

The walls stay clearly white marble. This is a well-kept sect, and the effect is weathering only.

Re-bake: gate, mirror, forge, library, steles, scroll, formation, abode, summit and the backdrop.
Those are the chunks that hold link walls.

### D. The Heavy Iron Sword: three tones on each face

The bake drops metalness and keeps only the base colour. The iron is very dark, so the blade's
three facet bands baked within 5 % of each other and the sword read as one dark slab with a thin
light outline.

Two changes, with the shape untouched:

- The two side facet bands of each broad face are now marked as half-worn (`arena.HS_SIDE_EDGE`,
  0.45). The middle band stays plain and the rounded edges stay fully worn.
- The blade, guard and pommel use `props_iron_heavy`, the iron with a lighter worn-edge colour
  (`#a0a0a6`, was `#8a8a8e`). Its name keeps the `props_iron` start that the bake looks for, so the
  web still adds the sky reflection for metal.

A rough estimate of the base colours before lighting: the middle band stays at 0.26 on a 0 to 1
scale, the side bands go from 0.26 to 0.44, and the rounded edges from 0.50 to 0.58. That gives
three clear tones across each face. The geometry is identical in both versions, checked face by
face. The patch reuses `patch_heavy_iron_sword.rebuild()`, the existing in-place rebuild with its
own checks.

Re-bake: arena and the backdrop.

### E. The bridge to the arena island hangs

The plank bridge from the forge to the arena island is 113.1 m long and climbs 23.7 m. It sagged
only 2 m, so it read as a straight ramp. It now sags 5.5 m (`world.FORGE_ARENA_SAG`), for this link
only.

What the new shape does, from the same numbers the builder uses:

- It still has 323 planks. The 22 planks on the level 4 m at each end do not move, so the posts and
  both bridgeheads are untouched.
- It still rises the whole way. The slope runs from 1.1 degrees at the forge end to 23.4 degrees at
  the arena end. The walking limit is about 29.5 degrees.
- Every step is at most 0.169 m high (the limit is 0.17 m) and every tread at least 0.35 m deep (the
  limit is 0.30 m).
- At mid-span the deck sits 5.5 m below a straight line between the ends, and up to 3.56 m lower
  than it does now.

A sag of 5.9 m or more would make the deck dip before it climbs. 5.5 m keeps it rising.

The patch builds the bridge with both sags and first checks that the scene's bridge matches the
2 m build, every point within 1 mm. A mismatch would mean a port has moved, and the patch stops. After the swap it
checks that the deck stays at least 2 m over the range along the middle 80 % of the span and never
goes into it, and that the lower bridge touches nothing it did not touch before.

Re-bake: forge and the backdrop.

## What the run found

One rented RTX 5090 ran all five parts on 2026-11-10. Every part went in.

Three checks in the patch were tighter than the real file could meet. Each was looked into and then
loosened:

- **The range against its recipe.** The range rebuilt from the round 48 record has the same 428,834
  faces as the scene, and the old rule gives every face near a terrace the material the scene has.
  But 83 of its 214,414 top points sit 1 mm to 2.8 cm off sideways. They are scattered over the
  whole range, none nearer than 38 m to a terrace's centre and none on a face the rule changes. Why
  was not traced. The scene was built on another machine. The check now allows 5 cm, and it refuses
  any changed face that uses such a point (`RIM_XY_TOL`, `RIM_XY_FACE`).
- **The abode lawn's frame.** The lawn sits at its area's origin. At world coordinates past 1,000 m
  the two matrices still differ by 0.04 mm from rounding. The check now allows 1 mm (`ROOT_TOL`).
- **Plants on the abode lawn's rim.** The garden scatter draws its plants face by face, so the faces
  the dive re-made drew new ones. Six plants went (four grass tufts and two shrubs, all past r 49.3)
  and two came (a grass tuft and an azalea). Inside r 49.12, where no face changed, the other 86
  kept their places. The check now guards that radius and lists the rest.

What each part did:

- **Rim.** 243 squares turned from grass to rock and none the other way: gate 23, mirror 24, forge
  28, arena 0, mission 25, library 22, steles 26, scroll 21, formation 33, abode 25, summit 16.
- **Lawn.** The mirror's lawn went from 18,219 to 18,558 points and nothing inside r 40 moved. The
  abode's went from 24,305 to 24,697. The ground under its two depart lanterns moved 7 mm and 3 mm.
- **Walls.** All 17 wall objects passed the layout check, so mode B ran, joints and all.
- **Sword.** The same 5,842 triangles with the new tones.
- **Bridge.** The deck stays 20.5 m or more over the range along the middle of the span and touches
  only the two bridgeheads, as before. Its lowest and highest points are still its two ends, so its
  box did not change.

The keep-list compare found no change outside the seven objects the patch may touch. `meta.json`
came out identical.

On the page, twelve frames were captured before and after the install at 1600 x 900: the eight in
the run sheet, the mirror and abode stops, and frames 250 and 1320. The teeth are gone, the bridge
hangs in a curve and the sword shows three tones. The mirror lawn's dark ring is now a thin lip.
The lawn still reads as a lighter disc on darker ground, because the lawn and the terrace are two
grass materials. The walls' joints show on the near stairways (frames 121 and 250). From 110 m
(frame 1500) a sunlit wall is still a bright white ribbon. Medium and Low were spot-checked and
load the new files.

Two shrubs fewer meant the abode's plant file had to be rebuilt. Without that, two bushes would
have hung in the air over the lowered lip. `bake_trees.py -- plan,build --quality production --only
abode --only-recs --out out/r56trees` took 20 minutes beside the bake. The new `abode_trees.glb` has
the same nodes, materials and textures as the old one and 2,000 fewer triangles, which is the two
shrubs. The new azalea and grass tuft are in no web file yet. The audit has never seen them, so the
export leaves them out until the next audit.

## Files

- `blender/xianxia-sect/sect/world.py`: `RIM_RULE` and `_rim_mats` in `terrain_data`;
  `WALL_MATERIAL`, `wall_coords`, `wall_attrs`, `set_wall_mode`; `FORGE_ARENA_SAG`, `LINK_SAG`.
- `blender/xianxia-sect/sect/lib/materials.py`: `wall_marble`, sharing `_marble_base` with
  `marble_white`.
- `blender/xianxia-sect/sect/areas/mirror.py`: `LAWN_EDGE`, `PATH_BOTTOM`, `edge_dive`,
  `lawn_edge`; `seat_lawn` can now work on part of a lawn.
- `blender/xianxia-sect/sect/areas/abode.py`: `LAWN_EDGE`, `LAWN_KEEP`, `DEPART_LANTERN_AT`,
  `lawn_edge`.
- `blender/xianxia-sect/sect/areas/arena.py`: `HS_SIDE_EDGE`, `HS_EDGE_COL`, `props_iron_heavy`.
- `blender/xianxia-sect/sect/patch_heavy_iron_sword.py`: `rebuild()` without the save.
- `blender/xianxia-sect/sect/patch_r56_form.py`: the patch.
- `blender/xianxia-sect/sect/preview_r56.py`: the before and after stills.

Every round 55 value is kept beside its replacement (`RIM_RULE_R55`, `LAWN_EDGE_R55`,
`PATH_BOTTOM_R55`, `WALL_MATERIAL_R55`, `HS_SIDE_EDGE_R55`, `HS_MATERIALS_R55`, `LINK_SAG_R55`).
The patch uses them to tell an unpatched file from a patched one.

## Run sheet

This is how the round ran, and how to run it again. It rents a GPU box. Everything runs on the box
through `tools/rblender.py`, never on the PC. Paths are as in round 55: the box keeps its mirror at the main
checkout's path.

1. Rent one RTX 5090 with a desktop CPU (skip host 366851). Upload `out/sect_chase.r55.blend` as
   `out/sect_chase.blend` and check its md5 is `fc77d985c6c084a277e0322ecf8f4adb`. Upload the round
   55 audit cache from `out/r55/web/full` to `out/web/full` (`vis_cache.npz`, `chunks.npz`,
   `chunks.json`), the other small files in that folder, and `out/section_timeline.json`. The
   wrapper does not send those, and the export and the tree plan stop without the timeline.
2. Keep-list dump: `patch_r48_keep.py -- MODE=dump LABEL=r56_before`.
3. Copy the scene to `out/r56try.blend` and render the before stills on it:
   `preview_r56.py -- --tag before`. This also saves the close-up boxes, so the after stills frame
   the same thing.
4. Dry run on the copy: `patch_r56_form.py -- DRY_RUN=1`. Read the log. It should list the rim
   counts per terrace, every wall's runs, the lawn checks and the bridge's clearance, and end with
   `PATCH CACHES needs chunks,meta; bakefull gate,mirror,forge,arena,mission,library,steles,scroll,formation,abode,summit,backdrop`.
   - If it stops on a wall's layout, add `WALLS_MODE=A` to every later run.
   - If it lists `PLANTS on the re-made rim faces`, run `bake_trees.py -- plan --out <folder>` on
     the file before and after the patch and compare the two `plan.json`. A change in an area's
     counts means that area's plant file needs step 11.
5. Real run on the copy with the same options. Note its `PATCH DIGEST`.
6. After stills on the copy: `preview_r56.py -- --tag after`. Look at all 18 pairs. If something
   looks wrong, stop here.
7. The main file, with `--fetch-blend`: `patch_r56_form.py` with the same options. Its digest must
   match step 5. Keep the result as `out/sect_chase.r56.blend` and note its md5.
8. Keep-list compare: `patch_r48_keep.py -- MODE=compare LABEL=r56_after
   REF=out/tmp/r48/keep_r56_before.json
   ALLOW=world.link.forge_arena.bridge,mirror.lawn,mirror.path_main,mirror.path_forge,abode.ground,abode.garden_scatter,arena.sword`.
   The walls and the range only change materials and attributes, which the keep-list does not
   record, so they should not show up.
9. `export_web.py -- chunks,meta --profile full`. The audit is not needed, because no name changed.
10. `bake_web.py -- bakefull --profile full --quality production --chunks
    gate,mirror,forge,arena,mission,library,steles,scroll,formation,abode,summit,backdrop`. Confirm
    the GPU in the first minutes (the `BAKE cycles device` line and `nvidia-smi`).
11. Only if the tree plans differ: `bake_trees.py -- plan,build --quality production --only abode
    --only-recs --out out/r56trees`, then put its `raw/abode_trees.glb` in `out/web/full/raw/`. It
    can run beside the bake.
12. Fetch the raw files and check them against the box's md5. On the PC, at below-normal priority:
    `sect_pack.py --profile full --only` with the twelve chunk names and `abode_trees`, the client
    tests, and screenshots at `?frame=889`, `1069`, `193`, `121`, `1500`, `516`, `469` and `421`.
13. Destroy the box once the pack reports 0 problems.

## How it ran

One rented RTX 5090 (Vast host 346497, a Ryzen 9 7950X with 93 GB of memory), 2026-11-10 08:04 to
09:52 Pacific: 1 hour 48 minutes, $1.34.

| Step | Time |
|---|---|
| Box setup, upload of the scene (177 MB, md5 checked) | 1 min |
| Keep-list dump, two dry runs, a diagnostic and the fixes between them | 7 min |
| The patch on a copy | 2 min |
| Stills, 18 before and 18 after (Cycles, 64 samples) | 5 min |
| Tree plans, before and after | 3 min |
| The patch on the main file, keep-list compare | 3 min |
| `chunks,meta` | 3 min |
| `bakefull` production, all twelve | 83 min |
| The abode's plant file, beside the bake | 20 min |
| Pack, check and install on the PC, 13 files | 1.5 min |

The bake took 83 minutes against the 94 in `bake_web.py`'s header, with the plant build sharing the
GPU for 20 of them. The GPU drew 375 to 395 W on OptiX. Round 55's host drew 270 W and took 2 to 2.4
times the header's numbers, so the host matters more than anything else in the plan.

The patch's digest was `7695493ea3af1be583a89ec39986a457` on the copy and on the main file.
`sect_pack.py` found 0 problems. All 1,947 client tests pass.

## Where the files are

- The patched scene is `out/sect_chase.r56.blend` in the main checkout (md5
  `03b2fd96917412d869129f1da0605a71`). The round 55 file and the round 54 `out/sect_chase.blend`
  beside it are untouched. When this branch is merged, the round 56 file becomes `sect_chase.blend`
  and the old ones go to `out/archive/`.
- `out/r56/` in the main checkout holds the new chunk plan, the twelve raw GLBs, the abode's plant
  file, the keep-lists, the tree plans and the 36 stills. On a merge its `web/full` goes over
  `out/web/full`. The audit cache is still round 55's.
- The worktree's own `out/` (ignored by git) has the full working set.
