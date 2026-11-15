/**
 * The look switch (lib/sect/looks.ts holds the looks, lib/sect/day-look.ts the time of day,
 * lib/sect/journey.ts the day along the flight).
 *
 * What the page shows (journey.ts choosePageLook): ?look=<id> forces one look; ?look=auto,
 * ?time=HH:MM and ?date=YYYY-MM-DD show the look for that hour in Pacific time; ?look=dusk shows
 * today's dusk and ?look=journey the journey (all development only). With none of them: the
 * journey while journey.ts JOURNEY_ON is on, else today's dusk (or the Pacific clock while
 * day-look.ts FOLLOW_PACIFIC_CLOCK is on).
 *
 * A forced look or the clock's: its overrides go into the tables the page reads (SECT_LOOK,
 * LIVE_LOOK, LUX, ATMOS, RANGE_LOOK, FRAME_LOOK) when this module loads. Shaders take those
 * numbers when they are built, so this module must load before any of them: sect-experience.tsx
 * imports it first of all. It is picked once, at load.
 *
 * The journey writes nothing into the tables: look-now.ts blends its own copies at each camera
 * frame and the page sets uniforms from them. Today's dusk writes nothing either.
 */
import { blendLevers, clockText, dayPatch, mixText, pacificDay } from "@/lib/sect/day-look";
import { choosePageLook } from "@/lib/sect/journey";
import { LIVE_LOOK } from "@/lib/sect/live";
import { SECT_LOOK } from "@/lib/sect/look";
import { FRAME_LOOK, LOOK_TARGETS, LOOKS, withLevers, writeLevers, type LookPatch, type LookTarget } from "@/lib/sect/looks";
import { LUX } from "@/lib/sect/lux";
import { ATMOS } from "@/lib/sect/post";
import { RANGE_LOOK } from "@/lib/sect/range-look";
import { parseSectParams } from "@/lib/sect/runtime";
import type { SectMeta } from "@/lib/sect/types";

/** The tables a look writes into, by target (meta is not one: it is copied, see lookMeta). */
export const LOOK_TABLES: Record<Exclude<LookTarget, "meta">, object> = {
  sect: SECT_LOOK,
  live: LIVE_LOOK,
  lux: LUX,
  atmos: ATMOS,
  range: RANGE_LOOK,
  frame: FRAME_LOOK,
};

/** The look the page shows: `weight` of the way from one look to another (null: today's dusk). */
interface ActiveLook {
  from: LookPatch | null;
  to: LookPatch | null;
  weight: number;
  /** For the console: what it is, and for the clock what time and day it took. */
  label: string;
}

/** How the page picks its look: today's dusk, one look (forced or by the clock) for the whole flight, or the journey. */
export type LookMode = "dusk" | "fixed" | "journey";

function pickMode(): { mode: LookMode; look: ActiveLook | null } {
  if (typeof window === "undefined") return { mode: "dusk", look: null };
  const choice = choosePageLook(parseSectParams(window.location.search));
  if (!choice) return { mode: "dusk", look: null };
  if (choice.kind === "journey") return { mode: "journey", look: null };
  if (choice.kind === "look") {
    const l = LOOKS[choice.id];
    return { mode: "fixed", look: { from: l.patch, to: l.patch, weight: 0, label: `"${l.id}": ${l.note}` } };
  }
  const d = pacificDay(new Date(), choice.options);
  const day = `${d.date.year}-${String(d.date.month).padStart(2, "0")}-${String(d.date.day).padStart(2, "0")}`;
  return {
    mode: "fixed",
    look: {
      from: dayPatch(d.from),
      to: dayPatch(d.to),
      weight: d.weight,
      label: `"${mixText(d)}" at ${clockText(d.minutes)} Pacific on ${day} (sunrise ${clockText(d.sunrise)}, sunset ${clockText(d.sunset)})`,
    },
  };
}

/**
 * The tables as the page has them before any look, kept across hot reloads: a reload of this
 * module runs it again on tables it already wrote, and a blend must start from today's values.
 */
const PRISTINE: WeakMap<object, object> = ((globalThis as unknown as { __sectLookBase?: WeakMap<object, object> }).__sectLookBase ??= new WeakMap());

/** A table as it was before any look wrote into it (a copy taken the first time it is asked for). */
export function pristine(table: object): object {
  let p = PRISTINE.get(table);
  if (!p) {
    p = structuredClone(table);
    PRISTINE.set(table, p);
  }
  return p;
}

/** Whether to say what is showing (the console and window.__sectLook): in development, or with ?debug=1. */
export const LOOK_READOUT =
  typeof window !== "undefined" && (process.env.NODE_ENV !== "production" || /[?&]debug=1/.test(window.location.search));

const PICKED = pickMode();

/** How the page picks its look (fixed when ?look= or the clock picked one). */
export const LOOK_MODE: LookMode = PICKED.mode;

/** The one look the page shows, or null (today's dusk, or the journey). */
export const ACTIVE_LOOK: ActiveLook | null = PICKED.look;

if (ACTIVE_LOOK) {
  const { from, to, weight } = ACTIVE_LOOK;
  for (const target of LOOK_TARGETS) {
    if (target === "meta") continue;
    const table = LOOK_TABLES[target];
    const levers = blendLevers(target, from?.[target], to?.[target], weight, pristine(table));
    if (Object.keys(levers).length > 0) writeLevers(table, levers);
  }
  if (LOOK_READOUT) {
    console.info(`[sect] look ${ACTIVE_LOOK.label}`);
    (window as unknown as { __sectLook?: string }).__sectLook = ACTIVE_LOOK.label;
  }
} else if (LOOK_MODE === "journey") {
  // Copies of today's tables for the journey to blend from (taken before anything could write them).
  for (const target of LOOK_TARGETS) if (target !== "meta") pristine(LOOK_TABLES[target]);
  if (LOOK_READOUT) {
    console.info("[sect] look: the journey (the day along the flight)");
    (window as unknown as { __sectLook?: string }).__sectLook = "journey";
  }
}

/** The scene's meta with a fixed look's own overrides (the sun's and the moon's colour, the vignette). */
export function lookMeta(meta: SectMeta): SectMeta {
  if (!ACTIVE_LOOK) return meta;
  const { from, to, weight } = ACTIVE_LOOK;
  return withLevers(meta, blendLevers("meta", from?.meta, to?.meta, weight, meta));
}
