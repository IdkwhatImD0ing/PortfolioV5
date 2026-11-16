# A smooth flight: what stuttered on the real visitor path, and what was done

Added 2026-11-14. The first round is in [`live-gate.md`](live-gate.md), "Lighting a stop without
freezing the page": it removed the freezes on shader programs. This is the second round.

## The measure

Every earlier timing used `?ui=0`: no interface, no loading screen. A visitor uses the real page.
So the measure from here on is the **visitor flight**, on a production build:

- load `/?tier=high` with the interface on, wait until Enter is enabled, wait 1.5 s, click Enter;
- rest 12 s, 80 wheel steps of 380 px 120 ms apart, rest 10 s, the same 80 steps back, rest 10 s;
- 1600 x 900.

It counts blocking shader waits (a call that blocks the page on a shader program for over 16 ms),
frames over 50 ms and over 100 ms, the worst frame, and "stall": the time lost in frames over
50 ms. Warm means a repeat load. Cold means a fresh browser with an empty profile, which is what a
first-ever visitor has. Cold was proven each time: shader programs took 6 to 10 times longer to
become ready.

A production build is made in a separate copy of the code, since `pnpm build` must not run beside
the dev server.

## What the diagnosis found

On the code before this round, over six production flights:

1. **Texture uploads on the main thread: about 2.2 s of stall per flight, 38 slow frames.** Each
   4096 px map went to the GPU in one call that blocked for 25 to 50 ms. A flight did 63 to 80 of
   them.
2. **The browser's GPU process: about 1.1 s per flight, 8 frames.** In these frames the page runs
   no script and makes no WebGL call. It waits. Traces show the graphics driver building shaders
   (turning cached programs into D3D11 shaders, about 230 ms each, or compiling from scratch, up to
   1.25 s each) while the frame's present waits for it. A flight linked 32 programs: 19 on the way
   down and the same 13 again on the way back. In a new browser session this gave frames of 0.4 to
   1.6 s right after Enter and at the start of the scroll.
3. **Main-thread script: about 0.75 s per flight, 14 frames.** Decoded images handed over on the
   main thread (10 to 14 ms per 4096 px map), mesh preparation, the grass build, the interface
   mounting on Enter.

## What changed

**The GPU side**

- **One queue for GPU jobs** (`client/src/lib/sect/gpu-queue.ts` holds the rules,
  `experience/gpu-queue.ts` runs them). Texture uploads from the sets' warm-up and from live light
  go through it. One step per display frame. None while the GPU is still working through the last
  step (a fence that is polled, never waited on) or while a shader program is linking, unless that
  has held the queue for 1.5 s.
- **Big maps go up in bands.** A 4096 px map goes up 512 rows at a time, about 2 ms a band, from
  the same decoded image, and its mipmaps are made after the last band. The texels are the same as
  one upload gives. Only maps whose sides are powers of two go in bands: on a 2048 x 1760 tree map
  the driver made different small mip levels after a banded upload, and far trees showed speckles.
  Those maps go up whole, as before.
- **Enter waits for the first stop.** Enter stays grey until the first stop is finished behind the
  loading screen: its sets drawn, its programs built, live light lit, the queue empty. The wait is
  capped at 6 s (`ENTER_SETTLE_MS` in `sect-experience.tsx`).
- **Programs are kept for the page** (`program-prime.ts` `keepPrograms`). A set that is dropped and
  loaded again builds nothing. The way back links no program (13 before).
- **The fire, the incense and the formation's glow are built before they first show** (`fx.tsx`
  `usePrimed`). three skips hidden objects when it compiles ahead, so their first frame blocked.
- A production build skips three's shader error checks, which cost extra blocking calls on a
  program's first use.

**The main thread**

- **Images are decoded and handed over in a worker** (`experience/bitmap-decode.ts`). It is three's
  own loader with the decode moved, with the same options, and it falls back to the main thread if
  the worker does not start. It takes an optional abort signal (the live light's maps use it): the
  download stops, and an image decoded too late is closed.
- **Big jobs are cut smaller**: the vertex colour repair, the built-mask grow (it redoes only the
  cells that changed, and gives the same mask), the grass steps, the mesh decoder's hand-off.
- **A tier change gives its memory back.** Page-level textures and the shadow depth materials each
  held a listener from every renderer that had used them, which kept old renderers alive. They are
  released when the canvas goes.
- **A lost graphics context recovers by itself.** 1.5 s after the error screen shows, the page
  loads again in place, at the stop the visitor was at or flying to, at most twice per visit.

## What it measured

Production builds, the visitor flight, old and new code taking turns, no game running. The checker
ran these. Each cell is frames over 50 ms / frames over 100 ms / worst frame.

| | Old code | New code |
|---|---|---|
| Warm, 4 flights each | 29/4/248 ms, 39/3/225, 31/2/112, 33/3/152 | 4/0/73 ms, 5/0/78, 5/0/85, 4/0/88 |
| Stall per flight, warm | 1.6 to 2.0 s | 0.18 to 0.27 s |
| Cold, 3 flights each | 26/0/99, 29/1/120, 27/1/105 | 3/0/67, 2/0/81, 2/0/60 |
| Stall per flight, cold | 1.2 to 1.3 s | 0.08 to 0.13 s |
| Programs linked in a flight | 34 | 12 or 13, all on the way down |
| Uploads over 10 ms in a flight | 54 to 59, worst 38 ms | 10 or 11, worst 13 ms |
| Mid tier | 5/1/106 | 0/0/49 |
| Low tier | 2/2/1414 | 1/0/60 |
| Enter enabled, warm | 1.4 to 2.0 s | 3.6 to 5.0 s |
| Enter enabled, cold | 2.1 to 2.2 s | 6.4 to 6.5 s |

In plain words: the old flight hitched about 30 times each way and sometimes froze for a quarter
of a second. The new one hitches 2 to 5 times, by 60 to 88 ms at most, mostly where the scroll
starts. No new-code flight had a blocking shader wait (14 of 14).

**With the scroll snap joined in** ([`scroll-snap.md`](scroll-snap.md)), one more pair in one session:
the old code had 33 frames over 50 ms, 9 over 100 ms and a worst frame of 1.17 s; the joined code had
1 frame over 50 ms (67 ms) and none over 100 ms. The final build repeated that (1 frame, 78 ms). A
tour of one wheel click per scene had no frame over 50 ms.

**The picture.** With motion frozen, lossless captures at the 11 stops on both builds: eight stops
differ by 1 to 7 steps of 255 at most, the rest by a handful of pixels that two captures of the
same build also differ by. Mid-flight captures show no area late and no texture half filled.

**Nothing grows.** Over three trips to the summit and back, programs settle at 92 and textures at
88. After High to Low to High, one renderer is alive (seven before) and memory stays at 266 to
278 MB (it grew from 257 to 337 MB before).

## Round 3: the queue's pace follows what the visitor can see

Round 2 left two costs: a loading screen 2 to 4 s longer, and places that showed their stand-in
models for seconds after a fast arrival. Both had one cause. The queue paced itself the same way
whatever the visitor could see.

- **Three paces** (`GPU_PACE` in `client/src/lib/sect/gpu-queue.ts`; `sceneView` in `store.ts`
  says which one applies, every frame):
  - *moving* (the camera flies, glides or catches up with the scroll): as before. One small step a
    frame, none while the GPU is busy or a program links.
  - *resting*: about 7 ms of steps a frame, and a linking program does not hold the queue. Only for
    work the visitor is waiting to see: the place on screen, the place the camera is heading to,
    live light starting at the stop. Work loaded ahead keeps the moving pace, so a camera resting at
    a finished place does not hitch for what is not on screen.
  - *veiled* (the loading screen, fast travel's ink): most of each frame, held by nothing.
- **Behind the loading screen the rest of the loading work takes bigger slices too**: model
  preparation, the idle plan and the grass build get 24 ms a slice instead of 5 or 6. The areas the
  first stop waits for load side by side, up to four at once. The check that nothing is changing
  before Enter is 150 ms instead of 400 (`SETTLE_GATE` in `lib/sect/settle.ts`).
- **A set's programs build while its textures upload**, once the camera is still. The place the
  camera is heading to uploads first (`setUploadPriority`).
- **The hold-focus blur is built behind the loading screen** (`post/atmos.ts`
  `HoldFocusEffect.prime`). Its two programs used to freeze the frame for 0.46 to 0.8 s the first
  time the camera rested at a stop after Enter.
- **A key step begun while the camera moves keeps the camera's speed** (`lib/sect/snap.ts`
  `planCarry`), so it no longer stops dead and starts again.

**What it measured.** The checker, on production builds, each build in its own browser profile, as
a visitor has:

| | Round 2 | Round 3 |
|---|---|---|
| Enter enabled, repeat visit, High | 3.75, 3.78, 3.97 s | 3.10, 2.99, 2.96 s |
| Enter enabled, first-ever visit | 6.54, 6.72 s | 4.60, 4.59 s |
| Enter enabled, Mid / Low | 3.37 / 1.97 s | 2.55 / 1.55 s |
| Flights with a frame of 100 ms or more | 4 of 9 (up to 3.3 s) | 0 of 9 |
| Worst frame in the first 1.5 s of the scroll | 272 ms in one run | 42 to 63 ms |

- After four fast flights to the summit, 96 landings of click tours and the key tours, every place
  was drawn in full when the camera stopped.
- Fast travel's ink cleared 0.2 to 0.35 s sooner.
- A key pressed during a glide kept the speed (81 before, 82 units a second after) and landed on
  the right stop.
- Nothing grows: 94 programs (92 plus the blur's 2) and 88 textures after three trips. Tier changes,
  interrupted starts and a lost graphics context all came back lit.

**Four things to know about these numbers.**

- With the two builds taking turns in one browser profile, the new one's Enter came later in 2 of
  4 pairs (6.9 s against 5.9 s, 6.2 s against 4.9 s). The other build's run had pushed its cached
  shaders out. A visitor has one build, so the table above uses separate profiles.
- The first stop's wait now also covers one more area's download. On localhost that is free. On a
  slow line it could make Enter later (the 6 s cap still holds). Not measured with a slowed network.
- At the forge, 56 pixels on the far pagoda differ in every capture of the new code, by up to 31
  steps of 255. It cannot be seen at normal size. The code before can give the same picture (it did
  on one of its two servers). Putting all of round 3's timing changes back at once removes it, no
  single one does. The reading, not proven: where two surfaces sit at the same depth, the order
  things were created in decides which shows, and faster loading changes that order.
- During a key flight leaving the steles, the pagoda ahead has a lighter roof and more orange walls
  in the new code, in 5 of 5 runs. With live light off the builds match. Not explained. The likely
  cause is that the next stop's live light now comes on sooner, because its maps are ready sooner.
  At rest every stop matches.

## Round 4: the test browser was part of the problem

After round 3 the first load in a browser that had just been started still froze in the timing
runs: 0.4 to 1.9 s after Enter, then several frames of 0.3 to 1.2 s in the first seconds of the
scroll. Repeat loads were smooth. Round 4 traced those freezes.

- **They belong to the test browser.** Nearly all the timing in rounds 1 to 3 was taken in one
  Chrome, the one the Playwright tool drives. For every shader its GPU process meets for the first
  time, that browser needs 0.1 to 1.9 s. Every other Chrome started on the same PC needs 0.1 to
  0.3 ms for the same shaders, and the page's own programs become ready 5 to 10 times sooner. A
  copy of the test browser's whole profile in another folder, with the same window size and flags,
  was smooth. So it is that browser instance, most likely the graphics driver's shader cache for
  it. Why is not known.
- **What froze was not the scene.** In the traces the long frames were Chrome drawing the page's
  HTML interface (the links, the rails and the map button mounting after Enter, a stop's panel
  fading in, the rail's marker moving), each waiting for the driver to turn a cached shader into a
  D3D11 one.
- **In a normal Chrome the first load of a fresh session is smooth.** The code after round 3 had
  no frame of 100 ms or more in 8 of 8 runs there (worst 49 to 67 ms).
- **What this means for rounds 2 and 3.** The waiting "on the browser's GPU process" they
  reported (about 1.1 s per flight in the round-2 diagnosis, and the freezes after Enter in a new
  session) was measured in that browser and is far smaller elsewhere. What those rounds fixed on
  the page's own thread is real in any browser: uploads of 25 to 50 ms, the image hand-over, the
  preparation work.
- Round 3 did make the test browser's fresh sessions worse than round 2: its earlier Enter leaves
  that browser's driver still catching up when the interface appears.

**From here on, timings are taken in a Chrome started for the run on its own profile.** Numbers
from the tool's own browser are named as such. The scripts are in `.playwright-mcp/survey/perf5_build/`
and `perf5_check/` on the PC that ran them.

**Drawing ahead: built, measured, set aside.** Before an area is marked ready, each of its meshes
is drawn once into a 16 px off-screen buffer of the composer's kind, a few per step of the GPU
queue, so the driver does a first draw's work ahead and every vertex buffer is on the GPU before
the area shows. In normal Chromes a flight then had no frame over 50 ms in 6 of 6 runs, against 1
or 2 frames of 50 to 64 ms without it. That is too small to see, and it has costs: about 25
percent more GPU buffers stay loaded (3641 against 2915 at the gate), and after a renderer is
rebuilt the live light comes back 2 to 5 s later. It did not remove the test browser's freezes
either. It is not merged. It is kept on the branch `claude/saltline-draw-ahead`, in case first
draws turn out to hitch on weaker GPUs.

**Enter on a slow line.** A first visit with the network slowed, first picture ready and then Enter
enabled:

| Line | First picture | Enter |
|---|---|---|
| 50 megabits a second | 5.5 s | 11.5 s |
| 20 megabits a second | 11.1 s | 17.2 s |
| 5 megabits a second | 35.2 s | 41.2 s |

In every case Enter came exactly 6.0 s after the first picture. That is the cap on the wait for
the first stop's neighbours, which are still downloading. Rounds 2 and 3 are the same here. On
localhost, where a download takes no time, this never showed. A repeat visit (files cached) gets
Enter at 3.4 to 3.5 s on any line.

**The lighting difference in the middle of a flight** (round 3's check) is not the next stop's
live light coming on sooner: both builds stop lighting the steles at frame 1090 to 1092 and start
the pavilion's light at 1103. It showed in 1 of 5 captures this round against 5 of 5 before. The
guess, not proven: in those captures the pavilion's own area was not ready yet and its stand-in
was drawn.

## Round 5: Enter does not wait for bytes that are still on the way

Round 4 had found that on a real line a first visit waited exactly 6 s between the first picture
and Enter. The loading screen was waiting for the first stop's neighbours and its live maps, which
were still downloading, so the wait always ran to its cap. No local work was holding it.

- **The first stop's wait now covers work on what has arrived.** Preparing an area, its uploads
  and shader links, the grass, live light starting from maps that are here: all of that still holds
  Enter, under the 6 s cap. A file that is still downloading holds it for at most 0.5 s
  (`arrivingMs` in `SETTLE_GATE`, `client/src/lib/sect/settle.ts`; `chunkArriving`, and
  `liveArriving` in `lib/sect/live.ts`, say what is still on the way). On localhost every file
  arrives well inside that half second, so nothing changes there.
- The detail texture's one-second fade no longer holds Enter. A fade is not work.
- At the first stop the areas download one at a time, nearest first, as everywhere else (four ran
  side by side since round 3). The nearest neighbour arrives first. Up to four can still be
  prepared at once.
- Fast travel's wait is unchanged: its ink hides the place until all of it is there.
- **A freeze this uncovered, fixed.** With Enter coming sooner, a visitor on a slow line can scroll
  past an area whose shaders are still being built. The stream then dropped the area and deleted
  those shaders, and deleting a shader the driver is still building makes the browser's GPU
  process wait for it: the page froze for 0.66 to 0.81 s, in 5 of 5 runs at 50 megabits a second.
  An area's programs are now kept for the page from the moment they start building, not only once
  they are ready (`scene.tsx`, the World warm-up's `keepPrograms`). After that the worst frame in
  the same runs was 46 to 49 ms.

**What it measured.** A normal Chrome, a new process and an empty profile per run, the network
slowed through CDP (the line really carried 46, 19 and 4.9 megabits a second). First picture, then
Enter, in seconds from the start of the load:

| Line | Before | Now |
|---|---|---|
| 50 megabits a second | 5.5 then 11.5 | 5.5 then 6.2 |
| 20 megabits a second | 11.0 then 17.0 | 10.9 then 11.6 |
| 5 megabits a second | 35.0 then 41.0 | 34.9 then 35.6 |

- Enter comes 0.66 to 0.68 s after the first picture on every line.
- After Enter on a slowed line, resting or scrolling at once, none of 7 runs had a frame of 100 ms
  or more (worst 46 to 68 ms). Places that have not arrived show their stand-in models until they
  do, as they did before round 2.
- The first stop's live light fades in when its maps come (1.2 s, a few seconds after Enter at 50
  and 20 megabits), it does not pop.
- With no slowing, Enter is at most 0.24 s later than before (cold 4.5 s, repeat visit 3.4 s), and
  flights are as they were: no frame of 100 ms or more, the worst 60 ms on both builds.
- The picture is unchanged, and tier changes, interrupted starts and a lost graphics context all
  still come back lit.

## What is left

- **The loading screen is still about 1 s longer than before round 2** on a repeat visit (3.0 s
  against 1.4 to 2.0 s) and 2.4 s longer on a first visit (4.6 s against 2.1 to 2.2 s), where
  building the first stop's shaders from scratch sets the floor. On a reload the first frame alone
  waits 0.3 to 1.3 s for 17 programs (the sky, the clouds, the screen effects); building those
  ahead is the next step for a repeat visit.
- **Slow lines beyond what round 5 measured**: the Medium and Low tiers, phones, and the real
  host (which serves over HTTP/2; the tests ran on localhost over HTTP/1.1 with Chrome's own
  slowing). At 5 megabits a second the first picture still comes from the stand-ins after a 25 s
  timeout, and the first stop's live light only comes on about half a minute after Enter.
- The mid-flight lighting difference and the forge's 56 pixels (see round 3) are open.
- The 12 programs of the way down are still built while the camera moves. In some flights one
  frame of 0.2 to 0.7 s follows them, with no script in it.
- A mesh's vertex buffers still go up on its first draw: about 26 frame tasks over 12 ms per
  flight, 28 ms at worst.
- About ten maps per flight still go up whole (sides not powers of two), 10 to 13 ms each.
- At the forge, 1 capture in 10 showed 57 speckled pixels on far trees (up to 30 steps), the same
  ones the banded upload caused before it was limited. Not explained. The old code showed none in
  4 captures.
- With reduced motion, a blur shader still blocks for about a second at the start. Not looked at.
- Two small gaps in the queue: an upload step that throws is counted as done (three then uploads
  the map whole on first draw), and a decode worker that crashes in the middle of a job loses the
  images it was decoding.

Scripts, raw numbers and sheets are on the PC that ran them, under `.playwright-mcp/survey/`:
`perf3_diag/` (the diagnosis), `perf3_gpu/`, `perf3_main/` and `perf3_check/` (the independent
check).
