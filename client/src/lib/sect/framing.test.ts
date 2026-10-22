import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { sampleCamera } from "./camera-path";
import { FRAMING_MAX_DEG, FRAMING_REACH_FRAMES, STOP_FRAMING, framingAt, framingWeight } from "./framing";
import { composeLook } from "./free-look";
import { POSTER } from "./opening";
import { projectPoint } from "./coords";
import { panelSide } from "./nav";
import type { CameraFrame, Vec3 } from "./types";

const DEG = Math.PI / 180;
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

  it("leaves unlisted stops, the flight between stops and the poster's start view as the film framed them", () => {
    for (const h of HOLDS) {
      if (STOP_FRAMING[h.id]) continue;
      expect(framingAt(HOLDS, h.frame)).toEqual({ yaw: 0, pitch: 0 });
    }
    expect(framingAt(HOLDS, POSTER.startFrame)).toEqual({ yaw: 0, pitch: 0 });
    for (let k = 0; k + 1 < HOLDS.length; k++) {
      const mid = (HOLDS[k].frame + HOLDS[k + 1].frame) / 2;
      expect(framingAt(HOLDS, mid)).toEqual({ yaw: 0, pitch: 0 });
    }
  });

  it("never lets two stops' framings meet", () => {
    for (let k = 0; k + 1 < HOLDS.length; k++) expect(HOLDS[k + 1].frame - HOLDS[k].frame).toBeGreaterThanOrEqual(2 * FRAMING_REACH_FRAMES);
    expect(HOLDS[0].frame - POSTER.startFrame).toBeGreaterThan(FRAMING_REACH_FRAMES);
  });

  it("eases in and out along the flight with no step from one frame to the next", () => {
    const h = HOLDS.find((x) => x.id === "mirror")!;
    let prev = framingAt(HOLDS, h.frame - FRAMING_REACH_FRAMES - 2);
    let biggest = 0;
    for (let f = h.frame - FRAMING_REACH_FRAMES - 2; f <= h.frame + FRAMING_REACH_FRAMES + 2; f += 0.25) {
      const o = framingAt(HOLDS, f);
      biggest = Math.max(biggest, Math.abs(o.yaw - prev.yaw), Math.abs(o.pitch - prev.pitch));
      prev = o;
    }
    // A quarter frame never turns the view more than 0.1 degrees.
    expect(biggest).toBeLessThan(0.1 * DEG);
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
  function view(holdId: string, framed: boolean): CameraFrame {
    const h = camera.holds.find((x) => x.id === holdId)!;
    const s = sampleCamera(camera.frames, h.frame);
    return { f: h.frame, p: s.p, fovY: s.fovY, q: framed ? composeLook(s.q, framingAt(camera.holds, h.frame)) : s.q };
  }
  /** Where a hotspot lands at a hold, in NDC (x right, y up): its centre and its box's screen extent. */
  function at(id: string, holdId: string, framed: boolean): { c: [number, number]; min: [number, number]; max: [number, number] } {
    const v = view(holdId, framed);
    const hs = meta.hotspots.find((x) => x.id === id)!;
    const pr = (x: Vec3) => {
      const p = projectPoint(v.p, v.q, v.fovY, camera.refAspect, x);
      expect(p.depth).toBeGreaterThan(0);
      return p.ndc;
    };
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

  it("brings the Heart-Mirror in from the left edge to the left third", () => {
    // At 1600 px wide: from 287 px in to 500 (the left third is at 533).
    expect(at("mirror", "mirror", false).c[0]).toBeLessThan(-0.6);
    const m = at("mirror", "mirror", true).c;
    expect(m[0]).toBeGreaterThan(-0.45);
    expect(m[0]).toBeLessThan(-0.3);
    // A little higher in the picture (the view tilts down): the pond and its reflection come in below.
    expect(m[1]).toBeGreaterThan(at("mirror", "mirror", false).c[1]);
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

  it("brings the jade slip's left roller in from the edge", () => {
    expect(at("resume", "scroll", false).min[0]).toBeLessThan(-0.99);
    expect(at("resume", "scroll", true).min[0]).toBeGreaterThan(-0.8);
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
      expect(panelSide(view(h.id, true), camera.refAspect, landmark), h.id).toBe(panelSide(view(h.id, false), camera.refAspect, landmark));
    }
  });
});
