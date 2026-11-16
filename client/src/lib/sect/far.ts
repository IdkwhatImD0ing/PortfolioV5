/**
 * Far places in full. Where the page holds every area (experience/streaming.ts
 * STREAM_BUDGETS.everything), a loaded area outside its need range is drawn with its own meshes in
 * place of the backdrop's stand-in (runtime.ts Quality.farFull, High only, the quality ladder's
 * first step down). scene.tsx World runs applyShow over the loaded chunks every rendered frame.
 *
 * Only the area's meshes: everything else that follows LoadedSet.drawn (grass, fires, decoration,
 * idle motion, picking, the pond's and the mirror's passes, the ladder's settle) stays with the
 * areas whose need range holds the frame. A far area shows its carved flames, as a fire out of view.
 *
 * three uploads a mesh's buffers the first time it is drawn, so an area's first show costs a long
 * frame. An area that has never been on screen in this page view first shows as far only while
 * nobody sees that frame (the loading screen or fast travel's ink covers the scene, or the camera
 * rests), and at most one a frame. One that has been on screen turns far at once when the frame
 * leaves its range, moving or not, so nothing swaps back to a stand-in on the way out. When the
 * ladder takes the step, every far area goes back to its stand-in at once.
 *
 * Measured at the gate on an RTX 5080 (1600 by 900), seven areas far: 550 to 1,076 draw calls,
 * 8.9 M to 22.0 M triangles, 2.4 to 3.4 ms of GPU time a frame. With those areas drawn as near
 * ones (their grass and fires too) it was 5.5 ms. Facing forward from the library on, the far areas
 * are behind the camera and cost nothing. docs/sect/background-fill.md has the table.
 */

/**
 * How a loaded set shows this frame: in full as the place the camera is at ("near", LoadedSet.drawn),
 * in full as far scenery ("far", LoadedSet.far), or as the backdrop's stand-in ("proxy").
 */
export type SetShow = "near" | "far" | "proxy";

/** What setShow reads of a set. */
export interface FarSet {
  id: string;
  /** Its need range; null for the global set, which is never near or far. */
  need: readonly [number, number] | null;
}

/** What applyShow reads and writes on a set (LoadedSet has them). */
export interface ShowSet extends FarSet {
  /** Drawn in full as the place the camera is at. */
  drawn: boolean;
  /** Drawn in full as far scenery. Never true with `drawn`. */
  far: boolean;
}

/** What the rule reads of the frame. World keeps one and rewrites it each frame (no allocation). */
export interface FarFrame {
  /** The camera's frame. */
  frame: number;
  /** The ladder's stand-in step (Quality.standIns): the one area drawn in full, or null while the step is off. */
  only: string | null;
  /** Far places in full (Quality.farFull). */
  farFull: boolean;
  /** Nobody would see a long frame: the loading screen or fast travel's ink covers the scene, or the camera rests. */
  calm: boolean;
}

/**
 * How one set shows this frame. `ok`: it may be drawn at all (assets.ts drawable). `seen`: it has
 * been on screen, near or far, in this page view. `firstFree`: no other set has had its first far
 * show this frame.
 * - near: drawable, with a need range that holds the frame, and the ladder's stand-in step off or
 *   naming this area (the rule the page always had);
 * - far: far places in full on, the stand-in step off, drawable with a need range, not near; and,
 *   for a set never on screen, only while calm and while the frame's one first show is free;
 * - else proxy.
 */
export function setShow(set: FarSet, ok: boolean, seen: boolean, f: FarFrame, firstFree = true): SetShow {
  if (!ok || set.need === null) return "proxy";
  const inside = f.frame >= set.need[0] && f.frame <= set.need[1];
  if (inside && (f.only === null || set.id === f.only)) return "near";
  if (!f.farFull || f.only !== null || inside) return "proxy";
  return seen || (f.calm && firstFree) ? "far" : "proxy";
}

/**
 * One rendered frame of the rule over the loaded chunks, in their order: sets each one's `drawn`
 * and `far` (setShow), adds a set to `seen` the first time it shows (near or far; at most one first
 * far show a frame), and calls `show(set, visible)` for each set whose scenes turn visible (near or
 * far) or hidden. Returns true when any set's `far` changed: the canvas renders on demand, so the
 * caller keeps frames coming for the first shows still waiting. Allocates nothing.
 */
export function applyShow<S extends ShowSet>(
  sets: readonly S[],
  seen: WeakSet<S>,
  f: FarFrame,
  ok: (set: S) => boolean,
  show: (set: S, visible: boolean) => void,
): boolean {
  let firstFree = true;
  let farChanged = false;
  for (let i = 0; i < sets.length; i++) {
    const s = sets[i];
    const was = seen.has(s);
    const st = setShow(s, ok(s), was, f, firstFree);
    const drawn = st === "near";
    const far = st === "far";
    if (!was && (drawn || far)) {
      seen.add(s);
      if (far) firstFree = false;
    }
    const before = s.drawn || s.far;
    if (s.far !== far) farChanged = true;
    s.drawn = drawn;
    s.far = far;
    if (before !== (drawn || far)) show(s, drawn || far);
  }
  return farChanged;
}

/** `?far=` on the page's URL: "0" / "off" keeps the stand-ins, "1" / "on" draws far places in full on High. */
export type FarSwitch = "on" | "off" | null;

export function parseFarParam(search: string): FarSwitch {
  const m = /[?&]far=([a-z0-9]+)/.exec(search);
  if (!m) return null;
  if (m[1] === "0" || m[1] === "off") return "off";
  if (m[1] === "1" || m[1] === "on") return "on";
  return null;
}

/**
 * Far places in full for the tier's quality (runtime.ts TierOptions.holdsAll): where the page holds
 * every area (`holdsAll`), unless ?far= says otherwise. High only either way (runtime.ts tierQuality).
 */
export function farFullOn(holdsAll: boolean, sw: FarSwitch): boolean {
  if (sw !== null) return sw === "on";
  return holdsAll;
}
