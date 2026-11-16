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

### 2026-11-09 · Light the bake cannot hold

**Decided.** The page adds three things on top of the baked light, each frame, on High: contact shade (small
soft shadows where a lantern, a pillar or a railing meets the ground, worked out from the depth buffer), sun
shafts (a shadow map of the world from the sun, then a march through the haze, so light and shade show in the
air behind pillars and islands) and a finish (deeper darks, a little sharpening, fine grain). Medium gets the
finish without the sharpening, and FXAA: it had no edge smoothing at all. Low is unchanged. The mist puffs
now read one noise field fixed in the world, so a row of them is one torn bank and no longer a stack of smooth
ellipses. The sun's glow is screened onto the sky and no longer added: added, it drew a flat pink plate with
a hard rim. `?lux=0` turns the new passes off for a before and after.

**Why.** The owner compared the site with Saltline, a browser game Claude built in one run, and found the
scene's "quality is not good enough compared to the game that was made". He wanted the Blender scenes kept.
Saltline's look comes from its lighting and its finish more than from its models, and those are the parts a
bake cannot hold: light at a few centimetres a texel loses the line where a prop meets the floor, and a bake
lights surfaces, not air. So the Blender scene and its bake stay as they are, and the page adds what is
missing. The shafts took three tries: adding light for all lit air washed the picture out, so they now only
change a ray that differs from the frame around it.

**See.** [`../sect/lux.md`](../sect/lux.md).

### 2026-11-09 · Placement with intent: the gate's camera, and round 55

**Decided.** At the Mountain Gate the camera steps 3 m left onto the plaza's centre line and turns a degree,
so the gate is seen square on. Four stops get prop moves in Blender (round 55): the forge yard becomes two
smith's bays, a pair of racks by the workshop door and an ore yard, with one stray anvil removed; the mission
hall's lanterns leave the Big Dipper for the arrival landing; the jade slip's walk keeps one lantern spacing, two of
its scholar's rocks flank the way out and the third stands by the peach; the mirror terrace's west rock gets its boulder. The gate change is in the
client. The Blender moves were baked the next night (the entry below).

**Why.** The owner: "some of the objects in the scene are haphazardly placed". Every stop was drawn as a plan
from the builders' own coordinates and projected into its camera. That showed two causes. The gate plaza is
mirror-symmetric, but the flight passes its stop 3 m off the centre line, so the right-hand lanterns hid
behind a pillar while the left-hand ones showed: the props were right and the view was wrong. At the other
four stops, yard dressing had been typed in one piece at a time with no rule joining one to the next.
Centring the camera was also tried at the stele forest and the formation and taken back out: at the first it
flips the panel onto half of a symmetric view, at the second the turn back breaks the gentle-camera limit.

**See.** [`../scene/placement-r55.md`](../scene/placement-r55.md).

---

### 2026-11-10 · Round 55 baked: what the first run changed

**Decided.** Round 55's prop moves are in the scene and baked (forge, mission, scroll, mirror and the
backdrop, production quality, one rented RTX 5090). Three things were settled on the box:

- The tall scholar's rock at the jade slip stands 5.1 m from the peach, not 3 m. At 3 m it stood inside the
  crown with branches through the stone. 5.1 m is the nearest spot on the visitor's side where it is clear.
- `tools/rblender.py` and `tools/sect_pack.py` find the project from their own path, so a round can run from
  a git worktree without touching the main checkout. The box keeps its mirror at the main checkout's path.
- The audit's cache (`vis_cache.npz`) is kept with the round's files. The copy on the PC had gone stale, and
  that cost a 38 minute re-audit.

**Why.** The scripts had never run in Blender. The patch's own checks caught the rock in the tree, a floor it
did not know (the mission's arrival landing) and a 3 mm gap under racks and lanterns that it was too strict
about. Previews of the four stops were looked at before the bake. The packer also had to be repaired: it had
not compiled since 2026-11-04.

**See.** [`../scene/placement-r55.md`](../scene/placement-r55.md).

---

### 2026-11-10 · The flight sweep: mist, turned views, beams, the summit

**Decided.** After a look at every half second of the film (twice, with readers listing flaws and each
claim checked on the full frame): mist puffs end in a wide soft rim and a thin bank seen edge on becomes a
low faint veil; a view turned to the side or behind comes down to 4 degrees below the horizon where the film
tilts up; a far light beam keeps a minimum width; the summit stands 8 frames back so the moon hangs clear of
the pavilion's finial.

**Why.** The owner asked for the long loop of changing and checking that the Saltline game had. The sweep's
worst finds were mist that read as stickers and tape, a summit where turning round showed only sky, beams
that read as scratches, and the moon resting on a spire. Four other ideas were tried on screenshots and
taken back (steep grass as stone, moss in patches, a lower highlight shoulder, a soft shore on the cloud
sea): none changed what the eye saw. What is left is in the scene itself and is scripted as round 56.

**See.** [`../sect/flight-sweep.md`](../sect/flight-sweep.md).

---

### 2026-11-10 · Round 56 scripted: form and edges

**Decided.** Five flaws the flight sweep found in the scene itself are scripted as one Blender round, to run
when the owner says so: grass ends on a level line at every terrace rim (a square near a terrace is grass
only when all four corners are on the flat), the mirror's and the abode's lawns dive under their terraces
instead of ending on a step, the stairways' side walls get a weathered white marble the bake can hold, the
arena sword's broad faces get three tones, and the plank bridge to the arena island hangs 5.5 m instead of 2.
No object is renamed, so the audit is not needed. The rim touches every chunk, so it is one full bake.

**Why.** Each was first tried or ruled out in the page: the teeth and the flat walls are in the baked
texture itself, and the others are geometry. One box session for all five costs about the same as doing the
rim alone.

**See.** [`../scene/form-r56.md`](../scene/form-r56.md).

---

### 2026-11-10 · Round 56 baked: three checks loosened, the abode's plants rebuilt

**Decided.** Round 56 ran on one rented box the morning the owner said "Yes, run 56", and all five parts are
in the client. Three of the patch's checks were loosened after the first dry runs. The range's top points may
sit up to 5 cm off the rebuilt recipe as long as no changed face uses one. A lawn may be 1 mm off its area's
origin. The plant check guards only the part of a lawn that no re-made face reaches. The abode's plant file
was rebuilt on its own, beside the bake.

**Why.** Each check had stopped on something real and harmless: 83 of 214,414 range points up to 2.8 cm off
for a reason not traced, float rounding at 1,300 m from the origin, and six rim plants the scatter drew again.
Two of those plants were shrubs the page draws, so keeping the old plant file would have left two bushes in
the air over the lowered lip.

**See.** [`../scene/form-r56.md`](../scene/form-r56.md).

---

### 2026-11-10 · Round 57: the bake gets a key light, the page a richer grade

**Decided.** Every bake now lights the scene with the film's sky and a crisp warm key from the sun's side, 27
degrees up, in place of the soft fill it had. The page's grade keeps most of green's lead, with more contrast
and saturation, and mist puffs are rounder and lit from the sun side. All eleven stops, the backdrop and every
area's plants were re-baked.

**Why.** The owner said the site "still doesnt seem photorealistic" and pointed, in effect, at his own style
frames: clear shadows, rich greens, lit cloud. The scene's sun is 7 degrees up, so the old soft fill was what
lit the ground, and it cast no shadow. A test at the mirror terrace showed that lowering the fill only darkens
the picture and that a key light gives lawns and plazas real light and shade. He saw the before and after and
said "Yes, roll it out".

**See.** [`../scene/light-r57.md`](../scene/light-r57.md).

---

### 2026-11-10 · Far trees are drawn as lit crowns built in code

**Decided.** On the High tier a far tree is an instanced crown shell that the page builds and lights itself,
from a list of every plant's place, size and family exported from the scene. The baked cards stay for trees
near the camera and for the other tiers. Ground cells 9 m across switch between the two by distance and by how
steeply the camera looks down, with the same lines of shader code on both sides.

**Why.** The owner: "far away objects show up as blocks which breaks the immersion". The blocks were the
cards' flat top quads, seen from above. He also asked to look at how Saltline does it: that game loads no
models, it builds from code and lights live. Doing the same for far trees removes the plates, lets the crowns
take the scene's light, and needs no bake when the look changes.

**See.** [`../sect/veg-shells.md`](../sect/veg-shells.md).

---

### 2026-11-10 · Far spires get a rock layer of their own; the first review round's fixes

**Decided.** After the rollout, three readers went through 117 frames of the flight and the look-around views.
Their top finding was far rock spires that read as smooth tubes. The backdrop's far peaks and the rock faces of
the areas' stand-ins now get a rock layer sized for a spire, with no distance fade. The same round lowered the
grade's shoulder and warm split (sunlit marble had blown out, cliffs had turned rust orange) and gave every tree
crown its own width.

**Why.** The backdrop is baked as one colour per point with no detail class, and the page's rock layer fades out
by 700 m, so everything past that was bare. The fix is in the page because the stand-ins' outlines are fine at
that distance: what was missing was surface.

**See.** [`../sect/far-rock.md`](../sect/far-rock.md), [`../scene/light-r57.md`](../scene/light-r57.md).

---

### 2026-11-10 · The gate is lit live, from three more maps the bake writes

**Decided.** One stop, the gate, is lit in the page on the High tier: its sun light, shadows and shine are worked
out per pixel. The bake writes three more maps per atlas for it (surface colour, surface direction, and the light
with the sun and the key lamp off), the page adds the two lamps with a shadow map each, and Blender's own view
transform is read from a lookup table so live colours match baked ones. On top of that come what a bake cannot
hold: bumps, gloss, and the sky in smooth surfaces. `?live=0` keeps the bake.

**Why.** The owner, after round 57: "It still doesnt look as good as Saltline unfortunately the photo realism,
etc", then "Yes, build the gate". Saltline lights everything live; a bake's shadows are as soft as its texels and
nothing in it shines. An export without a bake was the first plan and was dropped: it would have lost what
Blender's materials hold. Keeping the bake's sky light and replacing only the two lamps keeps all of that, and it
can be checked: the page's sum was measured against the bake's raw files (within 2%) and against the baked
picture (5 steps of 255 on average) before anything was tuned by eye.

**See.** [`../sect/live-gate.md`](../sect/live-gate.md).

---

### 2026-11-10 · Live light at every stop, one at a time, with the bake's bounced light and far shadows

**Decided.** All eleven stops have live maps, and the page lights the one the flight is at (High tier). The next
stop's maps load while the flight moves on, and fast travel's ink waits for the new stop's light. Two more things
now come from the bake, both worked out from its raw files by `sect/live_bounce.py`: the lamps' bounced light
(added to the sky-light map) and how much of the lamps' light the bake let through at each texel (in that map's
alpha). The live colour starts from the baked texel: it is multiplied by "baked texel over the bake's light as
the maps rebuild it", so where live changes nothing the picture is the bake's own. The page's own shadow maps
only tighten the bake's shadow, and only near its edges. The maps (83 MB of WebP) go in Git LFS.

**Why.** The owner: "Lets keep going", and earlier "MAke sure to go through multiple rounds across all scenes".
One stop at a time because stops are 190 to 240 m apart and a stop's maps are about 255 MB on the GPU. The bounce
came from a review: shade was 11 to 19 percent darker and cooler than the bake with a flat guess. The bake's far
shadow came from the abode, where a tree 30 m off drew a hard edge on the cliff that the bake has three metres
soft. Three review rounds compared baked and live pairs at full size. The third found live about equal to the
bake and its flaws all of one family: the page's maps are half the bake's size and its shadow maps have gaps
(faces the flight never sees are not in the page). So live was turned from "rebuild the light" into "the bake,
plus what live light changes". After that it differs from the bake by 2.6 steps of 255 on average over 55 views,
and what differs is what it adds: a little more sun, tile relief, tighter contact shadows, a held-down shine.
The honest finding: with these models a careful bake is most of what live light can show. What still reads as
fake is in both pictures, and is the models and textures.

**See.** [`../sect/live-gate.md`](../sect/live-gate.md).

---

### 2026-11-11 · Surfaces get wear, dirt and rock beds, in the page

**Decided.** The first round on models and textures is done in the page's shaders, with no new model and no
bake: paving gets replaced stones, stains, dust and cracks (and under the live lamps slabs that sit unevenly,
with bevelled edges); every baked surface with no detail class of its own gets patchy tone, rain streaks and a
fine grain; lawns drift more in colour and their clumps come and go; steep rock lies in level beds.

**Why.** The owner: "Yes, start it", after three reviews found the same four things fake at most stops, in the
baked and the live picture alike: spotless plazas, flat clean paint, lawns one even green, cliffs with no
structure. The page already had detail layers for three of them, set so gently that nobody saw them, so the
cheapest real gain was there, and it can be checked the same hour on the GPU. Shapes (cliffs, trees, the
waterfall) are left for a Blender round.

**See.** [`../sect/surfaces.md`](../sect/surfaces.md).

---

### 2026-11-12 · Round 58: near trees keep their leaves; far crowns and rock get detail, and half of it is taken back

**Decided.** The first round on models. Three things ship:

- Near broadleaf trees keep their leaf sprays, and peach trees use their fuller model. This is a tree
  build on the box, with no light bake.
- Far crowns keep the ragged leafy edge they had and get soft lit lumps that ease off when a crown is
  large on screen. A crown deep among others is darker low down, measured by height on its own shell.
- Cliffs and spires get the middle band of the bake's own rock photo (cracks and blocks from 12 cm
  to 1 m), read at the bake's own coordinates, only where the baked texel is too coarse to hold it.

The web pack grows from 122.6 to 127.2 MB. That is 2.2 MB over the packer's 125 MB line, which only
reports. It is accepted: the owner put the look first, and the leaves are the round's clearest gain.

**Why.** The owner: "Yes, start it", then "Keep going". Reviews named trees and rock at every stop.
The pipeline was mapped by five readers, five designs were each attacked by a skeptic, and three
were built. Then the pictures decided, twice:

- The first review of the page parts scored a small loss, 4.52 to 4.46 out of 10. The new crown
  outline "bites" caused 32 of 48 confirmed faults: holes through crowns, floating chips. Their
  maths was only right on a sphere, and crowns are flattened or tall. The bites were removed and the
  old leafy edge restored. The lumps looked like crumpled foil up close, so they were softened.
- The last review of the whole round scored a gain, 4.50 to 4.68. Near trees were a clear win at 9
  of 11 stops. Far crowns showed no change a reviewer could see. The rock band helped at five stops
  and hurt at two, where it sat on rock the bake already holds. So it now follows the baked texel's
  size. That last fix was checked on the GPU but not by a review round.

**Held for round 59.** A floor on the rock's baked texture density, a rebuilt rock material without
drawn cracks, and real ledges on the fine rock meshes. Lawn edges, the stair's stretched texture and
the steles court's paving wait longer.

**See.** [`../scene/trees-r58.md`](../scene/trees-r58.md), [`../sect/veg-shells.md`](../sect/veg-shells.md),
[`../sect/surfaces.md`](../sect/surfaces.md).

---

### 2026-11-12 · Round 59: only the rock texel floor is kept, and it waits for the next bake; the new rock material and the bake-time ledges are switched off

**Decided.** Round 59 built three things for the rock and tested them on a rented box. Only one is kept:

- The texel floor stays on in the code. It gives rock that the holds see from the front more of the bake's
  texture, paid for inside today's budget, with no atlas added. It was not baked for production: it goes out with
  the next full bake.
- The rebuilt rock material (world beds and joints in place of drawn cracks) is off (`ROCK_STRUCT = False`).
- Bake-time relief (real ledges and flat faces cut into the rock meshes) is off (`RELIEF = False`; `--relief`
  turns it on).

Nothing on the page changed. The box session cost 1.07 dollars. The code of all three stays in the repo, with its
tests, for a later rock round.

**Why.** The pictures decided:

- The new material looked worse than today's rock in 9 of 11 stills and better in none. Its beds came out as
  near-black painted bands, a contour map on a sloping slab and a block grid at the forge. Toned down twice, it lost
  to today's rock 9 to 2 and 8 to 2 with two blind reviewers. Under the 7 degree sun, structure drawn through a Bump
  reads as painted lines.
- The relief turned the abode cliff's sunlit shoulder into pleated cloth and let the lawn show through a new ledge.
  The floating rocks did not visibly change. The near columns gained a little, but one at the gate came away from
  the rope bridge's anchor.
- The floor kept every area at 93 % or more of today's texels a metre for everything else, and a fix keeps the
  steles from opening a third atlas. Its two-area test bake showed slightly sharper cracks on the abode cliff, but
  only at twice the page's size. That is too small to pay for a 145 minute production bake on its own.

**Next rock round.** Start with a better base rock photo: every reviewer, blind or not, named its web of small crack
cells, which reads as dried mud, as the strongest tell. Then give beds real shape, with finer cliff meshes or a baked
displacement, before any more painted structure. The column relief can come back with the gate's bridge anchor
pinned.

**See.** [`../scene/rock-r59.md`](../scene/rock-r59.md).

### 2026-11-13 · Round 60: the rock gets a new base photo, and texture work stops there

**Decided.** The rock's base photo is now a seamless tile cut from Poly Haven's mountainside model (`mtn_cliff`),
in place of the marble photo whose crack web read as dried mud. It was baked for production with round 59's texel
floor on, and the page's rock detail was rebuilt from it. No download was needed: the model was already on disk.
The rock tuning that was meant to follow was dropped, and so was any further round of texture polish.

**Why.** The pictures picked the tile: blind reviewers ranked it first of six variants, it beat today's rock in
11 and 12 of 17 pairs with no loss, and marble at three times the size did not help. On real page screenshots the
gain was smaller: it won about twice as often as it lost, short of the 2.5 to 1 set beforehand. Then the owner
looked at the before and after and said: "Tbh after all this 60 rounds I dont see any differences tbh um". Rounds
55 to 60 had all worked at the size of a texture. None changed what a visitor sees at a glance. The new photo is
kept because it is a measured gain with no loss a visitor would notice. The box's bill was 2.41 dollars (the
credit dropped by 2.49).

**Rule from now on.** A change must show in a full-frame before and after at page size, and the owner's eye
decides. Reviewer scores alone do not justify another round.

**See.** [`../scene/rock-r60.md`](../scene/rock-r60.md).

### 2026-11-13 · The day runs along the flight: sunrise at the gate, night at the summit

**Decided.** The page's look follows the camera. The gate is a gold sunrise, the mirror a misty morning, the middle
stops a clear day, the library late afternoon, the steles golden hour, the jade slip sunset, then dusk, blue hour at
the abode and night under the moon at the summit. It is the normal look for every visitor on every quality tier.
One table sets the arc (`JOURNEY` in `client/src/lib/sect/journey.ts`) and one flag turns it off (`JOURNEY_ON`),
which gives back the dusk the scene was baked in. The loading stills were captured again to match the sunrise gate.

**Why.** After the owner saw no difference from the texture rounds, he was shown three bold looks of the whole frame
(golden hour, moonlight, ink-wash mist). That gave him two ideas. First: "what if we had my site change colors based
on the current time of the day in Pacific time?" Then: "Or maybe we have the date change from sunrise to sunset. From
the start to the end of the map? Which one do you think is better?" The journey was recommended and he took it
("Yep, let's do that then."):

- Every visitor sees the whole day in one visit. With the clock, a visitor sees one look, and most visits fall in
  the same few hours.
- It tells the sect's name: sun into moon.
- Each stop needs one look polished, at its own hour.
- The bake's low sun suits sunrise, golden hour and dusk, which are the hours the arc leans on.

**How.** The looks only move settings the page can change while it runs (uniforms and colours), so no shader is
built when the look changes: a full scroll links the same number of shader programs with the journey as without.
The lowest tier has no post pass, so its frame grade runs inside the shaders that draw to the screen. Blending the
look costs about 0.03 ms on a frame where the camera moved.

**Limits.** The baked light's direction cannot move: shadows stay long at noon and the moon is lit from the sun's
side. The clock idea stays in the code as a development preview (`?look=auto`, `?time=`), off for visitors. The
share image still shows dusk. The lowest tier's extra shader work has not been timed on a real phone. The owner
found the local page very laggy. On the High tier, arriving at a stop could freeze the page for up to about a
second while the live light's shadow programs loaded. That was the live light's code, though the waits were longer
with the journey on. It is fixed in the next entry.

**See.** "Looks and the journey" in [`../sect/lux.md`](../sect/lux.md).

### 2026-11-13 · Shader programs are made ready before they are drawn with, and kept for the page

**Decided.** Nothing the page draws may build or first-use a shader program on the frame that shows it. The live
light's programs, the shadow maps' depth programs, each streamed chunk's programs, the decorations' and the fire's
are compiled off the frame, waited for until every one is linked, and have their first use run before anything
draws with them. Programs the live light needs are kept for the whole page instead of being freed with each stop.

**Why.** The owner tried the local page and wrote: "I tried out the localhost link and its very very laggy, what
kind of performance optimziations can we do? That wont ruin the visual performance". A timed scroll of the whole
flight showed 10 to 27 freezes per flight on the High tier, 0.8 to 12 s in all, each one the page waiting for the
graphics driver to finish a shader program. The earlier check of the journey had only counted programs, never
frame time.

**How.** Four causes: the shadow maps' depth programs were freed and rebuilt at every stop; the warm-up copies of
the live materials lost `flatShading` and `defines` when cloned, so they compiled the wrong programs; the real
materials were switched before their programs had finished; and a ready program's first use still blocked on a
busy frame. No shader, map or uniform value changed.

**Checked.** A second agent re-timed it and compared pictures. New code: no wait in 13 of 14 flights (one had two
at the first stop), 46 to 62 programs linked per flight against 229 to 285, worst frame 0.13 to 0.36 s against
0.24 to 3.2 s. With motion frozen, old and new code give the same picture (shadow crops differ by exactly 0).
Counts of programs and textures stop growing after the second pass over the flight.

**Limits.** All timing is on the development server with a game on the same GPU. Not timed: a first-ever visit
with no cached shaders, and a production build. Still there: texture uploads of 15 to 45 ms for each 4096 px map
(most of the frames over 100 ms that are left), and at the first stop a frame of 0.24 to 0.34 s in about one
flight in three while the driver builds its programs.

**Rule from this.** Before the owner is given a link, time a full scroll and compare it with the page before the
change. Counting shader programs is not a timing.

**See.** "Lighting a stop without freezing the page" in [`../sect/live-gate.md`](../sect/live-gate.md).

### 2026-11-13 · A song note's Chinese is written in columns, from the right

**Decided.** In the soundtrack drawer and on `/music` (the same note), the Chinese side of a
song's note is set in upright columns read from the right, at most seven characters to a column,
as an inscription on a scroll is written. The English side and the lyrics are unchanged; lyrics stay written across, as sung lines
are everywhere. The note is now as tall as the side it shows: the Chinese is taller, so pressing
the note opens its place and the lyrics under it move down, and the English view keeps the height
it had. The lyrics' brush font gained the comma and the full stop as a column writes them, in the
upper right of their squares (Ma Shan Zheng has no such forms). Details are in
[`../music/karaoke-lyrics.md`](../music/karaoke-lyrics.md).

**Why.** The owner asked whether the notes' Chinese would be more culturally correct written
vertically, starting from the right. It would for this spot: the note is dressed as the inscription
at a scroll's end, in a brush hand, and that is how one is written. Across is not wrong (it is how
the mainland has printed since the 1950s), it only reads as modern.

**Checked** on a preview page with the real drawer component and stylesheet, a made-up engine and
made-up lyrics, at 1024×768 and at a 250 px drawer (a 320 px phone), and the `/music` card on its
own stylesheet at 1024×768 and 375×812. Not checked in the full 3D page or the real `/music` page
with music playing, and the opening and closing motion was not watched (the preview pane was
hidden, where animation does not run).

### 2026-11-14 · GPU work goes through one queue, and Enter waits for the first stop

**Decided.** Smoothness is now measured on the path a visitor takes: a production build, the interface on, the
loading screen, a click on Enter, then a scroll down and back. On that path three things changed. Texture uploads
go through one queue, one small step per frame, and a big map goes up in bands. Enter stays grey until the first
stop is finished behind the loading screen, for at most 6 s. Images are decoded in a worker, and the big
preparation jobs are cut into smaller steps.

**Why.** After the shader freezes were gone the owner's page still stuttered, and every timing so far had skipped
the interface and the loading screen. A diagnosis on the real path found three causes per flight: 2.2 s of stall
from uploading 4096 px maps in one call each, 1.1 s of waiting on the browser's GPU process while the driver built
shaders, and 0.75 s of main-thread script.

**Checked.** A separate agent timed old against new on production builds and compared pictures. Frames over
50 ms per flight fell from about 30 to between 2 and 5, and none is over 100 ms. The time lost in slow frames
fell from 1.6 to 2.0 s per flight to about 0.2 s. With motion frozen the picture matches at all eleven stops.
A tier change now gives its memory back, and a lost graphics context recovers by itself.

**The cost.** The loading screen takes 2 to 4 s longer (Enter at 3.6 to 5.0 s on a repeat visit against 1.4 to
2.0 s, and 6.4 s on a first visit against 2.1 s). The stutter moved from after Enter to behind the loading
screen. The checker marked this as a fail against its brief. It is kept for now, and making that wait shorter is
the next step.

**Limits.** After a very fast flight a place can show its stand-in models for 3 to 5 s. Banded uploads are only
used for maps whose sides are powers of two, because the driver made different mipmaps for the others. One
capture in ten at the forge showed 57 speckled pixels on far trees, not explained.

**See.** [`../sect/smooth-flight.md`](../sect/smooth-flight.md).

### 2026-11-14 · The GPU queue's pace follows what the visitor can see

**Decided.** The queue that feeds the GPU has three paces. While the camera moves it takes one small step a
frame, as before. While the camera rests it takes about 7 ms a frame for the place the visitor is waiting to see.
Behind the loading screen or fast travel's ink it takes most of the frame. The rest of the loading work takes
bigger slices behind the loading screen too, and the areas the first stop waits for load side by side.

**Why.** Finishing the first stop before Enter had made the loading screen 2 to 4 s longer, and after a very fast
arrival a place could show its stand-in models for seconds. Both came from pacing the work as if the visitor were
always watching a moving camera.

**Checked.** Enter comes at about 3.0 s on a repeat visit (3.8 s before) and 4.6 s on a first visit (6.6 s
before). No flight had a frame of 100 ms or more. Every place was drawn in full when the camera stopped.

**Limits.** The checker marked two things. With both builds sharing one browser profile the new one's Enter was
sometimes later, because each build pushed the other's cached shaders out. And two picture differences are not
explained: 56 pixels on a far pagoda at the forge, and a place ahead that is lit a little differently in the
middle of a key flight. Enter on a slow line is not measured.

**See.** "Round 3" in [`../sect/smooth-flight.md`](../sect/smooth-flight.md).

### 2026-11-14 · Timings are taken in a normal Chrome, and drawing ahead is set aside

**Decided.** Smoothness is timed in a Chrome started for the run on its own profile, not in the browser the test
tool drives. The off-screen first draw built in round 4 is not merged.

**Why.** The freezes on the first load of a fresh browser session turned out to belong to that one browser, which
builds every shader 5 to 10 times slower than any other Chrome on the PC. In a normal Chrome the page was already
smooth on such a load. Drawing ahead took a flight from 1 or 2 frames of 50 to 64 ms to none, which cannot be
seen, and costs a quarter more GPU buffers and a slower relight after a renderer is rebuilt.

**Also found.** On a real line a first visit waits exactly 6 s between the first picture and Enter, the cap on
the wait for the first stop's neighbours. On localhost that never showed. It is the next thing to fix.

**See.** "Round 4" in [`../sect/smooth-flight.md`](../sect/smooth-flight.md). The set-aside code is on the
branch `claude/saltline-draw-ahead`.

### 2026-11-14 · Enter waits for work, not for downloads

**Decided.** After the first picture, the loading screen keeps Enter grey only while work is going on for files
that have already arrived. A file still downloading holds Enter for at most half a second. Whatever arrives after
Enter is handled as at every later stop: stand-in models until an area is in, live light fading in when its maps
come.

**Why.** With the network slowed to 50, 20 and 5 megabits a second, a first visit waited exactly 6 s between the
first picture and Enter, the cap on a wait for areas that were still downloading. Every earlier timing ran on
localhost, where a download takes no time, so nobody saw it.

**Checked.** Enter now comes 0.7 s after the first picture on all three lines (at 50 megabits a second: 6.2 s
from the start of the load instead of 11.5 s). No frame of 100 ms or more after Enter in 7 slowed runs. With no
slowing nothing changed by more than a quarter of a second. The checker found and fixed one freeze this exposed:
an area dropped while its shaders were still being built.

**Limits.** Measured on localhost with Chrome's own slowing, on the High tier, on a desktop.

**See.** "Round 5" in [`../sect/smooth-flight.md`](../sect/smooth-flight.md).

### 2026-11-14 · The branch goes up as one commit

**Decided.** The Saltline branch is pushed as a single commit on top of main and opened as one pull request.

**Why.** The branch's 29 commits hold every bake of the scene files. Pushing them all would upload 969 MB to Git
LFS, and LFS storage is never given back. Only 307 MB of that is the files as they are now. The other 661 MB is
older bakes of the same files. One commit uploads the 307 MB. It also leaves out 7 MB of gate maps that one
commit had stored outside LFS.

**Cost.** GitHub shows one commit where the work took 29. The write-ups in `docs/` hold what each round did. The
29 commits stay on the owner's PC, on the branch `claude/saltline-full-history`.

**Checked.** Before the push, two separate passes went over everything it would publish: every added line and
commit message for keys and private data, and every file for its kind, its size and text hidden inside it.
Nothing was found that had to stay out.

### 2026-11-14 · Stand-in trees keep their cards

**Decided.** The backdrop's stand-in trees get their own copy of the tree card material, so the distance past
which the crown shells take over from the cards applies to the backdrop's own far trees only.

**Why.** An independent review of the pull request found that both kinds of tree share one material in the
backdrop's file. The cut was set on that material, and stand-ins have no shells. On High every far stand-in lost
its trees: at the gate, the first thing a visitor sees, the far spires were bare.

**Checked.** A capture at the gate before and after, and a test that builds the shared material as the file has
it. The summit view did not change by a pixel.

**See.** "Stand-in trees keep their cards" in [`../sect/veg-shells.md`](../sect/veg-shells.md).

### 2026-11-14 · Scrolling snaps to a scene, and no longer sticks on one

**Decided.** A stop is no longer a stretch of the scroll where the camera stands still. Each stop keeps one scroll
unit instead of 42, and the legs are not eased. When the visitor's scrolling rests for 0.18 s, the camera glides to a
stop by itself: the next one in the direction of travel once they have moved 60 px, else back to the nearest. The
glide starts at the speed the camera has and lands softly. Any input ends it at once. One mechanism serves the
wheel, a trackpad, touch, Space and the scrollbar, and replaces the touch-only flick.

**Why.** The owner: "each scene will stop for a second when you scroll onto it, right? So when you're fast
traveling between scenes, it gets stuck on scenes and it feels weird. But at the same time, we should like snap to
a scene." Both came from tying the stop to a place in the scroll: the dead stretch was 5 to 7 wheel clicks long and
the camera slowed to 45 percent on the way in, yet scrolling that ended between two scenes left the camera there.
He was shown the design and answered "Yes, build it".

**The cost.** The camera can no longer rest halfway between two scenes. One wheel click now takes the visitor to
the next scene, so the whole flight is eleven clicks for someone in a hurry. The page is a fifth shorter.

**Limits.** The logic passed 13 cases and a round of attempts to break it, but in a hidden browser pane with
frames driven from a timer. How it feels in a real window, on a real trackpad and on a phone is not checked.

**See.** [`../sect/scroll-snap.md`](../sect/scroll-snap.md).

### 2026-11-14 · The snap becomes a gentle one

**Decided.** The camera stays where the visitor's scrolling rests. It is pulled on to a scene only when the rest
is close to it: within the last 16 percent of the way there, or a small overshoot past a scene just scrolled
through. Leaving a scene is free from the first wheel click, and while the visitor drags the view to look around
the snap waits. A wheel click no longer travels a whole scene; the keys, the rail and the map still do.

**Why.** The owner tried the first version, which glided to a scene after every rest: "I think the snapping is
too agggressive riht now, what if the user wants to sit in between a scene and look atound the map". The cost
named when it was built ("the camera can no longer rest halfway between two scenes") was the wrong one to pay.

**Limits.** The two reach numbers are a first guess and wait for his verdict.

**See.** "Which stop, and when it stays" in [`../sect/scroll-snap.md`](../sect/scroll-snap.md).

### 2026-11-15 · Four fixes from the review of the pull request

An independent review of the pull request found four things worth fixing before the merge. Each was built by one
agent and checked by another that had not seen it built.

**Decided.**

1. *The quality ladder turns off first what only High has.* On a High the page picked by itself, slow frames now
   turn off live light, then the far trees' crown shells, right after the resolution has dropped to 1x and before
   MSAA, bloom or anything Medium also has. The climb back is the exact reverse. Live light may come back once;
   the second time it goes off it stays off for the visit. A High the visitor picked keeps both.
2. *Live light's maps download two at a time, and stop when the stop is left.* The stop at the camera goes before
   maps loaded ahead. The view table, one small file, skips the queue.
3. *Leftover wheel momentum and a tap no longer end a flight part-way.* A flight that begins inside a running wheel
   stream ignores the rest of that stream. A tap pauses the flight while the finger is down, and it carries on
   when the finger lifts. A drag, a new push, a turn the other way, Space and a pause all still take over.
4. *The small effects follow the look.* The furnace mouths, petals, cranes, birds, butterflies, incense smoke, the
   waterfalls' spray and the beams read the same haze numbers and colour as the land. On Low, the ones that cover
   what is behind them take the frame grade as well.

**Why.**

1. An older GPU that got High ended at low resolution, stand-ins and 30 fps while still paying for the heaviest
   shader. Live light gets one more try because a slow stretch can be something else on the PC. It gets no more
   because its cost only shows at a lit stop, after the ladder has stopped watching the climb: without a limit it
   came back and went off again at every stop.
2. A steady scroll through four stops on a slow line downloaded four sets of maps and threw them away (86 MB over
   the whole flight), while the next area's models, which load one at a time, waited.
3. Since the snap went in, ending a flight leaves the camera where it coasts to. That is right for a visitor who
   scrolls. It is wrong for momentum left over from before a key press, and for a tap on a button.
4. These shaders were written for one dusk. They declared the look's numbers but were never handed them, so at the
   summit at night far cranes faded into dusk's pale haze.

**Checked.** Unit tests for each rule (the ladder's order both ways and its retry limit, the download queue, the
wheel tail, the tap, every effect's look uniforms): 2,616 tests, the typecheck and lint pass. Then in a browser
(Playwright, 1600 by 900), a production build of the pull request as pushed against one with the fixes:

1. Stepped by hand at the gate on High, the ladder went resolution, live light, crown shells, MSAA 4 to 2 to 0,
   bloom, render scale, stand-ins, no cards, 30 fps, and back up in reverse. Live light went off with no reload
   and was back within 2 s. The crowns emptied and refilled. After live light had gone off a second time, the
   ceiling had lost it and climbing left it off.
2. With every map slowed by 4 s: before, 6 maps downloaded at once (12 when a stop was left early) and none was
   cancelled. After, never more than 2 at once, and leaving a stop cancelled the 2 on their way and dropped the
   2 to 4 still waiting. The counters added up.
3. A dying wheel stream (59 events, a third of the way to the next stop) with J pressed after the sixth: before,
   the flight was dropped 2 ms after the key and the camera ended between the gate and the mirror, three runs of
   three. After, the scroll stayed at the flight's end and the camera landed on the mirror, two of two. One wheel
   notch 60 ms and 150 ms before J: landed. Five strong wheel turns 400 ms into a flight, and again after a
   250 ms pause in the momentum: the visitor took over both times. A tap 300 ms into a flight: before, stranded
   two of two; after, landed three of three. A drag still took over.
   The first build of this fix failed the momentum run. Chrome was still easing the earlier wheel turns in when
   the key was pressed, and that scroll ended the flight before the next wheel event could mark the tail.
   `wheelSettling` closes that gap, and the run was repeated after it.
4. On the dev server, all eleven stops on Low and four on High compiled with no shader errors. Stills of every
   stop on High and Low, before against after: High changed in at most 0.11% of its pixels (the effects' haze
   colour). Low changed in at most 0.12%, except the abode at night (2.8%), where the waterfall's mist and foam
   now take the night grade.

**Limits.** Not tried on a real trackpad, a phone or a slow GPU. A new push has to be clearly faster than the
momentum to end the tail at once (three to five times its speed); a gentler one waits for a pause. For 600 ms
after leftover wheel input, a scroll from the scrollbar is put back too. When live light goes off the picture
changes in one frame, with no fade (a fade would keep the heavy shader on while frames are slow). Additive lights
(flames, embers, beams) still take no frame grade on Low.

**See.** "Switches and numbers" in [`../sect/live-gate.md`](../sect/live-gate.md) and
[`../sect/veg-shells.md`](../sect/veg-shells.md); "The visitor always wins" in
[`../sect/scroll-snap.md`](../sect/scroll-snap.md); "Tiers" in [`../sect/lux.md`](../sect/lux.md).

### 2026-11-15 · Strong desktops load every place in the background

**Decided.** On a High desktop with 16 GB of memory, once the visitor has pressed Enter the places outside the
window load one at a time, the ones ahead first, until all eleven are held. They stay loaded. What is drawn
follows the same rule as before, so the first view does not change, and later stops draw more places in full
(nine at the mission hall where there were six). The first step down the quality ladder ends it for that visit
and gives the memory back. Phones, tablets, Low, Medium, a line the browser calls 3G or slower and the data
saver are as they were. A far stand-in no longer reads the built mask, so it keeps its rock look whatever has
been loaded.

**Why.** The owner asked what drawing far places in full would cost, saw the numbers and said: "I think the best
thing is to be first load the gate and then ... once we display the gate, we start to slowly load the stuff in
the background until everything". Measured at the gate on his card: holding all eleven takes 2.24 GB of
textures where the window takes 0.87 GB, and the frame costs the same 3.0 ms, because a held place is not drawn
outside the frames it is seen from. Drawing all eleven in full takes 5.5 ms and twice the draw calls for a
change in 1.8 percent of the pixels. So the page holds everything and draws as before.

**Checked.** One agent built it and a second checked it in a browser. The check failed once: the first build
also called a line slow under 5 Mbps, and Chrome's own guess for a new profile is 1.3 to 1.5 Mbps, so nothing
filled on the owner's PC. Only the browser's class of line counts now. The check also found the library's far
stand-in turning into a smooth tube once the library had loaded, which is the built mask above. After both
fixes: all eleven places in 7.4 to 8.8 s after Enter on localhost, never two loading at once. A full scroll
after that had no frame over 50 ms and no stand-in at all (before: 1 to 5 frames over 50 ms, and every place a
stand-in at some point). A far jump during filling took the same time as before. 2,632 tests, the typecheck and
lint pass.

**Limits.** A visitor who scrolls the moment the page opens gains little at first, since a background place
waits for the camera to rest before it is prepared. Not tried on a slow GPU, a card with little memory, a real
slow line, Firefox or Safari. Drawing far places in full is not built; it waits for the owner's eye.

**See.** [`../sect/background-fill.md`](../sect/background-fill.md).

### 2026-11-15 · Far places are drawn in full once they are loaded

**Decided.** Where the page holds every place (the entry above), a place outside its need range now shows as
itself, with its own meshes and textures, in place of its light stand-in. Only the meshes: grass, fires, idle
motion and hotspots stay with the places near the camera. A place first shows this way while the camera rests
or the scene is covered, one per frame. It is the quality ladder's first step down: that step puts the far
places back to stand-ins and keeps everything loaded, and only the next step gives the memory back. It does not
climb back in the same visit. `?far=0` and `?far=1` switch it for a comparison.

**Why.** The owner saw the gate both ways and said yes. Drawn as far scenery a place costs much less than in
the first measurement, which drew its grass and fires too: at the gate 3.4 ms of GPU time a frame against 2.4,
where the first measurement was 5.5. From the library on, facing forward, the far places are behind the camera
and cost nothing.

**Checked.** One agent built it and a second checked it in a browser at all eleven stops, with no blockers.
With the switch off the page draws what the commit before drew. With it on, a full scroll with every place in
had no frame over 50 ms in three runs (1 to 2 with it off), because a far place's buffers are already on the
GPU when the camera gets there. Fast travel's worst frame under the ink fell from about 170 ms to about 30. The
pond and the mirror did not change by a pixel. 19 new tests; 2,662 tests, the typecheck and lint pass.

**Limits.** At the gate the far pillars sharpen one by one in the first six seconds after Enter. Far tree
trunks are too thin to see, so the crowns on one far island seem to hang. Not tried on a slow GPU, where the
ladder's first step takes it off again.

**See.** "Far places in full" in [`../sect/background-fill.md`](../sect/background-fill.md).

---

## Longer write-ups

| Date | Change | Write-up |
|---|---|---|
| 2026-10-24 | Ice-Fire Island's steam rises from the crater; the Five Element flags get three times the texture detail (baked in the round-48 production bake) | [`2026-10-24-icefire-steam-and-element-flags.md`](2026-10-24-icefire-steam-and-element-flags.md) |
| 2026-10-24 | The music volume slider opens and closes on its own | [`../sect/music-volume-slider.md`](../sect/music-volume-slider.md) |
| 2026-10-24 | The jade slip camera steps back | [`../sect/jade-slip-framing.md`](../sect/jade-slip-framing.md) |
| 2026-10-24 | The background with intent: pillars with grassy shelves, a broadleaf canopy, fewer islands, a planned horizon (round 48; shipped as the final production bake) | [`2026-10-24-background-with-intent.md`](2026-10-24-background-with-intent.md) |
| 2026-11-09 | Lux: contact shade, sun shafts and a finish on top of the baked light; torn mist; a clean sun | [`../sect/lux.md`](../sect/lux.md) |
| 2026-11-10 | The flight sweep: how every half second of the film was checked, what changed, what was taken back | [`../sect/flight-sweep.md`](../sect/flight-sweep.md) |
| 2026-11-10 | Round 56: rim teeth, lawn steps, stair walls, the sword's tones, the bridge's sag (baked the same day) | [`../scene/form-r56.md`](../scene/form-r56.md) |
| 2026-11-10 | Round 57: the bake's key light, the richer grade, rounder mist; the test and the rollout | [`../scene/light-r57.md`](../scene/light-r57.md) |
| 2026-11-10 | Far trees as lit crowns built in code: the data, the shader, the switch with the baked cards | [`../sect/veg-shells.md`](../sect/veg-shells.md) |
| 2026-11-10 | Far spires that read as rock: why the backdrop was bare, the spire-sized layer, the stand-ins' gate | [`../sect/far-rock.md`](../sect/far-rock.md) |
| 2026-11-10 | Live light, first at the gate and then at every stop: the maps from the bake, two shadow maps, Blender's view as a table, the bake's bounced light and far shadows, how it was checked against the bake, three reviews | [`../sect/live-gate.md`](../sect/live-gate.md) |
| 2026-11-11 | Surfaces: wear and dirt on paving, weathering on walls and marble, lawns that vary, rock beds; what went wrong on the way | [`../sect/surfaces.md`](../sect/surfaces.md) |
| 2026-11-12 | Round 58, near trees: why they were smooth blobs, the leaf sprays kept, the tree build's run and cost, the box's two faults | [`../scene/trees-r58.md`](../scene/trees-r58.md) |
| 2026-11-12 | Round 59, rock: the texel floor kept for the next bake, the rebuilt material and the bake-time relief tested and switched off, the box run and its cost, what the next rock round starts with | [`../scene/rock-r59.md`](../scene/rock-r59.md) |
| 2026-11-13 | Round 60, rock: a seamless tile from the mountainside model, the blind stills review with a placebo, the production bake, the page test, and why tuning stopped | [`../scene/rock-r60.md`](../scene/rock-r60.md) |
| 2026-11-13 | Looks and the journey: the four looks, the arc table, how the look follows the camera with no shader built, the tiers, the switches | [`../sect/lux.md`](../sect/lux.md) |
| 2026-11-13 | Lighting a stop without freezing the page: the four causes of the shader waits, the fix, the timing before and after, what is left | [`../sect/live-gate.md`](../sect/live-gate.md) |
| 2026-11-14 | A smooth flight: the visitor flight as the measure, the three causes of stutter, the GPU queue and banded uploads, the Enter wait, the worker decode, old against new | [`../sect/smooth-flight.md`](../sect/smooth-flight.md) |
| 2026-11-14 | Scroll snap: why scenes felt stuck, the short stops, which stop a rest glides to, the glide that keeps the camera's speed, what was checked | [`../sect/scroll-snap.md`](../sect/scroll-snap.md) |
| 2026-11-15 | Every place loads in the background on a strong desktop: what holding and drawing cost, who gets it, how it stays out of the way, the stand-in that lost its rock | [`../sect/background-fill.md`](../sect/background-fill.md) |
| 2026-11-15 | Far places in full: what a far place has, when it first shows, the ladder's order, the cost stop by stop, what was checked | [`../sect/background-fill.md`](../sect/background-fill.md) |
| 2026-11-09 | Round 55: the gate seen square on, and prop moves at four stops (designed and scripted, not baked yet) | [`../scene/placement-r55.md`](../scene/placement-r55.md) |
