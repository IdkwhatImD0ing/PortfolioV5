import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { boundingRadius, packPuffs, PUFF_STRIDE, sortFarToNear, supportRadius } from "./clouds";
import { parseClouds, parseMeta } from "./parse";
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

/**
 * Ice-Fire Island's steam in the installed clouds.json (round 42). Only `export_web.py clouds`
 * writes Blender's puffs, and mist.py keeps whatever that step last wrote, so a batch that skips it
 * ships stale steam: until round 42 the site drew round 7's plume, made before round 34 turned the
 * island and round 36 gave it a volcano. It hung in the air 13 m beside the crater, its base above
 * the island's top. The steam is the small untagged puffs over the island's footprint (its lore
 * box); the world's banks are 15-60 m across and the mist is tagged.
 */
describe("installed Ice-Fire steam", () => {
  const dir = path.resolve(__dirname, "../../../public/sect/full");
  const load = () => {
    if (!existsSync(path.join(dir, "clouds.json")) || !existsSync(path.join(dir, "meta.json"))) return null;
    const meta = parseMeta(JSON.parse(readFileSync(path.join(dir, "meta.json"), "utf8")));
    const box = (meta.lore ?? []).find((b) => b.id === "icefire-island");
    if (!box) return null;
    const bottom = box.center[1] - box.size[1] / 2;
    const steam = parseClouds(JSON.parse(readFileSync(path.join(dir, "clouds.json"), "utf8")))
      .filter(
        (p) =>
          p.kind === undefined &&
          boundingRadius(p.axes) < 12 &&
          Math.abs(p.c[0] - box.center[0]) < box.size[0] / 2 &&
          Math.abs(p.c[2] - box.center[2]) < box.size[2] / 2 &&
          p.c[1] > bottom,
      )
      .sort((a, b) => a.c[1] - b.c[1]);
    return { steam, top: box.center[1] + box.size[1] / 2 };
  };

  it("rises from the island, not from the air above it", () => {
    const s = load();
    if (!s) return;
    expect(s.steam.length).toBeGreaterThanOrEqual(10);
    // The plume starts in the crater and the snout's steam on the top: inside the island's box.
    expect(s.steam[0].c[1]).toBeLessThan(s.top);
    expect(s.steam.filter((p) => p.c[1] < s.top).length).toBeGreaterThanOrEqual(2);
  });

  it("is one unbroken column above the island's top", () => {
    const s = load();
    if (!s) return;
    // Every puff above the top touches one below it (centres no farther apart than their radii).
    for (const p of s.steam.filter((q) => q.c[1] >= s.top)) {
      const touches = s.steam.some(
        (q) =>
          q !== p &&
          q.c[1] < p.c[1] &&
          Math.hypot(p.c[0] - q.c[0], p.c[1] - q.c[1], p.c[2] - q.c[2]) <= boundingRadius(p.axes) + boundingRadius(q.axes),
      );
      expect(touches, `puff at ${p.c.join(", ")}`).toBe(true);
    }
  });
});
