import { describe, expect, it } from "vitest";
import { EDUCATION, EXPERIENCE, HACKATHONS, PERSONAL_FACTS, PORTFOLIO, PROJECTS, SKILLS_LINE } from "@/lib/portfolio-data";
import { AREAS } from "./areas";
import { portfolioSummary } from "./summary";

describe("portfolioSummary", () => {
  const s = portfolioSummary();
  const section = (area: string) => s.sections.find((x) => x.area === area);
  const titles = (area: string) => section(area)?.items.map((i) => i.title) ?? [];

  it("names the owner and says who he is", () => {
    expect(s.name).toBe(PORTFOLIO.name);
    expect(s.tagline).toBe(PORTFOLIO.tagline);
    expect(s.intro).toContain("Pinterest");
  });

  it("follows the flight's order, each section with its place", () => {
    const order = AREAS.map((a) => a.id);
    const areas = s.sections.map((x) => x.area);
    expect(areas).toEqual(order.filter((a) => areas.includes(a)));
    // The gate's welcome is the intro; every other stop has a section.
    expect(areas).toEqual(order.filter((a) => a !== "gate"));
    for (const x of s.sections) {
      const a = AREAS.find((y) => y.id === x.area)!;
      expect(x.place).toBe(a.label);
      expect(x.zh).toBe(a.zh);
      expect(x.heading.length).toBeGreaterThan(0);
    }
  });

  it("lists every project with its summary and links", () => {
    expect(titles("forge")).toEqual(PROJECTS.map((p) => p.name));
    for (const p of PROJECTS) {
      const item = section("forge")!.items.find((i) => i.title === p.name)!;
      expect(item.lines).toEqual([p.summary]);
      if (p.github) expect(item.links).toContainEqual({ label: "Code", href: p.github });
      if (p.award) expect(item.meta).toContain(p.award);
    }
  });

  it("lists every win, role, school, skill and fact", () => {
    expect(section("arena")!.items).toHaveLength(HACKATHONS.length);
    expect(section("arena")!.intro).toBe(`${HACKATHONS.length} hackathon wins.`);
    expect(titles("mission")).toEqual(EXPERIENCE.map((e) => `${e.role}, ${e.where}`));
    expect(section("mission")!.items.flatMap((i) => i.lines)).toEqual(EXPERIENCE.flatMap((e) => e.bullets));
    expect(titles("library")).toEqual(EDUCATION.map((e) => e.full));
    for (const w of SKILLS_LINE) expect(section("steles")!.intro).toContain(w.w);
    const facts = section("abode")!.items.flatMap((i) => i.lines);
    expect(facts).toHaveLength(PERSONAL_FACTS.length);
    expect(facts.join(" ")).not.toMatch(/<\/?b>/);
  });

  it("links the resume and every way to get in touch", () => {
    const links = s.sections.flatMap((x) => x.items.flatMap((i) => i.links ?? []));
    const hrefs = links.map((l) => l.href);
    expect(hrefs).toContain("/resume.pdf");
    expect(hrefs).toContain(`mailto:${PORTFOLIO.email}`);
    expect(hrefs).toEqual(expect.arrayContaining([PORTFOLIO.github, PORTFOLIO.linkedin, PORTFOLIO.devpost]));
  });
});
