/**
 * public/manifest.json (the installed app's name, colours and icons) matches the site: the sect's
 * name, the sect's ink as the theme colour (the same one the layout's theme-color meta gives), and
 * icon sizes that are the files' real sizes.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = join(__dirname, "..", "..");
const manifest = JSON.parse(readFileSync(join(ROOT, "public", "manifest.json"), "utf8")) as {
  name: string;
  short_name: string;
  description: string;
  theme_color: string;
  background_color: string;
  icons: { src: string; sizes: string }[];
};

/** A PNG's width and height, from its IHDR chunk. */
function pngSize(path: string): string {
  const b = readFileSync(path);
  return `${b.readUInt32BE(16)}x${b.readUInt32BE(20)}`;
}

describe("manifest.json", () => {
  it("names the sect", () => {
    expect(manifest.name).toContain("Sun Moon Divine Cult");
    expect(manifest.short_name).toBe("日月神教");
    expect(manifest.description).toContain("日月神教, the Sun Moon Divine Cult");
  });

  it("takes its colours from the sect's ink, as the layout's theme-color does", () => {
    const ink = readFileSync(join(ROOT, "src", "app", "sect", "sect.css"), "utf8").match(/--sect-ink:\s*(#[0-9a-f]{6})/i)?.[1];
    const layout = readFileSync(join(ROOT, "src", "app", "layout.tsx"), "utf8").match(/themeColor:\s*"(#[0-9a-f]{6})"/i)?.[1];
    expect(ink).toBeTruthy();
    expect(manifest.theme_color).toBe(ink);
    expect(manifest.background_color).toBe(ink);
    expect(layout).toBe(ink);
  });

  it("gives each icon its file's real size", () => {
    for (const icon of manifest.icons) {
      expect(pngSize(join(ROOT, "public", icon.src)), icon.src).toBe(icon.sizes);
    }
  });
});
