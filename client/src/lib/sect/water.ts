/**
 * Still water for /sect. The bake has no reflections, so the pond reads as flat dark teal; the web
 * adds an analytic planar reflection: the sky gradient plus the glowing Heart-Mirror, found by
 * intersecting the reflected view ray with the mirror's disc. Pure geometry helpers here (no
 * three.js) so the water level and disc fitting are testable.
 *
 * Also the life at the waterfall feet (experience/waterfall-fx.tsx): which falls land on ground,
 * where each foot is, the foam skirt's mesh, and the spray and mist-puff motion that the shaders
 * mirror (sprayDrop / WFX_SPRAY_GLSL, mistPuff / WFX_PUFF_GLSL).
 */
import { PETAL_WIND } from "./fx";
import { glslFloat } from "./glsl";
import type { AreaMeta, Vec3 } from "./types";

export interface WaterSurface {
  /** Height of the water plane (three y). */
  level: number;
  /** A glowing disc mirrored in the water, or null. */
  disc: { center: Vec3; normal: Vec3; radius: number } | null;
}

/**
 * Height of the largest flat, level surface in a triangle soup (world-space xyz triplets): the
 * area-weighted mode of the heights of near-horizontal triangles, in `bin` m bins. A pond mesh
 * also holds its stones, basin and lily pads; the open water is by far the largest level area.
 */
export function dominantFlatLevel(
  positions: ArrayLike<number>,
  index: ArrayLike<number> | null,
  bin = 0.02,
  minUp = 0.995,
): { level: number; area: number } | null {
  const tri = index ? index.length / 3 : positions.length / 9;
  const bins = new Map<number, { area: number; sumY: number }>();
  for (let t = 0; t < tri; t++) {
    const ia = index ? index[t * 3] : t * 3;
    const ib = index ? index[t * 3 + 1] : t * 3 + 1;
    const ic = index ? index[t * 3 + 2] : t * 3 + 2;
    const ax = positions[ia * 3], ay = positions[ia * 3 + 1], az = positions[ia * 3 + 2];
    const ux = positions[ib * 3] - ax, uy = positions[ib * 3 + 1] - ay, uz = positions[ib * 3 + 2] - az;
    const vx = positions[ic * 3] - ax, vy = positions[ic * 3 + 1] - ay, vz = positions[ic * 3 + 2] - az;
    const nx = uy * vz - uz * vy;
    const ny = uz * vx - ux * vz;
    const nz = ux * vy - uy * vx;
    const len = Math.hypot(nx, ny, nz);
    if (len < 1e-12 || Math.abs(ny) / len < minUp) continue;
    const y = (ay + positions[ib * 3 + 1] + positions[ic * 3 + 1]) / 3;
    const k = Math.round(y / bin);
    const b = bins.get(k) ?? { area: 0, sumY: 0 };
    b.area += len / 2;
    b.sumY += (y * len) / 2;
    bins.set(k, b);
  }
  let best: { area: number; sumY: number } | null = null;
  for (const b of bins.values()) if (!best || b.area > best.area) best = b;
  return best ? { level: best.sumY / best.area, area: best.area } : null;
}

/**
 * A thin box (the mirror's glowing face) as a disc: centre, the box's thinnest axis as the normal
 * (turned to face `toward`), and a radius from the two wide axes.
 */
export function discFromBox(min: Vec3, max: Vec3, toward: Vec3): { center: Vec3; normal: Vec3; radius: number } {
  const center: Vec3 = [(min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2];
  const size: Vec3 = [max[0] - min[0], max[1] - min[1], max[2] - min[2]];
  let thin = 0;
  for (let i = 1; i < 3; i++) if (size[i] < size[thin]) thin = i;
  const normal: Vec3 = [0, 0, 0];
  normal[thin] = toward[thin] - center[thin] >= 0 ? 1 : -1;
  const wide = size.filter((_, i) => i !== thin);
  return { center, normal, radius: Math.min(wide[0], wide[1]) / 2 };
}

/** Schlick Fresnel for water (F0 = 0.02) at the angle between the view ray and the surface normal. */
export function waterFresnel(cosTheta: number): number {
  const c = Math.min(Math.max(cosTheta, 0), 1);
  return 0.02 + 0.98 * Math.pow(1 - c, 5);
}

/**
 * A waterfall sheet as a quad from its exported corners (lip-left, lip-right, foot-right,
 * foot-left, world space). UV u runs across (0 left, 1 right), v along the fall (1 at the lip).
 * Built from the corners directly, so nothing is rotated twice.
 */
export function quadFromCorners(c: readonly [Vec3, Vec3, Vec3, Vec3]): {
  positions: Float32Array;
  uvs: Float32Array;
  index: Uint16Array;
} {
  const positions = new Float32Array([...c[0], ...c[1], ...c[2], ...c[3]]);
  const uvs = new Float32Array([0, 1, 1, 1, 1, 0, 0, 0]);
  return { positions, uvs, index: new Uint16Array([0, 3, 1, 1, 3, 2]) };
}

/** Width (lip) and height of a sheet from its corners. */
export function sheetExtent(c: readonly [Vec3, Vec3, Vec3, Vec3]): { width: number; height: number } {
  const d = (a: Vec3, b: Vec3) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
  return { width: d(c[0], c[1]), height: (d(c[0], c[3]) + d(c[1], c[2])) / 2 };
}

export interface MistSpot {
  position: Vec3;
  radius: number;
}

/**
 * Spray at the foot of the falls that land on something (feet above the cloud sea; the falls off
 * the range's edges pour into the clouds). Sheets of one fall share a foot, so feet closer than
 * `merge` metres become one spot. Pass the falls through groundedFalls first: an island's fall
 * that stops in mid-air also has its foot above the clouds.
 */
export function mistSpots(
  falls: readonly { foot: Vec3 | null; corners: readonly Vec3[] | null; nearestM: number }[],
  cloudTopY: number,
  maxDistance = 1500,
  merge = 12,
): MistSpot[] {
  const out: MistSpot[] = [];
  for (const f of falls) {
    if (!f.foot || !f.corners || f.nearestM > maxDistance || f.foot[1] < cloudTopY + 5) continue;
    const c = f.corners as [Vec3, Vec3, Vec3, Vec3];
    const r = Math.max(4, sheetExtent(c).width * 1.1);
    const near = out.find((m) => Math.hypot(m.position[0] - f.foot![0], m.position[1] - f.foot![1], m.position[2] - f.foot![2]) < merge);
    if (near) near.radius = Math.max(near.radius, r);
    else out.push({ position: [f.foot[0], f.foot[1] + r * 0.35, f.foot[2]], radius: r });
  }
  return out;
}

// ---------------------------------------------------------------------------------------------
// Life at the waterfall feet (experience/waterfall-fx.tsx)

/**
 * Tuning for the foot effects. Lengths in metres, times in seconds, speeds in m/s; "x width" scales
 * by the fall's widest lip, "x scale" by fxScale(width) (1 for the abode's 6 m fall).
 */
export const WATERFALL_FX = {
  /** A foot lands on an area's ground when it is within the area's footprint plus this... */
  groundMargin: 15,
  /** ...and no more than this above or below the area's anchor. */
  groundRise: 40,
  /** Sheets whose feet are closer than this are one fall. */
  merge: 12,
  /** nature.pond's water_level: the pool's surface is this far below the fall's foot. */
  poolBelowFoot: 0.18,
  /** Grounded feet built at most (largest falls first). */
  maxFeet: 8,
  /** Feet drawing spray and mist at once (nearest the camera first). */
  slots: 4,
  /** Falls farther than this from the camera path (meta nearestM) get nothing. */
  maxPathDistance: 1500,
  spray: {
    /** Drops in the one instanced draw, shared by the feet in view. */
    count: { high: 250, mid: 160, low: 80 },
    /** Full within `near` of the camera, gone by `far`. */
    near: 140,
    far: 300,
    /** Cycle (s): the flight, then a pause until the drop is thrown again. */
    period: [1.4, 2.4],
    /** Launch ring around the foot (x width). */
    ring: [0.15, 0.45],
    /** Launch speed (x scale), elevation (degrees) and height over the pool (x scale). */
    speed: [3.0, 6.5],
    elevation: [35, 75],
    lift: [0.1, 0.8],
    /** Speed of a drop thrown back toward the cliff, as a share of a forward one. */
    back: 0.55,
    /** Azimuth spread around the pour direction (share of a full turn). */
    spread: 0.9,
    /** Horizontal air drag (1/s). */
    drag: 0.8,
    /** Drop radius (m). */
    size: [0.035, 0.09],
  },
  puffs: {
    /** Puffs per foot in view (instances are laid out `max` per foot). */
    count: { high: 10, mid: 8, low: 6 },
    max: 10,
    near: 380,
    far: 700,
    period: [4.5, 7.5],
    /** Peak opacity of one puff. */
    opacity: [0.15, 0.3],
    /** Birth ring (x width), rise (x scale) and outward roll (x scale). */
    ring: [0.1, 0.55],
    rise: [0.3, 0.8],
    roll: 0.35,
    /** Azimuth spread around the pour direction (share of a full turn). */
    spread: 0.8,
    /** Radius at birth (x width), and growth over a life (0.8: 1.8x at the end). */
    size: [0.3, 0.55],
    grow: 0.8,
    /** Share of the wind a puff drifts with. */
    wind: 0.3,
  },
  skirt: {
    near: 450,
    far: 800,
    /**
     * Outer radius (x width, plus the spread of the sheets' feet): past the bake's foam disc
     * (0.85 x width around the farthest sheet's foot), so its glowing rim is under the veil.
     */
    radius: 1.5,
    /**
     * The boil mound under the fall (x width, at most boilMax): a flat top out to boilIn of the
     * radius, meeting the pool at boilOut. Tall enough to cover the abode's baked foam disc and
     * splash blobs (nature.waterfall: blobs up to about 1.1 m within 0.45 x width).
     */
    boil: 0.2,
    boilMax: 1.6,
    boilIn: 0.22,
    boilOut: 0.6,
    /** Sits this far above the pool so it never flickers against the baked water. */
    lift: 0.04,
    segments: 48,
    rings: 10,
    /** Two foam layers drifting outward (m/s), and their texture tiles (m). */
    outward: [0.45, 0.8],
    tile: [2.6, 1.1],
  },
  /** Frames per side of the mist flipbook (public/sect/fx/mist_flipbook.webp, prep_textures.mjs). */
  flipbookGrid: 4,
  /** Horizontal wind (x, z): the petals' (fx.ts PETAL_WIND). */
  wind: [PETAL_WIND[0], PETAL_WIND[2]] as const,
  gravity: 9.81,
} as const;

/** How strongly a fall's effects scale with its size: 1 for a 6 m lip, within 0.6..2. */
export function fxScale(width: number): number {
  return Math.min(2, Math.max(0.6, width / 6));
}

/** Area ground for landsOnGround (meta.json "areas"). */
export type GroundArea = Pick<AreaMeta, "anchor" | "footprint">;

/**
 * True when a foot lies on an area's ground: within its footprint (plus `margin`) and near its
 * height. Island falls (scenery.py) are capped at 260 m, so some stop in mid-air over the cloud
 * sea; islands are kept at least 40 m clear of every area, so their feet never pass this.
 */
export function landsOnGround(foot: Vec3, areas: readonly GroundArea[], margin: number = WATERFALL_FX.groundMargin, rise: number = WATERFALL_FX.groundRise): boolean {
  for (const a of areas) {
    const d = Math.hypot(foot[0] - a.anchor[0], foot[2] - a.anchor[2]);
    if (d <= a.footprint + margin && Math.abs(foot[1] - a.anchor[1]) <= rise) return true;
  }
  return false;
}

/**
 * Falls that end on ground: sheets (not the feeder streams) whose foot is above the cloud tops
 * (`cloudTopY` + 5 m) and, when the meta has areas, on an area's ground. Without areas (older
 * meta files) every foot above the clouds counts, as before.
 */
export function groundedFalls<T extends { kind?: string; foot: Vec3 | null }>(falls: readonly T[], areas: readonly GroundArea[], cloudTopY: number): T[] {
  return falls.filter(
    (f) => f.foot !== null && (f.kind === undefined || f.kind === "sheet") && f.foot[1] >= cloudTopY + 5 && (areas.length === 0 || landsOnGround(f.foot, areas)),
  );
}

/** One fall's landing, with what its effects need. */
export interface FallFoot {
  /** The first sheet's name (for the debug probe). */
  name: string;
  /** Mean of the sheets' feet (world). */
  center: Vec3;
  /** The pool's surface under it (three y). */
  level: number;
  /** Unit horizontal direction the water pours (x, z): from the lips toward the feet. */
  pour: [number, number];
  /** atan2(pour z, pour x): the shaders' azimuth origin. */
  pourAngle: number;
  /** Widest lip of its sheets (m). */
  width: number;
  /** Lip to foot (m). */
  drop: number;
  /** Farthest sheet foot from `center`, horizontally (m). */
  spread: number;
  /** Chunk holding its pool (the effects draw only while that chunk does); null = global. */
  chunk: string | null;
  nearestM: number;
}

interface FootSheet {
  name: string;
  kind?: string;
  foot: Vec3 | null;
  corners: readonly [Vec3, Vec3, Vec3, Vec3] | null;
  nearestM: number;
  chunk?: string | null;
}

/**
 * The feet of the falls that land on ground (groundedFalls), one per fall: sheets of a fall share a
 * foot, so feet within `merge` metres in one chunk merge. Largest falls (width x drop) first, at
 * most `maxFeet`.
 */
export function fallFeet(
  falls: readonly FootSheet[],
  areas: readonly GroundArea[],
  cloudTopY: number,
  opts: { merge?: number; maxFeet?: number; maxPathDistance?: number } = {},
): FallFoot[] {
  const merge = opts.merge ?? WATERFALL_FX.merge;
  const maxFeet = opts.maxFeet ?? WATERFALL_FX.maxFeet;
  const maxPath = opts.maxPathDistance ?? WATERFALL_FX.maxPathDistance;
  const groups: { sheets: { foot: Vec3; corners: readonly [Vec3, Vec3, Vec3, Vec3]; name: string; nearestM: number }[]; chunk: string | null }[] = [];
  for (const f of groundedFalls(falls, areas, cloudTopY)) {
    if (!f.corners || !f.foot || f.nearestM > maxPath) continue;
    const chunk = f.chunk ?? null;
    const foot = f.foot;
    const g = groups.find((x) => x.chunk === chunk && x.sheets.some((s) => Math.hypot(s.foot[0] - foot[0], s.foot[1] - foot[1], s.foot[2] - foot[2]) < merge));
    const sheet = { foot, corners: f.corners, name: f.name, nearestM: f.nearestM };
    if (g) g.sheets.push(sheet);
    else groups.push({ sheets: [sheet], chunk });
  }
  const out: FallFoot[] = groups.map((g) => {
    const n = g.sheets.length;
    const center: Vec3 = [0, 0, 0];
    let px = 0;
    let pz = 0;
    let width = 0;
    let drop = 0;
    let nearestM = Infinity;
    for (const s of g.sheets) {
      for (let i = 0; i < 3; i++) center[i] += s.foot[i] / n;
      const c = s.corners;
      const lip: Vec3 = [(c[0][0] + c[1][0]) / 2, (c[0][1] + c[1][1]) / 2, (c[0][2] + c[1][2]) / 2];
      px += s.foot[0] - lip[0];
      pz += s.foot[2] - lip[2];
      width = Math.max(width, sheetExtent(c).width);
      drop = Math.max(drop, lip[1] - s.foot[1]);
      nearestM = Math.min(nearestM, s.nearestM);
    }
    let len = Math.hypot(px, pz);
    if (len < 0.2) {
      // Straight down: face away from the lip's line (either side reads the same for a vertical drop).
      const c = g.sheets[0].corners;
      px = -(c[1][2] - c[0][2]);
      pz = c[1][0] - c[0][0];
      len = Math.hypot(px, pz) || 1;
    }
    const pour: [number, number] = [px / len, pz / len];
    let spread = 0;
    for (const s of g.sheets) spread = Math.max(spread, Math.hypot(s.foot[0] - center[0], s.foot[2] - center[2]));
    return {
      name: g.sheets[0].name,
      center,
      level: center[1] - WATERFALL_FX.poolBelowFoot,
      pour,
      pourAngle: Math.atan2(pour[1], pour[0]),
      width,
      drop,
      spread,
      chunk: g.chunk,
      nearestM,
    };
  });
  out.sort((a, b) => b.width * b.drop - a.width * a.drop);
  return out.slice(0, maxFeet);
}

/** The effects' tier: no post pass = low, multisampled = high (lib/sect/life.ts lifeTier's rule). */
export function fxTier(q: { post: boolean; msaa: number }): "high" | "mid" | "low" {
  if (!q.post) return "low";
  return q.msaa > 0 ? "high" : "mid";
}

/** 1 within `near`, 0 from `far`, smooth between. */
export function distanceFade(d: number, near: number, far: number): number {
  const k = Math.min(1, Math.max(0, (d - near) / Math.max(far - near, 1e-6)));
  return 1 - k * k * (3 - 2 * k);
}

/**
 * Picks up to out.length feet with weight > 0, nearest first, into `out` (foot indices); returns
 * how many. No allocation (called every frame).
 */
export function pickFootSlots(weight: ArrayLike<number>, dist: ArrayLike<number>, out: Int32Array): number {
  let n = 0;
  if (out.length === 0) return 0;
  for (let i = 0; i < weight.length; i++) {
    if (!(weight[i] > 0)) continue;
    let j = n < out.length ? n++ : out.length;
    if (j === out.length && dist[i] >= dist[out[j - 1]]) continue;
    if (j === out.length) j--;
    while (j > 0 && dist[out[j - 1]] > dist[i]) {
      out[j] = out[j - 1];
      j--;
    }
    out[j] = i;
  }
  return n;
}

/**
 * The shared FX texture folder: `fx/` beside the asset set's folder (/sect/full -> /sect/fx), so
 * every set (full, before, proto) uses the same files.
 */
export function fxAssetUrl(base: string, file: string): string {
  const b = base.replace(/\/+$/, "");
  const i = b.lastIndexOf("/");
  return `${i >= 0 ? b.slice(0, i) : "."}/fx/${file}`;
}

// ---- foam skirt ------------------------------------------------------------------------------

/** Outer radius of a foot's foam skirt (m). */
export function skirtRadius(foot: Pick<FallFoot, "width" | "spread">): number {
  return WATERFALL_FX.skirt.radius * foot.width + foot.spread;
}

/** Height of the boil mound over the pool at distance r from the foot (m). */
export function skirtHeight(r: number, radius: number, width: number): number {
  const S = WATERFALL_FX.skirt;
  const boil = Math.min(S.boilMax, S.boil * width);
  const a = S.boilIn * radius;
  const b = S.boilOut * radius;
  const k = Math.min(1, Math.max(0, (r - a) / Math.max(b - a, 1e-6)));
  return boil * (1 - k * k * (3 - 2 * k));
}

/**
 * The feet's foam skirts as one mesh (world space): a polar grid per foot, rings packed toward the
 * centre, lying on the pool with the boil mound in the middle. uv = (turn around 0..1, share of
 * the radius 0..1); skirt = (radius in m, foot index, the mound's slope dh/dr, the fall's width).
 * Triangles face up.
 */
export function buildSkirts(
  feet: readonly FallFoot[],
  segments: number = WATERFALL_FX.skirt.segments,
  rings: number = WATERFALL_FX.skirt.rings,
): { positions: Float32Array; uv: Float32Array; skirt: Float32Array; index: Uint32Array } {
  const per = (segments + 1) * (rings + 1);
  const positions = new Float32Array(feet.length * per * 3);
  const uv = new Float32Array(feet.length * per * 2);
  const skirt = new Float32Array(feet.length * per * 4);
  const index = new Uint32Array(feet.length * segments * rings * 6);
  let v = 0;
  let t = 0;
  feet.forEach((f, k) => {
    const R = skirtRadius(f);
    const base = v;
    for (let i = 0; i <= rings; i++) {
      const s = Math.pow(i / rings, 1.25);
      const r = s * R;
      const y = f.level + WATERFALL_FX.skirt.lift + skirtHeight(r, R, f.width);
      const slope = (skirtHeight(r + 0.05, R, f.width) - skirtHeight(Math.max(r - 0.05, 0), R, f.width)) / (r + 0.05 - Math.max(r - 0.05, 0));
      for (let j = 0; j <= segments; j++) {
        const a = (j / segments) * Math.PI * 2;
        positions.set([f.center[0] + Math.cos(a) * r, y, f.center[2] + Math.sin(a) * r], v * 3);
        uv.set([j / segments, s], v * 2);
        skirt.set([R, k, slope, f.width], v * 4);
        v++;
      }
    }
    for (let i = 0; i < rings; i++) {
      for (let j = 0; j < segments; j++) {
        const a = base + i * (segments + 1) + j;
        const b = a + segments + 1;
        // Angle runs from +x toward +z; ring i+1 is outside ring i: (a, a+1, b+1) faces up.
        index.set([a, a + 1, b + 1, a, b + 1, b], t);
        t += 6;
      }
    }
  });
  return { positions, uv, skirt, index };
}

// ---- spray and mist puffs (mirrored by the shaders) -------------------------------------------

function fract(x: number): number {
  return x - Math.floor(x);
}

function mix(a: number, b: number, k: number): number {
  return a + (b - a) * k;
}

function smooth(a: number, b: number, x: number): number {
  const k = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return k * k * (3 - 2 * k);
}

/** 0..1 hash of a float, sine-free (after Dave Hoskins). Mirrors wfxHash in WFX_GLSL. */
export function wfxHash(p: number): number {
  let x = fract(p * 0.1031);
  x *= x + 33.33;
  x *= x + x;
  return fract(x);
}

/** A spray drop: offset from the foot's centre on the pool (m), velocity, and its fade (0 = not flying). */
export interface SprayDrop {
  p: Vec3;
  v: Vec3;
  fade: number;
}

/**
 * Where drop `seed` (four numbers in 0..1) is at time t: thrown from a ring around the foot on a
 * ballistic arc with horizontal drag, a new throw (direction, speed, height) every cycle, hidden
 * from the moment it falls back into the pool until the next throw. Mirrors wfxSpray (WFX_GLSL).
 */
export function sprayDrop(seed: readonly [number, number, number, number], t: number, width: number, pourAngle: number): SprayDrop {
  const S = WATERFALL_FX.spray;
  const g = WATERFALL_FX.gravity;
  const scale = fxScale(width);
  const period = mix(S.period[0], S.period[1], seed[0]);
  const c = t / period + seed[3];
  const k = Math.floor(c);
  const tau = (c - k) * period;
  const h1 = wfxHash(k * 1.731 + seed[1] * 97.31);
  const h2 = wfxHash(k * 2.417 + seed[2] * 57.13);
  const h3 = wfxHash(k * 3.119 + seed[0] * 41.77);
  const h4 = wfxHash(k * 4.271 + seed[3] * 23.53);
  const h5 = wfxHash(k * 5.003 + seed[1] * 13.37);
  const az = pourAngle + (h1 - 0.5) * Math.PI * 2 * S.spread;
  const fwd = 0.5 + 0.5 * Math.cos(az - pourAngle);
  const speed = mix(S.speed[0], S.speed[1], h3) * scale * mix(S.back, 1, fwd);
  const el = (mix(S.elevation[0], S.elevation[1], h4) * Math.PI) / 180;
  const vh = speed * Math.cos(el);
  const vy = speed * Math.sin(el);
  const y0 = mix(S.lift[0], S.lift[1], h5) * scale;
  const land = (vy + Math.sqrt(vy * vy + 2 * g * y0)) / g;
  const r0 = width * mix(S.ring[0], S.ring[1], h2);
  const e = Math.exp(-S.drag * tau);
  const d = (vh * (1 - e)) / S.drag;
  const dx = Math.cos(az);
  const dz = Math.sin(az);
  const fade = tau < land ? smooth(0, 0.06, tau) * (1 - smooth(0.75 * land, land, tau)) : 0;
  return {
    p: [dx * (r0 + d), y0 + vy * tau - 0.5 * g * tau * tau, dz * (r0 + d)],
    v: [dx * vh * e, vy - g * tau, dz * vh * e],
    fade,
  };
}

/** The farthest a drop can land from the foot's centre (m): the launch ring plus the longest throw. */
export function sprayReach(width: number): number {
  const S = WATERFALL_FX.spray;
  const g = WATERFALL_FX.gravity;
  const scale = fxScale(width);
  let best = 0;
  // Longest throw: full forward speed; scan the elevations and launch heights.
  for (let e = S.elevation[0]; e <= S.elevation[1]; e += 1) {
    for (const lift of S.lift) {
      const el = (e * Math.PI) / 180;
      const speed = S.speed[1] * scale;
      const vh = speed * Math.cos(el);
      const vy = speed * Math.sin(el);
      const y0 = lift * scale;
      const land = (vy + Math.sqrt(vy * vy + 2 * g * y0)) / g;
      best = Math.max(best, (vh * (1 - Math.exp(-S.drag * land))) / S.drag);
    }
  }
  return width * S.ring[1] + best;
}

/** A mist puff: centre offset from the foot's centre on the pool (m), radius, opacity, flipbook frame and layer. */
export interface MistPuff {
  p: Vec3;
  radius: number;
  alpha: number;
  /** Continuous frame, 0 .. frames - 1 (the shader blends the two around it). */
  frame: number;
  /** Flipbook channel: 0 = billow (R), 1 = torn wisps (G), 2 = second billow (B). */
  layer: number;
}

/**
 * Puff `seed` at time t: born on a ring around the foot, rising, rolling outward and drifting
 * with the wind while it grows; it fades in over the first fifth of its life and out over the last
 * half. Mirrors wfxPuff (WFX_GLSL).
 */
export function mistPuff(seed: readonly [number, number, number, number], t: number, width: number, pourAngle: number): MistPuff {
  const P = WATERFALL_FX.puffs;
  const scale = fxScale(width);
  const period = mix(P.period[0], P.period[1], seed[0]);
  const c = t / period + seed[3];
  const k = Math.floor(c);
  const age = c - k;
  const life = age * period;
  const h1 = wfxHash(k * 1.37 + seed[1] * 71.3);
  const h2 = wfxHash(k * 2.71 + seed[2] * 33.1);
  const az = pourAngle + (h1 - 0.5) * Math.PI * 2 * P.spread;
  const r = width * mix(P.ring[0], P.ring[1], h2) + P.roll * scale * life;
  const radius = width * mix(P.size[0], P.size[1], seed[2]) * (1 + P.grow * age);
  const y = radius * 0.45 + mix(P.rise[0], P.rise[1], seed[1]) * scale * life;
  const w = WATERFALL_FX.wind;
  const frames = WATERFALL_FX.flipbookGrid * WATERFALL_FX.flipbookGrid;
  return {
    p: [Math.cos(az) * r + w[0] * life * P.wind, y, Math.sin(az) * r + w[1] * life * P.wind],
    radius,
    alpha: mix(P.opacity[0], P.opacity[1], seed[1]) * smooth(0, 0.2, age) * (1 - smooth(0.5, 1, age)),
    frame: age * (frames - 1),
    layer: Math.min(2, Math.floor(seed[2] * 3)),
  };
}

const f = glslFloat;

/** GLSL mirrors of wfxHash, sprayDrop and mistPuff (vertex shaders of waterfall-fx.tsx). */
export const WFX_GLSL = /* glsl */ `
float wfxHash( float p ) {
  p = fract( p * 0.1031 );
  p *= p + 33.33;
  p *= p + p;
  return fract( p );
}
float wfxScale( float width ) { return clamp( width / 6.0, 0.6, 2.0 ); }
// water.ts sprayDrop: xyz = offset from the foot's centre on the pool, w = fade; vel = velocity.
vec4 wfxSpray( vec4 s, float t, float width, float pourAngle, out vec3 vel ) {
  float scale = wfxScale( width );
  float period = mix( ${f(WATERFALL_FX.spray.period[0])}, ${f(WATERFALL_FX.spray.period[1])}, s.x );
  float c = t / period + s.w;
  float k = floor( c );
  float tau = ( c - k ) * period;
  float h1 = wfxHash( k * 1.731 + s.y * 97.31 );
  float h2 = wfxHash( k * 2.417 + s.z * 57.13 );
  float h3 = wfxHash( k * 3.119 + s.x * 41.77 );
  float h4 = wfxHash( k * 4.271 + s.w * 23.53 );
  float h5 = wfxHash( k * 5.003 + s.y * 13.37 );
  float az = pourAngle + ( h1 - 0.5 ) * 6.2831853 * ${f(WATERFALL_FX.spray.spread)};
  float fwd = 0.5 + 0.5 * cos( az - pourAngle );
  float speed = mix( ${f(WATERFALL_FX.spray.speed[0])}, ${f(WATERFALL_FX.spray.speed[1])}, h3 ) * scale * mix( ${f(WATERFALL_FX.spray.back)}, 1.0, fwd );
  float el = radians( mix( ${f(WATERFALL_FX.spray.elevation[0])}, ${f(WATERFALL_FX.spray.elevation[1])}, h4 ) );
  float vh = speed * cos( el );
  float vy = speed * sin( el );
  float y0 = mix( ${f(WATERFALL_FX.spray.lift[0])}, ${f(WATERFALL_FX.spray.lift[1])}, h5 ) * scale;
  float g = ${f(WATERFALL_FX.gravity)};
  float land = ( vy + sqrt( vy * vy + 2.0 * g * y0 ) ) / g;
  float r0 = width * mix( ${f(WATERFALL_FX.spray.ring[0])}, ${f(WATERFALL_FX.spray.ring[1])}, h2 );
  float e = exp( - ${f(WATERFALL_FX.spray.drag)} * tau );
  float d = vh * ( 1.0 - e ) / ${f(WATERFALL_FX.spray.drag)};
  vec2 dir = vec2( cos( az ), sin( az ) );
  vel = vec3( dir.x * vh * e, vy - g * tau, dir.y * vh * e );
  float fade = tau < land ? smoothstep( 0.0, 0.06, tau ) * ( 1.0 - smoothstep( 0.75 * land, land, tau ) ) : 0.0;
  return vec4( dir.x * ( r0 + d ), y0 + vy * tau - 0.5 * g * tau * tau, dir.y * ( r0 + d ), fade );
}
// water.ts mistPuff: xyz = centre offset, w = radius; look = ( alpha, frame, layer ).
vec4 wfxPuff( vec4 s, float t, float width, float pourAngle, out vec3 look ) {
  float scale = wfxScale( width );
  float period = mix( ${f(WATERFALL_FX.puffs.period[0])}, ${f(WATERFALL_FX.puffs.period[1])}, s.x );
  float c = t / period + s.w;
  float k = floor( c );
  float age = c - k;
  float life = age * period;
  float h1 = wfxHash( k * 1.37 + s.y * 71.3 );
  float h2 = wfxHash( k * 2.71 + s.z * 33.1 );
  float az = pourAngle + ( h1 - 0.5 ) * 6.2831853 * ${f(WATERFALL_FX.puffs.spread)};
  float r = width * mix( ${f(WATERFALL_FX.puffs.ring[0])}, ${f(WATERFALL_FX.puffs.ring[1])}, h2 ) + ${f(WATERFALL_FX.puffs.roll)} * scale * life;
  float radius = width * mix( ${f(WATERFALL_FX.puffs.size[0])}, ${f(WATERFALL_FX.puffs.size[1])}, s.z ) * ( 1.0 + ${f(WATERFALL_FX.puffs.grow)} * age );
  float y = radius * 0.45 + mix( ${f(WATERFALL_FX.puffs.rise[0])}, ${f(WATERFALL_FX.puffs.rise[1])}, s.y ) * scale * life;
  vec2 wind = vec2( ${f(WATERFALL_FX.wind[0])}, ${f(WATERFALL_FX.wind[1])} ) * life * ${f(WATERFALL_FX.puffs.wind)};
  float alpha = mix( ${f(WATERFALL_FX.puffs.opacity[0])}, ${f(WATERFALL_FX.puffs.opacity[1])}, s.y ) * smoothstep( 0.0, 0.2, age ) * ( 1.0 - smoothstep( 0.5, 1.0, age ) );
  look = vec3( alpha, age * ${f(WATERFALL_FX.flipbookGrid * WATERFALL_FX.flipbookGrid - 1)}, min( 2.0, floor( s.z * 3.0 ) ) );
  return vec4( cos( az ) * r + wind.x, y, sin( az ) * r + wind.y, radius );
}
`;
