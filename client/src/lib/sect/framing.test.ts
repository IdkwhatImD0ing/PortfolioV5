import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { sampleCamera } from "./camera-path";
import { isAreaId } from "./areas";
import { areaSummary } from "./content";
import {
  FRAMING_MAX_BACK,
  FRAMING_MAX_DEG,
  FRAMING_REACH_FRAMES,
  STOP_FRAMING,
  framingAt,
  framingFrame,
  framingReach,
  framingWeight,
  type StopFraming,
} from "./framing";
import { composeLook } from "./free-look";
import { POSTER } from "./opening";
import { projectPoint } from "./coords";
import { panelSide } from "./nav";
import type { CameraFrame, Vec3 } from "./types";

const DEG = Math.PI / 180;

/** A camera orientation's forward direction (three.js cameras look down local -Z). */
function projectFwd(q: readonly number[]): Vec3 {
  const [x, y, z, w] = q;
  return [-2 * (x * z + w * y), -2 * (y * z - w * x), -(1 - 2 * (x * x + y * y))];
}

/** A stop's framing reach (frames), 0 for a stop that is not framed. */
function reachOf(id: string): number {
  const t = STOP_FRAMING[id];
  return t ? framingReach(t) : 0;
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
    for (const h of HOLDS) {
      const r = reachOf(h.id);
      if (!r) continue;
      for (const f of [h.frame - r, h.frame + r]) expect(framingAt(HOLDS, f)).toEqual({ yaw: 0, pitch: 0 });
    }
    // Midway between two stops the view is the film's own, or within a degree of it where the
    // mirror's longer reach has begun to ease in (0.65 degrees, 62 frames out of 80).
    for (let k = 0; k + 1 < HOLDS.length; k++) {
      const o = framingAt(HOLDS, (HOLDS[k].frame + HOLDS[k + 1].frame) / 2);
      expect(Math.hypot(o.yaw, o.pitch)).toBeLessThan(1 * DEG);
    }
  });

  it("never lets two stops' framings meet, or reach another stop or the poster", () => {
    for (let k = 0; k + 1 < HOLDS.length; k++) {
      expect(reachOf(HOLDS[k].id) + reachOf(HOLDS[k + 1].id)).toBeLessThanOrEqual(HOLDS[k + 1].frame - HOLDS[k].frame);
    }
    expect(HOLDS[0].frame - POSTER.startFrame).toBeGreaterThan(Math.max(FRAMING_REACH_FRAMES, reachOf(HOLDS[0].id)));
    for (const t of Object.values(STOP_FRAMING)) expect(framingReach(t)).toBeGreaterThanOrEqual(FRAMING_REACH_FRAMES);
  });

  it("eases in and out along the flight with no step from one frame to the next", () => {
    const h = HOLDS.find((x) => x.id === "mirror")!;
    const r = reachOf("mirror");
    let prev = framingAt(HOLDS, h.frame - r - 2);
    let biggest = 0;
    for (let f = h.frame - r - 2; f <= h.frame + r + 2; f += 0.25) {
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

describe("framingFrame", () => {
  it("stands the camera back by the stop's own amount at its hold, and not past its reach", () => {
    for (const h of HOLDS) {
      const back = STOP_FRAMING[h.id]?.back ?? 0;
      expect(framingFrame(HOLDS, h.frame)).toBeCloseTo(h.frame - back, 9);
    }
    expect(framingFrame(HOLDS, POSTER.startFrame)).toBe(POSTER.startFrame);
    // Midway between two stops, within 2 frames of the film's (the mirror's longer reach: 1.7).
    for (let k = 0; k + 1 < HOLDS.length; k++) {
      const mid = (HOLDS[k].frame + HOLDS[k + 1].frame) / 2;
      expect(Math.abs(framingFrame(HOLDS, mid) - mid)).toBeLessThan(2);
    }
    const r = reachOf("mirror");
    expect(framingFrame(HOLDS, 217 - r)).toBe(217 - r);
    expect(framingFrame(HOLDS, 217 + r)).toBe(217 + r);
  });

  it("keeps the camera moving forward, at between half and one and a half times the film's pace", () => {
    for (const [id, t] of Object.entries(STOP_FRAMING)) {
      const h = HOLDS.find((x) => x.id === id)!;
      const back = t.back ?? 0;
      const r = framingReach(t);
      expect(back).toBeGreaterThanOrEqual(0);
      expect(back).toBeLessThanOrEqual(FRAMING_MAX_BACK);
      let slowest = Infinity;
      let fastest = 0;
      for (let f = h.frame - r - 2; f <= h.frame + r + 2; f += 0.25) {
        const pace = (framingFrame(HOLDS, f + 0.25) - framingFrame(HOLDS, f)) / 0.25;
        slowest = Math.min(slowest, pace);
        fastest = Math.max(fastest, pace);
      }
      // The pace is 1 - back times the weight's slope (at most 1.5 / reach either way).
      expect(slowest, id).toBeGreaterThanOrEqual(1 - (1.5 * back) / r - 1e-3);
      expect(fastest, id).toBeLessThanOrEqual(1 + (1.5 * back) / r + 1e-3);
      expect(slowest, id).toBeGreaterThanOrEqual(0.5 - 1e-3);
      expect(fastest, id).toBeLessThanOrEqual(1.5 + 1e-3);
    }
  });

  it("holds the pull-back to FRAMING_MAX_BACK and the reach to at least FRAMING_REACH_FRAMES", () => {
    expect(framingFrame([{ id: "x", frame: 100 }], 100, { x: { yaw: 0, pitch: 0, back: 60 } })).toBe(100 - FRAMING_MAX_BACK);
    expect(framingFrame([{ id: "x", frame: 100 }], 100, { x: { yaw: 0, pitch: 0, back: -5 } })).toBe(100);
    expect(framingFrame([{ id: "x", frame: 100 }], 100, { x: { yaw: 3, pitch: 0 } })).toBe(100);
    expect(framingReach({ yaw: 0, pitch: 0, reach: 10 })).toBe(FRAMING_REACH_FRAMES);
    expect(framingReach({ yaw: 0, pitch: 0, reach: 80 })).toBe(80);
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
    const r = t ? framingReach(t) : FRAMING_REACH_FRAMES;
    let most = 0;
    let prev = fwd(viewAt(h - r - 2, framed, table));
    for (let f = h - r - 1.75; f <= h + r + 2; f += 0.25) {
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

  it("shows the jade slip as the film frames it: big and close on the left, past the left edge, the pavilion clear", () => {
    // The owner preferred the first build to the slip turned square to a turned view (2026-10-22): the
    // slip stands where it first stood (blender scroll.py, patch_r15_scroll_restore.py) and the page
    // shows the film's own pose at the hold, neither stood back nor turned.
    const h = camera.holds.find((x) => x.id === "scroll")!.frame;
    expect(STOP_FRAMING.scroll).toBeUndefined();
    expect(framingAt(camera.holds, h)).toEqual({ yaw: 0, pitch: 0 });
    expect(framingFrame(camera.holds, h)).toBe(h);
    expect(view("scroll", true)).toEqual(view("scroll", false));
    // The slip's middle at the left edge, its left half past it; its right end a third of the way in
    // (x 516 of 1600 in the owner's screenshot; the hotspot's box, square to the world, reaches a little
    // further), its top over the middle of the picture: big and close, the characters about 21 px tall.
    const slip = at("resume", "scroll", true);
    expect(slip.c[0]).toBeGreaterThan(-1.25);
    expect(slip.c[0]).toBeLessThan(-0.9);
    expect(slip.min[0]).toBeLessThan(-1);
    expect(slip.max[0]).toBeGreaterThan(-0.45);
    expect(slip.max[0]).toBeLessThan(-0.15);
    expect(slip.max[1]).toBeGreaterThan(0.2);
    expect(slip.max[1]).toBeLessThan(0.5);
    // The pavilion right of it near the middle, wholly under the panel's bottom (0.39 up at 1600 x 900).
    const pav = at("scroll", "scroll", true);
    expect(pav.c[0]).toBeGreaterThan(slip.max[0]);
    expect(Math.abs(pav.c[0])).toBeLessThan(0.2);
    expect(pav.max[1]).toBeLessThan(0.3);
  });

  it("turns the view on the way to and from the jade slip as the film does", () => {
    // Out of the stop the film turns right and tilts up the stair at a degree a frame (0.999); with
    // no framing there the page adds nothing to it.
    expect(steepest("scroll", false)).toBeLessThan(1);
    expect(Math.abs(steepest("scroll", true) - steepest("scroll", false))).toBeLessThan(1e-9);
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
