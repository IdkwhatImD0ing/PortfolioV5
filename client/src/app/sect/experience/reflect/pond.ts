import {
  HalfFloatType,
  LinearFilter,
  Matrix4,
  PerspectiveCamera,
  Plane,
  Vector3,
  Vector4,
  WebGLRenderTarget,
  type Scene,
  Vector2,
  type WebGLRenderer,
} from "three";
import { clipRect, narrowProjection, obliqueNearPlane, pondViewport, REFLECT } from "./plan";

/** The open water a planar reflection is rendered for. */
export interface PondPlane {
  /** Height of the water plane (three y). */
  level: number;
  /** Horizontal extent of the open water (x, z). */
  min: readonly [number, number];
  max: readonly [number, number];
}

/** What the water shader needs from one rendered reflection. */
export interface PondImage {
  /** World position to the reflection texture's coordinates (projective). */
  matrix: Matrix4;
  /** The part of the texture this frame filled: (min u, min v, max u, max v), half a texel in. */
  clamp: Vector4;
  /** One texel (u, v). */
  texel: Vector2;
  /** Texels rendered this frame. */
  texels: number;
}

const BIAS = new Matrix4();
const _plane = new Plane();
const _n = new Vector3();
const _p = new Vector4();
const _f = new Vector3();
const _u = new Vector3();
const _vp = new Matrix4();

/**
 * The Still Pond's planar reflection, three's Reflector reworked for one large shared material: the
 * camera mirrored in the water plane, its projection narrowed to the rectangle the open water fills
 * on screen (so the frustum culls what the pond cannot show, and only those pixels are drawn, at
 * `scale` texels per screen pixel), and its near plane moved onto the water (Lengyel's oblique
 * clipping) so nothing below it is drawn: the water's own surface included, while the lily pads a
 * few centimetres up and the stones stay. Into a half-float target, as the composer's buffer.
 */
export class PondReflector {
  readonly target: WebGLRenderTarget;
  readonly camera = new PerspectiveCamera();
  private readonly image: PondImage = { matrix: new Matrix4(), clamp: new Vector4(), texel: new Vector2(), texels: 0 };

  constructor(private readonly scale: number) {
    this.target = new WebGLRenderTarget(1, 1, {
      type: HalfFloatType,
      minFilter: LinearFilter,
      magFilter: LinearFilter,
      generateMipmaps: false,
      depthBuffer: true,
    });
    this.target.texture.name = "sect.pondReflection";
    this.camera.matrixAutoUpdate = true;
  }

  /**
   * Sets the mirrored camera up for `camera` and the target for a `drawing` px drawing buffer, and
   * returns what the water shader needs from the image draw() will render. Null when the camera is
   * at or below the water or the open water is off screen (draw nothing then). No GL calls but a
   * resize.
   */
  aim(camera: PerspectiveCamera, pond: PondPlane, drawing: Vector2): PondImage | null {
    const L = pond.level;
    camera.updateMatrixWorld();
    const eye = _f.setFromMatrixPosition(camera.matrixWorld);
    if (eye.y <= L + 0.05) return null;
    // Mirror the camera: position, forward and up reflected in the plane y = L.
    const vc = this.camera;
    vc.position.set(eye.x, 2 * L - eye.y, eye.z);
    _u.set(0, 1, 0).transformDirection(camera.matrixWorld);
    _u.y = -_u.y;
    vc.up.copy(_u);
    _n.set(0, 0, -1).transformDirection(camera.matrixWorld);
    _n.y = -_n.y;
    vc.lookAt(_n.add(vc.position));
    vc.near = camera.near;
    vc.far = camera.far;
    vc.updateMatrixWorld();
    const e = vc.projectionMatrix.elements;
    vc.projectionMatrix.copy(camera.projectionMatrix);
    // The open water's corners in the mirrored camera's clip space: the rectangle it fills.
    const vp = _vp.multiplyMatrices(vc.projectionMatrix, vc.matrixWorldInverse);
    const corners: [number, number, number][] = [];
    for (const [x, z] of [
      [pond.min[0], pond.min[1]],
      [pond.max[0], pond.min[1]],
      [pond.max[0], pond.max[1]],
      [pond.min[0], pond.max[1]],
    ] as const) {
      _p.set(x, L, z, 1).applyMatrix4(vp);
      corners.push([_p.x, _p.y, _p.w]);
    }
    const rect = clipRect(corners, REFLECT.pond.margin);
    if (!rect) return null;
    // The target: the drawing buffer at `scale`; this frame fills the pond's share of it.
    const tw = Math.max(8, Math.round(drawing.x * this.scale));
    const th = Math.max(8, Math.round(drawing.y * this.scale));
    if (this.target.width !== tw || this.target.height !== th) this.target.setSize(tw, th);
    const view = pondViewport(rect, drawing.x, drawing.y, this.scale, tw, th);
    narrowProjection(e, rect);
    // World to texture: [-1, 1] to the filled corner of the target.
    const sx = view.w / tw;
    const sy = view.h / th;
    BIAS.set(sx * 0.5, 0, 0, sx * 0.5, 0, sy * 0.5, 0, sy * 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1);
    this.image.matrix.multiplyMatrices(BIAS, vc.projectionMatrix).multiply(vc.matrixWorldInverse);
    this.image.clamp.set(0.5 / tw, 0.5 / th, (view.w - 0.5) / tw, (view.h - 0.5) / th);
    this.image.texel.set(1 / tw, 1 / th);
    this.image.texels = view.w * view.h;
    // Near plane on the water (a centimetre up: the water itself is cut, its lily pads are not).
    _plane.setFromNormalAndCoplanarPoint(_n.set(0, 1, 0), _f.set(0, L + REFLECT.pond.clipLift, 0));
    _plane.applyMatrix4(vc.matrixWorldInverse);
    obliqueNearPlane(e, [_plane.normal.x, _plane.normal.y, _plane.normal.z, _plane.constant]);
    vc.projectionMatrixInverse.copy(vc.projectionMatrix).invert();
    const t = this.target;
    t.viewport.set(0, 0, view.w, view.h);
    t.scissor.set(0, 0, view.w, view.h);
    t.scissorTest = true;
    return this.image;
  }

  /** Renders the reflection aimed by aim() into the target. The caller hides what must not be drawn. */
  draw(gl: WebGLRenderer, scene: Scene): void {
    const prev = gl.getRenderTarget();
    const autoClear = gl.autoClear;
    gl.autoClear = true;
    try {
      gl.setRenderTarget(this.target);
      gl.render(scene, this.camera);
    } finally {
      gl.setRenderTarget(prev);
      gl.autoClear = autoClear;
    }
  }

  dispose(): void {
    this.target.dispose();
  }
}
