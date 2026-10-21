/**
 * Living things in the air over /sect, as pure data and maths (no three.js): distant bird flocks
 * crossing the valleys, glowing qi motes and fireflies at the holds, rising off the near waterfalls
 * and hanging over the flowering trees and ponds, and a few spirit butterflies around the peach
 * trees. experience/life.tsx draws each kind as one instanced draw; its shaders mirror flockPoint,
 * birdPoint, motePoint and butterflyPoint, so the motion is testable here.
 *
 * Everything is placed from the camera path's holds (and meta.json's waterfalls and hotspots) with
 * fixed hashes: the same scroll position always shows the same flocks. Motion is a function of the
 * clock only (nothing random per frame). Each group (a flock, a cluster of motes, a tree's
 * butterflies) belongs to its hold's stretch of the flight and fades in and out with it.
 *
 * Tiers thin the same tables: instances are packed in rank order, so drawing the first N keeps an
 * even spread (whole flocks drop out first; motes thin evenly everywhere).
 */
import { forward, sampleCamera } from "./camera-path";
import { hash01 } from "./fx";
import { hexToLinear } from "./glsl";
import type { CameraData, SectMeta, Vec3 } from "./types";

export type LifeTier = "high" | "mid" | "low";

export const LIFE = {
  /** Share of each spawn table drawn per tier (life.tsx sets the instance count, never rebuilds). */
  tierShare: { high: 1, mid: 0.6, low: 0.35 } as Record<LifeTier, number>,
  /** Share of the motes kept with reduced motion (drawn still); birds and butterflies are hidden. */
  reducedMotesShare: 0.35,
  /** Frames over which a group fades in and out at the edges of its hold's stretch of the flight. */
  fadeFrames: 24,
  birds: {
    flocksPerHold: 3,
    /** Where a flock crosses the hold's view (m from the hold camera, along its view). */
    distance: [200, 520] as const,
    /** Seen between these distances from the camera (fading in below, out above). */
    near: [110, 150] as const,
    far: [600, 720] as const,
    /** Each lap moves the route this far toward or away from the camera, and up or down (m). */
    lapDepth: 35,
    lapHeight: 12,
    /** Gentle rise and fall along the route (m). */
    undulate: 5,
    /** Share of the route at each end over which a flock fades (it wraps there). */
    endFade: 0.18,
    /** Lowest a flock flies: this far over the cloud layer's fog top (m). */
    overCloud: 30,
    /** Drawn at least this many pixels across, fainter as they shrink below it. */
    minPx: 3,
    /** Dark silhouettes; the second kind (a straggling line of larger birds) a touch warmer. */
    color: "#232229",
    colorLine: "#3a3532",
  },
  motes: {
    /** Motes in front of each hold camera, before the twilight boost. */
    perHold: 70,
    /** Extra share at full twilight (the summit gets 1 + this). */
    twilightBoost: 0.8,
    /** Depth range in front of the hold camera (m). */
    depth: [9, 55] as const,
    /** Hold motes stay within this height over the ground (m): low over the terraces, not up in the sky. */
    maxHeight: 16,
    /**
     * ...and, with their rise, at most this far over the hold camera's eye (m). A low camera looking
     * up (the summit, the gate) would otherwise see them drift up through open sky like snow.
     */
    overEye: 3,
    /** Waterfalls whose sheet comes within this many metres of the flight get rising qi. */
    waterfallReach: 200,
    perBlossom: 28,
    perPond: 20,
    /** Smallest on-screen radius (px); smaller motes are drawn at this size, dimmer. */
    minPx: 2.2,
    /** Fade-in distance from the camera (m): a mote never blooms over the lens. */
    near: [1.2, 3.5] as const,
    /** Colours (sRGB hex) and their glow (linear multiplier: above 1 the bloom catches the core). */
    firefly: { color: "#d9ff8f", gain: 1.8 },
    qiGold: { color: "#ffe6a6", gain: 1.25 },
    qiJade: { color: "#9ef0d4", gain: 1.25 },
    qiTwilight: { color: "#b4d6f5", gain: 1.3 },
    blossom: { color: "#ffc4d8", gain: 1.3 },
    water: { color: "#d4f2ff", gain: 1.3 },
  },
  butterflies: {
    perTree: 8,
    /** Half wingspan (m): spirit butterflies, large enough to read from the hold. */
    halfSpan: [0.14, 0.2] as const,
    minPx: 5,
    colors: ["#fff3d1", "#ffd36b", "#bfe4ff", "#ffc2dc"] as const,
  },
  /** Hotspots that are flowering trees (motes and butterflies) and ponds (fireflies over the water). */
  blossomIds: ["mirror-blossom", "fact:1"] as const,
  pondIds: ["mirror-pond", "library-pond", "fact:6"] as const,
};

// ---------------------------------------------------------------------------------------------
// Small maths

function clamp(x: number, lo: number, hi: number): number {
  return x < lo ? lo : x > hi ? hi : x;
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

export function smoothstep(a: number, b: number, x: number): number {
  const t = clamp((x - a) / (b - a), 0, 1);
  return t * t * (3 - 2 * t);
}

function normalize(v: Vec3): Vec3 {
  const l = Math.hypot(v[0], v[1], v[2]);
  return l > 1e-9 ? [v[0] / l, v[1] / l, v[2] / l] : [0, 0, 0];
}

function fract(x: number): number {
  return x - Math.floor(x);
}

/** Hash of a float to 0..1 without sine (Dave Hoskins' hash11), mirrored by sectLifeHash in GLSL. */
export function lifeHash(p: number): number {
  let x = fract(p * 0.1031);
  x *= x + 33.33;
  x *= x + x;
  return fract(x);
}

/** GLSL of lifeHash (paste into a shader that mirrors flockPoint). */
export const LIFE_HASH_GLSL = /* glsl */ `
float sectLifeHash( float p ) {
  p = fract( p * 0.1031 );
  p *= p + 33.33;
  p *= p + p;
  return fract( p );
}
`;

/**
 * How much a group shows at a camera frame: 1 inside [lo, hi], 0 more than `fade` frames outside,
 * smooth between (two neighbouring holds cross-fade around the frame between them). Mirrored in
 * the shaders.
 */
export function windowFade(frame: number, lo: number, hi: number, fade = LIFE.fadeFrames): number {
  return smoothstep(lo - fade, lo + fade, frame) * (1 - smoothstep(hi - fade, hi + fade, frame));
}

// ---------------------------------------------------------------------------------------------
// Tiers

/** The quality the canvas runs at, as a life tier (the ladder's MSAA step makes high draw as mid). */
export function lifeTier(q: { post: boolean; msaa: number }): LifeTier {
  if (!q.post) return "low";
  return q.msaa > 0 ? "high" : "mid";
}

export interface LifeCounts {
  birds: number;
  motes: number;
  butterflies: number;
}

/** How many of each table's instances to draw at a tier (the tables are packed in rank order). */
export function lifeCounts(total: LifeCounts, tier: LifeTier, reducedMotion: boolean): LifeCounts {
  const share = LIFE.tierShare[tier];
  if (reducedMotion) {
    return { birds: 0, motes: Math.round(total.motes * Math.min(share, LIFE.reducedMotesShare)), butterflies: 0 };
  }
  return {
    birds: Math.round(total.birds * share),
    motes: Math.round(total.motes * share),
    // A handful of instances: phones skip them (they would be specks on a small screen).
    butterflies: tier === "low" ? 0 : Math.round(total.butterflies * share),
  };
}

// ---------------------------------------------------------------------------------------------
// Holds

/** A hold camera's view and the stretch of the flight it owns. */
export interface HoldView {
  id: string;
  frame: number;
  p: Vec3;
  /** Unit view direction. */
  fwd: Vec3;
  /** Unit horizontal view direction. */
  fwdH: Vec3;
  /** Unit horizontal right of the view. */
  right: Vec3;
  /** tan of half the vertical and horizontal field of view (16:9 film). */
  tanY: number;
  tanX: number;
  /** Frames [lo, hi]: halfway to the previous and next holds (the ends reach past the path's). */
  window: [number, number];
}

export function holdViews(camera: CameraData): HoldView[] {
  const holds = [...camera.holds].filter((h) => Number.isFinite(h.frame)).sort((a, b) => a.frame - b.frame);
  if (holds.length === 0 || camera.frames.length === 0) return [];
  const pad = LIFE.fadeFrames * 2;
  return holds.map((h, i) => {
    const s = sampleCamera(camera.frames, h.frame);
    const fwd = normalize(forward(s.q));
    let fwdH = normalize([fwd[0], 0, fwd[2]]);
    if (fwdH[0] === 0 && fwdH[2] === 0) fwdH = [0, 0, -1];
    const right: Vec3 = [-fwdH[2], 0, fwdH[0]];
    const tanY = Math.tan(((s.fovY || 35) * Math.PI) / 360);
    const lo = i === 0 ? camera.frameStart - pad : (holds[i - 1].frame + h.frame) / 2;
    const hi = i === holds.length - 1 ? camera.frameEnd + pad : (h.frame + holds[i + 1].frame) / 2;
    return { id: h.id, frame: h.frame, p: s.p, fwd, fwdH, right, tanY, tanX: tanY * (camera.refAspect || 16 / 9), window: [lo, hi] };
  });
}

/** 0 before the twilight's first hold, 1 from its second (look.ts twilightAmount), as a function. */
export function twilightOf(views: readonly HoldView[], from: string, to: string): (frame: number) => number {
  const a = views.find((v) => v.id === from)?.frame;
  const b = views.find((v) => v.id === to)?.frame;
  if (a === undefined || b === undefined || !(b > a)) return () => 0;
  return (f) => smoothstep(a, b, f);
}

/** A group's bounds and stretch of the flight, for the per-frame "anything to draw?" test. */
export interface LifeGroup {
  window: [number, number];
  center: Vec3;
  radius: number;
}

/** Floats per group in packGroups: lo, hi, centre (3), radius. */
export const GROUP_STRIDE = 6;

export function packGroups(groups: readonly LifeGroup[]): Float32Array {
  const out = new Float32Array(groups.length * GROUP_STRIDE);
  groups.forEach((g, i) => out.set([g.window[0], g.window[1], g.center[0], g.center[1], g.center[2], g.radius], i * GROUP_STRIDE));
  return out;
}

/**
 * Index of the first group live at `frame` that `visible(cx, cy, cz, r)` accepts, or -1. No
 * allocations: called every frame.
 */
export function firstLiveGroup(
  groups: Float32Array,
  frame: number,
  visible: (x: number, y: number, z: number, r: number) => boolean,
  fade = LIFE.fadeFrames,
): number {
  for (let o = 0, i = 0; o + GROUP_STRIDE <= groups.length; o += GROUP_STRIDE, i++) {
    if (frame <= groups[o] - fade || frame >= groups[o + 1] + fade) continue;
    if (visible(groups[o + 2], groups[o + 3], groups[o + 4], groups[o + 5])) return i;
  }
  return -1;
}

// ---------------------------------------------------------------------------------------------
// Birds

export interface Flock {
  hold: string;
  /** Where the route crosses the hold's view. */
  center: Vec3;
  /** Heading of travel in the ground plane: direction (cos a, 0, sin a). */
  angle: number;
  /** Route length (m): the flock flies it, then starts again at the other end (faded at both). */
  length: number;
  /** m/s. */
  speed: number;
  /** Metres along the route at t = 0. */
  offset: number;
  /** 0..1, varies each lap's route. */
  seed: number;
  count: number;
  /** 0: a loose flock of small dark birds; 1: a straggling line of larger, slower ones. */
  kind: 0 | 1;
  /** Wingspan (m). */
  span: number;
  flapHz: number;
  window: [number, number];
  /** Thinning order (lower is kept longer). */
  rank: number;
}

export interface BirdOptions {
  /** Lowest a flock's route may run (three y). */
  minY: number;
  flocksPerHold?: number;
}

export function birdFlocks(views: readonly HoldView[], opts: BirdOptions): Flock[] {
  const B = LIFE.birds;
  const per = opts.flocksPerHold ?? B.flocksPerHold;
  const out: Flock[] = [];
  views.forEach((v, i) => {
    for (let j = 0; j < per; j++) {
      const key = i * 16 + j;
      const h = (n: number) => hash01(key, 100 + n);
      const kind: 0 | 1 = j === per - 1 && h(1) < 0.5 ? 1 : 0;
      const d = lerp(B.distance[0], B.distance[1], h(0));
      const lateral = (h(2) * 2 - 1) * 0.4 * d * v.tanX;
      const lift = lerp(-0.5, 0.35, h(3)) * d * v.tanY;
      const c: Vec3 = [
        v.p[0] + v.fwd[0] * d + v.right[0] * lateral,
        v.p[1] + v.fwd[1] * d + lift,
        v.p[2] + v.fwd[2] * d + v.right[2] * lateral,
      ];
      // Keep the whole route (with its lap shifts and formation) over the cloud layer.
      c[1] = Math.max(c[1], opts.minY + B.lapHeight + B.undulate + 6);
      const across = Math.atan2(v.right[2], v.right[0]);
      const angle = across + (h(4) - 0.5) * ((70 * Math.PI) / 180) + (h(5) < 0.5 ? Math.PI : 0);
      const length = 2 * d * v.tanX * 1.25 + 160;
      out.push({
        hold: v.id,
        center: c,
        angle,
        length,
        speed: kind === 0 ? lerp(8, 13, h(6)) : lerp(6, 8.5, h(6)),
        // A hold's flocks start spread around their routes, so one is usually in view.
        offset: ((j + h(7) * 0.6) / per) * length,
        seed: h(11),
        count: kind === 0 ? Math.round(lerp(6, 20, h(8))) : Math.round(lerp(5, 9, h(8))),
        kind,
        span: kind === 0 ? lerp(0.85, 1.2, h(9)) : lerp(1.5, 1.9, h(9)),
        flapHz: kind === 0 ? lerp(3.0, 4.2, h(10)) : lerp(1.7, 2.3, h(10)),
        window: v.window,
        rank: j + h(12) * 0.5,
      });
    }
  });
  return out;
}

/** A bird's place in its flock: offset along the route, up, across (m), and its own phase. */
export interface BirdSlot {
  o: Vec3;
  phase: number;
  /** Amplitude (m) of its slow drift around the slot. */
  wander: number;
}

export function flockFormation(f: Flock, flockIndex: number): BirdSlot[] {
  const out: BirdSlot[] = [];
  const n = f.count;
  for (let k = 0; k < n; k++) {
    const h = (m: number) => hash01(flockIndex * 64 + k, 200 + m);
    if (f.kind === 0) {
      // A loose cloud, longer than it is wide, thin vertically.
      const sx = 10 + n * 0.8;
      const sy = 3 + n * 0.2;
      const sz = 8 + n * 0.6;
      out.push({ o: [(h(0) * 2 - 1) * sx, (h(1) * 2 - 1) * sy, (h(2) * 2 - 1) * sz], phase: h(3), wander: lerp(1.5, 3.5, h(4)) });
    } else {
      // A ragged echelon: a leader, the rest trailing on alternate sides.
      const rank = Math.ceil(k / 2);
      const side = k % 2 === 0 ? 1 : -1;
      out.push({
        o: [-rank * 4.5 + (h(0) - 0.5) * 2, (h(1) - 0.5) * 1.2, side * rank * 3.5 + (h(2) - 0.5) * 2],
        phase: h(3),
        wander: lerp(0.4, 1.0, h(4)),
      });
    }
  }
  return out;
}

/** Route centre of a flock at time t, how far along the route it is (0..1), and its end fade. */
export function flockPoint(f: Pick<Flock, "center" | "angle" | "length" | "speed" | "offset" | "seed">, t: number): { p: Vec3; u: number; fade: number } {
  const B = LIFE.birds;
  const s = t * f.speed + f.offset;
  const lap = Math.floor(s / f.length);
  const u = s - lap * f.length;
  const along = u - 0.5 * f.length;
  const dx = Math.cos(f.angle);
  const dz = Math.sin(f.angle);
  const depth = (lifeHash(lap * 1.618 + f.seed * 97) - 0.5) * 2 * B.lapDepth;
  const lift = (lifeHash(lap * 2.718 + f.seed * 57 + 11) - 0.5) * 2 * B.lapHeight + Math.sin(along * 0.011 + f.seed * 20) * B.undulate;
  const e = B.endFade * f.length;
  return {
    p: [f.center[0] + dx * along - dz * depth, f.center[1] + lift, f.center[2] + dz * along + dx * depth],
    u: u / f.length,
    fade: smoothstep(0, e, u) * smoothstep(0, e, f.length - u),
  };
}

/** A bird's position: its flock's point plus its slot (in the flock's frame) and a slow drift. */
export function birdPoint(f: Flock, slot: BirdSlot, t: number): Vec3 {
  const { p } = flockPoint(f, t);
  const dx = Math.cos(f.angle);
  const dz = Math.sin(f.angle);
  const ph = slot.phase;
  const w = slot.wander;
  return [
    p[0] + dx * slot.o[0] - dz * slot.o[2] + Math.sin(t * 0.23 + ph * 7) * w,
    p[1] + slot.o[1] + Math.sin(t * 0.31 + ph * 3) * w * 0.6,
    p[2] + dz * slot.o[0] + dx * slot.o[2] + Math.cos(t * 0.19 + ph * 5) * w,
  ];
}

/** Floats per bird: route (centre, angle), (length, speed, offset, seed), slot (o, phase), (span, flapHz, kind, wander), (lo, hi, 0, 0). */
export const BIRD_STRIDE = 20;

export interface Packed {
  data: Float32Array;
  count: number;
  stride: number;
  groups: Float32Array;
}

/** All flocks' birds, whole flocks in rank order (the first N drop the highest-ranked flocks first). */
export function packBirds(flocks: readonly Flock[]): Packed {
  const order = flocks.map((f, i) => i).sort((a, b) => flocks[a].rank - flocks[b].rank || a - b);
  const total = flocks.reduce((n, f) => n + f.count, 0);
  const data = new Float32Array(total * BIRD_STRIDE);
  let o = 0;
  const groups: LifeGroup[] = [];
  for (const i of order) {
    const f = flocks[i];
    for (const s of flockFormation(f, i)) {
      data.set(
        [
          f.center[0], f.center[1], f.center[2], f.angle,
          f.length, f.speed, f.offset, f.seed,
          s.o[0], s.o[1], s.o[2], s.phase,
          f.span, f.flapHz, f.kind, s.wander,
          f.window[0], f.window[1], 0, 0,
        ],
        o,
      );
      o += BIRD_STRIDE;
    }
    const reach = f.length / 2 + LIFE.birds.lapDepth + 40;
    groups.push({ window: f.window, center: f.center, radius: reach });
  }
  return { data, count: total, stride: BIRD_STRIDE, groups: packGroups(groups) };
}

// ---------------------------------------------------------------------------------------------
// Motes

/** 0: a firefly (wanders and blinks); 1: a qi mote (rises slowly and fades over its life). */
export type MoteKind = 0 | 1;

export interface Mote {
  home: Vec3;
  seed: number;
  /** Sprite half-size (m). */
  radius: number;
  kind: MoteKind;
  /** Drift amplitude around home (m). */
  wander: number;
  /** Height a qi mote rises over its life (m). */
  rise: number;
  /** Linear colour times glow. */
  color: Vec3;
  /** Qi: lives per second; firefly: blink speed (rad/s scale). */
  rate: number;
  /** Fades out from this far from the camera (m). */
  far: number;
  window: [number, number];
  rank: number;
}

export interface MoteCluster extends LifeGroup {
  id: string;
  kind: "hold" | "water" | "blossom" | "pond";
  count: number;
}

function tint(c: { color: string; gain: number }): Vec3 {
  const l = hexToLinear(c.color);
  return [l[0] * c.gain, l[1] * c.gain, l[2] * c.gain];
}

function mixV(a: Vec3, b: Vec3, t: number): Vec3 {
  return [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
}

function boundsOf(points: readonly Mote[]): { center: Vec3; radius: number } {
  const c: Vec3 = [0, 0, 0];
  for (const m of points) for (let k = 0; k < 3; k++) c[k] += m.home[k] / points.length;
  let r = 0;
  // motePoint drifts up to (w, 0.6 w + rise, w) from home: at most about 2.02 w + rise away.
  for (const m of points) r = Math.max(r, Math.hypot(m.home[0] - c[0], m.home[1] - c[1], m.home[2] - c[2]) + 2.05 * m.wander + m.rise + m.radius);
  return { center: c, radius: r };
}

export interface MoteOptions {
  /** Twilight amount (0..1) at a frame: twilight holds get more motes, cooler qi. */
  twilight?: (frame: number) => number;
}

/** Ground height under a hold's view: its area's anchor, else a hotspot of that id, else below the camera. */
function groundY(meta: SectMeta, v: HoldView): number {
  const a = meta.areas.find((x) => x.id === v.id)?.anchor ?? meta.hotspots.find((x) => x.id === v.id)?.center;
  return a ? a[1] : v.p[1] - 15;
}

/** Every mote cluster: in front of each hold camera, rising off near waterfalls, over flowering trees and ponds. */
export function moteField(meta: SectMeta, views: readonly HoldView[], opts: MoteOptions = {}): { motes: Mote[]; clusters: MoteCluster[] } {
  const M = LIFE.motes;
  const motes: Mote[] = [];
  const clusters: MoteCluster[] = [];
  const tw = opts.twilight ?? (() => 0);
  const firefly = tint(M.firefly);
  const gold = tint(M.qiGold);
  const jade = tint(M.qiJade);
  const dusk = tint(M.qiTwilight);
  const cloudTop = meta.cloudSea.fogTopY - 20;
  let salt = 0;
  const add = (id: string, kind: MoteCluster["kind"], window: [number, number], list: Mote[]) => {
    if (list.length === 0) return;
    const b = boundsOf(list);
    clusters.push({ id, kind, window, count: list.length, center: b.center, radius: b.radius });
    motes.push(...list);
  };
  const viewOf = (area: string | null | undefined) => views.find((v) => v.id === area) ?? null;

  // In front of each hold camera, over the ground: fireflies and qi drifting in the foreground.
  views.forEach((v, vi) => {
    const k = tw(v.frame);
    const n = Math.round(M.perHold * (1 + M.twilightBoost * k));
    const floor = groundY(meta, v) + 0.6;
    const list: Mote[] = [];
    for (let i = 0; i < n; i++) {
      const h = (m: number) => hash01(vi * 4096 + i, 300 + m);
      const d = lerp(M.depth[0], M.depth[1], Math.pow(h(0), 0.8));
      const x = (h(1) * 2 - 1) * d * v.tanX * 1.05;
      const axisY = v.p[1] + v.fwd[1] * d;
      const yLo = Math.max(floor, axisY - d * v.tanY * 0.9);
      const yHi = Math.max(Math.min(axisY + d * v.tanY * 0.3, floor + M.maxHeight), yLo + 2);
      const kind: MoteKind = h(3) < 0.5 + 0.25 * k ? 1 : 0;
      // The top of its rise stays near eye level: a shorter rise where the view's bottom (yLo) is
      // close under the cap, and the home below the cap less the rise.
      const eyeCap = v.p[1] + M.overEye;
      const rise = kind === 1 ? Math.min(lerp(2, 5, h(8)), Math.max(eyeCap - yLo, 1)) : 0;
      const top = Math.max(Math.min(yHi, eyeCap - rise), yLo);
      // Gold and jade qi; toward twilight both cool toward a pale moonlit blue.
      const qi = h(4) < 0.5 ? mixV(gold, dusk, k * 0.6) : mixV(jade, dusk, k);
      list.push({
        home: [v.p[0] + v.fwdH[0] * d + v.right[0] * x, lerp(yLo, top, Math.pow(h(2), 1.4)), v.p[2] + v.fwdH[2] * d + v.right[2] * x],
        seed: h(5),
        radius: kind === 0 ? lerp(0.06, 0.1, h(6)) : lerp(0.07, 0.12, h(6)),
        kind,
        wander: kind === 0 ? lerp(0.6, 1.6, h(7)) : lerp(0.25, 0.7, h(7)),
        rise,
        color: kind === 0 ? firefly : qi,
        rate: kind === 1 ? 1 / lerp(9, 16, h(9)) : lerp(0.8, 1.6, h(9)),
        far: 260,
        window: v.window,
        rank: h(10),
      });
    }
    add(`hold:${v.id}`, "hold", v.window, list);
  });

  // Rising off the waterfalls near the flight (each fall is two twin sheets: one cluster per fall).
  const water = tint(M.water);
  const seen: Vec3[] = [];
  meta.waterfalls.forEach((w) => {
    if (w.kind !== "sheet" || !(w.nearestM <= M.waterfallReach)) return;
    const v = viewOf(w.chunk);
    if (!v) return;
    if (seen.some((s) => Math.hypot(s[0] - w.position[0], s[2] - w.position[2]) < 30)) return;
    const H = w.size[1];
    const lip = w.position[1] + H / 2;
    if (lip < cloudTop + 15) return;
    seen.push(w.position);
    const foot: Vec3 = w.foot ?? [w.position[0], w.position[1] - H / 2, w.position[2]];
    // A fall that lands on solid ground (a pool) gets its motes over the splash; one that drops into
    // the cloud layer gets them along its face, above the cloud.
    const grounded = foot[1] > cloudTop + 10;
    const yBot = grounded ? foot[1] + 0.4 : Math.max(foot[1], cloudTop + 12);
    const yTop = grounded ? Math.min(lip, foot[1] + Math.max(8, Math.min(0.45 * H, 20))) : lip;
    const reachR = Math.max(w.size[0], w.size[2]) * 0.5 + (grounded ? 5 : 3);
    // More for a taller column, and many more for a fall the flight passes close by.
    const n = Math.round(clamp((yTop - yBot) / 6 + 1200 / Math.max(w.nearestM, 30), 10, 40));
    const size = clamp(0.0035 * w.nearestM, 0.1, 0.6);
    const list: Mote[] = [];
    salt++;
    for (let i = 0; i < n; i++) {
      const h = (m: number) => hash01(salt * 997 + i, 500 + m);
      const y = lerp(yBot, yTop, grounded ? Math.pow(h(0), 1.5) : h(0));
      const along = clamp((lip - y) / Math.max(lip - foot[1], 1), 0, 1);
      const ang = h(1) * Math.PI * 2;
      const rr = reachR * lerp(0.35, 1, Math.sqrt(h(2)));
      const kind: MoteKind = h(3) < 0.75 ? 1 : 0;
      list.push({
        home: [lerp(w.position[0], foot[0], along) + Math.cos(ang) * rr, y, lerp(w.position[2], foot[2], along) + Math.sin(ang) * rr],
        seed: h(4),
        radius: size * lerp(0.8, 1.2, h(5)),
        kind,
        wander: lerp(0.4, 1.2, h(6)) * (1 + w.nearestM / 100),
        rise: kind === 1 ? lerp(3, 8, h(7)) : 0,
        color: kind === 1 ? water : jade,
        rate: kind === 1 ? 1 / lerp(8, 14, h(8)) : lerp(0.8, 1.4, h(8)),
        far: w.nearestM + 250,
        window: v.window,
        rank: h(9),
      });
    }
    add(`water:${w.name}`, "water", v.window, list);
  });

  // Hanging in the flowering trees' crowns, and fireflies low over the ponds.
  const blossom = tint(M.blossom);
  for (const hs of meta.hotspots) {
    const isTree = (LIFE.blossomIds as readonly string[]).includes(hs.id);
    const isPond = (LIFE.pondIds as readonly string[]).includes(hs.id);
    if (!isTree && !isPond) continue;
    const v = viewOf(hs.area ?? hs.chunk);
    if (!v) continue;
    salt++;
    const n = isTree ? M.perBlossom : M.perPond;
    const list: Mote[] = [];
    for (let i = 0; i < n; i++) {
      const h = (m: number) => hash01(salt * 997 + i, 700 + m);
      const ang = h(0) * Math.PI * 2;
      const r = Math.sqrt(h(1));
      const home: Vec3 = isTree
        ? [hs.center[0] + Math.cos(ang) * r * hs.size[0] * 0.55, hs.center[1] + (h(2) - 0.35) * hs.size[1] * 0.8, hs.center[2] + Math.sin(ang) * r * hs.size[2] * 0.55]
        : [hs.center[0] + Math.cos(ang) * r * hs.size[0] * 0.45, hs.center[1] + lerp(0.3, 2.5, h(2)), hs.center[2] + Math.sin(ang) * r * hs.size[2] * 0.45];
      const kind: MoteKind = isTree && h(3) < 0.5 ? 1 : 0;
      list.push({
        home,
        seed: h(4),
        radius: lerp(0.09, 0.14, h(5)),
        kind,
        wander: kind === 0 ? lerp(0.5, 1.2, h(6)) : lerp(0.2, 0.5, h(6)),
        rise: kind === 1 ? lerp(1.5, 3.5, h(7)) : 0,
        color: isTree ? blossom : firefly,
        rate: kind === 1 ? 1 / lerp(9, 15, h(8)) : lerp(0.8, 1.5, h(8)),
        far: 300,
        window: v.window,
        rank: h(9),
      });
    }
    add(`${isTree ? "blossom" : "pond"}:${hs.id}`, isTree ? "blossom" : "pond", v.window, list);
  }
  return { motes, clusters };
}

/**
 * A mote's position and brightness (0..1) at time t: fireflies wander and blink; qi motes rise
 * from home over each life, fading in and out. Mirrored in life.tsx's mote vertex shader.
 */
export function motePoint(m: Pick<Mote, "home" | "seed" | "kind" | "wander" | "rise" | "rate">, t: number): { p: Vec3; glow: number } {
  const s = m.seed;
  const w = m.wander;
  let y = m.home[1] + Math.sin(t * 0.17 + s * 23) * w * 0.6;
  let glow: number;
  if (m.kind === 1) {
    const c = fract(t * m.rate + s * 7.3);
    y += c * m.rise;
    glow = smoothstep(0, 0.2, c) * (1 - smoothstep(0.65, 1, c));
  } else {
    const b = 0.5 + 0.5 * Math.sin(t * m.rate + s * 60);
    glow = 0.25 + 0.75 * b * b * b;
  }
  return { p: [m.home[0] + Math.sin(t * 0.21 + s * 41) * w, y, m.home[2] + Math.cos(t * 0.19 + s * 31) * w], glow };
}

/** Floats per mote: (home, seed), (radius, kind, wander, rise), (colour, rate), (lo, hi, far, 0). */
export const MOTE_STRIDE = 16;

/** All motes in rank order (the first N are an even thinning of every cluster). */
export function packMotes(field: { motes: readonly Mote[]; clusters: readonly MoteCluster[] }): Packed {
  const order = field.motes.map((m, i) => i).sort((a, b) => field.motes[a].rank - field.motes[b].rank || a - b);
  const data = new Float32Array(order.length * MOTE_STRIDE);
  order.forEach((i, k) => {
    const m = field.motes[i];
    data.set(
      [
        m.home[0], m.home[1], m.home[2], m.seed,
        m.radius, m.kind, m.wander, m.rise,
        m.color[0], m.color[1], m.color[2], m.rate,
        m.window[0], m.window[1], m.far, 0,
      ],
      k * MOTE_STRIDE,
    );
  });
  return { data, count: order.length, stride: MOTE_STRIDE, groups: packGroups(field.clusters) };
}

// ---------------------------------------------------------------------------------------------
// Butterflies

export interface Butterfly {
  /** Centre of its loops (in the tree's crown). */
  center: Vec3;
  seed: number;
  /** Loop radii (m). */
  rx: number;
  ry: number;
  rz: number;
  /** Radians per second around the loop. */
  speed: number;
  color: Vec3;
  halfSpan: number;
  flapHz: number;
  window: [number, number];
}

export function butterflies(meta: SectMeta, views: readonly HoldView[]): { list: Butterfly[]; groups: LifeGroup[] } {
  const Bf = LIFE.butterflies;
  const list: Butterfly[] = [];
  const groups: LifeGroup[] = [];
  let ti = 0;
  for (const hs of meta.hotspots) {
    if (!(LIFE.blossomIds as readonly string[]).includes(hs.id)) continue;
    const v = views.find((x) => x.id === (hs.area ?? hs.chunk));
    if (!v) continue;
    ti++;
    const reach = Math.max(hs.size[0], hs.size[2]) * 0.5;
    for (let i = 0; i < Bf.perTree; i++) {
      const h = (m: number) => hash01(ti * 131 + i, 900 + m);
      list.push({
        center: [hs.center[0] + (h(0) - 0.5) * reach * 0.6, hs.center[1] + lerp(-0.1, 0.45, h(1)) * hs.size[1], hs.center[2] + (h(2) - 0.5) * reach * 0.6],
        seed: h(3),
        rx: reach * lerp(0.5, 1.0, h(4)),
        ry: lerp(0.6, 1.8, h(5)),
        rz: reach * lerp(0.5, 1.0, h(6)),
        speed: lerp(0.18, 0.35, h(7)) * (h(8) < 0.5 ? 1 : -1),
        color: hexToLinear(Bf.colors[Math.floor(h(9) * Bf.colors.length) % Bf.colors.length]),
        halfSpan: lerp(Bf.halfSpan[0], Bf.halfSpan[1], h(10)),
        flapHz: lerp(4.5, 6.5, h(11)),
        window: v.window,
      });
    }
    groups.push({ window: v.window, center: hs.center, radius: reach * 1.6 + hs.size[1] + 3 });
  }
  return { list, groups };
}

/** Where a butterfly is at t: lazy loops around its centre with a flutter. Mirrored in life.tsx. */
export function butterflyPoint(b: Pick<Butterfly, "center" | "seed" | "rx" | "ry" | "rz" | "speed" | "flapHz">, t: number): Vec3 {
  const a = t * b.speed + b.seed * 6.2831853;
  const s = b.seed;
  return [
    b.center[0] + Math.cos(a) * b.rx + Math.sin(a * 2.3 + s * 5) * b.rx * 0.3,
    b.center[1] + Math.sin(a * 1.7 + s * 3) * b.ry + Math.sin(t * b.flapHz * 3.1415927 + s * 20) * 0.12,
    b.center[2] + Math.sin(a) * b.rz + Math.cos(a * 1.9 + s * 2) * b.rz * 0.3,
  ];
}

/** Floats per butterfly: (centre, seed), (rx, ry, rz, speed), (colour, halfSpan), (lo, hi, flapHz, 0). */
export const BUTTERFLY_STRIDE = 16;

export function packButterflies(field: { list: readonly Butterfly[]; groups: readonly LifeGroup[] }): Packed {
  const data = new Float32Array(field.list.length * BUTTERFLY_STRIDE);
  field.list.forEach((b, i) => {
    data.set(
      [
        b.center[0], b.center[1], b.center[2], b.seed,
        b.rx, b.ry, b.rz, b.speed,
        b.color[0], b.color[1], b.color[2], b.halfSpan,
        b.window[0], b.window[1], b.flapHz, 0,
      ],
      i * BUTTERFLY_STRIDE,
    );
  });
  return { data, count: field.list.length, stride: BUTTERFLY_STRIDE, groups: packGroups(field.groups) };
}

// ---------------------------------------------------------------------------------------------

export interface LifeTables {
  birds: Packed;
  motes: Packed;
  butterflies: Packed;
  totals: LifeCounts;
}

/** The three spawn tables for a flight: deterministic from the camera path and meta.json. */
export function buildLifeTables(meta: SectMeta, camera: CameraData, twilight?: { from: string; to: string }): LifeTables {
  const views = holdViews(camera);
  const tw = twilight ? twilightOf(views, twilight.from, twilight.to) : undefined;
  const birds = packBirds(birdFlocks(views, { minY: meta.cloudSea.fogTopY + LIFE.birds.overCloud }));
  const motes = packMotes(moteField(meta, views, { twilight: tw }));
  const bf = packButterflies(butterflies(meta, views));
  return { birds, motes, butterflies: bf, totals: { birds: birds.count, motes: motes.count, butterflies: bf.count } };
}
