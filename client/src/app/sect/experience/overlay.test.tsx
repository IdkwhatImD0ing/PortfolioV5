/**
 * The overlays that show what the free look found: the hover label (name, Chinese name and a line
 * about the thing, for every kind of hotspot) and the Recentre button for a view turned round. And
 * what a phone's HUD keeps: the top bar, the place row's name and the look hint in its spot.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { hotspotLabel, type HotspotLabel } from "@/lib/sect/content";
import { CompactRail, HoverLabel, LookHint, placeHoverLabel, RecentreButton, SectionRail, TopLinks, WIDE_HUD, type RailStop } from "./overlay";

const ENTITIES: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', "#x27": "'", "#39": "'", nbsp: " " };
const textOf = (html: string) =>
  html
    .replace(/<[^>]+>/g, " ")
    .replace(/&(amp|lt|gt|quot|#x27|#39|nbsp);/g, (_, e: string) => ENTITIES[e])
    .replace(/\s+/g, " ")
    .trim();
const squash = (s: string) => s.replace(/\s+/g, " ").trim();

const label = (l: HotspotLabel | null) => renderToStaticMarkup(<HoverLabel label={l} />);
const button = (visible: boolean) => renderToStaticMarkup(<RecentreButton visible={visible} onRecentre={() => {}} />);

const meta = JSON.parse(readFileSync(path.resolve(__dirname, "../../../../public/sect/full/meta.json"), "utf8")) as {
  hotspots: { id: string; label?: string }[];
};

describe("HoverLabel", () => {
  it("shows the title, the Chinese name and the blurb", () => {
    const html = label({ title: "Dispatch AI", zh: "传令符", blurb: "Talisman · ★ First place" });
    const text = textOf(html);
    expect(text).toContain("Dispatch AI");
    expect(text).toContain("传令符");
    expect(text).toContain("Talisman · ★ First place");
    // The Chinese name is marked as Chinese; the blurb is cut to two lines.
    expect(html).toContain('lang="zh"');
    expect(html.indexOf('lang="zh"')).toBeLessThan(html.indexOf("传令符"));
    expect(html).toContain("line-clamp-2");
  });

  it("is empty with nothing hovered, and leaves out parts a label does not have", () => {
    expect(textOf(label(null))).toBe("");
    const html = label({ title: "Gate lions" });
    expect(textOf(html)).toBe("Gate lions");
    expect(html).not.toContain('lang="zh"');
  });

  it("shows the label of every hotspot in the scene", () => {
    const kinds = new Set<string>();
    for (const h of meta.hotspots) {
      const l = hotspotLabel(h.id, h.label);
      const text = textOf(label(l));
      expect(text, h.id).toContain(squash(l.title));
      if (l.zh) expect(text, h.id).toContain(l.zh);
      if (l.blurb) expect(text, h.id).toContain(squash(l.blurb));
      kinds.add(h.id.split(":")[0]);
    }
    // Every kind of item is in the scene. Items carry no Chinese name (the area's would repeat it); the moon has its own.
    for (const kind of ["project", "hackathon", "role", "school", "skills", "arch", "fact", "resume", "moon"]) {
      expect(kinds.has(kind), kind).toBe(true);
      const id = meta.hotspots.find((h) => h.id.split(":")[0] === kind)!.id;
      const l = hotspotLabel(id);
      if (kind === "moon") expect(l.zh).toBeTruthy();
      else expect(l.zh, id).toBeUndefined();
    }
    // An area's own hotspot names the place, in both languages, with its summary.
    const forge = hotspotLabel("forge");
    expect(forge.zh).toBeTruthy();
    expect(forge.blurb).toBeTruthy();
  });
});

describe("RecentreButton", () => {
  it("is there only while the view is turned round, with a label that says what it does", () => {
    expect(button(false)).toBe("");
    const html = button(true);
    expect(html).toContain('type="button"');
    expect(html).toContain('aria-label="Recentre the view"');
    expect(textOf(html)).toContain("Recentre");
  });
});

const noop = () => {};
const css = readFileSync(path.resolve(__dirname, "../sect.css"), "utf8").replace(/\r\n/g, "\n");
/** The body of the first `@media <query> {...}` block in sect.css that holds `selector`. */
const mediaBlock = (query: string, selector: string) => {
  let from = 0;
  for (;;) {
    const at = css.indexOf(`@media ${query} {`, from);
    if (at < 0) return "";
    const end = css.indexOf("\n}\n", at);
    const block = css.slice(at, end);
    if (block.includes(selector)) return block;
    from = end;
  }
};
const stops: RailStop[] = [
  { id: "gate", label: "Mountain Gate", zh: "山门", section: "Welcome" },
  { id: "mirror", label: "Heart-Mirror Terrace", zh: "心镜台", section: "About" },
];

describe("the phone HUD's rule", () => {
  // WIDE_HUD as Tailwind spells it in a class: [@media(min-width:48rem)_and_(min-height:31.25rem)].
  const tw = `[@media${WIDE_HUD.replace(/: /g, ":").replace(/ /g, "_")}]`;

  it("is the rule the side rail and the place row swap on", () => {
    expect(tw).toBe("[@media(min-width:48rem)_and_(min-height:31.25rem)]");
    expect(renderToStaticMarkup(<SectionRail stops={stops} active="gate" atHold={false} onJump={noop} />)).toContain(`${tw}:block`);
    expect(renderToStaticMarkup(<CompactRail stops={stops} active="gate" onJump={noop} />)).toContain(`${tw}:hidden`);
  });

  it("is turned round for sect.css's phone rules (no side rail: under 48rem wide, or under 31.25rem tall)", () => {
    expect(mediaBlock("(max-width: 47.99rem), (max-height: 31.24rem)", ".sect-toplinks-page")).not.toBe("");
  });
});

describe("TopLinks", () => {
  const html = renderToStaticMarkup(<TopLinks onReadAsPage={noop} />);

  it("names the owner, with Read as page after a divider", () => {
    expect(textOf(html)).toBe("Bill Zhang art3m1s.me Read as page");
    expect(html).toMatch(/<span aria-hidden="true" class="sect-toplinks-rule [^"]*"><\/span><button type="button" class="sect-toplinks-page /);
  });

  it("shows the domain only beside the side rail; screen readers always read it", () => {
    const domain = /<span class="([^"]+)">art3m1s\.me<\/span>/.exec(html)![1];
    expect(domain).toMatch(/^sr-only /);
    expect(domain).toContain("[@media(min-width:48rem)_and_(min-height:31.25rem)]:not-sr-only");
    expect(domain).not.toContain("md:not-sr-only");
  });

  it("keeps Read as page on phones only as a skip link, shown when the keyboard reaches it", () => {
    const phone = mediaBlock("(max-width: 47.99rem), (max-height: 31.24rem)", ".sect-toplinks-page");
    // Scoped, so the divider's own rule (.sect-brushrule-v, later in the file) does not show it again.
    expect(phone).toMatch(/\.sect-toplinks \.sect-toplinks-rule \{\s*display: none;/);
    expect(phone).toMatch(/\.sect-toplinks-page:not\(:focus\) \{[^}]*clip-path: inset\(50%\);/);
    expect(phone).toMatch(/\.sect-toplinks-page:focus \{[^}]*position: absolute;[^}]*top: calc\(100% \+ 0\.375rem\);/);
    // Never display:none: it stays a real, reachable button.
    expect(phone).not.toMatch(/\.sect-toplinks-page[^{]*\{[^}]*display: none/);
  });
});

describe("CompactRail's place name", () => {
  const name = (props: { atHold?: boolean; labelHidden?: boolean }) =>
    /<p aria-hidden="true"(?: data-hold="true")? class="sect-rail-place [^"]*"/.exec(
      renderToStaticMarkup(<CompactRail stops={stops} active="mirror" onJump={noop} {...props} />),
    )![0];

  it("shows between stops", () => {
    const p = name({ atHold: false });
    expect(p).toContain("opacity-100");
    expect(p).not.toContain("data-hold");
  });

  it("hides at a stop, marked so a voice call can bring it back on a phone held upright", () => {
    const p = name({ atHold: true });
    expect(p).toContain("opacity-0");
    expect(p).toContain('data-hold="true"');
    const upright = mediaBlock("(max-width: 47.99rem)", ".sect-rail-place");
    expect(upright).toMatch(/body:has\(\.sect-orb \[role="dialog"\]\) \.sect-rail-place\[data-hold\] \{\s*opacity: 1;/);
    expect(upright).toMatch(/body:has\(\.sect-orb \[role="dialog"\]\) \.sect-lookhint \{\s*visibility: hidden;/);
  });

  it("stays hidden under the intro, call or not", () => {
    for (const atHold of [false, true]) {
      const p = name({ atHold, labelHidden: true });
      expect(p).toContain("opacity-0");
      expect(p).not.toContain("data-hold");
    }
  });
});

describe("LookHint", () => {
  it("takes the place name's spot under the place row on a phone, and its old corner on wider screens", () => {
    const hint = renderToStaticMarkup(<LookHint visible touch />);
    const rail = renderToStaticMarkup(<CompactRail stops={stops} active="gate" onJump={noop} />);
    const railTop = Number(/top-\[([\d.]+)rem\]/.exec(rail)![1]);
    // The row's buttons are 2.75rem tall (h-11); the name sits right under them.
    expect(rail).toContain("h-11");
    const hintTop = Number(/ top-\[([\d.]+)rem\]/.exec(hint)![1]);
    expect(hintTop).toBeCloseTo(railTop + 2.75, 5);
    expect(hint).toContain("md:top-[4.4rem]");
    expect(hint).toContain("sect-lookhint");
    expect(textOf(hint)).toBe("Swipe to look around");
    expect(textOf(renderToStaticMarkup(<LookHint visible />))).toBe("Drag to look around");
  });
});

describe("placeHoverLabel", () => {
  const view = { w: 1600, h: 900 };
  const label = { w: 240, h: 60 };
  // A content panel up at a stop, on the right of the window.
  const panel = { left: 1150, top: 200, right: 1560, bottom: 700 };
  const overlaps = (x: number, y: number, b: typeof panel, gap = 0) =>
    x - label.w / 2 < b.right + gap && x + label.w / 2 > b.left - gap && y - label.h < b.bottom + gap && y > b.top - gap;

  it("keeps the label over its anchor when nothing is in the way", () => {
    expect(placeHoverLabel([800, 400], label, view, [panel])).toEqual([800, 400]);
  });

  it("keeps it inside the window, as before", () => {
    expect(placeHoverLabel([20, 10], label, view)).toEqual([128, 68]);
    expect(placeHoverLabel([1590, 899], label, view)).toEqual([1472, 892]);
  });

  it("moves a label that would cover the panel to the panel's near side, clear by the gap", () => {
    // The abode waterfall case: the label's right side runs about 70 px into the panel.
    const [x, y] = placeHoverLabel([panel.left + 70 - label.w / 2, 450], label, view, [panel]);
    expect(y).toBe(450);
    expect(x + label.w / 2).toBeLessThanOrEqual(panel.left - 12);
    expect(x + label.w / 2).toBeGreaterThan(panel.left - 14);
    expect(overlaps(x, y, panel, 12)).toBe(false);
  });

  it("takes the shortest way out: above a wide, low panel", () => {
    const wide = { left: 100, top: 700, right: 1500, bottom: 880 };
    const [x, y] = placeHoverLabel([800, 720], label, view, [wide]);
    expect(x).toBe(800);
    expect(y).toBeLessThanOrEqual(wide.top - 12);
    expect(overlaps(x, y, wide, 12)).toBe(false);
  });

  it("never pushes the label out of the window to clear a panel", () => {
    // A panel filling the window: no way out, so the label stays put (inside the window).
    const full = { left: 0, top: 0, right: 1600, bottom: 900 };
    expect(placeHoverLabel([800, 400], label, view, [full])).toEqual([800, 400]);
  });

  it("clears every panel when two are up during a cross-fade", () => {
    const left = { left: 40, top: 200, right: 450, bottom: 700 };
    const [x, y] = placeHoverLabel([480, 400], label, view, [left, panel]);
    expect(overlaps(x, y, left, 12)).toBe(false);
    expect(overlaps(x, y, panel, 12)).toBe(false);
    expect(x - label.w / 2).toBeGreaterThanOrEqual(8);
    expect(x + label.w / 2).toBeLessThanOrEqual(view.w - 8);
  });
});
