import { describe, expect, it } from "vitest";
import {
  AUTO_FRAME_BUDGET_MS,
  CAPPED_FPS,
  CHOICE_FRAME_BUDGET_MS,
  climbCost,
  climbRebuildsPipeline,
  degradeQuality,
  effectiveDpr,
  FEATURE_CLIMB_COST,
  FrameLadder,
  LADDER,
  ladderCeiling,
  ladderStep,
  LIVE_LIGHT_TRIES,
  RENDER_SCALE_MIN,
  slowFrameMs,
  tierQuality,
  typicalFrameMs,
  upgradeQuality,
  type DegradeOptions,
  type LadderView,
  type Quality,
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

/** Every field the ladder can change. The optional flags read absent as false. */
const LADDER_FIELDS = ["maxDpr", "msaa", "bloom", "post", "lowTextures", "maxFps", "standIns", "noCards", "vegShells", "liveLight", "farFull"] as const;

const STEP_NAMES: Record<Exclude<(typeof LADDER_FIELDS)[number], "maxDpr">, string> = {
  msaa: "msaa",
  bloom: "bloom",
  post: "post",
  lowTextures: "textures",
  maxFps: "fps",
  standIns: "stand-ins",
  noCards: "no cards",
  vegShells: "shells",
  liveLight: "live",
  farFull: "far",
};

/** What one ladder step changed, by name. A step must change exactly one field. */
function stepName(a: Quality, b: Quality, dpr: number): string {
  const changed = LADDER_FIELDS.filter((k) => (a[k] ?? false) !== (b[k] ?? false));
  expect(changed, `one step changes one thing, not ${changed.join(", ")}`).toHaveLength(1);
  const k = changed[0];
  if (k === "maxDpr") return Math.min(effectiveDpr(a, dpr), effectiveDpr(b, dpr)) < 1 ? "scale" : "dpr";
  return STEP_NAMES[k];
}

interface Walk {
  steps: string[];
  /** Every quality on the way, the start included. */
  states: Quality[];
  end: Quality;
}

/** Steps down with degradeQuality until it returns null. */
function walkDown(start: Quality, dpr: number, opts?: DegradeOptions): Walk {
  const states = [start];
  const steps: string[] = [];
  let q = start;
  for (let i = 0; i < 30; i++) {
    const n = degradeQuality(q, dpr, opts);
    if (!n) return { steps, states, end: q };
    steps.push(stepName(q, n, dpr));
    states.push(n);
    q = n;
  }
  throw new Error("the ladder never reached its bottom");
}

/** Climbs with upgradeQuality toward `top` until it returns null. */
function walkUp(start: Quality, top: Quality, dpr: number): Walk {
  const states = [start];
  const steps: string[] = [];
  let q = start;
  for (let i = 0; i < 30; i++) {
    const n = upgradeQuality(q, top, dpr);
    if (!n) return { steps, states, end: q };
    steps.push(stepName(q, n, dpr));
    states.push(n);
    q = n;
  }
  throw new Error("the climb never reached its top");
}

describe("the quality ladder: live light and the crown shells", () => {
  it("a High the page picked loses resolution, then live light, then the shells, then the rest, in order", () => {
    // A 2x screen: High at 1.5x with 2x MSAA.
    const sharp = walkDown(tierQuality("high", 2), 2);
    expect(sharp.steps).toEqual(["dpr", "dpr", "live", "shells", "msaa", "bloom", "scale", "stand-ins", "no cards", "fps"]);
    // A 1x screen: no resolution to give, so live light goes first; 4x MSAA comes off in two steps.
    const plain = walkDown(tierQuality("high", 1), 1);
    expect(plain.steps).toEqual(["live", "shells", "msaa", "msaa", "bloom", "scale", "stand-ins", "no cards", "fps"]);
    // Each new step changes only its own flag; resolution is already at 1x when live light goes.
    const [, , atOne, liveOff, shellsOff] = sharp.states;
    expect(effectiveDpr(atOne, 2)).toBe(1);
    expect(atOne).toMatchObject({ liveLight: true, vegShells: true, msaa: 2, bloom: true });
    expect(liveOff).toEqual({ ...atOne, liveLight: false });
    expect(shellsOff).toEqual({ ...liveOff, vegShells: false });
    // The bottom: everything the ladder can take is gone, and nothing that needs a reload changed.
    for (const w of [sharp, plain]) {
      expect(w.end).toMatchObject({
        liveLight: false,
        vegShells: false,
        msaa: 0,
        bloom: false,
        maxDpr: RENDER_SCALE_MIN,
        standIns: true,
        noCards: true,
        maxFps: CAPPED_FPS,
        post: true,
        lowTextures: false,
      });
    }
  });

  it("a tier the visitor picked keeps live light and the shells all the way down", () => {
    for (const dpr of [1, 1.25, 1.5, 2]) {
      const start = tierQuality("high", dpr);
      const w = walkDown(start, dpr, { keepLook: true });
      expect(w.steps.every((s) => s === "dpr" || s === "scale"), `${dpr}x: ${w.steps.join(", ")}`).toBe(true);
      for (const q of w.states) expect(q, `${dpr}x`).toMatchObject({ liveLight: true, vegShells: true });
      expect(effectiveDpr(w.end, dpr)).toBe(RENDER_SCALE_MIN);
    }
    // At 1x the auto ladder would take live light next; a picked tier goes to the render scale.
    const atOne = { ...tierQuality("high", 2), maxDpr: 1 };
    expect(degradeQuality(atOne, 2)).toEqual({ ...atOne, liveLight: false });
    expect(degradeQuality(atOne, 2, { keepLook: true })).toEqual({ ...atOne, maxDpr: RENDER_SCALE_MIN });
  });

  it("Medium and Low never had them, so their walks down and back are as before", () => {
    const cases = [
      { name: "desktop Medium", top: tierQuality("mid", 1), dpr: 1, down: ["bloom", "scale", "stand-ins", "no cards", "fps"] },
      { name: "touch Medium", top: tierQuality("mid", 2, { coarse: true }), dpr: 2, down: ["dpr", "dpr", "bloom", "scale", "stand-ins", "no cards", "fps"] },
      { name: "Safari Medium", top: tierQuality("mid", 2, { appleGpu: true }), dpr: 2, down: ["dpr", "dpr", "bloom", "scale", "stand-ins", "no cards", "fps"] },
      { name: "desktop Low", top: tierQuality("low", 1), dpr: 1, down: ["scale", "stand-ins", "no cards", "fps"] },
      { name: "phone Low", top: tierQuality("low", 3, { coarse: true }), dpr: 3, down: ["dpr", "dpr", "scale", "stand-ins", "no cards", "fps"] },
    ];
    for (const { name, top, dpr, down } of cases) {
      expect(top, name).toMatchObject({ liveLight: false, vegShells: false });
      const d = walkDown(top, dpr);
      expect(d.steps, name).toEqual(down);
      const u = walkUp(d.end, top, dpr);
      expect(u.steps, name).toEqual([...down].reverse());
      for (const q of [...d.states, ...u.states]) expect(q, name).toMatchObject({ liveLight: false, vegShells: false });
    }
  });

  it("the climb brings them back in reverse: after MSAA, the shells, then live light, then resolution", () => {
    const top = tierQuality("high", 2);
    const down = walkDown(top, 2);
    const up = walkUp(down.end, top, 2);
    expect(up.steps).toEqual(["fps", "no cards", "stand-ins", "scale", "bloom", "msaa", "shells", "live", "dpr", "dpr"]);
    expect(up.steps).toEqual([...down.steps].reverse());
    // 4x MSAA on a 1x screen: both MSAA steps come back before the shells.
    const top1 = tierQuality("high", 1);
    const up1 = walkUp(walkDown(top1, 1).end, top1, 1);
    expect(up1.steps).toEqual(["fps", "no cards", "stand-ins", "scale", "bloom", "msaa", "msaa", "shells", "live"]);
    // Only when the tier's own quality has them.
    const mid = tierQuality("mid", 1);
    expect(upgradeQuality({ ...mid, liveLight: false, vegShells: false }, mid, 1)).toBeNull();
    expect(upgradeQuality({ ...top, liveLight: false }, { ...top, liveLight: false }, 2)).toBeNull();
    expect(upgradeQuality({ ...top, vegShells: false, liveLight: false }, { ...top, vegShells: undefined }, 2)).toEqual({ ...top, vegShells: false });
    // They switch without rebuilding the postprocessing pipeline, so the climb need not wait for rest,
    // and they cost what any feature climb is assumed to cost.
    for (const q of [{ ...top, maxDpr: 1, liveLight: false }, { ...top, maxDpr: 1, liveLight: false, vegShells: false }]) {
      expect(climbRebuildsPipeline(q, top, 2)).toBe(false);
      expect(climbCost(q, top, 2)).toBe(FEATURE_CLIMB_COST);
    }
  });

  it("a full walk down from High and back up ends where it started", () => {
    // The tier's own quality at 1x (4x MSAA) on a 2x screen, and High on 1.5x and 2x screens.
    for (const [top, dpr] of [
      [tierQuality("high"), 2],
      [tierQuality("high", 1.5), 1.5],
      [tierQuality("high", 2), 2],
    ] as const) {
      const end = walkUp(walkDown(top, dpr).end, top, dpr).end;
      // standIns and noCards come back as false rather than absent: the same thing.
      expect(end).toEqual({ ...top, standIns: false, noCards: false });
    }
    // Under 1.5x the screen cannot show the tier's 1.5x cap, so the climb stops at the screen's own
    // ratio: the same pixels, everything else exactly as before.
    for (const dpr of [1, 1.25]) {
      const top = tierQuality("high", dpr);
      const end = walkUp(walkDown(top, dpr).end, top, dpr).end;
      expect(effectiveDpr(end, dpr)).toBe(effectiveDpr(top, dpr));
      expect({ ...end, maxDpr: 0 }).toEqual({ ...top, maxDpr: 0, standIns: false, noCards: false });
    }
  });
});

describe("the ladder's ceiling: live light gets one more try, then stays off", () => {
  it("below the limit the ceiling is the tier's own quality, the same object", () => {
    // The first time live light goes off it may climb back once.
    expect(LIVE_LIGHT_TRIES).toBe(2);
    for (const top of [tierQuality("high", 1), tierQuality("high", 2)]) {
      for (let n = 0; n < LIVE_LIGHT_TRIES; n++) expect(ladderCeiling(top, n)).toBe(top);
    }
  });

  it("at the limit the climb never turns live light back on, but brings everything else back and ends", () => {
    for (const dpr of [1, 1.5, 2]) {
      const top = tierQuality("high", dpr);
      const lowered = ladderCeiling(top, LIVE_LIGHT_TRIES);
      expect(lowered, `${dpr}x`).toEqual({ ...top, liveLight: false });
      // Past the limit it stays lowered.
      expect(ladderCeiling(top, LIVE_LIGHT_TRIES + 3), `${dpr}x`).toEqual(lowered);
      // From the bottom: the same climb as toward the tier's own quality, without the live step.
      const down = walkDown(top, dpr);
      const full = walkUp(down.end, top, dpr);
      const up = walkUp(down.end, lowered, dpr);
      expect(full.steps, `${dpr}x`).toContain("live");
      expect(up.steps, `${dpr}x`).toEqual(full.steps.filter((s) => s !== "live"));
      for (const q of up.states) expect(q.liveLight, `${dpr}x`).toBe(false);
      // Everything else is the tier's own again.
      expect({ ...up.end, liveLight: true }, `${dpr}x`).toEqual({ ...full.end });
    }
    // Right after live light went off (resolution at 1x on a 2x screen): the next climb is the
    // resolution, not live light.
    const top = tierQuality("high", 2);
    const lowered = ladderCeiling(top, LIVE_LIGHT_TRIES);
    const liveOff = { ...top, maxDpr: 1, liveLight: false };
    expect(upgradeQuality(liveOff, lowered, 2)).toEqual({ ...liveOff, maxDpr: 1.25 });
  });

  it("a tier without live light (Medium, Low) gets its own quality back unchanged", () => {
    const tops = [
      tierQuality("mid", 1),
      tierQuality("mid", 2, { coarse: true }),
      tierQuality("mid", 2, { appleGpu: true }),
      tierQuality("low", 1),
      tierQuality("low", 3, { coarse: true }),
    ];
    for (const top of tops) {
      expect(top.liveLight).toBe(false);
      for (const n of [0, LIVE_LIGHT_TRIES, LIVE_LIGHT_TRIES + 5]) expect(ladderCeiling(top, n)).toBe(top);
    }
  });

  it("toward the lowered ceiling there is no climb left once everything else is back", () => {
    const top = tierQuality("high", 2);
    const lowered = ladderCeiling(top, LIVE_LIGHT_TRIES);
    const rest = { ...top, liveLight: false };
    expect(upgradeQuality(rest, lowered, 2)).toBeNull();
    expect(climbCost(rest, lowered, 2)).toBeNull();
    expect(climbRebuildsPipeline(rest, lowered, 2)).toBe(false);
    // Toward the tier's own quality the same state would still climb live light.
    expect(climbCost(rest, top, 2)).toBe(FEATURE_CLIMB_COST);
    // Until then the climbs cost what they did: the shells a feature's cost, resolution its pixels.
    expect(climbCost({ ...rest, maxDpr: 1, vegShells: false }, lowered, 2)).toBe(FEATURE_CLIMB_COST);
    expect(climbCost({ ...rest, maxDpr: 1 }, lowered, 2)).toBeCloseTo(1.5625, 6);
  });

  it("counted the way the page counts, live light comes back after its first time off and not after its second", () => {
    const dpr = 2;
    const top = tierQuality("high", dpr);
    let q = top;
    let liveOffs = 0;
    const down = () => {
      const n = degradeQuality(q, dpr);
      if (!n) return;
      if (q.liveLight && !n.liveLight) liveOffs++;
      q = n;
    };
    /** Climbs toward the ladder's ceiling until there is no climb left. */
    const climbAll = () => {
      for (let n = upgradeQuality(q, ladderCeiling(top, liveOffs), dpr); n; n = upgradeQuality(q, ladderCeiling(top, liveOffs), dpr)) q = n;
    };
    // Down past live light: two resolution steps, then live light off.
    for (let i = 0; i < 3; i++) down();
    expect(q).toEqual({ ...top, maxDpr: 1, liveLight: false });
    expect(liveOffs).toBe(1);
    // Room again between stops: the climb brings it back, then the resolution.
    climbAll();
    expect(q).toEqual(top);
    // At the next stop it costs too much again.
    for (let i = 0; i < 3; i++) down();
    expect(liveOffs).toBe(2);
    // Now the climb stops short of it, for the visit.
    climbAll();
    expect(q).toEqual({ ...top, liveLight: false });
    expect(climbCost(q, ladderCeiling(top, liveOffs), dpr)).toBeNull();
    // The steps down after that skip it (it is already off) and count nothing more.
    for (let i = 0; i < 3; i++) down();
    expect(liveOffs).toBe(2);
    expect(q).toMatchObject({ maxDpr: 1, liveLight: false, vegShells: false, msaa: 2 });
  });
});

describe("the quality ladder: far places in full", () => {
  it("only High where the page holds every area; Medium and Low never", () => {
    for (const dpr of [1, 1.5, 2]) {
      expect(tierQuality("high", dpr, { holdsAll: true }).farFull).toBe(true);
      expect(tierQuality("high", dpr).farFull).toBe(false);
      expect(tierQuality("high", dpr, { holdsAll: false }).farFull).toBe(false);
      // Everything else is the same High.
      expect({ ...tierQuality("high", dpr, { holdsAll: true }), farFull: false }).toEqual(tierQuality("high", dpr));
    }
    for (const top of [
      tierQuality("mid", 1, { holdsAll: true }),
      tierQuality("mid", 2, { coarse: true, holdsAll: true }),
      tierQuality("mid", 2, { appleGpu: true, holdsAll: true }),
      tierQuality("low", 1, { holdsAll: true }),
      tierQuality("low", 3, { coarse: true, holdsAll: true }),
    ]) {
      expect(top.farFull).toBeUndefined();
    }
  });

  it("is the first step down, before resolution, and the rest of the ladder is unchanged after it", () => {
    for (const dpr of [1, 1.25, 1.5, 2]) {
      const top = tierQuality("high", dpr, { holdsAll: true });
      const without = tierQuality("high", dpr);
      const w = walkDown(top, dpr);
      expect(w.steps[0], `${dpr}x`).toBe("far");
      // One step: far places off and nothing else.
      expect(w.states[1], `${dpr}x`).toEqual({ ...top, farFull: false });
      // Then exactly the walk a High without far places takes.
      const plain = walkDown(without, dpr);
      expect(w.steps.slice(1), `${dpr}x`).toEqual(plain.steps);
      expect(w.states.slice(1), `${dpr}x`).toEqual(plain.states);
    }
    expect(walkDown(tierQuality("high", 2, { holdsAll: true }), 2).steps).toEqual(["far", "dpr", "dpr", "live", "shells", "msaa", "bloom", "scale", "stand-ins", "no cards", "fps"]);
  });

  it("goes first for a tier the visitor picked too, which then loses only resolution as before", () => {
    for (const dpr of [1, 1.25, 1.5, 2]) {
      const top = tierQuality("high", dpr, { holdsAll: true });
      const w = walkDown(top, dpr, { keepLook: true });
      expect(w.steps[0], `${dpr}x`).toBe("far");
      expect(w.states[1], `${dpr}x`).toEqual({ ...top, farFull: false });
      const plain = walkDown(tierQuality("high", dpr), dpr, { keepLook: true });
      expect(w.steps.slice(1), `${dpr}x`).toEqual(plain.steps);
      expect(w.steps.slice(1).every((s) => s === "dpr" || s === "scale"), `${dpr}x`).toBe(true);
    }
    // A picked High at 1x has no resolution to give: far places are its only step before the render scale.
    expect(walkDown(tierQuality("high", 1, { holdsAll: true }), 1, { keepLook: true }).steps).toEqual(["far", "scale"]);
  });

  it("never climbs back, from anywhere on the ladder", () => {
    for (const dpr of [1, 1.5, 2]) {
      const top = tierQuality("high", dpr, { holdsAll: true });
      const down = walkDown(top, dpr);
      const up = walkUp(down.end, top, dpr);
      expect(up.steps, `${dpr}x`).not.toContain("far");
      for (const q of up.states) expect(q.farFull, `${dpr}x`).toBe(false);
      // Everything else is the tier's own again.
      expect({ ...up.end, maxDpr: 0 }, `${dpr}x`).toEqual({ ...top, maxDpr: 0, farFull: false, standIns: false, noCards: false });
      // Right after the step: nothing to climb, so the ladder neither probes nor rebuilds for it.
      const after = { ...top, farFull: false };
      expect(upgradeQuality(after, top, dpr), `${dpr}x`).toBeNull();
      expect(climbCost(after, top, dpr), `${dpr}x`).toBeNull();
      expect(climbRebuildsPipeline(after, top, dpr), `${dpr}x`).toBe(false);
      // Toward the lowered ceiling (live light given up) the same.
      expect(upgradeQuality({ ...after, liveLight: false }, ladderCeiling(top, LIVE_LIGHT_TRIES), dpr), `${dpr}x`).toBeNull();
    }
  });

  it("a High without it (absent or off) walks down and back exactly as before", () => {
    for (const dpr of [1, 1.5, 2]) {
      const top = tierQuality("high", dpr);
      const absent: Quality = { ...top };
      delete absent.farFull;
      const a = walkDown(top, dpr);
      const b = walkDown(absent, dpr);
      expect(a.steps).not.toContain("far");
      expect(b.steps).toEqual(a.steps);
      expect(walkUp(b.end, absent, dpr).steps).toEqual([...b.steps].reverse());
      expect(degradeQuality(top, dpr)).toEqual({ ...degradeQuality(absent, dpr)!, farFull: false });
    }
  });
});
