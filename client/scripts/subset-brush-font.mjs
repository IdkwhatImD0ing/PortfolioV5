// Writes src/app/sect/assets/sect-brush.woff2, the /sect brush hand: Ma Shan Zheng (SIL Open Font
// License 1.1, assets/OFL-MaShanZheng.txt) cut down to the characters of BRUSH_GLYPHS in
// src/lib/sect/brush.ts. Run it after a place's Chinese name changes (a test says when).
//
//   node scripts/subset-brush-font.mjs path/to/MaShanZheng-Regular.ttf
//
// The full font: https://github.com/google/fonts/raw/main/ofl/mashanzheng/MaShanZheng-Regular.ttf
// Needs Python with fontTools and brotli (pip install fonttools brotli).
import { execFileSync } from "node:child_process";
import { readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ttf = process.argv[2];
if (!ttf) {
  console.error("usage: node scripts/subset-brush-font.mjs path/to/MaShanZheng-Regular.ttf");
  process.exit(1);
}
const source = readFileSync(path.join(root, "src/lib/sect/brush.ts"), "utf8");
const glyphs = /BRUSH_GLYPHS = "([^"]+)"/.exec(source)?.[1];
if (!glyphs) throw new Error("BRUSH_GLYPHS not found in src/lib/sect/brush.ts");
const out = path.join(root, "src/app/sect/assets/sect-brush.woff2");
execFileSync(
  process.env.PYTHON ?? "python",
  [
    "-m",
    "fontTools.subset",
    ttf,
    `--text=${glyphs}`,
    "--flavor=woff2",
    // Ideographs need no shaping; keep the names that carry the copyright and the licence.
    "--layout-features=",
    "--name-IDs=0,1,2,3,4,5,6,13,14",
    "--no-hinting",
    "--desubroutinize",
    `--output-file=${out}`,
  ],
  { stdio: "inherit" },
);
console.log(`${path.relative(root, out)}: ${[...glyphs].length} characters, ${statSync(out).size} bytes`);
