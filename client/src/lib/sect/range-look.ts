/**
 * The range's own look on /sect (r47: phase A of the r45 background plan): colour, haze and mist
 * changes the page makes on the background around the eleven stops, never on the stops themselves.
 *
 * The owner (2026-10-24): "there is a lot of trunks, not enough greenery. In real life, people just
 * see green, they dont see the trunk". The r45 study measured 1-8 % of our land pixels in green to
 * blue hues against 65-96 % in photos of Zhangjiajie and Huangshan. Most of that gap was colour: the
 * grade takes all of green's lead away (look.ts greenTame 1), so pine pads came out olive-brown, the
 * cards' orange trunks were the brightest thing on a tree, and the haze was too thin to step the
 * ridges back. So, on the range only:
 * - foliage (far tree cards, near pines and their needle cards) keeps most of its green, capped
 *   short of lime, with a cooler, less violet shadow side (`foliage`);
 * - trunks on far cards turn to the canopy's shade colour (`trunks`);
 * - haze deepens per stop, with a clear zone round the camera (`haze`; lib/sect/glsl.ts applies it);
 * - sunlit rock is paler and greyer, with dark water streaks (`rock`);
 * - far lawns read as canopy (`ground`);
 * - mist puffs lie flatter and stretch along the wind, so they read as layers (`mist`).
 *
 * "The range" is everything farther than an area's footprint + `areas.pad` metres from its anchor
 * (meta.json areas), the change fading in over the next `areas.fade` metres. Halls, props, terraces
 * and the trees on them keep the look they had.
 *
 * Pure data, maths and GLSL strings (no three.js import), so it is testable.
 */
import { glslFloat, glslVec3 } from "./glsl";
import { gradeLinearWith, SECT_LOOK, unitTint, type SectLook } from "./look";
import type { CloudPuff, Hold, Vec3 } from "./types";

/** Most areas the shaders' list holds (meta.json has eleven); the rest of the slots stay empty. */
export const RANGE_MAX_AREAS = 16;

export const RANGE_LOOK = {
  areas: {
    /** Metres past an area's footprint where the range starts (the plan's "footprint + 30 m"). */
    pad: 30,
    /** Metres over which the range look fades in past that, so no seam shows on a slope. */
    fade: 25,
  },
  /**
   * Range foliage's grade (on top of SECT_LOOK.grade, which the stops keep):
   * - greenTame: share of green's lead removed (the stops' grade removes all of it, 1).
   * - satCap: saturation the graded colour is held under, measured on its square root (0.36 there
   *   is about 0.45 in sRGB on mid-dark greens): green, not lime.
   * - splitShadow, shadowTint: the shadow side's split tone (the grade's is 0.6 toward lavender
   *   #8b88c6; this is less of it, toward a neutral grey, so shaded crowns stay green, not violet).
   * - tint: leaf texels (green level with red or ahead, before the grade) turn `amount` of the way to
   *   `color`'s hue at `gain` x their own brightness: one canopy green (hue about 95 degrees) for the
   *   bake's olive-to-teal pads, a little lighter (the photos' canopy is value 0.2-0.3, ours 0.15).
   */
  foliage: {
    greenTame: 0.35,
    satCap: 0.36,
    splitShadow: 0.4,
    shadowTint: "#9a9aa8",
    tint: { color: "#4d6b35", amount: 0.7, gain: 2.0 },
  },
  /**
   * Far trunks: on bark texels (red-led and not pink, before the grade), past `near` metres and full
   * from `far`, the colour turns `amount` of the way to `color`'s hue at `value` x its own brightness
   * (a dark grey-green, like a trunk in its crown's shade). Cards start at 70 m (bake_trees CARD_CLEAR).
   */
  trunks: { near: 80, far: 150, amount: 0.9, value: 0.45, color: "#3a4a36" },
  /**
   * Haze per stop: the multiplier on meta.fog.density (0.0003 per metre at 100 m, thinning by e every
   * 220 m up) at each hold, blended smoothly by frame between holds. The high stops get more because
   * the height model thins their air (the first values aim at about 30 % fade 500 m out, level, at
   * the anchor's height). The haze leaves the first look.ts haze.clear metres clear.
   */
  haze: {
    holds: {
      gate: 1.6,
      mirror: 1.8,
      forge: 2.0,
      arena: 2.2,
      mission: 2.4,
      library: 2.7,
      steles: 3.0,
      scroll: 3.2,
      formation: 3.4,
      abode: 3.8,
      summit: 4.2,
    } as Record<string, number>,
    clear: 80,
  },
  /**
   * Range rock: the grade's colour turns `desat` of the way to a pale buff-grey (`color`'s hue at the
   * texel's own brightness), all of that in sun and `shade` of it in shadow (sun from graded
   * luminance lo to hi). Mossy rock (the bake's moss lines and drapes: olive or green before the
   * grade, detail.ts DETAIL_LOOK.greenRock's test) keeps its colour and more of its green (`moss.tame`
   * of green's lead removed), so the ledge lines read green. Streaks (mid and high tiers, with the far rock layer): dark vertical runs of
   * 3D noise `widthM` metres across and `lengthM` long, up to `dark` darker where the noise is under
   * `lo` (fully at `hi`), with the far rock layer's distance fade.
   */
  rock: {
    desat: 0.6,
    shade: 0.45,
    color: "#cfc6ba",
    sun: [0.05, 0.35] as const,
    moss: { tame: 0.4, hue: [0.72, 0.92] as const, sat: [0.18, 0.32] as const, lit: [0.06, 0.1] as const },
    streaks: { widthM: 6, lengthM: 40, lo: 0.42, hi: 0.2, dark: 0.3 },
  },
  /**
   * Range lawns: past the grass tufts' reach (`tame.near` to `tame.far` metres; the tufts grade their
   * root like the stops' ground) only `tame.tame` of green's lead is removed. Far ones read as canopy
   * (mid and high tiers): from `near` to `far` metres the colour turns `amount` of the way to
   * `color`'s hue at `value` x its own brightness, broken into lumps `lumpM` metres across
   * (brightness x lump[0] to lump[1]).
   */
  ground: {
    tame: { tame: 0.5, near: 50, far: 100 },
    near: 150,
    far: 260,
    amount: 0.75,
    value: 0.85,
    color: "#3f5a33",
    lumpM: 7,
    lump: [0.7, 1.25] as const,
  },
  /**
   * Mist as layers (the page's copy of clouds.json; the Blender file is unchanged): each puff's height
   * x `flat`, its extent along the wind (`wind`, three x and z) x `stretch` and across it x `across`
   * (3:1 along the wind to its height). Sprite fill along the path drops about 10 % (p95 6.8 to 6.2
   * screens by r47's estimate; clouds.json mist.fill says 7.4 today, the budget).
   * Left as they were: Ice-Fire Island's steam (`keep`: untagged puffs within `radius` metres of
   * `xz`, above `aboveY`) and the opening bank the flight starts in (puffs within `openingM` metres of
   * the path's first `openingFrames` frames).
   */
  mist: {
    flat: 0.5,
    stretch: 1.5,
    across: 0.8,
    wind: [0.87, 0.49] as const,
    keep: { xz: [330.08, -992.67] as const, radius: 60, aboveY: 270 },
    openingFrames: 60,
    openingM: 60,
  },
  /**
   * What is built (stairs, bridges, piers, terraces, shrines, halls) keeps its stone: the stairways'
   * piers and undersides bake with the cliff's rock material (world_pier_stone), so range rock under
   * anything built is left as it was. A grid of `cellM`-metre cells over the areas' anchors +-
   * `marginM` metres marks every cell under an upward-facing built triangle (normal y at least
   * `minUp`: treads, decks, landings, roofs; not hanging vines or roots), grown by `grow` cells (pier
   * footings flare past their deck).
   */
  built: { cellM: 2.5, marginM: 350, minUp: 0.7, grow: 2 },
};

export type RangeLook = typeof RANGE_LOOK;

/**
 * The built mask's grid (RANGE_LOOK.built): cells x0 + i x cell, z0 + j x cell (three's x and z),
 * `marks` the cells built triangles cover, `mask` those grown by `grow` cells (what the shader reads,
 * row j at j x nx).
 */
export interface BuiltGrid {
  x0: number;
  z0: number;
  cell: number;
  nx: number;
  nz: number;
  marks: Uint8Array;
  mask: Uint8Array;
}

/** An empty built grid over the areas' anchors +- marginM (a 1-cell grid at the origin with no areas). */
export function createBuiltGrid(areas: readonly RangeArea[], look: RangeLook = RANGE_LOOK): BuiltGrid {
  const b = look.built;
  const xs = areas.map((a) => a.anchor[0]);
  const zs = areas.map((a) => a.anchor[2]);
  const x0 = (xs.length ? Math.min(...xs) : 0) - b.marginM;
  const z0 = (zs.length ? Math.min(...zs) : 0) - b.marginM;
  const nx = xs.length ? Math.ceil((Math.max(...xs) + b.marginM - x0) / b.cellM) : 1;
  const nz = zs.length ? Math.ceil((Math.max(...zs) + b.marginM - z0) / b.cellM) : 1;
  return { x0, z0, cell: b.cellM, nx, nz, marks: new Uint8Array(nx * nz), mask: new Uint8Array(nx * nz) };
}

/**
 * A mesh's positions as markBuiltTriangles reads them: vertex v's x, y, z at array[v x stride +
 * offset + 0..2], times `scale` (1 for floats; 1 / 32767 for normalized 16-bit, which the glTF
 * files' quantized positions are).
 */
export interface PositionSource {
  array: ArrayLike<number>;
  stride: number;
  offset: number;
  scale: number;
}

/**
 * Marks the cells under triangles [from, to) of a mesh with positions `pos` (`index` or none) and
 * world matrix `m` (column-major, three's elements; null = identity), when the triangle faces up
 * (normal y at least minUp, either winding). A triangle marks the cells its x-z bounding box covers.
 * Returns how many triangles marked.
 */
export function markBuiltTriangles(
  grid: BuiltGrid,
  pos: PositionSource,
  index: ArrayLike<number> | null,
  from: number,
  to: number,
  m: ArrayLike<number> | null = null,
  look: RangeLook = RANGE_LOOK,
): number {
  const p = [0, 0, 0, 0, 0, 0, 0, 0, 0];
  const { array, stride, offset, scale } = pos;
  let marked = 0;
  for (let t = from; t < to; t++) {
    for (let k = 0; k < 3; k++) {
      const o = (index ? index[t * 3 + k] : t * 3 + k) * stride + offset;
      const x = array[o] * scale;
      const y = array[o + 1] * scale;
      const z = array[o + 2] * scale;
      p[k * 3] = m ? m[0] * x + m[4] * y + m[8] * z + m[12] : x;
      p[k * 3 + 1] = m ? m[1] * x + m[5] * y + m[9] * z + m[13] : y;
      p[k * 3 + 2] = m ? m[2] * x + m[6] * y + m[10] * z + m[14] : z;
    }
    const ax = p[3] - p[0];
    const ay = p[4] - p[1];
    const az = p[5] - p[2];
    const bx = p[6] - p[0];
    const by = p[7] - p[1];
    const bz = p[8] - p[2];
    const nx = ay * bz - az * by;
    const ny = az * bx - ax * bz;
    const nz = ax * by - ay * bx;
    const len = Math.hypot(nx, ny, nz);
    if (!(len > 1e-9) || Math.abs(ny) < look.built.minUp * len) continue;
    const i0 = Math.max(Math.floor((Math.min(p[0], p[3], p[6]) - grid.x0) / grid.cell), 0);
    const i1 = Math.min(Math.floor((Math.max(p[0], p[3], p[6]) - grid.x0) / grid.cell), grid.nx - 1);
    const j0 = Math.max(Math.floor((Math.min(p[2], p[5], p[8]) - grid.z0) / grid.cell), 0);
    const j1 = Math.min(Math.floor((Math.max(p[2], p[5], p[8]) - grid.z0) / grid.cell), grid.nz - 1);
    if (i0 > i1 || j0 > j1) continue;
    for (let j = j0; j <= j1; j++) grid.marks.fill(1, j * grid.nx + i0, j * grid.nx + i1 + 1);
    marked++;
  }
  return marked;
}

/** Grows the marks by `grow` cells into the mask (255 = built), a square max filter. */
export function growBuilt(grid: BuiltGrid, look: RangeLook = RANGE_LOOK): void {
  const { nx, nz, marks, mask } = grid;
  const r = look.built.grow;
  const rows = new Uint8Array(nx * nz);
  for (let j = 0; j < nz; j++) {
    for (let i = 0; i < nx; i++) {
      let v = 0;
      for (let d = Math.max(i - r, 0); d <= Math.min(i + r, nx - 1) && !v; d++) v = marks[j * nx + d];
      rows[j * nx + i] = v;
    }
  }
  for (let j = 0; j < nz; j++) {
    for (let i = 0; i < nx; i++) {
      let v = 0;
      for (let d = Math.max(j - r, 0); d <= Math.min(j + r, nz - 1) && !v; d++) v = rows[d * nx + i];
      mask[j * nx + i] = v ? 255 : 0;
    }
  }
}

/** The mask under world (x, z), 0..1 (nearest cell; the shader filters between cells). 0 outside the grid. */
export function builtAt(grid: BuiltGrid, x: number, z: number): number {
  const i = Math.floor((x - grid.x0) / grid.cell);
  const j = Math.floor((z - grid.z0) / grid.cell);
  if (i < 0 || j < 0 || i >= grid.nx || j >= grid.nz) return 0;
  return grid.mask[j * grid.nx + i] / 255;
}

/** An area as the range mask needs it (meta.json areas: anchor in three space, footprint in m). */
export interface RangeArea {
  anchor: Vec3;
  footprint: number;
}

const LUMA: Vec3 = [0.2126, 0.7152, 0.0722];

function luma(c: Vec3): number {
  return c[0] * LUMA[0] + c[1] * LUMA[1] + c[2] * LUMA[2];
}

function smoothstep(a: number, b: number, x: number): number {
  const t = Math.min(Math.max((x - a) / (b - a), 0), 1);
  return t * t * (3 - 2 * t);
}

function mixv(a: Vec3, b: Vec3, t: number): Vec3 {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

/**
 * The areas as the shaders' uniform holds them: [x, y, z, footprint + pad] per slot, RANGE_MAX_AREAS
 * slots, empty ones all zero (skipped). Areas past the last slot are dropped.
 */
export function packRangeAreas(areas: readonly RangeArea[], look: RangeLook = RANGE_LOOK): [number, number, number, number][] {
  const out: [number, number, number, number][] = [];
  for (let i = 0; i < RANGE_MAX_AREAS; i++) {
    const a = areas[i];
    out.push(a ? [a.anchor[0], a.anchor[1], a.anchor[2], Math.max(a.footprint, 0) + look.areas.pad] : [0, 0, 0, 0]);
  }
  return out;
}

/** 1 on the range, 0 within an area's footprint + pad, smooth over `fade` metres. Mirrors sectRangeW. */
export function rangeWeight(p: Vec3, areas: readonly RangeArea[], look: RangeLook = RANGE_LOOK): number {
  let w = 1;
  for (const [x, y, z, r] of packRangeAreas(areas, look)) {
    if (r <= 0) continue;
    w = Math.min(w, smoothstep(r, r + look.areas.fade, Math.hypot(p[0] - x, p[1] - y, p[2] - z)));
  }
  return w;
}

/** The grade's parameters on foliage with range weight w (0 = the stops' grade, 1 = the range's). */
export function foliageGradeParams(
  w: number,
  grade: SectLook["grade"] = SECT_LOOK.grade,
  look: RangeLook = RANGE_LOOK,
): { tame: number; shadowTint: Vec3; splitShadow: number } {
  const f = look.foliage;
  return {
    tame: grade.greenTame + (f.greenTame - grade.greenTame) * w,
    shadowTint: mixv(unitTint(grade.shadowTint), unitTint(f.shadowTint), w),
    splitShadow: (grade.splitShadow ?? grade.split) + (f.splitShadow - (grade.splitShadow ?? grade.split)) * w,
  };
}

/**
 * A linear colour held under HSV saturation `cap`, measured on its square root (about sRGB): the
 * largest channel stays, the others move toward it. Mirrors sectSatCap.
 */
export function capSaturation(c: Vec3, cap: number): Vec3 {
  const q = c.map((v) => Math.sqrt(Math.max(v, 0))) as Vec3;
  const m = Math.max(...q);
  const n = Math.min(...q);
  if (m <= 1e-5 || m - n <= cap * m) return c;
  const k = (cap * m) / (m - n);
  return q.map((v) => {
    const r = m - (m - v) * k;
    return r * r;
  }) as Vec3;
}

/** Leaf weight of a texel before the grade: 1 once green is level with red (look.ts leafWeight). Mirrors sectLeaf. */
export function leafWeight(t: Vec3): number {
  const s = t[0] + t[1];
  return s > 1e-6 ? smoothstep(-0.25, 0, (t[1] - t[0]) / s) : 0;
}

/** Bark weight of a texel before the grade: red-led (not foliage) and not pink (blossom). Mirrors sectBark. */
export function barkWeight(t: Vec3): number {
  const s = t[0] + t[1];
  if (!(s > 1e-6)) return 0;
  return (1 - leafWeight(t)) * smoothstep(0, 0.08, (t[1] - t[2]) / s);
}

/**
 * Range foliage: texel `t` (linear, before the grade) graded with range weight `w`, then the far
 * trunks' mute at `dist` metres. Mirrors the GLSL the foliage materials run (sectGradeWith, then
 * look.ts sectTreeShade in between, which this leaves out, then sectFoliageRange).
 */
export function foliageLinear(t: Vec3, w: number, dist: number, look: RangeLook = RANGE_LOOK, grade: SectLook["grade"] = SECT_LOOK.grade): Vec3 {
  const p = foliageGradeParams(w, grade, look);
  return foliageAfterGrade(gradeLinearWith(t, grade, p.tame, p.shadowTint, p.splitShadow), t, w, dist, look);
}

/** The canopy tint, the cap and the trunks' mute on a graded foliage colour `c` (texel `t`). Mirrors sectFoliageRange. */
export function foliageAfterGrade(c: Vec3, t: Vec3, w: number, dist: number, look: RangeLook = RANGE_LOOK): Vec3 {
  const ti = look.foliage.tint;
  const green = unitTint(ti.color).map((v) => v * luma(c) * ti.gain) as Vec3;
  const tinted = mixv(c, green, leafWeight(t) * w * ti.amount);
  const capped = capSaturation(tinted, 1 + (look.foliage.satCap - 1) * w);
  const tr = look.trunks;
  const k = barkWeight(t) * smoothstep(tr.near, tr.far, dist) * w * tr.amount;
  const target = unitTint(tr.color).map((v) => v * luma(capped) * tr.value) as Vec3;
  return mixv(capped, target, k);
}

/** How mossy a rock texel (before the grade) is, 0..1 (detail.ts greenRockGate's test). Mirrors sectMossGate. */
export function mossGate(t: Vec3, look: RangeLook = RANGE_LOOK): number {
  const g = look.rock.moss;
  const [r, gr, b] = t.map((v) => Math.sqrt(Math.max(v, 0)));
  const mx = Math.max(r, gr);
  return (
    smoothstep(g.hue[0], g.hue[1], (gr - b) / Math.max(mx - b, 1e-3)) * smoothstep(g.sat[0], g.sat[1], (mx - b) / Math.max(mx, 1e-3)) * smoothstep(g.lit[0], g.lit[1], mx)
  );
}

/** Range rock from its texel `t` (before the grade) at range weight w: the moss's tame, then sectRockRange off the moss. */
export function rockRangeLinear(t: Vec3, w: number, look: RangeLook = RANGE_LOOK, grade: SectLook["grade"] = SECT_LOOK.grade): Vec3 {
  const m = mossGate(t, look) * w;
  const c = gradeLinearWith(t, grade, grade.greenTame + (look.rock.moss.tame - grade.greenTame) * m, unitTint(grade.shadowTint), grade.splitShadow ?? grade.split);
  return rockLinear(c, w * (1 - m), look);
}

/** A range lawn's graded colour from its texel `t` at range weight w, `dist` metres away (before the detail). */
export function groundRangeLinear(t: Vec3, w: number, dist: number, look: RangeLook = RANGE_LOOK, grade: SectLook["grade"] = SECT_LOOK.grade): Vec3 {
  const g = look.ground.tame;
  const k = w * smoothstep(g.near, g.far, dist);
  return gradeLinearWith(t, grade, grade.greenTame + (g.tame - grade.greenTame) * k, unitTint(grade.shadowTint), grade.splitShadow ?? grade.split);
}

/** Range rock on a graded colour `c` with range weight w. Mirrors sectRockRange. */
export function rockLinear(c: Vec3, w: number, look: RangeLook = RANGE_LOOK): Vec3 {
  const r = look.rock;
  const l = luma(c);
  const k = r.desat * (r.shade + (1 - r.shade) * smoothstep(r.sun[0], r.sun[1], l)) * w;
  return mixv(c, unitTint(r.color).map((v) => v * l) as Vec3, k);
}

/**
 * The haze multiplier (on meta.fog.density) at a camera frame: each hold's value at its frame,
 * smooth between consecutive holds, the first before them and the last after. 1 with no holds.
 */
export function hazeScaleAt(frame: number, holds: readonly Pick<Hold, "id" | "frame">[], look: RangeLook = RANGE_LOOK): number {
  const pts = holds
    .filter((h) => look.haze.holds[h.id] !== undefined)
    .map((h) => ({ f: h.frame, v: look.haze.holds[h.id] }))
    .sort((a, b) => a.f - b.f);
  if (pts.length === 0) return 1;
  if (frame <= pts[0].f) return pts[0].v;
  for (let i = 1; i < pts.length; i++) {
    if (frame <= pts[i].f) return pts[i - 1].v + (pts[i].v - pts[i - 1].v) * smoothstep(pts[i - 1].f, pts[i].f, frame);
  }
  return pts[pts.length - 1].v;
}

/** True for the puffs the mist pass leaves as they were (Ice-Fire's steam, the opening bank). */
export function keepPuffShape(p: CloudPuff, opening: readonly Vec3[], look: RangeLook = RANGE_LOOK): boolean {
  const m = look.mist;
  if (!p.kind && p.c[1] > m.keep.aboveY && Math.hypot(p.c[0] - m.keep.xz[0], p.c[2] - m.keep.xz[1]) < m.keep.radius) return true;
  return opening.some((o) => Math.hypot(p.c[0] - o[0], p.c[1] - o[1], p.c[2] - o[2]) < m.openingM + boundRadius(p));
}

function boundRadius(p: CloudPuff): number {
  return Math.max(...p.axes.map((a) => Math.hypot(a[0], a[1], a[2])));
}

function support(axes: readonly Vec3[], e: Vec3): number {
  let s = 0;
  for (const a of axes) {
    const d = a[0] * e[0] + a[1] * e[1] + a[2] * e[2];
    s += d * d;
  }
  return Math.sqrt(s);
}

/**
 * A puff as a flat layer: new semi-axes along the wind, across it and up, each the old puff's reach
 * (support radius) that way times `stretch`, `across` and `flat`. Centre and density kept. Puffs
 * keepPuffShape names are returned unchanged.
 */
export function flattenPuff(p: CloudPuff, opening: readonly Vec3[] = [], look: RangeLook = RANGE_LOOK): CloudPuff {
  if (keepPuffShape(p, opening, look)) return p;
  const m = look.mist;
  const len = Math.hypot(m.wind[0], m.wind[1]) || 1;
  const wind: Vec3 = [m.wind[0] / len, 0, m.wind[1] / len];
  const across: Vec3 = [-wind[2], 0, wind[0]];
  const up: Vec3 = [0, 1, 0];
  const scale = (e: Vec3, k: number) => e.map((v) => v * support(p.axes, e) * k) as Vec3;
  return { ...p, axes: [scale(wind, m.stretch), scale(across, m.across), scale(up, m.flat)] };
}

// ---------------------------------------------------------------------------------------------
// GLSL

/** `uniform vec4 uSectAreas[16]` and `float sectRangeW( vec3 p )` (rangeWeight's twin). */
export function rangeGlsl(look: RangeLook = RANGE_LOOK): string {
  return /* glsl */ `
uniform vec4 uSectAreas[ ${RANGE_MAX_AREAS} ];
// 1 on the range, 0 within an area's footprint + pad (the slots are filled from the first; an
// empty one ends the list).
float sectRangeW( vec3 p ) {
  float w = 1.0;
  for ( int i = 0; i < ${RANGE_MAX_AREAS}; i++ ) {
    vec4 a = uSectAreas[ i ];
    if ( a.w <= 0.0 ) break;
    vec3 d = p - a.xyz;
    float far = a.w + ${glslFloat(look.areas.fade)};
    float dd = dot( d, d );
    if ( dd < far * far ) w = min( w, smoothstep( a.w, far, sqrt( dd ) ) );
  }
  return w;
}
// 1 under anything built (stairs, bridges, piers, terraces), 0 elsewhere and outside the grid: the
// built mask (RANGE_LOOK.built), its box as (x0, z0, 1 / width, 1 / depth) in metres.
uniform sampler2D tSectBuilt;
uniform vec4 uSectBuiltBox;
float sectBuilt( vec3 p ) {
  vec2 uv = ( p.xz - uSectBuiltBox.xy ) * uSectBuiltBox.zw;
  if ( uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0 ) return 0.0;
  return texture2D( tSectBuilt, uv ).r;
}
`;
}

/**
 * After rangeGlsl, for foliage: `vec3 sectFoliageRange( vec3 c, vec3 t, float w, float dist )`
 * (foliageAfterGrade's twin: the saturation cap, then the far trunks' mute) and its helpers.
 */
export function foliageGlsl(look: RangeLook = RANGE_LOOK): string {
  const tr = look.trunks;
  const ti = look.foliage.tint;
  return /* glsl */ `
vec3 sectSatCap( vec3 c, float cap ) {
  vec3 q = sqrt( max( c, 0.0 ) );
  float m = max( max( q.r, q.g ), q.b );
  float n = min( min( q.r, q.g ), q.b );
  if ( m <= 1e-5 || m - n <= cap * m ) return c;
  q = m - ( m - q ) * ( cap * m / ( m - n ) );
  return q * q;
}
float sectLeaf( vec3 t ) {
  float s = t.r + t.g;
  return s > 1e-6 ? smoothstep( -0.25, 0.0, ( t.g - t.r ) / s ) : 0.0;
}
float sectBark( vec3 t ) {
  float s = t.r + t.g;
  if ( s <= 1e-6 ) return 0.0;
  return ( 1.0 - sectLeaf( t ) ) * smoothstep( 0.0, 0.08, ( t.g - t.b ) / s );
}
vec3 sectFoliageRange( vec3 c, vec3 t, float w, float dist ) {
  float l = dot( c, vec3( 0.2126, 0.7152, 0.0722 ) );
  c = mix( c, l * ${glslFloat(ti.gain)} * ${glslVec3(unitTint(ti.color))}, sectLeaf( t ) * w * ${glslFloat(ti.amount)} );
  c = sectSatCap( c, ${glslFloat(1)} + ${glslFloat(look.foliage.satCap - 1)} * w );
  float k = sectBark( t ) * smoothstep( ${glslFloat(tr.near)}, ${glslFloat(tr.far)}, dist ) * w * ${glslFloat(tr.amount)};
  return mix( c, dot( c, vec3( 0.2126, 0.7152, 0.0722 ) ) * ${glslFloat(tr.value)} * ${glslVec3(unitTint(tr.color))}, k );
}
`;
}

/**
 * The GLSL statement foliage runs in place of `vec3 sectGraded = sectGrade( sectTexel );`: the grade
 * (look.ts sectGradeWith) with the range's parameters blended in by the range weight `sectRw`
 * (declared before it: `float sectRw = sectRangeW( vSectWorld );`, materials.ts).
 */
export function foliageGradeStatements(grade: SectLook["grade"] = SECT_LOOK.grade, look: RangeLook = RANGE_LOOK): string {
  const f = look.foliage;
  const ss = grade.splitShadow ?? grade.split;
  return [
    `  vec3 sectGraded = sectGradeWith( sectTexel, mix( ${glslFloat(grade.greenTame)}, ${glslFloat(f.greenTame)}, sectRw ),`,
    `    mix( ${glslVec3(unitTint(grade.shadowTint))}, ${glslVec3(unitTint(f.shadowTint))}, sectRw ), mix( ${glslFloat(ss)}, ${glslFloat(f.splitShadow)}, sectRw ) );`,
  ].join("\n");
}

/**
 * The GLSL statements rock runs in place of `vec3 sectGraded = sectGrade( sectTexel );` (needs
 * sectRw, rockGlsl, look.ts sectGradeWith): rockRangeLinear's twin.
 */
export function rockGradeStatements(grade: SectLook["grade"] = SECT_LOOK.grade, look: RangeLook = RANGE_LOOK): string {
  return [
    "  float sectMoss = sectMossGate( sectTexel ) * sectRw;",
    `  vec3 sectGraded = sectGradeWith( sectTexel, mix( ${glslFloat(grade.greenTame)}, ${glslFloat(look.rock.moss.tame)}, sectMoss ), ${baseTint(grade)} );`,
    "  sectGraded = sectRockRange( sectGraded, sectRw * ( 1.0 - sectMoss ) );",
  ].join("\n");
}

/**
 * The GLSL statement ground runs in place of `vec3 sectGraded = sectGrade( sectTexel );` (needs
 * sectRw, vSectWorld, look.ts sectGradeWith): groundRangeLinear's twin.
 */
export function groundGradeStatements(grade: SectLook["grade"] = SECT_LOOK.grade, look: RangeLook = RANGE_LOOK): string {
  const g = look.ground.tame;
  return [
    `  float sectGt = sectRw * smoothstep( ${glslFloat(g.near)}, ${glslFloat(g.far)}, length( vSectWorld - cameraPosition ) );`,
    `  vec3 sectGraded = sectGradeWith( sectTexel, mix( ${glslFloat(grade.greenTame)}, ${glslFloat(g.tame)}, sectGt ), ${baseTint(grade)} );`,
  ].join("\n");
}

/** The stops' shadow tint and split as sectGradeWith's last two arguments. */
function baseTint(grade: SectLook["grade"]): string {
  return `${glslVec3(unitTint(grade.shadowTint))}, ${glslFloat(grade.splitShadow ?? grade.split)}`;
}

/**
 * After rangeGlsl, for rock: `float sectMossGate( vec3 t )` (mossGate's twin) and `vec3
 * sectRockRange( vec3 c, float w )` (rockLinear's twin).
 */
export function rockGlsl(look: RangeLook = RANGE_LOOK): string {
  const r = look.rock;
  const m = r.moss;
  return /* glsl */ `
float sectMossGate( vec3 t ) {
  vec3 q = sqrt( max( t, vec3( 0.0 ) ) );
  float mx = max( q.r, q.g );
  return smoothstep( ${glslFloat(m.hue[0])}, ${glslFloat(m.hue[1])}, ( q.g - q.b ) / max( mx - q.b, 1e-3 ) )
    * smoothstep( ${glslFloat(m.sat[0])}, ${glslFloat(m.sat[1])}, ( mx - q.b ) / max( mx, 1e-3 ) ) * smoothstep( ${glslFloat(m.lit[0])}, ${glslFloat(m.lit[1])}, mx );
}
vec3 sectRockRange( vec3 c, float w ) {
  float l = dot( c, vec3( 0.2126, 0.7152, 0.0722 ) );
  float k = ${glslFloat(r.desat)} * mix( ${glslFloat(r.shade)}, 1.0, smoothstep( ${glslFloat(r.sun[0])}, ${glslFloat(r.sun[1])}, l ) ) * w;
  return mix( c, l * ${glslVec3(unitTint(r.color))}, k );
}
`;
}
