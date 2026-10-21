/**
 * Navigation along the flight: the next and previous stop for keys, the hash for an area, which keys
 * mean what (up and down fly between stops, left and right turn the view), and on which side of
 * the screen an area's panel goes. Pure functions.
 */
import { AREAS } from "./areas";
import { projectPoint } from "./coords";
import type { CameraFrame, Vec3 } from "./types";
import type { ScrollMap } from "./scroll-map";

/** Units within which the camera counts as already at a stop. */
export const AT_STOP_UNITS = 2;

export interface NavStop {
  /** A hold id (area id), or "start" / "end". */
  id: string;
  u: number;
}

/** Start, every hold (at the middle of its dwell), end. */
export function navStops(map: ScrollMap): NavStop[] {
  const out: NavStop[] = [{ id: "start", u: 0 }];
  for (const h of map.holds) out.push({ id: h.id, u: h.uMid });
  if (map.totalUnits > (out[out.length - 1]?.u ?? 0) + AT_STOP_UNITS) out.push({ id: "end", u: map.totalUnits });
  return out;
}

/**
 * The stop after (dir 1) or before (dir -1) scroll position u, skipping a stop the camera is
 * already at. Returns null past the ends. Callers pass where the camera is heading (the target of
 * a flight in progress), so pressing a key twice moves two stops.
 */
export function adjacentStop(map: ScrollMap, u: number, dir: 1 | -1): NavStop | null {
  const stops = navStops(map);
  if (dir > 0) return stops.find((s) => s.u > u + AT_STOP_UNITS) ?? null;
  for (let i = stops.length - 1; i >= 0; i--) if (stops[i].u < u - AT_STOP_UNITS) return stops[i];
  return null;
}

/** The hold nearest to u (the area the rail marks and the hash names), or null without holds. */
export function nearestHold(map: ScrollMap, u: number): string | null {
  let best: string | null = null;
  let dist = Infinity;
  for (const h of map.holds) {
    const d = Math.abs(u - h.uMid);
    if (d < dist) {
      dist = d;
      best = h.id;
    }
  }
  return best;
}

/** The hash for an area: its main-page section id, so links are the same on both pages. */
export function hashForArea(area: string): string {
  const info = AREAS.find((a) => a.id === area);
  return info ? `#${info.sectionId}` : "";
}

export type NavKey = "next" | "prev" | "first" | "last";

/** What a key press means for the flight, or null (leave the key alone). */
export function navKeyIntent(e: { key: string; ctrlKey?: boolean; metaKey?: boolean; altKey?: boolean }): NavKey | null {
  if (e.ctrlKey || e.metaKey || e.altKey) return null;
  switch (e.key) {
    case "PageDown":
    case "ArrowDown":
    case "j":
    case "J":
      return "next";
    case "PageUp":
    case "ArrowUp":
    case "k":
    case "K":
      return "prev";
    case "Home":
      return "first";
    case "End":
      return "last";
    default:
      return null;
  }
}

/**
 * Which way a key turns the view (free look), or null: the left arrow turns it left (1), the right
 * arrow right (-1). Up and down stay with the flight (navKeyIntent).
 */
export function turnKeyIntent(e: { key: string; ctrlKey?: boolean; metaKey?: boolean; altKey?: boolean }): 1 | -1 | null {
  if (e.ctrlKey || e.metaKey || e.altKey) return null;
  if (e.key === "ArrowLeft" || e.key === "Left") return 1;
  if (e.key === "ArrowRight" || e.key === "Right") return -1;
  return null;
}

/**
 * Where a key press takes the camera from scroll position u, or null (nothing that way). Home goes
 * to the very start (the intro); End to the last place (the contact panel), not to the bare end of
 * the track past it.
 */
export function navKeyTarget(map: ScrollMap, u: number, intent: NavKey): NavStop | null {
  if (intent === "first") return u > AT_STOP_UNITS ? { id: "start", u: 0 } : null;
  if (intent === "last") {
    const last = map.holds[map.holds.length - 1];
    const stop: NavStop = last ? { id: last.id, u: last.uMid } : { id: "end", u: map.totalUnits };
    return Math.abs(u - stop.u) > AT_STOP_UNITS ? stop : null;
  }
  return adjacentStop(map, u, intent === "next" ? 1 : -1);
}

/**
 * The side of the screen an area's panel goes on: opposite the area's landmark as the hold frame
 * frames it (landmark right of centre -> "left"). Null when there is no landmark, it is behind the
 * camera, or it sits near the middle (within `centre` of it, in NDC): the panel's own default then.
 */
export function panelSide(frame: CameraFrame, refAspect: number, landmark: Vec3 | null, centre = 0.12): "left" | "right" | null {
  if (!landmark) return null;
  const p = projectPoint(frame.p, frame.q, frame.fovY, refAspect, landmark);
  if (p.depth <= 0 || Math.abs(p.ndc[0]) < centre) return null;
  return p.ndc[0] > 0 ? "left" : "right";
}

/** Flight time in seconds for a programmatic jump over `units` of scroll (adjacent holds about 1.3 s). */
export function flightSeconds(units: number): number {
  const d = Math.abs(units);
  if (d < 1) return 0;
  return Math.min(2.8, 0.7 + Math.sqrt(d) * 0.05);
}
