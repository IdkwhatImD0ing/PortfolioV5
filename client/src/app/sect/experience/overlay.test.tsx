/**
 * The overlays that show what the free look found: the hover label (name, Chinese name and a line
 * about the thing, for every kind of hotspot) and the Recentre button for a view turned round.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { hotspotLabel, type HotspotLabel } from "@/lib/sect/content";
import { HoverLabel, placeHoverLabel, RecentreButton } from "./overlay";

const ENTITIES: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', "#x27": "'", "#39": "'", nbsp: " " };
const textOf = (html: string) =>
  html
    .replace(/<[^>]+>/g, " ")
    .replace(/&(amp|lt|gt|quot|#x27|#39|nbsp);/g, (_, e: string) => ENTITIES[e])
    .replace(/\s+/g, " ")
    .trim();
const squash = (s: string) => s.replace(/\s+/g, " ").trim();

const label = (l: HotspotLabel | null) => renderToStaticMarkup(<HoverLabel label={l} />);
const button = (visible: boolean) => renderToStaticMarkup(<RecentreButton visible={visible} onRecentre={() => {}} />);

const meta = JSON.parse(readFileSync(path.resolve(__dirname, "../../../../public/sect/full/meta.json"), "utf8")) as {
  hotspots: { id: string; label?: string }[];
};

describe("HoverLabel", () => {
  it("shows the title, the Chinese name and the blurb", () => {
    const html = label({ title: "Dispatch AI", zh: "传令符", blurb: "Talisman · ★ First place" });
    const text = textOf(html);
    expect(text).toContain("Dispatch AI");
    expect(text).toContain("传令符");
    expect(text).toContain("Talisman · ★ First place");
    // The Chinese name is marked as Chinese; the blurb is cut to two lines.
    expect(html).toContain('lang="zh"');
    expect(html.indexOf('lang="zh"')).toBeLessThan(html.indexOf("传令符"));
    expect(html).toContain("line-clamp-2");
  });

  it("is empty with nothing hovered, and leaves out parts a label does not have", () => {
    expect(textOf(label(null))).toBe("");
    const html = label({ title: "Gate lions" });
    expect(textOf(html)).toBe("Gate lions");
    expect(html).not.toContain('lang="zh"');
  });

  it("shows the label of every hotspot in the scene", () => {
    const kinds = new Set<string>();
    for (const h of meta.hotspots) {
      const l = hotspotLabel(h.id, h.label);
      const text = textOf(label(l));
      expect(text, h.id).toContain(squash(l.title));
      if (l.zh) expect(text, h.id).toContain(l.zh);
      if (l.blurb) expect(text, h.id).toContain(squash(l.blurb));
      kinds.add(h.id.split(":")[0]);
    }
    // Every kind of item is in the scene. Items carry no Chinese name (the area's would repeat it); the moon has its own.
    for (const kind of ["project", "hackathon", "role", "school", "skills", "arch", "fact", "resume", "moon"]) {
      expect(kinds.has(kind), kind).toBe(true);
      const id = meta.hotspots.find((h) => h.id.split(":")[0] === kind)!.id;
      const l = hotspotLabel(id);
      if (kind === "moon") expect(l.zh).toBeTruthy();
      else expect(l.zh, id).toBeUndefined();
    }
    // An area's own hotspot names the place, in both languages, with its summary.
    const forge = hotspotLabel("forge");
    expect(forge.zh).toBeTruthy();
    expect(forge.blurb).toBeTruthy();
  });
});

describe("RecentreButton", () => {
  it("is there only while the view is turned round, with a label that says what it does", () => {
    expect(button(false)).toBe("");
    const html = button(true);
    expect(html).toContain('type="button"');
    expect(html).toContain('aria-label="Recentre the view"');
    expect(textOf(html)).toContain("Recentre");
  });
});

describe("placeHoverLabel", () => {
  const view = { w: 1600, h: 900 };
  const label = { w: 240, h: 60 };
  // A content panel up at a stop, on the right of the window.
  const panel = { left: 1150, top: 200, right: 1560, bottom: 700 };
  const overlaps = (x: number, y: number, b: typeof panel, gap = 0) =>
    x - label.w / 2 < b.right + gap && x + label.w / 2 > b.left - gap && y - label.h < b.bottom + gap && y > b.top - gap;

  it("keeps the label over its anchor when nothing is in the way", () => {
    expect(placeHoverLabel([800, 400], label, view, [panel])).toEqual([800, 400]);
  });

  it("keeps it inside the window, as before", () => {
    expect(placeHoverLabel([20, 10], label, view)).toEqual([128, 68]);
    expect(placeHoverLabel([1590, 899], label, view)).toEqual([1472, 892]);
  });

  it("moves a label that would cover the panel to the panel's near side, clear by the gap", () => {
    // The abode waterfall case: the label's right side runs about 70 px into the panel.
    const [x, y] = placeHoverLabel([panel.left + 70 - label.w / 2, 450], label, view, [panel]);
    expect(y).toBe(450);
    expect(x + label.w / 2).toBeLessThanOrEqual(panel.left - 12);
    expect(x + label.w / 2).toBeGreaterThan(panel.left - 14);
    expect(overlaps(x, y, panel, 12)).toBe(false);
  });

  it("takes the shortest way out: above a wide, low panel", () => {
    const wide = { left: 100, top: 700, right: 1500, bottom: 880 };
    const [x, y] = placeHoverLabel([800, 720], label, view, [wide]);
    expect(x).toBe(800);
    expect(y).toBeLessThanOrEqual(wide.top - 12);
    expect(overlaps(x, y, wide, 12)).toBe(false);
  });

  it("never pushes the label out of the window to clear a panel", () => {
    // A panel filling the window: no way out, so the label stays put (inside the window).
    const full = { left: 0, top: 0, right: 1600, bottom: 900 };
    expect(placeHoverLabel([800, 400], label, view, [full])).toEqual([800, 400]);
  });

  it("clears every panel when two are up during a cross-fade", () => {
    const left = { left: 40, top: 200, right: 450, bottom: 700 };
    const [x, y] = placeHoverLabel([480, 400], label, view, [left, panel]);
    expect(overlaps(x, y, left, 12)).toBe(false);
    expect(overlaps(x, y, panel, 12)).toBe(false);
    expect(x - label.w / 2).toBeGreaterThanOrEqual(8);
    expect(x + label.w / 2).toBeLessThanOrEqual(view.w - 8);
  });
});
