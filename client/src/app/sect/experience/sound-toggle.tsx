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
 * While the music plays, its volume slider (VolumeSlider) comes out beside the toggle when it is
 * wanted: "Music" and the level written on a small plate with a gold line. Left of the toggle on
 * wider screens; on phones under it, standing upright, so it stays clear of the intro's title in the
 * middle. It shows for a few seconds when the music turns on, under the mouse, with the keyboard's
 * focus, and on a tap on the speaker (which then does not mute); it goes when the mouse leaves, on a
 * click or tap elsewhere, on Escape and after a few idle seconds (lib/sect/volume-reveal.ts has the
 * rules). It is the master the voice call's ducking takes a share of (lib/sect/volume.ts), and it is
 * remembered per visitor. Muted, it steps away and the toggle stands alone.
 *
 * `extra` (the graphics button) shares its place once the loading screen is gone: under the toggle,
 * or left of it in the top row beside the Map button. It shows without Web Audio too.
 */
import {
  type CSSProperties,
  type FocusEvent,
  type KeyboardEvent,
  type MouseEvent,
  type ReactNode,
  useEffect,
  useId,
  useLayoutEffect,
  useReducer,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { VOLUME_STEP, volumeFromPercent, volumePercent, volumeText } from "@/lib/sect/volume";
import { REVEAL_START, revealReducer, tapShows } from "@/lib/sect/volume-reveal";
import type { MusicEngine, MusicUi } from "./music-engine";

const OFF: MusicUi = { available: false, on: false, muted: false, volume: 1 };
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
      {ui.available && <SoundControls ui={ui} onToggle={() => engine.toggle()} onVolume={(v) => engine.setVolume(v)} />}
      {more}
    </div>
  );
}

/** The keyboard put the focus on `el` (:focus-visible), not a click or a tap. */
function keyboardFocus(el: EventTarget): boolean {
  try {
    return el instanceof Element && el.matches(":focus-visible");
  } catch {
    return false;
  }
}

/** `node` is `box` or inside it. */
function within(box: HTMLElement | null, node: EventTarget | null): boolean {
  return !!box && node instanceof Node && box.contains(node);
}

/**
 * The slider comes and goes (lib/sect/volume-reveal.ts): this runs its one timer and listens on the
 * page for what happens away from the controls. A press anywhere else closes it (in the capture
 * phase, so nothing that stops the press on its way keeps it open); a drag ends wherever the pointer
 * comes up.
 */
function useVolumeReveal(on: boolean) {
  const [reveal, dispatch] = useReducer(revealReducer, REVEAL_START);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    dispatch({ type: "music", on });
    // Muted while the slider had the focus: it has gone from the page, and the focus with it.
    if (!within(box.current, document.activeElement)) dispatch({ type: "blur" });
  }, [on]);
  useEffect(() => {
    if (reveal.closeIn === null) return;
    const timer = reveal.timer;
    const id = window.setTimeout(() => dispatch({ type: "timeout", timer }), reveal.closeIn);
    return () => window.clearTimeout(id);
  }, [reveal.closeIn, reveal.timer]);
  useEffect(() => {
    if (!reveal.open) return;
    const down = (e: PointerEvent) => {
      if (!within(box.current, e.target)) dispatch({ type: "outside" });
    };
    window.addEventListener("pointerdown", down, true);
    return () => window.removeEventListener("pointerdown", down, true);
  }, [reveal.open]);
  useEffect(() => {
    if (!reveal.drag) return;
    const up = () => dispatch({ type: "drag", down: false });
    window.addEventListener("pointerup", up, true);
    window.addEventListener("pointercancel", up, true);
    return () => {
      window.removeEventListener("pointerup", up, true);
      window.removeEventListener("pointercancel", up, true);
    };
  }, [reveal.drag]);
  return { reveal, dispatch, box };
}

/**
 * The toggle, and the volume slider beside it while the music plays (under it on phones), out while
 * it is wanted. The toggle comes first in the page's order (drawn right of the slider on wider
 * screens: row-reverse), so Tab goes from the toggle on into the slider. Hover counts only for a mouse.
 */
export function SoundControls({ ui, onToggle, onVolume }: { ui: MusicUi; onToggle: () => void; onVolume: (volume: number) => void }) {
  const { reveal, dispatch, box } = useVolumeReveal(ui.on);
  const toggle = useRef<HTMLButtonElement>(null);
  /** The pointer type of the last press on the toggle: a tap may show the slider rather than mute. */
  const press = useRef<string | null>(null);
  const onClick = (e: MouseEvent<HTMLButtonElement>) => {
    // A click from Enter or Space has no pointer behind it (detail 0).
    const pointer = e.detail === 0 ? null : press.current;
    press.current = null;
    if (tapShows(reveal, pointer)) dispatch({ type: "show" });
    else onToggle();
  };
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key !== "Escape" || !reveal.open) {
      dispatch({ type: "poke" });
      return;
    }
    // One Escape, one thing: the slider closes and the view stays turned (scene.tsx keysTaken).
    e.preventDefault();
    dispatch({ type: "escape" });
    toggle.current?.focus({ preventScroll: true });
  };
  return (
    <div
      ref={box}
      className="flex flex-col items-end gap-2 md:flex-row-reverse md:items-start"
      onPointerEnter={(e) => e.pointerType === "mouse" && dispatch({ type: "enter" })}
      onPointerLeave={(e) => e.pointerType === "mouse" && dispatch({ type: "leave" })}
      onPointerDown={() => dispatch({ type: "poke" })}
      onKeyDown={onKeyDown}
      onFocus={(e: FocusEvent) => dispatch({ type: "focus", keyboard: keyboardFocus(e.target), entering: !within(box.current, e.relatedTarget) })}
      onBlur={(e: FocusEvent) => {
        if (!within(box.current, e.relatedTarget)) dispatch({ type: "blur" });
      }}
    >
      <button
        ref={toggle}
        type="button"
        data-sect-sound
        onPointerDown={(e) => {
          press.current = e.pointerType;
        }}
        onClick={onClick}
        aria-label={ui.on ? "Sound off" : "Sound on"}
        className="sect-panel sect-plate sect-ctl pointer-events-auto relative grid h-11 w-11 place-items-center rounded-[3px] text-[var(--sect-paper-soft)] transition-colors hover:text-[var(--sect-gold)] md:h-10 md:w-10"
      >
        <SpeakerIcon on={ui.on} />
      </button>
      {ui.on && (
        <VolumeSlider
          volume={ui.volume}
          open={reveal.open}
          onVolume={(v) => {
            onVolume(v);
            dispatch({ type: "poke" });
          }}
          onDrag={() => dispatch({ type: "drag", down: true })}
        />
      )}
    </div>
  );
}

/**
 * The music's volume: a native range input (so the arrow keys, Page Up/Down, Home and End, touch and
 * screen readers all work as they do anywhere), 0 to 100% in VOLUME_STEP steps, with a visible label
 * and readout. On wider screens its plate is the toggle's height and the line runs left to right; on
 * phones the plate is the toggle's width and the line runs bottom to top (sect.css). A drag must not
 * scroll the flight under it (touch-action: none). Put away (`open` false) it fades and its room
 * closes up (sect.css), and it is inert: out of the Tab order, the screen reader's and the pointer's.
 */
export function VolumeSlider({
  volume,
  onVolume,
  open = true,
  onDrag,
}: {
  volume: number;
  onVolume: (volume: number) => void;
  open?: boolean;
  /** A finger or the mouse went down on it. */
  onDrag?: () => void;
}) {
  const id = useId();
  const pct = volumePercent(volume);
  return (
    <div
      data-sect-volume
      data-open={open || undefined}
      inert={!open}
      onPointerDown={onDrag}
      className="sect-panel sect-plate pointer-events-auto relative flex h-[8.75rem] w-11 flex-col items-center gap-1.5 rounded-[3px] py-2 md:h-10 md:w-[7.75rem] md:items-stretch md:justify-center md:gap-[3px] md:px-2.5 md:py-0"
    >
      <div className="flex flex-col items-center gap-1 text-[0.5rem] uppercase leading-none tracking-[0.1em] md:flex-row md:items-baseline md:justify-between md:text-[0.625rem] md:tracking-[0.2em]">
        <label htmlFor={id} className="text-[var(--sect-paper-soft)]">
          Music<span className="sr-only"> volume</span>
        </label>
        <span aria-hidden className="tabular-nums tracking-[0.08em] text-[var(--sect-gold)]">
          {pct}%
        </span>
      </div>
      <input
        id={id}
        type="range"
        min={0}
        max={100}
        step={VOLUME_STEP}
        value={pct}
        aria-valuetext={volumeText(volume)}
        onChange={(e) => onVolume(volumeFromPercent(e.currentTarget.value))}
        className="sect-volume-range min-h-0 flex-1 md:w-full md:flex-none"
        style={{ "--v": `${pct}%` } as CSSProperties}
      />
    </div>
  );
}

/**
 * The loading screen's invitation (loading-screen.tsx keeps its place): a round gold seal with the
 * speaker and "Turn on sound" beside it, all one button. Its press is the
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
 * SoundPrompt's button: its words are its name (the seal is not read out). Its width holds when the
 * words change (min-w: the longer wording's, in rem so it grows with the text), so the centred
 * button does not shift and the seal stays under the finger for a second tap.
 */
export function SoundCall({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      data-sect-sound
      data-on={on || undefined}
      onClick={onToggle}
      className="sect-soundcall sect-fade-in group inline-flex min-h-11 min-w-[10.5rem] items-center gap-3 rounded-[2px] py-1 pl-1 pr-3 text-left"
    >
      <span aria-hidden className="sect-soundcall-seal">
        <SpeakerIcon on={on} />
      </span>
      <span className="text-[0.9375rem] leading-tight text-[var(--sect-paper)] transition-colors group-hover:text-[var(--sect-gold)]">
        {on ? "Sound on" : "Turn on sound"}
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
