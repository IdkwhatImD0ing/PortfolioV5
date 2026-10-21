import { describe, expect, it } from "vitest";
import {
  BVH_MS_PER_KTRI,
  BVH_POST_REST_MS,
  BVH_REST_MS,
  BVH_TOUCH_MAX_TRIS,
  UPLOAD_FAST_FRAMES,
  UPLOAD_MAX_WAIT_MS,
  bvhCostMs,
  bvhPositions,
  bvhWanted,
  deferUpload,
  mayBuildBvh,
  mayPostBvh,
  updateBvhRate,
  uploadWaitedMs,
} from "./background-work";

describe("BVH builds", () => {
  it("estimates the cost from the triangle count", () => {
    expect(bvhCostMs(150_000)).toBeCloseTo(150 * BVH_MS_PER_KTRI);
    expect(bvhCostMs(150_000, 0.2)).toBeCloseTo(30);
    expect(bvhCostMs(-5)).toBe(0);
  });

  it("refines the estimate from measured builds, ignoring tiny ones", () => {
    expect(updateBvhRate(0.4, 60, 100_000)).toBeCloseTo(0.4 * 0.7 + 0.6 * 0.3);
    expect(updateBvhRate(0.4, 30, 500)).toBe(0.4);
    expect(updateBvhRate(0.4, NaN, 100_000)).toBe(0.4);
  });

  it("waits until the camera has been still for a while", () => {
    const base = { pageReady: true, builtThisSlice: 0, costMs: 1, timeRemainingMs: 10 };
    expect(mayBuildBvh({ ...base, stillForMs: 0 })).toBe(false);
    expect(mayBuildBvh({ ...base, stillForMs: BVH_REST_MS - 1 })).toBe(false);
    expect(mayBuildBvh({ ...base, stillForMs: BVH_REST_MS })).toBe(true);
  });

  it("builds nothing before the page is ready (the camera counts as still while it loads)", () => {
    expect(mayBuildBvh({ pageReady: false, stillForMs: 60_000, builtThisSlice: 0, costMs: 1, timeRemainingMs: 50 })).toBe(false);
  });

  it("runs one build per idle callback whatever its size, more only while they fit", () => {
    const still = BVH_REST_MS + 100;
    // A 60 ms build in a 2 ms idle period (the render loop asks for every display frame).
    expect(mayBuildBvh({ pageReady: true, stillForMs: still, builtThisSlice: 0, costMs: 60, timeRemainingMs: 2 })).toBe(true);
    expect(mayBuildBvh({ pageReady: true, stillForMs: still, builtThisSlice: 1, costMs: 60, timeRemainingMs: 2 })).toBe(false);
    expect(mayBuildBvh({ pageReady: true, stillForMs: still, builtThisSlice: 1, costMs: 1.5, timeRemainingMs: 2 })).toBe(true);
  });

  it("skips the big meshes on a touch screen (no hover: their boxes stand in for a tap)", () => {
    // The library pagoda (426k triangles) froze a phone for 1.46 s.
    expect(bvhWanted(426_000, true)).toBe(false);
    expect(bvhWanted(BVH_TOUCH_MAX_TRIS, true)).toBe(true);
    expect(bvhWanted(18_000, true)).toBe(true);
    // A mouse hovers: everything is built.
    expect(bvhWanted(426_000, false)).toBe(true);
  });
});

describe("BVH jobs for the worker", () => {
  it("go once the page is ready and the camera has been still past a wheel notch's gap", () => {
    expect(mayPostBvh({ pageReady: false, stillForMs: 10_000 })).toBe(false);
    expect(mayPostBvh({ pageReady: true, stillForMs: BVH_POST_REST_MS - 1 })).toBe(false);
    expect(mayPostBvh({ pageReady: true, stillForMs: BVH_POST_REST_MS })).toBe(true);
    // Sooner than a main-thread build may start: the main thread only copies arrays.
    expect(BVH_POST_REST_MS).toBeLessThan(BVH_REST_MS);
  });

  it("read positions as three does: plain floats as they are", () => {
    const f = new Float32Array([1, 2, 3, -4, 5.5, 6]);
    expect([...bvhPositions({ position: f, count: 2, stride: 3, offset: 0, normalized: false })]).toEqual([1, 2, 3, -4, 5.5, 6]);
  });

  it("read meshopt's normalised 16-bit positions at their real size, interleaved or not", () => {
    // Two vertices, stride 4 (xyz plus one more value), starting at element 0.
    const q = new Int16Array([32767, -32767, 0, 99, 16384, -32768, 3277, 99]);
    const out = bvhPositions({ position: q, count: 2, stride: 4, offset: 0, normalized: true });
    expect(out[0]).toBeCloseTo(1, 6);
    expect(out[1]).toBeCloseTo(-1, 6);
    expect(out[2]).toBe(0);
    expect(out[3]).toBeCloseTo(16384 / 32767, 6);
    // -32768 clamps to -1, as three's denormalize does.
    expect(out[4]).toBe(-1);
    expect(out[5]).toBeCloseTo(3277 / 32767, 6);
    const u = new Uint16Array([0, 65535, 32768]);
    const uo = bvhPositions({ position: u, count: 1, stride: 3, offset: 0, normalized: true });
    expect([...uo].map((v) => Math.round(v * 1e4) / 1e4)).toEqual([0, 1, 0.5]);
  });

  it("start at the attribute's offset in an interleaved buffer", () => {
    const a = new Float32Array([9, 9, 1, 2, 3, 9, 9, 4, 5, 6]);
    expect([...bvhPositions({ position: a, count: 2, stride: 5, offset: 2, normalized: false })]).toEqual([1, 2, 3, 4, 5, 6]);
  });
});

describe("texture uploads", () => {
  const slow = { flight: false, framesToGo: 0, inView: true, waitedMs: 0 };

  it("go while the camera is still or slow", () => {
    expect(deferUpload(slow)).toBe(false);
    expect(deferUpload({ ...slow, framesToGo: UPLOAD_FAST_FRAMES })).toBe(false);
  });

  it("wait during a jump, however long", () => {
    expect(deferUpload({ ...slow, flight: true, waitedMs: 60_000 })).toBe(true);
  });

  it("wait while the camera moves fast, but not forever for an area wanted on screen", () => {
    const fast = { ...slow, framesToGo: UPLOAD_FAST_FRAMES + 10 };
    expect(deferUpload({ ...fast, waitedMs: 10 })).toBe(true);
    expect(deferUpload({ ...fast, waitedMs: UPLOAD_MAX_WAIT_MS })).toBe(false);
    // A prefetched area (not on screen yet) waits until the camera slows down.
    expect(deferUpload({ ...fast, inView: false, waitedMs: 10 * UPLOAD_MAX_WAIT_MS })).toBe(true);
  });

  it("wait while the view turns (drag, arrow key, swing back), even with the camera at rest", () => {
    const turning = { ...slow, turning: true };
    expect(deferUpload({ ...turning, waitedMs: 10 })).toBe(true);
    // A prefetched area (not wanted on screen yet) waits for the turn to end.
    expect(deferUpload({ ...turning, inView: false, waitedMs: 10 * UPLOAD_MAX_WAIT_MS })).toBe(true);
    // An area wanted on screen (the one behind, loaded because the visitor looked back) still
    // arrives during a long spin, a texture at a time.
    expect(deferUpload({ ...turning, waitedMs: UPLOAD_MAX_WAIT_MS })).toBe(false);
    // Once the turn is over it goes at once.
    expect(deferUpload({ ...turning, turning: false, inView: false })).toBe(false);
  });

  it("count one wait per area, from when it was first wanted on screen", () => {
    // Not wanted on screen yet: nothing has been waited.
    expect(uploadWaitedMs(null, 5000)).toBe(0);
    // Wanted since t = 1000: by 1600 the area has used up its wait, whichever texture is next.
    expect(uploadWaitedMs(1000, 1600)).toBe(600);
    expect(deferUpload({ ...slow, framesToGo: UPLOAD_FAST_FRAMES + 10, waitedMs: uploadWaitedMs(1000, 1600) })).toBe(false);
  });
});
