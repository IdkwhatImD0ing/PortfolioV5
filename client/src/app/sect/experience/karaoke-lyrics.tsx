"use client";

/**
 * The soundtrack panel (docs/music/karaoke-lyrics.md): a title slip at the left edge, 乐曲 written
 * upright on it, opens a drawer dressed like the stops' panels (rice paper over ink, gold cloud
 * corners). It names the song that plays, carries the owner's note on it (lib/sect/song-notes.ts)
 * and, for a sung track, the whole song with the line being sung marked in ink and gold.
 *
 * The slip steps aside while the drawer is open (the drawer covers its place); the drawer's own close
 * button and Escape put it away. Opened from the keyboard, the focus goes to that close button, and
 * it comes back to the slip when the drawer closes the same way. Opened by a click or a tap, the
 * focus goes to the drawer itself (the slip that held it is hidden), so Escape still reaches it.
 * Its Escape is one Escape, one thing: it closes the drawer and the view stays turned (scene.tsx
 * keysTaken).
 */
import { type CSSProperties, type KeyboardEvent, type MouseEvent, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from "react";
import type { MusicKey, MusicTrack } from "@/lib/sect/music";
import { lyricLineAt, lyricUnitProgress, lyricWordAt, type LyricLine, type SongLyrics } from "@/lib/sect/lyrics";
import { hasHan, songCredits, songNote, songTitleEn, type SongNote } from "@/lib/sect/song-notes";
import { BrushName, InkRing, SealStamp, SealedName } from "../ornaments";
import type { MusicEngine } from "./music-engine";
import { SoundCall, serverSnapshot } from "./sound-toggle";

interface ActiveLine {
  track: MusicKey;
  index: number;
  line: LyricLine;
}

/** How far from the line being sung a row's ink fades to its faintest (sect.css --d). */
const FADE_ROWS = 4;

/** A click from Enter or Space: no pointer behind it (detail 0), as sound-toggle.tsx reads it. */
function fromKeys(e: MouseEvent): boolean {
  return e.detail === 0;
}

export function LyricsPanel({
  engine,
  loadLyrics,
  hidden,
}: {
  engine: MusicEngine;
  loadLyrics: (key: MusicKey, signal: AbortSignal) => Promise<SongLyrics | null>;
  hidden: boolean;
}) {
  const [active, setActive] = useState<ActiveLine | null>(null);
  const [panelTrack, setPanelTrack] = useState<MusicKey | null>(null);
  const [panelLyrics, setPanelLyrics] = useState<SongLyrics | null>(null);
  const [open, setOpen] = useState(false);
  const cache = useRef(new Map<MusicKey, SongLyrics | null>());
  const pending = useRef(new Map<MusicKey, Promise<SongLyrics | null>>());
  const activeRef = useRef<ActiveLine | null>(null);
  const lineNodes = useRef<(HTMLLIElement | null)[]>([]);
  activeRef.current = active;
  const panelTrackRef = useRef<MusicKey | null>(null);
  panelTrackRef.current = panelTrack;
  const panelLyricsRef = useRef<SongLyrics | null>(null);
  panelLyricsRef.current = panelLyrics;
  const slipRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);
  // Whether the visitor has the sound on: silent, the drawer names the soundtrack and offers the sound.
  const ui = useSyncExternalStore(engine.subscribe, engine.snapshot, serverSnapshot);
  const openRef = useRef(false);
  openRef.current = open;
  // The brush hand is asked for from the first opening on (sect.css [data-brush]): the font is
  // fetched only then, and a closing drawer keeps its hand while it fades.
  const [brush, setBrush] = useState(false);
  if (open && !brush) setBrush(true);
  /** The words of the line being sung, and the one the ink last reached (sect.css --p). */
  const wordNodes = useRef<(HTMLSpanElement | null)[]>([]);
  const inked = useRef<{ track: MusicKey; line: number; word: number } | null>(null);
  /** Where the focus goes once the drawer has opened or closed. */
  const focusNext = useRef<"close" | "drawer" | "slip" | null>(null);

  useEffect(() => {
    let frame = 0;
    let alive = true;
    const controller = new AbortController();
    const waiting = pending.current;

    const getLyrics = (key: MusicKey): SongLyrics | null => {
      if (!engine.hasLyrics(key)) {
        cache.current.set(key, null);
        return null;
      }
      if (cache.current.has(key)) return cache.current.get(key) ?? null;
      if (!pending.current.has(key)) {
        // A request this effect's cleanup cut short (the panel hid mid-fetch) is not an answer: it is
        // left out of the cache, so the next showing asks again. It also leaves a newer request's
        // place in `pending` alone.
        const signal = controller.signal;
        const request: Promise<SongLyrics | null> = loadLyrics(key, signal)
          .catch(() => null)
          .then((lyrics) => {
            if (pending.current.get(key) === request) pending.current.delete(key);
            if (lyrics || !signal.aborted) cache.current.set(key, lyrics);
            return lyrics;
          });
        pending.current.set(key, request);
      }
      return null;
    };

    const paint = () => {
      if (!alive) return;
      const playback = engine.playbackSnapshot();
      if (hidden || !playback.track) {
        if (panelTrackRef.current) setPanelTrack(null);
        if (panelLyricsRef.current) setPanelLyrics(null);
        if (activeRef.current) setActive(null);
      } else {
        if (panelTrackRef.current !== playback.track) {
          setPanelTrack(playback.track);
          setPanelLyrics(null);
          lineNodes.current = [];
        }
        const lyrics = engine.hasLyrics(playback.track) ? getLyrics(playback.track) : null;
        if (lyrics && panelLyricsRef.current !== lyrics) setPanelLyrics(lyrics);
        const match = playback.audible && lyrics ? lyricLineAt(lyrics.lines, playback.position) : null;
        const current = activeRef.current;
        if (!match) {
          if (current) setActive(null);
        } else {
          if (!current || current.track !== playback.track || current.index !== match.index) {
            setActive({ track: playback.track, index: match.index, line: match.line });
            inked.current = null;
          } else if (openRef.current) {
            // Word by word: the words already sung are full of gold ink (--p 1), the one being sung
            // fills from its left as its time passes, the rest wait in paper white. Written straight
            // to the spans, so a sung word costs no render.
            const words = match.line.words;
            const nodes = wordNodes.current;
            const at = lyricWordAt(words, playback.position);
            const last = inked.current;
            if (!last || last.track !== playback.track || last.line !== match.index || last.word !== at) {
              for (let i = 0; i < nodes.length; i++) nodes[i]?.style.setProperty("--p", i < at ? "1" : "0");
              inked.current = { track: playback.track, line: match.index, word: at };
            }
            if (words[at]) nodes[at]?.style.setProperty("--p", lyricUnitProgress(words[at], playback.position).toFixed(3));
          }
        }
      }
      frame = requestAnimationFrame(paint);
    };

    const unsubscribe = engine.subscribePlayback(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(paint);
    });
    frame = requestAnimationFrame(paint);
    return () => {
      alive = false;
      controller.abort();
      // Its requests are cut short: the next run asks afresh rather than wait on them.
      waiting.clear();
      unsubscribe();
      cancelAnimationFrame(frame);
    };
  }, [engine, hidden, loadLyrics]);

  useEffect(() => {
    if (!open || !active || active.track !== panelTrack) return;
    lineNodes.current[active.index]?.scrollIntoView({
      block: "center",
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
  }, [active, open, panelTrack]);

  // The focus follows the drawer once it is drawn (the slip shows again before it can take it).
  useLayoutEffect(() => {
    const next = focusNext.current;
    focusNext.current = null;
    if (next === "close" && open) closeRef.current?.focus({ preventScroll: true });
    else if (next === "drawer" && open) drawerRef.current?.focus({ preventScroll: true });
    else if (next === "slip" && !open) slipRef.current?.focus({ preventScroll: true });
  }, [open]);

  // The stops' panels on the left make room for the drawer on wide screens (sect.css).
  const shown = open && panelTrack !== null;
  useEffect(() => {
    if (!shown) return;
    document.body.dataset.sectLyrics = "";
    return () => {
      delete document.body.dataset.sectLyrics;
    };
  }, [shown]);

  if (!panelTrack) return null;
  const trackInfo = engine.trackInfo(panelTrack);
  if (!trackInfo) return null;
  const activeLine = active?.track === panelTrack ? active : null;
  const note = songNote(panelTrack);

  const close = (refocus: boolean) => {
    focusNext.current = refocus ? "slip" : null;
    setOpen(false);
  };
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key !== "Escape" || !open) return;
    e.preventDefault();
    close(true);
  };

  return (
    <div className="sect-lyrics" data-open={open ? "" : undefined} data-brush={brush ? "" : undefined}>
      <button
        ref={slipRef}
        type="button"
        className="sect-lyrics-slip sect-panel sect-plate sect-ctl"
        aria-controls="sect-lyrics-panel"
        aria-expanded={open}
        onClick={(e) => {
          focusNext.current = fromKeys(e) ? "close" : "drawer";
          setOpen(true);
        }}
      >
        <BrushName text="乐曲" vertical hidden />
        <span className="sect-lyrics-slip-label">Music</span>
      </button>
      <aside
        ref={drawerRef}
        id="sect-lyrics-panel"
        tabIndex={-1}
        className="sect-lyrics-drawer sect-panel sect-panel-lg"
        aria-hidden={!open}
        inert={!open}
        aria-label="Current soundtrack details"
        onKeyDown={onKeyDown}
      >
        <button
          ref={closeRef}
          type="button"
          onClick={(e) => close(fromKeys(e))}
          aria-label="Close soundtrack details"
          className="sect-lyrics-close grid h-11 w-11 shrink-0 place-items-center rounded-[3px] text-[var(--sect-paper-soft)] hover:text-[var(--sect-gold)] md:h-10 md:w-10"
        >
          <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden>
            <path d="M2 2l12 12M14 2L2 14" stroke="currentColor" strokeWidth="1.5" />
          </svg>
        </button>
        <div className="sect-lyrics-body">
          <SongHead track={trackInfo} note={note} titleEn={songTitleEn(panelTrack)} playing={ui.on} />
          {ui.available && !ui.on ? (
            // The button goes once the sound is on: the focus it held moves on first (from the
            // keyboard to the close button, else to the drawer), so it stays in the drawer.
            <div
              className="sect-lyrics-sound"
              onClick={(e) => (fromKeys(e) ? closeRef : drawerRef).current?.focus({ preventScroll: true })}
            >
              <SoundCall on={false} onToggle={() => engine.toggle()} />
            </div>
          ) : null}
          <p className="sr-only" aria-live="polite" aria-atomic="true">
            {activeLine ? `${activeLine.line.text}. ${activeLine.line.en || ""}` : ""}
          </p>
          {trackInfo.hasLyrics ? <span aria-hidden className="sect-brushrule sect-lyrics-rule" /> : null}
          {panelLyrics ? (
            <ol className="sect-lyrics-list" data-singing={activeLine ? "" : undefined}>
              {panelLyrics.lines.map((line, index) => {
                const isActive = activeLine?.index === index;
                const translation = line.en && line.en !== line.text ? line.en : null;
                return (
                  <li
                    className="sect-lyrics-row"
                    data-active={isActive ? "" : undefined}
                    aria-current={isActive ? "true" : undefined}
                    key={`${panelTrack}-${index}`}
                    style={activeLine ? ({ "--d": Math.min(FADE_ROWS, Math.abs(index - activeLine.index)) } as CSSProperties) : undefined}
                    ref={(node) => {
                      lineNodes.current[index] = node;
                    }}
                  >
                    <p className="sect-lyrics-line" lang={hasHan(line.text) ? "zh" : undefined}>
                      {isActive && line.words.length > 0
                        ? line.words.map((word, w) => (
                            <span
                              className="sect-lyrics-word"
                              key={w}
                              ref={(node) => {
                                wordNodes.current[w] = node;
                                if (w === 0) wordNodes.current.length = line.words.length;
                              }}
                            >
                              {word.w}
                            </span>
                          ))
                        : line.text}
                    </p>
                    {translation ? <p className="sect-lyrics-en">{translation}</p> : null}
                  </li>
                );
              })}
            </ol>
          ) : trackInfo.hasLyrics ? (
            <p className="sect-lyrics-state">
              <InkRing className="sect-lyrics-ring" />
              Loading
            </p>
          ) : null}
        </div>
      </aside>
    </div>
  );
}

/**
 * The drawer's head: an eyebrow, the song's title as the hero (a Chinese title in the brush hand with
 * its English after a short gold dash and the sect's seal closing the line, a Latin one in the
 * stops' serif), the gold brush stroke, the credits in
 * one or two quiet lines, then the owner's note on the song, set off by a brush rule like a colophon.
 */
export function SongHead({
  track,
  note,
  titleEn = null,
  playing = true,
}: {
  track: Pick<MusicTrack, "title" | "show" | "artist" | "language">;
  note: SongNote | null;
  /** A Chinese title's English, written after it; none for a title already in English. */
  titleEn?: string | null;
  /** The sound is on. Off (every visitor starts muted), the eyebrow does not claim a song is playing. */
  playing?: boolean;
}) {
  const credits = songCredits(track);
  const zhTitle = hasHan(track.title);
  return (
    <>
      <header className="sect-lyrics-head">
        <p className="sect-lyrics-eyebrow">{playing ? "Now playing" : "Soundtrack"}</p>
        <h2 className={`sect-lyrics-title${zhTitle ? " sect-lyrics-title-zh" : ""}`}>
          {!zhTitle ? (
            track.title
          ) : titleEn ? (
            // The Chinese name, its English, then the seal closing the line as on a signed scroll.
            <>
              <BrushName text={track.title} />
              <span className="sect-lyrics-title-en" lang="en">
                <span className="sect-lyrics-title-en-text">{titleEn}</span>
                <SealStamp />
              </span>
            </>
          ) : (
            <SealedName text={track.title} />
          )}
        </h2>
        <span aria-hidden className="sect-brushstroke sect-lyrics-stroke" />
        <dl className="sect-lyrics-credits">
          <div className="sect-lyrics-from">
            <dt className="sr-only">From</dt>
            <dd lang={hasHan(credits.show) ? "zh" : undefined}>{credits.show}</dd>
          </div>
          {credits.artist ? (
            <div className="sect-lyrics-by">
              <dt className="sr-only">Artist</dt>
              <dd>{credits.artist}</dd>
            </div>
          ) : null}
          <div className="sect-lyrics-by">
            <dt className="sr-only">Vocals</dt>
            <dd>{credits.sung}</dd>
          </div>
        </dl>
      </header>
      {note ? (
        <>
          <span aria-hidden className="sect-brushrule sect-lyrics-rule" />
          <SongNoteText key={note.en} note={note} />
        </>
      ) : null}
    </>
  );
}

/**
 * The owner's note, centred. A press swaps its English for its Chinese and back: the one showing
 * fades out, then the other fades in over the same place (both are laid in one cell, so the drawer
 * keeps its height). It starts in English for each song.
 */
export function SongNoteText({ note }: { note: SongNote }) {
  const [zh, setZh] = useState(false);
  return (
    <button
      type="button"
      className="sect-lyrics-note"
      data-lang={zh ? "zh" : "en"}
      title={zh ? "English" : "中文"}
      onClick={() => setZh((v) => !v)}
    >
      <span className="sect-lyrics-note-face" lang="en" aria-hidden={zh || undefined}>
        {note.en}
      </span>
      <span className="sect-lyrics-note-face" lang="zh" aria-hidden={!zh || undefined}>
        {note.zh}
      </span>
    </button>
  );
}
