/**
 * The journey: the day runs along the flight. Sunrise at the gate, a sunlit misty morning at the
 * Heart-Mirror, the clear day through the middle stops, late afternoon at the library, golden hour
 * at the steles, sunset at the jade slip, the last light at the formation, blue hour at the abode
 * and night under the moon at the summit (sun into moon: the sect's name).
 *
 * Here: the arc (JOURNEY, one table keyed by the stops' holds), the looks' weights at a camera frame
 * (smooth between two neighbouring stops), and the looks blended by those weights, lever by lever.
 * Only run-time levers are blended (RUNTIME_LEVERS): the page sets them every frame without building
 * a shader (experience/look-now.ts). The few others (FIXED_LEVERS) stay at today's values.
 *
 * Pure data and maths (no three.js, no DOM), so it is testable.
 */
import { hexToLinear } from "./glsl";
import { FOLLOW_PACIFIC_CLOCK, linearToHex, type DayLookKey, type LookChoice } from "./day-look";
import { FRAME_LOOK, LOOKS, readLever, type LeverValue, type LookTarget } from "./looks";
import { RANGE_HAZE_HOLDS } from "./range-look";
import type { SectParams } from "./runtime";
import type { Vec3 } from "./types";

/**
 * On: the journey is the page's look, for every visitor and every tier. Off: the page is exactly
 * today's dusk (no lever moves, no uniform switch is set, no extra shader term is built).
 */
export const JOURNEY_ON = true;

/** The looks the arc can use: the four looks and today's dusk (the page with no look). */
export const JOURNEY_LOOKS: readonly DayLookKey[] = ["gold", "day", "ink", "moon", "dusk"];

/** A stop's share of each look (any scale: they are normalised). */
export type JourneyMix = Partial<Record<DayLookKey, number>>;

export interface JourneyKey {
  /** The stop's hold id. */
  stop: string;
  /** Its hold frame. The page takes the camera's own frame for the stop when it has one. */
  frame: number;
  mix: JourneyMix;
}

/**
 * The arc. Retune here. Before the gate's frame the look is the gate's, after the summit's the
 * summit's; between two stops it blends smoothly by frame.
 */
export const JOURNEY: readonly JourneyKey[] = [
  // Sunrise: the first thing a visitor sees.
  { stop: "gate", frame: 93, mix: { gold: 1 } },
  // A soft sunlit morning mist, colour kept. (Ink and day half and half was a flat grey.)
  { stop: "mirror", frame: 217, mix: { gold: 0.5, day: 0.35, ink: 0.15 } },
  // The day keeps moving: late morning with a little haze left, noon, early afternoon warming.
  { stop: "forge", frame: 352, mix: { day: 0.85, ink: 0.15 } },
  { stop: "arena", frame: 516, mix: { day: 1 } },
  // (A quarter of gold at the mission turned its blue sky grey white; a tenth keeps it blue.)
  { stop: "mission", frame: 619, mix: { day: 0.9, gold: 0.1 } },
  // Late afternoon.
  { stop: "library", frame: 772, mix: { day: 0.5, gold: 0.5 } },
  { stop: "steles", frame: 974, mix: { gold: 1 } },
  // Sunset.
  { stop: "scroll", frame: 1103, mix: { gold: 0.5, dusk: 0.5 } },
  // From here the moon's share only grows, so no stop looks earlier than the one before. (Today's
  // dusk alone at the formation was paler and brighter than the sunset before it.)
  { stop: "formation", frame: 1208, mix: { dusk: 0.7, moon: 0.3 } },
  // Blue hour.
  { stop: "abode", frame: 1380, mix: { dusk: 0.4, moon: 0.6 } },
  { stop: "summit", frame: 1647, mix: { moon: 1 } },
];

export type JourneyWeights = Record<DayLookKey, number>;

function zero(): JourneyWeights {
  return { gold: 0, day: 0, ink: 0, moon: 0, dusk: 0 };
}

/** A mix as weights that sum to 1 (an empty mix is today's dusk). */
export function normalMix(mix: JourneyMix): JourneyWeights {
  const w = zero();
  let sum = 0;
  for (const id of JOURNEY_LOOKS) sum += Math.max(mix[id] ?? 0, 0);
  if (!(sum > 0)) {
    w.dusk = 1;
    return w;
  }
  for (const id of JOURNEY_LOOKS) w[id] = Math.max(mix[id] ?? 0, 0) / sum;
  return w;
}

/** The arc with each stop at the camera's own hold frame for it (when it has one), in frame order. */
export function journeyKeys(holds: readonly { id: string; frame: number }[], arc: readonly JourneyKey[] = JOURNEY): JourneyKey[] {
  return arc.map((k) => ({ ...k, frame: holds.find((h) => h.id === k.stop)?.frame ?? k.frame })).sort((a, b) => a.frame - b.frame);
}

function smoothstep(a: number, b: number, x: number): number {
  const t = Math.min(Math.max((x - a) / Math.max(b - a, 1e-6), 0), 1);
  return t * t * (3 - 2 * t);
}

/**
 * The looks' weights at a camera frame (they sum to 1): a stop's own mix at its frame, smooth
 * between two neighbours (the same easing as the haze per stop), the first stop's before it and the
 * last stop's after it.
 */
export function journeyWeights(frame: number, keys: readonly JourneyKey[] = JOURNEY): JourneyWeights {
  if (keys.length === 0) return normalMix({});
  if (!(frame > keys[0].frame)) return normalMix(keys[0].mix);
  for (let i = 1; i < keys.length; i++) {
    if (frame <= keys[i].frame) {
      const t = smoothstep(keys[i - 1].frame, keys[i].frame, frame);
      const a = normalMix(keys[i - 1].mix);
      const b = normalMix(keys[i].mix);
      const w = zero();
      for (const id of JOURNEY_LOOKS) w[id] = t >= 1 ? b[id] : t <= 0 ? a[id] : a[id] + (b[id] - a[id]) * t;
      return w;
    }
  }
  return normalMix(keys[keys.length - 1].mix);
}

/** "gold 50% / dusk 50%" (the looks with any weight, largest first). */
export function weightsText(w: JourneyWeights): string {
  return JOURNEY_LOOKS.filter((id) => w[id] > 0.005)
    .sort((a, b) => w[b] - w[a])
    .map((id) => (w[id] > 0.995 ? id : `${id} ${Math.round(w[id] * 100)}%`))
    .join(" / ");
}

// ---------------------------------------------------------------------------------------------
// Which levers move

/** Every stop's haze lever (range-look.ts RANGE_LOOK.haze.holds). */
const HAZE_HOLDS = Object.keys(RANGE_HAZE_HOLDS).map((id) => `haze.holds.${id}`);

/**
 * The levers the journey changes as the camera moves: each is read every frame where it is used
 * (a uniform, a material's colour, a post effect's setting, or a value the page reads each frame).
 * The page's look tables are never written by the journey (experience/look-now.ts keeps its own
 * copies), so nothing built from them later sees a moved value.
 */
export const RUNTIME_LEVERS: Readonly<Record<LookTarget, readonly string[]>> = {
  sect: [
    // The haze: fog colour and density (three's fog uniforms and the shared uSectLook array), its
    // colour toward and away from the sun, its blue fade, the valley mist.
    "haze.color",
    "haze.sunColor",
    "haze.densityScale",
    "haze.coolColor",
    "haze.coolMix",
    "haze.extinction",
    "haze.desaturate",
    "haze.aerialDepth",
    "haze.clear",
    "mist.density",
    "mist.falloff",
    "mist.start",
    // The sky dome's and the reflections' uniforms.
    "sky.zenith",
    "sky.mid",
    "sky.horizon",
    "sky.sunHorizon",
    "sky.gradeMix",
    "sky.haze",
    "skyClouds.sunLit",
    "skyClouds.lit",
    "skyClouds.shade",
    "skyClouds.rim",
    "skyClouds.coverage",
    // The cloud puffs' material.
    "puffs.lit",
    "puffs.shade",
    "puffs.rim",
    "puffs.opacity",
    // The baked surfaces' grade (uSectLook).
    "grade.exposure",
    "grade.contrast",
    "grade.shadowTint",
    "grade.highlightTint",
    "grade.split",
    "grade.splitShadow",
    "grade.saturation",
    "grade.greenTame",
    "grade.shoulder",
    "cloudSeaColor",
    "cloudFogColor",
    "water.skyLow",
    "water.skyHigh",
    "sunHaze.color",
    "sunHaze.strength",
    "trees.rim",
    "trees.rimStrength",
    "surfaces.mountains",
    "surfaces.ground",
    "moonHalo.day",
    "moonHalo.twilight",
    // The twilight's end colours: the page blends the sky toward them by frame (look.ts
    // twilightAmount), now on top of the journey's own colours.
    "twilight.zenith",
    "twilight.mid",
    "twilight.horizon",
    "twilight.sunHorizon",
    "twilight.haze",
    "twilight.cloudSea",
    "twilight.cloudSunLit",
    "twilight.cloudLit",
    "twilight.cloudShade",
    "twilight.cloudRim",
    "twilight.coverage",
  ],
  // The live light's uniforms (live.tsx sets them again when these change).
  live: ["sunGain", "keyGain", "ambientGain", "saturation", "specular"],
  // Post effects' uniforms.
  lux: ["shafts.color", "shafts.gain", "shafts.air", "shafts.dim", "shafts.shade", "ao.strength", "finish.grain", "finish.toe"],
  atmos: ["bloom.intensity", "cloudShadow.strength"],
  // Read each frame by hazeScaleAt.
  range: HAZE_HOLDS,
  // The frame grade (uSectLook on every tier), the stars and the sky's sun (the dome's uniforms), and
  // how much the two night-baked stops show their own light (materials.ts SECT_PULL, night-bake.ts).
  frame: [...Object.keys(FRAME_LOOK.grade).map((k) => `grade.${k}`), "stars", "skySun", "cloudSeaShade", "nightBake"],
  meta: ["sun.color", "moon.color", "vignette"],
};

/**
 * Levers a look sets that the journey leaves at today's value: each is built into a shader or into
 * geometry when the page loads, and the look reads well enough without it.
 * - puffs.areaThin: how much the puffs thin near the stops, packed into their instance data.
 * - shafts.dimMax: a constant of the shafts' shader.
 * - ao.tint: a constant of the contact shade's shader.
 */
export const FIXED_LEVERS: Readonly<Partial<Record<LookTarget, readonly string[]>>> = {
  sect: ["puffs.areaThin"],
  lux: ["shafts.dimMax", "ao.tint"],
};

/** True when the journey may move this lever. */
export function isRuntimeLever(target: LookTarget, path: string): boolean {
  return RUNTIME_LEVERS[target].includes(path);
}

// ---------------------------------------------------------------------------------------------
// Blending

/** A lever's value per look (JOURNEY_LOOKS order), ready to blend. */
type Column =
  | { kind: "number"; v: number[] }
  | { kind: "vector"; v: number[][] }
  | { kind: "color"; v: Vec3[]; hex: string[] }
  | { kind: "other"; v: LeverValue[] };

const HEX = /^#[0-9a-f]{6}$/i;

/**
 * Levers that do nothing while a gate lever is 0: the frame grade at amount 0 (today's dusk has
 * none). A look whose gate is 0 takes the other looks' values for them (weighted among themselves),
 * so only the amount fades (day-look.ts GATES, for any number of looks).
 */
const GATES: readonly { target: LookTarget; gate: string; group: string }[] = [{ target: "frame", gate: "grade.amount", group: "grade." }];

/**
 * Levers that lean to the lower value (day-look.ts LEAN_LOW): the share of the higher value is the
 * looks' weighted share raised to this power. Stars come out late: a half-moon blend has an eighth.
 */
const LEAN_LOW: Readonly<Record<string, number>> = { "frame:stars": 3 };

/**
 * Levers that switch over a short stretch (an edge): the share of the higher value is smoothstep
 * (from, to) of the looks' weighted share. The night-baked stops start to show their own light when
 * the moon's share passes 15%, and show it fully from 28%: their pull toward the sunset bake holds
 * up to the scroll (no moon) and is gone by the formation (30% moon), which keeps the look it was
 * tuned with. Between the two it fades over about 35 frames, 1156 to 1191 (night-bake.ts).
 */
const EDGE: Readonly<Record<string, readonly [number, number]>> = { "frame:nightBake": [0.15, 0.28] };

/** The higher value's share of a number lever: the weighted share, leaned (LEAN_LOW) or switched (EDGE). */
function shapedShare(share: number, lean: number | undefined, edge: readonly [number, number] | undefined): number {
  if (edge) return smoothstep(edge[0], edge[1], share);
  return Math.pow(share, lean ?? 1);
}

export type JourneyBases = Readonly<Record<LookTarget, object>>;

/**
 * The journey's levers for every look, read once (JOURNEY_LOOKS order; a look that leaves a lever
 * takes the base's value). `paths`: each key split at its dots, for journeyApply.
 */
export interface JourneyTable {
  targets: Record<
    LookTarget,
    {
      keys: string[];
      paths: string[][];
      cols: Column[];
      gate: number;
      group: boolean[];
      lean: (number | undefined)[];
      edge: (readonly [number, number] | undefined)[];
    }
  >;
}

function column(values: LeverValue[]): Column {
  if (values.every((x) => typeof x === "number")) return { kind: "number", v: values as number[] };
  if (values.every((x) => Array.isArray(x) && x.length === (values[0] as readonly number[]).length)) return { kind: "vector", v: values.map((x) => [...(x as number[])]) };
  if (values.every((x) => typeof x === "string" && HEX.test(x))) return { kind: "color", v: values.map((x) => hexToLinear(x as string)), hex: values as string[] };
  return { kind: "other", v: values };
}

/**
 * Reads every journey lever of every look once. `bases`: the page's tables as they are before any
 * look (and the scene's meta), where a look that leaves a lever alone takes its value.
 */
export function journeyTable(bases: JourneyBases, levers: Readonly<Record<LookTarget, readonly string[]>> = RUNTIME_LEVERS): JourneyTable {
  const targets = {} as JourneyTable["targets"];
  for (const t of Object.keys(levers) as LookTarget[]) {
    const keys = levers[t].filter((k) => readLever(bases[t], k) !== undefined);
    const cols = keys.map((k) =>
      column(
        JOURNEY_LOOKS.map((id) => {
          const own = id === "dusk" ? undefined : LOOKS[id].patch[t]?.[k];
          return (own ?? readLever(bases[t], k)) as LeverValue;
        }),
      ),
    );
    const g = GATES.find((x) => x.target === t);
    const gate = g ? keys.indexOf(g.gate) : -1;
    targets[t] = {
      keys,
      paths: keys.map((k) => k.split(".")),
      cols,
      gate,
      group: keys.map((k) => !!g && k !== g.gate && k.startsWith(g.group)),
      lean: keys.map((k) => LEAN_LOW[`${t}:${k}`]),
      edge: keys.map((k) => EDGE[`${t}:${k}`]),
    };
  }
  return { targets };
}

/** One column blended by the looks' weights `w` (JOURNEY_LOOKS order). */
function blendColumn(c: Column, w: readonly number[], lean?: number, edge?: readonly [number, number]): LeverValue {
  // A single look: its own value, exactly.
  const only = w.findIndex((x) => x >= 1);
  if (only >= 0) return c.kind === "color" ? c.hex[only] : c.kind === "vector" ? [...c.v[only]] : c.v[only];
  if (c.kind === "number") {
    if (lean !== undefined || edge !== undefined) {
      const lo = Math.min(...c.v);
      const hi = Math.max(...c.v);
      if (!(hi > lo)) return lo;
      let share = 0;
      for (let i = 0; i < w.length; i++) share += w[i] * ((c.v[i] - lo) / (hi - lo));
      return lo + (hi - lo) * shapedShare(share, lean, edge);
    }
    let s = 0;
    for (let i = 0; i < w.length; i++) s += w[i] * c.v[i];
    return s;
  }
  if (c.kind === "vector") {
    const out = c.v[0].map(() => 0);
    for (let i = 0; i < w.length; i++) for (let j = 0; j < out.length; j++) out[j] += w[i] * c.v[i][j];
    return out;
  }
  if (c.kind === "color") {
    const out: Vec3 = [0, 0, 0];
    for (let i = 0; i < w.length; i++) for (let j = 0; j < 3; j++) out[j] += w[i] * c.v[i][j];
    return linearToHex(out);
  }
  // Anything else: the heaviest look's.
  let best = 0;
  for (let i = 1; i < w.length; i++) if (w[i] > w[best]) best = i;
  return c.v[best];
}

/** The journey's levers for one table at the looks' weights. */
export function journeyLevers(table: JourneyTable, target: LookTarget, weights: JourneyWeights): Record<string, LeverValue> {
  const t = table.targets[target];
  const w = JOURNEY_LOOKS.map((id) => weights[id]);
  // The gated group: only the looks whose gate is open, renormalised among themselves.
  let wg = w;
  if (t.gate >= 0) {
    const gates = t.cols[t.gate].v as number[];
    const open = w.map((x, i) => (gates[i] !== 0 ? x : 0));
    const sum = open.reduce((a, b) => a + b, 0);
    if (sum > 0) wg = open.map((x) => x / sum);
  }
  const out: Record<string, LeverValue> = {};
  for (let i = 0; i < t.keys.length; i++) out[t.keys[i]] = blendColumn(t.cols[i], t.group[i] ? wg : w, t.lean[i], t.edge[i]);
  return out;
}

/** Every table's journey levers at the looks' weights. */
export function journeyPatch(table: JourneyTable, weights: JourneyWeights): Record<LookTarget, Record<string, LeverValue>> {
  const out = {} as Record<LookTarget, Record<string, LeverValue>>;
  for (const t of Object.keys(table.targets) as LookTarget[]) out[t] = journeyLevers(table, t, weights);
  return out;
}

/**
 * Writes levers into a table in place, without the checks of looks.ts writeLevers: for the page's
 * own copies, every frame, with levers journeyTable has already read from the same tables.
 */
export function setLevers(root: object, levers: Readonly<Record<string, LeverValue>>): void {
  for (const path in levers) {
    const keys = path.split(".");
    let node = root as Record<string, unknown>;
    for (let i = 0; i < keys.length - 1; i++) node = node[keys[i]] as Record<string, unknown>;
    const v = levers[path];
    node[keys[keys.length - 1]] = Array.isArray(v) ? [...v] : v;
  }
}

// Scratch for journeyApply (JOURNEY_LOOKS order): the looks' weights, the gated group's, a colour.
const APPLY_W: number[] = JOURNEY_LOOKS.map(() => 0);
const APPLY_WG: number[] = JOURNEY_LOOKS.map(() => 0);
const APPLY_RGB: Vec3 = [0, 0, 0];

/**
 * One column blended by the weights, as blendColumn does it (the same sums in the same order), but
 * with nothing made but a colour's hex: a list goes into `current` when it is a list of that length.
 */
function blendInto(c: Column, w: readonly number[], lean: number | undefined, edge: readonly [number, number] | undefined, current: unknown): LeverValue {
  let only = -1;
  for (let i = 0; i < w.length; i++) {
    if (w[i] >= 1) {
      only = i;
      break;
    }
  }
  if (c.kind === "vector") {
    const n = c.v[0].length;
    const out = Array.isArray(current) && current.length === n ? (current as number[]) : c.v[0].map(() => 0);
    if (only >= 0) {
      for (let j = 0; j < n; j++) out[j] = c.v[only][j];
      return out;
    }
    for (let j = 0; j < n; j++) out[j] = 0;
    for (let i = 0; i < w.length; i++) for (let j = 0; j < n; j++) out[j] += w[i] * c.v[i][j];
    return out;
  }
  if (c.kind === "other") {
    let best = only >= 0 ? only : 0;
    if (only < 0) for (let i = 1; i < w.length; i++) if (w[i] > w[best]) best = i;
    const v = c.v[best];
    return Array.isArray(v) ? [...v] : v;
  }
  if (only >= 0) return c.kind === "color" ? c.hex[only] : c.v[only];
  if (c.kind === "number") {
    if (lean !== undefined || edge !== undefined) {
      const lo = Math.min(...c.v);
      const hi = Math.max(...c.v);
      if (!(hi > lo)) return lo;
      let share = 0;
      for (let i = 0; i < w.length; i++) share += w[i] * ((c.v[i] - lo) / (hi - lo));
      return lo + (hi - lo) * shapedShare(share, lean, edge);
    }
    let s = 0;
    for (let i = 0; i < w.length; i++) s += w[i] * c.v[i];
    return s;
  }
  const out = APPLY_RGB;
  out[0] = 0;
  out[1] = 0;
  out[2] = 0;
  for (let i = 0; i < w.length; i++) for (let j = 0; j < 3; j++) out[j] += w[i] * c.v[i][j];
  return linearToHex(out);
}

/**
 * journeyPatch and setLevers in one, for the page's every moving frame (look-now.ts): every table's
 * journey levers at the looks' weights, written straight into `into` (the page's own copies), with
 * no patch built on the way. The values are journeyPatch's, exactly; a list is written into the
 * list already there.
 */
export function journeyApply(table: JourneyTable, weights: JourneyWeights, into: Readonly<Record<LookTarget, object>>): void {
  const w = APPLY_W;
  for (let i = 0; i < JOURNEY_LOOKS.length; i++) w[i] = weights[JOURNEY_LOOKS[i]];
  for (const target in table.targets) {
    const t = table.targets[target as LookTarget];
    // The gated group: only the looks whose gate is open, renormalised among themselves (journeyLevers).
    let wg = w;
    if (t.gate >= 0) {
      const gates = t.cols[t.gate].v as number[];
      let sum = 0;
      for (let i = 0; i < w.length; i++) {
        APPLY_WG[i] = gates[i] !== 0 ? w[i] : 0;
        sum += APPLY_WG[i];
      }
      if (sum > 0) {
        for (let i = 0; i < w.length; i++) APPLY_WG[i] = APPLY_WG[i] / sum;
        wg = APPLY_WG;
      }
    }
    const root = into[target as LookTarget];
    for (let k = 0; k < t.keys.length; k++) {
      const path = t.paths[k];
      let node = root as Record<string, unknown>;
      for (let i = 0; i < path.length - 1; i++) node = node[path[i]] as Record<string, unknown>;
      const last = path[path.length - 1];
      node[last] = blendInto(t.cols[k], t.group[k] ? wg : w, t.lean[k], t.edge[k], node[last]);
    }
  }
}

// ---------------------------------------------------------------------------------------------
// Which look the page shows

export type PageLook = LookChoice | { kind: "journey" };

/**
 * A forced look (?look=<id>) first, then the clock's options (?look=auto, ?time=, ?date=), then
 * ?look=dusk (today's) or ?look=journey; with none of them the journey when `journey` is on
 * (JOURNEY_ON), else the clock when `follow` is on, else today's dusk (null).
 */
export function choosePageLook(
  p: Pick<SectParams, "look" | "day" | "journey">,
  journey: boolean = JOURNEY_ON,
  follow: boolean = FOLLOW_PACIFIC_CLOCK,
): PageLook {
  if (p.look) return { kind: "look", id: p.look };
  if (p.day) return { kind: "clock", options: p.day };
  if (p.journey === false) return null;
  if (p.journey === true || journey) return { kind: "journey" };
  return follow ? { kind: "clock", options: {} } : null;
}
