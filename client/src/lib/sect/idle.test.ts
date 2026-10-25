import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  ARENA_HANGS,
  AREA_FRAMES,
  BANNER_HANGS,
  CRANE_GLIDES,
  FILM_TURN_SPEED,
  FIVE_ELEMENT_FLAGS,
  FLAG_FLIES,
  FLY_LIFT,
  FORMATION_CORE_SPEED,
  bobLift,
  breathe,
  craneFlap,
  fanHang,
  glideHeading,
  glidePivot,
  fitRing,
  flicker,
  flySway,
  hangStill,
  hangSway,
  hotspotHang,
  inCylinder,
  inFly,
  inHang,
  qiFlag,
  rigidStep,
  splitTriangles,
  treeSway,
  wave,
  type AreaFrame,
  type BannerHang,
  type FlagFly,
  type V3,
} from "./idle";

/** Points around a ring of radius r at centre c, tilted by `tilt` about the x axis. */
function ring(c: V3, r: number, tilt: number, n = 60, wobble = 0): V3[] {
  return Array.from({ length: n }, (_, i) => {
    const a = (2 * Math.PI * i) / n;
    const x = r * Math.cos(a);
    const z0 = r * Math.sin(a);
    const h = wobble * Math.sin(3 * a);
    // Tilt about x: y gains z0 * sin(tilt).
    return [c[0] + x, c[1] + z0 * Math.sin(tilt) + h * Math.cos(tilt), c[2] + z0 * Math.cos(tilt) - h * Math.sin(tilt)] as V3;
  });
}

describe("fitRing", () => {
  it("recovers a tilted hoop's centre, normal and radius", () => {
    const tilt = (12 * Math.PI) / 180;
    const fit = fitRing(ring([107.7, 104.5, -329.7], 13, tilt))!;
    expect(fit.radius).toBeCloseTo(13, 3);
    expect(fit.center[0]).toBeCloseTo(107.7, 3);
    expect(fit.center[1]).toBeCloseTo(104.5, 3);
    expect(fit.center[2]).toBeCloseTo(-329.7, 3);
    expect((Math.acos(fit.normal[1]) * 180) / Math.PI).toBeCloseTo(12, 3);
    expect(fit.normal[1]).toBeGreaterThan(0);
    expect(fit.planeError).toBeLessThan(1e-6);
  });

  it("is not thrown off by a bob that runs three times round the ring", () => {
    const fit = fitRing(ring([0, 10, 0], 13, 0.2, 15, 0.45))!;
    expect((Math.acos(fit.normal[1]) * 180) / Math.PI).toBeCloseTo((0.2 * 180) / Math.PI, 1);
  });

  it("gives up on too few or degenerate points", () => {
    expect(fitRing([[0, 0, 0]])).toBeNull();
    expect(fitRing(Array.from({ length: 8 }, () => [1, 2, 3] as V3))).toBeNull();
  });
});

describe("rhythms", () => {
  it("matches the film's speeds", () => {
    // One turn per 1500 frames (1499 frame steps) at 24 fps: about a minute.
    expect((2 * Math.PI) / FILM_TURN_SPEED).toBeCloseTo(1499 / 24, 6);
    // The armillary's driver, frame * 0.0025 (formation.py), at 24 fps.
    expect(FORMATION_CORE_SPEED).toBeCloseTo(0.06, 6);
  });

  it("breathes between 0 and 1 once a period", () => {
    expect(breathe(0, 4)).toBeCloseTo(0);
    expect(breathe(2, 4)).toBeCloseTo(1);
    expect(breathe(4, 4)).toBeCloseTo(0);
  });

  it("runs a wave along a row, one item at a time", () => {
    const n = 7;
    const P = 7;
    for (let i = 0; i < n; i++) {
      // Item i peaks a little after i/n of the cycle, and is dark half a cycle later.
      const peak = (i / n + 0.16) * P;
      expect(wave(peak, P, i, n)).toBeGreaterThan(0.9);
      expect(wave(peak + P / 2, P, i, n)).toBe(0);
    }
  });

  it("flickers inside 0..1 and never goes dark for long", () => {
    let low = 0;
    for (let t = 0; t < 30; t += 0.01) {
      const f = flicker(t, 1.3);
      expect(f).toBeGreaterThanOrEqual(0);
      expect(f).toBeLessThanOrEqual(1);
      if (f < 0.1) low++;
    }
    expect(low).toBeLessThan(300);
  });
});

/**
 * Points of a props.banner 'fan' banner as banner() builds it round a hang, its pole standing on
 * `foot` (three space): the pole and its clamping stones, the gold fittings (finial, the arm out
 * to the hook, the arm's brace, the hook's ring and the arm's curled end), the stiffener rod with
 * its knobs, the head above it, and the cloth and its tails below it.
 */
function fanParts(h: BannerHang, foot: number): Record<"pole" | "stones" | "finial" | "arm" | "brace" | "hook" | "curl" | "rod" | "head" | "cloth" | "tails", V3[]> {
  const W = h.width;
  const La = 0.75 + 0.6 * W;
  const za = h.hook[1] + 0.06;
  const top = za + 0.35;
  /** `along` from the hook (toward the pole is negative), `across` off the cloth's plane, at height y. */
  const at = (along: number, across: number, y: number): V3 => [
    h.hook[0] + h.out[0] * along - h.out[1] * across,
    y,
    h.hook[2] + h.out[1] * along + h.out[0] * across,
  ];
  /** n points round the pole (or, `along` from it, round that point) at radius r and height y. */
  const round = (r: number, y: number, along = 0, n = 8) =>
    Array.from({ length: n }, (_, k) => at(-La + along + r * Math.cos((2 * Math.PI * k) / n), r * Math.sin((2 * Math.PI * k) / n), y));
  const span = (n: number, f: (t: number) => V3) => Array.from({ length: n + 1 }, (_, k) => f(k / n));
  const rod = 0.42 * W;
  return {
    pole: [0.1, 0.5, 0.9, 0.999].flatMap((t) => round(0.07, foot + t * (top - 0.02 - foot))),
    stones: [0.05, 0.6].flatMap((y) => [...round(0.34, foot + y), ...round(0.48, foot + y)]),
    finial: [0, 0.2, 0.52].flatMap((y) => round(0.05, top + y)),
    arm: span(8, (t) => at(-La + t * La, 0.03, za - 0.03)),
    brace: span(6, (t) => at(-La + 0.5 * t, 0, za - 0.55 + 0.53 * t)),
    hook: round(0.028, za - 0.045, La, 6),
    curl: span(4, (t) => at(0.075 + 0.1 * t, 0, za - 0.125 + 0.06 * t)),
    // The knobs' undersides (0.035 width round the rod's ends) and the rod between them, billowed.
    rod: [-0.685, -0.4, 0, 0.4, 0.685].flatMap((s) => [at(s * W, 0.035 * W, h.hook[1] - rod - 0.035 * W), at(s * W, -0.035 * W, h.hook[1] - rod + 0.035 * W)]),
    head: span(4, (t) => at(0.4 * W * t, 0, h.hook[1] - rod * t)),
    cloth: span(6, (t) => at(-0.5 * W + W * t, 0.2, h.hook[1] - rod - 0.5 - t * (h.length - rod - 0.8))),
    tails: [-0.33, 0, 0.33].map((s) => at(s * W + 0.05 * h.length, 0.4, h.hook[1] - h.length)),
  };
}

describe("the arena's ring of banners", () => {
  const ring = ARENA_HANGS;
  /** The band the poles stand on (arena.py Z_BAND), in three space. */
  const ARENA_FOOT = AREA_FRAMES.arena.at[2] - 0.35;

  it("hangs forty, the hackathon banners first and the four decor ones the merged scenery holds last", () => {
    expect(ring).toHaveLength(40);
    expect(BANNER_HANGS.arena).toEqual(ring.slice(36));
    for (let i = 0; i < 36; i++) expect(hotspotHang(`hackathon:${i}`)).toBe(ring[i]);
    for (const id of ["hackathon:36", "hackathon:x", "arena", "arena-judges", "role:0", "project:tft"]) expect(hotspotHang(id)).toBeNull();
    // Banner 35, next to the four, as arena.py stands it.
    expect(Math.abs(ring[35].hook[0] - -37.797)).toBeLessThan(0.01);
    expect(Math.abs(ring[35].hook[2] - -452.885)).toBeLessThan(0.01);
    for (const h of ring) {
      expect(h.width).toBe(1.3);
      expect(Math.hypot(h.out[0], h.out[1])).toBeCloseTo(1, 9);
    }
  });

  it("stands each hackathon banner in its meta.json box, its height and its finial tall", () => {
    const meta = JSON.parse(readFileSync(path.resolve(__dirname, "../../../public/sect/full/meta.json"), "utf8")) as {
      hotspots: { id: string; center: V3; size: V3 }[];
    };
    const boxes = meta.hotspots.filter((b) => b.id.startsWith("hackathon:"));
    expect(boxes).toHaveLength(36);
    for (const b of boxes) {
      const h = hotspotHang(b.id)!;
      const La = 0.75 + 0.6 * h.width;
      const pole: V3 = [h.hook[0] - h.out[0] * La, h.hook[1], h.hook[2] - h.out[1] * La];
      const inBox = (p: V3) => [0, 2].every((i) => Math.abs(p[i] - b.center[i]) <= b.size[i] / 2 + 0.02);
      expect(inBox(h.hook)).toBe(true);
      expect(inBox(pole)).toBe(true);
      // The box runs from the pole's foot to its finial's tip, 0.52 m over the pole's top; the
      // hook hangs 0.41 m under that top.
      expect(Math.abs(b.center[1] + b.size[1] / 2 - (h.hook[1] + 0.41 + 0.52))).toBeLessThan(0.01);
      expect(Math.abs(b.center[1] - b.size[1] / 2 - ARENA_FOOT)).toBeLessThan(0.01);
    }
  });

  it("swings no two neighbours round the ring in step", () => {
    // Each banner's tails, under its hook: the flutter's phase there (the ring is one row, 39 pairs).
    const w = hangSway(ring.flatMap((h) => [h.hook[0], h.hook[1] - h.length, h.hook[2]]), ring);
    const apart = (a: number, b: number) => {
      const d = (((w[b * 4 + 3] - w[a * 4 + 3]) % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
      return Math.min(d, 2 * Math.PI - d);
    };
    for (let i = 0; i < ring.length; i++) expect(Math.hypot(w[i * 4], w[i * 4 + 2])).toBeCloseTo(1, 6);
    for (let i = 0; i + 1 < ring.length; i++) expect(apart(i, i + 1)).toBeGreaterThan(2);
    for (let i = 0; i + 2 < ring.length; i++) expect(apart(i, i + 2)).toBeGreaterThan(1.2);
  });

  it("moves banner 9 off the centre aisle's foot, 2 m back round the ring", () => {
    const pole = (h: BannerHang) => [h.hook[0] - h.out[0] * 1.53, h.hook[2] - h.out[1] * 1.53];
    const gap = (a: BannerHang, b: BannerHang) => Math.hypot(pole(a)[0] - pole(b)[0], pole(a)[1] - pole(b)[1]);
    // Neighbours stand 32.2 m x (334 / 39) deg apart (4.81 m on the chord).
    expect(gap(ring[7], ring[8])).toBeCloseTo(4.809, 2);
    expect(gap(ring[8], ring[9])).toBeCloseTo(4.809 - 2, 1);
    expect(gap(ring[9], ring[10])).toBeCloseTo(4.809 + 2, 1);
  });

  it("sways only a hackathon banner's cloth: its pole, stones, gold fittings, rod and head hold still", () => {
    for (const k of [0, 9, 20, 35]) {
      const h = ring[k];
      const parts = fanParts(h, ARENA_FOOT);
      const names = Object.keys(parts) as (keyof typeof parts)[];
      const w = hangSway(names.flatMap((n) => parts[n].flat()), [h]);
      const weight = (i: number) => Math.hypot(w[i * 4], w[i * 4 + 1], w[i * 4 + 2]);
      let i = 0;
      for (const n of names) {
        for (let j = 0; j < parts[n].length; j++, i++) {
          if (n === "cloth") expect(weight(i)).toBeGreaterThan(j === 0 ? 0.03 : 0.1);
          else if (n === "tails") expect(weight(i)).toBeCloseTo(1, 6);
          else expect(weight(i)).toBe(0);
        }
      }
    }
  });
});

describe("banners merged into the scenery", () => {
  const gate = BANNER_HANGS.gate;
  const westPlaza = gate.find((h) => h.hook[0] < 0 && h.hook[2] === 30)!;
  const eastLanding = gate.find((h) => h.hook[0] > 0 && h.hook[2] === 59.26)!;

  it("lists the gate's twelve, in pairs facing each other with their arms toward the axis", () => {
    expect(gate).toHaveLength(12);
    for (const h of gate) {
      expect(gate.some((o) => o.hook[0] === -h.hook[0] && o.hook[1] === h.hook[1] && o.hook[2] === h.hook[2])).toBe(true);
      expect(h.out[0]).toBe(-Math.sign(h.hook[0]));
      expect(h.out[1]).toBe(0);
      // gate.py: the hook hangs (0.75 + 0.6 width) in from the pole, 0.41 m under the pole's top.
      const pole = Math.abs(h.hook[0]) + 0.75 + 0.6 * h.width;
      expect(pole).toBeCloseTo(h.width === 1.7 ? 19.4 : 9.5, 6);
      expect(h.length).toBeCloseTo(0.6 * (h.width === 1.7 ? 14 : 12), 6);
    }
  });

  it("takes the cloth and none of the pole, arm, brace, ground or a landing's lantern", () => {
    const [x, y, z] = westPlaza.hook;
    // The cloth, its tails swung out along the arm, its billow off the plane, and both knobs of
    // its stiffener rod (0.42 width down, 0.685 width out, 6 cm round).
    expect(inHang(westPlaza, x, y, z)).toBe(true);
    expect(inHang(westPlaza, x - 1, y - 3, z + 0.4)).toBe(true);
    expect(inHang(westPlaza, x + 1.45, y - 8.4, z - 0.9)).toBe(true);
    for (const s of [-1, 1]) expect(inHang(westPlaza, x + s * 0.685 * 1.7, y - 0.714, z)).toBe(true);
    // The pole (1.77 m back toward x = -19.4), the brace's end, the arm above the hook, the ground.
    expect(inHang(westPlaza, -19.4, y - 4, z)).toBe(false);
    expect(inHang(westPlaza, -19.4 + 0.52, y + 0.02, z)).toBe(false);
    expect(inHang(westPlaza, -19.4 + 0.52, y - 0.2, z)).toBe(false);
    expect(inHang(westPlaza, x, y + 0.06, z)).toBe(false);
    expect(inHang(westPlaza, x, 40, z)).toBe(false);
    expect(inHang(westPlaza, x, y - 4, z + 1.5)).toBe(false);
    // The landing's stone lantern stands 0.65 m in from the cloth, 0.6 m along, 3.2 m tall.
    const [lx, ly, lz] = eastLanding.hook;
    const foot = ly - 11.59;
    expect(inHang(eastLanding, 8.5, foot + 3.2, lz + 0.6)).toBe(false);
    expect(inHang(eastLanding, lx, ly - 5, lz)).toBe(true);
  });

  it("holds the hook, the head and the stiffener rod still and swings the tails most, across the cloth", () => {
    const [x, y, z] = westPlaza.hook;
    const L = westPlaza.length;
    const still = hangStill(westPlaza);
    // The hook, the arm's curled end just under it, the rod's knobs' undersides (0.42 width down,
    // 0.685 width out, 0.035 width round), halfway down, a tail.
    const knob = 0.42 * 1.7 + 0.035 * 1.7;
    const pts = [x, y, z, x + 0.17, y - 0.1, z, x - 1.165, y - knob, z, x + 1.165, y - knob, z, x, y - L / 2, z, x + 0.5, y - L, z];
    const w = hangSway(pts, gate);
    const weight = (i: number) => Math.hypot(w[i * 4], w[i * 4 + 1], w[i * 4 + 2]);
    for (let i = 0; i < 4; i++) expect(weight(i)).toBe(0);
    expect(weight(4)).toBeCloseTo(((L / 2 - still) / (L - still)) ** 1.2, 6);
    expect(weight(5)).toBeCloseTo(1, 6);
    // The cloth hangs from the rod: still down to its knobs, with 2 cm of room.
    expect(still).toBeCloseTo(knob + 0.02, 9);
    expect(hangSway([x, y - still + 1e-4, z], gate)[2]).toBe(0);
    expect(hangSway([x, y - still - 1e-3, z], gate)[2]).toBeGreaterThan(0);
    expect(hangSway([x, y - still - 0.3, z], gate)[2]).toBeGreaterThan(0);
    // Along the cloth's normal (z here): never along the arm, never up.
    for (let i = 0; i < 6; i++) {
      expect(w[i * 4]).toBeCloseTo(0, 9);
      expect(w[i * 4 + 1]).toBe(0);
    }
    // A ripple runs across the cloth.
    expect(w[23]).not.toBe(w[19]);
  });

  it("moves nothing outside a banner's space (a pole, its stones, its fittings), wherever it is", () => {
    for (const h of [westPlaza, eastLanding]) {
      const foot = h.hook[1] + 0.41 - (h.width === 1.7 ? 14 : 12);
      const parts = fanParts(h, foot);
      for (const n of ["pole", "stones", "finial", "arm", "brace", "hook", "curl", "rod", "head"] as const) {
        const w = hangSway(parts[n].flat(), gate);
        expect([...w].filter((_, i) => i % 4 !== 3).every((v) => v === 0)).toBe(true);
      }
      expect(Math.max(...[...hangSway(parts.tails.flat(), gate)].filter((_, i) => i % 4 === 2).map(Math.abs))).toBeCloseTo(1, 6);
    }
  });

  it("gives each vertex its nearest banner's weight and phase, so neighbours swing out of step", () => {
    const a = westPlaza;
    const b = gate.find((h) => h.hook[0] < 0 && h.hook[2] === 20)!;
    const at = (h: BannerHang): V3 => [h.hook[0], h.hook[1] - h.length, h.hook[2]];
    const w = hangSway([...at(a), ...at(b)], gate);
    expect(w[2]).toBeCloseTo(1, 6);
    expect(w[6]).toBeCloseTo(1, 6);
    expect(w[3]).not.toBeCloseTo(w[7], 3);
    // A landing banner (shorter, narrower cloth) by its own length and rod.
    const l = hangSway([eastLanding.hook[0], eastLanding.hook[1] - 3.6, eastLanding.hook[2]], gate);
    const still = hangStill(eastLanding);
    expect(still).toBeLessThan(hangStill(westPlaza));
    expect(Math.abs(l[2])).toBeCloseTo(((3.6 - still) / (7.2 - still)) ** 1.2, 6);
  });

  it("is empty without banners", () => {
    expect([...hangSway([0, 0, 0, 1, 2, 3], [])].every((v) => v === 0)).toBe(true);
  });
});

describe("the forge's, the arena's and the mission hall's merged banners", () => {
  /**
   * Read from out/sect_chase.blend with round 5's sun-and-moon cloths: each cloth object's origin
   * (the hook), its width axis on the ground, and how far its mesh reaches below the hook.
   */
  const FILE: Record<string, { hook: V3; out: [number, number]; down: number }[]> = {
    forge: [
      { hook: [78.295, 104.59, -322.73], out: [0.5812, 0.8137], down: 5.925 },
      { hook: [91.489, 104.59, -304.258], out: [-0.5812, -0.8137], down: 5.925 },
    ],
    arena: [
      { hook: [-32.983, 127.96, -452.827], out: [-0.9939, 0.1099], down: 5.167 },
      { hook: [-28.214, 128.359, -453.486], out: [-0.9665, 0.2567], down: 5.398 },
      { hook: [-23.597, 128.38, -454.848], out: [-0.9175, 0.3977], down: 5.417 },
      { hook: [-19.234, 127.931, -456.882], out: [-0.848, 0.5299], down: 5.15 },
    ],
    mission: [
      { hook: [-135.792, 148.59, -584.906], out: [0.7727, -0.6347], down: 5.338 },
      { hook: [-113.429, 148.59, -603.276], out: [-0.7727, 0.6347], down: 5.333 },
    ],
  };

  it("hang where the file's cloths hang", () => {
    for (const [area, cloths] of Object.entries(FILE)) {
      const hangs = BANNER_HANGS[area];
      expect(hangs).toHaveLength(cloths.length);
      cloths.forEach((c, k) => {
        const h = hangs[k];
        for (let i = 0; i < 3; i++) expect(Math.abs(h.hook[i] - c.hook[i])).toBeLessThan(2e-3);
        for (let i = 0; i < 2; i++) expect(Math.abs(h.out[i] - c.out[i])).toBeLessThan(2e-4);
        expect(Math.hypot(h.out[0], h.out[1])).toBeCloseTo(1, 9);
        // The cloth (its tails lifted a little by the baked wind) ends just above its length.
        expect(c.down).toBeLessThanOrEqual(h.length);
        expect(c.down).toBeGreaterThan(h.length - 0.1);
        // Its hook, rod knobs and tails are inside its space.
        expect(inHang(h, ...h.hook)).toBe(true);
        for (const s of [-1, 1]) expect(inHang(h, h.hook[0] + s * 0.685 * h.width * h.out[0], h.hook[1] - 0.42 * h.width, h.hook[2] + s * 0.685 * h.width * h.out[1])).toBe(true);
        expect(inHang(h, h.hook[0], h.hook[1] - c.down, h.hook[2])).toBe(true);
      });
    }
  });

  it("builds the gate's plaza banners as its table lists them", () => {
    const gate: AreaFrame = { at: [0, 0, 40], yaw: 0 };
    for (const y of [-30, -20, 0, 14]) {
      for (const s of [-1, 1]) {
        const f = fanHang(gate, s * 19.4, y, 0, s < 0 ? 0 : Math.PI, 14, 1.7);
        const g = BANNER_HANGS.gate.find((h) => Math.sign(h.hook[0]) === s && h.hook[2] === -y)!;
        for (let i = 0; i < 3; i++) expect(f.hook[i]).toBeCloseTo(g.hook[i], 6);
        expect(f.out[0]).toBeCloseTo(g.out[0], 9);
        expect(f.out[1]).toBeCloseTo(g.out[1], 9);
        expect(f.length).toBeCloseTo(g.length, 9);
      }
    }
  });

  it("pairs the forge's and the mission hall's across the area's axis, arms toward each other", () => {
    for (const area of ["forge", "mission"] as const) {
      const [a, b] = BANNER_HANGS[area];
      const f = AREA_FRAMES[area];
      const dx = b.hook[0] - a.hook[0];
      const dz = b.hook[2] - a.hook[2];
      expect((dx * a.out[0] + dz * a.out[1]) / Math.hypot(dx, dz)).toBeCloseTo(1, 9);
      expect(b.out[0]).toBeCloseTo(-a.out[0], 9);
      expect(b.out[1]).toBeCloseTo(-a.out[1], 9);
      // Halfway between them is the area's axis (local x = 0), in front of its centre.
      const mx = (a.hook[0] + b.hook[0]) / 2 - f.at[0];
      const my = -(a.hook[2] + b.hook[2]) / 2 - f.at[1];
      expect(mx * Math.cos(f.yaw) + my * Math.sin(f.yaw)).toBeCloseTo(0, 6);
      expect(-mx * Math.sin(f.yaw) + my * Math.cos(f.yaw)).toBeLessThan(-30);
    }
  });

  it("keeps the arena's hackathon banners (hotspots of their own) out of the four's spaces", () => {
    // Banner 35, the hackathon next to the four, hangs well clear of every one of their spaces.
    const gap = (13 * Math.PI) / 180;
    const a = -Math.PI / 2 + gap + ((2 * Math.PI - 2 * gap) * 35) / 39;
    const h35 = fanHang(AREA_FRAMES.arena, 32.2 * Math.cos(a), 32.2 * Math.sin(a), -0.35, a - Math.PI / 2, 9, 1.3);
    expect(Math.abs(h35.hook[0] - -37.797)).toBeLessThan(0.01);
    expect(Math.abs(h35.hook[2] - -452.885)).toBeLessThan(0.01);
    for (const h of BANNER_HANGS.arena) {
      for (const dy of [0, 2, 5]) expect(inHang(h, h35.hook[0], h35.hook[1] - dy, h35.hook[2])).toBe(false);
    }
  });

  it("keeps every banner's space its own", () => {
    for (const hangs of Object.values(BANNER_HANGS)) {
      for (const a of hangs) {
        for (const b of hangs) {
          if (a === b) continue;
          // Farther apart than the two spaces reach out from their hooks.
          const reach = (h: BannerHang) => Math.hypot(0.685 * h.width + 0.05 * h.length + 0.1, 0.65 * h.width);
          expect(Math.hypot(a.hook[0] - b.hook[0], a.hook[2] - b.hook[2])).toBeGreaterThan(reach(a) + reach(b));
        }
      }
    }
  });

  it("swings each tail across its own cloth, level", () => {
    for (const area of ["forge", "arena", "mission"]) {
      const hangs = BANNER_HANGS[area];
      const w = hangSway(hangs.flatMap((h) => [h.hook[0], h.hook[1] - h.length, h.hook[2]]), hangs);
      hangs.forEach((h, k) => {
        // (Stored as 32-bit floats.)
        expect(w[k * 4]).toBeCloseTo(-h.out[1], 6);
        expect(w[k * 4 + 1]).toBe(0);
        expect(w[k * 4 + 2]).toBeCloseTo(h.out[0], 6);
      });
    }
  });
});

describe("the formation's Five Element flags", () => {
  const flags = FIVE_ELEMENT_FLAGS;
  const wood = flags[0];
  /** A point `along` out from the pole, `across` off the cloth's plane, at height y. */
  const at = (f: FlagFly, along: number, across: number, y: number): V3 => [
    f.pole[0] + f.out[0] * along - f.out[1] * across,
    y,
    f.pole[1] + f.out[1] * along + f.out[0] * across,
  ];
  /** A ring of n points round the pole at height y and radius r, the first along the cloth. */
  const round = (f: FlagFly, r: number, y: number, n: number, k: number): V3 => {
    const a = (2 * Math.PI * k) / n;
    return at(f, r * Math.cos(a), r * Math.sin(a), y);
  };

  it("fly where the bake's cloths fly", () => {
    // Read from the baked formation and abode chunks (high and low): every flag's hoist edge 0.098 m
    // from its pole in the cloth's plane, rows from 234.652 down to 230.956 m, the teeth's tips at
    // 235.239 m, the drooping fly no lower than 230.008 m, the fly 5.016 m out.
    expect(flags).toHaveLength(5);
    for (const f of flags) {
      expect(f.hoist).toBeCloseTo(0.098, 3);
      expect(Math.abs(f.hoistTop - 234.652)).toBeLessThan(2e-3);
      expect(Math.abs(f.hoistBottom - 230.956)).toBeLessThan(2e-3);
      expect(Math.abs(f.top - 235.239)).toBeLessThan(5e-3);
      expect(f.bottom).toBeLessThan(230.008);
      expect(Math.abs(f.reach - 5.016)).toBeLessThan(3e-3);
      expect(Math.hypot(f.out[0], f.out[1])).toBeCloseTo(1, 9);
      // One wind: they all fly the same way (the area's -x).
      expect(f.out[0]).toBeCloseTo(wood.out[0], 9);
      expect(f.out[1]).toBeCloseTo(wood.out[1], 9);
    }
    expect(wood.pole[0]).toBeCloseTo(98.59, 2);
    expect(wood.pole[1]).toBeCloseTo(-1165.06, 2);
  });

  it("stand inside meta.json's five-element-banners boxes, wood to water", () => {
    const meta = JSON.parse(readFileSync(path.resolve(__dirname, "../../../public/sect/full/meta.json"), "utf8")) as {
      lore: { id: string; boxes: { center: V3; size: V3; objects: string[] }[] }[];
    };
    const boxes = meta.lore.find((l) => l.id === "five-element-banners")!.boxes;
    expect(boxes.map((b) => b.objects[0])).toEqual(["wood", "fire", "earth", "metal", "water"].map((k) => `formation.flag.${k}`));
    flags.forEach((f, k) => {
      const b = boxes[k];
      const inBox = (p: V3) => [0, 1, 2].every((i) => Math.abs(p[i] - b.center[i]) <= b.size[i] / 2 + 0.05);
      expect(inBox(at(f, 0, 0, f.hoistTop))).toBe(true);
      expect(inBox(at(f, f.reach, 0, f.hoistBottom))).toBe(true);
      expect(inBox(at(f, f.reach / 2, 0, f.top))).toBe(true);
    });
  });

  it("takes the cloth from its hoist edge to its fly", () => {
    for (const f of flags) {
      // The hoist edge's rows (0.33 of 1.4 apart), its tooth bases, the cloth, the fly, the billow.
      for (let j = 0; j <= 8; j++) expect(inFly(f, ...at(f, f.hoist, 0.0004, f.hoistTop - 0.462 * j))).toBe(true);
      expect(inFly(f, ...at(f, 0.3, 0, f.top - 0.3))).toBe(true);
      expect(inFly(f, ...at(f, 2.5, 0.6, 233))).toBe(true);
      expect(inFly(f, ...at(f, f.reach, -0.9, f.hoistBottom - 0.2))).toBe(true);
      expect(inFly(f, ...at(f, 4, 1.2, f.bottom))).toBe(true);
      // Not the ground, the drum, beyond the fly, nor far off the plane.
      expect(inFly(f, ...at(f, 2, 0, 221))).toBe(false);
      expect(inFly(f, ...at(f, 0.4, 0, 222.2))).toBe(false);
      expect(inFly(f, ...at(f, f.reach + 0.3, 0, 233))).toBe(false);
      expect(inFly(f, ...at(f, 2, 1.5, 233))).toBe(false);
    }
  });

  it("cuts out no triangle of the pole, its hoist rings or its finial", () => {
    // props.banner at 1.4 x: a 16-sided pole 0.091 m round halfway up (8.1 m above the drum) and
    // 0.07 m at its top cap (15.07 m); four rings 0.105 m round, 0.017 thick (16 x 6 faces); the
    // finial from 15.06 m up, 0.112 m round at most.
    const tri = (f: FlagFly, ps: V3[]) => ps.every((p) => inFly(f, ...p));
    for (const f of flags) {
      const foot = f.hoistTop - 1.4 * 9.68;
      const cut: V3[][] = [];
      // The pole's side between its two upper vertex rings, and its top cap.
      for (let k = 0; k < 16; k++) {
        const a = round(f, 0.091, foot + 7.0, 16, k), b = round(f, 0.091, foot + 7.0, 16, k + 1);
        const c = round(f, 0.07, foot + 13.972, 16, k), d = round(f, 0.07, foot + 13.972, 16, k + 1);
        cut.push([a, b, c], [b, d, c], [c, d, at(f, 0, 0, foot + 13.972)]);
      }
      // The rings: a torus round the pole at each centre.
      for (const y of f.rings) {
        for (let k = 0; k < 16; k++) {
          for (let q = 0; q < 6; q++) {
            const pt = (kk: number, qq: number): V3 => {
              const phi = (2 * Math.PI * qq) / 6;
              return round(f, 1.4 * (0.075 + 0.012 * Math.cos(phi)), y + 1.4 * 0.012 * Math.sin(phi), 16, kk);
            };
            cut.push([pt(k, q), pt(k + 1, q), pt(k + 1, q + 1)], [pt(k, q), pt(k + 1, q + 1), pt(k, q + 1)]);
          }
        }
      }
      // The finial's lathe (radius, height above the pole's top).
      const fin: [number, number][] = [[0.062, -0.03], [0.07, 0], [0.05, 0.04], [0.08, 0.11], [0.05, 0.18], [0.022, 0.21], [0.045, 0.3], [0.03, 0.4], [0, 0.52]];
      for (let i = 0; i + 1 < fin.length; i++) {
        for (let k = 0; k < 16; k++) {
          const p = (j: number, kk: number) => round(f, 1.4 * fin[j][0], foot + 1.4 * (10 + fin[j][1]), 16, kk);
          cut.push([p(i, k), p(i, k + 1), p(i + 1, k + 1)], [p(i, k), p(i + 1, k + 1), p(i + 1, k)]);
        }
      }
      for (const t of cut) expect(tri(f, t)).toBe(false);
      // A ring's vertices in the cloth's plane are out too (by height), while the hoist edge's
      // rows 2.8 cm above two of the rings are in.
      for (const y of f.rings) for (const dy of [-0.0168, -0.0146, 0, 0.0146, 0.0168]) for (const r of [0.0882, 0.0966, 0.1134, 0.1218]) expect(inFly(f, ...at(f, r, 0, y + dy))).toBe(false);
      expect(inFly(f, ...at(f, f.hoist, 0, f.rings[0] + 0.028))).toBe(true);
      expect(inFly(f, ...at(f, f.hoist, 0, f.rings[2] + 0.028))).toBe(true);
    }
  });

  it("keeps each flag's space its own", () => {
    for (const a of flags) {
      for (const b of flags) {
        if (a === b) continue;
        for (const along of [a.hoist, a.reach / 2, a.reach]) for (const across of [-1, 0, 1]) expect(inFly(b, ...at(a, along, across, 233))).toBe(false);
      }
    }
  });

  it("holds the hoist edge and the pole, and swings the fly most, across the cloth and up", () => {
    const f = flags[2];
    const pts = [f.hoist, f.clear, 2.5, f.reach].flatMap((along) => at(f, along, 0, 233));
    const w = flySway(pts, flags);
    const level = (i: number) => Math.hypot(w[i * 4], w[i * 4 + 2]);
    expect(level(0)).toBe(0);
    expect(w[1]).toBe(0);
    expect(level(1)).toBeCloseTo(0, 9);
    expect(level(2)).toBeCloseTo(((2.5 - f.clear) / (f.reach - f.clear)) ** 1.2, 6);
    expect(level(3)).toBeCloseTo(1, 6);
    for (let i = 0; i < 4; i++) {
      // Across the cloth (never along it), and FLY_LIFT as much up.
      expect(w[i * 4] * f.out[0] + w[i * 4 + 2] * f.out[1]).toBeCloseTo(0, 6);
      expect(w[i * 4 + 1]).toBeCloseTo(FLY_LIFT * level(i), 6);
    }
    // The ripple runs out from the pole: the phase falls going out.
    expect(w[11]).toBeLessThan(w[7]);
    expect(w[15]).toBeLessThan(w[11]);
  });

  it("gives each vertex its own flag's weight and phase, so neighbours swing out of step", () => {
    const tips = flags.flatMap((f) => at(f, f.reach, 0, 233));
    const w = flySway(tips, flags);
    flags.forEach((f, k) => {
      expect(w[k * 4]).toBeCloseTo(-f.out[1], 6);
      expect(w[k * 4 + 2]).toBeCloseTo(f.out[0], 6);
    });
    expect(new Set(flags.map((_, k) => w[k * 4 + 3].toFixed(3))).size).toBe(5);
    expect([...flySway([0, 0, 0, 1, 2, 3], [])].every((v) => v === 0)).toBe(true);
  });

  it("are cut from the formation's chunk, which holds all five cloths since the round-48 bake", () => {
    expect(FLAG_FLIES.formation).toBe(FIVE_ELEMENT_FLAGS);
    expect(Object.keys(FLAG_FLIES)).toEqual(["formation"]);
  });

  it("builds a flag as qiFlag reads props.banner", () => {
    // An unturned, unscaled 6 m flag 1 m wide at the area's origin, flying along +x.
    const f = qiFlag({ at: [0, 0, 0], yaw: 0 }, 0, 0, 0, 0, 6, 1, 1);
    expect(f.pole).toEqual([0, -0]);
    expect(f.out[0]).toBeCloseTo(1, 9);
    expect(f.out[1]).toBeCloseTo(0, 9);
    expect(f.hoistTop).toBeCloseTo(5.68, 9);
    expect(f.hoistBottom).toBeCloseTo(5.68 - 0.8, 9);
    expect(f.rings).toHaveLength(4);
    expect(f.rings[0]).toBeCloseTo(5.66, 9);
    expect(f.rings[3]).toBeCloseTo(5.66 - 0.75, 9);
    expect(f.clear).toBeCloseTo(0.097, 9);
  });
});

describe("treeSway", () => {
  it("is still at the base and strongest at the crown, along the wind", () => {
    const w = treeSway(new Float32Array([0, 0, 0, 0, 5, 0, 0, 10, 0]), [1, 0]);
    expect(w[0]).toBe(0);
    expect(w[4]).toBeCloseTo(0.25);
    expect(w[8]).toBeCloseTo(1);
    expect(w[10]).toBe(0);
  });
});

describe("carving", () => {
  const cyl = { x: 0, z: 0, rMin: 8, rMax: 19, yMin: 4, yMax: 40 };

  it("tests a cylinder shell", () => {
    expect(inCylinder(cyl, 10, 10, 0)).toBe(true);
    expect(inCylinder(cyl, 5, 10, 0)).toBe(false); // the pagoda inside
    expect(inCylinder(cyl, 10, 2, 0)).toBe(false); // the plaza below
    expect(inCylinder(cyl, 25, 10, 0)).toBe(false);
  });

  it("moves only triangles wholly inside", () => {
    const world = new Float32Array([10, 10, 0, 11, 10, 0, 10, 11, 0, 5, 10, 0, 30, 10, 0]);
    const index = [0, 1, 2, 0, 1, 3, 2, 1, 4];
    const { kept, carved } = splitTriangles(index, 5, world, (x, y, z) => inCylinder(cyl, x, y, z));
    expect(carved).toEqual([0, 1, 2]);
    expect(kept).toEqual([0, 1, 3, 2, 1, 4]);
    const flat = splitTriangles(null, 3, world, (x, y, z) => inCylinder(cyl, x, y, z));
    expect(flat.carved).toEqual([0, 1, 2]);
  });
});

describe("gliding cranes", () => {
  it("puts the loop's centre to the left, so a positive turn about +y flies head first", () => {
    const c: V3 = [10, 50, 0];
    const h: V3 = [0, 0, -1];
    const p = glidePivot(c, h, 14);
    expect(p).toEqual([-4, 50, 0]);
    // Turn the crane a little about +y through the pivot (right-handed): it moves along -z.
    const a = 0.01;
    const dx = c[0] - p[0], dz = c[2] - p[2];
    const moved: V3 = [p[0] + Math.cos(a) * dx + Math.sin(a) * dz, c[1], p[2] - Math.sin(a) * dx + Math.cos(a) * dz];
    expect(moved[2]).toBeLessThan(c[2]);
    expect(Math.abs(moved[0] - c[0])).toBeLessThan(0.01);
  });

  it("averages the pair's heading on the ground plane", () => {
    const h = glideHeading({ radius: 1, speed: 1, cranes: [{ p: [0, 0, 0], f: [1, 0.5, 0] }, { p: [0, 0, 0], f: [0, -0.5, 1] }] });
    expect(h[1]).toBe(0);
    expect(Math.hypot(h[0], h[2])).toBeCloseTo(1, 6);
    expect(h[0]).toBeCloseTo(h[2], 6);
  });

  it("beats the wings and keeps the bodies still", () => {
    const cranes: { p: V3; f: V3 }[] = [
      { p: [0, 0, 0], f: [0, 0, -1] },
      { p: [20, 0, 0], f: [0, 0, -1] },
    ];
    // Each crane: a body point, a beak point ahead, both wingtips (1 m out across the heading).
    const pts = [0, 0, 0, 0, 0, -1, 1, 0, 0, -1, 0, 0, 20, 0, 0, 21, 0, 0, 19, 0, 0];
    const w = craneFlap(pts, cranes);
    const up = (i: number) => w[i * 4 + 1];
    expect(up(0)).toBe(0);
    expect(up(1)).toBe(0);
    expect(up(2)).toBeCloseTo(1, 6);
    expect(up(3)).toBeCloseTo(1, 6);
    expect(up(5)).toBeCloseTo(1, 6);
    for (let i = 0; i < 7; i++) {
      expect(w[i * 4]).toBe(0);
      expect(w[i * 4 + 2]).toBe(0);
    }
    expect(w[3]).not.toBe(w[4 * 4 + 3]);
  });

  it("matches the crane hotspots in meta.json", () => {
    const meta = JSON.parse(readFileSync(path.resolve(__dirname, "../../../public/sect/full/meta.json"), "utf8")) as {
      hotspots: { id: string; center: V3; size: V3 }[];
    };
    for (const [id, g] of Object.entries(CRANE_GLIDES)) {
      const h = meta.hotspots.find((x) => x.id === id);
      expect(h, id).toBeDefined();
      for (const c of g.cranes) {
        for (let k = 0; k < 3; k++) expect(Math.abs(c.p[k] - h!.center[k])).toBeLessThanOrEqual(h!.size[k] / 2 + 0.5);
      }
    }
  });
});

describe("turning pieces' own clock", () => {
  it("stops while the piece is pointed at, so its bob holds still too", () => {
    let clock = 0;
    for (let i = 0; i < 30; i++) clock += rigidStep(1 / 60, false);
    expect(clock).toBeCloseTo(0.5, 9);
    const lift = bobLift(clock, 0.6, 1.2);
    // Hovered for two seconds: neither the clock nor the lift moves.
    for (let i = 0; i < 120; i++) clock += rigidStep(1 / 60, true);
    expect(clock).toBeCloseTo(0.5, 9);
    expect(bobLift(clock, 0.6, 1.2)).toBe(lift);
    // Let go: it carries on from there, with no jump.
    clock += rigidStep(1 / 60, false);
    expect(Math.abs(bobLift(clock, 0.6, 1.2) - lift)).toBeLessThan(0.01);
  });

  it("caps a long frame and ignores a bad one", () => {
    expect(rigidStep(2, false)).toBe(0.1);
    expect(rigidStep(-1, false)).toBe(0);
    expect(rigidStep(NaN, false)).toBe(0);
  });

  it("bobs within its amplitude, and not at all without one", () => {
    for (let t = 0; t < 20; t += 0.7) expect(Math.abs(bobLift(t, 0.18, 2.4))).toBeLessThanOrEqual(0.18);
    expect(bobLift(3, 0)).toBe(0);
  });
});
