import { describe, expect, it } from "vitest";
import { parseMusicManifest, type MusicKey } from "./music";
import {
  afterEnd,
  clampSeek,
  clock,
  clockWords,
  elementVolume,
  playerCommand,
  previousRestarts,
  silentClip,
  songFromHash,
  songList,
  stepSong,
} from "./player";

const track = { title: "T", artist: "A", show: "S", language: null, revision: "r1", duration: 60, loopStart: 0, loopEnd: 60 };
const LIST: MusicKey[] = ["loading", "gate", "arena"];

describe("songList", () => {
  it("lists the manifest's songs in the flight's order", () => {
    const manifest = parseMusicManifest({ version: 2, tracks: { summit: track, loading: track, forge: track } });
    expect(songList(manifest)).toEqual(["loading", "forge", "summit"]);
  });

  it("is empty without a manifest", () => {
    expect(songList(null)).toEqual([]);
  });
});

describe("stepSong", () => {
  it("steps along the list and round its ends", () => {
    expect(stepSong(LIST, "loading", 1)).toBe("gate");
    expect(stepSong(LIST, "arena", 1)).toBe("loading");
    expect(stepSong(LIST, "loading", -1)).toBe("arena");
  });

  it("starts at an end when nothing in the list is current", () => {
    expect(stepSong(LIST, null, 1)).toBe("loading");
    expect(stepSong(LIST, "summit", -1)).toBe("arena");
    expect(stepSong([], "gate", 1)).toBeNull();
  });
});

describe("previous and a song's end", () => {
  it("goes back to the song's start only once it has played a few seconds", () => {
    expect(previousRestarts(0.5)).toBe(false);
    expect(previousRestarts(3)).toBe(false);
    expect(previousRestarts(3.1)).toBe(true);
  });

  it("plays the next song at the end, or the same one with Repeat on", () => {
    expect(afterEnd(LIST, "gate", false)).toBe("arena");
    expect(afterEnd(LIST, "arena", false)).toBe("loading");
    expect(afterEnd(LIST, "gate", true)).toBe("gate");
    expect(afterEnd([], null, true)).toBeNull();
  });
});

describe("songFromHash", () => {
  it("reads a listed song from the hash", () => {
    expect(songFromHash("#arena", LIST)).toBe("arena");
    expect(songFromHash("arena", LIST)).toBe("arena");
  });

  it("ignores a song the list lacks, and nonsense", () => {
    expect(songFromHash("#summit", LIST)).toBeNull();
    expect(songFromHash("#projects", LIST)).toBeNull();
    expect(songFromHash("", LIST)).toBeNull();
  });
});

describe("times", () => {
  it("writes minutes and two-digit seconds", () => {
    expect(clock(0)).toBe("0:00");
    expect(clock(7.9)).toBe("0:07");
    expect(clock(247.2)).toBe("4:07");
    expect(clock(Number.NaN)).toBe("0:00");
    expect(clock(-3)).toBe("0:00");
  });

  it("says a time in words", () => {
    expect(clockWords(0)).toBe("0 seconds");
    expect(clockWords(1)).toBe("1 second");
    expect(clockWords(65)).toBe("1 minute 5 seconds");
    expect(clockWords(120)).toBe("2 minutes");
  });

  it("keeps a seek inside the song", () => {
    expect(clampSeek(-4, 100)).toBe(0);
    expect(clampSeek(40, 100)).toBe(40);
    expect(clampSeek(140, 100)).toBe(100);
    expect(clampSeek(40, Number.NaN)).toBe(0);
  });
});

describe("playerCommand", () => {
  it("maps the page's keys", () => {
    expect(playerCommand({ key: " " }, false)).toBe("toggle");
    expect(playerCommand({ key: "ArrowLeft" }, false)).toBe("back");
    expect(playerCommand({ key: "ArrowRight" }, false)).toBe("forward");
    expect(playerCommand({ key: "m" }, false)).toBe("mute");
    expect(playerCommand({ key: "Enter" }, false)).toBeNull();
  });

  it("leaves a key to the control that has it, and to the browser's shortcuts", () => {
    expect(playerCommand({ key: " " }, true)).toBeNull();
    expect(playerCommand({ key: "ArrowLeft", altKey: true }, false)).toBeNull();
    expect(playerCommand({ key: "m", ctrlKey: true }, false)).toBeNull();
  });
});

describe("silentClip", () => {
  it("is a short WAV of silence", () => {
    const url = silentClip();
    expect(url.startsWith("data:audio/wav;base64,")).toBe(true);
    const bytes = Uint8Array.from(atob(url.split(",")[1]), (c) => c.charCodeAt(0));
    const ascii = (from: number, to: number) => String.fromCharCode(...bytes.slice(from, to));
    expect(ascii(0, 4)).toBe("RIFF");
    expect(ascii(8, 12)).toBe("WAVE");
    expect(ascii(36, 40)).toBe("data");
    expect(bytes.length).toBe(44 + 800);
    expect([...bytes.slice(44)].every((b) => b === 128)).toBe(true);
  });
});

describe("elementVolume", () => {
  it("is the file's own level at 100% and the square below it", () => {
    expect(elementVolume(1)).toBe(1);
    expect(elementVolume(0.5)).toBeCloseTo(0.25);
    expect(elementVolume(0)).toBe(0);
  });
});
