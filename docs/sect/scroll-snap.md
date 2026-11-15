# Scroll snap: never stuck on a scene, pulled in when you stop near one

Added 2026-11-14.

## Why

The owner: "Right now, there's this thing where each scene will stop for a second when you scroll
onto it, right? So when you're fast traveling between scenes, it gets stuck on scenes and it feels
weird. But at the same time, we should like snap to a scene."

Both halves came from one cause. A stop was a place in the scroll, not a moment:

- Every stop had a dead stretch of 42 scroll units where the camera did not move at all. On a
  1080 px screen that is about 750 px of scrolling, 5 to 7 clicks of a mouse wheel.
- Each leg was eased, so the camera fell to 45 percent of its speed going into a stop and coming
  out of it.
- And nothing brought the camera to a stop. Scrolling that ended between two scenes left it
  there. Only a touch flick glided on to a stop (`flickStop`).

So the rule now is: stopping depends on when the visitor stops scrolling, not on where the scroll
position is.

**The same day, after trying it.** The first version glided to a stop after every rest, so one
wheel click flew on to the next scene and the camera could never rest between two. The owner: "I
think the snapping is too agggressive riht now, what if the user wants to sit in between a scene
and look atound the map". So the snap is now a gentle one: the camera stays where the scrolling
rests, and is pulled on to a scene only when the rest is close to it. What follows describes the
gentle version; what the first one did is noted where it differs.

## What changed

1. **No dead stretch.** `FLIGHT_SCROLL` in `client/src/lib/sect/scroll-map.ts` went from
   `{ dwellUnits: 42, ease: 0.55 }` to `{ dwellUnits: 1, ease: 0 }`. A stop keeps one unit (18 px
   on a 1080 px screen), so "the camera is inside a hold zone" still means it is at the stop, and
   a scroll position a few pixels off still shows exactly the hold frame. No easing, because the
   film's own camera already slows into six of the eleven stops (a quarter to 70 percent of its
   mid-leg speed at the gate, the mirror, the forge, the mission hall, the jade slip and the
   summit), and easing on top made those drag.

   Scrolling past the gate at a steady 20 units a second, the camera used to stand still for
   2.08 s and keep 23 percent of its speed around the stop. Now it stands still for 33 ms (two
   frames) and keeps 95 percent.

   The page is a fifth shorter: 1713 units against 2164, about 29 screens against 36.
2. **A glide when the scrolling rests near a scene.** After 180 ms with no scroll from the visitor
   and no finger down, a camera close to a stop glides on to it and the page scroll is put there
   (which stop, and how close, is the next section). Further off it stays put. One mechanism for
   the wheel, a trackpad, touch, Space and the scrollbar (any scroll the page did not make
   itself). It replaces the touch-only flick code.

## Which stop, and when it stays

`snapTarget` in `client/src/lib/sect/snap.ts`, a pure function. It is given the stops (the start,
every hold's middle, the end), where the scrolling came to rest, and where this stretch of
scrolling began (the position at the last rest). It answers with a stop to glide to, or with
nothing: the camera stays where it is.

- **Between two scenes: it stays.** The visitor can sit there and look around.
- **A little before the scene ahead: on to it.** "A little" is the last 16 percent of the leg
  between the two stops, and never more than 32 scroll units (`SNAP.reachAhead`,
  `reachAheadMax`).
- **A little past a scene that was passed in this stretch: back to it.** An overshoot of up to
  10 percent of the leg, never more than 20 units (`reachBack`, `reachBackMax`).
- **Leaving a scene is free from the first wheel click.** The stop a stretch began at never pulls
  the camera back, whatever the distance.
- **A nudge settles back.** Moved less than 60 px of page scroll off a stop (`commitPx`, less than
  one click of a mouse wheel): back on to that stop. A nudge between scenes stays.
- Before the first stop or past the last: that stop. Within half a unit of a stop: nothing to do.
- **Looking around.** While the visitor drags the view, the snap waits until the drag is let go
  (`sect-experience.tsx`, the rest handler).

So a wheel click no longer travels a scene. The arrow keys, PageDown, J and K, the rail and the
map still go from scene to scene.

The reach numbers are a first guess, to be tuned by how it feels.

The first version had no "stays": moved 60 px or more, it glided to the next stop in the direction
of travel, and an overshoot under 35 percent of the leg came back.

## The glide

When the snap begins the camera is usually still moving. A glide that started from rest would
stop it and start it again. So the glide is a curve that starts at the camera's own speed and ends
with no speed and no acceleration (`planGlide` and `glideAt`, a quintic). The camera rig in
`scene.tsx` keeps the camera's speed in `store.speed` every frame for this.

- It takes 0.45 s plus 0.08 s times the square root of the distance in units, at most 2.8 s:
  1.25 s to the next stop on the shortest leg, 1.75 s on the longest, about half a second for a
  nudge that settles back.
- A camera already heading for the stop faster than that gets a shorter glide, so it never runs
  past the stop and comes back.

Flights from keys, the rail, links and the map keep their old ease-in-out curve.

## The visitor always wins

- Any input during a glide or a flight ends it at once. The page scroll is put where the camera
  would coast to at the speed it has (`coastTarget`), never past where the flight was going, and
  the visitor's scrolling moves on from there. Before, the scroll sat at the flight's end, so the
  camera jumped ahead toward it.
- The browser drops the wheel click that arrives while the page moves the scroll. So during a
  flight the page cancels that one click and applies it itself (`wheelPixels`). For this the wheel
  listener is not passive. That costs nothing here: the camera follows the scroll through the
  rig's damping, never through the browser's own scrolling.
- The page's own scroll moves never count as the visitor's (`instantScrollTo` marks them,
  `takeOwnScroll` reads the mark). Without that, arriving at a stop would start the next glide.

## When it does not snap

- Before the flight has started. If the visitor scrolled on the loading screen, the camera glides
  to the nearest stop right after the start.
- With reduced motion, which has its own stops.
- While a `?frame=` view is held, or a flight from a key or a link is under way.
- While a reader, the map, fast travel's ink or the page view is up, or a far jump is gathering:
  the snap waits and happens when that is gone.

Two things changed around it:

- `AT_HOLD_UNITS` went from 30 to 2. With stops this short, 30 units is 28 frames from the stop,
  and a click on a place in the moment before a snap would have opened its reader over a view
  between two scenes.
- A panel's Open button, clicked while a glide is leaving that stop, opens the reader when the
  camera arrives if the glide is going there, and otherwise flies back first (`openFromPanel`).

## What was checked on the gentle version

- The rule is unit-tested on the real camera path: free between scenes, pulled in before a
  scene (down and up, and the cap on the longest leg), a small overshoot brought back, the scene
  being left never pulling back, a nudge settling back, the ends, and a sweep over the whole track
  that finds most rests free and every glide short.
- On a production build in a browser: one wheel click from the top stayed where it was (100 px).
  Resting at 780 px, just short of the gate at 851 px, glided on to the gate. One click on from the
  gate stayed at 951 px, with no flight to the mirror and no pull back.
- The 13 browser cases below were run on the first version. Those about the glide, taking over,
  readers, keys and deep links use code the gentle version did not change. Those about where a
  rest lands (one click to the next scene, the click tour) describe the first version only.

## What was checked on the first version

One agent built it and a second one checked it. The second ran 13 cases in a browser and then
tried to break it. All pass:

- One wheel click from the gate lands on the mirror, exactly on frame 217, 1.8 s after the click.
  One click back lands on the gate. A 20 px nudge settles back.
- 45 clicks about 68 ms apart: the camera never stood still, kept 98 to 100 percent of its speed
  through the mirror and the forge, and landed on the stop the rule names 1.6 s after the last
  click.
- Resting 16 percent past a stop glides back to it.
- A click during a glide ends it at once, and the page then leaves the scroll alone until the next
  rest. After arriving nothing moves for 5.5 s.
- A scroll with no wheel event (as from the scrollbar) snaps the same way.
- With a reader or the page view open, scrolling is put back and nothing glides.
- Keys, the rail, the map's fast travel, Home, End and a deep link (`#skills`) land where they did.
- Every stop rests on exactly its hold frame.
- Quick back-and-forth scrolling, scrolling in the first second, resizing during a glide, opening
  a reader during a glide, touch and Space.

The check found and fixed four bugs: a click lost after scrolling back and forth, a lunge when the
scrollbar was used during a glide, a reader opening over the wrong place, and a camera left
between stops after scrolling on the loading screen.

On a production build, one wheel click from the top landed on the gate (66.5 units) and the next
on the mirror (191.5 units).

**In a real window.** After the snap was joined with the smoothness round (
[`smooth-flight.md`](smooth-flight.md)), a production build was driven with real wheel events, the
interface on, through the loading screen:

- A tour of one wheel click per scene, twelve down and twelve back, 3.2 s apart: every click landed
  on the next scene in order (gate, mirror, forge and on to the end, then back), with no frame over
  50 ms (45 ms at worst) and no blocking wait.
- A continuous scroll down and back: one frame over 50 ms (67 to 78 ms, where the scroll starts),
  none over 100 ms.

In development the rig writes `window.__sectScroll` (`u`, `targetU`, `frame`, `speed`, `flight`,
`glides`, `t`) every frame, for checks like these. It is not in a production build.

## Not checked, and rough edges

- **How it feels.** The checker's browser pane was hidden, so its frames were driven from a timer
  with drawing off. The click tour and the scroll above were timed in a real window afterwards,
  but whether the glide feels right is the owner's call.
- Real touch devices (on iOS the page moving the scroll at touch start may fight momentum
  scrolling), a real trackpad's momentum, and Chrome's own smooth wheel scrolling.
- A pull on to a scene starts about 0.2 to 0.4 s after the scrolling stops (the browser's own
  scroll plus the 180 ms rest).
- A click the other way during a glide works, but the camera drifts on for about 0.3 s before it
  turns.
- An overshoot runs about 20 frames past the stop before it settles back, because the camera is
  still catching up with the scroll when the rest comes.
- A key pressed during a glide used to stop the camera dead. It now keeps the camera's speed
  (`planCarry`, round 3 in [`smooth-flight.md`](smooth-flight.md)).
- During a flight or a glide, a wheel turn over a scrollable panel that is not a reader (the
  lyrics list) scrolls the flight, not the list.
- Scrolling on the loading screen still overrides a deep link. That is older than this change.
