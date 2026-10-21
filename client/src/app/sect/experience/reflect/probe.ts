import {
  CubeCamera,
  HalfFloatType,
  LinearFilter,
  LinearMipmapLinearFilter,
  type PerspectiveCamera,
  type Scene,
  WebGLCubeRenderTarget,
  type WebGLRenderer,
} from "three";
import { ProbeSchedule, REFLECT } from "./plan";

/**
 * The Heart-Mirror's surroundings as a cube map, captured from just in front of its face with the
 * face itself (and its rune ring) hidden: one face per rendered frame (a sixth of a scene render),
 * mipmapped when the sixth is in, so the face can read it a little blurred for the bronze's polish.
 * Half-float, like the composer's buffer: glows keep their energy and bloom in the reflection too.
 */
export class MirrorProbe {
  readonly target: WebGLCubeRenderTarget;
  readonly cube: CubeCamera;
  readonly schedule = new ProbeSchedule();

  constructor(size: number) {
    this.target = new WebGLCubeRenderTarget(size, {
      type: HalfFloatType,
      generateMipmaps: true,
      minFilter: LinearMipmapLinearFilter,
      magFilter: LinearFilter,
      depthBuffer: true,
    });
    this.target.texture.name = "sect.mirrorProbe";
    this.cube = new CubeCamera(REFLECT.mirror.near, REFLECT.mirror.far, this.target);
  }

  /** Renders cube face `face` (0..5: +x, -x, +y, -y, +z, -z) of `scene` from `at` (the caller hides the face). */
  renderFace(gl: WebGLRenderer, scene: Scene, at: { x: number; y: number; z: number }, face: number): void {
    const cube = this.cube;
    if (cube.coordinateSystem !== gl.coordinateSystem) {
      cube.coordinateSystem = gl.coordinateSystem;
      cube.updateCoordinateSystem();
    }
    cube.position.set(at.x, at.y, at.z);
    cube.updateMatrixWorld(true);
    const cam = cube.children[face] as PerspectiveCamera;
    const tex = this.target.texture;
    const prevTarget = gl.getRenderTarget();
    const prevFace = gl.getActiveCubeFace();
    const prevLevel = gl.getActiveMipmapLevel();
    const autoClear = gl.autoClear;
    gl.autoClear = true;
    try {
      gl.setRenderTarget(this.target, face);
      // Mipmaps once the last face is in (three makes them at the end of that render).
      tex.generateMipmaps = face === 5;
      gl.render(scene, cam);
    } finally {
      gl.setRenderTarget(prevTarget, prevFace, prevLevel);
      gl.autoClear = autoClear;
      tex.generateMipmaps = true;
    }
  }

  dispose(): void {
    this.target.dispose();
  }
}
