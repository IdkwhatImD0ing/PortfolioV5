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
 * way after it (or over the stop's own reach after it), along a smoothstep, so their rate is zero at
 * both ends and at the hold itself. The flight stays smooth (no jerk where it starts or ends, and the
 * scroll's own easing into the hold slows it further); a jump flies through the same frames, so it
 * eases in the same way; with reduced motion the camera steps from stop to stop and lands on the
 * framed view at once, with no motion of its own; and the view between stops is the film's own,
 * except where one framed stop hands its framing on to the next (the jade slip to the formation):
 * there the one fades out over the very frames the other fades in, and the two add up, so the view
 * passes from one stop's framing to the next's along the same smoothstep (S(x) + S(1 - x) = 1).
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
 * up), how far back along the path the camera stands at the hold, in frames (none when absent), how
 * far back on a portrait screen when its narrower view needs more room (`back` when absent;
 * PORTRAIT_STOP_FRAMING), and over how many frames before and after the hold the framing comes and
 * goes: one number for both sides, or [before, after] (FRAMING_REACH_FRAMES when absent; never fewer).
 */
export interface StopFraming {
  yaw: number;
  pitch: number;
  back?: number;
  portraitBack?: number;
  reach?: number | readonly [number, number];
}

/** Most a stop's framing may turn the view, either way (degrees). */
export const FRAMING_MAX_DEG = 8;

/**
 * Most a stop's framing may pull the camera back along the path (frames). The camera's pace along the
 * path is 1 - 1.5 back / reach on the way in and 1 + 1.5 back / reach on the way out (framingFrame),
 * so each stop keeps its back to a third of its reach on either side: the pace then stays between half
 * and one and a half times the film's own (framing.test.ts checks every stop, portrait screens too).
 */
export const FRAMING_MAX_BACK = 24;

/**
 * Frames before and after a hold over which its framing comes and goes, unless the stop sets a longer
 * reach. Stops are at least 103 frames apart (the arena at 516, the mission hall at 619), so two never
 * overlap (a longer reach is kept to the room its neighbours leave: the mirror's 80 lies between the
 * gate at 93 and the forge at 352, neither framed), except for a hand-over, where one stop's reach
 * after its hold and the next one's before it both run the whole way between them (the jade slip's
 * 105 after 1103 and the formation's 105 before 1208); and the poster's start view (frame 27,
 * opening.ts POSTER) is 66 frames before the first stop, out of reach. At the steepest an 8 degree
 * turn adds 0.25 degrees a frame to the film's own turning (up to about 1 a frame round the framed
 * stops).
 */
export const FRAMING_REACH_FRAMES = 48;

/**
 * The stops that need framing, by hold id, chosen on the hold frames at 16:9 (1600 x 900, the panel
 * up; framing.test.ts checks the numbers). Stops not listed keep the film's framing: the gate, the
 * forge, the arena, the library, the stele forest, the abode and the summit are balanced as they are.
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
 * - scroll: the jade slip stood big and close on the left, its left part past the edge and its stand
 *   cut by the bottom, the pavilion right of it ("too in my face", the owner, 2026-10-23, who wants the
 *   slip whole and the pavilion beside it; before that he turned down the slip turned 40 degrees to fit
 *   and a slip shrunk and stood back to fit, as too small with its posts cut). The slip stays where it
 *   first stood (blender scroll.py); the camera stands back and turns 8 left and 2.5 down. At first it
 *   stood back 9 frames (44 m from the slip), the slip's rolled end 7 px from the left edge; the owner
 *   found that "too far forward, maybe slightly back" (2026-10-24), so it stands back 12 (14 m, the
 *   film's pose at 1091, 48 m from the slip and square to it): the whole slip on the left with room
 *   round it (its end 111 px in from the left edge at 1600 x 900), its stand on the paving and its sun
 *   and moon in, the slips 272 px tall (the verses about 14 px a character; 299 from 9 frames back),
 *   the pavilion whole on its right, its finial left of the panel and its left eave tips just behind
 *   the slip's end. Out of the stop the film turns right and up the stair at a degree a frame, and
 *   turning back from the framing (and catching up the frames stood back) over the 48 frames to 1151
 *   would add half as much again (over 1.4 degrees a frame, also over all the 57 the formation's reach
 *   leaves). So the framing hands over to the formation's instead: it fades over the 105 frames to
 *   1208 while the formation's fades in, the tilt down passing on into the formation's own, and the
 *   view turns at most 1.17 degrees a frame (1.13 from 9 frames back), about as round the mirror
 *   (1.10). It comes in over 76 frames, where the film turns slowly: a stop's back is kept to a third
 *   of its reach (FRAMING_MAX_BACK), and a portrait screen stands back 24. A portrait phone sees 36
 *   degrees across, and from 48 m the slip and the pavilion together are still wider than that; there
 *   the camera stands 24 frames back (34 m, the film's pose at 1079, 67 m from the slip), the slip and
 *   the pavilion side by side across the phone (opening.ts PORTRAIT_TURN_DEG tilts them between the
 *   labels and the panel), the slips about 82 px tall on a 390 x 844 phone (89 from 21 frames back).
 *   Catching up the 24 frames makes the way out turn up to 1.35 degrees a frame on portrait screens.
 * - formation: the plaza sat on the bottom edge, its front stations and gate cut off, under the next
 *   stop's mountain. Down: the whole array, armillary, flags and gate in, the mountain behind. It comes
 *   in over the 105 frames from the jade slip (see scroll), and goes over the default 48.
 */
export const STOP_FRAMING: Readonly<Record<string, StopFraming>> = {
  mirror: { yaw: 4, pitch: -3, back: 13, reach: 80 },
  mission: { yaw: 8, pitch: 2 },
  scroll: { yaw: 8, pitch: -2.5, back: 12, portraitBack: 24, reach: [76, 105] },
  formation: { yaw: 0, pitch: -8, reach: [105, FRAMING_REACH_FRAMES] },
};

/**
 * STOP_FRAMING on a portrait screen: each stop stands back its `portraitBack` where it sets one, its
 * `back` elsewhere; the turns are the same on every screen.
 */
export const PORTRAIT_STOP_FRAMING: Readonly<Record<string, StopFraming>> = Object.fromEntries(
  Object.entries(STOP_FRAMING).map(([id, t]) => [id, t.portraitBack === undefined ? t : { ...t, back: t.portraitBack }]),
);

/** The framing for a screen `width` x `height`: PORTRAIT_STOP_FRAMING when it is taller than wide. */
export function framingTable(width: number, height: number): Readonly<Record<string, StopFraming>> {
  return height > width ? PORTRAIT_STOP_FRAMING : STOP_FRAMING;
}

/**
 * A stop's own reach (frames) before and after its hold: its `reach` (one number for both sides),
 * never less than `reach` (the default).
 */
export function framingReach(t: StopFraming, reach: number = FRAMING_REACH_FRAMES): readonly [number, number] {
  const r = t.reach ?? reach;
  const [before, after] = typeof r === "number" ? [r, r] : r;
  return [Math.max(reach, before), Math.max(reach, after)];
}

/**
 * 0 `reach` frames or more from the hold, 1 at it, eased (smoothstep) between: zero slope at both ends.
 * `reach` is one number for both sides, or [before, after].
 */
export function framingWeight(
  frame: number,
  holdFrame: number,
  reach: number | readonly [number, number] = FRAMING_REACH_FRAMES,
): number {
  const r = typeof reach === "number" ? reach : frame < holdFrame ? reach[0] : reach[1];
  if (!Number.isFinite(frame) || !(r > 0)) return 0;
  const x = 1 - Math.abs(frame - holdFrame) / r;
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  return x * x * (3 - 2 * x);
}

/** The listed holds `frame` is within the reach of, with their framings and weights. */
function framedHolds(
  holds: readonly { id: string; frame: number }[],
  frame: number,
  table: Readonly<Record<string, StopFraming>>,
  reach: number,
): { t: StopFraming; w: number }[] {
  const out: { t: StopFraming; w: number }[] = [];
  for (const h of holds) {
    const t = table[h.id];
    if (!t) continue;
    const w = framingWeight(frame, h.frame, framingReach(t, reach));
    if (w > 0) out.push({ t, w });
  }
  return out;
}

/**
 * The framing turn (radians, as a free-look offset) at path frame `frame`: each listed hold's turn
 * times its weight (over the stop's own reach), added up (only a hand-over has two at once, their
 * weights adding up to 1). Each turn is held to FRAMING_MAX_DEG.
 */
export function framingAt(
  holds: readonly { id: string; frame: number }[],
  frame: number,
  table: Readonly<Record<string, StopFraming>> = STOP_FRAMING,
  reach: number = FRAMING_REACH_FRAMES,
): LookOffset {
  const lim = (deg: number) => Math.max(-FRAMING_MAX_DEG, Math.min(FRAMING_MAX_DEG, deg)) * DEG;
  let yaw = 0;
  let pitch = 0;
  for (const { t, w } of framedHolds(holds, frame, table, reach)) {
    yaw += lim(t.yaw) * w;
    pitch += lim(t.pitch) * w;
  }
  return { yaw, pitch };
}

/**
 * The path frame whose pose the camera takes (position and orientation, before the turn) at path
 * frame `frame`: each listed hold's `back` (held to FRAMING_MAX_BACK) times its weight earlier. The
 * frame itself away from the framed stops; at such a hold, the film's pose `back` frames before it.
 * The camera never stops or turns back: its pace along the path is 1 - back times the weight's slope,
 * from 1 - 1.5 back / reach on the way in to 1 + 1.5 back / reach on the way out (the stop's own
 * reach on that side), and the film's own at the hold and outside the reach.
 */
export function framingFrame(
  holds: readonly { id: string; frame: number }[],
  frame: number,
  table: Readonly<Record<string, StopFraming>> = STOP_FRAMING,
  reach: number = FRAMING_REACH_FRAMES,
): number {
  let f = frame;
  for (const { t, w } of framedHolds(holds, frame, table, reach)) f -= Math.max(0, Math.min(FRAMING_MAX_BACK, t.back ?? 0)) * w;
  return f;
}
