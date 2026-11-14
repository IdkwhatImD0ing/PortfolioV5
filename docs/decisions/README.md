# Design decisions

Why the site is built the way it is. One dated entry per decision, oldest first. Where the owner
gave a reason, it is quoted in his own words, typos included.

When you make a design decision, add an entry here in the same commit as the change. Longer write-ups
of single changes sit next to this file or in the folder for their area, and are linked from their
entry.

---

### 2026-10-09 · The portfolio becomes a flight through a sect

**Decided.** Scrolling the site flies the camera through a floating xianxia sect (a cultivation school
from Chinese fantasy). Each section of the portfolio is one place: the welcome is the mountain gate,
projects are the artifact forge, education is the scripture pagoda, skills are the stele forest, "how
this site works" is the protecting formation, and contact is the moon summit.

**Why.** The setting is a celestial realm: a mountain range floating above a sea of clouds, ending at a
giant moon. The moon is there for the site's name: art3m1s is Artemis, goddess of the moon.

### 2026-10-10 · A gentle camera

**Decided.** The camera turns slowly, eases in and out of every turn, and almost never rolls. New
framings are checked for how fast the view turns as the camera leaves a stop.

**Why.** Abrupt turns and wavering in the first tests made the owner motion sick.

### 2026-10-12 · No person in the shot

**Decided.** The flight is a pure camera move. The sword-riding cultivator who was meant to fly in
front of the camera was removed. The place is the subject.

**Why.** After three takes the owner said: "just remove the person entirely, it just looks so bad
right now".

### 2026-10-15 · Real-time three.js with baked light, instead of AI video

**Decided.** The site draws a real 3D scene in the browser with three.js. Blender is the authoring
tool. Cycles, Blender's path tracer, bakes the lighting into textures once, offline, and the browser
draws those textures as they are, with live touches on top. AI video (Seedance) left the pipeline.

**Why.** The AI video kept failing: clips did not stay consistent with each other, and the person in
them looked wrong. Real 3D also makes things clickable: an artifact at the forge opens its project.
The look aims for a polished stylised game, not a photo.

**See.** [`../scene/web-research.md`](../scene/web-research.md) (the first web pipeline) and
[`../history/`](../history/) (the AI-video plan it replaced).

### 2026-10-20 · AAA scenery

**Decided.** The scenery aims for the quality of a big-budget game: dense pines, moss, mist, birds,
waterfalls and signs that the sect lives there. The steep stone pillars, in the style of Huangshan and
Zhangjiajie, stay. Outside assets must be free to use (CC0 or CC BY).

**Why.** The owner: "I want the sceneary to look like something from a triple AAA game, iagine the
scenery quality fromblack myth wukong, witcher 3". The mountains should feel "mystical full of live and
less barren and deserted".

**See.** [`../scene/asset-research.md`](../scene/asset-research.md).

### 2026-10-20 · Jin Yong references throughout

**Decided.** Treasures and places from Jin Yong's novels are hidden along the flight, each with a small
card that says what it is. There are 19 now, from the Heaven Sword and Dragon Saber at the gate to the
Divine Condor at the summit.

**Why.** The owner is a big Jin Yong fan (*The Legend of the Condor Heroes*, *The Return of the Condor
Heroes*, *Heaven Sword and Dragon Saber*, *The Smiling, Proud Wanderer*) and wants them woven through
the site.

**See.** [`../scene/jin-yong-references.md`](../scene/jin-yong-references.md).

### 2026-10-21 · Quality beats optimisation

**Decided.** A bigger download is fine when it buys quality a visitor can see. The first AAA pass grew
the full download from 98 MB to 116 MB, about a fifth more, and that was judged worth it.

**Why.** The owner: "Optimizations are great, but dont priorize optimizations over quality."

### 2026-10-21 · Low, Medium and High quality

**Decided.** Slower devices get a lower quality tier instead of a weaker top tier. The loading screen
offers Low, Medium and High, picks one from the device, and lets the visitor change it. If frames run
slow, the page steps down. A link can force a tier with `?tier=low`, `?tier=mid` or `?tier=high`.

**Why.** It follows from "quality beats optimisation": High is never cut back to suit slow devices.

### 2026-10-21 · Sun and moon, with the moon first

**Decided.** The sect's emblem is 日 (sun) and 月 (moon). The moon leads, and sun-and-moon marks run
through the sect. The site's seal logo (2026-10-24) is a crescent moon and a sun on a red seal.

**Why.** The owner: "moon is prioritized but should still be sun moon motifs".

### 2026-10-21 · Grounded props and readable text

**Decided.** Only the floating islands, and things that are clearly magic, may hover. Every other prop
rests on something. Text on scene objects must be readable from where the camera stops, and must say
something a visitor understands. From 2026-10-22, names go on bases and plaques, not on the object: the
gate's swords carry 倚天 and 屠龍 on their plinths, and their blades are plain.

**Why.** The owner: "Why is there just a floating instrument in the cave abode area lol". A hovering
prop reads as a bug. On the Mission Hall's glowing idiom cards: "hard to read and im not sure whats on
there". On names: "if it was a real weapon the name wouldnt be on it".

### 2026-10-22 · Development bakes now, one production bake at the end

**Decided.** While the content keeps changing, every light bake uses the fast development settings.
One production-quality bake (four to five times the samples, with the same files and sizes) runs once,
when the owner says the content is final.

**Why.** The owner agreed to the split: the slow bake only pays off once nothing will change.

### 2026-10-23 · A restrained Chinese look for the interface

**Decided.** The interface takes a light Chinese dress, in the manner of *Black Myth: Wukong*: a
minimal HUD, brush-stroke dividers, cloud-scroll corners, place names in a brush hand with red seals,
and paper texture on large panels. Body text keeps clean modern fonts. Restyles are shown to the owner,
before and after, before they ship.

**Why.** The scene carries the mood, so the controls stay quiet, as in *Wukong*.

### 2026-10-23 · The sect becomes the home page

**Decided.** `/` is the sect. The old one-page portfolio was archived out of the repo, and `/sect`
redirects to `/`. `?view=page` still shows everything as one plain page, without 3D.

**Why.** The owner: "remove the home page and use / as the main sect page now".

### 2026-10-23 · Stream the current area and two on each side

**Decided.** On a desktop at full detail, the page keeps the area the camera is at, and the two before
and after it, at full detail, plus one spare area ahead. Smaller machines, phones and the Low tier keep
one on each side. Places further away show light stand-ins.

**Why.** Everything a visitor can see from a stop stays sharp. Phones stop at one on each side because
two came close to the memory limit a phone browser gives one tab.

### 2026-10-23 · One backend for every site

**Decided.** One Cloud Run service answers for both the sect and the old site. The persona is chosen
per call: the sect asks for the senior disciple, and a call that asks for nothing gets the classic
persona (Bill, in the first person). So the old site and every older voice agent version keep working
unchanged.

**Why.** The owner: "idk if i want to pay for two deployements".

**See.** [`../deploy/README.md`](../deploy/README.md) and [`../../server/README.md`](../../server/README.md)
("Personas").

### 2026-10-23 · Never overwrite a voice agent version

**Decided.** Published versions of the Retell voice agent are never overwritten or deleted. A change is
a new version or a new agent, and every older one stays.

**Why.** The owner wants every earlier version of the website to keep working after a redeploy.

### 2026-10-24 · The old site stays at v4.art3m1s.me

**Decided.** art3m1s.me (with www and billzhang.tech) now serves the sect. The previous site still runs
at [v4.art3m1s.me](https://v4.art3m1s.me), from its own repo and project, on the same backend.

**Why.** Same rule as above: earlier versions keep working.

### 2026-10-24 · The jade slip, whole and facing you

**Decided.** At the Jade Slip Pavilion (the resume), the whole slip and the whole pavilion are in view
when the camera stops. The slip is big, readable and faces the viewer.

**How it got there.**

- 2026-10-23: a version turned 40 degrees was rejected, then a smaller, set-back slip, then the
  restored original was "too in my face".
- 2026-10-23: the camera was reframed to show the whole slip and the whole pavilion.
- 2026-10-24: the owner: "The jade slip looks too far forward, maybe slightly back might be better."
  The camera now stops a little further back (48 m from the slip on a desktop instead of 44 m).

**Rule from this.** Show the owner framing changes to hero props before calling them done.

**See.** [`../sect/jade-slip-framing.md`](../sect/jade-slip-framing.md).

### 2026-10-24 · The talisman and the senior disciple

**Decided.** The voice agent stays in the sect, because it shows the owner's work. Since 2026-10-23 it
is dressed as a 传音符 (a sound-transmission talisman) in gold and ink: the button at the bottom right.
Since 2026-10-24 it speaks as a senior disciple of the sect, who guides visitors and talks about Bill
in the third person. Its labels and answers never call it "AI". Answers stay plain and professional,
with no put-on accent.

**Why.** The owner: "Dont use AI in the agent".

### 2026-10-24 · The senior disciple travels by ink

**Decided.** When the senior disciple takes a visitor to a place, the page uses the map's fast travel
instead of flying the camera there: ink spreads from the talisman, the camera moves underneath, and the
ink clears once the place is fully drawn.

**Why.** It is quick, and the ink hides the place until it has loaded, so a visitor never sees it half
drawn. It is also how the map already moved visitors, so both kinds of travel look the same.

### 2026-10-24 · The name: Sun Moon Divine Sect

**Decided.** The sect is 日月神教 (Rì Yuè Shén Jiào), in English **the Sun Moon Divine Sect**. Never
"cult". The Ming Sect's treasures (the holy fire, the Five Element Banners) stay as Jin Yong references.
In code, the voice persona's id is still `ming-sect`.

**How it got there.**

| Date | Name | Why |
|---|---|---|
| 2026-10-09 | 月华宗, the Moonlit Sect | The moon, for Artemis. |
| 2026-10-20 | 明教, the Ming Sect | A Jin Yong sect, from *Heaven Sword and Dragon Saber*. 明 is 日 (sun) beside 月 (moon), so the moon stays. The sect is unorthodox in the novel, a nod to the owner's unorthodox education. |
| 2026-10-21 | English "Ming Sect", not "Ming Cult" | The owner: "i dont like to call it a cult". 教 means a teaching or a faith. |
| 2026-10-23 | 日月神教, the Sun Moon Divine Cult | The owner's wording. 神 (divine) is for Artemis the goddess. 日月神教 is the sect of *The Smiling, Proud Wanderer*, and an English name says what it is to visitors who don't read Chinese. |
| 2026-10-24 | 日月神教, the Sun Moon Divine Sect | The owner: "Rename the sect to sect instead of cult". |

The Chinese name changed twice. Each time "cult" crept into the English name, the owner dropped it.

### 2026-10-24 · One docs folder, and a README that looks like the site

**Decided.** Every doc lives in [`docs/`](../README.md), including this log. The repo's README looks and
reads like the sect.

**Why.** The owner: "make sure you having a docs folder where all the docs and stuff are being stored,
like design choices etc", and "The readme currently isnt as themed similar to the website as it
currently is".

---

### 2026-10-24 · The talisman's icon is a talisman slip

**Decided.** The agent's button shows a gold talisman slip with a spirit spark and two jade sparks
(`client/src/components/voice-orb/talisman-icons.tsx`, `ORB_ICON = "slip"`), not a microphone. The
paper crane and the senior disciple's figure stay in the file as drawn alternatives.

**Why.** The owner: "Need a more agentic icon than the microphone". Of three candidates on the real
button, the slip read most clearly at its real size and is the 传音符 the panel is named after.

---

### 2026-10-24 · The background gets intent

**Decided.** The scenery around the halls is rebuilt with one rule per view: a star, one host shape, framing, and
quiet sky, with a reason for every element. Trees leave the sheer walls; peaks become karst pillars with grassy
shelves; a broadleaf canopy replaces the trunk carpet; islands drop to a few per view; falls break into mist; the
horizon gets pillar families and level mesas. Every hall, prop and stair stays as it is. Details in
[`2026-10-24-background-with-intent.md`](2026-10-24-background-with-intent.md).

**Why.** The owner: "There is trees growing out of cliff faces, there is no ledges with grass. there is a lot of
trunks, not enough grenery. In real life, people just see green, they dont see the trunk", "the overall background
and vibe of the scene don't quite have enough intent yet", and, on the plan, "i approve of the new background".

### 2026-10-24 · The logo is cut like a seal

**Decided.** The logo keeps its idea and its three colours, a paper crescent holding a gold sun on a cinnabar
seal, but is redrawn as a carved 白文 seal (the design is cut out of the red, so the red margin is the border).
It is design B, "carved", of three redesigns. Every size comes from one unit, 1/16 of the moon's radius. The
moon's full circle is centred and lifted a little, the sun sits wholly inside it, and the red border is as wide
as the gap between sun and moon. The frame and the sun's rays are gone. Three drawings share the same circles: a
small one fitted to the pixel grid for the browser tab and the top bar (horn tips cut where they would smear, and
a red 1.25% lighter so it holds 3:1 on Chrome's dark tabs), a straight-edged one from 48 to about 128 px and in
the share image, and one with a hand-ground stone edge from 180 px up. The top bar's mark is now upright and
18 px. One source draws every icon, the share image's mark and the README's seal (`client/src/lib/sect/logo.ts`,
`client/scripts/make-icons.mjs`).

**Why.** The owner: "i like it tbh, but right now it doesnt seem like it was carefully designed, porportions seem
off". Measured, the old moon sat low and left (its red border was 7.4 units on two sides and 14.5 on the other
two), 92% of the sun hung outside the crescent, the tab icon and the big icon were two different drawings, and
all 60 edge pixels of the 16 px icon were blurred. Now 4 are, the rounded corners. The owner picked B.

### 2026-10-24 · The reworked background ships as the final production bake

**Decided.** The background rework is done, and its last web bake ran once at production quality (about four
times the light samples of a development bake; same files and sizes). That bake is the version on the site, the
final version for now. The rules it follows: trees grow on ledges, caps and slopes, never out of a sheer wall; past
about 70 m the forest is one green canopy, not trunks; every stop has one star, one background host and quiet sky;
0-3 floating islands per stop, each standing on rock; no range or island falls for now (the rebuilt ones stood in
the wrong place, and the bake found it); every hall, prop, stair, bridge, shrine, plaque and inscription stays
exactly as it was. Before the bake, a critic standing in for the owner checked every stop against these rules and
the owner's intent standard; its last blockers (blossoms floating in the sky, a floating rock chip, a man-made
dressing on the Cave Abode cliff) were fixed first. Details in
[`2026-10-24-background-with-intent.md`](2026-10-24-background-with-intent.md).

**Why.** The owner: "once everything is done, we can do the full hd render and use that as the final version for
now and call it." On the background: "i approve of the new background", "I trust you".

### 2026-10-25 · The loading screen waits for Enter, in fewer words

**Decided.** When the scene has loaded, the loading screen stays up. The bar reads Ready, and a gold Enter button
sits beside "Read as page", under the graphics picker and the sound button. The flight starts only when the visitor
presses Enter, so the graphics and sound are set first. While the screen waits, the next areas keep streaming in.
Asking the voice guide to go somewhere from this screen also enters. Links the screenshot tools use (`?ui=0`,
`?frame=N`) skip the button. A reload for a new graphics tier after Enter does not ask again. The words on the
screen were cut: the tagline is "AI engineer" (it was "AI engineer. Builder of voice-first systems.", which also
changes the gate's reader and the search description), and the sound button says "Turn on sound" with no "For the
best experience" under it.

**Why.** The owner: "add like a play or start button to the home screen so the user actually has the option to
chose the settings before the website loads". On the words: "I still think you occasionally overengineer the
words to include too many words ... seems long for the sake of being long".

### 2026-11-04 · Weaker devices: cut hidden work, not quality

**Decided.** Eleven changes remove work that never shows in the picture: hover frames render at the resting
30 per second instead of the screen's full rate; cloud puffs work out their fog once per sprite and re-sort
from the last order; the cloud sea draws after the solid world; tree cards skip the area loop away from the
stops and grade only the pixels they keep; ladder steps down switch MSAA and bloom off in place and rebuild
the post chain at the next rest; the cloud-shadow pass and far rock and lawn detail return early where they
add nothing; Low converts colour once instead of three times; the area panel drops its backdrop blur; asset
files are fetched as `<file>?v=<fingerprint>` (the manifest's `rev`) and cached for a year. Medium's pond
reflection, at rest only, redraws every third idle frame (about 10 per second); High's still redraws every
frame. Before and after screenshots of 21 views (3 tiers, 7 stops) match within the noise between two
identical runs. The research and measurements are in
[`../research/low-compute-devices.md`](../research/low-compute-devices.md).

**Why.** The owner asked for ways "to optimize for lower compute devices, without skimping on quality too
much", and earlier: "dont priorize optimizations over quality". So only changes that leave every tier's
picture as it was went in. Removing the HUD plates' blur on Low changes how Low looks, so it waits for the
owner.

### 2026-11-06 · "How this site works" covers the whole site

**Decided.** The Grand Formation's reader now explains the whole site in six steps: the sect built in Blender with
Python, the light baked and packed, three.js drawing it live, a song per stop, the voice agent, and how the agent
flies you to a stop. The Stack pillar has five groups (Scene, Browser, Music, Voice, Brain), one for each of the
Five Element banners. The facts were checked against the code. The agent has 13 tools (the old copy said nine), and
page moves reach the browser over Pusher (the old code sample showed a Retell event that v3 calls no longer send).
The speech side stays as it was: the owner confirmed Retell uses an ElevenLabs voice, with Deepgram hearing you.

**Why.** The owner: "I think its time to update how this site works with the 3d model and blender and music and
everything now". The old copy came from the one-page site and only described the voice agent.

### 2026-11-08 · The soundtrack moves behind the backend and gains timed lyrics

**Decided.** Twelve selected drama and donghua songs replace the loading theme and eleven area themes while
keeping the existing `loading`, `gate` through `summit` music keys. Prepared MP3s and the eight timed lyric
files live in private Cloud Storage, not the frontend bundle. FastAPI exposes a metadata manifest and issues
short-lived capabilities bound to one track and resource type; audio uses HTTP range responses. The browser
keeps the existing Web Audio loops, memory budget, ducking and equal-power crossfades.

Every track exposes an openable `乐曲 / Music` drawer at the left edge, clear of the map controls.
It identifies the song, artist, source show and vocal type; instrumentals remain available with a
no-lyrics note. The eight sung tracks add complete bilingual lyrics and highlight the current
Chinese and English lines together; source pinyin and word-level karaoke are not displayed. It
follows the dominant track during a crossfade, remains available when playback is suppressed, and
hides behind readers, the map, fast travel and page view. Details are in
[`../music/local-soundtrack.md`](../music/local-soundtrack.md),
[`../music/backend-soundtrack-delivery.md`](../music/backend-soundtrack-delivery.md) and
[`../music/karaoke-lyrics.md`](../music/karaoke-lyrics.md).

**Why.** The owner selected one song for each place, supplied the twelve MP3s and character-timed lyric JSON,
and wanted the files served through the backend instead of shipped as frontend assets. Short-lived capabilities,
opaque storage names and private storage deter direct static downloads while preserving the existing playback
quality.

### 2026-11-09 · The soundtrack drawer takes the stops' dress and a note for each song

**Decided.** The soundtrack drawer is dressed like the stops' panels: rice paper over ink, gold cloud
corners, the title as the hero (a Chinese one with the red seal), a brush stroke under it and brush
rules in place of lines. Its opener is a title slip at the left edge, 乐曲 written upright on a
control's plate; the left edge stays. The credits shrink to one or two quiet lines and leave out an
artist the source does not name. The line being sung is marked in gold with a short brush stroke,
and the other lines fade with their distance from it.

Each sung track carries the owner's note on it, set as a small inscription between the credits and
the lyrics, word for word (`client/src/lib/sect/song-notes.ts`). Instrumentals show nothing there.

The closed slip sits under the stops' panels, so it never covers their words. While the drawer is
open, a stop's panel on the left moves over beside it where the screen is at least 60rem wide;
narrower, the stop's panel steps away until the drawer closes, as it does behind a reader. Details
are in [`../music/karaoke-lyrics.md`](../music/karaoke-lyrics.md).

**Why.** The owner found the first panel too plain and out of step with the rest of the page, and
wrote a phrase for each of the eight sung tracks to show with it.

### 2026-11-09 · The Music slip waits for the first stop, and a phone's stop panel is a little smaller

**Decided.** On phones the 乐曲 slip is hidden while the intro's title is up and comes in at the first
stop. While the sound is off, the soundtrack drawer's eyebrow reads "Soundtrack" and the drawer
offers "Turn on sound". On wide screens the slip lines up with the other plates. On phones a stop
panel's title is 1.6rem with a little less padding above it; its text stays whole.

**Why.** From the same clutter audit as the phone HUD entry. The owner saw each change before and
after and kept all of them, along with moving Read as page and the graphics button into the map on
phones. A shorter panel would need shorter text, which he left as it is.

### 2026-11-09 · Lyrics in the brush hand, sung word by word

**Decided.** The Chinese lyric lines are written in Ma Shan Zheng, the brush hand of the place names,
from a second cut of the font that holds every character of the songs (about 290 KB, fetched only
when the drawer is first opened). The line being sung fills with gold word by word from the lyric
files' word timings. This replaces the earlier choice to show line timing only. The drawer is a card
of limited height with a bare cross to close it, and an instrumental's card ends at its credits.

**Why.** The owner asked for word-by-word highlighting and a Chinese face closer to wuxia and
xianxia titles; the system serif the lines fell back to read as plain.

### 2026-11-09 · A phone's HUD keeps to what fits

**Decided.** On phones (every screen without the side rail: under 768 px wide, or under 500 px tall,
so a phone on its side too) five things moved. Tablets and desktops look and behave as before.

- The top bar is the seal and the name. "Read as page" left it. It stays as a skip link that shows
  only when the keyboard reaches it, and the map's All places tab now starts with a "Read it all as
  one page" row. The loading screen, the error screen and the end of every reader still offer it.
  On a phone on its side the art3m1s.me text hides too (screen readers still read it).
- The graphics button left its spot under the sound toggle for the map's top row, left of the close
  button. Escape with its menu open closes only the menu. When the loading screen goes, a focus
  left in its graphics picker moves to the Map button.
- At a stop, the place's name under the row of diamonds hides, since the stop's panel already names
  the place. It comes back during a voice call on an upright phone, where the voice panel covers the
  stop's panel. The look hint takes the name's spot, stays about 11 seconds instead of 25, and stops
  showing after a turn of the view or once it has shown on two visits.
- The loading and error screens fit small phones: two columns on a phone on its side, and Enter and
  Read as page side by side at 320 px wide.
- The map's place card at 320 px stays above the Map and All places tabs (it was measured before its
  width was set, then grew), and drops its small emblem there.

**Why.** The owner found the phone UI cluttered. An audit of the home page at five screen sizes
ranked these first. At 320 px "Read as page" ended 3 px from the Map button. On a phone on its side
the name plate took almost half the top row, and Enter sat below the bottom edge of the loading
screen. At a stop, three plates stacked under the diamonds. The graphics menu covered the stop's
panel, and the map's place card ran over its tabs.

### 2026-11-10 · A Chinese song title carries its English

**Decided.** In the soundtrack drawer a Chinese title is followed by a short gold dash, its English
in italics and then the red seal, which moved from beside the Chinese name to the end of the line.
The eleven English names are in `client/src/lib/sect/song-notes.ts`. *Throne of Glory* is already
English and stays as it was.

**Why.** The owner asked for "the chinese name - english translation" on each song, then for the
stamp to come after.

### 2026-11-10 · A place's song starts from the top

**Decided.** Arriving at a place starts its song from the beginning. Before, a song picked up where
it had stopped on an earlier visit. A pause in the same place (mute, a video, a hidden tab) still
picks up where it was, and a song still fading out when the camera turns back carries on
(`client/src/app/sect/experience/music-engine.ts` `setPlan`).

**Why.** The owner: "going to each area, the song should restart".

### 2026-11-10 · The Grand Formation plays 曙光

**Decided.** The Grand Formation's song is 曙光 (Dawn) by Chen Bing (陈冰), from 神印王座, in place of the
instrumental 天谴觉醒. It is the ninth sung track, with timed Chinese and English lyrics. Its
note is the owner's own: many sparks joining into one light, and a little each day adding up the
same way. Three garbled English lines and four broken line timings
in its lyric file were corrected before it was prepared; the timings in its last third are still as
transcribed and have not been checked by ear.

**Why.** The owner asked to replace the formation song with it.

### 2026-11-10 · Enter waits on the loading screen, greyed out

**Decided.** The loading screen shows Enter from the start, beside Read as page. While the scene
loads it is dim and cannot be pressed. When the scene is ready it takes the gold and the keyboard
focus. Both buttons are plates like the Map button's: ink, a gold line, cloud curls at the corners
and small spaced capitals. Enter carries the diamond of the rail and the graphics picker, hollow
while it waits and full when it is ready. The solid gold rectangle is gone from this screen.

**Why.** The owner: "the start button shouldn't just appear after it's finished loading. It should
be like grayed out or something." He then found the solid box out of step with the page's other
controls.

### 2026-11-13 · Sound is on by default

**Decided.** A visitor who has never muted the music hears it. Browsers still allow sound only
after a press, so it starts on the first click, tap or key: Enter on the loading screen, the
graphics picker, or anything else. Until then the loading screen's sound button reads "Turn on
sound"; after the first press it reads "Sound on", and pressing it (or the speaker in the corner)
mutes. A mute is remembered as before. Visitors whose browser blocks storage get sound on too.

**Why.** The owner: "Can we have it so by default audio is on?"

### 2026-11-13 · The music gets a page of its own

**Decided.** `/music` is a player for the soundtrack, with no 3D. It lists the twelve songs, shows
the open song's credits and note, and shows its whole lyrics, which follow the song as in the
flight's drawer. A bar at the bottom has previous, play and pause, next, a seek line, repeat, mute
and volume. A song plays once and then the next one starts. Nothing plays or downloads before a
press. The volume is the one the flight remembers. The flight's mute is not read here, and 100% is
the file's own level, twice the flight's.

It plays through an `<audio>` element fed a downloaded copy of the song, not the flight's Web Audio
engine. The engine decodes whole tracks into memory to loop and crossfade them. A player needs
pause and seek, and should keep playing in a hidden tab.

**Why.** The owner: "Can I get a /music page that is just a music player and lets me see the lyrics
en its entirety with controls liek volumne next pause play, etc".

**See.** [`../music/music-page.md`](../music/music-page.md).

---

## Longer write-ups

| Date | Change | Write-up |
|---|---|---|
| 2026-10-24 | Ice-Fire Island's steam rises from the crater; the Five Element flags get three times the texture detail (baked in the round-48 production bake) | [`2026-10-24-icefire-steam-and-element-flags.md`](2026-10-24-icefire-steam-and-element-flags.md) |
| 2026-10-24 | The music volume slider opens and closes on its own | [`../sect/music-volume-slider.md`](../sect/music-volume-slider.md) |
| 2026-10-24 | The jade slip camera steps back | [`../sect/jade-slip-framing.md`](../sect/jade-slip-framing.md) |
| 2026-10-24 | The background with intent: pillars with grassy shelves, a broadleaf canopy, fewer islands, a planned horizon (round 48; shipped as the final production bake) | [`2026-10-24-background-with-intent.md`](2026-10-24-background-with-intent.md) |
