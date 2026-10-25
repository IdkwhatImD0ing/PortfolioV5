/**
 * Draws every icon file from the site's logo (src/lib/sect/logo.ts: the sect's seal, a sun cradled in
 * a crescent moon, cut like a 白文 seal on cinnabar).
 *
 *   node scripts/make-icons.mjs [contact-sheet.png]
 *
 * Each size gets the drawing made for it (logo.ts):
 * - "small", fitted to the pixel grid: public/favicon.svg, favicon-16x16.png, favicon-32x32.png, and
 *   the 16 and 32 px images in icon.ico and favicon.ico.
 * - "plain" (straight edge): the 48 px image in the .ico files.
 * - "worn" (the ground stone edge): public/android-chrome-*.png and public/icons/icon-*.png, and the
 *   README's seal (.github/readme/seal.svg, and seal-light.svg cut through for light pages).
 * - public/apple-touch-icon.png (180): the worn seal at 80% on the sect's ink (iOS rounds the corners
 *   and fills transparency with black). public/icons/maskable.png (512): full-bleed red, the moon's
 *   circle at 70% of the tile, inside any launcher's mask.
 * With a path, also a sheet of every size on a dark and a light tab strip, to look at.
 *
 * Needs Node 22.18+ (it imports the .ts module directly). sharp comes with Next (it is not a
 * dependency of its own), so it is loaded from there.
 */
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { appIconSvg, logoSvg } from "../src/lib/sect/logo.ts";

const require = createRequire(import.meta.url);
const sharp = createRequire(require.resolve("next/package.json"))("sharp");

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PUBLIC = path.join(ROOT, "public");
const README_DIR = path.join(ROOT, "..", ".github", "readme");

/** Rasterise at 4 times the size, then scale down (the svg's viewBox sets its natural size). */
async function png(svg, size) {
  const box = Number(svg.match(/viewBox="0 0 ([\d.]+)/)[1]);
  return sharp(Buffer.from(svg), { density: ((72 * size) / box) * 4 })
    .resize(size, size)
    .png({ compressionLevel: 9 })
    .toBuffer();
}

/** An .ico holding PNG images (every browser, and Windows since Vista, reads these). */
function ico(images) {
  const head = Buffer.alloc(6 + 16 * images.length);
  head.writeUInt16LE(0, 0);
  head.writeUInt16LE(1, 2);
  head.writeUInt16LE(images.length, 4);
  let offset = head.length;
  images.forEach(({ size, data }, i) => {
    const e = 6 + 16 * i;
    head.writeUInt8(size >= 256 ? 0 : size, e);
    head.writeUInt8(size >= 256 ? 0 : size, e + 1);
    head.writeUInt16LE(1, e + 4);
    head.writeUInt16LE(32, e + 6);
    head.writeUInt32LE(data.length, e + 8);
    head.writeUInt32LE(offset, e + 12);
    offset += data.length;
  });
  return Buffer.concat([head, ...images.map((x) => x.data)]);
}

const SMALL = logoSvg("small");
const PLAIN = logoSvg("plain");
const WORN = logoSvg("worn");
const WORN_LIGHT = logoSvg("worn", { cut: "through" });
const APPLE = appIconSvg("apple");
const MASKABLE = appIconSvg("maskable");

async function main() {
  const out = {};
  const write = (dir, rel, data) => {
    const file = path.join(dir, rel);
    mkdirSync(path.dirname(file), { recursive: true });
    writeFileSync(file, data);
    out[path.relative(path.join(ROOT, ".."), file).replaceAll("\\", "/")] = data;
  };
  write(PUBLIC, "favicon.svg", SMALL + "\n");
  const tab = { 16: await png(SMALL, 16), 32: await png(SMALL, 32), 48: await png(PLAIN, 48) };
  write(PUBLIC, "favicon-16x16.png", tab[16]);
  write(PUBLIC, "favicon-32x32.png", tab[32]);
  const icoData = ico([16, 32, 48].map((size) => ({ size, data: tab[size] })));
  write(PUBLIC, "icon.ico", icoData);
  write(PUBLIC, "favicon.ico", icoData);
  write(PUBLIC, "apple-touch-icon.png", await png(APPLE, 180));
  for (const size of [192, 512]) write(PUBLIC, `android-chrome-${size}x${size}.png`, await png(WORN, size));
  for (const size of [192, 256, 384, 512]) write(PUBLIC, `icons/icon-${size}x${size}.png`, await png(WORN, size));
  write(PUBLIC, "icons/maskable.png", await png(MASKABLE, 512));
  write(README_DIR, "seal.svg", WORN + "\n");
  write(README_DIR, "seal-light.svg", WORN_LIGHT + "\n");

  const sheet = process.argv[2];
  if (sheet) {
    const tiles = [
      [tab[16], 16],
      [tab[32], 32],
      [tab[48], 48],
      [out["client/public/apple-touch-icon.png"], 180],
      [out["client/public/icons/icon-192x192.png"], 192],
      [out["client/public/icons/maskable.png"], 256],
    ];
    const W = 16 + tiles.reduce((a, [, s]) => a + s + 24, 0);
    const H = 2 * (256 + 40);
    const layers = [];
    for (const [band, bg] of [
      [0, "#202124"],
      [1, "#dee1e6"],
    ]) {
      layers.push({ input: { create: { width: W, height: H / 2, channels: 4, background: bg } }, left: 0, top: band * (H / 2) });
      let x = 16;
      for (const [data, size] of tiles) {
        layers.push({ input: await sharp(data).resize(size, size).png().toBuffer(), left: x, top: band * (H / 2) + 20 });
        x += size + 24;
      }
    }
    await sharp({ create: { width: W, height: H, channels: 4, background: "#000" } }).composite(layers).png().toFile(sheet);
  }
  console.log(Object.keys(out).map((k) => `${k} ${out[k].length} B`).join("\n"));
}

await main();
