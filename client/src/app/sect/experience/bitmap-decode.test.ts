import { LoadingManager } from "three";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WorkerBitmapLoader } from "./bitmap-decode";

/** Lets every settled promise run its callbacks. */
const flush = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

class FakeBitmap {
  closed = false;
  close() {
    this.closed = true;
  }
}

/** A fetch that answers when told to and stops on its signal, as the browser's does. */
function fakeFetch() {
  const calls: { init: RequestInit; answer: () => void; fail: (e: unknown) => void }[] = [];
  const fn = (_url: string, init: RequestInit) =>
    new Promise<{ blob: () => Promise<Blob> }>((resolve, reject) => {
      calls.push({ init, answer: () => resolve({ blob: async () => new Blob(["webp"]) }), fail: reject });
      const signal = init.signal;
      if (!signal) return;
      if (signal.aborted) reject(signal.reason);
      signal.addEventListener("abort", () => reject(signal.reason), { once: true });
    });
  return { calls, fn };
}

/** createImageBitmap (under node there is no Worker, so the decode runs here): each waits until told. */
function fakeDecode() {
  const jobs: (() => FakeBitmap)[] = [];
  const fn = () =>
    new Promise<FakeBitmap>((resolve) => {
      jobs.push(() => {
        const b = new FakeBitmap();
        resolve(b);
        return b;
      });
    });
  return { jobs, fn };
}

let net: ReturnType<typeof fakeFetch>;
let decode: ReturnType<typeof fakeDecode>;

beforeEach(() => {
  net = fakeFetch();
  decode = fakeDecode();
  vi.stubGlobal("fetch", net.fn);
  vi.stubGlobal("createImageBitmap", decode.fn);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Starts one load; `out` collects what the loader hands back. */
function load(signal?: AbortSignal) {
  const manager = new LoadingManager();
  const calls = { start: vi.spyOn(manager, "itemStart"), end: vi.spyOn(manager, "itemEnd"), error: vi.spyOn(manager, "itemError") };
  const loader = new WorkerBitmapLoader(manager);
  if (signal) loader.signal = signal;
  const out = { bitmap: null as unknown, error: null as unknown, fetched: [] as string[] };
  loader.onFetched = (u) => out.fetched.push(u);
  loader.load(
    "a.webp",
    (b) => {
      out.bitmap = b;
    },
    undefined,
    (e) => {
      out.error = e;
    },
  );
  return { loader, calls, out };
}

describe("WorkerBitmapLoader", () => {
  it("loads as before with no signal: three's own signal on the fetch, the bitmap handed over", async () => {
    const { loader, calls, out } = load();
    expect(net.calls[0].init.signal).toBe((loader as unknown as { _abortController: AbortController })._abortController.signal);
    net.calls[0].answer();
    await flush();
    expect(out.fetched).toEqual(["a.webp"]);
    const bitmap = decode.jobs[0]();
    await flush();
    expect(out.bitmap).toBe(bitmap);
    expect(out.error).toBeNull();
    expect(calls.start).toHaveBeenCalledTimes(1);
    expect(calls.end).toHaveBeenCalledTimes(1);
    expect(calls.error).not.toHaveBeenCalled();
  });

  it("stops the fetch when cancelled while downloading, with an AbortError", async () => {
    const stop = new AbortController();
    const { calls, out } = load(stop.signal);
    stop.abort();
    await flush();
    expect((out.error as Error).name).toBe("AbortError");
    expect(out.bitmap).toBeNull();
    expect(out.fetched).toEqual([]);
    expect(decode.jobs).toHaveLength(0);
    expect(calls.error).toHaveBeenCalledTimes(1);
    expect(calls.end).toHaveBeenCalledTimes(1);
  });

  it("does not decode a file cancelled once its bytes are here", async () => {
    const stop = new AbortController();
    const { out } = load(stop.signal);
    net.calls[0].answer();
    stop.abort();
    await flush();
    expect(out.fetched).toEqual(["a.webp"]);
    expect(decode.jobs).toHaveLength(0);
    expect((out.error as Error).name).toBe("AbortError");
  });

  it("closes a bitmap whose decode ends after the cancel", async () => {
    const stop = new AbortController();
    const { calls, out } = load(stop.signal);
    net.calls[0].answer();
    await flush();
    expect(decode.jobs).toHaveLength(1);
    stop.abort();
    const bitmap = decode.jobs[0]();
    await flush();
    expect(bitmap.closed).toBe(true);
    expect(out.bitmap).toBeNull();
    expect((out.error as Error).name).toBe("AbortError");
    expect(calls.end).toHaveBeenCalledTimes(1);
  });

  it("reports a failure that is not a cancel as itself", async () => {
    const stop = new AbortController();
    const { out } = load(stop.signal);
    const offline = new TypeError("Failed to fetch");
    net.calls[0].fail(offline);
    await flush();
    expect(out.error).toBe(offline);
  });

  it("leaves a bitmap already handed over alone when cancelled later", async () => {
    const stop = new AbortController();
    const { out } = load(stop.signal);
    net.calls[0].answer();
    await flush();
    const bitmap = decode.jobs[0]();
    await flush();
    stop.abort();
    await flush();
    expect(out.bitmap).toBe(bitmap);
    expect(bitmap.closed).toBe(false);
    expect(out.error).toBeNull();
  });
});
