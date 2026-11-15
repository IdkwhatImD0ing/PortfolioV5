/**
 * Far trees as lit crown shells (experience/veg.tsx draws them on the High tier).
 *
 * The bake draws a far tree as a card: three flat textured quads (front, side and a level top).
 * Seen from above, as most of the flight sees them, the top quads read as flat green plates and the
 * forest as blocks. Here every card plant becomes one or more low-poly crowns built in code: a unit
 * shell placed, sized and turned per instance, made lumpy in the vertex shader and lit in the
 * fragment shader (wrap sun, sky ambient, light through the leaves toward the sun), with a ragged
 * silhouette eroded out of an object-space noise. Boughs a few metres across change the light only:
 * each has a lit side, a shaded side and a darker crease. A crown deep among its neighbours
 * (vegDepth, worked out here from the plant list) has a darker lower half. Nothing but the plant list is
 * downloaded: blender/xianxia-sect/tools/sect_veg.py writes one small binary per area,
 * public/sect/full/veg/<chunk>.veg, from the Blender export.
 *
 * <chunk>.veg (little-endian): a 16-byte header ("SVEG", uint32 version 1, uint32 count, uint32 0),
 * then `count` records of 24 bytes: float32 x, y, z (three.js coordinates: the foot of the trunk),
 * float32 height, float32 radius (the tree's world box: its height, and half its larger horizontal
 * extent), uint8 yaw (0-255 = 0-2 pi about +y), uint8 sun (0-255 = in terrain shadow to sunlit),
 * uint8 family (an index into index.json's families), uint8 flags (VEG_FLAG).
 *
 * Every tunable number is in VEG_LOOK. Pure data, maths and GLSL strings (no three.js import), so it
 * is testable.
 */
import { farCutCellGlsl } from "./card-shading";
import { glslFloat, glslVec3, hexToLinear } from "./glsl";
import { gradeGlsl, SECT_LOOK, treeShadeGlsl, unitTint } from "./look";
import type { Quality } from "./runtime";
import type { Vec3 } from "./types";

const f = glslFloat;

// ---------------------------------------------------------------------------------------------
// The file

export const VEG_MAGIC = "SVEG";
export const VEG_VERSION = 1;
export const VEG_HEADER_BYTES = 16;
export const VEG_RECORD_BYTES = 24;

/** Record flags: the baked files draw the plant as a near mesh (not a card); it belongs to a click target. */
export const VEG_FLAG = { mesh: 1, hotspot: 2 } as const;

/** One chunk's plants, as parseVeg reads them. */
export interface VegData {
  count: number;
  /** Foot of the trunk (three.js world, y up), 3 per plant. */
  pos: Float32Array;
  /** The tree's height and radius (m). */
  height: Float32Array;
  radius: Float32Array;
  /** 0-255 = 0-2 pi about +y (vegYaw). */
  yaw: Uint8Array;
  /** 0-255 = in terrain shadow to sunlit. */
  sun: Uint8Array;
  /** Index into the index file's families. */
  family: Uint8Array;
  flags: Uint8Array;
}

/** Reads a .veg file. Throws on a wrong magic, an unknown version or a length that does not match the count. */
export function parseVeg(buffer: ArrayBuffer): VegData {
  if (buffer.byteLength < VEG_HEADER_BYTES) throw new Error(`veg: ${buffer.byteLength} bytes is too short for the header`);
  const dv = new DataView(buffer);
  const magic = String.fromCharCode(dv.getUint8(0), dv.getUint8(1), dv.getUint8(2), dv.getUint8(3));
  if (magic !== VEG_MAGIC) throw new Error(`veg: bad magic "${magic}"`);
  const version = dv.getUint32(4, true);
  if (version !== VEG_VERSION) throw new Error(`veg: version ${version} (this page reads ${VEG_VERSION})`);
  const count = dv.getUint32(8, true);
  const want = VEG_HEADER_BYTES + count * VEG_RECORD_BYTES;
  if (buffer.byteLength !== want) throw new Error(`veg: ${buffer.byteLength} bytes for ${count} plants (want ${want})`);
  const out: VegData = {
    count,
    pos: new Float32Array(count * 3),
    height: new Float32Array(count),
    radius: new Float32Array(count),
    yaw: new Uint8Array(count),
    sun: new Uint8Array(count),
    family: new Uint8Array(count),
    flags: new Uint8Array(count),
  };
  for (let i = 0; i < count; i++) {
    const o = VEG_HEADER_BYTES + i * VEG_RECORD_BYTES;
    out.pos[i * 3] = dv.getFloat32(o, true);
    out.pos[i * 3 + 1] = dv.getFloat32(o + 4, true);
    out.pos[i * 3 + 2] = dv.getFloat32(o + 8, true);
    out.height[i] = dv.getFloat32(o + 12, true);
    out.radius[i] = dv.getFloat32(o + 16, true);
    out.yaw[i] = dv.getUint8(o + 20);
    out.sun[i] = dv.getUint8(o + 21);
    out.family[i] = dv.getUint8(o + 22);
    out.flags[i] = dv.getUint8(o + 23);
  }
  return out;
}

/** A yaw byte in radians (0-255 = 0-2 pi; rotation about +y, so the tree's local +x turns toward -z). */
export function vegYaw(byte: number): number {
  return (byte * Math.PI * 2) / 256;
}

/** index.json beside the .veg files. */
export interface VegIndex {
  version: number;
  families: string[];
  chunks: Record<string, { file: string; count: number; cards: number }>;
}

/** Reads index.json. Throws when it is not version 1 or its families or chunks are malformed. */
export function parseVegIndex(raw: unknown): VegIndex {
  const o = raw as Partial<VegIndex> | null;
  if (!o || typeof o !== "object") throw new Error("veg index: not an object");
  if (o.version !== VEG_VERSION) throw new Error(`veg index: version ${String(o.version)}`);
  if (!Array.isArray(o.families) || !o.families.every((s) => typeof s === "string")) throw new Error("veg index: families must be strings");
  if (!o.chunks || typeof o.chunks !== "object") throw new Error("veg index: no chunks");
  const chunks: VegIndex["chunks"] = {};
  for (const [id, c] of Object.entries(o.chunks)) {
    if (!/^[a-z0-9_-]+$/.test(id)) throw new Error(`veg index: bad chunk id "${id}"`);
    const e = c as { file?: unknown; count?: unknown; cards?: unknown };
    if (typeof e.file !== "string" || !/^[a-z0-9_-]+\.veg$/.test(e.file)) throw new Error(`veg index: chunk ${id} has no file`);
    chunks[id] = { file: e.file, count: Number(e.count) || 0, cards: Number(e.cards) || 0 };
  }
  return { version: VEG_VERSION, families: [...o.families], chunks };
}

/** The .veg chunk a loaded set's shells come from: the global set's are the backdrop's. */
export function vegChunkId(setId: string): string {
  return setId === "global" ? "backdrop" : setId;
}

// ---------------------------------------------------------------------------------------------
// The look

/** Crown shapes. */
export const VEG_ARCHETYPES = ["broadleaf", "huangshan", "masson", "shrub", "bamboo", "blossom"] as const;
export type VegArchetype = (typeof VEG_ARCHETYPES)[number];

/** Colour sets (VEG_LOOK.palettes); the tone attribute is the index in this list. */
export const VEG_TONES = ["broadleaf", "pine", "shrub", "scrub", "blossom", "bamboo"] as const;
export type VegTone = (typeof VEG_TONES)[number];

/** A single-shell crown's shape (archetypes other than huangshan). */
export interface CrownShape {
  /** Horizontal radius as a share of the tree's radius. */
  width: number;
  /** Cap on height / width (ry / rx), so the crown is wider than tall; 0 = no cap. */
  tall: number;
  /** Cap on width / height (rx / ry), so the crown is a spire; 0 = no cap. */
  narrow: number;
  /** The top narrows by this share of the width (0 = round, toward 1 = a point). */
  taper: number;
}

export interface VegLook {
  /** The unit crown: 1 = icosphere (80 triangles), 0 = octahedron sphere (32). */
  detail: 0 | 1;
  /** Positions are rounded to this many metres before hashing the seed (stable across exports). */
  seedQuantumM: number;
  /** Family name prefix to archetype, first match wins. Families no prefix matches are skipped. */
  families: readonly (readonly [string, VegArchetype])[];
  crown: {
    /** A one-crown plant's width is its radius times a seeded value between these two. */
    widthVary: readonly [number, number];
    /** Share of the tree's height the crown covers, from the top (shrubs cover all of it). */
    cover: number;
    shapes: Record<Exclude<VegArchetype, "huangshan">, CrownShape>;
  };
  /** Huangshan pines: flat needle pads along a leaning trunk. */
  pads: {
    /** Pads per tree, at least and at most. */
    count: readonly [number, number];
    /** Height share of the lowest pad's centre; the top pad's top is the tree's top. */
    from: number;
    /** A pad's height as a share of its width. */
    thickness: number;
    /** Pad radius as a share of the tree's radius: lowest pad, top pad. */
    size: readonly [number, number];
    /** How far the trunk leans by the top, as a share of the tree's radius (seeded in this range). */
    lean: readonly [number, number];
    /** Each pad's own sideways jitter, as a share of the tree's radius. */
    jitter: number;
    /** Pad depth as a share of its width (seeded in this range): pads are oval. */
    squash: readonly [number, number];
    /** Each pad turns up to this many radians off the tree's yaw. */
    yawJitter: number;
  };
  /** Vertex lumps: along the normal by +- `amount` of the radius, noise of `scale` cells over the unit shell. */
  displace: { amount: number; scale: number };
  normal: {
    /** Share of the direction from the crown's centre blended into the shell's normal. */
    round: number;
  };
  /**
   * Boughs: a value noise (vegBough) on a lattice turned off the crown's axes, in cells of `cellM` metres
   * (seeded per crown, at most `maxRel` of the crown's largest radius). They change the light only, never
   * the outline. The normal leans down the field's slope by `bump` (so a bough has a lit side and a shaded
   * side; the slope is taken per cell, so the tilt is the same at every bough size), and the crease
   * between boughs (the field from crease[0] up to crease[1]) keeps `dark` of its brightness at the
   * deepest. bump and dark are the defaults of the shared uniform uVegBough (x and y), so they can be
   * tuned at run time. Both ease off to `near` of themselves (uVegBough.z) while a cell grows from px[0]
   * to px[1] pixels on screen, and fade flat while a pixel grows from fade[0] to fade[1] of a cell. The
   * crease keeps its mean brightness at every strength (vegCrease).
   */
  boughs: {
    cellM: readonly [number, number];
    maxRel: number;
    bump: number;
    crease: readonly [number, number];
    dark: number;
    near: number;
    px: readonly [number, number];
    fade: readonly [number, number];
  };
  /**
   * Depth among crowns (vegDepth), per crown, from the plant list. `sink`: a neighbour within `reach`
   * crown radii whose top stands `sinkRel` of this crown's height above its top sinks it fully (less
   * the farther it is). `shade`: a neighbour toward the sun, within `sunReach` crown radii, whose
   * shadow under the scene's sun covers the lower half; its shade eases out as it stands off the sun's
   * line from `sideFrom` of its own radius to its full radius. The shader takes `shadow` of the sun and
   * `dark` of the colour off the lower half of a fully deep crown: where the height on the unit shell
   * (before the radii, so a flat pad's top counts as its top) is under low[0], easing out by low[1].
   * Neighbours are looked up in a grid of `gridM` metres.
   */
  depth: {
    reach: number;
    sinkRel: number;
    sunReach: number;
    sideFrom: number;
    low: readonly [number, number];
    shadow: number;
    dark: number;
    gridM: number;
  };
  light: {
    /** Wrap lighting: (N.L + wrap) / (1 + wrap). */
    wrap: number;
    /** How far full sun takes the colour from the shade ramp to the lit one (times the plant's sun). */
    sun: number;
    /** Normal y over which lit faces turn from the palette's light colour to its sunlit one. */
    lit: readonly [number, number];
    /** Sun a plant in the low sun's terrain shadow still gets: the bake's key light stands higher and reaches it. */
    floor: number;
    /** Added to the sun direction's y before lighting, so crowns are lit from the key light's height. */
    lift: number;
    /** Brightness of the palette before the scene's grade. */
    gain: number;
  };
  /**
   * Sky ambient where the sun does not reach: the hue of `above` (cool violet-blue sky) on faces
   * turned up, of `below` (darker green ground bounce) on faces turned down, each at its gain.
   */
  ambient: { above: string; aboveGain: number; below: string; belowGain: number; amount: number };
  /** The underside keeps `under` of its brightness (from the centre direction's y range[0] to range[1]). */
  occlusion: { under: number; underRange: readonly [number, number] };
  /** Leaves lit from behind: colour x (view . sun)^power x (1 - facing)^rim x amount x the plant's sun. */
  translucency: { color: string; power: number; rim: number; amount: number };
  /**
   * Ragged silhouette: object-space noise cells of max(cellM, crown radius x cellRel) metres, and a
   * threshold that rises from 0 where 1 - |N.V| passes `from` to `max` at the very edge.
   */
  erosion: { cellM: number; cellRel: number; from: number; max: number };
  /** sRGB colours per tone (VEG_TONES): shade dark, shade mid, lit, sunlit. */
  palettes: Record<VegTone, readonly [string, string, string, string]>;
  /** Per crown: brightness +- value, and a warm-cool tilt +- hue. */
  vary: { value: number; hue: number };
  /** Leaves: two brightness fields with cells `fineM` and `coarseM` metres across take a leaf from `dark` to `bright` times the crown's colour. */
  leaves: { fineM: number; coarseM: number; dark: number; bright: number };
  /** Share of the scene's grade (look.ts sectGrade, then the near pines' shade) applied, as on the baked cards. */
  grade: number;
}

export const VEG_LOOK: VegLook = {
  detail: 1,
  seedQuantumM: 0.1,
  families: [
    ["pine.huangshan.", "huangshan"],
    // Ancient pines are gnarled flat-pad pines too (the bake has them as near meshes; a card one
    // would otherwise lose its tree when the cards hide).
    ["pine.ancient.", "huangshan"],
    ["pine.masson.", "masson"],
    ["pine.broadleaf.", "broadleaf"],
    ["shrub.", "shrub"],
    ["bamboo.", "bamboo"],
    ["blossom.", "blossom"],
  ],
  crown: {
    widthVary: [0.72, 1.12],
    cover: 0.6,
    shapes: {
      broadleaf: { width: 1, tall: 0.8, narrow: 0, taper: 0 },
      masson: { width: 0.85, tall: 0, narrow: 0.5, taper: 0.65 },
      shrub: { width: 1, tall: 0, narrow: 0, taper: 0 },
      bamboo: { width: 0.7, tall: 0, narrow: 0.45, taper: 0.4 },
      blossom: { width: 1, tall: 1, narrow: 0, taper: 0 },
    },
  },
  pads: { count: [3, 5], from: 0.45, thickness: 0.18, size: [0.62, 0.4], lean: [0.1, 0.35], jitter: 0.1, squash: [0.75, 0.95], yawJitter: 0.6 },
  displace: { amount: 0.27, scale: 2.2 },
  normal: { round: 0.35 },
  boughs: { cellM: [1.3, 3.4], maxRel: 0.5, bump: 0.45, crease: [0.25, 0.55], dark: 0.8, near: 0.35, px: [12, 36], fade: [0.35, 0.9] },
  depth: { reach: 1, sinkRel: 0.5, sunReach: 1, sideFrom: 0.5, low: [-0.2, 0.3], shadow: 0.6, dark: 0.2, gridM: 8 },
  // gain is round 57's 1.22. Round 58 kept it and matched its crease's mean to round 57's gaps instead. Now the
  // crease keeps 0.938 of the brightness on average (dark 0.8), against 0.910 for round 57's gaps: 1.031 times.
  // Depth at the forests' mean (0.6) keeps about 0.971 of a round crown's brightness seen from 10 to 70 degrees
  // above. Together 1.000, so a crown is as bright as in round 57 at the same gain (veg.test.ts checks both).
  light: { wrap: 0.5, sun: 1, lit: [0.15, 0.9], floor: 0.4, lift: 0.38, gain: 1.22 },
  ambient: { above: "#a8b2c4", aboveGain: 1.0, below: "#2f4a2a", belowGain: 0.6, amount: 0.25 },
  occlusion: { under: 0.55, underRange: [-0.75, 0.35] },
  translucency: { color: "#c8d060", power: 4, rim: 1.5, amount: 0.35 },
  erosion: { cellM: 0.45, cellRel: 0.08, from: 0.3, max: 0.85 },
  palettes: {
    // The scene's canopy (nature.py nature_canopy_mass).
    broadleaf: ["#1d3122", "#2c4630", "#4a6634", "#74894a"],
    // Bluer and darker: the pine pads' own (nature.py _mat_pine_pad).
    pine: ["#10241a", "#173326", "#244a35", "#76884a"],
    // nature.py nature_shrub.
    shrub: ["#1d3317", "#335226", "#4f7234", "#7d8f45"],
    // Mountain scrub: olive.
    scrub: ["#262d17", "#3b4524", "#5a6334", "#8f9045"],
    // Peach blossom: #b97a8c in shade, #f6b3c3 lit (look.ts petals).
    blossom: ["#8e5c6a", "#b97a8c", "#f6b3c3", "#ffdbe3"],
    // Yellow-green (nature.py nature_bamboo_leaf).
    bamboo: ["#27451c", "#3f6d2a", "#5f8a34", "#a3b65a"],
  },
  vary: { value: 0.24, hue: 0.09 },
  leaves: { fineM: 0.32, coarseM: 0.95, dark: 0.66, bright: 1.22 },
  grade: 1,
};

/** The archetype a family draws as, or null when no VEG_LOOK.families prefix matches (skipped). */
export function vegArchetype(family: string, look: VegLook = VEG_LOOK): VegArchetype | null {
  for (const [prefix, a] of look.families) if (family.startsWith(prefix)) return a;
  return null;
}

/** The colour set of a family drawn as `archetype`: pines share the pine tone, scrub shrubs are olive. */
export function vegTone(family: string, archetype: VegArchetype): VegTone {
  if (archetype === "huangshan" || archetype === "masson") return "pine";
  if (archetype === "shrub") return family.startsWith("shrub.scrub.") ? "scrub" : "shrub";
  return archetype;
}

// ---------------------------------------------------------------------------------------------
// The shell

/** A unit crown mesh: positions on the unit sphere (they are also the normals), outward winding. */
export interface ShellGeometry {
  positions: Float32Array;
  normals: Float32Array;
  indices: Uint16Array;
  triangles: number;
}

/**
 * The unit crown: detail 1 is an icosphere of subdivision 1 (42 vertices, 80 triangles), detail 0
 * an octahedron split once (18 vertices, 32 triangles). Deterministic.
 */
export function shellGeometry(detail: 0 | 1 = VEG_LOOK.detail): ShellGeometry {
  let verts: number[][];
  let faces: number[][];
  if (detail === 1) {
    const t = (1 + Math.sqrt(5)) / 2;
    verts = [
      [-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0],
      [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
      [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1],
    ];
    faces = [
      [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
      [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
      [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
      [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
    ];
  } else {
    verts = [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]];
    faces = [[0, 2, 4], [4, 2, 1], [1, 2, 5], [5, 2, 0], [0, 4, 3], [4, 1, 3], [1, 5, 3], [5, 0, 3]];
  }
  verts = verts.map(unit);
  // Split every triangle in four through its edges' midpoints (each midpoint made once).
  const mid = new Map<string, number>();
  const midpoint = (a: number, b: number): number => {
    const key = a < b ? `${a}_${b}` : `${b}_${a}`;
    const known = mid.get(key);
    if (known !== undefined) return known;
    const va = verts[a];
    const vb = verts[b];
    verts.push(unit([va[0] + vb[0], va[1] + vb[1], va[2] + vb[2]]));
    mid.set(key, verts.length - 1);
    return verts.length - 1;
  };
  const split: number[][] = [];
  for (const [a, b, c] of faces) {
    const ab = midpoint(a, b);
    const bc = midpoint(b, c);
    const ca = midpoint(c, a);
    split.push([a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]);
  }
  // Outward winding (counter-clockwise seen from outside), whatever order the tables gave.
  for (const tri of split) {
    const [a, b, c] = tri.map((i) => verts[i]);
    const n = cross(sub(b, a), sub(c, a));
    const centre = [a[0] + b[0] + c[0], a[1] + b[1] + c[1], a[2] + b[2] + c[2]];
    if (n[0] * centre[0] + n[1] * centre[1] + n[2] * centre[2] < 0) [tri[1], tri[2]] = [tri[2], tri[1]];
  }
  const positions = new Float32Array(verts.flat());
  return { positions, normals: new Float32Array(positions), indices: new Uint16Array(split.flat()), triangles: split.length };
}

function unit(v: number[]): number[] {
  const l = Math.hypot(v[0], v[1], v[2]);
  return [v[0] / l, v[1] / l, v[2] / l];
}

function sub(a: number[], b: number[]): number[] {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function cross(a: number[], b: number[]): number[] {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}

// ---------------------------------------------------------------------------------------------
// Seeds

function mix32(h: number): number {
  h ^= h >>> 16;
  h = Math.imul(h, 0x7feb352d);
  h ^= h >>> 15;
  h = Math.imul(h, 0x846ca68b);
  h ^= h >>> 16;
  return h >>> 0;
}

/** A plant's seed (0..1) from its position rounded to `quantumM`: the same plant gets the same seed every export. */
export function vegSeed(x: number, y: number, z: number, quantumM = VEG_LOOK.seedQuantumM): number {
  let h = mix32(Math.round(x / quantumM) | 0);
  h = mix32((h + Math.imul(Math.round(y / quantumM) | 0, 0x9e3779b1)) >>> 0);
  h = mix32((h + Math.imul(Math.round(z / quantumM) | 0, 0x85ebca6b)) >>> 0);
  return h / 4294967296;
}

/** The k-th random number (0..1) of a seed. */
export function seedRandom(seed: number, k: number): number {
  return mix32((Math.floor(seed * 4294967296) ^ Math.imul(k + 1, 0x27d4eb2f)) >>> 0) / 4294967296;
}

// ---------------------------------------------------------------------------------------------
// Instances

/** Floats per instance in each attribute. */
export const SHELL_STRIDE = { center: 3, shape: 4, params: 4, depth: 1 } as const;

/**
 * Shell instances, packed for instanced attributes:
 * - center: the crown's centre (world), 3 per instance;
 * - shape: half-extents rx, ry, rz (m, before the yaw) and the taper, 4 per instance;
 * - params: yaw (radians), seed (0..1), sun (0..1) and tone (VEG_TONES index), 4 per instance;
 * - depth: how deep the crown sits among its neighbours (vegDepth, 0..1), 1 per instance.
 */
export interface ShellInstances {
  count: number;
  center: Float32Array;
  shape: Float32Array;
  params: Float32Array;
  depth: Float32Array;
  /** Instances per archetype (a huangshan pine's pads count one each), and plants per archetype. */
  byArchetype: Record<VegArchetype, number>;
  plantsByArchetype: Record<VegArchetype, number>;
  /** Card plants turned into shells, and card plants in the file (mesh flag 0). */
  plants: number;
  cards: number;
  /** Card plants left out: click targets (their cards stay), families with no archetype, and bad sizes. */
  skipped: { hotspot: number; invalid: number; families: Record<string, number> };
  /** A sphere round every instance (with its lumps), or null with no instances. */
  bounds: { center: Vec3; radius: number; min: Vec3; max: Vec3 } | null;
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function zeroCounts(): Record<VegArchetype, number> {
  return Object.fromEntries(VEG_ARCHETYPES.map((a) => [a, 0])) as Record<VegArchetype, number>;
}

/** Pads a huangshan pine of this seed carries. */
export function padCount(seed: number, look: VegLook = VEG_LOOK): number {
  const [lo, hi] = look.pads.count;
  return lo + Math.min(Math.floor(seedRandom(seed, 0) * (hi - lo + 1)), hi - lo);
}

interface Crown {
  dx: number;
  cy: number;
  dz: number;
  rx: number;
  ry: number;
  rz: number;
  taper: number;
  yaw: number;
}

/** The crowns of one plant, relative to its foot. */
export function plantCrowns(archetype: VegArchetype, height: number, radius: number, yaw: number, seed: number, look: VegLook = VEG_LOOK): Crown[] {
  const H = height;
  const R = radius;
  if (archetype !== "huangshan") {
    const s = look.crown.shapes[archetype];
    // No two crowns the same width: a forest of equal balls reads as cobbles.
    let rx = R * s.width * lerp(look.crown.widthVary[0], look.crown.widthVary[1], seedRandom(seed, 3));
    let ry = archetype === "shrub" ? H / 2 : (look.crown.cover * H) / 2;
    if (s.tall > 0) ry = Math.min(ry, rx * s.tall);
    if (s.narrow > 0) rx = Math.min(rx, ry * s.narrow);
    const rz = rx * lerp(0.8, 1, seedRandom(seed, 1));
    return [{ dx: 0, cy: archetype === "shrub" ? H / 2 : H - ry, dz: 0, rx, ry, rz, taper: s.taper, yaw }];
  }
  const P = look.pads;
  const n = padCount(seed, look);
  const leanAng = seedRandom(seed, 1) * Math.PI * 2;
  const lean = lerp(P.lean[0], P.lean[1], seedRandom(seed, 2)) * R;
  const out: Crown[] = [];
  const topRx = R * P.size[1];
  const topRy = topRx * P.thickness;
  for (let k = 0; k < n; k++) {
    const t = n > 1 ? k / (n - 1) : 1;
    // Largest lowest, along a leaning trunk.
    const rx = Math.min(R * lerp(P.size[0], P.size[1], t), R);
    const ry = rx * P.thickness;
    let cy = lerp(P.from * H, H - topRy, t);
    cy = Math.min(Math.max(cy, ry), H - ry);
    const ja = seedRandom(seed, 10 + k * 4) * Math.PI * 2;
    const jr = seedRandom(seed, 11 + k * 4) * P.jitter * R;
    let dx = Math.cos(leanAng) * lean * t + Math.cos(ja) * jr;
    let dz = Math.sin(leanAng) * lean * t + Math.sin(ja) * jr;
    // Inside the tree's box: the pad's reach from the trunk is at most the tree's radius.
    const off = Math.hypot(dx, dz);
    if (off + rx > R) {
      const k2 = off > 1e-9 ? Math.max(R - rx, 0) / off : 0;
      dx *= k2;
      dz *= k2;
    }
    const rz = rx * lerp(P.squash[0], P.squash[1], seedRandom(seed, 12 + k * 4));
    const py = yaw + (seedRandom(seed, 13 + k * 4) - 0.5) * 2 * P.yawJitter;
    out.push({ dx, cy, dz, rx, ry, rz, taper: 0, yaw: py });
  }
  return out;
}

export interface ShellOptions {
  look?: VegLook;
  /** Direction toward the scene's sun (meta.json), for the shade part of vegDepth; none: no shade part. */
  sun?: Vec3;
}

/**
 * Every card plant (mesh flag 0) of a chunk as shell instances. Broadleaf, shrub, blossom, masson and
 * bamboo give one crown each, its top at the foot + height, covering the upper `crown.cover` of the
 * height (shrubs: all of it, on the ground); huangshan pines give 3 to 5 flat pads. Click targets keep
 * their cards (skipped here), and so do families with no archetype. Each crown's depth among the
 * others comes from vegDepth.
 */
export function shellInstances(veg: VegData, families: readonly string[], opts: ShellOptions = {}): ShellInstances {
  const look = opts.look ?? VEG_LOOK;
  const arch = families.map((name) => vegArchetype(name, look));
  const tone = families.map((name, i) => {
    const a = arch[i];
    return a ? VEG_TONES.indexOf(vegTone(name, a)) : 0;
  });
  const byArchetype = zeroCounts();
  const plantsByArchetype = zeroCounts();
  const skipped = { hotspot: 0, invalid: 0, families: {} as Record<string, number> };
  let cards = 0;
  const take: number[] = [];
  for (let i = 0; i < veg.count; i++) {
    if (veg.flags[i] & VEG_FLAG.mesh) continue;
    cards++;
    if (veg.flags[i] & VEG_FLAG.hotspot) {
      skipped.hotspot++;
      continue;
    }
    const a = arch[veg.family[i]] ?? null;
    if (!a) {
      const name = families[veg.family[i]] ?? `#${veg.family[i]}`;
      skipped.families[name] = (skipped.families[name] ?? 0) + 1;
      continue;
    }
    const h = veg.height[i];
    const r = veg.radius[i];
    if (!(h > 0 && r > 0 && Number.isFinite(h) && Number.isFinite(r))) {
      skipped.invalid++;
      continue;
    }
    take.push(i);
  }
  const crowns: { i: number; a: VegArchetype; seed: number; list: Crown[] }[] = [];
  let count = 0;
  for (const i of take) {
    const a = arch[veg.family[i]] as VegArchetype;
    const seed = vegSeed(veg.pos[i * 3], veg.pos[i * 3 + 1], veg.pos[i * 3 + 2], look.seedQuantumM);
    const list = plantCrowns(a, veg.height[i], veg.radius[i], vegYaw(veg.yaw[i]), seed, look);
    crowns.push({ i, a, seed, list });
    count += list.length;
  }
  const center = new Float32Array(count * SHELL_STRIDE.center);
  const shape = new Float32Array(count * SHELL_STRIDE.shape);
  const params = new Float32Array(count * SHELL_STRIDE.params);
  const min: Vec3 = [Infinity, Infinity, Infinity];
  const max: Vec3 = [-Infinity, -Infinity, -Infinity];
  const reach = new Float32Array(count);
  const grow = 1 + look.displace.amount;
  let n = 0;
  for (const { i, a, seed, list } of crowns) {
    plantsByArchetype[a]++;
    const x = veg.pos[i * 3];
    const y = veg.pos[i * 3 + 1];
    const z = veg.pos[i * 3 + 2];
    for (let k = 0; k < list.length; k++) {
      const c = list[k];
      const cx = x + c.dx;
      const cy = y + c.cy;
      const cz = z + c.dz;
      center.set([cx, cy, cz], n * 3);
      shape.set([c.rx, c.ry, c.rz, c.taper], n * 4);
      // Each pad its own seed (its lumps and clumps), all from the plant's.
      params.set([c.yaw, k === 0 ? seed : seedRandom(seed, 100 + k), veg.sun[i] / 255, tone[veg.family[i]]], n * 4);
      const e = Math.max(c.rx, c.ry, c.rz) * grow;
      reach[n] = e;
      min[0] = Math.min(min[0], cx - e);
      min[1] = Math.min(min[1], cy - e);
      min[2] = Math.min(min[2], cz - e);
      max[0] = Math.max(max[0], cx + e);
      max[1] = Math.max(max[1], cy + e);
      max[2] = Math.max(max[2], cz + e);
      byArchetype[a]++;
      n++;
    }
  }
  let bounds: ShellInstances["bounds"] = null;
  if (count > 0) {
    const c: Vec3 = [(min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2];
    let radius = 0;
    for (let j = 0; j < count; j++) {
      const d = Math.hypot(center[j * 3] - c[0], center[j * 3 + 1] - c[1], center[j * 3 + 2] - c[2]) + reach[j];
      if (d > radius) radius = d;
    }
    bounds = { center: c, radius, min, max };
  }
  const depth = vegDepth(center, shape, count, opts.sun ?? null, look);
  return { count, center, shape, params, depth, byArchetype, plantsByArchetype, plants: crowns.length, cards, skipped, bounds };
}

// ---------------------------------------------------------------------------------------------
// Depth among crowns

/** A crown as vegDepth sees it: its centre, half height and horizontal radius (m). */
export interface DepthCrown {
  x: number;
  y: number;
  z: number;
  ry: number;
  rh: number;
}

/** The sun as vegDepth uses it: its level direction (unit x, z) and the rise per level metre. */
export interface DepthSun {
  dx: number;
  dz: number;
  rise: number;
}

/** The level direction and slope of a direction toward the sun, or null when it is at or under the horizon. */
export function depthSun(sun: Vec3 | null): DepthSun | null {
  if (!sun) return null;
  const l = Math.hypot(sun[0], sun[2]);
  if (!(sun[1] > 0) || !(l > 1e-6)) return null;
  return { dx: sun[0] / l, dz: sun[2] / l, rise: sun[1] / l };
}

function smooth01(a: number, b: number, x: number): number {
  const t = Math.min(Math.max((x - a) / (b - a), 0), 1);
  return t * t * (3 - 2 * t);
}

/**
 * What neighbour `b` does to crown `a`. sink: how far b's top stands over a's (a share of `sinkRel` of a's
 * height, 0..1), less the farther b is, nothing past `reach` of a's radius. shade: how much of a's lower
 * half b's shadow covers when b stands toward the sun within `sunReach` of a's radius (0..1), less as b
 * stands off the sun's line through a.
 */
export function depthTerms(a: DepthCrown, b: DepthCrown, sun: DepthSun | null, look: VegLook = VEG_LOOK): { sink: number; shade: number } {
  const D = look.depth;
  const ox = b.x - a.x;
  const oz = b.z - a.z;
  const d = Math.hypot(ox, oz);
  let sink = 0;
  const near = D.reach * a.rh;
  if (d < near) sink = Math.min(Math.max((b.y + b.ry - (a.y + a.ry)) / (D.sinkRel * 2 * a.ry), 0), 1) * (1 - d / near);
  let shade = 0;
  if (sun) {
    const along = ox * sun.dx + oz * sun.dz;
    if (along > 0 && along <= D.sunReach * a.rh) {
      const off = Math.abs(ox * sun.dz - oz * sun.dx);
      const wide = 1 - smooth01(D.sideFrom * b.rh, b.rh, off);
      // b's crown, lowered by the sun's slope over the distance, against a's lower half.
      const drop = along * sun.rise;
      const cover = Math.min(b.y + b.ry - drop, a.y) - Math.max(b.y - b.ry - drop, a.y - a.ry);
      shade = wide * Math.min(Math.max(cover / a.ry, 0), 1);
    }
  }
  return { sink, shade };
}

/**
 * Per crown, how deep it sits among the others (0..1): 1 - (1 - sink)(1 - shade), each the largest any
 * neighbour gives (depthTerms). Neighbours come from a level grid of depth.gridM; the order of the crowns
 * does not matter. `center` and `shape` are packed as in ShellInstances. A shading neighbour can stand up
 * to sunReach of this crown's radius along the sun and its own radius off the sun's line, so the search
 * reaches past both for the largest crown in the list.
 */
export function vegDepth(center: Float32Array, shape: Float32Array, count: number, sun: Vec3 | null, look: VegLook = VEG_LOOK): Float32Array {
  const out = new Float32Array(count);
  if (count === 0) return out;
  const D = look.depth;
  const ray = depthSun(sun);
  const crowns: DepthCrown[] = new Array(count);
  const grid = new Map<number, number[]>();
  const G = D.gridM;
  const key = (ix: number, iz: number) => ix * 1_000_003 + iz;
  let maxRh = 0;
  for (let i = 0; i < count; i++) {
    const c: DepthCrown = { x: center[i * 3], y: center[i * 3 + 1], z: center[i * 3 + 2], ry: shape[i * 4 + 1], rh: Math.max(shape[i * 4], shape[i * 4 + 2]) };
    crowns[i] = c;
    if (c.rh > maxRh) maxRh = c.rh;
    const k = key(Math.floor(c.x / G), Math.floor(c.z / G));
    const list = grid.get(k);
    if (list) list.push(i);
    else grid.set(k, [i]);
  }
  for (let i = 0; i < count; i++) {
    const a = crowns[i];
    if (!(a.ry > 0 && a.rh > 0)) continue;
    // Sink: within reach of a's radius. Shade: up to sunReach of a's radius along the sun and b's radius off it.
    const q = ray ? Math.max(D.reach * a.rh, Math.hypot(D.sunReach * a.rh, maxRh)) : D.reach * a.rh;
    let sink = 0;
    let shade = 0;
    for (let ix = Math.floor((a.x - q) / G); ix <= Math.floor((a.x + q) / G); ix++) {
      for (let iz = Math.floor((a.z - q) / G); iz <= Math.floor((a.z + q) / G); iz++) {
        const list = grid.get(key(ix, iz));
        if (!list) continue;
        for (const j of list) {
          if (j === i) continue;
          const t = depthTerms(a, crowns[j], ray, look);
          if (t.sink > sink) sink = t.sink;
          if (t.shade > shade) shade = t.shade;
        }
      }
    }
    out[i] = 1 - (1 - sink) * (1 - shade);
  }
  return out;
}

// ---------------------------------------------------------------------------------------------
// Switches

/** `?veg=` on the page's URL: "0" / "off" forces the baked cards, "1" / "on" forces the shells on any tier. */
export type VegSwitch = "on" | "off" | null;

export function parseVegParam(search: string): VegSwitch {
  const m = /[?&]veg=([a-z0-9]+)/.exec(search);
  if (!m) return null;
  if (m[1] === "0" || m[1] === "off") return "off";
  if (m[1] === "1" || m[1] === "on") return "on";
  return null;
}

/**
 * Shells at a quality: the tier's own (Quality.vegShells, High only) unless ?veg= forces them on or
 * off. Never while the ladder has the tree cards off (noCards): the shells stand in for the cards.
 */
export function vegShellsOn(q: Quality, sw: VegSwitch): boolean {
  if (q.noCards) return false;
  if (sw !== null) return sw === "on";
  return q.vegShells === true;
}

// ---------------------------------------------------------------------------------------------
// GLSL

/** GLSL: `float sectVegHash( vec3 p )` and `float sectVegNoise( vec3 x )`, a smooth 3D value noise (0..1). */
export function vegNoiseGlsl(): string {
  return /* glsl */ `
float sectVegHash( vec3 p ) {
  p = fract( p * 0.3183099 + 0.1 );
  p *= 17.0;
  return fract( p.x * p.y * p.z * ( p.x + p.y + p.z ) );
}
float sectVegNoise( vec3 x ) {
  vec3 i = floor( x );
  vec3 u = fract( x );
  u = u * u * ( 3.0 - 2.0 * u );
  return mix(
    mix( mix( sectVegHash( i ), sectVegHash( i + vec3( 1.0, 0.0, 0.0 ) ), u.x ),
      mix( sectVegHash( i + vec3( 0.0, 1.0, 0.0 ) ), sectVegHash( i + vec3( 1.0, 1.0, 0.0 ) ), u.x ), u.y ),
    mix( mix( sectVegHash( i + vec3( 0.0, 0.0, 1.0 ) ), sectVegHash( i + vec3( 1.0, 0.0, 1.0 ) ), u.x ),
      mix( sectVegHash( i + vec3( 0.0, 1.0, 1.0 ) ), sectVegHash( i + vec3( 1.0, 1.0, 1.0 ) ), u.x ), u.y ),
    u.z );
}
`;
}

function fract(x: number): number {
  return x - Math.floor(x);
}

function vegHash(x: number, y: number, z: number): number {
  const px = fract(x * 0.3183099 + 0.1) * 17;
  const py = fract(y * 0.3183099 + 0.1) * 17;
  const pz = fract(z * 0.3183099 + 0.1) * 17;
  return fract(px * py * pz * (px + py + pz));
}

/** TypeScript mirror of sectVegNoise (in double precision), for tests. */
export function vegNoise(x: number, y: number, z: number): number {
  const ix = Math.floor(x);
  const iy = Math.floor(y);
  const iz = Math.floor(z);
  const s = (t: number) => t * t * (3 - 2 * t);
  const ux = s(x - ix);
  const uy = s(y - iy);
  const uz = s(z - iz);
  const h = (a: number, b: number, c: number) => vegHash(ix + a, iy + b, iz + c);
  const m = lerp;
  return m(m(m(h(0, 0, 0), h(1, 0, 0), ux), m(h(0, 1, 0), h(1, 1, 0), ux), uy), m(m(h(0, 0, 1), h(1, 0, 1), ux), m(h(0, 1, 1), h(1, 1, 1), ux), uy), uz);
}

/**
 * GLSL: `vec4 sectVegNoiseD( vec3 x )`, sectVegNoise and its gradient: (value, d/dx, d/dy, d/dz). Same
 * corners and the same smooth step, so the value is sectVegNoise's. Needs sectVegHash (vegNoiseGlsl).
 */
export function vegNoiseDGlsl(): string {
  return /* glsl */ `
vec4 sectVegNoiseD( vec3 x ) {
  vec3 i = floor( x );
  vec3 w = fract( x );
  vec3 u = w * w * ( 3.0 - 2.0 * w );
  vec3 du = 6.0 * w * ( 1.0 - w );
  float a = sectVegHash( i );
  float b = sectVegHash( i + vec3( 1.0, 0.0, 0.0 ) );
  float c = sectVegHash( i + vec3( 0.0, 1.0, 0.0 ) );
  float d = sectVegHash( i + vec3( 1.0, 1.0, 0.0 ) );
  float e = sectVegHash( i + vec3( 0.0, 0.0, 1.0 ) );
  float f = sectVegHash( i + vec3( 1.0, 0.0, 1.0 ) );
  float g = sectVegHash( i + vec3( 0.0, 1.0, 1.0 ) );
  float h = sectVegHash( i + vec3( 1.0, 1.0, 1.0 ) );
  float k1 = b - a;
  float k2 = c - a;
  float k3 = e - a;
  float k4 = a - b - c + d;
  float k5 = a - c - e + g;
  float k6 = a - b - e + f;
  float k7 = - a + b + c - d + e - f - g + h;
  return vec4(
    a + k1 * u.x + k2 * u.y + k3 * u.z + k4 * u.x * u.y + k5 * u.y * u.z + k6 * u.z * u.x + k7 * u.x * u.y * u.z,
    du * vec3(
      k1 + k4 * u.y + k6 * u.z + k7 * u.y * u.z,
      k2 + k5 * u.z + k4 * u.x + k7 * u.z * u.x,
      k3 + k6 * u.x + k5 * u.y + k7 * u.x * u.y ) );
}
`;
}

/** TypeScript mirror of sectVegNoiseD: [value, d/dx, d/dy, d/dz]. */
export function vegNoiseD(x: number, y: number, z: number): [number, number, number, number] {
  const ix = Math.floor(x);
  const iy = Math.floor(y);
  const iz = Math.floor(z);
  const wx = x - ix;
  const wy = y - iy;
  const wz = z - iz;
  const ux = wx * wx * (3 - 2 * wx);
  const uy = wy * wy * (3 - 2 * wy);
  const uz = wz * wz * (3 - 2 * wz);
  const h = (a: number, b: number, c: number) => vegHash(ix + a, iy + b, iz + c);
  const a = h(0, 0, 0);
  const b = h(1, 0, 0);
  const c = h(0, 1, 0);
  const d = h(1, 1, 0);
  const e = h(0, 0, 1);
  const f = h(1, 0, 1);
  const g = h(0, 1, 1);
  const k1 = b - a;
  const k2 = c - a;
  const k3 = e - a;
  const k4 = a - b - c + d;
  const k5 = a - c - e + g;
  const k6 = a - b - e + f;
  const k7 = -a + b + c - d + e - f - g + h(1, 1, 1);
  return [
    a + k1 * ux + k2 * uy + k3 * uz + k4 * ux * uy + k5 * uy * uz + k6 * uz * ux + k7 * ux * uy * uz,
    6 * wx * (1 - wx) * (k1 + k4 * uy + k6 * uz + k7 * uy * uz),
    6 * wy * (1 - wy) * (k2 + k5 * uz + k4 * ux + k7 * uz * ux),
    6 * wz * (1 - wz) * (k3 + k6 * ux + k5 * uy + k7 * ux * uy),
  ];
}

/**
 * The boughs' lattice, turned off the crown's axes (rows; orthonormal, determinant 1): no lattice plane is
 * level, so value noise's blobs do not line up in rings round the dome.
 */
export const VEG_BOUGH_TURN: readonly (readonly [number, number, number])[] = [
  [0, 0.8, 0.6],
  [-0.8, 0.36, -0.48],
  [-0.6, -0.48, 0.64],
];

/** GLSL: `const mat3 SECT_VEG_TURN`, so SECT_VEG_TURN * p is VEG_BOUGH_TURN p and g * SECT_VEG_TURN turns a gradient back. */
export function vegTurnGlsl(): string {
  const R = VEG_BOUGH_TURN;
  // GLSL fills a mat3 column by column.
  const cols = [0, 1, 2].flatMap((c) => [0, 1, 2].map((r) => f(R[r][c])));
  return `const mat3 SECT_VEG_TURN = mat3( ${cols.join(", ")} );`;
}

/**
 * The bough field at a point of a crown (m, in its own frame) with cells of `cellM`: [value, gradient per
 * metre]. The noise of VEG_BOUGH_TURN p / cellM, its gradient turned back by the transpose. The shader
 * leans its normal by the gradient per cell instead (this at cellM 1, at p / cellM), so the tilt does not
 * change with the bough size.
 */
export function vegBough(x: number, y: number, z: number, cellM: number): [number, number, number, number] {
  const R = VEG_BOUGH_TURN;
  const q = R.map((r) => (r[0] * x + r[1] * y + r[2] * z) / cellM);
  const [v, gx, gy, gz] = vegNoiseD(q[0], q[1], q[2]);
  return [
    v,
    (R[0][0] * gx + R[1][0] * gy + R[2][0] * gz) / cellM,
    (R[0][1] * gx + R[1][1] * gy + R[2][1] * gz) / cellM,
    (R[0][2] * gx + R[1][2] * gy + R[2][2] * gz) / cellM,
  ];
}

/**
 * Points spread over many bough cells (a fixed sequence), for the statistics of the bough field. They are
 * a few cells apart, so neighbours in the list are near independent.
 */
export function vegFieldSamples(n: number): Vec3[] {
  const out: Vec3[] = [];
  for (let k = 0; k < n; k++) out.push([fract(k * 0.7548777) * 400 - 200, fract(k * 0.5698403) * 400 - 200, fract(k * 0.618034) * 400 - 200]);
  return out;
}

/** How far from a crease toward a bough a point is where the bough field reads `field` (0 in a crease, 1 on a bough). */
export function vegCreaseShare(field: number, look: VegLook = VEG_LOOK): number {
  return smooth01(look.boughs.crease[0], look.boughs.crease[1], field);
}

/**
 * How much of its brightness a point keeps for the creases: 1 - (1 - dark)(1 - mix(meanS, s, k)). s is
 * vegCreaseShare there, k the boughs' strength (1 at full, 0 where they have faded flat), meanS the mean
 * of s over the field (vegBoughMeans) and dark the brightness at the deepest crease (uVegBough.y). The
 * mix is linear in s, so over the field the mean is 1 - (1 - dark)(1 - meanS) at every k: a crown's
 * brightness does not move as its boughs fade or ease off.
 */
export function vegCrease(s: number, k: number, meanS: number, dark: number = VEG_LOOK.boughs.dark): number {
  return 1 - (1 - dark) * (1 - lerp(meanS, s, k));
}

/**
 * Means over the bough field. creaseShare: the mean of vegCreaseShare, the build-time constant the
 * shader's crease eases to (vegCrease).
 */
export function vegBoughMeans(look: VegLook = VEG_LOOK, samples = 20000): { creaseShare: number } {
  let s = 0;
  for (const [x, y, z] of vegFieldSamples(samples)) s += vegCreaseShare(vegBough(x, y, z, 1)[0], look);
  return { creaseShare: s / samples };
}

/**
 * The share of the boughs' lean and crease kept for a cell `cellPx` pixels across on screen: all of it
 * up to boughs.px[0], `near` from boughs.px[1] on. Relief that crisp, that large on screen, reads as
 * crumpled foil or clay.
 */
export function vegBoughNear(cellPx: number, near: number = VEG_LOOK.boughs.near, look: VegLook = VEG_LOOK): number {
  return lerp(1, near, smooth01(look.boughs.px[0], look.boughs.px[1], cellPx));
}

/** The shared uniform uVegBough's defaults: the slope lean, the deepest crease's brightness, the share kept large on screen, 0. */
export function vegBoughUniform(look: VegLook = VEG_LOOK): [number, number, number, number] {
  return [look.boughs.bump, look.boughs.dark, look.boughs.near, 0];
}

/** The palettes as linear colours, tone by tone (4 a tone), for the shader's table. */
export function vegPaletteLinear(look: VegLook = VEG_LOOK): Vec3[] {
  return VEG_TONES.flatMap((t) => look.palettes[t].map((hex) => hexToLinear(hex)));
}

const SHELL_VARYINGS = /* glsl */ `
varying vec3 vVegWorld;
varying vec3 vVegShellN;
varying vec3 vVegLocal;
varying vec3 vVegCenter;
// The point on the unit shell, before the radii and the lumps: its y is the height on the crown, a flat pad's too.
varying vec3 vVegUnit;
// The plant's sun, the bough cells' size (m), the crown's depth among the others (0..1), its yaw.
varying vec4 vVegInfo;
// The erosion cells' size (m).
varying float vVegEdgeM;
varying vec3 vVegDark;
varying vec3 vVegMid;
varying vec3 vVegLight;
varying vec3 vVegLit;
`;

/**
 * The vertex stage: the unit shell (position, also its normal) placed by the instance attributes
 * iCenter, iShape (rx, ry, rz, taper), iParams (yaw, seed, sun, tone) and iDepth (vegDepth), each
 * vertex moved along its normal by a low 3D value noise of where it sits on the shell and the seed, so
 * every crown is lumpy and different. The crown's colours come from the tone's palette with its own
 * brightness and tilt.
 */
export function vegVertexGlsl(look: VegLook = VEG_LOOK): string {
  const pal = vegPaletteLinear(look);
  const D = look.displace;
  const B = look.boughs;
  const E = look.erosion;
  return /* glsl */ `
uniform vec2 uVegNear;
attribute vec3 iCenter;
attribute vec4 iShape;
attribute vec4 iParams;
attribute float iDepth;
${SHELL_VARYINGS}
#include <common>
#include <fog_pars_vertex>
${vegNoiseGlsl()}
const vec3 SECT_VEG_PALETTE[ ${pal.length} ] = vec3[ ${pal.length} ](
  ${pal.map((c) => glslVec3(c)).join(",\n  ")}
);
// Rotation about +y: local +x turns toward -z as the yaw grows.
vec3 sectVegYaw( vec3 v, float a ) {
  float c = cos( a );
  float s = sin( a );
  return vec3( v.x * c + v.z * s, v.y, - v.x * s + v.z * c );
}
void main() {
  float seed = iParams.y;
  vec3 so = vec3( seed * 61.7, seed * 23.3, seed * 47.9 );
  vec3 n0 = normalize( position );
  // Lumps: +- ${f(D.amount)} of the radius along the normal.
  float lump = ( sectVegNoise( n0 * ${f(D.scale)} + so ) - 0.5 ) * 2.0 * ${f(D.amount)};
  vec3 r = iShape.xyz;
  // A spire's top narrows (iShape.w = 0: round).
  float narrow = 1.0 - iShape.w * smoothstep( -0.2, 1.0, n0.y );
  vec3 shellP = n0 * ( 1.0 + lump ) * r * vec3( narrow, 1.0, narrow );
  vec4 worldP = modelMatrix * vec4( iCenter + sectVegYaw( shellP, iParams.x ), 1.0 );
  vVegWorld = worldP.xyz;
  vVegCenter = ( modelMatrix * vec4( iCenter, 1.0 ) ).xyz;
  // The ellipsoid's normal (the lumps leave it be; the fragment stage breaks it up).
  vVegShellN = normalize( mat3( modelMatrix ) * sectVegYaw( n0 / r, iParams.x ) );
  vVegLocal = shellP + so;
  vVegUnit = n0;
  float rMax = max( r.x, max( r.y, r.z ) );
  float h1 = sectVegHash( vec3( seed * 113.0, 1.7, 3.1 ) );
  float h2 = sectVegHash( vec3( seed * 97.0, 5.3, 0.7 ) );
  float h3 = sectVegHash( vec3( seed * 71.0, 2.9, 8.3 ) );
  // Bough cells: seeded per crown, never more than ${f(B.maxRel)} of the crown's radius (a shrub keeps a few boughs).
  float boughM = min( mix( ${f(B.cellM[0])}, ${f(B.cellM[1])}, h1 ), rMax * ${f(B.maxRel)} );
  vVegInfo = vec4( iParams.z, boughM, iDepth, iParams.x );
  vVegEdgeM = max( ${f(E.cellM)}, rMax * ${f(E.cellRel)} );
  // This crown's own brightness and warm-cool tilt.
  float tilt = ( h3 - 0.5 ) * 2.0 * ${f(look.vary.hue)};
  vec3 k = ( 1.0 + ( h2 - 0.5 ) * 2.0 * ${f(look.vary.value)} ) * vec3( 1.0 + tilt, 1.0, 1.0 - tilt );
  int tone = clamp( int( iParams.w + 0.5 ), 0, ${VEG_TONES.length - 1} ) * 4;
  vVegDark = SECT_VEG_PALETTE[ tone ] * k;
  vVegMid = SECT_VEG_PALETTE[ tone + 1 ] * k;
  vVegLight = SECT_VEG_PALETTE[ tone + 2 ] * k;
  vVegLit = SECT_VEG_PALETTE[ tone + 3 ] * k;
  vec4 mvPosition = viewMatrix * worldP;
  gl_Position = projectionMatrix * mvPosition;
  // Near the camera the baked card draws this tree (it has the detail); the shell takes over past its ground
  // cell's switch distance. The same cell and hash as the card's cut, so one of the two always draws.
  if ( uVegNear.y > 0.0 ) {
${farCutCellGlsl("vVegCenter", "uVegNear")}
    if ( ! sectCellFar ) gl_Position = vec4( 2.0, 2.0, 2.0, 1.0 );
  }
  #include <fog_vertex>
}
`;
}

/**
 * The fragment stage. The silhouette is eroded first: near grazing angles (|N.V| small) fragments
 * whose object-space noise is under a threshold that rises toward the edge are cut (with alpha to
 * coverage on a multisampled buffer, a smooth cut). Boughs change the light only: a value noise of
 * 1.3-3.4 m cells on a turned lattice (sectVegNoiseD, its value and slope). The normal is the shell's
 * blended with the direction from the crown's centre, then leant down the boughs' slope, so each bough
 * has a lit side and a shaded side, and the creases between boughs are darker. Their strength is the
 * shared uniform uVegBough: it fades flat when a cell nears a couple of pixels and eases off when a cell
 * is large on screen. Leaves are two finer fields that only change the brightness. Light: wrap sun times
 * the plant's sun value between the palette's shade and lit colours, a sky ambient tint where the sun
 * does not reach (cool from above, darker green from below), occlusion under the crown, in the creases
 * and on the lower half of a crown deep among others (vegDepth), and leaves glowing at the silhouette
 * toward the sun. No specular. Then the scene's grade, as on the baked cards, and the scene's haze
 * (three's fog chunks, which carry the page's height haze, valley mist and cloud layer, as on every
 * baked surface).
 */
export function vegFragmentGlsl(look: VegLook = VEG_LOOK): string {
  const L = look.light;
  const A = look.ambient;
  const O = look.occlusion;
  const T = look.translucency;
  const E = look.erosion;
  const B = look.boughs;
  const D = look.depth;
  const means = vegBoughMeans(look);
  const above = unitTint(A.above).map((v) => v * A.aboveGain) as Vec3;
  const below = unitTint(A.below).map((v) => v * A.belowGain) as Vec3;
  return /* glsl */ `
uniform vec3 uVegSun;
// The boughs' strength, one object shared by every chunk and tunable at run time (vegBoughUniform): how far
// the normal leans down their slope, the brightness at the deepest crease, the share of both kept when a
// cell is large on screen, unused.
uniform vec4 uVegBough;
${SHELL_VARYINGS}
#include <common>
#include <fog_pars_fragment>
${vegNoiseGlsl()}
${vegNoiseDGlsl()}
${gradeGlsl(SECT_LOOK.grade)}
${treeShadeGlsl(SECT_LOOK.trees.shade)}
${vegTurnGlsl()}
void main() {
  vec3 V = normalize( cameraPosition - vVegWorld );
  vec3 Ns = normalize( vVegShellN );
  float facing = abs( dot( Ns, V ) );
  // A pixel's size on the crown along its shorter side: it stays small at the rim, where the surface is seen edge
  // on. Taken before the cut below, so every pixel of a quad still has its neighbours for the derivatives.
  float pxIso = max( min( length( dFdx( vVegLocal ) ), length( dFdy( vVegLocal ) ) ), 1e-5 );
  // Ragged like leaves at the silhouette: object-space noise, so the edge holds still as the camera moves.
  vec3 qe = vVegLocal / vVegEdgeM;
  float en = sectVegNoise( qe ) * 0.65 + sectVegNoise( qe * 2.31 + vec3( 7.7, 3.1, 5.3 ) ) * 0.35;
  float thr = smoothstep( ${f(E.from)}, 1.0, 1.0 - facing ) * ${f(E.max)};
#ifdef ALPHA_TO_COVERAGE
  float alpha = clamp( ( en - thr ) / max( fwidth( en ), 1e-4 ) + 0.5, 0.0, 1.0 );
  if ( alpha <= 0.0 ) discard;
#else
  if ( en < thr ) discard;
  float alpha = 1.0;
#endif
  // Boughs: value noise on a turned lattice, with its slope, in the crown's own frame (it holds still as the camera
  // moves). They fade flat as a cell nears a couple of pixels, and ease off to uVegBough.z of their strength as a
  // cell grows large on screen, where crisp relief reads as crumpled foil or clay.
  vec4 bough = sectVegNoiseD( SECT_VEG_TURN * ( vVegLocal / vVegInfo.y ) );
  float boughFade = 1.0 - smoothstep( ${f(B.fade[0])} * vVegInfo.y, ${f(B.fade[1])} * vVegInfo.y, pxIso );
  float cellPx = vVegInfo.y / pxIso;
  float boughNear = mix( 1.0, uVegBough.z, smoothstep( ${f(B.px[0])}, ${f(B.px[1])}, cellPx ) );
  float boughK = boughFade * boughNear;
  // The normal: the shell's and the centre's direction, leant down the boughs' slope by uVegBough.x (turned back
  // off the lattice, then by the crown's yaw), so each bough has a lit side and a shaded side.
  vec3 Nc = normalize( vVegWorld - vVegCenter );
  vec3 N = normalize( mix( Ns, Nc, ${f(look.normal.round)} ) );
  vec3 slope = ( bough.yzw * SECT_VEG_TURN ) * boughK;
  float yawC = cos( vVegInfo.w );
  float yawS = sin( vVegInfo.w );
  slope = vec3( slope.x * yawC + slope.z * yawS, slope.y, - slope.x * yawS + slope.z * yawC );
  N = normalize( N - uVegBough.x * ( slope - dot( slope, N ) * N ) );
  // Leaves are two finer fields that only change the brightness, each faded out before its cells get smaller
  // than a couple of pixels (no shimmer in the distance).
  float pxM = length( fwidth( vVegLocal ) );
  float leafA = sectVegNoise( vVegLocal / ${f(look.leaves.fineM)} + vec3( 3.3, 9.1, 1.7 ) );
  float leafB = sectVegNoise( vVegLocal / ${f(look.leaves.coarseM)} + vec3( 11.9, 2.3, 7.1 ) );
  float fadeA = 1.0 - smoothstep( ${f(look.leaves.fineM * 0.35)}, ${f(look.leaves.fineM * 0.9)}, pxM );
  float fadeB = 1.0 - smoothstep( ${f(look.leaves.coarseM * 0.35)}, ${f(look.leaves.coarseM * 0.9)}, pxM );
  float leaf = mix( 0.5, smoothstep( 0.32, 0.68, leafA ), fadeA ) * 0.55 + mix( 0.5, smoothstep( 0.3, 0.7, leafB ), fadeB ) * 0.45;
  // Warm sun with wrap lighting, times the plant's own sun (0 in terrain shadow).
  // The bake's key light stands higher than the sun and reaches most crowns: a floor under the plant's own sun.
  vec3 key = normalize( uVegSun + vec3( 0.0, ${f(L.lift)}, 0.0 ) );
  float wrap = clamp( ( dot( N, key ) + ${f(L.wrap)} ) / ( 1.0 + ${f(L.wrap)} ), 0.0, 1.0 );
  // A crown sunk among taller ones, or shaded by one toward the sun, is deep (vegDepth): its lower half loses sun.
  // The lower half by the height on the unit shell, not the direction from the centre: on a flat pad that
  // direction is near level almost everywhere, and the pad's lit top would count as its lower half.
  float deep = vVegInfo.z * ( 1.0 - smoothstep( ${f(D.low[0])}, ${f(D.low[1])}, normalize( vVegUnit ).y ) );
  float sun = clamp( wrap * mix( ${f(L.floor)}, 1.0, vVegInfo.x ) * ${f(L.sun)} * ( 1.0 - deep * ${f(D.shadow)} ), 0.0, 1.0 );
  vec3 shade = mix( vVegDark, vVegMid, leaf );
  vec3 lit = mix( vVegLight, vVegLit, smoothstep( ${f(L.lit[0])}, ${f(L.lit[1])}, N.y ) );
  vec3 col = mix( shade, lit, sun );
  // Sky ambient where the sun does not reach: cool violet-blue from above, darker green from below.
  vec3 amb = mix( ${glslVec3(below)}, ${glslVec3(above)}, N.y * 0.5 + 0.5 );
  col *= mix( vec3( 1.0 ), amb, ${f(A.amount)} * ( 1.0 - sun ) );
  // Occlusion: the underside, the creases between boughs, and a deep crown's lower half. The crease (uVegBough.y at
  // the deepest) eases to the field's mean as the boughs weaken, so its mean brightness is the same at every strength.
  float under = smoothstep( ${f(O.underRange[0])}, ${f(O.underRange[1])}, Nc.y );
  float creaseS = smoothstep( ${f(B.crease[0])}, ${f(B.crease[1])}, bough.x );
  float crease = 1.0 - ( 1.0 - uVegBough.y ) * ( 1.0 - mix( ${f(means.creaseShare)}, creaseS, boughK ) );
  col *= mix( ${f(O.under)}, 1.0, under ) * crease * ( 1.0 - deep * ${f(D.dark)} ) * mix( ${f(look.leaves.dark)}, ${f(look.leaves.bright)}, leaf );
  // Leaves lit from behind glow at the silhouette when the view looks toward the sun.
  float toward = pow( max( dot( - V, uVegSun ), 0.0 ), ${f(T.power)} );
  col += ${glslVec3(hexToLinear(T.color))} * toward * pow( 1.0 - facing, ${f(T.rim)} ) * ${f(T.amount)} * vVegInfo.x;
  // The scene's grade, as the baked cards get it.
  col *= ${f(L.gain)};
  col = mix( col, sectTreeShade( sectGrade( col ), col ), ${f(look.grade)} );
  gl_FragColor = vec4( col, alpha );
  #include <colorspace_fragment>
  #include <fog_fragment>
}
`;
}
