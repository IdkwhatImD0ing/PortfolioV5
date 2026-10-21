#!/usr/bin/env node
/**
 * Scan textures for the nature pilot (runs on this PC; uses the sharp already in the client's node_modules, so
 * no install; see loadSharp).
 *
 *     node E:/Github/PortfolioV5/blender/xianxia-sect/tools/prep_textures.mjs <assets dir> <detail.webp>
 *     e.g. node .../tools/prep_textures.mjs E:/Github/PortfolioV5/blender/xianxia-sect/assets
 *              E:/Github/PortfolioV5/blender/xianxia-sect/out/web/full/site/detail.webp
 *
 * The downloaded scans are only decoded as pixels (the paths come in as arguments; nothing in the assets
 * folder is run or opened by anything else).
 *
 * 1. <assets>/web/<name>.jpg: the CC0 scans at 2048 px (longest side), JPEG q90, each < 5 MB, for the Blender
 *    materials (materials.py loads them from <project>/assets/web; rblender.py uploads that folder). Colour maps
 *    stay sRGB; displacement and masks are written as 1-channel greyscale (load them as Non-Color).
 * 2. <detail.webp>: the page's tiling detail texture, 1024 x 1024 RGB, near-lossless WebP, seamless.
 *    R = marble_cliff_06 (one 8.14 m tile), G = leafy_grass (2.0 m), B = Moss001 (1.5 m). Each channel is the
 *    high-passed luminance of the whole tile: log2 of linear luminance minus its Gaussian blur (sigma 12 cm in
 *    that tile's metres, wrap-around), mapped to 0.5 + k * hp with k set so the std is 0.12, clamped. Log
 *    luminance because the page multiplies the baked colour by exp2((d - 0.5) * gain): the scan's contrast then
 *    comes back as a ratio, the same in light and shadow. Near-lossless because the three channels are
 *    unrelated: lossy WebP stores colour as YUV 4:2:0, which blurs and mixes them (measured RMS error 14 levels
 *    against a std of 31); near-lossless q40 changes each channel by at most 4 levels (0.5% brightness at the
 *    page's gain) for half the bytes of lossless (1.2 vs 2.35 MB).
 *
 * 3. <assets>/web/twig_card.png: the near pines' needle-card texture (bake_trees.py TWIG_TEX: Blender reads its G
 *    as the cards' cut-out for shadow rays and sprite renders; the tree GLBs embed it as the 'twig' card texture,
 *    extras cardAlpha 'twig'). TWIG_PX square, 8-bit RGB PNG, TWIG_GRID x TWIG_GRID cells; each cell is one card
 *    variant: a dense brush of 3-4 photographed pine twigs (Poly Haven pine_tree_01, CC0) radiating from the
 *    cell's bottom centre (the card's root, v = 0 in Blender's UVs) toward its top (the tip), clear of the other
 *    edges. G = coverage (three.js reads an alpha map's G), R = the twigs' luminance detail: log2 of linear
 *    luminance minus its coverage-weighted Gaussian blur (TWIG_SIGMA of a cell), scaled to TWIG_DETAIL_STD
 *    and stored as a ratio, R = 0.5 * 2^hp (0.5 = neutral: the page multiplies the baked colour by about 2 R;
 *    uncovered texels are exactly neutral, so filtering never darkens the card edges), B = 0. Lossless PNG:
 *    the packer keeps R and G apart (tools/sect_pack.py: never greyscale, never chroma-subsampled).
 *        node prep_textures.mjs <assets dir> --twig-only     builds only this one
 *
 * Every resize is wrap-aware (the tile is padded with its own opposite edges, resized by an exact integer
 * factor, then cropped), so the outputs stay seamless. Prints sizes and the detail texture's per-channel stats.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

/** sharp without an install: $SECT_SHARP (a sharp package folder) if set, else the newest sharp in the client's
 * pnpm store (next and @gltf-transform bring it in), else the cached npx @gltf-transform/cli the packer runs. */
function loadSharp() {
  const req = createRequire(import.meta.url);
  if (process.env.SECT_SHARP) return req(process.env.SECT_SHARP);
  const ls = (d) => { try { return fs.readdirSync(d); } catch { return []; } };
  const ver = (d) => d.match(/^sharp@(\d+)\.(\d+)\.(\d+)/).slice(1).map(Number);
  const newer = (a, b) => { const x = ver(a), y = ver(b); return (y[0] - x[0]) || (y[1] - x[1]) || (y[2] - x[2]); };
  const store = fileURLToPath(new URL('../../../client/node_modules/.pnpm/', import.meta.url));
  const npx = [path.join(process.env.LOCALAPPDATA || '', 'npm-cache', '_npx'), path.join(os.homedir(), '.npm', '_npx')];
  const tries = [
    ...ls(store).filter((d) => /^sharp@\d+\.\d+\.\d+/.test(d)).sort(newer)
      .map((d) => path.join(store, d, 'node_modules', 'sharp')),
    ...npx.flatMap((b) => ls(b).map((d) => path.join(b, d, 'node_modules', 'sharp'))),
  ].filter((p) => fs.existsSync(path.join(p, 'package.json')));
  let err = null;
  for (const p of tries) {
    try { return req(p); } catch (e) { err = e; }    // e.g. a native build for another platform: try the next
  }
  throw new Error(`sharp not found (tried ${tries.length ? tries.join(', ') : `${store} and the npx cache`}`
    + `${err ? `; last error: ${err.message}` : ''}). Run pnpm install in the client, or set SECT_SHARP to a sharp `
    + 'package folder.');
}
const sharp = loadSharp();

const JPG_PX = 2048;
const JPG_QUALITY = 90;
const JPG_MAX_BYTES = 5e6;                 // rblender.py uploads files under 5 MB only
// [output name, source under <assets>, 'colour' (sRGB) | 'grey' (Non-Color, 1 channel)]
const JPGS = [
  ['marble_cliff_06_diff.jpg', 'polyhaven/marble_cliff_06/marble_cliff_06_diff_4k.jpg', 'colour'],   // 8.14 m tile
  ['marble_cliff_06_disp.jpg', 'polyhaven/marble_cliff_06/marble_cliff_06_disp_4k.jpg', 'grey'],
  ['rock063_color.jpg', 'ambientcg/Rock063/Rock063_4K-JPG_Color.jpg', 'colour'],                     // 4.0 x 2.0 m
  ['rock063_disp.jpg', 'ambientcg/Rock063/Rock063_4K-JPG_Displacement.jpg', 'grey'],
  ['leafy_grass_diff.jpg', 'polyhaven/leafy_grass/leafy_grass_diff_4k.jpg', 'colour'],               // 2.0 m
  ['sparse_grass_diff.jpg', 'polyhaven/sparse_grass/sparse_grass_diff_4k.jpg', 'colour'],            // 2.0 m
  ['sparse_grass_mask.jpg', 'polyhaven/sparse_grass/sparse_grass_mask_4k.jpg', 'grey'],
  ['grass_ground_diff.jpg', 'polyhaven/grass_ground/grass_ground_diff_4k.jpg', 'colour'],            // 2.51 m
  ['moss001_color.jpg', 'ambientcg/Moss001/Moss001_4K-JPG_Color.jpg', 'colour'],                     // ~1.5 m
];

const DETAIL_PX = 1024;
const DETAIL_SIGMA_M = 0.12;               // high-pass blur, metres
const DETAIL_STD = 0.12;                   // target std of each channel (0..1)
const LOG_EPS = 0.004;                     // log2(Y + eps): keeps black crevices finite
const DETAIL_WEBP = { nearLossless: true, quality: 40, effort: 6 };
// channel order R, G, B; tile sizes must match the client's DETAIL_TILE_M
const DETAIL = [
  { ch: 'R', src: 'polyhaven/marble_cliff_06/marble_cliff_06_diff_4k.jpg', tileM: 8.14 },
  { ch: 'G', src: 'polyhaven/leafy_grass/leafy_grass_diff_4k.jpg', tileM: 2.0 },
  { ch: 'B', src: 'ambientcg/Moss001/Moss001_4K-JPG_Color.jpg', tileM: 1.5 },
];

const PAD_OUT = 16;                        // wrap padding in output pixels (Lanczos3 needs 3 x the shrink factor)

/** RGB pixels of a tileable image resized to w x h, keeping it seamless. {data, width, height, channels: 3} */
async function wrapResize(file, w, h) {
  const m = await sharp(file).metadata();
  const f = m.width / w;
  if (!Number.isInteger(f) || m.height / h !== f) {
    throw new Error(`${file}: ${m.width}x${m.height} -> ${w}x${h} is not one integer shrink factor`);
  }
  const pad = PAD_OUT * f;
  const ext = await sharp(file).removeAlpha().toColourspace('srgb')
    .extend({ top: pad, bottom: pad, left: pad, right: pad, extendWith: 'repeat' })
    .raw().toBuffer({ resolveWithObject: true });
  const out = await sharp(ext.data, { raw: { width: ext.info.width, height: ext.info.height, channels: 3 } })
    .resize(w + 2 * PAD_OUT, h + 2 * PAD_OUT, { kernel: 'lanczos3', fit: 'fill' })
    .extract({ left: PAD_OUT, top: PAD_OUT, width: w, height: h })
    .raw().toBuffer({ resolveWithObject: true });
  return { data: out.data, width: out.info.width, height: out.info.height, channels: out.info.channels };
}

/** Mean |difference| across the wrap seam over the mean |difference| of neighbouring columns / rows inside
 * (about 1 for a seamless tile; channel 0). */
function seamRatio(px, w, h, c) {
  let seam = 0, inner = 0;
  for (let y = 0; y < h; y++) {
    const r = y * w * c;
    seam += Math.abs(px[r + (w - 1) * c] - px[r]);
    inner += Math.abs(px[r + (w >> 1) * c] - px[r + ((w >> 1) - 1) * c]);
  }
  for (let x = 0; x < w; x++) {
    seam += Math.abs(px[((h - 1) * w + x) * c] - px[x * c]);
    inner += Math.abs(px[((h >> 1) * w + x) * c] - px[(((h >> 1) - 1) * w + x) * c]);
  }
  return seam / Math.max(inner, 1e-9);
}

function writeAtomic(file, buf) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file + '.part', buf);
  fs.renameSync(file + '.part', file);
}

async function makeJpgs(assets) {
  const outDir = path.join(assets, 'web');
  for (const [name, rel, kind] of JPGS) {
    const src = path.join(assets, rel);
    const m = await sharp(src).metadata();
    const s = JPG_PX / Math.max(m.width, m.height);
    const img = await wrapResize(src, Math.round(m.width * s), Math.round(m.height * s));
    let q = JPG_QUALITY, buf;
    for (;;) {
      let p = sharp(img.data, { raw: { width: img.width, height: img.height, channels: 3 } });
      if (kind === 'grey') p = p.toColourspace('b-w');
      buf = await p.jpeg({ quality: q }).toBuffer();
      if (buf.length < JPG_MAX_BYTES || q <= 70) break;
      q -= 4;
    }
    if (buf.length >= JPG_MAX_BYTES) throw new Error(`${name}: ${buf.length} bytes even at q${q}`);
    writeAtomic(path.join(outDir, name), buf);
    const om = await sharp(buf).metadata();
    console.log(`${name.padEnd(24)} ${om.width}x${om.height} ${om.channels} ch q${q} ${(buf.length / 1e6).toFixed(2)} MB  `
      + `seam ratio ${seamRatio(img.data, img.width, img.height, 3).toFixed(2)}  <- ${rel}`);
  }
}

/** Separable Gaussian blur with wrap-around edges (the tile repeated in both directions). */
function blurWrap(src, w, h, sigma) {
  const r = Math.min(Math.ceil(3.5 * sigma), Math.floor((Math.min(w, h) - 1) / 2));
  const k = new Float64Array(2 * r + 1);
  let ks = 0;
  for (let i = -r; i <= r; i++) ks += (k[i + r] = Math.exp(-0.5 * (i / sigma) ** 2));
  for (let i = 0; i < k.length; i++) k[i] /= ks;
  const tmp = new Float32Array(w * h), out = new Float32Array(w * h);
  const line = new Float64Array(Math.max(w, h) + 2 * r);
  for (let y = 0; y < h; y++) {
    for (let i = 0; i < w + 2 * r; i++) line[i] = src[y * w + (((i - r) % w) + w) % w];
    for (let x = 0; x < w; x++) {
      let s = 0;
      for (let j = 0; j < k.length; j++) s += k[j] * line[x + j];
      tmp[y * w + x] = s;
    }
  }
  for (let x = 0; x < w; x++) {
    for (let i = 0; i < h + 2 * r; i++) line[i] = tmp[((((i - r) % h) + h) % h) * w + x];
    for (let y = 0; y < h; y++) {
      let s = 0;
      for (let j = 0; j < k.length; j++) s += k[j] * line[y + j];
      out[y * w + x] = s;
    }
  }
  return out;
}

const LIN = Float64Array.from({ length: 256 }, (_, v) => {
  const c = v / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
});

/** One detail channel (0..255) from a tile: high-passed log luminance with std DETAIL_STD. */
async function detailChannel(file, tileM) {
  const n = DETAIL_PX;
  const img = await wrapResize(file, n, n);
  const L = new Float32Array(n * n);
  for (let i = 0; i < n * n; i++) {
    const p = i * 3;
    const y = 0.2126 * LIN[img.data[p]] + 0.7152 * LIN[img.data[p + 1]] + 0.0722 * LIN[img.data[p + 2]];
    L[i] = Math.log2(y + LOG_EPS);
  }
  const sigma = DETAIL_SIGMA_M / tileM * n;
  const B = blurWrap(L, n, n, sigma);
  let s2 = 0;
  for (let i = 0; i < n * n; i++) { L[i] -= B[i]; s2 += L[i] * L[i]; }
  const k = DETAIL_STD / Math.sqrt(s2 / (n * n));
  const out = new Uint8Array(n * n);
  let clipped = 0;
  for (let i = 0; i < n * n; i++) {
    const v = Math.round((0.5 + k * L[i]) * 255);
    if (v < 0 || v > 255) clipped++;
    out[i] = Math.max(0, Math.min(255, v));
  }
  return { px: out, sigma, k, clipped: clipped / (n * n) };
}

function channelStats(data, c, ch, n) {
  let s = 0, s2 = 0;
  for (let i = 0; i < n; i++) { const v = data[i * c + ch] / 255; s += v; s2 += v * v; }
  const mean = s / n;
  return { mean, std: Math.sqrt(Math.max(0, s2 / n - mean * mean)) };
}

async function makeDetail(assets, outFile) {
  const n = DETAIL_PX;
  const rgb = Buffer.alloc(n * n * 3);
  for (let c = 0; c < 3; c++) {
    const d = DETAIL[c];
    const r = await detailChannel(path.join(assets, d.src), d.tileM);
    for (let i = 0; i < n * n; i++) rgb[i * 3 + c] = r.px[i];
    console.log(`detail ${d.ch}: ${d.src} (${d.tileM} m tile) sigma ${r.sigma.toFixed(1)} px, k ${r.k.toFixed(3)}, `
      + `clipped ${(100 * r.clipped).toFixed(2)}%`);
  }
  const buf = await sharp(rgb, { raw: { width: n, height: n, channels: 3 } }).webp(DETAIL_WEBP).toBuffer();
  writeAtomic(outFile, buf);
  // stats of what the page will decode
  const dec = await sharp(buf).raw().toBuffer({ resolveWithObject: true });
  const { width: w, height: h, channels: cc } = dec.info;
  console.log(`detail.webp ${w}x${h} ${cc} ch ${(buf.length / 1e6).toFixed(2)} MB -> ${outFile}`);
  for (let c = 0; c < 3; c++) {
    const st = channelStats(dec.data, cc, c, w * h);
    let seam = 0, inner = 0;
    for (let y = 0; y < h; y++) {
      seam += Math.abs(dec.data[(y * w + w - 1) * cc + c] - dec.data[y * w * cc + c]);
      inner += Math.abs(dec.data[(y * w + (w >> 1)) * cc + c] - dec.data[(y * w + (w >> 1) - 1) * cc + c]);
    }
    let err = 0;
    for (let i = 0; i < w * h; i++) err = Math.max(err, Math.abs(dec.data[i * cc + c] - rgb[i * 3 + c]));
    console.log(`  ${'RGB'[c]}: mean ${st.mean.toFixed(4)} std ${st.std.toFixed(4)}  seam ratio ${(seam / inner).toFixed(2)}  `
      + `max WebP error ${err} levels`);
  }
}

// ---- twig card texture (3.) ---------------------------------------------------------------------------------

const TWIG_PX = 1024;                      // output side; TWIG_GRID x TWIG_GRID cells (bake_trees.py TWIG_GRID)
const TWIG_GRID = 2;
const TWIG_SS = 2;                         // supersampling (box-filtered down)
const TWIG_ROOT_Y = 0.03;                  // root height in a cell (cell units; the stem below fades out)
const TWIG_BORDER = 0.03;                  // cell edges kept clear (no cut needles at a card's edge)
const TWIG_SIGMA = 0.05;                   // detail high-pass blur, in cells (the bake resolves ~1/4 card)
const TWIG_DETAIL_STD = 0.32;              // std of the high-passed log2 luminance over covered texels
const TWIG_DIFF = 'polyhaven/pine_tree_01/textures/pine_tree_01_twig_diff_2k.jpg';
const TWIG_ALPHA = 'polyhaven/pine_tree_01/textures/pine_tree_01_twig_alpha_2k.png';
// The two whole twigs on the pine_tree_01 twig sheet (2048 px coordinates, measured from its alpha): a seed pixel
// on the stem (its connected cut-out is the twig; the sheet's other islands are masked off), the stem's base and
// the far end of the shoot. `anchor`: the share of the base -> tip length cut off below the card root (bare stem).
const TWIG_SPRITES = {
  A: { seed: [271, 879], base: [271, 904], tip: [212, 90], anchor: 0.12 },     // upright shoot
  B: { seed: [1397, 947], base: [1334, 973], tip: [1917, 789], anchor: 0.03 }, // sideways shoot
};
// Card variants (one per cell, row-major from the bottom-left cell = Blender UV (0, 0)): twigs drawn back to front,
// [sprite, angle from the card axis (deg, + toward u = 1), length (cell units, root to tip), mirrored].
const TWIG_CELLS = [
  [['B', -30, 0.62, true], ['B', 31, 0.6, false], ['A', 0, 0.94, false]],
  [['A', -26, 0.7, false], ['A', 27, 0.66, true], ['B', 4, 0.9, false]],
  [['B', 0, 0.48, false], ['A', -13, 0.9, false], ['A', 16, 0.84, true]],
  [['A', -31, 0.62, false], ['A', 29, 0.62, true], ['B', 9, 0.52, true], ['A', 0, 0.92, true]],
];

/** One twig sprite from the sheet: premultiplied linear RGB + alpha of its own connected cut-out only. */
function twigSprite(diff, alpha, W, H, s) {
  const n = W * H;
  const inC = new Uint8Array(n);
  const st = [s.seed[1] * W + s.seed[0]];
  if (alpha[st[0]] < 128) throw new Error(`twig seed ${s.seed} is not on the cut-out`);
  inC[st[0]] = 1;
  while (st.length) {
    const i = st.pop();
    const x = i % W, y = (i - x) / W;
    for (let dy = -1; dy <= 1; dy++) {
      for (let dx = -1; dx <= 1; dx++) {
        const X = x + dx, Y = y + dy;
        if (X < 0 || Y < 0 || X >= W || Y >= H) continue;
        const j = Y * W + X;
        if (!inC[j] && alpha[j] > 2) { inC[j] = 1; st.push(j); }
      }
    }
  }
  const px = new Float32Array(n * 4);        // premultiplied linear r, g, b, a
  let x0 = W, x1 = 0, y0 = H, y1 = 0;
  for (let i = 0; i < n; i++) {
    if (!inC[i]) continue;
    const a = alpha[i] / 255;
    px[i * 4] = LIN[diff[i * 3]] * a;
    px[i * 4 + 1] = LIN[diff[i * 3 + 1]] * a;
    px[i * 4 + 2] = LIN[diff[i * 3 + 2]] * a;
    px[i * 4 + 3] = a;
    const x = i % W, y = (i - x) / W;
    x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
  }
  const ax = s.tip[0] - s.base[0], ay = s.tip[1] - s.base[1];
  const len = Math.hypot(ax, ay);
  const u = [ax / len, ay / len];
  const anchor = [s.base[0] + u[0] * len * s.anchor, s.base[1] + u[1] * len * s.anchor];
  // `right`: the side that is +u in the card when the shoot points up the card
  return { px, W, H, axis: u, right: [-u[1], u[0]], anchor, len: len * (1 - s.anchor), box: [x0, y0, x1, y1] };
}

/** Bilinear sample (premultiplied rgba) of a sprite at image coordinates (x, y), into out. */
function sampleSprite(sp, x, y, out) {
  out[0] = out[1] = out[2] = out[3] = 0;
  const fx = x - 0.5, fy = y - 0.5;
  const ix = Math.floor(fx), iy = Math.floor(fy);
  if (ix < sp.box[0] - 1 || iy < sp.box[1] - 1 || ix > sp.box[2] || iy > sp.box[3]) return;
  const tx = fx - ix, ty = fy - iy;
  for (let k = 0; k < 4; k++) {
    const X = ix + (k & 1), Y = iy + (k >> 1);
    if (X < 0 || Y < 0 || X >= sp.W || Y >= sp.H) continue;
    const w = ((k & 1) ? tx : 1 - tx) * ((k >> 1) ? ty : 1 - ty);
    const o = (Y * sp.W + X) * 4;
    out[0] += sp.px[o] * w; out[1] += sp.px[o + 1] * w; out[2] += sp.px[o + 2] * w; out[3] += sp.px[o + 3] * w;
  }
}

/** One cell (n x n, row 0 = the cell's top) of premultiplied rgba: the twigs of `spec` scaled by `k`. */
function twigCell(sprites, spec, n, k) {
  const out = new Float32Array(n * n * 4);
  const s = new Float32Array(4);
  for (const [name, deg, len, mirror] of spec) {
    const sp = sprites[name];
    const th = deg * Math.PI / 180, c = Math.cos(th), sn = Math.sin(th);
    const L = len * k;
    const f = sp.len / L;                    // sprite px per cell unit
    for (let r = 0; r < n; r++) {
      const y = 1 - (r + 0.5) / n - TWIG_ROOT_Y;
      for (let q = 0; q < n; q++) {
        const x = (q + 0.5) / n - 0.5;
        let lx = x * c - y * sn;             // twig frame: ly along the shoot, lx to its right
        const ly = x * sn + y * c;
        if (mirror) lx = -lx;
        sampleSprite(sp, sp.anchor[0] + (sp.axis[0] * ly + sp.right[0] * lx) * f,
          sp.anchor[1] + (sp.axis[1] * ly + sp.right[1] * lx) * f, s);
        if (s[3] <= 0) continue;
        const o = (r * n + q) * 4, keep = 1 - s[3];
        for (let ch = 0; ch < 4; ch++) out[o + ch] = s[ch] + out[o + ch] * keep;
      }
    }
  }
  // the stem below the root (it would be cut by the cell edge) fades out over the bottom of the cell
  for (let r = 0; r < n; r++) {
    const y = 1 - (r + 0.5) / n;
    const t = Math.min(1, Math.max(0, (y - 0.25 * TWIG_ROOT_Y) / (0.75 * TWIG_ROOT_Y)));
    const w = t * t * (3 - 2 * t);
    if (w >= 1) continue;
    for (let q = 0; q < n; q++) for (let ch = 0; ch < 4; ch++) out[(r * n + q) * 4 + ch] *= w;
  }
  return out;
}

/** Largest coverage within TWIG_BORDER of the cell's left, right and top edges. */
function borderAlpha(cell, n) {
  const b = Math.ceil(TWIG_BORDER * n);
  let m = 0;
  for (let r = 0; r < n; r++) {
    for (let q = 0; q < n; q++) {
      if (r < b || q < b || q >= n - b) m = Math.max(m, cell[(r * n + q) * 4 + 3]);
    }
  }
  return m;
}

/** Gaussian blur of a (n x n) array with zero padding outside the cell. */
function blurCell(src, n, sigma) {
  const r = Math.ceil(3 * sigma);
  const k = new Float64Array(2 * r + 1);
  for (let i = -r; i <= r; i++) k[i + r] = Math.exp(-0.5 * (i / sigma) ** 2);
  const tmp = new Float64Array(n * n), out = new Float64Array(n * n);
  for (let y = 0; y < n; y++) {
    for (let x = 0; x < n; x++) {
      let s = 0;
      for (let j = Math.max(-r, -x); j <= Math.min(r, n - 1 - x); j++) s += k[j + r] * src[y * n + x + j];
      tmp[y * n + x] = s;
    }
  }
  for (let x = 0; x < n; x++) {
    for (let y = 0; y < n; y++) {
      let s = 0;
      for (let j = Math.max(-r, -y); j <= Math.min(r, n - 1 - y); j++) s += k[j + r] * tmp[(y + j) * n + x];
      out[y * n + x] = s;
    }
  }
  return out;
}

async function makeTwig(assets) {
  const dm = await sharp(path.join(assets, TWIG_DIFF)).removeAlpha().toColourspace('srgb').raw()
    .toBuffer({ resolveWithObject: true });
  const am = await sharp(path.join(assets, TWIG_ALPHA)).toColourspace('b-w').raw({ depth: 'uchar' })
    .toBuffer({ resolveWithObject: true });
  const { width: W, height: H } = dm.info;
  if (am.info.width !== W || am.info.height !== H) throw new Error('twig colour and alpha sizes differ');
  const sprites = {};
  for (const [name, s] of Object.entries(TWIG_SPRITES)) sprites[name] = twigSprite(dm.data, am.data, W, H, s);
  const cpx = TWIG_PX / TWIG_GRID;           // output cell side
  const n = cpx * TWIG_SS;                   // working cell side
  const rgb = Buffer.alloc(TWIG_PX * TWIG_PX * 3);
  if (TWIG_CELLS.length !== TWIG_GRID * TWIG_GRID) throw new Error('TWIG_CELLS must fill the grid');
  for (let ci = 0; ci < TWIG_CELLS.length; ci++) {
    // shrink the brush until no needle reaches the cell's sides or top
    let k = 1, work;
    for (;;) {
      work = twigCell(sprites, TWIG_CELLS[ci], n, k);
      if (borderAlpha(work, n) < 0.02 || k < 0.6) break;
      k *= 0.96;
    }
    // box-filter down to the output cell: premultiplied colour -> luminance, coverage
    const A = new Float64Array(cpx * cpx), Y = new Float64Array(cpx * cpx);
    for (let r = 0; r < cpx; r++) {
      for (let q = 0; q < cpx; q++) {
        let a = 0, yl = 0;
        for (let dy = 0; dy < TWIG_SS; dy++) {
          for (let dx = 0; dx < TWIG_SS; dx++) {
            const o = ((r * TWIG_SS + dy) * n + q * TWIG_SS + dx) * 4;
            a += work[o + 3];
            yl += 0.2126 * work[o] + 0.7152 * work[o + 1] + 0.0722 * work[o + 2];
          }
        }
        A[r * cpx + q] = a / (TWIG_SS * TWIG_SS);
        Y[r * cpx + q] = a > 0 ? yl / a : 0;           // un-premultiplied
      }
    }
    // detail: log2 luminance minus its coverage-weighted blur, scaled to TWIG_DETAIL_STD, as a ratio around 0.5
    const L = new Float64Array(cpx * cpx), AL = new Float64Array(cpx * cpx);
    for (let i = 0; i < L.length; i++) {
      L[i] = Math.log2(Y[i] + LOG_EPS);
      AL[i] = A[i] * L[i];
    }
    const sig = TWIG_SIGMA * cpx;
    const bA = blurCell(A, cpx, sig), bAL = blurCell(AL, cpx, sig);
    const hp = new Float64Array(cpx * cpx);
    let sw = 0, s1 = 0, s2 = 0;
    for (let i = 0; i < hp.length; i++) {
      hp[i] = bA[i] > 1e-6 ? L[i] - bAL[i] / bA[i] : 0;
      sw += A[i]; s1 += A[i] * hp[i]; s2 += A[i] * hp[i] * hp[i];
    }
    const mean = s1 / sw;
    const gain = TWIG_DETAIL_STD / Math.sqrt(Math.max(1e-12, s2 / sw - mean * mean));
    // the covered texels' mean ratio is 1 (the bake keeps the card's average brightness)
    let rs = 0;
    for (let i = 0; i < hp.length; i++) rs += A[i] * 2 ** (gain * (hp[i] - mean));
    const norm = sw / rs;
    let clipped = 0;
    const cx = ci % TWIG_GRID, cyFromBottom = Math.floor(ci / TWIG_GRID);
    const top = (TWIG_GRID - 1 - cyFromBottom) * cpx;  // file row of the cell's top (cell 0 = bottom-left)
    for (let r = 0; r < cpx; r++) {
      for (let q = 0; q < cpx; q++) {
        const i = r * cpx + q;
        const ratio = norm * 2 ** (gain * (hp[i] - mean));
        const rv = 0.5 + (0.5 * ratio - 0.5) * Math.min(1, A[i] * 4);   // neutral where nothing is covered
        if (rv > 1 && A[i] > 0.5) clipped++;
        const o = ((top + r) * TWIG_PX + cx * cpx + q) * 3;
        rgb[o] = Math.max(0, Math.min(255, Math.round(rv * 255)));
        rgb[o + 1] = Math.max(0, Math.min(255, Math.round(A[i] * 255)));
        rgb[o + 2] = 0;
      }
    }
    console.log(`twig cell ${ci} (u ${cx}, v ${cyFromBottom}): ${TWIG_CELLS[ci].length} twigs at x${k.toFixed(3)}, `
      + `coverage ${(100 * sw / (cpx * cpx)).toFixed(1)}%, detail gain ${gain.toFixed(3)}, `
      + `clipped ${(100 * clipped / Math.max(1, sw)).toFixed(2)}%`);
  }
  const buf = await sharp(rgb, { raw: { width: TWIG_PX, height: TWIG_PX, channels: 3 } })
    .png({ compressionLevel: 9, adaptiveFiltering: true }).toBuffer();
  const out = path.join(assets, 'web', 'twig_card.png');
  writeAtomic(out, buf);
  const st = (ch) => channelStats(rgb, 3, ch, TWIG_PX * TWIG_PX);
  console.log(`twig_card.png ${TWIG_PX}x${TWIG_PX} RGB ${(buf.length / 1e6).toFixed(2)} MB  R mean ${st(0).mean.toFixed(3)} `
    + `std ${st(0).std.toFixed(3)}, G mean ${st(1).mean.toFixed(3)} -> ${out}`);
}

// ---- waterfall mist flipbook (4., waterfall foot effects) --------------------------------------------------------
//
//     node prep_textures.mjs <assets dir> --mist-flipbook <out.webp>
//     e.g. node .../tools/prep_textures.mjs E:/Github/PortfolioV5/blender/xianxia-sect/assets --mist-flipbook
//              E:/Github/PortfolioV5/client/public/sect/fx/mist_flipbook.webp
//
// The mist puffs at the waterfall feet (client/src/app/sect/experience/waterfall-fx.tsx). Source: Thomas Iché's
// CC0 flipbooks (Unity Labs) as repackaged in the Brackeys VFX Bundle (CC0, its LICENSE & CREDITS.txt), downloaded
// to <assets>/brackeys/vfx-bundle/ (8 x 8 frames of 128 px, uncompressed 32-bit TGA). Only their alpha (the smoke's
// density) is kept: the page lights the puffs itself (sun side, haze). MIST_GRID x MIST_GRID frames of MIST_CELL
// px, every (64 / MIST_GRID^2)th source frame, frame 0 at the top-left, row-major (the page uploads with flipY
// off, so file row 0 is v = 0). R = Cloud01 (round billow), G = WispySmoke01 (torn spray), B = Cloud02. Each frame
// is faded to 0 by a radial window before the cell's edge (no square cut, no bleed into the next cell's mips) and
// each channel is scaled so its densest texel is 255. Near-lossless WebP q60 (each channel off by at most 2 levels;
// 98 KB against 176 KB lossless): the channels are unrelated, and lossy WebP's 4:2:0 chroma would mix them.

const MIST_FLIPBOOK_DIR = 'brackeys/vfx-bundle/brackeys_vfx_bundle/flipbooks';
const MIST_SOURCES = ['cloud_01_8x8.tga', 'wispy_smoke_01_8x8.tga', 'cloud_02_8x8.tga'];   // -> R, G, B
const MIST_SRC_GRID = 8;
const MIST_GRID = 4;                       // 16 frames out of 64
const MIST_CELL = 128;
const MIST_WINDOW = [0.82, 0.98];          // radial fade (share of the half cell): full inside, 0 outside

/** RGBA pixels (top row first) of a 32-bit TGA, uncompressed (type 2) or run-length encoded (type 10). */
function readTga32(file) {
  const b = fs.readFileSync(file);
  const idLen = b[0], cmapType = b[1], type = b[2];
  const w = b.readUInt16LE(12), h = b.readUInt16LE(14), bpp = b[16], desc = b[17];
  if (cmapType !== 0 || (type !== 2 && type !== 10) || bpp !== 32) {
    throw new Error(`${file}: only 32-bit true-colour TGA is read (type ${type}, ${bpp} bpp)`);
  }
  const n = w * h;
  const px = Buffer.alloc(n * 4);              // file order, BGRA
  let o = 18 + idLen;
  if (type === 2) {
    if (b.length < o + n * 4) throw new Error(`${file}: truncated`);
    b.copy(px, 0, o, o + n * 4);
  } else {
    for (let i = 0; i < n;) {
      const head = b[o++];
      const run = (head & 0x7f) + 1;
      if (i + run > n || o >= b.length) throw new Error(`${file}: bad RLE packet`);
      if (head & 0x80) {
        for (let k = 0; k < run; k++) b.copy(px, (i + k) * 4, o, o + 4);
        o += 4;
      } else {
        b.copy(px, i * 4, o, o + run * 4);
        o += run * 4;
      }
      i += run;
    }
  }
  const top = (desc & 0x20) !== 0, right = (desc & 0x10) !== 0;
  const out = Buffer.alloc(n * 4);
  for (let y = 0; y < h; y++) {
    const sy = top ? y : h - 1 - y;
    for (let x = 0; x < w; x++) {
      const sx = right ? w - 1 - x : x;
      const s = (sy * w + sx) * 4, d = (y * w + x) * 4;
      out[d] = px[s + 2]; out[d + 1] = px[s + 1]; out[d + 2] = px[s]; out[d + 3] = px[s + 3];
    }
  }
  return { data: out, width: w, height: h };
}

async function makeMistFlipbook(assets, outFile) {
  const side = MIST_GRID * MIST_CELL;
  const frames = MIST_GRID * MIST_GRID;
  const step = (MIST_SRC_GRID * MIST_SRC_GRID) / frames;
  const dens = MIST_SOURCES.map(() => new Float64Array(side * side));
  MIST_SOURCES.forEach((name, ch) => {
    const t = readTga32(path.join(assets, MIST_FLIPBOOK_DIR, name));
    const cell = t.width / MIST_SRC_GRID;
    if (t.width !== t.height || cell !== MIST_CELL) throw new Error(`${name}: expected ${MIST_SRC_GRID} x ${MIST_SRC_GRID} cells of ${MIST_CELL} px`);
    let edge = 0;
    for (let f = 0; f < frames; f++) {
      const src = f * step;
      const sx = (src % MIST_SRC_GRID) * cell, sy = Math.floor(src / MIST_SRC_GRID) * cell;
      const dx = (f % MIST_GRID) * MIST_CELL, dy = Math.floor(f / MIST_GRID) * MIST_CELL;
      for (let y = 0; y < MIST_CELL; y++) {
        for (let x = 0; x < MIST_CELL; x++) {
          const a = t.data[((sy + y) * t.width + sx + x) * 4 + 3] / 255;
          const rx = (x + 0.5) / MIST_CELL * 2 - 1, ry = (y + 0.5) / MIST_CELL * 2 - 1;
          const r = Math.hypot(rx, ry);
          const k = Math.min(1, Math.max(0, (r - MIST_WINDOW[0]) / (MIST_WINDOW[1] - MIST_WINDOW[0])));
          const win = 1 - k * k * (3 - 2 * k);
          if (x === 0 || y === 0 || x === MIST_CELL - 1 || y === MIST_CELL - 1) edge = Math.max(edge, a);
          dens[ch][(dy + y) * side + dx + x] = a * win;
        }
      }
    }
    console.log(`mist flipbook ${'RGB'[ch]} <- ${name}: frames 0..${(frames - 1) * step} step ${step}, `
      + `largest source alpha on a cell edge ${edge.toFixed(3)} (windowed to 0)`);
  });
  const rgb = Buffer.alloc(side * side * 3);
  dens.forEach((d, ch) => {
    let max = 0;
    for (let i = 0; i < d.length; i++) max = Math.max(max, d[i]);
    for (let i = 0; i < d.length; i++) rgb[i * 3 + ch] = Math.round(255 * d[i] / Math.max(max, 1e-6));
  });
  const buf = await sharp(rgb, { raw: { width: side, height: side, channels: 3 } })
    .webp({ nearLossless: true, quality: 60, effort: 6 }).toBuffer();
  writeAtomic(outFile, buf);
  for (let ch = 0; ch < 3; ch++) {
    const s = channelStats(rgb, 3, ch, side * side);
    console.log(`  ${'RGB'[ch]} mean ${s.mean.toFixed(3)} std ${s.std.toFixed(3)}`);
  }
  console.log(`mist_flipbook ${side}x${side} RGB (${MIST_GRID}x${MIST_GRID} frames of ${MIST_CELL} px) `
    + `${(buf.length / 1024).toFixed(0)} KB -> ${outFile}`);
}

// ---- waterfall sheet strands and pool foam (5., --fx) --------------------------------------------------------------
//
//     node prep_textures.mjs <assets dir> --fx <fx dir>
//     e.g. node .../tools/prep_textures.mjs E:/Github/PortfolioV5/blender/xianxia-sect/assets --fx
//              E:/Github/PortfolioV5/client/public/sect/fx
//
// <fx dir>/strands.webp: the falling-water strand mask the waterfall sheet shader scrolls down every sheet
// (client/src/lib/sect/waterfall.ts SHEET.strandTileM metres across per tile). Source: LibreShot "Waterfall Texture" by
// Martin Vorel (CC0, https://libreshot.com/waterfall-texture/; hotlinking is not allowed there, so the site hosts this
// derivative), <assets>/libreshot/waterfall-texture/waterfall.jpg, 3500 x 2333: a curtain of water over dark rock with
// white strands. Its curtain (rows STRAND_ROW0.., above the splash) is cut into a left and a right half, each
// shrunk by STRAND_SHRINK and made to wrap across by cross-fading its last STRAND_BAND columns into its first; the
// halves are stacked (left on top) and cross-fade into each other over STRAND_BAND rows at both joins, so the tile
// wraps both ways. Cross-fades keep the variance (no washed-out band). Then the luminance is high-passed (minus its
// wrap-around Gaussian blur, STRAND_SIGMA px: no light falloff from the photo) and scaled to mean STRAND_MEAN, std
// STRAND_STD: bright = white strands, dark = clear water. One channel (greyscale lossy WebP): the page reads R.
// STRAND_W x 2 STRAND_H_HALF px.
//
// <fx dir>/foam.webp: pool foam for the waterfall feet (the foot effects reuse it). Source: ambientCG Foam002 (CC0,
// https://ambientcg.com/view?id=Foam002), its 1K Opacity map (<assets>/ambientcg/Foam002/Foam002_1K-JPG_Opacity.jpg):
// lacy foam with holes, already seamless. Shrunk 2x wrap-aware, levels stretched so the 2nd..98th percentiles span
// 0..1: R = G = B = foam cover (0 open water, 1 dense foam). FOAM_PX square greyscale lossy WebP.

const STRAND_SRC = 'libreshot/waterfall-texture/waterfall.jpg';
const STRAND_W = 512;                      // output width; height 2 x STRAND_H_HALF
const STRAND_H_HALF = 384;
const STRAND_BAND = 48;                    // cross-fade width, output px
const STRAND_SHRINK = 3;                   // source px per output px
const STRAND_ROW0 = 150;                   // first source row used (below the lip's foam band)
const STRAND_SIGMA = 24;                   // high-pass blur, output px
const STRAND_MEAN = 0.45;
const STRAND_STD = 0.2;
const STRAND_WEBP = { quality: 82, effort: 6 };
const FOAM_SRC = 'ambientcg/Foam002/Foam002_1K-JPG_Opacity.jpg';
const FOAM_PX = 512;
const FOAM_WEBP = { quality: 80, effort: 6 };

/** Luminance (sRGB-weighted, 0..1) of a source region shrunk by an exact integer factor: Float32Array w x h. */
async function regionLuma(file, left, top, w, h, shrink) {
  const img = await sharp(file).removeAlpha().toColourspace('srgb')
    .extract({ left, top, width: w * shrink, height: h * shrink })
    .resize(w, h, { kernel: 'lanczos3', fit: 'fill' }).raw().toBuffer({ resolveWithObject: true });
  const c = img.info.channels, out = new Float32Array(w * h);
  for (let i = 0; i < w * h; i++) {
    out[i] = (0.2126 * img.data[i * c] + 0.7152 * img.data[i * c + 1] + 0.0722 * img.data[i * c + 2]) / 255;
  }
  return out;
}

function meanOf(a) {
  let s = 0;
  for (let i = 0; i < a.length; i++) s += a[i];
  return s / Math.max(a.length, 1);
}

/** Cross-fade of a (weight 1 - t) into b (weight t) that keeps the variance about the mean m. */
function fadeKeep(a, b, t, m) {
  const k = t * t * (3 - 2 * t);
  return m + ((a - m) * (1 - k) + (b - m) * k) / Math.hypot(1 - k, k);
}

/** A (w + band) x rows image made to wrap across: w columns, the last `band` faded into the first. */
function wrapAcross(src, w, band, rows, m) {
  const sw = w + band, out = new Float32Array(w * rows);
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < w; x++) {
      const v = src[y * sw + x];
      out[y * w + x] = x < band ? fadeKeep(src[y * sw + w + x], v, (x + 0.5) / band, m) : v;
    }
  }
  return out;
}

async function makeStrands(assets, outFile) {
  const file = path.join(assets, STRAND_SRC);
  const m = await sharp(file).metadata();
  const w = STRAND_W, hh = STRAND_H_HALF, band = STRAND_BAND, f = STRAND_SHRINK;
  const sw = w + band, sh = hh + band;
  if (m.width < 2 * sw * f || m.height < STRAND_ROW0 + sh * f) throw new Error(`${file}: ${m.width}x${m.height} is too small`);
  // Left and right halves of the curtain (they overlap in the middle of a narrow photo; fine).
  const halves = [await regionLuma(file, 0, STRAND_ROW0, sw, sh, f), await regionLuma(file, m.width - sw * f, STRAND_ROW0, sw, sh, f)];
  const mu = (meanOf(halves[0]) + meanOf(halves[1])) / 2;
  const [A, B] = halves.map((h) => wrapAcross(h, w, band, sh, mu));
  // Stacked: rows 0..hh from A, hh..2hh from B; each join fades from the upper half's extra rows into the lower's.
  const H = 2 * hh;
  const L = new Float32Array(w * H);
  for (let y = 0; y < hh; y++) {
    for (let x = 0; x < w; x++) {
      const t = (y + 0.5) / band;
      L[y * w + x] = y < band ? fadeKeep(B[(hh + y) * w + x], A[y * w + x], t, mu) : A[y * w + x];
      L[(hh + y) * w + x] = y < band ? fadeKeep(A[(hh + y) * w + x], B[y * w + x], t, mu) : B[y * w + x];
    }
  }
  const lo = blurWrap(L, w, H, STRAND_SIGMA);
  let s2 = 0;
  for (let i = 0; i < L.length; i++) { L[i] -= lo[i]; s2 += L[i] * L[i]; }
  const k = STRAND_STD / Math.sqrt(s2 / L.length);
  const grey = Buffer.alloc(w * H);
  let clipped = 0;
  for (let i = 0; i < L.length; i++) {
    const v = Math.round((STRAND_MEAN + k * L[i]) * 255);
    if (v < 0 || v > 255) clipped++;
    grey[i] = Math.max(0, Math.min(255, v));
  }
  const buf = await sharp(grey, { raw: { width: w, height: H, channels: 1 } }).webp(STRAND_WEBP).toBuffer();
  writeAtomic(outFile, buf);
  const dec = await sharp(buf).raw().toBuffer({ resolveWithObject: true });
  const st = channelStats(dec.data, dec.info.channels, 0, w * H);
  console.log(`strands.webp ${w}x${H} mean ${st.mean.toFixed(3)} std ${st.std.toFixed(3)} clipped `
    + `${(100 * clipped / L.length).toFixed(2)}% seam ratio ${seamRatio(dec.data, w, H, dec.info.channels).toFixed(2)} `
    + `${(buf.length / 1024).toFixed(0)} KB -> ${outFile}`);
}

async function makeFoam(assets, outFile) {
  const n = FOAM_PX;
  const img = await wrapResize(path.join(assets, FOAM_SRC), n, n);
  const v = Float32Array.from({ length: n * n }, (_, i) => img.data[i * 3] / 255);
  const sorted = Float32Array.from(v).sort();
  const p2 = sorted[Math.floor(0.02 * (n * n - 1))], p98 = sorted[Math.floor(0.98 * (n * n - 1))];
  const grey = Buffer.alloc(n * n);
  for (let i = 0; i < n * n; i++) grey[i] = Math.max(0, Math.min(255, Math.round((v[i] - p2) / Math.max(p98 - p2, 1e-6) * 255)));
  const buf = await sharp(grey, { raw: { width: n, height: n, channels: 1 } }).webp(FOAM_WEBP).toBuffer();
  writeAtomic(outFile, buf);
  const dec = await sharp(buf).raw().toBuffer({ resolveWithObject: true });
  const st = channelStats(dec.data, dec.info.channels, 0, n * n);
  console.log(`foam.webp ${n}x${n} mean ${st.mean.toFixed(3)} std ${st.std.toFixed(3)} (levels ${p2.toFixed(3)}..`
    + `${p98.toFixed(3)}) seam ratio ${seamRatio(dec.data, n, n, dec.info.channels).toFixed(2)} `
    + `${(buf.length / 1024).toFixed(0)} KB -> ${outFile}`);
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--mist-flipbook')) {            // 4. only (the waterfall foot effects' mist flipbook)
    const [assetsDir, out] = args.filter((a) => !a.startsWith('--'));
    if (!assetsDir || !out) {
      console.error('usage: node prep_textures.mjs <assets dir> --mist-flipbook <out.webp>');
      process.exit(2);
    }
    await makeMistFlipbook(path.resolve(assetsDir), path.resolve(out));
    return;
  }
  if (args.includes('--fx')) {                       // 5. only (the waterfall sheets' strands and the pool foam)
    const [assetsDir, fxDir] = args.filter((a) => !a.startsWith('--'));
    if (!assetsDir || !fxDir) {
      console.error('usage: node prep_textures.mjs <assets dir> --fx <fx dir>');
      process.exit(2);
    }
    await makeStrands(path.resolve(assetsDir), path.join(path.resolve(fxDir), 'strands.webp'));
    await makeFoam(path.resolve(assetsDir), path.join(path.resolve(fxDir), 'foam.webp'));
    return;
  }
  const twigOnly = args.includes('--twig-only');
  const [assets, detail] = args.filter((a) => !a.startsWith('--'));
  if (!assets || (!detail && !twigOnly)) {
    console.error('usage: node prep_textures.mjs <assets dir> <detail.webp path>\n'
      + '       node prep_textures.mjs <assets dir> --twig-only');
    process.exit(2);
  }
  if (!twigOnly) {
    await makeJpgs(path.resolve(assets));
    await makeDetail(path.resolve(assets), path.resolve(detail));
  }
  await makeTwig(path.resolve(assets));
}

main().catch((e) => { console.error(e); process.exit(1); });
