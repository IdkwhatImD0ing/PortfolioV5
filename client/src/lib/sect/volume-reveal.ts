/**
 * When the music's volume slider (experience/sound-toggle.tsx VolumeSlider) shows beside the sound
 * toggle. It used to stay out for as long as the music played, with no way to put it away ("there is
 * no way to close the slider after it opens", the owner, 2026-10-24). Now it comes when it is wanted
 * and goes when it is not:
 *
 * Shows
 * - for a few seconds after the music turns on (or when the toggle first appears with the music
 *   already on), so a visitor sees that it is there;
 * - while a mouse is over the toggle or the slider;
 * - while the keyboard's focus is on either: Tab onto the toggle shows it, and the next Tab goes on
 *   into it;
 * - on a tap on the speaker while the music plays and the slider is hidden: on a touch screen that
 *   tap shows the slider instead of muting, and a tap while it shows mutes (as phone video players
 *   do). A mouse click and Enter or Space always mute or unmute.
 *
 * Hides
 * - REVEAL_LEAVE_MS after the mouse leaves both (so crossing the gap between them does not close it);
 * - at once on a click or tap anywhere else, or on Escape (the focus goes back to the toggle);
 * - after REVEAL_IDLE_MS with nothing done to it, but never while a mouse is over it, the keyboard's
 *   focus is in it or a finger or the mouse is dragging it;
 * - with the music (muted, the toggle stands alone).
 *
 * Pure: a reducer over the visitor's moves. The component runs the one timer it asks for (closeIn)
 * and tells it what happened.
 */

/** How long the slider stays with nothing done to it, and how long it shows when the music turns on. */
export const REVEAL_IDLE_MS = 4000;

/** How long it stays after the mouse leaves the toggle and the slider. */
export const REVEAL_LEAVE_MS = 700;

export interface RevealState {
  /** The music plays (the slider is on the page only then). */
  on: boolean;
  /** The slider shows. */
  open: boolean;
  /** A mouse is over the toggle or the slider. */
  hover: boolean;
  /** The keyboard's focus is on the toggle or the slider. */
  focus: boolean;
  /** A finger or the mouse is down on the slider. */
  drag: boolean;
  /** Close after this many milliseconds (the component's timer), or not by time (null). */
  closeIn: number | null;
  /** Counts the timers asked for: a timer that fires after a newer one was asked for is ignored. */
  timer: number;
}

export type RevealEvent =
  /** The music turned on or off. */
  | { type: "music"; on: boolean }
  /** A mouse came over the toggle or the slider, or left both. */
  | { type: "enter" }
  | { type: "leave" }
  /**
   * The focus moved onto the toggle or the slider: by the keyboard (:focus-visible) or not (a click),
   * and from outside the two or between them.
   */
  | { type: "focus"; keyboard: boolean; entering: boolean }
  /** The focus left both. */
  | { type: "blur" }
  /** A tap on the toggle that shows the slider (tapShows). */
  | { type: "show" }
  /** Any other press, key or change on the toggle or the slider: the idle time starts again. */
  | { type: "poke" }
  /** A finger or the mouse went down on the slider, or came up (wherever it went meanwhile). */
  | { type: "drag"; down: boolean }
  /** A click or tap anywhere else on the page. */
  | { type: "outside" }
  | { type: "escape" }
  /** The component's timer fired: the `timer` it was armed for. */
  | { type: "timeout"; timer: number };

/** Before the music has ever played: nothing shows, nothing waits. */
export const REVEAL_START: RevealState = { on: false, open: false, hover: false, focus: false, drag: false, closeIn: null, timer: 0 };

/** Something keeps the slider out, whatever the time. */
export function revealHeld(s: RevealState): boolean {
  return s.hover || s.focus || s.drag;
}

/** The timer starts again for `ms`; none while closed or held. */
function arm(s: RevealState, ms: number): RevealState {
  if (!s.open || revealHeld(s)) return s.closeIn === null ? s : { ...s, closeIn: null };
  return { ...s, closeIn: ms, timer: s.timer + 1 };
}

/** What held it let go: the timer starts for `ms` unless it is already running or something still holds. */
function release(s: RevealState, ms: number): RevealState {
  if (!s.open || revealHeld(s)) return arm(s, ms);
  return s.closeIn === null ? arm(s, ms) : s;
}

function close(s: RevealState): RevealState {
  return s.open || s.closeIn !== null ? { ...s, open: false, closeIn: null } : s;
}

export function revealReducer(s: RevealState, e: RevealEvent): RevealState {
  switch (e.type) {
    case "music":
      if (e.on === s.on) return s;
      return e.on ? arm({ ...s, on: true, open: true }, REVEAL_IDLE_MS) : close({ ...s, on: false, drag: false });
    case "enter":
      return arm({ ...s, hover: true, open: s.on }, REVEAL_IDLE_MS);
    case "leave":
      return s.hover ? release({ ...s, hover: false }, REVEAL_LEAVE_MS) : s;
    case "focus": {
      const next = { ...s, focus: e.keyboard };
      // Only coming in from outside opens it: Escape hands the focus back to the toggle, closed.
      if (e.keyboard && e.entering && s.on) return arm({ ...next, open: true }, REVEAL_IDLE_MS);
      return release(next, REVEAL_IDLE_MS);
    }
    case "blur":
      return s.focus ? release({ ...s, focus: false }, REVEAL_LEAVE_MS) : s;
    case "show":
      return s.on ? arm({ ...s, open: true }, REVEAL_IDLE_MS) : s;
    case "poke":
      return arm(s, REVEAL_IDLE_MS);
    case "drag":
      if (e.down) return s.on ? arm({ ...s, drag: true }, REVEAL_IDLE_MS) : s;
      return s.drag ? release({ ...s, drag: false }, REVEAL_IDLE_MS) : s;
    case "outside":
    case "escape":
      return close(s.drag ? { ...s, drag: false } : s);
    case "timeout":
      return e.timer === s.timer && s.closeIn !== null && !revealHeld(s) ? close(s) : s;
  }
}

/**
 * A press on the toggle shows the slider instead of muting: a tap (a touch or a pen, not a mouse and
 * not a key: `pointer` is the pointer type of the press, null for a key) while the music plays and
 * the slider is hidden.
 */
export function tapShows(s: RevealState, pointer: string | null): boolean {
  return pointer !== null && pointer !== "mouse" && s.on && !s.open;
}
