# Running the sect on weaker devices

Research from November 4, 2026. Question: how can the fly-through run better on
weaker devices (integrated laptop GPUs, budget phones) without losing much quality?

It is a ranked list of options, each checked against the code. The eleven fixes
with no visible change were built the same day (see "What was built" below). The
big texture project and the look upgrades for Low and Medium were not.

## What was built (November 4, 2026)

All eleven fixes in "Fixes with no visible change" went in, with these
differences from the plan:

- Fix 4 (tree cards): the forest-range weight is not interpolated from the
  vertices, because its 25 m fade is not linear at card scale. Instead each vertex
  works out how far it sits past every area's fade, and a pixel skips the 16-slot
  loop only when that margin is at least 4 m (the weight is then exactly 1).
- Fix 5 (ladder steps): the tree-card shader variant is still compiled when MSAA
  drops to 0. Pre-warming it was left out.
- Fix 6 (Low colour): three.js's own scenery and tree materials go from 12 to 6
  `pow` calls per fogged pixel. The waterfall, sheet and foam skirt go to 3.
- Fix 7 (detail layers): the reflection passes were left alone.
- Fix 10 (caching): files are fetched as `<file>?v=<fingerprint>`, using a new
  `rev` map in `manifest.json` (written by `sect_pack.py` from now on), and those
  URLs are cached for a year. A test fails if a file changes without a new
  fingerprint. The early-start script was not built. On art3m1s.me (commit
  8906fe3) a `?v=` URL gets `public, max-age=31536000, immutable`, while the same
  file without `?v=` and `manifest.json` still get `max-age=0, must-revalidate`.
  14 of the 16 scene files the first stop loads used `?v=`.
- Fix 11 (reflections): pond reuse is on Medium only. High still redraws the pond
  every frame.

How it was checked:

- Types, lint and all 1,843 unit tests pass (36 are new).
- Screenshots of 21 views (Low, Medium and High at 7 stops) before and after match
  within the noise between two identical "before" runs. No view had a single pixel
  more than 8/255 off beyond that noise.
- No shader errors or warnings in the console on any tier.
- A quality step down mid-flight (MSAA off, then bloom off) shows the same picture
  after the next rest as a fresh load at that quality.
- Frame rates: with the mouse moving over the scene, High drew about 351 frames a
  second before (on a 360 Hz screen) and about 30 after. Medium's pond reflection
  at rest went from 30 redraws a second to 10.
- GPU time: on the test machine's RTX 5080 the GPU switches between a fast and a
  slow clock state on its own, so whole-frame times jump between about 1 ms and
  2.4 ms regardless of the code. In runs where both versions sat in the fast state,
  Low was about 17-23% faster. Medium and High showed no measurable change on this
  GPU, and nothing got slower. The savings are aimed at weak GPUs, which were not
  available to measure.

## Short answer

The site already does the big, obvious things well: quality tiers, a frame-time
ladder that steps quality down and back up, shader warm-up, worker decoding,
one texture upload per frame, and a slow frame rate at rest.

What is left is mostly hidden waste: work the GPU or CPU does that never shows up
in the picture. About ten fixes remove that waste with no visible change on any
tier. Most are small. The one big project is GPU-compressed textures, which would
cut texture memory to a quarter but make downloads 2.5 to 3.5 times larger.

## How this was done

- Four agents read the code in four areas: the render loop, the shaders, the live
  effects and CPU work, and assets, memory and CSS.
- One agent loaded the live site (art3m1s.me) at each tier and read what it draws.
- One agent searched the web for current techniques.
- A lead agent merged everything into 18 candidates.
- Two reviewers then tried to knock each candidate down by reading the cited code.
  They corrected most of the numbers. Two candidates were dropped or found mostly done.

The live run used a strong desktop GPU (RTX 5080) with the tier forced in the URL.
So it shows what each tier draws, not how fast a weak device draws it. Every
millisecond figure below is an estimate from counting shader work or from the
code's own comments, unless it says "measured".

## What each tier draws today (measured)

| Stop | Tier | Draw calls | Triangles drawn | Texture memory held |
|---|---|---|---|---|
| Gate | Low | 303 | 4.7 M | about 200 MB |
| Gate | Medium | 482 | 6.5 M | about 870 MB |
| Gate | High | 545 | 6.7 M | about 870 MB |
| Forge | Low | 200 | 3.0 M | about 280 MB |
| Forge | Medium | 341 | 5.1 M | about 1.23 GB |
| Forge | High | 384 | 5.3 M | about 1.23 GB |
| Summit | Low | 73 | 1.3 M | about 190 MB |
| Summit | Medium | 105 | 1.4 M | about 780 MB |
| Summit | High | 117 | 1.4 M | about 780 MB |

What this means:

- Medium on a desktop holds the same 4096 px textures as High. At the Forge stop
  that is about 1.23 GB of texture memory. Integrated laptop GPUs take that memory
  from the laptop's own RAM, so Medium on an 8 GB laptop is tight.
- Medium and High draw almost the same triangles. The gap between them is grass,
  reflection resolution, MSAA and textures, not mesh detail.
- The Gate is the heaviest stop on every tier. The Summit is the lightest.

## Fixes with no visible change

Ranked by how much they save for how little work. "S" means a small change,
"M" a medium one.

### 1. Hover frames at the resting rate (S, all tiers)

Moving the mouse over the canvas, or resting it on a clickable spot, makes the page
redraw at the screen's full rate, up to 144 times a second. The picture only
changes by a slow 0.5 Hz glow. Drawing those frames at the 30 per second already
used at rest cuts about half the frames on a 60 Hz screen and about 80% on a
144 Hz screen.

Where: `scene.tsx:1173-1183` (every pointer move wakes the loop) and
`scene.tsx:1925-1936` (a hovered spot counts as motion).

Catches the reviewer found:
- Render these frames through the idle path, not the capped path. The capped
  path feeds 33 ms frames to the ladder, which would read them as slow and step
  quality down on browsers without a GPU timer (Safari, Firefox).
- Hover and drag-look share one wake timer (`scene.tsx:319`). Hover needs its own,
  so drag-look keeps the full rate.
- The lore card that follows the cursor is moved inside the frame loop
  (`scene.tsx:1423`). Move it from the pointer handler instead, or it lags.

### 2. Cloud puffs: fog once per sprite, and a cheaper sort (S, all tiers)

About 1,000 cloud puffs are flat sprites. Every pixel redoes fog maths whose answer
is the same across the whole sprite: about 11 `exp` and 2 `pow` calls per pixel.
Doing it once per sprite in the vertex shader gives the same picture.

On the CPU, every moving frame re-sorts all puffs from scratch with a JavaScript
comparator and creates about 1,000 throwaway array views. Updating the previous
order (it is nearly sorted already) and copying by hand gives the same order with
about 60-100 KB less garbage per frame.

Guess: 0.3-1 ms of GPU in cloud banks on an integrated GPU, and 0.5-1.5 ms of CPU
per moving frame on a weak phone.

Where: `materials.ts:1902-1907`, `materials.ts:1975-1976` (the mist has the same
pattern), `scene.tsx:643-660`, `clouds.ts:63-78`.

Skip the proposed "discard faint rim pixels" part on Medium and High: their buffer
is half-float, so tiny alphas still count there.

### 3. Draw the cloud sea after the solid world (S, all tiers)

The cloud sea under the islands draws first (`renderOrder -800`), so the GPU
colours every pixel of it and then paints islands over much of it. Its shader is
9 texture reads and about 120 maths operations per pixel. Drawing it after the
world lets the depth test skip the hidden parts. The site already made this exact
fix for the sky and measured 13% of the world pass on average and 24% at the Gate.

Where: `scene.tsx:475`. A value like 999 sits between the world and the sky.

The saving is smaller than the sky's, because terrain that hangs below the sea
gets shaded and then covered after the move. Measure it with the GPU timer at the
Gate and two or three other stops, the way the sky move was measured. It also
helps the pond and mirror reflection passes.

### 4. Tree cards: move the forest-range weight to the vertex shader (M, all tiers)

Every tree-card pixel runs a 16-slot loop that weighs nearby forest ranges
(`range-look.ts:529-540`). The weight fades over 25 m and a card is a few metres
across, so computing it per vertex instead of per pixel looks the same and removes
about 100-160 operations from every card pixel.

A second, smaller part: today each card pixel is colour-graded before the cut-out
test throws it away. Moving the grade after the test helps on sprite crowns, much
less on needle fans (the GPU only skips work when a whole block of pixels is cut
out). Keep the twig detail multiply after the grade, or colours change.

Guess: 0.2-1 ms in forest-heavy views on an integrated GPU or phone.

Where: `materials.ts:777-810`, `materials.ts:936-947`, `card-shading.ts`.

### 5. Ladder steps without rebuilding the post-processing chain (M, Medium and High)

When a struggling device drops MSAA or bloom, the page throws away its whole
post-processing chain and compiles a new shader mid-flight
(`scene.tsx:1518-1546`). That is a freeze, guessed at 30-150 ms, arriving exactly
when frames are already slow. Climbing back up already waits for the camera to
rest; stepping down does not.

Fix: change MSAA in place (postprocessing 6.39 has a setter for it), switch bloom,
cloud shadows and hold focus off by uniform, and compile the tree-card shader
variants ahead of time. That removes up to 3 freezes on an auto-picked High and
1 on Medium.

### 6. Low tier: one colour conversion instead of three (M, Low)

On Low, three.js converts each pixel to screen colour too early. The fog code then
converts it back, adds fog, and converts it again (`glsl.ts:485-490`). That is 12
`pow` calls per fogged pixel. Fogging before the conversion, with the fog colour
decoded once on the CPU, leaves 3. Same maths, same colours.

Guess: 2-5% of a Low frame's GPU time. Change it once in `installFog`
(`materials.ts:81-91`) and check each custom shader that includes the colour chunk.

### 7. Rock and lawn detail: skip layers that have faded to zero (M, Medium and High)

Rock and lawn shaders read fine detail textures that fade to nothing far away
(rock detail past 150 m, ground detail past 140 m). The code reads them anyway,
because it was written without branches. A distance check with pre-computed
derivatives (`textureGrad`, as the paving already does) skips about 6 texture reads
per far rock pixel.

Guess: 0.2-0.7 ms in wide range views on an integrated GPU. The same switch can
turn detail off in the pond reflection, but not in High's mirror, which reflects
the paved dais sharply.

Where: `detail.ts:762-844`.

### 8. Cloud-shadow pass: cheap checks first (S, Medium and High)

The full-screen pass that darkens ground under clouds runs all its fog maths on
every pixel, including pixels that end up unchanged. Testing "is this pixel lit"
and "is the deck clear here" first, then returning early, gives a bit-identical
image. About 15-30% of that pass, roughly 0.1-0.4 ms on a weak integrated GPU.

Where: `post/atmos.ts:68-88`.

### 9. Drop the backdrop blur under the area panel (S, all tiers)

UI panels that blur the 3D scene behind them make the browser redo the blur every
time the scene redraws. The area panel is 89.5% opaque plus a paper texture, so
its blur barely shows. Removing it is near-invisible. Guess: 0.2-1 ms of
compositor work per frame on phones. Not profiled; a Chrome performance trace
would settle it.

Where: `sect.css:327-335`, `content.css:1313-1325`.

The map, the readers and the page-view header cost nothing here: the scene stops
redrawing under them.

### 10. Year-long caching for asset files (M, all tiers, load time only)

The 3D files are served with `max-age=0, must-revalidate` (checked with curl
today), so every visit asks the server about each file again. Caching them for a
year under versioned names saves about 4-8 round trips on the opening path on a
repeat visit (roughly 0.2-0.6 s on mobile).

Needs: versioned or hashed file names from `sect_pack.py`, a `headers()` rule in
`next.config.ts`, and `manifest.json` kept uncached. A second step could start the
manifest, camera JSON and the 9.6 MB backdrop from a tiny inline script before the
JavaScript loads (about 0.5-1 s sooner on a first visit). It must skip Save-Data,
`?view=page` and devices without WebGL2, as the loader does.

### 11. Pond reflection at rest (S, Medium and High, battery only)

At rest, the pond reflection redraws on every idle frame even though nothing in
it moves much. Redrawing it every third idle frame saves GPU power and heat at the
Mirror stop. It does not make flight smoother. Keep the ripple time advancing, or
the water freezes (`reflect/index.ts:99-103, 242`).

For the mirror cube, skip timed refreshes only while the camera moves. Do not
lengthen High's 6-second refresh: the bronze is very reflective and the cloud jump
would show.

## The big one: GPU-compressed textures (L, all tiers)

Textures ship as WebP, which the GPU cannot read, so each one is unpacked to full
size in GPU memory. KTX2 with UASTC stays compressed on the GPU at a quarter of
the size:

- Forge stop, Medium and High: about 1.23 GB down to about 0.31 GB.
- Low: about 280 MB down to about 70 MB.
- Uploads move a quarter of the data and skip mipmap generation, so the hitch when
  an area arrives gets shorter.

The cost is download size. UASTC is 8 bits per pixel before compression, against
WebP's much smaller files. The reviewer estimates the textures grow from about
40 MB to 200-320 MB over the whole flight, and each area file from about 11 MB to
25-40 MB. It also adds a WebAssembly transcoder.

Quality should match or beat today's WebP (which halves colour resolution) if it is
encoded from the original PNG bakes. Do not use ETC1S: it bands baked light.

Suggested path: trial one area first (bytes, an image-difference score, and a
side-by-side look). A cheaper fallback, if the download growth is too much: decode
each WebP just before its upload, which cuts the memory peak while an area arrives.

A follow-on, if KTX2 lands: a compressed 4096 px atlas costs about the same memory
as today's 2048 px one, so Low and touch Medium could get High's sharper textures
at today's memory, gated on connection speed.

## Making Low and Medium look closer to High

These cost a little GPU time but close part of the gap to High.

| Idea | Tier | Cost | Gain |
|---|---|---|---|
| FXAA edge smoothing when MSAA is off | Medium (and High after the ladder drops MSAA) | about 0.3-0.8 ms | Medium has no anti-aliasing at all today, so every edge stair-steps. This is the most visible gap. |
| Sun haze and vignette as two blended quads | Low | about 0.1-0.3 ms on a phone | Low skips all post effects, so it loses the warm sun glow and darker corners. Use a screen blend for the haze, not plain addition, or bright surfaces clip to yellow-white. |
| A small grass layer, as a ladder rung | Low | about 0.3-1 ms on a phone | Low draws no grass. Turn it on only while frames have room, and drop it first. It needs an 80-110 m reach to cover the lawns at the stops. |
| Edge-aware upscale (FSR 1) at the 0.75 render-scale step | Visitor-picked High only | about 0.5-1.5 ms | Sharper image at the bottom step. Only worth it where MSAA is still on; without it, the sharpening makes jaggies worse. |

For FXAA, run it in a second pass after the hue clip, and move the dither to the
very end so FXAA does not blur it.

## Dropped or already done

- **Dimming the resting frame rate sooner on Low and Medium.** Dropped: water,
  flames and petals would look steppier, which breaks the "quality beats
  optimisation" rule, and the real saving is 11-25% of resting frames, not half.
  A no-loss version: dim when the browser window loses focus.
- **Simplified far geometry.** Mostly already done offline: Blender decimates by
  distance to the camera path, and the packer simplifies each area to under half a
  pixel of error. One leftover: the backdrop and tree files skip that sub-pixel
  pass (`sect_pack.py:1706-1709`). Running it on the backdrop is invisible and adds
  no download. Check first why it was left out.

Already in place, and worth keeping: device-probe tiers and the ladder, the sky
drawn last, idle frame rates (30, then 20, 10 under the veil, 2 with reduced
motion, 0 under readers), one texture upload per frame, worker decoding, shader
warm-up with `compileAsync`, 2048 px textures for Low and touch Medium, the pond
reflection drawn only over the pond at reduced resolution, one instanced draw for
the clouds, and per-tier counts for flames, spray, petals and grass.

## What is still unknown

- No frame times on weak hardware. Before building, time one weak laptop or phone
  at the Gate with `?debug=1` and the GPU timer, then again after each fix.
- How much screen each material covers, and how many tree cards there are. The
  GLB files are Git LFS pointers in the worktree used for this research.
- The compositor cost of the backdrop blurs (fix 9).
- KTX2 size and quality against today's WebP. Needs a one-atlas trial.

## Decision for the owner

One option changes how Low looks, so it is the owner's call: removing the blur from
the small HUD plates on Low. The scene would show a little sharper through their
18% see-through. Raising their opacity from 0.82 to about 0.88 would keep the
contrast.

The raw research output, with every agent's findings and file references, is in
[`low-compute-devices-2026-11.json`](low-compute-devices-2026-11.json).
