/**
 * The site's logo: the sect's seal, a sun cradled in a crescent moon (日月, sun and moon: the sect is
 * 日月神教, and the site is named for Artemis, the moon goddess), in paper and gold on the cinnabar of
 * the seals stamped across the sect (app/sect/ornaments.tsx SealStamp).
 *
 * It is cut like a 白文 ("white-character") seal: the design is carved out of the red, so the red
 * margin is the border and there is no frame. Every size comes from one unit, a module: 1/16 of the
 * moon's radius. The seal is 41 modules across. The red margin equals the gap between sun and moon
 * (the carvers' rule for 白文 seals). The moon's full circle is centred across and lifted half a
 * module, and the sun sits wholly inside it. All three centres lie on one 45° line.
 * (Design: docs/decisions/README.md, 2026-10-24 "The logo is cut like a seal".)
 *
 * Three drawings of the same circles:
 * - "small" (a 16-unit box, 1 unit = 1 px at 16 px): the tab (16 and 32 px) and the top bar. The
 *   circles move at most 0.02 R to sit on whole pixels, the horn tips are cut where they are 1 px
 *   wide, the edge is a straight square on the pixel grid, and the red is 1.25% lighter so it keeps
 *   3:1 on Chrome's dark tab strip.
 * - "plain" (64-unit box): 48 to about 128 px, and the share image. Straight edge, 2-unit corners.
 * - "worn" (64-unit box): 180 px and up. The edge is ground into a few flat faces, each corner worn
 *   round by a different amount, like a stone seal face.
 *
 * scripts/make-icons.mjs draws every icon file from here; the top bar draws "small" inline
 * (ornaments.tsx SectLogo). Pure: strings only.
 */

/** The sect's colours (app/sect/sect.css). */
export const LOGO_COLORS = { ink: "#0e0c14", cinnabar: "#b8412d", paper: "#f5ecdc", gold: "#e9c77e" } as const;

/** The small drawing's red: cinnabar 1.25% lighter, 3.07:1 on Chrome's dark tab strip (#202124). */
export const TAB_RED = "#bd432e";

export type Circle = readonly [x: number, y: number, r: number];

const f = (n: number) => String(Math.round(n * 1000) / 1000);
const pt = ([x, y]: readonly [number, number]) => `${f(x)} ${f(y)}`;
const TAU = Math.PI * 2;
const wrap = (a: number) => ((a % TAU) + TAU) % TAU;

/** The master, in modules (1 module = R/16; the seal is `grid` modules across). */
export const LOGO_GEOMETRY = {
  grid: 41,
  /** Centred across, lifted half a module. */
  moon: { c: [20.5, 20], r: 16 },
  /** Offsets run along the 45° axis toward the mouth (up and right on screen). */
  bite: { off: 6, r: 13 },
  sun: { off: 4, r: 6 },
} as const;

/**
 * The small drawing, in px at 16 px. R is the master's; the centre and the ratios (of R) are the
 * pixel fit (r53: a search over about 9,000 placements for the least blur at 16 and 32 px), each
 * within 0.02 R of the master's.
 */
export const SMALL_GEOMETRY = {
  R: 6.244,
  c: [8.1975, 7.8013],
  bite: { off: 0.395, r: 0.8175 },
  sun: { off: 0.235, r: 0.37 },
  /** The horn tips are cut along a moon radius where the horn is this wide (px). */
  trim: 1,
} as const;

export interface LogoCircles {
  moon: Circle;
  bite: Circle;
  sun: Circle;
}

const AXIS = [Math.SQRT1_2, -Math.SQRT1_2] as const;

/** The master's circles in a box of side `side` (64 for the icon files). */
export function logoCircles(side = 64): LogoCircles {
  const g = LOGO_GEOMETRY;
  const k = side / g.grid;
  const [mx, my] = g.moon.c;
  const at = (off: number, r: number): Circle => [(mx + off * AXIS[0]) * k, (my + off * AXIS[1]) * k, r * k];
  return { moon: [mx * k, my * k, g.moon.r * k], bite: at(g.bite.off, g.bite.r), sun: at(g.sun.off, g.sun.r) };
}

/** The small drawing's circles, in its 16-unit box. */
export function smallCircles(): LogoCircles {
  const g = SMALL_GEOMETRY;
  const [cx, cy] = g.c;
  const at = (off: number, r: number): Circle => [cx + off * g.R * AXIS[0], cy + off * g.R * AXIS[1], r * g.R];
  return { moon: [cx, cy, g.R], bite: at(g.bite.off, g.bite.r), sun: at(g.sun.off, g.sun.r) };
}

/**
 * An arc's large-arc and sweep flags, from the geometry: the arc on the circle round `c` from p0 to
 * p1 that passes the angle `via`. Hard-coding them draws the crescent bulging the wrong way as soon as
 * the bite's centre crosses the line between the horns.
 */
function arcFlags(c: readonly [number, number], p0: readonly [number, number], p1: readonly [number, number], via: number) {
  const a0 = Math.atan2(p0[1] - c[1], p0[0] - c[0]);
  const a1 = Math.atan2(p1[1] - c[1], p1[0] - c[0]);
  const forward = wrap(a1 - a0);
  const sweep = wrap(via - a0) < forward ? 1 : 0; // 1: increasing angle (clockwise on screen)
  const len = sweep ? forward : TAU - forward;
  return `${len > Math.PI ? 1 : 0} ${sweep}`;
}

/**
 * A crescent: the disc `moon` with the disc `bite` taken out of it, as one path. With `trim` > 0, each
 * horn is cut along a radius of the moon where it is `trim` wide (the small drawing's tips, so they
 * don't smear into a blur). The arc flags are worked out from the circles, not assumed.
 */
export function crescentPath(moon: Circle, bite: Circle, trim = 0): string {
  const [mx, my, R] = moon;
  const [bx, by, rb] = bite;
  const d = Math.hypot(bx - mx, by - my);
  const ax = (bx - mx) / d;
  const ay = (by - my) / d;
  // From the moon's centre at angle psi off the axis: how far out the bite's far rim is, and so how
  // wide the crescent is there.
  const tIn = (psi: number) => d * Math.cos(psi) + Math.sqrt(Math.max(0, rb * rb - d * d * Math.sin(psi) ** 2));
  const width = (psi: number) => R - tIn(psi);
  let psi = Math.acos((R * R - rb * rb + d * d) / (2 * d * R)); // where the two rims cross
  if (trim > 0) {
    let lo = psi;
    let hi = Math.PI;
    for (let i = 0; i < 60; i++) {
      const mid = (lo + hi) / 2;
      if (width(mid) < trim) lo = mid;
      else hi = mid;
    }
    psi = hi;
  }
  const P = (s: number, t: number): [number, number] => {
    const cs = Math.cos(s);
    const sn = Math.sin(s);
    return [mx + (ax * cs - ay * sn) * t, my + (ax * sn + ay * cs) * t];
  };
  const oA = P(psi, R);
  const oB = P(-psi, R);
  const iA = P(psi, tIn(psi));
  const iB = P(-psi, tIn(psi));
  const belly = Math.atan2(-ay, -ax); // away from the mouth
  const outer = `A${f(R)} ${f(R)} 0 ${arcFlags([mx, my], oA, oB, belly)} ${pt(oB)}`;
  const inner = `A${f(rb)} ${f(rb)} 0 ${arcFlags([bx, by], iB, iA, belly)} ${pt(iA)}`;
  return trim > 0 ? `M${pt(oA)}${outer}L${pt(iB)}${inner}Z` : `M${pt(oA)}${outer}${inner}Z`;
}

/** A square of side `side` with corners rounded `r`, its straight sides on the box's edge. */
export function roundedSquarePath(side: number, r: number): string {
  const s = f(side);
  const e = f(side - r);
  const q = f(r);
  return `M${q} 0H${e}A${q} ${q} 0 0 1 ${s} ${q}V${e}A${q} ${q} 0 0 1 ${e} ${s}H${q}A${q} ${q} 0 0 1 0 ${e}V${q}A${q} ${q} 0 0 1 ${q} 0Z`;
}

/**
 * The worn edge, in the 64-unit box. The face is inset 0.6 so the wear can go both ways and never
 * leaves the box. Each side is ground into one or two flat faces: [where along the side, depth],
 * depth > 0 into the stone. They stray 0.35 to 0.75 units (0.6 to 1.2% of the side), deepest toward
 * the belly's corner. Corner radii run top-left, top-right, bottom-right, bottom-left (2.0 to 3.9% of
 * the side): the mouth's corner is the crispest, the belly's the most worn.
 */
export const LOGO_WEAR = {
  inset: 0.6,
  radii: [1.8, 1.3, 2.0, 2.5],
  sides: [
    [[21, -0.35], [44, 0.4]], // top, left to right
    [[30, 0.45]], // right, top to bottom
    [[25, -0.4], [47, 0.6]], // bottom, right to left
    [[17, 0.75], [41, -0.3]], // left, bottom to top
  ],
} as const;

/** The worn seal's outline in a box of side `side`. */
export function wornEdgePath(side = 64, wear = LOGO_WEAR): string {
  const [tl, tr, br, bl] = wear.radii;
  const lo = wear.inset;
  const hi = side - wear.inset;
  const run = hi - lo;
  const sides: { end: number; at: (a: number, o: number) => [number, number]; corner: string }[] = [
    { end: run - tr, at: (a, o) => [lo + a, lo + o], corner: `A${f(tr)} ${f(tr)} 0 0 1 ${f(hi)} ${f(lo + tr)}` },
    { end: run - br, at: (a, o) => [hi - o, lo + a], corner: `A${f(br)} ${f(br)} 0 0 1 ${f(hi - br)} ${f(hi)}` },
    { end: run - bl, at: (a, o) => [hi - a, hi - o], corner: `A${f(bl)} ${f(bl)} 0 0 1 ${f(lo)} ${f(hi - bl)}` },
    { end: run - tl, at: (a, o) => [lo + o, hi - a], corner: `A${f(tl)} ${f(tl)} 0 0 1 ${f(lo + tl)} ${f(lo)}` },
  ];
  let d = `M${f(lo + tl)} ${f(lo)}`;
  sides.forEach((s, i) => {
    for (const [a, o] of [...wear.sides[i]].sort((p, q) => p[0] - q[0])) d += `L${pt(s.at(a, o))}`;
    d += `L${pt(s.at(s.end, 0))}${s.corner}`;
  });
  return `${d}Z`;
}

export type LogoDrawing = "small" | "plain" | "worn";

export interface LogoOptions {
  /**
   * "paper" (the default) fills the crescent with paper, for dark grounds. "through" cuts it out of
   * the red so the page shows, like a real seal print: for light grounds.
   */
  cut?: "paper" | "through";
}

/** The logo's inner SVG markup (16-unit box for "small", else 64), without the <svg> element. */
export function logoMarkup(drawing: LogoDrawing = "worn", { cut = "paper" }: LogoOptions = {}): string {
  const c = LOGO_COLORS;
  const small = drawing === "small";
  const g = small ? smallCircles() : logoCircles(64);
  const edge = small ? roundedSquarePath(16, 0.5) : drawing === "plain" ? roundedSquarePath(64, 2) : wornEdgePath(64);
  const red = small ? TAB_RED : c.cinnabar;
  const crescent = crescentPath(g.moon, g.bite, small ? SMALL_GEOMETRY.trim : 0);
  const sun = `<circle cx="${f(g.sun[0])}" cy="${f(g.sun[1])}" r="${f(g.sun[2])}" fill="${c.gold}"/>`;
  if (cut === "through") return `<path d="${edge}${crescent}" fill="${red}" fill-rule="evenodd"/>${sun}`;
  return `<path d="${edge}" fill="${red}"/><path d="${crescent}" fill="${c.paper}"/>${sun}`;
}

/** The box a drawing is drawn in. */
export const logoBox = (drawing: LogoDrawing) => (drawing === "small" ? 16 : 64);

/** The logo as a standalone SVG file. */
export function logoSvg(drawing: LogoDrawing = "worn", opts: LogoOptions = {}): string {
  const b = logoBox(drawing);
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${b} ${b}">${logoMarkup(drawing, opts)}</svg>`;
}

const around = (k: number, inner: string) =>
  `<g transform="translate(32 32) scale(${Math.round(k * 1e6) / 1e6}) translate(-32 -32)">${inner}</g>`;

/**
 * The app icons, in the 64-unit box. "apple": the worn seal at 80% on the sect's ink (iOS rounds the
 * corners and fills transparency with black). "maskable": full bleed, the tile is the seal, with the
 * moon's circle at 70% of the tile so any launcher's mask keeps the emblem whole.
 */
export function appIconSvg(kind: "apple" | "maskable"): string {
  const c = LOGO_COLORS;
  let inner: string;
  if (kind === "apple") {
    inner = `<rect width="64" height="64" fill="${c.ink}"/>${around(0.8, logoMarkup("worn"))}`;
  } else {
    const g = logoCircles(64);
    const emblem =
      `<path d="${crescentPath(g.moon, g.bite)}" fill="${c.paper}"/>` +
      `<circle cx="${f(g.sun[0])}" cy="${f(g.sun[1])}" r="${f(g.sun[2])}" fill="${c.gold}"/>`;
    inner = `<rect width="64" height="64" fill="${c.cinnabar}"/>${around(0.7 / ((2 * g.moon[2]) / 64), emblem)}`;
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">${inner}</svg>`;
}
