/**
 * The opening of /sect, before the first picture: the poster still behind the loading screen, the
 * download progress of the opening files, and the size of that download for the page view's note.
 */
import type { LookOffset } from "./free-look";

/**
 * The poster stills: the scene at the default start (the top of the path, frame 27, no free look),
 * captured from the live page (?ui=0) and saved as WebP in public/sect/poster/ (landscape under
 * 80 KB, portrait under 60 KB). Landscape is captured on the high tier (desktops). Portrait is
 * captured on the low tier in a touch browser, as phones draw it (they start on Low): a High still
 * was 6 levels darker than a phone's first picture and had no sun glare. They must be captured again
 * whenever that view changes (a new bake of the gate or the backdrop, a new camera path, or a look
 * change: materials, grade, sky, moon): the loading screen crossfades from the still to the canvas,
 * so the two must match.
 *
 * Both are perspective views from the start camera, so each screen's view is a centred crop of one
 * of them at a scale the camera's field of view sets (camera-path.ts fovForAspect):
 * - landscape.webp covers every screen from minAspect to maxAspect wide: the vertical field of view
 *   is the path's fovY on screens wider than 16:9, and the 16:9 horizontal field is kept on narrower
 *   ones (two captures, composited; the corners no such screen sees are filled with a blur).
 * - portrait.webp is the 70 degree view of portrait screens (with the portrait shift, scene.tsx
 *   CameraRig), as wide as the 16:9 horizontal field: every phone sees a centred slice of it.
 * Other shapes get a plain cover fit (a near-square window, an ultrawide screen).
 */
export const POSTER = {
  landscape: "/sect/poster/landscape.webp",
  portrait: "/sect/poster/portrait.webp",
  /** The view the stills show: camera.json's startFrame and that frame's fovY, for a 16:9 film. */
  startFrame: 27,
  fovY: 35.1154,
  refAspect: 16 / 9,
  /** The aspect range landscape.webp covers exactly. */
  minAspect: 1.25,
  maxAspect: 2.4,
  /** Portrait screens see at most this vertical field of view (fovForAspect's maxFovY). */
  maxFovY: 70,
} as const;

const DEG = Math.PI / 180;

/** Rounded for CSS: four significant decimals are well under a pixel. */
function n(x: number): string {
  return String(Math.round(x * 1e4) / 1e4);
}

/**
 * CSS width and height of a poster image centred in a box that fills the screen (the canvas's box,
 * with `container-type: size`, so cqw and cqh are its width and height in hundredths).
 */
export function posterBox(kind: "landscape" | "portrait", p: typeof POSTER = POSTER): { width: string; height: string } {
  const ty0 = Math.tan((p.fovY * DEG) / 2);
  const tx0 = ty0 * p.refAspect;
  if (kind === "portrait") {
    // Image aspect tx0 / tan(maxFovY / 2): a cover fit.
    const a = tx0 / Math.tan((p.maxFovY * DEG) / 2);
    return { width: `max(100cqw, ${n(100 * a)}cqh)`, height: `max(100cqh, ${n(100 / a)}cqw)` };
  }
  // The image spans tan(angle) in [-TX, TX] by [-TY, TY]. A screen of aspect w/h shows
  // k = min(h / (2 ty0), w / (2 tx0)) pixels per unit, so the image is 2 TX k wide; outside the
  // covered range it still covers the screen.
  const TX = p.maxAspect * ty0;
  const TY = tx0 / p.minAspect;
  const r = TX / TY;
  const wh = (100 * TX) / ty0;
  const ww = (100 * TX) / tx0;
  return {
    width: `max(min(${n(wh)}cqh, ${n(ww)}cqw), 100cqw, ${n(100 * r)}cqh)`,
    height: `max(min(${n(wh / r)}cqh, ${n(ww / r)}cqw), ${n(100 / r)}cqw, 100cqh)`,
  };
}

/** The camera at the start frame is the one the stills were captured from. */
export function posterMatches(fovY: number | undefined, refAspect: number, startFrame: number, p: typeof POSTER = POSTER): boolean {
  return fovY !== undefined && Math.abs(fovY - p.fovY) < 0.01 && Math.abs(refAspect - p.refAspect) < 1e-3 && startFrame === p.startFrame;
}

// --- progress --------------------------------------------------------------------------------------

export interface FileProgress {
  loaded: number;
  /** Content-Length, or 0 until the response says. */
  total: number;
  done: boolean;
}

/** A set of opening files and the bytes the manifest says they add up to (0 when it does not say). */
export interface DownloadGroup {
  files: readonly FileProgress[];
  bytes: number;
}

function knownSize(f: FileProgress): number | null {
  if (f.done) return Math.max(f.total, f.loaded);
  return f.total > 0 ? f.total : null;
}

/**
 * Share of the opening download done (0..1), by bytes from the first byte. A file whose size is not
 * known yet counts as what its group still lacks of the manifest's figure (shared among its unknown
 * files), or, when its group has no figure, as the mean known file. So the fraction never jumps from
 * counting files to counting bytes (a small file done early read as a sixth of the download, and the
 * bar fell back when the last size arrived). A late size can still pull it back a little: the page
 * shows the running maximum.
 */
export function downloadFraction(groups: readonly DownloadGroup[]): number {
  const sizes: number[] = [];
  for (const g of groups) for (const f of g.files) {
    const s = knownSize(f);
    if (s !== null) sizes.push(s);
  }
  const mean = sizes.length > 0 ? sizes.reduce((a, b) => a + b, 0) / sizes.length : 0;
  let total = 0;
  let loaded = 0;
  for (const g of groups) {
    let known = 0;
    let unknown = 0;
    for (const f of g.files) {
      const s = knownSize(f);
      if (s === null) unknown++;
      else {
        known += s;
        loaded += f.done ? s : Math.min(f.loaded, s);
      }
    }
    total += known;
    if (unknown > 0) total += g.bytes > known ? g.bytes - known : unknown * mean;
  }
  return total > 0 ? Math.min(loaded / total, 1) : 0;
}

// --- size ------------------------------------------------------------------------------------------

/**
 * Megabytes (millions of bytes) the flight downloads before its first picture: the global set and
 * the first area, from the raw manifest.json (the parsed manifest leaves the global figure out).
 * Phones and the low tier load the 2048 px textures. Null when the manifest does not say.
 */
export function openingMegabytes(raw: unknown, low: boolean): number | null {
  if (!raw || typeof raw !== "object") return null;
  const m = raw as { globalBytes?: unknown; globalBytesLow?: unknown; chunks?: unknown };
  const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) && v > 0 ? v : null);
  const first = Array.isArray(m.chunks) && m.chunks.length > 0 ? (m.chunks[0] as { bytes?: unknown; bytesLow?: unknown }) : null;
  const global = (low ? num(m.globalBytesLow) : null) ?? num(m.globalBytes);
  const chunk = first ? ((low ? num(first.bytesLow) : null) ?? num(first.bytes)) : null;
  if (global === null || chunk === null) return null;
  return Math.max(1, Math.round((global + chunk) / 1e6));
}

// --- portrait framing ------------------------------------------------------------------------------

/**
 * Portrait screens see about 36 degrees of the 58 a 16:9 screen sees at a stop, the picture shifted
 * up (scene.tsx PORTRAIT_SHIFT) between the stop's label and look hint at the top (down to 156 px on
 * a 390 x 844 phone) and the panel at the bottom (from 579 px up, 603 at most stops). At some stops
 * the things the panel talks about sit off that narrower view, or under the labels. Once the camera
 * has come to rest at such a stop on a portrait screen, the view turns (yaw, degrees, positive left)
 * and tilts (pitch, positive up, which lowers the picture) this far, as a drag would turn it; the
 * next scroll swings it back. Measured on a 390 x 844 phone with the panel up, as turns from the
 * stop's framing (framing.ts STOP_FRAMING, every screen):
 * - gate: the roof's ridge and the sun on it sat under the label and the hint. 7 up puts the whole
 *   gate between them and the panel, the sun's top 12 px under the hint.
 * - mirror: the framing stands the camera back along the path and turns it 4 degrees left and 3
 *   down, which centres the Still Pond on a 16:9 screen; on a phone that leaves the pond's west rim
 *   and the pavilion cut by the left edge. 6 more (10 in all) put the pond in the middle, both rims
 *   in with a margin, and the pavilion, the Heart Mirror and the censer whole above the panel.
 * - arena: the Heavy Iron Sword's hilt sat under the label and the hint, its pommel 98 px down. 7
 *   up puts the pommel 175 px down and the whole sword clear, the yin-yang still above the panel.
 *   (Its banners sit off both edges, so no turn helps there.)
 * - mission: the first two experience entries 0% and the third 38% at 0; all seven 100% at 10, the
 *   hall 81% and its bell 72%. The framing turns 8 left and 2 up; 5 more, as 10 in all left the
 *   first post (Pinterest) cut by the left edge and 13 puts the whole board in with a margin either
 *   side. The hall's roof and name board sat under the label and the hint; 7 up clears them, the
 *   board of posts still 180 px above the panel.
 * - library: the pagoda's spire reached under the hint. 5 up puts its tip 8 px below; more would
 *   take the feet of the gate below it under the panel.
 * - steles: the end pavilion's finial touched the hint. 3 up puts it 15 px below.
 * - scroll: the framing turns 8 left and 2.5 down, which puts the whole jade slip and the pavilion
 *   side by side on a 16:9 screen. A phone sees 36 degrees across, narrower than the slip and the
 *   pavilion together from where that framing stands, so on portrait screens it stands further back
 *   (framing.ts portraitBack): the slip and the pavilion side by side across the phone, but high, the
 *   moon under the hint. Half a degree right (7.5 left in all) and 8 up put them 26 px in from the
 *   left edge to 24 from the right, the sun and the moon about 80 px below the hint, the stand on its
 *   rune rings about 170 px above the panel. (From 3 frames nearer, before the owner asked for the
 *   camera "slightly back", 2026-10-24, half a degree left put them 19 px in to 17 from the right.)
 * - abode: the cliff's 洞天福地 ran down under the label and the hint. 3 right moves it left of
 *   them, 30 px from the edge, the moon gate and the waterfall still in.
 * The poster's view is the start of the flight (frame 27, scroll 0), in no hold, so it never turns.
 * Portrait tablets (820 x 1180) turn the same way; their panel sits beside the view, and the tilts
 * hide nothing there the film's view did not (the arena's hilt is behind the panel either way). At
 * the jade slip a tablet stands as far back as a phone, the slip and the pavilion whole in the middle
 * of its wider view. Stood 3 frames further back (2026-10-24), its empty foreground below the plaza
 * also shows coarse rocks along its bottom edge, which the phone's panel covers.
 */
export const PORTRAIT_TURN_DEG: Readonly<Record<string, { yaw?: number; pitch?: number }>> = {
  gate: { pitch: 7 },
  mirror: { yaw: 6 },
  arena: { pitch: 7 },
  mission: { yaw: 5, pitch: 7 },
  library: { pitch: 5 },
  steles: { pitch: 3 },
  scroll: { yaw: -0.5, pitch: 8 },
  abode: { yaw: -3 },
};

/** The turn (radians, as a free-look offset) for a stop on a portrait screen; none when it needs none. */
export function portraitTurn(holdId: string | null, portrait: boolean): LookOffset {
  const t = portrait && holdId ? PORTRAIT_TURN_DEG[holdId] : undefined;
  return { yaw: ((t?.yaw ?? 0) * Math.PI) / 180, pitch: ((t?.pitch ?? 0) * Math.PI) / 180 };
}

/** Seconds the portrait turn takes (eased), about as long as the free look's swing back. */
export const PORTRAIT_TURN_SECONDS = 0.9;

// --- flicks ----------------------------------------------------------------------------------------

/** The scroll map's stops (the start, each hold's middle, the end) and hold zones, as flickStop reads them. */
export interface FlickMap {
  stops: readonly { u: number }[];
  holds: readonly { u0: number; u1: number }[];
}

/**
 * Where a touch flick that has come to rest at scroll position `u`, moving in `direction` (+1 down
 * the path, -1 back, 0 unknown), glides on to: the next stop ahead when it is within `reach` scroll
 * units (about one screen), else the stop just passed when the flick overshot it by a third of that
 * (gliding further back would undo the flick). Null when neither, or when the camera is already
 * there (inside a hold's dwell, where the panel is up, or within a unit of the start or the end).
 */
export function flickStop(map: FlickMap, u: number, reach: number, direction = 0): number | null {
  if (map.holds.some((h) => u >= h.u0 && u <= h.u1)) return null;
  const nearest = (side: number) => {
    let best: number | null = null;
    for (const s of map.stops) {
      if (side !== 0 && (s.u - u) * side <= 0) continue;
      if (best === null || Math.abs(s.u - u) < Math.abs(best - u)) best = s.u;
    }
    return best;
  };
  const near = (to: number | null, limit: number) => to !== null && Math.abs(to - u) >= 1 && Math.abs(to - u) <= limit;
  const dir = Math.sign(direction);
  const ahead = nearest(dir);
  if (near(ahead, reach)) return ahead;
  if (dir === 0) return null;
  const behind = nearest(-dir);
  return near(behind, reach / 3) ? behind : null;
}
