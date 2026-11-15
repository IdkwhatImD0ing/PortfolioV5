/**
 * Image decoding in a worker. createImageBitmap decodes on a browser thread, but its promise is
 * settled on the thread that called it, and there the browser builds the bitmap with its options
 * applied: 10 to 14 ms of main thread per 4096 px map, with no script running (a production flight
 * had 26 such tasks over 12 ms). Called in a worker, that step runs there; the bitmap comes back
 * transferred (no copy). The worker gets the same Blob and the same options, so the decoded texels
 * are the same (checked: a 4096 px WebP read back through WebGL matched byte for byte).
 *
 * The worker starts from a blob: URL like the gunzip worker (assets.ts). It says "ready" first; one
 * that never does (a Content-Security-Policy without worker-src blob:) or fails leaves decoding on
 * the main thread for the rest of the visit. It stops when idle for DECODER_IDLE_MS and starts again
 * on demand.
 */
import { ImageBitmapLoader } from "three";

const DECODE_WORKER = `
self.onmessage = async (e) => {
  const { id, blob, options } = e.data;
  try {
    const bitmap = await createImageBitmap(blob, options);
    self.postMessage({ id, bitmap }, [bitmap]);
  } catch (err) {
    self.postMessage({ id, error: String((err && err.message) || err) });
  }
};
self.postMessage({ ready: true });
`;
const DECODER_START_MS = 3000;
const DECODER_IDLE_MS = 30_000;

interface Decoder {
  worker: Worker;
  started: Promise<boolean>;
  jobs: Map<number, { resolve: (b: ImageBitmap) => void; reject: (e: unknown) => void }>;
  next: number;
  idle: ReturnType<typeof setTimeout> | undefined;
}
let decoder: Decoder | null = null;
/** Workers cannot run here (or one never started): decode on the main thread from now on. */
let decoderBlocked = false;

function stopDecoder(why: unknown): void {
  const d = decoder;
  if (!d) return;
  decoder = null;
  clearTimeout(d.idle);
  d.worker.terminate();
  for (const j of d.jobs.values()) j.reject(why);
}

function startDecoder(): Decoder | null {
  if (decoder) return decoder;
  if (decoderBlocked || typeof Worker === "undefined" || typeof URL.createObjectURL !== "function") return null;
  let worker: Worker;
  try {
    const url = URL.createObjectURL(new Blob([DECODE_WORKER], { type: "text/javascript" }));
    worker = new Worker(url);
    URL.revokeObjectURL(url);
  } catch (e) {
    console.warn("[sect] image decode worker unavailable; decoding on the main thread", e);
    decoderBlocked = true;
    return null;
  }
  let said: (ok: boolean) => void = () => {};
  const d: Decoder = {
    worker,
    started: new Promise<boolean>((resolve) => {
      said = resolve;
      setTimeout(() => resolve(false), DECODER_START_MS);
    }),
    jobs: new Map(),
    next: 1,
    idle: undefined,
  };
  worker.onmessage = (e: MessageEvent<{ ready?: boolean; id?: number; bitmap?: ImageBitmap; error?: string }>) => {
    const m = e.data;
    if (m.ready) return said(true);
    const job = m.id !== undefined ? d.jobs.get(m.id) : undefined;
    if (!job || m.id === undefined) return;
    d.jobs.delete(m.id);
    if (m.bitmap) job.resolve(m.bitmap);
    else job.reject(new Error(m.error ?? "image decode failed"));
    if (d.jobs.size === 0) {
      clearTimeout(d.idle);
      d.idle = setTimeout(() => {
        if (decoder === d && d.jobs.size === 0) stopDecoder(new Error("stopped"));
      }, DECODER_IDLE_MS);
    }
  };
  worker.onerror = (e) => {
    e.preventDefault();
    said(false);
    if (decoder === d) stopDecoder(new Error("the image decode worker failed"));
  };
  decoder = d;
  return d;
}

/** createImageBitmap(blob, options), run in the decode worker where it can (see the file's comment). */
export async function decodeBitmap(blob: Blob, options: ImageBitmapOptions): Promise<ImageBitmap> {
  const d = startDecoder();
  if (!d || !(await d.started)) {
    if (d && decoder === d) {
      console.warn("[sect] the image decode worker did not start; decoding on the main thread");
      decoderBlocked = true;
      stopDecoder(new Error("not started"));
    }
    return createImageBitmap(blob, options);
  }
  if (decoder !== d) return createImageBitmap(blob, options);
  const id = d.next++;
  clearTimeout(d.idle);
  return new Promise<ImageBitmap>((resolve, reject) => {
    d.jobs.set(id, { resolve, reject });
    d.worker.postMessage({ id, blob, options });
  });
}

/**
 * three's ImageBitmapLoader with the decode in the worker (decodeBitmap): the same fetch, the same
 * options (colorSpaceConversion "none" added as three adds it), the same callbacks and loading
 * manager calls. three's image cache is left out: it is off on this page (Cache.enabled).
 */
export class WorkerBitmapLoader extends ImageBitmapLoader {
  /**
   * Called once a load's file is all here, before it is decoded (the loading screen's wait tells a
   * file still downloading from work on one that has arrived: lib/sect/settle.ts). Not on a failed fetch.
   */
  onFetched: ((url: string) => void) | null = null;

  override load(url: string, onLoad?: (bitmap: ImageBitmap) => void, _onProgress?: unknown, onError?: (err: unknown) => void): void {
    let u = url ?? "";
    if (this.path !== undefined) u = this.path + u;
    u = this.manager.resolveURL(u);
    const manager = this.manager;
    const options = { ...(this.options as ImageBitmapOptions), colorSpaceConversion: "none" as const };
    const abort = (this as unknown as { _abortController?: AbortController })._abortController;
    const init: RequestInit = {
      credentials: this.crossOrigin === "anonymous" ? "same-origin" : "include",
      headers: this.requestHeader as HeadersInit,
      signal: abort?.signal,
    };
    manager.itemStart(u);
    const fetched = this.onFetched;
    fetch(u, init)
      .then((res) => res.blob())
      .then((blob) => {
        fetched?.(u);
        return decodeBitmap(blob, options);
      })
      .then((bitmap) => {
        onLoad?.(bitmap);
        manager.itemEnd(u);
      })
      .catch((e: unknown) => {
        onError?.(e);
        manager.itemError(u);
        manager.itemEnd(u);
      });
  }
}

/**
 * A GLTFLoader plugin that swaps the parser's ImageBitmapLoader for a WorkerBitmapLoader with the
 * same settings (where the parser fell back to a TextureLoader it leaves that alone).
 */
export function workerDecodePlugin(parser: {
  textureLoader: { isImageBitmapLoader?: boolean; options?: unknown; crossOrigin: string; requestHeader: Record<string, string>; manager: ImageBitmapLoader["manager"] };
}): { name: string } {
  const old = parser.textureLoader;
  if (old.isImageBitmapLoader === true) {
    const l = new WorkerBitmapLoader(old.manager);
    l.setOptions(old.options as ImageBitmapOptions);
    l.setCrossOrigin(old.crossOrigin);
    l.setRequestHeader(old.requestHeader);
    parser.textureLoader = l;
  }
  return { name: "sect_worker_decode" };
}
