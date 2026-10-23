import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { AREA_IDS } from "./areas";
import {
  clearOf,
  hereMark,
  linePath,
  mapFit,
  mapKeyStep,
  mapStops,
  parseSectMap,
  pickMapImage,
  platePosition,
  routeClimbsUp,
  routeLine,
  routeOrder,
  simplifyLine,
  spreadMarkers,
  walkLine,
  worldToUv,
  type UvTransform,
} from "./map";
import { parseCameraData, parseMeta } from "./parse";
import type { CameraFrame, Quat } from "./types";

const PUBLIC = path.resolve(__dirname, "../../../public/sect");
const readJson = (p: string) => JSON.parse(readFileSync(path.join(PUBLIC, p), "utf8")) as unknown;
const meta = parseMeta(readJson("full/meta.json"));
const camera = parseCameraData(readJson("full/camera.json"));

/** Top-down, x right, -z up, 1000 m square from (-500, -1000) to (500, 0). */
const XF: UvTransform = [
  [0.001, 0, 0.5],
  [0, 0.001, 1],
];

const file = (extra: Record<string, unknown> = {}) => ({
  version: 1,
  images: { full: { src: "map.webp", w: 2048, h: 4096 }, small: { src: "map_small.webp", w: 1024, h: 2048 } },
  world_to_uv: [
    [0.001, 0, 0.5],
    [0, 0.001, 1],
  ],
  ...extra,
});

describe("parseSectMap", () => {
  it("reads the pictures smallest first, each with the file's transform", () => {
    const m = parseSectMap(file());
    expect(m.images.map((i) => i.key)).toEqual(["small", "full"]);
    expect(m.images[1]).toMatchObject({ src: "map.webp", w: 2048, h: 4096 });
    expect(m.images[0].xf).toEqual(XF);
    expect(m.placeholder).toBe(false);
    expect(m.route).toBeNull();
  });

  it("reads the painted walkways as world [x, z] points, and leaves out a broken route", () => {
    expect(parseSectMap(file({ route: [[0, 0], [10, -20]] })).route).toEqual([
      [0, 0],
      [10, -20],
    ]);
    expect(parseSectMap(file({ route: [[0, 0]] })).route).toBeNull();
    expect(parseSectMap(file({ route: [[0, 0], [1, "x"]] })).route).toBeNull();
    expect(parseSectMap(file({ route: [[0, 0], [1, Infinity]] })).route).toBeNull();
    expect(parseSectMap(file({ route: "nope" })).route).toBeNull();
  });

  it("keeps a picture's own transform (a crop)", () => {
    const own = [
      [0.002, 0, 0.25],
      [0, 0.002, 1.5],
    ];
    const m = parseSectMap(file({ images: { crop: { src: "crop.webp", w: 900, h: 1600, world_to_uv: own } } }));
    expect(m.images[0].xf).toEqual(own);
  });

  it("refuses files the page cannot use, with a readable reason", () => {
    expect(() => parseSectMap(null)).toThrow(/JSON object/);
    expect(() => parseSectMap(file({ images: {} }))).toThrow(/at least one picture/);
    expect(() => parseSectMap(file({ world_to_uv: [[1, 0]] }))).toThrow(/world_to_uv/);
    expect(() => parseSectMap(file({ world_to_uv: [[1, 0, 0], [2, 0, 0]] }))).toThrow(/degenerate/);
    expect(() => parseSectMap(file({ world_to_uv: undefined }))).toThrow(/no world_to_uv/);
    expect(() => parseSectMap(file({ version: 2 }))).toThrow(/version 2/);
  });

  it("leaves out pictures with no size or a path that leaves the site", () => {
    const m = parseSectMap(
      file({
        images: {
          ok: { src: "ok.webp", w: 10, h: 20 },
          nosize: { src: "a.webp", w: 0, h: 20 },
          script: { src: "javascript:alert(1)", w: 10, h: 20 },
          offsite: { src: "//evil.example/a.webp", w: 10, h: 20 },
          quote: { src: 'a.webp" onerror="x', w: 10, h: 20 },
        },
      }),
    );
    expect(m.images.map((i) => i.key)).toEqual(["ok"]);
  });
});

describe("placing points", () => {
  it("maps world x and z to the picture and ignores height", () => {
    expect(worldToUv(XF, [0, 999, 0])).toEqual([0.5, 1]);
    expect(worldToUv(XF, [-500, 0, -1000])).toEqual([0, 0]);
    expect(worldToUv(XF, [250, 0, -500])).toEqual([0.75, 0.5]);
  });

  it("fits a picture inside a box, centred", () => {
    expect(mapFit({ w: 1000, h: 800 }, { w: 1000, h: 2000 }, 0)).toEqual({ x: 300, y: 0, w: 400, h: 800 });
    expect(mapFit({ w: 400, h: 800 }, { w: 2000, h: 1000 }, 10)).toEqual({ x: 10, y: 305, w: 380, h: 190 });
    expect(mapFit({ w: 0, h: 800 }, { w: 2, h: 1 }).w).toBe(0);
  });

  it("picks the smallest picture that is sharp enough, else the largest", () => {
    const m = parseSectMap(file());
    // A 300 x 600 box: 1024 px wide is enough at 1x and 3x (900 px).
    expect(pickMapImage(m, 300, 600, 1).key).toBe("small");
    expect(pickMapImage(m, 300, 600, 3).key).toBe("small");
    // A phone's 350 x 525 map at 3x wants 1050 px: the 1024 px picture is 2.5% short, close enough.
    expect(pickMapImage(m, 350, 525, 3).key).toBe("small");
    expect(pickMapImage(m, 600, 1200, 2).key).toBe("full");
    expect(pickMapImage(m, 4000, 8000, 2).key).toBe("full");
  });
});

describe("mapStops", () => {
  it("places the eleven stops in flight order at their anchors", () => {
    const stops = mapStops(meta, camera, XF);
    expect(stops.map((s) => s.id)).toEqual([...AREA_IDS]);
    for (const s of stops) expect(s.from).toBe("anchor");
    const gate = meta.areas.find((a) => a.id === "gate")!.anchor;
    expect(stops[0].uv).toEqual(worldToUv(XF, gate));
  });

  it("falls back to the camera at the hold for an area with no anchor", () => {
    const stops = mapStops({ areas: meta.areas.filter((a) => a.id !== "forge"), hotspots: meta.hotspots.filter((h) => h.id !== "forge") }, camera, XF);
    const forge = stops.find((s) => s.id === "forge")!;
    expect(forge.from).toBe("hold");
    const hold = camera.frames.find((f) => f.f === camera.holds.find((h) => h.id === "forge")!.frame)!;
    expect(forge.uv[0]).toBeCloseTo(worldToUv(XF, hold.p)[0], 6);
  });

  it("leaves out holds that are not areas", () => {
    const holds = [{ id: "nowhere", label: "x", frame: 10 }, ...camera.holds];
    expect(mapStops(meta, { frames: camera.frames, holds }, XF)).toHaveLength(11);
    expect(routeOrder(["summit", "gate", "nope", "forge"])).toEqual(["gate", "forge", "summit"]);
  });

  it("puts every stop and the whole route on the shipped map", () => {
    const m = parseSectMap(readJson("map/map.json"));
    for (const im of m.images) {
      for (const s of mapStops(meta, camera, im.xf)) {
        expect(s.uv[0], `${im.key} ${s.id}`).toBeGreaterThan(0.02);
        expect(s.uv[0], `${im.key} ${s.id}`).toBeLessThan(0.98);
        expect(s.uv[1], `${im.key} ${s.id}`).toBeGreaterThan(0.02);
        expect(s.uv[1], `${im.key} ${s.id}`).toBeLessThan(0.98);
      }
      for (const [u, v] of [...routeLine(camera, im.xf, im.w, im.h), ...walkLine(m.route ?? [], im.xf, im.w, im.h)]) {
        expect(u).toBeGreaterThanOrEqual(0);
        expect(u).toBeLessThanOrEqual(1);
        expect(v).toBeGreaterThanOrEqual(0);
        expect(v).toBeLessThanOrEqual(1);
      }
    }
  });

  it("walks the shipped map's route from the gate's stair foot through every stop, in order, to the summit", () => {
    const route = parseSectMap(readJson("map/map.json")).route;
    expect(route).not.toBeNull();
    const at = (id: string) => meta.areas.find((a) => a.id === id)!.anchor;
    let from = 0;
    for (const id of AREA_IDS) {
      const [x, , z] = at(id);
      const i = route!.findIndex((p, k) => k >= from && Math.hypot(p[0] - x, p[1] - z) < 0.5);
      expect(i, id).toBeGreaterThanOrEqual(from);
      from = i;
    }
    expect(from).toBe(route!.length - 1);
    // It starts south of the gate (the stairway climbing to it) and never strays far from the
    // stops' line: no step longer than the widest gap between two stops.
    expect(route![0][1]).toBeGreaterThan(at("gate")[2] + 50);
    for (let i = 1; i < route!.length; i++) expect(Math.hypot(route![i][0] - route![i - 1][0], route![i][1] - route![i - 1][1])).toBeLessThan(200);
  });
});

describe("spreadMarkers", () => {
  const box = { w: 400, h: 800 };
  const dist = (a: readonly number[], b: readonly number[]) => Math.hypot(a[0] - b[0], a[1] - b[1]);

  it("leaves seals that are apart where they are", () => {
    const pts: [number, number][] = [
      [100, 100],
      [200, 300],
      [300, 600],
    ];
    expect(spreadMarkers(pts, 40, box)).toEqual(pts);
  });

  it("pushes close seals apart evenly, and coincident ones too", () => {
    const out = spreadMarkers(
      [
        [200, 400],
        [210, 400],
        [205, 405],
        [100, 100],
        [100, 100],
      ],
      40,
      box,
    );
    for (let i = 0; i < out.length; i++) for (let j = i + 1; j < out.length; j++) expect(dist(out[i], out[j])).toBeGreaterThanOrEqual(39.9);
    // Each moved no further than it had to (well under a seal's width or two).
    expect(dist(out[0], [200, 400])).toBeLessThan(40);
  });

  it("keeps seals inside the box and clear of pinned points, deterministically", () => {
    const pts: [number, number][] = [
      [2, 2],
      [5, 4],
      [398, 798],
    ];
    const a = spreadMarkers(pts, 40, box, [[390, 790]], 18);
    expect(a).toEqual(spreadMarkers(pts, 40, box, [[390, 790]], 18));
    for (const [x, y] of a) {
      expect(x).toBeGreaterThanOrEqual(18);
      expect(x).toBeLessThanOrEqual(382);
      expect(y).toBeGreaterThanOrEqual(18);
      expect(y).toBeLessThanOrEqual(782);
    }
    expect(dist(a[2], [390, 790])).toBeGreaterThanOrEqual(27.9);
  });
});

describe("the route", () => {
  it("simplifies a line to the points it needs", () => {
    const line: [number, number][] = Array.from({ length: 50 }, (_, i) => [i, 0]);
    expect(simplifyLine(line, 0.5)).toEqual([
      [0, 0],
      [49, 0],
    ]);
    const corner: [number, number][] = [
      [0, 0],
      [5, 0.1],
      [10, 0],
      [10, 10],
    ];
    expect(simplifyLine(corner, 0.5)).toEqual([
      [0, 0],
      [10, 0],
      [10, 10],
    ]);
  });

  it("follows the camera from its start to the end, within the tolerance", () => {
    const w = 1000;
    const h = 2000;
    const pts = routeLine(camera, XF, w, h, 1.5);
    const first = camera.frames.find((f) => f.f === camera.startFrame)!;
    const last = camera.frames[camera.frames.length - 1];
    expect(pts[0]).toEqual(worldToUv(XF, first.p));
    expect(pts[pts.length - 1]).toEqual(worldToUv(XF, last.p));
    // Far fewer points than frames, but every frame still within 1.5 px of the line.
    expect(pts.length).toBeLessThan(camera.frames.length / 4);
    const segDist = (p: number[], a: readonly number[], b: readonly number[]) => {
      const dx = b[0] - a[0];
      const dy = b[1] - a[1];
      const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy || 1)));
      return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy);
    };
    const px = pts.map(([u, v]) => [u * w, v * h] as const);
    for (const f of camera.frames.filter((x) => x.f >= camera.startFrame)) {
      const [u, v] = worldToUv(XF, f.p);
      const p = [u * w, v * h];
      let best = Infinity;
      for (let i = 1; i < px.length; i++) best = Math.min(best, segDist(p, px[i - 1], px[i]));
      expect(best).toBeLessThanOrEqual(1.51);
    }
  });

  it("draws the painted walkways on the picture, simplified", () => {
    const pts = walkLine(
      [
        [0, 0],
        [100, -100],
        [200, -200],
        [200, -500],
      ],
      XF,
      1000,
      1000,
      1,
    );
    expect(pts.map(([u, v]) => [+u.toFixed(6), +v.toFixed(6)])).toEqual([
      [0.5, 1],
      [0.7, 0.8],
      [0.7, 0.5],
    ]);
  });

  it("draws an SVG path on the picture's pixels", () => {
    expect(
      linePath(
        [
          [0, 0],
          [0.5, 0.25],
        ],
        200,
        400,
      ),
    ).toBe("M0.0 0.0L100.0 100.0");
  });
});

describe("clearOf", () => {
  it("leaves a point that is clear of every disc where it is", () => {
    expect(clearOf([0, 0], [{ x: 100, y: 0, r: 10 }])).toEqual([0, 0]);
  });

  it("moves a point inside a disc straight out to just past its rim", () => {
    const [x, y] = clearOf([105, 0], [{ x: 100, y: 0, r: 20 }]);
    expect(x).toBeCloseTo(120, 1);
    expect(y).toBeCloseTo(0, 6);
  });

  it("moves a point on a disc's centre up, and clears discs that touch", () => {
    expect(clearOf([100, 50], [{ x: 100, y: 50, r: 20 }]).map((n) => +n.toFixed(1))).toEqual([100, 30]);
    const discs = [
      { x: 0, y: 0, r: 10 },
      { x: 18, y: 0, r: 10 },
    ];
    const q = clearOf([9, 1], discs);
    for (const d of discs) expect(Math.hypot(q[0] - d.x, q[1] - d.y)).toBeGreaterThanOrEqual(d.r - 1e-6);
  });
});

describe("hereMark", () => {
  const still = (q: Quat): CameraFrame[] => [
    { f: 1, p: [0, 10, -500], q, fovY: 40 },
    { f: 2, p: [0, 10, -500], q, fovY: 40 },
  ];
  const s = Math.SQRT1_2;

  it("puts the mark at the camera and points it the way the camera looks", () => {
    // Looking down -z (up the map): 0 degrees. Turned to look at +x (right): 90.
    const ahead = hereMark({ frames: still([0, 0, 0, 1]) }, 1, XF, 1000, 1000)!;
    expect(ahead.uv).toEqual([0.5, 0.5]);
    expect(ahead.heading).toBeCloseTo(0, 6);
    const right = hereMark({ frames: still([0, -s, 0, s]) }, 1, XF, 1000, 1000)!;
    expect(right.heading).toBeCloseTo(90, 6);
  });

  it("has no heading when the camera looks straight down", () => {
    expect(hereMark({ frames: still([-s, 0, 0, s]) }, 1, XF, 1000, 1000)!.heading).toBeNull();
    expect(hereMark({ frames: [] }, 1, XF, 1000, 1000)).toBeNull();
  });
});

describe("keys on the map", () => {
  it("moves along the route, stopping at the ends", () => {
    expect(mapKeyStep("ArrowUp", 3, 11)).toBe(4);
    expect(mapKeyStep("ArrowRight", 3, 11)).toBe(4);
    expect(mapKeyStep("ArrowDown", 3, 11)).toBe(2);
    expect(mapKeyStep("ArrowLeft", 0, 11)).toBe(0);
    expect(mapKeyStep("ArrowUp", 10, 11)).toBe(10);
    expect(mapKeyStep("Home", 5, 11)).toBe(0);
    expect(mapKeyStep("End", 5, 11)).toBe(10);
    expect(mapKeyStep("Enter", 5, 11)).toBeNull();
  });

  it("turns Up and Down round when the route runs down the picture", () => {
    expect(mapKeyStep("ArrowUp", 3, 11, false)).toBe(2);
    expect(mapKeyStep("ArrowDown", 3, 11, false)).toBe(4);
    expect(routeClimbsUp(mapStops(meta, camera, XF))).toBe(true);
    expect(
      routeClimbsUp([
        { uv: [0.5, 0.1] },
        { uv: [0.5, 0.9] },
      ]),
    ).toBe(false);
  });
});

describe("platePosition", () => {
  const view = { w: 1000, h: 800 };
  const plate = { w: 200, h: 60 };

  it("sets the plate beside the seal, right first", () => {
    expect(platePosition([500, 400], 20, plate, view)).toEqual({ side: "right", left: 528, top: 370 });
    expect(platePosition([900, 400], 20, plate, view)).toEqual({ side: "left", left: 672, top: 370 });
  });

  it("goes round the other seals when it can", () => {
    const below = [{ x: 600, y: 410, r: 20 }];
    expect(platePosition([500, 400], 20, plate, view, below).side).toBe("left");
  });

  it("goes above, or below near the top, when the sides do not fit (a phone)", () => {
    const phone = { w: 390, h: 800 };
    expect(platePosition([195, 400], 20, plate, phone)).toEqual({ side: "above", left: 95, top: 312 });
    expect(platePosition([195, 50], 20, plate, phone)).toEqual({ side: "below", left: 95, top: 78 });
    expect(platePosition([20, 400], 20, plate, phone).left).toBe(48);
  });

  it("stays inside a view too small for any side", () => {
    const tiny = platePosition([100, 30], 20, plate, { w: 150, h: 90 });
    expect(tiny.left).toBe(8);
    expect(tiny.top).toBeGreaterThanOrEqual(8);
  });
});
