import { readFileSync } from "node:fs";
import path from "node:path";
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
  ROCK_SCAN,
  rockDetailFactor,
  rockFarFactor,
  rockFarFade,
  rockFarOctaves,
  rockMidFade,
  rockMidLum,
  rockMidMossGate,
  rockMidPatch,
  rockMidTexel,
  rockScanUv,
  sheenFactor,
  tileCourseFactor,
  tileMeans,
  weatherApplyGlsl,
  weatherGlsl,
} from "./detail";
import { glslFloat } from "./glsl";
import { clumpField, groundNoise, rankBytes, tilingNoise } from "./noise";
import { mossGate, RANGE_LOOK } from "./range-look";

const count = (s: string, sub: string) => s.split(sub).length - 1;

/** GLSL's smoothstep. */
const smooth = (a: number, b: number, x: number) => {
  const t = Math.min(Math.max((x - a) / (b - a), 0), 1);
  return t * t * (3 - 2 * t);
};

/** Mirror of the paving's sectHash3, in 32-bit floats as the GPU works it. */
function sectHash3(x: number, y: number): [number, number, number] {
  const f = Math.fround;
  const fract = (v: number) => f(v - Math.floor(v));
  const q = [fract(f(f(x) * f(0.1031))), fract(f(f(y) * f(0.103))), fract(f(f(x) * f(0.0973)))];
  const k = f(33.33);
  const d = f(f(f(q[0] * f(q[1] + k)) + f(q[1] * f(q[0] + k))) + f(q[2] * f(q[2] + k)));
  const [a, b, c] = q.map((v) => f(v + d));
  return [fract(f(f(a + b) * c)), fract(f(f(a + c) * b)), fract(f(f(b + c) * a))];
}

describe("detail classes and tags", () => {
  it("tiles each channel at its scan's real size", () => {
    // R and B both come from the rock photo (B is its middle band now, not moss).
    expect(DETAIL_TILE_M).toEqual({ rock: 8.14, ground: 2.0, paving: 2.5 });
    expect(DETAIL_TILE_M.rock).toBe(ROCK_SCAN.tileM);
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
  it("rock: three projections on the flat face normal, two layers of red and the band in blue, its own tile", () => {
    const g = detailGlsl("rock");
    expect(g).toContain("vec2 sectRockDetail( vec3 p, bool fine, bool mid )");
    expect(g).not.toContain("float sectDetail(");
    expect(g).toContain("uniform sampler2D tSectDetail;");
    expect(g).toContain("uniform float uSectDetailOn;");
    expect(g).toContain("cross( dFdx( p ), dFdy( p ) )");
    // Still six reads: the band comes from the first three (.rb), the larger three are the fine layer's only.
    expect(count(g, "textureGrad( tSectDetail")).toBe(6);
    expect(count(g, "textureGrad( tSectDetail, d")).toBe(3);
    expect(count(g, ").rb;")).toBe(3);
    expect(g).toContain(glslFloat(1 / DETAIL_TILE_M.rock));
    // Softer than the first 6, so the pattern jumps less at each triangle edge.
    expect(DETAIL_LOOK.sharpness).toBe(3);
    expect(g).toContain(`vec3( ${glslFloat(DETAIL_LOOK.sharpness)} )`);
  });

  it("rock's second layer is not turned (mtn_cliff's grain runs one way); ground and paving keep layer2's turn", () => {
    expect(DETAIL_LOOK.rockLayer2.angle).toBe(0);
    expect(detailGlsl("rock")).toContain("mat2 r = mat2( 1.0, 0.0, 0.0, 1.0 );");
    expect(DETAIL_LOOK.layer2.angle).not.toBe(0);
    const turn = `mat2( ${glslFloat(Math.cos(DETAIL_LOOK.layer2.angle))}, ${glslFloat(Math.sin(DETAIL_LOOK.layer2.angle))}`;
    expect(detailGlsl("ground")).toContain(turn);
    expect(detailGlsl("paving")).toContain(turn);
    expect(detailGlsl("rock")).not.toContain(turn);
  });

  it("ground: straight down (Y up), two layers, green channel, its own tile", () => {
    const g = detailGlsl("ground");
    const photo = g.slice(g.indexOf("float sectDetail("));
    expect(photo).toContain("p.xz");
    expect(photo).toContain("dFdx( q )");
    expect(count(g, "textureGrad( tSectDetail")).toBe(2);
    expect(count(photo, ").g")).toBe(2);
    expect(g).toContain(glslFloat(1 / DETAIL_TILE_M.ground));
  });

  it("skips the layers that have faded to nothing, with every derivative taken before the branch", () => {
    // Each skipped layer: all dFdx / dFdy first, then the early-out, then only textureGrad reads.
    const beforeBranch = (g: string, fn: string, branch: string, read = "textureGrad(") => {
      const body = g.slice(g.indexOf(fn));
      const at = body.indexOf(branch);
      expect(at, `${fn} has ${branch}`).toBeGreaterThan(0);
      const [before, after] = [body.slice(0, at), body.slice(at, body.indexOf("\n}\n", at))];
      expect(before).toContain("dFdx(");
      expect(after).not.toMatch(/dFd[xy]|fwidth|texture2D/);
      expect(after).toContain(read);
    };
    const rock = detailGlsl("rock");
    const ground = detailGlsl("ground");
    beforeBranch(rock, "vec2 sectRockDetail( vec3 p, bool fine, bool mid )", "if ( !fine && !mid ) return vec2( 0.5 );");
    beforeBranch(rock, "float sectRockPatch( vec3 p, bool on )", "if ( !on ) return 1.0;", "textureLod(");
    beforeBranch(ground, "float sectDetail( vec3 p, bool on )", "if ( !on ) return 0.5;");
    beforeBranch(ground, "float sectSheen(", "if ( f <= 0.0 ) return 1.0;");
    beforeBranch(ground, "vec3 sectGroundLayers(", "if ( sectCf > 0.0 )", "sectClump( p, sectW, sectGa, sectGb )");
    // No implicit-derivative read is left in the detail stack (inside a branch it would be undefined).
    for (const g of [rock, ground]) expect(g).not.toContain("texture2D( tSectDetail");
    expect(ground).not.toContain("texture2D( tSectClump");
    // The call sites hand each layer its own fade, and the ground tint and far rock keep running.
    expect(detailApplyGlsl("rock")).toContain("sectRockDetail( vSectWorld, sectDf > 0.0, sectDm != 0.0 )");
    expect(detailApplyGlsl("ground")).toContain("sectDetail( vSectWorld, sectDf > 0.0 )");
    expect(ground).toMatch(/col = mix\( col, sectGroundTint\( col, p \), uSectGroundLayers \);\n {2}float sectW/);
    expect(rock).toContain("textureLod( tSectGroundNoise");
    expect(detailApplyGlsl("rock")).toContain("sectRockFar( vSectWorld )");
  });

  it("declares every uniform once, in both classes", () => {
    const both = ["sampler2D tSectDetail", "float uSectDetailOn", "sampler2D tSectClump", "sampler2D tSectGroundNoise", "float uSectGroundLayers", "float uSectTime", "vec3 uSectSun"];
    for (const kind of ["rock", "ground"] as const) {
      const g = detailGlsl(kind);
      for (const u of both) expect(count(g, `uniform ${u};`), `${kind} ${u}`).toBe(1);
      for (const u of ["float uSectRockFar", "float uSectRockOctaves", "float uSectRockMid"]) expect(count(g, `uniform ${u};`), `${kind} ${u}`).toBe(kind === "rock" ? 1 : 0);
      // Every function the apply step calls is defined, once.
      for (const fn of ["vec3 sectGroundTint(", "float sectClump(", "vec3 sectGroundLayers(", ...(kind === "rock" ? ["vec2 sectRockDetail(", "float sectRockPatch("] : ["float sectDetail("])]) {
        expect(count(g, fn), fn).toBe(1);
      }
    }
    expect(detailGlsl("rock")).toContain("float sectRockFar( vec3 p )");
    expect(detailGlsl("rock")).toContain("float sectNoise3( vec3 x )");
    expect(detailGlsl("ground")).not.toContain("sectRockFar");
  });

  it("the far rock layer reads the noise's top level (no derivatives) and skips its second octave on mid", () => {
    const g = detailGlsl("rock");
    // One read in sectNoise3 (the far layer's), three in sectRockPatch (the middle band's patches).
    expect(count(g, "textureLod( tSectGroundNoise")).toBe(4);
    const noise3 = g.slice(g.indexOf("float sectNoise3( vec3 x )"), g.indexOf("\n}\n", g.indexOf("float sectNoise3( vec3 x )")));
    expect(count(noise3, "textureLod( tSectGroundNoise")).toBe(1);
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
    // The clumps: their fade times the switch, times how patchy the lawn is there.
    expect(g2).toMatch(/smoothstep\( [\d.]+, [\d.]+, dist \) \) \* uSectGroundLayers\s+\* mix\(/);
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

  it("comes and goes over the lawn: the strength runs from patchy[0] to patchy[1] times what it was", () => {
    const c = DETAIL_LOOK.clump;
    const [p0, p1] = c.patchy;
    expect(p0).toBeGreaterThanOrEqual(0);
    expect(p0).toBeLessThan(p1);
    // The ground noise's A field at blobs patchyM across, read before the clumps' branch.
    const g = detailGlsl("ground");
    const read = `mix( ${glslFloat(p0)}, ${glslFloat(p1)}, texture2D( tSectGroundNoise, p.xz * ${glslFloat(1 / (c.patchyM * DETAIL_NOISE.ground.cells))} + vec2( 0.35, 0.91 ) ).a )`;
    expect(count(g, read)).toBe(1);
    expect(g.indexOf(read)).toBeLessThan(g.indexOf("if ( sectCf > 0.0 )"));
    // Mirror of sectCf (the switch on): the fade times the patchy field's value a (0..1).
    const strength = (dist: number, a: number) => (1 - smooth(c.fadeNear, c.fadeFar, dist)) * (p0 + (p1 - p0) * a);
    for (const dist of [0, c.fadeNear, (c.fadeNear + c.fadeFar) / 2]) {
      const was = detailFade(dist, c.fadeNear, c.fadeFar);
      for (let a = 0; a <= 1; a += 0.125) {
        expect(strength(dist, a)).toBeGreaterThanOrEqual(p0 * was - 1e-12);
        expect(strength(dist, a)).toBeLessThanOrEqual(p1 * was + 1e-12);
      }
    }
    expect(strength(c.fadeFar, 1)).toBe(0);
    // At its strongest, the deepest gap still keeps some of its colour.
    expect(1 + p1 * (clumpFactor(0, 0, 1, 0) - 1)).toBeGreaterThan(0);
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

describe("paving wear (replaced stones, stains, dust, cracks)", () => {
  const pv = DETAIL_LOOK.paving;
  const [bw, rh] = pv.slabM;
  const g = detailGlsl("paving");

  /** Mirror of sectSlabPos: the point's place in slab (col, row), metres from its low corner. */
  const slabPos = (x: number, y: number, col: number, row: number): [number, number] => {
    // GLSL's mod( row, 2.0 ) < 0.5: the even rows, negative ones too, are shifted.
    const even = ((row % 2) + 2) % 2 === 0;
    return [x + (even ? bw * pv.offset : 0) - col * bw, y - row * rh];
  };

  it("hashes each slab with the shader's own sectHash3", () => {
    expect(g).toContain("vec3 q = fract( p.xyx * vec3( 0.1031, 0.1030, 0.0973 ) );\n  q += dot( q, q.yxz + 33.33 );\n  return fract( ( q.xxy + q.yzz ) * q.zyx );");
    for (const [x, y] of [[0, 0], [17.3, 17.3], [-3, 41.7]]) {
      for (const v of sectHash3(x, y)) {
        expect(v).toBeGreaterThanOrEqual(0);
        expect(v).toBeLessThan(1);
      }
    }
  });

  it("sectSlabPos finds the point inside the slab sectSlab gave it, on both rows", () => {
    expect(count(g, "vec2 sectSlabPos( vec2 q, vec2 id )")).toBe(1);
    expect(g).toContain(`mod( id.y, 2.0 ) < 0.5 ? ${glslFloat(bw * pv.offset)} : 0.0 ) - id.x * ${glslFloat(bw)}`);
    expect(g).toContain(`q.y - id.y * ${glslFloat(rh)}`);
    const rows = new Set<number>();
    for (let x = -3; x < 3; x += 0.137) {
      for (let y = -3; y < 3; y += 0.113) {
        const s = pavingSlab(x, y);
        rows.add(((s.row % 2) + 2) % 2);
        const [px, py] = slabPos(x, y, s.col, s.row);
        expect(px).toBeGreaterThanOrEqual(-1e-9);
        expect(px).toBeLessThan(bw + 1e-9);
        expect(py).toBeGreaterThanOrEqual(-1e-9);
        expect(py).toBeLessThan(rh + 1e-9);
        // Its distances to the sides are sectSlab's.
        expect(Math.min(px, bw - px)).toBeCloseTo(s.edge[0], 9);
        expect(Math.min(py, rh - py)).toBeCloseTo(s.edge[1], 9);
      }
    }
    expect(rows).toEqual(new Set([0, 1]));
  });

  it("replaces one slab in 1 / odd.share and cracks one in 1 / crack.share", () => {
    expect(g).toContain("vec3 h2 = sectHash3( id + 17.3 );");
    expect(g).toContain(`step( ${glslFloat(1 - pv.odd.share)}, h2.x )`);
    expect(g).toContain("vec3 h3 = sectHash3( id + 41.7 );");
    expect(g).toContain(`step( ${glslFloat(1 - pv.crack.share)}, h3.x )`);
    let n = 0;
    let odd = 0;
    let cracked = 0;
    // A plaza's worth of slabs, either side of the origin.
    for (let col = -50; col < 50; col++) {
      for (let row = -80; row < 80; row++) {
        n++;
        if (sectHash3(col + 17.3, row + 17.3)[0] >= Math.fround(1 - pv.odd.share)) odd++;
        if (sectHash3(col + 41.7, row + 41.7)[0] >= Math.fround(1 - pv.crack.share)) cracked++;
      }
    }
    expect(Math.abs(odd / n - pv.odd.share)).toBeLessThan(0.01);
    expect(Math.abs(cracked / n - pv.crack.share)).toBeLessThan(0.01);
  });

  it("a replaced stone keeps its brightness under the grey, then moves by up to +-odd.value", () => {
    expect(g).toContain(
      `mix( col, vec3( dot( col, vec3( 0.2126, 0.7152, 0.0722 ) ) ), ${glslFloat(pv.odd.grey)} ) * ( 1.0 + ( h2.y - 0.5 ) * ${glslFloat(2 * pv.odd.value)} )`,
    );
    const lum = (c: readonly number[]) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
    const replaced = (c: readonly number[], hy: number) => {
      const l = lum(c);
      return c.map((v) => (v + (l - v) * pv.odd.grey) * (1 + (hy - 0.5) * 2 * pv.odd.value));
    };
    const marble = [0.62, 0.58, 0.5];
    expect(lum(replaced(marble, 0.5))).toBeCloseTo(lum(marble), 12);
    for (let hy = 0; hy <= 1; hy += 0.125) {
      const r = lum(replaced(marble, hy)) / lum(marble);
      expect(r).toBeGreaterThanOrEqual(1 - pv.odd.value - 1e-12);
      expect(r).toBeLessThanOrEqual(1 + pv.odd.value + 1e-12);
    }
  });

  it("the grime band: never above 1, thinner as the pixel grows, the same grey over a slab", () => {
    const gm = pv.grime.widthM;
    expect(g).toContain("float gw = max( w.x, w.y );");
    expect(g).toContain(
      `float gr = ( 1.0 - smoothstep( 0.0, ${glslFloat(gm)} + gw, min( e.x, e.y ) ) ) * ${glslFloat(gm)} / ( ${glslFloat(gm)} + gw ) * jf * keep;`,
    );
    const grime = (e: number, gw: number) => ((1 - smooth(0, gm + gw, e)) * gm) / (gm + gw);
    for (let gw = 0; gw <= 2; gw += 0.05) {
      for (let e = 0; e <= 0.6; e += 0.01) {
        expect(grime(e, gw)).toBeLessThanOrEqual(1);
        expect(grime(e, gw)).toBeGreaterThanOrEqual(0);
      }
    }
    // At the joint it falls as the pixel's footprint grows.
    expect(grime(0, 0)).toBe(1);
    let prev = 1;
    for (const gw of [0.01, 0.03, 0.1, 0.3, 1]) {
      expect(grime(0, gw)).toBeLessThan(prev);
      prev = grime(0, gw);
    }
    // Averaged across a slab it covers the same share whatever the pixel size (it greys rather than
    // flickers, and adds no grey far away). Widened alone it covered several times as much.
    const mean = (f: (e: number) => number) => {
      const n = 6000;
      let s = 0;
      for (let i = 0; i < n; i++) {
        const x = ((i + 0.5) / n) * bw;
        s += f(Math.min(x, bw - x));
      }
      return s / n;
    };
    for (const gw of [0.001, 0.05, 0.2, 0.4]) expect(mean((e) => grime(e, gw))).toBeCloseTo(gm / bw, 3);
    expect(mean((e) => 1 - smooth(0, gm + 0.4, e))).toBeGreaterThan(5 * mean((e) => grime(e, 0.4)));
  });

  it("the crack: never above 1, fainter as the pixel grows, gone by crack.fadeFar and off the slab sides", () => {
    const w = pv.crack.widthM;
    expect(g).toContain("float cw = max( w.x, w.y );");
    expect(g).toContain(`float crack = ( 1.0 - smoothstep( ${glslFloat(w)}, ${glslFloat(w)} + cw, cd ) ) * ${glslFloat(w)} / ( ${glslFloat(w)} + cw )`);
    expect(g).toMatch(new RegExp(`smoothstep\\( ${glslFloat(pv.crack.fadeNear)}, ${glslFloat(pv.crack.fadeFar)}, dist \\) \\) \\* up;`));
    expect(pv.crack.fadeNear).toBeLessThan(pv.crack.fadeFar);
    const crack = (d: number, cw: number) => ((1 - smooth(w, w + cw, d)) * w) / (w + cw);
    // How much of a line across it the crack darkens (metres): 2 widths up close, 1 at most far away.
    const across = (cw: number) => {
      const n = 20000;
      const span = 2 * (w + cw);
      let s = 0;
      for (let i = 0; i < n; i++) s += crack(Math.abs(-span / 2 + ((i + 0.5) / n) * span), cw);
      return (s / n) * span;
    };
    let peak = 1;
    let total = Infinity;
    for (const cw of [1e-5, 0.002, 0.01, 0.05, 0.2]) {
      for (let d = 0; d <= 0.3; d += 0.001) {
        expect(crack(d, cw)).toBeLessThanOrEqual(1);
        expect(crack(d, cw)).toBeGreaterThanOrEqual(0);
      }
      expect(crack(0, cw)).toBeLessThanOrEqual(peak);
      peak = crack(0, cw);
      expect(across(cw)).toBeLessThan(total);
      total = across(cw);
      expect(total).toBeGreaterThan(w * 0.99);
      expect(total).toBeLessThan(2 * w * 1.01);
    }
    expect(peak).toBeLessThan(0.05);
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
    // Still one read of the noise texture's top level for the far layers (the streak calls sectNoise3); the
    // other three are the middle band's patches (sectRockPatch).
    expect(count(g, "textureLod( tSectGroundNoise")).toBe(4);
    expect(count(g.slice(0, g.indexOf("float sectRockPatch(")), "textureLod( tSectGroundNoise")).toBe(1);
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

describe("far spires (the backdrop's far set and the areas' stand-ins)", () => {
  const rock = detailApplyGlsl("rock");
  const fs = DETAIL_LOOK.rockFarSet;

  it("reads the far rock layer again at the size of a spire, with flutes, strata and ledges, and no fade", () => {
    expect(rock).toContain("#ifdef SECT_FAR_SET");
    expect(rock).toContain(`sectRockFar( vSectWorld * ${glslFloat(fs.scale)} ) * ${glslFloat(fs.gain)}`);
    expect(rock).toContain(`vec3( ${glslFloat(fs.flute)}, ${glslFloat(fs.flute * fs.fluteY)}, ${glslFloat(fs.flute)} )`);
    expect(rock).toContain(`sectRockFar( vSectWorld + 41.0 ) * ${glslFloat(fs.fine)}`);
    expect(rock).toContain(`sin( vSectWorld.y * ${glslFloat((2 * Math.PI) / fs.ledgeM)}`);
    // Squeezed along the height: flutes run up and down.
    expect(fs.fluteY).toBeLessThan(0.3);
    // Not on canopy or moss.
    expect(rock).toContain("( 1.0 - sectGr ) * uSectDetailOn );");
  });

  it("gives a stand-in's buildings their baked colour back: only rock-coloured faces keep the layers", () => {
    expect(rock).toContain("vec3 sectOrig = diffuseColor.rgb;");
    expect(rock.indexOf("vec3 sectOrig = diffuseColor.rgb;")).toBeGreaterThan(0);
    expect(rock.indexOf("vec3 sectOrig = diffuseColor.rgb;")).toBeLessThan(rock.indexOf("sectRockDetail( vSectWorld"));
    expect(rock).toContain("#ifdef SECT_STANDIN");
    expect(rock).toContain("diffuseColor.rgb = mix( sectOrig, diffuseColor.rgb, max( sectWarm, sectGrey ) );");
    const g = fs.standIn;
    for (const pair of [g.greenOverRed, g.sat, g.white, g.flat, g.shade, g.steep]) expect(pair[0]).toBeLessThan(pair[1]);
    // The other classes have no such branch.
    expect(detailApplyGlsl("ground")).not.toContain("SECT_STANDIN");
  });
});

describe("the rock photo's middle band (detail.webp B, read where the bake read the photo)", () => {
  const repo = path.resolve(__dirname, "../../../..");
  const materialsPy = readFileSync(path.join(repo, "blender/xianxia-sect/sect/lib/materials.py"), "utf8");
  const prep = readFileSync(path.join(repo, "blender/xianxia-sect/tools/prep_textures.mjs"), "utf8");
  const match = (re: RegExp, s: string) => {
    const m = re.exec(s);
    expect(m, String(re)).toBeTruthy();
    return m!;
  };
  const g = detailGlsl("rock");
  const a = detailApplyGlsl("rock");
  const m = DETAIL_LOOK.rockMid;
  /** The bake's share of the photo's log luminance (materials.py _photo_mix: luminance ~ (1 - a h)(1 - a + a L) + a h L). */
  const mix = Number(match(/^ROCK_SCAN_MIX = ([\d.]+)/m, materialsPy)[1]);
  const hue = Number(match(/^ROCK_SCAN_HUE = ([\d.]+)/m, materialsPy)[1]);
  const share = mix + mix * hue * (1 - mix);

  /** Resolves #ifdef / #ifndef / #else / #endif for a set of defines. */
  const preprocess = (src: string, defs: string[]) => {
    const out: string[] = [];
    const stack: boolean[] = [];
    for (const line of src.split("\n")) {
      const t = line.trim();
      const d = /^#(ifdef|ifndef) (\w+)$/.exec(t);
      if (d) stack.push((d[1] === "ifdef") === defs.includes(d[2]));
      else if (t === "#else") stack.push(!stack.pop());
      else if (t === "#endif") stack.pop();
      else if (stack.every(Boolean)) out.push(line);
    }
    return out.join("\n");
  };

  /** A few hundred points from a fixed seed, in a 4 km cube round the origin. */
  const points = (() => {
    let s = 12345;
    const rnd = () => ((s = (Math.imul(s, 1103515245) + 12345) >>> 0) / 2 ** 32) * 4000 - 2000;
    return Array.from({ length: 500 }, () => [rnd(), rnd(), rnd()] as [number, number, number]);
  })();

  it("mirrors the bake's mapping of the photo (materials.py)", () => {
    // rock_cliff is the material with this photo; its tile, plane offsets and blend exponent.
    expect(materialsPy).toContain(`R("rock_cliff", _rock, scan="${ROCK_SCAN.scan}")`);
    const tile = match(new RegExp(`${ROCK_SCAN.scan}=dict\\(diff="${ROCK_SCAN.scan}_diff\\.jpg"[^)]*tile=\\(([\\d.]+), ([\\d.]+)\\)`), materialsPy);
    expect([Number(tile[1]), Number(tile[2])]).toEqual([ROCK_SCAN.tileM, ROCK_SCAN.tileM]);
    const offs = match(/offs = \(\(([\d.]+), ([\d.]+)\), \(([\d.]+), ([\d.]+)\), \(([\d.]+), ([\d.]+)\)\)/, materialsPy);
    expect(offs.slice(1).map(Number)).toEqual(ROCK_SCAN.offsets.flat());
    expect(Number(match(/^ROCK_SCAN_SHARP = ([\d.]+)/m, materialsPy)[1])).toBe(ROCK_SCAN.sharp);
    // The mapping itself: world (y, z), (x, z), (x, y) over the tile plus the offset, weighted by |normal|^sharp.
    expect(materialsPy).toContain("zip(((py, pz), (px, pz), (px, py)), offs)");
    expect(materialsPy).toContain("self.mapping(self.comb(a, b), scale=(1.0 / tu, 1.0 / tv, 1.0), offset=(ox, oy, 0.0))");
    expect(materialsPy).toContain("self.math('POWER', self.math('ABSOLUTE', c), sharp) for c in self.sep(self.geometry(\"Normal\"))");
    expect(materialsPy).toContain("g.triplanar([diff] + ([disp] if disp is not None else []), tile, ROCK_SCAN_SHARP)");
  });

  it("is cut from that photo at that tile, R as the fine layer and B as the band ROCK_SCAN names (prep_textures.mjs)", () => {
    const ch = Object.fromEntries(
      [...prep.matchAll(/\{ ch: '([RGB])', src: '([^']+)', tileM: ([\d.]+), band: ([^}]+) \}/g)].map((x) => [x[1], { src: x[2], tileM: Number(x[3]), band: x[4].trim() }]),
    );
    // A download (polyhaven/) or a tile made from one (derived/, tools/make_rock_tile.py).
    expect(ch.R.src).toMatch(new RegExp(`^(polyhaven|derived)/${ROCK_SCAN.scan}/${ROCK_SCAN.scan}_diff_4k\\.jpg$`));
    const photo = ch.R.src;
    expect(ch.R).toEqual({ src: photo, tileM: ROCK_SCAN.tileM, band: "[0, DETAIL_SIGMA_M]" });
    expect(ch.B).toEqual({ src: photo, tileM: ROCK_SCAN.tileM, band: "DETAIL_BAND_M" });
    expect(ch.G.tileM).toBe(DETAIL_TILE_M.ground);
    const band = match(/const DETAIL_BAND_M = \[([\d.]+), ([\d.]+)\];/, prep);
    expect([Number(band[1]), Number(band[2])]).toEqual([...ROCK_SCAN.bandM]);
    // The middle band: from the fine layer's 12 cm up to a metre.
    expect(ROCK_SCAN.bandM[0]).toBe(Number(match(/const DETAIL_SIGMA_M = ([\d.]+);/, prep)[1]));
    expect(ROCK_SCAN.bandM[1]).toBeGreaterThan(ROCK_SCAN.bandM[0] * 4);
    // prep prints the matching gain from the same share of the photo the bake holds.
    expect(prep).toContain(`const BAKE_SCAN_SHARE = ${mix} + ${mix} * ${hue} * (1 - ${mix});`);
  });

  it("sits between none and all of the gain that adds the band again at the bake's own strength", () => {
    expect(share).toBeCloseTo(0.732, 3);
    // Full strength was 2.48 on marble_cliff_06, where 2.0 was picked on the GPU (at 2.8 the abode's near cliff
    // is a net of cracks). mtn_cliff's is 1.84. The GPU look picks the gain for each photo, 0 (the band off) at
    // the least.
    const full = share / ROCK_SCAN.bandK;
    expect(m.gain).toBeGreaterThanOrEqual(0);
    expect(m.gain).toBeLessThanOrEqual(full);
  });

  it("reads at the bake's coordinates: the page's u is Blender's, its v Blender's turned over", () => {
    const T = ROCK_SCAN.tileM;
    // Blender plane i (its (y, z), (x, z), (x, y)) is the page projection along three x, z and y.
    const axes = ["x", "z", "y"] as const;
    for (const p of points) {
      const [bx, by, bz] = [p[0], -p[2], p[1]];
      const planes = [
        [by, bz],
        [bx, bz],
        [bx, by],
      ];
      planes.forEach(([u, v], i) => {
        const bl = [u / T + ROCK_SCAN.offsets[i][0], v / T + ROCK_SCAN.offsets[i][1]];
        const page = rockScanUv(p, axes[i]);
        expect(page[0]).toBeCloseTo(bl[0], 9);
        expect(page[1]).toBeCloseTo(-bl[1], 9);
      });
    }
  });

  it("the shader's three coordinates are rockScanUv's, weighted by the normal's matching component", () => {
    const evalTerm = (t: string, q: number[]) => {
      const x = match(/^(-?)q\.([xyz])(?: ([+-]) ([\d.]+))?$/, t.trim());
      const v = (x[1] ? -1 : 1) * q["xyz".indexOf(x[2])];
      return x[3] ? v + (x[3] === "+" ? 1 : -1) * Number(x[4]) : v;
    };
    const coords = [1, 2, 3].map((i) => match(new RegExp(`vec2 c${i} = vec2\\( ([^,]+), ([^)]+) \\);`), g));
    expect(g).toContain(`vec3 q = p * ${glslFloat(1 / ROCK_SCAN.tileM)};`);
    for (const p of points.slice(0, 50)) {
      const q = p.map((v) => v / ROCK_SCAN.tileM);
      (["x", "y", "z"] as const).forEach((axis, i) => {
        const uv = rockScanUv(p, axis);
        expect(evalTerm(coords[i][1], q)).toBeCloseTo(uv[0], 9);
        expect(evalTerm(coords[i][2], q)).toBeCloseTo(uv[1], 9);
      });
    }
    // c1 faces along x, c2 is level (y), c3 faces along z: the weights' x, y and z.
    expect(g).toContain("float a = t1.x * w.x + t2.x * w.y + t3.x * w.z;");
    expect(g).toContain("t1.y * wm.x + t2.y * wm.y + t3.y * wm.z");
  });

  it("blends the band with the bake's exponent, and reads it only once per plane (no rotated or larger read)", () => {
    expect(g).toContain(`vec3 wm = pow( abs( n ), vec3( ${glslFloat(ROCK_SCAN.sharp)} ) ) + 1e-4;`);
    expect(g).toContain(`vec3 w = pow( abs( n ), vec3( ${glslFloat(DETAIL_LOOK.sharpness)} ) ) + 1e-4;`);
    for (const i of [1, 2, 3]) expect(g).toContain(`vec2 t${i} = textureGrad( tSectDetail, c${i}, g${i}.xy, g${i}.zw ).rb;`);
    // The second layer's reads take red only, and only while the fine layer is on.
    expect([...g.matchAll(/textureGrad\( tSectDetail, d\d, h\d\.xy, h\d\.zw \)\.r\b(?!b)/g)].length).toBe(3);
    expect(g).toContain("if ( fine ) b = textureGrad( tSectDetail, d1,");
  });

  it("fades in from about 20 to 70 m and out from about 400 to 500 m", () => {
    expect(m.fadeIn[0]).toBeLessThan(m.fadeIn[1]);
    expect(m.fadeIn[1]).toBeLessThan(m.fadeOut[0]);
    expect(m.fadeOut[0]).toBeLessThan(m.fadeOut[1]);
    // It reaches well past the fine layer (gone by 150 m).
    expect(m.fadeOut[0]).toBeGreaterThan(DETAIL_LOOK.rock.fadeFar * 2);
    expect(rockMidFade(0)).toBe(0);
    expect(rockMidFade(m.fadeIn[0])).toBe(0);
    expect(rockMidFade(m.fadeIn[1])).toBe(1);
    expect(rockMidFade((m.fadeIn[1] + m.fadeOut[0]) / 2)).toBe(1);
    expect(rockMidFade(m.fadeOut[0])).toBe(1);
    expect(rockMidFade(m.fadeOut[1])).toBe(0);
    expect(rockMidFade(m.fadeOut[1] * 2)).toBe(0);
    let prev = 0;
    for (let d = m.fadeIn[0]; d <= m.fadeIn[1]; d += 1) {
      expect(rockMidFade(d)).toBeGreaterThanOrEqual(prev);
      prev = rockMidFade(d);
    }
    for (let d = m.fadeOut[0]; d <= m.fadeOut[1]; d += 1) {
      expect(rockMidFade(d)).toBeLessThanOrEqual(prev);
      prev = rockMidFade(d);
    }
    expect(a).toContain(
      `float sectDm = smoothstep( ${glslFloat(m.fadeIn[0])}, ${glslFloat(m.fadeIn[1])}, sectDd ) * ( 1.0 - smoothstep( ${glslFloat(m.fadeOut[0])}, ${glslFloat(m.fadeOut[1])}, sectDd ) ) * uSectDetailOn * uSectRockMid * sectRockMidOn;`,
    );
  });

  it("is off on the far set and the stand-ins (SECT_FAR_SET), on everywhere else", () => {
    const src = `${g}\n${a}`;
    const far = preprocess(src, ["SECT_FAR_SET"]);
    const standIn = preprocess(src, ["SECT_FAR_SET", "SECT_STANDIN"]);
    const near = preprocess(src, []);
    for (const s of [far, standIn]) {
      expect(s).toContain("const float sectRockMidOn = 0.0;");
      expect(s).not.toContain("const float sectRockMidOn = 1.0;");
    }
    expect(near).toContain("const float sectRockMidOn = 1.0;");
    expect(near).not.toContain("const float sectRockMidOn = 0.0;");
    // The mirror: on the far set only the fine layer is left.
    expect(rockDetailFactor(0.7, 0.9, 30, 0.5, { farSet: true })).toBeCloseTo(detailFactor("rock", 0.7, 30, 0.5), 12);
    expect(rockDetailFactor(0.5, 0.9, 200, 0.5, { farSet: true })).toBe(1);
  });

  it("is a gain in stops with the fine layer, less in shade, symmetric, and nothing at mid grey", () => {
    expect(a).toContain(`diffuseColor.rgb *= exp2( ( sectRd.x - 0.5 ) * ${glslFloat(DETAIL_LOOK.rock.gain)} * sectDf * sectDs + ( sectRd.y - 0.5 ) * sectDb );`);
    for (const d of [10, 50, 200, 450, 900]) expect(rockDetailFactor(0.5, 0.5, d, 0.3)).toBe(1);
    // At 200 m only the band is left, at full strength: (B - 0.5) x gain stops.
    expect(Math.log2(rockDetailFactor(0.9, 0.8, 200, 0.5))).toBeCloseTo(0.3 * m.gain, 9);
    expect(Math.log2(rockDetailFactor(0.5, 0.8, 200, 0.5))).toBeCloseTo(-Math.log2(rockDetailFactor(0.5, 0.2, 200, 0.5)), 9);
    // Under 20 m only the fine layer: the same as detailFactor.
    expect(rockDetailFactor(0.8, 0.1, 10, 0.5)).toBeCloseTo(detailFactor("rock", 0.8, 10, 0.5), 12);
    const dark = Math.abs(Math.log2(rockDetailFactor(0.5, 0.8, 200, 0.005)));
    expect(dark).toBeGreaterThan(0);
    expect(dark).toBeLessThan(Math.abs(Math.log2(rockDetailFactor(0.5, 0.8, 200, 0.4))));
    // Its gain is the uniform's: 0 turns the band off, double doubles it.
    expect(rockDetailFactor(0.5, 0.8, 200, 0.5, { gain: 0 })).toBe(1);
    expect(Math.log2(rockDetailFactor(0.5, 0.8, 200, 0.5, { gain: 2 * m.gain }))).toBeCloseTo(0.6 * m.gain, 9);
  });

  it("reads past the fine layer only while the band is on, and keeps every derivative before the branch", () => {
    expect(a).toContain("vec2 sectRd = sectRockDetail( vSectWorld, sectDf > 0.0, sectDm != 0.0 );");
    expect(a.indexOf("float sectDm =")).toBeLessThan(a.indexOf("sectRockDetail("));
    expect(a).not.toMatch(/\bif\b/);
  });

  it("takes its gain from a uniform (no recompile to tune it); the fades are compiled in", () => {
    const louder = { ...DETAIL_LOOK, rockMid: { ...m, gain: m.gain * 3 } };
    expect(detailProgramKey("rock", louder)).toBe(detailProgramKey("rock"));
    expect(detailGlsl("rock", louder)).toBe(g);
    const longer = { ...DETAIL_LOOK, rockMid: { ...m, fadeOut: [450, 600] } } as unknown as typeof DETAIL_LOOK;
    expect(detailProgramKey("rock", longer)).not.toBe(detailProgramKey("rock"));
    expect(count(g, "uniform float uSectRockMid;")).toBe(1);
    expect(detailGlsl("ground")).not.toContain("uSectRockMid");
    expect(detailGlsl("paving")).not.toContain("uSectRockMid");
  });

  // The round 58 review: the band never showed on shaded faces, sat on moss once, and read as one even
  // pattern of cells.
  it("has its own floor in shade: at luminance 0.01 it is 0.85 of the band at 0.3, where the fine layer keeps 0.4", () => {
    const d = DETAIL_LOOK.dark;
    expect(m.darkFloor).toBe(0.85);
    expect(d.floor).toBe(0.4);
    // Both luminances sit off the ramp: 0.01 under its foot, 0.3 over its top.
    expect(0.01).toBeLessThan(d.lo);
    expect(0.3).toBeGreaterThan(d.hi);
    // The band alone (at 200 m the fine layer is gone), then the fine layer alone (at 10 m the band is not in yet).
    const band = (lum: number) => Math.log2(rockDetailFactor(0.5, 0.8, 200, lum));
    const fine = (lum: number) => Math.log2(rockDetailFactor(0.8, 0.5, 10, lum));
    expect(band(0.01) / band(0.3)).toBeCloseTo(0.85, 12);
    expect(fine(0.01) / fine(0.3)).toBeCloseTo(0.4, 12);
    // Both at once (100 m): each keeps its own floor.
    const fineFade = detailFade(100, DETAIL_LOOK.rock.fadeNear, DETAIL_LOOK.rock.fadeFar);
    expect(fineFade).toBeGreaterThan(0);
    expect(Math.log2(rockDetailFactor(0.8, 0.8, 100, 0.01))).toBeCloseTo(0.3 * DETAIL_LOOK.rock.gain * fineFade * d.floor + 0.3 * m.gain * m.darkFloor, 9);
    // Up the ramp the band's scale rises from its floor to 1, and never sits under the fine layer's.
    for (let lum = 0; lum <= 0.2; lum += 0.005) {
      expect(detailDarkScale(lum, DETAIL_LOOK, m.darkFloor)).toBeGreaterThanOrEqual(detailDarkScale(lum));
      expect(band(lum) / band(0.3)).toBeCloseTo(detailDarkScale(lum, DETAIL_LOOK, m.darkFloor), 12);
    }
    // The shader: the band's weight on the same ramp with its own floor and without sectDs; the fine layer keeps sectDs.
    const weight = /float sectDb = [^;]*;/.exec(a)![0];
    expect(weight).toContain(`sectDm * mix( ${glslFloat(m.darkFloor)}, 1.0, smoothstep( ${glslFloat(d.lo)}, ${glslFloat(d.hi)}, sectDl ) )`);
    expect(weight).not.toContain("sectDs");
    expect(a).toContain(`( sectRd.x - 0.5 ) * ${glslFloat(DETAIL_LOOK.rock.gain)} * sectDf * sectDs + `);
    expect(a.indexOf("float sectDl =")).toBeLessThan(a.indexOf("float sectDb ="));
  });

  it("is gone on full moss; the moss gate comes before it and reads only the texel before any layer", () => {
    // A green texel before the grade opens the gate fully.
    const green = [0.07, 0.19, 0.03] as const;
    expect(greenRockGate(green)).toBe(1);
    expect(rockDetailFactor(0.5, 0.9, 200, 0.5, { moss: greenRockGate(green) })).toBe(1);
    expect(rockDetailFactor(0.5, 0.1, 300, 0.01, { moss: 1, patch: 1 })).toBe(1);
    // Half open, half the band.
    expect(Math.log2(rockDetailFactor(0.5, 0.9, 200, 0.5, { moss: 0.5 }))).toBeCloseTo(0.5 * Math.log2(rockDetailFactor(0.5, 0.9, 200, 0.5)), 12);
    // The fine layer is as before on moss.
    for (const dist of [10, 100]) expect(rockDetailFactor(0.8, 0.9, dist, 0.3, { moss: 1 })).toBeCloseTo(detailFactor("rock", 0.8, dist, 0.3), 12);
    // The shader: the gate, then the band's weight (times 1 - sectGr), the band, then the ground's layers on moss as before.
    const order = [
      "vec3 sectSq = sqrt( max( sectTexel, vec3( 0.0 ) ) );",
      "float sectMx = max( sectSq.r, sectSq.g );",
      "float sectGr =",
      "float sectDb =",
      "vec2 sectRd = sectRockDetail(",
      "diffuseColor.rgb *= exp2( ( sectRd.x - 0.5 )",
      "diffuseColor.rgb = mix( diffuseColor.rgb, sectGroundLayers( diffuseColor.rgb, vSectWorld, sectDv / sectDd, sectDd ), sectGr );",
      "float sectRf =",
    ].map((s) => a.indexOf(s));
    for (const at of order) expect(at).toBeGreaterThan(0);
    for (let i = 1; i < order.length; i++) expect(order[i]).toBeGreaterThan(order[i - 1]);
    // The band's own gate is the same one with a wider hue, so it is at least as closed as sectGr everywhere.
    expect(/float sectDb = [^;]*;/.exec(a)![0]).toContain(`* ( 1.0 - smoothstep( ${glslFloat(m.mossHue[0])}, ${glslFloat(m.mossHue[1])}, sectGh ) * sectGs ) *`);
    expect(a).toContain(`float sectGr = smoothstep( ${glslFloat(DETAIL_LOOK.greenRock.hue[0])}, ${glslFloat(DETAIL_LOOK.greenRock.hue[1])}, sectGh ) * sectGs;`);
    expect(m.mossHue[0]).toBeLessThan(DETAIL_LOOK.greenRock.hue[0]);
    expect(m.mossHue[1]).toBeLessThan(DETAIL_LOOK.greenRock.hue[1]);
    for (const t of [green, [0.3, 0.26, 0.05], [0.5, 0.3, 0.12], [0.2, 0.2, 0.2], [0.6, 0.5, 0.3]] as const) expect(rockMidMossGate(t)).toBeGreaterThanOrEqual(greenRockGate(t));
    // Yellow moss (red a little ahead of green) closes the band's gate though the green-rock gate is only part open.
    const yellow = [0.42, 0.36, 0.07] as const;
    expect(greenRockGate(yellow)).toBeLessThan(0.9);
    expect(rockMidMossGate(yellow)).toBe(1);
    // Orange rock stays rock for both.
    expect(rockMidMossGate([0.6, 0.3, 0.1])).toBe(0);
    // Moving the gate up changes nothing: it reads sectTexel and no colour, and nothing in the class writes sectTexel.
    const gate = a.slice(order[0], order[3]);
    expect(gate).not.toContain("diffuseColor");
    expect(a).not.toMatch(/\bsectTexel\s*[-+*/]?=[^=]/);
  });

  it("follows the baked texel's size: none where the bake still holds the band, all of it where the texel is coarse", () => {
    expect(m.texelM).toEqual([0.1, 0.3]);
    // The band's finest size is ROCK_SCAN.bandM[0] (0.12 m): a texel under that holds it; a texel of a third of a metre does not.
    expect(m.texelM[0]).toBeLessThanOrEqual(ROCK_SCAN.bandM[0]);
    expect(m.texelM[1]).toBeGreaterThan(2 * ROCK_SCAN.bandM[0]);
    expect(rockMidTexel(0.07)).toBe(0); // the abode's cliff at 14 texels a metre
    expect(rockMidTexel(0.1)).toBe(0);
    expect(rockMidTexel(0.2)).toBeCloseTo(0.5, 12);
    expect(rockMidTexel(0.33)).toBe(1); // range rock at 3 texels a metre
    expect(rockMidTexel(1)).toBe(1);
    // The shader measures it from derivatives of the world position and of the atlas coordinate in texels, before
    // the weight, and only where the material has a map (the far set and the stand-ins have none, and no band).
    const at = ["#ifdef USE_MAP", "vec2 sectTu = vMapUv * vec2( textureSize( map, 0 ) );", "float sectTm = sqrt(", "#else", "float sectTm = 1.0;", "#endif", "float sectDb ="].map((t) => a.indexOf(t));
    for (const i of at) expect(i).toBeGreaterThan(0);
    for (let i = 1; i < at.length; i++) expect(at[i]).toBeGreaterThan(at[i - 1]);
    expect(/float sectDb = [^;]*;/.exec(a)![0]).toContain(`* smoothstep( ${glslFloat(m.texelM[0])}, ${glslFloat(m.texelM[1])}, sectTm ) *`);
    expect(a).toContain("dot( dFdx( vSectWorld ), dFdx( vSectWorld ) ) + dot( dFdy( vSectWorld ), dFdy( vSectWorld ) )");
    expect(a).toContain("max( dot( dFdx( sectTu ), dFdx( sectTu ) ) + dot( dFdy( sectTu ), dFdy( sectTu ) ), 1e-12 )");
  });

  it("is weaker on pale lit faces, where the same stops read as blotches", () => {
    expect(m.pale).toEqual({ lo: 0.35, hi: 0.8, keep: 0.6 });
    expect(rockMidLum(0.3)).toBe(1);
    expect(rockMidLum(m.pale.lo)).toBe(1);
    expect(rockMidLum(m.pale.hi)).toBeCloseTo(m.pale.keep, 12);
    expect(rockMidLum(2)).toBeCloseTo(m.pale.keep, 12);
    expect(rockMidLum(0.01)).toBeCloseTo(m.darkFloor, 12);
    // Never above 1, and falling from the lit middle to the pale end.
    let prev = Infinity;
    for (let lum = m.pale.lo; lum <= 1; lum += 0.05) {
      expect(rockMidLum(lum)).toBeLessThanOrEqual(prev);
      prev = rockMidLum(lum);
    }
    expect(/float sectDb = [^;]*;/.exec(a)![0]).toContain(`* mix( 1.0, ${glslFloat(m.pale.keep)}, smoothstep( ${glslFloat(m.pale.lo)}, ${glslFloat(m.pale.hi)}, sectDl ) )`);
  });

  it("comes and goes in patches: lo to hi with one smooth field, (lo + hi) / 2 = 0.875 on average", () => {
    const pt = m.patch;
    expect(pt).toEqual({ scaleM: 9, lo: 0.45, hi: 1.3 });
    expect(pt.lo).toBeGreaterThan(0);
    expect(pt.lo).toBeLessThan(1);
    expect(pt.hi).toBeGreaterThan(1);
    expect(rockMidPatch(0)).toBe(pt.lo);
    expect(rockMidPatch(1)).toBeCloseTo(pt.hi, 12);
    let prev = -Infinity;
    for (let f = 0; f <= 1; f += 0.05) {
      expect(rockMidPatch(f)).toBeGreaterThan(prev);
      prev = rockMidPatch(f);
    }
    // Over a uniform field the factor averages (lo + hi) / 2.
    const n = 1000;
    let s = 0;
    for (let i = 0; i < n; i++) s += rockMidPatch((i + 0.5) / n);
    expect(s / n).toBeCloseTo(0.875, 9);
    expect((pt.lo + pt.hi) / 2).toBeCloseTo(0.875, 12);
    // And over the ground noise's B as the page builds it (ranked to uniform).
    const { size, offset, cells } = DETAIL_NOISE.ground;
    const tex = groundNoise(size, { offset, cells });
    let sb = 0;
    for (let k = 0; k < size * size; k++) sb += rockMidPatch(tex[k * 4 + 2] / 255);
    expect(sb / (size * size)).toBeCloseTo(0.875, 2);
    // The mirror: the band times the factor; left out, a factor of 1; the fine layer as before.
    expect(Math.log2(rockDetailFactor(0.5, 0.8, 200, 0.5, { patch: 0 }))).toBeCloseTo(0.3 * m.gain * pt.lo, 9);
    expect(Math.log2(rockDetailFactor(0.5, 0.8, 200, 0.5, { patch: 1 }))).toBeCloseTo(0.3 * m.gain * pt.hi, 9);
    expect(Math.log2(rockDetailFactor(0.5, 0.8, 200, 0.5, { patch: 0.5 }))).toBeCloseTo(0.3 * m.gain * 0.875, 9);
    expect(rockDetailFactor(0.8, 0.5, 10, 0.5, { patch: 0 })).toBeCloseTo(detailFactor("rock", 0.8, 10, 0.5), 12);
    expect(rockDetailFactor(0.7, 0.9, 30, 0.5, { farSet: true, patch: 1 })).toBeCloseTo(detailFactor("rock", 0.7, 30, 0.5), 12);
  });

  it("GLSL: the patches read B from the two upright sides and from above, blended with the band's own weights", () => {
    const s = glslFloat(1 / (m.patch.scaleM * DETAIL_NOISE.ground.cells));
    expect(count(g, "float sectRockPatch( vec3 p, bool on )")).toBe(1);
    const start = g.indexOf("float sectRockPatch(");
    const body = g.slice(start, g.indexOf("\n}\n", start));
    expect(body).toContain("vec3 n = cross( dFdx( p ), dFdy( p ) );");
    // The bake's exponent, as the band's own blend (wm in sectRockDetail): the weathering's fourth power of the normal.
    expect(ROCK_SCAN.sharp).toBe(4);
    expect(body).toContain(`vec3 k = pow( abs( n ), vec3( ${glslFloat(ROCK_SCAN.sharp)} ) ) + 1e-4;`);
    expect(body).toContain("k /= k.x + k.y + k.z;");
    expect(count(body, "textureLod( tSectGroundNoise")).toBe(3);
    for (const [view, weight] of [
      ["p.zy", "k.x"],
      ["p.xz", "k.y"],
      ["p.xy", "k.z"],
    ]) {
      const at = body.indexOf(`textureLod( tSectGroundNoise, ${view} * ${s} + `);
      expect(at, view).toBeGreaterThan(0);
      expect(body.slice(at, body.indexOf("\n", at)), view).toContain(`, 0.0 ).b * ${weight}`);
    }
    // Three different offsets, so the views do not repeat one another.
    const offs = [...body.matchAll(/\+ vec2\( ([\d.]+), ([\d.]+) \), 0\.0 \)/g)].map((x) => `${x[1]},${x[2]}`);
    expect(new Set(offs).size).toBe(3);
    expect(body).toContain(`return mix( ${glslFloat(m.patch.lo)}, ${glslFloat(m.patch.hi)}, f );`);
    // Called once, with the band's switch, on rock only. No new texture: rock already declares the ground noise.
    expect(count(a, "sectRockPatch(")).toBe(1);
    expect(/float sectDb = [^;]*;/.exec(a)![0]).toContain("* sectRockPatch( vSectWorld, sectDm != 0.0 );");
    expect(count(g, "uniform sampler2D tSectGroundNoise;")).toBe(1);
    for (const kind of ["ground", "paving", "tiles"] as const) {
      expect(detailGlsl(kind)).not.toContain("sectRockPatch");
      expect(detailApplyGlsl(kind)).not.toContain("sectDb");
    }
  });

  it("changes the rock program's key with the band's floor and patches (they are compiled in)", () => {
    const base = detailProgramKey("rock");
    for (const rockMid of [
      { ...m, darkFloor: 0.7 },
      { ...m, patch: { ...m.patch, scaleM: 12 } },
      { ...m, patch: { ...m.patch, lo: 0.3 } },
      { ...m, patch: { ...m.patch, hi: 1.5 } },
    ]) {
      expect(detailProgramKey("rock", { ...DETAIL_LOOK, rockMid })).not.toBe(base);
    }
  });
});

describe("paving stains (by the slab)", () => {
  const pv = DETAIL_LOOK.paving;
  const g = detailGlsl("paving");

  it("reads the stain field at the slab's middle, so a stain ends at a joint", () => {
    const cells = DETAIL_NOISE.ground.cells;
    expect(g).toContain(
      `textureLod( tSectGroundNoise, ( id + 0.5 ) * vec2( ${glslFloat(pv.slabM[0] / (pv.stain.scaleM * cells))}, ${glslFloat(pv.slabM[1] / (pv.stain.scaleM * cells))} ) + vec2( 0.77, 0.31 ), 0.0 ).a`,
    );
    // Not read at the pixel's own place any more (that drew blobs across the joints).
    expect(g).not.toMatch(/float stain = [^;]*p\.xz/);
  });

  it("is mild: a stained slab is at most a tenth darker in any channel, and warmer", () => {
    const k = pv.stain.tint.map((c) => c * (1 - pv.stain.dark));
    for (const c of k) {
      expect(c).toBeLessThanOrEqual(1);
      expect(c).toBeGreaterThanOrEqual(0.88);
    }
    expect(k[0]).toBeGreaterThan(k[2]);
    expect(pv.stain.lo).toBeLessThan(pv.stain.hi);
  });
});

describe("rock beds (level bedding on steep faces)", () => {
  const b = DETAIL_LOOK.rockBeds;
  // The two slow waves that bend the height (sectRockBeds): sin( t * 1.37 ) * 0.45 + sin( t * 2.71 + 1.3 ) * 0.22.
  const waves = [
    [1.37, 0.45, 0],
    [2.71, 0.22, 1.3],
  ] as const;
  /** Mirror of the bend: the height in beds (after the warps) to the bent height. */
  const bend = (t: number) => t + b.uneven * waves.reduce((s, [k, a, ph]) => s + Math.sin(t * k + ph) * a, 0);
  /** Mirror of the tone: tones(i) is bed i's noise (0..1), t the bent height, fw a pixel's height in beds. */
  const toneAt = (tones: (i: number) => number, t: number, fw: number) => {
    const i = Math.floor(t);
    const f = t - i;
    return tones(i) + (tones(i + 1) - tones(i)) * smooth(1 - b.soft - fw, 1, f) - 0.5;
  };
  /** Mirror of sectRockBeds' result for a tone (-0.5..0.5), where a pixel is fw beds tall. */
  const beds = (tone: number, fw: number) => 2 ** (tone * b.gain * (1 - smooth(0.12, 0.4, fw)));
  const lo = 2 ** (-b.gain / 2);
  const hi = 2 ** (b.gain / 2);
  /** Some bed tones, the same every run. */
  const tones = (i: number) => sectHash3(i * 7.31, 3)[0];

  it("is the GLSL the mirror follows, defined once on rock after sectNoise3", () => {
    const g = detailGlsl("rock");
    expect(count(g, "float sectRockBeds( vec3 p, float fy )")).toBe(1);
    expect(g.indexOf("float sectNoise3( vec3 x )")).toBeLessThan(g.indexOf("float sectRockBeds("));
    expect(g).toContain(`float t = ( p.y + warp * ${glslFloat(2 * b.warpM)} + ripple * ${glslFloat(2 * b.rippleM)} ) * ${glslFloat(1 / b.bedM)};`);
    expect(g).toContain(`t += ${glslFloat(b.uneven)} * ( sin( t * 1.37 ) * 0.45 + sin( t * 2.71 + 1.3 ) * 0.22 );`);
    // Each bed's tone, and the next bed's: the same read one bed up.
    const toneA = /float toneA = sectNoise3\( ([^;]*) \);/.exec(g)!;
    const toneB = /float toneB = sectNoise3\( ([^;]*) \);/.exec(g)!;
    expect(toneA && toneB).toBeTruthy();
    expect(toneB[1]).toBe(toneA[1].replace("i * 7.31", "( i + 1.0 ) * 7.31"));
    expect(g).toContain(`float tone = mix( toneA, toneB, smoothstep( 1.0 - ${glslFloat(b.soft)} - fw, 1.0, f ) ) - 0.5;`);
    expect(g).toContain(`float fw = fy * ${glslFloat(1 / b.bedM)};`);
    expect(g).toContain(`return exp2( tone * ${glslFloat(b.gain)} * ( 1.0 - smoothstep( 0.12, 0.4, fw ) ) );`);
    // No line where two beds meet: even a faint one showed as hairlines across a cliff.
    const body = g.slice(g.indexOf("float sectRockBeds("), g.indexOf("\n}", g.indexOf("float sectRockBeds(")));
    expect(body).not.toMatch(/\bline\b|\bseen\b|\blw\b/);
    expect(Object.keys(b)).not.toContain("lineDark");
    // Still one read of the noise texture's top level besides the middle band's three (sectRockPatch).
    expect(count(g, "textureLod( tSectGroundNoise")).toBe(4);
    expect(count(g.slice(0, g.indexOf("float sectRockPatch(")), "textureLod( tSectGroundNoise")).toBe(1);
    expect(detailGlsl("ground")).not.toContain("sectRockBeds");
    expect(detailGlsl("paving")).not.toContain("sectRockBeds");
  });

  it("never folds back: the bed height only rises with the height", () => {
    // The bend's slope is at least 1 - uneven x (the waves' slopes).
    const steepest = waves.reduce((s, [k, a]) => s + k * a, 0);
    expect(b.uneven * steepest).toBeLessThan(1);
    let prev = bend(-60);
    for (let t = -60 + 1e-3; t <= 60; t += 1e-3) {
      const v = bend(t);
      expect(v).toBeGreaterThan(prev);
      prev = v;
    }
    // Nor do the warps: value noise (eased) changes by at most 1.5 per lattice cell, so up the face the
    // large warp moves by at most 1.5 x (ws x 0.4) x 2 warpM per metre and the ripple by 1.5 x 0.11 x 2 rippleM.
    const g = detailGlsl("rock");
    const ws = 1 / b.warpScaleM;
    expect(g).toContain(`p * vec3( ${glslFloat(ws)}, ${glslFloat(ws * 0.4)}, ${glslFloat(ws)} )`);
    expect(g).toContain("float ripple = sectNoise3( p * vec3( 0.23, 0.11, 0.23 )");
    expect(1.5 * ws * 0.4 * 2 * b.warpM + 1.5 * 0.11 * 2 * b.rippleM).toBeLessThan(1);
  });

  it("has beds of different thickness, bedM on average", () => {
    // Where the bent height crosses each whole bed.
    const starts: number[] = [];
    let last = Math.floor(bend(-40));
    for (let t = -40; t <= 40; t += 1e-4) {
      const i = Math.floor(bend(t));
      if (i !== last) starts.push(t);
      last = i;
    }
    const thick = starts.slice(1).map((t, k) => t - starts[k]);
    expect(thick.length).toBeGreaterThan(60);
    expect(Math.min(...thick)).toBeGreaterThan(0);
    expect(Math.max(...thick) / Math.min(...thick)).toBeGreaterThan(1.3);
    expect((starts[starts.length - 1] - starts[0]) / thick.length).toBeCloseTo(1, 1);
  });

  it("eases each bed's tone into the next one's: no step at a boundary", () => {
    // The ease has room before the tone fades (smoothstep( 0.12, 0.4, fw )).
    expect(b.soft).toBeGreaterThan(0);
    expect(1 - b.soft - 0.4).toBeGreaterThan(0);
    for (const fw of [0, 0.05, 0.2, 0.39]) {
      for (let i = -20; i < 20; i++) {
        const below = toneAt(tones, i - 1e-9, fw);
        const at = toneAt(tones, i, fw);
        expect(Math.abs(at - below), `${i} ${fw}`).toBeLessThan(1e-6);
        // At the bottom of its bed the tone is the bed's own; up to 1 - soft - fw it stays so.
        expect(at).toBeCloseTo(tones(i) - 0.5, 12);
        expect(toneAt(tones, i + (1 - b.soft - fw) * 0.999, fw)).toBeCloseTo(tones(i) - 0.5, 12);
      }
    }
    // Hard steps, as at first, would jump by the two tones' difference.
    expect(Math.max(...Array.from({ length: 40 }, (_, k) => Math.abs(tones(k - 19) - tones(k - 20))))).toBeGreaterThan(0.2);
  });

  it("stays within exp2(+-gain / 2)", () => {
    for (let tone = -0.5; tone <= 0.5; tone += 0.125) {
      for (const fw of [0, 0.01, 0.1, 0.3, 0.5, 1, 3]) {
        const k = beds(tone, fw);
        expect(k).toBeGreaterThanOrEqual(lo - 1e-12);
        expect(k).toBeLessThanOrEqual(hi + 1e-12);
      }
    }
    expect(beds(0.5, 0)).toBeCloseTo(hi, 12);
    expect(beds(-0.5, 0)).toBeCloseTo(lo, 12);
    // A gentle tone: under a fifth of a stop either way.
    expect(b.gain / 2).toBeLessThan(0.2);
  });

  it("has no tone once a bed is under 2.5 pixels", () => {
    // fw 0.4: a bed 2.5 pixels tall.
    for (const fw of [0.4, 1, 2, 5]) {
      for (let tone = -0.5; tone <= 0.5; tone += 0.25) expect(beds(tone, fw)).toBe(1);
    }
    // And all of it while a bed is 8 pixels or more.
    expect(beds(0.5, 0.12)).toBeCloseTo(hi, 12);
  });

  it("applies on steep rock only, less where it is mossy, never on the far set", () => {
    const a = detailApplyGlsl("rock");
    expect(count(a, "sectRockBeds(")).toBe(1);
    const open = a.indexOf("#ifndef SECT_FAR_SET");
    const close = a.indexOf("#endif", open);
    expect(open).toBeGreaterThan(0);
    const block = a.slice(open, close);
    expect(block).toContain("diffuseColor.rgb *= mix( 1.0, sectRockBeds( vSectWorld, fwidth( vSectWorld.y ) ), sectBk );");
    expect(block).toContain(
      `float sectBk = ( 1.0 - smoothstep( ${glslFloat(b.steep[0])}, ${glslFloat(b.steep[1])}, abs( sectBn.y ) ) ) * ( 1.0 - sectGr ) * uSectRockFar;`,
    );
    expect(block).toContain("cross( dFdx( vSectWorld ), dFdy( vSectWorld ) )");
    // No other preprocessor branch inside it, and no runtime branch (it takes derivatives).
    expect(block.slice(1)).not.toContain("#if");
    expect(block).not.toMatch(/\bif\b/);
    // The far set's own block has none.
    const far = a.slice(a.indexOf("#ifdef SECT_FAR_SET"));
    expect(far.slice(0, far.indexOf("#endif"))).not.toContain("sectRockBeds");
    // After the mossy-rock gate it scales by.
    expect(a.indexOf("float sectGr =")).toBeLessThan(open);
    expect(detailApplyGlsl("ground")).not.toContain("sectRockBeds");
    expect(detailApplyGlsl("paving")).not.toContain("sectRockBeds");
    // Its weight: 1 on a wall, 0 on level rock, none on moss.
    const weight = (ny: number, gr: number) => (1 - smooth(b.steep[0], b.steep[1], Math.abs(ny))) * (1 - gr);
    expect(b.steep[0]).toBeLessThan(b.steep[1]);
    expect(weight(0, 0)).toBe(1);
    expect(weight(1, 0)).toBe(0);
    expect(weight(-0.2, 1)).toBe(0);
  });

  it("changes the rock program's key with the beds", () => {
    const look = { ...DETAIL_LOOK, rockBeds: { ...DETAIL_LOOK.rockBeds, gain: 0.3 } };
    expect(detailProgramKey("rock", look)).not.toBe(detailProgramKey("rock"));
    const soft = { ...DETAIL_LOOK, rockBeds: { ...DETAIL_LOOK.rockBeds, soft: 0.1 } };
    expect(detailProgramKey("rock", soft)).not.toBe(detailProgramKey("rock"));
  });
});

describe("weathering (baked surfaces with no detail class)", () => {
  const w = DETAIL_LOOK.weather;
  const g = weatherGlsl();
  /**
   * Mirror of the streak weight: s the stretched field (B), ay the coarse field's A, ny the face
   * normal's y, lum the colour's luminance, sh `show`, dist metres away.
   */
  const streakWeight = (s: number, ay: number, ny: number, lum: number, sh: number, dist: number) =>
    smooth(w.streak.lo, w.streak.hi, s) *
    smooth(0.3, 0.7, ay) *
    (1 - smooth(0.35, 0.7, Math.abs(ny))) *
    sh *
    (1 + (w.streak.pale - 1) * smooth(0.45, 0.8, lum)) *
    (1 - smooth(w.streak.fadeNear, w.streak.fadeFar, dist));

  it("declares its texture and switch, and defines nothing a detail class defines", () => {
    expect(count(g, "uniform sampler2D tSectGroundNoise;")).toBe(1);
    expect(count(g, "uniform float uSectWeather;")).toBe(1);
    expect(count(g, "uniform ")).toBe(2);
    expect(count(g, "float sectWnoise( vec3 x )")).toBe(1);
    expect(count(g, "vec3 sectWeather( vec3 col, vec3 p, float dist )")).toBe(1);
    const defined = (src: string) => [...src.matchAll(/^(?:float|vec[234]) (\w+)\(/gm)].map((m) => m[1]);
    expect(defined(g)).toEqual(["sectWnoise", "sectWeather"]);
    // The texture is the one name it shares with the detail classes (a material never has both).
    for (const kind of ["rock", "ground", "paving", "tiles"] as const) {
      for (const name of defined(g)) expect(detailGlsl(kind), `${kind} ${name}`).not.toContain(name);
    }
  });

  it("reads the noise's top level with no branch, and takes its derivatives at the top", () => {
    // Six reads of the smooth fields (the coarse one from three sides, the fine one from one, the
    // streaks from the two upright sides) and one in sectWnoise (the grain).
    expect(count(g, "textureLod( tSectGroundNoise")).toBe(7);
    expect(count(g, "textureLod( tSectGroundNoise, q * ")).toBe(1);
    expect(count(g, "sectWnoise( p")).toBe(1);
    expect(g).not.toContain("texture2D");
    expect(g).not.toMatch(/\bif\b/);
    // The grain's lattice is the far rock layer's sectNoise3's.
    expect(g).toContain(`vec2( ${glslFloat(DETAIL_NOISE.ground.offset[0])}, ${glslFloat(DETAIL_NOISE.ground.offset[1])} ) * i.y`);
    const body = g.slice(g.indexOf("vec3 sectWeather("));
    expect(body.indexOf("vec3 n = cross( dFdx( p ), dFdy( p ) );")).toBeGreaterThan(0);
    expect(count(g, "dFdx(")).toBe(1);
    expect(count(g, "dFdy(")).toBe(1);
    expect(g).not.toContain("fwidth");
  });

  it("reads the patches from above on level faces and from the side on steep ones", () => {
    expect(g).toContain("float wall = 1.0 - smoothstep( 0.35, 0.7, abs( n.y ) );");
    // The three views weighted by the way the face looks: the fourth power of the normal, summing to 1.
    expect(g).toContain("vec3 k = n * n;");
    expect(g).toContain("k *= k;");
    expect(g).toContain("k /= k.x + k.y + k.z;");
    // The coarse field's two channels (tone, and where streaks run): from above, and from the two upright sides.
    expect(count(g, ", 0.0 ).ba * k.")).toBe(3);
    for (const [view, weight] of [
      ["p.xz", "k.y"],
      ["p.zy", "k.x"],
      ["p.xy", "k.z"],
    ]) {
      const at = g.indexOf(`textureLod( tSectGroundNoise, ${view} * `);
      expect(at, view).toBeGreaterThan(0);
      expect(g.slice(at, g.indexOf("\n", at)), view).toContain(`.ba * ${weight}`);
    }
    // The fine one's A from the one view the face looks along most.
    expect(g).toContain("vec2 q = k.y > max( k.x, k.z ) ? p.xz : k.x > k.z ? p.zy : p.xy;");
    expect(g).toMatch(/float b = textureLod\( tSectGroundNoise, q \* [^;]*\)\.a;/);
    // The streaks from the two upright sides only, by their share of the two.
    expect(g).toContain("* k.x + textureLod( tSectGroundNoise, p.xy * sk + vec2( 0.67, 0.53 ), 0.0 ).b * k.z ) / max( k.x + k.z, 1e-4 );");
  });

  it("weights the three views so that they sum to 1, and a wall between two axes takes both sides", () => {
    const weights = (n: [number, number, number]) => {
      const k = n.map((x) => x * x * x * x);
      const sum = k[0] + k[1] + k[2];
      return k.map((x) => x / sum);
    };
    for (const n of [
      [1, 0, 0],
      [0, 1, 0],
      [0, 0, 1],
      [Math.SQRT1_2, 0, Math.SQRT1_2],
      [0.6, 0.3, 0.74],
    ] as [number, number, number][]) {
      const k = weights(n);
      expect(k[0] + k[1] + k[2]).toBeCloseTo(1, 12);
      for (const x of k) expect(x).toBeGreaterThanOrEqual(0);
    }
    // A wall facing one axis reads one side. One facing between two reads both equally, so there is
    // no side along which the pattern stands still.
    expect(weights([1, 0, 0])).toEqual([1, 0, 0]);
    const diag = weights([Math.SQRT1_2, 0, Math.SQRT1_2]);
    expect(diag[0]).toBeCloseTo(0.5, 12);
    expect(diag[2]).toBeCloseTo(0.5, 12);
    expect(diag[1]).toBe(0);
  });

  it("uses the look's sizes, amounts and fades", () => {
    const st = w.streak;
    const cells = DETAIL_NOISE.ground.cells;
    for (const s of [
      `p.xz * ${glslFloat(1 / (w.patchM[0] * cells))}`,
      `p.zy * ${glslFloat(1 / (w.patchM[0] * cells))}`,
      `p.xy * ${glslFloat(1 / (w.patchM[0] * cells))}`,
      `q * ${glslFloat(1 / (w.patchM[1] * cells))}`,
      // The coarse octave to fadeFar, the fine one gone by fineFade[1] (before it goes under a pixel).
      `( a.x - 0.5 ) * 1.3 * ( 1.0 - smoothstep( ${glslFloat(w.fadeNear)}, ${glslFloat(w.fadeFar)}, dist ) )`,
      `( b - 0.5 ) * 0.7 * ( 1.0 - smoothstep( ${glslFloat(w.fineFade[0])}, ${glslFloat(w.fineFade[1])}, dist ) )`,
      `* ${glslFloat(w.patch)} * show`,
      // The streaks: the same field stretched down the wall.
      `vec2 sk = vec2( ${glslFloat(1 / (st.widthM * cells))}, ${glslFloat(1 / (st.lengthM * cells))} );`,
      "textureLod( tSectGroundNoise, p.zy * sk + vec2( 0.31, 0.07 ), 0.0 ).b * k.x",
      `float streak = smoothstep( ${glslFloat(st.lo)}, ${glslFloat(st.hi)}, s ) * smoothstep( 0.3, 0.7, a.y ) * wall * show`,
      `* mix( 1.0, ${glslFloat(st.pale)}, smoothstep( 0.45, 0.8, lum ) ) * ( 1.0 - smoothstep( ${glslFloat(st.fadeNear)}, ${glslFloat(st.fadeFar)}, dist ) );`,
      `col = mix( col, col * vec3( ${glslFloat(st.tint[0])}, ${glslFloat(st.tint[1])}, ${glslFloat(st.tint[2])} ), streak );`,
      glslFloat(1 / w.grain.sizeM),
      `smoothstep( ${glslFloat(w.grain.fadeNear)}, ${glslFloat(w.grain.fadeFar)}, dist )`,
      `g * ${glslFloat(2 * w.grain.amount)} * show`,
      `mix( 1.0, ${glslFloat(w.paint)}, smoothstep( 0.35, 0.7, sat ) ) * mix( ${glslFloat(w.darkFloor)}, 1.0, smoothstep( 0.02, 0.2, lum ) ) * uSectWeather`,
    ]) {
      expect(g, s).toContain(s);
    }
    expect(st.lo).toBeLessThan(st.hi);
    expect(st.pale).toBeGreaterThanOrEqual(0);
    expect(st.pale).toBeLessThanOrEqual(1);
    for (const [near, far] of [[w.fadeNear, w.fadeFar], [w.fineFade[0], w.fineFade[1]], [st.fadeNear, st.fadeFar], [w.grain.fadeNear, w.grain.fadeFar]]) expect(near).toBeLessThan(far);
    // The finer a pattern, the sooner it is gone.
    expect(w.grain.fadeFar).toBeLessThan(st.fadeFar);
    expect(st.fadeFar).toBeLessThanOrEqual(w.fineFade[1]);
    expect(w.fineFade[1]).toBeLessThan(w.fadeFar);
  });

  it("moves the tone within the look's bounds, most on pale stone, less on paint and in deep shade", () => {
    type Rgb = readonly [number, number, number];
    const lum = (c: Rgb) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
    // Mirror of `show`.
    const show = (c: Rgb) => {
      const mx = Math.max(...c);
      const sat = (mx - Math.min(...c)) / Math.max(mx, 1e-4);
      return (1 + (w.paint - 1) * smooth(0.35, 0.7, sat)) * (w.darkFloor + (1 - w.darkFloor) * smooth(0.02, 0.2, lum(c)));
    };
    expect(show([0.6, 0.58, 0.54])).toBe(1);
    expect(show([0.8, 0.25, 0.1])).toBeCloseTo(w.paint, 12);
    expect(show([0.004, 0.004, 0.004])).toBeCloseTo(w.darkFloor, 12);
    // Mirror of the factor on one channel with tint k, up close on a wall of luminance 0.3: field reads
    // a (coarse B), ay (coarse A), b (fine A), s (streak B) and the grain's gn, all 0..1.
    const factor = (a: number, ay: number, b: number, s: number, gn: number, k: number, sh: number) => {
      const patch = 1 + ((a - 0.5) * 1.3 + (b - 0.5) * 0.7) * w.patch * sh;
      return patch * (1 + (k - 1) * streakWeight(s, ay, 0, 0.3, sh, 0)) * (1 + (gn - 0.5) * 2 * w.grain.amount * sh);
    };
    const tint = Math.min(...w.streak.tint);
    const reads = [0, 0.5, 1];
    for (const a of reads) {
      for (const ay of reads) {
        for (const b of reads) {
          for (const s of reads) {
            for (const gn of reads) {
              for (const k of w.streak.tint) {
                const f = factor(a, ay, b, s, gn, k, 1);
                expect(f).toBeGreaterThanOrEqual((1 - w.patch) * tint * (1 - w.grain.amount) - 1e-12);
                expect(f).toBeLessThanOrEqual((1 + w.patch) * (1 + w.grain.amount) + 1e-12);
              }
            }
          }
        }
      }
    }
    expect(factor(0.5, 1, 0.5, 0, 0.5, tint, 1)).toBe(1);
    expect(factor(0, 1, 0, 1, 0, tint, 0)).toBe(1);
  });

  it("streaks: a weight within 0..1, at most `pale` of itself on near-white stone, none on level faces", () => {
    const st = w.streak;
    // Up close, every part at its most.
    expect(streakWeight(1, 1, 0, 0.3, 1, 0)).toBe(1);
    const reads = [0, 0.25, 0.5, 0.75, 1];
    for (const s of reads) {
      for (const ay of reads) {
        for (const ny of [0, 0.3, 0.5, 0.7, 1, -0.4]) {
          for (const sh of [0, 0.5, 1]) {
            for (const dist of [0, st.fadeNear, (st.fadeNear + st.fadeFar) / 2, st.fadeFar]) {
              const k = streakWeight(s, ay, ny, 0.3, sh, dist);
              expect(k).toBeGreaterThanOrEqual(0);
              expect(k).toBeLessThanOrEqual(1);
              // Near-white stone (luminance 0.8 and up): pale of what a mid-grey wall gets.
              const white = streakWeight(s, ay, ny, 0.85, sh, dist);
              expect(white).toBeCloseTo(st.pale * k, 12);
              expect(white).toBeLessThanOrEqual(st.pale);
              // A level face (|n.y| from 0.7) has none.
              if (Math.abs(ny) >= 0.7) expect(k).toBe(0);
            }
          }
        }
      }
    }
    // Sparse: below lo nothing, gone by fadeFar.
    expect(streakWeight(st.lo, 1, 0, 0.3, 1, 0)).toBe(0);
    expect(streakWeight(1, 1, 0, 0.3, 1, st.fadeFar)).toBe(0);
    // Where the coarse field's A is low, none either.
    expect(streakWeight(1, 0.3, 0, 0.3, 1, 0)).toBe(0);
  });

  it("puts it on diffuseColor after the grade, never on a glow surface", () => {
    const a = weatherApplyGlsl();
    expect(a.split("\n")).toHaveLength(1);
    expect(a).toMatch(/^ {2}if \( max\( diffuse\.r, max\( diffuse\.g, diffuse\.b \) \) <= 1\.001 \) diffuseColor\.rgb = sectWeather\( /);
    expect(a).toContain("sectWeather( diffuseColor.rgb, vSectWorld, length( vSectWorld - cameraPosition ) )");
  });
});
