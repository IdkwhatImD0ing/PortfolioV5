/**
 * The web-side look for /sect: one place for the art-direction numbers that move the real-time
 * render from the Blender film (cool grey haze) toward the golden-hour style frames
 * (out/higgsfield/film/v2/kf_gate.png, kf_mirror.png): warm haze, a peach-to-lavender sky with
 * lit clouds, gold light with lavender shadows on the baked surfaces, falling petals and cranes.
 *
 * Geometry, lighting direction and composition still come from meta.json and the GLBs; this file
 * only changes colours and decoration. Pure data and maths (no three.js), so it is testable.
 */
import { fogConstantsFromMeta, glslFloat, glslVec3, hexToLinear, type FogConstants } from "./glsl";
import type { SectMeta, Vec3 } from "./types";

export interface SectLook {
  haze: {
    /**
     * Haze colour across the sun (the runtime fog colour: it replaces meta.fog.color, the film's
     * cooler grey, in applyLook).
     */
    color: string;
    /** Haze colour looking toward the sun. */
    sunColor: string;
    /** Multiplier on meta.fog.density. */
    densityScale: number;
    /**
     * Hue the haze cools to looking away from the sun. Only the hue counts: it is applied at the
     * haze's own brightness, so the twilight's bluer haze cools the same way.
     */
    coolColor: string;
    /** 0 = no cooling; 1 = the full hue looking straight away from the sun (eased in by angle). */
    coolMix: number;
    /**
     * Aerial perspective: haze optical depth per channel (r, g, b) on fogged surfaces. Real air
     * scatters blue about 5.7x more than red, far too weak to see at this scale; this exaggerated
     * ratio turns far ridges bluer while scenery a few hundred metres off barely moves.
     */
    extinction: Vec3;
    /** Share of a far surface's colour turned to the haze's hue once the haze covers it (0 = none). */
    desaturate: number;
    /**
     * Haze optical depth over which the blue fade and the cooling come in (63% at this depth; the
     * haze is about 0.3 deep 1 km out at terrace height). Thin haze keeps today's warm grey veil, so
     * nearby scenery does not shift; far ridges and the horizon take the full shift.
     */
    aerialDepth: number;
  };
  /**
   * Valley mist: a second, thin exponential layer sitting on the cloud layer's top (gorge floors,
   * under the floating islands). Same colour as the haze; no noise.
   */
  mist: {
    /** Extinction per metre at the cloud top (the haze is 0.00033 per metre at 100 m). 0 = off. */
    density: number;
    /** Metres over which it thins by e upward. */
    falloff: number;
    /** Metres from the camera before it starts (the scenery at hand never fogs). */
    start: number;
  };
  /**
   * Dither in 8-bit steps against banding in the sky and haze gradients: at the end of the post
   * pass (mid and high tiers) and in every fogged material on the low tier. 0 = off.
   */
  dither: number;
  sky: {
    zenith: string;
    mid: string;
    horizon: string;
    /** Horizon colour under the sun. */
    sunHorizon: string;
    /** 0 = Blender's sky image only, 1 = the painted gradient only. */
    gradeMix: number;
    /** Extra haze on the dome (the analytic haze reads thin on the sky). */
    haze: number;
  };
  skyClouds: {
    /** Lit side of the high clouds, toward the sun. */
    sunLit: string;
    /** Lit side away from the sun (pink). */
    lit: string;
    shade: string;
    /** Bright rim where a cloud edge faces the sun. */
    rim: string;
    /** 0-1: share of the sky they cover. */
    coverage: number;
  };
  puffs: {
    lit: string;
    /** Shade side: warm cream-mauve, so the banks read golden hour rather than grey. */
    shade: string;
    /** Silver lining toward the sun. */
    rim: string;
    /** Global opacity scale. */
    opacity: number;
    /** Density scale for puffs near the two areas (they veiled the gate and the gully trees). */
    areaThin: number;
    /** Metres from an area's centre where the thinning applies (fading out over the next half). */
    areaRadius: number;
    /** Soft-particle depth: the fade length where a sprite meets geometry, as a share of its depth. */
    soft: number;
  };
  grade: {
    /** Overall linear gain (exposure) on baked surfaces. */
    exposure: number;
    /** Power curve on luminance around `pivot` (1 = none): darks darker, lights lighter. */
    contrast: number;
    pivot: number;
    /** Split tone: shadows lean toward shadowTint, highlights toward highlightTint (sRGB hex). */
    shadowTint: string;
    highlightTint: string;
    /** 0 = no split tone, 1 = full tint. */
    split: number;
    /**
     * The shadow side's own strength (default `split`): the bake's golden-hour bounce keeps shadows
     * warm, so they need more of the lavender than the highlights need of the gold.
     */
    splitShadow?: number;
    /** 1 = unchanged saturation. */
    saturation: number;
    /**
     * Share of green's lead over red and blue removed (0 = none): lime grass toward olive-gold.
     * Materials that define SECT_KEEP_GREEN skip it (gradeGlsl): the formation's wood flag, whose
     * jade would otherwise read slate blue.
     */
    greenTame: number;
    /** Linear value above which highlights roll off softly toward 1 instead of clipping. */
    shoulder: number;
  };
  cloudSeaColor: string;
  /** Colour of the dense cloud layer that swallows everything under the cloud top. */
  cloudFogColor: string;
  water: {
    /** The Heart-Mirror's glowing face as seen in the pond (linear colour x gain, HDR). */
    mirrorGlow: string;
    mirrorGlowGain: number;
    /**
     * The mirror's parts as the pond's analytic reflection draws them (lib/sect/heart-mirror.ts):
     * the gilt (rim, crest, pearls, cradle), the red lacquer cloud arms, the cyan trigram ring's
     * glow (linear colour x gain) and the dark bronze of its back.
     */
    mirrorRim: string;
    mirrorRimOuter: string;
    mirrorRune: string;
    mirrorRuneGain: number;
    mirrorBronze: string;
    /** Sky reflected near the horizon and overhead. */
    skyLow: string;
    skyHigh: string;
  };
  waterfall: {
    /** Cool blue-white body and foam. */
    color: string;
    foam: string;
    opacity: number;
    mist: string;
  };
  petals: {
    count: number;
    colorA: string;
    colorB: string;
    /** Half-size of a petal (m). */
    size: number;
    /** Radius (m) of the drifting volume around the camera. */
    radius: number;
  };
  cranes: {
    count: number;
    color: string;
    /** Neck, head, the inner wing's trailing edge and the wing tips; the red crown. */
    dark: string;
    crown: string;
  };
  sunHaze: {
    color: string;
    /** Strength of the radial glow toward the sun (screen space, added in post). */
    strength: number;
  };
  beams: { opacity: number };
  trees: {
    /** Warm rim on tree cards facing the sun. */
    rim: string;
    rimStrength: number;
    /**
     * Near pines (trees.mesh / trees.needle) bake far darker than the far cards that replace them
     * (needle texels about 11 / 255 in the shade variant and 23-30 in the sun one, against the cards'
     * 29-36), so on sunlit cliffs they read as black cut-outs. Below `pivot` (linear luminance) a
     * texel's luminance is raised along a power curve, l' = pivot * (l / pivot)^gamma, by at most
     * `maxGain`: the darkest (shade) needles gain most, sun needles less, and trunks and lit tips above
     * the pivot keep their bake. A stopgap until the trees are baked brighter (audit plan C8).
     */
    lift: { pivot: number; gamma: number; maxGain: number };
    /**
     * The lifted needles' shade, after the grade. The grade is tuned for stone and grass: it takes
     * out green's lead (greenTame) and leans shadows lavender (splitShadow), so lifted shade needles
     * read slate blue. On foliage texels (green at least level with red, before the grade) whose
     * graded luminance is below `hi` (fully below `lo`), the colour turns toward `color`'s hue at
     * its own luminance, by up to `amount`: deep green in shadow, as brightness stays where the lift
     * put it. Trunks, blossom and lit tips (red-led or bright) keep the grade.
     */
    shade: { color: string; amount: number; lo: number; hi: number };
  };
  /**
   * Shiny surfaces the diffuse-only bake loses, shaded on the page with one sky reflection (the dome's
   * colours, a hazy mountain horizon and a dim ground below it) plus a sun glint
   * (materials.ts SECT_ENV / surfaceGlsl):
   * - mirror: the Heart-Mirror's face, polished bronze (its bake keeps only a flat glow);
   * - metal: materials the exporter tags extras.sectSurface = "metal" (steel blades, gold trim): the
   *   texel's hue tints the reflection, the bake keeps a share as diffuse;
   * - glaze: extras.sectSurface = "glaze" (glazed roof tiles, porcelain): a clear-coat Fresnel
   *   sheen over the bake;
   * - iron: the metal of the hotspots `iron.hotspots` lists, given on their material copies
   *   (hotspotSurface): black iron, dull, near-black and rough.
   */
  surfaces: {
    /**
     * Reflectance at normal incidence (sRGB hex), how much of its baked glow the face keeps,
     * roughness 0..1, and how convex the face is (the normal's outward lean at the disc's edge).
     */
    mirror: { f0: string; glow: number; rough: number; convex: number };
    /** Reflectance scale on the texel's hue, share of the bake kept as diffuse, roughness. */
    metal: { f0: number; diffuse: number; rough: number };
    /** Reflectance at normal incidence (dielectric), roughness, and a cap on the sheen. */
    glaze: { f0: number; rough: number; max: number };
    /**
     * Black meteoric iron (玄鐵): the Heavy Iron Sword 玄鐵重劍 in the arena (hotspot "arena" holds
     * arena.sword alone), blunt and dull (重劍無鋒，大巧不工), black with a faint red light deep in it
     * (黑中隱隱透出紅光). Its iron bakes mid grey, which the grade turns slate; as "metal" it also
     * mirrored the sky at 0.7 and read as light blue-grey steel. Here the bake's luminance is kept
     * as the shape only: times `diffuse` (near-black), leaned `warmth` of the way toward the hue of
     * `color` (sRGB hex). A rough oxide (`f0` facing, `grazing` at the silhouette, `rough`) shows
     * a faint sheen of the sky and the sun, which turns toward `glint`'s hue as the faces turn away
     * (by up to `amount`): a dark red rim along the rounded edges. `seams`: the hotspotTint of its
     * ember hairlines (".glow.molten", glow class strength 2): the bake's seams are orange, so a
     * red-orange multiplier at 0.6 of the class's strength leaves them a deep ember red that still
     * counts as a glow (its largest channel stays above 1) and breathes with the arena's rhythm.
     */
    iron: {
      hotspots: readonly string[];
      color: string;
      warmth: number;
      diffuse: number;
      f0: number;
      grazing: number;
      rough: number;
      glint: { color: string; amount: number };
      seams: { color: string; amount: number; gain: number };
    };
    /** What a reflection sees below the horizon (sRGB hex), and the far mountains' haze tint. */
    ground: string;
    mountains: string;
  };
  /** Hover / focus highlight on hotspots: a gold edge glow. */
  hover: string;
  /**
   * Glyph colours of the five stele rows (skills:0..4, front to back), from the film's stele
   * colours: the bake keeps the glyphs but not their emission colour, and one colour per row also
   * tells the five skill groups apart.
   */
  steleRows: readonly string[];
  /** The jade slip's sheet (resume): its bake reads pale cyan-white; the film's is saturated jade. */
  jade: { color: string; amount: number; gain: number };
  /**
   * The last stretch of the flight (the jade slip to the summit) darkens to the film's blue
   * twilight, so the moon-gazing finale has a night mood. Blended in by the camera frame.
   */
  twilight: {
    /** Hold ids the blend runs between (0 at the first, 1 at the second). */
    from: string;
    to: string;
    zenith: string;
    mid: string;
    horizon: string;
    sunHorizon: string;
    /** Haze colour on the sky dome and the cloud sea. */
    haze: string;
    /** The cloud sea's lit top. */
    cloudSea: string;
    cloudSunLit: string;
    cloudLit: string;
    cloudShade: string;
    cloudRim: string;
    coverage: number;
  };
  /** The moon's halo strength (additive glow), by day and at full twilight. */
  moonHalo: { day: number; twilight: number };
  /**
   * The formation's page-drawn light (lib/sect/formation.ts holds the maths): the barrier dome, the
   * soft shafts rising from the core and the eight array eyes, and the brazier fires. Linear
   * multipliers on additive light unless noted; colours are sRGB hex.
   */
  formation: FormationLook;
}

/** One soft shaft of light (lib/sect/formation.ts formationShafts). */
export interface ShaftLook {
  color: string;
  /** Half-width of the strip (m); the light falls off across it as exp(-2.5 x^2). */
  radius: number;
  /** Peak strength at the shaft's centre line. */
  opacity: number;
  /** Height (m): the light is gone by the top. */
  height: number;
  /** Metres over which it fades in above its base. */
  fadeIn: number;
  /** Metres over which its light halves going up. */
  halfLife: number;
  /** How much the drifting streaks modulate it (0: smooth). */
  streaks: number;
}

export interface FormationLook {
  dome: {
    /** Pale gold: the sun of 日月, and the barriers of the genre are golden. */
    color: string;
    /** Fresnel rim at the silhouette: gain * (1 - facing)^power. */
    rim: { power: number; gain: number };
    /** The seam where the dome meets the plaza: gain * exp(-height * sharpness) (height 0..1). */
    seam: { sharpness: number; gain: number };
    /**
     * Shimmer bands sliding from the top to the base every `period` seconds (two, half a period
     * apart), `width` of the height wide, lighting the edges of a tortoise-shell (hexagon) lattice
     * of `cell` metres: band * (base + (1 - base) * edges) * (face + grazing * (1 - facing)^power).
     */
    ripple: { period: number; width: number; cell: number; edge: number; base: number; face: number; grazing: number; power: number };
    /**
     * Share of its light the far wall's inner face keeps (seen through the near wall). From above
     * (frames 1240-1260) that wall is seen grazing over a broad band, which read as a pale cap.
     */
    backFace: number;
    /** Low tier: the step this light makes over a background of this linear grey (glsl.ts screenAdd). */
    screenBack: number;
  };
  /** The core's shaft, a wide faint halo round it (high tier only), and the eight eyes' wisps. */
  shaft: ShaftLook;
  halo: ShaftLook;
  wisp: ShaftLook & {
    /** The wisp starts this far below the top of its station's hotspot box (the jade eye). */
    belowTop: number;
    /** Share of its light that rests; the rest runs round the array with the eyes' wave (idle.ts). */
    rest: number;
  };
  /** The eyes' wave (idle.ts GLOWS formation arch:0..7): period (s), share of the cycle lit. */
  wave: { period: number; width: number };
  /** Upward drift of the shafts' streaks (noise texture repeats per second). */
  streakSpeed: number;
  /** The sun-fire core's glow, breathing with the formation's 4 s breath (idle.ts). */
  coreGlow: { radius: number; color: string; strength: number; period: number; rest: number };
}

export const SECT_LOOK: SectLook = {
  haze: {
    color: "#c8ada0",
    sunColor: "#f6c48a",
    densityScale: 1.1,
    coolColor: "#aeaad8",
    coolMix: 0.6,
    extinction: [0.7, 1.0, 1.6],
    desaturate: 0.4,
    aerialDepth: 0.35,
  },
  mist: { density: 0.001, falloff: 45, start: 150 },
  dither: 1,
  sky: {
    zenith: "#8b9ad0",
    mid: "#dcb0ae",
    horizon: "#f3cfb2",
    sunHorizon: "#fbd29a",
    gradeMix: 0.75,
    haze: 1.0,
  },
  skyClouds: { sunLit: "#ffd9a6", lit: "#f9c6b6", shade: "#ae98bd", rim: "#fff1d6", coverage: 0.68 },
  puffs: {
    lit: "#fff0dc",
    shade: "#d4b6a8",
    rim: "#ffdcae",
    opacity: 0.9,
    areaThin: 0.65,
    areaRadius: 240,
    soft: 0.4,
  },
  grade: {
    exposure: 1.42,
    contrast: 1.16,
    pivot: 0.18,
    shadowTint: "#8b88c6",
    highlightTint: "#ffd9b0",
    split: 0.34,
    splitShadow: 0.6,
    saturation: 0.86,
    greenTame: 1.0,
    shoulder: 0.9,
  },
  cloudSeaColor: "#f0d2b4",
  cloudFogColor: "#dccbc6",
  water: {
    mirrorGlow: "#ffc27a",
    mirrorGlowGain: 2.2,
    mirrorRim: "#d9a24a",
    mirrorRimOuter: "#a82a20",
    mirrorRune: "#8ff2e2",
    mirrorRuneGain: 2.4,
    mirrorBronze: "#4f5a46",
    skyLow: "#c9b2a8",
    skyHigh: "#8f9bcc",
  },
  waterfall: { color: "#cfe3ee", foam: "#f7fbff", opacity: 0.82, mist: "#eef3f6" },
  petals: { count: 520, colorA: "#f6b3c3", colorB: "#ffdbe3", size: 0.05, radius: 22 },
  cranes: { count: 5, color: "#f3eee6", dark: "#23211f", crown: "#c8302a" },
  sunHaze: { color: "#ffc88a", strength: 0.2 },
  beams: { opacity: 0.55 },
  trees: {
    rim: "#ffc890",
    rimStrength: 0.35,
    lift: { pivot: 0.1, gamma: 0.5, maxGain: 6 },
    shade: { color: "#34503a", amount: 0.8, lo: 0.012, hi: 0.07 },
  },
  surfaces: {
    mirror: { f0: "#f2cf98", glow: 0.12, rough: 0.12, convex: 0.32 },
    metal: { f0: 0.7, diffuse: 0.35, rough: 0.18 },
    glaze: { f0: 0.045, rough: 0.12, max: 0.4 },
    iron: {
      hotspots: ["arena"],
      color: "#3a1a1c",
      warmth: 0.42,
      diffuse: 0.21,
      f0: 0.055,
      grazing: 0.3,
      rough: 0.58,
      glint: { color: "#a8584e", amount: 0.8 },
      seams: { color: "#f25236", amount: 1, gain: 0.6 },
    },
    ground: "#56514a",
    mountains: "#7d7a96",
  },
  hover: "#ffd27a",
  steleRows: ["#9a7bff", "#5aa8ff", "#ff5a4a", "#ffa040", "#ffd08a"],
  jade: { color: "#2fae8f", amount: 0.75, gain: 0.82 },
  twilight: {
    from: "scroll",
    to: "summit",
    zenith: "#46619a",
    mid: "#7d91bd",
    horizon: "#c5b9c6",
    sunHorizon: "#efc6a2",
    haze: "#a3abc2",
    cloudSea: "#c4c2d2",
    cloudSunLit: "#eccbb4",
    cloudLit: "#c3c4dc",
    cloudShade: "#727ca3",
    cloudRim: "#f3e2d4",
    coverage: 0.42,
  },
  moonHalo: { day: 0.22, twilight: 0.5 },
  formation: {
    dome: {
      color: "#ffd9a0",
      rim: { power: 5, gain: 0.18 },
      seam: { sharpness: 90, gain: 0.22 },
      ripple: { period: 7, width: 0.035, cell: 3.5, edge: 0.07, base: 0.25, face: 0.03, grazing: 0.14, power: 1.5 },
      backFace: 0.45,
      screenBack: 0.2,
    },
    shaft: { color: "#ffdca0", radius: 3.5, opacity: 0.55, height: 140, fadeIn: 4, halfLife: 45, streaks: 0.7 },
    halo: { color: "#ffdca0", radius: 9, opacity: 0.12, height: 120, fadeIn: 6, halfLife: 40, streaks: 0.3 },
    wisp: { color: "#bff5e0", radius: 1.4, opacity: 0.3, height: 16, fadeIn: 0.8, halfLife: 9, streaks: 0.5, belowTop: 1.2, rest: 0.3 },
    wave: { period: 8, width: 0.32 },
    streakSpeed: 0.03,
    coreGlow: { radius: 4.5, color: "#ffd27a", strength: 0.55, period: 4, rest: 0.65 },
  },
};

/**
 * A colour the bake cannot carry for a hotspot's material copy: the stele rows' glyphs, the jade
 * slip's sheet and the Heavy Iron Sword's ember seams. `amount` is how far toward `color` from
 * white; the glow strength is kept and scaled by `gain`. Null for everything else.
 */
export function hotspotTint(
  hotspotId: string,
  materialName: string,
  look: SectLook = SECT_LOOK,
): { color: string; amount: number; gain: number } | null {
  const row = /^skills:(\d+)$/.exec(hotspotId);
  if (row && /\.glow\.(steles_rune|rune_cyan)$/.test(materialName)) {
    const color = look.steleRows[Number(row[1]) % look.steleRows.length];
    return color ? { color, amount: 0.85, gain: 1 } : null;
  }
  if (hotspotId === "resume" && /\.glow\.other$/.test(materialName)) return look.jade;
  if (look.surfaces.iron.hotspots.includes(hotspotId) && /\.glow\.molten$/.test(materialName)) return look.surfaces.iron.seams;
  return null;
}

/**
 * The reflective class a hotspot's material copy takes in place of the exporter's: "iron" for the
 * metal (".surface.metal") of the hotspots SECT_LOOK.surfaces.iron lists (the arena's Heavy Iron
 * Sword), so the gate's saber and every other steel keep the "metal" class. Null otherwise.
 */
export function hotspotSurface(hotspotId: string, materialName: string, look: SectLook = SECT_LOOK): "iron" | null {
  return look.surfaces.iron.hotspots.includes(hotspotId) && /\.surface\.metal$/.test(materialName) ? "iron" : null;
}

/** 0 before the twilight's first hold, 1 from its second, smooth between. */
export function twilightAmount(frame: number, fromFrame: number, toFrame: number): number {
  if (!(toFrame > fromFrame)) return 0;
  return smoothstep(fromFrame, toFrame, frame);
}

/** meta with the look's haze and cloud colours swapped in (everything else unchanged). */
export function applyLook(meta: SectMeta, look: SectLook = SECT_LOOK): SectMeta {
  return {
    ...meta,
    fog: { ...meta.fog, color: look.haze.color, density: meta.fog.density * look.haze.densityScale },
    sky: { ...meta.sky, horizonSun: look.haze.sunColor },
    cloudSea: { ...meta.cloudSea, color: look.cloudSeaColor },
  };
}

/**
 * Fog constants for the shaders, with the look's sky haze, cloud-layer colour, aerial perspective,
 * valley mist (on the cloud layer's top) and dither.
 */
export function lookFogConstants(meta: SectMeta, look: SectLook = SECT_LOOK): FogConstants {
  const base = fogConstantsFromMeta(meta);
  return {
    ...base,
    skyHaze: look.sky.haze,
    cloudColor: hexToLinear(look.cloudFogColor),
    extinction: balancedExtinction(look.haze.extinction, hexToLinear(look.haze.color)),
    coolTint: unitTint(look.haze.coolColor),
    coolMix: look.haze.coolMix,
    desaturate: look.haze.desaturate,
    aerialDepth: look.haze.aerialDepth,
    mistDensity: look.mist.density,
    mistBaseY: base.cloudTop,
    mistFalloff: look.mist.falloff,
    mistStart: look.mist.start,
    dither: look.dither,
  };
}

const LUMA: Vec3 = [0.2126, 0.7152, 0.0722];

function luma(c: Vec3): number {
  return c[0] * LUMA[0] + c[1] * LUMA[1] + c[2] * LUMA[2];
}

/**
 * The per-channel extinction ratio `k` scaled so the haze veil keeps its brightness: weighted by
 * the haze colour's luminance per channel, the scaled k averages 1. Unscaled, a warm haze would
 * lose more veil in red than blue adds back, and mid-distance terrain would darken instead of
 * going paler.
 */
export function balancedExtinction(k: Vec3, haze: Vec3): Vec3 {
  const w = haze.map((h, i) => h * LUMA[i]);
  const sum = w[0] + w[1] + w[2];
  const weighted = w[0] * k[0] + w[1] * k[1] + w[2] * k[2];
  const s = sum > 1e-6 && weighted > 1e-6 ? sum / weighted : 1;
  return [k[0] * s, k[1] * s, k[2] * s];
}

/** A tint as a linear colour scaled to luminance 1, so tinting moves hue without changing brightness. */
export function unitTint(hex: string): Vec3 {
  const c = hexToLinear(hex);
  const l = Math.max(luma(c), 1e-6);
  return [c[0] / l, c[1] / l, c[2] / l];
}

function smoothstep(a: number, b: number, x: number): number {
  const t = Math.min(Math.max((x - a) / (b - a), 0), 1);
  return t * t * (3 - 2 * t);
}

/** Split-tone weights: 0 in the shadows, 1 in the highlights (on graded luminance). */
const SPLIT_LO = 0.008;
const SPLIT_HI = 0.2;

/** TypeScript mirror of the GLSL grade (linear in, linear out), for tests. */
export function gradeLinear(c: Vec3, g: SectLook["grade"] = SECT_LOOK.grade): Vec3 {
  let x = c.map((v) => v * g.exposure) as Vec3;
  x[1] -= Math.max(x[1] - Math.max(x[0], x[2]), 0) * g.greenTame;
  const l0 = luma(x);
  const l1 = l0 > 0 ? g.pivot * Math.pow(l0 / g.pivot, g.contrast) : 0;
  x = x.map((v) => (l0 > 1e-6 ? (v * l1) / l0 : v)) as Vec3;
  const w = smoothstep(SPLIT_LO, SPLIT_HI, l1);
  const st = unitTint(g.shadowTint);
  const ht = unitTint(g.highlightTint);
  const ss = g.splitShadow ?? g.split;
  x = x.map((v, i) => v * (1 + (st[i] - 1) * ss + ((1 + (ht[i] - 1) * g.split) - (1 + (st[i] - 1) * ss)) * w)) as Vec3;
  const l = luma(x);
  const k = g.shoulder;
  return x.map((v) => {
    const s = Math.max(l + (v - l) * g.saturation, 0);
    return s <= k ? s : k + (1 - k) * (1 - Math.exp(-(s - k) / (1 - k)));
  }) as Vec3;
}

/**
 * GLSL for the grade: `vec3 sectGrade( vec3 linear )`. A material that defines SECT_KEEP_GREEN
 * keeps green's lead (no greenTame): the Five Element Banners' cloth (idle.ts swayCut), so the
 * wood flag reads green, not slate blue.
 */
export function gradeGlsl(g: SectLook["grade"] = SECT_LOOK.grade): string {
  const k = glslFloat(g.shoulder);
  return /* glsl */ `
vec3 sectGrade( vec3 c ) {
  c *= ${glslFloat(g.exposure)};
#ifndef SECT_KEEP_GREEN
  c.g -= max( c.g - max( c.r, c.b ), 0.0 ) * ${glslFloat(g.greenTame)};
#endif
  float l0 = dot( c, vec3( 0.2126, 0.7152, 0.0722 ) );
  float l1 = l0 > 0.0 ? ${glslFloat(g.pivot)} * pow( l0 / ${glslFloat(g.pivot)}, ${glslFloat(g.contrast)} ) : 0.0;
  c *= l0 > 1e-6 ? l1 / l0 : 1.0;
  float w = smoothstep( ${glslFloat(SPLIT_LO)}, ${glslFloat(SPLIT_HI)}, l1 );
  c *= mix( mix( vec3( 1.0 ), ${glslVec3(unitTint(g.shadowTint))}, ${glslFloat(g.splitShadow ?? g.split)} ),
    mix( vec3( 1.0 ), ${glslVec3(unitTint(g.highlightTint))}, ${glslFloat(g.split)} ), w );
  float l = dot( c, vec3( 0.2126, 0.7152, 0.0722 ) );
  c = max( vec3( l ) + ( c - vec3( l ) ) * ${glslFloat(g.saturation)}, 0.0 );
  vec3 rolled = ${k} + ( 1.0 - ${k} ) * ( 1.0 - exp( - ( c - ${k} ) / ( 1.0 - ${k} ) ) );
  return mix( c, rolled, step( vec3( ${k} ), c ) );
}
`;
}

/**
 * The near pines' lift (SECT_LOOK.trees.lift) on a linear texel: its luminance raised along the
 * power curve below the pivot, hue kept. Mirrors treeLiftGlsl.
 */
export function treeLiftLinear(c: Vec3, lift: SectLook["trees"]["lift"] = SECT_LOOK.trees.lift): Vec3 {
  const l = luma(c);
  if (!(l > 1e-6) || l >= lift.pivot) return c;
  const gain = Math.min((lift.pivot * Math.pow(l / lift.pivot, lift.gamma)) / l, lift.maxGain);
  return c.map((v) => v * gain) as Vec3;
}

/** GLSL for the lift: `vec3 sectTreeLift( vec3 linear )`. */
export function treeLiftGlsl(lift: SectLook["trees"]["lift"] = SECT_LOOK.trees.lift): string {
  const p = glslFloat(lift.pivot);
  return /* glsl */ `
vec3 sectTreeLift( vec3 c ) {
  float l = dot( c, vec3( 0.2126, 0.7152, 0.0722 ) );
  if ( l <= 1e-6 || l >= ${p} ) return c;
  return c * min( ${p} * pow( l / ${p}, ${glslFloat(lift.gamma)} ) / l, ${glslFloat(lift.maxGain)} );
}
`;
}

/** Foliage weight of a linear texel: 1 once green is level with red, 0 for red-led (bark, blossom). */
function leafWeight(t: Vec3): number {
  const s = t[0] + t[1];
  return s > 1e-6 ? smoothstep(-0.25, 0, (t[1] - t[0]) / s) : 0;
}

/**
 * The near pines' shade (SECT_LOOK.trees.shade) on a graded linear colour `c`, from its texel `t`
 * (before the grade): dark foliage turns toward the shade colour's hue at its own luminance. Mirrors
 * treeShadeGlsl.
 */
export function treeShadeLinear(c: Vec3, t: Vec3, shade: SectLook["trees"]["shade"] = SECT_LOOK.trees.shade): Vec3 {
  const l = luma(c);
  const w = (1 - smoothstep(shade.lo, shade.hi, l)) * leafWeight(t) * shade.amount;
  const tint = unitTint(shade.color);
  return c.map((v, i) => v + (l * tint[i] - v) * w) as Vec3;
}

/** GLSL for the shade: `vec3 sectTreeShade( vec3 graded, vec3 texel )`. */
export function treeShadeGlsl(shade: SectLook["trees"]["shade"] = SECT_LOOK.trees.shade): string {
  return /* glsl */ `
vec3 sectTreeShade( vec3 c, vec3 t ) {
  float l = dot( c, vec3( 0.2126, 0.7152, 0.0722 ) );
  float s = t.r + t.g;
  float leaf = s > 1e-6 ? smoothstep( -0.25, 0.0, ( t.g - t.r ) / s ) : 0.0;
  float w = ( 1.0 - smoothstep( ${glslFloat(shade.lo)}, ${glslFloat(shade.hi)}, l ) ) * leaf * ${glslFloat(shade.amount)};
  return mix( c, l * ${glslVec3(unitTint(shade.color))}, w );
}
`;
}

/** Linear colours of the look, for shader uniforms and defines. */
export function lookLinear(hex: string): Vec3 {
  return hexToLinear(hex);
}

/**
 * Density scale for a cloud puff: thinner within `areaRadius` of an area centre (fading back to 1
 * over the next half radius), so the banks frame the gate and the terrace instead of veiling them.
 */
export function puffDensityScale(c: Vec3, areas: readonly Vec3[], look: SectLook = SECT_LOOK): number {
  const { areaThin, areaRadius } = look.puffs;
  let s = 1;
  for (const a of areas) {
    const d = Math.hypot(c[0] - a[0], c[1] - a[1], c[2] - a[2]);
    const t = smoothstep(areaRadius, areaRadius * 1.5, d);
    s = Math.min(s, areaThin + (1 - areaThin) * t);
  }
  return s;
}
