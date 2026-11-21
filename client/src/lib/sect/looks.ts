/**
 * Looks: whole-frame moods for /sect, picked with ?look=<id> in development only (runtime.ts
 * parseSectParams). A look is a set of overrides of numbers the page already has: the sky's and the
 * haze's colours, the mist, the baked surfaces' grade, the live light's balance, the sun shafts, the
 * bloom, the vignette. It also turns on the few things only a look uses (FRAME_LOOK): a grade of the
 * whole frame (in the post pass after the sun shafts, before the bloom; on Low at the end of each
 * shader), stars, the sky's sun.
 *
 * A forced look's overrides are written once, before any shader is built (experience/look-switch.ts),
 * into the tables they name. The journey (journey.ts, the page's default) blends them by camera
 * frame into its own copies instead, run-time levers only. The time of day (day-look.ts, a preview)
 * blends two of them, or one and today's dusk, by the Pacific clock.
 *
 * Pure data, maths and GLSL strings (no three.js), so it is testable.
 */
import { glslFloat, glslVec3, hexToLinear, WARM, warmKeepGlsl } from "./glsl";
import { unitTint } from "./look";
import { RANGE_HAZE_HOLDS } from "./range-look";
import { LOOK_IDS, parseLookParam, type LookId } from "./runtime";
import type { Vec3 } from "./types";

// The ids and their parsing live in runtime.ts with the page's other URL options, so the page's
// main bundle (which reads those) does not carry this table.
export { LOOK_IDS, parseLookParam, type LookId };

/**
 * The grade of the whole frame (experience/post/grade.ts), after the sun shafts and before the
 * bloom, the sun's haze, the vignette, the finish and the hue clip (so a lantern's halo keeps its
 * colour under a night grade). Worked in a display-like space (v = c^(1/2.2)),
 * so the curve's pivot sits where the eye puts mid grey: the S-curve on each channel, the split
 * tone on luminance. Glows (a pixel whose brightest channel is over 1: lanterns, windows, runes,
 * fire) skip it and are only scaled.
 */
export interface FrameGrade {
  /** 0 = no grade at all (the effect is not built), 1 = the full grade. */
  amount: number;
  /** Linear gain on the frame. */
  exposure: number;
  /** White balance: the frame times this colour's hue (luminance 1, look.ts unitTint). */
  balance: string;
  /** S-curve on each channel's display value around `pivot` (1 = none, above 1 more contrast). */
  contrast: number;
  pivot: number;
  /**
   * Split tone by display luminance: below the crossover the frame leans toward `shadowTint`, above
   * it toward `highlightTint`, blended over splitPivot +- splitWidth. At golden hour a shaded
   * flagstone is a mid tone, so the crossover sits above mid grey.
   */
  splitPivot: number;
  splitWidth: number;
  shadowTint: string;
  shadowAmount: number;
  highlightTint: string;
  highlightAmount: number;
  /** 1 = unchanged. */
  saturation: number;
  /** Saturation of strongly red pixels instead (lacquer, banners): ink wash keeps its reds. */
  redSaturation: number;
  /** The darks lifted toward this colour (linear amount at black, fading out by mid grey), so night keeps detail. */
  lift: number;
  liftColor: string;
  /** Glows: brightest channel from glowFrom (none) to glowTo (all) skip the grade, times glowGain (faded in with the amount). */
  glowFrom: number;
  glowTo: number;
  glowGain: number;
  /**
   * Warm light keeps its colour (0 = off, 1 = all of it): where the frame's own colour is amber,
   * orange or red (warmWeight), that share of the pixel skips the grade, as a glow does. The
   * night's blue balance and split tone would otherwise turn a lantern's light on stone pink or
   * beige, and its exposure would leave it dimmer than the moonlit stone round it. Grey, blue and
   * green pixels (moonlit stone, the sky, grass) are graded as before.
   */
  warmKeep: number;
  /**
   * The kept warm light's blue times this (1 = as it is), on salmon, orange and amber only
   * (warmKept: pink and lacquer red keep theirs). Lantern light on pale stone that the cool key
   * lights too comes out salmon; with less blue it reads amber.
   */
  warmBlue: number;
}

/** What only a look uses. Every default here is "off", which is what the page does without a look. */
export interface FrameLook {
  grade: FrameGrade;
  /** Stars on the sky dome (0 = none, 1 = a clear night's). */
  stars: number;
  /** The sky's sun (its glow, its disc, the glint in reflections) times this: 0 at night. */
  skySun: number;
  /** The cloud sea's shaded hollows (scene.tsx Atmosphere). */
  cloudSeaShade: string;
  /**
   * How much the abode and the summit, baked under their own night light in round 61, show it (1),
   * or are pulled back toward the sunset bake the other chunks hold (0): night-bake.ts. 0 by day
   * and at sunset, 1 under the moon look; the journey switches it over a short stretch (journey.ts
   * EDGE) between the scroll and the formation.
   */
  nightBake: number;
}

/** The levers a look may set that live only here. Written by a look (look-switch.ts), read where they are used. */
export const FRAME_LOOK: FrameLook = {
  grade: {
    amount: 0,
    exposure: 1,
    balance: "#ffffff",
    contrast: 1,
    pivot: 0.45,
    splitPivot: 0.45,
    splitWidth: 0.3,
    shadowTint: "#ffffff",
    shadowAmount: 0,
    highlightTint: "#ffffff",
    highlightAmount: 0,
    saturation: 1,
    redSaturation: 1,
    lift: 0,
    liftColor: "#000000",
    glowFrom: 1,
    glowTo: 1.4,
    glowGain: 1,
    warmKeep: 0,
    warmBlue: 1,
  },
  stars: 0,
  skySun: 1,
  cloudSeaShade: "#8f93ad",
  nightBake: 0,
};

/** A lever's value: a number, a colour or a fixed-length vector. */
export type LeverValue = number | string | readonly number[];

/**
 * Where a lever lives:
 * - sect: look.ts SECT_LOOK (haze, mist, sky, clouds, mist puffs, the baked surfaces' grade, sun haze, twilight)
 * - live: live.ts LIVE_LOOK (the live light's balance at the lit stop)
 * - lux: lux.ts LUX (contact shade, sun shafts, the finish)
 * - atmos: post.ts ATMOS (cloud shade, bloom)
 * - range: range-look.ts RANGE_LOOK (the haze per stop)
 * - frame: FRAME_LOOK above
 * - meta: the scene's meta.json after look.ts applyLook (the sun's and the moon's colour, the vignette)
 */
export type LookTarget = "sect" | "live" | "lux" | "atmos" | "range" | "frame" | "meta";

export const LOOK_TARGETS: readonly LookTarget[] = ["sect", "live", "lux", "atmos", "range", "frame", "meta"];

/** Overrides by target, each a map of dotted paths ("sky.zenith") to values. */
export type LookPatch = Partial<Record<LookTarget, Readonly<Record<string, LeverValue>>>>;

export interface Look {
  id: LookId;
  /** One line: what it is meant to look like. */
  note: string;
  patch: LookPatch;
}

// The twilight (look.ts SECT_LOOK.twilight) blends the sky toward dusk from the jade slip to the
// summit. Each look gives it its own end, so the last stops keep the look.
function twilight(t: {
  zenith: string;
  mid: string;
  horizon: string;
  sunHorizon: string;
  haze: string;
  cloudSea: string;
  cloudSunLit: string;
  cloudLit: string;
  cloudShade: string;
  cloudRim: string;
  coverage: number;
}): Record<string, LeverValue> {
  return Object.fromEntries(Object.entries(t).map(([k, v]) => [`twilight.${k}`, v]));
}

/**
 * The per-stop haze times k. From the page's own numbers (RANGE_HAZE_HOLDS), never from
 * RANGE_LOOK, which a look writes: a hot reload of this module after that would scale it twice.
 */
function hazeHolds(k: number): Record<string, LeverValue> {
  return Object.fromEntries(Object.entries(RANGE_HAZE_HOLDS).map(([id, v]) => [`haze.holds.${id}`, Math.round(v * k * 100) / 100]));
}

export const LOOKS: Readonly<Record<LookId, Look>> = {
  /**
   * Golden hour: the low sun is the star. Gold key and rim light, long shadows that lean teal, a sky
   * from orange at the horizon to teal above, thick warm haze in bands, strong shafts.
   */
  gold: {
    id: "gold",
    note: "Golden hour: gold light, teal shadows, an orange-to-teal sky, warm haze in bands, sun shafts.",
    patch: {
      sect: {
        "haze.color": "#e0a27c",
        "haze.sunColor": "#ffb45e",
        "haze.densityScale": 1.6,
        "haze.coolColor": "#6f9fae",
        "haze.coolMix": 0.85,
        "haze.extinction": [0.6, 1.0, 1.7],
        "haze.desaturate": 0.45,
        "haze.aerialDepth": 0.22,
        "haze.clear": 60,
        "mist.density": 0.003,
        "mist.falloff": 55,
        "mist.start": 120,
        "sky.zenith": "#2a6a82",
        // Warm above the horizon glow (it was a teal grey, #7fa3a6): the gate's sky reads as sunrise.
        "sky.mid": "#b4a493",
        "sky.horizon": "#ffa65e",
        "sky.sunHorizon": "#ffc864",
        "sky.gradeMix": 1,
        "sky.haze": 0.6,
        "skyClouds.sunLit": "#ffc067",
        "skyClouds.lit": "#f29a76",
        "skyClouds.shade": "#5c7a90",
        "skyClouds.rim": "#fff2c4",
        "skyClouds.coverage": 0.48,
        "puffs.lit": "#ffcf94",
        "puffs.shade": "#8a98a6",
        "puffs.rim": "#ffd37e",
        "grade.exposure": 1.45,
        "grade.contrast": 1.32,
        "grade.shadowTint": "#4f8ea0",
        // Paler than the sun (#ffb874 at saturation 1 turned sunlit cliffs and the gate's far piers
        // a hot orange, and #ffc488 still left the piers behind the gate mustard).
        "grade.highlightTint": "#ffd2a6",
        "grade.split": 0.25,
        "grade.splitShadow": 0.8,
        "grade.saturation": 0.94,
        "cloudSeaColor": "#f4ba84",
        "cloudFogColor": "#d9ae98",
        "water.skyLow": "#e7a77c",
        "water.skyHigh": "#3f7f93",
        "sunHaze.color": "#ffa24a",
        "sunHaze.strength": 0.75,
        "trees.rim": "#ffb766",
        "trees.rimStrength": 0.6,
        "surfaces.mountains": "#86929e",
        "moonHalo.day": 0.12,
        "moonHalo.twilight": 0.3,
        ...twilight({
          zenith: "#1f5268",
          mid: "#6f9196",
          horizon: "#f59a5c",
          sunHorizon: "#ffc061",
          haze: "#c98d74",
          cloudSea: "#e3a47c",
          cloudSunLit: "#ffb35e",
          cloudLit: "#e8896a",
          cloudShade: "#4d6680",
          cloudRim: "#ffe3a8",
          coverage: 0.45,
        }),
      },
      live: { sunGain: 1.5, keyGain: 1.25, ambientGain: 0.72, saturation: 1 },
      lux: {
        "shafts.color": "#ffae5a",
        "shafts.gain": 4,
        "shafts.air": 5,
        "shafts.dim": 1.3,
        "shafts.shade": 0.45,
        "shafts.dimMax": 0.45,
        "ao.tint": [1.0, 1.02, 1.12],
      },
      atmos: { "bloom.intensity": 1.35, "cloudShadow.strength": 0.22 },
      range: hazeHolds(1.45),
      frame: {
        "grade.amount": 1,
        "grade.exposure": 1.02,
        "grade.balance": "#fff1e2",
        "grade.contrast": 1.3,
        "grade.pivot": 0.45,
        "grade.splitPivot": 0.62,
        "grade.splitWidth": 0.22,
        "grade.shadowTint": "#2f8a9c",
        "grade.shadowAmount": 0.55,
        "grade.highlightTint": "#ffb469",
        "grade.highlightAmount": 0.2,
        // Under 1: the per-channel curve and the teal split already add colour, and at 1 the abode's
        // sunlit cliff went neon orange with olive streaks.
        "grade.saturation": 0.88,
        // 1.1 also caught sunlit orange stone (it reads as red-led): the piers seen through the gate
        // went neon mustard. Lacquer keeps its red at 1.
        "grade.redSaturation": 1.0,
        "grade.glowGain": 1.2,
        cloudSeaShade: "#6d8698",
      },
      meta: { "sun.color": "#ff9c42", vignette: 0.32 },
    },
  },
  /**
   * Moonlit night: deep blue, the moon as the key light (cool silver on what the bake lit, dark blue
   * shade that keeps its detail), a dark starry sky, the lanterns, windows, fire and glyphs the only
   * warm things, pale blue mist in the valleys.
   */
  moon: {
    id: "moon",
    note: "Moonlit night: silver-blue light, dark blue shade with detail, stars, warm glows, pale mist.",
    patch: {
      sect: {
        "haze.color": "#33456c",
        "haze.sunColor": "#4d6290",
        "haze.densityScale": 1.2,
        "haze.coolColor": "#3d5590",
        "haze.coolMix": 0.5,
        "haze.extinction": [1.2, 1.0, 0.8],
        "haze.desaturate": 0.6,
        "mist.density": 0.0035,
        "mist.falloff": 50,
        "mist.start": 110,
        "sky.zenith": "#050a1c",
        "sky.mid": "#0f1a3a",
        "sky.horizon": "#2a3a64",
        "sky.sunHorizon": "#33467a",
        "sky.gradeMix": 1,
        "sky.haze": 0.55,
        "skyClouds.sunLit": "#5a6e9e",
        "skyClouds.lit": "#435684",
        "skyClouds.shade": "#141d38",
        "skyClouds.rim": "#a9c0f0",
        "skyClouds.coverage": 0.42,
        "puffs.lit": "#a9bde6",
        "puffs.shade": "#34466e",
        "puffs.rim": "#d6e4ff",
        // Since the night re-bake (2026-11-17, docs/scene/night-r61.md) the abode and summit hold
        // their own lantern light, so the surfaces keep its colour, and its dim edges and the summit's
        // shaded rock are lifted: was exposure 0.95, contrast 1.12, highlight tint #cbe0ff, saturation
        // 0.72, and today's green tame (0.45) and shoulder (0.74). The shoulder keeps a lantern's
        // brightest pool (the abode's moon gate) under the frame grade's glow line (0.85).
        "grade.exposure": 1.2,
        "grade.contrast": 0.85,
        "grade.shadowTint": "#5a80c0",
        "grade.highlightTint": "#ffffff",
        "grade.split": 0.45,
        "grade.splitShadow": 0.7,
        "grade.saturation": 1.0,
        "grade.greenTame": 0.1,
        "grade.shoulder": 0.45,
        "cloudSeaColor": "#5c6f9c",
        "cloudFogColor": "#3c4d78",
        "water.skyLow": "#2e3f68",
        "water.skyHigh": "#0c1530",
        "sunHaze.strength": 0,
        "trees.rim": "#9fb6ec",
        "trees.rimStrength": 0.25,
        "surfaces.mountains": "#3a4a72",
        "surfaces.ground": "#1c2236",
        "moonHalo.day": 0.75,
        "moonHalo.twilight": 0.85,
        ...twilight({
          zenith: "#040818",
          mid: "#0d1734",
          horizon: "#26365e",
          sunHorizon: "#2e4070",
          haze: "#2f4068",
          cloudSea: "#55689a",
          cloudSunLit: "#55689a",
          cloudLit: "#3f5180",
          cloudShade: "#121a34",
          cloudRim: "#a3b9ea",
          coverage: 0.4,
        }),
      },
      // The two night stops carry their own baked light now: the live light adds it as the bake did
      // (was 1.25, 1.1, 0.9, 0.85, tuned to turn a sunset bake into night).
      live: { sunGain: 1, keyGain: 1, ambientGain: 1, saturation: 1 },
      // No sun shafts or cloud shade at night: both march along the scene's sunset sun, and the
      // summit's light comes from the moon's side (were shafts 1.2, dim 1.0, cloud shade 0.1).
      lux: { "shafts.color": "#9fb8ff", "shafts.gain": 0, "shafts.dim": 0, "shafts.shade": 0, "finish.grain": 2.2, "ao.tint": [1.0, 0.98, 0.9] },
      atmos: { "bloom.intensity": 2, "cloudShadow.strength": 0 },
      range: hazeHolds(1.1),
      frame: {
        "grade.amount": 1,
        "grade.exposure": 0.62,
        "grade.balance": "#a6c6ff",
        "grade.contrast": 1.08,
        "grade.pivot": 0.42,
        "grade.shadowTint": "#27508f",
        "grade.shadowAmount": 0.55,
        "grade.highlightTint": "#d0e4ff",
        "grade.highlightAmount": 0.3,
        "grade.saturation": 0.62,
        "grade.redSaturation": 0.7,
        // Enough that eaves and corners keep a little navy detail instead of going black.
        "grade.lift": 0.018,
        "grade.liftColor": "#1d2c5c",
        "grade.glowFrom": 0.85,
        "grade.glowTo": 1.2,
        "grade.glowGain": 2.6,
        // Lantern light keeps its amber against the blue (looks.ts warmWeight): the grade above would
        // turn it pink or beige and darken it under the moonlit stone.
        "grade.warmKeep": 1,
        "grade.warmBlue": 0.5,
        stars: 1,
        skySun: 0,
        cloudSeaShade: "#1f2a4c",
        // The abode and the summit show the night light they were baked under (night-bake.ts).
        nightBake: 1,
      },
      meta: { "sun.color": "#b9cdf5", "moon.color": "#f3f6ff", vignette: 0.34 },
    },
  },
  /**
   * Ink-wash mist (shan shui): a pale misty morning, high-key and soft, colour muted toward grey-green
   * and ink blue with the buildings' reds kept, heavy mist in layers, far things fading to paper.
   */
  ink: {
    id: "ink",
    note: "Ink-wash mist: pale and soft, grey-green and ink blue with the reds kept, peaks rising out of white.",
    patch: {
      sect: {
        "haze.color": "#e6e3da",
        "haze.sunColor": "#f2ede2",
        "haze.densityScale": 2.6,
        "haze.coolColor": "#c4ccd0",
        "haze.coolMix": 0.35,
        "haze.extinction": [1.0, 1.0, 1.08],
        "haze.desaturate": 0.9,
        "haze.aerialDepth": 0.16,
        "haze.clear": 40,
        "mist.density": 0.007,
        "mist.falloff": 75,
        "mist.start": 70,
        "sky.zenith": "#c3cacc",
        "sky.mid": "#dedcd4",
        "sky.horizon": "#eeebe3",
        "sky.sunHorizon": "#f3eee2",
        "sky.gradeMix": 1,
        "sky.haze": 1.4,
        "skyClouds.sunLit": "#f6f3ec",
        "skyClouds.lit": "#ebe8e0",
        "skyClouds.shade": "#b4bbbe",
        "skyClouds.rim": "#ffffff",
        "skyClouds.coverage": 0.3,
        "puffs.lit": "#f6f4ee",
        "puffs.shade": "#c6cacb",
        "puffs.rim": "#ffffff",
        "puffs.opacity": 1,
        "puffs.areaThin": 0.8,
        // A little under day's: at 1.44 white marble paving went to paper white under the haze.
        "grade.exposure": 1.38,
        "grade.contrast": 1.3,
        "grade.shadowTint": "#4f5f70",
        "grade.highlightTint": "#f4efe2",
        "grade.split": 0.25,
        "grade.splitShadow": 0.55,
        "grade.greenTame": 0.7,
        "cloudSeaColor": "#efede6",
        "cloudFogColor": "#e8e6df",
        "water.skyLow": "#e6e3da",
        "water.skyHigh": "#c3cacc",
        "sunHaze.color": "#fff7ea",
        "sunHaze.strength": 0.12,
        "trees.rimStrength": 0.12,
        "surfaces.mountains": "#c9cdcc",
        "moonHalo.day": 0.1,
        "moonHalo.twilight": 0.18,
        ...twilight({
          zenith: "#b9c1c4",
          mid: "#d6d5ce",
          horizon: "#e9e6de",
          sunHorizon: "#efe9dc",
          haze: "#e0ddd5",
          cloudSea: "#eae8e1",
          cloudSunLit: "#f3f0e8",
          cloudLit: "#e6e3db",
          cloudShade: "#aeb6b9",
          cloudRim: "#ffffff",
          coverage: 0.3,
        }),
      },
      live: { sunGain: 0.7, keyGain: 0.85, ambientGain: 1.3, saturation: 0.8, specular: 0.25 },
      lux: { "shafts.gain": 0.3, "shafts.dim": 0.3, "shafts.shade": 0.1, "shafts.color": "#fff6e6", "finish.toe": 0.4, "ao.tint": [1, 1, 1], "ao.strength": 1 },
      atmos: { "bloom.intensity": 0.7, "cloudShadow.strength": 0.06 },
      range: hazeHolds(2.2),
      frame: {
        "grade.amount": 1,
        "grade.exposure": 1.0,
        "grade.balance": "#f4f5f2",
        "grade.contrast": 1.08,
        "grade.pivot": 0.5,
        "grade.shadowTint": "#30404f",
        "grade.shadowAmount": 0.4,
        "grade.highlightTint": "#f6f0e2",
        "grade.highlightAmount": 0.3,
        "grade.saturation": 0.32,
        "grade.redSaturation": 1.05,
        "grade.glowGain": 0.9,
        skySun: 0.35,
        cloudSeaShade: "#c8cccc",
      },
      meta: { "sun.color": "#f4ead8", vignette: 0.1 },
    },
  },
  /**
   * A clear day: a blue sky that pales to the horizon, white clouds, neutral sun, fresh greens, light
   * clean haze that turns far peaks blue. The bake's sun is low, so the shadows stay long: it reads
   * as mid-morning or mid-afternoon. The bake is warm, so the frame grade cools it toward neutral.
   */
  day: {
    id: "day",
    note: "Clear day: a blue sky pale at the horizon, white clouds, neutral sun, fresh greens, far peaks going blue.",
    patch: {
      sect: {
        "haze.color": "#b8d0e6",
        "haze.sunColor": "#eef2e6",
        "haze.densityScale": 0.95,
        "haze.coolColor": "#9dc0e6",
        "haze.coolMix": 0.7,
        // Nearly even: the bake is warm, and a haze that takes blue much faster than red leaves far
        // rock mauve. The haze's own blue and the desaturation turn it blue instead.
        "haze.extinction": [1.0, 1.0, 1.15],
        "haze.desaturate": 0.7,
        "haze.aerialDepth": 0.2,
        "haze.clear": 90,
        "mist.density": 0.0008,
        "mist.falloff": 45,
        "mist.start": 160,
        "sky.zenith": "#3c78cc",
        "sky.mid": "#74ace6",
        "sky.horizon": "#cce2f2",
        "sky.sunHorizon": "#eef2ea",
        "sky.gradeMix": 1,
        "sky.haze": 0.6,
        "skyClouds.sunLit": "#ffffff",
        "skyClouds.lit": "#f3f6fa",
        "skyClouds.shade": "#a8b9d0",
        "skyClouds.rim": "#ffffff",
        "skyClouds.coverage": 0.42,
        "puffs.lit": "#ffffff",
        "puffs.shade": "#b9c6d6",
        "puffs.rim": "#ffffff",
        // 1.5 left the mission hall's marble plaza near white at noon.
        "grade.exposure": 1.46,
        "grade.contrast": 1.16,
        "grade.shadowTint": "#9fb4d8",
        // Cool: the bake's sun is orange, and this takes the sunlit faces back toward neutral.
        "grade.highlightTint": "#d4e2ff",
        "grade.split": 0.4,
        "grade.splitShadow": 0.35,
        "grade.saturation": 0.92,
        "grade.greenTame": 0.15,
        // Highlights roll off from here (today's 0.74): the white marble paving kept its slabs
        // instead of clipping to paper white, and the mid tones did not move.
        "grade.shoulder": 0.5,
        "cloudSeaColor": "#f4f7fb",
        "cloudFogColor": "#cbd8e6",
        "water.skyLow": "#cadcef",
        "water.skyHigh": "#5a90d6",
        "sunHaze.color": "#fff6e0",
        "sunHaze.strength": 0.1,
        "trees.rim": "#fff2d6",
        "trees.rimStrength": 0.2,
        "surfaces.mountains": "#8ea6c8",
        "moonHalo.day": 0.04,
        "moonHalo.twilight": 0.06,
        ...twilight({
          zenith: "#336fc4",
          mid: "#72a4de",
          horizon: "#cadef0",
          sunHorizon: "#eceee8",
          haze: "#b6cadf",
          cloudSea: "#eef3f9",
          cloudSunLit: "#ffffff",
          cloudLit: "#eef2f8",
          cloudShade: "#a0b2ca",
          cloudRim: "#ffffff",
          coverage: 0.4,
        }),
      },
      live: { sunGain: 1.25, keyGain: 1.1, ambientGain: 1.1, saturation: 1.05 },
      lux: { "shafts.color": "#fff6e4", "shafts.gain": 0.5, "shafts.dim": 0.6, "ao.tint": [1.03, 1.0, 0.97] },
      atmos: { "bloom.intensity": 0.75, "cloudShadow.strength": 0.24 },
      range: hazeHolds(0.85),
      frame: {
        "grade.amount": 1,
        "grade.exposure": 1.04,
        "grade.balance": "#f2f6ff",
        "grade.contrast": 1.1,
        "grade.pivot": 0.45,
        "grade.splitPivot": 0.5,
        "grade.splitWidth": 0.3,
        "grade.shadowTint": "#6a90c0",
        "grade.shadowAmount": 0.18,
        // Yellow, not red: a red lean on a blue sky turns it lilac.
        "grade.highlightTint": "#fffbea",
        "grade.highlightAmount": 0.08,
        "grade.saturation": 1.05,
        "grade.redSaturation": 1.0,
        "grade.glowGain": 0.85,
        cloudSeaShade: "#9fb1c8",
      },
      // A paler moon by day.
      meta: { "sun.color": "#fff3e0", "moon.color": "#dce6f4", vignette: 0.14 },
    },
  },
};

// ---------------------------------------------------------------------------------------------
// Writing a look into the tables

type Node = Record<string, unknown>;

function isNode(v: unknown): v is Node {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

const HEX = /^#[0-9a-f]{6}$/i;

/**
 * Why `value` cannot go at `path` in `root` (null when it can): the path must lead to a value that
 * is there already, of the same kind (a number, a colour, a vector of the same length).
 */
export function leverProblem(root: unknown, path: string, value: LeverValue): string | null {
  const keys = path.split(".");
  let node: unknown = root;
  for (const k of keys.slice(0, -1)) {
    if (!isNode(node) || !Object.prototype.hasOwnProperty.call(node, k)) return `${path}: no such lever`;
    node = node[k];
  }
  const last = keys[keys.length - 1];
  if (!isNode(node) || !Object.prototype.hasOwnProperty.call(node, last)) return `${path}: no such lever`;
  const was = node[last];
  if (typeof was === "number") return typeof value === "number" && Number.isFinite(value) ? null : `${path}: wants a number`;
  if (typeof was === "string") {
    if (typeof value !== "string") return `${path}: wants a string`;
    return HEX.test(was) && !HEX.test(value) ? `${path}: wants a #rrggbb colour` : null;
  }
  if (Array.isArray(was) && was.every((x) => typeof x === "number")) {
    return Array.isArray(value) && value.length === was.length && value.every((x) => typeof x === "number" && Number.isFinite(x))
      ? null
      : `${path}: wants ${was.length} numbers`;
  }
  return `${path}: not a lever (a group, not a value)`;
}

/** The value at `path` in `root` when it is a lever (a number, a string or a list of numbers), else undefined. */
export function readLever(root: unknown, path: string): LeverValue | undefined {
  let node: unknown = root;
  for (const k of path.split(".")) {
    if (!isNode(node) || !Object.prototype.hasOwnProperty.call(node, k)) return undefined;
    node = node[k];
  }
  if (typeof node === "number" || typeof node === "string") return node;
  if (Array.isArray(node) && node.every((x) => typeof x === "number")) return node as readonly number[];
  return undefined;
}

/** Every problem with a set of overrides on `root` (empty when all of them fit). */
export function leverProblems(root: unknown, levers: Readonly<Record<string, LeverValue>>): string[] {
  return Object.entries(levers)
    .map(([path, value]) => leverProblem(root, path, value))
    .filter((p): p is string => p !== null);
}

/**
 * Writes the overrides into `root` in place (the tables are read when shaders are built, so a look
 * is written before that). Throws on any lever that does not fit, before writing anything.
 */
export function writeLevers(root: object, levers: Readonly<Record<string, LeverValue>>): void {
  const problems = leverProblems(root, levers);
  if (problems.length > 0) throw new Error(`look: ${problems.join("; ")}`);
  for (const [path, value] of Object.entries(levers)) {
    const keys = path.split(".");
    let node = root as Node;
    for (const k of keys.slice(0, -1)) node = node[k] as Node;
    node[keys[keys.length - 1]] = Array.isArray(value) ? [...value] : value;
  }
}

/** A copy of `root` with the overrides in it (the original is left as it was). */
export function withLevers<T extends object>(root: T, levers: Readonly<Record<string, LeverValue>> | undefined): T {
  if (!levers || Object.keys(levers).length === 0) return root;
  const copy = structuredClone(root);
  writeLevers(copy, levers);
  return copy;
}

// ---------------------------------------------------------------------------------------------
// The frame grade's maths (mirrored by frameGradeGlsl)

const LUMA: Vec3 = [0.2126, 0.7152, 0.0722];

function luma(c: Vec3): number {
  return c[0] * LUMA[0] + c[1] * LUMA[1] + c[2] * LUMA[2];
}

function smoothstep(a: number, b: number, x: number): number {
  const t = Math.min(Math.max((x - a) / Math.max(b - a, 1e-6), 0), 1);
  return t * t * (3 - 2 * t);
}

/** The S-curve on a display value v (0..1) around pivot p: power k below it, mirrored above. */
export function frameCurve(v: number, p: number, k: number): number {
  const x = Math.min(Math.max(v, 0), 1);
  const q = Math.min(Math.max(p, 0.05), 0.95);
  return x < q ? q * Math.pow(x / q, k) : 1 - (1 - q) * Math.pow((1 - x) / (1 - q), k);
}

/** How red-led a colour is (0 grey or any other hue, 1 lacquer red): the red saturation's weight. */
export function redWeight(c: Vec3): number {
  const r = Math.max(c[0], 1e-4);
  return smoothstep(0.45, 0.7, (c[0] - Math.max(c[1], c[2])) / r);
}

/** The hue as glsl.ts WARM measures it: (g - b) / (r - b), 0 at red, 1 at yellow. */
function warmHue(c: Vec3): number {
  return (c[1] - c[2]) / Math.max(c[0] - c[2], 1e-4);
}

/**
 * How much a colour reads as warm light (0 grey, blue, green or yellow-green; 1 amber, orange,
 * red): red leads blue by enough, and the hue is on the red side of yellow (glsl.ts WARM). Grass,
 * bamboo and the bake's ochre-stained grey rock stay out.
 */
export function warmWeight(c: Vec3): number {
  const lead = (c[0] - c[2]) / Math.max(c[0], 1e-4);
  return smoothstep(WARM.lead[0], WARM.lead[1], lead) * (1 - smoothstep(WARM.hue[0], WARM.hue[1], warmHue(c)));
}

/**
 * The colour warm light keeps (FrameGrade.warmKeep): the frame's own, with the blue of salmon,
 * orange and amber times `blue` (warmBlue); pink and lacquer red keep their blue. Mirrors glsl.ts
 * warmKeepGlsl.
 */
export function warmKept(c: Vec3, blue: number): Vec3 {
  return [c[0], c[1], c[2] * (1 + (blue - 1) * smoothstep(WARM.blueHue[0], WARM.blueHue[1], warmHue(c)))];
}

/** TypeScript mirror of the frame grade (linear in, linear out). */
export function frameGradeLinear(c0: Vec3, g: FrameGrade): Vec3 {
  const x0 = c0.map((v) => Math.max(v, 0)) as Vec3;
  const glow = smoothstep(g.glowFrom, g.glowTo, Math.max(...x0));
  const bal = unitTint(g.balance);
  let c = x0.map((v, i) => v * g.exposure * bal[i]) as Vec3;
  // The curve on each channel (a channel over 1 keeps its value): like film, the mids gain colour
  // and the lights go toward white instead of toward a hotter hue.
  c = c.map((x) => (x < 1 ? Math.pow(frameCurve(Math.pow(x, 1 / 2.2), g.pivot, g.contrast), 2.2) : x)) as Vec3;
  // The split tone and the lift, by display luminance.
  const v2 = Math.pow(Math.min(luma(c), 1), 1 / 2.2);
  const ws = 1 - smoothstep(g.splitPivot - g.splitWidth, g.splitPivot + Math.max(g.splitWidth, 1e-3), v2);
  const st = unitTint(g.shadowTint);
  const ht = unitTint(g.highlightTint);
  c = c.map((x, i) => x * (1 + (st[i] - 1) * g.shadowAmount * ws) * (1 + (ht[i] - 1) * g.highlightAmount * (1 - ws))) as Vec3;
  const lift = hexToLinear(g.liftColor);
  const lw = g.lift * Math.pow(1 - v2, 4);
  c = c.map((x, i) => x + lift[i] * lw) as Vec3;
  const sat = g.saturation + (g.redSaturation - g.saturation) * redWeight(c);
  const lc = luma(c);
  c = c.map((x) => Math.max(lc + (x - lc) * sat, 0)) as Vec3;
  // Warm light keeps its own colour and brightness, amber's blue cut by warmBlue.
  const wk = warmWeight(x0) * g.warmKeep;
  const kept = warmKept(x0, g.warmBlue);
  c = c.map((x, i) => x + (kept[i] - x) * wk) as Vec3;
  const graded = c.map((x, i) => x0[i] + (x - x0[i]) * g.amount) as Vec3;
  // The glows' gain fades with the amount, so a grade fading in does not jump the glows.
  const gain = 1 + (g.glowGain - 1) * Math.min(g.amount, 1);
  return graded.map((x, i) => x + (x0[i] * gain - x) * glow) as Vec3;
}

/** GLSL for the grade: `vec3 sectFrameGrade( vec3 linear )`. Mirrors frameGradeLinear. */
export function frameGradeGlsl(g: FrameGrade): string {
  const f = glslFloat;
  return /* glsl */ `
float sectFrameCurve( float v, float p, float k ) {
  float x = clamp( v, 0.0, 1.0 );
  // The bases are kept off 0 (glsl.ts POW_BASE_NOTE): a channel at 1 or over lands on pow( 0.0, k ) here.
  return x < p ? p * pow( max( x / p, 1e-6 ), k ) : 1.0 - ( 1.0 - p ) * pow( max( ( 1.0 - x ) / ( 1.0 - p ), 1e-6 ), k );
}
${warmKeepGlsl("sectFrameWarm")}
vec3 sectFrameGrade( vec3 c0 ) {
  const vec3 luma = vec3( 0.2126, 0.7152, 0.0722 );
  vec3 x0 = max( c0, 0.0 );
  float glow = smoothstep( ${f(g.glowFrom)}, ${f(Math.max(g.glowTo, g.glowFrom + 1e-3))}, max( x0.r, max( x0.g, x0.b ) ) );
  vec3 c = x0 * ${f(g.exposure)} * ${glslVec3(unitTint(g.balance))};
  // The curve on each channel (a channel over 1 keeps its value): like film, the mids gain colour
  // and the lights go toward white instead of toward a hotter hue.
  vec3 cv = pow( clamp( c, 1e-6, 1.0 ), vec3( 0.45454545 ) );
  float p = ${f(Math.min(Math.max(g.pivot, 0.05), 0.95))};
  float k = ${f(g.contrast)};
  vec3 cc = pow( vec3( sectFrameCurve( cv.r, p, k ), sectFrameCurve( cv.g, p, k ), sectFrameCurve( cv.b, p, k ) ), vec3( 2.2 ) );
  // Picked, not mixed: mix( cc, c, 1.0 ) still multiplies cc by 0, and 0 times a number that is not
  // one is not one either. In Safari's engine that took the channel (docs/sect/render-probe.md).
  c = vec3( c.r >= 1.0 ? c.r : cc.r, c.g >= 1.0 ? c.g : cc.g, c.b >= 1.0 ? c.b : cc.b );
  // The split tone and the lift, by display luminance.
  float v2 = pow( clamp( dot( c, luma ), 1e-6, 1.0 ), 0.45454545 );
  float ws = 1.0 - smoothstep( ${f(g.splitPivot - g.splitWidth)}, ${f(g.splitPivot + Math.max(g.splitWidth, 1e-3))}, v2 );
  c *= mix( vec3( 1.0 ), ${glslVec3(unitTint(g.shadowTint))}, ${f(g.shadowAmount)} * ws )
    * mix( vec3( 1.0 ), ${glslVec3(unitTint(g.highlightTint))}, ${f(g.highlightAmount)} * ( 1.0 - ws ) );
  c += ${glslVec3(hexToLinear(g.liftColor))} * ( ${f(g.lift)} * pow( max( 1.0 - v2, 1e-6 ), 4.0 ) );
  float red = smoothstep( 0.45, 0.7, ( c.r - max( c.g, c.b ) ) / max( c.r, 1e-4 ) );
  float sat = mix( ${f(g.saturation)}, ${f(g.redSaturation)}, red );
  float lc = dot( c, luma );
  c = max( vec3( lc ) + ( c - vec3( lc ) ) * sat, 0.0 );
  // Warm light keeps its own colour and brightness, amber's blue cut by warmBlue.
  vec4 wk = sectFrameWarm( x0, ${f(g.warmKeep)}, ${f(g.warmBlue)} );
  c = mix( c, wk.rgb, wk.a );
  vec3 graded = mix( x0, c, ${f(g.amount)} );
  return mix( graded, x0 * ${f(1 + (g.glowGain - 1) * Math.min(g.amount, 1))}, glow );
}
`;
}

// ---------------------------------------------------------------------------------------------
// Stars (FRAME_LOOK.stars), for the sky dome's shader

/**
 * GLSL: `float sectStars( vec3 dir )`, a star field on the sky (0 where there is none). The
 * direction is cut into a grid of cells; one cell in about 40 holds a star at a random spot in it,
 * most faint, a few bright. Each is a pixel or two wide whatever the screen, from the grid's size
 * on screen (fwidth). Needs sectHash12 (glsl.ts DITHER_GLSL, in the fog library). `amount`: a
 * number, or a GLSL expression (the sky's uStars uniform, which the journey moves).
 */
export function starsGlsl(amount: number | string = "uStars"): string {
  return /* glsl */ `
float sectStars( vec3 d ) {
  vec3 p = d * 520.0;
  vec3 id = floor( p );
  vec3 f = fract( p );
  float h = sectHash12( id.xy * 1.31 + id.z * 7.17 );
  if ( h < 0.976 ) return 0.0;
  vec3 at = 0.2 + 0.6 * vec3( sectHash12( id.yz + 3.1 ), sectHash12( id.zx + 5.7 ), sectHash12( id.xy + 9.3 ) );
  float w = max( length( fwidth( p ) ), 1e-4 );
  float r = length( f - at );
  float mag = 0.45 + 3.2 * pow( fract( h * 613.7 ), 4.0 );
  return mag * ( 1.0 - smoothstep( 0.0, 0.9 * w + 0.02, r ) ) * ${typeof amount === "number" ? glslFloat(amount) : amount};
}
`;
}
