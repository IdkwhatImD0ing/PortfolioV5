/**
 * Fast travel's settled wait (app/sect/experience/sect-experience.tsx, under the ink of
 * ink-travel.tsx): the ink clears only once the place it lands on is fully drawn and nothing in the
 * view is still arriving. Before, it cleared as soon as the place's own area was on the GPU, and the
 * visitor then watched the rest assemble: the neighbouring areas the stop's view draws swapping from
 * the backdrop's stand-ins to their full meshes, grass growing in, the Heart-Mirror's reflection
 * capturing and fading in, the hold focus coming in, and the frames that upload or compile all that
 * stalling.
 *
 * Settled means:
 * - every chunk the camera resting there draws (destinationChunks) is ready to draw (or failed: its
 *   stand-in stays for good), and none drawn there now is about to go;
 * - nothing on screen is still filling in (the page names those pieces: grass, reflection, focus,
 *   detail);
 * - then the renderer's resident counts (geometries, textures, programs) and the view itself hold
 *   still for SETTLE.stableFrames rendered frames and SETTLE.stableMs: an upload, a compile, a swap
 *   or a turn starts that count again.
 *
 * "Every chunk the camera draws there" means the place's own area and its direct neighbours in
 * flight order (SETTLE.around): the stream keeps two areas each side at full detail on desktops, and
 * waiting for all five would double the wait after a far jump. The two further out stream in once
 * the ink has cleared; their stand-ins sit far back in the view, where the swap hardly shows.
 *
 * Pure: plain inputs, no timers, no three.js.
 */
import { gapToRange, planChunks, windowCentreAt, type PlanInput } from "./chunks";

export const SETTLE = {
  /** Rendered frames, and milliseconds, the renderer's counts and the view must hold still. */
  stableFrames: 8,
  stableMs: 400,
  /** A chunk's share of its progress that is the download (the rest: preparing it and its upload). */
  download: 0.8,
  /** Prepared and on its way to the GPU (its textures uploading, its shaders compiling). */
  uploading: 0.9,
  /** Shares of the shown progress: the chunks, the pieces filling in, and the frames holding still. */
  share: { chunks: 0.8, pieces: 0.1, still: 0.1 },
  /**
   * Areas each side of the place's own, in flight order, the wait covers (destinationChunks
   * `around`): its view is mostly made of those. Areas further out the stream keeps come in after.
   */
  around: 1,
} as const;

/**
 * The chunks a camera resting at `input.frame` draws once streaming there has run its course: those
 * the plan at rest (planChunks with no jump target, nobody looking back) needs, keeps (resident, or
 * still loading and not cancelled: a prefetch under way) or loads whose need range holds the frame,
 * and its prefetch too when the budget fetches ahead at rest (`fetchAhead`: a prefetch whose need
 * range holds the frame is drawn there once it arrives). Handover chunks are not among them: they
 * stay only until the others are ready. `around`: only areas at most that many places from the
 * frame's own (lib/sect/chunks.ts windowCentreAt) in flight order are wanted (the others the plan
 * keeps stream in after; absent: all).
 * `leaving`: the resident chunks ready and drawn at the frame now that the plan does not keep (they
 * go, and the backdrop's stand-ins show in their place).
 */
export function destinationChunks(
  input: Omit<PlanInput, "target" | "lookingBack">,
  fetchAhead: boolean,
  around = Infinity,
): { want: string[]; leaving: string[] } {
  const plan = planChunks({ ...input, target: null, lookingBack: false });
  const margin = input.window?.drawMargin ?? 0;
  const byId = new Map(input.chunks.map((c) => [c.id, c]));
  const holds = (id: string) => {
    const c = byId.get(id);
    return c !== undefined && gapToRange(input.frame, c.need) <= margin;
  };
  const order = new Map(input.chunks.map((c, i) => [c.id, i]));
  const here = windowCentreAt(input.chunks, input.frame);
  const near = (id: string) => Math.abs((order.get(id) ?? Infinity) - here) <= around;
  const handover = new Set(plan.handover);
  const cancel = new Set(plan.cancel);
  const kept = [...input.loading].filter((id) => !cancel.has(id));
  // Everything drawn there once streaming has run its course, and of that what the wait covers.
  const drawn = new Set<string>();
  for (const id of [...plan.need, ...plan.keep, ...kept, ...(fetchAhead && plan.prefetch ? [plan.prefetch] : [])]) {
    if (!handover.has(id) && holds(id)) drawn.add(id);
  }
  const want = [...drawn].filter(near);
  const sorted = (ids: Iterable<string>) => [...ids].sort((a, b) => (order.get(a) ?? 0) - (order.get(b) ?? 0));
  const ready = input.ready ?? input.resident;
  const leaving = [...input.resident].filter((id) => ready.has(id) && holds(id) && !drawn.has(id));
  return { want: sorted(want), leaving: sorted(leaving) };
}

/** Where a chunk is on its way to being drawn (ChunkStreamer.settleAt). */
export interface ChunkState {
  /** Ready to draw, or given up on (failed: nothing to wait for). */
  done: boolean;
  /** Loaded and prepared, its textures and shaders on their way to the GPU. */
  resident: boolean;
  /** Bytes downloaded so far, and the chunk's whole download (0: unknown). */
  received: number;
  total: number;
}

/** How far a chunk has come toward being drawn, 0..1: mostly its download, then its preparing and upload. */
export function chunkDone(s: ChunkState, c = SETTLE): number {
  if (s.done) return 1;
  if (s.resident) return c.uploading;
  if (s.total <= 0) return 0;
  return c.download * Math.min(1, Math.max(0, s.received / s.total));
}

/** One look at the destination (taken each display frame while the ink is up). */
export interface SettleSnapshot {
  /** performance.now() (ms). */
  now: number;
  /** Frames the canvas has rendered so far. */
  frames: number;
  /**
   * The destination's chunks: how far each has come (chunkDone) and its weight (its download size).
   * `expected`: not wanted yet, but the plan will want it once the others are in (the prefetch
   * ahead): it counts toward the progress shown, never toward settling (it may not come after all).
   */
  chunks: readonly { id: string; done: number; weight: number; expected?: boolean }[];
  /** Chunks drawn there now that are about to go (destinationChunks `leaving`). */
  leaving: number;
  /** Pieces on screen still filling in (grass growing, a reflection capturing, ...), by name. */
  busy: readonly string[];
  /** The renderer's resident counts at the last rendered frame (geometries, textures, programs). */
  gpu: string;
  /** Where the view is (the frame and the look): a turn or a move starts the still count again. */
  view: string;
}

export interface SettleState {
  settled: boolean;
  /** 0..1 for the ink's card; never goes back (a chunk added late only slows it). */
  progress: number;
  /** What it still waits for: chunk ids, busy pieces, "leaving", or "still" (the frames holding). */
  waiting: string[];
}

/**
 * Follows the destination snapshot by snapshot and says when it has settled. A new one per travel.
 */
export class SettleWatch {
  private key = "";
  private pieces = false;
  private fromFrames = 0;
  private fromNow = 0;
  private shown = 0;

  constructor(private readonly c = SETTLE) {}

  push(s: SettleSnapshot): SettleState {
    const waiting: string[] = [];
    let weight = 0;
    let done = 0;
    let expecting = false;
    for (const ch of s.chunks) {
      const w = Math.max(ch.weight, 1);
      const k = Math.min(1, Math.max(0, ch.done));
      weight += w;
      done += w * k;
      if (k >= 1) continue;
      if (ch.expected) expecting = true;
      else waiting.push(ch.id);
    }
    if (s.leaving > 0) waiting.push("leaving");
    waiting.push(...s.busy);
    const pieces = waiting.length === 0;
    // The still count starts from the first snapshot with every piece in, and over again whenever
    // the counts or the view change.
    const key = `${s.gpu}|${s.view}`;
    if (!pieces || !this.pieces || key !== this.key) {
      this.key = key;
      this.fromFrames = s.frames;
      this.fromNow = s.now;
    }
    this.pieces = pieces;
    const frames = s.frames - this.fromFrames;
    const settled = pieces && frames >= this.c.stableFrames && s.now - this.fromNow >= this.c.stableMs;
    if (pieces && !settled) waiting.push("still");
    const { share } = this.c;
    const still = pieces && !expecting ? Math.min(1, frames / this.c.stableFrames, (s.now - this.fromNow) / this.c.stableMs) : 0;
    const raw = (weight > 0 ? done / weight : 1) * share.chunks + (pieces && !expecting ? share.pieces : 0) + still * share.still;
    this.shown = settled ? 1 : Math.max(this.shown, Math.min(0.99, raw));
    return { settled, progress: this.shown, waiting };
  }
}
