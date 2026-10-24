/**
 * Tiling surface detail on /sect's baked rock and ground, and the needle cards' alpha tag.
 *
 * The bake's atlas holds 3-20 texels a metre, so close up rock and grass read as a 5-40 cm blur.
 * The exporter (bake_web.py) splits rock and ground faces into their own materials
 * (extras.detail = "rock" | "ground"); the client multiplies a shared tileable texture
 * (detail.webp: R = high-passed marble cliff, G = leafy grass, B = moss, each mid grey 0.5) over
 * them in world space, fading it out with distance. Pine needle cards (bake_trees.py) are tagged
 * extras.cardAlpha = "needle" and carry their cut-out in the occlusion slot on the second UV set.
 *
 * On top of that photo detail, layers the bake cannot hold, from two runtime textures (noise.ts,
 * built in materials.ts): grass clumps (0.3-1 m), large colour patches (13-38 m) and moving wind
 * sheen on the ground and on mossy rock out to 260-320 m (the camera sees lawns from 30 to 400 m,
 * where single blades are below a pixel and the photo has faded out); and on rock a far layer of 3D
 * noise and strata bands, continuous across triangles, out to 700 m. They cannot re-light the
 * per-triangle bake; they only make its facet lines less noticeable.
 *
 * Paving (extras.detail = "paving": the marble plazas, paths and terrace tops, materials._paving):
 * the bake keeps each slab's tone but not its 1.2 cm joints, so the forge and mission plazas read as
 * flat white sheets. Their faces carry the material's own slab coordinates as a second UV set
 * (TEXCOORD_1, three's uv1: the object's local x and 1 - y in metres), and the layer draws the
 * slab grid of Blender's brick texture on them: filtered joints, a grime band along each slab's
 * edges, a tone and warmth per slab, moss in the joints where a noise field says damp, broad worn
 * patches, and the marble scan (R) per slab.
 *
 * Tiles (extras.detail = "tiles": the roof sheets' tile material, arch.tile_material): each roof
 * slope bakes as one island now (no more speckle from 2-texel strips), but at 1.4-2 texels a tile
 * course the bake cannot hold the courses. The faces carry the sheet's own tile UVs as uv1 (u:
 * courses, integers on the tube crests; v: laps, integers on the lips) and the layer draws the
 * material's own pattern (arch._lapped_tile: the dark crease where tube meets pan, the shadow under
 * each lip) plus a lit crest, normalised to keep the bake's mean and faded out where a pixel
 * covers half a course.
 *
 * Pure data, maths and GLSL strings (no three.js import), so it is testable.
 */
import { glslFloat, glslVec3 } from "./glsl";
import { unitTint } from "./look";
import { RANGE_LOOK, type RangeLook } from "./range-look";
import type { Tier } from "./runtime";

/**
 * Metres one repeat of each detail.webp channel covers (the whole scan tile it was cut from).
 * Paving reads the rock's marble scan (R) smaller, as polished slab grain.
 */
export const DETAIL_TILE_M = { rock: 8.14, ground: 2.0, moss: 1.5, paving: 2.5 } as const;

export type DetailClass = "rock" | "ground" | "paving" | "tiles";

/**
 * The layers' runtime textures (materials.ts getGroundNoiseTexture and getClumpTexture, from
 * noise.ts groundNoise and clumpField).
 */
export const DETAIL_NOISE = {
  /**
   * RGBA, `size` px: R a white-noise lattice and G the same moved by `offset` texels (one read =
   * two slices of 3D value noise); B and A smooth fields ranked to uniform 0..1, about `cells`
   * blobs across (so a layer with s-metre blobs repeats every s x cells metres).
   */
  ground: { size: 128, offset: [37, 17] as const, cells: 8 },
  /** One channel, `size` px, `cells` x `cells` clumps per tile, ranked to mean `mean`. */
  clump: { size: 256, cells: 11, mean: 0.7 },
} as const;

export const DETAIL_LOOK = {
  /**
   * gain: stops of brightness per unit of (d - 0.5) at full strength. fadeNear / fadeFar: camera
   * distance (m) where the detail starts to fade, and where it is gone.
   *
   * The two layers' (d - 0.5) has a std of about 0.11 in detail.webp, so the first guess (0.35 /
   * 0.3) moved a typical texel by 1.5 % and could not be seen. 2.0 / 1.0 move it by about 10 % /
   * 5 % (1 in 20 texels by more than 28 % / 15 %). The scans' own fine contrast would need about 7
   * (rock) and 3.8 (grass); the bake already holds part of it. Tune on the page. The ground's
   * reaches 140 m (was 90), so the clumps take over from it gradually.
   */
  rock: { gain: 2.0, fadeNear: 25, fadeFar: 150 },
  ground: { gain: 1.0, fadeNear: 15, fadeFar: 140 },
  /**
   * Paving. gain / fadeNear / fadeFar: the marble scan per slab, like the classes above. The rest
   * is the slab layer (sectPaving):
   * - slabM, offset, jointM: materials._paving's brick texture (Brick Width 1.2, Row Height 0.8,
   *   Offset 0.5 every second row, Mortar Size 0.012: a joint 2.4 cm wide), so the joints land on
   *   the edges of the slab tones the bake kept.
   * - joint: grout colour factor `dark`, faded out from fadeNear to fadeFar metres (beyond it a
   *   joint is a tenth of a pixel; the filtered lines would only grey the plaza).
   * - grime: a darker band `widthM` wide inside each slab's edges (dirt against the joint).
   * - slab: each slab's own value (+-value) and warmth (+-warm), faded out at fadeFar.
   * - moss: in the joints (and a third as much in the grime band) where the ground noise's A field,
   *   at blobs scaleM metres across, rises from lo to hi; more in shadow.
   * - wear: broad patches (the B field at scaleM) where feet polished the stone: lighter by `lift`,
   *   joints and grime at (1 - amount).
   * - up: the layer only on faces whose |normal.y| rises from up[0] to up[1] (slab sides that
   *   share the material keep the bake).
   * The first numbers are guesses checked on screenshots of the forge (352) and mission (619)
   * plazas.
   */
  paving: {
    gain: 1.2,
    fadeNear: 12,
    fadeFar: 60,
    slabM: [1.2, 0.8] as const,
    offset: 0.5,
    jointM: 0.012,
    joint: { dark: 0.5, fadeNear: 35, fadeFar: 100 },
    grime: { widthM: 0.06, dark: 0.12 },
    slab: { value: 0.09, warm: 0.04, fadeFar: 320 },
    moss: { scaleM: 7, lo: 0.58, hi: 0.82, amount: 0.8, tint: [0.6, 0.78, 0.4] as const },
    wear: { scaleM: 18, lo: 0.55, hi: 0.8, amount: 0.6, lift: 0.04 },
    up: [0.55, 0.8] as const,
  },
  /**
   * Roof tile courses (sectTiles), in course (u) and lap (v) units. crest: the tube's top, lifted by
   * `lift` up to `width` from the crest line. crease and lip: arch._lapped_tile's bands, each
   * mixing toward `dark` x the colour by its weight (creaseK, lipK) x k. The weights are about
   * twice the material's (0.45, 0.5): the bands also stand for the light the bake cannot resolve
   * (the crease and the lip in shadow, the crest catching the sky); at the material's weights the
   * courses were barely visible on the black roofs (+-6 levels). k = 1 - kLum x the
   * texel's (about sRGB) brightness, clamped to kRange (a pale glaze gets less, as in the
   * material). Each axis fades to the mean from fade[0] to fade[1] courses (laps) per pixel.
   */
  tiles: {
    crest: { width: 0.14, lift: 0.3 },
    crease: [0.17, 0.215, 0.24, 0.38] as const,
    lip: [0.8, 0.985] as const,
    dark: 0.42,
    creaseK: 0.9,
    lipK: 0.8,
    kLum: 0.75,
    kRange: [0.3, 1] as const,
    fade: [0.3, 0.6] as const,
  },
  /** Weight of the first layer (the tile at its real size). */
  layer1: 0.75,
  /**
   * The second layer hides the repeat: UV scale (0.31 = 3.2x larger), rotation (radians), offset
   * (in tiles) and weight.
   */
  layer2: { scale: 0.31, angle: 0.6435, offset: [0.37, 0.61] as const, weight: 0.5 },
  /**
   * Exponent on |face normal| for the rock's three projections. 3 (was 6) blends them over a wider
   * band of angles, so the pattern changes less at each triangle edge (a little softer at corners).
   */
  sharpness: 3,
  /** Shadowed texels get less detail: strength `floor` at graded luminance `lo`, 1 from `hi`. */
  dark: { floor: 0.4, lo: 0.015, hi: 0.15 },
  /**
   * Grass clumps, read straight down from the clump field: once at its own tile (`tileM` metres),
   * once rotated, `second.scale` as fine (3.2x larger: 1-3 m tussocks) at `second.weight` of the
   * strength. Gaps x `gap`, tops x `top`, divided by the field's mean so the average is unchanged.
   * The gaps darken fully looking down (|view.y| from grazing[1]) and by `grazingKeep` of that at
   * grazing angles (to grazing[0]), where the blades in front hide them. Fades from fadeNear to
   * fadeFar metres (mipmaps fade it before that). The first guess (gaps x 0.72, tops x 1.10, the
   * larger read at half strength, a third of the gaps at grazing) could not be seen from the holds
   * (lawns 40-125 m away): it raised the lawns' 4-pixel contrast by about 10 %; these by 35-45 %.
   */
  clump: {
    tileM: 6.4,
    gap: 0.6,
    top: 1.12,
    grazing: [0.12, 0.5] as const,
    grazingKeep: 0.5,
    second: { scale: 0.3125, angle: 1.1071, offset: [0.21, 0.73] as const, weight: 1 },
    fadeNear: 110,
    fadeFar: 260,
  },
  /**
   * Large colour patches, never faded (they carry the distant caps): the ground noise's B (lush)
   * and A (bright) fields with blobs about scalesM[0] and scalesM[1] metres across, weighted
   * `weights`. Each field's deviation from 0.5, times `spread`, is clamped to -1..1: lush turns the
   * hue by up to hueDeg degrees toward green (dry: toward gold) and the saturation by `sat`;
   * brightness moves by `value` (half from the bright field, half darker where lush). With hueDeg 4
   * the hue spread of a hold's lawn pixels grew by about 1 degree; 8 adds 2.5-4.5.
   */
  macro: {
    scalesM: [38, 13] as const,
    weights: [0.5, 0.5] as const,
    angles: [0.31, 2.03] as const,
    offsets: [
      [0.13, 0.47],
      [0.71, 0.29],
    ] as const,
    spread: 3,
    value: 0.14,
    sat: 0.12,
    hueDeg: 8,
  },
  /**
   * Wind sheen: the ground noise's B field at scaleM metres along the wind (`stretch` x longer
   * across it, so the waves run as bands; `offset` in texture repeats), drifting with the wind at
   * `speed` m/s. Brightness +-amount, (1 + sunBoost) x stronger looking toward the sun, less in
   * shadow (like the detail); fades from fadeNear to fadeFar metres. The grass tufts' gusts
   * (grass.ts grassWindGlsl) read the same field, so they bend under the bright bands.
   */
  sheen: {
    scaleM: 16,
    stretch: 2,
    wind: [0.87, 0.49] as const,
    offset: [0.53, 0.19] as const,
    speed: 1.1,
    amount: 0.08,
    sunBoost: 0.5,
    fadeNear: 160,
    fadeFar: 320,
  },
  /**
   * Mossy rock gets the ground's clumps and patches. The test reads the texel before the grade (the
   * grade removes green's lead over red, greenTame, so the graded colour cannot tell moss from
   * rock), as square roots of linear (about sRGB): `hue` on (g - b) / (max(r, g) - b), 1 for
   * yellow-green and greener, 0.8 at a hue of 48 degrees (olive moss), 0.58 at 35 (sandstone);
   * `sat` on (max(r, g) - b) / max(r, g); `lit` on max(r, g), so shadow noise stays out. Green
   * leading red by 0.03-0.08 (the first idea) missed the olive moss, which most mossy slopes are
   * (the arena's green cliff): on the atlases this opens on 97 % of green-hued rock texels, 73 % of
   * olive ones and none of the sandstone.
   */
  greenRock: { hue: [0.72, 0.92] as const, sat: [0.18, 0.32] as const, lit: [0.06, 0.1] as const },
  /**
   * Far rock: 3D value noise in world space at scalesM metres a lattice cell (the second octave on
   * high only, at `weights[1]`), plus horizontal strata bands every band.periodM metres, their
   * height warped by the noise (band.warpM metres). `gain` stops per unit of the sum (a std of
   * about 0.26), a little less in shadow (down to darkFloor: most range rock faces away from the low
   * sun, and the haze already halves it). In from fadeNear / 2 to fadeNear metres, out from 0.6 x
   * fadeFar to fadeFar. Keep gain at or below 0.8: stronger reads as dirt.
   */
  rockFar: {
    scalesM: [14, 45] as const,
    weights: [1, 0.8] as const,
    gain: 0.8,
    darkFloor: 0.75,
    band: { periodM: 11, weight: 0.15, warpM: 6 },
    fadeNear: 100,
    fadeFar: 700,
  },
};

export type DetailLook = typeof DETAIL_LOOK;

/** The detail class of a material's extras.detail, or null. */
export function detailClass(v: unknown): DetailClass | null {
  return v === "rock" || v === "ground" || v === "paving" || v === "tiles" ? v : null;
}

export interface PavingSlab {
  /** The slab's column and row in Blender's brick texture. */
  col: number;
  row: number;
  /** Distance (m) from the point to the slab's nearest vertical and horizontal side. */
  edge: [number, number];
}

/**
 * The slab under (x, y) (metres in the paving material's object space): Blender's brick texture
 * (svm_brick) with materials._paving's settings. Every second row (row % 2 == 0, as C's % has it:
 * so for negative rows too) is shifted by offset x the brick width.
 */
export function pavingSlab(x: number, y: number, look = DETAIL_LOOK): PavingSlab {
  const [bw, rh] = look.paving.slabM;
  const row = Math.floor(y / rh);
  const shift = row % 2 !== 0 ? 0 : bw * look.paving.offset;
  const col = Math.floor((x + shift) / bw);
  const ix = x + shift - col * bw;
  const iy = y - row * rh;
  return { col, row, edge: [Math.min(ix, bw - ix), Math.min(iy, rh - iy)] };
}

/**
 * The share of a pixel `w` metres across, centred `e` metres from a joint's middle, that the joint
 * (`half` metres each side) covers: the box-filtered line, so a joint thinner than a pixel greys it
 * by its share instead of flickering.
 */
export function jointCoverage(e: number, w: number, half: number): number {
  const ww = Math.max(w, 1e-5);
  return Math.max(Math.min(e + 0.5 * ww, half) - Math.max(e - 0.5 * ww, -half), 0) / ww;
}

type TileLook = DetailLook["tiles"];

function tileBands(fu: number, fv: number, t: TileLook): { crest: number; crease: number; lip: number } {
  const c = t.crease;
  return {
    crest: 1 - smoothstep(0, t.crest.width, fu),
    crease: smoothstep(c[0], c[1], fu) * (1 - smoothstep(c[2], c[3], fu)),
    lip: smoothstep(t.lip[0], t.lip[1], fv),
  };
}

const tileMeanCache = new WeakMap<object, { crest: number; crease: number; lip: number }>();

/** The bands' means over a course (crest, crease: u in 0..0.5) and a lap (lip: v in 0..1). */
export function tileMeans(look = DETAIL_LOOK): { crest: number; crease: number; lip: number } {
  const hit = tileMeanCache.get(look.tiles);
  if (hit) return hit;
  const n = 4000;
  const m = { crest: 0, crease: 0, lip: 0 };
  for (let i = 0; i < n; i++) {
    const b = tileBands(((i + 0.5) / n) * 0.5, (i + 0.5) / n, look.tiles);
    m.crest += b.crest / n;
    m.crease += b.crease / n;
    m.lip += b.lip / n;
  }
  tileMeanCache.set(look.tiles, m);
  return m;
}

/**
 * Mirror of sectTiles: the factor on a roof texel at tile UV (u, v), on a texel of linear luminance
 * `lum` (before the grade), with a pixel footprint of wu courses and wv laps. Its mean over a
 * course and a lap is 1 (the bake already holds the average).
 */
export function tileCourseFactor(u: number, v: number, lum: number, wu = 0, wv = 0, look = DETAIL_LOOK): number {
  const t = look.tiles;
  const fu = Math.abs(u + 0.5 - Math.floor(u + 0.5) - 0.5);
  const fv = v - Math.floor(v);
  const k = Math.min(Math.max(1 - t.kLum * Math.sqrt(Math.max(lum, 0)), t.kRange[0]), t.kRange[1]);
  const b = tileBands(fu, fv, t);
  const m = tileMeans(look);
  const d = 1 - t.dark;
  const a = ((1 + t.crest.lift * b.crest) * (1 - d * t.creaseK * k * b.crease)) / (1 + t.crest.lift * m.crest - d * t.creaseK * k * m.crease);
  const l = (1 - d * t.lipK * k * b.lip) / (1 - d * t.lipK * k * m.lip);
  const fa = smoothstep(t.fade[0], t.fade[1], wu);
  const fl = smoothstep(t.fade[0], t.fade[1], wv);
  return (a + (1 - a) * fa) * (l + (1 - l) * fl);
}

/** True for a needle card material (extras.cardAlpha = "needle"). */
export function isNeedleCard(userData: Record<string, unknown> | null | undefined): boolean {
  return userData?.cardAlpha === "needle";
}

function smoothstep(a: number, b: number, x: number): number {
  const t = Math.min(Math.max((x - a) / (b - a), 0), 1);
  return t * t * (3 - 2 * t);
}

function clamp1(x: number): number {
  return Math.min(Math.max(x, -1), 1);
}

/** 1 up to `near` metres from the camera, 0 from `far`, smooth between (the shader's fade). */
export function detailFade(dist: number, near: number, far: number): number {
  return 1 - smoothstep(near, far, dist);
}

/** Strength on a texel of graded linear luminance `lum`: lower in the shadows (down to `floor`). */
export function detailDarkScale(lum: number, look = DETAIL_LOOK, floor = look.dark.floor): number {
  const { lo, hi } = look.dark;
  return floor + (1 - floor) * smoothstep(lo, hi, lum);
}

/**
 * TypeScript mirror of the shader: the factor on a texel's colour for detail value `d` (0..1, 0.5
 * = no change), `dist` metres from the camera, on a texel of graded luminance `lum`. (Tiles have
 * no scan: tileCourseFactor.)
 */
export function detailFactor(kind: Exclude<DetailClass, "tiles">, d: number, dist: number, lum: number, look = DETAIL_LOOK): number {
  const k = look[kind];
  return Math.pow(2, (d - 0.5) * k.gain * detailFade(dist, k.fadeNear, k.fadeFar) * detailDarkScale(lum, look));
}

type Rgb = readonly [number, number, number];

/**
 * Mirror of sectGroundTint: the colour `col` (linear) under the patch fields, `lush` and `bright`
 * the weighted B and A reads (0..1, 0.5 = no change).
 */
export function groundTint(col: Rgb, lush: number, bright: number, look = DETAIL_LOOK): [number, number, number] {
  const m = look.macro;
  const l = clamp1((lush - 0.5) * m.spread);
  const b = clamp1((bright - 0.5) * m.spread);
  // Hue: a rotation about the grey axis (positive turns red toward green).
  const a = (l * m.hueDeg * Math.PI) / 180;
  const c = Math.cos(a);
  const s = Math.sin(a);
  const k = 1 / Math.sqrt(3);
  const dk = k * (col[0] + col[1] + col[2]) * (1 - c);
  const rot = [
    col[0] * c + k * (col[2] - col[1]) * s + k * dk,
    col[1] * c + k * (col[0] - col[2]) * s + k * dk,
    col[2] * c + k * (col[1] - col[0]) * s + k * dk,
  ];
  const y = 0.2126 * rot[0] + 0.7152 * rot[1] + 0.0722 * rot[2];
  const sat = 1 + l * m.sat;
  const v = 1 + (b * 0.5 - l * 0.5) * m.value;
  return [0, 1, 2].map((i) => Math.max(y + (rot[i] - y) * sat, 0) * v) as [number, number, number];
}

/** How much of the clumps' gap darkening shows at a view whose direction has |y| = `down`. */
export function clumpGapWeight(down: number, look = DETAIL_LOOK): number {
  const c = look.clump;
  return c.grazingKeep + (1 - c.grazingKeep) * smoothstep(c.grazing[0], c.grazing[1], down);
}

/**
 * Mirror of the shader's clumps: the factor for clump field reads v1 (own tile) and v2 (the larger
 * rotated read), both 0..1, seen with |view.y| = `down` from `dist` metres. Each read's factor has
 * mean 1 over the field (mean DETAIL_NOISE.clump.mean).
 */
export function clumpFactor(v1: number, v2: number, down: number, dist: number, look = DETAIL_LOOK, mean: number = DETAIL_NOISE.clump.mean): number {
  const c = look.clump;
  const w = clumpGapWeight(down, look);
  const layer = (v: number, weight: number) => {
    const gap = 1 - (1 - c.gap) * w * weight;
    const top = 1 + (c.top - 1) * weight;
    return (gap + (top - gap) * v) / (gap + (top - gap) * mean);
  };
  const f = layer(v1, 1) * layer(v2, c.second.weight);
  return 1 + (f - 1) * detailFade(dist, c.fadeNear, c.fadeFar);
}

/**
 * Mirror of the shader's wind sheen: the factor for sheen field value `n` (0..1), `toward` the
 * dot of the view direction with the sun's (negative = away), `dist` metres away, on a texel of
 * graded luminance `lum`.
 */
export function sheenFactor(n: number, toward: number, dist: number, lum: number, look = DETAIL_LOOK): number {
  const s = look.sheen;
  const t = Math.max(toward, 0);
  return 1 + (n - 0.5) * 2 * s.amount * (1 + s.sunBoost * t * t) * detailFade(dist, s.fadeNear, s.fadeFar) * detailDarkScale(lum, look);
}

/** In-out fade of the far rock layer at `dist` metres. */
export function rockFarFade(dist: number, look = DETAIL_LOOK): number {
  const r = look.rockFar;
  return smoothstep(r.fadeNear * 0.5, r.fadeNear, dist) * (1 - smoothstep(r.fadeFar * 0.6, r.fadeFar, dist));
}

/**
 * Mirror of the far rock layer: the factor for noise reads `a` (14 m) and `b` (45 m; 0.5 when
 * absent), both 0..1, and the strata band's sine `band` (-1..1), at `dist` metres on a texel of
 * graded luminance `lum`.
 */
export function rockFarFactor(a: number, b: number, band: number, dist: number, lum: number, look = DETAIL_LOOK): number {
  const r = look.rockFar;
  const d = (a - 0.5) * r.weights[0] + (b - 0.5) * r.weights[1] + band * r.band.weight;
  return Math.pow(2, d * r.gain * rockFarFade(dist, look) * detailDarkScale(lum, look, r.darkFloor));
}

/** Mirror of the mossy-rock gate: 0..1 from the texel's linear colour before the grade. */
export function greenRockGate(texel: Rgb, look = DETAIL_LOOK): number {
  const g = look.greenRock;
  const [r, gr, b] = texel.map((v) => Math.sqrt(Math.max(v, 0)));
  const mx = Math.max(r, gr);
  return (
    smoothstep(g.hue[0], g.hue[1], (gr - b) / Math.max(mx - b, 1e-3)) * smoothstep(g.sat[0], g.sat[1], (mx - b) / Math.max(mx, 1e-3)) * smoothstep(g.lit[0], g.lit[1], mx)
  );
}

export interface DetailContextHints {
  /** The device tier, when the caller knows it. */
  tier?: Tier;
  lowTextures: boolean;
  alphaToCoverage: boolean;
  shadows: boolean;
}

/**
 * Whether the page loads the detail texture and patches the materials: only when the manifest
 * names one, and never on the low tier. Without an explicit tier, the low tier is recognised by the
 * options the page makes for it (2048 px textures, no postprocessing: alpha to coverage on the
 * multisampled canvas and no shadows; mid on a touch screen has 2048 px textures too, but no alpha
 * to coverage).
 */
export function detailWanted(detail: string | null | undefined, hints: DetailContextHints): boolean {
  if (!detail) return false;
  const low = hints.tier !== undefined ? hints.tier === "low" : hints.lowTextures && hints.alphaToCoverage && !hints.shadows;
  return !low;
}

/** Octaves of the far rock layer for a tier (the uSectRockOctaves uniform): one on mid. */
export function rockFarOctaves(tier: Tier): number {
  return tier === "high" ? 2 : 1;
}

function rotation(angle: number): string {
  const c = glslFloat(Math.cos(angle));
  return `mat2( ${c}, ${glslFloat(Math.sin(angle))}, ${glslFloat(-Math.sin(angle))}, ${c} )`;
}

function vec2(v: readonly [number, number]): string {
  return `vec2( ${glslFloat(v[0])}, ${glslFloat(v[1])} )`;
}

/**
 * GLSL of the large colour patches, shared by the ground shader and the grass tufts (grass.ts calls
 * it at each tuft's root, so a tuft matches the ground around it): `uniform sampler2D
 * tSectGroundNoise;` (materials.ts getGroundNoiseTexture) and `vec3 sectGroundTint( vec3 col,
 * vec3 p )`, the linear colour `col` at world position p (three, Y up) under the patches. Two reads,
 * no time and no clumps; usable in a vertex shader (there the reads take the top mip level).
 */
export function groundTintGlsl(look = DETAIL_LOOK): string {
  const m = look.macro;
  const cells = DETAIL_NOISE.ground.cells;
  const read = (i: 0 | 1) =>
    `texture2D( tSectGroundNoise, ${rotation(m.angles[i])} * p.xz * ${glslFloat(1 / (m.scalesM[i] * cells))} + ${vec2(m.offsets[i])} ).ba`;
  const sp = glslFloat(m.spread);
  return /* glsl */ `
uniform sampler2D tSectGroundNoise;
vec3 sectGroundTint( vec3 col, vec3 p ) {
  vec2 sectTa = ${read(0)};
  vec2 sectTb = ${read(1)};
  vec2 sectTn = clamp( ( sectTa * ${glslFloat(m.weights[0])} + sectTb * ${glslFloat(m.weights[1])} - 0.5 ) * ${sp}, -1.0, 1.0 );
  // Lush (x) turns the hue toward green about the grey axis, dry toward gold.
  float sectTh = sectTn.x * ${glslFloat((m.hueDeg * Math.PI) / 180)};
  float sectTc = cos( sectTh );
  vec3 sectTk = vec3( 0.57735027 );
  col = col * sectTc + cross( sectTk, col ) * sin( sectTh ) + sectTk * dot( sectTk, col ) * ( 1.0 - sectTc );
  float sectTl = dot( col, vec3( 0.2126, 0.7152, 0.0722 ) );
  col = max( vec3( sectTl ) + ( col - vec3( sectTl ) ) * ( 1.0 + sectTn.x * ${glslFloat(m.sat)} ), 0.0 );
  return col * ( 1.0 + ( sectTn.y * 0.5 - sectTn.x * 0.5 ) * ${glslFloat(m.value)} );
}
`;
}

/** GLSL: `float sectClump( vec3 p, float w )`, the clumps' factor at p with gap weight w (clumpGapWeight). */
function clumpGlsl(look: DetailLook): string {
  const c = look.clump;
  const mean = glslFloat(DETAIL_NOISE.clump.mean);
  const layer = (v: string, weight: number) => {
    const g = `( 1.0 - ${glslFloat((1 - c.gap) * weight)} * w )`;
    const t = glslFloat(1 + (c.top - 1) * weight);
    return `mix( ${g}, ${t}, ${v} ) / mix( ${g}, ${t}, ${mean} )`;
  };
  const q = `p.xz * ${glslFloat(1 / c.tileM)}`;
  return /* glsl */ `
float sectClump( vec3 p, float w ) {
  float sectCa = texture2D( tSectClump, ${q} ).r;
  float sectCb = texture2D( tSectClump, ${rotation(c.second.angle)} * ${q} * ${glslFloat(c.second.scale)} + ${vec2(c.second.offset)} ).r;
  return ${layer("sectCa", 1)} * ${layer("sectCb", c.second.weight)};
}
`;
}

/**
 * GLSL: `vec3 sectGroundLayers( vec3 col, vec3 p, vec3 v, float dist )` (patches and clumps) and
 * `float sectSheen( vec3 p, vec3 v, float dist, float ds )` (the wind sheen's factor, ground only).
 */
function groundLayersGlsl(look: DetailLook): string {
  const c = look.clump;
  const s = look.sheen;
  const w = Math.hypot(s.wind[0], s.wind[1]);
  const wx = glslFloat(s.wind[0] / w);
  const wz = glslFloat(s.wind[1] / w);
  const inv = glslFloat(1 / (s.scaleM * DETAIL_NOISE.ground.cells));
  return /* glsl */ `
// The patches and clumps on colour col at p, seen along v (unit, camera to p) from dist metres.
vec3 sectGroundLayers( vec3 col, vec3 p, vec3 v, float dist ) {
  col = mix( col, sectGroundTint( col, p ), uSectGroundLayers );
  float sectW = mix( ${glslFloat(c.grazingKeep)}, 1.0, smoothstep( ${glslFloat(c.grazing[0])}, ${glslFloat(c.grazing[1])}, abs( v.y ) ) );
  return col * mix( 1.0, sectClump( p, sectW ), ( 1.0 - smoothstep( ${glslFloat(c.fadeNear)}, ${glslFloat(c.fadeFar)}, dist ) ) * uSectGroundLayers );
}
// The wind sheen's factor on a texel of shadow scale ds: bands drifting with the wind.
float sectSheen( vec3 p, vec3 v, float dist, float ds ) {
  vec2 q = vec2( dot( p.xz, vec2( ${wx}, ${wz} ) ) - uSectTime * ${glslFloat(s.speed)}, dot( p.xz, vec2( -${wz}, ${wx} ) ) * ${glslFloat(1 / s.stretch)} );
  float n = texture2D( tSectGroundNoise, q * ${inv} + ${vec2(s.offset)} ).b;
  float t = max( dot( v, uSectSun ), 0.0 );
  float f = ( 1.0 - smoothstep( ${glslFloat(s.fadeNear)}, ${glslFloat(s.fadeFar)}, dist ) ) * ds * uSectGroundLayers;
  return 1.0 + ( n - 0.5 ) * ${glslFloat(2 * s.amount)} * ( 1.0 + ${glslFloat(s.sunBoost)} * t * t ) * f;
}
`;
}

/**
 * GLSL: `float sectRockFar( vec3 p )`, the far rock layer's signed value (0 = none) at p, and
 * `float sectRockStreak( vec3 p )` (the range's water streaks).
 */
function rockFarGlsl(look: DetailLook, range: RangeLook): string {
  const r = look.rockFar;
  const n = DETAIL_NOISE.ground;
  return /* glsl */ `
// 3D value noise from one read: R and G of the ground noise are two slices (G = R moved by the
// slice offset), the lattice's y picking the pair. The top mip level, filtered (no derivatives).
float sectNoise3( vec3 x ) {
  vec3 i = floor( x );
  vec3 f = fract( x );
  f = f * f * ( 3.0 - 2.0 * f );
  vec2 s = mod( i.xz + ${vec2(n.offset)} * i.y, ${glslFloat(n.size)} ) + f.xz + 0.5;
  vec2 rg = textureLod( tSectGroundNoise, s * ${glslFloat(1 / n.size)}, 0.0 ).rg;
  return mix( rg.x, rg.y, f.y );
}
float sectRockFar( vec3 p ) {
  float a = sectNoise3( p * ${glslFloat(1 / r.scalesM[0])} );
  float b = 0.5;
  // A uniform: every pixel takes the same side (mid draws one octave).
  if ( uSectRockOctaves > 1.5 ) b = sectNoise3( p * ${glslFloat(1 / r.scalesM[1])} + vec3( 5.3, 1.7, 9.1 ) );
  float band = sin( ( p.y + ( ( a - 0.5 ) * 0.4 + ( b - 0.5 ) ) * ${glslFloat(r.band.warpM)} ) * ${glslFloat((2 * Math.PI) / r.band.periodM)} );
  return ( a - 0.5 ) * ${glslFloat(r.weights[0])} + ( b - 0.5 ) * ${glslFloat(r.weights[1])} + band * ${glslFloat(r.band.weight)};
}
${rockStreakGlsl(range)}`;
}

/**
 * GLSL: `float sectRockStreak( vec3 p )`, the range rock's dark water streaks (range-look.ts
 * RANGE_LOOK.rock.streaks), 0..1 with 1 fully dark: the 3D noise stretched up and down, so its low
 * values run down the faces. Needs sectNoise3.
 */
function rockStreakGlsl(range: RangeLook): string {
  const st = range.rock.streaks;
  const w = glslFloat(1 / st.widthM);
  return /* glsl */ `
float sectRockStreak( vec3 p ) {
  float n = sectNoise3( p * vec3( ${w}, ${glslFloat(1 / st.lengthM)}, ${w} ) + vec3( 3.1, 7.7, 1.9 ) );
  return 1.0 - smoothstep( ${glslFloat(st.hi)}, ${glslFloat(st.lo)}, n );
}
`;
}

/**
 * The vertex-shader GLSL a class needs besides vSectWorld: `pars` after `#include <common>`, `main`
 * after `#include <project_vertex>`. Paving passes its slab coordinates (uv1, TEXCOORD_1) to the
 * fragment shader as vSectUv1, v turned back (the glTF exporter wrote 1 - y); three declares uv1
 * itself only when a texture reads that channel. Tiles pass their tile UVs the same way. Empty for
 * rock and ground.
 */
export function detailVertexGlsl(kind: DetailClass): { pars: string; main: string } {
  if (kind !== "paving" && kind !== "tiles") return { pars: "", main: "" };
  return {
    pars: "#ifndef USE_UV1\nattribute vec2 uv1;\n#endif\nvarying vec2 vSectUv1;\n",
    main: "  vSectUv1 = vec2( uv1.x, 1.0 - uv1.y );\n",
  };
}

/**
 * GLSL of the tiles class (detailGlsl("tiles")): `vec3 sectTiles( vec3 col, vec3 texel )`, the
 * roof's tile courses on colour col (tileCourseFactor's shader twin). No uniforms.
 */
function tilesGlsl(look: DetailLook): string {
  const t = look.tiles;
  const m = tileMeans(look);
  const d = 1 - t.dark;
  const c = t.crease;
  return /* glsl */ `
varying vec2 vSectUv1;
// Roof tile courses on colour col; texel = the bake before the grade (its brightness sets k).
vec3 sectTiles( vec3 col, vec3 texel ) {
  vec2 q = vSectUv1;
  vec2 w = fwidth( q );
  float fu = abs( fract( q.x + 0.5 ) - 0.5 );
  float fv = fract( q.y );
  float k = clamp( 1.0 - ${glslFloat(t.kLum)} * sqrt( max( dot( texel, vec3( 0.2126, 0.7152, 0.0722 ) ), 0.0 ) ), ${glslFloat(t.kRange[0])}, ${glslFloat(t.kRange[1])} );
  float crest = 1.0 - smoothstep( 0.0, ${glslFloat(t.crest.width)}, fu );
  float crease = smoothstep( ${glslFloat(c[0])}, ${glslFloat(c[1])}, fu ) * ( 1.0 - smoothstep( ${glslFloat(c[2])}, ${glslFloat(c[3])}, fu ) );
  float lip = smoothstep( ${glslFloat(t.lip[0])}, ${glslFloat(t.lip[1])}, fv );
  float a = ( 1.0 + ${glslFloat(t.crest.lift)} * crest ) * ( 1.0 - ${glslFloat(d * t.creaseK)} * k * crease )
    / ( ${glslFloat(1 + t.crest.lift * m.crest)} - ${glslFloat(d * t.creaseK * m.crease)} * k );
  float b = ( 1.0 - ${glslFloat(d * t.lipK)} * k * lip ) / ( 1.0 - ${glslFloat(d * t.lipK * m.lip)} * k );
  a = mix( a, 1.0, smoothstep( ${glslFloat(t.fade[0])}, ${glslFloat(t.fade[1])}, w.x ) );
  b = mix( b, 1.0, smoothstep( ${glslFloat(t.fade[0])}, ${glslFloat(t.fade[1])}, w.y ) );
  return col * a * b;
}
`;
}

/**
 * GLSL of the paving class (detailGlsl("paving")): `vec2 sectSlab( vec2 q, out vec2 e )`, the slab
 * under q (column, row) and the distances to its sides, `float sectDetail( vec3 p )`, the marble
 * scan with every slab reading its own part of it (textureGrad on the continuous coordinates, so
 * the jump at a joint does not pick the smallest mip), and `vec3 sectPaving( vec3 col, vec3 p, vec3
 * n, float dist, float ds )`, the slab layer on colour col at world position p with face normal n,
 * dist metres away, on a texel of shadow scale ds.
 */
function pavingGlsl(look: DetailLook): string {
  const pv = look.paving;
  const [bw, rh] = pv.slabM;
  const l2 = look.layer2;
  const cells = DETAIL_NOISE.ground.cells;
  const t = pv.moss.tint;
  return /* glsl */ `
uniform sampler2D tSectDetail;
uniform float uSectDetailOn;
uniform sampler2D tSectGroundNoise;
varying vec2 vSectUv1;
vec3 sectHash3( vec2 p ) {
  vec3 q = fract( p.xyx * vec3( 0.1031, 0.1030, 0.0973 ) );
  q += dot( q, q.yxz + 33.33 );
  return fract( ( q.xxy + q.yzz ) * q.zyx );
}
// The slab under q (metres in the material's plane) as (column, row) of Blender's brick texture
// (every second row shifted half a slab); e = the distances to its vertical and horizontal sides.
vec2 sectSlab( vec2 q, out vec2 e ) {
  float row = floor( q.y * ${glslFloat(1 / rh)} );
  float x = q.x + ( mod( row, 2.0 ) < 0.5 ? ${glslFloat(bw * pv.offset)} : 0.0 );
  float col = floor( x * ${glslFloat(1 / bw)} );
  vec2 i = vec2( x - col * ${glslFloat(bw)}, q.y - row * ${glslFloat(rh)} );
  e = min( i, vec2( ${glslFloat(bw)}, ${glslFloat(rh)} ) - i );
  return vec2( col, row );
}
float sectDetail( vec3 p ) {
  vec2 e;
  vec2 c = vSectUv1 * ${glslFloat(1 / DETAIL_TILE_M.paving)};
  vec2 q = c + sectHash3( sectSlab( vSectUv1, e ) ).xy * 7.0;
  vec2 gx = dFdx( c );
  vec2 gy = dFdy( c );
  mat2 r = ${rotation(l2.angle)};
  float a = textureGrad( tSectDetail, q, gx, gy ).r;
  float b = textureGrad( tSectDetail, r * q * ${glslFloat(l2.scale)} + ${vec2(l2.offset)}, r * gx * ${glslFloat(l2.scale)}, r * gy * ${glslFloat(l2.scale)} ).r;
  return 0.5 + ( a - 0.5 ) * ${glslFloat(look.layer1)} + ( b - 0.5 ) * ${glslFloat(l2.weight)};
}
vec3 sectPaving( vec3 col, vec3 p, vec3 n, float dist, float ds ) {
  vec2 e;
  vec2 id = sectSlab( vSectUv1, e );
  vec2 w = max( fwidth( vSectUv1 ), vec2( 1e-5 ) );
  // Box-filtered joints: the pixel's footprint [e - w/2, e + w/2] against the joint [-J, J].
  vec2 cov = max( min( e + 0.5 * w, vec2( ${glslFloat(pv.jointM)} ) ) - max( e - 0.5 * w, vec2( ${glslFloat(-pv.jointM)} ) ), 0.0 ) / w;
  float joint = max( cov.x, cov.y );
  float up = smoothstep( ${glslFloat(pv.up[0])}, ${glslFloat(pv.up[1])}, abs( n.y ) );
  float jf = ( 1.0 - smoothstep( ${glslFloat(pv.joint.fadeNear)}, ${glslFloat(pv.joint.fadeFar)}, dist ) ) * up;
  float sf = ( 1.0 - smoothstep( ${glslFloat(pv.slab.fadeFar * 0.5)}, ${glslFloat(pv.slab.fadeFar)}, dist ) ) * up;
  vec3 h = sectHash3( id );
  col *= 1.0 + ( h.x - 0.5 ) * ${glslFloat(2 * pv.slab.value)} * sf;
  col *= mix( vec3( 1.0 ), vec3( ${glslFloat(1 + pv.slab.warm)}, 1.0, ${glslFloat(1 - pv.slab.warm)} ), ( h.y - 0.5 ) * 2.0 * sf );
  float wear = smoothstep( ${glslFloat(pv.wear.lo)}, ${glslFloat(pv.wear.hi)}, texture2D( tSectGroundNoise, p.xz * ${glslFloat(1 / (pv.wear.scaleM * cells))} + vec2( 0.41, 0.17 ) ).b );
  float damp = smoothstep( ${glslFloat(pv.moss.lo)}, ${glslFloat(pv.moss.hi)}, texture2D( tSectGroundNoise, p.xz * ${glslFloat(1 / (pv.moss.scaleM * cells))} + vec2( 0.23, 0.68 ) ).a );
  float keep = 1.0 - ${glslFloat(pv.wear.amount)} * wear;
  // The grime band, widened by the pixel's footprint so it greys rather than flickers far away.
  float gr = ( 1.0 - smoothstep( 0.0, ${glslFloat(pv.grime.widthM)} + max( w.x, w.y ), min( e.x, e.y ) ) ) * jf * keep;
  col *= 1.0 - ${glslFloat(pv.grime.dark)} * gr;
  col = mix( col, col * vec3( ${glslFloat(t[0])}, ${glslFloat(t[1])}, ${glslFloat(t[2])} ), clamp( damp * ${glslFloat(pv.moss.amount)} * max( joint * jf, 0.35 * gr ) * ( 1.25 - 0.5 * ds ), 0.0, 1.0 ) );
  col = mix( col, col * ${glslFloat(pv.joint.dark)}, joint * jf * keep );
  return col * ( 1.0 + ${glslFloat(pv.wear.lift)} * wear * sf );
}
`;
}

/**
 * GLSL for a detail class: the uniforms (tSectDetail, uSectDetailOn, the layers' textures and
 * switches) and `float sectDetail( vec3 p )`, the photo detail value (0.5 = none) at world position
 * p. Rock: three world projections blended by the flat face normal (from screen derivatives of p),
 * two layers each (6 reads, R). Ground: straight down (three is Y up), two layers (2 reads, G). The
 * moss channel (B) is not used. Then the layers: both classes get sectGroundTint and sectClump
 * through sectGroundLayers (4 reads), ground sectSheen (1 read), rock sectRockFar (1 read, 2 on
 * high). Paving: pavingGlsl (the marble scan per slab, 2 reads; the slab layer, 2 reads).
 */
export function detailGlsl(kind: DetailClass, look = DETAIL_LOOK, range: RangeLook = RANGE_LOOK): string {
  if (kind === "paving") return pavingGlsl(look);
  if (kind === "tiles") return tilesGlsl(look);
  const l2 = look.layer2;
  const inv = glslFloat(1 / (kind === "rock" ? DETAIL_TILE_M.rock : DETAIL_TILE_M.ground));
  const rot = rotation(l2.angle);
  const off = vec2(l2.offset);
  const s2 = glslFloat(l2.scale);
  const mix = `return 0.5 + ( a - 0.5 ) * ${glslFloat(look.layer1)} + ( b - 0.5 ) * ${glslFloat(l2.weight)};`;
  const shared = /* glsl */ `
uniform sampler2D tSectDetail;
uniform float uSectDetailOn;
uniform sampler2D tSectClump;
uniform float uSectGroundLayers;
uniform float uSectTime;
uniform vec3 uSectSun;
${groundTintGlsl(look)}${clumpGlsl(look)}${groundLayersGlsl(look)}`;
  if (kind === "ground") {
    return /* glsl */ `${shared}
float sectDetail( vec3 p ) {
  vec2 q = p.xz * ${inv};
  float a = texture2D( tSectDetail, q ).g;
  float b = texture2D( tSectDetail, ${rot} * q * ${s2} + ${off} ).g;
  ${mix}
}
`;
  }
  return /* glsl */ `${shared}
uniform float uSectRockFar;
uniform float uSectRockOctaves;
${rockFarGlsl(look, range)}
float sectDetail( vec3 p ) {
  vec3 n = cross( dFdx( p ), dFdy( p ) );
  n *= inversesqrt( max( dot( n, n ), 1e-30 ) );
  // The small floor keeps the weights defined on a degenerate (zero-area) fragment.
  vec3 w = pow( abs( n ), vec3( ${glslFloat(look.sharpness)} ) ) + 1e-4;
  w /= w.x + w.y + w.z;
  vec3 q = p * ${inv};
  mat2 r = ${rot};
  float a = texture2D( tSectDetail, q.zy ).r * w.x + texture2D( tSectDetail, q.xz ).r * w.y + texture2D( tSectDetail, q.xy ).r * w.z;
  float b = texture2D( tSectDetail, r * q.zy * ${s2} + ${off} ).r * w.x
    + texture2D( tSectDetail, r * q.xz * ${s2} + ${off} ).r * w.y
    + texture2D( tSectDetail, r * q.xy * ${s2} + ${off} ).r * w.z;
  ${mix}
}
`;
}

/**
 * GLSL that applies the detail and the layers to `diffuseColor` (after the grade, before fog),
 * needing vSectWorld, sectTexel (the texel colour before the grade) and the uniforms from
 * detailGlsl. No branch: the texture reads use screen derivatives (the far rock layer's one test
 * is on a uniform, and its reads name their mip level).
 */
export function detailApplyGlsl(kind: DetailClass, look = DETAIL_LOOK, range: RangeLook = RANGE_LOOK): string {
  if (kind === "tiles") return "  diffuseColor.rgb = sectTiles( diffuseColor.rgb, sectTexel );";
  const k = look[kind];
  const d = look.dark;
  if (kind === "paving") {
    const up = look.paving.up;
    return [
      "  {",
      "    vec3 sectDv = vSectWorld - cameraPosition;",
      "    float sectDd = max( length( sectDv ), 1e-3 );",
      "    vec3 sectPn = cross( dFdx( vSectWorld ), dFdy( vSectWorld ) );",
      "    sectPn *= inversesqrt( max( dot( sectPn, sectPn ), 1e-30 ) );",
      // The scan only on the slab tops: on a slab's side the plane coordinates run out along one axis.
      `    float sectDf = ( 1.0 - smoothstep( ${glslFloat(k.fadeNear)}, ${glslFloat(k.fadeFar)}, sectDd ) ) * uSectDetailOn * smoothstep( ${glslFloat(up[0])}, ${glslFloat(up[1])}, abs( sectPn.y ) );`,
      "    float sectDl = dot( diffuseColor.rgb, vec3( 0.2126, 0.7152, 0.0722 ) );",
      `    float sectDs = mix( ${glslFloat(d.floor)}, 1.0, smoothstep( ${glslFloat(d.lo)}, ${glslFloat(d.hi)}, sectDl ) );`,
      `    diffuseColor.rgb *= exp2( ( sectDetail( vSectWorld ) - 0.5 ) * ${glslFloat(k.gain)} * sectDf * sectDs );`,
      "    diffuseColor.rgb = sectPaving( diffuseColor.rgb, vSectWorld, sectPn, sectDd, sectDs );",
      "  }",
    ].join("\n");
  }
  const head = [
    "  {",
    "    vec3 sectDv = vSectWorld - cameraPosition;",
    "    float sectDd = max( length( sectDv ), 1e-3 );",
    `    float sectDf = ( 1.0 - smoothstep( ${glslFloat(k.fadeNear)}, ${glslFloat(k.fadeFar)}, sectDd ) ) * uSectDetailOn;`,
    "    float sectDl = dot( diffuseColor.rgb, vec3( 0.2126, 0.7152, 0.0722 ) );",
    `    float sectDs = mix( ${glslFloat(d.floor)}, 1.0, smoothstep( ${glslFloat(d.lo)}, ${glslFloat(d.hi)}, sectDl ) );`,
    `    diffuseColor.rgb *= exp2( ( sectDetail( vSectWorld ) - 0.5 ) * ${glslFloat(k.gain)} * sectDf * sectDs );`,
  ];
  if (kind === "ground") {
    const gr = range.ground;
    return [
      ...head,
      "    vec3 sectDu = sectDv / sectDd;",
      "    diffuseColor.rgb = sectGroundLayers( diffuseColor.rgb, vSectWorld, sectDu, sectDd ) * sectSheen( vSectWorld, sectDu, sectDd, sectDs );",
      // Far range lawns read as canopy (range-look.ts RANGE_LOOK.ground; sectRw from materials.ts).
      `    float sectGl = mix( ${glslFloat(gr.lump[0])}, ${glslFloat(gr.lump[1])}, texture2D( tSectGroundNoise, vSectWorld.xz * ${glslFloat(1 / (gr.lumpM * DETAIL_NOISE.ground.cells))} + vec2( 0.61, 0.37 ) ).b );`,
      `    vec3 sectGc = dot( diffuseColor.rgb, vec3( 0.2126, 0.7152, 0.0722 ) ) * ${glslFloat(gr.value)} * sectGl * ${glslVec3(unitTint(gr.color))};`,
      `    diffuseColor.rgb = mix( diffuseColor.rgb, sectGc, smoothstep( ${glslFloat(gr.near)}, ${glslFloat(gr.far)}, sectDd ) * sectRw * ${glslFloat(gr.amount)} );`,
      "  }",
    ].join("\n");
  }
  const r = look.rockFar;
  const g = look.greenRock;
  return [
    ...head,
    // Mossy rock (olive or green before the grade) gets the ground's clumps and patches.
    "    vec3 sectSq = sqrt( max( sectTexel, vec3( 0.0 ) ) );",
    "    float sectMx = max( sectSq.r, sectSq.g );",
    `    float sectGr = smoothstep( ${glslFloat(g.hue[0])}, ${glslFloat(g.hue[1])}, ( sectSq.g - sectSq.b ) / max( sectMx - sectSq.b, 1e-3 ) )`,
    `      * smoothstep( ${glslFloat(g.sat[0])}, ${glslFloat(g.sat[1])}, ( sectMx - sectSq.b ) / max( sectMx, 1e-3 ) ) * smoothstep( ${glslFloat(g.lit[0])}, ${glslFloat(g.lit[1])}, sectMx );`,
    "    diffuseColor.rgb = mix( diffuseColor.rgb, sectGroundLayers( diffuseColor.rgb, vSectWorld, sectDv / sectDd, sectDd ), sectGr );",
    `    float sectRf = smoothstep( ${glslFloat(r.fadeNear * 0.5)}, ${glslFloat(r.fadeNear)}, sectDd ) * ( 1.0 - smoothstep( ${glslFloat(r.fadeFar * 0.6)}, ${glslFloat(r.fadeFar)}, sectDd ) ) * uSectRockFar;`,
    `    diffuseColor.rgb *= exp2( sectRockFar( vSectWorld ) * ${glslFloat(r.gain)} * sectRf * mix( ${glslFloat(r.darkFloor)}, 1.0, smoothstep( ${glslFloat(d.lo)}, ${glslFloat(d.hi)}, sectDl ) ) );`,
    // The range's dark water streaks (range-look.ts RANGE_LOOK.rock.streaks; sectRw from materials.ts).
    `    diffuseColor.rgb *= 1.0 - ${glslFloat(range.rock.streaks.dark)} * sectRockStreak( vSectWorld ) * sectRf * sectRw;`,
    "  }",
  ].join("\n");
}

const programKeys = new Map<DetailClass, string>();

/**
 * A short tag of a class's detail GLSL for the material's program cache key: three keys a patched
 * built-in material's program by that key, not by its source, so a changed layer (a new constant,
 * or a hot reload) must change the key or the old program is reused.
 */
export function detailProgramKey(kind: DetailClass, look = DETAIL_LOOK): string {
  const cached = look === DETAIL_LOOK ? programKeys.get(kind) : undefined;
  if (cached) return cached;
  const v = detailVertexGlsl(kind);
  const src = detailGlsl(kind, look) + detailApplyGlsl(kind, look) + v.pars + v.main;
  let h = 0x811c9dc5;
  for (let i = 0; i < src.length; i++) h = Math.imul(h ^ src.charCodeAt(i), 0x01000193);
  const key = (h >>> 0).toString(36);
  if (look === DETAIL_LOOK) programKeys.set(kind, key);
  return key;
}
