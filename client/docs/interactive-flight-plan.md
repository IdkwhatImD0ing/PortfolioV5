# Interactive flight: implementation plan

Status: plan, not started. Written 2026-10-10.

## The idea

The site becomes a flight through the sect (then the Ming Sect, now the Sun Moon Divine Sect). Scrolling moves the camera. When the
camera reaches an area, the things in the video become clickable: the 15 floating
artifacts at the forge are your 15 projects, the 7 jade tablets are your 7 jobs, and so
on. Clicking one opens the same detail view the site already has. It works in reverse
too: hovering a project card makes its artifact glow in the video, and when the voice
agent talks about a project, the camera flies to the forge and that artifact pulses.

This works because the Blender scene knows where every object is in every frame. We
export that as a small data file, and the website places invisible buttons on top of the
video that move with the objects.

The camera doesn't fly alone. It follows a **flyer**: a cultivator riding a flying
sword, seen from behind, like a third-person game. The viewer travels with someone
through the sect.

## The flyer (third-person chase)

> **Dropped 2026-10-12.** The generated flyer looked bad in every take, so the film is now a
> pure camera fly-through with no people. This section is kept for history; ignore it when
> building the site. Each clip ends settled on its area's view, which is where the section
> content appears.

**Look.** A cultivator standing on a flying jade sword (御剑飞行), with purple robes
(deep violet with lilac sash ribbons, matching the site's purple; decided 2026-10-10, not
the user's likeness), long sleeves and hair ribbons streaming back, and a thin cyan light
trail behind the sword. Purple stands out against the red-and-teal buildings, the green
forest and the grey rock.

**Framing.** The camera sits about 7 m behind and 2 m above. The flyer is in the lower
centre of the frame, about a sixth of the frame tall, so they never hide what's ahead.
At each area's hero moment the camera swings out to a three-quarter side view, so the
focal object (the cauldron, the tablets, the scroll) is beside the flyer and not behind
them.

**One path for both.** The flyer flies the main path. The camera rides the same path
about 0.3 s behind, raised by the offset, and aims just ahead of the flyer. The path is
already checked for collisions, so the camera stays safe automatically. The flyer needs
2 m of clearance and the camera 5 m. Turns feel natural: the camera swings wide behind
the flyer the way a drone chasing a skier does.

**Tested 2026-10-10** (`blender/xianxia-sect/sect/flyer.py` and `sect/chase.py`,
video `out/video/chase_blocking.mp4`):

- *Pure chase* (the camera always behind, looking where the flyer goes) missed 7 of the
  11 areas. The old path looked sideways at them while flying past.
- *Second try, rejected by you:* the flyer hovered facing each area while drifting with
  the camera. That read as flying backwards, and it sat dead centre most of the time.
- **Current rig (orbit camera):**
  - The flyer always flies the route nose-first: its heading is its direction of travel.
  - The camera decides where to *look*: ahead along the route while travelling, swinging
    toward each area's designed view near its hero frame, never more than 70° from the
    flyer's heading. It then places itself 13 m back so the flyer sits on a third line:
    lower left by default, lower right when the camera looks left.
  - It is pushed out of geometry the same way the fly-through camera is.
  - Result: the flyer is never lost from frame, and it only passes the centre while
    sliding between thirds.

**Your rules for the flyer** (from review):
- The flyer is never dead centre by default.
- The flyer always flies forward.

**Each area becomes a manoeuvre**, choreographed so the flyer's direction of travel
shows the focal object:

| Area | Flyer's move |
|---|---|
| gate | bursts out of the cloud, races up the stairway, flies through the centre bay |
| mirror | glides low across the pond, the flyer reflected in the water and the mirror |
| forge | circles the cauldron *through* the ring of floating artifacts |
| arena | skims the dueling floor between the banner rows, past the giant sword |
| mission | rises up the face of the mission wall past the 7 jade tablets, over the roof |
| library | corkscrews up around the pagoda through the drifting scrolls |
| steles | low and fast down the aisle between the glowing steles |
| scroll | glides along the face of the giant jade scroll, reading it |
| formation | dives toward the glowing core, then pulls up along the light pillar (the circuit diagram reads below during the dive) |
| abode | through the waterfall spray, past the balcony and the moon gate |
| summit | rises past the pavilion and keeps climbing toward the moon; the last frame is the flyer's silhouette against the moon |

**Blender work** (part of phase 1):

- `sect/flyer.py`: a blocking mannequin built from simple shapes, with robe, sleeves,
  ribbons, sword and light trail. It leans forward with speed and banks into turns,
  the robe ripples, and it has small pose changes at hero moments (it turns its head
  toward the object; at the forge it reaches toward the artifacts).
- `camera.py` switches to chase mode: a new flight route made of the manoeuvres above,
  the camera on a time delay behind the flyer, the same speed and acceleration limits,
  and the same 8 clips of 12 s or less.

**On the website:** the flyer counts as an obstacle when checking whether a hotspot is
hidden. Its own screen box is exported, so tooltips never sit on top of it. The flyer can
be clickable too ("that's me", which starts the voice chat), which is a nice touch if the
flyer is you.

**In Seedance:** every clip gets the same character reference image and the same
character description, and the clips are chained by last frame. That keeps the flyer
looking like one person across all 8 clips.

## How it works

```
Blender scene (sect.blend)
  ├─ render ─────────────► video frames ──► flight video (desktop) / image frames (phones)
  └─ export_tracks.py ───► tracks.json: for every clickable object, its box on screen
                           in every frame, and whether it's hidden behind something

Website
  scroll position ──► timeline.ts ──► "show frame 402" ──► player seeks the video
                                          │
                                          └──► hotspot layer moves buttons to where
                                               tracks.json says the objects are in frame 402
  click a button ───► the same VoiceBus command the voice agent uses ("open project X")
  hover a card ─────► FlightBus.highlight("project:X") ──► glow drawn over the artifact
```

## What you can click in each section

Ids in the right column are hotspot ids. Each one maps to a real item in
`src/lib/portfolio-data`.

| Section | Area | Clickable things in the video | What clicking does |
|---|---|---|---|
| hero | Mountain Gate | the gate plaque (then 明教, now 日月神教) | scroll on to About |
| about | Heart-Mirror Terrace | the bronze mirror | your About text appears *inside* the mirror (projected onto its surface) |
| projects | Artifact Forge | 15 artifacts, `project:<id>` | opens the existing ProjectDetail modal; hovering a project card lights its artifact |
| hackathons | Sword Arena | 36 banners, `hackathon:<i>` | shows name, project and prize; scrolls its card into view |
| experience | Mission Hall | 7 jade tablets, `role:<i>` | the role and company are projected onto the tablet; click expands that experience row |
| education | Scripture Pagoda | 3 lit floors, `school:<i>` | flips that school's card |
| skills | Stele Forest | steles grouped in 6 colours, `skills:<group>` | highlights that group's words in the skills line |
| resume | Jade Slip Pavilion | the giant scroll | resume preview projected onto the scroll; click opens the PDF |
| architecture | Grand Formation | the nodes and light beams, `arch:<step>` | opens that step's explanation (Mic input → LLM agent → Tool calls → VoiceBus → Sections react → Voice reply) |
| personal | Cave Abode | 8 objects (tea table, crane, waterfall, koi pool, bamboo, peach tree, wind chimes, moon gate), `fact:<i>` | reveals that personal fact |
| footer | Moon Summit | the moon | starts a voice call with your AI ("talk to me") |

## Architecture

### 1. One list of ids, shared by the site and Blender

The website's data is the source of truth. A generator writes
`blender/xianxia-sect/scene_ids.json`, which lists project ids, the 36 hackathons, the 7
roles, the 3 schools, the skill groups, the architecture steps and the 8 personal facts.
Blender reads it, so object counts always match the data.

- The generator is a vitest test, `src/lib/flight/scene-ids.test.ts`, so it can use the
  site's `@/` imports with no new tooling. Normally it fails if the JSON is out of date;
  run it with `UPDATE_SCENE_IDS=1 pnpm test` to rewrite the file.
- **New data needed:** `SKILL_GROUPS` in `skills.ts`, about 6 groups (for example
  Languages, Frontend, Backend, AI/ML, Voice and realtime, Cloud), each with its words and a
  colour that matches its steles.

### 2. Blender changes (`blender/xianxia-sect`)

1. **Tag clickable objects.** Each area sets a custom property on its clickable objects:
   `obj["hotspot"] = "project:dispatchai"`. Flat surfaces that receive projected content
   (mirror face, giant scroll, tablet faces) get `obj["surface"] = "<id>"`.
2. **Make the counts match the data:**
   - arena: one banner per hackathon (36, not 40)
   - formation: rebuild the 8 nodes as the 6 real architecture steps, plus the stack as
     satellites, linked in the same order as the diagram on the site
   - steles: assign the 20 steles to the 6 skill groups and colour them to match
   - abode: tag the 8 objects to the 8 personal facts
   - forge: assign artifacts in `PROJECTS` order. Optionally pick each artifact's shape to
     suit the project (a bell for a voice project, a compass for a navigation one).
   - Build 3 spare, unlit artifacts so a new project can be added later without
     rebuilding the forge.
3. **`sect/export_tracks.py`** (runs headless on `out/sect.blend`, CPU only, takes
   minutes). For every frame in each section's range and every tagged object:
   - Projects the object's 3D box corners through the camera into a 2D screen box
     (`world_to_camera_view`).
   - Checks whether it's hidden: a ray from the camera to the object's centre must reach
     the object before anything else.
   - For surfaces, exports the 4 corners on screen.
   - Writes `client/public/flight/tracks.json` (format below).
4. **QA overlay:** `export_tracks.py --overlay` draws the exported boxes on top of the
   rendered frames and makes a contact sheet. Every box must sit on its object.
5. **Re-render** the blocking video after the area changes. That's 12 minutes on a rented
   RTX 5090, about $0.30.

### 3. Data files the site loads

`public/flight/manifest.json`, small and loaded first:

```json
{
  "version": "blocking-2026-10-10",
  "fps": 24, "frames": 1729, "width": 1920, "height": 1080,
  "media": {
    "desktop": "/flight/flight-desktop.mp4",
    "mobileFrames": "/flight/m/{frame}.avif",
    "stills": "/flight/stills/{section}.avif"
  },
  "sections": [
    { "id": "projects", "area": "forge", "frameStart": 288, "heroFrame": 389, "frameEnd": 497 }
  ]
}
```

`public/flight/tracks.json`. Positions are whole numbers from 0 to 10000 (fractions of
the frame width and height), which keeps the file small:

```json
{
  "hotspots": [
    { "id": "project:dispatchai", "section": "projects", "from": 300, "to": 470,
      "box": [[4120, 3310, 4480, 3720, 1], "...one [x0, y0, x1, y1, visible] per frame"] }
  ],
  "surfaces": [
    { "id": "resume", "section": "resume", "from": 1060, "to": 1150,
      "quad": [[3100, 2200, 6900, 2050, 7000, 6100, 3050, 6000, 1], "..."] }
  ]
}
```

Expected size: about 100 objects × about 200 frames each, roughly 150 KB gzipped.

### 4. Frontend modules (`client/src`)

Following the repo's convention, the logic is pure functions in `src/lib` with
`.test.ts` files, and the components stay thin.

| File | Job |
|---|---|
| `lib/flight/manifest.ts` | types and loader for manifest.json and tracks.json, with validation |
| `lib/flight/timeline.ts` (pure) | `buildKeyframes(layout, sections)` turns section positions on the page into scroll→frame keyframes; `frameAtScroll(y, keyframes)` interpolates with easing and holds |
| `lib/flight/project.ts` (pure) | `coverTransform` (the video is cropped to fill any screen shape: maps video coordinates to screen pixels), `trackAt(track, frame)` (interpolates between frames, hides when not visible), `quadToMatrix3d(quad)` (the CSS transform that pins a DOM element onto a surface in the video) |
| `lib/flight/flight-bus.ts` | tiny pub/sub like `VoiceBus`: `highlight(id)`, `hover(id)`, frame updates. Components subscribe through refs so nothing re-renders 60 times a second |
| `components/flight/flight-stage.tsx` | replaces `BgStage`: a fixed full-screen player, a requestAnimationFrame loop that eases the shown frame toward the scroll target (fast flicks stay smooth), publishes the current frame |
| `components/flight/video-player.ts`, `canvas-player.ts` | two players with one interface (`load`, `seek(frame)`, `ready`): the video seeks a keyframe-dense MP4 on desktop; the canvas draws image frames on phones |
| `components/flight/hotspot-layer.tsx` | real `<button>`s for the current section's hotspots, moved with CSS transforms each frame; hover or focus shows a glow and tooltip; click dispatches the action |
| `components/flight/surface-layer.tsx` | DOM content pinned onto surfaces with `matrix3d` (About in the mirror, roles on tablets, resume on the scroll) |
| `components/flight/flight-section.tsx` | wraps each existing section and adds the scroll choreography below |
| `app/flight/page.tsx` | a new route that composes the existing sections inside `FlightSection`, so `/` stays untouched until launch |

**Click actions reuse what exists.** `project:<id>` emits `VoiceBus.emit({ type: "open", id })`,
which already opens ProjectDetail. Sections that don't listen yet (hackathons, experience,
education, skills, personal) get a small `VoiceBus.on` handler for `focus` commands with
ids like `role:3`. The server wire contract (`navigation.py` ↔ `PAGE_TO_SECTION` ↔
section ids) does not change.

### 5. Scroll choreography per section

Each section gets four stretches of scroll:

```
arrive   pinned, ~120vh   frames frameStart → heroFrame, eased; the section title fades in at the end
explore  pinned, ~80vh    holds near heroFrame (a slow drift of a few frames); hotspots are live, with a hint
read     normal flow      the section's existing content scrolls up over the frozen hero frame, dimmed
depart   ~60vh            frames heroFrame → frameEnd: the transit to the next area
```

- The section's DOM `id` moves to the start of **explore**. That way `scrollToSection`
  (voice, hash links, nav) lands on the hero frame with the hotspots ready.
- Lengths are tuned per section. Long transits get more depart scroll.

### 6. Voice agent

- `applyNavigation` stays as is. Scrolling to a section drives the camera there.
- On `open project X`, the hotspot layer also calls `FlightBus.highlight("project:X")`, so
  the artifact pulses while the modal opens.
- For long jumps (more than 2 sections away), cap the fly-through speed or cross-fade
  instead of racing through 40 seconds of footage. This is a decision for you (see below).

### 7. Making it work with the AI (Seedance) video

How to keep the flyer and the architecture consistent across generations (reference mode,
saved Elements, area keyframes, about 1,300 credits) is researched in
`blender/xianxia-sect/docs/ai-video-consistency.md`.

The Blender positions are exact for the Blender render. The AI video will drift: slightly
different timing, framing and object shapes. The plan:

1. **Generate** each clip with its blocking clip as the motion reference (if Higgsfield
   allows it) and chain the clips by last frame (see `blender/xianxia-sect/out/seedance_prompts.md`).
   Name the counts in the prompts ("fifteen floating artifacts") and add the blocking hero
   frame as an image reference.
2. **Re-time:** a dev-only page, `/flight/calibrate`, shows the stitched AI video. You
   mark each section's hero moment, and that produces a frame map from blocking to AI
   timing.
3. **Place:** on the same page, at each hero moment, the Blender positions are overlaid,
   and you drag any marker that's off onto its real object. That's roughly 10 minutes of
   dragging. Banners and steles move as groups.
4. **Track:** CoTracker3, an open-source tool that follows points through a video, takes
   those corrected points and follows them through each section's frames. It runs in
   minutes on a rented GPU and writes a new `tracks.json` for the AI video in the same
   format.
5. **Fallback:** if tracking wobbles in a section, hotspots in that section are only live
   during **explore**, where the camera is nearly still.

### 8. Phones, reduced motion, accessibility

- **Phones:** iPhone Safari seeks video poorly, so phones get image frames on a canvas:
  AVIF, 960 px wide, every other frame (12 fps). That's about 30 MB in total, but it
  loads one section at a time, with the hero frames first. Tap targets are at least
  44 px. The first tap shows the tooltip and the second does the action.
- **Reduced motion, Save-Data and no JavaScript:** one still per section (the hero
  frame), with hotspots placed from hero-frame positions. No scrubbing.
- **Accessibility:** hotspots are real buttons with labels ("Open project Dispatch AI"),
  in tab order, with a visible focus ring. Everything a hotspot shows also exists in the
  section's normal content, so nothing is video-only. The video is decorative
  (`aria-hidden`).
- **SEO:** unchanged. All content is still server-rendered in the DOM.

### 9. Performance budget

- First view: poster still ≤ 200 KB, engine JS ≤ 20 KB gzipped, tracks ≤ 150 KB gzipped.
- Video: loaded section by section (the current one and the next). Target ≤ 25 MB in
  total on desktop and ≤ 15 MB on phones. The spike (phase 0) picks the encoding.
- 60 fps on scroll: positions update through `transform` only, nothing triggers React
  renders per frame, and the loop pauses when the tab is hidden.
- Hosting: big media on Vercel Blob (a CDN that supports the range requests video seeking
  needs). Small JSON files go in `public/`.

### 10. Testing

- **Unit (vitest):** keyframes always move forward and hold at hero frames;
  `frameAtScroll` at the edges; the cover-crop math; track interpolation and hiding;
  `quadToMatrix3d` against a known result; data sync, meaning every project, role,
  school, hackathon and fact has exactly one hotspot in `tracks.json`.
- **Blender QA:** the overlay contact sheet from `export_tracks.py --overlay`.
- **End to end (Playwright):** scroll to Projects explore, click an artifact, and the
  modal opens. `applyNavigation({ type: "navigation", page: "project", project_id })` lands
  on the forge hero frame and that artifact pulses. Reduced-motion mode shows stills.
- **Devices:** Chrome, Edge, Firefox and Safari on desktop; Safari on iPhone; Chrome on
  Android.
- **CI** stays green: `pnpm lint`, `pnpm typecheck`, `pnpm test`.

## Phases

Each phase ends with something you can look at.

| # | Phase | What happens | Done when |
|---|---|---|---|
| 0 | Scrub spike (small) | `/flight-spike` with the current blocking video: compare a keyframe-dense MP4 (720p and 1080p) against a canvas image sequence, measuring seek delay and dropped frames on desktop and phone | a format is picked per device type, with measurements |
| 1 | Flyer, ids, Blender export (medium-large) | the flyer (`flyer.py`) and the chase camera with the new manoeuvre route; scene-ids generator, `SKILL_GROUPS`, area changes (36 banners, formation = real architecture, stele groups, fact objects, moon), `export_tracks.py`, overlay QA, cloud re-render (~$0.50) | the new blocking video shows the flyer chased through all 11 areas, and the overlay contact sheet shows every box on its object with counts matching the data |
| 2 | Flight engine on `/flight` (medium-large) | manifest/tracks loading, both players, timeline, FlightSection choreography, hotspot layer with glow and tooltips, FlightBus, unit tests | scrolling `/flight` flies the whole route smoothly and hotspots stick to objects in the blocking video |
| 3 | Interactions + voice (medium) | per-section click actions, card-hover glow, projected surfaces (mirror, tablets, scroll), voice highlights, e2e tests | every hotspot does something useful and voice navigation lands on hero frames with the right object pulsing |
| 4 | AI video (large, spends credits) | generate clip 1 and judge it, then the rest; stitch; calibrate page; CoTracker tracking on a rented GPU | `/flight` runs on the AI video with hotspots on their objects (or explore-only in weak sections) |
| 5 | Phones, accessibility, speed, launch (medium) | canvas player, reduced-motion stills, budgets, device tests, then make it the home page | CI green, budgets met, tested on devices, live |

Phases 0–3 need no Higgsfield credits; they use the blocking video. That means the whole
interactive site can be built and tested before spending anything on AI video.

## Risks

| Risk | What we do about it |
|---|---|
| The AI video drifts from the Blender camera, so hotspots sit off their objects | calibration + CoTracker tracking; explore-only fallback |
| The AI changes objects (12 artifacts instead of 15, banners merge) | name counts in prompts, use hero frames as image references, regenerate only the bad clip; fallback: the site draws its own glowing markers |
| iPhone Safari can't seek video smoothly | canvas image sequence on phones |
| Download size | per-section loading, phone-sized media, CDN |
| Adding a project later | 3 spare artifacts; positions regenerate from data; only the forge clip needs a new AI generation |
| Text hard to read over video | the video freezes and dims while you read; contrast checks |
| Voice jumps across many sections feel dizzying | capped speed or cross-fade (your call) |
| The flyer looks different from clip to clip | the same character reference image and description in every clip, chained last frames; regenerate any clip that drifts |
| The flyer hides the thing you're meant to see | the flyer stays in the lower centre at about a sixth of the frame; the camera swings to the side at hero moments; the flyer's screen box keeps tooltips clear |

## Decisions for you

0. **Who is the flyer?** (a) You: Seedance uses a photo of you as the character
   reference, and the flyer becomes clickable ("that's me"). (b) A generic cultivator:
   one character image is generated first (a few credits) and reused in every clip.
   *Recommended:* (a). It makes the portfolio personal, and you're the person visitors
   came to see.
1. **Layout.** *Recommended:* pinned scene moments, with each section's content scrolling
   over a frozen, dimmed frame. The alternative is content always floating over moving
   video, which is more immersive but harder to read.
2. **Hotspot precision on the AI video.** *Recommended:* start with explore-only
   (cheap, reliable), then add tracking where it holds up.
3. **Voice long jumps.** *Recommended:* fly through at a capped speed. The alternative is
   a quick cross-fade.
4. **Seedance credit budget** for the 8 clips plus retries.
5. **Launch.** *Recommended:* build on `/flight`, then make it the home page once phase 5
   passes. The current layout could stay as a "simple view" link.
