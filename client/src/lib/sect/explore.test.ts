import { describe, expect, it } from "vitest";
import { EDUCATION, EXPERIENCE, HACKATHONS, PROJECTS } from "@/lib/portfolio-data";
import { ABOUT_CARDS, ARCH_FLOW, ARCH_STACK } from "./content-copy";
import { hotspotTarget, skillGroups } from "./content";
import {
  MIRROR_CARD_THINGS,
  itemSiblings,
  matchingSentence,
  mirrorCardIndex,
  parseSpan,
  roleTimeline,
  skillEvidence,
  spanYears,
  stackSteps,
  stepStack,
  topPrizes,
  type Related,
} from "./explore";

const NOW = new Date(2026, 9, 19);

/** Every related link must open something real: a hotspot-addressable item, or a whole area. */
function expectReal(list: Related[]) {
  for (const r of list) {
    if (r.target.item) expect(hotspotTarget(r.target.item), r.target.item).toMatchObject({ area: r.target.area });
    expect(r.title.length).toBeGreaterThan(0);
  }
}

describe("parseSpan", () => {
  it("reads month spans, year spans, Now and open-ended years", () => {
    expect(parseSpan("Jun 2025 — Jul 2026", NOW)).toEqual({ start: 2025 * 12 + 5, end: 2026 * 12 + 6, open: false });
    expect(parseSpan("Jul 2026 — Now", NOW)).toEqual({ start: 2026 * 12 + 6, end: 2026 * 12 + 9, open: true });
    expect(parseSpan("2016 — 2020", NOW)).toEqual({ start: 2016 * 12, end: 2020 * 12 + 11, open: false });
    expect(parseSpan("2023 — 2025+", NOW)).toEqual({ start: 2023 * 12, end: 2025 * 12 + 11, open: true });
    expect(parseSpan("whenever", NOW)).toBeNull();
    expect(spanYears(parseSpan("Aug 2023 — May 2025", NOW)!)).toEqual([2023, 2025]);
  });

  it("reads every role and school in the data", () => {
    for (const r of EXPERIENCE) expect(parseSpan(r.when, NOW), r.when).not.toBeNull();
    for (const e of EDUCATION) expect(parseSpan(e.when, NOW), e.when).not.toBeNull();
  });

  it("lays every role out on one axis, inside it", () => {
    const t = roleTimeline(NOW);
    expect(t.rows).toHaveLength(EXPERIENCE.length);
    for (const r of t.rows) {
      expect(r.width).toBeGreaterThan(0);
      expect(r.left).toBeGreaterThanOrEqual(0);
      expect(r.left + r.width).toBeLessThanOrEqual(1.0001);
    }
    expect(t.rows[0].open).toBe(true); // the current role runs to now
  });
});

describe("itemSiblings", () => {
  it("steps through an item's kind in order", () => {
    expect(itemSiblings("role:0")).toEqual({ prev: null, next: "role:1" });
    expect(itemSiblings(`hackathon:${HACKATHONS.length - 1}`).next).toBeNull();
    expect(itemSiblings("arch:6")).toEqual({ prev: "arch:5", next: "arch:7" });
    expect(itemSiblings("fact:3")).toEqual({ prev: "fact:2", next: "fact:4" });
  });

  it("steps through an area's named spots", () => {
    expect(itemSiblings("gate-lions")).toEqual({ prev: null, next: "gate-swords" });
    expect(itemSiblings(MIRROR_CARD_THINGS[1])).toEqual({ prev: MIRROR_CARD_THINGS[0], next: MIRROR_CARD_THINGS[2] });
    expect(itemSiblings("summit-arch")).toEqual({ prev: null, next: "summit-cranes" });
    expect(itemSiblings("abode-cranes")).toEqual({ prev: null, next: null });
    expect(itemSiblings("nope")).toEqual({ prev: null, next: null });
  });
});

describe("related items", () => {
  it("ranks the top prizes", () => {
    expect(topPrizes().length).toBeGreaterThan(2);
    expect(topPrizes()[0].target.item).toBe("hackathon:0");
  });

  it("finds real lines for every stele row", () => {
    for (const g of skillGroups()) {
      const ev = skillEvidence(g.index);
      expect(ev.length, g.label).toBeGreaterThanOrEqual(2);
      expectReal(ev);
      // Notes are quoted from the data, never invented.
      for (const r of ev) {
        const sources = [
          ...EXPERIENCE.flatMap((x) => x.bullets),
          ...PROJECTS.map((p) => `${p.summary} ${p.long ?? ""}`),
          ...ABOUT_CARDS.map((c) => `${c.title} ${c.body}`),
          ...ARCH_FLOW.map((f) => f.body),
        ];
        const quote = (r.note ?? "").replace(/…$/, "");
        expect(sources.some((s) => s.includes(quote)), quote).toBe(true);
      }
    }
  });

  it("quotes one sentence, cut at a word", () => {
    expect(matchingSentence("One. Two has latency here. Three.", /latency/)).toBe("Two has latency here.");
    expect(matchingSentence("Nothing here.", /latency/)).toBeNull();
    const long = matchingSentence(`${"word ".repeat(80)}latency.`, /latency/)!;
    expect(long.length).toBeLessThanOrEqual(200);
    expect(long.endsWith("…")).toBe(true);
  });

  it("pairs each About card with a mirror spot", () => {
    expect(MIRROR_CARD_THINGS).toHaveLength(ABOUT_CARDS.length);
    for (let i = 0; i < ABOUT_CARDS.length; i++) {
      expect(mirrorCardIndex(MIRROR_CARD_THINGS[i])).toBe(i);
    }
  });

  it("matches the formation's steps and stack both ways", () => {
    for (let i = 0; i < ARCH_FLOW.length; i++) {
      expect(stepStack(i).length, ARCH_FLOW[i].title).toBeGreaterThan(0);
      for (const g of stepStack(i)) expect(stackSteps(g.group)).toContain(i);
    }
    for (const s of ARCH_STACK) expect(stackSteps(s.group).length, s.group).toBeGreaterThan(0);
  });
});
