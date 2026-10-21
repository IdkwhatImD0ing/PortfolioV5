/**
 * The machine check that all of the main page's content exists in /sect: every area reader, every
 * project detail and the one-page view are rendered to HTML, and every text and link of the
 * inventory (src/lib/sect/content-inventory.ts) must be in them.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { EDUCATION, EXPERIENCE, HACKATHONS, PERSONAL_FACTS, PORTFOLIO, PROJECTS } from "@/lib/portfolio-data";
import { AREA_IDS, type AreaId } from "@/lib/sect/areas";
import { AREA_THING_IDS, areaItemHotspots, areaSummary, itemDomId, type ContentTarget } from "@/lib/sect/content";
import { ARCH_SNIPPET } from "@/lib/sect/content-copy";
import { contentInventory } from "@/lib/sect/content-inventory";
import { AreaPanel, AreaReader, ContentFallback } from "./index";

const noop = () => {};

const ENTITIES: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', "#x27": "'", "#39": "'", nbsp: " " };
const decode = (s: string) => s.replace(/&(amp|lt|gt|quot|#x27|#39|nbsp);/g, (_, e: string) => ENTITIES[e]);
const squash = (s: string) => s.replace(/\s+/g, " ").trim();

/** Visible text of server-rendered HTML: no comments, no tags, entities decoded, spaces collapsed. */
function textOf(html: string): string {
  return squash(decode(html.replace(/<!--.*?-->/g, "").replace(/<[^>]+>/g, " ")).replace(/\s+([.,;:!?)])/g, "$1"));
}

/** Text with tags removed in place (no spaces added): code split into highlighted tokens reads whole. */
function flatOf(html: string): string {
  return squash(decode(html.replace(/<!--.*?-->/g, "").replace(/<[^>]+>/g, "")));
}

/** Every href / src / srcSet target, with next/image's /_next/image?url=... unwrapped. */
function urlsOf(html: string): Set<string> {
  const out = new Set<string>();
  for (const m of html.matchAll(/\s(?:href|src|srcSet)="([^"]*)"/g)) {
    for (const part of decode(m[1]).split(/,\s+/)) {
      const u = part.trim().split(/\s+/)[0];
      if (!u) continue;
      out.add(u);
      const inner = /^\/_next\/image\?url=([^&]+)/.exec(u);
      if (inner) out.add(decodeURIComponent(inner[1]));
    }
  }
  return out;
}

interface View {
  html: string;
  text: string;
  flat: string;
  urls: Set<string>;
}

const cache = new Map<string, View>();
function view(kind: "reader" | "page", target: ContentTarget | null) {
  const key = `${kind}:${target?.area ?? ""}:${target?.item ?? ""}`;
  const hit = cache.get(key);
  if (hit) return hit;
  const html =
    kind === "reader"
      ? renderToStaticMarkup(
          <AreaReader target={target} onClose={noop} onNavigate={noop} onHighlight={noop} onTalk={noop} onReadAsPage={noop} />,
        )
      : renderToStaticMarkup(<ContentFallback initial={target} onTalk={noop} />);
  const v: View = { html, text: textOf(html), flat: flatOf(html), urls: urlsOf(html) };
  cache.set(key, v);
  return v;
}

const escape = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const normText = (s: string) => textOf(escape(s));
const hasText = (v: View, t: string) => v.text.includes(normText(t)) || v.flat.includes(squash(t));

function expectContent(v: View, texts: string[], urls: string[], label: string) {
  for (const t of texts) expect(hasText(v, t), `${label}: text "${t.slice(0, 80)}" missing`).toBe(true);
  for (const u of urls) expect(v.urls.has(u), `${label}: link "${u}" missing`).toBe(true);
}

describe("every inventory item is in the sect", () => {
  const entries = contentInventory().filter(
    (e) => e.area && (e.status === "carried" || e.status === "adapted") && (e.texts?.length || e.urls?.length),
  );

  it("covers a real share of the inventory", () => {
    expect(entries.length).toBeGreaterThan(120);
  });

  for (const e of entries) {
    const target: ContentTarget = e.project
      ? { area: "forge", item: `project:${e.project}` }
      : { area: e.area as AreaId, item: null };
    it(`${e.id} ${e.what.slice(0, 70)} (reader)`, () => {
      expectContent(view("reader", target), e.texts ?? [], e.urls ?? [], e.id);
    });
    it(`${e.id} (one-page view)`, () => {
      expectContent(view("page", e.project ? target : null), e.texts ?? [], e.urls ?? [], e.id);
    });
  }
});

describe("spot checks against the data", () => {
  it("lists all 15 projects in the forge reader and the page, with their GitHub links in the details", () => {
    const forge = view("reader", { area: "forge", item: null });
    const page = view("page", null);
    for (const p of PROJECTS) {
      expect(forge.text).toContain(p.name);
      expect(page.text).toContain(p.name);
      if (p.github) expect(view("reader", { area: "forge", item: `project:${p.id}` }).urls.has(p.github)).toBe(true);
    }
  });

  it("has every hackathon, role, school and fact", () => {
    const page = view("page", null);
    for (const h of HACKATHONS) expect(page.text).toContain(`★ ${h.prize}`);
    for (const r of EXPERIENCE) expect(page.text).toContain(r.role);
    for (const s of EDUCATION) expect(page.text).toContain(s.full);
    expect(page.text.match(/✦/g)?.length).toBe(PERSONAL_FACTS.length);
  });

  it("has the contact links and the resume download", () => {
    const summit = view("reader", { area: "summit", item: null });
    for (const u of [`mailto:${PORTFOLIO.email}`, PORTFOLIO.github, PORTFOLIO.linkedin, PORTFOLIO.devpost]) {
      expect(summit.urls.has(u)).toBe(true);
    }
    const scroll = view("reader", { area: "scroll", item: null });
    expect(scroll.html).toMatch(/href="\/resume.pdf" download="Bill-Zhang-Resume.pdf"/);
  });

  it("renders the architecture snippet in full", () => {
    const html = view("reader", { area: "formation", item: null }).html;
    const pre = html.match(/<pre[^>]*>([\s\S]*?)<\/pre>/)?.[1] ?? "";
    expect(decode(pre.replace(/<[^>]+>/g, ""))).toBe(ARCH_SNIPPET);
  });
});

describe("hotspot items are addressable", () => {
  it("every item hotspot has an element to focus in its area's reader and in the page", () => {
    const page = view("page", null);
    for (const a of AREA_IDS) {
      const reader = view("reader", { area: a, item: null });
      for (const h of areaItemHotspots(a)) {
        const id = `id="${itemDomId(h.id)}"`;
        if (h.id.startsWith("project:")) {
          expect(view("reader", { area: "forge", item: h.id }).html).toContain(id);
          expect(reader.html).toContain(id);
        } else {
          expect(reader.html, `${h.id} in ${a} reader`).toContain(id);
          expect(page.html, `${h.id} in page`).toContain(id);
        }
      }
    }
  });
});

describe("small objects open their own view", () => {
  // Every item except a project (the forge's detail, tested above), the resume scroll (the scroll
  // area's landmark) and the moon (a voice call), plus every named spot with a view.
  const items = [
    ...AREA_IDS.flatMap((a) => areaItemHotspots(a).map((h) => ({ area: a, id: h.id }))),
    ...Object.entries(AREA_THING_IDS).flatMap(([a, ids]) => (ids ?? []).map((id) => ({ area: a as AreaId, id }))),
  ].filter((x) => !x.id.startsWith("project:") && x.id !== "resume" && x.id !== "moon" && x.id !== "forge-hall");

  it("covers every kind", () => {
    const kinds = new Set(items.map((x) => (x.id.includes(":") ? x.id.split(":")[0] : "spot")));
    expect([...kinds].sort()).toEqual(["arch", "fact", "hackathon", "role", "school", "skills", "spot"]);
  });

  for (const { area, id } of items) {
    it(`${id} opens a view of its own, with a way back`, () => {
      const html = view("reader", { area, item: id }).html;
      expect(html, id).toMatch(new RegExp(`id="${itemDomId(id)}"[^>]*data-sc-top`));
      expect(html).toContain('class="sc-back"');
      // Not the whole list: the item's title is the only item anchor in the view.
      expect(html.match(/id="sect-item-/g)?.length, id).toBe(1);
      for (const m of html.matchAll(/<button([^>]*)>([\s\S]*?)<\/button>/g)) {
        const named = /aria-label="[^"]+"/.test(m[1]) || textOf(m[2]).length > 0;
        expect(named, `unnamed button in ${id}`).toBe(true);
      }
    });
  }

  it("the Forge Hall opens the forge at its standouts", () => {
    const html = view("reader", { area: "forge", item: "forge-hall" }).html;
    expect(html).toMatch(new RegExp(`id="${itemDomId("forge-hall")}"[^>]*data-sc-top`));
    expect(textOf(html)).toContain(`/${PROJECTS.length} standouts`);
  });

  it("the page view keeps the plain lists", () => {
    const html = view("page", { area: "mission", item: "role:3" }).html;
    for (const r of EXPERIENCE) expect(textOf(html)).toContain(normText(r.role));
  });
});

describe("reader and panel structure", () => {
  it("renders nothing without a target", () => {
    expect(renderToStaticMarkup(<AreaReader target={null} onClose={noop} onNavigate={noop} />)).toBe("");
  });

  it("is a labelled modal dialog with a named close button and area navigation", () => {
    for (const a of AREA_IDS) {
      const html = view("reader", { area: a, item: null }).html;
      expect(html).toMatch(/role="dialog"/);
      expect(html).toMatch(/aria-modal="true"/);
      expect(html).toContain(`aria-labelledby="sc-reader-title-${a}"`);
      expect(html).toMatch(/aria-label="Close [^"]+"/);
      expect(html).toContain('lang="zh"');
      const nav = html.match(/<nav aria-label="Other areas"[\s\S]*?<\/nav>/)?.[0] ?? "";
      expect(nav.match(/<button/g)?.length).toBe(a === "gate" || a === "summit" ? 1 : 2);
    }
  });

  it("gives every button a name", () => {
    for (const a of AREA_IDS) {
      const html = view("reader", { area: a, item: null }).html;
      for (const m of html.matchAll(/<button([^>]*)>([\s\S]*?)<\/button>/g)) {
        const named = /aria-label="[^"]+"/.test(m[1]) || textOf(m[2]).length > 0;
        expect(named, `unnamed button in ${a}: ${m[0].slice(0, 120)}`).toBe(true);
      }
    }
  });

  it("opens new tabs safely", () => {
    for (const a of AREA_IDS) {
      for (const m of view("reader", { area: a, item: null }).html.matchAll(/<a [^>]*target="_blank"[^>]*>/g)) {
        expect(m[0]).toContain('rel="noopener noreferrer"');
      }
    }
  });

  it("renders a hidden summary panel for every area with its action", () => {
    for (const a of AREA_IDS) {
      const html = renderToStaticMarkup(<AreaPanel area={a} onOpen={noop} />);
      const s = areaSummary(a);
      expect(html).toContain("visibility:hidden");
      expect(html).toContain('lang="zh"');
      expect(textOf(html)).toContain(normText(s.action));
      expect(textOf(html)).toContain(normText(s.title));
    }
    const gate = textOf(renderToStaticMarkup(<AreaPanel area="gate" onOpen={noop} />));
    expect(gate).toContain(PORTFOLIO.name);
    expect(gate).toContain(PORTFOLIO.tagline);
    expect(gate).toContain("Talk to the AI");
  });

  it("the one-page view has a navigation of all eleven areas", () => {
    const html = view("page", null).html;
    const nav = html.match(/<nav aria-label="Areas"[\s\S]*?<\/nav>/)?.[0] ?? "";
    expect(nav.match(/<a /g)?.length).toBe(AREA_IDS.length);
    expect(html).toContain("<main");
  });
});
