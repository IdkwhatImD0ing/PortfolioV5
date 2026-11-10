// Writes src/app/sect/assets/sect-lyrics-brush.woff2: Ma Shan Zheng (SIL Open Font License 1.1,
// assets/OFL-MaShanZheng.txt) cut down to the Chinese characters the soundtrack panel writes: every
// lyric line, each song's title, show and artist, and the notes in src/lib/sect/song-notes.ts. The panel loads it only once it is opened
// (sect.css "Sect Lyric Brush"). A character the file lacks falls back to the serif, so run this
// again after the songs or their lyrics change.
//
//   node scripts/subset-lyrics-font.mjs path/to/MaShanZheng-Regular.ttf path/to/prepared-music
//
// The prepared folder is the one prepare_music.py writes (server/.music-prepared): music_manifest.json
// and lyrics/*.json. The full font: https://github.com/google/fonts/raw/main/ofl/mashanzheng/MaShanZheng-Regular.ttf
// Needs Python with fontTools and brotli (pip install fonttools brotli).
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const [ttf, prepared] = process.argv.slice(2);
if (!ttf || !prepared) {
  console.error("usage: node scripts/subset-lyrics-font.mjs path/to/MaShanZheng-Regular.ttf path/to/prepared-music");
  process.exit(1);
}
const python = process.env.PYTHON ?? "python";

const chars = new Set();
const take = (text) => {
  // CJK ideographs and CJK punctuation; Latin stays in the page's own faces.
  for (const c of String(text ?? "")) if (c.codePointAt(0) >= 0x2e80) chars.add(c);
};
const manifest = JSON.parse(readFileSync(path.join(prepared, "music_manifest.json"), "utf8"));
for (const track of Object.values(manifest.tracks)) {
  take(track.title);
  take(track.show);
  take(track.artist);
}
const lyricsDir = path.join(prepared, "lyrics");
for (const name of readdirSync(lyricsDir).filter((n) => n.endsWith(".json"))) {
  const song = JSON.parse(readFileSync(path.join(lyricsDir, name), "utf8"));
  for (const line of song.lines) take(line.text);
}
// The owner's notes in Chinese (the panel writes them in this hand too).
take(readFileSync(path.join(root, "src/lib/sect/song-notes.ts"), "utf8"));
const text = [...chars].sort().join("");
const textFile = path.join(mkdtempSync(path.join(tmpdir(), "sect-lyrics-")), "chars.txt");
writeFileSync(textFile, text, "utf8");

const out = path.join(root, "src/app/sect/assets/sect-lyrics-brush.woff2");
execFileSync(
  python,
  [
    "-m",
    "fontTools.subset",
    ttf,
    `--text-file=${textFile}`,
    "--flavor=woff2",
    "--layout-features=",
    "--name-IDs=0,1,2,3,4,5,6,13,14",
    "--no-hinting",
    "--desubroutinize",
    `--output-file=${out}`,
  ],
  { stdio: "inherit" },
);
console.log(`${path.relative(root, out)}: ${chars.size} characters, ${statSync(out).size} bytes`);
