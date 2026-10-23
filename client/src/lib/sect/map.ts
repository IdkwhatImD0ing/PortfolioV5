/**
 * The painted map of the sect (public/sect/map/map.json): reading the file, placing world points on
 * the picture, the eleven stops' seals, the flight route as a dotted line and the visitor's own mark.
 *
 * map.json, version 1:
 *   { "version": 1,
 *     "images": { "<key>": { "src": "<file>.webp", "w": <px>, "h": <px> }, ... },
 *     "world_to_uv": [[a, b, c], [d, e, f]] }
 * A point (x, y, z) of the client's world (three.js, Y up: meta.json anchors, camera.json positions)
 * sits on every picture at u = a*x + b*z + c, v = d*x + e*z + f, as fractions of its width (u, left
 * to right) and height (v, top to bottom). A picture framed differently (a crop) carries its own
 * "world_to_uv"; the others share the file's. The numbers are the art's, never hard-coded here.
 *
 * Optional, "route": [[x, z], ...]: the walkways the painting shows, from the gate's stair foot up
 * through every stop's anchor to the summit, in the same world space (metres). The dotted route is
 * drawn along them; without it, along the camera's flight (which cuts corners through the air).
 *
 * Plain numbers only (no DOM, no three.js), so all of it is unit-tested.
 */
import { AREAS, isAreaId, type AreaId } from "./areas";
import { forward, sampleCamera } from "./camera-path";
import type { AreaMeta, CameraData, HotspotInfo, Vec3 } from "./types";

/** Rows of the affine map from world (x, z) to picture (u, v): [[a, b, c], [d, e, f]]. */
export type UvTransform = readonly [readonly [number, number, number], readonly [number, number, number]];

/** A point on the picture: [u, v] as fractions, or [x, y] in pixels where a function says so. */
export type Pt = readonly [number, number];

export interface MapImage {
  key: string;
  /** As written in map.json (relative to the map's folder, or absolute). */
  src: string;
  w: number;
  h: number;
  /** This picture's transform (its own, or the file's). */
  xf: UvTransform;
}

export interface SectMap {
  version: number;
  /** Smallest first. */
  images: MapImage[];
  /** The stand-in picture the client ships until the painted one lands ("placeholder": true). */
  placeholder: boolean;
  /** The painted walkways as world [x, z] points ("route"), or null (the flight stands in). */
  route: [number, number][] | null;
}

type Obj = Record<string, unknown>;

function isObj(v: unknown): v is Obj {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function parseTransform(v: unknown, what: string): UvTransform {
  const rows = Array.isArray(v) ? v : [];
  const row = (r: unknown): [number, number, number] | null =>
    Array.isArray(r) && r.length >= 3 && r.slice(0, 3).every((x) => typeof x === "number" && Number.isFinite(x)) ? [r[0], r[1], r[2]] : null;
  const a = row(rows[0]);
  const b = row(rows[1]);
  if (rows.length !== 2 || !a || !b) throw new Error(`${what}: world_to_uv must be [[a, b, c], [d, e, f]] (finite numbers)`);
  // A transform that flattens the ground onto a line places nothing.
  if (Math.abs(a[0] * b[1] - a[1] * b[0]) < 1e-12) throw new Error(`${what}: world_to_uv is degenerate`);
  return [a, b];
}

/** A picture path: a plain relative or site path, nothing that runs or leaves the site. */
function safeSrc(v: unknown): string | null {
  if (typeof v !== "string") return null;
  const s = v.trim();
  if (!s || s.length > 200 || /^[a-z][a-z0-9+.-]*:/i.test(s) || s.startsWith("//") || /[\s"'<>\\]/.test(s)) return null;
  return s;
}

/**
 * map.json. Throws a readable error for a file the page cannot use: no pictures, no transform, a
 * picture without a size. Pictures that are broken on their own are left out.
 */
export function parseSectMap(raw: unknown): SectMap {
  if (!isObj(raw)) throw new Error("map.json: expected a JSON object");
  const version = typeof raw.version === "number" && Number.isFinite(raw.version) ? raw.version : 1;
  if (version !== 1) throw new Error(`map.json: version ${version} is not one this page reads`);
  const base = raw.world_to_uv === undefined ? null : parseTransform(raw.world_to_uv, "map.json");
  const imgs = isObj(raw.images) ? raw.images : {};
  const images: MapImage[] = [];
  for (const [key, v] of Object.entries(imgs)) {
    if (!isObj(v)) continue;
    const src = safeSrc(v.src);
    const w = typeof v.w === "number" && Number.isFinite(v.w) && v.w > 0 ? v.w : 0;
    const h = typeof v.h === "number" && Number.isFinite(v.h) && v.h > 0 ? v.h : 0;
    if (!src || !w || !h) continue;
    const xf = v.world_to_uv !== undefined ? parseTransform(v.world_to_uv, `map.json images.${key}`) : base;
    if (!xf) throw new Error(`map.json images.${key}: no world_to_uv (none on the file either)`);
    images.push({ key, src, w, h, xf });
  }
  if (images.length === 0) throw new Error("map.json: 'images' must hold at least one picture with src, w and h");
  images.sort((a, b) => a.w * a.h - b.w * b.h);
  return { version, images, placeholder: raw.placeholder === true, route: parseRoute(raw.route) };
}

/** "route": two or more [x, z] pairs of finite numbers, else null (a broken route is left out, not fatal). */
function parseRoute(v: unknown): [number, number][] | null {
  if (!Array.isArray(v) || v.length < 2 || v.length > 20000) return null;
  const out: [number, number][] = [];
  for (const p of v) {
    if (!Array.isArray(p) || p.length < 2 || typeof p[0] !== "number" || typeof p[1] !== "number" || !Number.isFinite(p[0]) || !Number.isFinite(p[1])) return null;
    out.push([p[0], p[1]]);
  }
  return out;
}

/**
 * The picture to show in a box of `boxW` x `boxH` CSS pixels at device pixel ratio `dpr`: the
 * smallest that still has a pixel for every screen pixel, else the largest. Pictures framed like
 * the first one (the same transform) are preferred over crops.
 */
/** The share of the screen's pixels a map picture must have to be used (pickMapImage). */
export const MAP_SHORT_OK = 0.9;

export function pickMapImage(map: SectMap, boxW: number, boxH: number, dpr = 1): MapImage {
  const main = map.images.filter((im) => sameTransform(im.xf, map.images[map.images.length - 1].xf));
  const list = main.length > 0 ? main : map.images;
  const k = Math.max(1, Math.min(dpr, 3));
  for (const im of list) {
    const fit = mapFit({ w: boxW, h: boxH }, im, 0);
    // A picture up to MAP_SHORT_OK short of the screen's pixels looks the same (a 390 px phone at 3x
    // wanted 1050 px of the 1024 px picture and fetched the 1.36 MB one for 2.5%).
    if (im.w >= fit.w * k * MAP_SHORT_OK - 1 && im.h >= fit.h * k * MAP_SHORT_OK - 1) return im;
  }
  return list[list.length - 1];
}

function sameTransform(a: UvTransform, b: UvTransform): boolean {
  return a.every((row, i) => row.every((x, j) => Math.abs(x - b[i][j]) < 1e-12));
}

/** Where world point `p` (three space) sits on the picture, as [u, v] fractions. */
export function worldToUv(xf: UvTransform, p: Vec3): [number, number] {
  return [xf[0][0] * p[0] + xf[0][1] * p[2] + xf[0][2], xf[1][0] * p[0] + xf[1][1] * p[2] + xf[1][2]];
}

/** A world direction (dx, dz) on the picture, in pixels of a `w` x `h` picture (not normalised). */
export function worldDirToPx(xf: UvTransform, d: Vec3, w: number, h: number): [number, number] {
  return [(xf[0][0] * d[0] + xf[0][1] * d[2]) * w, (xf[1][0] * d[0] + xf[1][1] * d[2]) * h];
}

/** A picture of `img` size fitted inside `box` (contain), `pad` px clear of its edges, centred. */
export function mapFit(box: { w: number; h: number }, img: { w: number; h: number }, pad = 0): { x: number; y: number; w: number; h: number } {
  const bw = Math.max(0, box.w - 2 * pad);
  const bh = Math.max(0, box.h - 2 * pad);
  if (!(img.w > 0) || !(img.h > 0) || bw === 0 || bh === 0) return { x: box.w / 2, y: box.h / 2, w: 0, h: 0 };
  const s = Math.min(bw / img.w, bh / img.h);
  const w = img.w * s;
  const h = img.h * s;
  return { x: (box.w - w) / 2, y: (box.h - h) / 2, w, h };
}

export interface MapStop {
  id: AreaId;
  /** Where its seal goes, as [u, v]. */
  uv: [number, number];
  /** The area's anchor (meta.json), or where the camera stands at its hold when it has none. */
  from: "anchor" | "hold";
}

/**
 * The stops in flight order (camera.json holds), each at its area's anchor: meta.json areas[].anchor,
 * else the hotspot named after the area, else the camera at the hold. Holds that are not one of the
 * eleven areas are left out, and so is an area with no hold.
 */
export function mapStops(
  meta: { areas: readonly AreaMeta[]; hotspots: readonly HotspotInfo[] },
  camera: Pick<CameraData, "frames" | "holds">,
  xf: UvTransform,
): MapStop[] {
  const out: MapStop[] = [];
  const seen = new Set<string>();
  for (const h of camera.holds) {
    if (!isAreaId(h.id) || seen.has(h.id)) continue;
    seen.add(h.id);
    const anchor = meta.areas.find((a) => a.id === h.id)?.anchor ?? meta.hotspots.find((x) => x.id === h.id)?.center ?? null;
    if (anchor) out.push({ id: h.id, uv: worldToUv(xf, anchor), from: "anchor" });
    else if (camera.frames.length > 0) out.push({ id: h.id, uv: worldToUv(xf, sampleCamera(camera.frames, h.frame).p), from: "hold" });
  }
  return out;
}

/** Route order of the area ids (for lists that have no camera data). */
export function routeOrder(ids: readonly string[]): AreaId[] {
  const order = AREAS.map((a) => a.id);
  return ids.filter(isAreaId).sort((a, b) => order.indexOf(a) - order.indexOf(b));
}

/**
 * Seals that would overlap (centres closer than `minDist` px) pushed apart, a little at a time, so
 * each stays as near its true place as it can. `pinned` points (the visitor's mark) push seals to
 * `pinDist` px (default 0.7 of `minDist`) but never move. The result stays inside `box` (`margin` px
 * clear of its edges). Deterministic: the same input always gives the same layout.
 */
export function spreadMarkers(
  points: readonly Pt[],
  minDist: number,
  box: { w: number; h: number },
  pinned: readonly Pt[] = [],
  margin = 0,
  pinDist = minDist * 0.7,
): [number, number][] {
  const p = points.map((q) => [q[0], q[1]] as [number, number]);
  const lo = (n: number) => Math.min(margin, n / 2);
  const clampIn = (q: [number, number]) => {
    q[0] = Math.min(Math.max(q[0], lo(box.w)), box.w - lo(box.w));
    q[1] = Math.min(Math.max(q[1], lo(box.h)), box.h - lo(box.h));
  };
  p.forEach(clampIn);
  if (!(minDist > 0)) return p;
  for (let iter = 0; iter < 80; iter++) {
    let moved = false;
    for (let i = 0; i < p.length; i++) {
      for (let j = i + 1; j < p.length; j++) {
        const dx = p[j][0] - p[i][0];
        const dy = p[j][1] - p[i][1];
        const d = Math.hypot(dx, dy);
        if (d >= minDist - 1e-6) continue;
        // Coincident seals part along a fixed direction that depends on their order.
        const a = d > 1e-6 ? Math.atan2(dy, dx) : (i * 2.399963 + j) % (2 * Math.PI);
        const push = (minDist - d) / 2 + 0.01;
        p[i][0] -= Math.cos(a) * push;
        p[i][1] -= Math.sin(a) * push;
        p[j][0] += Math.cos(a) * push;
        p[j][1] += Math.sin(a) * push;
        clampIn(p[i]);
        clampIn(p[j]);
        moved = true;
      }
      for (const q of pinned) {
        const dx = p[i][0] - q[0];
        const dy = p[i][1] - q[1];
        const d = Math.hypot(dx, dy);
        const need = pinDist;
        if (d >= need - 1e-6) continue;
        const a = d > 1e-6 ? Math.atan2(dy, dx) : -Math.PI / 2;
        p[i][0] += Math.cos(a) * (need - d + 0.01);
        p[i][1] += Math.sin(a) * (need - d + 0.01);
        clampIn(p[i]);
        moved = true;
      }
    }
    if (!moved) break;
  }
  return p;
}

/** Ramer-Douglas-Peucker: the points of `pts` a line `epsilon` away from the original still needs. */
export function simplifyLine(pts: readonly Pt[], epsilon: number): Pt[] {
  if (pts.length <= 2) return pts.slice();
  const keep = new Uint8Array(pts.length);
  keep[0] = 1;
  keep[pts.length - 1] = 1;
  const stack: [number, number][] = [[0, pts.length - 1]];
  while (stack.length > 0) {
    const [s, e] = stack.pop()!;
    const [ax, ay] = pts[s];
    const [bx, by] = pts[e];
    const dx = bx - ax;
    const dy = by - ay;
    const len = Math.hypot(dx, dy);
    let best = -1;
    let bestD = epsilon;
    for (let i = s + 1; i < e; i++) {
      const [px, py] = pts[i];
      const d = len > 1e-9 ? Math.abs(dy * px - dx * py + bx * ay - by * ax) / len : Math.hypot(px - ax, py - ay);
      if (d > bestD) {
        bestD = d;
        best = i;
      }
    }
    if (best >= 0) {
      keep[best] = 1;
      stack.push([s, best], [best, e]);
    }
  }
  return pts.filter((_, i) => keep[i] === 1);
}

/** World points on the picture as [u, v], simplified to within `tolerancePx` pixels of a `w` x `h` picture. */
function uvLine(points: readonly Vec3[], xf: UvTransform, w: number, h: number, tolerancePx: number): Pt[] {
  const px = points.map((p) => {
    const [u, v] = worldToUv(xf, p);
    return [u * w, v * h] as const;
  });
  return simplifyLine(px, tolerancePx).map(([x, y]) => [x / w, y / h] as const);
}

/**
 * The flight as a line on the picture, as [u, v] points: the camera's positions from its start frame
 * to its last, simplified to within `tolerancePx` pixels of a `w` x `h` picture.
 */
export function routeLine(camera: Pick<CameraData, "frames" | "startFrame">, xf: UvTransform, w: number, h: number, tolerancePx = 1.5): Pt[] {
  return uvLine(
    camera.frames.filter((f) => f.f >= camera.startFrame).map((f) => f.p),
    xf,
    w,
    h,
    tolerancePx,
  );
}

/** The painted walkways (map.json "route", world [x, z]) on the picture, as routeLine draws the flight. */
export function walkLine(route: readonly (readonly [number, number])[], xf: UvTransform, w: number, h: number, tolerancePx = 1.5): Pt[] {
  return uvLine(
    route.map(([x, z]): Vec3 => [x, 0, z]),
    xf,
    w,
    h,
    tolerancePx,
  );
}

/** An SVG path through [u, v] points, drawn on a `w` x `h` viewBox. */
export function linePath(pts: readonly Pt[], w: number, h: number): string {
  return pts.map(([u, v], i) => `${i === 0 ? "M" : "L"}${(u * w).toFixed(1)} ${(v * h).toFixed(1)}`).join("");
}

export interface HereMark {
  uv: [number, number];
  /**
   * The way the camera looks, as degrees clockwise from straight up on a `w` x `h` picture, or null
   * when it looks almost straight up or down (no heading to show).
   */
  heading: number | null;
}

/** The visitor's mark: where the camera is at `frame`, and which way it looks. */
export function hereMark(camera: Pick<CameraData, "frames">, frame: number, xf: UvTransform, w: number, h: number): HereMark | null {
  if (camera.frames.length === 0 || !Number.isFinite(frame)) return null;
  const s = sampleCamera(camera.frames, frame);
  const f = forward(s.q);
  const flat = Math.hypot(f[0], f[2]);
  let heading: number | null = null;
  if (flat > 0.2) {
    const [dx, dy] = worldDirToPx(xf, f, w, h);
    if (Math.hypot(dx, dy) > 1e-9) heading = (Math.atan2(dx, -dy) * 180) / Math.PI;
  }
  return { uv: worldToUv(xf, s.p), heading };
}

/**
 * The seal an arrow key (or Home/End) moves to from seal `i` of `n`, or null for a key that does not
 * move. On the map "up" follows the picture: when the route climbs up it (`upIsForward`), Up and
 * Right go on toward the summit and Down and Left back toward the gate; the other way round, Up and
 * Left. The ends stop (no wrapping).
 */
export function mapKeyStep(key: string, i: number, n: number, upIsForward = true): number | null {
  if (n <= 0) return null;
  let d = 0;
  switch (key) {
    case "ArrowUp":
    case "Up":
      d = upIsForward ? 1 : -1;
      break;
    case "ArrowDown":
    case "Down":
      d = upIsForward ? -1 : 1;
      break;
    case "ArrowRight":
    case "Right":
      d = 1;
      break;
    case "ArrowLeft":
    case "Left":
      d = -1;
      break;
    case "Home":
      return 0;
    case "End":
      return n - 1;
    default:
      return null;
  }
  return Math.min(n - 1, Math.max(0, i + d));
}

/** The route climbs up the picture: the last stop sits higher (smaller v) than the first. */
export function routeClimbsUp(stops: readonly { uv: Pt }[]): boolean {
  return stops.length < 2 || stops[stops.length - 1].uv[1] <= stops[0].uv[1];
}

/** A round thing on the map a plate should not cover: a seal, the visitor's mark. */
export interface Disc {
  x: number;
  y: number;
  r: number;
}

/**
 * Point `p` moved just outside the discs it lies in: straight away from the centre of the one it sits
 * deepest in (up when it sits on the centre), or, where discs overlap and that lands in another, to
 * the nearest clear spot round it (rings 2 px apart), the one most nearly that way. The visitor's mark
 * steps aside so: the seals never leave their painted places for it. Deterministic.
 */
export function clearOf(p: Pt, discs: readonly Disc[]): [number, number] {
  const inside = (x: number, y: number) => discs.some((d) => Math.hypot(x - d.x, y - d.y) < d.r - 1e-6);
  if (!inside(p[0], p[1])) return [p[0], p[1]];
  const out = (d: Disc): [number, number] => {
    const dx = p[0] - d.x;
    const dy = p[1] - d.y;
    const dist = Math.hypot(dx, dy);
    return dist > 1e-6 ? [dx / dist, dy / dist] : [0, -1];
  };
  const deepest = discs.reduce((a, d) => (d.r - Math.hypot(p[0] - d.x, p[1] - d.y) > a.r - Math.hypot(p[0] - a.x, p[1] - a.y) ? d : a));
  const [ux, uy] = out(deepest);
  const exit: [number, number] = [deepest.x + ux * (deepest.r + 0.01), deepest.y + uy * (deepest.r + 0.01)];
  if (!inside(exit[0], exit[1])) return exit;
  const reach = Math.max(...discs.map((d) => d.r * 2)) * 2;
  for (let r = 2; r <= reach; r += 2) {
    let best: [number, number] | null = null;
    let bestDot = -Infinity;
    for (let k = 0; k < 36; k++) {
      const a = (k / 36) * Math.PI * 2;
      const x = p[0] + Math.cos(a) * r;
      const y = p[1] + Math.sin(a) * r;
      const dot = Math.cos(a) * ux + Math.sin(a) * uy;
      if (dot > bestDot + 1e-9 && !inside(x, y)) {
        best = [x, y];
        bestDot = dot;
      }
    }
    if (best) return best;
  }
  return exit;
}

/**
 * Where a seal's name plate goes, as its top-left corner in px. Beside the seal at `at` (radius
 * `r`) first, right then left, since the route mostly runs up and down; else above, else below. Of
 * the sides that fit inside `view` (`margin` px clear), the one covering the least of the `avoid`
 * discs (the other seals) wins, the earlier side on a tie. When none fits, above, moved inside.
 */
export function platePosition(
  at: Pt,
  r: number,
  plate: { w: number; h: number },
  view: { w: number; h: number },
  avoid: readonly Disc[] = [],
  gap = 8,
  margin = 8,
): { left: number; top: number; side: "right" | "left" | "above" | "below" } {
  const { w, h } = plate;
  const clampX = (x: number) => Math.min(Math.max(x, margin), Math.max(margin, view.w - w - margin));
  const clampY = (y: number) => Math.min(Math.max(y, margin), Math.max(margin, view.h - h - margin));
  const sides = [
    { side: "right" as const, left: at[0] + r + gap, top: clampY(at[1] - h / 2) },
    { side: "left" as const, left: at[0] - r - gap - w, top: clampY(at[1] - h / 2) },
    { side: "above" as const, left: clampX(at[0] - w / 2), top: at[1] - r - gap - h },
    { side: "below" as const, left: clampX(at[0] - w / 2), top: at[1] + r + gap },
  ];
  const inside = (c: { left: number; top: number }) =>
    c.left >= margin - 0.5 && c.top >= margin - 0.5 && c.left + w <= view.w - margin + 0.5 && c.top + h <= view.h - margin + 0.5;
  const covered = (c: { left: number; top: number }) => {
    let sum = 0;
    for (const d of avoid) {
      const ox = Math.min(c.left + w, d.x + d.r) - Math.max(c.left, d.x - d.r);
      const oy = Math.min(c.top + h, d.y + d.r) - Math.max(c.top, d.y - d.r);
      if (ox > 0 && oy > 0) sum += ox * oy;
    }
    return sum;
  };
  let best: (typeof sides)[number] | null = null;
  let bestCover = Infinity;
  for (const c of sides) {
    if (!inside(c)) continue;
    const k = covered(c);
    if (k < bestCover - 1e-6) {
      best = c;
      bestCover = k;
    }
  }
  if (best) return best;
  return { side: "above", left: clampX(at[0] - w / 2), top: clampY(at[1] - r - gap - h) };
}
