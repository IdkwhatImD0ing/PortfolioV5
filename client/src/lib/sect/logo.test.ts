import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { crescentPath, LOGO_COLORS, logoMarkup, logoSvg, sealPath } from "./logo";

const ROOT = path.resolve(__dirname, "../../..");
const PUBLIC = path.join(ROOT, "public");

/** A PNG's width and height, from its IHDR chunk. */
function pngSize(file: string): string {
  const b = readFileSync(file);
  return `${b.readUInt32BE(16)}x${b.readUInt32BE(20)}`;
}

describe("the logo", () => {
  it("is the sun in the crescent moon on the cinnabar seal, in the sect's colours", () => {
    const svg = logoSvg();
    expect(svg).toContain(`fill="${LOGO_COLORS.cinnabar}"`);
    expect(svg).toContain(`fill="${LOGO_COLORS.paper}"`);
    expect(svg).toContain(`fill="${LOGO_COLORS.gold}"`);
    // The tab's drawing drops the frame and the sunburst, which would only blur at 16 px.
    const tab = logoMarkup({ bold: true });
    expect(tab).not.toContain("stroke-opacity");
    expect(tab.match(/<path/g)).toHaveLength(2);
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

  it("keeps the seal inside its box", () => {
    for (const reach of [0.6, 0.8, 1]) {
      const nums = sealPath(reach).match(/[\d.]+/g)!.map(Number);
      expect(Math.min(...nums)).toBeGreaterThanOrEqual(0);
      expect(Math.max(...nums)).toBeLessThanOrEqual(64);
    }
  });

  it("is what public/favicon.svg holds (scripts/make-icons.mjs writes it)", () => {
    expect(readFileSync(path.join(PUBLIC, "favicon.svg"), "utf8").trim()).toBe(logoSvg({ bold: true }));
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
