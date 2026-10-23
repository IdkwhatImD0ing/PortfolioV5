/**
 * The portfolio as plain text, in the sect's order: what the server renders under the flight
 * (app/sect/summary.tsx) for crawlers, language models and visitors without JavaScript. Every fact
 * comes from portfolio-data and the copy the readers show (content-copy.ts); nothing is written here.
 *
 * Pure: no React, no three.js, no Next.
 */
import {
  EDUCATION,
  EXPERIENCE,
  HACKATHONS,
  PERSONAL_FACTS,
  PORTFOLIO,
  PROJECTS,
  SKILLS_LINE,
  type Project,
} from "@/lib/portfolio-data";
import { isImage } from "@/lib/video-embed";
import { AREAS, type AreaId } from "./areas";
import { ABOUT_CARDS, ARCH_HEAD, HERO, PERSONAL_HEAD, RESUME_GLANCE, RESUME_LINKS, type Run } from "./content-copy";
import { SECTION_NAMES, stripTags } from "./content";

export interface SummaryLink {
  label: string;
  href: string;
}

export interface SummaryItem {
  title: string;
  /** A short line under the title: dates, place, award. */
  meta?: string;
  lines: string[];
  links?: SummaryLink[];
}

export interface SummarySection {
  area: AreaId;
  /** The section's name ("Projects"), with the place that holds it ("Artifact Forge Peak", 炼器峰). */
  heading: string;
  place: string;
  zh: string;
  intro?: string;
  items: SummaryItem[];
}

export interface PortfolioSummary {
  name: string;
  tagline: string;
  intro: string;
  sections: SummarySection[];
}

const text = (runs: Run[]) => runs.map((r) => r.t).join("");

function projectLinks(p: Project): SummaryLink[] {
  const out: SummaryLink[] = [];
  if (p.github) out.push({ label: "Code", href: p.github });
  const demo = p.videoUrl ?? p.demo;
  // Some demos are a still from the project's gallery, not a video.
  if (demo) out.push({ label: isImage(demo) ? "Screenshot" : "Demo", href: demo });
  if (p.projectUrl && p.projectUrl !== demo) out.push({ label: "Project page", href: p.projectUrl });
  return out;
}

/** Each area's section, gate first and summit last; the gate's welcome is the summary's intro. */
export function portfolioSummary(): PortfolioSummary {
  const items: Partial<Record<AreaId, { intro?: string; items: SummaryItem[] }>> = {
    mirror: { items: ABOUT_CARDS.map((c) => ({ title: c.title, lines: [c.body] })) },
    forge: {
      items: PROJECTS.map((p) => ({
        title: p.name,
        meta: [p.year, p.award].filter(Boolean).join(" · ") || undefined,
        lines: [p.summary],
        links: projectLinks(p),
      })),
    },
    arena: {
      intro: `${HACKATHONS.length} hackathon wins.`,
      items: HACKATHONS.map((h) => ({ title: `${h.name}${h.year ? ` ${h.year}` : ""}: ${h.prize}`, lines: [h.project] })),
    },
    mission: { items: EXPERIENCE.map((e) => ({ title: `${e.role}, ${e.where}`, meta: e.when, lines: e.bullets })) },
    library: { items: EDUCATION.map((e) => ({ title: e.full, meta: `${e.degree} · ${e.when}`, lines: [e.detail] })) },
    steles: { intro: SKILLS_LINE.map((w) => w.w).join(" "), items: [] },
    scroll: {
      items: [
        {
          title: "Resume (PDF)",
          lines: RESUME_GLANCE.map((g) => `${g.k} ${g.v}`),
          links: [{ label: "resume.pdf", href: "/resume.pdf" }],
        },
      ],
    },
    formation: { intro: ARCH_HEAD.intro, items: [] },
    abode: { items: [{ title: text(PERSONAL_HEAD.heading), lines: PERSONAL_FACTS.map((f) => stripTags(f.line)) }] },
    summit: {
      items: [
        {
          title: "Get in touch",
          lines: [],
          links: [
            { label: PORTFOLIO.email, href: `mailto:${PORTFOLIO.email}` },
            ...RESUME_LINKS,
            { label: "devpost.com/IdkwhatImD0ing", href: PORTFOLIO.devpost },
          ],
        },
      ],
    },
  };
  const sections = AREAS.filter((a) => items[a.id]).map((a) => ({
    area: a.id,
    heading: SECTION_NAMES[a.id],
    place: a.label,
    zh: a.zh,
    ...items[a.id]!,
  }));
  return { name: PORTFOLIO.name, tagline: PORTFOLIO.tagline, intro: text(HERO.intro), sections };
}
