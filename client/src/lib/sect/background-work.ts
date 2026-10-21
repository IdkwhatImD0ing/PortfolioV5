/**
 * When /sect may do heavy main-thread work that is not drawing: building the picking BVHs
 * (bounding volume hierarchies, the trees that make a pointer ray test cheap) and uploading big
 * textures. Each blocks the frame it lands in (a 150k-triangle BVH takes tens of milliseconds, a
 * 4096 px atlas 6-30 ms), so both wait for the camera, without starving what the visitor is about
 * to see.
 *
 * Where workers run, the BVHs are built off the main thread (experience/bvh.worker.ts); the rules
 * here for building them on it are the fallback.
 *
 * Pure: plain numbers in, decisions out (the canvas supplies the clock and the camera state).
 */

/**
 * The camera must have been still this long before a BVH build starts: the pause between two
 * wheel bursts is not a rest, and a build that starts there lands in the next burst's first frames.
 */
export const BVH_REST_MS = 400;

/** First guess of a BVH build's cost, in ms per 1000 triangles (measured builds refine it). */
export const BVH_MS_PER_KTRI = 0.4;

/** Estimated milliseconds to build a BVH over `tris` triangles. */
export function bvhCostMs(tris: number, msPerKTri: number = BVH_MS_PER_KTRI): number {
  return (Math.max(tris, 0) / 1000) * msPerKTri;
}

/**
 * The cost estimate after a build of `tris` triangles took `ms`: a running average that leans
 * toward the latest build. Small builds are mostly overhead and say little, so they are ignored.
 */
export function updateBvhRate(msPerKTri: number, ms: number, tris: number): number {
  if (tris < 2000 || !(ms >= 0)) return msPerKTri;
  return msPerKTri * 0.7 + (ms / (tris / 1000)) * 0.3;
}

/**
 * On a touch screen a hotspot mesh bigger than this gets no idle BVH. With no hover, a pick only
 * happens on a tap, and until a mesh has its BVH the tap falls back to the hotspot's box (scene.tsx
 * Hotspots, lib/sect/pick.ts pickWithBoxes), which is enough for a finger. The builds it saves are
 * the ones that froze a phone at rest: the library pagoda (426k triangles) for up to 1.46 s, the
 * gate (347k) and the mission (264k) for most of a second.
 */
export const BVH_TOUCH_MAX_TRIS = 100_000;

/** Should a mesh of `tris` triangles get an idle BVH at all? Always with a mouse (hover picks). */
export function bvhWanted(tris: number, touch: boolean): boolean {
  return !touch || tris <= BVH_TOUCH_MAX_TRIS;
}

/**
 * With the BVH worker (experience/bvh-build.ts), the main thread only copies a mesh's position and
 * index arrays out and takes the tree back (a few ms for the biggest hotspot), so a job may be sent
 * once the camera has been still this long: enough to skip the gap between two wheel notches.
 */
export const BVH_POST_REST_MS = 150;

/** May the next BVH job go to the worker now? Once the page is ready and the camera is still. */
export function mayPostBvh(s: { pageReady: boolean; stillForMs: number }): boolean {
  return s.pageReady && s.stillForMs >= BVH_POST_REST_MS;
}

/** The typed arrays a glTF position attribute may be stored in (meshopt quantises to integers). */
export type PositionArray = Float32Array | Int32Array | Uint32Array | Int16Array | Uint16Array | Int8Array | Uint8Array | Uint8ClampedArray;

/** A position attribute's raw storage, as experience/bvh-build.ts copies it out for the worker. */
export interface RawPositions {
  position: PositionArray;
  /** Vertices. */
  count: number;
  /** Elements from one vertex to the next in `position` (interleaved: the buffer's stride). */
  stride: number;
  /** Element where the first vertex starts. */
  offset: number;
  /** Integers read as -1..1 or 0..1 (three's BufferAttribute.normalized). */
  normalized: boolean;
}

/**
 * The divisor three's BufferAttribute uses to read a normalised integer (MathUtils.denormalize),
 * by the array's type, and whether the result is clamped at -1 (signed types).
 */
function normScale(a: RawPositions["position"]): { div: number; signed: boolean } {
  if (a instanceof Int16Array) return { div: 32767, signed: true };
  if (a instanceof Uint16Array) return { div: 65535, signed: false };
  if (a instanceof Int8Array) return { div: 127, signed: true };
  if (a instanceof Uint8Array || a instanceof Uint8ClampedArray) return { div: 255, signed: false };
  if (a instanceof Int32Array) return { div: 2147483647, signed: true };
  if (a instanceof Uint32Array) return { div: 4294967295, signed: false };
  return { div: 1, signed: false };
}

/**
 * Plain xyz floats from a position attribute's raw storage, exactly as three's getX/getY/getZ read
 * them: meshopt's quantised files store positions as normalised 16-bit integers, sometimes
 * interleaved with other attributes. three-mesh-bvh's own worker takes the array as unnormalised
 * floats, which put a quantised mesh's boxes at the wrong scale; the BVH worker reads it with this.
 */
export function bvhPositions(raw: RawPositions): Float32Array {
  const { position: src, count, stride, offset } = raw;
  const out = new Float32Array(count * 3);
  const { div, signed } = raw.normalized ? normScale(src) : { div: 1, signed: false };
  for (let i = 0; i < count; i++) {
    const at = i * stride + offset;
    for (let k = 0; k < 3; k++) {
      const v = src[at + k];
      out[i * 3 + k] = div === 1 ? v : signed ? Math.max(v / div, -1) : v / div;
    }
  }
  return out;
}

export interface BvhSlice {
  /**
   * The page is ready (the loading screen has gone). The camera counts as still while it loads, and
   * a build then delayed the first picture (609 ms on a phone).
   */
  pageReady: boolean;
  /** How long the camera has been still (0 while it moves). */
  stillForMs: number;
  /** Builds already run in this idle callback. */
  builtThisSlice: number;
  /** Estimated cost of the next build (bvhCostMs). */
  costMs: number;
  /** What the browser says is left of this idle period (IdleDeadline.timeRemaining()). */
  timeRemainingMs: number;
}

/**
 * May the next queued BVH build run now? Never before the page is ready, nor until the camera has
 * been still for BVH_REST_MS. Then the first build of an idle callback always runs: while the render
 * loop asks for every display frame an idle period lasts a few milliseconds at most, so a large
 * build would otherwise never fit, and at rest a long task only delays the slow idle redraw. Further
 * builds in the same callback run only while their estimated cost fits in the time the browser says
 * is left.
 */
export function mayBuildBvh(s: BvhSlice): boolean {
  if (!s.pageReady || s.stillForMs < BVH_REST_MS) return false;
  if (s.builtThisSlice === 0) return true;
  return s.costMs <= s.timeRemainingMs;
}

/**
 * Camera travel (frames still to fly before it catches up with the scroll position) above which a
 * texture upload waits. The camera eases toward the scroll position at about 5 times this gap per
 * second, so 6 frames is about 30 frames of flight per second: a single wheel notch stays under
 * it, continuous scrolling goes over it.
 */
export const UPLOAD_FAST_FRAMES = 6;

/**
 * Longest an area's uploads wait for the camera to slow down once the area is wanted on screen (the
 * backdrop's proxy is showing in its place): one budget for the whole area, counted from when it was
 * first wanted (uploadWaitedMs), not one per texture (the abode's five textures could wait 2.5 s).
 * Past it, the rest go a texture per frame, so an area scrolled through without pause still arrives.
 */
export const UPLOAD_MAX_WAIT_MS = 500;

/** How long an area's uploads have waited: since it was first wanted on screen (`wantedSince`, or null: not yet). */
export function uploadWaitedMs(wantedSince: number | null, now: number): number {
  return wantedSince === null ? 0 : Math.max(0, now - wantedSince);
}

export interface UploadState {
  /** A programmatic jump is under way. */
  flight: boolean;
  /** Frames the camera still has to fly to reach the scroll position. */
  framesToGo: number;
  /**
   * The view is turning (a drag, a held arrow key, or the swing back to the path). A chunk that
   * loads because the visitor looked back would otherwise land its uploads mid-turn.
   */
  turning?: boolean;
  /** The set would be drawn at the camera's frame if it were ready (its need range holds it). */
  inView: boolean;
  /** How long the set's uploads have waited since it was first wanted on screen (uploadWaitedMs). */
  waitedMs: number;
}

/**
 * Should the next texture upload wait a frame? During a jump, yes (as before: the jump's
 * destination is gathered before it starts). While the camera moves fast or the view turns, yes,
 * unless its area is already wanted on screen and has waited UPLOAD_MAX_WAIT_MS (a visitor who keeps
 * turning still gets the area, a texture at a time). Otherwise it goes.
 */
export function deferUpload(s: UploadState): boolean {
  if (s.flight) return true;
  if (s.framesToGo <= UPLOAD_FAST_FRAMES && !s.turning) return false;
  return !(s.inView && s.waitedMs >= UPLOAD_MAX_WAIT_MS);
}
