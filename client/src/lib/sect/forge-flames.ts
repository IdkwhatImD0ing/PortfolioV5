/**
 * Live flames in the Artifact Forge Peak's fires: the furnace mouths in the forge hall, the fire
 * boxes in the two kiln towers' vent storeys and the ding cauldron's molten top. The bake holds
 * them as flat glowing boxes and a flat disc ("molten" glow); the page draws moving fire in them.
 *
 * Where the fires are comes from one of two places:
 * - meta.fires (FireAnchor, written by export_web.py from forge.py's fire anchors), once a bake has
 *   them: exact openings, beds and heights;
 * - until then, the bake's own ".glow.molten" geometry (fireSourcesFromGlow): its meshes are split
 *   into connected pieces (meshPieces) and each piece is read by its shape. A thin
 *   upright plate is a furnace mouth (an opening facing the area's centre), a flat disc is a
 *   cauldron's surface, and a block is a kiln's fire box.
 *
 * Three kinds of drawing (forge-flames.tsx):
 * - an opening is drawn as a fire box seen through it: a quad on the mouth whose shader traces the
 *   view ray into a box behind it (walls, a glowing coal bed, two sheets of flame at different
 *   depths), so the fire sits inside the furnace and shifts with the view;
 * - a bed carries upright camera-facing flame cards (turning about the vertical only): one wide
 *   fire in front of a kiln's box, several tongues spread over a cauldron's surface;
 * - embers rise from the openings and the kilns (the cauldron's sparks are fx.tsx ForgeFire's).
 *
 * Every fire flickers on fireFlicker (mirrored by FLICKER_GLSL), and so does the bake's molten glow
 * under it, in step. Pure: plain arrays, no three.js.
 */
import { glslFloat } from "./glsl";
import type { FireAnchor, Vec3 } from "./types";

export type { FireAnchor };

const f = glslFloat;

// ---- the look ----------------------------------------------------------------------------------

export const FLAMES = {
  /** Most fires one draw holds (the shaders' uniform arrays). */
  maxSources: 8,
  /** Pieces smaller than this across (m) are not fires (seams, rivets). */
  minSize: 0.4,
  /** Flames fade out between these distances from the camera (m); the haze dims them before. */
  fade: [520, 760] as [number, number],
  /** Flicker of the bake's molten glow, as a share of the flames' own (1 = as strong). */
  glowFlicker: 0.6,
  /**
   * The bake's molten glow under kiln and furnace flames, while they are drawn: a kiln's box burned
   * near white and washed its flames out (a furnace's plate is covered by its fire box anyway). A
   * cauldron's molten surface keeps its glow.
   */
  boxGlow: 0.4,
  /** A cauldron's molten surface under its flames (molten metal is dimmer than the flames over it). */
  poolGlow: 0.6,
  /** fx.tsx ForgeFire's soft glow over the cauldron while its flames are drawn (they carry the light). */
  cauldronGlow: 0.35,
  /**
   * How much of what is behind a flame card its dense body hides (0 = purely added light): over the
   * bright molten metal or a glowing box, added light alone washed the flames out to a pale pink.
   */
  cover: 0.6,
  /** How deep a furnace's fire box reads behind its mouth, per its larger side (m/m), and the bounds. */
  boxDepth: { perSize: 0.55, min: 0.6, max: 2.2 },
  /** The quad stands this far in front of the mouth's glowing plate (m). */
  mouthLift: 0.025,
  /** A kiln's flames reach this far above its fire box, per its height, and the bounds (m). */
  kilnRise: { perHeight: 0.72, min: 0.6, max: 1.4 },
  /** A cauldron's flames, per its radius (m/m), and the bounds (m). */
  cauldronHeight: { perRadius: 1.25, min: 1.2, max: 4.5 },
  /** Soft fade (m) where a flame card meets what is behind it (High and Medium). */
  soft: 0.35,
  /**
   * Colours along the heat ramp (linear: fire has almost no blue, so these encode to a deep red, an
   * orange, a yellow and a pale yellow).
   */
  ramp: {
    ember: [1.0, 0.07, 0.005] as Vec3,
    orange: [1.0, 0.2, 0.012] as Vec3,
    yellow: [1.0, 0.5, 0.05] as Vec3,
    white: [1.0, 0.78, 0.32] as Vec3,
  },
  /** Brightness at full heat (linear, times heat squared; bloom starts at 1). */
  brightness: 1.8,
  /** How fast the flame's noise climbs (texture units a second: the bend, the coarse and the fine turbulence). */
  rise: { bend: 0.25, coarse: 0.2, fine: 0.6 },
  /** Reduced motion: how calm the frozen flames are (0 = as alive, 1 = a smooth glow). */
  calm: 0.6,
  /** Reduced motion: the moment the frozen flames show (s). */
  stillTime: 7.25,
} as const;

/** The page's fx tier (water.ts fxTier). */
export type FlameTierName = "high" | "mid" | "low";

export interface FlameTier {
  /** Flame cards over a cauldron's surface. */
  cauldronCards: number;
  /** Flame cards in front of a kiln's fire box. */
  kilnCards: number;
  /** Flame sheets inside a furnace's box (1 or 2). */
  sheets: 1 | 2;
  /** Embers per furnace mouth and per kiln. */
  mouthEmbers: number;
  kilnEmbers: number;
}

/** High full; Medium fewer embers; Low (and so most phones) fewer cards, one sheet, few embers. */
export function flameTier(tier: FlameTierName): FlameTier {
  if (tier === "low") return { cauldronCards: 3, kilnCards: 1, sheets: 1, mouthEmbers: 6, kilnEmbers: 8 };
  if (tier === "mid") return { cauldronCards: 5, kilnCards: 2, sheets: 2, mouthEmbers: 12, kilnEmbers: 16 };
  return { cauldronCards: 6, kilnCards: 2, sheets: 2, mouthEmbers: 18, kilnEmbers: 24 };
}

// ---- fires -------------------------------------------------------------------------------------

/** A fire seen through an opening (a furnace mouth). */
export interface OpeningFire {
  kind: "opening";
  id: string;
  /** Centre of the opening's bottom edge, on its outer face (three.js world, m). */
  base: Vec3;
  /** Outward facing (horizontal unit vector). */
  normal: Vec3;
  /** Across the opening, to the right as seen from outside: up x normal (horizontal unit). */
  right: Vec3;
  width: number;
  height: number;
  /** How deep the fire box behind it reads (m). */
  depth: number;
  /** Flicker phase (fireFlicker). */
  phase: number;
}

/** Flames standing on a bed: a kiln's fire box or a cauldron's molten surface. */
export interface BedFire {
  kind: "bed";
  id: string;
  /** "kiln": one wide fire in front of a glowing box; "cauldron": tongues spread over a surface. */
  style: "kiln" | "cauldron";
  /** Centre of the fire's foot (m). */
  base: Vec3;
  /** Half the bed's width (m). */
  radius: number;
  /** How tall the flames stand above the foot (m). */
  height: number;
  /** The cards stand this far toward the camera (in front of a glowing box; m). */
  pull: number;
  phase: number;
}

export type FireSource = OpeningFire | BedFire;

/** Flicker phase of a fire at p (as fx.tsx fireMaterial's vPhase: 0 at the origin). */
export function firePhase(p: Vec3): number {
  return p[0] * 0.37 + p[1] * 0.11 + p[2] * 0.53;
}

/**
 * A fire's brightness at time t (s): about 0.69-1.01, mean 0.85 (fx.tsx ForgeFire's glow flicker,
 * so a fire at phase 0 flickers with the cauldron's glow). Mirrored by FLICKER_GLSL.
 */
export function fireFlicker(t: number, phase: number): number {
  return 0.85 + 0.1 * Math.sin(t * 7.3 + phase) + 0.06 * Math.sin(t * 13.1 + 1.7 + phase * 2.3);
}

export const FLICKER_GLSL = /* glsl */ `
float sectFireFlicker( float t, float phase ) {
  return 0.85 + 0.1 * sin( t * 7.3 + phase ) + 0.06 * sin( t * 13.1 + 1.7 + phase * 2.3 );
}
`;

/**
 * The molten glow's colour factor under fires whose fireFlicker values average `meanFlicker`: about
 * 1 on average, swinging with them at `share` of their strength.
 */
export function glowFactor(meanFlicker: number, share: number = FLAMES.glowFlicker): number {
  return 1 + share * (meanFlicker / 0.85 - 1);
}

function horizontalUnit(v: Vec3): Vec3 | null {
  const l = Math.hypot(v[0], v[2]);
  return l > 1e-6 ? [v[0] / l, 0, v[2] / l] : null;
}

/** up x n for a horizontal unit n: the right-hand side as seen looking at the opening from outside. */
function rightOf(n: Vec3): Vec3 {
  return [n[2], 0, -n[0]];
}

function clamp(x: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, x));
}

function boxDepth(width: number, height: number): number {
  const d = FLAMES.boxDepth;
  return clamp(d.perSize * Math.max(width, height), d.min, d.max);
}

function kilnHeight(boxH: number): number {
  const r = FLAMES.kilnRise;
  return boxH + clamp(r.perHeight * boxH, r.min, r.max);
}

function cauldronHeight(radius: number): number {
  const c = FLAMES.cauldronHeight;
  return clamp(c.perRadius * radius, c.min, c.max);
}

/** meta.fires kinds (lower case): a fire seen through an opening, a fire box, a fire over a surface. */
const OPENING_KINDS = new Set(["furnace", "mouth", "opening", "hearth"]);
const KILN_KINDS = new Set(["kiln", "chimney", "tower", "vent", "firebox"]);
const POOL_KINDS = new Set(["cauldron", "ding", "pool", "brazier", "bed"]);

/** The fires of a chunk from meta.fires (at most FLAMES.maxSources, in file order). */
export function fireSourcesFromAnchors(anchors: readonly FireAnchor[], chunk: string): FireSource[] {
  const out: FireSource[] = [];
  for (const a of anchors) {
    if (out.length >= FLAMES.maxSources) break;
    if ((a.chunk ?? a.area) !== chunk) continue;
    const kind = a.kind.toLowerCase();
    if (OPENING_KINDS.has(kind)) {
      const n = a.normal ? horizontalUnit(a.normal) : null;
      if (!n || !(a.width > 0) || !(a.height > 0)) continue;
      out.push({
        kind: "opening",
        id: a.id,
        base: a.position,
        normal: n,
        right: rightOf(n),
        width: a.width,
        height: a.height,
        depth: a.depth > 0 ? a.depth : boxDepth(a.width, a.height),
        phase: firePhase(a.position),
      });
    } else if (KILN_KINDS.has(kind) || POOL_KINDS.has(kind)) {
      const radius = a.radius > 0 ? a.radius : a.width / 2;
      if (!(radius > 0)) continue;
      const style = KILN_KINDS.has(kind) ? "kiln" : "cauldron";
      out.push({
        kind: "bed",
        id: a.id,
        style,
        base: a.position,
        radius,
        height: a.height > 0 ? a.height : style === "kiln" ? kilnHeight(radius * 1.4) : cauldronHeight(radius),
        // In front of a kiln's square box (its half-diagonal); a cauldron's tongues stand on its surface.
        pull: style === "kiln" ? radius * Math.SQRT2 + 0.05 : 0,
        phase: firePhase(a.position),
      });
    }
  }
  return out;
}

/** A piece of glow read by its shape: its extents along its long and short horizontal axes, and up. */
export interface GlowShape {
  center: Vec3;
  minY: number;
  maxY: number;
  /** Unit horizontal axes: `long` along the larger horizontal extent, `short` across it. */
  long: Vec3;
  short: Vec3;
  extentLong: number;
  extentShort: number;
  extentY: number;
}

/**
 * The shape of a set of points (xyz triples): the tightest rectangle round their horizontal spread
 * (searched in 1 degree steps; the forge's pieces stand upright and the area turns only about the
 * vertical), its axes and extents, centred on the middle of those extents. Null without points.
 */
export function glowShape(points: ArrayLike<number>): GlowShape | null {
  const n = Math.floor(points.length / 3);
  if (n === 0) return null;
  let minY = Infinity;
  let maxY = -Infinity;
  for (let i = 0; i < n; i++) {
    const y = points[i * 3 + 1];
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  }
  let best = { area: Infinity, theta: 0, a0: 0, a1: 0, b0: 0, b1: 0 };
  for (let deg = 0; deg < 90; deg++) {
    const theta = (deg * Math.PI) / 180;
    const c = Math.cos(theta);
    const sn = Math.sin(theta);
    let a0 = Infinity;
    let a1 = -Infinity;
    let b0 = Infinity;
    let b1 = -Infinity;
    for (let i = 0; i < n; i++) {
      const x = points[i * 3];
      const z = points[i * 3 + 2];
      const pa = x * c + z * sn;
      const pb = -x * sn + z * c;
      if (pa < a0) a0 = pa;
      if (pa > a1) a1 = pa;
      if (pb < b0) b0 = pb;
      if (pb > b1) b1 = pb;
    }
    // Area, plus a little perimeter so a flat plate (no area) still turns to its tightest fit.
    const area = (a1 - a0) * (b1 - b0) + 1e-3 * (a1 - a0 + b1 - b0);
    if (area < best.area - 1e-9) best = { area, theta, a0, a1, b0, b1 };
  }
  const { theta, a0, a1, b0, b1 } = best;
  const a: Vec3 = [Math.cos(theta), 0, Math.sin(theta)];
  const b: Vec3 = [-Math.sin(theta), 0, Math.cos(theta)];
  const ea = a1 - a0;
  const eb = b1 - b0;
  const ca = (a0 + a1) / 2;
  const cb = (b0 + b1) / 2;
  const center: Vec3 = [a[0] * ca + b[0] * cb, (minY + maxY) / 2, a[2] * ca + b[2] * cb];
  const swap = eb > ea;
  return {
    center,
    minY,
    maxY,
    long: swap ? b : a,
    short: swap ? a : b,
    extentLong: swap ? eb : ea,
    extentShort: swap ? ea : eb,
    extentY: maxY - minY,
  };
}

/**
 * What a piece of molten glow is, by its shape (null: not a fire):
 * - flat and wide (its height a fifth of its width or less): a cauldron's surface;
 * - thin and upright (its depth under a quarter of its width): a furnace mouth, an opening facing
 *   `toward` (the area's centre; the mouth's glowing plate stands on the furnace's front);
 * - otherwise a kiln's fire box, burning in front of it.
 */
export function classifyGlow(s: GlowShape, id: string, toward: Vec3 | null): FireSource | null {
  if (s.extentLong < FLAMES.minSize) return null;
  if (s.extentY <= Math.max(0.12, 0.2 * s.extentLong) && s.extentShort > 0.5 * s.extentLong) {
    const radius = (s.extentLong + s.extentShort) / 4;
    const base: Vec3 = [s.center[0], s.center[1], s.center[2]];
    return { kind: "bed", id, style: "cauldron", base, radius, height: cauldronHeight(radius), pull: 0, phase: firePhase(base) };
  }
  if (s.extentShort < 0.25 * s.extentLong && s.extentShort < 0.5 && s.extentY >= 0.3) {
    let n: Vec3 = s.short;
    if (toward) {
      const d = (toward[0] - s.center[0]) * n[0] + (toward[2] - s.center[2]) * n[2];
      if (d < 0) n = [-n[0], 0, -n[2]];
    }
    const half = s.extentShort / 2;
    const base: Vec3 = [s.center[0] + n[0] * half, s.minY, s.center[2] + n[2] * half];
    return {
      kind: "opening",
      id,
      base,
      normal: n,
      right: rightOf(n),
      width: s.extentLong,
      height: s.extentY,
      depth: boxDepth(s.extentLong, s.extentY),
      phase: firePhase(base),
    };
  }
  const radius = s.extentLong / 2;
  const base: Vec3 = [s.center[0], s.minY + 0.1 * s.extentY, s.center[2]];
  return {
    kind: "bed",
    id,
    style: "kiln",
    base,
    radius,
    // From a tenth of the way up the box to a little under what covers it.
    height: kilnHeight(s.extentY) - 0.1 * s.extentY,
    pull: Math.hypot(s.extentLong, s.extentShort) / 2 + 0.05,
    phase: firePhase(base),
  };
}

/**
 * The connected pieces of a mesh (positions: xyz triples; index: its triangles, or null for a plain
 * list of triangles): vertices joined by a triangle or standing at the same spot (to the millimetre;
 * a flat-shaded box repeats its corners per face) belong to one piece. Returns each piece's points.
 */
export function meshPieces(positions: ArrayLike<number>, index: ArrayLike<number> | null): number[][] {
  const n = Math.floor(positions.length / 3);
  if (n === 0) return [];
  const parent = new Int32Array(n);
  for (let i = 0; i < n; i++) parent[i] = i;
  const find = (i: number): number => {
    while (parent[i] !== i) {
      parent[i] = parent[parent[i]];
      i = parent[i];
    }
    return i;
  };
  const join = (a: number, b: number) => {
    const ra = find(a);
    const rb = find(b);
    if (ra !== rb) parent[Math.max(ra, rb)] = Math.min(ra, rb);
  };
  const same = new Map<string, number>();
  for (let i = 0; i < n; i++) {
    const key = `${Math.round(positions[i * 3] * 1000)},${Math.round(positions[i * 3 + 1] * 1000)},${Math.round(positions[i * 3 + 2] * 1000)}`;
    const j = same.get(key);
    if (j === undefined) same.set(key, i);
    else join(i, j);
  }
  const tris = index ? Math.floor(index.length / 3) : Math.floor(n / 3);
  for (let t = 0; t < tris; t++) {
    const a = index ? index[t * 3] : t * 3;
    const b = index ? index[t * 3 + 1] : t * 3 + 1;
    const c = index ? index[t * 3 + 2] : t * 3 + 2;
    if (a >= n || b >= n || c >= n) continue;
    join(a, b);
    join(b, c);
  }
  const groups = new Map<number, number[]>();
  for (let i = 0; i < n; i++) {
    const r = find(i);
    let g = groups.get(r);
    if (!g) {
      g = [];
      groups.set(r, g);
    }
    g.push(positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]);
  }
  return [...groups.values()];
}

/**
 * The fires in a chunk's molten glow, from its pieces (meshPieces, world xyz triples), each read by
 * classifyGlow. Openings face `toward` (the area's anchor). Sorted by x, then z, then y of their
 * centres (stable across loads); at most FLAMES.maxSources.
 */
export function fireSourcesFromGlow(pieces: readonly ArrayLike<number>[], toward: Vec3 | null, prefix = "glow"): FireSource[] {
  const shapes = pieces.map(glowShape).filter((s): s is GlowShape => s !== null);
  shapes.sort((a, b) => a.center[0] - b.center[0] || a.center[2] - b.center[2] || a.center[1] - b.center[1]);
  const out: FireSource[] = [];
  shapes.forEach((s, k) => {
    if (out.length >= FLAMES.maxSources) return;
    const src = classifyGlow(s, `${prefix}.${k}`, toward);
    if (src) out.push(src);
  });
  return out;
}

/** A sphere around everything a fire draws (flames, embers), for the view test. */
export function fireBounds(s: FireSource): { center: Vec3; radius: number } {
  if (s.kind === "opening") {
    const h = s.height * 0.5 + 1.2;
    return { center: [s.base[0], s.base[1] + h, s.base[2]], radius: Math.hypot(s.width * 0.5, h) + s.depth + 1.5 };
  }
  const rise = s.style === "kiln" ? 7 : s.height;
  return { center: [s.base[0], s.base[1] + rise * 0.5, s.base[2]], radius: Math.hypot(s.radius + s.pull + 2, rise * 0.5) };
}

// ---- instance tables ---------------------------------------------------------------------------

/**
 * Floats per flame card: base xyz, width | height, seed, source index, pull (toward the camera) |
 * shift (sideways along the card, m), heat (brightness scale), phase, lean (the tip's sideways
 * shift as a share of the width).
 */
export const CARD_STRIDE = 12;

function hash(i: number, salt: number): number {
  const s = Math.sin(i * 127.1 + salt * 311.7) * 43758.5453;
  return s - Math.floor(s);
}

/**
 * The flame cards over the beds (instanced quads, forge-flames.tsx): a kiln's are wide fires in
 * front of its box; a cauldron's are a tall one in the middle and shorter ones round it (golden
 * angle, so any count spreads evenly). A card's source index is the source's place in `sources`.
 */
export function flameCards(sources: readonly FireSource[], tier: FlameTier): Float32Array {
  const rows: number[] = [];
  sources.forEach((s, si) => {
    if (s.kind !== "bed") return;
    if (s.style === "kiln") {
      for (let k = 0; k < tier.kilnCards; k++) {
        // The second card is narrower, a little to one side, out of step.
        const shift = k === 0 ? 0 : (hash(si, k) - 0.5) * s.radius * 0.8;
        rows.push(s.base[0], s.base[1], s.base[2], s.radius * (k === 0 ? 2.3 : 1.6));
        rows.push(s.height * (k === 0 ? 1 : 0.82), si * 7.13 + k * 3.71, si, s.pull + k * 0.02);
        rows.push(shift, k === 0 ? 1 : 0.8, s.phase + k * 1.9, 0);
      }
      return;
    }
    for (let k = 0; k < tier.cauldronCards; k++) {
      const a = k * 2.399963 + s.phase;
      const r = k === 0 ? 0 : s.radius * (0.3 + 0.32 * hash(si, k));
      const x = s.base[0] + Math.cos(a) * r;
      const z = s.base[2] + Math.sin(a) * r;
      const w = s.radius * (k === 0 ? 1.0 : 0.6 + 0.2 * hash(si, k + 11));
      const h = s.height * (k === 0 ? 1 : 0.55 + 0.3 * hash(si, k + 23));
      rows.push(x, s.base[1], z, w);
      rows.push(h, si * 7.13 + k * 3.71, si, 0);
      // Hot enough to read as yellow fire over the bright molten metal; outer tongues lean a little
      // (the tip's sideways shift, as a share of the width).
      rows.push(0, k === 0 ? 1.25 : 1.12 + 0.1 * hash(si, k + 41), s.phase + k * 1.3, k === 0 ? 0 : (hash(si, k + 31) - 0.5) * 0.5);
    }
  });
  return new Float32Array(rows);
}

/** Floats per ember: source index, seed a, seed b, seed c. */
export const EMBER_STRIDE = 4;

/** Embers for the openings and kilns (the cauldron's sparks are ForgeFire's), at the tier's counts. */
export function emberSeeds(sources: readonly FireSource[], tier: FlameTier): Float32Array {
  const rows: number[] = [];
  sources.forEach((s, si) => {
    const count = s.kind === "opening" ? tier.mouthEmbers : s.style === "kiln" ? tier.kilnEmbers : 0;
    for (let k = 0; k < count; k++) rows.push(si, hash(si * 97 + k, 1), hash(si * 97 + k, 2), (k + hash(si * 97 + k, 3)) / count);
  });
  return new Float32Array(rows);
}

/** Floats per opening quad vertex: world xyz, local x, local y, then the source index. */
export const MOUTH_STRIDE = 6;

/**
 * One quad per opening (two triangles, non-indexed), FLAMES.mouthLift in front of the face:
 * world position, local (x across from the centre, y up from the bottom; m), source index.
 */
export function openingQuads(sources: readonly FireSource[]): Float32Array {
  const rows: number[] = [];
  sources.forEach((s, si) => {
    if (s.kind !== "opening") return;
    const corner = (u: number, v: number) => {
      const x = (u - 0.5) * s.width;
      const y = v * s.height;
      rows.push(
        s.base[0] + s.right[0] * x + s.normal[0] * FLAMES.mouthLift,
        s.base[1] + y,
        s.base[2] + s.right[2] * x + s.normal[2] * FLAMES.mouthLift,
        x,
        y,
        si,
      );
    };
    corner(0, 0);
    corner(1, 0);
    corner(1, 1);
    corner(0, 0);
    corner(1, 1);
    corner(0, 1);
  });
  return new Float32Array(rows);
}

// ---- shaders -----------------------------------------------------------------------------------

const R = FLAMES.ramp;
const v3 = (c: Vec3) => `vec3( ${f(c[0])}, ${f(c[1])}, ${f(c[2])} )`;

/**
 * Flame heat and colour, shared by the flame cards and the furnace boxes. Needs `tFlameNoise` (the
 * shared tiling noise, materials.ts getNoiseTexture) and FLICKER_GLSL.
 *
 * sectFlameHeat: uv.x across (-1..1 over the flame's foot), uv.y up (0 foot, 1 tip); `wall` 1 for a
 * sheet of fire (no teardrop sides; the caller fades its ends). Above 0 it shows; 1 is the hot core.
 */
export const FLAME_GLSL = /* glsl */ `
uniform sampler2D tFlameNoise;
float sectFlameHeat( vec2 uv, float t, float seed, float calm, float wall ) {
  float y = clamp( uv.y, 0.0, 1.0 );
  // A slow distortion bends the whole flame, more toward the tip.
  float d = ( texture2D( tFlameNoise, vec2( uv.x * 0.25 + seed * 0.31, uv.y * 0.2 + seed * 0.53 - t * ${f(FLAMES.rise.bend)} ) ).r - 0.5 ) * ( 1.0 - calm );
  float x = uv.x + d * 0.9 * ( 0.25 + y );
  float qy = uv.y + d * 0.15;
  // Rising turbulence: the tiling noise stretched upward at two scales, the fine one climbing faster,
  // so the fire tears into tongues that lick up and break off.
  float n1 = texture2D( tFlameNoise, vec2( x * 0.45 + seed * 0.173, qy * 0.14 + seed * 0.291 - t * ${f(FLAMES.rise.coarse)} ) ).r;
  float n2 = texture2D( tFlameNoise, vec2( x * 1.08 + seed * 0.419, qy * 0.294 + seed * 0.137 - t * ${f(FLAMES.rise.fine)} ) ).r;
  float n = smoothstep( 0.25, 0.75, mix( n1 * 0.55 + n2 * 0.45, 0.5, calm ) );
  n2 = smoothstep( 0.2, 0.8, mix( n2, 0.5, calm ) );
  // A teardrop: a narrower foot, widest a fifth of the way up, tapering to the tip (a sheet of fire
  // across a box keeps its width). Its edge licks in and out with the fine noise.
  float w = 0.85 * mix( 1.0, 0.08, smoothstep( 0.1, 1.0, y ) ) * ( 0.55 + 0.45 * smoothstep( - 0.05, 0.22, y ) );
  w = mix( w, 1.6, wall );
  float e = abs( x ) / w + ( 0.5 - n2 ) * 0.9 * ( 0.3 + y );
  float body = 1.0 - smoothstep( 0.4, 1.0, e );
  // Hottest at the foot; the turbulence eats it from the top.
  float h = body * ( 1.1 - 0.7 * y ) - ( 1.0 - n ) * mix( 0.2, 1.3, y ) * mix( 1.0, 0.5, calm );
  return h * smoothstep( - 0.02, 0.08, uv.y );
}
vec3 sectFlameColor( float h ) {
  h = clamp( h, 0.0, 1.4 );
  vec3 c = mix( ${v3(R.ember)}, ${v3(R.orange)}, smoothstep( 0.05, 0.35, h ) );
  c = mix( c, ${v3(R.yellow)}, smoothstep( 0.35, 0.8, h ) );
  c = mix( c, ${v3(R.white)}, smoothstep( 0.85, 1.25, h ) );
  return c * ( 0.15 + ${f(FLAMES.brightness)} * h * h ) * smoothstep( 0.0, 0.07, h );
}
${FLICKER_GLSL}
`;
