import { type Matrix4, PerspectiveCamera, Vector2, Vector3, Vector4 } from "three";
import { describe, expect, it } from "vitest";
import { PondReflector } from "./pond";

describe("pond reflector", () => {
  const pond = { level: 70, min: [-10, -10] as const, max: [10, 10] as const };
  const camera = (at: [number, number, number], look: [number, number, number]) => {
    const c = new PerspectiveCamera(35, 16 / 9, 0.5, 9000);
    c.position.set(...at);
    c.lookAt(...look);
    c.updateProjectionMatrix();
    c.updateMatrixWorld();
    return c;
  };
  const uv = (img: { matrix: Matrix4 }, p: Vector3) => {
    const v = new Vector4(p.x, p.y, p.z, 1).applyMatrix4(img.matrix);
    return new Vector2(v.x / v.w, v.y / v.w);
  };

  it("mirrors the camera in the water and reads a reflected ray where the water point is", () => {
    const r = new PondReflector(0.5);
    const cam = camera([0, 90, 50], [0, 70, 0]);
    const img = r.aim(cam, pond, new Vector2(1600, 900));
    expect(img).not.toBeNull();
    expect(r.camera.position.y).toBeCloseTo(50, 5);
    expect(r.camera.position.z).toBeCloseTo(50, 5);
    // A water point, the view ray's reflection off it, and a point 30 m along that reflection: the
    // mirrored camera sees both at the same place of its image.
    const w = new Vector3(3, 70, -2);
    const v = w.clone().sub(cam.position).normalize();
    const q = w.clone().add(new Vector3(v.x, -v.y, v.z).multiplyScalar(30));
    const a = uv(img!, w);
    const b = uv(img!, q);
    expect(b.x).toBeCloseTo(a.x, 4);
    expect(b.y).toBeCloseTo(a.y, 4);
    // Inside the part of the target filled this frame.
    expect(a.x).toBeGreaterThan(img!.clamp.x);
    expect(a.x).toBeLessThan(img!.clamp.z);
    expect(a.y).toBeGreaterThan(img!.clamp.y);
    expect(a.y).toBeLessThan(img!.clamp.w);
    // Only the pond's rectangle is drawn: fewer texels than the whole target.
    expect(img!.texels).toBeLessThan(r.target.width * r.target.height);
    expect(r.target.width).toBe(800);
    r.dispose();
  });

  it("draws nothing from under the water or with the pond behind the camera", () => {
    const r = new PondReflector(0.5);
    expect(r.aim(camera([0, 69, 50], [0, 69, 0]), pond, new Vector2(1600, 900))).toBeNull();
    expect(r.aim(camera([0, 90, 50], [0, 90, 200]), pond, new Vector2(1600, 900))).toBeNull();
    r.dispose();
  });
});
