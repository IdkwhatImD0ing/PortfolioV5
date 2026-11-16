import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { MUSIC_KEYS, isMusicKey, type MusicKey } from "./music";
import { NOTE_COLUMN, SONG_NOTES, SONG_TITLES_EN, hasHan, noteColumns, songCredits, songNote, songTitleEn } from "./song-notes";

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

describe("a note's Chinese in columns", () => {
  const notes = Object.entries(SONG_NOTES).map(([key, note]) => ({ key, zh: note?.zh ?? "", columns: noteColumns(note?.zh ?? "") }));

  it("keeps every character, in order", () => {
    for (const { key, zh, columns } of notes) expect(columns.join(""), key).toBe(zh);
  });

  it("opens no column with a comma or a full stop", () => {
    for (const { key, columns } of notes) for (const column of columns) expect(column, key).not.toMatch(/^[，。、]/);
  });

  it("fills the columns evenly: none a stub, none longer than a full column and one hanging mark", () => {
    for (const { key, columns } of notes) {
      for (const column of columns) {
        expect([...column].length, key).toBeGreaterThanOrEqual(NOTE_COLUMN - 2);
        expect([...column].length, key).toBeLessThanOrEqual(NOTE_COLUMN + 1);
        // One past the full length is only ever a mark hanging under the last character.
        if ([...column].length > NOTE_COLUMN) expect(column, key).toMatch(/[，。、]$/);
      }
    }
  });

  it("takes no more columns than the drawer holds at full size", () => {
    // sect.css: a column is 1.5 × 1.3rem wide and the note 20.2rem, so ten fit; eight leaves margins.
    for (const { key, columns } of notes) expect(columns.length, key).toBeLessThanOrEqual(8);
  });

  it("sends a column's last character over with the mark, where the columns after it have room", () => {
    // 天地玄黄宇宙洪 would be a full column with the comma opening the next.
    expect(noteColumns("天地玄黄宇宙洪，荒日月盈昃", 7)).toEqual(["天地玄黄宇宙", "洪，荒日月盈昃"]);
  });

  it("hangs the mark under a full column when every column is full", () => {
    expect(noteColumns("天地玄黄宇宙洪，荒日月盈昃辰", 7)).toEqual(["天地玄黄宇宙洪，", "荒日月盈昃辰"]);
  });

  it("writes a short note in one column, and nothing for an empty one", () => {
    expect(noteColumns("日月神教")).toEqual(["日月神教"]);
    expect(noteColumns("")).toEqual([]);
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
