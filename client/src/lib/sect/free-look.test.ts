import { describe, expect, it } from "vitest";
import { forward, rotate } from "./camera-path";
import {
  clampLook,
  composeLook,
  createFreeLook,
  dragLook,
  followPath,
  FREE_LOOK,
  isDrag,
  isDragging,
  isLookingBack,
  isTurning,
  keyTurnDirection,
  lookCursor,
  lookLimits,
  pathPitch,
  pressCancel,
  pressDown,
  pressMove,
  pressUp,
  radiansPerPixel,
  recenterDuration,
  recenterFactor,
  releaseTurnKeys,
  setTurnKey,
  startRecenter,
  takeClick,
  turnByKeys,
  wrapYaw,
  type PathAnchor,
} from "./free-look";
import type { Quat, Vec3 } from "./types";

const DEG = Math.PI / 180;
const at = (targetU: number, flight: number | null = null, override: number | null = null): PathAnchor => ({ targetU, flight, override });
const close = (a: readonly number[], b: readonly number[], digits = 6) => a.forEach((v, i) => expect(v).toBeCloseTo(b[i], digits));
/** Rotation of `a` radians about the unit axis (x, y, z). */
const axisAngle = (x: number, y: number, z: number, a: number): Quat => [x * Math.sin(a / 2), y * Math.sin(a / 2), z * Math.sin(a / 2), Math.cos(a / 2)];
/** The rotation `b` then `a` (Hamilton product a * b). */
const mulQ = ([ax, ay, az, aw]: Quat, [bx, by, bz, bw]: Quat): Quat => [
  aw * bx + ax * bw + ay * bz - az * by,
  aw * by - ax * bz + ay * bw + az * bx,
  aw * bz + ax * by - ay * bx + az * bw,
  aw * bw - ax * bx - ay * by - az * bz,
];

describe("limits and dragging", () => {
  it("wraps yaw all the way round and clamps pitch to the limits", () => {
    const o = clampLook({ yaw: 3, pitch: -3 });
    expect(o.yaw).toBe(3);
    expect(o.pitch).toBe(-FREE_LOOK.maxPitch);
    expect(clampLook({ yaw: 0.1, pitch: 0.2 })).toEqual({ yaw: 0.1, pitch: 0.2 });
    // Past a half turn it comes round the other side.
    expect(clampLook({ yaw: 200 * DEG, pitch: 0 }).yaw).toBeCloseTo(-160 * DEG, 9);
    expect(clampLook({ yaw: -200 * DEG, pitch: 0 }).yaw).toBeCloseTo(160 * DEG, 9);
  });

  it("wrapYaw keeps every angle in (-180, 180] degrees", () => {
    expect(wrapYaw(0)).toBe(0);
    expect(wrapYaw(Math.PI)).toBeCloseTo(Math.PI, 12);
    expect(wrapYaw(-Math.PI)).toBeCloseTo(Math.PI, 12);
    expect(wrapYaw(3 * Math.PI)).toBeCloseTo(Math.PI, 9);
    expect(wrapYaw(720 * DEG + 0.25)).toBeCloseTo(0.25, 9);
    expect(wrapYaw(-370 * DEG)).toBeCloseTo(-10 * DEG, 9);
    expect(wrapYaw(NaN)).toBe(0);
    for (let a = -20; a <= 20; a += 0.37) {
      const w = wrapYaw(a);
      expect(w).toBeGreaterThan(-Math.PI);
      expect(w).toBeLessThanOrEqual(Math.PI);
      expect(Math.cos(w)).toBeCloseTo(Math.cos(a), 9);
      expect(Math.sin(w)).toBeCloseTo(Math.sin(a), 9);
    }
  });

  it("looks back past 90 degrees either way", () => {
    expect(isLookingBack({ yaw: 80 * DEG, pitch: 0 })).toBe(false);
    expect(isLookingBack({ yaw: 100 * DEG, pitch: 0 })).toBe(true);
    expect(isLookingBack({ yaw: -170 * DEG, pitch: 0 })).toBe(true);
    expect(isLookingBack({ yaw: 350 * DEG, pitch: 0 })).toBe(false);
  });

  it("drags past 180 degrees without a stop: from 170 by +20 is -170", () => {
    const k = 0.002;
    const o = dragLook({ yaw: 170 * DEG, pitch: 0 }, (20 * DEG) / k, 0, k);
    expect(o.yaw).toBeCloseTo(-170 * DEG, 9);
    // Two full turns of dragging end where they began.
    expect(dragLook({ yaw: 0.3, pitch: 0 }, (4 * Math.PI) / k, 0, k).yaw).toBeCloseTo(0.3, 6);
  });

  it("keeps the view's direction continuous across the half turn", () => {
    const path = mulQ(axisAngle(0, 1, 0, 0.4), axisAngle(1, 0, 0, -10 * DEG));
    const before = forward(composeLook(path, { yaw: 179.9 * DEG, pitch: 0.1 }));
    const wrapped = wrapYaw(180.1 * DEG);
    expect(wrapped).toBeLessThan(0);
    const after = forward(composeLook(path, { yaw: wrapped, pitch: 0.1 }));
    // 0.2 degrees apart, not a jump.
    expect(Math.hypot(before[0] - after[0], before[1] - after[1], before[2] - after[2])).toBeLessThan(0.005);
  });

  it("turns so the scene follows the pointer, and touch only turns", () => {
    const k = radiansPerPixel(36, 720);
    expect(k).toBeCloseTo((36 * DEG) / 720, 9);
    // Right turns the view left (positive yaw), down tilts it up.
    const o = dragLook({ yaw: 0, pitch: 0 }, 100, 50, k);
    expect(o.yaw).toBeCloseTo(100 * k, 9);
    expect(o.pitch).toBeCloseTo(50 * k, 9);
    expect(dragLook({ yaw: 0, pitch: 0.1 }, 100, 50, k, true).pitch).toBe(0.1);
    // No stop sideways any more: a long drag just keeps turning (and wraps).
    expect(dragLook({ yaw: 0, pitch: 0 }, 1e5, 0, k).yaw).toBeCloseTo(wrapYaw(1e5 * k), 9);
  });

  it("never tips the view itself past 80 degrees above or below the horizon", () => {
    // A path camera that looks 40 degrees down (the dive between the formation and the abode).
    const down = mulQ(axisAngle(0, 1, 0, 0.6), axisAngle(1, 0, 0, -40 * DEG));
    expect(pathPitch(down)).toBeCloseTo(-40 * DEG, 6);
    expect(Math.asin(forward(down)[1])).toBeCloseTo(-40 * DEG, 6);
    const lim = lookLimits(down);
    expect(lim.maxPitch).toBeCloseTo(FREE_LOOK.maxPitch, 9);
    expect(lim.minPitch).toBeCloseTo(-40 * DEG, 6);
    const o = clampLook({ yaw: 0, pitch: -3 }, lim);
    expect(Math.asin(forward(composeLook(down, o))[1])).toBeCloseTo(-80 * DEG, 6);
    // A drag stops there too.
    const s = createFreeLook();
    s.limits = lim;
    pressDown(s, 1, 0, 0, false);
    pressMove(s, 1, 0, -1e5, radiansPerPixel(36, 720));
    expect(s.pitch).toBeCloseTo(-40 * DEG, 6);
    // A level path camera keeps the usual tilt both ways.
    const level = lookLimits([0, 0, 0, 1]);
    expect(level.maxPitch).toBeCloseTo(FREE_LOOK.maxPitch, 9);
    expect(level.minPitch).toBeCloseTo(-FREE_LOOK.maxPitch, 9);
  });

  it("tells a click from a drag", () => {
    expect(isDrag(3, 3, 5)).toBe(false);
    expect(isDrag(4, 3, 5)).toBe(true);
  });
});

describe("presses", () => {
  const k = 0.002;

  it("keeps a small mouse movement a click", () => {
    const s = createFreeLook();
    pressDown(s, 1, 100, 100, false);
    expect(pressMove(s, 1, 103, 102, k)).toBeNull();
    expect(pressUp(s, 1)).toBe(false);
    expect(takeClick(s)).toBe(false);
    expect(s.yaw).toBe(0);
  });

  it("turns after the threshold, from the threshold on, and swallows the click that follows", () => {
    const s = createFreeLook();
    pressDown(s, 1, 100, 100, false);
    expect(pressMove(s, 1, 110, 100, k)).toBe("start");
    expect(isDragging(s)).toBe(true);
    // The first move applies the whole distance from the press (no jump later).
    expect(s.yaw).toBeCloseTo(10 * k, 9);
    expect(pressMove(s, 1, 130, 90, k)).toBe("drag");
    expect(s.yaw).toBeCloseTo(30 * k, 9);
    expect(s.pitch).toBeCloseTo(-10 * k, 9);
    expect(pressUp(s, 1)).toBe(true);
    expect(takeClick(s)).toBe(true);
    // Used up: the next click picks again.
    expect(takeClick(s)).toBe(false);
  });

  it("clears a stale swallow flag on the next press", () => {
    const s = createFreeLook();
    pressDown(s, 1, 0, 0, false);
    pressMove(s, 1, 50, 0, k);
    pressUp(s, 1);
    pressDown(s, 2, 0, 0, false);
    pressUp(s, 2);
    expect(takeClick(s)).toBe(false);
  });

  it("ignores other pointers", () => {
    const s = createFreeLook();
    pressDown(s, 1, 0, 0, false);
    expect(pressMove(s, 2, 50, 0, k)).toBeNull();
    expect(pressUp(s, 2)).toBe(false);
    expect(s.press).not.toBeNull();
  });

  it("touch: a sideways swipe turns (yaw only); an up-down swipe is left to the page", () => {
    const s = createFreeLook();
    pressDown(s, 1, 100, 100, true);
    // Under the touch threshold.
    expect(pressMove(s, 1, 107, 100, k)).toBeNull();
    expect(pressMove(s, 1, 120, 105, k)).toBe("start");
    // A finger turns touchGain times as fast as a mouse.
    expect(s.yaw).toBeCloseTo(20 * k * FREE_LOOK.touchGain, 9);
    expect(s.pitch).toBe(0);

    const v = createFreeLook();
    pressDown(v, 1, 100, 100, true);
    expect(pressMove(v, 1, 104, 140, k)).toBeNull();
    // The browser takes the scroll and cancels the pointer.
    pressCancel(v, 1);
    expect(v.press).toBeNull();
    expect(v.yaw).toBe(0);
  });

  it("touch: a second finger (a pinch) drops the press", () => {
    const s = createFreeLook();
    pressDown(s, 1, 100, 100, true);
    pressDown(s, 2, 200, 100, true);
    expect(s.press).toBeNull();
    expect(pressMove(s, 1, 150, 100, k)).toBeNull();
  });
});

describe("following the path", () => {
  it("keeps the offset while the path holds still", () => {
    const s = createFreeLook();
    followPath(s, at(10), 0, false);
    s.yaw = 0.3;
    for (let t = 0; t < 5; t += 0.5) followPath(s, at(10), t, false);
    expect(s.yaw).toBe(0.3);
  });

  it("eases back to zero over the recentre time once the path moves", () => {
    const s = createFreeLook();
    followPath(s, at(10), 0, false);
    s.yaw = 0.4;
    s.pitch = -0.2;
    expect(followPath(s, at(12), 1, false)).toBe(true);
    expect(s.yaw).toBeCloseTo(0.4, 9);
    // A small offset takes the shortest swing.
    expect(s.recenter?.duration).toBe(FREE_LOOK.recenterSeconds);
    followPath(s, at(14), 1 + FREE_LOOK.recenterSeconds / 2, false);
    expect(s.yaw).toBeCloseTo(0.2, 9);
    expect(s.pitch).toBeCloseTo(-0.1, 9);
    followPath(s, at(16), 1 + FREE_LOOK.recenterSeconds, false);
    expect(s.yaw).toBe(0);
    expect(s.pitch).toBe(0);
    expect(s.recenter).toBeNull();
  });

  it("recentres on a jump and on a ?frame view change too", () => {
    const s = createFreeLook();
    followPath(s, at(10), 0, false);
    s.yaw = 0.4;
    expect(followPath(s, at(10, 123), 1, false)).toBe(true);
    s.recenter = null;
    s.yaw = 0.4;
    expect(followPath(s, at(10, 123, 50), 2, false)).toBe(true);
  });

  it("snaps with reduced motion", () => {
    const s = createFreeLook();
    followPath(s, at(10), 0, true);
    s.yaw = 0.4;
    followPath(s, at(30), 1, true);
    expect(s.yaw).toBe(0);
  });

  it("a drag holds the view and adopts the new path position (no recentre after it)", () => {
    const s = createFreeLook();
    followPath(s, at(10), 0, false);
    pressDown(s, 1, 0, 0, false);
    pressMove(s, 1, 100, 0, 0.002);
    followPath(s, at(20), 1, false);
    expect(s.yaw).toBeCloseTo(0.2, 9);
    pressUp(s, 1);
    expect(followPath(s, at(20), 2, false)).toBe(false);
    expect(s.yaw).toBeCloseTo(0.2, 9);
  });

  it("grabbing stops a recentre where it is", () => {
    const s = createFreeLook();
    followPath(s, at(10), 0, false);
    s.yaw = 0.4;
    followPath(s, at(20), 1, false);
    followPath(s, at(20), 1 + FREE_LOOK.recenterSeconds / 2, false);
    pressDown(s, 1, 0, 0, false);
    pressMove(s, 1, 10, 0, 0.002);
    expect(s.recenter).toBeNull();
    expect(s.yaw).toBeCloseTo(0.2 + 0.02, 9);
  });

  it("swings back the short way round: from -170 degrees, halfway at -85", () => {
    const s = createFreeLook();
    followPath(s, at(10), 0, false);
    pressDown(s, 1, 0, 0, false);
    const k = 0.002;
    pressMove(s, 1, (170 * DEG) / k, 0, k);
    pressMove(s, 1, (190 * DEG) / k, 0, k);
    pressUp(s, 1);
    expect(s.yaw).toBeCloseTo(-170 * DEG, 6);
    expect(followPath(s, at(20), 5, false)).toBe(true);
    const d = s.recenter!.duration;
    followPath(s, at(20), 5 + d / 2, false);
    expect(s.yaw).toBeCloseTo(-85 * DEG, 6);
    // Never through +90 (the long way round would pass it).
    for (let t = 5; t <= 5 + d; t += d / 20) {
      followPath(s, at(20), t, false);
      expect(s.yaw).toBeLessThanOrEqual(1e-9);
    }
    followPath(s, at(20), 5 + d, false);
    expect(s.yaw).toBe(0);
    expect(s.recenter).toBeNull();
  });

  it("takes longer to swing back the further the view is turned", () => {
    expect(recenterDuration({ yaw: 0.2, pitch: 0 })).toBe(FREE_LOOK.recenterSeconds);
    const quarter = recenterDuration({ yaw: 90 * DEG, pitch: 0 });
    const half = recenterDuration({ yaw: 180 * DEG, pitch: 0 });
    expect(quarter).toBeGreaterThan(FREE_LOOK.recenterSeconds);
    expect(half).toBeGreaterThan(quarter);
    expect(half).toBeLessThanOrEqual(FREE_LOOK.recenterMaxSeconds);
    // The same angle either way, and a turn past 180 counts as the short way.
    expect(recenterDuration({ yaw: -90 * DEG, pitch: 0 })).toBe(quarter);
    expect(recenterDuration({ yaw: 270 * DEG, pitch: 0 })).toBeCloseTo(quarter, 9);
    // The fastest moment of a half-turn swing stays under 220 degrees a second, measured on the
    // ease itself.
    const h = half / 1000;
    let peak = 0;
    for (let t = 0; t + h <= half; t += h) peak = Math.max(peak, (Math.abs(recenterFactor(t + h, half) - recenterFactor(t, half)) / h) * 180);
    expect(peak).toBeGreaterThan(180 / half);
    expect(peak).toBeLessThan(220);
    // Escape stores it on the swing.
    const s = createFreeLook();
    s.yaw = 180 * DEG;
    startRecenter(s, 0, false);
    expect(s.recenter?.duration).toBe(half);
  });

  it("Escape-style recentre: nothing to do at zero, eases otherwise", () => {
    const s = createFreeLook();
    expect(startRecenter(s, 0, false)).toBe(false);
    s.pitch = 0.3;
    expect(startRecenter(s, 0, false)).toBe(true);
    expect(s.recenter?.from).toEqual({ yaw: 0, pitch: 0.3 });
  });

  it("snaps the swing back with reduced motion, even from a half turn", () => {
    const s = createFreeLook();
    s.yaw = Math.PI;
    expect(startRecenter(s, 0, true)).toBe(true);
    expect(s.yaw).toBe(0);
    expect(s.recenter).toBeNull();
  });

  it("eases in and out", () => {
    expect(recenterFactor(0)).toBe(1);
    expect(recenterFactor(FREE_LOOK.recenterSeconds / 2)).toBeCloseTo(0.5, 9);
    expect(recenterFactor(10)).toBe(0);
    expect(recenterFactor(0.05)).toBeGreaterThan(0.97);
    expect(recenterFactor(1, 0)).toBe(0);
  });
});

describe("arrow keys", () => {
  it("turn the view while held, left positive, and wrap past 180", () => {
    const s = createFreeLook();
    expect(turnByKeys(s, 0.016)).toBe(false);
    setTurnKey(s, 1, true);
    expect(keyTurnDirection(s)).toBe(1);
    expect(isTurning(s)).toBe(true);
    expect(turnByKeys(s, 0.5)).toBe(true);
    // A long frame counts as at most 0.1 s.
    expect(s.yaw).toBeCloseTo(FREE_LOOK.keyTurnSpeed * 0.1, 9);
    for (let i = 0; i < 25; i++) turnByKeys(s, 0.1);
    expect(s.yaw).toBeCloseTo(wrapYaw(26 * 0.1 * FREE_LOOK.keyTurnSpeed), 9);
    expect(s.yaw).toBeLessThan(0);
    setTurnKey(s, 1, false);
    expect(isTurning(s)).toBe(false);
    setTurnKey(s, -1, true);
    const y = s.yaw;
    turnByKeys(s, 0.05);
    expect(s.yaw).toBeCloseTo(y - FREE_LOOK.keyTurnSpeed * 0.05, 9);
  });

  it("both arrows held cancel out; losing focus lets go of both", () => {
    const s = createFreeLook();
    setTurnKey(s, 1, true);
    setTurnKey(s, -1, true);
    expect(keyTurnDirection(s)).toBe(0);
    expect(turnByKeys(s, 0.05)).toBe(false);
    setTurnKey(s, 1, true);
    releaseTurnKeys(s);
    expect(keyTurnDirection(s)).toBe(0);
    expect(s.keys).toEqual({ left: false, right: false });
  });

  it("stop a swing back where it is, and hold the view through a scroll", () => {
    const s = createFreeLook();
    followPath(s, at(10), 0, false);
    s.yaw = 1;
    followPath(s, at(20), 1, false);
    expect(s.recenter).not.toBeNull();
    setTurnKey(s, -1, true);
    turnByKeys(s, 0.05);
    expect(s.recenter).toBeNull();
    const y = s.yaw;
    expect(followPath(s, at(30), 2, false)).toBe(false);
    expect(s.yaw).toBe(y);
    // Let go: the view stays, and the next scroll swings it back.
    setTurnKey(s, -1, false);
    expect(followPath(s, at(30), 3, false)).toBe(false);
    expect(followPath(s, at(40), 4, false)).toBe(true);
  });
});

describe("composeLook", () => {
  // A path camera heading north-east, looking 10 degrees down.
  const path = mulQ(axisAngle(0, 1, 0, -45 * DEG), axisAngle(1, 0, 0, -10 * DEG));
  const heading = (v: Vec3) => Math.atan2(-v[0], -v[2]);
  const elevation = (v: Vec3) => Math.asin(v[1]);

  it("is the path's orientation at zero", () => {
    close(composeLook(path, { yaw: 0, pitch: 0 }), path);
  });

  it("yaw turns about world up: the heading changes, the elevation does not", () => {
    const f0 = forward(path);
    const f = forward(composeLook(path, { yaw: 30 * DEG, pitch: 0 }));
    expect(heading(f) - heading(f0)).toBeCloseTo(30 * DEG, 6);
    expect(elevation(f)).toBeCloseTo(elevation(f0), 6);
  });

  it("pitch tilts about the camera's right axis: the heading stays, the right axis stays level", () => {
    const f0 = forward(path);
    const q = composeLook(path, { yaw: 0, pitch: 20 * DEG });
    const f = forward(q);
    expect(heading(f)).toBeCloseTo(heading(f0), 6);
    expect(elevation(f)).toBeCloseTo(10 * DEG, 6);
    close(rotate(q, [1, 0, 0]), rotate(path, [1, 0, 0]));
  });

  it("stays a unit quaternion", () => {
    const q = composeLook(path, { yaw: 0.7, pitch: -0.9 });
    expect(Math.hypot(...q)).toBeCloseTo(1, 9);
  });
});

describe("lookCursor", () => {
  it("grabbing while dragging, pointer over a hotspot, else the canvas's grab", () => {
    expect(lookCursor(true, true)).toBe("grabbing");
    expect(lookCursor(true, false)).toBe("pointer");
    expect(lookCursor(false, false)).toBe("");
  });
});
