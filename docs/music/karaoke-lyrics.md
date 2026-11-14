# Soundtrack and timed lyrics panel

Every soundtrack track has an openable left-side panel dressed like the stops' panels. It names the
song, its show, its artist and whether it is sung, and carries the owner's note on each sung track.
The nine vocal tracks also show the complete song and follow the Web Audio clock, marking the
current original and English lines together, with the line being sung filling word by word. Pinyin
is not displayed.

## Data contract

The source handoff file is named by source ID and contains song metadata plus ordered lines:

```json
{
  "song": "Example",
  "show": "Example show",
  "id": "source-id",
  "language": "zh",
  "lyrics_source": "https://example.com",
  "lines": [
    {
      "start": 10.0,
      "end": 12.0,
      "text": "示例",
      "pinyin": "shì lì",
      "en": "Example",
      "words": [
        { "w": "示", "start": 10.0, "end": 11.0 },
        { "w": "例", "start": 11.0, "end": 12.0 }
      ]
    }
  ]
}
```

`language` is `zh` or `en`. `estimated: true` marks a line whose placement was inferred between
neighbouring lines. Joining every `words[].w` must reproduce `text` exactly.

Prepared files served to the browser retain only `song`, `show`, `language` and `lines`. Source ID,
local MP3 name and source URL are validation inputs, not runtime fields.

The parser rejects a file when:

- song, show, language or source validation fields have the wrong type;
- line times are invalid, out of order or overlapping;
- a word falls outside its line;
- word times run backwards; or
- joined word units do not reproduce the displayed text.

A bad or missing lyric file never stops its music track.

## Timing

For audio time `t`, the current line satisfies `start <= t < end`. Gaps display nothing.

The line is chosen by line timing. Inside it, each word's own `start` and `end` drive the word by
word fill (`lyricWordAt`, `lyricUnitProgress`). Timing is checked against the final
normalized MP3 because processing or replacing audio can move the decoded timeline.

The music engine exposes an imperative playback snapshot with the dominant track, exact looped
position, crossfade gains and suppression state. The panel samples that clock with
`requestAnimationFrame` and changes React state only when the active line or track changes.

## Display

The panel is `client/src/app/sect/experience/karaoke-lyrics.tsx`, styled by the `.sect-lyrics-*`
block in `client/src/app/sect/sect.css`.

- **The slip.** A title slip at the left edge opens the drawer: 乐曲 written upright in gold, "Music"
  under it, on a control's plate with the small gold cloud corners. Every track has it, the loading
  screen's and the instrumentals' too. It reports its state with `aria-expanded` and steps aside
  while the drawer is open (the drawer covers its place).
- **The drawer.** Rice paper over ink, 3 px corners, the large gold cloud corners and no backdrop
  blur, as on the stops' panels. Its close button is a bare cross in the corner (a second framed
  box inside the frame looked crowded). It fades in and slides a short way from the left. On wide
  screens it is a card at most 37rem tall, not a wall down the screen.
- **The head.** A "Now playing" eyebrow ("Soundtrack" while the sound is off, which is how every
  visitor starts; the drawer then offers a "Turn on sound" button under the note), then the song's
  title. A Chinese title is written in the
  brush hand, then a short gold dash, its English in italics (`SONG_TITLES_EN` in
  `client/src/lib/sect/song-notes.ts`) and the red seal closing the line. Where they do not fit on
  one line, the dash, the English and the seal take the next line together. A Latin title (*Throne
  of Glory*) is in the stops' serif, with no seal. A
  gold brush stroke under it, then one or two quiet lines: the show (in the lyrics' brush hand), then
  the artist and "Sung in Chinese", "Sung in English" or "Instrumental". An artist given as "Not credited" is left out. The credits are a
  `dl` whose terms (From, Artist, Vocals) are only for screen readers.
- **The note.** The owner's note on a sung track (below) comes next, centred, in italic serif between
  two brush rules. It is a button: a press fades the English out and its Chinese in (in the lyrics'
  brush hand), and a second press brings the English back. Each song starts in English. The Chinese
  versions sit beside the English in `song-notes.ts`. Instrumentals have none: their card ends at
  the credits.
- **The note's Chinese** is written as an inscription is: upright columns, read from the right,
  hung from one line at the top. `noteColumns()` in `song-notes.ts` cuts the columns: at most seven
  characters each, filled evenly, and a comma or full stop never opens one. The block sits in the
  middle of the drawer. On a small phone the characters shrink until every column fits. The note
  is as tall as the side it shows, so the Chinese (taller) opens the note's place and the lyrics
  under it move down; the English keeps its own height. The lyrics stay written across: sung
  lines are read that way everywhere. A screen reader gets the Chinese in one piece.
- **The lyrics.** The complete ordered song. A Chinese line is in the brush hand with `lang="zh"` (below), its
  English under it, smaller, in the body face. An English-only line is one line in the serif, never
  the same text twice. Pinyin is not shown.
- **The line being sung** fills with gold ink word by word, over paper white for the words still to
  come: the words already sung are gold, and the one being sung fills from its left as its time
  passes. Its English turns paper white, and a short gold brush stroke is drawn down in the margin
  at its left (the lines themselves sit flush with the head). The other lines fade the farther they are from it. With nothing being
  sung (a gap, muted, before the first line) every line rests at the same middle strength. The line
  being sung scrolls toward the middle.
- **What scrolls.** On tall screens only the lyrics scroll, under the head, with both edges fading
  out. On phones and short screens the whole drawer scrolls, so the head goes up out of sight while
  a song plays. The scroll bar is a thin gold one.
- While lyrics load, the turning ink ring and "Loading".
- During a crossfade, the panel follows the track with the greater audible gain and keeps the
  current track on an exact tie.

乐曲 and the songs' Chinese titles are in the brush font's character list
(`BRUSH_EXTRA` in `client/src/lib/sect/brush.ts`). After a song changes, add its title there and
rerun `client/scripts/subset-brush-font.mjs` with the full Ma Shan Zheng TTF.

The lyric lines, the shows' names and the notes' Chinese use a second cut of the same font, `sect-lyrics-brush.woff2`
("Sect Lyric Brush" in `sect.css`): every Chinese character in the lyric files, the manifest and
`song-notes.ts`, about 300 KB. It is not preloaded; the browser fetches it the first time the drawer
is opened (`data-brush`, which then stays on so a closing drawer keeps its hand), and the CJK serif stands in until then and for any character it
lacks. After the songs or their lyrics change, rerun
`client/scripts/subset-lyrics-font.mjs <MaShanZheng-Regular.ttf> <server/.music-prepared>`.
Check that the prepared folder holds every sung track first: the script only keeps the characters
it finds there, so an old folder drops a newer song's characters.

Ma Shan Zheng has no forms for upright columns: its full stop sits at the foot of its square on the
left and its comma at the foot in the middle. In a column they belong in the upper right, under the
character they follow. `client/scripts/vertical-punctuation.py` (run by the subset script) adds a
copy of each moved there and a `vert` feature that swaps it in. Browsers turn `vert` on for upright
text in a column by themselves, and lines written across are unchanged.

### Where it sits

On phones the slip waits while the intro's title is up and comes in at the first stop (it sat over
the title's plate). On wide screens it lines up with the other plates, 1.25rem from the left edge.
On a phone held sideways it starts at 4.25rem, clear of the top bar.

- **Phone held upright:** the slip under the place row, level with the sound toggle on the right.
  The drawer starts under the place row and keeps left of the sound toggle's column.
- **Short screen (a phone on its side):** the slip right under the top bar, so 乐曲 stays in sight
  over a stop's panel. The drawer starts under the place row.
- **Wider screens:** the slip about a third of the way down. The drawer starts under the top bar and
  its hint and stops above the Recentre button.
- **Loading screen:** the slip comes up over the veil. On a phone it moves to the top-left corner,
  clear of the screen's centred column. On a phone it goes as soon as the screen starts to fade
  after Enter (`data-leaving` on the veil), so it is not left over the intro.
- **Stops' panels.** The closed slip sits under them, so where a long panel reaches it on a small
  screen, the panel's words stay on top. While the drawer is open, a panel on the left moves over
  beside it on screens 60rem (960 px) wide or more. On narrower screens there is no room for both, so
  the stop's panel steps away until the drawer closes, as it does behind a reader.

Checked on 2026-11-09 at 320×568, 375×812, 768×1024, 1440×900, 812×375 and 667×375, with the music
API stubbed.

## Song notes

The owner wrote a short note for each sung track. They live in
`client/src/lib/sect/song-notes.ts` and must stay word for word, curly apostrophe included.

| Key | Song | Note |
|---|---|---|
| `mirror` | Throne of Glory | Everyone wants to reach the throne, but only the one who gets there finds out how empty it is. Maybe sadness is all it gives, so it’s better to let the glory go on without you and rest. |
| `arena` | 降临 | Trouble finds a person whether or not he is ready for it. Since it comes either way, one may as well walk into the arena on purpose and stay standing until it is over. |
| `mission` | 璀璨冒险人 | People who say to take the safe way round mostly mean well, but they do not have to live your life. A few scars are worth it to see what the world is really like. |
| `library` | 化凡 | To grow, a person sometimes has to put down what he has and live plain for a long while. A teacher can only hand over so much, and the rest is learned out in the world. |
| `steles` | 光之少年 | A hero is just an ordinary person who kept going after getting hurt. Skills come the same way, by trying again until something works. |
| `scroll` | 浩瀚 | Being looked down on matters little to someone who already knows what he is good for. The belief has to come before there is any proof of it. |
| `abode` | 逍遥 | Fame and money are easier to let go of once you see how quickly the years pass. Success means little with no one to share it, and one person to grow old with is worth more than all of it. |
| `summit` | 破茧 | The world does not stop when you lose someone. It still expects you to get up and keep going. The only way through is to hold on to someone, and to be that person for somebody else too. |

`song-notes.test.ts` checks that every key is a music key and that the notes cover exactly the
tracks `server/music_manifest.json` serves lyrics for.

## When it hides

The panel remains available while music is muted, at zero volume, loading, suppressed by voice or
video, or the tab is hidden; in those states no lyric row advances or highlights. It hides in page
view, behind readers or the map, during fast travel, and on error screens.

## Accessibility

- Mark the active bilingual row with `aria-current`.
- Announce only the active complete line through a visually hidden polite live region.
- Make the closed drawer inert and `aria-hidden` so its close button and text are not focusable.
- Opened from the keyboard (Enter or Space on the slip), the focus moves to the drawer's close
  button. Escape, with the focus in the drawer, or the close button pressed from the keyboard closes
  it and puts the focus back on the slip. That Escape only closes the drawer: the view stays turned
  (one Escape, one thing, as for the volume slider). A mouse or touch open puts the focus on the
  drawer itself, with no ring (the slip that held it is hidden), so Escape still closes it.
- "Turn on sound" in the drawer goes away once the sound is on. Its focus moves first: to the close
  button from the keyboard, to the drawer from a click or tap.
- Lyrics whose request was cut short (the panel hid while they loaded) are asked for again the next
  time the panel shows. Only a finished answer is kept.
- Reduced-motion mode disables drawer, slip, row and auto-scroll animation.
- Forced-colour mode drops the fades, shows every line at full strength and marks the active line
  in the highlight colour.

## QA

Listen through all nine tracks before release. Priorities are the estimated *Throne of Glory*
lines, near-zero units, loop wrap, pause/resume, and the two corrected English translations in
`降临` near 2:13 and 2:17.
