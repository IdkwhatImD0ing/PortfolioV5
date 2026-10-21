/**
 * Grass along every grass edge on /sect, as pure data (no three.js): a long fringe hanging over each
 * cliff lip, a short one where a lawn meets a rock wall or runs onto bare rock, and small bushes
 * along the far rims, so no cap reads as a green lid with a crisp polygon outline at any distance.
 *
 * Input is the triangle soup experience/grass.tsx collects from a set's baked meshes (GroundSoup
 * and RockSoup, world space). The meshes arrive in pieces: each area is split into `.c<n>` chunk
 * nodes and two atlases (A0 near, A1 far), and gltfpack quantises every piece on its own grid. So
 * corners are first welded by position (EDGE.weldM); an open edge is one exactly one ground
 * triangle uses.
 *
 * Only open edges with rock behind them get grass. In the shipped areas the others are almost all
 * cut lines: the bake hands each range face to one area (or the backdrop), so an area's ground ends
 * where the next area's ground goes on, and each set is built on its own. The rest are lawn patches
 * stepping 0.15-0.45 m down onto more ground. Paths and plazas lie on top of the ground, which runs
 * on under them, so they make no open edge at all. A rock-backed edge is a rim when rock falls away
 * from it into a drop (steep rock at once, or a drop of a metre or two within a few metres), else a
 * plain edge (a wall foot, or grass running onto gentle rock).
 *
 * Output is GrassInstances (KIND.fringe, KIND.rim), rooted EDGE.inset inside the ground triangle
 * with the atlas UV there, so grass.tsx colours them from the bake exactly like its tufts. Every
 * hash is of a world position: the same meshes always give the same grass.
 */
import { hash01 } from "./fx";
import {
  camIndex,
  KIND,
  leanByte,
  nearestCam,
  nearSheet,
  rimDrawDist,
  sizeByte,
  underPond,
  yawByte,
  type GrassInstances,
  type GroundSoup,
  type Pond,
  type RockSoup,
  type SheetIndex,
} from "./grass";

export const EDGE = {
  /** Corners closer than this are one vertex (m): joins the chunk pieces, both atlases and gltfpack's grids. */
  weldM: 0.08,
  /** Instances root this far inside the ground triangle (m), less in a thin one. */
  inset: 0.25,
  /** The rock under a rim is steeper than this (normal y; 0.6 is about 53 degrees). */
  rimNy: 0.6,
  /**
   * ...or it falls away gentler but the surface probeM out is at least dropM lower (or missing), a
   * drop steeper than the 37 degrees grass grows on: the bake's decimation often leaves a gentle
   * first row of rock before the cliff (m).
   */
  lip: { probeM: 3, dropM: 2 },
  /**
   * Rim fallback when no rock triangle shares the edge (gltfpack can move borders): steep rock
   * within searchM outward whose top is at most dropM over the edge and which falls below it (m).
   */
  dropM: 0.2,
  searchM: 1.0,
  /** ...unless ground goes on this far past the edge, within this height of it (m): a lawn step by a boulder. */
  stepM: 0.3,
  /** Ground steeper than this (normal y) gets no fringe: tufts stop at 0.82, the fringe a little past. */
  minNy: 0.5,
  /** Fringe per metre of edge by distance to the camera path (m); none farther out. */
  spacing: [
    { to: 50, perM: 3 },
    { to: 150, perM: 1.5 },
  ] as const,
  /** Fringe height (m): long over a rim, short elsewhere. */
  fringe: { size: [0.5, 1.0] as const, edgeSize: [0.3, 0.5] as const },
  /**
   * Lean from upright (degrees): out over the drop on rims, a little out elsewhere, and a little
   * away from the rock at a wall foot.
   */
  rimLean: [45, 70] as const,
  edgeLean: [10, 25] as const,
  /** Each lean turns up to this far either side of straight out (degrees). */
  yawJitter: 20,
  /**
   * Small bushes on rims 100-400 m from the path: one every everyM, with a `gap` share of the rim
   * left bare in patches about gapM across, so they cluster. Each is drawn out to its own distance
   * (grass.ts rimDrawDist: size x 300 m / 1.5 m, at most 450 m); one that could never show is left out.
   */
  rimClump: { from: 100, to: 400, everyM: 5, gap: 0.4, gapM: 14, size: [1.0, 1.8] as const, lean: 10 },
};

/** GrassEdges classes. */
export const EDGE_RIM = 1;
export const EDGE_PLAIN = 2;

// ---------------------------------------------------------------------------------------------
// Small maths

function clamp(x: number, lo: number, hi: number): number {
  return x < lo ? lo : x > hi ? hi : x;
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/** 0..1 hash of a world position (to 1 cm) and a salt: the same point always draws the same numbers. */
function posHash(x: number, y: number, z: number, salt: number): number {
  const ix = Math.round(x * 100) | 0;
  const iy = Math.round(y * 100) | 0;
  const iz = Math.round(z * 100) | 0;
  return hash01(Math.imul(ix, 73856093) ^ Math.imul(iy, 19349663) ^ Math.imul(iz, 83492791), salt);
}

/** Smooth 2D value noise, 0..1, one cell per unit. */
function valueNoise(x: number, z: number, salt: number): number {
  const ix = Math.floor(x);
  const iz = Math.floor(z);
  const fx = x - ix;
  const fz = z - iz;
  const u = fx * fx * (3 - 2 * fx);
  const v = fz * fz * (3 - 2 * fz);
  const at = (i: number, j: number) => hash01(Math.imul(i, 73856093) ^ Math.imul(j, 19349663), salt);
  return lerp(lerp(at(ix, iz), at(ix + 1, iz), u), lerp(at(ix, iz + 1), at(ix + 1, iz + 1), u), v);
}

let gapCutCache: { gap: number; cut: number } | null = null;

/** The noise level below which a share `gap` of the rim stays bare (its quantile, sampled once). */
function gapCut(gap: number): number {
  if (gapCutCache?.gap === gap) return gapCutCache.cut;
  const n = 64;
  const s = new Float64Array(n * n);
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) s[i * n + j] = valueNoise(i * 0.618 + 0.13, j * 0.737 + 0.29, 11);
  s.sort();
  const cut = s[clamp(Math.round(gap * (s.length - 1)), 0, s.length - 1)];
  gapCutCache = { gap, cut };
  return cut;
}

/**
 * The world direction (x, z) a lean yaw (radians) points: three's rotation.y convention, yaw 0 is
 * +z and pi/2 is +x. grass.tsx must turn a fringe's lean by the same rule.
 */
export function leanDir(yaw: number): [number, number] {
  return [Math.sin(yaw), Math.cos(yaw)];
}

// ---------------------------------------------------------------------------------------------
// Weld

interface Weld {
  /** Welded vertex of each input point. */
  id: Int32Array;
  count: number;
  /** The welded vertex within `tol` of a point (the nearest), or -1. */
  find(x: number, y: number, z: number): number;
}

/** A power of two at least twice n: an open-addressing table that stays at most half full. */
function tableSize(n: number): number {
  let size = 16;
  while (size < n * 2) size <<= 1;
  return size;
}

/** Loop iterations between yields of the step generators (about a millisecond of work). */
const SLICE = 8192;

/**
 * Greedy weld by position: each point joins the nearest earlier vertex within `tol` (inclusive), or
 * starts one. Cells are at least 2 tol wide, so the box of `tol` around a point touches at most two
 * per axis. A soup repeats each mesh vertex about six times, bit for bit: those repeats are folded
 * first through an exact table and take the vertex their first copy found, without the search.
 */
function* weldSteps(pos: Float32Array, tol: number): Generator<void, Weld> {
  const nPts = Math.floor(pos.length / 3);
  const cell = Math.max(2 * tol, 0.4);
  const reach = (tol + 1e-4) ** 2;
  // Both tables hash a cell so neighbouring cells sit near each other in memory (a soup runs along
  // its mesh): an exact copy lands in its first copy's cell.
  const cellHash = (ix: number, iy: number, iz: number, mask: number) => (ix + (iz << 9) + Math.imul(iy, 40503)) & mask;

  // Exact copies: `exact` holds the first point seen at each position; `first` maps every point to
  // the unique position it repeats.
  const bits = new Int32Array(pos.buffer, pos.byteOffset, nPts * 3);
  const exMask = tableSize(nPts) - 1;
  const exact = new Int32Array(exMask + 1).fill(-1);
  const first = new Int32Array(nPts);
  const uniq: number[] = [];
  for (let i = 0; i < nPts; i++) {
    if (i % SLICE === SLICE - 1) yield;
    const bx = bits[i * 3], by = bits[i * 3 + 1], bz = bits[i * 3 + 2];
    let h = cellHash(Math.floor(pos[i * 3] / cell), Math.floor(pos[i * 3 + 1] / cell), Math.floor(pos[i * 3 + 2] / cell), exMask);
    let q = exact[h];
    while (q !== -1 && (bits[q * 3] !== bx || bits[q * 3 + 1] !== by || bits[q * 3 + 2] !== bz)) {
      h = (h + 1) & exMask;
      q = exact[h];
    }
    if (q === -1) {
      exact[h] = i;
      first[i] = uniq.length;
      uniq.push(i);
    } else first[i] = first[q];
  }

  // Tolerant clustering of the unique positions.
  const nU = uniq.length;
  const mask = tableSize(nU) - 1;
  const kx = new Int32Array(mask + 1);
  const ky = new Int32Array(mask + 1);
  const kz = new Int32Array(mask + 1);
  const head = new Int32Array(mask + 1).fill(-1);
  const vx = new Float32Array(nU);
  const vy = new Float32Array(nU);
  const vz = new Float32Array(nU);
  const next = new Int32Array(nU);
  const repOf = new Int32Array(nU);
  let count = 0;
  const slot = (ix: number, iy: number, iz: number): number => {
    let h = cellHash(ix, iy, iz, mask);
    while (head[h] !== -1 && (kx[h] !== ix || ky[h] !== iy || kz[h] !== iz)) h = (h + 1) & mask;
    return h;
  };
  const find = (x: number, y: number, z: number): number => {
    let best = -1;
    let bd = reach;
    const x0 = Math.floor((x - tol) / cell), x1 = Math.floor((x + tol) / cell);
    const y0 = Math.floor((y - tol) / cell), y1 = Math.floor((y + tol) / cell);
    const z0 = Math.floor((z - tol) / cell), z1 = Math.floor((z + tol) / cell);
    for (let ix = x0; ix <= x1; ix++) {
      for (let iy = y0; iy <= y1; iy++) {
        for (let iz = z0; iz <= z1; iz++) {
          for (let r = head[slot(ix, iy, iz)]; r !== -1; r = next[r]) {
            const d = (vx[r] - x) ** 2 + (vy[r] - y) ** 2 + (vz[r] - z) ** 2;
            if (d <= bd) {
              bd = d;
              best = r;
            }
          }
        }
      }
    }
    return best;
  };
  for (let u = 0; u < nU; u++) {
    if (u % SLICE === SLICE - 1) yield;
    const i = uniq[u];
    const x = pos[i * 3], y = pos[i * 3 + 1], z = pos[i * 3 + 2];
    let r = find(x, y, z);
    if (r < 0) {
      r = count++;
      vx[r] = x;
      vy[r] = y;
      vz[r] = z;
      const ix = Math.floor(x / cell), iy = Math.floor(y / cell), iz = Math.floor(z / cell);
      const h = slot(ix, iy, iz);
      kx[h] = ix;
      ky[h] = iy;
      kz[h] = iz;
      next[r] = head[h];
      head[h] = r;
    }
    repOf[u] = r;
  }
  const id = new Int32Array(nPts);
  for (let i = 0; i < nPts; i++) id[i] = repOf[first[i]];
  return { id, count, find };
}

// ---------------------------------------------------------------------------------------------
// Grass edges

export interface EdgeStats {
  /** Metres of edge used by exactly one ground triangle after the weld. */
  openM: number;
  /** ...on ground steeper than EDGE.minNy: not used. */
  steepM: number;
  /** ...with no rock behind them (cut lines between areas, lawn steps): not used. */
  unbackedM: number;
  /** Rims found by a shared steep rock edge, by the drop past gentler rock, and by the nearby-rock fallback. */
  rimSharedM: number;
  rimLipM: number;
  rimNearM: number;
  /** Plain edges: wall feet and grass running onto gentle rock. */
  edgeM: number;
}

/** The grass edges of a ground soup that get grass: rims and plain edges, in input order. */
export interface GrassEdges {
  count: number;
  /** The ground triangle each edge belongs to. */
  tri: Uint32Array;
  /** Its two corners (0-2) on the edge, 2 per edge, start first (the lower corner in x, then z). */
  corner: Uint8Array;
  /** EDGE_RIM or EDGE_PLAIN. */
  cls: Uint8Array;
  len: Float32Array;
  /** Midpoints, 3 per edge. */
  mid: Float32Array;
  /** Unit horizontal lean direction (x, z), 2 per edge: out of the lawn, or away from a wall. */
  lean: Float32Array;
  stats: EdgeStats;
}

/** Unit normal y of the triangle at float offset o (9 floats each), 0 when degenerate. */
function normalY(p: Float32Array, o: number): number {
  const ux = p[o + 3] - p[o], uy = p[o + 4] - p[o + 1], uz = p[o + 5] - p[o + 2];
  const vx = p[o + 6] - p[o], vy = p[o + 7] - p[o + 1], vz = p[o + 8] - p[o + 2];
  const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
  const l = Math.hypot(nx, ny, nz);
  return l > 1e-12 ? ny / l : 0;
}

/**
 * Distance in xz from (x, z) to the triangle at offset o, and the offset to its nearest point
 * (0 inside).
 */
function xzDistance(p: Float32Array, o: number, x: number, z: number): [number, number, number] {
  const ax = p[o], az = p[o + 2];
  const bx = p[o + 3] - ax, bz = p[o + 5] - az;
  const cx = p[o + 6] - ax, cz = p[o + 8] - az;
  const det = bx * cz - bz * cx;
  if (Math.abs(det) > 1e-9) {
    const px = x - ax, pz = z - az;
    const u = (px * cz - pz * cx) / det, v = (bx * pz - bz * px) / det;
    if (u >= 0 && v >= 0 && u + v <= 1) return [0, 0, 0];
  }
  let best: [number, number, number] = [Infinity, 0, 0];
  for (let k = 0; k < 3; k++) {
    const a = o + k * 3, b = o + ((k + 1) % 3) * 3;
    const ex = p[b] - p[a], ez = p[b + 2] - p[a + 2];
    const l2 = ex * ex + ez * ez;
    const t = l2 > 1e-12 ? clamp(((x - p[a]) * ex + (z - p[a + 2]) * ez) / l2, 0, 1) : 0;
    const dx = p[a] + ex * t - x, dz = p[a + 2] + ez * t - z;
    const d = Math.hypot(dx, dz);
    if (d < best[0]) best = [d, dx, dz];
  }
  return best;
}

/** Height of the triangle at offset o over (x, z), or NaN when (x, z) is outside it. */
function heightAt(p: Float32Array, o: number, x: number, z: number): number {
  const ax = p[o], az = p[o + 2];
  const bx = p[o + 3] - ax, bz = p[o + 5] - az;
  const cx = p[o + 6] - ax, cz = p[o + 8] - az;
  const det = bx * cz - bz * cx;
  if (Math.abs(det) < 1e-9) return NaN;
  const px = x - ax, pz = z - az;
  const u = (px * cz - pz * cx) / det, v = (bx * pz - bz * px) / det;
  if (u < -1e-4 || v < -1e-4 || u + v > 1 + 1e-4) return NaN;
  return p[o + 1] + u * (p[o + 4] - p[o + 1]) + v * (p[o + 7] - p[o + 1]);
}

/**
 * Dense xz grid over a set of points: each cell lists the points in it. A triangle then visits the
 * cells its padded footprint covers, so each point is tested only against triangles near it.
 */
function pointGrid(xs: Float32Array, zs: Float32Array) {
  const n = xs.length;
  let x0 = Infinity, x1 = -Infinity, z0 = Infinity, z1 = -Infinity;
  for (let i = 0; i < n; i++) {
    x0 = Math.min(x0, xs[i]);
    x1 = Math.max(x1, xs[i]);
    z0 = Math.min(z0, zs[i]);
    z1 = Math.max(z1, zs[i]);
  }
  const cell = Math.max(3, (x1 - x0) / 1024, (z1 - z0) / 1024);
  const nx = Math.max(1, Math.floor((x1 - x0) / cell) + 1);
  const nz = Math.max(1, Math.floor((z1 - z0) / cell) + 1);
  const head = new Int32Array(n > 0 ? nx * nz : 0).fill(-1);
  const next = new Int32Array(n);
  for (let i = 0; i < n; i++) {
    const c = Math.floor((zs[i] - z0) / cell) * nx + Math.floor((xs[i] - x0) / cell);
    next[i] = head[c];
    head[c] = i;
  }
  /** Calls fn with every point whose cell overlaps [ax, bx] x [az, bz]. */
  return (ax: number, az: number, bx: number, bz: number, fn: (i: number) => void) => {
    if (n === 0 || bx < x0 || ax > x1 || bz < z0 || az > z1) return;
    const i0 = Math.max(0, Math.floor((ax - x0) / cell)), i1 = Math.min(nx - 1, Math.floor((bx - x0) / cell));
    const j0 = Math.max(0, Math.floor((az - z0) / cell)), j1 = Math.min(nz - 1, Math.floor((bz - z0) / cell));
    for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) for (let q = head[j * nx + i]; q !== -1; q = next[q]) fn(q);
  };
}

/**
 * Marks each probe point (x, z, with a height window lo-hi) over which some triangle of a soup has
 * its surface inside the window. `tris` limits the triangles tried (all when null); `own` is a
 * triangle each point ignores (its edge's own).
 */
function covered(
  p: Float32Array,
  tris: readonly number[] | null,
  x: Float32Array,
  z: Float32Array,
  lo: Float32Array,
  hi: Float32Array,
  hit: Uint8Array,
  own: Uint32Array | null = null,
): void {
  if (x.length === 0) return;
  const each = pointGrid(x, z);
  const n = tris ? tris.length : Math.floor(p.length / 9);
  for (let i = 0; i < n; i++) {
    const t = tris ? tris[i] : i;
    const o = t * 9;
    const x0 = Math.min(p[o], p[o + 3], p[o + 6]), x1 = Math.max(p[o], p[o + 3], p[o + 6]);
    const z0 = Math.min(p[o + 2], p[o + 5], p[o + 8]), z1 = Math.max(p[o + 2], p[o + 5], p[o + 8]);
    each(x0, z0, x1, z1, (q) => {
      if (hit[q] || own?.[q] === t) return;
      const h = heightAt(p, o, x[q], z[q]);
      if (h >= lo[q] && h <= hi[q]) hit[q] = 1;
    });
  }
}

/** A box test: whether the triangle at float offset o of a soup touches something. */
type BoxTest = (p: Float32Array, o: number) => boolean;

/**
 * 4 m xz columns under some boxes (x0, y0, z0, x1, y1, z1 each, those in `list`), each with the
 * height range its boxes span; the test says whether a triangle's box touches one. Most rock is
 * nowhere near an open edge (and a cliff's lower rows sit far below its rim), so this skips it
 * before any lookup.
 */
function columnMask(boxes: Float32Array, list: readonly number[]): BoxTest {
  if (list.length === 0) return () => false;
  const M = 4;
  let ox = Infinity, oz = Infinity, ex = -Infinity, ez = -Infinity;
  for (const k of list) {
    ox = Math.min(ox, boxes[k * 6]);
    oz = Math.min(oz, boxes[k * 6 + 2]);
    ex = Math.max(ex, boxes[k * 6 + 3]);
    ez = Math.max(ez, boxes[k * 6 + 5]);
  }
  const nx = Math.floor((ex - ox) / M) + 1;
  const nz = Math.floor((ez - oz) / M) + 1;
  const lo = new Float32Array(nx * nz).fill(Infinity);
  const hi = new Float32Array(nx * nz).fill(-Infinity);
  for (const k of list) {
    const i0 = Math.floor((boxes[k * 6] - ox) / M), i1 = Math.floor((boxes[k * 6 + 3] - ox) / M);
    const j0 = Math.floor((boxes[k * 6 + 2] - oz) / M), j1 = Math.floor((boxes[k * 6 + 5] - oz) / M);
    for (let j = j0; j <= j1; j++) {
      for (let i = i0; i <= i1; i++) {
        lo[j * nx + i] = Math.min(lo[j * nx + i], boxes[k * 6 + 1]);
        hi[j * nx + i] = Math.max(hi[j * nx + i], boxes[k * 6 + 4]);
      }
    }
  }
  return (p, o) => {
    const y0 = Math.min(p[o + 1], p[o + 4], p[o + 7]), y1 = Math.max(p[o + 1], p[o + 4], p[o + 7]);
    const i0 = Math.max(0, Math.floor((Math.min(p[o], p[o + 3], p[o + 6]) - ox) / M));
    const i1 = Math.min(nx - 1, Math.floor((Math.max(p[o], p[o + 3], p[o + 6]) - ox) / M));
    const j0 = Math.max(0, Math.floor((Math.min(p[o + 2], p[o + 5], p[o + 8]) - oz) / M));
    const j1 = Math.min(nz - 1, Math.floor((Math.max(p[o + 2], p[o + 5], p[o + 8]) - oz) / M));
    for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) if (y1 >= lo[j * nx + i] && y0 <= hi[j * nx + i]) return true;
    return false;
  };
}

/**
 * Finds and classifies the grass edges of a ground soup against its rock, as a generator that
 * yields about every millisecond of work, so the page can spread it over frames (grass.tsx
 * `sliced`). Pure and deterministic. The result is kept for the soup pair, so fringeInstances and
 * rimClumps run on it at once afterwards.
 */
export function* grassEdgeSteps(ground: GroundSoup, rock: RockSoup): Generator<void, GrassEdges> {
  const hit = edgeCache.get(ground);
  if (hit?.rock === rock) return hit.edges;
  const G = ground.pos;
  const R = rock.pos;
  const nT = Math.floor(G.length / 9);
  const nR = Math.floor(R.length / 9);
  const w = yield* weldSteps(G.subarray(0, nT * 9), EDGE.weldM);
  const rep = w.id;
  const stats: EdgeStats = { openM: 0, steepM: 0, unbackedM: 0, rimSharedM: 0, rimLipM: 0, rimNearM: 0, edgeM: 0 };

  // Triangles with two corners welded into one are slivers under 8 cm: they would count an edge twice.
  const live = new Uint8Array(nT);
  for (let t = 0; t < nT; t++) {
    const a = rep[t * 3], b = rep[t * 3 + 1], c = rep[t * 3 + 2];
    live[t] = a !== b && b !== c && a !== c ? 1 : 0;
  }

  // Every edge filed under its lower welded vertex (CSR): `other` is the upper one, `ent` the corner.
  const off = new Int32Array(w.count + 1);
  for (let t = 0; t < nT; t++) {
    if (!live[t]) continue;
    for (let k = 0; k < 3; k++) off[Math.min(rep[t * 3 + k], rep[t * 3 + ((k + 1) % 3)]) + 1]++;
  }
  for (let i = 0; i < w.count; i++) off[i + 1] += off[i];
  const fill = off.slice(0, w.count);
  const other = new Int32Array(off[w.count]);
  const ent = new Int32Array(off[w.count]);
  for (let t = 0; t < nT; t++) {
    if (!live[t]) continue;
    for (let k = 0; k < 3; k++) {
      const i = rep[t * 3 + k], j = rep[t * 3 + ((k + 1) % 3)];
      const s = fill[Math.min(i, j)]++;
      other[s] = Math.max(i, j);
      ent[s] = t * 3 + k;
    }
  }
  // Open edges: no other entry under the same vertex pair. `open` holds the open-edge id per entry.
  const open = new Int32Array(other.length).fill(-1);
  let nOpen = 0;
  for (let v = 0; v < w.count; v++) {
    for (let s = off[v]; s < off[v + 1]; s++) {
      let n = 0;
      for (let q = off[v]; q < off[v + 1]; q++) if (other[q] === other[s]) n++;
      if (n === 1) open[s] = nOpen++;
    }
  }
  const openEnt = new Int32Array(nOpen);
  for (let s = 0; s < other.length; s++) if (open[s] >= 0) openEnt[open[s]] = ent[s];
  const findOpen = (i: number, j: number): number => {
    const lo = Math.min(i, j), hi = Math.max(i, j);
    for (let s = off[lo]; s < off[lo + 1]; s++) if (other[s] === hi) return open[s];
    return -1;
  };
  yield;

  // Geometry of each open edge: start/end corners, length, midpoint, direction out of the lawn.
  const tri = new Uint32Array(nOpen);
  const corner = new Uint8Array(nOpen * 2);
  const len = new Float32Array(nOpen);
  const mid = new Float32Array(nOpen * 3);
  const out = new Float32Array(nOpen * 2);
  const flat = new Uint8Array(nOpen);
  for (let e = 0; e < nOpen; e++) {
    const t = Math.floor(openEnt[e] / 3);
    const k0 = openEnt[e] % 3, k1 = (k0 + 1) % 3, k2 = (k0 + 2) % 3;
    const o = t * 9;
    const a = o + k0 * 3, b = o + k1 * 3, c = o + k2 * 3;
    // Start at the lower corner (x, then z), so an edge reads the same from either piece.
    const swap = G[b] < G[a] || (G[b] === G[a] && G[b + 2] < G[a + 2]);
    tri[e] = t;
    corner[e * 2] = swap ? k1 : k0;
    corner[e * 2 + 1] = swap ? k0 : k1;
    const ex = G[b] - G[a], ey = G[b + 1] - G[a + 1], ez = G[b + 2] - G[a + 2];
    const l = Math.hypot(ex, ey, ez);
    len[e] = l;
    mid[e * 3] = (G[a] + G[b]) / 2;
    mid[e * 3 + 1] = (G[a + 1] + G[b + 1]) / 2;
    mid[e * 3 + 2] = (G[a + 2] + G[b + 2]) / 2;
    // Out of the lawn: away from the far corner, square to the edge, flattened to xz.
    const cx = G[c] - G[a], cy = G[c + 1] - G[a + 1], cz = G[c + 2] - G[a + 2];
    const tau = l > 1e-9 ? (cx * ex + cy * ey + cz * ez) / (l * l) : 0;
    const ox = -(cx - tau * ex), oz = -(cz - tau * ez);
    const ol = Math.hypot(ox, oz);
    out[e * 2] = ol > 1e-9 ? ox / ol : 0;
    out[e * 2 + 1] = ol > 1e-9 ? oz / ol : 0;
    flat[e] = normalY(G, o) >= EDGE.minNy && ol > 1e-9 ? 1 : 0;
    stats.openM += l;
  }
  yield;

  // Each flat open edge's box: padded by the weld for rock that shares it, and by the fallback's
  // reach for edges no rock shares. Rock touching none is skipped.
  const edgeBoxes = (pad: number) => {
    const boxes = new Float32Array(nOpen * 6);
    for (let e = 0; e < nOpen; e++) {
      const o = tri[e] * 9, a = o + corner[e * 2] * 3, b = o + corner[e * 2 + 1] * 3;
      for (let k = 0; k < 3; k++) {
        boxes[e * 6 + k] = Math.min(G[a + k], G[b + k]) - pad;
        boxes[e * 6 + 3 + k] = Math.max(G[a + k], G[b + k]) + pad;
      }
    }
    return boxes;
  };
  const flatList: number[] = [];
  for (let e = 0; e < nOpen; e++) if (flat[e]) flatList.push(e);
  const touchesEdge = columnMask(edgeBoxes(EDGE.weldM), flatList);
  const nearEdge = columnMask(edgeBoxes(Math.max(EDGE.searchM, EDGE.lip.probeM)), flatList);
  const cand: number[] = [];
  for (let r = 0; r < nR; r++) {
    if (r % SLICE === SLICE - 1) yield;
    if (nearEdge(R, r * 9)) cand.push(r);
  }

  // Rock triangles that share an open edge. A steep one falling away makes a rim; a steep one rising
  // is a wall the grass leans away from.
  const backed = new Uint8Array(nOpen);
  const falls = new Uint8Array(nOpen);
  const rim = new Uint8Array(nOpen);
  const wall = new Uint8Array(nOpen);
  const rv = [0, 0, 0];
  for (let c = 0; c < cand.length; c++) {
    if (c % (SLICE / 4) === SLICE / 4 - 1) yield;
    const o = cand[c] * 9;
    if (!touchesEdge(R, o)) continue;
    for (let k = 0; k < 3; k++) rv[k] = w.find(R[o + k * 3], R[o + k * 3 + 1], R[o + k * 3 + 2]);
    if ((rv[0] < 0 ? 1 : 0) + (rv[1] < 0 ? 1 : 0) + (rv[2] < 0 ? 1 : 0) > 1) continue;
    const steep = normalY(R, o) < EDGE.rimNy;
    for (let k = 0; k < 3; k++) {
      const i = rv[k], j = rv[(k + 1) % 3];
      if (i < 0 || j < 0 || i === j) continue;
      const e = findOpen(i, j);
      if (e < 0) continue;
      backed[e] = 1;
      const down = R[o + ((k + 2) % 3) * 3 + 1] < mid[e * 3 + 1];
      if (down) falls[e] = 1;
      if (steep && down) rim[e] = 1;
      else if (steep) wall[e] = 1;
    }
  }

  // Gentler rock falling away is a rim too when the surface lip.probeM out (rock or ground) lies at
  // least lip.dropM below the edge, or is missing (an island's underside curving in).
  const lipList: number[] = [];
  for (let e = 0; e < nOpen; e++) if (flat[e] && falls[e] && !rim[e] && !wall[e]) lipList.push(e);
  const { probeM, dropM: lipDrop } = EDGE.lip;
  const lx = Float32Array.from(lipList, (e) => mid[e * 3] + out[e * 2] * probeM);
  const lz = Float32Array.from(lipList, (e) => mid[e * 3 + 2] + out[e * 2 + 1] * probeM);
  const llo = Float32Array.from(lipList, (e) => mid[e * 3 + 1] - lipDrop);
  const lhi = Float32Array.from(lipList, (e) => mid[e * 3 + 1] + 0.5);
  const shelf = new Uint8Array(lipList.length);
  covered(R, cand, lx, lz, llo, lhi, shelf);
  yield;
  covered(G, null, lx, lz, llo, lhi, shelf);
  yield;
  const lip = new Uint8Array(nOpen);
  lipList.forEach((e, q) => {
    lip[e] = shelf[q] ? 0 : 1;
  });

  // Edges no rock shares: steep rock just outside, falling from about the edge's height, is a rim.
  const ask: number[] = [];
  for (let e = 0; e < nOpen; e++) if (flat[e] && !backed[e]) ask.push(e);
  const qx = Float32Array.from(ask, (e) => mid[e * 3]);
  const qz = Float32Array.from(ask, (e) => mid[e * 3 + 2]);
  const each = pointGrid(qx, qz);
  const near = new Uint8Array(nOpen);
  const { searchM, dropM } = EDGE;
  const touchesAsk = columnMask(edgeBoxes(searchM), ask);
  for (let c = 0; c < (ask.length > 0 ? cand.length : 0); c++) {
    if (c % (SLICE / 2) === SLICE / 2 - 1) yield;
    const o = cand[c] * 9;
    if (!touchesAsk(R, o) || normalY(R, o) >= EDGE.rimNy) continue;
    const top = Math.max(R[o + 1], R[o + 4], R[o + 7]);
    const bottom = Math.min(R[o + 1], R[o + 4], R[o + 7]);
    const x0 = Math.min(R[o], R[o + 3], R[o + 6]) - searchM, x1 = Math.max(R[o], R[o + 3], R[o + 6]) + searchM;
    const z0 = Math.min(R[o + 2], R[o + 5], R[o + 8]) - searchM, z1 = Math.max(R[o + 2], R[o + 5], R[o + 8]) + searchM;
    each(x0, z0, x1, z1, (q) => {
      const e = ask[q];
      const y = mid[e * 3 + 1];
      if (near[e] || top > y + dropM || top < y - searchM || bottom > y - dropM) return;
      // Outward, or within a weld of the edge (each piece's own grid can put a wall a hair inside).
      const [d, dx, dz] = xzDistance(R, o, mid[e * 3], mid[e * 3 + 2]);
      if (d <= searchM && (d <= EDGE.weldM || dx * out[e * 2] + dz * out[e * 2 + 1] >= 0)) near[e] = 1;
    });
  }
  // ...but ground going on just past one means a lawn step beside a boulder, not a lip.
  const nearList = ask.filter((e) => near[e] === 1);
  const step = new Uint8Array(nearList.length);
  covered(
    G,
    null,
    Float32Array.from(nearList, (e) => mid[e * 3] + out[e * 2] * EDGE.stepM),
    Float32Array.from(nearList, (e) => mid[e * 3 + 2] + out[e * 2 + 1] * EDGE.stepM),
    Float32Array.from(nearList, (e) => mid[e * 3 + 1] - EDGE.stepM),
    Float32Array.from(nearList, (e) => mid[e * 3 + 1] + EDGE.stepM),
    step,
    Uint32Array.from(nearList, (e) => tri[e]),
  );
  nearList.forEach((e, q) => {
    if (step[q]) near[e] = 0;
  });
  yield;

  // Keep rims and plain edges, in input order.
  const keep: number[] = [];
  for (let e = 0; e < nOpen; e++) {
    if (!flat[e]) stats.steepM += len[e];
    else if (!backed[e] && !near[e]) stats.unbackedM += len[e];
    else keep.push(e);
  }
  const res: GrassEdges = {
    count: keep.length,
    tri: new Uint32Array(keep.length),
    corner: new Uint8Array(keep.length * 2),
    cls: new Uint8Array(keep.length),
    len: new Float32Array(keep.length),
    mid: new Float32Array(keep.length * 3),
    lean: new Float32Array(keep.length * 2),
    stats,
  };
  keep.forEach((e, i) => {
    res.tri[i] = tri[e];
    res.corner.set(corner.subarray(e * 2, e * 2 + 2), i * 2);
    res.len[i] = len[e];
    res.mid.set(mid.subarray(e * 3, e * 3 + 3), i * 3);
    const isRim = rim[e] === 1 || lip[e] === 1 || (!backed[e] && near[e] === 1);
    const away = !isRim && wall[e] === 1 ? -1 : 1;
    res.lean[i * 2] = out[e * 2] * away;
    res.lean[i * 2 + 1] = out[e * 2 + 1] * away;
    res.cls[i] = isRim ? EDGE_RIM : EDGE_PLAIN;
    if (rim[e]) stats.rimSharedM += len[e];
    else if (lip[e]) stats.rimLipM += len[e];
    else if (isRim) stats.rimNearM += len[e];
    else stats.edgeM += len[e];
  });
  edgeCache.set(ground, { rock, edges: res });
  return res;
}

/** The grass edges of each ground soup already worked out, with the rock they were found against. */
const edgeCache = new WeakMap<GroundSoup, { rock: RockSoup; edges: GrassEdges }>();

/** grassEdgeSteps run to the end (at once, when the edges of this soup pair are not kept yet). */
export function grassEdges(ground: GroundSoup, rock: RockSoup): GrassEdges {
  const it = grassEdgeSteps(ground, rock);
  for (;;) {
    const r = it.next();
    if (r.done) return r.value;
  }
}

// ---------------------------------------------------------------------------------------------
// Instances

export interface EdgeOptions {
  /** Scales how many instances each metre of edge gets (1 by default). */
  density?: number;
  /** Water the tufts also avoid (grass.ts underPond, nearSheet). */
  ponds?: readonly Pond[];
  sheets?: SheetIndex | null;
}

/** Instances being placed: the edge, where along it (0-1 from its start), and the look. */
interface Slot {
  e: number;
  t: number;
  size: number;
  /** Degrees. */
  lean: number;
  /** 0-1 hashes: the yaw jitter, and the seed byte. */
  jitter: number;
  seed: number;
}

/**
 * Packs slots into GrassInstances, rooting each one `inset` inside its ground triangle. Slots under
 * a pond or beside a water sheet are dropped, as tufts are.
 */
function pack(ground: GroundSoup, edges: GrassEdges, slots: readonly Slot[], kind: number, opts: EdgeOptions): GrassInstances {
  const G = ground.pos;
  const U = ground.uv;
  const ponds = opts.ponds ?? [];
  const sheets = opts.sheets ?? null;
  const n = slots.length;
  const res: GrassInstances = {
    count: 0,
    pos: new Float32Array(n * 3),
    uv: new Uint16Array(n * 2),
    a: new Uint8Array(n * 4),
    b: new Uint8Array(n * 4),
    atlas: new Uint8Array(n),
  };
  let i = 0;
  for (const s of slots) {
    const t = edges.tri[s.e];
    const ka = edges.corner[s.e * 2], kb = edges.corner[s.e * 2 + 1], kc = 3 - ka - kb;
    const o = t * 9;
    const a = o + ka * 3, b = o + kb * 3, c = o + kc * 3;
    // Barycentric (alpha, beta, gamma) of the point s.t along A->B moved `inset` toward C, square
    // to the edge: gamma is the inset over the triangle's height, capped so alpha and beta stay
    // positive (near a corner the triangle is too thin for the full inset).
    const ex = G[b] - G[a], ey = G[b + 1] - G[a + 1], ez = G[b + 2] - G[a + 2];
    const cx = G[c] - G[a], cy = G[c + 1] - G[a + 1], cz = G[c + 2] - G[a + 2];
    const l2 = ex * ex + ey * ey + ez * ez;
    const tau = l2 > 1e-12 ? (cx * ex + cy * ey + cz * ez) / l2 : 0;
    const h = Math.hypot(cx - tau * ex, cy - tau * ey, cz - tau * ez);
    let gamma = h > 1e-9 ? Math.min(EDGE.inset / h, 0.9) : 0;
    if (tau > 1e-6) gamma = Math.min(gamma, (0.9 * s.t) / tau);
    if (tau < 1 - 1e-6) gamma = Math.min(gamma, (0.9 * (1 - s.t)) / (1 - tau));
    const beta = s.t - gamma * tau;
    const alpha = 1 - beta - gamma;
    const x = G[a] * alpha + G[b] * beta + G[c] * gamma;
    const y = G[a + 1] * alpha + G[b + 1] * beta + G[c + 1] * gamma;
    const z = G[a + 2] * alpha + G[b + 2] * beta + G[c + 2] * gamma;
    if (underPond(ponds, x, y, z) || nearSheet(sheets, x, y, z)) continue;
    res.pos[i * 3] = x;
    res.pos[i * 3 + 1] = y;
    res.pos[i * 3 + 2] = z;
    const ua = t * 6 + ka * 2, ub = t * 6 + kb * 2, uc = t * 6 + kc * 2;
    for (let k = 0; k < 2; k++) {
      const u = U[ua + k] * alpha + U[ub + k] * beta + U[uc + k] * gamma;
      res.uv[i * 2 + k] = Math.round(clamp(u, 0, 1) * 65535);
    }
    res.atlas[i] = ground.atlas[t];
    const yaw = Math.atan2(edges.lean[s.e * 2], edges.lean[s.e * 2 + 1]) + ((s.jitter * 2 - 1) * EDGE.yawJitter * Math.PI) / 180;
    // Rank 0: a fringe shows wherever tufts are drawn at all, a rim clump out to its rimDrawDist.
    res.a[i * 4] = 0;
    res.a[i * 4 + 1] = Math.min(255, Math.floor(s.seed * 256));
    res.a[i * 4 + 2] = sizeByte(s.size);
    res.a[i * 4 + 3] = kind;
    res.b[i * 4] = leanByte(s.lean);
    res.b[i * 4 + 1] = yawByte(yaw);
    i++;
  }
  res.count = i;
  if (i < n) {
    res.pos = res.pos.slice(0, i * 3);
    res.uv = res.uv.slice(0, i * 2);
    res.a = res.a.slice(0, i * 4);
    res.b = res.b.slice(0, i * 4);
    res.atlas = res.atlas.slice(0, i);
  }
  return res;
}

/** Instances on an edge: len x perM, rounded up or down by a hash so short edges add up right. */
function slotsOn(len: number, perM: number, h: number): number {
  return Math.floor(len * perM + h);
}

/** Where slot k of n sits along an edge (0-1): evenly spaced, jittered by a hash. */
function slotT(k: number, n: number, h: number): number {
  return (k + 0.5 + (h - 0.5) * 0.7) / n;
}

/**
 * The fringe along every grass edge within reach of the camera path: EDGE.spacing per metre by
 * distance to the nearest of `cams` (the set's need range and its hold, 3 floats each), long and
 * leaning out over rims, short and nearly upright elsewhere. KIND.fringe, rank 0.
 */
export function fringeInstances(ground: GroundSoup, rock: RockSoup, cams: Float32Array, opts: EdgeOptions = {}): GrassInstances {
  const edges = grassEdges(ground, rock);
  const ix = camIndex(cams);
  const density = opts.density ?? 1;
  const reach = EDGE.spacing[EDGE.spacing.length - 1].to;
  const slots: Slot[] = [];
  for (let e = 0; e < edges.count; e++) {
    const mx = edges.mid[e * 3], my = edges.mid[e * 3 + 1], mz = edges.mid[e * 3 + 2];
    const d = nearestCam(ix, mx, my, mz, reach);
    const band = EDGE.spacing.find((s) => d < s.to);
    if (!band) continue;
    const n = slotsOn(edges.len[e], band.perM * density, posHash(mx, my, mz, 1));
    const isRim = edges.cls[e] === EDGE_RIM;
    const size = isRim ? EDGE.fringe.size : EDGE.fringe.edgeSize;
    const lean = isRim ? EDGE.rimLean : EDGE.edgeLean;
    for (let k = 0; k < n; k++) {
      const salt = 16 + k * 8;
      slots.push({
        e,
        t: slotT(k, n, posHash(mx, my, mz, salt)),
        size: lerp(size[0], size[1], posHash(mx, my, mz, salt + 1)),
        lean: lerp(lean[0], lean[1], posHash(mx, my, mz, salt + 2)),
        jitter: posHash(mx, my, mz, salt + 3),
        seed: posHash(mx, my, mz, salt + 4),
      });
    }
  }
  return pack(ground, edges, slots, KIND.fringe, opts);
}

/**
 * Small bushes along the far rims (EDGE.rimClump): rim edges `from`-`to` metres from the camera
 * path, one every everyM, in clusters. A clump farther from the path than its own draw distance
 * (it could never show) is left out. KIND.rim, rank 0.
 */
export function rimClumps(ground: GroundSoup, rock: RockSoup, cams: Float32Array, opts: EdgeOptions = {}): GrassInstances {
  const edges = grassEdges(ground, rock);
  const C = EDGE.rimClump;
  const ix = camIndex(cams);
  const density = opts.density ?? 1;
  const cut = gapCut(C.gap);
  const G = ground.pos;
  const slots: Slot[] = [];
  for (let e = 0; e < edges.count; e++) {
    if (edges.cls[e] !== EDGE_RIM) continue;
    const mx = edges.mid[e * 3], my = edges.mid[e * 3 + 1], mz = edges.mid[e * 3 + 2];
    const d = nearestCam(ix, mx, my, mz, C.to);
    if (!(d >= C.from && d < C.to)) continue;
    const n = slotsOn(edges.len[e], density / C.everyM, posHash(mx, my, mz, 2));
    const o = edges.tri[e] * 9;
    const pa = o + edges.corner[e * 2] * 3, pb = o + edges.corner[e * 2 + 1] * 3;
    for (let k = 0; k < n; k++) {
      const salt = 512 + k * 8;
      const t = slotT(k, n, posHash(mx, my, mz, salt));
      if (valueNoise(lerp(G[pa], G[pb], t) / C.gapM, lerp(G[pa + 2], G[pb + 2], t) / C.gapM, 11) < cut) continue;
      const size = lerp(C.size[0], C.size[1], posHash(mx, my, mz, salt + 1));
      if (d >= rimDrawDist(size)) continue;
      slots.push({ e, t, size, lean: C.lean, jitter: posHash(mx, my, mz, salt + 3), seed: posHash(mx, my, mz, salt + 4) });
    }
  }
  return pack(ground, edges, slots, KIND.rim, opts);
}
