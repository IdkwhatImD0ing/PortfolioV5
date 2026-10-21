import { describe, expect, it } from "vitest";
import { boundingRadius, packPuffs, PUFF_STRIDE, sortFarToNear, supportRadius } from "./clouds";
import type { CloudPuff, Vec3 } from "./types";

const puff = (c: Vec3, r: Vec3, density = 0.4): CloudPuff => ({
  c,
  axes: [
    [r[0], 0, 0],
    [0, r[1], 0],
    [0, 0, r[2]],
  ],
  density,
});

describe("cloud puffs", () => {
  it("measures an ellipsoid's reach along a direction", () => {
    const p = puff([0, 0, 0], [20, 5, 10]);
    expect(supportRadius(p.axes, [1, 0, 0])).toBeCloseTo(20);
    expect(supportRadius(p.axes, [0, 1, 0])).toBeCloseTo(5);
    const d = Math.SQRT1_2;
    expect(supportRadius(p.axes, [d, 0, d])).toBeCloseTo(Math.sqrt(0.5 * 400 + 0.5 * 100));
    expect(boundingRadius(p.axes)).toBe(20);
  });

  it("works for rotated axes", () => {
    const c = Math.cos(0.7);
    const s = Math.sin(0.7);
    const axes: [Vec3, Vec3, Vec3] = [
      [20 * c, 0, 20 * s],
      [-6 * s, 0, 6 * c],
      [0, 3, 0],
    ];
    expect(supportRadius(axes, [c, 0, s])).toBeCloseTo(20);
    expect(supportRadius(axes, [0, 1, 0])).toBeCloseTo(3);
  });

  it("keeps puffs near the path and packs them", () => {
    const puffs = [puff([0, 0, 0], [10, 5, 10]), puff([5000, 0, 0], [50, 20, 50], 0.1)];
    const packed = packPuffs(puffs, [[0, 0, 100]], 1000);
    expect(packed.length).toBe(PUFF_STRIDE);
    expect(Array.from(packed.slice(0, 3))).toEqual([0, 0, 0]);
    expect(packed[12]).toBeCloseTo(0.4);
    expect(packPuffs(puffs, [], 1000).length).toBe(2 * PUFF_STRIDE);
  });

  it("scales density by position when asked", () => {
    const packed = packPuffs([puff([0, 0, 0], [1, 1, 1], 0.5), puff([100, 0, 0], [1, 1, 1], 0.5)], [], 0, (c) =>
      c[0] < 50 ? 0.5 : 1,
    );
    expect(packed[12]).toBeCloseTo(0.25);
    expect(packed[PUFF_STRIDE + 12]).toBeCloseTo(0.5);
  });

  it("sorts far to near", () => {
    const packed = packPuffs([puff([0, 0, -10], [1, 1, 1]), puff([0, 0, -300], [1, 1, 1]), puff([0, 0, -50], [1, 1, 1])], [], 0);
    const order = sortFarToNear(packed, [0, 0, 0], new Uint32Array(3), new Float32Array(3));
    expect(Array.from(order)).toEqual([1, 2, 0]);
  });
});
