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

## Longer write-ups

| Date | Change | Write-up |
|---|---|---|
| 2026-10-24 | Ice-Fire Island's steam rises from the crater; the Five Element flags get three times the texture detail (needs a bake) | [`2026-10-24-icefire-steam-and-element-flags.md`](2026-10-24-icefire-steam-and-element-flags.md) |
| 2026-10-24 | The music volume slider opens and closes on its own | [`../sect/music-volume-slider.md`](../sect/music-volume-slider.md) |
| 2026-10-24 | The jade slip camera steps back | [`../sect/jade-slip-framing.md`](../sect/jade-slip-framing.md) |
