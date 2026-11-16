/**
 * The page's GPU job queue, one per renderer (lib/sect/gpu-queue.ts has the rules): texture uploads
 * go through it. Its pace follows what the visitor can see, which the store tells it (watchView;
 * scene.tsx GpuPaceFromStore): while the camera moves, one step a display frame, never while the GPU
 * is still working through the last frame's steps (a fence, polled, never waited on) or a shader
 * program is linking; with the camera at rest, steps for a few milliseconds of each frame, not held
 * by a linking program, for work the visitor waits to see (a place still showing its stand-ins; the
 * rest goes as while moving); behind the loading screen or the ink, most of each frame, held by nothing.
 *
 * A decoded image (ImageBitmap) in RGBA bytes goes up in bands. The first step has three allocate
 * the texture exactly as it would for a whole upload (immutable storage of the same internal format,
 * the same levels, filters, wrap and anisotropy) with the image held back (Source.dataReady false);
 * then each step uploads a band of rows from the same image into level 0 (WebGL 2 sub-rectangle
 * uploads; an ImageBitmap carries its own orientation, premultiply and colour handling, so the
 * texels are the ones one upload would give); the last one makes the mipmaps, as three would, and
 * only then runs the texture's onUpdate (which closes the image: prepare.ts, live.tsx). Anything
 * else (another format, an HTML image, a data texture, a mipmapped map with a side that is not a
 * power of two, whose mipmaps would come out different) goes up whole in one step through three.
 *
 * Between the first step and the last, three takes the texture for uploaded: whoever queues it must
 * not draw it before the upload resolves (the sets are not ready before then, live light's maps are
 * not bound). An upload given up halfway (its owner went) frees the texture's GPU copy, so nothing
 * can draw the half-filled one.
 */
import { LinearFilter, NearestFilter, RGBAFormat, UnsignedByteType, type Texture, type WebGLRenderer } from "three";
import { bandsKeepMipmaps, gpuPaceFor, mayRunGpuStep, pickGpuJob, uploadBands, type GpuView, type UploadBand } from "@/lib/sect/gpu-queue";

/** One queued job: `step` runs one step and says whether the job is done. */
interface Job {
  seq: number;
  priority: () => number;
  wait: () => boolean;
  alive: () => boolean;
  step: () => boolean;
  /** Called when the job is dropped before it is done. */
  cancel: () => void;
  resolve: (done: boolean) => void;
}

export interface UploadOptions {
  /** Higher goes first (default 1); read at each step. */
  priority?: number | (() => number);
  /** True while the upload should wait (the others may go meanwhile). */
  wait?: () => boolean;
  /** False once the texture's owner has gone: the upload is dropped (resolves false). */
  alive?: () => boolean;
}

/** The parts of three's texture properties used here. */
interface TextureProps {
  __webglTexture?: WebGLTexture;
  __version?: number;
}

const yes = () => true;
const no = () => false;
/** Until the store says otherwise, the queue paces itself as while the camera moves. */
const moving = (): GpuView => "moving";

export class GpuQueue {
  private jobs: Job[] = [];
  private seq = 0;
  private raf = 0;
  private fence: WebGLSync | null = null;
  /** When the queue was first held by the fence or a linking program (performance.now()), or null. */
  private heldSince: number | null = null;
  /** Programs seen linked (three's isReady stays true once it is). */
  private readyPrograms = new WeakSet<object>();
  private disposed = false;
  /** What the visitor can see now (watchView), read at every display frame. */
  private viewOf: () => GpuView = moving;
  /** Steps run (for inspection). */
  steps = 0;

  constructor(private readonly gl: WebGLRenderer) {}

  private get ctx(): WebGL2RenderingContext {
    return this.gl.getContext() as WebGL2RenderingContext;
  }

  /**
   * Has the queue ask `view` at every display frame what the visitor can see (the store knows: the
   * camera moving, at rest, or the scene covered), and pace itself for it (lib/sect/gpu-queue.ts
   * GPU_PACE). Returns the undo; until then, and after it, the queue paces itself as while moving.
   */
  watchView(view: () => GpuView): () => void {
    this.viewOf = view;
    return () => {
      if (this.viewOf === view) this.viewOf = moving;
    };
  }

  /** What the visitor can see now, as the queue paces itself for it. */
  view(): GpuView {
    try {
      return this.viewOf();
    } catch {
      return "moving";
    }
  }

  /**
   * Resolves at the first display frame in which the camera is not moving (at rest, or the scene
   * covered), or `stop()` says to stop waiting, or the queue has gone: at once when that is so now.
   */
  untilStill(stop: () => boolean): Promise<void> {
    return new Promise((resolve) => {
      const check = () => {
        if (this.disposed || stop() || this.view() !== "moving") resolve();
        else requestAnimationFrame(check);
      };
      check();
    });
  }

  /** Nothing queued and the GPU through the last step. */
  idle(): boolean {
    return this.jobs.length === 0 && this.fence === null;
  }

  /** Work queued or under way: an upload, the GPU's last step, or a program three made still linking. */
  busy(): boolean {
    return !this.idle() || this.linking();
  }

  /** Puts a texture on the GPU through the queue; resolves true once it is all there (mipmaps too), false if dropped. */
  uploadTexture(tex: Texture, opts: UploadOptions = {}): Promise<boolean> {
    const run = textureSteps(this.gl, tex);
    return this.add(run.step, run.cancel, opts);
  }

  private add(step: () => boolean, cancel: () => void, opts: UploadOptions): Promise<boolean> {
    if (this.disposed) return Promise.resolve(false);
    const p = opts.priority;
    return new Promise<boolean>((resolve) => {
      this.jobs.push({
        seq: this.seq++,
        priority: typeof p === "function" ? p : () => p ?? 1,
        wait: opts.wait ?? no,
        alive: opts.alive ?? yes,
        step,
        cancel,
        resolve,
      });
      this.schedule();
    });
  }

  private schedule(): void {
    if (this.raf === 0 && !this.disposed) this.raf = requestAnimationFrame(this.tick);
  }

  /** Some program three made is still linking (asked without waiting for the driver). */
  private linking(): boolean {
    for (const p of this.gl.info.programs ?? []) {
      if (this.readyPrograms.has(p)) continue;
      const ready = (p as { isReady?: () => boolean }).isReady;
      if (!ready || ready.call(p)) this.readyPrograms.add(p);
      else return true;
    }
    return false;
  }

  private fencePassed(): boolean {
    const f = this.fence;
    if (!f) return true;
    const ctx = this.ctx;
    if (ctx.isContextLost() || ctx.getSyncParameter(f, ctx.SYNC_STATUS) === ctx.SIGNALED) {
      ctx.deleteSync(f);
      this.fence = null;
      return true;
    }
    return false;
  }

  private tick = (): void => {
    this.raf = 0;
    if (this.disposed) return;
    const ctx = this.ctx;
    // Owners gone: their jobs are dropped.
    for (let i = this.jobs.length - 1; i >= 0; i--) {
      const j = this.jobs[i];
      if (j.alive() && !ctx.isContextLost()) continue;
      this.jobs.splice(i, 1);
      j.cancel();
      j.resolve(false);
    }
    const fencePending = !this.fencePassed();
    if (this.jobs.length === 0) {
      if (fencePending) this.schedule();
      this.heldSince = null;
      return;
    }
    const view = this.view();
    // The frame's pace: at rest, the larger share only while work the visitor waits to see is queued
    // (asked of the priorities alone: a job's `wait` is asked only when a step may run, as ever, since
    // it starts the clock of an area's longest wait).
    let top = 0;
    if (view === "resting") for (const j of this.jobs) top = Math.max(top, j.priority());
    const pace = gpuPaceFor(view, top);
    // Whether a program links is asked only where the pace holds for it (the question is cheap, but
    // a pace that does not hold has no use for the answer).
    const linking = pace.holdForLinks && !fencePending && this.linking();
    const now = performance.now();
    const held = (pace.holdForFence && fencePending) || linking;
    if (held) this.heldSince ??= now;
    else this.heldSince = null;
    const heldMs = this.heldSince === null ? 0 : now - this.heldSince;
    // As many steps as the pace gives this frame (one while the camera moves), the most wanted first;
    // at rest, a job the visitor does not wait for goes only as a frame's first step.
    let steps = 0;
    for (;;) {
      if (!mayRunGpuStep({ stepsThisFrame: steps, spentMs: performance.now() - now, fencePending, linking, heldMs }, pace)) break;
      const info = this.jobs.map((j) => ({ priority: j.priority(), seq: j.seq, waiting: j.wait() }));
      const i = pickGpuJob(info);
      if (i < 0) break;
      if (steps > 0 && gpuPaceFor(view, info[i].priority).budgetMs === 0) break;
      const j = this.jobs[i];
      let done = true;
      try {
        done = j.step();
      } catch (e) {
        console.warn("[sect] GPU upload failed", e);
        j.cancel();
      }
      this.steps++;
      steps++;
      if (done) {
        this.jobs.splice(i, 1);
        j.resolve(true);
      }
    }
    if (steps > 0) {
      this.heldSince = null;
      if (this.fence) ctx.deleteSync(this.fence);
      this.fence = ctx.fenceSync(ctx.SYNC_GPU_COMMANDS_COMPLETE, 0);
      ctx.flush();
    }
    this.schedule();
  };

  /** Drops every job (the renderer is going). */
  dispose(): void {
    this.disposed = true;
    if (this.raf) cancelAnimationFrame(this.raf);
    this.raf = 0;
    for (const j of this.jobs.splice(0)) {
      j.cancel();
      j.resolve(false);
    }
    if (this.fence && !this.ctx.isContextLost()) this.ctx.deleteSync(this.fence);
    this.fence = null;
  }
}

const queues = new WeakMap<WebGLRenderer, GpuQueue>();

/** The renderer's queue (made on first use). */
export function gpuQueue(gl: WebGLRenderer): GpuQueue {
  let q = queues.get(gl);
  if (!q) {
    q = new GpuQueue(gl);
    queues.set(gl, q);
  }
  return q;
}

/** Whether the texture is on the GPU as it stands (three would upload nothing for it). */
function uploaded(gl: WebGLRenderer, tex: Texture): boolean {
  const own = gl.properties.get(tex) as TextureProps;
  const src = gl.properties.get(tex.source) as TextureProps;
  return own.__webglTexture !== undefined && own.__version === tex.version && src.__version === tex.source.version;
}

/** A decoded image in RGBA bytes, at most the GPU's size: it can go up in bands. */
function bandable(gl: WebGLRenderer, tex: Texture): ImageBitmap | null {
  const img = tex.image as unknown;
  if (typeof ImageBitmap === "undefined" || !(img instanceof ImageBitmap)) return null;
  if (tex.format !== RGBAFormat || tex.type !== UnsignedByteType || tex.mipmaps.length > 0) return null;
  if ((tex as { isCompressedTexture?: boolean }).isCompressedTexture || (tex as { isVideoTexture?: boolean }).isVideoTexture) return null;
  if ((tex as { isDataTexture?: boolean }).isDataTexture || tex.isRenderTargetTexture) return null;
  const max = gl.capabilities.maxTextureSize;
  if (img.width === 0 || img.height === 0 || img.width > max || img.height > max) return null;
  // Mipmaps made from a level 0 that went up in parts differ on a map with a side that is not a power
  // of two (lib/sect/gpu-queue.ts bandsKeepMipmaps): that one goes up whole.
  if (makesMipmaps(tex) && !bandsKeepMipmaps(img.width, img.height)) return null;
  return img;
}

/** three makes this texture's mipmaps on the GPU after an upload (its textureNeedsGenerateMipmaps). */
function makesMipmaps(tex: Texture): boolean {
  return tex.generateMipmaps && tex.minFilter !== NearestFilter && tex.minFilter !== LinearFilter;
}

/** The steps of one texture's upload (see the file's comment). */
function textureSteps(gl: WebGLRenderer, tex: Texture): { step: () => boolean; cancel: () => void } {
  let bands: UploadBand[] | null = null;
  let image: ImageBitmap | null = null;
  let next = 0;
  /** The texture's own onUpdate, run once the last band is in. */
  let onUpdate: Texture["onUpdate"] = null;
  /** Allocated and partly filled: three takes it for uploaded. */
  let open = false;
  const step = (): boolean => {
    if (bands === null) {
      // Nothing to put up yet (no image), or up already (three drew it, or a clone shares it).
      if (tex.version === 0 || uploaded(gl, tex)) return true;
      image = bandable(gl, tex);
      const plan = image ? uploadBands(image.width, image.height) : [];
      if (!image || plan.length < 2) {
        gl.initTexture(tex);
        return true;
      }
      onUpdate = tex.onUpdate;
      tex.onUpdate = null;
      tex.source.dataReady = false;
      try {
        gl.initTexture(tex);
      } finally {
        tex.source.dataReady = true;
        tex.onUpdate = onUpdate;
      }
      const glTex = (gl.properties.get(tex) as TextureProps).__webglTexture;
      // three did not allocate it (a warning says why): left to its own upload when drawn.
      if (!glTex || !uploaded(gl, tex)) return true;
      bands = plan;
      open = true;
      return false;
    }
    const ctx = gl.getContext() as WebGL2RenderingContext;
    const glTex = (gl.properties.get(tex) as TextureProps).__webglTexture;
    const img = image;
    if (!glTex || !img) {
      open = false;
      return true;
    }
    const b = bands[next++];
    const st = gl.state;
    st.bindTexture(ctx.TEXTURE_2D, glTex, ctx.TEXTURE0);
    // As three's own upload does: bindTexture skips activeTexture when unit 0 still holds this
    // texture (from the last band), and the raw calls below act on the active unit's texture.
    st.activeTexture(ctx.TEXTURE0);
    st.pixelStorei(ctx.UNPACK_ALIGNMENT, tex.unpackAlignment);
    st.pixelStorei(ctx.UNPACK_ROW_LENGTH, 0);
    st.pixelStorei(ctx.UNPACK_SKIP_PIXELS, 0);
    st.pixelStorei(ctx.UNPACK_SKIP_ROWS, b.y);
    const last = next >= bands.length;
    try {
      ctx.texSubImage2D(ctx.TEXTURE_2D, 0, 0, b.y, img.width, b.rows, ctx.RGBA, ctx.UNSIGNED_BYTE, img);
      // The last band: the mipmaps from the full level 0, as three makes them after a whole upload.
      if (last && makesMipmaps(tex)) ctx.generateMipmap(ctx.TEXTURE_2D);
    } finally {
      st.pixelStorei(ctx.UNPACK_SKIP_ROWS, 0);
      // Unit 0 left empty after every band, as three's initTexture leaves it: a draw that does not
      // bind its samplers again (the same material as the last draw) never samples the half-filled map.
      st.unbindTexture();
    }
    if (!last) return false;
    open = false;
    tex.onUpdate?.(tex);
    return true;
  };
  const cancel = () => {
    if (!open) return;
    open = false;
    // Half filled: its GPU copy goes, so nothing draws it (the image is still open for another upload).
    tex.dispose();
  };
  return { step, cancel };
}
