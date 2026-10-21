/**
 * The reflections' settings and the pure parts of their passes (no three.js objects, so they are
 * testable): which tier draws them, when the Heart-Mirror's cube map is captured, the Still Pond's
 * screen rectangle and how many texels it gets, and the projection changes of the pond's mirrored
 * camera (a view-offset narrowed to the pond, and Lengyel's oblique near plane at the water).
 *
 * Matrices are three.js Matrix4 `elements`: column-major, so row r, column c is e[c * 4 + r].
 */

export type ReflectTier = "high" | "mid";

export const REFLECT = {
  pond: {
    /** Reflection texels per screen pixel, per axis: High 1/2, Medium 1/3 (over the pond only). */
    scale: { high: 0.5, mid: 1 / 3 } as Record<ReflectTier, number>,
    /** Drawn only while the camera is within this distance of the pond's box (m). */
    maxDistance: 320,
    /** The mirrored camera's near plane sits this far above the water (the water itself is cut). */
    clipLift: 0.01,
    /** Margin round the pond's screen rectangle, as a share of its size, for the ripples' reach. */
    margin: 0.05,
    /**
     * What it draws (reflect/index.ts view): no grass (a fringe at the bank, a seventh of its
     * triangles), and the other drawn areas as the backdrop's stand-ins.
     */
    view: { grass: false, standIns: true },
    /** How the water shows it (materials.ts WATER_FRAGMENT, the planar path). */
    look: {
      /** Water's reflectance straight down (Schlick), and a scale on the reflection. */
      f0: 0.05,
      gain: 1.4,
      /** The bake under the reflection, darkened and cooled: a deep pond (linear RGB scale). */
      deep: [0.42, 0.5, 0.55] as const,
      /** Ripple slope (the normal's lean) and how far off the reflected things are taken to be (m). */
      slope: 0.0025,
      reach: 25,
      /** The ripples calm out between these distances from the camera (m). */
      calm: [70, 220] as const,
    },
  },
  mirror: {
    /** Cube face size (px). */
    size: { high: 512, mid: 256 } as Record<ReflectTier, number>,
    near: 0.2,
    far: 9000,
    /** What a capture draws: everything on High; on Medium no grass and the other areas' stand-ins. */
    view: { high: { grass: true, standIns: false }, mid: { grass: false, standIns: true } } as Record<ReflectTier, { grass: boolean; standIns: boolean }>,
    /** The capture point sits this far in front of the face's centre (m). */
    front: 0.3,
    /**
     * The first capture once the camera is within this distance of the mirror (m: on the approach,
     * after the gate's stop at about 290 m), and fresh ones only within `refreshDistance` (its own
     * stop is 66-90 m off) while the mirror is on screen, every `refreshSeconds` (the clouds drift).
     */
    maxDistance: 250,
    refreshDistance: 160,
    refreshSeconds: 6,
    /** The real reflection fades in over this long once the first capture is whole (s). */
    fadeSeconds: 0.6,
    /** How the face shows it (materials.ts surfaceGlsl, the mirror's cube path). */
    look: {
      /** The normal's outward lean at the rim: a gently convex face (the sky-only path leans more). */
      convex: 0.1,
      /**
       * Reflectance at normal incidence (linear RGB): the pale warm bronze of a polished high-tin
       * mirror, less saturated than the sky-only path's gold so the scene keeps its colours.
       */
      f0: [0.8, 0.7, 0.52] as const,
      /** Mip bias of the sharp read, and the blurrier level mixed in for the bronze's polish. */
      bias: 0.25,
      hazeLod: 4,
      haze: 0.1,
      /** Radius of the sphere the reflected ray is met with (m): the dais, trees and cliffs round it. */
      parallax: 30,
      /** Scale on what the face reflects, the sun glint's share, and how much of the baked glow stays. */
      gain: 1,
      sun: 0.3,
      glow: 0.4,
      /** Where the patina takes over, as a share of the face's radius. */
      patina: [0.62, 0.92] as const,
    },
  },
} as const;

/** The reflections' tier: High (multisampled post), Medium (post), none on Low (water.ts fxTier's rule). */
export function reflectTier(q: { post: boolean; msaa: number }): ReflectTier | null {
  if (!q.post) return null;
  return q.msaa > 0 ? "high" : "mid";
}

/**
 * When the Heart-Mirror's cube map is captured: one face per rendered frame, a whole capture when
 * the mirror first comes near, again every `refreshSeconds` while it stays near, and at once when
 * what the capture would see changes (`signature`: the drawn sets, the quality step). `fade` runs
 * 0 to 1 once the first capture is whole.
 */
export class ProbeSchedule {
  /** Next face to render (0..5), or -1 between captures. */
  face = -1;
  /** A whole capture exists. */
  complete = false;
  fade = 0;
  private startedAt = -Infinity;
  private signature = "";

  constructor(
    private readonly refreshMs: number = REFLECT.mirror.refreshSeconds * 1000,
    private readonly fadeMs: number = REFLECT.mirror.fadeSeconds * 1000,
  ) {}

  /**
   * The face to render this frame (or -1). `near`: the mirror is close enough to matter; `dt` the
   * frame's length (ms) for the fade.
   */
  next(now: number, near: boolean, signature: string, dt: number): number {
    if (this.complete) this.fade = Math.min(1, this.fade + Math.max(dt, 0) / this.fadeMs);
    if (!near) {
      // A capture under way finishes (it is cheap); none starts.
      return this.face >= 0 ? this.take() : -1;
    }
    if (this.face < 0 && (signature !== this.signature || now - this.startedAt >= this.refreshMs)) {
      this.signature = signature;
      this.startedAt = now;
      this.face = 0;
    }
    return this.face >= 0 ? this.take() : -1;
  }

  /** Drop the capture (a new tier or a new target): the next near frame starts a fresh one. */
  reset(): void {
    this.face = -1;
    this.complete = false;
    this.fade = 0;
    this.startedAt = -Infinity;
    this.signature = "";
  }

  private take(): number {
    const f = this.face;
    this.face = f >= 5 ? -1 : f + 1;
    if (f >= 5) this.complete = true;
    return f;
  }
}

/** A rectangle in normalized device coordinates. */
export interface NdcRect {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

/**
 * The NDC rectangle covering points given in clip space ([x, y, w] each), grown by `margin` of its
 * size and clamped to the screen; the whole screen when some (not all) points are at or behind the
 * camera; null when all are behind it or they lie wholly off one side of the screen.
 */
export function clipRect(points: readonly (readonly [number, number, number])[], margin = 0): NdcRect | null {
  const behind = points.filter(([, , w]) => !(w > 1e-6)).length;
  if (behind === points.length) return null;
  if (behind > 0) return { x0: -1, y0: -1, x1: 1, y1: 1 };
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y, w] of points) {
    x0 = Math.min(x0, x / w);
    x1 = Math.max(x1, x / w);
    y0 = Math.min(y0, y / w);
    y1 = Math.max(y1, y / w);
  }
  if (!(x1 >= x0 && y1 >= y0)) return null;
  const mx = (x1 - x0) * margin;
  const my = (y1 - y0) * margin;
  const r = { x0: Math.max(-1, x0 - mx), y0: Math.max(-1, y0 - my), x1: Math.min(1, x1 + mx), y1: Math.min(1, y1 + my) };
  return r.x1 > r.x0 && r.y1 > r.y0 ? r : null;
}

/**
 * Pixels of the reflection's viewport for a screen rectangle `rect` of a `width` x `height` drawing
 * buffer at `scale` texels per pixel, at least 8 and at most the target's size.
 */
export function pondViewport(rect: NdcRect, width: number, height: number, scale: number, maxW: number, maxH: number): { w: number; h: number } {
  const w = Math.ceil(((rect.x1 - rect.x0) / 2) * width * scale);
  const h = Math.ceil(((rect.y1 - rect.y0) / 2) * height * scale);
  return { w: Math.min(maxW, Math.max(8, w)), h: Math.min(maxH, Math.max(8, h)) };
}

/**
 * Narrows a perspective projection (in place) to the NDC rectangle `rect`: what was inside it now
 * fills the clip space, as PerspectiveCamera.setViewOffset would (rows 0 and 1 scaled and shifted
 * by row 3, which is (0, 0, -1, 0) for a perspective matrix).
 */
export function narrowProjection(e: number[] | Float32Array, rect: NdcRect): void {
  const sx = 2 / (rect.x1 - rect.x0);
  const sy = 2 / (rect.y1 - rect.y0);
  const tx = -(rect.x1 + rect.x0) / (rect.x1 - rect.x0);
  const ty = -(rect.y1 + rect.y0) / (rect.y1 - rect.y0);
  for (let c = 0; c < 4; c++) {
    e[c * 4] = sx * e[c * 4] + tx * e[c * 4 + 3];
    e[c * 4 + 1] = sy * e[c * 4 + 1] + ty * e[c * 4 + 3];
  }
}

/**
 * Lengyel's oblique near plane (terathon.com/lengyel/Lengyel-Oblique.pdf), as three's Reflector
 * does it: replaces the projection's third row (in place) so that the near plane is `plane`, given
 * in view space as (a, b, c, d) with a x + b y + c z + d >= 0 on the kept side. Points on the far
 * side are clipped; depth stays monotonic along each ray.
 */
export function obliqueNearPlane(e: number[] | Float32Array, plane: readonly [number, number, number, number]): void {
  const [a, b, c, d] = plane;
  const qx = (Math.sign(a) + e[8]) / e[0];
  const qy = (Math.sign(b) + e[9]) / e[5];
  const qz = -1;
  const qw = (1 + e[10]) / e[14];
  const k = 2 / (a * qx + b * qy + c * qz + d * qw);
  e[2] = a * k;
  e[6] = b * k;
  e[10] = c * k + 1;
  e[14] = d * k;
}
