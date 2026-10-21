import { describe, expect, it } from "vitest";
import type { Vec3 } from "./types";
import {
  buildSkirts,
  discFromBox,
  discFromTriangles,
  distanceFade,
  dominantFlatLevel,
  fallFeet,
  flatLevelBounds,
  fxAssetUrl,
  fxTier,
  groundedFalls,
  landsOnGround,
  mistPuff,
  mistSpots,
  pickFootSlots,
  quadFromCorners,
  sheetExtent,
  skirtHeight,
  skirtRadius,
  sprayDrop,
  sprayReach,
  waterFresnel,
  WATERFALL_FX,
  WFX_GLSL,
  wfxHash,
} from "./water";

describe("water", () => {
  // A 10 x 10 m pond surface at y = 2 (two triangles), a 1 m stone top at y = 2.6 and a wall.
  const quad = (y: number, s: number, x0 = 0): number[] => [x0, y, 0, x0 + s, y, 0, x0 + s, y, s, x0, y, 0, x0 + s, y, s, x0, y, s];
  const wall = [0, 0, 0, 10, 0, 0, 10, 5, 0];
  const soup = new Float32Array([...quad(2, 10), ...quad(2.6, 1, 20), ...wall]);

  it("finds the level of the largest flat surface", () => {
    const r = dominantFlatLevel(soup, null);
    expect(r).not.toBeNull();
    expect(r!.level).toBeCloseTo(2, 5);
    expect(r!.area).toBeCloseTo(100, 5);
  });

  it("reads indexed geometry too", () => {
    const pos = new Float32Array([0, 1, 0, 4, 1, 0, 4, 1, 4, 0, 1, 4]);
    const r = dominantFlatLevel(pos, [0, 1, 2, 0, 2, 3]);
    expect(r!.level).toBeCloseTo(1, 5);
    expect(r!.area).toBeCloseTo(16, 5);
    expect(dominantFlatLevel(new Float32Array(wall), null)).toBeNull();
  });

  it("fits a disc to a thin box, facing the given point", () => {
    const d = discFromBox([-104.5, 74.6, -209.1], [-97.8, 81.4, -207.7], [-96, 69.6, -181]);
    expect(d.normal).toEqual([0, 0, 1]);
    expect(d.radius).toBeCloseTo(3.35, 2);
    expect(d.center[1]).toBeCloseTo(78, 1);
    expect(discFromBox([0, 0, 0], [0.5, 4, 4], [-10, 0, 0]).normal).toEqual([-1, 0, 0]);
  });

  it("Fresnel runs from 2% straight down to 100% at grazing", () => {
    expect(waterFresnel(1)).toBeCloseTo(0.02);
    expect(waterFresnel(0)).toBeCloseTo(1);
    expect(waterFresnel(0.34)).toBeGreaterThan(0.1);
  });

  it("bounds the open water at the level, not the pads floating above it or the stones", () => {
    // Water 10 x 10 at y = 2, a lily pad 4.5 cm up past the water's edge, a stone top at 2.6.
    const pad = quad(2.045, 1, 12);
    const b = flatLevelBounds(new Float32Array([...soup, ...pad]), null, 2);
    expect(b).not.toBeNull();
    expect(b!.min).toEqual([0, 0]);
    expect(b!.max).toEqual([10, 10]);
    expect(b!.area).toBeCloseTo(100, 5);
    expect(flatLevelBounds(soup, null, 3)).toBeNull();
    // A sloping triangle that touches the level is no water.
    expect(flatLevelBounds(new Float32Array(wall), null, 0)).toBeNull();
  });

  it("fits a disc to a turned face from its triangles (the rim band does not tilt it)", () => {
    // A 64-sided disc of radius 3.3 centred at (1, 78, -208), turned 18 degrees about y, plus a rim band.
    const a = (18 * Math.PI) / 180;
    const n: Vec3 = [Math.sin(a), 0, Math.cos(a)];
    const u: Vec3 = [Math.cos(a), 0, -Math.sin(a)];
    const c: Vec3 = [1, 78, -208];
    const pt = (r: number, t: number, off = 0): number[] => [
      c[0] + u[0] * r * Math.cos(t) + n[0] * off,
      c[1] + r * Math.sin(t),
      c[2] + u[2] * r * Math.cos(t) + n[2] * off,
    ];
    const tris: number[] = [];
    const seg = 64;
    for (let i = 0; i < seg; i++) {
      const t0 = (i / seg) * Math.PI * 2;
      const t1 = ((i + 1) / seg) * Math.PI * 2;
      tris.push(...pt(0, 0, 0.2), ...pt(3.3, t0, 0.2), ...pt(3.3, t1, 0.2));
      tris.push(...pt(3.3, t0, 0.2), ...pt(3.3, t0, 0.08), ...pt(3.3, t1, 0.08));
    }
    const d = discFromTriangles(new Float32Array(tris), null, [c[0] + n[0] * 30, 70, c[2] + n[2] * 30]);
    expect(d).not.toBeNull();
    for (let k = 0; k < 3; k++) expect(d!.normal[k]).toBeCloseTo(n[k], 4);
    expect(d!.radius).toBeCloseTo(3.3, 2);
    expect(d!.center[1]).toBeCloseTo(78, 1);
    // Seen from behind, the normal turns round.
    const back = discFromTriangles(new Float32Array(tris), null, [c[0] - n[0] * 30, 70, c[2] - n[2] * 30]);
    expect(back!.normal[2]).toBeCloseTo(-n[2], 4);
    expect(discFromTriangles(new Float32Array(9), null, [0, 0, 0])).toBeNull();
  });
});

describe("waterfall sheets", () => {
  // Lip 10 m wide at y = 100, falling 80 m, leaning out 5 m.
  const corners: [Vec3, Vec3, Vec3, Vec3] = [
    [0, 100, 0],
    [10, 100, 0],
    [10, 20, 5],
    [0, 20, 5],
  ];

  it("builds the quad from the corners as given (nothing rotated twice)", () => {
    const q = quadFromCorners(corners);
    expect(Array.from(q.positions.slice(0, 3))).toEqual([0, 100, 0]);
    expect(Array.from(q.positions.slice(6, 9))).toEqual([10, 20, 5]);
    // v = 1 at the lip, 0 at the foot; u across.
    expect(Array.from(q.uvs)).toEqual([0, 1, 1, 1, 1, 0, 0, 0]);
    expect(q.index.length).toBe(6);
  });

  it("measures width at the lip and height along the fall", () => {
    const e = sheetExtent(corners);
    expect(e.width).toBeCloseTo(10);
    expect(e.height).toBeCloseTo(Math.hypot(80, 5));
  });

  it("puts mist only at feet above the clouds, one spot per fall", () => {
    const fall = (foot: Vec3, nearestM = 100) => ({ foot, corners, nearestM });
    const spots = mistSpots([fall([5, 20, 5]), fall([6, 20, 5]), fall([5, -80, 5]), fall([300, 40, 0], 5000)], 0);
    expect(spots.length).toBe(1);
    expect(spots[0].position[1]).toBeGreaterThan(20);
    expect(spots[0].radius).toBeGreaterThanOrEqual(10);
    expect(mistSpots([{ foot: null, corners: null, nearestM: 10 }], 0)).toEqual([]);
  });
});

describe("waterfall feet", () => {
  // The Cave Abode's three sheets (meta.json), an island fall that stops in mid-air, a range fall
  // into the clouds and a feeder stream.
  const abode = { anchor: [185, 250, -1335] as Vec3, footprint: 45 };
  const forge = { anchor: [115, 95, -335] as Vec3, footprint: 50 };
  const sheet = (name: string, corners: [Vec3, Vec3, Vec3, Vec3], foot: Vec3, extra: { kind?: string; chunk?: string | null; nearestM?: number } = {}) => ({
    name,
    kind: "sheet",
    corners,
    foot,
    nearestM: 35,
    chunk: "abode" as string | null,
    ...extra,
  });
  const abodeSheets = [
    sheet(
      "abode.waterfall.sheet",
      [
        [211.449, 294.983, -1347.528],
        [215.938, 294.983, -1343.682],
        [214.554, 251.516, -1340.867],
        [209.064, 250, -1345.551],
      ],
      [211.705, 250.758, -1343.233],
    ),
    sheet(
      "abode.waterfall.sheet.001",
      [
        [212.117, 294.993, -1346.592],
        [215.937, 294.993, -1343.323],
        [213.602, 251.526, -1340.093],
        [209.202, 250.01, -1343.775],
      ],
      [211.415, 250.768, -1341.878],
    ),
    sheet(
      "abode.waterfall.sheet.002",
      [
        [212.05, 295.003, -1346.306],
        [215.255, 295.003, -1343.567],
        [212.703, 250.02, -1339.132],
        [207.932, 250.02, -1343.253],
      ],
      [210.346, 250.778, -1341.311],
    ),
  ];
  const island = sheet(
    "scenery.island.fall.022.sheet",
    [
      [300, 411, -460],
      [303, 411, -458],
      [299, 161, -467],
      [296, 161, -469],
    ],
    [298.1, 160.5, -465.8],
    { chunk: "forge", nearestM: 263 },
  );
  const range = sheet(
    "scenery.fall.006.sheet",
    [
      [240, 20, -270],
      [262, 20, -272],
      [242, -78, -274],
      [240, -78, -274],
    ],
    [241.8, -78, -274.5],
    { chunk: "forge" },
  );
  const stream = sheet(
    "world.stream.004",
    [
      [150, 90, -300],
      [155, 90, -300],
      [213, 33, -364],
      [210, 33, -364],
    ],
    [213.1, 33.1, -364.1],
    { kind: "stream", chunk: "forge" },
  );
  const all = [...abodeSheets, island, range, stream];

  it("keeps only feet on an area's ground (no mist hanging under an island)", () => {
    expect(landsOnGround([211.7, 250.8, -1343.2], [abode, forge])).toBe(true);
    expect(landsOnGround([298.1, 160.5, -465.8], [abode, forge])).toBe(false);
    // Inside the footprint but far below the terraces: not this area's ground.
    expect(landsOnGround([185, 150, -1335], [abode])).toBe(false);
    expect(groundedFalls(all, [abode, forge], 20).map((f) => f.name)).toEqual(abodeSheets.map((s) => s.name));
    // Older meta files without areas: every sheet foot above the clouds, as before (streams never).
    expect(groundedFalls(all, [], 20).map((f) => f.name)).toEqual([...abodeSheets.map((s) => s.name), island.name]);
  });

  it("drops the mid-air mist spots but keeps the abode's", () => {
    const spots = mistSpots(groundedFalls(all, [abode, forge], 20), 20);
    expect(spots.length).toBe(1);
    expect(spots[0].position[1]).toBeGreaterThan(250.7);
  });

  it("merges a fall's sheets into one foot on its pool", () => {
    const feet = fallFeet(all, [abode, forge], 20);
    expect(feet.length).toBe(1);
    const ft = feet[0];
    expect(ft.name).toBe("abode.waterfall.sheet");
    expect(ft.chunk).toBe("abode");
    expect(ft.center[0]).toBeCloseTo((211.705 + 211.415 + 210.346) / 3, 3);
    expect(ft.level).toBeCloseTo(ft.center[1] - WATERFALL_FX.poolBelowFoot, 6);
    expect(ft.width).toBeCloseTo(5.91, 1);
    expect(ft.drop).toBeGreaterThan(44);
    expect(ft.spread).toBeGreaterThan(0.5);
    expect(ft.spread).toBeLessThan(2);
    // Pours away from the cliff: from the lips (x ~214, z ~-1345.6) toward the feet (x ~211, z ~-1342).
    expect(Math.hypot(ft.pour[0], ft.pour[1])).toBeCloseTo(1, 6);
    expect(ft.pour[0]).toBeLessThan(-0.5);
    expect(ft.pour[1]).toBeGreaterThan(0.5);
    expect(ft.pourAngle).toBeCloseTo(Math.atan2(ft.pour[1], ft.pour[0]), 9);
  });

  it("orders feet largest first and caps them", () => {
    const shifted = (dx: number, wider: number) =>
      abodeSheets.map((s) => ({
        ...s,
        name: `${s.name}.${dx}`,
        corners: s.corners.map((c, i) => [c[0] + dx + (i === 1 ? wider : 0), c[1], c[2]]) as [Vec3, Vec3, Vec3, Vec3],
        foot: [s.foot[0] + dx, s.foot[1], s.foot[2]] as Vec3,
      }));
    const area = { anchor: [185, 250, -1335] as Vec3, footprint: 200 };
    const feet = fallFeet([...shifted(0, 0), ...shifted(40, 8), ...shifted(-40, 4)], [area], 20, { maxFeet: 2 });
    expect(feet.length).toBe(2);
    expect(feet[0].width).toBeGreaterThan(feet[1].width);
    expect(feet[0].center[0]).toBeGreaterThan(240);
  });

  it("picks the nearest weighted feet for the shared draws, without allocating", () => {
    const out = new Int32Array(2);
    expect(pickFootSlots([1, 0, 1, 1], [30, 5, 10, 20], out)).toBe(2);
    expect(Array.from(out)).toEqual([2, 3]);
    expect(pickFootSlots([0, 0], [1, 2], out)).toBe(0);
    expect(pickFootSlots([1], [7], new Int32Array(0))).toBe(0);
    const four = new Int32Array(4);
    expect(pickFootSlots([0.2, 0.5, 1], [9, 3, 6], four)).toBe(3);
    expect(Array.from(four.slice(0, 3))).toEqual([1, 2, 0]);
  });

  it("fades with distance and reads the tier like the other effects", () => {
    expect(distanceFade(10, 100, 200)).toBe(1);
    expect(distanceFade(150, 100, 200)).toBeCloseTo(0.5);
    expect(distanceFade(250, 100, 200)).toBe(0);
    expect(fxTier({ post: true, msaa: 4 })).toBe("high");
    expect(fxTier({ post: true, msaa: 0 })).toBe("mid");
    expect(fxTier({ post: false, msaa: 0 })).toBe("low");
  });

  it("finds the shared fx folder beside any asset set", () => {
    expect(fxAssetUrl("/sect/full", "foam.webp")).toBe("/sect/fx/foam.webp");
    expect(fxAssetUrl("/sect/before/", "mist_flipbook.webp")).toBe("/sect/fx/mist_flipbook.webp");
    expect(fxAssetUrl("https://cdn.example.com/a/full", "foam.webp")).toBe("https://cdn.example.com/a/fx/foam.webp");
  });
});

describe("foam skirt", () => {
  const foot = {
    name: "f",
    center: [0, 10, 0] as Vec3,
    level: 9.82,
    pour: [1, 0] as [number, number],
    pourAngle: 0,
    width: 6,
    drop: 46,
    spread: 1,
    chunk: null,
    nearestM: 30,
  };

  it("lies on the pool with a boil mound tall enough to hide the baked foam lump", () => {
    const R = skirtRadius(foot);
    expect(R).toBeCloseTo(WATERFALL_FX.skirt.radius * 6 + 1);
    // Covers the bake's foam disc (0.85 x width) even 1 m off centre.
    expect(R).toBeGreaterThan(0.85 * 6 + 1 + 2);
    // nature.waterfall's splash blobs reach about 1.1 m over the foot within 0.45 x width, and its
    // foam disc (0.85 x width) sits 0.21 m over the pool.
    expect(skirtHeight(0, R, 6)).toBeGreaterThanOrEqual(1.2);
    expect(skirtHeight(0.45 * 6, R, 6)).toBeGreaterThanOrEqual(1.0);
    expect(skirtHeight(R, R, 6)).toBe(0);
    expect(skirtHeight(0, R, 40)).toBe(WATERFALL_FX.skirt.boilMax);
  });

  it("builds one up-facing polar grid per foot", () => {
    const seg = 12;
    const rings = 4;
    const g = buildSkirts([foot, { ...foot, center: [50, 0, 0], level: -0.18 }], seg, rings);
    const per = (seg + 1) * (rings + 1);
    expect(g.positions.length).toBe(2 * per * 3);
    expect(g.index.length).toBe(2 * seg * rings * 6);
    expect(Math.max(...g.index)).toBe(2 * per - 1);
    // The rim sits on the pool (plus the lift); the second foot's vertices are tagged 1.
    const rim = (per - 1) * 3;
    expect(g.positions[rim + 1]).toBeCloseTo(foot.level + WATERFALL_FX.skirt.lift, 5);
    expect(g.skirt[per * 4 + 1]).toBe(1);
    expect(g.skirt[per * 4 + 3]).toBe(6);
    // The mound's slope: flat on top and on the pool, falling in between.
    expect(g.skirt[2]).toBeCloseTo(0, 6);
    let steepest = 0;
    for (let i = 0; i < per; i++) steepest = Math.min(steepest, g.skirt[i * 4 + 2]);
    expect(steepest).toBeLessThan(-0.1);
    expect(g.uv[(per - 1) * 2 + 1]).toBe(1);
    let up = 0;
    let down = 0;
    for (let t = 0; t < g.index.length; t += 3) {
      const [a, b, c] = [g.index[t], g.index[t + 1], g.index[t + 2]].map((i) => [g.positions[i * 3], g.positions[i * 3 + 1], g.positions[i * 3 + 2]]);
      const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
      const w = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
      const ny = u[2] * w[0] - u[0] * w[2];
      if (ny > 1e-9) up++;
      else if (ny < -1e-9) down++;
    }
    expect(down).toBe(0);
    expect(up).toBeGreaterThan(0);
  });
});

describe("spray and mist puffs", () => {
  const seedsOf = (n: number) =>
    Array.from({ length: n }, (_, i) => [wfxHash(i * 1.17 + 0.3), wfxHash(i * 2.31 + 0.7), wfxHash(i * 3.73 + 0.1), (i * 0.618034) % 1] as [number, number, number, number]);

  it("hashes into 0..1", () => {
    for (let i = 0; i < 500; i++) {
      const h = wfxHash(i * 0.37 - 40);
      expect(h).toBeGreaterThanOrEqual(0);
      expect(h).toBeLessThan(1);
    }
  });

  it("throws drops that stay over the pool and inside their reach", () => {
    const width = 5.91;
    const reach = sprayReach(width);
    // The abode's pool: radius 7 m, centred 3 m out from the foot.
    expect(reach).toBeLessThan(7);
    let flying = 0;
    for (const s of seedsOf(120)) {
      for (let t = 0; t < 12; t += 0.07) {
        const d = sprayDrop(s, t, width, 0.9);
        if (d.fade <= 0) continue;
        flying++;
        expect(d.fade).toBeLessThanOrEqual(1);
        expect(d.p[1]).toBeGreaterThan(-0.05);
        expect(Math.hypot(d.p[0], d.p[2])).toBeLessThanOrEqual(reach + 1e-6);
      }
    }
    expect(flying).toBeGreaterThan(1000);
  });

  it("moves each drop with its own velocity, and holds it when the clock stops", () => {
    const s: [number, number, number, number] = [0.3, 0.6, 0.2, 0.05];
    let checked = 0;
    for (let t = 0.5; t < 6; t += 0.37) {
      const a = sprayDrop(s, t, 6, 0);
      const b = sprayDrop(s, t + 1e-4, 6, 0);
      if (a.fade <= 0 || b.fade <= 0) continue;
      for (let i = 0; i < 3; i++) expect((b.p[i] - a.p[i]) / 1e-4).toBeCloseTo(a.v[i], 1);
      checked++;
    }
    expect(checked).toBeGreaterThan(0);
    expect(sprayDrop(s, 0, 6, 0)).toEqual(sprayDrop(s, 0, 6, 0));
  });

  it("raises puffs that fade in and out within their opacity range", () => {
    const P = WATERFALL_FX.puffs;
    let peak = 0;
    for (const s of seedsOf(40)) {
      for (let t = 0; t < 20; t += 0.1) {
        const m = mistPuff(s, t, 6, 0);
        expect(m.alpha).toBeGreaterThanOrEqual(0);
        expect(m.alpha).toBeLessThanOrEqual(P.opacity[1] + 1e-9);
        expect(m.frame).toBeGreaterThanOrEqual(0);
        expect(m.frame).toBeLessThanOrEqual(15);
        expect([0, 1, 2]).toContain(m.layer);
        expect(m.p[1]).toBeGreaterThan(0);
        expect(m.p[1]).toBeLessThan(12);
        expect(Math.hypot(m.p[0], m.p[2])).toBeLessThan(10);
        peak = Math.max(peak, m.alpha);
      }
    }
    expect(peak).toBeGreaterThanOrEqual(P.opacity[0]);
  });

  it("puts the tuning into the shader mirrors", () => {
    expect(WFX_GLSL).toContain("vec4 wfxSpray(");
    expect(WFX_GLSL).toContain("vec4 wfxPuff(");
    expect(WFX_GLSL).toContain("mix( 3.0, 6.5000000, h3 )");
    expect(WFX_GLSL).not.toContain("NaN");
  });
});
