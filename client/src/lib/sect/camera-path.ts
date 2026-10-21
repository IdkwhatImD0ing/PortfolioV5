/**
 * Sampling the exported camera (and flyer) path at fractional frames.
 * Position: uniform Catmull-Rom through the samples. Rotation: shortest-arc slerp. fovY: lerp.
 * Plain number arrays, no three.js, so the maths is unit-testable.
 */
import type { CameraFrame, PathFrame, Quat, Vec3 } from "./types";

export interface PathSample {
  p: Vec3;
  q: Quat;
}

export interface CameraSample extends PathSample {
  fovY: number;
}

export function clamp(x: number, lo: number, hi: number): number {
  return x < lo ? lo : x > hi ? hi : x;
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/** Uniform Catmull-Rom between p1 and p2 (t in 0..1), with p0/p3 as neighbours. */
export function catmullRom(p0: Vec3, p1: Vec3, p2: Vec3, p3: Vec3, t: number): Vec3 {
  const t2 = t * t;
  const t3 = t2 * t;
  const out: Vec3 = [0, 0, 0];
  for (let k = 0; k < 3; k++) {
    out[k] =
      0.5 *
      (2 * p1[k] +
        (-p0[k] + p2[k]) * t +
        (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2 +
        (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3);
  }
  return out;
}

export function normalizeQuat(q: Quat): Quat {
  const l = Math.hypot(q[0], q[1], q[2], q[3]);
  if (l < 1e-12) return [0, 0, 0, 1];
  return [q[0] / l, q[1] / l, q[2] / l, q[3] / l];
}

/** Shortest-arc spherical interpolation between unit quaternions (x, y, z, w). */
export function slerp(a: Quat, b: Quat, t: number): Quat {
  let [bx, by, bz, bw] = b;
  let cos = a[0] * bx + a[1] * by + a[2] * bz + a[3] * bw;
  if (cos < 0) {
    cos = -cos;
    bx = -bx;
    by = -by;
    bz = -bz;
    bw = -bw;
  }
  let wa: number;
  let wb: number;
  if (cos > 0.9995) {
    wa = 1 - t;
    wb = t;
  } else {
    const theta = Math.acos(clamp(cos, -1, 1));
    const sin = Math.sin(theta);
    wa = Math.sin((1 - t) * theta) / sin;
    wb = Math.sin(t * theta) / sin;
  }
  return normalizeQuat([a[0] * wa + bx * wb, a[1] * wa + by * wb, a[2] * wa + bz * wb, a[3] * wa + bw * wb]);
}

/**
 * Index of the sample at or before frame `f`, and the fraction toward the next one. Frames are
 * sorted (parse.ts drops repeated frame numbers); a non-finite f counts as the first frame.
 */
export function locate(frames: readonly PathFrame[], f: number): { i: number; s: number } {
  const n = frames.length;
  const first = frames[0].f;
  const last = frames[n - 1].f;
  const t = Number.isFinite(f) ? clamp(f, first, last) : first;
  // Fast path: consecutive integer frames. Checked at the two samples it lands between, so a
  // repeated or fractional frame number that happens to give the same span falls back to search.
  if (last - first === n - 1 && Number.isInteger(first) && Number.isInteger(last)) {
    const i = Math.min(Math.floor(t - first), n - 2);
    if (frames[i].f === first + i && frames[i + 1].f === first + i + 1) return { i, s: t - first - i };
  }
  let lo = 0;
  let hi = n - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (frames[mid].f <= t) lo = mid;
    else hi = mid;
  }
  const span = frames[hi].f - frames[lo].f;
  return { i: lo, s: span > 0 ? (t - frames[lo].f) / span : 0 };
}

export function samplePath(frames: readonly PathFrame[], f: number): PathSample {
  const n = frames.length;
  if (n === 1) return { p: [...frames[0].p], q: [...frames[0].q] };
  const { i, s } = locate(frames, f);
  const p0 = frames[Math.max(i - 1, 0)].p;
  const p1 = frames[i].p;
  const p2 = frames[i + 1].p;
  const p3 = frames[Math.min(i + 2, n - 1)].p;
  return { p: catmullRom(p0, p1, p2, p3, s), q: slerp(frames[i].q, frames[i + 1].q, s) };
}

export function sampleCamera(frames: readonly CameraFrame[], f: number): CameraSample {
  const base = samplePath(frames, f);
  if (frames.length === 1) return { ...base, fovY: frames[0].fovY };
  const { i, s } = locate(frames, f);
  return { ...base, fovY: lerp(frames[i].fovY, frames[i + 1].fovY, s) };
}

const DEG = Math.PI / 180;

/**
 * Vertical FOV for a viewport aspect. Keeps the reference horizontal FOV, so narrow (portrait)
 * screens see the same width of the scene, but never narrower than the original fovY and never
 * wider than maxFovY.
 */
export function fovForAspect(fovY: number, refAspect: number, aspect: number, maxFovY = 70): number {
  if (!(aspect > 0) || !(refAspect > 0)) return fovY;
  const fovX = 2 * Math.atan(Math.tan((fovY * DEG) / 2) * refAspect);
  const wanted = (2 * Math.atan(Math.tan(fovX / 2) / aspect)) / DEG;
  return clamp(wanted, fovY, Math.max(fovY, maxFovY));
}

/** Rotates vector v by unit quaternion q. */
export function rotate(q: Quat, v: Vec3): Vec3 {
  const [x, y, z, w] = q;
  // t = 2 * cross(q.xyz, v)
  const tx = 2 * (y * v[2] - z * v[1]);
  const ty = 2 * (z * v[0] - x * v[2]);
  const tz = 2 * (x * v[1] - y * v[0]);
  return [v[0] + w * tx + (y * tz - z * ty), v[1] + w * ty + (z * tx - x * tz), v[2] + w * tz + (x * ty - y * tx)];
}

/** Direction a camera with orientation q looks along (its local -Z). */
export function forward(q: Quat): Vec3 {
  return rotate(q, [0, 0, -1]);
}
