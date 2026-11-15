# Every place loads in the background on a strong desktop

Added 2026-11-15.

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
So the page now holds everything and still draws by the same rule. Drawing far places in full is
not built. It could become the first thing the quality ladder turns off, if the owner wants it.

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
- One strike: the first step down the quality ladder ends it for that page view. The page drops
  back to the window (2,241 MB to 867 MB in a quarter of a second when tried) and a step back up
  does not bring the filling back. Slow frames are the only sign of short GPU memory a page gets.

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

## What was checked

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

## Not checked, and rough edges

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
