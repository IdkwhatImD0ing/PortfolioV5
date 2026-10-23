"use client";

/**
 * Modal behaviour for the reader and the one-page view: remember what had focus and give it back on
 * close, keep Tab inside, lock the page scroll (it drives the camera) while open.
 *
 * The voice orb (.sect-orb) floats above every modal on purpose: its panel and text chat must keep
 * working while a reader is open (the agent opens readers while it answers). So focus inside the orb
 * is never pulled back, Tab moves on from the modal's last control to the orb, and a modal that
 * opens while the chat box has the caret leaves it there.
 */
import { useEffect, useRef, type KeyboardEvent as ReactKeyboardEvent, type RefObject } from "react";

const FOCUSABLE =
  'a[href], button:not([disabled]), iframe, input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Floating UI that lives beside the modals and may hold focus while one is open. */
const SIBLING_UI = ".sect-orb";

function focusables(root: ParentNode): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => el.getClientRects().length > 0 && !el.closest("[inert]"),
  );
}

/** The orb's controls, when the orb is on the page. */
function siblingFocusables(): HTMLElement[] {
  if (typeof document === "undefined") return [];
  const orb = document.querySelector(SIBLING_UI);
  return orb ? focusables(orb) : [];
}

/**
 * True when focus at `el` belongs to the orb (or to a field that asked to keep the caret, like the
 * main page's `data-keeps-focus`): a modal must not take it away.
 */
export function keepsFocus(el: Element | null | undefined): boolean {
  if (!el || typeof el.closest !== "function") return false;
  return el.closest(SIBLING_UI) !== null || el.closest("[data-keeps-focus]") !== null;
}

/** True when the element that has focus now belongs to the orb (see keepsFocus). */
export function focusIsKept(): boolean {
  return typeof document !== "undefined" && keepsFocus(document.activeElement);
}

/**
 * Keep Tab and Shift+Tab inside `root`, wrapping at both ends. When the orb is on the page, Tab from
 * the last control goes to the orb (and Shift+Tab from the first to the orb's last control), so a
 * keyboard can reach the call and chat controls over a reader; from the orb, Tab comes back.
 */
export function trapTab(e: ReactKeyboardEvent<HTMLElement> | KeyboardEvent, root: HTMLElement | null): void {
  if (!root || e.key !== "Tab") return;
  const items = focusables(root);
  if (items.length === 0) {
    e.preventDefault();
    return;
  }
  const first = items[0];
  const last = items[items.length - 1];
  const orb = siblingFocusables();
  const active = document.activeElement as HTMLElement | null;
  const inside = !!active && root.contains(active);
  const before = (a: HTMLElement, b: HTMLElement) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
  if (e.shiftKey) {
    // On the first control, or on a non-tabbable spot before it (the heading, the sheet itself).
    if (!inside || active === first || (active && !items.includes(active) && before(active, first))) {
      e.preventDefault();
      (orb[orb.length - 1] ?? last).focus();
    }
  } else if (!inside || active === last || (active && !items.includes(active) && before(last, active))) {
    e.preventDefault();
    (orb[0] ?? first).focus();
  }
}

function usable(el: HTMLElement | null): el is HTMLElement {
  if (!el || el === document.body || !el.isConnected || el.getClientRects().length === 0) return false;
  if (el.closest("[inert]")) return false;
  return getComputedStyle(el).visibility !== "hidden";
}

/**
 * While mounted: lock the document scroll and, on unmount, return focus to the element that had it
 * when the modal opened. When that element is gone or hidden by then (an item in the map, the
 * panel of the area the camera left), `fallbackFocus` names somewhere sensible instead. Focus that
 * escapes the modal (a click on the scene behind) is pulled back, except into the orb.
 */
export function useModalLifecycle(
  rootRef: RefObject<HTMLElement | null>,
  active = true,
  fallbackFocus?: () => HTMLElement | null,
): void {
  const openerRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!active) return;
    // Focus already inside the modal means this effect is running again for the same opening (React's
    // development double run): keep the opener from the first run.
    const now = document.activeElement as HTMLElement | null;
    if (!now || !rootRef.current?.contains(now)) openerRef.current = now;
    const opener = openerRef.current;
    const html = document.documentElement;
    const prevOverflow = html.style.overflow;
    html.style.overflow = "hidden";
    const onFocusIn = (e: FocusEvent) => {
      const root = rootRef.current;
      const t = e.target as Element | null;
      if (!root || !t || root.contains(t) || keepsFocus(t)) return;
      const items = focusables(root);
      (items[0] ?? root).focus({ preventScroll: true });
    };
    document.addEventListener("focusin", onFocusIn);
    return () => {
      document.removeEventListener("focusin", onFocusIn);
      html.style.overflow = prevOverflow;
      // After this commit: the page marks open modals on <body> (and hides the area panels behind
      // them) in an effect that runs after this cleanup, so the opener may not be focusable yet.
      window.setTimeout(() => {
        const now = document.activeElement;
        // Something else took focus meanwhile (another reader opened, the visitor clicked).
        if (now && now !== document.body && now !== document.documentElement) return;
        const to = usable(opener) ? opener : (fallbackFocus?.() ?? null);
        if (usable(to)) to.focus({ preventScroll: true });
      }, 0);
    };
    // The fallback is read when the modal closes; a new function each render must not reopen it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rootRef, active]);
}

/**
 * Where focus goes when a modal over the flight closes and its opener is gone: the open button of
 * the area panel on screen, else the rail's current place, else the Map button.
 */
export function flightFocusFallback(): HTMLElement | null {
  const visible = (el: HTMLElement) => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== "hidden";
  const panelBtn = Array.from(document.querySelectorAll<HTMLElement>(".sc-panel [data-sect-open]")).find(visible);
  if (panelBtn) return panelBtn;
  const rail = Array.from(document.querySelectorAll<HTMLElement>('nav [aria-current="location"]')).find(visible);
  if (rail) return rail;
  return document.querySelector<HTMLElement>("[data-sect-places]");
}

/** True when the visitor asked for less motion. */
export function reducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
