/**
 * How the voice agent (a senior disciple of the sect, in voice or text chat) takes the visitor to a
 * place: by the map's fast travel, never a fly-through. Ink blooms from the talisman the visitor
 * speaks through, covers the screen, the camera is put at the place underneath and the ink clears
 * only once the place has settled (app/sect/experience/ink-travel.tsx, lib/sect/settle.ts). A
 * reader the agent asked for opens after that. With reduced motion the ink is a plain fade over the
 * same wait.
 *
 * Scroll, the rail, the keys and links keep their own ways of moving (goTo / jumpTo in
 * sect-experience.tsx).
 *
 * Pure: the page passes in what it knows.
 */

export type AgentRoute =
  /** Fast travel's ink is already up: this command waits until it has cleared, then runs. */
  | "queue"
  /** The camera is already at the place: open what was asked for at once. */
  | "here"
  /** Go there under the ink. */
  | "ink"
  /** No ink to travel under (?ui=0 captures, or a stop that is not one of the eleven places): the old flight. */
  | "fly";

export interface AgentRouteInput {
  /** Fast travel's ink is up (the visitor's own map travel, or the agent's previous one). */
  inkUp: boolean;
  /** The camera holds at the place now (and is not flying). */
  atPlace: boolean;
  /** The page draws its overlays (not ?ui=0), so the ink can show. */
  overlay: boolean;
  /** The target is one of the eleven places (an area id). */
  isArea: boolean;
}

export function agentRoute(s: AgentRouteInput): AgentRoute {
  if (s.inkUp) return "queue";
  if (s.atPlace) return "here";
  if (s.overlay && s.isArea) return "ink";
  return "fly";
}

/** A box on screen (a DOMRect's fields). */
export interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

/**
 * Where the agent's ink starts: the middle of the talisman (the head of its open panel, else its
 * button in the corner), kept on screen. Without one on screen (null, or a box with no size): the
 * bottom-right corner, where the talisman lives.
 */
export function talismanInkOrigin(box: Box | null, view: { w: number; h: number }): [number, number] {
  const clamp = (v: number, hi: number) => Math.min(hi, Math.max(0, v));
  if (box && box.width > 0 && box.height > 0) {
    return [clamp(box.left + box.width / 2, view.w), clamp(box.top + box.height / 2, view.h)];
  }
  return [clamp(view.w - 60, view.w), clamp(view.h - 60, view.h)];
}
