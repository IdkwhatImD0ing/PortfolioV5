import { describe, expect, it } from "vitest";
import { fogConstantsFromMeta, hazeLayerDepth, hexToLinear } from "./glsl";
import { gradeGlsl, gradeLinear, gradeLinearWith, lookFogConstants, SECT_LOOK, unitTint } from "./look";
import { parseMeta } from "./parse";
import {
  barkWeight,
  builtAt,
  capSaturation,
  createBuiltGrid,
  flattenPuff,
  foliageGlsl,
  foliageGradeParams,
  foliageGradeStatements,
  foliageLinear,
  groundGradeStatements,
  groundRangeLinear,
  growBuilt,
  hazeScaleAt,
  keepPuffShape,
  leafWeight,
  markBuiltTriangles,
  mossGate,
  packRangeAreas,
  RANGE_LOOK,
  RANGE_MAX_AREAS,
  rangeGlsl,
  rangeWeight,
  rockGlsl,
  rockGradeStatements,
  rockLinear,
  canopyVary,
  valueNoise,
  rockRangeLinear,
  type RangeArea,
} from "./range-look";
import type { CloudPuff, Vec3 } from "./types";

const luma = (c: Vec3) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
const count = (s: string, sub: string) => s.split(sub).length - 1;

/** HSV of a linear colour as the screen shows it (sRGB-encoded): hue in degrees, saturation, value. */
function screenHsv(c: Vec3): [number, number, number] {
  const e = c.map((v) => {
    const x = Math.min(Math.max(v, 0), 1);
    return x <= 0.0031308 ? 12.92 * x : 1.055 * Math.pow(x, 1 / 2.4) - 0.055;
  });
  const mx = Math.max(...e);
  const mn = Math.min(...e);
  const d = mx - mn;
  let h = 0;
  if (d > 1e-9) {
    if (mx === e[0]) h = ((e[1] - e[2]) / d) % 6;
    else if (mx === e[1]) h = (e[2] - e[0]) / d + 2;
    else h = (e[0] - e[1]) / d + 4;
  }
  return [(h * 60 + 360) % 360, mx > 0 ? d / mx : 0, mx];
}

// meta.json's areas (anchor, footprint), r45.
const AREAS: RangeArea[] = [
  { anchor: [0, 40, 0], footprint: 40 },
  { anchor: [-95, 70, -185], footprint: 45 },
  { anchor: [115, 95, -335], footprint: 50 },
];

// Baked texels before the grade (linear): a far pine card's sunlit pad, its shaded pad, a trunk, a
// peach blossom, sunlit sandstone and a mossy ledge line.
const PAD_SUN = hexToLinear("#3b4a26");
const PAD_SHADE = hexToLinear("#16241c");
const BARK = hexToLinear("#7a4a2c");
const BLOSSOM = hexToLinear("#e8a0b8");
const SANDSTONE = hexToLinear("#c8875a");
const MOSS = hexToLinear("#5f6a33");

describe("range areas", () => {
  it("packs each area as anchor + footprint + pad, the rest of the slots empty", () => {
    const p = packRangeAreas(AREAS);
    expect(p).toHaveLength(RANGE_MAX_AREAS);
    expect(p[0]).toEqual([0, 40, 0, 40 + RANGE_LOOK.areas.pad]);
    expect(p[2]).toEqual([115, 95, -335, 50 + RANGE_LOOK.areas.pad]);
    expect(p.slice(AREAS.length).every((a) => a.every((v) => v === 0))).toBe(true);
    expect(packRangeAreas([])).toHaveLength(RANGE_MAX_AREAS);
  });

  it("weighs the range 0 within an area's footprint + pad and 1 past the fade, smoothly between", () => {
    const { pad, fade } = RANGE_LOOK.areas;
    const at = (d: number): Vec3 => [d, 40, 0];
    expect(rangeWeight(at(0), AREAS)).toBe(0);
    expect(rangeWeight(at(40 + pad), AREAS)).toBe(0);
    expect(rangeWeight(at(40 + pad + fade), AREAS)).toBe(1);
    expect(rangeWeight(at(40 + pad + fade / 2), AREAS)).toBeCloseTo(0.5, 6);
    let last = 0;
    for (let d = 0; d <= 200; d += 5) {
      const w = rangeWeight(at(d), AREAS);
      expect(w).toBeGreaterThanOrEqual(last);
      last = w;
    }
    // Far from every stop, and with no areas at all: all range.
    expect(rangeWeight([600, 100, -900], AREAS)).toBe(1);
    expect(rangeWeight([0, 40, 0], [])).toBe(1);
  });

  it("emits the mask's GLSL: one uniform array, the list ends at its first empty slot", () => {
    const g = rangeGlsl();
    expect(g).toContain(`uniform vec4 uSectAreas[ ${RANGE_MAX_AREAS} ];`);
    expect(g).toContain("float sectRangeW( vec3 p )");
    expect(g).toContain("if ( a.w <= 0.0 ) break;");
    expect(g).not.toMatch(/NaN|undefined|Infinity/);
  });
});

describe("range foliage", () => {
  it("leaves the stops' foliage exactly as the grade had it", () => {
    for (const t of [PAD_SUN, PAD_SHADE, BARK, BLOSSOM]) {
      for (const dist of [10, 200, 900]) {
        foliageLinear(t, 0, dist).forEach((v, i) => expect(v).toBeCloseTo(gradeLinear(t)[i], 9));
      }
    }
    const p = foliageGradeParams(0);
    expect(p.tame).toBe(SECT_LOOK.grade.greenTame);
    expect(p.splitShadow).toBe(SECT_LOOK.grade.splitShadow);
    p.shadowTint.forEach((v, i) => expect(v).toBeCloseTo(unitTint(SECT_LOOK.grade.shadowTint)[i], 9));
  });

  it("turns the range's pine pads green, short of lime, and no darker", () => {
    for (const t of [PAD_SUN, PAD_SHADE]) {
      const before = gradeLinear(t);
      const after = foliageLinear(t, 1, 200);
      const [h, s] = screenHsv(after);
      expect(h, "hue").toBeGreaterThan(75);
      expect(h, "hue").toBeLessThan(125);
      expect(s, "saturation").toBeLessThan(0.6);
      expect(luma(after)).toBeGreaterThan(luma(before));
    }
    // The sunlit pad was olive-brown (the grade takes all of green's lead); now it is green.
    expect(screenHsv(gradeLinear(PAD_SUN))[0]).toBeLessThan(65);
  });

  it("holds the saturation cap on the square root, keeping the largest channel", () => {
    const lime: Vec3 = [0.05, 0.5, 0.01];
    const c = capSaturation(lime, 0.36);
    const q = c.map(Math.sqrt);
    expect((Math.max(...q) - Math.min(...q)) / Math.max(...q)).toBeCloseTo(0.36, 6);
    expect(c[1]).toBeCloseTo(0.5, 9);
    const grey: Vec3 = [0.2, 0.21, 0.19];
    expect(capSaturation(grey, 0.36)).toEqual(grey);
    expect(capSaturation(lime, 1)).toEqual(lime);
  });

  it("tells bark from leaves and blossom", () => {
    expect(barkWeight(BARK)).toBeGreaterThan(0.9);
    expect(barkWeight(PAD_SUN)).toBe(0);
    expect(barkWeight(BLOSSOM)).toBe(0);
    expect(leafWeight(PAD_SHADE)).toBe(1);
    expect(leafWeight(BARK)).toBe(0);
  });

  it("mutes far trunks to a dark green-grey, and only far ones on the range", () => {
    const { near, far, value, color, amount } = RANGE_LOOK.trunks;
    const p = foliageGradeParams(1);
    const graded = gradeLinearWith(BARK, SECT_LOOK.grade, p.tame, p.shadowTint, p.splitShadow);
    // Near: the cap only (bark is not a leaf, so no canopy tint).
    foliageLinear(BARK, 1, near - 1).forEach((v, i) => expect(v).toBeCloseTo(capSaturation(graded, RANGE_LOOK.foliage.satCap)[i], 9));
    const muted = foliageLinear(BARK, 1, far + 50);
    expect(luma(muted)).toBeLessThan(luma(graded));
    const [h] = screenHsv(muted);
    expect(h).toBeGreaterThan(70);
    expect(h).toBeLessThan(160);
    // amount of the way to the tint at value x the capped brightness.
    const capped = capSaturation(graded, RANGE_LOOK.foliage.satCap);
    const target = unitTint(color).map((v) => v * luma(capped) * value);
    muted.forEach((v, i) => expect(v).toBeCloseTo(capped[i] + (target[i] - capped[i]) * amount * barkWeight(BARK), 9));
    // Blossom keeps its pink.
    const pink = foliageLinear(BLOSSOM, 1, far + 50);
    expect(screenHsv(pink)[0]).toBeGreaterThan(300);
  });

  it("emits the foliage GLSL with the look's numbers, blending the grade by sectRw", () => {
    const g = foliageGlsl();
    for (const fn of ["vec3 sectSatCap( vec3 c, float cap )", "float sectLeaf( vec3 t )", "float sectBark( vec3 t )", "vec3 sectFoliageRange( vec3 c, vec3 t, float w, float dist )"]) {
      expect(count(g, fn), fn).toBe(1);
    }
    const st = foliageGradeStatements();
    expect(st).toContain("vec3 sectGraded = sectGradeWith( sectTexel, mix(");
    expect(st).toContain("sectRw");
    expect(st).not.toContain("float sectRw");
    expect(gradeGlsl()).toContain("vec3 sectGradeWith( vec3 c, float tame, vec3 shadowTint, float splitShadow )");
    for (const s of [g, st]) expect(s).not.toMatch(/NaN|undefined|Infinity/);
  });
});

describe("range rock and lawns", () => {
  it("makes sunlit range rock pale buff-grey instead of saturated orange, and leaves the stops' rock", () => {
    const graded = gradeLinear(SANDSTONE);
    const [, s0] = screenHsv(graded);
    const pale = rockLinear(graded, 1);
    const [h, s] = screenHsv(pale);
    expect(s0).toBeGreaterThan(0.4);
    expect(s).toBeLessThan(0.3);
    expect(s).toBeGreaterThan(0.12);
    expect(h).toBeGreaterThan(10);
    expect(h).toBeLessThan(45);
    expect(luma(pale)).toBeCloseTo(luma(graded), 9);
    rockLinear(graded, 0).forEach((v, i) => expect(v).toBeCloseTo(graded[i], 12));
    rockRangeLinear(SANDSTONE, 0).forEach((v, i) => expect(v).toBeCloseTo(graded[i], 9));
  });

  it("darkens sunlit range rock near the camera only (the slice critic's F3)", () => {
    const graded = gradeLinear(SANDSTONE);
    const n = RANGE_LOOK.rock.near;
    const far = rockLinear(graded, 1);
    const near = rockLinear(graded, 1, RANGE_LOOK, n.near - 10);
    expect(luma(near) / luma(far)).toBeCloseTo(n.k, 1);
    rockLinear(graded, 1, RANGE_LOOK, n.far + 10).forEach((v, i) => expect(v).toBeCloseTo(far[i], 12));
    rockLinear(graded, 0, RANGE_LOOK, 10).forEach((v, i) => expect(v).toBeCloseTo(graded[i], 12));
  });

  it("varies range canopy leaves in patches, and leaves bark and the stops alone (F9)", () => {
    const c = gradeLinear(PAD_SUN);
    const lum = [0, 37, 91, 160, 233, 301].map((x) => luma(canopyVary(c, PAD_SUN, [x * 7.3, 100, x * 3.1], 1)));
    expect(Math.max(...lum) / Math.min(...lum)).toBeGreaterThan(1.05);
    expect(Math.max(...lum) / Math.min(...lum)).toBeLessThan(1.5);
    canopyVary(c, PAD_SUN, [12, 0, 40], 0).forEach((v, i) => expect(v).toBeCloseTo(c[i], 12));
    canopyVary(c, BARK, [12, 0, 40], 1).forEach((v, i) => expect(v).toBeCloseTo(c[i], 12));
    for (const x of [0.3, 1.7, 5.5]) expect(valueNoise(x, x * 2)).toBeGreaterThanOrEqual(0);
    expect(count(foliageGlsl(), "vec3 sectCanopyVary( vec3 c, vec3 t, vec3 p, float w )")).toBe(1);
  });

  it("keeps mossy ledge lines green on range rock", () => {
    expect(mossGate(MOSS)).toBeGreaterThan(0.9);
    expect(mossGate(SANDSTONE)).toBe(0);
    const before = gradeLinear(MOSS);
    const after = rockRangeLinear(MOSS, 1);
    expect(after[1] - Math.max(after[0], after[2])).toBeGreaterThan(before[1] - Math.max(before[0], before[2]));
    expect(screenHsv(after)[0]).toBeGreaterThan(screenHsv(before)[0]);
  });

  it("greens range lawns only past the grass tufts' reach", () => {
    const lawn = hexToLinear("#6a7a3a");
    const g = RANGE_LOOK.ground.tame;
    groundRangeLinear(lawn, 1, g.near - 1).forEach((v, i) => expect(v).toBeCloseTo(gradeLinear(lawn)[i], 12));
    groundRangeLinear(lawn, 0, 500).forEach((v, i) => expect(v).toBeCloseTo(gradeLinear(lawn)[i], 12));
    const far = groundRangeLinear(lawn, 1, g.far + 10);
    expect(screenHsv(far)[0]).toBeGreaterThan(screenHsv(gradeLinear(lawn))[0] + 5);
  });

  it("emits the rock and lawn GLSL", () => {
    const r = rockGlsl();
    expect(count(r, "float sectMossGate( vec3 t )")).toBe(1);
    expect(count(r, "vec3 sectRockRange( vec3 c, float w, float dist )")).toBe(1);
    const rs = rockGradeStatements();
    expect(rs.indexOf("sectMossGate( sectTexel )")).toBeLessThan(rs.indexOf("sectGradeWith("));
    expect(rs.indexOf("sectGradeWith(")).toBeLessThan(rs.indexOf("sectRockRange("));
    expect(groundGradeStatements()).toContain("length( vSectWorld - cameraPosition )");
    for (const s of [r, rs, groundGradeStatements()]) expect(s).not.toMatch(/NaN|undefined|Infinity/);
  });

  it("gradeLinearWith with the grade's own numbers is the grade", () => {
    const g = SECT_LOOK.grade;
    for (const t of [PAD_SUN, SANDSTONE, MOSS]) {
      gradeLinearWith(t, g, g.greenTame, unitTint(g.shadowTint), g.splitShadow ?? g.split).forEach((v, i) => expect(v).toBeCloseTo(gradeLinear(t)[i], 12));
    }
  });
});

describe("haze per stop", () => {
  const holds = [
    { id: "gate", frame: 93 },
    { id: "mirror", frame: 217 },
    { id: "summit", frame: 1647 },
    { id: "nowhere", frame: 500 },
  ];
  const H = RANGE_LOOK.haze.holds;

  it("takes each hold's value at its frame and blends smoothly between", () => {
    expect(hazeScaleAt(93, holds)).toBe(H.gate);
    expect(hazeScaleAt(1, holds)).toBe(H.gate);
    expect(hazeScaleAt(217, holds)).toBe(H.mirror);
    expect(hazeScaleAt(1700, holds)).toBe(H.summit);
    expect(hazeScaleAt(155, holds)).toBeCloseTo((H.gate + H.mirror) / 2, 9);
    let last = 0;
    for (let f = 1; f <= 1729; f += 7) {
      const s = hazeScaleAt(f, holds);
      expect(s).toBeGreaterThanOrEqual(last);
      last = s;
    }
    expect(hazeScaleAt(500, [])).toBe(1);
  });

  it("grows with the stops' height (their air is thinner in the height model)", () => {
    const order = ["gate", "mirror", "forge", "arena", "mission", "library", "steles", "scroll", "formation", "abode", "summit"];
    for (let i = 1; i < order.length; i++) expect(H[order[i]]).toBeGreaterThan(H[order[i - 1]]);
    expect(H.gate).toBeGreaterThan(1);
  });

  it("adds the extra haze only beyond the clear distance, so the stops' halls keep the film's", () => {
    const meta = parseMeta({ fog: { color: "#84889e", density: 0.0003, baseY: 100, falloff: 220 }, waterfalls: [], hotspots: [] });
    const c = lookFogConstants(meta);
    const film = fogConstantsFromMeta(meta);
    expect(film.hazeClear).toBe(0);
    expect(c.hazeClear).toBe(SECT_LOOK.haze.clear);
    for (const t of [10, 40, c.hazeClear]) expect(hazeLayerDepth(c, 150, -0.1, t, 4)).toBeCloseTo(hazeLayerDepth(c, 150, -0.1, t), 12);
    const one = hazeLayerDepth(c, 150, 0, 500);
    const four = hazeLayerDepth(c, 150, 0, 500, 4);
    expect(four).toBeGreaterThan(one * 3);
    expect(four).toBeLessThan(one * 4);
    expect(hazeLayerDepth(c, 150, 0, 500, 1)).toBeCloseTo(one, 12);
  });
});

describe("mist as layers", () => {
  const puff = (c: Vec3, axes: [Vec3, Vec3, Vec3], kind?: string): CloudPuff => ({ c, axes, density: 0.5, ...(kind ? { kind } : {}) });
  const reach = (p: CloudPuff, e: Vec3) => Math.sqrt(p.axes.reduce((s, a) => s + (a[0] * e[0] + a[1] * e[1] + a[2] * e[2]) ** 2, 0));
  const m = RANGE_LOOK.mist;
  const len = Math.hypot(m.wind[0], m.wind[1]);
  const wind: Vec3 = [m.wind[0] / len, 0, m.wind[1] / len];

  it("flattens a round puff and stretches it along the wind, keeping centre and density", () => {
    const round = puff([200, 150, -600], [[20, 0, 0], [0, 20, 0], [0, 0, 20]], "mist.band");
    const flat = flattenPuff(round);
    expect(flat.c).toEqual(round.c);
    expect(flat.density).toBe(round.density);
    expect(flat.kind).toBe("mist.band");
    expect(reach(flat, [0, 1, 0])).toBeCloseTo(20 * m.flat, 9);
    expect(reach(flat, wind)).toBeCloseTo(20 * m.stretch, 9);
    expect(reach(flat, [-wind[2], 0, wind[0]])).toBeCloseTo(20 * m.across, 9);
  });

  it("leaves Ice-Fire Island's steam and the opening bank as they were", () => {
    const steam = puff([m.keep.xz[0] + 5, m.keep.aboveY + 20, m.keep.xz[1]], [[3, 0, 0], [0, 3, 0], [0, 0, 3]]);
    expect(keepPuffShape(steam, [])).toBe(true);
    expect(flattenPuff(steam)).toBe(steam);
    // A tagged mist puff there is mist (only the untagged steam is kept).
    expect(keepPuffShape({ ...steam, kind: "mist.isle" }, [])).toBe(false);
    const bank = puff([0, 20, 300], [[30, 0, 0], [0, 15, 0], [0, 0, 30]]);
    expect(keepPuffShape(bank, [[0, 25, 280]])).toBe(true);
    expect(keepPuffShape(bank, [[0, 25, -400]])).toBe(false);
  });
});

describe("built mask", () => {
  const b = RANGE_LOOK.built;
  const flat = (x: number, z: number, y = 100, size = 1): number[] => [x, y, z, x + size, y, z, x, y, z + size];
  const src = (array: number[]) => ({ array, stride: 3, offset: 0, scale: 1 });

  it("covers the areas' anchors with a margin, in cells of cellM metres", () => {
    const g = createBuiltGrid(AREAS);
    expect(g.cell).toBe(b.cellM);
    expect(g.x0).toBe(-95 - b.marginM);
    expect(g.z0).toBe(-335 - b.marginM);
    expect(g.x0 + g.nx * g.cell).toBeGreaterThanOrEqual(115 + b.marginM);
    expect(g.z0 + g.nz * g.cell).toBeGreaterThanOrEqual(0 + b.marginM);
    expect(g.mask).toHaveLength(g.nx * g.nz);
    expect(createBuiltGrid([]).mask).toHaveLength(1);
  });

  it("marks the cells under upward-facing built triangles only, then grows them", () => {
    const g = createBuiltGrid(AREAS);
    // A tread (flat, either winding), a riser (vertical), and a triangle outside the grid.
    const tread = flat(10, -50);
    const back = [tread[0], tread[1], tread[2], tread[6], tread[7], tread[8], tread[3], tread[4], tread[5]];
    const riser = [40, 100, -50, 41, 100, -50, 40, 101, -50];
    const outside = flat(5000, 5000);
    expect(markBuiltTriangles(g, src([...tread, ...back, ...riser, ...outside]), null, 0, 4)).toBe(2);
    growBuilt(g);
    expect(builtAt(g, 10.5, -49.5)).toBe(1);
    expect(builtAt(g, 40.5, -50)).toBe(0);
    // Grown by `grow` cells, not more.
    expect(builtAt(g, 10.5 + b.grow * b.cellM, -49.5)).toBe(1);
    expect(builtAt(g, 10.5 + (b.grow + 1.5) * b.cellM, -49.5)).toBe(0);
    expect(builtAt(g, 1e5, 0)).toBe(0);
  });

  it("reads quantized, interleaved positions through the mesh's matrix, and indices", () => {
    const g = createBuiltGrid(AREAS);
    // Two values of padding per vertex (stride 5), positions as 16-bit fractions of 1.
    const q = (v: number) => Math.round(v * 32767);
    const array = [0, 0, q(0), q(0), q(0), 0, 0, q(1), q(0), q(0), 0, 0, q(0), q(0), q(1)];
    // Matrix: scale 4, then move to (20, 100, -80) (column-major).
    const m = [4, 0, 0, 0, 0, 4, 0, 0, 0, 0, 4, 0, 20, 100, -80, 1];
    expect(markBuiltTriangles(g, { array, stride: 5, offset: 2, scale: 1 / 32767 }, [0, 1, 2], 0, 1, m)).toBe(1);
    growBuilt(g);
    expect(builtAt(g, 21, -79)).toBe(1);
    expect(builtAt(g, 0.5, 0.5)).toBe(0);
  });

  it("emits sectBuilt with its texture and box", () => {
    const g = rangeGlsl();
    expect(g).toContain("uniform sampler2D tSectBuilt;");
    expect(g).toContain("uniform vec4 uSectBuiltBox;");
    expect(g).toContain("float sectBuilt( vec3 p )");
  });
});
