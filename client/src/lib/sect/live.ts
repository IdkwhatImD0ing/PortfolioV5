/**
 * Live light at the stop the flight is at (High only): that stop's atlas surfaces get their sun
 * light, shadows and shine worked out in the fragment shader instead of read from the bake. One
 * stop is lit at a time, and only a stop listed in live/index.json (liveStopsFile). The bake gives
 * three extra maps per atlas (public/sect/full/live/<chunk>/, written by
 * blender/xianxia-sect/sect/bake_web.py write_live_maps):
 *
 * - albedo: the surface colour with no light on it (sRGB);
 * - ambient: the bake with the sun and the key lamp off (the sky's light and its bounces), on the
 *   sRGB curve over ambientScale. As baked it is already times the surface colour ("radiance");
 *   tools/sect_live.py divides the colour out ("irradiance", index.json ambientKind), and the
 *   shader multiplies it back from the albedo map;
 * - normal: the surface normal in world space, three.js axes, as n * 0.5 + 0.5.
 *
 * The page adds the two lamps the bake lit the scene with (index.json light.sun and light.key), each
 * through its own static shadow map (experience/live-shadow.ts), and a GGX shine per lamp, then the
 * bake's own post (its grade, saturation, exposure) and Blender's view transform read from a table
 * (LIVE_VIEW), so the result is the same kind of colour as a baked texel. Two more things come
 * from the bake, in the ambient map: the lamps' bounced light (ambientBounce; without it the page
 * adds a flat warm fill) and, in its alpha, the bake's own soft shadow (bakedShadow), which takes
 * over from the page's sharp one far from what casts. On top come what a bake cannot hold: bumps,
 * roof tiles' relief, a soft sheen on paint and the sky in smooth surfaces. Away from the area's
 * centre the live colour fades back into the baked texel (LIVE_LOOK.blend, sized by the stop's
 * footprint: liveStopBox). The stop the flight is at is the one lit (liveStopAt).
 * docs/sect/live-gate.md has the measurements against the bake.
 *
 * Pure: the parsers, the material mapping, the art-direction numbers (LIVE_LOOK), which stop is
 * live (liveStopAt, liveStopKept, liveStep), which stop's maps to load ahead (livePreload), when
 * fast travel's ink waits (liveComing), the light-space maths and the GLSL as strings.
 * experience/materials.ts compiles the GLSL into the baked material, experience/live.tsx loads the
 * maps and drives it.
 */
import { glslFloat, glslVec3, hexToLinear } from "./glsl";
import type { Quality, Tier } from "./runtime";
import type { AreaMeta, Vec3 } from "./types";

// ---------------------------------------------------------------------------------------------
// The data

/** A chunk id as the live files name it (a folder name under live/). */
const CHUNK_ID = /^[A-Za-z0-9_-]+$/;

/** The list of stops that have live maps, relative to the asset folder. */
export function liveStopsFile(): string {
  return "live/index.json";
}

/**
 * live/index.json, `{ "version": 1, "chunks": ["gate", ...] }`: the chunk ids with live maps, in
 * the file's order, each once. [] when anything in it is missing or malformed (nothing is lit live).
 */
export function parseLiveStops(json: unknown): string[] {
  if (!isObj(json) || json.version !== 1 || !Array.isArray(json.chunks)) return [];
  const out: string[] = [];
  for (const c of json.chunks) {
    if (typeof c !== "string" || !CHUNK_ID.test(c)) return [];
    if (!out.includes(c)) out.push(c);
  }
  return out;
}

/** index.json of a chunk's live maps, relative to the asset folder. */
export function liveIndexFile(chunk: string): string {
  return `live/${chunk}/index.json`;
}

/** A file of a chunk's live maps, relative to the asset folder. */
export function liveMapFile(chunk: string, file: string): string {
  return `live/${chunk}/${file}`;
}

/**
 * Blender's view transform as a table (blender/xianxia-sect/tools/sect_view_lut.py): the "AgX" view
 * with the "AgX - Punchy" look on an sRGB display, scene-linear Rec.709 in, display sRGB out. `size`
 * cubed texels of 4 bytes, red fastest; each axis is log2 of the linear value from 2^lo to 2^hi.
 * The page's own AgX code (glsl.ts AGX_PUNCHY_GLSL, three.js's curve) is not Blender's: greys agree,
 * lacquer red comes out a third brighter and with no green or blue left in it.
 */
export const LIVE_VIEW = { file: "live/view_agx_punchy.bin", size: 48, lo: -12.47393, hi: 6.5 } as const;

/** One lamp the bake lit the scene with. */
export interface LiveLamp {
  /** Unit vector toward the lamp (three.js axes). */
  dir: Vec3;
  /** Linear colour. */
  color: Vec3;
  /** Blender's W/m2: a diffuse surface gets albedo / PI * strength * color * max(N.dir, 0). */
  strength: number;
  /** The lamp's angular diameter (degrees): how soft its shadows are. */
  angleDeg: number;
}

/** One atlas's live maps (file names in the chunk's live folder). */
export interface LiveAtlas {
  size: number;
  albedo: string;
  ambient: string;
  normal: string;
  /** The baked ambient map's 99.9th percentile of linear radiance (colour still in it), when given. */
  ambientMax: number | null;
}

export interface LiveIndex {
  version: 1;
  chunk: string;
  /** The ambient map holds its linear values / ambientScale. */
  ambientScale: number;
  /**
   * What the ambient map holds: "radiance" is the bake with the lamps off as it is (sky light times
   * the surface colour), "irradiance" is that with the surface colour divided out (tools/sect_live.py),
   * which is smooth, so the map can be small and the page's colour map brings the paint back sharp.
   */
  ambientKind: "radiance" | "irradiance";
  /**
   * The ambient map also holds the lamps' bounced light (blender/xianxia-sect/sect/live_bounce.py
   * estimates it from the bake). The page then adds no bounce fill of its own (LIVE_LOOK.bounce).
   */
  ambientBounce: boolean;
  /**
   * The ambient map's alpha holds how much of the two lamps' direct light the bake let through at
   * each texel, 0 in shade to 1 in full light (index.json "ambientAlpha": "visibility"; sect/live_bounce.py).
   * The page's own shadows are sharp, which is right close to what casts them. Far from the caster,
   * and where the page's maps hold no caster at all, it uses this (LIVE_LOOK.bakedShadow).
   */
  bakedShadow: boolean;
  /**
   * The normal map's alpha holds where that shadow is soft: 1 near an edge of it, 0 where it does
   * not change (index.json "normalAlpha": "soft"; tools/sect_live.py). The page's own shadow maps
   * are used only where it is soft. Without it they are used everywhere.
   */
  bakedSoft: boolean;
  /** By atlas key (the baked atlas image's name, e.g. gate_A0). */
  atlases: Record<string, LiveAtlas>;
  light: { sun: LiveLamp; key: LiveLamp; worldStrength: number };
  /** What the bake's own post does to linear radiance before it writes a baked atlas. */
  post: { exposureStops: number; saturation: number; view: string; look: string };
}

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function finite(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function vec3Of(v: unknown): Vec3 | null {
  if (!Array.isArray(v) || v.length !== 3 || !v.every(finite)) return null;
  return [v[0], v[1], v[2]];
}

/** A plain file name in the live folder (no path, nothing hidden). */
function fileName(v: unknown): string | null {
  return typeof v === "string" && /^[A-Za-z0-9_][A-Za-z0-9_.-]*$/.test(v) && !v.includes("..") ? v : null;
}

function parseLamp(v: unknown): LiveLamp | null {
  if (!isObj(v)) return null;
  const dir = vec3Of(v.dir);
  const color = vec3Of(v.color);
  if (!dir || !color || color.some((c) => c < 0)) return null;
  const len = Math.hypot(dir[0], dir[1], dir[2]);
  // Rounded to 5 places in the file: a unit vector is within a whisker of 1.
  if (Math.abs(len - 1) > 0.01) return null;
  if (!finite(v.strength) || v.strength < 0 || !finite(v.angleDeg) || v.angleDeg < 0 || v.angleDeg > 180) return null;
  return { dir: [dir[0] / len, dir[1] / len, dir[2] / len], color, strength: v.strength, angleDeg: v.angleDeg };
}

function parseAtlas(v: unknown): LiveAtlas | null {
  if (!isObj(v)) return null;
  const albedo = fileName(v.albedo);
  const ambient = fileName(v.ambient);
  const normal = fileName(v.normal);
  if (!albedo || !ambient || !normal) return null;
  if (!finite(v.size) || v.size <= 0 || !Number.isInteger(v.size)) return null;
  if (v.ambientMax !== undefined && !finite(v.ambientMax)) return null;
  return { size: v.size, albedo, ambient, normal, ambientMax: finite(v.ambientMax) ? v.ambientMax : null };
}

/** index.json as live.tsx reads it, or null when anything in it is missing or malformed (the chunk then stays baked). */
export function parseLiveIndex(json: unknown): LiveIndex | null {
  if (!isObj(json) || json.version !== 1) return null;
  if (typeof json.chunk !== "string" || !CHUNK_ID.test(json.chunk)) return null;
  if (!finite(json.ambientScale) || json.ambientScale <= 0) return null;
  if (!isObj(json.atlases)) return null;
  const atlases: Record<string, LiveAtlas> = {};
  for (const [key, v] of Object.entries(json.atlases)) {
    if (!/^[A-Za-z0-9]+_A\d+$/.test(key)) return null;
    const a = parseAtlas(v);
    if (!a) return null;
    atlases[key] = a;
  }
  if (Object.keys(atlases).length === 0) return null;
  const light = json.light;
  if (!isObj(light)) return null;
  const sun = parseLamp(light.sun);
  const key = parseLamp(light.key);
  if (!sun || !key) return null;
  if (light.worldStrength !== undefined && !finite(light.worldStrength)) return null;
  const post = json.post;
  if (!isObj(post) || !finite(post.exposureStops) || !finite(post.saturation) || post.saturation < 0) return null;
  return {
    version: 1,
    chunk: json.chunk,
    ambientScale: json.ambientScale,
    ambientKind: json.ambientKind === "irradiance" ? "irradiance" : "radiance",
    ambientBounce: json.ambientBounce === true,
    bakedShadow: json.ambientAlpha === "visibility",
    bakedSoft: json.normalAlpha === "soft",
    atlases,
    light: { sun, key, worldStrength: finite(light.worldStrength) ? light.worldStrength : 1 },
    post: {
      exposureStops: post.exposureStops,
      saturation: post.saturation,
      view: typeof post.view === "string" ? post.view : "AgX",
      look: typeof post.look === "string" ? post.look : "AgX - Punchy",
    },
  };
}

/**
 * The atlas a baked material is drawn from (the `<chunk>_A<n>` in its name, which is also its
 * texture image's name), or null for one that stays baked: vertex-coloured pieces (baked.vc*), glow
 * surfaces (`.glow.` in the name) and anything that is not an atlas material.
 */
export function liveAtlasOf(materialName: string): string | null {
  if (/\.glow\./i.test(materialName)) return null;
  const m = /^baked\.([A-Za-z0-9]+_A\d+)(?:\.|$)/.exec(materialName);
  return m ? m[1] : null;
}

/** The shine classes (LIVE_LOOK.classes). */
export type LiveClass = "default" | "paving" | "tiles" | "rock" | "ground" | "metal" | "glaze" | "cloth";

export const LIVE_CLASSES: readonly LiveClass[] = ["default", "paving", "tiles", "rock", "ground", "metal", "glaze", "cloth"];

/**
 * A material's shine class: cloth first (a material that sways: banners, flags, a blossom tree's
 * branches), then its reflective tag (userData.sectSurface: metal and black iron shine as metal,
 * glaze as glaze), then its detail class (userData.detail), else default.
 */
export function liveClassOf(detail: unknown, surface: unknown, sways = false): LiveClass {
  if (sways) return "cloth";
  if (surface === "metal" || surface === "iron") return "metal";
  if (surface === "glaze") return "glaze";
  if (detail === "paving" || detail === "tiles" || detail === "rock" || detail === "ground") return detail;
  return "default";
}

// ---------------------------------------------------------------------------------------------
// The knobs

/** Roughness and reflectance of a shine class. */
export interface LiveShine {
  /** 0 polished .. 1 matte (GGX alpha is its square). */
  roughness: number;
  /** Reflectance at normal incidence. */
  f0: number;
  /** 0..1: how much the albedo's hue tints the reflectance (metal gold, steel grey). */
  tint: number;
  /**
   * Bumps the bake's flat faces do not have, as two layers of noise: [size of the first (m), its
   * slope, size of the second (m), its slope]. A slope of 0.1 tilts the surface about 6 degrees.
   */
  bump: [number, number, number, number];
  /** Painted wood: strongly coloured parts of this class are lacquer (LIVE_LOOK.paint). */
  paint?: boolean;
  /**
   * A class that moves (cloth): its shadow lookups start this far toward the lamp (m), past where
   * it hung when the maps were drawn, so it does not shade itself as it waves.
   */
  liftM?: number;
}

/** How live light goes from one stop to the next (LIVE_LOOK.handover). */
export interface LiveHandover {
  /** The stop lit stays lit until the frame is more than this many frames past its own range, either side (liveStopKept). */
  stayFrames: number;
  /** Load the next stop's maps ahead while the flight heads there (livePreload). Off: each stop loads its own when it starts. */
  preload: boolean;
  /** The way of travel turns only once the frame has gone back more than this many frames (liveHeading). */
  reverseFrames: number;
  /** The preload begins once the frame is more than this many frames past the lit stop's hold, toward the next stop. */
  leadFrames: number;
  /**
   * Fast travel's ink waits for the live stop's mix to reach 1, but at most this long (ms) past when
   * it would have cleared anyway (settle.ts late pieces).
   */
  inkWaitMs: number;
}

export interface LiveLook {
  /** Everything, on the summed linear radiance (before the bake's post). */
  gain: number;
  /** On the sun's and the key lamp's strength (direct light and shine). */
  sunGain: number;
  keyGain: number;
  /** On the ambient map. */
  ambientGain: number;
  /** Stops added to index.json post.exposureStops. */
  exposureBias: number;
  /** Times index.json post.saturation. */
  saturation: number;
  /**
   * Sunlight bounced off the ground, for a stop whose ambient map does not hold the bake's bounced
   * light (LiveIndex.ambientBounce false; every installed stop has it, so this is a fallback): a
   * warm fill on faces turned down or sideways. `amount` is the share of the two lamps' light on
   * level ground that comes back up (ground albedo times how much ground a face sees).
   */
  bounce: { color: string; amount: number };
  /** Shine per class (liveClassOf). */
  classes: Record<LiveClass, LiveShine>;
  /** Overall strength of the lamps' shine. */
  specular: number;
  /**
   * Lacquer: where a `paint` class's colour is this saturated (0 grey .. 1 pure, from..to) it takes
   * this roughness and reflectance instead of the class's.
   */
  paint: { sat: [number, number]; roughness: number; f0: number };
  /**
   * The sky seen in smooth surfaces (not metal or glaze, which have their own): `amount` scales it,
   * `open` is the ambient map's level over the surface colour where the whole sky is in view (less
   * than that and the surface sees less sky, so it mirrors less of it).
   */
  sky: { amount: number; open: number };
  /** Overall strength of the bumps (0 gives the bake's flat faces). */
  bump: number;
  /**
   * Roof tiles (materials of the tiles detail class): each course is a half-round, so the normal
   * rolls across it. `roll` is how far (0 flat, about 0.6 a full half-round); it fades out between
   * `fade` courses to a pixel, before the courses get too small to draw.
   */
  tiles: { roll: number; fade: [number, number] };
  /**
   * Paving (materials of the paving detail class): each slab sits a little unevenly (`tilt`, the
   * slope its normal leans by, either way), and its edges are bevelled into the joint (`bevel`,
   * the slope, over `bevelM` metres from the edge). Under a 7 degree sun that is what paving shows:
   * slabs of slightly different brightness, a lit rim on the side toward the sun.
   */
  paving: { tilt: number; bevelM: number; bevel: number };
  /**
   * Where the bake's own soft shadow takes over from the page's sharp one (when the index has it,
   * LiveIndex.bakedShadow): the page's alone while what casts is within nearM of the surface, the
   * bake's alone from farM on. `missing` is the bake's share where the page's map finds nothing
   * casting near the point at all: the caster is far off, or not in the page. `graze`: a lamp that
   * only grazes a face is left to the bake whatever casts, wholly below the first number and not
   * at all above the second (the cosine between the face and the lamp). The sun stands 7 degrees
   * up, so on level ground one texel of its map is 40 cm long: its shadows on floors and stair
   * treads came out as dashes and saw teeth. `close`: so is a lamp whose caster is right at the
   * surface, wholly within the first number of metres and not at all past the second (a stair
   * tread under its own nosing is a texel or two in the map: saw teeth). And the page's maps
   * settle only what the bake holds soft (LiveIndex.bakedSoft): near an edge of the bake's shadow
   * the page's result stands, and where that shadow does not change the bake's does. The page's
   * maps have gaps the bake has not: faces the flight never sees are not in the page, and a roof
   * seen edge-on from a lamp is a sliver, so light came through in dashes.
   */
  bakedShadow: {
    nearM: number;
    farM: number;
    missing: number;
    graze: [number, number];
    close: [number, number];
  };
  /**
   * The bake's own detail. The maps rebuild the bake's light at half its size, so anything finer
   * (cracks in a cliff, a carved slab, lettering in shade) came out soft or blocky, and the
   * rebuilt colour drifts a little from the bake's. The baked texel over the bake's light as the
   * maps rebuild it is what they missed; the live colour is multiplied by it, held to min..max.
   * `floor` keeps the ratio steady in the dark. So where live light changes nothing, the picture
   * is the bake's own. `amount` 0 turns it off.
   */
  detail: { amount: number; min: number; max: number; floor: number };
  /**
   * Bumps and the tiles' roll can raise a lamp's light to at most this many times what the flat
   * face gets from it: on a face that barely sees the lamp, real bumps shade each other.
   */
  bumpCap: number;
  /** The lamps' shine is held to this share of the surface's own light, so a dark board stays dark. */
  shineCap: number;
  shadow: {
    /** The shadow map's side (px). */
    size: number;
    /**
     * Half its width round the area's centre, across the key lamp, is the blend's outer edge plus
     * this (m): liveStopBox.
     */
    marginM: number;
    /** Its depth along the lamp (m): from aheadM past the area's centre back toward the lamp. */
    depthM: number;
    /** How far past the centre, away from the lamp, the map reaches (m). */
    aheadM: number;
    /** Constant depth bias (m), grown by the slope (below). */
    biasM: number;
    /** The receiving point moves this far out along its normal before the lookup (m). */
    normalBiasM: number;
    /** Blocker search radius (m). */
    searchM: number;
    /** Penumbra width from blocker distance and the lamp's size, held to this range (m). */
    minPenumbraM: number;
    maxPenumbraM: number;
    /** And never narrower than this many of the map's texels (a bigger stop has bigger texels): livePenumbra. */
    minPenumbraTexels: number;
    /**
     * Nor wider than this many: the filter's taps are fixed (no noise), so an edge wider than they
     * can cover would show as steps.
     */
    maxPenumbraTexels: number;
    blockerTaps: number;
    pcfTaps: number;
    /** The coarse map the blocker search reads is this many times smaller than the shadow map. */
    coarse: number;
    /** The slope-scaled bias's slope is held below this (tan of the angle to the lamp). */
    slopeMax: number;
  };
  /**
   * The sun's own map. It stands 7 degrees up, so what shades the stop can be a spire two
   * kilometres off: its map is as wide as the key's and far deeper. The tap counts and the coarse
   * factor are shadow's.
   */
  sunShadow: {
    size: number;
    marginM: number;
    depthM: number;
    aheadM: number;
    biasM: number;
    normalBiasM: number;
    searchM: number;
    minPenumbraM: number;
    maxPenumbraM: number;
    minPenumbraTexels: number;
    maxPenumbraTexels: number;
    slopeMax: number;
  };
  /**
   * Where live fades back to the baked texel, by horizontal distance from the stop's centre (m):
   * whole out to its footprint plus padM, gone fadeM further out (liveStopBox).
   */
  blend: { padM: number; fadeM: number };
  /**
   * Per stop (by chunk id), numbers that replace the ones above at that stop (liveLookFor). Only
   * the overall balance: gain, the lamps' and the sky's gains, exposure and saturation.
   */
  stops: Record<string, LiveStopLook>;
  /** Live light by tier (runtime.ts tierQuality copies it into Quality.liveLight). */
  on: Record<Tier, boolean>;
  /** Going from one stop to the next (liveStopKept, livePreload, liveHeading, liveComing). */
  handover: LiveHandover;
  /**
   * The bake's post grade, which index.json does not carry (it mirrors blender/xianxia-sect/sect/lib/look.py
   * grade_* and bake_web.py post_scene): an ASC-CDL, then a Color Correction node's saturation by level
   * (Blender's midtone range and its 0.1 margins), in scene-linear light before the view transform.
   */
  grade: {
    slope: Vec3;
    offset: Vec3;
    power: Vec3;
    shadowSat: number;
    midSat: number;
    highlightSat: number;
    midStart: number;
    midEnd: number;
  };
}

/** The numbers a stop may set for itself (LIVE_LOOK.stops). */
export const LIVE_STOP_KNOBS = ["gain", "sunGain", "keyGain", "ambientGain", "exposureBias", "saturation"] as const;

export type LiveStopLook = Partial<Pick<LiveLook, (typeof LIVE_STOP_KNOBS)[number]>>;

export const LIVE_LOOK: LiveLook = {
  gain: 1,
  // At 1, 1, 1 the page's sum is the bake's (docs/sect/live-gate.md has the measurements). These lean
  // a little on the lamps. Much more (1.35, 1.25, 0.85 was tried) washes sunlit paint and steps
  // toward cream: the view transform takes the colour out of anything that bright. The shade is
  // left as the bake has it.
  sunGain: 1.1,
  keyGain: 1.05,
  ambientGain: 1,
  exposureBias: 0,
  saturation: 1,
  bounce: { color: "#f2d4b4", amount: 0.22 },
  classes: {
    // Lacquer wants to be smooth: a fine layer much above 0.02 reads as orange peel up close.
    // (0.03 and 0.018 made red pillars lumpy; paint is nearly flat now.)
    default: { roughness: 0.7, f0: 0.04, tint: 0, bump: [0.8, 0.012, 0.03, 0.006], paint: true },
    paving: { roughness: 0.55, f0: 0.04, tint: 0, bump: [0.6, 0.02, 0.035, 0.03] },
    tiles: { roughness: 0.78, f0: 0.03, tint: 0, bump: [0.5, 0.03, 0.06, 0.03] },
    // The sun stands 7 degrees up: on level ground a slope of 0.1 doubles or halves its light, and a
    // lawn bumped that much turned to leopard spots. Ground and rock stay gentle.
    rock: { roughness: 0.85, f0: 0.02, tint: 0, bump: [1.3, 0.14, 0.2, 0.12] },
    // Grass and earth have no shine to speak of.
    ground: { roughness: 0.95, f0: 0, tint: 0, bump: [0.6, 0.02, 0.08, 0.025] },
    // The surface classes' own reflection (materials.ts surfaceGlsl) already adds the sky and a sun
    // glint on these two, so their lamp shine stays modest.
    // (At roughness 0.3 a glazed ridge in the sun turned to a white chrome band.)
    // Metal has no bumps: on a blade they read as a dirty mirror.
    metal: { roughness: 0.5, f0: 0.25, tint: 1, bump: [0.4, 0, 0.02, 0] },
    glaze: { roughness: 0.6, f0: 0.02, tint: 0, bump: [0.5, 0.03, 0.05, 0.03] },
    // Banners swing up to a third of a metre (idle.ts BANNER, FLAG). Cloth lit from behind needs
    // nothing here: the bake's bounce holds the light that comes through it.
    cloth: { roughness: 0.9, f0: 0, tint: 0, bump: [1, 0, 1, 0], liftM: 0.45 },
  },
  specular: 0.5,
  // A soft sheen only: any glossier and a whole painted wall glares pink with the sun behind the eye
  // (strong colour cannot tell a lacquered column from a painted wall).
  paint: { sat: [0.45, 0.8], roughness: 0.68, f0: 0.04 },
  // The sheen lifts the darkest tones: kept low, or shade stops reading as shade.
  sky: { amount: 0.15, open: 0.22 },
  bump: 1,
  tiles: { roll: 0.5, fade: [0.2, 0.5] },
  // A tilt of 0.02 turned stair treads into a chequer of sunlit blocks: each tread shows a strip of the slab grid.
  paving: { tilt: 0.007, bevelM: 0.025, bevel: 0.5 },
  // graze: sin 14 degrees .. sin 24. The sun on level ground is 0.12 (the bake's), the key 0.45 (the page's).
  // A face the page still lights has a slope to the lamp under 2.3 to 3.9.
  bakedShadow: { nearM: 1.5, farM: 8, missing: 1, graze: [0.25, 0.4], close: [0.5, 1] },
  detail: { amount: 1, min: 0.4, max: 2.5, floor: 0.004 },
  bumpCap: 2.5,
  shineCap: 0.25,
  shadow: {
    size: 4096,
    marginM: 8,
    depthM: 1500,
    aheadM: 250,
    // Small biases: at 0.05 and a slope cap of 4 the thin shadow under each stair nosing broke into
    // dashes (some were left at 2.5). The normal offset and the "only where the bake is soft" rule
    // keep the acne a small bias would bring away.
    biasM: 0.03,
    normalBiasM: 0.05,
    searchM: 0.4,
    minPenumbraM: 0.06,
    maxPenumbraM: 1.5,
    minPenumbraTexels: 1.5,
    maxPenumbraTexels: 12,
    blockerTaps: 8,
    pcfTaps: 24,
    coarse: 4,
    slopeMax: 1.5,
  },
  sunShadow: {
    size: 4096,
    marginM: 8,
    depthM: 3200,
    aheadM: 300,
    biasM: 0.04,
    normalBiasM: 0.05,
    searchM: 0.3,
    minPenumbraM: 0.1,
    maxPenumbraM: 0.6,
    minPenumbraTexels: 2.5,
    maxPenumbraTexels: 12,
    // The faces the sun only grazes are the bake's (bakedShadow.graze), so its slope cap can be far under the 9 it was.
    slopeMax: 4,
  },
  // The gate (footprint 40): whole to 45 m, gone by 72 m, maps 80 m each way.
  blend: { padM: 5, fadeM: 27 },
  stops: {},
  on: { low: false, mid: false, high: true },
  handover: { stayFrames: 10, preload: true, reverseFrames: 8, leadFrames: 0, inkWaitMs: 2500 },
  grade: {
    slope: [1.02, 1.0, 0.975],
    offset: [-0.0015, 0, 0.0025],
    power: [1, 1, 1],
    shadowSat: 1.05,
    midSat: 1,
    highlightSat: 1.25,
    midStart: 0.2,
    midEnd: 0.7,
  },
};

/** The uniform values the shaders read, worked out from the index and the look (materials.ts SECT_LIVE). */
export interface LiveValues {
  sunDir: Vec3;
  /** colour * strength * sunGain. */
  sunE: Vec3;
  keyDir: Vec3;
  keyE: Vec3;
  /** 1 when the ambient map holds light without the surface colour (LiveIndex.ambientKind). */
  ambientIrr: number;
  /** The bake's soft shadow: (1 when the map has it, nearM, farM, missing). */
  vis: [number, number, number, number];
  /** bakedShadow.graze (from, to). */
  graze: [number, number];
  /** bakedShadow's (close from, close to) and 1 when the normal map's alpha says where the bake's shadow is soft. */
  close: Vec3;
  /** The bake's detail: (amount, min, max, floor). The amount is 0 unless the maps hold the bake's shadow and bounce. */
  detail: [number, number, number, number];
  /** What turns the lamps and the sky light back to the bake's own strength: 1 / (sunGain, keyGain, ambientGain). */
  bakeGain: Vec3;
  /** The bake's own post: (gain 1, its exposure, its saturation), without the look's. */
  bakePost: Vec3;
  /** (bumpCap, shineCap). */
  caps: [number, number];
  /** ambientScale * ambientGain. */
  ambient: number;
  /** The bounce fill's light (W/m2 per channel) before the 0.5 - 0.5 * N.y weight. */
  bounce: Vec3;
  gain: number;
  /** 2^(exposureStops + exposureBias). */
  exposure: number;
  /** post.saturation * saturation. */
  saturation: number;
  specular: number;
  /** (saturation from, to, the lacquer's roughness, its reflectance). */
  paint: [number, number, number, number];
  /** (the sky sheen's amount, 1 / the open-sky level, the bumps' strength). */
  surface: Vec3;
  /** (the tiles' roll, fade from, fade to). */
  tiles: Vec3;
  /** (the slabs' tilt, the bevel's width in metres, its slope). */
  paving: Vec3;
  /** The blend's (whole to, gone by) distances from the stop's centre (m). */
  blend: [number, number];
}

/**
 * The look at one stop: LIVE_LOOK with that stop's own numbers (LIVE_LOOK.stops) over it. Only
 * the LIVE_STOP_KNOBS, and only finite numbers; anything else in a stop's entry is ignored. The
 * look itself is left as it was.
 */
export function liveLookFor(look: LiveLook, stop: string): LiveLook {
  const stops = look.stops as Record<string, LiveStopLook> | undefined;
  const own = stops && Object.prototype.hasOwnProperty.call(stops, stop) ? stops[stop] : undefined;
  if (!own || typeof own !== "object") return look;
  const out: LiveLook = { ...look };
  for (const k of LIVE_STOP_KNOBS) {
    const v = own[k];
    if (typeof v === "number" && Number.isFinite(v)) out[k] = v;
  }
  return out;
}

/** The live region of a stop, from its footprint (liveStopBox). */
export interface LiveStopBox {
  /** Live is whole out to this distance from the stop's centre (m, horizontal)... */
  fromM: number;
  /** ...and gone by this one. */
  toM: number;
  /** Half the key lamp's shadow map across (m). */
  radiusM: number;
  /** Half the sun's shadow map across (m). */
  sunRadiusM: number;
}

/**
 * A stop's live region from its footprint (meta.json areas[].footprint, m): the blend is whole out
 * to footprint + padM and gone fadeM further out; each shadow map reaches its marginM past that.
 */
export function liveStopBox(footprint: number, look: LiveLook = LIVE_LOOK): LiveStopBox {
  const fromM = Math.max(footprint, 0) + Math.max(look.blend.padM, 0);
  const toM = fromM + Math.max(look.blend.fadeM, 0);
  return { fromM, toM, radiusM: toM + Math.max(look.shadow.marginM, 0), sunRadiusM: toM + Math.max(look.sunShadow.marginM, 0) };
}

/**
 * A shadow map's penumbra range (m) for a map whose texel is `texelM` wide: its narrowest is
 * minPenumbraM or minPenumbraTexels texels, whichever is wider; its widest is maxPenumbraM or
 * maxPenumbraTexels texels, whichever is narrower, and never below the narrowest.
 */
export function livePenumbra(
  s: { minPenumbraM: number; maxPenumbraM: number; minPenumbraTexels: number; maxPenumbraTexels?: number },
  texelM: number,
): [number, number] {
  const lo = Math.max(s.minPenumbraM, s.minPenumbraTexels * texelM);
  const hi = s.maxPenumbraTexels === undefined ? s.maxPenumbraM : Math.min(s.maxPenumbraM, s.maxPenumbraTexels * texelM);
  return [lo, Math.max(hi, lo)];
}

/** What a stop needs to be found by frame. */
type StopSpan = Pick<AreaMeta, "id" | "frameStart" | "frameEnd">;

/**
 * The stop a frame of the flight belongs to: the one whose frame range holds it. A frame between
 * two ranges (meta.json's are whole frames, 1-165 then 166-286: 165.5 is between) belongs to the
 * stop ahead, the one being flown toward; before the first range, the first stop; past the last,
 * the last. Null without stops or for a frame that is not a number.
 */
export function liveStopOf<A extends StopSpan>(frame: number, areas: readonly A[]): A | null {
  if (!Number.isFinite(frame)) return null;
  let best: A | null = null;
  let last: A | null = null;
  for (const a of areas) {
    if (!(a.frameEnd >= a.frameStart)) continue;
    // The range ending soonest at or after the frame: the one holding it, or else the next one.
    if (frame <= a.frameEnd && (best === null || a.frameEnd < best.frameEnd)) best = a;
    if (last === null || a.frameEnd > last.frameEnd) last = a;
  }
  return best ?? last;
}

/** The stop to light live at a frame: the stop it belongs to (liveStopOf) when it has live maps, else null. */
export function liveStopAt<A extends StopSpan>(frame: number, areas: readonly A[], withMaps: readonly string[]): A | null {
  const a = liveStopOf(frame, areas);
  return a && withMaps.includes(a.id) ? a : null;
}

/** What live.tsx knows each frame, for liveStep. `S` is a stop's loaded set (compared by identity). */
export interface LiveTick<S> {
  /** The stop lit now (its session), and whether it is fading out; null when none. */
  lit: { stop: string; fading: boolean } | null;
  /** uSectLiveMix now. */
  mix: number;
  /** The set a start under way is for, or null. */
  starting: S | null;
  /** The stop the frame names, when it has live maps (liveStopAt), else null. */
  here: string | null;
  /** That stop's resident set, or null while it is not loaded. */
  set: S | null;
  /** The set can be drawn (its textures are on the GPU). */
  ready: boolean;
  /** An earlier start failed with this very set (it is not tried again). */
  failed: boolean;
  /** An eased flight is under way to another stop: this one is only passed through. */
  passing: boolean;
  /** Fast travel's ink covers the view (store.inked): a stop left goes at once, with no fade. */
  covered?: boolean;
}

/**
 * What live light does next:
 * - keep: nothing changes (the stop lit is still the one here, its fade runs on, or the start under
 *   way is for the stop here);
 * - fade: the flight has left the stop lit: fade it out (then live.tsx ends it);
 * - resume: the flight came back to the stop lit before its fade ended: ramp up again;
 * - end: tear down now (the stop lit is left and shows only the bake already, or fast travel's ink
 *   hides it, or a start under way is for a stop the flight has left);
 * - start: start the stop here;
 * - wait: nothing lit and nothing to start: no stop here has maps, its set is not loaded or ready
 *   yet, it failed before, or it is only passed through. Never a different stop instead.
 */
export type LiveAction = "keep" | "fade" | "resume" | "end" | "start" | "wait";

export function liveStep<S>(t: LiveTick<S>): LiveAction {
  if (t.lit) {
    if (t.here === t.lit.stop) return t.lit.fading ? "resume" : "keep";
    if (t.covered) return "end";
    if (t.lit.fading) return "keep";
    return t.mix > 0 ? "fade" : "end";
  }
  if (t.starting !== null) return t.set !== null && t.starting === t.set ? "keep" : "end";
  if (t.here === null || t.set === null || !t.ready || t.failed || t.passing) return "wait";
  return "start";
}

// ---------------------------------------------------------------------------------------------
// Going from one stop to the next

/**
 * The stop to light at a frame (liveStopAt), with a memory: the stop lit or starting now
 * (`current`) stays while the frame is within `stayFrames` of its own range, either side. A visitor
 * resting on the line between two stops and scrolling a little back and forth then reloads nothing.
 * Past that band, or with no current stop, it is the frame's own stop. A jump lands far inside
 * another range and switches at once.
 */
export function liveStopKept<A extends StopSpan>(frame: number, areas: readonly A[], withMaps: readonly string[], current: string | null, stayFrames: number): A | null {
  if (current !== null && Number.isFinite(frame) && withMaps.includes(current)) {
    const stay = Math.max(stayFrames, 0);
    const a = areas.find((x) => x.id === current);
    if (a && a.frameEnd >= a.frameStart && frame >= a.frameStart - stay && frame <= a.frameEnd + stay) return a;
  }
  return liveStopAt(frame, areas, withMaps);
}

/** Which way the flight goes: 1 frames rising, -1 falling, 0 not known yet. `mark` is the furthest frame reached that way. */
export interface LiveHeading {
  dir: -1 | 0 | 1;
  mark: number;
}

/** Before the first frame. */
export const LIVE_HEADING_START: LiveHeading = { dir: 0, mark: Number.NaN };

/**
 * The way of travel once the frame is at `frame`. It turns only when the frame has gone back more
 * than `reverseFrames` from the furthest it reached, so a small scroll back (or the camera's ease
 * settling) does not turn it. A jump counts as travel. Returns `prev` itself when nothing changed.
 */
export function liveHeading(prev: LiveHeading, frame: number, reverseFrames: number): LiveHeading {
  if (!Number.isFinite(frame)) return prev;
  if (!Number.isFinite(prev.mark)) return { dir: 0, mark: frame };
  const r = Math.max(reverseFrames, 0);
  if (prev.dir === 0) {
    if (frame - prev.mark > r) return { dir: 1, mark: frame };
    if (prev.mark - frame > r) return { dir: -1, mark: frame };
    return prev;
  }
  // How far on the way it was going (negative: back).
  const on = (frame - prev.mark) * prev.dir;
  if (on > 0) return { dir: prev.dir, mark: frame };
  if (-on > r) return { dir: prev.dir === 1 ? -1 : 1, mark: frame };
  return prev;
}

/** The stop next to `id` in flight order, the way `dir` goes (1: the one after, -1: the one before), or null. */
export function liveNeighbour<A extends StopSpan>(id: string, dir: -1 | 1, areas: readonly A[]): A | null {
  const me = areas.find((a) => a.id === id);
  if (!me) return null;
  let best: A | null = null;
  for (const a of areas) {
    if (a === me || !(a.frameEnd >= a.frameStart)) continue;
    if (dir > 0) {
      if (a.frameStart > me.frameEnd && (best === null || a.frameStart < best.frameStart)) best = a;
    } else if (a.frameEnd < me.frameStart && (best === null || a.frameEnd > best.frameEnd)) best = a;
  }
  return best;
}

/** What live.tsx knows each frame, for livePreload. */
export interface LivePreloadTick {
  /** The stop lit now and not fading, or null. */
  lit: string | null;
  /** Its ramp is done (its own maps are all on the GPU and its mix is at 1). */
  litDone: boolean;
  /** The lit stop's hold frame (camera.json holds), or null. */
  hold: number | null;
  /** The stop to light at this frame (liveStopKept), or null. */
  here: string | null;
  frame: number;
  /** The way of travel (liveHeading). */
  heading: -1 | 0 | 1;
  /** The stop whose maps are held or loading now, or null. */
  held: string | null;
}

/**
 * The stop whose maps to hold ahead of need, or null (at most one stop):
 * - the stop about to start (here, not lit yet) keeps its held maps, so its start takes them;
 * - held maps of the lit stop's neighbour stay while the flight still heads there, or while the
 *   frame is still past the lit stop's hold on their side (a visitor rocking on the line between
 *   the two keeps them, however often the way of travel turns);
 * - else the neighbour the way the flight goes, if it has maps, begins once the lit stop's ramp is
 *   done and the frame is more than leadFrames past its hold that way (before then the lit stop's
 *   own start may still be putting maps on the GPU);
 * - anything else lets go: the way turned and the frame went back over the hold, the flight jumped
 *   elsewhere, nothing is lit, or preload is off.
 */
export function livePreload<A extends StopSpan>(t: LivePreloadTick, areas: readonly A[], withMaps: readonly string[], h: LiveHandover): string | null {
  if (!h.preload) return null;
  if (t.held !== null && t.held === t.here && t.here !== t.lit) return t.held;
  if (t.lit === null) return null;
  // Signed: frames after the lit stop's hold (negative: before it).
  const past = t.hold !== null && Number.isFinite(t.frame) ? t.frame - t.hold : 0;
  if (t.held !== null) {
    const side = past > 0 ? 1 : past < 0 ? -1 : 0;
    if (t.heading !== 0 && liveNeighbour(t.lit, t.heading, areas)?.id === t.held) return t.held;
    if (side !== 0 && liveNeighbour(t.lit, side, areas)?.id === t.held) return t.held;
  }
  if (t.heading === 0 || !t.litDone || t.hold === null || !Number.isFinite(t.frame)) return null;
  const next = liveNeighbour(t.lit, t.heading, areas);
  if (!next || !withMaps.includes(next.id)) return null;
  return past * t.heading > h.leadFrames ? next.id : null;
}

/**
 * Live light still has to come in at the stop the flight is at: the stop has maps (`here`), its
 * start has not failed, and it is not yet lit with the mix at 1. Fast travel's ink waits for this
 * (store.ts CanvasReport.live, settle.ts late pieces), at most handover.inkWaitMs.
 */
export function liveComing(t: { here: string | null; failed: boolean; lit: { stop: string; fading: boolean } | null; mix: number }): boolean {
  if (t.here === null || t.failed) return false;
  return !(t.lit !== null && t.lit.stop === t.here && !t.lit.fading && t.mix >= 1);
}

/**
 * Live light coming in at the stop (`coming`: liveComing) waits only for files still downloading,
 * with no work under way on anything that has arrived: no start and nothing lit (the list of stops
 * is still being read, or the stop's set is not here yet), or a start still fetching some of its
 * files (`fetching`: its index, its maps, the view table; a start taking the maps loaded ahead counts
 * theirs). Decoding, uploads, the shadow maps, the links and the ramp are work on what has arrived.
 * The loading screen's wait lets go of live light while this holds (lib/sect/settle.ts
 * SettleSnapshot.arriving), and it fades in when its maps come, as at every later stop.
 */
export function liveArriving(t: { coming: boolean; starting: boolean; lit: boolean; fetching: number }): boolean {
  if (!t.coming) return false;
  if (t.starting) return t.fetching > 0;
  return !t.lit;
}

/** A smoothstep ease from `from` to `to` at k (0..1) of the way: the mix's ramp in and fade out. */
export function liveEase(from: number, to: number, k: number): number {
  const t = Math.min(Math.max(k, 0), 1);
  return from + (to - from) * t * t * (3 - 2 * t);
}

/**
 * The shader's uniform values from a stop's index, its look (liveLookFor) and its box
 * (liveStopBox).
 */
export function liveValues(index: LiveIndex, look: LiveLook, box: Pick<LiveStopBox, "fromM" | "toM">): LiveValues {
  const { sun, key } = index.light;
  const sunE = sun.color.map((c) => c * sun.strength * look.sunGain) as Vec3;
  const keyE = key.color.map((c) => c * key.strength * look.keyGain) as Vec3;
  const level = sunE.map((s, i) => s * Math.max(sun.dir[1], 0) + keyE[i] * Math.max(key.dir[1], 0));
  const tint = hexToLinear(look.bounce.color);
  return {
    sunDir: [...sun.dir],
    sunE,
    keyDir: [...key.dir],
    keyE,
    ambientIrr: index.ambientKind === "irradiance" ? 1 : 0,
    vis: [
      index.bakedShadow ? 1 : 0,
      look.bakedShadow.nearM,
      Math.max(look.bakedShadow.farM, look.bakedShadow.nearM + 1e-3),
      Math.min(Math.max(look.bakedShadow.missing, 0), 1),
    ],
    graze: [look.bakedShadow.graze[0], Math.max(look.bakedShadow.graze[1], look.bakedShadow.graze[0] + 1e-3)],
    close: [look.bakedShadow.close[0], Math.max(look.bakedShadow.close[1], look.bakedShadow.close[0] + 1e-3), index.bakedShadow && index.bakedSoft ? 1 : 0],
    // The rebuilt bake needs the bake's own shadow and bounce: without them it is not the bake's light.
    detail: [
      // And every gain above 0: a lamp switched off cannot be turned back into the bake's.
      index.bakedShadow && index.ambientBounce && Math.min(look.sunGain, look.keyGain, look.ambientGain) > 1e-3
        ? Math.min(Math.max(look.detail.amount, 0), 1)
        : 0,
      Math.max(look.detail.min, 0),
      Math.max(look.detail.max, look.detail.min, 0),
      Math.max(look.detail.floor, 1e-5),
    ],
    bakeGain: [1 / Math.max(look.sunGain, 1e-3), 1 / Math.max(look.keyGain, 1e-3), 1 / Math.max(look.ambientGain, 1e-3)],
    bakePost: [1, Math.pow(2, index.post.exposureStops), index.post.saturation],
    caps: [Math.max(look.bumpCap, 1), Math.max(look.shineCap, 0)],
    ambient: index.ambientScale * look.ambientGain,
    // No fill where the ambient map already holds the bake's bounced light.
    bounce: index.ambientBounce
      ? [0, 0, 0]
      : [level[0] * tint[0] * look.bounce.amount, level[1] * tint[1] * look.bounce.amount, level[2] * tint[2] * look.bounce.amount],
    gain: look.gain,
    exposure: Math.pow(2, index.post.exposureStops + look.exposureBias),
    saturation: index.post.saturation * look.saturation,
    specular: look.specular,
    paint: [look.paint.sat[0], Math.max(look.paint.sat[1], look.paint.sat[0] + 1e-3), Math.min(Math.max(look.paint.roughness, 0.05), 1), look.paint.f0],
    surface: [look.sky.amount, 1 / Math.max(look.sky.open, 1e-3), look.bump],
    tiles: [look.tiles.roll, look.tiles.fade[0], Math.max(look.tiles.fade[1], look.tiles.fade[0] + 1e-3)],
    paving: [look.paving.tilt, Math.max(look.paving.bevelM, 1e-4), look.paving.bevel],
    blend: [box.fromM, Math.max(box.toM, box.fromM + 1e-3)],
  };
}

/** A class's shine as the shader's uniform holds it: (roughness, f0, tint), roughness held off 0. */
export function liveShineVec(s: LiveShine): Vec3 {
  return [Math.min(Math.max(s.roughness, 0.05), 1), Math.min(Math.max(s.f0, 0), 1), Math.min(Math.max(s.tint, 0), 1)];
}

/** A class's bumps as the shader's uniform holds them: (1 / size, slope, 1 / size, slope). */
export function liveBumpVec(s: LiveShine): [number, number, number, number] {
  const [m1, a1, m2, a2] = s.bump;
  return [1 / Math.max(m1, 1e-3), a1, 1 / Math.max(m2, 1e-3), a2];
}

/**
 * The bake's post in scene-linear light, before exposure and AgX (mirrors sectLivePost): gain, the
 * CDL, the Color Correction's saturation by level, then the Hue Saturation node's saturation (HSV:
 * toward the brightest channel). For tests and calibration notes.
 */
export function liveGradeLinear(rgb: Vec3, saturation: number, gain = 1, g: LiveLook["grade"] = LIVE_LOOK.grade): Vec3 {
  let c = rgb.map((x, i) => Math.pow(Math.max(x * gain * g.slope[i] + g.offset[i], 0), g.power[i]));
  const level = (c[0] + c[1] + c[2]) / 3;
  const w = liveLevelWeights(level, g);
  const sat = w[0] * g.shadowSat + w[1] * g.midSat + w[2] * g.highlightSat;
  const luma = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  c = c.map((x) => luma + sat * (x - luma));
  const v = Math.max(c[0], c[1], c[2]);
  return c.map((x) => Math.max(v + saturation * (x - v), 0)) as Vec3;
}

/** Blender's Color Correction weights (shadows, midtones, highlights) at a level (mean of r, g, b): 0.1 margins round midStart and midEnd. */
export function liveLevelWeights(level: number, g: LiveLook["grade"] = LIVE_LOOK.grade): Vec3 {
  const clamp = (x: number) => Math.min(Math.max(x, 0), 1);
  const s = 1 - clamp((level - (g.midStart - 0.1)) * 5);
  const h = clamp((level - (g.midEnd - 0.1)) * 5);
  return [s, 1 - s - h, h];
}

// ---------------------------------------------------------------------------------------------
// The shadow map's light space

export interface LiveShadowBox {
  radiusM: number;
  depthM: number;
  /**
   * How far past the centre, away from the lamp, the box reaches (m); the rest of depthM lies
   * toward the lamp, where the casters are. Left out: half each way.
   */
  aheadM?: number;
}

/** The middle of a map's box: the centre moved toward the lamp so the box ends aheadM past it. */
export function liveShadowBoxCentre(dir: Vec3, centre: Vec3, box: LiveShadowBox): Vec3 {
  const back = box.aheadM === undefined ? 0 : box.depthM / 2 - box.aheadM;
  const len = Math.hypot(dir[0], dir[1], dir[2]) || 1;
  return [centre[0] + (dir[0] / len) * back, centre[1] + (dir[1] / len) * back, centre[2] + (dir[2] / len) * back];
}

/**
 * An orthonormal frame for a lamp toward `dir`: `forward` is the way its light travels (-dir), `right`
 * and `up` span the map (up leans toward world +y; toward +z for a lamp straight overhead).
 */
export function liveLightBasis(dir: Vec3): { right: Vec3; up: Vec3; forward: Vec3 } {
  const len = Math.hypot(dir[0], dir[1], dir[2]) || 1;
  const f: Vec3 = [-dir[0] / len, -dir[1] / len, -dir[2] / len];
  const ref: Vec3 = Math.abs(f[1]) > 0.99 ? [0, 0, 1] : [0, 1, 0];
  // right = f x ref, up = right x f
  let r: Vec3 = [f[1] * ref[2] - f[2] * ref[1], f[2] * ref[0] - f[0] * ref[2], f[0] * ref[1] - f[1] * ref[0]];
  const rl = Math.hypot(r[0], r[1], r[2]) || 1;
  r = [r[0] / rl, r[1] / rl, r[2] / rl];
  const u: Vec3 = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]];
  return { right: r, up: u, forward: f };
}

/**
 * The shadow map's view-projection (column-major, as three's Matrix4.fromArray takes it): world
 * points within `radiusM` of `centre` across the lamp and `depthM / 2` along it go to [-1, 1]^3,
 * the centre to the middle, depth growing away from the lamp (toward -dir). With `aheadM` the box
 * is moved along the lamp (liveShadowBoxCentre): the centre stays in the middle across the map.
 */
export function liveShadowMatrix(dir: Vec3, at: Vec3, box: LiveShadowBox): number[] {
  const centre = liveShadowBoxCentre(dir, at, box);
  const { right: r, up: u, forward: f } = liveLightBasis(dir);
  const sx = 1 / box.radiusM;
  const sz = 2 / box.depthM;
  const dot = (a: Vec3) => a[0] * centre[0] + a[1] * centre[1] + a[2] * centre[2];
  // Rows: right / R, up / R, forward / (D / 2), (0, 0, 0, 1); stored by columns.
  return [
    r[0] * sx, u[0] * sx, f[0] * sz, 0,
    r[1] * sx, u[1] * sx, f[1] * sz, 0,
    r[2] * sx, u[2] * sx, f[2] * sz, 0,
    -dot(r) * sx, -dot(u) * sx, -dot(f) * sz, 1,
  ];
}

/** A point through a column-major 4x4 matrix (w divided out). */
export function liveProject(m: readonly number[], p: Vec3): Vec3 {
  const x = m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12];
  const y = m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13];
  const z = m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14];
  const w = m[3] * p[0] + m[7] * p[1] + m[11] * p[2] + m[15];
  return [x / w, y / w, z / w];
}

/**
 * The map's inverse scale: metres per unit of map UV (0..1 across) and per unit of stored depth
 * (0..1 along the lamp), the penumbra's width per metre of blocker distance for a lamp of angular
 * diameter `angleDeg`, and one texel's width (m) for a map `size` px across.
 */
export function liveShadowScale(
  box: LiveShadowBox,
  angleDeg: number,
  size: number,
): { metresPerUv: number; metresPerDepth: number; penumbraPerM: number; texelM: number } {
  return {
    metresPerUv: 2 * box.radiusM,
    metresPerDepth: box.depthM,
    penumbraPerM: 2 * Math.tan(((angleDeg * Math.PI) / 180) / 2),
    texelM: (2 * box.radiusM) / Math.max(size, 1),
  };
}

/**
 * A disc of `n` well-spread unit-disc points (a Vogel spiral: golden-angle steps, radius sqrt of
 * the step), the shadow lookup's taps (fixed: nothing turns them).
 */
export function liveDisc(n: number): [number, number][] {
  const out: [number, number][] = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < n; i++) {
    const r = Math.sqrt((i + 0.5) / n);
    const a = i * golden;
    out.push([r * Math.cos(a), r * Math.sin(a)]);
  }
  return out;
}

// ---------------------------------------------------------------------------------------------
// Switches

/** `?live=` on the page's URL: "0" / "off" keeps the bake, "1" / "on" lights live on any tier. */
export type LiveSwitch = "on" | "off" | null;

export function parseLiveParam(search: string): LiveSwitch {
  const m = /[?&]live=([a-z0-9]+)/.exec(search);
  if (!m) return null;
  if (m[1] === "0" || m[1] === "off") return "off";
  if (m[1] === "1" || m[1] === "on") return "on";
  return null;
}

/** Live light at a quality: the tier's own (Quality.liveLight, High only) unless ?live= forces it on or off. */
export function liveOn(q: Quality, sw: LiveSwitch): boolean {
  if (sw !== null) return sw === "on";
  return q.liveLight === true;
}

// ---------------------------------------------------------------------------------------------
// GLSL

const f = glslFloat;

function discGlsl(name: string, pts: readonly [number, number][]): string {
  return `const vec2 ${name}[ ${pts.length} ] = vec2[](\n${pts.map(([x, y]) => `  vec2( ${f(x)}, ${f(y)} )`).join(",\n")}\n);`;
}

/**
 * After <common> in a live material (with its other pars): the uniforms (materials.ts SECT_LIVE,
 * liveAtlasUniforms, liveClassUniforms), Blender's view transform (sectLiveView), and the functions
 * the apply block calls: sectLiveShadow and sectLiveSunShadow (PCSS on each lamp's map, and how
 * much of the lamp is left to the bake's soft shadow: sectLiveBakeShare), sectLiveBumped,
 * sectLiveGgx, sectLiveRadiance and sectLivePost.
 */
export function liveParsGlsl(look: LiveLook = LIVE_LOOK): string {
  const s = look.shadow;
  const g = look.grade;
  const blockers = Math.max(1, Math.round(s.blockerTaps));
  const pcf = Math.max(1, Math.round(s.pcfTaps));
  const coarse = Math.max(1, Math.round(s.coarse));
  return /* glsl */ `
#define SECT_LIVE
uniform sampler2D tSectLiveAlbedo;
uniform sampler2D tSectLiveAmbient;
uniform sampler2D tSectLiveNormal;
uniform float uSectLiveMix;
uniform vec3 uSectLiveSunDir;
uniform vec3 uSectLiveSunE;
uniform vec3 uSectLiveKeyDir;
uniform vec3 uSectLiveKeyE;
uniform float uSectLiveAmbient;
// 1: the ambient map is light with the surface colour divided out; the colour map multiplies it back.
uniform float uSectLiveAmbientIrr;
// The bake's soft shadow (the ambient map's alpha): x 1 when the map has it, y..z metres from the
// caster over which it takes over from the page's own, w its share where nothing casts nearby.
uniform vec4 uSectLiveVis;
// A lamp that only grazes a face is the bake's: wholly below x, not at all above y (the cosine).
uniform vec2 uSectLiveGraze;
// x..y: a caster this close (m) is the bake's. z: 1 when the normal map's alpha says where the bake's shadow is soft.
uniform vec3 uSectLiveClose;
// The bake's detail: x its amount, y..z the range it is held to, w a floor that steadies it in the dark.
uniform vec4 uSectLiveDetail;
// The bake's own light: 1 / the look's (sun, key, sky) gains, and its post's (gain, exposure, saturation).
uniform vec3 uSectLiveBakeGain;
uniform vec3 uSectLiveBakePost;
// x: bumps raise a lamp's light to at most this many times the flat face's, y: the shine's share of the surface's own light.
uniform vec2 uSectLiveCaps;
uniform vec3 uSectLiveBounce;
uniform float uSectLiveGain;
uniform float uSectLiveExposure;
uniform float uSectLiveSat;
uniform float uSectLiveSpecular;
// A class's shine: roughness, reflectance, hue tint, 1 where its strong colours are lacquer.
uniform vec4 uSectLiveSpec;
// A class's bumps: 1 / size and slope of two layers.
uniform vec4 uSectLiveBump;
// A class that moves: its shadow lookups start this far toward the lamp (m).
uniform float uSectLiveLift;
// Lacquer: saturation from, to, its roughness, its reflectance.
uniform vec4 uSectLivePaint;
// x: the sky sheen's amount, y: 1 / the open-sky level, z: the bumps' strength.
uniform vec3 uSectLiveSurface;
// Roof tiles: x how far the normal rolls across a course, y..z courses to a pixel where it fades out.
uniform vec3 uSectLiveTiles;
// Paving: x how far a slab's normal leans, y the bevel's width (m), z its slope.
uniform vec3 uSectLivePaving;
uniform vec3 uSectLiveCentre;
uniform vec2 uSectLiveBlend;
// The key lamp's map, read through the GPU's own depth compare (each read is a filtered 2x2), and
// a coarse copy with plain depths for the blocker search.
uniform highp sampler2DShadow tSectLiveShadow;
uniform highp sampler2D tSectLiveShadowB;
uniform float uSectLiveShadowOn;
uniform mat4 uSectLiveShadowMatrix;
// x: metres per map UV, y: metres per unit of depth, z: penumbra width per metre of blocker
// distance, w: one texel's width (m).
uniform vec4 uSectLiveShadowMap;
// x: depth bias (m), y: normal offset (m), z: blocker search radius (m), w: the slope's cap.
uniform vec4 uSectLiveShadowBias;
// The penumbra's width is held between these (m).
uniform vec2 uSectLiveShadowPen;
// The sun's own map, as the key's.
uniform highp sampler2DShadow tSectLiveSunShadow;
uniform highp sampler2D tSectLiveSunShadowB;
uniform float uSectLiveSunShadowOn;
uniform mat4 uSectLiveSunShadowMatrix;
uniform vec4 uSectLiveSunShadowMap;
uniform vec4 uSectLiveSunShadowBias;
uniform vec2 uSectLiveSunShadowPen;
// Blender's view transform (LIVE_VIEW): an sRGB 3D texture, so what comes out is linear display light.
uniform highp sampler3D tSectLiveView;
vec3 sectLiveView( vec3 c ) {
  vec3 t = clamp( ( log2( max( c, vec3( ${f(Math.pow(2, LIVE_VIEW.lo))} ) ) ) - ( ${f(LIVE_VIEW.lo)} ) ) / ${f(LIVE_VIEW.hi - LIVE_VIEW.lo)}, 0.0, 1.0 );
  // An explicit level: this is read inside a branch (the table has no mipmaps anyway).
  return textureLod( tSectLiveView, t * ${f((LIVE_VIEW.size - 1) / LIVE_VIEW.size)} + ${f(0.5 / LIVE_VIEW.size)}, 0.0 ).rgb;
}
${discGlsl("SECT_LIVE_BLOCKER", liveDisc(blockers))}
${discGlsl("SECT_LIVE_PCF", liveDisc(pcf))}
// A lamp's shadow from its static map: a blocker search on the coarse copy, a penumbra
// from the blockers' distance and the lamp's size, then PCF over a fixed disc, each tap a filtered
// 2x2 compare. Nothing is turned per pixel: a turned disc left a dot pattern in every soft edge.
// The bias grows with the slope to the lamp times each tap's distance from the centre plus a texel
// and a half (a tilted receiver's own depth changes across the kernel and across the 2x2 it reads). Outside
// the map: lit. scale, bias and pen are the map's uSectLive*ShadowMap, ...Bias and ...Pen.
// Returns (lit, metres from the point to what casts on it, or -1 where nothing near it casts or
// the point is outside the map).
vec2 sectLiveShadowAt( highp sampler2DShadow map, highp sampler2D coarse, mat4 toMap, vec4 scale, vec4 bias, vec2 pens, vec3 lamp, vec3 wp, vec3 n ) {
  vec4 c = toMap * vec4( wp + n * bias.y, 1.0 );
  vec3 s = c.xyz * 0.5 + 0.5;
  if ( s.x <= 0.0 || s.y <= 0.0 || s.x >= 1.0 || s.y >= 1.0 || s.z <= 0.0 || s.z >= 1.0 ) return vec2( 1.0, - 1.0 );
  float nl = clamp( dot( n, lamp ), 0.0, 1.0 );
  float slope = min( sqrt( max( 1.0 - nl * nl, 0.0 ) ) / max( nl, 1e-3 ), bias.w );
  float uvPerM = 1.0 / scale.x;
  float dPerM = 1.0 / scale.y;
  float found = 0.0;
  float depthSum = 0.0;
  for ( int i = 0; i < ${blockers}; i ++ ) {
    vec2 o = SECT_LIVE_BLOCKER[ i ] * bias.z;
    float d = textureLod( coarse, s.xy + o * uvPerM, 0.0 ).r;
    if ( d < s.z - ( bias.x + slope * ( length( o ) + scale.w * ${f(coarse)} ) ) * dPerM ) {
      depthSum += d;
      found += 1.0;
    }
  }
  // Nothing found is not "lit": a thin caster can slip between the coarse map's texels. The
  // narrowest edge then, and the fine map decides.
  float pen = found < 0.5 ? pens.x : clamp( ( s.z - depthSum / found ) * scale.y * scale.z, pens.x, pens.y );
  float lit = 0.0;
  for ( int i = 0; i < ${pcf}; i ++ ) {
    vec2 o = SECT_LIVE_PCF[ i ] * ( 0.5 * pen );
    // With no gradients: this is a loop inside the live branch (and the map has one level).
    lit += textureGrad( map, vec3( s.xy + o * uvPerM, s.z - ( bias.x + slope * ( length( o ) + scale.w * 1.5 ) ) * dPerM ), vec2( 0.0 ), vec2( 0.0 ) );
  }
  return vec2( lit / ${f(pcf)}, found < 0.5 ? - 1.0 : ( s.z - depthSum / found ) * scale.y );
}
// How far a lamp's light at a point is left to the bake's soft shadow, from the page's lookup r
// (lit, metres to the caster): not at all close to the caster, wholly far from it, and by
// uSectLiveVis.w where nothing near the point casts (the caster is far off, or not in the page).
// Wholly again where the caster is right at the surface (uSectLiveClose: the map cannot draw a
// shadow that small). 0 when the stop's maps have no baked shadow.
float sectLiveBakeShare( vec2 r ) {
  return ( r.y < 0.0 ? uSectLiveVis.w : max( smoothstep( uSectLiveVis.y, uSectLiveVis.z, r.y ), 1.0 - smoothstep( uSectLiveClose.x, uSectLiveClose.y, r.y ) ) ) * uSectLiveVis.x;
}
// The same for a lamp that only grazes the face (nl, the cosine between them): the bake's whatever
// casts. One texel of the map is 1 / nl texels long on such a face.
float sectLiveGraze( float nl ) {
  return ( 1.0 - smoothstep( uSectLiveGraze.x, uSectLiveGraze.y, nl ) ) * uSectLiveVis.x;
}
// The key lamp's shadow, and the sun's, at a face of normal n (the map's, without the bumps), as
// (the page's own shadow, 1 lit .. 0 shade; the share of this lamp's light left to the bake). A
// face turned away from a lamp is in its own shadow: (0, 0) with no lookup, so a bump that leans
// back toward the lamp gets no light there. The first few degrees past the edge fade in, the
// share with them: left whole, a bump at the very edge took the bake's full light at once. A face
// the lamp only grazes is the bake's, with no lookup.
vec2 sectLiveShadow( vec3 wp, vec3 n ) {
  float nl = dot( n, uSectLiveKeyDir );
  if ( nl <= 0.0 ) return vec2( 0.0 );
  float edge = smoothstep( 0.0, 0.06, nl );
  float graze = sectLiveGraze( nl );
  if ( graze >= 1.0 ) return vec2( edge );
  vec2 r = vec2( 1.0, - 1.0 );
  if ( uSectLiveShadowOn > 0.5 ) r = sectLiveShadowAt( tSectLiveShadow, tSectLiveShadowB, uSectLiveShadowMatrix, uSectLiveShadowMap, uSectLiveShadowBias, uSectLiveShadowPen, uSectLiveKeyDir, wp, n );
  return edge * vec2( r.x, max( sectLiveBakeShare( r ), graze ) );
}
vec2 sectLiveSunShadow( vec3 wp, vec3 n ) {
  float nl = dot( n, uSectLiveSunDir );
  if ( nl <= 0.0 ) return vec2( 0.0 );
  float edge = smoothstep( 0.0, 0.06, nl );
  float graze = sectLiveGraze( nl );
  if ( graze >= 1.0 ) return vec2( edge );
  vec2 r = vec2( 1.0, - 1.0 );
  if ( uSectLiveSunShadowOn > 0.5 ) r = sectLiveShadowAt( tSectLiveSunShadow, tSectLiveSunShadowB, uSectLiveSunShadowMatrix, uSectLiveSunShadowMap, uSectLiveSunShadowBias, uSectLiveSunShadowPen, uSectLiveSunDir, wp, n );
  return edge * vec2( r.x, max( sectLiveBakeShare( r ), graze ) );
}
// Value noise with its gradient (after Inigo Quilez): x the value 0..1, yzw its slope.
float sectLiveHash( vec3 p ) {
  p = fract( p * 0.3183099 + 0.1 );
  p *= 17.0;
  return fract( p.x * p.y * p.z * ( p.x + p.y + p.z ) );
}
vec4 sectLiveNoised( vec3 x ) {
  vec3 i = floor( x );
  vec3 w = fract( x );
  vec3 u = w * w * w * ( w * ( w * 6.0 - 15.0 ) + 10.0 );
  vec3 du = 30.0 * w * w * ( w * ( w - 2.0 ) + 1.0 );
  float a = sectLiveHash( i );
  float b = sectLiveHash( i + vec3( 1.0, 0.0, 0.0 ) );
  float c = sectLiveHash( i + vec3( 0.0, 1.0, 0.0 ) );
  float d = sectLiveHash( i + vec3( 1.0, 1.0, 0.0 ) );
  float e = sectLiveHash( i + vec3( 0.0, 0.0, 1.0 ) );
  float f = sectLiveHash( i + vec3( 1.0, 0.0, 1.0 ) );
  float g = sectLiveHash( i + vec3( 0.0, 1.0, 1.0 ) );
  float h = sectLiveHash( i + vec3( 1.0, 1.0, 1.0 ) );
  float k1 = b - a;
  float k2 = c - a;
  float k3 = e - a;
  float k4 = a - b - c + d;
  float k5 = a - c - e + g;
  float k6 = a - b - e + f;
  float k7 = - a + b + c - d + e - f - g + h;
  return vec4(
    a + k1 * u.x + k2 * u.y + k3 * u.z + k4 * u.x * u.y + k5 * u.y * u.z + k6 * u.z * u.x + k7 * u.x * u.y * u.z,
    du * vec3( k1 + k4 * u.y + k6 * u.z + k7 * u.y * u.z, k2 + k5 * u.z + k4 * u.x + k7 * u.z * u.x, k3 + k6 * u.x + k5 * u.y + k7 * u.x * u.y )
  );
}
// The normal n at p with the class's bumps (k: uSectLiveBump) on it. fw is the pixel's width at p
// (m): a layer fades out before its bumps get smaller than a few pixels.
vec3 sectLiveBumped( vec3 n, vec3 p, vec4 k, float fw ) {
  float w1 = ( 1.0 - smoothstep( 0.12, 0.4, fw * k.x ) ) * k.y * uSectLiveSurface.z;
  float w2 = ( 1.0 - smoothstep( 0.12, 0.4, fw * k.z ) ) * k.w * uSectLiveSurface.z;
  vec3 g = vec3( 0.0 );
  if ( w1 > 0.0 ) g += sectLiveNoised( p * k.x ).yzw * w1;
  if ( w2 > 0.0 ) g += sectLiveNoised( p * k.z + 17.3 ).yzw * w2;
  g -= n * dot( g, n );
  return normalize( n - g );
}
// GGX shine of a lamp toward l (times its irradiance at normal incidence): Smith-correlated
// visibility, Schlick's Fresnel held down by the roughness, alpha = roughness squared.
vec3 sectLiveGgx( vec3 n, vec3 v, vec3 l, float rough, vec3 f0 ) {
  float nl = dot( n, l );
  if ( nl <= 0.0 ) return vec3( 0.0 );
  vec3 h = l + v;
  h *= inversesqrt( max( dot( h, h ), 1e-8 ) );
  float nv = clamp( dot( n, v ), 1e-3, 1.0 );
  float nh = clamp( dot( n, h ), 0.0, 1.0 );
  float vh = clamp( dot( v, h ), 0.0, 1.0 );
  float a = rough * rough;
  float a2 = a * a;
  float dd = nh * nh * ( a2 - 1.0 ) + 1.0;
  float D = a2 / ( PI * dd * dd );
  float gv = nl * sqrt( nv * nv * ( 1.0 - a2 ) + a2 );
  float gl = nv * sqrt( nl * nl * ( 1.0 - a2 ) + a2 );
  float V = 0.5 / max( gv + gl, 1e-6 );
  // Schlick's Fresnel, with the low-angle end held down by the roughness and gone where there is
  // no reflectance at all: a matte surface does not turn into a mirror at a low angle (with the
  // plain form, grass facing the low sun went pale with glare).
  vec3 f90 = max( f0, clamp( f0 * 25.0, 0.0, 1.0 ) * ( 1.0 - rough ) );
  vec3 F = f0 + ( f90 - f0 ) * pow( 1.0 - vh, 5.0 );
  return F * ( V * D * nl );
}
// Linear radiance at a surface of albedo alb with ambient light amb (the ambient map, scaled),
// normal n, toward the eye v, lit by the two lamps, plus the shine and the bounce fill. sSun and
// sKey are each lamp's (own shadow, share left to the bake), bake.x the bake's soft shadow (vis
// below): how much
// of the two lamps' light together the bake let through. It is one number for both lamps, so it
// is used on their sum: what each lamp keeps of its own shadow comes first, and the part left to
// the bake is what the bake's total has over that, no more than those lamps could give. (Used on
// each lamp alone it cut the sun under an eave where only the key is shaded.) face is what the
// flat face gets from (the sun, the key): the bumps and the tiles' roll can add to that, up to
// uSectLiveCaps.x times it, since on a face that barely sees a lamp real bumps shade each other
// (tile crowns lit up on a roof face turned away).
vec3 sectLiveRadiance( vec3 alb, vec3 amb, vec3 n, vec3 v, vec2 sSun, vec2 sKey, vec2 bake, vec2 face, float rough, float refl ) {
  float vis = bake.x;
  vec2 raw = vec2( max( dot( n, uSectLiveSunDir ), 0.0 ), max( dot( n, uSectLiveKeyDir ), 0.0 ) );
  vec2 nl = min( raw, face * uSectLiveCaps.x );
  vec2 kept = vec2( raw.x > 1e-5 ? nl.x / raw.x : 1.0, raw.y > 1e-5 ? nl.y / raw.y : 1.0 );
  vec3 fromSun = uSectLiveSunE * nl.x;
  vec3 fromKey = uSectLiveKeyE * nl.y;
  vec3 own = fromSun * ( sSun.x * ( 1.0 - sSun.y ) ) + fromKey * ( sKey.x * ( 1.0 - sKey.y ) );
  vec3 cap = fromSun * sSun.y + fromKey * sKey.y;
  vec3 seen = own + clamp( ( fromSun + fromKey ) * vis - own, vec3( 0.0 ), cap );
  // The page's maps only tighten the bake's shadow, and only where the bake holds it soft (bake.y:
  // 1 near an edge of its shadow, 0 where it does not change). They never let in more light than
  // the bake did: they have gaps the bake has not (faces the flight never sees are not in the
  // page, a roof seen edge-on from a lamp is a sliver), and light came through them in dashes.
  vec3 baked = ( fromSun + fromKey ) * vis;
  vec3 lamps = mix( baked, min( seen, baked ), bake.y );
  vec3 direct = alb * RECIPROCAL_PI * lamps;
  float lum = dot( alb, vec3( 0.2126, 0.7152, 0.0722 ) );
  vec3 hue = lum > 1e-3 ? clamp( alb / lum, 0.0, 2.0 ) : vec3( 1.0 );
  vec3 f0 = clamp( refl * mix( vec3( 1.0 ), hue, uSectLiveSpec.z ), 0.0, 1.0 );
  // The shine follows the diffuse light: a lamp keeps its own shadow, and of its part left to
  // the bake it gets as much as the sum above did (got, 0..1); what the cap took off the bumps'
  // light it takes off their shine.
  float got = dot( seen - own, vec3( 0.2126, 0.7152, 0.0722 ) ) / max( dot( cap, vec3( 0.2126, 0.7152, 0.0722 ) ), 1e-5 );
  // What the bake's own shadow took off the lamps' light there it takes off their shine.
  float held = min( dot( lamps, vec3( 0.2126, 0.7152, 0.0722 ) ) / max( dot( seen, vec3( 0.2126, 0.7152, 0.0722 ) ), 1e-5 ), 1.0 );
  // And where the bake's shadow is not soft the shine is in the bake's shadow too, as the light is.
  vec2 lit = mix( vec2( vis ), vec2( sSun.x * ( 1.0 - sSun.y ) + sSun.y * got, sKey.x * ( 1.0 - sKey.y ) + sKey.y * got ) * held, bake.y );
  vec3 shine = sectLiveGgx( n, v, uSectLiveSunDir, rough, f0 ) * uSectLiveSunE * ( lit.x * kept.x ) + sectLiveGgx( n, v, uSectLiveKeyDir, rough, f0 ) * uSectLiveKeyE * ( lit.y * kept.y );
  vec3 bounce = alb * RECIPROCAL_PI * uSectLiveBounce * ( 0.5 - 0.5 * n.y );
  vec3 matte = amb + direct + bounce;
  // And it is held to a share of the surface's own light: a navy board went lavender, a teal
  // ridge cream.
  shine *= uSectLiveSpecular;
  shine *= min( 1.0, uSectLiveCaps.y * dot( matte, vec3( 0.2126, 0.7152, 0.0722 ) ) / max( dot( shine, vec3( 0.2126, 0.7152, 0.0722 ) ), 1e-5 ) );
  return matte + shine;
}
// The bake's own light at a texel as these maps rebuild it: its sky and bounced light, and the two
// lamps at the bake's strength on the flat face, through the bake's shadow.
vec3 sectLiveBaked( vec3 alb, vec3 amb, vec2 face, float vis ) {
  return amb * uSectLiveBakeGain.z + alb * RECIPROCAL_PI * ( uSectLiveSunE * ( uSectLiveBakeGain.x * face.x ) + uSectLiveKeyE * ( uSectLiveBakeGain.y * face.y ) ) * vis;
}
// The bake's detail: the baked texel over that rebuilt light (both display light), which the live
// colour is multiplied by. Where the rebuilt light is not to be trusted (the edge of a shadow cast
// from close by, which these maps hold softer than the bake does) only its hue is taken, not its
// level: the bake's brightness over the rebuilt light's is taken back out.
vec3 sectLiveDetail( vec3 baked, vec3 rebuilt, float trust ) {
  vec3 b = baked + uSectLiveDetail.w;
  vec3 q = rebuilt + uSectLiveDetail.w;
  vec3 r = b / q;
  r *= mix( dot( q, vec3( 0.2126, 0.7152, 0.0722 ) ) / dot( b, vec3( 0.2126, 0.7152, 0.0722 ) ), 1.0, trust );
  return mix( vec3( 1.0 ), clamp( r, uSectLiveDetail.y, uSectLiveDetail.z ), uSectLiveDetail.x );
}
// The bake's own post on linear radiance (bake_web.py post_scene): the CDL grade, the Color
// Correction's saturation by level, the Hue Saturation node (HSV), exposure, then Blender's view.
// Display-referred linear out, as three's decode leaves a baked texel. by: (gain, exposure,
// saturation), the look's for the live colour and the bake's own for the rebuilt bake.
vec3 sectLivePostBy( vec3 c, vec3 by ) {
  c = pow( max( c * by.x * ${glslVec3(g.slope)} + ${glslVec3(g.offset)}, 0.0 ), ${glslVec3(g.power)} );
  float lev = ( c.r + c.g + c.b ) / 3.0;
  float wS = 1.0 - clamp( ( lev - ${f(g.midStart - 0.1)} ) * 5.0, 0.0, 1.0 );
  float wH = clamp( ( lev - ${f(g.midEnd - 0.1)} ) * 5.0, 0.0, 1.0 );
  float sat = wS * ${f(g.shadowSat)} + ( 1.0 - wS - wH ) * ${f(g.midSat)} + wH * ${f(g.highlightSat)};
  float luma = dot( c, vec3( 0.2126, 0.7152, 0.0722 ) );
  c = vec3( luma ) + sat * ( c - vec3( luma ) );
  float top = max( c.r, max( c.g, c.b ) );
  c = max( vec3( top ) + by.z * ( c - vec3( top ) ), 0.0 );
  return sectLiveView( c * by.y );
}
vec3 sectLivePost( vec3 c ) {
  return sectLivePostBy( c, vec3( uSectLiveGain, uSectLiveExposure, uSectLiveSat ) );
}
`;
}

/**
 * Right after the baked texel is read (materials.ts patchMaterial: `vec3 sectTexel = ...`), at the
 * top of main: the three maps at the atlas UV, the normal, the share of live light here (uSectLiveMix, faded out from blend.x to blend.y metres
 * from the centre), and where that share is above 0 the lit colour mixed in. Leaves sectLiveN and
 * sectLiveShare for the surface classes (liveSurfaceNormalGlsl). With uSectLiveMix at 0 nothing
 * here touches sectTexel.
 *
 * An empty normal texel keeps the bake. Two kinds: grey (0.5, the decoded normal near 0 long) and
 * black, which is what Blender's object-space normal bake clears to: written as n / 2 + 0.5 after
 * the axis swap it reads back as (-1, -1, 1), about 1.73 long. A real normal is about 1 long (mip
 * levels only shorten it), so anything under 0.5 or over 1.25 is taken as empty.
 */
export function liveApplyGlsl(tiles = false, paving = false): string {
  // Roof tiles (a material of the tiles detail class, which has the tile coordinates vSectUv1, one
  // course to a unit across): the way across the courses on the surface, from screen derivatives
  // taken before the branch, and how many courses a pixel spans.
  const tilesPre = tiles
    ? `
    vec3 lTx = dFdx( vSectWorld ) * dFdy( vSectUv1 ).y - dFdy( vSectWorld ) * dFdx( vSectUv1 ).y;
    float lTw = fwidth( vSectUv1.x );`
    : "";
  // A half-round course: the normal leans away from the crest on both sides.
  const tilesRoll = tiles
    ? `
      vec3 lTd = lTx - sectLiveN * dot( lTx, sectLiveN );
      float lTl = length( lTd );
      float lTk = uSectLiveTiles.x * uSectLiveSurface.z * ( 1.0 - smoothstep( uSectLiveTiles.y, uSectLiveTiles.z, lTw ) );
      if ( lTk > 0.0 && lTl > 1e-9 ) sectLiveN = normalize( sectLiveN + ( lTd / lTl ) * ( sin( 6.2831853 * ( fract( vSectUv1.x + 0.5 ) - 0.5 ) ) * lTk ) );`
    : "";
  // Paving (a material of the paving detail class, which has the slab coordinates vSectUv1 in
  // metres and sectSlab, sectSlabPos and sectHash3 from detail.ts): the two ways along the slab
  // plane on the surface, and a pixel's size in it, from screen derivatives taken before the branch.
  const pavingPre = paving
    ? `
    vec3 lPx = dFdx( vSectWorld );
    vec3 lPy = dFdy( vSectWorld );
    vec2 lUx = dFdx( vSectUv1 );
    vec2 lUy = dFdy( vSectUv1 );
    // (Times the sign of the UVs' turn: on mirrored UVs the two would point backward.)
    float lPd = lUx.x * lUy.y - lUx.y * lUy.x < 0.0 ? - 1.0 : 1.0;
    vec3 lPu = ( lPx * lUy.y - lPy * lUx.y ) * lPd;
    vec3 lPv = ( lPy * lUx.x - lPx * lUy.x ) * lPd;
    float lPw = max( length( lUx ) + length( lUy ), 1e-5 );`
    : "";
  // Each slab leans its own way, and its edges fall into the joint. On the slab tops only.
  const pavingRelief = paving
    ? `
      if ( dot( lPu, lPu ) > 1e-18 && dot( lPv, lPv ) > 1e-18 ) {
        vec2 lPe;
        vec2 lPid = sectSlab( vSectUv1, lPe );
        vec2 lPs = sign( sectSlabPos( vSectUv1, lPid ) - lPe - 1e-4 );
        vec3 lPh = sectHash3( lPid + 29.1 );
        // The bevel, thinned as a pixel grows past it.
        vec2 lPb = ( 1.0 - smoothstep( vec2( 0.0 ), vec2( uSectLivePaving.y ), lPe ) ) * lPs * ( uSectLivePaving.z * clamp( uSectLivePaving.y / lPw, 0.0, 1.0 ) );
        vec2 lPg = ( lPh.xy - 0.5 ) * ( 2.0 * uSectLivePaving.x ) + lPb;
        float lPk = uSectLiveSurface.z * smoothstep( 0.55, 0.8, abs( lNg.y ) );
        sectLiveN = normalize( sectLiveN + ( normalize( lPu ) * lPg.x + normalize( lPv ) * lPg.y ) * lPk );
      }`
    : "";
  return /* glsl */ `  vec3 sectLiveN = vec3( 0.0, 1.0, 0.0 );
  float sectLiveShare = 0.0;
  // For the sky sheen (liveSheenGlsl): roughness, reflectance, how much of the sky the point sees.
  vec3 sectLiveGloss = vec3( 1.0, 0.0, 0.0 );
  {
    float lFw = length( fwidth( vSectWorld ) );${tilesPre}${pavingPre}
    vec3 lAlb = texture2D( tSectLiveAlbedo, vMapUv ).rgb;
    vec4 lAmbA = texture2D( tSectLiveAmbient, vMapUv );
    vec3 lAmb = lAmbA.rgb;
    // The bake's soft shadow. Its two ends are held (the raw bake's noise would mottle full light)
    // and it is straight in between: the sum reads it as a share of the lamps' light.
    float lVis = clamp( ( lAmbA.a - 0.04 ) / 0.86, 0.0, 1.0 );
    // At the map's top the light there was brighter than 8 bits hold (beside a lantern, in a
    // furnace's glow): that texel keeps the bake.
    float lHot = smoothstep( 0.88, 0.98, max( lAmb.r, max( lAmb.g, lAmb.b ) ) );
    lAmb = mix( lAmb, lAmb * lAlb, uSectLiveAmbientIrr );
    vec4 lNtA = texture2D( tSectLiveNormal, vMapUv );
    vec3 lNt = lNtA.rgb * 2.0 - 1.0;
    // Where the bake's shadow is soft (1 near an edge of it, 0 where it does not change), from the
    // normal map's alpha. 1 everywhere when the map has none.
    float lSoft = mix( 1.0, lNtA.a, uSectLiveClose.z );
    float lNl = length( lNt );
    float lFar = smoothstep( uSectLiveBlend.x, uSectLiveBlend.y, length( vSectWorld.xz - uSectLiveCentre.xz ) );
    sectLiveShare = lNl >= 0.5 && lNl <= 1.25 ? uSectLiveMix * ( 1.0 - lFar ) * ( 1.0 - lHot ) : 0.0;
    if ( sectLiveShare > 0.0 ) {
      // Shadows from the face as the bake has it; the light from the face with its bumps.
      vec3 lNg = lNt / lNl;
      vec3 lV = normalize( cameraPosition - vSectWorld );
      vec2 lKey = sectLiveShadow( vSectWorld + uSectLiveKeyDir * uSectLiveLift, lNg );
      vec2 lSun = sectLiveSunShadow( vSectWorld + uSectLiveSunDir * uSectLiveLift, lNg );
      // What the flat face gets from (the sun, the key).
      vec2 lFace = vec2( max( dot( lNg, uSectLiveSunDir ), 0.0 ), max( dot( lNg, uSectLiveKeyDir ), 0.0 ) );
      sectLiveN = sectLiveBumped( lNg, vSectWorld, uSectLiveBump, lFw );${tilesRoll}${pavingRelief}
      // Lacquer: the more saturated a painted class's colour, the glossier.
      float lMax = max( lAlb.r, max( lAlb.g, lAlb.b ) );
      float lSat = ( lMax - min( lAlb.r, min( lAlb.g, lAlb.b ) ) ) / max( lMax, 1e-3 ) * smoothstep( 0.02, 0.08, lMax );
      float lPaint = smoothstep( uSectLivePaint.x, uSectLivePaint.y, lSat ) * uSectLiveSpec.w;
      float lRough = mix( uSectLiveSpec.x, uSectLivePaint.z, lPaint );
      float lRefl = mix( uSectLiveSpec.y, uSectLivePaint.w, lPaint );
      float lLa = dot( lAlb, vec3( 0.2126, 0.7152, 0.0722 ) );
      sectLiveGloss = vec3( lRough, lRefl, clamp( dot( lAmb, vec3( 0.2126, 0.7152, 0.0722 ) ) * uSectLiveAmbient / max( lLa, 0.02 ) * uSectLiveSurface.y, 0.0, 1.0 ) );
      vec3 lTex = sectLivePost( sectLiveRadiance( lAlb, lAmb * uSectLiveAmbient, sectLiveN, lV, lSun, lKey, vec2( lVis, lSoft ), lFace, lRough, lRefl ) );
      vec3 lBake = sectLivePostBy( sectLiveBaked( lAlb, lAmb * uSectLiveAmbient, lFace, lVis ), uSectLiveBakePost );
      // As three's color_fragment multiplies the baked texel (vColor is a vec4 in three r186).
      #if defined( USE_COLOR ) || defined( USE_COLOR_ALPHA )
        lTex *= vColor.rgb;
        lBake *= vColor.rgb;
      #endif
      // The rebuilt bake is trusted except at the edge of a shadow cast from close by: there the
      // lamps keep the page's own shadow (little is left to the bake) and the bake's is half way.
      vec2 lW = lFace * vec2( dot( uSectLiveSunE, vec3( 0.2126, 0.7152, 0.0722 ) ), dot( uSectLiveKeyE, vec3( 0.2126, 0.7152, 0.0722 ) ) );
      float lLeft = lW.x + lW.y > 1e-5 ? ( lW.x * lSun.y + lW.y * lKey.y ) / ( lW.x + lW.y ) : 1.0;
      float lTrust = 1.0 - ( 1.0 - lLeft ) * smoothstep( 0.2, 0.6, 4.0 * lVis * ( 1.0 - lVis ) );
      lTex *= sectLiveDetail( sectTexel, lBake, lTrust );
      sectTexel = mix( sectTexel, lTex, sectLiveShare );
    }
  }`;
}

/**
 * Before <opaque_fragment> in a live material with no reflective class of its own (metal and glaze
 * have surfaceGlsl): the sky in a smooth surface. Fresnel by the bumped normal, less for a rough
 * surface and where the point sees little sky, mixed over the graded colour as the surface classes
 * do (materials.ts ENV_GLSL sectEnvSky is display light too).
 */
export function liveSheenGlsl(): string {
  return /* glsl */ `
  if ( sectLiveShare > 0.0 ) {
    vec3 hV = normalize( vSectWorld - cameraPosition );
    vec3 hN = dot( sectLiveN, hV ) > 0.0 ? - sectLiveN : sectLiveN;
    float hF5 = pow( 1.0 - clamp( - dot( hV, hN ), 0.0, 1.0 ), 5.0 );
    float hSmooth = ( 1.0 - sectLiveGloss.x ) * ( 1.0 - sectLiveGloss.x );
    float hF = ( sectLiveGloss.y + ( 1.0 - sectLiveGloss.y ) * hF5 ) * hSmooth * sectLiveGloss.z * uSectLiveSurface.x * sectLiveShare;
    outgoingLight = mix( outgoingLight, sectEnvSky( reflect( hV, hN ), sectLiveGloss.x ), clamp( hF, 0.0, 1.0 ) );
  }`;
}

/**
 * In a live material's surface class (materials.ts surfaceGlsl), after the flat face normal is
 * turned toward the eye: the normal map's normal (turned the same way) takes over by the live share.
 */
export function liveSurfaceNormalGlsl(): string {
  return /* glsl */ `
    if ( sectLiveShare > 0.0 ) {
      vec3 sLn = dot( sectLiveN, sV ) > 0.0 ? - sectLiveN : sectLiveN;
      vec3 sMx = mix( sN, sLn, sectLiveShare );
      if ( dot( sMx, sMx ) > 1e-8 ) sN = normalize( sMx );
    }`;
}
