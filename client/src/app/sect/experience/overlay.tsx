"use client";

/**
 * DOM overlays for /sect: intro title, section rail (desktop) and its compact phone version, the
 * Places list, the "gathering" indicator for far jumps, the hover label, the Recentre button for a
 * view turned round, the graphics button, the page-view control, the home link and the debug HUD.
 * The content itself (panels, reader, page view) comes from ../content.
 *
 * The rails and the Places list are memoised: the page re-renders on every hold it passes, and they
 * only change with their own props.
 *
 * Everything here floats over the 3D scene, whose sky runs from dusk violet to near white: text
 * always sits on an ink plate (.sect-plate) and controls carry .sect-ctl for a focus ring that shows
 * on any background (sect.css).
 */
import { forwardRef, memo, useEffect, useRef, useState } from "react";
import type { HotspotLabel } from "@/lib/sect/content";
import { TIER_LABELS, type Tier } from "@/lib/sect/runtime";
import { QualityPicker } from "../quality-picker";

export const IntroTitle = forwardRef<HTMLDivElement>(function IntroTitle(_, ref) {
  return (
    <div
      ref={ref}
      className="sect-intro pointer-events-none fixed inset-x-0 top-[13vh] z-10 flex flex-col items-center px-6 text-center md:top-[9vh]"
    >
      <div className="sect-intro-seal flex flex-col items-center">
        <p
          className="sect-text-shadow sect-zh pl-[0.2em] text-[clamp(2.8rem,8vw,5.25rem)] leading-none tracking-[0.2em] text-[var(--sect-paper)]"
          lang="zh"
        >
          明教
        </p>
        <p className="sect-plate mt-4 rounded-[2px] px-3 py-1.5 text-[0.75rem] uppercase tracking-[0.34em] text-[var(--sect-gold)]">
          The Ming Sect
        </p>
      </div>
      <div className="fixed inset-x-0 bottom-[6vh] flex justify-center px-4">
        <div className="sect-plate flex max-w-[34rem] flex-col items-center rounded-[3px] px-4 py-2.5 text-center">
          <span className="text-[0.75rem] uppercase tracking-[0.3em] text-[var(--sect-paper)]">Scroll to ascend</span>
          <span className="mt-1 hidden text-[0.8125rem] text-[var(--sect-paper-soft)] md:inline">
            or press J / K to fly between places
          </span>
          <span className="mt-1 text-[0.8125rem] leading-snug text-[var(--sect-paper-soft)]">
            <span className="md:hidden">Tap anything that glows</span>
            <span className="hidden md:inline">Click anything that glows</span>
          </span>
          <svg className="sect-hint-arrow mt-2 text-[var(--sect-gold)]" width="14" height="18" viewBox="0 0 14 18" aria-hidden>
            <path d="M7 1v15M1 10l6 6 6-6" fill="none" stroke="currentColor" strokeWidth="1.2" />
          </svg>
        </div>
      </div>
    </div>
  );
});

export interface RailStop {
  id: string;
  label: string;
  zh: string;
  /** What the stop shows on the main page ("Projects"). */
  section: string;
}

/** What a rail button does now: open the reader of the place the camera holds at, or fly there. */
function railLabel(s: RailStop, on: boolean, atHold: boolean): string {
  return on && atHold ? `${s.label}, ${s.section}: open` : `Fly to ${s.label}, ${s.section}`;
}

/**
 * Screen readers hear where the camera arrived (the panel appears silently otherwise). Rendered by
 * both rails; only the one on screen for the viewport size is announced (the other is display:none).
 */
function Arrival({ stops, active, atHold }: { stops: RailStop[]; active: string | null; atHold: boolean }) {
  const s = atHold ? stops.find((x) => x.id === active) : undefined;
  const text = s ? `${s.label}, ${s.section}.` : "";
  return (
    <p className="sr-only" role="status" aria-live="polite">
      {text}
    </p>
  );
}

/**
 * Desktop: the eleven places down the right edge. A click flies there; a click on the place the
 * camera is already at opens its reader. Only on screens at least 500 px tall: on a phone on its side
 * the column ran down under the voice orb (a tap meant for the last places started a call), so short
 * screens get the compact row instead.
 */
export const SectionRail = memo(function SectionRail({
  stops,
  active,
  atHold,
  onJump,
}: {
  stops: RailStop[];
  active: string | null;
  /** The camera holds at a place (its panel names it): the active label hides unless hovered. */
  atHold: boolean;
  onJump: (id: string) => void;
}) {
  // Only the diamonds (and a label while it shows) take the pointer: the hidden labels are up to
  // 380 px wide and would otherwise swallow clicks on a right-hand panel and on the scene.
  return (
    <nav
      aria-label="Places along the flight"
      className="pointer-events-none fixed right-4 top-1/2 z-20 hidden -translate-y-1/2 [@media(min-width:48rem)_and_(min-height:31.25rem)]:block"
    >
      <Arrival stops={stops} active={active} atHold={atHold} />
      <ol className="flex flex-col items-end gap-[0.3rem]">
        {stops.map((s, i) => {
          const on = s.id === active;
          const shown = on && !atHold;
          return (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => onJump(s.id)}
                aria-current={on ? "location" : undefined}
                aria-label={railLabel(s, on, atHold)}
                className="sect-ctl group pointer-events-none flex items-center gap-1.5 rounded-[3px] text-[0.72rem] uppercase tracking-[0.24em] text-[var(--sect-paper)]"
              >
                <span
                  className={`sect-plate whitespace-nowrap rounded-[2px] px-2.5 py-1 transition-opacity duration-300 ${shown ? "pointer-events-auto opacity-100" : "opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100"}`}
                >
                  <span className="mr-2 text-[var(--sect-gold)]">{String(i + 1).padStart(2, "0")}</span>
                  {s.section}
                  <span className="ml-2 normal-case tracking-[0.06em] text-[var(--sect-paper-soft)]">{s.label}</span>
                </span>
                <span aria-hidden className="pointer-events-auto grid h-6 w-6 cursor-pointer place-items-center">
                  <span
                    className={`block h-2.5 w-2.5 rotate-45 border border-[var(--sect-gold)] shadow-[0_0_0_1px_rgba(14,12,20,0.6)] transition-colors group-hover:bg-[var(--sect-gold-soft)] group-focus-visible:!bg-[var(--sect-gold)] ${on ? "!bg-[var(--sect-gold)]" : "bg-[rgba(14,12,20,0.62)]"}`}
                  />
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
});

/**
 * Phones and short screens: a row of eleven diamonds under the top bar, with the current place's name
 * beneath. Its buttons narrow to 28 px on the smallest phones (320 px), so the row fits.
 */
export const CompactRail = memo(function CompactRail({
  stops,
  active,
  atHold = false,
  labelHidden = false,
  onJump,
}: {
  stops: RailStop[];
  active: string | null;
  /** The camera holds at the active place (a tap there opens its reader instead of flying). */
  atHold?: boolean;
  /**
   * The intro title is up: it already says where the visitor is, and on a phone the place's name
   * would sit over its characters. The name fades in once the title has gone.
   */
  labelHidden?: boolean;
  onJump: (id: string) => void;
}) {
  const cur = stops.find((s) => s.id === active);
  return (
    <nav
      aria-label="Places along the flight"
      className="pointer-events-none fixed inset-x-0 top-[3.85rem] z-20 flex flex-col items-center [@media(min-width:48rem)_and_(min-height:31.25rem)]:hidden"
    >
      <Arrival stops={stops} active={active} atHold={atHold} />
      <ol className="pointer-events-auto flex items-center">
        {stops.map((s) => {
          const on = s.id === active;
          return (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => onJump(s.id)}
                aria-current={on ? "location" : undefined}
                aria-label={railLabel(s, on, atHold)}
                className="sect-ctl grid h-11 w-8 place-items-center rounded-[2px] [@media(max-width:340px)]:w-7"
              >
                <span
                  aria-hidden
                  className={`block h-2.5 w-2.5 rotate-45 border border-[var(--sect-gold)] shadow-[0_0_0_1px_rgba(14,12,20,0.6)] ${on ? "bg-[var(--sect-gold)]" : "bg-[rgba(14,12,20,0.62)]"}`}
                />
              </button>
            </li>
          );
        })}
      </ol>
      {cur && (
        <p
          aria-hidden
          className={`sect-plate rounded-[2px] px-2.5 py-0.5 text-[0.68rem] uppercase tracking-[0.22em] text-[var(--sect-paper)] transition-opacity duration-500 ${labelHidden ? "opacity-0" : "opacity-100"}`}
        >
          {cur.section}{" "}
          <span lang="zh" className="sect-zh ml-1 tracking-[0.12em] text-[var(--sect-gold)]">
            {cur.zh}
          </span>
        </p>
      )}
    </nav>
  );
});

export interface PlaceItem {
  id: string;
  label: string;
  area: string;
}

export interface PlaceGroup {
  id: string;
  section: string;
  items: PlaceItem[];
}

/** Every place and item along the flight, grouped by area; a scrolling popover from the top bar. */
export const PlacesList = memo(function PlacesList({
  groups,
  open,
  onToggle,
  onClose,
  onFocusPlace,
  onSelect,
}: {
  groups: PlaceGroup[];
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
  onFocusPlace: (id: string | null) => void;
  onSelect: (id: string) => void;
}) {
  const rootRef = useRef<HTMLElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  // Escape closes the list and returns focus to its toggle; a click outside closes it too.
  useEffect(() => {
    if (!open) return;
    const key = (e: KeyboardEvent) => {
      // An open reader takes the first Escape.
      if (e.key !== "Escape" || document.querySelector(".sc-scrim, .sc-page")) return;
      onClose();
      toggleRef.current?.focus();
    };
    const down = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) onClose();
    };
    window.addEventListener("keydown", key);
    window.addEventListener("pointerdown", down);
    return () => {
      window.removeEventListener("keydown", key);
      window.removeEventListener("pointerdown", down);
    };
  }, [open, onClose]);
  return (
    <nav ref={rootRef} aria-label="Every place" className="relative">
      <button
        ref={toggleRef}
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls="sect-places"
        className="sect-panel sect-plate sect-ctl relative min-h-10 rounded-[3px] px-3 text-[0.62rem] uppercase tracking-[0.2em] text-[var(--sect-paper)] md:min-h-10 md:px-4 md:text-[0.72rem] md:tracking-[0.26em] [@media(max-width:340px)]:px-2 [@media(max-width:340px)]:tracking-[0.12em]"
      >
        Places
      </button>
      {/* Always in the document (hidden when closed), so aria-controls points at something. */}
      <div
        id="sect-places"
        hidden={!open}
        className="sect-panel sect-scroll absolute right-0 top-12 max-h-[min(72vh,40rem)] w-[min(19rem,calc(100vw-1.5rem))] overflow-y-auto overflow-x-hidden overscroll-contain rounded-[3px] px-3 py-3"
        style={{ background: "var(--sect-panel-strong)" }}
      >
        {groups.map((g, i) => (
          <section key={g.id} aria-labelledby={`sect-places-${g.id}`} className="py-1.5">
            <h3 id={`sect-places-${g.id}`} className="flex flex-wrap items-baseline gap-x-2 px-2 text-[0.62rem] uppercase tracking-[0.26em] text-[var(--sect-gold)]">
              <span className="text-[var(--sect-paper-soft)]">{String(i + 1).padStart(2, "0")}</span>
              {g.section}
            </h3>
            <ul className="mt-1">
              {g.items.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    className="w-full rounded-[2px] px-2 py-1.5 text-left text-[0.86rem] leading-snug text-[var(--sect-paper-soft)] hover:bg-[var(--sect-gold-soft)] hover:text-[var(--sect-paper)] focus-visible:bg-[var(--sect-gold-soft)] focus-visible:text-[var(--sect-paper)] pointer-coarse:min-h-11"
                    onMouseEnter={() => onFocusPlace(p.id)}
                    onMouseLeave={() => onFocusPlace(null)}
                    onFocus={() => onFocusPlace(p.id)}
                    onBlur={() => onFocusPlace(null)}
                    onClick={() => {
                      // The list hides as the reader opens: hand focus to the toggle first, so
                      // closing the reader brings it back there and not to the page body.
                      toggleRef.current?.focus({ preventScroll: true });
                      onSelect(p.id);
                    }}
                  >
                    {p.label}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </nav>
  );
});

/**
 * The graphics button, in the sound toggle's place (sound-toggle.tsx): the loading screen's picker
 * in a small popover. A pick that keeps the textures applies at once and the popover stays open, so
 * the visitor can compare; one that needs other textures brings the loading screen back
 * (sect-experience.tsx). Escape or a press outside closes it, and the focus returns to the button.
 *
 * Once the loading screen goes, a focus left in its picker comes here (it would drop to the page).
 */
export function QualityButton({ tier, recommended, onPick }: { tier: Tier; recommended: Tier; onPick: (tier: Tier) => void }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (document.activeElement?.closest(".sect-veil [data-sect-picker]")) buttonRef.current?.focus({ preventScroll: true });
  }, []);
  useEffect(() => {
    if (!open) return;
    const key = (e: KeyboardEvent) => {
      // An open reader takes the first Escape.
      if (e.key !== "Escape" || document.querySelector(".sc-scrim, .sc-page")) return;
      setOpen(false);
      buttonRef.current?.focus();
    };
    const down = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("keydown", key);
    window.addEventListener("pointerdown", down);
    return () => {
      window.removeEventListener("keydown", key);
      window.removeEventListener("pointerdown", down);
    };
  }, [open]);
  return (
    <div ref={rootRef} data-sect-quality className="pointer-events-auto relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={`Graphics: ${TIER_LABELS[tier]}`}
        aria-expanded={open}
        aria-controls="sect-quality"
        className="sect-panel sect-plate sect-ctl relative grid h-11 w-11 place-items-center rounded-[3px] text-[var(--sect-paper-soft)] transition-colors hover:text-[var(--sect-gold)] md:h-10 md:w-10"
      >
        <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden className={open ? "text-[var(--sect-gold)]" : undefined}>
          <path d="M2.5 4.5h13M2.5 9h13M2.5 13.5h13" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          <g fill="rgb(18, 14, 24)" stroke="currentColor" strokeWidth="1.3">
            <circle cx="6" cy="4.5" r="1.75" />
            <circle cx="12" cy="9" r="1.75" />
            <circle cx="8" cy="13.5" r="1.75" />
          </g>
        </svg>
      </button>
      {/* Always in the document (hidden when closed), so aria-controls points at something. */}
      <div
        id="sect-quality"
        hidden={!open}
        className="sect-panel absolute right-0 top-12 w-[min(16rem,calc(100vw-1.5rem))] rounded-[3px] px-2 pb-2 pt-2.5"
        style={{ background: "var(--sect-panel-strong)" }}
      >
        {open && <QualityPicker tier={tier} recommended={recommended} onPick={onPick} layout="column" name="sect-quality-menu" />}
      </div>
    </div>
  );
}

/** A far jump is waiting for its area to load: a small seal that turns, with the place's name. */
export function Gathering({ label }: { label: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="sect-panel sect-plate pointer-events-none fixed left-1/2 top-[8.2rem] z-30 flex -translate-x-1/2 items-center gap-3 rounded-[3px] px-4 py-2 md:top-5"
    >
      <span aria-hidden className="sect-gather block h-3 w-3 rotate-45 border border-[var(--sect-gold)]" />
      <span className="text-[0.68rem] uppercase tracking-[0.26em] text-[var(--sect-paper)]">Loading {label}</span>
    </div>
  );
}

/** A short status line (a link that pointed at nothing here), with a close button. */
export function Notice({ text, onDismiss }: { text: string; onDismiss: () => void }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="sect-panel sect-plate fixed left-1/2 top-[8.2rem] z-[60] flex w-[min(30rem,calc(100vw-2rem))] -translate-x-1/2 items-start gap-3 rounded-[3px] py-2 pl-4 pr-2 md:top-5"
    >
      <span className="flex-1 py-1 text-[0.8125rem] leading-snug text-[var(--sect-paper)]">{text}</span>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="sect-ctl grid h-8 w-8 shrink-0 place-items-center rounded-[2px] text-[var(--sect-paper-soft)] hover:text-[var(--sect-gold)]"
      >
        <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden>
          <path d="M2 2l12 12M14 2L2 14" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      </button>
    </div>
  );
}

/**
 * The label over the hotspot under the pointer: its name, its Chinese name, and one line about it
 * (lib/sect/content.ts hotspotLabel), cut to two lines so it stays small. The scene moves it and
 * fades it (the page sets its transform and opacity directly, every frame).
 */
export const HoverLabel = forwardRef<HTMLDivElement, { label: HotspotLabel | null }>(function HoverLabel({ label }, ref) {
  return (
    <div
      ref={ref}
      aria-hidden
      className="sect-panel sect-plate pointer-events-none fixed left-0 top-0 z-30 max-w-[min(18rem,calc(100vw-2rem))] rounded-[2px] px-3 py-1 transition-opacity duration-150"
      style={{ opacity: 0 }}
    >
      {label && (
        <>
          <p className="text-[0.68rem] uppercase tracking-[0.24em] text-[var(--sect-paper)]">
            {label.title}
            {label.zh && (
              <span lang="zh" className="sect-zh ml-2 normal-case tracking-[0.12em] text-[var(--sect-gold)]">
                {label.zh}
              </span>
            )}
          </p>
          {label.blurb && <p className="mb-0.5 line-clamp-2 text-[0.75rem] leading-snug text-[var(--sect-paper-soft)]">{label.blurb}</p>}
        </>
      )}
    </div>
  );
});

/** A screen rectangle in CSS pixels (a DOMRect fits). */
export interface ScreenBox {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

/**
 * Where the hover label goes, as the point its bottom centre sits on: over the anchor `at`, kept
 * `margin` px inside the window, and moved clear of the boxes in `avoid` (the content panel up at a
 * stop) by `gap` px when it would cover one. Of the four ways out (left of the box, right of it,
 * above, below), the shortest move that stays inside the window and clear of every box wins; when
 * none does, the label stays where it was (still inside the window).
 */
export function placeHoverLabel(
  at: readonly [number, number],
  label: { w: number; h: number },
  view: { w: number; h: number },
  avoid: readonly ScreenBox[] = [],
  margin = 8,
  gap = 12,
): [number, number] {
  const { w, h } = label;
  const minX = w / 2 + margin;
  const maxX = Math.max(view.w - w / 2 - margin, minX);
  const minY = h + margin;
  const maxY = Math.max(view.h - margin, minY);
  const clampX = (x: number) => Math.min(Math.max(x, minX), maxX);
  const clampY = (y: number) => Math.min(Math.max(y, minY), maxY);
  const x0 = clampX(at[0]);
  const y0 = clampY(at[1]);
  const hits = (x: number, y: number) =>
    avoid.some((b) => x - w / 2 < b.right + gap && x + w / 2 > b.left - gap && y - h < b.bottom + gap && y > b.top - gap);
  if (!hits(x0, y0)) return [x0, y0];
  let best: [number, number] | null = null;
  let bestD = Infinity;
  for (const b of avoid) {
    const ways: [number, number][] = [
      [b.left - gap - w / 2 - 0.5, y0],
      [b.right + gap + w / 2 + 0.5, y0],
      [x0, b.top - gap - 0.5],
      [x0, b.bottom + gap + h + 0.5],
    ];
    for (const [x, y] of ways) {
      if (x < minX || x > maxX || y < minY || y > maxY || hits(x, y)) continue;
      const d = Math.hypot(x - x0, y - y0);
      if (d < bestD) {
        bestD = d;
        best = [x, y];
      }
    }
  }
  return best ?? [x0, y0];
}

/**
 * Shown while the view is turned round (free look past 90 degrees): one tap swings it back to the
 * path's framing. Mostly for phones, which have no Escape key; on a desktop it names the key too.
 * Under the compact rail on phones, at the bottom centre on desktops.
 *
 * A keyboard user who presses it keeps it (and the focus) until they move on: it does not vanish
 * from under the focus as the view swings back, which would drop the focus to the top of the page.
 */
export function RecentreButton({ visible, onRecentre }: { visible: boolean; onRecentre: () => void }) {
  const [keyFocus, setKeyFocus] = useState(false);
  if (!visible && !keyFocus) return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 top-[8.2rem] z-30 flex justify-center md:bottom-6 md:top-auto">
      <button
        type="button"
        onClick={onRecentre}
        onFocus={(e) => setKeyFocus(focusVisible(e.currentTarget))}
        onBlur={() => setKeyFocus(false)}
        aria-label="Recentre the view"
        className="sect-panel sect-plate sect-ctl pointer-events-auto flex min-h-11 items-center gap-2 rounded-[3px] px-3 text-[0.62rem] uppercase tracking-[0.2em] text-[var(--sect-paper)] hover:text-[var(--sect-gold)] md:min-h-10 md:px-4 md:text-[0.72rem] md:tracking-[0.24em]"
      >
        <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden className="text-[var(--sect-gold)]">
          <path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9M13.5 2v3.2h-3.2" fill="none" stroke="currentColor" strokeWidth="1.4" />
        </svg>
        Recentre
        <span aria-hidden className="hidden normal-case tracking-[0.06em] text-[var(--sect-paper-soft)] md:inline">
          · Esc
        </span>
      </button>
    </div>
  );
}

/** The element has keyboard focus (a click or a tap does not count). */
function focusVisible(el: HTMLElement): boolean {
  try {
    return el.matches(":focus-visible");
  } catch {
    // An engine without :focus-visible: treat any focus as the keyboard's.
    return true;
  }
}

const LOOK_HINT_KEY = "sect.lookHint";

/** The visitor has turned the view before (on this browser): the free-look hint stays away. */
export function lookHintSeen(): boolean {
  try {
    return window.localStorage.getItem(LOOK_HINT_KEY) === "1";
  } catch {
    return false;
  }
}

export function markLookHintSeen(): void {
  try {
    window.localStorage.setItem(LOOK_HINT_KEY, "1");
  } catch {
    // Storage blocked (private window): the hint just shows again next visit.
  }
}

/**
 * Free look's one quiet hint, under the top-left plate on a wide screen and under the place row on a
 * phone (the page shows it there once the intro has gone). A touch screen is told to swipe: sideways,
 * that turns the view toward items a narrow screen leaves out. The page hides it after the first turn.
 */
export function LookHint({ visible, touch = false }: { visible: boolean; touch?: boolean }) {
  return (
    <p
      aria-hidden
      className="sect-plate pointer-events-none fixed left-1/2 top-[8.2rem] z-20 -translate-x-1/2 whitespace-nowrap rounded-[2px] px-2.5 py-1 text-[0.62rem] uppercase tracking-[0.24em] text-[var(--sect-paper-soft)] transition-opacity duration-500 md:left-5 md:top-[4.4rem] md:translate-x-0"
      style={{ opacity: visible ? 1 : 0 }}
    >
      {touch ? "Swipe to look around" : "Drag to look around"}
    </p>
  );
}

export const DebugHud = forwardRef<HTMLDivElement>(function DebugHud(_, ref) {
  return (
    <div
      ref={ref}
      className="pointer-events-none fixed left-3 top-24 z-40 whitespace-pre rounded-[3px] bg-black/60 px-3 py-2 font-mono text-[11px] leading-[1.45] text-[#d9f7e8]"
      data-sect-hud
    >
      debug
    </div>
  );
});

/**
 * Top-left, on an ink plate: whose portfolio this is (a link back to the main site), and the
 * one-page view of everything. The link is a plain one: a full page load frees the scene's memory,
 * its decoder workers and its audio, which a client-side route change would keep alive.
 */
export function TopLinks({ onReadAsPage }: { onReadAsPage: () => void }) {
  return (
    <header className="fixed left-3 top-3 z-20 md:left-5 md:top-4">
      <div className="sect-panel sect-plate relative flex items-stretch rounded-[3px]">
        {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- a full page load (see above) */}
        <a
          href="/"
          className="sect-ctl flex min-h-11 items-center gap-2.5 rounded-[2px] px-2.5 text-[var(--sect-paper)] hover:text-[var(--sect-gold)] md:min-h-10 md:px-4 [@media(max-width:340px)]:px-2"
        >
          <span className="font-serif text-[1.05rem] leading-none tracking-[0.01em]">Bill Zhang</span>
          <span className="sr-only text-[0.68rem] uppercase tracking-[0.22em] text-[var(--sect-paper-soft)] md:not-sr-only">
            art3m1s.me
          </span>
        </a>
        <span aria-hidden className="my-2.5 w-px bg-[var(--sect-gold-soft)]" />
        <button
          type="button"
          onClick={onReadAsPage}
          className="sect-ctl flex min-h-11 items-center rounded-[2px] px-2.5 text-[0.62rem] uppercase tracking-[0.14em] text-[var(--sect-paper)] hover:text-[var(--sect-gold)] md:min-h-10 md:px-4 md:text-[0.72rem] md:tracking-[0.24em] [@media(max-width:340px)]:px-2 [@media(max-width:340px)]:tracking-[0.06em]"
        >
          Read as page
        </button>
      </div>
    </header>
  );
}
