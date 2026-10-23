import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  BIRD_STRIDE,
  birdFlocks,
  birdPoint,
  buildLifeTables,
  butterflies,
  butterflyPoint,
  firstLiveGroup,
  flockFormation,
  flockPoint,
  GROUP_STRIDE,
  holdViews,
  isBakedMote,
  LIFE,
  lifeCounts,
  lifeHash,
  lifeTier,
  MOTE_STRIDE,
  moteField,
  motePoint,
  packBirds,
  packGroups,
  packMotes,
  twilightOf,
  windowFade,
  type HoldView,
} from "./life";
import { parseCameraData, parseMeta } from "./parse";
import type { CameraData, CameraFrame, SectMeta, Vec3, Waterfall } from "./types";

const dist = (a: Vec3, b: Vec3) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const sub = (a: Vec3, b: Vec3): Vec3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

/** A straight flight north (three -z) at 100 m, looking ahead, with three holds. */
function camera(): CameraData {
  const frames: CameraFrame[] = [];
  for (let f = 1; f <= 300; f++) frames.push({ f, p: [0, 100, -f * 2], q: [0, 0, 0, 1], fovY: 35 });
  return {
    fps: 24,
    frameStart: 1,
    frameEnd: 300,
    frames,
    holds: [
      { id: "a", label: "A", frame: 50 },
      { id: "b", label: "B", frame: 150 },
      { id: "c", label: "C", frame: 250 },
    ],
    startFrame: 1,
    refAspect: 16 / 9,
    near: 0.1,
    far: 9000,
  };
}

function waterfall(name: string, position: Vec3, size: Vec3, foot: Vec3, nearestM: number, chunk: string): Waterfall {
  return { name, kind: "sheet", position, size, rotation: [0, 0, 0, 1], nearestM, corners: null, foot, flow: 1, chunk };
}

function meta(extra: Partial<SectMeta> = {}): SectMeta {
  return {
    sun: { direction: [-0.9, 0.1, 0.3], color: "#ffbf84" },
    sky: { zenith: "#000000", horizon: "#000000", horizonSun: "#000000", belowHorizon: "#000000", texture: null, asRenderedTop: null },
    fog: { color: "#c8ada0", scatterColor: "#ffffff", density: 0.0003, baseY: 100, falloff: 220 },
    moon: null,
    cloudSea: { y: -60, billowTopY: -45, fogTopY: 20, fogBottomY: -90, color: "#e9c9a8", extent: 9000 },
    waterfalls: [],
    beams: [],
    hotspots: [],
    areas: [
      { id: "a", label: "A", anchor: [0, 85, -140], footprint: 40, frameStart: 1, frameEnd: 100, heroFrame: 50 },
      { id: "b", label: "B", anchor: [0, 85, -340], footprint: 40, frameStart: 101, frameEnd: 200, heroFrame: 150 },
      { id: "c", label: "C", anchor: [0, 85, -540], footprint: 40, frameStart: 201, frameEnd: 300, heroFrame: 250 },
    ],
    vignette: 0.2,
    exposure: 0,
    ...extra,
  };
}

describe("life basics", () => {
  it("hashes deterministically into 0..1", () => {
    for (const p of [0, 1, 2.5, -3.7, 1234.567, 97.0]) {
      const h = lifeHash(p);
      expect(h).toBeGreaterThanOrEqual(0);
      expect(h).toBeLessThan(1);
      expect(lifeHash(p)).toBe(h);
    }
    expect(lifeHash(1)).not.toBe(lifeHash(2));
  });

  it("fades a group in and out at the ends of its stretch, cross-fading neighbours", () => {
    expect(windowFade(150, 100, 200)).toBe(1);
    expect(windowFade(100 - LIFE.fadeFrames - 1, 100, 200)).toBe(0);
    expect(windowFade(200 + LIFE.fadeFrames + 1, 100, 200)).toBe(0);
    // Two neighbouring holds share the frame between them: their fades add up to one.
    for (const f of [190, 195, 200, 205, 210]) expect(windowFade(f, 100, 200) + windowFade(f, 200, 300)).toBeCloseTo(1, 6);
  });

  it("maps the quality to a tier, and the tier to fewer instances", () => {
    expect(lifeTier({ post: true, msaa: 4 })).toBe("high");
    expect(lifeTier({ post: true, msaa: 0 })).toBe("mid");
    expect(lifeTier({ post: false, msaa: 0 })).toBe("low");
    const total = { birds: 300, motes: 1500, butterflies: 16 };
    const high = lifeCounts(total, "high", false);
    const mid = lifeCounts(total, "mid", false);
    const low = lifeCounts(total, "low", false);
    expect(high).toEqual(total);
    expect(mid.birds).toBeLessThan(high.birds);
    expect(low.motes).toBeLessThan(mid.motes);
    expect(low.butterflies).toBe(0);
    // Reduced motion: no birds or butterflies; a third of the motes, standing still.
    const still = lifeCounts(total, "high", true);
    expect(still.birds).toBe(0);
    expect(still.butterflies).toBe(0);
    expect(still.motes).toBe(Math.round(1500 * LIFE.reducedMotesShare));
  });

  it("reads each hold's view and splits the flight between the holds", () => {
    const v = holdViews(camera());
    expect(v.map((h) => h.id)).toEqual(["a", "b", "c"]);
    expect(v[0].fwd[2]).toBeCloseTo(-1);
    expect(v[0].right[0]).toBeCloseTo(1);
    expect(v[0].tanY).toBeCloseTo(Math.tan((17.5 * Math.PI) / 180));
    expect(v[0].window[1]).toBe(100);
    expect(v[1].window).toEqual([100, 200]);
    // The first and last stretches reach past the path's ends (no fade at the first frame).
    expect(windowFade(1, v[0].window[0], v[0].window[1])).toBe(1);
    expect(windowFade(300, v[2].window[0], v[2].window[1])).toBe(1);
  });

  it("finds the live groups (in their stretch and in view)", () => {
    const g = packGroups([
      { window: [0, 100], center: [0, 0, 0], radius: 5 },
      { window: [100, 200], center: [50, 0, 0], radius: 5 },
    ]);
    expect(g.length).toBe(2 * GROUP_STRIDE);
    const all = () => true;
    expect(firstLiveGroup(g, 50, all)).toBe(0);
    expect(firstLiveGroup(g, 150, all)).toBe(1);
    expect(firstLiveGroup(g, 500, all)).toBe(-1);
    expect(firstLiveGroup(g, 50, (x) => x > 10)).toBe(-1);
  });
});

describe("birds", () => {
  const views = holdViews(camera());
  const minY = 20 + LIFE.birds.overCloud;
  const flocks = birdFlocks(views, { minY });

  it("are the same every visit, a few loose flocks of 6-20 per hold", () => {
    expect(flocks).toEqual(birdFlocks(views, { minY }));
    expect(flocks.length).toBe(views.length * LIFE.birds.flocksPerHold);
    for (const f of flocks) {
      if (f.kind === 0) {
        expect(f.count).toBeGreaterThanOrEqual(6);
        expect(f.count).toBeLessThanOrEqual(20);
      } else {
        expect(f.count).toBeGreaterThanOrEqual(5);
        expect(f.count).toBeLessThanOrEqual(9);
      }
      expect(flockFormation(f, 0).length).toBe(f.count);
    }
  });

  it("cross each hold's view 150-600 m out", () => {
    for (const f of flocks) {
      const v = views.find((h) => h.id === f.hold) as HoldView;
      const to = sub(f.center, v.p);
      const d = Math.hypot(...to);
      expect(d).toBeGreaterThan(150);
      expect(d).toBeLessThan(600);
      // Inside the hold's horizontal field of view where the route crosses it.
      const ahead = dot(to, v.fwdH);
      expect(ahead).toBeGreaterThan(0);
      expect(Math.abs(dot(to, v.right)) / ahead).toBeLessThan(v.tanX);
    }
  });

  it("fly smoothly, fade out before their route wraps, and stay over the cloud layer", () => {
    for (const [i, f] of flocks.entries()) {
      const slots = flockFormation(f, i);
      const lap = f.length / f.speed;
      for (let k = 0; k <= 200; k++) {
        const t = (k / 200) * lap * 2.3;
        const a = flockPoint(f, t);
        const b = flockPoint(f, t + 0.05);
        // Away from the wrap the flock moves about speed * dt; at the wrap it is invisible.
        if (Math.abs(a.u - b.u) < 0.5) expect(dist(a.p, b.p)).toBeLessThan(f.speed * 0.05 + 0.2);
        else expect(Math.min(a.fade, b.fade)).toBeLessThan(0.01);
        for (const s of slots) expect(birdPoint(f, s, t)[1]).toBeGreaterThan(20 + 15);
      }
      expect(flockPoint(f, 0).fade).toBeGreaterThanOrEqual(0);
    }
  });

  it("pack whole flocks in rank order, so a thinned table keeps a flock at every hold", () => {
    const packed = packBirds(flocks);
    expect(packed.count).toBe(flocks.reduce((n, f) => n + f.count, 0));
    expect(packed.data.length).toBe(packed.count * BIRD_STRIDE);
    expect(packed.groups.length).toBe(flocks.length * GROUP_STRIDE);
    const holdOf = (i: number) => {
      const c: Vec3 = [packed.data[i * BIRD_STRIDE], packed.data[i * BIRD_STRIDE + 1], packed.data[i * BIRD_STRIDE + 2]];
      return flocks.find((f) => dist(f.center, c) < 1e-3)?.hold;
    };
    const kept = new Set<string | undefined>();
    for (let i = 0; i < Math.round(packed.count * LIFE.tierShare.low); i++) kept.add(holdOf(i));
    for (const v of views) expect(kept.has(v.id)).toBe(true);
  });
});

describe("motes", () => {
  const views = holdViews(camera());
  const fall = waterfall("near.sheet", [40, 70, -330], [10, 60, 5], [40, 40, -330], 60, "b");
  const twin = waterfall("near.sheet.001", [41, 70, -331], [8, 60, 5], [40, 40, -330], 61, "b");
  const far = waterfall("far.sheet", [900, 70, -330], [10, 60, 5], [900, 40, -330], 800, "b");
  const sunk = waterfall("sunk.sheet", [-60, -20, -540], [10, 40, 5], [-60, -40, -540], 90, "c");
  const m = meta({
    waterfalls: [fall, twin, far, sunk],
    hotspots: [
      { id: "mirror-blossom", label: "Peach", center: [10, 90, -160], size: [16, 8, 16], area: "a", chunk: "a" },
      { id: "mirror-pond", label: "Pond", center: [-10, 85, -150], size: [30, 2, 30], area: "a", chunk: "a" },
      // A jade slip square to hold b's view (the camera looks along -z from (0, 100, -300)).
      { id: "resume", label: "Jade Slip", center: [0, 92, -340], size: [20, 6, 2], area: "b", chunk: "b" },
    ],
  });
  const field = moteField(m, views, { twilight: twilightOf(views, "b", "c") });

  it("gather in front of every hold camera, above the ground, more at twilight", () => {
    const holds = field.clusters.filter((c) => c.kind === "hold");
    expect(holds.map((c) => c.id)).toEqual(["hold:a", "hold:b", "hold:c"]);
    expect(holds[0].count).toBe(LIFE.motes.perHold);
    expect(holds[2].count).toBe(Math.round(LIFE.motes.perHold * (1 + LIFE.motes.twilightBoost)));
    const v = views[0];
    const own = field.motes.filter((x) => x.window === v.window && x.far === 260);
    expect(own.length).toBe(LIFE.motes.perHold);
    for (const x of own) {
      const ahead = dot(sub(x.home, v.p), v.fwdH);
      expect(ahead).toBeGreaterThanOrEqual(LIFE.motes.depth[0] - 1e-6);
      expect(ahead).toBeLessThanOrEqual(LIFE.motes.depth[1] + 1e-6);
      expect(x.home[1]).toBeGreaterThanOrEqual(85.6 - 1e-6);
    }
  });

  it("stay near eye level with their rise when a low camera looks up (no snow in the sky)", () => {
    // Like the summit hold: 6 m over the ground, pitched 12 degrees up.
    const a = (12 * Math.PI) / 180;
    const up = camera();
    up.frames = up.frames.map((fr) => ({ ...fr, p: [fr.p[0], 91, fr.p[2]], q: [Math.sin(a / 2), 0, 0, Math.cos(a / 2)] }));
    const vs = holdViews(up);
    expect(vs[0].fwd[1]).toBeCloseTo(Math.sin(a), 6);
    const own = moteField(meta(), vs).motes.filter((x) => x.window === vs[0].window && x.far === 260);
    expect(own.length).toBe(LIFE.motes.perHold);
    for (const x of own) {
      expect(x.home[1]).toBeGreaterThanOrEqual(85.6 - 1e-6);
      expect(x.home[1] + x.rise).toBeLessThanOrEqual(91 + LIFE.motes.overEye + 1e-6);
    }
  });

  it("rise off near waterfalls (one cluster per fall, none for far or sunken ones)", () => {
    const water = field.clusters.filter((c) => c.kind === "water");
    expect(water.map((c) => c.id)).toEqual(["water:near.sheet"]);
    const w = field.motes.filter((x) => x.far === fall.nearestM + 250);
    expect(w.length).toBe(water[0].count);
    // This fall lands on solid ground: its motes hang over the splash, not up the whole face.
    for (const x of w) {
      expect(x.home[1]).toBeGreaterThanOrEqual(40);
      expect(x.home[1]).toBeLessThanOrEqual(40 + 20 + 1e-6);
      expect(Math.hypot(x.home[0] - 40, x.home[2] + 330)).toBeLessThan(12);
    }
  });

  it("hang in the flowering tree and over the pond", () => {
    expect(field.clusters.find((c) => c.id === "blossom:mirror-blossom")?.count).toBe(LIFE.motes.perBlossom);
    expect(field.clusters.find((c) => c.id === "pond:mirror-pond")?.count).toBe(LIFE.motes.perPond);
  });

  it("rise off the jade slip: a few soft glows along its face, in front of it, gone by its top edge", () => {
    const R = LIFE.motes.relic;
    const c = field.clusters.find((x) => x.id === "relic:resume");
    expect(c?.kind).toBe("relic");
    expect(c?.count).toBe(R.count);
    expect(c?.window).toEqual(views[1].window);
    const own = field.motes.filter((x) => x.far === 240);
    expect(own.length).toBe(R.count);
    let gold = 0;
    for (const x of own) {
      expect(x.kind).toBe(1);
      expect(x.soft).toBe(1);
      expect(x.radius).toBeGreaterThanOrEqual(R.radius[0]);
      expect(x.radius).toBeLessThanOrEqual(R.radius[1]);
      // Across the face (20 m wide) and just in front of it (toward the camera at z -300).
      expect(Math.abs(x.home[0])).toBeLessThanOrEqual(10 * R.across + 1e-9);
      expect(x.home[2] + 340).toBeGreaterThanOrEqual(R.front[0] - 1 * R.across - 1e-9);
      expect(x.home[2] + 340).toBeLessThanOrEqual(R.front[1] + 1 * R.across + 1e-9);
      // Pale gold is redder than green; jade is greener than red.
      if (x.color[0] > x.color[1]) gold++;
      for (let t = 0; t < 60; t += 0.53) {
        const p = motePoint(x, t).p;
        // Never over the top edge (95), where open sky is behind it (the owner's "white dots").
        expect(p[1]).toBeLessThanOrEqual(95 + 1e-9);
        expect(p[1]).toBeGreaterThanOrEqual(89 + R.from * 6 - x.wander * 0.6 - 1e-9);
      }
    }
    // Mostly jade, some pale gold.
    expect(gold).toBeGreaterThan(0);
    expect(gold).toBeLessThan(R.count / 2);
  });

  it("know the bake's still spirit motes by their glow class", () => {
    expect(isBakedMote("baked.scroll_A0.glow.mote")).toBe(true);
    expect(isBakedMote("baked.library_A0.glow.mote")).toBe(true);
    expect(isBakedMote("baked.scroll_A0.glow.molten")).toBe(false);
    expect(isBakedMote("baked.scroll_A0.glow.other")).toBe(false);
    expect(isBakedMote("sect.life.motes")).toBe(false);
  });

  it("wander, blink and rise within their bounds", () => {
    for (const x of field.motes.slice(0, 200)) {
      for (const t of [0, 1.3, 7.9, 55.5, 400]) {
        const { p, glow } = motePoint(x, t);
        expect(glow).toBeGreaterThanOrEqual(0);
        expect(glow).toBeLessThanOrEqual(1);
        if (x.kind === 0) expect(glow).toBeGreaterThanOrEqual(0.25);
        expect(Math.abs(p[0] - x.home[0])).toBeLessThanOrEqual(x.wander + 1e-9);
        expect(p[1] - x.home[1]).toBeLessThanOrEqual(x.rise + x.wander * 0.6 + 1e-9);
        expect(p[1] - x.home[1]).toBeGreaterThanOrEqual(-x.wander * 0.6 - 1e-9);
      }
    }
  });

  it("pack evenly thinned (rank order) and stay inside their cluster bounds", () => {
    const packed = packMotes(field);
    expect(packed.count).toBe(field.motes.length);
    expect(packed.data.length).toBe(packed.count * MOTE_STRIDE);
    // The first third covers every cluster.
    const firstThird = new Set<number>();
    for (let i = 0; i < Math.round(packed.count / 3); i++) firstThird.add(packed.data[i * MOTE_STRIDE + 14]);
    expect(firstThird.has(260)).toBe(true);
    expect(firstThird.has(fall.nearestM + 250)).toBe(true);
    // Only the relic's qi is drawn soft (the last float of each mote).
    for (let i = 0; i < packed.count; i++) expect(packed.data[i * MOTE_STRIDE + 15]).toBe(packed.data[i * MOTE_STRIDE + 14] === 240 ? 1 : 0);
    // Every mote stays inside its cluster's bounds as it moves (the per-frame view test culls by them).
    let o = 0;
    for (const c of field.clusters) {
      for (const x of field.motes.slice(o, o + c.count)) {
        for (let t = 0; t < 120; t += 0.37) expect(dist(motePoint(x, t).p, c.center)).toBeLessThanOrEqual(c.radius);
      }
      o += c.count;
    }
  });
});

describe("butterflies", () => {
  const views = holdViews(camera());
  const m = meta({
    hotspots: [{ id: "fact:1", label: "Peach", center: [10, 90, -360], size: [16, 8, 16], area: "b", chunk: "b" }],
  });

  it("loop through the flowering tree's crown", () => {
    const { list, groups } = butterflies(m, views);
    expect(list.length).toBe(LIFE.butterflies.perTree);
    expect(groups.length).toBe(1);
    for (const b of list) {
      expect(b.window).toEqual(views[1].window);
      for (const t of [0, 3, 17, 90]) {
        const p = butterflyPoint(b, t);
        expect(dist(p, [10, 90, -360])).toBeLessThan(groups[0].radius);
      }
    }
  });
});

// ---------------------------------------------------------------------------------------------

const full = join(process.cwd(), "public/sect/full");
const haveFull = existsSync(join(full, "camera.json")) && existsSync(join(full, "meta.json"));

describe.skipIf(!haveFull)("life over the real flight", () => {
  const cam = haveFull ? parseCameraData(JSON.parse(readFileSync(join(full, "camera.json"), "utf8"))) : null;
  const mt = haveFull ? parseMeta(JSON.parse(readFileSync(join(full, "meta.json"), "utf8"))) : null;

  it("puts flocks at every hold and motes by the abode's waterfall, more toward the summit", () => {
    if (!cam || !mt) return;
    const tables = buildLifeTables(mt, cam, { from: "scroll", to: "summit" });
    const views = holdViews(cam);
    const flocks = birdFlocks(views, { minY: mt.cloudSea.fogTopY + LIFE.birds.overCloud });
    for (const v of views) expect(flocks.some((f) => f.hold === v.id)).toBe(true);
    // Budgets: a few hundred birds, one to two thousand motes, a handful of butterflies.
    expect(tables.totals.birds).toBeGreaterThan(150);
    expect(tables.totals.birds).toBeLessThan(700);
    expect(tables.totals.motes).toBeGreaterThan(900);
    expect(tables.totals.motes).toBeLessThan(2500);
    expect(tables.totals.butterflies).toBe(LIFE.butterflies.perTree * 2);
    const field = moteField(mt, views, { twilight: twilightOf(views, "scroll", "summit") });
    expect(field.clusters.some((c) => c.id === "water:abode.waterfall.sheet")).toBe(true);
    const count = (id: string) => field.clusters.find((c) => c.id === `hold:${id}`)?.count ?? 0;
    expect(count("summit")).toBeGreaterThan(count("gate"));
    expect(count("abode")).toBeGreaterThan(count("gate"));
    // The jade slip's qi stays on the slip: within its box (and a little in front), never over its top edge.
    const slip = mt.hotspots.find((h) => h.id === "resume");
    const relic = field.clusters.find((c) => c.id === "relic:resume");
    expect(slip && relic).toBeTruthy();
    if (!slip || !relic) return;
    const own = field.motes.filter((x) => x.far === 240);
    expect(own.length).toBe(LIFE.motes.relic.count);
    for (const x of own) {
      expect(Math.abs(x.home[0] - slip.center[0])).toBeLessThanOrEqual(slip.size[0] / 2 + LIFE.motes.relic.front[1]);
      expect(Math.abs(x.home[2] - slip.center[2])).toBeLessThanOrEqual(slip.size[2] / 2 + LIFE.motes.relic.front[1]);
      for (let t = 0; t < 30; t += 0.7) expect(motePoint(x, t).p[1]).toBeLessThanOrEqual(slip.center[1] + slip.size[1] / 2 + 1e-6);
    }
  });
});
