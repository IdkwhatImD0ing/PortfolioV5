/**
 * Waterfalls for /sect: the pure maths (no three.js) behind the sheet shader, the per-vertex fall
 * attribute it reads, and the wet rock beside and behind the falls.
 *
 * Fall: water leaves the lip at FALL.lipSpeed and falls under gravity with quadratic air drag
 * (terminal speed FALL.terminal), so it speeds up all the way down: the abode's 46.5 m drop takes
 * about 3.1 s (15 m/s on average, 29 m/s at the pool); a 250 m range fall takes 9 s. Streams flow
 * at a steady FALL.streamSpeed.
 *
 * Sheet attribute `aFall` (four floats per vertex, built once per water mesh at load, in world
 * metres, so streak size does not depend on a sheet's size): x = metres across (u - 0.5 times the
 * lip width), y = metres below the lip (streams: along the flow from the head), z = the sheet's
 * height (negative for a stream: its length), w = the lip width. Metres below the lip come from
 * world height (today's GLBs: v is linear in height, and glTF flips it, so v = 0 is the lip there
 * while the corner quads have v = 1 at the lip; height avoids both). When a GLB carries Blender's
 * UV1 = (metres across, seconds since the lip), those are used instead: Blender writes free-fall
 * seconds (t = sqrt(2 d / g)), so they turn back into the true metres with uv1FallMetres. The shader
 * turns metres below the lip into seconds per pixel with its own drag model.
 *
 * Wet rock: the falls in meta.json (sheets of one fall grouped by their shared foot) become wet
 * volumes: a band beside and behind the falling water (the cliff it pours down), and a splash zone
 * around the foot. Every frame the page picks the WET.max nearest (tier-dependent) and the baked
 * surfaces inside them darken a little, gain colour, and get a faint sun glint (wetRockGlsl). Falls
 * near the cut-off fade out before they are swapped, so nothing pops.
 */
import { glslFloat } from "./glsl";
import type { Vec3, Waterfall } from "./types";

// ---------------------------------------------------------------------------------------------
// Fall physics

export interface FallPhysics {
  /** Gravity (m/s^2). */
  g: number;
  /** Terminal speed of falling water (m/s): the drag that keeps tall falls from going supersonic. */
  terminal: number;
  /** Speed over the lip (m/s). */
  lipSpeed: number;
  /** Steady speed of streams (m/s). */
  streamSpeed: number;
}

export const FALL: FallPhysics = { g: 9.81, terminal: 38, lipSpeed: 1.5, streamSpeed: 3 };

/** ln(cosh(x)) without overflow. */
function lnCosh(x: number): number {
  const a = Math.abs(x);
  return a + Math.log1p(Math.exp(-2 * a)) - Math.LN2;
}

/** Seconds to fall s metres from rest with quadratic drag. */
function fromRest(s: number, f: FallPhysics): number {
  const x = (Math.max(s, 0) * f.g) / (f.terminal * f.terminal);
  return (f.terminal / f.g) * (x + Math.log(1 + Math.sqrt(Math.max(1 - Math.exp(-2 * x), 0))));
}

/** Metres fallen from rest in t seconds with quadratic drag. */
function distanceFromRest(t: number, f: FallPhysics): number {
  return ((f.terminal * f.terminal) / f.g) * lnCosh((f.g * Math.max(t, 0)) / f.terminal);
}

/** Where a fall from rest reaches the lip speed (metres): the lip is that far down a fall from rest. */
export function lipStart(f: FallPhysics = FALL): number {
  const r = Math.min(f.lipSpeed / f.terminal, 0.999);
  return -((f.terminal * f.terminal) / (2 * f.g)) * Math.log(1 - r * r);
}

/** Seconds since the lip, d metres below it. */
export function fallSeconds(d: number, f: FallPhysics = FALL): number {
  const s0 = lipStart(f);
  return fromRest(Math.max(d, 0) + s0, f) - fromRest(s0, f);
}

/** Speed (m/s) d metres below the lip. */
export function fallSpeed(d: number, f: FallPhysics = FALL): number {
  const s = Math.max(d, 0) + lipStart(f);
  return f.terminal * Math.sqrt(Math.max(1 - Math.exp((-2 * f.g * s) / (f.terminal * f.terminal)), 0));
}

/** Metres below the lip after t seconds (the inverse of fallSeconds). */
export function fallDistance(t: number, f: FallPhysics = FALL): number {
  const s0 = lipStart(f);
  return Math.max(distanceFromRest(Math.max(t, 0) + fromRest(s0, f), f) - s0, 0);
}

/** Metres below the lip from Blender's UV1 seconds, which are free fall from the lip (d = g t^2 / 2). */
export function uv1FallMetres(t: number, f: FallPhysics = FALL): number {
  const s = Math.max(t, 0);
  return 0.5 * f.g * s * s;
}

/** GLSL: sectFallSeconds( d ) and sectFallSpeed( d ), the same maths as fallSeconds and fallSpeed. */
export function fallGlsl(f: FallPhysics = FALL): string {
  const s0 = lipStart(f);
  return /* glsl */ `
#define SECT_FALL_G ${glslFloat(f.g)}
#define SECT_FALL_VT ${glslFloat(f.terminal)}
#define SECT_FALL_S0 ${glslFloat(s0)}
#define SECT_FALL_T0 ${glslFloat(fromRest(s0, f))}
#define SECT_STREAM_SPEED ${glslFloat(f.streamSpeed)}
// Seconds to fall s metres from rest with quadratic drag (terminal speed SECT_FALL_VT).
float sectFallFromRest( float s ) {
  float x = max( s, 0.0 ) * ( SECT_FALL_G / ( SECT_FALL_VT * SECT_FALL_VT ) );
  return ( SECT_FALL_VT / SECT_FALL_G ) * ( x + log( 1.0 + sqrt( max( 1.0 - exp( -2.0 * x ), 0.0 ) ) ) );
}
// Seconds since the lip, d metres below it (the lip is SECT_FALL_S0 down a fall from rest).
float sectFallSeconds( float d ) {
  return sectFallFromRest( max( d, 0.0 ) + SECT_FALL_S0 ) - SECT_FALL_T0;
}
// Speed (m/s) d metres below the lip.
float sectFallSpeed( float d ) {
  float s = max( d, 0.0 ) + SECT_FALL_S0;
  return SECT_FALL_VT * sqrt( max( 1.0 - exp( -2.0 * SECT_FALL_G * s / ( SECT_FALL_VT * SECT_FALL_VT ) ), 0.0 ) );
}
`;
}

// ---------------------------------------------------------------------------------------------
// The sheet's look (createWaterfallSheetMaterial reads these as GLSL constants)

export const SHEET = {
  /** Pattern rate (1/s): a noise tile passes a point every 1/k s, so it is (speed / k) m long. */
  k: 0.9,
  /** Metres across per tile: clumps (layer A), fine streaks (layer B), the photo strands. */
  clumpTileM: 5,
  streakTileM: 1.4,
  strandTileM: 5,
  /** Layer B runs at 1.7 x the pattern rate and moves 1.12 x as fast as the water (shimmer). */
  streakRate: 1.7,
  streakSpeed: 1.12,
  /** Photo strand tiles per second: its natural 1 : 1.5 aspect at about 11 m/s. */
  strandRate: 1.5,
  /** Clumps grow on wide falls (more water): x sqrt(width / clumpRefWidthM), up to clumpMaxScale. */
  clumpRefWidthM: 6,
  clumpMaxScale: 2.5,
  /** Shares of the height: the glassy lip on top, where the clumps start tearing apart, the foot fade. */
  lip: 0.06,
  breakup: 0.6,
  footFade: 0.05,
  /**
   * Metres from the camera over which the tiling patterns give way to soft streaks that vary only
   * across the fall (far off, their repeats line up into a lattice).
   */
  farFrom: 130,
  farTo: 260,
  /** The glassy lip's tint and the sun's glow through the water (sRGB hex). */
  glass: "#7c9ca3",
  glow: "#ffcf9a",
  /** The strand texture (shared by every set, beside the sets: <sect>/fx/). */
  strands: "strands.webp",
} as const;

/** URL of a shared effect texture: the `fx` folder beside the set's folder ("/sect/full" -> "/sect/fx/<file>"). */
export function fxAssetUrl(base: string, file: string): string {
  const b = base.replace(/\/+$/, "");
  const i = b.lastIndexOf("/");
  return `${i >= 0 ? b.slice(0, i) : ""}/fx/${file}`;
}

// ---------------------------------------------------------------------------------------------
// The per-vertex fall attribute

export interface SheetVertices {
  /** World-space xyz per vertex. */
  positions: ArrayLike<number>;
  /** UV0 per vertex (u across the water). */
  uvs: ArrayLike<number>;
  /** Triangle list, or null for a plain triangle soup. */
  index: ArrayLike<number> | null;
  /** A stream (flows along the ground from its head) rather than a falling sheet. */
  stream?: boolean;
  /** Blender's UV1 = (metres across, seconds since the lip), when the GLB has it. */
  uv1?: ArrayLike<number> | null;
}

/** Vertex ids grouped by connected piece (each sheet of a merged water mesh is one piece). */
export function connectedPieces(vertexCount: number, index: ArrayLike<number> | null): number[][] {
  const parent = new Int32Array(vertexCount);
  for (let i = 0; i < vertexCount; i++) parent[i] = i;
  const find = (x: number): number => {
    let r = x;
    while (parent[r] !== r) r = parent[r];
    while (parent[x] !== r) {
      const nx = parent[x];
      parent[x] = r;
      x = nx;
    }
    return r;
  };
  const join = (a: number, b: number) => {
    const ra = find(a);
    const rb = find(b);
    if (ra !== rb) parent[rb] = ra;
  };
  const n = index ? index.length : vertexCount;
  for (let t = 0; t + 2 < n; t += 3) {
    const a = index ? index[t] : t;
    join(a, index ? index[t + 1] : t + 1);
    join(a, index ? index[t + 2] : t + 2);
  }
  const groups = new Map<number, number[]>();
  for (let i = 0; i < vertexCount; i++) {
    const r = find(i);
    const g = groups.get(r);
    if (g) g.push(i);
    else groups.set(r, [i]);
  }
  return [...groups.values()];
}

function dist3(p: ArrayLike<number>, i: number, j: number): number {
  return Math.hypot(p[i * 3] - p[j * 3], p[i * 3 + 1] - p[j * 3 + 1], p[i * 3 + 2] - p[j * 3 + 2]);
}

/** Lip width of a piece: across its top vertices, metres per unit of u (widening the band until it spans u). */
function lipWidth(ids: readonly number[], p: ArrayLike<number>, uv: ArrayLike<number>, below: Float32Array, height: number): number {
  for (const share of [0.03, 0.1, 0.3, 1.01]) {
    let lo = -1;
    let hi = -1;
    for (const i of ids) {
      if (below[i] > share * height + 1e-3) continue;
      if (lo < 0 || uv[i * 2] < uv[lo * 2]) lo = i;
      if (hi < 0 || uv[i * 2] > uv[hi * 2]) hi = i;
    }
    if (lo < 0) continue;
    const du = uv[hi * 2] - uv[lo * 2];
    if (du > 0.2) return Math.max(dist3(p, lo, hi) / du, 0.1);
  }
  return 1;
}

/**
 * The `aFall` attribute (four floats per vertex; see the header) for a water mesh. Each connected
 * piece is measured on its own: a merged water GLB holds every sheet of an area.
 */
export function sheetFallAttribute(m: SheetVertices, f: FallPhysics = FALL): Float32Array {
  const n = Math.floor(m.positions.length / 3);
  const out = new Float32Array(n * 4);
  const below = new Float32Array(n);
  const p = m.positions;
  const uv = m.uvs;
  for (const ids of connectedPieces(n, m.index)) {
    let height = 0;
    let width = 1;
    const across = (i: number) => (uv[i * 2] - 0.5) * width;
    let acrossOf = across;
    if (m.uv1) {
      const uv1 = m.uv1;
      let lo = Infinity;
      let hi = -Infinity;
      for (const i of ids) {
        below[i] = m.stream ? Math.max(uv1[i * 2 + 1], 0) * f.streamSpeed : uv1FallMetres(uv1[i * 2 + 1], f);
        height = Math.max(height, below[i]);
        lo = Math.min(lo, uv1[i * 2]);
        hi = Math.max(hi, uv1[i * 2]);
      }
      width = Math.max(hi - lo, 0.1);
      acrossOf = (i) => uv1[i * 2];
    } else if (m.stream) {
      height = streamBelow(ids, p, uv, below);
      width = streamWidth(ids, p, uv);
    } else {
      let top = -Infinity;
      let bottom = Infinity;
      for (const i of ids) {
        top = Math.max(top, p[i * 3 + 1]);
        bottom = Math.min(bottom, p[i * 3 + 1]);
      }
      for (const i of ids) below[i] = top - p[i * 3 + 1];
      height = top - bottom;
      width = lipWidth(ids, p, uv, below, height);
    }
    const h = Math.max(height, 0.01) * (m.stream ? -1 : 1);
    for (const i of ids) {
      out[i * 4] = acrossOf(i);
      out[i * 4 + 1] = below[i];
      out[i * 4 + 2] = h;
      out[i * 4 + 3] = width;
    }
  }
  return out;
}

/** A stream's rows (one per value of v), ordered from the head (the higher end), with their vertices. */
function streamRows(ids: readonly number[], p: ArrayLike<number>, uv: ArrayLike<number>): { c: Vec3; ids: number[] }[] {
  const rows = new Map<number, { s: Vec3; ids: number[] }>();
  for (const i of ids) {
    const key = Math.round(uv[i * 2 + 1] * 4096);
    const r = rows.get(key) ?? { s: [0, 0, 0] as Vec3, ids: [] };
    r.s[0] += p[i * 3];
    r.s[1] += p[i * 3 + 1];
    r.s[2] += p[i * 3 + 2];
    r.ids.push(i);
    rows.set(key, r);
  }
  const list = [...rows.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([, r]) => ({ c: [r.s[0] / r.ids.length, r.s[1] / r.ids.length, r.s[2] / r.ids.length] as Vec3, ids: r.ids }));
  if (list.length > 1 && list[list.length - 1].c[1] > list[0].c[1]) list.reverse();
  return list;
}

/** Metres along a stream from its head (into `below`); returns its length. */
function streamBelow(ids: readonly number[], p: ArrayLike<number>, uv: ArrayLike<number>, below: Float32Array): number {
  const rows = streamRows(ids, p, uv);
  let d = 0;
  rows.forEach((r, k) => {
    if (k > 0) {
      const a = rows[k - 1].c;
      d += Math.hypot(r.c[0] - a[0], r.c[1] - a[1], r.c[2] - a[2]);
    }
    for (const i of r.ids) below[i] = d;
  });
  return d;
}

/** Mean width of a stream's rows (from their lowest-u to their highest-u vertex). */
function streamWidth(ids: readonly number[], p: ArrayLike<number>, uv: ArrayLike<number>): number {
  let sum = 0;
  let count = 0;
  for (const r of streamRows(ids, p, uv)) {
    if (r.ids.length < 2) continue;
    let lo = r.ids[0];
    let hi = r.ids[0];
    for (const i of r.ids) {
      if (uv[i * 2] < uv[lo * 2]) lo = i;
      if (uv[i * 2] > uv[hi * 2]) hi = i;
    }
    const du = uv[hi * 2] - uv[lo * 2];
    if (du < 0.2) continue;
    sum += dist3(p, lo, hi) / du;
    count++;
  }
  return count > 0 ? Math.max(sum / count, 0.1) : 1;
}

// ---------------------------------------------------------------------------------------------
// Wet rock

export const WET = {
  /** Falls drawn wet at once (nearest first) by quality tier; the shader's array holds `max`. */
  max: 6,
  perTier: { high: 6, mid: 4, low: 2 } as Record<"high" | "mid" | "low", number>,
  /** No wet rock beyond this distance from the camera (m); it fades over the last 30 %. */
  maxDistance: 1500,
  /** Sheets whose feet are closer than this are one fall (m). */
  merge: 12,
  /** The wet band beside the water: its half width times `side` plus `sideM` metres. */
  side: 1.5,
  sideM: 2.5,
  /** How far behind the falling water the rock gets wet (m): reach + reachPerM x height, plus the arc's gap. */
  reach: 3,
  reachPerM: 0.02,
  /** In front of the water (the gorge's sides that stand forward of it) the spray fades out over these metres. */
  front: 1.5,
  frontFar: 6,
  /** Splash zone round the foot: radius = max(splashMinR, splashWidths x half foot width + 2), height share. */
  splashMinR: 4,
  splashWidths: 2.4,
  splashHeight: 0.2,
  splashMaxH: 8,
  /** The band beside the water fades in over this share of the height below the lip (wetDown). */
  wetIn: 0.18,
  /**
   * Trickle noise eats into the band's soft edges: a point is wet once its mask passes a threshold
   * between edgeCut and edgeCut + edgeSpread (set by the streaky noise), over +- edgeSoft.
   */
  edgeCut: 0.18,
  edgeSpread: 0.4,
  edgeSoft: 0.18,
  /** Look at full wetness: brightness factor, extra saturation, sheen (times the sun's colour). */
  dark: 0.52,
  saturate: 0.2,
  sheen: 0.22,
  gloss: 0.015,
} as const;

/** One fall as a wet volume (three space). */
export interface WetFall {
  name: string;
  /** The set its water is drawn with: its chunk, or "global" (the backdrop's water and v1 water files). */
  chunk: string;
  /** Centre of the lip and of the foot. */
  lip: Vec3;
  foot: Vec3;
  /** Horizontal unit vector away from the cliff (where the water arcs out). */
  out: [number, number];
  /** How far out the foot sits from the lip along `out` (m, >= 0). */
  outFoot: number;
  /** No clear arc: wet on both sides of the water. */
  symmetric: boolean;
  halfLip: number;
  halfFoot: number;
  /** Lip height above the foot (m). */
  height: number;
  splashR: number;
  splashH: number;
}

const mid = (a: Vec3, b: Vec3): Vec3 => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2];

/** The falls of meta.json as wet volumes: sheets (with corners) sharing a foot are one fall. */
export function wetFalls(falls: readonly Waterfall[], merge = WET.merge): WetFall[] {
  const groups: { sheets: Waterfall[]; foot: Vec3 }[] = [];
  for (const w of falls) {
    if (w.kind !== "sheet" || !w.corners) continue;
    const foot = w.foot ?? mid(w.corners[2], w.corners[3]);
    const g = groups.find((x) => Math.hypot(x.foot[0] - foot[0], x.foot[1] - foot[1], x.foot[2] - foot[2]) < merge);
    if (g) g.sheets.push(w);
    else groups.push({ sheets: [w], foot });
  }
  const out: WetFall[] = [];
  for (const { sheets } of groups) {
    const lips = sheets.map((s) => mid(s.corners![0], s.corners![1]));
    const feet = sheets.map((s) => mid(s.corners![2], s.corners![3]));
    const mean = (l: Vec3[]): Vec3 => [0, 1, 2].map((k) => l.reduce((a, v) => a + v[k], 0) / l.length) as Vec3;
    const lip = mean(lips);
    const foot = mean(feet);
    // Across: the widest sheet's lip, flattened.
    const wide = sheets.reduce((a, s) => (span(s.corners!) > span(a.corners!) ? s : a));
    let ax = wide.corners![1][0] - wide.corners![0][0];
    let az = wide.corners![1][2] - wide.corners![0][2];
    const al = Math.hypot(ax, az);
    if (al < 1e-6) {
      ax = 1;
      az = 0;
    } else {
      ax /= al;
      az /= al;
    }
    let o: [number, number] = [-az, ax];
    let outFoot = (foot[0] - lip[0]) * o[0] + (foot[2] - lip[2]) * o[1];
    if (outFoot < 0) {
      o = [-o[0], -o[1]];
      outFoot = -outFoot;
    }
    let halfLip = 0;
    let halfFoot = 0;
    for (const s of sheets) {
      const c = s.corners!;
      for (const k of [0, 1]) halfLip = Math.max(halfLip, Math.abs((c[k][0] - lip[0]) * ax + (c[k][2] - lip[2]) * az));
      for (const k of [2, 3]) halfFoot = Math.max(halfFoot, Math.abs((c[k][0] - foot[0]) * ax + (c[k][2] - foot[2]) * az));
    }
    const height = Math.max(lip[1] - foot[1], 0.5);
    const chunk = sheets[0].chunk;
    out.push({
      name: sheets[0].name,
      chunk: chunk && chunk !== "backdrop" ? chunk : "global",
      lip,
      foot,
      out: o,
      outFoot,
      symmetric: outFoot < 0.5,
      halfLip,
      halfFoot,
      height,
      splashR: Math.max(WET.splashMinR, WET.splashWidths * halfFoot + 2),
      splashH: Math.min(Math.max(WET.splashHeight * height, 2), WET.splashMaxH),
    });
  }
  return out;
}

function span(c: readonly Vec3[]): number {
  return Math.hypot(c[1][0] - c[0][0], c[1][2] - c[0][2]);
}

/** Distance from p to the fall (its lip-to-foot axis, less its half width), >= 0. */
export function wetFallDistance(f: WetFall, p: Vec3): number {
  const d: Vec3 = [f.foot[0] - f.lip[0], f.foot[1] - f.lip[1], f.foot[2] - f.lip[2]];
  const l2 = d[0] * d[0] + d[1] * d[1] + d[2] * d[2];
  const t = l2 > 0 ? Math.min(Math.max(((p[0] - f.lip[0]) * d[0] + (p[1] - f.lip[1]) * d[1] + (p[2] - f.lip[2]) * d[2]) / l2, 0), 1) : 0;
  const q = [f.lip[0] + d[0] * t, f.lip[1] + d[1] * t, f.lip[2] + d[2] * t];
  return Math.max(Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]) - Math.max(f.halfLip, f.halfFoot), 0);
}

function smoothstep(a: number, b: number, x: number): number {
  const t = Math.min(Math.max((x - a) / (b - a), 0), 1);
  return t * t * (3 - 2 * t);
}

/**
 * The `max` falls nearest the camera, each with a strength (0..1) that fades it out before it
 * would be swapped for a nearer one (and toward WET.maxDistance), so the wet rock never pops.
 */
export function selectWetFalls(falls: readonly WetFall[], camera: Vec3, max: number, maxDistance: number = WET.maxDistance): { fall: WetFall; strength: number }[] {
  const ranked = falls
    .map((fall) => ({ fall, d: wetFallDistance(fall, camera) }))
    .filter((r) => r.d < maxDistance)
    .sort((a, b) => a.d - b.d);
  const cut = ranked.length > max ? ranked[max].d : maxDistance;
  const ramp = Math.max(0.25 * cut, 30);
  return ranked
    .slice(0, Math.max(max, 0))
    .map((r) => ({
      fall: r.fall,
      strength: Math.min(Math.max((cut - r.d) / ramp, 0), 1) * (1 - smoothstep(0.7 * maxDistance, maxDistance, r.d)),
    }))
    .filter((r) => r.strength > 0);
}

/** Uniform arrays of the wet shader (four vec4 per fall; see wetRockGlsl). */
export interface WetArrays {
  a: Float32Array;
  b: Float32Array;
  c: Float32Array;
  d: Float32Array;
}

export function wetArrays(max: number = WET.max): WetArrays {
  return { a: new Float32Array(max * 4), b: new Float32Array(max * 4), c: new Float32Array(max * 4), d: new Float32Array(max * 4) };
}

/** Writes the selected falls into the arrays; returns how many were written. */
export function packWetFalls(sel: readonly { fall: WetFall; strength: number }[], arr: WetArrays): number {
  const n = Math.min(sel.length, arr.a.length / 4);
  for (let i = 0; i < n; i++) {
    const { fall: f, strength } = sel[i];
    arr.a.set([f.lip[0], f.lip[1], f.lip[2], f.foot[1]], i * 4);
    arr.b.set([f.out[0], f.out[1], strength, f.symmetric ? 1 : 0], i * 4);
    arr.c.set([f.outFoot, f.halfLip, f.halfFoot, f.height], i * 4);
    arr.d.set([f.foot[0], f.foot[2], f.splashR, f.splashH], i * 4);
  }
  return n;
}

/**
 * How wet the band beside the water is at share s of the way down (0 at the lip): dry at the lip,
 * wetter as the spray spreads (over the top WET.wetIn of the height), wettest at the foot. A
 * gradual top instead of a ruled line level with the lip.
 */
export function wetDown(s: number): number {
  return smoothstep(0, WET.wetIn, s) * (0.75 + 0.25 * s);
}

/**
 * Wetness (0..1) of a surface point p from one fall: the band beside and behind the water and the
 * splash zone round the foot. The same maths as sectWetMask in wetRockGlsl (before the streaky
 * drip noise), for tests.
 */
export function wetAmount(f: WetFall, p: Vec3, strength = 1): number {
  if (p[1] > f.lip[1] + 1 || p[1] < f.foot[1] - 2) return 0;
  const dx = p[0] - f.lip[0];
  const dz = p[2] - f.lip[2];
  const o = dx * f.out[0] + dz * f.out[1];
  const a = dx * f.out[1] - dz * f.out[0];
  const s = Math.min(Math.max((f.lip[1] - p[1]) / Math.max(f.height, 1), 0), 1);
  const hw = (f.halfLip + (f.halfFoot - f.halfLip) * s) * WET.side + WET.sideM;
  const h = p[1] - f.foot[1];
  const r = Math.hypot(p[0] - f.foot[0], p[2] - f.foot[2]);
  const wS = (1 - smoothstep(f.splashR * 0.55, f.splashR, r)) * (1 - smoothstep(f.splashH * 0.35, f.splashH, h)) * smoothstep(-1.5, -0.5, h);
  const lat = 1 - smoothstep(hw * 0.65, hw, Math.abs(a));
  const oSheet = f.outFoot * s * s;
  const dl = o - oSheet;
  const reach = WET.reach + WET.reachPerM * f.height + oSheet;
  const depth = f.symmetric
    ? 1 - smoothstep(reach * 0.6, reach, Math.abs(dl))
    : (1 - smoothstep(reach * 0.6, reach, -dl)) * (1 - smoothstep(WET.front, WET.frontFar, dl));
  const vert = (1 - smoothstep(0, 0.8, p[1] - f.lip[1])) * smoothstep(-1.5, 0, h);
  const wC = lat * depth * vert * wetDown(s);
  return Math.max(wC, wS) * strength;
}

/**
 * GLSL for baked surfaces near the falls: the uniforms (four vec4 arrays of WET.max falls, as
 * packWetFalls writes them, the count, the sun direction and the sheen colour, the clock, a noise
 * texture) and `vec3 sectWetRock( vec3 col, vec3 p )`. Call it in uniform control flow (it takes
 * screen-space derivatives); it returns `col` untouched away from the falls. Cost: per pixel and
 * selected fall, a height test (about 4 operations) and, inside a fall's height range, about 40
 * more; one noise fetch only on wet pixels.
 */
export function wetRockGlsl(max: number = WET.max): string {
  return /* glsl */ `
#define SECT_WET_MAX ${Math.max(1, Math.round(max))}
uniform vec4 uWetA[ SECT_WET_MAX ];
uniform vec4 uWetB[ SECT_WET_MAX ];
uniform vec4 uWetC[ SECT_WET_MAX ];
uniform vec4 uWetD[ SECT_WET_MAX ];
uniform int uWetCount;
uniform vec3 uWetSun;
uniform vec3 uWetSheen;
uniform float uWetTime;
uniform sampler2D tWetNoise;
// Wetness of p (0..1) from the selected falls, and its across coordinate on the wettest one.
float sectWetMask( vec3 p, out float across ) {
  float w = 0.0;
  across = 0.0;
  for ( int i = 0; i < SECT_WET_MAX; i ++ ) {
    if ( i >= uWetCount ) break;
    vec4 A = uWetA[ i ];
    if ( p.y > A.y + 1.0 || p.y < A.w - 2.0 ) continue;
    vec4 B = uWetB[ i ];
    vec4 C = uWetC[ i ];
    vec4 D = uWetD[ i ];
    vec2 d = p.xz - A.xz;
    float o = dot( d, B.xy );
    float a = dot( d, vec2( B.y, - B.x ) );
    float s = clamp( ( A.y - p.y ) / max( C.w, 1.0 ), 0.0, 1.0 );
    float hw = mix( C.y, C.z, s ) * ${glslFloat(WET.side)} + ${glslFloat(WET.sideM)};
    float h = p.y - A.w;
    float r = length( p.xz - D.xy );
    if ( abs( a ) > hw && r > D.z ) continue;
    float wS = ( 1.0 - smoothstep( D.z * 0.55, D.z, r ) ) * ( 1.0 - smoothstep( D.w * 0.35, D.w, h ) ) * smoothstep( -1.5, -0.5, h );
    float lat = 1.0 - smoothstep( hw * 0.65, hw, abs( a ) );
    float oSheet = C.x * s * s;
    float dl = o - oSheet;
    float reach = ${glslFloat(WET.reach)} + ${glslFloat(WET.reachPerM)} * C.w + oSheet;
    float depth = B.w > 0.5 ? 1.0 - smoothstep( reach * 0.6, reach, abs( dl ) )
      : ( 1.0 - smoothstep( reach * 0.6, reach, - dl ) ) * ( 1.0 - smoothstep( ${glslFloat(WET.front)}, ${glslFloat(WET.frontFar)}, dl ) );
    float vert = ( 1.0 - smoothstep( 0.0, 0.8, p.y - A.y ) ) * smoothstep( -1.5, 0.0, h );
    float down = smoothstep( 0.0, ${glslFloat(WET.wetIn)}, s ) * ( 0.75 + 0.25 * s );
    float wi = max( lat * depth * vert * down, wS ) * B.z;
    if ( wi > w ) {
      w = wi;
      across = a;
    }
  }
  return w;
}
// Darker, a little more saturated, with a faint sun glint streaked by trickles running down.
vec3 sectWetRock( vec3 col, vec3 p ) {
  if ( uWetCount <= 0 ) return col;
  float across;
  float w = sectWetMask( p, across );
  vec3 dpx = dFdx( p );
  vec3 dpy = dFdy( p );
  if ( w <= 0.002 ) return col;
  vec3 toCam = cameraPosition - p;
  float dist = length( toCam );
  vec3 v = toCam / max( dist, 1e-3 );
  vec3 n = normalize( cross( dpx, dpy ) + vec3( 0.0, 1e-6, 0.0 ) );
  if ( dot( n, v ) < 0.0 ) n = - n;
  // Explicit level of detail: this runs in non-uniform control flow (no implicit derivatives).
  float lod = clamp( log2( max( dist * 0.08, 1.0 ) ), 0.0, 7.0 );
  float drip = textureLod( tWetNoise, vec2( across * 0.45, ( p.y + uWetTime * 0.35 ) * 0.11 ), lod ).r;
  drip = smoothstep( 0.3, 0.7, drip );
  // The trickles eat into the soft edges (ragged, streaked tops and sides, never a ruled band) and
  // mottle the inside. Continuous at w = 0: the lowest threshold's ramp starts there.
  float cut = ${glslFloat(WET.edgeCut)} + ${glslFloat(WET.edgeSpread)} * ( 1.0 - drip );
  w = smoothstep( cut - ${glslFloat(WET.edgeSoft)}, cut + ${glslFloat(WET.edgeSoft)}, w ) * mix( 0.8, 1.0, drip );
  float l = dot( col, vec3( 0.2126, 0.7152, 0.0722 ) );
  vec3 wet = max( mix( vec3( l ), col, ${glslFloat(1 + WET.saturate)} ), 0.0 ) * ${glslFloat(WET.dark)};
  float spec = pow( max( dot( reflect( - v, n ), uWetSun ), 0.0 ), 24.0 );
  float fres = pow( 1.0 - max( dot( n, v ), 0.0 ), 5.0 );
  wet += uWetSheen * ( ${glslFloat(WET.sheen)} * ( 0.35 + 0.65 * drip ) * ( spec * 0.8 + fres * 0.2 ) + ${glslFloat(WET.gloss)} );
  return mix( col, wet, w );
}
`;
}

// ---------------------------------------------------------------------------------------------
// Picking a waterfall

/** A waterfall sheet that picks a hotspot: its quad (meta.json corners) in world space. */
export interface FallPick {
  /** The hotspot the sheet belongs to. */
  id: string;
  /** Chunk whose water file draws the sheet (the pick only counts while it is drawn), or null. */
  chunk: string | null;
  corners: readonly [Vec3, Vec3, Vec3, Vec3];
}

function insideBox(p: Vec3, center: Vec3, size: Vec3): boolean {
  for (let k = 0; k < 3; k++) if (Math.abs(p[k] - center[k]) > size[k] / 2) return false;
  return true;
}

/**
 * The falling water as pick shapes for the item it is part of (the abode's "Waterfall" fact). The
 * merged water mesh carries no object names, and the item's own tagged meshes are only the small
 * lip and pool pieces, so the water itself never picked it (1 of 57 points over the falling water).
 * A sheet belongs to the item hotspot (an id with a ':') of its own chunk whose box holds the
 * sheet's centre; when boxes nest, the smallest. Sheets without corners, or in no item's box, are
 * left out.
 */
export function fallPickQuads(
  falls: readonly Waterfall[],
  hotspots: readonly { id: string; center: Vec3; size: Vec3; chunk?: string | null }[],
): FallPick[] {
  const out: FallPick[] = [];
  for (const f of falls) {
    if (!f.corners) continue;
    let best: { id: string; volume: number } | null = null;
    for (const h of hotspots) {
      if (!h.id.includes(":") || (h.chunk ?? null) !== (f.chunk ?? null) || !insideBox(f.position, h.center, h.size)) continue;
      const volume = h.size[0] * h.size[1] * h.size[2];
      if (!best || volume < best.volume) best = { id: h.id, volume };
    }
    if (best) out.push({ id: best.id, chunk: f.chunk ?? null, corners: f.corners });
  }
  return out;
}

function sub(a: Vec3, b: Vec3): Vec3 {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function cross(a: Vec3, b: Vec3): Vec3 {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}

function dot(a: Vec3, b: Vec3): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

/** Distance along a ray to a triangle, from either side (Möller-Trumbore), or null. */
function rayTriangle(o: Vec3, d: Vec3, a: Vec3, b: Vec3, c: Vec3): number | null {
  const e1 = sub(b, a);
  const e2 = sub(c, a);
  const p = cross(d, e2);
  const det = dot(e1, p);
  if (Math.abs(det) < 1e-9) return null;
  const inv = 1 / det;
  const s = sub(o, a);
  const u = dot(s, p) * inv;
  if (u < 0 || u > 1) return null;
  const q = cross(s, e1);
  const v = dot(d, q) * inv;
  if (v < 0 || u + v > 1) return null;
  const t = dot(e2, q) * inv;
  return t > 0 ? t : null;
}

/** Distance along a ray (unit `dir`) to a quad given by its corners in order, or null when it misses. */
export function rayQuad(origin: Vec3, dir: Vec3, c: readonly [Vec3, Vec3, Vec3, Vec3]): number | null {
  const t1 = rayTriangle(origin, dir, c[0], c[1], c[2]);
  const t2 = rayTriangle(origin, dir, c[0], c[2], c[3]);
  if (t1 === null) return t2;
  return t2 === null ? t1 : Math.min(t1, t2);
}
