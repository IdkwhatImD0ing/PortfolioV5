/**
 * Snapping: where the camera goes once the visitor's own scrolling has rested, and the glide that
 * takes it there. Stopping depends on when the visitor stops scrolling, not on where the scroll
 * position is: the scroll map has (almost) no dead stretch at a stop (scroll-map.ts FLIGHT_SCROLL),
 * so scrolling through a stop is one continuous motion, and once the scrolling rests close to a
 * stop the camera glides on to it by itself (sect-experience.tsx wires the rest, scene.tsx's camera rig runs the
 * glide). Pure functions.
 */
import { clamp } from "./camera-path";

export const SNAP = {
  /** No scroll from the visitor (and no finger down) for this long is a rest (ms). */
  restMs: 180,
  /**
   * A stretch of scrolling shorter than this (page pixels) is a nudge: less than one click of a
   * mouse wheel (100 to 120 px), more than a stray trackpad touch. A nudge off a stop settles back
   * on it.
   */
  commitPx: 60,
  /**
   * A rest this close before the stop ahead, as a share of the leg between the two stops it lies
   * between and never more than `reachAheadMax` scroll units, glides on to that stop. Further off,
   * the camera stays where the visitor left it: they may want to sit between two scenes and look
   * around.
   */
  reachAhead: 0.16,
  reachAheadMax: 32,
  /**
   * A rest this close past a stop that was passed in this stretch (an overshoot), as a share of the
   * leg and never more than `reachBackMax` units, comes back to it. The stop a stretch began at is
   * never pulled back to: leaving a scene is free from the first wheel click.
   */
  reachBack: 0.1,
  reachBackMax: 20,
  /** Within this many scroll units of a stop the camera is there already (the hold's frozen half-unit). */
  atStopUnits: 0.5,
} as const;

/**
 * The camera follows the scroll position by exponential damping at this rate (per second): the
 * camera rig's damp(store.u, store.targetU, SCROLL_DAMP, delta). Its speed is then
 * SCROLL_DAMP x (target - u), which coastTarget turns round.
 */
export const SCROLL_DAMP = 5;

/**
 * Where the camera glides to once the visitor's scrolling has rested at scroll position `u`, having
 * begun this stretch at `fromU` (the position at the last rest); null when it stays where it is.
 * `stops`: the scroll map's stops (the start, every hold's middle, the end). `commit`: SNAP.commitPx
 * in scroll units (commitUnits).
 *
 * The snap is a gentle one: the camera is pulled on to a scene only when the scrolling rests close
 * to it, and otherwise stays put, so the visitor can sit between two scenes and look around.
 * - At a stop already (within SNAP.atStopUnits): nothing to do.
 * - A nudge (moved less than `commit`) off a stop: back on to that stop. A nudge between stops stays.
 * - Resting a little before the stop ahead (SNAP.reachAhead): on to it.
 * - Resting a little past a stop that was passed in this stretch (SNAP.reachBack): back to it.
 * - Anywhere else: it stays. The stop the stretch began at never pulls it back.
 * - Before the first stop or past the last: that stop.
 */
export function snapTarget(stops: readonly number[], u: number, fromU: number, commit: number): number | null {
  if (stops.length === 0) return null;
  const s = [...stops].sort((a, b) => a - b);
  if (s.some((x) => Math.abs(x - u) <= SNAP.atStopUnits)) return null;
  if (u <= s[0]) return s[0];
  if (u >= s[s.length - 1]) return s[s.length - 1];
  // The two stops u lies between.
  let i = 0;
  while (s[i + 1] < u) i++;
  const below = s[i];
  const above = s[i + 1];
  const leg = above - below;
  const moved = u - fromU;
  if (Math.abs(moved) < commit) {
    // A nudge: back on to the stop it began at, if it began at one (a pixel's rounding, or a rest
    // within SNAP.atStopUnits, can have left the scroll a hair off it).
    const home = Math.abs(below - fromU) <= Math.abs(above - fromU) ? below : above;
    return Math.abs(home - fromU) <= SNAP.atStopUnits ? home : null;
  }
  const down = moved > 0;
  const ahead = down ? above : below;
  const behind = down ? below : above;
  // Passed in this stretch: the stretch began on the far side of it (not at it: that is leaving it).
  const passed = (down ? behind - fromU : fromU - behind) > SNAP.atStopUnits;
  if (passed && Math.abs(u - behind) <= Math.min(SNAP.reachBack * leg, SNAP.reachBackMax)) return behind;
  if (Math.abs(ahead - u) <= Math.min(SNAP.reachAhead * leg, SNAP.reachAheadMax)) return ahead;
  return null;
}

/** SNAP.commitPx in scroll units, for a track whose `totalUnits` take `maxScroll` page pixels. */
export function commitUnits(totalUnits: number, maxScroll: number): number {
  return (SNAP.commitPx * totalUnits) / Math.max(1, maxScroll);
}

// --- the glide -------------------------------------------------------------------------------------

/** A glide from `fromU` to `toU` over `duration` seconds, starting at speed `v0` (units per second). */
export interface Glide {
  fromU: number;
  toU: number;
  v0: number;
  duration: number;
}

/** Longest glide (s), the far end of the track; a key flight takes at most as long (nav.ts flightSeconds). */
const GLIDE_MAX_S = 2.8;
/**
 * The quintic below runs past its end when it starts faster than this many times its average speed
 * toward the target: its speed is (1-s)^2 (m (1 + 2s - 15s^2) + 30 s^2) x D/T for m = v0 T / D, which
 * stays at or above 0 for every s in 0..1 while m <= 2.5.
 */
const NO_OVERSHOOT = 2.5;

/**
 * Seconds a glide over `units` takes from rest: about 1.25 s to the neighbouring stop on the shortest
 * leg (about 100 units) and 1.75 s on the longest (about 265), half a second for a small nudge back,
 * never more than 2.8 s.
 */
export function glideSeconds(units: number): number {
  return Math.min(GLIDE_MAX_S, 0.45 + 0.08 * Math.sqrt(Math.abs(units)));
}

/**
 * The glide from the camera at `fromU`, moving at `v0` units per second, to the stop at `toU`. It
 * carries that speed on (no stop and restart) and lands softly (no speed and no acceleration at the
 * end). A camera already heading there faster than the glide's own pace gets a shorter glide, so it
 * never runs past the stop and back (one so fast that it gets a glide of a frame or two would be
 * there that soon at its own speed anyway).
 */
export function planGlide(fromU: number, toU: number, v0: number): Glide {
  const d = toU - fromU;
  let duration = glideSeconds(d);
  if (v0 * d > 0) duration = Math.min(duration, (NO_OVERSHOOT * Math.abs(d)) / Math.abs(v0));
  return { fromU, toU, v0, duration };
}

/**
 * Below this speed (units per second, either way) the camera counts as at rest for a key's step: the
 * step keeps its own ease in and out from rest. The damped camera creeps the last hair toward the
 * scroll position at a fraction of a unit a second; a glide or a scroll moves tens of units a second.
 */
export const CARRY_MIN_SPEED = 1;

/**
 * A key's step (or another flight) that begins while the camera moves at `v0` units per second, from
 * `fromU` to the stop at `toU`, over `seconds` (its own length, nav.ts flightSeconds): the glide's
 * curve (glideAt), which carries that speed on and lands softly, instead of stopping the camera dead
 * and easing it out again. Shortened as planGlide does when the camera already heads there faster,
 * so it never runs past the stop and back. Null when the camera is at rest (|v0| < CARRY_MIN_SPEED)
 * or there is nothing to fly: the step keeps its ease from rest.
 */
export function planCarry(fromU: number, toU: number, v0: number, seconds: number): Glide | null {
  if (!(Math.abs(v0) >= CARRY_MIN_SPEED) || !(seconds > 0) || !Number.isFinite(v0)) return null;
  const d = toU - fromU;
  let duration = seconds;
  if (v0 * d > 0) duration = Math.min(duration, (NO_OVERSHOOT * Math.abs(d)) / Math.abs(v0));
  return { fromU, toU, v0, duration };
}

/**
 * Where the glide is `t` seconds in, and how fast it moves (units per second): a quintic from (fromU,
 * v0, no acceleration) to (toU, at rest, no acceleration). At or past its end, the stop itself.
 */
export function glideAt(g: Glide, t: number): { u: number; v: number } {
  if (!(g.duration > 0) || t >= g.duration) return { u: g.toU, v: 0 };
  const s = Math.max(0, t) / g.duration;
  const d = g.toU - g.fromU;
  const r = 1 - s;
  // Hermite basis: H1 carries the start speed, H5 the distance (both flat and still at s = 1).
  const h1 = s - 6 * s ** 3 + 8 * s ** 4 - 3 * s ** 5;
  const h5 = 10 * s ** 3 - 15 * s ** 4 + 6 * s ** 5;
  const dh1 = r * r * (1 + 2 * s - 15 * s * s);
  const dh5 = 30 * s * s * r * r;
  return { u: g.fromU + g.v0 * g.duration * h1 + d * h5, v: g.v0 * dh1 + (d / g.duration) * dh5 };
}

/**
 * The visitor takes over from a glide or flight with the camera at scroll position `u`, moving at
 * `v`: the scroll target to put there so the damped camera (SCROLL_DAMP) carries on at that speed at
 * first, within the track, rather than jolting on toward where the glide was going or stopping dead.
 * Their own scrolling then moves on from there. Never past `toU`, the end of the flight it takes over
 * from (the glide would have stopped there; near its end the coast would otherwise run past the stop,
 * and a wheel click back would then only return to it).
 */
export function coastTarget(u: number, v: number, totalUnits: number, toU?: number): number {
  let to = u + v / SCROLL_DAMP;
  if (toU !== undefined && (to - toU) * (toU - u) > 0) to = toU;
  return clamp(to, 0, Math.max(0, totalUnits));
}

/**
 * A wheel event's vertical turn in page pixels: deltaMode 0 is pixels (Chrome, Safari), 1 lines
 * (Firefox's mouse wheel, about 40 px each), 2 pages (`pageHeight` each).
 */
export function wheelPixels(deltaY: number, deltaMode: number, pageHeight: number): number {
  if (!Number.isFinite(deltaY)) return 0;
  return deltaMode === 1 ? deltaY * 40 : deltaMode === 2 ? deltaY * pageHeight : deltaY;
}
