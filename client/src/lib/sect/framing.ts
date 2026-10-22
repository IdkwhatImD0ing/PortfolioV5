/**
 * Stop framing: a small turn of the view at a stop, on top of the baked path's orientation, for the
 * stops whose hold frame leaves their subject off to one side (the Heart-Mirror sat near the left
 * edge at the mirror's hold). The path camera stays where Blender put it; only where it looks
 * changes, by a few degrees: a yaw about world up and a pitch about the camera's own right axis
 * (free-look.ts composeLook), then the visitor's free look on top.
 *
 * The turn is a function of the path frame, not of time: it grows from nothing FRAMING_REACH_FRAMES
 * before the hold frame to its full size at the hold, and fades the same way after it, along a
 * smoothstep, so its rate is zero at both ends and at the hold itself. The flight stays smooth (no
 * jerk where it starts or ends, and the scroll's own easing into the hold slows it further); a jump
 * flies through the same frames, so it eases in the same way; with reduced motion the camera steps
 * from stop to stop and lands on the framed view at once, with no motion of its own; and the view
 * between stops is the film's own.
 *
 * Kept small (FRAMING_MAX_DEG): the bake's visibility, which also renders all-round views at every
 * hold (export_web.py audit, see free-look.ts), covers a view turned this little, so no hole or
 * missing piece shows at the edges.
 *
 * Pure: plain numbers, no three.js.
 */
import type { LookOffset } from "./free-look";

const DEG = Math.PI / 180;

/** A stop's turn, in degrees: yaw positive turns the view left, pitch positive tilts it up. */
export interface StopFraming {
  yaw: number;
  pitch: number;
}

/** Most a stop's framing may turn the view, either way (degrees). */
export const FRAMING_MAX_DEG = 8;

/**
 * Frames before and after a hold over which its framing comes and goes. Stops are at least 103
 * frames apart (the arena at 516, the mission hall at 619), so two never overlap, and the poster's
 * start view (frame 27, opening.ts POSTER) is 66 frames before the first stop, out of reach. At the
 * steepest an 8 degree turn adds 0.25 degrees a frame to the film's own turning (up to about 1 a
 * frame round the framed stops).
 */
export const FRAMING_REACH_FRAMES = 48;

/**
 * The stops that need a turn, by hold id, chosen on the hold frames at 16:9 (1600 x 900, the panel
 * up; framing.test.ts checks the numbers). Stops not listed keep the film's framing: the gate, the
 * forge, the arena, the library, the stele forest, the abode and the summit are balanced as they are.
 * - mirror: the Heart-Mirror stood 290 px in from the left edge, its terrace cut by it, the pond's
 *   reflection by the bottom. Left and a little down: the mirror on the left third, the whole terrace,
 *   pond and pavilion in, the gate on the right below the panel.
 * - mission: the hall and its board of seven posts sat on the left, the first post touching the edge
 *   and the roof cut by the top, an empty courtyard on the right. Left and a little up: hall and
 *   board in the middle, the bell pavilion beside them.
 * - scroll: the jade slip's left roller was cut by the left edge. Left: the slip whole, the pavilion
 *   near the middle.
 * - formation: the plaza sat on the bottom edge, its front stations and gate cut off, under the next
 *   stop's mountain. Down: the whole array, armillary, flags and gate in, the mountain behind.
 */
export const STOP_FRAMING: Readonly<Record<string, StopFraming>> = {
  mirror: { yaw: 8, pitch: -2 },
  mission: { yaw: 8, pitch: 2 },
  scroll: { yaw: 6, pitch: 0 },
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

/**
 * The framing turn (radians, as a free-look offset) at path frame `frame`: the nearest listed hold's
 * turn times its weight. Each turn is held to FRAMING_MAX_DEG.
 */
export function framingAt(
  holds: readonly { id: string; frame: number }[],
  frame: number,
  table: Readonly<Record<string, StopFraming>> = STOP_FRAMING,
  reach: number = FRAMING_REACH_FRAMES,
): LookOffset {
  let best: { h: { id: string; frame: number }; d: number } | null = null;
  for (const h of holds) {
    if (!table[h.id]) continue;
    const d = Math.abs(frame - h.frame);
    if (d < reach && (!best || d < best.d)) best = { h, d };
  }
  if (!best) return { yaw: 0, pitch: 0 };
  const t = table[best.h.id];
  const w = framingWeight(frame, best.h.frame, reach);
  const lim = (deg: number) => Math.max(-FRAMING_MAX_DEG, Math.min(FRAMING_MAX_DEG, deg)) * DEG * w;
  return { yaw: lim(t.yaw), pitch: lim(t.pitch) };
}
