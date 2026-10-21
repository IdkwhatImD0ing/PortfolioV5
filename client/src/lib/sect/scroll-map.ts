/**
 * Scroll position -> camera frame, with dwell ("hold") zones where the camera stops so an overlay
 * panel can be read. Distances are in abstract scroll units; the page decides how many pixels a
 * unit is. Moving segments are eased so the camera slows into each hold and speeds out of it.
 */
import { clamp } from "./camera-path";
import type { Hold } from "./types";

export interface ScrollMapOptions {
  /** Scroll units per camera frame on moving segments. */
  unitsPerFrame?: number;
  /** Extra scroll units where the camera stays on a hold frame. */
  dwellUnits?: number;
  /** 0 = linear, 1 = full smoothstep on every moving segment. */
  ease?: number;
}

export interface Segment {
  kind: "move" | "hold";
  u0: number;
  u1: number;
  f0: number;
  f1: number;
  holdId?: string;
}

export interface HoldZone extends Hold {
  u0: number;
  u1: number;
  uMid: number;
}

export interface Stop {
  id: string;
  label: string;
  frame: number;
  u: number;
}

export interface ScrollMap {
  segments: Segment[];
  holds: HoldZone[];
  /** Reduced-motion stops: start, each hold, end. */
  stops: Stop[];
  totalUnits: number;
  startFrame: number;
  endFrame: number;
  ease: number;
}

/**
 * The flight's scroll feel, the same as the first test's: one unit per frame on moving segments
 * and 42 units of dwell at every hold. With eleven holds the page simply gets longer (about 36
 * screens), so each leg between two areas scrolls like the gate-to-mirror leg did.
 */
export const FLIGHT_SCROLL: Required<ScrollMapOptions> = { unitsPerFrame: 1, dwellUnits: 42, ease: 0.55 };

export function easeInOut(t: number, e: number): number {
  const x = clamp(t, 0, 1);
  return (1 - e) * x + e * x * x * (3 - 2 * x);
}

/** Inverse of easeInOut (it is monotonic for e in 0..1), by bisection. */
export function easeInOutInverse(y: number, e: number): number {
  const target = clamp(y, 0, 1);
  if (e <= 0) return target;
  let lo = 0;
  let hi = 1;
  for (let k = 0; k < 48; k++) {
    const mid = (lo + hi) / 2;
    if (easeInOut(mid, e) < target) lo = mid;
    else hi = mid;
  }
  return (lo + hi) / 2;
}

export function buildScrollMap(
  startFrame: number,
  endFrame: number,
  holds: readonly Hold[],
  opts: ScrollMapOptions = {},
): ScrollMap {
  const upf = opts.unitsPerFrame ?? 1;
  const dwell = opts.dwellUnits ?? 40;
  const ease = clamp(opts.ease ?? 0.6, 0, 1);
  const end = Math.max(endFrame, startFrame);
  const sorted = [...holds].filter((h) => h.frame >= startFrame && h.frame <= end).sort((a, b) => a.frame - b.frame);

  const segments: Segment[] = [];
  const zones: HoldZone[] = [];
  let f = startFrame;
  let u = 0;
  for (const h of sorted) {
    if (h.frame > f) {
      const len = (h.frame - f) * upf;
      segments.push({ kind: "move", u0: u, u1: u + len, f0: f, f1: h.frame });
      u += len;
      f = h.frame;
    }
    if (zones.some((z) => z.frame === h.frame)) continue;
    segments.push({ kind: "hold", u0: u, u1: u + dwell, f0: h.frame, f1: h.frame, holdId: h.id });
    zones.push({ ...h, u0: u, u1: u + dwell, uMid: u + dwell / 2 });
    u += dwell;
  }
  if (end > f) {
    const len = (end - f) * upf;
    segments.push({ kind: "move", u0: u, u1: u + len, f0: f, f1: end });
    u += len;
  }
  if (segments.length === 0) segments.push({ kind: "hold", u0: 0, u1: 0, f0: startFrame, f1: startFrame });

  const stops: Stop[] = [{ id: "start", label: "Start", frame: startFrame, u: 0 }];
  for (const z of zones) stops.push({ id: z.id, label: z.label, frame: z.frame, u: z.uMid });
  const lastHoldFrame = zones.length > 0 ? zones[zones.length - 1].frame : startFrame;
  if (end > lastHoldFrame) stops.push({ id: "end", label: "End", frame: end, u });

  return { segments, holds: zones, stops, totalUnits: u, startFrame, endFrame: end, ease };
}

function segmentAt(map: ScrollMap, u: number): Segment {
  for (const s of map.segments) if (u <= s.u1) return s;
  return map.segments[map.segments.length - 1];
}

export function uToFrame(map: ScrollMap, u: number): number {
  const x = clamp(u, 0, map.totalUnits);
  const s = segmentAt(map, x);
  if (s.kind === "hold" || s.u1 <= s.u0) return s.f0;
  const t = easeInOut((x - s.u0) / (s.u1 - s.u0), map.ease);
  return s.f0 + (s.f1 - s.f0) * t;
}

/** Scroll units that show frame f. A hold frame maps to the middle of its dwell zone. */
export function frameToU(map: ScrollMap, frame: number): number {
  if (!Number.isFinite(frame)) return 0;
  const f = frame;
  // Holds first: a hold on the start or end frame still maps to the middle of its dwell zone.
  const zone = map.holds.find((z) => Math.abs(z.frame - f) < 1e-6);
  if (zone) return zone.uMid;
  if (frame <= map.startFrame) return 0;
  if (frame >= map.endFrame) return map.totalUnits;
  for (const s of map.segments) {
    if (s.kind !== "move") continue;
    if (f >= s.f0 && f <= s.f1) {
      const t = easeInOutInverse((f - s.f0) / (s.f1 - s.f0), map.ease);
      return s.u0 + t * (s.u1 - s.u0);
    }
  }
  return f <= map.startFrame ? 0 : map.totalUnits;
}

export interface Presence {
  id: string;
  /** 0..1: 1 inside the dwell zone, fading to 0 `fadeUnits` outside it. */
  amount: number;
}

function smooth01(t: number): number {
  const x = clamp(t, 0, 1);
  return x * x * (3 - 2 * x);
}

/**
 * How much each hold's panel shows at scroll position u. With `lastToEnd`, the last hold's panel
 * stays up from its dwell to the end of the track (the contact panel at the bottom of the page).
 */
export function holdPresence(map: ScrollMap, u: number, fadeUnits = 14, lastToEnd = false): Presence[] {
  const last = map.holds.length - 1;
  return map.holds.map((z, i) => {
    const after = lastToEnd && i === last ? 0 : u - z.u1;
    const d = u < z.u0 ? z.u0 - u : u > z.u1 ? Math.max(after, 0) : 0;
    return { id: z.id, amount: fadeUnits > 0 ? smooth01(1 - d / fadeUnits) : d === 0 ? 1 : 0 };
  });
}

/** 1 at the very top of the page, 0 after `fadeUnits` of scrolling. */
export function introPresence(u: number, fadeUnits = 10): number {
  return 1 - smooth01(u / fadeUnits);
}

/** Reduced motion: the stop nearest to scroll position u. */
export function nearestStop(map: ScrollMap, u: number): Stop {
  let best = map.stops[0];
  for (const s of map.stops) if (Math.abs(s.u - u) < Math.abs(best.u - u)) best = s;
  return best;
}

/** Pixels of scroll per unit, scaled so the journey takes a similar number of screens on any device. */
export function pxPerUnit(viewportHeight: number): number {
  return clamp(viewportHeight / 60, 8, 18);
}

export function scrollToU(scrollY: number, maxScroll: number, totalUnits: number): number {
  if (maxScroll <= 0) return 0;
  return clamp(scrollY / maxScroll, 0, 1) * totalUnits;
}

export function uToScroll(u: number, maxScroll: number, totalUnits: number): number {
  if (totalUnits <= 0) return 0;
  return clamp(u / totalUnits, 0, 1) * Math.max(0, maxScroll);
}

/** Viewport size the scroll track is built from. */
export interface TrackViewport {
  width: number;
  height: number;
}

/**
 * The track height should not follow every viewport change: on phones the address bar shows and
 * hides during the first scroll (innerHeight changes by ~50-100 px), and re-sizing the track then
 * jumps the page and cancels the flick. Re-size (and re-sync the scroll position) only when the
 * width changes (rotation, window resize) or the height changes by more than `tolerance` of itself.
 */
export function nextTrackViewport(
  current: TrackViewport,
  width: number,
  height: number,
  tolerance = 0.2,
): { viewport: TrackViewport; resize: boolean } {
  const widthChanged = Math.abs(width - current.width) > 1;
  const bigHeightChange = current.height <= 0 || Math.abs(height - current.height) > tolerance * current.height;
  if (widthChanged || bigHeightChange) return { viewport: { width, height }, resize: true };
  return { viewport: current, resize: false };
}
