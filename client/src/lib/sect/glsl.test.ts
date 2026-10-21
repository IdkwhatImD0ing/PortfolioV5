import { describe, expect, it } from "vitest";
import {
  aerialColor,
  aerialFar,
  DITHER_GLSL,
  ditherNoise,
  fogChunks,
  fogConstantsFromMeta,
  fogDefines,
  fogLibrary,
  hazeColor,
  hazeLayerDepth,
  hazeOpticalDepth,
  mistOpticalDepth,
  SCREEN_ADD_GLSL,
  screenAdd,
  SCREEN_CLIP,
  SCREEN_CLIP_GLSL,
  screenClip,
  type FogConstants,
} from "./glsl";
import { parseMeta } from "./parse";
import type { Vec3 } from "./types";

const luma = (c: Vec3) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];

function norm(v: Vec3): Vec3 {
  const l = Math.hypot(v[0], v[1], v[2]);
  return [v[0] / l, v[1] / l, v[2] / l];
}

const plain = fogConstantsFromMeta(parseMeta({}));
const sun = norm(plain.sunDir);
const away = norm([-sun[0], 0, -sun[2]]);
const across = norm([sun[2], 0, -sun[0]]);
const base: Vec3 = [0.578, 0.42, 0.352];

/** The fog before aerial perspective: one grey veil toward the sun-tinted haze colour. */
function oldFog(c: FogConstants, col: Vec3, rd: Vec3, od: number): Vec3 {
  const mu = rd[0] * c.sunDir[0] + rd[1] * c.sunDir[1] + rd[2] * c.sunDir[2];
  const s = Math.pow(mu * 0.5 + 0.5, 3) * c.sunFogMix;
  const v = 1 - Math.exp(-od);
  return col.map((x, i) => {
    const h = base[i] + (c.sunFogColor[i] - base[i]) * s;
    return x + (h - x) * v;
  }) as Vec3;
}

const lavender: Vec3 = [1.0, 0.95, 1.5];
const aerial: FogConstants = {
  ...plain,
  extinction: [0.75, 1.05, 1.6],
  coolTint: lavender.map((v) => v / luma(lavender)) as Vec3,
  coolMix: 0.6,
  desaturate: 0.4,
  aerialDepth: 0.35,
  mistDensity: 0.001,
  mistFalloff: 45,
  mistStart: 150,
};

describe("aerial perspective", () => {
  it("is the old grey veil at the defaults (nothing changes until the look turns it on)", () => {
    const rock: Vec3 = [0.2, 0.15, 0.1];
    for (const rd of [sun, away, across, norm([0.3, -0.4, 0.8])]) {
      for (const od of [0, 0.05, 0.4, 2, 9]) {
        const a = aerialColor(plain, rock, base, rd, od);
        const b = oldFog(plain, rock, rd, od);
        a.forEach((v, i) => expect(v).toBeCloseTo(b[i], 9));
      }
    }
  });

  it("leaves thin haze (the scenery at hand) within about a tenth of an 8-bit step", () => {
    const dark: Vec3 = [0.03, 0.04, 0.025];
    const a = aerialColor(aerial, dark, base, away, 0.035);
    const b = oldFog(aerial, dark, away, 0.035);
    a.forEach((v, i) => expect(Math.abs(v - b[i])).toBeLessThan(0.0015));
  });

  it("turns far ridges bluer and paler, never darker", () => {
    const rock: Vec3 = [0.12, 0.09, 0.06];
    for (const od of [0.4, 0.8, 1.5]) {
      const a = aerialColor(aerial, rock, base, away, od);
      const b = oldFog(aerial, rock, away, od);
      expect(a[2] / a[0]).toBeGreaterThan((b[2] / b[0]) * 1.05);
      expect(luma(a)).toBeGreaterThan(luma(b) * 0.97);
    }
  });

  it("fades the far surface's own colour toward the haze's hue", () => {
    const red: Vec3 = [0.5, 0.05, 0.04];
    const sat = (c: Vec3) => (Math.max(...c) - Math.min(...c)) / Math.max(...c);
    const withDesat = aerialColor(aerial, red, base, across, 0.6);
    const without = aerialColor({ ...aerial, desaturate: 0 }, red, base, across, 0.6);
    expect(sat(withDesat)).toBeLessThan(sat(without));
  });

  it("converges on the deep-distance haze colour the sky uses", () => {
    const a = aerialColor(aerial, [0.1, 0.2, 0.05], base, away, 60);
    const h = hazeColor(aerial, base, away);
    a.forEach((v, i) => expect(v).toBeCloseTo(h[i], 6));
  });

  it("brings the shifts in smoothly with depth", () => {
    expect(aerialFar(aerial, 0)).toBe(0);
    expect(aerialFar(aerial, aerial.aerialDepth)).toBeCloseTo(1 - Math.exp(-1), 9);
    let prev = -1;
    for (let od = 0; od < 4; od += 0.05) {
      const g = aerialColor(aerial, [0.1, 0.1, 0.1], base, away, od)[1];
      expect(g).toBeGreaterThan(prev);
      prev = g;
    }
  });
});

describe("haze colour", () => {
  it("cools away from the sun at the same brightness, and not at all toward it", () => {
    const warm = hazeColor(plain, base, away);
    const cool = hazeColor(aerial, base, away);
    expect(luma(cool)).toBeCloseTo(luma(warm), 9);
    expect(cool[2] / cool[0]).toBeGreaterThan(warm[2] / warm[0]);
    hazeColor(aerial, base, sun).forEach((v, i) => expect(v).toBeCloseTo(hazeColor(plain, base, sun)[i], 9));
  });

  it("changes smoothly all the way round (no seam between the warm and cool sides)", () => {
    let prev = hazeColor(aerial, base, sun);
    for (let a = 0.02; a <= Math.PI; a += 0.02) {
      const rd = norm([sun[0] * Math.cos(a) + across[0] * Math.sin(a), sun[1] * Math.cos(a), sun[2] * Math.cos(a) + across[2] * Math.sin(a)]);
      const c = hazeColor(aerial, base, rd);
      c.forEach((v, i) => expect(Math.abs(v - prev[i])).toBeLessThan(0.02));
      prev = c;
    }
  });
});

describe("valley mist", () => {
  it("is off at the defaults", () => {
    expect(mistOpticalDepth(plain, 20, -0.1, 2000)).toBe(0);
    expect(hazeOpticalDepth(plain, 20, -0.1, 2000)).toBe(hazeLayerDepth(plain, 20, -0.1, 2000));
  });

  it("starts mistStart metres out, so the scenery at hand never mists", () => {
    expect(mistOpticalDepth(aerial, 30, 0, aerial.mistStart)).toBe(0);
    expect(mistOpticalDepth(aerial, 30, 0, aerial.mistStart + 1)).toBeGreaterThan(0);
    expect(mistOpticalDepth(aerial, 30, 0, aerial.mistStart + 1)).toBeLessThan(0.002);
  });

  it("lies low: thick over the cloud layer, gone at terrace height", () => {
    const low = mistOpticalDepth(aerial, aerial.mistBaseY + 10, 0, 1000);
    const high = mistOpticalDepth(aerial, aerial.mistBaseY + 300, 0, 1000);
    expect(low).toBeGreaterThan(0.3);
    expect(high).toBeLessThan(low * 1e-2);
    // Looking down from high up into a gorge it gathers near the floor.
    expect(mistOpticalDepth(aerial, 300, -0.3, 900)).toBeGreaterThan(mistOpticalDepth(aerial, 300, -0.3, 500) * 5);
  });

  it("stops where the ray sinks into the cloud layer (no runaway below it)", () => {
    const y0 = 200;
    const dy = -0.2;
    const toBase = (y0 - aerial.mistBaseY) / -dy;
    const atBase = mistOpticalDepth(aerial, y0, dy, toBase);
    expect(mistOpticalDepth(aerial, y0, dy, toBase + 500)).toBeCloseTo(atBase, 9);
    expect(Number.isFinite(mistOpticalDepth(aerial, y0, -1, 1e7))).toBe(true);
  });

  it("adds to the haze in every shader's sectHazeDepth", () => {
    expect(hazeOpticalDepth(aerial, 40, -0.05, 1500)).toBeCloseTo(
      hazeLayerDepth(aerial, 40, -0.05, 1500) + mistOpticalDepth(aerial, 40, -0.05, 1500),
      12,
    );
    expect(fogLibrary(aerial)).toMatch(/float sectHazeDepth\( float y0, float dy, float t \) \{\s*return sectHazeLayerDepth\( y0, dy, t \) \+ sectMistDepth\( y0, dy, t \);/);
  });
});

describe("dither", () => {
  it("is triangular noise in -1..1 with a zero mean", () => {
    let sum = 0;
    let inner = 0;
    const n = 256 * 256;
    for (let y = 0; y < 256; y++) {
      for (let x = 0; x < 256; x++) {
        const v = ditherNoise(x + 0.5, y + 0.5);
        expect(Math.abs(v)).toBeLessThan(1);
        sum += v;
        if (Math.abs(v) < 0.5) inner++;
      }
    }
    expect(Math.abs(sum / n)).toBeLessThan(0.02);
    // A triangle puts 75% of its mass within half its reach (a flat spread would put 50%).
    expect(inner / n).toBeGreaterThan(0.7);
    expect(inner / n).toBeLessThan(0.8);
  });

  it("ships the GLSL the post pass and the low tier share", () => {
    expect(DITHER_GLSL).toContain("float sectDitherNoise( vec2 p )");
    expect(DITHER_GLSL).toContain("vec3 sectSrgbEncode( vec3 c )");
    expect(DITHER_GLSL).toContain("vec3 sectSrgbDecode( vec3 c )");
    expect(DITHER_GLSL).not.toContain("gl_FragCoord");
  });
});

describe("fog GLSL", () => {
  it("defines every constant the functions use, and the mist switch only when it is on", () => {
    const d = fogDefines(aerial);
    for (const name of ["SECT_EXTINCTION", "SECT_COOL_TINT", "SECT_COOL_MIX", "SECT_DESATURATE", "SECT_AERIAL_DEPTH", "SECT_MIST_DENSITY", "SECT_DITHER", "SECT_LUMA"]) {
      expect(d).toContain(`#define ${name} `);
    }
    expect(d).toMatch(/^#define SECT_MIST$/m);
    expect(fogDefines(plain)).not.toMatch(/^#define SECT_MIST$/m);
    expect(d).not.toMatch(/NaN|undefined|Infinity/);
    const used = new Set([...fogLibrary(aerial).matchAll(/\bSECT_[A-Z_]+\b/g)].map((m) => m[0]));
    for (const name of used) expect(d).toMatch(new RegExp(`#define ${name}\\b`));
  });

  it("fogs surfaces with sectAerial, in linear even when three has already encoded to sRGB", () => {
    const f = fogChunks(aerial).fog_fragment;
    expect(f).toContain("sectAerial( sectC, sectBase, sectRd, sectHazeDepth(");
    expect(f).toContain("linearToOutputTexel( vec4( 0.5 ) )");
    expect(f).toContain("sectSrgbDecode( gl_FragColor.rgb )");
    expect(f).toContain("sectSrgbDecode( fogColor )");
    expect(f).toContain("sectDitherEncoded( sectSrgbEncode( sectScreenClip( sectC ) ), gl_FragCoord.xy )");
  });

  it("puts the cloud layer under the haze: cloud first (the far end of the ray), then the air in front", () => {
    const f = fogChunks(aerial).fog_fragment;
    const cloud = f.indexOf("SECT_CLOUD_FOG, 1.0 - exp( - sectCloudDepth(");
    const haze = f.indexOf("sectAerial( sectC, sectBase");
    expect(cloud).toBeGreaterThan(0);
    expect(haze).toBeGreaterThan(cloud);
  });

  it("keeps the functions custom shaders call", () => {
    const lib = fogLibrary(aerial);
    for (const fn of ["float sectHazeDepth(", "float sectCloudDepth(", "vec3 sectHazeColor( vec3 base, vec3 rd )", "vec3 sectAerial("]) {
      expect(lib).toContain(fn);
    }
  });
});

describe("screen clip (the Low tier's direct-to-screen path)", () => {
  const max = (c: Vec3) => Math.max(c[0], c[1], c[2]);
  const hue = (c: Vec3) => {
    const m = max(c);
    return c.map((v) => v / m);
  };

  it("leaves everything up to the knee as it is", () => {
    for (const c of [[0, 0, 0], [0.2, 0.5, 0.1], [0.9, 0.9, 0.9], [SCREEN_CLIP.knee, 0.3, 0.1]] as Vec3[]) {
      expect(screenClip(c)).toEqual(c);
    }
  });

  it("never goes past 1 and keeps a glow's hue where the screen would clip it white", () => {
    // The forge's cyan item ring: baked cyan times its glow factor, over 1 in every channel.
    const ring: Vec3 = [1.3, 2.6, 2.9];
    const out = screenClip(ring);
    expect(max(out)).toBeLessThanOrEqual(1);
    expect(max(out)).toBeGreaterThan(0.99);
    // Per-channel clipping would give white (1, 1, 1); the clip keeps red well under blue.
    expect(out[0] / out[2]).toBeCloseTo(ring[0] / ring[2], 1);
    const h = hue(out);
    const h0 = hue(ring);
    for (let i = 0; i < 3; i++) expect(Math.abs(h[i] - h0[i])).toBeLessThan(0.03);
  });

  it("rolls off smoothly: brighter in, brighter out, no step at the knee", () => {
    let last = 0;
    for (let m = 0.5; m < 20; m *= 1.07) {
      const out = max(screenClip([m, m * 0.5, m * 0.2]));
      expect(out).toBeGreaterThanOrEqual(last - 1e-12);
      last = out;
    }
    const k = SCREEN_CLIP.knee;
    expect(max(screenClip([k + 1e-4, 0, 0]))).toBeCloseTo(k + 1e-4, 4);
    // A lit white surface barely moves (1.0 lands at about 0.96).
    expect(screenClip([1, 1, 1])[0]).toBeGreaterThan(0.95);
  });

  it("lets only very hot cores drift toward white, as the post pass's clip does", () => {
    const warm = screenClip([1.5, 0.75, 0.3]);
    expect(warm[2] / warm[0]).toBeCloseTo(0.2, 2);
    const hot = screenClip([30, 15, 6]);
    expect(hot[2] / hot[0]).toBeGreaterThan(0.5);
    expect(hot[2] / hot[0]).toBeLessThan(0.7);
  });

  it("has GLSL with the same constants, in the fog library", () => {
    expect(SCREEN_CLIP_GLSL).toContain("vec3 sectScreenClip( vec3 c )");
    for (const v of [SCREEN_CLIP.knee, SCREEN_CLIP.whiteFrom, SCREEN_CLIP.whiteTo, SCREEN_CLIP.white]) {
      expect(SCREEN_CLIP_GLSL).toContain(String(v));
    }
    expect(SCREEN_CLIP_GLSL).not.toMatch(/NaN|undefined/);
    expect(fogLibrary(aerial)).toContain("vec3 sectScreenClip( vec3 c )");
  });
});

describe("screen add (additive light on the Low tier)", () => {
  const enc = (v: number) => (v <= 0.0031308 ? v * 12.92 : 1.055 * Math.pow(v, 1 / 2.4) - 0.055);

  it("adds what High shows: the encoded step over the background, not the raw light", () => {
    const back = 0.3;
    const l: Vec3 = [0.1, 0.1, 0.1];
    const step = screenAdd(l, back);
    for (const v of step) expect(v).toBeCloseTo(enc(back + 0.1) - enc(back), 9);
    // Over a bright sky the sRGB curve is flat: less than the raw light (which Low used to add).
    expect(step[0]).toBeLessThan(0.1);
    expect(screenAdd([0, 0, 0], back)).toEqual([0, 0, 0]);
  });

  it("never pushes the sum past white, and keeps the light's hue", () => {
    const back = 0.3;
    const hot = screenAdd([4, 2, 1], back);
    for (const v of hot) expect(enc(back) + v).toBeLessThanOrEqual(1 + 1e-9);
    expect(hot[0]).toBeGreaterThan(hot[1]);
    expect(hot[1]).toBeGreaterThan(hot[2]);
  });

  it("has GLSL that leaves the composer's linear path alone", () => {
    expect(SCREEN_ADD_GLSL).toContain("vec3 sectScreenAdd( vec3 l, float back )");
    expect(SCREEN_ADD_GLSL).toContain("if ( linearToOutputTexel( vec4( 0.5 ) ).r <= 0.6 ) return l;");
    expect(SCREEN_ADD_GLSL).toContain("sectScreenClip(");
  });
});
