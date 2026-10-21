import { describe, expect, it } from "vitest";
import {
  buildCells,
  camIndex,
  cellCount,
  cellDistance,
  densityAt,
  fitBudget,
  flowerAt,
  GRASS,
  grassRingGlsl,
  grassTier,
  heightFade,
  KIND,
  leanByte,
  mergeInstances,
  nearestCam,
  nearSheet,
  rankByte,
  rankOf,
  rootGreen,
  rootInstances,
  rootTexel,
  RANK_STEP,
  ringAt,
  rimDrawDist,
  scatterGround,
  scatterSteps,
  sheetIndex,
  sizeByte,
  sizeOf,
  underPond,
  yawByte,
  type GrassInstances,
  type GroundSoup,
} from "./grass";
import { tierQuality } from "./runtime";

const high = GRASS.tiers.high;
const mid = GRASS.tiers.mid;

/** A flat square lawn at height y, split into 2 x n x n triangles, one atlas, UVs across [0, 1]. */
function lawn(size: number, n: number, y = 0, x0 = 0, z0 = 0, tilt = 0): GroundSoup {
  const pos: number[] = [];
  const uv: number[] = [];
  const h = size / n;
  const at = (i: number, j: number) => [x0 + i * h, y + tilt * i * h, z0 + j * h];
  const tex = (i: number, j: number) => [i / n, j / n];
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      // Counter-clockwise seen from above (+y up): a, c, b with z growing "down" the screen.
      for (const [p, q, r] of [
        [at(i, j), at(i, j + 1), at(i + 1, j)],
        [at(i + 1, j), at(i, j + 1), at(i + 1, j + 1)],
      ]) {
        pos.push(...p, ...q, ...r);
      }
      for (const [p, q, r] of [
        [tex(i, j), tex(i, j + 1), tex(i + 1, j)],
        [tex(i + 1, j), tex(i, j + 1), tex(i + 1, j + 1)],
      ]) {
        uv.push(...p, ...q, ...r);
      }
    }
  }
  return { pos: new Float32Array(pos), uv: new Float32Array(uv), atlas: new Uint8Array(pos.length / 9) };
}

/** Camera positions along a straight line at height y (xyz, flat). */
function line(x0: number, x1: number, z: number, y: number, step = 2): Float32Array {
  const out: number[] = [];
  for (let x = x0; x <= x1; x += step) out.push(x, y, z);
  return new Float32Array(out);
}

describe("rings", () => {
  it("holds each ring's value through its middle and is 0 past the last ring", () => {
    expect(ringAt(0).density).toBe(8);
    expect(ringAt(12.5).density).toBeCloseTo(8, 6);
    expect(ringAt(37.5).density).toBeCloseTo(6, 6);
    expect(ringAt(70).density).toBeCloseTo(3, 6);
    expect(ringAt(120).density).toBeCloseTo(1.5, 6);
    expect(ringAt(180).density).toBeCloseTo(0.8, 6);
    expect(ringAt(255).density).toBeCloseTo(0.4, 6);
    expect(ringAt(299).density).toBeCloseTo(0.4, 6);
    expect(ringAt(300).density).toBe(0);
    expect(ringAt(0).size).toBe(1);
    expect(ringAt(70).size).toBeCloseTo(1.3, 6);
    expect(ringAt(120).size).toBeCloseTo(1.7, 6);
    expect(ringAt(290).size).toBeCloseTo(2.6, 6);
  });

  it("averages about each ring's density over the ring", () => {
    let from = 0;
    for (const r of GRASS.rings) {
      let s = 0;
      const n = 200;
      for (let i = 0; i < n; i++) s += ringAt(from + ((i + 0.5) / n) * (r.to - from)).density;
      expect(Math.abs(s / n - r.density) / r.density).toBeLessThan(0.2);
      from = r.to;
    }
  });

  it("never rises with distance (no ring steps)", () => {
    let prev = Infinity;
    for (let d = 0; d < 310; d += 0.5) {
      const v = ringAt(d).density;
      expect(v).toBeLessThanOrEqual(prev + 1e-9);
      prev = v;
    }
  });

  it("scales by the tier and ends at its maxDist, thinning and shrinking toward it", () => {
    expect(densityAt(30, mid)).toBeCloseTo(ringAt(30).density * mid.share, 6);
    expect(densityAt(mid.maxDist - 1, mid)).toBeGreaterThan(0);
    expect(densityAt(mid.maxDist, mid)).toBe(0);
    expect(densityAt(100, high, 0.5)).toBeCloseTo(ringAt(100).density * 0.5, 6);
    expect(heightFade(100, high)).toBe(1);
    expect(heightFade(255, high)).toBe(1);
    expect(heightFade(277.5, high)).toBeCloseTo(0.5, 6);
    expect(heightFade(300, high)).toBe(0);
    expect(densityAt(300, high)).toBe(0);
    const half = (mid.maxDist * (1 + mid.fadeFrom)) / 2;
    expect(heightFade(mid.maxDist * mid.fadeFrom, mid)).toBe(1);
    expect(heightFade(half, mid)).toBeCloseTo(0.5, 6);
    // The density thins over the same stretch, so the grass has no end line.
    expect(densityAt(half, mid)).toBeCloseTo(ringAt(half).density * mid.share * 0.5, 6);
  });

  it("has a GLSL mirror built from the same control points", () => {
    const g = grassRingGlsl();
    expect(g).toContain("float sectGrassDensity( float d )");
    expect(g).toContain("float sectGrassSize( float d )");
    // Evaluate the generated chain in JS: same numbers as ringAt.
    const body = (name: string) => {
      const m = new RegExp(`float ${name}\\( float d \\) \\{([\\s\\S]*?)\\n\\}`).exec(g);
      return m![1]
        .replace(/float k/g, "let k")
        .replace(/mix\( k, ([^,]+), clamp\( (.+?), 0\.0, 1\.0 \) \)/g, "k + ($1 - k) * Math.min(Math.max($2, 0), 1)")
        .replace(/d < ([\d.]+) \? k : 0\.0/, "d < $1 ? k : 0");
    };
    const density = new Function("d", body("sectGrassDensity")) as (d: number) => number;
    const size = new Function("d", body("sectGrassSize")) as (d: number) => number;
    for (const d of [0, 10, 30, 47, 80, 110, 149, 151, 200, 260, 299, 301]) {
      expect(density(d)).toBeCloseTo(ringAt(d).density, 6);
      expect(size(d)).toBeCloseTo(ringAt(d).size, 6);
    }
  });
});

describe("tiers", () => {
  it("is off without postprocessing, mid without MSAA, and mid after any step down", () => {
    expect(grassTier(tierQuality("low"))).toBe("off");
    expect(grassTier(tierQuality("mid"))).toBe("mid");
    expect(grassTier(tierQuality("high", 1))).toBe("high");
    expect(grassTier(tierQuality("high", 1.5), 1.5)).toBe("high");
    expect(grassTier({ ...tierQuality("high", 1.5), maxDpr: 1.25 }, 1.5)).toBe("mid");
    expect(grassTier({ ...tierQuality("high", 1), msaa: 2 }, 1)).toBe("mid");
    expect(grassTier({ ...tierQuality("high", 1), bloom: false }, 1)).toBe("mid");
    expect(grassTier({ ...tierQuality("high", 1), maxFps: 30 }, 1)).toBe("mid");
  });
});

describe("byte packing", () => {
  it("round-trips sizes, leans, yaws and ranks within one step", () => {
    for (const m of [0.25, 0.3, 0.45, 0.6, 1.0, 1.8, 2.5]) expect(Math.abs(sizeOf(sizeByte(m)) - m)).toBeLessThanOrEqual(2.25 / 255 / 2 + 1e-9);
    expect(sizeByte(5)).toBe(255);
    expect(sizeByte(0)).toBe(0);
    expect(leanByte(75)).toBe(255);
    expect(leanByte(37.5)).toBe(128);
    expect(yawByte(0)).toBe(0);
    expect(yawByte(Math.PI)).toBe(128);
    expect(yawByte(-Math.PI / 2)).toBe(192);
    expect(yawByte(Math.PI * 2 - 1e-9)).toBe(0);
    for (const r of [0, 0.2, 1.5, 6, 7.99]) {
      const b = rankByte(r);
      expect(rankOf(b) - r).toBeLessThanOrEqual(RANK_STEP);
      expect(rankOf(b) - r).toBeGreaterThan(-RANK_STEP);
    }
    expect(rankByte(10)).toBe(255);
  });

  it("gives rim clumps their own draw distance", () => {
    expect(rimDrawDist(1.0)).toBe(200);
    expect(rimDrawDist(1.5)).toBe(300);
    expect(rimDrawDist(3)).toBe(450);
  });
});

describe("camera index", () => {
  it("finds the same nearest distance as a brute-force search", () => {
    const pts: number[] = [];
    let s = 1;
    const r = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
    // A curving path with some height.
    for (let i = 0; i < 400; i++) pts.push(Math.cos(i / 60) * 300 + r() * 3, 40 + Math.sin(i / 25) * 20, Math.sin(i / 60) * 300 + i * 0.5);
    const ix = camIndex(pts);
    for (let q = 0; q < 300; q++) {
      const x = (r() - 0.5) * 900;
      const y = r() * 100;
      const z = (r() - 0.5) * 900;
      let best = Infinity;
      for (let i = 0; i < pts.length; i += 3) best = Math.min(best, Math.hypot(pts[i] - x, pts[i + 1] - y, pts[i + 2] - z));
      const got = nearestCam(ix, x, y, z, 150);
      if (best <= 150) expect(got).toBeCloseTo(best, 4);
      else expect(got).toBe(Infinity);
    }
    expect(nearestCam(camIndex([]), 0, 0, 0, 100)).toBe(Infinity);
  });
});

describe("scatter", () => {
  it("places density x area tufts within 3 % (rank thinning included)", () => {
    // A 200 m lawn, the camera 1 m over its middle line: every ring is crossed.
    const soup = lawn(200, 40, 0, -100, -100);
    const cams = camIndex(line(-100, 100, 0, 1));
    const inst = scatterGround(soup, cams, { tier: high });
    // Expected: integrate the ring density over the lawn on a fine grid.
    let expected = 0;
    const g = 0.5;
    for (let x = -100 + g / 2; x < 100; x += g) for (let z = -100 + g / 2; z < 100; z += g) expected += densityAt(nearestCam(cams, x, 0, z, 200), high) * g * g;
    expect(Math.abs(inst.count - expected) / expected).toBeLessThan(0.03);
    // Thinning to any density d (rank below d) keeps d per m² where the candidates allow it.
    for (const d of [0.5, 1.5]) {
      let shown = 0;
      for (let i = 0; i < inst.count; i++) if (rankOf(inst.a[i * 4]) < d) shown++;
      let want = 0;
      for (let x = -100 + g / 2; x < 100; x += g) for (let z = -100 + g / 2; z < 100; z += g) want += Math.min(d, densityAt(nearestCam(cams, x, 0, z, 200), high)) * g * g;
      expect(Math.abs(shown - want) / want).toBeLessThan(0.03);
    }
  });

  it("is the same for the same input, and differs with the seed", () => {
    const soup = lawn(60, 6, 10, 0, 0);
    const cams = camIndex(line(0, 60, 30, 12));
    const a = scatterGround(soup, cams, { tier: high });
    const b = scatterGround(soup, cams, { tier: high });
    expect(a.count).toBeGreaterThan(1000);
    expect(b.count).toBe(a.count);
    expect([...b.pos]).toEqual([...a.pos]);
    expect([...b.a]).toEqual([...a.a]);
    expect([...b.b]).toEqual([...a.b]);
    expect([...b.uv]).toEqual([...a.uv]);
    const c = scatterGround(soup, cams, { tier: high, seed: 3 });
    expect([...c.pos.slice(0, 30)]).not.toEqual([...a.pos.slice(0, 30)]);
  });

  it("does not depend on triangle order", () => {
    const soup = lawn(40, 4, 0, 0, 0);
    const cams = camIndex(line(0, 40, 20, 3));
    const a = scatterGround(soup, cams, { tier: high });
    // Reverse the triangles.
    const n = soup.pos.length / 9;
    const rev: GroundSoup = { pos: new Float32Array(soup.pos.length), uv: new Float32Array(soup.uv.length), atlas: new Uint8Array(n) };
    for (let t = 0; t < n; t++) {
      rev.pos.set(soup.pos.subarray(t * 9, t * 9 + 9), (n - 1 - t) * 9);
      rev.uv.set(soup.uv.subarray(t * 6, t * 6 + 6), (n - 1 - t) * 6);
    }
    const b = scatterGround(rev, cams, { tier: high });
    expect(b.count).toBe(a.count);
    const key = (x: GrassInstances) =>
      Array.from({ length: x.count }, (_, i) => `${x.pos[i * 3].toFixed(4)},${x.pos[i * 3 + 2].toFixed(4)},${x.a[i * 4]}`).sort();
    expect(key(b)).toEqual(key(a));
  });

  it("puts each tuft on its triangle with the UV at its root", () => {
    const soup = lawn(20, 2, 5, 0, 0);
    const inst = scatterGround(soup, camIndex(line(0, 20, 10, 6)), { tier: high });
    expect(inst.count).toBeGreaterThan(100);
    for (let i = 0; i < inst.count; i++) {
      const x = inst.pos[i * 3];
      const z = inst.pos[i * 3 + 2];
      expect(inst.pos[i * 3 + 1]).toBeCloseTo(5, 4);
      // The lawn's UV is (x, z) / 20.
      expect(inst.uv[i * 2] / 65535).toBeCloseTo(x / 20, 3);
      expect(inst.uv[i * 2 + 1] / 65535).toBeCloseTo(z / 20, 3);
      const kind = inst.a[i * 4 + 3];
      expect(kind === KIND.tuft || kind === KIND.flower).toBe(true);
      expect(sizeOf(inst.a[i * 4 + 2])).toBeGreaterThanOrEqual(GRASS.tuft.height[0] - 0.01);
      expect(sizeOf(inst.a[i * 4 + 2])).toBeLessThanOrEqual(GRASS.tuft.height[1] + 0.01);
    }
  });

  it("rejects slopes steeper than 35 degrees and faces turned down", () => {
    const cams = camIndex(line(0, 20, 10, 3));
    // tan(35 deg) = 0.70: a 0.65 slope stays, a 0.75 slope goes.
    expect(scatterGround(lawn(20, 2, 0, 0, 0, 0.65), cams, { tier: high }).count).toBeGreaterThan(100);
    expect(scatterGround(lawn(20, 2, 0, 0, 0, 0.75), cams, { tier: high }).count).toBe(0);
    const down = lawn(20, 2, 0, 0, 0);
    for (let t = 0; t < down.pos.length / 9; t++) {
      // Swap two corners: the triangle faces down.
      const o = t * 9;
      for (let k = 0; k < 3; k++) [down.pos[o + 3 + k], down.pos[o + 6 + k]] = [down.pos[o + 6 + k], down.pos[o + 3 + k]];
    }
    expect(scatterGround(down, cams, { tier: high }).count).toBe(0);
  });

  it("skips ground beyond the tier's reach", () => {
    const soup = lawn(20, 2, 0, 1000, 1000);
    expect(scatterGround(soup, camIndex(line(0, 20, 0, 3)), { tier: high }).count).toBe(0);
    // 130 m away: high places tufts there, mid (110 m) does not.
    const near = lawn(20, 2, 0, 0, 130);
    const cams = camIndex(line(0, 20, 0, 0));
    expect(scatterGround(near, cams, { tier: high }).count).toBeGreaterThan(0);
    expect(scatterGround(near, cams, { tier: mid }).count).toBe(0);
  });

  it("drops tufts under a pond and beside water sheets", () => {
    const soup = lawn(40, 4, 0, 0, 0);
    const cams = camIndex(line(0, 40, 20, 4));
    const all = scatterGround(soup, cams, { tier: high });
    const pond = { level: 0.3, min: [10, -0.5, 10] as const, max: [20, 0.5, 20] as const };
    const dry = scatterGround(soup, cams, { tier: high, ponds: [pond] });
    expect(dry.count).toBeLessThan(all.count);
    for (let i = 0; i < dry.count; i++) expect(underPond([pond], dry.pos[i * 3], dry.pos[i * 3 + 1], dry.pos[i * 3 + 2])).toBe(false);
    // A pond whose water stands below the lawn changes nothing.
    expect(scatterGround(soup, cams, { tier: high, ponds: [{ ...pond, level: -0.4 }] }).count).toBe(all.count);
    // A stream sheet along x = 30, just above the ground.
    const sheet = sheetIndex(new Float32Array([29, 0.05, 0, 31, 0.05, 0, 29, 0.05, 40, 31, 0.05, 0, 31, 0.05, 40, 29, 0.05, 40]));
    const away = scatterGround(soup, cams, { tier: high, sheets: sheet });
    expect(away.count).toBeLessThan(all.count);
    for (let i = 0; i < away.count; i++) {
      const x = away.pos[i * 3];
      expect(x < 29 - GRASS.sheetM + 1e-3 || x > 31 + GRASS.sheetM - 1e-3).toBe(true);
    }
    expect(nearSheet(sheet, 30, 1.0, 20)).toBe(true);
    expect(nearSheet(sheet, 30, 2.0, 20)).toBe(false);
    expect(nearSheet(null, 30, 0, 20)).toBe(false);
  });

  it("puts about 3 % of tufts in flower, in drifts, with a rare spirit herb", () => {
    let flowers = 0;
    let spirits = 0;
    let n = 0;
    const colours = new Set<number>();
    for (let i = 0; i < 300; i++) {
      for (let j = 0; j < 300; j++) {
        const f = flowerAt(i * 4.7, j * 4.7, ((i * 7919 + j * 104729) % 10007) / 10007);
        n++;
        if (f > 0) flowers++;
        if (f === 5) spirits++;
        if (f > 0 && f < 5) colours.add(f);
      }
    }
    expect(flowers / n).toBeGreaterThan(0.02);
    expect(flowers / n).toBeLessThan(0.045);
    expect(spirits).toBeGreaterThan(0);
    expect(spirits / flowers).toBeLessThan(0.02);
    expect(colours.size).toBe(4);
  });

  it("yields while it works and returns the same lawn", () => {
    const soup = lawn(100, 20, 0, 0, 0);
    const cams = camIndex(line(0, 100, 50, 2));
    const it = scatterSteps(soup, cams, { tier: high });
    let yields = 0;
    let r = it.next();
    while (!r.done) {
      yields++;
      r = it.next();
    }
    expect(yields).toBeGreaterThan(1);
    expect(r.value.count).toBe(scatterGround(soup, cams, { tier: high }).count);
  });
});

describe("the bake at the roots", () => {
  const lawnC = [0.03, 0.05, 0.02];
  const soilC = [0.05, 0.03, 0.015];
  const black = [0.001, 0.0012, 0.0008];

  it("reads lawn green, soil brown and any black tap as covered", () => {
    expect(rootGreen(lawnC[0], lawnC[1], lawnC[2])).toBe(1);
    expect(rootGreen(soilC[0], soilC[1], soilC[2])).toBe(0);
    // Olive (red = green, hue 60) is lawn; dry yellow (hue about 50) is in between.
    expect(rootGreen(0.04, 0.04, 0.01)).toBe(1);
    const dry = rootGreen(0.05, 0.0415, 0.01);
    expect(dry).toBeGreaterThan(0.2);
    expect(dry).toBeLessThan(0.8);
    expect(rootTexel(lawnC, lawnC, lawnC)[3]).toBe(255);
    expect(rootTexel(soilC, soilC, soilC)[3]).toBe(64);
    expect(rootTexel(lawnC, black, lawnC)[3]).toBe(0);
    expect(rootTexel(lawnC, lawnC, black)[3]).toBe(0);
    // sqrt(linear): 0.04 -> 0.2 -> 51.
    expect(rootTexel([0.04, 0.04, 0.04], [0.05, 0.05, 0.05], [0.03, 0.03, 0.03]).slice(0, 3)).toEqual([51, 51, 51]);
    // A root in a dark pocket (a path's dim rim, under a stepping stone) is dropped, whichever tap
    // shows the lit ground around it; one in a shadow (a third as bright or more) is kept.
    const pit = [0.006, 0.005, 0.004];
    expect(rootTexel(pit, lawnC, pit)[3]).toBe(0);
    expect(rootTexel(pit, pit, pit, pit, lawnC)[3]).toBe(0);
    expect(rootTexel(pit, pit, pit)[3]).toBeGreaterThan(0);
    const shade = rootTexel([0.012, 0.018, 0.008], lawnC, lawnC, lawnC, lawnC);
    expect(shade[3]).toBe(255);
    // ...lifted out of the contact shadow to 0.6 of the ground around it: 0.6 x 0.05 = 0.03 green.
    expect(shade[1]).toBe(Math.round(Math.sqrt(0.03) * 255));
    expect(shade[0]).toBe(Math.round(Math.sqrt(0.02) * 255));
    expect(rootTexel(lawnC, lawnC, lawnC).slice(0, 3)).toEqual(lawnC.map((v) => Math.round(Math.sqrt(v) * 255)));
  });

  it("drops covered roots, thins tufts on soil and keeps the fringe as it is", () => {
    const soup = lawn(40, 4, 0, 0, 0);
    const inst = scatterGround(soup, camIndex(line(0, 40, 20, 2)), { tier: high });
    const n = inst.count;
    // Thirds: lawn, soil, covered.
    const t = [rootTexel(lawnC, lawnC, lawnC), rootTexel(soilC, soilC, soilC), rootTexel(lawnC, black, lawnC)];
    const texels = new Uint8Array(n * 4);
    for (let i = 0; i < n; i++) texels.set(t[i % 3], i * 4);
    const r = rootInstances(inst, texels);
    let lawnN = 0;
    let soilN = 0;
    for (let i = 0; i < r.count; i++) {
      expect(r.col[i * 4 + 3]).toBeGreaterThan(0);
      if (r.col[i * 4 + 3] === 255) lawnN++;
      else soilN++;
    }
    const third = n / 3;
    expect(Math.abs(lawnN - third) / third).toBeLessThan(0.02);
    // Soil tufts that could never show (rank / keep past the densest ring) are gone.
    expect(soilN).toBeLessThan(third);
    expect(soilN).toBeGreaterThan(third * GRASS.green.soilKeep * 0.9);
    // Soil: the share of tufts shown at any density is soilKeep (ranks divided by it).
    for (const d of [1, 3, 6]) {
      let lawnShown = 0;
      let soilShown = 0;
      for (let i = 0; i < r.count; i++) {
        if (rankOf(r.a[i * 4]) >= d) continue;
        if (r.col[i * 4 + 3] === 255) lawnShown++;
        else soilShown++;
      }
      expect(Math.abs(soilShown / lawnShown - GRASS.green.soilKeep)).toBeLessThan(0.05);
    }
    // The fringe keeps rank 0 on soil.
    const fringe: GrassInstances = { count: 1, pos: new Float32Array(3), uv: new Uint16Array(2), a: new Uint8Array([0, 1, 100, KIND.fringe]), b: new Uint8Array(4), atlas: new Uint8Array(1) };
    const f1 = rootInstances(fringe, Uint8Array.from(rootTexel(soilC, soilC, soilC)));
    expect(f1.count).toBe(1);
    expect(f1.a[0]).toBe(0);
    expect(rootInstances(fringe, Uint8Array.from(rootTexel(soilC, black, soilC))).count).toBe(0);
  });
});

describe("cells", () => {
  const soup = lawn(160, 16, 0, -80, -80);
  const cams = camIndex(line(-80, 80, 0, 2));
  const tufts = scatterGround(soup, cams, { tier: high });
  // Two rim clumps and a fringe instance, as grass-edge.ts makes them.
  const extra: GrassInstances = {
    count: 3,
    pos: new Float32Array([5, 0, 5, 6, 0, 5, 7, 0, 5]),
    uv: new Uint16Array([1, 2, 3, 4, 5, 6]),
    a: new Uint8Array([0, 9, sizeByte(1.0), KIND.rim, 0, 9, sizeByte(1.8), KIND.rim, 0, 9, sizeByte(0.7), KIND.fringe]),
    b: new Uint8Array([leanByte(10), 0, 0, 0, leanByte(10), 64, 0, 0, leanByte(60), 128, 0, 0]),
    atlas: new Uint8Array([0, 0, 0]),
  };
  // Every root open lawn (the GPU read's bytes for a green texel).
  const merged = mergeInstances([tufts, extra]);
  const lawnTexel = rootTexel([0.03, 0.05, 0.02], [0.03, 0.05, 0.02], [0.03, 0.05, 0.02]);
  const all = rootInstances(merged, Uint8Array.from({ length: merged.count * 4 }, (_, i) => lawnTexel[i % 4]));
  const cells = buildCells(all);

  it("keeps every instance exactly once, with its own data", () => {
    expect(cells.reduce((s, c) => s + c.count, 0)).toBe(all.count);
    // Every instance's 24 bytes as one number; the sorted lists match.
    const key = (pos: Float32Array, a: Uint8Array, b: Uint8Array, col: Uint8Array, i: number) => {
      let h = 0;
      for (const v of [pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2], ...a.subarray(i * 4, i * 4 + 4), ...b.subarray(i * 4, i * 4 + 4), ...col.subarray(i * 4, i * 4 + 4)]) {
        h = (Math.imul(h ^ Math.round(v * 4096), 0x9e3779b1) + 0x632be5ab) >>> 0;
      }
      return h;
    };
    const want = Float64Array.from({ length: all.count }, (_, i) => key(all.pos, all.a, all.b, all.col, i)).sort();
    const got: number[] = [];
    let outside = 0;
    for (const c of cells) {
      for (let i = 0; i < c.count; i++) {
        got.push(key(c.pos, c.a, c.b, c.col, i));
        for (let ax = 0; ax < 3; ax++) if (c.pos[i * 3 + ax] < c.min[ax] || c.pos[i * 3 + ax] > c.max[ax]) outside++;
      }
    }
    expect(Float64Array.from(got).sort()).toEqual(want);
    expect(outside).toBe(0);
  });

  it("sorts tuft cells by rank and rim cells by reach", () => {
    for (const c of cells) {
      if (c.layer === 0) {
        for (let i = 1; i < c.count; i++) expect(c.a[i * 4]).toBeGreaterThanOrEqual(c.a[(i - 1) * 4]);
        expect(c.below![256]).toBe(c.count);
      } else {
        expect(c.reach!.length).toBe(c.count);
        for (let i = 1; i < c.count; i++) expect(c.reach![i]).toBeLessThanOrEqual(c.reach![i - 1]);
      }
    }
    const rim = cells.filter((c) => c.layer === 1);
    expect(rim.reduce((s, c) => s + c.count, 0)).toBe(2);
  });

  it("counts what a cell draws at a distance", () => {
    for (const c of cells.filter((x) => x.layer === 0)) {
      for (const dist of [0, 30, 80, 140, 160]) {
        const d = densityAt(dist, high);
        let want = 0;
        for (let i = 0; i < c.count; i++) if (rankOf(c.a[i * 4]) < d) want++;
        expect(cellCount(c, dist, high)).toBe(want);
      }
    }
    // The fringe (rank 0) shows nearly to the tier's end; rim clumps to their own reach.
    const fringeCell = cells.find((c) => c.layer === 0 && [...Array(c.count).keys()].some((i) => c.a[i * 4 + 3] === KIND.fringe))!;
    expect(cellCount(fringeCell, 140, high)).toBeGreaterThan(0);
    const rim = cells.find((c) => c.layer === 1)!;
    expect(cellCount(rim, 150, high)).toBe(2);
    expect(cellCount(rim, 250, high)).toBe(1);
    expect(cellCount(rim, 400, high)).toBe(0);
  });

  it("puts tufts that are never near the flight in larger cells of their own", () => {
    const wide = lawn(320, 16, 0, -160, -160);
    const camPts = line(-10, 10, 0, 2);
    const tier = { ...high, share: 0.2, maxDist: 170 };
    const inst = scatterGround(wide, camIndex(camPts), { tier });
    const ix = camIndex(camPts);
    const piece = Math.sqrt(GRASS.pieceM2) * 2;
    let far = 0;
    for (let i = 0; i < inst.count; i++) {
      const d = nearestCam(ix, inst.pos[i * 3], inst.pos[i * 3 + 1], inst.pos[i * 3 + 2], 400);
      if (inst.b[i * 4 + 3] === 1) {
        far++;
        expect(d).toBeGreaterThan(GRASS.farCell.fromM - piece);
      } else expect(d).toBeLessThan(GRASS.farCell.fromM + piece);
    }
    expect(far).toBeGreaterThan(100);
    const rooted = rootInstances(inst, Uint8Array.from({ length: inst.count * 4 }, (_, i) => lawnTexel[i % 4]));
    for (const c of buildCells(rooted)) {
      const flags = new Set(Array.from({ length: c.count }, (_, i) => c.b[i * 4 + 3]));
      expect(flags.size).toBe(1);
      const m = flags.has(1) ? GRASS.cellM * GRASS.farCell.scale : GRASS.cellM;
      let x0 = Infinity, x1 = -Infinity;
      for (let i = 0; i < c.count; i++) {
        x0 = Math.min(x0, c.pos[i * 3]);
        x1 = Math.max(x1, c.pos[i * 3]);
      }
      expect(Math.floor(x0 / m)).toBe(Math.floor(x1 / m));
    }
  });

  it("measures the distance to a cell's box", () => {
    const c = cells[0];
    expect(cellDistance(c, c.center[0], c.center[1], c.center[2])).toBe(0);
    expect(cellDistance(c, c.max[0] + 10, c.center[1], c.center[2])).toBeCloseTo(10, 6);
  });

  it("scales densities down evenly to fit the tufts budget", () => {
    const tuftCells = cells.filter((c) => c.layer === 0);
    const dists = tuftCells.map((c) => cellDistance(c, 0, 2, 0));
    const total = tuftCells.reduce((s, c, i) => s + cellCount(c, dists[i], high), 0);
    if (total <= high.maxTufts) expect(fitBudget(tuftCells, dists, high)).toBe(1);
    else expect(fitBudget(tuftCells, dists, high)).toBeLessThan(1);
    expect(fitBudget(tuftCells, dists, { ...high, maxTufts: total })).toBe(1);
    const tight = { ...high, maxTufts: Math.floor(total / 3) };
    const s = fitBudget(tuftCells, dists, tight);
    expect(s).toBeLessThan(0.4);
    expect(s).toBeGreaterThan(0.25);
    const drawn = tuftCells.reduce((sum, c, i) => sum + cellCount(c, dists[i], tight, s), 0);
    expect(drawn).toBeLessThanOrEqual(tight.maxTufts);
    expect(drawn).toBeGreaterThan(tight.maxTufts * 0.9);
  });
});
