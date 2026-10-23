"use client";

/**
 * The music's sound toggle: one icon button, no text (its name is for screen readers). A speaker
 * with waves while the music plays, a crossed-out speaker while it is silent (muted, or before the
 * visitor's first click: browsers let sound start only after one).
 *
 * Phones: under the voice orb in the top-right corner (the area panel spans the bottom). Desktops:
 * under the Map button, above the section rail; on short wide screens (a phone on its side, a
 * small laptop window) beside it instead (see BESIDE_PLACES). It sits under the map and the
 * readers, like the other controls. While the loading screen is up, that screen's own "Turn on
 * sound" (SoundPrompt, below, in its column under the graphics picker) stands in for it; the toggle
 * floats over the screen only where that column runs past the bottom edge and hides the prompt (a
 * phone on its side, a short window).
 *
 * `extra` (the graphics button) shares its place once the loading screen is gone: under the toggle,
 * or left of it in the top row beside the Map button. It shows without Web Audio too.
 */
import { type ReactNode, useEffect, useLayoutEffect, useState, useSyncExternalStore } from "react";
import type { MusicEngine, MusicUi } from "./music-engine";

const OFF: MusicUi = { available: false, on: false, muted: false };
const serverSnapshot = () => OFF;

/**
 * Wide but short screens: the place rail is centred on the right edge and reaches up under the Map
 * below about 580 px, and the voice panel's top corner below about 740 px. There the toggle sits in
 * the top row, left of the Map button (measured, so its label can change).
 */
const BESIDE_PLACES = "(min-width: 768px) and (max-height: 740px)";
const GAP_PX = 8;

/**
 * The loading screen's sound prompt is in full view (its kept place, loading-screen.tsx). True until
 * measured, so a tall screen never flashes the toggle.
 */
function usePromptInView(loading: boolean): boolean {
  const [inView, setInView] = useState(true);
  useEffect(() => {
    if (!loading) return;
    let obs: IntersectionObserver | null = null;
    let tries = 0;
    let timer = 0;
    const attach = () => {
      const place = document.querySelector("[data-sect-sound-place]");
      if (!place) {
        if (++tries < 40) timer = window.setTimeout(attach, 250);
        return;
      }
      obs = new IntersectionObserver(([e]) => setInView(e.intersectionRatio > 0.99), { threshold: [0, 0.99, 1] });
      obs.observe(place);
    };
    attach();
    return () => {
      window.clearTimeout(timer);
      obs?.disconnect();
    };
  }, [loading]);
  return inView;
}

function useBesidePlaces(): { right: number; top: number } | null {
  const [pos, setPos] = useState<{ right: number; top: number } | null>(null);
  useEffect(() => {
    const mq = window.matchMedia(BESIDE_PLACES);
    const measure = () => {
      const b = mq.matches ? document.querySelector("[data-sect-places]")?.getBoundingClientRect() : undefined;
      const next = b && b.width > 0 ? { right: Math.round(window.innerWidth - b.left + GAP_PX), top: Math.round(b.top) } : null;
      setPos((cur) => (cur?.right === next?.right && cur?.top === next?.top ? cur : next));
    };
    measure();
    window.addEventListener("resize", measure);
    // Places appears after the loading screen, and its width settles once the font has loaded.
    const id = window.setInterval(measure, 1000);
    return () => {
      window.removeEventListener("resize", measure);
      window.clearInterval(id);
    };
  }, []);
  return pos;
}

export function SoundToggle({ engine, loading, extra }: { engine: MusicEngine; loading: boolean; extra?: ReactNode }) {
  const ui = useSyncExternalStore(engine.subscribe, engine.snapshot, serverSnapshot);
  const beside = useBesidePlaces();
  const promptInView = usePromptInView(loading);
  // The loading screen has its own graphics picker, and its sound prompt when that is in view.
  const more = loading ? null : (extra ?? null);
  if ((loading && promptInView) || (!ui.available && !more)) return null;
  const inRow = beside !== null && !loading;
  return (
    <div
      className={`pointer-events-none fixed right-[0.625rem] top-[7.25rem] flex gap-2 md:right-6 md:top-[4.25rem] ${inRow ? "flex-row-reverse items-start" : "flex-col items-end"} ${loading ? "z-[51]" : "z-[25]"}`}
      style={inRow ? { right: beside.right, top: beside.top } : undefined}
    >
      {ui.available && (
        <button
          type="button"
          data-sect-sound
          onClick={() => engine.toggle()}
          aria-label={ui.on ? "Sound off" : "Sound on"}
          className="sect-panel sect-plate sect-ctl pointer-events-auto relative grid h-11 w-11 place-items-center rounded-[3px] text-[var(--sect-paper-soft)] transition-colors hover:text-[var(--sect-gold)] md:h-10 md:w-10"
        >
          <SpeakerIcon on={ui.on} />
        </button>
      )}
      {more}
    </div>
  );
}

/**
 * The loading screen's invitation (loading-screen.tsx keeps its place): a round gold seal with the
 * speaker, "Turn on sound" and "for the best experience" beside it, all one button. Its press is the
 * gesture browsers need before any sound, so the loading music can start at once; the choice is
 * remembered like the toggle's. Once on it says so, and a second press mutes. Nothing without Web
 * Audio or a track list (the place stays empty).
 */
export function SoundPrompt({ engine }: { engine: MusicEngine }) {
  const ui = useSyncExternalStore(engine.subscribe, engine.snapshot, serverSnapshot);
  // Gone with the loading screen while it had the keyboard's focus: the corner toggle (the same
  // switch) takes it, not <body>. A layout effect's cleanup runs while the button is still on the page.
  // Keyboard focus only: after a click, Space must stay with the flight, not mute the music.
  useLayoutEffect(
    () => () => {
      if (!document.activeElement?.closest(".sect-soundcall")?.matches(":focus-visible")) return;
      window.setTimeout(() => {
        const a = document.activeElement;
        // Not while a screen still covers the toggle (the error screen), nor when something took the focus.
        if ((a && a !== document.body) || document.querySelector(".sect-veil")) return;
        document.querySelector<HTMLElement>("button[data-sect-sound]")?.focus({ preventScroll: true });
      }, 0);
    },
    [],
  );
  return ui.available ? <SoundCall on={ui.on} onToggle={() => engine.toggle()} /> : null;
}

/**
 * SoundPrompt's button. Named in full for screen readers ("Turn on sound, for the best experience").
 * Its width holds when the words change (min-w: the longer wording's, in rem so it grows with the
 * text), so the centred button does not shift and the seal stays under the finger for a second tap.
 */
export function SoundCall({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  const [line, note] = on ? ["Sound on", "Tap again to mute"] : ["Turn on sound", "For the best experience"];
  return (
    <button
      type="button"
      data-sect-sound
      data-on={on || undefined}
      onClick={onToggle}
      aria-label={`${line}, ${note.toLowerCase()}`}
      className="sect-soundcall sect-fade-in group inline-flex min-h-11 min-w-[15rem] items-center gap-3 rounded-[2px] py-1 pl-1 pr-3 text-left"
    >
      <span aria-hidden className="sect-soundcall-seal">
        <SpeakerIcon on={on} />
      </span>
      <span className="flex flex-col leading-tight">
        <span className="text-[0.9375rem] text-[var(--sect-paper)] transition-colors group-hover:text-[var(--sect-gold)]">{line}</span>
        <span className="mt-1 text-[0.625rem] uppercase tracking-[0.24em] text-[var(--sect-gold)]">{note}</span>
      </span>
    </button>
  );
}

function SpeakerIcon({ on }: { on: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden className={on ? "text-[var(--sect-gold)]" : undefined}>
      <path d="M2.5 6.75h2.9L9 3.6v10.8l-3.6-3.15H2.5z" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
      {on ? (
        <path d="M11.6 6.4a3.6 3.6 0 0 1 0 5.2M13.6 4.4a6.4 6.4 0 0 1 0 9.2" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      ) : (
        <path d="M11.8 7l4 4M15.8 7l-4 4" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      )}
    </svg>
  );
}
