import { PerspectiveCamera, Vector3 } from "three";
import { describe, expect, it } from "vitest";
import { onScreenDepth } from "./pick";

describe("onScreenDepth (the hover label hides behind the camera)", () => {
  // A camera at the origin looking down -Z, as three's cameras do.
  const camera = new PerspectiveCamera(40, 16 / 9, 0.5, 4000);
  camera.updateMatrixWorld();
  const project = (x: number, y: number, z: number) => new Vector3(x, y, z).project(camera);

  it("keeps a point in front of the camera", () => {
    const p = project(3, 1, -50);
    expect(onScreenDepth(p.z)).toBe(true);
  });

  it("drops a point behind the camera, which projects mirrored", () => {
    // The view turned round: the hovered artifact is now 50 m behind, a little to the right.
    const p = project(3, 1, 50);
    expect(onScreenDepth(p.z)).toBe(false);
    // Without the check the label would land on the left half of the screen.
    expect(p.x).toBeLessThan(0);
  });

  it("drops a point past the far plane or before the near plane", () => {
    expect(onScreenDepth(project(0, 0, -5000).z)).toBe(false);
    expect(onScreenDepth(project(0, 0, -0.1).z)).toBe(false);
    expect(onScreenDepth(NaN)).toBe(false);
  });
});
