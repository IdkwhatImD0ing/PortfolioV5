import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { MUSIC_KEYS, isMusicKey, type MusicKey } from "./music";
import { SONG_NOTES, hasHan, songCredits, songNote } from "./song-notes";

/** The eight sung tracks (docs/music/local-soundtrack.md). */
const VOCAL_KEYS: readonly MusicKey[] = ["mirror", "arena", "mission", "library", "steles", "scroll", "abode", "summit"];

describe("song notes", () => {
  it("are keyed by real music keys", () => {
    for (const key of Object.keys(SONG_NOTES)) expect(isMusicKey(key), key).toBe(true);
  });

  it("cover the eight sung tracks, and no instrumental", () => {
    for (const key of VOCAL_KEYS) expect(songNote(key)?.length, key).toBeGreaterThan(0);
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

  it("keep the owner's curly apostrophe", () => {
    expect(songNote("mirror")).toContain("it’s better");
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
