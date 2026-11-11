import { describe, expect, it } from "vitest";
import { lyricLineAt, lyricUnitProgress, lyricWordAt, parseLyrics } from "./lyrics";

const raw = {
  song: "降临",
  show: "神印王座",
  language: "zh",
  lines: [
    {
      start: 1,
      end: 3,
      text: "光。",
      pinyin: "guāng",
      en: "Light.",
      words: [
        { w: "光。", start: 1, end: 3 },
      ],
    },
    {
      start: 5,
      end: 7,
      text: "来",
      pinyin: "lái",
      en: "Come",
      words: [{ w: "来", start: 5, end: 5 }],
    },
  ],
};

describe("timed lyrics", () => {
  it("parses the public allowlisted payload and preserves exact units", () => {
    const lyrics = parseLyrics(raw, "arena");
    expect(lyrics).not.toBeNull();
    expect(lyrics?.lines[0].words.map((word) => word.w).join("")).toBe("光。");
    expect(lyrics).toMatchObject({ key: "arena", song: "降临", language: "zh" });
  });

  it("finds half-open lines and leaves lyric gaps empty", () => {
    const lines = parseLyrics(raw, "arena")!.lines;
    expect(lyricLineAt(lines, 1)?.index).toBe(0);
    expect(lyricLineAt(lines, 2.999)?.index).toBe(0);
    expect(lyricLineAt(lines, 3)).toBeNull();
    expect(lyricLineAt(lines, 4)).toBeNull();
    expect(lyricLineAt(lines, 5)?.index).toBe(1);
    expect(lyricLineAt(lines, 7)).toBeNull();
  });

  it("clamps karaoke progress and fills zero-length units instantly", () => {
    const lines = parseLyrics(raw, "arena")!.lines;
    expect(lyricUnitProgress(lines[0].words[0], 0)).toBe(0);
    expect(lyricUnitProgress(lines[0].words[0], 2)).toBe(0.5);
    expect(lyricUnitProgress(lines[0].words[0], 4)).toBe(1);
    expect(lyricUnitProgress(lines[1].words[0], 4.9)).toBe(0);
    expect(lyricUnitProgress(lines[1].words[0], 5)).toBe(1);
    expect(lyricWordAt(lines[0].words, 1.5)).toBe(0);
  });

  it("rejects overlaps, timing escapes and text that words do not reconstruct", () => {
    expect(parseLyrics({ ...raw, lines: [{ ...raw.lines[0], text: "different" }] }, "arena")).toBeNull();
    expect(
      parseLyrics(
        {
          ...raw,
          lines: [
            raw.lines[0],
            { ...raw.lines[1], start: 2.5 },
          ],
        },
        "arena",
      ),
    ).toBeNull();
    expect(
      parseLyrics(
        {
          ...raw,
          lines: [{ ...raw.lines[0], words: [{ w: "光。", start: 0, end: 3 }] }],
        },
        "arena",
      ),
    ).toBeNull();
  });
});
