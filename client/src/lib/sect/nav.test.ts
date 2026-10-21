import { describe, expect, it } from "vitest";
import { AREAS } from "./areas";
import {
  adjacentStop,
  flightSeconds,
  hashForArea,
  navKeyIntent,
  navKeyTarget,
  navStops,
  nearestHold,
  panelSide,
  turnKeyIntent,
} from "./nav";
import { buildScrollMap } from "./scroll-map";
import type { CameraFrame, Hold } from "./types";

// The full flight's eleven holds (section_timeline.json hero frames).
const HOLDS: Hold[] = [
  ["gate", 93],
  ["mirror", 217],
  ["forge", 389],
  ["arena", 516],
  ["mission", 619],
  ["library", 818],
  ["steles", 967],
  ["scroll", 1103],
  ["formation", 1277],
  ["abode", 1449],
  ["summit", 1647],
].map(([id, frame]) => ({ id: id as string, label: id as string, frame: frame as number }));

const map = buildScrollMap(27, 1729, HOLDS, { dwellUnits: 42, ease: 0.55 });
const uOf = (id: string) => map.holds.find((h) => h.id === id)!.uMid;

describe("navStops", () => {
  it("lists start, the eleven holds and the end", () => {
    const s = navStops(map);
    expect(s.map((x) => x.id)).toEqual(["start", ...HOLDS.map((h) => h.id), "end"]);
    expect(s[s.length - 1].u).toBe(map.totalUnits);
  });
});

describe("adjacentStop", () => {
  it("goes to the next and previous hold", () => {
    expect(adjacentStop(map, 0, 1)?.id).toBe("gate");
    expect(adjacentStop(map, uOf("gate"), 1)?.id).toBe("mirror");
    expect(adjacentStop(map, uOf("forge"), -1)?.id).toBe("mirror");
    // Between two holds: forward is the next one, back is the one just passed.
    const mid = (uOf("arena") + uOf("mission")) / 2;
    expect(adjacentStop(map, mid, 1)?.id).toBe("mission");
    expect(adjacentStop(map, mid, -1)?.id).toBe("arena");
  });

  it("skips the stop the camera is already at (within a couple of units)", () => {
    expect(adjacentStop(map, uOf("library") + 1, 1)?.id).toBe("steles");
    expect(adjacentStop(map, uOf("library") - 1, -1)?.id).toBe("mission");
  });

  it("reaches the ends and stops there", () => {
    expect(adjacentStop(map, uOf("summit"), 1)?.id).toBe("end");
    expect(adjacentStop(map, map.totalUnits, 1)).toBeNull();
    expect(adjacentStop(map, uOf("gate"), -1)?.id).toBe("start");
    expect(adjacentStop(map, 0, -1)).toBeNull();
  });
});

describe("nearestHold", () => {
  it("names the hold nearest to the scroll position", () => {
    expect(nearestHold(map, 0)).toBe("gate");
    expect(nearestHold(map, uOf("scroll") + 10)).toBe("scroll");
    expect(nearestHold(map, map.totalUnits)).toBe("summit");
    expect(nearestHold(buildScrollMap(1, 10, []), 3)).toBeNull();
  });
});

describe("area -> hash", () => {
  it("names every area by its main-page section id", () => {
    for (const a of AREAS) expect(hashForArea(a.id)).toBe(`#${a.sectionId}`);
    expect(hashForArea("nowhere")).toBe("");
  });
});

describe("keys", () => {
  it("maps paging, arrows and J/K to holds, Home/End to the ends", () => {
    expect(navKeyIntent({ key: "PageDown" })).toBe("next");
    expect(navKeyIntent({ key: "ArrowDown" })).toBe("next");
    expect(navKeyIntent({ key: "j" })).toBe("next");
    expect(navKeyIntent({ key: "K" })).toBe("prev");
    expect(navKeyIntent({ key: "ArrowUp" })).toBe("prev");
    expect(navKeyIntent({ key: "Home" })).toBe("first");
    expect(navKeyIntent({ key: "End" })).toBe("last");
  });

  it("leaves other keys and modified keys alone", () => {
    expect(navKeyIntent({ key: " " })).toBeNull();
    expect(navKeyIntent({ key: "a" })).toBeNull();
    expect(navKeyIntent({ key: "ArrowDown", ctrlKey: true })).toBeNull();
    expect(navKeyIntent({ key: "j", metaKey: true })).toBeNull();
  });

  it("left and right turn the view (left positive), and do not fly", () => {
    expect(turnKeyIntent({ key: "ArrowLeft" })).toBe(1);
    expect(turnKeyIntent({ key: "ArrowRight" })).toBe(-1);
    expect(navKeyIntent({ key: "ArrowLeft" })).toBeNull();
    expect(navKeyIntent({ key: "ArrowRight" })).toBeNull();
    // Up and down keep flying between stops and never turn.
    expect(turnKeyIntent({ key: "ArrowUp" })).toBeNull();
    expect(turnKeyIntent({ key: "ArrowDown" })).toBeNull();
    // Browser shortcuts (Alt+Left is Back) are left alone.
    expect(turnKeyIntent({ key: "ArrowLeft", altKey: true })).toBeNull();
    expect(turnKeyIntent({ key: "ArrowRight", ctrlKey: true })).toBeNull();
    expect(turnKeyIntent({ key: "ArrowLeft", metaKey: true })).toBeNull();
  });

  it("turns an intent into a stop", () => {
    expect(navKeyTarget(map, uOf("arena"), "next")?.id).toBe("mission");
    expect(navKeyTarget(map, uOf("arena"), "first")).toEqual({ id: "start", u: 0 });
    expect(navKeyTarget(map, 0, "first")).toBeNull();
    // End lands on the last place (the contact panel), not the bare end of the track past it.
    expect(navKeyTarget(map, uOf("arena"), "last")).toEqual({ id: "summit", u: uOf("summit") });
    expect(navKeyTarget(map, uOf("summit"), "last")).toBeNull();
    expect(navKeyTarget(map, map.totalUnits, "last")).toEqual({ id: "summit", u: uOf("summit") });
  });
});

describe("panelSide", () => {
  // Camera at the origin looking down -z (identity quaternion), 16:9.
  const frame: CameraFrame = { f: 1, p: [0, 0, 0], q: [0, 0, 0, 1], fovY: 40 };
  it("puts the panel opposite the landmark", () => {
    expect(panelSide(frame, 16 / 9, [10, 0, -50])).toBe("left");
    expect(panelSide(frame, 16 / 9, [-10, 0, -50])).toBe("right");
  });
  it("leaves the choice to the panel for a centred, missing or hidden landmark", () => {
    expect(panelSide(frame, 16 / 9, [1, 0, -50])).toBeNull();
    expect(panelSide(frame, 16 / 9, null)).toBeNull();
    expect(panelSide(frame, 16 / 9, [-10, 0, 50])).toBeNull();
  });
});

describe("flightSeconds", () => {
  it("grows with distance and stays bounded", () => {
    expect(flightSeconds(0)).toBe(0);
    const near = flightSeconds(170);
    const far = flightSeconds(1700);
    expect(near).toBeGreaterThan(0.9);
    expect(near).toBeLessThan(far);
    expect(flightSeconds(1e6)).toBeLessThanOrEqual(2.8);
  });
});
