import { describe, expect, it } from "vitest";
import {
  blendLevers,
  blendPatches,
  blendValue,
  chooseLook,
  clockText,
  DAY_SCHEDULE,
  dayMix,
  dayPatch,
  FOLLOW_PACIFIC_CLOCK,
  linearToHex,
  mixText,
  pacificDay,
  pacificMinutes,
  pacificOffset,
  pacificParts,
  sunTimes,
  type DayKey,
  type DayLookKey,
} from "./day-look";
import { glslFloat, hexToLinear } from "./glsl";
import { LIVE_LOOK } from "./live";
import { SECT_LOOK } from "./look";
import { FRAME_LOOK, frameGradeGlsl, frameGradeLinear, leverProblems, LOOK_IDS, LOOKS, starsGlsl, withLevers, type LookTarget } from "./looks";
import { LUX } from "./lux";
import { ATMOS } from "./post";
import { RANGE_LOOK } from "./range-look";
import { parseDateParam, parseSectParams, parseTimeParam } from "./runtime";
import type { Vec3 } from "./types";

const BASES: Record<Exclude<LookTarget, "meta">, object> = {
  sect: SECT_LOOK,
  live: LIVE_LOOK,
  lux: LUX,
  atmos: ATMOS,
  range: RANGE_LOOK,
  frame: FRAME_LOOK,
};

const hm = (s: string) => {
  const [h, m] = s.split(":").map(Number);
  return h * 60 + m;
};

describe("day look: the Pacific clock", () => {
  it("reads minutes since midnight in Pacific time, winter and summer", () => {
    expect(pacificMinutes(new Date("2026-11-13T20:30:00Z"))).toBe(hm("12:30"));
    expect(pacificMinutes(new Date("2026-07-04T19:15:30Z"))).toBeCloseTo(hm("12:15") + 0.5, 6);
    expect(pacificOffset(new Date("2026-01-15T12:00:00Z"))).toBe(-480);
    expect(pacificOffset(new Date("2026-07-15T12:00:00Z"))).toBe(-420);
  });

  it("is right across the clock changes (8 March and 1 November 2026)", () => {
    // Spring forward: 01:59 PST, then 03:00 PDT.
    expect(pacificMinutes(new Date("2026-03-08T09:59:00Z"))).toBe(hm("01:59"));
    expect(pacificMinutes(new Date("2026-03-08T10:00:00Z"))).toBe(hm("03:00"));
    // Fall back: 01:59 PDT, then 01:00 PST.
    expect(pacificMinutes(new Date("2026-11-01T08:59:00Z"))).toBe(hm("01:59"));
    expect(pacificMinutes(new Date("2026-11-01T09:00:00Z"))).toBe(hm("01:00"));
  });

  it("knows the skipped hour in March and the repeated hour in November", () => {
    // 8 March: 02:00 to 02:59 never happens; the offset goes from -480 to -420 at 10:00 UTC.
    expect(pacificOffset(new Date("2026-03-08T09:59:00Z"))).toBe(-480);
    expect(pacificOffset(new Date("2026-03-08T10:00:00Z"))).toBe(-420);
    expect(pacificParts(new Date("2026-03-08T19:00:00Z"))).toMatchObject({ day: 8, minutes: hm("12:00") });
    // 1 November: 01:30 happens twice, an hour apart in UTC.
    expect(pacificMinutes(new Date("2026-11-01T08:30:00Z"))).toBe(hm("01:30"));
    expect(pacificMinutes(new Date("2026-11-01T09:30:00Z"))).toBe(hm("01:30"));
    expect(pacificOffset(new Date("2026-11-01T08:59:00Z"))).toBe(-420);
    expect(pacificOffset(new Date("2026-11-01T09:00:00Z"))).toBe(-480);
    expect(pacificParts(new Date("2026-11-01T20:00:00Z"))).toMatchObject({ day: 1, minutes: hm("12:00") });
  });

  it("gives the Pacific date, not the UTC one", () => {
    expect(pacificParts(new Date("2026-11-14T07:59:00Z"))).toMatchObject({ year: 2026, month: 11, day: 13, minutes: hm("23:59") });
    expect(pacificParts(new Date("2026-11-14T08:00:00Z"))).toMatchObject({ year: 2026, month: 11, day: 14, minutes: 0 });
  });
});

describe("day look: sunrise and sunset on the Bay", () => {
  // Published times for San Francisco, a few km from the spot: within 10 minutes.
  const known: [string, string, string][] = [
    ["2026-11-13", "06:47", "16:59"],
    ["2026-06-21", "05:48", "20:35"],
    ["2026-12-21", "07:21", "16:54"],
    ["2026-03-20", "07:12", "19:20"],
    ["2026-09-22", "06:59", "19:08"],
  ];
  for (const [date, rise, set] of known) {
    it(`${date}: about ${rise} and ${set}`, () => {
      const [year, month, day] = date.split("-").map(Number);
      const s = sunTimes({ year, month, day });
      expect(Math.abs(s.sunrise - hm(rise))).toBeLessThan(10);
      expect(Math.abs(s.sunset - hm(set))).toBeLessThan(10);
    });
  }

  // A second check, against a different method: the US Naval Observatory's "Almanac for Computers"
  // sunrise algorithm at the same spot (37.6, -122.2), worked out apart from this code. Within 3 minutes.
  const usno: [string, number, number][] = [
    ["2026-03-07", 391.9, 1088.4],
    ["2026-03-08", 450.5, 1149.4],
    ["2026-03-20", 432.6, 1160.6],
    ["2026-06-21", 347.6, 1233.5],
    ["2026-09-22", 416.4, 1145.9],
    ["2026-10-31", 452.7, 1091.6],
    ["2026-11-01", 393.8, 1030.5],
    ["2026-11-13", 406.4, 1019.4],
    ["2026-12-21", 440.0, 1013.9],
  ];
  for (const [date, rise, set] of usno) {
    it(`${date}: matches a second method within 3 minutes`, () => {
      const [year, month, day] = date.split("-").map(Number);
      const s = sunTimes({ year, month, day });
      expect(Math.abs(s.sunrise - rise)).toBeLessThan(3);
      expect(Math.abs(s.sunset - set)).toBeLessThan(3);
    });
  }

  it("moves an hour on the clock when the clocks change", () => {
    const step = (a: [number, number, number], b: [number, number, number]) => {
      const x = sunTimes({ year: a[0], month: a[1], day: a[2] });
      const y = sunTimes({ year: b[0], month: b[1], day: b[2] });
      return [y.sunrise - x.sunrise, y.sunset - x.sunset];
    };
    // Spring forward: about an hour later on the clock (less a minute or so of real change).
    for (const d of step([2026, 3, 7], [2026, 3, 8])) expect(Math.abs(d - 60)).toBeLessThan(3);
    // Fall back: about an hour earlier.
    for (const d of step([2026, 10, 31], [2026, 11, 1])) expect(Math.abs(d + 60)).toBeLessThan(3);
  });

  it("summer evenings stay light, winter ones go dark early", () => {
    const june = sunTimes({ year: 2026, month: 6, day: 21 });
    const dec = sunTimes({ year: 2026, month: 12, day: 21 });
    expect(june.sunset - dec.sunset).toBeGreaterThan(200);
    expect(june.sunset - june.sunrise).toBeGreaterThan(14 * 60);
    expect(dec.sunset - dec.sunrise).toBeLessThan(10 * 60);
  });
});

describe("day look: the schedule", () => {
  const R = hm("06:47");
  const S = hm("16:59");
  const at = (t: string) => dayMix(hm(t), R, S);

  it("holds moon at night, ink after dawn, day by day, gold before sunset, dusk just after", () => {
    expect(at("00:00")).toEqual({ from: "moon", to: "moon", weight: 0 });
    expect(at("21:00")).toEqual({ from: "moon", to: "moon", weight: 0 });
    expect(at("07:30")).toEqual({ from: "ink", to: "ink", weight: 0 });
    expect(at("12:30")).toEqual({ from: "day", to: "day", weight: 0 });
    expect(at("16:15")).toEqual({ from: "gold", to: "gold", weight: 0 });
    expect(at("17:05")).toEqual({ from: "dusk", to: "dusk", weight: 0 });
  });

  it("blends linearly between neighbours", () => {
    // Moon to ink from R-60 to R+15.
    const m = dayMix(R - 60 + 30, R, S);
    expect(m.from).toBe("moon");
    expect(m.to).toBe("ink");
    expect(m.weight).toBeCloseTo(30 / 75, 9);
    // Dusk to moon from S+30 to S+75.
    const n = dayMix(S + 52.5, R, S);
    expect([n.from, n.to]).toEqual(["dusk", "moon"]);
    expect(n.weight).toBeCloseTo(0.5, 9);
    // Day to gold, gold to dusk.
    expect(dayMix(S - 90, R, S)).toMatchObject({ from: "day", to: "gold" });
    expect(dayMix(S - 5, R, S)).toMatchObject({ from: "gold", to: "dusk" });
    expect(dayMix(S - 5, R, S).weight).toBeCloseTo(10 / 15, 9);
  });

  it("reaches each point exactly, and runs on smoothly through midnight", () => {
    for (const k of DAY_SCHEDULE) {
      const t = (k.from === "R" ? R : S) + k.at;
      const m = dayMix(t, R, S);
      expect(m.weight).toBe(0);
      expect(m.from).toBe(k.look);
    }
    expect(dayMix(1439.9, R, S)).toEqual(dayMix(-0.1, R, S));
    expect(dayMix(1440 + 60, R, S)).toEqual(dayMix(60, R, S));
  });

  it("never jumps: a minute apart, the blend moves by a minute's share at most", () => {
    const amount = (m: ReturnType<typeof dayMix>, key: DayLookKey) => (m.from === key ? 1 - m.weight : 0) + (m.to === key ? m.weight : 0);
    const keys: DayLookKey[] = ["moon", "ink", "day", "gold", "dusk"];
    for (let t = 0; t < 1440; t++) {
      const a = dayMix(t, R, S);
      const b = dayMix(t + 1, R, S);
      for (const k of keys) expect(Math.abs(amount(a, k) - amount(b, k)), `${clockText(t)} ${k}`).toBeLessThanOrEqual(1 / 15 + 1e-9);
    }
  });

  it("on every day of 2026 the points come in order, a day apart, with no holding needed", () => {
    const start = Date.UTC(2026, 0, 1);
    for (let i = 0; i < 365; i++) {
      const t = new Date(start + i * 86400000);
      const s = sunTimes({ year: t.getUTCFullYear(), month: t.getUTCMonth() + 1, day: t.getUTCDate() });
      const times = DAY_SCHEDULE.map((k) => (k.from === "R" ? s.sunrise : s.sunset) + k.at);
      for (let j = 1; j < times.length; j++) expect(times[j], `${t.toISOString().slice(0, 10)} point ${j}`).toBeGreaterThan(times[j - 1]);
      expect(times[0]).toBeGreaterThan(0);
      expect(times[times.length - 1]).toBeLessThan(1440);
      expect(times[times.length - 1] - 1440).toBeLessThan(times[0]);
    }
  });

  it("the shortest and the longest day", () => {
    const at = (d: [number, number, number], t: string) => {
      const s = sunTimes({ year: d[0], month: d[1], day: d[2] });
      return dayMix(hm(t), s.sunrise, s.sunset);
    };
    const dec: [number, number, number] = [2026, 12, 21];
    const jun: [number, number, number] = [2026, 6, 21];
    // 21 December: R 07:21, S 16:54. Day from R+150 (09:51) to S-120 (14:54), night from S+75 (18:09).
    expect(at(dec, "09:45")).toMatchObject({ from: "ink", to: "day" });
    expect(at(dec, "12:00")).toEqual({ from: "day", to: "day", weight: 0 });
    expect(at(dec, "15:00")).toMatchObject({ from: "day", to: "gold" });
    expect(at(dec, "18:15")).toEqual({ from: "moon", to: "moon", weight: 0 });
    // 21 June: R 05:48, S 20:35. Day from 08:18 to 18:35, gold at 20:00, night only from 21:50.
    expect(at(jun, "08:30")).toEqual({ from: "day", to: "day", weight: 0 });
    expect(at(jun, "18:30")).toEqual({ from: "day", to: "day", weight: 0 });
    expect(at(jun, "20:00")).toEqual({ from: "gold", to: "gold", weight: 0 });
    expect(at(jun, "21:00")).toEqual({ from: "dusk", to: "dusk", weight: 0 });
    expect(at(jun, "21:30")).toMatchObject({ from: "dusk", to: "moon" });
    expect(at(jun, "22:00")).toEqual({ from: "moon", to: "moon", weight: 0 });
    expect(at(jun, "04:30")).toEqual({ from: "moon", to: "moon", weight: 0 });
    expect(at(jun, "05:00")).toMatchObject({ from: "moon", to: "ink" });
  });

  it("keeps a very short day in order", () => {
    // Sunrise 10:00, sunset 13:00: day's points would come before ink's.
    for (let t = 0; t < 1440; t += 7) {
      const m = dayMix(t, 600, 780);
      expect(m.weight).toBeGreaterThanOrEqual(0);
      expect(m.weight).toBeLessThanOrEqual(1);
    }
  });

  it("takes any schedule", () => {
    const two: DayKey[] = [
      { from: "R", at: 0, look: "day" },
      { from: "S", at: 0, look: "moon" },
    ];
    expect(dayMix(R + (S - R) / 2, R, S, two).weight).toBeCloseTo(0.5, 9);
    expect(dayMix(0, R, S, two).from).toBe("moon");
    expect(dayMix(0, R, S, [])).toEqual({ from: "dusk", to: "dusk", weight: 0 });
  });

  it("the clock and the options in its place", () => {
    const d = pacificDay(new Date("2026-11-13T20:30:00Z"));
    expect(d.date).toEqual({ year: 2026, month: 11, day: 13 });
    expect(d.minutes).toBe(hm("12:30"));
    expect(d).toMatchObject({ from: "day", to: "day", weight: 0 });
    const e = pacificDay(new Date("2026-11-13T20:30:00Z"), { time: hm("21:00"), date: { year: 2026, month: 6, day: 21 } });
    expect(e.date).toEqual({ year: 2026, month: 6, day: 21 });
    // 21:00 in June is just after sunset: dusk, not night.
    expect(e.from).toBe("dusk");
  });

  it("names the mix", () => {
    expect(mixText({ from: "day", to: "day", weight: 0 })).toBe("day");
    expect(mixText({ from: "day", to: "gold", weight: 0.56 })).toBe("day 44% / gold 56%");
    expect(clockText(hm("05:50"))).toBe("05:50");
    expect(clockText(1440)).toBe("00:00");
  });
});

describe("day look: blending two looks", () => {
  it("a weight of 0 or 1 gives that look exactly", () => {
    for (const t of Object.keys(BASES) as Exclude<LookTarget, "meta">[]) {
      expect(blendLevers(t, LOOKS.day.patch[t], LOOKS.gold.patch[t], 0, BASES[t])).toEqual(LOOKS.day.patch[t] ?? {});
      expect(blendLevers(t, LOOKS.day.patch[t], LOOKS.gold.patch[t], 1, BASES[t])).toEqual(LOOKS.gold.patch[t] ?? {});
      expect(blendLevers(t, undefined, LOOKS.moon.patch[t], 0, BASES[t])).toEqual({});
    }
  });

  it("numbers and lists linearly, colours in linear light, other strings at half-way", () => {
    expect(blendValue(1, 3, 0.25)).toBe(1.5);
    expect(blendValue([0, 1, 2], [2, 3, 4], 0.5)).toEqual([1, 2, 3]);
    const mid = blendValue("#000000", "#ffffff", 0.5) as string;
    expect(hexToLinear(mid)[0]).toBeCloseTo(0.5, 2);
    expect(mid).toBe("#bcbcbc");
    expect(blendValue("a", "b", 0.49)).toBe("a");
    expect(blendValue("a", "b", 0.5)).toBe("b");
    expect(linearToHex(hexToLinear("#3c78cc"))).toBe("#3c78cc");
  });

  it("a weight of 0 or 1 gives exactly that look for every pair the day uses, meta included", () => {
    const keys: DayLookKey[] = ["moon", "ink", "day", "gold", "dusk"];
    const strip = (p: ReturnType<typeof dayPatch>) => {
      const out: Record<string, unknown> = {};
      for (const t of Object.keys(BASES)) if (p?.[t as LookTarget]) out[t] = p[t as LookTarget];
      return out;
    };
    for (const a of keys) {
      for (const b of keys) {
        expect(blendPatches(dayPatch(a), dayPatch(b), 0, BASES), `${a} ${b} 0`).toEqual(strip(dayPatch(a)));
        expect(blendPatches(dayPatch(a), dayPatch(b), 1, BASES), `${a} ${b} 1`).toEqual(strip(dayPatch(b)));
        expect(blendLevers("meta", dayPatch(a)?.meta, dayPatch(b)?.meta, 0, {})).toEqual(dayPatch(a)?.meta ?? {});
        expect(blendLevers("meta", dayPatch(a)?.meta, dayPatch(b)?.meta, 1, {})).toEqual(dayPatch(b)?.meta ?? {});
      }
    }
    // Today's dusk at weight 0 writes nothing at all.
    expect(blendPatches(null, LOOKS.moon.patch, 0, BASES)).toEqual({});
  });

  it("colours blend channel by channel in linear light, not in sRGB", () => {
    expect(blendValue("#ff0000", "#0000ff", 0.5)).toBe("#bc00bc");
    const a = "#3c78cc";
    const b = "#ffa65e";
    for (const w of [0.2, 0.5, 0.8]) {
      const got = hexToLinear(blendValue(a, b, w) as string);
      const want = hexToLinear(a).map((x, i) => x + (hexToLinear(b)[i] - x) * w);
      for (let i = 0; i < 3; i++) expect(got[i]).toBeCloseTo(want[i], 2);
    }
  });

  it("the grade fading out toward today's dusk keeps its own numbers too", () => {
    const l = blendLevers("frame", LOOKS.gold.patch.frame, undefined, 0.5, FRAME_LOOK);
    expect(l["grade.amount"]).toBe(0.5);
    expect(l["grade.exposure"]).toBe(LOOKS.gold.patch.frame?.["grade.exposure"]);
    expect(l["grade.shadowTint"]).toBe(LOOKS.gold.patch.frame?.["grade.shadowTint"]);
  });

  it("stars are the same coming and going, and none just after dusk starts to fade", () => {
    for (const w of [0.1, 0.3, 0.5, 0.7, 0.9]) {
      const up = blendLevers("frame", undefined, LOOKS.moon.patch.frame, w, FRAME_LOOK).stars as number;
      const down = blendLevers("frame", LOOKS.moon.patch.frame, undefined, 1 - w, FRAME_LOOK).stars as number;
      expect(up).toBeCloseTo(down, 12);
      expect(up).toBeCloseTo(w ** 3, 12);
    }
    // A sliver of night: the stars' code is built, at a strength nobody can see.
    const sliver = blendLevers("frame", undefined, LOOKS.moon.patch.frame, 0.01, FRAME_LOOK);
    expect(sliver.stars as number).toBeGreaterThan(0);
    expect(sliver.stars as number).toBeLessThan(1e-5);
    expect(sliver["grade.amount"]).toBeCloseTo(0.01, 12);
  });

  it("takes today's value for a lever only one look names", () => {
    const l = blendLevers("sect", { "sky.zenith": "#000000" }, undefined, 0.5, SECT_LOOK);
    const want = hexToLinear(SECT_LOOK.sky.zenith).map((v) => v / 2) as Vec3;
    expect(hexToLinear(l["sky.zenith"] as string)[2]).toBeCloseTo(want[2], 2);
    const m = blendLevers("live", undefined, { sunGain: 2 }, 0.5, LIVE_LOOK);
    expect(m.sunGain).toBeCloseTo((LIVE_LOOK.sunGain + 2) / 2, 9);
  });

  it("a grade fading in keeps its own numbers: only the amount fades", () => {
    const l = blendLevers("frame", undefined, LOOKS.moon.patch.frame, 0.5, FRAME_LOOK);
    expect(l["grade.amount"]).toBe(0.5);
    expect(l["grade.exposure"]).toBe(LOOKS.moon.patch.frame?.["grade.exposure"]);
    expect(l["grade.balance"]).toBe(LOOKS.moon.patch.frame?.["grade.balance"]);
    // Between two graded looks the numbers blend.
    const g = blendLevers("frame", LOOKS.day.patch.frame, LOOKS.gold.patch.frame, 0.5, FRAME_LOOK);
    expect(g["grade.amount"]).toBe(1);
    expect(g["grade.exposure"]).toBeCloseTo(((LOOKS.day.patch.frame?.["grade.exposure"] as number) + 1.02) / 2, 9);
  });

  it("stars come out late: none over a sky still half dusk", () => {
    const l = blendLevers("frame", undefined, LOOKS.moon.patch.frame, 0.5, FRAME_LOOK);
    expect(l.stars).toBeCloseTo(0.125, 9);
    const m = blendLevers("frame", LOOKS.moon.patch.frame, LOOKS.ink.patch.frame, 0.5, FRAME_LOOK);
    expect(m.stars).toBeCloseTo(0.125, 9);
    expect(blendLevers("frame", LOOKS.moon.patch.frame, LOOKS.ink.patch.frame, 0.1, FRAME_LOOK).stars).toBeCloseTo(0.729, 9);
    // The day has none.
    expect(withLevers(FRAME_LOOK, LOOKS.day.patch.frame).stars).toBe(0);
  });

  it("dusk and moon at half-way: every lever fits, and the grade and stars build", () => {
    const p = blendPatches(null, LOOKS.moon.patch, 0.5, BASES);
    for (const t of Object.keys(BASES) as Exclude<LookTarget, "meta">[]) expect(leverProblems(BASES[t], p[t] ?? {}), t).toEqual([]);
    const frame = withLevers(FRAME_LOOK, p.frame);
    expect(frame.grade.amount).toBe(0.5);
    expect(frame.stars).toBeGreaterThan(0);
    expect(frame.skySun).toBeCloseTo(0.5, 9);
    const s = frameGradeGlsl(frame.grade);
    expect(s).toContain("vec3 sectFrameGrade( vec3 c0 )");
    expect(s).toContain(`mix( x0, c, ${glslFloat(0.5)} )`);
    expect(starsGlsl(frame.stars)).toContain("float sectStars( vec3 d )");
    // Half the night's darkening: a mid grey lands between today's and the moon's.
    const grey: Vec3 = [0.2, 0.2, 0.2];
    const half = frameGradeLinear(grey, frame.grade)[1];
    const night = frameGradeLinear(grey, withLevers(FRAME_LOOK, LOOKS.moon.patch.frame).grade)[1];
    expect(half).toBeLessThan(0.2);
    expect(half).toBeGreaterThan(night);
    expect(Math.abs(half - (0.2 + night) / 2)).toBeLessThan(0.01);
  });

  it("every neighbour pair of the schedule blends into levers that fit", () => {
    for (let i = 0; i < DAY_SCHEDULE.length; i++) {
      const a = DAY_SCHEDULE[i].look;
      const b = DAY_SCHEDULE[(i + 1) % DAY_SCHEDULE.length].look;
      for (const w of [0.25, 0.5, 0.75]) {
        const p = blendPatches(dayPatch(a), dayPatch(b), w, BASES);
        for (const t of Object.keys(BASES) as Exclude<LookTarget, "meta">[]) expect(leverProblems(BASES[t], p[t] ?? {}), `${a} ${b} ${w} ${t}`).toEqual([]);
      }
    }
  });

  it("the blend writes nothing into the tables", () => {
    const before = JSON.stringify(Object.values(BASES));
    for (const id of LOOK_IDS) blendPatches(LOOKS[id].patch, null, 0.5, BASES);
    expect(JSON.stringify(Object.values(BASES))).toBe(before);
  });
});

describe("day look: which look the page shows", () => {
  it("is off for visitors until the flag is turned on", () => {
    expect(FOLLOW_PACIFIC_CLOCK).toBe(false);
    expect(chooseLook({})).toBeNull();
    expect(chooseLook({}, true)).toEqual({ kind: "clock", options: {} });
  });

  it("a production build ignores every option: with the flag off it shows today's dusk", () => {
    for (const q of ["", "?look=auto", "?time=21:00", "?date=2026-06-21", "?look=moon", "?look=auto&time=03:00&date=2026-12-21", "?frame=93&ui=0"]) {
      expect(chooseLook(parseSectParams(q, false)), q).toBeNull();
      // With the flag on, production follows the clock itself, whatever the URL says.
      expect(chooseLook(parseSectParams(q, false), true), q).toEqual({ kind: "clock", options: {} });
    }
    // In development a plain URL is today's dusk too.
    expect(chooseLook(parseSectParams("?frame=93&ui=0&tier=high&live=1", true))).toBeNull();
  });

  it("a forced look wins, then the clock's options", () => {
    expect(chooseLook({ look: "gold", day: { time: 60 } }, true)).toEqual({ kind: "look", id: "gold" });
    expect(chooseLook({ day: { time: 60 } })).toEqual({ kind: "clock", options: { time: 60 } });
  });

  it("reads ?look=auto, ?time= and ?date= in development only", () => {
    expect(parseSectParams("?look=auto", true).day).toEqual({});
    expect(parseSectParams("?frame=93&time=05:50", true).day).toEqual({ time: 350 });
    expect(parseSectParams("?time=16:40&date=2026-06-21", true).day).toEqual({ time: 1000, date: { year: 2026, month: 6, day: 21 } });
    expect(parseSectParams("?look=gold&time=10:00", true)).toMatchObject({ look: "gold" });
    expect("day" in parseSectParams("?look=gold&time=10:00", true)).toBe(false);
    expect("day" in parseSectParams("?look=auto&time=10:00", false)).toBe(false);
    expect("day" in parseSectParams("?frame=93", true)).toBe(false);
    expect(parseSectParams("?look=auto", true).look).toBeUndefined();
  });

  it("checks the time and the date", () => {
    expect(parseTimeParam("00:00")).toBe(0);
    expect(parseTimeParam("5:05")).toBe(305);
    expect(parseTimeParam("23:59")).toBe(1439);
    expect(parseTimeParam("24:00")).toBeNull();
    expect(parseTimeParam("12:60")).toBeNull();
    expect(parseTimeParam("noon")).toBeNull();
    expect(parseTimeParam(null)).toBeNull();
    expect(parseDateParam("2026-11-13")).toEqual({ year: 2026, month: 11, day: 13 });
    expect(parseDateParam("2028-02-29")).toEqual({ year: 2028, month: 2, day: 29 });
    expect(parseDateParam("2026-02-29")).toBeNull();
    expect(parseDateParam("2026-13-01")).toBeNull();
    expect(parseDateParam("13/11/2026")).toBeNull();
  });
});
