import { describe, expect, it } from "vitest";
import { craneFlights, cranePose, hash01, PETAL_STRIDE, petalOffset, petalSeeds, wrap } from "./fx";
import type { Vec3 } from "./types";

describe("petals", () => {
  it("wraps into [0, n) for negative values too", () => {
    expect(wrap(5, 4)).toBe(1);
    expect(wrap(-1, 4)).toBe(3);
    expect(wrap(8, 4)).toBe(0);
  });

  it("seeds are deterministic and in range", () => {
    const a = petalSeeds(50);
    expect(a.length).toBe(50 * PETAL_STRIDE);
    expect(Array.from(a)).toEqual(Array.from(petalSeeds(50)));
    for (let i = 0; i < 50; i++) {
      for (let k = 0; k < 3; k++) {
        expect(Math.abs(a[i * PETAL_STRIDE + k])).toBeLessThanOrEqual(1);
      }
    }
    expect(hash01(3)).not.toBe(hash01(4));
  });

  it("always stay in a cube around the camera, wherever it flies", () => {
    const seed: Vec3 = [0.3, -0.7, 0.9];
    for (const cam of [
      [0, 0, 0],
      [1234.5, 80, -567.8],
      [-90, 40, 250],
    ] as Vec3[]) {
      for (const t of [0, 3.7, 120]) {
        const o = petalOffset(seed, 1.2, t, cam, 24);
        for (const v of o) expect(Math.abs(v)).toBeLessThanOrEqual(24);
      }
    }
  });

  it("drift smoothly with the wind (no jumps between nearby times, away from the wrap)", () => {
    const a = petalOffset([0, 0, 0], 0, 1.0, [0, 0, 0], 24);
    const b = petalOffset([0, 0, 0], 0, 1.05, [0, 0, 0], 24);
    expect(Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])).toBeLessThan(0.2);
  });
});

describe("cranes", () => {
  const areas: Vec3[] = [
    [0, 50, 12],
    [-100, 77, -208],
  ];

  it("circle high over the areas, the same every visit", () => {
    const f = craneFlights(areas, 5);
    expect(f.length).toBe(5);
    expect(f).toEqual(craneFlights(areas, 5));
    for (const c of f) expect(c.center[1]).toBeGreaterThan(90);
    expect(craneFlights([], 5)).toEqual([]);
  });

  it("head along their loop", () => {
    const [c] = craneFlights(areas, 1);
    const a = cranePose(c, 10);
    const b = cranePose(c, 10.1);
    const dx = b.p[0] - a.p[0];
    const dz = b.p[2] - a.p[2];
    // heading 0 faces -z; the direction of travel matches (-sin h, -cos h).
    const h = a.heading;
    const dot = (dx * -Math.sin(h) + dz * -Math.cos(h)) / Math.hypot(dx, dz);
    expect(dot).toBeGreaterThan(0.95);
  });
});
