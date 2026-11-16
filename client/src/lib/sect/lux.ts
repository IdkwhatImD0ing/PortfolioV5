/**
 * "Lux": the light the bake cannot hold, worked out on the page each frame (experience/post/ao.ts,
 * shafts.ts, finish.ts). Art-direction numbers and the small pure maths behind them, so they are
 * testable without three.js.
 *
 * The world's light is baked in Blender: every surface arrives as its lit colour, and a bake at a
 * few centimetres a texel cannot keep the thin dark line where a lantern meets the paving, nor
 * anything that hangs in the air. Three passes add those on High:
 *
 * - Contact shade (ao): ground-truth ambient occlusion from the depth buffer. Props sit on the
 *   ground instead of floating over it, eaves and brackets gain depth, railings read as carved.
 * - Sun shafts (shafts): the low sun's light in the haze, cut by whatever stands in its way. A
 *   shadow map of the static world is drawn from the sun (and only redrawn when the camera has
 *   moved far enough), then each pixel's view ray is marched through the haze against it.
 * - Finish (finish): the lens and the print. A filmic shoulder, a little halation round the
 *   brightest light, and a fine grain that only changes when a frame is drawn anyway.
 */
import type { Quality } from "./runtime";
import type { Vec3 } from "./types";

/** Which lux passes a pipeline is built with (the tier's own top) and which run now (the ladder). */
export interface LuxFeatures {
  ao: boolean;
  shafts: boolean;
  finish: boolean;
}

export const LUX_OFF: LuxFeatures = { ao: false, shafts: false, finish: false };

/**
 * What a tier is built with. High (the tier with MSAA) gets all three; Medium gets the finish only
 * (one more term in the merged effect shader, no extra pass); Low has no post chain.
 */
export function luxBuilt(top: Quality): LuxFeatures {
  if (!top.post) return LUX_OFF;
  const high = top.msaa > 0;
  return { ao: high, shafts: high, finish: true };
}

/**
 * What runs now on a chain built for `top`: once the ladder has taken MSAA off a High tier (a GPU
 * that cannot hold it), the two passes with their own render targets rest too. The finish stays
 * (it costs a few instructions a pixel).
 */
export function luxLive(top: Quality, now: Quality): LuxFeatures {
  const built = luxBuilt(top);
  const post = top.post && now.post;
  const strong = post && now.msaa > 0 && now.bloom;
  return { ao: built.ao && strong, shafts: built.shafts && strong, finish: built.finish && post };
}

/** `?lux=` on the page's URL: "0" builds none of it, "ao" / "shafts" show that pass alone as a grey image. */
export type LuxDebug = "off" | "ao" | "shafts" | null;

export function parseLuxParam(search: string): LuxDebug {
  const m = /[?&]lux=([a-z0-9]+)/.exec(search);
  if (!m) return null;
  if (m[1] === "0" || m[1] === "off") return "off";
  if (m[1] === "ao" || m[1] === "shafts") return m[1];
  return null;
}

export const LUX = {
  ao: {
    /** World radius a surface point looks for occluders in (metres): a lantern's foot, an eave's depth. */
    radius: 1.6,
    /** The radius never spans more than this share of the frame's height (close-ups stay cheap and local). */
    maxScreen: 0.12,
    /** Horizon slices per pixel and steps along each side of a slice. */
    slices: 3,
    steps: 4,
    /**
     * The AO buffer is the frame's own size up to this many pixels (a 1080p frame), and scaled down
     * to it above that: a 4K frame works at half size, where a crease is still several pixels wide.
     */
    maxPixels: 2.2e6,
    /** Darkening at full occlusion (0..1), and the curve on the visibility term (above 1: deeper creases). */
    strength: 0.9,
    power: 1.7,
    /**
     * Share of the shade leaves and grass keep (ao.ts tells them by colour): blades and needles are
     * thinner than the radius, and at full strength a lawn or a canopy turns to soot.
     */
    foliage: 0.18,
    /**
     * Occlusion fades out between these view distances (metres): past them a crease is under a
     * pixel wide and the haze has taken the surface anyway.
     */
    fade: [110, 260] as [number, number],
    /** Glows keep their light: no shade on pixels whose linear luminance is over glow[0], eased to glow[1]. */
    glow: [0.95, 1.6] as [number, number],
    /**
     * The shade's colour, as exponents on the darkening per channel: red falls fastest and blue
     * slowest, so creases lean toward the dusk's lavender instead of grey.
     */
    tint: [1.1, 1.02, 0.86] as Vec3,
  },
  shafts: {
    /**
     * The sun's shadow map: a square of this half-width (metres) centred on the camera, seen from
     * the sun, `map` texels a side. It looks `reach` metres toward the sun for what stands in the
     * light's way (the sun is 7 degrees up: a 300 m pillar throws 2.4 km of shade) and `back`
     * metres past the centre.
     */
    box: 640,
    map: 4096,
    reach: 5200,
    back: 1400,
    /** The map is drawn again once the camera is this far (metres) from its centre, or the drawn world changed. */
    refresh: 110,
    /** Seconds between two redraws at least (streaming brings a chunk in over several frames). */
    minInterval: 0.4,
    /** A view ray is marched this far (metres), fading out over the last 30%. */
    maxDist: 520,
    steps: 32,
    /** Depth bias on the shadow test, metres along the sun's ray. */
    bias: 0.7,
    /**
     * The air that catches the light: this many times the haze's own density (the haze is thin, a
     * shaft needs dust), with the haze's height falloff.
     */
    air: 3.0,
    /** The buffer's size as a share of the frame's, and its pixel cap. */
    resolution: 0.5,
    maxPixels: 0.6e6,
    /**
     * The haze the materials draw is lit evenly, as if nothing stood in the sun, and it is tuned.
     * So the shafts never add haze: each ray's lit share is held against the same share averaged
     * over the frame around it (a copy of the buffer `wide` times smaller, blurred). A ray with
     * more light than its surroundings is a shaft and gains light (times `gain`); one with less
     * lies in a shadow and loses a share of the frame's (times `dim`). Open air, lit or shaded
     * alike, stays as it was.
     */
    wide: 8,
    gain: 1.0,
    dim: 0.8,
    /**
     * Broad shade: air in shadow all around (a gorge floor, the lee of a cliff) takes this share
     * of the frame's light per unit of shaded air, so sunlit heights stand over darker depths.
     */
    shade: 0.32,
    /** Shade and dimming together never take more than this share of a pixel. */
    dimMax: 0.22,
    /** The shafts' colour: the low sun's gold. */
    color: "#ffc27c",
    /**
     * Two-lobe phase (Henyey-Greenstein): `forward` toward the sun with weight `mix`, a broad lobe
     * for the rest so side-lit shafts stay visible. Normalised to 1 looking across the light and
     * capped at `max` looking into it.
     */
    phase: { forward: 0.76, broad: 0.18, mix: 0.3, max: 2.4 },
  },
  finish: {
    /**
     * Toe: the darks go deeper and the rest stays. Worked on luminance in a display-like domain
     * (v = l^(1/2.2)): v' = v * (1 - toe * (1 - v)^toePower). Black stays black, white stays white,
     * mid grey moves by about four percent. The haze lifts every dark in the frame a little; this puts
     * the nearest ones back down, so the foreground has weight against the pale distance.
     */
    toe: 0.26,
    toePower: 3,
    /** Saturation after the toe (1 = unchanged): what the deeper darks take, given back as colour. */
    saturation: 1.07,
    /**
     * Sharpening on High (0 = off): the frame's difference from its four neighbours' mean, added
     * back times this, never more than `sharpenMax` of linear light. The bake's texels are several
     * centimetres wide; this gives their edges back some bite.
     */
    sharpen: 0.4,
    sharpenMax: 0.06,
    /** Film grain in 8-bit steps at mid grey, fading out toward white and black. 0 = off. */
    grain: 1.6,
  },
} as const;

/** The AO buffer's scale for a frame of `width` x `height` pixels (1 up to maxPixels, then smaller). */
export function aoScale(width: number, height: number, maxPixels: number = LUX.ao.maxPixels): number {
  const px = Math.max(1, width * height);
  return Math.min(1, Math.sqrt(maxPixels / px));
}

/**
 * How many pixels of the AO buffer `radius` metres span at view distance `z` (metres), for a camera
 * whose projection matrix has `p11` (1 / tan(fovY / 2)) drawing `height` pixels tall.
 */
export function aoRadiusPx(radius: number, z: number, p11: number, height: number): number {
  return (radius * p11 * 0.5 * height) / Math.max(z, 1e-3);
}

/**
 * Multi-bounce fit (Jimenez et al. 2016): light bouncing inside a crease of albedo `albedo` fills
 * some of it back in, so white marble never creases to black the way dark slate does.
 */
export function aoMultiBounce(visibility: number, albedo: number): number {
  const a = 2.0404 * albedo - 0.3324;
  const b = -4.7951 * albedo + 0.6417;
  const c = 2.7552 * albedo + 0.6903;
  return Math.max(visibility, ((visibility * a + b) * visibility + c) * visibility);
}

/** Henyey-Greenstein phase function without its 1 / 4 pi (only ratios are used). */
export function henyeyGreenstein(cos: number, g: number): number {
  const d = 1 + g * g - 2 * g * cos;
  return (1 - g * g) / (d * Math.sqrt(d));
}

/**
 * How much of the sun's light a parcel of air sends toward the eye, for the cosine of the angle
 * between the view ray and the direction to the sun: 1 looking across the light, more looking into
 * it (capped), less looking down-sun.
 */
export function shaftPhase(cos: number, p: { forward: number; broad: number; mix: number; max: number } = LUX.shafts.phase): number {
  const at = (c: number) => p.mix * henyeyGreenstein(c, p.forward) + (1 - p.mix) * henyeyGreenstein(c, p.broad);
  return Math.min(at(cos) / at(0), p.max);
}

function cross(a: Vec3, b: Vec3): Vec3 {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}

function dot(a: Vec3, b: Vec3): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function normalize(a: Vec3): Vec3 {
  const l = Math.hypot(a[0], a[1], a[2]) || 1;
  return [a[0] / l, a[1] / l, a[2] / l];
}

/**
 * Where the sun's shadow map is centred for a camera at `cam`: the camera's own position, moved
 * onto the map's texel grid across the light (so a redraw lands every texel on the same world
 * column as before and the shafts' edges do not jump). `sun` points toward the sun; `texel` is one
 * texel's width in metres.
 */
export function shaftCentre(cam: Vec3, sun: Vec3, texel: number): Vec3 {
  const s = normalize(sun);
  const right = normalize(cross([0, 1, 0], s));
  const up = cross(s, right);
  const snap = (v: number) => Math.round(v / texel) * texel;
  const x = snap(dot(cam, right));
  const y = snap(dot(cam, up));
  const z = dot(cam, s);
  return [right[0] * x + up[0] * y + s[0] * z, right[1] * x + up[1] * y + s[1] * z, right[2] * x + up[2] * y + s[2] * z];
}

/** True once the camera has left the middle of the shadow map (metres from its centre, across the light or along it). */
export function shaftsStale(cam: Vec3, centre: Vec3, refresh: number = LUX.shafts.refresh): boolean {
  return Math.hypot(cam[0] - centre[0], cam[1] - centre[1], cam[2] - centre[2]) > refresh;
}

/** The shafts buffer's scale for a frame of `width` x `height` pixels. */
export function shaftScale(width: number, height: number, c: { resolution: number; maxPixels: number } = LUX.shafts): number {
  const px = Math.max(1, width * height);
  return Math.min(c.resolution, Math.sqrt(c.maxPixels / px));
}
