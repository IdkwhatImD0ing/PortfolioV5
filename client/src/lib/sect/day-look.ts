/**
 * The look by the time of day in Pacific time. The owner lives on Pacific time, so the page shows
 * the hour it is where he is, whoever visits: moonlit night, an ink-wash dawn, a clear day, golden
 * hour, then today's dusk (the bake as it is) and back to night.
 *
 * Here: the Pacific clock, sunrise and sunset for a spot on the coast (the NOAA solar formulas), the
 * schedule of looks through the day, and how two looks blend. experience/look-switch.ts applies the
 * result once, when the page loads: many levers are built into shaders, so the look does not move
 * while the page is open.
 *
 * A preview, development only (?look=auto, ?time=, ?date=: runtime.ts parseSectParams). The page's
 * own look is the journey (journey.ts: the day along the flight). Setting FOLLOW_PACIFIC_CLOCK to
 * true makes a page with no option follow the clock only while journey.ts JOURNEY_ON is off.
 *
 * Pure maths and data (no three.js, no DOM), so it is testable.
 */
import { hexToLinear } from "./glsl";
import { LOOKS, readLever, type LeverValue, type LookPatch, type LookTarget } from "./looks";
import type { CivilDate, DayOptions, LookId, SectParams } from "./runtime";
import type { Vec3 } from "./types";

/**
 * Off: a page with no look option shows the journey (or today's dusk with the journey off). On, with
 * the journey off: it shows the look for the hour it is in Pacific time, for every visitor
 * (production included).
 */
export const FOLLOW_PACIFIC_CLOCK = false;

export const PACIFIC_TIME_ZONE = "America/Los_Angeles";

/**
 * Where the sun is worked out: a stand-in for "where the owner is", a spot on the San Francisco
 * Bay. Degrees, north and east positive.
 */
export const SUN_LATITUDE = 37.6;
export const SUN_LONGITUDE = -122.2;

// ---------------------------------------------------------------------------------------------
// The Pacific clock

let formatter: Intl.DateTimeFormat | null = null;

function pacificFormat(): Intl.DateTimeFormat {
  formatter ??= new Intl.DateTimeFormat("en-US", {
    timeZone: PACIFIC_TIME_ZONE,
    hourCycle: "h23",
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
  });
  return formatter;
}

/** The Pacific date at an instant, and the minutes since its midnight (seconds as a fraction). */
export function pacificParts(at: Date): CivilDate & { minutes: number } {
  const parts = pacificFormat().formatToParts(at);
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
  // Some engines write midnight as 24 even with h23.
  const hour = get("hour") % 24;
  return { year: get("year"), month: get("month"), day: get("day"), minutes: hour * 60 + get("minute") + get("second") / 60 };
}

/** Minutes since midnight in Pacific time at an instant (daylight saving included). */
export function pacificMinutes(at: Date): number {
  return pacificParts(at).minutes;
}

/** Minutes Pacific time is ahead of UTC at an instant: -480 in winter, -420 in summer. */
export function pacificOffset(at: Date): number {
  const p = pacificParts(at);
  const wall = Date.UTC(p.year, p.month - 1, p.day) + p.minutes * 60000;
  return Math.round((wall - at.getTime()) / 60000);
}

// ---------------------------------------------------------------------------------------------
// Sunrise and sunset (NOAA's solar calculator: Meeus, "Astronomical Algorithms")

const DEG = Math.PI / 180;

/** The Julian day at 0h UT of a calendar date. */
export function julianDay(d: CivilDate): number {
  let y = d.year;
  let m = d.month;
  if (m <= 2) {
    y -= 1;
    m += 12;
  }
  const a = Math.floor(y / 100);
  const b = 2 - a + Math.floor(a / 4);
  return Math.floor(365.25 * (y + 4716)) + Math.floor(30.6001 * (m + 1)) + d.day + b - 1524.5;
}

/** The sun's declination (degrees) and the equation of time (minutes) at a Julian day. */
export function solarPosition(jd: number): { declination: number; equationOfTime: number } {
  const t = (jd - 2451545) / 36525;
  const l0 = (((280.46646 + t * (36000.76983 + t * 0.0003032)) % 360) + 360) % 360;
  const m = 357.52911 + t * (35999.05029 - 0.0001537 * t);
  const e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t);
  const c =
    Math.sin(m * DEG) * (1.914602 - t * (0.004817 + 0.000014 * t)) + Math.sin(2 * m * DEG) * (0.019993 - 0.000101 * t) + Math.sin(3 * m * DEG) * 0.000289;
  const omega = 125.04 - 1934.136 * t;
  const lambda = l0 + c - 0.00569 - 0.00478 * Math.sin(omega * DEG);
  const seconds = 21.448 - t * (46.815 + t * (0.00059 - t * 0.001813));
  const eps = 23 + (26 + seconds / 60) / 60 + 0.00256 * Math.cos(omega * DEG);
  const declination = Math.asin(Math.sin(eps * DEG) * Math.sin(lambda * DEG)) / DEG;
  const y = Math.tan((eps / 2) * DEG) ** 2;
  const eq =
    y * Math.sin(2 * l0 * DEG) -
    2 * e * Math.sin(m * DEG) +
    4 * e * y * Math.sin(m * DEG) * Math.cos(2 * l0 * DEG) -
    0.5 * y * y * Math.sin(4 * l0 * DEG) -
    1.25 * e * e * Math.sin(2 * m * DEG);
  return { declination, equationOfTime: (4 * eq) / DEG };
}

/** Minutes after 0h UT of the date when the sun's top edge crosses the horizon (refraction included). */
function riseSetUtc(rise: boolean, jd0: number, lat: number, lon: number): number | null {
  let minutes = 720 - 4 * lon;
  // Twice: the sun's place at the event itself, not at noon.
  for (let i = 0; i < 2; i++) {
    const { declination, equationOfTime } = solarPosition(jd0 + minutes / 1440);
    const cosH = Math.cos(90.833 * DEG) / (Math.cos(lat * DEG) * Math.cos(declination * DEG)) - Math.tan(lat * DEG) * Math.tan(declination * DEG);
    if (cosH > 1 || cosH < -1) return null;
    const h = Math.acos(cosH) / DEG;
    minutes = 720 - 4 * (lon + (rise ? h : -h)) - equationOfTime;
  }
  return minutes;
}

/**
 * Sunrise and sunset on a date at the spot (SUN_LATITUDE, SUN_LONGITUDE), in minutes since that
 * day's midnight in Pacific time. A day with no sunrise (not on this coast) falls back to 6:00 and 18:00.
 */
export function sunTimes(d: CivilDate, lat = SUN_LATITUDE, lon = SUN_LONGITUDE): { sunrise: number; sunset: number } {
  const jd0 = julianDay(d);
  const midnightUtc = Date.UTC(d.year, d.month - 1, d.day);
  const local = (utc: number | null, fallback: number) =>
    utc === null ? fallback : utc + pacificOffset(new Date(midnightUtc + utc * 60000));
  return { sunrise: local(riseSetUtc(true, jd0, lat, lon), 360), sunset: local(riseSetUtc(false, jd0, lat, lon), 1080) };
}

// ---------------------------------------------------------------------------------------------
// The schedule

/** A look the day can show: one of the looks, or today's dusk (the page with no look). */
export type DayLookKey = LookId | "dusk";

/** A point in the day: minutes from sunrise ("R") or sunset ("S"), and the look shown there. */
export interface DayKey {
  from: "R" | "S";
  at: number;
  look: DayLookKey;
}

/**
 * The day, as points in time. Between two neighbours the look blends linearly; two points with the
 * same look hold it. After the last the night runs on to the next morning's first. Retune here.
 * - night: moon from S+75 to R-60;
 * - dawn: moon to ink by R+15, ink to R+90;
 * - morning: ink to day by R+150, day to S-120;
 * - evening: day to gold by S-75, gold to S-15, gold to today's dusk by S, dusk to S+30;
 * - nightfall: dusk to moon by S+75.
 */
export const DAY_SCHEDULE: readonly DayKey[] = [
  { from: "R", at: -60, look: "moon" },
  { from: "R", at: 15, look: "ink" },
  { from: "R", at: 90, look: "ink" },
  { from: "R", at: 150, look: "day" },
  { from: "S", at: -120, look: "day" },
  { from: "S", at: -75, look: "gold" },
  { from: "S", at: -15, look: "gold" },
  { from: "S", at: 0, look: "dusk" },
  { from: "S", at: 30, look: "dusk" },
  { from: "S", at: 75, look: "moon" },
];

/** Two looks and how far from the first to the second (0 = the first alone, 1 = the second alone). */
export interface DayMix {
  from: DayLookKey;
  to: DayLookKey;
  weight: number;
}

/**
 * The look at `minutes` since midnight on a day with that sunrise and sunset (minutes since
 * midnight too). A point that would come before the one listed ahead of it is held at that one, so
 * a very short day still runs in order.
 */
export function dayMix(minutes: number, sunrise: number, sunset: number, schedule: readonly DayKey[] = DAY_SCHEDULE): DayMix {
  if (schedule.length === 0) return { from: "dusk", to: "dusk", weight: 0 };
  const times: number[] = [];
  for (const k of schedule) times.push(Math.max((k.from === "R" ? sunrise : sunset) + k.at, times.length ? times[times.length - 1] : -Infinity));
  const n = schedule.length;
  const m = ((minutes % 1440) + 1440) % 1440;
  // The segment m falls in: between key i and key i + 1, the last wrapping to the first a day later.
  let i = n - 1;
  for (let j = 0; j < n; j++) if (times[j] <= m) i = j;
  let t0 = times[i];
  let t1 = i + 1 < n ? times[i + 1] : times[0] + 1440;
  if (m < times[0]) {
    t0 = times[n - 1] - 1440;
    t1 = times[0];
  }
  const a = schedule[i].look;
  const b = schedule[(i + 1) % n].look;
  const weight = t1 > t0 ? Math.min(Math.max((m - t0) / (t1 - t0), 0), 1) : 1;
  if (a === b || weight <= 0) return { from: a, to: a, weight: 0 };
  if (weight >= 1) return { from: b, to: b, weight: 0 };
  return { from: a, to: b, weight };
}

/** What the clock (or the options in its place) says now. */
export interface DayState extends DayMix {
  date: CivilDate;
  /** Minutes since midnight, Pacific. */
  minutes: number;
  sunrise: number;
  sunset: number;
}

/** The look for an instant in Pacific time, or for the options' time and date in its place. */
export function pacificDay(now: Date, o: DayOptions = {}, schedule: readonly DayKey[] = DAY_SCHEDULE): DayState {
  const p = pacificParts(now);
  const date = o.date ?? { year: p.year, month: p.month, day: p.day };
  const minutes = o.time ?? p.minutes;
  const { sunrise, sunset } = sunTimes(date);
  return { ...dayMix(minutes, sunrise, sunset, schedule), date, minutes, sunrise, sunset };
}

/** "HH:MM" (24 hour) for minutes since midnight. */
export function clockText(minutes: number): string {
  const m = ((Math.round(minutes) % 1440) + 1440) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

/** "day", or "day 44% / gold 56%" while two blend. */
export function mixText(mix: DayMix): string {
  if (mix.weight <= 0 || mix.from === mix.to) return mix.from;
  const b = Math.round(mix.weight * 100);
  return `${mix.from} ${100 - b}% / ${mix.to} ${b}%`;
}

/** The look's overrides: null for today's dusk (it has none). */
export function dayPatch(key: DayLookKey): LookPatch | null {
  return key === "dusk" ? null : LOOKS[key].patch;
}

// ---------------------------------------------------------------------------------------------
// Which look the page shows

export type LookChoice = { kind: "look"; id: LookId } | { kind: "clock"; options: DayOptions } | null;

/**
 * A forced look (?look=<id>) first, then the clock's options (?look=auto, ?time=, ?date=), then the
 * clock itself if `follow` (FOLLOW_PACIFIC_CLOCK), else none: today's dusk.
 */
export function chooseLook(p: Pick<SectParams, "look" | "day">, follow: boolean = FOLLOW_PACIFIC_CLOCK): LookChoice {
  if (p.look) return { kind: "look", id: p.look };
  if (p.day) return { kind: "clock", options: p.day };
  return follow ? { kind: "clock", options: {} } : null;
}

// ---------------------------------------------------------------------------------------------
// Blending two looks

type Levers = Readonly<Record<string, LeverValue>>;

/**
 * Levers that do nothing while a gate lever is 0: the frame grade at amount 0 (today's dusk has
 * none). A look whose gate is 0 takes the other look's values for them, so only the gate fades.
 * Otherwise a grade fading in would also bend its numbers toward doing nothing, and half-way it
 * would show about a quarter of itself.
 */
const GATES: readonly { target: LookTarget; gate: string; group: string }[] = [{ target: "frame", gate: "grade.amount", group: "grade." }];

/**
 * Levers whose blend leans to the lower value, by this power of the higher one's weight: stars come
 * out late and go early, so a pale sky never shows them (at half-way, an eighth of them).
 */
const LEAN_LOW: Readonly<Record<string, number>> = { "frame:stars": 3 };

/** #rrggbb from linear-sRGB floats (clamped). */
export function linearToHex(c: Vec3): string {
  return `#${c
    .map((v) => {
      const x = Math.min(Math.max(v, 0), 1);
      const s = x <= 0.0031308 ? x * 12.92 : 1.055 * Math.pow(x, 1 / 2.4) - 0.055;
      return Math.round(s * 255)
        .toString(16)
        .padStart(2, "0");
    })
    .join("")}`;
}

const HEX = /^#[0-9a-f]{6}$/i;

/**
 * One lever between two values: numbers and lists of numbers linearly, colours in linear light; any
 * other string switches at half-way. `lean`: LEAN_LOW's power for this lever.
 */
export function blendValue(a: LeverValue, b: LeverValue, w: number, lean?: number): LeverValue {
  if (typeof a === "number" && typeof b === "number") {
    if (lean === undefined) return a + (b - a) * w;
    const hiWeight = b >= a ? w : 1 - w;
    return Math.min(a, b) + Math.abs(b - a) * Math.pow(hiWeight, lean);
  }
  if (Array.isArray(a) && Array.isArray(b) && a.length === b.length) return a.map((x: number, i: number) => x + ((b[i] as number) - x) * w);
  if (typeof a === "string" && typeof b === "string" && HEX.test(a) && HEX.test(b)) {
    const x = hexToLinear(a);
    const y = hexToLinear(b);
    return linearToHex([x[0] + (y[0] - x[0]) * w, x[1] + (y[1] - x[1]) * w, x[2] + (y[2] - x[2]) * w]);
  }
  return w < 0.5 ? a : b;
}

/**
 * Two looks' levers on one table, `w` of the way from `a` to `b` (undefined: the look changes nothing
 * there). A lever only one look names takes today's value from `base`, the table as the page has it
 * before any look. A weight of 0 or 1 gives that look's own levers, exactly.
 */
export function blendLevers(target: LookTarget, a: Levers | undefined, b: Levers | undefined, w: number, base: unknown): Record<string, LeverValue> {
  if (!(w > 0)) return { ...(a ?? {}) };
  if (w >= 1) return { ...(b ?? {}) };
  const keys = [...new Set([...Object.keys(a ?? {}), ...Object.keys(b ?? {})])];
  const va: Record<string, LeverValue> = {};
  const vb: Record<string, LeverValue> = {};
  for (const k of keys) {
    const x = a?.[k] ?? readLever(base, k);
    const y = b?.[k] ?? readLever(base, k);
    // A lever the table does not have: the look that names it keeps it (writeLevers reports it).
    va[k] = (x ?? y) as LeverValue;
    vb[k] = (y ?? x) as LeverValue;
  }
  for (const g of GATES) {
    if (g.target !== target) continue;
    const ga = va[g.gate] ?? readLever(base, g.gate);
    const gb = vb[g.gate] ?? readLever(base, g.gate);
    const group = keys.filter((k) => k !== g.gate && k.startsWith(g.group));
    if (ga === 0 && gb !== 0) for (const k of group) va[k] = vb[k];
    else if (gb === 0 && ga !== 0) for (const k of group) vb[k] = va[k];
  }
  const out: Record<string, LeverValue> = {};
  for (const k of keys) out[k] = blendValue(va[k], vb[k], w, LEAN_LOW[`${target}:${k}`]);
  return out;
}

/** Two looks blended on every table but meta (that one is the scene's, copied when it loads). */
export function blendPatches(a: LookPatch | null, b: LookPatch | null, w: number, bases: Readonly<Record<Exclude<LookTarget, "meta">, object>>): LookPatch {
  const out: LookPatch = {};
  for (const t of Object.keys(bases) as Exclude<LookTarget, "meta">[]) {
    const levers = blendLevers(t, a?.[t], b?.[t], w, bases[t]);
    if (Object.keys(levers).length > 0) out[t] = levers;
  }
  return out;
}
