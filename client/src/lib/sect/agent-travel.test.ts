import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { agentRoute, talismanInkOrigin, type AgentRouteInput } from "./agent-travel";

const base: AgentRouteInput = { inkUp: false, atPlace: false, overlay: true, isArea: true };

describe("agentRoute", () => {
  it("takes the visitor to another place under the map's ink, not a fly-through", () => {
    expect(agentRoute(base)).toBe("ink");
  });

  it("opens what was asked for at once when the camera is already there", () => {
    expect(agentRoute({ ...base, atPlace: true })).toBe("here");
  });

  it("waits for an ink that is already up (the latest command runs once it clears)", () => {
    expect(agentRoute({ ...base, inkUp: true })).toBe("queue");
    expect(agentRoute({ ...base, inkUp: true, atPlace: true })).toBe("queue");
  });

  it("flies only where no ink can show: ?ui=0 captures, or a target that is not a place", () => {
    expect(agentRoute({ ...base, overlay: false })).toBe("fly");
    expect(agentRoute({ ...base, isArea: false })).toBe("fly");
  });
});

describe("talismanInkOrigin", () => {
  const view = { w: 1600, h: 900 };

  it("starts the ink at the middle of the talisman", () => {
    expect(talismanInkOrigin({ left: 1500, top: 800, width: 64, height: 64 }, view)).toEqual([1532, 832]);
  });

  it("keeps the start on screen", () => {
    expect(talismanInkOrigin({ left: 1590, top: 890, width: 40, height: 40 }, view)).toEqual([1600, 900]);
    expect(talismanInkOrigin({ left: -40, top: -40, width: 20, height: 20 }, view)).toEqual([0, 0]);
  });

  it("falls back to the bottom-right corner, where the talisman lives", () => {
    expect(talismanInkOrigin(null, view)).toEqual([1540, 840]);
    expect(talismanInkOrigin({ left: 10, top: 10, width: 0, height: 0 }, view)).toEqual([1540, 840]);
  });
});

describe("the sect routes the agent's commands through agentRoute", () => {
  const src = readFileSync(path.resolve(__dirname, "../../app/sect/experience/sect-experience.tsx"), "utf8");
  const route = src.slice(src.indexOf("const routeVoice = "), src.indexOf("useVoiceRouting(routeVoice"));

  it("asks agentRoute, and sends the ink from the talisman", () => {
    expect(route).toContain("agentRoute(");
    expect(route).toContain("talismanInkOrigin(");
    expect(route).toContain('travel: "ink"');
  });

  it("keeps a command that arrives under the ink for when it clears", () => {
    expect(route).toContain("queuedVoice.current = cmd");
    expect(src).toContain("const cmd = queuedVoice.current;");
  });
});
