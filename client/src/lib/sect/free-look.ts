/**
 * Free look: press and drag on the 3D view (or hold the left and right arrow keys) to turn the view
 * away from the flight path. The path still places the camera; a look offset (a yaw about world up
 * and a pitch about the camera's own right axis) is put on top of the path camera's orientation
 * every frame. When the path position changes (a scroll, a jump, the voice agent) the offset eases
 * back to zero the short way round, so each stop's authored framing returns; while the visitor holds
 * still it stays where they left it.
 *
 * The view turns all the way round: yaw wraps into (-180, 180] degrees. The baked world covers it.
 * The export (blender/xianxia-sect/sect/export_web.py `audit`) renders all-around views at each of
 * the eleven holds (8 compass directions at 5 tilts, plus straight down) and lighter ones every 48
 * path frames between them, so what lies behind or beside the path is exported and baked too, not
 * only what the flight camera faced. Those extra views count for less than the flight's own when
 * detail and texture space are shared out, so a turned view may be a little softer than the path's.
 * Streaming still plans by frame; looking back at rest on a desktop lets one more area load (the
 * one behind, lib/sect/chunks.ts `lookingBack`).
 *
 * Pitch keeps its limits: the tilt stops at 60 degrees either way, and the view itself never goes
 * past 80 degrees above or below the horizon. The path camera tilts too (from about 39 degrees
 * down, where it dives between the formation and the cave abode, to 20 up), and a view past
 * straight down would make a sideways drag spin the picture instead of panning it.
 *
 * Pure: plain numbers and quaternion arrays, no three.js, no DOM.
 */
import type { Quat } from "./types";

const DEG = Math.PI / 180;

export const FREE_LOOK = {
  /** Most the view tilts up or down from the path's own pitch (radians). */
  maxPitch: 60 * DEG,
  /** Most the view itself (path pitch plus tilt) points above or below the horizon (radians). */
  maxViewPitch: 80 * DEG,
  /** A mouse press that moves less than this (CSS px) stays a click. */
  mouseDragPx: 5,
  /** A finger moves a little on any tap, so a touch needs more before it turns the view. */
  touchDragPx: 10,
  /**
   * A finger turns this many times faster than a mouse. At 1:1 a half turn took about six swipes
   * across a phone; at 3 it takes two.
   */
  touchGain: 3,
  /** Turning speed while a left or right arrow key is held (radians per second). */
  keyTurnSpeed: 90 * DEG,
  /** Shortest swing back to the path's framing (seconds); small offsets take this long. */
  recenterSeconds: 0.6,
  /** Longest swing back (seconds), for a view turned right round. */
  recenterMaxSeconds: 1.4,
  /** The swing back takes this much longer per radian turned (seconds), between the two. */
  recenterSecondsPerRadian: 0.33,
  /** Turned further than this from the path's heading, the view looks back (radians). */
  lookBackYaw: 90 * DEG,
} as const;

export interface LookOffset {
  /** Radians about world up, in (-pi, pi]; positive turns the view left. */
  yaw: number;
  /** Radians about the camera's right axis; positive tilts the view up. */
  pitch: number;
}

/** The tilt limits (yaw has none: it wraps). */
export interface LookLimits {
  /** Most the tilt goes up; it goes down as far, unless `minPitch` says otherwise. */
  maxPitch: number;
  minPitch?: number;
}

/** Where the path is headed: a change in any of these is the visitor (or a jump) moving on. */
export interface PathAnchor {
  /** The scroll position the camera is heading for (scroll units). */
  targetU: number;
  /** Start time of the jump under way, or null. */
  flight: number | null;
  /** The ?frame=N view, or null. */
  override: number | null;
}

/** A pointer pressed on the view. */
export interface LookPress {
  id: number;
  touch: boolean;
  /** Where the press started, and the last position applied (CSS px). */
  x0: number;
  y0: number;
  x: number;
  y: number;
  /** Moved past the threshold: it turns the view and is not a click. */
  dragging: boolean;
}

/** A swing back to the path's framing: from this offset, since t0, over `duration` (seconds). */
export interface Recenter {
  from: LookOffset;
  t0: number;
  /** Grows with the angle (recenterDuration), so a half turn does not whip round. */
  duration: number;
}

export interface FreeLookState extends LookOffset {
  /** Swinging back to the path's framing, or null. */
  recenter: Recenter | null;
  press: LookPress | null;
  /** Arrow keys held down: the view turns left (positive yaw) or right while they are. */
  keys: { left: boolean; right: boolean };
  /** The press that just ended was a drag: the click the browser sends after it is not a pick. */
  swallowClick: boolean;
  /** The path position the current offset belongs to (null until the first frame). */
  anchor: PathAnchor | null;
  /** Limits for the path camera of the current frame (lookLimits; set every frame). */
  limits: LookLimits;
}

export function createFreeLook(): FreeLookState {
  return {
    yaw: 0,
    pitch: 0,
    recenter: null,
    press: null,
    keys: { left: false, right: false },
    swallowClick: false,
    anchor: null,
    limits: FREE_LOOK,
  };
}

function clamp(x: number, lo: number, hi: number): number {
  return x < lo ? lo : x > hi ? hi : x;
}

/** An angle (radians) brought into (-pi, pi]: the same direction, the short way from zero. */
export function wrapYaw(a: number): number {
  if (!Number.isFinite(a)) return 0;
  const t = 2 * Math.PI;
  const w = a - t * Math.floor((a + Math.PI) / t);
  // floor puts exactly pi at -pi; keep pi itself (a half turn to the left stays left).
  return w === -Math.PI ? Math.PI : w;
}

/** Yaw wraps all the way round; pitch stays inside its limits. */
export function clampLook(o: LookOffset, lim: LookLimits = FREE_LOOK): LookOffset {
  return { yaw: wrapYaw(o.yaw), pitch: clamp(o.pitch, lim.minPitch ?? -lim.maxPitch, lim.maxPitch) };
}

/** True while the view is turned more than `lookBackYaw` from the path's heading. */
export function isLookingBack(o: LookOffset): boolean {
  return Math.abs(wrapYaw(o.yaw)) > FREE_LOOK.lookBackYaw;
}

/** How far above (+) or below (-) the horizon the path camera `q` looks (radians). */
export function pathPitch(q: Quat): number {
  const [x, y, z, w] = q;
  // The y of q applied to the camera's forward (0, 0, -1).
  return Math.asin(clamp(2 * (w * x - y * z), -1, 1));
}

/**
 * The limits for a path camera `q`: the usual tilt, cut short where the view itself would pass
 * maxViewPitch above or below the horizon.
 */
export function lookLimits(q: Quat): LookLimits {
  const p = pathPitch(q);
  return {
    maxPitch: Math.max(0, Math.min(FREE_LOOK.maxPitch, FREE_LOOK.maxViewPitch - p)),
    minPitch: Math.min(0, Math.max(-FREE_LOOK.maxPitch, -FREE_LOOK.maxViewPitch - p)),
  };
}

/** True while the view is turned away from the path (by more than a hair). */
export function isTurned(o: LookOffset): boolean {
  return Math.abs(o.yaw) > 1e-5 || Math.abs(o.pitch) > 1e-5;
}

/**
 * Radians per CSS pixel dragged, so the scene stays under the pointer near the middle of the view
 * (the vertical field of view spread over the view's height).
 */
export function radiansPerPixel(fovYDeg: number, viewHeightPx: number): number {
  return (fovYDeg * DEG) / Math.max(viewHeightPx, 1);
}

/**
 * The offset after dragging (dx, dy) CSS px: the scene follows the pointer, so dragging right turns
 * the view left and dragging down tilts it up. `yawOnly` (touch): vertical swipes scroll the page,
 * so a finger only turns the view.
 */
export function dragLook(o: LookOffset, dx: number, dy: number, radPerPx: number, yawOnly = false, lim: LookLimits = FREE_LOOK): LookOffset {
  return clampLook({ yaw: o.yaw + dx * radPerPx, pitch: yawOnly ? o.pitch : o.pitch + dy * radPerPx }, lim);
}

/** A press that has moved this far from where it started is a drag, not a click. */
export function isDrag(dx: number, dy: number, thresholdPx: number): boolean {
  return dx * dx + dy * dy >= thresholdPx * thresholdPx;
}

/**
 * How long the swing back from offset `o` takes (seconds): recenterSeconds for small offsets, longer
 * for big ones, up to recenterMaxSeconds for a half turn. The ease (recenterFactor) peaks at 1.5
 * times the average speed, so a fixed 0.6 s for 180 degrees would peak near 450 degrees a second;
 * this keeps a half turn under about 200.
 */
export function recenterDuration(o: LookOffset): number {
  const angle = Math.hypot(wrapYaw(o.yaw), o.pitch);
  const s = 0.35 + angle * FREE_LOOK.recenterSecondsPerRadian;
  return clamp(s, FREE_LOOK.recenterSeconds, FREE_LOOK.recenterMaxSeconds);
}

/**
 * Share of the offset left `elapsed` seconds into a recentre (1 at the start, 0 when done; eased
 * both ends). Smoothstep: its fastest moment, halfway, is 1.5 times the average speed.
 */
export function recenterFactor(elapsed: number, duration: number = FREE_LOOK.recenterSeconds): number {
  if (!(duration > 0)) return 0;
  const t = clamp(elapsed / duration, 0, 1);
  return 1 - t * t * (3 - 2 * t);
}

export function samePathPosition(a: PathAnchor, b: PathAnchor, eps = 0.01): boolean {
  return Math.abs(a.targetU - b.targetU) <= eps && a.flight === b.flight && a.override === b.override;
}

// --- presses ------------------------------------------------------------------------------------

/** A pointer went down on the view. A second finger (a pinch) drops the press. */
export function pressDown(s: FreeLookState, id: number, x: number, y: number, touch: boolean): void {
  s.swallowClick = false;
  if (touch && s.press?.touch && s.press.id !== id) {
    s.press = null;
    return;
  }
  s.press = { id, touch, x0: x, y0: y, x, y, dragging: false };
}

/**
 * The pressed pointer moved. Returns "start" when the press just became a drag, "drag" while it
 * turns the view, null otherwise (no press, another pointer, or still under the threshold). A touch
 * becomes a drag only when it moves more sideways than up or down (the browser scrolls the rest).
 */
export function pressMove(s: FreeLookState, id: number, x: number, y: number, radPerPx: number): "start" | "drag" | null {
  const p = s.press;
  if (!p || p.id !== id) return null;
  let started = false;
  if (!p.dragging) {
    const dx = x - p.x0;
    const dy = y - p.y0;
    if (!isDrag(dx, dy, p.touch ? FREE_LOOK.touchDragPx : FREE_LOOK.mouseDragPx)) return null;
    if (p.touch && Math.abs(dy) > Math.abs(dx)) return null;
    p.dragging = true;
    started = true;
    // Grabbing the view stops a recentre where it is.
    s.recenter = null;
  }
  // A finger turns faster (touchGain), so a half turn does not take a handful of swipes.
  const o = dragLook(s, x - p.x, y - p.y, p.touch ? radPerPx * FREE_LOOK.touchGain : radPerPx, p.touch, s.limits);
  s.yaw = o.yaw;
  s.pitch = o.pitch;
  p.x = x;
  p.y = y;
  return started ? "start" : "drag";
}

/** The pressed pointer came up. Returns true when it was a drag (its click is then swallowed). */
export function pressUp(s: FreeLookState, id: number): boolean {
  const p = s.press;
  if (!p || p.id !== id) return false;
  s.press = null;
  s.swallowClick = p.dragging;
  return p.dragging;
}

/** The browser took the gesture (a vertical swipe scrolls the page) or the pointer was lost. */
export function pressCancel(s: FreeLookState, id: number): void {
  if (s.press?.id === id) s.press = null;
}

/** A click reached the view: true when it ends a drag and must not pick (the flag is used up). */
export function takeClick(s: FreeLookState): boolean {
  const swallow = s.swallowClick;
  s.swallowClick = false;
  return swallow;
}

export function isDragging(s: FreeLookState): boolean {
  return s.press?.dragging === true;
}

// --- arrow keys ---------------------------------------------------------------------------------

/** Which way the held arrow keys turn the view: 1 left, -1 right, 0 none (or both). */
export function keyTurnDirection(s: FreeLookState): number {
  return (s.keys.left ? 1 : 0) - (s.keys.right ? 1 : 0);
}

/** An arrow key went down (`down`) or up. 1 is the left arrow, -1 the right one. */
export function setTurnKey(s: FreeLookState, dir: 1 | -1, down: boolean): void {
  if (dir > 0) s.keys.left = down;
  else s.keys.right = down;
}

/** The window lost focus: a key held then never sends its keyup here. */
export function releaseTurnKeys(s: FreeLookState): void {
  s.keys.left = false;
  s.keys.right = false;
}

/**
 * Once per frame: turns the view while an arrow key is held, `dt` seconds' worth (at most 0.1, so a
 * stalled frame does not jump). Like a drag, it stops a recentre where it is. Returns true when the
 * view turned.
 */
export function turnByKeys(s: FreeLookState, dt: number): boolean {
  const dir = keyTurnDirection(s);
  if (dir === 0 || !(dt > 0)) return false;
  s.recenter = null;
  s.yaw = wrapYaw(s.yaw + dir * FREE_LOOK.keyTurnSpeed * Math.min(dt, 0.1));
  return true;
}

/**
 * The view is being turned: a drag, a held arrow key or a swing back to the path. Texture uploads
 * and other heavy work wait for it (a stall mid-turn shows as a jerk).
 */
export function isTurning(s: FreeLookState): boolean {
  return isDragging(s) || s.recenter !== null || keyTurnDirection(s) !== 0;
}

// --- following the path -------------------------------------------------------------------------

/**
 * Swing the view back to the path's framing from now (seconds), or at once with `snap` (reduced
 * motion). Returns false when there was nothing to recentre.
 */
export function startRecenter(s: FreeLookState, now: number, snap: boolean): boolean {
  if (!isTurned(s)) {
    s.recenter = null;
    return false;
  }
  if (snap) {
    s.yaw = 0;
    s.pitch = 0;
    s.recenter = null;
    return true;
  }
  // Yaw is kept in (-pi, pi], so easing it to zero takes the short way round.
  const from = { yaw: wrapYaw(s.yaw), pitch: s.pitch };
  s.recenter = { from, t0: now, duration: recenterDuration(from) };
  return true;
}

/**
 * Once per frame, before the offset is applied: a new path position starts a recentre (not while a
 * drag or a held arrow key holds the view: it adopts the new position), and a recentre under way
 * advances (a scroll that goes on does not restart it). Returns true when a recentre has just
 * started.
 */
export function followPath(s: FreeLookState, at: PathAnchor, now: number, snap: boolean): boolean {
  let started = false;
  if (!s.anchor || isDragging(s) || keyTurnDirection(s) !== 0) s.anchor = { ...at };
  else if (!samePathPosition(s.anchor, at)) {
    s.anchor = { ...at };
    if (!s.recenter) started = startRecenter(s, now, snap);
  }
  const r = s.recenter;
  if (r) {
    const k = snap ? 0 : recenterFactor(now - r.t0, r.duration);
    s.yaw = k === 0 ? 0 : r.from.yaw * k;
    s.pitch = k === 0 ? 0 : r.from.pitch * k;
    if (k === 0) s.recenter = null;
  }
  return started;
}

// --- orientation --------------------------------------------------------------------------------

function mul(a: Quat, b: Quat): Quat {
  const [ax, ay, az, aw] = a;
  const [bx, by, bz, bw] = b;
  return [
    aw * bx + ax * bw + ay * bz - az * by,
    aw * by - ax * bz + ay * bw + az * bx,
    aw * bz + ax * by - ay * bx + az * bw,
    aw * bw - ax * bx - ay * by - az * bz,
  ];
}

/**
 * The path camera's orientation `q` (x, y, z, w; three.js camera: looks down local -Z, up +Y)
 * turned by the offset: yaw about world up (so turning sweeps along the horizon even when the path
 * camera looks down a stairway), then pitch about the camera's own right axis.
 */
export function composeLook(q: Quat, o: LookOffset): Quat {
  if (!isTurned(o)) return [q[0], q[1], q[2], q[3]];
  const yaw: Quat = [0, Math.sin(o.yaw / 2), 0, Math.cos(o.yaw / 2)];
  const pitch: Quat = [Math.sin(o.pitch / 2), 0, 0, Math.cos(o.pitch / 2)];
  return mul(mul(yaw, q), pitch);
}

/**
 * The view's cursor: the pointer over a hotspot, grabbing while a drag turns the view, else empty
 * (the canvas then shows its own `grab` cursor).
 */
export function lookCursor(overHotspot: boolean, dragging: boolean): string {
  return dragging ? "grabbing" : overHotspot ? "pointer" : "";
}
