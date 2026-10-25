import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  appIconSvg,
  type Circle,
  crescentPath,
  LOGO_COLORS,
  LOGO_GEOMETRY,
  logoCircles,
  logoMarkup,
  logoSvg,
  roundedSquarePath,
  SMALL_GEOMETRY,
  smallCircles,
  TAB_RED,
  wornEdgePath,
} from "./logo";

const ROOT = path.resolve(__dirname, "../../..");
const PUBLIC = path.join(ROOT, "public");
const REPO = path.resolve(ROOT, "..");

/** A PNG's width and height, from its IHDR chunk. */
function pngSize(file: string): string {
  const b = readFileSync(file);
  return `${b.readUInt32BE(16)}x${b.readUInt32BE(20)}`;
}

type Pt = readonly [number, number];
interface Arc {
  from: Pt;
  to: Pt;
  r: number;
  large: number;
  sweep: number;
}

/** The arcs of a path made of M, L, A and Z commands (absolute). */
function arcs(d: string): Arc[] {
  const out: Arc[] = [];
  let at: Pt = [0, 0];
  for (const [, cmd, args] of d.matchAll(/([MLAZ])([^MLAZ]*)/g)) {
    const n = args.trim() ? args.trim().split(/[\s,]+/).map(Number) : [];
    if (cmd === "A") {
      const to: Pt = [n[5], n[6]];
      out.push({ from: at, to, r: n[0], large: n[3], sweep: n[4] });
      at = to;
    } else if (cmd !== "Z") at = [n[0], n[1]];
  }
  return out;
}

/** The centre a renderer puts an arc's circle on (SVG 1.1 implementation notes, F.6.5, rx = ry). */
function arcCentre({ from, to, r, large, sweep }: Arc): Pt {
  const hx = (from[0] - to[0]) / 2;
  const hy = (from[1] - to[1]) / 2;
  const h2 = hx * hx + hy * hy;
  const k = (large !== sweep ? 1 : -1) * Math.sqrt(Math.max(0, (r * r - h2) / h2));
  return [k * hy + (from[0] + to[0]) / 2, -k * hx + (from[1] + to[1]) / 2];
}

/** Whether the arc, drawn as a renderer draws it, passes the point of its circle at `angle`. */
function arcPasses(a: Arc, angle: number): boolean {
  const [cx, cy] = arcCentre(a);
  const wrap = (x: number) => ((x % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
  const a0 = Math.atan2(a.from[1] - cy, a.from[0] - cx);
  const a1 = Math.atan2(a.to[1] - cy, a.to[0] - cx);
  return a.sweep ? wrap(angle - a0) < wrap(a1 - a0) : wrap(a0 - angle) < wrap(a0 - a1);
}

const dist = (p: Pt, q: Pt) => Math.hypot(p[0] - q[0], p[1] - q[1]);

/** `p` reflected across the line through a and b. */
function mirror(p: Pt, a: Pt, b: Pt): Pt {
  const [dx, dy] = [b[0] - a[0], b[1] - a[1]];
  const t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy);
  const foot: Pt = [a[0] + t * dx, a[1] + t * dy];
  return [2 * foot[0] - p[0], 2 * foot[1] - p[1]];
}

/** Area two discs share. */
function lens(r1: number, r2: number, d: number): number {
  const a = r1 * r1 * Math.acos((d * d + r1 * r1 - r2 * r2) / (2 * d * r1));
  const b = r2 * r2 * Math.acos((d * d + r2 * r2 - r1 * r1) / (2 * d * r2));
  return a + b - 0.5 * Math.sqrt((-d + r1 + r2) * (d + r1 - r2) * (d - r1 + r2) * (d + r1 + r2));
}

/** The crescent's measurements, in units of the moon's radius R. */
function measure({ moon, bite, sun }: { moon: Circle; bite: Circle; sun: Circle }) {
  const R = moon[2];
  const d = dist([moon[0], moon[1]], [bite[0], bite[1]]);
  const belly = R - (bite[2] - d); // along the axis, away from the mouth
  const horn = Math.acos((R * R - bite[2] * bite[2] + d * d) / (2 * d * R));
  return {
    R,
    belly: belly / R,
    arcDeg: 360 - (2 * horn * 180) / Math.PI,
    sunInside: R - (dist([moon[0], moon[1]], [sun[0], sun[1]]) + sun[2]),
    gap: bite[2] - dist([bite[0], bite[1]], [sun[0], sun[1]]) - sun[2],
    crescentOverSun: (Math.PI * R * R - lens(R, bite[2], d)) / (Math.PI * sun[2] * sun[2]),
  };
}

describe("the logo", () => {
  it("is the sun in the crescent moon on the cinnabar seal, in the sect's colours", () => {
    for (const drawing of ["worn", "plain"] as const) {
      const svg = logoSvg(drawing);
      expect(svg).toContain(`fill="${LOGO_COLORS.cinnabar}"`);
      expect(svg).toContain(`fill="${LOGO_COLORS.paper}"`);
      expect(svg).toContain(`fill="${LOGO_COLORS.gold}"`);
    }
    // The small drawing's red is a shade lighter, for Chrome's dark tab strip.
    expect(logoSvg("small")).toContain(`fill="${TAB_RED}"`);
    // A 白文 seal: no frame, no rays, no lines at all. One red shape, the crescent, the sun.
    for (const drawing of ["small", "plain", "worn"] as const) {
      const m = logoMarkup(drawing);
      expect(m).not.toContain("stroke");
      expect(m.match(/<path/g)).toHaveLength(2);
      expect(m.match(/<circle/g)).toHaveLength(1);
    }
  });

  it("draws the crescent between the two circles' crossings", () => {
    const d = crescentPath([30, 34, 16], [37, 27, 13]);
    const [, ax, ay, bx, by] = d.match(/^M([\d.]+) ([\d.]+)A[^A]* ([\d.]+) ([\d.]+)A/)!.map(Number);
    for (const [x, y] of [
      [ax, ay],
      [bx, by],
    ]) {
      expect(Math.hypot(x - 30, y - 34)).toBeCloseTo(16, 1);
      expect(Math.hypot(x - 37, y - 27)).toBeCloseTo(13, 1);
    }
  });

  it("works its arc flags out from the circles, so the crescent never bulges the wrong way", () => {
    // The new seal (the bite's centre on the moon's side of the horns: its arc goes the long way), the
    // old one (the bite's centre past the horns: the short way), and the small drawing's cut horns.
    const cases: [string, Circle, Circle, number][] = [
      ["master", logoCircles().moon, logoCircles().bite, 0],
      ["old", [28.6, 35.4, 21.2], [37.4, 26.6, 17.4], 0],
      ["small", smallCircles().moon, smallCircles().bite, SMALL_GEOMETRY.trim],
    ];
    for (const [name, moon, bite, trim] of cases) {
      const [outer, inner] = arcs(crescentPath(moon, bite, trim));
      const belly = Math.atan2(moon[1] - bite[1], moon[0] - bite[0]);
      // Each arc lands on its own circle, not on that circle's mirror image across the chord...
      for (const [arc, [cx, cy]] of [
        [outer, moon],
        [inner, bite],
      ] as const) {
        const c = arcCentre(arc);
        expect(dist(c, [cx, cy]), name).toBeLessThan(0.05);
        expect(dist(c, [cx, cy]), name).toBeLessThan(dist(c, mirror([cx, cy], arc.from, arc.to)) / 4);
      }
      // ...and runs through the belly, not the mouth.
      expect(arcPasses(outer, belly), name).toBe(true);
      expect(arcPasses(inner, belly), name).toBe(true);
    }
    expect(arcs(crescentPath(logoCircles().moon, logoCircles().bite))[1].large).toBe(1);
    expect(arcs(crescentPath([28.6, 35.4, 21.2], [37.4, 26.6, 17.4]))[1].large).toBe(0);
  });

  it("is built from one module, 1/16 of the moon's radius, on one 45° line", () => {
    const g = LOGO_GEOMETRY;
    for (const n of [g.moon.r, g.bite.r, g.bite.off, g.sun.r, g.sun.off]) expect(Number.isInteger(n)).toBe(true);
    expect(g.moon.r).toBe(16);
    const c = logoCircles();
    for (const k of ["bite", "sun"] as const) {
      // up and to the right of the moon's centre at 45°
      expect(c[k][0] - c.moon[0]).toBeCloseTo(c.moon[1] - c[k][1], 9);
      expect(c[k][0]).toBeGreaterThan(c.moon[0]);
    }
  });

  it("has the proportions of a carved seal (craft rules 4, 7-13)", () => {
    const c = logoCircles();
    const m = measure(c);
    expect(m.belly).toBeGreaterThanOrEqual(0.45); // rule 4: a slim crescent...
    expect(m.belly).toBeLessThanOrEqual(0.6);
    expect(m.arcDeg).toBeGreaterThanOrEqual(220); // ...that shows 220-280° of the moon
    expect(m.arcDeg).toBeLessThanOrEqual(280);
    expect(m.sunInside).toBeGreaterThan(0); // rule 7: the sun lies inside the moon's circle
    expect(m.gap / (m.belly * m.R)).toBeGreaterThanOrEqual(0.5 * 0.85); // rule 8: gap = half the belly
    expect(m.gap / (m.belly * m.R)).toBeLessThanOrEqual(0.5 * 1.15);
    expect(m.crescentOverSun).toBeGreaterThanOrEqual(2.5); // rule 9: the moon leads
    expect(m.crescentOverSun).toBeLessThanOrEqual(4.5);
    // Rule 10: the moon's full circle centred across, lifted 1-3%.
    expect(Math.abs(c.moon[0] - 32) / 64).toBeLessThanOrEqual(0.015);
    expect((32 - c.moon[1]) / 64).toBeGreaterThanOrEqual(0.01);
    expect((32 - c.moon[1]) / 64).toBeLessThanOrEqual(0.03);
    // Rule 12: the moon's circle spans 0.78-0.84 of the seal.
    expect((2 * c.moon[2]) / 64).toBeGreaterThanOrEqual(0.78);
    expect((2 * c.moon[2]) / 64).toBeLessThanOrEqual(0.84);
    // Rule 13: the red margin (moon's circle to the seal's edge) is 0.8-1.2 times the gap.
    for (const margin of [c.moon[0] - c.moon[2], 64 - c.moon[0] - c.moon[2], c.moon[1] - c.moon[2], 64 - c.moon[1] - c.moon[2]]) {
      expect(margin / m.gap).toBeGreaterThanOrEqual(0.8 - 1e-9);
      expect(margin / m.gap).toBeLessThanOrEqual(1.2 + 1e-9);
    }
  });

  it("draws the tab's version from the same circles, fitted to the pixel grid (rules 3, 5, 18)", () => {
    const big = logoCircles(16);
    const small = smallCircles();
    const R = small.moon[2];
    expect(Math.abs(R / big.moon[2] - 1)).toBeLessThan(0.01);
    for (const k of ["moon", "bite", "sun"] as const) {
      // every centre within 0.02 R of the master's, relative to the moon (the whole may shift to fit)
      const db = dist([small[k][0] - small.moon[0], small[k][1] - small.moon[1]], [big[k][0] - big.moon[0], big[k][1] - big.moon[1]]);
      expect(db / R, k).toBeLessThanOrEqual(0.0201);
      expect(Math.abs(small[k][2] - big[k][2]) / R, k).toBeLessThanOrEqual(0.0201);
    }
    // Each horn is cut across where it is 1 px wide: no sub-pixel tip to smear.
    const nums = crescentPath(small.moon, small.bite, SMALL_GEOMETRY.trim).match(/-?[\d.]+/g)!.map(Number);
    const oA: Pt = [nums[0], nums[1]];
    const oB: Pt = [nums[7], nums[8]];
    const iB: Pt = [nums[9], nums[10]];
    const iA: Pt = [nums[16], nums[17]];
    expect(dist(oB, iB)).toBeCloseTo(1, 2);
    expect(dist(oA, iA)).toBeCloseTo(1, 2);
    // Big enough to read at 16 px.
    const m = measure(small);
    expect(m.belly * R).toBeGreaterThanOrEqual(2.5);
    expect(2 * small.sun[2]).toBeGreaterThanOrEqual(3);
    expect(m.gap).toBeGreaterThanOrEqual(1);
    expect(small.moon[0] - R).toBeGreaterThanOrEqual(1);
    expect(16 - small.moon[1] - R).toBeGreaterThanOrEqual(1);
  });

  it("keeps every edge inside its box, straight on the pixel grid when small", () => {
    const within = (d: string, max: number) => {
      const nums = d.match(/-?[\d.]+/g)!.map(Number);
      expect(Math.min(...nums)).toBeGreaterThanOrEqual(0);
      expect(Math.max(...nums)).toBeLessThanOrEqual(max);
    };
    within(wornEdgePath(), 64);
    within(roundedSquarePath(64, 2), 64);
    within(roundedSquarePath(16, 0.5), 16);
    expect(roundedSquarePath(16, 0.5)).toBe("M0.5 0H15.5A0.5 0.5 0 0 1 16 0.5V15.5A0.5 0.5 0 0 1 15.5 16H0.5A0.5 0.5 0 0 1 0 15.5V0.5A0.5 0.5 0 0 1 0.5 0Z");
  });

  it("is what public/favicon.svg holds (scripts/make-icons.mjs writes it)", () => {
    expect(readFileSync(path.join(PUBLIC, "favicon.svg"), "utf8").trim()).toBe(logoSvg("small"));
  });

  it("is what the README shows: the worn seal, cut through on light pages", () => {
    expect(readFileSync(path.join(REPO, ".github/readme/seal.svg"), "utf8").trim()).toBe(logoSvg("worn"));
    expect(readFileSync(path.join(REPO, ".github/readme/seal-light.svg"), "utf8").trim()).toBe(logoSvg("worn", { cut: "through" }));
  });

  it("stands upright in the top bar, at 18 px", () => {
    const css = readFileSync(path.join(ROOT, "src/app/sect/sect.css"), "utf8");
    const rule = (sel: string) => css.match(new RegExp(`\\${sel} \\{([^}]*)\\}`))![1];
    expect(rule(".sect-logo")).not.toMatch(/rotate/);
    expect(rule(".sect-toplinks-seal")).toMatch(/font-size: 1\.125rem/);
  });

  it("fills the maskable icon edge to edge, with the moon at 70% of the tile", () => {
    const svg = appIconSvg("maskable");
    expect(svg).toContain(`<rect width="64" height="64" fill="${LOGO_COLORS.cinnabar}"/>`);
    const k = Number(svg.match(/scale\(([\d.]+)\)/)![1]);
    expect((k * 2 * logoCircles().moon[2]) / 64).toBeCloseTo(0.7, 4);
    expect(appIconSvg("apple")).toContain(`fill="${LOGO_COLORS.ink}"`);
  });
});

describe("the icon files", () => {
  it("are their names' sizes", () => {
    for (const [file, size] of [
      ["favicon-16x16.png", "16x16"],
      ["favicon-32x32.png", "32x32"],
      ["apple-touch-icon.png", "180x180"],
      ["android-chrome-192x192.png", "192x192"],
      ["android-chrome-512x512.png", "512x512"],
      ["icons/icon-192x192.png", "192x192"],
      ["icons/icon-256x256.png", "256x256"],
      ["icons/icon-384x384.png", "384x384"],
      ["icons/icon-512x512.png", "512x512"],
      ["icons/maskable.png", "512x512"],
    ]) {
      expect(pngSize(path.join(PUBLIC, file)), file).toBe(size);
    }
  });

  it("put 16, 32 and 48 px images in the .ico", () => {
    for (const file of ["icon.ico", "favicon.ico"]) {
      const b = readFileSync(path.join(PUBLIC, file));
      expect(b.readUInt16LE(2), file).toBe(1);
      const n = b.readUInt16LE(4);
      expect([...Array(n)].map((_, i) => b.readUInt8(6 + 16 * i))).toEqual([16, 32, 48]);
    }
  });

  it("are the ones the layout links", () => {
    const layout = readFileSync(path.join(ROOT, "src", "app", "layout.tsx"), "utf8");
    const urls = [...layout.matchAll(/url: "(\/[^"]+\.(?:png|ico|svg))"/g)].map((m) => m[1]);
    expect(urls).toEqual(expect.arrayContaining(["/favicon.svg", "/favicon-32x32.png", "/favicon-16x16.png", "/icon.ico", "/apple-touch-icon.png"]));
    for (const url of urls) expect(existsSync(path.join(PUBLIC, url)), url).toBe(true);
  });
});
