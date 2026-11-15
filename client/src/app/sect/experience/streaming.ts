/**
 * Streams the manifest's chunks around the camera (lib/sect/chunks.ts decides what; this does it):
 * keeps the area the camera is in and its neighbours in flight order at full detail (two each side
 * on desktops, STREAM_BUDGETS), starts loads nearest first, prefetches the next area past that
 * window (desktops as soon as nothing else loads, phones while the camera rests), cancels loads
 * nobody wants any more, keeps the area on screen until the next one can be drawn, retries failed
 * loads a few times and hands dropped chunks back for disposal once React has taken them out of the
 * scene. It measures what each loaded chunk holds (triangles, texture memory: status()). On a strong
 * desktop (STREAM_BUDGETS.everything) it also loads every other area in the background once the page
 * opens it (fillOpen), one at a time, and keeps them. For fast travel's settled wait it says what a
 * camera resting at a stop will draw and how far that has come (settleAt).
 *
 * Not React: the page calls update() on a timer and on jumps, and re-renders on onChange.
 */
import { LinearFilter, NearestFilter, type Texture } from "three";
import {
  areaIndexAt,
  DEFAULT_WINDOW,
  holdCores,
  jumpLeg,
  planChunks,
  travelAfterJump,
  travelDirection,
  type AreaWindow,
  type ChunkCost,
  type ChunkPlan,
  type ChunkSpan,
  type JumpLeg,
  type PlanWindow,
  type Travel,
  windowCentreAt,
} from "@/lib/sect/chunks";
import type { DeviceInfo, Tier } from "@/lib/sect/runtime";
import { chunkArriving, chunkDone, destinationChunks, SETTLE, type SettleSnapshot } from "@/lib/sect/settle";
import type { ChunkInfo } from "@/lib/sect/types";
import { chunkFiles, disposeSet, loadSet, retireSet, type LoadedSet, type SetLoadOptions, type WorldContext } from "./assets";

/**
 * Loads at once (needed chunks first; a prefetch only when nothing else is loading). Only one of them
 * downloads at a time, the nearest first: the next starts once its files are in, while the first is
 * parsed and prepared. Downloading two areas side by side, the gate's mirror (the peak beside the
 * stair, the first thing the opening view shows past the gate) stayed its stand-in about 1.7 s longer
 * on a 40 Mbps line, sharing the line with the forge further back.
 */
const MAX_PARALLEL = 2;
/**
 * Loads at once during the loading screen's wait for the first stop (settleAt with `around`
 * Infinity), the area the plan prefetches once the others are in among them (it is drawn in the
 * first view too, far back). One after another, the prefetch started only once the others were
 * drawn, and its parsing, preparing and uploads alone held "Enter" about half a second, or,
 * finishing after it, went up and linked their programs in the first seconds of the flight.
 *
 * Their downloads still go one at a time, nearest first, as everywhere (MAX_PARALLEL): the next
 * starts once the last one's files are in, while that one is parsed and prepared, so on localhost
 * they overlap as before. The wait no longer waits for a download (lib/sect/settle.ts SETTLE_GATE),
 * and on a real line four side by side made the nearest neighbour (the mirror's peak beside the
 * stair) and the first stop's own area, when the opening view went on without it, arrive last with
 * the rest.
 */
const GATE_PARALLEL = 4;
/** Tries a chunk gets (the first load and its retries) before the backdrop's proxy stands in for good. */
const MAX_TRIES = 3;
/**
 * How long one settleAt call holds back the loads fast travel's wait does not cover (it is called
 * every display frame while the ink is up, so they start about this long after the ink lets go).
 */
const SETTLE_FOCUS_MS = 400;
/** Wait before the first retry; each later one waits RETRY_GROWTH times longer (2 s, then 8 s). */
const RETRY_BASE_MS = 2000;
const RETRY_GROWTH = 4;

/**
 * How long after its `failures`-th failed try a chunk waits before the next one, or null once it
 * has had MAX_TRIES (it stays failed, until the network comes back: ChunkStreamer listens for
 * "online"). The old fixed 15 s retry ran forever, and on the error screen it fetched the 8.7 MB
 * gate again every 15 s.
 */
export function retryDelayMs(failures: number): number | null {
  if (failures >= MAX_TRIES) return null;
  return RETRY_BASE_MS * RETRY_GROWTH ** Math.max(0, failures - 1);
}

/**
 * When a prefetch may start: "moving" as soon as nothing else loads (desktops: it downloads during
 * the flight, and its main-thread part waits for a rest unless the area is needed first), "rest"
 * only while the camera rests (phones), "off" never (the visitor asked to save data).
 */
export type PrefetchMode = "moving" | "rest" | "off";

/**
 * How many areas stay at full detail around the one the camera is in, by flight order (their own
 * meshes and full-resolution textures, never the backdrop's stand-ins), and when the next area past
 * them loads (see lib/sect/chunks.ts PlanWindow.around). The owner's rule: the place on screen, the
 * two before it and the two after it. Clamped at the flight's ends (three areas at the gate and at
 * the summit). Nothing in a loaded area is reduced: every area loads its own atlases at the size
 * the tier's texture set has (4096 px, or 2048 px on the low tier and touch screens), with full
 * mipmaps and the same filtering, whether the camera is in it or two areas away.
 *
 * Measured at the stops from the gate to the library (production build, 1600x900 and 390x844):
 * - `full` (High, and Medium with 8 GB or more, roomyMemory): two each side. Five or six areas
 *   with the spare: 0.96-1.2 GB of textures, 0.25-0.32 GB of geometry, 8.3-10.2 M triangles
 *   resident, against three areas, 0.55-0.65 GB, 0.14-0.2 GB and 5.4-6.2 M for the area and the
 *   next it replaces. Frustum culling keeps what a frame draws close: 2.9-6.8 M triangles at the
 *   stops against 2.7-5.7 M.
 * - `narrow` (Medium on a smaller machine): one each side, about 0.8 GB of textures with the spare.
 *   An integrated GPU shares the system's memory; six areas would take a third of 4 GB.
 * - `low` (phones, tablets and the low tier, with the 2048 px set): one each side. Four areas with
 *   the spare: 0.26-0.3 GB of textures, 0.17-0.22 GB of geometry and 0.16-0.29 GB of script
 *   buffers, 0.6-0.8 GB in all against 0.4-0.5 GB before, about half of what iOS allows a tab (it
 *   drops one at about 1.5 GB). Two each side measured 0.9-1.05 GB (0.4-0.43 GB of textures, up to
 *   0.31 GB of geometry): too close to that limit once the browser's own share and a load's
 *   decoding are added.
 * - `lean` (a touch screen on High, which keeps the 4096 px set): the area alone and the spare, as
 *   every phone had before: two 4096 px areas are 0.32-0.48 GB of textures already.
 *
 * `spare`: the next area past the window in the direction of travel, prefetched once the window is
 * in and kept until the camera has passed it, so crossing into the next area finds its new far
 * neighbour loaded. During a jump the camera's own window stays while the cap (the window and the
 * spare) allows. Phones too: without it a phone showed the backdrop's stand-ins for 4-7 s at every
 * stop on a 12 Mbps network.
 *
 * `prefetch`: when the next area may start loading (PrefetchMode). Desktops download it during the
 * flight (a visitor who never pauses saw five stops arrive as stand-ins); phones wait for a rest
 * (their data and CPU are scarcer).
 *
 * `lookBack`: while the visitor looks back at rest (free look turned past 90 degrees), one more area
 * behind the view may load past the cap (lib/sect/chunks.ts PlanWindow.lookBack). 0 everywhere now:
 * the window already holds the areas behind.
 *
 * `fillTexBytes` (`everything`: a High desktop with 16 GB and the line for it, streamBudget):
 * once the visitor is in, every other area loads in the background too, one at a time, ahead first,
 * and stays (lib/sect/chunks.ts PlanWindow.fill), while all of it fits this much texture memory. 0:
 * off. Measured at the gate on High (production build, 1600x900, RTX 5080): the full window holds 4
 * areas, 867 MB of textures and 7.6 M triangles; all eleven hold 2,241 MB and 19.2 M, and the frame
 * is unchanged (550 draw calls, 8.9 M triangles drawn, 3.0 ms of GPU time), because an area is drawn
 * only while the frame is inside its need range, and the seven more are outside theirs there. So
 * holding everything costs memory, not frame time. 3 GB holds all eleven with room; it is a guard
 * should the scene grow.
 */
const FULL = { around: { behind: 2, ahead: 2 }, spare: 1, lookBack: 0, prefetch: "moving", fillTexBytes: 0 } as const;
/** Texture memory every area may fill in the background (STREAM_BUDGETS.everything): 3 GB. */
const FILL_TEX_BYTES = 3 * 2 ** 30;
export const STREAM_BUDGETS = {
  everything: { ...FULL, fillTexBytes: FILL_TEX_BYTES },
  full: FULL,
  narrow: { around: { behind: 1, ahead: 1 }, spare: 1, lookBack: 0, prefetch: "moving", fillTexBytes: 0 },
  low: { around: { behind: 1, ahead: 1 }, spare: 1, lookBack: 0, prefetch: "rest", fillTexBytes: 0 },
  lean: { around: { behind: 0, ahead: 0 }, spare: 1, lookBack: 0, prefetch: "rest", fillTexBytes: 0 },
} as const satisfies Record<string, StreamBudget>;

export interface StreamBudget {
  /** Areas before and after the camera's own kept at full detail (lib/sect/chunks.ts PlanWindow.around). */
  around: AreaWindow;
  /** Areas past the window in the direction of travel, prefetched and kept (PlanWindow.spare). */
  spare: number;
  /** When the next area may start loading. */
  prefetch: PrefetchMode;
  /** Areas behind allowed past the cap while looking back (lib/sect/chunks.ts PlanWindow.lookBack). */
  lookBack: number;
  /**
   * Texture memory (bytes) every area may take while the rest load in the background and stay
   * (lib/sect/chunks.ts PlanWindow.fill). 0: off.
   */
  fillTexBytes: number;
}

/** The same budget without background filling (the page's one strike: a step down the quality ladder). */
export function withoutFill(budget: StreamBudget): StreamBudget {
  return budget.fillTexBytes === 0 ? budget : { ...budget, fillTexBytes: 0 };
}

/** What the browser tells about the machine's memory (lib/sect/runtime.ts DeviceInfo). */
export type MemoryHints = Pick<DeviceInfo, "deviceMemory" | "hardwareConcurrency">;

/**
 * navigator.deviceMemory is in GB, rounded down to a power of two. Chrome and Edge capped it at 8
 * for years (8 meant 8 GB or more); current ones go higher (Chrome 157 reported 32).
 */
const ROOMY_MEMORY_GB = 8;
/** Without deviceMemory (Firefox, Safari), logical cores stand in for it (see roomyMemory). */
const ROOMY_CORES = 8;

/**
 * True when a Medium desktop has the memory for the full window (STREAM_BUDGETS.full): 8 GB or more.
 * - deviceMemory known (Chrome, Edge): at least 8, its cap. A typical laptop (8-16 GB) qualifies;
 *   its integrated GPU shares that memory, and the full window peaks at about 1.5 GB of it
 *   (textures and geometry).
 * - deviceMemory unknown (Firefox, Safari): at least 8 logical cores. Machines with that many are
 *   unlikely to have less than 8 GB; 4-core machines are where small memory is common. Firefox's
 *   fingerprinting guard reports 2 cores: the narrow window then.
 */
export function roomyMemory(memory: MemoryHints): boolean {
  if (memory.deviceMemory !== undefined) return memory.deviceMemory >= ROOMY_MEMORY_GB;
  return (memory.hardwareConcurrency ?? 0) >= ROOMY_CORES;
}

/** Memory for holding every area at once (STREAM_BUDGETS.everything): 16 GB. */
const FILL_MEMORY_GB = 16;
/** Without deviceMemory, the logical cores that stand in for 16 GB (see fillMemory). */
const FILL_CORES = 10;

/**
 * True when a High desktop has the memory to hold every area at once (STREAM_BUDGETS.everything,
 * about 2.2 GB of textures against 0.9 to 1.2 GB for the window): 16 GB or more.
 * - deviceMemory known: at least 16. A machine with 8 GB shares it with the system and the browser,
 *   and an integrated GPU (or an Apple one) takes its textures from the same 8 GB. A browser that
 *   still caps the figure at 8 does not fill.
 * - deviceMemory unknown (Firefox, Safari): at least 10 logical cores. The 8-core laptops that sell
 *   with 8 GB (and Apple's 8-core chips) stay out; machines with 10 or more rarely have under 16 GB.
 */
export function fillMemory(memory: MemoryHints): boolean {
  if (memory.deviceMemory !== undefined) return memory.deviceMemory >= FILL_MEMORY_GB;
  return (memory.hardwareConcurrency ?? 0) >= FILL_CORES;
}

function navigatorMemory(): MemoryHints {
  if (typeof navigator === "undefined") return {};
  const nav = navigator as Navigator & { deviceMemory?: number };
  return { deviceMemory: nav.deviceMemory, hardwareConcurrency: nav.hardwareConcurrency };
}

/** The visitor's data saver is on (navigator.connection.saveData: Chrome, Edge, Android browsers). */
function navigatorSaveData(): boolean {
  if (typeof navigator === "undefined") return false;
  return (navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData === true;
}

/** What the browser tells about the visitor's line (navigator.connection: Chrome, Edge, Android browsers). */
export interface ConnectionHints {
  /** "slow-2g", "2g", "3g" or "4g" (the fastest it names). */
  effectiveType?: string;
}

/** Lines that never fill in the background: the browser calls them 3G or slower. */
const SLOW_TYPES: readonly string[] = ["slow-2g", "2g", "3g"];

/**
 * The line is too slow to download every area in the background (only when the browser says so).
 * Only the browser's class of line counts, not its bandwidth figure (navigator.connection.downlink):
 * Chrome leaves traffic to localhost out of that figure and starts a new profile near 1.3-1.5 Mbps
 * until it has seen a fast download, and the budget is chosen when the world is made, before the
 * page's own downloads could raise it. A cut at 5 Mbps turned filling off on a fast desktop line
 * (measured in Chrome, which called the same line "4g").
 */
export function slowLine(connection: ConnectionHints): boolean {
  return connection.effectiveType !== undefined && SLOW_TYPES.includes(connection.effectiveType);
}

function navigatorConnection(): ConnectionHints {
  if (typeof navigator === "undefined") return {};
  const c = (navigator as Navigator & { connection?: ConnectionHints }).connection;
  return c ? { effectiveType: c.effectiveType } : {};
}

/**
 * The budget for a device (STREAM_BUDGETS): High desktops keep two areas each side, and so do
 * Medium ones with the memory for it (roomyMemory), else one each side; every touch screen (phones,
 * and tablets the tier ranks mid: they share the phone's memory limits, and iOS drops a tab at about
 * 1.5 GB) and the low tier keep one each side with the 2048 px textures, and the area alone on High
 * (its 4096 px textures). A High desktop with 16 GB (fillMemory) on a line that is not slow
 * (slowLine) also loads every other area in the background (`everything`). With the data saver on,
 * nothing is fetched ahead and nothing fills (the next area loads when it is needed). `memory`,
 * `saveData` and `connection` default to what the browser reports.
 */
export function streamBudget(
  tier: Tier,
  coarsePointer: boolean,
  memory: MemoryHints = navigatorMemory(),
  saveData = navigatorSaveData(),
  connection: ConnectionHints = navigatorConnection(),
): StreamBudget {
  const base = coarsePointer
    ? tier === "high"
      ? STREAM_BUDGETS.lean
      : STREAM_BUDGETS.low
    : tier === "low"
      ? STREAM_BUDGETS.low
      : tier === "high" || roomyMemory(memory)
        ? STREAM_BUDGETS.full
        : STREAM_BUDGETS.narrow;
  if (saveData) return { ...base, prefetch: "off" };
  if (!coarsePointer && tier === "high" && fillMemory(memory) && !slowLine(connection)) return STREAM_BUDGETS.everything;
  return base;
}

/**
 * GPU texture memory per byte downloaded, to estimate an area before it loads when the manifest
 * does not say (chunkTexBytes): the full set's areas measured 13-26 (WebP atlases in the GLBs
 * against RGBA8 with mips on the GPU), so 26 errs high. It only holds while geometry and textures
 * shrink together; smaller geometry alone (repacks, culling) makes it guess low. Loaded areas count
 * what was measured (textureBytes).
 */
const TEX_BYTES_PER_DOWNLOAD_BYTE = 26;
/** An area whose download size the manifest does not give: about the largest measured (228 MB). */
const UNKNOWN_AREA_TEX_BYTES = 256_000_000;
/** A texture whose size cannot be read: counted as a full 4096 px atlas. */
const UNKNOWN_TEXTURE_PX = 4096 * 4096;

/** Estimated GPU texture memory of a chunk before it loads, from its download size. */
export function estimateTexBytes(downloadBytes: number): number {
  return downloadBytes > 0 ? downloadBytes * TEX_BYTES_PER_DOWNLOAD_BYTE : UNKNOWN_AREA_TEX_BYTES;
}

/**
 * GPU texture memory of a chunk before it loads, for the texture set in use: the manifest's own
 * figure (`texBytes` / `texBytesLow`, RGBA8 with mips, written by the packer) when it has one, else
 * the estimate from the download size.
 */
export function chunkTexBytes(chunk: ChunkInfo, lowTextures: boolean): number {
  const low = lowTextures && chunk.filesLow !== null;
  const known = low ? chunk.texBytesLow : chunk.texBytes;
  if (known !== undefined && known !== null && known > 0) return known;
  return estimateTexBytes(low && chunk.bytesLow ? chunk.bytesLow : chunk.bytes);
}

/**
 * GPU memory the textures take (RGBA8, plus a third for the mip chain when there is one), from
 * their decoded sizes: read before the upload (the image, or the size prepare.ts keeps in
 * userData once it closes the image). Textures in `shared` (the sky) are not the chunk's own.
 */
export function textureBytes(textures: readonly Texture[], shared: ReadonlySet<Texture> = new Set()): number {
  let n = 0;
  for (const t of textures) {
    if (shared.has(t)) continue;
    const size = t.userData?.size as [number, number] | undefined;
    const img = t.image as { width?: number; height?: number } | null | undefined;
    const w = size?.[0] || img?.width || 0;
    const h = size?.[1] || img?.height || 0;
    const px = w > 0 && h > 0 ? w * h : UNKNOWN_TEXTURE_PX;
    const mips = t.generateMipmaps && t.minFilter !== NearestFilter && t.minFilter !== LinearFilter ? 4 / 3 : 1;
    n += px * 4 * mips;
  }
  return Math.round(n);
}

export interface StreamStatus {
  resident: { id: string; ready: boolean; drawn: boolean; tris: number; bytes: number; texBytes: number; retained: boolean; handover: boolean }[];
  loading: string[];
  /** Of `loading`, the background loads (lib/sect/chunks.ts ChunkPlan.fill). */
  filling: string[];
  /** Chunks not loaded now because they failed (waiting for a retry, or given up). */
  failed: string[];
  /** The global set's triangles (setGlobalTris). */
  globalTris: number;
}

/** What a camera resting at a stop will draw, and how far it has come (ChunkStreamer.settleAt). */
export interface DestinationStatus {
  /** The chunks it draws there (and the one the plan will fetch next for it, `expected`). */
  chunks: SettleSnapshot["chunks"];
  /** Chunks drawn there now that go once those are in. */
  leaving: string[];
  /**
   * Of `chunks` (the expected one aside: it holds nothing anyway), those whose bytes are still on
   * the way: not loaded yet, or a file of theirs still downloading (lib/sect/settle.ts
   * chunkArriving). The loading screen's wait lets go of them.
   */
  arriving: string[];
}

/** Someone waiting for a chunk (whenReady): released when it is ready, or when nobody wants it any more. */
interface Waiter {
  done: () => void;
  wanted: () => boolean;
}

export class ChunkStreamer {
  private readonly ctx: WorldContext;
  readonly chunks: readonly ChunkInfo[];
  private readonly onChange: () => void;
  private readonly sets = new Map<string, LoadedSet>();
  private readonly loading = new Map<string, AbortController>();
  /** Bytes each loading chunk has downloaded so far, per file (settleAt's progress). */
  private readonly received = new Map<string, Map<string, number>>();
  /** Loading chunks whose files have all downloaded (parsing and preparing may still run). */
  private readonly fetched = new Set<string>();
  /** Failed tries per chunk and when the last one failed (cleared by a load that works). */
  private readonly failures = new Map<string, { count: number; at: number }>();
  private readonly waiters = new Map<string, Waiter[]>();
  /** Loads whose main-thread part waits for calm() (a prefetch started while the camera moves). */
  private readonly gates = new Map<string, (() => void)[]>();
  /** The camera was at rest at the last update. */
  private idle = false;
  /** Given-up chunks get their tries back when the browser comes back online. */
  private readonly onOnline = () => {
    for (const [id, f] of this.failures) if (retryDelayMs(f.count) === null) this.failures.delete(id);
  };
  /** What each loaded set holds (triangles, texture memory), measured on load, for the residency budget. */
  private readonly costs = new Map<string, ChunkCost>();
  private disposals: LoadedSet[] = [];
  /** Direction of travel, smoothed (lib/sect/chunks.ts travelDirection). */
  private travel: Travel | null = null;
  /** Where the first area's stretch ends and the last one's starts (null: unknown, or one area). */
  private readonly ends: [number, number] | null;
  /** The areas' own stretches in flight order (lib/sect/chunks.ts travelAfterJump). */
  private readonly cores: (readonly [number, number])[];
  /** The far jump under way (update's `target`): the frame it counts from and the one it goes to (jumpLeg). */
  private jump: JumpLeg | null = null;
  private disposed = false;
  /** The latest plan (for the debug HUD and tests in the browser). */
  plan: ChunkPlan | null = null;
  /** Chunks for the planner: need ranges, the area's own frames (ranking), triangles and texture estimates. */
  readonly spans: ChunkSpan[];
  private readonly window: Partial<PlanWindow>;
  private budget: StreamBudget;
  /** The global set's triangles (setGlobalTris), for status(). */
  private globalTris = 0;
  /**
   * Fast travel's settled wait is watching this stop (settleAt, every display frame while the ink is
   * up), until `until`: meanwhile only the loads it waits for start (SETTLE.around of the stop), so
   * the window's further areas do not share the line with them. They start once it lets go.
   */
  private settling: { frame: number; until: number; around: number } | null = null;
  /**
   * Background loads may start (a budget with fillTexBytes): the page opens this once the visitor
   * is in, so the loading screen's wait for the first stop never shares the line with them.
   */
  fillOpen = false;
  /** Loads under way that were started as background loads (ChunkPlan.fill). */
  private readonly fillLoads = new Set<string>();

  constructor(ctx: WorldContext, onChange: () => void, budget: StreamBudget = ctx.lowTextures ? STREAM_BUDGETS.low : STREAM_BUDGETS.full) {
    this.ctx = ctx;
    const { manifest, meta, camera } = ctx.data;
    this.chunks = manifest.chunks;
    this.onChange = onChange;
    const cores = holdCores(camera.holds, camera.frameStart, camera.frameEnd);
    this.spans = this.chunks.map((c) => {
      const a = meta.areas.find((x) => x.id === c.id);
      const core: [number, number] | undefined = a && a.frameEnd > a.frameStart ? [a.frameStart, a.frameEnd] : cores.get(c.id);
      const hold = camera.holds.find((h) => h.id === c.id)?.frame;
      return { id: c.id, need: c.need, core, ...(hold !== undefined ? { hold } : {}), tris: c.tris, texBytes: chunkTexBytes(c, ctx.lowTextures) };
    });
    const areas = this.spans.flatMap((s) => (s.core ? [s.core] : []));
    const first = Math.min(...areas.map((c) => c[1]));
    const last = Math.max(...areas.map((c) => c[0]));
    this.ends = areas.length > 1 && first < last ? [first, last] : null;
    this.cores = this.spans.map((s) => s.core ?? s.need);
    this.budget = budget;
    this.window = {};
    this.applyBudget();
    if (typeof window !== "undefined" && typeof window.addEventListener === "function") window.addEventListener("online", this.onOnline);
  }

  private applyBudget(): void {
    const b = this.budget;
    // Filling keeps what it loads through the residency budget: texture memory alone bounds it.
    const fill = b.fillTexBytes > 0;
    Object.assign(this.window, {
      around: b.around,
      spare: b.spare,
      lookBack: b.lookBack,
      fill,
      retainTris: fill ? Infinity : 0,
      retainTexBytes: b.fillTexBytes,
    });
  }

  /**
   * The global set's triangles (the backdrop and every area's stand-in, never dropped), for
   * status(). The window counts areas, not triangles, so nothing is planned from them.
   */
  setGlobalTris(tris: number): void {
    this.globalTris = tris;
  }

  /**
   * Another budget from the next update on (the visitor picked another tier with the same texture
   * set: desktop High and Medium, whose windows differ on a smaller machine). Areas the new window
   * no longer holds are dropped then.
   */
  setBudget(budget: StreamBudget): void {
    this.budget = budget;
    this.applyBudget();
  }

  /** Chunks a stop at `frame` needs (the area it lands in), nearest first. */
  needAt(frame: number): string[] {
    return planChunks({ chunks: this.spans, frame, direction: 1, resident: new Set(), loading: new Set(), target: frame, window: this.window }).need;
  }

  has(id: string): boolean {
    return this.chunks.some((c) => c.id === id);
  }

  isReady(id: string): boolean {
    return this.sets.get(id)?.ready === true;
  }

  /** The chunk failed and is not to be loaded now (waiting for its next try, or given up). */
  isFailed(id: string, now = performance.now()): boolean {
    const f = this.failures.get(id);
    if (!f) return false;
    const wait = retryDelayMs(f.count);
    return wait === null || now - f.at < wait;
  }

  private failedIds(now = performance.now()): string[] {
    return [...this.failures.keys()].filter((id) => this.isFailed(id, now));
  }

  /** Chunks a stop at `frame` needs that are not ready to draw yet (failed ones excluded). */
  missingAt(frame: number): string[] {
    return this.needAt(frame).filter((id) => !this.isReady(id) && !this.isFailed(id));
  }

  /**
   * What a camera resting at `frame` will draw once streaming there has run its course (fast
   * travel's settled wait, lib/sect/settle.ts destinationChunks): the chunks the plan at rest keeps,
   * needs or prefetches there within SETTLE.around areas of the stop's own (its view and its direct
   * neighbours: the window's areas further out come in after the ink), each with how far it has come
   * (chunkDone) and its download size, and the drawn chunks that go once those are in. The prefetch
   * counts only when this budget fetches ahead (not with the data saver: its stand-in stays). The
   * area the plan will fetch next once these are in is listed too, `expected` (for the progress
   * shown: it may not come after all). While it is called, update() starts only the loads it waits
   * for (SETTLE_FOCUS_MS): the window's further areas would otherwise share the line with them and
   * make the wait about a third longer. `around`: how many areas each side of the stop's own it
   * covers (the loading screen's wait for the first stop: every area its view draws, Infinity; then
   * the loads start side by side, the prefetch among them: GATE_PARALLEL).
   */
  settleAt(frame: number, around: number = SETTLE.around): DestinationStatus {
    this.settling = { frame, until: performance.now() + SETTLE_FOCUS_MS, around };
    const failed = this.failedIds();
    const ready = new Set<string>(failed);
    for (const [id, s] of this.sets) if (s.ready) ready.add(id);
    const resident = new Set([...this.sets.keys(), ...failed]);
    const loading = new Set(this.loading.keys());
    const base = { chunks: this.spans, frame, direction: this.travel?.direction ?? 1, loaded: this.costs, window: this.window };
    const ahead = this.budget.prefetch !== "off";
    const now = destinationChunks({ ...base, resident, loading, ready }, ahead, around);
    // As if those were all in: what the plan wants then (the prefetch it starts once they are).
    const assumed = new Set(now.want);
    const next = destinationChunks(
      {
        ...base,
        resident: new Set([...resident, ...assumed]),
        loading: new Set([...loading].filter((id) => !assumed.has(id))),
        ready: new Set([...ready, ...assumed]),
      },
      ahead,
      around,
    );
    const stateOf = (id: string) => ({
      done: ready.has(id),
      resident: this.sets.has(id),
      received: [...(this.received.get(id)?.values() ?? [])].reduce((a, b) => a + b, 0),
      total: this.downloadBytes(id),
      fetched: this.loading.has(id) && this.fetched.has(id),
    });
    const status = (id: string, expected: boolean) => ({
      id,
      done: chunkDone(stateOf(id)),
      weight: this.downloadBytes(id),
      ...(expected ? { expected } : {}),
    });
    const chunks = [...now.want.map((id) => status(id, false)), ...next.want.filter((id) => !assumed.has(id)).map((id) => status(id, true))];
    return {
      chunks,
      leaving: now.leaving,
      arriving: now.want.filter((id) => chunkArriving(stateOf(id))),
    };
  }

  /** A chunk's download for the texture set in use (bytes; 0 when the manifest does not say). */
  private downloadBytes(id: string): number {
    const c = this.chunks.find((x) => x.id === id);
    if (!c) return 0;
    return (this.ctx.lowTextures && c.filesLow !== null ? c.bytesLow : null) ?? c.bytes ?? 0;
  }

  /** Resident sets in flight order (loaded; possibly not yet uploaded). */
  list(): LoadedSet[] {
    return this.chunks.map((c) => this.sets.get(c.id)).filter((s): s is LoadedSet => s !== undefined);
  }

  /**
   * The area the camera at `frame` is in: the one whose own stretch holds it, else the nearest
   * (lib/sect/chunks.ts areaIndexAt). Null without areas. The quality ladder's stand-in step draws
   * only this one (scene.tsx World).
   */
  areaAt(frame: number): string | null {
    const i = areaIndexAt(this.cores, frame);
    return i < 0 ? null : this.spans[i].id;
  }

  status(): StreamStatus {
    return {
      resident: this.list().map((s) => ({
        id: s.id,
        ready: s.ready,
        drawn: s.drawn,
        tris: s.tris,
        bytes: s.bytes,
        texBytes: this.costs.get(s.id)?.texBytes ?? 0,
        retained: this.plan?.retain.includes(s.id) === true,
        handover: this.plan?.handover.includes(s.id) === true,
      })),
      loading: [...this.loading.keys()],
      filling: [...this.fillLoads].filter((id) => this.loading.has(id)),
      failed: this.failedIds(),
      globalTris: this.globalTris,
    };
  }

  /**
   * Plan at the camera frame (and a jump's destination, when one is under way), then act on it.
   * `idle`: the camera is at rest: a phone's prefetch may start, and a prefetch that downloaded
   * during the flight may now be parsed and prepared (a load done then is ready before the flight
   * reaches the area, instead of costing frames during it).
   * `lookingBack`: the view is turned round at rest, so one more area behind may load too when the
   * budget has a `lookBack` slot (none does now: the window holds the areas behind).
   */
  update(
    frame: number,
    target: number | null,
    idle: boolean,
    opts?: Pick<SetLoadOptions, "onBytes" | "onFileDone">,
    lookingBack = false,
  ): ChunkPlan | null {
    if (this.disposed || this.chunks.length === 0) return null;
    // A small step back (an overshoot at a stop corrected) does not turn the plan around: that would
    // drop the area prefetched ahead into the spare slot, and it would then load mid-flight.
    const turn = this.window.behind ?? DEFAULT_WINDOW.behind;
    this.travel = travelDirection(this.travel, frame, turn);
    // A far jump back has landed (its target is gone and the camera is there): face forward again
    // unless it was a step to the area just before (lib/sect/chunks.ts travelAfterJump). A jump the
    // visitor's own scrolling cut short leaves the direction to that scrolling. K pressed again
    // during the flight counts as another one-area step, not as one far jump (jumpLeg).
    if (target !== null) this.jump = jumpLeg(this.jump, frame, target, this.cores);
    else if (this.jump) {
      const j = this.jump;
      this.jump = null;
      if (Math.abs(frame - j.to) <= turn) this.travel = travelAfterJump(this.travel, j.from, j.to, frame, this.cores);
    }
    // At either end of the flight nothing lies further that way (Home, or the gate picked on the
    // rail, leaves the camera travelling back): face the only way on, so the next area is
    // prefetched there too.
    const e = this.ends;
    if (e && this.travel.direction < 0 && frame <= e[0]) this.travel = { direction: 1, extreme: frame };
    else if (e && this.travel.direction > 0 && frame >= e[1]) this.travel = { direction: -1, extreme: frame };
    this.idle = idle;
    this.releaseStaleWaiters();
    const failed = this.failedIds();
    // Ready to draw, or failed (nothing to wait for): the plan hands over until the needed are.
    const ready = new Set<string>(failed);
    for (const [id, s] of this.sets) if (s.ready) ready.add(id);
    const input = {
      chunks: this.spans,
      frame,
      direction: this.travel.direction,
      // Failed chunks count as resident, so they are not loaded again before their retry is due.
      resident: new Set([...this.sets.keys(), ...failed]),
      loading: new Set(this.loading.keys()),
      target,
      lookingBack,
      loaded: this.costs,
      ready,
      window: this.window,
    };
    const plan = planChunks(input);
    this.plan = plan;

    let changed = false;
    for (const id of plan.cancel) {
      // A far jump is waiting for this one (a newer plan may not look there yet): let it finish
      // rather than start it again from zero; the next plan drops it if nobody wants it.
      if (this.waiters.has(id)) continue;
      this.abortLoad(id);
    }
    for (const id of plan.drop) {
      const set = this.sets.get(id);
      if (!set) continue;
      this.sets.delete(id);
      this.costs.delete(id);
      // Off the screen at once (never drawn again); its GPU copies go after React's commit (takeDisposals).
      retireSet(set);
      this.disposals.push(set);
      this.resolve(id);
      changed = true;
    }
    // While fast travel waits at a stop, only what it waits for starts (the stop's own area and its
    // neighbours, a prefetch among them when the window is the area alone); the rest once it is done.
    const settling = this.settling !== null && performance.now() < this.settling.until ? this.settling : null;
    const focus = settling?.frame ?? null;
    const order = new Map(this.spans.map((s, i) => [s.id, i]));
    const centre = focus === null ? -1 : windowCentreAt(this.spans, focus);
    const waitedFor = (id: string) => settling === null || Math.abs((order.get(id) ?? Infinity) - centre) <= settling.around;
    // One download at a time, nearest first (MAX_PARALLEL loads). Behind the loading screen, waiting
    // for the first stop, more loads side by side (GATE_PARALLEL), their downloads still one at a time.
    const gate = settling !== null && settling.around === Infinity;
    const downloading = () => [...this.loading.keys()].some((id) => !this.fetched.has(id));
    // A needed area never queues behind a background download. While the plan has areas to load,
    // a background load still downloading stops when the plan does not need it and nobody waits for
    // it (it is picked again later). So does a load that only filling keeps: a window load the camera
    // has moved away from, which the plan without filling would have cancelled by now.
    if (plan.load.length > 0) {
      const needed = new Set(plan.need);
      let usualCancel: Set<string> | null = null;
      for (const id of [...this.loading.keys()]) {
        if (this.fetched.has(id) || needed.has(id) || this.waiters.has(id)) continue;
        if (!this.fillLoads.has(id)) {
          if (this.window.fill !== true) continue;
          usualCancel ??= new Set(planChunks({ ...input, window: { ...this.window, fill: false } }).cancel);
          if (!usualCancel.has(id)) continue;
        }
        this.abortLoad(id);
      }
    }
    for (const id of plan.load) {
      if (this.loading.size >= (gate ? GATE_PARALLEL : MAX_PARALLEL) || downloading()) break;
      if (waitedFor(id)) this.start(id, opts);
    }
    const mode = this.budget.prefetch;
    // And the area the plan prefetches once those are in, beside them (planned as if they were in:
    // it takes the spare slot it would take then, so the plans that follow keep it, and the wait then
    // covers it as a load under way), its download after theirs.
    if (gate && plan.prefetch === null && (mode === "moving" || (mode === "rest" && idle)) && this.loading.size < GATE_PARALLEL && !downloading()) {
      const inAll = new Set([...input.resident, ...plan.need]);
      const later = planChunks({ ...input, resident: inAll, ready: new Set([...ready, ...plan.need]), loading: new Set([...input.loading].filter((id) => !inAll.has(id))) });
      if (later.prefetch && waitedFor(later.prefetch)) this.start(later.prefetch);
    }
    if (plan.prefetch && waitedFor(plan.prefetch) && this.loading.size === 0 && (mode === "moving" || (mode === "rest" && idle))) this.start(plan.prefetch);
    // Then the next area in the background (filling), once the page lets it (after Enter), never
    // while fast travel's wait watches a stop, and only with nothing else loading. Its main-thread
    // part waits for a rest, as a prefetch's does (calmFor).
    if (this.fillOpen && plan.fill && settling === null && this.loading.size === 0 && (mode === "moving" || (mode === "rest" && idle))) {
      this.start(plan.fill);
      if (this.loading.has(plan.fill)) this.fillLoads.add(plan.fill);
    }
    this.openGates();
    if (changed) this.onChange();
    return plan;
  }

  /**
   * May the main-thread part of loading `id` (parsing, preparing) run now? At rest, when the
   * area is needed (no longer just prefetched), or once nothing waits for it any more.
   */
  private calmFor(id: string): boolean {
    return this.disposed || this.idle || !this.loading.has(id) || this.plan === null || this.plan.need.includes(id);
  }

  /** Resolves once loading `id` may use the main thread (calmFor), checked at every update. */
  private calm(id: string): Promise<void> {
    if (this.calmFor(id)) return Promise.resolve();
    return new Promise((resolve) => {
      const list = this.gates.get(id) ?? [];
      list.push(resolve);
      this.gates.set(id, list);
    });
  }

  private openGates(): void {
    for (const [id, list] of [...this.gates]) {
      if (!this.calmFor(id)) continue;
      this.gates.delete(id);
      for (const fn of list) fn();
    }
  }

  /** Stops the load of `id` under way (cancelled, or a background load making way for a needed one). */
  private abortLoad(id: string): void {
    this.loading.get(id)?.abort();
    this.loading.delete(id);
    this.received.delete(id);
    this.fillLoads.delete(id);
  }

  private start(id: string, opts?: Pick<SetLoadOptions, "onBytes" | "onFileDone">): void {
    const chunk = this.chunks.find((c) => c.id === id);
    if (!chunk || this.loading.has(id) || this.sets.has(id)) return;
    const ac = new AbortController();
    this.loading.set(id, ac);
    const got = new Map<string, number>();
    this.received.set(id, got);
    this.fetched.delete(id);
    const files = chunkFiles(chunk, this.ctx.lowTextures);
    // Files whose bytes are all in: the download said it is done (it reads to the end, so a size the
    // server does not say, or a body it decompresses, cannot make it look done early), or the file is
    // over (loaded, or failed: a decorative one the set goes on without).
    const arrived = new Set<string>();
    const arrive = (url: string) => {
      arrived.add(url);
      if (arrived.size >= files.length && this.loading.get(id) === ac) this.fetched.add(id);
    };
    loadSet(this.ctx, id, [chunk.need[0], chunk.need[1]], files, {
      signal: ac.signal,
      calm: () => this.calm(id),
      ...opts,
      // Bytes per file for settleAt and for the next download (update), and on to the caller's
      // tracker when it has one.
      onBytes: (url) => {
        const outer = opts?.onBytes?.(url);
        return (loaded, total, done) => {
          got.set(url, loaded);
          if (done) arrive(url);
          outer?.(loaded, total, done);
        };
      },
      onFileDone: (url) => {
        arrive(url);
        opts?.onFileDone?.(url);
      },
    })
      .then((set) => {
        if (this.received.get(id) === got) this.received.delete(id);
        if (this.loading.get(id) !== ac || this.disposed || ac.signal.aborted) {
          disposeSet(this.ctx, set);
          return;
        }
        this.loading.delete(id);
        this.fillLoads.delete(id);
        this.failures.delete(id);
        this.sets.set(id, set);
        // Measured now, before the upload closes the images (prepare.ts keeps their sizes anyway).
        const shared = new Set<Texture>(this.ctx.sky ? [this.ctx.sky] : []);
        this.costs.set(id, { tris: set.tris, texBytes: textureBytes(set.textures, shared) });
        this.onChange();
      })
      .catch((e) => {
        if (this.received.get(id) === got) this.received.delete(id);
        if (this.loading.get(id) === ac) {
          this.loading.delete(id);
          this.fillLoads.delete(id);
        }
        if (ac.signal.aborted) return;
        const count = (this.failures.get(id)?.count ?? 0) + 1;
        this.failures.set(id, { count, at: performance.now() });
        const next = retryDelayMs(count);
        console.warn(`[sect] chunk ${id} failed to load (try ${count}); ${next === null ? "the stand-in stays" : `trying again in ${next / 1000} s`}`, e);
        this.resolve(id);
      });
  }

  /** The render loop uploaded the set's textures: it may be drawn now. */
  markReady(id: string): void {
    const set = this.sets.get(id);
    if (!set || set.ready) return;
    set.ready = true;
    this.resolve(id);
    this.onChange();
  }

  private resolve(id: string): void {
    const list = this.waiters.get(id);
    if (!list) return;
    this.waiters.delete(id);
    for (const w of list) w.done();
  }

  /**
   * Lets go of waiters nobody wants any more (a jump cancelled by a newer one or by the visitor's
   * own scrolling): their promises resolve, and a load only they kept going may be cancelled.
   */
  private releaseStaleWaiters(): void {
    for (const [id, list] of [...this.waiters]) {
      const keep = list.filter((w) => w.wanted());
      if (keep.length === list.length) continue;
      if (keep.length > 0) this.waiters.set(id, keep);
      else this.waiters.delete(id);
      for (const w of list) if (!keep.includes(w)) w.done();
    }
  }

  /**
   * Resolves when chunk `id` is ready to draw, or failed, or was dropped, or after `timeoutMs`
   * (a far jump never waits forever: the backdrop proxy stands in), or once `wanted` says false (the
   * jump was cancelled; checked at every update): a waiting jump keeps its chunk loading even when
   * a newer plan looks elsewhere, and a cancelled one no longer does.
   */
  whenReady(id: string, timeoutMs = 15000, wanted: () => boolean = () => true): Promise<void> {
    if (!this.has(id) || this.isReady(id) || this.isFailed(id)) return Promise.resolve();
    return new Promise((resolve) => {
      const timer = window.setTimeout(done, timeoutMs);
      function done() {
        window.clearTimeout(timer);
        resolve();
      }
      const list = this.waiters.get(id) ?? [];
      list.push({ done, wanted });
      this.waiters.set(id, list);
    });
  }

  /** Dropped sets, to dispose once the scene no longer holds them (after React's commit). */
  takeDisposals(): LoadedSet[] {
    const out = this.disposals;
    this.disposals = [];
    return out;
  }

  flushDisposals(): void {
    for (const s of this.takeDisposals()) disposeSet(this.ctx, s);
  }

  /** True once dispose() ran (the page went away): a far jump still waiting must not go on. */
  get isDisposed(): boolean {
    return this.disposed;
  }

  dispose(): void {
    this.disposed = true;
    if (typeof window !== "undefined" && typeof window.removeEventListener === "function") window.removeEventListener("online", this.onOnline);
    for (const ac of this.loading.values()) ac.abort();
    this.loading.clear();
    this.fillLoads.clear();
    this.received.clear();
    this.fetched.clear();
    this.openGates();
    for (const s of this.sets.values()) disposeSet(this.ctx, s);
    this.sets.clear();
    this.costs.clear();
    this.flushDisposals();
    for (const id of [...this.waiters.keys()]) this.resolve(id);
  }
}
