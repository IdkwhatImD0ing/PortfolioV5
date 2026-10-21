/**
 * Turns a loaded glTF scene into something cheap to draw:
 * - materials: baked (unlit) atlases stay unlit with fog; stand-in PBR materials get the AgX curve;
 *   glow primitives push their colour above 1.0 (by their own strength and tint) so they bloom;
 *   waterfalls get the animated shaders; alpha-tested tree cards get alpha to coverage.
 * - hotspots: nodes with extras.hotspot get their own material copies with a highlight uniform.
 *   Their meshes are listed for picking; the bounding volume hierarchy that makes a pick cost
 *   microseconds is built later, in idle time (ensureBvh, called by the canvas).
 * - draw calls: static meshes that share a material are merged per spatial cell (the stand-in has
 *   ~1,900 draw calls before this). Instanced meshes stay as they are; baked chunks
 *   (extras.chunk) stay separate so the GPU can skip the ones off screen. Backdrop nodes that stand
 *   in for an area (extras.proxyOf) only merge with the same area's proxies, so the page can hide
 *   them while that area's own chunk is drawn.
 * - memory: decoded texture bitmaps are released once they are on the GPU, and so are the vertex
 *   arrays nothing reads again (releaseAfterGpuUpload, called by assets.ts once a set is prepared).
 * - repairs: vertex colours the bake left unset (pure black) are filled from their neighbours
 *   (lib/sect/vertex-colors.ts); colours the bake cannot carry (the stele rows' glyphs, the jade
 *   slip's sheet) are set on the hotspot's material copy (lib/sect/look.ts hotspotTint).
 */
import {
  Box3,
  BufferAttribute,
  BufferGeometry,
  Color,
  Group,
  type InstancedMesh,
  type InterleavedBufferAttribute,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  Object3D,
  Sphere,
  Vector2,
  Vector3,
  type IUniform,
  type Material,
  type Texture,
} from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { acceleratedRaycast, MeshBVH } from "three-mesh-bvh";
import { hotspotTint } from "@/lib/sect/look";
import type { HotspotInfo } from "@/lib/sect/types";
import { anyMissingColor, repairColors } from "@/lib/sect/vertex-colors";
import { bakedDetail, patchCardMaterial, patchMaterial, prepareBakedMaterial, prepareNeedleCard, type DetailUniforms } from "./materials";

export interface HotspotEntry extends HotspotInfo {
  /** Highlight strength shared by the hotspot's material copies (0 off, about 1 on). */
  uniform: IUniform<number>;
}

export interface PrepareOptions {
  exposure: number;
  shadows: boolean;
  /** World-space-noise waterfall shader (stand-in meshes without UVs). */
  waterfallMaterial: Material;
  /** UV waterfall shader for water.glb sheets and streams ('water.*' materials). */
  waterSheetMaterial?: Material;
  /** Sky panorama used as a reflection on still water (baked mode). */
  envTexture: Texture | null;
  hotspots: Map<string, HotspotEntry>;
  /** Merge cell for a root-space position; defaults to a uniform 160 m grid. */
  cellKey?: (x: number, y: number, z: number) => string;
  /** Instanced meshes with at most this many triangles in total are expanded and merged. */
  instanceExpandLimit?: number;
  /** Tree cards (alpha-tested): alpha to coverage when the frame buffer is multisampled. */
  cards?: { alphaToCoverage: boolean; sunDir: Vector3 };
  /** Shared detail texture for baked rock and ground (extras.detail); none skips the detail. */
  detail?: DetailUniforms | null;
}

export interface PrepareResult {
  root: Object3D;
  /** Meshes that belong to each hotspot, for precise pointer picking. */
  hotspotMeshes: Map<string, Mesh[]>;
  /** Alpha-tested card materials (re-patched when MSAA turns on or off). */
  cardMaterials: MeshBasicMaterial[];
  /** Meshes that stand in for an area (extras.proxyOf), by area id. */
  proxies: Map<string, Mesh[]>;
  litMaterials: number;
  colorClasses: number;
  waterfallMeshes: number;
  mergedFrom: number;
  mergedInto: number;
}

function isMesh(o: Object3D): o is Mesh {
  return (o as Mesh).isMesh === true;
}

function hotspotOf(o: Object3D): { id: string; label: string } | null {
  let cur: Object3D | null = o;
  while (cur) {
    const h = cur.userData?.hotspot;
    if (typeof h === "string" && h) {
      const label = typeof cur.userData.label === "string" ? cur.userData.label : h;
      return { id: h, label };
    }
    cur = cur.parent;
  }
  return null;
}

/** The area a backdrop node stands in for (extras.proxyOf on it or an ancestor), or null. */
export function proxyOf(o: Object3D): string | null {
  let cur: Object3D | null = o;
  while (cur) {
    const p = cur.userData?.proxyOf;
    if (typeof p === "string" && p) return p;
    cur = cur.parent;
  }
  return null;
}

/** Glow strength for the untinted ".glow.other" class (see prepareScene). */
const UNCLASSED_GLOW = 1.05;

function glowOf(o: { userData: Record<string, unknown> }): number | null {
  const g = o.userData?.glow;
  const n = typeof g === "number" ? g : typeof g === "string" ? Number(g) : NaN;
  return Number.isFinite(n) && n > 0 ? n : null;
}

function tintOf(o: { userData: Record<string, unknown> } | null | undefined): string | null {
  const t = o?.userData?.glowTint;
  return typeof t === "string" && /^#[0-9a-f]{6}$/i.test(t) ? t : null;
}

/** Vertices converted between two checks of a sliced prepare's time budget (toFloat32). */
const FLOAT_STEP = 8192;

/**
 * Copy of a geometry with plain Float32 attributes (meshopt/quantized data can be int or
 * interleaved). Yields every FLOAT_STEP vertices, so a sliced prepare can stop between them.
 */
function* toFloat32(src: BufferGeometry): Generator<void, BufferGeometry, void> {
  const g = new BufferGeometry();
  for (const name of Object.keys(src.attributes)) {
    const a = src.getAttribute(name);
    const n = a.count;
    const size = a.itemSize;
    const arr = new Float32Array(n * size);
    for (let i = 0; i < n; i++) {
      if (i > 0 && i % FLOAT_STEP === 0) yield;
      arr[i * size] = a.getX(i);
      if (size > 1) arr[i * size + 1] = a.getY(i);
      if (size > 2) arr[i * size + 2] = a.getZ(i);
      if (size > 3) arr[i * size + 3] = a.getW(i);
    }
    g.setAttribute(name, new BufferAttribute(arr, size));
  }
  if (src.index) g.setIndex(new BufferAttribute(Uint32Array.from(src.index.array as ArrayLike<number>), 1));
  return g;
}

/** Vertices or indices handled between two checks of a sliced prepare's time budget (merge, bounds). */
const MERGE_STEP = 32768;

/**
 * mergeGeometries(geoms, false) for the toFloat32 copies a prepare merges (plain Float32 attributes,
 * the same ones on each, all indexed or none), a slice at a time: three's own merge pushes every
 * index into one array in a single block (100 ms and more for a big cell on a slowed phone). The
 * index comes out as three's does (16-bit unless an index reaches 65535). Anything else goes to
 * three's merge.
 */
export function* mergeSliced(geoms: readonly BufferGeometry[]): Generator<void, BufferGeometry | null, void> {
  const first = geoms[0];
  if (!first) return null;
  const names = Object.keys(first.attributes);
  const indexed = first.index !== null;
  const plain = (g: BufferGeometry) =>
    (g.index !== null) === indexed &&
    Object.keys(g.morphAttributes).length === 0 &&
    Object.keys(g.attributes).length === names.length &&
    names.every((n) => {
      const a = g.getAttribute(n) as BufferAttribute | InterleavedBufferAttribute | undefined;
      const f = first.getAttribute(n);
      return a !== undefined && !(a as InterleavedBufferAttribute).isInterleavedBufferAttribute && a.array instanceof Float32Array && !a.normalized && a.itemSize === f.itemSize;
    });
  if (!geoms.every(plain)) return mergeGeometries(geoms as BufferGeometry[], false);
  let verts = 0;
  let indices = 0;
  for (const g of geoms) {
    verts += g.getAttribute("position").count;
    if (indexed) indices += g.index!.count;
  }
  const out = new BufferGeometry();
  for (const n of names) {
    const size = first.getAttribute(n).itemSize;
    const arr = new Float32Array(verts * size);
    let at = 0;
    for (const g of geoms) {
      const src = g.getAttribute(n).array as Float32Array;
      arr.set(src, at);
      at += src.length;
      if (src.length > MERGE_STEP) yield;
    }
    out.setAttribute(n, new BufferAttribute(arr, size));
    yield;
  }
  if (indexed) {
    const index = new Uint32Array(indices);
    let at = 0;
    let base = 0;
    let max = 0;
    for (const g of geoms) {
      const src = g.index!.array;
      for (let j = 0; j < src.length; j++) {
        const v = src[j] + base;
        index[at++] = v;
        if (v > max) max = v;
        if (j % MERGE_STEP === MERGE_STEP - 1) yield;
      }
      base += g.getAttribute("position").count;
    }
    // As three's setIndex(array) picks the type (arrayNeedsUint32).
    out.setIndex(new BufferAttribute(max >= 65535 ? index : Uint16Array.from(index), 1));
  }
  return out;
}

/**
 * computeBoundingBox and computeBoundingSphere for a geometry without morph targets, a slice at a
 * time (one pass each over a big merged cell took tens of milliseconds on a slowed phone). The same
 * box and sphere as three's: the box over every vertex, the sphere round the box's centre.
 */
export function* boundsSliced(g: BufferGeometry): Generator<void, void, void> {
  const pos = g.getAttribute("position");
  if (!pos || Object.keys(g.morphAttributes).length > 0) {
    g.computeBoundingBox();
    g.computeBoundingSphere();
    return;
  }
  const box = (g.boundingBox ??= new Box3());
  box.makeEmpty();
  const v = new Vector3();
  for (let i = 0; i < pos.count; i++) {
    box.expandByPoint(v.fromBufferAttribute(pos, i));
    if (i % MERGE_STEP === MERGE_STEP - 1) yield;
  }
  const sphere = (g.boundingSphere ??= new Sphere());
  box.getCenter(sphere.center);
  let maxSq = 0;
  for (let i = 0; i < pos.count; i++) {
    maxSq = Math.max(maxSq, sphere.center.distanceToSquared(v.fromBufferAttribute(pos, i)));
    if (i % MERGE_STEP === MERGE_STEP - 1) yield;
  }
  sphere.radius = Math.sqrt(maxSq);
}

function flipWinding(g: BufferGeometry): void {
  if (g.index) {
    const idx = g.index.array as Uint32Array;
    for (let i = 0; i + 2 < idx.length; i += 3) {
      const t = idx[i + 1];
      idx[i + 1] = idx[i + 2];
      idx[i + 2] = t;
    }
    return;
  }
  for (const name of Object.keys(g.attributes)) {
    const a = g.getAttribute(name) as BufferAttribute;
    const s = a.itemSize;
    const arr = a.array as Float32Array;
    for (let v = 0; v + 2 < a.count; v += 3) {
      for (let k = 0; k < s; k++) {
        const t = arr[(v + 1) * s + k];
        arr[(v + 1) * s + k] = arr[(v + 2) * s + k];
        arr[(v + 2) * s + k] = t;
      }
    }
  }
}

export function triangleCount(g: BufferGeometry): number {
  return (g.index ? g.index.count : (g.getAttribute("position")?.count ?? 0)) / 3;
}

function signature(g: BufferGeometry): string {
  const attrs = Object.keys(g.attributes)
    .sort()
    .map((n) => `${n}${g.getAttribute(n).itemSize}`)
    .join(",");
  return `${attrs}|${g.index ? "i" : "n"}|${Object.keys(g.morphAttributes).length}`;
}

/** Decoded images this module has closed (shared by a texture and its clones, so kept by image). */
const closedImages = new WeakSet<object>();

function closeImage(img: ImageBitmap): void {
  closedImages.add(img);
  img.close();
}

/**
 * True once the texture's decoded image is closed (after its upload, or with its set). Its GPU copy
 * is then the only one: anything that would make three upload it again (needsUpdate, a new
 * anisotropy or filter, which three keeps as a separate GPU texture, or a draw after dispose())
 * would upload an empty image and draw black.
 */
export function imageClosed(tex: Texture): boolean {
  const img = tex.image as object | null | undefined;
  return img != null && closedImages.has(img);
}

/**
 * three keeps each decoded ImageBitmap in memory after uploading it (about 67 MB per 4096 atlas).
 * Close it once the texture is on the GPU; the size is kept in userData for shaders that need it.
 */
function releaseAfterUpload(tex: Texture): void {
  const img = tex.image as { width?: number; height?: number; close?: () => void } | null;
  if (!img || typeof ImageBitmap === "undefined" || !(img instanceof ImageBitmap)) return;
  tex.userData.size = [img.width, img.height];
  if (tex.userData.releaseHooked) return;
  tex.userData.releaseHooked = true;
  tex.onUpdate = () => {
    closeImage(tex.image as ImageBitmap);
    tex.onUpdate = null;
  };
}

function textureSize(tex: Texture | null | undefined): Vector2 {
  const s = tex?.userData?.size as [number, number] | undefined;
  if (s) return new Vector2(s[0], s[1]);
  const img = tex?.image as { width?: number; height?: number } | undefined;
  return new Vector2(img?.width || 2048, img?.height || 2048);
}

const tmpBox = new Box3();
const tmpV = new Vector3();
const tmpSize = new Vector3();

/** Hotspot boxes measured from the loaded nodes (three space), for hotspots meta.json lacks. */
export function measureHotspots(root: Object3D): HotspotInfo[] {
  const out: HotspotInfo[] = [];
  root.updateMatrixWorld(true);
  root.traverse((o) => {
    const id = o.userData?.hotspot;
    if (typeof id !== "string" || !id) return;
    tmpBox.makeEmpty().expandByObject(o);
    if (tmpBox.isEmpty()) return;
    tmpBox.getCenter(tmpV);
    tmpBox.getSize(tmpSize);
    out.push({
      id,
      label: typeof o.userData.label === "string" ? o.userData.label : id,
      center: [tmpV.x, tmpV.y, tmpV.z],
      size: [tmpSize.x, tmpSize.y, tmpSize.z],
    });
  });
  return out;
}

const repairedColors = new WeakSet<BufferGeometry>();

/** The raw array of an attribute, how far apart its vertices are in it and where the first starts. */
function rawLayout(a: BufferAttribute | InterleavedBufferAttribute): { array: ArrayLike<number>; stride: number; offset: number } {
  const i = a as InterleavedBufferAttribute;
  if (i.isInterleavedBufferAttribute) return { array: i.data.array, stride: i.data.stride, offset: i.offset };
  return { array: a.array, stride: a.itemSize, offset: 0 };
}

/** What a stored value is divided by to read as 0..1 (normalised integers), else 1. */
function normalisedScale(a: BufferAttribute | InterleavedBufferAttribute): number {
  if (!a.normalized) return 1;
  const arr = rawLayout(a).array;
  if (arr instanceof Uint8Array || arr instanceof Uint8ClampedArray) return 255;
  if (arr instanceof Uint16Array) return 65535;
  if (arr instanceof Int8Array) return 127;
  if (arr instanceof Int16Array) return 32767;
  return 1;
}

/**
 * Vertex-colour (baked.vc) meshes: fills the vertices the bake left pure black (see
 * lib/sect/vertex-colors.ts). Once per geometry. A mesh with no black vertex (most of them) is told
 * from its raw array, before any copy; the positions are copied only if the fallback needs them,
 * and only the filled vertices are written back.
 */
function repairVertexColors(mesh: Mesh): void {
  const g = mesh.geometry;
  const col = g.getAttribute("color") as BufferAttribute | InterleavedBufferAttribute | undefined;
  const pos = g.getAttribute("position");
  if (!col || !pos || repairedColors.has(g)) return;
  repairedColors.add(g);
  const mat = mesh.material as Material;
  if (Array.isArray(mesh.material) || !/^baked\.vc/i.test(mat.name) || col.itemSize < 3) return;
  const n = col.count;
  const raw = rawLayout(col);
  if (!anyMissingColor(raw.array, n, raw.stride, raw.offset, normalisedScale(col))) return;
  const colors = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    colors[i * 3] = col.getX(i);
    colors[i * 3 + 1] = col.getY(i);
    colors[i * 3 + 2] = col.getZ(i);
  }
  const positions = () => {
    const p = new Float32Array(pos.count * 3);
    for (let i = 0; i < pos.count; i++) {
      p[i * 3] = pos.getX(i);
      p[i * 3 + 1] = pos.getY(i);
      p[i * 3 + 2] = pos.getZ(i);
    }
    return p;
  };
  const filled = repairColors(colors, positions, g.index ? g.index.array : null);
  if (filled.length === 0) return;
  for (const v of filled) col.setXYZ(v, colors[v * 3], colors[v * 3 + 1], colors[v * 3 + 2]);
  if ((col as InterleavedBufferAttribute).isInterleavedBufferAttribute) (col as InterleavedBufferAttribute).data.needsUpdate = true;
  else (col as BufferAttribute).needsUpdate = true;
}

/**
 * Vertex attributes nothing on the CPU reads once they are on the GPU: UVs, the second UV set (the
 * needle cards' cut-out, the falls' lip coordinates) and the vertex colours. Every reader runs while
 * a set is prepared (merging, the colour repair, the waterfall sheets), before its first draw. Ray
 * picks would interpolate UVs at a hit, but nothing here reads them (an emptied array gives NaN,
 * never an error). Positions and indices stay: the picking BVHs, the occluder tests and the grass
 * read them later. So does the UV set of the ground (`detail: "ground"` materials): the grass reads
 * it when it builds an area, which may come after the upload (grass.tsx collectSoups).
 */
const GPU_ONLY_ATTRIBUTES = ["uv", "uv1", "color"] as const;

/**
 * Lets go of the CPU copies of the attributes in GPU_ONLY_ATTRIBUTES once three has uploaded them,
 * for every mesh under the roots: an area keeps 14-32 MB of them on a phone (50-80 MB on a
 * desktop), all already on the GPU. Each array is swapped for an empty one of its type when its
 * buffer is first uploaded (BufferAttribute.onUpload), so the decoded buffer behind it can be
 * collected; a geometry never drawn keeps them until it is disposed. Interleaved attributes share a
 * buffer with ones that must stay and are left alone. Call once the set is prepared.
 */
export function releaseAfterGpuUpload(roots: readonly Object3D[]): void {
  const geos = new Set<BufferGeometry>();
  // A geometry any ground material draws keeps its UVs (shared geometries included).
  const groundUv = new Set<BufferGeometry>();
  for (const r of roots) {
    r.traverse((o) => {
      const mesh = o as Mesh;
      if (!mesh.isMesh) return;
      geos.add(mesh.geometry);
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      if (mats.some((m) => m?.userData?.detail === "ground")) groundUv.add(mesh.geometry);
    });
  }
  for (const g of geos) {
    for (const name of GPU_ONLY_ATTRIBUTES) {
      if (name === "uv" && groundUv.has(g)) continue;
      const a = g.getAttribute(name) as BufferAttribute | InterleavedBufferAttribute | undefined;
      if (!a || (a as InterleavedBufferAttribute).isInterleavedBufferAttribute) continue;
      const attr = a as BufferAttribute;
      attr.onUpload(() => {
        const Kind = attr.array.constructor as new (n: number) => typeof attr.array;
        attr.array = new Kind(0);
        attr.onUploadCallback = () => {};
      });
    }
  }
}

/**
 * A BVH on a mesh's geometry (once), so raycasts against it are fast. Building one blocks the main
 * thread (tens of ms for 100k+ triangles): call it from idle time, not while the camera moves.
 */
export function ensureBvh(mesh: Mesh): void {
  const g = mesh.geometry as BufferGeometry & { boundsTree?: MeshBVH };
  if (!g.boundsTree) g.boundsTree = new MeshBVH(g);
  mesh.raycast = acceleratedRaycast;
}

/** True once ensureBvh has run on the mesh's geometry. */
export function hasBvh(mesh: Mesh): boolean {
  return Boolean((mesh.geometry as BufferGeometry & { boundsTree?: MeshBVH }).boundsTree);
}

/**
 * Prepares a loaded scene in one go (see the file comment). The streamed areas use
 * prepareSceneSliced instead, which does the same work a few milliseconds at a time.
 */
export function prepareScene(root: Object3D, opts: PrepareOptions): PrepareResult {
  const steps = prepareSteps(root, opts);
  for (;;) {
    const r = steps.next();
    if (r.done) return r.value;
  }
}

/**
 * Main-thread time a sliced prepare takes before it lets a frame through (ms). A 4x-slowed phone
 * spent 140-580 ms in one prepareScene at rest, which froze the water, the clouds and a tap; in 5 ms
 * slices the render loop keeps its 30 frames a second while the next area is prepared.
 */
export const PREPARE_SLICE_MS = 5;

export interface SliceOptions {
  signal?: AbortSignal;
  /** Time per slice (ms); PREPARE_SLICE_MS by default. */
  budgetMs?: number;
  /** Waits between two slices (default: yieldToBrowser). */
  pause?: () => Promise<void>;
  /** The clock (default performance.now). */
  now?: () => number;
}

/** Resolves in a task of its own: a message to this window (no 4 ms clamp, unlike a chain of timeouts). */
function nextTask(): Promise<void> {
  if (typeof MessageChannel === "undefined") return new Promise((r) => setTimeout(r, 0));
  return new Promise((resolve) => {
    const ch = new MessageChannel();
    ch.port1.onmessage = () => {
      ch.port1.close();
      resolve();
    };
    ch.port2.postMessage(0);
  });
}

/**
 * Gives the browser its turn: resolves in the first task after the next frame (an animation frame,
 * then a message), so a frame is drawn between two slices. scheduler.yield did not do that: its
 * continuations run ahead of the frame, and a 4x-slowed phone went 110 ms between frames at rest
 * while the slices ran back to back. In a hidden tab (no animation frames) only the message.
 */
export function yieldToBrowser(): Promise<void> {
  const frames = typeof requestAnimationFrame === "function" && typeof document !== "undefined" && document.visibilityState !== "hidden";
  if (!frames) return nextTask();
  return new Promise((resolve) => {
    requestAnimationFrame(() => void nextTask().then(resolve));
  });
}

/**
 * prepareScene in slices of about `budgetMs` of main-thread time, letting the browser draw between
 * them. Same result as prepareScene. Throws the signal's reason when it is aborted between slices.
 * The scene is then half-prepared, for the caller to free (assets.ts prepareSetScenes); the merge
 * copies made so far were never uploaded and go with the generator.
 */
export async function prepareSceneSliced(root: Object3D, opts: PrepareOptions, slice: SliceOptions = {}): Promise<PrepareResult> {
  const now = slice.now ?? (() => performance.now());
  const budget = slice.budgetMs ?? PREPARE_SLICE_MS;
  const pause = slice.pause ?? yieldToBrowser;
  slice.signal?.throwIfAborted();
  const steps = prepareSteps(root, opts);
  try {
    let t0 = now();
    for (;;) {
      const r = steps.next();
      if (r.done) return r.value;
      if (now() - t0 < budget) continue;
      await pause();
      slice.signal?.throwIfAborted();
      t0 = now();
    }
  } catch (e) {
    // Ends the generator where it stopped (it holds the copies; nothing else does).
    steps.return(undefined as never);
    throw e;
  }
}

/** The work of prepareScene, yielding wherever it may stop for a frame. */
function* prepareSteps(root: Object3D, opts: PrepareOptions): Generator<void, PrepareResult, void> {
  root.updateMatrixWorld(true);
  const rootInv = new Matrix4().copy(root.matrixWorld).invert();
  const cellKey =
    opts.cellKey ?? ((x: number, y: number, z: number) => `${Math.floor(x / 160)},${Math.floor(y / 160)},${Math.floor(z / 160)}`);
  const instanceExpandLimit = opts.instanceExpandLimit ?? 60000;

  const litPatched = new Set<Material>();
  const glowCopies = new Map<string, Material>();
  const hotspotCopies = new Map<string, Material>();
  const cardMaterials = new Set<MeshBasicMaterial>();
  let waterfallMeshes = 0;

  // Stand-in only: plain-colour lit materials that differ only in colour are folded into a few
  // shared vertex-colour materials (by roughness, metalness, side and hotspot), so merging can
  // cross material boundaries. Baked atlases never take this path (they have textures).
  const classes = new Map<string, MeshStandardMaterial>();
  const meshClass = new Map<Mesh, { material: MeshStandardMaterial; color: Color }>();
  const classFor = (m: Material, hotspot: HotspotEntry | null): MeshStandardMaterial | null => {
    const s = m as MeshStandardMaterial;
    if (!s.isMeshStandardMaterial || s.map || s.vertexColors || s.transparent || s.alphaTest > 0) return null;
    if (s.emissiveMap || s.normalMap || s.roughnessMap || s.metalnessMap || s.aoMap) return null;
    if ((s.emissive.r + s.emissive.g + s.emissive.b) * s.emissiveIntensity > 1e-3) return null;
    if (/water|pond/i.test(s.name)) return null;
    const rough = Math.round(s.roughness * 4) / 4;
    const metal = s.metalness > 0.5 ? 1 : 0;
    const key = `${rough}|${metal}|${s.side}|${s.flatShading ? 1 : 0}|${hotspot?.id ?? ""}`;
    let cls = classes.get(key);
    if (!cls) {
      cls = new MeshStandardMaterial({
        name: `class.r${rough}.m${metal}${hotspot ? `.${hotspot.id}` : ""}`,
        vertexColors: true,
        roughness: rough,
        metalness: metal,
        side: s.side,
        flatShading: s.flatShading,
      });
      patchMaterial(cls, { lit: true, exposure: opts.exposure, highlight: hotspot?.uniform });
      classes.set(key, cls);
    }
    return cls;
  };

  const meshes: Mesh[] = [];
  root.traverse((o) => {
    if (isMesh(o)) meshes.push(o);
  });

  const prepMaterial = (m: Material): Material => {
    const b = m as MeshBasicMaterial;
    if (b.isMeshBasicMaterial) {
      if (b.map) releaseAfterUpload(b.map);
      prepareBakedMaterial(b, opts.detail);
      if (opts.envTexture && /water|pond/i.test(m.name) && !b.envMap) {
        b.envMap = opts.envTexture;
        b.reflectivity = 0.35;
      }
      // Needle and twig cards are opaque in the file; their cut-out moves to the alpha map first.
      const needle = prepareNeedleCard(b);
      if (opts.cards && (needle || (b.alphaTest > 0 && b.map)) && !cardMaterials.has(b)) {
        patchCardMaterial(b, { ...opts.cards, texSize: textureSize(b.alphaMap ?? b.map) });
        cardMaterials.add(b);
      }
    } else if ((m as MeshStandardMaterial).isMeshStandardMaterial) {
      const s = m as MeshStandardMaterial;
      if (s.map) releaseAfterUpload(s.map);
      if (/water|pond/i.test(s.name)) {
        s.roughness = Math.min(s.roughness, 0.08);
        s.metalness = 0;
      }
      // The bronze mirror glows pale gold in the Blender render (its white emission picks up the
      // golden-hour light there); the unbaked stand-in has to say so explicitly.
      if (/mirror_face/i.test(s.name)) {
        s.emissive.set("#f4d08e");
        s.emissiveIntensity = 0.9;
        s.color.set("#b99a5e");
      }
      // Blender's "blend" mode on fully opaque surfaces only costs sorting.
      if (s.transparent && s.opacity >= 0.98 && !s.map && !s.alphaMap) {
        s.transparent = false;
        s.depthWrite = true;
      }
      if (!litPatched.has(s)) {
        patchMaterial(s, { lit: true, exposure: opts.exposure });
        litPatched.add(s);
      }
    }
    return m;
  };

  const mergeable: Mesh[] = [];

  for (const mesh of meshes) {
    yield;
    if (Array.isArray(mesh.material)) {
      mesh.material = mesh.material.map(prepMaterial);
      continue;
    }
    repairVertexColors(mesh);
    let mat = mesh.material as Material;

    if (/^water\./i.test(mat.name) && opts.waterSheetMaterial) {
      mesh.material = opts.waterSheetMaterial;
      mesh.renderOrder = 2;
      waterfallMeshes++;
      continue;
    }
    if (/waterfall/i.test(mat.name)) {
      mesh.material = opts.waterfallMaterial;
      mesh.castShadow = false;
      mesh.receiveShadow = false;
      mesh.renderOrder = 2;
      waterfallMeshes++;
      continue;
    }

    mat = prepMaterial(mat);

    // The tag sits on the node, or (for a primitive of a multi-material node, e.g. a hotspot's
    // glowing runes) only on the material. The tint likewise.
    const tagged = glowOf(mesh) ?? (mesh.parent ? glowOf(mesh.parent) : null) ?? glowOf(mat);
    const tint = tagged !== null ? (tintOf(mat) ?? tintOf(mesh) ?? tintOf(mesh.parent)) : null;
    // The exporter's untinted catch-all class (".glow.other": the jade slip's sheet, the abode
    // waterfall's foam) is a large pale surface whose bake already holds its light: boosting it
    // turned the jade white and buried its gold glyphs.
    const glow = tagged !== null && !tint && /\.glow\.other$/i.test(mat.name) ? Math.min(tagged, UNCLASSED_GLOW) : tagged;
    if (glow !== null) {
      const key = `${mat.uuid}|${glow}|${tint ?? ""}`;
      let copy = glowCopies.get(key);
      if (!copy) {
        copy = mat.clone();
        const c = copy as MeshBasicMaterial;
        if (c.color) {
          c.color.multiplyScalar(glow);
          if (tint) {
            // Toward the class colour (75 %), so the baked detail (runes, panes) still shows.
            const t = new Color(tint);
            c.color.multiply(new Color(1, 1, 1).lerp(t, 0.75));
          }
        }
        copy.customProgramCacheKey = mat.customProgramCacheKey;
        copy.onBeforeCompile = mat.onBeforeCompile;
        glowCopies.set(key, copy);
      }
      mat = copy;
    }

    const hs = hotspotOf(mesh);
    if (hs) {
      let entry = opts.hotspots.get(hs.id);
      if (!entry) {
        entry = { id: hs.id, label: hs.label, center: [0, 0, 0], size: [0, 0, 0], uniform: { value: 0 } };
        opts.hotspots.set(hs.id, entry);
      }
      const key = `${mat.uuid}|${hs.id}`;
      let copy = hotspotCopies.get(key);
      if (!copy) {
        copy = mat.clone();
        const tint = hotspotTint(hs.id, mat.name);
        const c = (copy as MeshBasicMaterial).color;
        if (tint && c) {
          // The class colour replaces the bake's (white) one; the glow strength stays.
          const strength = Math.max(c.r, c.g, c.b);
          c.setRGB(1, 1, 1).lerp(new Color(tint.color), tint.amount).multiplyScalar(strength * tint.gain);
        }
        // patchMaterial only applies the tone curve to lit (standard) materials. The copy keeps
        // its rock / ground detail (userData is copied with it).
        patchMaterial(copy, { lit: true, exposure: opts.exposure, highlight: entry.uniform, detail: bakedDetail(copy, opts.detail) });
        // A tree card's copy (a click-target tree's sprites or needles) gets the card patch back,
        // which patchMaterial replaced, and joins the cards setCardCoverage switches.
        const card = copy as MeshBasicMaterial;
        if (opts.cards && cardMaterials.has(mat as MeshBasicMaterial)) {
          patchCardMaterial(card, { ...opts.cards, texSize: textureSize(card.alphaMap ?? card.map) });
          cardMaterials.add(card);
        }
        hotspotCopies.set(key, copy);
      }
      mesh.material = copy;
    } else {
      mesh.material = mat;
    }
    const cls = classFor(mat, hs ? (opts.hotspots.get(hs.id) ?? null) : null);
    if (cls) meshClass.set(mesh, { material: cls, color: (mat as MeshStandardMaterial).color.clone() });

    mesh.castShadow = opts.shadows;
    mesh.receiveShadow = opts.shadows;

    const g = mesh.geometry;
    const transparent = (mesh.material as Material).transparent;
    const inst = mesh as unknown as InstancedMesh;
    const chunk = mesh.userData?.chunk === 1 || mesh.parent?.userData?.chunk === 1;
    const expandable =
      !inst.isInstancedMesh || (inst.instanceColor === null && inst.count * triangleCount(g) <= instanceExpandLimit);
    if (
      expandable &&
      !chunk &&
      !transparent &&
      !(mesh as unknown as { isSkinnedMesh?: boolean }).isSkinnedMesh &&
      Object.keys(g.morphAttributes).length === 0 &&
      g.getAttribute("position")
    ) {
      mergeable.push(mesh);
    }
  }

  // Every static mesh (and every instance of a small instanced mesh) becomes a "part" with a
  // root-relative matrix. Parts are grouped by material, attribute layout and spatial cell.
  interface Part {
    mesh: Mesh;
    matrix: Matrix4;
  }
  const groups = new Map<string, Part[]>();
  const instMatrix = new Matrix4();
  const addPart = (mesh: Mesh, matrix: Matrix4) => {
    const g = mesh.geometry;
    if (!g.boundingSphere) g.computeBoundingSphere();
    tmpV.copy(g.boundingSphere!.center).applyMatrix4(matrix);
    const cls = meshClass.get(mesh);
    // One material per group (needle cards never join their tree's opaque parts), and one
    // attribute layout (the needles' second UV set, uv1, is kept through toFloat32).
    const matId = cls ? cls.material.uuid : (mesh.material as Material).uuid;
    const proxy = proxyOf(mesh) ?? "";
    const key = `${matId}|${signature(g)}${cls ? "+color" : ""}|${cellKey(tmpV.x, tmpV.y, tmpV.z)}|${proxy}`;
    const list = groups.get(key);
    if (list) list.push({ mesh, matrix });
    else groups.set(key, [{ mesh, matrix }]);
  };
  for (const mesh of mergeable) {
    yield;
    const base = new Matrix4().multiplyMatrices(rootInv, mesh.matrixWorld);
    const inst = mesh as unknown as InstancedMesh;
    if (inst.isInstancedMesh) {
      for (let i = 0; i < inst.count; i++) {
        inst.getMatrixAt(i, instMatrix);
        addPart(mesh, new Matrix4().multiplyMatrices(base, instMatrix));
      }
    } else {
      addPart(mesh, base);
    }
  }

  const merged = new Group();
  merged.name = "sect.merged";
  const floatCache = new Map<BufferGeometry, BufferGeometry>();
  function* asFloat(g: BufferGeometry): Generator<void, BufferGeometry, void> {
    let f = floatCache.get(g);
    if (!f) {
      f = yield* toFloat32(g);
      floatCache.set(g, f);
    }
    return f;
  }
  const removable = new Set<Mesh>();
  let mergedFrom = 0;
  let mergedInto = 0;
  for (const list of groups.values()) {
    // A lone plain mesh gains nothing from merging; a lone instance still leaves its batch.
    const lone = list.length < 2 && !(list[0].mesh as unknown as InstancedMesh).isInstancedMesh;
    if (lone) continue;
    const geoms: BufferGeometry[] = [];
    for (const part of list) {
      yield;
      const g = (yield* asFloat(part.mesh.geometry)).clone();
      g.applyMatrix4(part.matrix);
      if (part.matrix.determinant() < 0) flipWinding(g);
      const cls = meshClass.get(part.mesh);
      if (cls) {
        const n = g.getAttribute("position").count;
        const col = new Float32Array(n * 3);
        for (let i = 0; i < n; i++) {
          col[i * 3] = cls.color.r;
          col[i * 3 + 1] = cls.color.g;
          col[i * 3 + 2] = cls.color.b;
        }
        g.setAttribute("color", new BufferAttribute(col, 3));
      }
      geoms.push(g);
    }
    yield;
    const geo = yield* mergeSliced(geoms);
    for (const p of geoms) p.dispose();
    if (!geo) continue;
    yield;
    yield* boundsSliced(geo);
    const first = list[0].mesh;
    const material = meshClass.get(first)?.material ?? (first.material as Material);
    const m = new Mesh(geo, material);
    m.name = `merged.${material.name || "mat"}`;
    const hs = hotspotOf(first);
    if (hs) m.userData.hotspot = hs.id;
    const px = proxyOf(first);
    if (px) m.userData.proxyOf = px;
    m.castShadow = first.castShadow;
    m.receiveShadow = first.receiveShadow;
    merged.add(m);
    for (const part of list) removable.add(part.mesh);
    mergedFrom += list.length;
    mergedInto += 1;
  }
  for (const mesh of removable) mesh.removeFromParent();
  for (const g of floatCache.values()) g.dispose();
  if (merged.children.length > 0) root.add(merged);

  root.traverse((o) => {
    o.matrixAutoUpdate = false;
  });
  root.updateMatrixWorld(true);

  const hotspotMeshes = new Map<string, Mesh[]>();
  const proxies = new Map<string, Mesh[]>();
  root.traverse((o) => {
    if (!isMesh(o)) return;
    const px = proxyOf(o);
    if (px) {
      const list = proxies.get(px);
      if (list) list.push(o);
      else proxies.set(px, [o]);
    }
    const id = typeof o.userData.hotspot === "string" ? o.userData.hotspot : hotspotOf(o)?.id;
    if (!id) return;
    // No BVH here: building them took 30-163 ms per file in one block, mid-flight. The canvas
    // builds them in idle time once the camera rests (scene.tsx Hotspots) and picks without one
    // until then.
    const list = hotspotMeshes.get(id);
    if (list) list.push(o);
    else hotspotMeshes.set(id, [o]);
  });

  return {
    root,
    hotspotMeshes,
    cardMaterials: [...cardMaterials],
    proxies,
    litMaterials: litPatched.size,
    colorClasses: classes.size,
    waterfallMeshes,
    mergedFrom,
    mergedInto,
  };
}

/**
 * Frees the GPU and CPU copies of everything under the roots (geometries, materials, textures),
 * except the materials and textures in `keep` (shared ones, like the sky used as a water reflection).
 */
export function disposeObjects(roots: readonly Object3D[], keep?: ReadonlySet<Material | Texture>): void {
  const mats = new Set<Material>();
  const geos = new Set<BufferGeometry>();
  for (const r of roots) {
    r.traverse((o) => {
      const m = o as Mesh;
      if (!m.isMesh) return;
      geos.add(m.geometry);
      for (const mat of Array.isArray(m.material) ? m.material : [m.material]) if (mat && !keep?.has(mat)) mats.add(mat);
    });
  }
  for (const g of geos) g.dispose();
  for (const m of mats) {
    for (const v of Object.values(m)) {
      const t = v as Texture | null;
      if (!t || !(t as Texture).isTexture || keep?.has(t)) continue;
      // A set dropped before its upload (a load cancelled late) still holds its decoded images:
      // free them now, not whenever the garbage collector runs (about 67 MB per 4096 atlas).
      if (typeof ImageBitmap !== "undefined" && t.image instanceof ImageBitmap) closeImage(t.image);
      t.dispose();
    }
    m.dispose();
  }
}
