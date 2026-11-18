import { describe, expect, it, vi } from "vitest";
import { parseMusicManifest, type MusicManifest } from "./music";
import {
  AUDIO_CACHE,
  MANIFEST_KEY,
  audioCacheUrl,
  cachedMusicBytes,
  openAudioCache,
  pruneCachedAudio,
  readCachedAudio,
  readSavedManifest,
  writeCachedAudio,
  writeSavedManifest,
  type AudioCache,
} from "./music-cache";

const ORIGIN = "https://site.example";

/** Cache Storage's cache, in memory: entries by absolute URL, as a browser lists them. */
class FakeCache implements AudioCache {
  entries = new Map<string, Uint8Array>();
  failPut = false;
  private abs(url: string) {
    return new URL(url, ORIGIN).href;
  }
  async match(url: string) {
    const bytes = this.entries.get(this.abs(url));
    return bytes ? new Response(bytes.slice()) : undefined;
  }
  async put(url: string, response: Response) {
    if (this.failPut) throw new Error("QuotaExceededError");
    this.entries.set(this.abs(url), new Uint8Array(await response.arrayBuffer()));
  }
  async delete(url: string) {
    return this.entries.delete(this.abs(url));
  }
  async keys() {
    return [...this.entries.keys()].map((url) => ({ url }));
  }
}

function memoryStorage(initial: Record<string, string> = {}) {
  const map = new Map(Object.entries(initial));
  return {
    map,
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => void map.set(k, v),
    removeItem: (k: string) => void map.delete(k),
  };
}

const entry = (bytes: number, revision = "20261108-1") => ({
  title: "Song",
  artist: "Artist",
  show: "Show",
  language: null,
  hasLyrics: false,
  revision,
  duration: 60,
  loopStart: 0,
  loopEnd: 60,
  bpm: null,
  lufs: -17,
  bytes,
});

const MANIFEST = parseMusicManifest({ version: 2, tracks: { loading: entry(4), gate: entry(3) } }) as MusicManifest;
const gate = MANIFEST.tracks.gate!;
const bytesOf = (...n: number[]) => new Uint8Array(n).buffer as ArrayBuffer;

describe("the track list kept between visits", () => {
  it("round-trips through storage", () => {
    const storage = memoryStorage();
    expect(readSavedManifest(storage)).toBeNull();
    writeSavedManifest(storage, MANIFEST);
    expect(storage.map.has(MANIFEST_KEY)).toBe(true);
    expect(readSavedManifest(storage)).toEqual(MANIFEST);
  });

  it("forgets the kept list when the backend has no usable one", () => {
    const storage = memoryStorage();
    writeSavedManifest(storage, MANIFEST);
    writeSavedManifest(storage, null);
    expect(readSavedManifest(storage)).toBeNull();
  });

  it("reads rubbish, an old format or blocked storage as no list", () => {
    expect(readSavedManifest(memoryStorage({ [MANIFEST_KEY]: "{not json" }))).toBeNull();
    expect(readSavedManifest(memoryStorage({ [MANIFEST_KEY]: JSON.stringify({ version: 1, tracks: {} }) }))).toBeNull();
    expect(readSavedManifest(null)).toBeNull();
    const blocked = {
      getItem: () => {
        throw new Error("SecurityError");
      },
      setItem: () => {
        throw new Error("QuotaExceededError");
      },
      removeItem: () => {
        throw new Error("SecurityError");
      },
    };
    expect(readSavedManifest(blocked)).toBeNull();
    expect(() => writeSavedManifest(blocked, MANIFEST)).not.toThrow();
    expect(() => writeSavedManifest(blocked, null)).not.toThrow();
  });
});

describe("the tracks kept between visits", () => {
  it("names an entry by key, revision and size", () => {
    expect(audioCacheUrl("gate", gate)).toBe("/__sect-music/gate?r=20261108-1&b=3");
    expect(audioCacheUrl("gate", { revision: "r2", bytes: null })).toBe("/__sect-music/gate?r=r2&b=");
  });

  it("opens this site's cache, or none where the browser has no Cache Storage", async () => {
    const cache = new FakeCache();
    const open = vi.fn(async () => cache as unknown as Cache);
    await expect(openAudioCache({ open })).resolves.toBe(cache);
    expect(open).toHaveBeenCalledWith(AUDIO_CACHE);
    await expect(openAudioCache(null)).resolves.toBeNull();
    await expect(openAudioCache({ open: () => Promise.reject(new Error("SecurityError")) })).resolves.toBeNull();
  });

  it("keeps a download and reads it back", async () => {
    const cache = new FakeCache();
    await expect(readCachedAudio(cache, "gate", gate)).resolves.toBeNull();
    await writeCachedAudio(cache, "gate", gate, bytesOf(1, 2, 3));
    const kept = await readCachedAudio(cache, "gate", gate);
    expect([...new Uint8Array(kept!)]).toEqual([1, 2, 3]);
  });

  it("keeps a copy: the bytes handed to the decoder can be emptied", async () => {
    const cache = new FakeCache();
    const bytes = bytesOf(1, 2, 3);
    const kept = writeCachedAudio(cache, "gate", gate, bytes);
    // What decodeAudioData does to its input, right after the call returns.
    structuredClone(bytes, { transfer: [bytes] });
    expect(bytes.byteLength).toBe(0);
    await kept;
    expect([...new Uint8Array((await readCachedAudio(cache, "gate", gate))!)]).toEqual([1, 2, 3]);
  });

  it("does not keep a download of the wrong size, and throws a kept one away", async () => {
    const cache = new FakeCache();
    await writeCachedAudio(cache, "gate", gate, bytesOf(1, 2));
    await writeCachedAudio(cache, "gate", gate, bytesOf());
    expect(cache.entries.size).toBe(0);
    // A copy cut short on disk.
    cache.entries.set(`${ORIGIN}${audioCacheUrl("gate", gate)}`, new Uint8Array([1]));
    await expect(readCachedAudio(cache, "gate", gate)).resolves.toBeNull();
    expect(cache.entries.size).toBe(0);
  });

  it("a new revision never reads the old one's bytes", async () => {
    const cache = new FakeCache();
    await writeCachedAudio(cache, "gate", gate, bytesOf(1, 2, 3));
    await expect(readCachedAudio(cache, "gate", { ...gate, revision: "20261201-1" })).resolves.toBeNull();
  });

  it("forgets tracks the list no longer names and leaves the rest of the cache alone", async () => {
    const cache = new FakeCache();
    await writeCachedAudio(cache, "gate", gate, bytesOf(1, 2, 3));
    await writeCachedAudio(cache, "gate", { revision: "old", bytes: 2 }, bytesOf(1, 2));
    await writeCachedAudio(cache, "mirror", { revision: "20261108-1", bytes: 1 }, bytesOf(9));
    cache.entries.set(`${ORIGIN}/something-else`, new Uint8Array([7]));
    await pruneCachedAudio(cache, MANIFEST);
    expect([...cache.entries.keys()].sort()).toEqual([`${ORIGIN}/__sect-music/gate?r=20261108-1&b=3`, `${ORIGIN}/something-else`]);
    // No usable list from the backend: nothing of the music is kept.
    await pruneCachedAudio(cache, null);
    expect([...cache.entries.keys()]).toEqual([`${ORIGIN}/something-else`]);
  });

  it("without a cache, or with one that fails, nothing throws", async () => {
    await expect(readCachedAudio(null, "gate", gate)).resolves.toBeNull();
    await expect(writeCachedAudio(null, "gate", gate, bytesOf(1, 2, 3))).resolves.toBeUndefined();
    await expect(pruneCachedAudio(null, MANIFEST)).resolves.toBeUndefined();
    const full = new FakeCache();
    full.failPut = true;
    await expect(writeCachedAudio(full, "gate", gate, bytesOf(1, 2, 3))).resolves.toBeUndefined();
    const broken: AudioCache = {
      match: () => Promise.reject(new Error("broken")),
      put: () => Promise.reject(new Error("broken")),
      delete: () => Promise.reject(new Error("broken")),
      keys: () => Promise.reject(new Error("broken")),
    };
    await expect(readCachedAudio(broken, "gate", gate)).resolves.toBeNull();
    await expect(pruneCachedAudio(broken, MANIFEST)).resolves.toBeUndefined();
  });
});

describe("cachedMusicBytes", () => {
  it("downloads a track once, then plays the kept copy without the backend", async () => {
    const cache = new FakeCache();
    const download = vi.fn(async () => bytesOf(1, 2, 3));
    const first = await cachedMusicBytes({ cache, key: "gate", track: gate, download });
    expect([...new Uint8Array(first)]).toEqual([1, 2, 3]);
    await vi.waitFor(() => expect(cache.entries.size).toBe(1));
    const again = await cachedMusicBytes({ cache, key: "gate", track: gate, download });
    expect([...new Uint8Array(again)]).toEqual([1, 2, 3]);
    expect(download).toHaveBeenCalledTimes(1);
  });

  it("downloads every time where nothing can be kept, and passes a failed download on", async () => {
    const download = vi.fn(async () => bytesOf(1, 2, 3));
    await cachedMusicBytes({ cache: null, key: "gate", track: gate, download });
    await cachedMusicBytes({ cache: null, key: "gate", track: gate, download });
    expect(download).toHaveBeenCalledTimes(2);
    const failing = () => Promise.reject(new Error("music 503"));
    await expect(cachedMusicBytes({ cache: new FakeCache(), key: "gate", track: gate, download: failing })).rejects.toThrow("music 503");
  });
});
