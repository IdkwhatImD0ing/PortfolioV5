/**
 * The graphics picker (loading screen and overlay popover), the loading screen around it, the
 * overlay's graphics button and its place beside the sound toggle.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Tier } from "@/lib/sect/runtime";
import type { MusicEngine } from "./experience/music-engine";
import { QualityButton } from "./experience/overlay";
import { SoundToggle } from "./experience/sound-toggle";
import { LoadingScreen } from "./loading-screen";
import { QUALITY_HINT, QualityPicker, QualityPickerSpace } from "./quality-picker";

const ENTITIES: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', "#x27": "'", "#39": "'", nbsp: " " };
const textOf = (html: string) =>
  html
    .replace(/<[^>]+>/g, " ")
    .replace(/&(amp|lt|gt|quot|#x27|#39|nbsp);/g, (_, e: string) => ENTITIES[e])
    .replace(/\s+/g, " ")
    .trim();

const picker = (tier: Tier, recommended: Tier, layout: "row" | "column" = "row") =>
  renderToStaticMarkup(<QualityPicker tier={tier} recommended={recommended} onPick={() => {}} layout={layout} />);

/** The radio inputs in document order: value, name, checked. */
function radios(html: string): { value: string; name: string; checked: boolean }[] {
  return [...html.matchAll(/<input[^>]*>/g)].map(([tag]) => ({
    value: /value="([^"]*)"/.exec(tag)?.[1] ?? "",
    name: /name="([^"]*)"/.exec(tag)?.[1] ?? "",
    checked: /\schecked(=""|\s|>|\/)/.test(tag),
  }));
}

/** Each cell's text (its label), in order. */
function cells(html: string): string[] {
  return [...html.matchAll(/<label[^>]*>([\s\S]*?)<\/label>/g)].map((m) => textOf(m[1]));
}

describe("QualityPicker", () => {
  it("is a fieldset named Graphics with three radios, Low to High", () => {
    for (const layout of ["row", "column"] as const) {
      const html = picker("mid", "mid", layout);
      expect(html).toMatch(/^<div[^>]*><fieldset|^<fieldset/);
      expect(html).toMatch(/<legend[^>]*>Graphics<\/legend>/);
      const r = radios(html);
      expect(r.map((x) => x.value)).toEqual(["low", "mid", "high"]);
      expect(r.every((x) => x.name === "sect-quality")).toBe(true);
      expect(html.match(/type="radio"/g)).toHaveLength(3);
      expect(cells(html).map((c) => c.split(",")[0].trim())).toEqual(["Low", "Medium", "High"]);
    }
  });

  it("checks the given tier", () => {
    for (const t of ["low", "mid", "high"] as const) {
      const r = radios(picker(t, "mid"));
      expect(r.filter((x) => x.checked).map((x) => x.value)).toEqual([t]);
    }
  });

  it("tags only the recommended tier, and its name says so", () => {
    for (const rec of ["low", "mid", "high"] as const) {
      const html = picker("low", rec);
      expect(html.match(/Recommended/g)).toHaveLength(1);
      const c = cells(html);
      const i = ["low", "mid", "high"].indexOf(rec);
      expect(c[i]).toMatch(/, Recommended$/);
      expect(c.filter((x) => x.includes("Recommended"))).toHaveLength(1);
    }
  });

  it("warns only when the checked tier is above the recommended one", () => {
    expect(textOf(picker("high", "mid"))).toContain(QUALITY_HINT);
    expect(textOf(picker("mid", "low"))).toContain(QUALITY_HINT);
    expect(textOf(picker("mid", "mid"))).not.toContain(QUALITY_HINT);
    expect(textOf(picker("low", "high"))).not.toContain(QUALITY_HINT);
    // Every radio is described by the hint's row (present even when empty).
    const html = picker("mid", "mid");
    const id = /<p id="([^"]+)"/.exec(html)?.[1];
    expect(id).toBeTruthy();
    expect(html.match(new RegExp(`aria-describedby="${id}"`, "g"))).toHaveLength(3);
  });

  it("keeps its copy short and free of dashes", () => {
    for (const html of [picker("high", "low"), picker("low", "high", "column")]) {
      expect(html).not.toContain("—");
      expect(html).not.toContain("–");
    }
    expect(QUALITY_HINT).toBe("May run slowly on this device.");
  });

  it("takes another group name (two pickers on the page must not share one)", () => {
    const html = renderToStaticMarkup(<QualityPicker tier="mid" recommended="mid" onPick={() => {}} name="sect-quality-menu" />);
    expect(radios(html).every((x) => x.name === "sect-quality-menu")).toBe(true);
  });

  it("its placeholder keeps the room but has nothing to focus or announce", () => {
    const html = renderToStaticMarkup(<QualityPickerSpace />);
    expect(html).not.toContain("<input");
    expect(html).toContain('aria-hidden="true"');
    // Same box as the picker's.
    const box = /class="([^"]+)"/.exec(html)![1];
    expect(picker("mid", "mid").startsWith(`<div class="${box}">`)).toBe(true);
  });
});

describe("LoadingScreen with the picker", () => {
  const screen = (extra: Partial<Parameters<typeof LoadingScreen>[0]>) =>
    renderToStaticMarkup(<LoadingScreen progress={0.4} label="Loading the sect" {...extra} />);
  const quality = { tier: "mid" as Tier, recommended: "mid" as Tier, onPick: () => {} };

  it("shows the picker under the progress bar, or its empty place, or nothing", () => {
    const html = screen({ quality });
    expect(radios(html)).toHaveLength(3);
    expect(html.indexOf('role="progressbar"')).toBeLessThan(html.indexOf("<fieldset"));
    expect(html.indexOf("<fieldset")).toBeLessThan(html.indexOf("Read as page"));
    const reserved = screen({ quality: "reserve" });
    expect(reserved).not.toContain("<input");
    expect(reserved).not.toContain("Graphics");
    expect(screen({})).not.toContain("<fieldset");
    expect(screen({}).length).toBeLessThan(reserved.length);
  });

  it("keeps the picker on the error screen, above Reload", () => {
    const html = screen({ quality, error: "The graphics card dropped the scene.", onReload: () => {} });
    expect(radios(html)).toHaveLength(3);
    expect(html.indexOf("The graphics card dropped the scene.")).toBeLessThan(html.indexOf("<fieldset"));
    expect(html.indexOf("<fieldset")).toBeLessThan(html.indexOf(">Reload<"));
    // Only the message is the alert, not the controls under it.
    expect(html).toMatch(/<p role="alert">The graphics card dropped the scene\.<\/p>/);
    // No placeholder on the error screen.
    expect(screen({ quality: "reserve", error: "The scene failed to load." })).not.toMatch(/aria-hidden="true" class="mt-7/);
  });
});

describe("QualityButton", () => {
  it("names the current tier and starts closed", () => {
    const html = renderToStaticMarkup(<QualityButton tier="mid" recommended="high" onPick={() => {}} />);
    expect(html).toContain('aria-label="Graphics: Medium"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('aria-controls="sect-quality"');
    expect(html).toContain("data-sect-quality");
    expect(html).toMatch(/<div id="sect-quality" hidden=""/);
    expect(html).not.toContain("<input");
    expect(renderToStaticMarkup(<QualityButton tier="low" recommended="low" onPick={() => {}} />)).toContain('aria-label="Graphics: Low"');
  });
});

describe("SoundToggle's place", () => {
  // Rendered on the server the music is never available (useSyncExternalStore's server snapshot), so
  // these show the slot alone: what a browser without Web Audio gets.
  const engine = { subscribe: () => () => {}, snapshot: () => ({ available: false, on: false, muted: false }), toggle: () => {} } as unknown as MusicEngine;
  const extra = <button type="button" data-extra />;

  it("shows the extra control once the loading screen is gone, even without sound", () => {
    const html = renderToStaticMarkup(<SoundToggle engine={engine} raised={false} extra={extra} />);
    expect(html).toContain("data-extra");
    expect(html).not.toContain("data-sect-sound");
  });

  it("hides it while the loading screen is up (it has its own picker)", () => {
    expect(renderToStaticMarkup(<SoundToggle engine={engine} raised extra={extra} />)).toBe("");
    expect(renderToStaticMarkup(<SoundToggle engine={engine} raised={false} />)).toBe("");
  });
});
