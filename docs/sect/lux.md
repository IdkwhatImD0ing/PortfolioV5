# Lux: the light the bake cannot hold

The sect's light is baked in Blender. Every surface arrives in the browser already lit, and the page
draws it as it is. That keeps the picture cheap and stable, but a bake has limits:

- It stores light at a few centimetres a texel, so the thin dark line where a lantern meets the paving
  is lost and small props look like they float.
- It lights surfaces, not the air between them. A sun 7 degrees up should streak the haze behind every
  pillar. Baked, the air is evenly lit.
- It has no lens. Darks sit a little lifted under the haze, and texel edges are soft.

"Lux" is the set of passes the page adds each frame to cover those three. The code is in
`client/src/app/sect/experience/post/` (`ao.ts`, `shafts.ts`, `finish.ts`), the numbers and the plain
maths are in `client/src/lib/sect/lux.ts`, and `effects.ts` puts them into the post chain.

## Who gets what

| Tier | Contact shade | Sun shafts | Finish | Edge smoothing |
|---|---|---|---|---|
| High | yes | yes | toe, sharpening, grain | MSAA, as before |
| Medium | no | no | toe, grain | FXAA (new: Medium had none) |
| Low | no | no | no | canvas MSAA, as before |

Low has no post chain at all, so nothing changes there. When the quality ladder takes MSAA off a
struggling High device, contact shade and shafts rest too, without a shader compile.

## Contact shade (`post/ao.ts`)

Ground-truth ambient occlusion (the horizon method from Jimenez and others, 2016) worked out from the
depth buffer. For each pixel it looks 1.6 m around the surface point for anything that blocks the sky
and darkens the pixel by how much is blocked.

- The scene files carry no normals, so the normal is rebuilt from depth.
- It runs at the frame's size up to 1080p and is scaled down above that.
- Two depth-aware blur passes take out the sampling noise without smearing across edges.
- Bright surfaces fill their own creases back in (a multi-bounce fit), so white marble never creases
  to black.
- Glows are left alone. Leaves and grass keep only a small share, because blades are thinner than the
  search radius and a lawn at full strength turns to soot.
- It fades out between 110 and 260 m.
- Mist and cloud puffs are drawn after the world and are not in the depth buffer. They now write how
  much of the world they let through into the frame's alpha (`veilBlending` in `materials.ts`), and
  the shade is scaled by it. Without that the shade was drawn on top of the mist as dark specks.

## Sun shafts (`post/shafts.ts`)

1. A shadow map of the world from the sun: 4096 texels across a 1280 m square centred on the camera,
   looking 5.2 km toward the sun for whatever stands in the light's way. The world is static, so the
   map is only drawn again when the camera has moved 110 m or a chunk has streamed in.
2. A march of every pixel's view ray through the haze, 32 steps, at half size. Each step is in light
   or in shade by the map.
3. Each ray's lit share is compared with the same share averaged over the frame around it. A ray with
   more light than its surroundings is a shaft and gains a little gold. One with less lies in a shadow
   and loses a little. Air that is in shade all around (a gorge floor) takes a mild broad shade.

Step 3 is the part that took three tries. Adding light for all lit air washed the picture out toward
the sun. Comparing each ray with a fixed share still lifted open sky. Comparing with its own
surroundings changes nothing in open air, lit or shaded, and only shows where light and shade meet.

The shade is kept off the cloud sea. An island's shadow in the air above it read as a dark stripe
drawn on the cloud.

## Finish (`post/finish.ts`)

One more term in the merged effect shader, no pass of its own.

- **Toe.** Darks go deeper, the rest stays. The haze lifts every dark in the frame a little, and this
  puts the nearest ones back down so the foreground has weight against the pale distance.
- **Saturation** up 7%, giving back the colour the deeper darks take.
- **Sharpening** on High only: the frame's difference from its four neighbours, added back, capped.
- **Grain**, about one and a half 8-bit steps in the mid tones. The pattern changes only when a frame
  is drawn, and stands still with reduced motion.

Glows over 1.0 pass through unchanged. The hue clip after it handles them.

## Also changed with it

- **Mist.** The puffs' noise is now fixed in the world instead of in each sprite, and it cuts deep
  into the rim. A row of puffs reads as one torn bank of mist. Before, each puff showed its own smooth
  ellipse, which from the side looked like a stack of saucers.
- **The sun.** Its glow is screened onto the sky instead of added. Added, the sky near the sun went
  past 1.0 and the hue clip turned it into a flat pink plate with a hard rim.

The mist was reworked once more the next day, after the flight sweep
([`flight-sweep.md`](flight-sweep.md)): a wide soft rim on every puff, and thin banks seen edge on
drawn as low faint veils.

## Looking at it

- `?lux=0` builds none of it, for a before and after on the same frame.
- `?lux=ao` shows the contact shade alone as a grey image.
- `?lux=shafts` shows where a ray is lighter than its surroundings (gold) and darker.
- With `?debug=1`, `window.__sectPost.ao`, `.shafts` and `.finish` each have a `suspended` switch, and
  `shafts.redraws` counts shadow map draws.

## What it costs

Measured only on the owner's RTX 5080, where it is too small to see. By count, on a 1080p frame:
contact shade is about 17 depth reads a pixel plus two blur passes, shafts are 32 shadow reads a pixel
at a quarter of the pixels, and each shadow map redraw is one depth-only draw of the loaded world.
High is picked for desktops with a discrete GPU (or one the browser will not name), never for touch
devices, and the ladder rests both passes when frames run slow. The shadow map takes about 48 MB of
GPU memory. None of this has been timed on a mid-range or integrated GPU yet.

## Looks and the journey

The day runs along the flight. The gate is at sunrise, the day passes as the visitor scrolls, and
the summit is night under the moon (sun into moon is the sect's name). This is the page's normal
look, for every visitor and every quality tier. It is built from four looks (gold, day, ink, moon)
and today's dusk, blended by where the camera is.

### The arc

One table, `JOURNEY` in `client/src/lib/sect/journey.ts`, keyed by the stops' holds. Retune it
there.

| Stop | Hold frame | Look | Reads as |
|---|---|---|---|
| gate | 93 | gold | sunrise |
| mirror | 217 | gold 50%, day 35%, ink 15% | a soft sunlit morning mist, colour kept |
| forge | 352 | day 85%, ink 15% | late morning, a little haze left |
| arena | 516 | day | noon |
| mission | 619 | day 90%, gold 10% | early afternoon, a first warmth |
| library | 772 | day 50%, gold 50% | late afternoon |
| steles | 974 | gold | golden hour |
| scroll | 1103 | gold 50%, dusk 50% | sunset |
| formation | 1208 | dusk 70%, moon 30% | the last light after sunset |
| abode | 1380 | dusk 40%, moon 60% | blue hour |
| summit | 1647 | moon | night |

- Each stop takes the camera's own hold frame (the table's frame is the fallback).
- The mirror was ink and day half and half: a flat grey sky and grey far peaks right after the
  gold sunrise. Gold in the mix warms the mist and gives the far peaks back a little colour.
- The day keeps moving through the three day stops, each a small step from the one before. The
  forge keeps a little of the mirror's mist (never more ink than the mirror), the arena is the clear
  day alone, the mission takes a tenth of gold. (A quarter was tried: gold's warm sky turned the
  mission's blue sky grey white, top of the frame 142,142,150. At a tenth it is 141,150,164.)
- From the steles on, gold's share only falls and the moon's only rises, so no stop looks earlier
  than the one before it. Today's dusk alone at the formation was paler and brighter than the
  sunset at the scroll, so the day seemed to go back an hour. Along the evening the frame now gets
  darker and bluer at every stop and half-way point (mean brightness 139 at the scroll, 131 at
  frame 1156, 108 at the formation, 83 at 1294, 80 at the abode, 58 at 1514, 56 at the summit).
  The abode's plaque and its red characters stay readable at 60% moon.
- Between two stops the weights blend by frame with the same smooth easing as the haze per stop,
  so the look rests near each stop and changes on the way. Before the gate it is the gate's look,
  after the summit the summit's.
- The looks blend lever by lever: numbers and lists linearly, colours in linear light. The frame
  grade fades by its amount alone where today's dusk (which has none) is in the mix, and its glow
  gain fades with the amount too. (Without that, a stop of dusk alone made the glows jump one frame
  past it: the moon's glow gain of 2.6 applied in full at an amount near 0. The arc has no such
  stop now; the test keeps the case.) Stars
  lean late: their share is the moon's weight cubed, about a fortieth at the formation and a fifth
  at the abode.
- `journey.test.ts` checks the endpoints, that each stop is exactly its mix, that every look's
  weight moves one way between two stops, that the day stops are all mostly day and differ from
  their neighbours, that from the steles on gold only falls and the moon only rises, that today's
  dusk alone is exactly today's page, that the frame grade has no jump next to a stop that is dusk
  alone, and that the blended patch holds every run-time lever and nothing else.

### How the look follows the frame

`client/src/app/sect/experience/look-now.ts` keeps its own copies of the look tables. Each frame,
`scene.tsx` Atmosphere asks it for the look at `store.frame`, before anything draws. When the
frame moved it blends the looks into the copies and bumps a version. The page's own tables are
never written by the journey, so a shader built later still gets today's numbers as its fallback.

Every reader compares the version with the one it last used, so a frame where nothing moved costs
nothing:

- Atmosphere: the sky dome's gradient, clouds, coverage, stars and sun, the reflections' sky
  (`SECT_ENV`), the cloud sea, the moon and its halo, the land's haze colour (`scene.fog.color`)
  and the haze per stop (`scene.fog.density`), and the shared uniforms below (`pushLookGpu`).
- The twilight is part of it. Today's blend toward `SECT_LOOK.twilight` from the scroll to the
  summit still runs by frame, but from the journey's colours to the journey's twilight colours.
  With today's dusk alone that is exactly today's sky.
- CloudPuffs: the puffs' colours and opacity.
- The post chain (`effects.ts` `setLook`): bloom, sun haze, vignette, sun shafts, cloud shade,
  finish and contact shade. A suspended pass stays off.
- `live.tsx`: the live light's gains at the lit stop.

Scrolling, the map's fast travel, a deep link (`#skills`) and `?frame=` all set `store.frame`, so
they all get the look of the frame the camera is at.

### What it costs while scrolling

Measured on the dev server at 1600 x 900: a wheel scroll of the whole flight (80 steps of 380 px),
a fresh page load per run, the journey and `?look=dusk` taking turns. A game was running on the
same GPU the whole time, so single runs swing a lot.

- The blend itself takes about 0.03 ms per moving frame in `lookNowAt`, and all of Atmosphere
  about 0.04 ms more than with dusk. `journeyApply` (`journey.ts`) writes the blended values
  straight into look-now's copies, through paths split once in `journeyTable`, and builds no object
  on the way. The first version built a patch per table and split every lever's path on every frame
  (0.08 ms, and 0.10 ms in Atmosphere). A test checks `journeyApply` against `journeyPatch` +
  `setLevers` exactly, over the whole arc.
- Main-thread script time per second of scroll is level with dusk: 361 to 431 ms against 411 to
  445.
- On Mid and Low, and on High with the live light off (`live=0`), the journey scrolls as dusk does.
  High with `live=0`: 259 frames a second against 263, worst frame 89 ms against 83.
- On High with the live light on (its default) it did not at first. Over five pairs the journey's
  median was 117 frames a second against 159, with 10 frames over 100 ms against 4, and its worst
  freezes were 0.9 to 1.2 s against 0.1 to 0.5 s. Those freezes were the live light's shader
  programs loading on the frame. They were fixed the same day ("Lighting a stop without freezing
  the page" in [`live-gate.md`](live-gate.md)): a flight now has no such wait with either look,
  and 2 to 11 frames over 100 ms with either.

### Run-time levers

Nothing is compiled when the look moves. Levers that used to be built into shaders now read one
shared uniform array, `uSectLook` (17 vec4s, `client/src/lib/sect/look-gpu.ts` packs it,
`materials.ts` `SECT_LOOK_GPU` holds it):

- The haze constants: sun haze colour, cloud layer colour, blue fade, cool tint and mix,
  desaturation, aerial depth, the clear distance, valley mist density, falloff and start, sky
  haze, density (`glsl.ts` `fogDefines`).
- The baked surfaces' grade: exposure, contrast, pivot, split tones, saturation, green tame,
  shoulder (`look.ts` `gradeGlsl` and the range's grade statements).
- The frame grade (see the tiers).

The haze and the grade each have a switch in the array. Off (the default, and what any material
the page never handed the array reads), every shader uses the numbers it was built with. Only the
journey turns them on. Stars are built into the sky once (with a look or the journey) and scaled by
a `uStars` uniform. The tree cards' rim, the ponds' sky and the haze colour of the waterfall mist
and the light beams are shared uniforms too.

The surfaces' grade shoulder (`grade.shoulder`, where highlights start to roll off) is in
`uSectLook` too, and it is a journey lever, since the day look sets it.

`RUNTIME_LEVERS` in `journey.ts` lists every lever the journey moves. Three levers a look sets are
left at today's value, listed in `FIXED_LEVERS`: `puffs.areaThin` (packed into the puffs' instance
data at load), `shafts.dimMax` and `ao.tint` (constants of their shaders). The test checks that
every lever a look sets is in exactly one of the two lists.

### Tiers

- High and Mid: the frame grade is a term of the merged post shader (`post/grade.ts`), built once,
  reading the frame part of `uSectLook` as a uniform array. At amount 0 it passes the frame
  through.
- Low has no post pass. The same grade (`glsl.ts` `sectLookGrade`) runs at the end of every shader
  that draws to the screen there: in the fog chunk just before the hue clip (all baked surfaces,
  the waterfalls, grass and veg shells), and before the colour encode in the sky, the cloud sea,
  the moon, the cloud puffs and the mist. On High and Mid that code is folded away. So a forced
  look such as `?look=moon` grades the whole frame on Low, the land as well as the sky.
- Low still has no bloom, shafts, contact shade, finish or vignette, so it is paler than High at
  the same stop (bright paving reads near white at the forge and the gate).

### Switches

- `JOURNEY_ON` in `journey.ts`: on. Off, the page is exactly today's dusk: no lever moves, no
  switch in `uSectLook` is set and the frame grade and stars are not built. The loading stills
  show the journey's gold sunrise, so turning it off also needs them captured again (see Loading
  posters), or the loading screen fades from a sunrise still to a dusk scene.
- Development only (a production build ignores them):
  - `?look=journey` forces the journey, `?look=dusk` forces today's dusk.
  - `?look=gold|day|ink|moon` forces one look for the whole flight. It is written into the tables
    at load, and it grades the Low tier too.
  - `?look=auto`, `?time=HH:MM` and `?date=YYYY-MM-DD` preview the Pacific clock (below).
- In development, or with `?debug=1` on the live site, `window.__sectLook` says what is showing,
  for example `journey: gold 50% / dusk 50% at frame 1103`, and the console names the look at load
  (`LOOK_READOUT` in `look-switch.ts`). A visitor's page writes neither.

### The four looks

- `gold`, golden hour. Orange to teal sky, warm haze about 1.5 times as thick in bands, a gold key
  and teal shade on the surfaces and in the frame grade, the lit stop's sun at 1.5 and its sky light
  at 0.72, shafts about four times as strong, more bloom and vignette. Its surface highlights are
  paler and a little less saturated than at first (sunlit cliffs and the gate's far piers went hot
  orange), and the frame's highlight tint is at 0.2.
  - The piers seen through the gate were still a neon mustard. Two causes: the frame grade gave
    red-led colour extra saturation (`redSaturation` 1.1), and sunlit orange stone counts as
    red-led; and the surface highlight tint was still strong. Now `redSaturation` is 1 and the
    surface highlight tint is `#ffd2a6` (was `#ffc488`). The piers' blue channel went from about 30
    to about 70 out of 255 on High, so they read as warm sunlit stone. The gate's red lacquer and
    the plaque barely moved.
  - The sky's middle band is a warm grey (`#b4a493`, was the teal grey `#7fa3a6`), so the gate's
    sky reads as sunrise at a glance: the top of the gate's frame went from a teal grey to a peach
    grey (mean of the top 120 rows from 115, 114, 103 to 135, 115, 96). The zenith stays teal.
- `moon`, moonlit night. Navy sky with stars and no sun, blue haze and pale blue valley mist, the
  surfaces darker and cooler, the frame grade at 0.62 exposure leaning blue with the blacks lifted
  to navy (lift 0.018, so eaves keep some detail). Glows skip the grade and are 2.6 times as bright.
- `ink`, ink-wash mist. Paper white sky and haze, the haze about 2.2 times as thick and the valley
  mist seven times, colour taken down to a third except strong reds, soft light at the lit stop.
  Surface exposure 1.38 (white paving went paper white at 1.44).
- `day`, a clear day. A painted blue sky that pales to the horizon, white clouds, thin clean haze
  that turns far peaks blue, fresh greens. Surface exposure 1.46 (the mission hall's marble was
  near white at 1.5). The bake's shadows stay long, so it reads as mid-morning or mid-afternoon.
  - The surfaces' highlights roll off from 0.5 (today's shoulder is 0.74), so the white marble
    paving keeps its slabs instead of clipping. The sky and the mid tones do not move: the shoulder
    is in the baked surfaces' grade only, and anything under 0.5 is untouched.
  - Measured as the share of pixels with all three channels over 245 in the lower half of the
    picture: forge 1.1% to 0.5% on High, arena 0.1% (no change), mission 0.2% to 0.0%, forge on Low
    1.2% to 0.7%, forge on Mid 1.5% to 0.7%. The forge's orbiting props move the number by about
    0.2 between captures.
  - The Low tier shows no paving joints at the forge, with any look: even today's dusk on Low has
    none (the joints on High come from the live light's paving bevel and the detail map). So the
    paving on Low is off the clip but still reads as a plain pale floor.

### The clock (preview only)

`client/src/lib/sect/day-look.ts` holds the look by the time of day in Pacific time, with its
own tests. It is a development preview: `?look=auto` (the clock at load), `?time=` and `?date=`. It picks
one look for the whole flight at load. `FOLLOW_PACIFIC_CLOCK` stays `false`, and the journey wins
over it while `JOURNEY_ON` is on.

- Sunrise and sunset: NOAA's formulas for latitude 37.6, longitude -122.2, checked against
  published times and a second method in the tests.
- The schedule (`DAY_SCHEDULE`): moon at night, moon to ink by R+15, ink to R+90, ink to day by
  R+150, day to S-120, day to gold by S-75, gold to S-15, gold to today's dusk by S, dusk to S+30,
  dusk to moon by S+75.

### Captures

`.playwright-mcp/survey/journey2/`: `strip_stops.jpg` (each stop on High with its weights),
`strip_mids.jpg` (half-way between neighbours), `strip_tiers.jpg` (gate, forge, abode and summit
on High, Mid and Low), `strip_scroll.jpg` (a real wheel scroll from the gate to the summit in 40
steps, plus a `#skills` deep link).

`.playwright-mcp/survey/journey3/` is the tuned arc with the mission still at a quarter gold: the
same strips (no scroll strip), plus `before_after_changed.jpg`, each changed stop from journey2
beside its new picture. `.playwright-mcp/survey/journey4/` has the mission at a tenth gold, as it
ships: `stop_05_mission.jpg`, `mid_568.jpg`, `mid_696.jpg` and `sheet_00.jpg` are new captures, the
other ten stops are copies of journey3's.

### Limits

- The share image (`public/og-image.jpg`) is still the dusk picture.
- What a look cannot change without a new bake: where the light comes from. Shadows and lit faces
  are baked for a sun 7 degrees up in the west, so the moon is lit from the sun's side and no look
  can lengthen, turn or soften a baked shadow. The live light can change how strong the sun and the
  sky light are, not their colour; colour comes from the grades.
- So the wet rock right of the abode's waterfall keeps a warm peach sheen in the blue hour. The
  sun's colour reaches the live shader as a uniform (`uSectLiveSunE`), but the same uniform also
  rebuilds the bake's own light for the detail ratio (`sectLiveBaked`), and that ratio multiplies
  the live colour. A tint on the uniform cancels itself out. Making it work needs a separate
  per-channel uniform for the bake's lamps in the live shader, a shader change, so it is not done.
- The shafts' air density follows the haze per stop but not each look's near haze
  (`haze.densityScale`), so the shafts are a little weaker in thick-haze looks than a forced look
  shows them.
- Small fogged effects outside the list above (flames, petals, fireflies, spray) keep today's haze
  constants and get no Low-tier frame grade.
- Arriving at a stop used to freeze the page for 0.1 to 1.3 s on High while the live light's
  shader programs loaded. That is fixed ("Lighting a stop without freezing the page" in
  [`live-gate.md`](live-gate.md)). Why those waits were longer with the journey on was never
  found; with the fix there are none with either look.
- Chunks streaming in while scrolling used to cost frames of 50 to 125 ms (texture uploads, mesh
  preparation), the same with the journey as without. A second round cut a flight's slow frames
  from about 30 to between 2 and 5: [`smooth-flight.md`](smooth-flight.md).

## Loading posters

The loading screen shows a still of the start view behind its text and crossfades from it to the
canvas (`lib/sect/opening.ts` `POSTER` and `posterBox`, `app/sect/loading-screen.tsx` `Poster`).
The stills are the journey's start: the gate's gold sunrise at frame 27. Capture them again when
that view changes: the gate's entry in `JOURNEY`, the gold look, `JOURNEY_ON`, a new bake of the
gate or the backdrop, or the camera path. They were last captured on 2026-11-13.

`client/public/sect/poster/landscape.webp` is 1640 x 972 (78,390 bytes) and `portrait.webp` is
884 x 1100 (58,890 bytes).

### Capturing

Playwright on the dev server. The default start is frame 27, so the URL needs no `?frame=`. No
`?look=` and no `?live=`: the poster shows what a visitor sees.

| File | Window (CSS px) | Device | URL |
|---|---|---|---|
| `land_wide.png` | 1920 x 800 (aspect 2.4) | desktop, scale 1 | `/?ui=0&tier=high` |
| `land_tall.png` | 1250 x 1000 (aspect 1.25) | desktop, scale 1 | `/?ui=0&tier=high` |
| `portrait.png` | 884 x 1100 | phone: scale 1.5, `isMobile`, `hasTouch`, an Android Chrome user agent | `/?ui=0&tier=low` |

- The phone needs its own browser context (`browser.newContext({ viewport, deviceScaleFactor: 1.5,
  isMobile: true, hasTouch: true, userAgent })`). The page then matches `(pointer: coarse)` and
  draws at 1.5x, as a phone on Low does. The portrait shift is on, since the window is more than
  1.15 times taller than wide.
- `?tier=low` pins the phone's tier. A touch screen starts on Low unless it looks strong (8 GB,
  8 cores and a GPU that is not a phone's, `runtime.ts` `chooseTier`), and in an emulated phone
  the probe reads this PC's memory, cores and GPU, not a phone's.
- `?ui=0` skips Enter, so the veil has faded by the time of the shot.
- For each: wait for `body[data-sect-ready]`, then 13 s more, then a PNG screenshot with the style
  `nextjs-portal{display:none !important}`, which hides the dev server's badge in the corner.

Then, from the repo root:

```
python client/scripts/make-poster.py land_wide.png land_tall.png portrait.png client/public/sect/poster
```

It scales both landscape captures to one scale (1640 px across), pastes the tall one over the
wide one, evens out the seam, fills the corners with a blur, resizes the portrait, saves WebP at
the highest quality that fits under 80,000 and 60,000 bytes, and prints the sizes.

### How well they match

Checked by cutting each screen's view out of the poster with `posterBox`'s maths and comparing it
with the live start view (`.playwright-mcp/survey/journey3/poster/`):

- Position: within 0.2 px on 1920 x 1080, 1280 x 1024, 2400 x 1000 and a 390 x 844 phone. The two
  landscape captures also line up with each other within 0.2 px.
- Colour: 1280 x 1024 and the phone differ by about 3 levels out of 255 on average, which is
  moving clouds and resampling. The old dusk stills differed by 12 to 43 on average, and by up to
  61 in blue in the top third at 1920 x 1080.
- The frame's vignette darkens each screen towards its own edges, so a still can match it exactly
  only at the shape it was captured at. On 1920 x 1080 the poster is 10 to 19 levels brighter in
  the top and bottom thirds (about 1 in the middle). On 2400 x 1000 it is 6 to 9 darker in the
  middle third. Both change smoothly, with no step, and the veil's scrim darkens the still far
  more than that.
- The two captures meet at the edges of the tall one, where the vignette made it about 15% darker
  than the wide one. The wide one's sides are brought to its level there and back to their own
  over 160 px, so no seam shows. The four corners neither covers are a blur; no screen sees them.
- With every request under `/sect/full/` held back 5 s (1600 x 900, `?tier=high`), the veil
  showed the new poster while it waited, and the canvas after Enter was the same view in the same
  colours (`fade_ends.jpg`). In the first second
  after Enter the tall pillars on the left were still smooth stand-ins without texture; they had
  their texture 15 s later. The poster plays no part in that: those textures were still streaming
  in.

## Not done

- Sharp sun shadows on the ground. The shadow map is 31 cm a texel, and at 7 degrees that stretches
  to 2.5 m along the ground. Good for air, too soft for a lantern's shadow on paving.
- Shine on surfaces the exporter did not tag (lacquer, marble). The atlas mixes materials, so the page
  cannot tell them apart per pixel.
