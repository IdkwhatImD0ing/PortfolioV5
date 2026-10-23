import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { fovForAspect } from "./camera-path";
import { STOP_FRAMING } from "./framing";
import { downloadFraction, flickStop, openingMegabytes, PORTRAIT_TURN_DEG, portraitTurn, POSTER, posterBox, posterMatches, type DownloadGroup } from "./opening";
import { buildScrollMap, FLIGHT_SCROLL } from "./scroll-map";

const DEG = Math.PI / 180;

/** Evaluates a posterBox expression (max/min of cqw and cqh terms) for a box of w x h pixels. */
function cssPx(expr: string, w: number, h: number): number {
  const js = expr.replace(/([\d.]+)cq([wh])/g, (_, v: string, u: string) => String((Number(v) / 100) * (u === "w" ? w : h))).replace(/\b(max|min)\(/g, "Math.$1(");
  return Function(`return ${js};`)() as number;
}

/** Pixels per unit of tan(angle) of the live canvas on a w x h screen (vertical half-field). */
function canvasScale(w: number, h: number): number {
  const fov = fovForAspect(POSTER.fovY, POSTER.refAspect, w / h, POSTER.maxFovY);
  return h / (2 * Math.tan((fov * DEG) / 2));
}

describe("posterBox", () => {
  const ty0 = Math.tan((POSTER.fovY * DEG) / 2);
  const TX = POSTER.maxAspect * ty0;

  it("draws the landscape still at the canvas's own scale on every covered landscape screen", () => {
    for (const [w, h] of [
      [1600, 900],
      [1366, 768],
      [1920, 960],
      [1440, 900],
      [1280, 1000],
      [844, 390],
      [2560, 1080],
    ]) {
      const box = posterBox("landscape");
      const width = cssPx(box.width, w, h);
      const height = cssPx(box.height, w, h);
      // The still spans 2 TX in tan units across its width.
      expect(width / (2 * TX), `${w}x${h}`).toBeCloseTo(canvasScale(w, h), 3);
      expect(width / height).toBeCloseTo((POSTER.maxAspect * ty0) / ((ty0 * POSTER.refAspect) / POSTER.minAspect), 3);
      // It covers the screen.
      expect(width).toBeGreaterThanOrEqual(w - 1e-6);
      expect(height).toBeGreaterThanOrEqual(h - 1e-6);
    }
  });

  it("still covers screens outside the range", () => {
    const box = posterBox("landscape");
    for (const [w, h] of [
      [1000, 1000],
      [3840, 1080],
    ]) {
      expect(cssPx(box.width, w, h)).toBeGreaterThanOrEqual(w - 1e-6);
      expect(cssPx(box.height, w, h)).toBeGreaterThanOrEqual(h - 1e-6);
    }
  });

  it("fills a phone's height with the 70 degree portrait still", () => {
    const box = posterBox("portrait");
    for (const [w, h] of [
      [390, 844],
      [360, 800],
      [768, 1024],
    ]) {
      expect(cssPx(box.height, w, h), `${w}x${h}`).toBeCloseTo(h, 6);
      // As wide as the 16:9 horizontal field at that scale.
      const scale = h / 2 / Math.tan((POSTER.maxFovY * DEG) / 2);
      expect(cssPx(box.width, w, h)).toBeCloseTo(2 * ty0 * POSTER.refAspect * scale, 2);
      // The canvas really is at 70 degrees there.
      expect(fovForAspect(POSTER.fovY, POSTER.refAspect, w / h, POSTER.maxFovY)).toBeCloseTo(POSTER.maxFovY, 6);
    }
  });
});

describe("posterMatches", () => {
  it("holds for the shipped camera, and not for another start", () => {
    const camera = JSON.parse(readFileSync(path.resolve(__dirname, "../../../public/sect/full/camera.json"), "utf8")) as {
      startFrame: number;
      refAspect: number;
      frames: { f: number; fovY: number }[];
    };
    const start = camera.frames.find((f) => f.f === camera.startFrame);
    expect(posterMatches(start?.fovY, camera.refAspect, camera.startFrame)).toBe(true);
    expect(posterMatches(40, camera.refAspect, camera.startFrame)).toBe(false);
    expect(posterMatches(start?.fovY, camera.refAspect, 1)).toBe(false);
    expect(posterMatches(undefined, camera.refAspect, camera.startFrame)).toBe(false);
  });
});

describe("downloadFraction", () => {
  const f = (loaded: number, total: number, done = false) => ({ loaded, total, done });

  it("counts bytes, with the manifest's figure standing in for sizes not known yet", () => {
    const groups: DownloadGroup[] = [
      // Global: no manifest figure, sizes known.
      { files: [f(0, 6_000_000), f(0, 2_000_000), f(250_000, 250_000, true)], bytes: 0 },
      // The first area: one size not known yet.
      { files: [f(0, 8_000_000), f(0, 0), f(90_000, 90_000, true)], bytes: 13_000_000 },
    ];
    expect(downloadFraction(groups)).toBeCloseTo(340_000 / 21_250_000, 9);
  });

  it("does not read a small file done early as a sixth of the download", () => {
    const early: DownloadGroup[] = [
      { files: [f(0, 0), f(0, 0), f(250_000, 0, true)], bytes: 0 },
      { files: [f(0, 0), f(0, 0), f(90_000, 0, true)], bytes: 13_000_000 },
    ];
    const v = downloadFraction(early);
    expect(v).toBeLessThan(0.05);
    // Once every size is known the fraction is close, not far below.
    const later: DownloadGroup[] = [
      { files: [f(0, 6_000_000), f(0, 2_000_000), f(250_000, 250_000, true)], bytes: 0 },
      { files: [f(0, 8_700_000), f(0, 4_200_000), f(90_000, 90_000, true)], bytes: 13_000_000 },
    ];
    expect(downloadFraction(later)).toBeGreaterThan(v * 0.5);
  });

  it("is 0 with nothing known and 1 when everything is done", () => {
    expect(downloadFraction([])).toBe(0);
    expect(downloadFraction([{ files: [f(0, 0)], bytes: 0 }])).toBe(0);
    expect(downloadFraction([{ files: [f(5, 5, true), f(7, 0, true)], bytes: 100 }])).toBe(1);
  });
});

describe("openingMegabytes", () => {
  it("adds the global set and the first area from the shipped manifest", () => {
    const raw = JSON.parse(readFileSync(path.resolve(__dirname, "../../../public/sect/full/manifest.json"), "utf8")) as {
      globalBytes: number;
      chunks: { bytes: number; bytesLow: number }[];
    };
    expect(openingMegabytes(raw, false)).toBe(Math.round((raw.globalBytes + raw.chunks[0].bytes) / 1e6));
    expect(openingMegabytes(raw, true)).toBe(Math.round((raw.globalBytes + raw.chunks[0].bytesLow) / 1e6));
  });

  it("is null when the manifest does not say", () => {
    expect(openingMegabytes(null, false)).toBeNull();
    expect(openingMegabytes({ chunks: [] }, false)).toBeNull();
    expect(openingMegabytes({ globalBytes: 9e6, chunks: [{}] }, false)).toBeNull();
    expect(openingMegabytes({ globalBytes: 9e6, chunks: [{ bytes: 13e6 }] }, true)).toBe(22);
  });
});

describe("portraitTurn", () => {
  it("turns toward the items at the stops that need it, on portrait screens only", () => {
    // 10 and 13 degrees left of the path's own view in all, 4 and 8 of them the stops' framing on
    // every screen.
    expect(portraitTurn("mirror", true).yaw + STOP_FRAMING.mirror.yaw * DEG).toBeCloseTo(10 * DEG, 9);
    expect(portraitTurn("mission", true).yaw + STOP_FRAMING.mission.yaw * DEG).toBeCloseTo(13 * DEG, 9);
    // The jade slip keeps the film's own view on phones too, as before its framing (2026-10-22).
    expect(portraitTurn("scroll", true)).toEqual({ yaw: 0, pitch: 0 });
    // The cave abode turns right, the cliff's inscription out from under the labels.
    expect(portraitTurn("abode", true).yaw).toBeCloseTo(-3 * DEG, 9);
    expect(portraitTurn("mirror", true).pitch).toBe(0);
    expect(portraitTurn("mirror", false)).toEqual({ yaw: 0, pitch: 0 });
    expect(portraitTurn("forge", true)).toEqual({ yaw: 0, pitch: 0 });
    expect(portraitTurn(null, true)).toEqual({ yaw: 0, pitch: 0 });
  });

  it("tilts up at the stops whose landmark reached under the labels, a few degrees", () => {
    // Up lowers the picture: the gate's ridge, the sword's hilt, the hall's roof, the pagoda's spire
    // and the end pavilion's finial come out from under the stop's label and look hint.
    expect(portraitTurn("arena", true).yaw).toBe(0);
    expect(portraitTurn("arena", true).pitch).toBeCloseTo(7 * DEG, 9);
    expect(portraitTurn("gate", true).pitch).toBeCloseTo(7 * DEG, 9);
    expect(portraitTurn("mission", true).pitch).toBeCloseTo(7 * DEG, 9);
    for (const id of ["library", "steles"]) expect(portraitTurn(id, true).pitch).toBeGreaterThan(0);
    for (const t of Object.values(PORTRAIT_TURN_DEG)) {
      expect(Math.abs(t.pitch ?? 0)).toBeLessThanOrEqual(8);
      expect(Math.abs(t.yaw ?? 0)).toBeLessThanOrEqual(12);
    }
  });

  it("never turns the opening view, the poster's: the start of the flight is in no stop's hold", () => {
    const camera = JSON.parse(readFileSync(path.resolve(__dirname, "../../../public/sect/full/camera.json"), "utf8")) as {
      startFrame: number;
      frameEnd: number;
      holds: { id: string; label: string; frame: number }[];
    };
    const map = buildScrollMap(camera.startFrame, camera.frameEnd, camera.holds, FLIGHT_SCROLL);
    expect(camera.startFrame).toBe(POSTER.startFrame);
    expect(map.holds.some((h) => 0 >= h.u0 && 0 <= h.u1)).toBe(false);
  });
});

describe("flickStop", () => {
  const camera = JSON.parse(readFileSync(path.resolve(__dirname, "../../../public/sect/full/camera.json"), "utf8")) as {
    startFrame: number;
    frameEnd: number;
    holds: { id: string; label: string; frame: number }[];
  };
  const map = buildScrollMap(camera.startFrame, camera.frameEnd, camera.holds, FLIGHT_SCROLL);
  const mirror = map.holds.find((h) => h.id === "mirror")!;
  const forge = map.holds.find((h) => h.id === "forge")!;

  it("glides on to the next stop ahead within reach", () => {
    expect(flickStop(map, forge.u0 - 30, 60, 1)).toBe(forge.uMid);
    expect(flickStop(map, mirror.u1 + 20, 60, -1)).toBe(mirror.uMid);
    // Direction unknown: the nearest.
    expect(flickStop(map, mirror.u1 + 20, 60)).toBe(mirror.uMid);
    expect(flickStop(map, 5, 60)).toBe(0);
  });

  it("glides back only to a stop it overshot by a little", () => {
    // Just past the mirror's dwell going on (21 units from its middle), the forge far ahead.
    expect(forge.uMid - (mirror.u1 + 2)).toBeGreaterThan(75);
    expect(flickStop(map, mirror.u1 + 2, 75, 1)).toBe(mirror.uMid);
    expect(flickStop(map, mirror.u1 + 10, 75, 1)).toBeNull();
    // Far past the stop behind, nothing ahead within reach: stay.
    const gap = (mirror.u1 + forge.u0) / 2;
    expect(flickStop(map, gap, 20, 1)).toBeNull();
    expect(flickStop(map, gap, 20, -1)).toBeNull();
  });

  it("stays inside a hold, at the start, or too far from any stop", () => {
    expect(flickStop(map, mirror.uMid + 5, 60, 1)).toBeNull();
    expect(flickStop(map, 0.5, 60, -1)).toBeNull();
    const gap = (mirror.u1 + forge.u0) / 2;
    expect(flickStop(map, gap, 10)).toBeNull();
  });
});
