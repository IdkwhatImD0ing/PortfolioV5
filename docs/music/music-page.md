# The music page (`/music`)

`/music` is a player for the site's soundtrack. It has no 3D scene. It lists the twelve songs, shows
the open song's credits and note, shows its whole lyrics, and has the usual controls.

The flight's own soundtrack drawer is described in [`karaoke-lyrics.md`](karaoke-lyrics.md). This
page reuses its look and its lyric data.

## What is on the page

- **Top bar.** The site's seal and "Back to the sect" (one link to `/`), and the page's name, 乐曲.
- **The card.** The open song as the drawer shows it: title in the brush hand, its English, the
  show, the artist, and the owner's note (press it to swap English and Chinese). Under it, the
  songs in the flight's order. Press one to play it.
- **The lyrics.** Every line of the song, Chinese with its English under it. They can be read
  without playing anything. While the song plays, the line being sung fills with gold word by word
  and moves toward the middle. A click or tap on a line plays from that line.
- **The bar.** Previous, play or pause, next, the seek line with the time on both sides, repeat,
  the speaker (mute) and the volume line.

Instrumentals show 乐曲 and "Instrumental" where the lyrics would be.

## How it behaves

- Nothing plays and no song is downloaded until the visitor presses play (or a song, or a line).
- A song plays once, start to end. Then the next one plays. After the last comes the first.
  Repeat plays the same song again instead.
- Previous goes back to the start of the song once it is more than 3 seconds in. Before that it
  goes to the song before.
- While a song plays, the next one is downloaded, so it starts without a wait.
- The address names the open song: `/music#arena` opens on 降临. It updates as songs change, and
  changing the hash on an open page changes the song.
- Keys: Space plays and pauses, the left and right arrows move 5 seconds, M mutes. A focused
  button or slider keeps its own keys.
- A headset's or a lock screen's buttons work (the Media Session API), and show the song's name.
- After the visitor scrolls the lyrics, the page stops following the song for 5 seconds.
- If the backend is away the page says "No music right now. Try again in a bit." If one song
  fails to load, a line under its credits says so, and play tries again.

## Volume and mute

- The volume line is the same setting the flight remembers (`sect.music.volume` in localStorage),
  so a change on either page carries over.
- 100% here is the file's own level. The flight plays the same files at half of that, because
  there the music sits under a scene.
- The speaker mutes for this visit only. The flight's own mute (`sect.music.muted`) is not read
  here: pressing play on a music player means the visitor wants to hear it.
- iPhones do not let a page set the volume. There the volume line is left out and the speaker
  still mutes.

## How it plays

The code is in `client/src/app/music/`:

| File | What it does |
|---|---|
| `page.tsx` | The route: title, description, the two style sheets. |
| `music-player.tsx` | The page: loads the song list and lyrics, draws everything, handles keys. |
| `song-player.ts` | The audio: one `<audio>` element, downloads, play, pause, seek, next. |
| `music.css` | The page's layout. The colours, plates and lyric rows come from `sect/sect.css`. |
| `../../lib/sect/player.ts` | The small rules: song order, next and previous, time formatting, keys. |

The flight's engine (`sect/experience/music-engine.ts`) is not used here. It decodes whole tracks
into memory, about 55 MB each, so it can loop and crossfade them. A player needs pause and seek
and should keep playing in a hidden tab. An `<audio>` element does all of that with the 5 MB file.

The backend only serves a song to a request that carries a short-lived capability in a header
([`backend-soundtrack-delivery.md`](backend-soundtrack-delivery.md)). An `<audio>` element cannot
send headers. So the page downloads the whole song with `fetch`, then hands it to the element as
an object URL. It keeps at most three songs this way and frees the rest.

Phones only let a page start sound inside a tap, and the song arrives seconds after the tap. So
the tap first plays a tenth of a second of silence on the same element. After that the element is
allowed to start the song by itself.

Lyric timing uses the same files and the same functions as the drawer (`lib/sect/lyrics.ts`). The
clock is the element's `currentTime`, read every animation frame while the song plays.

## Layout

- **Phones and small windows:** one column that scrolls as a page. The card, with the songs as a
  strip that scrolls sideways, then the lyrics. The bar stays at the bottom of the screen.
- **60rem by 36rem and up:** the page is exactly the window. The card is on the left with the
  songs as a column. The lyrics scroll beside it. The bar runs across the bottom.

Behind everything is the flight's poster still of the Mountain Gate, far under ink.

## Accessibility

- The controls are native buttons and range inputs with names ("Play", "Next", "Repeat this
  song", "Position in the song", "Volume").
- The open song is marked with `aria-current` in the list. The line being sung is marked the same
  way and read out through a hidden polite live region.
- The lyric lines are left out of the Tab order. Some songs have sixty lines and the controls come
  after them. The keyboard moves through a song with the arrow keys and the seek line.
- Reduced motion turns off the smooth scrolling and the transitions. Forced colours drop the
  backdrop and the fades.

## Testing it

Set the volume to zero before pressing play, so nobody at the PC hears it:
`localStorage["sect.music.volume"] = "0"`, then reload. The song still plays, so the lyric fill can
be checked in silence. Do not press the speaker button or M while testing: at zero they bring the
sound back at half.

Checked on 2026-11-13 at 320×568, 375×812, 812×375, 1024×768 and 1440×900 against the real
`server/music.py` routes served from local prepared files. Not checked: a real iPhone, and the
"No music right now" screen in a browser.
