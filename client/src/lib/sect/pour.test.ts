import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parseMeta } from "./parse";
import { fromPour, inPour, pourCrest, pourFrame, pourMiddle, POURS, poursFor, pourStream, pourWidth, toPour, warpPour, type PourSpec } from "./pour";
import type { Vec3, Waterfall } from "./types";
import { SHEET } from "./waterfall";

/** A fall pouring toward +z off a lip at (10, 100, 5), 6 m wide along x. */
function fall(over: Partial<Waterfall> = {}): Waterfall {
  return {
    name: "abode.waterfall.sheet",
    kind: "sheet",
    position: [10, 77, 7],
    size: [6, 46, 4],
    rotation: [0, 0, 0, 1],
    nearestM: 30,
    corners: [
      [7, 99, 5.6],
      [13, 99, 5.6],
      [14, 54, 9],
      [6, 54, 9],
    ],
    foot: [10, 54, 9],
    lip: [10, 100, 5],
    flow: 1,
    chunk: "abode",
    ...over,
  };
}

const spec: PourSpec = POURS[0];

describe("a pour's frame", () => {
  it("has its origin at the lip, runs across the lip and out toward the pool", () => {
    const f = pourFrame(fall());
    expect(f).not.toBeNull();
    expect(f!.origin).toEqual([10, 100, 5]);
    expect(f!.across).toEqual([1, 0, 0]);
    // The water lands at larger z.
    expect(f!.out[2]).toBeCloseTo(1);
    // The same lip seen from the other side: across turns round, out still points at the pool.
    const g = pourFrame(fall({ corners: [[13, 99, 5.6], [7, 99, 5.6], [6, 54, 9], [14, 54, 9]] }));
    expect(g!.across[0]).toBeCloseTo(-1);
    expect(g!.out[2]).toBeCloseTo(1);
  });

  it("needs the lip and the corners", () => {
    expect(pourFrame(fall({ lip: null }))).toBeNull();
    expect(pourFrame(fall({ corners: null }))).toBeNull();
  });

  it("goes to the frame and back", () => {
    const f = pourFrame(fall({ corners: [[7, 99, 3], [12, 99, 8], [14, 54, 2], [6, 54, 12]], foot: [14, 54, 2] }))!;
    const p: Vec3 = [11.5, 97.25, 6.75];
    const back = fromPour(f, toPour(f, p));
    for (let k = 0; k < 3; k++) expect(back[k]).toBeCloseTo(p[k], 9);
    // Read from a flat array at an offset.
    expect(toPour(f, [0, 0, 0, ...p], 3)).toEqual(toPour(f, p));
  });
});

describe("where a pour moves the baked sheets", () => {
  it("lifts the top to the water level, steps the crest back and narrows it to the notch", () => {
    const top = warpPour(spec, [2, spec.crestOut, spec.top]);
    expect(top[2]).toBeCloseTo(spec.level, 9);
    expect(top[1]).toBeCloseTo(spec.crestOut - spec.back, 9);
    expect(top[0] - spec.centre).toBeCloseTo((2 - spec.centre) * spec.neck, 9);
    expect(pourCrest(spec)).toEqual({ out: spec.crestOut - spec.back, level: spec.level });
  });

  it("below the lift, the step back and the fan only widens the water about its own middle", () => {
    const deep = Math.max(spec.liftOver, spec.backOver, spec.fanOver);
    const middle = 0.6;
    for (const d of [deep, deep + 3, deep + 30]) {
      const p: Vec3 = [-2.4, 1.8, spec.top - d];
      const w = warpPour(spec, p, middle);
      // Its height and its distance from the cliff are the baked ones: the foot stays on the pool.
      expect(w[1]).toBeCloseTo(p[1], 9);
      expect(w[2]).toBeCloseTo(p[2], 9);
      expect(w[0] - middle).toBeCloseTo((p[0] - middle) * spec.widen, 9);
    }
    // It reaches the sheets from their top to the pool, and nothing that is not on them.
    expect(inPour(spec, [0, 0.5, spec.top - 3])).toBe(true);
    expect(inPour(spec, [0, 4, spec.top - 46])).toBe(true);
    expect(inPour(spec, [spec.reach.across + 1, 0.5, spec.top - 3])).toBe(false);
    expect(inPour(spec, [0, spec.reach.front + 1, spec.top - 3])).toBe(false);
    expect(inPour(spec, [0, 0.5, spec.top + 2])).toBe(false);
  });

  it("keeps the rows in order: none passes the one above it, and the water only ever widens on the way down", () => {
    let lastH = Infinity;
    let lastW = 0;
    let lastO = -Infinity;
    for (let d = 0; d <= 24; d += 0.25) {
      const w = warpPour(spec, [2.5, 0.4, spec.top - d]);
      expect(w[2]).toBeLessThan(lastH);
      lastH = w[2];
      const width = w[0] - spec.centre;
      expect(width).toBeGreaterThanOrEqual(lastW - 1e-9);
      lastW = width;
      // The step back only ever eases off.
      expect(w[1]).toBeGreaterThanOrEqual(lastO - 1e-9);
      lastO = w[1];
    }
  });

  it("is as wide as the neck at the crest and at its full width from fanOver on, most of it early", () => {
    expect(pourWidth(spec, 0)).toBeCloseTo(spec.neck, 9);
    expect(pourWidth(spec, -1)).toBeCloseTo(spec.neck, 9);
    expect(pourWidth(spec, spec.fanOver)).toBeCloseTo(spec.widen, 9);
    expect(pourWidth(spec, spec.fanOver * 3)).toBeCloseTo(spec.widen, 9);
    const half = pourWidth(spec, spec.fanOver / 2);
    expect(half).toBeGreaterThan((spec.neck + spec.widen) / 2);
    // Wider than baked (room for the thin sides), and the crest still fits the notch: the abode's
    // notch is about 3 m wide at the water's level and the widest baked sheet 5.9 m.
    expect(spec.widen).toBeGreaterThanOrEqual(1);
    expect(spec.neck * 5.9).toBeLessThan(3.6);
  });

  it("gathers a fall's layers on the notch's centre line at the crest and lets them back to their places below", () => {
    const middle = 0.68;
    // The layer's own middle: on the centre line at the crest, at its baked place at full width.
    expect(warpPour(spec, [middle, 0, spec.top], middle)[0]).toBeCloseTo(spec.centre, 9);
    expect(warpPour(spec, [middle, 0.9, spec.top - 30], middle)[0]).toBeCloseTo(middle, 9);
    // Its two ends at the crest sit evenly about the centre line.
    const l = warpPour(spec, [middle - 2.5, 0, spec.top], middle)[0];
    const r = warpPour(spec, [middle + 2.5, 0, spec.top], middle)[0];
    expect((l + r) / 2).toBeCloseTo(spec.centre, 9);
    expect(r - l).toBeCloseTo(5 * spec.neck, 9);
  });

  it("finds a layer's middle from its top rows, and tells a piece that is not this pour's", () => {
    // Top rows from -1.8 to 3.2; lower rows have spread and do not count.
    const across = [-1.8, 3.2, 0.5, -4.0, 4.6];
    const up = [spec.top, spec.top - 0.5, spec.top - 0.9, spec.top - 20, spec.top - 20];
    expect(pourMiddle(spec, across, up)).toBeCloseTo(0.7, 9);
    // A sheet whose top is elsewhere (another fall in the same water file).
    expect(pourMiddle(spec, [-1, 1], [spec.top - 12, spec.top - 14])).toBeNull();
    expect(pourMiddle(spec, [40, 42], [spec.top, spec.top])).toBeNull();
  });
});

describe("the water in the notch", () => {
  const f = pourFrame(fall())!;
  const s = pourStream(spec, f);
  const n = s.positions.length / 3;
  const local = Array.from({ length: n }, (_, i) => toPour(f, s.positions, i * 3));

  it("runs from the notch's floor to the crest, level over its last metres", () => {
    // The positions are 32-bit floats at world size: good to a few hundredths of a millimetre.
    const eps = 1e-4;
    const crest = pourCrest(spec);
    const outs = local.map((l) => l[1]);
    expect(Math.min(...outs)).toBeCloseTo(spec.stream.from, 4);
    expect(Math.max(...outs)).toBeCloseTo(crest.out, 4);
    for (const l of local) {
      if (l[1] >= spec.stream.levelFrom + eps) expect(l[2]).toBeCloseTo(crest.level, 4);
      expect(l[2]).toBeGreaterThanOrEqual(spec.stream.floor - eps);
      expect(l[2]).toBeLessThanOrEqual(crest.level + eps);
      expect(Math.abs(l[0] - spec.centre)).toBeLessThanOrEqual(spec.stream.width / 2 + eps);
    }
    // It starts at the floor.
    expect(local.find((l) => Math.abs(l[1] - spec.stream.from) < eps)![2]).toBeCloseTo(spec.stream.floor, 4);
  });

  it("is a stream to the sheet shader that flows to the crest and does not thin out there", () => {
    expect(s.fall.length).toBe(n * 4);
    expect(s.uvs.length).toBe(n * 2);
    expect(s.colors.length).toBe(n * 3);
    let last = -1;
    for (let i = 0; i < n; i++) {
      const [x, along, z, w] = [s.fall[i * 4], s.fall[i * 4 + 1], s.fall[i * 4 + 2], s.fall[i * 4 + 3]];
      // z < 0 marks a stream; -(1 + its share of the length), short of the shader's foot fade.
      expect(z).toBeLessThanOrEqual(-1);
      expect(-z - 1).toBeLessThan(1 - SHEET.footFade);
      expect(w).toBe(spec.stream.width);
      expect(Math.abs(x)).toBeLessThanOrEqual(spec.stream.width / 2 + 1e-6);
      // Metres along the flow grow toward the crest (rows run from the start to the crest).
      if (i % 5 === 0) {
        expect(along).toBeGreaterThan(last);
        last = along;
      }
      // Core layer, the fall's flow.
      expect(s.colors[i * 3 + 1]).toBeCloseTo(spec.stream.flow, 6);
      expect(s.colors[i * 3 + 2]).toBe(0);
    }
  });

  it("is a closed grid of triangles that face up", () => {
    expect(s.index.length % 3).toBe(0);
    expect(Math.max(...s.index)).toBe(n - 1);
    for (let t = 0; t < s.index.length; t += 3) {
      const [a, b, c] = [s.index[t], s.index[t + 1], s.index[t + 2]].map((i) => [s.positions[i * 3], s.positions[i * 3 + 1], s.positions[i * 3 + 2]]);
      const e1 = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
      const e2 = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
      // The normal's world y.
      expect(e1[2] * e2[0] - e1[0] * e2[2]).toBeGreaterThan(0);
    }
  });
});

describe("which falls pour", () => {
  it("finds a pour by its core sheet, with its frame", () => {
    const found = poursFor([fall({ name: "other.sheet" }), fall()]);
    expect(found).toHaveLength(1);
    expect(found[0].spec).toBe(spec);
    expect(found[0].frame.origin).toEqual([10, 100, 5]);
    expect(poursFor([fall({ name: "abode.waterfall.sheet.001" })])).toEqual([]);
    expect(poursFor([fall({ lip: null })])).toEqual([]);
  });

  // The pour is tied to the bake by a name and by the lip in meta.json: a new export that renames
  // the sheet or drops its lip would switch the pour off without a word.
  const meta = join(process.cwd(), "public/sect/full/meta.json");
  it.skipIf(!existsSync(meta))("finds every pour's fall in the shipped meta.json, on its own chunk", () => {
    const m = parseMeta(JSON.parse(readFileSync(meta, "utf8")));
    for (const p of POURS) {
      const core = m.waterfalls.find((w) => w.name === p.sheet);
      expect(core, p.sheet).toBeDefined();
      const mine = m.waterfalls.filter((w) => (w.chunk ?? "global") === (core!.chunk ?? "global"));
      const found = poursFor(mine, [p]);
      expect(found, p.sheet).toHaveLength(1);
      // Out of the cliff is toward the foot, far below; the sheet's corners are within the pour's reach.
      const foot = toPour(found[0].frame, core!.foot!);
      expect(foot[1]).toBeGreaterThan(1);
      expect(foot[2]).toBeLessThan(-p.fanOver);
      for (const c of [core!.corners![0], core!.corners![1]]) expect(inPour(p, toPour(found[0].frame, c)), p.sheet).toBe(true);
    }
  });
});
