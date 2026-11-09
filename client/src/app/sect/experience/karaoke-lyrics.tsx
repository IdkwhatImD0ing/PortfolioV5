"use client";

import { useEffect, useRef, useState } from "react";
import type { MusicKey } from "@/lib/sect/music";
import { lyricLineAt, type LyricLine, type SongLyrics } from "@/lib/sect/lyrics";
import type { MusicEngine } from "./music-engine";

interface ActiveLine {
  track: MusicKey;
  index: number;
  line: LyricLine;
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
  const lineNodes = useRef<(HTMLDivElement | null)[]>([]);
  activeRef.current = active;
  const panelTrackRef = useRef<MusicKey | null>(null);
  panelTrackRef.current = panelTrack;
  const panelLyricsRef = useRef<SongLyrics | null>(null);
  panelLyricsRef.current = panelLyrics;

  useEffect(() => {
    let frame = 0;
    let alive = true;
    const controller = new AbortController();

    const getLyrics = (key: MusicKey): SongLyrics | null => {
      if (!engine.hasLyrics(key)) {
        cache.current.set(key, null);
        return null;
      }
      if (cache.current.has(key)) return cache.current.get(key) ?? null;
      if (!pending.current.has(key)) {
        const request = loadLyrics(key, controller.signal)
          .catch(() => null)
          .then((lyrics) => {
            pending.current.delete(key);
            cache.current.set(key, lyrics);
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

  if (!panelTrack) return null;
  const trackInfo = engine.trackInfo(panelTrack);
  if (!trackInfo) return null;
  const activeLine = active?.track === panelTrack ? active : null;
  const trackType =
    trackInfo.language === null
      ? "Instrumental"
      : trackInfo.language === "en"
        ? "English vocals"
        : "Chinese vocals";
  return (
    <div className="sect-lyrics" data-open={open ? "" : undefined}>
      <button
        type="button"
        className="sect-lyrics__toggle sect-ctl"
        aria-controls="sect-lyrics-panel"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span lang="zh">乐曲</span>
        <span>Music</span>
      </button>
      <aside
        id="sect-lyrics-panel"
        className="sect-lyrics__panel"
        aria-hidden={!open}
        inert={!open}
        aria-label="Current soundtrack details"
      >
        <header className="sect-lyrics__header">
          <span>Now playing · <span lang="zh">正在播放</span></span>
          <button type="button" className="sect-lyrics__close sect-ctl" onClick={() => setOpen(false)} aria-label="Close soundtrack details">
            ×
          </button>
        </header>
        <div className="sect-lyrics__body">
          <section className="sect-lyrics__about" aria-label="About this song">
            <p className="sect-lyrics__title">{trackInfo.title}</p>
            <dl className="sect-lyrics__meta">
              <div><dt>Artist</dt><dd>{trackInfo.artist}</dd></div>
              <div><dt>From</dt><dd>{trackInfo.show}</dd></div>
              <div><dt>Type</dt><dd>{trackType}</dd></div>
            </dl>
          </section>
          <p className="sr-only" aria-live="polite" aria-atomic="true">
            {activeLine ? `${activeLine.line.text}. ${activeLine.line.en || ""}` : ""}
          </p>
          {panelLyrics ? (
            <div className="sect-lyrics__list">
              {panelLyrics.lines.map((line, index) => {
                const isActive = activeLine?.index === index;
                return (
                  <div
                    className="sect-lyrics__row"
                    data-active={isActive ? "" : undefined}
                    aria-current={isActive ? "true" : undefined}
                    key={`${panelTrack}-${index}`}
                    ref={(node) => {
                      lineNodes.current[index] = node;
                    }}
                  >
                    {line.text !== line.en ? <p className="sect-lyrics__line" lang="zh">{line.text}</p> : null}
                    <p className="sect-lyrics__translation">{line.en || line.text}</p>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="sect-lyrics__gap">
              {trackInfo.hasLyrics ? "Loading lyrics…" : "Instrumental track · No lyrics"}
            </p>
          )}
        </div>
      </aside>
    </div>
  );
}
