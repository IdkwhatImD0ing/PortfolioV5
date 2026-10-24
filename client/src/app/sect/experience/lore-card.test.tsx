/**
 * The Jin Yong reference card and its quiet relatives: the card's words and manners (aria-hidden,
 * no fade with reduced motion), its timer (lore-card.tsx LoreCardController), the extra line a
 * hotspot's hover label gains, and the screen reader list on a stop's panel.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { hotspotLabel } from "@/lib/sect/content";
import { hoverNote, LORE_HOVER_MS, LORE_TAP_MS, type LoreCardState } from "@/lib/sect/lore";
import { AreaPanel } from "../content";
import { LoreCard, LoreCardController } from "./lore-card";
import { HoverLabel } from "./overlay";

const ENTITIES: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', "#x27": "'", "#39": "'", nbsp: " " };
const textOf = (html: string) =>
  html
    .replace(/<[^>]+>/g, " ")
    .replace(/&(amp|lt|gt|quot|#x27|#39|nbsp);/g, (_, e: string) => ENTITIES[e])
    .replace(/\s+/g, " ")
    .replace(/ ([,.:)])/g, "$1")
    .replace(/\( /g, "(")
    .trim();

describe("LoreCard", () => {
  it("names the reference: Chinese name in gold, English name, one line with the novel", () => {
    const html = renderToStaticMarkup(<LoreCard id="heavy-iron-sword" visible />);
    expect(textOf(html)).toBe("玄鐵重劍 Black Iron Heavy Sword Dugu Qiubai's edgeless sword, from Return of the Condor Heroes");
    expect(html).toContain('lang="zh-Hant"');
    expect(html).toMatch(/text-\[var\(--sect-gold\)\][^>]*>玄鐵重劍/);
    expect(html).toContain("<cite");
    expect(html).toContain('data-sect-lore="heavy-iron-sword"');
  });

  it("is decorative: hidden from screen readers, never takes the pointer, no glow", () => {
    const html = renderToStaticMarkup(<LoreCard id="divine-condor" visible />);
    expect(html).toContain('aria-hidden="true"');
    expect(html).toContain("pointer-events-none");
    expect(html).not.toMatch(/tabindex|<button|<a /i);
    expect(html).not.toMatch(/shadow|glow/i);
  });

  it("fades, except with reduced motion; empty and invisible with nothing to say", () => {
    expect(renderToStaticMarkup(<LoreCard id="sword-tomb" visible />)).toContain("transition:opacity 180ms ease-out");
    expect(renderToStaticMarkup(<LoreCard id="sword-tomb" visible reducedMotion />)).toContain("transition:none");
    expect(renderToStaticMarkup(<LoreCard id="sword-tomb" visible={false} />)).toContain("opacity:0");
    const none = renderToStaticMarkup(<LoreCard id={null} visible />);
    expect(none).toContain("visibility:hidden");
    expect(textOf(none)).toBe("");
  });

  it("says the line alone when the novel's title is the name, and names the novel otherwise", () => {
    expect(textOf(renderToStaticMarkup(<LoreCard id="sun-moon" visible />))).toBe(
      "日月 Sun and Moon This sect's name and emblem, 日月神教, from The Smiling, Proud Wanderer",
    );
    const sword = renderToStaticMarkup(<LoreCard id="heaven-sword" visible />);
    expect(textOf(sword)).toBe("倚天劍 Heaven-Reliant Sword The Dragon-Slaying Saber's only rival: 倚天不出，誰與爭鋒");
    expect(sword).not.toContain("<cite");
  });

  it("names round 34's new references", () => {
    expect(textOf(renderToStaticMarkup(<LoreCard id="cliff-of-reflection" visible />))).toBe(
      "思過崖 Cliff of Reflection Linghu Chong's year of reflection, from The Smiling, Proud Wanderer",
    );
    expect(textOf(renderToStaticMarkup(<LoreCard id="mount-hua" visible />))).toBe(
      "華山論劍 Sword Contest of Mount Hua The seats of the Five Greats, from Legend of the Condor Heroes",
    );
  });
});

describe("LoreCardController", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  const setup = () => {
    vi.useFakeTimers({ now: 0 });
    const seen: (string | null)[] = [];
    // The fake clock moves with the fake timers, as performance.now() does with real ones.
    const ctl = new LoreCardController(
      (s: LoreCardState) => seen.push(s.shown),
      () => Date.now(),
    );
    const at = (t: number) => vi.advanceTimersByTime(t - Date.now());
    return { ctl, seen, at };
  };

  it("re-arms when its timer fires a hair early", () => {
    vi.useFakeTimers({ now: 0 });
    let clock = 0;
    const seen: (string | null)[] = [];
    const ctl = new LoreCardController((s) => seen.push(s.shown), () => clock);
    ctl.dispatch({ type: "hover", id: "jade-flute" });
    clock = LORE_HOVER_MS - 3; // the timer fires, but the page's clock says the delay is not over
    vi.advanceTimersByTime(LORE_HOVER_MS + 1);
    expect(seen).toEqual([]);
    clock = LORE_HOVER_MS + 10;
    vi.advanceTimersByTime(10);
    expect(seen).toEqual(["jade-flute"]);
    ctl.dispose();
  });

  it("shows a rested-on reference after the delay with no further events (the scene stops picking at rest)", () => {
    const { ctl, seen, at } = setup();
    ctl.dispatch({ type: "hover", id: "five-wheels" });
    at(LORE_HOVER_MS - 10);
    expect(seen).toEqual([]);
    at(LORE_HOVER_MS + 5);
    expect(seen).toEqual(["five-wheels"]);
    ctl.dispatch({ type: "hover", id: null });
    expect(seen).toEqual(["five-wheels", null]);
    ctl.dispose();
  });

  it("holds a tapped card for its time, then lets it go", () => {
    const { ctl, seen, at } = setup();
    ctl.dispatch({ type: "tap", id: "divine-condor" });
    ctl.dispatch({ type: "hover", id: null });
    at(LORE_TAP_MS - 100);
    expect(seen).toEqual(["divine-condor"]);
    at(LORE_TAP_MS + 10);
    expect(seen).toEqual(["divine-condor", null]);
    ctl.dispose();
  });

  it("tells the page only when the card changes, not on every pick", () => {
    const { ctl, seen, at } = setup();
    for (let t = 0; t <= 1000; t += 50) {
      at(t);
      ctl.dispatch({ type: "hover", id: "sword-tomb" });
    }
    expect(seen).toEqual(["sword-tomb"]);
    ctl.dispose();
  });
});

describe("the hover label's quiet line", () => {
  const label = (id: string, hosted: { id: string; host: string | null } | null) =>
    renderToStaticMarkup(<HoverLabel label={hotspotLabel(id)} note={hoverNote(id, hosted)} />);

  it("names the sword under the pointer on the gate's swords", () => {
    const html = label("gate-swords", { id: "heaven-sword", host: "gate-swords" });
    expect(textOf(html)).toContain("倚天劍 Heaven-Reliant Sword, the Dragon-Slaying Saber's only rival: 倚天不出，誰與爭鋒");
    expect(html).toContain("data-sect-note");
  });

  it("names the duet on the music fact, which round 34 made its object", () => {
    expect(textOf(label("fact:3", { id: "wanderer-duet", host: "fact:3" }))).toContain(
      "笑傲江湖 Laughing Proudly in the Jianghu, from The Smiling, Proud Wanderer",
    );
  });

  it("gives the Stack pillar the five banners' brigades", () => {
    expect(textOf(label("arch:6", null))).toContain("五行旗 洪水 Voice · 烈火 Brain · 巨木 Frame · 銳金 State · 厚土 the core");
  });

  it("names the Black Iron Heavy Sword on the arena's landmark", () => {
    expect(textOf(label("arena", { id: "heavy-iron-sword", host: "arena" }))).toContain(
      "玄鐵重劍 Black Iron Heavy Sword, from Return of the Condor Heroes",
    );
  });

  it("gives the jade scroll one line about its verses", () => {
    expect(textOf(label("resume", null))).toBe("Resume Verses from Jin Yong's novels");
  });

  it("leaves every other label as it was", () => {
    for (const id of ["gate", "gate-swords", "project:dispatchai", "fact:4", "moon"]) {
      const before = renderToStaticMarkup(<HoverLabel label={hotspotLabel(id)} />);
      expect(label(id, null)).toBe(before);
    }
  });
});

describe("the stop's panel", () => {
  it("lists its references for screen readers only", () => {
    const html = renderToStaticMarkup(<AreaPanel area="gate" onOpen={() => {}} references={["heaven-sword", "dragon-saber", "sun-moon"]} />);
    const list = html.slice(html.indexOf("<ul"));
    expect(list).toMatch(/^<ul class="sr-only" aria-label="Jin Yong references in this place">/);
    expect(textOf(list)).toContain("Heaven-Reliant Sword (倚天劍): The Dragon-Slaying Saber's only rival: 倚天不出，誰與爭鋒.");
    expect(textOf(list)).toContain("Dragon-Slaying Saber (屠龍刀): The blade whose holder rules the martial world: 武林至尊，寶刀屠龍.");
  });

  it("is unchanged without references (today's meta.json)", () => {
    const html = renderToStaticMarkup(<AreaPanel area="forge" onOpen={() => {}} />);
    expect(html).not.toContain("sr-only");
    expect(html).toBe(renderToStaticMarkup(<AreaPanel area="forge" onOpen={() => {}} references={[]} />));
  });
});
