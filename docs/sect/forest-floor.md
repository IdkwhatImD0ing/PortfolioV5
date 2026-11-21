# The forest floor

Added 2026-11-20. The leftover from the black holes in the mist
([`render-probe.md`](render-probe.md), "What is left").

## What was wrong

The ground under the far forests was nearly black. Where the trees are drawn as baked cards and
stand apart, it showed as dark gaps between the crowns: on Medium, on Low, and on High once the
quality ladder has taken the crown shells off. The clearest view is the mirror terrace looking
right over the valley, where it also ran as a black strip along the cliff's foot.

## What that ground is, and why it is dark

Found in the page, on a local build:

- **It is each area's own ground**, not the backdrop. Hiding one group of meshes at a time, the
  gaps turned to sky when the ground class went (`baked.<area>_A<n>.detail.ground`, the atlas
  material with `detail: "ground"`). Hiding the backdrop's far set changed nothing in that view.
- **The bake left it unlit.** With the ground coloured by its baked texel's brightness, the forest
  floor is under 0.002 (linear luminance, where 1 is white). The trees stand over it in the bake,
  so no light reaches it. A lawn in a hall's or a tree's shadow is 0.01 to 0.04, and a lit lawn is
  0.04 and up. So the two are easy to tell apart.
- **No layer darkens it.** The grade, the ground's layers and the "far lawns as canopy" layer all
  multiply the colour, so black stays black. The slate tone the gaps had was only the haze over
  black.

## The change

In the page's shaders, with no bake (`RANGE_LOOK.floor` in `client/src/lib/sect/range-look.ts`):

- A ground texel under 0.002 is replaced by undergrowth in shade: the canopy's green (`#4d6b35`)
  at a brightness of 0.05. From 0.006 up nothing changes, with a smooth step between. That is
  below any shadow on a lawn.
- It happens before the grade, in the ground's own grade (`groundGradeStatements`). So the grade,
  the day along the flight, the night stops and the ground's layers treat it like any shaded lawn.
- Ground only. Rock is another class and never runs it, so dark rock and cliff shade stay. Halls
  and paving have no class and never run it, so building shadow stays.
- On the range only, like the rest of the range look: inside a stop's footprint plus 30 m the
  ground keeps its bake.
- Every tier has it, Low too, because it sits in the grade and not in the detail layers.
- Grass. On High a few tufts and rim clumps root on the edge of that ground (the ones right on it
  are dropped as covered). They kept the bake's near black and stood on the lifted floor as black
  specks. Their roots now take the same texel as the ground under them (`liftRootSteps` in
  `grass.ts`, `floorLift` in `range-look.ts`), with the same stops left alone.

`?floor=0` loads the page with the lift off, for a before and after on one build. It is one shared
uniform (`uSectFloor` in `SECT_AREAS`, `materials.ts`), so the switch builds no shader.

### Picking the brightness

Six levels were shot at the mirror terrace on Medium. Measured on screen, in sRGB levels out of
255:

| | red, green, blue |
|---|---|
| The floor before | 40, 45, 50 |
| The darkest third of the crowns | 46, 55, 60 |
| The crowns' middle | 58, 73, 68 |
| The floor now | 57, 72, 64 |

At 0.02 and under the floor hardly moved, because the grade's contrast pushes darks down. At 0.08
and over it was as light as the lit crowns and read as a lawn under the trees. At 0.05 it sits at
the crowns' middle: the gaps close and the floor still reads as shade.

## What was checked

On a production build of this change, in headless Chrome on the PC (RTX 5080), lift off
(`?floor=0`) against on.

- **Before and after**, six turned views on Medium and at the ladder's bottom (High stepped down
  ten times: stand-ins, cards): the mirror terrace twice, the arena, the mission hall, the
  formation and the abode at night. 0.7 to 4.2 percent of the pixels change by more than 12
  levels. They lie between the crowns and go from slate to green (the rest is what moves). At the
  mirror terrace with motion frozen, the lift alone is 2.9 percent of the frame.
- **Where it lands.** All eleven stops straight on and turned 50 degrees left and right, on
  Medium, with the changed pixels marked. They are in the forests and nowhere else: no lawn at a
  stop, no rock, no wall. What else differs between two pictures is what moves (flags, fire,
  petals, mist).
- **High with shells**, the eleven stops straight on: see the numbers below.
- **Low**: the same view has the lift. Low has no detail layers, so its floor is one flat tone.
- Typecheck, lint and the unit tests pass. New tests cover the texel test, the stops, the switch,
  that rock and halls never run it, and the grass roots.

### High with shells, the eleven stops

The picture must not change there: the crowns are dense, and the stops are what the owner signed
off. Two measures, each a share of the frame's pixels (the probe's debug HUD left out).

- **Three probe runs** (`render-probe.mjs`), two with the lift off and one with it on, compared by
  `render-compare.mjs` (pixels that differ by more than 40 levels of 255). Two runs of the same
  page differ because flags, fire, grass and water move.
- **The lift alone.** One page with motion frozen (the browser's reduced-motion setting), the lift
  switched off and on in place. Here a pixel counts from 12 levels, since the floor moves by about
  20.

| stop | two runs, lift off | lift off against on | the lift alone, motion frozen |
|---|---|---|---|
| gate | 0.16% | 0.41% | 0.00% |
| mirror | 0.12% | 0.37% | 0.09% |
| forge | 5.01% | 6.24% | 0.01% |
| arena | 2.65% | 2.17% | 0.06% |
| mission hall | 0.33% | 0.13% | 0.01% |
| library | 0.88% | 0.58% | 0.00% |
| steles | 0.01% | 0.02% | 0.00% |
| scroll | 0.03% | 0.05% | 0.18% |
| formation | 0.52% | 0.50% | 0.68% |
| abode | 1.02% | 1.71% | 0.22% |
| summit | 0.28% | 0.18% | 0.00% |

Off against on is in the same band as two runs of the same page (the forge's orbiting artifacts
are the 5 and 6 percent). The lift itself moves under 0.7 percent of the pixels at any stop, and
under 0.01 percent by more than 40 levels. Where it does (the formation's left slope, the scroll's
right slope, a patch between the abode's gate and its cliff) it is forest floor that shows through
the shells.

The frozen test does not include the grass roots: they are set when a place's grass is built, so
a switch in place leaves them. The three probe runs do include them.

No frame of the three runs held a pixel that is not a number.

## Limits

- The floor is one colour with the ground's usual patches on top. It has no light of its own: no
  sun flecks, no shadow of a single tree. A bake round would do that.
- A forest inside a stop's footprint plus 30 m keeps its black floor. None was found in view.
- The backdrop's far set and the stand-ins are vertex-coloured and have their own repair for
  black vertices (`vertex-colors.ts`). This change does not touch them.
- Not looked at on a real slow machine. The cost is one `mix` in the ground's shader, and 4 to 8 ms
  when a place's grass is built on High, spread over slices like the steps beside it.

## The tools

`client/scripts/render-probe.mjs` with `--extra floor=0` for the picture before. The pictures and
the scripts that hid mesh groups and tried the levels are in `.playwright-mcp/floor/` on the PC
that ran it (not in git).
