# Sect Theme Music: Suno prompts

This folder holds ready-to-paste Suno prompts for the background music of `/sect`, the scroll-driven fly-through of the Sun Moon Divine Cult (日月神教), the sect from Jin Yong's *The Smiling, Proud Wanderer* (until October 2026 the Ming Sect 明教 of *Heaven Sword and Dragon Saber*). There is one file per area, plus one for the loading screen. Every track is instrumental and led by traditional Chinese instruments.

Nothing here plays on the site yet. These files only help you make the music.

## Files

| File | Area | Site section |
|---|---|---|
| `00-loading.md` | Loading screen | (while the 3D scene loads) |
| `01-gate.md` | Mountain Gate 山门 | Hero |
| `02-mirror.md` | Heart-Mirror Terrace 心镜台 | About |
| `03-forge.md` | Artifact Forge Peak 炼器峰 | Projects |
| `04-arena.md` | Sword-Discussion Arena 论剑台 | Hackathons |
| `05-mission.md` | Mission Hall 任务殿 | Experience |
| `06-library.md` | Scripture Pavilion 藏经阁 | Education |
| `07-steles.md` | Stele Forest 碑林 | Skills |
| `08-scroll.md` | Jade Slip Pavilion 玉简阁 | Resume |
| `09-formation.md` | Grand Sect-Protecting Formation 护宗大阵 | Architecture |
| `10-abode.md` | Cave Abode 洞府 | Personal |
| `11-summit.md` | Moon-Gazing Summit 望月台 | Contact |

## How to use a prompt in Suno

1. Open Suno and click **Create**. Switch to **Custom** mode (on the website it may be labelled **Advanced**).
2. Turn **Instrumental** on.
3. Copy the **Style of Music** block from the area file into the Styles box.
4. Open the advanced options. Paste the **Exclude styles** block. Set **Weirdness** and **Style Influence** to the numbers in the file.
5. Paste the **Structure** block into the Lyrics box. It starts with `[Instrumental]` and has only square-bracket tags, so there are no words to sing.
6. Type the suggested **Title**. The title does not change the sound.
7. Pick the newest model you have (v5 or later). Click **Create**.
8. Each click gives you two takes. Make two or three rounds, then keep the best take.

**Lyrics box hidden?** On some Suno versions the Lyrics box disappears when Instrumental is on. You have two choices. Skip the Structure; the Style prompt alone still works. Or turn Instrumental off, paste the Structure (it starts with `[Instrumental]`), add "instrumental" to the Style, and keep the vocal words in Exclude styles. Every file's Exclude list starts with the same vocal blockers: "vocals, singing, humming, choir, chant, female vocals, wordless vocals". Listen for stray humming if you do that.

**Fix one thing at a time.** If a take is wrong, change one word or one slider, not the whole prompt. Then you know what fixed it. Each file has an "If it comes out wrong" list.

**No names.** The prompts never name an artist, composer, film or game. Suno blocks those, so keep it that way if you edit them.

## The shared plan

### One set of five notes for every track

Chinese music often uses a five-note scale. Every track here uses the same five notes: **D, E, F#, A, B**. These are the notes of D major pentatonic.

Any of the five notes can act as "home". Moving home changes the mood, but the notes stay the same. Chinese theory gives each home note a mode name. Because every track shares the same notes, any two tracks can overlap during a crossfade without sounding out of tune.

| Mode | Home note | What Suno is told | Mood |
|---|---|---|---|
| Gong 宫 | D | D major pentatonic | Bright, settled, "home" |
| Shang 商 | E | E Dorian pentatonic (shang mode) | Sturdy, open, a little questioning |
| Jue 角 | F# | pentatonic centered on F# (jue mode, D major key signature) | Unusual, floating, arcane |
| Zhi 徵 | A | A Mixolydian pentatonic (zhi mode) | Heroic, bold, forward |
| Yu 羽 | B | B minor pentatonic (yu mode) | Minor, wistful, ancient |

The prompts use Western words like "Dorian" and "Mixolydian" because Suno understands them better than the Chinese mode names. Every one of those scales fits inside the D major key, so they all agree.

**Key check:** Suno does not always obey the key. After you pick a take, check it with any free online key finder. Key finders only know major and minor keys, and our five notes fit inside six of them. So a correct take can read as D major, G major, A major, B minor, E minor or F# minor, whatever its home note is. All six are fine. Only shift the pitch if it reads something else, such as C major, E major or E-flat major. Use Audacity (Effect > Pitch and Tempo > Change Pitch). A shift of one or two semitones sounds fine. A bigger shift starts to sound odd, so regenerate instead.

### Mode and tempo for each track

BPM means beats per minute. "Bar" is one group of four beats. The bar length matters when you trim loops (see below).

| File | Mode | Home | BPM | One bar lasts (at prompt tempo) | Lead instruments | Fullness |
|---|---|---|---|---|---|---|
| 00-loading | Gong | D | 84 (half-time feel) | 2.857 s | xiao, guqin | Very sparse |
| 01-gate | Gong | D | 84 | 2.857 s | dizi, guzheng, erhu | Medium |
| 02-mirror | Yu | B | 66 | 3.636 s | guqin, xiao | Sparse |
| 03-forge | Shang | E | 108 | 2.222 s | yangqin, pipa, erhu, drums | Full |
| 04-arena | Yu | B | 140 | 1.714 s | suona, erhu, gehu, guzheng, yangqin, dagu drums | Fullest |
| 05-mission | Zhi | A | 100 | 2.400 s | erhu, guzheng, temple bell | Medium |
| 06-library | Shang | E | 76 | 3.158 s | xiao, guzheng, liuqin | Sparse |
| 07-steles | Yu | B | 70 | 3.429 s | xun, guqin, bronze bells | Sparse |
| 08-scroll | Shang | E | 92 | 2.609 s | guzheng, dizi, yangqin | Medium-light |
| 09-formation | Yu | F# | 60 | 4.000 s | dagu drums, gong, deep horns, xun, guqin | Sparse, then fullest |
| 10-abode | Gong | D | 72 | 3.333 s | zhongruan, pipa, erhu | Sparse |
| 11-summit | Gong | D | 84 | 2.857 s | erhu, dizi, guzheng | Medium-full |

The flight starts and ends on D (gong), the "home" mode. The mission's heroic mood sits on A. The arena uses B minor (yu) for a cold, godlike grandeur. The steles use a darker mode. The formation uses F# minor (yu) for slow, ancient weight. Calm areas are sparse so the page does not feel busy. The forge and arena are allowed to be full.

### The sect theme

One tune ties the whole site together. It plays at the gate, comes back at the summit, and is hinted on the loading screen.

In words: a bamboo flute (dizi) melody climbs up the scale, leaps to the high octave, then steps back down and settles on home. If you want it in notes, it is roughly: D E F# A, leap to high D, then B A F# E D.

Suno cannot read notes reliably. So you make the theme once, then reuse that audio:

1. **Make the gate first.** Generate `01-gate.md` until one take has a clear, catchy dizi melody you like. That melody is now the sect theme.
2. **Make the summit from the gate.** Open the gate take's menu and choose **Cover** (it may sit under Remix). Paste the summit Style prompt and Structure. Cover keeps the tune but changes the sound. Push Audio Influence up if the theme drifts.
3. **Make the loading bed from the gate.** Same thing with `00-loading.md`. You want only a hint of the theme, so keep Audio Influence low to medium.
4. **No take you like?** Hum or play the theme into your phone (any free piano app works), upload the clip in Suno, and Cover it with the gate prompt. That gives Suno your exact tune to start from. Keep Instrumental on. Set Audio Influence to about 55-70% so Suno follows the tune. Hum in time, and keep the BPM (84) in the Style.

**Extend** is useful too. If a summit take starts well but ends early, Extend it from a good spot instead of starting over.

**Personas** are for singing voices. These tracks have no vocals, so skip them.

## Rules every track follows (so it works as background music)

- One mood the whole way. No slow-down, no tempo change, no big ending. Two exceptions: the arena ends on a big suona finale, and the formation goes from calm to huge and back to calm. Both keep one tempo, so the loop maths still work, and each loop point lands somewhere that matches (drum hits for the arena, calm for the formation).
- No long silent intro. The texture starts within the first few seconds.
- No solo drum breaks. They sound jarring when the loop restarts.
- About 2 to 3 minutes. Suno cannot set length exactly, so trim if it runs long.
- Ends on its home note so the loop point sounds natural.
- Mixed soft. These tracks sit under the visuals, not on top of them.

## Export and trim a loop

You can do all of this in Audacity, which is free.

1. **Download** the take. Use WAV if your plan has it, otherwise MP3.
2. **Find the loop start.** Zoom in on the waveform. Pick the first strong beat where the full sound is already playing. Cut everything before it.
3. **Find the loop end.** The loop should be a whole number of bars long. First check the take's real tempo with any online BPM finder (or Audacity's Analyze > Beat Finder). Suno often misses the asked-for tempo by a few BPM. One bar = 240 / real BPM seconds. Use that number, not the table, when the two differ. If they match, use the "One bar lasts" column above. Example: the gate is 84 BPM, so one bar is 2.857 s. Sixty bars is 171.4 s, about 2 min 51 s. Set the end that many seconds after the start, then nudge it onto the nearest beat.
4. **Smooth the loop point.** Add a tiny fade (about 10 ms) at the very start and end. That stops a click. For a softer join, copy the last 1 to 2 seconds onto a second track at the start and crossfade them.
5. **Even out loudness.** Use Effect > Volume and Compression > Loudness Normalization. Set it to -17 LUFS for every track. LUFS measures how loud music feels. Background music usually sits between -18 and -16. Using one number for all tracks means the volume does not jump when the visitor flies to the next area.
6. **Export** as MP3 at 128 to 160 kbps. MP3 plays in every browser. You can also export an `.ogg` copy if you want smaller files.

If you like the command line, ffmpeg can do the loudness step:

```
ffmpeg -i gate.wav -af loudnorm=I=-17:TP=-1.5:LRA=11 -b:a 160k gate.mp3
```

## File names for the site

When you add music to the site, name the files after the area ids already used in `client/src/lib/sect/areas.ts`:

```
client/public/sect/audio/loading.mp3
client/public/sect/audio/gate.mp3
client/public/sect/audio/mirror.mp3
client/public/sect/audio/forge.mp3
client/public/sect/audio/arena.mp3
client/public/sect/audio/mission.mp3
client/public/sect/audio/library.mp3
client/public/sect/audio/steles.mp3
client/public/sect/audio/scroll.mp3
client/public/sect/audio/formation.mp3
client/public/sect/audio/abode.mp3
client/public/sect/audio/summit.mp3
```

That folder does not exist yet. Create it when you have the files.

Size check: a 2.5-minute MP3 at 128 kbps is about 2.4 MB. Twelve tracks is roughly 29 MB. The site should load only the current and next area's track, not all twelve at once.

## Playing the music on /sect is a separate step

These prompts do not change the site. Adding playback is its own job. When that happens:

- Start muted, with a visible sound toggle. Browsers block autoplay with sound until the visitor clicks something.
- Crossfade over 2 to 4 seconds when the camera moves into a new area.
- Remember the visitor's mute choice.

## Rights

What you can do with Suno songs depends on your plan at the time you make them. Check Suno's current terms before you publish the tracks on the site.
