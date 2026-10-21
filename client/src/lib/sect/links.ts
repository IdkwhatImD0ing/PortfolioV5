/**
 * The /sect URL and browser history: where a link lands (?open=<hotspot id>, #section,
 * #project/<id>), the URL that names an open reader (so it can be shared, and Back closes it), and
 * the page's own entries in history.state. Pure functions.
 */
import { areaInfo, isAreaId } from "./areas";
import { SECTION_NAMES, hotspotTarget, parseContentHash, type ContentTarget } from "./content";

/** Where the page opens, and whether the reader opens there too. */
export interface DeepLink {
  target: ContentTarget;
  open: boolean;
}

export interface DeepLinkResult {
  link: DeepLink | null;
  /** A link that asked for something the page does not have: what to tell the visitor, or null. */
  note: string | null;
}

/**
 * Resolves the page's starting point from ?open= and the hash. `?open=` wins. An item that does not
 * exist in a section that does ("hackathon:999") opens that section with a note; anything else
 * unknown starts at the beginning with a note. Unknown projects resolve to the forge, whose reader
 * says it couldn't find them.
 */
export function resolveDeepLink(open: string | null, hash: string): DeepLinkResult {
  let note: string | null = null;
  if (open) {
    const t = hotspotTarget(open);
    if (t) return { link: { target: t, open: true }, note: null };
    const head = open.split(":")[0];
    const section = hotspotTarget(`${head}:0`) ?? hotspotTarget(head);
    if (section) {
      return {
        link: { target: { area: section.area, item: null }, open: true },
        note: `Couldn't find "${open}", so here is all of ${SECTION_NAMES[section.area]}.`,
      };
    }
    note = `"${open}" isn't here.`;
  }
  const t = parseContentHash(hash);
  if (t) return { link: { target: t, open: t.item !== null }, note };
  const raw = hash.replace(/^#/, "").trim();
  if (raw && !note) note = `"#${raw.slice(0, 40)}" isn't here.`;
  return { link: null, note };
}

/** The page's own entries in history.state (under one key; Next.js keeps its own keys beside it). */
export interface SectHistoryState {
  /** The reader open at this entry, or null. */
  reader: ContentTarget | null;
  /** The one-page view is open at this entry. */
  page: boolean;
  /** Entries the page pushed above the one the visitor arrived on (0: that one). */
  depth: number;
  /** A project opened inside the reader, pushed above the reader's own entry (Back: the list). */
  nested: boolean;
}

const KEY = "sect";

function readTarget(v: unknown): ContentTarget | null {
  if (!v || typeof v !== "object") return null;
  const o = v as Record<string, unknown>;
  if (typeof o.area !== "string" || !isAreaId(o.area)) return null;
  const item = typeof o.item === "string" ? o.item : null;
  const t: ContentTarget = { area: o.area, item };
  if (typeof o.filter === "string") t.filter = o.filter;
  return t;
}

/** The page's state in a history entry, or null for an entry it did not write. */
export function readHistoryState(state: unknown): SectHistoryState | null {
  if (!state || typeof state !== "object") return null;
  const s = (state as Record<string, unknown>)[KEY];
  if (!s || typeof s !== "object") return null;
  const o = s as Record<string, unknown>;
  const depth = typeof o.depth === "number" && Number.isFinite(o.depth) ? Math.max(0, Math.floor(o.depth)) : 0;
  return { reader: readTarget(o.reader), page: o.page === true, depth, nested: o.nested === true };
}

/** `prev` (the entry's current state, Next.js's keys included) with the page's state set. */
export function withHistoryState(prev: unknown, s: SectHistoryState): Record<string, unknown> {
  const base = prev && typeof prev === "object" ? (prev as Record<string, unknown>) : {};
  const reader = s.reader ? { area: s.reader.area, item: s.reader.item, ...(s.reader.filter ? { filter: s.reader.filter } : {}) } : null;
  return { ...base, [KEY]: { reader, page: s.page, depth: s.depth, nested: s.nested } };
}

/** `prev` without the page's state (the entry is plain again). */
export function withoutHistoryState(prev: unknown): Record<string, unknown> | null {
  if (!prev || typeof prev !== "object") return null;
  const { [KEY]: _drop, ...rest } = prev as Record<string, unknown>;
  void _drop;
  return rest;
}

/** The query string without ?open= (the other options, like ?debug=1, stay). */
export function searchWithout(search: string, ...names: string[]): string {
  const q = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  for (const n of names) q.delete(n);
  const s = q.toString();
  return s ? `?${s}` : "";
}

function searchWith(search: string, name: string, value: string): string {
  const q = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  q.set(name, value);
  return `?${q.toString().replace(/%3A/gi, ":")}`;
}

/**
 * The URL of an open reader: "#project/<id>" for a project (the main page's own link), else
 * "?open=<item or area>#<section>", which resolveDeepLink opens again.
 */
export function readerUrl(t: ContentTarget, pathname: string, search: string): string {
  const section = `#${areaInfo(t.area).sectionId}`;
  if (t.item?.startsWith("project:")) {
    return `${pathname}${searchWithout(search, "open")}#project/${encodeURIComponent(t.item.slice("project:".length))}`;
  }
  return `${pathname}${searchWith(search, "open", t.item ?? t.area)}${section}`;
}

/** The URL with no reader open: the area's section hash (or none), without ?open=. */
export function plainUrl(area: string | null, pathname: string, search: string): string {
  const hash = area && isAreaId(area) ? `#${areaInfo(area).sectionId}` : "";
  return `${pathname}${searchWithout(search, "open")}${hash}`;
}
