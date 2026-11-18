/**
 * The night-baked stops seen by day (night-bake.ts): their texels pulled toward the sunset bake the
 * other chunks hold. Reads the installed JSON only (never a baked map's bytes: CI has no Git LFS
 * files).
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { liveIndexFile, parseLiveIndex } from "./live";
import {
  FLAT_UP,
  pullGreen,
  pullNormal,
  SUNSET_DIR,
  SUNSET_PULL,
  SUNSET_PULL_APPLY,
  sunsetPullChunk,
  sunsetPullData,
  sunsetPullGain,
  sunsetPullGlsl,
  sunsetPullLinear,
  type PullChunk,
} from "./night-bake";
import type { Vec3 } from "./types";

const ROOT = path.resolve(__dirname, "../../../public/sect/full");

function readJson(file: string): unknown {
  return JSON.parse(readFileSync(path.join(ROOT, file), "utf8"));
}

function unit(v: Vec3): Vec3 {
  const l = Math.hypot(v[0], v[1], v[2]);
  return [v[0] / l, v[1] / l, v[2] / l];
}

/** A wall facing straight along a light's direction, level (no height). */
function wallToward(d: Vec3): Vec3 {
  return unit([d[0], 0, d[2]]);
}

const CHUNKS = Object.keys(SUNSET_PULL) as PullChunk[];
/** A mid grey stone texel (linear). */
const GREY: Vec3 = [0.2, 0.2, 0.2];

describe("the night-baked stops' pull toward the sunset bake", () => {
  it("pulls toward the scene's own sunset sun, and away from each stop's own key as its live index has it", () => {
    const meta = readJson("meta.json") as { sun: { direction: Vec3 } };
    SUNSET_DIR.forEach((v, i) => expect(v).toBeCloseTo(meta.sun.direction[i], 4));
    expect(CHUNKS.sort()).toEqual(["abode", "summit"]);
    for (const c of CHUNKS) {
      const ix = parseLiveIndex(readJson(liveIndexFile(c)));
      expect(ix, c).not.toBeNull();
      SUNSET_PULL[c].key.forEach((v, i) => expect(v, `${c} key`).toBeCloseTo(ix!.light.sun.dir[i], 4));
    }
  });

  it("takes the two chunks' atlas surfaces only: not their glows, vertex-coloured pieces or trees, nor any other chunk", () => {
    expect(sunsetPullChunk("baked.abode_A0")).toBe("abode");
    expect(sunsetPullChunk("baked.abode_A1.detail.ground")).toBe("abode");
    expect(sunsetPullChunk("baked.abode_A0.detail.tiles.surface.glaze")).toBe("abode");
    expect(sunsetPullChunk("baked.summit_A2.detail.rock")).toBe("summit");
    expect(sunsetPullChunk("baked.summit_A0.surface.metal")).toBe("summit");
    for (const n of ["baked.abode_A0.glow.lantern", "baked.summit_A0.glow.paper_screen_lit", "baked.vc", "baked.vc.surface.metal", "baked.abode_trees_A0", "baked.formation_A0", "baked.scroll_A1.detail.rock", "abode_A0"]) {
      expect(sunsetPullChunk(n), n).toBeNull();
    }
  });

  it("leaves a texel exactly as baked at no pull (the night holds), and pulls it all the way at 1", () => {
    for (const c of CHUNKS) {
      for (const n of [wallToward(SUNSET_DIR), [0, 1, 0] as Vec3, wallToward(SUNSET_PULL[c].key)]) {
        expect(sunsetPullLinear(GREY, n, SUNSET_PULL[c], 0)).toEqual(GREY);
        const g = sunsetPullGain(GREY, n, SUNSET_PULL[c]);
        sunsetPullLinear(GREY, n, SUNSET_PULL[c], 1).forEach((v, i) => expect(v).toBeCloseTo(GREY[i] * g[i], 12));
        // Half way is half the gain's change.
        sunsetPullLinear(GREY, n, SUNSET_PULL[c], 0.5).forEach((v, i) => expect(v).toBeCloseTo(GREY[i] * (1 + (g[i] - 1) / 2), 12));
      }
    }
  });

  it("warms the abode's stone: more red, less blue, whichever way it faces", () => {
    for (const n of [wallToward(SUNSET_DIR), [0, 1, 0] as Vec3, wallToward([1, 0, 0])]) {
      const g = sunsetPullGain(GREY, n, SUNSET_PULL.abode);
      expect(g[0]).toBeGreaterThan(1.5);
      expect(g[2]).toBeLessThan(1);
      expect(g[0]).toBeGreaterThan(g[1]);
    }
  });

  it("lights the summit's sunset side warm and brighter, and dims the side its moon lit", () => {
    const sunSide = sunsetPullGain(GREY, wallToward(SUNSET_DIR), SUNSET_PULL.summit);
    const moonSide = sunsetPullGain(GREY, wallToward(SUNSET_PULL.summit.key), SUNSET_PULL.summit);
    // The side the moon left dark was the sunlit one: much brighter, and warm (red over blue).
    expect(sunSide[0]).toBeGreaterThan(5);
    expect(sunSide[0] / sunSide[2]).toBeGreaterThan(2);
    // The side the moon lit was in the sunset's shade.
    expect(moonSide.every((v) => v < 1)).toBe(true);
    // The gain stays finite and bounded whatever the face.
    for (let a = 0; a < 360; a += 15) {
      for (const y of [-1, -0.5, 0, 0.5, 0.9, 1]) {
        const h = Math.sqrt(1 - y * y);
        const n: Vec3 = [Math.cos((a * Math.PI) / 180) * h, y, Math.sin((a * Math.PI) / 180) * h];
        for (const c of CHUNKS) {
          for (const v of sunsetPullGain(GREY, n, SUNSET_PULL[c])) {
            expect(v).toBeGreaterThan(0);
            expect(v).toBeLessThan(150);
          }
        }
      }
    }
  });

  it("gives the summit's grass more green than its stone (the sunset lit lawns yellow-green)", () => {
    const grass: Vec3 = [0.03, 0.06, 0.03];
    expect(pullGreen(GREY)).toBe(0);
    expect(pullGreen([0.3, 0.2, 0.1])).toBe(0);
    expect(pullGreen(grass)).toBe(1);
    const up: Vec3 = [0, 1, 0];
    const stone = sunsetPullGain(GREY, up, SUNSET_PULL.summit);
    const lawn = sunsetPullGain(grass, up, SUNSET_PULL.summit);
    expect(lawn[1] / stone[1]).toBeGreaterThan(1.5);
    expect(lawn[2] / stone[2]).toBeLessThan(1);
    // The abode's single gain does not look at the colour.
    expect(sunsetPullGain(grass, up, SUNSET_PULL.abode)).toEqual(sunsetPullGain(GREY, up, SUNSET_PULL.abode));
  });

  it("counts gentle slopes as level ground, so a lawn's flat faces take one tint (no facets)", () => {
    const tilt = (deg: number, az: number): Vec3 => {
      const t = (deg * Math.PI) / 180;
      const z = (az * Math.PI) / 180;
      return [Math.sin(t) * Math.cos(z), Math.cos(t), Math.sin(t) * Math.sin(z)];
    };
    const level = sunsetPullGain(GREY, [0, 1, 0], SUNSET_PULL.summit);
    for (const deg of [0, 10, 20, 30]) {
      for (const az of [0, 90, 180, 270]) {
        expect(Math.cos((deg * Math.PI) / 180)).toBeGreaterThanOrEqual(FLAT_UP[1]);
        sunsetPullGain(GREY, tilt(deg, az), SUNSET_PULL.summit).forEach((v, i) => expect(v).toBeCloseTo(level[i], 9));
      }
    }
    // A cliff keeps its own normal.
    const wall = wallToward(SUNSET_DIR);
    pullNormal(wall).forEach((v, i) => expect(v).toBeCloseTo(wall[i], 12));
    // In between it turns smoothly, and always comes back unit length.
    for (let y = 0.5; y <= 0.95; y += 0.05) {
      const m = pullNormal(unit([Math.sqrt(1 - y * y), y, 0]));
      expect(Math.hypot(...m)).toBeCloseTo(1, 12);
      expect(m[1]).toBeGreaterThanOrEqual(y - 1e-12);
    }
  });

  it("packs a chunk's terms as the shader reads them, and the shader runs only while it pulls", () => {
    const p = SUNSET_PULL.summit;
    const d = sunsetPullData(p);
    expect(d.length).toBe(24);
    [p.base, p.sunset, p.own, p.up, p.green, p.key].forEach((v, k) => v.forEach((x, i) => expect(d[k * 4 + i]).toBeCloseTo(x, 6)));
    const src = sunsetPullGlsl();
    expect(src).toContain("uniform vec4 uSectPull[ 6 ];");
    expect(src).toContain("uniform float uSectPullAmount;");
    expect(src).toContain("vec3 sectSunsetPull( vec3 c, vec3 wp )");
    expect(src).toContain("dFdx( wp )");
    // A uniform test around the call: the derivatives stay in uniform control flow, and at no pull
    // nothing runs (the night holds are exactly as before).
    expect(SUNSET_PULL_APPLY).toContain("if ( uSectPullAmount > 0.0 )");
  });
});
