/**
 * The owner's wish (October 2026): the sect's agent is a senior disciple of the sect, and nothing it
 * is labelled with says "AI". Its labels live in several places: the orb's copy (content-copy.ts
 * VOICE_ORB, FOOTER), the talisman's hover plate (sect.css), the moon's hint (content.ts), and the
 * "ask" buttons on the panels and readers. (The owner's own job title, "AI engineer", and his
 * projects' names stay: they are portfolio content, not the agent.)
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { hotspotLabel } from "./content";
import { FOOTER, VOICE_ORB } from "./content-copy";

const APP = path.resolve(__dirname, "../../app/sect");
const read = (rel: string) => readFileSync(path.join(APP, rel), "utf8");
const NOT_AI = /\bAI\b|\bassistant\b|\bbot\b|\bportfolio\b|\borb\b/i;

describe("the agent's labels on the sect", () => {
  it("name a senior disciple, never an AI", () => {
    for (const words of [VOICE_ORB.pill, VOICE_ORB.button, VOICE_ORB.panel, FOOTER.tapOrb, hotspotLabel("moon").blurb]) {
      expect(words, words).toMatch(/senior disciple/i);
      expect(words, words).not.toMatch(NOT_AI);
    }
  });

  it("the talisman's hover plate says it too", () => {
    const css = read("sect.css");
    const plate = css.match(/\.sect-orb > div:not\(\[role="dialog"\]\)::after \{\s*content: "([^"]+)";/);
    expect(plate?.[1]).toBe("Ask a senior disciple");
    expect(css).not.toContain('content: "Talk to the AI"');
  });

  it("so do the panels' and readers' buttons", () => {
    for (const file of ["content/panel.tsx", "content/sections/intro.tsx", "content/sections/abode.tsx"]) {
      const labels = [...read(file).matchAll(/<TalkButton[^>]*label=(?:"([^"]+)"|\{([^}]+)\})/g)].map((m) => m[1] ?? m[2]);
      expect(labels.length, file).toBeGreaterThan(0);
      for (const label of labels) {
        if (label.startsWith("FOOTER.")) continue;
        expect(label, file).toBe("Ask a senior disciple");
      }
    }
  });

  it("the footer's line asks for the talisman, not the orb", () => {
    expect(FOOTER.body).toContain("Tap the talisman");
    expect(FOOTER.body).not.toMatch(/\bAI\b|\borb\b/i);
  });
});
