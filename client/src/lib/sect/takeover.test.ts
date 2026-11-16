import { describe, expect, it } from "vitest";
import { SNAP } from "./snap";
import {
  createTouchTakeover,
  createWheelTail,
  endWheelTail,
  touchDown,
  touchScrolled,
  touchUp,
  WHEEL_TAIL,
  type WheelTailState,
  wheelSettling,
  wheelTail,
} from "./takeover";

/** A trackpad flick's momentum: `n` wheel events dying away from `from` px, never below 1. */
const decay = (from: number, n: number, k = 0.88) => Array.from({ length: n }, (_, i) => Math.max(1, Math.round(from * k ** i)));

/** Wheel events as [time ms, page pixels]. */
type Wheel = [ms: number, px: number];

/** Chrome merging `n` wheel events from index `i` that piled up in a long frame: pixels summed, the newest one's time. */
const merge = (evs: Wheel[], i: number, n: number): Wheel[] => [
  ...evs.slice(0, i),
  [evs[i + n - 1][0], evs.slice(i, i + n).reduce((sum, [, px]) => sum + px, 0)],
  ...evs.slice(i + n),
];

/** Each event's verdict, with a flight on from `flightMs`. */
const verdicts = (evs: Wheel[], flightMs: number) => {
  const s = createWheelTail();
  return evs.map(([ms, px]) => wheelTail(s, ms, px, ms >= flightMs));
};

/** The verdicts wanted when all the stream from the flight on is momentum: tail from `flightMs`. */
const tailFrom = (evs: Wheel[], flightMs: number) => evs.map(([ms]) => ms >= flightMs);

/** Wheel events every `stepMs` up to `untilMs` from where the page would be at each time: each one the pixels since the one before. */
const sample = (at: (ms: number) => number, stepMs: number, untilMs: number): Wheel[] => {
  const out: Wheel[] = [];
  for (let ms = stepMs; ms <= untilMs; ms += stepMs) out.push([ms, at(ms) - at(ms - stepMs)]);
  return out;
};

/** Momentum that has run a while at `px` a frame (every 16 ms), a flight on from its second event. */
const settled = (px: number, n = 12) => {
  const s = createWheelTail();
  for (let i = 0; i < n; i++) wheelTail(s, i * 16, px, i >= 1);
  return { s, nextMs: n * 16 };
};

/** Wheel events every 16 ms from `fromMs` with the flight on: their verdicts. */
const feed = (s: WheelTailState, fromMs: number, pxs: number[]) => pxs.map((px, i) => wheelTail(s, fromMs + i * 16, px, true));

describe("wheelTail", () => {
  it("keeps a stream's gap below the snap's rest, so a snap glide never begins inside one", () => {
    expect(WHEEL_TAIL.gapMs).toBeLessThan(SNAP.restMs);
  });

  it("takes the momentum after a flight began as tail, all of it", () => {
    // A flick (60 px dying away, every 16 ms); J pressed before the 7th event.
    const s = createWheelTail();
    const px = decay(60, 35);
    expect(px[0]).toBe(60);
    expect(px.at(-1)).toBe(1);
    const got = px.map((p, i) => wheelTail(s, i * 16, p, i >= 6));
    expect(got.slice(0, 6)).toEqual(Array(6).fill(false));
    expect(got.slice(6)).toEqual(Array(px.length - 6).fill(true));
  });

  it("outlives the flight until the stream ends, so the last of it does not nudge the camera off the stop", () => {
    const s = createWheelTail();
    const px = decay(50, 40);
    // The flight runs from the 4th event to the 15th; the momentum goes on after it has landed.
    const got = px.map((p, i) => wheelTail(s, i * 16, p, i >= 3 && i < 15));
    expect(got.slice(3)).toEqual(Array(px.length - 3).fill(true));
  });

  it("is never tail without a flight", () => {
    const s = createWheelTail();
    for (const [i, p] of decay(80, 40).entries()) expect(wheelTail(s, i * 16, p, false)).toBe(false);
    for (let i = 0; i < 10; i++) expect(wheelTail(s, 1000 + i * 50, 100, false)).toBe(false);
  });

  it("does not count the first wheel event as tail when the flight began with no stream running", () => {
    const s = createWheelTail();
    expect(wheelTail(s, 0, 30, true)).toBe(false);
    // The visitor took over (the page ended the flight); the rest of the stream is theirs.
    expect(wheelTail(s, 16, 28, false)).toBe(false);
    // Under a reader the page leaves the flight on: still not tail, the flight was on before too.
    const t = createWheelTail();
    wheelTail(t, 0, 30, true);
    expect(wheelTail(t, 16, 28, true)).toBe(false);
  });

  it("ends at a gap of gapMs: the next wheel event is the visitor's again", () => {
    const s = createWheelTail();
    wheelTail(s, 0, 40, false);
    expect(wheelTail(s, 16, 36, true)).toBe(true);
    // Slow momentum near its end still counts.
    expect(wheelTail(s, 16 + WHEEL_TAIL.gapMs - 1, 30, true)).toBe(true);
    const t = 16 + WHEEL_TAIL.gapMs - 1 + WHEEL_TAIL.gapMs;
    expect(wheelTail(s, t, 30, true)).toBe(false);
    expect(wheelTail(s, t + 16, 30, true)).toBe(false);
  });

  it("ends at a turn the other way", () => {
    const s = createWheelTail();
    wheelTail(s, 0, 40, false);
    expect(wheelTail(s, 16, 35, true)).toBe(true);
    expect(wheelTail(s, 32, 30, true)).toBe(true);
    expect(wheelTail(s, 48, -4, true)).toBe(false);
    // Upward momentum turned downward too.
    const u = createWheelTail();
    wheelTail(u, 0, -40, false);
    expect(wheelTail(u, 16, -35, true)).toBe(true);
    expect(wheelTail(u, 32, 6, true)).toBe(false);
  });

  // The smallest push that ends the tail within 48 ms (three 16 ms frames), measured on smooth motion
  // sampled every 16 ms or every 8 ms (the same at both): about 3 times the momentum's pixels per
  // event on steady momentum, 3.25 times on a flick fading 3% a frame, 3.75 times at 6% and 5 times
  // at 12%. Fast-fading momentum needs the bigger push because the smoothed speed lags it. A push of
  // double the momentum or less never ends the tail (WHEEL_TAIL.rise); one in between ends it later.
  it("ends at a new push: 100 px a frame at once, 40 px within four frames, and inside a long frame too", () => {
    // Momentum that has run a while at 10 px a frame, then the fingers push again.
    const a = settled(10);
    expect(a.s.tail).toBe(true);
    expect(feed(a.s, a.nextMs, [100])).toEqual([false]);
    const b = settled(10);
    expect(feed(b.s, b.nextMs, [40, 40, 40, 40]).at(-1)).toBe(false);
    // The same 40 px push during a 48 ms frame: three frames of it come as one event of 120 px.
    const c = settled(10);
    expect(wheelTail(c.s, c.nextMs - 16 + 48, 120, true)).toBe(false);
  });

  it("does not end at a push below double the speed, or at a few pixels of jitter", () => {
    // 15 px a frame after momentum at 10 is under `rise` times it: still momentum, by the rule.
    const a = settled(10);
    expect(feed(a.s, a.nextMs, Array(20).fill(15))).toEqual(Array(20).fill(true));
    // Momentum at 10 px a frame, give or take 3.
    const b = settled(10);
    const jitter = [13, 7, 12, 8, 13, 7, 10, 13, 7, 9, 11, 13];
    expect(feed(b.s, b.nextMs, jitter)).toEqual(Array(jitter.length).fill(true));
  });

  it("at the very end of the momentum, takes 1 to 3 px of jitter as tail and 20 px a frame as a push", () => {
    const s = createWheelTail();
    wheelTail(s, 0, 5, false);
    expect(wheelTail(s, 16, 1, true)).toBe(true);
    const jitter = [2, 3, 1, 3, 2, 2, 3, 1, 3, 2];
    expect(feed(s, 32, jitter)).toEqual(Array(jitter.length).fill(true));
    expect(feed(s, 32 + jitter.length * 16, [20, 20, 20]).at(-1)).toBe(false);
  });

  it("lets a sideways (zero) event keep the stream going without ending the tail", () => {
    const s = createWheelTail();
    wheelTail(s, 0, 30, false);
    expect(wheelTail(s, 16, 28, true)).toBe(true);
    expect(wheelTail(s, 32, 0, true)).toBe(true);
    expect(wheelTail(s, 48, 27, true)).toBe(true);
    // A flight that began at a zero event: the tail measures from the speed before it.
    const t = createWheelTail();
    wheelTail(t, 0, 30, false);
    expect(wheelTail(t, 16, 0, true)).toBe(true);
    expect(wheelTail(t, 32, 28, true)).toBe(true);
    expect(wheelTail(t, 48, 27, true)).toBe(true);
    // A real push after one still ends it: momentum at 10 px a frame for a while, the flight begins
    // at a zero event, then the fingers push 100 px a frame.
    const u = createWheelTail();
    for (let i = 0; i < 8; i++) wheelTail(u, i * 16, 10, false);
    expect(wheelTail(u, 120, 0, true)).toBe(true);
    expect(wheelTail(u, 128, 10, true)).toBe(true);
    expect(wheelTail(u, 144, 10, true)).toBe(true);
    expect(wheelTail(u, 160, 100, true)).toBe(false);
  });

  it("does not take the momentum event just after a sideways one for a push", () => {
    // A zero event 8 ms, then 1 ms, before the next momentum event. Timed from the zero event, that
    // event used to read as twice the speed or more.
    const a: Wheel[] = [[0, 14], [16, 12], [32, 10], [48, 9], [56, 0], [64, 9]];
    expect(verdicts(a, 16)).toEqual(tailFrom(a, 16));
    const b: Wheel[] = [[0, 12], [16, 11], [32, 10], [48, 10], [63, 0], [64, 10]];
    expect(verdicts(b, 16)).toEqual(tailFrom(b, 16));
    // A zero event 1 ms or 8 ms before a steady or slightly rising momentum event.
    for (const beforeMs of [1, 8]) {
      for (const px of [10, 11, 12]) {
        const evs: Wheel[] = [...Array.from({ length: 6 }, (_, i): Wheel => [i * 16, 10]), [96 - beforeMs, 0], [96, px], [112, px]];
        expect(verdicts(evs, 16)).toEqual(tailFrom(evs, 16));
      }
    }
  });

  it("does not take uneven gaps between events for a push", () => {
    // A fast mouse wheel, 100 px a notch, its events rounded to an 8 ms poll; a flight from the third.
    const mouse: Wheel[] = [0, 16, 24, 40, 48, 64, 72, 88].map((ms): Wheel => [ms, 100]);
    expect(verdicts(mouse, 24)).toEqual(tailFrom(mouse, 24));
    // Equal events with gaps of 8 and 16 ms by turns, starting with either; a flight from the fourth.
    for (const firstGap of [8, 16]) {
      const evs: Wheel[] = [];
      for (let i = 0, ms = 0; i < 20; i++) {
        evs.push([ms, 30]);
        ms += i % 2 === 0 ? firstGap : 24 - firstGap;
      }
      expect(verdicts(evs, evs[3][0])).toEqual(tailFrom(evs, evs[3][0]));
    }
    // Momentum every 16 ms with one event stamped 6 ms late (at 70 ms, not 64).
    const late: Wheel[] = [[0, 16], [16, 16], [32, 15], [48, 15], [70, 14], [80, 14], [96, 13], [112, 13]];
    expect(verdicts(late, 32)).toEqual(tailFrom(late, 32));
  });

  it("treats a fast mouse wheel's notches after the flight began as tail until it pauses", () => {
    // 100 px notches 50 ms apart; a click on the rail starts a flight after the third.
    const s = createWheelTail();
    const got = [0, 1, 2, 3, 4, 5].map((i) => wheelTail(s, i * 50, 100, i >= 3));
    expect(got).toEqual([false, false, false, true, true, true]);
    // A pause, then a notch: the visitor's.
    expect(wheelTail(s, 250 + WHEEL_TAIL.gapMs, 100, true)).toBe(false);
  });

  it("keeps momentum as tail when a long frame merges three of its events into one", () => {
    // Momentum at about 10 px a frame; a 50 ms frame then hands over the next three (about 9 px
    // each) as one event of 27 px, stamped with the last one's time. By pixels it was a push.
    const s = createWheelTail();
    wheelTail(s, 0, 12, false);
    expect(wheelTail(s, 16, 11, true)).toBe(true);
    expect(wheelTail(s, 32, 10, true)).toBe(true);
    expect(wheelTail(s, 80, 27, true)).toBe(true);
    expect(wheelTail(s, 96, 8, true)).toBe(true);
  });

  it.each([2, 3, 5, 7])("keeps momentum as tail when %i of its events are merged, wherever that lands", (n) => {
    // Seven merged events span 112 ms: still one stream.
    expect(n * 16).toBeLessThan(WHEEL_TAIL.gapMs);
    // Every 16 ms: a flick (60 px dying away fast or slowly), or steady momentum. A flight begins at
    // the 7th event, or at the 2nd (where the speed is set from the real spacing).
    const streams: [string, number[]][] = [
      ["fading 12%", decay(60, 40, 0.88)],
      ["fading 3%", decay(60, 40, 0.97)],
      ...[5, 10, 20, 40, 100].map((px): [string, number[]] => [`steady ${px} px`, Array(30).fill(px)]),
    ];
    const wrong: string[] = [];
    for (const [name, pxs] of streams) {
      const evs = pxs.map((px, i): Wheel => [i * 16, px]);
      for (const flightMs of [16, 6 * 16]) {
        for (let i = 1; i + n <= evs.length; i++) {
          const merged = merge(evs, i, n);
          if (verdicts(merged, flightMs).some((tail, j) => tail !== tailFrom(merged, flightMs)[j])) {
            wrong.push(`${name}, flight at ${flightMs} ms, merged at ${i}`);
          }
        }
      }
    }
    expect(wrong).toEqual([]);
  });

  it("reads the same motion alike at 60 Hz and 120 Hz from the second event on", () => {
    // The first event's speed is a guess; the second sets it from the real spacing.
    const tau = -16 / Math.log(0.88);
    const motions: [string, (ms: number) => number][] = [
      ["steady", (ms) => 0.625 * ms],
      ["a flick fading 12% a frame", (ms) => 3 * tau * (1 - Math.exp(-ms / tau))],
    ];
    for (const [name, at] of motions) {
      const speeds = (stepMs: number) => {
        const s = createWheelTail();
        const out = new Map<number, number>();
        for (let ms = stepMs; ms <= 400; ms += stepMs) {
          wheelTail(s, ms, at(ms) - at(ms - stepMs), false);
          out.set(ms, s.rate);
        }
        return out;
      };
      const at16 = speeds(16);
      const at8 = speeds(8);
      // From 32 ms, the 60 Hz stream's second event.
      const off = [...at16].filter(([ms]) => ms >= 32).filter(([ms, rate]) => Math.abs(rate / at8.get(ms)! - 1) > 0.15);
      expect(off, name).toEqual([]);
    }
  });

  it("does not take the speed set from the real spacing at the second event for a push", () => {
    // A small first event, a flight begun at a sideways event, then the stream's second event five
    // times the size: against the first event's guess that is a rise, but it is the first real speed.
    const s = createWheelTail();
    wheelTail(s, 0, 4, false);
    expect(wheelTail(s, 8, 0, true)).toBe(true);
    expect(wheelTail(s, 16, 20, true)).toBe(true);
    // The stream did grow five times since the flight began, so the next event at that speed is a push.
    expect(wheelTail(s, 32, 20, true)).toBe(false);
  });

  it("adds an event stamped with the same time as the one before to the speed, not as a burst", () => {
    const s = createWheelTail();
    wheelTail(s, 0, 12, false);
    expect(wheelTail(s, 16, 10, true)).toBe(true);
    // 3 px with the same time stamp only adds 3 px to the speed.
    expect(wheelTail(s, 16, 3, true)).toBe(true);
    expect(wheelTail(s, 32, 9, true)).toBe(true);
  });

  it("still hands a merged event after a frame of gapMs or longer to the visitor (a known limit)", () => {
    const s = createWheelTail();
    wheelTail(s, 0, 12, false);
    expect(wheelTail(s, 16, 11, true)).toBe(true);
    // A 128 ms frame: the eight events in it come as one, which looks like a new stream after a pause.
    expect(wheelTail(s, 16 + WHEEL_TAIL.gapMs + 8, 60, true)).toBe(false);
  });

  describe("gives the same verdicts at 8 ms spacing (a 120 Hz trackpad) as at 16 ms, for the same motion", () => {
    // A flick at 3 px a ms dying away (88% a 16 ms frame); a flight begins at 96 ms; the motion
    // changes at 192 ms. Each event is the pixels since the one before, so at 8 ms they are half.
    // The smoothed speed lags a flick that dies away this fast, so a push here must be about 5 times
    // the momentum's speed to end the tail soon.
    const tau = -16 / Math.log(0.88);
    const flick = (ms: number) => 3 * tau * (1 - Math.exp(-ms / tau));
    const speed = (ms: number) => 3 * Math.exp(-ms / tau);
    const S = 192;
    const flightMs = 96;
    const untilMs = 800;
    /** Speed from the momentum's to `n` times it over 32 ms, then held: pixels `d` ms after S. */
    const ramp = (n: number, d: number) => speed(S) * (d <= 32 ? d + ((n - 1) * d * d) / 64 : 32 + (n - 1) * 16 + n * (d - 32));
    const run = (at: (ms: number) => number, stepMs: number) => {
      const evs = sample(at, stepMs, untilMs);
      const got = verdicts(evs, flightMs);
      return new Map(evs.map(([ms], i): [number, boolean] => [ms, got[i]]));
    };
    // [motion, where the page is at each time, the last time that is still tail at 16 ms]
    const cases: [string, (ms: number) => number, number][] = [
      ["momentum alone", flick, untilMs],
      ["a new push at five times the speed", (ms) => (ms <= S ? flick(ms) : flick(S) + 5 * speed(S) * (ms - S)), S + 32],
      ["a new push at ten times the speed", (ms) => (ms <= S ? flick(ms) : flick(S) + 10 * speed(S) * (ms - S)), S],
      ["a push that builds to six times the speed over two frames", (ms) => (ms <= S ? flick(ms) : flick(S) + ramp(6, ms - S)), S + 48],
      ["a bump of 40% for three frames", (ms) => flick(ms) + 0.4 * (flick(Math.min(Math.max(ms, S), S + 48)) - flick(S)), untilMs],
      ["a turn the other way", (ms) => (ms <= S ? flick(ms) : flick(S) - 0.3 * (flick(ms) - flick(S))), S],
    ];
    it.each(cases)("%s", (_, at, lastTailMs) => {
      const at16 = run(at, 16);
      const at8 = run(at, 8);
      expect([...at16.values()]).toEqual([...at16.keys()].map((ms) => ms >= flightMs && ms <= lastTailMs));
      expect([...at16.keys()].map((ms) => at8.get(ms))).toEqual([...at16.values()]);
    });
  });
});

describe("endWheelTail", () => {
  it("gives the rest of the momentum to the visitor after Space or a finger down, until a flight begins inside it again", () => {
    // A flick (60 px dying away, every 16 ms): J before the 7th event, Space before the 13th (it
    // ends the flight), a click on the rail before the 25th.
    const s = createWheelTail();
    const px = decay(60, 40);
    const got = px.map((p, i) => {
      if (i === 12) endWheelTail(s, false);
      return wheelTail(s, i * 16, p, (i >= 6 && i < 12) || i >= 24);
    });
    expect(got.slice(0, 6)).toEqual(Array(6).fill(false));
    expect(got.slice(6, 12)).toEqual(Array(6).fill(true));
    // Theirs, so the page no longer puts the scroll back under them.
    expect(got.slice(12, 24)).toEqual(Array(12).fill(false));
    expect(got.slice(24)).toEqual(Array(px.length - 24).fill(true));
  });

  it("counts a flight begun after the input, before the next wheel event, as begun inside the stream", () => {
    // A finger down ends the flight, and its tap starts it again before the next wheel event.
    const s = createWheelTail();
    wheelTail(s, 0, 40, false);
    expect(wheelTail(s, 16, 36, true)).toBe(true);
    endWheelTail(s, false);
    expect(wheelTail(s, 32, 32, true)).toBe(true);
  });

  it("does not take a far jump still gathering after a finger down for a flight begun since", () => {
    const s = createWheelTail();
    wheelTail(s, 0, 40, false);
    expect(wheelTail(s, 16, 36, true)).toBe(true);
    endWheelTail(s, true);
    expect(wheelTail(s, 32, 32, true)).toBe(false);
    expect(wheelTail(s, 48, 28, true)).toBe(false);
  });
});

describe("wheelSettling", () => {
  it("covers the longest a browser eases one wheel turn in over", () => {
    // Chrome up to 200 ms, Edge up to 500 ms.
    expect(WHEEL_TAIL.settleMs).toBeGreaterThan(500);
  });

  it("is never on before the first wheel event, or with no flight and no tail", () => {
    const s = createWheelTail();
    expect(wheelSettling(s, 0, true)).toBe(false);
    wheelTail(s, 0, 100, false);
    // The visitor's own wheel turn easing in, nothing flying: theirs.
    expect(wheelSettling(s, 16, false)).toBe(false);
    expect(wheelSettling(s, 150, false)).toBe(false);
  });

  it("takes the scroll still easing in from a wheel turn just before the flight began as leftover", () => {
    // One notch of a mouse wheel at 0; J at 60 ms, while Chrome is a third of the way through it.
    const s = createWheelTail();
    wheelTail(s, 0, 100, false);
    expect(wheelSettling(s, 62, true)).toBe(true);
    expect(wheelSettling(s, 190, true)).toBe(true);
    expect(wheelSettling(s, WHEEL_TAIL.settleMs - 1, true)).toBe(true);
    // Long after any easing: a scroll then is new input (the scrollbar, say).
    expect(wheelSettling(s, WHEEL_TAIL.settleMs, true)).toBe(false);
  });

  it("covers the gap between the flight beginning inside a stream and the stream's next event", () => {
    const s = createWheelTail();
    const px = decay(40, 30);
    for (let i = 0; i < 6; i++) wheelTail(s, i * 45, px[i], false);
    // J at 240 ms: the next event (270 ms) has not come, so nothing is tail yet.
    expect(s.tail).toBe(false);
    expect(wheelSettling(s, 242, true)).toBe(true);
    // From the next event on the stream is tail, and its scroll is put back as the tail's.
    expect(wheelTail(s, 270, px[6], true)).toBe(true);
    expect(wheelSettling(s, 275, true)).toBe(true);
  });

  it("puts the tail's own scroll back after the flight has landed too, until it has had time to ease in", () => {
    const s = createWheelTail();
    wheelTail(s, 0, 40, false);
    expect(wheelTail(s, 16, 36, true)).toBe(true);
    expect(wheelTail(s, 32, 32, false)).toBe(true);
    expect(wheelSettling(s, 40, false)).toBe(true);
    expect(wheelSettling(s, 32 + WHEEL_TAIL.settleMs - 1, false)).toBe(true);
    expect(wheelSettling(s, 32 + WHEEL_TAIL.settleMs, false)).toBe(false);
  });

  it("leaves the scroll of a wheel turn that took over to the visitor", () => {
    // A flight on, no stream running: the wheel turn is the visitor's and the page ends the flight.
    const s = createWheelTail();
    expect(wheelTail(s, 0, 100, true)).toBe(false);
    endWheelTail(s, false);
    expect(wheelSettling(s, 16, false)).toBe(false);
    // Under a reader the page leaves the flight on: still the visitor's turn, not leftover.
    const t = createWheelTail();
    expect(wheelTail(t, 0, 100, true)).toBe(false);
    expect(wheelSettling(t, 16, true)).toBe(false);
  });

  it("ends with the tail at Space or a finger down, and comes back with a flight begun after it", () => {
    const s = createWheelTail();
    wheelTail(s, 0, 40, false);
    expect(wheelTail(s, 16, 36, true)).toBe(true);
    // Space: it ends the flight, and its own scroll is the visitor's.
    endWheelTail(s, false);
    expect(wheelSettling(s, 20, false)).toBe(false);
    // A click on the rail right after starts a flight: what the browser is still easing in is leftover again.
    expect(wheelSettling(s, 40, true)).toBe(true);
    // A finger down with a far jump still gathering: no flight begun since, so the drag is the visitor's.
    const t = createWheelTail();
    wheelTail(t, 0, 40, false);
    expect(wheelTail(t, 16, 36, true)).toBe(true);
    endWheelTail(t, true);
    expect(wheelSettling(t, 20, true)).toBe(false);
  });

  it("is timed from when the page handled the event, not from the event's own time", () => {
    // An event stamped at 0 that a long frame held back until 400 ms: its scroll comes after that.
    const s = createWheelTail();
    wheelTail(s, 0, 100, false, 400);
    expect(wheelSettling(s, 700, true)).toBe(true);
    expect(wheelSettling(s, 400 + WHEEL_TAIL.settleMs, true)).toBe(false);
  });
});

describe("touch takeover", () => {
  const flight = (toU: number, moves: number, onArrive?: () => void) => ({ toU, moves, ...(onArrive ? { onArrive } : {}) });

  it("lets a tap carry on with the flight it ended, with what was to run on arrival", () => {
    const s = createTouchTakeover();
    const onArrive = () => {};
    touchDown(s, 1, flight(320, 7, onArrive));
    const back = touchUp(s, 0, { busy: false, moves: 7 });
    expect(back).toEqual({ toU: 320, moves: 7, onArrive });
    expect(back?.onArrive).toBe(onArrive);
    // Remembered once only.
    expect(touchUp(s, 0, { busy: false, moves: 7 })).toBeNull();
  });

  it("leaves the camera with the visitor once the page scrolled under the finger", () => {
    const s = createTouchTakeover();
    touchDown(s, 1, flight(320, 7));
    expect(touchScrolled(s)).toBe(true);
    // Only the first scroll of a touch counts as the first.
    expect(touchScrolled(s)).toBe(false);
    expect(touchUp(s, 0, { busy: false, moves: 7 })).toBeNull();
    // After the finger lifts, a scroll (a flick's momentum) is not under a finger.
    expect(touchScrolled(s)).toBe(false);
  });

  it("does not carry on when something newer flies or gathers", () => {
    const s = createTouchTakeover();
    touchDown(s, 1, flight(320, 7));
    expect(touchUp(s, 0, { busy: true, moves: 7 })).toBeNull();
    touchDown(s, 1, flight(320, 7));
    expect(touchUp(s, 0, { busy: false, moves: 8 })).toBeNull();
  });

  it("has nothing to carry on when the touch ended no flight", () => {
    const s = createTouchTakeover();
    touchDown(s, 1, null);
    expect(touchUp(s, 0, { busy: false, moves: 0 })).toBeNull();
  });

  it("waits for the last finger, and remembers the flight the first one ended", () => {
    const s = createTouchTakeover();
    touchDown(s, 1, flight(500, 2));
    touchDown(s, 2, null);
    expect(touchUp(s, 1, { busy: false, moves: 2 })).toBeNull();
    expect(touchUp(s, 0, { busy: false, moves: 2 })).toEqual({ toU: 500, moves: 2 });
  });

  it("starts each touch afresh, even after a lost touchend", () => {
    const s = createTouchTakeover();
    touchDown(s, 1, flight(500, 2));
    touchScrolled(s);
    // Its touchend never came; the next touch begins with one finger.
    touchDown(s, 1, flight(640, 3));
    expect(touchUp(s, 0, { busy: false, moves: 3 })).toEqual({ toU: 640, moves: 3 });
  });
});
