import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { damp } from "./runtime";
import { buildScrollMap, FLIGHT_SCROLL, pxPerUnit } from "./scroll-map";
import { flightSeconds } from "./nav";
import { CARRY_MIN_SPEED, coastTarget, commitUnits, glideAt, glideSeconds, planCarry, planGlide, SCROLL_DAMP, SNAP, snapTarget, wheelPixels } from "./snap";

const camera = JSON.parse(readFileSync(path.resolve(__dirname, "../../../public/sect/full/camera.json"), "utf8")) as {
  startFrame: number;
  frameEnd: number;
  holds: { id: string; label: string; frame: number }[];
};
const map = buildScrollMap(camera.startFrame, camera.frameEnd, camera.holds, FLIGHT_SCROLL);
const stops = map.stops.map((s) => s.u);
const at = (id: string) => map.stops.find((s) => s.id === id)!.u;
// A 1080 px screen: 18 px a unit, so the commit distance is 60 / 18 = 3.3 units and a wheel click
// (100 px) is 5.6.
const PX = pxPerUnit(1080);
const commit = commitUnits(map.totalUnits, map.totalUnits * PX);
const click = 100 / PX;

describe("snapTarget", () => {
  const legTo = (id: string) => {
    const i = map.stops.findIndex((x) => x.id === id);
    return map.stops[i].u - map.stops[i - 1].u;
  };

  it("leaves the camera where the scrolling rests between two scenes", () => {
    const gate = at("gate");
    // One wheel click off a scene, either way: free, not flown on to the next and not pulled back.
    expect(snapTarget(stops, gate + click, gate, commit)).toBeNull();
    expect(snapTarget(stops, at("mirror") - click, at("mirror"), commit)).toBeNull();
    expect(snapTarget(stops, click, 0, commit)).toBeNull();
    // Half way along a leg, however the visitor got there.
    const mid = (at("arena") + at("mission")) / 2;
    expect(snapTarget(stops, mid, at("gate"), commit)).toBeNull();
    expect(snapTarget(stops, mid, at("scroll"), commit)).toBeNull();
    expect(snapTarget(stops, mid, mid - 20, commit)).toBeNull();
  });

  it("pulls a rest a little before a scene on to it, down or up", () => {
    const mirror = at("mirror");
    const leg = legTo("mirror");
    expect(snapTarget(stops, mirror - 0.1 * leg, at("gate"), commit)).toBe(mirror);
    expect(snapTarget(stops, mirror - SNAP.reachAhead * leg + 0.01, at("gate"), commit)).toBe(mirror);
    expect(snapTarget(stops, mirror - SNAP.reachAhead * leg - 0.5, at("gate"), commit)).toBeNull();
    // Going back up toward the gate.
    const gate = at("gate");
    expect(snapTarget(stops, gate + 0.1 * leg, mirror, commit)).toBe(gate);
    expect(snapTarget(stops, gate + 0.3 * leg, mirror, commit)).toBeNull();
    // On the longest leg the reach is capped in scroll units.
    const longest = map.stops.slice(1).reduce((best, x, i) => (x.u - map.stops[i].u > best.leg ? { u: x.u, leg: x.u - map.stops[i].u } : best), { u: 0, leg: 0 });
    expect(SNAP.reachAhead * longest.leg).toBeGreaterThan(SNAP.reachAheadMax);
    expect(snapTarget(stops, longest.u - SNAP.reachAheadMax + 1, longest.u - 100, commit)).toBe(longest.u);
    expect(snapTarget(stops, longest.u - SNAP.reachAheadMax - 1, longest.u - 100, commit)).toBeNull();
  });

  it("brings a small overshoot back, and never pulls back to the scene being left", () => {
    const arena = at("arena");
    const leg = legTo("mission");
    expect(snapTarget(stops, arena + 0.05 * leg, at("gate"), commit)).toBe(arena);
    expect(snapTarget(stops, arena + (SNAP.reachBack + 0.05) * leg, at("gate"), commit)).toBeNull();
    // Going back up, a little past the mirror toward the gate.
    const mirror = at("mirror");
    expect(snapTarget(stops, mirror - 0.05 * legTo("mirror"), at("arena"), commit)).toBe(mirror);
    // Leaving the arena by the same distance: free.
    expect(snapTarget(stops, arena + 0.05 * leg, arena, commit)).toBeNull();
    expect(snapTarget(stops, arena - 0.05 * legTo("arena"), arena, commit)).toBeNull();
  });

  it("settles a small nudge back on the stop it left, and leaves a nudge between scenes alone", () => {
    const forge = at("forge");
    const nudge = 20 / PX;
    expect(nudge).toBeLessThan(commit);
    expect(snapTarget(stops, forge + nudge, forge, commit)).toBe(forge);
    expect(snapTarget(stops, forge - nudge, forge, commit)).toBe(forge);
    const mid = (at("arena") + at("mission")) / 2;
    expect(snapTarget(stops, mid - 2, mid, commit)).toBeNull();
    expect(snapTarget(stops, mid + 2, mid, commit)).toBeNull();
  });

  it("does not count the stop a stretch began at as passed when the scroll sat a hair off it", () => {
    // The scroll rounds to a pixel, and a rest within half a unit of a stop needs no glide, so a
    // stretch can begin a little before or after the stop. One click on is still leaving it: free.
    const jade = at("scroll");
    expect(snapTarget(stops, jade - 0.007 + click, jade - 0.007, commit)).toBeNull();
    expect(snapTarget(stops, jade + 0.3 - click, jade + 0.3, commit)).toBeNull();
    // And a nudge from a hair off it settles on it.
    expect(snapTarget(stops, jade + 0.3 + 1, jade + 0.3, commit)).toBe(jade);
    // Half a unit or more before it, the scroll was not at the stop: an overshoot past it comes back.
    expect(snapTarget(stops, jade + 2, jade - 3, commit)).toBe(jade);
  });

  it("does nothing at a stop, and holds the ends", () => {
    expect(snapTarget(stops, at("gate") + 0.3, at("start"), commit)).toBeNull();
    expect(snapTarget(stops, 0, click, commit)).toBeNull();
    expect(snapTarget(stops, map.totalUnits, map.totalUnits - click, commit)).toBeNull();
    // Off the ends of a list that does not reach them: that end's stop.
    expect(snapTarget([10, 50], 2, 30, commit)).toBe(10);
    expect(snapTarget([10, 50], 70, 30, commit)).toBe(50);
    expect(snapTarget([], 5, 0, commit)).toBeNull();
  });

  it("only ever glides a short way, to a stop", () => {
    let free = 0;
    let pulled = 0;
    for (let u = 0; u <= map.totalUnits; u += 3.7) {
      for (const fromU of [0, at("arena"), map.totalUnits, u - 1, u + 40]) {
        const to = snapTarget(stops, u, fromU, commit);
        if (to === null) {
          free++;
          continue;
        }
        pulled++;
        expect(stops).toContain(to);
        expect(Math.abs(to - u)).toBeLessThanOrEqual(SNAP.reachAheadMax);
      }
    }
    // Most of the track is free; the pull is the exception.
    expect(free).toBeGreaterThan(pulled * 2);
    expect(pulled).toBeGreaterThan(0);
  });
});

describe("commitUnits", () => {
  it("is 60 px of page scroll: less than a wheel click, more than a stray touch", () => {
    expect(commit).toBeCloseTo(60 / 18, 9);
    for (const h of [600, 720, 900, 1080, 1440]) {
      const c = commitUnits(map.totalUnits, map.totalUnits * pxPerUnit(h));
      expect(c * pxPerUnit(h)).toBeCloseTo(SNAP.commitPx, 6);
      expect(c * pxPerUnit(h)).toBeLessThan(100);
    }
  });
});

describe("the glide", () => {
  it("takes about 1.2 to 1.8 s to the neighbouring stop, and never more than 2.8 s", () => {
    const legs = map.stops.slice(1).map((s, i) => s.u - map.stops[i].u);
    for (const d of legs.filter((x) => x > 100)) {
      expect(glideSeconds(d - click)).toBeGreaterThanOrEqual(1.2);
      expect(glideSeconds(d - click)).toBeLessThanOrEqual(1.8);
    }
    expect(glideSeconds(map.totalUnits)).toBe(2.8);
    expect(glideSeconds(1)).toBeLessThan(0.6);
  });

  it("starts at the camera's place and speed, and lands still on the stop", () => {
    const g = planGlide(100, 220, 40);
    const a = glideAt(g, 0);
    expect(a.u).toBeCloseTo(100, 9);
    expect(a.v).toBeCloseTo(40, 9);
    const end = glideAt(g, g.duration);
    expect(end).toEqual({ u: 220, v: 0 });
    // Soft: almost still just before the end.
    expect(Math.abs(glideAt(g, g.duration - 0.01).v)).toBeLessThan(0.5);
    expect(glideAt(g, g.duration + 5).u).toBe(220);
  });

  it("reports its own speed (the derivative of its position)", () => {
    const g = planGlide(300, 180, 25);
    for (const t of [0.05, 0.3, 0.6, 0.9]) {
      const h = 1e-5;
      const num = (glideAt(g, t + h).u - glideAt(g, t - h).u) / (2 * h);
      expect(glideAt(g, t).v).toBeCloseTo(num, 3);
    }
  });

  it("never runs past the stop when the camera already heads there fast", () => {
    for (const v0 of [0, 10, 60, 150, 400]) {
      for (const d of [1, 4, 30, 130]) {
        const g = planGlide(0, d, v0);
        let prev = 0;
        for (let t = 0; t <= g.duration; t += g.duration / 200) {
          const { u } = glideAt(g, t);
          expect(u).toBeGreaterThanOrEqual(prev - 1e-9);
          expect(u).toBeLessThanOrEqual(d + 1e-9);
          prev = u;
        }
      }
    }
    // Arriving fast shortens it.
    expect(planGlide(0, 4, 60).duration).toBeLessThan(glideSeconds(4));
  });

  it("turns round smoothly when the camera was moving away from the stop", () => {
    // An overshoot: still moving on at 30 units/s, the stop 20 units behind.
    const g = planGlide(120, 100, 30);
    expect(glideAt(g, 0).v).toBeCloseTo(30, 9);
    let far = 120;
    for (let t = 0; t <= g.duration; t += 0.01) far = Math.max(far, glideAt(g, t).u);
    // It carries on a little, then comes back.
    expect(far).toBeGreaterThan(120);
    expect(far).toBeLessThan(126);
    expect(glideAt(g, g.duration).u).toBe(100);
  });
});

describe("planCarry (a key's step begun while the camera moves)", () => {
  const mirror = at("mirror");
  const forge = at("forge");

  it("keeps the step's own ease from rest when the camera is still", () => {
    expect(planCarry(mirror, forge, 0, flightSeconds(forge - mirror))).toBeNull();
    expect(planCarry(mirror, forge, CARRY_MIN_SPEED / 2, flightSeconds(forge - mirror))).toBeNull();
    expect(planCarry(mirror, forge, -CARRY_MIN_SPEED / 2, flightSeconds(forge - mirror))).toBeNull();
    expect(planCarry(mirror, forge, 30, 0)).toBeNull();
    expect(planCarry(mirror, forge, Number.NaN, 1)).toBeNull();
  });

  it("carries the camera's place and speed on, with no jolt, and lands still on the stop", () => {
    // A glide toward the mirror, 20 units short of it, at 45 units/s: J flies on to the forge.
    const from = mirror - 20;
    const g = planCarry(from, forge, 45, flightSeconds(forge - from))!;
    expect(g).not.toBeNull();
    expect(g.duration).toBeCloseTo(flightSeconds(forge - from), 9);
    const a = glideAt(g, 0);
    expect(a.u).toBeCloseTo(from, 9);
    expect(a.v).toBeCloseTo(45, 9);
    // One frame on it has moved about as far as that speed takes it (an eased start from rest would
    // have barely moved: the stop-and-start this replaces).
    expect(glideAt(g, 1 / 60).u - from).toBeGreaterThan((45 / 60) * 0.9);
    expect(glideAt(g, g.duration)).toEqual({ u: forge, v: 0 });
    let prev = from;
    for (let t = 0; t <= g.duration; t += g.duration / 200) {
      const { u } = glideAt(g, t);
      expect(u).toBeGreaterThanOrEqual(prev - 1e-9);
      expect(u).toBeLessThanOrEqual(forge + 1e-9);
      prev = u;
    }
  });

  it("is shorter when the camera already heads there fast, so it never runs past the stop", () => {
    const g = planCarry(forge - 6, forge, 120, flightSeconds(6))!;
    expect(g.duration).toBeLessThan(flightSeconds(6));
    for (let t = 0; t <= g.duration; t += g.duration / 100) expect(glideAt(g, t).u).toBeLessThanOrEqual(forge + 1e-9);
  });

  it("turns round smoothly for a step back pressed while the camera moves on", () => {
    // Gliding down at 40 units/s past the mirror, K goes back up to it.
    const from = mirror + 10;
    const g = planCarry(from, mirror, 40, flightSeconds(10))!;
    expect(glideAt(g, 0).v).toBeCloseTo(40, 9);
    expect(g.duration).toBeCloseTo(flightSeconds(10), 9);
    expect(glideAt(g, g.duration)).toEqual({ u: mirror, v: 0 });
  });
});

describe("coastTarget", () => {
  it("keeps the damped camera at its speed when the visitor takes over", () => {
    const u = 400;
    const v = 55;
    const target = coastTarget(u, v, map.totalUnits);
    expect(SCROLL_DAMP * (target - u)).toBeCloseTo(v, 9);
    // One damped frame on, it has moved about v / 60.
    expect(damp(u, target, SCROLL_DAMP, 1 / 60) - u).toBeCloseTo(v / 60, 1);
    expect(coastTarget(2, -100, map.totalUnits)).toBe(0);
    expect(coastTarget(map.totalUnits - 1, 100, map.totalUnits)).toBe(map.totalUnits);
  });

  it("never coasts past the stop the glide was landing on, so a click back still leaves it", () => {
    const mirror = at("mirror");
    // Late in a glide to the mirror: the coast alone would run 6 units past it.
    const to = coastTarget(mirror - 5, 55, map.totalUnits, mirror);
    expect(to).toBe(mirror);
    // One click back up from there leaves the mirror (free to rest), not pulled back to it.
    expect(snapTarget(stops, to - click, to, commit)).toBeNull();
    // Moving away from it (an overshoot turning round) it coasts on as before.
    expect(coastTarget(mirror + 4, 30, map.totalUnits, mirror)).toBeCloseTo(mirror + 10, 9);
  });
});

describe("wheelPixels", () => {
  it("reads pixels, lines and pages", () => {
    expect(wheelPixels(100, 0, 800)).toBe(100);
    expect(wheelPixels(-3, 1, 800)).toBe(-120);
    expect(wheelPixels(1, 2, 800)).toBe(800);
    expect(wheelPixels(Number.NaN, 0, 800)).toBe(0);
  });
});
