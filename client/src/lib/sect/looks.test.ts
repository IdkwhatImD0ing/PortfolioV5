import { describe, expect, it } from "vitest";
import { glslFloat, hexToLinear } from "./glsl";
import { LIVE_LOOK } from "./live";
import { gradeLinear, SECT_LOOK } from "./look";
import {
  FRAME_LOOK,
  frameCurve,
  frameGradeGlsl,
  frameGradeLinear,
  leverProblems,
  LOOK_IDS,
  LOOK_TARGETS,
  LOOKS,
  parseLookParam,
  readLever,
  redWeight,
  starsGlsl,
  warmKept,
  warmWeight,
  withLevers,
  writeLevers,
  type FrameGrade,
  type LookTarget,
} from "./looks";
import { LUX } from "./lux";
import { parseMeta } from "./parse";
import { ATMOS } from "./post";
import { RANGE_HAZE_HOLDS, RANGE_LOOK } from "./range-look";
import { parseSectParams } from "./runtime";
import type { Vec3 } from "./types";

const META = parseMeta({ moon: { position: [0, 1000, -6000], radius: 600 }, waterfalls: [], hotspots: [] });

const TABLES: Record<LookTarget, object> = {
  sect: SECT_LOOK,
  live: LIVE_LOOK,
  lux: LUX,
  atmos: ATMOS,
  range: RANGE_LOOK,
  frame: FRAME_LOOK,
  meta: META,
};

const luma = (c: Vec3) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
const grade = (id: keyof typeof LOOKS): FrameGrade => withLevers(FRAME_LOOK, LOOKS[id].patch.frame).grade;

describe("looks: the switch", () => {
  it("parses the ids, and nothing else", () => {
    expect(LOOK_IDS).toEqual(["gold", "moon", "ink", "day"]);
    for (const id of LOOK_IDS) expect(parseLookParam(id)).toBe(id);
    expect(parseLookParam(" MOON ")).toBe("moon");
    expect(parseLookParam("today")).toBeNull();
    expect(parseLookParam("neon")).toBeNull();
    expect(parseLookParam("")).toBeNull();
    expect(parseLookParam(null)).toBeNull();
  });

  it("is a URL option in development only, absent when not given", () => {
    expect(parseSectParams("?frame=93&look=gold", true).look).toBe("gold");
    expect(parseSectParams("?look=ink", true).look).toBe("ink");
    expect(parseSectParams("?look=gold", false).look).toBeUndefined();
    expect(parseSectParams("?look=neon", true).look).toBeUndefined();
    expect("look" in parseSectParams("?frame=93", true)).toBe(false);
  });

  it("every look has its own id and an entry for each id", () => {
    expect(Object.keys(LOOKS).sort()).toEqual([...LOOK_IDS].sort());
    for (const id of LOOK_IDS) expect(LOOKS[id].id).toBe(id);
  });
});

describe("looks: the default is today's page", () => {
  it("the frame levers are all off", () => {
    expect(FRAME_LOOK.grade.amount).toBe(0);
    expect(FRAME_LOOK.stars).toBe(0);
    expect(FRAME_LOOK.skySun).toBe(1);
    // The cloud sea's shade colour the page used before it was a lever (scene.tsx Atmosphere).
    expect(FRAME_LOOK.cloudSeaShade).toBe("#8f93ad");
  });

  it("the default grade leaves every colour as it is, glows included", () => {
    for (const c of [[0, 0, 0], [0.02, 0.05, 0.1], [0.18, 0.18, 0.18], [0.6, 0.1, 0.05], [0.9, 0.95, 1], [3, 1.2, 0.3]] as Vec3[]) {
      const out = frameGradeLinear(c, FRAME_LOOK.grade);
      out.forEach((v, i) => expect(v).toBeCloseTo(c[i], 6));
    }
  });

  it("building the looks writes nothing into the tables", () => {
    const before = JSON.stringify([SECT_LOOK, LIVE_LOOK, LUX, ATMOS, RANGE_LOOK, FRAME_LOOK]);
    for (const id of LOOK_IDS) for (const t of LOOK_TARGETS) withLevers(TABLES[t], LOOKS[id].patch[t]);
    expect(JSON.stringify([SECT_LOOK, LIVE_LOOK, LUX, ATMOS, RANGE_LOOK, FRAME_LOOK])).toBe(before);
  });

  it("no overrides gives back the very same object", () => {
    expect(withLevers(META, undefined)).toBe(META);
    expect(withLevers(SECT_LOOK, {})).toBe(SECT_LOOK);
  });
});

describe("looks: the overrides", () => {
  it("every override names a real lever of the right kind", () => {
    for (const id of LOOK_IDS) {
      for (const t of LOOK_TARGETS) {
        const levers = LOOKS[id].patch[t];
        if (levers) expect(leverProblems(TABLES[t], levers), `${id} ${t}`).toEqual([]);
      }
    }
  });

  it("each look grades the whole frame and repaints the sky and the haze", () => {
    for (const id of LOOK_IDS) {
      const p = LOOKS[id].patch;
      expect(p.frame?.["grade.amount"]).toBe(1);
      for (const k of ["sky.zenith", "sky.horizon", "haze.color", "grade.exposure", "puffs.lit"]) expect(p.sect?.[k], `${id} ${k}`).toBeDefined();
      expect(p.sect?.["haze.color"]).not.toBe(SECT_LOOK.haze.color);
    }
    // And they are not one look: their haze differs.
    expect(new Set(LOOK_IDS.map((id) => LOOKS[id].patch.sect?.["haze.color"])).size).toBe(LOOK_IDS.length);
  });

  it("the haze per stop is scaled from the page's own numbers, which no look writes", () => {
    expect(Object.isFrozen(RANGE_HAZE_HOLDS)).toBe(true);
    expect(RANGE_LOOK.haze.holds).not.toBe(RANGE_HAZE_HOLDS);
    expect(RANGE_LOOK.haze.holds).toEqual(RANGE_HAZE_HOLDS);
    expect(LOOKS.gold.patch.range?.["haze.holds.gate"]).toBe(Math.round(RANGE_HAZE_HOLDS.gate * 1.45 * 100) / 100);
    // Writing a look into a copy of the table leaves the numbers the looks are made from alone.
    const t = structuredClone(RANGE_LOOK);
    writeLevers(t, LOOKS.gold.patch.range ?? {});
    writeLevers(t, LOOKS.gold.patch.range ?? {});
    expect(t.haze.holds.gate).toBe(LOOKS.gold.patch.range?.["haze.holds.gate"]);
    expect(RANGE_HAZE_HOLDS.gate).toBe(1.6);
  });

  it("reads a lever's value, and nothing that is not one", () => {
    expect(readLever(SECT_LOOK, "sky.zenith")).toBe(SECT_LOOK.sky.zenith);
    expect(readLever(SECT_LOOK, "haze.extinction")).toEqual(SECT_LOOK.haze.extinction);
    expect(readLever(SECT_LOOK, "sky")).toBeUndefined();
    expect(readLever(SECT_LOOK, "sky.nope")).toBeUndefined();
    expect(readLever(FRAME_LOOK, "grade.amount")).toBe(0);
  });

  it("finds the problems: an unknown lever, a wrong kind, a group, a short vector", () => {
    expect(leverProblems(SECT_LOOK, { "sky.nope": "#000000" })).toEqual(["sky.nope: no such lever"]);
    expect(leverProblems(SECT_LOOK, { "nope.zenith": "#000000" })).toEqual(["nope.zenith: no such lever"]);
    expect(leverProblems(SECT_LOOK, { "sky.zenith": 3 })).toEqual(["sky.zenith: wants a string"]);
    expect(leverProblems(SECT_LOOK, { "sky.zenith": "blue" })).toEqual(["sky.zenith: wants a #rrggbb colour"]);
    expect(leverProblems(SECT_LOOK, { "sky.gradeMix": "#ffffff" })).toEqual(["sky.gradeMix: wants a number"]);
    expect(leverProblems(SECT_LOOK, { "sky.gradeMix": Number.NaN })).toEqual(["sky.gradeMix: wants a number"]);
    expect(leverProblems(SECT_LOOK, { sky: 1 })).toEqual(["sky: not a lever (a group, not a value)"]);
    expect(leverProblems(SECT_LOOK, { "haze.extinction": [1, 1] })).toEqual(["haze.extinction: wants 3 numbers"]);
  });

  it("writes in place, and refuses a bad set whole", () => {
    const t = structuredClone(SECT_LOOK);
    writeLevers(t, { "sky.zenith": "#010203", "haze.extinction": [1, 2, 3], "mist.density": 0.5 });
    expect(t.sky.zenith).toBe("#010203");
    expect(t.haze.extinction).toEqual([1, 2, 3]);
    expect(t.mist.density).toBe(0.5);
    const u = structuredClone(SECT_LOOK);
    expect(() => writeLevers(u, { "sky.zenith": "#010203", "sky.nope": 1 })).toThrow(/sky\.nope/);
    expect(u.sky.zenith).toBe(SECT_LOOK.sky.zenith);
  });

  it("a copy with overrides leaves the original alone", () => {
    const m = withLevers(META, LOOKS.moon.patch.meta);
    expect(m.sun.color).toBe(LOOKS.moon.patch.meta?.["sun.color"]);
    expect(m.vignette).toBe(LOOKS.moon.patch.meta?.vignette);
    expect(META.sun.color).not.toBe(m.sun.color);
    expect(META.vignette).toBe(0.22);
  });
});

describe("looks: the frame grade", () => {
  it("the S-curve keeps its ends and its pivot, and steepens through it", () => {
    expect(frameCurve(0, 0.45, 1.3)).toBe(0);
    expect(frameCurve(1, 0.45, 1.3)).toBe(1);
    expect(frameCurve(0.45, 0.45, 1.3)).toBeCloseTo(0.45, 9);
    expect(frameCurve(0.3, 0.45, 1.3)).toBeLessThan(0.3);
    expect(frameCurve(0.7, 0.45, 1.3)).toBeGreaterThan(0.7);
    expect(frameCurve(0.3, 0.45, 1)).toBeCloseTo(0.3, 9);
  });

  it("knows lacquer red from orange stone", () => {
    expect(redWeight([0.6, 0.05, 0.03])).toBe(1);
    expect(redWeight([0.6, 0.4, 0.25])).toBe(0);
    expect(redWeight([0.3, 0.3, 0.3])).toBe(0);
  });

  it("gold: the lights warm, the shade leans teal", () => {
    const g = grade("gold");
    const lit = frameGradeLinear([0.7, 0.7, 0.7], g);
    const shade = frameGradeLinear([0.08, 0.08, 0.08], g);
    expect(lit[0]).toBeGreaterThan(lit[2] * 1.1);
    expect(shade[2]).toBeGreaterThan(shade[0]);
  });

  it("gold: sunlit orange stone is not pushed toward neon (it reads as red-led, so red-led colour gets no extra saturation)", () => {
    expect(LOOKS.gold.patch.frame?.["grade.redSaturation"]).toBeLessThanOrEqual(1);
    const sat = (c: Vec3) => (Math.max(...c) - Math.min(...c)) / Math.max(...c);
    const stone: Vec3 = [0.8, 0.3, 0.08];
    expect(redWeight(stone)).toBeGreaterThan(0.5);
    const g = grade("gold");
    const hot = frameGradeLinear(stone, { ...g, redSaturation: 1.1 });
    expect(sat(frameGradeLinear(stone, g))).toBeLessThan(sat(hot));
  });

  it("day: the baked surfaces' highlights roll off sooner than today's, and the mid tones are the same", () => {
    const day = withLevers(SECT_LOOK, LOOKS.day.patch.sect).grade;
    expect(day.shoulder).toBeLessThan(SECT_LOOK.grade.shoulder);
    const atToday = { ...day, shoulder: SECT_LOOK.grade.shoulder };
    // White marble in the sun: still near white, but off the clip.
    const marble = gradeLinear([0.85, 0.83, 0.8], day);
    expect(Math.max(...marble)).toBeLessThan(Math.max(...gradeLinear([0.85, 0.83, 0.8], atToday)));
    expect(luma(marble)).toBeGreaterThan(0.85);
    // A mid tone sits under both shoulders.
    gradeLinear([0.08, 0.07, 0.06], day).forEach((v, i) => expect(v).toBeCloseTo(gradeLinear([0.08, 0.07, 0.06], atToday)[i], 12));
  });

  it("moon: darker and blue, with the darks kept off black and the glows warm and brighter", () => {
    const g = grade("moon");
    const stone = frameGradeLinear([0.5, 0.45, 0.4], g);
    expect(luma(stone)).toBeLessThan(luma([0.5, 0.45, 0.4]));
    expect(stone[2]).toBeGreaterThan(stone[0]);
    expect(luma(frameGradeLinear([0, 0, 0], g))).toBeGreaterThan(0);
    const lantern: Vec3 = [3, 1.2, 0.3];
    const lit = frameGradeLinear(lantern, g);
    expect(lit[0] / lit[2]).toBeCloseTo(lantern[0] / lantern[2], 6);
    expect(lit[0]).toBeGreaterThan(lantern[0]);
  });

  it("moon: lantern light on stone stays amber and grey stone goes cool (the night re-bake)", () => {
    const g = grade("moon");
    const rb = (c: Vec3) => c[0] / Math.max(c[2], 1e-6);
    // An amber texel as the abode's bake holds its lantern light: amber after the grade, and as bright.
    const amber: Vec3 = [0.6, 0.33, 0.12];
    const lit = frameGradeLinear(amber, g);
    expect(rb(lit)).toBeGreaterThan(1.6);
    expect(lit[0]).toBeGreaterThan(lit[1]);
    expect(lit[1]).toBeGreaterThan(lit[2]);
    expect(luma(lit)).toBeGreaterThan(luma(amber) * 0.9);
    // Under the lantern and the cool key at once the abode's stair wall is salmon (red leads blue by
    // three quarters, hue 0.17): it comes out amber, not pink.
    const salmon: Vec3 = [0.3, 0.111, 0.072];
    const wall = frameGradeLinear(salmon, g);
    expect(rb(wall)).toBeGreaterThan(rb(salmon));
    expect(wall[1]).toBeGreaterThan(wall[2] * 1.4);
    // Without the warm keep the same grade turns amber beige: the lever is what keeps it.
    expect(rb(frameGradeLinear(amber, { ...g, warmKeep: 0 }))).toBeLessThan(1.6);
    // Grey stone, the bake's ochre-stained rock and grass are graded blue as before.
    for (const c of [[0.3, 0.3, 0.3], [0.08, 0.08, 0.08], [0.3, 0.27, 0.2], [0.1, 0.16, 0.04]] as Vec3[]) {
      expect(warmWeight(c), `${c}`).toBe(0);
      const out = frameGradeLinear(c, g);
      expect(out[2], `${c}`).toBeGreaterThan(out[0]);
      out.forEach((v, i) => expect(v, `${c}`).toBeCloseTo(frameGradeLinear(c, { ...g, warmKeep: 0 })[i], 9));
    }
    // Pink blossom and lacquer red keep their blue (only amber's is cut).
    expect(warmKept([0.6, 0.12, 0.22], 0.5)).toEqual([0.6, 0.12, 0.22]);
    expect(warmKept([0.5, 0.05, 0.05], 0.5)[2]).toBeCloseTo(0.05, 9);
    expect(warmKept(amber, 0.5)[2]).toBeCloseTo(0.06, 9);
    // The night sky is not touched.
    const sky: Vec3 = [0.004, 0.006, 0.03];
    frameGradeLinear(sky, g).forEach((v, i) => expect(v).toBeCloseTo(frameGradeLinear(sky, { ...g, warmKeep: 0 })[i], 12));
    // Lantern bodies still glow as before: the glow skips the grade whatever the warm keep.
    const lantern: Vec3 = [3, 1.2, 0.3];
    frameGradeLinear(lantern, g).forEach((v, i) => expect(v).toBeCloseTo(lantern[i] * g.glowGain, 6));
  });

  it("only the moon keeps warm light: the other looks and today's dusk grade it as before", () => {
    expect(FRAME_LOOK.grade.warmKeep).toBe(0);
    expect(FRAME_LOOK.grade.warmBlue).toBe(1);
    for (const id of ["gold", "day", "ink"] as const) expect(grade(id).warmKeep, id).toBe(0);
    expect(grade("moon").warmKeep).toBeGreaterThan(0);
    // And the GLSL carries the numbers.
    const s = frameGradeGlsl(grade("moon"));
    expect(s).toContain("vec4 sectFrameWarm( vec3 c, float keep, float blue )");
    expect(s).toContain(`sectFrameWarm( x0, ${glslFloat(grade("moon").warmKeep)}, ${glslFloat(grade("moon").warmBlue)} )`);
  });

  it("day: no stars, the sun in the sky, a blue sky paler at the horizon, greens kept", () => {
    const f = withLevers(FRAME_LOOK, LOOKS.day.patch.frame);
    expect(f.stars).toBe(0);
    expect(f.skySun).toBe(1);
    const s = withLevers(SECT_LOOK, LOOKS.day.patch.sect);
    const zenith = hexToLinear(s.sky.zenith);
    const horizon = hexToLinear(s.sky.horizon);
    expect(zenith[2]).toBeGreaterThan(zenith[0] * 2);
    expect(luma(horizon)).toBeGreaterThan(luma(zenith));
    // Not an orange horizon: blue at least level with red there.
    expect(horizon[2]).toBeGreaterThanOrEqual(horizon[0]);
    expect(s.grade.greenTame).toBeLessThan(SECT_LOOK.grade.greenTame);
    // The frame grade cools: the bake's warm stone (a dusk-lit grey) comes out near neutral.
    const g = frameGradeLinear([0.22, 0.2, 0.16], f.grade);
    expect(g[2] / g[0]).toBeGreaterThan(0.85);
    expect(g[2] / g[0]).toBeLessThan(1.2);
  });

  it("ink: greens go grey, lacquer red stays red", () => {
    const g = grade("ink");
    const sat = (c: Vec3) => (Math.max(...c) - Math.min(...c)) / Math.max(...c);
    const leaf: Vec3 = [0.12, 0.25, 0.08];
    const red: Vec3 = [0.5, 0.04, 0.03];
    expect(sat(frameGradeLinear(leaf, g))).toBeLessThan(sat(leaf) * 0.5);
    expect(sat(frameGradeLinear(red, g))).toBeGreaterThan(0.8);
  });

  it("the GLSL carries the grade's numbers", () => {
    const g = grade("gold");
    const s = frameGradeGlsl(g);
    expect(s).toContain("vec3 sectFrameGrade( vec3 c0 )");
    expect(s).toContain("float sectFrameCurve(");
    expect(s).toContain(`* ${g.exposure}`);
    expect(frameGradeGlsl(FRAME_LOOK.grade)).toContain("mix( x0, c, 0.0 )");
  });

  it("stars: a function of the direction, scaled by the amount", () => {
    const s = starsGlsl(0.8);
    expect(s).toContain("float sectStars( vec3 d )");
    expect(s).toContain("* 0.8");
    expect(s).toContain("sectHash12");
  });
});
