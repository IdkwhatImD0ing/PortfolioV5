import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { packPuffs, PUFF_STRIDE, supportRadius } from "./clouds";
import { parseClouds } from "./parse";
import { isSteamPuff, RANGE_LOOK } from "./range-look";
import {
  STEAM_BRANCH,
  STEAM_HIDE_STATEMENT,
  STEAM_NL_PER_HEIGHT,
  STEAM_NL_WRAP,
  STEAM_NW_PER_METRE,
  steamChurnStatement,
  steamClimbStatement,
  steamLoop,
  steamPhase,
  steamRise,
  steamShare,
  steamVertexGlsl,
  steamVertexStatements,
  steamWind,
} from "./steam";
import type { CloudPuff, Vec3 } from "./types";

const st = RANGE_LOOK.steam;
const keep = RANGE_LOOK.mist.keep;

/** An untagged round puff over Ice-Fire Island (in the keep zone) with vertical half-extent hy. */
const steamPuff = (hy: number, dx = 5, y = keep.aboveY + 20): CloudPuff => ({
  c: [keep.xz[0] + dx, y, keep.xz[1]],
  axes: [
    [hy, 0, 0],
    [0, hy, 0],
    [0, 0, hy],
  ],
  density: 1.2,
});

describe("steam rise span", () => {
  it("is the puff's vertical half-extent times span, held to spanM, for steam only", () => {
    expect(steamRise(steamPuff(3))).toBeCloseTo(3 * st.span, 9);
    // Small puffs get the shortest loop, big ones the longest.
    expect(steamRise(steamPuff(1))).toBe(st.spanM[0]);
    expect(steamRise(steamPuff(7.9))).toBe(st.spanM[1]);
    // Not steam: tagged mist there, a big bank there, a small puff elsewhere.
    expect(steamRise({ ...steamPuff(3), kind: "mist.isle" })).toBe(0);
    expect(steamRise(steamPuff(20))).toBe(0);
    expect(steamRise(steamPuff(3, 200))).toBe(0);
    expect(steamRise(steamPuff(3, 5, keep.aboveY - 5))).toBe(0);
  });

  it("measures the vertical half-extent of a tilted puff, not its largest axis", () => {
    const p: CloudPuff = { ...steamPuff(1), axes: [[3, 0, 0], [0, 2, 0], [0, 0, 1]] };
    expect(steamRise(p)).toBeCloseTo(Math.max(st.spanM[0], Math.min(st.spanM[1], st.span * supportRadius(p.axes, [0, 1, 0]))), 9);
  });

  it("keeps a copy near its place: the loop is at most about one and a half half-heights", () => {
    // A long loop sent copies past their neighbours, and the plume broke into balls (2026-11-15).
    expect(st.span).toBeLessThanOrEqual(1.6);
    expect(st.spanM[1]).toBeLessThanOrEqual(8);
    expect(st.grow[0]).toBeGreaterThanOrEqual(0.85);
    expect(st.grow[1]).toBeLessThanOrEqual(1.2);
  });
});

describe("steam loop", () => {
  /** Distance between two loop positions, round the loop (0.999 is next to 0). */
  const apart = (a: number, b: number) => Math.min(Math.abs(a - b), 1 - Math.abs(a - b));

  it("wraps the phase once per span / speed seconds, from the puff's own phase", () => {
    const rise = 6;
    const period = rise / st.speed;
    for (const phase of [0, 0.3, 0.97]) {
      expect(apart(steamLoop(0, rise, phase).s, phase)).toBeLessThan(1e-12);
      expect(apart(steamLoop(period, rise, phase).s, phase)).toBeLessThan(1e-9);
      expect(apart(steamLoop(period * 3, rise, phase).s, phase)).toBeLessThan(1e-9);
      expect(apart(steamLoop(period * 0.25, rise, phase).s, (phase + 0.25) % 1)).toBeLessThan(1e-9);
      for (let t = 0; t < 40; t += 0.37) {
        const s = steamLoop(t, rise, phase).s;
        expect(s).toBeGreaterThanOrEqual(0);
        expect(s).toBeLessThan(1);
      }
    }
  });

  it("puts the second copy (its span negated) half a loop on, at the same pace", () => {
    for (const phase of [0, 0.3, 0.97]) {
      for (let t = 0; t < 30; t += 0.41) {
        const a = steamLoop(t, 5, phase);
        const b = steamLoop(t, -5, phase);
        expect(apart(b.s, (a.s + 0.5) % 1)).toBeLessThan(1e-9);
      }
    }
  });

  it("climbs at speed, drifting downwind, and grows from grow[0] to grow[1]", () => {
    const rise = 6;
    for (const r of [rise, -rise]) {
      // Half a loop apart, the copies wrap at different moments: pick a second where neither does.
      const a = steamLoop(1, r, 0.1);
      const b = steamLoop(1.5, r, 0.1);
      expect(b.s).toBeGreaterThan(a.s);
      expect(b.offset[1] - a.offset[1]).toBeCloseTo(st.speed * 0.5, 9);
      const [wx, wz] = steamWind();
      expect(Math.hypot(wx, wz)).toBeCloseTo(1, 12);
      expect(b.offset[0] - a.offset[0]).toBeCloseTo(st.speed * 0.5 * st.drift * wx, 9);
      expect(b.offset[2] - a.offset[2]).toBeCloseTo(st.speed * 0.5 * st.drift * wz, 9);
    }
    expect(steamLoop(0, rise, 0).grow).toBeCloseTo(st.grow[0], 12);
    expect(steamLoop(0, rise, 0.999999).grow).toBeCloseTo(st.grow[1], 5);
    expect(steamLoop(0, -rise, 0.499999).grow).toBeCloseTo(st.grow[1], 5);
  });

  it("never leaves its span: half of it below its place to half above", () => {
    for (const rise of [st.spanM[0], 4.3, st.spanM[1]]) {
      for (const r of [rise, -rise]) {
        for (let t = 0; t < 30; t += 0.05) {
          const up = steamLoop(t, r, 0.42).offset[1];
          expect(up).toBeGreaterThanOrEqual(-rise / 2);
          expect(up).toBeLessThan(rise / 2);
        }
      }
    }
  });

  it("gives a copy nothing at both ends of its loop, so its jump back down never shows", () => {
    expect(steamShare(0)).toBe(0);
    expect(steamShare(1)).toBeLessThan(1e-30);
    expect(steamShare(1e-3)).toBeLessThan(1e-4);
    expect(steamShare(1 - 1e-3)).toBeLessThan(1e-4);
    expect(steamShare(0.5)).toBe(1);
    expect(steamLoop(0, 6, 0).density).toBe(0);
    // Just before and just after the wrap the copy is all but gone.
    const period = 6 / st.speed;
    expect(steamLoop(period - 1e-3, 6, 0).density).toBeLessThan(1e-5);
    expect(steamLoop(period + 1e-3, 6, 0).density).toBeLessThan(1e-5);
  });

  it("shares the puff's whole density between its two copies at every moment, so its place is never empty", () => {
    for (const rise of [st.spanM[0], 4.3, st.spanM[1]]) {
      for (const phase of [0, 0.21, 0.5, 0.88]) {
        for (let t = 0; t < 40; t += 0.033) {
          const sum = steamLoop(t, rise, phase).density + steamLoop(t, -rise, phase).density;
          expect(sum).toBeCloseTo(1, 9);
        }
      }
    }
    // One copy alone averages a half over its loop.
    const n = 20000;
    let d = 0;
    for (let i = 0; i < n; i++) d += steamLoop(((i + 0.5) / n) * (5.5 / st.speed), 5.5, 0.77).density;
    expect(d / n).toBeCloseTo(0.5, 6);
  });

  it("leaves a puff that is not steam alone", () => {
    expect(steamLoop(12.3, 0, 0.5)).toEqual({ s: 0, offset: [0, 0, 0], grow: 1, density: 1 });
    expect(steamLoop(12.3, Number.NaN, 0.5)).toEqual({ s: 0, offset: [0, 0, 0], grow: 1, density: 1 });
  });

  it("gives each puff its own phase from its centre", () => {
    expect(steamPhase([313, 298.7, -993])).toBe(steamPhase([313, 298.7, -993]));
    expect(steamPhase([313, 298.7, -993])).not.toBeCloseTo(steamPhase([312.7, 300.4, -992.7]), 2);
    for (const c of [[0, 0, 0], [327.4, 283.1, -986.6], [-1e3, 50, 2e3]] as Vec3[]) {
      const p = steamPhase(c);
      expect(p).toBeGreaterThanOrEqual(0);
      expect(p).toBeLessThan(1);
    }
  });
});

describe("steam GLSL", () => {
  it("mirrors steamLoop and steamPhase", () => {
    expect(steamVertexGlsl()).toContain("float sectSteamHash( vec3 p )");
    expect(steamVertexGlsl()).toContain("p += dot( p, p.zyx + 31.32 );");
    // Both copies take the branch; a puff that is not steam (iRise 0) never does.
    expect(STEAM_BRANCH).toBe("if ( iRise != 0.0 && uSteam > 0.5 ) {");
    const v = steamVertexStatements();
    expect(v).toContain("float steamSpan = abs( iRise );");
    expect(v).toContain("float steamS = fract( sectSteamHash( iCenter ) + ( iRise < 0.0 ? 0.5 : 0.0 ) + uTime * 1.3000000 / steamSpan );");
    expect(v).toContain("float steamUp = ( steamS - 0.5 ) * steamSpan;");
    expect(v).toContain("puffC += vec3( ");
    expect(v).toContain(`float steamGrow = mix( ${st.grow[0].toPrecision(8)}, ${st.grow[1].toPrecision(8)}, steamS );`);
    expect(v).toContain("puffA0 *= steamGrow;");
    expect(v).toContain("float steamShare = sin( 3.1415927 * steamS );");
    expect(v).toContain("puffD *= steamShare * steamShare;");
    expect(v).toContain("vSteam = 1.0;");
  });

  it("hides the second copy while the steam stands still, so the first alone is the still puff", () => {
    expect(STEAM_HIDE_STATEMENT).toBe("  if ( iRise < 0.0 && uSteam < 0.5 ) vFade = 0.0;");
  });

  it("raises the world noise inside a steam sprite at the copies' speed", () => {
    expect(STEAM_NW_PER_METRE).toBe(1.35);
    expect(steamClimbStatement()).toBe(`  if ( vSteam > 0.5 ) nw.y -= uTime * ${(st.speed * 1.35).toPrecision(8)};`);
  });

  it("slides the sprite's own noise at churn sprite heights a second, wrapping where the texture tiles", () => {
    expect(STEAM_NL_PER_HEIGHT).toBeCloseTo(2 * 1.9, 12);
    // Read at nl x 0.5 and nl x 1.3 from a texture that tiles at 1: the wrap is whole tiles.
    expect(Number.isInteger(STEAM_NL_WRAP * 0.5)).toBe(true);
    expect(Math.abs(STEAM_NL_WRAP * 1.3 - Math.round(STEAM_NL_WRAP * 1.3))).toBeLessThan(1e-9);
    expect(steamChurnStatement()).toBe(`  if ( vSteam > 0.5 ) nl.y -= mod( uTime * ${(st.churn * 3.8).toPrecision(8)}, 10.0 );`);
  });
});

/** The installed clouds.json's steam (a normal file, so this runs on CI too). */
describe("installed steam rises", () => {
  const file = path.resolve(__dirname, "../../../public/sect/full/clouds.json");
  const load = () => (existsSync(file) ? parseClouds(JSON.parse(readFileSync(file, "utf8"))) : null);

  it("packs the 15 steam puffs twice (span 2-7 m, then negated) and every other puff once with 0", () => {
    const puffs = load();
    if (!puffs) return;
    const packed = packPuffs(puffs, [], 0, undefined, (p) => steamRise(p));
    expect(packed.length).toBe((puffs.length + 15) * PUFF_STRIDE);
    let o = 0;
    let n = 0;
    for (const p of puffs) {
      const rise = packed[o + 13];
      // Its place and density are where they were.
      expect(packed[o + 1]).toBeCloseTo(p.c[1], 3);
      expect(packed[o + 12]).toBeCloseTo(p.density, 5);
      o += PUFF_STRIDE;
      if (isSteamPuff(p)) {
        n++;
        expect(rise).toBeGreaterThanOrEqual(st.spanM[0]);
        expect(rise).toBeLessThanOrEqual(st.spanM[1]);
        expect(Array.from(packed.slice(o, o + 13))).toEqual(Array.from(packed.slice(o - PUFF_STRIDE, o - 1)));
        expect(packed[o + 13]).toBe(-rise);
        o += PUFF_STRIDE;
      } else {
        expect(rise).toBe(0);
      }
    }
    expect(o).toBe(packed.length);
    expect(n).toBe(15);
  });

  /**
   * How opaque the plume is along its height (the shader's optical depth through each copy's middle,
   * with its noise at the middle of its range), summed over the steam's copies at time t.
   */
  const profile = (steam: CloudPuff[], t: number | null): number[] => {
    const out: number[] = [];
    for (let y = 280; y <= 332; y += 0.5) {
      let tau = 0;
      for (const p of steam) {
        const hy = supportRadius(p.axes, [0, 1, 0]);
        const hf = supportRadius(p.axes, [1, 0, 0]);
        const rise = steamRise(p);
        const copies = t === null ? [{ offset: [0, 0, 0], grow: 1, density: 1 }] : [rise, -rise].map((r) => steamLoop(t, r, steamPhase(p.c)));
        for (const c of copies) {
          const q = (y - p.c[1] - c.offset[1]) / (hy * c.grow);
          if (q * q < 1) tau += p.density * c.density * 2 * hf * c.grow * Math.sqrt(1 - q * q);
        }
      }
      out.push(1 - Math.exp(-0.27 * tau));
    }
    return out;
  };

  it("stays one plume: no gap opens inside it and it never pumps (the first loop broke it into balls)", () => {
    const puffs = load();
    if (!puffs) return;
    const steam = puffs.filter((p) => isSteamPuff(p));
    const still = profile(steam, null);
    // Inside the plume: where the still plume is solid, at least 2 m from where it thins out.
    const solid = (k: number) => [-4, -3, -2, -1, 0, 1, 2, 3, 4].every((d) => (still[k + d] ?? 0) >= 0.5);
    const inside = still.map((a, k) => (a >= 0.75 && solid(k) ? k : -1)).filter((k) => k >= 0);
    expect(inside.length).toBeGreaterThan(40);
    let lo = Infinity;
    let meanLo = Infinity;
    let meanHi = 0;
    for (let t = 0; t < 120; t += 0.05) {
      const a = profile(steam, t);
      let sum = 0;
      for (const k of inside) {
        lo = Math.min(lo, a[k]);
        sum += a[k] / still[k];
      }
      meanLo = Math.min(meanLo, sum / inside.length);
      meanHi = Math.max(meanHi, sum / inside.length);
    }
    // The still plume is at least 0.76 opaque inside; the moving one stays above 0.6 there (the first
    // loop opened gaps down to 0 and thinned the plume to 0.65 of itself on average at moments).
    expect(lo).toBeGreaterThan(0.55);
    expect(meanLo).toBeGreaterThan(0.95);
    expect(meanHi).toBeLessThan(1.06);
  });
});
