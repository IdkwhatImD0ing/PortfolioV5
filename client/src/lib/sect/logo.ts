/**
 * The site's logo: the sect's seal, a sun cradled in a crescent moon (日月, sun and moon: the sect is
 * 日月神教, and the site is named for Artemis, the moon goddess), in paper and gold on the cinnabar
 * of the seals stamped across the sect (app/sect/ornaments.tsx SealStamp), its edge as rough as
 * theirs.
 *
 * Two drawings: the full seal (a paper frame inside the edge, a sunburst round the sun) for 180 px and
 * up, and a bold one with neither for the tab (16 to 48 px) and the top bar, where those would only
 * blur. scripts/make-icons.mjs draws every icon file from logoSvg(); the top bar draws the bold one
 * inline (ornaments.tsx SectLogo).
 *
 * Pure: strings only.
 */

/** The sect's colours (app/sect/sect.css). */
export const LOGO_COLORS = { ink: "#0e0c14", cinnabar: "#b8412d", paper: "#f5ecdc", gold: "#e9c77e" } as const;

/** SealStamp's rough square, in its 40-unit box. */
const SEAL_40: readonly (readonly [number, number])[] = [
  [3.6, 3.2], [12, 2.7], [20.4, 3.1], [29, 2.6], [36.8, 3.5], [37.2, 12], [36.9, 20.6], [37.4, 29],
  [36.5, 36.8], [28, 37.3], [19.6, 36.9], [11.2, 37.4], [3.1, 36.6], [2.7, 28.2], [3.2, 19.6], [2.6, 11.4],
];

const f = (n: number) => String(Math.round(n * 100) / 100);

/** The seal's edge in the logo's 64-unit box, spread from its centre to span `reach` of it (0..1). */
export function sealPath(reach: number): string {
  const k = (64 * reach) / 34.8; // the 40-unit seal is about 34.8 units across
  return `M${SEAL_40.map(([x, y]) => `${f(32 + (x - 20) * k)} ${f(32 + (y - 20) * k)}`).join("L")}Z`;
}

type Circle = readonly [x: number, y: number, r: number];

/**
 * A crescent: the disc `moon` with the disc `bite` taken out of it, as one path (the long way round
 * the moon's rim between the two circles' crossings, then back along the bite's rim).
 */
export function crescentPath(moon: Circle, bite: Circle): string {
  const [x1, y1, r1] = moon;
  const [x2, y2, r2] = bite;
  const dx = x2 - x1;
  const dy = y2 - y1;
  const d = Math.hypot(dx, dy);
  const a = (r1 * r1 - r2 * r2 + d * d) / (2 * d);
  const h = Math.sqrt(Math.max(0, r1 * r1 - a * a));
  const px = x1 + (a * dx) / d;
  const py = y1 + (a * dy) / d;
  const ax = px + (h * -dy) / d;
  const ay = py + (h * dx) / d;
  const bx = px - (h * -dy) / d;
  const by = py - (h * dx) / d;
  return `M${f(ax)} ${f(ay)}A${f(r1)} ${f(r1)} 0 1 1 ${f(bx)} ${f(by)}A${f(r2)} ${f(r2)} 0 0 0 ${f(ax)} ${f(ay)}Z`;
}

const GEOMETRY = {
  bold: { moon: [28.6, 35.4, 21.2], bite: [37.4, 26.6, 17.4], sun: [41.2, 22.9, 7.6] },
  full: { moon: [29.6, 34.4, 16.6], bite: [36.6, 27.4, 13.6], sun: [39.4, 24.6, 5] },
} as const satisfies Record<string, { moon: Circle; bite: Circle; sun: Circle }>;

/** A sunburst of slim pointed rays round the sun, as on the sun medallion of the gate's plaque. */
function sunburst([sx, sy]: Circle, r0 = 6.4, r1 = 10.2, half = 0.13): string {
  const p = (a: number, r: number) => `${f(sx + Math.cos(a) * r)} ${f(sy + Math.sin(a) * r)}`;
  let d = "";
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2;
    const len = i % 2 ? r1 * 0.86 : r1;
    d += `M${p(a - half, r0)}L${p(a, len)}L${p(a + half, r0)}Z`;
  }
  return d;
}

export interface LogoOptions {
  /** The tab's drawing: bigger, no frame, no rays. */
  bold?: boolean;
  /** A colour to fill the square behind the seal (the maskable and apple-touch icons), else none. */
  ground?: string | null;
  /** How much of the square the seal spans (0..1). */
  reach?: number;
}

/** The logo's inner SVG markup (the 64-unit box), without the <svg> element. */
export function logoMarkup({ bold = false, ground = null, reach = bold ? 1 : 0.96 }: LogoOptions = {}): string {
  const c = LOGO_COLORS;
  const g = bold ? GEOMETRY.bold : GEOMETRY.full;
  const parts: string[] = [];
  if (ground) parts.push(`<rect width="64" height="64" fill="${ground}"/>`);
  // The edge stroked in its own colour with round joins: rough, like a stamp, not jagged.
  parts.push(
    bold
      ? `<path d="${sealPath(reach)}" fill="${c.cinnabar}"/>`
      : `<path d="${sealPath(reach)}" fill="${c.cinnabar}" stroke="${c.cinnabar}" stroke-width=".9" stroke-linejoin="round"/>`,
  );
  if (!bold) {
    const inset = 32 - 32 * reach + 64 * reach * 0.105;
    const side = 64 - 2 * inset;
    parts.push(
      `<rect x="${f(inset)}" y="${f(inset)}" width="${f(side)}" height="${f(side)}" fill="none" stroke="${c.paper}" stroke-opacity=".5" stroke-width="1.1"/>`,
    );
  }
  // The emblem is drawn for a seal that spans the box; it scales with the seal.
  const s = reach / (bold ? 1 : 0.96);
  const emblem =
    `<path d="${crescentPath(g.moon, g.bite)}" fill="${c.paper}"/>` +
    `<circle cx="${g.sun[0]}" cy="${g.sun[1]}" r="${g.sun[2]}" fill="${c.gold}"/>` +
    (bold ? "" : `<path d="${sunburst(g.sun)}" fill="${c.gold}"/>`);
  parts.push(s === 1 ? emblem : `<g transform="translate(32 32) scale(${Math.round(s * 1000) / 1000}) translate(-32 -32)">${emblem}</g>`);
  return parts.join("");
}

/** The logo as a standalone SVG file. */
export function logoSvg(opts: LogoOptions = {}): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">${logoMarkup(opts)}</svg>`;
}
