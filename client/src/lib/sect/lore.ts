/**
 * The Jin Yong references in the scene (the sect's owner is a big fan): what each one is, in a few
 * plain words, for the small card the page shows when the pointer rests on one (a tap on a touch
 * screen). Decorative only: never a hotspot, never in the rail, the Places list or the progress, and
 * never opens anything.
 *
 * Their hover boxes come from meta.json "lore" (blender/xianxia-sect/sect/export_web.py LORE, the
 * same ids). A meta.json without them shows no cards and the page works as before. A box the
 * exporter found inside a content hotspot (the gate's swords, the arena's sword, the gate's sun and
 * moon, the flute in the pond pavilion, the duet on the music fact, the summit's bamboo blinds, the
 * master stele) never gets a card of its own: the hotspot keeps the pointer and the click, and its
 * hover label carries the reference's name on one quiet extra line instead (loreNote).
 *
 * A card says what the thing is and which novel it comes from, nothing more: never why it stands at
 * its stop (the owner, round 34).
 *
 * Round 34 moved six references to the stop whose story they share and added four (思過崖, the
 * Mount Hua seats, 獨孤九劍, 綠竹巷): 15 became 19. Each meta.json box says where it stands, so the
 * stops' lists follow the installed file before and after that bake (loreByArea).
 *
 * Pure: no React, no three.js.
 */
import { isAreaId, type AreaId } from "./areas";
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
  /**
   * English name, faithful to every character (倚天劍 is the Heaven-Reliant Sword, not just the Heaven
   * Sword); where a literal name would be clumsy, the usual English name, and `what` says the rest.
   */
  en: string;
  /** The shorter name the novel's English title uses for it ("Heaven Sword"), when `en` is fuller. */
  short?: string;
  /** What it is, in a few plain words (the card's line adds the novel). */
  what: string;
  /** The novel it comes from, or null when the line says it all. */
  novel: string | null;
  /** The stop it belongs to (the screen reader list on that stop's panel). */
  area: AreaId;
}

/** Every reference, in flight order. Ids match export_web.py LORE. */
export const LORE = {
  // The blades quote their halves of the saber rhyme (武林至尊，寶刀屠龍 … 倚天不出，誰與爭鋒), which
  // the plinths carry but no one can read from the stop.
  "heaven-sword": {
    zh: "倚天劍",
    en: "Heaven-Reliant Sword",
    short: "Heaven Sword",
    what: "The Dragon-Slaying Saber's only rival: 倚天不出，誰與爭鋒",
    novel: NOVELS.heavenSword,
    area: "gate",
  },
  "dragon-saber": {
    zh: "屠龍刀",
    en: "Dragon-Slaying Saber",
    short: "Dragon Saber",
    what: "The blade whose holder rules the martial world: 武林至尊，寶刀屠龍",
    novel: NOVELS.heavenSword,
    area: "gate",
  },
  "sun-moon": {
    zh: "日月",
    en: "Sun and Moon",
    what: "This sect's name and emblem, 日月神教",
    novel: NOVELS.wanderer,
    area: "gate",
  },
  "jade-flute": {
    zh: "玉簫",
    en: "Jade Flute",
    what: "Huang Yaoshi's flute",
    novel: NOVELS.condorLegend,
    area: "mirror",
  },
  "cliff-of-reflection": {
    zh: "思過崖",
    en: "Cliff of Reflection",
    what: "Linghu Chong's year of reflection",
    novel: NOVELS.wanderer,
    area: "mirror",
  },
  "five-wheels": {
    zh: "金銀銅鐵鉛五輪",
    en: "Five Metal Wheels",
    what: "Gold, silver, copper, iron and lead",
    novel: NOVELS.condorReturn,
    area: "forge",
  },
  "heavy-iron-sword": {
    zh: "玄鐵重劍",
    en: "Black Iron Heavy Sword",
    what: "Dugu Qiubai's edgeless sword",
    novel: NOVELS.condorReturn,
    area: "arena",
  },
  // The first contest's titles (北丐 東邪 南帝 西毒) on four bronze plates; the taiji is the centre's seat.
  "mount-hua": {
    zh: "華山論劍",
    en: "Sword Contest of Mount Hua",
    what: "The seats of the Five Greats",
    novel: NOVELS.condorLegend,
    area: "arena",
  },
  "big-dipper-array": {
    zh: "天罡北斗陣",
    en: "Big Dipper Formation",
    what: "Seven Quanzhen masters, one per star",
    novel: NOVELS.condorLegend,
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
    en: "Holy Flame Tablets",
    what: "The Ming Sect's tokens of command",
    novel: NOVELS.heavenSword,
    area: "steles",
  },
  "dugu-nine-swords": {
    zh: "獨孤九劍",
    en: "Nine Swords of Dugu",
    what: "The art of finding every move's flaw",
    novel: NOVELS.wanderer,
    area: "steles",
  },
  "sword-tomb": {
    zh: "劍塚",
    en: "Sword Tomb",
    what: "Where Dugu Qiubai buried his swords",
    novel: NOVELS.condorReturn,
    area: "scroll",
  },
  "five-element-banners": {
    zh: "五行旗",
    en: "Five Element Banners",
    what: "The Ming Sect's five brigades",
    novel: NOVELS.heavenSword,
    area: "formation",
  },
  "holy-fire-altar": {
    zh: "聖火",
    en: "Holy Flame",
    what: "The fire the Ming Sect worships",
    novel: NOVELS.heavenSword,
    area: "formation",
  },
  "wanderer-duet": {
    zh: "笑傲江湖",
    en: "Laughing Proudly in the Jianghu",
    what: "Qu Yang and Liu Zhengfeng's duet",
    novel: NOVELS.wanderer,
    area: "abode",
  },
  "golden-bell-ribbon": {
    zh: "金鈴索",
    en: "Golden Bell Rope",
    what: "Xiaolongnü's white silk ribbon",
    novel: NOVELS.condorReturn,
    area: "summit",
  },
  "divine-condor": {
    zh: "神鵰",
    en: "Divine Condor",
    what: "Yang Guo's companion and teacher",
    novel: NOVELS.condorReturn,
    area: "summit",
  },
  // Bamboo blinds half down over pale gauze, and a qin and a lamp in the open middle bay: Green Bamboo
  // Lane, where Ren Yingying taught Linghu Chong the qin from behind a blind.
  "green-bamboo": {
    zh: "綠竹巷",
    en: "Green Bamboo Lane",
    what: "Qin lessons through a bamboo blind",
    novel: NOVELS.wanderer,
    area: "summit",
  },
} as const satisfies Record<string, LoreEntry>;

export type LoreId = keyof typeof LORE;

export const LORE_IDS = Object.keys(LORE) as LoreId[];

export function isLoreId(id: string): id is LoreId {
  return Object.prototype.hasOwnProperty.call(LORE, id);
}

/**
 * True when the novel's title already says the reference's name (the Heaven Sword and the Dragon
 * Saber are the title of Heaven Sword and Dragon Saber), so naming the novel would repeat it. The
 * title uses the short names, so they are the ones looked for.
 */
function titled(e: LoreEntry): boolean {
  return e.novel !== null && e.novel.toLowerCase().includes((e.short ?? e.en).toLowerCase());
}

/** The novel the card names after its line: none when the line says it all or the title names it. */
export function loreNovel(e: LoreEntry): string | null {
  return titled(e) ? null : e.novel;
}

/** The card's one line: what it is and the novel it comes from (unless the title already names it). */
export function loreLine(e: LoreEntry): string {
  const novel = loreNovel(e);
  return novel ? `${e.what}, from ${novel}` : e.what;
}

/** The quiet extra line in a hotspot's hover label: a reference's name (and novel), or a fixed note. */
export interface HoverNote {
  zh?: string;
  text: string;
  /** The novel, set in italics after `text` (", from <novel>"). */
  novel?: string;
}

/** A hotspot's fixed quiet line (HOTSPOT_NOTES). */
export interface FixedNote extends HoverNote {
  /**
   * Shown only once the installed meta.json has this reference (standing at `area`, when given): a
   * line about something a later bake brings, which the scene before it does not have.
   */
  needs?: { id: LoreId; area?: AreaId };
}

/**
 * The Big Dipper's seven stars in the array's order, bowl (斗魁) then handle (斗柄), each with the
 * Quanzhen master who holds it (Legend of the Condor Heroes). The Mission Hall's star drums carry
 * the names; its seven role tablets take the stars in their order (role:0 to role:6), the bowl's
 * four under the top row of tablets and the handle's three under the bottom row.
 */
export const DIPPER_STARS = [
  { zh: "天樞", en: "Tianshu", master: "Ma Yu" },
  { zh: "天璇", en: "Tianxuan", master: "Tan Chuduan" },
  { zh: "天璣", en: "Tianji", master: "Liu Chuxuan" },
  { zh: "天權", en: "Tianquan", master: "Qiu Chuji" },
  { zh: "玉衡", en: "Yuheng", master: "Wang Chuyi" },
  { zh: "開陽", en: "Kaiyang", master: "Hao Datong" },
  { zh: "搖光", en: "Yaoguang", master: "Sun Bu'er" },
] as const;

/** A martial-arts manual carved on a stele. */
export interface SteleManual {
  zh: string;
  en: string;
  novel: string;
}

/**
 * The manual each stele row's front steles carry (round 34): one that fits the row's skill phrase
 * (content.ts skillGroups, front row first). The row's hover label names it.
 */
export const STELE_ROW_MANUALS: readonly (readonly SteleManual[])[] = [
  // voice-first
  [
    { zh: "獅子吼", en: "Lion's Roar", novel: NOVELS.heavenSword },
    { zh: "清心普善咒", en: "Pure Heart Chant", novel: NOVELS.wanderer },
  ],
  // agents (the Holy Flame Tablets stand in front of it: a reference of their own)
  [{ zh: "吸星大法", en: "Star-Absorbing Great Method", novel: NOVELS.wanderer }],
  // latency
  [{ zh: "天羅地網勢", en: "Heaven-and-Earth Net", novel: NOVELS.condorReturn }],
  // keeping a human in the loop
  [{ zh: "玉女心經", en: "Jade Maiden Heart Sutra", novel: NOVELS.condorReturn }],
  // when the model is wrong
  [{ zh: "乾坤大挪移", en: "Great Shift of Heaven and Earth", novel: NOVELS.heavenSword }],
];

/** A row's manuals as one hover line: their names, and the novel when they share one. */
function manualsNote(ms: readonly SteleManual[]): HoverNote {
  const novel = ms.every((m) => m.novel === ms[0].novel) ? ms[0].novel : undefined;
  const zh = ms.map((m) => m.zh).join(" · ");
  const text = ms.map((m) => m.en).join(" and the ");
  return novel ? { zh, text, novel } : { zh, text };
}

/**
 * The Ming Sect's five banner brigades (五行旗), one for each part of the site: the formation
 * reader's four Stack groups (content-copy.ts ARCH_STACK) and the core.
 */
export const STACK_BRIGADES = [
  { part: "Voice", zh: "洪水", en: "Flood Water" },
  { part: "Brain", zh: "烈火", en: "Raging Fire" },
  { part: "Frame", zh: "巨木", en: "Giant Wood" },
  { part: "State", zh: "銳金", en: "Sharp Metal" },
  { part: "core", zh: "厚土", en: "Thick Earth" },
] as const;

/** The brigade of a part of the site ("Voice", ..., "core"), or null. */
export function stackBrigade(part: string): (typeof STACK_BRIGADES)[number] | null {
  return STACK_BRIGADES.find((b) => b.part === part) ?? null;
}

/** The scene the round-34 bake brings: what the notes about it wait for. */
const DIPPER_AT_MISSION = { id: "big-dipper-array", area: "mission" } as const;
const STELES_RECARVED = { id: "dugu-nine-swords" } as const;

/**
 * Content hotspots whose hover label carries a quiet extra line: the jade scroll's verses, the
 * Stack pillar's brigades, each role tablet's star (once the Dipper stands at the Mission Hall) and
 * each stele row's manual (once the steles are re-carved).
 */
export const HOTSPOT_NOTES: Readonly<Record<string, FixedNote>> = {
  resume: { text: "Verses from Jin Yong's novels" },
  "arch:6": { zh: "五行旗", text: STACK_BRIGADES.map((b) => `${b.zh} ${b.part === "core" ? "the core" : b.part}`).join(" · ") },
  ...Object.fromEntries(
    DIPPER_STARS.map((s, i) => [`role:${i}`, { zh: s.zh, text: `${s.en}, ${s.master}'s star`, needs: DIPPER_AT_MISSION }]),
  ),
  ...Object.fromEntries(STELE_ROW_MANUALS.map((ms, i) => [`skills:${i}`, { ...manualsNote(ms), needs: STELES_RECARVED }])),
};

/**
 * The line a reference adds to the label of the hotspot that holds it: its name and novel ("玄鐵重劍
 * Black Iron Heavy Sword, from ..."), or its name and line when the title names it ("倚天劍
 * Heaven-Reliant Sword, the Dragon-Slaying Saber's only rival"), or the line alone with no novel.
 */
export function loreNote(id: LoreId): HoverNote {
  const e: LoreEntry = LORE[id];
  if (titled(e)) return { zh: e.zh, text: `${e.en}, ${e.what.charAt(0).toLowerCase()}${e.what.slice(1)}` };
  return e.novel ? { zh: e.zh, text: e.en, novel: e.novel } : { zh: e.zh, text: e.what };
}

/** True when `boxes` has a box of reference `needs.id` (at stop `needs.area`, when given). */
function hasReference(boxes: readonly LoreBox[], needs: { id: LoreId; area?: AreaId }): boolean {
  return boxes.some((b) => b.id === needs.id && (needs.area === undefined || b.area === needs.area));
}

/**
 * The hover label's extra line for hotspot `hovered`: the reference under the pointer that the
 * hotspot holds (`hosted`, when its host is that hotspot), else the hotspot's fixed note, else null.
 *
 * `fixedNotes` says which fixed notes may show: meta.json's reference boxes (the page's
 * `meta.lore`), or just whether it has any. None while it has none, so the notes arrive with the
 * bake that has the references. A note that `needs` a reference shows only when the boxes are
 * given and hold it: with `true` alone it stays hidden, since the scene may not have it yet.
 */
export function hoverNote(
  hovered: string | null,
  hosted: { id: string; host: string | null } | null,
  fixedNotes: boolean | readonly LoreBox[] = true,
): HoverNote | null {
  if (!hovered) return null;
  if (hosted && hosted.host === hovered && isLoreId(hosted.id)) return loreNote(hosted.id);
  const note = Object.prototype.hasOwnProperty.call(HOTSPOT_NOTES, hovered) ? HOTSPOT_NOTES[hovered] : undefined;
  if (!note) return null;
  const boxes = typeof fixedNotes === "boolean" ? null : fixedNotes;
  if (boxes ? boxes.length === 0 : !fixedNotes) return null;
  if (note.needs && !(boxes && hasReference(boxes, note.needs))) return null;
  const line: HoverNote = { text: note.text };
  if (note.zh) line.zh = note.zh;
  if (note.novel) line.novel = note.novel;
  return line;
}

/**
 * The references meta.json has boxes for, by stop, in flight order (the panel's screen reader
 * list). Each goes to the stop its box names (where the installed bake put it: before round 34 the
 * altars stood at the Mission Hall, for one), else the one LORE gives.
 */
export function loreByArea(boxes: readonly LoreBox[] | undefined): Partial<Record<AreaId, LoreId[]>> {
  const at = new Map<LoreId, AreaId>();
  for (const b of boxes ?? []) {
    if (!isLoreId(b.id) || at.has(b.id)) continue;
    at.set(b.id, b.area !== null && isAreaId(b.area) ? b.area : LORE[b.id].area);
  }
  const out: Partial<Record<AreaId, LoreId[]>> = {};
  for (const id of LORE_IDS) {
    const area = at.get(id);
    if (area) (out[area] ??= []).push(id);
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
