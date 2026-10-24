import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { fovForAspect, sampleCamera } from "./camera-path";
import { isAreaId } from "./areas";
import { areaSummary } from "./content";
import {
  FRAMING_MAX_BACK,
  FRAMING_MAX_DEG,
  FRAMING_REACH_FRAMES,
  PORTRAIT_STOP_FRAMING,
  STOP_FRAMING,
  framingAt,
  framingFrame,
  framingReach,
  framingTable,
  framingWeight,
  type StopFraming,
} from "./framing";
import { composeLook } from "./free-look";
import { POSTER, portraitTurn } from "./opening";
import { projectPoint } from "./coords";
import { panelSide } from "./nav";
import type { CameraFrame, Vec3 } from "./types";

const DEG = Math.PI / 180;

/** A camera orientation's forward direction (three.js cameras look down local -Z). */
function projectFwd(q: readonly number[]): Vec3 {
  const [x, y, z, w] = q;
  return [-2 * (x * z + w * y), -2 * (y * z - w * x), -(1 - 2 * (x * x + y * y))];
}

/** A stop's framing reach before and after its hold (frames), 0 for a stop that is not framed. */
function reachOf(id: string): readonly [number, number] {
  const t = STOP_FRAMING[id];
  return t ? framingReach(t) : [0, 0];
}

/** The table with only stop `id`: its own framing, without a neighbour's handing over. */
function only(id: string): Record<string, StopFraming> {
  return { [id]: STOP_FRAMING[id] };
}

/** Holds whose framing passes straight on to the next framed hold's (one's reach after meets the other's before). */
function handsOver(k: number): boolean {
  const a = HOLDS[k];
  const b = HOLDS[k + 1];
  const gap = b.frame - a.frame;
  return !!STOP_FRAMING[a.id] && !!STOP_FRAMING[b.id] && reachOf(a.id)[1] === gap && reachOf(b.id)[0] === gap;
}

const HOLDS = [
  { id: "gate", frame: 93 },
  { id: "mirror", frame: 217 },
  { id: "forge", frame: 352 },
  { id: "arena", frame: 516 },
  { id: "mission", frame: 619 },
  { id: "library", frame: 772 },
  { id: "steles", frame: 974 },
  { id: "scroll", frame: 1103 },
  { id: "formation", frame: 1208 },
  { id: "abode", frame: 1380 },
  { id: "summit", frame: 1647 },
];

describe("framingWeight", () => {
  it("is full at the hold, gone a reach away, and eased between", () => {
    expect(framingWeight(217, 217)).toBe(1);
    expect(framingWeight(217 + FRAMING_REACH_FRAMES, 217)).toBe(0);
    expect(framingWeight(217 - FRAMING_REACH_FRAMES - 5, 217)).toBe(0);
    expect(framingWeight(217 + FRAMING_REACH_FRAMES / 2, 217)).toBeCloseTo(0.5, 9);
    expect(framingWeight(217 - FRAMING_REACH_FRAMES / 2, 217)).toBeCloseTo(0.5, 9);
    expect(framingWeight(Number.NaN, 217)).toBe(0);
    expect(framingWeight(217, 217, 0)).toBe(0);
  });

  it("comes and goes over each side's own reach when the two differ", () => {
    // 64 frames before the hold, 105 after: half way in 32 frames before it, 52.5 after.
    expect(framingWeight(1103 - 32, 1103, [64, 105])).toBeCloseTo(0.5, 9);
    expect(framingWeight(1103 + 52.5, 1103, [64, 105])).toBeCloseTo(0.5, 9);
    expect(framingWeight(1103 - 64, 1103, [64, 105])).toBe(0);
    expect(framingWeight(1103 + 80, 1103, [64, 105])).toBeGreaterThan(0);
    expect(framingWeight(1103 + 105, 1103, [64, 105])).toBe(0);
    expect(framingWeight(1103, 1103, [64, 105])).toBe(1);
  });

  it("starts, peaks and ends with zero slope, and never moves faster than 1.5 times its average", () => {
    const R = FRAMING_REACH_FRAMES;
    const slope = (f: number) => (framingWeight(f + 1e-4, 0) - framingWeight(f - 1e-4, 0)) / 2e-4;
    expect(Math.abs(slope(R - 1e-3))).toBeLessThan(1e-3);
    expect(Math.abs(slope(-R + 1e-3))).toBeLessThan(1e-3);
    expect(Math.abs(slope(1e-3))).toBeLessThan(1e-3);
    let steepest = 0;
    for (let f = -R; f <= R; f += 0.25) steepest = Math.max(steepest, Math.abs(slope(f)));
    expect(steepest).toBeLessThanOrEqual((1.5 / R) * 1.0001);
    // Monotonic on each side.
    for (let f = 0; f < R; f += 0.5) expect(framingWeight(f + 0.5, 0)).toBeLessThanOrEqual(framingWeight(f, 0));
  });
});

describe("framingAt", () => {
  it("turns the view by the stop's own amount at its hold, in radians", () => {
    for (const [id, t] of Object.entries(STOP_FRAMING)) {
      const h = HOLDS.find((x) => x.id === id)!;
      const o = framingAt(HOLDS, h.frame);
      expect(o.yaw).toBeCloseTo(t.yaw * DEG, 9);
      expect(o.pitch).toBeCloseTo(t.pitch * DEG, 9);
    }
  });

  it("leaves unlisted stops, the flight away from the framed stops and the poster's start view as the film framed them", () => {
    for (const h of HOLDS) {
      if (STOP_FRAMING[h.id]) continue;
      expect(framingAt(HOLDS, h.frame)).toEqual({ yaw: 0, pitch: 0 });
    }
    expect(framingAt(HOLDS, POSTER.startFrame)).toEqual({ yaw: 0, pitch: 0 });
    // Each stop's own framing is gone at the ends of its reach.
    for (const h of HOLDS) {
      if (!STOP_FRAMING[h.id]) continue;
      const [before, after] = reachOf(h.id);
      for (const f of [h.frame - before, h.frame + after]) expect(framingAt(HOLDS, f, only(h.id))).toEqual({ yaw: 0, pitch: 0 });
    }
    // Midway between two stops the view is the film's own, or within a degree of it where the
    // mirror's longer reach has begun to ease in (0.65 degrees, 62 frames out of 80); except where
    // the jade slip hands over to the formation, midway between their framings there.
    for (let k = 0; k + 1 < HOLDS.length; k++) {
      const o = framingAt(HOLDS, (HOLDS[k].frame + HOLDS[k + 1].frame) / 2);
      if (handsOver(k)) {
        const [a, b] = [STOP_FRAMING[HOLDS[k].id], STOP_FRAMING[HOLDS[k + 1].id]];
        expect(o.yaw).toBeCloseTo(((a.yaw + b.yaw) / 2) * DEG, 9);
        expect(o.pitch).toBeCloseTo(((a.pitch + b.pitch) / 2) * DEG, 9);
      } else expect(Math.hypot(o.yaw, o.pitch)).toBeLessThan(1 * DEG);
    }
    expect(HOLDS.filter((_, k) => k + 1 < HOLDS.length && handsOver(k)).map((h) => h.id)).toEqual(["scroll"]);
  });

  it("never lets two stops' framings meet, or reach another stop or the poster, but where one hands over to the next", () => {
    for (let k = 0; k + 1 < HOLDS.length; k++) {
      const gap = HOLDS[k + 1].frame - HOLDS[k].frame;
      // A hand-over runs the whole way from one hold to the next, both ways: the two weights add up
      // to 1 there (smoothstep S(x) + S(1 - x) = 1), and neither reaches past the other's hold.
      if (handsOver(k)) continue;
      expect(reachOf(HOLDS[k].id)[1] + reachOf(HOLDS[k + 1].id)[0], HOLDS[k].id).toBeLessThanOrEqual(gap);
    }
    expect(HOLDS[0].frame - POSTER.startFrame).toBeGreaterThan(Math.max(FRAMING_REACH_FRAMES, reachOf(HOLDS[0].id)[0]));
    for (const t of Object.values(STOP_FRAMING)) for (const r of framingReach(t)) expect(r).toBeGreaterThanOrEqual(FRAMING_REACH_FRAMES);
  });

  it("adds a hand-over's two framings up to the one, then the other, along the smoothstep", () => {
    const s = STOP_FRAMING.scroll;
    const f = STOP_FRAMING.formation;
    for (const x of [0, 0.1, 0.25, 0.5, 0.75, 0.9, 1]) {
      const t = x * x * (3 - 2 * x);
      const o = framingAt(HOLDS, 1103 + 105 * x);
      expect(o.yaw).toBeCloseTo((s.yaw + (f.yaw - s.yaw) * t) * DEG, 9);
      expect(o.pitch).toBeCloseTo((s.pitch + (f.pitch - s.pitch) * t) * DEG, 9);
      expect(framingFrame(HOLDS, 1103 + 105 * x)).toBeCloseTo(1103 + 105 * x - (s.back ?? 0) * (1 - t), 9);
    }
  });

  it("eases in and out along the flight with no step from one frame to the next", () => {
    for (const id of ["mirror", "scroll", "formation"]) {
      const h = HOLDS.find((x) => x.id === id)!;
      const [before, after] = reachOf(id);
      let prev = framingAt(HOLDS, h.frame - before - 2);
      let biggest = 0;
      for (let f = h.frame - before - 2; f <= h.frame + after + 2; f += 0.25) {
        const o = framingAt(HOLDS, f);
        biggest = Math.max(biggest, Math.abs(o.yaw - prev.yaw), Math.abs(o.pitch - prev.pitch));
        prev = o;
      }
      // A quarter frame never turns the view more than 0.1 degrees.
      expect(biggest, id).toBeLessThan(0.1 * DEG);
    }
  });

  it("keeps every turn small", () => {
    for (const t of Object.values(STOP_FRAMING)) {
      expect(Math.abs(t.yaw)).toBeLessThanOrEqual(FRAMING_MAX_DEG);
      expect(Math.abs(t.pitch)).toBeLessThanOrEqual(FRAMING_MAX_DEG);
    }
    const big = framingAt([{ id: "x", frame: 0 }], 0, { x: { yaw: 30, pitch: -30 } });
    expect(big.yaw).toBeCloseTo(FRAMING_MAX_DEG * DEG, 9);
    expect(big.pitch).toBeCloseTo(-FRAMING_MAX_DEG * DEG, 9);
  });
});

describe("framingFrame", () => {
  it("stands the camera back by the stop's own amount at its hold, and not past its reach", () => {
    for (const h of HOLDS) {
      const back = STOP_FRAMING[h.id]?.back ?? 0;
      expect(framingFrame(HOLDS, h.frame)).toBeCloseTo(h.frame - back, 9);
    }
    expect(framingFrame(HOLDS, POSTER.startFrame)).toBe(POSTER.startFrame);
    // Midway between two stops, within 2 frames of the film's (the mirror's longer reach: 1.7), but
    // half way through a hand-over (the jade slip's 12 frames back, half gone).
    for (let k = 0; k + 1 < HOLDS.length; k++) {
      const mid = (HOLDS[k].frame + HOLDS[k + 1].frame) / 2;
      const want = handsOver(k) ? ((STOP_FRAMING[HOLDS[k].id].back ?? 0) + (STOP_FRAMING[HOLDS[k + 1].id].back ?? 0)) / 2 : 0;
      expect(Math.abs(mid - framingFrame(HOLDS, mid) - want)).toBeLessThan(handsOver(k) ? 1e-9 : 2);
    }
    const [before, after] = reachOf("mirror");
    expect(framingFrame(HOLDS, 217 - before)).toBe(217 - before);
    expect(framingFrame(HOLDS, 217 + after)).toBe(217 + after);
  });

  it("keeps the camera moving forward, at between half and one and a half times the film's pace", () => {
    for (const table of [STOP_FRAMING, PORTRAIT_STOP_FRAMING]) {
      for (const [id, t] of Object.entries(table)) {
        const h = HOLDS.find((x) => x.id === id)!;
        const back = t.back ?? 0;
        const [before, after] = framingReach(t);
        expect(back).toBeGreaterThanOrEqual(0);
        expect(back).toBeLessThanOrEqual(FRAMING_MAX_BACK);
        let slowest = Infinity;
        let fastest = 0;
        for (let f = h.frame - before - 2; f <= h.frame + after + 2; f += 0.25) {
          const pace = (framingFrame(HOLDS, f + 0.25, table) - framingFrame(HOLDS, f, table)) / 0.25;
          slowest = Math.min(slowest, pace);
          fastest = Math.max(fastest, pace);
        }
        // The pace is 1 - back times the weight's slope (at most 1.5 / reach on either side; a hand-over
        // adds the next stop's, which stands no further back).
        const b = Math.max(back, ...HOLDS.filter((x) => Math.abs(x.frame - h.frame) <= Math.max(before, after)).map((x) => table[x.id]?.back ?? 0));
        expect(slowest, id).toBeGreaterThanOrEqual(1 - (1.5 * b) / Math.min(before, after) - 1e-3);
        expect(fastest, id).toBeLessThanOrEqual(1 + (1.5 * b) / Math.min(before, after) + 1e-3);
        expect(slowest, id).toBeGreaterThanOrEqual(0.5 - 1e-3);
        expect(fastest, id).toBeLessThanOrEqual(1.5 + 1e-3);
      }
    }
  });

  it("stands further back on a portrait screen only where a stop asks, with the same turns", () => {
    expect(framingTable(1600, 900)).toBe(STOP_FRAMING);
    expect(framingTable(390, 844)).toBe(PORTRAIT_STOP_FRAMING);
    expect(framingFrame(HOLDS, 1103, PORTRAIT_STOP_FRAMING)).toBeCloseTo(1103 - STOP_FRAMING.scroll.portraitBack!, 9);
    for (const [id, t] of Object.entries(STOP_FRAMING)) {
      const p = PORTRAIT_STOP_FRAMING[id];
      expect({ ...p, back: t.back }, id).toEqual(t);
      expect(p.back, id).toBe(t.portraitBack ?? t.back);
      const h = HOLDS.find((x) => x.id === id)!;
      for (const f of [h.frame - 30, h.frame, h.frame + 30]) expect(framingAt(HOLDS, f, PORTRAIT_STOP_FRAMING)).toEqual(framingAt(HOLDS, f));
    }
  });

  it("holds the pull-back to FRAMING_MAX_BACK and the reach to at least FRAMING_REACH_FRAMES", () => {
    expect(framingFrame([{ id: "x", frame: 100 }], 100, { x: { yaw: 0, pitch: 0, back: 60 } })).toBe(100 - FRAMING_MAX_BACK);
    expect(framingFrame([{ id: "x", frame: 100 }], 100, { x: { yaw: 0, pitch: 0, back: -5 } })).toBe(100);
    expect(framingFrame([{ id: "x", frame: 100 }], 100, { x: { yaw: 3, pitch: 0 } })).toBe(100);
    expect(framingReach({ yaw: 0, pitch: 0, reach: 10 })).toEqual([FRAMING_REACH_FRAMES, FRAMING_REACH_FRAMES]);
    expect(framingReach({ yaw: 0, pitch: 0, reach: 80 })).toEqual([80, 80]);
    expect(framingReach({ yaw: 0, pitch: 0, reach: [64, 20] })).toEqual([64, FRAMING_REACH_FRAMES]);
    expect(framingReach({ yaw: 0, pitch: 0 })).toEqual([FRAMING_REACH_FRAMES, FRAMING_REACH_FRAMES]);
    const long = { x: { yaw: 8, pitch: 0, back: 8, reach: 80 } };
    expect(framingAt([{ id: "x", frame: 100 }], 160, long).yaw).toBeCloseTo(8 * DEG * framingWeight(160, 100, 80), 9);
    expect(framingFrame([{ id: "x", frame: 100 }], 160, long)).toBeCloseTo(160 - 8 * framingWeight(160, 100, 80), 9);
  });
});

describe("the stops' framing on the baked path", () => {
  const camera = JSON.parse(readFileSync(path.resolve(__dirname, "../../../public/sect/full/camera.json"), "utf8")) as {
    frames: CameraFrame[];
    holds: { id: string; frame: number }[];
    refAspect: number;
  };
  const meta = JSON.parse(readFileSync(path.resolve(__dirname, "../../../public/sect/full/meta.json"), "utf8")) as {
    areas: { id: string; anchor: Vec3 }[];
    hotspots: { id: string; center: Vec3; size: Vec3 }[];
  };
  type Table = Readonly<Record<string, StopFraming>>;
  /**
   * The camera at path frame `f` as the page shows it: framed (stood back and turned, by `table`),
   * or the film's own.
   */
  function viewAt(f: number, framed: boolean, table: Table = STOP_FRAMING): CameraFrame {
    const s = sampleCamera(camera.frames, framed ? framingFrame(camera.holds, f, table) : f);
    return { f, p: s.p, fovY: s.fovY, q: framed ? composeLook(s.q, framingAt(camera.holds, f, table)) : s.q };
  }
  function view(holdId: string, framed: boolean, table?: Table): CameraFrame {
    return viewAt(camera.holds.find((x) => x.id === holdId)!.frame, framed, table);
  }
  /** Where a point lands at a hold, in NDC (x right, y up), at 16:9. */
  function pointAt(x: Vec3, holdId: string, framed: boolean, table?: Table): [number, number] {
    const v = view(holdId, framed, table);
    const p = projectPoint(v.p, v.q, v.fovY, camera.refAspect, x);
    expect(p.depth).toBeGreaterThan(0);
    return p.ndc as [number, number];
  }
  /** Where a hotspot lands at a hold, in NDC (x right, y up): its centre and its box's screen extent. */
  function at(id: string, holdId: string, framed: boolean, table?: Table): { c: [number, number]; min: [number, number]; max: [number, number] } {
    const hs = meta.hotspots.find((x) => x.id === id)!;
    const pr = (x: Vec3) => pointAt(x, holdId, framed, table);
    const corners = [-1, 1].flatMap((a) => [-1, 1].flatMap((b) => [-1, 1].map((c) => pr([0, 1, 2].map((k) => hs.center[k] + [a, b, c][k] * hs.size[k] / 2) as Vec3))));
    return {
      c: pr(hs.center) as [number, number],
      min: [Math.min(...corners.map((q) => q[0])), Math.min(...corners.map((q) => q[1]))],
      max: [Math.max(...corners.map((q) => q[0])), Math.max(...corners.map((q) => q[1]))],
    };
  }

  it("uses the camera's holds", () => {
    expect(camera.holds.map((h) => ({ id: h.id, frame: h.frame }))).toEqual(HOLDS);
  });

  it("brings the whole Still Pond into the middle of the picture, its pavilion and the Heart-Mirror above its reflection", () => {
    // The pond's box at the water: its west, east, far (north) and near (south) ends.
    const pond = meta.hotspots.find((x) => x.id === "mirror-pond")!;
    const water = pond.center[1];
    const ends = ([[-1, 0], [1, 0], [0, -1], [0, 1]] as const).map(([a, b]) => [pond.center[0] + (a * pond.size[0]) / 2, water, pond.center[2] + (b * pond.size[2]) / 2] as Vec3);
    // The film's hold showed a side of it: its west end off the left edge, its near end off the bottom.
    expect(pointAt(ends[0], "mirror", false)[0]).toBeLessThan(-1);
    expect(pointAt(ends[3], "mirror", false)[1]).toBeLessThan(-1);
    // Now all of it is in with a margin, below the panel (whose bottom is 0.2 up at 1600 x 900), its
    // middle a little left of the screen's (in the free space left of and below the panel).
    for (const e of ends) {
      const p = pointAt(e, "mirror", true);
      expect(Math.abs(p[0])).toBeLessThan(0.9);
      expect(p[1]).toBeGreaterThan(-0.9);
      expect(p[1]).toBeLessThan(0.2);
    }
    const c = pointAt(pond.center, "mirror", true);
    expect(c[0]).toBeGreaterThan(-0.3);
    expect(c[0]).toBeLessThan(0);
    // The pavilion on its island, whole.
    const pav = at("mirror-pavilion", "mirror", true);
    expect(pav.min[0]).toBeGreaterThan(-0.9);
    expect(pav.min[1]).toBeGreaterThan(-0.9);
    expect(pav.max[1]).toBeLessThan(0.9);
    // The Heart-Mirror from 287 px in from the left edge to the middle, whole and left of the panel
    // (its left edge is 0.38 in at 1600 x 900), standing over its own reflection in the pond.
    expect(at("mirror", "mirror", false).c[0]).toBeLessThan(-0.6);
    const m = at("mirror", "mirror", true);
    expect(m.min[0]).toBeGreaterThan(-0.3);
    expect(m.max[0]).toBeLessThan(0.38);
    expect(m.max[1]).toBeLessThan(0.9);
    const mc = meta.hotspots.find((x) => x.id === "mirror")!.center;
    const r = pointAt([mc[0], 2 * water - mc[1], mc[2]], "mirror", true);
    expect(Math.abs(r[0] - m.c[0])).toBeLessThan(0.05);
    const near = pointAt(ends[3], "mirror", true);
    const far = pointAt(ends[2], "mirror", true);
    expect(r[1]).toBeLessThan(far[1]);
    expect(r[1]).toBeGreaterThan(near[1]);
  });

  /**
   * Most degrees the view turns per path frame on the way to and from hold `holdId`, from 2 frames
   * before its reach (by `table`) to 2 after.
   */
  function steepest(holdId: string, framed: boolean, table: Table = STOP_FRAMING): number {
    const fwd = (v: CameraFrame) => projectFwd(v.q);
    const h = camera.holds.find((x) => x.id === holdId)!.frame;
    const t = table[holdId];
    const [before, after] = t ? framingReach(t) : [FRAMING_REACH_FRAMES, FRAMING_REACH_FRAMES];
    let most = 0;
    let prev = fwd(viewAt(h - before - 2, framed, table));
    for (let f = h - before - 1.75; f <= h + after + 2; f += 0.25) {
      const d = fwd(viewAt(f, framed, table));
      const dot = Math.min(1, prev[0] * d[0] + prev[1] * d[1] + prev[2] * d[2]);
      most = Math.max(most, Math.acos(dot) / DEG / 0.25);
      prev = d;
    }
    return most;
  }

  it("turns the view on the way to and from the mirror about as gently as the old turn did", () => {
    // The film's own turning peaks near 0.8 degrees a frame here, as the camera leaves. The old 8
    // degree turn added a quarter (1.08); standing back speeds the camera along that stretch, and over
    // the mirror's 80 frame reach the framing adds about as much (1.1).
    expect(steepest("mirror", false)).toBeLessThan(0.85);
    expect(steepest("mirror", true)).toBeLessThan(1.12);
  });

  it("brings the mission hall's board in from the left edge, the bell left of the panel", () => {
    const posts = ["role:0", "role:1", "role:2", "role:3", "role:4", "role:5", "role:6"];
    // The first post touched the left edge (7 px in); now the board starts 245 px in.
    expect(at("role:0", "mission", false).min[0]).toBeLessThan(-0.98);
    expect(Math.min(...posts.map((r) => at(r, "mission", true).min[0]))).toBeGreaterThan(-0.75);
    // The board's middle, left of the screen's by about the width the panel takes on the right.
    const mid = posts.reduce((a, r) => a + at(r, "mission", true).c[0], 0) / posts.length;
    expect(mid).toBeGreaterThan(-0.3);
    expect(mid).toBeLessThan(0);
    // The bell's centre stays left of the panel (its left edge is about 0.45 in at 1600 x 900).
    expect(at("mission-bell", "mission", true).c[0]).toBeLessThan(0.45);
  });

  /**
   * The jade slip from its hotspot's box (square to the world; the slip runs from its west-north end to
   * its east-south one, across the box's plan diagonal, so the box's corners there are its two ends, a
   * little past its rolled left end): a point `s` along it (-1 its left end, 1 its right) at height `y`.
   */
  function slipAt(s: number, y: number): Vec3 {
    const box = meta.hotspots.find((x) => x.id === "resume")!;
    return [box.center[0] + (s * box.size[0]) / 2, y, box.center[2] - (s * box.size[2]) / 2];
  }

  it("shows the whole jade slip on its stand, big and square to the view, and the whole pavilion beside it", () => {
    // The owner found the film's own view "too in my face" (2026-10-23): the slip big and close on the
    // left, its left part past the edge and its stand cut by the bottom. The slip stands where it first
    // stood (blender scroll.py); the camera stands back and turns.
    const box = meta.hotspots.find((x) => x.id === "resume")!;
    const top = box.center[1] + box.size[1] / 2;
    const bottom = box.center[1] - box.size[1] / 2;
    const paving = meta.areas.find((a) => a.id === "scroll")!.anchor[1];
    // Its sun and moon on the post heads rise about 4.3 m over the slips (scroll.py frame_points); the
    // posts stand 7.5 m either side of its middle, a little over half way to its ends.
    const emblems = top + 4.3;
    const before = (s: number, y: number) => pointAt(slipAt(s, y), "scroll", false);
    const after = (s: number, y: number) => pointAt(slipAt(s, y), "scroll", true);
    // Before: its left end past the left edge, its middle at it, its stand's feet below the bottom.
    expect(before(-1, top)[0]).toBeLessThan(-2);
    expect(before(0, top)[0]).toBeLessThan(-1);
    expect(before(0.56, paving)[1]).toBeLessThan(-1);
    // Now: both ends in with room round them (the left one 111 px in from the edge at 1600 x 900: the
    // box's corner, a little past the slip's rolled end; 7 px when the camera stood 9 frames back, "too
    // far forward", the owner, 2026-10-24), the stand's feet on the paving above the bottom (94 px up),
    // the sun and the moon on the post heads below the top (150 px down).
    for (const s of [-1, 1]) for (const y of [top, bottom]) {
      const p = after(s, y);
      expect(Math.abs(p[0]), `${s} ${y}`).toBeLessThan(0.9);
      expect(Math.abs(p[1]), `${s} ${y}`).toBeLessThan(0.5);
    }
    expect(after(-1, top)[0]).toBeGreaterThan(-0.88);
    for (const s of [-0.56, 0.56]) {
      expect(after(s, paving)[1]).toBeGreaterThan(-0.9);
      expect(after(s, paving)[1]).toBeLessThan(-0.7);
      expect(after(s, emblems)[1]).toBeLessThan(0.75);
    }
    // Big: the slips 272 px tall at their middle at 1600 x 900 (the verses about 14 px a character;
    // 299 from 9 frames back), against 434 in the film's own view; and square to the view, its two
    // ends as far away as each other (they were 26 m and 33 m away).
    const tall = (after(0, top)[1] - after(0, bottom)[1]) * 450;
    expect(tall).toBeGreaterThan(265);
    expect(tall).toBeLessThan(280);
    expect((before(0, top)[1] - before(0, bottom)[1]) * 450).toBeGreaterThan(430);
    const v = view("scroll", true);
    const depth = (s: number) => projectPoint(v.p, v.q, v.fovY, camera.refAspect, slipAt(s, box.center[1])).depth;
    expect(Math.abs(depth(-1) - depth(1)) / depth(0)).toBeLessThan(0.05);
    const v0 = view("scroll", false);
    const depth0 = (s: number) => projectPoint(v0.p, v0.q, v0.fovY, camera.refAspect, slipAt(s, box.center[1])).depth;
    expect(Math.abs(depth0(-1) - depth0(1)) / depth0(0)).toBeGreaterThan(0.2);
    // The pavilion right of the slip, whole and clear of the edges, its top (the finial) left of the
    // panel (its left edge 0.42 in at 1600 x 900, 0.35 at 1366 x 768) and its eaves below it.
    const pav = at("scroll", "scroll", true);
    expect(pav.c[0]).toBeGreaterThan(after(1, top)[0]);
    expect(pav.min[0]).toBeGreaterThan(-0.9);
    expect(pav.max[0]).toBeLessThan(0.9);
    expect(pav.min[1]).toBeGreaterThan(-0.9);
    expect(pav.max[1]).toBeLessThan(0.9);
    const p = meta.hotspots.find((x) => x.id === "scroll")!;
    expect(pointAt([p.center[0], p.center[1] + p.size[1] / 2, p.center[2]], "scroll", true)[0]).toBeLessThan(0.33);
  });

  it("on a phone, stands further back: the whole slip and the whole pavilion side by side between the labels and the panel", () => {
    // A 390 x 844 phone sees 36 degrees across (camera-path.ts fovForAspect), the picture shifted up
    // a fifth of the screen (scene.tsx PORTRAIT_SHIFT), between the stop's label and look hint (down to
    // 156 px) and the panel (from 632 px), and turned at rest (opening.ts PORTRAIT_TURN_DEG).
    const [w, h] = [390, 844];
    const px = (x: Vec3, table: Table): [number, number] => {
      const v = view("scroll", true, table);
      const q = composeLook(v.q, portraitTurn("scroll", true));
      const p = projectPoint(v.p, q, fovForAspect(v.fovY, camera.refAspect, w / h), w / h, x);
      expect(p.depth).toBeGreaterThan(0);
      return [((p.ndc[0] + 1) / 2) * w, ((1 - p.ndc[1]) / 2) * h - Math.round(h * 0.2)];
    };
    const box = meta.hotspots.find((x) => x.id === "resume")!;
    const top = box.center[1] + box.size[1] / 2;
    const bottom = box.center[1] - box.size[1] / 2;
    const paving = meta.areas.find((a) => a.id === "scroll")!.anchor[1];
    // The pavilion round its hotspot's centre: its eaves reach about 9 m out (the box, 24 m across, is
    // padded for picking), its platform on the paving, its roofs up to 14 m, its finial at the box's top.
    const pav = meta.hotspots.find((x) => x.id === "scroll")!;
    const eaves = Array.from({ length: 24 }, (_, k) => (k * Math.PI) / 12).flatMap((a) =>
      [paving, paving + 14].map((y) => [pav.center[0] + 9 * Math.cos(a), y, pav.center[2] + 9 * Math.sin(a)] as Vec3),
    );
    const pavPoints = [...eaves, [pav.center[0], pav.center[1] + pav.size[1] / 2, pav.center[2]] as Vec3];
    const slip = [-1, 1].flatMap((s) => [top, bottom].map((y) => slipAt(s, y)));
    const stand = [-0.56, 0.56].flatMap((s) => [slipAt(s, paving), slipAt(s, top + 4.3)]);
    const span = (table: Table) => {
      const ps = [...slip, ...stand, ...pavPoints].map((x) => px(x, table));
      return { x0: Math.min(...ps.map((p) => p[0])), x1: Math.max(...ps.map((p) => p[0])), y0: Math.min(...ps.map((p) => p[1])), y1: Math.max(...ps.map((p) => p[1])) };
    };
    // From where the 16:9 framing stands the slip and the pavilion are wider than the phone.
    const near = span(STOP_FRAMING);
    expect(near.x1 - near.x0).toBeGreaterThan(w);
    // From further back, both whole across it: the slip's ends, its stand's feet on the paving and its
    // sun and moon, the pavilion's box; between the hint and the panel, with room.
    const far = span(PORTRAIT_STOP_FRAMING);
    expect(far.x0).toBeGreaterThan(5);
    expect(far.x1).toBeLessThan(w - 5);
    expect(far.y0).toBeGreaterThan(156 + 40);
    expect(far.y1).toBeLessThan(632 - 100);
    // Centred across the phone, within a few pixels.
    expect(Math.abs(far.x0 - (w - far.x1))).toBeLessThan(10);
    // The pavilion right of the slip, the slips 82 px tall at their middle (89 from 21 frames back,
    // before the owner asked for the camera "slightly back", 2026-10-24).
    expect(px(pav.center, PORTRAIT_STOP_FRAMING)[0]).toBeGreaterThan(px(slipAt(1, top), PORTRAIT_STOP_FRAMING)[0]);
    const slipTall = px(slipAt(0, bottom), PORTRAIT_STOP_FRAMING)[1] - px(slipAt(0, top), PORTRAIT_STOP_FRAMING)[1];
    expect(slipTall).toBeGreaterThan(78);
    expect(slipTall).toBeLessThan(86);
  });

  it("turns the view on the way to and from the jade slip about as gently as round the mirror", () => {
    // Out of the stop the film turns right and tilts up the stair at a degree a frame (0.999). The
    // framing's turn back the same way, and the camera catching up the 12 frames it stood back, add to
    // it: over the default 48 frames, or all the 57 the formation's 48 leave, that would be over 1.4
    // degrees a frame. Handed over to the formation's framing over the 105 frames to its hold
    // instead, the view turns at most 1.17 degrees a frame (1.13 from 9 frames back), about as round
    // the mirror (1.10); the formation's approach carries the slip's framing in (its own framing alone
    // made it 1.09).
    expect(steepest("scroll", false)).toBeLessThan(1);
    const s = STOP_FRAMING.scroll;
    const alone = (reach: number) => ({ ...STOP_FRAMING, scroll: { ...s, reach }, formation: { ...STOP_FRAMING.formation, reach: FRAMING_REACH_FRAMES } });
    expect(steepest("scroll", true, alone(48))).toBeGreaterThan(1.4);
    expect(steepest("scroll", true, alone(57))).toBeGreaterThan(1.4);
    expect(steepest("scroll", true)).toBeLessThan(1.18);
    expect(steepest("formation", true)).toBeLessThan(1.18);
    expect(steepest("formation", true, alone(48))).toBeLessThan(1.1);
    // On a portrait screen the camera catches up 24 frames instead, over the same 105: 1.35 degrees a
    // frame at the most (the turn at rest, opening.ts PORTRAIT_TURN_DEG, swings back with the free look).
    expect(steepest("scroll", true, PORTRAIT_STOP_FRAMING)).toBeLessThan(1.36);
    expect(steepest("formation", true, PORTRAIT_STOP_FRAMING)).toBeLessThan(1.36);
  });

  it("brings the whole formation up into the picture", () => {
    // The two front stations reached past the bottom edge; now all eight are in, with room.
    for (const k of [5, 6]) expect(at(`arch:${k}`, "formation", false).min[1]).toBeLessThan(-1);
    for (let k = 0; k < 8; k++) expect(at(`arch:${k}`, "formation", true).min[1]).toBeGreaterThan(-0.8);
    // The armillary from the bottom third to near the middle.
    expect(at("formation", "formation", false).c[1]).toBeLessThan(-0.6);
    expect(Math.abs(at("formation", "formation", true).c[1])).toBeLessThan(0.3);
  });

  it("leaves every stop's panel on the side it was on", () => {
    for (const h of camera.holds) {
      const landmark = meta.areas.find((a) => a.id === h.id)?.anchor ?? meta.hotspots.find((x) => x.id === h.id)?.center ?? null;
      // A landmark near the middle leaves the panel on its area's own side (content.ts areaSummary).
      const fallback = isAreaId(h.id) ? areaSummary(h.id).side : null;
      const side = (framed: boolean) => panelSide(view(h.id, framed), camera.refAspect, landmark) ?? fallback;
      expect(side(true), h.id).toBe(side(false));
    }
  });
});
