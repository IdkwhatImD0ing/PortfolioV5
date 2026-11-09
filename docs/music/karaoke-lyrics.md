# Soundtrack and timed lyrics panel

Every soundtrack track has an openable left-side panel with its title, artist, source show and
vocal type. The eight vocal tracks also show the complete song and follow the Web Audio clock,
highlighting the current original and English lines together. Pinyin and word-level karaoke are not
displayed.

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

Word timings remain in the source and served schema so the alignment can be regenerated without a
format migration, but the interface uses line timing only. Timing is checked against the final
normalized MP3 because processing or replacing audio can move the decoded timeline.

The music engine exposes an imperative playback snapshot with the dominant track, exact looped
position, crossfade gains and suppression state. The panel samples that clock with
`requestAnimationFrame` and changes React state only when the active line or track changes.

## Display

- Every track, including loading-screen and instrumental music, exposes a compact `乐曲 / Music`
  button at the left edge.
- The button opens a left-side drawer and reports its state with `aria-expanded`.
- The drawer begins with the song title, artist, source show and whether it is instrumental,
  Chinese vocals or English vocals.
- The drawer contains the complete ordered lyrics, not only the current line.
- Each row contains the original Chinese line and its English translation; pinyin is not shown.
- The active row highlights both languages at the same time and scrolls toward the centre.
- English-only lines and songs show one English line instead of duplicating the same text.
- Instrumentals keep the same metadata panel and state that the track has no lyrics. During vocal
  lyric gaps the full list remains visible with no highlighted row.
- During a crossfade, the panel follows the track with the greater audible gain and keeps the
  current track on an exact tie.

The drawer slides from the left on desktop and phones, away from the map and voice controls on the
right. It stays clear of the compact top rail and lower controls and respects safe-area insets.

## When it hides

The panel remains available while music is muted, at zero volume, loading, suppressed by voice or
video, or the tab is hidden; in those states no lyric row advances or highlights. It hides in page
view, behind readers or the map, during fast travel, and on error screens.

## Accessibility

- Mark the active bilingual row with `aria-current`.
- Announce only the active complete line through a visually hidden polite live region.
- Make the closed drawer inert so its close button and text are not focusable.
- Reduced-motion mode disables drawer, row and auto-scroll animation.
- Forced-colour mode preserves the distinction between active and inactive rows.

## QA

Listen through all eight tracks before release. Priorities are the estimated *Throne of Glory*
lines, near-zero units, loop wrap, pause/resume, and the two corrected English translations in
`降临` near 2:13 and 2:17.
