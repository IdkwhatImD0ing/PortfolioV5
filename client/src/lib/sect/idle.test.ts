import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  BANNER_HANGS,
  CRANE_GLIDES,
  FILM_TURN_SPEED,
  FORMATION_CORE_SPEED,
  HANG_STILL,
  bannerSway,
  bobLift,
  breathe,
  craneFlap,
  glideHeading,
  glidePivot,
  fitRing,
  flicker,
  hangSway,
  inCylinder,
  inHang,
  rigidStep,
  splitTriangles,
  treeSway,
  wave,
  type BannerHang,
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

describe("bannerSway", () => {
  /** A pole at x = 1 from y 0 to 10, a crossbar at y 9.5, cloth from x -1.5 to 0.8 between y 3.5 and 9.5. */
  function banner(): Float32Array {
    const p: number[] = [];
    for (let y = 0; y <= 10; y += 0.5) p.push(1, y, 0.05, 1, y, -0.05);
    for (let x = -1.5; x <= 1; x += 0.25) p.push(x, 9.5, 0);
    for (let x = -1.5; x <= 0.8; x += 0.25) for (let y = 3.5; y <= 9.4; y += 0.5) p.push(x, y, 0.01 * Math.sin(x * 4));
    return new Float32Array(p);
  }

  it("keeps the pole and crossbar still and lets the free corner move most", () => {
    const pos = banner();
    const w = bannerSway(pos);
    const weight = (i: number) => Math.hypot(w[i * 4], w[i * 4 + 1], w[i * 4 + 2]);
    let maxPole = 0, maxCloth = 0, corner = 0;
    for (let i = 0; i < pos.length / 3; i++) {
      const x = pos[i * 3], y = pos[i * 3 + 1];
      if (x === 1) maxPole = Math.max(maxPole, weight(i));
      else if (y >= 9.5) maxPole = Math.max(maxPole, weight(i));
      else maxCloth = Math.max(maxCloth, weight(i));
      if (x === -1.5 && y === 3.5) corner = weight(i);
    }
    expect(maxPole).toBe(0);
    expect(maxCloth).toBeGreaterThan(0.5);
    expect(corner).toBeCloseTo(maxCloth, 5);
    // It moves across the cloth (z here), not along it.
    for (let i = 0; i < pos.length / 3; i++) expect(Math.abs(w[i * 4])).toBeLessThan(0.05 + Math.abs(w[i * 4 + 2]));
  });

  it("is empty for a flat or empty mesh", () => {
    expect(bannerSway(new Float32Array(0))).toHaveLength(0);
    expect([...bannerSway(new Float32Array([0, 0, 0, 1, 0, 0, 0, 0, 1]))].every((v) => v === 0)).toBe(true);
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

  it("holds the hook still and swings the tails most, across the cloth", () => {
    const [x, y, z] = westPlaza.hook;
    const L = westPlaza.length;
    // The hook, the arm's curled end just under it, halfway down, a tail.
    const pts = [x, y, z, x + 0.17, y - 0.1, z, x, y - L / 2, z, x + 0.5, y - L, z];
    const w = hangSway(pts, gate);
    const weight = (i: number) => Math.hypot(w[i * 4], w[i * 4 + 1], w[i * 4 + 2]);
    expect(weight(0)).toBe(0);
    expect(weight(1)).toBe(0);
    expect(weight(2)).toBeCloseTo(((L / 2 - HANG_STILL) / (L - HANG_STILL)) ** 1.2, 6);
    expect(weight(3)).toBeCloseTo(1, 6);
    // Along the cloth's normal (z here): never along the arm, never up.
    for (let i = 0; i < 4; i++) {
      expect(w[i * 4]).toBeCloseTo(0, 9);
      expect(w[i * 4 + 1]).toBe(0);
    }
    // A ripple runs across the cloth.
    expect(w[15]).not.toBe(w[11]);
  });

  it("gives each vertex its nearest banner's weight and phase, so neighbours swing out of step", () => {
    const a = westPlaza;
    const b = gate.find((h) => h.hook[0] < 0 && h.hook[2] === 20)!;
    const at = (h: BannerHang): V3 => [h.hook[0], h.hook[1] - h.length, h.hook[2]];
    const w = hangSway([...at(a), ...at(b)], gate);
    expect(w[2]).toBeCloseTo(1, 6);
    expect(w[6]).toBeCloseTo(1, 6);
    expect(w[3]).not.toBeCloseTo(w[7], 3);
    // A landing banner (shorter cloth) by its own length.
    const l = hangSway([eastLanding.hook[0], eastLanding.hook[1] - 3.6, eastLanding.hook[2]], gate);
    expect(Math.abs(l[2])).toBeCloseTo(((3.6 - HANG_STILL) / (7.2 - HANG_STILL)) ** 1.2, 6);
  });

  it("is empty without banners", () => {
    expect([...hangSway([0, 0, 0, 1, 2, 3], [])].every((v) => v === 0)).toBe(true);
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
