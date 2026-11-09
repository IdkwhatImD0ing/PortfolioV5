import { DEV_API_URL, PROD_API_URL, chooseApiBase, isDevBackendUp } from "@/lib/backend";
import { MUSIC_MANIFEST_PATH, type MusicKey } from "./music";
import { parseLyrics, type SongLyrics } from "./lyrics";

export type MusicResource = "audio" | "lyrics";
type Fetcher = typeof fetch;

export async function resolveMusicApiBase(): Promise<string> {
  const isDev = process.env.NODE_ENV !== "production";
  const devReachable = isDev ? await isDevBackendUp() : false;
  return chooseApiBase({ isDev, devReachable, devUrl: DEV_API_URL, prodUrl: PROD_API_URL }).replace(/\/+$/, "");
}

export async function fetchMusicManifest(base: string, signal: AbortSignal, fetcher: Fetcher = fetch): Promise<unknown> {
  const response = await fetcher(`${base}${MUSIC_MANIFEST_PATH}`, {
    signal,
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`music manifest ${response.status}`);
  return response.json();
}

async function capability(
  base: string,
  key: MusicKey,
  resource: MusicResource,
  signal: AbortSignal,
  fetcher: Fetcher,
): Promise<string> {
  const response = await fetcher(`${base}/music/access/${key}/${resource}`, {
    method: "POST",
    signal,
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`music access ${response.status}`);
  const body = (await response.json()) as { token?: unknown };
  if (typeof body.token !== "string" || body.token.length === 0) throw new Error("music access token");
  return body.token;
}

async function authorizedFetch(
  base: string,
  key: MusicKey,
  resource: MusicResource,
  signal: AbortSignal,
  fetcher: Fetcher,
): Promise<Response> {
  const path = resource === "audio" ? "tracks" : "lyrics";
  for (let attempt = 0; attempt < 2; attempt++) {
    const token = await capability(base, key, resource, signal, fetcher);
    const response = await fetcher(`${base}/music/${path}/${key}`, {
      signal,
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (response.status !== 401 || attempt === 1) return response;
  }
  throw new Error("music authorization");
}

export async function fetchMusicBytes(
  base: string,
  key: MusicKey,
  signal: AbortSignal,
  fetcher: Fetcher = fetch,
): Promise<ArrayBuffer> {
  const response = await authorizedFetch(base, key, "audio", signal, fetcher);
  if (!response.ok) throw new Error(`music ${response.status}`);
  return response.arrayBuffer();
}

export async function fetchTrackLyrics(
  base: string,
  key: MusicKey,
  signal: AbortSignal,
  fetcher: Fetcher = fetch,
): Promise<SongLyrics | null> {
  const response = await authorizedFetch(base, key, "lyrics", signal, fetcher);
  if (!response.ok) return null;
  return parseLyrics(await response.json(), key);
}
