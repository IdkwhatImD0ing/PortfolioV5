# Live light at the stops

Status on 2026-11-10: on the branch, High tier only, behind a switch, at all eleven stops. Part
of the pull request opened on 2026-11-14. It began as a test at the gate and was then rolled out: see
"Every stop" below.

## Why

The owner, 2026-11-10, after round 57: "It still doesnt look as good as Saltline unfortunately the
photo realism, etc". Then, to a proposal to rebuild one stop with live light: "Yes, build the gate".

Saltline, the game he compares against, lights every surface while it draws: the sun's light, soft
shadows and shine are worked out per pixel, so edges are sharp at any distance and highlights move
as the camera does. This page draws a bake: Blender works the light out once and saves the lit
picture into textures at 3 to 20 texels a metre. Shadows are as soft as the texels are big, and
nothing shines.

This lights the page's own surfaces live. It began as a test at one stop, the gate.

## How it works

The first plan was to export the gate without a bake and paint its materials in the page. That
would have thrown away what Blender's materials hold (banner emblems, beam patterns, rock colour).
The bake now writes what live light needs instead.

1. **Three more maps from the bake.** `bake_web.py -- bakefull --live` bakes, per atlas and in the
   atlas's own layout:
   - the surface colour with no light on it (the bake already made this for its denoiser),
   - the surface direction in world space (also already made),
   - the light with the sun and the key lamp switched off: the sky's light and its bounces.

   It writes them to `out/web/full/live/<chunk>/` with `index.json`, which also gives the two lamps'
   directions, colours and strengths and the bake's exposure and saturation.
2. **The page's files.** `tools/sect_live.py --chunk gate` (plain Python, on the PC) turns them
   into WebP in `client/public/sect/full/live/gate/`: 7 MB for the gate's two atlases. The maps
   only fit the chunk file of the same bake run, so the gate was packed again from that run.
   The sky-light map is written with the surface colour divided out (light alone), at half size;
   the shader multiplies it by the full-size colour map. Stored with the colour in it, everything
   painted on a surface went soft wherever the surface was in shade.
3. **The light.** A surface with live maps is drawn as

       sky light + bounced light + colour / pi x (sun x facing x its shadow + key x facing x its shadow) + shine

   then through the bake's own grade and Blender's own view transform (below), so it comes out as
   the same kind of colour a baked texel is. The rest of the page's pipeline (detail layers, grade,
   haze) runs on it unchanged.

   The bounced light is the two lamps' light after its first bounce: a terrace warmed by the
   sunlit wall beside it. The lit bake has it and the bake with the lamps off does not, so
   `sect/live_bounce.py` (on the box, from the bake's raw files, under a minute for nine stops)
   works it out: where a texel gets no direct light all of "lit minus lamps-off" is bounce, where
   it is in full light bounce is what is left over the direct light, and in a shadow's soft edge
   it is filled in from the texels around. `sect_live.py` adds it to the sky-light map. Without
   it shade came out 16 to 37 percent short of the bake's and cooler.

   Where the sky-light map is at the top of its range (beside a lantern, in a furnace's glow) the
   texel keeps the bake: that light is brighter than the map holds.
4. **Shadows.** Two depth maps, one from the key lamp (27 degrees up) and one from the sun (7
   degrees up), each 4096 px over 160 m round the gate terrace, drawn once. What casts into them:
   the gate's own meshes, its tree cards through their picture's alpha, and behind them the far
   peaks, the other areas' stand-ins and the far forests, because a 7 degree sun is shaded by
   things two kilometres off. The lookup widens a shadow's edge with the distance to what casts
   it, up to 12 texels (about 45 cm). Each read of the map is the GPU's own filtered 2x2 depth
   test and the reads sit on a fixed disc, so a soft edge is smooth; the distance to the caster
   comes from a second, coarse copy of the map.
   Pieces that move (the forge's artifacts on their hoop, the cranes, the library's scrolls) do
   not cast: the maps are drawn once, and their shadow would stay behind while they travel.
   Cloth that waves (banners, flags) reads the maps from a point lifted 45 cm toward the lamp, so
   it does not shade itself against where it hung when the maps were drawn. Cloth lit from behind
   needs nothing more: the bake's bounced light holds the light that comes through it.

   **The page's shadows only tighten the bake's.** `sect/live_bounce.py` also writes how much of
   the two lamps' light the bake let through at each texel (0 shade to 1 full light), and
   `sect_live.py` puts it in the sky-light map's alpha. The page's own shadow maps are sharper
   than that at an edge, and worse everywhere else:

   - They have gaps the bake has not. Faces the flight never sees are not in the page's meshes,
     and a roof seen edge-on from a lamp is a sliver in its map. Light came through in dashes.
   - Far from what casts it a shadow should be soft: a tree 30 m off throws one three metres
     soft at the edge, and a hard one on the abode's cliff looked false.
   - The sun stands 7 degrees up, so on level ground one texel of its map is 40 cm long.
   - A stair tread under its own nosing is a texel or two.

   So the rules are (`LIVE_LOOK.bakedShadow`):

   - The page's result can take light away from the bake's, never add to it.
   - And only where the bake's shadow is soft, which is near an edge of it. `sect_live.py` works
     that out from the bake's shadow (it changes within 3 texels) and puts it in the direction
     map's alpha. Where the bake's shadow does not change, the bake's light stands.
   - A lamp is left to the bake when its caster is over 8 m off (page alone within 1.5 m), when
     nothing near casts in the page's map, when the caster is right at the surface (within half
     a metre), and when the lamp only grazes the face (under 14 degrees).

   The bake's number is one for both lamps, so it is used on their summed light: what each lamp
   keeps of its own shadow comes first, and the part left to the bake is what the bake's total
   has over that. Used on each lamp alone it cut the sun under an eave where only the key lamp
   is shaded. The shine takes the same share as the diffuse light.

   **The bake's detail.** The maps rebuild the bake's light at half its size, so anything finer
   came out soft or blocky (cracks in the abode's cliff, the carved slabs in the stairs), and
   the rebuilt colour drifted (the cliff a quarter more orange). The shader now also works out
   the bake's own light from the same maps (the lamps at the bake's strength, on the flat face,
   through the bake's shadow), and multiplies the live colour by "baked texel over rebuilt
   bake", held between 0.4 and 2.5 (`LIVE_LOOK.detail`). Where live light changes nothing, the
   picture is then the bake's own, texel for texel. At the edge of a shadow the page keeps,
   only the hue is taken, since the rebuilt shadow is softer there than the bake's.
5. **Blender's colours.** The bake goes through Blender's "AgX" view with the "Punchy" look. The
   page's own AgX code is three.js's, a different curve: greys agreed, lacquer red came out a third
   too bright with no green or blue left in it. `tools/sect_view_lut.py` reads Blender's colour
   config with the OpenColorIO library (no Blender is run) and writes the whole transform as a 48
   cubed table, `live/view_agx_punchy.bin`, which the shader reads. Against the exact transform the
   table is off by 0.4 of an 8 bit step on average. The old curve was off by 7, and by up to 67.
6. **What a bake cannot do.** With the light live, four things were added on top, all kept small
   (see "What the first review found"):
   - **Bumps.** Two layers of noise tilt each surface's direction by class (rock the most, ground
     and paving hardly at all). Under a 7 degree sun a small tilt changes the light a lot.
   - **Roof tiles.** A roof's courses are half-rounds: the normal rolls across each one, so the
     low light catches every row.
   - **Gloss.** Each class has its own shine. In painted wood the strongly coloured parts get a
     soft sheen. A matte surface does not turn into a mirror at a low angle, and grass does not
     shine at all.
   - **The sky in smooth surfaces.** Paving and paint mirror a little sky at a low angle, less
     where the sky-light map says the point sees little sky. Glaze keeps its own reflection and
     uses the map's surface direction. Metal keeps the flat face's: the half-size map is wrong
     on thin pieces (a crescent, a blade), and in a mirror that shows as blotches.

   Two limits keep these honest. Bumps and the tiles' roll can raise a lamp's light to at most
   2.5 times what the flat face gets (`bumpCap`): tile crowns lit up on a roof face that barely
   saw the lamp. And the shine is held to a quarter of the surface's own light (`shineCap`): a
   navy name board went lavender and a teal ridge cream.
7. **Blend.** Past 45 m from the gate terrace the live colour fades into the baked texel and is
   gone by 72 m, so the areas that are still baked join without a seam.

## Does the sum match the bake?

Two checks, both on purpose before any tuning by eye.

**The numbers.** `sect/live_calib.py` (on the box, after the bake) reads the four raw bakes per atlas
and measures the lamps' share of the lit bake against colour x (sun + key). If the page's formula is
right the share is 1 / pi = 0.318 on every texel in full light.

| Atlas | Share at full light | Sun alone | Key alone | Sky's part of all light |
|---|---|---|---|---|
| gate_A0 | 0.325 | 0.36 | 0.30 | 35% |
| gate_A1 | 0.325 | 0.34 | 0.29 | 31% |

So the formula holds to about 2%, and the lamp directions and axes are right. The sun reads a
little high because its light bounced off other surfaces is in the bake and not in the formula;
the bake's bounced light (item 3) holds it. About a third of the gate's light is sky light, which
stays baked. All eleven stops measured 0.325.

**The picture.** The hold view, baked against live with the bumps, gloss and sheen off:

| Where | Baked (r, g, b) | Live |
|---|---|---|
| Column, lit side | 146, 26, 12 | 144, 25, 11 |
| Paving in sun | 220, 194, 177 | 226, 201, 182 |
| Paving in shade | 194, 173, 162 | 196, 176, 165 |
| Roof | 33, 51, 65 | 28, 51, 66 |

The whole frame differs by 5 steps of 255 on average, most of it at shadow edges, where live is
sharper.

Getting there took three fixes, each found by comparing against the bake:

1. One shadow map for both lamps left the sun unshaded by anything the key lamp clears. The sun
   got its own map.
2. Sunlight leaked through forests. Tree cards now cast.
3. The colour curve (item 5 above).

## Switches and numbers

- Quality: `liveLight`, on for High, off for Medium and Low.
- URL: `?live=0` keeps the bake, `?live=1` lights live on any tier.
- Look: everything is in `LIVE_LOOK` in `client/src/lib/sect/live.ts`.
- `?debug=1` puts the state on `window.__sectLive`: change `look`, call `apply()`. `setMix(0)` shows
  the bake.
- Cost on the development PC at 1600 x 900: no measurable change in frame time (about 1.7 ms
  either way). The two shadow maps draw once, in 7 ms. GPU memory is the price, about 420 MB: the
  colour maps at 4096 px, the sky-light and direction maps at 2048 px (`sect_live.py` halves those
  two; sky light is soft and the page normalises directions), and two 4096 px depth maps. A
  stop's maps are a 5 to 10 MB download (83 MB for all eleven; the page fetches one stop's at a
  time, and the next stop's ahead).

## The balance

With `sunGain`, `keyGain` and `ambientGain` at 1 the page's sum is the bake's. They are now 1.1,
1.05 and 1: a little more sun, and the bake's own shade. The baked areas start 45 m away, past
the lawn, and no seam shows in the flight.

## What the first review found

Once four stops were live, a reviewer compared 20 baked and live views of them at full size
(2026-11-10). The verdict was that live was not better than the bake yet: it kept every glow and
showed no seam, but it added defects. Each was checked on crops and fixed:

| Seen | Cause | Fix |
|---|---|---|
| A dot pattern in every soft shadow | The filter's sample disc was turned per pixel | Fixed disc, the GPU's filtered depth test for each read, edges held to 12 texels |
| White chrome bands on glazed roof ridges, a pink glare on painted walls, pale grass on a slope facing the sun | The shine's low-angle term ignored roughness | Held down by roughness and by reflectance; grass has none; paint is a soft sheen |
| The mirror terrace's lawn in leopard spots | Bumps of slope 0.1 on ground the sun grazes | Ground and paving bumps cut to 0.02 to 0.03 |
| Sunlit paint and steps washing toward cream | Gains of 1.35, 1.25, 0.85: the view transform takes the colour out of anything that bright | 1.12, 1.08, 0.95 |
| Painted trim blurry in shade | The half-size sky-light map carried the paint | Sky light stored without the colour |
| The darkest tones a little lighter | The sky sheen | Its amount from 0.8 to 0.3 |

A second round on seven stops found live "about as good as the bake, not clearly better", and
four more things, fixed the same day:

| Seen | Cause | Fix |
|---|---|---|
| Shade 11 to 19 percent darker and cooler than the bake (a terrace, a hall's inside) | The lamps' bounced light was a flat guess | Taken from the bake (`sect/live_bounce.py`) |
| The forge's doors grey beside the furnace | The sky-light map clipped firelight | Its range doubled; a texel at the top keeps the bake |
| Banners dull on one side | They shaded themselves as they waved | The lift above. A two-sided light was tried too and dropped: the bounce map already holds the light that comes through cloth, so it was counted twice |
| Navy name boards gone mauve, white roof ridges at three stops | Sheen and shine again | Sheen 0.3 to 0.15, shine 0.8 to 0.5, rougher tiles, glaze and paint |

A third round looked at all eleven stops (110 pictures, two reviewers). Verdict: live about equal
to the bake everywhere, a little better at the forge and the mirror, a little worse at the abode,
and what it still added were small blotches up close. This time the fixes changed the approach
(the two bold paragraphs under "Shadows" above) instead of tuning numbers:

| Seen | Cause | Fix |
|---|---|---|
| The abode's cliff a quarter more orange, its cracks soft | The maps rebuild the bake's light at half size and a little off in colour | The bake's detail |
| Carved stair slabs in hard blocks, red pillars blotchy | The half-size direction map under a grazing lamp | The same: the blocks are in the rebuilt bake too, and divide out |
| Dashes of light on the stele colonnade's floor | The roof is a sliver in the key lamp's map, and faces the flight never sees are not in the page | The page's shadows only tighten the bake's, near its edges |
| Saw teeth on stair treads | The slope bias broke the thin shadow under each nosing into dashes | Biases 0.05 to 0.03, slope cap 4 to 1.5 |
| Name boards lavender again, a teal ridge cream | The lamps' shine on dark paint and glaze | The shine's cap |
| Blotches on a silver crescent, a gold disc and a sword blade | The half-size direction map in a mirror, and bumps on metal | Metal keeps the face's direction and has no bumps |
| Warm ovals on a roof face in shade | The tiles' roll caught a lamp the face barely sees | The bump cap |
| Red pillars lumpy | Bumps on paint | Paint's bumps cut to a third |

After it, live differs from the bake by 2.6 steps of 255 on average over the 55 views (it was 3.4
before), and the brightest and darkest tones match. What live still adds is small on purpose:
a little more sun, tile relief, tighter shadows next to what casts them, a held-down shine.

A forge roof that looked wrong in a small picture was right: the bake and the page's sum agreed
there to a few steps of 255. `tools/sect_live_probe.py <stop> "x,y,z"` is for that kind of check: it
reads the baked atlas and the bake's live maps at a world point and prints both through Blender's
view transform.

## How it ran

The gate: one rented box on 2026-11-10, 14:49 to 15:12, $0.29. The gate at production quality
took 16 minutes: 7 for the lit bake, 6.5 for the bake with the lamps off, the rest for the two
guide passes, the small pieces and the post step. The scene file did not change.

The other ten stops, and the gate again so every stop is from one run: one box (instance
60144405) the same day, 16:39 to 19:08, about $2.08. The bake is repeatable: the gate came out
with the same layout and the same calibration as the first time. `live_bounce.py` for all eleven
took under a minute. 154 files were fetched and checked by md5, the box was destroyed and the
instance list confirmed empty.

## Every stop

The page lights one stop at a time: the one the flight is at. Stops are 190 to 240 m apart and a
stop's live disc is at most 90 m across its radius, so two never meet.

- **Which stops.** `client/public/sect/full/live/index.json` lists the stops that have maps
  (`tools/sect_live.py` adds a stop when it installs its maps). A stop not in the list stays baked.
- **Which one now.** Each stop owns a range of the flight's frames (`meta.json` `frameStart` to
  `frameEnd`). The stop whose range holds the current frame is lit, and it stays lit until the
  frame is 10 past its range, so resting on a boundary does not flip it back and forth.
- **How big.** From the stop's footprint in `meta.json`: live is whole out to the footprint plus
  5 m, gone 27 m further, and the shadow maps reach 8 m past that (gate: 45, 72, 80 m; the
  formation, the biggest: 63, 90, 98 m).
- **Handover.** While a stop is lit and the flight moves on past its hold view, the next stop's
  maps load in the background and are held. At the change the old stop fades out in 0.3 s and is
  freed, and the new one only has to draw its shadow maps and fade in. One stop's maps are about
  255 MB on the GPU, so the peak is about 420 + 255 MB while a neighbour is held
  (`LIVE_LOOK.handover.preload` switches the holding off).
- **Fast travel.** Under the ink the old stop ends at once, the new one lights with no fade, and
  the ink waits for it, at most 2.5 s.
- **Per-stop numbers.** `LIVE_LOOK.stops.<id>` can override the gains, exposure and saturation
  for one stop.

## Lighting a stop without freezing the page

Added 2026-11-13. The owner tried the local page and found it "very very laggy". A timed wheel
scroll of the whole flight showed why: each time the live light started at a stop the page froze
for 0.1 to 1.3 s, sometimes 3 s. Every freeze was the page asking the GPU about a shader program
that was not built yet. three.js asks on a program's first use, and the call waits for the driver.

Four causes, all fixed without touching a shader, a map or a uniform's value:

1. **The shadow maps' depth programs were built again at every stop.** Their materials were freed
   with each stop's maps, and a freed material frees its program. They now belong to the page
   (`live-shadow.ts` `depthMaterial`): one for each program three builds for them (a plain or an
   instanced caster, with or without normals), and for a cut-out caster one per card material.
   `LiveShadowMap.compile` builds them off the frame before a map's first draw, with the map's own
   target bound, since a render target's programs are not the screen's.
2. **A stand-in copy did not compile its material's program.** The live programs are compiled
   ahead on copies of the materials (`live.tsx` `warmCopies`). three's `Material.clone` leaves
   `flatShading` and `defines` behind. GLTFLoader sets `flatShading` on every baked material,
   because the baked meshes have no normals, so every copy compiled a program nobody drew with
   and the real one was linked on the frame (mission paving 0.6 to 0.7 s, mirror tiles 0.5 s).
   `client/src/lib/sect/program-key.ts` `keepProgramFields` gives a copy those fields back. Its
   test builds three's own program key and checks that a copy gets the material's.
3. **One material can need several programs, and the switch came too early.** A material drawn
   on meshes of two kinds (plain and instanced, with and without normals) has a program for each.
   There is now one copy and stand-in per kind (`programVariant` in the same file). The real
   materials used to be bound to live light while the copies were still compiling, so one of them
   could pick up a half-built program. They are now bound only for the compile call itself, which
   is synchronous, and again at the switch.
4. **A program that is ready still costs its first use.** three then reads its uniforms and
   attributes, a blocking round trip that waits behind whatever the GPU process has queued (on a
   stop's first frame, that frame's uploads). `program-prime.ts` waits until every program of a set
   of materials is linked (`programsReady`; three's `compileAsync` only waits for each material's
   last one), waits for the GPU to work through its queue (`gpuDrained`, a fence that is polled,
   never waited on), and runs the first use there (`primePrograms`). The chunks' own programs
   (`scene.tsx` World warm-up), the decorations and the fire go through the same three steps.

Two more things came with it:

- **Programs are kept for the page.** When a stop goes, one copy per live program stays, per
  renderer (`releaseCopies`). A stop whose set was dropped and loaded again links nothing.
- **A guard in development.** For 30 frames after a stop's switch, `guardSwitch` warns in the
  console if one of the stop's materials draws with a program that did not exist at the switch.
  It is compiled out of a production build. It never fired in about 40 page loads.

### What it measured

Dev server, 1600 x 900, High, live light on, a game running on the same GPU. One run is a fresh
load, 12 s at the gate, 80 wheel steps down to the summit, 10 s, 80 steps back, 10 s. A "wait" is
a blocking call on a shader program that takes over 16 ms. The engineer and the checker each ran
journey and dusk in turns; these are both their runs together.

| Per flight | Old code (10 flights) | New code (14 flights) |
|---|---|---|
| Waits | 10 to 27 | none in 13 flights; 2 in one (346 and 25 ms, both at the first stop) |
| Time frozen in waits | 0.8 to 12 s | 0, and 0.37 s in that one |
| Shader programs linked | 229 to 285 | 46 to 62 (19 on the way down, 13 on the way back, the rest at the first stop) |
| Frames over 100 ms | 3 to 23 | 2 to 11 |
| Worst frame | 0.24 to 3.2 s | 0.13 to 0.36 s, and 2.6 s in one flight |

The waits no longer depend on the look: the journey and dusk both have none.

The old code also made Chrome log 217 to 256 "texture format and sampler type mismatch" errors a
run, each one a draw call that was skipped. The new code logs none. Which draw it was is not known.

**The picture is the same.** With motion frozen (`prefers-reduced-motion`, lossless captures) old
and new code were compared at five views: the abode is identical in every pixel, the dusk summit
in 99.98 percent (largest difference 1 step of 255), the arena 97.8 (1 step), the forge 96.6
(2 steps), the gate 95.6 (10 steps on 0.01 percent of pixels, which two captures of the same code
also show). Crops of shade and of sunlit ground at the gate, the arena and the abode differ by
exactly 0. All 11 stops and 4 dusk views against the earlier references: within 0.5 steps on
still areas, except the forge (its fire) and the dusk summit (the reference itself is off by the
same amount with the old code).

**Nothing grows.** Over gate, summit, gate, summit, gate, summit the counts settle after the second
pass: 87 programs and 84 textures at the gate, 85 and 84 at the summit. Turning live light off
while a stop was starting (4 tries), fast travel away while it was starting (4 tries) and a new
canvas after a tier change all came back lit with no error.

Sheets and raw numbers are on the PC that ran them: `.playwright-mcp/survey/perf2/` (the fix) and
`.playwright-mcp/survey/perf2_check/` (the check).

### What is left

The second round dealt with most of this list: see [`smooth-flight.md`](smooth-flight.md). What follows is
the state after the first round.

- **Texture uploads.** With live light on a flight puts about 90 textures on the GPU that take over
  10 ms each, 2.2 s in all (about 49 and 1.1 s with it off). A 4096 px map takes 15 to 45 ms.
  About 70 percent of the frames over 100 ms that are left hold one. Not changed here: no simple
  change gives the same texels without going round three's upload code.
- **The first stop.** In about one flight in three the first stop has a frame of 0.24 to 0.34 s
  (2.6 s once) while the driver builds a burst of 7 to 13 new programs. The page is not blocked;
  the browser's GPU process is, so the frame shows late. A trace shows the driver holding the
  frame's present until its shader creation is done.
- **A first-ever visit** (no cached shaders) was not measured by the checker. One early run of the
  engineer's with a cold cache had no waits but GPU stalls of up to 1.9 s.
- **A production build** was not timed. Everything above is the development server.
- A set now shows only after all its programs are ready and their first use has run (capped at
  11 s). In a fast flight it may show a little later than before. Not measured.
- The depth materials and the kept copies are never freed, so they hold on to their renderer. An
  older leak already does that: each High to Low to High tier change keeps two old renderers and
  about 330 MB, the same with the old code.
- After a lost graphics context during a start the page raised no error but was not back 15 s
  after the context was restored. Whether the old code recovers was not checked.
- Why the old code's waits were longer with the journey on is still not known. The scene's
  shaders are the same in both looks (185 programs with the same names and lengths; only the post
  pass and dusk's sky differ), and a wait's length did not follow how many programs were being
  built at the time.

## Running it for a stop

1. Rent one RTX 5090 and set it up as in [`../scene/light-r57.md`](../scene/light-r57.md).
2. `bake_web.py -- bakefull --profile full --quality production --chunks <area> --live`, then
   `blender --background --python sect/live_calib.py -- <area>` and read the share (0.318),
   then `blender --background --python sect/live_bounce.py -- <area>` for the bounced light and
   the bake's soft shadow. About 10 to 16 minutes a stop.
3. On the PC: `tools/sect_live.py --chunk <area>`, `tools/sect_pack.py --profile full --only <area>`.
   The maps only fit the chunk file of the same bake run: always do both.

## Not done

- One stop at a time. A stop seen from the next one is the bake.
- Needle and twig cards do not cast (their alpha comes from a pattern the depth pass lacks), and
  the far trees' crown shells cast through their cards.
- Small vertex-coloured pieces and glow surfaces stay baked.
- The sky sheen reads the painted sky, not the scene: a column does not mirror the terrace.
- The bounced light is the bake's, so it does not follow the live shadows' sharper edges, and in
  a shadow's soft edge it is an estimate.
- Live light now changes the picture only a little. Three reviews found the same thing each
  time: with these models and textures a careful bake is already most of what live light can
  show. What still reads as fake is in both pictures (a cliff like crumpled paper, crowns in
  rows, spotless marble, a flat waterfall), and light will not fix it. The reviewers' lists are
  in `.playwright-mcp/survey/review_live3_a.md` and `review_live3_b.md` on the PC that ran them.
- The page's shadow maps never add light. Where the bake's shadow is softer than it should be on
  its lit side, it stays soft there.
- A live rock or ground material uses 15 of the 16 texture units many GPUs allow. One more map
  on those classes would not link there.
- The table file and the maps are not in the manifest's revision list. The page fetches them with
  `cache: "no-cache"`.
- If a map or the table fails to load once, that stop stays baked until the page is reloaded.
- The bake's soft shadow is one number for both lamps. Where one lamp is shaded from far off and
  the other from close by, the split between them is a guess.
- `tools/sect_view_lut.py` needs `pip install opencolorio` and Blender's `config.ocio` on disk. The
  table only changes if Blender's colour config or the bake's view settings do.
