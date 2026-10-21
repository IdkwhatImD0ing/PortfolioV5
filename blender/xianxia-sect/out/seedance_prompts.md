# Moonlit Sect: Seedance prompts (8 clips, 72 s total)

Each clip matches one segment of the Blender blocking flight. The blocking clips are in
`out/video/seg01.mp4` … `seg08.mp4`, and each clip's first and last blocking frames are in
`out/stills/segNN_start.png` and `segNN_end.png`.

## How to use them (saves credits)

> **Updated 2026-10-10.** The full research and pipeline are in
> `blender/xianxia-sect/docs/ai-video-consistency.md`. The main correction: Seedance's
> first/last-frame mode **cannot** be combined with a reference video. Use **reference
> mode** instead.
>
> These prompts were written for the earlier 8-clip camera without the flyer. The current
> video is `out/video/chase_blocking.mp4`, with a third-person flyer and a smoother camera.
> Rewrite them for that video, and for the 4 longer clips the research recommends, before
> spending credits.

1. **Generate clip 1 first and judge it** before spending on the rest.
2. **In reference mode, attach to every clip:**
   - the blocking clip as @Video 1, with the line "Use Video 1 only for camera, timing and framing"
   - the saved flyer Element
   - the approved keyframe of each area in the clip
   - the previous clip's approved last frame as its "opening state"
3. **Don't describe camera moves in the text.** The reference video carries them. Describe
   the look, the flyer and what's in each area.
4. **Drafts at 480p, finals at 720p (or 1080p).** 16:9.

## Style block (paste at the start of every clip's prompt)

> Cinematic continuous aerial flythrough, one unbroken shot, no cuts. A celestial xianxia
> immortal sect built on a range of colossal karst mountains that float high in the sky above
> an endless sea of clouds; the mountains' undersides break into hanging rock and roots, with
> small floating islets, waterfalls pouring into the void, and drifting mist. Traditional
> Chinese palace architecture: vermilion lacquered columns, deep teal glazed tile roofs with
> sweeping upturned eaves, gold ornaments, white marble terraces and balustrades, red lanterns.
> Golden-hour sunlight from the left, soft god rays, warm highlights, cool blue-violet sky
> ahead. A colossal full moon in the sky. Glowing jade-cyan spiritual energy, white cranes.
> Photoreal, epic donghua quality, smooth stabilised camera, 24 fps.

---

## Clip 1: Mountain Gate → Heart-Mirror Terrace (hero, about) · 12 s

> 0–1 s: the camera bursts out of a soft cloud bank; a long white marble stairway climbs
> steeply ahead toward a five-bay red-and-teal paifang gate at the top, karst peaks on both
> sides, the giant moon upper right. 1–4 s: fly fast up the stair axis, paired stone lanterns
> streaming past, the gate growing until it fills the frame: guardian stone lions, two tall
> sword-shaped monoliths with glowing cyan runes, tall banners. 4–5 s: fly straight through the
> tall centre opening of the gate, the gold plaque passing overhead. 5–7 s: rise over a white
> marble plaza and curve slightly left toward the next floating peak. 7–9 s: sweep high over a
> still reflecting pond with a hexagonal pavilion and a zig-zag bridge; a giant round polished
> bronze mirror on a carved stand catches the sun and glows, mirrored in the water, a pink
> peach blossom tree beside it. 9–12 s: bank right over a cloud-filled chasm between floating
> mountains; another sect peak appears ahead.

## Clip 2: Artifact Forge (projects) · 9 s

> 0–1 s: a floating mountain peak ahead topped by a two-tier forge hall with dark roofs and
> smoking chimneys, red side halls, a white stone plaza, clouds wrapping the cliff. 1–3 s: close
> in; in front of the hall a colossal bronze ding cauldron glows molten orange, sparks rising,
> and a slowly rotating ring of fifteen floating magical artifacts circles it: swords, bells,
> mirrors, orbs, a fan, a seal, a gourd, a jade disc, a compass, each with a faint jade glow.
> 3–5 s: glide past the artifact ring, the cauldron centred, embers drifting toward the lens.
> 5–8 s: pan left past rock and cloud. 8–9 s: reveal a round arena island floating alone over a
> gap in the range, its inverted rocky underside and hanging roots visible, massive chains
> trailing away, a giant stone sword towering on it.

## Clip 3: Sword Arena → Mission Hall (hackathons, experience) · 10 s

> 0–1 s: approach the floating arena at rim height, chains and hanging roots below. 1–3 s: cross
> low over a vast circular stone dueling platform with a glowing taiji and bagua inlay, a ring of
> dozens of colourful silk banners rippling on tall poles on both sides; a 38-metre stone sword
> rises ahead and slides past on the left. 3–5 s: a grand double-eave teal-roofed hall on the
> next peak; in front stands a tall carved mission wall where seven large glowing jade tablets
> hang on red cords with tassels among rows of small wooden tablets, bell and drum towers at the
> sides. 5–6 s: fly straight at the jade tablets, then crane up over the hall roof. 6–10 s: bank
> right into a fast glide over mist and low cloud, a white arched marble bridge on the right,
> a tall pagoda appearing ahead.

## Clip 4: Scripture Pagoda (education) · 9 s

> 0–2 s: a seven-storey red octagonal pagoda library on a floating peak; three of its floors
> glow warm gold from inside; glowing scrolls and books drift in a slow spiral around it; a lotus
> pool and two small study pavilions at its foot. 2–4 s: sweep close past the pagoda's side,
> floating scrolls and spirit motes passing near the lens, upturned eaves stacking up out of
> frame. 4–6 s: curve left away from the pagoda, past a towering karst pillar. 6–9 s: reveal a
> walled stone courtyard ahead with a white central aisle framed by covered red corridors and a
> teal pavilion at the far end.

## Clip 5: Stele Forest → Jade Slip Pavilion (skills, resume) · 10 s

> 0–1 s: descend toward the courtyard. 1–2 s: glide low down the white central aisle between
> rows of tall carved stone steles on stone turtle bases, their engraved glyph columns glowing
> cyan, blue, violet, green, red and amber; a teal pavilion with a golden master stele centred
> ahead. 2–3 s: rise over the pavilion roof. 3–5 s: glide toward the next peak. 5–7 s: a
> colossal unrolled scroll of jade bamboo slips, twenty metres wide and gently curved, floats
> over a glowing rune circle, covered in columns of glowing golden calligraphy, a red two-storey
> pavilion beside it on the cliff edge; the scroll fills the frame. 7–8 s: pass over the
> pavilion roof, turning right. 8–10 s: climb past a karst pillar with the giant moon behind it;
> a glowing dome appears ahead.

## Clip 6: Grand Formation (architecture) · 7 s (or 8 s)

> 0–1 s: rise toward a floating peak crowned by a vast circular plaza under a faint translucent
> dome, a floating jade core at its centre sending a beam of cyan light into the sky. 1–2 s:
> climb high over the dome. 2–4 s: look straight down: the plaza is a glowing magical formation
> array that reads like a system diagram: concentric rune rings, a central hub, eight tall
> array-flag pillar nodes, four colour-coded clusters (red, green, blue, white) linked by beams
> of light and golden cross-links. 4–6 s: descend past the light pillar. 6–7 s: a tall cliff
> with a waterfall ahead.

## Clip 7: Cave Abode (personal) · 8 s

> 0–2 s: approach a sheer 60-metre cliff on a floating peak, twin karst towers beside it, a tall
> waterfall plunging into a misty koi pool. 2–4 s: glide sideways along the cliff face past the
> waterfall. 4–5 s: centred on a round moon gate carved into the rock with a gold ring and a
> plaque, a white marble stair leading to it, a red-stilted wooden balcony with a small teal tea
> pavilion, peach blossom trees in the foreground, lantern light from inside the cave, a crane
> resting on a rock. 5–8 s: pan right and climb past the end of the cliff; the moon shows between
> karst towers; the highest summit with a marble stairway appears ahead.

## Clip 8: Moon-Gazing Summit (footer) · 8 s

> 0–2 s: the highest floating peak ahead, a marble stairway up its cliff, a giant white
> crescent-moon arch framing a round two-tier pavilion with moon-white tiles on top. 2–4 s: rise
> over the circular white marble terrace, a lone ancient pine leaning over the edge; slow down,
> turn right and tilt up. 4–6 s: looking up past the pavilion's silver finial, a crane gliding
> across, the colossal glowing full moon filling most of the frame. 6–8 s: very slow drift
> forward and up toward the moon until it fills the frame, only the finial tip at the bottom.
> Calm, awe-struck ending.
