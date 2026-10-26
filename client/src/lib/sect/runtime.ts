/**
 * Small runtime helpers for /sect: frame-rate independent damping, URL parameters, the device
 * quality tier, the visitor's own pick of it (stored, and how a running page applies a new one) and
 * the quality ladder the page steps down when frames run long (and back up when they have room
 * again). Pure functions with plain inputs, so they are unit-testable.
 */

/** Exponential damping toward target; frame-rate independent. dt is clamped to 0.1 s. */
export function damp(current: number, target: number, lambda: number, dt: number): number {
  const step = Math.min(Math.max(dt, 0), 0.1);
  if (lambda <= 0) return current;
  const next = current + (target - current) * (1 - Math.exp(-lambda * step));
  return Math.abs(target - next) < 1e-4 ? target : next;
}

export interface SectParams {
  /** Blender frame to jump to (?frame=N), or null. */
  frame: number | null;
  debug: boolean;
  flyer: boolean;
  /** ?ui=0 hides the overlays (for screenshot comparisons with the Blender renders). */
  ui: boolean;
  /** ?tier=low|mid|high forces a quality tier (testing: the picker hides and nothing is stored). */
  tier: Tier | null;
  /**
   * ?set=<name> loads public/sect/<name>/manifest.json (default "full"; "proto" is the first test).
   * Development only: a production build always loads "full".
   */
  set: string;
  /** ?open=<hotspot id> opens that item's reader once the page is ready, or null. */
  open: string | null;
}

/**
 * The loading screen waits for the visitor's "Enter" once the scene is ready, so the
 * graphics and sound can be set first. The screenshot views (?ui=0, ?frame=N) open at once: the
 * tools that capture them wait for body[data-sect-ready] and press nothing.
 */
export function waitsForEnter(p: Pick<SectParams, "ui" | "frame">): boolean {
  return p.ui && p.frame === null;
}

function flag(v: string | null): boolean {
  return v !== null && v !== "0" && v.toLowerCase() !== "false";
}

/**
 * high: discrete or Apple-silicon GPUs on a desktop (bloom, MSAA, up to 1.5x resolution).
 * mid: integrated laptop GPUs and strong tablets (bloom, no MSAA, 1x resolution).
 * low: phones, small devices and software renderers (no postprocessing, 1x, 2048 px textures).
 */
export type Tier = "high" | "mid" | "low";

const TIERS: readonly string[] = ["high", "mid", "low"];

/** Asset folder names under public/sect/ (lower-case letters, digits and dashes only). */
export function assetSet(v: string | null): string {
  const s = (v ?? "").trim().toLowerCase();
  return /^[a-z0-9][a-z0-9-]{0,31}$/.test(s) ? s : "full";
}

/**
 * Where an asset set's files live: /sect/<set> on this site, or under NEXT_PUBLIC_SECT_ASSET_BASE
 * (a CDN or storage bucket; the GLBs need not ship with the site).
 */
export function sectAssetBase(set: string, base?: string | null): string {
  const root = (base ?? "").trim().replace(/\/+$/, "");
  return `${root || "/sect"}/${set}`;
}

function openParam(v: string | null): string | null {
  const s = (v ?? "").trim();
  return s.length > 0 && s.length <= 80 && /^[\w:.-]+$/.test(s) ? s : null;
}

/**
 * The page's URL options. `dev` allows ?set= (a production build ignores it, so the test sets are
 * neither loaded nor reachable there).
 */
export function parseSectParams(search: string, dev = process.env.NODE_ENV !== "production"): SectParams {
  const q = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const raw = q.get("frame");
  const n = raw !== null && raw.trim() !== "" ? Number(raw) : NaN;
  const t = q.get("tier");
  return {
    frame: Number.isFinite(n) ? n : null,
    debug: flag(q.get("debug")),
    flyer: flag(q.get("flyer")),
    ui: q.get("ui") === null || flag(q.get("ui")),
    tier: t !== null && TIERS.includes(t) ? (t as Tier) : null,
    set: dev ? assetSet(q.get("set")) : "full",
    open: openParam(q.get("open")),
  };
}

export interface DeviceInfo {
  coarsePointer: boolean;
  /** navigator.deviceMemory in GB, when the browser exposes it (Chrome caps it at 8; Safari hides it). */
  deviceMemory?: number;
  hardwareConcurrency?: number;
  maxTextureSize: number;
  /** UNMASKED_RENDERER_WEBGL (WEBGL_debug_renderer_info), when the browser exposes it. */
  renderer?: string;
}

export type GpuClass = "software" | "mobile" | "integrated" | "discrete" | "unknown";

/**
 * Entry-level and old NVIDIA parts: GeForce MX and GT, the 9x0M laptop chips, Kepler Quadros and
 * the small Maxwell and Pascal ones, NVS. About as fast as an integrated GPU, with 2-4 GB, so they
 * get the integrated class (mid) rather than High, whose stream keeps five areas (and the next one)
 * at full detail: about 1.2 GB of textures at the worst point of the flight.
 */
const ENTRY_NVIDIA = /geforce (mx|gt )|geforce \d{3}mx?\b|quadro (fx|nvs|k\d)|quadro [mp]\d{3}\b|\bnvs \d/;

/** Rough GPU class from the WebGL renderer string (ANGLE wraps it, e.g. "ANGLE (Intel, Intel(R) UHD ...)"). */
export function classifyGpu(renderer: string | undefined): GpuClass {
  const r = (renderer ?? "").toLowerCase();
  if (!r) return "unknown";
  if (/swiftshader|llvmpipe|softpipe|basic render|software/.test(r)) return "software";
  if (/mali|adreno|powervr|xclipse|immortalis|videocore|tegra|apple a\d/.test(r)) return "mobile";
  if (ENTRY_NVIDIA.test(r)) return "integrated";
  if (/nvidia|geforce|quadro|rtx|gtx|radeon rx|radeon pro|arc\(tm\)|intel\(r\) arc|apple m\d/.test(r)) return "discrete";
  if (/intel|uhd|iris|hd graphics|radeon\(tm\) graphics|radeon graphics|vega \d|apple gpu/.test(r)) return "integrated";
  return "unknown";
}

/**
 * Safari's renderer name ("Apple GPU": it hides the real one, on a Mac and on an iPhone alike). In
 * Chrome the same Mac says "Apple M1 ..." and gets High.
 */
export function isAppleGpu(renderer: string | undefined): boolean {
  return (renderer ?? "").trim().toLowerCase() === "apple gpu";
}

/**
 * Touch devices start on low unless they look strong (8 GB, 8 cores, a GPU that is not a known
 * phone GPU); integrated laptop GPUs and small machines get mid; other desktops get high.
 */
export function chooseTier(d: DeviceInfo): Tier {
  if (d.maxTextureSize < 4096) return "low";
  const gpu = classifyGpu(d.renderer);
  if (gpu === "software") return "low";
  if (d.coarsePointer) {
    const strong =
      (d.deviceMemory ?? 0) >= 8 && (d.hardwareConcurrency ?? 0) >= 8 && (gpu === "integrated" || gpu === "discrete");
    return strong ? "mid" : "low";
  }
  if (gpu === "integrated" || gpu === "mobile") return "mid";
  const small =
    (d.deviceMemory !== undefined && d.deviceMemory <= 4) || (d.hardwareConcurrency !== undefined && d.hardwareConcurrency <= 4);
  return small ? "mid" : "high";
}

/** What the renderer does at a tier; the page steps down from here when frames run long. */
export interface Quality {
  /**
   * Device-pixel-ratio cap (the canvas never renders above the screen's own ratio). Under 1 it is a
   * render scale: the ladder's last resolution step (RENDER_SCALE_MIN), whatever the screen.
   */
  maxDpr: number;
  /** MSAA samples in the postprocessing buffers (0 = off). */
  msaa: number;
  bloom: boolean;
  /** Any postprocessing at all (composer, soft cloud edges, sun haze). */
  post: boolean;
  /** The 2048 px texture set (manifest filesLow / globalLow). */
  lowTextures: boolean;
  /**
   * Render-rate cap in frames per second while things move and at rest (0 = every display frame
   * while moving). The last step of the ladder, for devices that are slow even at the bottom.
   */
  maxFps: number;
  /**
   * The areas other than the one the camera is in are drawn as the backdrop's stand-ins (their
   * proxies), though they stay loaded. A ladder step for a tier the page picked (absent: false).
   */
  standIns?: boolean;
  /** Tree cards (alpha-tested sprites and needle cards) are not drawn. A ladder step, as standIns. */
  noCards?: boolean;
}

export interface TierOptions {
  /** A touch screen (phones and tablets): sharper pixels, lighter textures. */
  coarse?: boolean;
  /** Safari on a Mac (isAppleGpu): Medium starts at up to 1.5x there too. */
  appleGpu?: boolean;
}

/**
 * Touch screens start at up to 1.5x: at 1x a 3x phone shows a third of its resolution and every
 * edge stairs (the ladder steps back to 1x when frames run long). The mid tier there also takes the
 * 2048 px textures: about 180 MB of 4K atlases per area is too much for a tablet's shared memory.
 * Safari on a Mac lands on Medium (it names every GPU "Apple GPU"), and at 1x a Retina screen would
 * show a quarter of its pixels with no MSAA, so Medium starts at 1.5x there as well.
 */
export function tierQuality(tier: Tier, devicePixelRatio = 1, opts: TierOptions = {}): Quality {
  const coarse = opts.coarse === true;
  if (tier === "low") return { maxDpr: coarse ? 1.5 : 1, msaa: 0, bloom: false, post: false, lowTextures: true, maxFps: 0 };
  if (tier === "mid") return { maxDpr: coarse || opts.appleGpu ? 1.5 : 1, msaa: 0, bloom: true, post: true, lowTextures: coarse, maxFps: 0 };
  // Above 1x the extra pixels already smooth edges, so 2 samples do: 4x MSAA at 1.25x (a 1440p
  // screen at 125 % scaling) cost up to about 1 ms of GPU a frame, a third of a 360 Hz frame.
  // Never 0 here: tree cards need a multisampled buffer for alpha to coverage (setCardCoverage).
  const dpr = Math.min(Math.max(devicePixelRatio || 1, 1), 1.5);
  return { maxDpr: 1.5, msaa: dpr >= 1.25 ? 2 : 4, bloom: true, post: true, lowTextures: false, maxFps: 0 };
}

/**
 * The ladder's last resolution step: the canvas renders at 3/4 of the CSS pixels and the browser
 * scales it up. On a weak integrated GPU at the gate, 720p instead of 1080p cut the frame from 43
 * to 26 ms; that is worth more than any other step left at that point.
 */
export const RENDER_SCALE_MIN = 0.75;

/**
 * Canvas DPR for a quality on a screen: never above the screen's own ratio, never below 1 (except
 * the ladder's render scale, RENDER_SCALE_MIN).
 */
export function effectiveDpr(q: Quality, devicePixelRatio: number): number {
  if (q.maxDpr < 1) return q.maxDpr;
  return Math.max(1, Math.min(q.maxDpr, devicePixelRatio || 1));
}

/** The render-rate cap the ladder's last step sets. */
export const CAPPED_FPS = 30;

/**
 * A render-rate cap does nothing on a screen that shows no more frames than that anyway (a 30 Hz
 * cap: an iPhone in Low Power Mode, a 30 Hz screen). `cadenceMs` is the screen's frame interval,
 * null while it is not known yet.
 */
export function capIsMoot(maxFps: number, cadenceMs: number | null): boolean {
  return maxFps > 0 && cadenceMs !== null && cadenceMs >= 1000 / maxFps - 2;
}

export interface DegradeOptions {
  /**
   * The visitor picked the tier: only resolution steps down (to the render scale), never MSAA,
   * bloom or the render rate, so what they chose still looks like it.
   */
  keepLook?: boolean;
  /** The screen's frame interval (FrameLadder.cadenceMs): no render-rate cap where it is moot. */
  cadenceMs?: number | null;
}

/**
 * One step down the quality ladder: resolution first (to 1x), then MSAA, then bloom, then the
 * render scale (RENDER_SCALE_MIN), then the other areas as their stand-ins (standIns), then the
 * tree cards off (noCards), then the render rate (30 fps while moving). Returns null at the bottom.
 * A tier the visitor picked (`keepLook`) only loses resolution. Textures never change at runtime
 * (that would need a reload).
 */
export function degradeQuality(q: Quality, devicePixelRatio: number, opts: DegradeOptions = {}): Quality | null {
  const d = effectiveDpr(q, devicePixelRatio);
  if (d > 1) return { ...q, maxDpr: Math.max(1, d - 0.25) };
  if (!opts.keepLook) {
    if (q.msaa > 0) return { ...q, msaa: q.msaa > 2 ? 2 : 0 };
    if (q.bloom) return { ...q, bloom: false };
  }
  if (d > RENDER_SCALE_MIN) return { ...q, maxDpr: RENDER_SCALE_MIN };
  if (opts.keepLook) return null;
  if (!q.standIns) return { ...q, standIns: true };
  if (!q.noCards) return { ...q, noCards: true };
  if ((q.maxFps === 0 || q.maxFps > CAPPED_FPS) && !capIsMoot(CAPPED_FPS, opts.cadenceMs ?? null)) return { ...q, maxFps: CAPPED_FPS };
  return null;
}

/**
 * One step back up toward the tier's own quality (`top`) once frames have room again, in the
 * reverse order of the steps down: the render-rate cap off, the tree cards back, the other areas
 * back, the render scale back to 1x, bloom, MSAA (to 2 samples, then the tier's own), and last the
 * resolution above 1x, 0.25 at a time. Null when there is nothing to climb.
 */
export function upgradeQuality(q: Quality, top: Quality, devicePixelRatio: number): Quality | null {
  if (q.maxFps > 0 && q.maxFps !== top.maxFps) return { ...q, maxFps: top.maxFps };
  if (q.noCards && !top.noCards) return { ...q, noCards: false };
  if (q.standIns && !top.standIns) return { ...q, standIns: false };
  const d = effectiveDpr(q, devicePixelRatio);
  const t = effectiveDpr(top, devicePixelRatio);
  if (d < 1 && t >= 1) return { ...q, maxDpr: 1 };
  if (!q.bloom && top.bloom) return { ...q, bloom: true };
  if (q.msaa < top.msaa) return { ...q, msaa: q.msaa === 0 ? Math.min(2, top.msaa) : top.msaa };
  if (d >= t - 1e-6) return null;
  return { ...q, maxDpr: Math.min(t, d + 0.25) };
}

/**
 * The cost the ladder assumes for a climb that adds work rather than pixels (tree cards, the other
 * areas, bloom, MSAA): the frame must be predicted to fit with this much more. The margin is the
 * ladder's hysteresis there (a step comes back only with clear room, not at the edge where it was
 * dropped); a climb that still drops frames is undone and blocked for a while (FrameLadder).
 */
export const FEATURE_CLIMB_COST = 1.3;

/**
 * How much more one frame costs after a climb, for the ladder's headroom test: the pixel count's
 * ratio for a resolution step, FEATURE_CLIMB_COST for one that turns something back on, 1 for the
 * render-rate cap (it leaves each frame as it was). Null when there is no step up.
 */
export function climbCost(q: Quality, top: Quality, devicePixelRatio: number): number | null {
  const up = upgradeQuality(q, top, devicePixelRatio);
  if (!up) return null;
  if (up.maxFps !== q.maxFps) return 1;
  const r = effectiveDpr(up, devicePixelRatio) / effectiveDpr(q, devicePixelRatio);
  return Math.abs(r - 1) > 1e-6 ? r * r : FEATURE_CLIMB_COST;
}

/**
 * The next climb turns MSAA or bloom back on: that rebuilds the postprocessing pipeline (new
 * buffers, programs compiled), which stalls the frame it lands in, so the canvas waits for the
 * camera to rest before it takes it (scene.tsx Driver).
 */
export function climbRebuildsPipeline(q: Quality, top: Quality, devicePixelRatio: number): boolean {
  const up = upgradeQuality(q, top, devicePixelRatio);
  return up !== null && (up.msaa !== q.msaa || up.bloom !== q.bloom);
}

/** The ladder's frame budget for a tier the page picked (20 ms = under 50 fps). */
export const AUTO_FRAME_BUDGET_MS = 20;
/**
 * The ladder's frame budget for a tier the visitor picked (40 ms = under 25 fps): their choice holds
 * unless the page would feel broken.
 */
export const CHOICE_FRAME_BUDGET_MS = 40;

/** Median of frame times (ms) over budget (20 ms = under 50 fps), once there are enough samples. */
export function framesOverBudget(frameMs: readonly number[], budgetMs = AUTO_FRAME_BUDGET_MS, minSamples = 20): boolean {
  if (frameMs.length < minSamples) return false;
  return median(frameMs) > budgetMs;
}

function quantile(xs: readonly number[], p: number): number {
  const s = [...xs].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.floor(s.length * p))];
}

function median(xs: readonly number[]): number {
  return quantile(xs, 0.5);
}

/**
 * A frame is slow over this: the budget, or a little over the screen's own interval when that is
 * longer (`expectMs`: 33 ms on a 30 Hz screen, where every frame takes 33 ms however fast the GPU).
 */
export function slowFrameMs(budgetMs: number, expectMs: number): number {
  return Math.max(budgetMs, 1.15 * expectMs);
}

/** How the ladder judges frames (FrameLadder; scene.tsx Driver feeds it). */
export const LADDER = {
  /** Frames are ignored this long after a set becomes ready or is first drawn, or the screen changes. */
  settleMs: 2000,
  /** At least this long between two steps. */
  spacingMs: 4000,
  /** Moving frames needed before a judgement (the last LADDER.window count). */
  minFrames: 45,
  window: 90,
  /** Seconds of moving frames, since the last step, before a climb. */
  climbAfterMs: 3000,
  /** A climb needs the next level's frame (this one's times its pixel ratio) to fit this share of a frame. */
  climbFit: 0.9,
  /**
   * After a climb its frames are watched this long: a step down then means the climb failed. The
   * watch also lasts until probeMotionMs of moving frames have been seen (a climb taken at rest,
   * scene.tsx Driver, is judged on the flight after it, not on the rest).
   */
  probeMs: 10000,
  probeMotionMs: 3000,
  /** Right after a climb, more than this share of dropped frames undoes it. */
  probeJank: 0.25,
  /** With no GPU timer and a 60 Hz or slower screen, a climb is tried when at most this share drops. */
  steadyJank: 0.05,
  /** A failed climb waits this long before the next one, doubling each time up to maxBackoffMs. */
  backoffMs: 30000,
  maxBackoffMs: 480000,
} as const;

/** What one ladder judgement looks at (FrameLadder.decide). */
export interface LadderView {
  /** Intervals of the last moving frames (ms). */
  deltas: readonly number[];
  /** GPU time of moving frames (ms, EXT_disjoint_timer_query), empty without the timer. */
  gpu: readonly number[];
  /** The screen's frame interval, or null while unknown. */
  cadenceMs: number | null;
  /** The render-rate cap's interval while it applies, else 0. */
  capMs: number;
  budgetMs: number;
  /** Moving time sampled since the last step or settle. */
  motionMs: number;
  /** The last step was a climb and its frames are still being watched. */
  probing: boolean;
  /** How much more a frame costs after the next climb (climbCost), or null: no climb. */
  climbScale: number | null;
}

/**
 * The moving frames' typical interval: the median of the means of runs of 10 frames (the latest
 * first; a shorter run left at the start is dropped). A run's mean is the frame rate over it, which
 * the median of single frames is not: a GPU-bound page gets its frames unevenly (12, 57, 17, 34,
 * 9 ms ...), and their median (20 ms) hid a real 42 fps (24 ms). The median over runs keeps a stall
 * now and then (a GC, an upload the counters missed) to its own run, where an overall mean or a
 * trimmed one let it move the answer or let bursts of long frames be cut away (23 fps read as 30).
 */
export function typicalFrameMs(deltas: readonly number[], run = 10): number {
  if (deltas.length === 0) return 0;
  if (deltas.length < run) return deltas.reduce((a, d) => a + d, 0) / deltas.length;
  const means: number[] = [];
  for (let end = deltas.length; end - run >= 0; end -= run) {
    let sum = 0;
    for (let i = end - run; i < end; i++) sum += deltas[i];
    means.push(sum / run);
  }
  return median(means);
}

/**
 * Down when the typical moving frame is slow (slowFrameMs), or right after a climb when frames
 * drop; unless a GPU timer shows the GPU idle half the frame (a busy main thread: fewer pixels
 * would not help). Up when the next level's frame is predicted to fit: from the GPU timer, or on a
 * screen faster than 70 Hz from the frame intervals themselves; on a 60 Hz or slower screen without
 * a timer a frame's real cost is hidden under the screen's interval, so steady frames are the sign
 * and a climb that drops frames is undone (FrameLadder backs off).
 */
export function ladderStep(v: LadderView): "down" | "up" | null {
  if (v.deltas.length < LADDER.minFrames) return null;
  const expect = Math.max(v.cadenceMs ?? 0, v.capMs);
  const frame = typicalFrameMs(v.deltas);
  const gpuMed = v.gpu.length >= LADDER.minFrames / 2 ? median(v.gpu) : null;
  // Some drivers answer the timer with zeros: not a measurement.
  const gpu = gpuMed !== null && gpuMed >= 0.3 ? gpuMed : null;
  const drop = Math.max(v.budgetMs, 1.5 * (expect || 1000 / 60));
  const jank = v.deltas.filter((d) => d > drop).length / v.deltas.length;
  if (frame > slowFrameMs(v.budgetMs, expect) || (v.probing && jank > LADDER.probeJank)) {
    if (!v.probing && gpu !== null && gpu < 0.5 * frame) return null;
    return "down";
  }
  if (v.climbScale === null || v.motionMs < LADDER.climbAfterMs) return null;
  // The frame has to fit the screen's interval (at most 60 fps' worth), not the cap's: the cap is
  // the first thing a climb removes.
  const fit = LADDER.climbFit * Math.max(v.cadenceMs ?? 0, 1000 / 60);
  if (gpu !== null) return gpu * v.climbScale <= fit ? "up" : null;
  if (v.cadenceMs === null) return null;
  if (expect < 14) return frame * v.climbScale <= fit ? "up" : null;
  return frame <= 1.1 * expect && jank <= LADDER.steadyJank ? "up" : null;
}

/** What the ladder knows, for the debug HUD and inspection scripts. */
export interface LadderStatus {
  cadenceMs: number | null;
  /** The last moving frames' intervals (ms). */
  recentMs: number[];
  frames: number;
  /** typicalFrameMs of those frames. */
  frameMs: number | null;
  gpuMs: number | null;
  motionMs: number;
  settling: boolean;
  probing: boolean;
  /** No climb before this (performance.now()), after a failed one. */
  blockedUntil: number;
}

/**
 * The quality ladder's judge (pure: the caller passes the time). It learns the screen's own frame
 * interval from display frames that follow one where nothing was rendered (the browser waited on
 * nothing), keeps the intervals and GPU times of moving frames, ignores frames while sets settle,
 * spaces steps LADDER.spacingMs apart, and backs off climbs that fail.
 */
export class FrameLadder {
  private readonly quiet: number[] = [];
  private deltas: number[] = [];
  private gpu: number[] = [];
  private motionMs = 0;
  private settleUntil = 0;
  private lastStep: number;
  private probeUntil = 0;
  /** Moving time still to watch after a climb (LADDER.probeMotionMs). */
  private probeMotionLeft = 0;
  private blockedUntil = 0;
  private backoffMs: number = LADDER.backoffMs;
  /** Bumped by every settle and step: GPU times measured before arrive late and are dropped. */
  generation = 0;

  constructor(now: number) {
    this.lastStep = now;
  }

  /** A display frame's interval when nothing was rendered in the frame before it. */
  quietTick(intervalMs: number): void {
    if (!(intervalMs > 0 && intervalMs < 100)) return;
    this.quiet.push(intervalMs);
    if (this.quiet.length > 32) this.quiet.shift();
  }

  /**
   * The screen's frame interval (ms), once 8 quiet frames have been seen: their lower quartile (a
   * busy main thread only ever makes an interval longer than the screen's).
   */
  cadenceMs(): number | null {
    return this.quiet.length >= 8 ? quantile(this.quiet, 0.25) : null;
  }

  /** Ignore frames for a while (a set became ready or drew for the first time, the canvas resized). */
  settle(now: number, ms: number = LADDER.settleMs): void {
    this.settleUntil = Math.max(this.settleUntil, now + ms);
    this.clear();
  }

  /**
   * A moving frame's interval (ms). Over a second it was no frame (a hidden tab, a debugger); a
   * stall counts as 250 ms at most.
   */
  frame(now: number, deltaMs: number): void {
    if (now < this.settleUntil || !(deltaMs > 0) || deltaMs > 1000) return;
    const d = Math.min(deltaMs, 250);
    this.deltas.push(d);
    if (this.deltas.length > LADDER.window) this.deltas.shift();
    this.motionMs += d;
    this.probeMotionLeft = Math.max(0, this.probeMotionLeft - d);
  }

  /** A climb is still watched: within LADDER.probeMs of it, or before LADDER.probeMotionMs of motion. */
  private probing(now: number): boolean {
    return now < this.probeUntil || this.probeMotionLeft > 0;
  }

  /** A moving frame's GPU time (ms), measured in `generation`. */
  gpuTime(now: number, ms: number, generation: number): void {
    if (generation !== this.generation || now < this.settleUntil || !(ms >= 0)) return;
    this.gpu.push(ms);
    if (this.gpu.length > LADDER.window) this.gpu.shift();
  }

  /** The step to take now, if any. `climbScale`: climbCost of the next step up, or null. */
  decide(now: number, budgetMs: number, capMs: number, climbScale: number | null): "down" | "up" | null {
    if (now < this.settleUntil || now - this.lastStep < LADDER.spacingMs) return null;
    return ladderStep({
      deltas: this.deltas,
      gpu: this.gpu,
      cadenceMs: this.cadenceMs(),
      capMs,
      budgetMs,
      motionMs: this.motionMs,
      probing: this.probing(now),
      climbScale: now < this.blockedUntil ? null : climbScale,
    });
  }

  /** The caller took a step: judging starts over, and a step down soon after a climb blocks climbing. */
  stepped(now: number, dir: "down" | "up"): void {
    if (dir === "up") {
      this.probeUntil = now + LADDER.probeMs;
      this.probeMotionLeft = LADDER.probeMotionMs;
    } else if (this.probing(now)) {
      this.probeUntil = 0;
      this.probeMotionLeft = 0;
      this.blockedUntil = now + this.backoffMs;
      this.backoffMs = Math.min(this.backoffMs * 2, LADDER.maxBackoffMs);
    }
    this.lastStep = now;
    this.clear();
  }

  status(now: number): LadderStatus {
    return {
      cadenceMs: this.cadenceMs(),
      recentMs: this.deltas.slice(-24).map((d) => Math.round(d * 10) / 10),
      frames: this.deltas.length,
      frameMs: this.deltas.length ? typicalFrameMs(this.deltas) : null,
      gpuMs: this.gpu.length ? median(this.gpu) : null,
      motionMs: Math.round(this.motionMs),
      settling: now < this.settleUntil,
      probing: this.probing(now),
      blockedUntil: this.blockedUntil,
    };
  }

  private clear(): void {
    this.deltas = [];
    this.gpu = [];
    this.motionMs = 0;
    this.generation++;
  }
}

// ---------------------------------------------------------------------------------------------
// The visitor's own pick (the graphics picker on the loading screen and in the overlay)

/** The tiers from lowest to highest, in the picker's order. */
export const TIER_ORDER: readonly Tier[] = ["low", "mid", "high"];

/** What the picker calls each tier. */
export const TIER_LABELS: Readonly<Record<Tier, string>> = { low: "Low", mid: "Medium", high: "High" };

/** localStorage key of the visitor's pick. */
export const TIER_KEY = "sect.quality";

export function isTier(v: unknown): v is Tier {
  return typeof v === "string" && TIERS.includes(v);
}

/** The pick stored by an earlier visit, or null (none, junk, or storage blocked). */
export function readTierChoice(storage: Pick<Storage, "getItem"> | null): Tier | null {
  try {
    const v = storage?.getItem(TIER_KEY) ?? null;
    return isTier(v) ? v : null;
  } catch {
    return null;
  }
}

/** Stores the pick; false when storage is blocked (the pick then lasts for this visit only). */
export function writeTierChoice(storage: Pick<Storage, "setItem"> | null, tier: Tier): boolean {
  if (!storage) return false;
  try {
    storage.setItem(TIER_KEY, tier);
    return true;
  } catch {
    return false;
  }
}

/**
 * Where the tier came from: "link" (?tier=, testing: no picker, nothing stored), "choice" (the
 * visitor picked it, now or on an earlier visit) or "auto" (the device probe).
 */
export type TierSource = "link" | "choice" | "auto";

/** ?tier= wins over the visitor's pick, which wins over the probe's. */
export function resolveTier(o: { recommended: Tier; stored: Tier | null; forced: Tier | null }): { tier: Tier; source: TierSource } {
  if (o.forced) return { tier: o.forced, source: "link" };
  if (o.stored) return { tier: o.stored, source: "choice" };
  return { tier: o.recommended, source: "auto" };
}

/**
 * How a running page moves from one tier to another. "live": same textures and same render
 * pipeline (desktop Medium and High), so only the renderer's settings change. "restart": the
 * texture set differs (a new download), or postprocessing turns on or off (the canvas's antialias
 * is fixed when its context is made, and the low tier's world has no detail texture).
 */
export function tierChange(from: Tier, to: Tier, devicePixelRatio: number, coarse: boolean): "none" | "live" | "restart" {
  if (from === to) return "none";
  const a = tierQuality(from, devicePixelRatio, { coarse });
  const b = tierQuality(to, devicePixelRatio, { coarse });
  return a.lowTextures === b.lowTextures && a.post === b.post ? "live" : "restart";
}

/** Combined download progress (0..1) from per-file byte counts; unknown totals count as one file each. */
export function combinedProgress(files: readonly { loaded: number; total: number; done: boolean }[]): number {
  if (files.length === 0) return 0;
  let sum = 0;
  for (const f of files) {
    if (f.done) sum += 1;
    else if (f.total > 0) sum += Math.min(f.loaded / f.total, 0.999);
  }
  const byFile = sum / files.length;
  const known = files.every((f) => f.total > 0 || f.done);
  if (!known) return byFile;
  const total = files.reduce((a, f) => a + Math.max(f.total, 1), 0);
  const loaded = files.reduce((a, f) => a + (f.done ? Math.max(f.total, 1) : Math.min(f.loaded, f.total)), 0);
  return Math.min(loaded / total, 1);
}

/**
 * Workers for decoding meshopt-compressed geometry off the main thread: half the logical cores,
 * at least 1 and at most 4 (a chunk loads a handful of files at once; more workers would only
 * hold memory).
 */
export function meshoptWorkerCount(hardwareConcurrency: number | undefined): number {
  const n = Math.floor((hardwareConcurrency || 2) / 2);
  return Math.min(4, Math.max(1, n));
}

/** True when the bytes start with the gzip magic number (1f 8b). */
export function isGzip(bytes: Uint8Array): boolean {
  return bytes.length >= 2 && bytes[0] === 0x1f && bytes[1] === 0x8b;
}
