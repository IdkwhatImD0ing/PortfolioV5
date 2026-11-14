/**
 * /music's pieces as the server draws them: the song list in the flight's order with the open song
 * marked, and the bar of controls saying what each button will do.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MUSIC_KEYS, parseMusicManifest, type MusicManifest } from "@/lib/sect/music";
import { SongList, Transport } from "./music-player";
import { PLAYER_OFF, type PlayerUi, type SongPlayer } from "./song-player";

/** The repo's own track list, as the backend serves it. */
function manifest(): MusicManifest {
  const raw = JSON.parse(readFileSync(join(__dirname, "..", "..", "..", "..", "server", "music_manifest.json"), "utf8")) as {
    tracks: Record<string, Record<string, unknown>>;
  };
  const tracks = Object.fromEntries(Object.entries(raw.tracks).map(([key, t]) => [key, { ...t, hasLyrics: Boolean(t.lyricsObject) }]));
  const parsed = parseMusicManifest({ version: 2, tracks });
  if (!parsed) throw new Error("no manifest");
  return parsed;
}

const text = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
/** Enough of a player to draw the bar: nothing here is called while rendering. */
const player = { subscribe: () => () => {}, subscribeTime: () => () => {}, position: () => 0 } as unknown as SongPlayer;
const bar = (ui: Partial<PlayerUi>) => renderToStaticMarkup(<Transport player={player} ui={{ ...PLAYER_OFF, song: "arena", duration: 240, ...ui }} />);

describe("SongList", () => {
  it("lists every song in the flight's order, with its English and its length", () => {
    const html = renderToStaticMarkup(<SongList manifest={manifest()} current="arena" onChoose={() => {}} />);
    expect(html.match(/<button/g)).toHaveLength(MUSIC_KEYS.length);
    const words = text(html);
    expect(words.indexOf("风舞")).toBeLessThan(words.indexOf("铁血丹心"));
    expect(words.indexOf("铁血丹心")).toBeLessThan(words.indexOf("Throne of Glory"));
    expect(words).toContain("降临 Descent 3:59");
    // A title already in English has no second line.
    expect(html).toMatch(/<span class="music-song-latin">Throne of Glory<\/span><\/span>/);
  });

  it("marks the open song, and only that one", () => {
    const html = renderToStaticMarkup(<SongList manifest={manifest()} current="arena" onChoose={() => {}} />);
    expect(html.match(/aria-current="true"/g)).toHaveLength(1);
    expect(html).toMatch(/aria-current="true"[^>]*>.*?降临/);
  });
});

describe("Transport", () => {
  it("offers play while paused and pause while playing", () => {
    expect(bar({ playing: false })).toContain('aria-label="Play"');
    expect(bar({ playing: true })).toContain('aria-label="Pause"');
    expect(bar({})).toContain('aria-label="Previous"');
    expect(bar({})).toContain('aria-label="Next"');
  });

  it("turns the ink ring while the song's file is on its way", () => {
    expect(bar({ playing: true, loading: true })).toContain("sect-enso");
    expect(bar({ playing: true, loading: false })).not.toContain("sect-enso");
  });

  it("shows the song's length and where it is", () => {
    const html = bar({ duration: 247 });
    expect(text(html)).toContain("0:00");
    expect(text(html)).toContain("4:07");
    expect(html).toContain('aria-valuetext="0 seconds of 4 minutes 7 seconds"');
  });

  it("says whether repeat is on", () => {
    expect(bar({ repeat: false })).toMatch(/aria-label="Repeat this song" aria-pressed="false"/);
    expect(bar({ repeat: true })).toMatch(/aria-label="Repeat this song" aria-pressed="true"/);
  });

  it("offers the sound back when it is muted or at zero, and mute otherwise", () => {
    expect(bar({ volume: 0.8 })).toContain('aria-label="Mute"');
    expect(bar({ volume: 0.8, muted: true })).toContain('aria-label="Sound on"');
    expect(bar({ volume: 0 })).toContain('aria-label="Sound on"');
    // Muted, the volume line rests at zero and says so.
    expect(bar({ volume: 0.8, muted: true })).toMatch(/aria-label="Volume" aria-valuetext="Muted"/);
    expect(bar({ volume: 0.8 })).toMatch(/value="80"/);
  });

  it("leaves the volume line out where the browser will not let a page set it", () => {
    expect(bar({ volumeSettable: false })).not.toContain('aria-label="Volume"');
    expect(bar({ volumeSettable: false })).toContain('aria-label="Mute"');
  });
});

describe("music.css", () => {
  const css = readFileSync(join(__dirname, "music.css"), "utf8");

  it("keeps the bar of controls at the foot of a scrolling page", () => {
    expect(css).toMatch(/\.music \.music-bar \{[^}]*position: sticky;[^}]*bottom: var\(--music-foot\);/);
  });

  it("lets an up and down drag on a seek or volume line scroll the page", () => {
    expect(css).toMatch(/\.music-range \{[^}]*touch-action: pan-y;/);
  });
});
