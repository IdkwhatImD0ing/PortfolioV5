# Round 59: more bake texels for the rock the holds see; a new rock material and real ledges tried and left off

Status on 2026-11-12: tested on a rented box, and nothing on the page changed. No production bake ran. See "How it
ran". The round had three parts, and only one of them is kept:

- **The texel floor (A)** passed its plan-only gates and a test bake of two areas. It stays on in the code
  (`ROCK_FLOOR = True`) but was not baked for production: its gain at the page's size is too small to pay for a
  145 minute bake on its own. It goes out with the next full bake.
- **The rebuilt rock material (B, C)** failed its look review and is off (`ROCK_STRUCT = False`, the default).
- **Bake-time relief (E)** failed its look review and is off (`RELIEF = False`, the default; `--relief` turns it on).

The code of all three stays in the repo, with its tests, for a later rock round. The material and the relief plug
together through the `geo_w` attribute; each part can still be turned on without the others. The rest of this page is
the plan as built, corrected for what the session changed. The run sheet is kept for a later round that turns a part
back on.

**If the relief is turned on, the film and every scene preview stop matching the web rock.** The relief is applied
only to the bake's copies of the meshes. `out/sect_chase.blend` keeps the old shapes, so a Cycles render of the scene
(the film, `preview_r56.py`, `preview_r59.py --relief none`) shows the rock as it was. Only `preview_r59.py --relief on`
and a bake with `--relief` show the relieved rock. While the relief is off, as it is now, they match.

## Why

Reviews score how real the scene reads at about 4.5 of 10 and name the rock at all eleven stops: no mid-scale shape
(ledges, strata, blocks), smeared or blocky textures, and thin cracks that look drawn. Two things cause most of it.

- **The rock material draws its cracks.** `materials._rock` paints Voronoi joints as dark lines (cells about 6 m
  across and 83 m tall, stretched 13 times along z), 33 m water stains, object-space strata bands and a mottle bump. At bake density those turn into ink lines,
  stripes and crumpled paper.
- **Most rock in a hold's frame has about 1 texel a metre.** 71 to 80 % of the rock pixels at the mirror, forge and
  scroll holds are 250 to 400 m away. One texel covers about 5 screen pixels there, so the photo and any structure
  blur away (attack_2's measurements on the shipped GLBs).

## How it ran (2026-11-12)

One box, Vast instance 60435948: an RTX 5090 with a Ryzen 9 9900X3D, 0.694 US dollars an hour, up from 18:11 to
19:43 Pacific. The session cost 1.07 dollars (credit went from 10.77 to 9.70). The box was destroyed afterwards and
the instance list was empty.

The scene was the round 56 file (md5 `03b2fd96917412d869129f1da0605a71`). The material was only ever patched into
copies of it (`out/r59try.blend`, `out/r59try3.blend`). The steps ran in chains, each with its own log.

| Step | Time (Pacific) | What it showed |
|---|---|---|
| Rent, set up, upload | 18:11 to 18:26 | the scene's md5 matched |
| Keep-list, inspect, a copy | 18:26 to 18:28 | 4,844 location objects listed. The four main rock tags equal today's graph; the forge's tomb rock says `neither`, as expected; no material carries the cairn or flute tag. 86 objects carry `nature_top_radius`, 160 floating rocks get `rock_flat`, no mesh has `geo_w` |
| Before stills, patch dry run, patch the copy, after stills | 18:28 to 18:33 | 10 of the 12 planned stills each way: the library and arena close-ups found no rock to aim at. Every object unchanged. The new shader rendered each still in the same seconds as the old |
| The two missing close-ups before and after, then relief off and on (6 stills each) | 18:33 to 18:38 | the arena close-up falls back to a floating rock; the library close-up still found no rock. 82 relief targets. The in-memory setup took 76 s with the relief, 50 s without |
| The library close-up and six new shots before and after (7 stills each), then relief off and on (9 stills each) | 18:41 to 18:50 | the first try stopped in its first seconds and ran clean the second time. Now 18 stills per material version and 15 relief pairs |
| Plan only, all eleven areas | 18:52 to 18:57 | the floor's and the relief's plan gates passed, except a third atlas at the steles |
| Material tuning pass 1 (`after2`), steles plan again | 19:00 to 19:06 | the patch's first try stopped at once and ran clean the second time. The new atlas refit brings the steles back to 2 atlases |
| Material tuning pass 2 (`after3`) | 19:06 to 19:09 | almost the same picture as pass 1 |
| Test bake with the floor: steles and abode, then `verify` | 19:11 to 19:29 | the first try crashed after the atlas build (fixed, below); the second ran end to end |
| The same without the floor, then `verify` | 19:29 to 19:42 | for comparison |
| Destroy | 19:43 | instance list empty |

### The material (B, C): failed, off

The first build was reviewed on 11 stills: the ten that rendered and the arena close-up. Three lens reviewers looked
at it (geology, art direction, artifacts), one reviewer compared the pictures blind, and a skeptic checked every claim
against the pictures and the code. The skeptic's verdict: the new rock looked worse than today's in 9 of 11 stills, the
same in 2 and better in none. The blind reviewer preferred today's rock in 10 of 11 and called 1 a tie.

Look gate items 1 (plaid at the forge), 5 (masonry) and 6 (brightness) failed. Items 2, 3 and 4 passed: no
hairlines, the boulders and floating rocks clean, the karst columns unchanged. The brightness gate allows about 5 %;
`abode_1380_close` came out 6.1 % brighter and `steles_974_close` 7.6 %.

The faults the skeptic confirmed:

- **Near-black bed bands** across the abode and steles cliffs, about a quarter of the brightness of the rock around
  them. Most of the dark came from the Bump itself: an overhang's roof faces down and loses its light under the
  7 degree sun. The albedo cavity added the rest.
- **Wide winding dark-and-tan ribbons** on the mirror's sloping slab. A level bed cut by a gentle slope draws a contour
  map, and the beds had no steepness fade.
- **A block-wall grid** on the terrace cliff behind the forge.
- **A joint like a marker stroke** in the arena close-up.
- **Thin rings round the library's rock tower.** That tower is a kept cone of `world.range`, not a column, so no
  object property turns its beds off.

Tuning pass 1 (tag `after2`) took the skeptic's values, and they are now the defaults in `materials.py`:
`ROCK_STRUCT_BUMP` 0.8 to 0.45, `ROCK_CAVITY` joint and overhang 0.30 to 0.12, `ROCK_BED` hard 0.30 to 0.20 and
hard_pale 0.2 to 0.08, and two new keys. `ROCK_BED` steep (0.62, 0.42) keeps the beds to steep faces. `ROCK_BED` gap
(18.0, 0.38, 0.62, 0.15) and `ROCK_JOINT` gap (24.0, 0.36, 0.60, 0.10) make the beds and joints come and go along a
face. In its stills the structure hardly shows, and the rock is close to the plain photo.

Tuning pass 2 (tag `after3`) used overrides on the patch only: bump 0.62, cavity joint 0.18 and overhang 0.2, hard
0.26, gap floors 0.35 and 0.3. It gave almost the same picture as pass 1: the two differ by at most 0.5 of 255 per
still, on average over the still.

A blind recheck put today's rock against `after3` on 12 stills. Two blind reviewers saw each pair with its two sides
swapped between them. Today's rock won 9 of 12 with one and 8 of 12 with the other; `after3` won 2 with each, and the rest
were ties.

Two things held in every version. The two close stills stayed 6 to 8 % brighter than today's, because the old
graph's dark drawn cracks and stains are gone. And every reviewer, blind or not, named the same strongest tell: the
rock photo's web of small crack cells (`marble_cliff_06` at its 8.14 m tile) reads as dried mud or crazy paving. No
new version scored above 5.5 of 10 with any reviewer of the material.

Decision: the material is not shipped. `ROCK_STRUCT = False` is the default. The graph, the patch, the twin module
`rock_struct.py` and its test stay in the repo for a later rock round.

### The relief (E): failed, off

The relief was judged on 15 pairs of stills, off and on. It ran in memory on 82 objects: 61 columns, 20 floating
rocks and the abode cliff. The mean move was 0.50 m and the largest 3.00 m. The setup took 76 s, of which the relief
itself took about 24 s; the rest is gathering and copying the scene, which the relief-off run does too. These stills
ran on the patched copy, so their material was the first build. The review had three lens reviewers (attachment and seams,
form, mesh artifacts), one blind reviewer and a skeptic.

- **The abode cliff: dropped.** Its sunlit left shoulder turns into a fan of 6 to 8 long creases that read as pleated
  cloth. A patch of the lawn shows through on a new ledge beside the bamboo left of the door. Where the rock moved, the
  material's painted beds fade out (they give way wherever `geo_w` is above 0), and nothing sharp takes their place.
  The pleats and the lawn show at the page's size in both abode stills. From the formation hold the pleats are still
  there as a few fine streaks, and the lawn shows only when zoomed. The cliff's dressed zones held: the door,
  plaque, inscription, balcony, waterfall and pool were pixel-identical.
- **The floating rocks:** no visible change in any still. Their mean moves were 0.03 to 0.47 m.
- **The columns: a small gain on near columns** (forge 352, steles 974, arena 516, mission 619, the right columns at
  gate 93). Rounded tubes become flat faces with crisp vertical edges, with no pleats and no bubbles round shelf
  plants. Small and far columns and the summit crag did not change. One fault: at gate 93 the far-left column, at the
  frame's edge, was shaved away from a side shrub and from the rope bridge's anchor.

Decision: the relief is not shipped this round. `RELIEF = False` is the default in `bake_web.py`, and the new flag
`--relief` turns it on (`--no-relief` is still accepted). The columns are the part worth taking up again, with the
bridge anchor pinned and stills at turned views.

### The floor (A): passed, on, not baked

The plan-only run covered all eleven areas. It ran with the relief on for the columns and floating rocks and the
cliff left out (`--relief-only '^(?!abode\.cliff$)'`). In every area the rest of the chunk keeps 93.0 % or more of
today's linear density, which is what the rule promises:

| Area | Rest keeps | Floor texels | Atlases |
|---|---|---|---|
| gate | 95.8 % | 1.77M | 4096+4096, as the last bake |
| mirror | 93.0 % | 2.02M | 4096+2048, as the last bake |
| forge | 93.5 % | 3.21M | 4096+4096, as the last bake |
| arena | 93.0 % | 2.11M | 4096+2048, as the last bake |
| mission | 93.0 % | 2.05M | 4096+2048, as the last bake |
| library | 93.0 % | 1.98M | 4096+2048, as the last bake |
| steles | 95.5 % | 2.63M | 4096+4096+2048, one more than the last bake's 4096+4096 (fixed, below) |
| scroll | 93.5 % | 1.90M | 4096+2048, as the last bake |
| formation | 100.0 % | 0.85M | 4096, as the last bake |
| abode | 93.0 % | 2.23M | 4096+2048, as the last bake |
| summit | 98.1 % | 1.08M | 4096+4096+2048, as the last bake |

What the floor buys, in rock texels a metre before and after. At the gate, rock 60 to 120 m from the holds goes from
5.5 to 10.9, rock at 120 to 250 m from 1.6 to 5.4, and rock at 250 to 400 m from 1.3 to 4.0. So the far rock gets
about three times as many texels a metre. At the abode, rock at 30 to 60 m goes from 13.7 to 19.8 and rock at 60 to 120 m from
7.4 to 12.4.

The steles' third atlas came from the floor. It cuts rock into parts, and the greedy grouping then leaves more room
unused at the end of each atlas. Fixed in code: `bake_rules.greedy_groups` works out how many atlases the chunk makes
without the floor, and `bake_rules.refit_groups` brings the floor's grouping back to that count. The steles plan then
logged `ROCK FLOOR refit: 3 atlases back to 2; 5 items moved, 1 forced; fullest atlas 100.8 % of its room`, and the
test bake 101.3 %. "1 forced" means one item fit nowhere and went into the atlas with the most room; the packer
shrinks that atlas's layout slightly to fit.

The relief's plan gate passed in the same run, though the relief is off now. Every `PLAN RELIEF LOD` line ended
`none dropped`. The relief floors added 30.4k triangles at the gate, 40.4k at the forge, 10.1k at the mission, 50.6k
at the library and 23.9k at the steles: about 155k in all, under the gate's 60k a chunk and 250k in all.

Then a dev test bake of steles and abode, with the floor and without the relief, ran end to end on the round 56 scene
and today's material: steles in 251.7 s and abode in 142.9 s, OptiX on the RTX 5090. The first try crashed after the
atlas build, because the refit code had reused `bake_chunk`'s variable `idx`. Fixed: the refit's names now start with
`rf_`. The same two areas were baked without the floor (250.2 s and 143.0 s, so the floor costs no bake time), and
both bakes were rendered with `verify`. Viewed at twice the page's size, the abode cliff's cracks are a little sharper
with the floor. At the page's size the two renders look the same, and nothing else in the two areas changed visibly.

Decision: that gain is too small to pay for a 145 minute production bake on its own. The floor stays on in the code
(`ROCK_FLOOR = True`) and rides with the next full bake.

### The stills tool (D)

`preview_r59.py` changed during the session; section D below has it as it is now. The close-ups try faces turned
toward the camera first, with up to 3000 rays (`PICK_TRIES`). A ray that stops on the shot's own rock within 12 m of
the point counts as seeing it (`NEAR_SURF`), because a column's rendered surface sits metres off its own mesh. A shot
can name fallbacks (`alts`): the arena hold cannot see its island's underside, so its close-up falls back to a
floating rock. The library close-up aims at the big tower, which is part of `world.range`. Six shots are new:
`forge_352_close`, `gate_93`, `mission_619`, `mission_619_close`, `scroll_1103` and `formation_1208`.

The box setup ran from a script in the session's scratchpad. The box scripts are now in
`blender/xianxia-sect/tools/box/` (`vast_rent.py`, `box_up.sh`, `box_setup.sh`; step 1 of the run sheet). The setup
now downloads Blender from the Berkeley mirror (`mirrors.ocf.berkeley.edu`) first, because the official server gave
one box 10 KB/s, and checks the archive against Blender's official sha256 list.

### Lessons

- Under a 7 degree sun, structure drawn through a Bump reads as painted lines. Strong enough to see, the Bump's own
  shade turns a recess near black. Toned down, it disappears. Beds need real geometry or a baked displacement.
- Moving the vertices of a coarse mesh gives pleats and soft lumps. The cliff needs a finer mesh before it can take
  real ledges.
- The rock photo is the strongest tell left, in every version: its web of small crack cells reads as dried mud.

What the reviews point to for the next rock round, in order:

1. A better base rock photo first. The crackle web was the strongest tell in every version.
2. Beds as real shape (finer cliff meshes, or a baked displacement) before any more painted structure.
3. The column relief again, with the gate's bridge anchor pinned.

## What was built

Each part says first whether it is on. The text is the plan as it was built, with the session's changes in.

### A. A texel floor for rock the holds see (`bake_web.py`, `bake_rules.py`)

**On** (`ROCK_FLOOR = True`), not baked for production yet. It goes out with the next full bake.

Rock faces that a hold camera sees from the front get at least `min(1130 / d, 24)` texels a metre, d being the
median hold distance of their distance bin. That is 3.8 texels a metre at 300 m (today about 0.85), 9.4 at 120 m
and 24 nearer than 47 m (the page's fine rock layer covers nearer rock).

- **Hold views.** Each stop's hold camera looking forward and turned 60 degrees left and right, for the chunk's own
  stop and the two stops each side of it (the page draws those chunks there). The frame is widened to 1.3 x 1.5 in
  NDC for the page's framing turns and formation's -8 degree pitch. A face counts only if it faces the camera.
- **Paid inside today's budget.** `FULL_ATLASES_BY_AREA` does not change, so no atlas grows. Everything else in the
  chunk keeps at least 93 % of today's linear density (about 86 % of its texels). The bins (0, 30, 60, 120, 250,
  400 m) are filled nearest first. The bin that does not fit is scaled down, and the bins past it get nothing, so far
  rock never takes texels from near rock (`bake_rules.floor_reserve`).
- **No extra atlas.** The floor cuts rock into parts, and the greedy grouping then leaves more room unused at the end
  of each atlas, so it can open one more atlas than the chunk had (the steles did, in round 59's plan).
  `bake_rules.greedy_groups` works out the chunk's atlas count without the floor, on today's demands. When the floor's
  grouping comes out with more, `bake_rules.refit_groups` moves the last atlas's items, largest first, into the
  earlier atlas with the most room. An item that fits nowhere is forced into the atlas with the most room, and the
  packer shrinks that atlas's layout to fit. The refit is skipped with `--rock-floor-units`, which is meant to try a
  bigger budget.
- **Decide first, split last.** The floor is worked out before any mesh is cut. A kept part becomes its own item
  `<name>.rh<bin>`; the rest of the item keeps its name and density; an empty rest is dropped. On the split range a
  part also takes the ring of faces round it, so the density step lands in the grass beside a rim, where the page's
  ground layer covers it. A part must gain at least 5 % or it is not cut out.
- **One line per chunk** in every run, plan-only included, for example round 59's abode:
  `ROCK FLOOR abode: scale today 0.464 -> rest 0.432 (keeps 93.0 % of today's linear density); floor 2.23M of 11.53M texels (1.25 atlases); texels a metre by bin: 0-30 m 0.0 (was 0.0, 0 of 0 parts); 30-60 m 19.8 (was 13.7, 2 of 3 parts); ...`.
  The plan-only summary repeats it as `PLAN ROCK FLOOR <id>: ...` with the chunk's atlas sizes added at the end
  (`; atlases 4096+2048 px`), after any refit. A refit adds its own line:
  `ROCK FLOOR refit: 3 atlases back to 2; 5 items moved, 1 forced; fullest atlas 100.8 % of its room`. The same
  numbers go to `bake/chunks/<id>.json` and `plan_<id>.json` under `rock_floor`, the refit's under
  `rock_floor.refit` (`moved`, `forced`, `over`, `atlases_before`, `atlases`).

| Option on `bake_web.py` | Default | Use |
|---|---|---|
| `--no-rock-floor` | off | today's plan exactly, for A/B and for a bake without the floor |
| `--rock-floor-units x` | off | try a budget of x atlases per chunk in a plan-only run (never less than the chunk's own; no refit) |

### B. The rock material rebuilt (`materials.py`, `ROCK_STRUCT`)

**Off** (`ROCK_STRUCT = False`, the default). It looked worse than today's rock as first built, and no better when
toned down ("How it ran"). The text below describes what `ROCK_STRUCT = True` builds, with tuning pass 1's values,
which are the defaults in `materials.py` now.

`_rock` hands over to `_rock_r59` when `ROCK_STRUCT` is True. `ROCK_STRUCT = False` builds today's graph exactly.

- **Gone:** the Z-stretched Voronoi joints and their seep, the 33 m stains, the object-space strata bands and bed
  lines, the pits, and the mottle and fine bumps. Today's graph has five Bump nodes; the new one has two (the
  structure and the photo's own).
- **Kept exactly:** the `marble_cliff_06` photo, its 8.14 m tile, plane offsets, blend and mix, so the page's rock
  band stays registered. Also the tonal zones, the lichen, the rock life layer and the per-object tint.
- **World beds.** Level beds 1.8 to 5.6 m thick (2.75 m on average) that wander 2 m over 50 m and dip about 2 degrees.
  They are in world space, so they line up across objects. A fifth are hard beds (30 % in the first build) that
  stand out 0.25 to 0.5 m; the height eases into the next bed over the top 0.6 m of a bed, which makes shelf tops and
  overhang roofs. The soft bed under an overhang is cut back 0.25 m and darkened; a shelf's lip is drier and paler.
  Each bed is up to 0.05 lighter or darker, eased into the next over the top fifth of a bed. Hard beds lean a little
  toward a paler sandstone (8 % of its colour; 20 % in the first build).
- **Beds only on steep faces, and not everywhere along them** (new in tuning pass 1). A level bed on a gentle slope
  draws wide winding ribbons, a contour map, as on the mirror's slab. So the beds fade in on faces steeper than about
  52 degrees from level and are whole from about 65 degrees (`ROCK_BED` steep). A ledge at one strength from wall to
  wall reads as a ruled line, so an 18 m noise takes the beds down to 15 % of their strength in places (`ROCK_BED`
  gap).
- **One set of master joints.** A 2D Voronoi on world x, y, wandering 1.5 m over 20 m of height, so its edges are
  near-vertical joints about 12 m apart. A groove 1.2 m across and 0.35 m deep, 12 % darker at its centre (30 % in the
  first build), only on steep faces. Each block between joints is up to 0.03 lighter or darker, also on steep faces
  only (on a flat top the 2D cells would read as crazy paving). A 24 m noise takes the joints down to 10 % of their
  strength in places (`ROCK_JOINT` gap), so no groove runs one width down a whole cliff.
- **One structure Bump, continuous everywhere.** A step in height bakes as a one-texel hairline (attack_2). Every
  height term is continuous across bed boundaries and joint edges; `tools/test_rock_struct.py` checks it on the numpy
  twin (`sect/lib/rock_struct.py`). Its strength is 0.45 (0.8 in the first build, which turned overhang roofs and
  joint walls near black under the low sun).
- **Where it stays off.** Beds are off on objects with the float property `nature_top_radius` (`peak_pillar`,
  `rock_pillar`: the karst pillars, the abode pinnacles, the summit crag carry modelled beds), on the floating rocks
  (bake_web flags their bake pieces `rock_flat`, see below), and on the boulders, the forge's tomb and cairn stones and
  the flute's stone (variants with bed 0). Joints there run at half strength, or at the variant's joint scale. Beds and
  joints fade out where a POINT attribute `geo_w` is above 0 (the relief writes it on rock it relieves, and
  `bake_web.COPY_ATTRS` carries it onto the bake mesh) and on the vertex-colour bake mesh (the backdrop).
- **Weathering follows the beds, partly.** Streaks hang from the beds' tops instead of the 11 m lines, strongest under
  shelf lips and overhangs, and the recess under an overhang is damp. The moss cushions stay on today's 11 m lines:
  they sit on the real 11 m ledges of the range's kept cones (`world.py _strata`), which the world beds do not follow
  (attack_2). Where the beds are off (objects with their own beds, the backdrop, rock where `geo_w` fades them out),
  the streaks keep the 11 m lines too.

**Floating rocks.** No property in the scene marks a `nature.floating_rock`, and this round touches no object. So
`bake_web._full_item` gives the bake pieces of objects matching `ROCK_FLAT_RE` (`arena.island`, `arena.islet`,
`scenery.island`, `world.islet`, `world.link.arena_mission.stone`, `nature.floating_rock`) the property
`rock_flat` = 1, which the material reads as an OBJECT attribute. The scene file itself renders beds on them;
`preview_r59.py` sets the same property in memory so its stills match the bake. With today's material the property does nothing.

### C. The patch (`sect/patch_r59_rock.py`)

**Not applied to the scene.** Round 59 ran it only on copies on the box.

Rebuilds every material whose builder is `_rock` in place, under its own name, with its own parameters. No object is
touched. Before anything it compares each shipped node tree with a throwaway build of today's graph (every node's
settings, input values to 4 decimals, images, ramps and links). A difference stops the patch and lists it, except on
the forge's tomb and cairn rock and the flute's stone, which no earlier rock patch rebuilt (`STALE_OK`). `MODE=inspect`
reports without changing anything. Prints `PATCH DIGEST` and `PATCH CACHES needs bakefull ...`.

The patch builds whatever `materials.ROCK_STRUCT` says. Now that the default is False, a run meant to apply the new
material needs `ROCK_STRUCT=True` after `--`. Without it the patch builds today's graph, so the new material is not
applied; only the forge's tomb rock, which is older than today's graph, gets rebuilt to it.

### D. The stills (`sect/preview_r59.py`)

Cycles on the box GPU (refuses the CPU), 1600 x 900, 64 samples, never saves. Eighteen stills by default. Round 59
started with twelve and added six during the session:

| Shot | What it frames |
|---|---|
| `abode_1380`, `_close` | the abode's hold; close on its cliff (`abode.cliff`) near the frame's centre |
| `library_772`, `_close` | the library's hold; close on steep rock of the columns or of `world.range` near the frame's centre. It lands on the big tower left of the pagoda, a kept cone of `world.range` |
| `steles_974`, `_close` | the steles' hold; close on the cliff behind the pavilion |
| `mirror_217`, `_close` | the mirror's hold turned to the cliff under the hall; close on it |
| `forge_352`, `_close` | the forge's hold, far rock 250 to 400 m off where beds and joints could read as plaid; close on a column (new) |
| `gate_93` | the gate's hold (new) |
| `mission_619`, `_close` | the mission's hold; close on a column (new) |
| `scroll_1103`, `formation_1208` | those holds (new) |
| `arena_516`, `_close` | the arena's hold; close on the island's underside, or a fallback |
| `summit_1647` | the summit's hold |

How a close-up finds its rock. The candidates are the shot's rock faces, at most 40,000, and only steep ones (|normal
z| under 0.75) where the shot asks. Faces in the frame are tried nearest its centre first, faces turned toward the
camera before the others, with at most 3000 rays (`PICK_TRIES`). A ray that stops on the shot's own rock within 12 m
of the point counts as seeing it (`NEAR_SURF`): a column's rendered surface sits metres off its own mesh. A shot can
name fallbacks (`alts`), tried in order. The arena hold sees neither the island's underside nor its wall, so its
close-up falls back to a floating rock in the frame, 135 m off (`fallback 2` in its log line).

`targets.json` keeps the close boxes, so before and after frame the same thing (`--retarget` works them out again).
`--relief none` (the default) renders the scene's own rock; `--relief off|on` is the relief's A/B (E below).

### E. Rock relief: shape at bake time (`relief.py`, `relief_rules.py`)

**Off** (`RELIEF = False` in `bake_web.py`, the default). `--relief` on a bake turns it on. It broke the abode cliff,
changed nothing visible on the floating rocks and gave the near columns a small gain ("How it ran"). The text below
describes what it does when on.

This is attack_0's cheaper version of plan_0. It reshapes only rock that already has a fine mesh and is seen close,
and it adds no vertex anywhere:

| Object | Mesh today | What the relief does |
|---|---|---|
| `abode.cliff` | 0.8 x 0.83 m grid | beds, soft-bed recesses, joint blocks, lost blocks; folds inside a block flattened 70 % toward its plane |
| karst columns: `world.peak.NNN`, `abode.pinnacle(.NNN)`, `summit.condor_crag` | lathes, 1.25-2.5 m segments, 1.6-6 m rings | wide flat faces along the two joint sets, steps at the bed joints the lathe already has, a few missing-block notches; inward only |
| floating rocks: `arena.island`, `scenery.island(.NNN)`, `world.islet(.NNN)` | cones, 0.5-1.9 m segments, 0.7 m rings | soft-bed recesses ring the cone, blocks break its smooth facets; folds flattened 60 % |

Round 59 counted 82 targets in the round 56 scene: 61 columns, 20 floating rocks and the cliff. 29 more objects were
skipped because no area chunk bakes them, and 1 because it has no `rock_cliff` slot.

Only faces whose material is `rock_cliff` move, so Ice-Fire Island, the boulders and the forge rocks stay as they are.
**Nothing on the range heightfield** (`world.range`): attack_0 showed that range relief zigzags along the 2.5 m vertex
lattice, takes triangles from other pieces and coarsens the far range.

- **Where it runs.** `bake_web.full_ctx` calls `relief.relieve_bases` right after `capture`, on the captured
  evaluated copies, before anything is decimated, split or cut. Only records baked into an area chunk are relieved,
  and a target a session does not relieve (its chunk not asked for, or left out by `--relief-only`) is not a pin
  either, so every session relieves an object the same way whatever chunks it was asked for. The scene file never changes:
  no object is added, renamed or moved, the visibility audit and the keep-list stay valid, and the plants seeded on
  these meshes by face index stay where they are.
- **One geology field** (`relief_rules.Geo`), in world space, so beds and joints line up across the cliff, the columns
  and the islands. Beds 2.5 to 11 m thick dip 2.2 degrees and wander up to 3 m. About a fifth are soft beds 1.2 to
  2.6 m thick that sit 1 to 2 m back under the bed above. Hard beds stand out or back up to 0.7 m, with a rounded top
  edge and a groove at the base. Joint set A runs through every bed, 7 to 22 m apart. Set B, 87 degrees from A, is cut
  again in each bed, with a spacing of 1.6 x the bed's thickness (6 to 16 m), so it never makes a running bond.
  Blocks between joints stand out or back up to 0.35 m and lean a little; 7 % of hard-bed blocks are lost, a notch
  0.8 to 2 m deep. The field is clipped to 3 m in and 0.8 m out. With the block flattening below (up to 1.5 m) a
  vertex's whole move is capped at 3 m (`MOVE_MAX`), so the rock can stand up to 2.3 m out where a block's
  flattening fills a cleft, and never goes more than 3 m in.
- **No feature narrower than two vertex spacings** (attack_0). The field is box-filtered before it reaches a vertex:
  each vertex takes the mean of 5 x 3 samples spread 2 x its own vertical spacing up and down and 2 x its own spacing
  across the face. A bed thinner than that is drawn shallower, not as teeth along the lattice. The move is along the
  smoothed horizontal normal, so the faces come out flat instead of crumpled.
- **Flat blocks.** On the cliff and the islands each block's vertices are pulled toward the block's fitted plane
  (least squares on smoothed normals; a block whose normals do not agree, such as one wrapped round a corner, is left
  alone), then that move is smoothed over the mesh so it never steps at a block's edge.
- **Columns.** The column's outline is smoothed up the column over 6 m (its envelope; on a lathe with fewer segments
  than the 72 sectors, such as a 40-segment 'mid' pillar, the empty sectors are filled round the column from their
  neighbours, so the outline still follows the lobes). Eight planes cut it: four main
  faces at 0.86 of the radius whose normals follow the two joint sets (each column turned up to 12 degrees), four
  chamfers at 0.93 between them. A closer plane makes a wider face, so the main faces are the wide ones (0.91 R
  against 0.57 R; attack_0 found the plan had them swapped). The envelope is shaved 70 % of the way to the polygon,
  and that move is applied to every vertex at that height and angle, so the column's own beds, shelves and fissures
  ride on top: its shelves keep their plants and their depth. (attack_0 asked for the move from each vertex's own
  radius; that would shave the shelves off, so the envelope stands in for it.) Each bed's face sits back up to 0.25 m
  and 6 % of them are notches 0.6 to 1.5 m deep. The bed steps fall exactly on the lathe's ring pairs (a pair of rings
  0.08 to 0.1 m apart that differ in radius by at least 0.04 m), so they stay sharp. Columns only move in, never past
  3 m or a fifth of their radius, so they stay inside their old cones.
- **Pins.** The relief is 0 and fades in over a few metres near: every plant origin (2.5 to 5 m), the box of every
  hall, stair, bridge, plaque, prop, lawn or rock prop that is not relieved (2.5 to 6.5 m; a long thin one such as the
  arena's chains or a link stair by its surface, since its box would cover a whole island flank), the surface of every
  waterfall sheet (1.5 to 4.5 m, by its vertices and edge samples, not its box), every hanging root (0.8 to 3 m), every
  face that is not rock (0.5 to 3 m; a column's cap 1 to 10 m, so the dome never overhangs a shaved wall; a column's
  shelf cushions do not pin, attack_0), the mesh's open edges (0.5 to 4 m), a column's foot (2 to 12 m over its
  plinth), and on the abode cliff its dressed rock round the gate and balcony, the slope cap over it, the inscription
  panel, the water chute and the front edge (fading over 3 m). On the cliff and the floating rocks, steep rock only:
  relief fades from |normal z| 0.45 to none at 0.75. Columns have no steepness weight: their move is radial, so a
  shelf's two rings move together and the shelf keeps its width (weighted by steepness, each shelf's lip kept its
  old radius and stood out as a flange 1 to 2 m past the shaved face, a stack of drums). Nothing pins the rope
  bridge's anchor at the gate: round 59's stills showed the far-left column there shaved away from it.
- **Thin rock.** A ray from each moving vertex into the rock measures how much rock is behind it. Under 6 m the move
  scales down (none under 0.5 m), and an inward move never goes deeper than 0.4 x that thickness.
- **Inside-out rocks.** Some floating rocks are inside out (`world.py`: `recalc_face_normals` over overlapping
  spurs). The relief finds each connected part's outward side from its own geometry, so it never pushes a rock the
  wrong way.
- **Shading.** Edges the relief folds past 40 degrees (and 10 degrees more than before), with both ends relieved,
  shade sharp. Other edges keep what they had.
- **`geo_w`.** Each relieved mesh gets a POINT float `geo_w`: 1 where fully relieved, 0 where pinned. `COPY_ATTRS`
  carries it onto the bake mesh, and the round 59 material turns its own beds and joints off where it is above 0, so
  a rock never shows two bed sets. Today's material ignores it.
- **LOD floors added on top of the budget** (attack_0's budget fix). Relieved pieces seen at 60 px or more keep
  `clip(K x px^2, LO, HI)` triangles (`RELIEF_FLOORS`), at most 160k per chunk, and what that adds over the other
  floors is added to the chunk's triangle budget, as the pillar floors are. It is counted at the LOD level each
  floor rounds up to (the pick keeps a 0.3 floor at level 0.5), and the room rule's cap
  (`ROOM_GROWTH_MAX` x the budget) grows by the same amount, or it would swallow the addition where it binds. So
  halls, roofs, props and stairs keep their triangles. (Counted at the raw ratio with the cap unchanged, a
  synthetic check of the LOD rule dropped a non-rock piece a level in 163 of 400 chunks; counted this way, in none.)
- **Log.** One line per relieved object, then a summary, for example round 59's
  `RELIEF world.peak.002 column: 7873 verts, 4485 moved, mean 0.83 m, max 2.83 m, pinned 48 %, 15742 tris, 0.0 s; 7 bed tops`
  and `relief: {"objects": ..., "kinds": ..., "mean": ..., "max": ..., "pinned": ..., "skipped": ...}`. Per chunk:
  `RELIEF LOD <id>: <n> relieved pieces keep <t> of <src> tris (relief floors off: <t0>); budget <b> (off <b0>);
  largest non-rock pieces <name> <level>/<level off>, ...; none dropped`. The plan-only run picks the LODs twice
  (relief floors on and off) to fill in the "off" numbers; a real bake prints the line without them. The numbers go to
  `bake/chunks/<id>.json` and `plan_<id>.json` under `relief`, and the summary to `plan_stats.json` under
  `check.relief`.

| Option | Where | Use |
|---|---|---|
| `--relief` | `bake_web.py` | the relief and its relief floors on. Off by default; `--no-relief` is still accepted and changes nothing |
| `--relief-only <regex>` | `bake_web.py`, `preview_r59.py` | relieve only the objects whose name also matches; round 59 left the cliff out with `'^(?!abode\.cliff$)'` |
| `--relief-set KEY=value` | `bake_web.py` (repeatable; only with `--relief`) | override a constant of `relief_rules.py` or `relief.py`; a dict merges, e.g. `"COL={'k': 0.5}"`; an unknown name or dict key stops the run before the setup |
| `KEY=value` | `preview_r59.py` (plain arguments) | the same, for a tuning pass on the stills |
| `--relief none`, `off`, `on` | `preview_r59.py` | the scene's rock; in-memory copies as they are; copies relieved |

## Constants

Floor, in `bake_web.py` (after `HOLD_RHO_AROUND`):

| Constant | Value | Meaning |
|---|---|---|
| `ROCK_FLOOR` | True | the floor on (`--no-rock-floor` sets it off); not in a production bake yet |
| `ROCK_FLOOR_PX` | 1.5 | screen pixels a texel wanted at 1920 px wide; `RHO_K`'s 2.5 became 3 to 5 after the budget scale |
| `ROCK_FLOOR_K` | 1130 | texels a metre at 1 m, 1 / (1.5 x 5.9e-4 rad); 1.7 x `RHO_K` |
| `ROCK_FLOOR_MAX` | 24 | texels a metre at most; nearer than 47 m the page's fine layer takes over |
| `ROCK_FLOOR_BINS` | 0, 30, 60, 120, 250, 400 m | hold distance bins, filled nearest first; none past 400 m |
| `ROCK_FLOOR_YAWS` | 0, 60, -60 deg | forward, and the visitor turned each way (a third of the review captures) |
| `ROCK_FLOOR_NDC` | 1.3, 1.5 | frame margins x, y for the page's framing turns and formation's pitch |
| `ROCK_FLOOR_WINDOW` | 2 | holds this many stops each side of the chunk's own |
| `ROCK_FLOOR_GMIN` | 0.93 | the rest of the chunk keeps at least this share of today's linear density |
| `ROCK_FLOOR_KEEP` | 1.05 | a part is cut out only when it gains at least 5 % |
| `ROCK_SPLIT_MIN` | 32 | rock faces an item, and each bin of it, needs to take part |
| `ROCK_FLAT_RE`, `ROCK_FLAT_PROP` | see above | floating rocks by name; the property their bake pieces get |
| `COPY_ATTRS` | + `geo_w` | the relief weight reaches the joined bake mesh (0 where absent) |

The atlas refit has no constant of its own: `bake_rules.greedy_groups` uses the bake's own spill rule (a last atlas
under 0.15 of the room goes into the one before), and `bake_rules.refit_groups` takes the count from it.

Material, in `materials.py` (after `ROCK_LIP_MOSS`; `tools/test_rock_struct.py` checks that the twin uses the same
`ROCK_BED`, `ROCK_JOINT`, `ROCK_BED_HARM` and `ROCK_GEO_FADE`, and that `ROCK_STRUCT` is off). Where tuning pass 1 changed a value, the first build's value is in brackets.

| Constant | Value | Meaning |
|---|---|---|
| `ROCK_STRUCT` | False | off: today's graph exactly. True builds the round 59 graph |
| `ROCK_STRUCT_TAG` | 59 | `mat["rock_struct"]` on a rebuilt material |
| `ROCK_BED["m"]` | 2.75 m | mean bed thickness at strata 2.5 |
| `ROCK_BED["uneven"]`, `ROCK_BED_HARM` | 0.42; two harmonics | beds 1.8 to 5.6 m thick, never folding back |
| `ROCK_BED["warp"]` | 50, 2 m | beds wander 2 m over about 50 m |
| `ROCK_BED["dip"]` | 0.03, -0.02 | m per m along x and y, about 2 degrees |
| `ROCK_BED["hard"]` | 0.20 (0.30) | share of hard beds; at 0.30 the forge's terrace cliff read as even courses |
| `ROCK_BED["hard_out"]`, `["soft_out"]` | 0.25 + 0.25 r; 0.1 m | how far a hard bed stands out; a soft one +-0.1 m |
| `ROCK_BED["edge"]`, `["edge_max"]` | 0.6 m; 0.35 | the top of a bed over which the height eases to the next |
| `ROCK_BED["under"]`, `["under_w"]` | 0.25 m; 0.6 m | the cut-back under an overhang and its band |
| `ROCK_BED["shelf"]` | 0.2, 0.3 m | a step between beds that counts as a shelf or an overhang |
| `ROCK_BED["lip"]`, `["overhang_w"]` | 0.15 m; 0.8 m | the pale lip band, the damp recess band |
| `ROCK_BED["tone"]`, `["ease"]` | 0.05; 0.2 | +- tone per bed, eased over the top fifth of a bed |
| `ROCK_BED["hard_pale"]`, `ROCK_HARD_COLOUR` | 0.08 (0.2); #a79c8a | how far hard beds lean to the paler sandstone; 0.2 lifted whole shaded beds by half or more. At 0.08 the two close stills still came out 6 to 8 % brighter (Known limits) |
| `ROCK_BED["steep"]` | 0.62, 0.42 (new) | \|normal z\| from which the beds fade in (0.62, a face about 52 degrees from level) to where they are whole (0.42, about 65 degrees) |
| `ROCK_BED["gap"]` | 18.0, 0.38, 0.62, 0.15 (new) | the beds come and go along a face: a 3D noise about 18 m across; where it is under 0.38 the beds keep 15 % of their strength, from 0.62 all of it |
| `ROCK_JOINT["master_m"]`, `["master_w"]`, `["master_d"]` | 12, 0.6, 0.35 m | joint spacing, half width, depth at strata 2.5 (scale with strata / 2.5, no minimum) |
| `ROCK_JOINT["wiggle"]` | 20, 1.5 m | joints wander 1.5 m over 20 m of height |
| `ROCK_JOINT["tone"]`, `["steep"]`, `["flat"]` | 0.03; 0.8 to 0.5; 0.5 | tone per block; joints only on steep faces; their share on rock with its own beds |
| `ROCK_JOINT["gap"]` | 24.0, 0.36, 0.60, 0.10 (new) | the joints come and go likewise: a 24 m noise; under 0.36 they keep 10 % of their strength, from 0.60 all of it |
| `ROCK_CAVITY` | joint 0.12, overhang 0.12 (0.30 each) | albedo darkening in a groove's centre and in an overhang's recess; with the Bump's shade, 0.30 took recesses to a quarter of the rock's brightness |
| `ROCK_SHELF_PALE` | 0.6 | share of the lighter, drier colour on a shelf's lip |
| `ROCK_ZONE_TONE`, `ROCK_MOTTLE_TONE` | 0.3, 0.1 | tone from the 25 m zones and the 3 m mottle (colour only) |
| `ROCK_STRUCT_BUMP` | 0.45 (0.8) | strength of the one structure Bump (distance 1, heights in metres); at 0.8 overhang roofs and joint walls went near black under the 7 degree sun |
| `ROCK_STRUCT_VARIANTS` | per tag | beds and joints: underside 0.5 / 0.6, piers 0.5 / 0.4, boulders 0 / 0.8, tomb 0 / 0.6, cairn 0 / 0, flute stone 0 / 0.5 |
| `ROCK_GEO_ATTR`, `ROCK_GEO_FADE` | geo_w; 0 to 0.25 | the relief's weight, and over what range the beds and joints fade out |
| `ROCK_FLAT_PROPS` | nature_top_radius, rock_flat | OBJECT properties that switch the beds off |

Relief, in `relief_rules.py` (`tools/test_relief_rules.py` tests the rules; any of them can be overridden with
`KEY=value`). None of these changed in the session:

| Constant | Value | Meaning |
|---|---|---|
| `GEO_SEED` | 5901 | the bed list and every hash; one value for the whole range |
| `GEO_DIP` | 2.2 deg toward 35 deg | about 3.8 m over 100 m: level on one cliff, drifting across the range |
| `GEO_BED_WARP` | 3 terms, 0.5-1.6 m over 61-310 m | the beds wander, never a ruled line |
| `GEO_BED_T` | 2.5-11 m, exponent 1.5 | hard bed thickness; thin beds common, 11 m rare |
| `GEO_SOFT` | 22 %, 1.2-2.6 m thick, 1-2 m back | soft beds: at least about two vertex rows of the abode cliff, so most of the recess survives the filter |
| `GEO_HARD_OFF` | +-0.7 m (sd 0.29) | a hard bed's own offset |
| `GEO_SHOULDER`, `GEO_UNDERCUT` | 0.35 m over 0.6 m; 0.45 m over 15 % | a hard bed's rounded top edge and the groove at its base |
| `GEO_JOINT_A` | 28 deg, 14.5 m +-25 % | master joints through every bed, 7-22 m apart |
| `GEO_JOINT_B` | 115 deg, 1.6 x bed thickness, 6-16 m | the second set, cut again in each bed (no running bond) |
| `GEO_BLOCK` | 0.35 m (x0.3 soft), lean 0.06 m/m up to 0.5 m, 7 % lost 0.8-2 m | blocks between joints |
| `GEO_CLAMP` | -3 m, +0.8 m | the field, along the outward horizontal normal |
| `MOVE_MAX` | 3 m | a vertex's whole move (field plus block flattening) at most, scaled down past it |
| `GEO_SCALE` | 20 m, at least x0.25 | relief scales by radius / 20 on smaller objects (islets) |
| `LP_K`, `LP_RANGE`, `LP_TAPS` | 2; 0.5-6 m; 5 x 3 | filter width = 2 x the local vertex spacing; samples up and across |
| `NRM_ITERS`, `LP_LAMBDA`, `PLANAR_LP_ITERS` | 3; 0.5; 3 | Laplacian passes over the normals and over the planarize move |
| `PLANARIZE` | cliff 0.7, island 0.6 | share of the in-block folds flattened |
| `PLANAR_MIN_N`, `PLANAR_MIN_R`, `PLANAR_CLIP` | 6; 0.85; 1.5 m | a block is fitted only with 6 vertices whose smoothed normals agree; a vertex moves at most 1.5 m |
| `COL` | main 0.86, chamfer 0.93, k 0.7, +-5 %, +-12 deg, block 0.25 m, 6 % lost 0.6-1.5 m, at most 3 m or 0.2 R | the column faces |
| `COL_ENV` | 72 sectors, 1 m rows, 6 m sigma | the column's smoothed outline |
| `COL_CAP`, `COL_FOOT`, `COL_FOOT_SINK` | 1-10 m; 2-12 m; 8 m | fades under the cap and over the plinth (or the lowest wall point + 8 m) |
| `RING_PAIR_GAP`, `RING_EPS`, `RING_STEP_MIN` | 0.12 m; 0.01 m; 0.04 m | which lathe rings make a bed top |
| `RELIEF_STEEP` | 0.75 to 0.45 | \|normal z\|: none to whole |
| `PIN_NONROCK`, `PIN_VEG`, `PIN_STRUCT` | 0.5-3; 2.5-5; 2.5-6.5 m | non-rock faces, plant origins, structure boxes |
| `PIN_WATER`, `PIN_ROOT`, `PIN_EDGE` | 1.5-4.5; 0.8-3; 0.5-4 m | water sheet and root surfaces, open edges |
| `STRUCT_MAX_DIAG`, `ROCK_PROP_MAX_DIAG` | 150 m; 40 m | larger boxes are terrain or canopy shells, not structures; larger rock is not a prop |
| `STRUCT_POINTS` | 20 m, 2 x | a structure longer than 20 m and twice its middle side (a chain, a link stair) pins by its surface, not its box |
| `SAMPLE_STEP`, `ABODE_FADE` | 0.5 m; 3 m | edge samples on water and roots; the abode zones' fade |
| `RELIEF_THICK` | 0.5, 6, 8 m, 0.4 | thin rock: none under 0.5 m, whole from 6 m, ray 8 m, inward at most 0.4 x thickness |
| `RELIEF_SHARP_DEG`, `RELIEF_SHARP_GAIN` | 40 deg; 10 deg | new folds past this shade sharp |

In `relief.py`: `RELIEF_OWNER_RE`, `COLUMN_RE`, `CLIFF_RE` (which objects, which kind), `RELIEF_MAT` (`rock_cliff`),
`SHELF_MAT`, `ROOT_RE`, and the abode zones `ABODE_RECT` (-16 to 10 m, z -2 m to `abode.CAP_Z1`, blend 5 m),
`ABODE_INSC` (`abode.INSC_X` +-3.5 m, z 18.5-41 m, blend 3 m), `ABODE_CHUTE` (6.5 m either side of `abode.FALL_X`),
`ABODE_CAP_TOL` (1 m) and `ABODE_TOP` (1.5 m under the front edge). The rectangles are `abode._face_y`'s own numbers.

In `bake_web.py` (after `PILLAR_FLOOR_CAP`):

| Constant | Value | Meaning |
|---|---|---|
| `RELIEF` | False | the relief off, and the bake exactly as before (no relief, no relief floors); `--relief` sets it on |
| `RELIEF_FLOORS` | column 0.07, 600-16000; island 0.30, 400-14000; cliff 0.07, 4000-40000 | K, LO, HI of the relieved pieces' LOD floors, added to the budget |
| `RELIEF_FLOOR_MIN_PX` | 60 px | smaller on screen: no relief floor |
| `RELIEF_FLOOR_CAP` | 160k | relief floor triangles per chunk at most |
| `RELIEF_ONLY`, `RELIEF_SET` | empty | set by `--relief-only` and `--relief-set` |

## Run sheet

This is the sheet for a later round that turns a part back on, with its commands corrected for the code as it is
now. Round 59 itself ran steps 0 to 10 in its own order, with more stills, and stopped before step 11 ("How it
ran"). With only the floor kept, the floor needs no steps of its own: it rides with any full bake (step 13 and on),
since `ROCK_FLOOR` is on.

One list, top to bottom. Each box step gives its minutes, its cost at 0.81 US dollars an hour (1.35 cents a
minute; round 59's box cost 0.694) and the log lines that say it worked. Never run Blender on the PC. The run sheet
needs `PIPELINE_CHANGED_OK=1` (`spec.md`): `bake_web.py` and `bake_rules.py` changed, and `relief.py` and
`relief_rules.py` are new.

Run the commands in Git Bash from the worktree root, `E:/Github/PortfolioV5/.claude/worktrees/saltline-game-architecture-ae3e16`,
after

```
RB="python E:/Github/PortfolioV5/.claude/worktrees/saltline-game-architecture-ae3e16/blender/xianxia-sect/tools/rblender.py"
```

`$RB` sends this branch's `sect/`, `docs/` and `assets/web/` to the box and runs Blender 5.2.2 there. The box keeps
its copy of the project at the main checkout's path, so every path after `-b` and `--python` is
`E:/Github/PortfolioV5/blender/xianxia-sect/...`. What a run writes under `out/` comes back to the worktree's
`blender/xianxia-sect/out/` (a `.blend` only with `--fetch-blend`). `$RB --sh "..."` runs a shell command in the
project folder on the box.

The round has three parts, and each can drop out on its own ("When a gate fails"): the material (the patch, steps 5,
6 and 11, each with `ROCK_STRUCT=True`), the floor (on by default; `--no-rock-floor` on a bake drops it) and the
relief (off by default; `--relief` on a bake turns it on).

0. **PC checks (no box).** From `E:/Github/PortfolioV5/.claude/worktrees/saltline-game-architecture-ae3e16/blender/xianxia-sect`,
   one at a time:
   ```
   python -m py_compile sect/bake_web.py sect/bake_rules.py sect/lib/materials.py sect/lib/rock_struct.py sect/patch_r59_rock.py sect/preview_r59.py sect/relief.py sect/relief_rules.py
   python -P tools/test_bake_rules.py
   python -P tools/test_rock_struct.py
   python -P tools/test_relief_rules.py
   ```
   The first prints nothing, the others `test_bake_rules ok`, `test_rock_struct ok` and `test_relief_rules ok`. Fix
   any failure before renting. `test_rock_struct` checks that `ROCK_STRUCT` is off: a round that turns the material
   on by default changes that check too.

1. **Rent and set up (10 min, 0.14 dollars).**
   - Rent one RTX 5090 (skip host 366851; 346497 was fast) with
     `python blender/xianxia-sect/tools/box/vast_rent.py <offer id> <label>`. It reads `VAST_API_KEY` from the
     environment and repairs the base image's SSH key file, which the SSH server otherwise refuses.
   - `bash blender/xianxia-sect/tools/box/box_up.sh <host> <port>` does the rest of this step. It writes the box's
     address into `tools/remote.json`, starts `tools/box/box_setup.sh` on the box, uploads the files below, and
     prints the scene's md5 and the end of the setup log. The setup installs Blender 5.2.2 at `/root/blender`, taken
     from the Berkeley mirror first (`https://mirrors.ocf.berkeley.edu/blender/release/Blender5.2/blender-5.2.2-linux-x64.tar.xz`;
     the official server gave one box 10 KB/s) and checked against Blender's official list
     (`https://download.blender.org/release/Blender5.2/blender-5.2.2.sha256`). It also takes out the CUDA compat path,
     as rounds 55 to 59 did. Its log must end with `cuda init ok` and `SETUP_OK`, with no `SETUP_FAIL`.
   - By hand, the CUDA check is
     `$RB --sh "python3 -c \"import ctypes; print(ctypes.CDLL('libcuda.so.1').cuInit(0))\""`, which must print
     `0`. If it prints `804`, run
     `$RB --sh "mkdir -p /root/ld_off && mv /etc/ld.so.conf.d/00-compat-*.conf /root/ld_off/ && ldconfig"` and check
     again. `$RB --sh "nvidia-smi"` must name the RTX 5090.
   - What `box_up.sh` uploads, because `rblender.py` does not send it: the scene, the audit cache and chunk plan, the
     timeline, the camera (step 10's verify reads it) and the fonts. By hand, with `H` and `P` the host and port from
     `tools/remote.json`:
     ```
     B=/E:/Github/PortfolioV5/blender/xianxia-sect
     W=E:/Github/PortfolioV5/.claude/worktrees/saltline-game-architecture-ae3e16/blender/xianxia-sect
     ssh -p $P root@$H "mkdir -p $B/out/web/full/site /C:/Windows/Fonts"
     scp -P $P E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.r56.blend root@$H:$B/out/sect_chase.blend
     scp -P $P $W/out/section_timeline.json root@$H:$B/out/
     scp -P $P $W/out/web/full/{vis_cache.npz,chunks.npz,chunks.json,audit.json,camcheck.json,mist_voxels.bin,mist_voxels.json,plan_check.json,standin_stats.json,water_meta.json} root@$H:$B/out/web/full/
     scp -P $P $W/out/web/full/site/camera.json root@$H:$B/out/web/full/site/
     scp -P $P C:/Windows/Fonts/{georgiab.ttf,msyh.ttc,palab.ttf,simkai.ttf} root@$H:/C:/Windows/Fonts/
     ```
     The scene is the round 56 file. The main checkout's own `out/sect_chase.blend` is the older round 54 file: never
     upload that one.
   - `$RB --sh "md5sum out/sect_chase.blend"` must print `03b2fd96917412d869129f1da0605a71`.

   Gate: `cuInit` prints 0, `nvidia-smi` lists the RTX 5090, the md5 is right. Otherwise destroy the box and rent
   another.

2. **Keep-list before (2 min, 0.03 dollars).**
   ```
   $RB -b E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r48_keep.py -- MODE=dump LABEL=r59_before
   ```
   Look for `PATCH KEEP dump: <n> location objects` (4,844 in round 59). `out/tmp/r48/keep_r59_before.json` comes back
   to the PC, and step 12 sends it back.

3. **Inspect the rock materials, read only (2 min, 0.03 dollars).**
   ```
   $RB -b E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r59_rock.py -- MODE=inspect
   ```
   It builds today's graph and the new one for every rock tag, whatever `ROCK_STRUCT` says, so a socket name the new
   graph gets wrong stops here, with a `KeyError` naming the node. Look for
   `PATCH INSPECT rock_cliff M.rock_cliff: ... equals today's graph` with photo tile and offsets
   `(8.14, 8.14, 0.0, 0.0), (8.14, 8.14, 0.37, 0.61), (8.14, 8.14, 0.71, 0.13)`, and `equals today's graph` for
   `world_rock_under`, `nature_rock_small` and `world_pier_stone`. In round 59 all four matched. The forge's tomb rock
   said `neither` (expected: no earlier patch rebuilt it), and no material in the scene carries the cairn or flute
   tag (`PATCH WARN no material tagged forge_cairn_rock`, `... flute_qingshi`). `PATCH INSPECT pillars ...` counted 86
   objects with `nature_top_radius` (59 of them `world.peak.NNN`), `PATCH INSPECT floating rocks ...` 160, and
   `PATCH INSPECT meshes with a geo_w attribute: 0`, then `PATCH inspect done`.
   Gate: a traceback, or `neither` on one of those four. Read the listed differences: if they are one override an
   earlier patch used, write it into `materials.py` on the PC and run this step again. Otherwise the material drops
   out.

4. **A copy, and the before stills (5 min, 0.07 dollars).**
   ```
   $RB --sh "cp out/sect_chase.blend out/r59try.blend"
   $RB -b E:/Github/PortfolioV5/blender/xianxia-sect/out/r59try.blend --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r59.py -- --tag before
   ```
   Look for `PREVIEW cycles device OPTIX`, 18 `PREVIEW wrote` lines and `PREVIEW done 18 stills`. A
   `PREVIEW WARN no rock target for <shot>` means a close-up found nothing to aim at: fix the shot on the PC and render
   that close-up again with `--shots`, as round 59 did. `arena_516_close` says `fallback 2`: the hold sees neither the island's underside
   nor its wall, so it frames a floating rock. The run also writes `out/tmp/r59/renders/targets.json` on the box, so
   every later still frames the same rock.

5. **Patch dry run on the copy (2 min, 0.03 dollars).**
   ```
   $RB -b E:/Github/PortfolioV5/blender/xianxia-sect/out/r59try.blend --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r59_rock.py -- DRY_RUN=1 ROCK_STRUCT=True
   ```
   `ROCK_STRUCT=True` is needed now that the default is off: without it the patch builds today's graph and the new
   material is not applied. Look for `PATCH round 59 rock: ROCK_STRUCT True`, `PATCH state rock_cliff: M.rock_cliff old` and the
   other tags `old` (the forge's tomb rock says `differs` and then `expected`), one `rebuilt` line per tag,
   `PATCH DIGEST <md5>`,
   `PATCH CACHES needs bakefull gate,mirror,forge,arena,mission,library,steles,scroll,formation,abode,summit,backdrop`
   and `PATCH DRY_RUN: checks passed`.
   Gate: `NOT SAVED` or a traceback. The material drops out.

6. **Patch the copy (2 min, 0.03 dollars).** The same command without `DRY_RUN=1` (keep `ROCK_STRUCT=True`). Look
   for `PATCH saved` and note the `PATCH DIGEST`.

7. **After stills and the look gate (5 min, 0.07 dollars).**
   ```
   $RB -b E:/Github/PortfolioV5/blender/xianxia-sect/out/r59try.blend --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r59.py -- --tag after
   ```
   Compare each `out/tmp/r59/renders/r59_after_<shot>.png` with `r59_before_<shot>.png` against the look gate
   below. Up to two tuning passes, about 8 minutes (0.11 dollars) each: a fresh copy, step 6 again with `KEY=value`
   overrides after `ROCK_STRUCT=True`, then this step with `--tag after2`. Write the values that pass into
   `materials.py` on the PC. Step 11 needs the same overrides. Also add up the seconds at the end of the
   `PREVIEW wrote` lines, before and after, leaving out each run's first still (it carries the GPU's warm-up: 72 s on
   round 59's first run). The same shots on the same host, so their ratio is what the new shader costs. Over 1.5
   times, the production bake would run about that much longer than its 145 minutes. In round 59 the ratio was 1.0.
   Gate: the look gate still fails after two passes, or the stills take over 1.5 times as long. The material drops
   out. (In round 59 it did.)

8. **Relief stills, off and on (10 min, 0.14 dollars).**
   ```
   $RB -b E:/Github/PortfolioV5/blender/xianxia-sect/out/r59try.blend --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r59.py -- --tag reliefoff --relief off --shots abode_1380,abode_1380_close,library_772,library_772_close,arena_516,arena_516_close,summit_1647,gate_93,forge_352,forge_352_close,mission_619,mission_619_close,steles_974,scroll_1103,formation_1208
   $RB -b E:/Github/PortfolioV5/blender/xianxia-sect/out/r59try.blend --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/preview_r59.py -- --tag reliefon --relief on --shots abode_1380,abode_1380_close,library_772,library_772_close,arena_516,arena_516_close,summit_1647,gate_93,forge_352,forge_352_close,mission_619,mission_619_close,steles_974,scroll_1103,formation_1208
   ```
   These fifteen shots are the ones with relieved rock in them. The stills tool has its own switch (`--relief off|on`),
   so it needs no `--relief` flag. Both runs put in-memory copies in place of the objects the bake relieves (the
   scene is never saved), so compare `reliefon` with `reliefoff`, not with `after`. Each run first gathers the scene
   and copies the targets (about 50 s); the `on` run also relieves them (about 25 s more in round 59). Look for
   `PREVIEW context: 82 targets {"column": 61, "island": 20, "cliff": 1}` (round 59's count), in the `on` run one
   `PREVIEW RELIEF <name> <kind>: ...` line per object and
   `PREVIEW relief on: 82 objects copied; relieved, mean 0.50 m, max 3.00 m`, then `PREVIEW done 15 stills`. In round
   59 the cliff's mean move was 0.65 m, the columns' 0.26 to 1.57 m and the floating rocks' 0.03 to 0.47 m. No max
   was over 3.0 m. 11 columns and 5 floating rocks were over 60 % pinned, by plants on their shelves and rims. Then
   the relief look gate below.
   Up to two tuning passes on the `on` run only, about 4 minutes (0.05 dollars) each, with `KEY=value` arguments after
   the others, for example `"GEO_BLOCK={'amp': 0.2}"` (masonry), `"COL={'k': 0.5}"` (columns too hard-edged),
   `"GEO_SOFT={'recess': (0.6, 1.2)}"` (overhangs too deep) or `"PLANARIZE={'cliff': 0.5}"` (cliff too flat).
   `--relief-only "^abode"` limits a pass to the abode, and `--relief-only '^(?!abode\.cliff$)'` leaves the cliff
   out. Write the values that pass into `relief_rules.py` on the PC before step 9 (`rblender.py` sends it), or give
   each to every bake below as `--relief-set "KEY=value"`.
   Gate: the relief look gate still fails after two passes. The relief drops out.

9. **Plan only: the floor and the relief for all eleven (6 min, 0.08 dollars).** With the relief on, the plan-only
   run picks each chunk's LODs twice (relief floors on and off). Round 59's took 5 minutes.
   ```
   $RB -b E:/Github/PortfolioV5/blender/xianxia-sect/out/r59try.blend --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/bake_web.py -- bakefull --profile full --plan-only --relief --chunks gate,mirror,forge,arena,mission,library,steles,scroll,formation,abode,summit --out-dir r59plan
   ```
   Add `--relief-only '^(?!abode\.cliff$)'` (as round 59 did) if the cliff stays out; the same then goes on steps 10
   and 13. Without `--relief` this run checks the floor alone. Look for `BAKE rock floor on` and
   `BAKE relief on (--relief)` near the top, then `BAKE context: ...`, one `BAKE RELIEF <name> <kind>: ...` line per
   object and `BAKE relief: {...}` after the capture. The per-object lines should match step 8's `on` run (the same
   rules on the same meshes; round 59's matched). A chunk whose floor grouping needed one more atlas logs
   `ROCK FLOOR refit: ...`. The log ends with one `BAKE PLAN ROCK FLOOR <id>: ...` and one
   `BAKE PLAN RELIEF LOD <id>: ...` line per chunk. Apply both plan-only gates below.
   `out/r59plan/bake/plan_<id>.json` and `plan_stats.json` come back to the PC.
   Optional and not in the budget: the same with `--rock-floor-units 2.0 --out-dir r59plan2` shows what a bigger
   budget would buy (it skips the refit). Do not bake with it without the owner: it grows the download and GPU memory.

10. **Look bake (30 min, 0.41 dollars) and a library without relief (12 min, 0.16 dollars).**
    ```
    $RB -b E:/Github/PortfolioV5/blender/xianxia-sect/out/r59try.blend --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/bake_web.py -- bakefull --profile full --quality dev --relief --chunks abode,library,arena,steles,forge --out-dir r59look
    $RB --background --factory-startup --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/bake_web.py -- verify --profile full --chunks abode,library,arena,steles,forge --out-dir r59look --ref-frames 1380,772,516,974,352
    $RB -b E:/Github/PortfolioV5/blender/xianxia-sect/out/r59try.blend --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/bake_web.py -- bakefull --profile full --quality dev --chunks library --out-dir r59flat
    $RB --background --factory-startup --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/bake_web.py -- verify --profile full --chunks library --out-dir r59flat --ref-frames 772
    ```
    The `r59flat` bake leaves the relief out by default (`--no-relief` is still accepted there). `--background` on the
    verify matters: without it Blender tries to open a window on the box. Look for `BAKE cycles device OPTIX`, each
    chunk's `ROCK FLOOR` and `RELIEF LOD` lines, and each `BAKE CHUNK DONE <id> {...}` with its `"total"` in seconds
    (the dev table in `bake_web.py`'s header: abode 3.0, library 4.2, arena 2.9, steles 4.4, forge 3.7 minutes;
    round 59 baked steles in 4.2 and abode in 2.4). The verify renders come back as
    `out/r59look/bake/verify/hold_<frame>.png` and `out/r59flat/bake/verify/hold_772.png`. They show only the chunks
    baked here. Apply the last two items of the relief look gate.
    Round 59 ran a different look bake, because by then only the floor was left: steles and abode with the floor and
    no relief (`r59look`), then the same with `--no-rock-floor` (`r59flat`), on the unpatched round 56 scene. Those
    renders are in the worktree under the same names.
    The chunk times against the header's dev table tell what step 13 will take. If every chunk is over 1.5 times its
    header time while step 7's still ratio was fine, the host is slow (round 55's took 2 to 2.4 times): re-rent before
    step 11. The look results stay valid.
    Gate: steps gone after the LOD pick: raise that kind's K in
    `bake_web.RELIEF_FLOORS` on the PC (`--relief-set` reaches only `relief_rules.py` and `relief.py`) and run steps 9
    and 10 once more; still gone, the relief drops out. A hall or prop at library 772 coarser than in `r59flat`: the
    relief drops out. If money is short, the `r59flat` pair can go: the plan-only gate already checks the largest
    pieces' levels.

11. **The main file (6 min, 0.08 dollars).** Skip it if the material dropped out.
    ```
    $RB --fetch-blend -b E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r59_rock.py -- ROCK_STRUCT=True
    ```
    with step 7's overrides after `ROCK_STRUCT=True`, if any. `PATCH DIGEST` must equal step 6's. The patched file
    comes back as the worktree's `blender/xianxia-sect/out/sect_chase.blend`: keep it as `out/sect_chase.r59.blend`
    and note its md5.

12. **Keep-list compare (2 min, 0.03 dollars).** Skip it if step 11 was skipped.
    ```
    $RB -b E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r48_keep.py -- MODE=compare LABEL=r59_after REF=out/tmp/r48/keep_r59_before.json
    ```
    With no ALLOW. It must print `PATCH KEEP diff 0`. No audit and no `chunks,meta`: no name, mesh or box changed.
    Gate: any other number. The patch touched an object, which it must not: do not bake this file. Upload the round 56
    scene again (step 1's `scp` and md5) and go on with the material dropped out.

13. **Production bake (145 min, 1.96 dollars).**
    ```
    $RB -b E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/bake_web.py -- bakefull --profile full --quality production --live --chunks gate,mirror,forge,arena,mission,library,steles,scroll,formation,abode,summit,backdrop
    ```
    Add `--relief` if the relief passed (with `--relief-only` and `--relief-set "KEY=value"` as the gates decided),
    and `--no-rock-floor` if the floor dropped out. First lines: `BAKE quality production`, `BAKE rock floor on` and
    `BAKE relief on (--relief)` (or `off` where a part is left out), then `BAKE cycles device OPTIX`. Run
    `$RB --sh "nvidia-smi"` within 3 minutes of the first chunk. If `BAKE gate baked atlases in N s` passes 600 s, the
    host is slow: stop, destroy, re-rent and run steps 1, 11, 12 and 13 again (the look results stay valid). With the
    relief on, `BAKE relief: {...}` must list the same objects with the same mean and max as step 9. Each chunk logs
    its `ROCK FLOOR` line (and `ROCK FLOOR refit` where it needed one), and its `RELIEF LOD` line with the relief on.

14. **Live maps (10 min, 0.14 dollars).**
    ```
    for c in gate mirror forge arena mission library steles scroll formation abode summit; do $RB --background --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/live_calib.py -- $c; done
    $RB --background --python-exit-code 1 --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/live_bounce.py -- gate mirror forge arena mission library steles scroll formation abode summit
    ```
    Each `live_calib` run prints its share: about 0.318 (`docs/sect/live-gate.md`).

15. **Fetch, check and close (10 min, 0.14 dollars).** The raw GLBs, live maps and bake JSONs came back with each
    run. Check them with `$RB --sh "md5sum out/web/full/raw/*.glb"` against the PC's copies, and fetch anything
    missing with `$RB --pull <path>`. Destroy the box once the pack below reports 0 problems, and confirm the instance
    list is empty.

16. **On the PC (no box).** At below-normal priority: `python blender/xianxia-sect/tools/sect_live.py --chunk <id>` for
    the eleven areas, `python blender/xianxia-sect/tools/sect_pack.py --profile full --workers 2`, the page changes
    below, `pnpm lint`, `pnpm typecheck` and `pnpm test` in `client/`, then screenshots at the eleven holds, forward and
    turned 60 degrees.

**Cost.** Steps 1 to 15 come to about 259 box minutes: 3.5 dollars at 0.81 dollars an hour. One tuning pass of the
material (8 minutes) and one of the relief (4 minutes) make it about 3.7 dollars; second passes of both reach about
3.8, so take a second pass for one part only. The look tests (steps 1 to 10) are about 86 minutes, so the round can
stop before the production bake at about 1.15 dollars. Round 59 ran its look tests (with more stills, two material
passes and a smaller look bake) in 92 box minutes for 1.07 dollars. With the relief on, the relief itself adds well
under a minute to a session (4.2 s for 81 objects in round 59's plan-only run, about 24 s in its stills runs).
Download: no atlas grows (the plan-only gate checks it). The
relief floors add triangles only in the chunks where the budget binds: in round 59's plan about 155k in all, in gate,
forge, mission, library and steles, at about 4.7 bytes a triangle gzipped, so under 1 MB in all. GPU memory: about
the same.

## When a gate fails

Each part drops out on its own, and the others go on.

- **The material drops out** (step 3, 5 or 7; step 12 says what to do there): skip steps 11 and 12 and bake the
  round 56 scene as it is. If steps 8 to 10 are still to come, first run
  `$RB --sh "cp out/sect_chase.blend out/r59try.blend"` so they run on today's material. Page: none of changes 1 to
  4; change 5 only if the floor ships (it is about the floor's sharper far rock, judged on the GPU); if the relief
  ships, change 7's second half. This is where round 59 ended up.
- **The floor drops out** (the plan-only floor gate, step 9), for all chunks or one. All: add `--no-rock-floor` to
  step 13. One chunk: leave it out of step 13's `--chunks`, then bake it in its own session with
  `--no-rock-floor --live` (about 5 minutes of setup plus the chunk, 0.15 to 0.25 dollars) and run step 14 for it. Its
  relief comes out the same as in the main session: a target a session does not relieve is not a pin either. Page:
  with no floor anywhere, skip change 5 and keep `rockMid.gain` at 2.0 (change 5 is about the floor's sharper far
  rock).
- **The relief drops out** (step 8, 9 or 10): leave `--relief` out of steps 9 and 10 if they are still to come, and
  out of step 13 (off is the default). Page: change 7 does not apply. This is where round 59 ended up.
- **All three drop out**: stop before step 11. There is nothing to bake.

## Look gate (stills, step 7)

The bake is allowed only when the after stills show all of these:

- **No plaid at the forge.** In `forge_352` the far rock shows no even grid of level stripes crossed by vertical
  columns.
- **No hairlines.** In the `_close` stills, no bright or dark line one pixel wide along a bed boundary or a joint.
- **No stripes on boulders.** The boulders, the forge's tomb and cairn stones and the flute's stone show no beds.
- **Pillars without a second bed set.** In `library_772_close` and `summit_1647` the pillars show their modelled beds
  only, with no thin level bands across them. `arena_516_close`: the island's underside has no beds.
- **Not masonry.** In `abode_1380_close` and `steles_974_close`: level beds of different thickness, some standing out
  with a pale lip and a dark recess under them, joints cutting them into blocks. No three beds in a row of equal
  thickness with the joints lined up over each other.
- **Same brightness.** Each still's mean brightness within about 5 % of its before still.

Round 59's first build failed the first item (a block grid on the forge's terrace cliff), the fifth (even courses at
the forge and on the arena's small mesa) and the last (+6.1 % and +7.6 % in the abode and steles close-ups). It passed
the other three. A gate item alone did not catch the worst fault, the contour-map ribbons on the mirror's slope; the
reviewers did.

Knobs, as overrides on the patch after `ROCK_STRUCT=True`: masonry or too busy: `"ROCK_BED={'hard': 0.22}"` and
`"ROCK_JOINT={'tone': 0.0}"`. Plaid at the forge: `"ROCK_BED={'tone': 0.03}" "ROCK_JOINT={'tone': 0.0}"`. Hairlines
or harsh ledges under the low sun: `ROCK_STRUCT_BUMP=0.5 "ROCK_BED={'edge': 0.9}"`. Round 59's tuning showed the
limit of these knobs: soft enough to pass, the structure barely shows ("How it ran"). After two failed passes the
material drops out: the main file is not touched until step 11.

## Relief look gate (stills step 8, verify renders step 10)

The relief may go into the production bake only when the `reliefon` stills against `reliefoff`, and the step 10
verify renders against the `reliefon` stills and `r59flat`, show all of these:

- **Nothing floating.** No plant, rail, lantern, stair, plaque, pavilion or boulder hangs in the air or sinks into the
  rock, at any stop. Look closest at the abode's gate, balcony and inscription, the summit crag's capstone and bird,
  shrubs on the column shelves, the arena island's rim and roots, the abode waterfall's sheets, and the rope bridge's
  anchor on the far-left column at gate 93.
- **No column reads as masonry or a stack of drums.** The columns show a few wide flat faces running the height of
  the column, with steps where their beds already stepped, not a grid of equal blocks and not round drums.
- **No green stripe along bed floors.** The new ledges must not paint a moss line along every bed on the abode
  cliff, the columns or the islands, and no new ledge may let the lawn show through. If they do:
  `"GEO_SOFT={'recess': (0.6, 1.2)}"` and `"GEO_BLOCK={'tilt': 0.0}"`.
- **No gap where relieved rock meets pinned rock.** At the abode's dressed rock, the lawn rim, a column's cap and
  foot, a pinned plant or a box: no crack, seam, step or hole, only a fade over a few metres.
- **No bubble round a plant.** On a column's shelf, the rock round a pinned shrub must not stand out as a bump, and
  no patch of the material's joint grooves may show there (see Known limits). If either does: `"PIN_VEG=(1.5, 6.0)"`
  (a longer, softer fade).
- **No faceting.** The relieved rock shades as smoothly as `reliefoff` away from the new folds (the relief drops a
  mesh's custom normals when it moves it), and no face turns into creases or pleats.
- **The steps survive the LOD pick.** In the step 10 verify renders the column faces, the cliff's beds and the
  island's recess rings are still there (against the `reliefon` stills and `r59flat`).
- **The halls keep their detail.** At library 772 the halls, roofs and props look as they do in `r59flat`.

Round 59's result, on the stills only (no relief bake ran): the cliff failed the green item (the lawn through a new
ledge) and the faceting item (pleats on its shoulder). The columns passed everything except the first item, at
gate 93's far-left column. The floating rocks did not visibly change.

## Relief plan-only gate (step 9)

- **No other piece drops.** Every `PLAN RELIEF LOD <id>` line ends with `none dropped` (or says the chunk has no
  relieved piece). `DROPPED: <names>` is a bug (the relief floors are meant to be added to the budget): the relief
  drops out, and report it.
- **Triangle growth.** Each line's `keep <t> of <src> tris (relief floors off: <t0>)`: t - t0 is what the relief
  floors add in that chunk. At most 60k a chunk and 250k over the eleven. More: lower `RELIEF_FLOORS` K in
  `bake_web.py` (column 0.055, island 0.2) and run step 9 again. Still more: the relief drops out.
- **The relief ran.** `BAKE relief: {...}` lists `objects` in the dozens, `skipped` without "mesh shared" for a column
  (a shared mesh is never relieved), and a `max` of 3.0 m or less.
- The atlas sizes of the floor gate below must still hold: relief adds no surface to speak of (inward moves of a few
  metres on faces tens of metres wide).

Round 59 passed all four, with the cliff left out: 81 objects, max 3.0 m, every line `none dropped`, and about 155k
triangles added (the most, 50.6k, at the library).

## Plan-only gate (floor, step 9)

Per chunk, the `PLAN ROCK FLOOR` line must say `keeps` 93.0 % or more: the rest of the chunk keeps at least 93 % of
today's linear density. The rule enforces it, so a lower number is a bug: the floor drops out for that chunk, and
report it.

The same line ends with `atlases <sizes> px`, counted after any refit. They must equal the last bake's
(`out/web/full/bake/chunks/<id>.json`): `4096+2048` at abode, arena, library, mirror, mission and scroll; `4096` at
formation; `4096+4096` at forge, gate and steles; `4096+4096+2048` at summit. The floor keeps the texel total inside
the budget, but it moves parts between atlases, and the greedy grouping can then push an A1 past 0.325 of an atlas
(it becomes a 4096) or open one more atlas. Either would grow the download and GPU memory, which this round must not
do.

One more atlas is now fixed in code: the chunk logs
`ROCK FLOOR refit: <n> atlases back to <m>; <k> items moved, <f> forced; fullest atlas <p> % of its room`, and the
numbers go to `rock_floor.refit` in the chunk's JSON. A fullest atlas over 100 % means an item was forced, and the
packer shrinks that atlas's layout to fit. Round 59's steles needed it (3 atlases back to 2; 100.8 % in the plan,
101.3 % in the bake). If a chunk's sizes still differ, run the plan-only once more for that chunk alone with
`--no-rock-floor --out-dir r59plan0` (about 3 minutes, 0.04 dollars, most of it the setup). If that one matches the
last bake, the floor caused it: the floor drops out for that chunk ("When a gate fails"). If it does not match
either, the floor is not the cause and the bake can go ahead.

Also expect `floor` above 0.5M texels in the chunks whose holds look at far rock (mirror, forge, scroll, library;
round 59: 1.9M to 3.2M). If a chunk's floor takes nothing although its hold sees rock, check `holds` in its
`rock floor:` JSON (9 to 15 views); the bake can still go ahead, that chunk just gets no floor. `gscale` in
`rock_floor` is the scale the rest really got; it should match `g_rest` within 1 %.

Round 59 passed: every area kept 93.0 % or more, and every atlas size matched after the steles' refit.

## Rollback

- Material: off by default (`ROCK_STRUCT = False` in `materials.py`). On a file patched with it,
  `patch_r59_rock.py -- ROCK_STRUCT=False` rebuilds today's graph (the forge's tomb and cairn rock and the flute's
  stone then get today's repo graph, not the older one they had). Or go back to `out/sect_chase.r56.blend`.
- Floor: `--no-rock-floor` on the bake, or `ROCK_FLOOR = False`.
- Relief: off by default (`RELIEF = False` in `bake_web.py`); leave `--relief` off the bake. Nothing in the scene file
  to undo.
- `geo_w` in `COPY_ATTRS` and the `rock_flat` property do nothing without the round 59 material. Neither reaches the
  GLBs: the post step exports no custom attributes.

## Page changes when the bake lands

Round 59 changed no client code. While the material and the relief are off, items 1 to 4 and 7 do not apply: they
were written for them. Item 5 is to be judged when a bake with the floor lands. Items 6 and 8 stand.

Make the ones that apply in the same commit as the packed bake, then run the client tests. `detail.test.ts` reads
these constants rather than pinning their numbers (lines 458 and 835), but run it to see.

1. (Material only.) `client/src/lib/sect/detail.ts`, `DETAIL_LOOK.rockBeds.gain`: `0.34` -> `0`. The page's 2.9 m
   beds would draw a second, unrelated bed set over the baked beds. Note `0.34` in the comment as the value until
   round 59.
2. (Material only.) `client/src/lib/sect/detail.ts`, `DETAIL_LOOK.rockFar.band.weight`: `0.15` -> `0`. Its 11 m bands
   would cross the baked beds out to 700 m. The noise part of `rockFar` stays.
3. (Material only.) `client/src/lib/sect/range-look.ts`, `RANGE_LOOK.rock.streaks.dark`: `0.3` -> `0`. The bake's
   streaks now hang from the beds' lips; the page's 40 m vertical streaks would be a second set.
4. (Material only.) `client/src/lib/sect/live.ts`, `LIVE_LOOK.classes.rock.bump`: `[1.3, 0.14, 0.2, 0.12]` ->
   `[1.3, 0.04, 0.2, 0.08]`. The live normal map now carries the baked beds and joints; the 1.3 m bumps at slope 0.14
   (crumpled paper in live light) mostly go, the 0.2 m grain stays a little.
5. (The floor; judge it when a bake with the floor lands.) `client/src/lib/sect/detail.ts`,
   `DETAIL_LOOK.rockMid.gain`: `2.0` -> `1.0`. The middle band adds the photo's crack band (detail.webp B: the blur
   at 0.12 m minus the blur at 1 m, `DETAIL_BAND_M`) where the bake had blurred it. Once the floor is baked, rock at
   250 to 400 m gets about 3.5 texels a metre at most stops (in round 59's plan, 1.6 to 4.0 where that bin got a
   floor at all), so the bake holds more of that band itself, and 2.0 could double it. `rockMid.texelM` (0.1 to 0.3 m
   a texel) does not take care of it alone: at 3.5 texels a metre a texel is 0.29 m, where the band is still almost
   fully on (about 99 %). Judge it on the GPU at the abode, forge and library holds with 0.6, 1.0 and 1.4, as round 58
   picked 2.0. Round 59's test bake showed only a small gain from the floor, so 2.0 may well stay.
6. Not changed: `ROCK_SCAN` (same photo, tile, offsets and blend), `rockFarSet` (the far set is vertex colours and
   gets none of the new structure), `DETAIL_LOOK.rock` (the fine layer).
7. (Relief only.) The relief (E) needs nothing more when items 1 and 2 land: plan_0's rider asked for
   `DETAIL_LOOK.rockFar.band.weight` `0.15` -> `0.05` and `DETAIL_LOOK.rockBeds.gain` `0.34` -> `0.12`, because the
   baked rock now has real beds and the page's painted 11 m and 2.9 m bands would draw a second, unrelated bed set on
   top. Items 1 and 2 take both to `0`, which covers it. **If the relief ships without the material rebuild** (the
   patch not applied), still change those two, to plan_0's values: `rockBeds.gain` `0.34` -> `0.12` and
   `rockFar.band.weight` `0.15` -> `0.05` (both were already too faint to see, review_surf2.md), and leave items 3 to
   5 alone.
8. The relief changes no object, name, box or hotspot, so `meta.json`, the hotspots and the streaming plan stay as
   they are. The GLBs carry no normals (lux.md), so the live light tier gets the relieved shape only through the baked
   normal pass of `--live` (the same production bake). The floor changes none of these either.

## Left out of this round

- A production bake. The floor alone gave too small a gain to pay for 145 minutes; it rides with the next one.
- The high-passed photo and closed-crack scans (`prep_textures.mjs`): the photo stays `marble_cliff_06` exactly. The
  reviews named its crackle web as the strongest tell in every version, so the next rock round starts there.
- Finer meshes for the abode cliff or a baked displacement, which real beds need (see Known limits).
- The second joint set and the block tilt in the material: they put steps in the height (attack_2).
- The `rock_bed` attribute on pillars and any `nature.py` change: beds are simply off on pillars.
- Lathe UVs, direction smoothing, the stair chart rule, the steles paving class, any atlas growth and `sect_pack.py`.
- The forge's tomb and cairn rock are still not in `bake_web.DETAIL_CLASSES`, so neither the floor nor the page's rock
  layers reach them.
- The moss cushions do not follow the beds (see above).
- Relief on the range heightfield (`world.range`): no refinement, no relief (attack_0). If the walls under the mirror
  hall and the steles still lead the next review, the next round does them with edge cuts at the bed boundaries within
  150 m.
- Relief on `arena.islet` (the islets orbiting the arena), the gate's stair ridge, Ice-Fire Island, the range
  undersides, the backdrop and the far set: not in this round's list.
- A near-hold LOD floor for relieved pieces (plan_0's `RELIEF_HOLD_FLOOR`): attack_0 showed those pieces already ship
  whole where the budget does not bind; the screen-size relief floors cover the chunks where it does.
- The `geo_blk` and `geo_lip` attributes (per-block tone, streaks from real bed tops): the round 59 material reads only
  `geo_w`.

## Known limits

The floor (on):

- At 3 to 4 texels a metre a texel is 0.25 to 0.33 m, so far rock still holds nothing much finer than half a metre.
  Rock past 400 m gets no floor and keeps vertex colours.
- The floor has no occlusion test: rock hidden behind a hall but facing a hold also gets texels.
- Its gain at the page's size is small. In round 59's test bake, the abode cliff's cracks were a little sharper, and
  only visible at twice the page's size.
- A refit can force an item past an atlas's room (the steles: one item, about 1 % over). The packer then shrinks that
  atlas's layout, so everything in it gets slightly fewer texels.

The material (off; these hold when it is on):

- Bump casts no shadow: an overhang darkens its recess by colour, not by a shadow, and under the 7 degree sun shelf
  tops get their light mostly from the key.
- Beds drawn through a Bump read as painted lines under the 7 degree sun. In the first build a recess went to about a
  quarter of the brightness of the rock around it, from the Bump's own shade plus the albedo cavity. Toned down
  enough to lose that, the structure barely shows.
- The photo's crackle runs unbroken through every bed and joint, so any painted structure looks laid on top of it.
- The two close stills were 6 to 8 % brighter than today's in every version, because the old graph's dark drawn
  cracks and stains are gone.
- The range's kept cones (`world.py PILLAR_KEEP_CONE`) are part of `world.range`, so no object property can turn the
  world beds off there: they get the 2.75 m world beds over their modelled 11 m steps. Round 59's stills showed this
  as thin rings round the library's rock tower.
- On a relieved column the material's joints come back at half strength where `geo_w` is under 0.25: within about
  3 m of a plant on a shelf, under the cap and at the foot. Small patches of grooves may show round shelf plants.

The relief (off; these hold when it is on):

- Moving the vertices of a coarse mesh gives pleats and soft lumps. On the abode cliff's sunlit shoulder it made a
  fan of 6 to 8 creases like pleated cloth, a new ledge beside the bamboo let the lawn show through, and where the
  rock moved the material's beds faded with nothing sharp in their place. The cliff needs a finer mesh first.
- Nothing pins the rope bridge's anchor at the gate: the far-left column at gate 93 was shaved away from it and from a
  side shrub.
- Round 59 counted 82 targets: 61 columns, 20 floating rocks and 1 cliff. The floating rocks moved 0.03 to 0.47 m on
  average and showed no visible change; the arena island's underside is in no still.
- Outlines change only on the relieved objects. Range peaks that stayed cones keep their outlines.
- The film and every scene preview show the old rock (see the top of this page).
- While a chunk bakes, the relieved objects of other chunks still cast shadows and bounce light with their old shapes
  (they are the scene's own objects then). The error is a few metres of shadow edge at most, and only where one
  relieved object shadows another chunk's piece.
- Plants keep their cached sun visibility from the old rock (bake_trees.py runs on the scene). Only near walls can a
  plant's light be a little off.
- A relieved column stays inside its old cone, but the relief can stand up to 2.3 m out on the cliff and the
  islands (0.8 m from the field, the rest where a block's flattening fills a cleft). Anything closer than the pins'
  fades (a prop 2.5 m from the rock) keeps unmoved rock round it.
- Bed steps at 150-400 m from every view get 1.5 to 3.4 texels a metre (attack_0): they bake as soft lines there. The
  relief reads best on the abode cliff, the near columns and the arena island.
- Two bed systems, when the material and the relief are both on. The material's world beds (`ROCK_BED`, 1.8 to
  5.6 m) and the relief's beds (`GEO_*`, 2.5 to 11 m) are separate. On the abode cliff the material's beds come back
  where the relief is pinned (its dressed rock, the inscription, near plants and halls, flat tops), and they do not
  line up with the relief's. The bed lines also do not run on from a relieved object to the unrelieved range beside
  it. Round 59's relief stills showed one such break: a painted bed line that stops for about 60 px at the edge of
  the pinned inscription zone.
