"use client";

/**
 * /music: the site's soundtrack as a player of its own (docs/music/music-page.md). No 3D: the song
 * list, the song that plays with its credits and the owner's note, its whole lyrics with the line
 * being sung marked, and a bar of controls (previous, play and pause, next, a seek line, repeat,
 * mute and volume).
 *
 * The songs, their lyrics and the short-lived capabilities come from the same backend as the
 * flight's music (lib/sect/music-api.ts). The audio is ./song-player.ts; the choices are
 * lib/sect/player.ts. The page wears the sect's dress (sect.css) with its own layout (./music.css).
 *
 * Nothing plays, and no song is downloaded, until the visitor presses play. The volume is the one
 * the flight remembers ("sect.music.volume"); the flight's mute is its own and is not read here.
 */
import Link from "next/link";
import {
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  memo,
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { parseMusicManifest, type MusicKey, type MusicManifest, type MusicTrack } from "@/lib/sect/music";
import { fetchMusicBytes, fetchMusicManifest, fetchTrackLyrics, resolveMusicApiBase } from "@/lib/sect/music-api";
import { lyricLineAt, lyricUnitProgress, lyricWordAt, type SongLyrics } from "@/lib/sect/lyrics";
import { SEEK_STEP_SECONDS, clock, clockWords, playerCommand, silentClip, songFromHash, songList } from "@/lib/sect/player";
import { hasHan, songCredits, songNote, songTitleEn } from "@/lib/sect/song-notes";
import { VOLUME_STEP, readVolume, volumeFromPercent, volumePercent, volumeText, writeVolume } from "@/lib/sect/volume";
import { SongHead } from "../sect/experience/karaoke-lyrics";
import { BrushName, InkRing, SectLogo } from "../sect/ornaments";
import { PLAYER_OFF, SongPlayer, type PlayerUi } from "./song-player";

/** After the visitor scrolls the lyrics, the page leaves them where they are this long. */
const SCROLL_HOLD_MS = 5000;
/** How far from the line being sung a row's ink fades to its faintest (sect.css --d). */
const FADE_ROWS = 4;

type Status = "loading" | "ready" | "none";

/** A song's lyrics as the page has them: still coming, here, or not to be had. */
interface LyricState {
  song: MusicKey;
  state: "loading" | "ready" | "failed";
  lyrics: SongLyrics | null;
}

function localStore(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

const noStore = () => () => {};
const offSnapshot = () => PLAYER_OFF;

/** `fontClass`: the brush font's variable (sect/brush-font.ts), which the page sets on the root. */
export function MusicPlayer({ fontClass = "" }: { fontClass?: string }) {
  const [player, setPlayer] = useState<SongPlayer | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [manifest, setManifest] = useState<MusicManifest | null>(null);
  const [apiBase, setApiBase] = useState<string | null>(null);
  const [lyrics, setLyrics] = useState<LyricState | null>(null);
  const lyricCache = useRef(new Map<MusicKey, SongLyrics>());
  const ui = useSyncExternalStore(player?.subscribe ?? noStore, player?.snapshot ?? offSnapshot, offSnapshot);
  const song = ui.song;
  const track = song && manifest ? (manifest.tracks[song] ?? null) : null;

  // The player and the song list. No list (the backend is away): the page says so.
  useEffect(() => {
    const store = localStore();
    const base = resolveMusicApiBase();
    const audio = new Audio();
    audio.preload = "auto";
    const p = new SongPlayer(
      {
        audio,
        fetchBytes: async (key, signal) => fetchMusicBytes(await base, key, signal),
        createUrl: (bytes) => URL.createObjectURL(new Blob([bytes], { type: "audio/mpeg" })),
        revokeUrl: (url) => URL.revokeObjectURL(url),
        silence: silentClip(),
        saveVolume: (v) => writeVolume(store, v),
      },
      { volume: readVolume(store) },
    );
    setPlayer(p);
    const ac = new AbortController();
    base
      .then((b) => {
        if (!ac.signal.aborted) setApiBase(b);
        return fetchMusicManifest(b, ac.signal);
      })
      .then((raw) => {
        if (ac.signal.aborted) return;
        const m = parseMusicManifest(raw);
        const list = songList(m);
        if (!m || list.length === 0) {
          setStatus("none");
          return;
        }
        setManifest(m);
        p.setSongs(list, (key) => m.tracks[key]?.duration ?? 0, songFromHash(window.location.hash, list));
        setStatus("ready");
      })
      .catch(() => {
        if (!ac.signal.aborted) setStatus("none");
      });
    return () => {
      ac.abort();
      p.dispose();
      setPlayer((cur) => (cur === p ? null : cur));
    };
  }, []);

  // The song's lyrics: asked for when it is chosen, so they can be read without playing it.
  useEffect(() => {
    if (!apiBase || !song || !track) return;
    if (!track.hasLyrics) {
      setLyrics(null);
      return;
    }
    const kept = lyricCache.current.get(song);
    if (kept) {
      setLyrics({ song, state: "ready", lyrics: kept });
      return;
    }
    setLyrics({ song, state: "loading", lyrics: null });
    const ac = new AbortController();
    fetchTrackLyrics(apiBase, song, ac.signal)
      .catch(() => null)
      .then((found) => {
        if (ac.signal.aborted) return;
        if (found) lyricCache.current.set(song, found);
        setLyrics({ song, state: found ? "ready" : "failed", lyrics: found });
      });
    return () => ac.abort();
  }, [apiBase, song, track]);

  // The address names the song (/music#arena), once the visitor has chosen one or came with one.
  const opened = useRef<MusicKey | null>(null);
  useEffect(() => {
    if (!song) return;
    if (opened.current === null) {
      opened.current = song;
      if (!window.location.hash) return;
    }
    if (window.location.hash !== `#${song}`) window.history.replaceState(null, "", `#${song}`);
  }, [song]);
  // And a hash typed or followed while the page is open chooses its song.
  useEffect(() => {
    if (!player || !manifest) return;
    const on = () => {
      const key = songFromHash(window.location.hash, songList(manifest));
      if (key) player.select(key);
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, [player, manifest]);

  // The page's keys (lib/sect/player.ts): Space, the left and right arrows, M.
  useEffect(() => {
    if (!player) return;
    const on = (e: KeyboardEvent) => {
      const el = e.target instanceof Element ? e.target : null;
      const field = !!el?.closest("input, select, textarea, [contenteditable]");
      const pressable = !!el?.closest("button, a[href], summary");
      const command = playerCommand(e, field || (pressable && (e.key === " " || e.key === "Spacebar")));
      if (!command) return;
      e.preventDefault();
      if (command === "toggle") player.toggle();
      else if (command === "mute") player.toggleMute();
      else player.seek(player.position() + (command === "forward" ? SEEK_STEP_SECONDS : -SEEK_STEP_SECONDS));
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [player]);

  // A headset's or a lock screen's buttons, and what they show.
  useEffect(() => {
    if (!player || !("mediaSession" in navigator)) return;
    const session = navigator.mediaSession;
    const set = (action: MediaSessionAction, handler: MediaSessionActionHandler | null) => {
      try {
        session.setActionHandler(action, handler);
      } catch {
        // An action this browser does not know.
      }
    };
    set("play", () => player.play());
    set("pause", () => player.pause());
    set("previoustrack", () => player.previous());
    set("nexttrack", () => player.next());
    set("seekto", (d) => {
      if (typeof d.seekTime === "number") player.seek(d.seekTime);
    });
    return () => {
      for (const action of ["play", "pause", "previoustrack", "nexttrack", "seekto"] as const) set(action, null);
    };
  }, [player]);
  useEffect(() => {
    if (!song || !track || !("mediaSession" in navigator) || typeof MediaMetadata === "undefined") return;
    const en = songTitleEn(song);
    const credits = songCredits(track);
    navigator.mediaSession.metadata = new MediaMetadata({
      title: en && hasHan(track.title) ? `${track.title} · ${en}` : track.title,
      artist: credits.artist ?? "",
      album: credits.show,
    });
  }, [song, track]);
  useEffect(() => {
    if ("mediaSession" in navigator) navigator.mediaSession.playbackState = ui.playing ? "playing" : "paused";
  }, [ui.playing]);

  const choose = useCallback((key: MusicKey) => player?.select(key, true), [player]);
  const songLyrics = lyrics && lyrics.song === song ? lyrics : null;

  return (
    <div className={`sect-root sect-lyrics music ${fontClass}`} data-brush="">
      <div aria-hidden className="music-backdrop" />
      <header className="music-top">
        <Link href="/" prefetch={false} className="music-home sect-panel sect-plate sect-ctl">
          <SectLogo className="music-home-logo" />
          <span className="music-home-name">Bill Zhang</span>
          <span aria-hidden className="sect-brushrule-v music-home-rule" />
          <span className="music-home-back">Back to the sect</span>
        </Link>
        <h1 className="music-name">
          <BrushName text="乐曲" hidden />
          <span className="music-name-en">Music</span>
        </h1>
      </header>

      {status !== "ready" || !player || !manifest || !song || !track ? (
        <main className="music-main music-main-empty">
          <p className="sect-lyrics-state music-state" role="status">
            {status === "none" ? (
              "No music right now. Try again in a bit."
            ) : (
              <>
                <InkRing className="sect-lyrics-ring" />
                Loading
              </>
            )}
          </p>
        </main>
      ) : (
        <>
          <main className="music-main">
            <aside className="music-card sect-panel sect-panel-lg">
              <div className="music-now">
                <SongHead track={track} note={songNote(song)} titleEn={songTitleEn(song)} playing={ui.playing} />
                {ui.failed ? (
                  <p className="music-alert" role="alert">
                    This song didn’t load. Press play to try again.
                  </p>
                ) : null}
              </div>
              <SongList manifest={manifest} current={song} onChoose={choose} />
            </aside>
            <LyricSheet key={song} player={player} track={track} lyrics={songLyrics} />
          </main>
          <Transport player={player} ui={ui} />
        </>
      )}
    </div>
  );
}

/**
 * The songs, in the flight's order. A column in the card on wide screens; a strip that scrolls
 * sideways on phones. The song that is open is marked (aria-current) and kept in view.
 */
export const SongList = memo(function SongList({
  manifest,
  current,
  onChoose,
}: {
  manifest: MusicManifest;
  current: MusicKey | null;
  onChoose: (key: MusicKey) => void;
}) {
  const box = useRef<HTMLOListElement>(null);
  const list = songList(manifest);

  // The open song's row comes into view by scrolling the list alone, never the page.
  useEffect(() => {
    const el = box.current;
    const row = el?.querySelector<HTMLElement>("[aria-current]");
    if (!el || !row) return;
    const a = el.getBoundingClientRect();
    const b = row.getBoundingClientRect();
    el.scrollTo({
      left: el.scrollLeft + (b.left - a.left) - (a.width - b.width) / 2,
      top: el.scrollTop + (b.top - a.top) - (a.height - b.height) / 2,
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
  }, [current]);

  return (
    <nav className="music-songs" aria-label="Songs">
      <h2 className="music-songs-title">Songs</h2>
      <ol ref={box} className="music-songs-list">
        {list.map((key) => {
          const t = manifest.tracks[key];
          if (!t) return null;
          const zh = hasHan(t.title);
          const en = zh ? songTitleEn(key) : null;
          return (
            <li key={key}>
              <button
                type="button"
                className="music-song"
                aria-current={key === current ? "true" : undefined}
                onClick={() => onChoose(key)}
              >
                <span aria-hidden className="music-song-mark" />
                <span className="music-song-name">
                  {zh ? <BrushName text={t.title} /> : <span className="music-song-latin">{t.title}</span>}
                  {en ? (
                    <span className="music-song-en" lang="en">
                      {en}
                    </span>
                  ) : null}
                </span>
                <span className="music-song-time">{clock(t.duration)}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
});

/**
 * The whole song. A click or a tap on a line plays from it. The lines are left out of the Tab order
 * (some songs have sixty, and the controls come after them); the keyboard moves through a song with
 * the arrow keys and the seek line instead.
 *
 * The line being sung is marked as in the flight's drawer (sect.css .sect-lyrics-row): gold ink runs
 * through its words as they are sung, and the other lines fade with their distance from it. It
 * follows the song toward the middle of the view, and stops following for a few seconds after the
 * visitor scrolls.
 *
 * It reads the player's clock in an animation frame while the song plays and changes React state
 * only when the line changes; the words' ink is written straight to their spans.
 */
function LyricSheet({ player, track, lyrics }: { player: SongPlayer; track: MusicTrack; lyrics: LyricState | null }) {
  const lines = lyrics?.lyrics?.lines ?? null;
  const [active, setActive] = useState<number | null>(null);
  const activeRef = useRef<number | null>(null);
  activeRef.current = active;
  const rows = useRef<(HTMLLIElement | null)[]>([]);
  const words = useRef<(HTMLSpanElement | null)[]>([]);
  const inked = useRef<{ line: number; word: number } | null>(null);
  const scrolledAt = useRef(-Infinity);

  useEffect(() => {
    if (!lines) return;
    let frame = 0;
    const paint = () => {
      frame = 0;
      const time = player.position();
      const match = lyricLineAt(lines, time);
      const current = activeRef.current;
      // While it plays, every frame. Paused, once more after a new line is drawn, to ink its words.
      let again = player.snapshot().playing;
      if (!match) {
        if (current !== null) setActive(null);
      } else if (current !== match.index) {
        setActive(match.index);
        inked.current = null;
        again = true;
      } else {
        // The words already sung are full of gold ink (--p 1), the one being sung fills from its
        // left as its time passes, the rest wait in paper white.
        const units = match.line.words;
        const nodes = words.current;
        const at = lyricWordAt(units, time);
        const last = inked.current;
        if (!last || last.line !== match.index || last.word !== at) {
          for (let i = 0; i < nodes.length; i++) nodes[i]?.style.setProperty("--p", i < at ? "1" : "0");
          inked.current = { line: match.index, word: at };
        }
        if (units[at]) nodes[at]?.style.setProperty("--p", lyricUnitProgress(units[at], time).toFixed(3));
      }
      if (again) frame = requestAnimationFrame(paint);
    };
    const kick = () => {
      if (!frame) frame = requestAnimationFrame(paint);
    };
    const offTime = player.subscribeTime(kick);
    const offUi = player.subscribe(kick);
    kick();
    return () => {
      offTime();
      offUi();
      cancelAnimationFrame(frame);
    };
  }, [player, lines]);

  // The visitor's own scrolling: the page stops following for a while.
  useEffect(() => {
    const on = () => {
      scrolledAt.current = performance.now();
    };
    const key = (e: KeyboardEvent) => {
      if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End"].includes(e.key)) on();
    };
    window.addEventListener("wheel", on, { passive: true });
    window.addEventListener("touchmove", on, { passive: true });
    window.addEventListener("keydown", key);
    return () => {
      window.removeEventListener("wheel", on);
      window.removeEventListener("touchmove", on);
      window.removeEventListener("keydown", key);
    };
  }, []);

  useEffect(() => {
    if (active === null || performance.now() - scrolledAt.current < SCROLL_HOLD_MS) return;
    rows.current[active]?.scrollIntoView({
      block: "center",
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
  }, [active]);

  const jump = (start: number) => {
    // A drag that selected some of the words is not a press.
    if (window.getSelection()?.toString()) return;
    scrolledAt.current = -Infinity;
    player.seek(start);
    player.play();
  };

  if (!track.hasLyrics) {
    return (
      <section className="music-sheet music-sheet-quiet" aria-label="Lyrics">
        <p className="music-quiet">
          <BrushName text="乐曲" hidden className="music-quiet-zh" />
          <span aria-hidden className="sect-brushstroke" />
          <span>Instrumental</span>
        </p>
      </section>
    );
  }
  if (!lines) {
    return (
      <section className="music-sheet music-sheet-quiet" aria-label="Lyrics">
        <p className="sect-lyrics-state music-state" role="status">
          {lyrics?.state === "failed" ? (
            "The lyrics didn’t load."
          ) : (
            <>
              <InkRing className="sect-lyrics-ring" />
              Loading
            </>
          )}
        </p>
      </section>
    );
  }

  const activeLine = active !== null ? lines[active] : null;
  return (
    <section className="music-sheet" aria-label="Lyrics">
      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {activeLine ? `${activeLine.text}. ${activeLine.en && activeLine.en !== activeLine.text ? activeLine.en : ""}` : ""}
      </p>
      <ol className="sect-lyrics-list" data-singing={active !== null ? "" : undefined}>
        {lines.map((line, index) => {
          const isActive = active === index;
          const translation = line.en && line.en !== line.text ? line.en : null;
          return (
            <li
              className="sect-lyrics-row"
              data-active={isActive ? "" : undefined}
              aria-current={isActive ? "true" : undefined}
              key={index}
              style={active !== null ? ({ "--d": Math.min(FADE_ROWS, Math.abs(index - active)) } as CSSProperties) : undefined}
              ref={(node) => {
                rows.current[index] = node;
              }}
            >
              <button type="button" tabIndex={-1} className="music-line" onClick={() => jump(line.start)}>
                <span className="sect-lyrics-line" lang={hasHan(line.text) ? "zh" : undefined}>
                  {isActive && line.words.length > 0
                    ? line.words.map((word, w) => (
                        <span
                          className="sect-lyrics-word"
                          key={w}
                          ref={(node) => {
                            words.current[w] = node;
                            if (w === 0) words.current.length = line.words.length;
                          }}
                        >
                          {word.w}
                        </span>
                      ))
                    : line.text}
                </span>
                {translation ? <span className="sect-lyrics-en">{translation}</span> : null}
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/**
 * The bar of controls, on a plate at the foot of the page: previous, play or pause, next; the seek
 * line with the time on either side; repeat; the speaker and the volume line. Native buttons and
 * range inputs, so the keyboard, touch and screen readers work as they do anywhere.
 */
export function Transport({ player, ui }: { player: SongPlayer; ui: PlayerUi }) {
  const quiet = ui.muted || ui.volume === 0;
  const pct = volumePercent(ui.volume);
  return (
    <footer className="music-bar sect-panel sect-plate" role="group" aria-label="Player">
      <div className="music-bar-main">
        <button type="button" className="music-btn" aria-label="Previous" onClick={() => player.previous()}>
          <SkipIcon back />
        </button>
        <button
          type="button"
          className="music-btn music-play"
          aria-label={ui.playing ? "Pause" : "Play"}
          data-loading={ui.loading ? "" : undefined}
          onClick={() => player.toggle()}
        >
          {ui.loading ? <InkRing className="music-play-ring" /> : <PlayIcon playing={ui.playing} />}
        </button>
        <button type="button" className="music-btn" aria-label="Next" onClick={() => player.next()}>
          <SkipIcon />
        </button>
      </div>
      <SeekLine player={player} duration={ui.duration} />
      <div className="music-bar-side">
        <button
          type="button"
          className="music-btn music-repeat"
          aria-label="Repeat this song"
          aria-pressed={ui.repeat}
          onClick={() => player.toggleRepeat()}
        >
          <RepeatIcon />
        </button>
        <button type="button" className="music-btn" aria-label={quiet ? "Sound on" : "Mute"} onClick={() => player.toggleMute()}>
          <SpeakerIcon on={!quiet} />
        </button>
        {ui.volumeSettable ? (
          <input
            type="range"
            className="music-range music-volume"
            min={0}
            max={100}
            step={VOLUME_STEP}
            value={ui.muted ? 0 : pct}
            aria-label="Volume"
            aria-valuetext={ui.muted ? "Muted" : volumeText(ui.volume)}
            onChange={(e) => player.setVolume(volumeFromPercent(e.currentTarget.value))}
            style={{ "--v": `${ui.muted ? 0 : pct}%` } as CSSProperties}
          />
        ) : null}
      </div>
    </footer>
  );
}

/**
 * Where the song is, and a way to move through it: the time so far, a range input, the song's
 * length. It keeps its own clock (a few updates a second), so the rest of the page does not redraw
 * as the song plays. Its arrow keys move five seconds, as the page's do.
 */
function SeekLine({ player, duration }: { player: SongPlayer; duration: number }) {
  const [time, setTime] = useState(0);
  useEffect(() => {
    const read = () => setTime(player.position());
    read();
    const offTime = player.subscribeTime(read);
    const offUi = player.subscribe(read);
    return () => {
      offTime();
      offUi();
    };
  }, [player]);
  const length = duration > 0 ? duration : 0;
  const at = Math.min(time, length);
  const onKeyDown = (e: ReactKeyboardEvent<HTMLInputElement>) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    player.seek(player.position() + (e.key === "ArrowRight" ? SEEK_STEP_SECONDS : -SEEK_STEP_SECONDS));
  };
  return (
    <div className="music-seek">
      <span className="music-clock" aria-hidden>
        {clock(at)}
      </span>
      <input
        type="range"
        className="music-range"
        min={0}
        max={Math.max(1, Math.round(length))}
        step={1}
        value={Math.round(at)}
        disabled={length === 0}
        aria-label="Position in the song"
        aria-valuetext={`${clockWords(at)} of ${clockWords(length)}`}
        onChange={(e) => player.seek(Number(e.currentTarget.value))}
        onKeyDown={onKeyDown}
        style={{ "--v": `${length > 0 ? (at / length) * 100 : 0}%` } as CSSProperties}
      />
      <span className="music-clock" aria-hidden>
        {clock(length)}
      </span>
    </div>
  );
}

function PlayIcon({ playing }: { playing: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden>
      {playing ? <path d="M5.5 3.5h3v13h-3zM11.5 3.5h3v13h-3z" fill="currentColor" /> : <path d="M6 3.2l10.5 6.8L6 16.8z" fill="currentColor" />}
    </svg>
  );
}

function SkipIcon({ back = false }: { back?: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden style={back ? { transform: "scaleX(-1)" } : undefined}>
      <path d="M3 3.5l8.5 5.5L3 14.5z" fill="currentColor" />
      <path d="M13.75 3.5v11" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function RepeatIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden>
      <path
        d="M4 8V7a2.5 2.5 0 0 1 2.5-2.5h7M11.5 2.5l2 2-2 2M14 10v1a2.5 2.5 0 0 1-2.5 2.5h-7M6.5 15.5l-2-2 2-2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M9 7.4v3.4M8.2 8.1L9 7.4" fill="none" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** The flight's speaker (sect/experience/sound-toggle.tsx): waves while it sounds, a cross when it does not. */
function SpeakerIcon({ on }: { on: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden>
      <path d="M2.5 6.75h2.9L9 3.6v10.8l-3.6-3.15H2.5z" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
      {on ? (
        <path d="M11.6 6.4a3.6 3.6 0 0 1 0 5.2M13.6 4.4a6.4 6.4 0 0 1 0 9.2" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      ) : (
        <path d="M11.8 7l4 4M15.8 7l-4 4" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      )}
    </svg>
  );
}
