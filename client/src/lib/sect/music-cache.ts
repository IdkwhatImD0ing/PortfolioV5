/**
 * What the browser keeps of the flight's music between visits: the track list from the last visit
 * (localStorage) and the tracks already downloaded (Cache Storage, this site's own).
 *
 * The backend sleeps when nobody has called it for a while and takes seconds to wake
 * (lib/backend-warmup.ts). Without these a returning visitor's music waits for it twice: once for
 * the list, once for the track. With them the list is there at once and a track heard before plays
 * without the backend at all. The list from the backend still replaces the kept one when it
 * arrives, and a track whose entry changed is downloaded again (see sameTrackFile).
 *
 * Nothing here throws: a browser without Cache Storage (an insecure origin, some private windows),
 * a full disk or a blocked localStorage only means the music is downloaded as before.
 *
 * The kept copies are the same bytes the page was already sent, in a store only this site reads
 * (docs/music/backend-soundtrack-delivery.md has what that changes about the deterrence boundary).
 */
import { parseMusicManifest, type MusicKey, type MusicManifest, type MusicTrack } from "./music";

/** localStorage key of the track list from the last visit (the parsed manifest, as JSON). */
export const MANIFEST_KEY = "sect.music.manifest";
/** The Cache Storage cache holding the tracks. A change of format takes a new name. */
export const AUDIO_CACHE = "sect-music-v1";
/** Path of a kept track's entry. Nothing is served there: it is only the entry's name. */
const AUDIO_PATH = "/__sect-music/";

/** The part of the Cache interface used here (a real Cache fits it). */
export interface AudioCache {
  match(url: string): Promise<Response | undefined>;
  put(url: string, response: Response): Promise<void>;
  delete(url: string): Promise<boolean>;
  keys(): Promise<readonly { url: string }[]>;
}

type FileId = Pick<MusicTrack, "revision" | "bytes">;

export function readSavedManifest(storage: Pick<Storage, "getItem"> | null | undefined): MusicManifest | null {
  try {
    const raw = storage?.getItem(MANIFEST_KEY);
    return raw ? parseMusicManifest(JSON.parse(raw)) : null;
  } catch {
    return null;
  }
}

/** Keeps the list for the next visit; no usable list (null) forgets the kept one. */
export function writeSavedManifest(
  storage: Pick<Storage, "setItem" | "removeItem"> | null | undefined,
  manifest: MusicManifest | null,
): void {
  try {
    if (manifest) storage?.setItem(MANIFEST_KEY, JSON.stringify(manifest));
    else storage?.removeItem(MANIFEST_KEY);
  } catch {
    // Storage blocked or full: the next visit asks the backend first, as before.
  }
}

/**
 * A kept track's entry name: the key with the file's revision and size, so a new revision of a
 * track never reads the old one's bytes.
 */
export function audioCacheUrl(key: MusicKey, track: FileId): string {
  return `${AUDIO_PATH}${key}?r=${encodeURIComponent(track.revision)}&b=${track.bytes ?? ""}`;
}

export async function openAudioCache(storage: Pick<CacheStorage, "open"> | null | undefined): Promise<AudioCache | null> {
  try {
    return storage ? await storage.open(AUDIO_CACHE) : null;
  } catch {
    return null;
  }
}

/** The kept bytes for this revision of a track, or null. A copy of the wrong size is thrown away. */
export async function readCachedAudio(cache: AudioCache | null, key: MusicKey, track: FileId): Promise<ArrayBuffer | null> {
  if (!cache) return null;
  const url = audioCacheUrl(key, track);
  try {
    const hit = await cache.match(url);
    if (!hit) return null;
    const bytes = await hit.arrayBuffer();
    if (bytes.byteLength > 0 && (track.bytes === null || bytes.byteLength === track.bytes)) return bytes;
    await cache.delete(url);
    return null;
  } catch {
    return null;
  }
}

/** Keeps a downloaded track (a download of the wrong size is not kept). */
export async function writeCachedAudio(cache: AudioCache | null, key: MusicKey, track: FileId, bytes: ArrayBuffer): Promise<void> {
  if (!cache || bytes.byteLength === 0 || (track.bytes !== null && bytes.byteLength !== track.bytes)) return;
  try {
    // A copy, taken now: decoding empties the buffer it is given.
    const body = bytes.slice(0);
    await cache.put(audioCacheUrl(key, track), new Response(body, { headers: { "Content-Type": "audio/mpeg" } }));
  } catch {
    // No room, or no permission: the track is downloaded again next time.
  }
}

/** Forgets every kept track the list no longer names: older revisions, and tracks that are gone. */
export async function pruneCachedAudio(cache: AudioCache | null, manifest: MusicManifest | null): Promise<void> {
  if (!cache) return;
  const current = new Set<string>();
  for (const [key, track] of Object.entries(manifest?.tracks ?? {})) {
    if (track) current.add(audioCacheUrl(key as MusicKey, track));
  }
  try {
    for (const entry of await cache.keys()) {
      let name: string;
      try {
        const u = new URL(entry.url, "https://sect.invalid");
        name = u.pathname + u.search;
      } catch {
        continue;
      }
      if (name.startsWith(AUDIO_PATH) && !current.has(name)) await cache.delete(entry.url);
    }
  } catch {
    // An old copy left behind takes room and nothing else: its name is never asked for again.
  }
}

/**
 * A track's bytes: the kept copy when there is one for this revision, else the download, which is
 * kept for next time.
 */
export async function cachedMusicBytes(opts: {
  cache: AudioCache | null;
  key: MusicKey;
  track: FileId;
  download: () => Promise<ArrayBuffer>;
}): Promise<ArrayBuffer> {
  const kept = await readCachedAudio(opts.cache, opts.key, opts.track);
  if (kept) return kept;
  const bytes = await opts.download();
  void writeCachedAudio(opts.cache, opts.key, opts.track, bytes);
  return bytes;
}
