import { describe, expect, it } from "vitest";
import { aerialColor, fogConstantsFromMeta, hazeColor, hazeLayerDepth, hexToLinear, mistOpticalDepth } from "./glsl";
import {
  applyLook,
  balancedExtinction,
  gradeGlsl,
  gradeLinear,
  hotspotSurface,
  hotspotTint,
  lookFogConstants,
  puffDensityScale,
  SECT_LOOK,
  treeLiftGlsl,
  treeLiftLinear,
  treeShadeGlsl,
  treeShadeLinear,
  twilightAmount,
  unitTint,
} from "./look";
import { parseMeta } from "./parse";
import type { Vec3 } from "./types";

const luma = (c: Vec3) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];

describe("look", () => {
  const meta = parseMeta({ fog: { color: "#84889e", density: 0.0003, baseY: 100, falloff: 220 }, waterfalls: [], hotspots: [] });

  it("swaps in the warm haze and cloud colours and leaves geometry alone", () => {
    const m = applyLook(meta);
    expect(m.fog.color).toBe(SECT_LOOK.haze.color);
    expect(m.fog.density).toBeCloseTo(0.0003 * SECT_LOOK.haze.densityScale, 9);
    expect(m.fog.baseY).toBe(100);
    expect(m.sky.horizonSun).toBe(SECT_LOOK.haze.sunColor);
    expect(m.cloudSea.color).toBe(SECT_LOOK.cloudSeaColor);
    expect(m.cloudSea.y).toBe(meta.cloudSea.y);
    expect(m.sun).toEqual(meta.sun);
  });

  it("the haze reads warmer than the film's grey", () => {
    const film = hexToLinear("#84889e");
    const look = hexToLinear(SECT_LOOK.haze.color);
    expect(look[0] / look[2]).toBeGreaterThan(film[0] / film[2]);
  });

  it("fog constants carry the look's sky haze and cloud colour", () => {
    const c = lookFogConstants(applyLook(meta));
    expect(c.skyHaze).toBe(SECT_LOOK.sky.haze);
    expect(c.cloudColor).toEqual(hexToLinear(SECT_LOOK.cloudFogColor));
    expect(c.density).toBeCloseTo(applyLook(meta).fog.density, 12);
  });

  it("fog constants carry the aerial perspective, the valley mist and the dither", () => {
    const c = lookFogConstants(applyLook(meta));
    const plain = fogConstantsFromMeta(applyLook(meta));
    expect(c.coolMix).toBe(SECT_LOOK.haze.coolMix);
    expect(c.desaturate).toBe(SECT_LOOK.haze.desaturate);
    expect(c.aerialDepth).toBe(SECT_LOOK.haze.aerialDepth);
    expect(luma(c.coolTint)).toBeCloseTo(1, 9);
    expect(c.coolTint[2]).toBeGreaterThan(c.coolTint[0]);
    expect(c.extinction[2]).toBeGreaterThan(c.extinction[1]);
    expect(c.extinction[1]).toBeGreaterThan(c.extinction[0]);
    expect(c.mistDensity).toBe(SECT_LOOK.mist.density);
    expect(c.mistFalloff).toBe(SECT_LOOK.mist.falloff);
    expect(c.mistStart).toBe(SECT_LOOK.mist.start);
    // The mist sits on the dense cloud layer's top.
    expect(c.mistBaseY).toBe(plain.cloudTop);
    expect(c.dither).toBe(SECT_LOOK.dither);
    // Everything the film's haze had is untouched.
    for (const k of ["density", "baseY", "falloff", "cloudTop", "cloudScale", "cloudDensity", "sunFogMix"] as const) {
      expect(c[k]).toBe(plain[k]);
    }
  });

  it("the pond's mirror rim is gold with a red edge, not a brick-red ring", () => {
    const rim = hexToLinear(SECT_LOOK.water.mirrorRim);
    expect(rim[1] / rim[0]).toBeGreaterThan(0.3);
    const outer = hexToLinear(SECT_LOOK.water.mirrorRimOuter);
    expect(outer[0]).toBeGreaterThan(outer[1] * 3);
  });
});

describe("balancedExtinction", () => {
  const haze = hexToLinear(SECT_LOOK.haze.color);
  const weighted = (k: Vec3) => k[0] * haze[0] * 0.2126 + k[1] * haze[1] * 0.7152 + k[2] * haze[2] * 0.0722;

  it("keeps the haze veil's brightness and the look's ratio", () => {
    const k = balancedExtinction(SECT_LOOK.haze.extinction, haze);
    expect(weighted(k)).toBeCloseTo(weighted([1, 1, 1]), 9);
    expect(k[2] / k[0]).toBeCloseTo(SECT_LOOK.haze.extinction[2] / SECT_LOOK.haze.extinction[0], 9);
  });

  it("is the identity for a grey veil", () => {
    balancedExtinction([1, 1, 1], haze).forEach((v) => expect(v).toBeCloseTo(1, 9));
  });
});

describe("the look's air", () => {
  const meta = applyLook(parseMeta({}));
  const c = lookFogConstants(meta);
  const base = hexToLinear(meta.fog.color);
  const sun = c.sunDir;
  const flat = Math.hypot(sun[0], sun[2]);
  const away: Vec3 = [-sun[0] / flat, 0, -sun[2] / flat];
  /** The fog as it was: one grey veil toward the sun-tinted haze. */
  const before = (col: Vec3, rd: Vec3, od: number): Vec3 => {
    const h = hazeColor({ ...c, coolMix: 0 }, base, rd);
    const v = 1 - Math.exp(-od);
    return col.map((x, i) => x + (h[i] - x) * v) as Vec3;
  };
  const srgb = (x: number) => (x <= 0.0031308 ? x * 12.92 : 1.055 * Math.pow(x, 1 / 2.4) - 0.055) * 255;

  it("leaves the scenery at hand within about one 8-bit step (dark forest 250 m below a high camera)", () => {
    const od = hazeLayerDepth(c, 373, -0.6, 250);
    for (const col of [[0.03, 0.04, 0.025], [0.25, 0.18, 0.1], [0.6, 0.55, 0.5]] as Vec3[]) {
      const a = aerialColor(c, col, base, away, od);
      const b = before(col, away, od);
      a.forEach((v, i) => expect(Math.abs(srgb(v) - srgb(b[i]))).toBeLessThan(1.5));
    }
  });

  it("turns a far ridge away from the sun bluer and paler (1.5 km out at terrace height)", () => {
    const od = hazeLayerDepth(c, 180, 0, 1500);
    const rock: Vec3 = [0.2, 0.14, 0.09];
    const a = aerialColor(c, rock, base, away, od);
    const b = before(rock, away, od);
    expect(a[2] / a[0]).toBeGreaterThan((b[2] / b[0]) * 1.15);
    expect(luma(a)).toBeGreaterThan(luma(b) * 0.98);
  });

  it("keeps the haze's brightness everywhere round the sky (only its hue cools)", () => {
    for (let a = 0; a < Math.PI * 2; a += 0.3) {
      const rd: Vec3 = [Math.cos(a), 0.05, Math.sin(a)];
      const l = Math.hypot(...rd);
      const n: Vec3 = [rd[0] / l, rd[1] / l, rd[2] / l];
      expect(luma(hazeColor(c, base, n))).toBeCloseTo(luma(hazeColor({ ...c, coolMix: 0 }, base, n)), 9);
    }
  });

  it("mists the gorge floors, barely the terraces or the summit", () => {
    const top = c.mistBaseY;
    // Low over the cloud layer it outweighs the haze...
    expect(mistOpticalDepth(c, top + 10, 0, 800)).toBeGreaterThan(hazeLayerDepth(c, top + 10, 0, 800));
    // ...at terrace height (the library hold) and the summit it is a few percent of it.
    expect(mistOpticalDepth(c, 180, 0, 1500)).toBeLessThan(hazeLayerDepth(c, 180, 0, 1500) * 0.1);
    expect(mistOpticalDepth(c, 330, 0, 3000)).toBeLessThan(hazeLayerDepth(c, 330, 0, 3000) * 0.02);
  });
});

describe("unitTint", () => {
  it("has luminance 1 and keeps the hue", () => {
    const t = unitTint("#9a98c0");
    expect(luma(t)).toBeCloseTo(1, 9);
    expect(t[2]).toBeGreaterThan(t[0]);
    expect(unitTint("#ffffff").map((v) => Number(v.toFixed(9)))).toEqual([1, 1, 1]);
  });
});

describe("gradeLinear", () => {
  it("never clips: highlights roll off at or below 1", () => {
    for (const v of [0.5, 0.8, 1, 2]) {
      for (const ch of gradeLinear([v, v, v])) expect(ch).toBeLessThanOrEqual(1);
    }
    for (const ch of gradeLinear([10, 10, 10])) expect(ch).toBeLessThanOrEqual(1);
  });

  it("is monotonic in brightness", () => {
    let prev = -1;
    for (let v = 0.005; v <= 1.2; v += 0.02) {
      const l = luma(gradeLinear([v, v * 0.9, v * 0.8]));
      expect(l).toBeGreaterThan(prev);
      prev = l;
    }
  });

  it("splits the tone: lavender shadows, gold highlights", () => {
    const dark = gradeLinear([0.02, 0.02, 0.02]);
    expect(dark[2]).toBeGreaterThan(dark[0]);
    const light = gradeLinear([0.45, 0.45, 0.45]);
    expect(light[0]).toBeGreaterThan(light[2]);
  });

  it("adds contrast: darks darker and lights lighter than exposure alone", () => {
    const e = SECT_LOOK.grade.exposure;
    expect(luma(gradeLinear([0.03, 0.03, 0.03]))).toBeLessThan(0.03 * e);
    expect(luma(gradeLinear([0.4, 0.4, 0.4]))).toBeGreaterThan(0.4 * e);
  });

  it("lets sunlit edges reach about 0.9", () => {
    expect(luma(gradeLinear([0.6, 0.55, 0.45]))).toBeGreaterThan(0.85);
  });

  it("takes lime grass toward olive", () => {
    const grass = hexToLinear("#434f03");
    const g = gradeLinear(grass);
    expect(g[1] / g[0]).toBeLessThan(grass[1] / grass[0]);
  });

  it("is the identity with a neutral grade below the shoulder", () => {
    const neutral = {
      exposure: 1,
      contrast: 1,
      pivot: 0.18,
      shadowTint: "#ffffff",
      highlightTint: "#ffffff",
      split: 0,
      saturation: 1,
      greenTame: 0,
      shoulder: 0.9,
    };
    const c: Vec3 = [0.3, 0.5, 0.1];
    gradeLinear(c, neutral).forEach((v, i) => expect(v).toBeCloseTo(c[i], 9));
  });

  it("emits a GLSL function with the look's numbers", () => {
    const src = gradeGlsl();
    expect(src).toContain("vec3 sectGrade( vec3 c )");
    expect(src).toContain("c *= 1.4200000;");
    expect(src).toContain("0.18");
    expect(src).not.toMatch(/NaN|undefined/);
  });
});

describe("hotspotTint", () => {
  it("gives each stele row its own glyph colour", () => {
    const rows = [0, 1, 2, 3, 4].map((i) => hotspotTint(`skills:${i}`, i === 0 ? "baked.steles_A0.glow.rune_cyan" : "baked.steles_A0.glow.steles_rune"));
    expect(rows.map((r) => r?.color)).toEqual([...SECT_LOOK.steleRows]);
    expect(new Set(rows.map((r) => r?.color)).size).toBe(5);
  });

  it("tints the jade slip's sheet, and nothing else", () => {
    expect(hotspotTint("resume", "baked.scroll_A0.glow.other")).toEqual(SECT_LOOK.jade);
    expect(hotspotTint("resume", "baked.scroll_A0.glow.rune_gold")).toBeNull();
    expect(hotspotTint("skills:1", "baked.steles_A0")).toBeNull();
    expect(hotspotTint("gate", "baked.gate_A0.glow.other")).toBeNull();
  });
});

describe("the Heavy Iron Sword's black iron (hotspotSurface, its seams' hotspotTint)", () => {
  const iron = SECT_LOOK.surfaces.iron;

  it("gives the arena sword's metal the iron class, and no other steel", () => {
    expect(hotspotSurface("arena", "baked.arena_A0.surface.metal")).toBe("iron");
    expect(hotspotSurface("arena", "baked.vc.surface.metal")).toBe("iron");
    expect(hotspotSurface("arena", "baked.arena_A0")).toBeNull();
    expect(hotspotSurface("arena", "baked.arena_A0.surface.glaze")).toBeNull();
    // The gate's Dragon Saber (gate-swords) and the arena's banner finials (hackathon:<i>) stay steel.
    expect(hotspotSurface("gate-swords", "baked.gate_A0.surface.metal")).toBeNull();
    expect(hotspotSurface("hackathon:3", "baked.arena_A0.surface.metal")).toBeNull();
  });

  it("turns its seams a deep ember red that still counts as a glow; other molten keeps its colour", () => {
    expect(hotspotTint("arena", "baked.arena_A0.glow.molten")).toEqual(iron.seams);
    expect(hotspotTint("forge", "baked.forge_A0.glow.molten")).toBeNull();
    expect(hotspotTint("gate-swords", "baked.gate_A0.glow.molten")).toBeNull();
    // As prepare.ts sets it: white toward the colour by amount, times the class's strength (molten 2) and gain.
    const c = hexToLinear(iron.seams.color).map((v) => (1 + (v - 1) * iron.seams.amount) * 2 * iron.seams.gain);
    // Above 1: idle.ts breathes only glows, and the grade keeps a glow's colour.
    expect(Math.max(...c)).toBeGreaterThan(1.001);
    // Red: the class's own tint (#ff9a50 at 75 %) keeps green at half of red, bright orange.
    expect(c[1] / c[0]).toBeLessThan(0.15);
    expect(c[2]).toBeLessThan(c[1]);
  });

  it("is near-black with a dark red undertone, rough and dull beside the polished metal", () => {
    const t = unitTint(iron.color);
    expect(t[0]).toBeGreaterThan(3 * t[1]);
    expect(unitTint(iron.glint.color)[0]).toBeGreaterThan(3 * unitTint(iron.glint.color)[1]);
    expect(iron.diffuse).toBeLessThan(SECT_LOOK.surfaces.metal.diffuse);
    // A mid-grey baked texel (graded luminance 0.2) ends near-black.
    expect(0.2 * iron.diffuse).toBeLessThan(0.05);
    expect(iron.f0).toBeLessThan(SECT_LOOK.surfaces.metal.f0 / 10);
    expect(iron.grazing).toBeLessThan(0.5);
    expect(iron.rough).toBeGreaterThan(2 * SECT_LOOK.surfaces.metal.rough);
  });
});

describe("twilightAmount", () => {
  it("runs from 0 at the first hold to 1 at the second", () => {
    expect(twilightAmount(900, 1103, 1647)).toBe(0);
    expect(twilightAmount(1375, 1103, 1647)).toBeCloseTo(0.5, 6);
    expect(twilightAmount(1700, 1103, 1647)).toBe(1);
    expect(twilightAmount(1200, 1647, 1103)).toBe(0);
  });
});

describe("puffDensityScale", () => {
  const areas: Vec3[] = [
    [0, 50, 12],
    [-100, 77, -208],
  ];

  it("thins puffs near an area and leaves far ones alone", () => {
    expect(puffDensityScale([10, 50, 20], areas)).toBeCloseTo(SECT_LOOK.puffs.areaThin, 9);
    expect(puffDensityScale([2000, 0, 0], areas)).toBe(1);
  });

  it("fades back to full density over half the radius", () => {
    const r = SECT_LOOK.puffs.areaRadius;
    const mid = puffDensityScale([r * 1.25, 50, 12], [areas[0]]);
    expect(mid).toBeGreaterThan(SECT_LOOK.puffs.areaThin);
    expect(mid).toBeLessThan(1);
  });
});

describe("near pine lift", () => {
  const lift = SECT_LOOK.trees.lift;

  it("leaves texels at or above the pivot (trunks, lit tips) as baked", () => {
    for (const c of [[lift.pivot, lift.pivot, lift.pivot], [0.3, 0.2, 0.1], [0.9, 0.8, 0.7]] as Vec3[]) expect(treeLiftLinear(c)).toEqual(c);
    expect(treeLiftLinear([0, 0, 0])).toEqual([0, 0, 0]);
  });

  it("lifts the darkest needles most, keeps their order and hue, and caps the gain", () => {
    // Shade needles average about sRGB 11, sun ones 23-30, the far cards 29-36 (audit vv/varlum.py).
    const shade = hexToLinear("#0b0b0b");
    const sun = hexToLinear("#1b1b1b");
    const ls = luma(treeLiftLinear(shade)) / luma(shade);
    const lu = luma(treeLiftLinear(sun)) / luma(sun);
    expect(ls).toBeGreaterThan(lu);
    expect(lu).toBeGreaterThan(1.3);
    expect(ls).toBeLessThanOrEqual(lift.maxGain + 1e-9);
    // Lifted shade stays darker than lifted sun.
    expect(luma(treeLiftLinear(shade))).toBeLessThan(luma(treeLiftLinear(sun)));
    let last = 0;
    for (let l = 0.001; l < 0.2; l *= 1.4) {
      const out = luma(treeLiftLinear([l, l, l]));
      expect(out).toBeGreaterThanOrEqual(last - 1e-12);
      last = out;
    }
    const green: Vec3 = [0.004, 0.009, 0.002];
    const g = treeLiftLinear(green);
    expect(g[0] / g[1]).toBeCloseTo(green[0] / green[1], 9);
    expect(g[2] / g[1]).toBeCloseTo(green[2] / green[1], 9);
  });

  it("has GLSL with the same constants", () => {
    const g = treeLiftGlsl();
    expect(g).toContain("vec3 sectTreeLift( vec3 c )");
    expect(g).toContain(String(lift.pivot));
    expect(g).toContain(String(lift.gamma));
    expect(g).not.toMatch(/NaN|undefined/);
  });
});

describe("near pine shade", () => {
  const shade = SECT_LOOK.trees.shade;
  // A shade needle (olive, green level with red), lifted, and the grade it gets: green's lead gone,
  // so the haze's lavender on top reads slate.
  const needle: Vec3 = [0.003, 0.0031, 0.001];
  const slate = gradeLinear(treeLiftLinear(needle));

  it("turns the graded shade of a needle green, at the same luminance", () => {
    expect(slate[1]).toBeLessThanOrEqual(slate[0]);
    const out = treeShadeLinear(slate, treeLiftLinear(needle));
    expect(luma(out)).toBeCloseTo(luma(slate), 9);
    expect(out[1]).toBeGreaterThan(out[0]);
    expect(out[1]).toBeGreaterThan(out[2]);
    expect(out[2]).toBeLessThan(slate[2]);
  });

  it("leaves bark and blossom (red-led texels) and lit needles as graded", () => {
    const bark: Vec3 = [0.03, 0.015, 0.005];
    const blossom: Vec3 = [0.6, 0.25, 0.3];
    for (const t of [bark, blossom]) {
      const g = gradeLinear(t);
      expect(treeShadeLinear(g, t)).toEqual(g);
    }
    const lit: Vec3 = [0.2, 0.22, 0.06];
    const g = gradeLinear(lit);
    expect(luma(g)).toBeGreaterThan(shade.hi);
    expect(treeShadeLinear(g, lit)).toEqual(g);
  });

  it("comes in gradually with darkness and with greenness", () => {
    const t: Vec3 = [0.01, 0.012, 0.004];
    const shift = (c: Vec3, tex: Vec3) => {
      const o = treeShadeLinear(c, tex);
      return Math.abs(o[0] - c[0]) + Math.abs(o[1] - c[1]) + Math.abs(o[2] - c[2]);
    };
    const grey = (l: number): Vec3 => [l, l, l];
    expect(shift(grey(0.005), t) / 0.005).toBeGreaterThan(shift(grey(0.04), t) / 0.04);
    expect(shift(grey(0.005), t)).toBeGreaterThan(shift(grey(0.005), [0.012, 0.011, 0.004]));
  });

  it("has GLSL with the same constants", () => {
    const g = treeShadeGlsl();
    expect(g).toContain("vec3 sectTreeShade( vec3 c, vec3 t )");
    expect(g).toContain(String(shade.lo));
    expect(g).toContain(String(shade.hi));
    expect(g).toContain(String(shade.amount));
    expect(g).not.toMatch(/NaN|undefined/);
  });
});
