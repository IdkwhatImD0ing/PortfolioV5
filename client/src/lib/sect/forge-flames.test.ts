import { describe, expect, it } from "vitest";
import {
  CARD_STRIDE,
  classifyGlow,
  EMBER_STRIDE,
  emberSeeds,
  fireBounds,
  fireFlicker,
  FLAME_GLSL,
  flameCards,
  FLAMES,
  flameTier,
  FLICKER_GLSL,
  fireSourcesFromAnchors,
  fireSourcesFromGlow,
  glowFactor,
  glowShape,
  meshPieces,
  MOUTH_STRIDE,
  openingQuads,
  type BedFire,
  type FireSource,
  type OpeningFire,
} from "./forge-flames";
import { parseFires } from "./parse";
import type { FireAnchor, Vec3 } from "./types";

/** A flat-shaded box (24 vertices, each face its own four corners, indexed), turned `yaw` about the vertical. */
function box(center: Vec3, size: Vec3, yaw = 0): { positions: number[]; index: number[] } {
  const [cx, cy, cz] = center;
  const [sx, sy, sz] = size.map((v) => v / 2);
  const c = Math.cos(yaw);
  const s = Math.sin(yaw);
  const corner = (x: number, y: number, z: number): Vec3 => [cx + x * c - z * s, cy + y, cz + x * s + z * c];
  const faces: Vec3[][] = [
    [corner(-sx, -sy, sz), corner(sx, -sy, sz), corner(sx, sy, sz), corner(-sx, sy, sz)],
    [corner(sx, -sy, -sz), corner(-sx, -sy, -sz), corner(-sx, sy, -sz), corner(sx, sy, -sz)],
    [corner(-sx, -sy, -sz), corner(-sx, -sy, sz), corner(-sx, sy, sz), corner(-sx, sy, -sz)],
    [corner(sx, -sy, sz), corner(sx, -sy, -sz), corner(sx, sy, -sz), corner(sx, sy, sz)],
    [corner(-sx, sy, sz), corner(sx, sy, sz), corner(sx, sy, -sz), corner(-sx, sy, -sz)],
    [corner(-sx, -sy, -sz), corner(sx, -sy, -sz), corner(sx, -sy, sz), corner(-sx, -sy, sz)],
  ];
  const positions: number[] = [];
  const index: number[] = [];
  faces.forEach((f, i) => {
    for (const p of f) positions.push(...p);
    index.push(i * 4, i * 4 + 1, i * 4 + 2, i * 4, i * 4 + 2, i * 4 + 3);
  });
  return { positions, index };
}

/** A flat disc of `n` rim points round a centre point (a triangle fan, unindexed). */
function disc(center: Vec3, r: number, n = 24): number[] {
  const out: number[] = [];
  for (let i = 0; i < n; i++) {
    const a0 = (i / n) * Math.PI * 2;
    const a1 = ((i + 1) / n) * Math.PI * 2;
    out.push(...center, center[0] + Math.cos(a0) * r, center[1], center[2] + Math.sin(a0) * r, center[0] + Math.cos(a1) * r, center[1], center[2] + Math.sin(a1) * r);
  }
  return out;
}

const YAW = 0.62; // about the forge's turn

/** The forge as the current bake has it: three mouth plates and two kiln boxes in one mesh, and the ding's disc. */
function forgePieces(): number[][] {
  const merged = { positions: [] as number[], index: [] as number[] };
  const add = (b: { positions: number[]; index: number[] }) => {
    const off = merged.positions.length / 3;
    merged.positions.push(...b.positions);
    merged.index.push(...b.index.map((i) => i + off));
  };
  // Mouth plates 0.12 m thick, their long side across the hall (the hall's x axis turned by the yaw).
  for (const [x, w, h] of [
    [-7.5, 1.98, 1.43],
    [0, 2.75, 1.93],
    [7.5, 1.98, 1.43],
  ]) {
    const c = Math.cos(YAW);
    const s = Math.sin(YAW);
    add(box([130 + x * c, 97 + h / 2, -350 + x * s], [w, h, 0.12], YAW));
  }
  add(box([140.9, 121.7, -365.8], [2, 1.4, 2], YAW));
  add(box([152.5, 121.7, -349.5], [2, 1.4, 2], YAW));
  return [...meshPieces(merged.positions, merged.index), ...meshPieces(disc([107.7, 102.17, -329.8], 2.83), null)];
}

describe("fireFlicker", () => {
  it("swings about 0.69-1.01 round 0.85, as fx.tsx's cauldron glow does at phase 0", () => {
    let lo = Infinity;
    let hi = -Infinity;
    let sum = 0;
    const n = 4000;
    for (let i = 0; i < n; i++) {
      const v = fireFlicker(i * 0.0173, 0);
      lo = Math.min(lo, v);
      hi = Math.max(hi, v);
      sum += v;
    }
    expect(lo).toBeGreaterThan(0.68);
    expect(hi).toBeLessThan(1.02);
    expect(sum / n).toBeCloseTo(0.85, 2);
    expect(fireFlicker(1.3, 0)).toBeCloseTo(0.85 + 0.1 * Math.sin(1.3 * 7.3) + 0.06 * Math.sin(1.3 * 13.1 + 1.7), 9);
  });

  it("is mirrored in GLSL with the same rates", () => {
    expect(FLICKER_GLSL).toContain("t * 7.3 + phase");
    expect(FLICKER_GLSL).toContain("t * 13.1 + 1.7 + phase * 2.3");
    expect(FLAME_GLSL).toContain("sectFireFlicker");
    expect(FLAME_GLSL).toContain("float sectFlameHeat(");
    expect(FLAME_GLSL).toContain("vec3 sectFlameColor(");
  });

  it("moves the molten glow round 1 at a share of the fires' swing", () => {
    expect(glowFactor(0.85)).toBeCloseTo(1, 9);
    expect(glowFactor(1.0, 1)).toBeCloseTo(1 / 0.85, 9);
    expect(glowFactor(1.0, 0.5) - 1).toBeCloseTo((1 / 0.85 - 1) * 0.5, 9);
  });
});

describe("meshPieces", () => {
  it("joins a flat-shaded box's faces into one piece and keeps two boxes apart", () => {
    const a = box([0, 0, 0], [2.75, 1.93, 0.12]);
    const b = box([10, 0, 0], [2, 1.4, 2]);
    const positions = [...a.positions, ...b.positions];
    const index = [...a.index, ...b.index.map((i) => i + 24)];
    const pieces = meshPieces(positions, index);
    expect(pieces).toHaveLength(2);
    expect(pieces.map((p) => p.length / 3).sort()).toEqual([24, 24]);
  });

  it("reads an unindexed list three vertices to a triangle", () => {
    expect(meshPieces(disc([0, 0, 0], 1, 8), null)).toHaveLength(1);
    expect(meshPieces([], null)).toEqual([]);
  });
});

describe("glowShape", () => {
  it("finds a turned plate's long and short sides", () => {
    const s = glowShape(box([5, 2, -3], [2.75, 1.93, 0.12], 0.62).positions)!;
    expect(s.extentLong).toBeCloseTo(2.75, 1);
    expect(s.extentShort).toBeCloseTo(0.12, 1);
    expect(s.extentY).toBeCloseTo(1.93, 6);
    expect(s.center[0]).toBeCloseTo(5, 2);
    expect(s.center[2]).toBeCloseTo(-3, 2);
    // The short axis is the plate's facing (the box's local z turned by the yaw).
    expect(Math.abs(s.short[0] * -Math.sin(0.62) + s.short[2] * Math.cos(0.62))).toBeCloseTo(1, 2);
  });

  it("fits a turned square box by its sides, not its diagonal", () => {
    const s = glowShape(box([0, 0, 0], [2, 1.4, 2], 0.5).positions)!;
    expect(s.extentLong).toBeCloseTo(2, 1);
    expect(s.extentShort).toBeCloseTo(2, 1);
  });

  it("is null without points", () => {
    expect(glowShape([])).toBeNull();
  });
});

describe("classifyGlow", () => {
  it("reads a thin upright plate as an opening facing the area's centre", () => {
    const s = glowShape(box([0, 1, 0], [2.75, 1.93, 0.12]).positions)!;
    const front = classifyGlow(s, "a", [0, 0, 10]) as OpeningFire;
    expect(front.kind).toBe("opening");
    expect(front.normal[2]).toBeCloseTo(1, 6);
    expect(front.base[1]).toBeCloseTo(1 - 1.93 / 2, 6);
    expect(front.base[2]).toBeCloseTo(0.06, 2);
    expect(front.width).toBeCloseTo(2.75, 1);
    expect(front.height).toBeCloseTo(1.93, 6);
    expect(front.depth).toBeGreaterThanOrEqual(FLAMES.boxDepth.min);
    // up x normal: the right-hand side seen from outside.
    expect(front.right[0]).toBeCloseTo(1, 6);
    expect(front.right[2]).toBeCloseTo(0, 6);
    const back = classifyGlow(s, "b", [0, 0, -10]) as OpeningFire;
    expect(back.normal[2]).toBeCloseTo(-1, 6);
  });

  it("reads a flat disc as a cauldron's surface and a block as a kiln's fire box", () => {
    const pool = classifyGlow(glowShape(disc([1, 5, 2], 2.8))!, "p", null) as BedFire;
    expect(pool).toMatchObject({ kind: "bed", style: "cauldron", pull: 0 });
    expect(pool.radius).toBeCloseTo(2.8, 1);
    expect(pool.base).toEqual([expect.closeTo(1, 1), 5, expect.closeTo(2, 1)]);
    expect(pool.height).toBeGreaterThan(pool.radius);
    const kiln = classifyGlow(glowShape(box([0, 10.7, 0], [2, 1.4, 2], 0.3).positions)!, "k", null) as BedFire;
    expect(kiln).toMatchObject({ kind: "bed", style: "kiln" });
    expect(kiln.radius).toBeCloseTo(1, 1);
    // In front of the box from any side (its half-diagonal), and up to a little above it.
    expect(kiln.pull).toBeGreaterThan(Math.SQRT2);
    expect(kiln.base[1] + kiln.height).toBeGreaterThan(10.7 + 0.7);
  });

  it("skips specks", () => {
    expect(classifyGlow(glowShape(box([0, 0, 0], [0.2, 0.1, 0.05]).positions)!, "x", null)).toBeNull();
  });
});

describe("fireSourcesFromGlow", () => {
  it("finds the forge's cauldron, three furnace mouths facing the courtyard and two kilns", () => {
    const fires = fireSourcesFromGlow(forgePieces(), [115, 95, -335], "forge");
    const kinds = fires.map((f) => (f.kind === "opening" ? "opening" : f.style));
    expect(kinds.filter((k) => k === "opening")).toHaveLength(3);
    expect(kinds.filter((k) => k === "kiln")).toHaveLength(2);
    expect(kinds.filter((k) => k === "cauldron")).toHaveLength(1);
    for (const f of fires) {
      if (f.kind !== "opening") continue;
      // Toward the anchor (the area's centre), not into the furnace.
      const to = [115 - f.base[0], 0, -335 - f.base[2]];
      expect(to[0] * f.normal[0] + to[2] * f.normal[2]).toBeGreaterThan(0);
    }
    // Sorted by x: stable ids across loads.
    const xs = fires.map((f) => f.base[0]);
    expect([...xs].sort((a, b) => a - b)).toEqual(xs);
    expect(new Set(fires.map((f) => f.id)).size).toBe(fires.length);
  });

  it("keeps at most FLAMES.maxSources", () => {
    const pieces: number[][] = [];
    for (let i = 0; i < 12; i++) pieces.push(...meshPieces(box([i * 10, 0, 0], [2, 1.4, 2]).positions, box([0, 0, 0], [1, 1, 1]).index));
    expect(fireSourcesFromGlow(pieces, null)).toHaveLength(FLAMES.maxSources);
  });
});

describe("fireSourcesFromAnchors", () => {
  const anchors: FireAnchor[] = [
    { id: "f0", kind: "furnace", area: "forge", chunk: "forge", position: [1, 2, 3], normal: [0, 0.2, -2], width: 2, height: 1.5, depth: 0, radius: 0 },
    { id: "f1", kind: "furnace", area: "forge", chunk: "forge", position: [1, 2, 3], normal: null, width: 2, height: 1.5, depth: 0, radius: 0 },
    { id: "k0", kind: "kiln", area: "forge", chunk: "forge", position: [5, 20, 5], normal: null, width: 2, height: 0, depth: 0, radius: 0 },
    { id: "c0", kind: "Cauldron", area: "forge", chunk: null, position: [0, 7, 0], normal: null, width: 0, height: 3, depth: 0, radius: 2.8 },
    { id: "x0", kind: "brazier", area: "formation", chunk: "formation", position: [0, 0, 0], normal: null, width: 0, height: 0, depth: 0, radius: 1 },
    { id: "z0", kind: "lamp", area: "forge", chunk: "forge", position: [0, 0, 0], normal: null, width: 1, height: 1, depth: 0, radius: 1 },
  ];

  it("takes the chunk's furnaces, kilns and cauldrons and fills in what a kind needs", () => {
    const fires = fireSourcesFromAnchors(anchors, "forge");
    expect(fires.map((f) => f.id)).toEqual(["f0", "k0", "c0"]);
    const mouth = fires[0] as OpeningFire;
    expect(mouth.normal).toEqual([0, 0, -1]);
    expect(mouth.right).toEqual([-1, 0, -0]);
    expect(mouth.depth).toBeGreaterThan(0);
    const kiln = fires[1] as BedFire;
    expect(kiln.radius).toBe(1);
    expect(kiln.height).toBeGreaterThan(0);
    expect(kiln.pull).toBeGreaterThan(Math.SQRT2);
    const pot = fires[2] as BedFire;
    expect(pot).toMatchObject({ style: "cauldron", radius: 2.8, height: 3, pull: 0 });
  });

  it("reads meta.fires as parse.ts parseFires does", () => {
    const parsed = parseFires([
      { id: "a", kind: "furnace", area: "forge", position: [1, 2, 3], normal: [0, 0, 1], width: 2, height: 1 },
      { kind: "kiln", position: [1, 2] },
      { kind: "", position: [1, 2, 3] },
      { kind: "cauldron", chunk: "forge", position: [0, 1, 0], radius: "x" },
      "junk",
    ]);
    expect(parsed).toHaveLength(2);
    expect(parsed[0]).toMatchObject({ id: "a", chunk: "forge", normal: [0, 0, 1], depth: 0 });
    expect(parsed[1]).toMatchObject({ id: "fire.3", kind: "cauldron", radius: 0, normal: null });
    expect(parseFires(undefined)).toEqual([]);
    // Other spellings: center, facing, type, size [w, h, d], r; kind synonyms.
    const alt = parseFires([
      { type: "mouth", area: "forge", center: [1, 2, 3], facing: [1, 0, 0], size: [2, 1.5, 1.2] },
      { type: "chimney", area: "forge", pos: [0, 30, 0], r: 1.1 },
      { type: "ding", area: "forge", center: [0, 7, 0], r: 2.5 },
    ]);
    expect(alt[0]).toMatchObject({ kind: "mouth", position: [1, 2, 3], normal: [1, 0, 0], width: 2, height: 1.5, depth: 1.2 });
    const fromAlt = fireSourcesFromAnchors(alt, "forge");
    expect(fromAlt.map((f) => (f.kind === "opening" ? "opening" : f.style))).toEqual(["opening", "kiln", "cauldron"]);
    expect((fromAlt[0] as OpeningFire).depth).toBe(1.2);
    expect(fireSourcesFromAnchors(parsed, "forge").map((f) => f.kind)).toEqual(["opening"]);
  });

  it("reads the round-29 rebuild's anchors by position, normal and sizes, its extra keys aside", () => {
    // export_web.py fire_meta over lib/forge_detail.py's anchors: a furnace's position is the plane its fire box is
    // drawn on (just inside the firebox, behind the stone mouth passage), not the flame's foot ('foot', 'size'); a
    // chimney's is the foot of the flames on its fire tray.
    const fires = fireSourcesFromAnchors(
      parseFires([
        {
          id: "forge.fire.chimney.0", kind: "chimney", area: "forge", chunk: "forge", position: [140.923, 120.8, -365.806], normal: null,
          width: 1.6, height: 1.5, depth: 1.6, radius: 0.8, foot: [140.923, 120.8, -365.806], size: [1.6, 1.5, 1.6], facing: [0, 1, 0], mouth: null, openSides: 3,
        },
        {
          id: "forge.fire.furnace.0", kind: "furnace", area: "forge", chunk: "forge", position: [134.961, 97.4, -349.258], normal: [-0.8137, 0, 0.5812],
          width: 2.24, height: 2.07, depth: 1.645, radius: 0, foot: [135.608, 97.55, -349.72], size: [1.904, 1.76, 1.32], facing: [-0.8137, 0, 0.5812],
          mouth: { center: [134.53, 98.435, -348.95], width: 2.24, height: 2.07 }, openSides: 1,
        },
      ]),
      "forge",
    );
    const [kiln, mouth] = fires as [BedFire, OpeningFire];
    expect(kiln).toMatchObject({ kind: "bed", style: "kiln", radius: 0.8, height: 1.5 });
    expect(mouth).toMatchObject({ kind: "opening", base: [134.961, 97.4, -349.258], width: 2.24, height: 2.07, depth: 1.645 });
    expect(mouth.normal[0]).toBeCloseTo(-0.8137, 3);
    // The kiln's cards stand toward the camera from the tray but stay inside the fire storey (inner half-width 1.70 m,
    // forge_detail HL - TW) whichever side the camera is on.
    const cards = flameCards(fires, flameTier("high"));
    for (let i = 0; i < cards.length; i += CARD_STRIDE) {
      if (cards[i + 6] !== 0) continue;
      const reach = Math.hypot(cards[i + 7], Math.abs(cards[i + 8]) + cards[i + 3] / 2);
      expect(reach).toBeLessThan(1.7);
    }
  });
});

describe("tiers and tables", () => {
  const fires: FireSource[] = fireSourcesFromGlow(forgePieces(), [115, 95, -335], "forge");

  it("draws less on the lower tiers", () => {
    const [hi, mid, lo] = (["high", "mid", "low"] as const).map(flameTier);
    for (const k of ["cauldronCards", "kilnCards", "sheets", "mouthEmbers", "kilnEmbers"] as const) {
      expect(hi[k]).toBeGreaterThanOrEqual(mid[k]);
      expect(mid[k]).toBeGreaterThanOrEqual(lo[k]);
    }
    expect(lo.cauldronCards).toBeLessThan(hi.cauldronCards);
    expect(lo.mouthEmbers).toBeLessThan(hi.mouthEmbers);
  });

  it("packs the bed cards with their sources' indices", () => {
    for (const name of ["high", "low"] as const) {
      const t = flameTier(name);
      const cards = flameCards(fires, t);
      expect(cards.length % CARD_STRIDE).toBe(0);
      const rows = cards.length / CARD_STRIDE;
      expect(rows).toBe(t.cauldronCards + 2 * t.kilnCards);
      for (let r = 0; r < rows; r++) {
        const src = fires[cards[r * CARD_STRIDE + 6]];
        expect(src.kind).toBe("bed");
        if (src.kind !== "bed") continue;
        // On its bed's foot, no wider than a little over the bed, no taller than its flames.
        expect(cards[r * CARD_STRIDE + 1]).toBeCloseTo(src.base[1], 3);
        expect(Math.hypot(cards[r * CARD_STRIDE] - src.base[0], cards[r * CARD_STRIDE + 2] - src.base[2])).toBeLessThanOrEqual(src.radius);
        expect(cards[r * CARD_STRIDE + 3]).toBeLessThanOrEqual(src.radius * 2.5);
        expect(cards[r * CARD_STRIDE + 4]).toBeLessThanOrEqual(src.height + 1e-9);
        // A kiln's cards stand in front of its box; a cauldron's on its surface.
        if (src.style === "kiln") expect(cards[r * CARD_STRIDE + 7]).toBeGreaterThanOrEqual(src.pull - 1e-6);
        else expect(cards[r * CARD_STRIDE + 7]).toBe(0);
      }
    }
  });

  it("gives embers to the openings and kilns only", () => {
    const t = flameTier("high");
    const e = emberSeeds(fires, t);
    expect(e.length % EMBER_STRIDE).toBe(0);
    const bySource = new Map<number, number>();
    for (let i = 0; i < e.length; i += EMBER_STRIDE) {
      bySource.set(e[i], (bySource.get(e[i]) ?? 0) + 1);
      expect(e[i + 3]).toBeGreaterThanOrEqual(0);
      expect(e[i + 3]).toBeLessThan(1);
    }
    fires.forEach((f, i) => {
      const want = f.kind === "opening" ? t.mouthEmbers : f.style === "kiln" ? t.kilnEmbers : 0;
      expect(bySource.get(i) ?? 0).toBe(want);
    });
  });

  it("puts one quad on each opening, just in front of its face", () => {
    const q = openingQuads(fires);
    const mouths = fires.filter((f): f is OpeningFire => f.kind === "opening");
    expect(q.length).toBe(mouths.length * 6 * MOUTH_STRIDE);
    for (let v = 0; v < q.length / MOUTH_STRIDE; v++) {
      const o = q.subarray(v * MOUTH_STRIDE, (v + 1) * MOUTH_STRIDE);
      const m = fires[o[5]] as OpeningFire;
      const d = [o[0] - m.base[0], o[1] - m.base[1], o[2] - m.base[2]];
      // Float32 world positions near x 130: about 1e-5 m.
      expect(d[0] * m.normal[0] + d[2] * m.normal[2]).toBeCloseTo(FLAMES.mouthLift, 3);
      expect(d[0] * m.right[0] + d[2] * m.right[2]).toBeCloseTo(o[3], 3);
      expect(d[1]).toBeCloseTo(o[4], 3);
      expect(Math.abs(o[3])).toBeLessThanOrEqual(m.width / 2 + 1e-6);
      expect(o[4]).toBeGreaterThanOrEqual(0);
      expect(o[4]).toBeLessThanOrEqual(m.height + 1e-6);
    }
  });

  it("bounds every fire with what it draws", () => {
    for (const f of fires) {
      const b = fireBounds(f);
      expect(Math.hypot(f.base[0] - b.center[0], f.base[1] - b.center[1], f.base[2] - b.center[2])).toBeLessThan(b.radius);
      const top: Vec3 = [f.base[0], f.base[1] + f.height, f.base[2]];
      expect(Math.hypot(top[0] - b.center[0], top[1] - b.center[1], top[2] - b.center[2])).toBeLessThan(b.radius);
    }
  });
});
