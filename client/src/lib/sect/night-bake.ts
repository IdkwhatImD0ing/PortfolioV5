/**
 * The two night-baked stops seen by day (docs/scene/night-r61.md). Since round 61 the abode and the
 * summit are baked under their own night light (a cool afterglow from the west, the moon from the
 * north-east); every other chunk still holds the scene's sunset. From the stops before the
 * formation, under a gold or blue sky, the two read as cool grey or dark slate shapes beside
 * sunset-warm neighbours, and the summit's sunlit side is the one its moon leaves dark.
 *
 * So the page pulls their baked colour back toward the sunset bake while the sky is still day or
 * sunset: each texel of their atlas materials times exp(q0 + q1 sat(n.sunset) + q2 sat(n.key) +
 * q3 n.y + q4 green), per channel, with n the face's normal and `green` how far the texel leans
 * green (grass and moss took the sunset differently from stone). The chunks carry no normals, so n
 * is the flat face's (the screen derivatives of its world position), and gentle slopes count as
 * level ground (FLAT_UP): a lawn's big flat faces would otherwise each take their own tint.
 *
 * The numbers were fitted per chunk on the round-61 atlases against the sunset ones they replaced,
 * texel by texel in display levels, with each texel's normal from the live normal maps. Mean error
 * in display levels (red, green, blue): the abode from 21, 9, 8 to 15, 8, 6 with one gain (its
 * afterglow came from the sunset's side, so the other terms gained little); the summit from 61,
 * 43, 24 to 43, 30, 18 with all the terms (one gain only got it to 59, 43, 26). It stands in for
 * the old light and does not copy it: cast shadows and bounce stay as baked.
 *
 * How far it pulls is the journey's (FrameLook.nightBake, journey.ts EDGE): all the way up to the
 * scroll, none from the formation on, so the formation, the abode and the summit look as tuned.
 * Glow surfaces, vertex-coloured pieces and the trees (not re-baked) are left alone.
 *
 * Pure data, maths and GLSL strings (no three.js), so it is testable.
 */
import { glslFloat, glslVec3 } from "./glsl";
import type { Vec3 } from "./types";

/** The scene's sunset sun, as meta.json has it (the light every other chunk was baked under). */
export const SUNSET_DIR: Vec3 = [-0.94397, 0.12187, 0.30671];

/**
 * A face whose normal's height is from FLAT_UP[0] (none) to FLAT_UP[1] (all) counts as facing
 * straight up: slopes under about 32 degrees take the level ground's tint, steeper ones their own.
 */
export const FLAT_UP: readonly [number, number] = [0.6, 0.85];

/** One chunk's pull: its own key's direction (its live index's sun) and the fitted terms, per channel. */
export interface SunsetPull {
  key: Vec3;
  /** The constant term. */
  base: Vec3;
  /** Times how much the face turns to the sunset sun (0 to 1). */
  sunset: Vec3;
  /** Times how much the face turns to the chunk's own key (0 to 1). */
  own: Vec3;
  /** Times the normal's height (-1 facing down, 1 facing up). */
  up: Vec3;
  /** Times how far the texel leans green (pullGreen: 0 grey or warm, 1 grass). */
  green: Vec3;
}

const ZERO: Vec3 = [0, 0, 0];

/** The night-baked chunks and their pulls (fitted 2026-11-17 on the round-61 bake). */
export const SUNSET_PULL: Readonly<Record<"abode" | "summit", SunsetPull>> = {
  // The afterglow came from the west like the sunset, so the faces it lit are the sunset's: one
  // gain, more red and less blue.
  abode: {
    key: [-0.83973, 0.46947, 0.27285],
    base: [0.514, 0.163, -0.267],
    sunset: ZERO,
    own: ZERO,
    up: ZERO,
    green: ZERO,
  },
  // The moon stands on the far side: the faces it leaves dark were the sunlit ones.
  summit: {
    key: [0.65562, 0.37461, -0.65562],
    base: [0.945, 0.349, -0.113],
    sunset: [2.331, 2.219, 1.364],
    own: [-3.118, -3.103, -1.656],
    up: [1.297, 0.656, 0.511],
    green: [0.439, 0.483, -0.454],
  },
};

export type PullChunk = keyof typeof SUNSET_PULL;

/**
 * The night-baked chunk an atlas material belongs to (`baked.<chunk>_A<n>`, with any suffix but a
 * glow), or null: the other chunks, glow surfaces, vertex-coloured pieces and the tree chunks.
 */
export function sunsetPullChunk(materialName: string): PullChunk | null {
  if (/\.glow\./i.test(materialName)) return null;
  const m = /^baked\.(abode|summit)_A\d+(?:\.|$)/.exec(materialName);
  return m ? (m[1] as PullChunk) : null;
}

function sat(x: number): number {
  return Math.min(Math.max(x, 0), 1);
}

function smoothstep(a: number, b: number, x: number): number {
  const t = sat((x - a) / (b - a));
  return t * t * (3 - 2 * t);
}

function dot(a: Vec3, b: Vec3): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

/** The normal the pull reads: a gentle slope's turned to straight up (FLAT_UP). */
export function pullNormal(n: Vec3): Vec3 {
  const f = smoothstep(FLAT_UP[0], FLAT_UP[1], n[1]);
  const m: Vec3 = [n[0] * (1 - f), n[1] * (1 - f) + f, n[2] * (1 - f)];
  const l = Math.hypot(m[0], m[1], m[2]);
  return l > 1e-12 ? [m[0] / l, m[1] / l, m[2] / l] : [0, 1, 0];
}

/** How far a linear texel leans green: green's lead over red and blue as a share of green, times 4, to 1. */
export function pullGreen(c: Vec3): number {
  return sat(((c[1] - Math.max(c[0], c[2])) / Math.max(c[1], 1e-4)) * 4);
}

/** The gain on texel `c` of a face with unit normal `n`, pulled all the way. Mirrors sunsetPullGlsl. */
export function sunsetPullGain(c: Vec3, n: Vec3, p: SunsetPull): Vec3 {
  const m = pullNormal(n);
  const s = sat(dot(m, SUNSET_DIR));
  const k = sat(dot(m, p.key));
  const g = pullGreen(c);
  return [0, 1, 2].map((i) => Math.exp(p.base[i] + p.sunset[i] * s + p.own[i] * k + p.up[i] * m[1] + p.green[i] * g)) as Vec3;
}

/** A texel pulled `amount` of the way (0 none, 1 all): the texel times mix(1, gain, amount). Mirrors the GLSL. */
export function sunsetPullLinear(c: Vec3, n: Vec3, p: SunsetPull, amount: number): Vec3 {
  const g = sunsetPullGain(c, n, p);
  const a = sat(amount);
  return c.map((v, i) => v * (1 + (g[i] - 1) * a)) as Vec3;
}

/** A chunk's terms as the shader's uSectPull reads them: base, sunset, own, up, green (rgb), then the key (xyz). */
export function sunsetPullData(p: SunsetPull): Float32Array {
  const out = new Float32Array(24);
  [p.base, p.sunset, p.own, p.up, p.green, p.key].forEach((v, i) => out.set([v[0], v[1], v[2], 0], i * 4));
  return out;
}

/**
 * GLSL: the uniforms (uSectPull, the chunk's terms; uSectPullAmount, how far, shared) and
 * `vec3 sectSunsetPull( vec3 texel, vec3 worldPos )`. Call it only while uSectPullAmount is above 0
 * (a uniform test, so the derivatives stay in uniform control flow): at 0 the texel is untouched.
 */
export function sunsetPullGlsl(): string {
  return /* glsl */ `
uniform vec4 uSectPull[ 6 ];
uniform float uSectPullAmount;
vec3 sectSunsetPull( vec3 c, vec3 wp ) {
  vec3 cr = cross( dFdx( wp ), dFdy( wp ) );
  float cl = length( cr );
  vec3 n = cl > 1e-12 ? cr / cl : vec3( 0.0, 1.0, 0.0 );
  vec3 m = mix( n, vec3( 0.0, 1.0, 0.0 ), smoothstep( ${glslFloat(FLAT_UP[0])}, ${glslFloat(FLAT_UP[1])}, n.y ) );
  float ml = length( m );
  m = ml > 1e-12 ? m / ml : vec3( 0.0, 1.0, 0.0 );
  float s = clamp( dot( m, ${glslVec3(SUNSET_DIR)} ), 0.0, 1.0 );
  float k = clamp( dot( m, uSectPull[ 5 ].xyz ), 0.0, 1.0 );
  float g = clamp( ( c.g - max( c.r, c.b ) ) / max( c.g, 1e-4 ) * 4.0, 0.0, 1.0 );
  vec3 e = uSectPull[ 0 ].rgb + uSectPull[ 1 ].rgb * s + uSectPull[ 2 ].rgb * k + uSectPull[ 3 ].rgb * m.y + uSectPull[ 4 ].rgb * g;
  return c * mix( vec3( 1.0 ), exp( e ), clamp( uSectPullAmount, 0.0, 1.0 ) );
}
`;
}

/** The statement a pulled material runs on its texel (after the live light, before the grade). */
export const SUNSET_PULL_APPLY = "  if ( uSectPullAmount > 0.0 ) sectTexel = sectSunsetPull( sectTexel, vSectWorld );";
