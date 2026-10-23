/**
 * Stop framing: at a stop whose hold frame leaves its subject off to one side (the Heart-Mirror sat
 * near the left edge at the mirror's hold, its pond cut by the bottom), the camera stands a little
 * back along the baked path and its view turns a few degrees, on top of the path's own orientation.
 * The turn is a yaw about world up and a pitch about the camera's own right axis (free-look.ts
 * composeLook), then the visitor's free look on top. Standing back moves the camera only along the
 * film's own path: at the hold it shows the film's pose of a few frames earlier (framingFrame).
 *
 * Both are functions of the path frame, not of time: they grow from nothing FRAMING_REACH_FRAMES
 * (or the stop's own reach) before the hold frame to their full size at the hold, and fade the same
 * way after it, along a smoothstep, so their rate is zero at both ends and at the hold itself. The
 * flight stays smooth (no jerk where it starts or ends, and the scroll's own easing into the hold
 * slows it further); a jump flies through the same frames, so it eases in the same way; with reduced
 * motion the camera steps from stop to stop and lands on the framed view at once, with no motion of
 * its own; and the view between stops is the film's own.
 *
 * Kept small (FRAMING_MAX_DEG, FRAMING_MAX_BACK): every view the framing shows is a pose the film
 * itself flies through, turned a few degrees. The bake's visibility covers the film's poses (the
 * audit renders the path every few frames) and all-round views at every hold and every 48 frames
 * between them (export_web.py audit, see free-look.ts), so no hole or missing piece shows.
 *
 * Pure: plain numbers, no three.js.
 */
import type { LookOffset } from "./free-look";

const DEG = Math.PI / 180;

/**
 * A stop's framing: its turn, in degrees (yaw positive turns the view left, pitch positive tilts it
 * up), how far back along the path the camera stands at the hold, in frames (none when absent), and
 * over how many frames either side of the hold the framing comes and goes (FRAMING_REACH_FRAMES when
 * absent; never fewer).
 */
export interface StopFraming {
  yaw: number;
  pitch: number;
  back?: number;
  reach?: number;
}

/** Most a stop's framing may turn the view, either way (degrees). */
export const FRAMING_MAX_DEG = 8;

/**
 * Most a stop's framing may pull the camera back along the path (frames). With a reach of at least
 * FRAMING_REACH_FRAMES, the camera's pace along the path then stays between half and one and a half
 * times the film's own.
 */
export const FRAMING_MAX_BACK = 16;

/**
 * Frames before and after a hold over which its framing comes and goes, unless the stop sets a longer
 * reach. Stops are at least 103 frames apart (the arena at 516, the mission hall at 619), so two never
 * overlap (a longer reach is kept to the room its neighbours leave: the mirror's 80 lies between the
 * gate at 93 and the forge at 352, neither framed), and the poster's start view (frame 27,
 * opening.ts POSTER) is 66 frames before the first stop, out of reach. At the steepest an 8 degree
 * turn adds 0.25 degrees a frame to the film's own turning (up to about 1 a frame round the framed
 * stops).
 */
export const FRAMING_REACH_FRAMES = 48;

/**
 * The stops that need framing, by hold id, chosen on the hold frames at 16:9 (1600 x 900, the panel
 * up; framing.test.ts checks the numbers). Stops not listed keep the film's framing: the gate, the
 * forge, the arena, the library, the stele forest, the jade slip, the abode and the summit are
 * balanced as they are. (The jade slip was framed from 2026-10-22, turned square to a view turned 6
 * degrees left, then stood back and tilted up too; the owner preferred the first build, so the slip
 * stands where it first stood, big and close on the left with its left part past the edge, and the
 * view is the film's own: blender scroll.py, patch_r15_scroll_restore.py.)
 * - mirror: the camera stood 19 m above the near edge of the Still Pond and saw only its far side,
 *   cut by the left edge and the bottom, the pavilion cut by the left edge and the Heart-Mirror 290 px
 *   in from it. A turn alone cannot fit the pond and the mirror in from there, so the camera stands
 *   back 13 frames (18 m, the film's own pose at frame 204) and turns a little left and down: the
 *   whole pond in the middle of the picture below the panel, the pavilion on its island, and the
 *   Heart-Mirror on its dais straight above its own reflection, left of the panel. It comes and goes
 *   over 80 frames, not 48 (clear of the gate at 93 and the forge at 352, neither framed): standing
 *   back speeds the camera along the path on the way out, where the film turns fastest, and over 48
 *   frames the view would peak at 1.3 degrees a frame there; over 80 it peaks at 1.1, as the old 8
 *   degree turn did. The camera's pace stays between 0.76 and 1.24 of the film's.
 * - mission: the hall and its board of seven posts sat on the left, the first post touching the edge
 *   and the roof cut by the top, an empty courtyard on the right. Left and a little up: hall and
 *   board in the middle, the bell pavilion beside them.
 * - formation: the plaza sat on the bottom edge, its front stations and gate cut off, under the next
 *   stop's mountain. Down: the whole array, armillary, flags and gate in, the mountain behind.
 */
export const STOP_FRAMING: Readonly<Record<string, StopFraming>> = {
  mirror: { yaw: 4, pitch: -3, back: 13, reach: 80 },
  mission: { yaw: 8, pitch: 2 },
  formation: { yaw: 0, pitch: -8 },
};

/** 0 `reach` frames or more from the hold, 1 at it, eased (smoothstep) between: zero slope at both ends. */
export function framingWeight(frame: number, holdFrame: number, reach: number = FRAMING_REACH_FRAMES): number {
  if (!Number.isFinite(frame) || !(reach > 0)) return 0;
  const x = 1 - Math.abs(frame - holdFrame) / reach;
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  return x * x * (3 - 2 * x);
}

/** A stop's own reach (frames): its `reach`, never less than `reach` (the default). */
export function framingReach(t: StopFraming, reach: number = FRAMING_REACH_FRAMES): number {
  return Math.max(reach, t.reach ?? reach);
}

/** The listed hold nearest `frame` within its reach of it, with its framing and weight, or null. */
function framedHold(
  holds: readonly { id: string; frame: number }[],
  frame: number,
  table: Readonly<Record<string, StopFraming>>,
  reach: number,
): { t: StopFraming; w: number } | null {
  let best: { t: StopFraming; w: number; d: number } | null = null;
  for (const h of holds) {
    const t = table[h.id];
    if (!t) continue;
    const r = framingReach(t, reach);
    const d = Math.abs(frame - h.frame);
    if (d < r && (!best || d < best.d)) best = { t, w: framingWeight(frame, h.frame, r), d };
  }
  return best;
}

/**
 * The framing turn (radians, as a free-look offset) at path frame `frame`: the nearest listed hold's
 * turn times its weight (over the stop's own reach). Each turn is held to FRAMING_MAX_DEG.
 */
export function framingAt(
  holds: readonly { id: string; frame: number }[],
  frame: number,
  table: Readonly<Record<string, StopFraming>> = STOP_FRAMING,
  reach: number = FRAMING_REACH_FRAMES,
): LookOffset {
  const near = framedHold(holds, frame, table, reach);
  if (!near) return { yaw: 0, pitch: 0 };
  const lim = (deg: number) => Math.max(-FRAMING_MAX_DEG, Math.min(FRAMING_MAX_DEG, deg)) * DEG * near.w;
  return { yaw: lim(near.t.yaw), pitch: lim(near.t.pitch) };
}

/**
 * The path frame whose pose the camera takes (position and orientation, before the turn) at path
 * frame `frame`: the nearest listed hold's `back` (held to FRAMING_MAX_BACK) times its weight
 * earlier. The frame itself away from the framed stops; at such a hold, the film's pose `back` frames
 * before it. The camera never stops or turns back: its pace along the path is 1 - back times the
 * weight's slope, from 1 - 1.5 back / reach on the way in to 1 + 1.5 back / reach on the way out (the
 * stop's own reach), and the film's own at the hold and outside the reach.
 */
export function framingFrame(
  holds: readonly { id: string; frame: number }[],
  frame: number,
  table: Readonly<Record<string, StopFraming>> = STOP_FRAMING,
  reach: number = FRAMING_REACH_FRAMES,
): number {
  const near = framedHold(holds, frame, table, reach);
  if (!near) return frame;
  const back = Math.max(0, Math.min(FRAMING_MAX_BACK, near.t.back ?? 0));
  return frame - back * near.w;
}
