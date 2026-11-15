"use client";

/**
 * Live light at the stop the flight is at (lib/sect/live.ts): on the High tier, or on any tier with
 * ?live=1 (?live=0 keeps the bake), that stop's atlas surfaces get their sun light, shadows and shine
 * worked out in the shader from three maps the bake writes beside them (public/sect/full/live/<chunk>/).
 * Only stops listed in live/index.json are tried. Everything else stays baked, and so does the stop
 * itself until all of it is ready. One stop is lit at a time: the shared uniforms (materials.ts
 * SECT_LIVE) are one set for the page.
 *
 * Which stop: the one whose frame range holds the flight's frame (store.frame; between two ranges,
 * the one ahead), if it has maps; the stop lit or starting stays until the frame is
 * LIVE_LOOK.handover.stayFrames past its range (live.ts liveStopKept). What happens each frame is
 * live.ts liveStep. When that stop's set is ready: its index.json is fetched (once per page; missing
 * or unreadable, the stop stays baked and nothing is said), its maps are loaded and put on the GPU
 * through the page's GPU queue (gpu-queue.ts: in bands, one step a frame), the two lamps' shadow
 * maps are drawn (live-shadow.ts; their depth programs compiled
 * off the frame first, and kept for the page), the shared uniforms are filled, the live programs are
 * compiled off the frame on stand-in copies of the materials (program-prime.ts runs their first use
 * too), and only then are the materials switched and uSectLiveMix ramped from 0 to 1. Nothing a
 * stop's first frames draw links a program (in development, guardSwitch says so if one does). When
 * the flight moves on to another stop, the mix fades to 0, then the materials go back to the bake
 * and the maps and the shadow maps are freed, and the next stop starts the same way once its set is
 * ready. When the set drops, or live is turned off, all of that happens at once, with no fade.
 *
 * Ahead of need: while a stop is lit and the flight heads past its hold toward a neighbour with maps,
 * that neighbour's maps are loaded and put on the GPU in the background and held (one stop at most,
 * live.ts livePreload); its start then takes them instead of loading. Under fast travel's ink a stop
 * left goes with no fade and the new one's ramp is instant, and the ink waits for the mix to reach 1
 * (store.report.live, at most LIVE_LOOK.handover.inkWaitMs past when it would have cleared). The
 * loading screen's wait for the first stop waits for it too, but not while it only waits for files
 * still downloading (store.report.liveArriving, live.ts liveArriving): on a slow line the maps come
 * after Enter, and the light then fades in as at every later stop.
 *
 * With ?debug=1, window.__sectLive holds the state (`held`: the stop whose maps are held) and a copy
 * of LIVE_LOOK to retune from the console (change it, then call apply()).
 */
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import {
  ClampToEdgeWrapping,
  Data3DTexture,
  Group,
  HalfFloatType,
  ImageLoader,
  InstancedMesh,
  LinearFilter,
  Mesh,
  NoColorSpace,
  RGBAFormat,
  SRGBColorSpace,
  Texture,
  UnsignedByteType,
  WebGLRenderTarget,
  type Material,
  type WebGLRenderer,
} from "three";
import { WorkerBitmapLoader } from "./bitmap-decode";
import {
  LIVE_HEADING_START,
  LIVE_VIEW,
  liveBumpVec,
  LIVE_CLASSES,
  LIVE_LOOK,
  liveArriving,
  liveAtlasOf,
  liveComing,
  liveEase,
  liveHeading,
  liveIndexFile,
  liveLookFor,
  liveMapFile,
  liveOn,
  livePenumbra,
  livePreload,
  liveShadowMatrix,
  liveShadowScale,
  liveShineVec,
  liveStep,
  liveStopBox,
  liveStopKept,
  liveStopOf,
  liveStopsFile,
  liveValues,
  parseLiveIndex,
  parseLiveParam,
  parseLiveStops,
  type LiveHeading,
  type LiveIndex,
  type LiveLook,
  type LiveShadowBox,
  type LiveStopBox,
} from "@/lib/sect/live";
import { fetchUrl } from "@/lib/sect/parse";
import { keepProgramFields, programVariant } from "@/lib/sect/program-key";
import type { Quality } from "@/lib/sect/runtime";
import type { AreaMeta, Vec3 } from "@/lib/sect/types";
import { drawable, type LoadedSet, type WorldContext } from "./assets";
import { gpuQueue } from "./gpu-queue";
import { idleMovers } from "./idle";
import { liveCasters, liveFarCasters, LiveShadowMap } from "./live-shadow";
import { primePrograms } from "./program-prime";
import {
  isLiveCandidate,
  liveAtlasUniforms,
  liveClassOfMaterial,
  liveClassUniforms,
  materialLive,
  SECT_LIVE,
  setMaterialLive,
  type LiveBinding,
} from "./materials";
import { lookNow } from "./look-now";
import { wake, type SectStore } from "./store";

/** How long the live light takes to fade in over the bake (ms). */
export const LIVE_RAMP_MS = 1200;
/** How long it takes to fade out when the flight moves on to another stop (ms). */
export const LIVE_FADE_MS = 300;
/** How often the shadow map's casters are checked for a change (ms). */
const CASTER_CHECK_MS = 1000;

/** What live light is doing (window.__sectLive with ?debug=1). */
export interface LiveStats {
  on: boolean;
  /** "off", "loading <stop>", "live", "leaving <stop>", "waiting for <stop>", or why a stop stays baked. */
  status: string;
  /** The stop lit live or being started (its chunk id), or null. */
  stop: string | null;
  /** The stops with live maps (live/index.json), or null until the list is read. */
  stops: string[] | null;
  /** The live stop's region (live.ts liveStopBox), or null. */
  box: LiveStopBox | null;
  atlases: string[];
  /** Materials switched to live light. */
  materials: number;
  /** Meshes drawn into the shadow map. */
  casters: number;
  shadowBox: { centre: Vec3; dir: Vec3; radiusM: number; depthM: number } | null;
  /** Main-thread time of the last shadow map render (ms), and how many there have been. */
  shadowMs: number | null;
  shadowRenders: number;
  /** uSectLiveMix now. */
  readonly mix: number;
  /** The stop whose maps are held ahead of need (loading or ready), or null; and whether they are on the GPU. */
  held: string | null;
  heldReady: boolean;
  /**
   * A copy of LIVE_LOOK: change it, then call apply() (tap counts, the coarse factor and the grade
   * need a reload).
   * look.stops["<stop>"] retunes one stop.
   */
  look: LiveLook;
  apply: () => void;
  /** Sets uSectLiveMix (0 shows the bake exactly) and draws a frame. */
  setMix: (v: number) => void;
}

/** index.json per asset folder and chunk, fetched once (null: none or unreadable). */
const indexes = new Map<string, Promise<LiveIndex | null>>();

/** A file with a fingerprint may come from the browser's cache as is; the rest are checked each time. */
function liveFetch(base: string, file: string, rev: Readonly<Record<string, string>> | undefined): Promise<Response> {
  return fetch(fetchUrl(base, file, rev), rev?.[file] ? undefined : { cache: "no-cache" });
}

function loadIndex(base: string, rev: Readonly<Record<string, string>> | undefined, chunk: string): Promise<LiveIndex | null> {
  const key = `${base}|${chunk}`;
  let p = indexes.get(key);
  if (!p) {
    p = liveFetch(base, liveIndexFile(chunk), rev)
      .then(async (res) => (res.ok ? parseLiveIndex(await res.json()) : null))
      .catch(() => null);
    indexes.set(key, p);
  }
  return p;
}

/** live/index.json per asset folder, fetched once: the stops with live maps ([] when missing or unreadable). */
const stopLists = new Map<string, Promise<string[]>>();

function loadStops(base: string, rev: Readonly<Record<string, string>> | undefined): Promise<string[]> {
  let p = stopLists.get(base);
  if (!p) {
    p = liveFetch(base, liveStopsFile(), rev)
      .then(async (res) => (res.ok ? parseLiveStops(await res.json()) : []))
      .catch(() => []);
    stopLists.set(base, p);
  }
  return p;
}

/**
 * How many of a start's (or a preload's) files are still downloading (live.ts liveArriving: the
 * loading screen's wait does not wait for those).
 */
interface Fetching {
  n: number;
}

/** Counts one file as downloading in `f` until the returned function is called (once). */
function downloading(f: Fetching): () => void {
  f.n++;
  let open = true;
  return () => {
    if (!open) return;
    open = false;
    f.n--;
  };
}

/** Frees a map, closing its decoded image if it never reached the GPU. */
function freeTexture(t: Texture): void {
  const img = t.image as unknown;
  if (typeof ImageBitmap !== "undefined" && img instanceof ImageBitmap) img.close();
  t.dispose();
}

/**
 * One live map: data straight from the file (no premultiply, no colour conversion), not flipped
 * (the glTF way, as the atlases), mipmapped, `srgb` for colour, none for the normals. Its decoded
 * image is closed once it is on the GPU (the GPU copy is then the only one: never set needsUpdate
 * on it again). Counted in `fetching` until its file is here (or failed).
 */
function loadMap(url: string, name: string, srgb: boolean, anisotropy: number, fetching: Fetching): Promise<Texture> {
  return new Promise((resolve, reject) => {
    const tex = new Texture();
    tex.name = name;
    tex.flipY = false;
    tex.colorSpace = srgb ? SRGBColorSpace : NoColorSpace;
    tex.anisotropy = anisotropy;
    const arrived = downloading(fetching);
    const done = (image: ImageBitmap | HTMLImageElement) => {
      arrived();
      tex.image = image;
      tex.needsUpdate = true;
      tex.onUpdate = () => {
        const img = tex.image as unknown;
        if (typeof ImageBitmap !== "undefined" && img instanceof ImageBitmap) img.close();
        tex.onUpdate = null;
      };
      resolve(tex);
    };
    const failed = (e: unknown) => {
      arrived();
      reject(e);
    };
    if (typeof createImageBitmap !== "undefined") {
      const loader = new WorkerBitmapLoader().setOptions({ premultiplyAlpha: "none", colorSpaceConversion: "none" });
      // Here: decoding is work on what has arrived.
      loader.onFetched = arrived;
      loader.load(url, done, undefined, failed);
    } else {
      new ImageLoader().load(url, done, undefined, failed);
    }
  });
}

/**
 * Blender's view transform (live.ts LIVE_VIEW) as an sRGB 3D texture, filtered: the shader reads
 * linear display light from it. Rejects when the file is missing or not the size the shader expects.
 * Counted in `fetching` until its bytes are here.
 */
async function loadView(base: string, rev: Readonly<Record<string, string>> | undefined, fetching: Fetching): Promise<Data3DTexture> {
  const arrived = downloading(fetching);
  let bytes: Uint8Array;
  try {
    const res = await liveFetch(base, LIVE_VIEW.file, rev);
    if (!res.ok) throw new Error(`${LIVE_VIEW.file}: ${res.status}`);
    bytes = new Uint8Array(await res.arrayBuffer());
  } finally {
    arrived();
  }
  const n = LIVE_VIEW.size;
  if (bytes.length !== n * n * n * 4) throw new Error(`${LIVE_VIEW.file}: ${bytes.length} bytes, not ${n}^3 x 4`);
  const tex = new Data3DTexture(bytes, n, n, n);
  tex.name = "sect.live.view";
  tex.format = RGBAFormat;
  tex.type = UnsignedByteType;
  tex.colorSpace = SRGBColorSpace;
  tex.minFilter = LinearFilter;
  tex.magFilter = LinearFilter;
  tex.wrapS = tex.wrapT = tex.wrapR = ClampToEdgeWrapping;
  tex.generateMipmaps = false;
  tex.unpackAlignment = 1;
  tex.needsUpdate = true;
  return tex;
}

function nextFrame(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

/**
 * A stop's maps for these atlases (albedo, ambient, normal each, in that order) and the view table,
 * fetched and decoded, not yet on the GPU. Whatever loaded comes back even when something failed
 * (`error`), for the caller to free. `fetching` counts the files still downloading.
 */
async function loadStopMaps(
  base: string,
  rev: Readonly<Record<string, string>> | undefined,
  index: LiveIndex,
  atlases: readonly string[],
  anisotropy: number,
  fetching: Fetching,
): Promise<{ textures: Texture[]; view: Data3DTexture | null; error: string | null }> {
  const jobs = atlases.flatMap((a) => {
    const e = index.atlases[a];
    return [
      loadMap(fetchUrl(base, liveMapFile(index.chunk, e.albedo), rev), `sect.live.${a}.albedo`, true, anisotropy, fetching),
      loadMap(fetchUrl(base, liveMapFile(index.chunk, e.ambient), rev), `sect.live.${a}.ambient`, true, anisotropy, fetching),
      loadMap(fetchUrl(base, liveMapFile(index.chunk, e.normal), rev), `sect.live.${a}.normal`, false, anisotropy, fetching),
    ];
  });
  const viewJob = loadView(base, rev, fetching).catch((e: unknown) => (e instanceof Error ? e : new Error(String(e))));
  const got = await Promise.allSettled(jobs);
  const gotView = await viewJob;
  const textures: Texture[] = [];
  for (const r of got) if (r.status === "fulfilled") textures.push(r.value);
  const view = gotView instanceof Error ? null : gotView;
  const bad = got.find((r): r is PromiseRejectedResult => r.status === "rejected");
  let error: string | null = null;
  if (bad) error = `${index.chunk}: a live map failed to load: ${bad.reason instanceof Error ? bad.reason.message : String(bad.reason)}`;
  else if (gotView instanceof Error) error = `the view table failed to load: ${gotView.message}`;
  return { textures, view, error };
}

/**
 * Puts maps on the GPU through the page's GPU queue (gpu-queue.ts): one step a frame, a 4096 px map
 * in bands of about 2 ms (in one call it stalled the frame it landed in for 15 to 59 ms), never while
 * the GPU is busy or a program links. `priority`: the stop at the camera before maps loaded ahead.
 * False once `alive` says stop (what was not up yet is dropped).
 */
async function uploadEach(gl: WebGLRenderer, textures: readonly Texture[], alive: () => boolean, priority: number): Promise<boolean> {
  const queue = gpuQueue(gl);
  const done = await Promise.all(textures.map((t) => queue.uploadTexture(t, { priority, alive })));
  return done.every(Boolean) && alive();
}

/** The live start's uploads go before the maps loaded ahead for the next stop. */
const START_PRIORITY = 2;
const PRELOAD_PRIORITY = 0;

/**
 * Gets both shadow maps' programs ready off the frame (live-shadow.ts compile), for their casters as
 * they stand now. A failure is only said: the draw then links what it needs itself.
 */
async function compileShadows(gl: WebGLRenderer, ...maps: LiveShadowMap[]): Promise<void> {
  try {
    await Promise.all(maps.map((m) => m.compile(gl)));
  } catch (e) {
    console.warn("[sect] live shadow shader warm-up failed", e);
  }
}

/** A stop's resident set: one the streamer has not dropped (a dropped one may linger in the list a frame or two). */
function setOf(chunks: readonly LoadedSet[], id: string): LoadedSet | null {
  return chunks.find((s) => s.id === id && !s.dropped) ?? null;
}

/** The set's materials that can be lit live with this index, by atlas. */
function liveMaterials(set: LoadedSet, index: LiveIndex): Map<string, Material[]> {
  const byAtlas = new Map<string, Material[]>();
  const seen = new Set<Material>();
  for (const root of set.scenes) {
    root.traverse((o) => {
      const mesh = o as Mesh;
      if (!mesh.isMesh) return;
      for (const mat of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
        if (!mat || seen.has(mat)) continue;
        seen.add(mat);
        const atlas = liveAtlasOf(mat.name);
        if (!atlas || !index.atlases[atlas] || !isLiveCandidate(mat)) continue;
        const list = byAtlas.get(atlas);
        if (list) list.push(mat);
        else byAtlas.set(atlas, [mat]);
      }
    });
  }
  return byAtlas;
}

/**
 * Stand-in copies of the materials on meshes sharing a geometry that draws each one: compiled off
 * the frame, they leave the programs ready for the real materials to pick up without a stall. A
 * copy compiles the real material's program exactly: it shares its shader patch and cache key, and
 * gets back the program fields a clone drops (lib/sect/program-key.ts keepProgramFields: the flat
 * shading GLTFLoader sets on every baked material, the scene's own defines). Each material gets a
 * stand-in, with a copy of its own, per program its meshes need (programVariant: plain or instanced,
 * instance colours, the geometry's attributes): compileAsync waits for each material's last program
 * only. Kept while the stop is lit; then one per program stays for the page (releaseCopies).
 */
function warmCopies(set: LoadedSet, mats: ReadonlySet<Material>): { holder: Group; copies: Material[] } {
  const holder = new Group();
  const copies: Material[] = [];
  const done = new Set<string>();
  for (const root of set.scenes) {
    root.traverse((o) => {
      const mesh = o as Mesh;
      if (!mesh.isMesh) return;
      const src = mesh as unknown as InstancedMesh;
      const inst = src.isInstancedMesh === true;
      for (const mat of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
        if (!mat || !mats.has(mat)) continue;
        const key = `${mat.uuid}|${programVariant(mesh, mat)}`;
        if (done.has(key)) continue;
        done.add(key);
        const copy = mat.clone();
        copy.onBeforeCompile = mat.onBeforeCompile;
        copy.customProgramCacheKey = mat.customProgramCacheKey;
        keepProgramFields(mat, copy);
        let stand: Mesh;
        if (inst) {
          const im = new InstancedMesh(mesh.geometry, copy, 1);
          if (src.instanceColor) im.instanceColor = src.instanceColor;
          if (src.morphTexture) im.morphTexture = src.morphTexture;
          stand = im;
        } else {
          stand = new Mesh(mesh.geometry, copy);
        }
        stand.castShadow = mesh.castShadow;
        stand.receiveShadow = mesh.receiveShadow;
        holder.add(stand);
        copies.push(copy);
      }
    });
  }
  return { holder, copies };
}

/**
 * Live programs kept for the page, per renderer: one stand-in copy per program (by three's cache
 * key). A stop's real materials go when its set is dropped, and their programs with them, which a
 * later visit would link again; most live programs are shared by every stop (the key holds the
 * shader, not the atlas), so there are few. Never drawn.
 */
const liveKeepers = new WeakMap<WebGLRenderer, Map<string, Material>>();

/** Gives back a start's or a session's copies: each one whose program no keeper holds yet becomes its keeper; the rest are freed. */
function releaseCopies(gl: WebGLRenderer, copies: readonly Material[]): void {
  let keep = liveKeepers.get(gl);
  if (!keep) {
    keep = new Map();
    liveKeepers.set(gl, keep);
  }
  for (const c of copies) {
    const key = (gl.properties.get(c) as { currentProgram?: { cacheKey?: string } } | undefined)?.currentProgram?.cacheKey;
    if (key && !keep.has(key)) keep.set(key, c);
    else c.dispose();
  }
}

/** A lamp's shadow box at a stop: the look's depth, the stop's radius. */
function shadowBox(s: { depthM: number; aheadM: number }, radiusM: number): LiveShadowBox {
  return { radiusM, depthM: s.depthM, aheadM: s.aheadM };
}

/**
 * Fills the shared uniforms from a stop's index, the look (with the stop's own numbers over it:
 * liveLookFor) and its box, for a key map `mapSize` px across and a sun map `sunSize` px across;
 * returns the two maps' view-projections.
 */
function applyLook(index: LiveIndex, look: LiveLook, centre: Vec3, box: LiveStopBox, mapSize: number, sunSize: number): { key: number[]; sun: number[] } {
  const v = liveValues(index, liveLookFor(look, index.chunk), box);
  const u = SECT_LIVE;
  u.uSectLiveSunDir.value.set(...v.sunDir);
  u.uSectLiveSunE.value.set(...v.sunE);
  u.uSectLiveKeyDir.value.set(...v.keyDir);
  u.uSectLiveKeyE.value.set(...v.keyE);
  u.uSectLiveAmbient.value = v.ambient;
  u.uSectLiveAmbientIrr.value = v.ambientIrr;
  u.uSectLiveVis.value.set(...v.vis);
  u.uSectLiveGraze.value.set(...v.graze);
  u.uSectLiveClose.value.set(...v.close);
  u.uSectLiveDetail.value.set(...v.detail);
  u.uSectLiveBakeGain.value.set(...v.bakeGain);
  u.uSectLiveBakePost.value.set(...v.bakePost);
  u.uSectLiveCaps.value.set(...v.caps);
  u.uSectLiveBounce.value.set(...v.bounce);
  u.uSectLiveGain.value = v.gain;
  u.uSectLiveExposure.value = v.exposure;
  u.uSectLiveSat.value = v.saturation;
  u.uSectLiveSpecular.value = v.specular;
  u.uSectLiveCentre.value.set(...centre);
  u.uSectLiveBlend.value.set(...v.blend);
  u.uSectLivePaint.value.set(...v.paint);
  u.uSectLiveSurface.value.set(...v.surface);
  u.uSectLiveTiles.value.set(...v.tiles);
  u.uSectLivePaving.value.set(...v.paving);
  for (const cls of LIVE_CLASSES) {
    const c = look.classes[cls];
    const cu = liveClassUniforms(cls);
    cu.uSectLiveSpec.value.set(...liveShineVec(c), c.paint ? 1 : 0);
    cu.uSectLiveBump.value.set(...liveBumpVec(c));
    cu.uSectLiveLift.value = c.liftM ?? 0;
  }
  const s = look.shadow;
  const keyBox = shadowBox(s, box.radiusM);
  const scale = liveShadowScale(keyBox, index.light.key.angleDeg, mapSize);
  u.uSectLiveShadowMap.value.set(scale.metresPerUv, scale.metresPerDepth, scale.penumbraPerM, scale.texelM);
  u.uSectLiveShadowBias.value.set(s.biasM, s.normalBiasM, s.searchM, s.slopeMax);
  u.uSectLiveShadowPen.value.set(...livePenumbra(s, scale.texelM));
  const m = liveShadowMatrix(index.light.key.dir, centre, keyBox);
  u.uSectLiveShadowMatrix.value.fromArray(m);
  const ss = look.sunShadow;
  const sunBox = shadowBox(ss, box.sunRadiusM);
  const sunScale = liveShadowScale(sunBox, index.light.sun.angleDeg, sunSize);
  u.uSectLiveSunShadowMap.value.set(sunScale.metresPerUv, sunScale.metresPerDepth, sunScale.penumbraPerM, sunScale.texelM);
  u.uSectLiveSunShadowBias.value.set(ss.biasM, ss.normalBiasM, ss.searchM, ss.slopeMax);
  u.uSectLiveSunShadowPen.value.set(...livePenumbra(ss, sunScale.texelM));
  const sm = liveShadowMatrix(index.light.sun.dir, centre, sunBox);
  u.uSectLiveSunShadowMatrix.value.fromArray(sm);
  return { key: m, sun: sm };
}

/** Development only: watch the frames after the switch for programs linked on them (guardSwitch). */
const LIVE_GUARD = process.env.NODE_ENV !== "production";
/** How many frames after the switch the guard watches. */
const GUARD_FRAMES = 30;

/**
 * Development only. On the first frames after a stop's materials are switched to live light, says
 * once for the stop which of them drew with a program that did not exist at the switch: one their
 * warm copies did not compile, so it was linked on the frame (a stall; see warmCopies). Programs
 * other parts of the page made meanwhile are not counted.
 */
function guardSwitch(gl: WebGLRenderer, s: Session): void {
  const g = s.guard;
  if (!g) return;
  if (++g.frames > GUARD_FRAMES) {
    s.guard = null;
    return;
  }
  const programs = gl.info.programs ?? [];
  const fresh = new Set<unknown>(programs.filter((p) => !g.before.has(p)));
  if (fresh.size === 0) return;
  const names = new Set<string>();
  for (const m of s.materials) {
    const own = (gl.properties.get(m) as { programs?: Map<string, unknown> } | undefined)?.programs;
    if (own) for (const p of own.values()) if (fresh.has(p)) names.add(m.name);
  }
  if (names.size === 0) return;
  s.guard = null;
  console.warn(`[sect] live light at ${s.area.id}: linked on the frame after the switch, not warmed by the copies: ${[...names].join(", ")}`);
}

/** A stop lit live: what it holds, to give back when it goes. */
interface Session {
  area: AreaMeta;
  set: LoadedSet;
  index: LiveIndex;
  centre: Vec3;
  box: LiveStopBox;
  atlases: string[];
  textures: Texture[];
  materials: Material[];
  shadow: LiveShadowMap;
  sunShadow: LiveShadowMap;
  view: Data3DTexture;
  matrix: { key: number[]; sun: number[] };
  warm: { holder: Group; copies: Material[] };
  /** The mix going up (from `from` at t0) or down to 0 as the flight leaves; null when still. */
  ramp: { t0: number; from: number } | null;
  fade: { t0: number; from: number } | null;
  nextCheck: number;
  /** Development only (LIVE_GUARD): the programs there were at the switch, and frames watched since; null when done. */
  guard: { before: Set<unknown>; frames: number } | null;
}

/**
 * The next stop's maps, loaded ahead while the flight heads there (live.ts livePreload): fetched,
 * decoded and put on the GPU, then held for that stop's start to take. At most one.
 */
interface Held {
  stop: string;
  /** All on the GPU: index, atlases, textures and view are set, and owned here until taken or freed. */
  ready: boolean;
  /** Why nothing could be held (the stop's start then loads its own), or null. */
  failed: string | null;
  index: LiveIndex | null;
  /** Every atlas in the index, sorted; `textures` has three maps each (albedo, ambient, normal). */
  atlases: string[];
  textures: Texture[];
  view: Data3DTexture | null;
  /** Settles when the loading is over, however it ended. */
  done: Promise<void>;
  /** Its files still downloading (a start waiting for these maps counts them as its own: liveArriving). */
  fetching: Fetching;
}

export interface LiveLightProps {
  chunks: LoadedSet[];
  ctx: WorldContext;
  store: SectStore;
  quality: Quality;
}

export function LiveLight({ chunks, ctx, store, quality }: LiveLightProps) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const sw = useMemo(() => parseLiveParam(typeof window === "undefined" ? "" : window.location.search), []);
  const on = liveOn(quality, sw);

  const kit = useMemo(() => {
    const look: LiveLook = structuredClone(LIVE_LOOK);
    return {
      /** Bumped by every start and stop: a start whose number is old gives back what it made. */
      gen: 0,
      session: null as Session | null,
      starting: null as LoadedSet | null,
      /** The files the start under way still waits to download (its own, or the held maps' it waits for). */
      startFetch: null as Fetching | null,
      /** The stops with live maps, once live/index.json is read. */
      stops: null as string[] | null,
      /** Sets that cannot be lit live (no index, no maps), with why: not tried again. */
      failed: new WeakMap<LoadedSet, string>(),
      warmTarget: null as WebGLRenderTarget | null,
      /** The next stop's maps, held ahead (or loading), or null. */
      held: null as Held | null,
      /** Which way the flight goes (live.ts liveHeading). */
      heading: LIVE_HEADING_START as LiveHeading,
      look,
      stats: {
        on: false,
        status: "off",
        stop: null,
        stops: null,
        box: null,
        atlases: [],
        materials: 0,
        casters: 0,
        shadowBox: null,
        shadowMs: null,
        shadowRenders: 0,
        get mix() {
          return SECT_LIVE.uSectLiveMix.value;
        },
        held: null,
        heldReady: false,
        look,
        apply: () => {},
        setMix: () => {},
      } as LiveStats,
    };
  }, []);

  const mounted = useRef(false);
  const live = useRef({ on, chunks, post: quality.post });
  live.current = { on, chunks, post: quality.post };

  /** Takes live light off at once (or stops a start in flight): the bake back, everything freed. */
  const stop = useMemo(
    () => () => {
      kit.gen++;
      kit.starting = null;
      kit.startFetch = null;
      const s = kit.session;
      kit.session = null;
      SECT_LIVE.uSectLiveMix.value = 0;
      SECT_LIVE.uSectLiveShadowOn.value = 0;
      SECT_LIVE.tSectLiveShadow.value = null;
      SECT_LIVE.tSectLiveShadowB.value = null;
      SECT_LIVE.uSectLiveSunShadowOn.value = 0;
      SECT_LIVE.tSectLiveSunShadow.value = null;
      SECT_LIVE.tSectLiveSunShadowB.value = null;
      Object.assign(kit.stats, { stop: null, box: null, atlases: [], materials: 0, casters: 0, shadowBox: null });
      if (!s) return;
      for (const m of s.materials) {
        setMaterialLive(m, null);
        // The bake's program is still the material's own: switching back compiles nothing.
        if (!s.set.dropped) m.needsUpdate = true;
      }
      releaseCopies(gl, s.warm.copies);
      for (const a of s.atlases) {
        const u = liveAtlasUniforms(a);
        u.tSectLiveAlbedo.value = null;
        u.tSectLiveAmbient.value = null;
        u.tSectLiveNormal.value = null;
      }
      for (const t of s.textures) freeTexture(t);
      s.shadow.dispose();
      s.sunShadow.dispose();
      if (SECT_LIVE.tSectLiveView.value === s.view) SECT_LIVE.tSectLiveView.value = null;
      s.view.dispose();
      if (!s.set.dropped) wake(store, 200);
    },
    [kit, store, gl],
  );

  /**
   * Lets go of the maps held ahead. Ready ones are freed now; a load under way sees it is no longer
   * kit.held and gives back what it made as each piece lands.
   */
  const dropHeld = useMemo(
    () => () => {
      const h = kit.held;
      kit.held = null;
      kit.stats.held = null;
      kit.stats.heldReady = false;
      if (!h || !h.ready) return;
      h.ready = false;
      for (const t of h.textures) freeTexture(t);
      h.view?.dispose();
      h.textures = [];
      h.view = null;
    },
    [kit],
  );

  /** Loads a stop's maps ahead of need and holds them (Held) for its start to take. */
  const preload = useMemo(
    () => (stop: string) => {
      const held: Held = { stop, ready: false, failed: null, index: null, atlases: [], textures: [], view: null, done: Promise.resolve(), fetching: { n: 0 } };
      kit.held = held;
      kit.stats.held = stop;
      kit.stats.heldReady = false;
      // Let go of (dropHeld), live turned off, or the canvas gone.
      const alive = () => kit.held === held && mounted.current && live.current.on;
      const run = async () => {
        let textures: Texture[] = [];
        let view: Data3DTexture | null = null;
        const undo = () => {
          for (const t of textures) freeTexture(t);
          view?.dispose();
        };
        const fail = (why: string) => {
          undo();
          held.failed = why;
        };
        try {
          const { base, manifest } = ctx.data;
          const indexIn = downloading(held.fetching);
          const index = await loadIndex(base, manifest.rev, stop).finally(indexIn);
          if (!alive()) return undo();
          if (!index || index.chunk !== stop) return fail(`${stop}: no live maps`);
          const atlases = Object.keys(index.atlases).sort();
          const got = await loadStopMaps(base, manifest.rev, index, atlases, Math.min(8, gl.capabilities.getMaxAnisotropy()), held.fetching);
          textures = got.textures;
          view = got.view;
          if (!alive()) return undo();
          if (got.error || !view) return fail(got.error ?? "the view table failed to load");
          if (!(await uploadEach(gl, [...textures, view], alive, PRELOAD_PRIORITY))) return undo();
          // No await from the last alive() to here: dropHeld either sees ready (and frees) or not.
          Object.assign(held, { index, atlases, textures, view, ready: true });
          kit.stats.heldReady = true;
        } catch (e) {
          fail(e instanceof Error ? e.message : String(e));
        }
      };
      held.done = run();
    },
    [kit, ctx, gl],
  );

  const start = useMemo(
    () => async (target: LoadedSet, area: AreaMeta) => {
      const gen = ++kit.gen;
      kit.starting = target;
      // This start's files still downloading (liveArriving), while it is the start under way.
      const own: Fetching = { n: 0 };
      kit.startFetch = own;
      const stats = kit.stats;
      // A newer start or a stop (the flight left this stop, the set dropped, live turned off) bumps gen.
      const alive = () => gen === kit.gen && mounted.current && live.current.on && !target.dropped && live.current.chunks.includes(target);
      // What this start has made so far, given back if it does not finish. A newer start may have
      // begun meanwhile: only what is still this one's own is taken back.
      const textures: Texture[] = [];
      let shadow: LiveShadowMap | null = null;
      let sunShadow: LiveShadowMap | null = null;
      let view: Data3DTexture | null = null;
      let warm: { holder: Group; copies: Material[] } | null = null;
      const bound: Material[] = [];
      const bindings = new Map<Material, LiveBinding>();
      const filled: string[] = [];
      const undo = () => {
        for (const [m, b] of bindings) if (materialLive(m) === b) setMaterialLive(m, null);
        if (warm) releaseCopies(gl, warm.copies);
        for (const a of filled) {
          const u = liveAtlasUniforms(a);
          for (const slot of [u.tSectLiveAlbedo, u.tSectLiveAmbient, u.tSectLiveNormal]) if (slot.value && textures.includes(slot.value)) slot.value = null;
        }
        if (shadow && SECT_LIVE.tSectLiveShadow.value === shadow.texture) {
          SECT_LIVE.tSectLiveShadow.value = null;
          SECT_LIVE.tSectLiveShadowB.value = null;
          SECT_LIVE.uSectLiveShadowOn.value = 0;
        }
        if (sunShadow && SECT_LIVE.tSectLiveSunShadow.value === sunShadow.texture) {
          SECT_LIVE.tSectLiveSunShadow.value = null;
          SECT_LIVE.tSectLiveSunShadowB.value = null;
          SECT_LIVE.uSectLiveSunShadowOn.value = 0;
        }
        for (const t of textures) freeTexture(t);
        shadow?.dispose();
        sunShadow?.dispose();
        if (view && SECT_LIVE.tSectLiveView.value === view) SECT_LIVE.tSectLiveView.value = null;
        view?.dispose();
      };
      const giveUp = (status: string) => {
        undo();
        if (gen !== kit.gen) return;
        kit.failed.set(target, status);
        Object.assign(stats, { status, stop: null, box: null });
      };
      try {
        const box = liveStopBox(area.footprint, kit.look);
        Object.assign(stats, { status: `loading ${area.id}`, stop: area.id, box });
        const indexIn = downloading(own);
        const index = await loadIndex(ctx.data.base, ctx.data.manifest.rev, area.id).finally(indexIn);
        if (!alive()) return undo();
        if (!index) return giveUp(`${area.id}: no live maps (index.json missing or unreadable)`);
        if (index.chunk !== area.id) return giveUp(`${area.id}: index.json is for ${index.chunk}`);
        const centre: Vec3 = [...area.anchor];
        const byAtlas = liveMaterials(target, index);
        if (byAtlas.size === 0) return giveUp(`${area.id}: no material with live maps`);
        const atlases = [...byAtlas.keys()].sort();
        // The maps held ahead for this stop (livePreload), already on the GPU: taken, not loaded.
        let taken = false;
        const h = kit.held;
        if (h && h.stop === area.id && h.failed === null) {
          if (!h.ready) {
            // Waiting for those maps: their downloads are this start's.
            kit.startFetch = h.fetching;
            await h.done;
            if (gen === kit.gen) kit.startFetch = own;
          }
          if (!alive()) return undo();
          if (kit.held === h && h.ready && h.index === index) {
            kit.held = null;
            kit.stats.held = null;
            kit.stats.heldReady = false;
            const mapsOf = (a: string) => {
              const i = h.atlases.indexOf(a);
              return i < 0 ? [] : h.textures.slice(i * 3, i * 3 + 3);
            };
            if (h.view && atlases.every((a) => mapsOf(a).length === 3)) {
              // This start's own now: undo gives them back if it does not finish. Atlases the set
              // does not draw ride along at the end and are freed with the rest.
              for (const a of atlases) textures.push(...mapsOf(a));
              for (const a of h.atlases) if (!atlases.includes(a)) textures.push(...mapsOf(a));
              view = h.view;
              taken = true;
            } else {
              for (const t of h.textures) freeTexture(t);
              h.view?.dispose();
            }
          }
        }
        if (!taken) {
          const { base, manifest } = ctx.data;
          const got = await loadStopMaps(base, manifest.rev, index, atlases, Math.min(8, gl.capabilities.getMaxAnisotropy()), own);
          textures.push(...got.textures);
          view = got.view;
          if (!alive()) return undo();
          if (got.error) return giveUp(got.error);
          if (!(await uploadEach(gl, view ? [view, ...textures] : textures, alive, START_PRIORITY))) return undo();
        }
        if (!view) return giveUp("the view table failed to load: nothing");
        SECT_LIVE.tSectLiveView.value = view;
        const look = kit.look;
        shadow = new LiveShadowMap(look.shadow.size, look.shadow.coarse);
        sunShadow = new LiveShadowMap(look.sunShadow.size, look.shadow.coarse);
        const matrix = applyLook(index, look, centre, box, shadow.size, sunShadow.size);
        // The stop's own meshes, and the far peaks and the other areas' stand-ins behind them.
        const casters = [...liveCasters(target.scenes, idleMovers(target.idle)), ...liveFarCasters(scene, area.id)];
        shadow.setCasters(casters);
        sunShadow.setCasters(casters);
        // Their depth programs, ready before the first draw (made once for the page: later stops find them).
        await compileShadows(gl, shadow, sunShadow);
        if (!alive()) return undo();
        shadow.render(gl, matrix.key);
        await nextFrame();
        if (!alive()) return undo();
        sunShadow.render(gl, matrix.sun);
        SECT_LIVE.tSectLiveShadow.value = shadow.texture;
        SECT_LIVE.tSectLiveShadowB.value = shadow.coarseTexture;
        SECT_LIVE.uSectLiveShadowOn.value = 1;
        SECT_LIVE.tSectLiveSunShadow.value = sunShadow.texture;
        SECT_LIVE.tSectLiveSunShadowB.value = sunShadow.coarseTexture;
        SECT_LIVE.uSectLiveSunShadowOn.value = 1;
        atlases.forEach((a, i) => {
          const u = liveAtlasUniforms(a);
          u.tSectLiveAlbedo.value = textures[i * 3];
          u.tSectLiveAmbient.value = textures[i * 3 + 1];
          u.tSectLiveNormal.value = textures[i * 3 + 2];
          filled.push(a);
        });
        for (const [atlas, mats] of byAtlas) {
          for (const m of mats) {
            bindings.set(m, { atlas, cls: liveClassOfMaterial(m) });
            bound.push(m);
          }
        }
        warm = warmCopies(target, new Set(bound));
        try {
          const prev = gl.getRenderTarget();
          let pending: Promise<unknown>;
          try {
            // The copies' shader patch reads the real materials' binding: bound only while they
            // compile, which is synchronous. Bound any longer, a real material whose program three
            // works out again before the switch (one drawn on meshes needing two programs does so at
            // every change between them) would go live at once, with a program still linking.
            for (const [m, b] of bindings) setMaterialLive(m, b);
            // As World's warm-up: compile for the composer's (linear) buffer, not the screen.
            if (live.current.post) {
              kit.warmTarget ??= new WebGLRenderTarget(1, 1, { type: HalfFloatType, depthBuffer: false });
              gl.setRenderTarget(kit.warmTarget);
            }
            pending = gl.compileAsync(warm.holder, camera, scene);
          } finally {
            for (const [m, b] of bindings) if (materialLive(m) === b) setMaterialLive(m, null);
            gl.setRenderTarget(prev);
          }
          await pending;
        } catch (e) {
          console.warn("[sect] live light shader warm-up failed", e);
        }
        if (!alive()) return undo();
        // The copies' programs are the real materials': their first use run now, not on the first live frame.
        await primePrograms(gl, warm.copies);
        if (!alive()) return undo();
        const guard = LIVE_GUARD ? { before: new Set<unknown>(gl.info.programs ?? []), frames: 0 } : null;
        // The switch: bound for good, and recompiled (to the copies' programs, ready).
        for (const [m, b] of bindings) setMaterialLive(m, b);
        for (const m of bound) m.needsUpdate = true;
        const now = performance.now();
        kit.session = {
          area,
          set: target,
          index,
          centre,
          box,
          atlases,
          textures,
          materials: bound,
          shadow,
          sunShadow,
          view,
          matrix,
          warm,
          ramp: { t0: now, from: 0 },
          fade: null,
          nextCheck: now + CASTER_CHECK_MS,
          guard,
        };
        Object.assign(stats, {
          status: "live",
          stop: area.id,
          box,
          atlases,
          materials: bound.length,
          casters: shadow.casters,
          shadowBox: { centre, dir: [...index.light.key.dir] as Vec3, radiusM: box.radiusM, depthM: look.shadow.depthM },
          shadowMs: shadow.lastMs + sunShadow.lastMs,
          shadowRenders: shadow.renders + sunShadow.renders,
        });
        wake(store, LIVE_RAMP_MS + 200);
      } catch (e) {
        // Stored, the session owns what was made (stop gives it back).
        if (kit.session?.set === target) return;
        console.warn(`[sect] live light failed; ${area.id} stays baked`, e);
        giveUp(e instanceof Error ? e.message : String(e));
      } finally {
        if (gen === kit.gen) {
          kit.starting = null;
          kit.startFetch = null;
        }
      }
    },
    [kit, ctx, gl, scene, camera, store],
  );

  // Everything goes with the canvas.
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      stop();
      dropHeld();
      store.report.live = false;
      store.report.liveArriving = false;
      kit.warmTarget?.dispose();
      kit.warmTarget = null;
    };
  }, [kit, stop, dropHeld, store]);

  // The list of stops with maps, read once live light is on.
  useEffect(() => {
    if (!on || kit.stops !== null) return;
    void loadStops(ctx.data.base, ctx.data.manifest.rev).then((list) => {
      if (!mounted.current || kit.stops !== null) return;
      kit.stops = list;
      kit.stats.stops = list;
      wake(store, 200);
    });
  }, [on, kit, ctx, store]);

  // Off, or the live stop's set gone: back to the bake at once.
  useEffect(() => {
    kit.stats.on = on;
    if (!on) {
      kit.stats.status = "off";
      dropHeld();
      store.report.live = false;
      store.report.liveArriving = false;
    }
    const gone = (s: LoadedSet) => s.dropped === true || !chunks.includes(s);
    const s = kit.session;
    if ((s && (!on || gone(s.set))) || (kit.starting && (!on || gone(kit.starting)))) stop();
  }, [on, chunks, kit, stop, dropHeld, store]);

  const lookSeen = useRef(-1);
  useFrame(() => {
    const cur = live.current;
    const stats = kit.stats;
    if (!cur.on) {
      if (kit.session || kit.starting) stop();
      if (kit.held) dropHeld();
      store.report.live = false;
      store.report.liveArriving = false;
      return;
    }
    // The journey's light gains (look-now.ts) into the look, and the lit stop's uniforms set again
    // (no shadow redraw: the maps do not depend on them).
    const look = lookNow();
    if (look?.journey && look.version !== lookSeen.current) {
      lookSeen.current = look.version;
      const L = look.live;
      Object.assign(kit.look, { sunGain: L.sunGain, keyGain: L.keyGain, ambientGain: L.ambientGain, saturation: L.saturation, specular: L.specular });
      const s = kit.session;
      if (s) s.matrix = applyLook(s.index, kit.look, s.centre, s.box, s.shadow.size, s.sunShadow.size);
    }
    const gone = (s: LoadedSet) => s.dropped === true || !cur.chunks.includes(s);
    if (kit.session && gone(kit.session.set)) stop();
    if (kit.starting && gone(kit.starting)) stop();
    const now = performance.now();
    const areas = ctx.data.meta.areas;
    const stops = kit.stops;
    const hand = kit.look.handover;
    // The stop lit or starting stays until the frame is well past its range (no reload on a boundary).
    const current = kit.session?.area.id ?? kit.starting?.id ?? null;
    const here = stops ? liveStopKept(store.frame, areas, stops, current, hand.stayFrames) : null;
    const set = here ? setOf(cur.chunks, here.id) : null;
    // An eased flight only passes the stops between where it starts and where it ends.
    const fl = store.flight;
    const passing = fl !== null && here !== null && liveStopOf(fl.toFrame, areas)?.id !== here.id;
    // At most twice: a stop left at once (or a start dropped) lets the next one start this frame.
    for (let round = 0; round < 2; round++) {
      const s = kit.session;
      const act = liveStep({
        lit: s ? { stop: s.area.id, fading: s.fade !== null } : null,
        mix: SECT_LIVE.uSectLiveMix.value,
        starting: kit.starting,
        here: here?.id ?? null,
        set,
        ready: set !== null && drawable(set),
        failed: set !== null && kit.failed.has(set),
        passing,
        covered: store.inked,
      });
      if (act === "end") {
        stop();
        continue;
      }
      if (act === "fade" && s) {
        s.fade = { t0: now, from: SECT_LIVE.uSectLiveMix.value };
        s.ramp = null;
        stats.status = `leaving ${s.area.id}`;
      } else if (act === "resume" && s) {
        // Back before the fade ended: up again from where it got to.
        s.ramp = { t0: now, from: SECT_LIVE.uSectLiveMix.value };
        s.fade = null;
        stats.status = "live";
      } else if (act === "start" && here && set) {
        void start(set, here);
      } else if (act === "wait") {
        if (!stops) stats.status = "reading the list of live stops";
        else if (stops.length === 0) stats.status = "no stop has live maps";
        else if (!here) stats.status = `${liveStopOf(store.frame, areas)?.id ?? "this stop"} has no live maps`;
        else if (set && kit.failed.has(set)) stats.status = kit.failed.get(set) ?? "failed";
        else if (passing) stats.status = `passing ${here.id}`;
        else stats.status = `waiting for ${here.id}`;
      }
      break;
    }
    const sess = kit.session;
    if (sess?.fade) {
      const k = Math.min(1, (now - sess.fade.t0) / LIVE_FADE_MS);
      SECT_LIVE.uSectLiveMix.value = liveEase(sess.fade.from, 0, k);
      // Faded out: the bake back and everything freed; the next stop starts on a later frame.
      if (k >= 1) stop();
      else wake(store, 100);
    } else if (sess) {
      if (LIVE_GUARD) guardSwitch(gl, sess);
      if (sess.ramp) {
        // Under fast travel's ink nobody sees the ramp: straight to 1.
        const k = store.inked ? 1 : Math.min(1, (now - sess.ramp.t0) / LIVE_RAMP_MS);
        SECT_LIVE.uSectLiveMix.value = liveEase(sess.ramp.from, 1, k);
        if (k >= 1) sess.ramp = null;
        else wake(store, 100);
      }
      // The casters changed (a mesh added or taken away): draw the map again.
      if (now >= sess.nextCheck) {
        sess.nextCheck = now + CASTER_CHECK_MS;
        const casters = [...liveCasters(sess.set.scenes, idleMovers(sess.set.idle)), ...liveFarCasters(scene, sess.area.id)];
        if (sess.shadow.setCasters(casters)) {
          sess.sunShadow.setCasters(casters);
          // A new caster's program made off the frame first; the maps drawn again once it is ready.
          void compileShadows(gl, sess.shadow, sess.sunShadow).then(() => {
            if (kit.session !== sess) return;
            stats.shadowMs = sess.shadow.render(gl, sess.matrix.key) + sess.sunShadow.render(gl, sess.matrix.sun);
            stats.shadowRenders = sess.shadow.renders + sess.sunShadow.renders;
            stats.casters = sess.shadow.casters;
            wake(store, 200);
          });
        }
      }
    }
    const after = kit.session;
    const lit = after && !after.fade ? after.area.id : null;
    // Fast travel's ink waits (a little) for live light to come in at the place.
    store.report.live = liveComing({
      here: here?.id ?? null,
      failed: set !== null && kit.failed.has(set),
      lit: after ? { stop: after.area.id, fading: after.fade !== null } : null,
      mix: SECT_LIVE.uSectLiveMix.value,
    });
    // The loading screen's wait does not wait for its files still downloading (liveArriving).
    store.report.liveArriving = liveArriving({
      coming: store.report.live,
      starting: kit.starting !== null,
      lit: after !== null,
      fetching: kit.startFetch?.n ?? 0,
    });
    // The next stop's maps, loaded ahead while the flight heads there.
    kit.heading = liveHeading(kit.heading, store.frame, hand.reverseFrames);
    const want = livePreload(
      {
        lit,
        litDone: after !== null && after.fade === null && after.ramp === null,
        hold: lit ? (store.camera.holds.find((h) => h.id === lit)?.frame ?? null) : null,
        here: here?.id ?? null,
        frame: store.frame,
        heading: kit.heading.dir,
        held: kit.held?.stop ?? null,
      },
      areas,
      stops ?? [],
      hand,
    );
    if (kit.held && kit.held.stop !== want) dropHeld();
    // Never for the stop already starting or lit: those have their own maps.
    if (want !== null && !kit.held && want !== kit.starting?.id && want !== lit) preload(want);
  });

  // Retuning from the console (?debug=1): the look copy (and its stops' own numbers) back into the
  // uniforms, the box worked out again, the shadow redrawn.
  useEffect(() => {
    kit.stats.apply = () => {
      const s = kit.session;
      if (!s) return;
      s.box = liveStopBox(s.area.footprint, kit.look);
      s.matrix = applyLook(s.index, kit.look, s.centre, s.box, s.shadow.size, s.sunShadow.size);
      kit.stats.shadowMs = s.shadow.render(gl, s.matrix.key) + s.sunShadow.render(gl, s.matrix.sun);
      kit.stats.shadowRenders = s.shadow.renders + s.sunShadow.renders;
      kit.stats.box = s.box;
      kit.stats.shadowBox = { centre: s.centre, dir: [...s.index.light.key.dir] as Vec3, radiusM: s.box.radiusM, depthM: kit.look.shadow.depthM };
      wake(store, 300);
    };
    kit.stats.setMix = (v: number) => {
      const s = kit.session;
      if (s) s.ramp = null;
      SECT_LIVE.uSectLiveMix.value = Math.min(Math.max(v, 0), 1);
      wake(store, 300);
    };
  }, [kit, gl, store]);

  // Exposed for inspection scripts in debug mode only.
  useEffect(() => {
    if (!/[?&]debug=1/.test(window.location.search)) return;
    const w = window as unknown as { __sectLive?: LiveStats };
    w.__sectLive = kit.stats;
    return () => {
      if (w.__sectLive === kit.stats) delete w.__sectLive;
    };
  }, [kit]);

  return null;
}
