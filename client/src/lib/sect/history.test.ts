import { describe, expect, it } from "vitest";
import { LEAVE_TIMEOUT_MS, PageHistory, type HistoryLike, type LocationLike } from "./history";
import { readHistoryState, readerUrl } from "./links";

/**
 * A browser's session history for one document: push and replace act at once, go() is finished
 * later (traverse), and a traversal fires popstate, then hashchange when only the fragment changed.
 */
class FakeBrowser implements HistoryLike, LocationLike {
  entries: { state: unknown; url: string }[];
  index = 0;
  pending: number[] = [];
  t = 0;

  constructor(url: string) {
    this.entries = [{ state: null, url }];
  }

  get state(): unknown {
    return this.entries[this.index].state;
  }
  get url(): string {
    return this.entries[this.index].url;
  }
  get pathname(): string {
    return new URL(this.url, "https://x.test").pathname;
  }
  get search(): string {
    return new URL(this.url, "https://x.test").search;
  }
  get hash(): string {
    return new URL(this.url, "https://x.test").hash;
  }

  pushState(data: unknown, _unused: string, url?: string | null): void {
    this.entries.splice(this.index + 1);
    this.entries.push({ state: structuredClone(data), url: url ?? this.url });
    this.index++;
  }
  replaceState(data: unknown, _unused: string, url?: string | null): void {
    this.entries[this.index] = { state: structuredClone(data), url: url ?? this.url };
  }
  go(delta: number): void {
    this.pending.push(delta);
  }

  /** The browser finishes the oldest traversal (go, or the Back button: `delta`). */
  traverse(handlers: { pop: (state: unknown) => void; hash: () => void }, delta?: number): void {
    const d = delta ?? this.pending.shift();
    if (d === undefined) throw new Error("nothing to traverse");
    const before = this.url;
    this.index += d;
    const after = this.url;
    const doc = (u: string) => u.split("#")[0];
    const frag = (u: string) => u.split("#")[1] ?? "";
    handlers.pop(this.state);
    if (doc(before) === doc(after) && frag(before) !== frag(after)) handlers.hash();
  }
}

/** The page's handlers as sect-experience.tsx wires them: the camera's area, and where a hashchange flies. */
function page(b: FakeBrowser, ph: PageHistory, camera: { area: string; open: boolean }) {
  const flights: string[] = [];
  const handlers = {
    pop: (state: unknown) => {
      const closing = camera.open;
      ph.arrived(state, camera.area, closing);
      const st = readHistoryState(state);
      if (!st?.reader) camera.open = false;
    },
    hash: () => {
      if (ph.ownHashChange()) return;
      const st = readHistoryState(b.state);
      if (st && (st.reader || st.page)) return;
      flights.push(b.hash);
    },
  };
  return { flights, handlers };
}

function setup(start = "/sect") {
  const b = new FakeBrowser(start);
  const ph = new PageHistory(b, b, () => b.t);
  return { b, ph };
}

/** Opens a reader as the page does (a new entry above the flight's, which is pointed at the area). */
function openReader(ph: PageHistory, b: FakeBrowser, area: "mirror" | "forge", item: string | null = null) {
  const cur = ph.current();
  const ours = cur !== null && (cur.reader !== null || cur.page);
  const t = { area, item };
  ph.write(ours ? "replace" : "push", { reader: t, page: false, depth: (cur?.depth ?? 0) + (ours ? 0 : 1), nested: false }, readerUrl(t, b.pathname, b.search), area);
}

describe("PageHistory", () => {
  it("open, Next, close: the walk back keeps the camera's place and flies nowhere", () => {
    const { b, ph } = setup();
    const camera = { area: "mirror", open: false };
    const { flights, handlers } = page(b, ph, camera);
    expect(ph.follow("mirror")).toBe(true);
    expect(b.url).toBe("/sect#about");

    openReader(ph, b, "mirror");
    camera.open = true;
    expect(b.entries.map((e) => e.url)).toEqual(["/sect#about", "/sect?open=mirror#about"]);
    // Next: the camera flies to the forge and the reader's entry is rewritten there.
    camera.area = "forge";
    openReader(ph, b, "forge");
    expect(b.entries.map((e) => e.url)).toEqual(["/sect#about", "/sect?open=forge#projects"]);

    // Esc: the walk back starts; the browser has not finished it yet.
    camera.open = false;
    ph.leave("forge");
    expect(ph.leaving).toBe(true);
    // The hash-follow tick must not rewrite the entry being left (that is what made the arrival a
    // hash-only change that flew the camera back to #about).
    expect(ph.follow("forge")).toBe(false);
    expect(b.url).toBe("/sect?open=forge#projects");

    b.traverse(handlers);
    expect(ph.leaving).toBe(false);
    expect(b.index).toBe(0);
    expect(b.url).toBe("/sect#projects");
    expect(flights).toEqual([]);
    expect(ph.follow("forge")).toBe(true);
    expect(b.url).toBe("/sect#projects");
  });

  it("the old order of events (hash-follow first) is now an ignored hashchange, not a flight", () => {
    const { b, ph } = setup();
    const camera = { area: "mirror", open: false };
    const { flights, handlers } = page(b, ph, camera);
    ph.follow("mirror");
    openReader(ph, b, "mirror");
    camera.open = true;
    camera.area = "forge";
    openReader(ph, b, "forge", "project:dispatchai");
    expect(b.url).toBe("/sect#project/dispatchai");
    // The visitor presses Back (no walk of the page's own): only the hash changes, so the browser
    // fires hashchange after popstate. The arrival names the forge, and its hashchange is its own.
    b.traverse(handlers, -1);
    expect(b.url).toBe("/sect#projects");
    expect(flights).toEqual([]);
  });

  it("a hash the visitor typed still flies (Back between plain entries)", () => {
    const { b, ph } = setup("/sect#projects");
    const camera = { area: "forge", open: false };
    const { flights, handlers } = page(b, ph, camera);
    b.pushState(null, "", "/sect#skills");
    camera.area = "steles";
    b.traverse(handlers, -1);
    expect(b.url).toBe("/sect#projects");
    expect(flights).toEqual(["#projects"]);
  });

  it("Back from a project inside the reader returns to its list without renaming anything", () => {
    const { b, ph } = setup();
    const camera = { area: "forge", open: false };
    const { flights, handlers } = page(b, ph, camera);
    ph.follow("forge");
    openReader(ph, b, "forge");
    camera.open = true;
    const list = b.url;
    ph.write("push", { reader: { area: "forge", item: "project:dispatchai" }, page: false, depth: 2, nested: true }, "/sect#project/dispatchai");
    b.traverse(handlers, -1);
    expect(b.url).toBe(list);
    expect(readHistoryState(b.state)?.reader).toEqual({ area: "forge", item: null });
    expect(flights).toEqual([]);
  });

  it("on the entry the visitor arrived on, closing cleans the URL in place", () => {
    const { b, ph } = setup("/sect?open=resume#resume");
    // A deep link's reader takes over the entry the visitor arrived on (depth 0).
    const t = { area: "scroll" as const, item: "resume" };
    ph.write("replace", { reader: t, page: false, depth: 0, nested: false }, readerUrl(t, b.pathname, b.search));
    expect(b.url).toBe("/sect?open=resume#resume");
    ph.leave("scroll");
    expect(ph.leaving).toBe(false);
    expect(b.pending).toEqual([]);
    expect(b.url).toBe("/sect#resume");
    expect(b.state).toBeNull();
  });

  it("a walk back that never arrives stops holding the hash", () => {
    const { b, ph } = setup();
    ph.follow("mirror");
    openReader(ph, b, "mirror");
    ph.leave("mirror");
    expect(ph.follow("mirror")).toBe(false);
    b.t += LEAVE_TIMEOUT_MS + 1;
    expect(ph.leaving).toBe(false);
    expect(ph.follow("mirror")).toBe(true);
  });

  it("an arrival's hashchange mark is used once and expires", () => {
    const { b, ph } = setup("/sect#about");
    b.pushState({ sect: { reader: { area: "forge", item: null }, page: false, depth: 1, nested: false } }, "", "/sect#project/x");
    expect(ph.arrived(null, "forge", true)).toBe(true);
    expect(ph.ownHashChange()).toBe(true);
    expect(ph.ownHashChange()).toBe(false);
    ph.arrived(null, "forge", true);
    b.t += 5000;
    expect(ph.ownHashChange()).toBe(false);
    // A popstate onto one of the page's views renames nothing.
    expect(ph.arrived({ sect: { reader: { area: "forge", item: null }, page: false, depth: 1, nested: false } }, "mirror", true)).toBe(false);
  });
});
