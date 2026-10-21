import { describe, expect, it } from "vitest";
import {
  AUTO_FRAME_BUDGET_MS,
  CHOICE_FRAME_BUDGET_MS,
  FrameLadder,
  LADDER,
  ladderStep,
  slowFrameMs,
  typicalFrameMs,
  type LadderView,
} from "./runtime";

const view = (o: Partial<LadderView>): LadderView => ({
  deltas: [],
  gpu: [],
  cadenceMs: 1000 / 60,
  capMs: 0,
  budgetMs: AUTO_FRAME_BUDGET_MS,
  motionMs: 0,
  probing: false,
  climbScale: null,
  ...o,
});
const frames = (ms: number, n = 60) => Array<number>(n).fill(ms);

/** A ladder that has seen `cadence` ms quiet frames, then `n` moving frames of `ms`. */
function fed(cadence: number, ms: number, n = 60, now = 10_000): FrameLadder {
  const l = new FrameLadder(0);
  for (let i = 0; i < 16; i++) l.quietTick(cadence);
  for (let i = 0; i < n; i++) l.frame(now, ms);
  return l;
}

describe("the screen's frame interval", () => {
  it("is learned from quiet display frames, unknown until 8 are in", () => {
    const l = new FrameLadder(0);
    for (let i = 0; i < 7; i++) l.quietTick(16.7);
    expect(l.cadenceMs()).toBeNull();
    l.quietTick(16.7);
    expect(l.cadenceMs()).toBeCloseTo(16.7, 6);
  });

  it("is not stretched by a busy main thread (late frames only ever come later)", () => {
    const l = new FrameLadder(0);
    for (let i = 0; i < 32; i++) l.quietTick(i % 3 === 0 ? 50 : i % 3 === 1 ? 33.4 : 16.7);
    expect(l.cadenceMs()).toBeCloseTo(16.7, 6);
  });

  it("reads 33 ms on a 30 Hz screen (Low Power Mode) and follows a change", () => {
    const l = new FrameLadder(0);
    for (let i = 0; i < 32; i++) l.quietTick(16.7);
    for (let i = 0; i < 32; i++) l.quietTick(33.3);
    expect(l.cadenceMs()).toBeCloseTo(33.3, 6);
  });

  it("ignores intervals that are no frame (a hidden tab, a stall)", () => {
    const l = new FrameLadder(0);
    for (let i = 0; i < 10; i++) l.quietTick(0);
    for (let i = 0; i < 10; i++) l.quietTick(500);
    expect(l.cadenceMs()).toBeNull();
  });
});

describe("ladderStep: down", () => {
  it("a 30 Hz screen is not a slow GPU: 33 ms frames are its normal", () => {
    expect(slowFrameMs(AUTO_FRAME_BUDGET_MS, 1000 / 30)).toBeCloseTo(38.33, 1);
    expect(ladderStep(view({ deltas: frames(33.3), cadenceMs: 33.3 }))).toBeNull();
    // Unknown, it would have been (the old ladder's 13-15 fps on iPhones in Low Power Mode).
    expect(ladderStep(view({ deltas: frames(33.3), cadenceMs: null }))).toBe("down");
    // A 30 Hz screen whose GPU cannot keep 30 still steps down.
    expect(ladderStep(view({ deltas: frames(50), cadenceMs: 33.3 }))).toBe("down");
  });

  it("steps down at 60 Hz when the median frame is over 20 ms, and not before 45 frames", () => {
    expect(ladderStep(view({ deltas: frames(16.7) }))).toBeNull();
    expect(ladderStep(view({ deltas: frames(25) }))).toBe("down");
    expect(ladderStep(view({ deltas: frames(25, 44) }))).toBeNull();
  });

  it("a hand-picked tier holds down to 25 fps", () => {
    expect(ladderStep(view({ deltas: frames(33.3), budgetMs: CHOICE_FRAME_BUDGET_MS }))).toBeNull();
    expect(ladderStep(view({ deltas: frames(45), budgetMs: CHOICE_FRAME_BUDGET_MS }))).toBe("down");
    // 23 fps that arrive in bursts (10 ms, 76 ms, ...) are still 23 fps.
    const bursts = Array.from({ length: 60 }, (_, i) => (i % 2 ? 76 : 10));
    expect(ladderStep(view({ deltas: bursts, budgetMs: CHOICE_FRAME_BUDGET_MS }))).toBe("down");
  });

  it("does not drop pixels when the GPU timer shows the GPU idle half the frame (a busy main thread)", () => {
    expect(ladderStep(view({ deltas: frames(30), gpu: frames(6) }))).toBeNull();
    expect(ladderStep(view({ deltas: frames(30), gpu: frames(24) }))).toBe("down");
    // A timer that answers zeros is no timer.
    expect(ladderStep(view({ deltas: frames(30), gpu: frames(0) }))).toBe("down");
  });

  it("judges the frames' mean, not their median: a GPU-bound page gets its frames unevenly", () => {
    // Measured under a GPU load at 60 Hz: 42 frames a second whose median was under 20 ms.
    const uneven = [57.5, 16.4, 20.6, 12.8, 17, 20.4, 12.7, 34.1, 23.7, 8.8, 41.6, 8.7, 18, 53.1, 12.2, 38, 11.9, 16.6, 45.2, 4.9, 46.6, 37.1, 31.9, 23.6];
    const deltas = [...uneven, ...uneven, ...uneven];
    expect(typicalFrameMs(deltas)).toBeGreaterThan(24);
    expect(ladderStep(view({ deltas }))).toBe("down");
    // A stall or two in a window of smooth frames is no slow GPU.
    expect(ladderStep(view({ deltas: [...frames(16.7, 30), 240, ...frames(16.7, 29)] }))).toBeNull();
    expect(ladderStep(view({ deltas: [...frames(16.7, 20), 250, ...frames(16.7, 39), 180] }))).toBeNull();
    // A GPU so slow that every frame is a stall still steps down.
    expect(ladderStep(view({ deltas: frames(250) }))).toBe("down");
  });

  it("right after a climb, dropped frames undo it even when the mean holds", () => {
    const deltas = [...frames(14, 42), ...frames(26, 18)];
    expect(typicalFrameMs(deltas)).toBeLessThan(20);
    expect(ladderStep(view({ deltas }))).toBeNull();
    expect(ladderStep(view({ deltas, probing: true }))).toBe("down");
  });

  it("at the render-rate cap, frames at the cap's interval are fine", () => {
    expect(ladderStep(view({ deltas: frames(33.3), capMs: 1000 / 30 }))).toBeNull();
  });
});

describe("ladderStep: up", () => {
  const climb = { motionMs: 4000, climbScale: (1.25 / 1) ** 2 };

  it("climbs when the GPU timer says the next level fits in 90% of a 60 Hz frame", () => {
    expect(ladderStep(view({ deltas: frames(16.7), gpu: frames(8), ...climb }))).toBe("up");
    expect(ladderStep(view({ deltas: frames(16.7), gpu: frames(10), ...climb }))).toBeNull();
    // Not before 3 s of motion, and never without a step to take.
    expect(ladderStep(view({ deltas: frames(16.7), gpu: frames(8), ...climb, motionMs: 2000 }))).toBeNull();
    expect(ladderStep(view({ deltas: frames(16.7), gpu: frames(8), motionMs: 4000 }))).toBeNull();
  });

  it("on a fast screen without a timer, the frame intervals themselves show the room", () => {
    expect(ladderStep(view({ deltas: frames(8.3), cadenceMs: 8.3, ...climb }))).toBe("up");
    expect(ladderStep(view({ deltas: frames(11), cadenceMs: 8.3, ...climb }))).toBeNull();
  });

  it("at 60 Hz without a timer, only steady frames try a climb", () => {
    expect(ladderStep(view({ deltas: frames(16.7), ...climb }))).toBe("up");
    const someDrops = [...frames(16.7, 54), ...frames(33.3, 6)];
    expect(ladderStep(view({ deltas: someDrops, ...climb }))).toBeNull();
    expect(ladderStep(view({ deltas: frames(16.7), cadenceMs: null, ...climb }))).toBeNull();
  });

  it("lifts the render-rate cap when frames fit the screen's own interval, not the cap's", () => {
    const capped = { capMs: 1000 / 30, motionMs: 4000, climbScale: 1 };
    expect(ladderStep(view({ deltas: frames(33.3), gpu: frames(12), ...capped }))).toBe("up");
    expect(ladderStep(view({ deltas: frames(33.3), gpu: frames(25), ...capped }))).toBeNull();
    // No timer: steady capped frames try it, and a failure is undone.
    expect(ladderStep(view({ deltas: frames(33.3), ...capped }))).toBe("up");
  });
});

describe("FrameLadder", () => {
  it("spaces steps 4 s apart and starts judging over after each", () => {
    const l = fed(16.7, 25, 60, 5000);
    expect(l.decide(3000, AUTO_FRAME_BUDGET_MS, 0, null)).toBeNull();
    expect(l.decide(5000, AUTO_FRAME_BUDGET_MS, 0, null)).toBe("down");
    l.stepped(5000, "down");
    expect(l.status(5000).frames).toBe(0);
    for (let i = 0; i < 60; i++) l.frame(6000, 25);
    expect(l.decide(6000, AUTO_FRAME_BUDGET_MS, 0, null)).toBeNull();
    expect(l.decide(9001, AUTO_FRAME_BUDGET_MS, 0, null)).toBe("down");
  });

  it("ignores frames while a set settles (uploads, first draws)", () => {
    const l = fed(16.7, 16.7, 0);
    l.settle(10_000);
    for (let i = 0; i < 60; i++) l.frame(11_000, 40);
    expect(l.status(11_000)).toMatchObject({ frames: 0, settling: true });
    expect(l.decide(11_000, AUTO_FRAME_BUDGET_MS, 0, null)).toBeNull();
    for (let i = 0; i < 60; i++) l.frame(12_001, 40);
    expect(l.decide(12_001, AUTO_FRAME_BUDGET_MS, 0, null)).toBe("down");
  });

  it("drops GPU times measured before a settle or a step", () => {
    const l = fed(16.7, 16.7, 0);
    const gen = l.generation;
    l.settle(0, 0);
    for (let i = 0; i < 40; i++) l.gpuTime(10, 5, gen);
    expect(l.status(10).gpuMs).toBeNull();
    for (let i = 0; i < 40; i++) l.gpuTime(10, 5, l.generation);
    expect(l.status(10).gpuMs).toBe(5);
  });

  it("backs off a climb that failed, longer each time", () => {
    const l = new FrameLadder(0);
    for (let i = 0; i < 16; i++) l.quietTick(16.7);
    const scale = 1.5625;
    let t = 10_000;
    const run = (ms: number) => {
      for (let i = 0; i < 240; i++) l.frame(t, ms);
    };
    run(16.7);
    expect(l.decide(t, AUTO_FRAME_BUDGET_MS, 0, scale)).toBe("up");
    l.stepped(t, "up");
    // The climb drops frames: undone at the next judgement.
    t += 4500;
    run(33.3);
    expect(l.status(t).probing).toBe(true);
    expect(l.decide(t, AUTO_FRAME_BUDGET_MS, 0, null)).toBe("down");
    l.stepped(t, "down");
    expect(l.status(t).blockedUntil).toBe(t + LADDER.backoffMs);
    // Room again, but blocked for 30 s.
    t += 10_000;
    run(16.7);
    expect(l.decide(t, AUTO_FRAME_BUDGET_MS, 0, scale)).toBeNull();
    t += LADDER.backoffMs;
    run(16.7);
    expect(l.decide(t, AUTO_FRAME_BUDGET_MS, 0, scale)).toBe("up");
    l.stepped(t, "up");
    t += 4500;
    run(33.3);
    expect(l.decide(t, AUTO_FRAME_BUDGET_MS, 0, null)).toBe("down");
    l.stepped(t, "down");
    expect(l.status(t).blockedUntil).toBe(t + 2 * LADDER.backoffMs);
  });

  it("a step down long after a climb is no failed climb", () => {
    const l = fed(16.7, 16.7, 240);
    expect(l.decide(10_000, AUTO_FRAME_BUDGET_MS, 0, 1.5625)).toBe("up");
    l.stepped(10_000, "up");
    const later = 10_000 + LADDER.probeMs + 1;
    // A flight's worth of steady frames since (the watch also counts moving time), then slow ones.
    for (let i = 0; i < Math.ceil(LADDER.probeMotionMs / 16.7); i++) l.frame(later, 16.7);
    for (let i = 0; i < 90; i++) l.frame(later, 30);
    expect(l.decide(later, AUTO_FRAME_BUDGET_MS, 0, null)).toBe("down");
    l.stepped(later, "down");
    expect(l.status(later).blockedUntil).toBe(0);
  });

  it("watches a climb taken at rest on the flight after it, however long the rest", () => {
    const l = fed(16.7, 16.7, 240);
    l.stepped(10_000, "up");
    // A long read at the stop: no moving frames, the 10 s pass.
    const back = 10_000 + LADDER.probeMs + 30_000;
    expect(l.status(back).probing).toBe(true);
    // The flight after it drops frames: the climb is undone and blocked.
    for (let i = 0; i < 60; i++) l.frame(back, 33.3);
    expect(l.decide(back, AUTO_FRAME_BUDGET_MS, 0, null)).toBe("down");
    l.stepped(back, "down");
    expect(l.status(back).blockedUntil).toBe(back + LADDER.backoffMs);
  });

  it("ends the watch once both the time and enough moving frames have passed", () => {
    const l = fed(16.7, 16.7, 240);
    l.stepped(10_000, "up");
    const later = 10_000 + LADDER.probeMs + 1;
    for (let i = 0; i < Math.ceil(LADDER.probeMotionMs / 16.7); i++) l.frame(later, 16.7);
    expect(l.status(later).probing).toBe(false);
  });

  it("skips frame intervals that are no frame (a hidden tab)", () => {
    const l = fed(16.7, 5000, 60);
    expect(l.status(10_000).frames).toBe(0);
  });
});
