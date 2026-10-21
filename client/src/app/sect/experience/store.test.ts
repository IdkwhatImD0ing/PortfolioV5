import { describe, expect, it } from "vitest";
import { createFreeLook } from "@/lib/sect/free-look";
import { buildScrollMap, uToFrame } from "@/lib/sect/scroll-map";
import { cameraStill, framesToGo, isMoving } from "./store";

const map = buildScrollMap(1, 400, [
  { id: "gate", label: "Mountain Gate", frame: 93 },
  { id: "mirror", label: "Heart-Mirror Terrace", frame: 217 },
]);
const gate = map.holds[0];

describe("isMoving", () => {
  it("moves while the camera trails the scroll position, or flies", () => {
    expect(isMoving({ map, flight: null, reducedMotion: false, targetU: gate.uMid + 5, u: gate.uMid })).toBe(true);
    expect(isMoving({ map, flight: null, reducedMotion: false, targetU: gate.uMid, u: gate.uMid })).toBe(false);
    const flight = { fromU: 0, toU: gate.uMid, t0: 0, duration: 1, toFrame: 93 };
    expect(isMoving({ map, flight, reducedMotion: false, targetU: gate.uMid, u: gate.uMid })).toBe(true);
  });

  it("with reduced motion, is at rest once the camera shows the stop nearest the scroll position", () => {
    // The scroll position sits a few units off the stop (wheel scrolling, or a rounding round trip).
    expect(isMoving({ map, flight: null, reducedMotion: true, targetU: gate.uMid + 3.7, u: gate.uMid })).toBe(false);
    expect(isMoving({ map, flight: null, reducedMotion: true, targetU: gate.uMid - 0.04, u: gate.uMid })).toBe(false);
    // Scrolled far enough that another stop is nearer: the camera has to snap there.
    const mirror = map.holds[1];
    expect(isMoving({ map, flight: null, reducedMotion: true, targetU: mirror.uMid - 2, u: gate.uMid })).toBe(true);
  });
});

describe("cameraStill", () => {
  const at = { map, flight: null, reducedMotion: false, targetU: gate.uMid, u: gate.uMid };

  it("is still at a stop, and not while scrolling, dragging, turning by keys or swinging back", () => {
    expect(cameraStill({ ...at, look: createFreeLook() })).toBe(true);
    expect(cameraStill({ ...at, targetU: gate.uMid + 5, look: createFreeLook() })).toBe(false);
    const drag = createFreeLook();
    drag.press = { id: 1, touch: false, x0: 0, y0: 0, x: 40, y: 0, dragging: true };
    expect(cameraStill({ ...at, look: drag })).toBe(false);
    const swing = createFreeLook();
    swing.recenter = { from: { yaw: 0.3, pitch: 0 }, t0: 0, duration: 0.6 };
    expect(cameraStill({ ...at, look: swing })).toBe(false);
    const keys = createFreeLook();
    keys.keys.right = true;
    expect(cameraStill({ ...at, look: keys })).toBe(false);
  });
});

describe("framesToGo", () => {
  const mid = map.segments.find((s) => s.kind === "move" && s.f0 > 93)!;
  const base = { map, frameOverride: null, reducedMotion: false };

  it("is the frames between the camera and the scroll position", () => {
    const u = (mid.u0 + mid.u1) / 2;
    const frame = uToFrame(map, u);
    expect(framesToGo({ ...base, targetU: u, frame })).toBeCloseTo(0);
    expect(framesToGo({ ...base, targetU: mid.u1, frame })).toBeCloseTo(uToFrame(map, mid.u1) - frame);
  });

  it("is 0 when the camera snaps (reduced motion) or is pinned (?frame=)", () => {
    expect(framesToGo({ ...base, reducedMotion: true, targetU: mid.u1, frame: mid.f0 })).toBe(0);
    expect(framesToGo({ ...base, frameOverride: 93, targetU: mid.u1, frame: 93 })).toBe(0);
  });
});
