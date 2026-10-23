import { Matrix4, PerspectiveCamera, Vector3, Vector4 } from "three";
import { describe, expect, it } from "vitest";
import { clipRect, narrowProjection, obliqueNearPlane, pondViewport, ProbeSchedule, reflectTier, REFLECT } from "./plan";

describe("reflection tier", () => {
  it("draws real reflections on High and Medium, none on Low", () => {
    expect(reflectTier({ post: true, msaa: 4 })).toBe("high");
    expect(reflectTier({ post: true, msaa: 0 })).toBe("mid");
    expect(reflectTier({ post: false, msaa: 0 })).toBeNull();
    expect(REFLECT.pond.scale.high).toBe(0.5);
    expect(REFLECT.pond.scale.mid).toBeCloseTo(1 / 3);
  });
});

describe("mirror capture schedule", () => {
  it("captures one face a frame when the mirror comes near, then fades the result in", () => {
    const s = new ProbeSchedule(6000, 600);
    expect(s.next(0, false, "a", 16)).toBe(-1);
    const faces = [0, 1, 2, 3, 4, 5].map((i) => s.next(100 + i * 16, true, "a", 16));
    expect(faces).toEqual([0, 1, 2, 3, 4, 5]);
    expect(s.complete).toBe(true);
    expect(s.fade).toBe(0);
    expect(s.next(300, true, "a", 300)).toBe(-1);
    expect(s.fade).toBeCloseTo(0.5);
    s.next(400, true, "a", 1000);
    expect(s.fade).toBe(1);
  });

  it("shows a whole capture at once under fast travel's ink (snap)", () => {
    const s = new ProbeSchedule(6000, 600);
    for (let i = 0; i < 6; i++) s.next(i * 16, true, "a", 16, true);
    expect(s.complete).toBe(true);
    expect(s.fade).toBe(0);
    expect(s.next(100, true, "a", 16, true)).toBe(-1);
    expect(s.fade).toBe(1);
  });

  it("refreshes every few seconds while near, and at once when the scene changes", () => {
    const s = new ProbeSchedule(6000, 600);
    for (let i = 0; i < 6; i++) s.next(i, true, "a", 16);
    expect(s.next(3000, true, "a", 16)).toBe(-1);
    expect(s.next(6001, true, "a", 16)).toBe(0);
    for (let i = 1; i < 6; i++) expect(s.next(6001 + i, true, "a", 16)).toBe(i);
    expect(s.next(6100, true, "b", 16)).toBe(0);
  });

  it("finishes a capture under way when the mirror goes out of reach, but starts none", () => {
    const s = new ProbeSchedule(6000, 600);
    s.next(0, true, "a", 16);
    s.next(1, true, "a", 16);
    expect([2, 3, 4, 5, 6].map((t) => s.next(t, false, "a", 16))).toEqual([2, 3, 4, 5, -1]);
    expect(s.next(20000, false, "b", 16)).toBe(-1);
    s.reset();
    expect(s.complete).toBe(false);
    expect(s.next(20001, true, "b", 16)).toBe(0);
  });
});

describe("pond rectangle", () => {
  it("covers the projected points with a margin, clamped to the screen", () => {
    const r = clipRect(
      [
        [-0.5, -0.5, 1],
        [0.5, 0.25, 1],
        [0, -1, 2],
      ],
      0.1,
    );
    expect(r).not.toBeNull();
    expect(r!.x0).toBeCloseTo(-0.6);
    expect(r!.x1).toBeCloseTo(0.6);
    expect(r!.y0).toBeCloseTo(-0.575);
    expect(r!.y1).toBeCloseTo(0.325);
    expect(clipRect([[-3, 0, 1], [3, 0.5, 1]])).toEqual({ x0: -1, y0: 0, x1: 1, y1: 0.5 });
  });

  it("is the whole screen when a point is behind the camera, and nothing when all are behind or off one side", () => {
    expect(clipRect([[0, 0, 1], [0, 0, -1]])).toEqual({ x0: -1, y0: -1, x1: 1, y1: 1 });
    expect(clipRect([[0, 0, -1], [1, 0, -2]])).toBeNull();
    expect(clipRect([[2, 0, 1], [3, 0.5, 1]])).toBeNull();
  });

  it("gets a scaled share of the drawing buffer's pixels", () => {
    expect(pondViewport({ x0: -1, y0: -1, x1: 0, y1: 0 }, 1600, 900, 0.5, 800, 450)).toEqual({ w: 400, h: 225 });
    expect(pondViewport({ x0: -1, y0: -1, x1: 1, y1: 1 }, 1600, 900, 1, 800, 450)).toEqual({ w: 800, h: 450 });
    expect(pondViewport({ x0: 0, y0: 0, x1: 0.001, y1: 0.001 }, 1600, 900, 0.5, 800, 450)).toEqual({ w: 8, h: 8 });
  });
});

describe("mirrored camera projection", () => {
  const cam = () => {
    const c = new PerspectiveCamera(40, 16 / 9, 0.5, 9000);
    c.updateProjectionMatrix();
    return c;
  };
  const ndc = (m: Matrix4, p: Vector3) => {
    const v = new Vector4(p.x, p.y, p.z, 1).applyMatrix4(m);
    return new Vector3(v.x / v.w, v.y / v.w, v.z / v.w);
  };

  it("narrows to a rectangle as setViewOffset does", () => {
    const a = cam();
    const e = a.projectionMatrix.elements.slice();
    narrowProjection(e, { x0: -1, y0: -1, x1: 0, y1: 0 });
    const b = cam();
    b.setViewOffset(1600, 900, 0, 450, 800, 450);
    for (let i = 0; i < 16; i++) expect(e[i]).toBeCloseTo(b.projectionMatrix.elements[i], 6);
    // A point at the rectangle's centre lands in the middle of the narrowed view.
    const q = ndc(new Matrix4().fromArray(e), new Vector3(-0.5, -0.5, 0.5).unproject(a));
    expect(q.x).toBeCloseTo(0, 5);
    expect(q.y).toBeCloseTo(0, 5);
  });

  it("moves the near plane onto the given plane and keeps what lies beyond it", () => {
    const c = cam();
    const e = c.projectionMatrix.elements.slice();
    // A plane through (0, -2, -20), tilted: n . p + d >= 0 is kept.
    const n = new Vector3(0, 1, 0.3).normalize();
    const on = new Vector3(0, -2, -20);
    const d = -n.dot(on);
    obliqueNearPlane(e, [n.x, n.y, n.z, d]);
    const m = new Matrix4().fromArray(e);
    expect(ndc(m, on).z).toBeCloseTo(-1, 4);
    const kept = on.clone().addScaledVector(n, 1);
    const z = ndc(m, kept).z;
    expect(z).toBeGreaterThan(-1);
    expect(z).toBeLessThan(1);
    expect(ndc(m, on.clone().addScaledVector(n, -1)).z).toBeLessThan(-1);
    // x and y are untouched.
    expect(ndc(m, kept).x).toBeCloseTo(ndc(c.projectionMatrix, kept).x, 6);
  });
});
