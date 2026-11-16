# Round 55: prop placement with intent

Status on 2026-11-10: done. The gate is a camera change in the client. The four Blender moves below were
applied to the scene and baked on the night of 2026-11-09 (the owner: "Yes, bake"), and the new files are
in `client/public/sect/full`. They are part of the pull request opened on 2026-11-14. How the run went, and
what it changed in this plan, is at the end.

## Why

The owner, 2026-11-09: "some of the objects in the scene are haphazardly placed".

To find out which, every stop was drawn as a plan from the builders' own coordinates and projected
into its hold camera (the drawings were checked against screenshots). Two different causes showed up.

1. **The camera, not the props.** The gate plaza is mirror-symmetric on its centre line, but the
   flight passes its stop 3 m to the right of that line. From there the right-hand lanterns hid behind
   a pillar and the left-hand ones showed in the open bays: three lanterns on one side, one on the
   other. Nothing in the scene was wrong. The fix is in the page: the camera steps onto the centre line
   at that stop (`client/src/lib/sect/framing.ts`, `side`).
2. **Props typed in one at a time.** At the forge, the mission hall, the jade slip pavilion and the
   mirror terrace, some yard dressing was placed as single hand-typed coordinates with no rule joining
   one piece to the next. Those are the moves below.

Each move follows one of three rules:

- **A formal place is symmetric on its axis**, and things along a walk keep one spacing.
- **Working things stand in groups that make sense as a workplace** (an anvil with its quench trough
  and its rack), not one by one across a yard.
- **Fewer pieces, each with a reason.** One piece is removed.

Kept out of this round on purpose: banners and flags (the page animates them by fixed regions in
`client/src/lib/sect/idle.ts`, so moving one means moving its region too), anything that is a
clickable item or carries a hover card, and trees (a moved tree needs the slow tree bake). The Five
Element flags at the formation stay on the east rim: five flags cannot be symmetric about an axis
that must stay clear for the walk, and their even spacing along the rim already reads as a rank.

## The moves

Coordinates are metres in each area's own frame (origin at the plateau centre, the visitor arrives
from -Y, +X is to the right on arrival). Rotations are degrees about Z.

### Forge (`sect/areas/forge.py`): a yard of two smith's bays

The east bay already exists and was fitted to the hold view in round 34: the five wheels on their
stand, an anvil and a quench trough (`SMITH_AT`, `SMITH_YAW`). The rest of the yard was single
pieces: two more anvils, a trough, three racks and five ore piles, eleven east of the axis and five
west.

| Object | From | To | Why |
|---|---|---|---|
| `forge.weapon_rack` | (-21, -21) rot 14.3 | mirror of the five wheels' stand: (-13.27, 3.75) rot -15.96 | the west bay's rack |
| `forge.anvil.002` | (-16, -24) rot 68.8 | mirror of `forge.anvil`: (-11.68, 0.59) rot 1.23 | the west bay's anvil |
| `forge.trough.1` and `forge.trough_water.1` | (18, -9) rot 0 | mirror of trough 0: (-15.72, 1.02) rot 74.04 | the west bay's quench trough |
| `forge.anvil.001` | (13.5, -17) | removed | a lone anvil under the artifacts' orbit, belonging to no bay |
| `forge.weapon_rack.002` | (21, 10) rot -14.3 | (24.3, 9.4) rot 90 | the two racks flank the east workshop's porch, 5.4 m either side of its centre |
| `forge.weapon_rack.003` | (24, 15.5) rot -14.3 | (24.3, -1.4) rot 90 | |
| `forge.ore.002` | (26, -4) | (25, 14) | mirrors `forge.ore.003` at (-25, 14): one pile at each workshop's hall-side corner |
| `forge.ore.001` | (-22, -30) | (-23.4, -26.6) | the ore yard by the bridge gate: three heaps together |
| `forge.ore.004` | (20, 26) | (-26.0, -29.6) | |

The west bay must be written as the mirror of `SMITH_AT` / `SMITH_YAW` in code, not as new literals,
so the two bays cannot drift apart.

### Mission Hall (`sect/areas/mission.py`): lanterns out of the Dipper

| Object | From | To | Why |
|---|---|---|---|
| `mission.stone_lantern` | (-5.2, -40) | (-5.2, -48) | the pair stood between the Big Dipper's star drums and broke its line; now it stands on the arrival landing and marks the way in, below the hold's frame |
| `mission.stone_lantern.001` | (5.2, -40) | (5.2, -48) | |

### Jade Slip Pavilion (`sect/areas/scroll.py`): one rhythm up the walk, the rocks given places

The walk's lantern pairs stood at y -13, -4 and 5 (9 m apart), then 14 m on at 19.1, then the door
pair at 23.1. The three scholar's rocks on their pedestals stood at three unrelated spots.

| Object | From | To | Why |
|---|---|---|---|
| `scroll.lantern_stone` | (8.4, 19.1) | (7.8, 14) | the walk keeps its 9 m beat all the way: -13, -4, 5, 14, then the door at 23 |
| `scroll.lantern_stone.001` | (15.6, 19.1) | (16.2, 14) | |
| `scroll.rock.1` and its pedestal | (22, -14) | (22, -10) | the two rocks of a height flank the way out to the side steps (its line is y -3.5), 6.5 m either side |
| `scroll.rock.2` and its pedestal | (-2, 21.5) | (22, 3) | |
| `scroll.rock.0` and its pedestal | (-23, 14) | (18.4, 8.4) | the tall rock stands by the peach, 5.1 m from the trunk on the visitor's side: a rock and a tree together, which also gives the peach on the paving a reason |

### Heart-Mirror Terrace (`sect/areas/mirror.py`): the west rock gets its companion

| Object | From | To | Why |
|---|---|---|---|
| `mirror.boulder.003` | (-21.5, -9.5) | (-24.4, -3.6) | the east scholar's rock has a boulder at its foot; the west one stood alone with its boulder 7.5 m off |

## What the run found

The scripts had never run in Blender before the box. The patch was rehearsed on a copy of the scene
first (`DRY_RUN=1`), and its own checks stopped it three times:

- **The tall rock stood inside the peach.** The first place for `scroll.rock.0` was 3 m from the trunk.
  Measured on the box, the peach's crown comes down to 1.5 m and reaches 4 to 5 m out, so a 4.5 m rock
  there had branches through the stone. It now stands 5.1 m from the trunk on the visitor's side, the
  nearest spot where it is clear of the crown (0.7 m from the nearest blossom).
- **The mission lanterns' new floor was not on the patch's list.** The arrival landing is its own slab
  (`mission.arrival`), level with the plaza. The check now knows it.
- **Racks and stone lanterns are built 3 mm above their floor**, at the old places too. The check asked
  for zero. It now allows 5 mm.

After those three fixes the rehearsal passed, and previews of the four holds were rendered before and
after and looked at. Nothing else needed moving. Two things the previews showed that are worth knowing:

- From the forge's hold the west bay is mostly behind the cauldron (and under the Projects panel). Only
  its trough shows. The bay is there for the fly-in and for a visitor who turns the view.
- The porch racks are seen end on from the forge's hold, because they face the yard and the camera
  looks along it.

The real patch then gave the same result as the rehearsal (digest `f8bdb49bf29667a4d11fe1e90c4ce103`).
The keep-list compare found 0 changes outside the moved pieces, 36 inside. The scene went from 13,692
objects to 13,691 (the anvil).

## How it ran

One rented RTX 5090, 2026-11-09 23:24 to 2026-11-10 01:58 Pacific: 2 hours 34 minutes. With the first box that failed, the night cost $2.16.

| Step | Time |
|---|---|
| Box setup, upload of the scene (177 MB, md5 checked) | 4 min |
| Rehearsals on a copy, measuring the peach and the landing | 20 min |
| Previews, before and after, 10 stills each (Cycles, 64 samples) | 7 min |
| The patch on the main file, keep-list compare | 4 min |
| Audit (see below) | 38 min |
| `chunks,meta` | 2.5 min |
| `bakefull` production: forge 21, mission 17, scroll 17, mirror 17, backdrop 8 | 83 min |

Three things did not go to plan:

- **The audit had to run again.** The copy of `out/web/full/vis_cache.npz` on the PC turned out to be an
  old one from before round 48 (92,824 pieces against the plan's 101,979), so the box had nothing to
  bake from. The new audit's chunk plan is the shipped plan minus the anvil: no piece changed chunk.
  The new cache is saved this time.
- **`tools/sect_pack.py` did not compile.** Since 2026-11-04 one of its byte strings had real line
  breaks in it where `\r\n` and `\n` belonged. Nobody had packed since. Fixed.
- **The first box refused the SSH key** for four minutes and was destroyed. The second one worked.

`meta.json` came out identical, so only the five baked files and the manifest changed in the client.

## Where the files are

- The patched scene is `out/sect_chase.r55.blend` in the main checkout (md5 `fc77d985c6c084a277e0322ecf8f4adb`).
  The round 54 file `out/sect_chase.blend` beside it is untouched (md5 `4a449cb8...`). When this branch
  is merged, the round 55 file becomes `sect_chase.blend` and the old one goes to `out/archive/`.
- This round ran from a git worktree. Its `out/` folder (gitignored) holds the round 55 audit cache,
  chunk plan, raw GLBs and pack work files; a copy of the small ones is in the main checkout under
  `out/r55/`. `tools/rblender.py` and `tools/sect_pack.py` now find the project from their own path, so
  they work from a worktree. The box still keeps its mirror at the main checkout's path, which is the
  path to write in Blender arguments.

## Running it again

Everything runs on a rented box through `tools/rblender.py`, never on the PC.

1. Keep-list dump: `patch_r48_keep.py -- MODE=dump LABEL=r55_before`.
2. On a copy: `patch_r55_placement.py -- DRY_RUN=1`, then without `DRY_RUN`, then `preview_r55.py`
   (`--tag after`, and `--tag before` on the untouched file). Look at them.
3. On the main file with `--fetch-blend`, then keep-list compare with
   `ALLOW=forge.,mission.stone_lantern,scroll.lantern_stone,scroll.rock,mirror.boulder`.
4. `export_web.py -- audit --profile full` only if `vis_cache.npz` is missing or older than the scene,
   then `export_web.py -- chunks,meta --profile full`.
5. `bake_web.py -- bakefull --profile full --quality production --chunks forge,mission,scroll,mirror,backdrop`.
   Confirm the GPU in the first minutes (the log line `BAKE cycles device`, and `nvidia-smi`).
6. On the PC: `sect_pack.py --profile full --only forge,mission,scroll,mirror,backdrop`, the client tests,
   and screenshots at `?frame=352`, `619`, `1103`, `217`.
7. Destroy the box.

No tree moved, so the tree bake is not needed.
