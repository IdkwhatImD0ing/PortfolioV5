/**
 * The night re-bake (docs/scene/night-r61.md): the abode and the summit were baked under their own
 * light, and their live index says so, so the live light adds what the bake had. The other nine
 * stops keep the scene's sunset sun. Reads the installed JSON only (never a baked map's bytes: CI
 * has no Git LFS files).
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { liveIndexFile, liveStopsFile, parseLiveIndex, parseLiveStops, type LiveIndex } from "./live";
import type { Vec3 } from "./types";

const ROOT = path.resolve(__dirname, "../../../public/sect/full");

function readJson(file: string): unknown {
  return JSON.parse(readFileSync(path.join(ROOT, file), "utf8"));
}

function index(stop: string): LiveIndex {
  const ix = parseLiveIndex(readJson(liveIndexFile(stop)));
  if (!ix) throw new Error(`${stop}: index.json does not parse`);
  return ix;
}

/** The unit vector toward a lamp at a compass azimuth and an elevation (degrees), three.js axes, as the bake writes it. */
function toward(azDeg: number, elDeg: number): Vec3 {
  const az = (azDeg * Math.PI) / 180;
  const el = (elDeg * Math.PI) / 180;
  return [Math.sin(az) * Math.cos(el), Math.sin(el), -Math.cos(az) * Math.cos(el)];
}

function angleDeg(a: Vec3, b: Vec3): number {
  const d = a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  return (Math.acos(Math.min(Math.max(d, -1), 1)) * 180) / Math.PI;
}

/** What each night stop was baked under (blender/xianxia-sect/sect/bake_light.py). */
const NIGHT: Record<string, { az: number; el: number; strength: number }> = {
  // Blue hour: a soft cool afterglow from the west.
  abode: { az: 252, el: 28, strength: 2.5 },
  // Full moon: a cool white key from the moon's side.
  summit: { az: 45, el: 22, strength: 4 },
};

const meta = readJson("meta.json") as { sun: { direction: Vec3; colorLinear: Vec3; intensity: number; azimuthDeg: number; elevationDeg: number } };

describe("the night stops' live light (public/sect/full/live)", () => {
  it("the scene's sun in meta.json is the sunset the other stops were baked under", () => {
    // The helper writes directions as the bake does: the scene's own sun from its azimuth and elevation.
    toward(meta.sun.azimuthDeg, meta.sun.elevationDeg).forEach((v, i) => expect(v).toBeCloseTo(meta.sun.direction[i], 4));
  });

  it("the abode and the summit carry the light they were baked under, with no key lamp", () => {
    for (const [stop, n] of Object.entries(NIGHT)) {
      const ix = index(stop);
      expect(ix.light.key.strength, stop).toBe(0);
      toward(n.az, n.el).forEach((v, i) => expect(ix.light.sun.dir[i], `${stop} sun dir`).toBeCloseTo(v, 4));
      expect(ix.light.sun.strength, stop).toBe(n.strength);
      // A cool light, not the sunset's orange.
      const c = ix.light.sun.color;
      expect(c[2], stop).toBeGreaterThanOrEqual(c[0]);
      expect(c[2], stop).toBeGreaterThanOrEqual(c[1]);
    }
    // The summit's moon stands on the far side of the sky from the sunset.
    expect(angleDeg(index("summit").light.sun.dir, meta.sun.direction)).toBeGreaterThan(120);
  });

  it("the other nine stops still carry the scene's sun from meta.json, and its key lamp", () => {
    const stops = parseLiveStops(readJson(liveStopsFile()));
    const day = stops.filter((s) => !(s in NIGHT));
    expect(day).toHaveLength(9);
    for (const stop of day) {
      const sun = index(stop).light.sun;
      sun.dir.forEach((v, i) => expect(v, `${stop} sun dir`).toBeCloseTo(meta.sun.direction[i], 4));
      sun.color.forEach((v, i) => expect(v, `${stop} sun colour`).toBeCloseTo(meta.sun.colorLinear[i], 4));
      expect(sun.strength, stop).toBe(meta.sun.intensity);
      expect(index(stop).light.key.strength, stop).toBeGreaterThan(0);
    }
  });
});
