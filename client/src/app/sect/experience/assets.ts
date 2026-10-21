/**
 * Loading for /sect. The data files (manifest, camera, meta, clouds, flyer path) come first, then
 * "sets" of GLBs: the global set (backdrop with a reduced proxy of every area) once, and one set per
 * streamed chunk, loaded and disposed as the camera moves (streaming.ts decides when).
 *
 * Everything a set needs from the others (the waterfall shaders, the sky, hotspot entries, merge
 * cells, fog-aware overlay decor) lives in one WorldContext made once per page.
 *
 * GLBs are fetched as bytes (a ".glb.gz" is inflated with DecompressionStream), so downloads can be
 * cancelled and report progress, then parsed with GLTFLoader.parseAsync.
 */
import {
  Box3,
  BufferAttribute,
  BufferGeometry,
  Color,
  EquirectangularReflectionMapping,
  Group,
  ImageBitmapLoader,
  ImageLoader,
  InstancedBufferAttribute,
  InstancedBufferGeometry,
  type InstancedMesh,
  type IUniform,
  LinearFilter,
  type Material,
  Mesh,
  type MeshBasicMaterial,
  NoColorSpace,
  type Object3D,
  PlaneGeometry,
  RepeatWrapping,
  SphereGeometry,
  SRGBColorSpace,
  type ShaderMaterial,
  Texture,
  TextureLoader,
  Vector3,
} from "three";
import { type GLTF, GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";
import { pathCellKey } from "@/lib/sect/cells";
import { isCutoutCard } from "@/lib/sect/card-shading";
import { detailWanted, rockFarOctaves } from "@/lib/sect/detail";
import { FORMATION_DOME, formationShafts, formationTier, isFormationLinkBeam, type FormationTierName } from "@/lib/sect/formation";
import { applyLook, lookFogConstants, SECT_LOOK } from "@/lib/sect/look";
import { parseCameraData, parseClouds, parseFlyerPath, parseManifest, parseMeta, resolveAsset } from "@/lib/sect/parse";
import { combinedProgress, isGzip, meshoptWorkerCount, type Tier } from "@/lib/sect/runtime";
import type { CameraData, ChunkInfo, CloudPuff, FlyerPath, SectManifest, SectMeta, Waterfall } from "@/lib/sect/types";
import { discFromBox, dominantFlatLevel, groundedFalls, mistSpots, quadFromCorners, type WaterSurface } from "@/lib/sect/water";
import { fxAssetUrl, SHEET, sheetFallAttribute, WET, wetFalls } from "@/lib/sect/waterfall";
import {
  bakedDetail,
  createBeamMaterial,
  createDetailUniforms,
  createDomeMaterial,
  createMistMaterial,
  createShaftMaterial,
  createWaterfallMaterial,
  createWaterfallSheetMaterial,
  createWaterUniforms,
  createWetRock,
  patchMaterial,
  setCardAlphaMode,
  setSheetStrands,
  standInExposure,
  type DetailUniforms,
  type WaterUniforms,
  type WetRock,
} from "./materials";
import { IDLE_ON, planIdleSliced, type IdlePlan } from "./idle";
import {
  disposeObjects,
  measureHotspots,
  prepareScene,
  prepareSceneSliced,
  releaseAfterGpuUpload,
  triangleCount,
  type HotspotEntry,
  type PrepareResult,
  type SliceOptions,
  yieldToBrowser,
} from "./prepare";

export interface SectData {
  base: string;
  manifest: SectManifest;
  camera: CameraData;
  /** meta.json with the web look's colours applied (lib/sect/look.ts). */
  meta: SectMeta;
  flyerPath: FlyerPath | null;
  clouds: CloudPuff[];
}

/**
 * Waits before the second and third try of a file the page cannot start without (the data files and
 * the global set's GLBs): a dropped connection or a server restarting is usually back within seconds.
 * Streamed chunks retry on their own schedule (streaming.ts).
 */
export const FILE_RETRY_MS: readonly number[] = [1000, 3000];

/** Waits `ms`, or rejects as soon as `signal` aborts. */
function pause(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(signal.reason);
    const t = setTimeout(done, ms);
    function done() {
      signal?.removeEventListener("abort", stop);
      resolve();
    }
    function stop() {
      clearTimeout(t);
      reject(signal?.reason);
    }
    signal?.addEventListener("abort", stop, { once: true });
  });
}

/**
 * Runs `fn`, and again after each wait in `delays` while it fails (not once `signal` has aborted):
 * the last failure is thrown.
 */
export async function withRetries<T>(fn: () => Promise<T>, delays: readonly number[], signal?: AbortSignal, what = "a file"): Promise<T> {
  for (let i = 0; ; i++) {
    try {
      return await fn();
    } catch (e) {
      if (signal?.aborted || i >= delays.length) throw e;
      console.warn(`[sect] ${what} failed; trying again in ${delays[i] / 1000} s`, e);
      await pause(delays[i], signal);
    }
  }
}

async function fetchJson(url: string, signal?: AbortSignal): Promise<unknown> {
  return withRetries(
    async () => {
      const res = await fetch(url, { cache: "no-cache", signal });
      if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
      return res.json();
    },
    FILE_RETRY_MS,
    signal,
    url,
  );
}

export async function loadSectData(base: string, wantFlyer: boolean, signal?: AbortSignal): Promise<SectData> {
  const manifest = parseManifest(await fetchJson(resolveAsset(base, "manifest.json"), signal));
  const [cameraRaw, metaRaw, flyerRaw, cloudsRaw] = await Promise.all([
    fetchJson(resolveAsset(base, manifest.camera), signal),
    fetchJson(resolveAsset(base, manifest.meta), signal),
    wantFlyer && manifest.flyer && manifest.flyerPath ? fetchJson(resolveAsset(base, manifest.flyerPath), signal).catch(() => null) : Promise.resolve(null),
    // Clouds are decoration: a missing or broken file leaves the sky clear rather than failing.
    manifest.clouds ? fetchJson(resolveAsset(base, manifest.clouds), signal).catch(() => null) : Promise.resolve(null),
  ]);
  return {
    base,
    manifest,
    camera: parseCameraData(cameraRaw),
    meta: applyLook(parseMeta(metaRaw)),
    flyerPath: flyerRaw ? parseFlyerPath(flyerRaw) : null,
    clouds: cloudsRaw ? parseClouds(cloudsRaw) : [],
  };
}

// ---------------------------------------------------------------------------------------------

export interface PondReflection {
  /** Water plane height (three y). */
  level: number;
  /** World box of the pond (to skip the reflection render when it is off screen). */
  box: Box3;
  /** Uniforms of the pond's water materials (tReflect, uHasReflect, uReflectMatrix). */
  uniforms: WaterUniforms[];
  /** The meshes the pond reflects (the Heart-Mirror). */
  mirrorMeshes: Mesh[];
}

/** Shared by every set the page loads. Made once per page (createWorldContext). */
export interface WorldContext {
  data: SectData;
  exposure: number;
  waterfallMaterial: ShaderMaterial;
  sheetMaterial: ShaderMaterial;
  /** Wet rock beside the nearest falls (baked materials): call update(camera position) every frame. */
  wetRock: WetRock;
  sky: Texture | null;
  /** Every hotspot the page knows: meta.json's, plus the ones found in loaded GLBs. */
  hotspotMap: Map<string, HotspotEntry>;
  cellKey: (x: number, y: number, z: number) => string;
  sunDir: Vector3;
  /** Mist at waterfall feet and the light beams (global, one instanced draw each). */
  overlay: Object3D[];
  /** Load-time settings (MSAA changes re-patch the card materials of loaded sets). */
  shadows: boolean;
  alphaToCoverage: boolean;
  lowTextures: boolean;
  /**
   * The tiling detail texture for baked rock and ground (manifest.detail), shared by every set;
   * null when the manifest has none or on the low tier (no detail patch at all).
   */
  detail: DetailUniforms | null;
}

/** A group of GLBs prepared together: the global set, or one chunk. */
export interface LoadedSet {
  /** "global" or the chunk (area) id. */
  id: string;
  /** Need range for a chunk; null for the global set (always drawn). */
  need: [number, number] | null;
  scenes: Object3D[];
  hotspotMeshes: Map<string, Mesh[]>;
  cardMaterials: MeshBasicMaterial[];
  /** Backdrop meshes standing in for an area, by area id (global set only in practice). */
  proxies: Map<string, Mesh[]>;
  pond: PondReflection | null;
  litMaterials: number;
  waterfallMeshes: number;
  bytes: number;
  /** Triangles in the set's meshes (instances counted). */
  tris: number;
  /** Textures to upload before the set is first drawn. */
  textures: Texture[];
  /** Textures uploaded and shaders compiled: the set may be drawn. */
  ready: boolean;
  /** Set by the render loop: drawn this frame. */
  drawn: boolean;
  /** What idles while the chunk is drawn (idle.ts); absent for the global set. */
  idle?: IdlePlan;
  /**
   * The streamer dropped it (its GPU copies are freed, or about to be). The canvas's own React root
   * may still list it for a frame or two after the drop; it must never be drawn again (its images
   * were closed after upload, so a redraw would upload empty textures).
   */
  dropped?: boolean;
  /** disposeSet has freed its GPU copies (it is dropped too). */
  freed?: boolean;
}

let gltfLoader: GLTFLoader | null = null;
function getLoader(): GLTFLoader {
  if (!gltfLoader) {
    gltfLoader = new GLTFLoader();
    // Decode the compressed geometry in workers: on the main thread each chunk's buffers blocked it
    // for 8-29 ms at a time, mid-flight. The decoder starts its workers from a blob: URL and runs
    // WebAssembly in them; the site sends no Content-Security-Policy (next.config.ts sets no
    // headers), so nothing blocks either. If one is ever added, it needs worker-src blob: and
    // 'wasm-unsafe-eval'. A blocked worker fails silently (it never answers, and three's decoder
    // would wait forever), so the first decode waits for a test request: when the workers do not
    // answer it in time, they are stopped and decoding stays on the main thread.
    // (Renamed: the React lint rules take any `useX()` call for a hook. It needs no `this`.)
    const { useWorkers: startWorkers } = MeshoptDecoder;
    let checked: Promise<void> = Promise.resolve();
    try {
      startWorkers(meshoptWorkerCount(typeof navigator !== "undefined" ? navigator.hardwareConcurrency : undefined));
      checked = checkMeshoptWorkers(() => startWorkers(0));
    } catch (e) {
      console.warn("[sect] meshopt workers unavailable; decoding on the main thread", e);
    }
    gltfLoader.setMeshoptDecoder({
      ...MeshoptDecoder,
      decodeGltfBufferAsync: (count, size, source, mode, filter) => checked.then(() => MeshoptDecoder.decodeGltfBufferAsync(count, size, source, mode, filter)),
    });
  }
  return gltfLoader;
}

/** How long the meshopt workers get to answer their test request (start-up and WebAssembly). */
const MESHOPT_WORKER_CHECK_MS = 3000;

/**
 * Sends the workers a tiny request (a malformed one: any answer, a decode or an error, shows they
 * run). No answer in time means they are blocked: `stop` shuts them so decoding falls back to the
 * main thread. Always resolves.
 */
function checkMeshoptWorkers(stop: () => void): Promise<void> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const answered = MeshoptDecoder.decodeGltfBufferAsync(1, 4, new Uint8Array(1), "ATTRIBUTES", "NONE").then(
    () => true,
    () => true,
  );
  const late = new Promise<boolean>((resolve) => {
    timer = setTimeout(() => resolve(false), MESHOPT_WORKER_CHECK_MS);
  });
  return Promise.race([answered, late]).then((ok) => {
    clearTimeout(timer);
    if (ok) return;
    console.warn("[sect] meshopt workers did not answer; decoding on the main thread");
    stop();
  });
}

/** Bytes of a URL with progress (Content-Length), cancellable. */
async function fetchBytes(url: string, signal: AbortSignal | undefined, onBytes: (loaded: number, total: number) => void): Promise<Uint8Array> {
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  const total = Number(res.headers.get("content-length") ?? 0) || 0;
  if (!res.body) {
    const b = new Uint8Array(await res.arrayBuffer());
    onBytes(b.length, b.length);
    return b;
  }
  const reader = res.body.getReader();
  const parts: Uint8Array[] = [];
  let loaded = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    parts.push(value);
    loaded += value.length;
    onBytes(loaded, total);
  }
  const out = new Uint8Array(loaded);
  let o = 0;
  for (const p of parts) {
    out.set(p, o);
    o += p.length;
  }
  return out;
}

/** Inflates gzip bytes on this thread (the worker's fallback). */
function inflateHere(bytes: Uint8Array): Promise<ArrayBuffer> {
  const stream = new Blob([bytes as BlobPart]).stream().pipeThrough(new DecompressionStream("gzip"));
  return new Response(stream).arrayBuffer();
}

/**
 * The gunzip worker: inflating an area's 8.7 MB file on the main thread froze a phone-class CPU
 * for 106-138 ms (24-34 ms on a desktop), once per file. It takes the bytes and hands back the
 * inflated buffer, both transferred rather than copied. Started from a blob: URL like the meshopt
 * decoder's workers (getLoader). It says "ready" first; until it has, nothing is sent (a transferred
 * buffer is gone from this side), and a worker that never says so (a Content-Security-Policy without
 * worker-src blob:) leaves inflating on the main thread for the rest of the visit. It stops when
 * idle for INFLATER_IDLE_MS and starts again on demand.
 */
const INFLATE_WORKER = `
self.onmessage = async (e) => {
  const { id, bytes } = e.data;
  try {
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
    const out = await new Response(stream).arrayBuffer();
    self.postMessage({ id, out }, [out]);
  } catch (err) {
    self.postMessage({ id, error: String((err && err.message) || err) });
  }
};
self.postMessage({ ready: true });
`;
const INFLATER_START_MS = 3000;
const INFLATER_IDLE_MS = 30_000;

interface Inflater {
  worker: Worker;
  started: Promise<boolean>;
  jobs: Map<number, { resolve: (b: ArrayBuffer) => void; reject: (e: unknown) => void }>;
  next: number;
  idle: ReturnType<typeof setTimeout> | undefined;
}
let inflater: Inflater | null = null;
/** Workers cannot run here (or one never started): inflate on the main thread from now on. */
let inflaterBlocked = false;

function stopInflater(why: unknown): void {
  const w = inflater;
  if (!w) return;
  inflater = null;
  clearTimeout(w.idle);
  w.worker.terminate();
  for (const j of w.jobs.values()) j.reject(why);
}

function startInflater(): Inflater | null {
  if (inflater) return inflater;
  if (inflaterBlocked || typeof Worker === "undefined" || typeof URL.createObjectURL !== "function") return null;
  let worker: Worker;
  try {
    const url = URL.createObjectURL(new Blob([INFLATE_WORKER], { type: "text/javascript" }));
    worker = new Worker(url);
    URL.revokeObjectURL(url);
  } catch (e) {
    console.warn("[sect] gunzip worker unavailable; inflating on the main thread", e);
    inflaterBlocked = true;
    return null;
  }
  let said: (ok: boolean) => void = () => {};
  const w: Inflater = {
    worker,
    started: new Promise<boolean>((resolve) => {
      said = resolve;
      setTimeout(() => resolve(false), INFLATER_START_MS);
    }),
    jobs: new Map(),
    next: 1,
    idle: undefined,
  };
  worker.onmessage = (e: MessageEvent<{ ready?: boolean; id?: number; out?: ArrayBuffer; error?: string }>) => {
    const d = e.data;
    if (d.ready) return said(true);
    const job = d.id !== undefined ? w.jobs.get(d.id) : undefined;
    if (!job || d.id === undefined) return;
    w.jobs.delete(d.id);
    if (d.out) job.resolve(d.out);
    else job.reject(new Error(d.error ?? "gunzip failed"));
    if (w.jobs.size === 0) {
      clearTimeout(w.idle);
      w.idle = setTimeout(() => {
        if (inflater === w && w.jobs.size === 0) stopInflater(new Error("stopped"));
      }, INFLATER_IDLE_MS);
    }
  };
  worker.onerror = (e) => {
    e.preventDefault();
    said(false);
    if (inflater === w) stopInflater(new Error("the gunzip worker failed"));
  };
  inflater = w;
  return w;
}

/** Inflates gzip bytes (a ".glb.gz"), off the main thread where it can; other bytes (the host already decoded them) pass through. */
async function inflate(bytes: Uint8Array): Promise<ArrayBuffer> {
  if (!isGzip(bytes)) return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
  if (typeof DecompressionStream === "undefined") throw new Error("this browser cannot unpack the scene files (no DecompressionStream)");
  const w = startInflater();
  if (!w || !(await w.started)) {
    if (w && inflater === w) {
      console.warn("[sect] the gunzip worker did not start; inflating on the main thread");
      inflaterBlocked = true;
      stopInflater(new Error("not started"));
    }
    return inflateHere(bytes);
  }
  if (inflater !== w) return inflateHere(bytes);
  // Transferred whole: fetchBytes makes a buffer of exactly these bytes (copy anything else first).
  const own = bytes.byteOffset === 0 && bytes.byteLength === bytes.buffer.byteLength ? bytes : bytes.slice();
  const id = w.next++;
  clearTimeout(w.idle);
  return new Promise<ArrayBuffer>((resolve, reject) => {
    w.jobs.set(id, { resolve, reject });
    w.worker.postMessage({ id, bytes: own }, [own.buffer]);
  });
}

async function loadGlb(
  url: string,
  signal: AbortSignal | undefined,
  onBytes: (l: number, t: number) => void,
  calm?: () => Promise<void>,
): Promise<{ gltf: GLTF; bytes: number }> {
  const bytes = await fetchBytes(url, signal, onBytes);
  const size = bytes.length;
  const buf = await inflate(bytes);
  signal?.throwIfAborted();
  // Parsing builds the meshes on the main thread: a prefetch downloaded mid-flight waits here.
  if (calm) await calm();
  signal?.throwIfAborted();
  const gltf = await getLoader().parseAsync(buf, url.slice(0, url.lastIndexOf("/") + 1));
  await loadCardAlpha(gltf);
  return { gltf, bytes: size };
}

/**
 * Needle and twig cards (extras.cardAlpha = "needle" | "twig") carry their cut-out as the occlusion
 * texture on TEXCOORD_1, which GLTFLoader leaves out of unlit materials. Loads it as the material's
 * aoMap (through the parser, so the UV set and any texture transform apply, and as data: no colour
 * space, so a twig's R detail and G coverage read raw); prepareScene moves it to the alpha map. A
 * failed image leaves the needles opaque rather than failing the file.
 */
export async function loadCardAlpha(gltf: GLTF): Promise<void> {
  const { parser } = gltf;
  const defs = (parser.json?.materials ?? []) as { occlusionTexture?: { index: number; texCoord?: number; extensions?: unknown } }[];
  const seen = new Set<Material>();
  const jobs: Promise<void>[] = [];
  gltf.scene.traverse((o) => {
    const mesh = o as Mesh;
    if (!mesh.isMesh) return;
    for (const mat of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
      const b = mat as MeshBasicMaterial;
      if (!b || seen.has(b) || !isCutoutCard(b.userData) || b.aoMap || b.alphaMap) continue;
      seen.add(b);
      // Clones the loader made (flat shading) keep their source material's index.
      const index = parser.associations.get(b)?.materials;
      const def = index !== undefined ? defs[index]?.occlusionTexture : undefined;
      if (!def) continue;
      const params: { aoMap?: Texture | null } = {};
      jobs.push(
        parser
          .assignTexture(params, "aoMap", def)
          .then(() => {
            if (!params.aoMap) return;
            b.aoMap = params.aoMap;
            b.needsUpdate = true;
          })
          .catch((e) => console.warn(`[sect] card alpha for ${b.name} failed to load`, e)),
      );
    }
  });
  await Promise.all(jobs);
}

/** Waterfall quads from meta corners, for sets without water geometry. */
function waterfallQuads(falls: readonly Waterfall[], material: Material): Group | null {
  const g = new Group();
  g.name = "sect.waterfalls";
  falls.forEach((w, k) => {
    if (w.kind !== "sheet" || w.nearestM > 2500 || !w.corners) return;
    const q = quadFromCorners(w.corners);
    const geo = new BufferGeometry();
    geo.setAttribute("position", new BufferAttribute(q.positions, 3));
    geo.setAttribute("uv", new BufferAttribute(q.uvs, 2));
    geo.setIndex(new BufferAttribute(q.index, 1));
    // As the water GLBs carry them: a seed, the flow / 2, the layer (0: core). aFall follows in prepareWaterSheets.
    const seed = ((k * 0.618034) % 1 + 1) % 1;
    const col = [seed, Math.min(w.flow / 2, 1), 0];
    geo.setAttribute("color", new BufferAttribute(new Float32Array([...col, ...col, ...col, ...col]), 3));
    const m = new Mesh(geo, material);
    m.renderOrder = 2;
    m.name = w.name;
    g.add(m);
  });
  return g.children.length > 0 ? g : null;
}

/** An overlay object's own response to the fx tier (userData.sectTier): see setOverlayTier. */
type TierTune = (tier: FormationTierName) => void;

/**
 * Moves the overlay's tiered pieces to an fx tier (water.ts fxTier: high, mid or low): the
 * formation's barrier keeps its shimmer on High and Medium, its core shaft its halo on High and
 * its streaks off Low. Cheap (uniforms and instance counts), so it follows the frame ladder too.
 */
export function setOverlayTier(objects: readonly Object3D[] | undefined, tier: FormationTierName): void {
  for (const o of objects ?? []) (o.userData.sectTier as TierTune | undefined)?.(tier);
}

/**
 * Mist at the waterfall feet that land on the terrain, the formation's barrier and its shafts of
 * light, and any light beams left: one instanced draw each. Exported for the tests.
 */
export function overlayDecor(meta: SectMeta, time: ShaderMaterial["uniforms"][string]): Object3D[] {
  const fog = lookFogConstants(meta);
  const out: Object3D[] = [];
  // Only feet on an area's ground: an island's fall that stops above the clouds gets no mist.
  const spots = mistSpots(groundedFalls(meta.waterfalls, meta.areas, meta.cloudSea.fogTopY), meta.cloudSea.fogTopY);
  if (spots.length > 0) {
    const quad = new PlaneGeometry(2, 2);
    const geo = new InstancedBufferGeometry();
    geo.setIndex(quad.getIndex());
    geo.setAttribute("position", quad.getAttribute("position"));
    geo.setAttribute("iCenter", new InstancedBufferAttribute(new Float32Array(spots.flatMap((s) => s.position)), 3));
    geo.setAttribute("iRadius", new InstancedBufferAttribute(new Float32Array(spots.map((s) => s.radius)), 1));
    geo.instanceCount = spots.length;
    const m = new Mesh(geo, createMistMaterial(fog, meta.fog.color, time));
    m.frustumCulled = false;
    m.renderOrder = 4;
    m.name = "sect.mist";
    out.push(m);
  }
  // The formation's dome, on the plaza (the area's anchor), as blender/xianxia-sect/sect/areas/
  // formation.py builds it: shield_dome(radius=R_PLAZA - 0.1, height=50).
  const plaza = meta.areas.find((a) => a.id === FORMATION_DOME.area)?.anchor;
  if (plaza) {
    const geo = new SphereGeometry(1, 96, 24, 0, Math.PI * 2, 0, Math.PI / 2);
    const material = createDomeMaterial(fog, SECT_LOOK.formation.dome.color, time, IDLE_ON);
    const m = new Mesh(geo, material);
    m.position.set(plaza[0], plaza[1], plaza[2]);
    m.scale.set(FORMATION_DOME.radius, FORMATION_DOME.height, FORMATION_DOME.radius);
    m.updateMatrixWorld(true);
    m.renderOrder = 6;
    m.name = "sect.dome";
    const tune: TierTune = (tier) => {
      material.uniforms.uDetail.value = formationTier(tier).domeDetail;
    };
    m.userData.sectTier = tune;
    out.push(m);
  }
  // Soft shafts from the formation's core and its eight array eyes, placed from the hotspots (so
  // before and after the Blender rebake alike); they replace the formation's neon link beams.
  const shafts = formationShafts(meta.hotspots);
  if (shafts.length > 0) {
    const quad = new PlaneGeometry(2, 2);
    const geo = new InstancedBufferGeometry();
    geo.setIndex(quad.getIndex());
    geo.setAttribute("position", quad.getAttribute("position"));
    geo.setAttribute("iBase", new InstancedBufferAttribute(new Float32Array(shafts.flatMap((s) => s.base)), 3));
    geo.setAttribute("iShape", new InstancedBufferAttribute(new Float32Array(shafts.flatMap((s) => [s.look.height, s.look.fadeIn, s.look.halfLife, s.look.radius])), 4));
    geo.setAttribute("iLook", new InstancedBufferAttribute(new Float32Array(shafts.flatMap((s) => [s.look.opacity, s.look.streaks, s.phase, s.rest])), 4));
    geo.setAttribute("iColor", new InstancedBufferAttribute(new Float32Array(shafts.flatMap((s) => new Color(s.look.color).toArray() as number[])), 3));
    geo.instanceCount = shafts.length;
    const material = createShaftMaterial(fog, time, IDLE_ON);
    const m = new Mesh(geo, material);
    m.frustumCulled = false;
    m.renderOrder = 5;
    m.name = "sect.shafts";
    // The halo is last: a tier without it draws one instance less.
    const withHalo = shafts.length;
    const withoutHalo = shafts.filter((s) => s.kind !== "halo").length;
    const tune: TierTune = (tier) => {
      const t = formationTier(tier);
      geo.instanceCount = t.halo ? withHalo : withoutHalo;
      material.uniforms.uStreaks.value = t.streaks;
    };
    m.userData.sectTier = tune;
    out.push(m);
  }
  // The formation's link beams and sky pillar are gone (the shafts above stand for them).
  const beams = meta.beams.filter((b) => b.nearestM < 2500 && !isFormationLinkBeam(b.name));
  if (beams.length > 0) {
    const quad = new PlaneGeometry(2, 2);
    const geo = new InstancedBufferGeometry();
    geo.setIndex(quad.getIndex());
    geo.setAttribute("position", quad.getAttribute("position"));
    geo.setAttribute("iBase", new InstancedBufferAttribute(new Float32Array(beams.flatMap((b) => b.base)), 3));
    geo.setAttribute("iTop", new InstancedBufferAttribute(new Float32Array(beams.flatMap((b) => b.top)), 3));
    geo.setAttribute("iRadius", new InstancedBufferAttribute(new Float32Array(beams.map((b) => Math.max(0.6, b.radius))), 1));
    const cols = beams.flatMap((b) => new Color(b.color).toArray() as number[]);
    geo.setAttribute("iColor", new InstancedBufferAttribute(new Float32Array(cols), 3));
    geo.instanceCount = beams.length;
    const m = new Mesh(geo, createBeamMaterial(fog, meta.fog.color, time));
    m.frustumCulled = false;
    m.renderOrder = 5;
    m.name = "sect.beams";
    out.push(m);
  }
  return out;
}

/** World-space positions of a mesh as a flat xyz array (quantized attributes are decoded). */
function worldPositions(mesh: Mesh): Float32Array {
  const pos = mesh.geometry.getAttribute("position");
  const out = new Float32Array(pos.count * 3);
  const v = new Vector3();
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i).applyMatrix4(mesh.matrixWorld);
    out[i * 3] = v.x;
    out[i * 3 + 1] = v.y;
    out[i * 3 + 2] = v.z;
  }
  return out;
}

const POND_HOTSPOT = "mirror-pond";
const MIRROR_HOTSPOT = "mirror";

/**
 * The bake has no reflections. Give the Still Pond one: its water level is the largest level
 * surface in the pond hotspot, and the water shader draws the Heart-Mirror in it as an analytic
 * glowing disc (round and soft, like the film's). A planar render of the mirror's meshes was tried
 * and dropped: at 512 px, cut by the shader's dark-water test, it came out as a torn blob with a
 * red fringe, and it cost a second scene render every frame.
 */
function addPondReflection(
  hotspotMeshes: Map<string, Mesh[]>,
  hotspots: Map<string, HotspotEntry>,
  exposure: number,
  detail: DetailUniforms | null,
  cards: ReadonlySet<Material>,
): PondReflection | null {
  const pond = hotspotMeshes.get(POND_HOTSPOT);
  if (!pond || pond.length === 0) return null;
  let best: { level: number; area: number } | null = null;
  for (const m of pond) {
    m.updateMatrixWorld(true);
    const lvl = dominantFlatLevel(worldPositions(m), m.geometry.index ? m.geometry.index.array : null);
    if (lvl && (!best || lvl.area > best.area)) best = lvl;
  }
  if (!best || best.area < 20) return null;
  const mirror = hotspotMeshes.get(MIRROR_HOTSPOT) ?? [];
  const glow = mirror.filter((m) => {
    const c = (m.material as MeshBasicMaterial).color;
    return c !== undefined && Math.max(c.r, c.g, c.b) > 1.001;
  });
  const pondBox = new Box3();
  for (const m of pond) pondBox.expandByObject(m);
  let disc: WaterSurface["disc"] = null;
  if (glow.length > 0) {
    const box = new Box3();
    for (const m of glow) box.expandByObject(m);
    disc = discFromBox(box.min.toArray(), box.max.toArray(), pondBox.getCenter(new Vector3()).toArray());
  }
  const surface: WaterSurface = { level: best.level, disc };
  const done = new Set<Material>();
  const uniforms: WaterUniforms[] = [];
  for (const m of pond) {
    const mat = m.material as Material;
    // Tree cards are not water, and a re-patch would drop their card patch.
    if (done.has(mat) || cards.has(mat)) continue;
    done.add(mat);
    const u = createWaterUniforms(surface);
    uniforms.push(u);
    // Re-patched with the water; a rock or ground copy keeps its detail.
    patchMaterial(mat, { lit: true, exposure, highlight: hotspots.get(POND_HOTSPOT)?.uniform, water: u, detail: bakedDetail(mat, detail) });
  }
  return { level: best.level, box: pondBox, uniforms, mirrorMeshes: mirror };
}

interface FileProgress {
  url: string;
  loaded: number;
  total: number;
  done: boolean;
}

/** Byte progress over a list of URLs, reported as one fraction. */
export function progressTracker(urls: string[], onProgress: (f: number) => void) {
  const files: FileProgress[] = urls.map((url) => ({ url, loaded: 0, total: 0, done: false }));
  const report = () => onProgress(combinedProgress(files));
  return {
    bytes: (url: string) => (loaded: number, total: number) => {
      const f = files.find((x) => x.url === url);
      if (!f) return;
      f.loaded = loaded;
      if (total > 0) f.total = total;
      report();
    },
    finish: (url: string) => {
      const f = files.find((x) => x.url === url);
      if (f) f.done = true;
      report();
    },
  };
}

export interface ContextOptions {
  shadows: boolean;
  alphaToCoverage: boolean;
  lowTextures: boolean;
  /** The device tier (the detail texture is skipped on low); recognised from the rest when absent. */
  tier?: Tier;
  /**
   * The detail texture waits for startDetail (the opening's files download first: it is over a
   * megabyte, and the first picture does not need it).
   */
  deferDetail?: boolean;
}

/** Detail textures waiting for startDetail (createWorldContext with deferDetail). */
const pendingDetail = new WeakMap<WorldContext, () => void>();

/** Starts a deferred detail texture download; nothing when it started already or there is none. */
export function startDetail(ctx: WorldContext): void {
  const start = pendingDetail.get(ctx);
  pendingDetail.delete(ctx);
  start?.();
}

export function createWorldContext(data: SectData, sky: Texture | null, opts: ContextOptions): WorldContext {
  const { meta, manifest } = data;
  const waterfallMaterial = createWaterfallMaterial("#e6eff2", 0.82);
  const sunDir = new Vector3(...meta.sun.direction).normalize();
  const sheetMaterial = createWaterfallSheetMaterial(waterfallMaterial.uniforms.uTime, undefined, { sunDir });
  loadStrandTexture(sheetMaterial, fxAssetUrl(data.base, SHEET.strands));
  const tier: Tier = opts.tier ?? (opts.lowTextures ? "low" : "high");
  const wetRock = createWetRock(wetFalls(meta.waterfalls), {
    max: WET.perTier[tier],
    sunDir,
    time: waterfallMaterial.uniforms.uTime,
    sheen: tier !== "low",
  });
  const hotspotMap = new Map<string, HotspotEntry>();
  for (const h of meta.hotspots) hotspotMap.set(h.id, { ...h, uniform: { value: 0 } });
  const detail =
    manifest.detail && detailWanted(manifest.detail, opts)
      ? loadDetailTexture(resolveAsset(data.base, manifest.detail), {
          time: waterfallMaterial.uniforms.uTime,
          sunDir,
          rockOctaves: rockFarOctaves(tier),
        })
      : null;
  const ctx: WorldContext = {
    data,
    exposure: standInExposure(meta.exposure),
    waterfallMaterial,
    sheetMaterial,
    wetRock,
    sky,
    hotspotMap,
    cellKey: pathCellKey(data.camera.frames.filter((_, i) => i % 3 === 0).map((f) => f.p)),
    sunDir,
    overlay: overlayDecor(meta, waterfallMaterial.uniforms.uTime),
    shadows: opts.shadows && !data.manifest.baked,
    alphaToCoverage: opts.alphaToCoverage,
    lowTextures: opts.lowTextures,
    detail: detail?.uniforms ?? null,
  };
  setOverlayTier(ctx.overlay, tier);
  if (detail && opts.deferDetail) pendingDetail.set(ctx, detail.start);
  else detail?.start();
  return ctx;
}

export function disposeWorldContext(ctx: WorldContext): void {
  disposeObjects(ctx.overlay);
  ctx.waterfallMaterial.dispose();
  const strands = ctx.sheetMaterial.userData.strands as Texture | undefined;
  if (strands) {
    strands.userData.disposed = true;
    strands.dispose();
  }
  ctx.sheetMaterial.dispose();
  ctx.wetRock.clear();
  ctx.sky?.dispose();
  if (ctx.detail) {
    const t = ctx.detail.tSectDetail.value;
    ctx.detail.uSectDetailOn.value = 0;
    t.userData.disposed = true;
    t.dispose();
  }
}

/**
 * Moves a context to another tier with the same texture set and pipeline (desktop Medium and High,
 * picked while the page runs): how many falls are wet at once, the far rock's octaves and the
 * formation's tiered light (setOverlayTier; the canvas also follows the frame ladder's steps).
 */
export function retuneWorld(ctx: WorldContext, tier: Tier): void {
  ctx.wetRock.setMax(WET.perTier[tier]);
  setOverlayTier(ctx.overlay, tier);
  if (ctx.detail) ctx.detail.uSectRockOctaves.value = rockFarOctaves(tier);
}

/**
 * The tiling detail texture (manifest.detail), shared by every rock and ground material. Returned
 * at once so materials can be patched before it arrives (`start` downloads it); the shaders leave the
 * surface without the photo detail until it has (uSectDetailOn 0), and for good if it fails. It
 * fades in over DETAIL_FADE_MS rather than popping onto rock already on screen. Data, not colour
 * (NoColorSpace), repeating, mipmapped, anisotropic for ground at grazing angles. Decoded off the
 * main thread where the browser can. The uniforms also carry the layers (clumps, patches, sheen,
 * far rock), which need no download: the page's clock and sun drive them, `rockOctaves` by tier.
 */
function loadDetailTexture(
  url: string,
  shared: { time: IUniform<number>; sunDir: Vector3; rockOctaves: number },
): { uniforms: DetailUniforms; start: () => void } {
  const tex = new Texture();
  tex.name = "sect.detail";
  tex.wrapS = tex.wrapT = RepeatWrapping;
  tex.colorSpace = NoColorSpace;
  tex.anisotropy = 8;
  const uniforms = createDetailUniforms(tex, shared);
  const done = (image: ImageBitmap | HTMLImageElement) => {
    if (tex.userData.disposed) {
      if (typeof ImageBitmap !== "undefined" && image instanceof ImageBitmap) image.close();
      return;
    }
    tex.image = image;
    tex.needsUpdate = true;
    const t0 = performance.now();
    const fade = () => {
      if (tex.userData.disposed) return;
      const k = Math.min(1, (performance.now() - t0) / DETAIL_FADE_MS);
      uniforms.uSectDetailOn.value = k * k * (3 - 2 * k);
      if (k < 1) requestAnimationFrame(fade);
    };
    fade();
  };
  const failed = (e: unknown) => console.warn("[sect] the detail texture failed to load; rock and ground stay plain", e);
  const start = () => {
    if (tex.userData.disposed) return;
    if (typeof createImageBitmap !== "undefined") {
      // An ImageBitmap is not flipped on upload; a tiling texture does not care which way up it is.
      tex.flipY = false;
      new ImageBitmapLoader().setOptions({ premultiplyAlpha: "none", colorSpaceConversion: "none" }).load(url, done, undefined, failed);
    } else {
      new ImageLoader().load(url, done, undefined, failed);
    }
  };
  return { uniforms, start };
}

/** How long the detail texture takes to fade in once it has arrived. */
const DETAIL_FADE_MS = 1000;

/**
 * The waterfall sheets' strand texture (fx/strands.webp, beside the sets and shared by them), loaded
 * like the detail texture: data, repeating, mipmapped, a little anisotropy for sheets seen at a
 * slant. The sheets draw flat grey strands until it arrives, and for good if it fails.
 */
function loadStrandTexture(sheet: ShaderMaterial, url: string): void {
  const tex = new Texture();
  tex.name = "sect.waterfall.strands";
  tex.wrapS = tex.wrapT = RepeatWrapping;
  tex.colorSpace = NoColorSpace;
  tex.anisotropy = 4;
  sheet.userData.strands = tex;
  const done = (image: ImageBitmap | HTMLImageElement) => {
    if (tex.userData.disposed) {
      if (typeof ImageBitmap !== "undefined" && image instanceof ImageBitmap) image.close();
      return;
    }
    tex.image = image;
    tex.needsUpdate = true;
    setSheetStrands(sheet, tex);
  };
  const failed = (e: unknown) => console.warn("[sect] the waterfall strand texture failed to load; the falls keep plain streaks", e);
  if (typeof createImageBitmap !== "undefined") {
    tex.flipY = false;
    new ImageBitmapLoader().setOptions({ premultiplyAlpha: "none", colorSpaceConversion: "none" }).load(url, done, undefined, failed);
  } else {
    new ImageLoader().load(url, done, undefined, failed);
  }
}

/**
 * Gives every mesh drawn with the sheet material its `aFall` attribute (lib/sect/waterfall.ts
 * sheetFallAttribute: metres across and below the lip, measured per sheet in world space; Blender's
 * UV1 when the GLB has one). Streams are told by their node (extras.water = "stream") or name. Once
 * per geometry; about 2-5 ms for an area's 22k water vertices.
 */
function prepareWaterSheets(roots: readonly Object3D[], sheet: Material): void {
  for (const r of roots) {
    r.updateMatrixWorld(true);
    r.traverse((o) => {
      const mesh = o as Mesh;
      if (!mesh.isMesh || mesh.material !== sheet || mesh.geometry.getAttribute("aFall")) return;
      const g = mesh.geometry;
      const uv = g.getAttribute("uv");
      if (!uv) return;
      const uvs = new Float32Array(uv.count * 2);
      for (let i = 0; i < uv.count; i++) {
        uvs[i * 2] = uv.getX(i);
        uvs[i * 2 + 1] = uv.getY(i);
      }
      const a1 = g.getAttribute("uv1");
      let uv1: Float32Array | null = null;
      if (a1) {
        uv1 = new Float32Array(a1.count * 2);
        for (let i = 0; i < a1.count; i++) {
          uv1[i * 2] = a1.getX(i);
          uv1[i * 2 + 1] = a1.getY(i);
        }
      }
      // GLTFLoader strips the dots from node names (the exporter's name stays in userData.name).
      const exported = typeof mesh.userData?.name === "string" ? (mesh.userData.name as string) : mesh.name;
      const stream = mesh.userData?.water === "stream" || /(^|\.)stream(\.|$)/i.test(exported);
      const fall = sheetFallAttribute({ positions: worldPositions(mesh), uvs, index: g.index ? g.index.array : null, stream, uv1 });
      g.setAttribute("aFall", new BufferAttribute(fall, 4));
    });
  }
}

/** The equirectangular sky image, or null when it is missing (the gradient sky stands in). */
export async function loadSky(url: string | null): Promise<Texture | null> {
  if (!url) return null;
  try {
    const t = await new TextureLoader().loadAsync(url);
    t.colorSpace = SRGBColorSpace;
    t.mapping = EquirectangularReflectionMapping;
    t.generateMipmaps = false;
    t.minFilter = LinearFilter;
    t.magFilter = LinearFilter;
    return t;
  } catch {
    return null;
  }
}

function prepareOpts(ctx: WorldContext) {
  return {
    exposure: ctx.exposure,
    shadows: ctx.shadows,
    waterfallMaterial: ctx.waterfallMaterial,
    waterSheetMaterial: ctx.sheetMaterial,
    envTexture: ctx.sky,
    hotspots: ctx.hotspotMap,
    cellKey: ctx.cellKey,
    cards: { alphaToCoverage: ctx.alphaToCoverage, sunDir: ctx.sunDir },
    detail: ctx.detail,
  };
}

function collectTextures(roots: readonly Object3D[]): Texture[] {
  const out = new Set<Texture>();
  for (const r of roots) {
    r.traverse((o) => {
      const m = o as Mesh;
      if (!m.isMesh) return;
      for (const mat of Array.isArray(m.material) ? m.material : [m.material]) {
        if (!mat) continue;
        for (const v of Object.values(mat)) {
          const t = v as Texture | null;
          if (t && (t as Texture).isTexture && t.image) out.add(t);
        }
      }
    });
  }
  return [...out];
}

function countTris(roots: readonly Object3D[]): number {
  let n = 0;
  for (const r of roots) {
    r.traverse((o) => {
      const m = o as Mesh;
      if (!m.isMesh) return;
      const inst = m as unknown as InstancedMesh;
      n += triangleCount(m.geometry) * (inst.isInstancedMesh ? inst.count : 1);
    });
  }
  return Math.round(n);
}

/** File names of a chunk (or the global set) for the current texture tier. */
export function chunkFiles(chunk: ChunkInfo, lowTextures: boolean): string[] {
  return lowTextures && chunk.filesLow ? chunk.filesLow : chunk.files;
}

export function globalFiles(manifest: SectManifest, lowTextures: boolean): string[] {
  const files = lowTextures && manifest.globalLow ? manifest.globalLow : manifest.global;
  // A version 1 manifest keeps its water GLB beside the scene list.
  return manifest.water ? [...files, manifest.water] : files;
}

export interface SetLoadOptions {
  signal?: AbortSignal;
  /** Byte progress of each URL (shared tracker for the opening download). */
  onBytes?: (url: string) => (loaded: number, total: number) => void;
  onFileDone?: (url: string) => void;
  /**
   * Resolves when the main-thread part of the load (parsing, preparing) may run. A prefetch the
   * streamer starts while the camera moves downloads at once and waits here for a rest (or for the
   * area to be needed), so the flight does not stutter on it. Absent: no wait.
   */
  calm?: () => Promise<void>;
  /**
   * Waits before trying a failed file again (FILE_RETRY_MS). Defaults to FILE_RETRY_MS for the
   * global set, which the page cannot open without, and to none for chunks (the streamer retries).
   */
  retries?: readonly number[];
}

/**
 * Prepares a set's decoded scenes one after another, each a few milliseconds at a time
 * (prepareSceneSliced): in one go a prepare froze a 4x-slowed phone at rest for up to 577 ms. Each
 * waits for `calm` first (a prefetch waits for a rest again). Cancelled or failed part way, it frees
 * all of the scenes (their images are still open: nothing of them reached the GPU) and throws, so a
 * half-prepared set is never handed on. `slice` is for tests.
 */
export async function prepareSetScenes(
  ctx: WorldContext,
  id: string,
  roots: readonly Object3D[],
  opts: { signal?: AbortSignal; calm?: () => Promise<void>; slice?: SliceOptions } = {},
): Promise<PrepareResult[]> {
  const { signal, calm } = opts;
  const prepared: PrepareResult[] = [];
  try {
    for (const root of roots) {
      // Let a frame through between two files.
      await new Promise((r) => setTimeout(r, 0));
      signal?.throwIfAborted();
      if (calm) await calm();
      signal?.throwIfAborted();
      root.name = `sect.${id}`;
      for (const h of measureHotspots(root)) {
        const known = ctx.hotspotMap.get(h.id);
        // meta.json boxes win; boxes for hotspots it lacks come from the geometry.
        if (!known) ctx.hotspotMap.set(h.id, { ...h, chunk: id === "global" ? null : id, uniform: { value: 0 } });
        else if (known.size.every((s) => s <= 0)) Object.assign(known, { center: h.center, size: h.size });
      }
      prepared.push(await prepareSceneSliced(root, prepareOpts(ctx), { ...opts.slice, signal }));
    }
    // Nothing after this waits: a load cancelled by now never comes back as a set.
    signal?.throwIfAborted();
  } catch (e) {
    disposeObjects(roots, sharedResources(ctx));
    throw e;
  }
  // The tree cards were patched for the MSAA setting their prepare began with; the quality ladder
  // may have changed it since, and setCardCoverage only reaches the sets already handed on.
  for (const r of prepared) setCardCoverageOf(r.cardMaterials, ctx.alphaToCoverage);
  return prepared;
}

/**
 * Loads and prepares one set. Decorative files (names with "_trees" or "_water", or a v1 water
 * GLB) may fail without failing the set. The scenes come back hidden (`visible = false`); the
 * render loop shows them once their textures are on the GPU.
 */
export async function loadSet(
  ctx: WorldContext,
  id: string,
  need: [number, number] | null,
  files: readonly string[],
  opts: SetLoadOptions = {},
): Promise<LoadedSet> {
  const { data } = ctx;
  const urls = files.map((f) => resolveAsset(data.base, f));
  const decorative = (f: string) => /_trees|_water|(^|\/)water\.glb/i.test(f);
  const retries = opts.retries ?? (id === "global" ? FILE_RETRY_MS : []);
  let bytes = 0;
  const results = await Promise.all(
    urls.map((url, i) =>
      withRetries(() => loadGlb(url, opts.signal, opts.onBytes ? opts.onBytes(url) : () => {}, opts.calm), retries, opts.signal, files[i])
        .then((r) => {
          bytes += r.bytes;
          opts.onFileDone?.(url);
          return r.gltf;
        })
        .catch((e) => {
          opts.onFileDone?.(url);
          if (opts.signal?.aborted || !decorative(files[i])) throw e;
          console.warn(`[sect] ${files[i]} failed to load; going on without it`, e);
          return null;
        }),
    ),
  );
  const gltfs = results.filter((g): g is GLTF => g !== null);
  // The area's own scene (its trees and water come in files of their own).
  const main = results.find((g, i) => g !== null && !decorative(files[i]))?.scene ?? null;
  const scenes = gltfs.map((g) => g.scene);
  // It checks the signal before it starts (a load cancelled now frees the decoded scenes there), and
  // so do the two waits below: a cancelled load never comes back as a set.
  const prepared = await prepareSetScenes(ctx, id, scenes, { signal: opts.signal, calm: opts.calm });
  const waterfallMeshes = prepared.reduce((a, r) => a + r.waterfallMeshes, 0);
  if (waterfallMeshes === 0) {
    const mine = data.meta.waterfalls.filter((w) => (w.chunk ?? "global") === id);
    const quads = waterfallQuads(mine, ctx.sheetMaterial);
    if (quads) scenes.push(quads);
  }
  prepareWaterSheets(scenes, ctx.sheetMaterial);
  const hotspotMeshes = new Map<string, Mesh[]>();
  const proxies = new Map<string, Mesh[]>();
  for (const r of prepared) {
    for (const [hid, list] of r.hotspotMeshes) hotspotMeshes.set(hid, [...(hotspotMeshes.get(hid) ?? []), ...list]);
    for (const [area, list] of r.proxies) proxies.set(area, [...(proxies.get(area) ?? []), ...list]);
  }
  const cardMaterials = prepared.flatMap((r) => r.cardMaterials);
  // What is left runs a frame after the prepare's last slice, and the bookkeeping a frame after the
  // idle plan (on a 4x-slowed phone the three together froze a rest for 170-200 ms). A load
  // cancelled in between is freed here, like one cancelled during the prepare.
  await yieldToBrowser();
  if (opts.signal?.aborted) {
    disposeObjects(scenes, sharedResources(ctx));
    opts.signal.throwIfAborted();
  }
  const pond = data.manifest.baked
    ? addPondReflection(hotspotMeshes, ctx.hotspotMap, ctx.exposure, ctx.detail, new Set<Material>(cardMaterials))
    : null;
  const idle = id === "global" ? undefined : await planIdleSliced(id, main, hotspotMeshes, ctx.hotspotMap, { signal: opts.signal });
  await yieldToBrowser();
  if (opts.signal?.aborted) {
    idle?.reset();
    for (const u of pond?.uniforms ?? []) u.uHasReflect.value = 0;
    disposeObjects(scenes, sharedResources(ctx));
    opts.signal.throwIfAborted();
  }
  for (const s of scenes) s.visible = false;
  // Its falls' rock is wet while it is shown.
  ctx.wetRock?.track(id, scenes);
  // Everything above has read what it needs: the UVs and colours go once they are on the GPU.
  releaseAfterGpuUpload(scenes);
  return {
    idle,
    id,
    need,
    scenes,
    hotspotMeshes,
    cardMaterials,
    proxies,
    pond,
    litMaterials: prepared.reduce((a, r) => a + r.litMaterials, 0),
    waterfallMeshes,
    bytes,
    tris: countTris(scenes),
    textures: collectTextures(scenes),
    ready: false,
    drawn: false,
  };
}

/** The flyer (only with ?flyer=1): lit, slightly desaturated so it sits in the scene's light. */
export async function loadFlyer(ctx: WorldContext, signal?: AbortSignal): Promise<{ object: Object3D; lit: number } | null> {
  const { manifest, base } = ctx.data;
  if (!manifest.flyer || !ctx.data.flyerPath) return null;
  try {
    const { gltf } = await loadGlb(resolveAsset(base, manifest.flyer), signal, () => {});
    const r = prepareScene(gltf.scene, {
      exposure: ctx.exposure,
      shadows: false,
      waterfallMaterial: ctx.waterfallMaterial,
      envTexture: null,
      hotspots: new Map(),
    });
    // The flyer's robe read pasted on (heavily saturated violet against the warm bake).
    gltf.scene.traverse((o) => {
      const m = (o as Mesh).material as { color?: Color } | undefined;
      if (m?.color) {
        const hsl = { h: 0, s: 0, l: 0 };
        m.color.getHSL(hsl);
        m.color.setHSL(hsl.h, hsl.s * 0.85, hsl.l);
      }
    });
    return { object: gltf.scene, lit: r.litMaterials };
  } catch (e) {
    if (!signal?.aborted) console.warn("[sect] the flyer failed to load", e);
    return null;
  }
}

/**
 * Re-patches tree cards (alpha-tested sprites and needle cards alike) when MSAA turns on or off
 * (alpha to coverage needs a multisampled buffer).
 */
export function setCardCoverage(ctx: WorldContext, sets: readonly LoadedSet[], alphaToCoverage: boolean): void {
  ctx.alphaToCoverage = alphaToCoverage;
  for (const s of sets) setCardCoverageOf(s.cardMaterials, alphaToCoverage);
}

/** Re-patches these tree cards for MSAA on or off (setCardCoverage); the ones already right stay as they are. */
function setCardCoverageOf(cards: readonly MeshBasicMaterial[], alphaToCoverage: boolean): void {
  for (const m of cards) {
    if (m.alphaToCoverage === alphaToCoverage) continue;
    setCardAlphaMode(m, alphaToCoverage);
    m.needsUpdate = true;
  }
}

/** Materials and textures the context shares with every set (never freed with one). */
function sharedResources(ctx: WorldContext): Set<Material | Texture> {
  const shared = new Set<Material | Texture>([ctx.waterfallMaterial, ctx.sheetMaterial]);
  if (ctx.sky) shared.add(ctx.sky);
  return shared;
}

/**
 * Takes a set off the screen for good (LoadedSet.dropped): hidden, not ready, never drawn again,
 * and no longer uploaded, warmed or given grass. Its GPU copies may then be freed.
 */
export function retireSet(set: LoadedSet): void {
  set.dropped = true;
  set.ready = false;
  set.drawn = false;
  for (const r of set.scenes) r.visible = false;
}

/** May the canvas draw the set at all: its textures are on the GPU, and it was neither dropped nor freed. */
export function drawable(set: LoadedSet): boolean {
  return set.ready && !set.dropped && !set.freed;
}

/**
 * Frees every GPU resource a set holds (geometries, materials, textures). Materials shared with the
 * context (waterfall shaders) are left alone.
 *
 * The set leaves the screen first (retireSet). Whatever still holds it must not draw it again: the
 * canvas's React state lags a teardown by a commit or more (a page that loads its world again keeps
 * the old sets until the new ones arrive, which on a hot refresh takes seconds). Its decoded images
 * are closed, and three would make fresh GPU textures from them, which come out empty: the area
 * drawn black, with "texSubImage2D: The source data has been detached" and "glTexStorage2D: image
 * dimensions are not positive" warnings. Freeing a set twice does nothing more.
 */
export function disposeSet(ctx: WorldContext, set: LoadedSet): void {
  retireSet(set);
  if (set.freed) return;
  set.freed = true;
  // Pick boxes the idle motion turned go back to where the bake put them (a reload starts there).
  set.idle?.reset();
  ctx.wetRock?.untrack(set.id, set.scenes);
  disposeObjects(set.scenes, sharedResources(ctx));
  for (const u of set.pond?.uniforms ?? []) u.uHasReflect.value = 0;
}
