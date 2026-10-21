/**
 * Seamlessly tiling noise, generated at runtime (no image download): fractal value noise for the
 * cloud sea and the moon, and the ground and rock layers' fields (lib/sect/detail.ts): a smooth
 * patch field, a white-noise lattice for 3D value noise, and a cellular clump field. Each returns
 * bytes, row-major, `size` x `size` (one per texel, or four for RGBA).
 */

function hash2(x: number, y: number, seed: number): number {
  let h = (x * 374761393 + y * 668265263 + seed * 2147483647) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967295;
}

function smooth(t: number): number {
  return t * t * (3 - 2 * t);
}

function mod(a: number, n: number): number {
  return ((a % n) + n) % n;
}

/** Value noise at (x, y) in lattice units, wrapping every `period` cells. */
export function valueNoise(x: number, y: number, period: number, seed: number): number {
  const x0 = Math.floor(x);
  const y0 = Math.floor(y);
  const fx = smooth(x - x0);
  const fy = smooth(y - y0);
  const ax = mod(x0, period);
  const ay = mod(y0, period);
  const bx = mod(x0 + 1, period);
  const by = mod(y0 + 1, period);
  const v00 = hash2(ax, ay, seed);
  const v10 = hash2(bx, ay, seed);
  const v01 = hash2(ax, by, seed);
  const v11 = hash2(bx, by, seed);
  return (v00 * (1 - fx) + v10 * fx) * (1 - fy) + (v01 * (1 - fx) + v11 * fx) * fy;
}

export interface NoiseOptions {
  /** Lattice cells across the texture for the first octave. */
  basePeriod?: number;
  octaves?: number;
  /** Amplitude multiplier per octave. */
  gain?: number;
  seed?: number;
}

export function tilingNoise(size: number, opts: NoiseOptions = {}): Uint8Array {
  const base = Math.max(1, Math.round(opts.basePeriod ?? 4));
  const octaves = Math.max(1, Math.round(opts.octaves ?? 5));
  const gain = opts.gain ?? 0.5;
  const seed = opts.seed ?? 7;
  const out = new Float32Array(size * size);
  let lo = Infinity;
  let hi = -Infinity;
  for (let j = 0; j < size; j++) {
    for (let i = 0; i < size; i++) {
      let v = 0;
      let amp = 1;
      let period = base;
      for (let o = 0; o < octaves; o++) {
        v += amp * valueNoise((i / size) * period, (j / size) * period, period, seed + o * 101);
        amp *= gain;
        period *= 2;
      }
      out[j * size + i] = v;
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
  }
  const bytes = new Uint8Array(size * size);
  const span = hi - lo || 1;
  for (let k = 0; k < out.length; k++) bytes[k] = Math.round(((out[k] - lo) / span) * 255);
  return bytes;
}

/**
 * Ranks a field onto 0..1 and maps the rank through `curve` (identity: every value equally
 * common), as bytes. Order is kept (to 1 part in 65536 of the field's range), so the shapes stay;
 * values in one such step share their mean rank, so a flat area stays flat. With curve u^p the
 * mean is 1 / (p + 1). Linear time (a histogram, not a sort).
 */
export function rankBytes(field: ArrayLike<number>, curve: (u: number) => number = (u) => u): Uint8Array {
  const n = field.length;
  const bins = 65536;
  let lo = Infinity;
  let hi = -Infinity;
  for (let i = 0; i < n; i++) {
    if (field[i] < lo) lo = field[i];
    if (field[i] > hi) hi = field[i];
  }
  const scale = hi > lo ? (bins - 1) / (hi - lo) : 0;
  const bin = new Uint16Array(n);
  const count = new Uint32Array(bins);
  for (let i = 0; i < n; i++) {
    bin[i] = Math.round((field[i] - lo) * scale);
    count[bin[i]]++;
  }
  // Each bin's byte: the curve at the mean rank of its values.
  const byte = new Uint8Array(bins);
  let below = 0;
  for (let b = 0; b < bins; b++) {
    if (count[b] === 0) continue;
    const u = n > 1 ? (below + (count[b] - 1) / 2) / (n - 1) : 0.5;
    byte[b] = Math.round(Math.min(Math.max(curve(u), 0), 1) * 255);
    below += count[b];
  }
  const out = new Uint8Array(n);
  for (let i = 0; i < n; i++) out[i] = byte[bin[i]];
  return out;
}

/** White noise blurred with a Gaussian of `sigma` texels, wrapping: smooth, round blobs with no lattice. */
function blurredNoise(size: number, sigma: number, seed: number): Float32Array {
  const r = Math.max(1, Math.ceil(sigma * 3));
  const w = Array.from({ length: 2 * r + 1 }, (_, k) => Math.exp(-((k - r) ** 2) / (2 * sigma * sigma)));
  const a = new Float32Array(size * size);
  for (let k = 0; k < a.length; k++) a[k] = hash2(k % size, Math.floor(k / size), seed) - 0.5;
  const b = new Float32Array(size * size);
  for (let j = 0; j < size; j++) {
    for (let i = 0; i < size; i++) {
      let v = 0;
      for (let k = -r; k <= r; k++) v += a[j * size + mod(i + k, size)] * w[k + r];
      b[j * size + i] = v;
    }
  }
  for (let j = 0; j < size; j++) {
    for (let i = 0; i < size; i++) {
      let v = 0;
      for (let k = -r; k <= r; k++) v += b[mod(j + k, size) * size + i] * w[k + r];
      a[j * size + i] = v;
    }
  }
  return a;
}

/**
 * A smooth tiling field ranked to a uniform 0..1 distribution (mean 0.5): blobs about size / cells
 * texels across, with a quarter-strength finer layer for uneven edges.
 */
export function patchNoise(size: number, cells: number, seed: number): Uint8Array {
  const sigma = size / cells / 2.5;
  const a = blurredNoise(size, sigma, seed);
  const b = blurredNoise(size, sigma * 0.4, seed + 17);
  const sa = Math.sqrt(a.reduce((s, v) => s + v * v, 0) / a.length) || 1;
  const sb = Math.sqrt(b.reduce((s, v) => s + v * v, 0) / b.length) || 1;
  return rankBytes(a.map((v, k) => v / sa + (0.25 * b[k]) / sb));
}

export interface GroundNoiseOptions {
  /** Texels G is moved by against R (the slice step of the 3D value noise). */
  offset: readonly [number, number];
  /** Blobs across the texture of the smooth B and A fields. */
  cells: number;
  seed?: number;
}

/**
 * The ground and rock layers' RGBA noise. R: white noise, one value a texel; G: R `offset` texels
 * on (wrapping), so one bilinear read at lattice point (x + ox z, y + oy z) gives two slices of
 * 3D value noise (R at z, G at z + 1). B, A: two independent smooth fields (patchNoise: about
 * `cells` blobs across), each ranked to uniform 0..1.
 */
export function groundNoise(size: number, o: GroundNoiseOptions): Uint8Array {
  const seed = o.seed ?? 29;
  const [ox, oy] = o.offset;
  const b = patchNoise(size, o.cells, seed + 1);
  const a = patchNoise(size, o.cells, seed + 2);
  const out = new Uint8Array(size * size * 4);
  const white = (x: number, y: number) => Math.min(255, Math.floor(hash2(mod(x, size), mod(y, size), seed) * 256));
  for (let j = 0; j < size; j++) {
    for (let i = 0; i < size; i++) {
      const k = j * size + i;
      out[k * 4] = white(i, j);
      out[k * 4 + 1] = white(i + ox, j + oy);
      out[k * 4 + 2] = b[k];
      out[k * 4 + 3] = a[k];
    }
  }
  return out;
}

export interface ClumpOptions {
  /** Jittered cells across the tile (one clump each). */
  cells: number;
  /** Mean of the result (0..1): the bytes follow u^(1 / mean - 1), mostly high with narrow low gaps. */
  mean: number;
  seed?: number;
}

/**
 * A tiling cellular field of grass clumps: one clump per jittered cell (a 3 x 3 cell search), a
 * rounded dome highest at its point and falling to 0 at the borders with its neighbours, each clump
 * taller or shorter. The lookup is warped by a smooth field (about a third of a cell), so the
 * borders wander instead of running straight like cracks or paving. Ranked so its mean is `mean`, which mipmaps and
 * filtering keep: a shader that divides by that mean leaves the average brightness alone at any
 * distance.
 */
export function clumpField(size: number, o: ClumpOptions): Uint8Array {
  const n = Math.max(1, Math.round(o.cells));
  const seed = o.seed ?? 53;
  const px = new Float32Array(n * n);
  const py = new Float32Array(n * n);
  const ht = new Float32Array(n * n);
  for (let cy = 0; cy < n; cy++) {
    for (let cx = 0; cx < n; cx++) {
      const c = cy * n + cx;
      px[c] = cx + 0.075 + 0.85 * hash2(cx, cy, seed);
      py[c] = cy + 0.075 + 0.85 * hash2(cx, cy, seed + 1);
      ht[c] = 0.55 + 0.45 * hash2(cx, cy, seed + 2);
    }
  }
  // The warp: blobs of about 1.5 cells, +-0.35 cell (2 std), built at a quarter of the size and
  // read bilinearly (it is smooth).
  const ws = Math.max(4, size >> 2);
  const sigma = ws / Math.max(1, n / 1.5) / 2.5;
  const wx = blurredNoise(ws, sigma, seed + 3);
  const wy = blurredNoise(ws, sigma, seed + 4);
  let sq = 0;
  for (let k = 0; k < wx.length; k++) sq += wx[k] * wx[k] + wy[k] * wy[k];
  const amp = 0.35 / (2 * Math.sqrt(sq / (2 * wx.length)) || 1);
  const at = (f: Float32Array, u: number, v: number) => {
    const x0 = Math.floor(u);
    const y0 = Math.floor(v);
    const fx = u - x0;
    const fy = v - y0;
    const a = f[mod(y0, ws) * ws + mod(x0, ws)];
    const b = f[mod(y0, ws) * ws + mod(x0 + 1, ws)];
    const c = f[mod(y0 + 1, ws) * ws + mod(x0, ws)];
    const d = f[mod(y0 + 1, ws) * ws + mod(x0 + 1, ws)];
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy;
  };
  const raw = new Float32Array(size * size);
  for (let j = 0; j < size; j++) {
    for (let i = 0; i < size; i++) {
      const k = j * size + i;
      const u = ((i + 0.5) / size) * ws - 0.5;
      const v = ((j + 0.5) / size) * ws - 0.5;
      const x = ((i + 0.5) / size) * n + at(wx, u, v) * amp;
      const y = ((j + 0.5) / size) * n + at(wy, u, v) * amp;
      const gx = Math.floor(x);
      const gy = Math.floor(y);
      // Squared distances to the nearest and second nearest point.
      let f1 = Infinity;
      let f2 = Infinity;
      let h = 1;
      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          const c = mod(gy + dy, n) * n + mod(gx + dx, n);
          // The neighbour's point, moved by whole tiles so it sits next to this texel.
          const qx = px[c] + (gx + dx - mod(gx + dx, n));
          const qy = py[c] + (gy + dy - mod(gy + dy, n));
          const d = (qx - x) * (qx - x) + (qy - y) * (qy - y);
          if (d < f1) {
            f2 = f1;
            f1 = d;
            h = ht[c];
          } else if (d < f2) {
            f2 = d;
          }
        }
      }
      // A round dome on the nearest point (dark where no point is near, so the gaps are blobs,
      // not lines), split a little where two clumps meet (e: 0 at the point, 1 on the border).
      const d1 = Math.sqrt(f1);
      const e = (2 * d1) / (d1 + Math.sqrt(f2) || 1);
      raw[k] = h * (1 - Math.pow(Math.min(d1 / 0.75, 1), 1.5)) * (1 - 0.35 * e ** 4);
    }
  }
  const p = 1 / Math.min(Math.max(o.mean, 0.05), 0.95) - 1;
  return rankBytes(raw, (u) => Math.pow(u, p));
}
