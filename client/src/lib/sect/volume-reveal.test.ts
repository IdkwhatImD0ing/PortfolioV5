import { describe, expect, it } from "vitest";
import { REVEAL_IDLE_MS, REVEAL_LEAVE_MS, REVEAL_START, revealHeld, revealReducer, tapShows, type RevealEvent, type RevealState } from "./volume-reveal";

/** The state after these events, from the start. */
function run(...events: RevealEvent[]): RevealState {
  return events.reduce(revealReducer, REVEAL_START);
}

/** Its timer fires (the one it last asked for). */
function fire(s: RevealState): RevealState {
  return revealReducer(s, { type: "timeout", timer: s.timer });
}

const on: RevealEvent = { type: "music", on: true };
const off: RevealEvent = { type: "music", on: false };
const keyIn: RevealEvent = { type: "focus", keyboard: true, entering: true };

describe("revealReducer", () => {
  it("shows the slider for a few seconds when the music turns on, then puts it away", () => {
    expect(REVEAL_START.open).toBe(false);
    const s = run(on);
    expect(s.open).toBe(true);
    expect(s.closeIn).toBe(REVEAL_IDLE_MS);
    expect(REVEAL_IDLE_MS).toBeGreaterThanOrEqual(3000);
    expect(REVEAL_IDLE_MS).toBeLessThanOrEqual(5000);
    const t = fire(s);
    expect(t.open).toBe(false);
    expect(t.closeIn).toBeNull();
    // The music still plays: the toggle alone shows, and turning the music on again shows it again.
    expect(t.on).toBe(true);
    expect(run(on, off, on).open).toBe(true);
  });

  it("goes with the music, and nothing shows while it is off", () => {
    const s = run(on, off);
    expect(s.open).toBe(false);
    expect(s.closeIn).toBeNull();
    expect(run({ type: "enter" }).open).toBe(false);
    expect(run(keyIn).open).toBe(false);
    expect(run({ type: "show" }).open).toBe(false);
    expect(run({ type: "drag", down: true }).drag).toBe(false);
  });

  it("stays while a mouse is over the toggle or the slider, and goes a moment after it leaves", () => {
    const s = run(on, { type: "enter" });
    expect(s.open).toBe(true);
    expect(s.closeIn).toBeNull();
    // An old timer firing while hovered does nothing.
    expect(revealReducer(s, { type: "timeout", timer: s.timer }).open).toBe(true);
    const left = revealReducer(s, { type: "leave" });
    expect(left.open).toBe(true);
    expect(left.closeIn).toBe(REVEAL_LEAVE_MS);
    expect(REVEAL_LEAVE_MS).toBeGreaterThanOrEqual(500);
    expect(REVEAL_LEAVE_MS).toBeLessThanOrEqual(1000);
    expect(fire(left).open).toBe(false);
    // Crossing the gap between the toggle and the slider: back before the timer fires, it stays.
    const back = revealReducer(left, { type: "enter" });
    expect(back.closeIn).toBeNull();
    expect(revealReducer(back, { type: "timeout", timer: left.timer }).open).toBe(true);
  });

  it("opens under the mouse after it had closed by itself", () => {
    const s = fire(run(on));
    expect(s.open).toBe(false);
    expect(revealReducer(s, { type: "enter" }).open).toBe(true);
  });

  it("shows while the keyboard's focus is in, and goes a moment after it leaves", () => {
    const s = fire(run(on));
    const k = revealReducer(s, keyIn);
    expect(k.open).toBe(true);
    expect(k.focus).toBe(true);
    expect(k.closeIn).toBeNull();
    // Tab from the toggle on into the slider keeps it.
    const inside = revealReducer(k, { type: "focus", keyboard: true, entering: false });
    expect(inside.open).toBe(true);
    expect(inside.closeIn).toBeNull();
    // Muting with Enter and turning it on again keeps it out (the focus is still there).
    const again = [off, on].reduce(revealReducer, inside);
    expect(again.open).toBe(true);
    expect(again.closeIn).toBeNull();
    // Tab on past it.
    const out = revealReducer(again, { type: "blur" });
    expect(out.focus).toBe(false);
    expect(out.closeIn).toBe(REVEAL_LEAVE_MS);
    expect(fire(out).open).toBe(false);
  });

  it("does not count a click's focus as the keyboard's", () => {
    const s = run(on, { type: "focus", keyboard: false, entering: true });
    expect(s.focus).toBe(false);
    expect(revealHeld(s)).toBe(false);
    expect(fire(s).open).toBe(false);
    // Hidden, a click's focus does not open it.
    expect(revealReducer(fire(run(on)), { type: "focus", keyboard: false, entering: true }).open).toBe(false);
  });

  it("closes on Escape, and the focus handed back to the toggle does not open it again", () => {
    const s = run(on, keyIn, { type: "focus", keyboard: true, entering: false }, { type: "escape" });
    expect(s.open).toBe(false);
    const back = revealReducer(s, { type: "focus", keyboard: true, entering: false });
    expect(back.open).toBe(false);
    expect(back.closeIn).toBeNull();
    // Leaving and coming back with Tab opens it.
    expect([{ type: "blur" } as const, keyIn].reduce(revealReducer, back).open).toBe(true);
  });

  it("closes at once on a click or tap anywhere else, even under the mouse or the keyboard's focus", () => {
    expect(run(on, { type: "outside" }).open).toBe(false);
    expect(run(on, { type: "enter" }, { type: "outside" }).open).toBe(false);
    expect(run(on, keyIn, { type: "outside" }).open).toBe(false);
    expect(run(on, { type: "drag", down: true }, { type: "outside" }).drag).toBe(false);
  });

  it("goes after a few seconds with nothing done to it, and each touch or key starts the time again", () => {
    const s = run(on);
    const poked = revealReducer(s, { type: "poke" });
    expect(poked.closeIn).toBe(REVEAL_IDLE_MS);
    expect(poked.timer).toBeGreaterThan(s.timer);
    // The first timer no longer counts; the new one does.
    expect(revealReducer(poked, { type: "timeout", timer: s.timer }).open).toBe(true);
    expect(fire(poked).open).toBe(false);
    // Nothing to start while it is hidden.
    expect(revealReducer(fire(s), { type: "poke" }).closeIn).toBeNull();
  });

  it("never goes by time while it is being dragged, and waits again after the drag", () => {
    const s = run(on, { type: "drag", down: true });
    expect(s.drag).toBe(true);
    expect(s.closeIn).toBeNull();
    expect(revealReducer(s, { type: "timeout", timer: s.timer }).open).toBe(true);
    const up = revealReducer(s, { type: "drag", down: false });
    expect(up.drag).toBe(false);
    expect(up.closeIn).toBe(REVEAL_IDLE_MS);
    expect(fire(up).open).toBe(false);
    // A mouse that drags on past the slider: its leaving does not close it mid-drag.
    const mouse = run(on, { type: "enter" }, { type: "drag", down: true }, { type: "leave" });
    expect(mouse.closeIn).toBeNull();
    expect(fire(mouse).open).toBe(true);
    expect(revealReducer(mouse, { type: "drag", down: false }).closeIn).toBe(REVEAL_IDLE_MS);
  });

  it("shows on a tap, then waits; ignores a timer it no longer runs", () => {
    const hidden = fire(run(on));
    const s = revealReducer(hidden, { type: "show" });
    expect(s.open).toBe(true);
    expect(s.closeIn).toBe(REVEAL_IDLE_MS);
    expect(fire(s).open).toBe(false);
    expect(revealReducer(s, { type: "timeout", timer: s.timer + 1 }).open).toBe(true);
  });

  it("returns the same state when nothing changes", () => {
    const s = fire(run(on));
    expect(revealReducer(s, on)).toBe(s);
    expect(revealReducer(s, { type: "leave" })).toBe(s);
    expect(revealReducer(s, { type: "blur" })).toBe(s);
    expect(revealReducer(s, { type: "escape" })).toBe(s);
    expect(revealReducer(s, { type: "timeout", timer: s.timer })).toBe(s);
  });
});

describe("tapShows", () => {
  const playing = fire(run(on));
  const showing = run(on);

  it("shows the hidden slider on a tap while the music plays, instead of muting", () => {
    expect(tapShows(playing, "touch")).toBe(true);
    expect(tapShows(playing, "pen")).toBe(true);
  });

  it("mutes on a tap while it shows, and always on a click or a key", () => {
    expect(tapShows(showing, "touch")).toBe(false);
    expect(tapShows(playing, "mouse")).toBe(false);
    expect(tapShows(playing, null)).toBe(false);
  });

  it("turns the music on with a tap while it is off", () => {
    expect(tapShows(REVEAL_START, "touch")).toBe(false);
    expect(tapShows(run(on, off), "touch")).toBe(false);
  });
});
