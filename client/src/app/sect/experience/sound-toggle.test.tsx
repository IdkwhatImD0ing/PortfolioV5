/**
 * The music's volume slider beside the sound toggle: a real range input with a visible label, its
 * level readout, and keyboard steps; only while the music plays.
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

describe("SoundControls", () => {
  it("shows the slider beside the toggle while the music plays", () => {
    const html = controls({ available: true, on: true, muted: false, volume: 0.4 });
    expect(html).toContain('aria-label="Sound off"');
    expect(html).toContain('type="range"');
    expect(html).toContain('value="40"');
  });

  it("hides the slider while muted: the toggle stands alone", () => {
    const html = controls({ available: true, on: false, muted: true, volume: 0.4 });
    expect(html).toContain('aria-label="Sound on"');
    expect(html).not.toContain('type="range"');
  });
});
