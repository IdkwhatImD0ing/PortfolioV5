import { describe, expect, it } from "vitest";
import { MISSING_COLOR, anyMissingColor, fillMissingColors, repairColors } from "./vertex-colors";

/**
 * The repair as it was before it learnt to skip work (every triangle every pass, a full sort for
 * the median): the reference the faster one must match.
 */
function referenceFill(colors: Float32Array, positions: ArrayLike<number>, index: ArrayLike<number>, passes = 6, shade = 0.5): number {
  const n = colors.length / 3;
  const miss = (v: number) => colors[v * 3] <= MISSING_COLOR && colors[v * 3 + 1] <= MISSING_COLOR && colors[v * 3 + 2] <= MISSING_COLOR;
  const known = new Uint8Array(n);
  let missing = 0;
  for (let v = 0; v < n; v++) {
    if (miss(v)) missing++;
    else known[v] = 1;
  }
  if (missing === 0 || missing === n) return 0;
  const sum = new Float32Array(n * 3);
  const cnt = new Uint16Array(n);
  let filled = 0;
  for (let p = 0; p < passes; p++) {
    sum.fill(0);
    cnt.fill(0);
    for (let t = 0; t + 2 < index.length; t += 3) {
      const tv = [index[t], index[t + 1], index[t + 2]];
      const k = known[tv[0]] + known[tv[1]] + known[tv[2]];
      if (k === 0 || k === 3) continue;
      for (const v of tv) {
        if (known[v]) continue;
        for (const u of tv) {
          if (!known[u]) continue;
          for (let c = 0; c < 3; c++) sum[v * 3 + c] += colors[u * 3 + c];
          cnt[v]++;
        }
      }
    }
    let changed = 0;
    for (let v = 0; v < n; v++) {
      if (known[v] || cnt[v] === 0) continue;
      for (let c = 0; c < 3; c++) colors[v * 3 + c] = sum[v * 3 + c] / cnt[v];
      known[v] = 1;
      changed++;
    }
    filled += changed;
    if (changed === 0) break;
  }
  if (filled === missing) return filled;
  const order: number[] = [];
  for (let v = 0; v < n; v++) if (known[v]) order.push(v);
  const lum = (v: number) => 0.2126 * colors[v * 3] + 0.7152 * colors[v * 3 + 1] + 0.0722 * colors[v * 3 + 2];
  order.sort((x, y) => lum(x) - lum(y));
  const m = order[Math.floor(order.length / 2)];
  const ny = new Float32Array(n);
  for (let t = 0; t + 2 < index.length; t += 3) {
    const [a, b, c] = [index[t], index[t + 1], index[t + 2]];
    const u = [positions[b * 3] - positions[a * 3], positions[b * 3 + 1] - positions[a * 3 + 1], positions[b * 3 + 2] - positions[a * 3 + 2]];
    const w = [positions[c * 3] - positions[a * 3], positions[c * 3 + 1] - positions[a * 3 + 1], positions[c * 3 + 2] - positions[a * 3 + 2]];
    const nrm = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
    const y = nrm[1] / (Math.hypot(nrm[0], nrm[1], nrm[2]) || 1);
    ny[a] += y;
    ny[b] += y;
    ny[c] += y;
  }
  for (let v = 0; v < n; v++) {
    if (known[v]) continue;
    const k = ny[v] < -0.35 ? shade : 1;
    for (let c = 0; c < 3; c++) colors[v * 3 + c] = colors[m * 3 + c] * k;
    filled++;
  }
  return filled;
}

/** A w x h grid of vertices (two triangles a cell) with seeded colours: `black` of them unset. */
function grid(w: number, h: number, black: (x: number, y: number) => boolean, seed = 1) {
  let s = seed;
  const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  const pos = new Float32Array(w * h * 3);
  const col = new Float32Array(w * h * 3);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const v = y * w + x;
      pos.set([x, Math.sin(x * 0.3) * 0.2, y], v * 3);
      if (!black(x, y)) col.set([0.2 + 0.6 * rnd(), 0.2 + 0.5 * rnd(), 0.1 + 0.4 * rnd()], v * 3);
    }
  }
  const idx: number[] = [];
  for (let y = 0; y + 1 < h; y++) {
    for (let x = 0; x + 1 < w; x++) {
      const a = y * w + x;
      idx.push(a, a + w, a + 1, a + 1, a + w, a + w + 1);
    }
  }
  return { pos, col, idx: new Uint32Array(idx) };
}

/** A strip of quads along x (two triangles each), all facing up. */
function strip(quads: number) {
  const pos: number[] = [];
  for (let i = 0; i <= quads; i++) pos.push(i, 0, 0, i, 0, 1);
  const idx: number[] = [];
  for (let i = 0; i < quads; i++) {
    const a = i * 2;
    // Counter-clockwise seen from above (+y): normals point up.
    idx.push(a, a + 1, a + 2, a + 2, a + 1, a + 3);
  }
  return { pos: new Float32Array(pos), idx: new Uint32Array(idx), n: (quads + 1) * 2 };
}

describe("fillMissingColors", () => {
  it("fills black vertices from their coloured neighbours", () => {
    const { pos, idx, n } = strip(3);
    const c = new Float32Array(n * 3).fill(0);
    // The first two vertices are lit grey; the rest are unset.
    c.set([0.5, 0.5, 0.6, 0.5, 0.5, 0.6]);
    const filled = fillMissingColors(c, pos, idx);
    expect(filled).toBe(n - 2);
    for (let v = 0; v < n; v++) {
      expect(c[v * 3]).toBeCloseTo(0.5, 5);
      expect(c[v * 3 + 2]).toBeCloseTo(0.6, 5);
    }
  });

  it("leaves a mesh with no black vertex, or none set at all, alone", () => {
    const { pos, idx, n } = strip(1);
    const lit = new Float32Array(n * 3).fill(0.3);
    expect(fillMissingColors(lit, pos, idx)).toBe(0);
    const dark = new Float32Array(n * 3).fill(0);
    expect(fillMissingColors(dark, pos, idx)).toBe(0);
    expect([...dark].every((x) => x === 0)).toBe(true);
  });

  it("keeps dark-but-set colours (only an exact black is missing)", () => {
    const { pos, idx, n } = strip(1);
    const c = new Float32Array(n * 3).fill(0.02);
    expect(fillMissingColors(c, pos, idx)).toBe(0);
  });

  it("gives a piece the bake missed entirely the mesh's median colour, darker underneath", () => {
    // Two separate triangles: one lit, one black and facing down.
    const pos = new Float32Array([0, 0, 0, 0, 0, 1, 1, 0, 0, 5, 0, 0, 6, 0, 0, 5, 0, 1]);
    const idx = new Uint32Array([0, 1, 2, 3, 4, 5]);
    const c = new Float32Array(18).fill(0);
    c.set([0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4]);
    // Second triangle, wound so it faces down (-y).
    expect(fillMissingColors(c, pos, idx, { undersideShade: 0.5 })).toBe(3);
    expect(c[9]).toBeCloseTo(0.2, 5);
  });

  it("matches the full repair exactly wherever the colours spread", () => {
    // Scattered black vertices and a black blob 4 rings deep, all within reach of set ones.
    const { pos, col, idx } = grid(40, 30, (x, y) => (x * 7 + y * 13) % 11 === 0 || (Math.abs(x - 20) < 4 && Math.abs(y - 15) < 4), 7);
    const ref = col.slice();
    const want = referenceFill(ref, pos, idx);
    expect(want).toBeGreaterThan(50);
    let asked = 0;
    const got = fillMissingColors(col, () => (asked++, pos), idx);
    expect(got).toBe(want);
    expect([...col]).toEqual([...ref]);
    // Nothing needed the fallback, so the positions were never made.
    expect(asked).toBe(0);
  });

  it("gives unreachable pieces about the median colour the full sort found", () => {
    // One pass only: the middle of a big black square stays out of reach.
    const { pos, col, idx } = grid(30, 30, (x, y) => x > 5 && x < 25 && y > 5 && y < 25, 3);
    const ref = col.slice();
    referenceFill(ref, pos, idx, 1);
    const filled = repairColors(col, pos, idx, { passes: 1 });
    expect(filled.length).toBe(19 * 19);
    const centre = (15 * 30 + 15) * 3;
    for (let c = 0; c < 3; c++) expect(col[centre + c]).toBeCloseTo(ref[centre + c], 1);
    // The ring the one pass reached is exact.
    const ring = (6 * 30 + 15) * 3;
    for (let c = 0; c < 3; c++) expect(col[ring + c]).toBe(ref[ring + c]);
  });

  it("lists the vertices it filled", () => {
    const { pos, idx, n } = strip(3);
    const c = new Float32Array(n * 3).fill(0);
    c.set([0.5, 0.5, 0.6, 0.5, 0.5, 0.6]);
    expect([...repairColors(c, pos, idx)].sort((a, b) => a - b)).toEqual([2, 3, 4, 5, 6, 7]);
    expect(repairColors(new Float32Array(n * 3).fill(0.3), pos, idx).length).toBe(0);
  });
});

describe("anyMissingColor", () => {
  it("finds an unset vertex in a float attribute", () => {
    expect(anyMissingColor(new Float32Array([0.2, 0.1, 0.3, 0, 0, 0]), 2, 3, 0, 1)).toBe(true);
    expect(anyMissingColor(new Float32Array([0.2, 0.1, 0.3, 0, 0.01, 0]), 2, 3, 0, 1)).toBe(false);
  });

  it("reads normalised bytes (RGBA, interleaved) at their scale", () => {
    // Two RGBA vertices after 4 bytes of something else: the second is black (1/255 counts as unset).
    const bytes = new Uint8Array([9, 9, 9, 9, 40, 30, 20, 255, 9, 9, 9, 9, 1, 0, 1, 255]);
    expect(anyMissingColor(bytes, 2, 8, 4, 255)).toBe(true);
    bytes[12] = 3;
    expect(anyMissingColor(bytes, 2, 8, 4, 255)).toBe(false);
  });
});
