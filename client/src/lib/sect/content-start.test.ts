import { describe, expect, it } from "vitest";
import { flightHref, pageViewHref, POSTER_ATTR, POSTER_SCRIPT, posterStart, skippedNote, startView, startYaw, type NetworkHint } from "./content-start";
import { POSTER } from "./opening";

/** Runs POSTER_SCRIPT against a fake page; true when it set the attribute. */
function runPosterScript(search: string, hash: string, net?: NetworkHint): boolean {
  const attrs = new Map<string, string>();
  const links: Record<string, string>[] = [];
  const document = {
    documentElement: { setAttribute: (k: string, v: string) => attrs.set(k, v) },
    createElement: () => {
      const l: Record<string, string> = {};
      return Object.assign(l, { setAttribute: (k: string, v: string) => (l[k] = v) });
    },
    head: { appendChild: (l: Record<string, string>) => links.push(l) },
  };
  Function("location", "navigator", "document", POSTER_SCRIPT)({ search, hash }, { connection: net }, document);
  // It preloads both stills, each for its own orientation (the browser fetches the matching one).
  expect(links.map((l) => [l.rel, l.as, l.href, l.media])).toEqual(
    attrs.has(POSTER_ATTR)
      ? [
          ["preload", "image", POSTER.landscape, "(orientation: landscape)"],
          ["preload", "image", POSTER.portrait, "(orientation: portrait)"],
        ]
      : [],
  );
  return attrs.has(POSTER_ATTR);
}

describe("posterStart", () => {
  const cases: [string, string, NetworkHint | undefined, boolean][] = [
    ["", "", undefined, true],
    ["?view=flight", "", undefined, true],
    ["?tier=low", "", undefined, true],
    ["?ui=0&debug=1", "", undefined, true],
    ["?set=full", "", undefined, true],
    // Somewhere else on the path: the still would not match.
    ["", "#projects", undefined, false],
    ["?open=project:dispatchai", "", undefined, false],
    ["?frame=93", "", undefined, false],
    ["?yaw=90", "", undefined, false],
    ["?set=proto", "", undefined, false],
    // The page view: no flight at all.
    ["?view=page", "", undefined, false],
    ["", "", { saveData: true }, false],
    ["", "", { effectiveType: "2g" }, false],
    ["?view=flight", "", { saveData: true }, true],
    ["?tier=high", "", { saveData: true }, true],
    ["", "", { effectiveType: "4g" }, true],
  ];

  it("is the top of the path with the full set", () => {
    for (const [search, hash, net, want] of cases) expect(posterStart(search, hash, net), `${search}${hash} ${JSON.stringify(net)}`).toBe(want);
  });

  it("decides the same in the script that runs before the first paint", () => {
    for (const [search, hash, net, want] of cases) expect(runPosterScript(search, hash, net), `${search}${hash} ${JSON.stringify(net)}`).toBe(want);
  });

  it("names the attribute the loading screen's class spells out", () => {
    expect(POSTER_ATTR).toBe("data-sect-poster");
  });

  it("never throws from the script", () => {
    expect(() => Function("location", "navigator", "document", POSTER_SCRIPT)({}, {}, {})).not.toThrow();
  });
});

describe("startView", () => {
  it("flies by default", () => {
    expect(startView("")).toEqual({ view: "flight" });
    expect(startView("?open=project:dispatchai")).toEqual({ view: "flight" });
    expect(startView("", { saveData: false, effectiveType: "4g" })).toEqual({ view: "flight" });
  });

  it("opens the page view when asked", () => {
    expect(startView("?view=page")).toEqual({ view: "page", reason: "asked" });
    expect(startView("?view=PAGE&open=resume")).toEqual({ view: "page", reason: "asked" });
  });

  it("skips the 3D download when the browser asks to save data or the connection is very slow", () => {
    expect(startView("", { saveData: true })).toEqual({ view: "page", reason: "save-data" });
    expect(startView("", { effectiveType: "2g" })).toEqual({ view: "page", reason: "slow-network" });
    expect(startView("", { effectiveType: "slow-2g" })).toEqual({ view: "page", reason: "slow-network" });
    // "3g" is reported for many ordinary connections: not enough to skip the flight.
    expect(startView("", { effectiveType: "3g" })).toEqual({ view: "flight" });
  });

  it("always flies with ?view=flight or the flight's own test options", () => {
    expect(startView("?view=flight", { saveData: true })).toEqual({ view: "flight" });
    expect(startView("?view=3d", { effectiveType: "2g" })).toEqual({ view: "flight" });
    for (const q of ["?frame=93", "?debug=1", "?tier=low", "?set=proto", "?ui=0", "?flyer=1", "?yaw=180"]) {
      expect(startView(q, { saveData: true }), q).toEqual({ view: "flight" });
    }
  });
});

describe("view links", () => {
  it("keep the deep link while switching view", () => {
    expect(pageViewHref()).toBe("/?view=page");
    expect(pageViewHref("?open=project:dispatchai", "#projects")).toBe("/?open=project%3Adispatchai&view=page#projects");
    expect(flightHref("?view=page", "#footer")).toBe("/?view=flight#footer");
  });
});

describe("startYaw", () => {
  const DEG = Math.PI / 180;
  it("reads ?yaw in degrees as a wrapped yaw in radians", () => {
    expect(startYaw("?frame=974&yaw=90")).toBeCloseTo(90 * DEG, 9);
    expect(startYaw("?yaw=180")).toBeCloseTo(Math.PI, 9);
    expect(startYaw("?yaw=270")).toBeCloseTo(-90 * DEG, 9);
    expect(startYaw("?yaw=-45")).toBeCloseTo(-45 * DEG, 9);
    expect(startYaw("?yaw=0")).toBe(0);
  });

  it("is null when absent or not a number", () => {
    expect(startYaw("")).toBeNull();
    expect(startYaw("?frame=93")).toBeNull();
    expect(startYaw("?yaw=")).toBeNull();
    expect(startYaw("?yaw=back")).toBeNull();
  });
});

describe("skippedNote", () => {
  it("says why the flight was skipped, with its size when known", () => {
    expect(skippedNote("asked", 22)).toBe("");
    expect(skippedNote("save-data", 19)).toBe("Your browser asked to save data, so the 3D flight (about 19 MB) was skipped.");
    expect(skippedNote("slow-network", 22)).toBe("Your connection looks slow, so the 3D flight (about 22 MB) was skipped.");
    expect(skippedNote("slow-network", null)).toBe("Your connection looks slow, so the 3D flight was skipped.");
  });
});
