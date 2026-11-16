import { describe, expect, it } from "vitest";
import { fogDefines, fogLibrary, hexToLinear, lookFrameGradeGlsl, LOOK_UNIFORM_GLSL, SCREEN_GRADE_GLSL, SCREEN_GRADE_PARS, type FogConstants } from "./glsl";
import { gradeGlsl, lookFogConstants, SECT_LOOK, unitTint } from "./look";
import { createLookData, gradeLookDefines, LOOK_SLOT, LOOK_VEC4S, packFog, packFrame, packGrade } from "./look-gpu";
import { FRAME_LOOK, frameCurve, frameGradeLinear, LOOKS, redWeight, withLevers, type FrameGrade } from "./looks";
import type { SectMeta, Vec3 } from "./types";

const META = {
  fog: { color: "#c8ada0", density: 0.00033, baseY: 0, falloff: 220 },
  sky: { horizonSun: "#f6c48a" },
  sun: { direction: [-0.94, 0.12, 0.31] },
  cloudSea: { fogTopY: -40, color: "#f0d2b4" },
} as unknown as SectMeta;

const FOG: FogConstants = lookFogConstants(META);

function slot(d: Float32Array, i: number): number[] {
  return Array.from(d.subarray(i * 4, i * 4 + 4));
}

/** The frame grade worked out from a packed array the way lookFrameGradeGlsl reads it. */
function gradeFromPacked(c0: Vec3, d: Float32Array, base: number): Vec3 {
  const [amount, exposure, contrast, pivot] = slot(d, base);
  if (amount <= 0) return c0;
  const bal = slot(d, base + 1);
  const sh = slot(d, base + 2);
  const hi = slot(d, base + 3);
  const lift = slot(d, base + 4);
  const sp = slot(d, base + 5);
  const gw = slot(d, base + 6);
  const ss = (a: number, b: number, x: number) => {
    const t = Math.min(Math.max((x - a) / (b - a), 0), 1);
    return t * t * (3 - 2 * t);
  };
  const luma = (c: Vec3) => c[0] * 0.2126 + c[1] * 0.7152 + c[2] * 0.0722;
  const x0 = c0.map((v) => Math.max(v, 0)) as Vec3;
  const glow = ss(gw[0], gw[1], Math.max(...x0));
  let c = x0.map((v, i) => v * exposure * bal[i]) as Vec3;
  c = c.map((x) => (x < 1 ? Math.pow(frameCurve(Math.pow(x, 1 / 2.2), pivot, contrast), 2.2) : x)) as Vec3;
  const v2 = Math.pow(Math.min(luma(c), 1), 1 / 2.2);
  const ws = 1 - ss(sp[0] - sp[1], sp[0] + sp[1], v2);
  c = c.map((x, i) => x * (1 + (sh[i] - 1) * sh[3] * ws) * (1 + (hi[i] - 1) * hi[3] * (1 - ws))) as Vec3;
  c = c.map((x, i) => x + lift[i] * lift[3] * Math.pow(1 - v2, 4)) as Vec3;
  const sat = bal[3] + (sp[2] - bal[3]) * redWeight(c);
  const lc = luma(c);
  c = c.map((x) => Math.max(lc + (x - lc) * sat, 0)) as Vec3;
  const k = Math.min(amount, 1);
  const graded = c.map((x, i) => x0[i] + (x - x0[i]) * k) as Vec3;
  return graded.map((x, i) => x + (x0[i] * (1 + (sp[3] - 1) * k) - x) * glow) as Vec3;
}

describe("look on the GPU: the shared array", () => {
  it("starts with every switch off and the frame grade at amount 0", () => {
    const d = createLookData();
    expect(d.length).toBe(LOOK_VEC4S * 4);
    expect(d[LOOK_SLOT.fog * 4 + 3]).toBe(0);
    expect(d[(LOOK_SLOT.grade + 2) * 4 + 3]).toBe(0);
    expect(d[LOOK_SLOT.frame * 4]).toBe(0);
  });

  it("packs the haze behind its switch, and switches it off again", () => {
    const d = createLookData();
    packFog(d, FOG);
    expect(slot(d, 0)[3]).toBe(1);
    expect(slot(d, 0).slice(0, 3)).toEqual(FOG.sunFogColor.map((v) => Math.fround(v)));
    expect(slot(d, 2)[3]).toBeCloseTo(FOG.desaturate, 6);
    expect(slot(d, 4)).toEqual([FOG.hazeClear, FOG.mistDensity, FOG.mistFalloff, FOG.mistStart].map((v) => Math.fround(v)));
    expect(slot(d, 5)[1]).toBeCloseTo(FOG.density, 9);
    packFog(d, null);
    expect(slot(d, 0)[3]).toBe(0);
  });

  it("packs the surfaces' grade with unit tints", () => {
    const d = createLookData();
    const g = SECT_LOOK.grade;
    packGrade(d, g);
    const s = LOOK_SLOT.grade;
    unitTint(g.shadowTint).forEach((v, i) => expect(slot(d, s)[i]).toBeCloseTo(v, 5));
    expect(slot(d, s)[3]).toBeCloseTo(g.splitShadow ?? g.split, 6);
    expect(slot(d, s + 2)).toEqual([g.exposure, g.contrast, g.pivot, 1].map((v) => Math.fround(v)));
    expect(slot(d, s + 3).slice(0, 3)).toEqual([g.saturation, g.greenTame, g.shoulder].map((v) => Math.fround(v)));
    packGrade(d, null);
    expect(slot(d, s + 2)[3]).toBe(0);
  });

  it("packs the frame grade so the shader's reading matches frameGradeLinear", () => {
    const greys: Vec3[] = [
      [0.02, 0.03, 0.05],
      [0.2, 0.18, 0.15],
      [0.6, 0.4, 0.3],
      [0.5, 0.05, 0.04],
      [2.4, 1.6, 0.6],
    ];
    for (const id of ["gold", "moon", "ink", "day"] as const) {
      const g: FrameGrade = withLevers(FRAME_LOOK, LOOKS[id].patch.frame).grade;
      const d = createLookData();
      packFrame(d, g);
      for (const c of greys) {
        const want = frameGradeLinear(c, g);
        const got = gradeFromPacked(c, d, LOOK_SLOT.frame);
        got.forEach((v, i) => expect(v, `${id} ${c}`).toBeCloseTo(want[i], 4));
      }
    }
    // Amount 0 (today's dusk): untouched.
    const d = createLookData();
    packFrame(d, FRAME_LOOK.grade);
    expect(gradeFromPacked([0.3, 0.2, 0.1], d, LOOK_SLOT.frame)).toEqual([0.3, 0.2, 0.1]);
  });

  it("fades the whole grade with its amount, glows too: no jump as the journey leaves today's dusk", () => {
    // One frame past the formation toward the abode the moon's grade is at a tiny amount. Its glow
    // gain (2.6, from 0.85) must not apply in full there: bright marble and lanterns would jump.
    const moon: FrameGrade = withLevers(FRAME_LOOK, LOOKS.moon.patch.frame).grade;
    for (const c of [[2.4, 1.6, 0.6], [0.95, 0.9, 0.85], [0.2, 0.18, 0.15]] as Vec3[]) {
      const g = { ...moon, amount: 1e-4 };
      frameGradeLinear(c, g).forEach((v, i) => expect(v, `${c}`).toBeCloseTo(c[i], 3));
      const d = createLookData();
      packFrame(d, g);
      gradeFromPacked(c, d, LOOK_SLOT.frame).forEach((v, i) => expect(v, `${c}`).toBeCloseTo(c[i], 3));
    }
    // And the shader does what the helper does.
    expect(lookFrameGradeGlsl("x", "u", 0)).toContain("return mix( graded, x0 * mix( 1.0, sp.w, k ), glow );");
  });

  it("takes a slot of its own for the post pass", () => {
    const d = new Float32Array(28);
    packFrame(d, withLevers(FRAME_LOOK, LOOKS.moon.patch.frame).grade, 0);
    expect(d[0]).toBe(1);
    const lift = hexToLinear(LOOKS.moon.patch.frame?.["grade.liftColor"] as string);
    lift.forEach((v, i) => expect(d[16 + i]).toBeCloseTo(v, 6));
  });
});

describe("look on the GPU: the GLSL", () => {
  it("the haze's movable constants read the array while its switch is on, else their own numbers", () => {
    const s = fogDefines(FOG);
    expect(s).toContain(LOOK_UNIFORM_GLSL);
    for (const name of ["SECT_FOG_DENSITY", "SECT_SUN_FOG", "SECT_CLOUD_FOG", "SECT_SKY_HAZE", "SECT_EXTINCTION", "SECT_COOL_TINT", "SECT_COOL_MIX", "SECT_DESATURATE", "SECT_AERIAL_DEPTH", "SECT_HAZE_CLEAR", "SECT_MIST_DENSITY", "SECT_MIST_FALLOFF", "SECT_MIST_START"]) {
      expect(s).toMatch(new RegExp(`#define ${name} \\( \\( uSectLook\\[ 0 \\]\\.w > 0\\.5 \\) \\? `));
    }
    expect(s).not.toMatch(/NaN|undefined|Infinity/);
    // Declared once even when the grade's GLSL comes first.
    expect(s).toContain("#ifndef SECT_LOOK_UNIFORM");
  });

  it("the surfaces' grade reads the array while its switch is on", () => {
    const s = gradeLookDefines(SECT_LOOK.grade);
    expect(s).toContain("( uSectLook[ 8 ].w > 0.5 )");
    expect(gradeGlsl()).toContain(s);
    for (const name of ["EXPOSURE", "CONTRAST", "PIVOT", "SATURATION", "TAME", "SHOULDER", "SHADOW", "HIGH"]) expect(s).toContain(`#define SECT_GRADE_${name} `);
  });

  it("the frame grade is one function per array, at amount 0 a pass-through", () => {
    const g = lookFrameGradeGlsl("sectFrameGrade", "uFrameGrade", 0);
    expect(g).toContain("vec3 sectFrameGrade( vec3 c0 )");
    expect(g).toContain("if ( a.x <= 0.0 ) return c0;");
    expect(g).toContain("uFrameGrade[ 6 ]");
    expect(g).not.toContain("uFrameGrade[ 7 ]");
    // The Low tier's: in the fog library once, guarded, and the statement that applies it.
    expect(fogLibrary(FOG)).toContain("vec3 sectLookGrade( vec3 c0 )");
    expect(SCREEN_GRADE_PARS).toContain("#ifndef SECT_LOOK_GRADE");
    expect(SCREEN_GRADE_GLSL).toContain("sectLookGrade( gl_FragColor.rgb )");
    expect(lookFrameGradeGlsl("x", "uSectLook", LOOK_SLOT.frame)).toContain(`uSectLook[ ${LOOK_SLOT.frame + 6} ]`);
  });
});
