/**
 * Mutable state shared by the DOM layer and the render loop. Read every frame, so it is a plain
 * object rather than React state (React re-renders only when something visible changes).
 */
import { createFreeLook, isTurning, startRecenter, type FreeLookState } from "@/lib/sect/free-look";
import { nearestStop, uToFrame, type ScrollMap } from "@/lib/sect/scroll-map";
import type { CameraData } from "@/lib/sect/types";

/** A programmatic jump: the camera eases from one scroll position to another. */
export interface Flight {
  fromU: number;
  toU: number;
  /** performance.now() at the start. */
  t0: number;
  /** Seconds. */
  duration: number;
  /** Destination frame (chunk planning looks there, not along the sweep). */
  toFrame: number;
  /** Called once the camera is there (not when the flight is cancelled). */
  onArrive?: () => void;
}

export interface SectStore {
  map: ScrollMap;
  camera: CameraData;
  /** Scroll position in scroll units (from the page scroll). */
  targetU: number;
  /** Scroll position the camera actually shows (damped, or eased during a flight). */
  u: number;
  /** Blender frame the camera is on. */
  frame: number;
  /** ?frame=N: show this frame until the visitor scrolls (wheel, touch, keys). */
  frameOverride: number | null;
  /** A programmatic jump under way, or null. */
  flight: Flight | null;
  /** Destination frame of a jump waiting for its chunk to load ("gathering"), or null. */
  gatherFrame: number | null;
  reducedMotion: boolean;
  /** The 3D view is covered (the "read as a page" document): render nothing. */
  paused: boolean;
  /** A reader covers most of the view: a pulsing highlight renders at the idle rate. */
  modal: boolean;
  hovered: string | null;
  /** Hotspot focused in the keyboard list or highlighted by the reader. */
  focused: string | null;
  /** Hotspot whose reader is open. */
  selected: string | null;
  /**
   * The canvas renders on demand: every display frame while something moves, at a low idle rate for
   * the water and clouds otherwise. Events that change the picture call wake() to render until then.
   */
  wakeUntil: number;
  /** Quality line for the debug HUD (resolution, MSAA, bloom). */
  qualityLabel: string;
  /**
   * Free look (lib/sect/free-look.ts): the view turned by a drag, on top of the path camera. Only
   * the rendered camera turns; everything that asks where the flight is (holds, panels, streaming)
   * reads the scroll position and the frame, never the camera.
   */
  look: FreeLookState;
}

export function createStore(map: ScrollMap, camera: CameraData, u: number, frameOverride: number | null, reducedMotion: boolean): SectStore {
  return {
    map,
    camera,
    targetU: u,
    u,
    frame: frameOverride ?? camera.startFrame,
    frameOverride,
    flight: null,
    gatherFrame: null,
    reducedMotion,
    paused: false,
    modal: false,
    hovered: null,
    focused: null,
    selected: null,
    wakeUntil: 0,
    qualityLabel: "",
    look: createFreeLook(),
  };
}

/** Render continuously for the next `ms` milliseconds (the picture is about to change). */
export function wake(store: SectStore, ms = 400): void {
  store.wakeUntil = Math.max(store.wakeUntil, performance.now() + ms);
}

/** Render for as long as the swing back to the path under way takes (a moment, after a snap). */
export function wakeForRecenter(store: SectStore): void {
  const r = store.look.recenter;
  wake(store, r ? r.duration * 1000 + 100 : 400);
}

/**
 * Swing the view back to the path's framing, the short way round (Escape, the Recentre button).
 * Returns false when it was not turned.
 */
export function recenterView(store: SectStore): boolean {
  if (!startRecenter(store.look, performance.now() / 1000, store.reducedMotion)) return false;
  wakeForRecenter(store);
  return true;
}

/**
 * Something on screen moves: the render loop runs every display frame. With reduced motion the
 * camera snaps to the stop nearest the scroll position, so it is at rest once it shows that stop
 * (the raw scroll position itself rarely lands exactly on one).
 */
export function isMoving(store: Pick<SectStore, "flight" | "targetU" | "u" | "reducedMotion" | "map">): boolean {
  if (store.flight !== null) return true;
  const target = store.reducedMotion ? nearestStop(store.map, store.targetU).u : store.targetU;
  return Math.abs(target - store.u) > 1e-3;
}

/**
 * The view is still: no scroll, jump, drag, held arrow key or swing back to the path turns or moves
 * the camera. Heavy background work (BVH builds) waits for this, so it never lands in a moving frame.
 */
export function cameraStill(store: Pick<SectStore, "flight" | "targetU" | "u" | "reducedMotion" | "map" | "look">): boolean {
  return !isMoving(store) && !isTurning(store.look);
}

/**
 * Frames the camera still has to fly before it shows the scroll position (0 at rest, during a
 * ?frame= override and with reduced motion, where it snaps). The camera eases toward the scroll
 * position, so this is also how fast it is moving: about 5 times this many frames per second.
 */
export function framesToGo(store: Pick<SectStore, "targetU" | "frame" | "frameOverride" | "reducedMotion" | "map">): number {
  if (store.frameOverride !== null || store.reducedMotion) return 0;
  return Math.abs(uToFrame(store.map, store.targetU) - store.frame);
}
