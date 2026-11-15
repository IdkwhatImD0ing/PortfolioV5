import { CARD_LOOK, cardFarCutGlsl, farCutCellGlsl } from "./card-shading";
import { describe, expect, it } from "vitest";
import { glslFloat, hexToLinear } from "./glsl";
import { tierQuality } from "./runtime";
import {
  depthSun,
  depthTerms,
  padCount,
  parseVeg,
  parseVegIndex,
  parseVegParam,
  seedRandom,
  SHELL_STRIDE,
  shellGeometry,
  shellInstances,
  VEG_BOUGH_TURN,
  VEG_FLAG,
  VEG_LOOK,
  VEG_TONES,
  vegArchetype,
  vegBough,
  vegBoughMeans,
  vegBoughNear,
  vegBoughUniform,
  vegChunkId,
  vegCrease,
  vegCreaseShare,
  vegDepth,
  vegFieldSamples,
  vegFragmentGlsl,
  vegNoise,
  vegNoiseD,
  vegNoiseDGlsl,
  vegNoiseGlsl,
  vegSeed,
  vegShellsOn,
  vegTone,
  vegTurnGlsl,
  vegVertexGlsl,
  vegYaw,
  type DepthCrown,
  type ShellInstances,
  type VegData,
} from "./veg";
import type { Vec3 } from "./types";

interface Plant {
  x: number;
  y: number;
  z: number;
  h: number;
  r: number;
  family: number;
  yaw?: number;
  sun?: number;
  flags?: number;
}

/** A .veg file as sect_veg.py writes it. */
function vegFile(plants: Plant[], o: { magic?: string; version?: number; extra?: number } = {}): ArrayBuffer {
  const buf = new ArrayBuffer(16 + plants.length * 24 + (o.extra ?? 0));
  const dv = new DataView(buf);
  const magic = o.magic ?? "SVEG";
  for (let i = 0; i < 4; i++) dv.setUint8(i, magic.charCodeAt(i));
  dv.setUint32(4, o.version ?? 1, true);
  dv.setUint32(8, plants.length, true);
  plants.forEach((p, i) => {
    const b = 16 + i * 24;
    [p.x, p.y, p.z, p.h, p.r].forEach((v, k) => dv.setFloat32(b + k * 4, v, true));
    dv.setUint8(b + 20, p.yaw ?? 0);
    dv.setUint8(b + 21, p.sun ?? 255);
    dv.setUint8(b + 22, p.family);
    dv.setUint8(b + 23, p.flags ?? 0);
  });
  return buf;
}

const FAMILIES = [
  "bamboo.culm.v0",
  "pine.broadleaf.v3",
  "pine.huangshan.v1",
  "pine.masson.v2",
  "shrub.green.v1",
  "shrub.green.v1.low",
  "shrub.scrub.v0",
  "blossom.peach.v0",
  "pine.cliff.v0",
];
const F = Object.fromEntries(FAMILIES.map((name, i) => [name, i])) as Record<string, number>;

/** Plants spread over a hillside, every family, fixed sizes per family. */
function forest(n: number): Plant[] {
  const out: Plant[] = [];
  for (let i = 0; i < n; i++) {
    const family = i % (FAMILIES.length - 1);
    out.push({ x: (i % 37) * 7.3 - 120, y: 40 + (i % 11) * 3.1, z: Math.floor(i / 37) * 6.1 - 90, h: 4 + (i % 13), r: 1.2 + (i % 7) * 0.6, family, yaw: (i * 37) % 256, sun: (i * 53) % 256 });
  }
  return out;
}

/** The instances of one plant, as plain numbers. */
function crowns(inst: ShellInstances): { c: Vec3; rx: number; ry: number; rz: number; taper: number; yaw: number; seed: number; sun: number; tone: number; depth: number }[] {
  return Array.from({ length: inst.count }, (_, j) => ({
    c: [inst.center[j * 3], inst.center[j * 3 + 1], inst.center[j * 3 + 2]] as Vec3,
    rx: inst.shape[j * 4],
    ry: inst.shape[j * 4 + 1],
    rz: inst.shape[j * 4 + 2],
    taper: inst.shape[j * 4 + 3],
    yaw: inst.params[j * 4],
    seed: inst.params[j * 4 + 1],
    sun: inst.params[j * 4 + 2],
    tone: inst.params[j * 4 + 3],
    depth: inst.depth[j],
  }));
}

/** The scene's sun (public/sect/full/meta.json): toward -x, 7 degrees up. */
const SUN: Vec3 = [-0.94397, 0.12187, 0.30671];

function one(p: Plant): ShellInstances {
  return shellInstances(parseVeg(vegFile([p])), FAMILIES);
}

const count = (s: string, sub: string) => s.split(sub).length - 1;
const f32 = (v: number) => Math.fround(v);

describe("the .veg file", () => {
  it("reads every field of every record", () => {
    const v: VegData = parseVeg(
      vegFile([
        { x: 12.5, y: 80.25, z: -310.75, h: 14, r: 4.5, family: 2, yaw: 64, sun: 191, flags: 0 },
        { x: -1, y: 2, z: 3, h: 1.5, r: 0.75, family: 5, yaw: 255, sun: 0, flags: VEG_FLAG.mesh | VEG_FLAG.hotspot },
      ]),
    );
    expect(v.count).toBe(2);
    expect([...v.pos]).toEqual([12.5, 80.25, -310.75, -1, 2, 3]);
    expect([...v.height]).toEqual([14, 1.5]);
    expect([...v.radius]).toEqual([4.5, 0.75]);
    expect([...v.yaw]).toEqual([64, 255]);
    expect([...v.sun]).toEqual([191, 0]);
    expect([...v.family]).toEqual([2, 5]);
    expect([...v.flags]).toEqual([0, 3]);
    expect(parseVeg(vegFile([])).count).toBe(0);
  });

  it("rejects a wrong magic, another version, and a length that does not match the count", () => {
    const good = vegFile(forest(3));
    expect(() => parseVeg(vegFile(forest(3), { magic: "GLTF" }))).toThrow(/magic/);
    expect(() => parseVeg(vegFile(forest(3), { version: 2 }))).toThrow(/version/);
    expect(() => parseVeg(good.slice(0, good.byteLength - 5))).toThrow(/bytes for 3 plants/);
    expect(() => parseVeg(vegFile(forest(3), { extra: 24 }))).toThrow(/bytes for 3 plants/);
    expect(() => parseVeg(good.slice(0, 10))).toThrow(/header/);
  });

  it("turns a yaw byte into radians about +y", () => {
    expect(vegYaw(0)).toBe(0);
    expect(vegYaw(64)).toBeCloseTo(Math.PI / 2, 12);
    expect(vegYaw(128)).toBeCloseTo(Math.PI, 12);
    expect(vegYaw(255)).toBeLessThan(Math.PI * 2);
  });

  it("reads the index, and the global set takes the backdrop's file", () => {
    const ix = parseVegIndex({ version: 1, families: ["pine.masson.v2"], chunks: { gate: { file: "gate.veg", count: 9, cards: 7 }, backdrop: { file: "backdrop.veg", count: 2, cards: 2 } } });
    expect(ix.chunks.gate).toEqual({ file: "gate.veg", count: 9, cards: 7 });
    expect(ix.families).toEqual(["pine.masson.v2"]);
    expect(() => parseVegIndex({ version: 2, families: [], chunks: {} })).toThrow(/version/);
    expect(() => parseVegIndex({ version: 1, families: [3], chunks: {} })).toThrow(/families/);
    expect(() => parseVegIndex({ version: 1, families: [], chunks: { "../x": { file: "x.veg" } } })).toThrow(/chunk id/);
    expect(() => parseVegIndex({ version: 1, families: [], chunks: { gate: { file: "../gate.veg" } } })).toThrow(/file/);
    expect(() => parseVegIndex(null)).toThrow();
    expect(vegChunkId("global")).toBe("backdrop");
    expect(vegChunkId("mirror")).toBe("mirror");
  });
});

describe("archetypes", () => {
  it("maps each family to its crown, and skips the rest", () => {
    expect(vegArchetype("pine.huangshan.v1")).toBe("huangshan");
    expect(vegArchetype("pine.ancient.v2")).toBe("huangshan");
    expect(vegArchetype("pine.masson.v2")).toBe("masson");
    expect(vegArchetype("pine.broadleaf.v3")).toBe("broadleaf");
    expect(vegArchetype("shrub.green.v1")).toBe("shrub");
    expect(vegArchetype("shrub.green.v1.low")).toBe("shrub");
    expect(vegArchetype("shrub.scrub.v0")).toBe("shrub");
    expect(vegArchetype("shrub.azalea.v1")).toBe("shrub");
    expect(vegArchetype("bamboo.culm.v0")).toBe("bamboo");
    expect(vegArchetype("blossom.peach.v0")).toBe("blossom");
    for (const name of ["grass.v2", "lotus.bud.v0", "pine.cliff.v0", "pine", ""]) expect(vegArchetype(name)).toBeNull();
  });

  it("gives pines one bluer, darker tone, scrub an olive one, and blossom pink", () => {
    expect(vegTone("pine.huangshan.v1", "huangshan")).toBe("pine");
    expect(vegTone("pine.masson.v2", "masson")).toBe("pine");
    expect(vegTone("shrub.scrub.v0", "shrub")).toBe("scrub");
    expect(vegTone("shrub.green.v1.low", "shrub")).toBe("shrub");
    expect(vegTone("blossom.peach.v0", "blossom")).toBe("blossom");
    const P = VEG_LOOK.palettes;
    const lum = (hex: string) => {
      const c = hexToLinear(hex);
      return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
    };
    for (const t of VEG_TONES) expect(P[t]).toHaveLength(4);
    // Each palette runs from dark shade to sunlit.
    for (const t of VEG_TONES) for (let k = 1; k < 4; k++) expect(lum(P[t][k])).toBeGreaterThan(lum(P[t][k - 1]));
    for (let k = 0; k < 3; k++) {
      expect(lum(P.pine[k])).toBeLessThan(lum(P.broadleaf[k]));
      const pine = hexToLinear(P.pine[k]);
      const broad = hexToLinear(P.broadleaf[k]);
      expect(pine[2] / pine[1]).toBeGreaterThan(broad[2] / broad[1]);
    }
    const pink = hexToLinear(P.blossom[2]);
    expect(pink[0]).toBeGreaterThan(pink[1]);
    expect(pink[2]).toBeGreaterThan(pink[1]);
    expect(P.broadleaf).toEqual(["#1d3122", "#2c4630", "#4a6634", "#74894a"]);
    expect(P.blossom[1]).toBe("#b97a8c");
    expect(P.blossom[2]).toBe("#f6b3c3");
  });
});

describe("the unit shell", () => {
  for (const [detail, verts, tris] of [
    [1, 42, 80],
    [0, 18, 32],
  ] as const) {
    it(`detail ${detail}: ${tris} triangles on the unit sphere, wound outward, the same every time`, () => {
      const g = shellGeometry(detail);
      expect(g.triangles).toBe(tris);
      expect(g.indices.length).toBe(tris * 3);
      expect(g.positions.length).toBe(verts * 3);
      expect([...g.normals]).toEqual([...g.positions]);
      for (let i = 0; i < verts; i++) expect(Math.hypot(g.positions[i * 3], g.positions[i * 3 + 1], g.positions[i * 3 + 2])).toBeCloseTo(1, 6);
      for (let t = 0; t < tris; t++) {
        const [a, b, c] = [0, 1, 2].map((k) => {
          const i = g.indices[t * 3 + k];
          expect(i).toBeLessThan(verts);
          return [g.positions[i * 3], g.positions[i * 3 + 1], g.positions[i * 3 + 2]];
        });
        const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
        const v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
        const n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
        expect(n[0] * (a[0] + b[0] + c[0]) + n[1] * (a[1] + b[1] + c[1]) + n[2] * (a[2] + b[2] + c[2])).toBeGreaterThan(0);
      }
      const again = shellGeometry(detail);
      expect([...again.positions]).toEqual([...g.positions]);
      expect([...again.indices]).toEqual([...g.indices]);
    });
  }

  it("is the icosphere by default", () => {
    expect(VEG_LOOK.detail).toBe(1);
    expect(shellGeometry().triangles).toBe(80);
  });
});

describe("shell instances", () => {
  it("turns card plants into crowns: one each, a huangshan pine 3 to 5 pads", () => {
    const plants = forest(400);
    const inst = shellInstances(parseVeg(vegFile(plants)), FAMILIES);
    expect(inst.cards).toBe(400);
    expect(inst.plants).toBe(400);
    const pines = plants.filter((p) => p.family === F["pine.huangshan.v1"]);
    const pads = pines.reduce((a, p) => a + padCount(vegSeed(f32(p.x), f32(p.y), f32(p.z))), 0);
    expect(inst.plantsByArchetype.huangshan).toBe(pines.length);
    expect(inst.byArchetype.huangshan).toBe(pads);
    expect(pads).toBeGreaterThanOrEqual(pines.length * 3);
    expect(pads).toBeLessThanOrEqual(pines.length * 5);
    // Every pad count shows up.
    expect(new Set(pines.map((p) => padCount(vegSeed(f32(p.x), f32(p.y), f32(p.z))))).size).toBe(3);
    expect(inst.byArchetype.shrub).toBe(plants.filter((p) => FAMILIES[p.family].startsWith("shrub.")).length);
    expect(inst.byArchetype.broadleaf + inst.byArchetype.masson + inst.byArchetype.bamboo + inst.byArchetype.blossom).toBe(
      plants.filter((p) => ["pine.broadleaf.v3", "pine.masson.v2", "bamboo.culm.v0", "blossom.peach.v0"].includes(FAMILIES[p.family])).length,
    );
    expect(inst.count).toBe(Object.values(inst.byArchetype).reduce((a, b) => a + b, 0));
    expect(inst.center.length).toBe(inst.count * 3);
    expect(inst.shape.length).toBe(inst.count * 4);
    expect(inst.params.length).toBe(inst.count * 4);
    expect(inst.depth.length).toBe(inst.count * SHELL_STRIDE.depth);
  });

  it("leaves near meshes out, and keeps the cards of click targets and unknown families (counted)", () => {
    const inst = shellInstances(
      parseVeg(
        vegFile([
          { x: 0, y: 0, z: 0, h: 10, r: 3, family: F["pine.broadleaf.v3"], flags: VEG_FLAG.mesh },
          { x: 5, y: 0, z: 0, h: 10, r: 3, family: F["pine.broadleaf.v3"], flags: VEG_FLAG.hotspot },
          { x: 9, y: 0, z: 0, h: 10, r: 3, family: F["pine.cliff.v0"] },
          { x: 9, y: 0, z: 5, h: 10, r: 3, family: F["pine.cliff.v0"] },
          { x: 13, y: 0, z: 0, h: 0, r: 3, family: F["pine.broadleaf.v3"] },
          { x: 20, y: 0, z: 0, h: 10, r: 3, family: F["pine.broadleaf.v3"] },
        ]),
      ),
      FAMILIES,
    );
    expect(inst.cards).toBe(5);
    expect(inst.plants).toBe(1);
    expect(inst.count).toBe(1);
    expect(inst.skipped).toEqual({ hotspot: 1, invalid: 1, families: { "pine.cliff.v0": 2 } });
    const empty = shellInstances(parseVeg(vegFile([])), FAMILIES);
    expect(empty.count).toBe(0);
    expect(empty.bounds).toBeNull();
  });

  it("puts a single crown's top at the foot + height, over the upper 60 % (shrubs: all of it, on the ground)", () => {
    const foot = { x: 31.5, y: 102.25, z: -44 };
    for (const name of ["pine.broadleaf.v3", "pine.masson.v2", "bamboo.culm.v0", "blossom.peach.v0", "shrub.green.v1", "shrub.scrub.v0"]) {
      const h = 16;
      const r = name.startsWith("pine.broadleaf") || name.startsWith("blossom") ? 7 : 3;
      const [c] = crowns(one({ ...foot, h, r, family: F[name], yaw: 32, sun: 128 }));
      expect(c.c[1] + c.ry, name).toBeCloseTo(foot.y + h, 3);
      if (name.startsWith("shrub.")) expect(c.c[1] - c.ry, name).toBeCloseTo(foot.y, 3);
      else expect(c.c[1] - c.ry, name).toBeCloseTo(foot.y + 0.4 * h, 3);
      expect(c.c[0]).toBeCloseTo(foot.x, 4);
      expect(c.c[2]).toBeCloseTo(foot.z, 4);
      expect(Math.max(c.rx, c.rz), name).toBeLessThanOrEqual(r + 1e-6);
      expect(c.yaw).toBeCloseTo(vegYaw(32), 6);
      expect(c.sun).toBeCloseTo(128 / 255, 6);
      expect(VEG_TONES[c.tone]).toBe(vegTone(name, vegArchetype(name)!));
    }
  });

  it("keeps a broadleaf wider than tall and a masson pine a narrow spire", () => {
    const [broad] = crowns(one({ x: 0, y: 0, z: 0, h: 20, r: 4, family: F["pine.broadleaf.v3"] }));
    expect(broad.ry).toBeLessThanOrEqual(broad.rx * 0.8 + 1e-6);
    expect(broad.c[1] + broad.ry).toBeCloseTo(20, 4);
    const [spire] = crowns(one({ x: 0, y: 0, z: 0, h: 20, r: 6, family: F["pine.masson.v2"] }));
    expect(spire.rx).toBeLessThanOrEqual(spire.ry * 0.5 + 1e-6);
    expect(spire.taper).toBeGreaterThan(0);
    expect(broad.taper).toBe(0);
  });

  it("sizes crowns as round 57 did: no widening to make up for bites (round 58's were taken out)", () => {
    expect("rim" in VEG_LOOK).toBe(false);
    // A broadleaf of radius 4 and height 14: its seeded width share, the upper 60 % of the height, at most 0.8 tall for its width.
    const p = { x: 3, y: 10, z: -4, h: 14, r: 4, family: F["pine.broadleaf.v3"] };
    const [c] = crowns(one(p));
    const share = VEG_LOOK.crown.widthVary[0] + (VEG_LOOK.crown.widthVary[1] - VEG_LOOK.crown.widthVary[0]) * seedRandom(vegSeed(p.x, p.y, p.z), 3);
    expect(c.rx).toBeCloseTo(p.r * share, 5);
    expect(c.ry).toBeCloseTo(Math.min(0.6 * p.h * 0.5, c.rx * 0.8), 5);
    // A huangshan pine's lowest pad is 0.62 of the tree's radius, its top one 0.4.
    const pads = crowns(one({ x: 3, y: 10, z: -4, h: 14, r: 4, family: F["pine.huangshan.v1"] }));
    expect(pads[0].rx).toBeCloseTo(4 * VEG_LOOK.pads.size[0], 5);
    expect(pads[pads.length - 1].rx).toBeCloseTo(4 * VEG_LOOK.pads.size[1], 5);
  });

  it("spreads a huangshan pine's flat pads from 45 % to the top, largest lowest, inside the tree's box", () => {
    const plants = forest(900).filter((p) => p.family === F["pine.huangshan.v1"]);
    expect(plants.length).toBeGreaterThan(50);
    for (const p of plants) {
      const inst = one(p);
      const pads = crowns(inst);
      expect(pads.length).toBeGreaterThanOrEqual(3);
      expect(pads.length).toBeLessThanOrEqual(5);
      const x = f32(p.x);
      const y = f32(p.y);
      const z = f32(p.z);
      expect(pads[0].c[1] - y).toBeGreaterThanOrEqual(0.45 * p.h - 1e-3);
      expect(pads[pads.length - 1].c[1] + pads[pads.length - 1].ry - y).toBeCloseTo(p.h, 3);
      for (let k = 0; k < pads.length; k++) {
        const d = pads[k];
        expect(d.ry).toBeCloseTo(d.rx * VEG_LOOK.pads.thickness, 5);
        expect(d.rz).toBeLessThanOrEqual(d.rx + 1e-6);
        expect(Math.hypot(d.c[0] - x, d.c[2] - z) + Math.max(d.rx, d.rz)).toBeLessThanOrEqual(p.r + 1e-3);
        expect(d.c[1] - d.ry).toBeGreaterThanOrEqual(y - 1e-3);
        expect(d.c[1] + d.ry).toBeLessThanOrEqual(y + p.h + 1e-3);
        if (k > 0) {
          expect(d.rx).toBeLessThan(pads[k - 1].rx);
          expect(d.c[1]).toBeGreaterThan(pads[k - 1].c[1]);
        }
      }
      // The pads lean off the trunk: not all stacked on its line.
      expect(Math.max(...pads.map((d) => Math.hypot(d.c[0] - x, d.c[2] - z)))).toBeGreaterThan(0);
    }
  });

  it("bounds every crown with its lumps", () => {
    const inst = shellInstances(parseVeg(vegFile(forest(300))), FAMILIES);
    const b = inst.bounds!;
    for (const c of crowns(inst)) {
      const e = Math.max(c.rx, c.ry, c.rz) * (1 + VEG_LOOK.displace.amount);
      expect(Math.hypot(c.c[0] - b.center[0], c.c[1] - b.center[1], c.c[2] - b.center[2]) + e).toBeLessThanOrEqual(b.radius + 1e-3);
      for (let k = 0; k < 3; k++) {
        expect(c.c[k] - e).toBeGreaterThanOrEqual(b.min[k] - 1e-3);
        expect(c.c[k] + e).toBeLessThanOrEqual(b.max[k] + 1e-3);
      }
    }
  });

  it("seeds each plant from its position: the same every run and in any order", () => {
    const plants = forest(200);
    const a = shellInstances(parseVeg(vegFile(plants)), FAMILIES);
    const b = shellInstances(parseVeg(vegFile(plants)), FAMILIES);
    expect([...a.params]).toEqual([...b.params]);
    expect([...a.center]).toEqual([...b.center]);
    const r = shellInstances(parseVeg(vegFile([...plants].reverse())), FAMILIES);
    const key = (c: { c: Vec3 }) => c.c.map((v) => v.toFixed(3)).join(",");
    const seedsA = new Map(crowns(a).map((c) => [key(c), c.seed]));
    for (const c of crowns(r)) expect(seedsA.get(key(c))).toBe(c.seed);
    // Rounded to 10 cm: a re-export that moves a plant by a few millimetres keeps its seed.
    expect(vegSeed(12.3, 40.02, -7.81)).toBe(vegSeed(12.302, 40.019, -7.808));
    expect(vegSeed(12.3, 40.02, -7.81)).not.toBe(vegSeed(12.6, 40.02, -7.81));
    const seeds = crowns(a).map((c) => c.seed);
    expect(new Set(seeds).size).toBeGreaterThan(seeds.length * 0.95);
    for (const s of seeds) {
      expect(s).toBeGreaterThanOrEqual(0);
      expect(s).toBeLessThan(1);
    }
    expect(seedRandom(0.25, 3)).toBe(seedRandom(0.25, 3));
    expect(seedRandom(0.25, 3)).not.toBe(seedRandom(0.25, 4));
  });
});

describe("depth among crowns", () => {
  const D = VEG_LOOK.depth;
  /** A crown by its top. */
  const crown = (x: number, z: number, top: number, ry: number, rh: number): DepthCrown => ({ x, y: top - ry, z, ry, rh });
  const sun = depthSun(SUN)!;

  it("reads the sun as a level direction and a rise: 7 degrees, toward -x", () => {
    expect(Math.hypot(sun.dx, sun.dz)).toBeCloseTo(1, 9);
    expect((Math.atan(sun.rise) * 180) / Math.PI).toBeCloseTo(7, 1);
    expect(sun.dx).toBeLessThan(-0.9);
    expect(depthSun(null)).toBeNull();
    expect(depthSun([0.5, -0.1, 0.2])).toBeNull();
    expect(depthSun([0, 1, 0])).toBeNull();
  });

  it("sinks a crown under a taller neighbour within its radius, less the farther it stands", () => {
    const a = crown(0, 0, 10, 3, 5);
    // 3 m taller is sinkRel of the crown's 6 m height: fully sunk, times 1 - 2/5 for the distance.
    expect(D.sinkRel * 2 * a.ry).toBeCloseTo(3, 9);
    expect(depthTerms(a, crown(2, 0, 13, 3, 5), null).sink).toBeCloseTo(0.6, 6);
    expect(depthTerms(a, crown(1, 0, 13, 3, 5), null).sink).toBeCloseTo(0.8, 6);
    expect(depthTerms(a, crown(1, 0, 11.5, 3, 5), null).sink).toBeCloseTo(0.4, 6);
    // Lower, or past the crown's radius: nothing.
    expect(depthTerms(a, crown(1, 0, 8, 3, 5), null).sink).toBe(0);
    expect(depthTerms(a, crown(0, D.reach * a.rh + 0.01, 20, 3, 5), null).sink).toBe(0);
  });

  it("shades the lower half from a neighbour toward the sun under the 7 degree sun, never from one away from it", () => {
    const a = crown(0, 0, 10, 3, 5);
    const toward = (along: number, side: number, top: number, ry = 3, rh = 5) => crown(sun.dx * along - sun.dz * side, sun.dz * along + sun.dx * side, top, ry, rh);
    // A twin 3 m toward the sun: its shadow drops 3 x rise and still covers the whole lower half.
    expect(depthTerms(a, toward(3, 0, 10), sun).shade).toBeCloseTo(1, 6);
    // The same twin away from the sun, or off to the side of the sun's line: no shadow.
    expect(depthTerms(a, toward(-3, 0, 10), sun).shade).toBe(0);
    expect(depthTerms(a, toward(3, 5.5, 10), sun).shade).toBe(0);
    // A shorter one: its shadow's top, 3 x rise lower again, covers half the lower half.
    const top = a.y - a.ry / 2 + 3 * sun.rise;
    expect(depthTerms(a, toward(3, 0, top, 1), sun).shade).toBeCloseTo(0.5, 6);
    // Too short to reach the lower half at all, or past sunReach.
    expect(depthTerms(a, toward(3, 0, a.y - a.ry, 1), sun).shade).toBe(0);
    expect(depthTerms(a, toward(D.sunReach * a.rh + 0.1, 0, 30), sun).shade).toBe(0);
    // No sun: no shade.
    expect(depthTerms(a, toward(3, 0, 10), null).shade).toBe(0);
  });

  it("is 1 - (1 - sink)(1 - shade) of the largest each, the grid finding every neighbour a search of all pairs finds", () => {
    const inst = shellInstances(parseVeg(vegFile(forest(300))), FAMILIES, { sun: SUN });
    const list = crowns(inst).map((c) => ({ x: c.c[0], y: c.c[1], z: c.c[2], ry: c.ry, rh: Math.max(c.rx, c.rz) }));
    for (let i = 0; i < list.length; i++) {
      let sink = 0;
      let shade = 0;
      for (let j = 0; j < list.length; j++) {
        if (j === i) continue;
        const t = depthTerms(list[i], list[j], sun);
        sink = Math.max(sink, t.sink);
        shade = Math.max(shade, t.shade);
      }
      expect(inst.depth[i]).toBe(f32(1 - (1 - sink) * (1 - shade)));
    }
    const d = [...inst.depth];
    for (const v of d) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(1);
    }
    // Both ends show up: crowns in the open and crowns deep in the stand.
    expect(d.filter((v) => v === 0).length).toBeGreaterThan(d.length * 0.05);
    expect(d.filter((v) => v > 0.5).length).toBeGreaterThan(d.length * 0.05);
  });

  /** Crowns packed as ShellInstances packs them (centre; rx, ry, rz, taper), and read back at float precision. */
  const pack = (list: DepthCrown[]) => {
    const center = new Float32Array(list.flatMap((c) => [c.x, c.y, c.z]));
    const shape = new Float32Array(list.flatMap((c) => [c.rh, c.ry, c.rh, 0]));
    const read = list.map((_, i): DepthCrown => ({ x: center[i * 3], y: center[i * 3 + 1], z: center[i * 3 + 2], ry: shape[i * 4 + 1], rh: shape[i * 4] }));
    return { center, shape, read };
  };
  /** Depth by a search of all pairs; `far`: pairs that shade from past the crown's own radius (sunReach of it). */
  const allPairs = (list: DepthCrown[]) => {
    let far = 0;
    const depth = list.map((a, i) => {
      let sink = 0;
      let shade = 0;
      for (let j = 0; j < list.length; j++) {
        if (j === i) continue;
        const t = depthTerms(a, list[j], sun);
        sink = Math.max(sink, t.sink);
        shade = Math.max(shade, t.shade);
        if (t.shade > 0 && Math.hypot(list[j].x - a.x, list[j].z - a.z) > Math.max(D.reach, D.sunReach) * a.rh) far++;
      }
      return f32(1 - (1 - sink) * (1 - shade));
    });
    return { depth, far };
  };

  it("finds a large neighbour that shades a small crown from across a grid line, farther than the small crown's radius", () => {
    // A 2 m crown, and a 10 m one 1.5 m toward the sun and 7.5 m off the sun's line: at about (1.89, 8.60), in the next cell.
    const along = 1.5;
    const side = -7.5;
    const p = pack([
      { x: 1, y: 9, z: 1, ry: 1, rh: 2 },
      { x: 1 + sun.dx * along - sun.dz * side, y: 9, z: 1 + sun.dz * along + sun.dx * side, ry: 5, rh: 10 },
    ]);
    const [a, b] = p.read;
    expect(Math.floor(b.z / D.gridM)).toBe(Math.floor(a.z / D.gridM) + 1);
    // A search of the small crown's own radius would stay in its own cell.
    expect(Math.floor((a.z + Math.max(D.reach, D.sunReach) * a.rh) / D.gridM)).toBe(Math.floor(a.z / D.gridM));
    // Its shadow covers the small crown's whole lower half, eased by how far it stands off the sun's line.
    const t = Math.min(Math.max((Math.abs(side) - D.sideFrom * b.rh) / (b.rh - D.sideFrom * b.rh), 0), 1);
    const wide = 1 - t * t * (3 - 2 * t);
    expect(wide).toBeGreaterThan(0);
    const got = vegDepth(p.center, p.shape, 2, SUN);
    expect(got[0]).toBeCloseTo(wide, 4);
    expect([...got]).toEqual(allPairs(p.read).depth);
  });

  it("matches a search of all pairs in a dense stand of mixed sizes (1,500 crowns, 2 to 8 m across, over 90 x 90 m)", () => {
    let s = 1;
    const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
    const list: DepthCrown[] = [];
    for (let i = 0; i < 1500; i++) {
      const rh = 2 + rnd() * 6;
      const ry = rh * (0.5 + rnd() * 0.4);
      list.push({ x: rnd() * 90, y: 20 + rnd() * 6 + ry, z: rnd() * 90, ry, rh });
    }
    const p = pack(list);
    const got = vegDepth(p.center, p.shape, list.length, SUN);
    const want = allPairs(p.read);
    expect(list.map((_, i) => i).filter((i) => got[i] !== want.depth[i])).toEqual([]);
    // The stand has larger neighbours shading from past a crown's own radius, the case a search of that radius misses.
    expect(want.far).toBeGreaterThan(0);
  });

  it("is the same in any order, nothing for a lone crown, and only the sink part with no sun", () => {
    const plants = forest(200);
    const a = shellInstances(parseVeg(vegFile(plants)), FAMILIES, { sun: SUN });
    const r = shellInstances(parseVeg(vegFile([...plants].reverse())), FAMILIES, { sun: SUN });
    const key = (c: { c: Vec3; rx: number }) => [...c.c, c.rx].map((v) => v.toFixed(3)).join(",");
    const depthA = new Map(crowns(a).map((c) => [key(c), c.depth]));
    for (const c of crowns(r)) expect(depthA.get(key(c))).toBe(c.depth);
    expect(crowns(one({ x: 0, y: 0, z: 0, h: 12, r: 4, family: F["pine.broadleaf.v3"] }))[0].depth).toBe(0);
    const noSun = shellInstances(parseVeg(vegFile(plants)), FAMILIES);
    for (let i = 0; i < a.count; i++) expect(noSun.depth[i]).toBeLessThanOrEqual(a.depth[i]);
    expect(vegDepth(new Float32Array(0), new Float32Array(0), 0, SUN).length).toBe(0);
  });
});

describe("the bough field", () => {
  const points = vegFieldSamples(500).map(([x, y, z], k) => [x * 0.037 + k * 0.011, y * 0.041, z * 0.029] as Vec3);

  it("is the leaves' value noise with its exact gradient", () => {
    const e = 1e-5;
    for (const [x, y, z] of points) {
      const [v, gx, gy, gz] = vegNoiseD(x, y, z);
      expect(Math.abs(v - vegNoise(x, y, z))).toBeLessThan(1e-12);
      expect(gx).toBeCloseTo((vegNoise(x + e, y, z) - vegNoise(x - e, y, z)) / (2 * e), 6);
      expect(gy).toBeCloseTo((vegNoise(x, y + e, z) - vegNoise(x, y - e, z)) / (2 * e), 6);
      expect(gz).toBeCloseTo((vegNoise(x, y, z + e) - vegNoise(x, y, z - e)) / (2 * e), 6);
    }
    const g = vegNoiseDGlsl();
    expect(g).toContain("vec4 sectVegNoiseD( vec3 x ) {");
    expect(g).toContain("vec3 u = w * w * ( 3.0 - 2.0 * w );");
    expect(g).toContain("vec3 du = 6.0 * w * ( 1.0 - w );");
    expect(g).toContain("float k7 = - a + b + c - d + e - f - g + h;");
  });

  it("turns its lattice off the crown's axes, and its gradient back through the transpose", () => {
    const R = VEG_BOUGH_TURN;
    // Orthonormal, determinant 1.
    for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) expect(R[i][0] * R[j][0] + R[i][1] * R[j][1] + R[i][2] * R[j][2]).toBeCloseTo(i === j ? 1 : 0, 12);
    const det = R[0][0] * (R[1][1] * R[2][2] - R[1][2] * R[2][1]) - R[0][1] * (R[1][0] * R[2][2] - R[1][2] * R[2][0]) + R[0][2] * (R[1][0] * R[2][1] - R[1][1] * R[2][0]);
    expect(det).toBeCloseTo(1, 12);
    // No lattice plane is level (none of the lattice's axes is near the crown's up), and up crosses the cells on a slant.
    for (const row of R) expect(Math.abs(row[1])).toBeLessThan(0.9);
    // The gradient of the noise of R p / cell, by central differences.
    const e = 1e-5;
    for (const cell of [1.5, 2.7]) {
      const h = (x: number, y: number, z: number) => vegNoise(...(R.map((r) => (r[0] * x + r[1] * y + r[2] * z) / cell) as [number, number, number]));
      for (const [x, y, z] of points.slice(0, 200)) {
        const [v, gx, gy, gz] = vegBough(x, y, z, cell);
        expect(Math.abs(v - h(x, y, z))).toBeLessThan(1e-12);
        expect(gx).toBeCloseTo((h(x + e, y, z) - h(x - e, y, z)) / (2 * e), 6);
        expect(gy).toBeCloseTo((h(x, y + e, z) - h(x, y - e, z)) / (2 * e), 6);
        expect(gz).toBeCloseTo((h(x, y, z + e) - h(x, y, z - e)) / (2 * e), 6);
      }
    }
    // GLSL fills a mat3 column by column: column k holds R[0][k], R[1][k], R[2][k].
    const nums = /mat3\( (.+) \);/.exec(vegTurnGlsl())![1].split(", ").map(Number);
    expect(nums).toEqual([0, 1, 2].flatMap((c) => [0, 1, 2].map((r) => R[r][c])));
  });

  /** The median tilt of the normal (degrees) for a lean of `bump`, over directions spread on the sphere. */
  function medianTilt(bump: number): number {
    const tilts: number[] = [];
    const n = 4000;
    const pts = vegFieldSamples(n);
    for (let k = 0; k < n; k++) {
      // Directions spread over the sphere.
      const y = 1 - (2 * (k + 0.5)) / n;
      const r = Math.sqrt(1 - y * y);
      const N: Vec3 = [r * Math.cos(k * 2.399963), y, r * Math.sin(k * 2.399963)];
      const [, gx, gy, gz] = vegBough(...pts[k], 1);
      const gd = gx * N[0] + gy * N[1] + gz * N[2];
      const t = [gx - gd * N[0], gy - gd * N[1], gz - gd * N[2]].map((v) => v * bump);
      tilts.push((Math.atan(Math.hypot(t[0], t[1], t[2])) * 180) / Math.PI);
    }
    tilts.sort((a, b) => a - b);
    return tilts[n / 2];
  }

  it("leans the normal a median of 8 to 12 degrees at full strength (round 58: about 15), a third of that large on screen", () => {
    const B = VEG_LOOK.boughs;
    expect(B.bump).toBe(0.45);
    expect(medianTilt(0.7)).toBeGreaterThan(13);
    const full = medianTilt(B.bump);
    expect(full).toBeGreaterThan(8);
    expect(full).toBeLessThan(12);
    const near = medianTilt(B.bump * B.near);
    expect(near).toBeGreaterThan(2.5);
    expect(near).toBeLessThan(4.5);
  });

  it("keeps the crease's mean brightness at every strength: 1 - (1 - dark)(1 - mean share), checked over the field", () => {
    const B = VEG_LOOK.boughs;
    const s = vegFieldSamples(20000).map(([x, y, z]) => vegCreaseShare(vegBough(x, y, z, 1)[0]));
    const { creaseShare } = vegBoughMeans();
    // vegBoughMeans averages the same points.
    expect(creaseShare).toBeCloseTo(s.reduce((a, b) => a + b, 0) / s.length, 12);
    expect(creaseShare).toBeGreaterThan(0.3);
    expect(creaseShare).toBeLessThan(0.9);
    for (const dark of [B.dark, 0.6, 1]) {
      const want = 1 - (1 - dark) * (1 - creaseShare);
      for (const k of [0, B.near, 0.6, 1]) {
        const mean = s.reduce((a, v) => a + vegCrease(v, k, creaseShare, dark), 0) / s.length;
        expect(Math.abs(mean - want), `dark ${dark}, strength ${k}`).toBeLessThan(1e-9);
      }
    }
    // At full strength: dark in the deepest crease, full on a bough. At none: the mean everywhere. 1: no crease.
    expect(vegCrease(0, 1, creaseShare)).toBeCloseTo(B.dark, 12);
    expect(vegCrease(1, 1, creaseShare)).toBe(1);
    expect(vegCrease(0, 0, creaseShare)).toBeCloseTo(vegCrease(1, 0, creaseShare), 12);
    expect(vegCrease(0, 1, creaseShare, 1)).toBe(1);
    expect(vegCreaseShare(0)).toBe(0);
    expect(vegCreaseShare(1)).toBe(1);
    // Softer than round 58's 0.7.
    expect(B.dark).toBe(0.8);
  });

  it("eases the boughs off when a cell is large on screen: all of them up to 12 px, `near` of them from 36 px", () => {
    const B = VEG_LOOK.boughs;
    expect(B.px).toEqual([12, 36]);
    expect(B.near).toBe(0.35);
    for (const px of [0, 3, 12]) expect(vegBoughNear(px)).toBe(1);
    for (const px of [36, 80, 1e6]) expect(vegBoughNear(px)).toBeCloseTo(B.near, 12);
    expect(vegBoughNear(24)).toBeCloseTo((1 + B.near) / 2, 12);
    for (let px = 12; px < 36; px += 2) expect(vegBoughNear(px + 2)).toBeLessThanOrEqual(vegBoughNear(px));
    // The uniform's z sets the far end.
    expect(vegBoughNear(50, 1)).toBe(1);
    expect(vegBoughNear(50, 0)).toBe(0);
  });

  it("seeds bough cells from 1.3 to 3.4 m, so lumps differ more from crown to crown than round 58's 1.5 to 3", () => {
    expect(VEG_LOOK.boughs.cellM).toEqual([1.3, 3.4]);
    expect(VEG_LOOK.boughs.cellM[1] / VEG_LOOK.boughs.cellM[0]).toBeGreaterThan(3 / 1.5);
  });

  it("takes its run-time strength from one uniform: lean 0.45, deepest crease 0.8, 0.35 kept large on screen, w unused", () => {
    expect(vegBoughUniform()).toEqual([0.45, 0.8, 0.35, 0]);
    const B = VEG_LOOK.boughs;
    expect(vegBoughUniform()).toEqual([B.bump, B.dark, B.near, 0]);
  });
});

describe("depth on a flat pad", () => {
  /**
   * The share of a huangshan pad's top, seen from straight above, that counts as lower half, by the shader's
   * deep line: area spread evenly over the pad's disc, a pad 0.18 as thick as it is wide.
   */
  function lowerShare(byUnit: boolean): number {
    const [lo, hi] = VEG_LOOK.depth.low;
    const ss = (x: number) => {
      const t = Math.min(Math.max((x - lo) / (hi - lo), 0), 1);
      return t * t * (3 - 2 * t);
    };
    const th = VEG_LOOK.pads.thickness;
    const n = 20000;
    let sum = 0;
    for (let k = 0; k < n; k++) {
      const rho = Math.sqrt((k + 0.5) / n);
      const a = k * 2.399963;
      // The unit shell's point over this spot of the disc (upper half), and the pad's point.
      const u: Vec3 = [rho * Math.cos(a), Math.sqrt(1 - rho * rho), rho * Math.sin(a)];
      const p: Vec3 = [u[0], u[1] * th, u[2]];
      const y = byUnit ? u[1] : p[1] / Math.hypot(p[0], p[1], p[2]);
      sum += 1 - ss(y);
    }
    return sum / n;
  }

  it("keeps a pad's top lit: by the height on the shell about 1 % of it counts as lower half, against about a fifth before", () => {
    expect(VEG_LOOK.pads.thickness).toBeCloseTo(0.18, 9);
    // Round 58 went by the direction from the pad's centre, which is near level over most of a flat pad: 0.19.
    const byCentre = lowerShare(false);
    expect(byCentre).toBeGreaterThan(0.15);
    // By the height on the unit shell only the pad's very rim counts: 0.012.
    const byHeight = lowerShare(true);
    expect(byHeight).toBeLessThan(0.02);
    expect(byHeight).toBeLessThan(byCentre / 10);
  });
});

describe("the ragged edge", () => {
  /** The share of a round crown's face-on disc the edge keeps: two octaves of a fine noise over a threshold rising toward the edge. */
  function kept(n = 40000): number {
    const E = VEG_LOOK.erosion;
    const pts = vegFieldSamples(n);
    let k2 = 0;
    for (let k = 0; k < n; k++) {
      // Spread evenly over the disc's area.
      const rho = Math.sqrt((k + 0.5) / n);
      const facing = Math.sqrt(1 - rho * rho);
      const t = Math.min(Math.max((1 - facing - E.from) / (1 - E.from), 0), 1);
      const thr = t * t * (3 - 2 * t) * E.max;
      const [x, y, z] = pts[(k * 7919) % n];
      const en = vegNoise(x, y, z) * 0.65 + vegNoise(x * 2.31 + 7.7, y * 2.31 + 3.1, z * 2.31 + 5.3) * 0.35;
      if (en >= thr) k2++;
    }
    return k2 / n;
  }

  it("is round 57's again: fine cells, nothing cut facing the camera, about a tenth of the face-on disc cut near the edge", () => {
    expect(VEG_LOOK.erosion).toEqual({ cellM: 0.45, cellRel: 0.08, from: 0.3, max: 0.85 });
    const s = kept();
    expect(s).toBeGreaterThan(0.88);
    expect(s).toBeLessThan(0.92);
  });
});

describe("the ?veg= switch and the tier", () => {
  it("reads ?veg= from the query string", () => {
    expect(parseVegParam("")).toBeNull();
    expect(parseVegParam("?veg=0")).toBe("off");
    expect(parseVegParam("?veg=off")).toBe("off");
    expect(parseVegParam("?veg=1")).toBe("on");
    expect(parseVegParam("?veg=on")).toBe("on");
    expect(parseVegParam("?debug=1&veg=1")).toBe("on");
    expect(parseVegParam("?veg=0&tier=high")).toBe("off");
    expect(parseVegParam("?veg=2")).toBeNull();
    expect(parseVegParam("?veg=")).toBeNull();
    expect(parseVegParam("?soveg=1")).toBeNull();
    expect(parseVegParam("#veg=1")).toBeNull();
  });

  it("draws shells on High, cards elsewhere, unless the link says otherwise; never with the cards off", () => {
    expect(vegShellsOn(tierQuality("high", 1), null)).toBe(true);
    expect(vegShellsOn(tierQuality("mid", 1), null)).toBe(false);
    expect(vegShellsOn(tierQuality("low", 1), null)).toBe(false);
    expect(vegShellsOn(tierQuality("high", 1), "off")).toBe(false);
    expect(vegShellsOn(tierQuality("low", 1), "on")).toBe(true);
    expect(vegShellsOn(tierQuality("mid", 1), "on")).toBe(true);
    expect(vegShellsOn({ ...tierQuality("high", 1), noCards: true }, null)).toBe(false);
    expect(vegShellsOn({ ...tierQuality("high", 1), noCards: true }, "on")).toBe(false);
    expect(vegShellsOn({ ...tierQuality("high", 1), vegShells: undefined }, null)).toBe(false);
  });
});

describe("the shell shaders", () => {
  const vs = vegVertexGlsl();
  const fs = vegFragmentGlsl();
  const L = VEG_LOOK;

  it("place the unit shell by its instance and make it lumpy by a noise of the shell position and seed", () => {
    for (const a of ["attribute vec3 iCenter;", "attribute vec4 iShape;", "attribute vec4 iParams;", "attribute float iDepth;"]) expect(vs).toContain(a);
    expect(count(vs, "float sectVegNoise( vec3 x )")).toBe(1);
    expect(vs).toContain(`float lump = ( sectVegNoise( n0 * ${glslFloat(L.displace.scale)} + so ) - 0.5 ) * 2.0 * ${glslFloat(L.displace.amount)};`);
    expect(L.displace.amount).toBeCloseTo(0.27, 9);
    expect(vs).toContain("vec3 shellP = n0 * ( 1.0 + lump ) * r * vec3( narrow, 1.0, narrow );");
    expect(vs).toContain("iCenter + sectVegYaw( shellP, iParams.x )");
    // The palette: 4 colours a tone.
    expect(vs).toContain(`const vec3 SECT_VEG_PALETTE[ ${VEG_TONES.length * 4} ]`);
    // Fogged like the baked surfaces: three's fog chunks (the page's haze), after the position.
    expect(vs).toContain("#include <fog_pars_vertex>");
    expect(vs.indexOf("#include <fog_vertex>")).toBeGreaterThan(vs.indexOf("gl_Position = projectionMatrix * mvPosition;"));
    for (const s of [vs, fs]) expect(s).not.toMatch(/NaN|undefined|Infinity/);
  });

  it("draw the boughs from a turned lattice in the crown's own frame (never screen space), its cell seeded per crown", () => {
    expect(count(fs, "vec4 sectVegNoiseD( vec3 x )")).toBe(1);
    expect(vs).not.toContain("sectVegNoiseD");
    expect(count(fs, "const mat3 SECT_VEG_TURN")).toBe(1);
    expect(fs).toContain(vegTurnGlsl());
    expect(fs).toContain("vec4 bough = sectVegNoiseD( SECT_VEG_TURN * ( vVegLocal / vVegInfo.y ) );");
    const B = L.boughs;
    expect(vs).toContain(`float boughM = min( mix( ${glslFloat(B.cellM[0])}, ${glslFloat(B.cellM[1])}, h1 ), rMax * ${glslFloat(B.maxRel)} );`);
    expect(vs).toContain(`mix( ${glslFloat(1.3)}, ${glslFloat(3.4)}, h1 )`);
    expect(vs).toContain("vVegInfo = vec4( iParams.z, boughM, iDepth, iParams.x );");
    expect(fs).not.toContain("gl_FragCoord");
    // Faded flat by the pixel's shorter side.
    expect(fs).toContain("float pxIso = max( min( length( dFdx( vVegLocal ) ), length( dFdy( vVegLocal ) ) ), 1e-5 );");
    expect(fs).toContain(`float boughFade = 1.0 - smoothstep( ${glslFloat(B.fade[0])} * vVegInfo.y, ${glslFloat(B.fade[1])} * vVegInfo.y, pxIso );`);
  });

  it("take the boughs' strength from the shared uniform, eased off by the cell's size in pixels (vegBoughNear)", () => {
    const B = L.boughs;
    expect(count(fs, "uniform vec4 uVegBough;")).toBe(1);
    expect(vs).not.toContain("uVegBough");
    expect(fs).toContain("float cellPx = vVegInfo.y / pxIso;");
    expect(fs).toContain(`float boughNear = mix( 1.0, uVegBough.z, smoothstep( ${glslFloat(B.px[0])}, ${glslFloat(B.px[1])}, cellPx ) );`);
    expect(fs).toContain("float boughK = boughFade * boughNear;");
    // The lean and the crease read the uniform, not the look's numbers.
    expect(fs).toContain("vec3 slope = ( bough.yzw * SECT_VEG_TURN ) * boughK;");
    expect(fs).toContain("N = normalize( N - uVegBough.x * ( slope - dot( slope, N ) * N ) );");
    expect(fs).not.toContain("boughFade );");
    expect(fs).not.toContain(`N = normalize( N - ${glslFloat(B.bump)}`);
    // Every name is declared once.
    for (const name of ["float cellPx", "float boughNear", "float boughK", "float creaseS", "float crease ", "vec4 bough "]) expect(count(fs, name), name).toBe(1);
  });

  it("darken the creases around the field's mean, so the brightness holds at every strength (vegCrease)", () => {
    const B = L.boughs;
    const { creaseShare } = vegBoughMeans();
    expect(fs).toContain(`float creaseS = smoothstep( ${glslFloat(B.crease[0])}, ${glslFloat(B.crease[1])}, bough.x );`);
    expect(fs).toContain(`float crease = 1.0 - ( 1.0 - uVegBough.y ) * ( 1.0 - mix( ${glslFloat(creaseShare)}, creaseS, boughK ) );`);
    expect(fs.indexOf("float creaseS")).toBeGreaterThan(fs.indexOf("float boughK"));
    expect(fs.indexOf("float crease =")).toBeLessThan(fs.indexOf("* crease *"));
  });

  it("erode a ragged silhouette from object-space noise, never screen space", () => {
    const E = L.erosion;
    expect(fs).toContain("float facing = abs( dot( Ns, V ) );");
    expect(fs).toContain("vec3 qe = vVegLocal / vVegEdgeM;");
    expect(fs).toContain("float en = sectVegNoise( qe ) * 0.65 + sectVegNoise( qe * 2.31 + vec3( 7.7, 3.1, 5.3 ) ) * 0.35;");
    expect(fs).toContain(`float thr = smoothstep( ${glslFloat(E.from)}, 1.0, 1.0 - facing ) * ${glslFloat(E.max)};`);
    expect(fs).toContain("float alpha = clamp( ( en - thr ) / max( fwidth( en ), 1e-4 ) + 0.5, 0.0, 1.0 );");
    expect(fs).toContain("if ( en < thr ) discard;");
    expect(fs).toContain("#ifdef ALPHA_TO_COVERAGE");
    expect(fs).not.toContain("gl_FragCoord");
    expect(fs.indexOf("discard")).toBeLessThan(fs.indexOf("float wrap"));
    // The cells: max(0.45 m, 0.08 of the crown's radius), worked out per vertex as in round 57.
    expect(vs).toContain(`vVegEdgeM = max( ${glslFloat(E.cellM)}, rMax * ${glslFloat(E.cellRel)} );`);
    for (const s of [vs, fs]) expect(s).toContain("varying float vVegEdgeM;");
    // Round 58's bites are gone: no projected radius, nothing cut by the bough field.
    for (const gone of ["float rho", "float rim", "float edge", "rho > rim"]) expect(fs).not.toContain(gone);
    // Derivatives are taken before the cut.
    expect(fs.indexOf("float pxIso")).toBeLessThan(fs.indexOf("discard"));
  });

  it("light the crown: normal leant down the boughs' slope, wrap sun times the plant's sun, sky ambient, occlusion, light through the leaves, no specular", () => {
    expect(fs).toContain(`vec3 N = normalize( mix( Ns, Nc, ${glslFloat(L.normal.round)} ) );`);
    expect(fs).toContain("vec3 Nc = normalize( vVegWorld - vVegCenter );");
    // The slope turned back off the lattice (the transpose), then by the crown's yaw: the vertex stage's sectVegYaw.
    expect(fs).toContain("vec3 slope = ( bough.yzw * SECT_VEG_TURN ) * boughK;");
    expect(fs).toContain("float yawC = cos( vVegInfo.w );");
    expect(fs).toContain("slope = vec3( slope.x * yawC + slope.z * yawS, slope.y, - slope.x * yawS + slope.z * yawC );");
    expect(vs).toContain("return vec3( v.x * c + v.z * s, v.y, - v.x * s + v.z * c );");
    expect(fs).toContain("N = normalize( N - uVegBough.x * ( slope - dot( slope, N ) * N ) );");
    expect(L.light.wrap).toBeCloseTo(0.5, 9);
    // Lit from the bake's key light (higher than the sun), with a floor under the plant's own low-sun value.
    expect(fs).toContain(`vec3 key = normalize( uVegSun + vec3( 0.0, ${glslFloat(L.light.lift)}, 0.0 ) );`);
    expect(fs).toContain(`float wrap = clamp( ( dot( N, key ) + ${glslFloat(L.light.wrap)} ) / ( 1.0 + ${glslFloat(L.light.wrap)} ), 0.0, 1.0 );`);
    expect(fs).toContain(`wrap * mix( ${glslFloat(L.light.floor)}, 1.0, vVegInfo.x ) * ${glslFloat(L.light.sun)} * ( 1.0 - deep * ${glslFloat(L.depth.shadow)} ), 0.0, 1.0 );`);
    expect(L.light.floor).toBeGreaterThan(0.2);
    expect(L.light.floor).toBeLessThan(0.7);
    expect(fs).toContain(`col *= ${glslFloat(L.light.gain)};`);
    expect(fs).toContain("vec3 amb = mix(");
    // A deep crown (vegDepth) loses sun and brightness on its lower half only: by the height on the unit shell (a
    // flat pad's top stays its top). The underside's occlusion still goes by the direction from the centre.
    expect(fs).toContain(`float deep = vVegInfo.z * ( 1.0 - smoothstep( ${glslFloat(L.depth.low[0])}, ${glslFloat(L.depth.low[1])}, normalize( vVegUnit ).y ) );`);
    expect(fs).toContain(`float under = smoothstep( ${glslFloat(L.occlusion.underRange[0])}, ${glslFloat(L.occlusion.underRange[1])}, Nc.y );`);
    for (const s of [vs, fs]) expect(s).toContain("varying vec3 vVegUnit;");
    expect(vs).toContain("vVegUnit = n0;");
    expect(vs.indexOf("vVegUnit = n0;")).toBeGreaterThan(vs.indexOf("vec3 n0 = normalize( position );"));
    expect(L.depth.low[0]).toBeLessThan(0);
    expect(L.depth.low[1]).toBeLessThanOrEqual(0.35);
    expect(L.depth.shadow).toBeLessThan(1);
    expect(L.depth.dark).toBeLessThan(0.5);
    expect(fs).toContain(
      `col *= mix( ${glslFloat(L.occlusion.under)}, 1.0, under ) * crease * ( 1.0 - deep * ${glslFloat(L.depth.dark)} ) * mix( ${glslFloat(L.leaves.dark)}, ${glslFloat(L.leaves.bright)}, leaf );`,
    );
    // Leaves: two brightness fields, each faded out before its cells shrink under a couple of pixels.
    expect(fs).toContain("float pxM = length( fwidth( vVegLocal ) );");
    expect(fs).toContain(`sectVegNoise( vVegLocal / ${glslFloat(L.leaves.fineM)} + vec3( 3.3, 9.1, 1.7 ) )`);
    expect(fs).toContain(`sectVegNoise( vVegLocal / ${glslFloat(L.leaves.coarseM)} + vec3( 11.9, 2.3, 7.1 ) )`);
    expect(L.leaves.fineM).toBeLessThan(L.leaves.coarseM);
    expect(L.leaves.dark).toBeLessThan(1);
    expect(L.leaves.bright).toBeGreaterThan(1);
    expect(fs).toContain("float toward = pow( max( dot( - V, uVegSun ), 0.0 ), ");
    expect(fs).not.toMatch(/specular|reflect\(/i);
  });

  describe("a crown's brightness against round 57's", () => {
    // A TypeScript mirror of the lighting (broadleaf tone, full plant sun, leaves at their far mean), weighted by
    // projected area over a round crown's visible half, inside the ragged edge (the same in both rounds). Round 57:
    // three noises tilting the normal by 1, gaps keeping 0.8, gain 1.22. Now: the lean at strength k, the crease at
    // strength k, depth by the height on the shell (on a round crown, the normal's y). 0.6 is about the mean depth
    // over the twelve plant lists with the scene's sun.
    const ss = (a: number, b: number, x: number) => {
      const t = Math.min(Math.max((x - a) / (b - a), 0), 1);
      return t * t * (3 - 2 * t);
    };
    const mix = (a: number, b: number, t: number) => a + (b - a) * t;
    const norm = (v: Vec3): Vec3 => {
      const l = Math.hypot(v[0], v[1], v[2]);
      return [v[0] / l, v[1] / l, v[2] / l];
    };
    const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    const lum = (hex: string) => {
      const c = hexToLinear(hex);
      return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
    };
    const P = L.palettes.broadleaf.map(lum);
    const key = norm([SUN[0], SUN[1] + L.light.lift, SUN[2]]);
    const light = (N: Vec3, N0: Vec3, sunK: number) => {
      const wrap = Math.min(Math.max((dot(N, key) + L.light.wrap) / (1 + L.light.wrap), 0), 1);
      return mix(mix(P[0], P[1], 0.5), mix(P[2], P[3], ss(L.light.lit[0], L.light.lit[1], N[1])), wrap * sunK) * mix(L.occlusion.under, 1, ss(L.occlusion.underRange[0], L.occlusion.underRange[1], N0[1]));
    };
    const n = 20000;
    const pts = vegFieldSamples(n);
    const { creaseShare } = vegBoughMeans();
    const ELEVATIONS = [10, 25, 45, 70];
    /** Mean brightness seen from `elev` degrees above: round 57's, or now's at bough strength k and depth `depth`. */
    const bright = (elev: number, now: { k: number; depth: number } | null): number => {
      const e = (elev * Math.PI) / 180;
      const view = norm([0.3 * Math.cos(e), Math.sin(e), 0.95 * Math.cos(e)]);
      let sum = 0;
      let w = 0;
      for (let j = 0; j < n; j++) {
        const y = 1 - (2 * (j + 0.5)) / n;
        const r = Math.sqrt(1 - y * y);
        const N0: Vec3 = [r * Math.cos(j * 2.399963), y, r * Math.sin(j * 2.399963)];
        const fv = dot(N0, view);
        if (fv <= 0) continue;
        const [x, py, z] = pts[j];
        const c = vegNoise(x, py, z);
        const en = c * 0.65 + vegNoise(x * 2.31 + 7.7, py * 2.31 + 3.1, z * 2.31 + 5.3) * 0.35;
        if (en < ss(L.erosion.from, 1, 1 - fv) * L.erosion.max) continue;
        if (!now) {
          const N = norm([N0[0] + c - 0.5, N0[1] + vegNoise(x + 19.1, py + 7.3, z + 3.7) - 0.5, N0[2] + vegNoise(x + 5.9, py + 13.7, z + 29.3) - 0.5]);
          sum += fv * light(N, N0, 1) * mix(0.8, 1, ss(0.3, 0.65, c)) * 1.22;
        } else {
          const [h, gx, gy, gz] = vegBough(x, py, z, 1);
          const deep = now.depth * (1 - ss(L.depth.low[0], L.depth.low[1], N0[1]));
          const gd = gx * N0[0] + gy * N0[1] + gz * N0[2];
          const b = L.boughs.bump * now.k;
          const N = norm([N0[0] - b * (gx - gd * N0[0]), N0[1] - b * (gy - gd * N0[1]), N0[2] - b * (gz - gd * N0[2])]);
          const crease = vegCrease(vegCreaseShare(h), now.k, creaseShare);
          sum += fv * light(N, N0, 1 - deep * L.depth.shadow) * crease * (1 - deep * L.depth.dark) * L.light.gain;
        }
        w += fv;
      }
      return sum / w;
    };
    const avg = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;

    it("keeps light.gain at round 57's 1.22: the softer crease (x 1.031) and depth at the mean (x 0.971) cancel within 1 %", () => {
      expect(L.light.gain).toBe(1.22);
      // Round 57's gaps between clumps kept 0.8, from clump noise 0.3 up to 0.65: 0.910 on average.
      const gaps57 = avg(pts.map(([x, y, z]) => mix(0.8, 1, ss(0.3, 0.65, vegNoise(x, y, z)))));
      const crease = 1 - (1 - L.boughs.dark) * (1 - creaseShare);
      expect(crease / gaps57).toBeGreaterThan(1.02);
      expect(crease / gaps57).toBeLessThan(1.04);
      // Depth's mean factor: the boughs at their mean (strength 0), with and without depth.
      const depth = avg(ELEVATIONS.map((e) => bright(e, { k: 0, depth: 0.6 }) / bright(e, { k: 0, depth: 0 })));
      expect(depth).toBeGreaterThan(0.96);
      expect(depth).toBeLessThan(0.98);
      expect(Math.abs((L.light.gain / 1.22) * (crease / gaps57) * depth - 1)).toBeLessThan(0.01);
    });

    it("stays within 5 % of round 57's from 10 to 70 degrees above, 2 % on average, at full strength, eased off and faded flat", () => {
      for (const elev of ELEVATIONS) {
        const old = bright(elev, null);
        const full = bright(elev, { k: 1, depth: 0.6 });
        expect(Math.abs(full / old - 1), `${elev} degrees`).toBeLessThan(0.05);
        // Large on screen (eased off) and far away (faded flat) move the brightness by under 2 %.
        for (const k of [L.boughs.near, 0]) expect(Math.abs(bright(elev, { k, depth: 0.6 }) / full - 1), `${elev} degrees, strength ${k}`).toBeLessThan(0.02);
      }
      for (const k of [1, L.boughs.near, 0]) {
        const mean = avg(ELEVATIONS.map((e) => bright(e, { k, depth: 0.6 }) / bright(e, null)));
        expect(Math.abs(mean - 1), `strength ${k}`).toBeLessThan(0.02);
      }
    });
  });

  it("hand a tree to the baked card near the camera: the same ground cell and switch distance on both sides", () => {
    // The card's fragment stage and the shell's vertex stage share these lines, so one of the two always draws.
    const cell = farCutCellGlsl("X", "L");
    expect(cell).toContain(`vec2 sectCell = floor( X.xz / ${glslFloat(CARD_LOOK.farCut.cellM)} );`);
    expect(cell).toContain("float sectCellH = fract( sin( dot( sectCell, vec2( 12.9898, 78.233 ) ) ) * 43758.5453 );");
    expect(cell).toContain("bool sectCellFar = sectCellD > mix( L.x, L.y, sectCellH ) || sectCellEl > mix(");
    expect(vs).toContain("uniform vec2 uVegNear;");
    expect(vs).toContain(farCutCellGlsl("vVegCenter", "uVegNear"));
    expect(vs).toContain("if ( ! sectCellFar ) gl_Position = vec4( 2.0, 2.0, 2.0, 1.0 );");
    const card = cardFarCutGlsl();
    expect(card).toContain("if ( uSectCardFar.y > 0.0 ) {");
    expect(card).toContain(farCutCellGlsl("vSectCardWorld", "uSectCardFar"));
    expect(card).toContain("if ( sectCellFar ) discard;");
    expect(CARD_LOOK.farCut.from).toBeLessThan(CARD_LOOK.farCut.to);
    // Looking down on a forest the shells draw at any distance: from 11 to 19 degrees.
    expect(CARD_LOOK.farCut.above[0]).toBeGreaterThan(0.1);
    expect(CARD_LOOK.farCut.above[1]).toBeLessThan(0.5);
  });

  it("grade like the baked cards, then haze, in the colour space the scene's materials write", () => {
    expect(count(fs, "vec3 sectGrade( vec3 c )")).toBe(1);
    expect(count(fs, "vec3 sectTreeShade( vec3 c, vec3 t )")).toBe(1);
    expect(fs).toContain("sectTreeShade( sectGrade( col ), col )");
    expect(fs).toContain("#include <fog_pars_fragment>");
    const cs = fs.indexOf("#include <colorspace_fragment>");
    expect(cs).toBeGreaterThan(fs.indexOf("gl_FragColor = vec4( col, alpha );"));
    expect(fs.indexOf("#include <fog_fragment>")).toBeGreaterThan(cs);
  });

  it("share one value noise with a TypeScript mirror: smooth, 0..1, the same every call", () => {
    const g = vegNoiseGlsl();
    expect(g).toContain("p = fract( p * 0.3183099 + 0.1 );");
    expect(g).toContain("p *= 17.0;");
    let last = vegNoise(0.1, 0.2, 0.3);
    for (let i = 0; i < 500; i++) {
      const t = i * 0.01;
      const v = vegNoise(0.1 + t, 0.2 + t * 0.7, 0.3 - t * 0.4);
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(1);
      expect(Math.abs(v - last)).toBeLessThan(0.08);
      last = v;
    }
    expect(vegNoise(3.7, -2.1, 9.4)).toBe(vegNoise(3.7, -2.1, 9.4));
    // Integer lattice points take the hash itself: the field varies.
    const lattice = new Set([0, 1, 2, 3, 4, 5].map((k) => vegNoise(k, 2 * k, 3 - k).toFixed(4)));
    expect(lattice.size).toBeGreaterThan(3);
  });
});
