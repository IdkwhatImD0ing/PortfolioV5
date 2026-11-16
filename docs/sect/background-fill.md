# Every place loads in the background on a strong desktop

Added 2026-11-15. Far places drawn in full came the same evening (the section "Far places in full").

## Why

The owner asked what it would cost to draw the far places in full by default. After seeing the
numbers and a picture he said: "I think the best thing is to be first load the gate and then ...
once we display the gate, we start to slowly load the stuff in the background until everything".

Until now the page held the place the camera is at and two on each side (the window). A place
further off showed as a light stand-in until the camera came near, and was thrown away again once
the camera had left it behind.

## What holding costs, and what drawing costs

Measured at the gate on High (production build, 1600 by 900, RTX 5080):

| | places held | texture memory | draw calls | triangles drawn | GPU time per frame |
|---|---|---|---|---|---|
| Before | 4 | 867 MB | 550 | 8.9 M | 3.0 ms |
| Every place held, drawn as before | 11 | 2,241 MB | 550 | 8.9 M | 3.0 ms |
| Every place drawn in full | 11 | 2,241 MB | 1,077 | 22.0 M | 5.5 ms |

Holding a place costs memory and nothing else. A place is drawn only while the camera's frame is
inside the range of frames it is seen from (its need range in the manifest), so the seven extra
places at the gate are held but not drawn, and the frame is the same frame.

Drawing every place in full costs about 80 percent more GPU time at the gate and twice the draw
calls. What it buys there is small: 1.8 percent of the pixels change, the far spires by the moon.
So the first build held everything and still drew by the same rule. The owner then looked at the
gate both ways and said yes to drawing far places in full. That is "Far places in full" below. It
costs much less than the last row here, because a far place is drawn without its grass and fires.

## What changed

1. **After Enter, the rest load one at a time.** The places past the window in the direction of
   travel come first, nearest first, then the ones behind. The next one starts only when the last
   one is on the graphics card.
2. **What is loaded stays**, up to 3 GB of textures. All eleven places take 2.24 GB.
3. **More places are drawn in full on the way.** The draw rule did not change, but a place inside
   its need range that used to be a stand-in because it was outside the window is now loaded, so it
   is drawn. At the mission hall 9 places are drawn in full where there were 6, at the library 9
   where there were 6, at the abode 7 where there were 4.
4. **A stand-in keeps its rock** whatever has been loaded (below).

## Who gets it

- The High tier on a desktop (no touch screen).
- 16 GB of memory: `navigator.deviceMemory` of 16 or more, or 10 logical cores where the browser
  hides the memory (Firefox, Safari). An 8 GB machine shares that memory with the system, and an
  integrated GPU takes its textures from it too.
- A line the browser does not call 3G or slower, and no data saver.
- One strike: a step down the quality ladder ends it for that page view. The page drops back to the
  window (2,241 MB to 867 MB in a quarter of a second when tried) and a step back up does not bring
  the filling back. Slow frames are the only sign of short GPU memory a page gets. Since far places
  are drawn in full, the ladder's first step only puts them back to stand-ins and keeps everything
  loaded. The strike is the step after that.

Phones, tablets, Low and Medium are as they were.

Only the browser's class of line is read, not its bandwidth figure. Chrome leaves localhost out of
that figure and starts a new profile near 1.3 to 1.5 Mbps, and the first build, which cut at 5 Mbps,
never filled on the owner's PC.

## How it stays out of the way

- Nothing fills before Enter (`fillOpen`), so the loading screen's wait for the first stop has the
  line to itself.
- It comes after the spare place ahead (the prefetch), and only while nothing else is loading.
- A background place's parsing waits for the camera to rest, as a prefetch's does.
- A place the camera needs never waits behind a background download. The download is stopped and
  picked up again later. The same goes for a window load the camera has moved away from.
- Nothing fills while fast travel waits under the ink for a stop to settle.

Where it lives: `PlanWindow.fill` and `ChunkPlan.fill` in `client/src/lib/sect/chunks.ts` (the
planner, pure); `STREAM_BUDGETS.everything`, `streamBudget`, `fillMemory`, `slowLine` and
`ChunkStreamer.fillOpen` in `client/src/app/sect/experience/streaming.ts`; `pageBudget` and
`fillStruck` in `sect-experience.tsx`. With `?debug=1` a background load shows in the HUD's chunk
line as `id+...`.

## The stand-in that lost its rock

The first browser check found one thing in the gate's picture that changed after filling: the
tall pillar right of the moon went from banded rock to a smooth tan tube. It is the library's
stand-in.

The cause is older than this change. Rock on the range is drawn paler with dark streaks, except
under anything built (the built mask, which is filled as each place's set is prepared and never
emptied). A stand-in read the same mask. So once the real library had been loaded, the whole
pillar under its terraces counted as built and the stand-in lost its range look for the rest of
the visit. Before this change that took a flight to the library and back. With filling it happened
to every stand-in a few seconds after Enter.

Now a stand-in does not read the built mask (`SECT_STANDIN` in `materials.ts`). It looks the same
before and after its place has loaded.

Checked at the gate, the build before this change against the new one with all eleven places in:
before the fix 1,041 pixels of 1.44 million differed by more than 12 levels out of 255, all on that
pillar. After it, 41 do, on the tip of one far stand-in at the left edge, which used to sit under
a neighbour's built cells and now has its range look back.

## Far places in full

Added 2026-11-15, after the owner saw the gate both ways and said yes.

Until this change a held place outside its need range still showed as its stand-in. Now it shows as
itself, with its own meshes and textures. The page calls that state "far".

**What a far place has.** Only its meshes. No grass, no fires (its carved flames show, as for a
fire out of view), no decoration, no idle motion worked out on the CPU, no hotspots, and no
reflection pass of its own. Those stay with the places whose need range holds the camera, as
before. That is why far costs much less than drawing every place as a near one: at the gate 3.4 ms
of GPU time a frame, where the first measurement above was 5.5.

**When a place first shows as far.** three.js uploads a mesh's buffers the first time it is drawn,
so a first show costs one long frame (28 to 39 ms when measured). A place that has never been on
screen first shows as far only while nobody would notice that frame: under the loading screen,
under fast travel's ink, or while the camera rests. One place per frame. A place that has already
been on screen turns far the moment the camera leaves its need range, moving or not, so nothing
swaps back to a stand-in on the way out.

**In a reflection** a far place is still drawn as its stand-in. The pond and the mirror show what
they showed before and cost the same.

**The quality ladder.** Far places are its first step down, before the resolution, and for a tier
the visitor picked too. That step puts every far place back to its stand-in and keeps everything
loaded. The next step down is the strike that ends filling and gives the memory back. Far places do
not come back on a climb: each would swap forms again, so a page view gets one try. Picking a tier
again starts the ladder over, far places included.

**Who gets it.** The machines that fill: High on a desktop with 16 GB, no slow line, no data saver.
`?far=0` turns it off and `?far=1` forces it on (High only), for a before and after on the same
build. With `?debug=1` the HUD marks a far place with `^`.

Where it lives: `client/src/lib/sect/far.ts` (the rule, pure, and the switch), `LoadedSet.far` in
`assets.ts`, `World` in `scene.tsx`, `Quality.farFull` and `degradeQuality` in
`lib/sect/runtime.ts`, `tierLook` and `stepLadder` in `sect-experience.tsx`, `reflectView` in
`reflect/isolate.ts`.

### What it costs, stop by stop

All eleven places held, the camera at rest at each stop, far off against far on (production build,
1600 by 900, RTX 5080, headless Chrome). GPU time is the median over 120 frames. "Pixels changed"
is the share that differs by more than 12 levels out of 255.

| stop | far places | draw calls | triangles | GPU ms | pixels changed |
|---|---|---|---|---|---|
| gate | 7 | 550 to 1,076 | 8.9 M to 22.0 M | 2.42 to 3.35 | 1.56% |
| mirror | 5 | 482 to 615 | 11.8 M to 16.8 M | 2.64 to 2.70 | 0.01% |
| forge | 4 | 465 to 685 | 10.0 M to 16.1 M | 2.73 to 2.90 | 0.13% |
| arena | 4 | 448 to 506 | 7.8 M to 10.4 M | 2.50, same | 2.42% |
| mission hall | 2 | 323 to 330 | 7.6 M to 8.4 M | 2.46 to 2.57 | 0.34% |
| library | 2 | 262, same | 6.8 M, same | 1.94, same | none |
| steles | 3 | 323 to 340 | 8.5 M to 9.3 M | 2.33 to 2.47 | 1.48% |
| scroll, formation, abode, summit | 3 to 5 | same | same | same | none |
| summit, looking back | 5 | 469 to 950 | 11.8 M to 20.2 M | 2.49 to 3.02 | 0.97% |

The cost shows only where far places are in view. The gate is the worst case: about 1 ms more a
frame, which is 38 percent. From the library on, facing forward, the far places are behind the
camera and cost nothing.

What changes in the picture: at the gate the pillars in front of the moon and the floating rock
show their real rock. At the arena the far pagoda island has its real five-tier pagoda, and a
banner that glowed cyan as a stand-in is the real green one. At the steles the cliff and the
forested slope are the real ones. Looking back from the summit, the whole sect behind is in full
detail.

### What was checked

One agent built it and a second, which had not seen it built, checked it in a browser. It found no
blockers. The lead read the diff and looked at the pictures.

- **Off is the old page.** With `?far=0` the build draws the same calls and triangles as the commit
  before it at four stops, and the stills differ in one pixel.
- **Tests.** 19 new unit tests: the rule, the first-show gate, the ladder's order, the reflection
  view. The whole suite, typecheck and lint pass.
- **First show.** Sitting at the gate after Enter, the seven far places turned far one at a time
  between 0.65 and 6.05 s, never before they were ready, never two in a frame. The longest frame in
  those 25 s was 39 ms with far on and 42 ms with far off, so no frame over 50 ms either way.
  Scrolling from the moment of Enter, no place that had never been on screen turned far while the
  camera moved.
- **Smoothness.** The 40 s scroll over the whole flight with every place in, three runs each. Far
  off had 1, 2 and 1 frames over 50 ms. Far on had none (the worst frames were 25, 47 and 22 ms): a
  far place's buffers are already on the GPU when the camera reaches it. Scrolling the moment Enter
  is pressed, far on had 3 to 4 frames over 50 ms and far off had 5.
- **Fast travel** from the gate to the summit settled in 1.6 to 2.1 s with far on and 1.7 to 1.8 s
  with far off. Under the ink the worst frame was 25 to 34 ms with far on and 158 to 183 ms with
  far off, since the summit's neighbours were already on the GPU.
- **The ladder.** One step down at the gate: far off, the picture equal to the far-off still, all
  eleven places still held (2,241 MB). A second step: the strike, down to the window's 867 MB in a
  quarter of a second. Steps back up never brought far places back.
- **Reflections** at the mirror: in each of the 1,446 reflection passes logged, every far place was
  drawn as its stand-in. The mirror and the pond did not change by a pixel.
- **No holes, no doubles.** At run time each place's meshes were visible exactly when it was near
  or far, and its stand-in exactly when it was neither.

### Rough edges

- **Far places arrive in view.** At the gate the pillars by the moon sharpen one by one in the
  first six seconds after Enter. All seven together change 1.6 percent of the pixels.
- **Thin trunks vanish far away.** On the far pagoda island, seen from the arena, the tree crowns
  seem to hang over the cliff. The page before this drew that island the same way from the mission
  hall.
- **Idle motion worked out on the CPU stops** in a far place (the forge's artifacts, the
  formation's core, the library's scrolls) at the pose it had. Sway done in the shader goes on.
- A far place in front of a hotspot does not block its pick. Far places are normally behind.
- Not tried on a slow GPU. There the ladder's first step takes far places off again, once.
- The ladder's own trigger was not exercised, only its debug hook, which makes the same call.

## What was checked for the filling

This is the first build's check, before far places were drawn in full.

One agent built it and a second one, which had not seen it built, checked it in a browser. The
check failed once (the 5 Mbps rule above), was fixed, and passed. The stand-in fix and the 16 GB
rule came after that, from the lead's own review, and were checked again.

- **Tests.** 16 new unit tests: the fill order both ways, one at a time, the prefetch first,
  nothing dropped once all are held, the texture budget, a jump, the device table, the strike,
  a needed load stopping a background download. With filling off every plan equals the old one
  (a sweep over windows, loaded sets and frames). The whole suite, typecheck and lint pass.
- **The order.** After Enter on High: mission, library, steles, scroll, formation, abode, summit,
  never two at once, each starting after the last was ready. All eleven were in 7.4 to 8.8 s
  after Enter on localhost. Before Enter nothing filled.
- **Cost at rest**, GPU time per frame, before and after (headless Chrome, 60 frames a second held):

  | stop | places drawn in full | draw calls | triangles drawn | GPU ms |
  |---|---|---|---|---|
  | gate | 4, as before | 550, as before | 8.93 M, as before | 2.6 to 2.6 |
  | mission hall | 6 to 9 | 314 to 323 | 6.97 M to 7.57 M | 2.6 to 2.7 |
  | library | 6 to 9 | 249 to 262 | 5.69 M to 6.76 M | 1.9 to 2.0 |
  | abode | 4 to 7 | 195 to 196 | 4.86 M to 5.07 M | 2.1 to 2.2 |

- **Smoothness.** The whole flight scrolled top to bottom in 40 s. Before: 1 to 5 frames over
  50 ms, none over 100 ms, and every place showed as a stand-in at some point. After, scrolling
  the moment the page opens: 1 to 3 frames over 50 ms, none over 100 ms, stand-ins only from the
  library on (5 to 8 s each). After, once everything was in: no frame over 50 ms and no stand-in
  at all.
- **A far jump while filling**, on a line held to 20 Mbit/s: the background download stopped in
  the same instant the summit started loading. The summit was ready 5.8 s after the key and the
  ink cleared at 16.5 s, the same as before.
- **One strike**: see "Who gets it".
- **The picture**, old build against new with everything in (pixels that differ by more than 12
  levels): the gate 0.003 percent, the mission hall 0.12, the library 0.42, the abode none. At the
  mission hall and the library that is the places now drawn in full.

## Not checked for the filling, and its rough edges

- **A visitor who scrolls at once gains little at first.** A background place's parsing waits for
  a rest, so at most one place runs ahead of a steady scroll. The seven places past the gate's
  window are 75 MB to download: 8 s on localhost, about 30 s at 20 Mbit/s.
- No real slow GPU, no card with little memory, no real slow line, no Firefox or Safari.
- Chrome calls a line "4g" from about 0.7 Mbps up. Such a line fills too. A needed place still
  never waits, so the cost is data. A full flight downloads the same files anyway.
- A jump stops a background download and it starts again from zero later.
- A background place whose bytes are already in when fast travel starts is prepared under the ink,
  and the ink can stay up that much longer (a prefetch does the same today). Not seen in the check.
- The page wiring (`fillOpen` after Enter, the strike) has browser checks only, no unit test.
