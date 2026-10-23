/**
 * Fast travel from the map (app/sect/experience/ink-travel.tsx), as in Black Myth: Wukong: ink
 * blooms out from the seal the visitor picked until it covers the screen, the camera jumps to the
 * place while it is covered and the place is drawn there until it has settled (every area its view
 * draws loaded and on the GPU, grass grown, reflections captured: lib/sect/settle.ts), then the ink
 * clears from the middle. With reduced motion: the same wait, under a plain fade.
 *
 * The timings and the ink's shapes. Plain numbers, so they are unit-tested; the component draws.
 */

/** Milliseconds of each step. */
export interface TravelTiming {
  /** The ink spreads until it covers the screen. */
  cover: number;
  /**
   * Covered at least this long (the place's name reads, and the travel feels deliberate), however
   * fast the place settles. The Loading seal shows only past it.
   */
  hold: number;
  /** The ink clears. */
  reveal: number;
  /**
   * The place never takes longer than this to settle (a very slow network): the ink clears anyway,
   * the camera already there, and what has not come yet streams in as it would after a scroll.
   */
  giveUp: number;
}

export function travelTiming(reducedMotion: boolean): TravelTiming {
  return reducedMotion ? { cover: 160, hold: 1200, reveal: 220, giveUp: 30000 } : { cover: 700, hold: 1200, reveal: 950, giveUp: 30000 };
}

/** A small seeded random generator (mulberry32): the same place always gets the same splash. */
export function seededRandom(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** A seed from a string (an area id). */
export function seedOf(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return h >>> 0;
}

/** A blot's rim never comes nearer its centre than this fraction of its widest reach. */
export const BLOT_SOLID = 0.6;

/** The soft halo round a blot reaches this far beyond its rim; a blot's sprite is the halo's size. */
export const BLOT_HALO = 1.12;

/** The fraction of a blot sprite's radius that is solid ink all the way round. */
export const BLOT_CORE = BLOT_SOLID / BLOT_HALO;

/**
 * The rim of an ink blot: `n` radii round the circle, as fractions of the sprite's radius, between
 * BLOT_SOLID and 1. A few slow lobes and some fine ragged detail, like ink soaking into paper.
 */
export function blotOutline(seed: number, n = 120): number[] {
  const rnd = seededRandom(seed);
  const waves = [
    { k: 2 + Math.floor(rnd() * 2), a: 0.09, p: rnd() * Math.PI * 2 },
    { k: 5 + Math.floor(rnd() * 3), a: 0.06, p: rnd() * Math.PI * 2 },
    { k: 11 + Math.floor(rnd() * 5), a: 0.035, p: rnd() * Math.PI * 2 },
    { k: 23 + Math.floor(rnd() * 9), a: 0.02, p: rnd() * Math.PI * 2 },
  ];
  const out: number[] = [];
  for (let i = 0; i < n; i++) {
    const t = (i / n) * Math.PI * 2;
    let r = 0.8;
    for (const w of waves) r += w.a * Math.sin(w.k * t + w.p);
    out.push(Math.min(1, Math.max(BLOT_SOLID, r)));
  }
  return out;
}

/** The distance from `at` to the screen's farthest corner. */
export function farCorner(at: readonly [number, number], view: { w: number; h: number }): number {
  const dx = Math.max(at[0], view.w - at[0]);
  const dy = Math.max(at[1], view.h - at[1]);
  return Math.hypot(dx, dy);
}

/** The sprite radius a blot centred at `at` needs (its solid core, with a margin) to cover the whole screen. */
export function coverRadius(at: readonly [number, number], view: { w: number; h: number }): number {
  return (farCorner(at, view) / BLOT_CORE) * 1.04;
}

export interface InkDrop {
  /** Centre, in screen pixels. */
  x: number;
  y: number;
  /** Final radius, in screen pixels. */
  r: number;
  /** When it starts and how long it grows, as fractions of the step. */
  start: number;
  span: number;
  /** Which blot shape it uses, and its turn (radians). */
  shape: number;
  turn: number;
  /**
   * How it grows: "bloom" starts small and gathers pace before it settles (the main blot, so the
   * spread from the seal reads), "splash" lands fast and slows (the drops round it).
   */
  curve: "bloom" | "splash";
}

/**
 * The ink of one travel: the main blot from `at` (the seal) that covers the screen, and `extra`
 * smaller drops that land around it a moment later, so it reads as ink and not as a growing circle.
 */
export function inkDrops(seed: number, at: readonly [number, number], view: { w: number; h: number }, extra = 3, shapes = 3): InkDrop[] {
  const rnd = seededRandom(seed);
  const main: InkDrop = { x: at[0], y: at[1], r: coverRadius(at, view), start: 0, span: 1, shape: 0, turn: rnd() * Math.PI * 2, curve: "bloom" };
  const out = [main];
  const span = Math.min(view.w, view.h);
  for (let i = 0; i < extra; i++) {
    const a = rnd() * Math.PI * 2;
    const d = span * (0.18 + rnd() * 0.32);
    out.push({
      x: Math.min(view.w, Math.max(0, at[0] + Math.cos(a) * d)),
      y: Math.min(view.h, Math.max(0, at[1] + Math.sin(a) * d)),
      r: span * (0.22 + rnd() * 0.22),
      start: 0.08 + rnd() * 0.22,
      span: 0.45 + rnd() * 0.2,
      shape: (i + 1) % Math.max(1, shapes),
      turn: rnd() * Math.PI * 2,
      curve: "splash",
    });
  }
  return out;
}

/** How far a drop has grown at time `t` (0..1 of its step), by its curve (InkDrop.curve). */
export function dropGrowth(d: Pick<InkDrop, "start" | "span"> & { curve?: InkDrop["curve"] }, t: number): number {
  const k = Math.min(1, Math.max(0, (t - d.start) / Math.max(1e-6, d.span)));
  return d.curve === "bloom" ? k * k * (3 - 2 * k) : 1 - (1 - k) ** 3;
}

export function easeInOutCubic(t: number): number {
  const k = Math.min(1, Math.max(0, t));
  return k < 0.5 ? 4 * k * k * k : 1 - (-2 * k + 2) ** 3 / 2;
}
