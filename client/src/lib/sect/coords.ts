/**
 * Coordinate helpers between Blender (Z up) and three.js (Y up), plus a pinhole projection used
 * to check that camera.json frames a known point where the Blender render does.
 * glTF convention: three = (bx, bz, -by), a -90 degree rotation about X.
 */
import { rotate } from "./camera-path";
import type { Quat, Vec3 } from "./types";

export function blenderToThree(v: Vec3): Vec3 {
  return [v[0], v[2], -v[1]];
}

export function threeToBlender(v: Vec3): Vec3 {
  return [v[0], -v[2], v[1]];
}

/** Bounding-box sizes swap axes but never change sign. */
export function blenderSizeToThree(s: Vec3): Vec3 {
  return [s[0], s[2], s[1]];
}

function mulQuat(a: Quat, b: Quat): Quat {
  const [ax, ay, az, aw] = a;
  const [bx, by, bz, bw] = b;
  return [
    aw * bx + ax * bw + ay * bz - az * by,
    aw * by - ax * bz + ay * bw + az * bx,
    aw * bz + ax * by - ay * bx + az * bw,
    aw * bw - ax * bx - ay * by - az * bz,
  ];
}

const S = Math.SQRT1_2;
/** Rotation of -90 degrees about X (Blender world to three world). */
const C: Quat = [-S, 0, 0, S];

/** World orientation (x, y, z, w) of a Blender object expressed in three.js world space. */
export function blenderQuatToThree(q: Quat): Quat {
  return mulQuat(C, q);
}

export interface Projection {
  /** Normalised device coordinates: x right, y up, -1..1 inside the frame. */
  ndc: [number, number];
  /** Distance along the view axis (metres); negative means behind the camera. */
  depth: number;
  distance: number;
}

/** Projects world point `x` through a camera at `p` with orientation `q` (looks down local -Z). */
export function projectPoint(p: Vec3, q: Quat, fovYDeg: number, aspect: number, x: Vec3): Projection {
  const rel: Vec3 = [x[0] - p[0], x[1] - p[1], x[2] - p[2]];
  const inv: Quat = [-q[0], -q[1], -q[2], q[3]];
  const local = rotate(inv, rel);
  const depth = -local[2];
  const t = Math.tan(((fovYDeg * Math.PI) / 180) / 2);
  return {
    ndc: [local[0] / (depth * t * aspect), local[1] / (depth * t)],
    depth,
    distance: Math.hypot(rel[0], rel[1], rel[2]),
  };
}
