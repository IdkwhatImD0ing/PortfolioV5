/**
 * The links between things in the sect, for the item detail views: a clicked tablet, banner, floor,
 * stele row, pillar, fact or named spot opens its own view, and these say where a skill shows up
 * in the work and which wins are the biggest.
 * Everything quoted comes from portfolio-data and the main page's copy; nothing is made up here.
 *
 * Pure: no React.
 */
import { EDUCATION, EXPERIENCE, HACKATHONS, PERSONAL_FACTS, PROJECTS, type Project } from "@/lib/portfolio-data";
import { ABOUT_CARDS, ARCH_FLOW, ARCH_STACK } from "./content-copy";
import { AREA_THING_IDS, formationItems, skillGroups, thingArea, type ContentTarget } from "./content";

// ---- siblings -----------------------------------------------------------------------------------

/** The indexed items of a kind, in order: "role" -> role:0..6. */
function kindIds(kind: string): string[] {
  switch (kind) {
    case "hackathon":
      return HACKATHONS.map((_, i) => `hackathon:${i}`);
    case "role":
      return EXPERIENCE.map((_, i) => `role:${i}`);
    case "school":
      return EDUCATION.map((_, i) => `school:${i}`);
    case "skills":
      return skillGroups().map((g) => `skills:${g.index}`);
    case "arch":
      return formationItems().map((a) => a.id);
    case "fact":
      return PERSONAL_FACTS.map((_, i) => `fact:${i}`);
    default:
      return [];
  }
}

/** The item before and after this one among its kind (or its area's named spots), for the pager. */
export function itemSiblings(item: string): { prev: string | null; next: string | null } {
  const area = thingArea(item);
  const ring = area ? [...(AREA_THING_IDS[area] ?? [])] : kindIds(item.split(":")[0]);
  const i = ring.indexOf(item);
  if (i < 0) return { prev: null, next: null };
  return { prev: i > 0 ? ring[i - 1] : null, next: i < ring.length - 1 ? ring[i + 1] : null };
}

// ---- time spans ---------------------------------------------------------------------------------

const MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];

/** A point in time as a month count (year * 12 + month index). */
function monthOf(text: string, end: boolean): number | null {
  const m = /^(?:([a-z]{3})[a-z]*\s+)?(\d{4})(\+)?$/i.exec(text.trim());
  if (!m) return null;
  const year = Number(m[2]);
  const mi = m[1] ? MONTHS.indexOf(m[1].toLowerCase()) : end ? 11 : 0;
  if (mi < 0) return null;
  return year * 12 + mi;
}

export interface Span {
  /** Months since year 0 (year * 12 + month index). */
  start: number;
  end: number;
  /** Still going ("Now", "2025+"). */
  open: boolean;
}

/**
 * "Jun 2025 — Jul 2026", "Jul 2026 — Now", "2023 — 2025+", "2016 — 2020" as months. A year without a
 * month covers that whole year. "Now" ends at `now`. Null when the text is not a span.
 */
export function parseSpan(when: string, now: Date): Span | null {
  const parts = when.split(/\s*[—–-]\s*/);
  if (parts.length !== 2) return null;
  const start = monthOf(parts[0], false);
  const nowMonth = now.getFullYear() * 12 + now.getMonth();
  const isNow = /^now$/i.test(parts[1].trim());
  const end = isNow ? nowMonth : monthOf(parts[1], true);
  if (start === null || end === null || end < start) return null;
  return { start, end: Math.max(end, start), open: isNow || /\+\s*$/.test(parts[1]) };
}

/** Calendar years a span touches. */
export function spanYears(s: Span): [number, number] {
  return [Math.floor(s.start / 12), Math.floor(s.end / 12)];
}

/** The roles laid out on one time axis: each role's share of it, for the mission timeline. */
export function roleTimeline(now: Date): { from: number; to: number; rows: { item: string; left: number; width: number; open: boolean }[] } {
  const spans = EXPERIENCE.map((r) => parseSpan(r.when, now));
  const known = spans.filter((s): s is Span => s !== null);
  const from = Math.min(...known.map((s) => Math.floor(s.start / 12))) * 12;
  const to = (Math.max(...known.map((s) => Math.floor(s.end / 12))) + 1) * 12;
  const total = Math.max(1, to - from);
  return {
    from: from / 12,
    to: to / 12,
    rows: EXPERIENCE.map((_, i) => {
      const s = spans[i];
      if (!s) return { item: `role:${i}`, left: 0, width: 0, open: false };
      return {
        item: `role:${i}`,
        left: (s.start - from) / total,
        width: Math.max(1, s.end - s.start + 1) / total,
        open: s.open,
      };
    }),
  };
}

// ---- related items ------------------------------------------------------------------------------

export interface Related {
  target: ContentTarget;
  title: string;
  /** Small text under the title (a prize, a year, the quoted line). */
  note?: string;
}

function projectRelated(p: Project, note?: string): Related {
  return { target: { area: "forge", item: `project:${p.id}` }, title: p.name, note: note ?? (p.award ? `★ ${p.award}` : p.summary) };
}

function hackathonRelated(i: number): Related {
  const h = HACKATHONS[i];
  return { target: { area: "arena", item: `hackathon:${i}` }, title: h.year ? `${h.name} ${h.year}` : h.name, note: `★ ${h.prize} · ${h.project}` };
}

/** The biggest wins: grand prizes and first places, in the list's order (most impressive first). */
export function topPrizes(): Related[] {
  const out: Related[] = [];
  HACKATHONS.forEach((h, i) => {
    if (/grand prize|1st|first/i.test(h.prize)) out.push(hackathonRelated(i));
  });
  return out;
}

// ---- skills: where each phrase shows up ---------------------------------------------------------

/** What to look for in the work for each stele row (skillGroups order). */
const SKILL_PATTERNS: RegExp[] = [
  /\bvoice\b|phone call|by voice|speak/i,
  /\bagents?\b|multi-agent/i,
  /latenc|real[- ]time|\blive\b|faster/i,
  /\bhumans?\b|hand-?offs?|dispatcher|responders/i,
  /\beval|guardrail|accuracy|wrong|fail|judge|validation/i,
];

/** The first sentence of `text` matching `re`, trimmed to about 200 characters. */
export function matchingSentence(text: string, re: RegExp): string | null {
  const sentences = text.split(/(?<=[.!?])\s+/);
  const hit = sentences.find((s) => re.test(s));
  if (!hit) return null;
  const s = hit.trim();
  return s.length <= 200 ? s : `${s.slice(0, 197).replace(/\s+\S*$/, "")}…`;
}

/** Lines from the work that show a stele row's phrase: roles, projects, About cards, the formation. */
export function skillEvidence(group: number, limit = 8): Related[] {
  const re = SKILL_PATTERNS[group];
  if (!re) return [];
  const out: Related[] = [];
  EXPERIENCE.forEach((r, i) => {
    const line = r.bullets.map((b) => matchingSentence(b, re)).find(Boolean);
    if (line) out.push({ target: { area: "mission", item: `role:${i}` }, title: `${r.role} · ${r.where.split("·")[0].trim()}`, note: line });
  });
  for (const p of PROJECTS) {
    const line = matchingSentence(`${p.summary} ${p.long ?? ""}`, re);
    if (line) out.push(projectRelated(p, line));
  }
  ABOUT_CARDS.forEach((c, i) => {
    const line = matchingSentence(`${c.title} ${c.body}`, re);
    const thing = MIRROR_CARD_THINGS[i];
    if (line && thing) out.push({ target: { area: "mirror", item: thing }, title: c.title, note: line });
  });
  ARCH_FLOW.forEach((f, i) => {
    const line = matchingSentence(f.body, re);
    if (line) out.push({ target: { area: "formation", item: `arch:${i}` }, title: `${f.k} ${f.title}`, note: line });
  });
  // Mix the sources so the first few are not all roles: one of each kind in turn.
  const byKind = new Map<string, Related[]>();
  for (const r of out) {
    const k = r.target.area;
    byKind.set(k, [...(byKind.get(k) ?? []), r]);
  }
  const mixed: Related[] = [];
  const lists = [...byKind.values()];
  for (let i = 0; mixed.length < out.length; i++) {
    for (const l of lists) if (l[i]) mixed.push(l[i]);
  }
  return mixed.slice(0, limit);
}

// ---- formation ----------------------------------------------------------------------------------

/** The stack groups behind each flow step (by what the step's text describes). */
const STEP_STACK: string[][] = [["Voice"], ["Brain"], ["Brain"], ["State"], ["Frame", "State"], ["Voice"]];

export function stepStack(step: number): { group: string; items: string[] }[] {
  const groups = STEP_STACK[step] ?? [];
  return ARCH_STACK.filter((s) => groups.includes(s.group)).map((s) => ({ group: s.group, items: [...s.items] }));
}

/** Which flow steps each stack group powers (the inverse of stepStack). */
export function stackSteps(group: string): number[] {
  return STEP_STACK.flatMap((g, i) => (g.includes(group) ? [i] : []));
}

// ---- named spots --------------------------------------------------------------------------------

/** The Heart-Mirror's four spots each hold one About card (ABOUT_CARDS order). */
export const MIRROR_CARD_THINGS = ["mirror-pond", "mirror-censer", "mirror-blossom", "mirror-pavilion"] as const;

export function mirrorCardIndex(thing: string): number {
  return (MIRROR_CARD_THINGS as readonly string[]).indexOf(thing);
}
