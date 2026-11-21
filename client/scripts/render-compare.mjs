// Compares two sets of render-probe screenshots of the same views (say a PC's and a Mac's): for
// each camera frame both have, how many pixels are near black in B and not in A, how many are much
// darker, and where. Writes one diff picture per frame: B in grey, new black in magenta, much
// darker in orange, other large differences in blue. See docs/sect/render-probe.md.
//
//   node scripts/render-compare.mjs --a outA --alabel chromium-d3d11-high --b outB --blabel chromium-metal-high --out diff
//
// The debug HUD (top left, its numbers differ from run to run) is left out of the counts.
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

function arg(name, dflt) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && i + 1 < process.argv.length ? process.argv[i + 1] : dflt;
}

/** An 8-bit RGB or RGBA PNG (what browsers save) as RGB bytes. */
export function decodePng(file) {
  const buf = fs.readFileSync(file);
  let p = 8;
  let w = 0;
  let h = 0;
  let bitDepth = 0;
  let colorType = 0;
  const idat = [];
  while (p < buf.length) {
    const len = buf.readUInt32BE(p);
    const type = buf.toString("ascii", p + 4, p + 8);
    const data = buf.subarray(p + 8, p + 8 + len);
    if (type === "IHDR") {
      w = data.readUInt32BE(0);
      h = data.readUInt32BE(4);
      bitDepth = data[8];
      colorType = data[9];
    } else if (type === "IDAT") idat.push(data);
    p += 12 + len;
  }
  if (bitDepth !== 8 || (colorType !== 2 && colorType !== 6)) throw new Error(`unsupported png ${bitDepth}/${colorType}: ${file}`);
  const bpp = colorType === 6 ? 4 : 3;
  const raw = zlib.inflateSync(Buffer.concat(idat));
  const stride = w * bpp;
  const px = new Uint8Array(w * h * 3);
  let prev = new Uint8Array(stride);
  let cur = new Uint8Array(stride);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)];
    const line = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    for (let i = 0; i < stride; i++) {
      const a = i >= bpp ? cur[i - bpp] : 0;
      const b = prev[i];
      const c = i >= bpp ? prev[i - bpp] : 0;
      let v = line[i];
      if (f === 1) v += a;
      else if (f === 2) v += b;
      else if (f === 3) v += (a + b) >> 1;
      else if (f === 4) {
        const pa = Math.abs(b - c);
        const pb = Math.abs(a - c);
        const pc = Math.abs(a + b - 2 * c);
        v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
      }
      cur[i] = v & 255;
    }
    for (let x = 0; x < w; x++) {
      px[(y * w + x) * 3] = cur[x * bpp];
      px[(y * w + x) * 3 + 1] = cur[x * bpp + 1];
      px[(y * w + x) * 3 + 2] = cur[x * bpp + 2];
    }
    [prev, cur] = [cur, prev];
  }
  return { w, h, px };
}

function crc32(buf) {
  let crc = ~0;
  for (let n = 0; n < buf.length; n++) {
    let c = (crc ^ buf[n]) & 255;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    crc = (crc >>> 8) ^ c;
  }
  return ~crc >>> 0;
}

export function encodePng(w, h, rgb) {
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) Buffer.from(rgb.buffer, rgb.byteOffset + y * w * 3, w * 3).copy(raw, y * (w * 3 + 1) + 1);
  const chunk = (type, data) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type, "ascii"), data]);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(td));
    return Buffer.concat([len, td, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ihdr), chunk("IDAT", zlib.deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}

/** B scaled to A's size by nearest pixel (a 2x screen's shot against a 1x one). */
function fit(B, w, h) {
  if (B.w === w && B.h === h) return B;
  const px = new Uint8Array(w * h * 3);
  for (let y = 0; y < h; y++) {
    const sy = Math.min(B.h - 1, Math.floor(((y + 0.5) * B.h) / h));
    for (let x = 0; x < w; x++) {
      const sx = Math.min(B.w - 1, Math.floor(((x + 0.5) * B.w) / w));
      const s = (sy * B.w + sx) * 3;
      const d = (y * w + x) * 3;
      px[d] = B.px[s];
      px[d + 1] = B.px[s + 1];
      px[d + 2] = B.px[s + 2];
    }
  }
  return { w, h, px };
}

export function compare(A, B0) {
  const { w, h } = A;
  const B = fit(B0, w, h);
  // The HUD's share of the frame (up to 700 x 340 of 1600 x 900: its chunk line grows with the places held).
  const hud = (x, y) => x < w * 0.44 && y < h * 0.378;
  let n = 0, blackA = 0, blackB = 0, newBlackB = 0, newBlackA = 0, differ = 0, darker = 0;
  const diff = new Uint8Array(w * h * 3);
  const cells = new Map();
  const cell = Math.max(1, Math.round(w / 16));
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 3;
      const ma = Math.max(A.px[i], A.px[i + 1], A.px[i + 2]);
      const mb = Math.max(B.px[i], B.px[i + 1], B.px[i + 2]);
      const d = Math.max(Math.abs(A.px[i] - B.px[i]), Math.abs(A.px[i + 1] - B.px[i + 1]), Math.abs(A.px[i + 2] - B.px[i + 2]));
      const g = Math.round((B.px[i] + B.px[i + 1] + B.px[i + 2]) / 6);
      diff[i] = g;
      diff[i + 1] = g;
      diff[i + 2] = g;
      if (hud(x, y)) continue;
      n++;
      if (ma < 6) blackA++;
      if (mb < 6) blackB++;
      const nb = mb < 6 && ma > 30;
      if (nb) newBlackB++;
      if (ma < 6 && mb > 30) newBlackA++;
      if (d > 40) differ++;
      const dk = ma - mb > 40;
      if (dk) darker++;
      if (nb) {
        diff[i] = 255;
        diff[i + 1] = 0;
        diff[i + 2] = 255;
      } else if (dk) {
        diff[i] = 255;
        diff[i + 1] = 70;
        diff[i + 2] = 0;
      } else if (d > 40) {
        diff[i] = 0;
        diff[i + 1] = 150;
        diff[i + 2] = 255;
      }
      if (nb || dk) {
        const k = `${Math.floor(x / cell)},${Math.floor(y / cell)}`;
        cells.set(k, (cells.get(k) ?? 0) + 1);
      }
    }
  }
  const worst = [...cells.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6).map(([k, v]) => `${k}:${v}`);
  return { n, blackA, blackB, newBlackInB: newBlackB, newBlackInA: newBlackA, differBy40: differ, bDarkerBy40: darker, worstCells: worst, diff, w, h };
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
if (isMain) {
  const a = arg("a", "");
  const b = arg("b", a);
  const alabel = arg("alabel", "");
  const blabel = arg("blabel", "");
  const out = arg("out", "");
  if (!a || !alabel || !blabel) {
    console.error("usage: node scripts/render-compare.mjs --a DIR --alabel LABEL [--b DIR] --blabel LABEL [--out DIR]");
    process.exit(2);
  }
  if (out) fs.mkdirSync(out, { recursive: true });
  const frames = fs
    .readdirSync(a)
    .map((f) => new RegExp(`^${alabel.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}-f(\\d+)\\.png$`).exec(f)?.[1])
    .filter(Boolean)
    .map(Number)
    .sort((x, y) => x - y);
  for (const f of frames) {
    const fa = path.join(a, `${alabel}-f${f}.png`);
    const fb = path.join(b, `${blabel}-f${f}.png`);
    if (!fs.existsSync(fb)) {
      console.log(`f${f}: no ${blabel} shot`);
      continue;
    }
    const r = compare(decodePng(fa), decodePng(fb));
    const pct = (v) => `${((100 * v) / r.n).toFixed(3)}%`;
    console.log(
      `f${f}: new black in ${blabel} ${r.newBlackInB} (${pct(r.newBlackInB)}), much darker ${r.bDarkerBy40} (${pct(r.bDarkerBy40)}), differ ${pct(r.differBy40)}, black ${r.blackA} -> ${r.blackB}` +
        (r.worstCells.length ? `, worst cells ${r.worstCells.join(" ")}` : ""),
    );
    if (out) fs.writeFileSync(path.join(out, `${alabel}__${blabel}-f${f}.png`), encodePng(r.w, r.h, r.diff));
  }
}
