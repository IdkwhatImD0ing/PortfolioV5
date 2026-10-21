import { describe, expect, it } from "vitest";
import {
  clusterFlames,
  domeAlpha,
  domeCellsAround,
  domeGlsl,
  fireRadius,
  FORMATION_DOME,
  formationShafts,
  formationTier,
  hexDist,
  isFormationLinkBeam,
  rippleBands,
  shaftProfile,
  wispPulse,
} from "./formation";
import { SECT_LOOK } from "./look";
import type { Vec3 } from "./types";

const F = SECT_LOOK.formation;

/** The formation's hotspots as meta.json has them (round 5 bake). */
function hotspots(stations = 8) {
  const out: { id: string; center: Vec3; size: Vec3 }[] = [{ id: "formation", center: [65, 238, -1195], size: [29.4, 17.8, 29.4] }];
  for (let k = 0; k < stations; k++) {
    const a = (22.5 + 45 * k) * (Math.PI / 180);
    out.push({ id: `arch:${k}`, center: [65 + 29 * Math.cos(a), 227.98, -1195 + 29 * Math.sin(a)], size: [5, 15.95, 5] });
  }
  out.push({ id: "abode", center: [0, 0, 0], size: [1, 1, 1] });
  return out;
}

describe("isFormationLinkBeam", () => {
  it("matches every neon strip and the sky pillar the round 5 bake exported, with their cores", () => {
    for (const name of [
      "formation.light_pillar.column",
      "formation.light_pillar.core",
      "formation.core_feed",
      "formation.core_feed.core",
      "formation.spoke",
      "formation.spoke.7.core",
      "formation.sat_link",
      "formation.sat_link.15.core",
      "formation.cluster_link",
      "formation.cluster_link.0.core",
      "formation.cross_link",
      "formation.cross_link.3.core",
    ]) {
      expect(isFormationLinkBeam(name), name).toBe(true);
    }
  });

  it("leaves the hotspots' objects and other areas' beams alone", () => {
    for (const name of ["formation.core", "formation.pillar.0", "formation.spokes", "forge.spoke", "gate.light_pillar", "formation.brazier.3"]) {
      expect(isFormationLinkBeam(name), name).toBe(false);
    }
  });
});

describe("formationShafts", () => {
  it("rises from the core's centre, then one wisp per array eye, then the halo", () => {
    const s = formationShafts(hotspots());
    expect(s.map((x) => x.kind)).toEqual(["core", ...Array(8).fill("wisp"), "halo"]);
    expect(s[0].base).toEqual([65, 238, -1195]);
    expect(s[9].base).toEqual([65, 238, -1195]);
    expect(s[0].phase).toBe(-1);
    expect(s[0].rest).toBe(1);
  });

  it("starts each wisp at the jade eye, just under the top of its station's box, in the eyes' wave order", () => {
    const hs = hotspots();
    const s = formationShafts(hs).filter((x) => x.kind === "wisp");
    s.forEach((w, k) => {
      const h = hs.find((x) => x.id === `arch:${k}`)!;
      expect(w.base[0]).toBeCloseTo(h.center[0], 6);
      expect(w.base[2]).toBeCloseTo(h.center[2], 6);
      expect(w.base[1]).toBeCloseTo(h.center[1] + h.size[1] / 2 - F.wisp.belowTop, 6);
      expect(w.phase).toBeCloseTo(k / 8, 9);
      expect(w.rest).toBe(F.wisp.rest);
    });
  });

  it("is empty without the formation (the proto profile) and skips missing stations", () => {
    expect(formationShafts([])).toEqual([]);
    expect(formationShafts(hotspots().filter((h) => h.id !== "formation"))).toEqual([]);
    const some = formationShafts(hotspots().filter((h) => h.id !== "arch:3" && h.id !== "arch:6"));
    expect(some.filter((x) => x.kind === "wisp").map((x) => x.phase * 8)).toEqual([0, 1, 2, 4, 5, 7]);
  });
});

describe("shaftProfile", () => {
  const s = F.shaft;

  it("is soft across, with no hard core line", () => {
    const c = shaftProfile(20, 0, s);
    expect(shaftProfile(20, 0.15, s)).toBeGreaterThan(0.9 * c);
    expect(shaftProfile(20, 0.5, s)).toBeGreaterThan(0.45 * c);
    expect(shaftProfile(20, 1.6, s)).toBe(0);
    // Symmetric.
    expect(shaftProfile(20, -0.7, s)).toBeCloseTo(shaftProfile(20, 0.7, s), 12);
  });

  it("fades in above the base, halves about every halfLife metres and is gone by its height", () => {
    expect(shaftProfile(0, 0, s)).toBe(0);
    expect(shaftProfile(s.fadeIn, 0, s)).toBeGreaterThan(0.9);
    expect(shaftProfile(10 + s.halfLife, 0, s) / shaftProfile(10, 0, s)).toBeCloseTo(0.5, 6);
    expect(shaftProfile(s.height, 0, s)).toBe(0);
    expect(shaftProfile(s.height + 50, 0, s)).toBe(0);
    // Monotonic above the fade-in.
    let prev = Infinity;
    for (let h = s.fadeIn; h <= s.height; h += 5) {
      const v = shaftProfile(h, 0, s);
      expect(v).toBeLessThanOrEqual(prev);
      prev = v;
    }
  });

  it("keeps every shaft soft and faint: no laser", () => {
    for (const x of [F.shaft, F.halo, F.wisp]) {
      expect(x.opacity).toBeLessThanOrEqual(0.6);
      expect(x.radius).toBeGreaterThanOrEqual(1);
    }
    expect(F.halo.radius).toBeGreaterThan(F.shaft.radius);
    expect(F.halo.opacity).toBeLessThan(F.shaft.opacity);
  });
});

describe("wispPulse", () => {
  it("rests between waves and peaks as the eyes' wave passes, one station after another", () => {
    const { period, width } = F.wave;
    for (let k = 0; k < 8; k++) {
      const crest = (k / 8 + width / 2) * period;
      expect(wispPulse(crest, k / 8, F.wisp.rest)).toBeCloseTo(1, 6);
      expect(wispPulse(crest + period / 2, k / 8, F.wisp.rest)).toBeCloseTo(F.wisp.rest, 6);
    }
    expect(wispPulse(3, -1, 0.2)).toBe(1);
  });
});

describe("clusterFlames", () => {
  /** A flame: a little cone of points (0.9 m across, 1.2 m tall) standing at `foot`. */
  function flame(foot: Vec3): number[] {
    const out: number[] = [];
    for (let i = 0; i < 24; i++) {
      const a = (i / 24) * Math.PI * 2;
      const y = (i % 4) * 0.4;
      const r = 0.45 * (1 - y / 1.3);
      out.push(foot[0] + r * Math.cos(a), foot[1] + y, foot[2] + r * Math.sin(a));
    }
    return out;
  }

  it("finds one fire per brazier round the array", () => {
    const pts: number[] = [];
    for (let k = 0; k < 8; k++) {
      const a = (22.5 + 45 * k) * (Math.PI / 180);
      pts.push(...flame([65 + 24.6 * Math.cos(a), 222.6, -1195 + 24.6 * Math.sin(a)]));
    }
    const fires = clusterFlames(pts, F.fire.cell);
    expect(fires).toHaveLength(8);
    for (const f of fires) {
      expect(f.count).toBe(24);
      expect(Math.hypot(f.center[0] - 65, f.center[2] + 1195)).toBeCloseTo(24.6, 0);
      expect(f.min[1]).toBeCloseTo(222.6, 6);
      expect(f.max[1] - f.min[1]).toBeCloseTo(1.2, 6);
    }
    // Stable order (by x).
    for (let i = 1; i < fires.length; i++) expect(fires[i].center[0]).toBeGreaterThanOrEqual(fires[i - 1].center[0]);
  });

  it("joins a flame that straddles grid cells, and nothing from nothing", () => {
    expect(clusterFlames(flame([2.49, 0, 2.49]), 2.5)).toHaveLength(1);
    expect(clusterFlames([], 2.5)).toEqual([]);
    expect(clusterFlames([1, 2, 3], 0)).toEqual([]);
  });

  it("gives a brazier's fire a glow of about a metre and a half, within the look's bounds", () => {
    const [f] = clusterFlames(flame([0, 0, 0]), F.fire.cell);
    expect(fireRadius(f)).toBeGreaterThan(0.9);
    expect(fireRadius(f)).toBeLessThanOrEqual(F.fire.radius[1]);
    const candle = clusterFlames([0, 0, 0, 0.05, 0.2, 0], F.fire.cell)[0];
    expect(fireRadius(candle)).toBe(F.fire.radius[0]);
  });
});

describe("the barrier dome", () => {
  it("all but vanishes face-on: at most 0.04 at mid-height whenever the shimmer passes", () => {
    let max = 0;
    for (let t = 0; t < F.dome.ripple.period; t += 0.05) for (let az = -Math.PI; az < Math.PI; az += 0.37) max = Math.max(max, domeAlpha(1, 0.5, t, { az }));
    expect(max).toBeLessThanOrEqual(0.04);
    // And nothing at all between bands.
    expect(domeAlpha(1, 0.5, 0.25 * F.dome.ripple.period)).toBeLessThan(0.002);
  });

  it("shows a thin rim at its silhouette", () => {
    expect(domeAlpha(0, 0.5, 1.3)).toBeGreaterThanOrEqual(0.12);
    expect(domeAlpha(0.5, 0.5, 1.3, { motion: 0 })).toBeLessThan(0.01);
  });

  it("dims the far wall seen through the near one, so from above it is no pale cap", () => {
    for (const [f, h] of [
      [0.1, 0.3],
      [0.4, 0.1],
      [0, 0.8],
    ]) {
      expect(domeAlpha(f, h, 2, { front: false })).toBeCloseTo(F.dome.backFace * domeAlpha(f, h, 2), 12);
    }
    expect(F.dome.backFace).toBeGreaterThan(0.2);
    expect(F.dome.backFace).toBeLessThan(0.8);
  });

  it("lights a seam where it meets the plaza", () => {
    expect(domeAlpha(1, 0, 0, { motion: 0 })).toBeCloseTo(F.dome.seam.gain, 6);
    expect(domeAlpha(1, 0.05, 0, { motion: 0 })).toBeLessThan(0.01);
  });

  it("never returns NaN or Infinity below the plaza (MSAA extrapolation) or at the apex", () => {
    for (const h of [-0.01, -5, -1e9, Number.NaN, 0, 1, 1.2]) {
      for (const f of [0, 0.3, 1, -0.2, 1.5]) {
        const a = domeAlpha(f, h, 3.3, { az: Math.PI });
        expect(Number.isFinite(a), `h ${h} facing ${f}`).toBe(true);
        expect(a).toBeLessThanOrEqual(F.dome.rim.gain + F.dome.seam.gain + 2 * (F.dome.ripple.face + F.dome.ripple.grazing));
      }
    }
  });

  it("slides its shimmer from the top toward the base, two bands half a period apart", () => {
    const p = F.dome.ripple.period;
    // A band's crest is at 1 - t / period: 0.8 at 0.2 periods, 0.7 at 0.3, the other band 0.5 lower.
    expect(rippleBands(0.8, 0.2 * p)).toBeCloseTo(1, 3);
    expect(rippleBands(0.3, 0.2 * p)).toBeCloseTo(1, 3);
    expect(rippleBands(0.7, 0.3 * p)).toBeCloseTo(1, 3);
    expect(rippleBands(0.8, 0.3 * p)).toBeLessThan(0.01);
    expect(rippleBands(0.55, 0.2 * p)).toBeLessThan(0.01);
    // Each band is about `width` of the height wide at half its light.
    expect(rippleBands(0.8 + F.dome.ripple.width / 2, 0.2 * p)).toBeCloseTo(0.5, 2);
    // It fades in at the top and out before the seam.
    expect(rippleBands(0.98, 0.02 * p)).toBeLessThan(0.2);
    expect(rippleBands(0.03, 0.97 * p)).toBeLessThan(0.3);
  });

  it("rests with reduced motion and on the Low tier: rim and seam only", () => {
    for (const t of [0, 1.7, 4.1]) {
      const still = domeAlpha(0.2, 0.4, t, { motion: 0 });
      expect(domeAlpha(0.2, 0.4, t, { detail: 0 })).toBeCloseTo(still, 12);
      expect(still).toBeCloseTo(Math.pow(0.8, F.dome.rim.power) * F.dome.rim.gain + Math.exp(-0.4 * F.dome.seam.sharpness) * F.dome.seam.gain, 12);
    }
  });

  it("closes its lattice round the dome without a seam", () => {
    const n = domeCellsAround();
    expect(Number.isInteger(n)).toBe(true);
    expect((2 * Math.PI * FORMATION_DOME.radius) / n).toBeCloseTo(F.dome.ripple.cell, 0);
    // A band's light just either side of the azimuth wrap matches.
    const t = 0.3 * F.dome.ripple.period;
    expect(domeAlpha(0.3, 0.7, t, { az: Math.PI - 1e-7 })).toBeCloseTo(domeAlpha(0.3, 0.7, t, { az: -Math.PI + 1e-7 }), 4);
  });

  it("has GLSL with the same numbers", () => {
    const g = domeGlsl();
    expect(g).toContain("float sectDomeAlpha( float facing, float h, float t, float az, float detail, float motion )");
    expect(g).toContain("float sectHexDist( vec2 p )");
    expect(g).toContain("max( h, 0.0 )");
    expect(g).toContain("fwidth( hd )");
    expect(g).toContain(`pow( g, ${F.dome.rim.power.toFixed(1)} )`);
  });
});

describe("hexDist", () => {
  it("is 0 at a cell's centre and 0.5 on its edges, the same in every cell", () => {
    expect(hexDist(0.5, 0.5 * Math.sqrt(3))).toBeCloseTo(0, 9);
    expect(hexDist(0, 0)).toBeCloseTo(0, 9);
    expect(hexDist(0.5, 0)).toBeCloseTo(0.5, 9);
    for (const [x, y] of [
      [0.13, 0.41],
      [0.77, 1.2],
      [0.31, 2.9],
    ]) {
      expect(hexDist(x + 1, y)).toBeCloseTo(hexDist(x, y), 9);
      expect(hexDist(x, y + Math.sqrt(3))).toBeCloseTo(hexDist(x, y), 9);
      expect(hexDist(x, y)).toBeLessThanOrEqual(1 / Math.sqrt(3) + 1e-9);
    }
  });
});

describe("formationTier", () => {
  it("draws everything on High, drops the halo and some sparks on Medium, and the shimmer and streaks on Low", () => {
    const hi = formationTier("high"), mid = formationTier("mid"), lo = formationTier("low");
    expect(hi).toEqual({ domeDetail: 1, streaks: 1, halo: true, sparks: F.fire.sparks.high });
    expect(mid.halo).toBe(false);
    expect(mid.domeDetail).toBe(1);
    expect(mid.sparks).toBeLessThan(hi.sparks);
    expect(lo).toEqual({ domeDetail: 0, streaks: 0, halo: false, sparks: F.fire.sparks.low });
    expect(lo.sparks).toBeLessThan(mid.sparks);
  });
});

describe("the formation's palette", () => {
  it("is warm gold, not the old mint: no colour fully saturated", () => {
    for (const hex of [F.dome.color, F.shaft.color, F.halo.color, F.wisp.color, F.coreGlow.color, F.fire.core, F.fire.hot]) {
      const n = parseInt(hex.slice(1), 16);
      const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
      expect(Math.min(...c), hex).toBeGreaterThan(40);
    }
    const dome = parseInt(F.dome.color.slice(1), 16);
    expect((dome >> 16) & 255).toBeGreaterThan(dome & 255);
  });
});
