"use client";

/**
 * The Jin Yong reference card: a small gold-on-ink plate near the pointer naming the reference it
 * rests on (lib/sect/lore.ts): its Chinese name in gold, its English name, and one line saying what
 * it is and which novel it comes from. No glow, no outline, no marker, no sound, no cursor change.
 *
 * Desktop: it fades in once the pointer has rested on a reference for LORE_HOVER_MS, follows the
 * pointer, and fades out as it leaves. Touch: a tap shows it above the finger for LORE_TAP_MS (a
 * tap anywhere else hides it); it never opens or flies anywhere. With reduced motion it appears and
 * goes without the fade.
 *
 * Purely decorative, so aria-hidden and never focusable: screen readers get the same names from a
 * visually hidden list on the stop's panel (content/panel.tsx), which costs sighted visitors nothing.
 */
import { forwardRef, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  LORE,
  LORE_CARD_IDLE,
  loreCardStep,
  loreCardWake,
  placeLoreCard,
  type LoreCardEvent,
  type LoreCardState,
  type LoreEntry,
  type LoreHit,
  type LoreId,
} from "@/lib/sect/lore";

export const LoreCard = forwardRef<HTMLDivElement, { id: LoreId | null; visible: boolean; reducedMotion?: boolean }>(function LoreCard(
  { id, visible, reducedMotion = false },
  ref,
) {
  const e: LoreEntry | null = id ? LORE[id] : null;
  return (
    <div
      ref={ref}
      aria-hidden
      data-sect-lore={id ?? undefined}
      className="sect-panel sect-plate pointer-events-none fixed left-0 top-0 z-30 max-w-[min(27rem,calc(100vw-1rem))] rounded-[2px] px-3 py-1.5"
      style={{
        opacity: visible && e ? 1 : 0,
        visibility: e ? "visible" : "hidden",
        transition: reducedMotion ? "none" : "opacity 180ms ease-out",
      }}
    >
      {e && (
        <>
          <p className="flex flex-wrap items-baseline gap-x-2">
            <span lang="zh-Hant" className="sect-zh text-[0.95rem] leading-tight tracking-[0.12em] text-[var(--sect-gold)]">
              {e.zh}
            </span>
            <span className="text-[0.66rem] uppercase tracking-[0.22em] text-[var(--sect-paper)]">{e.en}</span>
          </p>
          <p className="mt-0.5 text-[0.75rem] leading-snug text-[var(--sect-paper-soft)]">
            {e.what}
            {e.novel && (
              <>
                , from <cite className="italic">{e.novel}</cite>
              </>
            )}
          </p>
        </>
      )}
    </div>
  );
});

/** Runs the card's timing (lib/sect/lore.ts loreCardStep) with one timer; tells `onChange` when the card changes. */
export class LoreCardController {
  state: LoreCardState = LORE_CARD_IDLE;
  private timer: ReturnType<typeof setTimeout> | undefined;

  constructor(
    private readonly onChange: (s: LoreCardState) => void,
    private readonly now: () => number = () => performance.now(),
  ) {}

  dispatch = (e: LoreCardEvent): void => {
    const t = this.now();
    const prev = this.state;
    const next = loreCardStep(prev, e, t);
    // A tick always re-arms the timer: one that fired a hair early finds the delay not quite over.
    if (next === prev && e.type !== "tick") return;
    this.state = next;
    clearTimeout(this.timer);
    const wait = loreCardWake(next, t);
    this.timer = wait === null ? undefined : setTimeout(() => this.dispatch({ type: "tick" }), wait + 1);
    if (next.shown !== prev.shown || next.tapped !== prev.tapped) this.onChange(next);
  };

  dispose(): void {
    clearTimeout(this.timer);
  }
}

export interface LoreCardView {
  /** The reference whose card is up, or null. */
  shown: LoreId | null;
  /** What the card says: the last one shown (kept while it fades out). */
  content: LoreId | null;
  tapped: boolean;
}

/**
 * The card's state for the page: `onLore` for the scene (SectCanvasProps.onLore), the card's `ref`
 * and what it shows, and `hosted`, the reference a hovered hotspot holds (its label's note).
 * `blocked` (a reader or the page view is open) hides everything.
 */
export function useLoreCard(blocked: boolean) {
  const ref = useRef<HTMLDivElement>(null);
  const at = useRef<readonly [number, number]>([0, 0]);
  const [view, setView] = useState<LoreCardView>({ shown: null, content: null, tapped: false });
  const [hosted, setHosted] = useState<{ id: LoreId; host: string } | null>(null);
  const [ctl] = useState(
    () => new LoreCardController((s) => setView((v) => ({ shown: s.shown, content: s.shown ?? v.content, tapped: s.tapped }))),
  );
  useEffect(() => () => ctl.dispose(), [ctl]);

  /** Puts the card by the pointer (lib/sect/lore.ts placeLoreCard), from its measured size. */
  const place = useCallback(() => {
    const el = ref.current;
    if (!el || !ctl.state.shown) return;
    const [x, y] = placeLoreCard(
      at.current,
      { w: el.offsetWidth, h: el.offsetHeight },
      { w: window.innerWidth, h: window.innerHeight },
      ctl.state.tapped,
    );
    el.style.transform = `translate(${x}px, ${y}px)`;
  }, [ctl]);

  const onLore = useCallback(
    (hit: LoreHit | null, how: "hover" | "tap") => {
      if (hit) at.current = hit.at;
      const host = how === "hover" && hit?.host ? hit.host : null;
      setHosted((h) => (host ? (h?.id === hit!.id && h.host === host ? h : { id: hit!.id, host }) : null));
      ctl.dispatch({ type: how, id: hit && !hit.host ? hit.id : null });
      if (how === "tap") place();
    },
    [ctl, place],
  );

  // Placed once its new words are in (their size decides the side), then it follows the pointer.
  useLayoutEffect(() => {
    if (view.shown) place();
  }, [view, place]);
  useEffect(() => {
    if (!view.shown || view.tapped) return;
    const move = (e: PointerEvent) => {
      at.current = [e.clientX, e.clientY];
      place();
    };
    window.addEventListener("pointermove", move, { passive: true });
    return () => window.removeEventListener("pointermove", move);
  }, [view.shown, view.tapped, place]);
  // A tapped card goes at the next press anywhere (a tap on another reference then shows that one).
  useEffect(() => {
    if (!view.tapped) return;
    const press = () => ctl.dispatch({ type: "dismiss" });
    window.addEventListener("pointerdown", press, true);
    return () => window.removeEventListener("pointerdown", press, true);
  }, [view.tapped, ctl]);
  useEffect(() => {
    if (!blocked) return;
    ctl.dispatch({ type: "dismiss" });
    setHosted(null);
  }, [blocked, ctl]);

  return { ref, view, hosted, onLore };
}
