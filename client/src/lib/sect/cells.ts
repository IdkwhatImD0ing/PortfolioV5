/**
 * Merge cells for static geometry that grow with distance from the camera path: small near the
 * path (fine culling where the detail is), large far away (few draw calls for scenery that is
 * always in view anyway). Distances are measured on the ground plane (three x/z).
 */
import type { Vec3 } from "./types";

export interface CellTiers {
  /** [maxDistance, cellSize] pairs in ascending distance; the last size applies beyond. */
  steps: [number, number][];
  farSize: number;
}

export const DEFAULT_CELL_TIERS: CellTiers = {
  steps: [
    [250, 150],
    [900, 450],
  ],
  farSize: 1800,
};

/** Ground-plane distance to the nearest path sample (camera paths are sampled every few metres). */
export function distanceToPath2D(path: readonly Vec3[], x: number, z: number): number {
  let d2 = Infinity;
  for (const p of path) {
    const dx = p[0] - x;
    const dz = p[2] - z;
    const v = dx * dx + dz * dz;
    if (v < d2) d2 = v;
  }
  return Math.sqrt(d2);
}

export function pathCellKey(path: readonly Vec3[], tiers: CellTiers = DEFAULT_CELL_TIERS): (x: number, y: number, z: number) => string {
  return (x, _y, z) => {
    const d = distanceToPath2D(path, x, z);
    let size = tiers.farSize;
    for (const [maxD, s] of tiers.steps) {
      if (d < maxD) {
        size = s;
        break;
      }
    }
    return `${size}:${Math.floor(x / size)},${Math.floor(z / size)}`;
  };
}
