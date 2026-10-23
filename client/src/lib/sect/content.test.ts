import { describe, expect, it } from "vitest";
import {
  EDUCATION,
  EXPERIENCE,
  HACKATHONS,
  PERSONAL_FACTS,
  PORTFOLIO,
  PROJECTS,
  SKILLS_LINE,
  STANDOUT_PROJECT_IDS,
} from "@/lib/portfolio-data";
import { AREA_IDS } from "./areas";
import { FORGE_RING } from "./artifacts";
import {
  AREA_THING_IDS,
  FORGE_FILTERS,
  isThing,
  areaItemHotspots,
  areaSummary,
  commandTarget,
  company,
  factRuns,
  filterProjects,
  formationItems,
  hackathonProject,
  heroChipTarget,
  holdPanels,
  hotspotArea,
  hotspotCard,
  hotspotLabel,
  hotspotTarget,
  itemDomId,
  itemIndex,
  neighborAreas,
  pageSectionDomId,
  parseContentHash,
  parseFilter,
  projectMedia,
  sectionDomId,
  shortFact,
  skillGroups,
  skillsSentence,
  stripTags,
} from "./content";
import * as COPY from "./content-copy";

describe("hotspotTarget", () => {
  it("opens the whole area for an area's landmark and for spots without a view of their own", () => {
    for (const a of AREA_IDS) expect(hotspotTarget(a)).toEqual({ area: a, item: null });
    expect(hotspotTarget("abode-moon-gate")).toEqual({ area: "abode", item: null });
  });

  it("opens a named spot's own view", () => {
    expect(hotspotTarget("gate-lions")).toEqual({ area: "gate", item: "gate-lions" });
    expect(hotspotTarget("mirror-pond")).toEqual({ area: "mirror", item: "mirror-pond" });
    expect(hotspotTarget("mission-bell")).toEqual({ area: "mission", item: "mission-bell" });
    expect(hotspotTarget("summit-arch")).toEqual({ area: "summit", item: "summit-arch" });
    for (const [area, ids] of Object.entries(AREA_THING_IDS)) {
      for (const id of ids ?? []) {
        expect(hotspotTarget(id)).toEqual({ area, item: id });
        expect(isThing(id)).toBe(true);
        expect(hotspotLabel(id).title, id).not.toBe(id);
      }
    }
    expect(isThing("gate")).toBe(false);
    expect(isThing("role:0")).toBe(false);
  });

  it("maps every item id of the contract to its area", () => {
    expect(hotspotTarget("project:dispatchai")).toEqual({ area: "forge", item: "project:dispatchai" });
    expect(hotspotTarget("hackathon:0")).toEqual({ area: "arena", item: "hackathon:0" });
    expect(hotspotTarget("hackathon:35")).toEqual({ area: "arena", item: "hackathon:35" });
    expect(hotspotTarget("role:6")).toEqual({ area: "mission", item: "role:6" });
    expect(hotspotTarget("school:2")).toEqual({ area: "library", item: "school:2" });
    expect(hotspotTarget("skills:4")).toEqual({ area: "steles", item: "skills:4" });
    expect(hotspotTarget("arch:7")).toEqual({ area: "formation", item: "arch:7" });
    expect(hotspotTarget("fact:6")).toEqual({ area: "abode", item: "fact:6" });
    expect(hotspotTarget("resume")).toEqual({ area: "scroll", item: "resume" });
    expect(hotspotTarget("moon")).toEqual({ area: "summit", item: "moon" });
    expect(hotspotTarget("steles")).toEqual({ area: "steles", item: null });
  });

  it("sends other project slugs to the forge, where the reader loads them from the archive", () => {
    expect(hotspotTarget("project:talktuahbank")).toEqual({ area: "forge", item: "project:talktuahbank" });
    expect(hotspotTarget("project:Secway")).toEqual({ area: "forge", item: "project:secway" });
    expect(hotspotTarget("project:nope")).toEqual({ area: "forge", item: "project:nope" });
  });

  it("resolves project aliases to the canonical id", () => {
    expect(hotspotTarget("project:dispatch-ai")).toEqual({ area: "forge", item: "project:dispatchai" });
    expect(hotspotTarget("project:magicloops")).toEqual({ area: "forge", item: "project:instarizz" });
  });

  it("treats out-of-range, unknown and malformed ids as decorative", () => {
    expect(hotspotTarget("hackathon:36")).toBeNull();
    expect(hotspotTarget("hackathon:39")).toBeNull();
    expect(hotspotTarget("role:7")).toBeNull();
    expect(hotspotTarget("skills:5")).toBeNull();
    expect(hotspotTarget("arch:8")).toBeNull();
    expect(hotspotTarget("fact:-1")).toBeNull();
    expect(hotspotTarget("project:")).toBeNull();
    expect(hotspotTarget("project:../x")).toBeNull();
    expect(hotspotTarget("role")).toBeNull();
    expect(hotspotTarget("unknown")).toBeNull();
    expect(hotspotTarget("moon:1")).toBeNull();
    expect(hotspotTarget("")).toBeNull();
  });

  it("groups ids by their area for the hold they belong to", () => {
    expect(hotspotArea("mirror-pond")).toBe("mirror");
    expect(hotspotArea("gate")).toBe("gate");
    expect(hotspotArea("project:sentinelai")).toBe("forge");
    expect(hotspotArea("moon")).toBe("summit");
    expect(hotspotArea("whatever")).toBe("whatever");
  });
});

describe("hotspotLabel", () => {
  it("labels items from the real data", () => {
    expect(hotspotLabel("project:dispatchai").title).toBe("Dispatch AI");
    expect(hotspotLabel("hackathon:1").title).toBe("HackUTD 2024");
    expect(hotspotLabel("hackathon:1").blurb).toBe("TalkTuahBank · ★ Grand Prize + Goldman Sachs");
    expect(hotspotLabel("role:0").title).toBe("Software Engineer II · Pinterest");
    expect(hotspotLabel("school:0").title).toBe(EDUCATION[0].full);
    expect(hotspotLabel("skills:0").title).toBe("voice-first");
    expect(hotspotLabel("arch:0").title).toBe("01 Mic input");
    expect(hotspotLabel("arch:6").title).toBe("Stack");
    expect(hotspotLabel("arch:7").title).toBe("Code");
    expect(hotspotLabel("fact:0").title).toBe("Finished a 4-year CS degree in 2.5 years");
    expect(hotspotLabel("resume").title).toBe("Resume");
    expect(hotspotLabel("moon").title).toBe("The moon");
  });

  it("labels areas with the place name and Chinese name", () => {
    expect(hotspotLabel("forge")).toMatchObject({ title: "Artifact Forge Peak", zh: "炼器峰", blurb: "Projects" });
  });

  it("uses the glTF label for things in an area, with known Chinese names", () => {
    expect(hotspotLabel("gate-lions", "Guardian Lions")).toMatchObject({ title: "Guardian Lions", zh: "石狮" });
    expect(hotspotLabel("abode-koi-pool").title).toBe("Koi pool");
    expect(hotspotLabel("abode-koi-pool", "Koi Pool").title).toBe("Koi Pool");
  });

  it("falls back for unknown ids", () => {
    expect(hotspotLabel("nope")).toEqual({ title: "nope" });
    expect(hotspotLabel("nope", "Thing")).toEqual({ title: "Thing" });
  });

  it("leaves out lore, the area's Chinese name on items and lines that repeat the title", () => {
    expect(hotspotLabel("gate-lions").blurb).toBeUndefined();
    expect(hotspotLabel("project:dispatchai").zh).toBeUndefined();
    expect(hotspotLabel("hackathon:1").zh).toBeUndefined();
    expect(hotspotLabel("skills:0").blurb).toBeUndefined();
    expect(hotspotLabel("fact:0").blurb).toBeUndefined();
    expect(hotspotLabel("fact:2").blurb).toBe(stripTags(PERSONAL_FACTS[2].line));
    expect(hotspotLabel("moon")).toEqual({ title: "The moon", zh: "明月", blurb: "Talk to the AI" });
  });

  it("gives every item of every area a non-empty label and a DOM id", () => {
    const ids = AREA_IDS.flatMap((a) => areaItemHotspots(a).map((h) => h.id));
    expect(ids).toHaveLength(PROJECTS.length + HACKATHONS.length + EXPERIENCE.length + EDUCATION.length + 5 + 1 + 8 + PERSONAL_FACTS.length + 1);
    for (const id of ids) {
      expect(hotspotTarget(id)?.item).toBe(id);
      expect(hotspotLabel(id).title.length).toBeGreaterThan(0);
      expect(itemDomId(id)).toMatch(/^sect-item-[a-z0-9-]+$/i);
    }
  });
});

describe("prototype API", () => {
  it("keeps the gate and mirror panels and adds the other areas", () => {
    const p = holdPanels();
    expect(Object.keys(p)).toEqual([...AREA_IDS]);
    expect(p.gate.title).toBe(PORTFOLIO.name);
    expect(p.gate.body).toContain(PORTFOLIO.tagline);
    expect(p.mirror.body.join(" ")).toMatch(/hackathon/);
  });

  it("builds hotspot cards from real data for items and from the place text for areas", () => {
    expect(hotspotCard("unknown", "Thing")).toEqual({ title: "Thing", zh: undefined, body: "" });
    expect(hotspotCard("gate", "Mountain Gate").body.length).toBeGreaterThan(0);
    expect(hotspotCard("role:1", "x")).toMatchObject({ title: "Applied AI Engineer (Forward-Deployed) · Scale AI" });
  });
});

describe("areaSummary", () => {
  it("has a place name, title, at most one line and an Open action for every area", () => {
    for (const a of AREA_IDS) {
      const s = areaSummary(a);
      expect(s.eyebrow.length).toBeGreaterThan(0);
      expect(s.zh.length).toBeGreaterThan(0);
      expect(s.title.length).toBeGreaterThan(0);
      expect(s.lines.length).toBeLessThanOrEqual(1);
      expect(s.action).toBe("Open");
    }
  });

  it("counts from the data", () => {
    expect(areaSummary("forge").lines).toEqual([`${PROJECTS.length} projects, ${FORGE_RING.length} prize winners.`]);
    expect(areaSummary("arena").lines).toEqual([`${HACKATHONS.length} wins during college. $150k+ in prizes.`]);
    expect(areaSummary("mission").lines).toEqual(["Now: Software Engineer II at Pinterest."]);
    expect(areaSummary("library").lines).toEqual([EDUCATION.map((e) => e.school).join(" · ")]);
  });

  it("knows the neighbours in flight order", () => {
    expect(neighborAreas("gate")).toEqual({ prev: null, next: "mirror" });
    expect(neighborAreas("forge")).toEqual({ prev: "mirror", next: "arena" });
    expect(neighborAreas("summit")).toEqual({ prev: "abode", next: null });
  });
});

describe("projects", () => {
  it("shows the six standouts in their curated order for the main page's default filter", () => {
    expect(filterProjects("all", null).map((p) => p.id)).toEqual([...STANDOUT_PROJECT_IDS]);
  });

  it("shows the ring's winners by default and all projects for the added All filter", () => {
    expect(FORGE_FILTERS[0]).toEqual({ key: "ring", label: "On the ring" });
    expect(filterProjects("ring", null).map((p) => p.id)).toEqual([...FORGE_RING]);
    expect(filterProjects("ring", 2024).every((p) => p.year === 2024 && FORGE_RING.includes(p.id as never))).toBe(true);
    expect(filterProjects("every", null)).toHaveLength(PROJECTS.length);
    expect(FORGE_FILTERS[1]).toEqual({ key: "every", label: `All ${PROJECTS.length}` });
  });

  it("filters by tag and narrows by year like the main page", () => {
    const voice = filterProjects("voice", null);
    expect(voice.length).toBeGreaterThan(0);
    expect(voice.every((p) => p.tags.includes("voice"))).toBe(true);
    expect(filterProjects("voice", 2025).every((p) => p.year === 2025 && p.tags.includes("voice"))).toBe(true);
    expect(filterProjects("all", 2024).every((p) => p.year === 2024)).toBe(true);
    expect(filterProjects("all", 2024).length).toBe(PROJECTS.filter((p) => p.year === 2024).length);
  });

  it("parses filter targets", () => {
    expect(parseFilter("voice")).toEqual({ filter: "voice", year: null });
    expect(parseFilter("2025")).toEqual({ filter: "every", year: 2025 });
    expect(parseFilter("bogus")).toEqual({ filter: "ring", year: null });
    expect(parseFilter(undefined)).toEqual({ filter: "ring", year: null });
    expect(parseFilter("every")).toEqual({ filter: "every", year: null });
  });

  it("picks the same media as the main page's detail view", () => {
    const dispatch = PROJECTS.find((p) => p.id === "dispatchai")!;
    expect(projectMedia(dispatch).embed).toBe("https://www.youtube.com/embed/hdpdgxrilQM?rel=0&modestbranding=1");
    const court = PROJECTS.find((p) => p.id === "courtvision")!;
    expect(projectMedia(court)).toMatchObject({ embed: null, image: court.demo });
  });

  it("links hackathon wins to the forge project they were won with", () => {
    const linked = HACKATHONS.map((_, i) => hackathonProject(i)?.id).filter(Boolean);
    expect(hackathonProject(0)?.id).toBe("dispatchai");
    expect(hackathonProject(9)?.id).toBe("tft");
    expect(hackathonProject(15)?.id).toBe("swarmaid");
    expect(hackathonProject(3)).toBeUndefined();
    expect(linked.length).toBeGreaterThanOrEqual(10);
  });
});

describe("text helpers", () => {
  it("splits facts into bold and plain runs", () => {
    expect(factRuns("Won my first hackathon at <b>17</b>.")).toEqual([
      { t: "Won my first hackathon at ", b: false },
      { t: "17", b: true },
      { t: ".", b: false },
    ]);
    for (const f of PERSONAL_FACTS) expect(factRuns(f.line).map((r) => r.t).join("")).toBe(stripTags(f.line));
  });

  it("shortens long facts at a clause", () => {
    expect(shortFact(PERSONAL_FACTS[5].line)).toBe("Convinced everyone gets a personal Jarvis eventually");
    expect(shortFact(PERSONAL_FACTS[2].line)).toBe("Speaks Mandarin and English");
    for (const f of PERSONAL_FACTS) expect(shortFact(f.line).length).toBeLessThanOrEqual(60);
  });

  it("takes the company from an experience entry", () => {
    expect(company("Scale AI · San Francisco")).toBe("Scale AI");
    expect(company(EXPERIENCE[6].where)).toBe(EXPERIENCE[6].where);
  });

  it("finds the five skill phrases of the skills line", () => {
    expect(skillGroups().map((g) => g.label)).toEqual([
      "voice-first",
      "agents",
      "latency",
      "keeping a human in the loop",
      "when the model is wrong",
    ]);
    expect(skillsSentence()).toBe(SKILLS_LINE.map((w) => w.w).join(" "));
  });

  it("has eight formation pillars", () => {
    expect(formationItems().map((f) => f.id)).toEqual(["arch:0", "arch:1", "arch:2", "arch:3", "arch:4", "arch:5", "arch:6", "arch:7"]);
  });

  it("reads indexed item ids", () => {
    expect(itemIndex("role:3", "role")).toBe(3);
    expect(itemIndex("role:3", "fact")).toBeNull();
    expect(itemIndex("role:x", "role")).toBeNull();
    expect(itemIndex(null, "role")).toBeNull();
  });
});

describe("navigation", () => {
  it("routes main-page voice commands to sect targets", () => {
    expect(commandTarget({ type: "filter", tag: "voice" })).toEqual({ area: "forge", item: null, filter: "voice" });
    expect(commandTarget({ type: "filter", year: 2025 })).toEqual({ area: "forge", item: null, filter: "2025" });
    expect(commandTarget({ type: "open", id: "dispatch-ai" })).toEqual({ area: "forge", item: "project:dispatchai" });
    expect(commandTarget({ type: "focus", id: "sentinelai" })).toEqual({ area: "forge", item: "project:sentinelai" });
    expect(commandTarget({ type: "scroll", id: "hackathons" })).toEqual({ area: "arena", item: null });
    expect(commandTarget({ type: "scroll", id: "nowhere" })).toBeNull();
  });

  it("sends hero chips where the main page sends them", () => {
    expect(COPY.HERO_CHIPS.map((c) => heroChipTarget(c))).toEqual([
      { area: "mirror", item: null },
      { area: "forge", item: null, filter: "voice" },
      { area: "arena", item: null },
      { area: "abode", item: null },
      { area: "forge", item: null },
    ]);
  });

  it("parses main-page deep links", () => {
    expect(parseContentHash("#project/dispatchai")).toEqual({ area: "forge", item: "project:dispatchai" });
    expect(parseContentHash("#project/dispatch-ai")).toEqual({ area: "forge", item: "project:dispatchai" });
    expect(parseContentHash("#projects")).toEqual({ area: "forge", item: null });
    expect(parseContentHash("#footer")).toEqual({ area: "summit", item: null });
    expect(parseContentHash("#forge")).toEqual({ area: "forge", item: null });
    expect(parseContentHash("#nope")).toBeNull();
    expect(parseContentHash("")).toBeNull();
  });

  it("ignores case in section hashes and opens archived or unknown projects in the forge", () => {
    expect(parseContentHash("#Projects")).toEqual({ area: "forge", item: null });
    expect(parseContentHash("#FORGE")).toEqual({ area: "forge", item: null });
    expect(parseContentHash("#project/DispatchAI")).toEqual({ area: "forge", item: "project:dispatchai" });
    expect(parseContentHash("#project/talktuahbank")).toEqual({ area: "forge", item: "project:talktuahbank" });
    expect(parseContentHash("#project/notreal")).toEqual({ area: "forge", item: "project:notreal" });
    expect(parseContentHash("#project/")).toBeNull();
    expect(parseContentHash("#project/<script>")).toBeNull();
  });

  it("never throws on malformed escapes", () => {
    for (const h of ["#%", "#%zz", "#100%", "#project/%E0", "#project/caf%E9", "%"]) {
      expect(() => parseContentHash(h), h).not.toThrow();
      expect(parseContentHash(h), h).toBeNull();
    }
  });

  it("gives page-view sections ids the main page does not use", () => {
    for (const a of AREA_IDS) {
      expect(pageSectionDomId(a)).toBe(`sc-page-area-${a}`);
      expect(pageSectionDomId(a)).not.toBe(sectionDomId(a));
    }
  });
});
