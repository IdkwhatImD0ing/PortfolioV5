import { describe, expect, it } from "vitest";
import {
  catmullRom,
  fovForAspect,
  forward,
  locate,
  normalizeQuat,
  rotate,
  sampleCamera,
  samplePath,
  slerp,
} from "./camera-path";
import type { CameraFrame, Quat } from "./types";

const yaw = (deg: number): Quat => {
  const h = (deg * Math.PI) / 360;
  return [0, Math.sin(h), 0, Math.cos(h)];
};

function frames(n: number): CameraFrame[] {
  return Array.from({ length: n }, (_, i) => ({
    f: i + 1,
    p: [i * 2, 10, 5 - i * 3] as [number, number, number],
    q: yaw(i * 10),
    fovY: 30 + i,
  }));
}

describe("catmullRom", () => {
  it("passes through the control points", () => {
    const a: [number, number, number] = [0, 0, 0];
    const b: [number, number, number] = [1, 2, 3];
    const c: [number, number, number] = [4, 4, 4];
    const d: [number, number, number] = [9, 9, 9];
    expect(catmullRom(a, b, c, d, 0)).toEqual(b);
    expect(catmullRom(a, b, c, d, 1).map((x) => +x.toFixed(9))).toEqual(c);
  });

  it("is linear on evenly spaced collinear points", () => {
    const p = catmullRom([0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0], 0.25);
    expect(p[0]).toBeCloseTo(1.25, 9);
  });
});

describe("slerp", () => {
  it("interpolates the rotation angle halfway", () => {
    const q = slerp(yaw(0), yaw(90), 0.5);
    const e = yaw(45);
    q.forEach((v, i) => expect(v).toBeCloseTo(e[i], 9));
  });

  it("takes the short way when quaternions are on opposite hemispheres", () => {
    const b = yaw(20).map((x) => -x) as Quat;
    const q = slerp(yaw(0), b, 0.5);
    const e = yaw(10);
    q.forEach((v, i) => expect(Math.abs(v)).toBeCloseTo(Math.abs(e[i]), 9));
  });

  it("returns unit quaternions", () => {
    const q = slerp(normalizeQuat([0.1, 0.2, 0.3, 0.9]), normalizeQuat([0.4, -0.2, 0.1, 0.8]), 0.37);
    expect(Math.hypot(...q)).toBeCloseTo(1, 12);
  });
});

describe("sampleCamera", () => {
  const fr = frames(10);

  it("hits samples exactly at integer frames", () => {
    const s = sampleCamera(fr, 4);
    expect(s.p).toEqual(fr[3].p);
    expect(s.fovY).toBe(fr[3].fovY);
    s.q.forEach((v, i) => expect(v).toBeCloseTo(fr[3].q[i], 9));
  });

  it("interpolates between frames", () => {
    const s = sampleCamera(fr, 4.5);
    expect(s.p[0]).toBeCloseTo(7, 9);
    expect(s.p[2]).toBeCloseTo(-5.5, 9);
    expect(s.fovY).toBeCloseTo(33.5, 9);
    const e = yaw(35);
    s.q.forEach((v, i) => expect(v).toBeCloseTo(e[i], 9));
  });

  it("clamps outside the frame range", () => {
    expect(sampleCamera(fr, -5).p).toEqual(fr[0].p);
    expect(sampleCamera(fr, 99).p).toEqual(fr[9].p);
  });

  it("handles non-consecutive frame numbers", () => {
    const sparse = [fr[0], { ...fr[4], f: 5 }, { ...fr[9], f: 10 }];
    const s = samplePath(sparse, 7.5);
    expect(s.p[0]).toBeGreaterThan(fr[4].p[0]);
    expect(s.p[0]).toBeLessThan(fr[9].p[0]);
  });
});

describe("fovForAspect", () => {
  it("keeps fovY at the reference aspect", () => {
    expect(fovForAspect(35.1154, 16 / 9, 16 / 9)).toBeCloseTo(35.1154, 6);
  });

  it("never narrows on wider screens", () => {
    expect(fovForAspect(35, 16 / 9, 21 / 9)).toBe(35);
  });

  it("widens on portrait screens up to the cap", () => {
    const f = fovForAspect(35, 16 / 9, 0.8);
    expect(f).toBeGreaterThan(35);
    expect(f).toBeLessThanOrEqual(70);
    expect(fovForAspect(35, 16 / 9, 0.3)).toBe(70);
  });
});

describe("rotate / forward", () => {
  it("identity looks down -Z", () => {
    expect(forward([0, 0, 0, 1])).toEqual([0, 0, -1]);
  });

  it("a 90 degree yaw turns -Z toward -X", () => {
    const f = forward(yaw(90));
    expect(f[0]).toBeCloseTo(-1, 9);
    expect(f[2]).toBeCloseTo(0, 9);
  });

  it("preserves length", () => {
    const v = rotate(normalizeQuat([0.3, -0.5, 0.2, 0.7]), [3, 4, 12]);
    expect(Math.hypot(...v)).toBeCloseTo(13, 9);
  });
});

describe("locate", () => {
  const at = (fs: number[]) => fs.map((f) => ({ f, p: [f * 10, 0, 0] as [number, number, number], q: [0, 0, 0, 1] as Quat }));

  it("finds consecutive integer frames directly", () => {
    expect(locate(at([1, 2, 3, 4]), 2.5)).toEqual({ i: 1, s: 0.5 });
    expect(locate(at([1, 2, 3, 4]), 99)).toEqual({ i: 2, s: 1 });
  });

  it("does not trust the fast path when a frame repeats or is fractional", () => {
    // [1, 2, 2, 4] spans 3 frames over 4 samples, like consecutive frames would.
    const a = locate(at([1, 2, 2, 4]), 3);
    expect(at([1, 2, 2, 4])[a.i].f).toBe(2);
    expect(a.i).toBe(2);
    // [1, 1.5, 3] at frame 2: one third of the way from 1.5 to 3.
    const b = locate(at([1, 1.5, 3]), 2);
    expect(b.i).toBe(1);
    expect(b.s).toBeCloseTo(1 / 3, 9);
  });

  it("treats a non-finite frame as the first", () => {
    expect(locate(at([1, 2, 3]), Number.NaN)).toEqual({ i: 0, s: 0 });
    expect(() => samplePath(at([1, 2, 3]), Number.NaN)).not.toThrow();
  });
});
