/**
 * Repairs the bake's vertex colours. The backdrop's far islands and the reduced proxies of each
 * area carry their light as vertex colours, and the bake left a share of vertices pure black (no
 * sample landed on them): a pier of the formation's aqueduct drew black from the steles, and the
 * black vertices streaked island undersides. Real light is never exactly 0 here (the sky fills every
 * shadow), so an exact black is treated as missing and filled from its neighbours. Pure functions.
 *
 * It runs on the main thread while a set is prepared, over the backdrop's 1.2 M vertex-coloured
 * vertices at the opening, so it only visits what it must: meshes without a black vertex are told
 * apart from the raw attribute before anything is copied (anyMissingColor), each spreading pass
 * walks only the triangles that still touch an unset vertex, and the fallback colour is a histogram
 * median instead of a sort (on a phone the old full pass took 1.4 s, its sort alone 350 ms).
 */

/** A channel at or below this (8-bit 0 is 0.0) counts as unset. */
export const MISSING_COLOR = 1.5 / 255;

export interface FillOptions {
  /** Rings of neighbours a known colour may spread across. */
  passes?: number;
  /** Brightness of a filled vertex on a face that looks down (an island underside), 0..1. */
  undersideShade?: number;
}

/** Buckets of the brightness histogram the fallback colour's median is read from. */
const MEDIAN_BINS = 1024;

function isMissing(c: ArrayLike<number>, v: number): boolean {
  return c[v * 3] <= MISSING_COLOR && c[v * 3 + 1] <= MISSING_COLOR && c[v * 3 + 2] <= MISSING_COLOR;
}

/**
 * True when some vertex of a raw colour attribute is unset (all three channels at or below
 * MISSING_COLOR), read straight from its array: `count` vertices `stride` values apart from
 * `offset`, a channel being `array value / scale` (1 for floats, 255 for normalised bytes, 65535
 * for normalised shorts).
 */
export function anyMissingColor(array: ArrayLike<number>, count: number, stride: number, offset: number, scale: number): boolean {
  const lim = MISSING_COLOR * scale;
  for (let v = 0, i = offset; v < count; v++, i += stride) {
    if (array[i] <= lim && array[i + 1] <= lim && array[i + 2] <= lim) return true;
  }
  return false;
}

/**
 * Fills unset (pure black) vertex colours in place: each takes the mean of its set neighbours,
 * spreading up to `passes` rings; vertices with no set colour within reach (a whole piece the bake
 * missed) take the mesh's median colour, darker where their faces look down. Returns how many
 * vertices changed. `colors` is rgb per vertex in 0..1; `positions` xyz per vertex, or a function
 * that makes them (only called when some piece needs the fallback colour).
 */
export function fillMissingColors(
  colors: Float32Array,
  positions: ArrayLike<number> | (() => ArrayLike<number>),
  index: ArrayLike<number> | null,
  opts: FillOptions = {},
): number {
  return repairColors(colors, positions, index, opts).length;
}

/** fillMissingColors, returning the vertices it filled (in no particular order). */
export function repairColors(
  colors: Float32Array,
  positions: ArrayLike<number> | (() => ArrayLike<number>),
  index: ArrayLike<number> | null,
  opts: FillOptions = {},
): Uint32Array {
  const n = Math.floor(colors.length / 3);
  const passes = opts.passes ?? 6;
  const shade = opts.undersideShade ?? 0.5;
  const tri = index ? index.length : n;
  const at = (i: number) => (index ? index[i] : i);
  const known = new Uint8Array(n);
  // Each unset vertex's slot in the per-pass sums (-1: set from the start).
  const slot = new Int32Array(n).fill(-1);
  let missing = 0;
  for (let v = 0; v < n; v++) {
    if (isMissing(colors, v)) slot[v] = missing++;
    else known[v] = 1;
  }
  if (missing === 0 || missing === n) return new Uint32Array(0);
  const unset = new Uint32Array(missing);
  for (let v = 0; v < n; v++) if (slot[v] >= 0) unset[slot[v]] = v;

  // The triangles that touch an unset vertex: the only ones a pass needs (most of a mesh is set).
  let active = new Uint32Array(Math.min(Math.floor(tri / 3), missing * 8) || 1);
  let na = 0;
  for (let t = 0; t + 2 < tri; t += 3) {
    if (known[at(t)] && known[at(t + 1)] && known[at(t + 2)]) continue;
    if (na === active.length) {
      const grown = new Uint32Array(active.length * 2);
      grown.set(active);
      active = grown;
    }
    active[na++] = t;
  }

  const sum = new Float32Array(missing * 3);
  const cnt = new Uint16Array(missing);
  let left = missing;
  /** Adds the colour of `u` (when set) to unset `v`'s sum. */
  const take = (v: number, u: number) => {
    if (!known[u]) return;
    const s = slot[v];
    if (cnt[s] === 65535) return;
    sum[s * 3] += colors[u * 3];
    sum[s * 3 + 1] += colors[u * 3 + 1];
    sum[s * 3 + 2] += colors[u * 3 + 2];
    cnt[s]++;
  };
  for (let p = 0; p < passes && left > 0; p++) {
    sum.fill(0);
    cnt.fill(0);
    let kept = 0;
    for (let i = 0; i < na; i++) {
      const t = active[i];
      const a = at(t);
      const b = at(t + 1);
      const c = at(t + 2);
      const k = known[a] + known[b] + known[c];
      // Fully set now: no later pass needs it.
      if (k === 3) continue;
      active[kept++] = t;
      if (k === 0) continue;
      if (!known[a]) {
        take(a, b);
        take(a, c);
      }
      if (!known[b]) {
        take(b, a);
        take(b, c);
      }
      if (!known[c]) {
        take(c, a);
        take(c, b);
      }
    }
    na = kept;
    // Every vertex of this ring is set at once (as if the pass had read the colours from before it).
    let changed = 0;
    for (let i = 0; i < left; ) {
      const v = unset[i];
      const s = slot[v];
      if (cnt[s] === 0) {
        i++;
        continue;
      }
      colors[v * 3] = sum[s * 3] / cnt[s];
      colors[v * 3 + 1] = sum[s * 3 + 1] / cnt[s];
      colors[v * 3 + 2] = sum[s * 3 + 2] / cnt[s];
      known[v] = 1;
      changed++;
      // Move it past the still-unset ones (swap with the last of them).
      left--;
      unset[i] = unset[left];
      unset[left] = v;
    }
    if (changed === 0) break;
  }
  // `unset` now lists the still-unset vertices first (`left` of them), then the filled ones.
  if (left === 0) return unset;

  // Pieces the spreading never reached: the median colour (by brightness) of the set vertices, read
  // from a brightness histogram, as the mean of the vertices in the median's bucket.
  const lum = (v: number) => 0.2126 * colors[v * 3] + 0.7152 * colors[v * 3 + 1] + 0.0722 * colors[v * 3 + 2];
  let top = 0;
  for (let v = 0; v < n; v++) if (known[v]) top = Math.max(top, lum(v));
  const width = top > 0 ? top / MEDIAN_BINS : 1;
  const bin = (v: number) => Math.min(MEDIAN_BINS - 1, Math.floor(lum(v) / width));
  const hist = new Uint32Array(MEDIAN_BINS);
  let setCount = 0;
  for (let v = 0; v < n; v++) {
    if (!known[v]) continue;
    hist[bin(v)]++;
    setCount++;
  }
  let mid = 0;
  for (let acc = 0, want = Math.floor(setCount / 2); mid < MEDIAN_BINS - 1; mid++) {
    acc += hist[mid];
    if (acc > want) break;
  }
  const median = [0, 0, 0];
  for (let v = 0; v < n; v++) {
    if (!known[v] || bin(v) !== mid) continue;
    median[0] += colors[v * 3];
    median[1] += colors[v * 3 + 1];
    median[2] += colors[v * 3 + 2];
  }
  const inMid = Math.max(1, hist[mid]);
  median[0] /= inMid;
  median[1] /= inMid;
  median[2] /= inMid;
  // Which way each unset vertex's faces look (summed face normals, y only): every triangle that
  // holds one is still in `active`.
  const pos = typeof positions === "function" ? positions() : positions;
  const ny = new Float32Array(left);
  for (let i = 0; i < left; i++) slot[unset[i]] = i;
  const face = (v: number, y: number) => {
    if (!known[v]) ny[slot[v]] += y;
  };
  for (let i = 0; i < na; i++) {
    const t = active[i];
    const a = at(t);
    const b = at(t + 1);
    const c = at(t + 2);
    if (known[a] && known[b] && known[c]) continue;
    const ux = pos[b * 3] - pos[a * 3];
    const uy = pos[b * 3 + 1] - pos[a * 3 + 1];
    const uz = pos[b * 3 + 2] - pos[a * 3 + 2];
    const vx = pos[c * 3] - pos[a * 3];
    const vy = pos[c * 3 + 1] - pos[a * 3 + 1];
    const vz = pos[c * 3 + 2] - pos[a * 3 + 2];
    const nx = uy * vz - uz * vy;
    const nyy = uz * vx - ux * vz;
    const nz = ux * vy - uy * vx;
    const y = nyy / (Math.hypot(nx, nyy, nz) || 1);
    face(a, y);
    face(b, y);
    face(c, y);
  }
  for (let i = 0; i < left; i++) {
    const v = unset[i];
    const k = ny[i] < -0.35 ? shade : 1;
    colors[v * 3] = median[0] * k;
    colors[v * 3 + 1] = median[1] * k;
    colors[v * 3 + 2] = median[2] * k;
  }
  return unset;
}
