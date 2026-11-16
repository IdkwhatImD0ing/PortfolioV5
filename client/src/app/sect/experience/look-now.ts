/**
 * The look now: every run-time lever's value at the camera's frame (lib/sect/journey.ts), and the
 * shared uniforms they reach (materials.ts SECT_LOOK_GPU, SECT_TREE_RIM, SECT_WATER_SKY).
 *
 * With the journey (look-switch.ts LOOK_MODE), this keeps its own copies of the look tables and
 * blends the looks into them whenever the frame moves; nothing is compiled. Without it (today's
 * dusk, or one look for the whole flight), the copies are the tables themselves and never change.
 *
 * Who reads it, each frame (all after scene.tsx Atmosphere, which moves it first):
 * - scene.tsx Atmosphere: the sky dome and the reflections' sky (with the twilight on top), the
 *   cloud sea, the moon and its halo, the land's haze colour and density, and the shared uniforms
 *   (pushLookGpu);
 * - scene.tsx CloudPuffs: the puffs' colours;
 * - scene.tsx's post chain: bloom, sun haze, vignette, shafts, cloud shade, finish, contact shade;
 * - live.tsx: the live light's gains.
 * Each compares `version` with the one it last used, so a frame where nothing moved costs nothing.
 */
import { journeyApply, journeyKeys, journeyTable, journeyWeights, weightsText, JOURNEY_LOOKS, type JourneyKey, type JourneyTable, type JourneyWeights } from "@/lib/sect/journey";
import { LIVE_LOOK, type LiveLook } from "@/lib/sect/live";
import { applyLook, lookFogConstants, SECT_LOOK, type SectLook } from "@/lib/sect/look";
import { packFog, packFrame, packGrade } from "@/lib/sect/look-gpu";
import { FRAME_LOOK, type FrameLook, type LookTarget } from "@/lib/sect/looks";
import { LUX } from "@/lib/sect/lux";
import { ATMOS } from "@/lib/sect/post";
import { RANGE_LOOK, type RangeLook } from "@/lib/sect/range-look";
import type { Hold, SectMeta } from "@/lib/sect/types";
import { LOOK_MODE, LOOK_READOUT, pristine } from "./look-switch";
import { SECT_LOOK_GPU, SECT_TREE_RIM, SECT_WATER_SKY } from "./materials";

/** The scene meta's levers a look sets. */
export interface LookMeta {
  sun: { color: string };
  moon: { color: string };
  vignette: number;
}

export interface LookNow {
  /** The journey moves these as the camera does; otherwise they never change. */
  journey: boolean;
  /** Bumped each time a lever moved. */
  version: number;
  /** The looks' weights at the frame (the journey only). */
  weights: JourneyWeights | null;
  sect: SectLook;
  live: LiveLook;
  lux: typeof LUX;
  atmos: typeof ATMOS;
  range: RangeLook;
  frame: FrameLook;
  meta: LookMeta;
}

interface Engine {
  meta: SectMeta;
  table: JourneyTable | null;
  now: LookNow;
  /** The copies the journey writes into, by target (now's own tables). */
  into: Record<LookTarget, object>;
  holds: readonly Hold[] | null;
  keys: JourneyKey[];
  frame: number;
}

function intoOf(n: LookNow): Record<LookTarget, object> {
  return { sect: n.sect, live: n.live, lux: n.lux, atmos: n.atmos, range: n.range, frame: n.frame, meta: n.meta };
}

let engine: Engine | null = null;

function metaOf(meta: SectMeta): LookMeta {
  return { sun: { color: meta.sun.color }, moon: { color: meta.moon?.color ?? "#ffffff" }, vignette: meta.vignette };
}

function build(meta: SectMeta): Engine {
  if (LOOK_MODE !== "journey") {
    const now: LookNow = {
      journey: false,
      version: 0,
      weights: null,
      sect: SECT_LOOK,
      live: LIVE_LOOK,
      lux: LUX,
      atmos: ATMOS,
      range: RANGE_LOOK,
      frame: FRAME_LOOK,
      meta: metaOf(meta),
    };
    return { meta, table: null, now, into: intoOf(now), holds: null, keys: [], frame: Number.NaN };
  }
  // The tables as they were before any look (look-switch.ts kept copies at load), and the meta as
  // the scene has it: what the journey blends from, and where a look that leaves a lever takes it.
  const bases = {
    sect: pristine(SECT_LOOK) as SectLook,
    live: pristine(LIVE_LOOK) as LiveLook,
    lux: pristine(LUX) as typeof LUX,
    atmos: pristine(ATMOS) as typeof ATMOS,
    range: pristine(RANGE_LOOK) as RangeLook,
    frame: pristine(FRAME_LOOK) as FrameLook,
    meta: metaOf(meta),
  };
  const now: LookNow = {
    journey: true,
    version: 0,
    weights: null,
    sect: structuredClone(bases.sect),
    live: structuredClone(bases.live),
    lux: structuredClone(bases.lux),
    atmos: structuredClone(bases.atmos),
    range: structuredClone(bases.range),
    frame: structuredClone(bases.frame),
    meta: structuredClone(bases.meta),
  };
  return { meta, table: journeyTable(bases), now, into: intoOf(now), holds: null, keys: [], frame: Number.NaN };
}

function sameWeights(a: JourneyWeights | null, b: JourneyWeights): boolean {
  return !!a && JOURNEY_LOOKS.every((id) => Math.abs(a[id] - b[id]) < 1e-6);
}

/**
 * The look at a camera frame (the journey blends it when the frame moved; otherwise it is the same
 * object, unchanged). `holds`: the camera's, where the arc's stops take their frames.
 */
export function lookNowAt(frame: number, holds: readonly Hold[], meta: SectMeta): LookNow {
  if (!engine || engine.meta !== meta) engine = build(meta);
  const e = engine;
  if (!e.table) return e.now;
  if (e.holds !== holds) {
    e.holds = holds;
    e.keys = journeyKeys(holds);
    e.frame = Number.NaN;
  }
  if (Math.abs(frame - e.frame) < 1e-3) return e.now;
  e.frame = frame;
  const w = journeyWeights(frame, e.keys);
  // For the console (development or ?debug=1): the frame too, so it follows the camera through a stretch of one look.
  if (LOOK_READOUT) (window as unknown as { __sectLook?: string }).__sectLook = `journey: ${weightsText(w)} at frame ${Math.round(frame)}`;
  if (sameWeights(e.now.weights, w)) return e.now;
  // Every moving frame: straight into the copies, no patch built on the way (journey.ts journeyApply).
  journeyApply(e.table, w, e.into);
  const n = e.now;
  n.weights = w;
  n.version++;
  return n;
}

/** The look as last moved (null before the scene first asked). */
export function lookNow(): LookNow | null {
  return engine?.now ?? null;
}

/**
 * The shared uniforms from the look: the haze and the surfaces' grade (their switches on with the
 * journey only, so without it every shader keeps the numbers it was built with), the frame grade
 * (every tier: the post pass on High and Mid, the end of each shader on Low), the tree cards' rim
 * and the ponds' sky. The effects' shared haze colour (materials.ts SECT_HAZE_COLOR) is not set
 * here: scene.tsx applyLookNow sets it to the land's haze with the twilight, right after this.
 */
export function pushLookGpu(now: LookNow, meta: SectMeta): void {
  const d = SECT_LOOK_GPU.uSectLook.value;
  if (now.journey) {
    // The scene's meta carries the haze density times today's densityScale (assets.ts applyLook).
    const base = pristine(SECT_LOOK) as SectLook;
    const raw: SectMeta = { ...meta, fog: { ...meta.fog, density: meta.fog.density / Math.max(base.haze.densityScale, 1e-6) } };
    packFog(d, lookFogConstants(applyLook(raw, now.sect), now.sect));
    packGrade(d, now.sect.grade);
  } else {
    packFog(d, null);
    packGrade(d, null);
  }
  packFrame(d, now.frame.grade);
  SECT_TREE_RIM.value.set(now.sect.trees.rim).multiplyScalar(now.sect.trees.rimStrength);
  SECT_WATER_SKY.uWaterSkyLow.value.set(now.sect.water.skyLow);
  SECT_WATER_SKY.uWaterSkyHigh.value.set(now.sect.water.skyHigh);
}
