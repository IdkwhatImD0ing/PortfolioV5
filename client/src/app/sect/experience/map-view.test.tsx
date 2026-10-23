/**
 * The map's markup before its files arrive (the dialog, its list of every place, the phone tabs),
 * its seals' emblems, the Map button, and fast travel's ink card. The placing itself is
 * lib/sect/map.test.ts; the travel's shapes lib/sect/travel.test.ts.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AREA_IDS, AREAS } from "@/lib/sect/areas";
import { SECTION_NAMES } from "@/lib/sect/content";
import { parseCameraData, parseMeta } from "@/lib/sect/parse";
import { InkTravel } from "./ink-travel";
import { EMBLEMS, Emblem, HereGlyph } from "./map-emblems";
import MapView from "./map-view";
import { MapButton, type PlaceGroup, type RailStop } from "./overlay";

const PUBLIC = path.resolve(__dirname, "../../../../public/sect/full");
const meta = parseMeta(JSON.parse(readFileSync(path.join(PUBLIC, "meta.json"), "utf8")));
const camera = parseCameraData(JSON.parse(readFileSync(path.join(PUBLIC, "camera.json"), "utf8")));

const stops: RailStop[] = AREAS.map((a) => ({ id: a.id, label: a.label, zh: a.zh, section: SECTION_NAMES[a.id] }));
const groups: PlaceGroup[] = AREAS.map((a) => ({
  id: a.id,
  section: SECTION_NAMES[a.id],
  items: [
    { id: a.id, label: a.label, area: a.id },
    { id: `${a.id}:thing`, label: `${a.label} thing`, area: a.id },
  ],
}));
const noop = () => {};

const view = (active: string | null) =>
  renderToStaticMarkup(
    <MapView
      base="/sect/map"
      stops={stops}
      groups={groups}
      meta={meta}
      camera={camera}
      frame={352}
      active={active}
      atHold
      onClose={noop}
      onTravel={noop}
      onOpenHere={noop}
      onFocusPlace={noop}
      onSelectPlace={noop}
    />,
  );

describe("MapView", () => {
  it("is a modal dialog named by its title and described by how to travel", () => {
    const html = view("forge");
    expect(html).toMatch(/role="dialog"/);
    expect(html).toMatch(/aria-modal="true"/);
    expect(html).toContain('aria-labelledby="sect-map-title"');
    expect(html).toMatch(/id="sect-map-title"[^>]*>Map of the sect</);
    expect(html).toContain('aria-describedby="sect-map-help"');
    expect(html).toMatch(/id="sect-map-help"[^>]*>.*Click a seal to travel there/);
    expect(html).toContain('aria-label="Close the map"');
  });

  it("keeps every place and item in its list, and marks where the visitor is", () => {
    const html = view("forge");
    for (const g of groups) {
      expect(html).toContain(`id="sect-places-${g.id}"`);
      for (const p of g.items) expect(html).toContain(`>${p.label}</button>`);
    }
    expect(html.match(/you are here/g)).toHaveLength(1);
    expect(html.indexOf("you are here")).toBeGreaterThan(html.indexOf('id="sect-places-forge"'));
    expect(html.indexOf("you are here")).toBeLessThan(html.indexOf('id="sect-places-arena"'));
  });

  it("explains the map and its keys in the side column (shown on wide screens)", () => {
    const html = view("forge");
    expect(html).toMatch(/class="sect-map-side"/);
    expect(html).toContain("<kbd>Enter</kbd> Travel");
    expect(html).toContain("<kbd>M</kbd> Close");
    // The Chinese title rides beside the English one.
    expect(html).toMatch(/lang="zh"[^>]*>明教全图</);
  });

  it("offers the map and the list as two tabs (shown on phones)", () => {
    const html = view(null);
    expect(html).toMatch(/aria-pressed="true"[^>]*>Map</);
    expect(html).toMatch(/aria-pressed="false"[^>]*>All places</);
    expect(html).toContain('data-pane="map"');
  });
});

describe("emblems", () => {
  it("gives every stop its own drawing", () => {
    const drawn = new Set<string>();
    for (const id of AREA_IDS) {
      expect(EMBLEMS[id], id).toBeTruthy();
      const svg = renderToStaticMarkup(<Emblem id={id} />);
      expect(svg).toContain('aria-hidden="true"');
      expect(svg).toContain('viewBox="0 0 40 40"');
      drawn.add(svg);
    }
    expect(drawn.size).toBe(AREA_IDS.length);
  });

  it("draws the visitor's mark as the sun beside the moon", () => {
    const svg = renderToStaticMarkup(<HereGlyph />);
    expect(svg).toContain("var(--sect-cinnabar)");
    expect(svg.match(/<circle/g)?.length).toBeGreaterThanOrEqual(3);
    expect(svg).toContain("<path");
  });
});

describe("MapButton", () => {
  it("opens a dialog, says so, and names its key", () => {
    const html = renderToStaticMarkup(<MapButton open={false} onOpen={noop} />);
    expect(html).toContain("data-sect-places");
    expect(html).toContain('aria-haspopup="dialog"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('aria-keyshortcuts="M"');
    expect(html).toMatch(/>Map<\/button>$/);
  });
});

describe("InkTravel", () => {
  it("names the place it travels to, in Chinese and English, with its section", () => {
    const html = renderToStaticMarkup(
      <InkTravel request={{ key: 1, area: "library", at: [10, 10] }} reducedMotion={false} progress={0.4} arrive={() => Promise.resolve()} onDone={noop} />,
    );
    expect(html).toContain("藏经阁");
    expect(html).toContain("Scripture Pavilion");
    expect(html).toContain("Education");
    expect(html).toContain('data-phase="cover"');
    // A status line for screen readers, empty until the place is slow to come, and no progress bar yet.
    expect(html).toMatch(/role="status"[^>]*><\/p>/);
    expect(html).not.toContain('role="progressbar"');
    // The Loading line is drawn (hidden) at the progress so far.
    expect(html).toContain("scaleX(0.4)");
  });
});
