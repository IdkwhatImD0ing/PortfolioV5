import { describe, expect, it } from "vitest";
import { distanceToPath2D, pathCellKey } from "./cells";
import { holdPanels, hotspotArea, hotspotCard } from "./content";
import {
  fogChunks,
  fogConstantsFromMeta,
  glslFloat,
  hazeVeil,
  hexToLinear,
} from "./glsl";
import { tilingNoise, valueNoise } from "./noise";
import { parseMeta } from "./parse";
import { boxHits, canStandIn, containedItemAt, pickWithBoxes, rayBox, rayBoxSpan } from "./pick";
import {
  chooseTier,
  classifyGpu,
  combinedProgress,
  damp,
  CAPPED_FPS,
  capIsMoot,
  CHOICE_FRAME_BUDGET_MS,
  climbCost,
  climbRebuildsPipeline,
  degradeQuality,
  FEATURE_CLIMB_COST,
  effectiveDpr,
  framesOverBudget,
  isAppleGpu,
  RENDER_SCALE_MIN,
  upgradeQuality,
  isGzip,
  meshoptWorkerCount,
  parseSectParams,
  readTierChoice,
  resolveTier,
  sectAssetBase,
  TIER_KEY,
  TIER_LABELS,
  TIER_ORDER,
  tierChange,
  tierQuality,
  waitsForEnter,
  writeTierChoice,
  type Quality,
} from "./runtime";
import { PORTFOLIO } from "@/lib/portfolio-data";

describe("damp", () => {
  it("moves part of the way toward the target", () => {
    const x = damp(0, 10, 6, 1 / 60);
    expect(x).toBeGreaterThan(0);
    expect(x).toBeLessThan(10);
  });

  it("is frame-rate independent", () => {
    let a = 0;
    for (let i = 0; i < 4; i++) a = damp(a, 10, 6, 1 / 120);
    const b = damp(damp(0, 10, 6, 1 / 60), 10, 6, 1 / 60);
    expect(a).toBeCloseTo(b, 9);
  });

  it("clamps long frames and snaps when close", () => {
    expect(damp(0, 10, 6, 5)).toBeCloseTo(damp(0, 10, 6, 0.1), 12);
    expect(damp(9.99999, 10, 6, 1 / 60)).toBe(10);
  });
});

describe("parseSectParams", () => {
  it("reads frame, debug and flyer", () => {
    expect(parseSectParams("?frame=93&debug=1&flyer=1")).toEqual({
      frame: 93,
      debug: true,
      flyer: true,
      ui: true,
      tier: null,
      set: "full",
      open: null,
    });
    expect(parseSectParams("?ui=0").ui).toBe(false);
    expect(parseSectParams("?tier=low").tier).toBe("low");
    expect(parseSectParams("?tier=mid").tier).toBe("mid");
    expect(parseSectParams("?tier=ultra").tier).toBeNull();
  });

  it("defaults to off and ignores junk", () => {
    expect(parseSectParams("")).toEqual({ frame: null, debug: false, flyer: false, ui: true, tier: null, set: "full", open: null });
    expect(parseSectParams("?frame=abc&debug=0&flyer=false")).toEqual({
      frame: null,
      debug: false,
      flyer: false,
      ui: true,
      tier: null,
      set: "full",
      open: null,
    });
    expect(parseSectParams("frame=12.5").frame).toBe(12.5);
  });

  it("waits for Enter except in the screenshot views", () => {
    expect(waitsForEnter(parseSectParams(""))).toBe(true);
    expect(waitsForEnter(parseSectParams("?open=project:dispatchai&tier=low"))).toBe(true);
    expect(waitsForEnter(parseSectParams("?ui=0"))).toBe(false);
    expect(waitsForEnter(parseSectParams("?frame=352&ui=0&tier=high"))).toBe(false);
    expect(waitsForEnter(parseSectParams("?frame=93"))).toBe(false);
  });

  it("reads the asset set and the item to open, rejecting anything path-like", () => {
    expect(parseSectParams("?set=proto").set).toBe("proto");
    expect(parseSectParams("?set=DEV-v2").set).toBe("dev-v2");
    expect(parseSectParams("?set=../secret").set).toBe("full");
    expect(parseSectParams("?set=").set).toBe("full");
    expect(parseSectParams("?open=project:dispatchai").open).toBe("project:dispatchai");
    expect(parseSectParams("?open=hackathon:12").open).toBe("hackathon:12");
    expect(parseSectParams("?open=<script>").open).toBeNull();
    expect(parseSectParams("?open=").open).toBeNull();
  });

  it("ignores ?set= in a production build", () => {
    expect(parseSectParams("?set=proto", false).set).toBe("full");
    expect(parseSectParams("?set=proto", true).set).toBe("proto");
  });
});

describe("sectAssetBase", () => {
  it("serves from /sect unless a CDN base is configured", () => {
    expect(sectAssetBase("full")).toBe("/sect/full");
    expect(sectAssetBase("full", "")).toBe("/sect/full");
    expect(sectAssetBase("full", "https://cdn.example.com/sect/v3/")).toBe("https://cdn.example.com/sect/v3/full");
  });
});

describe("chooseTier", () => {
  const desktop = { coarsePointer: false, deviceMemory: 8, hardwareConcurrency: 16, maxTextureSize: 16384 };

  it("is high on a desktop with a discrete or unknown GPU", () => {
    expect(chooseTier({ ...desktop, renderer: "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)" })).toBe("high");
    expect(chooseTier(desktop)).toBe("high");
    expect(chooseTier({ ...desktop, renderer: "Apple M2 Pro" })).toBe("high");
  });

  it("is mid on integrated laptop GPUs and small machines", () => {
    expect(chooseTier({ ...desktop, renderer: "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)" })).toBe("mid");
    expect(chooseTier({ ...desktop, renderer: "ANGLE (AMD, AMD Radeon(TM) Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)" })).toBe("mid");
    expect(chooseTier({ ...desktop, hardwareConcurrency: 4 })).toBe("mid");
  });

  it("starts touch devices on low unless they look strong", () => {
    expect(chooseTier({ coarsePointer: true, deviceMemory: 4, hardwareConcurrency: 8, maxTextureSize: 16384 })).toBe("low");
    // iOS hides deviceMemory; "Apple GPU" alone is not proof of a strong device.
    expect(chooseTier({ coarsePointer: true, hardwareConcurrency: 6, maxTextureSize: 16384, renderer: "Apple GPU" })).toBe("low");
    expect(chooseTier({ coarsePointer: true, deviceMemory: 8, hardwareConcurrency: 8, maxTextureSize: 8192, renderer: "Mali-G710" })).toBe("low");
    expect(chooseTier({ coarsePointer: true, deviceMemory: 8, hardwareConcurrency: 8, maxTextureSize: 16384, renderer: "Intel(R) Iris(R) Xe Graphics" })).toBe("mid");
  });

  it("is low on a weak or software GPU", () => {
    expect(chooseTier({ coarsePointer: false, maxTextureSize: 2048 })).toBe("low");
    expect(chooseTier({ ...desktop, renderer: "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)), SwiftShader driver)" })).toBe("low");
  });
});

describe("classifyGpu", () => {
  it("sorts renderer strings into classes", () => {
    expect(classifyGpu("Adreno (TM) 740")).toBe("mobile");
    expect(classifyGpu("ANGLE (Intel, Intel(R) Arc(TM) A770 Graphics, D3D11)")).toBe("discrete");
    expect(classifyGpu("ANGLE (Intel, Intel(R) HD Graphics 520, D3D11)")).toBe("integrated");
    expect(classifyGpu("llvmpipe (LLVM 15.0.7, 256 bits)")).toBe("software");
    expect(classifyGpu(undefined)).toBe("unknown");
  });

  it("puts entry-level and old NVIDIA parts with the integrated GPUs (mid), not with High", () => {
    for (const r of [
      "ANGLE (NVIDIA, NVIDIA GeForce MX450 (0x00001F97) Direct3D11 vs_5_0 ps_5_0, D3D11)",
      "ANGLE (NVIDIA, NVIDIA GeForce MX150 Direct3D11 vs_5_0 ps_5_0, D3D11)",
      "ANGLE (NVIDIA, NVIDIA GeForce GT 1030 Direct3D11 vs_5_0 ps_5_0, D3D11)",
      "ANGLE (NVIDIA, NVIDIA GeForce GT 730 Direct3D11 vs_5_0 ps_5_0, D3D11)",
      "ANGLE (NVIDIA, NVIDIA GeForce 940MX Direct3D11 vs_5_0 ps_5_0, D3D11)",
      "ANGLE (NVIDIA, NVIDIA GeForce 920M Direct3D11 vs_5_0 ps_5_0, D3D11)",
      "ANGLE (NVIDIA, NVIDIA Quadro K620 Direct3D11 vs_5_0 ps_5_0, D3D11)",
      "ANGLE (NVIDIA, NVIDIA Quadro K2200 Direct3D11 vs_5_0 ps_5_0, D3D11)",
      "ANGLE (NVIDIA, NVIDIA Quadro P620 Direct3D11 vs_5_0 ps_5_0, D3D11)",
      "ANGLE (NVIDIA, NVIDIA Quadro M520 Direct3D11 vs_5_0 ps_5_0, D3D11)",
      "ANGLE (NVIDIA, NVIDIA NVS 310 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    ])
      expect(classifyGpu(r), r).toBe("integrated");
    for (const r of [
      "ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)",
      "ANGLE (NVIDIA, NVIDIA GeForce RTX 3050 Laptop GPU Direct3D11 vs_5_0 ps_5_0, D3D11)",
      "ANGLE (NVIDIA, NVIDIA Quadro RTX 4000 Direct3D11 vs_5_0 ps_5_0, D3D11)",
      "ANGLE (NVIDIA, NVIDIA Quadro P2000 Direct3D11 vs_5_0 ps_5_0, D3D11)",
      "ANGLE (NVIDIA, NVIDIA RTX A2000 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    ])
      expect(classifyGpu(r), r).toBe("discrete");
    const desktop = { coarsePointer: false, deviceMemory: 8, hardwareConcurrency: 16, maxTextureSize: 16384 };
    expect(chooseTier({ ...desktop, renderer: "ANGLE (NVIDIA, NVIDIA GeForce MX350 Direct3D11 vs_5_0 ps_5_0, D3D11)" })).toBe("mid");
  });
});

describe("Safari's Apple GPU", () => {
  it("is recognised only by Safari's masked name", () => {
    expect(isAppleGpu("Apple GPU")).toBe(true);
    expect(isAppleGpu(" apple gpu ")).toBe(true);
    expect(isAppleGpu("ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Pro, Unspecified Version)")).toBe(false);
    expect(isAppleGpu("Apple M2")).toBe(false);
    expect(isAppleGpu(undefined)).toBe(false);
  });

  it("starts Medium at up to 1.5x on a Mac (the ladder steps down from there); Low and phones as before", () => {
    expect(tierQuality("mid", 2, { appleGpu: true })).toMatchObject({ maxDpr: 1.5, msaa: 0, bloom: true, lowTextures: false });
    expect(effectiveDpr(tierQuality("mid", 2, { appleGpu: true }), 2)).toBe(1.5);
    expect(tierQuality("mid", 2)).toMatchObject({ maxDpr: 1 });
    expect(tierQuality("low", 2, { appleGpu: true })).toMatchObject({ maxDpr: 1 });
    expect(tierQuality("low", 3, { coarse: true, appleGpu: true })).toMatchObject({ maxDpr: 1.5, lowTextures: true });
    // The same pipeline and textures, so a live switch is unaffected.
    expect(tierChange("mid", "high", 2, false)).toBe("live");
  });
});

/** What changed between two ladder levels (one step), for the ladder tests. */
function stepName(a: Quality, b: Quality, dpr: number): string {
  if (a.maxFps !== b.maxFps) return "fps";
  if (Boolean(a.noCards) !== Boolean(b.noCards)) return "no cards";
  if (Boolean(a.standIns) !== Boolean(b.standIns)) return "stand-ins";
  if (a.msaa !== b.msaa) return "msaa";
  if (a.bloom !== b.bloom) return "bloom";
  const lo = Math.min(effectiveDpr(a, dpr), effectiveDpr(b, dpr));
  return lo < 1 ? "scale" : "dpr";
}

describe("quality ladder", () => {
  it("high renders at up to 1.5x with 4x MSAA at 1x and 2x MSAA from 1.25x up", () => {
    expect(tierQuality("high", 1)).toMatchObject({ maxDpr: 1.5, msaa: 4, bloom: true, post: true });
    expect(tierQuality("high", 1.2).msaa).toBe(4);
    // A 1440p screen at 125 % scaling.
    expect(tierQuality("high", 1.25).msaa).toBe(2);
    expect(tierQuality("high", 1.5).msaa).toBe(2);
    expect(tierQuality("high", 2).msaa).toBe(2);
    expect(effectiveDpr(tierQuality("high", 1), 1)).toBe(1);
    expect(effectiveDpr(tierQuality("high", 2), 2)).toBe(1.5);
  });

  it("mid has bloom but no MSAA at 1x; low has no postprocessing and 2048 px textures", () => {
    expect(tierQuality("mid")).toEqual({ maxDpr: 1, msaa: 0, bloom: true, post: true, lowTextures: false, maxFps: 0 });
    expect(tierQuality("low")).toEqual({ maxDpr: 1, msaa: 0, bloom: false, post: false, lowTextures: true, maxFps: 0 });
  });

  it("touch screens render sharper, and the mid tier there takes the 2048 px textures", () => {
    expect(tierQuality("low", 3, { coarse: true })).toMatchObject({ maxDpr: 1.5, lowTextures: true });
    expect(tierQuality("mid", 2, { coarse: true })).toMatchObject({ maxDpr: 1.5, lowTextures: true, bloom: true });
    expect(effectiveDpr(tierQuality("low", 3, { coarse: true }), 3)).toBe(1.5);
  });

  it("a phone at the bottom of the ladder still has steps left: the render scale, stand-ins, tree cards, the render rate", () => {
    let q = tierQuality("low", 3, { coarse: true });
    const steps: string[] = [];
    for (let i = 0; i < 10; i++) {
      const n = degradeQuality(q, 3);
      if (!n) break;
      steps.push(
        n.maxFps !== q.maxFps ? "fps" : n.standIns !== q.standIns ? "stand-ins" : n.noCards !== q.noCards ? "no cards" : n.maxDpr < 1 ? "scale" : "dpr",
      );
      q = n;
    }
    expect(steps).toEqual(["dpr", "dpr", "scale", "stand-ins", "no cards", "fps"]);
    expect(q).toMatchObject({ maxFps: CAPPED_FPS, standIns: true, noCards: true });
    expect(effectiveDpr(q, 3)).toBe(RENDER_SCALE_MIN);
    expect(degradeQuality({ ...tierQuality("low"), maxDpr: RENDER_SCALE_MIN }, 1)).toMatchObject({ standIns: true, maxFps: 0 });
    expect(degradeQuality({ ...tierQuality("low"), maxDpr: RENDER_SCALE_MIN, standIns: true, noCards: true }, 1)).toMatchObject({
      maxFps: CAPPED_FPS,
    });
  });

  it("steps down resolution, MSAA, bloom, the render scale, the other areas, the tree cards, the render rate, then stops", () => {
    let q = tierQuality("high", 2);
    const steps: string[] = [];
    for (let i = 0; i < 12; i++) {
      const n = degradeQuality(q, 2);
      if (!n) break;
      steps.push(stepName(q, n, 2));
      q = n;
    }
    expect(steps).toEqual(["dpr", "dpr", "msaa", "bloom", "scale", "stand-ins", "no cards", "fps"]);
    expect(q.post).toBe(true);
    expect(degradeQuality(q, 2)).toBeNull();
  });

  it("the render scale renders under 1x whatever the screen; 1x and up never above the screen", () => {
    const q = { ...tierQuality("mid"), maxDpr: RENDER_SCALE_MIN };
    expect(effectiveDpr(q, 1)).toBe(0.75);
    expect(effectiveDpr(q, 2)).toBe(0.75);
    expect(effectiveDpr(tierQuality("mid"), 0.9)).toBe(1);
    expect(effectiveDpr(tierQuality("high"), 1.25)).toBe(1.25);
  });

  it("puts no render-rate cap on a screen that already runs at 30 Hz", () => {
    const bottom = { ...tierQuality("mid"), bloom: false, maxDpr: RENDER_SCALE_MIN, standIns: true, noCards: true };
    expect(degradeQuality(bottom, 1, { cadenceMs: 33.3 })).toBeNull();
    expect(degradeQuality(bottom, 1, { cadenceMs: 16.7 })).toMatchObject({ maxFps: CAPPED_FPS });
    // Not known yet: the cap may apply.
    expect(degradeQuality(bottom, 1, { cadenceMs: null })).toMatchObject({ maxFps: CAPPED_FPS });
    expect(capIsMoot(30, 33.4)).toBe(true);
    expect(capIsMoot(30, 31.5)).toBe(true);
    expect(capIsMoot(30, 16.7)).toBe(false);
    expect(capIsMoot(30, null)).toBe(false);
    expect(capIsMoot(0, 33.3)).toBe(false);
  });

  it("climbs back in the reverse order: the cap, tree cards, other areas, 1x, bloom, MSAA, then resolution", () => {
    const top = tierQuality("high", 2);
    const bottom: Quality = { ...top, msaa: 0, bloom: false, maxDpr: RENDER_SCALE_MIN, maxFps: CAPPED_FPS, standIns: true, noCards: true };
    let q = bottom;
    const seen: string[] = [];
    for (let i = 0; i < 12; i++) {
      const n = upgradeQuality(q, top, 2);
      if (!n) break;
      seen.push(stepName(q, n, 2));
      q = n;
    }
    expect(seen).toEqual(["fps", "no cards", "stand-ins", "scale", "bloom", "msaa", "dpr", "dpr"]);
    expect(q).toMatchObject({ msaa: top.msaa, bloom: true, maxFps: 0, standIns: false, noCards: false, maxDpr: 1.5 });
    // Each climb undoes one step down: the climb is the way down, reversed.
    let d: Quality | null = top;
    const down: string[] = [];
    while (d) {
      const n = degradeQuality(d, 2);
      if (n) down.push(stepName(d, n, 2));
      d = n;
    }
    expect(down).toEqual([...seen].reverse());
    // Never above the screen: a 1x screen climbs no further than 1x.
    expect(upgradeQuality({ ...top, maxDpr: 1 }, top, 1)).toBeNull();
    expect(upgradeQuality(top, top, 2)).toBeNull();
    // The pixel cost of each climb, for the headroom test; a feature costs FEATURE_CLIMB_COST.
    expect(climbCost({ ...top, maxDpr: 1 }, top, 2)).toBeCloseTo(1.5625, 6);
    expect(climbCost({ ...top, maxDpr: RENDER_SCALE_MIN }, top, 2)).toBeCloseTo(16 / 9, 6);
    expect(climbCost({ ...top, maxFps: CAPPED_FPS, maxDpr: 1 }, top, 2)).toBe(1);
    expect(climbCost({ ...top, noCards: true }, top, 2)).toBe(FEATURE_CLIMB_COST);
    expect(climbCost({ ...top, standIns: true }, top, 2)).toBe(FEATURE_CLIMB_COST);
    expect(climbCost({ ...top, bloom: false, msaa: 0, maxDpr: 1 }, top, 2)).toBe(FEATURE_CLIMB_COST);
    expect(climbCost(top, top, 2)).toBeNull();
  });

  it("brings 4x MSAA back in two steps, and says which climbs rebuild the pipeline (taken at rest)", () => {
    const top = tierQuality("high", 1);
    expect(top.msaa).toBe(4);
    const noMsaa = { ...top, msaa: 0 };
    expect(upgradeQuality(noMsaa, top, 1)).toMatchObject({ msaa: 2 });
    expect(upgradeQuality({ ...top, msaa: 2 }, top, 1)).toMatchObject({ msaa: 4 });
    expect(climbRebuildsPipeline(noMsaa, top, 1)).toBe(true);
    expect(climbRebuildsPipeline({ ...top, bloom: false, msaa: 0 }, top, 1)).toBe(true);
    // Tree cards, stand-ins and resolution switch without a rebuild.
    expect(climbRebuildsPipeline({ ...noMsaa, noCards: true }, top, 1)).toBe(false);
    expect(climbRebuildsPipeline({ ...noMsaa, standIns: true }, top, 1)).toBe(false);
    expect(climbRebuildsPipeline({ ...tierQuality("high", 2), maxDpr: 1 }, tierQuality("high", 2), 2)).toBe(false);
    expect(climbRebuildsPipeline(top, top, 1)).toBe(false);
  });

  it("a tier that never had bloom or MSAA climbs back without them (Low on a phone)", () => {
    const top = tierQuality("low", 3, { coarse: true });
    let q: Quality | null = { ...top, maxDpr: RENDER_SCALE_MIN, standIns: true, noCards: true, maxFps: CAPPED_FPS };
    let last = q;
    while (q) {
      last = q;
      q = upgradeQuality(q, top, 3);
    }
    expect(last).toMatchObject({ msaa: 0, bloom: false, standIns: false, noCards: false, maxFps: 0 });
    expect(effectiveDpr(last, 3)).toBe(1.5);
  });

  it("degrades when the median frame is over 20 ms", () => {
    expect(framesOverBudget(Array(30).fill(16.7))).toBe(false);
    expect(framesOverBudget(Array(30).fill(25))).toBe(true);
    expect(framesOverBudget([40, 40])).toBe(false);
  });

  it("a tier the visitor picked steps down resolution only, to the render scale, and only under 25 fps", () => {
    for (const [tier, dpr, coarse] of [
      ["high", 2, false],
      ["high", 1, false],
      ["mid", 3, true],
      ["low", 3, true],
      ["mid", 1, false],
    ] as const) {
      const start = tierQuality(tier, dpr, { coarse });
      let q = start;
      const dprs: number[] = [];
      for (let i = 0; i < 10; i++) {
        const n = degradeQuality(q, dpr, { keepLook: true });
        if (!n) break;
        dprs.push(n.maxDpr);
        // Everything that makes the tier look like itself stays.
        expect({ ...n, maxDpr: 0 }, `${tier} ${dpr}`).toEqual({ ...start, maxDpr: 0 });
        q = n;
      }
      expect(effectiveDpr(q, dpr), `${tier} ${dpr}`).toBe(RENDER_SCALE_MIN);
      expect(dprs.every((d, i) => i === 0 || d < dprs[i - 1])).toBe(true);
    }
    // Desktop High at 2x: 1.5 -> 1.25 -> 1 -> the render scale, then nothing (the auto ladder
    // would have gone to MSAA before the render scale).
    let q = tierQuality("high", 2);
    q = degradeQuality(q, 2, { keepLook: true })!;
    q = degradeQuality(q, 2, { keepLook: true })!;
    expect(q.maxDpr).toBe(1);
    expect(degradeQuality(q, 2)).toMatchObject({ msaa: 0 });
    q = degradeQuality(q, 2, { keepLook: true })!;
    expect(q).toMatchObject({ maxDpr: RENDER_SCALE_MIN, msaa: 2, bloom: true, maxFps: 0 });
    expect(degradeQuality(q, 2, { keepLook: true })).toBeNull();
    // Desktop Medium (1x, no MSAA) has only the render scale.
    expect(degradeQuality(tierQuality("mid", 1), 1, { keepLook: true })).toMatchObject({ maxDpr: RENDER_SCALE_MIN, bloom: true });
    // Its frame budget: under 25 fps, not under 50.
    expect(CHOICE_FRAME_BUDGET_MS).toBe(40);
    expect(framesOverBudget(Array(30).fill(30), CHOICE_FRAME_BUDGET_MS)).toBe(false);
    expect(framesOverBudget(Array(30).fill(45), CHOICE_FRAME_BUDGET_MS)).toBe(true);
  });
});

describe("the visitor's quality pick", () => {
  const storage = (value: string | null) => {
    const data = new Map<string, string>(value === null ? [] : [[TIER_KEY, value]]);
    return {
      getItem: (k: string) => data.get(k) ?? null,
      setItem: (k: string, v: string) => void data.set(k, v),
      data,
    };
  };
  const throwing = {
    getItem: (): string | null => {
      throw new Error("SecurityError");
    },
    setItem: () => {
      throw new Error("QuotaExceededError");
    },
  };

  it("reads a stored pick, and nothing from junk, no storage or blocked storage", () => {
    for (const t of ["low", "mid", "high"] as const) expect(readTierChoice(storage(t))).toBe(t);
    for (const junk of ["", "ultra", "HIGH", "medium", " mid", "null"]) expect(readTierChoice(storage(junk)), junk).toBeNull();
    expect(readTierChoice(storage(null))).toBeNull();
    expect(readTierChoice(null)).toBeNull();
    expect(readTierChoice(throwing)).toBeNull();
  });

  it("writes the pick under its key, and survives blocked storage", () => {
    const s = storage(null);
    expect(writeTierChoice(s, "high")).toBe(true);
    expect(s.data.get(TIER_KEY)).toBe("high");
    expect(readTierChoice(s)).toBe("high");
    expect(TIER_KEY).toBe("sect.quality");
    expect(() => writeTierChoice(throwing, "low")).not.toThrow();
    expect(writeTierChoice(throwing, "low")).toBe(false);
    expect(writeTierChoice(null, "low")).toBe(false);
  });

  it("?tier= beats the stored pick, which beats the probe", () => {
    expect(resolveTier({ recommended: "mid", stored: "low", forced: "high" })).toEqual({ tier: "high", source: "link" });
    expect(resolveTier({ recommended: "mid", stored: "low", forced: null })).toEqual({ tier: "low", source: "choice" });
    expect(resolveTier({ recommended: "mid", stored: null, forced: null })).toEqual({ tier: "mid", source: "auto" });
    // A pick equal to the probe's is still the visitor's own; a link never is.
    expect(resolveTier({ recommended: "mid", stored: "mid", forced: null }).source).toBe("choice");
    expect(resolveTier({ recommended: "mid", stored: null, forced: "mid" }).source).toBe("link");
  });

  it("applies desktop Medium and High live; every other change restarts the load", () => {
    expect(tierChange("mid", "high", 1, false)).toBe("live");
    expect(tierChange("high", "mid", 1.5, false)).toBe("live");
    for (const [a, b] of [
      ["low", "mid"],
      ["mid", "low"],
      ["low", "high"],
      ["high", "low"],
    ] as const) {
      expect(tierChange(a, b, 1, false), `${a} -> ${b}`).toBe("restart");
    }
    // Touch screens: Low and Medium differ in postprocessing, Medium and High in the texture set.
    for (const [a, b] of [
      ["low", "mid"],
      ["mid", "high"],
      ["low", "high"],
      ["high", "mid"],
    ] as const) {
      expect(tierChange(a, b, 3, true), `touch ${a} -> ${b}`).toBe("restart");
    }
    for (const t of TIER_ORDER) expect(tierChange(t, t, 2, true)).toBe("none");
  });

  it("names the tiers in plain English, lowest first", () => {
    expect(TIER_ORDER).toEqual(["low", "mid", "high"]);
    expect(TIER_ORDER.map((t) => TIER_LABELS[t])).toEqual(["Low", "Medium", "High"]);
  });
});

describe("meshoptWorkerCount", () => {
  it("uses half the cores, between 1 and 4", () => {
    expect(meshoptWorkerCount(16)).toBe(4);
    expect(meshoptWorkerCount(6)).toBe(3);
    expect(meshoptWorkerCount(2)).toBe(1);
    expect(meshoptWorkerCount(1)).toBe(1);
    expect(meshoptWorkerCount(undefined)).toBe(1);
  });
});

describe("isGzip", () => {
  it("recognises the gzip magic number", () => {
    expect(isGzip(new Uint8Array([0x1f, 0x8b, 8, 0]))).toBe(true);
    expect(isGzip(new Uint8Array([0x67, 0x6c, 0x54, 0x46]))).toBe(false);
    expect(isGzip(new Uint8Array([]))).toBe(false);
  });
});

describe("combinedProgress", () => {
  it("weights by bytes once all totals are known", () => {
    expect(
      combinedProgress([
        { loaded: 50, total: 100, done: false },
        { loaded: 300, total: 300, done: true },
      ]),
    ).toBeCloseTo(350 / 400);
  });

  it("falls back to per-file fractions when a total is unknown", () => {
    expect(
      combinedProgress([
        { loaded: 10, total: 0, done: false },
        { loaded: 0, total: 0, done: true },
      ]),
    ).toBeCloseTo(0.5);
  });
});

describe("pick", () => {
  it("hits a box in front of the ray and misses one beside it", () => {
    expect(rayBox([0, 0, 10], [0, 0, -1], [0, 0, 0], [2, 2, 2])).toBeCloseTo(9);
    expect(rayBox([5, 0, 10], [0, 0, -1], [0, 0, 0], [2, 2, 2])).toBeNull();
    expect(rayBox([0, 0, -10], [0, 0, -1], [0, 0, 0], [2, 2, 2])).toBeNull();
    expect(rayBox([0, 0, 0], [0, 0, -1], [0, 0, 0], [2, 2, 2])).toBe(0);
  });

  it("lists every box on the ray, nearest first", () => {
    const boxes = [
      { id: "far", center: [0, 0, -100] as [number, number, number], size: [5, 5, 5] as [number, number, number] },
      { id: "near", center: [0, 0, 0] as [number, number, number], size: [2, 2, 2] as [number, number, number] },
    ];
    expect(boxHits([0, 0, 30], [0, 0, -1], boxes).map((h) => h.id)).toEqual(["near", "far"]);
    expect(boxHits([0, 0, 30], [0, 0, -1], boxes, 50).map((h) => h.id)).toEqual(["near"]);
    // Where the ray enters and leaves each box.
    expect(boxHits([0, 0, 30], [0, 0, -1], boxes).map((h) => [h.distance, h.exit])).toEqual([
      [29, 31],
      [127.5, 132.5],
    ]);
    expect(rayBoxSpan([0, 0, 0], [0, 0, -1], [0, 0, 0], [2, 2, 2])).toEqual([0, 1]);
  });

  it("before a precise test is available, a box wins only over exact hits beyond its far side", () => {
    const hall = { id: "forge", distance: 20, exit: 60 };
    // An artifact inside the hall's box keeps its pick; one behind the hall does not.
    expect(pickWithBoxes({ id: "project:a", distance: 35 }, hall)?.id).toBe("project:a");
    expect(pickWithBoxes({ id: "project:b", distance: 80 }, hall)?.id).toBe("forge");
    expect(pickWithBoxes(null, hall)?.id).toBe("forge");
    expect(pickWithBoxes({ id: "project:a", distance: 35 }, null)?.id).toBe("project:a");
    expect(pickWithBoxes(null, null)).toBeNull();
  });

  it("never lets a box the camera is inside stand in for its hotspot", () => {
    // Flying through the gate's box before its BVH exists: every ray enters it at 0.
    const gate = { id: "gate", distance: 0, exit: 12 };
    expect(canStandIn(gate)).toBe(false);
    expect(canStandIn({ id: "forge", distance: 20, exit: 60 })).toBe(true);
    expect(pickWithBoxes(null, gate)).toBeNull();
    expect(pickWithBoxes({ id: "project:a", distance: 40 }, gate)?.id).toBe("project:a");
  });

  it("gives a hit on the pagoda's wall to the lit floor (school) at that height", () => {
    type V = [number, number, number];
    // The real boxes from meta.json (library pagoda and its three lit floors).
    const library = { id: "library", center: [132.13, 186.84, -768.63] as V, size: [26.1, 44.6, 26.1] as V };
    const items = [
      { id: "school:2", center: [132.13, 174.2, -768.63] as V, size: [14.5, 2.67, 14.5] as V },
      { id: "school:1", center: [132.13, 185.26, -768.63] as V, size: [12.3, 2.78, 12.3] as V },
      { id: "school:0", center: [132.13, 196.31, -768.63] as V, size: [10.1, 2.89, 10.1] as V },
      // Not a contained kind: ignored even when it sits inside the landmark.
      { id: "project:x", center: [132.13, 185.26, -768.63] as V, size: [2, 2, 2] as V },
    ];
    // A hit on the outer wall 8 m from the axis, 2.5 m above the middle floor's lit core.
    expect(containedItemAt([140.1, 187.8, -768.63], library, items)).toBe("school:1");
    expect(containedItemAt([132.13, 171.0, -762.0], library, items)).toBe("school:2");
    expect(containedItemAt([132.13, 199.5, -774.0], library, items)).toBe("school:0");
    // The pagoda's spire and its base stay the pavilion.
    expect(containedItemAt([132.13, 206.0, -768.63], library, items)).toBeNull();
    expect(containedItemAt([132.13, 166.0, -768.63], library, items)).toBeNull();
    // Items outside the landmark's box never count.
    const elsewhere = { id: "school:9", center: [0, 0, 0] as V, size: [1, 1, 1] as V };
    expect(containedItemAt([0, 0, 0], library, [elsewhere])).toBeNull();
  });
});

describe("noise", () => {
  it("tiles seamlessly", () => {
    const period = 4;
    for (const y of [0.3, 1.7, 3.2]) {
      expect(valueNoise(0, y, period, 3)).toBeCloseTo(valueNoise(period, y, period, 3), 12);
      expect(valueNoise(y, 0, period, 3)).toBeCloseTo(valueNoise(y, period, period, 3), 12);
    }
  });

  it("fills the full byte range", () => {
    const t = tilingNoise(32, { octaves: 3 });
    expect(t.length).toBe(32 * 32);
    expect(Math.min(...t)).toBe(0);
    expect(Math.max(...t)).toBe(255);
  });

  it("wraps across texture edges smoothly", () => {
    const n = 64;
    const t = tilingNoise(n, { basePeriod: 4, octaves: 2 });
    let edge = 0;
    let inner = 0;
    for (let j = 0; j < n; j++) {
      edge += Math.abs(t[j * n] - t[j * n + n - 1]);
      inner += Math.abs(t[j * n + 31] - t[j * n + 32]);
    }
    expect(edge).toBeLessThan(inner * 3 + 64);
  });
});

describe("glsl helpers", () => {
  it("converts sRGB hex to linear", () => {
    expect(hexToLinear("#ffffff")).toEqual([1, 1, 1]);
    expect(hexToLinear("#000000")).toEqual([0, 0, 0]);
    expect(hexToLinear("#808080")[0]).toBeCloseTo(0.2158, 3);
  });

  it("writes valid float literals", () => {
    expect(glslFloat(2)).toBe("2.0");
    expect(glslFloat(-60)).toBe("-60.0");
    expect(glslFloat(0.0003)).toContain(".");
  });

  it("haze matches Blender's veil at area height (about 21% at 600 m)", () => {
    const c = fogConstantsFromMeta(parseMeta({}));
    const v600 = hazeVeil(c, 50, 0, 600);
    expect(v600).toBeGreaterThan(0.15);
    expect(v600).toBeLessThan(0.25);
    expect(hazeVeil(c, 50, 0, 1500)).toBeGreaterThan(v600);
    // looking up thins the haze
    expect(hazeVeil(c, 50, 0.5, 600)).toBeLessThan(v600);
    // a steep ray down a long way saturates instead of overflowing
    expect(hazeVeil(c, 50, -1, 1e6)).toBeLessThanOrEqual(1);
  });

  it("fog chunks declare what three's fog uniforms need", () => {
    const ch = fogChunks(fogConstantsFromMeta(parseMeta({})));
    expect(ch.fog_pars_fragment).toContain("uniform vec3 fogColor");
    expect(ch.fog_pars_fragment).toContain("uniform float fogDensity");
    expect(ch.fog_vertex).toContain("vFogWorldPos");
    expect(ch.fog_fragment).toContain("gl_FragColor.rgb");
  });
});

describe("content", () => {
  it("uses the portfolio name and tagline on the gate panel", () => {
    const p = holdPanels();
    expect(p.gate.title).toBe(PORTFOLIO.name);
    expect(p.gate.body).toContain(PORTFOLIO.tagline);
    expect(p.mirror.body.join(" ")).toMatch(/hackathon/);
  });

  it("falls back to the label for unknown hotspots", () => {
    expect(hotspotCard("unknown", "Thing")).toEqual({ title: "Thing", zh: undefined, body: "" });
    expect(hotspotCard("gate", "Mountain Gate").body.length).toBeGreaterThan(0);
  });

  it("groups hotspots by area prefix", () => {
    expect(hotspotArea("mirror-pond")).toBe("mirror");
    expect(hotspotArea("gate")).toBe("gate");
  });
});

describe("pathCellKey", () => {
  const path: [number, number, number][] = [
    [0, 50, 0],
    [0, 50, -100],
  ];
  const key = pathCellKey(path);

  it("uses small cells near the path and large ones far away", () => {
    expect(key(10, 0, -50).startsWith("150:")).toBe(true);
    expect(key(500, 0, -50).startsWith("450:")).toBe(true);
    expect(key(3000, 0, 0).startsWith("1800:")).toBe(true);
  });

  it("ignores height", () => {
    expect(key(10, -500, -50)).toBe(key(10, 500, -50));
  });

  it("measures distance on the ground plane", () => {
    expect(distanceToPath2D(path, 3, -100)).toBe(3);
    // Distance to the nearest sample point (paths are sampled densely, about 1-3 m apart).
    expect(distanceToPath2D(path, 0, -40)).toBe(40);
  });
});
