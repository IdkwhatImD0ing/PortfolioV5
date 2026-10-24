import { describe, expect, it } from "vitest";
import { areaForSection } from "./sect/areas";
import { commandTarget } from "./sect/content";
import {
  applyNavigation,
  metaToNavigationAction,
  PAGE_TO_SECTION,
  VoiceBus,
  type NavigationMeta,
  type VoiceCommand,
} from "./voice-bus";

describe("metaToNavigationAction", () => {
  it("returns null for null/undefined/missing-page payloads", () => {
    expect(metaToNavigationAction(null)).toBeNull();
    expect(metaToNavigationAction(undefined)).toBeNull();
    expect(metaToNavigationAction({ type: "navigation" } as NavigationMeta)).toBeNull();
  });

  it("returns null when type is not 'navigation'", () => {
    expect(
      metaToNavigationAction({ type: "other", page: "education" } as NavigationMeta),
    ).toBeNull();
  });

  it("emits an open command when navigating to a specific project", () => {
    const action = metaToNavigationAction({
      type: "navigation",
      page: "project",
      project_id: "dispatch-ai",
    });
    expect(action).toEqual({ type: "open", id: "dispatch-ai" });
  });

  it("uses the canonical Pinecone slug for the open command", () => {
    // The agent emits Pinecone IDs; the routing layer should not rewrite
    // them. Alias resolution happens later in projects.tsx (findProject).
    const action = metaToNavigationAction({
      type: "navigation",
      page: "project",
      project_id: "sentinelai-dec0jp",
    });
    expect(action).toEqual({ type: "open", id: "sentinelai-dec0jp" });
  });

  it("falls back to a scroll-to-projects when no project_id is provided", () => {
    const action = metaToNavigationAction({
      type: "navigation",
      page: "project",
    });
    expect(action).toEqual({ type: "scroll", id: "projects" });
  });

  it.each([
    ["landing", "hero"],
    ["about", "about"],
    ["experience", "experience"],
    ["skills", "skills"],
    ["personal", "personal"],
    ["education", "education"],
    ["resume", "resume"],
    ["hackathon", "hackathons"],
    ["architecture", "architecture"],
  ] as const)("maps page='%s' to scroll-to-'%s'", (page, section) => {
    const action = metaToNavigationAction({ type: "navigation", page });
    expect(action).toEqual({ type: "scroll", id: section });
  });

  it("returns null for an unknown page value", () => {
    expect(
      metaToNavigationAction({
        type: "navigation",
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        page: "blog" as any,
      }),
    ).toBeNull();
  });
});

describe("applyNavigation", () => {
  it("emits the command for navigation metadata", () => {
    const seen: VoiceCommand[] = [];
    const off = VoiceBus.on((cmd) => seen.push(cmd));

    applyNavigation({ type: "navigation", page: "project", project_id: "dispatch-ai" });
    applyNavigation({ type: "navigation", page: "resume" });
    off();

    expect(seen).toEqual([
      { type: "open", id: "dispatch-ai" },
      { type: "scroll", id: "resume" },
    ]);
  });

  it("does nothing for non-navigation or empty metadata", () => {
    const seen: VoiceCommand[] = [];
    const off = VoiceBus.on((cmd) => seen.push(cmd));

    applyNavigation(null);
    applyNavigation({ type: "other", page: "education" } as NavigationMeta);
    off();

    expect(seen).toEqual([]);
  });
});

describe("PAGE_TO_SECTION", () => {
  it("has an entry for every page the server can emit", () => {
    // Mirrors the server-side `_PAGE_TOOLS` values + 'project'. If a new
    // page is added on the server, this test should be updated in lockstep.
    const expected = [
      "landing",
      "about",
      "experience",
      "skills",
      "personal",
      "education",
      "resume",
      "hackathon",
      "architecture",
      "project",
    ];
    expect(Object.keys(PAGE_TO_SECTION).sort()).toEqual(expected.sort());
  });

  it("names a stop of the sect for every page, so every navigation flies somewhere", () => {
    // The sect is the whole site: a page's section must be an area's sectionId
    // (lib/sect/areas.ts), and the command must resolve to that area.
    for (const [page, section] of Object.entries(PAGE_TO_SECTION)) {
      const area = areaForSection(section);
      expect(area, `${page} -> ${section}`).not.toBeNull();
      const cmd = metaToNavigationAction({ type: "navigation", page: page as NavigationMeta["page"] });
      expect(cmd && commandTarget(cmd), page).toEqual({ area, item: null });
    }
  });

  it("opens a named project in the forge", () => {
    const cmd = metaToNavigationAction({ type: "navigation", page: "project", project_id: "dispatch-ai" });
    expect(cmd && commandTarget(cmd)).toEqual({ area: "forge", item: "project:dispatchai" });
  });
});
