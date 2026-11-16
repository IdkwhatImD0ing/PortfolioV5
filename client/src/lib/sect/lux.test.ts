import { describe, expect, it } from "vitest";
import {
  aoMultiBounce,
  aoRadiusPx,
  aoScale,
  henyeyGreenstein,
  LUX,
  LUX_OFF,
  luxBuilt,
  luxLive,
  parseLuxParam,
  shaftCentre,
  shaftPhase,
  shaftScale,
  shaftsStale,
} from "./lux";
import { degradeQuality, tierQuality } from "./runtime";
import type { Vec3 } from "./types";

const ALL = { ao: true, shafts: true, finish: true };
const FINISH_ONLY = { ao: false, shafts: false, finish: true };

describe("luxBuilt", () => {
  it("builds all three on High, the finish alone on Medium, nothing on Low", () => {
    expect(luxBuilt(tierQuality("high", 1))).toEqual(ALL);
    // High above 1.25x has 2 samples, still MSAA.
    expect(luxBuilt(tierQuality("high", 1.5))).toEqual(ALL);
    expect(luxBuilt(tierQuality("mid", 1))).toEqual(FINISH_ONLY);
    expect(luxBuilt(tierQuality("mid", 2, { coarse: true }))).toEqual(FINISH_ONLY);
    expect(luxBuilt(tierQuality("low", 1))).toEqual(LUX_OFF);
  });
});

describe("luxLive", () => {
  const high = tierQuality("high", 1);
  const mid = tierQuality("mid", 1);

  it("runs everything that is built at the tier's own top", () => {
    expect(luxLive(high, high)).toEqual(ALL);
    expect(luxLive(mid, mid)).toEqual(FINISH_ONLY);
    expect(luxLive(tierQuality("low", 1), tierQuality("low", 1))).toEqual(LUX_OFF);
  });

  it("keeps the contact shade and the shafts while some MSAA is left", () => {
    expect(luxLive(high, { ...high, msaa: 2 })).toEqual(ALL);
  });

  it("rests the contact shade and the shafts once MSAA or bloom is gone, and keeps the finish", () => {
    expect(luxLive(high, { ...high, msaa: 0 })).toEqual(FINISH_ONLY);
    expect(luxLive(high, { ...high, bloom: false })).toEqual(FINISH_ONLY);
    expect(luxLive(high, { ...high, msaa: 0, bloom: false })).toEqual(FINISH_ONLY);
    expect(luxLive(mid, { ...mid, bloom: false })).toEqual(FINISH_ONLY);
  });

  it("runs nothing once post is off", () => {
    expect(luxLive(high, { ...high, post: false })).toEqual(LUX_OFF);
  });

  it("never runs a pass the tier was not built with", () => {
    // Medium given a quality with MSAA still has no contact shade or shafts to switch on.
    expect(luxLive(mid, { ...mid, msaa: 4 })).toEqual(FINISH_ONLY);
  });

  it("follows a real ladder walk from High: only a subset of what is built, the finish to the bottom", () => {
    const built = luxBuilt(high);
    let q = high;
    for (let i = 0; i < 12; i++) {
      const next = degradeQuality(q, 1);
      if (!next) break;
      q = next;
      const live = luxLive(high, q);
      for (const k of ["ao", "shafts", "finish"] as const) if (live[k]) expect(built[k]).toBe(true);
      expect(live.finish).toBe(true);
      if (q.msaa === 0) {
        expect(live.ao).toBe(false);
        expect(live.shafts).toBe(false);
      }
    }
    expect(q.msaa).toBe(0);
  });
});

describe("parseLuxParam", () => {
  it("reads ?lux= from the query string", () => {
    expect(parseLuxParam("")).toBeNull();
    expect(parseLuxParam("?lux=0")).toBe("off");
    expect(parseLuxParam("?lux=off")).toBe("off");
    expect(parseLuxParam("?lux=ao")).toBe("ao");
    expect(parseLuxParam("?debug=1&lux=shafts")).toBe("shafts");
    expect(parseLuxParam("?lux=ao&debug=1")).toBe("ao");
  });

  it("ignores values it does not know and look-alike keys", () => {
    expect(parseLuxParam("?lux=bloom")).toBeNull();
    expect(parseLuxParam("?lux=AO")).toBeNull();
    expect(parseLuxParam("?lux=")).toBeNull();
    expect(parseLuxParam("?flux=ao")).toBeNull();
    expect(parseLuxParam("#lux=ao")).toBeNull();
  });
});

describe("aoScale", () => {
  it("is 1 at 1080p and below", () => {
    expect(aoScale(1920, 1080)).toBe(1);
    expect(aoScale(1280, 720)).toBe(1);
    expect(aoScale(1, 1)).toBe(1);
  });

  it("is about a half at 4K, and the buffer then holds about maxPixels", () => {
    const s = aoScale(3840, 2160);
    expect(s).toBeCloseTo(0.5, 1);
    expect(3840 * s * 2160 * s).toBeCloseTo(LUX.ao.maxPixels, -2);
  });

  it("is never above 1, and finite for an empty frame", () => {
    for (const [w, h] of [[0, 0], [10, 10], [800, 600], [2560, 1440], [7680, 4320]]) {
      const s = aoScale(w, h);
      expect(Number.isFinite(s)).toBe(true);
      expect(s).toBeGreaterThan(0);
      expect(s).toBeLessThanOrEqual(1);
    }
  });

  it("takes its own pixel cap", () => {
    expect(aoScale(100, 100, 2500)).toBeCloseTo(0.5);
  });
});

describe("aoRadiusPx", () => {
  it("is the radius projected to pixels at that distance", () => {
    // 1 m at 10 m with p11 = 1 on a 1000 px frame: 1 * 1 * 500 / 10.
    expect(aoRadiusPx(1, 10, 1, 1000)).toBeCloseTo(50);
  });

  it("halves when the distance doubles and doubles with the radius", () => {
    const a = aoRadiusPx(LUX.ao.radius, 20, 1.7, 1080);
    expect(aoRadiusPx(LUX.ao.radius, 40, 1.7, 1080)).toBeCloseTo(a / 2);
    expect(aoRadiusPx(LUX.ao.radius * 2, 20, 1.7, 1080)).toBeCloseTo(a * 2);
  });

  it("stays finite at zero distance", () => {
    expect(Number.isFinite(aoRadiusPx(1, 0, 1, 1000))).toBe(true);
  });
});

describe("aoMultiBounce", () => {
  const grid = Array.from({ length: 11 }, (_, i) => i / 10);

  it("never darkens below the visibility it was given", () => {
    for (const v of grid) for (const a of grid) expect(aoMultiBounce(v, a)).toBeGreaterThanOrEqual(v);
  });

  it("fills more of a crease on a brighter surface", () => {
    for (const v of grid.slice(1, -1)) {
      expect(aoMultiBounce(v, 0.9)).toBeGreaterThan(aoMultiBounce(v, 0.1));
      for (let i = 1; i < grid.length; i++) expect(aoMultiBounce(v, grid[i])).toBeGreaterThanOrEqual(aoMultiBounce(v, grid[i - 1]));
    }
  });

  it("keeps a fully open point open and a fully closed one closed", () => {
    for (const a of grid) {
      expect(aoMultiBounce(1, a)).toBeCloseTo(1, 3);
      expect(aoMultiBounce(0, a)).toBe(0);
    }
  });
});

describe("henyeyGreenstein", () => {
  it("is 1 everywhere with no anisotropy", () => {
    for (const c of [-1, -0.3, 0, 0.5, 1]) expect(henyeyGreenstein(c, 0)).toBeCloseTo(1);
  });

  it("integrates to 2 over the cosine (the sphere's 4 pi left out)", () => {
    for (const g of [0.18, 0.5, 0.76]) {
      const n = 4000;
      let sum = 0;
      for (let i = 0; i < n; i++) sum += henyeyGreenstein(-1 + ((i + 0.5) * 2) / n, g) * (2 / n);
      expect(sum).toBeCloseTo(2, 2);
    }
  });

  it("rises toward the light for a forward lobe", () => {
    for (let i = 0; i < 20; i++) expect(henyeyGreenstein(-1 + (i + 1) / 10, 0.76)).toBeGreaterThan(henyeyGreenstein(-1 + i / 10, 0.76));
  });
});

describe("shaftPhase", () => {
  const p = LUX.shafts.phase;

  it("is exactly 1 looking across the light", () => {
    expect(shaftPhase(0)).toBe(1);
  });

  it("is capped at phase.max looking into the sun", () => {
    expect(shaftPhase(1)).toBeLessThanOrEqual(p.max);
    const uncapped = shaftPhase(1, { ...p, max: Number.POSITIVE_INFINITY });
    expect(shaftPhase(1)).toBe(Math.min(uncapped, p.max));
    expect(p.max).toBeGreaterThan(1);
  });

  it("is below 1 looking down-sun, and never negative", () => {
    expect(shaftPhase(-1)).toBeLessThan(1);
    expect(shaftPhase(-1)).toBeGreaterThan(0);
    expect(shaftPhase(-0.5)).toBeLessThan(1);
  });

  it("rises with the cosine until the cap", () => {
    let prev = shaftPhase(-1);
    for (let i = 1; i <= 40; i++) {
      const v = shaftPhase(-1 + i / 20);
      expect(v).toBeGreaterThanOrEqual(prev);
      prev = v;
    }
  });

  it("takes its own lobes", () => {
    expect(shaftPhase(0.7, { forward: 0, broad: 0, mix: 0.5, max: 10 })).toBeCloseTo(1);
  });
});

describe("shaftCentre", () => {
  // The sect's sun (low, 7 degrees up) and the shadow map's own texel.
  const sun: Vec3 = [-0.94397, 0.12187, 0.30671];
  const texel = (2 * LUX.shafts.box) / LUX.shafts.map;
  const len = Math.hypot(...sun);
  const s: Vec3 = [sun[0] / len, sun[1] / len, sun[2] / len];
  const cross = (a: Vec3, b: Vec3): Vec3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const r0 = cross([0, 1, 0], s);
  const rl = Math.hypot(...r0);
  const right: Vec3 = [r0[0] / rl, r0[1] / rl, r0[2] / rl];
  const up = cross(s, right);
  const add = (a: Vec3, b: Vec3, k = 1): Vec3 => [a[0] + b[0] * k, a[1] + b[1] * k, a[2] + b[2] * k];
  const onGrid = (x: number) => Math.abs(x / texel - Math.round(x / texel));
  const cams: Vec3[] = [
    [0, 0, 0],
    [123.4, 56.7, -89.1],
    [-1520.25, 312.9, 2047.6],
    [0.11, 900, -0.07],
  ];

  it("lands on the texel grid across the light", () => {
    for (const cam of cams) {
      const c = shaftCentre(cam, sun, texel);
      expect(onGrid(dot(c, right))).toBeLessThan(1e-6);
      expect(onGrid(dot(c, up))).toBeLessThan(1e-6);
    }
  });

  it("keeps the camera's position along the sun, and stays within half a texel of it across", () => {
    for (const cam of cams) {
      const c = shaftCentre(cam, sun, texel);
      expect(dot(c, s)).toBeCloseTo(dot(cam, s), 6);
      expect(Math.abs(dot(c, right) - dot(cam, right))).toBeLessThanOrEqual(texel / 2 + 1e-9);
      expect(Math.abs(dot(c, up) - dot(cam, up))).toBeLessThanOrEqual(texel / 2 + 1e-9);
    }
  });

  it("does not need a unit sun direction", () => {
    const cam = cams[1];
    const a = shaftCentre(cam, sun, texel);
    const b = shaftCentre(cam, [sun[0] * 5, sun[1] * 5, sun[2] * 5], texel);
    for (let i = 0; i < 3; i++) expect(b[i]).toBeCloseTo(a[i], 6);
  });

  it("is stable while the camera moves less than half a texel from a grid point", () => {
    const grid = shaftCentre(cams[2], sun, texel);
    const base = shaftCentre(grid, sun, texel);
    for (const [dx, dy] of [[0.4, 0], [-0.4, 0], [0, 0.4], [0, -0.4], [0.3, -0.3]]) {
      const c = shaftCentre(add(add(grid, right, dx * texel), up, dy * texel), sun, texel);
      expect(dot(c, right)).toBeCloseTo(dot(base, right), 6);
      expect(dot(c, up)).toBeCloseTo(dot(base, up), 6);
    }
  });

  it("moves by whole texels, and by at most one for a move under a texel", () => {
    const grid = shaftCentre(cams[1], sun, texel);
    const base = shaftCentre(grid, sun, texel);
    for (const k of [1, 2, 7, -3]) {
      const c = shaftCentre(add(grid, right, k * texel), sun, texel);
      expect((dot(c, right) - dot(base, right)) / texel).toBeCloseTo(k, 6);
    }
    expect((dot(shaftCentre(add(grid, up, 3.7 * texel), sun, texel), up) - dot(base, up)) / texel).toBeCloseTo(4, 6);
    for (let i = 0; i < 20; i++) {
      const cam = add(cams[3], right, (i / 20) * 0.99 * texel);
      const a = shaftCentre(cams[3], sun, texel);
      const b = shaftCentre(cam, sun, texel);
      const steps = Math.abs(dot(b, right) - dot(a, right)) / texel;
      expect(onGrid(steps * texel)).toBeLessThan(1e-6);
      expect(steps).toBeLessThanOrEqual(1 + 1e-6);
    }
  });

  it("follows a move along the sun exactly, with no snap", () => {
    const a = shaftCentre(cams[1], sun, texel);
    const b = shaftCentre(add(cams[1], s, 37.3), sun, texel);
    expect(dot(b, s) - dot(a, s)).toBeCloseTo(37.3, 6);
    expect(dot(b, right)).toBeCloseTo(dot(a, right), 6);
    expect(dot(b, up)).toBeCloseTo(dot(a, up), 6);
  });

  it("is never stale for the camera it was made for", () => {
    for (const cam of cams) expect(shaftsStale(cam, shaftCentre(cam, sun, texel))).toBe(false);
  });
});

describe("shaftsStale", () => {
  const r = LUX.shafts.refresh;

  it("goes stale once the camera is more than refresh metres from the centre", () => {
    const c: Vec3 = [10, 20, 30];
    expect(shaftsStale(c, c)).toBe(false);
    expect(shaftsStale([10 + r * 0.99, 20, 30], c)).toBe(false);
    expect(shaftsStale([10 + r * 1.01, 20, 30], c)).toBe(true);
    // In 3D, not per axis: each axis under refresh, the distance over it.
    const d = r * 0.75;
    expect(shaftsStale([10 + d, 20 + d, 30], c)).toBe(true);
  });

  it("takes its own distance", () => {
    expect(shaftsStale([5, 0, 0], [0, 0, 0], 4)).toBe(true);
    expect(shaftsStale([3, 0, 0], [0, 0, 0], 4)).toBe(false);
  });
});

describe("shaftScale", () => {
  const c = LUX.shafts;

  it("is never above the resolution share, and the buffer never above its pixel cap", () => {
    for (const [w, h] of [[640, 360], [1920, 1080], [2560, 1440], [3840, 2160]]) {
      const s = shaftScale(w, h);
      expect(s).toBeGreaterThan(0);
      expect(s).toBeLessThanOrEqual(c.resolution);
      expect(w * s * h * s).toBeLessThanOrEqual(c.maxPixels * (1 + 1e-9));
    }
  });

  it("drops below the share on a large frame", () => {
    expect(shaftScale(3840, 2160)).toBeLessThan(c.resolution);
    expect(shaftScale(3840, 2160)).toBeLessThan(shaftScale(1920, 1080));
  });

  it("takes its own share and cap, and stays finite for an empty frame", () => {
    expect(shaftScale(100, 100, { resolution: 0.5, maxPixels: 1e6 })).toBe(0.5);
    expect(shaftScale(1000, 1000, { resolution: 0.5, maxPixels: 1e4 })).toBeCloseTo(0.1);
    expect(Number.isFinite(shaftScale(0, 0))).toBe(true);
  });
});

describe("LUX", () => {
  it("keeps its smoothstep edges in order (equal edges are undefined in GLSL)", () => {
    expect(LUX.ao.fade[0]).toBeLessThan(LUX.ao.fade[1]);
    expect(LUX.ao.glow[0]).toBeLessThan(LUX.ao.glow[1]);
  });

  it("keeps a marched ray inside the sun's map until the map is redrawn", () => {
    const c = LUX.shafts;
    // The camera can be `refresh` metres from the map's centre, and a ray reaches maxDist further.
    expect(c.refresh + c.maxDist).toBeLessThanOrEqual(c.box);
    expect(c.maxDist).toBeLessThanOrEqual(c.back);
  });

  it("never takes a whole pixel away", () => {
    expect(LUX.shafts.dimMax).toBeGreaterThan(0);
    expect(LUX.shafts.dimMax).toBeLessThan(1);
    expect(LUX.ao.strength).toBeLessThanOrEqual(1);
  });
});
