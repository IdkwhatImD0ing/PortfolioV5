/**
 * The page's queue of GPU jobs (app/sect/experience/gpu-queue.ts): texture uploads from the sets'
 * warm-up (scene.tsx World), live light's maps (live.tsx) and the rest go through one queue. Its pace
 * follows what the visitor can see (GpuView, GPU_PACE): while the camera moves at most one step runs
 * in a display frame, and never while the GPU is still working through the last one or a shader
 * program is linking (both block the upload's copy in the browser's GPU process, and the page waits
 * for it); with the camera at rest a few milliseconds of steps a frame; behind the loading screen or
 * fast travel's ink most of the frame. A large texture goes up in bands of rows, one band a step, from the
 * same decoded image: WebGL 2 uploads a sub-rectangle of an image (UNPACK_SKIP_ROWS), and the texels
 * are the same as one upload's. A 4096 px map in one call held the frame 15 to 59 ms; a band of 512
 * rows takes about 2 ms.
 *
 * Pure: plain inputs, no timers, no three.js.
 */

export const GPU_QUEUE = {
  /** Bytes one band of an upload carries: 512 rows of a 4096 px RGBA map (about 2 ms on a desktop). */
  bandBytes: 8 * 1024 * 1024,
  /**
   * How long the GPU's fence or a linking program may hold the queue before it goes on anyway (ms):
   * a link can take a second on a first visit, and the queue must not starve behind a stream of them.
   */
  maxHoldMs: 1500,
} as const;

/** Rows `y` to `y + rows` of an image. */
export interface UploadBand {
  y: number;
  rows: number;
}

/**
 * The bands an upload of a `width` x `height` image goes up in, top to bottom: as many whole rows
 * as fit in `bandBytes` (at least one), the last band whatever is left. None for an empty image.
 */
export function uploadBands(width: number, height: number, bytesPerTexel = 4, bandBytes: number = GPU_QUEUE.bandBytes): UploadBand[] {
  if (!(width > 0) || !(height > 0)) return [];
  const rows = Math.max(1, Math.floor(bandBytes / (width * bytesPerTexel)));
  const out: UploadBand[] = [];
  for (let y = 0; y < height; y += rows) out.push({ y, rows: Math.min(rows, height - y) });
  return out;
}

/**
 * Whether a map whose mipmaps the GPU makes can go up in bands and come out the same as one upload:
 * both sides a power of two. With an odd side somewhere down its chain (2048 x 1760 has 55 rows at
 * level 5) the driver made different mipmaps once level 0 had gone up in parts (checked on this PC:
 * a 2048 x 1760 map's levels from 6 down differed, every level of 2048 and 4096 squares matched),
 * and a far tree showed it. Such a map goes up whole, as three does it.
 */
export function bandsKeepMipmaps(width: number, height: number): boolean {
  const pow2 = (n: number) => Number.isInteger(n) && n > 0 && (n & (n - 1)) === 0;
  return pow2(width) && pow2(height);
}

/**
 * What the visitor can see of the scene, which sets how hard the queue pushes (GPU_PACE):
 * - "moving": the camera flies, glides, catches up with the scroll, or the view turns. A long frame
 *   shows as a hitch, so one small step a frame, and none while the GPU is busy or a program links.
 * - "resting": the camera is still at a place. A hitch shows far less than a place still made of
 *   its stand-ins, so a larger share of each frame, and a linking program does not hold the queue
 *   (the GPU's fence still does: the next frame's steps wait for it).
 * - "veiled": nothing of the scene shows (the loading screen, fast travel's ink): flat out.
 */
export type GpuView = "moving" | "resting" | "veiled";

/** How the queue paces itself for one view (GPU_PACE). */
export interface GpuPace {
  /** Milliseconds of steps one display frame may run (a step that starts under it runs whole); 0: one step a frame. */
  budgetMs: number;
  /** Wait while the GPU is still working through the steps of an earlier frame (the fence). */
  holdForFence: boolean;
  /** Wait while a shader program links (its link and an upload's copy contend in the GPU process). */
  holdForLinks: boolean;
}

export const GPU_PACE: Readonly<Record<GpuView, GpuPace>> = {
  moving: { budgetMs: 0, holdForFence: true, holdForLinks: true },
  // About 7 ms of a 16.7 ms frame: at rest the canvas draws at the idle rate, so the frame has room.
  resting: { budgetMs: 7, holdForFence: true, holdForLinks: false },
  // Most of the frame; the loading screen and the ink still get their frames, at about 30 a second.
  veiled: { budgetMs: 14, holdForFence: false, holdForLinks: false },
};

/**
 * Main-thread time one slice of a set's preparation may take (experience/prepare.ts
 * prepareSceneSliced, idle.ts planIdleSliced) before a frame is let through, by the same view: 5 ms
 * while the scene shows (a 4x-slowed phone keeps its 30 frames a second, at rest too: the water, the
 * clouds and a tap go on), most of a frame behind the loading screen or the ink, where only the
 * screen's own bar moves.
 */
export const PREPARE_SLICE: Readonly<Record<GpuView, number>> = { moving: 5, resting: 5, veiled: 24 };

/**
 * The same for the slices of an area's grass build (experience/grass.tsx): 6 ms while the scene shows,
 * as before; behind the loading screen or the ink, which wait for the grass, as much as a prepare's.
 */
export const GRASS_SLICE: Readonly<Record<GpuView, number>> = { moving: 6, resting: 6, veiled: PREPARE_SLICE.veiled };

/**
 * Jobs at or above this priority are work the visitor waits to see: a set wanted where the camera
 * is or is heading (its stand-in shows meanwhile; setUploadPriority), live light's start at the stop.
 */
export const URGENT_PRIORITY = 2;

/**
 * The pace for a job of `priority` while the visitor sees `view`. At rest the larger share is only
 * for work the visitor waits to see (URGENT_PRIORITY): an area loaded ahead, or live light's maps for
 * the next stop, goes up a step a frame as while moving, so a camera resting at a place that is all
 * there does not hitch for what is not on screen.
 */
export function gpuPaceFor(view: GpuView, priority: number): GpuPace {
  if (view === "resting" && !(priority >= URGENT_PRIORITY)) return GPU_PACE.moving;
  return GPU_PACE[view];
}

/** What the store knows of the view (gpuView). */
export interface GpuViewInput {
  /** The loading screen or fast travel's ink covers the scene, or the scene is not drawn at all. */
  veiled: boolean;
  /** The camera is moving (a flight, a glide, catching up with the scroll) or the view is turning. */
  moving: boolean;
}

/** The view the queue paces itself for (see GpuView): covered wins, then moving, else at rest. */
export function gpuView(s: GpuViewInput): GpuView {
  if (s.veiled) return "veiled";
  return s.moving ? "moving" : "resting";
}

/** What the queue knows at a display frame. */
export interface GpuGate {
  /** Steps already run in this display frame, and the milliseconds they took. */
  stepsThisFrame: number;
  spentMs: number;
  /** The fence placed after the last frame's steps has not passed: the GPU is still working through them. */
  fencePending: boolean;
  /** A shader program is still linking. */
  linking: boolean;
  /** How long the fence or the linking has held the queue so far (ms). */
  heldMs: number;
}

/**
 * Whether the queue may run its next step now, at `pace` (default: as while the camera moves, one a
 * frame): the frame's first step, or another while the steps so far are under the pace's budget; and
 * not while the GPU is busy with an earlier frame's steps or a program links, where the pace holds
 * for those, unless that has held it `maxHoldMs` already.
 */
export function mayRunGpuStep(g: GpuGate, pace: GpuPace = GPU_PACE.moving, maxHoldMs: number = GPU_QUEUE.maxHoldMs): boolean {
  if (g.stepsThisFrame > 0 && !(g.spentMs < pace.budgetMs)) return false;
  const held = (pace.holdForFence && g.fencePending) || (pace.holdForLinks && g.linking);
  return !held || g.heldMs >= maxHoldMs;
}

/**
 * The queue priority of a set's uploads (scene.tsx World): the global set first (the opening
 * picture), then a set wanted where the camera is heading (the end of a flight or glide, else where
 * it is), then one on screen now that the camera is leaving, then one loaded ahead. Live light's
 * start at a stop has 2 (live.tsx), so a place's own models go before its light.
 */
export function setUploadPriority(s: { global: boolean; headed: boolean; inView: boolean }): number {
  if (s.global) return 4;
  if (s.headed) return 3;
  return s.inView ? 2 : 1;
}

/** A queued job as the queue orders it. */
export interface GpuJobInfo {
  /** Higher goes first (what is on screen, or about to be, before what is loaded ahead). */
  priority: number;
  /** Order added: among equal priorities the older goes first, so a started upload finishes first. */
  seq: number;
  /** The job waits for now (an upload kept out of a fast flight); the others may go meanwhile. */
  waiting: boolean;
}

/** Which job runs the next step: the highest priority, then the oldest, of those not waiting; -1 when none may. */
export function pickGpuJob(jobs: readonly GpuJobInfo[]): number {
  let best = -1;
  for (let i = 0; i < jobs.length; i++) {
    const j = jobs[i];
    if (j.waiting) continue;
    if (best < 0) {
      best = i;
      continue;
    }
    const b = jobs[best];
    if (j.priority > b.priority || (j.priority === b.priority && j.seq < b.seq)) best = i;
  }
  return best;
}
