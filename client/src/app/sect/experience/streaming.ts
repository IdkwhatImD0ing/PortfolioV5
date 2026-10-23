/**
 * Streams the manifest's chunks around the camera (lib/sect/chunks.ts decides what; this does it):
 * starts loads, prefetches the next chunk (desktops as soon as nothing else loads, phones while the
 * camera rests), cancels loads nobody wants any more, keeps the area on screen until the next one
 * can be drawn, retries failed loads a few times and hands dropped chunks back for disposal once
 * React has taken them out of the scene. On roomy desktops it measures what each loaded chunk holds,
 * so passed areas can stay within a residency budget (STREAM_BUDGETS.retain). For fast travel's
 * settled wait it says what a camera resting at a stop will draw and how far that has come (settleAt).
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
  type ChunkCost,
  type ChunkPlan,
  type ChunkSpan,
  type JumpLeg,
  type PlanWindow,
  type Travel,
} from "@/lib/sect/chunks";
import type { DeviceInfo, Tier } from "@/lib/sect/runtime";
import { chunkDone, destinationChunks, type SettleSnapshot } from "@/lib/sect/settle";
import type { ChunkInfo } from "@/lib/sect/types";
import { chunkFiles, disposeSet, loadSet, retireSet, type LoadedSet, type SetLoadOptions, type WorldContext } from "./assets";

/** Loads at once (needed chunks first; a prefetch only when nothing else is loading). */
const MAX_PARALLEL = 2;
/** Tries a chunk gets (the first load and its retries) before the backdrop's proxy stands in for good. */
const MAX_TRIES = 3;
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
 * Triangles resident at once (global set included) and how many of the nearest areas are always
 * allowed past that budget (see lib/sect/chunks.ts). Desktops keep the area they are in and the
 * next; the low (phone) tier draws only the area it is in, with the backdrop's proxies standing in
 * for its neighbours, so a phone holds about 1.2-1.9 M triangles instead of 3.4 M (plus the spare).
 *
 * `spare`: one area past the budget (the three-chunk cap still holds): the next one, prefetched so
 * it does not load mid-flight, or during a jump the one the camera waits in. Phones too: without it
 * a phone showed the backdrop's stand-ins for 4-7 s at every stop on a 12 Mbps network; with it the
 * area is there on arrival, for about 60 MB more of textures (150-165 MB) while two are resident.
 *
 * `prefetch`: when the next area may start loading (PrefetchMode). Desktops download it during the
 * flight (a visitor who never pauses saw five stops arrive as stand-ins); phones wait for a rest
 * (their data and CPU are scarcer).
 *
 * `lookBack`: while the visitor looks back at rest (free look turned past 90 degrees), desktops
 * may load one more area, the one behind, past the cap and the budget (four areas instead of
 * three). Phones keep the backdrop's proxy there.
 *
 * `retainTris` / `retainTexBytes` (`retain`, high-tier desktops with memory to spare only, see
 * streamBudget): areas already loaded stay after the camera has passed them, nearest first, while
 * all the areas resident fit 5 M triangles and 900 MB of texture memory; the farthest go first.
 * Scrolling back to them is then instant. Areas only: the global set (about 0.7 M triangles and
 * 8 MB, never dropped) comes on top. The full set's 11 areas hold about 11.7 M triangles and
 * 1.82 GB of RGBA8 textures with mips (115-228 MB an area), so this keeps four or five areas, never
 * all of them; triangles are what binds (a flight there and back peaks at about 4.9 M and 740 MB).
 * The usual desktop plan already peaks at about 3.9 M. Retained areas are drawn while their need
 * range holds the frame (World in scene.tsx), so the triangles drawn can rise by as much (about a
 * fifth over that peak). 0 turns it off: phones, tablets, the mid tier and the plain desktop budget.
 */
export const STREAM_BUDGETS = {
  full: { triBudget: 2_500_000, minResident: 2, spare: 1, lookBack: 1, retainTris: 0, retainTexBytes: 0, prefetch: "moving" },
  retain: { triBudget: 2_500_000, minResident: 2, spare: 1, lookBack: 1, retainTris: 5_000_000, retainTexBytes: 900_000_000, prefetch: "moving" },
  low: { triBudget: 1_200_000, minResident: 1, spare: 1, lookBack: 0, retainTris: 0, retainTexBytes: 0, prefetch: "rest" },
} as const satisfies Record<string, StreamBudget>;

export interface StreamBudget {
  triBudget: number;
  minResident: number;
  /** Areas allowed past the triangle budget (lib/sect/chunks.ts PlanWindow.spare). */
  spare: number;
  /** When the next area may start loading. */
  prefetch: PrefetchMode;
  /** Areas behind allowed past the cap while looking back (lib/sect/chunks.ts PlanWindow.lookBack). */
  lookBack: number;
  /** Residency budget for keeping loaded areas the camera has passed (PlanWindow.retainTris); 0 = off. */
  retainTris: number;
  retainTexBytes: number;
}

/** What the browser tells about the machine's memory (lib/sect/runtime.ts DeviceInfo). */
export type MemoryHints = Pick<DeviceInfo, "deviceMemory" | "hardwareConcurrency">;

/** navigator.deviceMemory is in GB and capped at 8 (Chrome, Edge): 8 means 8 GB or more. */
const RETAIN_MIN_MEMORY_GB = 8;
/** Without deviceMemory (Firefox), logical cores stand in for it (see canRetain). */
const RETAIN_MIN_CORES = 8;

/**
 * True when a device may keep areas loaded past the usual plan (STREAM_BUDGETS.retain): the high
 * tier (a discrete or Apple-silicon GPU, lib/sect/runtime.ts chooseTier) with a mouse, and 8 GB or
 * more. Conservative on purpose:
 * - deviceMemory known (Chrome, Edge): at least 8, its cap. An 8 GB Apple-silicon Mac in Chrome
 *   qualifies; its GPU shares that memory, and the budget caps what retained areas add.
 * - deviceMemory unknown (Firefox): only with at least 8 logical cores. A desktop with that many
 *   and a GPU the tier ranks high is unlikely to have less than 8 GB; 4-core machines are where
 *   small memory is common. Firefox's fingerprinting guard reports 2 cores, which the tier already
 *   ranks mid. Safari hides both the memory and the GPU ("Apple GPU"), so it ranks mid and never
 *   gets here.
 * - Touch screens never (iOS drops a tab at about 1.5 GB), nor the mid and low tiers.
 */
export function canRetain(tier: Tier, coarsePointer: boolean, memory: MemoryHints): boolean {
  if (tier !== "high" || coarsePointer) return false;
  if (memory.deviceMemory !== undefined) return memory.deviceMemory >= RETAIN_MIN_MEMORY_GB;
  return (memory.hardwareConcurrency ?? 0) >= RETAIN_MIN_CORES;
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

/**
 * The budget for a device: every touch screen (phones, and tablets the tier ranks mid: they share
 * the phone's memory limits, and iOS drops a tab at about 1.5 GB) and the low tier keep only the
 * area they are in (and a spare slot); desktops keep that area and the next, and high-tier desktops
 * with memory to spare also keep the areas they have passed (canRetain). With the data saver on,
 * nothing is fetched ahead (the next area loads when it is needed). `memory` and `saveData` default
 * to what the browser reports.
 */
export function streamBudget(tier: Tier, coarsePointer: boolean, memory: MemoryHints = navigatorMemory(), saveData = navigatorSaveData()): StreamBudget {
  const base = tier === "low" || coarsePointer ? STREAM_BUDGETS.low : canRetain(tier, coarsePointer, memory) ? STREAM_BUDGETS.retain : STREAM_BUDGETS.full;
  return saveData ? { ...base, prefetch: "off" } : base;
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
  /** Chunks not loaded now because they failed (waiting for a retry, or given up). */
  failed: string[];
}

/** What a camera resting at a stop will draw, and how far it has come (ChunkStreamer.settleAt). */
export interface DestinationStatus {
  /** The chunks it draws there (and the one the plan will fetch next for it, `expected`). */
  chunks: SettleSnapshot["chunks"];
  /** Chunks drawn there now that go once those are in. */
  leaving: string[];
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
  /** The global set's triangles (setGlobalTris), kept so a new budget counts them too. */
  private globalTris = 0;

  constructor(ctx: WorldContext, onChange: () => void, budget: StreamBudget = ctx.lowTextures ? STREAM_BUDGETS.low : STREAM_BUDGETS.full) {
    this.ctx = ctx;
    const { manifest, meta, camera } = ctx.data;
    this.chunks = manifest.chunks;
    this.onChange = onChange;
    const cores = holdCores(camera.holds, camera.frameStart, camera.frameEnd);
    this.spans = this.chunks.map((c) => {
      const a = meta.areas.find((x) => x.id === c.id);
      const core: [number, number] | undefined = a && a.frameEnd > a.frameStart ? [a.frameStart, a.frameEnd] : cores.get(c.id);
      return { id: c.id, need: c.need, core, tris: c.tris, texBytes: chunkTexBytes(c, ctx.lowTextures) };
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
    Object.assign(this.window, {
      triBudget: Math.max(b.triBudget * 0.4, b.triBudget - this.globalTris),
      minResident: b.minResident,
      spare: b.spare,
      lookBack: b.lookBack,
      retainTris: b.retainTris,
      retainTexBytes: b.retainTexBytes,
    });
  }

  /** The global set's triangles count against the budget too (not the residency budget: areas only). */
  setGlobalTris(tris: number): void {
    this.globalTris = tris;
    this.applyBudget();
  }

  /**
   * Another budget from the next update on (the visitor picked another tier with the same texture
   * set: High keeps passed areas, Medium does not). Areas the new budget has no room for are dropped
   * then.
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
   * needs or prefetches there, each with how far it has come (chunkDone) and its download size, and
   * the drawn chunks that go once those are in. The prefetch counts only when this budget fetches
   * ahead (not with the data saver: its stand-in stays). The area the plan will fetch next once these
   * are in is listed too, `expected` (for the progress shown: it may not come after all).
   */
  settleAt(frame: number): DestinationStatus {
    const failed = this.failedIds();
    const ready = new Set<string>(failed);
    for (const [id, s] of this.sets) if (s.ready) ready.add(id);
    const resident = new Set([...this.sets.keys(), ...failed]);
    const loading = new Set(this.loading.keys());
    const base = { chunks: this.spans, frame, direction: this.travel?.direction ?? 1, loaded: this.costs, window: this.window };
    const ahead = this.budget.prefetch !== "off";
    const now = destinationChunks({ ...base, resident, loading, ready }, ahead);
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
    );
    const status = (id: string, expected: boolean) => ({
      id,
      done: chunkDone({
        done: ready.has(id),
        resident: this.sets.has(id),
        received: [...(this.received.get(id)?.values() ?? [])].reduce((a, b) => a + b, 0),
        total: this.downloadBytes(id),
      }),
      weight: this.downloadBytes(id),
      ...(expected ? { expected } : {}),
    });
    return {
      chunks: [...now.want.map((id) => status(id, false)), ...next.want.filter((id) => !assumed.has(id)).map((id) => status(id, true))],
      leaving: now.leaving,
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
      failed: this.failedIds(),
    };
  }

  /**
   * Plan at the camera frame (and a jump's destination, when one is under way), then act on it.
   * `idle`: the camera is at rest: a phone's prefetch may start, and a prefetch that downloaded
   * during the flight may now be parsed and prepared (a load done then is ready before the flight
   * reaches the area, instead of costing frames during it).
   * `lookingBack`: the view is turned round at rest, so the area behind may load too (desktops;
   * the budget's `lookBack` is 0 on phones).
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
    const plan = planChunks({
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
    });
    this.plan = plan;

    let changed = false;
    for (const id of plan.cancel) {
      // A far jump is waiting for this one (a newer plan may not look there yet): let it finish
      // rather than start it again from zero; the next plan drops it if nobody wants it.
      if (this.waiters.has(id)) continue;
      this.loading.get(id)?.abort();
      this.loading.delete(id);
      this.received.delete(id);
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
    for (const id of plan.load) {
      if (this.loading.size >= MAX_PARALLEL) break;
      this.start(id, opts);
    }
    const mode = this.budget.prefetch;
    if (plan.prefetch && this.loading.size === 0 && (mode === "moving" || (mode === "rest" && idle))) this.start(plan.prefetch);
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

  private start(id: string, opts?: Pick<SetLoadOptions, "onBytes" | "onFileDone">): void {
    const chunk = this.chunks.find((c) => c.id === id);
    if (!chunk || this.loading.has(id) || this.sets.has(id)) return;
    const ac = new AbortController();
    this.loading.set(id, ac);
    const got = new Map<string, number>();
    this.received.set(id, got);
    loadSet(this.ctx, id, [chunk.need[0], chunk.need[1]], chunkFiles(chunk, this.ctx.lowTextures), {
      signal: ac.signal,
      calm: () => this.calm(id),
      ...opts,
      // Bytes per file for settleAt, and on to the caller's tracker when it has one.
      onBytes: (url) => {
        const outer = opts?.onBytes?.(url);
        return (loaded, total) => {
          got.set(url, loaded);
          outer?.(loaded, total);
        };
      },
    })
      .then((set) => {
        if (this.received.get(id) === got) this.received.delete(id);
        if (this.loading.get(id) !== ac || this.disposed || ac.signal.aborted) {
          disposeSet(this.ctx, set);
          return;
        }
        this.loading.delete(id);
        this.failures.delete(id);
        this.sets.set(id, set);
        // Measured now, before the upload closes the images (prepare.ts keeps their sizes anyway).
        const shared = new Set<Texture>(this.ctx.sky ? [this.ctx.sky] : []);
        this.costs.set(id, { tris: set.tris, texBytes: textureBytes(set.textures, shared) });
        this.onChange();
      })
      .catch((e) => {
        if (this.received.get(id) === got) this.received.delete(id);
        if (this.loading.get(id) === ac) this.loading.delete(id);
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
    this.received.clear();
    this.openGates();
    for (const s of this.sets.values()) disposeSet(this.ctx, s);
    this.sets.clear();
    this.costs.clear();
    this.flushDisposals();
    for (const id of [...this.waiters.keys()]) this.resolve(id);
  }
}
