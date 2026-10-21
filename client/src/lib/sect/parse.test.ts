import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { sampleCamera } from "./camera-path";
import { projectPoint } from "./coords";
import { parseCameraData, parseClouds, parseFlyerPath, parseManifest, parseMeta, resolveAsset } from "./parse";

describe("parseManifest (version 2)", () => {
  const v2 = {
    version: 2,
    baked: false,
    camera: "camera.json",
    meta: "meta.json",
    clouds: "clouds.json",
    flyer: "flyer.glb",
    flyerPath: "flyer.json",
    water: null,
    global: ["backdrop.glb.gz"],
    globalLow: null,
    chunks: [
      { id: "gate", files: ["gate.glb.gz", "gate_trees.glb.gz"], filesLow: ["low/gate.glb.gz", "low/gate_trees.glb.gz"], need: [1, 190], bytes: 9e6, bytesLow: 5e6, tris: 900000 },
      { id: "mirror", files: ["mirror.glb.gz"], need: [140, 320] },
    ],
  };

  it("reads global files and chunks in flight order", () => {
    const m = parseManifest(v2);
    expect(m.version).toBe(2);
    expect(m.baked).toBe(false);
    expect(m.global).toEqual(["backdrop.glb.gz"]);
    expect(m.globalLow).toBeNull();
    expect(m.water).toBeNull();
    expect(m.clouds).toBe("clouds.json");
    expect(m.chunks.map((c) => c.id)).toEqual(["gate", "mirror"]);
    expect(m.chunks[0]).toEqual({
      id: "gate",
      files: ["gate.glb.gz", "gate_trees.glb.gz"],
      filesLow: ["low/gate.glb.gz", "low/gate_trees.glb.gz"],
      need: [1, 190],
      bytes: 9e6,
      bytesLow: 5e6,
      tris: 900000,
    });
    // Optional chunk keys default.
    expect(m.chunks[1]).toEqual({ id: "mirror", files: ["mirror.glb.gz"], filesLow: null, need: [140, 320], bytes: 0, bytesLow: null, tris: 0 });
  });

  it("reads the texture memory the packer measured: one number, or one per file", () => {
    const m = parseManifest({
      ...v2,
      chunks: [
        { id: "gate", files: ["a.glb", "b.glb"], need: [1, 2], texBytes: 228e6, texBytesLow: [60e6, 2e6] },
        { id: "mirror", files: ["c.glb"], need: [3, 4], texBytes: "lots", texBytesLow: [1e6, -5] },
      ],
    });
    expect(m.chunks[0].texBytes).toBe(228e6);
    expect(m.chunks[0].texBytesLow).toBe(62e6);
    // Malformed: as if absent (streaming.ts estimates from the download size then).
    expect(m.chunks[1].texBytes).toBeUndefined();
    expect(m.chunks[1].texBytesLow).toBeUndefined();
  });

  it("ignores a low-texture list that does not pair up with its files", () => {
    const m = parseManifest({ ...v2, globalLow: ["a.glb", "b.glb"], chunks: [{ id: "gate", files: ["a.glb", "b.glb"], filesLow: ["a.glb"], need: [1, 2] }] });
    expect(m.globalLow).toBeNull();
    expect(m.chunks[0].filesLow).toBeNull();
  });

  it("rejects chunks the page cannot stream", () => {
    expect(() => parseManifest({ ...v2, chunks: [{ files: ["a.glb"], need: [1, 2] }] })).toThrow(/id/);
    expect(() => parseManifest({ ...v2, chunks: [{ id: "a", files: [], need: [1, 2] }] })).toThrow(/files/);
    expect(() => parseManifest({ ...v2, chunks: [{ id: "a", files: ["a.glb"] }] })).toThrow(/need/);
    expect(() => parseManifest({ ...v2, chunks: [{ id: "a", files: ["a.glb"], need: [9, 2] }] })).toThrow(/before it starts/);
    expect(() =>
      parseManifest({ ...v2, chunks: [{ id: "a", files: ["a.glb"], need: [1, 2] }, { id: "a", files: ["b.glb"], need: [3, 4] }] }),
    ).toThrow(/twice/);
    expect(() => parseManifest({ version: 2, global: [], chunks: [] })).toThrow(/global/);
    expect(() => parseManifest(null)).toThrow();
  });

  it("defaults optional keys and treats a missing baked flag as false", () => {
    const m = parseManifest({ version: 2, global: ["a.glb"] });
    expect(m.camera).toBe("camera.json");
    expect(m.meta).toBe("meta.json");
    expect(m.flyer).toBeNull();
    expect(m.clouds).toBeNull();
    expect(m.baked).toBe(false);
    expect(m.chunks).toEqual([]);
    expect(m.detail).toBeUndefined();
  });

  it("reads the detail texture when the packer wrote one", () => {
    expect(parseManifest({ ...v2, detail: "detail.webp" }).detail).toBe("detail.webp");
    expect(parseManifest({ ...v2, detail: "" }).detail).toBeUndefined();
    expect(parseManifest({ ...v2, detail: 3 }).detail).toBeUndefined();
  });
});

describe("parseManifest (version 1, the first test)", () => {
  it("reads the flat scene list as global files with no chunks", () => {
    const m = parseManifest({
      scene: ["gate.glb.gz", "mirror.glb.gz"],
      sceneLow: ["low/gate.glb.gz", "low/mirror.glb.gz"],
      sceneDeferred: ["mirror.glb.gz"],
      water: "water.glb.gz",
      baked: true,
      clouds: "clouds.json",
    });
    expect(m.version).toBe(1);
    expect(m.global).toEqual(["gate.glb.gz", "mirror.glb.gz"]);
    expect(m.globalLow).toEqual(["low/gate.glb.gz", "low/mirror.glb.gz"]);
    expect(m.chunks).toEqual([]);
    expect(m.water).toBe("water.glb.gz");
    expect(m.baked).toBe(true);
    expect(parseManifest({ scene: ["a.glb", "b.glb"], sceneLow: ["a.glb"] }).globalLow).toBeNull();
  });

  it("rejects a manifest without scene files", () => {
    expect(() => parseManifest({ scene: [] })).toThrow(/scene/);
  });
});

describe("resolveAsset", () => {
  it("joins relative files to the base folder", () => {
    expect(resolveAsset("/sect/proto/", "camera.json")).toBe("/sect/proto/camera.json");
    expect(resolveAsset("/sect/proto", "./x.glb")).toBe("/sect/proto/x.glb");
  });

  it("leaves absolute paths and URLs alone", () => {
    expect(resolveAsset("/sect/proto", "/other/a.glb")).toBe("/other/a.glb");
    expect(resolveAsset("/sect/proto", "https://cdn.example/a.glb")).toBe("https://cdn.example/a.glb");
  });
});

describe("parseCameraData", () => {
  const frames = [
    { f: 2, p: [0, 1, 2], q: [0, 0, 0, 1], fovY: 35 },
    { f: 1, p: [0, 1, 3], q: [0, 0, 0, 1], fovY: 35 },
    { f: 3, p: [0, 1, 1], q: [0, 0, 0, 1], fovY: 35 },
  ];

  it("sorts frames and keeps holds inside the range", () => {
    const c = parseCameraData({
      frames,
      holds: [
        { id: "late", label: "Late", frame: 99 },
        { id: "mid", label: "Mid", frame: 2 },
      ],
      startFrame: 2,
    });
    expect(c.frames.map((f) => f.f)).toEqual([1, 2, 3]);
    expect(c.holds.map((h) => h.id)).toEqual(["mid"]);
    expect(c.startFrame).toBe(2);
    expect(c.refAspect).toBeCloseTo(16 / 9);
  });

  it("uses the exported aspect when refAspect is absent", () => {
    expect(parseCameraData({ frames, aspect: 2 }).refAspect).toBe(2);
    expect(parseCameraData({ frames, aspect: 2, refAspect: 1.5 }).refAspect).toBe(1.5);
  });

  it("rejects malformed frames", () => {
    expect(() => parseCameraData({ frames: [{ f: 1, p: [0, 0], q: [0, 0, 0, 1] }, frames[0]] })).toThrow();
  });

  it("drops repeated frame numbers so frames strictly increase", () => {
    const c = parseCameraData({ frames: [...frames, { f: 2, p: [9, 9, 9], q: [0, 0, 0, 1], fovY: 35 }] });
    expect(c.frames.map((f) => f.f)).toEqual([1, 2, 3]);
    expect(c.frames[1].p).toEqual([0, 1, 2]);
    expect(() =>
      parseCameraData({
        frames: [
          { f: 1, p: [0, 0, 0], q: [0, 0, 0, 1] },
          { f: 1, p: [1, 0, 0], q: [0, 0, 0, 1] },
        ],
      }),
    ).toThrow(/distinct/);
  });
});

describe("parseMeta", () => {
  it("fills defaults for an empty object", () => {
    const m = parseMeta({});
    expect(m.fog.density).toBeGreaterThan(0);
    expect(m.waterfalls).toEqual([]);
    expect(m.moon).toBeNull();
    expect(m.sky.texture).toBeNull();
  });

  it("normalises the sun direction and prefers sky.panorama over sky.texture", () => {
    const m = parseMeta({ sun: { direction: [0, 2, 0] }, sky: { texture: "sky.png", panorama: "sky.webp" } });
    expect(m.sun.direction).toEqual([0, 1, 0]);
    expect(m.sky.texture).toBe("sky.webp");
  });

  it("reads waterfall corners and light beams", () => {
    const m = parseMeta({
      waterfalls: [
        { name: "a", corners: [[0, 1, 0], [1, 1, 0], [1, 0, 0], [0, 0, 0]], foot: [0.5, 0, 0], flow: 1.25 },
        { name: "b", corners: [[0, 1, 0]] },
      ],
      beams: [
        { name: "pillar", base: [0, 0, 0], top: [0, 300, 0], radius: 1.6, color: "#6fffd8" },
        { name: "link", base: [0, 10, 0], top: [12, 10, 5], radius: 0.3 },
        { name: "broken", base: [0, 0], top: [0, 1, 0] },
        { name: "point", base: [1, 1, 1], top: [1, 1, 1] },
      ],
    });
    expect(m.waterfalls[0].corners).toHaveLength(4);
    expect(m.waterfalls[0].foot).toEqual([0.5, 0, 0]);
    expect(m.waterfalls[0].flow).toBe(1.25);
    expect(m.waterfalls[1].corners).toBeNull();
    expect(m.beams.map((b) => b.name)).toEqual(["pillar", "link"]);
    expect(m.beams[1].color).toBe("#9ff3ff");
  });

  it("reads hotspot areas and chunks, waterfall and beam chunks, and the areas list", () => {
    const m = parseMeta({
      hotspots: [{ id: "project:dispatchai", label: "Dispatch AI", area: "forge", chunk: "forge", center: [1, 2, 3], size: [1, 1, 1] }, { id: "moon" }],
      waterfalls: [{ name: "fall.1", chunk: "abode" }],
      beams: [{ name: "b", base: [0, 0, 0], top: [0, 10, 0], chunk: "formation" }],
      areas: [{ id: "forge", label: "Artifact Forge Peak", anchor: [130, 90, -350], footprint: 60, frameStart: 287, frameEnd: 496, heroFrame: 389 }, { label: "no id" }],
    });
    expect(m.hotspots[0].area).toBe("forge");
    expect(m.hotspots[0].chunk).toBe("forge");
    expect(m.hotspots[1].area).toBeNull();
    expect(m.waterfalls[0].chunk).toBe("abode");
    expect(m.beams[0].chunk).toBe("formation");
    expect(m.areas).toEqual([{ id: "forge", label: "Artifact Forge Peak", anchor: [130, 90, -350], footprint: 60, frameStart: 287, frameEnd: 496, heroFrame: 389 }]);
    expect(parseMeta({}).areas).toEqual([]);
  });

  it("drops hotspots without an id", () => {
    const m = parseMeta({ hotspots: [{ label: "x" }, { id: "gate", center: [1, 2, 3], size: [4, 5, 6] }] });
    expect(m.hotspots).toEqual([{ id: "gate", label: "gate", center: [1, 2, 3], size: [4, 5, 6], area: null, chunk: null }]);
  });
});

describe("parseClouds", () => {
  it("reads puffs and drops malformed ones", () => {
    const puffs = parseClouds({
      puffs: [
        { c: [1, 2, 3], a: [[10, 0, 0], [0, 5, 0], [0, 0, 8]], d: 0.4 },
        { c: [1, 2], a: [[1, 0, 0], [0, 1, 0], [0, 0, 1]], d: 0.4 },
        { c: [0, 0, 0], a: [[1, 0, 0], [0, 1, 0]], d: 0.4 },
        { c: [0, 0, 0], a: [[1, 0, 0], [0, 1, 0], [0, 0, 1]] },
      ],
    });
    expect(puffs).toHaveLength(2);
    expect(puffs[0]).toEqual({ c: [1, 2, 3], axes: [[10, 0, 0], [0, 5, 0], [0, 0, 8]], density: 0.4 });
    expect(puffs[1].density).toBe(0.4);
  });

  it("keeps the mist tag", () => {
    const puffs = parseClouds({
      puffs: [
        { c: [0, 0, 0], a: [[1, 0, 0], [0, 1, 0], [0, 0, 1]], d: 0.3, k: "mist.band" },
        { c: [0, 0, 0], a: [[1, 0, 0], [0, 1, 0], [0, 0, 1]], d: 0.3, k: 7 },
      ],
    });
    expect(puffs[0].kind).toBe("mist.band");
    expect(puffs[1].kind).toBeUndefined();
  });

  it("returns no puffs when the list is missing", () => {
    expect(parseClouds({})).toEqual([]);
    expect(() => parseClouds(null)).toThrow();
  });
});

describe("parseFlyerPath", () => {
  it("reads p/q frames", () => {
    const f = parseFlyerPath({ frames: [{ f: 1, p: [0, 0, 0], q: [0, 0, 0, 1] }, { f: 2, p: [1, 0, 0], q: [0, 0, 0, 1] }] });
    expect(f.frameEnd).toBe(2);
  });

  it("drops repeated frame numbers", () => {
    const f = parseFlyerPath({
      frames: [
        { f: 1, p: [0, 0, 0], q: [0, 0, 0, 1] },
        { f: 2, p: [1, 0, 0], q: [0, 0, 0, 1] },
        { f: 2, p: [5, 0, 0], q: [0, 0, 0, 1] },
      ],
    });
    expect(f.frames.map((x) => x.f)).toEqual([1, 2]);
  });
});

const proto = join(process.cwd(), "public/sect/proto");

describe.skipIf(!existsSync(join(proto, "manifest.json")))("the published proto files", () => {
  const read = (f: string) => JSON.parse(readFileSync(join(proto, f), "utf8"));

  it("parse without errors and agree with each other", () => {
    const manifest = parseManifest(read("manifest.json"));
    const cam = parseCameraData(read(manifest.camera));
    const meta = parseMeta(read(manifest.meta));
    expect(cam.frames.length).toBe(cam.frameEnd - cam.frameStart + 1);
    expect(cam.holds.map((h) => h.id)).toEqual(["gate", "mirror"]);
    expect(cam.startFrame).toBeGreaterThanOrEqual(cam.frameStart);
    expect(meta.hotspots.some((h) => h.id === "gate")).toBe(true);
    expect(meta.hotspots.some((h) => h.id === "mirror")).toBe(true);
    for (const f of manifest.global) expect(existsSync(join(proto, f))).toBe(true);
    for (const f of manifest.globalLow ?? []) expect(existsSync(join(proto, f))).toBe(true);
    if (manifest.water) expect(existsSync(join(proto, manifest.water))).toBe(true);
    if (meta.sky.texture) expect(existsSync(join(proto, meta.sky.texture))).toBe(true);
    if (manifest.flyerPath) parseFlyerPath(read(manifest.flyerPath));
    if (manifest.clouds) {
      const puffs = parseClouds(read(manifest.clouds));
      expect(puffs.length).toBeGreaterThan(100);
      // Some puffs sit along the flight (the stair-foot and gate-side banks), none absurdly far.
      expect(puffs.some((p) => Math.hypot(p.c[0], p.c[2] - 100) < 300)).toBe(true);
      for (const p of puffs) expect(Math.hypot(...p.c)).toBeLessThan(9000);
    }
  });

  it("camera quaternions are unit length and stay on one hemisphere", () => {
    const cam = parseCameraData(read("camera.json"));
    for (let i = 0; i < cam.frames.length; i++) {
      const q = cam.frames[i].q;
      expect(Math.hypot(...q)).toBeCloseTo(1, 4);
      if (i > 0) {
        const p = cam.frames[i - 1].q;
        expect(p[0] * q[0] + p[1] * q[1] + p[2] * q[2] + p[3] * q[3]).toBeGreaterThan(0);
      }
    }
  });
});

const full = join(process.cwd(), "public/sect/full");

describe.skipIf(!existsSync(join(full, "manifest.json")))("the published full files", () => {
  const read = (f: string) => JSON.parse(readFileSync(join(full, f), "utf8"));

  it("is a version 2 set with one chunk per area along the whole flight", () => {
    const manifest = parseManifest(read("manifest.json"));
    expect(manifest.version).toBe(2);
    const cam = parseCameraData(read(manifest.camera));
    expect(cam.frameEnd).toBe(1729);
    expect(cam.holds.length).toBe(11);
    const ids = cam.holds.map((h) => h.id);
    for (const c of manifest.chunks) expect(ids).toContain(c.id);
    for (const f of [...manifest.global, ...manifest.chunks.flatMap((c) => c.files)]) expect(existsSync(join(full, f))).toBe(true);
    // The low tier's files too (phones load these).
    for (const f of [...(manifest.globalLow ?? []), ...manifest.chunks.flatMap((c) => c.filesLow ?? [])]) {
      expect(existsSync(join(full, f)), f).toBe(true);
    }
    const meta = parseMeta(read(manifest.meta));
    if (meta.sky.texture) expect(existsSync(join(full, meta.sky.texture))).toBe(true);
  });

  it("every hold frames its own landmark (the area's hotspot): in front of the camera and on screen", () => {
    const manifest = parseManifest(read("manifest.json"));
    const cam = parseCameraData(read(manifest.camera));
    const meta = parseMeta(read(manifest.meta));
    for (const h of cam.holds) {
      const landmark = meta.hotspots.find((x) => x.id === h.id)?.center ?? meta.areas.find((a) => a.id === h.id)?.anchor;
      expect(landmark, h.id).toBeDefined();
      const s = sampleCamera(cam.frames, h.frame);
      const p = projectPoint(s.p, s.q, s.fovY, cam.refAspect, landmark!);
      expect(p.depth, h.id).toBeGreaterThan(0);
      expect(Math.abs(p.ndc[0]), h.id).toBeLessThan(1);
      expect(Math.abs(p.ndc[1]), h.id).toBeLessThan(1);
    }
  });
});
