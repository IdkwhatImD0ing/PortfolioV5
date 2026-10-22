/**
 * Tolerant parsers for the /sect data files. Each takes unknown JSON and returns typed data with
 * defaults for optional keys, or throws a readable error when a required key is missing.
 * Optional keys from the research doc (sky.panorama, fog.baseY, camera.refAspect, ...) are accepted
 * but never required.
 */
import type {
  AreaMeta,
  CameraData,
  ChunkInfo,
  CameraFrame,
  CloudPuff,
  FlyerPath,
  Hold,
  HotspotInfo,
  LightBeam,
  LoreBox,
  PathFrame,
  Quat,
  SectManifest,
  SectMeta,
  Vec3,
  Waterfall,
} from "./types";

type Obj = Record<string, unknown>;

function isObj(v: unknown): v is Obj {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function num(v: unknown, fallback: number): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function str(v: unknown, fallback: string): string {
  return typeof v === "string" && v.length > 0 ? v : fallback;
}

function vec3(v: unknown, fallback: Vec3): Vec3 {
  if (Array.isArray(v) && v.length >= 3 && v.slice(0, 3).every((x) => typeof x === "number")) {
    return [v[0], v[1], v[2]];
  }
  return fallback;
}

function quat(v: unknown, fallback: Quat): Quat {
  if (Array.isArray(v) && v.length >= 4 && v.slice(0, 4).every((x) => typeof x === "number")) {
    return [v[0], v[1], v[2], v[3]];
  }
  return fallback;
}

function requireObj(v: unknown, what: string): Obj {
  if (!isObj(v)) throw new Error(`${what}: expected a JSON object`);
  return v;
}

function strList(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((s): s is string => typeof s === "string" && s.length > 0) : [];
}

function optStr(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}

/** A low-texture list must pair up with its full list one to one, or it is ignored. */
function pairedList(v: unknown, full: readonly string[]): string[] | null {
  const low = strList(v);
  return low.length > 0 && low.length === full.length ? low : null;
}

function parseChunk(v: unknown, i: number): ChunkInfo {
  const o = requireObj(v, `manifest.json chunks[${i}]`);
  const id = typeof o.id === "string" ? o.id.trim() : "";
  if (!id) throw new Error(`manifest.json chunks[${i}]: needs an id`);
  const files = strList(o.files);
  if (files.length === 0) throw new Error(`manifest.json chunk '${id}': 'files' must list at least one GLB`);
  const need = Array.isArray(o.need) ? o.need : [];
  const a = num(need[0], NaN);
  const b = num(need[1], NaN);
  if (!Number.isFinite(a) || !Number.isFinite(b)) throw new Error(`manifest.json chunk '${id}': 'need' must be [firstFrame, lastFrame]`);
  if (b < a) throw new Error(`manifest.json chunk '${id}': 'need' ends (${b}) before it starts (${a})`);
  const bytesLow = num(o.bytesLow, NaN);
  const texBytes = texBytesOf(o.texBytes);
  const texBytesLow = texBytesOf(o.texBytesLow);
  return {
    id,
    files,
    filesLow: pairedList(o.filesLow, files),
    need: [a, b],
    bytes: Math.max(0, num(o.bytes, 0)),
    bytesLow: Number.isFinite(bytesLow) ? Math.max(0, bytesLow) : null,
    tris: Math.max(0, num(o.tris, 0)),
    ...(texBytes !== null ? { texBytes } : {}),
    ...(texBytesLow !== null ? { texBytesLow } : {}),
  };
}

/** A chunk's texture memory: one number, or one per file (summed); null when absent or malformed. */
function texBytesOf(v: unknown): number | null {
  const parts = Array.isArray(v) ? v : [v];
  if (parts.length === 0) return null;
  let sum = 0;
  for (const p of parts) {
    const n = num(p, NaN);
    if (!Number.isFinite(n) || n < 0) return null;
    sum += n;
  }
  return sum > 0 ? sum : null;
}

/**
 * manifest.json. Version 2 lists `global` files and per-area `chunks`; version 1 (the first test,
 * a flat `scene` list) is read as global files with no chunks, so the old test still loads.
 * Throws a readable error for a manifest the page cannot use.
 */
export function parseManifest(raw: unknown): SectManifest {
  const o = requireObj(raw, "manifest.json");
  const detail = optStr(o.detail);
  const common = {
    baked: o.baked === true,
    camera: str(o.camera, "camera.json"),
    meta: str(o.meta, "meta.json"),
    clouds: optStr(o.clouds),
    flyer: optStr(o.flyer),
    flyerPath: optStr(o.flyerPath),
    water: optStr(o.water),
    ...(detail ? { detail } : {}),
  };
  const version = num(o.version, Array.isArray(o.scene) ? 1 : 2);
  if (version < 2) {
    const scene = strList(o.scene);
    if (scene.length === 0) throw new Error("manifest.json: 'scene' must list at least one GLB");
    return { version: 1, ...common, global: scene, globalLow: pairedList(o.sceneLow, scene), chunks: [] };
  }
  const global = strList(o.global);
  const chunks = Array.isArray(o.chunks) ? o.chunks.map(parseChunk) : [];
  if (global.length === 0 && chunks.length === 0) throw new Error("manifest.json: needs 'global' files or 'chunks'");
  const seen = new Set<string>();
  for (const c of chunks) {
    if (seen.has(c.id)) throw new Error(`manifest.json: chunk '${c.id}' is listed twice`);
    seen.add(c.id);
  }
  return { version, ...common, global, globalLow: pairedList(o.globalLow, global), chunks };
}

/**
 * clouds.json: {"puffs": [{"c": [x,y,z], "a": [[ax],[ay],[az]], "d": density, "k"?: tag}, ...]}, three space.
 * Puffs with a malformed centre or axes are dropped rather than failing the page.
 */
export function parseClouds(raw: unknown): CloudPuff[] {
  const o = requireObj(raw, "clouds.json");
  if (!Array.isArray(o.puffs)) return [];
  const out: CloudPuff[] = [];
  for (const v of o.puffs) {
    if (!isObj(v)) continue;
    const c = vec3(v.c, [NaN, NaN, NaN]);
    const a = Array.isArray(v.a) ? v.a.map((x) => vec3(x, [NaN, NaN, NaN])) : [];
    if (c.some(Number.isNaN) || a.length !== 3 || a.some((x) => x.some(Number.isNaN))) continue;
    const puff: CloudPuff = { c, axes: [a[0], a[1], a[2]], density: Math.max(0, num(v.d ?? v.density, 0.4)) };
    if (typeof v.k === "string") puff.kind = v.k;
    out.push(puff);
  }
  return out;
}

/** Resolves a manifest entry against the folder the manifest was served from. */
export function resolveAsset(base: string, file: string): string {
  if (/^(https?:)?\/\//.test(file) || file.startsWith("/")) return file;
  return `${base.replace(/\/+$/, "")}/${file.replace(/^\.\//, "")}`;
}

function parsePathFrame(v: unknown, i: number): PathFrame {
  const o = requireObj(v, `frame ${i}`);
  const p = vec3(o.p, [NaN, NaN, NaN]);
  const q = quat(o.q, [NaN, NaN, NaN, NaN]);
  if (p.some(Number.isNaN) || q.some(Number.isNaN)) throw new Error(`frame ${i}: needs p[3] and q[4]`);
  return { f: num(o.f, i + 1), p, q };
}

/**
 * Sorted by frame number with repeated frame numbers dropped (the first one is kept), so frame
 * numbers strictly increase: path sampling assumes it.
 */
function increasing<T extends { f: number }>(frames: T[], what: string): T[] {
  const sorted = frames.filter((x) => Number.isFinite(x.f)).sort((a, b) => a.f - b.f);
  const out = sorted.filter((x, i) => i === 0 || x.f > sorted[i - 1].f);
  if (out.length < 2) throw new Error(`${what}: needs at least 2 distinct frames`);
  return out;
}

export function parseCameraData(raw: unknown): CameraData {
  const o = requireObj(raw, "camera.json");
  if (!Array.isArray(o.frames) || o.frames.length < 2) throw new Error("camera.json: needs at least 2 frames");
  const frames: CameraFrame[] = increasing(
    o.frames.map((v, i) => {
      const pf = parsePathFrame(v, i);
      return { ...pf, fovY: num((v as Obj).fovY, 35) };
    }),
    "camera.json",
  );
  const frameStart = num(o.frameStart, frames[0].f);
  const frameEnd = num(o.frameEnd, frames[frames.length - 1].f);
  const holds: Hold[] = Array.isArray(o.holds)
    ? o.holds
        .filter(isObj)
        .map((h) => ({ id: str(h.id, "hold"), label: str(h.label, str(h.id, "")), frame: num(h.frame, NaN) }))
        .filter((h) => Number.isFinite(h.frame) && h.frame >= frameStart && h.frame <= frameEnd)
        .sort((a, b) => a.frame - b.frame)
    : [];
  const startFrame = Math.min(Math.max(num(o.startFrame, frameStart), frameStart), frameEnd);
  return {
    fps: num(o.fps, 24),
    frameStart,
    frameEnd,
    frames,
    holds,
    startFrame,
    refAspect: num(o.refAspect, num(o.aspect, 16 / 9)),
    near: num(o.near, 0.1),
    far: num(o.far, 9000),
  };
}

export function parseFlyerPath(raw: unknown): FlyerPath {
  const o = requireObj(raw, "flyer.json");
  if (!Array.isArray(o.frames) || o.frames.length < 2) throw new Error("flyer.json: needs at least 2 frames");
  const frames = increasing(o.frames.map(parsePathFrame), "flyer.json");
  return {
    frameStart: num(o.frameStart, frames[0].f),
    frameEnd: num(o.frameEnd, frames[frames.length - 1].f),
    frames,
  };
}

const DEFAULT_META: SectMeta = {
  sun: { direction: [-0.944, 0.122, 0.307], color: "#ffbf84" },
  sky: {
    zenith: "#2d5785",
    horizon: "#918c96",
    horizonSun: "#d2b7a1",
    belowHorizon: "#90898d",
    texture: null,
    asRenderedTop: null,
  },
  fog: { color: "#84889e", scatterColor: "#fff6ec", density: 0.0003, baseY: 100, falloff: 220 },
  moon: null,
  cloudSea: { y: -60, billowTopY: -45, fogTopY: 20, fogBottomY: -90, color: "#e9c9a8", extent: 9000 },
  waterfalls: [],
  beams: [],
  hotspots: [],
  lore: [],
  areas: [],
  vignette: 0.22,
  exposure: 0.25,
};

function corners4(v: unknown): [Vec3, Vec3, Vec3, Vec3] | null {
  if (!Array.isArray(v) || v.length !== 4) return null;
  const c = v.map((x) => vec3(x, [NaN, NaN, NaN]));
  return c.some((x) => x.some(Number.isNaN)) ? null : [c[0], c[1], c[2], c[3]];
}

function normalize3(v: Vec3): Vec3 {
  const l = Math.hypot(v[0], v[1], v[2]);
  return l > 1e-9 ? [v[0] / l, v[1] / l, v[2] / l] : [0, 1, 0];
}

export function parseMeta(raw: unknown): SectMeta {
  const o = requireObj(raw, "meta.json");
  const d = DEFAULT_META;
  const sun = isObj(o.sun) ? o.sun : {};
  const sky = isObj(o.sky) ? o.sky : {};
  const asRendered = isObj(sky.asRendered) ? sky.asRendered : {};
  const fog = isObj(o.fog) ? o.fog : {};
  const moon = isObj(o.moon) ? o.moon : null;
  const halo = moon && isObj(moon.halo) ? moon.halo : null;
  const cloud = isObj(o.cloudSea) ? o.cloudSea : {};
  const tone = isObj(o.toneMapping) ? o.toneMapping : {};

  const waterfalls: Waterfall[] = Array.isArray(o.waterfalls)
    ? o.waterfalls.filter(isObj).map((w, i) => ({
        name: str(w.name, `waterfall.${i}`),
        kind: str(w.kind, "sheet"),
        position: vec3(w.position, [0, 0, 0]),
        size: vec3(w.size, [1, 1, 1]),
        rotation: quat(w.rotation, [0, 0, 0, 1]),
        nearestM: num(w.nearestM, Infinity),
        corners: corners4(w.corners),
        foot: Array.isArray(w.foot) ? vec3(w.foot, [0, 0, 0]) : null,
        flow: num(w.flow, 1),
        chunk: optStr(w.chunk),
      }))
    : [];

  const beams: LightBeam[] = Array.isArray(o.beams)
    ? o.beams
        .filter(isObj)
        .map((b, i) => ({
          name: str(b.name, `beam.${i}`),
          base: vec3(b.base, [NaN, NaN, NaN]),
          top: vec3(b.top, [NaN, NaN, NaN]),
          radius: Math.max(0, num(b.radius, 1)),
          color: str(b.color, "#9ff3ff"),
          nearestM: num(b.nearestM, Infinity),
          chunk: optStr(b.chunk),
        }))
        .filter(
          (b) =>
            !b.base.some(Number.isNaN) &&
            !b.top.some(Number.isNaN) &&
            Math.hypot(b.top[0] - b.base[0], b.top[1] - b.base[1], b.top[2] - b.base[2]) > 1e-3,
        )
    : [];

  const hotspots: HotspotInfo[] = Array.isArray(o.hotspots)
    ? o.hotspots
        .filter(isObj)
        .filter((h) => typeof h.id === "string" && h.id.length > 0)
        .map((h) => ({
          id: h.id as string,
          label: str(h.label, h.id as string),
          center: vec3(h.center, [0, 0, 0]),
          size: vec3(h.size, [1, 1, 1]),
          area: optStr(h.area),
          chunk: optStr(h.chunk),
        }))
    : [];

  // The Jin Yong references (export_web.py LORE): one entry per reference with its boxes, flattened
  // to one LoreBox per box. A box without a usable centre and size is dropped.
  const lore: LoreBox[] = Array.isArray(o.lore)
    ? o.lore
        .filter(isObj)
        .filter((e) => typeof e.id === "string" && e.id.length > 0)
        .flatMap((e) => {
          const boxes = Array.isArray(e.boxes) ? e.boxes.filter(isObj) : [e];
          return boxes.map((b) => ({
            id: e.id as string,
            center: vec3(b.center, [NaN, NaN, NaN]),
            size: vec3(b.size, [NaN, NaN, NaN]),
            host: optStr(b.hotspot),
            area: optStr(e.area),
          }));
        })
        .filter((b) => ![...b.center, ...b.size].some((x) => !Number.isFinite(x)) && b.size.every((x) => x >= 0))
    : [];

  const areas: AreaMeta[] = Array.isArray(o.areas)
    ? o.areas
        .filter(isObj)
        .filter((a) => typeof a.id === "string" && a.id.length > 0)
        .map((a) => {
          const frameStart = num(a.frameStart, 0);
          const frameEnd = num(a.frameEnd, frameStart);
          return {
            id: a.id as string,
            label: str(a.label, a.id as string),
            anchor: vec3(a.anchor, [0, 0, 0]),
            footprint: Math.max(0, num(a.footprint, 40)),
            frameStart,
            frameEnd,
            heroFrame: num(a.heroFrame, (frameStart + frameEnd) / 2),
          };
        })
    : [];

  return {
    sun: {
      direction: normalize3(vec3(sun.direction ?? sun.dir, d.sun.direction)),
      color: str(sun.color, d.sun.color),
    },
    sky: {
      zenith: str(sky.zenith, d.sky.zenith),
      horizon: str(sky.horizon, d.sky.horizon),
      horizonSun: str(sky.horizonSun, d.sky.horizonSun),
      belowHorizon: str(sky.belowHorizon, d.sky.belowHorizon),
      texture:
        typeof sky.panorama === "string" && sky.panorama
          ? sky.panorama
          : typeof sky.texture === "string" && sky.texture
            ? sky.texture
            : null,
      asRenderedTop: typeof asRendered.top === "string" ? asRendered.top : null,
    },
    fog: {
      color: str(fog.color, d.fog.color),
      scatterColor: str(fog.scatterColor, d.fog.scatterColor),
      density: num(fog.density, d.fog.density),
      baseY: num(fog.baseY, d.fog.baseY),
      falloff: Math.max(1, num(fog.falloff, d.fog.falloff)),
    },
    moon: moon
      ? {
          position: vec3(moon.position, [0, 1000, -6000]),
          radius: num(moon.radius, num(moon.size, 500)),
          color: str(moon.color, "#e9edf5"),
          halo: halo ? { position: vec3(halo.position, [0, 1000, -6000]), radius: num(halo.radius, 1000) } : null,
        }
      : null,
    cloudSea: {
      y: num(cloud.y, d.cloudSea.y),
      billowTopY: num(cloud.billowTopY, d.cloudSea.billowTopY),
      fogTopY: num(cloud.fogTopY, d.cloudSea.fogTopY),
      fogBottomY: num(cloud.fogBottomY, d.cloudSea.fogBottomY),
      color: str(cloud.color, d.cloudSea.color),
      extent: num(cloud.extent, d.cloudSea.extent),
    },
    waterfalls,
    beams,
    hotspots,
    lore,
    areas,
    vignette: num(tone.vignette, d.vignette),
    exposure: num(tone.exposure, d.exposure),
  };
}
