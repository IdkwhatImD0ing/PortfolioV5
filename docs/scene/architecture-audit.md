# Architecture audit: fix plan

> Moved here from `blender/xianxia-sect/docs/` on 2026-10-24, when every doc moved into `docs/`. File paths inside it are relative to `blender/xianxia-sect/`.

Date: 2026-10-10. Covers all 11 areas, from the Mountain Gate to the Moon-Gazing Summit.
Each area was checked against the project skill `.claude/skills/sect-architecture`. Its one
rule is that a visitor can walk to every front door, and every stair, bridge and walkway starts
and ends on something solid.

## The short version

All 10 links between areas are broken at both ends. Stairs start on bare grass with no path to
them. They land on grass, off-centre, short of the next area's paving. Seven of the eight
connector stairs end buried in a cliff, so a climber would face a rock wall.

Inside the areas, almost every building can be reached. There are four exceptions. The arena's
three tier pavilions have no stair. The formation altar has no stair. The stele pavilion's steps
are buried inside its own platform. The Mission Hall can be reached, but the mission wall hides
its stairs in every approach shot.

Most of this comes from one function, `_stairway` in `sect/world.py`. It aims each stair at a
point 4 m inside the next terrace and 0.4 m below the paving. Its sideways wiggle never fades out
at the ends. It also hugs the ground, so most steps come out about 0.65 m tall. A normal step is
0.17 m, so they are almost four times too tall. Fixing `_stairway` once (section 2) and adding a
landing and a gate at each area's edge (section 1) clears most of the problems.

The AI style frames make it worse. Where the blocking leaves a gap, the image model paints over
the route. It turned a stair into a waterfall, a stair head into a pavilion, and a lawn into a
gorge. A prompt can't add geometry the blocking lacks, so prompts come last (section 3).

The audits found 36 high-severity problems. 31 are geometry. 5 are style frames or prompts. A
few are the same break seen from both ends of a link.

## Tags

- [Blender]: changes geometry. Needs a Blender re-render on the cloud GPU before it shows in any image.
- [Style frame]: needs a new style frame from OpenAI. No re-render.
- [Prompt]: text only. Free to write. It costs Higgsfield credits only when you regenerate that video segment.

Everything in sections 1, 2 and 4 is [Blender]. Section 3 items carry their own tags. Section 5
lists exactly what to re-render and regenerate.

## Order of work

1. Do sections 1, 2 and 4 in one pass. Sections 1 and 2 share coordinates: each area declares
   where its stairs arrive and leave, and `world.py` aims at those points. Section 4 rides along
   so you only render once.
2. Build headless and run `walkcheck.py` (W9). This needs no GPU.
3. Check the chase camera still clears the new stairs, bridge, archways and dome.
4. Re-render on the cloud GPU (section 5).
5. Write the new prompt files (section 3).
6. Regenerate the style frames, then the video segments.

## Coordinates

Each area uses its own frame, in metres. The front, where you arrive, is -y. x is to the right as
you arrive. z 0 is the main paving or lawn, and the grass around most terraces is at z -0.4.
The arena is the exception: its z 0 is the dueling floor, and its grass is about -1.5.
"W1" to "W9" refer to the `world.py` fixes in section 2.

---

## 1. High-severity breaks, by area

Areas are listed in flight order. Each area also gets the landings that W1 needs, even where the
audit rated them medium.

### 1.1 Mountain Gate

1. The terrace buries the top of the grand stair. `TERRACE_PAD` is now 9 m, so the terrace edge
   moved out to about 50.5 m. `gate.py` still puts the stair top at y -46. Up to 2.9 m of moss
   covers about 20 of the top flight's 24 steps. You can see it as a dark band in
   `out/stills/seg01_start.png`.
   Fix: carve a notch for the stair in `world.py` `Range.fields`, inside the
   `if "gate" in self.anchors:` block, after the terrace loop:
   ```python
   cut = (along > 0) & (lat < 15.0)
   T = np.where(cut, np.minimum(T, gz - 1.0 - 0.82 * np.minimum(along, 5.3)
                                - 0.6 * np.maximum(along - 5.3, 0)), T)
   ```
   This keeps every `gate.py` number and camera hint. Also fix the stale comment on `gate.py`
   line 36 ("radius footprint + 6").
2. Nothing leads from the plaza to the stair to the mirror. The back opening (x ±6, y 23.6) ends
   in a 0.4 m drop onto moss. The stair starts 28 m to the west, at (-27.9, 35.2).
   Fix: in `gate.py` `_plaza`, add
   `_grid_slab("depart_landing", coll, root, -6.0, 6.0, PLAZA_Y1, 36.0, -0.6, 0.0)`. That is a
   12 x 12 m landing on the axis. Extend the side balustrades to y 35.6 at x ±5.6.
   Declare depart = (0, 36, 0), heading +y (W1).
3. Style frame: see 3.2, Gate.

### 1.2 Heart-Mirror Terrace

1. The stair from the gate is buried at both ends of its climb. Its top 6 steps sit 0.6 to 3.3 m
   under the terrace. In the middle, about 30 steps run up to 12 m deep inside a ridge.
   Fixed by W2.
2. No arrival landing. The stair's last step, at (-9.5, -49), is 7.5 m from where the paved path
   starts at (-5, -43), and 0.5 m below it.
   Fix: declare arrival = (-5, -51.5, -0.4), heading +y. In `mirror.py` add
   `_strip(_n('arrival'), coll, [(-5,-50.5), (-5,-43)], 7.0, 0.12, -0.6, 'marble_paving', root)`
   and three steps up to it:
   `A.stairs(_n('arrival_steps'), coll, 5.0, 0.52, ramp=False, location=(-5.0, -50.5, -0.4))`.
   Lower the lawn `edge_drop` to about 0.2.
3. No path to the stair to the forge. It starts on grass at (47.5, 13.8), 30 m from the nearest
   paving.
   Fix: add `PATH_FORGE = [(18.5, 0.0), (30.0, 5.0), (41.0, 11.0)]`, 2.4 m wide, top 0.12,
   branching off the east path. Add a 6 x 6 m landing centred at (44, 12), top 0.12, with three
   steps down its east edge (`A.stairs`, width 5, height 0.52, rotation +90°). Declare
   depart = (48.5, 13, -0.4), heading +x.
4. Style frame: see 3.2, Mirror.

### 1.3 Artifact Forge Peak

1. The stair from the mirror runs into the cliff. Its last 14 steps sit up to 7.1 m below the
   terrace. Fixed by W2.
2. No arrival landing. The stair tops out on grass 7 m short of the plaza and 0.4 m below it. It
   points at the archway's outer-left column, not its centre opening.
   Fix: in `forge.py` add
   `A.platform(_n('arrival'), coll, 12.0, depth=11.0, height=0.4, style='plain', parent=root, location=(0.0, -52.5, -0.4))`.
   It spans y -58 to -47 with its top flush at z 0. Add stone lanterns at (±5, -56). Declare
   arrival = (0, -58, 0), heading +y. W1 then lines the stair up with the centre opening.
3. You cannot walk from the plaza to the chain bridge to the arena. The bridge starts behind the
   left side hall, outside a closed balustrade. The cause is a 22 m sideways offset in
   `build_connectors`.
   Fix: W5 removes the offset, so the bridge starts at (-53.3, -8.9, 0), at an angle of 189.5°.
   In `forge.py`:
   - `BRIDGE_ANG = math.radians(189.5)`.
   - Split `_terrace_balustrade` into two arcs, -76° to 183.5° and 195.5° to 256°. That leaves a
     9.8 m opening.
   - Add a bridgehead: `A.platform(_n('bridgehead'), coll, 8.0, depth=10.0, height=0.4, style='plain', parent=root, location=(-51.3, -8.6, -0.4), rotation_z=math.radians(99.5))`.
     Name it `forge.bridgehead` so walkcheck counts it as a landing.
   - Add a one-bay gate: `A.paifang(_n('bridge_gate'), coll, bays=1, width=6.0, height=7.0, roof_mat='roof_tile_black', parent=root, location=(-46.0, -7.7, 0.0), rotation_z=math.radians(99.5))`.
   - Add stone lanterns at (-52.0, -4.7) and (-50.6, -12.5).
   - Move quench trough 0 from (-18, -10) to (-18, -15). It sits on the new walking line.

### 1.4 Sword-Discussion Arena

1. The bridge from the forge lands on grass 17.6 m right of the front steps. Its deck end hangs
   1.2 to 1.4 m above the ground.
   Fix: W5 lands it on the axis. In `arena.py` `_build_entrance`:
   - Bridgehead: `A.platform('arena.bridgehead', ...)`, 12 wide, 8 deep, 0.3 high, plain,
     centred at (0, -41, -1.8). Its top (-1.5) is flush with the foot of the front steps.
     Print `rim(-pi/2)` first and keep the slab's outer edge 1 m inside it.
   - A paved strip from the slab to the front steps, between the lanterns at (±6.5, -38).
   - A three-bay paifang about 10 m wide at (0, -44.5, -1.5). Keep it 8 m tall or less so the
     "rim" camera at z 12 clears it.
   - Balustrades along both sides of the slab.
   - Declare arrival = (0, -45, -1.5).
2. Nobody can walk to Mission Hall. The first stepping stone is a jump over the void. 8 of the 11
   hops climb more than 1.2 m, which is the comfortable limit. The last stone is 1.55 m below the
   Mission terrace and 24 m off its axis. Also, the only way off the banner walkway is the front
   steps, so the back of the island is a 110 m walk round the grass.
   Fix: W6 rebuilds the stones. In `arena.py`:
   - A stair from the banner walkway down to the grass at 107°, between two banner poles:
     `A.stairs(..., width 2.5, height 1.45, run_per_step 0.3, ramp=False, balustrade=False, location=(-9.9, 32.5, -1.8), rotation_z=a + pi/2)`.
   - A paved path from its foot to an 8 x 6 m rear landing centred at (-13, 43), top -1.8. Keep
     its outer edge 1 m inside `rim(107°)`. Put a balustrade on the void side.
   - Declare depart = (-13, 43, -1.8).
3. The three pavilions on the spectator tier have no way up. The tier is five 0.85 m seat steps
   with no aisle.
   Fix: first trim the tier (section 4, arena). Then add an aisle stair in front of each
   pavilion, at a = -31°, 0° and +31°:
   `A.stairs(U.name(K, 'tier_aisle'), coll, 2.0, tops[-1] - Z_BAND, run_per_step=0.26, ramp=False, balustrade=True, parent=root, location=(radii[-1]*cos(a), radii[-1]*sin(a), Z_BAND), rotation_z=a - pi/2)`.
   Its risers come out at 0.17 m. Move the banner pole at 0.1° about 2 m sideways, because it
   stands 1.3 m in front of the centre aisle's foot.

### 1.5 Mission Hall

1. The way in from the arena fails (stones, see 1.4). On the Mission side there is no landing.
   Fix: a new `_arrival()` slab at x -10 to 10, y -58 to -44, top 0, bottom -1.0,
   `marble_paving`. Run the axis walk out onto it to y -58. Put a balustrade on its sides and
   front, with a 6 m gap at x 0 where the last stone touches. On the axis the terrace edge is at
   y -61.5, so the landing fits 3.5 m inside it. Optional: a three-bay paifang at (0, -47).
   Declare arrival = (0, -58, 0). This also removes the 0.4 m step at the plaza's front opening.
2. No way out to the library. The stair starts 17 m outside the east railing, right behind the
   bell tower and the east corridor. The railing has no gate.
   Fix: split `plaza_rail` to leave a 6 m side gate on the east edge at y -15 to -9. Optional:
   a small gate arch there. Run a straight 5 m wide paved spur along y -12 from the gate to a
   landing at about (52, -12). Declare depart = (54, -12, -0.4), heading +x. Keep y -12 clear of
   the corridors (section 4).
3. The mission wall hides the whole route to the hall. From the approach camera, the line of
   sight over the wall's roof crosses the terrace front at z 8.6. The terrace is 3 m tall, so
   the terrace, its stair and the hall stair never show. In `kf_mission.png` the hall ends up
   sitting on the wall's roof, with no stair or door anyone could reach.
   Fix in `mission.py`:
   - `WALL_Y` -19 to -30. `TABLET_HANG` 9.2 to 7.0. `WALL_TOP` 10.9 to 8.4.
   - Wood-tablet rails from z 3.6 / 2.35 to 3.3 / 2.1.
   - Stone lanterns from y -38 / -26 to -40 / -20.
   - `CAMERA_HINTS['wall']`: location (0, -58, 7.5), target (0, -30, 5.5).
   - Optional: in `_hall`, change the `- 2.5` in `t_front` to `- 8.0` for an 8 m moon terrace,
     and move the censer to (0, -9).
   After this, the sight line crosses the terrace front at about z 2.4, so the terrace edge,
   the hall stair and the doors all show.

### 1.6 Scripture Pavilion (library)

1. The stair from the Mission Hall is buried at the top. Its last 5 steps sit 0.65 to 3.24 m
   inside the plateau, so a climber meets a 3 m rock wall at the lip. Fixed by W2.
2. No arrival landing (rated medium, but W1 needs it). The stair lands 9 m left of centre and 6 m
   short of the walkway. The walkway's end stands 0.55 m above the grass with no step.
   Fix: declare arrival = (0, -49, -0.25), heading +y. In `library.py` `_ground` add
   `_slab(_n('arrival_landing'), coll, root, -6.0, 6.0, -49.0, -41.0, top=-0.25, bottom=-0.6)`
   and `A.stairs(_n('arrival_steps'), coll, 8.0, 0.4, ramp=False, balustrade=False, location=(0, -40, -0.25))`.
   Add a three-bay paifang about 12 m wide at (0, -42.5, -0.25) as the entrance gate, and a
   balustrade along the landing's south edge on both sides of the stair head.
3. No way out to the Stele Forest. The stair starts at the plateau's front-left rim. The straight
   line to it from the pagoda crosses the lotus pool.
   Fix: declare depart = (-44.7, -10.8, -0.4). Add a 3 m paved path from the plaza's south-west
   face at (-10, -1) to (-44, -10), top 0.15. It passes about 3 m north of the pool and 4 m south
   of the pine at (-36, -2). End it with `A.stairs` (width 3, height 0.55, rotation -90°) down
   to the stair head.
4. Style frame: see 3.2, Library.

### 1.7 Stele Forest

1. No way out to the Jade Slip Pavilion. Its stair starts on grass 18 m behind a solid back wall
   with no gate. Both corridors dead-end against that wall.
   Fix in `steles.py`:
   - Split the back wall into (-28.6, 35.5) to (-17.5, 35.5) and (-12.5, 35.5) to (28.6, 35.5).
   - Put a one-bay gate in the gap: `A.paifang(bays=1, width=5.0, height=6.0)` at (-15, 35.5, 0),
     facing -y. Its opening is about 3.4 m wide and 3.8 m tall. Add a matching gate at x +15
     for symmetry.
   - Inside: a 3 m marble walk (top 0.06) west along y 9 to 12 from the aisle to x -15, then
     north along x -16.5 to -13.5 to the gate.
   - Outside: a 3 m strip on the terrace (top -0.34) from the gate to the stair head.
   - Move the left pine from (-17, 41.5) to about (-27, 46). It stands on the new path.
   - Declare depart = (-15, 44, -0.34), heading +y.
2. The stair from the library lands on grass 16.5 m in front and 17 m left of centre. Its last
   flight points at a corridor corner. The aisle's front edge is a 0.46 m ledge with no steps.
   Fix: declare arrival = (0, -56, -0.34), heading +y. Add:
   - A paved forecourt: box x -9 to 9, y -57 to -37.5, top -0.34.
   - Three steps onto the aisle: `A.stairs(width 15, height 0.40, ramp=False, balustrade=False)`
     at (0, -37.5, -0.34). The risers come out at about 0.13 m.
   - An entrance gate: `A.paifang(bays=3, width=34, height=24)` at (0, -50, -0.34). Its centre
     opening is about 12.3 m wide and 15.4 m tall. It sits 4 m behind the hero camera, so the
     hero frame does not change.
3. Both stairs at this area have giant steps and end about 1.3 to 2.6 m under the rim.
   Fixed by W2 and W3.

### 1.8 Jade Slip Pavilion (scroll)

1. The stair from the steles ends on lawn 25 m in front of the terrace and 23.5 m left of the
   pavilion's axis (x 12). Nothing marks the arrival.
   Fix: declare arrival = (12, -44, -0.35), heading +y. In `scroll.py` add:
   - A paved walk: `A.platform(_n('approach'), coll, 6.0, 25.0, height=0.05, style='plain', sink=0.3, parent=root, location=(12.0, -31.5, -0.4))`.
     It runs from y -44 to -19.
   - Stone lanterns at (8, -42, -0.35) and (16, -42, -0.35).
   - Front steps onto the terrace: `A.stairs(_n('front_steps'), coll, 6.0, 0.35, ramp=False, balustrade=False, parent=root, location=(12.0, -19.0, -0.35))`.
2. No way out to the formation. The right railing has no opening. The stair head is 16 m out on
   unmarked grass, past the scholar rock.
   Fix:
   - In `_terrace`, end the right rail at `(x1 - e, 0.0)` instead of `(x1 - e, y0 + 8)`.
   - Side steps: `A.stairs(_n('side_steps'), coll, 5.0, 0.35, ramp=False, balustrade=False, parent=root, location=(27.0, -3.5, -0.35), rotation_z=math.pi/2)`.
   - Exit walk: `A.platform(_n('exit_walk'), coll, 17.0, 5.0, height=0.05, style='plain', sink=0.3, parent=root, location=(35.5, -3.5, -0.4))`.
   - One-bay gate: `A.paifang(_n('exit_gate'), coll, bays=1, width=7.0, height=7.0, parent=root, location=(41.0, -3.5, -0.35), rotation_z=-math.pi/2)`.
   - Move the scholar rock from (24, -8) to (22, -14).
   - Declare depart = (44, -3.5, -0.35), heading +x.
3. Both stairs have steps about 0.65 m tall, with no landings. Fixed by W2 and W3.
4. The stair into this area starts behind the steles' back wall. Fixed in 1.7, item 1.

### 1.9 Grand Sect-Protecting Formation

1. No way out at the back. The 1.1 m railing closes the whole back of the plaza. The stair to
   the abode starts 15 m outside it.
   Fix in `formation.py`:
   - Split the `_rim` railing into two arcs, -76.5° to 83° and 97° to 256.5°. That leaves a 12 m
     opening at x -6 to 6. The back axis is clear of pillars and pads.
   - Rear gate: `A.paifang(bays=1, width=10, height=11, location=(0, 46.5, 0), rotation_z=math.pi)`.
   - Rear apron: `marble_paving` box at x -6 to 6, y 49.5 to 61, top 0.
   - Steps down: `A.stairs(name, coll, 8.0, 0.4, ramp=False, balustrade=False, location=(0, 61, -0.4), rotation_z=math.pi)`.
     That gives three risers of 0.13 m.
   - Declare depart = (0, 62, -0.4), heading +y.
2. The stair from the scroll lands on grass 12 m outside the rim and 10.8 m right of centre. It
   points at the archway's outer column. The plaza is a 0.4 m kerb all the way round.
   Fix: declare arrival = (0, -62, -0.4), heading +y. Add an `_approach()`: a `marble_paving`
   box at x -7 to 7, y -61 to -49.5, top 0;
   `A.stairs(name, coll, 8.0, 0.4, ramp=False, balustrade=False, location=(0, -61, -0.4))`;
   and stone lanterns at (±5, -59.5).
3. The stair to the abode misses the abode's path by 24 m. Fixed in 1.10, item 1.

### 1.10 Cave Abode

1. The stair from the formation lands 24 m right of the path line and 7 m short of it. The path,
   the balcony stair and the moon gate all sit on x -8.
   Fix: declare arrival = (-8, -51, -0.4), heading +y. In `abode.py` add
   `_box(K + '.arrival', coll, root, (8.0, 6.0, 0.4), (GATE_X, -48.0, -0.4), 'marble_paving')`
   and extend the path box to meet it. Call `N.ground_patch(..., radius=50.0, edge_drop=0.2)`.
   Today the lawn drops away under the path, so the path starts with a 0.5 to 0.7 m ledge.
2. No path to the summit stair (rated medium, but W1 needs it). The stair head is 41 m west
   across open lawn, past bamboo and a rock. The cliff's end covers half its width.
   Fix:
   - `_box(K + '.path_west', coll, root, (38.0, 3.0, 0.4), (-27.0, 0.0, -0.1), 'marble_paving')`.
   - `_box(K + '.depart', coll, root, (6.0, 6.0, 0.4), (-47.0, 0.0, -0.3), 'marble_paving')`.
   - Move the bamboo at (-31, 6) to (-33, 14), the rock at (-12.5, 7) to (-13, 11), and the
     shrub at (-22, 2) to (-22, -5).
   - Two stone lanterns at (-49, ±3.4).
   - Declare depart = (-52, 0, -0.4), heading -x. That is clear of the cliff's end.
3. Two style-frame breaks: see 3.2, Abode.

### 1.11 Moon-Gazing Summit

1. The stair's top 7 steps are buried 0.7 to 3.2 m inside the summit cliff. In
   `out/stills/seg08_start.png` the treads vanish into rock 3 to 4 m below the rim.
   Fix: declare arrival = (0, -38.5, 0), heading +y. That is on the marble terrace, inside the
   balustrade gap, 6.5 m in front of the crescent arch. W1 and W2 then bring the stair up the
   cliff on piers, centred on the arch. It also fixes today's 5.5 m sideways miss.
2. The stair is far too steep to climb. It drops 25 m from the abode, then climbs 95 m in one
   flight of 147 steps. Each step is 0.65 m tall, with no landing anywhere.
   Fixed by W2 and W3. At 0.17 m per step that is about 410 steps with about 20 landings. Put
   an archway on the foot landing and a small rest pavilion near halfway (world z about 285).

---

## 2. Cross-area connector fixes (`sect/world.py`)

### W1. Stairs aim at declared landings, straight on at both ends

Today `_stairway` starts and ends at footprint + 4 m, at z - 0.4. Its sideways offset is
`meander * sin(pi * t)`, which is not zero at `t0` or `t1`. That puts stair ends up to 24 m off
an area's axis, on grass.

Fix:
- Each area module adds `depart` and `arrival` to its `AREA` dict as (x, y, z, heading) in its
  own frame. Section 1 gives every value. `world.py` converts them with the anchor's position
  and yaw.
- The stair runs from area A's depart point to area B's arrival point. Its first and last step
  sit at the declared z, flush with the landing, not 0.4 m below.
- The first and last 15 m run straight along the declared heading.
- In between, the sideways offset is `meander * sin(pi * u) ** 2`, with u going from 0 to 1
  over the middle part. Both the offset and the turn are zero where the straight runs start.
- Optional: make the ridge crest in `Range.fields` follow the same centreline, so stairs ride
  the ridge instead of piers.

This fixes the off-axis and on-grass landings at all 11 areas.

### W2. A stair profile that never dives and never goes underground

Today `_path_z` hugs the terrain with a slope limit of 0.8. So stairs dive 11 to 44 m into
valleys before climbing out. One runs 12 m deep inside a ridge (gate to mirror). Most arrive
under the rim, because the cliff rises 3.2 m per metre and the stair may only climb 0.8.

Fix: replace the stair profile with one steady climb, raised over any bump:
```python
z = np.linspace(z0, z1, n)            # steady climb, no dive
z = np.maximum(z, h + clear)          # never inside the ground
g = 0.57                              # 0.17 m riser on a 0.30 m tread
for i in range(n - 2, -1, -1):        # ramp up to each bump...
    z[i] = max(z[i], z[i + 1] - g * ds)
for i in range(1, n):                 # ...and down from it
    z[i] = max(z[i], z[i - 1] - g * ds)
```
Both passes only raise points, so no step ends up below the ground. Add a check that
`z >= h - 0.05` everywhere. Where the ground falls away, the stair rides on piers like a
viaduct. If any link's average slope comes out above 0.57, it needs a switchback. None should,
but check the build log.

This fixes the buried ends at mirror, forge, library, steles, scroll, abode and summit, the
buried middle of gate to mirror, and the valley dives.

### W3. Human-size steps with landings

Today each 0.8 m sample is one step, so the riser is whatever the height change is. The median
riser is 0.65 m. A comfortable riser is 0.15 to 0.18 m.

Fix:
- For each sample, build `ceil(abs(dz) / 0.17)` sub-steps, with tread = sample length / count.
- After every 18 risers, hold z flat for at least 2 m as a landing. Re-run the W2 passes so no
  riser goes over 0.18 m.
- Put an archway on each stair's foot landing. Put a small rest pavilion on the middle landing
  of any stair longer than about 100 m. Mount Tai marks every stage this way.

Rough counts from the audits: gate to mirror about 177 steps, formation to abode about 177,
library to steles and steles to scroll about 118 each, abode to summit about 410.

### W4. Piers and the arched bridge (library to steles)

Today piers go in every 11 samples. On library to steles the first pier comes at step 11, so
7 m of stair hangs 2.5 to 18 m over the cliff. The "arched bridge" deck climbs 24 m at about
29°, and its arch is a fixed 22 m deep.

Fix:
- Piers every 6 samples wherever the stair is more than 4 m above the ground.
- Make the bridge deck level, or at most 1 in 10, with a 3 m landing at each end. The flights
  before and after take the rise.
- Arch depth at each sample = `z - h`, so the arch reaches the ground, not a fixed 22 m.

Revised 2026-10-21 (site audit D1). Piers every 6 samples (4.8 m), with a round-headed arcade
between them and tie arches every 12 m down, read as a Roman aqueduct. It was the most repeated
style break of the flight, large in about 10 of 35 audit frames. The rule now
(`world._supports`, `sect/patch_r2_links.py` for the finished scene):
- Where the treads stand more than 4 m over the ground, piers split each such run into equal
  spans near 17.5 m and never more than 20 m between supports (`PIER_SPAN`). A pier, a footing
  end, the arched bridge or an area counts as a support. Each pier is nudged by up to 12% of its
  span, so a row of them is not a fence.
- Each pier is a heavy shaft (3.4 m along the stair at the top, just inside the parapets across
  it) that widens 2% per metre down, to at most 2x, into the ground. Its head is three stepped
  cantilever courses that reach out along the stair, not sideways.
- Under the lower stretches, where the soffit stands over the ground, a solid footing runs from
  the soffit into the ground. Its end is the abutment where a run of piers starts.
- No arcades and no tie arches.
- Piers, footings, the arch and the stairs' undersides are `world_pier_stone`, now the cliff
  rock's sandstone (#8a8172 to #5e5a52), so the supports recede into the cliffs and the white
  stair reads on top of them.
- Every stair still meets its landings at both ends. The patch rebuilds each plan from the ports
  and checks that it reproduces the scene's treads to 1 mm before it touches anything.
- Not done yet: cliff-hugging stretches as rock-cut stairs.

### W5. Chain bridge, forge to arena

Today a 22 m sideways offset (`lat` in `build_connectors`) starts the bridge behind the forge's
side hall and lands it 17.6 m right of the arena's steps. It sags 7 m. Its last stretch is a
23° plank ramp. The planks are flat boxes 1.08 m apart, with up to 0.48 m height between
neighbours, so it reads as a ladder of loose boards.

Fix:
- Remove `lat` at both ends. p0 = forge bridgehead (-53.3, -8.9, 0). p1 = arena arrival
  (0, -45, -1.5).
- `sag=2.0`. That brings the worst slope down to about 15°.
- Pitch each plank to the deck slope and space planks about 0.35 m apart, or build one
  continuous deck.
- Add a `steps` option that rounds plank z to multiples of 0.17 m. Keep the last 4 m level.
- Check that the seg02 chase camera stays at least 8 m above the deck. The offset may have
  been there for camera clearance.

### W6. Stepping stones, arena to Mission Hall

Today there are 12 stones. Each hop climbs 1.0 to 2.3 m, and the line dips 2.5 m in the middle.
The first stone is off the island. The last is 1.55 m below the Mission terrace and 24 m off its
axis.

Fix (keep the stones, they suit the setting):
- Delete `p.z -= 2.5 * math.sin(math.pi * t)`.
- p0 = arena rear landing (-13, 43, -1.8). p1 = Mission arrival (0, -58, 0). No `lat`.
- `bulge` about 6. `count = ceil(rise / 1.1) + 1`, about 20 for the 21 m climb.
- `size = uniform(3.6, 4.4)`, flat tops, edge gaps 1.2 m or less.
- The first stone touches the rear landing at its height. The last is level with the Mission
  landing.

If the stones still don't read in the style frame, swap them for a second stepped chain bridge
between the same two points (sag 2, about 126 risers of 0.17 m).

### W7. Terrain under two areas (`Range.fields`)

- Gate: carve the stair notch (1.1, item 1).
- Summit: give it a flat radius of 39.5 m with no bulge:
  `rf = 39.5 if k == 'summit' else fp + TERRACE_PAD + bulge`. Today the flat ground runs out to
  49 to 55 m, so there is a 10 to 16 m ring of unrailed grass outside the balustrade. After the
  change the cliff starts right under the marble rim, and the balustrade becomes the cliff rail.

### W8. Scenery that reads as unreachable buildings

- `build_islets`: stop placing `world.islet.pavilion`. These tiny pavilions on floating rocks
  show in the arena, library and summit frames, with no bridge to them.
- `build_backdrop`: `top_flat=(i % 3 == 2)` makes some rock pillars look man-made. The image
  model turned the one behind the library into a walled tower with a pool. Set `top_flat=False`,
  at least for that pillar.

### W9. Verify before rendering

- Build headless, then run `.claude/skills/sect-architecture/scripts/walkcheck.py` at
  `--max-rise 0.7`, then `0.45`, over each area's bounds and each link. Each link should show
  as one connected piece from landing to landing.
- Re-check chase-camera clearance. The stairs no longer hug the ground, so in valleys they
  stand much higher than today. Also check the arena's new archway (8 m or less) and the
  formation dome.

### 2b. Shared building code (`sect/lib/arch.py`)

- `pavilion` with `sides=4`: the platform's half-width is `pr` (8.3 m on the stele pavilion),
  but the steps sit at `pr * cos(45°)` (5.9 m). So the steps are buried inside the platform.
  Build the platform with width `2 * pr * cos(pi / 4)`. Then check every other 4-sided pavilion.
- `pagoda`, line 3133: the upper storeys get `door_face=None`, so the balcony has no door. Use
  `door_face=0 if (k == 0 or balcony > 0) else None`. This fixes the scroll pavilion and the
  library pagoda.
- `tower`: add an option for a gap in the balustrade. The Mission galleries need it (section 4).

---

## 3. Prompt and style-frame wording

The style-frame prompts say Image 1 is the only source of geometry. So a prompt cannot add a
stair the blocking lacks. Write the new prompts now, for free. Generate only after the
re-render.

### 3.1 Lines every prompt gets

- End every style-frame and segment prompt with: "No isolated buildings without a path, no
  stairs ending in mid-air or in a rock wall, no doors without steps, no bridges or walkways
  stopping at a cliff edge, no railings standing alone on grass."
- Describe the route in walking order. Name both ends of every stair, bridge and path.
- Say what floats on purpose, and that nobody walks there: floating islets ("pines and
  waterfalls only, no buildings"), the forge artifacts, the formation's jade core, golden rings
  ("a band of light, not a platform"), and the arena chains ("tethers hanging below the rim,
  not walkways").
- Don't name things that are out of shot. Anything named gets drawn, usually without a path.
- Stop using: "dip over the far edge", "cross the gap" with no connector named, "steep",
  "on the cliff edge" for the scroll pavilion, "beside" for the moon gate, "small shrine" for
  the abode door, and "octagonal" for the scroll pavilion (it is hexagonal).

### 3.2 Per area

High-severity items are marked (high).

Gate
- (high) `out/higgsfield/kf_gate_fantasy.png` and `kf_gate_noflyer.png`. The model painted the
  stair to the mirror out as a cliff and waterfall, and the plaza floats in cloud. No prompt for
  this frame was saved. Save one as `film/prompt_gate.txt`, in the style of `prompt_mirror.txt`.
  Include: "Keep the white marble stairway on the left exactly where it is in Image 1: it starts
  at a paved landing behind the gate and climbs the ridge to the left with stone railings.
  Through the centre opening, the plaza continues to that landing; do not replace it with
  forest or cloud." And: "The marble plaza sits on the flat grassy summit of the mountain, lawn
  and pines around its balustrades; the cloud sea lies far below, beyond the cliff edge." Leave
  the distant red halls out of the prompt. [Blender: re-render `kf_src_gate.png` first, then
  Style frame]
- `seg01_prompt.txt` 0-3 s: the stair climbs unbroken, its lowest flights fading into thick mist.
  The stair foot stays hidden in cloud, so never ask to see it. 5-8 s: replace "dip over the far
  edge, up the next cliff's stair" with: behind the gate, a paved landing where a white marble
  stairway with stone railings begins and climbs the ridge, landing on a lantern-lined path.
  [Prompt]

Heart-Mirror Terrace
- (high) `prompt_mirror.txt`, "Mid-right" line. It told the model to turn the head of the stair
  to the forge into a pavilion on an island. Replace it with: "Mid-right, at the far edge of the
  lawn: the low white marble structure is the head of the stairway to the next peak. Keep it as
  a small paved landing with a short marble stair and low railings going over the terrace edge,
  reached by a paved path from the garden walkway. Do not put a pavilion, island or any building
  there." Drop the island pavilion from this frame's text, because it is out of shot.
  [Blender for `PATH_FORGE`, then Style frame]
- Walkway line: "a flat paved garden path at grass level with no railings". Today's frame has a
  stray railing on the lawn. Also call the arena chain "a heavy anchor chain, a tether, not a
  walkway". [Style frame]
- `seg01_prompt.txt` 6-8 s: stair tops out on a paved landing, a lantern-lined path leads to the
  pond, the zig-zag bridge crosses to the island pavilion, a second path curves to the stair of
  the mirror terrace. 10-12 s: a path leads to a landing at the right edge where a railed stair
  starts toward the forge peak, climbing its cliff on stone piers to a landing in front of a
  red three-bay archway. [Prompt]

Artifact Forge Peak
- `seg02_prompt.txt` (and `seg02_prompt_v1.txt`) 0-1 s: the plaza is entered through a red
  three-bay archway at the top of a long stair; the forge hall stands on a platform with a broad
  flight of steps; the side halls each have a short flight. 4-6 s: a small red gate in the white
  balustrade opens onto a paved bridgehead with two red posts where the chain bridge begins.
  6-9 s: the bridge lands on a stone bridgehead under a small red archway, in front of the
  arena's front steps. Add: "the artifacts float on purpose in a slow ring; no stairs, stands or
  walkways lead to them." Do not use "steep". [Prompt]
- `prompt_forge_1.txt`: it says to keep "the chain suspension bridge on the left, the grassy
  slope" exactly as is, which locks in the bridge starting from bare grass. Replace with: the
  bridge starts from a paved stone bridgehead with two red posts, just outside a small red gate
  in the white balustrade beside the side hall. Add: "The red side hall's short flight of white
  marble steps faces the cauldron; keep it." [Blender, then Style frame]

Sword-Discussion Arena
- `prompt_arena.txt`: add the route in walking order. Behind the camera the chain bridge lands
  on a bridgehead terrace, and white steps lead up to the walkway and floor. On the right,
  narrow aisle stairs climb the tiers to the pavilions. Behind the sword on the left, a short
  stair drops to a rear landing where flat stepping stones climb to the Mission Hall plaza. Add:
  "the massive iron chains hang from the rocky sides of the island below the grass edge; none
  lie on the platform or walkway." Reject any frame where the Mission cliff has no visible way
  up. [Blender, then Style frame]
- `seg03_prompt.txt` 3-5 s: replace "cross the gap to the Mission Hall cliff" with "follow a
  curving line of flat floating stepping stones that climbs gently from the island's rear
  landing to a paved landing at the front of the Mission Hall plaza, on its centre line".
  [Prompt]

Mission Hall
- `prompt_mission.txt`: "Behind the mission wall, with open plaza paving between them, the hall
  stands on a tall white marble terrace. A broad white marble stairway with a carved central
  ramp climbs from the plaza to the terrace, and a shorter flight rises to the hall's three
  glowing centre doors. A clear band of terrace and stair shows between the wall's roof and the
  hall's lower eave; the hall does not sit on the wall." Add the corridors joining each tower
  to the terrace, and the side gate. [Blender, then Style frame]
- `seg03_prompt.txt` 5-7 s: the walkway splits round the wall; the terrace stair climbs to the
  hall doors; each tower has a stair down to the plaza. 8-9 s: a stair leaves through a side
  gate past the bell tower and runs down the ridge. [Prompt]

Scripture Pavilion (library)
- (high) `prompt_library.txt` and `prompt_library_2.txt`, bottom-right bullet. "The round stone
  terrace holds a lotus pool and two small study pavilions" made the model build a raised
  cistern and a walled tower, neither with stairs. Seedance then copied them. Replace with:
  "Bottom right: the round flat-topped shape behind the pagoda is a distant natural sandstone
  rock pillar rising from the cloud sea, rough rock with a few pines on top: no walls, no pool,
  no buildings, no stairs." Drop the teal islet pavilion line (W8 removes it). [Style frame]
- `seg03_prompt.txt` 9-10 s: the way in is a long white stair straight up the cliff face to a
  landing at the plateau's front edge. The arched bridge is the way out, further left. Today the
  prompt makes the bridge sound like the way in. [Prompt]
- `seg04_prompt.txt` 0-1 s: the stair arrives on a paved landing with a stone archway; a broad
  lantern-lined walkway runs to the pagoda terrace, and a flight of steps rises to its glowing
  door. 5-7.5 s: a white stair leaves the plateau's left edge and crosses the gap on a tall
  arched bridge with a level deck, landing on stone terraces at both ends. [Prompt]

Stele Forest
- `prompt_steles.txt`: replace the area paragraph with the walking-order version. Three low
  steps onto the aisle; short steps up into each stele platform; the terrace stair; the
  pavilion's own short steps; corridors one step up, from corner pavilions to small gates in the
  back wall; through the left gate, the only stair behind the courtyard. Drop "a faint rune
  circle in the sky". [Blender, then Style frame]
- `seg04_prompt.txt` 7.5-9 s: the stair arrives on a paved landing in front of a tall three-bay
  archway; pass through its centre bay and over three low steps onto the aisle. [Prompt]
- `seg05_prompt.txt` 1-3 s: pass over the small gate in the courtyard's back wall at left;
  follow the stair that starts at that gate. [Prompt]

Jade Slip Pavilion (scroll)
- `prompt_scroll.txt`: change "on the cliff edge ... octagonal plan" to "at the back of the
  terrace ... hexagonal plan". Add the stone walkway from the terrace front to the foot of the
  pavilion's nine-step stair. [Blender, then Style frame]
- `seg05_prompt.txt` 3-4 s: the stair ends on a paved landing between two stone lanterns, in
  line with the pavilion's front stair. 7.5-10 s: a white stair leaves the terrace's right side
  through a small stone archway toward the domed plaza. [Prompt]

Grand Sect-Protecting Formation
- `prompt_formation.txt`: the eight pillars stand well inside the plaza; every beam runs between
  pillars or to the core and none leaves the plaza; a stone railing rings the plaza, with a gap
  and a small gate where the stair begins. Change "small shrine" to "a round moon-gate door cut
  into the cliff (an opening in the rock, not a pavilion)". The jade core floats on purpose. Any
  golden ring is a thin band of light around the beam, not a platform. [Blender, then Style
  frame]
- `seg06_prompt.txt` 0-1 s: the stair ends on a paved landing; three low steps lead to the red
  three-bay archway. 5-7 s: follow the stair from the small rear gate up the cliff; its top step
  meets the white path to the moon-gate door. [Prompt]

Cave Abode
- (high) `kf_abode.png` was made from the wrong moment. `film/src/src_abode.png` is frame 1449,
  4.4 s into seg07. There the camera looks west at the cliff's end, so none of the abode's
  buildings are in it. The model invented a balcony and pavilion on stilts with no stair.
  Fix: in `sect/camera.py` `ROUTE['abode']`, move `hero=True` from `H('balcony')` to
  `H('waterfall', 13.0, hero=True, hero_at=0.5)`. Or simply re-render frame 1367 (1.0 s in).
  That moment shows the path, balcony stair, deck, moon gate, tea pavilion, waterfall and pool.
  [Blender: one frame]
- (high) `prompt_abode.txt`: the model also turned the lawn into a gorge, and the summit stair
  rises out of cloud with no ends. Replace the "carve the moon gate" paragraph with a
  keep-exactly description in walking order: the white path, the marble stair up to the
  red-railed balcony, the moon gate opening onto the balcony at deck level, the tea pavilion on
  the same deck to the right of the gate, the waterfall into a koi pool on a flat green lawn.
  The summit stair starts from a paved landing on the lawn's left rim. Remove "misty" from the
  pool. [Style frame, after the new base image]
- `seg07_prompt.txt` (and v1, v2) 1-3 s: "glide low along the white paved path to the marble
  stair that climbs to a red-railed balcony on red stilts; the round moon gate with its gold
  plaque opens onto that balcony at deck level, the small teal tea pavilion beside it on the
  same deck." 5.5-8 s: a paved side path leads to a landing with two stone lanterns at the
  plateau's west rim; from there the stair climbs on stone piers, past a rest pavilion, to the
  crescent-moon arch. [Prompt]

Moon-Gazing Summit
- `prompt_summit.txt`: the model turned the 1.2 m tiers into 3 to 4 m drum walls with one stair
  at the far edge. Replace the pavilion bullet with: "the round two-tier pavilion stands on two
  low stacked round white marble tiers, each about waist height, not tall walls; a broad flight
  of white marble steps with balustrades climbs each tier straight to the pavilion's open
  front." Add: "the weathered stone block at lower left is a distant rock pillar, separate from
  the terrace, with no stairs or buildings on it." Make the islets uninhabited. The blocking is
  already right here. [Style frame]
- `seg08_prompt.txt` (and v1, v2) 0-1 s: the stair's top flight ends on a flat paved landing at
  the rim, on the centre line of the crescent arch. 1-2.5 s: through the arch onto the terrace.
  2.5-4 s: the pavilion on two low tiers, steps centred on its front. Drop "beside a white
  marble stair". [Prompt]

---

## 4. Medium and low fixes, by area

Do these in the same pass as sections 1 and 2, so you only render once.

Mountain Gate
- Stair foot: leave it hidden in cloud. If a shot ever shows it, build an arrival plaza at the
  foot: `foot_plaza` slab at x ±18, y -160 to -137.5, at z -51.84; a three-bay paifang
  (width 16, height 12) at (0, -141); balustrades on three sides; `_ridge` y_end to about -168.
- Landings have no side rails: pass `bal_extend=LANDING_L` for flights k ≥ 1.
- The grand stair's 0.22 m treads give a 39° slope. Keep it as a steep pilgrim stair.

Heart-Mirror Terrace
- The east dais lantern at (6.9, 12.8) blocks a third of the only path to the mirror. Move the
  dais lanterns to shrine-local (±4.6, -DAIS_D/2 - 0.6). Move the path lantern pair at y -30 to
  y -32.
- The dais stair faces the pond with no flat space in front. Add a 12 x 2 m shore walk at
  shrine-local x -6 to 6, y -10.5 to -8.5, top 0.12. End `PATH_EAST` into it.
- The path meets the bridge deck with a 0.42 m ledge. Add `bridge_steps` (three 0.14 m risers)
  at (-5, -25, 0.12) and end `PATH_MAIN` at (-5, -26).
- The bridge runs straight into the island pavilion's bottom step. Set `ISLE_W` to 13.5, move
  the bridge's last point to (-9, -6.75), and rail the island with a 3 m gap at the bridge.
- Rim rails at radius 52 on the south and east rim, with 6 m gaps at both stairs.

Artifact Forge Peak
- The cauldron dais has no back stair, so the axis is blocked by a 1.2 m drop. Add
  `A.stairs(_n('dais_stairs_back'), coll, 4.0, DAIS_H, ramp=False, balustrade=False, parent=root, location=(0.0, DAIS_C[1] + 17.0*0.5*math.cos(math.pi/8), 0.0), rotation_z=math.pi)`.
- The chimneys don't connect to the furnaces. Add 1.4 x 1.4 m stone flues from (±7.5, 27.2) to
  the chimney bases at (±10, 35.6).

Sword-Discussion Arena
- The tier hangs up to 2 m past the island rim. Set `TIER_STEPS = 3`. Use
  `backs = [min(TIER_BACK, rim(a) - 0.5) for a in angles]`, and the same back in `r_pav`.
  Shrink the judges' pavilion radius from 3.3 to 2.8. Do this before the aisle stairs, which
  then become 3.4 m tall (20 steps).
- Optional: a second walkway stair at 175.6° (west), so the grass ring forms a loop.
- The front steps leave a 0.6 m slot below the walkway. Move them to (0, -33.9, Z_BAND - 1.15).
- The floor ring is one 0.35 m riser and the taiji dais one 0.3 m riser. Split each into two.
- A low balustrade along the void side of both landings, 20 m each way.
- Keep orbiting islets out of the stone corridor (x -15 to 15, y 40 to 125, z -5 to 25).

Mission Hall
- The centre walk runs into the wall's 1 m base, which has no steps. Split the axis box at the
  wall. Add paved aprons in front of and behind the wall (x ±17) and 4 m side strips at x ±16.
  Add `A.stairs(width=22, height=1.0, ramp=False, balustrade=False)` on the wall's front.
- The side corridors touch no building. Make them raised galleries: tower `base_h` 3.4 to 3.0
  (same as the terrace); corridor points `[(sx*30, 0), (sx*33.5, 0), (sx*33.5, 22), (sx*23.1, 22)]`
  with `platform_h=3.0`; open the tower balustrade at y -2 to 2 (needs the `tower` gap option)
  and `terrace_rail` at y 20.4 to 23.6. Fallback: delete both corridors.

Scripture Pavilion (library)
- Rail the rim for about 8 m on each side of both stair heads, height 1.0.

Stele Forest
- The pavilion's steps are buried in its platform. Fixed by the `arch.pavilion` change (2b).
- The side corridors sit 0.45 m up and lead from nowhere to a wall. Set `platform_h=0.17`.
  Extend each along the back wall to end beside a rear gate:
  `[(s*12, -35), (s*27, -35), (s*27, 33), (s*18, 33)]`. Close the front ends with a small
  square corner pavilion (`sides=4, radius=2.4, height=3.4, platform_h=0.17, seats=False`) at
  (±12, -35, 0).
- The stele fields are 0.44 m ledges. Add three-step flights at y -15 and y 1 on both sides of
  the aisle, at x ±7.5. The aisle stays 13 m clear.

Jade Slip Pavilion (scroll)
- The stone desk blocks the axis. Set `DESK = (4.0, 14.0)`.
- Draw the route on the ground: a grey stone strip,
  `A.platform(_n('walk'), coll, 4.0, 39.0, height=0.03, style='plain', mat='stone_grey', top_mat='stone_grey', sink=0.03, parent=root, location=(12.0, 0.5, 0.0))`.
- The upper balcony has no door. Fixed by the `arch.pagoda` change (2b).

Grand Sect-Protecting Formation
- The central altar has three 0.5 m tiers and no stair. Add four flights, one per compass
  point, like the Circular Mound Altar at the Temple of Heaven: `A.stairs(name, coll, 3.0, 1.5,
  ramp=False, balustrade=False, parent=root)` at (0, -8.4, 0) rot 0, (0, 8.4, 0) rot pi,
  (8.4, 0, 0) rot +pi/2, (-8.4, 0, 0) rot -pi/2. That gives 9 risers of 0.167 m each. The
  minimum is the front and back flights.
- The archway pokes about 3 m through the dome, and the dome's base hovers 0.4 m above the
  grass. Use `P.shield_dome(radius=49.9, height=50.0, ...)` and check the chase camera.
  Fallback: keep the dome and set the paifang height to 13.
- A 4 m white `marble_paving` strip on x 0 at z 0.004, from y -49.5 to -11.4 and from 11.4 to
  49.5. It draws the route across the dark floor.
- The railing's front gap leaves a 1.5 m slot each side of the archway. Set
  `gap = math.radians(11.9)`.
- Optional: delete the `light_pillar` `.halo` rings, or keep only the highest. The model drew
  one as a portal beside the stair.

Cave Abode
- The balcony stair is one 36-step flight. Split it into two flights of 18 with a 2 m landing
  at z 3.0.
- The koi pool has no path. Add 8 flagstones from (-6.3, 2) to a 3 x 2 m stone ledge at
  (6, 12). Move the rock at (-4, 4) and the shrub at (-4.5, 0) off that line.
- The corner stilt at (8.5, 18.4) stands in the pool. Move it to x 7.0, with its brace.
- The deck's side rails stop 0.6 m short of the rock. End both at `YG - 0.05`.
- A stone rim rail at radius 53, from 200° to 340°, with 6 m gaps at both landings.

Moon-Gazing Summit
- Narrow the front balustrade gap to the stair's width: `gap_front = math.asin(3.0 / bal_r)`,
  a 6 m opening. Needed once W7 makes the balustrade the cliff rail.
- Optional: balustrade wings from each crescent-arch base to the rim
  (`[(sx*13.0, ARCH_Y, 0), (sx*21.6, ARCH_Y, 0)]` for sx = ±1), so the path goes through the
  arch, not round it.
- The 8.7 m gap at the pine is only partly filled by boulders. Set
  `gap_pine = math.radians(3.0)`.

---

## 5. What to re-run, and what it costs

Blender re-render (cloud GPU). Needed for everything in sections 1, 2 and 4.
- 11 style-frame base images: `out/higgsfield/kf_src_gate.png` and the 10
  `out/higgsfield/film/src/src_*.png`. Render `src_abode.png` from the new camera moment.
- 16 segment stills: `out/stills/seg01_start.png` to `seg08_end.png`. The video model copies
  the start frame, so these matter.
- The hero stills (`out/stills/hero_*.png`) only if you still use them.

New style frames (OpenAI images). Regenerate all 11 `kf_*.png` once, after the re-render, with
the section 3 prompts. Only `kf_summit` and `kf_library` could be fixed by prompt alone today.
But their areas change in the re-render too, so doing them now means paying for them twice.

Prompt text. Every edit in section 3. Free to write now.

Video (Higgsfield credits). Regenerate seg01 to seg08 after the new style frames.

## 6. Choices this plan made

Where audits proposed different fixes for the same break, this plan picks one:
- Stair profile: one steady climb raised over bumps (W2). The area audits proposed five
  variants: a floor pass, an outward pass, a straight line, grade 0.22, and the line minus 5 m.
  W2 covers all of their cases.
- The stair from the gate starts on the gate's axis at (0, 36), not at a side landing at
  (-19, 38).
- Arena to Mission keeps the stepping stones, rebuilt. A stepped chain bridge is the fallback.
- The forge bridge lands at arena level -1.5 with a 2 m sag, not at -10 with an extra stair
  inside the arena.
- The gate stair's foot stays hidden in cloud, and its 0.22 m treads stay.

## 7. Limits

- Nobody ran Blender or `walkcheck.py`. The numbers come from reading the code and re-running
  `world.py`'s terrain and stair maths in plain Python. The terrain mesh uses a 5 m grid, so
  cliff edges may sit 1 to 2 m from these numbers.
- The audits' scratch scripts are in the session scratchpad (`forgeaudit/`, `summit/`,
  `steles_links.py`, `mirror_stairs.py`).

## What's left for you

- Approve the cloud GPU re-render once sections 1, 2 and 4 are built and pass walkcheck.
- Approve the OpenAI style-frame and Higgsfield video spend after the renders are back.
