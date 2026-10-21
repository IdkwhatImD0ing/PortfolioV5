import { describe, expect, it } from "vitest";
import {
  plainUrl,
  readHistoryState,
  readerUrl,
  resolveDeepLink,
  searchWithout,
  withHistoryState,
  withoutHistoryState,
} from "./links";

describe("resolveDeepLink", () => {
  it("opens what ?open= names, ahead of the hash", () => {
    expect(resolveDeepLink("project:dispatchai", "#education")).toEqual({
      link: { target: { area: "forge", item: "project:dispatchai" }, open: true },
      note: null,
    });
    expect(resolveDeepLink("resume", "")).toEqual({ link: { target: { area: "scroll", item: "resume" }, open: true }, note: null });
  });

  it("follows the hash: a section flies there, an item opens its reader", () => {
    expect(resolveDeepLink(null, "#projects")).toEqual({ link: { target: { area: "forge", item: null }, open: false }, note: null });
    expect(resolveDeepLink(null, "#project/dispatchai").link).toEqual({ target: { area: "forge", item: "project:dispatchai" }, open: true });
    expect(resolveDeepLink(null, "")).toEqual({ link: null, note: null });
  });

  it("an unknown item in a known section opens that section, and says so", () => {
    const r = resolveDeepLink("hackathon:999", "");
    expect(r.link).toEqual({ target: { area: "arena", item: null }, open: true });
    expect(r.note).toMatch(/Couldn't find "hackathon:999"/);
    expect(r.note).toMatch(/Hackathons/);
  });

  it("anything else unknown starts at the beginning, and says so", () => {
    const a = resolveDeepLink("nothing:1", "");
    expect(a.link).toBeNull();
    expect(a.note).toMatch(/isn't here/);
    const b = resolveDeepLink(null, "#nowhere");
    expect(b.link).toBeNull();
    expect(b.note).toMatch(/#nowhere/);
    // A bad ?open= still lets a good hash land.
    const c = resolveDeepLink("nothing:1", "#skills");
    expect(c.link).toEqual({ target: { area: "steles", item: null }, open: false });
    expect(c.note).toMatch(/isn't here/);
  });
});

describe("reader URLs", () => {
  it("names a project the way the main page does", () => {
    expect(readerUrl({ area: "forge", item: "project:dispatchai" }, "/sect", "?debug=1&open=resume")).toBe("/sect?debug=1#project/dispatchai");
  });

  it("names other items and whole sections with ?open=, which opens them again", () => {
    const u = readerUrl({ area: "arena", item: "hackathon:3" }, "/sect", "");
    expect(u).toBe("/sect?open=hackathon:3#hackathons");
    const q = new URL(u, "https://x.test");
    expect(resolveDeepLink(q.searchParams.get("open"), q.hash).link).toEqual({ target: { area: "arena", item: "hackathon:3" }, open: true });
    expect(readerUrl({ area: "library", item: null }, "/sect", "?tier=low")).toBe("/sect?tier=low&open=library#education");
    const s = new URL(readerUrl({ area: "library", item: null }, "/sect", ""), "https://x.test");
    expect(resolveDeepLink(s.searchParams.get("open"), s.hash).link).toEqual({ target: { area: "library", item: null }, open: true });
  });

  it("drops ?open= once no reader is open", () => {
    expect(plainUrl("summit", "/sect", "?open=project:dispatchai&debug=1")).toBe("/sect?debug=1#footer");
    expect(plainUrl(null, "/sect", "?open=resume")).toBe("/sect");
    expect(searchWithout("?a=1&open=x", "open")).toBe("?a=1");
  });
});

describe("history state", () => {
  it("round-trips beside Next.js's own keys", () => {
    const next = { __NA: true, __PRIVATE_NEXTJS_INTERNALS_TREE: [1] };
    const s = withHistoryState(next, { reader: { area: "forge", item: "project:dispatchai" }, page: false, depth: 2, nested: true });
    expect(s.__NA).toBe(true);
    expect(readHistoryState(s)).toEqual({ reader: { area: "forge", item: "project:dispatchai" }, page: false, depth: 2, nested: true });
    expect(withoutHistoryState(s)).toEqual(next);
  });

  it("ignores entries it did not write, and junk", () => {
    expect(readHistoryState(null)).toBeNull();
    expect(readHistoryState({ __NA: true })).toBeNull();
    expect(readHistoryState({ sect: { reader: { area: "nowhere", item: null }, depth: -3 } })).toEqual({
      reader: null,
      page: false,
      depth: 0,
      nested: false,
    });
  });
});
