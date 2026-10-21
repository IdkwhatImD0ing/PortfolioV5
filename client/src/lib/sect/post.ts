/**
 * Atmosphere and finishing passes for /sect's postprocessing (experience/post/atmos.ts): which
 * tier gets which pass, their art-direction numbers, and the small pure maths behind them, so it is
 * testable without three.js.
 *
 * - Cloud shadows: soft patches of shade from clouds overhead, drifting slowly over terrain and
 *   roofs (The Witcher 3's moving cloud shade). Worked out per pixel from the depth buffer in the
 *   post pass, so every baked surface gets them without touching its material. High and Medium.
 * - Hold focus: a slight depth of field that only comes in while the camera rests at a stop and
 *   goes before it moves (never during motion): the far background softens a little and the
 *   stop's subject stays sharp, like a long lens. High only.
 * - Bloom: glows (windows, lanterns, holy fire, runes, formation beams) spread into the air
 *   around them as light does, instead of stopping at their edge as flat colour.
 */
import type { Quality } from "./runtime";
import type { Vec3 } from "./types";

/** What the post pass adds at a quality (the tier's own top, and where the ladder has it now). */
export interface AtmosFeatures {
  cloudShadows: boolean;
  holdFocus: boolean;
}

/**
 * High is the tier with MSAA (tierQuality never gives it 0). Medium has bloom without MSAA; Low has
 * no post pass at all. Once the ladder has dropped bloom (a GPU struggling even on Medium), the
 * cloud shadows go too; once it has dropped MSAA on High, so does the hold focus.
 */
export function atmosFeatures(top: Quality, now: Quality): AtmosFeatures {
  const post = top.post && now.post;
  return {
    cloudShadows: post && now.bloom,
    holdFocus: post && top.msaa > 0 && now.msaa > 0,
  };
}

export const ATMOS = {
  cloudShadow: {
    /** Darkening at the core of a shadow on a sunlit surface (0.16 = 16% darker). */
    strength: 0.16,
    /** Height of the cloud deck the shade falls from (three y, metres). */
    deckY: 700,
    /** Size of one cloud's shade on the deck (metres). */
    scale: 240,
    /** Drift on the deck (metres a second, x and z): the high wind. */
    drift: [2.4, -1.3] as [number, number],
    /** Share of the deck in shade: noise below `cover[0]` is clear, above `cover[1]` full shade. */
    cover: [0.5, 0.74] as [number, number],
    /**
     * Linear luminance band over which a surface counts as lit (shade only where there is light to
     * take away): below lit[0] none; and glows (luminance over glow[0]) fade out by glow[1].
     */
    lit: [0.02, 0.3] as [number, number],
    glow: [1.1, 2.2] as [number, number],
    /** No shade within this many metres of the stop's subject (eased back in over as many again). */
    keepRadius: 45,
  },
  holdFocus: {
    /** Seconds at rest before the focus starts to come in, and how long it takes. */
    delay: 0.6,
    fadeIn: 1.2,
    /** Seconds to go when the camera starts moving (quick: never visible in motion). */
    fadeOut: 0.18,
    /**
     * Blur starts this far behind the subject (times its distance) and is full by `far` times it.
     * The subject and everything near it stays sharp.
     */
    near: 2.5,
    far: 10,
    /** Share of the blurred frame mixed in at full weight (under 1: soft, never smeared). */
    mix: 0.5,
    /** The blurred copy's resolution (share of the frame's): half, the smallest Kawase kernel. */
    resolution: 0.5,
    /** Metres past which the blur eases back out: the moon (6 km) and sky dome stay crisp. */
    cap: [3200, 4500] as [number, number],
  },
  bloom: {
    /**
     * What the bloom's threshold reads: luminance mixed this far toward the brightest channel. A
     * lit window is (1.38, 0.64, 0.18) in linear light, luminance 0.77: under the threshold of 1,
     * so it never bloomed and read as flat orange. Its red channel is well over 1. Marble (0.64 at
     * most), sky (0.86) and sunlit cliffs (0.85) stay under it either way.
     */
    chroma: 0.6,
    intensity: 1,
    /** Mipmap blur radius (0-1): a little tighter than the library's 0.85, so a glow hugs its source. */
    radius: 0.8,
  },
} as const;

/**
 * Where a surface point's shade comes from on the cloud deck: along the sun's ray up to deckY. With
 * the sun 7 degrees up, a metre of height moves the point about 8 m along the sun's bearing, so a
 * cloud's shade on a sun-facing cliff is squashed into a blob about an eighth as tall as it is wide,
 * as it is in a real low-sun landscape. The sun must be above the horizon (dir.y > 0).
 */
export function cloudDeckPoint(p: Vec3, sunDir: Vec3, deckY: number): [number, number] {
  const k = (deckY - p[1]) / Math.max(sunDir[1], 0.02);
  return [p[0] + sunDir[0] * k, p[2] + sunDir[2] * k];
}

/** 0 = clear, 1 = full shade, from a noise value in 0..1 and the cover band. */
export function cloudCover(n: number, cover: readonly [number, number]): number {
  const t = Math.min(Math.max((n - cover[0]) / Math.max(cover[1] - cover[0], 1e-6), 0), 1);
  return t * t * (3 - 2 * t);
}

/**
 * What the camera is doing for the hold focus: at rest at the stop ("still"); a scroll or key
 * pending while the camera still shows the stop's frame, or the view turned off it ("input"); the
 * view itself moving: off the stop's frame along the path, or turning under a drag ("view").
 */
export type HoldMotion = "still" | "input" | "view";

/**
 * Hold focus weight (0 = off, 1 = full) one frame on: comes in over fadeIn once the camera has
 * rested `delay` seconds (`restS`), goes over fadeOut on input, and at once when the view itself
 * moves, so no moving frame ever shows it (a drag turns the view on its first frame, and a scroll
 * near the edge of a stop's dwell moves the camera before a fade would end).
 */
export function holdFocusStep(weight: number, motion: HoldMotion, restS: number, dt: number, c = ATMOS.holdFocus): number {
  const step = Math.min(Math.max(dt, 0), 0.1);
  if (motion === "view") return 0;
  if (motion === "input") return Math.max(0, weight - step / Math.max(c.fadeOut, 1e-3));
  if (restS < c.delay) return weight;
  return Math.min(1, weight + step / Math.max(c.fadeIn, 1e-3));
}

function smoothstep(a: number, b: number, x: number): number {
  const t = Math.min(Math.max((x - a) / Math.max(b - a, 1e-6), 0), 1);
  return t * t * (3 - 2 * t);
}

/**
 * Share of the blurred frame at view distance `d` with the subject at `focus` metres and the hold
 * weight `w` (the shader's maths): none up to near x focus, `mix` by far x focus, and none again
 * past the cap.
 */
export function holdBlur(d: number, focus: number, w = 1, c = ATMOS.holdFocus): number {
  if (!(w > 0)) return 0;
  const t = smoothstep(c.near, c.far, d / Math.max(focus, 1)) * (1 - smoothstep(c.cap[0], c.cap[1], d));
  return w * t * c.mix;
}

/**
 * The stop the camera rests at: the hold within `slack` frames of `frame`, or null (resting
 * between stops gets no hold focus).
 */
export function holdAt<H extends { frame: number }>(holds: readonly H[], frame: number, slack = 1.5): H | null {
  let best: H | null = null;
  for (const h of holds) if (Math.abs(h.frame - frame) <= slack && (!best || Math.abs(h.frame - frame) < Math.abs(best.frame - frame))) best = h;
  return best;
}

/** The hold nearest `frame` along the flight (any distance), or null when there are none. */
export function nearestHold<H extends { frame: number }>(holds: readonly H[], frame: number): H | null {
  let best: H | null = null;
  for (const h of holds) if (!best || Math.abs(h.frame - frame) < Math.abs(best.frame - frame)) best = h;
  return best;
}
