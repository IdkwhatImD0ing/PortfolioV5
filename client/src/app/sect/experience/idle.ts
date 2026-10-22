/**
 * Idle motion for each area while its chunk is drawn, so a stop is never a still picture
 * (lib/sect/idle.ts has the math):
 * - the film's turning pieces: the forge's artifacts travel along their tilted hoop, the
 *   formation's core turns, the library's scrolls circle the pagoda (cut out of the merged scenery
 *   when the chunk loads);
 * - the flying cranes over the abode and the summit glide in a loop, beating their wings;
 * - glow rhythms on clickable things: a light running along the mission tablets, the stele rows,
 *   the library floors and the formation pillars; breathing runes at the gate, the mirror, the jade
 *   scroll and the summit arch; the censer's ember and the abode's wind chimes flicker;
 * - cloth and branches: the arena's hackathon banners flutter, and so do the sect's other pole
 *   banners, at the gate, the forge, the arena and the mission hall, and the formation's Five
 *   Element flags (cut out of the merged scenery where they hang or fly); the mirror's and the
 *   abode's peach trees sway (a vertex offset in the shader, weighted so poles and trunks stay put).
 * Nothing moves with reduced motion. planIdleSliced (or planIdle, in one go) runs once per loaded
 * chunk; updateIdle every frame.
 */
import {
  Box3,
  BufferAttribute,
  BufferGeometry,
  Color,
  type IUniform,
  type InstancedMesh,
  type InterleavedBufferAttribute,
  type Material,
  Matrix3,
  Matrix4,
  Mesh,
  type MeshBasicMaterial,
  type Object3D,
  Sphere,
  Vector2,
  Vector3,
} from "three";
import {
  BANNER_HANGS,
  CRANE_GLIDES,
  FILM_TURN_SPEED,
  FLAG_FLIES,
  FORMATION_CORE_SPEED,
  bannerSway,
  bobLift,
  breathe,
  craneFlap,
  glideHeading,
  glidePivot,
  fitRing,
  flicker,
  flySway,
  hangSway,
  inCylinder,
  inFly,
  inHang,
  rigidStep,
  treeSway,
  wave,
  type BannerHang,
  type Cylinder,
  type FlagFly,
  type V3,
} from "@/lib/sect/idle";
import { PREPARE_SLICE_MS, yieldToBrowser, type HotspotEntry, type SliceOptions } from "./prepare";

/** Seconds since the page started, for the sway shader (one clock for every chunk). */
export const IDLE_TIME: IUniform<number> = { value: 0 };
/** 1 while things may sway, 0 with reduced motion (the cloth and branches rest as baked). */
export const IDLE_ON: IUniform<number> = { value: 1 };

interface MeshRef {
  m: Mesh;
  base: Matrix4;
  parentInv: Matrix4;
}

interface RigidGroup {
  meshes: MeshRef[];
  /** Phase of the group's own bob along the axis (radians). */
  bobPhase: number;
  /** The hotspot's pick box, turned with the group (centre and extents, as baked). */
  box: { c: V3; c0: V3; s: V3; s0: V3 } | null;
}

/** Pieces turning together about an axis through a pivot (and bobbing a little along it). */
interface Rigid {
  name: string;
  groups: RigidGroup[];
  pivot: Vector3;
  axis: Vector3;
  /** Radians per second. */
  speed: number;
  angle: number;
  /**
   * Seconds of the piece's own motion: it stops while the piece is pointed at, and both the turn
   * and the bob follow it (on the page clock a hovered crane drifted out from under the pointer).
   */
  clock: number;
  /** Bob amplitude along the axis (m). */
  bob: number;
  /** Hold still while a hotspot with this prefix is under the pointer or highlighted. */
  pauseOn: string | null;
}

interface Glow {
  mats: { mat: MeshBasicMaterial; base: Color }[];
  kind: "breathe" | "wave" | "flicker";
  period: number;
  /** Position in its row (wave), and the row's length. */
  i: number;
  n: number;
  /** Extra brightness at the top of the rhythm (1 + gain times the base). */
  gain: number;
  seed: number;
}

export interface IdlePlan {
  rigid: Rigid[];
  glows: Glow[];
  /** Sway materials of the chunk (their geometry carries the per-vertex weights). */
  sway: number;
  /** Puts moved pick boxes back (the chunk is going away). */
  reset: () => void;
  /** At rest (reduced motion): everything shows as baked. */
  rested: boolean;
}

// ---- what moves where ---------------------------------------------------------------------------

type GlowSpec = { ids: string[]; kind: Glow["kind"]; period: number; gain: number };

const range = (prefix: string, n: number) => Array.from({ length: n }, (_, i) => `${prefix}:${i}`);

/** Glow rhythms per area (hotspot ids; a wave runs in the order given). */
const GLOWS: Record<string, GlowSpec[]> = {
  gate: [{ ids: ["gate-swords"], kind: "breathe", period: 4.5, gain: 0.55 }],
  mirror: [
    { ids: ["mirror"], kind: "breathe", period: 6, gain: 0.4 },
    { ids: ["mirror-censer"], kind: "flicker", period: 1, gain: 0.8 },
  ],
  forge: [{ ids: range("project", 0), kind: "breathe", period: 7, gain: 0.25 }],
  arena: [{ ids: ["arena"], kind: "breathe", period: 5, gain: 0.6 }],
  mission: [{ ids: range("role", 7), kind: "wave", period: 7, gain: 0.9 }],
  // The floors light up from the ground floor (school:2) to the top.
  library: [{ ids: ["school:2", "school:1", "school:0"], kind: "wave", period: 6, gain: 0.7 }],
  steles: [
    { ids: range("skills", 5), kind: "wave", period: 5, gain: 0.8 },
    { ids: ["steles"], kind: "breathe", period: 5, gain: 0.45 },
  ],
  scroll: [{ ids: ["resume"], kind: "breathe", period: 6, gain: 0.6 }],
  formation: [
    { ids: range("arch", 8), kind: "wave", period: 8, gain: 0.9 },
    { ids: ["formation"], kind: "breathe", period: 4, gain: 0.45 },
  ],
  abode: [{ ids: ["fact:3"], kind: "flicker", period: 1, gain: 0.6 }],
  summit: [{ ids: ["summit-arch"], kind: "breathe", period: 6, gain: 0.5 }],
};

/** Banner flutter, tree sway and wing beat: amplitude (m at full weight) and angular frequency (rad/s). */
const BANNER = { amp: 0.32, freq: 2.1 };
/** The formation's flags are bigger (4.6 m out): a little more swing, a little slower. */
const FLAG = { amp: 0.38, freq: 1.7 };
const TREE = { amp: 0.14, freq: 0.85 };
const WINGS = { amp: 0.42, freq: 3.2 };
const SWAY_TREES: Record<string, string[]> = { mirror: ["mirror-blossom"], abode: ["fact:1"] };

// ---- setup --------------------------------------------------------------------------------------

function meshRef(m: Mesh): MeshRef {
  const parentInv = new Matrix4();
  if (m.parent) parentInv.copy(m.parent.matrixWorld).invert();
  return { m, base: m.matrixWorld.clone(), parentInv };
}

function worldPositions(m: Mesh): Float32Array {
  const pos = m.geometry.getAttribute("position");
  const out = new Float32Array(pos.count * 3);
  const v = new Vector3();
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i).applyMatrix4(m.matrixWorld);
    out[i * 3] = v.x;
    out[i * 3 + 1] = v.y;
    out[i * 3 + 2] = v.z;
  }
  return out;
}

function glowMaterials(meshes: Mesh[]): { mat: MeshBasicMaterial; base: Color }[] {
  const out: { mat: MeshBasicMaterial; base: Color }[] = [];
  const seen = new Set<Material>();
  for (const m of meshes) {
    const mat = m.material as MeshBasicMaterial;
    if (Array.isArray(m.material) || seen.has(mat) || !mat.isMeshBasicMaterial || !mat.color) continue;
    seen.add(mat);
    // Glow surfaces only (colour above 1): brightening them never crosses back below the grade's
    // glow threshold, and the baked surfaces around them keep their light.
    if (Math.max(mat.color.r, mat.color.g, mat.color.b) <= 1.001) continue;
    out.push({ mat, base: mat.color.clone() });
  }
  return out;
}

/**
 * Adds the sway offset to a hotspot material copy: the mesh's geometry carries `sectSway` (the
 * offset direction times its weight, and a phase), the shader moves each vertex along it.
 */
function addSway(mat: Material, amp: number, freq: number): void {
  if (mat.userData.sectSway) return;
  mat.userData.sectSway = true;
  const prev = mat.onBeforeCompile;
  const prevKey = mat.customProgramCacheKey.bind(mat);
  const params = { value: new Vector2(amp, freq) };
  mat.onBeforeCompile = (shader, renderer) => {
    prev.call(mat, shader, renderer);
    shader.uniforms.uSectTime = IDLE_TIME;
    shader.uniforms.uSectSwayOn = IDLE_ON;
    shader.uniforms.uSectSway = params;
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        "#include <common>\nattribute vec4 sectSway;\nuniform float uSectTime;\nuniform float uSectSwayOn;\nuniform vec2 uSectSway;",
      )
      .replace(
        "#include <begin_vertex>",
        [
          "#include <begin_vertex>",
          "  float sectSw = sin( uSectTime * uSectSway.y + sectSway.w ) + 0.35 * sin( uSectTime * uSectSway.y * 2.3 + sectSway.w * 1.7 );",
          "  transformed += sectSway.xyz * ( uSectSway.x * sectSw * uSectSwayOn );",
        ].join("\n"),
      );
  };
  mat.customProgramCacheKey = () => `${prevKey()}|sway`;
  mat.needsUpdate = true;
}

/** Writes per-vertex sway weights (computed in world space) into the mesh's own frame. */
function setSway(m: Mesh, weights: (world: Float32Array) => Float32Array, amp: number, freq: number): boolean {
  if (Array.isArray(m.material) || m.geometry.getAttribute("sectSway")) return false;
  const w = weights(worldPositions(m));
  // Directions into the mesh's frame (identity for the baked chunks, whose nodes only translate).
  const toLocal = new Matrix3().setFromMatrix4(new Matrix4().copy(m.matrixWorld).invert());
  const v = new Vector3();
  for (let i = 0; i < w.length; i += 4) {
    v.set(w[i], w[i + 1], w[i + 2]).applyMatrix3(toLocal);
    w[i] = v.x;
    w[i + 1] = v.y;
    w[i + 2] = v.z;
  }
  m.geometry.setAttribute("sectSway", new BufferAttribute(w, 4));
  addSway(m.material, amp, freq);
  return true;
}

/**
 * Vertices or triangles the carve handles between two looks at the clock. On a 4x-slowed phone the
 * library's carve took 174-200 ms in one go; a step of this size is well under a millisecond.
 */
const CARVE_STEP = 2048;

/** What MathUtils.denormalize divides a normalized component of this array by, and whether it is signed. */
function normalizedScale(a: ArrayLike<number>): [number, boolean] | null {
  if (a instanceof Int16Array) return [32767, true];
  if (a instanceof Int8Array) return [127, true];
  if (a instanceof Int32Array) return [2147483647, true];
  if (a instanceof Uint16Array) return [65535, false];
  if (a instanceof Uint8Array || a instanceof Uint8ClampedArray) return [255, false];
  if (a instanceof Uint32Array) return [4294967295, false];
  return null;
}

/**
 * A mesh's vertex positions in its own frame, as getX/getY/getZ return them (quantized ones
 * denormalized the same way), in one plain array: the carve reads them twice (the cylinder test
 * and the carved piece's sphere), and the baked areas' positions are interleaved 16-bit ones,
 * behind a getter per component.
 */
function* localPositions(pos: BufferGeometry["attributes"][string]): Generator<void, Float64Array, void> {
  const n = pos.count;
  const out = new Float64Array(n * 3);
  // Where getX reads: the attribute's own array, or the interleaved buffer's at a stride and offset.
  const il = (pos as InterleavedBufferAttribute).isInterleavedBufferAttribute === true;
  const a = (il ? (pos as InterleavedBufferAttribute).data.array : pos.array) as ArrayLike<number>;
  const stride = il ? (pos as InterleavedBufferAttribute).data.stride : pos.itemSize;
  const offset = il ? (pos as InterleavedBufferAttribute).offset : 0;
  const float = a instanceof Float32Array;
  const scale = pos.normalized && !float ? normalizedScale(a) : null;
  // Half floats (decoded by their own getter) and unknown normalized types: the getters.
  if ((pos as { isFloat16BufferAttribute?: boolean }).isFloat16BufferAttribute === true || (pos.normalized && !float && !scale)) {
    for (let i = 0; i < n; i++) {
      out[i * 3] = pos.getX(i);
      out[i * 3 + 1] = pos.getY(i);
      out[i * 3 + 2] = pos.getZ(i);
      if (i % CARVE_STEP === CARVE_STEP - 1) yield;
    }
    return out;
  }
  for (let i = 0; i < n; i++) {
    const at = i * stride + offset;
    for (let c = 0; c < 3; c++) {
      let v = a[at + c];
      if (scale) v = scale[1] ? Math.max(v / scale[0], -1) : v / scale[0];
      out[i * 3 + c] = v;
    }
    if (i % CARVE_STEP === CARVE_STEP - 1) yield;
  }
  return out;
}

/**
 * What a carve cuts out of the merged scenery, in world space: a height band (tested first, most
 * vertices fail it), which meshes it can reach at all, and which part of it a vertex is in.
 */
interface CarveRegion {
  yMin: number;
  yMax: number;
  /** False for a mesh whose world box keeps clear of the region (passed over unread). */
  touches: (box: Box3) => boolean;
  /** Which part (1..255) a world position inside the band lies in, or 0 for none. */
  part: (x: number, y: number, z: number) => number;
  /**
   * Cut the pieces into small geometries of their own (else they share the scenery's vertex
   * buffers), with their bounding spheres this much (m) larger: for pieces that sway in the shader.
   */
  compact?: { pad: number };
}

/** The library's shell round the pagoda as a carve. */
function cylinderRegion(cyl: Cylinder): CarveRegion {
  return {
    yMin: cyl.yMin,
    yMax: cyl.yMax,
    touches: (bb) => {
      const nx = Math.max(bb.min.x, Math.min(cyl.x, bb.max.x));
      const nz = Math.max(bb.min.z, Math.min(cyl.z, bb.max.z));
      return Math.hypot(nx - cyl.x, nz - cyl.z) <= cyl.rMax;
    },
    part: (x, y, z) => (inCylinder(cyl, x, y, z) ? 1 : 0),
  };
}

/** An area's flags as a carve: each flag's cloth is a part, cut out on its own to flutter. */
function flyRegion(flies: readonly FlagFly[]): CarveRegion {
  // A box round each flag's space (inFly's bounds, a little wider).
  const boxes = flies.map((f) => {
    const r = Math.hypot(f.reach + 0.2, f.billow + 0.2);
    return new Box3(new Vector3(f.pole[0] - r, f.bottom - 0.3, f.pole[1] - r), new Vector3(f.pole[0] + r, f.top + 0.1, f.pole[1] + r));
  });
  return {
    yMin: Math.min(...boxes.map((b) => b.min.y)),
    yMax: Math.max(...boxes.map((b) => b.max.y)),
    touches: (bb) => boxes.some((b) => b.intersectsBox(bb)),
    part: (x, y, z) => {
      for (let k = 0; k < flies.length; k++) if (inFly(flies[k], x, y, z)) return k + 1;
      return 0;
    },
    // Room for the flutter (FLAG.amp at full weight, across and FLY_LIFT up, both waves at their peak).
    compact: { pad: 0.6 },
  };
}

/** An area's banners as a carve: each hang's cloth is a part, cut out on its own to flutter. */
function hangRegion(hangs: readonly BannerHang[]): CarveRegion {
  // A box round each hang's space (inHang's bounds, a little wider).
  const boxes = hangs.map((h) => {
    const r = Math.max(0.685 * h.width, 0.63 * h.width + 0.05 * h.length) + 0.2;
    return new Box3(new Vector3(h.hook[0] - r, h.hook[1] - h.length - 0.7, h.hook[2] - r), new Vector3(h.hook[0] + r, h.hook[1] + 0.1, h.hook[2] + r));
  });
  return {
    yMin: Math.min(...boxes.map((b) => b.min.y)),
    yMax: Math.max(...boxes.map((b) => b.max.y)),
    touches: (bb) => boxes.some((b) => b.intersectsBox(bb)),
    part: (x, y, z) => {
      for (let k = 0; k < hangs.length; k++) if (inHang(hangs[k], x, y, z)) return k + 1;
      return 0;
    },
    compact: { pad: 0.45 },
  };
}

/**
 * Which part of the region each vertex (`local`, from localPositions) lies in (0: none), tested in
 * world space. Exactly the test splitTriangles made on worldPositions (the world position rounded
 * to 32 bits, then the region's test), without the copy: the height is checked before the rest.
 */
function* regionParts(local: Float64Array, matrixWorld: Matrix4, region: CarveRegion): Generator<void, Uint8Array, void> {
  const n = local.length / 3;
  const ins = new Uint8Array(n);
  const e = matrixWorld.elements;
  for (let i = 0; i < n; i++) {
    const x = local[i * 3];
    const y = local[i * 3 + 1];
    const z = local[i * 3 + 2];
    // As Vector3.applyMatrix4.
    const w = 1 / (e[3] * x + e[7] * y + e[11] * z + e[15]);
    const wy = Math.fround((e[1] * x + e[5] * y + e[9] * z + e[13]) * w);
    if (wy >= region.yMin && wy <= region.yMax) {
      const wx = Math.fround((e[0] * x + e[4] * y + e[8] * z + e[12]) * w);
      const wz = Math.fround((e[2] * x + e[6] * y + e[10] * z + e[14]) * w);
      ins[i] = region.part(wx, wy, wz);
    }
    if (i % CARVE_STEP === CARVE_STEP - 1) yield;
  }
  return ins;
}

type Numbers = Float32Array | Float64Array | Int8Array | Int16Array | Int32Array | Uint8Array | Uint8ClampedArray | Uint16Array | Uint32Array;

/**
 * The vertices `ids` of an attribute in a plain one of their own, the stored values copied as they
 * are (quantized ones stay quantized; an interleaved one comes out on its own).
 */
function compactAttribute(attr: BufferAttribute | InterleavedBufferAttribute, ids: Uint32Array): BufferAttribute {
  const il = (attr as InterleavedBufferAttribute).isInterleavedBufferAttribute === true;
  const src = (il ? (attr as InterleavedBufferAttribute).data.array : (attr as BufferAttribute).array) as Numbers;
  const stride = il ? (attr as InterleavedBufferAttribute).data.stride : attr.itemSize;
  const offset = il ? (attr as InterleavedBufferAttribute).offset : 0;
  const size = attr.itemSize;
  const out = new (src.constructor as new (n: number) => Numbers)(ids.length * size);
  for (let k = 0; k < ids.length; k++) {
    const at = ids[k] * stride + offset;
    for (let c = 0; c < size; c++) out[k * size + c] = src[at + c];
  }
  if (il) return new BufferAttribute(out, size, attr.normalized);
  // Its own kind (a half-float attribute keeps decoding as one), and how it reaches the GPU.
  const a = attr as BufferAttribute;
  const copy = new (a.constructor as typeof BufferAttribute)(out, size, a.normalized);
  copy.gpuType = a.gpuType;
  return copy;
}

/**
 * A geometry of the vertices the carved triangles use (`used`), in their order, and the carved
 * triangles re-indexed onto it: a swaying piece's own `sectSway` then covers its own few
 * vertices, not the whole merged mesh's.
 */
function* compactGeometry(g: BufferGeometry, carved: ArrayLike<number>, used: Uint8Array): Generator<void, BufferGeometry, void> {
  const remap = new Uint32Array(used.length);
  let n = 0;
  for (let i = 0; i < used.length; i++) {
    if (used[i]) remap[i] = n++;
    if (i % CARVE_STEP === CARVE_STEP - 1) yield;
  }
  const ids = new Uint32Array(n);
  for (let i = 0; i < used.length; i++) if (used[i]) ids[remap[i]] = i;
  const cg = new BufferGeometry();
  for (const [name, attr] of Object.entries(g.attributes)) {
    yield;
    cg.setAttribute(name, compactAttribute(attr, ids));
  }
  const index = new (n > 65535 ? Uint32Array : Uint16Array)(carved.length);
  for (let t = 0; t < carved.length; t++) index[t] = remap[carved[t]];
  cg.setIndex(new BufferAttribute(index, 1));
  return cg;
}

/**
 * A copy of a scenery material for pieces that sway, made as prepare.ts makes its glow copies:
 * the sway shader declares `sectSway`, and the scenery left behind, which has no such attribute,
 * must keep a program without it (WebGL would feed it a stale value).
 */
function swayCopy(mat: Material, copies: Map<Material, Material>): Material {
  let copy = copies.get(mat);
  if (!copy) {
    copy = mat.clone();
    copy.onBeforeCompile = mat.onBeforeCompile;
    copy.customProgramCacheKey = mat.customProgramCacheKey;
    copies.set(mat, copy);
  }
  return copy;
}

/**
 * The bounding sphere of the vertices the carved triangles use (`used`), centred on their box as
 * three's computeBoundingSphere is. Over the whole vertex buffer, which the carved piece shares with
 * the rest of the scenery, it was a third of the carve's time; this one bounds only what the piece
 * draws, which is all culling needs.
 */
function* carvedSphere(local: Float64Array, used: Uint8Array): Generator<void, Sphere, void> {
  let x0 = Infinity, y0 = Infinity, z0 = Infinity, x1 = -Infinity, y1 = -Infinity, z1 = -Infinity;
  for (let i = 0; i < used.length; i++) {
    if (i % CARVE_STEP === CARVE_STEP - 1) yield;
    if (!used[i]) continue;
    const x = local[i * 3], y = local[i * 3 + 1], z = local[i * 3 + 2];
    if (x < x0) x0 = x;
    if (y < y0) y0 = y;
    if (z < z0) z0 = z;
    if (x > x1) x1 = x;
    if (y > y1) y1 = y;
    if (z > z1) z1 = z;
  }
  const c = new Vector3((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
  let maxSq = 0;
  for (let i = 0; i < used.length; i++) {
    if (i % CARVE_STEP === CARVE_STEP - 1) yield;
    if (!used[i]) continue;
    const dx = c.x - local[i * 3], dy = c.y - local[i * 3 + 1], dz = c.z - local[i * 3 + 2];
    maxSq = Math.max(maxSq, dx * dx + dy * dy + dz * dz);
  }
  return new Sphere(c, Math.sqrt(maxSq));
}

/**
 * Cuts the triangles of `root`'s merged meshes whose three corners lie in one part of the region
 * into meshes of their own (same material; same vertex buffers, or with `compact` small ones of
 * their own), so they can turn or sway. Hotspot meshes stay whole. The same split as
 * splitTriangles over worldPositions, yielding every CARVE_STEP vertices or triangles; a mesh's
 * index only changes once its whole split is known.
 */
function* carveRegion(root: Object3D, skip: Set<Mesh>, region: CarveRegion): Generator<void, Mesh[], void> {
  root.updateMatrixWorld(true);
  const meshes: Mesh[] = [];
  root.traverse((o) => {
    const m = o as Mesh;
    if (m.isMesh && !(m as InstancedMesh).isInstancedMesh && !skip.has(m) && !Array.isArray(m.material)) meshes.push(m);
  });
  yield;
  const out: Mesh[] = [];
  for (const m of meshes) {
    const g = m.geometry;
    const pos = g.getAttribute("position");
    if (!pos) continue;
    // A compact piece carries no morph targets along.
    if (region.compact && Object.keys(g.morphAttributes).length) continue;
    if (!g.boundingBox) {
      g.computeBoundingBox();
      yield;
    }
    const bb = g.boundingBox!.clone().applyMatrix4(m.matrixWorld);
    if (bb.max.y < region.yMin || bb.min.y > region.yMax) continue;
    if (!region.touches(bb)) continue;
    const local = yield* localPositions(pos);
    const ins = yield* regionParts(local, m.matrixWorld, region);
    const index = g.index ? g.index.array : null;
    const count = index ? index.length : pos.count;
    const Arr = pos.count > 65535 ? Uint32Array : Uint16Array;
    const kept = new Arr(count);
    const carved = new Arr(count);
    const used = new Uint8Array(pos.count);
    let nk = 0;
    let nc = 0;
    for (let t = 0; t + 2 < count; t += 3) {
      const a = index ? index[t] : t;
      const b = index ? index[t + 1] : t + 1;
      const c = index ? index[t + 2] : t + 2;
      const p = ins[a];
      if (p && ins[b] === p && ins[c] === p) {
        carved[nc++] = a;
        carved[nc++] = b;
        carved[nc++] = c;
        used[a] = used[b] = used[c] = 1;
      } else {
        kept[nk++] = a;
        kept[nk++] = b;
        kept[nk++] = c;
      }
      if (t % (3 * CARVE_STEP) === 3 * CARVE_STEP - 3) yield;
    }
    if (nc === 0) continue;
    const sphere = yield* carvedSphere(local, used);
    const carvedIndex = carved.slice(0, nc);
    let cg: BufferGeometry;
    if (region.compact) {
      cg = yield* compactGeometry(g, carvedIndex, used);
      // Room for the sway, in the mesh's own units (the baked nodes scale their quantized positions).
      sphere.radius += region.compact.pad / Math.max(1e-9, m.matrixWorld.getMaxScaleOnAxis());
    } else {
      cg = new BufferGeometry();
      for (const [name, attr] of Object.entries(g.attributes)) cg.setAttribute(name, attr);
      cg.setIndex(new BufferAttribute(carvedIndex, 1));
    }
    g.setIndex(new BufferAttribute(kept.slice(0, nk), 1));
    cg.boundingSphere = sphere;
    const cm = new Mesh(cg, m.material);
    cm.name = `${m.name}.idle`;
    cm.matrixAutoUpdate = false;
    cm.matrix.copy(m.matrix);
    cm.renderOrder = m.renderOrder;
    cm.castShadow = m.castShadow;
    cm.receiveShadow = m.receiveShadow;
    m.parent?.add(cm);
    cm.matrixWorld.copy(m.matrixWorld);
    out.push(cm);
  }
  return out;
}

/**
 * Cuts the region's cloth out of the merged scenery, onto a copy of its material, and sets it
 * fluttering with `weights` (computed on its world positions), counting each piece in the plan.
 */
function* swayCut(
  plan: IdlePlan,
  main: Object3D,
  skip: Set<Mesh>,
  region: CarveRegion,
  weights: (world: Float32Array) => Float32Array,
  motion: { amp: number; freq: number },
): Generator<void, void, void> {
  const pieces = yield* carveRegion(main, skip, region);
  const copies = new Map<Material, Material>();
  for (const m of pieces) {
    yield;
    m.material = swayCopy(m.material as Material, copies);
    if (setSway(m, weights, motion.amp, motion.freq)) plan.sway++;
  }
}

/** The forge hoop's ring, from its glowing tube in the merged scenery (else the artifacts' plane). */
function* forgeRing(main: Object3D | null, skip: Set<Mesh>, centers: V3[]): Generator<void, { pivot: Vector3; axis: Vector3 } | null, void> {
  const guess = centers.reduce<V3>((a, c) => [a[0] + c[0] / centers.length, a[1] + c[1] / centers.length, a[2] + c[2] / centers.length], [0, 0, 0]);
  const pts: V3[] = [];
  main?.updateMatrixWorld(true);
  const tubes: Mesh[] = [];
  main?.traverse((o) => {
    const m = o as Mesh;
    if (m.isMesh && !skip.has(m) && !Array.isArray(m.material) && /\.glow\.rune_cyan$/i.test(m.material.name)) tubes.push(m);
  });
  for (const m of tubes) {
    yield;
    const w = worldPositions(m);
    for (let i = 0; i < w.length; i += 3) {
      const d = Math.hypot(w[i] - guess[0], w[i + 1] - guess[1], w[i + 2] - guess[2]);
      if (d > 9 && d < 17 && Math.abs(w[i + 1] - guess[1]) < 4.5) pts.push([w[i], w[i + 1], w[i + 2]]);
    }
  }
  yield;
  let fit = fitRing(pts);
  if (!fit || fit.radius < 9 || fit.radius > 17 || fit.planeError > 0.8) fit = fitRing(centers);
  if (!fit) return null;
  return { pivot: new Vector3(...fit.center), axis: new Vector3(...fit.normal).normalize() };
}

/**
 * What idles in a freshly loaded chunk. `main` is the area's own scene (not its trees or water);
 * `hotspotMeshes` covers all of the chunk's files. In one go: the streamed chunks use
 * planIdleSliced, which does the same work a few milliseconds at a time.
 */
export function planIdle(
  id: string,
  main: Object3D | null,
  hotspotMeshes: Map<string, Mesh[]>,
  hotspots: Map<string, HotspotEntry>,
): IdlePlan {
  const steps = planSteps(id, main, hotspotMeshes, hotspots);
  for (;;) {
    const r = steps.next();
    if (r.done) return r.value;
  }
}

/**
 * planIdle in slices of about `budgetMs` of main-thread time (PREPARE_SLICE_MS by default), letting
 * the browser draw between them (yieldToBrowser), as prepareSceneSliced does: on a 4x-slowed phone
 * the library's carve froze a rest for 174-200 ms in one go. Same plan as planIdle. Once the
 * signal is aborted it stops between two slices and returns what it planned so far, for the caller
 * to undo and free with the rest of the load (a mesh is only ever carved whole or not at all).
 */
export async function planIdleSliced(
  id: string,
  main: Object3D | null,
  hotspotMeshes: Map<string, Mesh[]>,
  hotspots: Map<string, HotspotEntry>,
  slice: SliceOptions = {},
): Promise<IdlePlan> {
  const now = slice.now ?? (() => performance.now());
  const budget = slice.budgetMs ?? PREPARE_SLICE_MS;
  const pause = slice.pause ?? yieldToBrowser;
  const partial: { plan: IdlePlan | null } = { plan: null };
  const steps = planSteps(id, main, hotspotMeshes, hotspots, partial);
  let t0 = now();
  for (;;) {
    const r = steps.next();
    if (r.done) return r.value;
    if (now() - t0 < budget) continue;
    await pause();
    if (slice.signal?.aborted) {
      steps.return(undefined as never);
      return partial.plan!;
    }
    t0 = now();
  }
}

/** The work of planIdle, yielding wherever it may stop for a frame. `partial` gets the plan at once. */
function* planSteps(
  id: string,
  main: Object3D | null,
  hotspotMeshes: Map<string, Mesh[]>,
  hotspots: Map<string, HotspotEntry>,
  partial: { plan: IdlePlan | null } = { plan: null },
): Generator<void, IdlePlan, void> {
  const rigid: Rigid[] = [];
  const glows: Glow[] = [];
  const reset = () => {
    for (const r of rigid) {
      for (const g of r.groups) {
        if (!g.box) continue;
        for (let k = 0; k < 3; k++) {
          g.box.c[k] = g.box.c0[k];
          g.box.s[k] = g.box.s0[k];
        }
      }
    }
  };
  const plan: IdlePlan = { rigid, glows, sway: 0, reset, rested: true };
  partial.plan = plan;
  const skip = new Set<Mesh>([...hotspotMeshes.values()].flat());

  // Glow rhythms.
  for (const spec of GLOWS[id] ?? []) {
    const ids = spec.ids.length ? spec.ids : [...hotspotMeshes.keys()].filter((h) => h.startsWith("project:"));
    ids.forEach((hid, i) => {
      const mats = glowMaterials(hotspotMeshes.get(hid) ?? []);
      if (mats.length) glows.push({ mats, kind: spec.kind, period: spec.period, i, n: ids.length, gain: spec.gain, seed: i * 1.7 });
    });
  }
  yield;

  // The forge's artifacts along their hoop.
  if (id === "forge") {
    const items = [...hotspotMeshes].filter(([h]) => h.startsWith("project:"));
    const entries = items
      .map(([h, meshes]) => ({ e: hotspots.get(h), meshes }))
      .filter((x): x is { e: HotspotEntry; meshes: Mesh[] } => x.e !== undefined);
    const ring = entries.length >= 3 ? yield* forgeRing(main, skip, entries.map((x) => x.e.center as V3)) : null;
    if (ring) {
      rigid.push({
        name: "forge.ring",
        groups: entries.map((x, k) => ({
          meshes: x.meshes.map(meshRef),
          bobPhase: k * 2.399,
          box: { c: x.e.center as V3, c0: [...x.e.center] as V3, s: x.e.size as V3, s0: [...x.e.size] as V3 },
        })),
        pivot: ring.pivot,
        axis: ring.axis,
        speed: FILM_TURN_SPEED,
        angle: 0,
        clock: 0,
        bob: 0.18,
        pauseOn: "project:",
      });
    }
  }

  // The formation's core turns on its axis.
  if (id === "formation") {
    const core = hotspotMeshes.get("formation");
    const e = hotspots.get("formation");
    if (core?.length && e) {
      rigid.push({
        name: "formation.core",
        groups: [{ meshes: core.map(meshRef), bobPhase: 0, box: null }],
        pivot: new Vector3(e.center[0], e.center[1], e.center[2]),
        axis: new Vector3(0, 1, 0),
        speed: FORMATION_CORE_SPEED,
        angle: 0,
        clock: 0,
        bob: 0,
        pauseOn: null,
      });
    }
  }

  // The library's scroll spiral circles the pagoda (cut from the merged scenery around it).
  if (id === "library" && main) {
    const e = hotspots.get("library");
    if (e) {
      const ground = e.center[1] - e.size[1] / 2;
      const carved = yield* carveRegion(
        main,
        skip,
        cylinderRegion({
          x: e.center[0],
          z: e.center[2],
          rMin: 8,
          rMax: 19,
          yMin: ground + 4.3,
          yMax: ground + e.size[1] + 2,
        }),
      );
      if (carved.length) {
        rigid.push({
          name: "library.spiral",
          groups: [{ meshes: carved.map(meshRef), bobPhase: 0, box: null }],
          pivot: new Vector3(e.center[0], ground, e.center[2]),
          axis: new Vector3(0, 1, 0),
          speed: FILM_TURN_SPEED,
          angle: 0,
          clock: 0,
          bob: 0,
          pauseOn: null,
        });
      }
    }
  }

  // Banners flutter; peach trees sway (a mesh at a time).
  if (id === "arena") {
    for (const [h, meshes] of hotspotMeshes) {
      if (!h.startsWith("hackathon:")) continue;
      for (const m of meshes) {
        yield;
        if (setSway(m, bannerSway, BANNER.amp, BANNER.freq)) plan.sway++;
      }
    }
  }
  // The banners merged into the baked scenery (BANNER_HANGS: the gate's, the forge's, the arena's
  // four that no hackathon claims, the mission hall's): their cloth is cut out where it hangs, onto
  // a copy of its material, and flutters as props.banner's wave did in Blender.
  const hangs = BANNER_HANGS[id];
  if (hangs?.length && main) yield* swayCut(plan, main, skip, hangRegion(hangs), (w) => hangSway(w, hangs), BANNER);
  // The flags flying from their poles' tops (FLAG_FLIES: the formation's Five Element Banners, in the
  // formation's chunk and the abode's), the same way, rippling out from the pole.
  const flies = FLAG_FLIES[id];
  if (flies?.length && main) yield* swayCut(plan, main, skip, flyRegion(flies), (w) => flySway(w, flies), FLAG);
  for (const h of SWAY_TREES[id] ?? []) {
    for (const m of hotspotMeshes.get(h) ?? []) {
      yield;
      if (setSway(m, (w) => treeSway(w), TREE.amp, TREE.freq)) plan.sway++;
    }
  }

  // The flying cranes glide in a loop (holding still under the pointer) and beat their wings.
  for (const [h, glide] of Object.entries(CRANE_GLIDES)) {
    const meshes = hotspotMeshes.get(h);
    const e = hotspots.get(h);
    if (!meshes?.length || !e) continue;
    const pivot = glidePivot(e.center as V3, glideHeading(glide), glide.radius);
    rigid.push({
      name: h,
      groups: [
        {
          meshes: meshes.map(meshRef),
          bobPhase: 0,
          box: { c: e.center as V3, c0: [...e.center] as V3, s: e.size as V3, s0: [...e.size] as V3 },
        },
      ],
      pivot: new Vector3(...pivot),
      axis: new Vector3(0, 1, 0),
      speed: glide.speed,
      angle: 0,
      clock: 0,
      bob: 0.6,
      pauseOn: h,
    });
    for (const m of meshes) {
      yield;
      if (setSway(m, (w) => craneFlap(w, glide.cranes), WINGS.amp, WINGS.freq)) plan.sway++;
    }
  }
  return plan;
}

// ---- per frame ----------------------------------------------------------------------------------

const rot = new Matrix4();
const tmp = new Matrix4();
const world = new Matrix4();
const r3 = new Matrix3();
const off = new Vector3();

function glowLevel(g: Glow, t: number): number {
  switch (g.kind) {
    case "breathe":
      return breathe(t, g.period, g.i / Math.max(1, g.n));
    case "wave":
      return wave(t, g.period, g.i, g.n);
    case "flicker":
      return flicker(t, g.seed);
  }
}

function placeRigid(r: Rigid): void {
  // Rotation about the axis through the pivot: T(p) R T(-p).
  rot.makeTranslation(r.pivot.x, r.pivot.y, r.pivot.z)
    .multiply(tmp.makeRotationAxis(r.axis, r.angle))
    .multiply(tmp.makeTranslation(-r.pivot.x, -r.pivot.y, -r.pivot.z));
  r3.setFromMatrix4(rot);
  for (const g of r.groups) {
    const lift = bobLift(r.clock, r.bob, g.bobPhase);
    off.copy(r.axis).multiplyScalar(lift);
    for (const x of g.meshes) {
      world.multiplyMatrices(rot, x.base);
      world.elements[12] += off.x;
      world.elements[13] += off.y;
      world.elements[14] += off.z;
      x.m.matrixWorld.copy(world);
      x.m.matrix.multiplyMatrices(x.parentInv, world);
    }
    if (g.box) {
      const { c, c0, s, s0 } = g.box;
      const e = r3.elements; // column-major
      const dx = c0[0] - r.pivot.x, dy = c0[1] - r.pivot.y, dz = c0[2] - r.pivot.z;
      c[0] = r.pivot.x + e[0] * dx + e[3] * dy + e[6] * dz + off.x;
      c[1] = r.pivot.y + e[1] * dx + e[4] * dy + e[7] * dz + off.y;
      c[2] = r.pivot.z + e[2] * dx + e[5] * dy + e[8] * dz + off.z;
      // The axis-aligned box around the turned one.
      s[0] = Math.abs(e[0]) * s0[0] + Math.abs(e[3]) * s0[1] + Math.abs(e[6]) * s0[2];
      s[1] = Math.abs(e[1]) * s0[0] + Math.abs(e[4]) * s0[1] + Math.abs(e[7]) * s0[2];
      s[2] = Math.abs(e[2]) * s0[0] + Math.abs(e[5]) * s0[1] + Math.abs(e[8]) * s0[2];
    }
  }
}

/**
 * Moves one chunk's idle pieces to time `t` (seconds). `dt` advances the turning pieces on their
 * own clocks, which stop (turn and bob alike) while the visitor points at one of them. With `still`
 * (reduced motion) everything goes back to how it was baked and stays.
 */
export function updateIdle(plan: IdlePlan, t: number, dt: number, still: boolean, pointed: (prefix: string) => boolean): void {
  if (still) {
    if (plan.rested) return;
    for (const g of plan.glows) for (const { mat, base } of g.mats) mat.color.copy(base);
    for (const r of plan.rigid) {
      r.angle = 0;
      r.clock = 0;
      for (const g of r.groups) {
        for (const x of g.meshes) {
          x.m.matrixWorld.copy(x.base);
          x.m.matrix.multiplyMatrices(x.parentInv, x.base);
        }
      }
    }
    plan.reset();
    plan.rested = true;
    return;
  }
  plan.rested = false;
  for (const g of plan.glows) {
    const k = 1 + g.gain * glowLevel(g, t);
    for (const { mat, base } of g.mats) mat.color.copy(base).multiplyScalar(k);
  }
  for (const r of plan.rigid) {
    const step = rigidStep(dt, r.pauseOn !== null && pointed(r.pauseOn));
    r.angle += step * r.speed;
    r.clock += step;
    placeRigid(r);
  }
}
