/**
 * Hotspot picking against axis-aligned boxes (center + size, three space). Cheap enough to run on
 * every pointer move, and it avoids raycasting the large merged scene meshes.
 */
import type { Vec3 } from "./types";

export interface PickBox {
  id: string;
  center: Vec3;
  size: Vec3;
}

/**
 * Distances along the ray to where it enters the box (0 when the origin is inside) and where it
 * leaves it, or null when it misses.
 */
export function rayBoxSpan(origin: Vec3, dir: Vec3, center: Vec3, size: Vec3): [number, number] | null {
  let tmin = -Infinity;
  let tmax = Infinity;
  for (let k = 0; k < 3; k++) {
    const lo = center[k] - size[k] / 2;
    const hi = center[k] + size[k] / 2;
    if (Math.abs(dir[k]) < 1e-12) {
      if (origin[k] < lo || origin[k] > hi) return null;
      continue;
    }
    let t1 = (lo - origin[k]) / dir[k];
    let t2 = (hi - origin[k]) / dir[k];
    if (t1 > t2) [t1, t2] = [t2, t1];
    if (t1 > tmin) tmin = t1;
    if (t2 < tmax) tmax = t2;
    if (tmin > tmax) return null;
  }
  if (tmax < 0) return null;
  return [Math.max(tmin, 0), tmax];
}

/** Distance along the ray to the box (0 when the origin is inside), or null when it misses. */
export function rayBox(origin: Vec3, dir: Vec3, center: Vec3, size: Vec3): number | null {
  return rayBoxSpan(origin, dir, center, size)?.[0] ?? null;
}

/**
 * Item kinds that sit inside their landmark and are only seen through its walls: the library's lit
 * floors (school:0..2) inside the pagoda ("library"). A hit on the landmark's surface near such an
 * item counts as the item, so each floor band of the pagoda opens its school.
 */
export const CONTAINED_ITEM_KINDS: readonly string[] = ["school"];

/** How far (x, y, z metres) around a contained item's box a hit on its landmark still counts. */
export const CONTAINED_ITEM_MARGIN: Vec3 = [3, 4.2, 3];

function inside(p: Vec3, center: Vec3, size: Vec3, margin: Vec3 = [0, 0, 0]): boolean {
  for (let k = 0; k < 3; k++) if (Math.abs(p[k] - center[k]) > size[k] / 2 + margin[k]) return false;
  return true;
}

/**
 * The contained item whose box (grown by `margin`) holds `point`, a hit on `landmark`'s surface, or
 * null. Only items of `kinds` ("school:1" is kind "school") whose box lies inside the landmark's box
 * count; when bands overlap, the item whose centre is nearest the point wins.
 */
export function containedItemAt(
  point: Vec3,
  landmark: PickBox,
  items: readonly PickBox[],
  kinds: readonly string[] = CONTAINED_ITEM_KINDS,
  margin: Vec3 = CONTAINED_ITEM_MARGIN,
): string | null {
  let best: { id: string; d: number } | null = null;
  for (const it of items) {
    const kind = it.id.split(":")[0];
    if (it.id === landmark.id || !it.id.includes(":") || !kinds.includes(kind)) continue;
    const lo = it.center.map((c, k) => c - it.size[k] / 2) as Vec3;
    const hi = it.center.map((c, k) => c + it.size[k] / 2) as Vec3;
    if (!inside(lo, landmark.center, landmark.size, [0.01, 0.01, 0.01]) || !inside(hi, landmark.center, landmark.size, [0.01, 0.01, 0.01])) continue;
    if (!inside(point, it.center, it.size, margin)) continue;
    const d = Math.hypot(point[0] - it.center[0], point[1] - it.center[1], point[2] - it.center[2]);
    if (!best || d < best.d) best = { id: it.id, d };
  }
  return best?.id ?? null;
}

export interface BoxHit {
  id: string;
  /** Where the ray enters the box. */
  distance: number;
  /** Where it leaves it. */
  exit: number;
}

/** Every box the ray hits within maxDistance, nearest first (broad phase for precise picking). */
export function boxHits(origin: Vec3, dir: Vec3, boxes: readonly PickBox[], maxDistance = Infinity): BoxHit[] {
  const out: BoxHit[] = [];
  for (const b of boxes) {
    const t = rayBoxSpan(origin, dir, b.center, b.size);
    if (t !== null && t[0] <= maxDistance) out.push({ id: b.id, distance: t[0], exit: t[1] });
  }
  return out.sort((a, b) => a.distance - b.distance);
}

/**
 * Whether a box hit may stand in for its hotspot's precise test: not when the camera is inside the
 * box (entry at 0). Every ray would then hit it, so the landmark would cover the whole screen, and
 * its "hit point" would be the camera itself, which has no place on screen for a label.
 */
export function canStandIn(hit: BoxHit): boolean {
  return hit.distance > 0;
}

/**
 * The pick when some hotspots could only be tested by their box (their precise test is not
 * available yet): `precise` is the nearest exact hit, `boxOnly` the box-only hit the ray leaves
 * first (of nested boxes the innermost, of boxes one behind the other the front one). A box
 * only wins when there is no exact hit, or the exact one lies beyond the box's far side: an item
 * inside a landmark's box, or in front of it, keeps its own pick (the forge's artifacts inside the
 * hall's box, the library's floors inside the pagoda's), while a landmark still covers what lies
 * behind it.
 */
export function pickWithBoxes<T extends { id: string; distance: number }>(precise: T | null, boxOnly: BoxHit | null): T | BoxHit | null {
  if (!boxOnly || !canStandIn(boxOnly)) return precise;
  if (!precise || precise.distance > boxOnly.exit) return boxOnly;
  return precise;
}

/**
 * True when a point projected to normalised device coordinates (three's Vector3.project) lies in
 * front of the camera, between the near and far planes (-1 <= z <= 1). A point behind the camera
 * projects to z > 1 with its x and y mirrored, so a label placed there would show on the wrong side
 * of the screen: the hover label hides instead (the view can turn all the way round).
 */
export function onScreenDepth(ndcZ: number): boolean {
  return ndcZ >= -1 && ndcZ <= 1;
}
