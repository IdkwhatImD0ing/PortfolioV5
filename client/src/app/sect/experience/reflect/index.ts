/**
 * Real reflections at the Heart-Mirror stop, on High and Medium (Low keeps the analytic sky and
 * disc, materials.ts): the mirror's face samples a cube map of its surroundings (probe.ts), and the
 * Still Pond samples a planar reflection of the scene (pond.ts). Both run only while the mirror's
 * area is drawn: the cube a face a frame when the mirror comes near and every few seconds while it
 * stays near, the pond only while its open water is on screen and near. Elsewhere in the flight
 * update() returns at its first test.
 *
 * Each pass draws the loaded sets with the sky, moon, cloud sea and grass (isolate.ts), soft edges
 * off (they read the main view's depth), and the samplers it writes into unbound from the materials
 * that read them: the pond's image while the pond is drawn, the mirror's cube while a face of it is.
 */
import { Frustum, Matrix4, Sphere, Vector2, Vector3, type Object3D, type PerspectiveCamera, type Scene, type Vector4, type WebGLRenderer } from "three";
import type { LoadedSet, PondReflection } from "../assets";
import { SECT_MIRROR, SOFT_DEPTH, type WaterUniforms } from "../materials";
import { isolateForReflection, type ReflectView } from "./isolate";
import { REFLECT, type ReflectTier } from "./plan";
import { PondReflector, type PondImage } from "./pond";
import { MirrorProbe } from "./probe";
import type { SpanTimer } from "./timer";

export interface ReflectFrame {
  gl: WebGLRenderer;
  scene: Scene;
  camera: PerspectiveCamera;
  /** The canvas's sets (global and chunks). */
  sets: readonly LoadedSet[];
  /** The ripples' clock (s; 0 with reduced motion). */
  time: number;
  /** performance.now() and the frame's length (ms). */
  now: number;
  dt: number;
  /** What else changes what a capture sees (the quality step). */
  quality: string;
  /**
   * The quality ladder has stepped down to drawing the other areas as stand-ins (a device short of
   * time): the pond keeps its analytic reflection, which costs no second scene render.
   */
  lean: boolean;
}

/** What the last update did (the debug probe shows it). */
export interface ReflectStatus {
  tier: ReflectTier;
  /** The pond's reflection was rendered, and its texels. */
  pond: boolean;
  pondTexels: number;
  /** The cube face captured (-1: none), whether a whole capture exists, and its fade. */
  face: number;
  complete: boolean;
  fade: number;
  /** Main-thread time of this frame's passes (ms). */
  cpuMs: number;
  /** The targets hold GPU memory (released while the mirror's area is not loaded). */
  allocated: boolean;
}

export class SectReflections {
  private readonly planar: PondReflector;
  private readonly probe: MirrorProbe;
  /** Pond uniforms pointed at the planar image last frame. */
  private readonly fed = new Set<WaterUniforms>();
  private readonly drawing = new Vector2();
  private readonly frustum = new Frustum();
  private readonly viewProj = new Matrix4();
  private readonly mirrorAt = new Vector3();
  private readonly mirrorSphere = new Sphere();
  /** GPU time of the passes (?debug=1 only). */
  timer: SpanTimer | null = null;
  /** Inspection switches (?debug=1): either pass off. */
  readonly enabled = { pond: true, mirror: true };
  readonly status: ReflectStatus;

  constructor(readonly tier: ReflectTier) {
    this.planar = new PondReflector(REFLECT.pond.scale[tier]);
    this.probe = new MirrorProbe(REFLECT.mirror.size[tier]);
    this.status = { tier, pond: false, pondTexels: 0, face: -1, complete: false, fade: 0, cpuMs: 0, allocated: false };
  }

  update(f: ReflectFrame): ReflectStatus {
    const st = this.status;
    st.pond = false;
    st.pondTexels = 0;
    st.face = -1;
    st.cpuMs = 0;
    // Last frame's pond reads the analytic path again unless it is rendered below.
    for (const u of this.fed) {
      u.uHasReflect.value = 0;
      u.tReflect.value = null;
    }
    this.fed.clear();
    let pond: PondReflection | null = null;
    let loaded = false;
    for (const s of f.sets) {
      if (!s.pond || s.dropped || s.freed) continue;
      loaded = true;
      if (s.drawn) {
        pond = s.pond;
        break;
      }
    }
    // Away from the mirror's area the targets give their GPU memory back; a later visit captures again.
    if (!loaded && st.allocated) this.release();
    if (!pond) return st;
    const mirror = pond.mirror;
    this.viewProj.multiplyMatrices(f.camera.projectionMatrix, f.camera.matrixWorldInverse);
    this.frustum.setFromProjectionMatrix(this.viewProj);
    let face = -1;
    if (mirror && this.enabled.mirror) {
      // The first capture as soon as the mirror is within reach (before it is on screen); fresh ones
      // only near its stop while it is on screen.
      this.mirrorAt.fromArray(mirror.center);
      this.mirrorSphere.set(this.mirrorAt, mirror.radius * 1.5);
      const d = f.camera.position.distanceTo(this.mirrorAt);
      const near = this.probe.schedule.complete
        ? d < REFLECT.mirror.refreshDistance && this.frustum.intersectsSphere(this.mirrorSphere)
        : d < REFLECT.mirror.maxDistance;
      const signature = near ? `${f.sets.map((s) => (s.drawn ? s.id : "")).join(",")}|${f.quality}` : "";
      face = this.probe.schedule.next(f.now, near, signature, f.dt);
    }
    let img: PondImage | null = null;
    if (this.enabled.pond && !f.lean && pond.box.distanceToPoint(f.camera.position) <= REFLECT.pond.maxDistance && this.frustum.intersectsBox(pond.box)) {
      f.gl.getDrawingBufferSize(this.drawing);
      img = this.planar.aim(f.camera, { level: pond.level, min: pond.water.min, max: pond.water.max }, this.drawing);
    }
    if (face >= 0 || img) {
      const t0 = performance.now();
      st.allocated = true;
      // Matrices once for both passes (three would update the whole scene graph for each).
      f.scene.updateMatrixWorld();
      const autoUpdate = f.scene.matrixWorldAutoUpdate;
      f.scene.matrixWorldAutoUpdate = false;
      const hadDepth = SOFT_DEPTH.uHasDepth.value;
      SOFT_DEPTH.uHasDepth.value = 0;
      try {
        if (face >= 0 && mirror) {
          const restore = isolateForReflection(f.scene, this.view(f.sets, pond, REFLECT.mirror.view[this.tier], mirror.hide));
          try {
            this.capture(f, pond, face);
          } finally {
            restore();
          }
        }
        this.applyMirror(pond);
        if (img) {
          const restore = isolateForReflection(f.scene, this.view(f.sets, pond, REFLECT.pond.view));
          try {
            this.renderPond(f, pond, img);
          } finally {
            restore();
          }
        }
      } finally {
        SOFT_DEPTH.uHasDepth.value = hadDepth;
        f.scene.matrixWorldAutoUpdate = autoUpdate;
        st.cpuMs = performance.now() - t0;
      }
    } else {
      this.applyMirror(pond);
    }
    st.face = face;
    st.complete = this.probe.schedule.complete;
    st.fade = this.probe.schedule.fade;
    return st;
  }

  /**
   * What a pass draws: the global set and the mirror's area as they are, the grass if `o.grass`, and
   * the other drawn areas either as they are or (`o.standIns`) as the backdrop's low stand-ins (in
   * a reflection they are a few distant shapes, and their full meshes were most of its triangles).
   */
  private view(sets: readonly LoadedSet[], pond: PondReflection, o: { grass: boolean; standIns: boolean }, hide?: readonly Object3D[]): ReflectView {
    const roots = new Set<Object3D>();
    const show: Object3D[] = [];
    const global = sets.find((s) => s.need === null) ?? null;
    for (const s of sets) {
      if (!s.drawn) continue;
      if (s === global || s.pond === pond || !o.standIns) {
        for (const r of s.scenes) roots.add(r);
      } else {
        for (const m of global?.proxies.get(s.id) ?? []) show.push(m);
      }
    }
    return { roots, grass: o.grass, show, hide };
  }

  /** One cube face, with the face and its ring hidden, the pond showing only its sky, the cube unbound. */
  private capture(f: ReflectFrame, pond: PondReflection, face: number): void {
    const mirror = pond.mirror!;
    const discs = pond.uniforms.map((u) => u.uDiscR.value as number);
    for (const u of pond.uniforms) u.uDiscR.value = 0;
    SECT_MIRROR.tSectMirrorEnv.value = null;
    this.timer?.begin("mirror");
    try {
      this.probe.renderFace(f.gl, f.scene, { x: mirror.capture[0], y: mirror.capture[1], z: mirror.capture[2] }, face);
    } finally {
      this.timer?.end();
      pond.uniforms.forEach((u, i) => (u.uDiscR.value = discs[i]));
    }
  }

  /** The face reads the cube once a whole capture exists, faded in. */
  private applyMirror(pond: PondReflection): void {
    const mirror = pond.mirror;
    const s = this.probe.schedule;
    if (!mirror || !s.complete || !this.enabled.mirror) {
      SECT_MIRROR.uSectMirrorEnvOn.value = 0;
      SECT_MIRROR.tSectMirrorEnv.value = null;
      return;
    }
    SECT_MIRROR.tSectMirrorEnv.value = this.probe.target.texture;
    SECT_MIRROR.uSectMirrorEnvOn.value = s.fade;
    SECT_MIRROR.uSectMirrorEnvP.value.fromArray(mirror.capture);
    SECT_MIRROR.uSectMirrorEnvC.value.fromArray(mirror.center);
    SECT_MIRROR.uSectMirrorEnvN.value.fromArray(mirror.normal);
    SECT_MIRROR.uSectMirrorEnvR.value = mirror.radius;
  }

  private renderPond(f: ReflectFrame, pond: PondReflection, img: PondImage): void {
    this.timer?.begin("pond");
    try {
      this.planar.draw(f.gl, f.scene);
    } finally {
      this.timer?.end();
    }
    for (const u of pond.uniforms) {
      u.uHasReflect.value = 1;
      u.tReflect.value = this.planar.target.texture;
      (u.uReflectMatrix.value as Matrix4).copy(img.matrix);
      (u.uReflectClamp.value as Vector4).copy(img.clamp);
      (u.uReflectTexel.value as Vector2).copy(img.texel);
      u.uWaterTime.value = f.time;
      this.fed.add(u);
    }
    this.status.pond = true;
    this.status.pondTexels = img.texels;
  }

  /** Frees both targets' GPU memory (three allocates them again on their next use). */
  private release(): void {
    if (SECT_MIRROR.tSectMirrorEnv.value === this.probe.target.texture) SECT_MIRROR.tSectMirrorEnv.value = null;
    SECT_MIRROR.uSectMirrorEnvOn.value = 0;
    this.probe.schedule.reset();
    this.planar.target.dispose();
    this.probe.target.dispose();
    this.status.allocated = false;
    // update() returns early from here on, so the debug status says now that the capture is gone.
    this.status.complete = false;
    this.status.fade = 0;
  }

  dispose(): void {
    for (const u of this.fed) {
      u.uHasReflect.value = 0;
      u.tReflect.value = null;
    }
    this.fed.clear();
    if (SECT_MIRROR.tSectMirrorEnv.value === this.probe.target.texture) SECT_MIRROR.tSectMirrorEnv.value = null;
    SECT_MIRROR.uSectMirrorEnvOn.value = 0;
    this.planar.dispose();
    this.probe.dispose();
  }
}
