/**
 * Pours for /sect: the top of a waterfall that leaves its cliff through a notch (pure maths, no
 * three.js; docs/sect/waterfall-pour.md has the pictures and the measurements).
 *
 * The abode's fall is baked as three flat sheets as wide as the fall (6 m) whose top row hangs level
 * with the lowest point of a V-shaped notch in the cliff top. A V has no width at its point, so
 * 3 m of water on either side began on bare rock face along a ruled line, under an empty notch.
 *
 * A pour reshapes that top when the water loads (no bake, no new file):
 *
 * - The sheets' top rises to a water level inside the notch (`level`), where the notch is as wide
 *   as the pour, and steps back to the cliff's edge (`back`). The lift fades out over `liftOver`
 *   metres of fall, so the foot and everything below stay where they were baked.
 * - The sheets narrow toward the notch's centre line: `neck` of their width at the crest, the full
 *   width `fanOver` metres further down (most of it early: falling water spreads fast, then slows).
 *   The streaks keep their baked metres across, so they spread out of the notch with the water.
 * - A water surface fills the notch behind the crest (pourStream): level for a few metres, then
 *   sinking to the notch's floor further back, where its walls close over it. It is what a view
 *   from above sees in the notch.
 * - The moved vertices are flagged (the sheet shader's `aPour`): over the edge the water is deep,
 *   so its glassy lip hides the notch behind it and starts on a clean line, the water's level.
 *
 * Frame of a pour (pourFrame): origin at the core sheet's lip (meta.json `lip`: the mean of its
 * top row), a = metres across (along the lip, corner 0 to corner 1), o = metres out of the cliff
 * (toward the pool), h = metres up. The numbers of a PourSpec are read off the baked rock in that
 * frame, so they hold as long as the cliff and the fall are built as they are; a re-bake that
 * moves the area keeps them (they ride on the fall's own lip and corners).
 */
import type { Vec3, Waterfall } from "./types";

export interface PourSpec {
  /** The fall's core sheet in meta.json (its lip and corners give the frame). */
  sheet: string;
  /** The baked sheets' top row and the first row of their fall, above the lip point (m). */
  top: number;
  /** How far out of the cliff the baked core sheet starts to fall (m; its crest row). */
  crestOut: number;
  /** The water level in the notch, above the lip point (m): the sheets' new top. */
  level: number;
  /** Metres of fall below the baked top over which the lift fades out. */
  liftOver: number;
  /** The crest steps back toward the cliff by this much (m), fading out over `backOver` m of fall. */
  back: number;
  backOver: number;
  /** The notch's centre line across (m). */
  centre: number;
  /** Share of the baked width the sheets keep at the crest. */
  neck: number;
  /** Metres below the crest at which the sheets are back to their baked width. */
  fanOver: number;
  /** The baked sheets lie within this of the origin: metres across (either side), behind and in front of the lip. */
  reach: { across: number; behind: number; front: number };
  /** The water in the notch behind the crest. */
  stream: {
    /** Strip width (m): wider than the notch at the water level, so its ragged edges are inside the rock. */
    width: number;
    /** Where it starts behind the lip (o, negative), and from where it is level (o). */
    from: number;
    levelFrom: number;
    /** Its height at the start, above the lip point (m): just over the notch's floor there. */
    floor: number;
    /** Rows along it (it bends where it sinks). */
    rows: number;
    /** The sheets' seed and flow in the vertex colour (r, g). */
    seed: number;
    flow: number;
  };
}

/**
 * The abode's fall. Read off the baked cliff (2026-11-20, abode.glb of bake round 61) in the pour's
 * frame: the notch's floor is at h 0.6 at the cliff's edge (o -1.0 to -0.55), 0.1 to 0.4 from 2 to
 * 8 m behind it and sinks behind that (the ridge's back); the notch is open, seen from the front,
 * from a -1.5 to 1.3 at h 2.0 and from -1.7 to 1.6 at h 2.4; the cliff's face under it stands at
 * o -0.55. The baked sheets' top rows are at h 0.49 to 0.56, from a -2.93 to 2.94 (core).
 */
export const POURS: readonly PourSpec[] = [
  {
    sheet: "abode.waterfall.sheet",
    top: 0.55,
    crestOut: -0.1,
    level: 2.2,
    liftOver: 6,
    back: 0.65,
    backOver: 2,
    centre: -0.08,
    neck: 0.58,
    fanOver: 14,
    reach: { across: 5, behind: 2, front: 8 },
    stream: { width: 6, from: -8.5, levelFrom: -3.5, floor: 0.3, rows: 14, seed: 0.37, flow: 0.5 },
  },
];

export interface PourFrame {
  /** The core sheet's lip (world). */
  origin: Vec3;
  /** Unit vectors (world, horizontal): across the fall, and out of the cliff. */
  across: Vec3;
  out: Vec3;
}

/** The frame of a pour from its core sheet's lip, corners and foot; null when meta.json lacks them. */
export function pourFrame(fall: Waterfall): PourFrame | null {
  if (!fall.corners || !fall.lip) return null;
  const [c0, c1, c2, c3] = fall.corners;
  const ax = c1[0] - c0[0];
  const az = c1[2] - c0[2];
  const al = Math.hypot(ax, az);
  if (al < 1e-6) return null;
  const across: Vec3 = [ax / al, 0, az / al];
  let out: Vec3 = [-across[2], 0, across[0]];
  // Out is the side the water lands on.
  const fx = (c2[0] + c3[0]) / 2 - fall.lip[0];
  const fz = (c2[2] + c3[2]) / 2 - fall.lip[2];
  if (fx * out[0] + fz * out[2] < 0) out = [-out[0], 0, -out[2]];
  return { origin: [fall.lip[0], fall.lip[1], fall.lip[2]], across, out };
}

/** A world point in the pour's frame: [a, o, h]. */
export function toPour(f: PourFrame, p: ArrayLike<number>, at = 0): Vec3 {
  const x = p[at] - f.origin[0];
  const y = p[at + 1] - f.origin[1];
  const z = p[at + 2] - f.origin[2];
  return [x * f.across[0] + z * f.across[2], x * f.out[0] + z * f.out[2], y];
}

/** A point of the pour's frame in the world. */
export function fromPour(f: PourFrame, l: Vec3): Vec3 {
  return [f.origin[0] + l[0] * f.across[0] + l[1] * f.out[0], f.origin[1] + l[2], f.origin[2] + l[0] * f.across[2] + l[1] * f.out[2]];
}

function smoothstep(a: number, b: number, x: number): number {
  const t = Math.min(Math.max((x - a) / (b - a), 0), 1);
  return t * t * (3 - 2 * t);
}

/** Whether a point (pour frame) is one the warp moves: on the baked sheets, down to where they are full width again. */
export function inPour(s: PourSpec, l: Vec3): boolean {
  const down = Math.max(s.liftOver, s.backOver, s.fanOver) + 1;
  return Math.abs(l[0]) <= s.reach.across && l[1] >= -s.reach.behind && l[1] <= s.reach.front && l[2] <= s.top + 0.5 && l[2] >= s.top - down;
}

/** Share of the baked width the sheets have `below` metres under the crest: `neck` there, 1 from `fanOver` on. */
export function pourWidth(s: PourSpec, below: number): number {
  const t = Math.min(Math.max(below / s.fanOver, 0), 1);
  return s.neck + (1 - s.neck) * (1 - (1 - t) * (1 - t));
}

/**
 * Where a baked sheet vertex goes (pour frame, both ways): up toward the water level, back toward
 * the cliff's edge and in toward the notch's centre line, each fading out with the metres fallen.
 * `middle` is the middle of the vertex's own sheet across (pourMiddle): the layers of a fall are
 * baked a little to one side of each other, and at the crest each narrows about the notch's centre
 * line, sliding back to its own place as it widens. Heights keep their order (a row never passes
 * the one above it), and a point below the lift, the step back and the fan does not move.
 */
export function warpPour(s: PourSpec, l: Vec3, middle: number = s.centre): Vec3 {
  // Metres below the baked top, and below the new crest: the rows near the top rise by the whole
  // lift, the ones further down by less (they spread over the extra height).
  const d = Math.max(s.top - l[2], 0);
  const below = d + (s.level - s.top) * smoothstep(0, s.liftOver, d);
  const h = s.level - below + Math.max(l[2] - s.top, 0);
  const o = l[1] - s.back * (1 - smoothstep(0, s.backOver, d));
  const w = pourWidth(s, below);
  // 0 at the crest, 1 at full width.
  const k = (w - s.neck) / Math.max(1 - s.neck, 1e-6);
  const a = s.centre + (middle - s.centre) * k + (l[0] - middle) * w;
  return [a, o, h];
}

/**
 * The middle across of one sheet (pour frame), from its vertices' a and h (metres across and up):
 * halfway between the ends of its top rows (the rows within a metre of the baked top, before the
 * sheet has spread). Null for a piece that is not a sheet of this pour: none of its vertices is
 * near the top.
 */
export function pourMiddle(s: PourSpec, across: ArrayLike<number>, up: ArrayLike<number>): number | null {
  let lo = Infinity;
  let hi = -Infinity;
  for (let i = 0; i < across.length; i++) {
    if (Math.abs(up[i] - s.top) > 1 || Math.abs(across[i]) > s.reach.across) continue;
    lo = Math.min(lo, across[i]);
    hi = Math.max(hi, across[i]);
  }
  return hi >= lo ? (lo + hi) / 2 : null;
}

/** The pour's crest (pour frame): where the core sheet starts to fall, after the warp. */
export function pourCrest(s: PourSpec): { out: number; level: number } {
  return { out: s.crestOut - s.back, level: s.level };
}

export interface PourStream {
  /** World xyz per vertex. */
  positions: Float32Array;
  /** u across, v along (0 at its start, 1 at the crest). */
  uvs: Float32Array;
  /** The sheet shader's vertex colour: a seed, the flow / 2, the layer (0: core). */
  colors: Float32Array;
  /** The sheet shader's `aFall` (waterfall.ts): metres across, metres along the flow, -(1 + share of its length), width. */
  fall: Float32Array;
  index: Uint16Array;
}

/**
 * The water in the notch behind the crest: a strip along the notch from `stream.from` to the crest,
 * level with the crest from `levelFrom` on and sinking to the notch's floor before that (so the
 * notch's walls close over its start: it wells up out of the rock). Drawn by the sheet shader as a
 * stream that flows to the crest. Its share of the length stops short of the shader's foot fade
 * (waterfall.ts SHEET.footFade): the water does not thin out where it goes over the edge.
 */
export function pourStream(s: PourSpec, f: PourFrame): PourStream {
  const st = s.stream;
  const rows = Math.max(2, Math.round(st.rows));
  const cols = 4;
  const crest = pourCrest(s);
  const n = (rows + 1) * (cols + 1);
  const positions = new Float32Array(n * 3);
  const uvs = new Float32Array(n * 2);
  const colors = new Float32Array(n * 3);
  const fall = new Float32Array(n * 4);
  let along = 0;
  let prev: [number, number] | null = null;
  const lengths: number[] = [];
  for (let j = 0; j <= rows; j++) {
    const o = st.from + ((crest.out - st.from) * j) / rows;
    const h = st.floor + (crest.level - st.floor) * smoothstep(st.from, st.levelFrom, o);
    if (prev) along += Math.hypot(o - prev[0], h - prev[1]);
    prev = [o, h];
    lengths.push(along);
    for (let i = 0; i <= cols; i++) {
      const k = j * (cols + 1) + i;
      const u = i / cols;
      const p = fromPour(f, [s.centre + (u - 0.5) * st.width, o, h]);
      positions.set(p, k * 3);
      uvs.set([u, j / rows], k * 2);
      colors.set([st.seed, st.flow, 0], k * 3);
    }
  }
  const total = Math.max(along, 1e-6);
  for (let j = 0; j <= rows; j++) {
    for (let i = 0; i <= cols; i++) {
      const k = j * (cols + 1) + i;
      fall.set([(i / cols - 0.5) * st.width, lengths[j], -(1 + 0.9 * (lengths[j] / total)), st.width], k * 4);
    }
  }
  const index = new Uint16Array(rows * cols * 6);
  let q = 0;
  for (let j = 0; j < rows; j++) {
    for (let i = 0; i < cols; i++) {
      const a = j * (cols + 1) + i;
      const b = a + 1;
      const c = a + cols + 1;
      const d = c + 1;
      // Facing up: the strip runs toward the crest (out of the cliff).
      index.set([a, c, b, b, c, d], q);
      q += 6;
    }
  }
  return { positions, uvs, colors, fall, index };
}

/** The pours whose core sheet is among `falls`, each with its frame. */
export function poursFor(falls: readonly Waterfall[], specs: readonly PourSpec[] = POURS): { spec: PourSpec; frame: PourFrame }[] {
  const out: { spec: PourSpec; frame: PourFrame }[] = [];
  for (const spec of specs) {
    const fall = falls.find((w) => w.name === spec.sheet);
    const frame = fall ? pourFrame(fall) : null;
    if (frame) out.push({ spec, frame });
  }
  return out;
}
