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
 *   or a turn starts that count again;
 * - and then any late piece the page names (live light coming in at the place) is done, or a short
 *   while has passed (SettleSnapshot.lateMs): a late piece never holds the ink longer than that.
 *
 * "Every chunk the camera draws there" means the place's own area and its direct neighbours in
 * flight order (SETTLE.around): the stream keeps two areas each side at full detail on desktops, and
 * waiting for all five would double the wait after a far jump. The two further out stream in once
 * the ink has cleared; their stand-ins sit far back in the view, where the swap hardly shows.
 *
 * The loading screen's wait for the first stop (SETTLE_GATE) is the same watch, with one difference:
 * a piece whose bytes are still on the way (an area still downloading or not started, the detail
 * texture or live light's maps still downloading: SettleSnapshot.arriving) holds it only briefly
 * (SettleConfig.arrivingMs). It waits for work on what has arrived, not for the line.
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
  /**
   * Fast travel's ink waits for every piece, a download still under way too (SettleConfig.arrivingMs):
   * the visitor asked to see that place, and the ink hides it until it is all there.
   */
  arrivingMs: Infinity,
} as const;

/** What a SettleWatch counts by (SETTLE, SETTLE_GATE). */
export interface SettleConfig {
  stableFrames: number;
  stableMs: number;
  share: { chunks: number; pieces: number; still: number };
  /**
   * How long a piece whose bytes are still on the way (SettleSnapshot.arriving) may hold the wait,
   * from the first snapshot that showed it so (ms). Infinity: as long as it takes (fast travel's ink
   * waits for its downloads).
   */
  arrivingMs: number;
}

/**
 * The loading screen's wait for the first stop: as fast travel's, with a shorter still, and a
 * download still under way does not hold it.
 *
 * The still: that wait also waits for the GPU's queue to be empty and every program linked (the
 * page names that piece: "gpu"), which is most of what the still stood for, and its first still is
 * always counted twice (the frame drawn with nothing culled uploads the areas' meshes and starts it
 * again): at 400 ms each they held "Enter" back about 0.8 s with nothing left to do. A swap, an
 * upload or a compile still shows in the counts within a frame or two.
 *
 * Downloads: the wait is there to spend the work on what has arrived (preparing it, its uploads and
 * links, the grass, live light starting) behind the loading screen rather than on the first frames
 * after Enter. A file still arriving is not such work: on a real line the first stop's neighbours
 * and its live maps took longer than the wait's 6 s cap at 50 megabits a second, so Enter always
 * came 6 s after the first picture, for nothing. An area or a map whose bytes are all here is local
 * work and still holds it (under the cap). One still downloading holds it only for `arrivingMs`
 * from when the wait first saw it so: on localhost every area the first view draws arrived within
 * 0.3 s of the first picture (and the next one starts up to 150 ms after it, at the stream's next
 * update), so there it is waited for as before; on a real line it lets go, and what arrives after
 * Enter goes up at the queue's resting or moving pace, as at every later stop.
 */
export const SETTLE_GATE: SettleConfig = { stableFrames: SETTLE.stableFrames, stableMs: 150, share: SETTLE.share, arrivingMs: 500 };

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
  /** Every one of its files has all its bytes here (parsing and preparing may still run). */
  fetched?: boolean;
}

/**
 * The chunk's bytes are still on the way (SettleSnapshot.arriving): not drawn yet, not loaded and
 * prepared, and some file of it still downloading, or its load not started. One whose files are all
 * here is work on what has arrived, however far its preparing has come.
 */
export function chunkArriving(s: Pick<ChunkState, "done" | "resident" | "fetched">): boolean {
  return !s.done && !s.resident && !s.fetched;
}

/**
 * Where the tiling detail texture is (experience/assets.ts detailState): not on its way (none yet,
 * in, or failed), its file still downloading, being decoded, or fading in over the rock.
 */
export type DetailState = "none" | "arriving" | "decoding" | "fading";

/**
 * Whether the detail texture holds a settled wait. Fast travel's ink waits until it has faded in:
 * the ink lifts on the final picture. The loading screen's wait (`gate`) waits for its decoding
 * only (its download is a piece still arriving: SettleSnapshot.arriving). The fade is no work (a
 * uniform's ramp; the upload is on the first frame drawn with it), and it held Enter up to a second
 * after the first picture on a line where the file came just before or after it. It ends behind the
 * loading screen, or within the veil's own fade once Enter is pressed.
 */
export function detailHolds(state: DetailState, gate: boolean): boolean {
  if (state === "none") return false;
  return !gate || state !== "fading";
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
  /**
   * Pieces that may hold the ink past settled, but not for long (live light coming in at the place:
   * experience/live.tsx). They hold nothing back until everything else has settled; from then the
   * watch waits while any is busy, at most `lateMs` (absent: 0, no wait).
   */
  late?: readonly string[];
  lateMs?: number;
  /**
   * Of the chunks (by id), the busy pieces and the late pieces (by name), those whose bytes are still
   * on the way: a chunk not loaded yet or still downloading, the detail texture or live light's maps
   * still downloading. Once the watch has seen one so for SettleConfig.arrivingMs it holds nothing
   * (absent: none). A chunk whose files are all here but not yet prepared or uploaded is not among
   * them: that is work on what has arrived.
   */
  arriving?: readonly string[];
}

export interface SettleState {
  settled: boolean;
  /** 0..1 for the ink's card; never goes back (a chunk added late only slows it). */
  progress: number;
  /** What it still waits for: chunk ids, busy pieces, "leaving", or "still" (the frames holding). */
  waiting: string[];
  /** What it no longer waits for: pieces still arriving past SettleConfig.arrivingMs. */
  away: string[];
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
  /** When everything but the late pieces first settled (null: not yet). */
  private lateFrom: number | null = null;
  /** When each piece was first seen still arriving (SettleSnapshot.arriving). */
  private readonly arrivingSince = new Map<string, number>();

  constructor(private readonly c: SettleConfig = SETTLE) {}

  push(s: SettleSnapshot): SettleState {
    // Pieces whose bytes are still on the way, and of those the ones that no longer hold the wait.
    const arriving = new Set(s.arriving ?? []);
    for (const id of arriving) if (!this.arrivingSince.has(id)) this.arrivingSince.set(id, s.now);
    const gone = (id: string) => arriving.has(id) && s.now - (this.arrivingSince.get(id) ?? s.now) >= this.c.arrivingMs;
    const away: string[] = [];
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
      // Expected next, or still downloading past arrivingMs: counted in the progress, never waited for.
      if (ch.expected) expecting = true;
      else if (gone(ch.id)) {
        expecting = true;
        away.push(ch.id);
      } else waiting.push(ch.id);
    }
    if (s.leaving > 0) waiting.push("leaving");
    for (const b of s.busy) {
      if (gone(b)) away.push(b);
      else waiting.push(b);
    }
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
    const calm = pieces && frames >= this.c.stableFrames && s.now - this.fromNow >= this.c.stableMs;
    // Settled but for the late pieces: they may hold it lateMs from the first time it got here.
    if (calm && this.lateFrom === null) this.lateFrom = s.now;
    const late: string[] = [];
    for (const l of s.late ?? []) {
      if (!gone(l)) late.push(l);
      else if (!away.includes(l)) away.push(l);
    }
    const capped = this.lateFrom !== null && s.now - this.lateFrom >= Math.max(s.lateMs ?? 0, 0);
    const settled = capped || (calm && late.length === 0);
    if (!settled) {
      if (pieces && !calm) waiting.push("still");
      if (this.lateFrom !== null) waiting.push(...late);
    }
    const { share } = this.c;
    const still = pieces && !expecting ? Math.min(1, frames / this.c.stableFrames, (s.now - this.fromNow) / this.c.stableMs) : 0;
    const raw = (weight > 0 ? done / weight : 1) * share.chunks + (pieces && !expecting ? share.pieces : 0) + still * share.still;
    this.shown = settled ? 1 : Math.max(this.shown, Math.min(0.99, raw));
    return { settled, progress: this.shown, waiting, away };
  }
}
