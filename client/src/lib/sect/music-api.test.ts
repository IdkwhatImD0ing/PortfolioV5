import { describe, expect, it, vi } from "vitest";
import { fetchMusicBytes, fetchMusicManifest, fetchTrackLyrics } from "./music-api";

const signal = new AbortController().signal;
const base = "https://music.example";

describe("music backend client", () => {
  it("loads the metadata manifest without caching", async () => {
    const fetcher = vi.fn(async () => Response.json({ version: 2, tracks: {} }));
    await expect(fetchMusicManifest(base, signal, fetcher as typeof fetch)).resolves.toEqual({ version: 2, tracks: {} });
    expect(fetcher).toHaveBeenCalledWith(
      `${base}/music/manifest`,
      expect.objectContaining({ cache: "no-store", signal }),
    );
  });

  it("mints a capability and sends it only as a bearer header", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ token: "short-lived" }))
      .mockResolvedValueOnce(new Response(new Uint8Array([1, 2, 3])));
    const bytes = await fetchMusicBytes(base, "gate", signal, fetcher as typeof fetch);
    expect([...new Uint8Array(bytes)]).toEqual([1, 2, 3]);
    expect(fetcher.mock.calls[0][0]).toBe(`${base}/music/access/gate/audio`);
    expect(fetcher.mock.calls[1]).toEqual([
      `${base}/music/tracks/gate`,
      expect.objectContaining({ headers: { Authorization: "Bearer short-lived" }, cache: "no-store" }),
    ]);
  });

  it("refreshes an expired capability once", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ token: "expired" }))
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(Response.json({ token: "fresh" }))
      .mockResolvedValueOnce(new Response(new Uint8Array([9])));
    await expect(fetchMusicBytes(base, "gate", signal, fetcher as typeof fetch)).resolves.toBeInstanceOf(ArrayBuffer);
    expect(fetcher).toHaveBeenCalledTimes(4);
  });

  it("parses sanitized lyrics and treats absent lyrics as unavailable", async () => {
    const lyricPayload = {
      song: "Test",
      show: "Show",
      language: "en",
      lines: [{ start: 0, end: 1, text: "Rise", pinyin: "", en: "Rise", words: [{ w: "Rise", start: 0, end: 1 }] }],
    };
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ token: "lyrics" }))
      .mockResolvedValueOnce(Response.json(lyricPayload));
    await expect(fetchTrackLyrics(base, "mirror", signal, fetcher as typeof fetch)).resolves.toMatchObject({
      key: "mirror",
      song: "Test",
    });

    const missing = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ token: "lyrics" }))
      .mockResolvedValueOnce(new Response(null, { status: 404 }));
    await expect(fetchTrackLyrics(base, "mirror", signal, missing as typeof fetch)).resolves.toBeNull();
  });
});
