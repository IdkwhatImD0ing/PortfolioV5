import { describe, expect, it } from "vitest";
import { HACKATHONS, PROJECTS } from "@/lib/portfolio-data";
import { FORGE_RING, PROJECT_ARTIFACTS, onRing, projectArtifact, ringWin } from "./artifacts";

describe("project artifacts", () => {
  it("gives every project on the ring its own artifact", () => {
    expect(Object.keys(PROJECT_ARTIFACTS)).toEqual([...FORGE_RING]);
    const names = Object.values(PROJECT_ARTIFACTS).map((a) => a.name);
    expect(new Set(names).size).toBe(names.length);
    for (const a of Object.values(PROJECT_ARTIFACTS)) {
      expect(a.zh).toMatch(/^[一-鿿]+$/);
      expect(a.body.length).toBeGreaterThan(20);
    }
  });

  it("puts only projects that won on the ring, biggest win first", () => {
    for (const id of FORGE_RING) expect(PROJECTS.some((p) => p.id === id)).toBe(true);
    const at = FORGE_RING.map((id) => HACKATHONS.indexOf(ringWin(id)!));
    expect(at.every((i) => i >= 0)).toBe(true);
    expect([...at].sort((a, b) => a - b)).toEqual(at);
    expect(ringWin("tft")?.prize).toBe("Sustainability");
    for (const id of ["courtvision", "secway", "talktuahduck", "instarizz"]) {
      expect(onRing(id)).toBe(false);
      expect(ringWin(id)).toBeNull();
    }
  });

  it("resolves aliases and ignores projects outside the ring", () => {
    expect(projectArtifact("talktuahbank")?.zh).toBe("聚宝盆");
    expect(projectArtifact("dispatch-ai")?.name).toBe("Command Flag");
    expect(projectArtifact("magicloops")).toBeNull();
    expect(projectArtifact("not-a-project")).toBeNull();
  });
});
