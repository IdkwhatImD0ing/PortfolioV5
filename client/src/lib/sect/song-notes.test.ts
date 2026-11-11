import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { MUSIC_KEYS, isMusicKey, type MusicKey } from "./music";
import { SONG_NOTES, SONG_TITLES_EN, hasHan, songCredits, songNote, songTitleEn } from "./song-notes";

/** The nine sung tracks (docs/music/local-soundtrack.md). */
const VOCAL_KEYS: readonly MusicKey[] = ["mirror", "arena", "mission", "library", "steles", "scroll", "formation", "abode", "summit"];

describe("song notes", () => {
  it("are keyed by real music keys", () => {
    for (const key of Object.keys(SONG_NOTES)) expect(isMusicKey(key), key).toBe(true);
  });

  it("cover the nine sung tracks, and no instrumental", () => {
    for (const key of VOCAL_KEYS) {
      expect(songNote(key)?.en.length, key).toBeGreaterThan(0);
      expect(hasHan(songNote(key)?.zh ?? ""), key).toBe(true);
    }
    for (const key of MUSIC_KEYS.filter((k) => !VOCAL_KEYS.includes(k))) expect(songNote(key), key).toBeNull();
  });

  it("match the tracks the backend serves lyrics for", () => {
    // server/music_manifest.json: a track with a lyric file is sung.
    const manifest = JSON.parse(readFileSync(join(__dirname, "../../../../server/music_manifest.json"), "utf8")) as {
      tracks: Record<string, { lyricsObject: string | null }>;
    };
    const sung = Object.entries(manifest.tracks)
      .filter(([, t]) => t.lyricsObject)
      .map(([key]) => key)
      .sort();
    expect(sung).toEqual([...VOCAL_KEYS].sort());
  });

  it("are never in the first person", () => {
    for (const note of Object.values(SONG_NOTES)) {
      expect(note?.en).not.toMatch(/(I|my|me|mine|myself)/);
      expect(note?.zh).not.toContain("我");
    }
  });

  it("keep the owner's curly apostrophe", () => {
    expect(songNote("mirror")?.en).toContain("it’s better");
  });
});

describe("song titles in English", () => {
  it("cover every track but the one already titled in English", () => {
    for (const key of Object.keys(SONG_TITLES_EN)) expect(isMusicKey(key), key).toBe(true);
    for (const key of MUSIC_KEYS) {
      if (key === "mirror") expect(songTitleEn(key)).toBeNull();
      else expect(songTitleEn(key)?.length, key).toBeGreaterThan(0);
    }
  });

  it("are plain English", () => {
    for (const title of Object.values(SONG_TITLES_EN)) expect(hasHan(title ?? "")).toBe(false);
  });
});

describe("songCredits", () => {
  it("leaves out an artist the source does not name", () => {
    expect(songCredits({ show: "射雕英雄传 2017", artist: "Not credited", language: null })).toEqual({
      show: "射雕英雄传 2017",
      artist: null,
      sung: "Instrumental",
    });
  });

  it("says what language a sung track is in", () => {
    expect(songCredits({ show: "神印王座", artist: "Qi You (祁游)", language: "zh" })).toEqual({
      show: "神印王座",
      artist: "Qi You (祁游)",
      sung: "Sung in Chinese",
    });
    expect(songCredits({ show: "神印王座", artist: "Xian Ke", language: "en" }).sung).toBe("Sung in English");
  });
});

describe("hasHan", () => {
  it("tells Chinese titles from Latin ones", () => {
    expect(hasHan("降临")).toBe(true);
    expect(hasHan("斗罗大陆2")).toBe(true);
    expect(hasHan("Throne of Glory")).toBe(false);
    expect(hasHan("Qi You")).toBe(false);
  });
});
