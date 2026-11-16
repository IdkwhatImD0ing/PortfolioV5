import { closeSync, existsSync, openSync, readFileSync, readSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { DETAIL_LOOK, detailGlsl, pavingSlab } from "./detail";
import { glslFloat } from "./glsl";
import {
  LIVE_CLASSES,
  LIVE_HEADING_START,
  LIVE_LOOK,
  LIVE_STOP_KNOBS,
  LIVE_VIEW,
  liveApplyGlsl,
  liveArriving,
  liveAtlasOf,
  liveBumpVec,
  liveClassOf,
  liveComing,
  liveDisc,
  liveEase,
  liveGradeLinear,
  liveHeading,
  liveIndexFile,
  liveLevelWeights,
  liveLightBasis,
  liveLookFor,
  liveMapFile,
  liveNeighbour,
  liveOn,
  liveParsGlsl,
  livePenumbra,
  livePreload,
  liveProject,
  liveShadowBoxCentre,
  liveShadowMatrix,
  liveShadowScale,
  liveSheenGlsl,
  liveShineVec,
  liveStep,
  liveStopAt,
  liveStopBox,
  liveStopKept,
  liveStopOf,
  liveStopsFile,
  liveSurfaceNormalGlsl,
  liveValues,
  parseLiveIndex,
  parseLiveParam,
  parseLiveStops,
  type LiveAction,
  type LiveHeading,
  type LiveIndex,
  type LivePreloadTick,
  type LiveShadowBox,
  type LiveTick,
} from "./live";
import { parseCameraData, parseMeta } from "./parse";
import { tierQuality } from "./runtime";
import type { AreaMeta, Vec3 } from "./types";

/** The stops as the page reads them (meta.json areas, in flight order). */
const AREAS: AreaMeta[] = parseMeta(JSON.parse(readFileSync(path.resolve(__dirname, "../../../public/sect/full/meta.json"), "utf8"))).areas;
const GATE = AREAS.find((a) => a.id === "gate")!;
/** Where the camera rests at each stop (camera.json holds): where fast travel lands. */
const HOLDS = parseCameraData(JSON.parse(readFileSync(path.resolve(__dirname, "../../../public/sect/full/camera.json"), "utf8"))).holds;
const holdOf = (id: string): number => HOLDS.find((h) => h.id === id)!.frame;

/** A lamp's shadow box at a stop of this footprint, as live.tsx builds it. */
function boxAt(footprint: number, lamp: "key" | "sun"): LiveShadowBox {
  const stop = liveStopBox(footprint, LIVE_LOOK);
  const s = lamp === "key" ? LIVE_LOOK.shadow : LIVE_LOOK.sunShadow;
  return { radiusM: lamp === "key" ? stop.radiusM : stop.sunRadiusM, depthM: s.depthM, aheadM: s.aheadM };
}

interface SampleLamp {
  dir: unknown;
  color: unknown;
  strength: unknown;
  angleDeg: unknown;
}

interface Sample {
  version: unknown;
  chunk?: unknown;
  ambientScale: unknown;
  ambientKind?: unknown;
  ambientBounce?: unknown;
  ambientAlpha?: unknown;
  normalAlpha?: unknown;
  atlases: Record<string, Record<string, unknown>>;
  light: { sun: SampleLamp; key?: SampleLamp; worldStrength: unknown };
  post?: Record<string, unknown>;
}

/** An index.json as the bake writes it. */
function sample(): Sample {
  const k = 1 / Math.sqrt(3);
  return {
    version: 1,
    chunk: "gate",
    ambientScale: 2,
    atlases: {
      gate_A0: { size: 4096, albedo: "gate_A0_albedo.webp", ambient: "gate_A0_ambient.webp", normal: "gate_A0_normal.png", ambientMax: 1.23 },
      gate_A1: { size: 4096, albedo: "gate_A1_albedo.webp", ambient: "gate_A1_ambient.webp", normal: "gate_A1_normal.png" },
    },
    light: {
      sun: { dir: [-0.94397, 0.12187, 0.30671], color: [1, 0.52, 0.23], strength: 8, angleDeg: 1.2 },
      key: { dir: [k, k, k], color: [1, 0.72, 0.5], strength: 2.4, angleDeg: 6 },
      worldStrength: 1,
    },
    post: { exposureStops: 1.2, saturation: 1.15, view: "AgX", look: "AgX - Punchy" },
  };
}

const close = (a: readonly number[], b: readonly number[], eps = 1e-9) => a.length === b.length && a.every((x, i) => Math.abs(x - b[i]) < eps);

/** GLSL's smoothstep, mix and the luminance the shader weighs light by. */
const smoothstep = (a: number, b: number, x: number) => {
  const t = Math.min(Math.max((x - a) / (b - a), 0), 1);
  return t * t * (3 - 2 * t);
};
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const luma = (c: readonly number[]) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];

/**
 * The arguments of the first call to `name` in a GLSL source, split at the commas outside any
 * parentheses.
 */
function callArgs(src: string, name: string): string[] {
  const at = src.indexOf(`${name}( `);
  expect(at, name).toBeGreaterThanOrEqual(0);
  const out: string[] = [];
  let depth = 0;
  let cur = "";
  for (let i = at + name.length + 1; i < src.length; i++) {
    const ch = src[i];
    if (ch === "(") depth++;
    if (ch === ")") {
      if (depth === 0) break;
      depth--;
    }
    if (ch === "," && depth === 0) {
      out.push(cur.trim());
      cur = "";
    } else cur += ch;
  }
  out.push(cur.trim());
  return out;
}

/** A GLSL source without its line comments. */
const code = (src: string) => src.replace(/\/\/[^\n]*/g, "");

/** The first `n` bytes of a file. */
function fileHead(file: string, n = 32): Uint8Array {
  const fd = openSync(file, "r");
  try {
    const b = new Uint8Array(n);
    return b.subarray(0, readSync(fd, b, 0, n, 0));
  } finally {
    closeSync(fd);
  }
}

/**
 * Whether a WebP's header says it has an alpha channel: the VP8X chunk's alpha flag (0x10 of the
 * byte at 20), or the lossless header's alpha bit. A plain lossy (VP8) file has none. Null when it
 * is not a WebP.
 */
function webpAlpha(head: Uint8Array): boolean | null {
  const tag = (at: number) => String.fromCharCode(...head.subarray(at, at + 4));
  if (head.length < 25 || tag(0) !== "RIFF" || tag(8) !== "WEBP") return null;
  const chunk = tag(12);
  if (chunk === "VP8X") return (head[20] & 0x10) !== 0;
  // VP8L: a 0x2f byte, then width - 1 and height - 1 (14 bits each), then the alpha bit.
  if (chunk === "VP8L") return head[20] === 0x2f && ((head[24] >> 4) & 1) === 1;
  if (chunk === "VP8 ") return false;
  return null;
}

/**
 * Whether these first bytes of a file are a Git LFS pointer. The live maps are kept in Git LFS, and
 * a checkout that does not fetch LFS (the CI's) holds this short text file in place of each map.
 */
function lfsPointer(head: Uint8Array): boolean {
  return String.fromCharCode(...head).startsWith("version https://git-lfs");
}

describe("parseLiveIndex", () => {
  it("reads the bake's index.json", () => {
    const ix = parseLiveIndex(sample());
    expect(ix).not.toBeNull();
    expect(ix!.chunk).toBe("gate");
    expect(ix!.ambientScale).toBe(2);
    expect(Object.keys(ix!.atlases)).toEqual(["gate_A0", "gate_A1"]);
    expect(ix!.atlases.gate_A0).toEqual({ size: 4096, albedo: "gate_A0_albedo.webp", ambient: "gate_A0_ambient.webp", normal: "gate_A0_normal.png", ambientMax: 1.23 });
    expect(ix!.atlases.gate_A1.ambientMax).toBeNull();
    expect(ix!.light.sun.strength).toBe(8);
    expect(ix!.light.key.angleDeg).toBe(6);
    expect(ix!.post).toEqual({ exposureStops: 1.2, saturation: 1.15, view: "AgX", look: "AgX - Punchy" });
  });

  it("gives the lamps exact unit directions (the file rounds them)", () => {
    const ix = parseLiveIndex(sample())!;
    for (const lamp of [ix.light.sun, ix.light.key]) expect(Math.hypot(...lamp.dir)).toBeCloseTo(1, 12);
  });

  it("returns null on anything malformed", () => {
    const bad: ((j: Sample) => void)[] = [
      (j) => (j.version = 2),
      (j) => delete j.chunk,
      (j) => (j.chunk = "../gate"),
      (j) => (j.ambientScale = 0),
      (j) => (j.atlases = {}),
      (j) => ((j as { atlases: unknown }).atlases = []),
      (j) => delete j.atlases.gate_A0.normal,
      (j) => (j.atlases.gate_A0.albedo = "../../secret.webp"),
      (j) => (j.atlases.gate_A0.ambient = "sub/dir.webp"),
      (j) => (j.atlases.gate_A0.size = -1),
      (j) => (j.atlases.gate_A0.ambientMax = "big"),
      (j) => (j.atlases["not an atlas"] = j.atlases.gate_A0),
      (j) => (j.light.sun.dir = [1, 1, 0]),
      (j) => (j.light.key!.dir = [0, 1]),
      (j) => (j.light.key!.color = [1, -0.1, 0]),
      (j) => (j.light.sun.strength = Number.NaN),
      (j) => delete j.light.key,
      (j) => (j.light.worldStrength = "1"),
      (j) => delete j.post,
      (j) => (j.post!.exposureStops = null),
    ];
    for (const change of bad) {
      const j = sample();
      change(j);
      expect(parseLiveIndex(j), String(change)).toBeNull();
    }
    expect(parseLiveIndex(null)).toBeNull();
    expect(parseLiveIndex("index")).toBeNull();
  });

  it("names its files under live/<chunk>/", () => {
    expect(liveIndexFile("gate")).toBe("live/gate/index.json");
    expect(liveMapFile("gate", "gate_A0_normal.png")).toBe("live/gate/gate_A0_normal.png");
  });

  it("reads what the ambient map holds: radiance unless it says irradiance", () => {
    expect(parseLiveIndex(sample())!.ambientKind).toBe("radiance");
    const irr = sample();
    irr.ambientKind = "irradiance";
    expect(parseLiveIndex(irr)!.ambientKind).toBe("irradiance");
    // Anything else is the old kind, and not a reason to drop the index.
    for (const junk of ["radiance", "Irradiance", "irradiance ", "", 1, true, null, ["irradiance"], { kind: "irradiance" }]) {
      const j = sample();
      j.ambientKind = junk;
      const ix = parseLiveIndex(j);
      expect(ix, JSON.stringify(junk)).not.toBeNull();
      expect(ix!.ambientKind, JSON.stringify(junk)).toBe("radiance");
    }
  });

  it("reads whether the normal map's alpha says where the bake's shadow is soft", () => {
    expect(parseLiveIndex(sample())!.bakedSoft).toBe(false);
    const soft = sample();
    soft.normalAlpha = "soft";
    expect(parseLiveIndex(soft)!.bakedSoft).toBe(true);
    // Anything else is no soft map, and not a reason to drop the index.
    for (const junk of ["Soft", "soft ", "visibility", "", true, 1, null, ["soft"], { kind: "soft" }]) {
      const j = sample();
      j.normalAlpha = junk;
      const ix = parseLiveIndex(j);
      expect(ix, JSON.stringify(junk)).not.toBeNull();
      expect(ix!.bakedSoft, JSON.stringify(junk)).toBe(false);
    }
    // It says nothing of the ambient map's alpha, nor that of the normal map.
    const vis = sample();
    vis.ambientAlpha = "visibility";
    expect(parseLiveIndex(vis)!.bakedSoft).toBe(false);
    expect(parseLiveIndex(soft)!.bakedShadow).toBe(false);
  });
});

describe("the installed live maps (public/sect/full/live)", () => {
  const root = path.resolve(__dirname, "../../../public/sect/full");
  // Read when the test runs: more stops may be installed at any time.
  const stops = parseLiveStops(JSON.parse(readFileSync(path.join(root, liveStopsFile()), "utf8")));

  it("list the gate at least, and only stops the flight has", () => {
    expect(stops).toContain("gate");
    for (const s of stops) expect(AREAS.map((a) => a.id), s).toContain(s);
  });

  it("list every stop of the flight", () => {
    expect([...stops].sort()).toEqual(AREAS.map((a) => a.id).sort());
  });

  it("each hold the bake's soft shadow in their ambient maps' alpha", () => {
    for (const stop of stops) {
      const ix = parseLiveIndex(JSON.parse(readFileSync(path.join(root, liveIndexFile(stop)), "utf8")));
      expect(ix, stop).not.toBeNull();
      expect(ix!.bakedShadow, stop).toBe(true);
      for (const a of Object.values(ix!.atlases)) {
        const head = fileHead(path.join(root, liveMapFile(stop, a.ambient)));
        // Without Git LFS (the CI) there is a pointer in the map's place, and no header to read.
        if (lfsPointer(head)) continue;
        expect(webpAlpha(head), `${stop}/${a.ambient}`).toBe(true);
      }
    }
  });

  it("each say where the bake's shadow is soft in their normal maps' alpha", () => {
    for (const stop of stops) {
      const ix = parseLiveIndex(JSON.parse(readFileSync(path.join(root, liveIndexFile(stop)), "utf8")));
      expect(ix, stop).not.toBeNull();
      expect(ix!.bakedSoft, stop).toBe(true);
      for (const a of Object.values(ix!.atlases)) {
        const head = fileHead(path.join(root, liveMapFile(stop, a.normal)));
        if (lfsPointer(head)) continue;
        expect(webpAlpha(head), `${stop}/${a.normal}`).toBe(true);
      }
    }
  });

  it("each have an index that parses, holds light without the surface colour, and names files that are there", () => {
    for (const stop of stops) {
      const ix = parseLiveIndex(JSON.parse(readFileSync(path.join(root, liveIndexFile(stop)), "utf8")));
      expect(ix, stop).not.toBeNull();
      expect(ix!.chunk, stop).toBe(stop);
      expect(ix!.ambientKind, stop).toBe("irradiance");
      const atlases = Object.entries(ix!.atlases);
      expect(atlases.length, stop).toBeGreaterThan(0);
      for (const [key, a] of atlases) {
        expect(key.startsWith(`${stop}_A`), key).toBe(true);
        for (const file of [a.albedo, a.ambient, a.normal]) expect(existsSync(path.join(root, liveMapFile(stop, file))), `${stop}/${file}`).toBe(true);
      }
    }
  });
});

describe("parseLiveStops (live/index.json)", () => {
  it("is the file beside the stops' folders", () => {
    expect(liveStopsFile()).toBe("live/index.json");
    expect(liveStopsFile()).not.toBe(liveIndexFile("gate"));
  });

  it("reads the stops with maps, in the file's order, each once", () => {
    expect(parseLiveStops({ version: 1, chunks: ["gate"] })).toEqual(["gate"]);
    expect(parseLiveStops({ version: 1, chunks: ["mirror", "gate", "mirror", "summit"] })).toEqual(["mirror", "gate", "summit"]);
    expect(parseLiveStops({ version: 1, chunks: [] })).toEqual([]);
    // The ids index.json's own parser takes.
    expect(parseLiveStops({ version: 1, chunks: ["a_b-C9"] })).toEqual(["a_b-C9"]);
  });

  it("gives nothing for anything malformed", () => {
    for (const bad of [
      null,
      "gate",
      ["gate"],
      {},
      { chunks: ["gate"] },
      { version: 2, chunks: ["gate"] },
      { version: "1", chunks: ["gate"] },
      { version: 1 },
      { version: 1, chunks: "gate" },
      { version: 1, chunks: { gate: true } },
      { version: 1, chunks: ["gate", "../secret"] },
      { version: 1, chunks: ["gate", "live/gate"] },
      { version: 1, chunks: ["gate", ""] },
      { version: 1, chunks: ["gate", 3] },
      { version: 1, chunks: ["gate", null] },
    ]) {
      expect(parseLiveStops(bad), JSON.stringify(bad)).toEqual([]);
    }
  });
});

describe("which stop is lit live", () => {
  const ids = AREAS.map((a) => a.id);

  it("reads eleven stops from the real meta.json, in flight order", () => {
    expect(AREAS).toHaveLength(11);
    for (let i = 1; i < AREAS.length; i++) expect(AREAS[i].frameStart, AREAS[i].id).toBeGreaterThan(AREAS[i - 1].frameEnd);
  });

  it("names the stop whose frame range holds the frame", () => {
    for (const a of AREAS) {
      for (const f of [a.frameStart, a.frameEnd, a.heroFrame, (a.frameStart + a.frameEnd) / 2]) expect(liveStopOf(f, AREAS)?.id, `${a.id} at ${f}`).toBe(a.id);
    }
  });

  it("gives a frame between two ranges to the stop ahead", () => {
    for (let i = 1; i < AREAS.length; i++) {
      const [prev, next] = [AREAS[i - 1], AREAS[i]];
      // The ranges are whole frames: the camera's frame is not.
      for (const f of [(prev.frameEnd + next.frameStart) / 2, prev.frameEnd + 1e-6, next.frameStart - 1e-6]) {
        if (f > prev.frameEnd && f < next.frameStart) expect(liveStopOf(f, AREAS)?.id, `${f}`).toBe(next.id);
      }
    }
  });

  it("gives frames before the first stop to it, and past the last to the last", () => {
    expect(liveStopOf(AREAS[0].frameStart - 10, AREAS)?.id).toBe(AREAS[0].id);
    expect(liveStopOf(-1e6, AREAS)?.id).toBe(AREAS[0].id);
    expect(liveStopOf(AREAS[AREAS.length - 1].frameEnd + 10, AREAS)?.id).toBe(AREAS[AREAS.length - 1].id);
    expect(liveStopOf(Number.NaN, AREAS)).toBeNull();
    expect(liveStopOf(100, [])).toBeNull();
  });

  it("does not need the stops in order", () => {
    const shuffled = [...AREAS].reverse();
    for (const a of AREAS) expect(liveStopOf(a.heroFrame, shuffled)?.id).toBe(a.id);
    expect(liveStopOf((AREAS[0].frameEnd + AREAS[1].frameStart) / 2, shuffled)?.id).toBe(AREAS[1].id);
  });

  it("lights only a stop with maps, and never another stop in its place", () => {
    const withGate = ["gate"];
    for (const a of AREAS) {
      const f = a.heroFrame;
      expect(liveStopAt(f, AREAS, withGate)?.id ?? null, a.id).toBe(a.id === "gate" ? "gate" : null);
      expect(liveStopAt(f, AREAS, ids)?.id, a.id).toBe(a.id);
      expect(liveStopAt(f, AREAS, []), a.id).toBeNull();
    }
    // Any subset: each stop is lit exactly when it is listed.
    const some = ids.filter((_, i) => i % 3 === 1);
    for (const a of AREAS) expect(liveStopAt(a.heroFrame, AREAS, some)?.id ?? null, a.id).toBe(some.includes(a.id) ? a.id : null);
    // Between the gate and the mirror, with only the gate listed: the mirror's, so nothing.
    expect(liveStopAt((GATE.frameEnd + AREAS[1].frameStart) / 2, AREAS, withGate)).toBeNull();
  });
});

describe("a stop's live region", () => {
  it("is today's at the gate: whole to 45 m, gone by 72 m, both maps 80 m each way", () => {
    expect(GATE.footprint).toBe(40);
    expect(liveStopBox(GATE.footprint, LIVE_LOOK)).toEqual({ fromM: 45, toM: 72, radiusM: 80, sunRadiusM: 80 });
    expect(liveStopBox(40)).toEqual(liveStopBox(40, LIVE_LOOK));
  });

  it("grows with the footprint: the blend past it by padM and fadeM, the maps past that by their margins", () => {
    const L = LIVE_LOOK;
    for (const a of AREAS) {
      const b = liveStopBox(a.footprint, L);
      expect(b.fromM, a.id).toBeCloseTo(a.footprint + L.blend.padM, 12);
      expect(b.toM, a.id).toBeCloseTo(b.fromM + L.blend.fadeM, 12);
      expect(b.radiusM, a.id).toBeCloseTo(b.toM + L.shadow.marginM, 12);
      expect(b.sunRadiusM, a.id).toBeCloseTo(b.toM + L.sunShadow.marginM, 12);
    }
    const big = liveStopBox(58, L);
    expect(big.radiusM).toBeGreaterThan(liveStopBox(40, L).radiusM);
  });

  it("follows the look and stays sane with odd numbers", () => {
    const look = structuredClone(LIVE_LOOK);
    look.blend = { padM: 10, fadeM: 0 };
    look.shadow.marginM = 3;
    look.sunShadow.marginM = 20;
    expect(liveStopBox(50, look)).toEqual({ fromM: 60, toM: 60, radiusM: 63, sunRadiusM: 80 });
    look.blend = { padM: -5, fadeM: -5 };
    const b = liveStopBox(-1, look);
    expect(b.fromM).toBe(0);
    expect(b.toM).toBe(0);
  });

  it("keeps the narrowest penumbra off a texel and the widest within the filter's reach, at every stop", () => {
    for (const [name, s, lamp] of [
      ["key", LIVE_LOOK.shadow, "key"],
      ["sun", LIVE_LOOK.sunShadow, "sun"],
    ] as const) {
      expect(s.minPenumbraTexels, name).toBeGreaterThanOrEqual(1);
      expect(s.maxPenumbraTexels, name).toBeGreaterThan(s.minPenumbraTexels);
      for (const a of AREAS) {
        const texel = liveShadowScale(boxAt(a.footprint, lamp), 1, s.size).texelM;
        const [lo, hi] = livePenumbra(s, texel);
        expect(lo, `${name} ${a.id}`).toBeGreaterThanOrEqual(texel);
        expect(lo, `${name} ${a.id}`).toBeGreaterThanOrEqual(s.minPenumbraM);
        expect(hi, `${name} ${a.id}`).toBeGreaterThanOrEqual(lo);
        // The taps are fixed: an edge wider than they cover would show as steps.
        expect(hi, `${name} ${a.id}`).toBeLessThanOrEqual(s.maxPenumbraTexels * texel + 1e-12);
        expect(hi, `${name} ${a.id}`).toBeLessThanOrEqual(s.maxPenumbraM);
      }
    }
    // The gate: a texel of 160 m / 4096 = 0.039 m. Its widest edge is the narrower of the two caps.
    const texel = liveShadowScale(boxAt(GATE.footprint, "key"), 1, LIVE_LOOK.shadow.size).texelM;
    expect(texel).toBeCloseTo(0.0390625, 12);
    const s = LIVE_LOOK.shadow;
    expect(livePenumbra(s, texel)[1]).toBeCloseTo(Math.min(s.maxPenumbraM, s.maxPenumbraTexels * texel), 12);
  });

  it("works its penumbra range out from metres and texels", () => {
    // Without a texel ceiling: the metre ceiling, as before.
    expect(livePenumbra({ minPenumbraM: 0.05, maxPenumbraM: 1.5, minPenumbraTexels: 2 }, 0.04)).toEqual([0.08, 1.5]);
    // With one: whichever ceiling is narrower.
    const [lo, hi] = livePenumbra({ minPenumbraM: 0.05, maxPenumbraM: 1.5, minPenumbraTexels: 2, maxPenumbraTexels: 12 }, 0.04);
    expect(lo).toBeCloseTo(0.08, 12);
    expect(hi).toBeCloseTo(0.48, 12);
    expect(livePenumbra({ minPenumbraM: 0.05, maxPenumbraM: 0.3, minPenumbraTexels: 2, maxPenumbraTexels: 100 }, 0.04)[1]).toBe(0.3);
    // Coarse texels take over the floor, and the ceiling never drops under it.
    expect(livePenumbra({ minPenumbraM: 0.05, maxPenumbraM: 0.1, minPenumbraTexels: 2 }, 0.2)).toEqual([0.4, 0.4]);
    expect(livePenumbra({ minPenumbraM: 0.05, maxPenumbraM: 1.5, minPenumbraTexels: 2, maxPenumbraTexels: 1 }, 0.2)).toEqual([0.4, 0.4]);
  });
});

describe("a stop's own numbers (LIVE_LOOK.stops)", () => {
  it("are the overall balance only", () => {
    expect([...LIVE_STOP_KNOBS].sort()).toEqual(["ambientGain", "exposureBias", "gain", "keyGain", "saturation", "sunGain"]);
    for (const [stop, own] of Object.entries(LIVE_LOOK.stops)) {
      for (const [k, v] of Object.entries(own)) {
        expect(LIVE_STOP_KNOBS as readonly string[], `${stop}.${k}`).toContain(k);
        expect(Number.isFinite(v), `${stop}.${k}`).toBe(true);
      }
    }
  });

  it("leave the look as it is at a stop with none", () => {
    const bare = { ...LIVE_LOOK, stops: {} };
    expect(liveLookFor(bare, "gate")).toBe(bare);
    expect(liveLookFor({ ...bare, stops: { mirror: { sunGain: 3 } } }, "gate").sunGain).toBe(bare.sunGain);
    // Names that only look like stops on any object.
    expect(liveLookFor(bare, "constructor")).toBe(bare);
    // A console copy with no stops at all.
    const none = { ...bare, stops: undefined as never };
    expect(liveLookFor(none, "gate")).toBe(none);
  });

  it("replace those numbers at that stop only, and nothing else", () => {
    const look = structuredClone(LIVE_LOOK);
    const before = structuredClone(look);
    look.stops = {
      mirror: { sunGain: 2, ambientGain: 0.5, exposureBias: -0.5, saturation: 1.1, gain: 0.9, keyGain: 0 },
      forge: { sunGain: Number.NaN, specular: 9, bump: 0 } as never,
    };
    const m = liveLookFor(look, "mirror");
    expect([m.sunGain, m.ambientGain, m.exposureBias, m.saturation, m.gain, m.keyGain]).toEqual([2, 0.5, -0.5, 1.1, 0.9, 0]);
    expect(m.classes).toBe(look.classes);
    expect(m.shadow).toBe(look.shadow);
    // Not a knob, or not a number: ignored.
    const f = liveLookFor(look, "forge");
    expect(f.sunGain).toBe(look.sunGain);
    expect(f.specular).toBe(look.specular);
    expect(f.bump).toBe(look.bump);
    expect(liveLookFor(look, "gate").sunGain).toBe(look.sunGain);
    // The look itself is untouched.
    expect({ ...look, stops: {} }).toEqual({ ...before, stops: {} });
  });

  it("reach the uniforms through liveValues", () => {
    const ix = parseLiveIndex(sample()) as LiveIndex;
    const look = structuredClone(LIVE_LOOK);
    look.stops = { gate: { sunGain: look.sunGain * 2, exposureBias: look.exposureBias + 1 } };
    const box = liveStopBox(GATE.footprint, look);
    const own = liveValues(ix, liveLookFor(look, "gate"), box);
    const plain = liveValues(ix, look, box);
    expect(own.sunE[0]).toBeCloseTo(plain.sunE[0] * 2, 12);
    expect(own.exposure).toBeCloseTo(plain.exposure * 2, 12);
    expect(own.keyE).toEqual(plain.keyE);
    expect(own.blend).toEqual(plain.blend);
    // The rebuilt bake stays at the bake's own strength and post whatever the stop asks for.
    for (let i = 0; i < 3; i++) expect(own.sunE[i] * own.bakeGain[0]).toBeCloseTo(plain.sunE[i] * plain.bakeGain[0], 12);
    expect(own.bakePost).toEqual(plain.bakePost);
  });
});

describe("liveStep", () => {
  const A = { id: "A" };
  const C = { id: "C" };
  /** Nothing lit, nothing starting, at stop C, its set loaded and ready. */
  const tick = (t: Partial<LiveTick<{ id: string }>> = {}): LiveTick<{ id: string }> => ({
    lit: null,
    mix: 0,
    starting: null,
    here: "C",
    set: C,
    ready: true,
    failed: false,
    passing: false,
    ...t,
  });
  const lit = (stop: string, fading = false) => ({ stop, fading });

  it("starts the stop here once its set is ready", () => {
    expect(liveStep(tick())).toBe<LiveAction>("start");
  });

  it("waits for the stop's set and never starts another stop meanwhile", () => {
    expect(liveStep(tick({ set: null, ready: false }))).toBe("wait");
    expect(liveStep(tick({ ready: false }))).toBe("wait");
    expect(liveStep(tick({ here: null, set: null, ready: false }))).toBe("wait");
  });

  it("does not try a set that failed again, but tries the stop's next set", () => {
    expect(liveStep(tick({ failed: true }))).toBe("wait");
    expect(liveStep(tick({ set: { id: "C" }, failed: false }))).toBe("start");
  });

  it("does not start a stop an eased flight only passes", () => {
    expect(liveStep(tick({ passing: true }))).toBe("wait");
    // A start already under way there is left to finish.
    expect(liveStep(tick({ passing: true, starting: C }))).toBe("keep");
  });

  it("keeps the stop lit while the flight stays there", () => {
    expect(liveStep(tick({ lit: lit("C"), mix: 1 }))).toBe("keep");
    expect(liveStep(tick({ lit: lit("C"), mix: 0.4 }))).toBe("keep");
  });

  it("fades the stop lit out when the flight leaves it, and ends it at once if it already shows the bake", () => {
    expect(liveStep(tick({ lit: lit("A"), mix: 1 }))).toBe("fade");
    expect(liveStep(tick({ lit: lit("A"), mix: 1, here: null, set: null }))).toBe("fade");
    expect(liveStep(tick({ lit: lit("A"), mix: 0 }))).toBe("end");
    // The fade runs on; the next stop waits for it.
    expect(liveStep(tick({ lit: lit("A", true), mix: 0.5 }))).toBe("keep");
  });

  it("ramps up again when the flight comes back before the fade ends", () => {
    expect(liveStep(tick({ lit: lit("C", true), mix: 0.3 }))).toBe("resume");
  });

  it("drops a start for a stop the flight has left, and keeps one for the stop here", () => {
    expect(liveStep(tick({ starting: C }))).toBe("keep");
    expect(liveStep(tick({ starting: A }))).toBe("end");
    expect(liveStep(tick({ starting: A, here: null, set: null }))).toBe("end");
    // The stop's set was dropped and is not back yet: the start for the old one goes.
    expect(liveStep(tick({ starting: C, set: null, ready: false }))).toBe("end");
    // Or it is back as a new set: the start for the old one goes, the new one starts after.
    expect(liveStep(tick({ starting: C, set: { id: "C" } }))).toBe("end");
  });

  it("takes a fast-travel jump past several stops as one change", () => {
    // Lit at A, the frame jumps to C: fade A out, then (nothing lit) start C.
    expect(liveStep(tick({ lit: lit("A"), mix: 1 }))).toBe("fade");
    expect(liveStep(tick({ lit: lit("A", true), mix: 0.2 }))).toBe("keep");
    expect(liveStep(tick())).toBe("start");
    // Loading A when the jump lands at C: A's start goes, C starts once ready.
    expect(liveStep(tick({ starting: A }))).toBe("end");
    expect(liveStep(tick({ ready: false }))).toBe("wait");
  });

  it("under fast travel's ink, ends the stop left at once (nobody sees a fade) and keeps the rest as it was", () => {
    expect(liveStep(tick({ lit: lit("A"), mix: 1, covered: true }))).toBe("end");
    expect(liveStep(tick({ lit: lit("A", true), mix: 0.5, covered: true }))).toBe("end");
    expect(liveStep(tick({ lit: lit("C"), mix: 1, covered: true }))).toBe("keep");
    expect(liveStep(tick({ lit: lit("C", true), mix: 0.5, covered: true }))).toBe("resume");
    expect(liveStep(tick({ covered: true }))).toBe("start");
    expect(liveStep(tick({ starting: C, covered: true }))).toBe("keep");
  });
});

describe("going from stop to stop (LIVE_LOOK.handover)", () => {
  const H = LIVE_LOOK.handover;
  const ids = AREAS.map((a) => a.id);

  it("has sane knobs", () => {
    expect(H.stayFrames).toBeGreaterThanOrEqual(0);
    expect(H.reverseFrames).toBeGreaterThanOrEqual(0);
    expect(Number.isFinite(H.leadFrames)).toBe(true);
    expect(H.inkWaitMs).toBeGreaterThan(0);
    expect(typeof H.preload).toBe("boolean");
  });

  describe("which stop: the one lit stays a little past its range", () => {
    it("keeps the stop lit until the frame is more than stayFrames past its range, either side", () => {
      for (let i = 1; i < AREAS.length; i++) {
        const [prev, next] = [AREAS[i - 1], AREAS[i]];
        const kept = (f: number, cur: string) => liveStopKept(f, AREAS, ids, cur, H.stayFrames)?.id;
        // Forward over the line: the stop behind stays to stayFrames past its end.
        expect(kept(prev.frameEnd + H.stayFrames, prev.id), prev.id).toBe(prev.id);
        expect(kept(prev.frameEnd + H.stayFrames + 0.01, prev.id), prev.id).toBe(next.id);
        // Back over it: the stop ahead stays to stayFrames before its start.
        expect(kept(next.frameStart - H.stayFrames, next.id), next.id).toBe(next.id);
        expect(kept(next.frameStart - H.stayFrames - 0.01, next.id), next.id).toBe(prev.id);
      }
    });

    it("switches at once when fast travel lands at any other stop's hold (real meta.json and camera.json)", () => {
      expect(HOLDS.map((h) => h.id).sort()).toEqual([...ids].sort());
      for (const a of AREAS) {
        for (const b of AREAS) {
          if (a === b) continue;
          expect(liveStopKept(holdOf(b.id), AREAS, ids, a.id, H.stayFrames)?.id, `${a.id} to ${b.id}`).toBe(b.id);
        }
      }
    });

    it("remembers only a stop with maps, and is the frame's own stop without one", () => {
      const f = GATE.frameEnd + 1;
      expect(liveStopKept(f, AREAS, ids, null, H.stayFrames)?.id).toBe(AREAS[1].id);
      expect(liveStopKept(f, AREAS, [AREAS[1].id], "gate", H.stayFrames)?.id).toBe(AREAS[1].id);
      expect(liveStopKept(f, AREAS, ids, "nowhere", H.stayFrames)?.id).toBe(AREAS[1].id);
      // The gate alone has maps: kept just past its end, then nothing (the mirror has none).
      expect(liveStopKept(f, AREAS, ["gate"], "gate", H.stayFrames)?.id).toBe("gate");
      expect(liveStopKept(GATE.frameEnd + H.stayFrames + 1, AREAS, ["gate"], "gate", H.stayFrames)).toBeNull();
      expect(liveStopKept(Number.NaN, AREAS, ids, "gate", H.stayFrames)).toBeNull();
      // No memory at all: liveStopAt.
      for (const a of AREAS) expect(liveStopKept(a.frameEnd + 0.5, AREAS, ids, null, 0)?.id).toBe(liveStopAt(a.frameEnd + 0.5, AREAS, ids)?.id);
    });
  });

  describe("which way the flight goes", () => {
    const r = H.reverseFrames;

    it("is unknown until the frame has moved more than reverseFrames, then follows it", () => {
      let h = liveHeading(LIVE_HEADING_START, 100, r);
      expect(h).toEqual({ dir: 0, mark: 100 });
      expect(liveHeading(h, 100 + r, r)).toBe(h);
      expect(liveHeading(h, 100 - r, r)).toBe(h);
      h = liveHeading(h, 100 + r + 1, r);
      expect(h.dir).toBe(1);
      h = liveHeading(h, 150, r);
      expect(h).toEqual({ dir: 1, mark: 150 });
      expect(liveHeading({ dir: 0, mark: 100 }, 100 - r - 1, r).dir).toBe(-1);
    });

    it("turns only when the frame has gone back more than reverseFrames from the furthest it reached", () => {
      const h: LiveHeading = { dir: 1, mark: 150 };
      expect(liveHeading(h, 150 - r, r)).toBe(h);
      expect(liveHeading(h, 150 - r - 1, r)).toEqual({ dir: -1, mark: 150 - r - 1 });
      const back: LiveHeading = { dir: -1, mark: 150 };
      expect(liveHeading(back, 150 + r, r)).toBe(back);
      expect(liveHeading(back, 140, r)).toEqual({ dir: -1, mark: 140 });
      expect(liveHeading(back, 150 + r + 1, r).dir).toBe(1);
    });

    it("counts a jump as travel, and ignores a frame that is not a number", () => {
      expect(liveHeading({ dir: -1, mark: holdOf("gate") }, holdOf("summit"), r).dir).toBe(1);
      expect(liveHeading({ dir: 1, mark: holdOf("summit") }, holdOf("gate"), r).dir).toBe(-1);
      const h: LiveHeading = { dir: 1, mark: 300 };
      expect(liveHeading(h, Number.NaN, r)).toBe(h);
    });
  });

  it("finds a stop's neighbours in flight order, in any order of the list", () => {
    const shuffled = [...AREAS].reverse();
    for (let i = 0; i < AREAS.length; i++) {
      for (const list of [AREAS, shuffled]) {
        expect(liveNeighbour(AREAS[i].id, 1, list)?.id ?? null, AREAS[i].id).toBe(AREAS[i + 1]?.id ?? null);
        expect(liveNeighbour(AREAS[i].id, -1, list)?.id ?? null, AREAS[i].id).toBe(AREAS[i - 1]?.id ?? null);
      }
    }
    expect(liveNeighbour("nowhere", 1, AREAS)).toBeNull();
  });

  describe("which stop's maps to hold ahead (livePreload)", () => {
    const hold = holdOf("forge");
    /** Lit at the forge (a middle stop), its ramp done, just past its hold heading on, nothing held. */
    const at = (t: Partial<LivePreloadTick> = {}): LivePreloadTick => ({
      lit: "forge",
      litDone: true,
      hold,
      here: "forge",
      frame: hold + H.leadFrames + 1,
      heading: 1,
      held: null,
      ...t,
    });
    const pick = (t: Partial<LivePreloadTick> = {}, maps: readonly string[] = ids, h = H) => livePreload(at(t), AREAS, maps, h);

    it("begins the next stop the way the flight goes, once past the lit stop's hold", () => {
      expect(pick()).toBe("arena");
      expect(pick({ heading: -1, frame: hold - H.leadFrames - 1 })).toBe("mirror");
    });

    it("waits for the hold to be passed, the lit stop's ramp to finish and the way to be known", () => {
      expect(pick({ frame: hold + H.leadFrames })).toBeNull();
      expect(pick({ frame: hold - H.leadFrames - 1 })).toBeNull();
      expect(pick({ litDone: false })).toBeNull();
      expect(pick({ heading: 0 })).toBeNull();
      expect(pick({ hold: null })).toBeNull();
      expect(pick({ lit: null })).toBeNull();
    });

    it("holds only a neighbour with maps, never a stop further on, and nothing when switched off", () => {
      expect(pick({}, ids.filter((id) => id !== "arena"))).toBeNull();
      expect(pick({}, ["forge", "arena"])).toBe("arena");
      expect(pick({}, ids, { ...H, preload: false })).toBeNull();
      expect(pick({ held: "arena" }, ids, { ...H, preload: false })).toBeNull();
    });

    it("keeps held maps while the flight heads there, back before the hold or mid-ramp", () => {
      expect(pick({ held: "arena", frame: hold - 3 })).toBe("arena");
      expect(pick({ held: "arena", litDone: false })).toBe("arena");
    });

    it("keeps them while the frame is past the hold on their side, however the way turns (a rest on the line)", () => {
      expect(pick({ held: "arena", heading: -1, frame: hold + 5 })).toBe("arena");
      expect(pick({ held: "mirror", heading: 1, frame: hold - 5 })).toBe("mirror");
    });

    it("lets them go once the way has turned and the frame has gone back over the hold", () => {
      expect(pick({ held: "arena", heading: -1, frame: hold - 1 })).not.toBe("arena");
      expect(pick({ held: "arena", heading: -1, frame: hold })).not.toBe("arena");
    });

    it("keeps them for the stop about to start, which takes them", () => {
      expect(pick({ lit: null, here: "arena", held: "arena" })).toBe("arena");
      expect(pick({ here: "arena", held: "arena" })).toBe("arena");
    });

    it("lets them go when the flight jumps elsewhere, or their stop is lit with maps of its own", () => {
      expect(pick({ lit: null, here: "summit", held: "arena" })).toBeNull();
      expect(pick({ lit: "summit", here: "summit", hold: holdOf("summit"), frame: holdOf("summit"), held: "arena" })).toBeNull();
      expect(pick({ lit: "arena", here: "arena", hold: holdOf("arena"), frame: holdOf("arena"), held: "arena" })).toBeNull();
    });
  });

  /**
   * A flight along `frames` as live.tsx steps it, simplified: the stop here is lit at once and its
   * ramp is done a frame later; a start takes the held maps when they are its own, else loads them.
   */
  function fly(frames: readonly number[], maps: readonly string[] = ids, h = H) {
    let lit: string | null = null;
    let litDone = false;
    let heading: LiveHeading = LIVE_HEADING_START;
    let held: string | null = null;
    const steps: { frame: number; lit: string | null; held: string | null; took: boolean; loaded: boolean }[] = [];
    for (const frame of frames) {
      const here: string | null = liveStopKept(frame, AREAS, maps, lit, h.stayFrames)?.id ?? null;
      let took = false;
      let loaded = false;
      if (here !== lit) {
        took = here !== null && held === here;
        loaded = here !== null && !took;
        if (took) held = null;
        lit = here;
        litDone = false;
      } else litDone = lit !== null;
      heading = liveHeading(heading, frame, h.reverseFrames);
      held = livePreload({ lit, litDone, hold: lit ? holdOf(lit) : null, here, frame, heading: heading.dir, held }, AREAS, maps, h);
      steps.push({ frame, lit, held, took, loaded });
    }
    return steps;
  }
  const range = (from: number, to: number, step = 1) => {
    const out: number[] = [];
    const n = Math.round(Math.abs(to - from) / step);
    for (let i = 0; i <= n; i++) out.push(from + Math.sign(to - from) * step * i);
    return out;
  };
  const switches = (steps: ReturnType<typeof fly>) => steps.filter((s, i) => i > 0 && s.lit !== steps[i - 1].lit);

  it("a slow scroll from the gate to the mirror and back: each stop's maps are ready before it is reached", () => {
    const [gate, mirror] = [holdOf("gate"), holdOf("mirror")];
    const steps = fly([...range(gate, mirror), ...range(mirror, gate)]);
    // Only the first stop loads its own maps; both changes take the held ones.
    expect(steps.filter((s) => s.loaded).map((s) => s.lit)).toEqual(["gate"]);
    const sw = switches(steps);
    expect(sw.map((s) => [s.lit, s.took])).toEqual([
      ["mirror", true],
      ["gate", true],
    ]);
    // The mirror switches only past the band, and its maps were held well before the line.
    expect(sw[0].frame).toBeGreaterThan(GATE.frameEnd + H.stayFrames);
    const first = steps.find((s) => s.held === "mirror")!;
    expect(first.frame).toBeLessThan(GATE.frameEnd);
    // Never the lit stop's own, and at the turn (the mirror's hold) nothing further is held.
    for (const s of steps) expect(s.held === null || s.held !== s.lit, `${s.frame}`).toBe(true);
    expect(steps.find((s) => s.frame === mirror)!.held).toBeNull();
    expect(steps[steps.length - 1].held).toBeNull();
  });

  it("a rest on the line between two stops, scrolling a little back and forth, reloads nothing", () => {
    for (let i = 1; i < AREAS.length; i++) {
      const [prev, next] = [AREAS[i - 1], AREAS[i]];
      const line = (prev.frameEnd + next.frameStart) / 2;
      const rock = Math.max(H.stayFrames - 1, 0);
      const wiggle = Array.from({ length: 40 }, (_, k) => line + (k % 2 ? rock : -rock) * (0.5 + 0.5 * ((k % 5) / 4)));
      for (const [from, to] of [
        [prev, next],
        [next, prev],
      ]) {
        // Coming in from behind the stop's hold, so the way is known by the time it passes it.
        const dir = Math.sign(line - holdOf(from.id));
        const steps = fly([...range(holdOf(from.id) - dir * (H.reverseFrames + 2), line), ...wiggle]);
        const rest = steps.slice(-wiggle.length);
        // The stop it came from stays lit, and the other's maps stay held: no load, no free.
        expect(new Set(rest.map((s) => s.lit)), `${from.id} at ${line}`).toEqual(new Set([from.id]));
        expect(new Set(rest.map((s) => s.held)), `${from.id} at ${line}`).toEqual(new Set([to.id]));
      }
      // Without the memory the same rocking would light the two stops by turns.
      if (rock > 0.5) expect(new Set(wiggle.map((f) => liveStopAt(f, AREAS, ids)?.id)).size).toBe(2);
    }
  });

  it("a fast-travel jump from the gate to the arena lets the mirror's maps go and lights the arena at once", () => {
    const gate = holdOf("gate");
    const arena = holdOf("arena");
    const steps = fly([...range(gate, gate + 30), arena, arena, arena, arena + 1, arena + 2]);
    const jump = steps.findIndex((s) => s.frame === arena);
    expect(steps[jump - 1]).toMatchObject({ lit: "gate", held: "mirror" });
    expect(steps[jump]).toMatchObject({ lit: "arena", held: null, took: false, loaded: true });
    // At rest at the arena's hold nothing is loaded ahead; on past it, the next stop is.
    expect(steps[jump + 2].held).toBeNull();
    expect(steps[steps.length - 1].held).toBe(liveNeighbour("arena", 1, AREAS)!.id);
  });

  it("with preload off, every stop loads its own maps and nothing is held", () => {
    const off = { ...H, preload: false };
    const steps = fly([...range(holdOf("gate"), holdOf("forge")), ...range(holdOf("forge"), holdOf("gate"))], ids, off);
    expect(steps.every((s) => s.held === null)).toBe(true);
    expect(switches(steps).every((s) => s.loaded)).toBe(true);
  });

  describe("what fast travel's ink waits for (liveComing)", () => {
    const lit = (stop: string, fading = false) => ({ stop, fading });

    it("waits while the stop here, which has maps, is not lit with its mix at 1", () => {
      expect(liveComing({ here: "gate", failed: false, lit: null, mix: 0 })).toBe(true);
      expect(liveComing({ here: "gate", failed: false, lit: lit("gate"), mix: 0.6 })).toBe(true);
      expect(liveComing({ here: "gate", failed: false, lit: lit("gate", true), mix: 1 })).toBe(true);
      // Another stop still lit (its fade under way): the one here is still to come.
      expect(liveComing({ here: "gate", failed: false, lit: lit("forge"), mix: 1 })).toBe(true);
    });

    it("does not wait once it is lit, nor for a stop without maps or one whose start failed", () => {
      expect(liveComing({ here: "gate", failed: false, lit: lit("gate"), mix: 1 })).toBe(false);
      expect(liveComing({ here: null, failed: false, lit: null, mix: 0 })).toBe(false);
      expect(liveComing({ here: "gate", failed: true, lit: null, mix: 0 })).toBe(false);
    });
  });

  describe("what the loading screen's wait lets go of (liveArriving)", () => {
    it("is live light waiting only for files still downloading", () => {
      // Nothing under way yet: the list of stops is being read, or the stop's set is not here.
      expect(liveArriving({ coming: true, starting: false, lit: false, fetching: 0 })).toBe(true);
      // A start still fetching its index, its maps or the view table (or the maps loaded ahead it took).
      expect(liveArriving({ coming: true, starting: true, lit: false, fetching: 3 })).toBe(true);
      expect(liveArriving({ coming: true, starting: true, lit: true, fetching: 1 })).toBe(true);
    });

    it("is not work on what has arrived, nor live light that is not coming", () => {
      // Every file in: decoding, uploads, shadow maps, links.
      expect(liveArriving({ coming: true, starting: true, lit: false, fetching: 0 })).toBe(false);
      // Lit and ramping up, or another stop fading out first.
      expect(liveArriving({ coming: true, starting: false, lit: true, fetching: 0 })).toBe(false);
      // Lit at the stop already, no maps here, or failed.
      expect(liveArriving({ coming: false, starting: false, lit: false, fetching: 0 })).toBe(false);
      expect(liveArriving({ coming: false, starting: true, lit: false, fetching: 2 })).toBe(false);
    });
  });
});

describe("the mix's ease", () => {
  it("ramps from 0 to 1 as before (smoothstep) and fades back from where it is", () => {
    for (const k of [0, 0.1, 0.25, 0.5, 0.8, 1]) expect(liveEase(0, 1, k)).toBeCloseTo(k * k * (3 - 2 * k), 12);
    expect(liveEase(0.6, 0, 0)).toBe(0.6);
    expect(liveEase(0.6, 0, 1)).toBe(0);
    expect(liveEase(0.6, 0, 0.5)).toBeCloseTo(0.3, 12);
    expect(liveEase(0.4, 1, 1)).toBe(1);
    // Held to the ends outside 0..1.
    expect(liveEase(0, 1, -1)).toBe(0);
    expect(liveEase(0, 1, 3)).toBe(1);
  });
});

describe("liveAtlasOf", () => {
  it("finds the atlas in a baked material's name", () => {
    expect(liveAtlasOf("baked.gate_A0")).toBe("gate_A0");
    expect(liveAtlasOf("baked.gate_A0.detail.paving")).toBe("gate_A0");
    expect(liveAtlasOf("baked.gate_A0.detail.rock")).toBe("gate_A0");
    expect(liveAtlasOf("baked.gate_A0.surface.metal")).toBe("gate_A0");
    expect(liveAtlasOf("baked.gate_A1.detail.tiles.surface.glaze")).toBe("gate_A1");
    expect(liveAtlasOf("baked.gate_A12")).toBe("gate_A12");
  });

  it("keeps vertex-coloured pieces, glow surfaces and everything else baked", () => {
    expect(liveAtlasOf("baked.vc")).toBeNull();
    expect(liveAtlasOf("baked.vc.surface.metal")).toBeNull();
    expect(liveAtlasOf("baked.gate_A0.glow.rune_cyan")).toBeNull();
    expect(liveAtlasOf("baked.gate_A0.glow.paper_screen_lit")).toBeNull();
    expect(liveAtlasOf("trees.mesh.gate")).toBeNull();
    expect(liveAtlasOf("baked.gate")).toBeNull();
    expect(liveAtlasOf("gate_A0")).toBeNull();
  });
});

describe("liveClassOf", () => {
  it("takes the reflective tag first, then the detail class", () => {
    expect(liveClassOf("tiles", "glaze")).toBe("glaze");
    expect(liveClassOf(undefined, "metal")).toBe("metal");
    expect(liveClassOf(undefined, "iron")).toBe("metal");
    expect(liveClassOf("paving", null)).toBe("paving");
    expect(liveClassOf("rock", null)).toBe("rock");
    expect(liveClassOf("ground", undefined)).toBe("ground");
    expect(liveClassOf("tiles", null)).toBe("tiles");
    expect(liveClassOf(undefined, null)).toBe("default");
    expect(liveClassOf("moss", "chrome")).toBe("default");
  });

  it("has a shine for every class, roughness held off zero", () => {
    for (const c of LIVE_CLASSES) {
      const v = liveShineVec(LIVE_LOOK.classes[c]);
      expect(v[0]).toBeGreaterThanOrEqual(0.05);
      expect(v[0]).toBeLessThanOrEqual(1);
      expect(v[1]).toBeGreaterThanOrEqual(0);
      expect(v[1]).toBeLessThanOrEqual(1);
    }
    expect(liveShineVec({ roughness: 0, f0: 2, tint: -1, bump: [1, 0, 1, 0] })).toEqual([0.05, 1, 0]);
  });

  it("gives every class two layers of bumps, and only the default class lacquer", () => {
    for (const c of LIVE_CLASSES) {
      const b = LIVE_LOOK.classes[c].bump;
      expect(b, c).toHaveLength(4);
      expect(b.every(Number.isFinite), c).toBe(true);
      // Sizes (m) above 0, slopes not below it.
      expect(b[0], c).toBeGreaterThan(0);
      expect(b[2], c).toBeGreaterThan(0);
      expect(b[1], c).toBeGreaterThanOrEqual(0);
      expect(b[3], c).toBeGreaterThanOrEqual(0);
    }
    expect(LIVE_CLASSES.filter((c) => LIVE_LOOK.classes[c].paint)).toEqual(["default"]);
  });

  it("hands the shader 1 / size and the slope of each bump layer", () => {
    for (const c of LIVE_CLASSES) {
      const [m1, a1, m2, a2] = LIVE_LOOK.classes[c].bump;
      expect(close(liveBumpVec(LIVE_LOOK.classes[c]), [1 / m1, a1, 1 / m2, a2], 1e-12), c).toBe(true);
    }
    // A size of 0 or less stays finite.
    const flat = liveBumpVec({ ...LIVE_LOOK.classes.default, bump: [0, 0.1, -1, 0.2] });
    expect(flat.every(Number.isFinite)).toBe(true);
    expect([flat[1], flat[3]]).toEqual([0.1, 0.2]);
  });
});

describe("the shadow map's light space", () => {
  // The gate's two maps, as live.tsx builds them, and the biggest stop's key map.
  const key = boxAt(GATE.footprint, "key");
  // Without aheadM the box reaches depthM / 2 each way round the centre.
  const half: LiveShadowBox = { radiusM: key.radiusM, depthM: key.depthM };
  const looks: [string, LiveShadowBox][] = [
    ["half", half],
    ["key", key],
    ["sun", boxAt(GATE.footprint, "sun")],
    ["key, biggest stop", boxAt(Math.max(...AREAS.map((a) => a.footprint)), "key")],
  ];
  const ahead = looks.slice(1);
  const centre: Vec3 = [0, 40, 0];
  const dirs: Vec3[] = [
    parseLiveIndex(sample())!.light.key.dir,
    [-0.94397, 0.12187, 0.30671],
    [0, 1, 0],
    [0.3, 0.9, -0.3],
  ];
  /** The point t metres from the centre toward the lamp. */
  const along = (d: Vec3, t: number): Vec3 => {
    const len = Math.hypot(...d);
    return [centre[0] + (d[0] / len) * t, centre[1] + (d[1] / len) * t, centre[2] + (d[2] / len) * t];
  };

  it("builds an orthonormal frame with depth along the light's travel", () => {
    for (const d of dirs) {
      const len = Math.hypot(...d);
      const n: Vec3 = [d[0] / len, d[1] / len, d[2] / len];
      const { right, up, forward } = liveLightBasis(d);
      const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
      expect(dot(forward, n)).toBeCloseTo(-1, 9);
      for (const v of [right, up, forward]) expect(Math.hypot(...v)).toBeCloseTo(1, 9);
      expect(dot(right, up)).toBeCloseTo(0, 9);
      expect(dot(right, forward)).toBeCloseTo(0, 9);
      expect(dot(up, forward)).toBeCloseTo(0, 9);
    }
  });

  it("maps the centre to the middle across the map and a point radiusM to the side to its edge", () => {
    for (const [name, box] of looks) {
      for (const d of dirs) {
        const m = liveShadowMatrix(d, centre, box);
        expect(m).toHaveLength(16);
        const c = liveProject(m, centre);
        expect(close([c[0], c[1]], [0, 0]), name).toBe(true);
        const { right, up } = liveLightBasis(d);
        const side: Vec3 = [centre[0] + right[0] * box.radiusM, centre[1] + right[1] * box.radiusM, centre[2] + right[2] * box.radiusM];
        expect(close(liveProject(m, side), [1, 0, c[2]]), name).toBe(true);
        const top: Vec3 = [centre[0] - up[0] * box.radiusM, centre[1] - up[1] * box.radiusM, centre[2] - up[2] * box.radiusM];
        expect(close(liveProject(m, top), [0, -1, c[2]]), name).toBe(true);
      }
    }
    // Half each way, the centre is the middle in depth too.
    for (const d of dirs) expect(close(liveProject(liveShadowMatrix(d, centre, half), centre), [0, 0, 0])).toBe(true);
  });

  it("without aheadM, puts depth along the lamp: nearer the lamp is smaller, depthM / 2 each way spans -1..1", () => {
    for (const d of dirs) {
      const m = liveShadowMatrix(d, centre, half);
      const toward = liveProject(m, along(d, 10));
      const away = liveProject(m, along(d, -10));
      expect(toward[2]).toBeLessThan(0);
      expect(away[2]).toBeGreaterThan(0);
      // Along the lamp only depth changes.
      expect(Math.abs(toward[0]) + Math.abs(toward[1])).toBeLessThan(1e-9);
      expect(liveProject(m, along(d, half.depthM / 2))[2]).toBeCloseTo(-1, 9);
      expect(liveProject(m, along(d, -half.depthM / 2))[2]).toBeCloseTo(1, 9);
      // A caster above the receiver along the lamp is nearer: its stored depth (z / 2 + 0.5) is smaller.
      expect(liveProject(m, along(d, 3))[2] * 0.5 + 0.5).toBeLessThan(liveProject(m, along(d, 0))[2] * 0.5 + 0.5);
    }
  });

  it("with aheadM, ends the box aheadM past the centre and reaches depthM - aheadM toward the lamp", () => {
    for (const [name, box] of ahead) {
      const a = box.aheadM!;
      for (const d of dirs) {
        const m = liveShadowMatrix(d, centre, box);
        // Away from the lamp: the far plane. Toward it: the near plane.
        expect(liveProject(m, along(d, -a))[2], name).toBeCloseTo(1, 9);
        expect(liveProject(m, along(d, box.depthM - a))[2], name).toBeCloseTo(-1, 9);
        // So the centre sits at 1 - 2 * aheadM / depthM in depth.
        const c = liveProject(m, centre);
        expect(c[2], name).toBeCloseTo(1 - (2 * a) / box.depthM, 9);
        // Nearer the lamp is still smaller, and along the lamp only depth changes.
        const toward = liveProject(m, along(d, 3));
        expect(toward[2], name).toBeLessThan(c[2]);
        expect(Math.abs(toward[0]) + Math.abs(toward[1]), name).toBeLessThan(1e-9);
      }
    }
  });

  it("moves the box's middle toward the lamp by depthM / 2 - aheadM", () => {
    for (const d of dirs) {
      expect(close(liveShadowBoxCentre(d, centre, half), centre)).toBe(true);
      // aheadM of half the depth is the box without it.
      expect(close(liveShadowBoxCentre(d, centre, { ...half, aheadM: half.depthM / 2 }), centre)).toBe(true);
      for (const [name, box] of ahead) {
        const back = box.depthM / 2 - box.aheadM!;
        expect(close(liveShadowBoxCentre(d, centre, box), along(d, back)), name).toBe(true);
        // The lamp's direction need not be unit length.
        const longer: Vec3 = [d[0] * 3, d[1] * 3, d[2] * 3];
        expect(close(liveShadowBoxCentre(longer, centre, box), along(d, back)), name).toBe(true);
      }
    }
  });

  it("gives its inverse scale in metres", () => {
    const size = LIVE_LOOK.shadow.size;
    const s = liveShadowScale(key, 6, size);
    expect(s.metresPerUv).toBe(2 * key.radiusM);
    expect(s.metresPerDepth).toBe(key.depthM);
    // A 6 degree lamp: a blocker 10 m off gives a penumbra about a metre wide.
    expect(s.penumbraPerM * 10).toBeCloseTo(1.048, 3);
    expect(liveShadowScale(key, 0, size).penumbraPerM).toBe(0);
    // One texel: the map's width over its side.
    expect(s.texelM).toBeCloseTo((2 * key.radiusM) / size, 12);
    // The matrix's own scale agrees: one UV unit (two NDC units) across is 2 * radiusM.
    const m = liveShadowMatrix([0, 1, 0], [0, 0, 0], key);
    const { right } = liveLightBasis([0, 1, 0]);
    const p = liveProject(m, [right[0] * s.metresPerUv * 0.5, right[1] * s.metresPerUv * 0.5, right[2] * s.metresPerUv * 0.5]);
    expect(p[0] * 0.5 + 0.5).toBeCloseTo(1, 12);
  });

  it("spreads the PCSS taps over the unit disc", () => {
    for (const n of [LIVE_LOOK.shadow.blockerTaps, LIVE_LOOK.shadow.pcfTaps]) {
      const pts = liveDisc(n);
      expect(pts).toHaveLength(n);
      for (const [x, y] of pts) expect(Math.hypot(x, y)).toBeLessThanOrEqual(1);
      const mean = pts.reduce((a, [x, y]) => [a[0] + x / n, a[1] + y / n], [0, 0]);
      expect(Math.hypot(mean[0], mean[1])).toBeLessThan(0.1);
      // The outer ring is reached.
      expect(Math.max(...pts.map(([x, y]) => Math.hypot(x, y)))).toBeGreaterThan(0.9);
    }
  });
});

describe("the two shadow looks", () => {
  const looks = [
    ["key", LIVE_LOOK.shadow],
    ["sun", LIVE_LOOK.sunShadow],
  ] as const;

  it("have sane numbers", () => {
    for (const [name, s] of looks) {
      expect(Number.isInteger(s.size) && s.size > 0, name).toBe(true);
      expect(s.marginM, name).toBeGreaterThanOrEqual(0);
      expect(s.minPenumbraM, name).toBeLessThan(s.maxPenumbraM);
      expect(s.searchM, name).toBeGreaterThan(0);
      expect(s.aheadM, name).toBeGreaterThanOrEqual(0);
      expect(s.aheadM, name).toBeLessThan(s.depthM);
      expect(s.biasM, name).toBeGreaterThanOrEqual(0);
      expect(s.normalBiasM, name).toBeGreaterThanOrEqual(0);
      expect(s.slopeMax, name).toBeGreaterThan(0);
      // The narrowest penumbra is at least one texel of its map at every stop (livePenumbra: a
      // texel floor of a texel or more), the widest more than that.
      expect(s.minPenumbraTexels, name).toBeGreaterThanOrEqual(1);
      expect(s.maxPenumbraTexels, name).toBeGreaterThan(s.minPenumbraTexels);
    }
    // The blocker search's coarse map: a whole factor smaller, still more than a texel. One factor
    // for both maps (the shader has one).
    const c = LIVE_LOOK.shadow.coarse;
    expect(Number.isInteger(c) && c >= 1).toBe(true);
    for (const [name, s] of looks) expect(s.size / c, name).toBeGreaterThanOrEqual(1);
    // The maps reach past where live fades out: nothing live is drawn unshaded.
    for (const a of AREAS) {
      const b = liveStopBox(a.footprint, LIVE_LOOK);
      expect(b.radiusM, a.id).toBeGreaterThanOrEqual(b.toM);
      expect(b.sunRadiusM, a.id).toBeGreaterThanOrEqual(b.toM);
    }
    // The sun stands lower: what shades the stop can be much farther off.
    expect(LIVE_LOOK.sunShadow.depthM).toBeGreaterThan(LIVE_LOOK.shadow.depthM);
  });
});

describe("Blender's view transform table (LIVE_VIEW)", () => {
  const n = LIVE_VIEW.size;
  const file = path.resolve(__dirname, "../../../public/sect/full", LIVE_VIEW.file);

  it("is on disk at the size the shader reads", () => {
    expect(Number.isInteger(n) && n >= 2).toBe(true);
    expect(LIVE_VIEW.lo).toBeLessThan(LIVE_VIEW.hi);
    expect(readFileSync(file).length).toBe(n * n * n * 4);
  });

  it("keeps greys grey, rising from black to white", () => {
    const b = readFileSync(file);
    // Red fastest, then green, then blue.
    const grey = (i: number) => {
      const k = ((i * n + i) * n + i) * 4;
      return [b[k], b[k + 1], b[k + 2], b[k + 3]];
    };
    let last = -1;
    for (let i = 0; i < n; i++) {
      const [r, g, bl, a] = grey(i);
      expect(Math.max(r, g, bl) - Math.min(r, g, bl), `grey ${i}`).toBeLessThanOrEqual(2);
      expect(a, `alpha ${i}`).toBe(255);
      expect(g, `rising at ${i}`).toBeGreaterThanOrEqual(last);
      last = g;
    }
    expect(grey(0)[1]).toBeLessThanOrEqual(2);
    expect(grey(n - 1)[1]).toBeGreaterThanOrEqual(253);
  });

  it("is read in the shader with the same numbers", () => {
    const pars = liveParsGlsl();
    expect(pars).toContain("uniform highp sampler3D tSectLiveView;");
    const start = pars.indexOf("vec3 sectLiveView( vec3 c ) {");
    expect(start).toBeGreaterThan(0);
    const body = pars.slice(start, pars.indexOf("\n}", start));
    const f = glslFloat;
    // Each axis is log2 of the linear value from 2^lo to 2^hi.
    expect(body).toContain(`log2( max( c, vec3( ${f(Math.pow(2, LIVE_VIEW.lo))} ) ) ) - ( ${f(LIVE_VIEW.lo)} ) ) / ${f(LIVE_VIEW.hi - LIVE_VIEW.lo)}, 0.0, 1.0 )`);
    // 0..1 lands on the first and last texels' centres: half a texel in from each edge.
    // At an explicit level: it is read inside the live branch.
    expect(body).toContain(`textureLod( tSectLiveView, t * ${f((n - 1) / n)} + ${f(0.5 / n)}, 0.0 )`);
  });

  it("agrees with the tool that writes it", () => {
    const py = readFileSync(path.resolve(__dirname, "../../../../blender/xianxia-sect/tools/sect_view_lut.py"), "utf8");
    const ends = /^LO, HI = (\S+), (\S+)/m.exec(py);
    expect(ends).not.toBeNull();
    expect(Number(ends![1])).toBe(LIVE_VIEW.lo);
    expect(Number(ends![2])).toBe(LIVE_VIEW.hi);
    expect(py).toMatch(new RegExp(`"--size", type=int, default=${n}\\b`));
  });
});

describe("?live= and the tier", () => {
  it("reads the URL switch as ?veg= is read", () => {
    expect(parseLiveParam("")).toBeNull();
    expect(parseLiveParam("?live=0")).toBe("off");
    expect(parseLiveParam("?live=off")).toBe("off");
    expect(parseLiveParam("?live=1")).toBe("on");
    expect(parseLiveParam("?live=on")).toBe("on");
    expect(parseLiveParam("?debug=1&live=1")).toBe("on");
    expect(parseLiveParam("?live=0&tier=high")).toBe("off");
    expect(parseLiveParam("?live=2")).toBeNull();
    expect(parseLiveParam("?live=")).toBeNull();
    expect(parseLiveParam("?alive=1")).toBeNull();
    expect(parseLiveParam("#live=1")).toBeNull();
  });

  it("is on at High only unless the switch says otherwise", () => {
    expect(liveOn(tierQuality("high", 1), null)).toBe(true);
    expect(liveOn(tierQuality("mid", 1), null)).toBe(false);
    expect(liveOn(tierQuality("low", 1), null)).toBe(false);
    expect(liveOn(tierQuality("high", 1), "off")).toBe(false);
    expect(liveOn(tierQuality("low", 1), "on")).toBe(true);
    expect(liveOn({ ...tierQuality("high", 1), liveLight: undefined }, null)).toBe(false);
    expect(LIVE_LOOK.on).toEqual({ low: false, mid: false, high: true });
  });
});

describe("the uniform values", () => {
  it("turns the lamps, the ambient scale and the post into what the shader reads", () => {
    const ix = parseLiveIndex(sample()) as LiveIndex;
    const L = LIVE_LOOK;
    const box = liveStopBox(GATE.footprint, L);
    const v = liveValues(ix, L, box);
    expect(close(v.sunE, [8 * L.sunGain, 0.52 * 8 * L.sunGain, 0.23 * 8 * L.sunGain], 1e-12)).toBe(true);
    expect(close(v.keyE, [2.4 * L.keyGain, 0.72 * 2.4 * L.keyGain, 0.5 * 2.4 * L.keyGain], 1e-12)).toBe(true);
    expect(v.ambient).toBeCloseTo(2 * L.ambientGain, 12);
    expect(v.exposure).toBeCloseTo(Math.pow(2, 1.2 + L.exposureBias), 12);
    expect(v.saturation).toBeCloseTo(1.15 * L.saturation, 12);
    expect(v.gain).toBe(L.gain);
    expect(v.specular).toBe(L.specular);
    // The stop's own blend: at the gate today's 45 to 72 m.
    expect(v.blend).toEqual([box.fromM, box.toM]);
    expect(v.blend).toEqual([45, 72]);
    for (const c of v.bounce) expect(c).toBeGreaterThan(0);
    // Lacquer: (saturation from, to, its roughness, its reflectance).
    expect(v.paint[0]).toBe(LIVE_LOOK.paint.sat[0]);
    expect(v.paint[1]).toBeGreaterThan(v.paint[0]);
    expect(v.paint[2]).toBeGreaterThanOrEqual(0.05);
    expect(v.paint[2]).toBeLessThanOrEqual(1);
    expect(v.paint[3]).toBe(LIVE_LOOK.paint.f0);
    // The sky sheen's amount, 1 / the open-sky level, the bumps' strength.
    expect(v.surface[0]).toBe(LIVE_LOOK.sky.amount);
    expect(v.surface[1]).toBeCloseTo(1 / LIVE_LOOK.sky.open, 12);
    expect(v.surface[2]).toBe(LIVE_LOOK.bump);
    // The tiles' roll and where it fades.
    expect(v.tiles).toEqual([LIVE_LOOK.tiles.roll, LIVE_LOOK.tiles.fade[0], LIVE_LOOK.tiles.fade[1]]);
    // The slabs' tilt, the bevel's width and its slope.
    expect(v.paving).toEqual([LIVE_LOOK.paving.tilt, LIVE_LOOK.paving.bevelM, LIVE_LOOK.paving.bevel]);
    // The sample says nothing of its ambient map: radiance, used as it is, and no baked shadow in it.
    expect(v.ambientIrr).toBe(0);
    expect(v.vis).toEqual([0, L.bakedShadow.nearM, L.bakedShadow.farM, L.bakedShadow.missing]);
    // Nor a soft map, nor what the rebuilt bake needs: no detail.
    expect(v.graze).toEqual(L.bakedShadow.graze);
    expect(v.close).toEqual([...L.bakedShadow.close, 0]);
    expect(v.detail).toEqual([0, L.detail.min, L.detail.max, L.detail.floor]);
    expect(v.caps).toEqual([L.bumpCap, L.shineCap]);
    // The bake's own strength and post: the look's gains undone, the index's exposure and saturation.
    expect(close(v.bakeGain, [1 / L.sunGain, 1 / L.keyGain, 1 / L.ambientGain], 1e-12)).toBe(true);
    expect(close(v.bakePost, [1, Math.pow(2, 1.2), 1.15], 1e-12)).toBe(true);
  });

  it("gives the detail its amount only when the maps hold the bake's shadow and its bounce", () => {
    const box = liveStopBox(GATE.footprint, LIVE_LOOK);
    const D = LIVE_LOOK.detail;
    for (const shadow of [false, true]) {
      for (const bounce of [false, true]) {
        const j = sample();
        if (shadow) j.ambientAlpha = "visibility";
        j.ambientBounce = bounce;
        const v = liveValues(parseLiveIndex(j) as LiveIndex, LIVE_LOOK, box);
        const want = shadow && bounce ? Math.min(Math.max(D.amount, 0), 1) : 0;
        expect(v.detail, `${shadow} ${bounce}`).toEqual([want, D.min, D.max, D.floor]);
      }
    }
  });

  it("turns the soft map on only when the index has both the bake's shadow and where it is soft", () => {
    const box = liveStopBox(GATE.footprint, LIVE_LOOK);
    const C = LIVE_LOOK.bakedShadow.close;
    for (const shadow of [false, true]) {
      for (const soft of [false, true]) {
        const j = sample();
        if (shadow) j.ambientAlpha = "visibility";
        if (soft) j.normalAlpha = "soft";
        const v = liveValues(parseLiveIndex(j) as LiveIndex, LIVE_LOOK, box);
        expect(v.close, `${shadow} ${soft}`).toEqual([C[0], C[1], shadow && soft ? 1 : 0]);
      }
    }
  });

  it("holds the new knobs to what the shader can use", () => {
    const ix = parseLiveIndex(sample()) as LiveIndex;
    const box = liveStopBox(GATE.footprint, LIVE_LOOK);
    const look = structuredClone(LIVE_LOOK);
    look.bakedShadow = { ...look.bakedShadow, graze: [0.3, 0.3], close: [2, 1] };
    look.detail = { amount: 3, min: 2, max: 1, floor: 0 };
    look.bumpCap = 0.5;
    look.shineCap = -1;
    look.sunGain = 0;
    const v = liveValues(ix, look, box);
    // Each smoothstep keeps a width.
    expect(v.graze[0]).toBe(0.3);
    expect(v.graze[1]).toBeGreaterThan(v.graze[0]);
    expect(v.close[0]).toBe(2);
    expect(v.close[1]).toBeGreaterThan(v.close[0]);
    // The range never turns over, the floor stays above 0.
    expect(v.detail[2]).toBeGreaterThanOrEqual(v.detail[1]);
    expect(v.detail[3]).toBeGreaterThan(0);
    // The amount is 0 here (no baked shadow), and held to 0..1 where it counts.
    expect(v.detail[0]).toBe(0);
    const j = sample();
    j.ambientAlpha = "visibility";
    j.ambientBounce = true;
    // A lamp turned off (sunGain 0 here) cannot be turned back into the bake's: the detail is off.
    expect(liveValues(parseLiveIndex(j) as LiveIndex, look, box).detail[0]).toBe(0);
    expect(liveValues(parseLiveIndex(j) as LiveIndex, { ...look, sunGain: 1 }, box).detail[0]).toBe(1);
    // Bumps may always keep the flat face's own light; the shine's share is never negative.
    expect(v.caps).toEqual([1, 0]);
    // A lamp turned off stays finite.
    expect(v.bakeGain.every(Number.isFinite)).toBe(true);
  });

  it("has sane numbers for the detail and the caps", () => {
    const D = LIVE_LOOK.detail;
    expect(D.amount).toBeGreaterThanOrEqual(0);
    expect(D.amount).toBeLessThanOrEqual(1);
    // The range holds 1: a texel the maps rebuild exactly is left as it is.
    expect(D.min).toBeGreaterThan(0);
    expect(D.min).toBeLessThan(1);
    expect(D.max).toBeGreaterThan(1);
    expect(D.floor).toBeGreaterThan(0);
    expect(LIVE_LOOK.bumpCap).toBeGreaterThanOrEqual(1);
    expect(LIVE_LOOK.shineCap).toBeGreaterThan(0);
  });

  it("tells the shader when the ambient map is light without the surface colour", () => {
    const box = liveStopBox(GATE.footprint, LIVE_LOOK);
    const irr = sample();
    irr.ambientKind = "irradiance";
    const a = liveValues(parseLiveIndex(irr) as LiveIndex, LIVE_LOOK, box);
    const b = liveValues(parseLiveIndex(sample()) as LiveIndex, LIVE_LOOK, box);
    expect(a.ambientIrr).toBe(1);
    expect(b.ambientIrr).toBe(0);
    // Nothing else changes with it.
    expect({ ...a, ambientIrr: 0 }).toEqual(b);
  });

  it("follows the knobs", () => {
    const ix = parseLiveIndex(sample()) as LiveIndex;
    const look = structuredClone(LIVE_LOOK);
    look.sunGain = 0.5;
    look.keyGain = 0;
    look.ambientGain = 1.5;
    look.exposureBias = -1;
    look.saturation = 0.5;
    look.bounce.amount = 0;
    look.blend = { padM: 10, fadeM: 0 };
    look.paint = { sat: [0.6, 0.6], roughness: 0, f0: 0.07 };
    look.sky = { amount: 0.5, open: 0 };
    look.bump = 0;
    look.tiles = { roll: 0.3, fade: [0.4, 0.4] };
    look.paving = { tilt: 0.01, bevelM: 0, bevel: 0.3 };
    const v = liveValues(ix, look, liveStopBox(40, look));
    expect(v.blend[0]).toBe(50);
    expect(v.sunE[0]).toBe(4);
    expect(v.keyE).toEqual([0, 0, 0]);
    expect(v.ambient).toBe(3);
    expect(v.exposure).toBeCloseTo(Math.pow(2, 0.2), 12);
    expect(v.saturation).toBeCloseTo(0.575, 12);
    expect(v.bounce).toEqual([0, 0, 0]);
    // A blend with no width still fades (smoothstep needs from < to).
    expect(v.blend[1]).toBeGreaterThan(v.blend[0]);
    // So does a lacquer range with no width; its roughness is held off 0.
    expect(v.paint[1]).toBeGreaterThan(v.paint[0]);
    expect(v.paint[2]).toBe(0.05);
    expect(v.paint[3]).toBe(0.07);
    // No open sky at all stays finite; no bumps is 0.
    expect(Number.isFinite(v.surface[1])).toBe(true);
    expect(v.surface[0]).toBe(0.5);
    expect(v.surface[2]).toBe(0);
    // A tiles fade with no width still fades.
    expect(v.tiles[0]).toBe(0.3);
    expect(v.tiles[1]).toBe(0.4);
    expect(v.tiles[2]).toBeGreaterThan(v.tiles[1]);
    // A bevel with no width keeps one (the shader's smoothstep needs it).
    expect(v.paving[0]).toBe(0.01);
    expect(v.paving[1]).toBeGreaterThan(0);
    expect(v.paving[2]).toBe(0.3);
  });
});

describe("the bake's post grade (scene-linear part)", () => {
  it("weights shadows, midtones and highlights as Blender's Color Correction node does", () => {
    expect(liveLevelWeights(0)).toEqual([1, 0, 0]);
    expect(liveLevelWeights(0.4)).toEqual([0, 1, 0]);
    expect(liveLevelWeights(2)).toEqual([0, 0, 1]);
    const mid = liveLevelWeights(LIVE_LOOK.grade.midStart);
    expect(mid[0]).toBeCloseTo(0.5, 12);
    expect(mid[1]).toBeCloseTo(0.5, 12);
    for (const l of [0, 0.15, 0.25, 0.45, 0.65, 0.75, 1]) {
      const w = liveLevelWeights(l);
      expect(w[0] + w[1] + w[2]).toBeCloseTo(1, 12);
    }
  });

  it("leaves a grey grey (bar the CDL's tint) and saturates colour", () => {
    const grey = liveGradeLinear([0.4, 0.4, 0.4], 1.15);
    expect(grey[0]).toBeGreaterThan(grey[2]);
    const flat = liveGradeLinear([0.4, 0.4, 0.4], 1.15, 1, { ...LIVE_LOOK.grade, slope: [1, 1, 1], offset: [0, 0, 0] });
    expect(close(flat, [0.4, 0.4, 0.4], 1e-12)).toBe(true);
    const warm = liveGradeLinear([0.6, 0.4, 0.2], 1.15);
    const plain = liveGradeLinear([0.6, 0.4, 0.2], 1);
    expect(warm[2]).toBeLessThan(plain[2]);
    expect(liveGradeLinear([0.6, 0.4, 0.2], 3).every((c) => c >= 0)).toBe(true);
  });
});

describe("GLSL", () => {
  const pars = liveParsGlsl();
  const apply = liveApplyGlsl();
  const sheen = liveSheenGlsl();
  /** A function in the pars, from its signature to its closing brace. */
  const fn = (sig: string) => {
    const i = pars.indexOf(sig);
    expect(i, sig).toBeGreaterThan(0);
    return pars.slice(i, pars.indexOf("\n}", i) + 2);
  };
  /** Screen derivatives, or a lookup that takes its level from them. */
  const derivative = /dFd[xy]|fwidth|texture2D\(|texture\(/;

  it("declares every uniform the page sets, once, and no other", () => {
    const want = [
      "sampler2D tSectLiveAlbedo",
      "sampler2D tSectLiveAmbient",
      "sampler2D tSectLiveNormal",
      "float uSectLiveMix",
      "vec3 uSectLiveSunDir",
      "vec3 uSectLiveSunE",
      "vec3 uSectLiveKeyDir",
      "vec3 uSectLiveKeyE",
      "float uSectLiveAmbient",
      "float uSectLiveAmbientIrr",
      "vec4 uSectLiveVis",
      "vec2 uSectLiveGraze",
      "vec3 uSectLiveClose",
      "vec4 uSectLiveDetail",
      "vec3 uSectLiveBakeGain",
      "vec3 uSectLiveBakePost",
      "vec2 uSectLiveCaps",
      "vec3 uSectLiveBounce",
      "float uSectLiveGain",
      "float uSectLiveExposure",
      "float uSectLiveSat",
      "float uSectLiveSpecular",
      "vec4 uSectLiveSpec",
      "vec4 uSectLiveBump",
      "float uSectLiveLift",
      "vec4 uSectLivePaint",
      "vec3 uSectLiveSurface",
      "vec3 uSectLiveTiles",
      "vec3 uSectLivePaving",
      "vec3 uSectLiveCentre",
      "vec2 uSectLiveBlend",
      // Each lamp's map through the GPU's depth compare, and its coarse plain copy.
      "highp sampler2DShadow tSectLiveShadow",
      "highp sampler2D tSectLiveShadowB",
      "float uSectLiveShadowOn",
      "mat4 uSectLiveShadowMatrix",
      "vec4 uSectLiveShadowMap",
      "vec4 uSectLiveShadowBias",
      "vec2 uSectLiveShadowPen",
      "highp sampler2DShadow tSectLiveSunShadow",
      "highp sampler2D tSectLiveSunShadowB",
      "float uSectLiveSunShadowOn",
      "mat4 uSectLiveSunShadowMatrix",
      "vec4 uSectLiveSunShadowMap",
      "vec4 uSectLiveSunShadowBias",
      "vec2 uSectLiveSunShadowPen",
      "highp sampler3D tSectLiveView",
    ];
    for (const u of want) expect(pars, u).toContain(`uniform ${u};`);
    const names = [...pars.matchAll(/^uniform (?:highp )?\w+ (\w+);$/gm)].map((m) => m[1]);
    expect(new Set(names).size).toBe(names.length);
    expect([...names].sort()).toEqual(want.map((u) => u.split(" ").pop()!).sort());
    expect(pars).toContain("#define SECT_LIVE");
  });

  it("declares each function before anything calls it", () => {
    const defs = [...pars.matchAll(/^(?:float|vec[234]|mat[234]) (sectLive\w+)\(/gm)].map((m) => m[1]);
    expect(defs).toEqual(
      expect.arrayContaining([
        "sectLiveView",
        "sectLiveShadowAt",
        "sectLiveBakeShare",
        "sectLiveGraze",
        "sectLiveShadow",
        "sectLiveSunShadow",
        "sectLiveHash",
        "sectLiveNoised",
        "sectLiveBumped",
        "sectLiveGgx",
        "sectLiveRadiance",
        "sectLiveBaked",
        "sectLiveDetail",
        "sectLivePostBy",
        "sectLivePost",
      ]),
    );
    expect(new Set(defs).size).toBe(defs.length);
    // The per-pixel noise that turned the shadow taps is gone, and so is the per-lamp mix with the bake.
    expect(defs).not.toContain("sectLiveNoise");
    expect(pars).not.toContain("sectLiveShadowMix");
    for (const name of defs) {
      // The first time the name is called is its own definition.
      const def = pars.search(new RegExp(`^\\w+ ${name}\\(`, "m"));
      expect(pars.search(new RegExp(`\\b${name}\\(`)), name).toBe(def + pars.slice(def).indexOf(name));
    }
    // Every live function the blocks in main call is one of these.
    for (const m of (apply + sheen + liveSurfaceNormalGlsl()).matchAll(/\b(sectLive\w+)\(/g)) expect(defs, m[1]).toContain(m[1]);
  });

  it("lights the two lamps through their own shadows and the bake's on their sum, with a GGX shine and the bounce, then the bake's post and Blender's view", () => {
    const L = "vec3( 0.2126, 0.7152, 0.0722 )";
    const radiance = fn("vec3 sectLiveRadiance(");
    expect(radiance).toContain(
      "vec3 sectLiveRadiance( vec3 alb, vec3 amb, vec3 n, vec3 v, vec2 sSun, vec2 sKey, vec2 bake, vec2 face, float rough, float refl )",
    );
    // Each lamp's light with no shadow on it, from the bumped normal, held to bumpCap times the flat face's.
    expect(radiance).toContain("vec2 raw = vec2( max( dot( n, uSectLiveSunDir ), 0.0 ), max( dot( n, uSectLiveKeyDir ), 0.0 ) );");
    expect(radiance).toContain("vec2 nl = min( raw, face * uSectLiveCaps.x );");
    expect(radiance).toContain("vec2 kept = vec2( raw.x > 1e-5 ? nl.x / raw.x : 1.0, raw.y > 1e-5 ? nl.y / raw.y : 1.0 );");
    expect(radiance).toContain("vec3 fromSun = uSectLiveSunE * nl.x;");
    expect(radiance).toContain("vec3 fromKey = uSectLiveKeyE * nl.y;");
    // Their shadowed sum (its numbers: "the lamps" below), on the albedo.
    expect(radiance).toContain("vec3 direct = alb * RECIPROCAL_PI * lamps;");
    // The shine follows the sum: a lamp's own shadow, and of its part left to the bake as much as
    // the page's sum got, then cut by what the bake's shadow and the bump cap took off.
    expect(radiance).toContain(`float got = dot( seen - own, ${L} ) / max( dot( cap, ${L} ), 1e-5 );`);
    expect(radiance).toContain(`float held = min( dot( lamps, ${L} ) / max( dot( seen, ${L} ), 1e-5 ), 1.0 );`);
    // Where the bake's shadow is not soft the shine is in the bake's shadow, as the light is.
    expect(radiance).toContain(
      "vec2 lit = mix( vec2( vis ), vec2( sSun.x * ( 1.0 - sSun.y ) + sSun.y * got, sKey.x * ( 1.0 - sKey.y ) + sKey.y * got ) * held, bake.y );",
    );
    expect(radiance).toContain("sectLiveGgx( n, v, uSectLiveSunDir, rough, f0 ) * uSectLiveSunE * ( lit.x * kept.x )");
    expect(radiance).toContain("sectLiveGgx( n, v, uSectLiveKeyDir, rough, f0 ) * uSectLiveKeyE * ( lit.y * kept.y )");
    // bake.x is the vis the sums read; the shine takes it from there. bake.y only picks between them.
    const body = code(radiance);
    expect(body).toContain("float vis = bake.x;");
    expect(body.match(/\bvis\b/g)).toHaveLength(4);
    expect(body.match(/\bbake\.[xy]\b/g)).toEqual(["bake.x", "bake.y", "bake.y"]);
    // face only caps the bumps.
    expect(body.match(/\bface\b/g)).toHaveLength(2);
    // The sky's light and the bounce are not in the lamps' shadows; the shine is held to a share of them all.
    expect(radiance).toContain("vec3 bounce = alb * RECIPROCAL_PI * uSectLiveBounce * ( 0.5 - 0.5 * n.y );");
    expect(radiance).toContain("vec3 matte = amb + direct + bounce;");
    expect(radiance).toContain("return matte + shine;");
    expect(pars).toContain("float D = a2 / ( PI * dd * dd );");
    // The page's own AgX is gone: the post ends in Blender's view transform.
    expect(pars).not.toContain("sectAgxPunchy");
    // The look's post on the live colour.
    const post = fn("vec3 sectLivePost(");
    expect(post).toContain("return sectLivePostBy( c, vec3( uSectLiveGain, uSectLiveExposure, uSectLiveSat ) );");
    const by = fn("vec3 sectLivePostBy(");
    expect(by).toContain("vec3 sectLivePostBy( vec3 c, vec3 by )");
    expect(by).toContain("return sectLiveView( c * by.y );");
    // Only its parameters: the rebuilt bake uses it with the bake's own.
    expect(by).not.toMatch(/uSectLive/);
    // The bake's order: gain, grade and saturation in scene-linear light, exposure and the view after.
    const at = ["c * by.x", "float sat = ", "by.z *", "sectLiveView( c * by.y )"].map((x) => by.indexOf(x));
    expect(at.every((i) => i >= 0)).toBe(true);
    expect([...at].sort((a, b) => a - b)).toEqual(at);
  });

  it("rebuilds the bake's own light from the maps: the sky and bounce, and the lamps at the bake's strength on the flat face", () => {
    const baked = fn("vec3 sectLiveBaked(");
    expect(baked).toBe(
      [
        "vec3 sectLiveBaked( vec3 alb, vec3 amb, vec2 face, float vis ) {",
        "  return amb * uSectLiveBakeGain.z + alb * RECIPROCAL_PI * ( uSectLiveSunE * ( uSectLiveBakeGain.x * face.x ) + uSectLiveKeyE * ( uSectLiveBakeGain.y * face.y ) ) * vis;",
        "}",
      ].join("\n"),
    );
    // No page fill in it: the detail is on only where the ambient map holds the bake's bounce.
    expect(baked).not.toContain("uSectLiveBounce");
    // At the bake's strength: the lamps and the sky as the index has them, whatever the look's gains.
    const look = structuredClone(LIVE_LOOK);
    look.sunGain = 1.7;
    look.keyGain = 0.6;
    look.ambientGain = 1.3;
    const ix = parseLiveIndex(sample()) as LiveIndex;
    const v = liveValues(ix, look, liveStopBox(GATE.footprint, look));
    for (let i = 0; i < 3; i++) {
      expect(v.sunE[i] * v.bakeGain[0]).toBeCloseTo(ix.light.sun.color[i] * ix.light.sun.strength, 12);
      expect(v.keyE[i] * v.bakeGain[1]).toBeCloseTo(ix.light.key.color[i] * ix.light.key.strength, 12);
    }
    expect(v.ambient * v.bakeGain[2]).toBeCloseTo(ix.ambientScale, 12);
  });

  it("looks each shadow up PCSS-style in one function, with a wrapper per lamp", () => {
    const s = LIVE_LOOK.shadow;
    const at = fn("vec2 sectLiveShadowAt(");
    expect(at).toContain(
      "vec2 sectLiveShadowAt( highp sampler2DShadow map, highp sampler2D coarse, mat4 toMap, vec4 scale, vec4 bias, vec2 pens, vec3 lamp, vec3 wp, vec3 n )",
    );
    expect(at).toContain(`for ( int i = 0; i < ${s.blockerTaps}; i ++ )`);
    expect(at).toContain(`for ( int i = 0; i < ${s.pcfTaps}; i ++ )`);
    expect(at).toContain("* scale.y * scale.z, pens.x, pens.y )");
    // Normal offset, and the slope to this lamp held below the map's cap.
    expect(at).toContain("toMap * vec4( wp + n * bias.y, 1.0 )");
    expect(at).toContain("dot( n, lamp )");
    expect(at).toMatch(/float slope = min\( [^;]*, bias\.w \);/);
    // Only its parameters: no lamp's own uniforms.
    expect(at).not.toMatch(/uSectLive|tSectLive/);
    expect(at).not.toMatch(derivative);
    const key = fn("vec2 sectLiveShadow(");
    // A face turned away from the lamp is in its own shadow (a bump leaning back gets no light),
    // the first degrees past the edge fade in, and with the map off the lookup is "lit, nothing casts".
    expect(key).toContain("vec2 sectLiveShadow( vec3 wp, vec3 n )");
    expect(key).toContain("float nl = dot( n, uSectLiveKeyDir );");
    expect(key).toContain("if ( nl <= 0.0 ) return vec2( 0.0 );");
    expect(key).toContain("vec2 r = vec2( 1.0, - 1.0 );");
    expect(key).toContain(
      "if ( uSectLiveShadowOn > 0.5 ) r = sectLiveShadowAt( tSectLiveShadow, tSectLiveShadowB, uSectLiveShadowMatrix, uSectLiveShadowMap, uSectLiveShadowBias, uSectLiveShadowPen, uSectLiveKeyDir, wp, n );",
    );
    // A lamp that only grazes the face is the bake's.
    expect(key).toContain("float graze = sectLiveGraze( nl );");
    expect(key).toContain("if ( graze >= 1.0 ) return vec2( edge );");
    expect(key).toContain("return edge * vec2( r.x, max( sectLiveBakeShare( r ), graze ) );");
    expect(key).not.toMatch(/Sun/);
    const sun = fn("vec2 sectLiveSunShadow(");
    expect(sun).toContain("vec2 sectLiveSunShadow( vec3 wp, vec3 n )");
    expect(sun).toContain("float nl = dot( n, uSectLiveSunDir );");
    expect(sun).toContain("if ( nl <= 0.0 ) return vec2( 0.0 );");
    expect(sun).toContain("vec2 r = vec2( 1.0, - 1.0 );");
    expect(sun).toContain(
      "if ( uSectLiveSunShadowOn > 0.5 ) r = sectLiveShadowAt( tSectLiveSunShadow, tSectLiveSunShadowB, uSectLiveSunShadowMatrix, uSectLiveSunShadowMap, uSectLiveSunShadowBias, uSectLiveSunShadowPen, uSectLiveSunDir, wp, n );",
    );
    expect(sun).toContain("float graze = sectLiveGraze( nl );");
    expect(sun).toContain("if ( graze >= 1.0 ) return vec2( edge );");
    expect(sun).toContain("return edge * vec2( r.x, max( sectLiveBakeShare( r ), graze ) );");
    expect(sun).not.toMatch(/Key|[tu]SectLiveShadow/);
    expect(pars).not.toMatch(/NaN|undefined|Infinity/);
  });

  it("gives a face turned to the lamp its own shadow and the share left to the bake, a face the lamp only grazes to the bake with no lookup, and a face turned away nothing", () => {
    for (const [sig, on] of [
      ["vec2 sectLiveShadow(", "uSectLiveShadowOn"],
      ["vec2 sectLiveSunShadow(", "uSectLiveSunShadowOn"],
    ] as const) {
      const body = fn(sig);
      const returns = [...body.matchAll(/return ([^;]*);/g)];
      expect(returns, sig).toHaveLength(3);
      // First a face turned away: no light and nothing left to the bake, before anything is looked up.
      expect(returns[0][1], sig).toBe("vec2( 0.0 )");
      expect(body.slice(0, returns[0].index), sig).toMatch(/if \( nl <= 0\.0 \) $/);
      // Then a face the lamp only grazes: lit and wholly the bake's (both times the edge), still
      // before the lookup.
      const grazing = body.slice(returns[0].index, returns[1].index);
      expect(returns[1][1], sig).toBe("vec2( edge )");
      expect(grazing, sig).toContain("float edge = smoothstep( 0.0, 0.06, nl );");
      expect(grazing, sig).toContain("float graze = sectLiveGraze( nl );");
      expect(grazing, sig).toMatch(/if \( graze >= 1\.0 \) $/);
      expect(grazing, sig).not.toContain("sectLiveShadowAt");
      // Then "lit, nothing casts" unless the map is on, and the edge on both: the page's own shadow
      // and the share (a bump on a face edge-on to the lamp must not take the bake's light whole).
      const after = body.slice(returns[1].index, returns[2].index);
      expect(after.indexOf("vec2 r = vec2( 1.0, - 1.0 );"), sig).toBeGreaterThan(0);
      expect(after.indexOf(`if ( ${on} > 0.5 ) r = sectLiveShadowAt(`), sig).toBeGreaterThan(after.indexOf("vec2 r ="));
      expect(body.match(/\br = /g), sig).toHaveLength(2);
      // The share is at least the graze's.
      expect(returns[2][1], sig).toBe("edge * vec2( r.x, max( sectLiveBakeShare( r ), graze ) )");
      // The bake's own shadow is not read here: that is the sum's (sectLiveRadiance).
      expect(body, sig).not.toMatch(/\bvis\b|uSectLiveVis/);
    }
  });

  describe("the smooth shadow lookup", () => {
    const s = LIVE_LOOK.shadow;
    const start = pars.indexOf("vec2 sectLiveShadowAt(");
    // Its code without the comments.
    const at = pars.slice(start, pars.indexOf("\n}", start) + 2).replace(/\/\/[^\n]*/g, "");
    const blocker = at.indexOf(`i < ${s.blockerTaps}`);
    const penAt = at.indexOf("float pen = ");
    const pcf = at.indexOf(`i < ${s.pcfTaps}`);

    it("returns how lit the point is and how far off what casts on it is, or -1 when nothing casts", () => {
      const returns = [...at.matchAll(/return ([^;]*);/g)].map((m) => m[1]);
      expect(returns).toEqual([
        // Outside the map: lit, and nothing casts.
        "vec2( 1.0, - 1.0 )",
        // Inside it the map decides; no blocker found is -1, else the blockers' mean depth in metres.
        `vec2( lit / ${glslFloat(s.pcfTaps)}, found < 0.5 ? - 1.0 : ( s.z - depthSum / found ) * scale.y )`,
      ]);
      expect(at).toContain("s.x >= 1.0 || s.y >= 1.0 || s.z <= 0.0 || s.z >= 1.0 ) return vec2( 1.0, - 1.0 );");
      // The last thing it does, after the PCF.
      expect(at.indexOf("return vec2( lit")).toBeGreaterThan(pcf);
      // The same distance sizes the penumbra.
      expect(at).toContain("( s.z - depthSum / found ) * scale.y * scale.z");
    });

    it("measures that distance in metres along the lamp: stored depth times the map's depth (scale.y)", () => {
      const ix = parseLiveIndex(sample())!;
      const receiver: Vec3 = [0, 40, 0];
      for (const lamp of ["key", "sun"] as const) {
        const box = boxAt(GATE.footprint, lamp);
        const dir = ix.light[lamp].dir;
        const m = liveShadowMatrix(dir, receiver, box);
        // What the map stores: z / 2 + 0.5.
        const depth = (p: Vec3) => liveProject(m, p)[2] * 0.5 + 0.5;
        const metresPerDepth = liveShadowScale(box, ix.light[lamp].angleDeg, LIVE_LOOK.shadow.size).metresPerDepth;
        const { nearM, farM } = LIVE_LOOK.bakedShadow;
        for (const t of [0.3, nearM, (nearM + farM) / 2, farM, 3 * farM]) {
          const caster: Vec3 = [receiver[0] + dir[0] * t, receiver[1] + dir[1] * t, receiver[2] + dir[2] * t];
          expect((depth(receiver) - depth(caster)) * metresPerDepth, `${lamp} ${t}`).toBeCloseTo(t, 6);
        }
      }
    });

    it("turns nothing per pixel: no screen position, no noise, no rotation", () => {
      expect(start).toBeGreaterThan(0);
      expect(pars).not.toContain("gl_FragCoord");
      expect(apply + liveApplyGlsl(true) + sheen).not.toContain("gl_FragCoord");
      expect(pars).not.toContain("sectLiveNoise(");
      expect(at).not.toMatch(/\bmat2\b|\bturn\b|sin\(|cos\(/);
    });

    it("spreads its taps over fixed discs, used as they are", () => {
      const disc = (name: string, n: number) =>
        `const vec2 ${name}[ ${n} ] = vec2[](\n${liveDisc(n)
          .map(([x, y]) => `  vec2( ${glslFloat(x)}, ${glslFloat(y)} )`)
          .join(",\n")}\n);`;
      expect(pars).toContain(disc("SECT_LIVE_BLOCKER", s.blockerTaps));
      expect(pars).toContain(disc("SECT_LIVE_PCF", s.pcfTaps));
      expect(at).toContain("vec2 o = SECT_LIVE_BLOCKER[ i ] * bias.z;");
      expect(at).toContain("vec2 o = SECT_LIVE_PCF[ i ] * ( 0.5 * pen );");
    });

    it("searches for blockers on the coarse map, with the coarse texel in the bias", () => {
      const coarse = glslFloat(Math.max(1, Math.round(s.coarse)));
      expect(at.match(/textureLod\( coarse, /g)).toHaveLength(1);
      expect(at).toContain("float d = textureLod( coarse, s.xy + o * uvPerM, 0.0 ).r;");
      expect(at).toContain(`if ( d < s.z - ( bias.x + slope * ( length( o ) + scale.w * ${coarse} ) ) * dPerM ) {`);
      // In the blocker loop, before the penumbra is worked out.
      expect(blocker).toBeGreaterThan(0);
      expect(at.indexOf("textureLod( coarse")).toBeGreaterThan(blocker);
      expect(at.indexOf("textureLod( coarse")).toBeLessThan(penAt);
    });

    it("falls back on the narrowest penumbra when no blocker is found, and lets the fine map decide", () => {
      expect(at).toContain("float pen = found < 0.5 ? pens.x : clamp( ( s.z - depthSum / found ) * scale.y * scale.z, pens.x, pens.y );");
      expect(at).not.toContain("if ( found < 0.5 ) return");
      expect(penAt).toBeGreaterThan(blocker);
      expect(pcf).toBeGreaterThan(penAt);
    });

    it("compares each PCF tap in hardware, with no gradients, and reads the fine map nowhere else", () => {
      expect(at).toContain(
        // The slope bias covers the tap's distance and the 2x2 the hardware reads (a texel and a half).
        "lit += textureGrad( map, vec3( s.xy + o * uvPerM, s.z - ( bias.x + slope * ( length( o ) + scale.w * 1.5 ) ) * dPerM ), vec2( 0.0 ), vec2( 0.0 ) );",
      );
      expect(at.indexOf("textureGrad( map")).toBeGreaterThan(pcf);
      expect(at.match(/\bmap\b/g)).toHaveLength(2);
      expect(at).not.toMatch(/texture(?:Lod|2D)?\( map\b/);
      // The plain depths are never compared in hardware, nor the compare map read as depths.
      expect(at).not.toMatch(/textureGrad\( coarse|texture(?:2D)?\( coarse/);
    });
  });

  it("holds the shine's low-angle end down by roughness and by reflectance", () => {
    const ggx = fn("vec3 sectLiveGgx(");
    expect(ggx).toContain("vec3 f90 = max( f0, clamp( f0 * 25.0, 0.0, 1.0 ) * ( 1.0 - rough ) );");
    expect(ggx).toContain("vec3 F = f0 + ( f90 - f0 ) * pow( 1.0 - vh, 5.0 );");
    expect(ggx).toContain("return F * ( V * D * nl );");
    // The same two lines in numbers.
    const fresnel = (f0: number, rough: number, vh: number) => {
      const f90 = Math.max(f0, Math.min(Math.max(f0 * 25, 0), 1) * (1 - rough));
      return f0 + (f90 - f0) * Math.pow(1 - vh, 5);
    };
    for (const rough of [0.05, 0.3, 0.6, 0.95]) {
      for (const vh of [0, 0.2, 0.7, 1]) {
        // No reflectance, no shine at any angle.
        expect(fresnel(0, rough, vh)).toBe(0);
        // Never below f0, never above 1.
        expect(fresnel(0.04, rough, vh)).toBeGreaterThanOrEqual(0.04 - 1e-12);
        expect(fresnel(0.04, rough, vh)).toBeLessThanOrEqual(1);
      }
      // At a grazing angle a common dielectric reaches 1 - rough, not 1.
      expect(fresnel(0.04, rough, 0)).toBeCloseTo(1 - rough, 12);
      // Head on it is f0.
      expect(fresnel(0.04, rough, 1)).toBeCloseTo(0.04, 12);
    }
    // Grass and earth have no shine at all.
    expect(liveShineVec(LIVE_LOOK.classes.ground)[1]).toBe(0);
  });

  it("puts the surface colour back into an ambient map without it, right after the maps are read", () => {
    const line = "lAmb = mix( lAmb, lAmb * lAlb, uSectLiveAmbientIrr );";
    for (const src of [apply, liveApplyGlsl(true)]) {
      expect(src.split(line).length - 1).toBe(1);
      const order = [
        "vec3 lAlb = texture2D( tSectLiveAlbedo, vMapUv ).rgb;",
        "vec4 lAmbA = texture2D( tSectLiveAmbient, vMapUv );",
        "vec3 lAmb = lAmbA.rgb;",
        line,
        "if ( sectLiveShare > 0.0 ) {",
        "sectLiveGloss = vec3( lRough, lRefl, ",
        "sectLiveRadiance( lAlb, lAmb * uSectLiveAmbient,",
      ].map((x) => src.indexOf(x));
      expect(order.every((i) => i >= 0), String(order)).toBe(true);
      expect([...order].sort((a, b) => a - b)).toEqual(order);
      // Set nowhere else.
      expect(src.match(/(?<!vec3 )\blAmb =/g)).toHaveLength(1);
    }
  });

  it("bumps the normal with value noise and its gradient, each layer fading out before it gets too small to see", () => {
    expect(pars).toContain("float sectLiveHash( vec3 p )");
    const noised = fn("vec4 sectLiveNoised(");
    expect(noised).toContain("vec4 sectLiveNoised( vec3 x )");
    // The eight corners of the cell.
    expect(noised.match(/sectLiveHash\( i\b/g)).toHaveLength(8);
    const bumped = fn("vec3 sectLiveBumped(");
    expect(bumped).toContain("vec3 sectLiveBumped( vec3 n, vec3 p, vec4 k, float fw )");
    // Each layer: its 1 / size (k.x, k.z) against the pixel's width, its slope (k.y, k.w), the overall strength.
    expect(bumped).toContain("fw * k.x ) ) * k.y * uSectLiveSurface.z");
    expect(bumped).toContain("fw * k.z ) ) * k.w * uSectLiveSurface.z");
    expect(bumped).toMatch(/sectLiveNoised\( p \* k\.x[^)]*\)\.yzw \* w1/);
    expect(bumped).toMatch(/sectLiveNoised\( p \* k\.z[^)]*\)\.yzw \* w2/);
    // Only the slope across the face tilts it.
    expect(bumped).toContain("g -= n * dot( g, n );");
    expect(bumped).not.toMatch(derivative);
  });

  it("replaces the texel only where the live share is above 0, and falls back on an empty normal", () => {
    expect(apply).toContain("texture2D( tSectLiveAlbedo, vMapUv )");
    expect(apply).toContain("vec4 lNtA = texture2D( tSectLiveNormal, vMapUv );");
    expect(apply).toContain("vec3 lNt = lNtA.rgb * 2.0 - 1.0;");
    // Empty: grey (decodes near 0 long) or Blender's black clear (decodes to (-1, -1, 1), 1.73 long).
    // And where the sky-light map is at its top (a lantern's light is brighter than it can hold) the bake stays.
    expect(apply).toContain("sectLiveShare = lNl >= 0.5 && lNl <= 1.25 ? uSectLiveMix * ( 1.0 - lFar ) * ( 1.0 - lHot ) : 0.0;");
    expect(apply).toMatch(/float lHot = smoothstep\( [\d.]+, [\d.]+, max\( lAmb\.r, max\( lAmb\.g, lAmb\.b \) \) \);/);
    // Read off the map as stored, before the colour is multiplied back in.
    expect(apply.indexOf("float lHot =")).toBeLessThan(apply.indexOf("lAmb = mix( lAmb, lAmb * lAlb, uSectLiveAmbientIrr );"));
    const decode = (byte: number) => (byte / 255) * 2 - 1;
    expect(Math.hypot(decode(0), decode(0), decode(255))).toBeGreaterThan(1.25);
    expect(Math.hypot(decode(128), decode(128), decode(128))).toBeLessThan(0.5);
    expect(Math.hypot(decode(128), decode(255), decode(128))).toBeGreaterThan(0.5);
    expect(Math.hypot(decode(128), decode(255), decode(128))).toBeLessThan(1.25);
    expect(apply).toContain("smoothstep( uSectLiveBlend.x, uSectLiveBlend.y, length( vSectWorld.xz - uSectLiveCentre.xz ) )");
    const guard = apply.indexOf("if ( sectLiveShare > 0.0 ) {");
    expect(guard).toBeGreaterThan(0);
    expect(apply.indexOf("sectTexel = mix( sectTexel, lTex, sectLiveShare );")).toBeGreaterThan(guard);
    // sectTexel is written nowhere else.
    expect(apply.match(/sectTexel =/g)).toHaveLength(1);
    expect(liveSurfaceNormalGlsl()).toContain("if ( sectLiveShare > 0.0 ) {");
    // Vertex colours as three applies them to the baked texel (vColor is a vec4 there).
    expect(apply).toContain("#if defined( USE_COLOR ) || defined( USE_COLOR_ALPHA )\n        lTex *= vColor.rgb;");
    expect(apply).not.toMatch(/lTex \*= vColor;/);
  });

  it("reads where the bake's shadow is soft from the normal map's alpha, only when the index says so, and hands it to the sum", () => {
    for (const src of [apply, liveApplyGlsl(true)]) {
      // One read of the normal map, for its normal and its alpha.
      expect(src.match(/tSectLiveNormal/g)).toHaveLength(1);
      expect(src.match(/\blNtA\b/g)).toHaveLength(3);
      // 1 everywhere (the page's maps used everywhere) unless uSectLiveClose.z says the map has it.
      const soft = "float lSoft = mix( 1.0, lNtA.a, uSectLiveClose.z );";
      expect(src).toContain(soft);
      expect(src.indexOf(soft)).toBeLessThan(src.indexOf("if ( sectLiveShare > 0.0 ) {"));
      // Read by the sum alone, as bake.y.
      expect(src.match(/\blSoft\b/g)).toHaveLength(2);
      const params = /vec3 sectLiveRadiance\( ([^)]*) \)/.exec(pars)![1].split(", ").map((p) => p.split(" ")[1]);
      const args = callArgs(src, "sectLiveRadiance");
      expect(args[params.indexOf("bake")]).toMatch(/^vec2\( \w+, lSoft \)$/);
    }
    // The shader's mix in numbers: 1 without the map, the map's alpha with it.
    const lSoft = (alpha: number, on: number) => mix(1, alpha, on);
    for (const a of [0, 0.3, 1]) {
      expect(lSoft(a, 0)).toBe(1);
      expect(lSoft(a, 1)).toBeCloseTo(a, 12);
    }
  });

  it("takes the shadows and the flat face's light from the map's normal, and the light from the bumped one", () => {
    const params = /vec3 sectLiveRadiance\( ([^)]*) \)/.exec(pars)![1].split(", ").map((p) => p.split(" ")[1]);
    const args = callArgs(apply, "sectLiveRadiance");
    expect(args).toHaveLength(params.length);
    // Each lookup starts lifted toward its own lamp by the class's lift (0 for all but cloth).
    const key = /vec2 (\w+) = sectLiveShadow\( vSectWorld \+ uSectLiveKeyDir \* uSectLiveLift, (\w+) \);/.exec(apply)!;
    const sun = /vec2 (\w+) = sectLiveSunShadow\( vSectWorld \+ uSectLiveSunDir \* uSectLiveLift, (\w+) \);/.exec(apply)!;
    const bump = /sectLiveN = sectLiveBumped\( (\w+), vSectWorld, uSectLiveBump, (\w+) \);/.exec(apply)!;
    const vis = /float (\w+) = clamp\( \( lAmbA\.a - [\d.]+ \) \/ [\d.]+, 0\.0, 1\.0 \);/.exec(apply)!;
    expect(key && sun && bump && vis).toBeTruthy();
    // One face normal, the map's, for both shadows and under the bumps.
    expect(apply).toContain(`vec3 ${bump[1]} = lNt / lNl;`);
    expect(key[2]).toBe(bump[1]);
    expect(sun[2]).toBe(bump[1]);
    // The light from the bumped normal, each lamp through its own shadow, and the bake's shadow once, on the sum.
    expect(args[params.indexOf("n")]).toBe("sectLiveN");
    expect(args[params.indexOf("sSun")]).toBe(sun[1]);
    expect(args[params.indexOf("sKey")]).toBe(key[1]);
    expect(args[params.indexOf("bake")]).toBe(`vec2( ${vis[1]}, lSoft )`);
    // What the flat face gets from (the sun, the key): the map's normal, as the shadows.
    const face = /vec2 (\w+) = vec2\( max\( dot\( (\w+), uSectLiveSunDir \), 0\.0 \), max\( dot\( (\w+), uSectLiveKeyDir \), 0\.0 \) \);/.exec(apply)!;
    expect(face).not.toBeNull();
    expect(face[2]).toBe(bump[1]);
    expect(face[3]).toBe(bump[1]);
    expect(args[params.indexOf("face")]).toBe(face[1]);
    // Shadows and the flat face first, then the bumps, then the light.
    const radiance = apply.indexOf("sectLiveRadiance(");
    expect(Math.max(key.index, sun.index, face.index)).toBeLessThan(bump.index);
    expect(bump.index).toBeLessThan(radiance);
    // The pixel's width for the bumps is taken before the live branch.
    const width = apply.indexOf(`float ${bump[2]} = length( fwidth( vSectWorld ) );`);
    expect(width).toBeGreaterThan(0);
    expect(width).toBeLessThan(apply.indexOf("if ( sectLiveShare > 0.0 ) {"));
  });

  it("makes a painted class's saturated colours lacquer", () => {
    expect(apply).toMatch(/smoothstep\( uSectLivePaint\.x, uSectLivePaint\.y, \w+ \) \* uSectLiveSpec\.w/);
    expect(apply).toMatch(/mix\( uSectLiveSpec\.x, uSectLivePaint\.z, \w+ \)/);
    expect(apply).toMatch(/mix\( uSectLiveSpec\.y, uSectLivePaint\.w, \w+ \)/);
  });

  it("takes screen derivatives only outside the live branch", () => {
    const guard = apply.indexOf("if ( sectLiveShare > 0.0 ) {");
    expect(apply.indexOf("fwidth( vSectWorld )")).toBeLessThan(guard);
    expect(apply.slice(guard)).not.toMatch(derivative);
    for (const sig of [
      "vec2 sectLiveShadowAt(",
      "float sectLiveBakeShare(",
      "float sectLiveGraze(",
      "vec2 sectLiveShadow(",
      "vec2 sectLiveSunShadow(",
      "vec3 sectLiveBumped(",
      "vec3 sectLiveGgx(",
      "vec3 sectLiveRadiance(",
      "vec3 sectLiveBaked(",
      "vec3 sectLiveDetail(",
      "vec3 sectLivePostBy(",
      "vec3 sectLivePost(",
    ]) {
      expect(fn(sig), sig).not.toMatch(derivative);
    }
    // The sheen runs in a branch too.
    expect(sheen).not.toMatch(derivative);
  });

  it("leaves a gloss for the sky sheen, matte until the live branch sets it", () => {
    const guard = apply.indexOf("if ( sectLiveShare > 0.0 ) {");
    const decl = apply.indexOf("vec3 sectLiveGloss = vec3( 1.0, 0.0, 0.0 );");
    expect(decl).toBeGreaterThanOrEqual(0);
    expect(decl).toBeLessThan(guard);
    expect(apply.slice(guard)).toMatch(/sectLiveGloss = vec3\( lRough, lRefl, /);
  });

  it("adds the sky to smooth surfaces only where the live share is above 0", () => {
    const guard = sheen.indexOf("if ( sectLiveShare > 0.0 ) {");
    expect(guard).toBeGreaterThanOrEqual(0);
    expect(sheen.slice(0, guard).trim()).toBe("");
    expect(sheen.match(/outgoingLight =/g)).toHaveLength(1);
    expect(sheen.indexOf("outgoingLight =")).toBeGreaterThan(guard);
    // The bumped normal turned to the eye, the gloss the apply block left, the page's sky.
    expect(sheen).toContain("dot( sectLiveN, hV ) > 0.0 ? - sectLiveN : sectLiveN");
    for (const g of ["sectLiveGloss.x", "sectLiveGloss.y", "sectLiveGloss.z"]) expect(sheen).toContain(g);
    expect(sheen).toContain("sectEnvSky( reflect( hV, hN ), sectLiveGloss.x )");
    // Weighted by the sheen's amount and the live share; a matte surface (roughness 1) gets none.
    expect(sheen).toMatch(/hF = [^;]*\* uSectLiveSurface\.x \* sectLiveShare;/);
    expect(sheen).toContain("( 1.0 - sectLiveGloss.x ) * ( 1.0 - sectLiveGloss.x )");
  });
});

describe("roof tiles (the tiles detail class)", () => {
  const plain = liveApplyGlsl();
  const tiles = liveApplyGlsl(true);
  const branch = (src: string) => src.indexOf("if ( sectLiveShare > 0.0 ) {");

  it("rolls the normal across each course, on top of the bumps", () => {
    expect(tiles).toContain("fract( vSectUv1.x + 0.5 ) - 0.5");
    expect(tiles).toContain("uSectLiveTiles.x * uSectLiveSurface.z");
    // After the bumps, and before the light is worked out with the normal.
    const bumped = tiles.indexOf("sectLiveN = sectLiveBumped(");
    const roll = tiles.indexOf("sin( 6.2831853 *");
    expect(bumped).toBeGreaterThan(0);
    expect(roll).toBeGreaterThan(bumped);
    expect(tiles.indexOf("sectLiveRadiance(")).toBeGreaterThan(roll);
    // Along the surface only: the part of the way across that lies in the face.
    expect(tiles).toContain("lTx - sectLiveN * dot( lTx, sectLiveN )");
  });

  it("takes its derivatives before the live branch and fades out where courses get small", () => {
    const b = branch(tiles);
    expect(b).toBeGreaterThan(0);
    for (const d of ["dFdx( vSectUv1 )", "dFdy( vSectUv1 )", "fwidth( vSectUv1.x )"]) {
      expect(tiles.indexOf(d)).toBeGreaterThan(0);
      expect(tiles.indexOf(d)).toBeLessThan(b);
    }
    expect(tiles.slice(b)).not.toMatch(/dFd[xy]|fwidth/);
    expect(tiles).toContain("1.0 - smoothstep( uSectLiveTiles.y, uSectLiveTiles.z, lTw )");
    const t = LIVE_LOOK.tiles;
    expect(t.fade[0]).toBeLessThan(t.fade[1]);
    expect(t.roll).toBeGreaterThanOrEqual(0);
  });

  it("is only in the tiles variant: every other class has no tile coordinates", () => {
    expect(plain).not.toContain("vSectUv1");
    expect(plain).not.toContain("uSectLiveTiles");
    expect(liveParsGlsl()).toContain("uniform vec3 uSectLiveTiles;");
    // Otherwise the two are the same block.
    expect(tiles.replace(/\n {4}vec3 lTx[^\n]*\n {4}float lTw[^\n]*/, "").replace(/\n {6}vec3 lTd[\s\S]*?lTk \) \);/, "")).toBe(plain);
  });
});

describe("paving relief (the paving detail class)", () => {
  const plain = liveApplyGlsl();
  const paving = liveApplyGlsl(false, true);
  const branch = (src: string) => src.indexOf("if ( sectLiveShare > 0.0 ) {");
  const P = LIVE_LOOK.paving;
  const [bw, rh] = DETAIL_LOOK.paving.slabM;
  const smooth = (a: number, b: number, x: number) => {
    const t = Math.min(Math.max((x - a) / (b - a), 0), 1);
    return t * t * (3 - 2 * t);
  };

  it("takes its derivatives before the live branch and none inside it", () => {
    const b = branch(paving);
    expect(b).toBeGreaterThan(0);
    for (const d of ["dFdx( vSectWorld )", "dFdy( vSectWorld )", "dFdx( vSectUv1 )", "dFdy( vSectUv1 )"]) {
      expect(paving.indexOf(d), d).toBeGreaterThan(0);
      expect(paving.indexOf(d), d).toBeLessThan(b);
    }
    expect(paving.slice(b)).not.toMatch(/dFd[xy]|fwidth|texture2D\(|texture\(/);
    // Nor do the slab helpers it calls there (detail.ts pavingGlsl).
    const g = detailGlsl("paving");
    for (const sig of ["vec3 sectHash3( vec2 p )", "vec2 sectSlab( vec2 q, out vec2 e )", "vec2 sectSlabPos( vec2 q, vec2 id )"]) {
      const at = g.indexOf(sig);
      expect(at, sig).toBeGreaterThan(0);
      expect(g.slice(at, g.indexOf("\n}", at)), sig).not.toMatch(/dFd[xy]|fwidth|texture/);
    }
  });

  it("leans each slab its own way and bevels its edges, on the slab tops, after the bumps", () => {
    expect(paving).toContain("vec3 lPh = sectHash3( lPid + 29.1 );");
    expect(paving).toContain("vec2 lPs = sign( sectSlabPos( vSectUv1, lPid ) - lPe - 1e-4 );");
    expect(paving).toContain(
      "vec2 lPb = ( 1.0 - smoothstep( vec2( 0.0 ), vec2( uSectLivePaving.y ), lPe ) ) * lPs * ( uSectLivePaving.z * clamp( uSectLivePaving.y / lPw, 0.0, 1.0 ) );",
    );
    expect(paving).toContain("vec2 lPg = ( lPh.xy - 0.5 ) * ( 2.0 * uSectLivePaving.x ) + lPb;");
    expect(paving).toContain("float lPk = uSectLiveSurface.z * smoothstep( 0.55, 0.8, abs( lNg.y ) );");
    // Skipped where the slab plane has no direction on screen, and a pixel's size held off 0.
    expect(paving).toContain("if ( dot( lPu, lPu ) > 1e-18 && dot( lPv, lPv ) > 1e-18 ) {");
    expect(paving).toContain("float lPw = max( length( lUx ) + length( lUy ), 1e-5 );");
    const bumped = paving.indexOf("sectLiveN = sectLiveBumped(");
    const relief = paving.indexOf("sectLiveN = normalize( sectLiveN + ( normalize( lPu ) * lPg.x + normalize( lPv ) * lPg.y ) * lPk );");
    expect(bumped).toBeGreaterThan(0);
    expect(relief).toBeGreaterThan(bumped);
    expect(paving.indexOf("sectLiveRadiance(")).toBeGreaterThan(relief);
  });

  it("is only in the paving variant", () => {
    for (const src of [plain, liveApplyGlsl(true)]) {
      expect(src).not.toContain("uSectLivePaving");
      expect(src).not.toContain("sectSlab");
    }
    expect(liveParsGlsl()).toContain("uniform vec3 uSectLivePaving;");
    // Otherwise the two are the same block.
    expect(paving.replace(/\n {4}vec3 lPx[\s\S]*?float lPw[^\n]*/, "").replace(/\n {6}if \( dot\( lPu, lPu \)[\s\S]*?\n {6}\}/, "")).toBe(plain);
  });

  it("finds the ways along the slabs from the derivatives, mirrored UVs too (a mirror in numbers)", () => {
    expect(paving).toContain("float lPd = lUx.x * lUy.y - lUx.y * lUy.x < 0.0 ? - 1.0 : 1.0;");
    expect(paving).toContain("vec3 lPu = ( lPx * lUy.y - lPy * lUx.y ) * lPd;");
    expect(paving).toContain("vec3 lPv = ( lPy * lUx.x - lPx * lUy.x ) * lPd;");
    // A slab plane in the world: P = u U + v V, seen through a screen mapping with (du, dv) per pixel.
    const U: Vec3 = [0.8, 0, -0.6];
    const V: Vec3 = [0.6, 0, 0.8];
    const at = (u: number, v: number): Vec3 => [u * U[0] + v * V[0], u * U[1] + v * V[1], u * U[2] + v * V[2]];
    const norm = (a: readonly number[]) => {
      const l = Math.hypot(...a);
      return a.map((x) => x / l);
    };
    const turns = new Set<number>();
    for (const [ux, uy] of [
      [
        [0.02, 0.003],
        [-0.004, 0.03],
      ],
      [
        [0.01, -0.02],
        [0.05, 0.01],
      ],
      // Mirrored UVs: the grid turns the other way on screen.
      [
        [-0.02, 0.003],
        [0.004, 0.03],
      ],
      [
        [0.01, 0.02],
        [0.05, -0.01],
      ],
    ] as const) {
      const det = ux[0] * uy[1] - ux[1] * uy[0];
      turns.add(Math.sign(det));
      const d = det < 0 ? -1 : 1;
      const px = at(ux[0], ux[1]);
      const py = at(uy[0], uy[1]);
      const pu = px.map((x, i) => (x * uy[1] - py[i] * ux[1]) * d);
      const pv = py.map((x, i) => (x * ux[0] - px[i] * uy[0]) * d);
      norm(pu).forEach((x, i) => expect(x).toBeCloseTo(U[i], 9));
      norm(pv).forEach((x, i) => expect(x).toBeCloseTo(V[i], 9));
      // Without the sign, mirrored UVs would point both ways backward (the bevel's lit rim on the wrong side).
      if (det < 0) norm(px.map((x, i) => x * uy[1] - py[i] * ux[1])).forEach((x, i) => expect(x).toBeCloseTo(-U[i], 9));
    }
    expect(turns).toEqual(new Set([1, -1]));
  });

  it("in numbers: a slab leans by up to tilt; its rim by up to the bevel's slope, outward, less once a pixel outgrows the bevel", () => {
    expect(P.tilt).toBeGreaterThanOrEqual(0);
    // 0.02 turned stair treads into a chequer of sunlit blocks.
    expect(P.tilt).toBeLessThan(0.02);
    expect(P.bevelM).toBeGreaterThan(0);
    expect(P.bevelM).toBeLessThan(Math.min(bw, rh) / 2);
    expect(P.bevel).toBeGreaterThanOrEqual(0);
    // Mirror of lPs on one axis, from detail.ts sectSlabPos (row 1 is not shifted): which side is nearer.
    const side = (x: number) => {
      const s = pavingSlab(x, 0.9);
      expect(s.row).toBe(1);
      return Math.sign(x - s.col * bw - s.edge[0] - 1e-4);
    };
    expect(side(0.01)).toBe(-1);
    expect(side(1.19)).toBe(1);
    expect(side(1.21)).toBe(-1);
    // Mirror of lPb on one axis: e to the nearer side, s that side, w a pixel's size (m).
    const bevel = (e: number, s: number, w: number) => (1 - smooth(0, P.bevelM, e)) * s * P.bevel * Math.min(Math.max(P.bevelM / Math.max(w, 1e-5), 0), 1);
    expect(bevel(0, 1, 0.001)).toBe(P.bevel);
    expect(bevel(0, -1, 0.001)).toBe(-P.bevel);
    expect(bevel(P.bevelM, 1, 0.001)).toBe(0);
    expect(bevel(0, 1, 10 * P.bevelM)).toBeCloseTo(P.bevel / 10, 12);
    for (let e = 0; e <= 0.1; e += 0.002) {
      for (const w of [0, 0.001, 0.01, 0.1, 1]) expect(Math.abs(bevel(e, 1, w))).toBeLessThanOrEqual(P.bevel);
    }
    // The lean: (hash - 0.5) x 2 tilt, either way.
    for (const h of [0, 0.25, 0.5, 1]) expect(Math.abs((h - 0.5) * 2 * P.tilt)).toBeLessThanOrEqual(P.tilt);
  });
});

describe("cloth (materials that sway)", () => {
  it("is its own class, ahead of every other", () => {
    expect(liveClassOf("paving", "metal", true)).toBe("cloth");
    expect(liveClassOf(undefined, undefined, true)).toBe("cloth");
    expect(liveClassOf("paving", "metal", false)).toBe("metal");
    expect(liveClassOf("paving", "metal")).toBe("metal");
    expect(LIVE_CLASSES).toContain("cloth");
  });

  it("starts its shadow lookups past its own swing, and nothing else is lifted", () => {
    const cloth = LIVE_LOOK.classes.cloth;
    // A banner swings about a third of a metre (idle.ts BANNER, FLAG).
    expect(cloth.liftM).toBeGreaterThan(0.38);
    expect(cloth.liftM).toBeLessThan(1);
    for (const c of LIVE_CLASSES) if (c !== "cloth") expect(LIVE_LOOK.classes[c].liftM ?? 0).toBe(0);
    // Matte, flat and without shine.
    expect(cloth.f0).toBe(0);
    expect(cloth.bump[1]).toBe(0);
    expect(cloth.bump[3]).toBe(0);
  });

  it("keeps the map's normal as it is: the bake's bounce already holds the light through cloth lit from behind", () => {
    for (const apply of [liveApplyGlsl(), liveApplyGlsl(true)]) {
      // The face normal is set once and never flipped.
      expect(apply).toContain("vec3 lNg = lNt / lNl;");
      expect(apply).not.toMatch(/lNg = - lNg/);
      expect(apply).not.toMatch(/- lNg\b/);
      expect(apply.match(/\blNg =/g)).toHaveLength(1);
      // The lift only moves where each shadow lookup starts.
      expect(apply.match(/uSectLiveLift/g)).toHaveLength(2);
      expect(apply).toContain("sectLiveShadow( vSectWorld + uSectLiveKeyDir * uSectLiveLift, lNg )");
      expect(apply).toContain("sectLiveSunShadow( vSectWorld + uSectLiveSunDir * uSectLiveLift, lNg )");
    }
  });
});

describe("the lamps' bounced light (index.json ambientBounce)", () => {
  const box = liveStopBox(40, LIVE_LOOK);

  it("is off unless the index says the ambient map holds it", () => {
    expect(parseLiveIndex(sample())!.ambientBounce).toBe(false);
    for (const junk of [1, "true", null, {}]) {
      const j = sample();
      j.ambientBounce = junk;
      expect(parseLiveIndex(j)!.ambientBounce, JSON.stringify(junk)).toBe(false);
    }
    const j = sample();
    j.ambientBounce = true;
    expect(parseLiveIndex(j)!.ambientBounce).toBe(true);
  });

  it("drops the page's own fill when the map has the bake's bounce, and changes nothing else", () => {
    const with_ = sample();
    with_.ambientBounce = true;
    const a = liveValues(parseLiveIndex(with_) as LiveIndex, LIVE_LOOK, box);
    const b = liveValues(parseLiveIndex(sample()) as LiveIndex, LIVE_LOOK, box);
    expect(a.bounce).toEqual([0, 0, 0]);
    expect({ ...a, bounce: b.bounce }).toEqual(b);
    // Without it the fill is what the look asks for (some light, if the look's amount is above 0).
    if (LIVE_LOOK.bounce.amount > 0) expect(b.bounce.some((v) => v > 0)).toBe(true);
  });

  it("is in every installed stop's maps", () => {
    const dir = path.resolve(__dirname, "../../../public/sect/full/live");
    const stops = parseLiveStops(JSON.parse(readFileSync(path.join(dir, "index.json"), "utf8")));
    expect(stops).toContain("gate");
    for (const stop of stops) {
      const ix = parseLiveIndex(JSON.parse(readFileSync(path.join(dir, stop, "index.json"), "utf8")));
      expect(ix, stop).not.toBeNull();
      expect(ix!.ambientBounce, stop).toBe(true);
    }
  });
});

describe("the bake's soft shadow (index.json ambientAlpha)", () => {
  const box = liveStopBox(40, LIVE_LOOK);
  const B = LIVE_LOOK.bakedShadow;
  const withAlpha = (): LiveIndex => {
    const j = sample();
    j.ambientAlpha = "visibility";
    return parseLiveIndex(j) as LiveIndex;
  };
  const pars = liveParsGlsl();
  /** The function in the pars that starts with `sig`, to its closing brace. */
  const fnOf = (sig: string) => {
    const i = pars.indexOf(sig);
    expect(i, sig).toBeGreaterThan(0);
    return pars.slice(i, pars.indexOf("\n}", i) + 2);
  };
  /**
   * sectLiveBakeShare in numbers: from the lookup's metres to the caster (or -1), uSectLiveVis and
   * uSectLiveClose.
   */
  const bakeShare = (metres: number, u: readonly number[], c: readonly number[]) =>
    (metres < 0 ? u[3] : Math.max(smoothstep(u[1], u[2], metres), 1 - smoothstep(c[0], c[1], metres))) * u[0];
  /** sectLiveGraze in numbers: from the cosine between the face and the lamp, uSectLiveGraze and uSectLiveVis. */
  const grazeShare = (nl: number, g: readonly number[], u: readonly number[]) => (1 - smoothstep(g[0], g[1], nl)) * u[0];
  /**
   * sectLiveRadiance's `seen` in numbers, one channel: what the page's own shadows let through of
   * the two lamps. Each lamp's light with no shadow, its (own shadow, share left to the bake), and
   * the bake's vis. GLSL's clamp is min( max( x, lo ), hi ).
   */
  const seenSum = (fromSun: number, fromKey: number, sSun: readonly [number, number], sKey: readonly [number, number], vis: number) => {
    const own = fromSun * (sSun[0] * (1 - sSun[1])) + fromKey * (sKey[0] * (1 - sKey[1]));
    const cap = fromSun * sSun[1] + fromKey * sKey[1];
    return own + Math.min(Math.max((fromSun + fromKey) * vis - own, 0), cap);
  };
  /** The same on 3-vectors, channel by channel, as the GLSL runs it. */
  const seenSum3 = (fromSun: Vec3, fromKey: Vec3, sSun: readonly [number, number], sKey: readonly [number, number], vis: number): Vec3 =>
    fromSun.map((s, i) => seenSum(s, fromKey[i], sSun, sKey, vis)) as Vec3;
  /** sectLiveRadiance's `baked`: the two lamps through the bake's shadow. */
  const bakedSum3 = (fromSun: Vec3, fromKey: Vec3, vis: number): Vec3 => fromSun.map((s, i) => (s + fromKey[i]) * vis) as Vec3;
  /** sectLiveRadiance's `lamps`: the page's maps tighten the bake's shadow where it is soft (bake.y). */
  const lampsSum3 = (fromSun: Vec3, fromKey: Vec3, sSun: readonly [number, number], sKey: readonly [number, number], vis: number, soft: number): Vec3 => {
    const seen = seenSum3(fromSun, fromKey, sSun, sKey, vis);
    const baked = bakedSum3(fromSun, fromKey, vis);
    return baked.map((b, i) => mix(b, Math.min(seen[i], b), soft)) as Vec3;
  };
  /** Coloured lamps as the gate has them: a wall turned to the sun, the key at a slant. */
  const lampsLit = (): [Vec3, Vec3] => {
    const v = liveValues(withAlpha(), LIVE_LOOK, box);
    return [v.sunE.map((c) => c * 0.9) as Vec3, v.keyE.map((c) => c * 0.6) as Vec3];
  };
  const lits = [0, 0.25, 0.7, 1];
  const shares = [0, 0.3, 0.5, 1];
  const viss = [0, 0.4, 0.75, 1];

  it("is off unless the index says the ambient map's alpha holds it", () => {
    expect(parseLiveIndex(sample())!.bakedShadow).toBe(false);
    expect(withAlpha().bakedShadow).toBe(true);
    // Anything else is no baked shadow, and not a reason to drop the index.
    for (const junk of ["Visibility", "visibility ", "coverage", "", true, 1, null, ["visibility"], { kind: "visibility" }]) {
      const j = sample();
      j.ambientAlpha = junk;
      const ix = parseLiveIndex(j);
      expect(ix, JSON.stringify(junk)).not.toBeNull();
      expect(ix!.bakedShadow, JSON.stringify(junk)).toBe(false);
    }
  });

  it("has sane numbers: the page's own shadow near the caster, the bake's from farther off and right at the surface", () => {
    for (const v of [B.nearM, B.farM, B.missing, ...B.graze, ...B.close]) expect(Number.isFinite(v)).toBe(true);
    expect(B.nearM).toBeGreaterThanOrEqual(0);
    expect(B.farM).toBeGreaterThan(B.nearM);
    expect(B.missing).toBeGreaterThanOrEqual(0);
    expect(B.missing).toBeLessThanOrEqual(1);
    // The graze is on a cosine: within 0..1, rising.
    expect(B.graze[0]).toBeGreaterThanOrEqual(0);
    expect(B.graze[1]).toBeGreaterThan(B.graze[0]);
    expect(B.graze[1]).toBeLessThanOrEqual(1);
    // A caster right at the surface is the bake's, and there is a band where the page's own shadow stands.
    expect(B.close[0]).toBeGreaterThanOrEqual(0);
    expect(B.close[1]).toBeGreaterThan(B.close[0]);
    expect(B.close[1]).toBeLessThanOrEqual(B.nearM);
  });

  it("reaches the shader only when the index has it, and changes nothing else", () => {
    const a = liveValues(withAlpha(), LIVE_LOOK, box);
    const b = liveValues(parseLiveIndex(sample()) as LiveIndex, LIVE_LOOK, box);
    expect(a.vis).toEqual([1, B.nearM, B.farM, B.missing]);
    expect(b.vis[0]).toBe(0);
    expect({ ...a, vis: b.vis }).toEqual(b);
  });

  it("keeps farM above nearM, so the shader's smoothstep has a width", () => {
    const look = structuredClone(LIVE_LOOK);
    for (const [nearM, farM] of [
      [4, 4],
      [6, 2],
    ]) {
      look.bakedShadow = { ...LIVE_LOOK.bakedShadow, nearM, farM, missing: 0.5 };
      const v = liveValues(withAlpha(), look, box);
      expect(v.vis[1]).toBe(nearM);
      expect(v.vis[2]).toBeGreaterThan(nearM);
      expect(v.vis[3]).toBe(0.5);
    }
  });

  it("holds the share where nothing casts to 0..1", () => {
    const look = structuredClone(LIVE_LOOK);
    for (const [missing, want] of [
      [1.5, 1],
      [-0.3, 0],
      [0.4, 0.4],
    ]) {
      look.bakedShadow = { ...LIVE_LOOK.bakedShadow, missing };
      expect(liveValues(withAlpha(), look, box).vis[3], String(missing)).toBe(want);
    }
  });

  it("leaves each lamp to the bake by the distance to what casts (sectLiveBakeShare)", () => {
    expect(fnOf("float sectLiveBakeShare(")).toBe(
      [
        "float sectLiveBakeShare( vec2 r ) {",
        "  return ( r.y < 0.0 ? uSectLiveVis.w : max( smoothstep( uSectLiveVis.y, uSectLiveVis.z, r.y ), 1.0 - smoothstep( uSectLiveClose.x, uSectLiveClose.y, r.y ) ) ) * uSectLiveVis.x;",
        "}",
      ].join("\n"),
    );
  });

  it("without it in the map, leaves nothing to the bake", () => {
    const v = liveValues(parseLiveIndex(sample()) as LiveIndex, LIVE_LOOK, box);
    for (const m of [-1, 0, B.close[0], B.nearM, (B.nearM + B.farM) / 2, B.farM, 10 * B.farM]) expect(bakeShare(m, v.vis, v.close), String(m)).toBe(0);
  });

  it("with it, leaves nothing to the bake between the surface's own band and nearM, all of it far off, and `missing` where nothing casts", () => {
    const { vis: u, close: c } = liveValues(withAlpha(), LIVE_LOOK, box);
    for (const m of [B.close[1], (B.close[1] + B.nearM) / 2, B.nearM]) expect(bakeShare(m, u, c), `near ${m}`).toBe(0);
    for (const m of [B.farM, 2 * B.farM, 500]) expect(bakeShare(m, u, c), `far ${m}`).toBe(1);
    expect(bakeShare(-1, u, c)).toBe(B.missing);
    // Between nearM and farM it goes over from one to the other, always within 0..1.
    const steps = Array.from({ length: 21 }, (_, k) => bakeShare(B.nearM + ((B.farM - B.nearM) * k) / 20, u, c));
    for (let k = 1; k < steps.length; k++) expect(steps[k]).toBeGreaterThanOrEqual(steps[k - 1]);
    for (const s of steps) {
      expect(s).toBeGreaterThanOrEqual(0);
      expect(s).toBeLessThanOrEqual(1);
    }
    const mid = bakeShare((B.nearM + B.farM) / 2, u, c);
    expect(mid).toBeGreaterThan(0);
    expect(mid).toBeLessThan(1);
  });

  it("leaves a lamp whose caster is right at the surface to the bake: wholly within close[0], as before past close[1]", () => {
    const { vis: u, close: c } = liveValues(withAlpha(), LIVE_LOOK, box);
    expect([c[0], c[1]]).toEqual(B.close);
    for (const m of [0, B.close[0] / 2, B.close[0]]) expect(bakeShare(m, u, c), `at ${m}`).toBe(1);
    // Past close[1] it is the distance's share alone (the old rule).
    for (const m of [B.close[1], B.nearM, (B.nearM + B.farM) / 2, B.farM, 3 * B.farM]) {
      expect(bakeShare(m, u, c), `past ${m}`).toBe(smoothstep(B.nearM, B.farM, m));
    }
    // In between it falls from 1 to 0 and stays within 0..1.
    const steps = Array.from({ length: 21 }, (_, k) => bakeShare(B.close[0] + ((B.close[1] - B.close[0]) * k) / 20, u, c));
    expect(steps[0]).toBe(1);
    expect(steps[20]).toBe(0);
    for (let k = 1; k < steps.length; k++) expect(steps[k]).toBeLessThanOrEqual(steps[k - 1]);
    for (const s of steps) {
      expect(s).toBeGreaterThanOrEqual(0);
      expect(s).toBeLessThanOrEqual(1);
    }
    // Where nothing casts, the close term has no say.
    expect(bakeShare(-1, u, c)).toBe(B.missing);
  });

  it("leaves a lamp that only grazes a face to the bake (sectLiveGraze)", () => {
    expect(fnOf("float sectLiveGraze(")).toBe(
      [
        "float sectLiveGraze( float nl ) {",
        "  return ( 1.0 - smoothstep( uSectLiveGraze.x, uSectLiveGraze.y, nl ) ) * uSectLiveVis.x;",
        "}",
      ].join("\n"),
    );
    const ix = withAlpha();
    const v = liveValues(ix, LIVE_LOOK, box);
    expect(v.graze).toEqual(B.graze);
    // On level ground (normal straight up) the cosine is the lamp's height: the sample's sun stands
    // 7 degrees up (the bake's), its key well above (the page's).
    expect(grazeShare(ix.light.sun.dir[1], v.graze, v.vis)).toBe(1);
    expect(grazeShare(ix.light.key.dir[1], v.graze, v.vis)).toBe(0);
    // Wholly below graze[0], not at all above graze[1], falling in between.
    expect(grazeShare(B.graze[0], v.graze, v.vis)).toBe(1);
    expect(grazeShare(B.graze[1], v.graze, v.vis)).toBe(0);
    const steps = Array.from({ length: 21 }, (_, k) => grazeShare(k / 20, v.graze, v.vis));
    for (let k = 1; k < steps.length; k++) expect(steps[k]).toBeLessThanOrEqual(steps[k - 1]);
    // Without the bake's shadow in the maps, nothing is left to it.
    const off = liveValues(parseLiveIndex(sample()) as LiveIndex, LIVE_LOOK, box);
    for (const nl of [0, ix.light.sun.dir[1], 1]) expect(grazeShare(nl, off.graze, off.vis)).toBe(0);
  });

  describe("what the page's own shadows let through (seen, in sectLiveRadiance)", () => {
    const radiance = fnOf("vec3 sectLiveRadiance(");

    it("pins the lines seenSum mirrors", () => {
      expect(radiance).toContain("vec3 fromSun = uSectLiveSunE * nl.x;");
      expect(radiance).toContain("vec3 fromKey = uSectLiveKeyE * nl.y;");
      expect(radiance).toContain("vec3 own = fromSun * ( sSun.x * ( 1.0 - sSun.y ) ) + fromKey * ( sKey.x * ( 1.0 - sKey.y ) );");
      expect(radiance).toContain("vec3 cap = fromSun * sSun.y + fromKey * sKey.y;");
      expect(radiance).toContain("vec3 seen = own + clamp( ( fromSun + fromKey ) * vis - own, vec3( 0.0 ), cap );");
      // seen goes to the lamps (against the bake's) and to the shine (got, held), nowhere else.
      expect(code(radiance).match(/\bseen\b/g)).toHaveLength(4);
    });

    it("gives the shine what the diffuse got: the full sun under an eave, none of a lamp shaded near", () => {
      // One channel: `got` is the part left to the bake that the sum let through, over what it could have.
      const shineShare = (fromSun: number, fromKey: number, sSun: readonly [number, number], sKey: readonly [number, number], vis: number) => {
        const own = fromSun * (sSun[0] * (1 - sSun[1])) + fromKey * (sKey[0] * (1 - sKey[1]));
        const cap = fromSun * sSun[1] + fromKey * sKey[1];
        const got = (seenSum(fromSun, fromKey, sSun, sKey, vis) - own) / Math.max(cap, 1e-5);
        return [sSun[0] * (1 - sSun[1]) + sSun[1] * got, sKey[0] * (1 - sKey[1]) + sKey[1] * got] as const;
      };
      // The eave: the key shaded near, the sun open, the bake's total the sun alone.
      const [sun, key] = shineShare(3, 1, [1, 1], [0, 0], 3 / 4);
      expect(sun).toBeCloseTo(1, 12);
      expect(key).toBe(0);
      // Never outside 0..1, and with both lamps left to the bake both get the bake's share.
      for (const xs of lits) {
        for (const ys of shares) {
          for (const xk of lits) {
            for (const yk of shares) {
              for (const vis of viss) {
                for (const s of shineShare(2, 0.7, [xs, ys], [xk, yk], vis)) {
                  expect(s).toBeGreaterThanOrEqual(0);
                  expect(s).toBeLessThanOrEqual(1 + 1e-12);
                }
              }
            }
          }
        }
      }
      for (const vis of viss) {
        const both = shineShare(2, 0.7, [0.3, 1], [0.6, 1], vis);
        expect(both[0]).toBeCloseTo(vis, 12);
        expect(both[1]).toBeCloseTo(vis, 12);
      }
    });

    it("with no lamp left to the bake, is each lamp times its own shadow, whatever vis is", () => {
      const [fS, fK] = lampsLit();
      for (const xs of lits) {
        for (const xk of lits) {
          for (const vis of viss) {
            const got = seenSum3(fS, fK, [xs, 0], [xk, 0], vis);
            const want = fS.map((s, i) => s * xs + fK[i] * xk);
            expect(close(got, want, 1e-12), `${xs} ${xk} ${vis}`).toBe(true);
          }
        }
      }
    });

    it("with both left to the bake, is the two lamps times vis, whatever their own shadows are", () => {
      const [fS, fK] = lampsLit();
      for (const xs of lits) {
        for (const xk of lits) {
          for (const vis of viss) {
            const got = seenSum3(fS, fK, [xs, 1], [xk, 1], vis);
            const want = fS.map((s, i) => (s + fK[i]) * vis);
            expect(close(got, want, 1e-12), `${xs} ${xk} ${vis}`).toBe(true);
          }
        }
      }
    });

    it("under an eave that shades only the key, gives the full sun", () => {
      // On a grey scale: the key shaded by something near (own 0, share 0), the sun with nothing
      // casting (own 1, share 1), and the bake's total the sun alone.
      // The eave a metre or so above: past the surface's own band, short of nearM.
      const { vis: u, close: c } = liveValues(withAlpha(), LIVE_LOOK, box);
      expect(bakeShare((B.close[1] + B.nearM) / 2, u, c)).toBe(0);
      for (const [fS, fK] of [
        [3, 1],
        [1, 3],
        [0.586, 0.832],
      ]) {
        const vis = fS / (fS + fK);
        expect(seenSum(fS, fK, [1, 1], [0, 0], vis), `${fS} ${fK}`).toBeCloseTo(fS, 12);
        // The same for any share the sun is left to the bake.
        for (const s of [...shares, bakeShare(-1, u, c)]) expect(seenSum(fS, fK, [1, s], [0, 0], vis), `${fS} ${fK} ${s}`).toBeCloseTo(fS, 12);
        // And the lamps keep it at any softness: it is the bake's own light there.
        for (const soft of [0, 0.5, 1]) {
          expect(lampsSum3([fS, fS, fS], [fK, fK, fK], [1, 1], [0, 0], vis, soft)[0], `${fS} ${fK} soft ${soft}`).toBeCloseTo(fS, 12);
        }
        // The bake's shadow on each lamp alone cut the sun to fS * vis there.
        expect(fS * vis).toBeLessThan(fS);
      }
    });

    it("never gives a lamp left to the bake more than its own unshadowed light", () => {
      // vis 1, the key shaded near (0, share 0), the sun left to the bake (share 1): the sun, not both.
      const [fS, fK] = lampsLit();
      for (const xs of lits) {
        expect(close(seenSum3(fS, fK, [xs, 1], [0, 0], 1), fS, 1e-12), String(xs)).toBe(true);
        expect(seenSum(3, 1, [xs, 1], [0, 0], 1), String(xs)).toBeCloseTo(3, 12);
      }
    });

    it("is never negative, never above the two lamps, and lies between the page's own total and the bake's", () => {
      const [fS, fK] = lampsLit();
      for (const xs of lits) {
        for (const ys of shares) {
          for (const xk of lits) {
            for (const yk of shares) {
              for (const vis of viss) {
                const got = seenSum3(fS, fK, [xs, ys], [xk, yk], vis);
                for (let i = 0; i < 3; i++) {
                  const at = `${xs} ${ys} ${xk} ${yk} ${vis} ch${i}`;
                  const page = fS[i] * xs + fK[i] * xk;
                  const bake = (fS[i] + fK[i]) * vis;
                  expect(got[i], at).toBeGreaterThanOrEqual(0);
                  expect(got[i], at).toBeLessThanOrEqual(fS[i] + fK[i] + 1e-12);
                  expect(got[i], at).toBeGreaterThanOrEqual(Math.min(page, bake) - 1e-12);
                  expect(got[i], at).toBeLessThanOrEqual(Math.max(page, bake) + 1e-12);
                }
              }
            }
          }
        }
      }
    });
  });

  describe("the lamps: the page's maps only tighten the bake's shadow, where the bake holds it soft", () => {
    const radiance = fnOf("vec3 sectLiveRadiance(");
    const softs = [0, 0.3, 0.7, 1];

    it("pins the lines lampsSum3 mirrors", () => {
      expect(radiance).toContain("vec3 baked = ( fromSun + fromKey ) * vis;");
      expect(radiance).toContain("vec3 lamps = mix( baked, min( seen, baked ), bake.y );");
      expect(radiance).toContain("vec3 direct = alb * RECIPROCAL_PI * lamps;");
      // lamps is the only light the lamps give the diffuse (its third use is the shine's `held`).
      expect(code(radiance).match(/\blamps\b/g)).toHaveLength(3);
      expect(code(radiance).match(/\bbaked\b/g)).toHaveLength(3);
    });

    it("never let in more light than the bake did, for any shadows, shares, vis and softness", () => {
      const [fS, fK] = lampsLit();
      for (const xs of lits) {
        for (const ys of shares) {
          for (const xk of lits) {
            for (const yk of shares) {
              for (const vis of viss) {
                const baked = bakedSum3(fS, fK, vis);
                for (const soft of softs) {
                  const got = lampsSum3(fS, fK, [xs, ys], [xk, yk], vis, soft);
                  for (let i = 0; i < 3; i++) {
                    const at = `${xs} ${ys} ${xk} ${yk} ${vis} ${soft} ch${i}`;
                    expect(got[i], at).toBeLessThanOrEqual(baked[i] + 1e-12);
                    expect(got[i], at).toBeGreaterThanOrEqual(0);
                  }
                }
              }
            }
          }
        }
      }
    });

    it("are the bake's light where its shadow does not change, and the darker of the two where it is soft", () => {
      const [fS, fK] = lampsLit();
      for (const xs of lits) {
        for (const ys of shares) {
          for (const xk of lits) {
            for (const yk of shares) {
              for (const vis of viss) {
                const at = `${xs} ${ys} ${xk} ${yk} ${vis}`;
                const baked = bakedSum3(fS, fK, vis);
                const seen = seenSum3(fS, fK, [xs, ys], [xk, yk], vis);
                expect(close(lampsSum3(fS, fK, [xs, ys], [xk, yk], vis, 0), baked, 1e-12), at).toBe(true);
                expect(close(lampsSum3(fS, fK, [xs, ys], [xk, yk], vis, 1), seen.map((s, i) => Math.min(s, baked[i])), 1e-12), at).toBe(true);
              }
            }
          }
        }
      }
    });

    it("are the bake's light at any softness when both lamps are left to the bake", () => {
      const [fS, fK] = lampsLit();
      for (const xs of lits) {
        for (const xk of lits) {
          for (const vis of viss) {
            for (const soft of softs) {
              const got = lampsSum3(fS, fK, [xs, 1], [xk, 1], vis, soft);
              expect(close(got, bakedSum3(fS, fK, vis), 1e-12), `${xs} ${xk} ${vis} ${soft}`).toBe(true);
            }
          }
        }
      }
    });

    it("take a light leak in the page's maps back to the bake's shade", () => {
      // The page's maps see no caster (lit, nothing left to the bake) where the bake is in shade.
      const [fS, fK] = lampsLit();
      const seen = seenSum3(fS, fK, [1, 0], [1, 0], 0.1);
      const baked = bakedSum3(fS, fK, 0.1);
      for (let i = 0; i < 3; i++) expect(seen[i]).toBeGreaterThan(baked[i]);
      for (const soft of softs) expect(close(lampsSum3(fS, fK, [1, 0], [1, 0], 0.1, soft), baked, 1e-12), String(soft)).toBe(true);
    });

    it("cut the shine by what the bake's shadow took off the page's sum (held), never raise it", () => {
      expect(radiance).toContain("float held = min( dot( lamps, vec3( 0.2126, 0.7152, 0.0722 ) ) / max( dot( seen, vec3( 0.2126, 0.7152, 0.0722 ) ), 1e-5 ), 1.0 );");
      const held = (lamps: Vec3, seen: Vec3) => Math.min(luma(lamps) / Math.max(luma(seen), 1e-5), 1);
      const [fS, fK] = lampsLit();
      for (const xs of lits) {
        for (const ys of shares) {
          for (const vis of viss) {
            for (const soft of softs) {
              const seen = seenSum3(fS, fK, [xs, ys], [1, 0], vis);
              const h = held(lampsSum3(fS, fK, [xs, ys], [1, 0], vis, soft), seen);
              expect(h).toBeGreaterThanOrEqual(0);
              expect(h).toBeLessThanOrEqual(1);
            }
          }
        }
      }
      // A leak (the page lit, the bake in shade): the shine drops to the bake's share of it.
      const seen = seenSum3(fS, fK, [1, 0], [1, 0], 0.1);
      expect(held(lampsSum3(fS, fK, [1, 0], [1, 0], 0.1, 0), seen)).toBeCloseTo(0.1, 12);
      // Where the page's sum is the lamps' light, the shine is left as it was.
      expect(held(seen, seen)).toBe(1);
    });
  });

  describe("bumps cannot outrun the flat face (LIVE_LOOK.bumpCap)", () => {
    const radiance = fnOf("vec3 sectLiveRadiance(");
    const cap = liveValues(withAlpha(), LIVE_LOOK, box).caps[0];
    /** The lines in numbers, one lamp: the bumped normal's cosine and the flat face's. */
    const capped = (raw: number, face: number) => {
      const nl = Math.min(raw, face * cap);
      return { nl, kept: raw > 1e-5 ? nl / raw : 1 };
    };

    it("pins the lines it mirrors, and takes the face from the map's normal", () => {
      expect(radiance).toContain("vec2 nl = min( raw, face * uSectLiveCaps.x );");
      expect(radiance).toContain("vec2 kept = vec2( raw.x > 1e-5 ? nl.x / raw.x : 1.0, raw.y > 1e-5 ? nl.y / raw.y : 1.0 );");
      expect(cap).toBe(LIVE_LOOK.bumpCap);
    });

    it("holds a face that barely sees the lamp to bumpCap times its own light", () => {
      const face = 0.04;
      expect(face * cap).toBeLessThan(1);
      // A bump that leans well toward the lamp.
      const raw = (face * cap + 1) / 2;
      const { nl, kept } = capped(raw, face);
      expect(nl).toBeCloseTo(face * cap, 12);
      expect(kept).toBeCloseTo((face * cap) / raw, 12);
      expect(kept).toBeLessThan(1);
      // A gentler bump is left alone.
      expect(capped(face * cap * 0.9, face)).toEqual({ nl: face * cap * 0.9, kept: 1 });
    });

    it("leaves a face that sees the lamp fully as it is", () => {
      for (const raw of [0, 0.3, 0.8, 1]) {
        const { nl, kept } = capped(raw, 1);
        expect(nl).toBe(raw);
        expect(kept).toBe(1);
      }
    });

    it("gives a face turned away from the lamp nothing, whatever its bumps", () => {
      for (const raw of [0.01, 0.3, 1]) expect(capped(raw, 0)).toEqual({ nl: 0, kept: 0 });
      // No light either way: nothing to cut.
      expect(capped(0, 0)).toEqual({ nl: 0, kept: 1 });
    });
  });

  describe("the shine's cap (LIVE_LOOK.shineCap)", () => {
    const radiance = fnOf("vec3 sectLiveRadiance(");
    const share = liveValues(withAlpha(), LIVE_LOOK, box).caps[1];
    /** The two lines in numbers: the shine times the look's strength, then held to a share of the matte light. */
    const shineOut = (shine: Vec3, matte: Vec3, specular = 1): Vec3 => {
      const s = shine.map((c) => c * specular);
      const k = Math.min(1, (share * luma(matte)) / Math.max(luma(s), 1e-5));
      return s.map((c) => c * k) as Vec3;
    };

    it("pins the lines it mirrors, after the shine's strength", () => {
      const a = radiance.indexOf("shine *= uSectLiveSpecular;");
      const b = radiance.indexOf(
        "shine *= min( 1.0, uSectLiveCaps.y * dot( matte, vec3( 0.2126, 0.7152, 0.0722 ) ) / max( dot( shine, vec3( 0.2126, 0.7152, 0.0722 ) ), 1e-5 ) );",
      );
      expect(a).toBeGreaterThan(0);
      expect(b).toBeGreaterThan(a);
      expect(radiance.indexOf("vec3 matte = amb + direct + bounce;")).toBeLessThan(b);
      expect(share).toBe(LIVE_LOOK.shineCap);
    });

    it("is never above shineCap times the matte light's luminance", () => {
      const mattes: Vec3[] = [
        [0.02, 0.03, 0.08],
        [0.3, 0.1, 0.05],
        [1, 1, 1],
      ];
      const shines: Vec3[] = [
        [0, 0, 0],
        [0.01, 0.01, 0.01],
        [0.5, 0.4, 0.3],
        [5, 5, 5],
      ];
      for (const m of mattes) {
        for (const s of shines) {
          for (const spec of [LIVE_LOOK.specular, 1]) {
            const out = shineOut(s, m, spec);
            expect(luma(out), `${m} ${s}`).toBeLessThanOrEqual(share * luma(m) + 1e-12);
            // Its hue kept: only scaled down.
            for (let i = 0; i < 3; i++) expect(out[i]).toBeLessThanOrEqual(s[i] * spec + 1e-12);
          }
        }
      }
      // A dark board in a bright sun's shine: held to the share exactly.
      expect(luma(shineOut([2, 2, 2], [0.02, 0.03, 0.08]))).toBeCloseTo(share * luma([0.02, 0.03, 0.08]), 12);
    });

    it("leaves a shine below it untouched", () => {
      const m: Vec3 = [0.6, 0.5, 0.4];
      const s: Vec3 = [0.3, 0.2, 0.1].map((c) => (c * share * luma(m)) / luma([0.3, 0.2, 0.1]) * 0.9) as Vec3;
      expect(close(shineOut(s, m), s, 1e-12)).toBe(true);
    });
  });

  describe("the bake's detail (sectLiveDetail)", () => {
    const D = LIVE_LOOK.detail;
    /** uSectLiveDetail with the amount whole and the look's range and floor. */
    const u: [number, number, number, number] = [1, D.min, D.max, D.floor];
    /** sectLiveDetail in numbers; `pre` is the ratio before the clamp. */
    const detail = (baked: Vec3, rebuilt: Vec3, trust: number, d: readonly number[] = u) => {
      const lum = (c: readonly number[]) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
      const b = baked.map((x) => x + d[3]);
      const q = rebuilt.map((x) => x + d[3]);
      const r = b.map((x, i) => x / q[i]);
      const k = mix(lum(q) / lum(b), 1, trust);
      const pre = r.map((x) => x * k) as Vec3;
      const out = pre.map((x) => mix(1, Math.min(Math.max(x, d[1]), d[2]), d[0])) as Vec3;
      return { pre, out };
    };
    const texels: [Vec3, Vec3][] = [
      // (the baked texel, the bake as the maps rebuild it)
      [
        [0.36, 0.18, 0.12],
        [0.3, 0.2, 0.1],
      ],
      [
        [0.05, 0.04, 0.03],
        [0.06, 0.05, 0.03],
      ],
      [
        [0.8, 0.6, 0.5],
        [0.5, 0.45, 0.4],
      ],
    ];

    it("pins the lines it mirrors", () => {
      expect(fnOf("vec3 sectLiveDetail(")).toBe(
        [
          "vec3 sectLiveDetail( vec3 baked, vec3 rebuilt, float trust ) {",
          "  vec3 b = baked + uSectLiveDetail.w;",
          "  vec3 q = rebuilt + uSectLiveDetail.w;",
          "  vec3 r = b / q;",
          "  r *= mix( dot( q, vec3( 0.2126, 0.7152, 0.0722 ) ) / dot( b, vec3( 0.2126, 0.7152, 0.0722 ) ), 1.0, trust );",
          "  return mix( vec3( 1.0 ), clamp( r, uSectLiveDetail.y, uSectLiveDetail.z ), uSectLiveDetail.x );",
          "}",
        ].join("\n"),
      );
    });

    it("gives back the baked texel where live changes nothing and the rebuilt bake is trusted", () => {
      for (const [baked, rebuilt] of texels) {
        const { pre, out } = detail(baked, rebuilt, 1);
        // Inside the range, so the clamp has no say.
        for (const x of pre) {
          expect(x).toBeGreaterThan(D.min);
          expect(x).toBeLessThan(D.max);
        }
        for (let i = 0; i < 3; i++) {
          // The live colour is the rebuilt bake: times the factor it is the baked texel, give or take
          // the floor (exactly floor * (1 - factor) off).
          const got = rebuilt[i] * out[i];
          expect(got - baked[i]).toBeCloseTo(D.floor * (1 - out[i]), 12);
          expect(Math.abs(got - baked[i])).toBeLessThanOrEqual(D.floor * Math.max(1 - D.min, D.max - 1) + 1e-12);
        }
      }
      // Where the two agree it is exactly 1.
      expect(detail([0.2, 0.3, 0.4], [0.2, 0.3, 0.4], 1).out).toEqual([1, 1, 1]);
    });

    it("takes only the hue where the rebuilt bake is not trusted: the rebuilt light keeps its brightness", () => {
      const lum = (c: readonly number[]) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
      for (const [baked, rebuilt] of texels) {
        const { pre } = detail(baked, rebuilt, 0);
        const q = rebuilt.map((x) => x + D.floor);
        expect(lum(q.map((x, i) => x * pre[i]))).toBeCloseTo(lum(q), 12);
      }
      // A bake brighter all over is a level, not a hue: nothing is taken.
      const { out } = detail([0.4, 0.4, 0.4], [0.2, 0.2, 0.2], 0);
      for (const x of out) expect(x).toBeCloseTo(1, 12);
    });

    it("is 1 at amount 0, and its amount reaches the shader only with the bake's shadow and bounce", () => {
      for (const [baked, rebuilt] of texels) {
        for (const trust of [0, 0.5, 1]) expect(detail(baked, rebuilt, trust, [0, D.min, D.max, D.floor]).out).toEqual([1, 1, 1]);
      }
      // The bake's shadow without its bounce: 0.
      expect(liveValues(withAlpha(), LIVE_LOOK, box).detail[0]).toBe(0);
    });

    it("holds the factor to its range, whatever the texels", () => {
      const extremes: [Vec3, Vec3][] = [
        [
          [1, 1, 1],
          [0, 0, 0],
        ],
        [
          [0, 0, 0],
          [1, 1, 1],
        ],
        [
          [1, 0, 0],
          [0, 1, 1],
        ],
        [
          [0, 0, 0],
          [0, 0, 0],
        ],
      ];
      for (const [baked, rebuilt] of [...texels, ...extremes]) {
        for (const trust of [0, 0.5, 1]) {
          for (const amount of [0.5, 1]) {
            for (const x of detail(baked, rebuilt, trust, [amount, D.min, D.max, D.floor]).out) {
              expect(Number.isFinite(x)).toBe(true);
              expect(x).toBeGreaterThanOrEqual(D.min - 1e-12);
              expect(x).toBeLessThanOrEqual(D.max + 1e-12);
            }
          }
        }
      }
      // No light in either: left as it is.
      expect(detail([0, 0, 0], [0, 0, 0], 1).out).toEqual([1, 1, 1]);
    });

    it("trusts the rebuilt bake except at the edge of a shadow the page keeps", () => {
      const apply = liveApplyGlsl();
      const L = "vec3( 0.2126, 0.7152, 0.0722 )";
      expect(apply).toContain(`vec2 lW = lFace * vec2( dot( uSectLiveSunE, ${L} ), dot( uSectLiveKeyE, ${L} ) );`);
      expect(apply).toContain("float lLeft = lW.x + lW.y > 1e-5 ? ( lW.x * lSun.y + lW.y * lKey.y ) / ( lW.x + lW.y ) : 1.0;");
      expect(apply).toContain("float lTrust = 1.0 - ( 1.0 - lLeft ) * smoothstep( 0.2, 0.6, 4.0 * lVis * ( 1.0 - lVis ) );");
      const trust = (left: number, vis: number) => 1 - (1 - left) * smoothstep(0.2, 0.6, 4 * vis * (1 - vis));
      for (const left of [0, 0.4, 1]) {
        // Away from the edge of the bake's shadow (vis 0 or 1): trusted.
        expect(trust(left, 0)).toBe(1);
        expect(trust(left, 1)).toBe(1);
        // Half way across it: only as much as is left to the bake.
        expect(trust(left, 0.5)).toBeCloseTo(left, 12);
      }
      // Everything left to the bake: trusted whatever vis is.
      for (const vis of viss) expect(trust(1, vis)).toBe(1);
      for (const left of [0, 0.4, 1]) for (const vis of viss) expect(trust(left, vis)).toBeGreaterThanOrEqual(0);
    });
  });

  it("reads the ambient map once, takes the bake's shadow from its alpha before the branch, and hands it to the sum, the rebuilt bake and the detail's trust", () => {
    for (const src of [liveApplyGlsl(), liveApplyGlsl(true)]) {
      expect(src.match(/tSectLiveAmbient/g)).toHaveLength(1);
      expect(src).toContain("vec4 lAmbA = texture2D( tSectLiveAmbient, vMapUv );");
      expect(src).toContain("vec3 lAmb = lAmbA.rgb;");
      const vis = /float (\w+) = clamp\( \( lAmbA\.a - ([\d.]+) \) \/ ([\d.]+), 0\.0, 1\.0 \);/.exec(src)!;
      expect(vis).not.toBeNull();
      // Its two ends held inside 0..1. A map with no alpha reads 1 there: full light.
      const [lo, width] = [Number(vis[2]), Number(vis[3])];
      const read = (a: number) => Math.min(Math.max((a - lo) / width, 0), 1);
      expect(lo).toBeGreaterThanOrEqual(0);
      expect(width).toBeGreaterThan(0);
      expect(lo + width).toBeLessThanOrEqual(1);
      expect(read(1)).toBe(1);
      expect(read(0)).toBe(0);
      // Straight in between: the sum reads it as a share of the lamps' light, so a curve would bend the bake's ratio.
      expect(read(lo + width / 2)).toBeCloseTo(0.5, 12);
      expect(read(lo + width / 4)).toBeCloseTo(0.25, 12);
      // The texel is read for its colour and its alpha, nothing else.
      expect(src.match(/\blAmbA\b/g)).toHaveLength(3);
      expect(src.indexOf("vec4 lAmbA")).toBeLessThan(vis.index);
      expect(vis.index).toBeLessThan(src.indexOf("if ( sectLiveShare > 0.0 ) {"));
      // The sum of the two lamps gets it, the rebuilt bake and the detail's trust (twice), and
      // nothing else reads it: the lookups do not take it.
      expect(src).toContain(`sectLiveRadiance( lAlb, lAmb * uSectLiveAmbient, sectLiveN, lV, lSun, lKey, vec2( ${vis[1]}, lSoft ), lFace, lRough, lRefl )`);
      expect(src).toContain(`sectLiveBaked( lAlb, lAmb * uSectLiveAmbient, lFace, ${vis[1]} )`);
      expect(src).toContain(`4.0 * ${vis[1]} * ( 1.0 - ${vis[1]} )`);
      expect(src).toContain("vec2 lKey = sectLiveShadow( vSectWorld + uSectLiveKeyDir * uSectLiveLift, lNg );");
      expect(src).toContain("vec2 lSun = sectLiveSunShadow( vSectWorld + uSectLiveSunDir * uSectLiveLift, lNg );");
      expect(src.match(new RegExp(`\\b${vis[1]}\\b`, "g"))).toHaveLength(5);
    }
  });

  it("multiplies the live colour by the bake's detail before it is mixed in, both after the vertex colours", () => {
    for (const src of [liveApplyGlsl(), liveApplyGlsl(true)]) {
      const order = [
        "vec3 lTex = sectLivePost( sectLiveRadiance(",
        "vec3 lBake = sectLivePostBy( sectLiveBaked( lAlb, lAmb * uSectLiveAmbient, lFace, lVis ), uSectLiveBakePost );",
        "#if defined( USE_COLOR ) || defined( USE_COLOR_ALPHA )\n        lTex *= vColor.rgb;\n        lBake *= vColor.rgb;\n      #endif",
        "float lTrust = ",
        "lTex *= sectLiveDetail( sectTexel, lBake, lTrust );",
        "sectTexel = mix( sectTexel, lTex, sectLiveShare );",
      ].map((x) => src.indexOf(x));
      expect(order.every((i) => i >= 0), String(order)).toBe(true);
      expect([...order].sort((a, b) => a - b)).toEqual(order);
      // The baked texel it reads is the one the bake wrote: nothing has replaced it yet.
      expect(src.match(/\bsectTexel =/g)).toHaveLength(1);
      // Each made once, used once more each.
      expect(src.match(/\blBake\b/g)).toHaveLength(3);
      expect(src.match(/\blTrust\b/g)).toHaveLength(2);
      // In the live branch.
      expect(src.indexOf("vec3 lBake")).toBeGreaterThan(src.indexOf("if ( sectLiveShare > 0.0 ) {"));
    }
    // The detail uniform holds the amount at 0 unless the stop's maps can rebuild the bake (liveValues).
    expect(liveParsGlsl()).toContain("uniform vec4 uSectLiveDetail;");
  });

  it("reads a WebP's alpha from its header", () => {
    const ascii = (s: string) => Uint8Array.from(s, (c) => c.charCodeAt(0));
    const head = (chunk: string, bytes: Record<number, number> = {}) => {
      const b = new Uint8Array(30);
      b.set(ascii("RIFF"), 0);
      b.set(ascii("WEBP"), 8);
      b.set(ascii(chunk), 12);
      for (const [k, v] of Object.entries(bytes)) b[Number(k)] = v;
      return b;
    };
    expect(webpAlpha(head("VP8X", { 20: 0x10 }))).toBe(true);
    expect(webpAlpha(head("VP8X", { 20: 0x30 }))).toBe(true);
    // An ICC profile and no alpha.
    expect(webpAlpha(head("VP8X", { 20: 0x20 }))).toBe(false);
    expect(webpAlpha(head("VP8 ", { 20: 0xff }))).toBe(false);
    expect(webpAlpha(head("VP8L", { 20: 0x2f, 24: 0x10 }))).toBe(true);
    expect(webpAlpha(head("VP8L", { 20: 0x2f, 24: 0xef }))).toBe(false);
    expect(webpAlpha(head("ALPH", { 20: 0x10 }))).toBeNull();
    expect(webpAlpha(ascii("RIFF0000WEBPVP8X0000000"))).toBeNull();
    expect(webpAlpha(ascii("not a webp at all, but long enough"))).toBeNull();
  });

  it("tells a Git LFS pointer from a map", () => {
    const ascii = (s: string) => Uint8Array.from(s, (c) => c.charCodeAt(0));
    // What a checkout without LFS holds, cut to the 32 bytes the tests read.
    const pointer = "version https://git-lfs.github.com/spec/v1\noid sha256:0000\nsize 1\n";
    expect(lfsPointer(ascii(pointer).subarray(0, 32))).toBe(true);
    expect(webpAlpha(ascii(pointer).subarray(0, 32))).toBeNull();
    expect(lfsPointer(ascii("RIFF0000WEBPVP8X00000000000000000"))).toBe(false);
    expect(lfsPointer(new Uint8Array(0))).toBe(false);
  });
});
