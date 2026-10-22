import { describe, expect, it } from "vitest";
import type { Vec3, Waterfall } from "./types";
import {
  connectedPieces,
  FALL,
  fallDistance,
  fallGlsl,
  fallPickQuads,
  fallSeconds,
  fallSpeed,
  fxAssetUrl,
  lipStart,
  packWetFalls,
  rayQuad,
  selectWetFalls,
  sheetFallAttribute,
  STREAM,
  streamFlow,
  WET,
  wetAmount,
  wetArrays,
  wetDown,
  wetFalls,
  wetRockGlsl,
  type WetFall,
} from "./waterfall";

describe("fall physics", () => {
  it("leaves the lip at the lip speed and speeds up all the way down, below the terminal speed", () => {
    expect(fallSpeed(0)).toBeCloseTo(FALL.lipSpeed, 6);
    let last = 0;
    for (const d of [0, 1, 5, 20, 46.5, 100, 250, 600]) {
      const v = fallSpeed(d);
      expect(v).toBeGreaterThan(last);
      expect(v).toBeLessThan(FALL.terminal);
      last = v;
    }
  });

  it("takes the abode's 46.5 m drop in about 3.1 s (15 m/s on average, not the old 50)", () => {
    const t = fallSeconds(46.5);
    expect(t).toBeGreaterThan(2.9);
    expect(t).toBeLessThan(3.3);
    expect(46.5 / t).toBeGreaterThan(13);
    expect(46.5 / t).toBeLessThan(17);
    // A 250 m range fall: drag keeps it under 30 m/s on average.
    expect(250 / fallSeconds(250)).toBeLessThan(30);
  });

  it("matches drag-free kinematics near the lip", () => {
    for (const d of [0.25, 1, 3]) {
      const free = (Math.sqrt(FALL.lipSpeed ** 2 + 2 * FALL.g * d) - FALL.lipSpeed) / FALL.g;
      expect(fallSeconds(d)).toBeCloseTo(free, 2);
    }
    expect(fallSeconds(0)).toBe(0);
    expect(fallSeconds(-3)).toBe(0);
    expect(lipStart()).toBeCloseTo(FALL.lipSpeed ** 2 / (2 * FALL.g), 2);
  });

  it("turns seconds back into metres (Blender's UV1 seconds)", () => {
    for (const d of [0, 0.5, 4, 46.5, 180, 320]) expect(fallDistance(fallSeconds(d))).toBeCloseTo(d, 6);
    expect(fallDistance(-1)).toBeCloseTo(0, 9);
  });

  it("puts the same maths in the shader", () => {
    const g = fallGlsl();
    expect(g).toContain("#define SECT_FALL_VT 38.0");
    expect(g).toContain(`#define SECT_FALL_S0 ${lipStart().toPrecision(8)}`);
    expect(g).toContain("float sectFallSeconds( float d )");
    expect(g).toContain("float sectFallSpeed( float d )");
    expect(g).toContain("#define SECT_STREAM_SPEED 3.0");
  });
});

describe("fxAssetUrl", () => {
  it("finds the fx folder beside the set's folder", () => {
    expect(fxAssetUrl("/sect/full", "strands.webp")).toBe("/sect/fx/strands.webp");
    expect(fxAssetUrl("/sect/before/", "strands.webp")).toBe("/sect/fx/strands.webp");
    expect(fxAssetUrl("https://cdn.example/x/sect/full", "foam.webp")).toBe("https://cdn.example/x/sect/fx/foam.webp");
  });
});

/** A rows x cols grid sheet hanging from (x0, top, z) across +x, `height` m tall; `vAtLip` is v at the top row. */
function sheet(x0: number, top: number, width: number, height: number, vAtLip: 0 | 1, rows = 6, cols = 3) {
  const pos: number[] = [];
  const uv: number[] = [];
  for (let r = 0; r <= rows; r++) {
    for (let c = 0; c <= cols; c++) {
      const s = r / rows;
      pos.push(x0 + (c / cols) * width * (1 + 0.3 * s), top - s * height, 0.5 * s * s);
      uv.push(c / cols, vAtLip === 1 ? 1 - s : s);
    }
  }
  const idx: number[] = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const a = r * (cols + 1) + c;
      idx.push(a, a + cols + 1, a + 1, a + 1, a + cols + 1, a + cols + 2);
    }
  }
  return { pos, uv, idx };
}

function merge(...parts: { pos: number[]; uv: number[]; idx: number[] }[]) {
  const pos: number[] = [];
  const uv: number[] = [];
  const idx: number[] = [];
  for (const p of parts) {
    const base = pos.length / 3;
    pos.push(...p.pos);
    uv.push(...p.uv);
    idx.push(...p.idx.map((i) => i + base));
  }
  return { positions: new Float32Array(pos), uvs: new Float32Array(uv), index: new Uint32Array(idx) };
}

describe("connectedPieces", () => {
  it("splits a merged mesh into its sheets", () => {
    const m = merge(sheet(0, 10, 2, 5, 0), sheet(50, 30, 4, 20, 1));
    const pieces = connectedPieces(m.positions.length / 3, m.index);
    expect(pieces.map((p) => p.length).sort()).toEqual([28, 28]);
    expect(connectedPieces(6, null)).toHaveLength(2);
  });
});

describe("sheetFallAttribute", () => {
  it("measures each sheet in metres from world height, whichever way its v runs", () => {
    const m = merge(sheet(0, 10, 2, 5, 0), sheet(50, 30, 4, 20, 1));
    const a = sheetFallAttribute({ positions: m.positions, uvs: m.uvs, index: m.index });
    const n = m.positions.length / 3;
    for (let i = 0; i < n; i++) {
      const first = i < 28;
      const top = first ? 10 : 30;
      expect(a[i * 4 + 1]).toBeCloseTo(top - m.positions[i * 3 + 1], 4);
      expect(a[i * 4 + 2]).toBeCloseTo(first ? 5 : 20, 4);
      expect(a[i * 4 + 3]).toBeCloseTo(first ? 2 : 4, 4);
      expect(a[i * 4]).toBeCloseTo((m.uvs[i * 2] - 0.5) * (first ? 2 : 4), 4);
    }
  });

  it("measures a stream along its flow from the head (the higher end), its z the share to its foot", () => {
    // Two-vertex rows down a 3-4-5 slope: 10 rows of 5 m.
    const pos: number[] = [];
    const uv: number[] = [];
    const idx: number[] = [];
    for (let r = 0; r <= 10; r++) {
      pos.push(r * 4, -r * 3, 0, r * 4, -r * 3, 2);
      uv.push(0, r / 10, 1, r / 10);
      if (r < 10) idx.push(r * 2, r * 2 + 1, r * 2 + 2, r * 2 + 1, r * 2 + 3, r * 2 + 2);
    }
    const a = sheetFallAttribute({ positions: pos, uvs: uv, index: idx, stream: true });
    for (let r = 0; r <= 10; r++) {
      expect(a[r * 8 + 1]).toBeCloseTo(r * 5, 4);
      // z < 0 marks a stream: -(1 + share of its length from the head), so the shader fades the foot.
      expect(a[r * 8 + 2]).toBeCloseTo(-(1 + r / 10), 5);
    }
    expect(a[3]).toBeCloseTo(2, 4);
  });

  /**
   * A 4 m wide stream strip in two-vertex rows through the given row centres (x, y), from the first
   * row to the last; with uv1, its seconds count from the first row (as bake_web writes them).
   */
  function strip(centres: [number, number][], withUv1: boolean) {
    const pos: number[] = [];
    const uv: number[] = [];
    const uv1: number[] = [];
    const idx: number[] = [];
    let s = 0;
    centres.forEach(([x, y], r) => {
      if (r > 0) s += Math.hypot(x - centres[r - 1][0], y - centres[r - 1][1]);
      pos.push(x, y, -2, x, y, 2);
      uv.push(0, r / (centres.length - 1), 1, r / (centres.length - 1));
      uv1.push(-2, s / FALL.streamSpeed, 2, s / FALL.streamSpeed);
      if (r < centres.length - 1) idx.push(r * 2, r * 2 + 1, r * 2 + 2, r * 2 + 1, r * 2 + 3, r * 2 + 2);
    });
    return sheetFallAttribute({ positions: pos, uvs: uv, index: idx, stream: true, uv1: withUv1 ? uv1 : null });
  }

  /** Every stretch steeper than STREAM.levelDeg carries its pattern downhill, at its true length. */
  function expectDownhill(order: [number, number][], below: (r: number) => number) {
    for (let r = 1; r < order.length; r++) {
      const [x0, y0] = order[r - 1];
      const [x1, y1] = order[r];
      if (Math.abs(y1 - y0) < Math.tan((STREAM.levelDeg * Math.PI) / 180) * Math.abs(x1 - x0)) continue;
      // The pattern moves toward larger `below`: from the higher row to the lower one.
      const downhill = y1 < y0 ? below(r) - below(r - 1) : below(r - 1) - below(r);
      expect(downhill).toBeCloseTo(Math.hypot(x1 - x0, y1 - y0), 3);
    }
  }

  it("runs a stream downhill on every stretch, over a crest and whichever end its rows start from", () => {
    // Down a slope, level, up a 35 m cliff (the stretches that flowed up), down two more, up 1 m.
    const centres: [number, number][] = [[0, 60], [10, 55], [20, 55], [30, 90], [40, 70], [50, 40], [60, 41]];
    for (const withUv1 of [false, true]) {
      for (const order of [centres, [...centres].reverse()]) {
        const a = strip(order, withUv1);
        const below = (r: number) => a[r * 8 + 1];
        expect(Math.min(...order.map((_, r) => below(r)))).toBeCloseTo(0, 4);
        expectDownhill(order, below);
        // The level stretch keeps going the way the water came down the first slope: toward the cliff.
        const lv = order.findIndex(([x]) => x === 10);
        const lv2 = order.findIndex(([x]) => x === 20);
        expect(below(lv2) - below(lv)).toBeCloseTo(10, 3);
        // The foot is the lower end (x = 60, y 41 against 60), whichever way the rows run.
        const foot = order.findIndex(([x]) => x === 60);
        const head = order.findIndex(([x]) => x === 0);
        expect(a[foot * 8 + 2]).toBeCloseTo(-2, 5);
        expect(a[head * 8 + 2]).toBeCloseTo(-1, 5);
        // Metres across still come from UV1 when it is there.
        if (withUv1) expect(a[0]).toBeCloseTo(-2, 5);
      }
    }
  });

  it("runs random streams downhill on every steep stretch, with or without UV1, either way round", () => {
    let seed = 7;
    const rnd = () => {
      seed = (seed * 1103515245 + 12345) % 2147483648;
      return seed / 2147483648;
    };
    for (let t = 0; t < 40; t++) {
      const centres: [number, number][] = [];
      let x = 0;
      let y = 200 * rnd();
      for (let r = 0; r < 24; r++) {
        centres.push([x, y]);
        x += 5 + 50 * rnd();
        y += (rnd() - 0.5) * (rnd() < 0.3 ? 300 : 8);
      }
      for (const withUv1 of [false, true]) {
        for (const order of [centres, [...centres].reverse()]) {
          const a = strip(order, withUv1);
          expectDownhill(order, (r) => a[r * 8 + 1]);
          for (let r = 0; r < order.length; r++) {
            expect(a[r * 8 + 1]).toBeGreaterThanOrEqual(0);
            expect(a[r * 8 + 2]).toBeLessThanOrEqual(-1);
            expect(a[r * 8 + 2]).toBeGreaterThanOrEqual(-2);
          }
        }
      }
    }
  });

  it("measures a sheet from world height when its UV1 seconds grow upward (exported upside down)", () => {
    const m = merge(sheet(0, 10, 2, 5, 0));
    const n = m.positions.length / 3;
    const uv1 = new Float32Array(n * 2);
    for (let i = 0; i < n; i++) {
      uv1[i * 2] = (m.uvs[i * 2] - 0.5) * 2;
      uv1[i * 2 + 1] = Math.sqrt((2 * Math.max(m.positions[i * 3 + 1] - 5, 0)) / 9.81);
    }
    const a = sheetFallAttribute({ positions: m.positions, uvs: m.uvs, index: m.index, uv1 });
    for (let i = 0; i < n; i++) {
      expect(a[i * 4 + 1]).toBeCloseTo(10 - m.positions[i * 3 + 1], 4);
      expect(a[i * 4]).toBeCloseTo(uv1[i * 2], 5);
    }
    expect(a[2]).toBeCloseTo(5, 4);
  });

  it("uses Blender's UV1 (metres across, seconds since the lip) when present", () => {
    const m = merge(sheet(0, 10, 2, 5, 0));
    const n = m.positions.length / 3;
    const uv1 = new Float32Array(n * 2);
    for (let i = 0; i < n; i++) {
      uv1[i * 2] = m.uvs[i * 2] * 3;
      uv1[i * 2 + 1] = Math.sqrt((2 * Math.max(10 - m.positions[i * 3 + 1], 0)) / 9.81);
    }
    const a = sheetFallAttribute({ positions: m.positions, uvs: m.uvs, index: m.index, uv1 });
    for (let i = 0; i < n; i++) {
      expect(a[i * 4]).toBeCloseTo(uv1[i * 2], 5);
      expect(a[i * 4 + 1]).toBeCloseTo(10 - m.positions[i * 3 + 1], 3);
    }
    expect(a[2]).toBeCloseTo(5, 3);
    expect(a[3]).toBeCloseTo(3, 4);
  });
});

describe("streamFlow", () => {
  const at = (pts: [number, number][]): Vec3[] => pts.map(([x, y]) => [x, y, 0]);

  it("pours down both sides of a crest and into both sides of a dip", () => {
    // world.stream's shape: down, a 101 m cliff up (it flowed up it), down the far side.
    const f = streamFlow(at([[0, 70], [20, 45], [40, 146], [60, 113], [80, 20]]));
    expect(f.dirs).toEqual([1, -1, 1, 1]);
    // Row 1 is the dip both sides run into, row 2 the crest they leave; the smallest value is 0.
    expect(f.along[1]).toBeGreaterThan(f.along[0]);
    expect(f.along[1]).toBeGreaterThan(f.along[2]);
    expect(f.along[2]).toBe(0);
    expect(f.along[4] - f.along[2]).toBeCloseTo(Math.hypot(20, 33) + Math.hypot(20, 93), 6);
  });

  it("keeps level stretches going the way the water was going, not back and forth over small bumps", () => {
    // Down a slope onto a floor with 0.3-1 m bumps every 20 m (under 3 degrees), then down again.
    const f = streamFlow(at([[0, 60], [20, 40], [40, 40.5], [60, 40.2], [80, 41], [100, 40.4], [120, 20]]));
    expect(f.dirs).toEqual([1, 1, 1, 1, 1, 1]);
    // A 30 m cliff at the far (higher) end instead: the water off it keeps going across the floor.
    const g = streamFlow(at([[0, 70], [20, 40], [40, 40.5], [60, 40.2], [80, 41], [100, 71]]));
    expect(g.dirs).toEqual([1, -1, -1, -1, -1]);
  });

  it("runs a level strip toward its lower end, and gives the foot share 1 at the lower end", () => {
    const f = streamFlow(at([[0, 10], [20, 10.5], [40, 10.2], [60, 10.9]]));
    expect(f.dirs).toEqual([-1, -1, -1]);
    expect(f.share[3]).toBe(0);
    expect(f.share[0]).toBe(1);
    expect(f.along[0]).toBeCloseTo(60, 1);
    const g = streamFlow(at([[0, 30], [10, 20], [20, 10]]));
    expect(g.share).toEqual([0, 0.5, 1]);
    expect(streamFlow(at([[0, 5]]))).toEqual({ dirs: [], along: [0], share: [0] });
  });

  it("follows the slope above STREAM.levelDeg, and treats gentler stretches as level", () => {
    const rise = (deg: number) => 20 * Math.tan((deg * Math.PI) / 180);
    // Down a cliff, then a gentle climb of (levelDeg - 1) and a steeper one of (levelDeg + 1).
    const gentle = streamFlow(at([[0, 100], [20, 0], [40, rise(STREAM.levelDeg - 1)]]));
    expect(gentle.dirs).toEqual([1, 1]);
    const steep = streamFlow(at([[0, 100], [20, 0], [40, rise(STREAM.levelDeg + 1)]]));
    expect(steep.dirs).toEqual([1, -1]);
  });
});

const fall = (name: string, lipL: Vec3, lipR: Vec3, footR: Vec3, footL: Vec3, chunk = "abode"): Waterfall => ({
  name,
  kind: "sheet",
  position: [0, 0, 0],
  size: [1, 1, 1],
  rotation: [0, 0, 0, 1],
  nearestM: 10,
  corners: [lipL, lipR, footR, footL],
  foot: [(footR[0] + footL[0]) / 2, footR[1], (footR[2] + footL[2]) / 2],
  flow: 1,
  chunk,
});

describe("wet falls", () => {
  // A 6 m wide, 40 m fall from y 100, across +x, arcing 4 m out toward -z; a second sheet of it; a stream.
  const a = fall("a.sheet", [-3, 100, 0], [3, 100, 0], [4, 60, -4], [-4, 60, -4]);
  const b = fall("a.sheet.001", [-2.5, 100, 0.05], [2.5, 100, 0.05], [3.5, 60, -3.9], [-3.5, 60, -3.9]);
  const straight = fall("b.sheet", [200, 50, 0], [200, 50, 10], [200, 20, 10], [200, 20, 0]);
  const stream: Waterfall = { ...a, name: "s", kind: "stream" };
  const list = wetFalls([a, b, straight, stream, { ...a, name: "nocorners", corners: null }]);

  it("groups the sheets of one fall by their foot", () => {
    expect(list.map((f) => f.name)).toEqual(["a.sheet", "b.sheet"]);
    const f = list[0];
    expect(f.lip[1]).toBeCloseTo(100);
    expect(f.foot[1]).toBeCloseTo(60);
    expect(f.height).toBeCloseTo(40);
    expect(f.halfLip).toBeCloseTo(3, 1);
    expect(f.halfFoot).toBeCloseTo(4, 1);
    // The set that draws its water: the chunk, or the global set for the backdrop's (and v1) water.
    expect(f.chunk).toBe("abode");
    expect(wetFalls([{ ...a, chunk: "backdrop" }])[0].chunk).toBe("global");
    expect(wetFalls([{ ...a, chunk: null }])[0].chunk).toBe("global");
  });

  it("points `out` the way the water arcs, and has no side when it falls straight", () => {
    const f = list[0];
    expect(f.out[1]).toBeCloseTo(-1, 3);
    expect(f.outFoot).toBeCloseTo(3.98, 1);
    expect(f.symmetric).toBe(false);
    expect(list[1].symmetric).toBe(true);
  });

  it("wets the rock behind and beside the water and round the foot, not above the lip or out in front", () => {
    const f = list[0];
    const behind: Vec3 = [0, 80, 1];
    expect(wetAmount(f, behind)).toBeGreaterThan(0.6);
    expect(wetAmount(f, [5, 80, 0.5])).toBeGreaterThan(0.2);
    expect(wetAmount(f, [20, 80, 0])).toBe(0);
    expect(wetAmount(f, [0, 104, 1])).toBe(0);
    expect(wetAmount(f, [0, 80, -12])).toBe(0);
    expect(wetAmount(f, [5, 60.5, -8])).toBeGreaterThan(0.5);
    expect(wetAmount(f, [30, 60.5, -10])).toBe(0);
    expect(wetAmount(f, behind, 0.5)).toBeCloseTo(wetAmount(f, behind) / 2, 6);
  });

  it("is dry beside the lip and wets the band gradually downward (no ruled line level with the lip)", () => {
    const f = list[0];
    expect(wetDown(0)).toBe(0);
    expect(wetDown(1)).toBeCloseTo(1, 6);
    for (let s = 0.02; s <= 1; s += 0.02) expect(wetDown(s)).toBeGreaterThanOrEqual(wetDown(s - 0.02));
    expect(wetAmount(f, [0, 99.6, 1])).toBeLessThan(0.05);
    expect(wetAmount(f, [0, 96, 1])).toBeGreaterThan(wetAmount(f, [0, 99, 1]));
  });

  it("frays the band's edges with the trickle noise without a hard edge where the mask ends", () => {
    const g = wetRockGlsl();
    expect(g).toContain("float cut = ");
    // The lowest threshold's ramp starts at w = 0, so the w <= 0.002 early return draws no edge.
    expect(WET.edgeCut - WET.edgeSoft).toBeGreaterThanOrEqual(0);
    expect(WET.edgeCut + WET.edgeSpread + WET.edgeSoft).toBeLessThanOrEqual(1);
  });

  it("picks the nearest falls and fades the last ones out before they are swapped", () => {
    const xs = [0, 100, 200, 300, 320, 600, 700, 800, 900, 1000];
    const many: WetFall[] = xs.map((x, i) => ({ ...list[0], name: `f${i}`, lip: [x, 100, 0], foot: [x, 60, -4] }));
    const sel = selectWetFalls(many, [0, 80, 20], 4);
    expect(sel.map((s) => s.fall.name)).toEqual(["f0", "f1", "f2", "f3"]);
    expect(sel[0].strength).toBe(1);
    expect(sel[2].strength).toBe(1);
    // f3 is only 20 m nearer than f4, the first one left out: almost faded.
    expect(sel[3].strength).toBeLessThan(0.4);
    expect(sel[3].strength).toBeGreaterThan(0);
    // Nothing beyond the reach.
    expect(selectWetFalls(many, [0, 80, 5000], 4)).toEqual([]);
    expect(selectWetFalls(many, [0, 80, 20], 0)).toEqual([]);
  });

  it("packs four vec4 per fall", () => {
    const arr = wetArrays(2);
    const n = packWetFalls([{ fall: list[0], strength: 0.5 }, { fall: list[1], strength: 1 }, { fall: list[0], strength: 1 }], arr);
    expect(n).toBe(2);
    expect([...arr.a.slice(0, 4)]).toEqual([...list[0].lip, list[0].foot[1]].map((x) => Math.fround(x)));
    expect(arr.b[2]).toBeCloseTo(0.5);
    expect(arr.b[7]).toBe(1);
    expect(arr.c[3]).toBeCloseTo(list[0].height, 4);
    expect(arr.d[2]).toBeCloseTo(list[0].splashR, 4);
  });

  it("has GLSL that keeps derivatives and implicit-LOD fetches out of non-uniform control flow", () => {
    const g = wetRockGlsl();
    expect(g).toContain(`#define SECT_WET_MAX ${WET.max}`);
    for (const u of ["uWetA", "uWetB", "uWetC", "uWetD", "uWetCount", "uWetSun", "uWetSheen", "uWetTime", "tWetNoise"]) expect(g).toContain(u);
    expect(g).toContain("vec3 sectWetRock( vec3 col, vec3 p )");
    expect(g).not.toMatch(/\bhalf\b/);
    expect(g).not.toContain("texture2D(");
    expect(g).toContain("textureLod( tWetNoise");
    expect(g.indexOf("dFdx( p )")).toBeLessThan(g.indexOf("if ( w <= 0.002 ) return col;"));
  });
});

describe("waterfall picking", () => {
  const corners: [Vec3, Vec3, Vec3, Vec3] = [
    [-4, 50, 0],
    [4, 50, 0],
    [4, 0, 2],
    [-4, 0, 2],
  ];
  const fall = (name: string, position: Vec3, chunk: string | null, c: Waterfall["corners"] = corners): Waterfall => ({
    name,
    kind: "sheet",
    position,
    size: [8, 50, 2],
    rotation: [0, 0, 0, 1],
    nearestM: 30,
    corners: c,
    foot: [0, 0, 2],
    flow: 1,
    chunk,
  });
  const hotspots = [
    { id: "abode", center: [0, 25, 0] as Vec3, size: [200, 120, 200] as Vec3, chunk: "abode" },
    { id: "fact:0", center: [0, 24, 1] as Vec3, size: [23, 48, 23] as Vec3, chunk: "abode" },
    { id: "fact:6", center: [0, 1, 0] as Vec3, size: [400, 2, 400] as Vec3, chunk: "abode" },
  ];

  it("gives a sheet to the smallest item box of its own chunk that holds its centre", () => {
    const picks = fallPickQuads([fall("abode.waterfall.sheet", [0, 25, 1], "abode"), fall("abode.waterfall.sheet.001", [0, 25, 1], "abode")], hotspots);
    expect(picks.map((p) => p.id)).toEqual(["fact:0", "fact:0"]);
    expect(picks[0].chunk).toBe("abode");
    expect(picks[0].corners).toBe(corners);
  });

  it("leaves out sheets with no corners, in another chunk, or only inside a landmark's box", () => {
    expect(fallPickQuads([fall("a", [0, 25, 1], "abode", null)], hotspots)).toEqual([]);
    expect(fallPickQuads([fall("b", [0, 25, 1], "summit")], hotspots)).toEqual([]);
    expect(fallPickQuads([fall("c", [90, 25, 90], "abode")], hotspots)).toEqual([]);
  });

  it("hits a quad from either side and misses beside it", () => {
    const front = rayQuad([0, 20, -30], [0, 0, 1], corners);
    expect(front).not.toBeNull();
    // The quad leans: at y = 20 it sits at z = 2 * (1 - 20 / 50).
    expect(front!).toBeCloseTo(30 + 1.2, 6);
    expect(rayQuad([0, 20, 30], [0, 0, -1], corners)).toBeCloseTo(30 - 1.2, 6);
    expect(rayQuad([6, 20, -30], [0, 0, 1], corners)).toBeNull();
    expect(rayQuad([0, 20, -30], [0, 0, -1], corners)).toBeNull();
    // Both triangles: near the lip (first) and near the foot (second).
    expect(rayQuad([3, 45, -10], [0, 0, 1], corners)).not.toBeNull();
    expect(rayQuad([-3, 5, -10], [0, 0, 1], corners)).not.toBeNull();
  });
});
