import { describe, expect, it } from "vitest";
import { EDGE, EDGE_PLAIN, EDGE_RIM, fringeInstances, grassEdges, grassEdgeSteps, leanDir, rimClumps } from "./grass-edge";
import { KIND, leanByte, sizeOf, type GrassInstances, type GroundSoup, type RockSoup } from "./grass";

type P3 = [number, number, number];

/** Triangle soups built quad by quad; ground UV is (x, z) / 100. */
class Soup {
  pos: number[] = [];
  uv: number[] = [];
  /** Two triangles, both facing the side the corners turn left around (a, b, c, d in order). */
  quad(a: P3, b: P3, c: P3, d: P3): this {
    for (const p of [a, b, d, d, b, c]) {
      this.pos.push(...p);
      this.uv.push(p[0] / 100, p[2] / 100);
    }
    return this;
  }
  ground(atlas = 0): GroundSoup {
    return { pos: new Float32Array(this.pos), uv: new Float32Array(this.uv), atlas: new Uint8Array(this.pos.length / 9).fill(atlas) };
  }
  rock(): RockSoup {
    return { pos: new Float32Array(this.pos) };
  }
}

/** A level lawn at height y over [x0, x1] x [z0, z1] in cells of `step` m, facing up. */
function lawn(s: Soup, x0: number, x1: number, z0: number, z1: number, y: number, step: number): Soup {
  for (let x = x0; x < x1 - 1e-6; x += step) {
    for (let z = z0; z < z1 - 1e-6; z += step) {
      const xa = Math.min(x + step, x1), za = Math.min(z + step, z1);
      s.quad([x, y, z], [x, y, za], [xa, y, za], [xa, y, z]);
    }
  }
  return s;
}

/** A vertical rock face along (x0, z0)-(x1, z1) from y0 to y1, split every `step` m. */
function face(s: Soup, x0: number, z0: number, x1: number, z1: number, y0: number, y1: number, step: number): Soup {
  const n = Math.max(1, Math.round(Math.hypot(x1 - x0, z1 - z0) / step));
  for (let i = 0; i < n; i++) {
    const a = i / n, b = (i + 1) / n;
    const xa = x0 + (x1 - x0) * a, za = z0 + (z1 - z0) * a, xb = x0 + (x1 - x0) * b, zb = z0 + (z1 - z0) * b;
    s.quad([xa, y1, za], [xb, y1, zb], [xb, y0, zb], [xa, y0, za]);
  }
  return s;
}

/** A plateau: a lawn at y = 10 over [0, L]^2 with cliff walls down to y = 0 on every side. */
function plateau(L: number, step: number) {
  const g = lawn(new Soup(), 0, L, 0, L, 10, step);
  const r = new Soup();
  face(r, 0, 0, L, 0, 0, 10, step);
  face(r, L, 0, L, L, 0, 10, step);
  face(r, L, L, 0, L, 0, 10, step);
  face(r, 0, L, 0, 0, 0, 10, step);
  return { ground: g.ground(), rock: r.rock() };
}

const cams = (...p: P3[]) => new Float32Array(p.flat());

/** Instance i decoded. */
function at(inst: GrassInstances, i: number) {
  const yaw = (inst.b[i * 4 + 1] / 256) * Math.PI * 2;
  return {
    x: inst.pos[i * 3],
    y: inst.pos[i * 3 + 1],
    z: inst.pos[i * 3 + 2],
    u: inst.uv[i * 2] / 65535,
    v: inst.uv[i * 2 + 1] / 65535,
    rank: inst.a[i * 4],
    size: sizeOf(inst.a[i * 4 + 2]),
    kind: inst.a[i * 4 + 3],
    leanB: inst.b[i * 4],
    dir: leanDir(yaw),
  };
}

const all = (inst: GrassInstances) => Array.from({ length: inst.count }, (_, i) => at(inst, i));

describe("grassEdges", () => {
  it("finds the four rims of a plateau, and no edge inside it", () => {
    const { ground, rock } = plateau(40, 2);
    const e = grassEdges(ground, rock);
    expect(e.stats.openM).toBeCloseTo(160, 3);
    expect(e.stats.rimSharedM).toBeCloseTo(160, 3);
    expect(e.stats.edgeM + e.stats.unbackedM + e.stats.steepM).toBeCloseTo(0, 6);
    expect([...e.cls].every((c) => c === EDGE_RIM)).toBe(true);
  });

  it("joins a plateau's two pieces across an 8 cm gap, but not a 30 cm one", () => {
    const split = (gap: number) => {
      const g = lawn(new Soup(), 0, 20, 0, 40, 10, 2);
      const g2 = lawn(new Soup(), 20 + gap, 40 + gap, 0, 40, 10, 2);
      g.pos.push(...g2.pos);
      g.uv.push(...g2.uv);
      const r = new Soup();
      face(r, 0, 0, 20, 0, 0, 10, 2);
      face(r, 20 + gap, 0, 40 + gap, 0, 0, 10, 2);
      face(r, 40 + gap, 0, 40 + gap, 40, 0, 10, 2);
      face(r, 40 + gap, 40, 20 + gap, 40, 0, 10, 2);
      face(r, 20, 40, 0, 40, 0, 10, 2);
      face(r, 0, 40, 0, 0, 0, 10, 2);
      return grassEdges(g.ground(), r.rock()).stats;
    };
    const welded = split(0.08);
    expect(welded.openM).toBeCloseTo(160, 0);
    expect(welded.unbackedM).toBe(0);
    // Apart, each piece's side of the gap is open; no rock backs it, so it gets no grass either.
    const apart = split(0.3);
    expect(apart.openM).toBeCloseTo(160 + 80, 0);
    expect(apart.unbackedM).toBeCloseTo(80, 0);
  });

  it("drops edges no rock backs: a lawn that just ends (an area's cut line, a lawn step)", () => {
    const e = grassEdges(lawn(new Soup(), 0, 30, 0, 30, 5, 3).ground(), { pos: new Float32Array(0) });
    expect(e.count).toBe(0);
    expect(e.stats.unbackedM).toBeCloseTo(120, 3);
  });

  it("finds a rim from rock just outside that shares no corner (a moved border)", () => {
    const g = lawn(new Soup(), 0, 20, 0, 20, 10, 2);
    const r = face(new Soup(), 0, -0.4, 20, -0.4, 0, 9.95, 2.5);
    const e = grassEdges(g.ground(), r.rock());
    expect(e.stats.rimNearM).toBeCloseTo(20, 3);
    expect(e.stats.rimSharedM).toBe(0);
    // ...but not where the lawn steps down onto more ground right past that rock (a boulder by a step).
    lawn(g, -10, 30, -10, -0.1, 9.85, 2);
    expect(grassEdges(g.ground(), r.rock()).stats.rimNearM).toBe(0);
  });

  it("calls a gentle rock shoulder a rim when a drop follows it, and plain when the slope goes on", () => {
    // Lawn to z = 0, then rock falling 1.2 m over 2 m (31 degrees), then either a cliff or more of the same.
    const shoulder = (cliff: boolean) => {
      const g = lawn(new Soup(), 0, 20, 0, 20, 10, 2);
      const r = new Soup();
      for (let x = 0; x < 20; x += 2) {
        r.quad([x, 10, 0], [x + 2, 10, 0], [x + 2, 8.8, -2], [x, 8.8, -2]);
        if (cliff) r.quad([x, 8.8, -2], [x + 2, 8.8, -2], [x + 2, -20, -2], [x, -20, -2]);
        else r.quad([x, 8.8, -2], [x + 2, 8.8, -2], [x + 2, 7.6, -4], [x, 7.6, -4]);
      }
      return grassEdges(g.ground(), r.rock()).stats;
    };
    expect(shoulder(true).rimLipM).toBeCloseTo(20, 3);
    expect(shoulder(false).rimLipM).toBe(0);
    expect(shoulder(false).edgeM).toBeCloseTo(20, 3);
  });

  it("runs in slices, and keeps the result for the instance builders", () => {
    const { ground, rock } = plateau(400, 1);
    const it = grassEdgeSteps(ground, rock);
    let yields = 0;
    let r = it.next();
    for (; !r.done; r = it.next()) yields++;
    expect(yields).toBeGreaterThan(10);
    expect(r.value.stats.rimSharedM).toBeCloseTo(1600, 1);
    // The same object back: fringeInstances and rimClumps do not work it out again.
    expect(grassEdges(ground, rock)).toBe(r.value);
  });

  it("skips ground steeper than minNy", () => {
    const g = new Soup().quad([0, 0, 0], [0, 10, 3], [10, 10, 3], [10, 0, 0]);
    const e = grassEdges(g.ground(), face(new Soup(), 0, 0, 10, 0, -10, 0, 2).rock());
    expect(e.count).toBe(0);
    expect(e.stats.steepM).toBeGreaterThan(0);
  });
});

describe("fringeInstances", () => {
  it("hangs a fringe over all four rims of a plateau, about 3 per metre, leaning out and down", () => {
    const { ground, rock } = plateau(40, 2);
    const f = fringeInstances(ground, rock, cams([20, 30, 20]));
    const list = all(f);
    expect(f.count / 160).toBeGreaterThan(2.85);
    expect(f.count / 160).toBeLessThan(3.15);
    const sides = [0, 0, 0, 0];
    for (const p of list) {
      expect(p.kind).toBe(KIND.fringe);
      expect(p.rank).toBe(0);
      expect(p.y).toBeCloseTo(10, 4);
      expect(p.size).toBeGreaterThanOrEqual(EDGE.fringe.size[0] - 0.01);
      expect(p.size).toBeLessThanOrEqual(EDGE.fringe.size[1] + 0.01);
      expect(p.leanB).toBeGreaterThanOrEqual(leanByte(EDGE.rimLean[0]));
      expect(p.leanB).toBeLessThanOrEqual(leanByte(EDGE.rimLean[1]));
      // Leaning out (within the jitter) over a rim it is rooted at most `inset` inside of.
      const d = [p.z, 40 - p.x, 40 - p.z, p.x];
      const outs = [[0, -1], [1, 0], [0, 1], [-1, 0]];
      const k = outs.findIndex((o) => p.dir[0] * o[0] + p.dir[1] * o[1] > Math.cos(((EDGE.yawJitter + 2) * Math.PI) / 180));
      expect(k).toBeGreaterThanOrEqual(0);
      sides[k]++;
      expect(d[k]).toBeGreaterThanOrEqual(0);
      expect(d[k]).toBeLessThanOrEqual(EDGE.inset + 1e-3);
      // UV from the triangle under the root.
      expect(p.u).toBeCloseTo(p.x / 100, 4);
      expect(p.v).toBeCloseTo(p.z / 100, 4);
    }
    for (const n of sides) expect(n).toBeGreaterThan(110);
  });

  it("thins to 1.5 per metre farther than 50 m, and stops at 150 m", () => {
    const { ground, rock } = plateau(40, 2);
    expect(fringeInstances(ground, rock, cams([20, 110, 20])).count / 160).toBeCloseTo(1.5, 1);
    expect(fringeInstances(ground, rock, cams([20, 170, 20])).count).toBe(0);
  });

  it("puts no fringe along the seam of a plateau built in two pieces (quantised on their own grids)", () => {
    const g = lawn(new Soup(), 0, 20, 0, 40, 10, 2);
    const g2 = lawn(new Soup(), 20, 40, 0, 40, 10, 4);
    // The second piece: coarser triangles (T-junctions along the seam), shifted 2 cm (its own grid).
    g.pos.push(...g2.pos.map((v, i) => v + [0.013, 0.007, -0.011][i % 3]));
    g.uv.push(...g2.uv);
    const { rock } = plateau(40, 2);
    const list = all(fringeInstances(g.ground(), rock, cams([20, 30, 20])));
    expect(list.length).toBeGreaterThan(400);
    expect(list.filter((p) => Math.abs(p.x - 20) < 1 && p.z > 1 && p.z < 39)).toHaveLength(0);
  });

  it("gives a lawn at the foot of a rock wall a short fringe leaning away from the wall", () => {
    const g = lawn(new Soup(), 0, 30, 0, 30, 0, 3);
    const r = face(new Soup(), 30, 30, 0, 30, 0, 20, 3);
    const list = all(fringeInstances(g.ground(), r.rock(), cams([15, 20, -10])));
    expect(list.length).toBeGreaterThan(80);
    for (const p of list) {
      expect(p.z).toBeGreaterThan(29.7);
      expect(p.size).toBeLessThanOrEqual(EDGE.fringe.edgeSize[1] + 0.01);
      expect(p.leanB).toBeLessThanOrEqual(leanByte(EDGE.edgeLean[1]));
      expect(p.dir[1]).toBeLessThan(-0.9);
    }
    expect(grassEdges(g.ground(), r.rock()).cls.every((c) => c === EDGE_PLAIN)).toBe(true);
  });

  it("leaves out roots under a pond", () => {
    const { ground, rock } = plateau(40, 2);
    const ponds = [{ level: 10.5, min: [-1, 8, -1] as const, max: [41, 11, 10] as const }];
    const list = all(fringeInstances(ground, rock, cams([20, 30, 20]), { ponds }));
    expect(list.length).toBeGreaterThan(250);
    expect(list.filter((p) => p.z < 10)).toHaveLength(0);
  });

  it("gives the same instances for the same meshes, in any triangle order", () => {
    const { ground, rock } = plateau(40, 2);
    const c = cams([20, 30, 20]);
    const a = fringeInstances(ground, rock, c);
    expect(fringeInstances({ ...ground }, { ...rock }, c)).toEqual(a);
    // Reversed triangle order: the same set of roots.
    const n = ground.pos.length / 9;
    const rev: GroundSoup = { pos: new Float32Array(ground.pos.length), uv: new Float32Array(ground.uv.length), atlas: ground.atlas.slice() };
    for (let t = 0; t < n; t++) {
      rev.pos.set(ground.pos.subarray(t * 9, t * 9 + 9), (n - 1 - t) * 9);
      rev.uv.set(ground.uv.subarray(t * 6, t * 6 + 6), (n - 1 - t) * 6);
    }
    const key = (inst: GrassInstances) =>
      all(inst)
        .map((p) => `${p.x.toFixed(3)},${p.z.toFixed(3)},${p.size.toFixed(3)}`)
        .sort();
    expect(key(fringeInstances(rev, rock, c))).toEqual(key(a));
  });
});

describe("rimClumps", () => {
  // A 200 m mesa seen from 120 m over its middle: every rim point is 156-184 m from the camera.
  const mesa = plateau(200, 10);
  const far = cams([100, 130, 100]);

  it("sets bushes along far rims, one per 5 m less the gaps, in their size and lean", () => {
    // The gaps come from noise: average over six mesas in different places.
    let kept = 0;
    for (let k = 0; k < 6; k++) {
      const shift = (s: Float32Array) => s.map((v, i) => (i % 3 === 0 ? v + k * 1000 : v));
      const g: GroundSoup = { ...mesa.ground, pos: shift(mesa.ground.pos) };
      kept += rimClumps(g, { pos: shift(mesa.rock.pos) }, cams([100 + k * 1000, 130, 100])).count;
    }
    expect(kept / (6 * (800 / EDGE.rimClump.everyM))).toBeCloseTo(1 - EDGE.rimClump.gap, 1);
    const list = all(rimClumps(mesa.ground, mesa.rock, far));
    for (const p of list) {
      expect(p.kind).toBe(KIND.rim);
      expect(p.rank).toBe(0);
      expect(p.size).toBeGreaterThanOrEqual(EDGE.rimClump.size[0] - 0.01);
      expect(p.size).toBeLessThanOrEqual(EDGE.rimClump.size[1] + 0.01);
      expect(p.leanB).toBe(leanByte(EDGE.rimClump.lean));
    }
    // Clustered: some stretch of rim more than 15 m long has none.
    const south = list.filter((p) => p.z < 1).map((p) => p.x).sort((a, b) => a - b);
    const gaps = south.slice(1).map((x, i) => x - south[i]);
    expect(Math.max(...gaps, 0)).toBeGreaterThan(15);
  });

  it("puts none within 100 m of the path, and none farther than a clump of its size is drawn", () => {
    // From just off the south rim: the near rims get none (the fringe covers them), the far ones do.
    const near = all(rimClumps(mesa.ground, mesa.rock, cams([100, 20, -20])));
    expect(near.length).toBeGreaterThan(0);
    for (const p of near) expect(Math.hypot(p.x - 100, p.y - 20, p.z + 20)).toBeGreaterThan(94);
    // 260-290 m out: only clumps of 1.3 m and up are drawn that far (size x 200 m).
    const list = all(rimClumps(mesa.ground, mesa.rock, cams([100, 250, 100])));
    expect(list.length).toBeGreaterThan(0);
    for (const p of list) expect(p.size * 200 + 6).toBeGreaterThan(Math.hypot(p.x - 100, p.y - 250, p.z - 100));
  });
});
