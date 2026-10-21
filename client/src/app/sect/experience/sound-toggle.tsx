"use client";

/**
 * The music's sound toggle: one icon button, no text (its name is for screen readers). A speaker
 * with waves while the music plays, a crossed-out speaker while it is silent (muted, or before the
 * visitor's first click: browsers let sound start only after one).
 *
 * Phones: under the voice orb in the top-right corner (the area panel spans the bottom). Desktops:
 * under the Places button, above the section rail; on short wide screens (a phone on its side, a
 * small laptop window) beside Places instead (see BESIDE_PLACES). While the loading screen is up it
 * floats over it, so the visitor can turn the loading music on there; afterwards it sits under the
 * Places list and the readers, like the other controls.
 *
 * `extra` (the graphics button) shares its place once the loading screen is gone: under the toggle,
 * or left of it in the top row beside Places. It shows without Web Audio too.
 */
import { type ReactNode, useEffect, useState, useSyncExternalStore } from "react";
import type { MusicEngine, MusicUi } from "./music-engine";

const OFF: MusicUi = { available: false, on: false, muted: false };
const serverSnapshot = () => OFF;

/**
 * Wide but short screens: the place rail is centred on the right edge and reaches up under Places
 * below about 580 px, and the voice panel's top corner below about 740 px. There the toggle sits in
 * the top row, left of the Places button (measured, so its label can change).
 */
const BESIDE_PLACES = "(min-width: 768px) and (max-height: 740px)";
const GAP_PX = 8;

function useBesidePlaces(): { right: number; top: number } | null {
  const [pos, setPos] = useState<{ right: number; top: number } | null>(null);
  useEffect(() => {
    const mq = window.matchMedia(BESIDE_PLACES);
    const measure = () => {
      const b = mq.matches ? document.querySelector('[aria-controls="sect-places"]')?.getBoundingClientRect() : undefined;
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

export function SoundToggle({ engine, raised, extra }: { engine: MusicEngine; raised: boolean; extra?: ReactNode }) {
  const ui = useSyncExternalStore(engine.subscribe, engine.snapshot, serverSnapshot);
  const beside = useBesidePlaces();
  // The loading screen has its own graphics picker.
  const more = raised ? null : (extra ?? null);
  if (!ui.available && !more) return null;
  const inRow = beside !== null && !raised;
  return (
    <div
      className={`pointer-events-none fixed right-[0.625rem] top-[7.25rem] flex gap-2 md:right-6 md:top-[4.25rem] ${inRow ? "flex-row-reverse items-start" : "flex-col items-end"} ${raised ? "z-[51]" : "z-[25]"}`}
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
