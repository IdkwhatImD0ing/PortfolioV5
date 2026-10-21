/**
 * Decoration for /sect that the style frames have and the bake does not: peach petals drifting
 * around the camera and cranes circling the areas. Pure maths (no three.js); the shaders in
 * experience/fx.tsx mirror petalOffset so the motion is testable here.
 */
import type { Vec3 } from "./types";

/** Deterministic 0..1 hash of an integer (and a salt). */
export function hash01(i: number, salt = 0): number {
  let h = (Math.imul(i + 1, 374761393) ^ Math.imul(salt + 7, 668265263)) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967295;
}

/** Floats per petal in the instance buffer: seed position in -1..1 (3), phase, spin, colour mix. */
export const PETAL_STRIDE = 6;

export function petalSeeds(count: number): Float32Array {
  const out = new Float32Array(count * PETAL_STRIDE);
  for (let i = 0; i < count; i++) {
    const o = i * PETAL_STRIDE;
    out[o] = hash01(i, 1) * 2 - 1;
    out[o + 1] = hash01(i, 2) * 2 - 1;
    out[o + 2] = hash01(i, 3) * 2 - 1;
    out[o + 3] = hash01(i, 4) * Math.PI * 2;
    out[o + 4] = 0.6 + hash01(i, 5) * 1.6;
    out[o + 5] = hash01(i, 6);
  }
  return out;
}

/** a mod n into [0, n), also for negative a. */
export function wrap(a: number, n: number): number {
  return a - n * Math.floor(a / n);
}

/** Wind (m/s): the petals drift east-north-east and sink slowly, like the style frames. */
export const PETAL_WIND: Vec3 = [0.9, -0.45, -0.35];

/**
 * Where a petal is relative to the camera: its seed point in a cube of half-size `radius`, carried
 * by the wind with a sideways flutter, wrapped so the cube always surrounds the camera.
 */
export function petalOffset(seed: Vec3, phase: number, t: number, cam: Vec3, radius: number): Vec3 {
  const size = radius * 2;
  const out: Vec3 = [0, 0, 0];
  for (let k = 0; k < 3; k++) {
    const flutter = k === 1 ? 0 : Math.sin(t * 1.3 + phase + k) * 0.6;
    const p = seed[k] * radius + PETAL_WIND[k] * t + flutter;
    out[k] = wrap(p - cam[k] + radius, size) - radius;
  }
  return out;
}

export interface CraneFlight {
  /** Centre of the loop (three space). */
  center: Vec3;
  /** Loop radii on the ground plane (m). */
  rx: number;
  rz: number;
  /** Radians per second around the loop (sign = direction). */
  speed: number;
  phase: number;
  /** Height wobble (m). */
  bob: number;
}

/** A few cranes circling high over the two areas (seeded, so every visit looks the same). */
export function craneFlights(areas: readonly Vec3[], count: number): CraneFlight[] {
  const out: CraneFlight[] = [];
  for (let i = 0; i < count && areas.length > 0; i++) {
    const a = areas[i % areas.length];
    out.push({
      // Ahead of the area (the camera looks north, three -z, at both holds) and above it.
      center: [a[0] + (hash01(i, 11) - 0.5) * 80, a[1] + 40 + hash01(i, 12) * 35, a[2] - 110 + (hash01(i, 13) - 0.5) * 60],
      rx: 50 + hash01(i, 14) * 60,
      rz: 30 + hash01(i, 15) * 40,
      speed: (0.05 + hash01(i, 16) * 0.04) * (hash01(i, 17) > 0.5 ? 1 : -1),
      phase: hash01(i, 18) * Math.PI * 2,
      bob: 3 + hash01(i, 19) * 4,
    });
  }
  return out;
}

/** Crane position and heading (radians about +y, 0 = facing -z) at time t. */
export function cranePose(f: CraneFlight, t: number): { p: Vec3; heading: number } {
  const a = f.phase + f.speed * t;
  const p: Vec3 = [f.center[0] + Math.cos(a) * f.rx, f.center[1] + Math.sin(a * 2.3) * f.bob, f.center[2] + Math.sin(a) * f.rz];
  // Velocity direction on the ellipse.
  const vx = -Math.sin(a) * f.rx * Math.sign(f.speed);
  const vz = Math.cos(a) * f.rz * Math.sign(f.speed);
  return { p, heading: Math.atan2(-vx, -vz) };
}
