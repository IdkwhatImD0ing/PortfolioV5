import { describe, expect, it } from "vitest";
import {
  FLIGHT_SCROLL,
  buildScrollMap,
  easeInOut,
  easeInOutInverse,
  frameToU,
  holdPresence,
  introPresence,
  nearestStop,
  nextTrackViewport,
  pxPerUnit,
  scrollToU,
  uToFrame,
  uToScroll,
} from "./scroll-map";

const HOLDS = [
  { id: "gate", label: "Mountain Gate", frame: 93 },
  { id: "mirror", label: "Heart-Mirror Terrace", frame: 217 },
];

describe("buildScrollMap", () => {
  const map = buildScrollMap(27, 288, HOLDS, { dwellUnits: 40, ease: 0.6 });

  it("adds one unit per frame plus a dwell per hold", () => {
    expect(map.totalUnits).toBe(288 - 27 + 2 * 40);
    expect(map.segments.map((s) => s.kind)).toEqual(["move", "hold", "move", "hold", "move"]);
  });

  it("starts on startFrame and ends on frameEnd", () => {
    expect(uToFrame(map, 0)).toBe(27);
    expect(uToFrame(map, map.totalUnits)).toBe(288);
    expect(uToFrame(map, -10)).toBe(27);
    expect(uToFrame(map, 1e6)).toBe(288);
  });

  it("holds the camera still across each dwell zone", () => {
    const gate = map.holds[0];
    expect(uToFrame(map, gate.u0)).toBe(93);
    expect(uToFrame(map, gate.uMid)).toBe(93);
    expect(uToFrame(map, gate.u1)).toBe(93);
    expect(uToFrame(map, map.holds[1].uMid)).toBe(217);
  });

  it("is monotonic", () => {
    let prev = -Infinity;
    for (let u = 0; u <= map.totalUnits; u += 0.5) {
      const f = uToFrame(map, u);
      expect(f).toBeGreaterThanOrEqual(prev - 1e-9);
      prev = f;
    }
  });

  it("slows the camera near holds (eased)", () => {
    const gate = map.holds[0];
    const nearHold = uToFrame(map, gate.u0) - uToFrame(map, gate.u0 - 1);
    const midway = uToFrame(map, gate.u0 / 2 + 0.5) - uToFrame(map, gate.u0 / 2 - 0.5);
    expect(nearHold).toBeLessThan(midway);
  });

  it("frameToU inverts uToFrame on moving segments", () => {
    for (const f of [27, 40.5, 92, 150, 216.9, 250, 288]) {
      expect(uToFrame(map, frameToU(map, f))).toBeCloseTo(f, 6);
    }
  });

  it("maps a hold frame to the middle of its dwell", () => {
    expect(frameToU(map, 93)).toBe(map.holds[0].uMid);
    expect(frameToU(map, 217)).toBe(map.holds[1].uMid);
  });

  it("clamps frames before the start to scroll 0", () => {
    expect(frameToU(map, 5)).toBe(0);
  });

  it("ignores holds outside the range", () => {
    const m = buildScrollMap(100, 200, HOLDS);
    expect(m.holds.map((h) => h.id)).toEqual([]);
    expect(m.totalUnits).toBe(100);
  });

  it("lists reduced-motion stops: start, holds, end", () => {
    expect(map.stops.map((s) => s.id)).toEqual(["start", "gate", "mirror", "end"]);
    expect(nearestStop(map, 1).frame).toBe(27);
    expect(nearestStop(map, map.holds[0].uMid + 3).frame).toBe(93);
    expect(nearestStop(map, map.totalUnits).frame).toBe(288);
  });
});

describe("presence", () => {
  const map = buildScrollMap(27, 288, HOLDS, { dwellUnits: 40 });

  it("is 1 inside a dwell and fades outside", () => {
    const gate = map.holds[0];
    const at = (u: number) => holdPresence(map, u, 14).find((p) => p.id === "gate")!.amount;
    expect(at(gate.uMid)).toBe(1);
    expect(at(gate.u0 - 7)).toBeGreaterThan(0);
    expect(at(gate.u0 - 7)).toBeLessThan(1);
    expect(at(gate.u0 - 20)).toBe(0);
  });

  it("can keep the last hold's panel up to the end of the track", () => {
    const last = map.holds[map.holds.length - 1];
    const at = (u: number, tail: boolean) => holdPresence(map, u, 14, tail).find((p) => p.id === last.id)!.amount;
    expect(map.totalUnits).toBeGreaterThan(last.u1 + 20);
    expect(at(map.totalUnits, false)).toBe(0);
    expect(at(map.totalUnits, true)).toBe(1);
    // The other holds are unchanged.
    const gate = (tail: boolean) => holdPresence(map, map.holds[0].u1 + 20, 14, tail).find((p) => p.id === "gate")!.amount;
    expect(gate(true)).toBe(gate(false));
  });

  it("intro fades out after the first units", () => {
    expect(introPresence(0)).toBe(1);
    expect(introPresence(20)).toBe(0);
  });
});

describe("easing", () => {
  it("easeInOutInverse undoes easeInOut", () => {
    for (const t of [0, 0.1, 0.5, 0.77, 1]) {
      expect(easeInOutInverse(easeInOut(t, 0.6), 0.6)).toBeCloseTo(t, 9);
    }
  });
});

describe("pixel mapping", () => {
  it("converts scroll pixels to units and back", () => {
    expect(scrollToU(500, 1000, 340)).toBe(170);
    expect(uToScroll(170, 1000, 340)).toBe(500);
    expect(scrollToU(10, 0, 340)).toBe(0);
  });

  it("scales pixels per unit with the viewport", () => {
    expect(pxPerUnit(720)).toBe(12);
    expect(pxPerUnit(200)).toBe(8);
    expect(pxPerUnit(4000)).toBe(18);
  });
});

describe("frameToU edge cases", () => {
  it("maps a hold on the start or end frame to the middle of its dwell zone", () => {
    const map = buildScrollMap(10, 50, [
      { id: "a", label: "A", frame: 10 },
      { id: "b", label: "B", frame: 50 },
    ]);
    expect(frameToU(map, 10)).toBe(map.holds[0].uMid);
    expect(frameToU(map, 50)).toBe(map.holds[1].uMid);
    expect(frameToU(map, 5)).toBe(0);
    expect(frameToU(map, Number.NaN)).toBe(0);
  });
});

describe("nextTrackViewport", () => {
  const cur = { width: 390, height: 700 };

  it("ignores the phone address bar showing and hiding", () => {
    expect(nextTrackViewport(cur, 390, 756)).toEqual({ viewport: cur, resize: false });
    expect(nextTrackViewport(cur, 390, 640)).toEqual({ viewport: cur, resize: false });
  });

  it("follows rotation, window resizes and big height changes", () => {
    expect(nextTrackViewport(cur, 844, 390).resize).toBe(true);
    expect(nextTrackViewport(cur, 390, 500)).toEqual({ viewport: { width: 390, height: 500 }, resize: true });
  });
});

describe("the full flight's scroll map (eleven holds)", () => {
  const holds = [
    ["gate", 93],
    ["mirror", 217],
    ["forge", 389],
    ["arena", 516],
    ["mission", 619],
    ["library", 818],
    ["steles", 967],
    ["scroll", 1103],
    ["formation", 1277],
    ["abode", 1449],
    ["summit", 1647],
  ].map(([id, frame]) => ({ id: id as string, label: id as string, frame: frame as number }));
  const map = buildScrollMap(27, 1729, holds, FLIGHT_SCROLL);

  it("keeps the first test's pace: one unit per frame plus the same dwell at every hold", () => {
    expect(map.totalUnits).toBe(1729 - 27 + 11 * FLIGHT_SCROLL.dwellUnits);
    expect(map.holds.map((h) => h.id)).toEqual(holds.map((h) => h.id));
    for (const z of map.holds) expect(z.u1 - z.u0).toBe(FLIGHT_SCROLL.dwellUnits);
    // About 36 screens on a 720 px viewport.
    const screens = (map.totalUnits * pxPerUnit(720)) / 720;
    expect(screens).toBeGreaterThan(30);
    expect(screens).toBeLessThan(42);
  });

  it("stops at every hold frame and maps each back to the middle of its dwell", () => {
    for (const z of map.holds) {
      expect(uToFrame(map, z.u0 + 1)).toBe(z.frame);
      expect(uToFrame(map, z.u1 - 1)).toBe(z.frame);
      expect(frameToU(map, z.frame)).toBe(z.uMid);
    }
  });

  it("is monotonic over the whole flight", () => {
    let prev = -Infinity;
    for (let u = 0; u <= map.totalUnits; u += 3) {
      const f = uToFrame(map, u);
      expect(f).toBeGreaterThanOrEqual(prev);
      prev = f;
    }
    expect(uToFrame(map, map.totalUnits)).toBe(1729);
  });

  it("shows one panel at a time", () => {
    for (const z of map.holds) {
      const lit = holdPresence(map, z.uMid, 16).filter((p) => p.amount > 0);
      expect(lit.map((p) => p.id)).toEqual([z.id]);
    }
  });

  it("gives reduced motion thirteen stops: start, eleven holds, end", () => {
    expect(map.stops.length).toBe(13);
    expect(nearestStop(map, frameToU(map, 600)).id).toBe("mission");
  });
});
