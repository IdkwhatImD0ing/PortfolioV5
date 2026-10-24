/**
 * The music's volume slider beside the sound toggle: a real range input with a visible label, its
 * level readout, and keyboard steps; only while the music plays, and out only while it is wanted
 * (lib/sect/volume-reveal.test.ts has the rules for when).
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { VOLUME_STEP } from "@/lib/sect/volume";
import type { MusicUi } from "./music-engine";
import { SoundControls, VolumeSlider } from "./sound-toggle";

const controls = (ui: MusicUi) => renderToStaticMarkup(<SoundControls ui={ui} onToggle={() => {}} onVolume={() => {}} />);

describe("VolumeSlider", () => {
  const html = renderToStaticMarkup(<VolumeSlider volume={0.7} onVolume={() => {}} />);

  it("is a range input from 0 to 100% in keyboard steps", () => {
    expect(html).toMatch(/<input[^>]*type="range"/);
    expect(html).toContain('min="0"');
    expect(html).toContain('max="100"');
    expect(html).toContain(`step="${VOLUME_STEP}"`);
    expect(html).toContain('value="70"');
    expect(html).toContain('aria-valuetext="70%"');
  });

  it("has a visible label tied to the input, read as the music volume", () => {
    const id = html.match(/<input[^>]*id="([^"]+)"/)?.[1];
    expect(id).toBeTruthy();
    expect(html).toContain(`for="${id}"`);
    const label = html.match(/<label[^>]*>(.*?)<\/label>/)?.[1].replace(/<[^>]+>/g, "");
    expect(label).toBe("Music volume");
    // The level is written beside it, and its gold fill follows the value.
    expect(html).toContain(">70%<");
    expect(html).toContain("--v:70%");
  });
});

describe("VolumeSlider put away", () => {
  const shown = renderToStaticMarkup(<VolumeSlider volume={0.7} onVolume={() => {}} />);
  const hidden = renderToStaticMarkup(<VolumeSlider volume={0.7} open={false} onVolume={() => {}} />);
  const plate = (html: string) => html.match(/<div[^>]*data-sect-volume[^>]*>/)?.[0] ?? "";

  it("is marked open and reachable while it shows", () => {
    expect(plate(shown)).toContain("data-open");
    expect(plate(shown)).not.toContain("inert");
  });

  it("is inert while put away: out of the Tab order, the screen reader's and the pointer's", () => {
    expect(plate(hidden)).not.toContain("data-open");
    expect(plate(hidden)).toMatch(/\sinert=""/);
    // Still the same slider, ready to come back at the same level.
    expect(hidden).toContain('value="70"');
  });
});

describe("SoundControls", () => {
  it("puts the slider beside the toggle while the music plays, put away until it is wanted", () => {
    const html = controls({ available: true, on: true, muted: false, volume: 0.4 });
    expect(html).toContain('aria-label="Sound off"');
    expect(html).toContain('type="range"');
    expect(html).toContain('value="40"');
    // It comes out once the page has it (the music turning on shows it for a moment, with a fade).
    expect(html.match(/<div[^>]*data-sect-volume[^>]*>/)?.[0]).toMatch(/\sinert=""/);
  });

  it("keeps the toggle first, so Tab goes from it on into the slider (drawn left of it on wider screens)", () => {
    const html = controls({ available: true, on: true, muted: false, volume: 0.4 });
    expect(html.indexOf("data-sect-sound")).toBeLessThan(html.indexOf("data-sect-volume"));
    expect(html).toContain("md:flex-row-reverse");
    // Phones: a column, the slider standing under the toggle.
    expect(html).toMatch(/class="flex flex-col items-end/);
  });

  it("hides the slider while muted: the toggle stands alone", () => {
    const html = controls({ available: true, on: false, muted: true, volume: 0.4 });
    expect(html).toContain('aria-label="Sound on"');
    expect(html).not.toContain('type="range"');
  });
});
