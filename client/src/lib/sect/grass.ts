/**
 * Grass tufts on /sect's baked lawns: where they grow, how many show at a distance, and how they
 * are packed for drawing (grass.tsx draws them).
 *
 * The lawns are a photo baked onto large, nearly level triangles, seen from 30 to 400 m. Single
 * blades are sub-pixel there; clumps of 7 blades 0.3-0.6 m tall are 5-25 px and give the lawn
 * height, outline and motion. The client scatters them over the ground-class triangles
 * (extras.detail = "ground") within the tier's reach of the flight (300 m on high), densest near
 * the flight path; far out a few large tufts give distant lawns and cap rims a tufted surface and a
 * soft outline instead of a painted lid.
 * Nothing is downloaded: every tuft takes its colour from the bake's atlas at its root, so it
 * carries the baked light and shadow. The roots are read once on the GPU when the area's textures
 * are up (ROOT): tufts on covered ground (paths, plazas, ground under ground, all of which baked
 * black) are dropped there, and tufts on soil thinned.
 *
 * Each candidate has a rank: the density (per m²) from which it shows. Candidates are uniform in
 * rank, so drawing every tuft with rank below d draws a uniform lawn of d tufts per m². Cells of
 * 32 m are sorted by rank, so a cell draws its first n instances; the vertex shader thins the rest
 * of the cell by each tuft's own distance (no steps: the last 10 % of a tuft's rank shrinks it).
 *
 * Pure data, maths and GLSL strings (no three.js import), so it is testable.
 */
import { DETAIL_LOOK, DETAIL_NOISE } from "./detail";
import { glslFloat } from "./glsl";
import { valueNoise } from "./noise";
import { tierQuality, type Quality } from "./runtime";

/**
 * Grass instances, 24 bytes each. `rank`: the density (per m², 0-255 = 0-10) at which the instance
 * first shows; `seed`: shape and colour hash; `size`: 0-255 = 0.25-2.5 m tall; `kind`: 0 tuft,
 * 1 fringe, 2 rim clump, 3 flower tuft. `leanAmount`: 0-255 = 0-75 degrees; `leanYaw`: 0-255 =
 * 0-2 pi (world, around +y). b[2] is the flower (FLOWER_COLORS index + 1) on a flower tuft, 0 on
 * everything else; b[3] is 1 on a tuft never within GRASS.farCell.fromM of the flight (it is drawn
 * from a larger cell), 0 on everything else (grass-edge.ts writes 0).
 */
export interface GrassInstances {
  count: number;
  /** World xyz, 3 per instance. */
  pos: Float32Array;
  /** Atlas UV at the root, normalised, 2 per instance. */
  uv: Uint16Array;
  /** 4 per instance: rank, seed, size, kind. */
  a: Uint8Array;
  /** 4 per instance: leanAmount, leanYaw, flower, far. */
  b: Uint8Array;
  /** Which ground atlas (index into the set's atlas list), 1 per instance. */
  atlas: Uint8Array;
}

/** World-space ground triangles: 9 position floats and 6 UV floats each, and an atlas per triangle. */
export interface GroundSoup {
  pos: Float32Array;
  uv: Float32Array;
  atlas: Uint8Array;
}

/** World-space rock triangles, 9 floats each. */
export interface RockSoup {
  pos: Float32Array;
}

export const KIND = { tuft: 0, fringe: 1, rim: 2, flower: 3 } as const;

/** One step of a rank byte, in tufts per m² (0-255 = 0-10). */
export const RANK_STEP = 10 / 255;

export interface GrassTier {
  /** Share of the ring densities drawn. */
  share: number;
  /** Camera distance (m) where tufts end (they shrink away over the last 10 %). */
  maxDist: number;
  /** Cells drawn at most, nearest first. */
  maxDraws: number;
  /** Tufts submitted at most per frame (all cells); densities scale down evenly beyond it. */
  maxTufts: number;
  /** Blades are widened to at least this many pixels. */
  minPx: number;
  /**
   * Share of maxDist from which tufts thin out and shrink to nothing at maxDist, so the grass has no
   * end line (mid ends at 110 m with 0.7 tufts per m² still there, so it fades over 44 m).
   */
  fadeFrom: number;
}

export const GRASS = {
  /**
   * By distance from the camera: tufts per m², and a size scale (fewer, larger tufts far away keep
   * the cover). Each value holds through its ring; between ring centres the curve is linear, so a
   * ring's average stays its value and the lawn has no visible density steps. The last two reach
   * the lawns the holds see at 150-300 m (all of 1208's, the mission cap from 516): 0.7-1.6 m tufts
   * there are 3-6 px, enough to break up the surface and the cap's outline.
   */
  rings: [
    { to: 25, density: 8, size: 1.0 },
    { to: 50, density: 6, size: 1.0 },
    { to: 90, density: 3, size: 1.3 },
    { to: 150, density: 1.5, size: 1.7 },
    { to: 210, density: 0.8, size: 2.2 },
    { to: 300, density: 0.4, size: 2.6 },
  ],
  tuft: {
    blades: 7,
    /** Height (m) at size 1, before the ring's size scale; short ones are commoner. */
    height: [0.3, 0.6] as const,
    /** Blade width (m) at the root (each blade stands for a few real ones). */
    width: 0.065,
    /** Radius (m) of the tuft's footprint at size 1. */
    spread: 0.18,
    /** Lean of the whole tuft (degrees). */
    lean: [5, 25] as const,
  },
  /** Flatter than 35 degrees (triangle normal y). */
  maxSlopeNy: 0.82,
  /**
   * Cell size (m). A cell draws what its nearest point needs, so the far side of a large cell is
   * submitted and thinned away in the shader: at 64 m about half the submitted tufts were.
   */
  cellM: 32,
  /**
   * Tufts that are never nearer than fromM to the flight (b[3] = 1) go in cells `scale` times as
   * large: they are few a square metre, and the high tier's 300 m reach would otherwise need about
   * twice the draws.
   */
  farCell: { fromM: 120, scale: 3 },
  /** Columns of the camera index (m). */
  camCellM: 20,
  /** Larger ground triangles are split (for the distance) into pieces of about this area (m²). */
  pieceM2: 16,
  /**
   * High reaches 300 m (the far rings): 0.15-0.25 ms a frame on an RTX 5080 at the holds. Mid
   * reaches the lawns most holds look at (50-110 m) at 40 % of the density, with wider blades (it
   * has no MSAA): about 0.05 ms there.
   */
  tiers: {
    high: { share: 1.0, maxDist: 300, maxDraws: 96, maxTufts: 60_000, minPx: 1.5, fadeFrom: 0.85 },
    mid: { share: 0.4, maxDist: 110, maxDraws: 28, maxTufts: 16_000, minPx: 2.0, fadeFrom: 0.6 },
  } as Record<"high" | "mid", GrassTier>,
  /**
   * Covered or unlit ground: every tap's brightest channel below this (linear; about 7/255 sRGB).
   * Paths, plazas, stairs and ground under ground baked to sRGB 1/255 (grass_place: 0.5 % of
   * covered points and 78 % of open ones pass a 3x3 test).
   */
  black: 0.0025,
  /**
   * Greenness of the root texel: (g - max(r, b)) / luminance, on the raw (ungraded) linear texel
   * (the grade tames green to max(r, b), so graded colours cannot tell grass from soil). Hue 40
   * degrees (brown soil) is about -0.45, hue 60 (olive) 0, a lawn 0.1-0.4. Soil keeps `soilKeep`
   * of its tufts, and they come out straw-coloured.
   */
  green: { lo: -0.45, hi: -0.05, soilKeep: 0.35 },
  colour: {
    /**
     * Blade root and tip brightness against the ground under it: lit tips over a shaded base are
     * what reads as grass from 30-150 m (at 0.78 / 1.22 the tufts melted into the lawn). Over a
     * blade's area the mean is about 0.94, so the lawn's brightness hardly moves.
     */
    root: 0.6,
    tip: 1.62,
    /** Each tuft's own brightness, +- this (clumps differ, as on a real lawn). */
    clump: 0.2,
    /** The tip is a little warmer. */
    tipWarm: [1.06, 1.0, 0.86] as const,
    /** Sun back light through the tips: pow(view . sun, power) * amount, gated by the root's light. */
    backPower: 6,
    backAmount: 0.35,
    /** Root luminance (graded) at which the back light is full. */
    backLit: 0.18,
    /** Camera distance (m) over which the blade gradient flattens to the plain root colour. */
    flatten: [90, 150] as const,
    /** Share of the root-to-tip shading kept past flatten[1]. */
    flattenKeep: 0.75,
    /** Linear straw colour the tips of tufts on soil turn toward. */
    straw: [0.42, 0.33, 0.16] as const,
  },
  /**
   * The gusts are the ground's own wind sheen (detail.ts DETAIL_LOOK.sheen: the ground noise's B
   * field, 16 m bands along (0.87, 0.49) drifting at 1.1 m/s), so tufts bow exactly where the
   * bright bands roll across the lawn under them.
   */
  wind: {
    /** Bend (radians) from calm to gust, downwind. */
    bend: [0.1, 0.35] as const,
    /** The sheen field's value from calm to full gust (it is ranked to uniform 0..1). */
    gust: [0.3, 0.85] as const,
    /** Each tuft's own bob: radians and Hz (hashed per tuft). */
    bob: 0.04,
    bobHz: [0.6, 1.1] as const,
    /** Gusts brighten the bent blades a little (the classic rolling waves). */
    gustLift: 0.06,
  },
  flowers: {
    /** Drift noise scale (m) and the noise band that is inside a drift. */
    driftM: 25,
    band: [0.6, 0.8] as const,
    /** Chance a tuft fully inside a drift carries flowers (about 3 % of all tufts overall). */
    inside: 0.25,
    /** One flower in this many is a glowing spirit herb. */
    spiritEvery: 250,
    /** Metres per flower-colour patch. */
    speciesM: 40,
    /** Camera distance (m) over which the flower heads shrink away (a spirit herb's x 4/3). */
    fadeM: [80, 120] as const,
  },
  /** Tufts closer than this to a stream or waterfall sheet are dropped (m). */
  sheetM: 1.5,
  /** A pond's water stands this far above its level (m) before ground counts as dry. */
  pondMargin: 0.02,
} as const;

/** Flower colours (sRGB): pale jade-white, peach blossom, wisteria, gold, then the spirit herb's cyan glow. */
export const FLOWER_COLORS = ["#efe8dc", "#e9b3c2", "#b6a3d9", "#e2bf5c", "#7ff0e6"] as const;

export type GrassTierName = "high" | "mid" | "off";

/**
 * Grass at a quality: off without postprocessing (the low tier), mid without MSAA (the mid tier:
 * thin blades shimmer without it), and mid too once the page has stepped down from its high
 * settings (resolution, MSAA, bloom or the frame cap).
 */
export function grassTier(q: Quality, devicePixelRatio = 1): GrassTierName {
  if (!q.post) return "off";
  if (q.msaa === 0) return "mid";
  const top = tierQuality("high", devicePixelRatio);
  if (q.msaa < top.msaa || q.maxDpr < top.maxDpr || !q.bloom || q.maxFps > 0) return "mid";
  return "high";
}

// ---------------------------------------------------------------------------------------------
// Density and size by distance

function clamp01(x: number): number {
  return Math.min(Math.max(x, 0), 1);
}

function smoothstep(a: number, b: number, x: number): number {
  const t = clamp01((x - a) / (b - a));
  return t * t * (3 - 2 * t);
}

/** Ring centres (m) and values, the control points of the density and size curves. */
function ringPoints(): { at: number; density: number; size: number }[] {
  let from = 0;
  return GRASS.rings.map((r) => {
    const p = { at: (from + r.to) / 2, density: r.density, size: r.size };
    from = r.to;
    return p;
  });
}

/** Ring density (per m²) and size scale at a camera distance; 0 density past the last ring. */
export function ringAt(d: number): { density: number; size: number } {
  const pts = ringPoints();
  const last = GRASS.rings[GRASS.rings.length - 1].to;
  let density = pts[0].density;
  let size = pts[0].size;
  for (let i = 1; i < pts.length; i++) {
    const t = clamp01((d - pts[i - 1].at) / (pts[i].at - pts[i - 1].at));
    density += (pts[i].density - density) * t;
    size += (pts[i].size - size) * t;
  }
  return { density: d < last ? density : 0, size };
}

/** Tufts per m² drawn at a camera distance on a tier, times the frame's budget scale. */
export function densityAt(d: number, tier: GrassTier, scale = 1): number {
  return d < tier.maxDist ? ringAt(d).density * tier.share * scale * heightFade(d, tier) : 0;
}

/** Near a tier's far end: 1, falling to 0 from fadeFrom x maxDist (both the density and the height). */
export function heightFade(d: number, tier: GrassTier): number {
  return 1 - smoothstep(tier.maxDist * tier.fadeFrom, tier.maxDist, d);
}

/** The rank a byte stands for (the middle of its step). */
export function rankOf(byte: number): number {
  return (byte + 0.5) * RANK_STEP;
}

export function rankByte(rank: number): number {
  return Math.min(255, Math.max(0, Math.floor(rank / RANK_STEP)));
}

export function sizeByte(m: number): number {
  return Math.min(255, Math.max(0, Math.round(((m - 0.25) / 2.25) * 255)));
}

export function sizeOf(byte: number): number {
  return 0.25 + (byte / 255) * 2.25;
}

export function leanByte(deg: number): number {
  return Math.min(255, Math.max(0, Math.round((deg / 75) * 255)));
}

export function yawByte(rad: number): number {
  const t = (((rad / (Math.PI * 2)) % 1) + 1) % 1;
  return Math.round(t * 256) % 256;
}

/** A rim clump's own draw distance (m): size x 300 m / 1.5 m, at most 450 m (grass-edge.ts). */
export function rimDrawDist(sizeM: number): number {
  return Math.min(450, (sizeM * 300) / 1.5);
}

/**
 * GLSL mirrors of ringAt (density without the tier, and size): `float sectGrassDensity( float d )`
 * and `float sectGrassSize( float d )`.
 */
export function grassRingGlsl(): string {
  const pts = ringPoints();
  const last = GRASS.rings[GRASS.rings.length - 1].to;
  const chain = (key: "density" | "size") =>
    pts
      .slice(1)
      .map((p, i) => {
        const a = pts[i].at;
        return `  k = mix( k, ${glslFloat(p[key])}, clamp( ( d - ${glslFloat(a)} ) / ${glslFloat(p.at - a)}, 0.0, 1.0 ) );`;
      })
      .join("\n");
  return /* glsl */ `
float sectGrassDensity( float d ) {
  float k = ${glslFloat(pts[0].density)};
${chain("density")}
  return d < ${glslFloat(last)} ? k : 0.0;
}
float sectGrassSize( float d ) {
  float k = ${glslFloat(pts[0].size)};
${chain("size")}
  return k;
}
`;
}

/**
 * GLSL: `float sectGrassGust( vec2 xz )`, 0 (calm) to 1 (full gust) at a world (x, z): the field
 * of the ground's wind sheen (detail.ts sectSheen), read from tSectGroundNoise at the top mip
 * level, so it works in a vertex shader. Needs `uniform float uTime` (seconds) and the
 * tSectGroundNoise declaration (detail.ts groundTintGlsl).
 */
export function grassWindGlsl(): string {
  const s = DETAIL_LOOK.sheen;
  const len = Math.hypot(s.wind[0], s.wind[1]);
  const wx = glslFloat(s.wind[0] / len);
  const wz = glslFloat(s.wind[1] / len);
  const inv = glslFloat(1 / (s.scaleM * DETAIL_NOISE.ground.cells));
  const g = GRASS.wind.gust;
  return /* glsl */ `
float sectGrassGust( vec2 xz ) {
  vec2 q = vec2( dot( xz, vec2( ${wx}, ${wz} ) ) - uTime * ${glslFloat(s.speed)}, dot( xz, vec2( -${wz}, ${wx} ) ) * ${glslFloat(1 / s.stretch)} );
  // The same offset as detail.ts sectSheen, so the bands line up.
  float n = textureLod( tSectGroundNoise, q * ${inv} + vec2( 0.53, 0.19 ), 0.0 ).b;
  return smoothstep( ${glslFloat(g[0])}, ${glslFloat(g[1])}, n );
}
const vec2 SECT_GRASS_WIND = vec2( ${wx}, ${wz} );
`;
}

// ---------------------------------------------------------------------------------------------
// Hashing (deterministic: the same lawn on every load)

function mix32(h: number): number {
  h ^= h >>> 16;
  h = Math.imul(h, 0x7feb352d);
  h ^= h >>> 15;
  h = Math.imul(h, 0x846ca68b);
  h ^= h >>> 16;
  return h >>> 0;
}

/** A key for a world position, quantised to 1/64 m (independent of mesh order). */
function posKey(x: number, y: number, z: number, seed: number): number {
  let h = mix32(Math.round(x * 64) ^ seed);
  h = mix32(h ^ Math.round(y * 64));
  return mix32(h ^ Math.round(z * 64));
}

/** Uniform in [0, 1) for a key and a counter. */
function rnd(key: number, n: number): number {
  return mix32((key + Math.imul(n + 1, 0x9e3779b1)) >>> 0) / 4294967296;
}

// ---------------------------------------------------------------------------------------------
// Camera index: nearest distance from a point to the flight's camera positions

export interface CamIndex {
  cellM: number;
  x0: number;
  z0: number;
  nx: number;
  nz: number;
  /** Points of column k are pts[start[k] .. start[k + 1]) (xyz each). */
  start: Int32Array;
  pts: Float32Array;
  /** Chebyshev distance (columns) from each column to the nearest column with points. */
  gap: Int32Array;
  count: number;
}

/** Columns of `cellM` metres in x and z over camera positions (xyz, flat). */
export function camIndex(points: ArrayLike<number>, cellM: number = GRASS.camCellM): CamIndex {
  const n = Math.floor(points.length / 3);
  let x0 = Infinity;
  let z0 = Infinity;
  let x1 = -Infinity;
  let z1 = -Infinity;
  for (let i = 0; i < n; i++) {
    x0 = Math.min(x0, points[i * 3]);
    x1 = Math.max(x1, points[i * 3]);
    z0 = Math.min(z0, points[i * 3 + 2]);
    z1 = Math.max(z1, points[i * 3 + 2]);
  }
  if (n === 0) return { cellM, x0: 0, z0: 0, nx: 0, nz: 0, start: new Int32Array(1), pts: new Float32Array(0), gap: new Int32Array(0), count: 0 };
  const nx = Math.floor((x1 - x0) / cellM) + 1;
  const nz = Math.floor((z1 - z0) / cellM) + 1;
  const col = new Int32Array(n);
  const start = new Int32Array(nx * nz + 1);
  for (let i = 0; i < n; i++) {
    const c = Math.floor((points[i * 3 + 2] - z0) / cellM) * nx + Math.floor((points[i * 3] - x0) / cellM);
    col[i] = c;
    start[c + 1]++;
  }
  for (let k = 0; k < nx * nz; k++) start[k + 1] += start[k];
  const fill = start.slice(0, nx * nz);
  const pts = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const o = fill[col[i]]++ * 3;
    pts[o] = points[i * 3];
    pts[o + 1] = points[i * 3 + 1];
    pts[o + 2] = points[i * 3 + 2];
  }
  // Chebyshev distance transform (two passes), so a search skips the empty rings around a point.
  const big = nx + nz + 2;
  const gap = new Int32Array(nx * nz);
  for (let k = 0; k < nx * nz; k++) gap[k] = start[k + 1] > start[k] ? 0 : big;
  for (let j = 0; j < nz; j++) {
    for (let i = 0; i < nx; i++) {
      let g = gap[j * nx + i];
      if (i > 0) g = Math.min(g, gap[j * nx + i - 1] + 1);
      if (j > 0) {
        g = Math.min(g, gap[(j - 1) * nx + i] + 1);
        if (i > 0) g = Math.min(g, gap[(j - 1) * nx + i - 1] + 1);
        if (i < nx - 1) g = Math.min(g, gap[(j - 1) * nx + i + 1] + 1);
      }
      gap[j * nx + i] = g;
    }
  }
  for (let j = nz - 1; j >= 0; j--) {
    for (let i = nx - 1; i >= 0; i--) {
      let g = gap[j * nx + i];
      if (i < nx - 1) g = Math.min(g, gap[j * nx + i + 1] + 1);
      if (j < nz - 1) {
        g = Math.min(g, gap[(j + 1) * nx + i] + 1);
        if (i < nx - 1) g = Math.min(g, gap[(j + 1) * nx + i + 1] + 1);
        if (i > 0) g = Math.min(g, gap[(j + 1) * nx + i - 1] + 1);
      }
      gap[j * nx + i] = g;
    }
  }
  return { cellM, x0, z0, nx, nz, start, pts, gap, count: n };
}

/** Distance from (x, y, z) to the nearest camera position, or Infinity when none is within maxR. */
export function nearestCam(ix: CamIndex, x: number, y: number, z: number, maxR: number): number {
  if (ix.count === 0) return Infinity;
  const c = ix.cellM;
  // Horizontally farther than maxR from every column: nothing to search.
  const dx = Math.max(ix.x0 - x, 0, x - (ix.x0 + ix.nx * c));
  const dz = Math.max(ix.z0 - z, 0, z - (ix.z0 + ix.nz * c));
  if (dx * dx + dz * dz > maxR * maxR) return Infinity;
  const ci = Math.floor((x - ix.x0) / c);
  const cj = Math.floor((z - ix.z0) / c);
  const inside = ci >= 0 && ci < ix.nx && cj >= 0 && cj < ix.nz;
  // Rings closer than the gap to the nearest occupied column are empty.
  const r0 = inside ? Math.max(ix.gap[cj * ix.nx + ci] - 0, 0) : 0;
  let best2 = maxR * maxR;
  let found = false;
  const rMax = Math.ceil(maxR / c) + 1;
  const scan = (i: number, j: number) => {
    if (i < 0 || j < 0 || i >= ix.nx || j >= ix.nz) return;
    const k = j * ix.nx + i;
    for (let p = ix.start[k]; p < ix.start[k + 1]; p++) {
      const ex = ix.pts[p * 3] - x;
      const ey = ix.pts[p * 3 + 1] - y;
      const ez = ix.pts[p * 3 + 2] - z;
      const d2 = ex * ex + ey * ey + ez * ez;
      if (d2 <= best2) {
        best2 = d2;
        found = true;
      }
    }
  };
  for (let r = r0; r <= rMax; r++) {
    const near = Math.max(0, (r - 1) * c);
    if (near * near > best2) break;
    if (r === 0) {
      scan(ci, cj);
      continue;
    }
    for (let i = ci - r; i <= ci + r; i++) {
      scan(i, cj - r);
      scan(i, cj + r);
    }
    for (let j = cj - r + 1; j <= cj + r - 1; j++) {
      scan(ci - r, j);
      scan(ci + r, j);
    }
  }
  return found ? Math.sqrt(best2) : Infinity;
}

// ---------------------------------------------------------------------------------------------
// Water: ponds (a level in a box) and stream / waterfall sheets (triangles)

export interface Pond {
  level: number;
  min: readonly [number, number, number];
  max: readonly [number, number, number];
}

/** Under a pond's water: inside its box (x, z) and below its level. */
export function underPond(ponds: readonly Pond[], x: number, y: number, z: number): boolean {
  for (const p of ponds) {
    if (x < p.min[0] || x > p.max[0] || z < p.min[2] || z > p.max[2]) continue;
    if (y < p.level + GRASS.pondMargin && y > p.min[1] - 1) return true;
  }
  return false;
}

export interface SheetIndex {
  cellM: number;
  tris: Float32Array;
  cells: Map<number, number[]>;
}

function cellId(i: number, j: number): number {
  return (i + 32768) * 65536 + (j + 32768);
}

/** Water sheet triangles (9 floats each) in columns, for nearSheet. */
export function sheetIndex(tris: Float32Array, cellM = 4): SheetIndex {
  const cells = new Map<number, number[]>();
  const r = GRASS.sheetM;
  for (let t = 0; t < tris.length / 9; t++) {
    let x0 = Infinity;
    let x1 = -Infinity;
    let z0 = Infinity;
    let z1 = -Infinity;
    for (let k = 0; k < 3; k++) {
      x0 = Math.min(x0, tris[t * 9 + k * 3]);
      x1 = Math.max(x1, tris[t * 9 + k * 3]);
      z0 = Math.min(z0, tris[t * 9 + k * 3 + 2]);
      z1 = Math.max(z1, tris[t * 9 + k * 3 + 2]);
    }
    for (let i = Math.floor((x0 - r) / cellM); i <= Math.floor((x1 + r) / cellM); i++) {
      for (let j = Math.floor((z0 - r) / cellM); j <= Math.floor((z1 + r) / cellM); j++) {
        const id = cellId(i, j);
        const list = cells.get(id);
        if (list) list.push(t);
        else cells.set(id, [t]);
      }
    }
  }
  return { cellM, tris, cells };
}

/** Squared distance from p to triangle t (closest point, after Ericson). */
function triDist2(T: Float32Array, t: number, px: number, py: number, pz: number): number {
  const o = t * 9;
  const ax = T[o], ay = T[o + 1], az = T[o + 2];
  const abx = T[o + 3] - ax, aby = T[o + 4] - ay, abz = T[o + 5] - az;
  const acx = T[o + 6] - ax, acy = T[o + 7] - ay, acz = T[o + 8] - az;
  const apx = px - ax, apy = py - ay, apz = pz - az;
  const d1 = abx * apx + aby * apy + abz * apz;
  const d2 = acx * apx + acy * apy + acz * apz;
  let qx: number, qy: number, qz: number;
  if (d1 <= 0 && d2 <= 0) {
    qx = ax;
    qy = ay;
    qz = az;
  } else {
    const bpx = px - T[o + 3], bpy = py - T[o + 4], bpz = pz - T[o + 5];
    const d3 = abx * bpx + aby * bpy + abz * bpz;
    const d4 = acx * bpx + acy * bpy + acz * bpz;
    const cpx = px - T[o + 6], cpy = py - T[o + 7], cpz = pz - T[o + 8];
    const d5 = abx * cpx + aby * cpy + abz * cpz;
    const d6 = acx * cpx + acy * cpy + acz * cpz;
    const vc = d1 * d4 - d3 * d2;
    const vb = d5 * d2 - d1 * d6;
    const va = d3 * d6 - d5 * d4;
    if (d3 >= 0 && d4 <= d3) {
      qx = T[o + 3];
      qy = T[o + 4];
      qz = T[o + 5];
    } else if (d6 >= 0 && d5 <= d6) {
      qx = T[o + 6];
      qy = T[o + 7];
      qz = T[o + 8];
    } else if (vc <= 0 && d1 >= 0 && d3 <= 0) {
      const v = d1 / (d1 - d3);
      qx = ax + abx * v;
      qy = ay + aby * v;
      qz = az + abz * v;
    } else if (vb <= 0 && d2 >= 0 && d6 <= 0) {
      const w = d2 / (d2 - d6);
      qx = ax + acx * w;
      qy = ay + acy * w;
      qz = az + acz * w;
    } else if (va <= 0 && d4 - d3 >= 0 && d5 - d6 >= 0) {
      const w = (d4 - d3) / (d4 - d3 + (d5 - d6));
      qx = T[o + 3] + (T[o + 6] - T[o + 3]) * w;
      qy = T[o + 4] + (T[o + 7] - T[o + 4]) * w;
      qz = T[o + 5] + (T[o + 8] - T[o + 5]) * w;
    } else {
      const den = 1 / (va + vb + vc);
      const v = vb * den;
      const w = vc * den;
      qx = ax + abx * v + acx * w;
      qy = ay + aby * v + acy * w;
      qz = az + abz * v + acz * w;
    }
  }
  return (px - qx) ** 2 + (py - qy) ** 2 + (pz - qz) ** 2;
}

/** Within GRASS.sheetM of a stream or waterfall sheet. */
export function nearSheet(ix: SheetIndex | null, x: number, y: number, z: number): boolean {
  if (!ix) return false;
  const list = ix.cells.get(cellId(Math.floor(x / ix.cellM), Math.floor(z / ix.cellM)));
  if (!list) return false;
  const r2 = GRASS.sheetM * GRASS.sheetM;
  for (const t of list) if (triDist2(ix.tris, t, x, y, z) < r2) return true;
  return false;
}

// ---------------------------------------------------------------------------------------------
// Flowers

/** The flower (1-4 a colour of FLOWER_COLORS, 5 a spirit herb) a tuft at (x, z) carries, or 0. */
export function flowerAt(x: number, z: number, u: number, seed = 0): number {
  const F = GRASS.flowers;
  // A broad drift with a ragged edge (two octaves), so flowers come in patches, not as confetti.
  const n = 0.65 * valueNoise(x / F.driftM, z / F.driftM, 65536, 31 + seed) + 0.35 * valueNoise(x / 9, z / 9, 65536, 37 + seed);
  const p = smoothstep(F.band[0], F.band[1], n) * F.inside;
  if (u >= p) return 0;
  // Each patch is mostly one colour; one flower in spiritEvery is a spirit herb.
  if (Math.floor((u / p) * F.spiritEvery) === 0) return 5;
  const cx = Math.floor(x / F.speciesM);
  const cz = Math.floor(z / F.speciesM);
  const main = mix32(cellId(cx, cz) ^ (seed * 977)) % 4;
  const other = (u / p) * 7.3 - Math.floor((u / p) * 7.3) < 0.2 ? (main + 1 + (mix32(cellId(cz, cx)) % 3)) % 4 : main;
  return other + 1;
}

// ---------------------------------------------------------------------------------------------
// Scatter

export interface ScatterOptions {
  tier: GrassTier;
  ponds?: readonly Pond[];
  sheets?: SheetIndex | null;
  /** Varies the whole lawn (tests); 0 on the page. */
  seed?: number;
}

/** Growable instance arrays. */
class InstanceWriter {
  count = 0;
  pos = new Float32Array(3 * 1024);
  uv = new Uint16Array(2 * 1024);
  a = new Uint8Array(4 * 1024);
  b = new Uint8Array(4 * 1024);
  atlas = new Uint8Array(1024);

  private grow(): void {
    const cap = this.atlas.length * 2;
    const g = <T extends Float32Array | Uint16Array | Uint8Array>(src: T, per: number): T => {
      const out = new (src.constructor as new (n: number) => T)(cap * per);
      out.set(src);
      return out;
    };
    this.pos = g(this.pos, 3);
    this.uv = g(this.uv, 2);
    this.a = g(this.a, 4);
    this.b = g(this.b, 4);
    this.atlas = g(this.atlas, 1);
  }

  push(x: number, y: number, z: number, u: number, v: number, a: readonly number[], b: readonly number[], atlas: number): void {
    if (this.count === this.atlas.length) this.grow();
    const i = this.count++;
    this.pos[i * 3] = x;
    this.pos[i * 3 + 1] = y;
    this.pos[i * 3 + 2] = z;
    this.uv[i * 2] = Math.round(clamp01(u) * 65535);
    this.uv[i * 2 + 1] = Math.round(clamp01(v) * 65535);
    for (let k = 0; k < 4; k++) {
      this.a[i * 4 + k] = a[k];
      this.b[i * 4 + k] = b[k];
    }
    this.atlas[i] = atlas;
  }

  done(): GrassInstances {
    const n = this.count;
    return { count: n, pos: this.pos.slice(0, n * 3), uv: this.uv.slice(0, n * 2), a: this.a.slice(0, n * 4), b: this.b.slice(0, n * 4), atlas: this.atlas.slice(0, n) };
  }
}

export function emptyInstances(): GrassInstances {
  return { count: 0, pos: new Float32Array(0), uv: new Uint16Array(0), a: new Uint8Array(0), b: new Uint8Array(0), atlas: new Uint8Array(0) };
}

/**
 * Tufts on the ground soup, as a generator that yields (the triangles done so far) every few
 * hundred triangles, so the page can spread the work over frames. Kept: triangles at least as flat
 * as maxSlopeNy whose pieces come within the tier's maxDist of a camera position. Each piece gets
 * the ring density at its nearest camera distance (times the tier's share); points are placed
 * uniformly with hashed randoms (the same on every load), with a rank uniform in [0, density).
 * Points under a pond or beside a water sheet are dropped. About 3 % of tufts carry flowers, in
 * drifts.
 */
export function* scatterSteps(soup: GroundSoup, cams: CamIndex, opts: ScatterOptions): Generator<number, GrassInstances> {
  const { tier } = opts;
  const seed = opts.seed ?? 0;
  const ponds = opts.ponds ?? [];
  const P = soup.pos;
  const UV = soup.uv;
  const T = GRASS.tuft;
  const out = new InstanceWriter();
  const tris = Math.floor(P.length / 9);
  const a = [0, 0, 0, 0];
  const b = [0, 0, 0, 0];
  // Work since the last yield: a distance query counts 4, a point 1.
  let work = 0;
  for (let t = 0; t < tris; t++) {
    if (work > 1024) {
      work = 0;
      yield t;
    }
    // The quick distance test below costs about as much as a piece's.
    work += 4;
    const o = t * 9;
    const ax = P[o], ay = P[o + 1], az = P[o + 2];
    const ux = P[o + 3] - ax, uy = P[o + 4] - ay, uz = P[o + 5] - az;
    const vx = P[o + 6] - ax, vy = P[o + 7] - ay, vz = P[o + 8] - az;
    const nx = uy * vz - uz * vy;
    const ny = uz * vx - ux * vz;
    const nz = ux * vy - uy * vx;
    const len = Math.hypot(nx, ny, nz);
    if (len < 1e-8 || ny / len < GRASS.maxSlopeNy) continue;
    const area = len / 2;
    // Quick reject: the whole triangle is out of reach.
    const cx = ax + (ux + vx) / 3;
    const cy = ay + (uy + vy) / 3;
    const cz = az + (uz + vz) / 3;
    const rad = Math.sqrt(Math.max((ax - cx) ** 2 + (ay - cy) ** 2 + (az - cz) ** 2, (P[o + 3] - cx) ** 2 + (P[o + 4] - cy) ** 2 + (P[o + 5] - cz) ** 2, (P[o + 6] - cx) ** 2 + (P[o + 7] - cy) ** 2 + (P[o + 8] - cz) ** 2));
    if (nearestCam(cams, cx, cy, cz, tier.maxDist + rad) === Infinity) continue;
    const key = posKey(cx, cy, cz, seed);
    // Large triangles are split into pieces on a barycentric grid, each with its own distance.
    const k = Math.max(1, Math.ceil(Math.sqrt(area / GRASS.pieceM2)));
    const pieceArea = area / (k * k);
    let piece = 0;
    for (let i = 0; i < k; i++) {
      for (let j = 0; j < k - i; j++) {
        for (let flip = 0; flip < (j < k - i - 1 ? 2 : 1); flip++, piece++) {
          // Piece corners in the parent's barycentric (s along u, r along v).
          const s0 = flip ? (i + 1) / k : i / k;
          const r0 = flip ? (j + 1) / k : j / k;
          const s1 = flip ? i / k : (i + 1) / k;
          const r1 = flip ? (j + 1) / k : j / k;
          const s2 = flip ? (i + 1) / k : i / k;
          const r2 = flip ? j / k : (j + 1) / k;
          const ps = (s0 + s1 + s2) / 3;
          const pr = (r0 + r1 + r2) / 3;
          const d = k === 1 ? nearestCam(cams, cx, cy, cz, tier.maxDist) : nearestCam(cams, ax + ux * ps + vx * pr, ay + uy * ps + vy * pr, az + uz * ps + vz * pr, tier.maxDist);
          const dens = densityAt(d, tier);
          work += 4;
          // A large triangle is many pieces: yield inside it too.
          if (work > 1024) {
            work = 0;
            yield t;
          }
          if (dens <= 0) continue;
          const pkey = mix32(key + piece * 0x632be5ab);
          const n = Math.floor(pieceArea * dens + rnd(pkey, 0));
          work += n;
          for (let q = 0; q < n; q++) {
            // A uniform point in the piece (folded square), then into the parent.
            let e1 = rnd(pkey, q * 8 + 1);
            let e2 = rnd(pkey, q * 8 + 2);
            if (e1 + e2 > 1) {
              e1 = 1 - e1;
              e2 = 1 - e2;
            }
            const s = s0 + (s1 - s0) * e1 + (s2 - s0) * e2;
            const r = r0 + (r1 - r0) * e1 + (r2 - r0) * e2;
            const x = ax + ux * s + vx * r;
            const y = ay + uy * s + vy * r;
            const z = az + uz * s + vz * r;
            if (underPond(ponds, x, y, z) || nearSheet(opts.sheets ?? null, x, y, z)) continue;
            const w0 = 1 - s - r;
            const tu = UV[t * 6] * w0 + UV[t * 6 + 2] * s + UV[t * 6 + 4] * r;
            const tv = UV[t * 6 + 1] * w0 + UV[t * 6 + 3] * s + UV[t * 6 + 5] * r;
            const flower = flowerAt(x, z, rnd(pkey, q * 8 + 3), seed);
            const h = T.height[0] + (T.height[1] - T.height[0]) * Math.pow(rnd(pkey, q * 8 + 4), 1.4);
            a[0] = rankByte(rnd(pkey, q * 8 + 5) * dens);
            a[1] = Math.floor(rnd(pkey, q * 8 + 6) * 256);
            a[2] = sizeByte(h);
            a[3] = flower ? KIND.flower : KIND.tuft;
            b[0] = leanByte(T.lean[0] + (T.lean[1] - T.lean[0]) * rnd(pkey, q * 8 + 7));
            b[1] = Math.floor(rnd(pkey, q * 8 + 8) * 256);
            b[2] = flower;
            b[3] = d >= GRASS.farCell.fromM ? 1 : 0;
            out.push(x, y, z, tu, tv, a, b, soup.atlas[t]);
          }
        }
      }
    }
  }
  return out.done();
}

/** scatterSteps run to the end. */
export function scatterGround(soup: GroundSoup, cams: CamIndex, opts: ScatterOptions): GrassInstances {
  return runSteps(scatterSteps(soup, cams, opts));
}

/** A step generator (the page spreads them over frames) run to the end at once. */
export function runSteps<T>(it: Generator<unknown, T>): T {
  for (;;) {
    const r = it.next();
    if (r.done) return r.value;
  }
}

/** Several instance sets as one (the scatter, then the edge fringe and rim clumps). */
export function mergeInstances(list: readonly GrassInstances[]): GrassInstances {
  const n = list.reduce((s, l) => s + l.count, 0);
  const out: GrassInstances = { count: n, pos: new Float32Array(n * 3), uv: new Uint16Array(n * 2), a: new Uint8Array(n * 4), b: new Uint8Array(n * 4), atlas: new Uint8Array(n) };
  let o = 0;
  for (const l of list) {
    out.pos.set(l.pos.subarray(0, l.count * 3), o * 3);
    out.uv.set(l.uv.subarray(0, l.count * 2), o * 2);
    out.a.set(l.a.subarray(0, l.count * 4), o * 4);
    out.b.set(l.b.subarray(0, l.count * 4), o * 4);
    out.atlas.set(l.atlas.subarray(0, l.count), o);
    o += l.count;
  }
  return out;
}

// ---------------------------------------------------------------------------------------------
// The bake at the roots

/**
 * Each instance's root is read from its atlas once, on the GPU, when its area's textures are up
 * (grass.tsx renders one point per instance into an RGBA8 target and reads it back). The texel
 * goes out as sqrt(linear) in RGB (finer steps in the shadows than linear) and in A either 0
 * (covered: one of three taps, 1.5 texels either side, was black) or `alpha0` + greenness x
 * (255 - alpha0). The per-frame shader then needs no atlas at all, and covered roots are never
 * drawn. A root darker than `pocket` times the brightest of its taps (two more, `far` texels out
 * along the other diagonal) sits in a pocket the bake left nearly black: the dim rim around a path,
 * or the ground under a stepping stone. It is dropped too, or it would stand as a black speck
 * poking through the stone (on the atlases this costs 0.6 % of open roots). One darker than `lift`
 * times that brightness (the bake's contact shadow along a path or a wall) is lifted to it: the
 * blades stand up out of that shadow, and their tips over the path's edge would read as dark specks.
 */
export const ROOT = { alpha0: 64, tap: 1.5, far: 4, pocket: 0.3, lift: 0.6 } as const;

/** Greenness (0 soil .. 1 lawn) of a linear root texel. */
export function rootGreen(r: number, g: number, b: number): number {
  const l = Math.max(0.2126 * r + 0.7152 * g + 0.0722 * b, 1e-4);
  return smoothstep(GRASS.green.lo, GRASS.green.hi, (g - Math.max(r, b)) / l);
}

/**
 * TypeScript mirror of the GPU read: the RGBA8 bytes for a root whose taps (linear RGB) are `c0`
 * (the root), `c1` and `c2` (ROOT.tap texels either side) and `c3`, `c4` (ROOT.far texels out).
 */
export function rootTexel(
  c0: readonly number[],
  c1: readonly number[],
  c2: readonly number[],
  c3: readonly number[] = c0,
  c4: readonly number[] = c0,
): [number, number, number, number] {
  const m0 = Math.max(...c0);
  const lit = Math.min(m0, Math.max(...c1), Math.max(...c2));
  const ref = Math.max(...c1, ...c2, ...c3, ...c4);
  const k = Math.max(1, (ROOT.lift * ref) / Math.max(m0, 1e-4));
  const enc = (v: number) => Math.round(Math.sqrt(clamp01(v * k)) * 255);
  const a = lit < GRASS.black || m0 < ROOT.pocket * ref ? 0 : Math.round(ROOT.alpha0 + rootGreen(c0[0], c0[1], c0[2]) * (255 - ROOT.alpha0));
  return [enc(c0[0]), enc(c0[1]), enc(c0[2]), a];
}

/**
 * GLSL of the GPU read (fragment shader body helpers): `vec4 sectGrassRoot( sampler2D map, vec2 uv )`,
 * the RGBA (0-1) rootTexel writes for the root at uv. textureLod at the top level, so the bake's
 * own texel is read wherever the point lands.
 */
export function grassRootGlsl(): string {
  const G = GRASS.green;
  return /* glsl */ `
float sectGrassMax( vec3 c ) {
  return max( c.r, max( c.g, c.b ) );
}
vec4 sectGrassRoot( sampler2D map, vec2 uv ) {
  vec2 px = 1.0 / vec2( textureSize( map, 0 ) );
  vec2 ts = ${glslFloat(ROOT.tap)} * px;
  vec2 tf = ${glslFloat(ROOT.far)} * vec2( px.x, - px.y );
  vec3 c0 = textureLod( map, uv, 0.0 ).rgb;
  float m0 = sectGrassMax( c0 );
  float m1 = sectGrassMax( textureLod( map, uv + ts, 0.0 ).rgb );
  float m2 = sectGrassMax( textureLod( map, uv - ts, 0.0 ).rgb );
  float lit = min( m0, min( m1, m2 ) );
  // Far darker than the ground around it: a pocket the bake left nearly black (a path's dim rim,
  // the ground under a stepping stone).
  float ref = max( max( m1, m2 ), max( sectGrassMax( textureLod( map, uv + tf, 0.0 ).rgb ), sectGrassMax( textureLod( map, uv - tf, 0.0 ).rgb ) ) );
  bool pocket = m0 < ${glslFloat(ROOT.pocket)} * ref;
  float l = max( dot( c0, vec3( 0.2126, 0.7152, 0.0722 ) ), 1e-4 );
  float green = smoothstep( ${glslFloat(G.lo)}, ${glslFloat(G.hi)}, ( c0.g - max( c0.r, c0.b ) ) / l );
  float a = lit < ${glslFloat(GRASS.black)} || pocket ? 0.0 : ( ${glslFloat(ROOT.alpha0)} + green * ${glslFloat(255 - ROOT.alpha0)} ) / 255.0;
  // Out of a contact shadow (a path's or a wall's foot), lifted toward the ground around it.
  float k = max( 1.0, ${glslFloat(ROOT.lift)} * ref / max( m0, 1e-4 ) );
  return vec4( sqrt( clamp( c0 * k, 0.0, 1.0 ) ), a );
}
`;
}

/** Instances with their root read: world position, root texel (rootTexel bytes), a and b as in GrassInstances. */
export interface RootedGrass {
  count: number;
  pos: Float32Array;
  col: Uint8Array;
  a: Uint8Array;
  b: Uint8Array;
}

/**
 * Keeps the instances whose root is open ground, with their texel. A tuft (or flower tuft) on soil
 * keeps soilKeep of its chance: its rank is divided by its keep share (rank < density x keep is
 * rank / keep < density), and one that could never show at the densest ring goes. The fringe and
 * the rim clumps keep their rank 0.
 */
export function rootInstances(inst: GrassInstances, texels: Uint8Array): RootedGrass {
  return runSteps(rootSteps(inst, texels));
}

/** rootInstances as a generator that yields every few thousand instances. */
export function* rootSteps(inst: GrassInstances, texels: Uint8Array): Generator<void, RootedGrass> {
  const keepMax = GRASS.rings[0].density;
  const idx = new Int32Array(inst.count);
  const ranks = new Uint8Array(inst.count);
  let n = 0;
  for (let i = 0; i < inst.count; i++) {
    if ((i & 16383) === 16383) yield;
    const a = texels[i * 4 + 3];
    if (a < ROOT.alpha0 / 2) continue;
    const kind = inst.a[i * 4 + 3];
    let rank = inst.a[i * 4];
    if (kind === KIND.tuft || kind === KIND.flower) {
      const green = (a - ROOT.alpha0) / (255 - ROOT.alpha0);
      const keep = GRASS.green.soilKeep + (1 - GRASS.green.soilKeep) * clamp01(green);
      const r = rankOf(rank) / keep;
      if (r >= keepMax) continue;
      rank = rankByte(r);
    }
    idx[n] = i;
    ranks[n] = rank;
    n++;
  }
  const out: RootedGrass = { count: n, pos: new Float32Array(n * 3), col: new Uint8Array(n * 4), a: new Uint8Array(n * 4), b: new Uint8Array(n * 4) };
  for (let o = 0; o < n; o++) {
    if ((o & 16383) === 16383) yield;
    const i = idx[o];
    for (let k = 0; k < 3; k++) out.pos[o * 3 + k] = inst.pos[i * 3 + k];
    for (let k = 0; k < 4; k++) {
      out.col[o * 4 + k] = texels[i * 4 + k];
      out.a[o * 4 + k] = inst.a[i * 4 + k];
      out.b[o * 4 + k] = inst.b[i * 4 + k];
    }
    out.a[o * 4] = ranks[o];
  }
  return out;
}

// ---------------------------------------------------------------------------------------------
// Cells

/**
 * One draw: the instances in one cell (cellM metres square). Layer 0 holds tufts, fringe and
 * flowers, sorted by rank (`below[k]` = how many have a rank byte below k); layer 1 holds rim
 * clumps, sorted by their own draw distance, farthest first (`reach`).
 */
export interface GrassCell {
  layer: 0 | 1;
  count: number;
  /** Box around the roots, grown by the tallest instance at its largest. */
  min: [number, number, number];
  max: [number, number, number];
  center: [number, number, number];
  radius: number;
  below: Uint32Array | null;
  reach: Float32Array | null;
  pos: Float32Array;
  col: Uint8Array;
  a: Uint8Array;
  b: Uint8Array;
}

/** Splits instances into cells by layer and column, each sorted for drawing. */
export function buildCells(inst: RootedGrass, cellM: number = GRASS.cellM): GrassCell[] {
  return runSteps(cellSteps(inst, cellM));
}

/** buildCells as a generator that yields every few thousand instances. */
export function* cellSteps(inst: RootedGrass, cellM: number = GRASS.cellM): Generator<void, GrassCell[]> {
  const groups = new Map<number, number[]>();
  let work = 0;
  const farM = cellM * GRASS.farCell.scale;
  for (let i = 0; i < inst.count; i++) {
    if ((i & 16383) === 16383) yield;
    const layer = inst.a[i * 4 + 3] === KIND.rim ? 1 : 0;
    // Key: column, then 0 near tufts (and the fringe), 1 rim clumps, 2 far tufts (larger columns).
    const far = layer === 0 && inst.b[i * 4 + 3] === 1;
    const m = far ? farM : cellM;
    const key = cellId(Math.floor(inst.pos[i * 3] / m), Math.floor(inst.pos[i * 3 + 2] / m)) * 3 + (far ? 2 : layer);
    const list = groups.get(key);
    if (list) list.push(i);
    else groups.set(key, [i]);
  }
  const cells: GrassCell[] = [];
  for (const [key, list] of groups) {
    work += list.length;
    if (work > 16384) {
      work = 0;
      yield;
    }
    const layer = (key % 3 === 1 ? 1 : 0) as 0 | 1;
    let order: number[];
    let below: Uint32Array | null = null;
    let reach: Float32Array | null = null;
    if (layer === 0) {
      // Counting sort by rank byte (stable, so the order is the input's within a rank).
      below = new Uint32Array(257);
      for (const i of list) below[inst.a[i * 4] + 1]++;
      for (let k = 0; k < 256; k++) below[k + 1] += below[k];
      const fill = below.slice(0, 256);
      order = new Array<number>(list.length);
      for (const i of list) order[fill[inst.a[i * 4]]++] = i;
    } else {
      order = [...list].sort((p, q) => inst.a[q * 4 + 2] - inst.a[p * 4 + 2] || p - q);
      reach = Float32Array.from(order, (i) => rimDrawDist(sizeOf(inst.a[i * 4 + 2])));
    }
    const n = order.length;
    const pos = new Float32Array(n * 3);
    const col = new Uint8Array(n * 4);
    const a = new Uint8Array(n * 4);
    const b = new Uint8Array(n * 4);
    const min: [number, number, number] = [Infinity, Infinity, Infinity];
    const max: [number, number, number] = [-Infinity, -Infinity, -Infinity];
    let tallest = 0;
    order.forEach((i, o) => {
      for (let k = 0; k < 3; k++) {
        const v = inst.pos[i * 3 + k];
        pos[o * 3 + k] = v;
        min[k] = Math.min(min[k], v);
        max[k] = Math.max(max[k], v);
      }
      for (let k = 0; k < 4; k++) {
        col[o * 4 + k] = inst.col[i * 4 + k];
        a[o * 4 + k] = inst.a[i * 4 + k];
        b[o * 4 + k] = inst.b[i * 4 + k];
      }
      tallest = Math.max(tallest, sizeOf(inst.a[i * 4 + 2]));
    });
    // The largest size scale, a lean and the widest footprint: nothing of an instance leaves the box.
    const pad = tallest * GRASS.rings[GRASS.rings.length - 1].size + GRASS.tuft.spread * 4;
    for (let k = 0; k < 3; k++) {
      min[k] -= pad;
      max[k] += pad;
    }
    const center: [number, number, number] = [(min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2];
    const radius = Math.hypot(max[0] - center[0], max[1] - center[1], max[2] - center[2]);
    cells.push({ layer, count: n, min, max, center, radius, below, reach, pos, col, a, b });
  }
  return cells;
}

/** Distance from a point to a cell's box (0 inside). */
export function cellDistance(cell: GrassCell, x: number, y: number, z: number): number {
  const dx = Math.max(cell.min[0] - x, 0, x - cell.max[0]);
  const dy = Math.max(cell.min[1] - y, 0, y - cell.max[1]);
  const dz = Math.max(cell.min[2] - z, 0, z - cell.max[2]);
  return Math.hypot(dx, dy, dz);
}

/**
 * Instances a cell draws when its nearest point is `dist` from the camera: tufts whose rank is
 * below the density there (times the budget scale), or rim clumps that reach that far.
 */
export function cellCount(cell: GrassCell, dist: number, tier: GrassTier, scale = 1): number {
  if (cell.reach) {
    let lo = 0;
    let hi = cell.count;
    while (lo < hi) {
      const m = (lo + hi) >> 1;
      if (cell.reach[m] > dist) lo = m + 1;
      else hi = m;
    }
    return lo;
  }
  const d = densityAt(dist, tier, scale);
  if (d <= 0 || !cell.below) return 0;
  // rankOf(byte) < d  <=>  byte < d / RANK_STEP - 0.5.
  const k = Math.min(256, Math.max(0, Math.ceil(d / RANK_STEP - 0.5)));
  return cell.below[k];
}

/**
 * The scale on every density that keeps the tufts drawn within the tier's budget (1 when they fit).
 * Rim clumps do not scale (they are few).
 */
export function fitBudget(cells: readonly GrassCell[], dists: readonly number[], tier: GrassTier): number {
  let scale = 1;
  for (let it = 0; it < 4; it++) {
    let total = 0;
    cells.forEach((c, i) => {
      total += cellCount(c, dists[i], tier, scale);
    });
    if (total <= tier.maxTufts) return scale;
    scale *= (tier.maxTufts / total) * 0.98;
  }
  return scale;
}
