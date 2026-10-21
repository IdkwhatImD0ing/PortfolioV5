/**
 * Cloud puffs for /sect: Blender's volume cloud puffs (ellipsoids) drawn as soft camera-facing
 * sprites. Pure helpers (no three.js) so packing, sizing and sorting are testable in node.
 */
import type { CloudPuff, Vec3 } from "./types";

/** Floats per puff in the packed instance buffer: centre (3), semi-axes (9), density (1). */
export const PUFF_STRIDE = 13;

/**
 * Half-extent of an ellipsoid along a unit direction e: |M^T e|, where M's columns are the
 * semi-axes. This is how far the puff's silhouette reaches along e (exact for a parallel view).
 */
export function supportRadius(axes: [Vec3, Vec3, Vec3], e: Vec3): number {
  let s = 0;
  for (const a of axes) {
    const d = a[0] * e[0] + a[1] * e[1] + a[2] * e[2];
    s += d * d;
  }
  return Math.sqrt(s);
}

/** Largest semi-axis length (the bounding-sphere radius). */
export function boundingRadius(axes: [Vec3, Vec3, Vec3]): number {
  return Math.max(...axes.map((a) => Math.hypot(a[0], a[1], a[2])));
}

/** Minimum distance from a point to any of the path points. */
function nearestOnPath(c: Vec3, path: Vec3[]): number {
  let best = Infinity;
  for (const p of path) best = Math.min(best, Math.hypot(c[0] - p[0], c[1] - p[1], c[2] - p[2]));
  return best;
}

/**
 * Keeps puffs whose surface comes within maxDistance of the camera path (a coarse sample of it is
 * plenty) and packs them into one Float32Array, PUFF_STRIDE floats each. densityScale (optional)
 * scales each puff's density by its centre (thinner banks near the two areas).
 */
export function packPuffs(
  puffs: CloudPuff[],
  path: Vec3[],
  maxDistance: number,
  densityScale?: (c: Vec3) => number,
): Float32Array {
  const kept = path.length === 0 ? puffs : puffs.filter((p) => nearestOnPath(p.c, path) - boundingRadius(p.axes) <= maxDistance);
  const out = new Float32Array(kept.length * PUFF_STRIDE);
  kept.forEach((p, i) => {
    const o = i * PUFF_STRIDE;
    out.set(p.c, o);
    out.set(p.axes[0], o + 3);
    out.set(p.axes[1], o + 6);
    out.set(p.axes[2], o + 9);
    out[o + 12] = p.density * (densityScale ? densityScale(p.c) : 1);
  });
  return out;
}

/**
 * Back-to-front order of the packed puffs as seen from cam (farthest first), so alpha blending of
 * overlapping sprites in one instanced draw comes out right. Writes into order and returns it.
 */
export function sortFarToNear(packed: Float32Array, cam: Vec3, order: Uint32Array, scratch: Float32Array): Uint32Array {
  const n = order.length;
  for (let i = 0; i < n; i++) {
    const o = i * PUFF_STRIDE;
    const dx = packed[o] - cam[0];
    const dy = packed[o + 1] - cam[1];
    const dz = packed[o + 2] - cam[2];
    scratch[i] = dx * dx + dy * dy + dz * dz;
    order[i] = i;
  }
  order.sort((a, b) => scratch[b] - scratch[a]);
  return order;
}

/** Squared distance the camera must move before the puffs are re-sorted (sorting is per frame otherwise). */
export const RESORT_DISTANCE2 = 0.5 * 0.5;
