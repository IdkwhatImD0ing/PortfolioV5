/**
 * The look's run-time numbers as the shaders read them: one array of vec4s, uSectLook (glsl.ts
 * LOOK_UNIFORM_GLSL), shared by every material that fogs or grades (experience/materials.ts
 * SECT_LOOK_GPU), so the journey (journey.ts) can change the haze, the surfaces' grade and the
 * frame grade every frame without building a shader.
 *
 * The haze and the surfaces' grade each have a switch. Off (0, which is also what an array no one
 * filled reads), a shader keeps the numbers it was built with: a material the page never handed
 * the array to still draws as before, and the page without the journey draws exactly as it did.
 * The frame grade is off at amount 0.
 *
 * Pure data and maths (no three.js), so it is testable.
 */
import { glslFloat, hexToLinear, LOOK_SLOT, LOOK_UNIFORM_GLSL, LOOK_VEC4S, type FogConstants } from "./glsl";
import type { SectLook } from "./look";
import type { FrameGrade } from "./looks";
import type { Vec3 } from "./types";

export { LOOK_SLOT, LOOK_VEC4S };

/** A fresh array for uSectLook: every switch off, the frame grade at amount 0. */
export function createLookData(): Float32Array {
  return new Float32Array(LOOK_VEC4S * 4);
}

function put(out: Float32Array, slot: number, a: number, b: number, c: number, d: number): void {
  const i = slot * 4;
  out[i] = a;
  out[i + 1] = b;
  out[i + 2] = c;
  out[i + 3] = d;
}

/** The haze's run-time numbers (null: the switch off, every fogging shader keeps its own). */
export function packFog(out: Float32Array, c: FogConstants | null): void {
  const s = LOOK_SLOT.fog;
  if (!c) {
    out[s * 4 + 3] = 0;
    return;
  }
  put(out, s, c.sunFogColor[0], c.sunFogColor[1], c.sunFogColor[2], 1);
  put(out, s + 1, c.cloudColor[0], c.cloudColor[1], c.cloudColor[2], c.coolMix);
  put(out, s + 2, c.extinction[0], c.extinction[1], c.extinction[2], c.desaturate);
  put(out, s + 3, c.coolTint[0], c.coolTint[1], c.coolTint[2], c.aerialDepth);
  put(out, s + 4, c.hazeClear, c.mistDensity, c.mistFalloff, c.mistStart);
  put(out, s + 5, c.skyHaze, c.density, 0, 0);
}

/** A tint as a linear colour scaled to luminance 1 (look.ts unitTint, without importing look.ts). */
function unit(hex: string): Vec3 {
  const c = hexToLinear(hex);
  const l = Math.max(c[0] * 0.2126 + c[1] * 0.7152 + c[2] * 0.0722, 1e-6);
  return [c[0] / l, c[1] / l, c[2] / l];
}

/** The baked surfaces' grade (null: the switch off, every graded shader keeps its own). */
export function packGrade(out: Float32Array, g: SectLook["grade"] | null): void {
  const s = LOOK_SLOT.grade;
  if (!g) {
    out[(s + 2) * 4 + 3] = 0;
    return;
  }
  const st = unit(g.shadowTint);
  const ht = unit(g.highlightTint);
  put(out, s, st[0], st[1], st[2], g.splitShadow ?? g.split);
  put(out, s + 1, ht[0], ht[1], ht[2], g.split);
  put(out, s + 2, g.exposure, g.contrast, g.pivot, 1);
  put(out, s + 3, g.saturation, g.greenTame, g.shoulder, 0);
}

/**
 * The frame grade into `out` from vec4 `slot` (the frame group of uSectLook, or an array of its
 * own): glsl.ts lookFrameGradeGlsl's layout.
 */
export function packFrame(out: Float32Array, g: FrameGrade, slot: number = LOOK_SLOT.frame): void {
  const bal = unit(g.balance);
  const st = unit(g.shadowTint);
  const ht = unit(g.highlightTint);
  const lift = hexToLinear(g.liftColor);
  put(out, slot, Math.max(g.amount, 0), g.exposure, g.contrast, Math.min(Math.max(g.pivot, 0.05), 0.95));
  put(out, slot + 1, bal[0], bal[1], bal[2], g.saturation);
  put(out, slot + 2, st[0], st[1], st[2], g.shadowAmount);
  put(out, slot + 3, ht[0], ht[1], ht[2], g.highlightAmount);
  put(out, slot + 4, lift[0], lift[1], lift[2], g.lift);
  put(out, slot + 5, g.splitPivot, Math.max(g.splitWidth, 1e-3), g.redSaturation, g.glowGain);
  put(out, slot + 6, g.glowFrom, Math.max(g.glowTo, g.glowFrom + 1e-3), 0, 0);
}

/** The surfaces' grade numbers behind their switch (look.ts gradeGlsl uses them). */
export function gradeLookDefines(g: SectLook["grade"]): string {
  const on = `( uSectLook[ ${LOOK_SLOT.grade + 2} ].w > 0.5 )`;
  const f = (slot: number, comp: string, v: number) => `( ${on} ? uSectLook[ ${slot} ].${comp} : ${glslFloat(v)} )`;
  const v4 = (slot: number, t: Vec3, w: number) =>
    `( ${on} ? uSectLook[ ${slot} ] : vec4( ${glslFloat(t[0])}, ${glslFloat(t[1])}, ${glslFloat(t[2])}, ${glslFloat(w)} ) )`;
  const s = LOOK_SLOT.grade;
  return [
    LOOK_UNIFORM_GLSL,
    `#define SECT_GRADE_EXPOSURE ${f(s + 2, "x", g.exposure)}`,
    `#define SECT_GRADE_CONTRAST ${f(s + 2, "y", g.contrast)}`,
    `#define SECT_GRADE_PIVOT ${f(s + 2, "z", g.pivot)}`,
    `#define SECT_GRADE_SATURATION ${f(s + 3, "x", g.saturation)}`,
    `#define SECT_GRADE_TAME ${f(s + 3, "y", g.greenTame)}`,
    `#define SECT_GRADE_SHOULDER ${f(s + 3, "z", g.shoulder)}`,
    // The shadow tint (luminance 1) and its split; the highlight tint and its split.
    `#define SECT_GRADE_SHADOW ${v4(s, unit(g.shadowTint), g.splitShadow ?? g.split)}`,
    `#define SECT_GRADE_HIGH ${v4(s + 1, unit(g.highlightTint), g.split)}`,
  ].join("\n");
}
