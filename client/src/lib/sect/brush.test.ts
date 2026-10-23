import { readFileSync } from "node:fs";
import path from "node:path";
import { brotliDecompressSync } from "node:zlib";
import { describe, expect, it } from "vitest";
import { AREAS } from "./areas";
import { BRUSH_EXTRA, BRUSH_GLYPHS, BRUSH_INK, brushCovers, brushSpacing, brushText } from "./brush";

const FONT = path.resolve(__dirname, "../../app/sect/assets/sect-brush.woff2");

/** WOFF2's variable-length unsigned integer. */
function base128(b: Buffer, at: { i: number }): number {
  let v = 0;
  for (let k = 0; k < 5; k++) {
    const x = b[at.i++];
    v = v * 128 + (x & 0x7f);
    if (!(x & 0x80)) return v;
  }
  throw new Error("bad UIntBase128");
}

/**
 * The code points a WOFF2 font maps to a glyph: its cmap table (index 0 of WOFF2's known tags, never
 * transformed), read from the one brotli stream that holds every table, format 4 or 12.
 */
function woff2CodePoints(file: Buffer): Set<number> {
  expect(file.toString("latin1", 0, 4)).toBe("wOF2");
  const numTables = file.readUInt16BE(12);
  const compressed = file.readUInt32BE(20);
  const at = { i: 48 };
  let offset = 0;
  let cmap: { offset: number; length: number } | null = null;
  for (let t = 0; t < numTables; t++) {
    const flags = file[at.i++];
    const tagIndex = flags & 0x3f;
    if (tagIndex === 0x3f) at.i += 4;
    const version = (flags >> 6) & 3;
    const origLength = base128(file, at);
    // glyf (10) and loca (11) are transformed at version 0; every other table at any other version.
    const transformed = tagIndex === 10 || tagIndex === 11 ? version === 0 : version !== 0;
    const length = transformed ? base128(file, at) : origLength;
    if (tagIndex === 0) cmap = { offset, length };
    offset += length;
  }
  if (!cmap) throw new Error("no cmap");
  const data = brotliDecompressSync(file.subarray(at.i, at.i + compressed));
  const c = data.subarray(cmap.offset, cmap.offset + cmap.length);
  const points = new Set<number>();
  const records = c.readUInt16BE(2);
  for (let r = 0; r < records; r++) {
    const sub = c.subarray(c.readUInt32BE(4 + 8 * r + 4));
    const format = sub.readUInt16BE(0);
    if (format === 4) {
      const seg = sub.readUInt16BE(6) / 2;
      const ends = 14;
      const starts = ends + 2 * seg + 2;
      const deltas = starts + 2 * seg;
      const ranges = deltas + 2 * seg;
      for (let s = 0; s < seg; s++) {
        const end = sub.readUInt16BE(ends + 2 * s);
        const start = sub.readUInt16BE(starts + 2 * s);
        const delta = sub.readInt16BE(deltas + 2 * s);
        const range = sub.readUInt16BE(ranges + 2 * s);
        for (let cp = start; cp <= end && cp !== 0xffff; cp++) {
          const glyph = range === 0 ? (cp + delta) & 0xffff : sub.readUInt16BE(ranges + 2 * s + range + 2 * (cp - start));
          if (glyph !== 0) points.add(cp);
        }
      }
    } else if (format === 12) {
      const groups = sub.readUInt32BE(12);
      for (let g = 0; g < groups; g++) {
        const start = sub.readUInt32BE(16 + 12 * g);
        const end = sub.readUInt32BE(20 + 12 * g);
        for (let cp = start; cp <= end; cp++) points.add(cp);
      }
    }
  }
  return points;
}

describe("the brush hand", () => {
  it("carries every place name and the sect's own name", () => {
    for (const a of AREAS) expect(brushCovers(a.zh), a.id).toBe(true);
    for (const t of BRUSH_EXTRA) expect(brushCovers(t), t).toBe(true);
  });

  it("carries those characters and no others, each once (the subset stays as small as it can)", () => {
    expect(BRUSH_GLYPHS).toBe(brushText());
    expect(new Set(BRUSH_GLYPHS).size).toBe([...BRUSH_GLYPHS].length);
  });

  it("leaves to the serif any text it cannot write whole", () => {
    expect(brushCovers("")).toBe(false);
    // The Jin Yong references are traditional characters, never in the subset.
    expect(brushCovers("劍塚")).toBe(false);
    expect(brushCovers("日月")).toBe(true);
    expect(brushCovers("日月劍")).toBe(false);
    // The sect's old name: 明 left the subset with it.
    expect(brushCovers("明教")).toBe(false);
  });

  it("knows where every character's ink sits, and nothing else (scripts/subset-brush-font.mjs writes both)", () => {
    expect(Object.keys(BRUSH_INK).sort()).toEqual([...BRUSH_GLYPHS].sort());
    for (const [ch, side] of Object.entries(BRUSH_INK)) {
      expect(side, ch).toHaveLength(2);
      for (const v of side) expect(v >= 0 && v < 0.5, ch).toBe(true);
    }
  });

  it("sets a name's characters evenly apart, ink to ink, its box trimmed to the ink", () => {
    const name = "日月神教";
    const gap = 0.1;
    const s = brushSpacing(name, gap)!;
    const ink = [...name].map((c) => BRUSH_INK[c]);
    expect(s.start).toBeCloseTo(-ink[0][0], 9);
    expect(s.after).toHaveLength(4);
    // Between two characters: the margin plus the paper either side is the gap, whatever the glyphs.
    for (let i = 0; i < 3; i++) expect(s.after[i] + ink[i][1] + ink[i + 1][0], `${name[i]}${name[i + 1]}`).toBeCloseTo(gap, 9);
    expect(s.after[3]).toBeCloseTo(-ink[3][1], 9);
    // Tracking alone leaves 日 standing off from 月神教: its paper is several times 教's.
    expect(ink[0][1] + ink[1][0]).toBeGreaterThan(3 * (ink[2][1] + ink[3][0]));
  });

  it("leaves the spacing alone where the brush cannot write the name", () => {
    expect(brushSpacing("明教", 0.1)).toBeNull();
    expect(brushSpacing("", 0.1)).toBeNull();
  });

  it("matches the font that ships: every character has a glyph, and the file stays small", () => {
    const file = readFileSync(FONT);
    const points = woff2CodePoints(file);
    // A failure here: run scripts/subset-brush-font.mjs after changing a name.
    for (const ch of BRUSH_GLYPHS) expect(points.has(ch.codePointAt(0)!), ch).toBe(true);
    expect(file.length).toBeLessThan(24 * 1024);
  });
});
