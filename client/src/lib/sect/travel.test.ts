import { describe, expect, it } from "vitest";
import { BLOT_CORE, BLOT_SOLID, blotOutline, coverRadius, dropGrowth, easeInOutCubic, farCorner, inkDrops, seedOf, seededRandom, travelTiming } from "./travel";

describe("travelTiming", () => {
  it("moves plainly with reduced motion, and never waits forever", () => {
    const ink = travelTiming(false);
    const plain = travelTiming(true);
    expect(plain.cover + plain.reveal).toBeLessThan(500);
    expect(ink.cover + ink.hold + ink.reveal).toBeLessThan(3000);
    expect(ink.cover).toBeGreaterThan(plain.cover);
    for (const t of [ink, plain]) expect(t.giveUp).toBeLessThanOrEqual(30000);
  });

  it("stays covered long enough to feel deliberate, the same with reduced motion, and waits long for a slow place", () => {
    for (const t of [travelTiming(false), travelTiming(true)]) {
      expect(t.hold).toBeGreaterThanOrEqual(1000);
      expect(t.hold).toBeLessThanOrEqual(1500);
      // Longer than the 16 s the slowest measured arrival (700 KB/s) took for the place's own area.
      expect(t.giveUp).toBeGreaterThanOrEqual(20000);
    }
    expect(travelTiming(true).hold).toBe(travelTiming(false).hold);
  });
});

describe("seeded shapes", () => {
  it("gives the same numbers for the same seed", () => {
    const a = seededRandom(7);
    const b = seededRandom(7);
    const xs = Array.from({ length: 5 }, () => a());
    expect(xs).toEqual(Array.from({ length: 5 }, () => b()));
    for (const x of xs) {
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThan(1);
    }
    expect(seedOf("forge")).toBe(seedOf("forge"));
    expect(seedOf("forge")).not.toBe(seedOf("arena"));
  });

  it("draws a ragged rim that stays between the solid part and the sprite's edge", () => {
    const rim = blotOutline(seedOf("gate"), 120);
    expect(rim).toHaveLength(120);
    for (const r of rim) {
      expect(r).toBeGreaterThanOrEqual(BLOT_SOLID);
      expect(r).toBeLessThanOrEqual(1);
    }
    // Not a circle.
    expect(Math.max(...rim) - Math.min(...rim)).toBeGreaterThan(0.1);
    expect(blotOutline(seedOf("gate"))).toEqual(blotOutline(seedOf("gate")));
  });
});

describe("covering the screen", () => {
  const view = { w: 1600, h: 900 };

  it("measures to the farthest corner", () => {
    expect(farCorner([0, 0], view)).toBeCloseTo(Math.hypot(1600, 900));
    expect(farCorner([800, 450], view)).toBeCloseTo(Math.hypot(800, 450));
  });

  it("grows the main blot until even its solid part covers every corner", () => {
    for (const at of [
      [0, 0],
      [800, 450],
      [1500, 100],
    ] as const) {
      const drops = inkDrops(seedOf("x"), at, view);
      const main = drops[0];
      expect(main.x).toBe(at[0]);
      expect(main.start).toBe(0);
      expect(main.span).toBe(1);
      expect(main.r * BLOT_CORE).toBeGreaterThanOrEqual(farCorner(at, view));
      expect(main.r).toBe(coverRadius(at, view));
    }
  });

  it("adds smaller drops on the screen that start later and end in time", () => {
    const drops = inkDrops(seedOf("library"), [200, 700], view, 3);
    expect(drops).toHaveLength(4);
    for (const d of drops.slice(1)) {
      expect(d.x).toBeGreaterThanOrEqual(0);
      expect(d.x).toBeLessThanOrEqual(view.w);
      expect(d.y).toBeGreaterThanOrEqual(0);
      expect(d.y).toBeLessThanOrEqual(view.h);
      expect(d.r).toBeLessThan(drops[0].r);
      expect(d.start).toBeGreaterThan(0);
      expect(d.start + d.span).toBeLessThanOrEqual(1);
    }
  });

  it("splashes fast then slows, or blooms slow then fast, and holds once done", () => {
    const d = { start: 0.2, span: 0.5 };
    expect(dropGrowth(d, 0.1)).toBe(0);
    expect(dropGrowth(d, 0.45)).toBeGreaterThan(0.8);
    expect(dropGrowth(d, 0.7)).toBe(1);
    expect(dropGrowth(d, 2)).toBe(1);
    const bloom = { start: 0, span: 1, curve: "bloom" as const };
    expect(dropGrowth(bloom, 0.2)).toBeLessThan(0.15);
    expect(dropGrowth(bloom, 0.5)).toBe(0.5);
    expect(dropGrowth(bloom, 1)).toBe(1);
    expect(inkDrops(1, [10, 10], { w: 100, h: 100 }).map((x) => x.curve)).toEqual(["bloom", "splash", "splash", "splash"]);
    expect(easeInOutCubic(0)).toBe(0);
    expect(easeInOutCubic(0.5)).toBe(0.5);
    expect(easeInOutCubic(1)).toBe(1);
  });
});
