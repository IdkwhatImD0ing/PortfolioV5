/**
 * The Jin Yong references in the scene (the sect's owner is a big fan): what each one is, in a few
 * plain words, for the small card the page shows when the pointer rests on one (a tap on a touch
 * screen). Decorative only: never a hotspot, never in the rail, the Places list or the progress, and
 * never opens anything.
 *
 * Their hover boxes come from meta.json "lore" (blender/xianxia-sect/sect/export_web.py LORE, the
 * same ids). A meta.json without them shows no cards and the page works as before. A box the
 * exporter found inside a content hotspot (the gate's swords, the arena's sword, the gate's sun and
 * moon) never gets a card of its own: the hotspot keeps the pointer and the click, and its hover
 * label carries the reference's name on one quiet extra line instead (loreNote).
 *
 * Pure: no React, no three.js.
 */
import type { AreaId } from "./areas";
import { rayBoxSpan, type BoxHit } from "./pick";
import type { LoreBox, Vec3 } from "./types";

/** The novels, by their usual English titles. */
export const NOVELS = {
  heavenSword: "Heaven Sword and Dragon Saber",
  condorReturn: "Return of the Condor Heroes",
  condorLegend: "Legend of the Condor Heroes",
  wanderer: "The Smiling, Proud Wanderer",
} as const;

export interface LoreEntry {
  /** Chinese name, in traditional characters as the novels were first printed. */
  zh: string;
  /** English name. */
  en: string;
  /** What it is, in a few plain words (the card's line adds the novel). */
  what: string;
  /** The novel it comes from, or null when the line says it all. */
  novel: string | null;
  /** The stop it belongs to (the screen reader list on that stop's panel). */
  area: AreaId;
}

/** Every reference, in flight order. Ids match export_web.py LORE. */
export const LORE = {
  "heaven-sword": {
    zh: "倚天劍",
    en: "Heaven Sword",
    what: "The Dragon Saber's only rival",
    novel: NOVELS.heavenSword,
    area: "gate",
  },
  "dragon-saber": {
    zh: "屠龍刀",
    en: "Dragon Saber",
    what: "Its holder rules the martial world",
    novel: NOVELS.heavenSword,
    area: "gate",
  },
  "sun-moon": {
    zh: "日月",
    en: "Sun and Moon",
    what: "Sun 日 and moon 月 make 明, the Ming Sect's name",
    novel: null,
    area: "gate",
  },
  "jade-flute": {
    zh: "玉簫",
    en: "Jade Flute",
    what: "Huang Yaoshi's flute",
    novel: NOVELS.condorLegend,
    area: "mirror",
  },
  "five-wheels": {
    zh: "金銀銅鐵鉛五輪",
    en: "Five Wheels",
    what: "The Golden Wheel Lama's weapons",
    novel: NOVELS.condorReturn,
    area: "forge",
  },
  "sword-tomb": {
    zh: "劍冢",
    en: "Sword Tomb",
    what: "Where Dugu Qiubai buried his swords",
    novel: NOVELS.condorReturn,
    area: "forge",
  },
  "heavy-iron-sword": {
    zh: "玄鐵重劍",
    en: "Heavy Iron Sword",
    what: "Dugu Qiubai's edgeless sword",
    novel: NOVELS.condorReturn,
    area: "arena",
  },
  "holy-fire-altar": {
    zh: "聖火壇",
    en: "Holy Fire Altar",
    what: "The Ming Sect's sacred flame",
    novel: NOVELS.heavenSword,
    area: "mission",
  },
  "icefire-island": {
    zh: "冰火島",
    en: "Ice-Fire Island",
    what: "Where Zhang Wuji was born",
    novel: NOVELS.heavenSword,
    area: "library",
  },
  "holy-fire-tokens": {
    zh: "聖火令",
    en: "Holy Fire Tokens",
    what: "The Ming Sect's tokens of command",
    novel: NOVELS.heavenSword,
    area: "scroll",
  },
  "five-element-banners": {
    zh: "五行旗",
    en: "Five Element Banners",
    what: "The Ming Sect's five brigades",
    novel: NOVELS.heavenSword,
    area: "formation",
  },
  "big-dipper-array": {
    zh: "天罡北斗陣",
    en: "Big Dipper Array",
    what: "Quanzhen's seven-star formation",
    novel: NOVELS.condorLegend,
    area: "formation",
  },
  "wanderer-duet": {
    zh: "笑傲江湖",
    en: "The Wanderer's Duet",
    what: "Qu Yang and Liu Zhengfeng's duet",
    novel: NOVELS.wanderer,
    area: "abode",
  },
  "golden-bell-ribbon": {
    zh: "金鈴索",
    en: "Golden Bell Ribbon",
    what: "Xiaolongnü's silk ribbon",
    novel: NOVELS.condorReturn,
    area: "abode",
  },
  "divine-condor": {
    zh: "神鵰",
    en: "Divine Condor",
    what: "Yang Guo's companion and teacher",
    novel: NOVELS.condorReturn,
    area: "summit",
  },
} as const satisfies Record<string, LoreEntry>;

export type LoreId = keyof typeof LORE;

export const LORE_IDS = Object.keys(LORE) as LoreId[];

export function isLoreId(id: string): id is LoreId {
  return Object.prototype.hasOwnProperty.call(LORE, id);
}

/** The card's one line: what it is and the novel it comes from. */
export function loreLine(e: LoreEntry): string {
  return e.novel ? `${e.what}, from ${e.novel}` : e.what;
}

/** Content hotspots whose hover label always carries a quiet extra line (the jade scroll's verses). */
export const HOTSPOT_NOTES: Readonly<Record<string, string>> = {
  resume: "Verses from Jin Yong's novels",
};

/** The quiet extra line in a hotspot's hover label: a reference's name (and novel), or a fixed note. */
export interface HoverNote {
  zh?: string;
  text: string;
  /** The novel, set in italics after `text` (", from <novel>"). */
  novel?: string;
}

/** The line a reference adds to the label of the hotspot that holds it ("倚天劍 Heaven Sword, from ..."). */
export function loreNote(id: LoreId): HoverNote {
  const e: LoreEntry = LORE[id];
  return e.novel ? { zh: e.zh, text: e.en, novel: e.novel } : { zh: e.zh, text: e.what };
}

/**
 * The hover label's extra line for hotspot `hovered`: the reference under the pointer that the
 * hotspot holds (`hosted`, when its host is that hotspot), else the hotspot's fixed note (only with
 * `fixedNotes`: the page passes whether meta.json has references, so the verses note arrives with the
 * bake that has them), else null.
 */
export function hoverNote(
  hovered: string | null,
  hosted: { id: string; host: string | null } | null,
  fixedNotes = true,
): HoverNote | null {
  if (!hovered) return null;
  if (hosted && hosted.host === hovered && isLoreId(hosted.id)) return loreNote(hosted.id);
  const fixed = fixedNotes ? HOTSPOT_NOTES[hovered] : undefined;
  return fixed ? { text: fixed } : null;
}

/** The references meta.json has boxes for, by stop, in flight order (the panel's screen reader list). */
export function loreByArea(boxes: readonly LoreBox[] | undefined): Partial<Record<AreaId, LoreId[]>> {
  const present = new Set((boxes ?? []).map((b) => b.id));
  const out: Partial<Record<AreaId, LoreId[]>> = {};
  for (const id of LORE_IDS) {
    if (!present.has(id)) continue;
    (out[LORE[id].area] ??= []).push(id);
  }
  return out;
}

// ---- picking --------------------------------------------------------------------------------------

/** Farther than this (m, to where the ray enters the box) a reference is not named; as for hotspots. */
export const LORE_MAX_DISTANCE = 450;

/**
 * How far (m) behind the hovered hotspot's hit a box it holds may begin and still be the thing
 * under the pointer (its hit lies on that box's surface or inside it; box-only picks report where
 * the hotspot's own box begins).
 */
export const HOST_SLACK = 3;

/**
 * The reference box the ray (origin, unit dir) enters first: only known ids, only boxes whose host
 * is `host` (null: the references with no hotspot of their own), entered in front of the camera
 * (a box the camera is inside would cover the whole screen) and within `maxDistance`.
 */
export function loreHit(
  origin: Vec3,
  dir: Vec3,
  boxes: readonly LoreBox[],
  host: string | null,
  maxDistance = LORE_MAX_DISTANCE,
): BoxHit | null {
  let best: BoxHit | null = null;
  for (const b of boxes) {
    if (b.host !== host || !isLoreId(b.id)) continue;
    const t = rayBoxSpan(origin, dir, b.center, b.size);
    if (!t || t[0] <= 0 || t[0] > maxDistance) continue;
    if (!best || t[0] < best.distance) best = { id: b.id, distance: t[0], exit: t[1] };
  }
  return best;
}

/**
 * The reference under the pointer, given what the hotspot pick found on the same ray. A hotspot
 * (`hot`, with the distance of its hit) always keeps the pointer: only a reference it holds counts
 * (`host` set: its label names it), and only where the ray meets that reference's box by the hit.
 * With no hotspot, the nearest reference box in reach that `hidden` (scenery nearer on the ray)
 * does not cover, with `host` null: it gets a card of its own.
 */
export function loreUnderPointer(
  origin: Vec3,
  dir: Vec3,
  boxes: readonly LoreBox[],
  hot: { id: string; distance: number } | null,
  hidden: (distance: number) => boolean,
): { id: LoreId; host: string | null } | null {
  if (hot) {
    const h = loreHit(origin, dir, boxes, hot.id);
    return h && h.distance <= hot.distance + HOST_SLACK ? { id: h.id as LoreId, host: hot.id } : null;
  }
  const h = loreHit(origin, dir, boxes, null, LORE_MAX_DISTANCE);
  return h && !hidden(h.distance) ? { id: h.id as LoreId, host: null } : null;
}

/** A reference the pointer is on, as the scene reports it. */
export interface LoreHit {
  id: LoreId;
  /** The content hotspot that holds it (its label carries the name), or null (a card of its own). */
  host: string | null;
  /** The pointer, CSS px in the window. */
  at: readonly [number, number];
}

// ---- the card -------------------------------------------------------------------------------------

/** The pointer rests this long on a reference before its card fades in. */
export const LORE_HOVER_MS = 250;
/** A tapped card stays this long (a tap elsewhere hides it sooner). */
export const LORE_TAP_MS = 4000;

export interface LoreCardState {
  /** The reference whose card shows, or null. */
  shown: LoreId | null;
  /** Shown by a tap: it holds for LORE_TAP_MS whatever the pointer does. */
  tapped: boolean;
  /** The reference under the pointer, waiting out LORE_HOVER_MS since `since`. */
  candidate: LoreId | null;
  since: number;
  /** A tapped card hides at this time. */
  until: number;
}

export const LORE_CARD_IDLE: LoreCardState = { shown: null, tapped: false, candidate: null, since: 0, until: 0 };

export type LoreCardEvent =
  | { type: "hover"; id: LoreId | null }
  | { type: "tap"; id: LoreId | null }
  | { type: "tick" }
  | { type: "dismiss" };

/**
 * The card's timing (times in ms, any clock). Hover: the card fades in once the pointer has rested
 * on one reference for LORE_HOVER_MS, and goes the moment it leaves (or moves to another, which
 * then waits its own delay). Tap: shows at once and holds for LORE_TAP_MS; a tap on nothing (or
 * dismiss) hides it.
 */
export function loreCardStep(s: LoreCardState, e: LoreCardEvent, now: number): LoreCardState {
  switch (e.type) {
    case "tap":
      return e.id ? { shown: e.id, tapped: true, candidate: null, since: now, until: now + LORE_TAP_MS } : LORE_CARD_IDLE;
    case "dismiss":
      return LORE_CARD_IDLE;
    case "tick":
      if (s.tapped) return now >= s.until ? LORE_CARD_IDLE : s;
      if (s.candidate && s.shown !== s.candidate && now - s.since >= LORE_HOVER_MS) return { ...s, shown: s.candidate };
      return s;
    case "hover": {
      if (s.tapped && now < s.until) return s;
      const base = s.tapped ? LORE_CARD_IDLE : s;
      if (e.id !== base.candidate) return { ...base, shown: null, candidate: e.id, since: now };
      if (e.id && base.shown !== e.id && now - base.since >= LORE_HOVER_MS) return { ...base, shown: e.id };
      return base;
    }
  }
}

/** Milliseconds until the state needs a tick (the hover delay ends, a tapped card expires), or null. */
export function loreCardWake(s: LoreCardState, now: number): number | null {
  if (s.tapped) return Math.max(0, s.until - now);
  if (s.candidate && s.shown !== s.candidate) return Math.max(0, s.since + LORE_HOVER_MS - now);
  return null;
}

/**
 * Where the card goes (its top-left corner, CSS px): beside the pointer `at` for a hover (below and
 * to the right, flipped left or up near the window's edges), centred above the finger for a tap
 * (below it when there is no room above); always `margin` px inside the window.
 */
export function placeLoreCard(
  at: readonly [number, number],
  card: { w: number; h: number },
  view: { w: number; h: number },
  tapped: boolean,
  margin = 8,
): [number, number] {
  const [x, y] = at;
  const { w, h } = card;
  let left: number;
  let top: number;
  if (tapped) {
    left = x - w / 2;
    top = y - h - 28;
    if (top < margin) top = y + 28;
  } else {
    left = x + 14;
    top = y + 20;
    if (left + w > view.w - margin) left = x - 14 - w;
    if (top + h > view.h - margin) top = y - 12 - h;
  }
  left = Math.min(Math.max(left, margin), Math.max(view.w - w - margin, margin));
  top = Math.min(Math.max(top, margin), Math.max(view.h - h - margin, margin));
  return [Math.round(left), Math.round(top)];
}
