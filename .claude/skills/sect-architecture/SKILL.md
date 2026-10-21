---
name: sect-architecture
description: Use when designing or reviewing xianxia sect or Chinese temple architecture (Blender blocking, AI style frames, Seedance video prompts) so every building is reachable and every stair, bridge and walkway connects at both ends.
---

# Sect architecture: every building reachable, every path connected

The one rule: **a visitor who arrives at the mountain gate can walk to every front door, and
every stair, bridge and walkway starts and ends on something solid.** Everything below is a
way to design for that rule or to check it.

Design order: lay out the walking route first, then place buildings along it, with each front
door facing the route. Placing buildings first and adding paths later is how buildings end up
with no way in. (This is how the scene team of the game Moonlight Blade works.)

More detail: `references/planning.md` (long rules with sources, a connection plan per area, all phrases, all sources).

## 1. Core principles

1. **One axis per complex.** The main gate's centre opening, the stairs and the centre door of
   every main hall sit on one straight line. Test: a line through the gate's centre passes
   through the centre bay of each hall on the axis.
2. **Gates in a fixed order.** Archway (paifang) or spirit-screen wall (the path goes round it),
   then a bridge over a pond on the axis, then a three-opening mountain gate, then a courtyard
   with a bell tower and a drum tower, then the guardian hall, main hall and rear halls. The bell
   tower is on the main hall's left as it looks out (local +X here), so on a visitor's right.
   Every hall on the axis has a back door or side passage doors into the next courtyard. A hall
   with no rear opening cuts off everything behind it.
3. **Rank grows with depth and height.** The main hall is the biggest: highest platform, double
   eaves, most bays (odd: 3, 5, 7, 9). Side halls come in mirrored pairs facing each other
   across the courtyard, doors opening onto it. Dorms and kitchens sit beside or behind the axis.
4. **Every building stands on a platform with a stair centred on its front door**, about as
   wide as the centre bay. Big halls add a moon terrace (yuetai) in front: a platform-height
   forecourt with three flights at its front and one at each side. A tall base never lacks a
   stair.
5. **A paved walkway runs down the middle of each courtyard**, from the gate to the foot of the
   next hall's stair. It draws the route on the ground.
6. **Covered corridors (lang) join halls.** Each corridor touches a building at both ends (side,
   corner or porch) at that building's floor level. Between halls at different heights it steps
   down in stages or climbs the slope. It never stops at a terrace edge.
7. **On a mountain, the stairway is the axis.** Height replaces depth: each courtyard becomes a
   level terrace held by a retaining wall, joined to the next by a stair on the axis. Wudang's
   Purple Heaven Palace has five rising terraces with one hall each.
8. **Stairs come in stages.** A landing at every break, and a gate, archway or pavilion at each
   stage boundary. Mount Tai has about 11 gates, 14 archways and 14 pavilions on a 9 to 10 km
   climb, so a marker every few hundred metres. Put the top gate in the saddle between two peaks
   so the last flight aims straight at it.
9. **Branch, don't scatter.** A building off the main route sits on flat ground beside it,
   reached by a short side stair that ends at its gate.
10. **Bridges deliver you to a gate.** A bridge lines up with a gate opening and lands on a
    terrace at both ends. A cliff plank road (zhandao) is beams in holes cut in the rock, planks
    on top, a chain or rail on the open side, solid ground or a building at each end.
11. **Pick the connector by the size of the gap.** Short: stone arch bridge or roofed corridor
    bridge (langqiao, can carry a small shrine). Up to about 100 m: iron-chain bridge with a
    plank deck and chain handrails, anchored in bridgehead pavilions (like Luding Bridge). Sheer
    cliff: plank road or rock-cut stair with chains (like Huashan). Very long: a landing plaza
    or teleport array at each end.
12. **Sword flight ends on a landing plaza.** A big open plaza at the peak's edge, on the main
    path. Cultivators land there and walk the rest. Never on roofs or small courtyards.
    Teleport arrays are round stone or jade platforms ringed by pillars, on a plaza, with a
    stair leading off.
13. **A floating island needs three things:** a believable rocky underside, something holding
    it (chains to a neighbour, a formation array), and a walkable connector that lands on a
    terrace in front of a gate.
14. **Paths end at something.** A door, gate, stair, another path, or a pavilion at a
    viewpoint. A path that stops at a cliff edge stops at a pavilion or a railed viewing
    terrace.
15. **Cliff buildings** sit under a rock overhang on beams socketed into the rock, with a
    one-person walkway with a railing along the beam ends (like the Hanging Temple). Cave abodes:
    a door in the cliff, a small ledge terrace with a rail, a rock-cut stair or plank walk to it.
16. **Facing.** Halls face the open, downhill side with the peak behind. Doors and stairs point
    at the approach, never into rock.
17. **Landmarks.** One global landmark (the moon and the summit pavilion) visible most of the
    flight. One hero building per area, visible from the area before. The main route and the
    door it ends at are the brightest, warmest part of the frame.

## 2. Circulation checklist

Run it on every area, every style frame and every video keyframe. Trace the route with a finger
from the arrival point.

- [ ] **Arrival.** Where does a visitor arrive: stair top, bridgehead, landing plaza or teleport
      array? It is a level paved surface.
- [ ] **Every door.** From the arrival you can walk to every door: arrival, forecourt, stair,
      door. No jumping, no flying.
- [ ] **Door landings.** Each door has a flat landing in front at threshold height, plus a stair
      if the floor is more than about 0.3 m above the forecourt. No door opens onto a drop or a
      wall.
- [ ] **Stairs.** Each stair meets a level landing at top and bottom. Long flights (about 20
      steps or more) have landings in between.
- [ ] **Bridges.** Each bridge lands on a platform at both ends, in front of a gate or archway.
      Not on a roof, a blank wall, open air, or past a terrace edge.
- [ ] **No dead ends.** Every walkway ends at a door, gate, stair, another path or a viewpoint
      pavilion. Delete the rest.
- [ ] **Corridors** touch a building at both ends at the same floor level.
- [ ] **Nothing floats by accident.** Every building has a base and a connection. A floating
      island is fine only with a bridge, chain walkway or teleport array landing on it.
- [ ] **Railings** on every drop: cliff stairs, bridge edges, terrace edges, plank roads.
- [ ] **On the axis.** Connectors arrive on the area's front axis, pointing at the main door,
      not 15 m off to the side.
- [ ] **Human scale.** Risers 0.15 to 0.18 m, treads 0.26 m or more, paths 1.5 m or wider,
      doors 2.3 m or taller (main halls 3.5 to 4.5 m). A 1.75 m figure looks right on the stair.
- [ ] **Next goal visible.** The next area's hero building shows ahead along the route.

## 3. Blender blocking rules (this project)

Conventions from `blender/xianxia-sect/spec.md`: metres, Z up, +Y is the direction of travel.
Each area has a local frame: origin at the plateau centre, z = 0 is the walkable top, the front
faces −Y, and everything fits inside the area's `footprint` radius. `world.py` puts a flat
terrace at local z = −0.4 under each area, radius footprint + `TERRACE_PAD` (9 m), plus up to
6 m of bulges. Library builders in `sect/lib/arch.py` face −Y.

1. **Block the route first, as grey shapes:** arrival landing, forecourt, stairs and door
   landings. The video model copies the blocking. A prompt will not reliably add a missing stair.
2. **Use the builders that already include access.** `arch.hall(..., stairs=True)` gives a
   platform and a front stair. `arch.platform` plus `arch.stairs` for anything else.
   `arch.stairs` keeps risers at 0.17 m or less, and its top edge (local y = 0) meets the
   platform. Put that edge on the platform edge, centred on the door bay.
3. **Every area gets an arrival landing** where its incoming connector lands: on the −Y side,
   near local x = 0, with paving from there to the main stair.
4. **Connectors (`world.py` `build_connectors`) run from one area's declared exit to the next
   area's declared entrance.** Each area module puts `depart` and `arrival` in its `AREA` dict:
   (x, y, z, heading) in the area's frame, heading in radians from local +x (+y = pi/2). The
   point sits on the area's own paving at the foot of its steps; `world.py` lands the stair
   flush there, straight on for 15 m. The 2026-10-10 fix (audit W1-W6, all measured with
   walkcheck) gave 0.17 m risers, flights of 18 with landings, an archway on each foot landing,
   piers where a stair stands high, a level arched bridge, a stepped chain bridge, and
   stepping stones with 1.07 m hops. A comfortable hop is at most 1.2 m up and 2.4 m across.
   Start a stair's parapets where its first flight starts, so the foot landing stays one open
   landing. Run parapets through it and they cut it into a centre lane and two dead strips.
5. **Tag doors.** Proposed (not done): in `arch._facade`, add an Empty `door.<name>` at each
   door bay's threshold (bay centre, floor height, facing −Y). Until then the check finds door
   leaves by their prototype collection name (`arch.p.lattice.*.door.*`).
6. **Name connectors so the check can find them:** `world.link.*`, or a name part `stairs`,
   `steps`, `bridge`, `walk`, `walkway`, `lang`, `corridor`, `plank` or `stone`, followed only
   by parts like `steps`, `floor`, `deck` or a number. `x.stairs.bal.panels` (a balustrade),
   `x.lang.post` and `x.banner.stones` (a banner's base) are not connectors. Archways and
   pavilions standing on a link (`world.link.*.foot_gate`, `.rest_pavilion`) are not part of
   it. Mark viewpoints where a path may end with Empties named `vista.*` or `landmark.*`.
7. **Put a 1.75 m figure** at every door and on each connector in the hero frame.
8. **Snap path ends and platform edges to a 1 m grid** so walkways meet landings exactly.

### Automated walkability check

Scripts: `scripts/walkcheck.py` (one run) and `scripts/walk_sect.py` (the whole W9 battery for
this project). Headless only. For this project, run Blender only on the cloud box. The wrapper
uploads only `sect/`, `docs/`, `spec.md` and small files under `out/tmp/`, so copy both
scripts into `out/tmp/<you>/` first:

```
python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background   E:/Github/PortfolioV5/blender/xianxia-sect/out/sect.blend   --python E:/Github/PortfolioV5/blender/xianxia-sect/out/tmp/<you>/walk_sect.py   -- --json E:/Github/PortfolioV5/blender/xianxia-sect/out/tmp/<you>/w9.json
```

`walk_sect.py` scans the scene once (about 16 s), then runs every check at max rise 0.7 and
0.45 (about 15 s more). It checks three things:
- **Global:** from the gate plaza, every door and every area's arrival and depart point.
- **Each area:** from its `AREA['arrival']`, every door, its depart point, its own connectors
  and orphan patches.
- **Each link:** from the depart point, the arrival is reached, the link joins both areas'
  floors, and every standable piece of the link is reached.

It prints `W9 ...` lines. `walkcheck.py` alone takes `--start X,Y,Z`, `--bounds X0,X1,Y0,Y1`,
`--max-rise`, `--no-hop` and `--json`.

How it works:

1. **Find floors.** It keeps triangles that face within 40° of straight up and use a path
   material, read from the `sect_material` custom property. Built materials count everywhere:
   marble*, any `*paving*` (area variants too), light/dark/soot wood, grey/dark stone, jade.
   Natural ones (rock, moss, grass, soil, `nature_soil_moss`) count except on world terrain and
   scenery islets. Roofs never count. Faces must point up. An inside-out mesh has no floor, so
   fix its winding (2026-10-10: `arch._wall_box` and some stepping stones were inside out).
2. **Sample.** Every 0.5 m it casts rays straight down and keeps every floor layer. It drops a
   sample if anything solid sits within 2 m above it. Glows, runes, cloth, foliage, water
   sheets and volumes are not solid. Door leaves are not solid either, because doors open.
3. **Link.** Neighbouring samples connect when their height differs by no more than the max
   rise and nothing solid stands between them. Two level rays, 0.35 m and 0.9 m above the
   higher sample, test this, so walls, balustrades, parapets and benches block. It also links
   across one empty sample (1 m gaps between planks). Stepping stones also link by hops of at
   most 1.2 m up and 2.4 m across.
4. **Search** from `--start` (default: gate plaza, 0, 0, 40).
5. **Report**:
   - doors with no landing in front, and doors not reachable;
   - connectors in pieces, with the worst hop. A piece must be standable: a sliver behind a
     bench rail is not counted. Stairs with a carved centre ramp are two pieces by design, so
     what matters is that every piece is reached;
   - connector ends that touch no other floor. This is often harmless where a landing borders
     terrace grass, which is never floor;
   - orphan floors: unreachable patches of 4 m² or more, wide enough to stand on. `walk_sect`
     sorts them into three kinds. **Open** ones have sky above; these are the real ones. A
     **covered** one is under a roof, or was sampled inside a tall solid such as a terrace
     body. A **rock** one is cliff or ridge rock. An open patch with a door is a building with
     no way in. A door at least 2 m above a reachable door of the same building is listed as
     upper storey, reached by an inner stair.

Doors are found from lattice door leaves (prototype collections `arch.p.lattice.*.door.*`),
clustered per building. Open pavilions and gates have no leaves. For those, check that their
platform is not an orphan.

Status (2026-10-10, full sect): every link passes at 0.7 and 0.45. All 21 arrival and depart
points and every ground-floor door are reachable from the gate plaza. The only open orphans
left are decoration: lantern pads beside the grand stair, plinth tops, the ends of the
arena's top seat row, and the library pagoda's and scroll pavilion's upper balconies.
`scripts/test_walkcheck.py` covers the graph part (run with `python -I`).

## 4. Prompt rules (OpenAI style frames, Seedance clips)

1. **Fix connections in the blocking first.** This project's style-frame prompts say "Image 1
   is the ONLY source of truth for geometry", so a missing stair stays missing. If a frame needs
   a connector the blocking lacks, say exactly what to add and nothing more: "Add only a white
   marble stair from the plaza to the hall's front door. Do not move or add any building."
2. **Name the path to every building, with both ends:** "a white marble stairway climbs from the
   arrival plaza in the foreground to the moon terrace in front of the Mission Hall's centre
   door".
3. **Describe in walking order:** arrival, gate, courtyard, stair, hall door. The model reads it
   like a route.
4. **Say where every bridge lands:** "the chain bridge lands on a stone bridgehead terrace in
   front of a red archway on the arena rim".
5. **Floating things:** say what holds them and how you reach them, or say they are meant to
   float and nobody walks there (the jade scroll, the formation core).
6. **Seedance:** mention the path in the same time range as its building: "3-5 s: the stone
   stair rises from the cliff-edge landing to the hall's platform".
7. **Don't name buildings that have no path.** Anything named gets drawn, and the model will
   draw it floating.
8. **End with one short negative line** (below), and check each output against section 2.
   Reject frames where a building has no way in.

Phrases to reuse:

- every building visibly reached by a stair, bridge or walkway; paths continuous from the
  foreground to the summit
- each hall stands on a raised white marble platform with a flight of steps centred on its
  front door
- a broad moon terrace in front of the main hall, with three flights of steps at its front
- a raised paved walkway down the middle of the courtyard from the gate to the hall steps
- red-pillared covered corridors connect the side halls to the main hall
- the stairway passes through stone archways at each landing, with a rest pavilion at every turn
- a wide open landing plaza at the cliff edge where cultivators arrive on flying swords and
  continue on foot
- an iron-chain bridge with a plank deck and chain handrails, anchored in small stone
  bridgehead pavilions at both ends
- a roofed timber corridor bridge spanning the gorge, each end landing on a stone terrace in
  front of a gateway
- a narrow plank walkway pinned to the cliff with iron chains, with a railing, leading to the
  next ledge
- each floating peak has a landing terrace at its edge where the bridge arrives in front of a
  gate
- stone railings along every cliff-edge path and stair; landings at the top and bottom of every
  flight
- 依山而建，层层台地，石阶相连 (built into the mountain, terrace above terrace, linked by stone
  stairs)
- Negative: no isolated buildings without a path, no stairs ending in mid-air, no bridges ending
  at blank walls or roofs, no doors without steps, no walkways stopping at a cliff edge, no
  impossible Escher-like geometry.

## 5. Sources

Main ones below. The full list (about 90 links) is in `references/planning.md`.

- Axis and layout: https://en.wikipedia.org/wiki/Chinese_architecture , https://en.wikipedia.org/wiki/Forbidden_City
- Temple order: https://www.travelchinaguide.com/intro/architecture/styles/chinese-buddhist-temples.htm
- Platforms, moon terraces, stairs: https://www.antiquekeeper.ca/?p=108961 , http://szj-tou.com/cn/show/1825
- Wudang terraces: https://wudang.org/wudang-mountain/temples-and-sites/layout-and-architecture , https://whc.unesco.org/document/154060
- Mount Tai gates and stair stages: http://www.intotaishan.com/html/2006/1008/201.html
- Hanging Temple: https://zh.wikipedia.org/zh-hans/%E6%82%AC%E7%A9%BA%E5%AF%BA ; plank roads: https://en.wikipedia.org/wiki/Gallery_road
- Chain bridges: https://en.wikipedia.org/wiki/Luding_Bridge ; covered bridges: https://www.intrans.iastate.edu/wp-content/uploads/sites/12/2019/03/Knapp_ChinasForgottenBridges.pdf
- Moonlight Blade scene design (route first, landmarks, rhythm): https://game.xiaomi.com/viewpoint/1392697565_1637716502230_11
- Level-design skill (reachability, dead ends, landmarks, metrics): https://github.com/omer-metin/skills-for-antigravity/tree/HEAD/skills/level-design
- Blender environment skills (grid, scale figure): https://github.com/arjun988/blender-skills
