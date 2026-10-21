/**
 * Pure shaping for the /sect content layer: which area and item a hotspot opens, the labels shown
 * on hover and in the Places list, the summary panel of each area, project filtering, and the
 * small text helpers the readers use. No React here; the components live in src/app/sect/content.
 *
 * Portfolio facts come from portfolio-data (and main-page copy from content-copy.ts), so the 3D
 * page always says what the main page says.
 *
 * The prototype exports (holdPanels, hotspotCard, hotspotArea, HoldPanel, HotspotCard) still work.
 */
import { STANDOUT_PROJECT_IDS } from "@/components/sections/projects/constants";
import type { VoiceCommand } from "@/lib/voice-bus";
import {
  EDUCATION,
  EXPERIENCE,
  HACKATHONS,
  PERSONAL_FACTS,
  PORTFOLIO,
  PROJECTS,
  SKILLS_LINE,
  findProject,
  type Project,
} from "@/lib/portfolio-data";
import { isImage, toEmbed } from "@/lib/video-embed";
import { AREAS, AREA_IDS, areaForSection, areaInfo, isAreaId, type AreaId } from "./areas";
import { FORGE_RING, projectAward } from "./artifacts";
import { ARCH_FLOW, ARCH_STACK, HERO_CHIPS, PROJECT_FILTERS } from "./content-copy";

// ---- targets ----------------------------------------------------------------------------------

export interface ContentTarget {
  area: AreaId;
  /** An item-level hotspot id ("project:dispatchai"), or null for the whole section. */
  item: string | null;
  /**
   * Optional project filter for the forge reader: a PROJECT_FILTERS key ("voice"), "ring" for the
   * winners on the ring, "every" for all projects, or a year ("2025"). Ignored by the other areas.
   */
  filter?: string;
}

const ITEM_AREA: Record<string, AreaId> = {
  project: "forge",
  hackathon: "arena",
  role: "mission",
  school: "library",
  skills: "steles",
  arch: "formation",
  fact: "abode",
  resume: "scroll",
  moon: "summit",
};

/** How many indexed items each item prefix has (hackathon:0..35, role:0..6, ...). */
export function itemCount(prefix: string): number {
  switch (prefix) {
    case "hackathon":
      return HACKATHONS.length;
    case "role":
      return EXPERIENCE.length;
    case "school":
      return EDUCATION.length;
    case "skills":
      return skillGroups().length;
    case "arch":
      return formationItems().length;
    case "fact":
      return PERSONAL_FACTS.length;
    default:
      return 0;
  }
}

/** Splits "project:dispatchai" into ["project", "dispatchai"]; "gate-lions" into ["gate", "lions"]. */
function splitId(id: string): { head: string; rest: string | null; sep: string | null } {
  const m = /^([a-z0-9]+)(?:([-:])(.*))?$/i.exec(id.trim());
  if (!m) return { head: id, rest: null, sep: null };
  return { head: m[1], rest: m[3] ?? null, sep: m[2] ?? null };
}

/** The index of an indexed item id ("role:3" -> 3), or null when it is not one. */
export function itemIndex(item: string | null | undefined, prefix: string): number | null {
  if (!item) return null;
  const { head, rest, sep } = splitId(item);
  if (head !== prefix || sep !== ":" || rest === null || !/^\d+$/.test(rest)) return null;
  const i = Number(rest);
  return i < itemCount(prefix) ? i : null;
}

/** The project of a "project:<id or alias>" item, or undefined. */
export function itemProject(item: string | null | undefined): Project | undefined {
  if (!item) return undefined;
  const { head, rest, sep } = splitId(item);
  if (head !== "project" || sep !== ":" || !rest) return undefined;
  return findProject(rest);
}

/**
 * The project item a slug names: a curated project by id or alias ("dispatch-ai" -> project:dispatchai),
 * else any slug-shaped id as is, lower-cased ("project:talktuahbank"). The forge reader loads such an
 * id from the archive of every project the voice agent knows, like the main page does, and says so
 * when it is not there either. Null when the text cannot be a project id.
 */
export function projectItem(slug: string): string | null {
  const raw = slug.trim();
  const known = findProject(raw) ?? findProject(raw.toLowerCase());
  if (known) return `project:${known.id}`;
  return /^[a-z0-9][a-z0-9_-]{0,79}$/i.test(raw) ? `project:${raw.toLowerCase()}` : null;
}

/** Which section (and item) a hotspot opens, or null when the hotspot is decorative or unknown. */
export function hotspotTarget(hotspotId: string): ContentTarget | null {
  const id = hotspotId.trim();
  const { head, rest, sep } = splitId(id);
  if (isAreaId(head)) {
    // "<area>": the whole section. "<area>-<thing>": the spot's own view when it has one, else
    // the whole section.
    if (sep === ":") return null;
    return { area: head, item: isThing(id) ? id : null };
  }
  const area = ITEM_AREA[head];
  if (!area) return null;
  if (head === "resume" || head === "moon") return sep === null ? { area, item: head } : null;
  if (head === "project") {
    // Curated ids resolve through aliases; other slugs open in the forge reader, which loads them
    // from the archive (or says it couldn't find them).
    const item = sep === ":" && rest ? projectItem(rest) : null;
    return item ? { area, item } : null;
  }
  if (sep !== ":" || rest === null) return null;
  const i = itemIndex(id, head);
  return i === null ? null : { area, item: `${head}:${i}` };
}

/** Hotspot ids belong to an area by prefix ("mirror-pond" -> "mirror", "project:x" -> "forge"). */
export function hotspotArea(id: string): string {
  const t = hotspotTarget(id);
  if (t) return t.area;
  return splitId(id).head;
}

// ---- labels -----------------------------------------------------------------------------------

export interface HotspotLabel {
  title: string;
  zh?: string;
  blurb?: string;
}

/** Remove the <b> markup PERSONAL_FACTS carry. */
export function stripTags(html: string): string {
  return html.replace(/<[^>]*>/g, "");
}

/** A personal fact as text runs, so it renders bold without dangerouslySetInnerHTML. */
export function factRuns(html: string): { t: string; b: boolean }[] {
  const out: { t: string; b: boolean }[] = [];
  const re = /<b>(.*?)<\/b>/g;
  let last = 0;
  for (let m = re.exec(html); m; m = re.exec(html)) {
    if (m.index > last) out.push({ t: stripTags(html.slice(last, m.index)), b: false });
    out.push({ t: stripTags(m[1]), b: true });
    last = m.index + m[0].length;
  }
  if (last < html.length) out.push({ t: stripTags(html.slice(last)), b: false });
  return out.filter((r) => r.t.length > 0);
}

/** A short label for a personal fact: its first clause, at most about 60 characters. */
export function shortFact(html: string): string {
  const text = stripTags(html).trim();
  const clause = text.split(/[:;.]\s/)[0].replace(/[.:;]$/, "");
  if (clause.length <= 60) return clause;
  const cut = clause.slice(0, 57);
  return `${cut.slice(0, cut.lastIndexOf(" "))}…`;
}

/** The company part of an experience "where" ("Pinterest · San Francisco" -> "Pinterest"). */
export function company(where: string): string {
  return where.split("·")[0].trim();
}

/** Name and year of a hackathon ("HackUTD 2024"). */
export function hackathonTitle(i: number): string {
  const h = HACKATHONS[i];
  return h.year ? `${h.name} ${h.year}` : h.name;
}

/** The five skill phrases of the skills line, one per stele row (front to back). */
export interface SkillGroup {
  index: number;
  /** The phrase, without its trailing punctuation. */
  label: string;
  /** Indices into SKILLS_LINE that this row lights up. */
  words: number[];
}

/**
 * The skills section is one sentence (SKILLS_LINE). Its key phrases are the five things it says
 * Bill builds and cares about: "voice-first" plus the four tagged phrases. Each stele row carries
 * one, in reading order.
 */
export function skillGroups(): SkillGroup[] {
  const picks: number[] = [];
  SKILLS_LINE.forEach((w, i) => {
    if (w.tag || /voice/i.test(w.w)) picks.push(i);
  });
  return picks.map((wi, index) => ({
    index,
    label: SKILLS_LINE[wi].w.replace(/[.,;:]+$/, ""),
    words: [wi],
  }));
}

/** The skills line as one sentence. */
export function skillsSentence(): string {
  return SKILLS_LINE.map((w) => w.w).join(" ");
}

/** The formation's eight pillars: the six flow steps, then the stack and the code. */
export function formationItems(): { id: string; title: string; blurb: string }[] {
  return [
    ...ARCH_FLOW.map((f, i) => ({ id: `arch:${i}`, title: `${f.k} ${f.title}`, blurb: f.body })),
    { id: "arch:6", title: "Stack", blurb: ARCH_STACK.map((s) => s.group).join(" · ") },
    { id: "arch:7", title: "Code", blurb: "metadata event → bus command → scroll" },
  ];
}

const AREA_THINGS: Record<string, { name?: string; zh?: string; body?: string }> = {
  gate: {
    zh: "山门",
    body: "The paifang of the Ming Sect. Every disciple passes beneath its three tiers of teal tile on the first climb.",
  },
  "gate-lions": { name: "Guardian Lions", zh: "石狮" },
  "gate-swords": { name: "Sword Monoliths", zh: "剑碑" },
  mirror: {
    zh: "心镜",
    body: "The Heart-Mirror. Disciples come here to see what they actually want, not what they say they want.",
  },
  "mirror-pavilion": { name: "Pond Pavilion", zh: "水亭" },
  "mirror-pond": { name: "Still Pond", zh: "静池" },
  "mirror-blossom": { name: "Peach Blossom", zh: "桃花" },
  "mirror-censer": { name: "Incense Burner", zh: "香炉" },
  "forge-hall": { name: "Forge Hall", zh: "炼器殿" },
  "arena-judges": { name: "Judges' Pavilion", zh: "评判亭" },
  "mission-bell": { name: "Bell Tower", zh: "钟楼" },
  "library-pond": { name: "Lotus Pond", zh: "莲池" },
  "abode-cranes": { name: "Cranes in Flight", zh: "仙鹤" },
  "summit-arch": { name: "Crescent Moon Arch", zh: "月门" },
  "summit-cranes": { name: "Cranes to the Moon", zh: "鹤归月" },
};

/**
 * The named spots of each area that open their own view (hotspot ids, scene order). The area's
 * landmark ("<area>") opens the whole section; these open something of their own.
 */
export const AREA_THING_IDS: Partial<Record<AreaId, readonly string[]>> = {
  gate: ["gate-lions", "gate-swords"],
  mirror: ["mirror-pond", "mirror-censer", "mirror-blossom", "mirror-pavilion"],
  forge: ["forge-hall"],
  arena: ["arena-judges"],
  mission: ["mission-bell"],
  library: ["library-pond"],
  abode: ["abode-cranes"],
  summit: ["summit-arch", "summit-cranes"],
};

const THING_AREA = new Map<string, AreaId>(
  Object.entries(AREA_THING_IDS).flatMap(([area, ids]) => (ids ?? []).map((id) => [id, area as AreaId] as const)),
);

/** True for a named spot with its own view ("gate-lions"). */
export function isThing(id: string): boolean {
  return THING_AREA.has(id);
}

/** The area a named spot belongs to, or null. */
export function thingArea(id: string): AreaId | null {
  return THING_AREA.get(id) ?? null;
}

/** A named spot's name and Chinese name (an area's landmark also carries a line about it). */
export function thingLore(id: string): { name?: string; zh?: string; body?: string } | null {
  return AREA_THINGS[id] ?? null;
}

/** "lions" -> "Lions", "koi-pool" -> "Koi pool". */
function prettyThing(thing: string): string {
  const s = thing.replace(/[-_]+/g, " ").trim();
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

/**
 * Short text for the hover label and the Places list. Item ids get their label from the real data
 * (project name, hackathon, role and company, school, skill phrase, flow step, fact); area ids get
 * the place name, or `fallback` (the glTF label) for a thing in an area.
 */
export function hotspotLabel(hotspotId: string, fallback?: string): HotspotLabel {
  const id = hotspotId.trim();
  const t = hotspotTarget(id);
  if (!t) return { title: fallback ?? id };
  const info = areaInfo(t.area);
  if (t.item === null || isThing(id)) {
    const thing = AREA_THINGS[id];
    if (id === t.area) return { title: info.label, zh: info.zh, blurb: areaSummary(t.area).title };
    const rest = splitId(id).rest ?? "";
    return { title: fallback ?? thing?.name ?? prettyThing(rest), zh: thing?.zh };
  }
  const item = t.item;
  const head = splitId(item).head;
  switch (head) {
    case "project": {
      const p = itemProject(item);
      if (!p) break;
      const award = projectAward(p.id);
      return { title: p.name, blurb: award ? `★ ${award}` : p.summary };
    }
    case "hackathon": {
      const i = itemIndex(item, "hackathon")!;
      const h = HACKATHONS[i];
      return { title: hackathonTitle(i), blurb: `${h.project} · ★ ${h.prize}` };
    }
    case "role": {
      const r = EXPERIENCE[itemIndex(item, "role")!];
      return { title: `${r.role} · ${company(r.where)}`, blurb: r.when };
    }
    case "school": {
      const e = EDUCATION[itemIndex(item, "school")!];
      return { title: e.full, blurb: `${e.degree} · ${e.when}` };
    }
    case "skills": {
      const g = skillGroups()[itemIndex(item, "skills")!];
      return { title: g.label };
    }
    case "arch": {
      const a = formationItems()[itemIndex(item, "arch")!];
      return { title: a.title, blurb: a.blurb };
    }
    case "fact": {
      const f = PERSONAL_FACTS[itemIndex(item, "fact")!];
      const title = shortFact(f.line);
      const full = stripTags(f.line);
      return full.replace(/\.$/, "") === title ? { title } : { title, blurb: full };
    }
    case "resume":
      return { title: "Resume" };
    case "moon":
      return { title: "The moon", zh: "明月", blurb: "Talk to the AI" };
  }
  return { title: fallback ?? id };
}

/** Every item-level hotspot id of an area, in scene order, with its label. */
export function areaItemHotspots(area: AreaId): { id: string; label: string }[] {
  const ids: string[] = [];
  switch (area) {
    case "forge":
      PROJECTS.forEach((p) => ids.push(`project:${p.id}`));
      break;
    case "arena":
      HACKATHONS.forEach((_, i) => ids.push(`hackathon:${i}`));
      break;
    case "mission":
      EXPERIENCE.forEach((_, i) => ids.push(`role:${i}`));
      break;
    case "library":
      EDUCATION.forEach((_, i) => ids.push(`school:${i}`));
      break;
    case "steles":
      skillGroups().forEach((_, i) => ids.push(`skills:${i}`));
      break;
    case "scroll":
      ids.push("resume");
      break;
    case "formation":
      formationItems().forEach((a) => ids.push(a.id));
      break;
    case "abode":
      PERSONAL_FACTS.forEach((_, i) => ids.push(`fact:${i}`));
      break;
    case "summit":
      ids.push("moon");
      break;
  }
  return ids.map((id) => ({ id, label: hotspotLabel(id).title }));
}

// ---- area summaries (the panel at each camera hold) ------------------------------------------

export interface AreaSummary {
  area: AreaId;
  /** English place name. */
  eyebrow: string;
  /** Chinese place name. */
  zh: string;
  /** Title of the panel (the section, or the name at the gate). */
  title: string;
  /** Name of the main-page section this area presents, for the reader header. */
  section: string;
  /** At most one short line. */
  lines: string[];
  /** The label of the button that opens the reader ("Open"). */
  action: string;
  /** Default side of the screen for the panel on wide screens. */
  side: "left" | "right";
}

/** Main-page section names, as the section eyebrows read (sentence case). */
export const SECTION_NAMES: Record<AreaId, string> = {
  gate: "Welcome",
  mirror: "About",
  forge: "Projects",
  arena: "Hackathons",
  mission: "Experience",
  library: "Education",
  steles: "Skills",
  scroll: "Resume",
  formation: "How this site works",
  abode: "Off the clock",
  summit: "Contact",
};

export function areaSummary(area: AreaId): AreaSummary {
  const info = areaInfo(area);
  const index = AREA_IDS.indexOf(area);
  const base = {
    area,
    eyebrow: info.label,
    zh: info.zh,
    section: SECTION_NAMES[area],
    action: "Open",
    side: (index % 2 === 0 ? "left" : "right") as "left" | "right",
  };
  const now = EXPERIENCE[0];
  switch (area) {
    case "gate":
      return {
        ...base,
        title: PORTFOLIO.name,
        lines: [PORTFOLIO.tagline],
      };
    case "mirror":
      return {
        ...base,
        title: "About",
        lines: [
          "By day I build LLM agents at Pinterest. By night I build software you can talk to, which is how I ended up with 36 hackathon wins.",
        ],
      };
    case "forge":
      return {
        ...base,
        title: "Projects",
        lines: [`${PROJECTS.length} projects, ${FORGE_RING.length} prize winners.`],
      };
    case "arena":
      return {
        ...base,
        title: "Hackathons",
        lines: [`${HACKATHONS.length} wins during college. $150k+ in prizes.`],
      };
    case "mission":
      return {
        ...base,
        title: "Experience",
        lines: [now ? `Now: ${now.role} at ${company(now.where)}.` : ""].filter(Boolean),
      };
    case "library":
      return {
        ...base,
        title: "Education",
        lines: [EDUCATION.map((e) => e.school).join(" · ")],
      };
    case "steles":
      return {
        ...base,
        title: "Skills",
        lines: [skillsSentence()],
      };
    case "scroll":
      return {
        ...base,
        title: "Resume",
        lines: [],
      };
    case "formation":
      return {
        ...base,
        title: "How this site works",
        lines: [],
      };
    case "abode":
      return {
        ...base,
        title: "Off the clock",
        lines: [],
      };
    case "summit":
      return {
        ...base,
        title: "Contact",
        lines: [],
      };
  }
}

/** The previous and next area in flight order. */
export function neighborAreas(area: AreaId): { prev: AreaId | null; next: AreaId | null } {
  const i = AREA_IDS.indexOf(area);
  return { prev: i > 0 ? AREA_IDS[i - 1] : null, next: i < AREA_IDS.length - 1 ? AREA_IDS[i + 1] : null };
}

// ---- projects ---------------------------------------------------------------------------------

/**
 * The forge reader's filters: the main page's, with "On the ring" (the winners whose artifacts
 * circle the cauldron, the default) and "All" added.
 */
export const FORGE_FILTERS: readonly { key: string; label: string }[] = [
  { key: "ring", label: "On the ring" },
  { key: "every", label: `All ${PROJECTS.length}` },
  ...PROJECT_FILTERS,
];

export const STANDOUT_IDS: readonly string[] = STANDOUT_PROJECT_IDS;

/** Normalize a filter: a FORGE_FILTERS key or a year (over all projects); anything else is "ring". */
export function parseFilter(filter: string | undefined | null): { filter: string; year: number | null } {
  if (filter && /^\d{4}$/.test(filter)) return { filter: "every", year: Number(filter) };
  if (filter && FORGE_FILTERS.some((f) => f.key === filter)) return { filter, year: null };
  return { filter: "ring", year: null };
}

/**
 * The projects a filter shows, in PROJECTS order, like the main page: "all" is the six hand-picked
 * standouts (in their curated order), a tag shows every project carrying it, a year narrows it.
 * "ring" is the ring's winners, biggest win first.
 */
export function filterProjects(filter: string, year: number | null): Project[] {
  if (filter === "all" && !year) {
    return STANDOUT_IDS.map((id) => PROJECTS.find((p) => p.id === id)).filter((p): p is Project => Boolean(p));
  }
  if (filter === "ring") {
    return FORGE_RING.map((id) => PROJECTS.find((p) => p.id === id)).filter(
      (p): p is Project => Boolean(p) && (!year || p!.year === year),
    );
  }
  return PROJECTS.filter((p) => {
    if (year && p.year !== year) return false;
    if (filter === "all" || filter === "every") return true;
    return p.tags.includes(filter);
  });
}

/** What the detail view shows as media, matching the main page's ProjectDetail. */
export function projectMedia(p: Project): { demoLink?: string; embed: string | null; image: string | null } {
  const demoLink = p.videoUrl ?? p.demo;
  const embed = toEmbed(demoLink);
  const image = !embed && isImage(p.demo) ? (p.demo ?? null) : null;
  return { demoLink, embed, image };
}

/** The project a hackathon was won with, when it is one of the 15 ("DispatchAI" -> dispatchai). */
export function hackathonProject(i: number): Project | undefined {
  const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");
  const want = norm(HACKATHONS[i]?.project ?? "");
  if (!want) return undefined;
  return PROJECTS.find((p) => norm(p.name) === want || norm(p.id) === want);
}

// ---- navigation helpers -----------------------------------------------------------------------

/** Where a main-page voice or chip command goes in the sect. */
export function commandTarget(cmd: VoiceCommand): ContentTarget | null {
  switch (cmd.type) {
    case "filter":
      if (cmd.tag) return { area: "forge", item: null, filter: cmd.tag === "all" ? "all" : cmd.tag };
      if (cmd.year) return { area: "forge", item: null, filter: String(cmd.year) };
      return { area: "forge", item: null };
    case "focus":
    case "open": {
      const p = findProject(cmd.id);
      return { area: "forge", item: `project:${p?.id ?? cmd.id}` };
    }
    case "scroll": {
      const area = areaForSection(cmd.id) ?? (isAreaId(cmd.id) ? cmd.id : null);
      return area ? { area, item: null } : null;
    }
  }
}

/** Where a hero chip goes, mirroring HeroSection.onChip. */
export function heroChipTarget(chip: string): ContentTarget {
  const lower = chip.toLowerCase();
  if (lower.includes("voice ai")) return { area: "forge", item: null, filter: "voice" };
  if (lower.includes("hackathon")) return { area: "arena", item: null };
  if (lower.includes("projects")) return { area: "forge", item: null };
  if (lower.includes("fun")) return { area: "abode", item: null };
  return { area: "mirror", item: null };
}

export const HERO_CHIP_TARGETS = HERO_CHIPS.map((chip) => ({ chip, target: heroChipTarget(chip) }));

/**
 * A URL hash as a content target: "#project/<id>" (the main page's project deep link), a main-page
 * section id ("#projects") or an area id ("#forge"). Null for anything else.
 */
export function parseContentHash(hash: string): ContentTarget | null {
  let h: string;
  try {
    h = decodeURIComponent(hash.replace(/^#/, "")).trim();
  } catch {
    // A lone "%" or a link cut mid-escape ("#project/caf%E9"): not a target, and never a crash.
    return null;
  }
  if (!h) return null;
  if (/^project\//i.test(h)) {
    const item = projectItem(h.slice("project/".length));
    return item ? { area: "forge", item } : null;
  }
  const key = h.toLowerCase();
  const area = areaForSection(key) ?? (isAreaId(key) ? key : null);
  return area ? { area, item: null } : null;
}

/** The main page's section id of an area ("forge" -> "projects"): the hash a link to it uses. */
export function sectionDomId(area: AreaId): string {
  return areaInfo(area).sectionId;
}

/**
 * DOM id of an area's section in the one-page view. Deliberately not the main page's id: the voice
 * orb scrolls the window to an element with that id, which would move the flight hidden behind.
 */
export function pageSectionDomId(area: AreaId): string {
  return `sc-page-area-${area}`;
}

/** DOM id of an item inside a reader or the page view ("project:dispatchai" -> "sect-item-project-dispatchai"). */
export function itemDomId(item: string): string {
  return `sect-item-${item.replace(/[^a-z0-9]+/gi, "-")}`;
}

/** Areas in flight order with their names, for navigation lists. */
export function areaNav(): { id: AreaId; label: string; zh: string; section: string }[] {
  return AREAS.map((a) => ({ id: a.id, label: a.label, zh: a.zh, section: SECTION_NAMES[a.id] }));
}

// ---- prototype API (kept while the engine still uses it) -------------------------------------

export interface HoldPanel {
  id: string;
  eyebrow: string;
  /** Chinese name of the place, shown small beside the eyebrow. */
  zh: string;
  title: string;
  body: string[];
  side: "left" | "right";
}

export function holdPanels(): Record<string, HoldPanel> {
  const out: Record<string, HoldPanel> = {};
  for (const id of AREA_IDS) {
    const s = areaSummary(id);
    out[id] = { id, eyebrow: s.eyebrow, zh: s.zh, title: s.title, body: s.lines, side: s.side };
  }
  return out;
}

export interface HotspotCard {
  title: string;
  zh?: string;
  body: string;
}

export function hotspotCard(id: string, label: string): HotspotCard {
  const t = hotspotTarget(id);
  if (t?.item) {
    const l = hotspotLabel(id, label);
    return { title: l.title, zh: l.zh, body: l.blurb ?? "" };
  }
  const thing = AREA_THINGS[id];
  return { title: label || id, zh: thing?.zh, body: thing?.body ?? "" };
}
