import { describe, expect, it } from "vitest";
import {
  clumpFactor,
  clumpGapWeight,
  DETAIL_LOOK,
  DETAIL_NOISE,
  DETAIL_TILE_M,
  detailApplyGlsl,
  detailClass,
  detailDarkScale,
  detailFactor,
  detailFade,
  detailGlsl,
  detailProgramKey,
  detailVertexGlsl,
  detailWanted,
  greenRockGate,
  groundTint,
  groundTintGlsl,
  isNeedleCard,
  jointCoverage,
  pavingSlab,
  rockFarFactor,
  rockFarFade,
  rockFarOctaves,
  sheenFactor,
  tileCourseFactor,
  tileMeans,
} from "./detail";
import { glslFloat } from "./glsl";
import { clumpField, groundNoise, rankBytes, tilingNoise } from "./noise";
import { mossGate, RANGE_LOOK } from "./range-look";

const count = (s: string, sub: string) => s.split(sub).length - 1;

describe("detail classes and tags", () => {
  it("tiles each channel at its scan's real size", () => {
    expect(DETAIL_TILE_M).toEqual({ rock: 8.14, ground: 2.0, moss: 1.5, paving: 2.5 });
  });

  it("reads extras.detail and the needle card tag", () => {
    expect(detailClass("rock")).toBe("rock");
    expect(detailClass("ground")).toBe("ground");
    expect(detailClass("paving")).toBe("paving");
    expect(detailClass("moss")).toBeNull();
    expect(detailClass(undefined)).toBeNull();
    expect(detailClass(1)).toBeNull();
    expect(isNeedleCard({ cardAlpha: "needle", baked: true })).toBe(true);
    expect(isNeedleCard({ cardAlpha: "leaf" })).toBe(false);
    expect(isNeedleCard({})).toBe(false);
    expect(isNeedleCard(undefined)).toBe(false);
  });
});

describe("detail strength", () => {
  it("fades from full near the camera to nothing far away", () => {
    const { fadeNear, fadeFar } = DETAIL_LOOK.rock;
    expect(detailFade(0, fadeNear, fadeFar)).toBe(1);
    expect(detailFade(fadeNear, fadeNear, fadeFar)).toBe(1);
    expect(detailFade(fadeFar, fadeNear, fadeFar)).toBe(0);
    expect(detailFade(fadeFar * 3, fadeNear, fadeFar)).toBe(0);
    let prev = 1;
    for (let d = fadeNear; d <= fadeFar; d += 5) {
      const f = detailFade(d, fadeNear, fadeFar);
      expect(f).toBeLessThanOrEqual(prev);
      prev = f;
    }
  });

  it("ground detail is gone sooner than rock detail, and reaches 140 m", () => {
    expect(DETAIL_LOOK.ground.fadeFar).toBe(140);
    expect(DETAIL_LOOK.ground.fadeFar).toBeLessThan(DETAIL_LOOK.rock.fadeFar);
    expect(detailFactor("ground", 0.9, 100, 0.3)).toBeGreaterThan(1);
    expect(detailFactor("ground", 0.9, 145, 0.3)).toBe(1);
    expect(detailFactor("rock", 0.9, 145, 0.3)).toBeGreaterThan(1);
  });

  it("mid grey changes nothing; brighter and darker detail move the colour both ways", () => {
    expect(detailFactor("rock", 0.5, 10, 0.3)).toBe(1);
    expect(detailFactor("rock", 0.8, 10, 0.3)).toBeGreaterThan(1);
    expect(detailFactor("rock", 0.2, 10, 0.3)).toBeLessThan(1);
    // Symmetric in stops.
    expect(Math.log2(detailFactor("rock", 0.8, 10, 0.3))).toBeCloseTo(-Math.log2(detailFactor("rock", 0.2, 10, 0.3)), 9);
    // Full strength: (d - 0.5) x gain stops.
    expect(Math.log2(detailFactor("rock", 1, 10, 0.5))).toBeCloseTo(0.5 * DETAIL_LOOK.rock.gain, 9);
  });

  it("shadowed texels get less detail than lit ones", () => {
    expect(detailDarkScale(0)).toBeCloseTo(DETAIL_LOOK.dark.floor, 9);
    expect(detailDarkScale(1)).toBe(1);
    const dark = Math.abs(Math.log2(detailFactor("rock", 0.8, 10, 0.005)));
    const lit = Math.abs(Math.log2(detailFactor("rock", 0.8, 10, 0.4)));
    expect(dark).toBeLessThan(lit);
    expect(dark).toBeGreaterThan(0);
  });
});

describe("detailWanted", () => {
  const high = { lowTextures: false, alphaToCoverage: true, shadows: true };
  const mid = { lowTextures: false, alphaToCoverage: false, shadows: false };
  const midTouch = { lowTextures: true, alphaToCoverage: false, shadows: false };
  const low = { lowTextures: true, alphaToCoverage: true, shadows: false };

  it("needs a detail texture in the manifest", () => {
    expect(detailWanted(undefined, high)).toBe(false);
    expect(detailWanted(null, high)).toBe(false);
    expect(detailWanted("", high)).toBe(false);
    expect(detailWanted("detail.webp", high)).toBe(true);
  });

  it("is off on the low tier, given or recognised from the page's options", () => {
    expect(detailWanted("detail.webp", mid)).toBe(true);
    expect(detailWanted("detail.webp", midTouch)).toBe(true);
    expect(detailWanted("detail.webp", low)).toBe(false);
    expect(detailWanted("detail.webp", { ...high, tier: "low" })).toBe(false);
    expect(detailWanted("detail.webp", { ...low, tier: "mid" })).toBe(true);
  });
});

describe("detail GLSL", () => {
  it("rock: three projections on the flat face normal, two layers, red channel, its own tile", () => {
    const g = detailGlsl("rock");
    expect(g).toContain("float sectDetail( vec3 p )");
    expect(g).toContain("uniform sampler2D tSectDetail;");
    expect(g).toContain("uniform float uSectDetailOn;");
    expect(g).toContain("cross( dFdx( p ), dFdy( p ) )");
    expect(count(g, "texture2D( tSectDetail")).toBe(6);
    expect(count(g, "texture2D( tSectDetail, r * q")).toBe(3);
    expect(g).toContain(glslFloat(1 / DETAIL_TILE_M.rock));
    // Softer than the first 6, so the pattern jumps less at each triangle edge.
    expect(DETAIL_LOOK.sharpness).toBe(3);
    expect(g).toContain(`vec3( ${glslFloat(DETAIL_LOOK.sharpness)} )`);
  });

  it("ground: straight down (Y up), two layers, green channel, its own tile", () => {
    const g = detailGlsl("ground");
    const photo = g.slice(g.indexOf("float sectDetail("));
    expect(photo).toContain("p.xz");
    expect(g).not.toContain("dFdx");
    expect(count(g, "texture2D( tSectDetail")).toBe(2);
    expect(count(photo, ").g")).toBe(2);
    expect(g).toContain(glslFloat(1 / DETAIL_TILE_M.ground));
  });

  it("declares every uniform once, in both classes", () => {
    const both = ["sampler2D tSectDetail", "float uSectDetailOn", "sampler2D tSectClump", "sampler2D tSectGroundNoise", "float uSectGroundLayers", "float uSectTime", "vec3 uSectSun"];
    for (const kind of ["rock", "ground"] as const) {
      const g = detailGlsl(kind);
      for (const u of both) expect(count(g, `uniform ${u};`), `${kind} ${u}`).toBe(1);
      for (const u of ["float uSectRockFar", "float uSectRockOctaves"]) expect(count(g, `uniform ${u};`), `${kind} ${u}`).toBe(kind === "rock" ? 1 : 0);
      // Every function the apply step calls is defined, once.
      for (const fn of ["vec3 sectGroundTint(", "float sectClump(", "vec3 sectGroundLayers(", "float sectDetail("]) expect(count(g, fn), fn).toBe(1);
    }
    expect(detailGlsl("rock")).toContain("float sectRockFar( vec3 p )");
    expect(detailGlsl("rock")).toContain("float sectNoise3( vec3 x )");
    expect(detailGlsl("ground")).not.toContain("sectRockFar");
  });

  it("the far rock layer reads the noise's top level (no derivatives) and skips its second octave on mid", () => {
    const g = detailGlsl("rock");
    expect(count(g, "textureLod( tSectGroundNoise")).toBe(1);
    expect(g).toContain(`vec2( ${glslFloat(DETAIL_NOISE.ground.offset[0])}, ${glslFloat(DETAIL_NOISE.ground.offset[1])} ) * i.y`);
    expect(g).toContain("if ( uSectRockOctaves > 1.5 )");
    expect(g).toContain(glslFloat(1 / DETAIL_LOOK.rockFar.scalesM[0]));
    expect(g).toContain(glslFloat(1 / DETAIL_LOOK.rockFar.scalesM[1]));
    expect(rockFarOctaves("high")).toBe(2);
    expect(rockFarOctaves("mid")).toBe(1);
    expect(rockFarOctaves("low")).toBe(1);
  });

  it("applies the class's gain and fade to diffuseColor", () => {
    for (const kind of ["rock", "ground"] as const) {
      const a = detailApplyGlsl(kind);
      const k = DETAIL_LOOK[kind];
      expect(a).toContain("diffuseColor.rgb *= exp2(");
      expect(a).toContain(glslFloat(k.gain));
      expect(a).toContain(`smoothstep( ${glslFloat(k.fadeNear)}, ${glslFloat(k.fadeFar)}`);
      expect(a).toContain("uSectDetailOn");
      expect(a).toContain("sectGroundLayers( diffuseColor.rgb, vSectWorld");
      expect(a).not.toMatch(/\bif\b/);
    }
  });

  it("ground gets the sheen; rock the mossy-rock gate (on the texel before the grade) and the far layer", () => {
    const g = detailApplyGlsl("ground");
    expect(g).toContain("sectSheen( vSectWorld");
    expect(g).not.toContain("sectTexel");
    const r = detailApplyGlsl("rock");
    expect(r).not.toContain("sectSheen");
    expect(r).toContain("sqrt( max( sectTexel, vec3( 0.0 ) ) )");
    expect(r).toContain(`smoothstep( ${glslFloat(DETAIL_LOOK.greenRock.hue[0])}, ${glslFloat(DETAIL_LOOK.greenRock.hue[1])}`);
    expect(r).toContain("sectRockFar( vSectWorld )");
    expect(r).toContain("* uSectRockFar;");
    // The layers' switch reaches the patches, the clumps and the sheen.
    const g2 = detailGlsl("ground");
    expect(g2).toContain("sectGroundTint( col, p ), uSectGroundLayers )");
    expect(g2).toMatch(/smoothstep\( [\d.]+, [\d.]+, dist \) \) \* uSectGroundLayers \);/);
    expect(g2).toContain("* ds * uSectGroundLayers;");
  });

  it("changes the program cache key with the layers", () => {
    const rock = detailProgramKey("rock");
    const ground = detailProgramKey("ground");
    expect(rock).not.toBe(ground);
    expect(detailProgramKey("rock")).toBe(rock);
    const look = { ...DETAIL_LOOK, rockFar: { ...DETAIL_LOOK.rockFar, gain: 0.5 } };
    expect(detailProgramKey("rock", look)).not.toBe(rock);
    const look2 = { ...DETAIL_LOOK, sheen: { ...DETAIL_LOOK.sheen, amount: 0.05 } };
    expect(detailProgramKey("ground", look2)).not.toBe(ground);
  });
});

describe("ground tint (the shared colour patches)", () => {
  const olive = [0.1, 0.1, 0.03] as const;
  const lum = (c: readonly number[]) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  const hue = (c: readonly number[]) => (Math.atan2(Math.sqrt(3) * (c[1] - c[2]), 2 * c[0] - c[1] - c[2]) * 180) / Math.PI;

  it("declares its texture and nothing else: no clock, no clumps, no derivatives (it runs in vertex shaders)", () => {
    const g = groundTintGlsl();
    expect(count(g, "uniform sampler2D tSectGroundNoise;")).toBe(1);
    expect(count(g, "uniform ")).toBe(1);
    expect(g).toContain("vec3 sectGroundTint( vec3 col, vec3 p )");
    expect(count(g, "texture2D( tSectGroundNoise")).toBe(2);
    for (const s of ["uSectTime", "tSectClump", "dFdx", "dFdy", "textureLod"]) expect(g).not.toContain(s);
    for (const m of DETAIL_LOOK.macro.scalesM) expect(g).toContain(glslFloat(1 / (m * DETAIL_NOISE.ground.cells)));
  });

  it("changes nothing at the fields' middle", () => {
    const c = groundTint(olive, 0.5, 0.5);
    for (let i = 0; i < 3; i++) expect(c[i]).toBeCloseTo(olive[i], 12);
  });

  it("turns lush patches greener and darker, dry ones golder and brighter, within the look's bounds", () => {
    const m = DETAIL_LOOK.macro;
    const lush = groundTint(olive, 1, 0.5);
    const dry = groundTint(olive, 0, 0.5);
    expect(lush[1] / lush[0]).toBeGreaterThan(1);
    expect(dry[1] / dry[0]).toBeLessThan(1);
    expect(lum(lush)).toBeLessThan(lum(olive));
    expect(lum(dry)).toBeGreaterThan(lum(olive));
    expect(hue(lush) - hue(olive)).toBeLessThanOrEqual(m.hueDeg + 1e-6);
    expect(hue(lush) - hue(olive)).toBeGreaterThan(m.hueDeg * 0.9);
    expect(hue(olive) - hue(dry)).toBeGreaterThan(m.hueDeg * 0.9);
    for (let l = 0; l <= 1; l += 0.125) {
      for (let b = 0; b <= 1; b += 0.125) {
        const c = groundTint(olive, l, b);
        expect(Math.min(...c)).toBeGreaterThanOrEqual(0);
        const ratio = lum(c) / lum(olive);
        expect(ratio).toBeGreaterThan(1 - m.value * 1.6);
        expect(ratio).toBeLessThan(1 + m.value * 1.6);
      }
    }
  });

  it("has no bias: over the fields' range the mean colour stays put", () => {
    const sum = [0, 0, 0];
    let n = 0;
    for (let i = 0; i < 32; i++) {
      for (let j = 0; j < 32; j++) {
        const c = groundTint(olive, (i + 0.5) / 32, (j + 0.5) / 32);
        for (let k = 0; k < 3; k++) sum[k] += c[k];
        n++;
      }
    }
    for (let k = 0; k < 3; k++) expect(sum[k] / n / olive[k]).toBeCloseTo(1, 1);
  });
});

describe("grass clumps", () => {
  const n = DETAIL_NOISE.clump.size;
  const field = clumpField(n, DETAIL_NOISE.clump);
  const mean = field.reduce((a, b) => a + b, 0) / field.length / 255;

  it("has the mean the shader divides by, mostly high with low gaps", () => {
    expect(mean).toBeCloseTo(DETAIL_NOISE.clump.mean, 2);
    const low = field.filter((v) => v < 128).length / field.length;
    expect(low).toBeGreaterThan(0.1);
    expect(low).toBeLessThan(0.35);
  });

  it("tiles seamlessly: the texels across each edge differ like neighbours inside", () => {
    const at = (x: number, y: number) => field[y * n + x];
    let inside = 0;
    let across = 0;
    for (let y = 0; y < n; y++) {
      for (let x = 1; x < n; x++) inside += Math.abs(at(x, y) - at(x - 1, y)) + Math.abs(at(y, x) - at(y, x - 1));
      across += Math.abs(at(0, y) - at(n - 1, y)) + Math.abs(at(y, 0) - at(y, n - 1));
    }
    inside /= 2 * n * (n - 1);
    across /= 2 * n;
    expect(across).toBeLessThan(inside * 1.5);
  });

  it("is the same every load", () => {
    expect(clumpField(64, { cells: 5, mean: 0.7 })).toEqual(clumpField(64, { cells: 5, mean: 0.7 }));
  });

  it("darkens the gaps and lifts the tops, keeping the average", () => {
    const c = DETAIL_LOOK.clump;
    expect(clumpFactor(0, mean, 1, 0)).toBeLessThan(1);
    expect(clumpFactor(1, mean, 1, 0)).toBeGreaterThan(1);
    const m = DETAIL_NOISE.clump.mean;
    expect(clumpFactor(0, m, 1, 0)).toBeCloseTo(c.gap / (c.gap + (c.top - c.gap) * m), 9);
    expect(clumpFactor(1, m, 1, 0)).toBeCloseTo(c.top / (c.gap + (c.top - c.gap) * m), 9);
    // Over the field itself (two independent reads): mean 1.
    let s = 0;
    let k = 0;
    for (let i = 0; i < field.length; i += 7, k++) s += clumpFactor(field[i] / 255, field[(i * 31 + 4099) % field.length] / 255, 1, 0);
    expect(s / k).toBeCloseTo(1, 2);
  });

  it("shows less of the gaps at grazing angles, and fades out by fadeFar", () => {
    const c = DETAIL_LOOK.clump;
    expect(clumpGapWeight(1)).toBe(1);
    expect(clumpGapWeight(0)).toBeCloseTo(c.grazingKeep, 9);
    const down = Math.abs(Math.log2(clumpFactor(0, 0.7, 1, 0)));
    const grazing = Math.abs(Math.log2(clumpFactor(0, 0.7, 0.05, 0)));
    expect(grazing).toBeLessThan(down);
    expect(grazing).toBeGreaterThan(0);
    expect(clumpFactor(0, 0, 1, c.fadeNear)).toBeLessThan(1);
    expect(clumpFactor(0, 0, 1, c.fadeFar)).toBe(1);
    expect(clumpFactor(1, 1, 1, c.fadeFar + 50)).toBe(1);
  });
});

describe("wind sheen", () => {
  const s = DETAIL_LOOK.sheen;

  it("moves brightness by +-amount, more toward the sun, less in shadow, and fades out by fadeFar", () => {
    expect(sheenFactor(0.5, 1, 0, 0.5)).toBe(1);
    expect(sheenFactor(1, -1, 0, 0.5)).toBeCloseTo(1 + s.amount, 9);
    expect(sheenFactor(0, -1, 0, 0.5)).toBeCloseTo(1 - s.amount, 9);
    expect(sheenFactor(1, 1, 0, 0.5)).toBeCloseTo(1 + s.amount * (1 + s.sunBoost), 9);
    expect(sheenFactor(1, 1, 0, 0.001) - 1).toBeLessThan(sheenFactor(1, 1, 0, 0.5) - 1);
    expect(sheenFactor(1, 1, s.fadeFar, 0.5)).toBe(1);
    expect(sheenFactor(1, 1, (s.fadeNear + s.fadeFar) / 2, 0.5)).toBeGreaterThan(1);
  });

  it("drifts with the wind at its speed (the GLSL)", () => {
    const g = detailGlsl("ground");
    expect(g).toContain(`uSectTime * ${glslFloat(s.speed)}`);
    expect(g).toContain("float sectSheen( vec3 p, vec3 v, float dist, float ds )");
    expect(g).toContain("dot( v, uSectSun )");
  });
});

describe("far rock layer", () => {
  const r = DETAIL_LOOK.rockFar;

  it("fades in by fadeNear and out by fadeFar", () => {
    expect(rockFarFade(0)).toBe(0);
    expect(rockFarFade(r.fadeNear * 0.5)).toBe(0);
    expect(rockFarFade(r.fadeNear)).toBe(1);
    expect(rockFarFade(r.fadeFar * 0.6)).toBe(1);
    expect(rockFarFade(r.fadeFar)).toBe(0);
    expect(rockFarFade(300)).toBe(1);
  });

  it("changes nothing at the noise's middle, and stays within a gain that does not read as dirt", () => {
    expect(r.gain).toBeLessThanOrEqual(0.8);
    expect(rockFarFactor(0.5, 0.5, 0, 300, 0.3)).toBe(1);
    const hi = rockFarFactor(1, 1, 1, 300, 0.3);
    const lo = rockFarFactor(0, 0, -1, 300, 0.3);
    expect(Math.log2(hi)).toBeCloseTo(-Math.log2(lo), 9);
    expect(Math.log2(hi)).toBeCloseTo((0.5 * r.weights[0] + 0.5 * r.weights[1] + r.band.weight) * r.gain, 9);
    expect(rockFarFactor(1, 1, 1, 50, 0.3)).toBe(1);
    expect(rockFarFactor(1, 1, 1, r.fadeFar, 0.3)).toBe(1);
    // A little less in shadow, never down to the photo detail's floor.
    const dark = Math.log2(rockFarFactor(1, 1, 1, 300, 0.001));
    expect(dark).toBeLessThan(Math.log2(hi));
    expect(dark).toBeGreaterThan(Math.log2(hi) * DETAIL_LOOK.dark.floor);
  });
});

describe("mossy rock gate", () => {
  const lin = (s: number) => (s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4));
  const srgb = (r: number, g: number, b: number) => [lin(r), lin(g), lin(b)] as const;

  it("opens on green and olive moss, stays shut on grey rock, sandstone and shadow", () => {
    expect(greenRockGate(srgb(0.3, 0.45, 0.2))).toBe(1);
    expect(greenRockGate(srgb(0.45, 0.45, 0.25))).toBe(1);
    // Olive (hue about 50 degrees): mostly open.
    expect(greenRockGate(srgb(0.45, 0.42, 0.25))).toBeGreaterThan(0.6);
    // Sandstone (hue about 30) and grey rock: shut.
    expect(greenRockGate(srgb(0.6, 0.45, 0.3))).toBe(0);
    expect(greenRockGate(srgb(0.4, 0.4, 0.4))).toBe(0);
    expect(greenRockGate(srgb(0.4, 0.42, 0.38))).toBe(0);
    // Bluish and dark texels: shut.
    expect(greenRockGate(srgb(0.3, 0.32, 0.45))).toBe(0);
    expect(greenRockGate(srgb(0.03, 0.04, 0.01))).toBe(0);
    expect(greenRockGate([0, 0, 0])).toBe(0);
  });
});

describe("the layers' noise textures", () => {
  it("leaves the cloud sea's noise as it was", () => {
    const b = tilingNoise(256, { basePeriod: 4, octaves: 6, seed: 11 });
    let h = 0x811c9dc5;
    for (const v of b) h = Math.imul(h ^ v, 0x01000193);
    expect((h >>> 0).toString(16)).toBe("1f5a6280");
  });

  it("ground noise: G is R moved by the slice offset; B and A are uniform 0..1 and smooth", () => {
    const { size, offset, cells } = DETAIL_NOISE.ground;
    const g = groundNoise(size, { offset, cells });
    expect(g.length).toBe(size * size * 4);
    for (let j = 0; j < size; j += 3) {
      for (let i = 0; i < size; i += 5) {
        const moved = (((j + offset[1]) % size) * size + ((i + offset[0]) % size)) * 4;
        expect(g[(j * size + i) * 4 + 1]).toBe(g[moved]);
      }
    }
    for (const ch of [2, 3]) {
      let s = 0;
      let step = 0;
      for (let k = 0; k < size * size; k++) {
        s += g[k * 4 + ch];
        const right = (Math.floor(k / size) * size + (((k % size) + 1) % size)) * 4 + ch;
        const down = (((Math.floor(k / size) + 1) % size) * size + (k % size)) * 4 + ch;
        step = Math.max(step, Math.abs(g[k * 4 + ch] - g[right]), Math.abs(g[k * 4 + ch] - g[down]));
      }
      expect(s / (size * size) / 255).toBeCloseTo(0.5, 2);
      // Smooth, also across the wrap: no texel jumps by more than a quarter of the range.
      expect(step).toBeLessThan(255 / 4);
    }
  });

  it("rankBytes keeps order, gives equal values one byte, and follows the curve's mean", () => {
    const b = rankBytes([3, 1, 2, 2, 5, 4]);
    expect(b[1]).toBe(0);
    expect(b[4]).toBe(255);
    expect(b[2]).toBe(b[3]);
    expect(b[0]).toBeGreaterThan(b[2]);
    expect(b[5]).toBeGreaterThan(b[0]);
    const big = Array.from({ length: 10000 }, (_, i) => Math.abs(Math.sin(i * 12.9898) * 43758.5453) % 1);
    const m = rankBytes(big, (u) => u ** 0.5).reduce((a, v) => a + v, 0) / big.length / 255;
    expect(m).toBeCloseTo(2 / 3, 2);
  });
});

describe("paving (the marble plazas)", () => {
  const pv = DETAIL_LOOK.paving;

  it("follows materials._paving's brick texture: 1.2 x 0.8 m slabs, every second row (even rows) shifted half a slab", () => {
    expect(pv.slabM).toEqual([1.2, 0.8]);
    expect(pv.offset).toBe(0.5);
    expect(pv.jointM).toBe(0.012);
    // Row 0 is shifted (Blender: rownum % 2 == 0 takes the offset): x 0.1 lands 0.7 into slab 0.
    const a = pavingSlab(0.1, 0.1);
    expect([a.col, a.row]).toEqual([0, 0]);
    expect(a.edge[0]).toBeCloseTo(0.5, 6);
    expect(a.edge[1]).toBeCloseTo(0.1, 6);
    // Row 1 is not: x 0.1 is 0.1 into slab 0; x 1.25 is in slab 1.
    expect(pavingSlab(0.1, 0.9).col).toBe(0);
    expect(pavingSlab(0.1, 0.9).edge[0]).toBeCloseTo(0.1, 6);
    expect(pavingSlab(1.25, 0.9).col).toBe(1);
    // Negative rows as C's % has it: -1 is odd (no shift), -2 even (shifted).
    expect(pavingSlab(0.1, -0.5).row).toBe(-1);
    expect(pavingSlab(0.1, -0.5).edge[0]).toBeCloseTo(0.1, 6);
    expect(pavingSlab(0.1, -1.0).row).toBe(-2);
    expect(pavingSlab(0.1, -1.0).edge[0]).toBeCloseTo(0.5, 6);
    // The vertical joints of neighbouring rows sit half a slab apart.
    const x0 = 0.6 - 1e-6;
    expect(pavingSlab(x0, 0.1).edge[0]).toBeLessThan(1e-3);
    expect(pavingSlab(x0, 0.9).edge[0]).toBeCloseTo(0.6, 3);
  });

  it("filters the joints: full on a joint up close, a share of the pixel far away, nothing beside it", () => {
    const J = pv.jointM;
    expect(jointCoverage(0, 0.001, J)).toBe(1);
    expect(jointCoverage(J + 0.01, 0.001, J)).toBe(0);
    // A pixel 10 cm across centred on the joint: the joint covers 2.4 cm of it.
    expect(jointCoverage(0, 0.1, J)).toBeCloseTo((2 * J) / 0.1, 6);
    // Averaged over a slab, the coverage is the joint's width share whatever the pixel size (no extra grey far away).
    for (const w of [0.002, 0.03, 0.3]) {
      let sum = 0;
      const n = 4000;
      for (let i = 0; i < n; i++) {
        const x = ((i + 0.5) / n) * 1.2;
        sum += jointCoverage(Math.min(x, 1.2 - x), w, J);
      }
      expect(sum / n).toBeCloseTo((2 * J) / 1.2, 2);
    }
  });

  it("passes uv1 to the fragment shader, v turned back; nothing for rock and ground", () => {
    const v = detailVertexGlsl("paving");
    expect(v.pars).toContain("#ifndef USE_UV1\nattribute vec2 uv1;\n#endif");
    expect(v.pars).toContain("varying vec2 vSectUv1;");
    expect(v.main).toContain("vSectUv1 = vec2( uv1.x, 1.0 - uv1.y );");
    expect(detailVertexGlsl("rock")).toEqual({ pars: "", main: "" });
    expect(detailVertexGlsl("ground")).toEqual({ pars: "", main: "" });
  });

  it("GLSL: the slab grid, filtered joints, the scan per slab, every uniform once", () => {
    const g = detailGlsl("paving");
    for (const fn of ["vec2 sectSlab( vec2 q, out vec2 e )", "float sectDetail( vec3 p )", "vec3 sectPaving( vec3 col", "vec3 sectHash3( vec2 p )"]) {
      expect(count(g, fn), fn).toBe(1);
    }
    for (const u of ["sampler2D tSectDetail", "float uSectDetailOn", "sampler2D tSectGroundNoise"]) expect(count(g, `uniform ${u};`), u).toBe(1);
    expect(count(g, "varying vec2 vSectUv1;")).toBe(1);
    expect(g).toContain(`mod( row, 2.0 ) < 0.5 ? ${glslFloat(pv.slabM[0] * pv.offset)} : 0.0`);
    expect(g).toContain(glslFloat(1 / pv.slabM[1]));
    expect(g).toContain("fwidth( vSectUv1 )");
    expect(count(g, "textureGrad( tSectDetail")).toBe(2);
    expect(g).toContain(glslFloat(1 / DETAIL_TILE_M.paving));
    expect(g).not.toContain("sectGroundLayers");
    const a = detailApplyGlsl("paving");
    expect(a).toContain("sectPaving( diffuseColor.rgb, vSectWorld, sectPn, sectDd, sectDs )");
    expect(a).toContain(`smoothstep( ${glslFloat(pv.fadeNear)}, ${glslFloat(pv.fadeFar)}`);
    expect(a).toContain("uSectDetailOn");
    expect(a).not.toMatch(/\bif\b/);
  });

  it("has its own program key, which follows the layer and the vertex code", () => {
    const k = detailProgramKey("paving");
    expect(k).not.toBe(detailProgramKey("rock"));
    expect(k).not.toBe(detailProgramKey("ground"));
    const look = { ...DETAIL_LOOK, paving: { ...DETAIL_LOOK.paving, joint: { ...DETAIL_LOOK.paving.joint, dark: 0.3 } } };
    expect(detailProgramKey("paving", look)).not.toBe(k);
  });

  it("factor: the scan's gain and fade like the other classes", () => {
    expect(detailFactor("paving", 0.5, 1, 0.5)).toBe(1);
    expect(detailFactor("paving", 1, 1, 0.5)).toBeCloseTo(Math.pow(2, 0.5 * pv.gain), 6);
    expect(detailFactor("paving", 1, pv.fadeFar + 1, 0.5)).toBe(1);
  });
});

describe("tiles (roof courses)", () => {
  const t = DETAIL_LOOK.tiles;

  it("reads the class and passes uv1 like paving", () => {
    expect(detailClass("tiles")).toBe("tiles");
    expect(detailVertexGlsl("tiles")).toEqual(detailVertexGlsl("paving"));
  });

  it("keeps the bake's mean over a course and a lap, for dark and pale tiles", () => {
    for (const lum of [0.005, 0.05, 0.4]) {
      let sum = 0;
      const n = 400;
      for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) sum += tileCourseFactor((i + 0.5) / n, (j + 0.5) / n, lum);
      expect(sum / (n * n), `lum ${lum}`).toBeCloseTo(1, 2);
    }
  });

  it("draws the material's bands: crease and lip darker than the crest, less on a pale glaze", () => {
    const crest = tileCourseFactor(0, 0.5, 0.01);
    const crease = tileCourseFactor(0.25, 0.5, 0.01);
    const lip = tileCourseFactor(0.5, 0.95, 0.01);
    expect(crest).toBeGreaterThan(1);
    expect(crease).toBeLessThan(crest * 0.7);
    expect(lip).toBeLessThan(1);
    const paleCrease = tileCourseFactor(0.25, 0.5, 0.5);
    expect(paleCrease / tileCourseFactor(0, 0.5, 0.5)).toBeGreaterThan(crease / crest);
    // Symmetric about the crest.
    expect(tileCourseFactor(0.3, 0.5, 0.05)).toBeCloseTo(tileCourseFactor(-0.3, 0.5, 0.05), 9);
  });

  it("fades each axis to its mean when a pixel covers more than half a course", () => {
    expect(tileCourseFactor(0.25, 0.5, 0.01, t.fade[1], 0)).toBeCloseTo(tileCourseFactor(0.6, 0.5, 0.01, t.fade[1], 0), 9);
    expect(tileCourseFactor(0.25, 0.95, 0.01, t.fade[1], t.fade[1])).toBe(1);
    expect(tileCourseFactor(0.25, 0.5, 0.01, t.fade[0], 0)).toBeCloseTo(tileCourseFactor(0.25, 0.5, 0.01), 9);
  });

  it("GLSL: sectTiles on the texel before the grade, normalised by the bands' means, filtered by fwidth", () => {
    const g = detailGlsl("tiles");
    const m = tileMeans();
    expect(count(g, "vec3 sectTiles( vec3 col, vec3 texel )")).toBe(1);
    expect(count(g, "varying vec2 vSectUv1;")).toBe(1);
    expect(g).toContain("fwidth( q )");
    expect(g).toContain(glslFloat(1 + t.crest.lift * m.crest));
    expect(g).not.toContain("uniform");
    expect(detailApplyGlsl("tiles")).toBe("  diffuseColor.rgb = sectTiles( diffuseColor.rgb, sectTexel );");
    expect(detailProgramKey("tiles")).not.toBe(detailProgramKey("paving"));
    expect(m.crest).toBeCloseTo(0.14, 3);
    expect(m.lip).toBeGreaterThan(0.1);
  });
});

describe("the range look's detail layers (range-look.ts)", () => {
  it("draws the range rock's water streaks with the far rock layer, on the range only", () => {
    const g = detailGlsl("rock");
    expect(count(g, "float sectRockStreak( vec3 p )")).toBe(1);
    expect(g.indexOf("float sectNoise3( vec3 x )")).toBeLessThan(g.indexOf("float sectRockStreak( vec3 p )"));
    expect(g).toContain(glslFloat(1 / RANGE_LOOK.rock.streaks.lengthM));
    // Still one read of the noise texture's top level (the streak calls sectNoise3).
    expect(count(g, "textureLod( tSectGroundNoise")).toBe(1);
    const a = detailApplyGlsl("rock");
    expect(a).toContain(`1.0 - ${glslFloat(RANGE_LOOK.rock.streaks.dark)} * sectRockStreak( vSectWorld ) * sectRf * sectRw;`);
    expect(a.indexOf("sectRockFar( vSectWorld )")).toBeLessThan(a.indexOf("sectRockStreak( vSectWorld )"));
  });

  it("turns far range lawns toward the canopy, from `near` to `far` metres", () => {
    const a = detailApplyGlsl("ground");
    const gr = RANGE_LOOK.ground;
    expect(a).toContain(`smoothstep( ${glslFloat(gr.near)}, ${glslFloat(gr.far)}, sectDd ) * sectRw * ${glslFloat(gr.amount)}`);
    expect(a.indexOf("sectSheen( vSectWorld")).toBeLessThan(a.indexOf("float sectGl"));
    expect(detailApplyGlsl("paving")).not.toContain("sectRw");
    expect(detailApplyGlsl("tiles")).not.toContain("sectRw");
  });

  it("the range's moss test is the detail's mossy-rock test", () => {
    for (const hex of ["#5f6a33", "#53673a", "#c8875a", "#8a8070", "#36503a"]) {
      const t = [1, 3, 5].map((i) => {
        const c = parseInt(hex.slice(i, i + 2), 16) / 255;
        return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
      }) as [number, number, number];
      expect(mossGate(t)).toBeCloseTo(greenRockGate(t), 9);
    }
  });

  it("changes the rock and ground programs' keys with the range look", () => {
    const tweaked = { ...RANGE_LOOK, rock: { ...RANGE_LOOK.rock, streaks: { ...RANGE_LOOK.rock.streaks, dark: 0.5, lengthM: 55 } } };
    expect(detailGlsl("rock", DETAIL_LOOK, tweaked)).not.toBe(detailGlsl("rock"));
    expect(detailApplyGlsl("rock", DETAIL_LOOK, tweaked)).not.toBe(detailApplyGlsl("rock"));
  });
});
