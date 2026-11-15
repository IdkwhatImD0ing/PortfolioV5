import { describe, expect, it } from "vitest";
import { hexToLinear } from "./glsl";
import {
  choosePageLook,
  FIXED_LEVERS,
  isRuntimeLever,
  JOURNEY,
  JOURNEY_LOOKS,
  JOURNEY_ON,
  journeyApply,
  journeyKeys,
  journeyLevers,
  journeyPatch,
  journeyTable,
  journeyWeights,
  normalMix,
  RUNTIME_LEVERS,
  setLevers,
  weightsText,
  type JourneyBases,
} from "./journey";
import { LIVE_LOOK } from "./live";
import { SECT_LOOK } from "./look";
import { FRAME_LOOK, frameGradeLinear, LOOK_IDS, LOOK_TARGETS, LOOKS, leverProblems, readLever, withLevers, type LookTarget } from "./looks";
import { LUX } from "./lux";
import { ATMOS } from "./post";
import { hazeScaleAt, RANGE_HAZE_HOLDS, RANGE_LOOK } from "./range-look";
import { parseSectParams } from "./runtime";
import type { Vec3 } from "./types";

const META = { sun: { color: "#ffbf84" }, moon: { color: "#f3f6ff" }, vignette: 0.22 };
const BASES: JourneyBases = { sect: SECT_LOOK, live: LIVE_LOOK, lux: LUX, atmos: ATMOS, range: RANGE_LOOK, frame: FRAME_LOOK, meta: META };
const TABLE = journeyTable(BASES);

/** The stops' hold frames (camera.json), as the brief lists them. */
const HOLDS = [
  ["gate", 93],
  ["mirror", 217],
  ["forge", 352],
  ["arena", 516],
  ["mission", 619],
  ["library", 772],
  ["steles", 974],
  ["scroll", 1103],
  ["formation", 1208],
  ["abode", 1380],
  ["summit", 1647],
].map(([id, frame]) => ({ id: id as string, label: id as string, frame: frame as number }));

describe("journey: the arc", () => {
  it("is on by default, and runs from sunrise at the gate to the moon at the summit", () => {
    expect(JOURNEY_ON).toBe(true);
    expect(JOURNEY.map((k) => k.stop)).toEqual(HOLDS.map((h) => h.id));
    expect(JOURNEY.map((k) => k.frame)).toEqual(HOLDS.map((h) => h.frame));
    expect(journeyWeights(93).gold).toBe(1);
    expect(journeyWeights(1647).moon).toBe(1);
    // Every stop's mix names known looks with positive shares.
    for (const k of JOURNEY) {
      for (const [id, v] of Object.entries(k.mix)) {
        expect(JOURNEY_LOOKS).toContain(id);
        expect(v).toBeGreaterThan(0);
      }
    }
  });

  it("holds the first stop's look before it and the last stop's after it", () => {
    expect(journeyWeights(0)).toEqual(normalMix({ gold: 1 }));
    expect(journeyWeights(-50)).toEqual(normalMix({ gold: 1 }));
    expect(journeyWeights(1700)).toEqual(normalMix({ moon: 1 }));
    expect(journeyWeights(99999)).toEqual(normalMix({ moon: 1 }));
  });

  it("is exactly each stop's mix at its frame", () => {
    for (const k of JOURNEY) expect(journeyWeights(k.frame), k.stop).toEqual(normalMix(k.mix));
    const near = (w: Record<string, number>, want: Record<string, number>) => {
      for (const id of JOURNEY_LOOKS) expect(w[id], id).toBeCloseTo(want[id] ?? 0, 12);
    };
    near(journeyWeights(217), { gold: 0.5, day: 0.35, ink: 0.15 });
    near(journeyWeights(352), { day: 0.85, ink: 0.15 });
    near(journeyWeights(619), { day: 0.9, gold: 0.1 });
    near(journeyWeights(1208), { dusk: 0.7, moon: 0.3 });
    near(journeyWeights(1380), { dusk: 0.4, moon: 0.6 });
  });

  it("keeps the day moving: forge, arena and mission are all clear day, and no two in a row are the same", () => {
    const day = ["forge", "arena", "mission"].map((id) => normalMix(JOURNEY.find((k) => k.stop === id)?.mix ?? {}));
    for (const w of day) expect(w.day).toBeGreaterThanOrEqual(0.75);
    expect(day[0]).not.toEqual(day[1]);
    expect(day[1]).not.toEqual(day[2]);
    // Late morning keeps a little of the mirror's mist, never more of it.
    const mirror = normalMix(JOURNEY.find((k) => k.stop === "mirror")?.mix ?? {});
    expect(day[0].ink).toBeLessThanOrEqual(mirror.ink);
  });

  it("never goes back an hour in the evening: from the steles on, gold only falls and the moon only rises", () => {
    let prev = journeyWeights(974);
    for (let f = 975; f <= 1700; f++) {
      const w = journeyWeights(f);
      expect(w.gold, `gold at ${f}`).toBeLessThanOrEqual(prev.gold + 1e-12);
      expect(w.moon, `moon at ${f}`).toBeGreaterThanOrEqual(prev.moon - 1e-12);
      prev = w;
    }
    // The formation is past the sunset: some moon, no gold.
    expect(journeyWeights(1208).gold).toBe(0);
    expect(journeyWeights(1208).moon).toBeGreaterThan(0);
  });

  it("weights sum to 1 and each look moves one way between two neighbouring stops", () => {
    for (let i = 1; i < JOURNEY.length; i++) {
      const a = JOURNEY[i - 1].frame;
      const b = JOURNEY[i].frame;
      let prev = journeyWeights(a);
      const dir = Object.fromEntries(JOURNEY_LOOKS.map((id) => [id, Math.sign(normalMix(JOURNEY[i].mix)[id] - normalMix(JOURNEY[i - 1].mix)[id])]));
      for (let s = 1; s <= 40; s++) {
        const w = journeyWeights(a + ((b - a) * s) / 40);
        const sum = JOURNEY_LOOKS.reduce((t, id) => t + w[id], 0);
        expect(sum).toBeCloseTo(1, 12);
        for (const id of JOURNEY_LOOKS) {
          const d = w[id] - prev[id];
          expect(d * dir[id], `${JOURNEY[i - 1].stop}-${JOURNEY[i].stop} ${id}`).toBeGreaterThanOrEqual(-1e-12);
          if (dir[id] === 0) expect(Math.abs(d)).toBeLessThan(1e-12);
        }
        prev = w;
      }
    }
  });

  it("eases in and out at each stop (the look rests where the visitor stops)", () => {
    const near = journeyWeights(93 + 2);
    expect(near.gold).toBeGreaterThan(0.995);
    const mid = journeyWeights((93 + 217) / 2);
    expect(mid.gold).toBeCloseTo((1 + normalMix(JOURNEY[1].mix).gold) / 2, 9);
  });

  it("takes the camera's own hold frames, in frame order", () => {
    const moved = HOLDS.map((h) => (h.id === "forge" ? { ...h, frame: 400 } : h));
    const keys = journeyKeys(moved);
    expect(keys.find((k) => k.stop === "forge")?.frame).toBe(400);
    expect(journeyWeights(400, keys)).toEqual(normalMix(JOURNEY.find((k) => k.stop === "forge")?.mix ?? {}));
    // A stop the camera lacks keeps the table's frame.
    expect(journeyKeys([]).map((k) => k.frame)).toEqual(JOURNEY.map((k) => k.frame));
    // Out of order holds still come back sorted.
    const swapped = journeyKeys([{ id: "gate", frame: 2000 }]);
    expect(swapped[swapped.length - 1].stop).toBe("gate");
  });

  it("says what it shows", () => {
    expect(weightsText(journeyWeights(93))).toBe("gold");
    expect(weightsText(journeyWeights(1103))).toBe("gold 50% / dusk 50%");
  });
});

describe("journey: only run-time levers move", () => {
  it("every lever a look sets is either moved by the journey or listed as left at today's value", () => {
    for (const id of LOOK_IDS) {
      for (const t of LOOK_TARGETS) {
        for (const path of Object.keys(LOOKS[id].patch[t] ?? {})) {
          const fixed = FIXED_LEVERS[t]?.includes(path) ?? false;
          expect(isRuntimeLever(t, path) || fixed, `${id} ${t} ${path}`).toBe(true);
          expect(isRuntimeLever(t, path) && fixed, `${t} ${path} in both lists`).toBe(false);
        }
      }
    }
  });

  it("every run-time lever is a real lever of its table", () => {
    for (const t of LOOK_TARGETS) {
      for (const path of RUNTIME_LEVERS[t]) expect(readLever(BASES[t], path), `${t} ${path}`).toBeDefined();
    }
  });

  it("the blended patch holds run-time levers only, and every one of them, at every frame", () => {
    for (let f = 0; f <= 1700; f += 37) {
      const p = journeyPatch(TABLE, journeyWeights(f));
      for (const t of LOOK_TARGETS) {
        expect(Object.keys(p[t]).sort(), `${t} at ${f}`).toEqual([...RUNTIME_LEVERS[t]].sort());
        for (const path of Object.keys(p[t])) expect(isRuntimeLever(t as LookTarget, path)).toBe(true);
        if (t !== "meta") expect(leverProblems(BASES[t], p[t]), `${t} at ${f}`).toEqual([]);
      }
    }
  });
});

describe("journey: blending the looks", () => {
  it("at a stop with one look, every lever is that look's own value (today's where it sets none)", () => {
    const gate = journeyPatch(TABLE, journeyWeights(93));
    expect(gate.sect["sky.zenith"]).toBe(LOOKS.gold.patch.sect?.["sky.zenith"]);
    expect(gate.frame["grade.exposure"]).toBe(LOOKS.gold.patch.frame?.["grade.exposure"]);
    expect(gate.sect["grade.greenTame"]).toBe(SECT_LOOK.grade.greenTame);
    expect(gate.range["haze.holds.gate"]).toBe(LOOKS.gold.patch.range?.["haze.holds.gate"]);
    expect(gate.meta["sun.color"]).toBe(LOOKS.gold.patch.meta?.["sun.color"]);
    const summit = journeyPatch(TABLE, journeyWeights(1647));
    expect(summit.frame.stars).toBe(1);
    expect(summit.frame.skySun).toBe(0);
    expect(summit.sect["twilight.zenith"]).toBe(LOOKS.moon.patch.sect?.["twilight.zenith"]);
  });

  it("today's dusk alone is exactly today's page", () => {
    const p = journeyPatch(TABLE, normalMix({ dusk: 1 }));
    for (const t of LOOK_TARGETS) for (const [path, v] of Object.entries(p[t])) expect(v, `${t} ${path}`).toEqual(readLever(BASES[t], path));
    expect(p.frame["grade.amount"]).toBe(0);
    expect(p.frame.stars).toBe(0);
  });

  it("rolls the day's highlights off sooner (the marble paving) and leaves the other looks' shoulder at today's", () => {
    expect(journeyPatch(TABLE, journeyWeights(516)).sect["grade.shoulder"]).toBe(LOOKS.day.patch.sect?.["grade.shoulder"]);
    expect(LOOKS.day.patch.sect?.["grade.shoulder"]).toBeLessThan(SECT_LOOK.grade.shoulder);
    expect(journeyPatch(TABLE, journeyWeights(93)).sect["grade.shoulder"]).toBe(SECT_LOOK.grade.shoulder);
    expect(journeyPatch(TABLE, journeyWeights(1647)).sect["grade.shoulder"]).toBe(SECT_LOOK.grade.shoulder);
  });

  it("blends numbers linearly and colours in linear light", () => {
    const w = journeyWeights(772);
    const p = journeyPatch(TABLE, w);
    const day = LOOKS.day.patch.sect?.["grade.exposure"] as number;
    const gold = LOOKS.gold.patch.sect?.["grade.exposure"] as number;
    expect(p.sect["grade.exposure"]).toBeCloseTo((day + gold) / 2, 12);
    const a = hexToLinear(LOOKS.day.patch.sect?.["sky.horizon"] as string);
    const b = hexToLinear(LOOKS.gold.patch.sect?.["sky.horizon"] as string);
    const got = hexToLinear(p.sect["sky.horizon"] as string);
    for (let i = 0; i < 3; i++) expect(got[i]).toBeCloseTo((a[i] + b[i]) / 2, 2);
  });

  it("fades the frame grade in by its amount alone, between dusk and a graded look", () => {
    const p = journeyLevers(TABLE, "frame", journeyWeights(1103));
    expect(p["grade.amount"]).toBeCloseTo(0.5, 12);
    expect(p["grade.exposure"]).toBe(LOOKS.gold.patch.frame?.["grade.exposure"]);
    const abode = journeyLevers(TABLE, "frame", journeyWeights(1380));
    expect(abode["grade.balance"]).toBe(LOOKS.moon.patch.frame?.["grade.balance"]);
  });

  it("grades the frame continuously through today's dusk: no jump in the glows next to a stop that is dusk alone", () => {
    // The arc has no such stop now; an arc with one shows the frame grade fades out with its amount.
    const arc = [
      { stop: "a", frame: 100, mix: { gold: 0.5, dusk: 0.5 } },
      { stop: "b", frame: 200, mix: { dusk: 1 } },
      { stop: "c", frame: 300, mix: { dusk: 0.5, moon: 0.5 } },
    ];
    const bright: Vec3 = [2.4, 1.6, 0.6];
    const marble: Vec3 = [0.95, 0.9, 0.85];
    for (const f of [199, 201, 202]) {
      const g = withLevers(FRAME_LOOK, journeyLevers(TABLE, "frame", journeyWeights(f, arc))).grade;
      expect(g.amount, `${f}`).toBeLessThan(0.01);
      for (const c of [bright, marble]) frameGradeLinear(c, g).forEach((v, i) => expect(Math.abs(v - c[i]), `${f} ${c}`).toBeLessThan(0.01 * Math.max(c[i], 1)));
    }
  });

  it("brings the stars out late: the moon's share cubed, a fifth at the abode's blue hour", () => {
    expect(journeyLevers(TABLE, "frame", journeyWeights(1380)).stars).toBeCloseTo(0.6 ** 3, 12);
    expect(journeyLevers(TABLE, "frame", journeyWeights(1208)).stars).toBeCloseTo(0.3 ** 3, 12);
    expect(journeyLevers(TABLE, "frame", journeyWeights(1103)).stars).toBe(0);
  });

  it("scales the haze per stop as a whole: hazeScaleAt with the blended holds is today's times the looks' factor", () => {
    const holds = journeyLevers(TABLE, "range", journeyWeights(772));
    const look = { ...RANGE_LOOK, haze: { ...RANGE_LOOK.haze, holds: { ...RANGE_LOOK.haze.holds } } };
    setLevers(look, holds);
    const k = (0.85 + 1.45) / 2;
    for (const f of [700, 772, 850]) expect(hazeScaleAt(f, HOLDS, look)).toBeCloseTo(hazeScaleAt(f, HOLDS) * k, 1);
    expect(look.haze.holds.library).toBeCloseTo(RANGE_HAZE_HOLDS.library * k, 1);
  });

  it("never writes into the tables it blends from", () => {
    const before = JSON.stringify(Object.values(BASES));
    for (let f = 0; f <= 1700; f += 50) journeyPatch(TABLE, journeyWeights(f));
    expect(JSON.stringify(Object.values(BASES))).toBe(before);
  });

  it("journeyApply writes exactly what journeyPatch and setLevers write, frame after frame on the same copies", () => {
    const viaPatch = structuredClone(BASES) as Record<LookTarget, object>;
    const viaApply = structuredClone(BASES) as Record<LookTarget, object>;
    const keys = journeyKeys(HOLDS);
    const frames: number[] = [];
    for (let f = -20; f <= 1720; f += 3.7) frames.push(f);
    // Each stop's own frame and just either side (one look alone, the gate's plateau), and back down the arc.
    for (const h of HOLDS) frames.push(h.frame, h.frame - 0.01, h.frame + 0.01);
    for (let f = 1700; f >= 0; f -= 41.3) frames.push(f);
    for (const f of frames) {
      const w = journeyWeights(f, keys);
      const p = journeyPatch(TABLE, w);
      for (const t of LOOK_TARGETS) setLevers(viaPatch[t], p[t]);
      journeyApply(TABLE, w, viaApply);
      expect(viaApply, `frame ${f}`).toEqual(viaPatch);
    }
    // Each look alone, today's dusk alone, and an even mix of all five.
    for (const mix of [...JOURNEY_LOOKS.map((id) => ({ [id]: 1 })), { gold: 1, day: 1, ink: 1, moon: 1, dusk: 1 }]) {
      const w = normalMix(mix);
      const p = journeyPatch(TABLE, w);
      for (const t of LOOK_TARGETS) setLevers(viaPatch[t], p[t]);
      journeyApply(TABLE, w, viaApply);
      expect(viaApply, JSON.stringify(mix)).toEqual(viaPatch);
    }
  });

  it("journeyApply writes into the copies only, a list into the list already there", () => {
    const before = JSON.stringify(Object.values(BASES));
    const into = structuredClone(BASES) as Record<LookTarget, object>;
    const list = (into.sect as typeof SECT_LOOK).haze.extinction;
    for (let f = 0; f <= 1700; f += 50) journeyApply(TABLE, journeyWeights(f), into);
    expect(JSON.stringify(Object.values(BASES))).toBe(before);
    expect((into.sect as typeof SECT_LOOK).haze.extinction).toBe(list);
    expect((into.sect as typeof SECT_LOOK).haze.extinction).toEqual(journeyPatch(TABLE, journeyWeights(1700)).sect["haze.extinction"]);
  });

  it("setLevers writes paths in place, copying lists", () => {
    const o = { a: { b: 1, c: [1, 2, 3] } };
    const list = [4, 5, 6];
    setLevers(o, { "a.b": 2, "a.c": list });
    expect(o.a.b).toBe(2);
    expect(o.a.c).toEqual([4, 5, 6]);
    expect(o.a.c).not.toBe(list);
  });
});

describe("journey: which look the page shows", () => {
  it("shows the journey by default, in production too", () => {
    expect(choosePageLook({})).toEqual({ kind: "journey" });
    for (const q of ["", "?look=moon", "?look=dusk", "?look=journey", "?time=21:00", "?frame=93&ui=0"]) {
      expect(choosePageLook(parseSectParams(q, false)), q).toEqual({ kind: "journey" });
    }
  });

  it("with the flag off it is today's dusk (or the clock when that flag is on)", () => {
    expect(choosePageLook({}, false)).toBeNull();
    expect(choosePageLook({}, false, true)).toEqual({ kind: "clock", options: {} });
  });

  it("lets development force a look, the clock, today's dusk or the journey", () => {
    expect(choosePageLook(parseSectParams("?look=gold", true))).toEqual({ kind: "look", id: "gold" });
    expect(choosePageLook(parseSectParams("?time=12:00", true))).toEqual({ kind: "clock", options: { time: 720 } });
    expect(choosePageLook(parseSectParams("?look=auto", true))).toEqual({ kind: "clock", options: {} });
    expect(choosePageLook(parseSectParams("?look=dusk", true))).toBeNull();
    expect(choosePageLook(parseSectParams("?look=journey", true), false)).toEqual({ kind: "journey" });
    expect(parseSectParams("?look=dusk", true).journey).toBe(false);
    expect(parseSectParams("?look=journey", true).journey).toBe(true);
    expect("journey" in parseSectParams("?look=journey", false)).toBe(false);
    expect("journey" in parseSectParams("?look=gold", true)).toBe(false);
  });
});
