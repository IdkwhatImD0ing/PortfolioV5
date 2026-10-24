/**
 * Draws every icon file from the site's logo (src/lib/sect/logo.ts: the sect's seal, a sun cradled in
 * a crescent moon, on cinnabar).
 *
 *   node scripts/make-icons.mjs [contact-sheet.png]
 *
 * Writes public/favicon.svg (the bold drawing), public/favicon-16x16.png, public/favicon-32x32.png,
 * public/icon.ico and public/favicon.ico (16, 32 and 48 px, bold), public/apple-touch-icon.png (180,
 * the full seal on the sect's ink: iOS rounds the corners and fills transparency with black),
 * public/android-chrome-*.png and public/icons/icon-*.png (the full seal), and public/icons/maskable.png
 * (the full seal inside the circle a launcher may crop a maskable icon to, on ink). With a path, also
 * a sheet of every size on a dark and a light tab strip, to look at.
 *
 * Needs Node 22.18+ (it imports the .ts module directly). sharp comes with Next (it is not a
 * dependency of its own), so it is loaded from there.
 */
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { LOGO_COLORS, logoSvg } from "../src/lib/sect/logo.ts";

const require = createRequire(import.meta.url);
const sharp = createRequire(require.resolve("next/package.json"))("sharp");

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PUBLIC = path.join(ROOT, "public");

async function png(svg, size) {
  return sharp(Buffer.from(svg), { density: Math.max(72, (72 * size) / 64) * 4 })
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

const TAB = logoSvg({ bold: true });
const FULL = logoSvg();
const MASKABLE = logoSvg({ ground: LOGO_COLORS.ink, reach: 0.6 });
const APPLE = logoSvg({ ground: LOGO_COLORS.ink, reach: 0.8 });

async function main() {
  const out = {};
  const write = (rel, data) => {
    const file = path.join(PUBLIC, rel);
    mkdirSync(path.dirname(file), { recursive: true });
    writeFileSync(file, data);
    out[rel] = data;
  };
  write("favicon.svg", TAB + "\n");
  const tab = {};
  for (const size of [16, 32, 48]) tab[size] = await png(TAB, size);
  write("favicon-16x16.png", tab[16]);
  write("favicon-32x32.png", tab[32]);
  const icoData = ico([16, 32, 48].map((size) => ({ size, data: tab[size] })));
  write("icon.ico", icoData);
  write("favicon.ico", icoData);
  write("apple-touch-icon.png", await png(APPLE, 180));
  for (const size of [192, 512]) write(`android-chrome-${size}x${size}.png`, await png(FULL, size));
  for (const size of [192, 256, 384, 512]) write(`icons/icon-${size}x${size}.png`, await png(FULL, size));
  write("icons/maskable.png", await png(MASKABLE, 512));

  const sheet = process.argv[2];
  if (sheet) {
    const tiles = [
      ["favicon-16x16.png", 16],
      ["favicon-32x32.png", 32],
      [null, 48],
      ["apple-touch-icon.png", 180],
      ["icons/icon-192x192.png", 192],
      ["icons/maskable.png", 256],
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
      for (const [rel, size] of tiles) {
        const data = rel ? await sharp(out[rel]).resize(size, size).png().toBuffer() : tab[48];
        layers.push({ input: data, left: x, top: band * (H / 2) + 20 });
        x += size + 24;
      }
    }
    await sharp({ create: { width: W, height: H, channels: 4, background: "#000" } }).composite(layers).png().toFile(sheet);
  }
  console.log(Object.keys(out).map((k) => `${k} ${out[k].length} B`).join("\n"));
}

await main();
