/**
 * Mutable state shared by the DOM layer and the render loop. Read every frame, so it is a plain
 * object rather than React state (React re-renders only when something visible changes).
 */
import { createFreeLook, isTurning, startRecenter, type FreeLookState } from "@/lib/sect/free-look";
import { gpuView, type GpuView } from "@/lib/sect/gpu-queue";
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
  /**
   * A flight on the glide's curve (lib/sect/snap.ts glideAt): the camera's speed when it began
   * (units per second), which it carries on. A snap glide has it, and so has a key's step begun
   * while the camera moved (planCarry). Without it the flight eases in and out from rest (keys
   * pressed at rest, links).
   */
  v0?: number;
}

/**
 * What the canvas says about the frame it has just rendered, for fast travel's settled wait
 * (lib/sect/settle.ts): how many frames it has rendered, what the renderer holds, and what on
 * screen is still filling in.
 */
export interface CanvasReport {
  frames: number;
  /** gl.info after the frame: geometries and textures on the GPU, programs compiled. */
  geometries: number;
  textures: number;
  programs: number;
  /** A drawn area's grass is still being built, or grass on screen is still growing in. */
  grass: boolean;
  /** The Heart-Mirror's cube map is being captured, or is still fading in. */
  reflection: boolean;
  /** The hold focus is still coming in at the stop. */
  focus: boolean;
  /**
   * Live light is still coming in at the stop (live.tsx, live.ts liveComing): a late piece, which
   * holds the ink only a little past settled (LIVE_LOOK.handover.inkWaitMs).
   */
  live: boolean;
  /**
   * Of `live`, the part where it waits only for files still downloading (live.ts liveArriving): the
   * loading screen's wait lets go of it then.
   */
  liveArriving: boolean;
  /**
   * The GPU has work queued or under way (gpu-queue.ts: an upload, or a shader program still
   * linking). The loading screen holds "Enter" back for it at the first stop.
   */
  gpu: boolean;
}

export interface SectStore {
  map: ScrollMap;
  camera: CameraData;
  /** Scroll position in scroll units (from the page scroll). */
  targetU: number;
  /** Scroll position the camera actually shows (damped, or eased during a flight). */
  u: number;
  /**
   * How fast `u` moves (units per second, signed), set by the camera rig every frame: a snap glide
   * starts at it, and the visitor taking over from a glide carries it on (lib/sect/snap.ts).
   */
  speed: number;
  /** Snap glides started so far (the development readout, window.__sectScroll, counts them). */
  glides: number;
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
  /**
   * Fast travel's ink covers the whole view (ink-travel.tsx): what would grow or fade in at the place
   * it lands on (grass, the hold focus, the mirror's reflection, a phone's turn) is there at once.
   */
  inked: boolean;
  /**
   * The loading screen covers the scene (until "Enter"): nothing of it shows, so the GPU queue may
   * run flat out (sceneView).
   */
  veiled: boolean;
  /** The canvas's report on its last rendered frame (CanvasReport). */
  report: CanvasReport;
  /**
   * Fast travel asks for one frame drawn with nothing in the drawn areas culled (scene.tsx
   * UncullOnce): every mesh there reaches the GPU behind the ink, so a look round once it has
   * cleared uploads nothing. The canvas clears it once done.
   */
  uncull: boolean;
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
  /**
   * The pointer moved over the canvas: the hover pick and the card that follows the cursor want
   * frames, but the picture itself barely changes (a slow glow), so they render at the idle rate,
   * not every display frame. wakeUntil keeps its meaning: a full-rate wake.
   */
  hoverWakeUntil: number;
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
    speed: 0,
    glides: 0,
    frame: frameOverride ?? camera.startFrame,
    frameOverride,
    flight: null,
    gatherFrame: null,
    reducedMotion,
    paused: false,
    modal: false,
    inked: false,
    veiled: true,
    report: { frames: 0, geometries: 0, textures: 0, programs: 0, grass: false, reflection: false, focus: false, live: false, liveArriving: false, gpu: false },
    uncull: false,
    hovered: null,
    focused: null,
    selected: null,
    wakeUntil: 0,
    hoverWakeUntil: 0,
    qualityLabel: "",
    look: createFreeLook(),
  };
}

/** Render continuously for the next `ms` milliseconds (the picture is about to change). */
export function wake(store: SectStore, ms = 400): void {
  store.wakeUntil = Math.max(store.wakeUntil, performance.now() + ms);
}

/** The pointer moved: render at the idle rate (not every display frame) for the next `ms` milliseconds. */
export function wakeHover(store: SectStore, ms = 200): void {
  store.hoverWakeUntil = Math.max(store.hoverWakeUntil, performance.now() + ms);
}

/** How long a hotspot gaining or losing the pointer renders at the full rate, for its glow's fade (ms). */
export const HOVER_BURST_MS = 300;

/** Which hotspots glow (hovered, focused, selected): a change of it starts a short full-rate burst. */
export function glowKey(s: Pick<SectStore, "hovered" | "focused" | "selected">): string {
  return `${s.hovered ?? ""}|${s.focused ?? ""}|${s.selected ?? ""}`;
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
 * What the visitor can see of the scene, for the GPU queue's pace (lib/sect/gpu-queue.ts gpuView):
 * covered by the loading screen or fast travel's ink, the camera moving or the view turning, or at
 * rest.
 */
export function sceneView(store: Pick<SectStore, "veiled" | "inked" | "flight" | "targetU" | "u" | "reducedMotion" | "map" | "look">): GpuView {
  return gpuView({ veiled: store.veiled || store.inked, moving: !cameraStill(store) });
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
