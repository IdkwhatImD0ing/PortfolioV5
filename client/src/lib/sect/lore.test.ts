/**
 * The Jin Yong references (lore.ts): the words on the cards, the ids the exporter writes, how a
 * reference is found under the pointer without ever beating a hotspot, the card's timing and place,
 * and meta.json's "lore" list (absent from today's files, which must keep working as before).
 */
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { AREA_IDS } from "./areas";
import {
  HOST_SLACK,
  HOTSPOT_NOTES,
  hoverNote,
  isLoreId,
  LORE,
  LORE_CARD_IDLE,
  LORE_HOVER_MS,
  LORE_IDS,
  LORE_MAX_DISTANCE,
  LORE_TAP_MS,
  loreByArea,
  loreCardStep,
  loreCardWake,
  loreHit,
  loreLine,
  loreNote,
  loreNovel,
  loreUnderPointer,
  NOVELS,
  placeLoreCard,
  type LoreCardEvent,
  type LoreCardState,
  type LoreEntry,
} from "./lore";
import { parseMeta } from "./parse";
import type { LoreBox, Vec3 } from "./types";

const entries = Object.entries(LORE) as [string, LoreEntry][];
const words = (e: LoreEntry) => [e.zh, e.en, e.what, e.novel ?? "", loreLine(e)];

describe("the cards' words", () => {
  it("has the fifteen references the scene holds", () => {
    expect(LORE_IDS).toHaveLength(15);
  });

  it("keeps every card line short: one line, at most 70 characters", () => {
    for (const [id, e] of entries) {
      expect(loreLine(e).length, id).toBeLessThanOrEqual(70);
      expect(loreLine(e), id).not.toMatch(/\n/);
    }
  });

  it("uses no dashes for drama and never calls the sect a cult", () => {
    for (const [id, e] of entries) {
      for (const w of words(e)) {
        expect(w, id).not.toMatch(/[—–]/);
        expect(w.toLowerCase(), id).not.toContain("cult");
      }
    }
    for (const note of Object.values(HOTSPOT_NOTES)) {
      expect(note).not.toMatch(/[—–]/);
      expect(note.toLowerCase()).not.toContain("cult");
    }
  });

  it("gives every reference a Chinese name in Chinese characters, an English name, a stop and a known novel", () => {
    const novels = new Set<string>(Object.values(NOVELS));
    for (const [id, e] of entries) {
      expect(e.zh, id).toMatch(/^[㐀-鿿]+$/u);
      expect(e.en.length, id).toBeGreaterThan(0);
      expect(AREA_IDS, id).toContain(e.area);
      if (e.novel !== null) expect(novels.has(e.novel), id).toBe(true);
    }
  });

  it("names the novels right", () => {
    expect(loreLine(LORE["heavy-iron-sword"])).toBe(`${LORE["heavy-iron-sword"].what}, from Return of the Condor Heroes`);
    // The novel's title already names the two blades (by their short names), so their lines don't repeat it.
    expect(loreLine(LORE["heaven-sword"])).toBe("The Dragon-Slaying Saber's only rival");
    expect(loreLine(LORE["dragon-saber"])).toBe("The blade whose holder rules the martial world");
    // A Chinese title that holds the name is not enough: the English title must say it.
    expect(loreLine(LORE["wanderer-duet"])).toBe("Qu Yang and Liu Zhengfeng's duet, from The Smiling, Proud Wanderer");
    expect(loreLine(LORE["divine-condor"])).toBe("Yang Guo's companion and teacher, from Return of the Condor Heroes");
    expect(LORE["heavy-iron-sword"].novel).toBe("Return of the Condor Heroes");
    expect(LORE["jade-flute"].novel).toBe("Legend of the Condor Heroes");
    expect(LORE["big-dipper-array"].novel).toBe("Legend of the Condor Heroes");
    expect(LORE["wanderer-duet"].novel).toBe("The Smiling, Proud Wanderer");
    expect(LORE["icefire-island"].what).toContain("Zhang Wuji");
  });

  it("translates every character of the name, as the usual English sources do", () => {
    expect(LORE["heaven-sword"].en).toBe("Heaven-Reliant Sword"); // 倚 relying on, 天 heaven, 劍 sword
    expect(LORE["dragon-saber"].en).toBe("Dragon-Slaying Saber"); // 屠 slaying, 龍 dragon, 刀 saber
    expect(LORE["heavy-iron-sword"].en).toBe("Black Iron Heavy Sword"); // 玄 black, 鐵 iron, 重 heavy, 劍 sword
    expect(LORE["wanderer-duet"].en).toBe("Laughing Proudly in the Jianghu"); // 笑傲江湖
    // The five metals of 金銀銅鐵鉛五輪 are in the line, not crammed into the name.
    expect(LORE["five-wheels"].what).toBe("Gold, silver, copper, iron and lead");
    // As the traditional editions print them.
    expect(LORE["sword-tomb"].zh).toBe("劍塚");
    expect(LORE["holy-fire-altar"].zh).toBe("聖火");
  });

  it("keeps a short name only where the novel's title uses it", () => {
    for (const [id, e] of entries) {
      if (e.short === undefined) continue;
      expect(e.novel?.toLowerCase(), id).toContain(e.short.toLowerCase());
      expect(loreNovel(e), id).toBeNull();
    }
    expect(loreNovel(LORE["heavy-iron-sword"])).toBe("Return of the Condor Heroes");
    expect(loreNovel(LORE["sun-moon"])).toBeNull();
  });

  it("matches the exporter's ids and stops (blender/xianxia-sect/sect/export_web.py LORE)", () => {
    const file = path.resolve(__dirname, "../../../../blender/xianxia-sect/sect/export_web.py");
    if (!existsSync(file)) return; // the client checked out alone
    const src = readFileSync(file, "utf8");
    const block = src.slice(src.indexOf("\nLORE = ("), src.indexOf("\nLORE_SKIP"));
    const pairs = [...block.matchAll(/^\s+\("([a-z-]+)", "([a-z]+)",/gm)].map((m) => [m[1], m[2]]);
    expect(pairs).toEqual(entries.map(([id, e]) => [id, e.area]));
  });
});

describe("hover notes (a reference a hotspot holds)", () => {
  it("names the reference on the hotspot that holds it, with its novel unless the title already names it", () => {
    expect(loreNote("heavy-iron-sword")).toEqual({ zh: "玄鐵重劍", text: "Black Iron Heavy Sword", novel: "Return of the Condor Heroes" });
    expect(loreNote("heaven-sword")).toEqual({ zh: "倚天劍", text: "Heaven-Reliant Sword, the Dragon-Slaying Saber's only rival" });
    expect(hoverNote("gate-swords", { id: "dragon-saber", host: "gate-swords" })).toEqual({
      zh: "屠龍刀",
      text: "Dragon-Slaying Saber, the blade whose holder rules the martial world",
    });
    // No novel: the line itself.
    expect(hoverNote("gate", { id: "sun-moon", host: "gate" })).toEqual({ zh: "日月", text: LORE["sun-moon"].what });
  });

  it("says nothing when the hovered hotspot is not the reference's host", () => {
    expect(hoverNote("gate-lions", { id: "heaven-sword", host: "gate-swords" })).toBeNull();
    expect(hoverNote(null, { id: "heaven-sword", host: "gate-swords" })).toBeNull();
    expect(hoverNote("gate", null)).toBeNull();
  });

  it("adds the one quiet line to the jade scroll (the resume), once meta.json has the references", () => {
    expect(hoverNote("resume", null)).toEqual({ text: "Verses from Jin Yong's novels" });
    expect(hoverNote("resume", null, false)).toBeNull();
  });
});

// A camera at the origin looking down -Z; boxes 100 m ahead.
const O: Vec3 = [0, 0, 0];
const AHEAD: Vec3 = [0, 0, -1];
const box = (id: string, z: number, host: string | null = null, size: Vec3 = [4, 4, 4]): LoreBox => ({
  id,
  center: [0, 0, z],
  size,
  host,
  area: null,
});

describe("loreHit", () => {
  it("takes the nearest box the ray enters", () => {
    const h = loreHit(O, AHEAD, [box("sword-tomb", -150), box("five-wheels", -100)], null);
    expect(h?.id).toBe("five-wheels");
    expect(h?.distance).toBeCloseTo(98);
    expect(h?.exit).toBeCloseTo(102);
  });

  it("only takes boxes of the asked host", () => {
    const boxes = [box("heaven-sword", -50, "gate-swords"), box("five-wheels", -100)];
    expect(loreHit(O, AHEAD, boxes, null)?.id).toBe("five-wheels");
    expect(loreHit(O, AHEAD, boxes, "gate-swords")?.id).toBe("heaven-sword");
    expect(loreHit(O, AHEAD, boxes, "gate")).toBeNull();
  });

  it("ignores a box the camera is inside, one out of reach, one to the side and unknown ids", () => {
    expect(loreHit(O, AHEAD, [box("icefire-island", 0, null, [100, 100, 100])], null)).toBeNull();
    expect(loreHit(O, AHEAD, [box("icefire-island", -(LORE_MAX_DISTANCE + 50))], null)).toBeNull();
    expect(loreHit(O, AHEAD, [{ ...box("five-wheels", -100), center: [30, 0, -100] }], null)).toBeNull();
    expect(loreHit(O, AHEAD, [box("not-a-reference", -100)], null)).toBeNull();
    expect(loreHit(O, AHEAD, [box("five-wheels", 100)], null)).toBeNull(); // behind
  });
});

describe("loreUnderPointer: a hotspot always wins", () => {
  const visible = () => false;

  it("gives a reference its own card only when no hotspot is under the pointer", () => {
    const boxes = [box("five-wheels", -100)];
    expect(loreUnderPointer(O, AHEAD, boxes, null, visible)).toEqual({ id: "five-wheels", host: null });
    // A hotspot in front of it (or anywhere on the ray) keeps the pointer: no card.
    expect(loreUnderPointer(O, AHEAD, boxes, { id: "forge-hall", distance: 60 }, visible)).toBeNull();
    expect(loreUnderPointer(O, AHEAD, boxes, { id: "forge-hall", distance: 120 }, visible)).toBeNull();
  });

  it("drops a reference that scenery hides", () => {
    const seen: number[] = [];
    const hidden = (d: number) => {
      seen.push(d);
      return true;
    };
    expect(loreUnderPointer(O, AHEAD, [box("five-wheels", -100)], null, hidden)).toBeNull();
    expect(seen[0]).toBeCloseTo(98); // tested up to where the box begins
  });

  it("names a reference the hovered hotspot holds where the ray meets it by the hit", () => {
    const boxes = [box("heaven-sword", -100, "gate-swords"), box("five-wheels", -40)];
    // The hit lies on the sword's box: named (the free reference nearer on the ray is not).
    expect(loreUnderPointer(O, AHEAD, boxes, { id: "gate-swords", distance: 99 }, visible)).toEqual({
      id: "heaven-sword",
      host: "gate-swords",
    });
    // The hotspot was hit well before the sword's box (another part of it): no name.
    expect(loreUnderPointer(O, AHEAD, boxes, { id: "gate-swords", distance: 98 - HOST_SLACK - 1 }, visible)).toBeNull();
  });

  it("never names a reference on the moon", () => {
    expect(loreUnderPointer(O, AHEAD, [box("divine-condor", -100)], { id: "moon", distance: Infinity }, visible)).toBeNull();
  });
});

describe("the card's timing", () => {
  const run = (events: [number, LoreCardEvent][]): LoreCardState =>
    events.reduce((s, [t, e]) => loreCardStep(s, e, t), LORE_CARD_IDLE);
  const hover = (id: (typeof LORE_IDS)[number] | null): LoreCardEvent => ({ type: "hover", id });

  it("fades in after the pointer rests 250 ms on a reference, not before", () => {
    expect(LORE_HOVER_MS).toBe(250);
    let s = run([[0, hover("five-wheels")]]);
    expect(s.shown).toBeNull();
    expect(loreCardWake(s, 100)).toBe(150);
    s = loreCardStep(s, hover("five-wheels"), 200);
    expect(s.shown).toBeNull();
    s = loreCardStep(s, { type: "tick" }, 250);
    expect(s.shown).toBe("five-wheels");
    expect(loreCardWake(s, 300)).toBeNull();
  });

  it("goes the moment the pointer leaves, and a new reference waits its own delay", () => {
    let s = run([
      [0, hover("five-wheels")],
      [300, { type: "tick" }],
    ]);
    expect(s.shown).toBe("five-wheels");
    s = loreCardStep(s, hover("sword-tomb"), 400);
    expect(s.shown).toBeNull();
    s = loreCardStep(s, { type: "tick" }, 600);
    expect(s.shown).toBeNull();
    s = loreCardStep(s, { type: "tick" }, 650);
    expect(s.shown).toBe("sword-tomb");
    expect(loreCardStep(s, hover(null), 700).shown).toBeNull();
  });

  it("a passing sweep never shows a card", () => {
    const s = run([
      [0, hover("five-wheels")],
      [100, hover(null)],
      [150, hover("sword-tomb")],
      [300, hover(null)],
      [1000, { type: "tick" }],
    ]);
    expect(s.shown).toBeNull();
  });

  it("a tap shows the card at once for 4 s, whatever the pointer does, then it goes", () => {
    expect(LORE_TAP_MS).toBe(4000);
    let s = run([[0, { type: "tap", id: "divine-condor" }]]);
    expect(s).toMatchObject({ shown: "divine-condor", tapped: true });
    s = loreCardStep(s, hover(null), 50); // the finger lifts: the pointer leaves the canvas
    expect(s.shown).toBe("divine-condor");
    expect(loreCardWake(s, 1000)).toBe(3000);
    expect(loreCardStep(s, { type: "tick" }, 3999).shown).toBe("divine-condor");
    expect(loreCardStep(s, { type: "tick" }, 4000).shown).toBeNull();
  });

  it("a tap on nothing, or a press anywhere, hides a tapped card", () => {
    const s = run([[0, { type: "tap", id: "divine-condor" }]]);
    expect(loreCardStep(s, { type: "tap", id: null }, 500)).toEqual(LORE_CARD_IDLE);
    expect(loreCardStep(s, { type: "dismiss" }, 500)).toEqual(LORE_CARD_IDLE);
  });
});

describe("placeLoreCard", () => {
  const card = { w: 240, h: 56 };
  const view = { w: 1600, h: 900 };

  it("sits below and to the right of the pointer", () => {
    expect(placeLoreCard([400, 300], card, view, false)).toEqual([414, 320]);
  });

  it("flips left and up near the right and bottom edges", () => {
    expect(placeLoreCard([1500, 880], card, view, false)).toEqual([1500 - 14 - 240, 880 - 12 - 56]);
  });

  it("goes above the finger for a tap, below it at the top of the screen", () => {
    expect(placeLoreCard([400, 300], card, view, true)).toEqual([280, 300 - 56 - 28]);
    expect(placeLoreCard([400, 40], card, view, true)).toEqual([280, 68]);
  });

  it("stays inside a phone's screen", () => {
    const [x, y] = placeLoreCard([5, 5], card, { w: 320, h: 568 }, true);
    expect(x).toBe(8);
    expect(y).toBeGreaterThanOrEqual(8);
    const [x2] = placeLoreCard([318, 300], card, { w: 320, h: 568 }, true);
    expect(x2 + card.w).toBeLessThanOrEqual(320 - 8);
  });
});

// Two entries as export_web.py writes them (from a dry run of `meta` on the scene file).
const EXPORTED = [
  {
    id: "heaven-sword",
    kind: "lore",
    area: "gate",
    node: null,
    objects: ["gate.sword_monolith"],
    boxes: [{ center: [-16.0, 47.8, 25.0], size: [6.40472, 15.6, 6.40472], hotspot: "gate-swords", objects: ["gate.sword_monolith"] }],
  },
  {
    id: "holy-fire-altar",
    kind: "lore",
    area: "mission",
    node: null,
    objects: ["mission.holy_fire", "mission.holy_fire.001"],
    boxes: [
      { center: [-113.54, 142.45, -620.0], size: [8.44479, 5.00999, 8.44482], hotspot: null, objects: ["mission.holy_fire"] },
      { center: [-152.18, 142.45, -588.27], size: [8.44479, 5.00999, 8.44482], hotspot: null, objects: ["mission.holy_fire.001"] },
    ],
  },
];

describe("meta.json lore", () => {
  it("reads the exporter's entries as one box each, never as hotspots", () => {
    const meta = parseMeta({ hotspots: [], lore: EXPORTED });
    expect(meta.hotspots).toEqual([]);
    expect(meta.lore).toEqual([
      { id: "heaven-sword", center: [-16, 47.8, 25], size: [6.40472, 15.6, 6.40472], host: "gate-swords", area: "gate" },
      { id: "holy-fire-altar", center: [-113.54, 142.45, -620], size: [8.44479, 5.00999, 8.44482], host: null, area: "mission" },
      { id: "holy-fire-altar", center: [-152.18, 142.45, -588.27], size: [8.44479, 5.00999, 8.44482], host: null, area: "mission" },
    ]);
    expect(loreByArea(meta.lore)).toEqual({ gate: ["heaven-sword"], mission: ["holy-fire-altar"] });
  });

  it("drops entries without an id and boxes without a usable size", () => {
    const meta = parseMeta({
      lore: [
        { boxes: [{ center: [0, 0, 0], size: [1, 1, 1] }] },
        { id: "five-wheels", boxes: [{ center: [0, 0, 0] }, { center: [0, 0, 0], size: [1, -1, 1] }, { center: [1, 2, 3], size: [1, 1, 1] }] },
        { id: "sword-tomb", center: [4, 5, 6], size: [2, 2, 2] },
        "nonsense",
      ],
    });
    expect(meta.lore?.map((b) => [b.id, b.center])).toEqual([
      ["five-wheels", [1, 2, 3]],
      ["sword-tomb", [4, 5, 6]],
    ]);
  });

  it("is empty for a meta.json without it, and the installed file's (if any) are references, never hotspots", () => {
    expect(parseMeta({}).lore).toEqual([]);
    expect(loreByArea(parseMeta({}).lore)).toEqual({});
    // The installed file has no "lore" before the bake that adds it and has it after the pack:
    // this holds either way, so the pack does not break the suite.
    const live = path.resolve(__dirname, "../../../public/sect/full/meta.json");
    if (!existsSync(live)) return;
    const meta = parseMeta(JSON.parse(readFileSync(live, "utf8")));
    expect(meta.hotspots.length).toBeGreaterThan(0);
    const hot = new Set(meta.hotspots.map((h) => h.id));
    for (const b of meta.lore ?? []) {
      expect(isLoreId(b.id)).toBe(true);
      expect(hot.has(b.id)).toBe(false);
    }
  });

  it("keeps references out of the hotspot ids", () => {
    for (const id of LORE_IDS) {
      expect(isLoreId(id)).toBe(true);
      expect(id).not.toContain(":");
    }
    expect(isLoreId("gate-swords")).toBe(false);
    expect(isLoreId("toString")).toBe(false);
  });
});
