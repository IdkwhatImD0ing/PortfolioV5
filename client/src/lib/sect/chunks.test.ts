import { describe, expect, it } from "vitest";
import { areaIndexAt, gapToRange, holdCores, jumpLeg, planChunks, travelAfterJump, travelDirection, type ChunkCost, type ChunkSpan, type PlanWindow, type Travel } from "./chunks";

// Need ranges shaped like the full flight's: each area plus a lead-in, neighbours overlapping.
const CHUNKS: ChunkSpan[] = [
  { id: "gate", need: [1, 190] },
  { id: "mirror", need: [140, 320] },
  { id: "forge", need: [270, 520] },
  { id: "arena", need: [480, 630] },
  { id: "mission", need: [590, 760] },
  { id: "library", need: [720, 960] },
];

const none = new Set<string>();
const set = (...ids: string[]) => new Set(ids);

describe("gapToRange", () => {
  it("is zero inside the range and the distance outside it", () => {
    expect(gapToRange(50, [10, 100])).toBe(0);
    expect(gapToRange(5, [10, 100])).toBe(5);
    expect(gapToRange(130, [10, 100])).toBe(30);
  });
});

describe("planChunks", () => {
  it("needs the chunks around the camera, nearest first, and loads the missing ones", () => {
    const p = planChunks({ chunks: CHUNKS, frame: 93, direction: 1, resident: none, loading: none });
    expect(p.need).toEqual(["gate", "mirror"]);
    expect(p.load).toEqual(["gate", "mirror"]);
    expect(p.prefetch).toBeNull(); // nothing is prefetched while something needed is missing
    expect(p.draw).toEqual([]);
  });

  it("looks further ahead than behind, and flips with the direction of travel", () => {
    // Frame 220: the gate ended 30 frames back (beyond the 24 behind), the forge starts 50 ahead.
    const fwd = planChunks({ chunks: CHUNKS, frame: 220, direction: 1, resident: none, loading: none });
    expect(fwd.need).toEqual(["mirror", "forge"]);
    const back = planChunks({ chunks: CHUNKS, frame: 220, direction: -1, resident: none, loading: none });
    expect(back.need).toEqual(["mirror", "gate"]);
  });

  it("draws only resident chunks whose need range holds the frame", () => {
    const p = planChunks({ chunks: CHUNKS, frame: 150, direction: 1, resident: set("gate", "mirror"), loading: none });
    expect(p.draw).toEqual(["gate", "mirror"]);
    const q = planChunks({ chunks: CHUNKS, frame: 230, direction: 1, resident: set("gate", "mirror"), loading: none });
    expect(q.draw).toEqual(["mirror"]);
    expect(q.keep).toContain("gate"); // still inside the keep window
  });

  it("prefetches the next chunk in flight order while idle", () => {
    const p = planChunks({ chunks: CHUNKS, frame: 93, direction: 1, resident: set("gate", "mirror"), loading: none });
    expect(p.load).toEqual([]);
    expect(p.prefetch).toBe("forge");
    // Going backwards from the forge, the chunk behind is prefetched instead.
    const q = planChunks({ chunks: CHUNKS, frame: 440, direction: -1, resident: set("forge"), loading: none });
    expect(q.need).toEqual(["forge"]);
    expect(q.prefetch).toBe("mirror");
  });

  it("does not prefetch past the cap or beyond the keep window", () => {
    const full = planChunks({ chunks: CHUNKS, frame: 93, direction: 1, resident: set("gate", "mirror", "forge"), loading: none });
    expect(full.prefetch).toBeNull();
    const far = planChunks({
      chunks: [
        { id: "a", need: [0, 100] },
        { id: "b", need: [900, 1000] },
      ],
      frame: 50,
      direction: 1,
      resident: set("a"),
      loading: none,
    });
    expect(far.prefetch).toBeNull();
  });

  it("keeps chunks inside the wider window (hysteresis) and drops the ones outside", () => {
    // Just past the mirror: gate is no longer needed but is kept.
    const near = planChunks({ chunks: CHUNKS, frame: 330, direction: 1, resident: set("gate", "mirror", "forge"), loading: none });
    expect(near.need).toEqual(["forge", "mirror"]);
    expect(near.keep.sort()).toEqual(["forge", "gate", "mirror"]);
    expect(near.drop).toEqual([]);
    // Scrolling back a little re-needs the mirror without any reload.
    const back = planChunks({ chunks: CHUNKS, frame: 300, direction: -1, resident: set("gate", "mirror", "forge"), loading: none });
    expect(back.load).toEqual([]);
    // Well into the forge the gate is out of the keep window.
    const later = planChunks({ chunks: CHUNKS, frame: 420, direction: 1, resident: set("gate", "mirror", "forge"), loading: none });
    expect(later.drop).toEqual(["gate"]);
    expect(later.keep.sort()).toEqual(["forge", "mirror"]);
  });

  it("holds about three chunks: over the cap the farthest unneeded chunk goes first", () => {
    const p = planChunks({
      chunks: CHUNKS,
      frame: 600,
      direction: 1,
      resident: set("forge", "arena", "mission", "library"),
      loading: none,
      window: { keepBehind: 400, keepAhead: 400 },
    });
    expect(p.need).toEqual(["arena", "mission"]);
    expect(p.keep.length).toBe(3);
    expect(p.drop.length).toBe(1);
    expect(p.keep).toEqual(expect.arrayContaining(["arena", "mission"]));
  });

  it("caps the resident set even when more chunks are needed: nearest area first", () => {
    // Need ranges as wide as an area's whole visibility (seen from far away); cores are the areas.
    const wide: ChunkSpan[] = [
      { id: "a", need: [0, 900], core: [0, 100] },
      { id: "b", need: [0, 900], core: [101, 200] },
      { id: "c", need: [0, 900], core: [201, 300] },
      { id: "d", need: [0, 900], core: [301, 400] },
      { id: "e", need: [0, 900], core: [401, 500] },
    ];
    const p = planChunks({ chunks: wide, frame: 250, direction: 1, resident: none, loading: none });
    expect(p.need).toEqual(["c", "b", "d"]);
    const q = planChunks({ chunks: wide, frame: 250, direction: 1, resident: set("a", "b", "c", "d", "e"), loading: none });
    expect(q.keep.sort()).toEqual(["b", "c", "d"]);
    expect(q.drop.sort()).toEqual(["a", "e"]);
  });

  it("keeps extra chunks inside the triangle budget; the two nearest areas always stay", () => {
    const heavy: ChunkSpan[] = [
      { id: "a", need: [0, 900], core: [0, 100], tris: 1_400_000 },
      { id: "b", need: [0, 900], core: [101, 200], tris: 900_000 },
      { id: "c", need: [0, 900], core: [201, 300], tris: 1_600_000 },
      { id: "d", need: [0, 900], core: [301, 400], tris: 100_000 },
    ];
    // a + b are the nearest two (2.3M); with a 2.5M budget c (1.6M more) does not fit, d does.
    const p = planChunks({ chunks: heavy, frame: 50, direction: 1, resident: none, loading: none, window: { triBudget: 2_500_000, maxResident: 4 } });
    expect(p.need).toEqual(["a", "b", "d"]);
    // A tight budget: only the nearest two (moving forward, the area ahead beats the one passed).
    const q = planChunks({ chunks: heavy, frame: 250, direction: 1, resident: none, loading: none, window: { triBudget: 1_000_000 } });
    expect(q.need).toEqual(["c", "d"]);
  });

  it("does not swap chunks back and forth at a boundary between two areas (stickiness)", () => {
    const wide: ChunkSpan[] = [
      { id: "a", need: [0, 900], core: [0, 100] },
      { id: "b", need: [0, 900], core: [101, 200] },
      { id: "c", need: [0, 900], core: [201, 300] },
      { id: "d", need: [0, 900], core: [301, 400] },
    ];
    // A resident area keeps its slot until another is clearly nearer: at 160 nothing swaps.
    const p = planChunks({ chunks: wide, frame: 160, direction: 1, resident: set("a", "b", "c"), loading: none, window: { maxResident: 3 } });
    expect(p.drop).toEqual([]);
    expect(p.load).toEqual([]);
  });

  it("gathers only the area a jump lands in, even when wider need ranges reach the target", () => {
    const wide: ChunkSpan[] = [
      { id: "a", need: [0, 900], core: [0, 100] },
      { id: "b", need: [0, 900], core: [101, 200] },
      { id: "c", need: [0, 900], core: [201, 300] },
    ];
    const p = planChunks({ chunks: wide, frame: 50, direction: 1, resident: set("a"), loading: none, target: 250 });
    expect(p.need).toEqual(["c"]);
    expect(p.load).toEqual(["c"]);
  });

  it("with a one-area budget, a jump gathers its landing area even when a held neighbour ends just before the stop", () => {
    // Forge to arena on a phone: the forge's core ends 20 frames before the arena stop, so with
    // stickiness the held forge ranks as near as the arena. The arena must still be the one needed.
    const areas: ChunkSpan[] = [
      { id: "forge", need: [1, 943], core: [287, 496], tris: 1_100_000 },
      { id: "arena", need: [97, 1057], core: [497, 604], tris: 900_000 },
      { id: "mission", need: [181, 1276], core: [605, 738], tris: 1_200_000 },
    ];
    const p = planChunks({
      chunks: areas,
      frame: 352,
      direction: 1,
      resident: set("forge"),
      loading: none,
      target: 516,
      window: { minResident: 1, triBudget: 510_000 },
    });
    expect(p.need).toEqual(["arena"]);
    expect(p.load).toEqual(["arena"]);
  });

  it("plans a far jump for its destination, not for the frames it sweeps through", () => {
    const p = planChunks({
      chunks: CHUNKS,
      frame: 93,
      direction: 1,
      resident: set("gate", "mirror"),
      loading: none,
      target: 818,
    });
    expect(p.need).toEqual(["library"]);
    expect(p.load).toEqual(["library"]);
    expect(p.prefetch).toBeNull();
    // The chunks the camera is leaving stay while the cap allows (the world is never empty).
    expect(p.drop).toEqual([]);
    expect(p.draw).toEqual(["gate"]);
  });

  it("cancels loads that no window wants any more", () => {
    const p = planChunks({ chunks: CHUNKS, frame: 900, direction: 1, resident: set("library"), loading: set("gate") });
    expect(p.cancel).toEqual(["gate"]);
  });

  it("prefetches the next area past the triangle budget into a spare slot, and keeps it until passed", () => {
    const heavy: ChunkSpan[] = [
      { id: "gate", need: [1, 190], tris: 1_000_000 },
      { id: "mirror", need: [140, 320], tris: 800_000 },
      { id: "forge", need: [270, 520], tris: 900_000 },
      { id: "arena", need: [480, 630], tris: 600_000 },
    ];
    const budget = { triBudget: 2_000_000 };
    const spare = { ...budget, spare: 1 };
    // Resting at the gate with the gate and the mirror (1.8M): the forge (0.9M more) does not fit.
    expect(planChunks({ chunks: heavy, frame: 93, direction: 1, resident: set("gate", "mirror"), loading: none, window: budget }).prefetch).toBeNull();
    expect(planChunks({ chunks: heavy, frame: 93, direction: 1, resident: set("gate", "mirror"), loading: none, window: spare }).prefetch).toBe("forge");
    // Once loaded it stays (no load, drop, load again), and nothing more is prefetched.
    const held = planChunks({ chunks: heavy, frame: 93, direction: 1, resident: set("gate", "mirror", "forge"), loading: none, window: spare });
    expect(held.drop).toEqual([]);
    expect(held.prefetch).toBeNull();
    // Without the spare slot it would be dropped again.
    expect(planChunks({ chunks: heavy, frame: 93, direction: 1, resident: set("gate", "mirror", "forge"), loading: none, window: budget }).drop).toEqual(["forge"]);
    // An area the camera has passed never takes the spare slot: past the mirror the gate goes, and
    // the slot goes to the next area ahead.
    const on = planChunks({ chunks: heavy, frame: 330, direction: 1, resident: set("gate", "mirror", "forge"), loading: none, window: spare });
    expect(on.drop).toEqual(["gate"]);
    expect(on.prefetch).toBe("arena");
  });

  it("keeps its spare slot during a jump (the areas it leaves are not fetched again), but prefetches nothing", () => {
    const heavy: ChunkSpan[] = [
      { id: "gate", need: [1, 190], tris: 1_000_000 },
      { id: "mirror", need: [140, 320], tris: 800_000 },
      { id: "forge", need: [270, 520], tris: 900_000 },
    ];
    const p = planChunks({ chunks: heavy, frame: 93, direction: 1, resident: set("gate", "mirror", "forge"), loading: none, target: 217, window: { triBudget: 2_000_000, spare: 1 } });
    expect(p.prefetch).toBeNull();
    // The mirror (the stop) and the gate (where the camera waits) fit the budget; the forge, prefetched
    // ahead, keeps the spare slot. (Before, it was dropped here and fetched again on arrival.)
    expect(p.keep).toEqual(["gate", "mirror", "forge"]);
    expect(p.drop).toEqual([]);
  });

  it("finds the next chunk to prefetch from a gap between need ranges", () => {
    const gappy: ChunkSpan[] = [
      { id: "a", need: [0, 100] },
      { id: "b", need: [300, 400] },
    ];
    const p = planChunks({ chunks: gappy, frame: 150, direction: 1, resident: none, loading: none });
    expect(p.need).toEqual([]);
    expect(p.prefetch).toBe("b");
  });
});

// The shipped full set's chunks (need ranges, area cores, triangles).
const FLIGHT: ChunkSpan[] = [
  { id: "gate", need: [1, 319], core: [1, 165], tris: 1_177_903 },
  { id: "mirror", need: [1, 730], core: [166, 286], tris: 680_793 },
  { id: "forge", need: [1, 943], core: [287, 496], tris: 1_116_876 },
  { id: "arena", need: [97, 1057], core: [497, 604], tris: 921_320 },
  { id: "mission", need: [181, 1276], core: [605, 738], tris: 1_191_075 },
  { id: "library", need: [253, 1348], core: [739, 942], tris: 1_187_907 },
  { id: "steles", need: [448, 1342], core: [943, 1053], tris: 1_550_538 },
  { id: "scroll", need: [538, 1612], core: [1054, 1187], tris: 863_205 },
  { id: "formation", need: [640, 1666], core: [1188, 1343], tris: 418_083 },
  { id: "abode", need: [775, 1729], core: [1344, 1534], tris: 1_059_285 },
  { id: "summit", need: [1024, 1729], core: [1535, 1729], tris: 533_087 },
];

describe("planChunks looking back", () => {
  // The desktop budget less the global set's 0.69 M triangles (streaming.ts STREAM_BUDGETS, setGlobalTris).
  const desktop = { triBudget: 1_807_288, minResident: 2, spare: 1, lookBack: 1 };
  const phone = { triBudget: 507_288, minResident: 1, spare: 0, lookBack: 0 };
  const plan = (frame: number, resident: Set<string>, lookingBack: boolean | undefined, window = desktop) =>
    planChunks({ chunks: FLIGHT, frame, direction: 1, resident, loading: none, window, lookingBack });

  it("at rest at the steles, turned round: the library behind is needed, and the plan is unchanged without the flag", () => {
    // What a forward flight leaves resident at the steles: the area, the next and the one after.
    const resident = set("steles", "scroll", "formation");
    const off = plan(974, resident, false);
    expect(plan(974, resident, undefined)).toEqual(off);
    expect(off.need).not.toContain("library");
    expect(off.drop).toEqual([]);
    const on = plan(974, resident, true);
    expect(on.need).toContain("library");
    expect(on.load).toEqual(["library"]);
    // The usual plan is untouched: the areas ahead (formation is the prefetched one) all stay.
    expect(on.keep).toEqual(["steles", "scroll", "formation"]);
    expect(on.drop).toEqual([]);
    // Turning forward again drops only the extra area.
    const after = plan(974, set("steles", "scroll", "formation", "library"), false);
    expect(after.drop).toEqual(["library"]);
    expect(after.keep).toEqual(["steles", "scroll", "formation"]);
    expect(after.load).toEqual([]);
  });

  it("at the forge, turned round: the mirror behind is requested, and the areas ahead stay", () => {
    const on = plan(352, set("forge", "arena", "mission"), true);
    expect(on.load).toEqual(["mirror"]);
    expect(on.keep).toEqual(["forge", "arena", "mission"]);
    expect(on.drop).toEqual([]);
    expect(plan(352, set("forge", "arena", "mission"), false).load).toEqual([]);
    const after = plan(352, set("mirror", "forge", "arena", "mission"), false);
    expect(after.drop).toEqual(["mirror"]);
  });

  it("looks for the area behind the view at lower frames, even after scrolling backward", () => {
    // The path camera faces higher frames either way, so turned round it looks toward lower ones.
    const back = (resident: Set<string>, lookingBack: boolean) =>
      planChunks({ chunks: FLIGHT, frame: 974, direction: -1, resident, loading: none, window: desktop, lookingBack });
    const resident = new Set(back(set("steles", "library"), false).keep);
    const on = back(resident, true);
    expect(on.load).toEqual(["mission"]);
    expect(on.drop).toEqual([]);
    expect(on.load).not.toContain("scroll");
  });

  it("takes one area past the cap (four instead of three), and only one that is drawn at this frame", () => {
    // At the mission the forge (two areas back) is behind the camera: it loads as a fourth area.
    const on = plan(619, set("arena", "mission", "library"), true);
    expect(on.load).toEqual(["forge"]);
    expect(on.drop).toEqual([]);
    // Once loaded, all four stay and are drawn.
    const held = plan(619, set("arena", "mission", "library", "forge"), true);
    expect(held.drop).toEqual([]);
    expect(held.draw.sort()).toEqual(["arena", "forge", "library", "mission"]);
    // An area behind whose need range ends just before the frame would not be drawn: it never
    // takes the slot. Ending just after, it does.
    const behind = (end: number): ChunkSpan[] => [
      { id: "a", need: [0, end], core: [0, 100] },
      { id: "b", need: [80, 400], core: [101, 300] },
      { id: "c", need: [250, 600], core: [301, 600] },
    ];
    const look = (end: number) =>
      planChunks({ chunks: behind(end), frame: 300, direction: 1, resident: set("b", "c"), loading: none, lookingBack: true, window: { maxResident: 2, lookBack: 1 } });
    expect(look(290).load).toEqual([]);
    expect(look(310).load).toEqual(["a"]);
  });

  it("gives the area back once the view turns forward or the camera moves on", () => {
    const four = set("arena", "mission", "library", "forge");
    const off = plan(619, four, false);
    expect(off.drop).toEqual(["forge"]);
    expect(off.keep.length).toBe(3);
  });

  it("phones keep their one-area limit", () => {
    const resident = set("steles");
    expect(plan(974, resident, true, phone)).toEqual(plan(974, resident, false, phone));
    expect(plan(974, resident, true, phone).need).toEqual(["steles"]);
  });

  it("is ignored during a jump", () => {
    const on = planChunks({ chunks: FLIGHT, frame: 974, direction: 1, resident: set("steles"), loading: none, target: 1647, lookingBack: true, window: desktop });
    const off = planChunks({ chunks: FLIGHT, frame: 974, direction: 1, resident: set("steles"), loading: none, target: 1647, window: desktop });
    expect(on).toEqual(off);
  });
});

describe("planChunks retaining passed areas", () => {
  const MB = 1_000_000;
  // Texture memory each shipped area takes on the GPU (RGBA8 with mips, measured from the GLBs).
  const TEX: Record<string, number> = {
    gate: 228, mirror: 156, forge: 157, arena: 158, mission: 152, library: 225,
    steles: 150, scroll: 141, formation: 115, abode: 183, summit: 152,
  };
  const loadedOf = (...ids: string[]) =>
    new Map<string, ChunkCost>(ids.map((id) => [id, { tris: FLIGHT.find((c) => c.id === id)!.tris!, texBytes: TEX[id] * MB }]));
  const desktop = { triBudget: 1_807_288, minResident: 2, spare: 1, lookBack: 1 };
  const roomy = { ...desktop, retainTris: 5_000_000, retainTexBytes: 900 * MB };
  // A forward flight that has reached the steles, with the three areas before it still loaded.
  const passed = ["arena", "mission", "library", "steles", "scroll", "formation"];

  it("is off by default: the usual plan, nothing retained", () => {
    const resident = set(...passed);
    const off = planChunks({ chunks: FLIGHT, frame: 974, direction: 1, resident, loading: none, loaded: loadedOf(...passed), window: desktop });
    expect(off).toEqual(planChunks({ chunks: FLIGHT, frame: 974, direction: 1, resident, loading: none, window: desktop }));
    expect(off.retain).toEqual([]);
    expect(off.drop).toEqual(["arena", "mission", "library"]);
  });

  it("keeps passed areas nearest first while they fit; the farthest go first", () => {
    const p = planChunks({ chunks: FLIGHT, frame: 974, direction: 1, resident: set(...passed), loading: none, loaded: loadedOf(...passed), window: roomy });
    // The usual three (2.83 M) and the library (1.19 M more) fit 5 M; the mission would not.
    expect(p.retain).toEqual(["library"]);
    expect(p.keep).toEqual(["library", "steles", "scroll", "formation"]);
    expect(p.drop).toEqual(["arena", "mission"]);
    // The usual plan is untouched.
    expect(p.need).toEqual(planChunks({ chunks: FLIGHT, frame: 974, direction: 1, resident: set(...passed), loading: none, window: desktop }).need);
    // When texture memory binds first: 406 + 225 + 152 MB fit 800 MB, the arena's 158 MB more does not.
    const tex = planChunks({
      chunks: FLIGHT,
      frame: 974,
      direction: 1,
      resident: set(...passed),
      loading: none,
      loaded: loadedOf(...passed),
      window: { ...desktop, retainTris: 100_000_000, retainTexBytes: 800 * MB },
    });
    expect(tex.retain).toEqual(["library", "mission"]);
    expect(tex.drop).toEqual(["arena"]);
  });

  it("scrolling back to a retained area needs no load", () => {
    const resident = set("library", "steles", "scroll", "formation");
    const p = planChunks({ chunks: FLIGHT, frame: 900, direction: -1, resident, loading: none, loaded: loadedOf(...resident), window: roomy });
    expect(p.need).toContain("library");
    expect(p.load).toEqual([]);
    expect(p.draw).toContain("library");
  });

  it("never gives up a nearer area to keep a farther one", () => {
    const line: ChunkSpan[] = [
      { id: "far", need: [0, 100], tris: 100_000 },
      { id: "near", need: [400, 500], tris: 3_000_000 },
      { id: "here", need: [900, 1000], tris: 1_000_000 },
    ];
    const loaded = new Map<string, ChunkCost>(line.map((c) => [c.id, { tris: c.tris!, texBytes: MB }]));
    const p = planChunks({
      chunks: line,
      frame: 950,
      direction: 1,
      resident: set("far", "near", "here"),
      loading: none,
      loaded,
      window: { retainTris: 2_000_000, retainTexBytes: 900 * MB },
    });
    // "far" alone would fit (1.1 M), but "near" is nearer and does not: both go.
    expect(p.retain).toEqual([]);
    expect(p.drop).toEqual(["far", "near"]);
  });

  it("never retains a chunk that is still loading or failed to load", () => {
    // "mission" failed (the streamer counts it resident so it is not retried at once); "arena" is loading.
    const p = planChunks({
      chunks: FLIGHT,
      frame: 974,
      direction: 1,
      resident: set("mission", "library", "steles", "scroll", "formation"),
      loading: set("arena"),
      loaded: loadedOf("library", "steles", "scroll", "formation"),
      window: { ...roomy, retainTris: 100_000_000 },
    });
    expect(p.retain).toEqual(["library"]);
    expect(p.drop).toEqual(["mission"]);
    expect(p.cancel).toEqual(["arena"]);
  });

  it("counts the areas still to load and the prefetch with their estimates", () => {
    const line: ChunkSpan[] = [
      { id: "a", need: [0, 100], tris: 1, texBytes: 100 * MB },
      { id: "b", need: [101, 200], tris: 1, texBytes: 100 * MB },
      { id: "c", need: [201, 300], tris: 1, texBytes: 100 * MB },
      { id: "z", need: [800, 900], tris: 1, texBytes: 100 * MB },
    ];
    const loaded = new Map<string, ChunkCost>(["a", "b", "z"].map((id) => [id, { tris: 1, texBytes: 100 * MB }]));
    const at = (retainTexBytes: number) =>
      planChunks({ chunks: line, frame: 50, direction: 1, resident: set("a", "b", "z"), loading: none, loaded, window: { retainTris: 100, retainTexBytes } });
    // a and b kept, c prefetched (its estimate counts): 300 MB, so z does not fit...
    expect(at(300 * MB).prefetch).toBe("c");
    expect(at(300 * MB).drop).toEqual(["z"]);
    // ...with room for it, it stays.
    expect(at(400 * MB).retain).toEqual(["z"]);
    // An area still to load counts too: at 850 "z" is needed and not loaded yet, so its 100 MB
    // estimate leaves no room for "a" (10 MB) under 105 MB.
    const small = new Map<string, ChunkCost>([["a", { tris: 1, texBytes: 10 * MB }]]);
    const need = (retainTexBytes: number) =>
      planChunks({ chunks: line, frame: 850, direction: 1, resident: set("a"), loading: none, loaded: small, window: { retainTris: 100, retainTexBytes } });
    expect(need(105 * MB).load).toEqual(["z"]);
    expect(need(105 * MB).drop).toEqual(["a"]);
    expect(need(110 * MB).retain).toEqual(["a"]);
  });

  it("during a jump, an area near the target counts as near as one near the camera", () => {
    const line: ChunkSpan[] = [
      { id: "a", need: [0, 100], tris: 1 },
      { id: "m1", need: [350, 449], tris: 1 },
      { id: "m2", need: [550, 640], tris: 1 },
      { id: "z", need: [700, 799], tris: 1 },
      { id: "t", need: [800, 900], tris: 1 },
    ];
    const loaded = new Map<string, ChunkCost>(["a", "m1", "m2", "z"].map((id) => [id, { tris: 1, texBytes: 0 }]));
    const p = planChunks({
      chunks: line,
      frame: 50,
      direction: 1,
      resident: set("a", "m1", "m2", "z"),
      loading: none,
      target: 850,
      loaded,
      window: { retainTris: 4, retainTexBytes: 1 },
    });
    expect(p.load).toEqual(["t"]);
    // t, a and z are the usual plan; one more fits: m2 (210 frames short of the target) before m1
    // (300 frames from the camera).
    expect(p.retain).toEqual(["m2"]);
    expect(p.drop).toEqual(["m1"]);
  });

  it("phones and the plain desktop budget plan exactly as before", () => {
    for (const window of [desktop, { triBudget: 507_288, minResident: 1, spare: 0, lookBack: 0 }]) {
      for (const frame of [93, 352, 974, 1647]) {
        const resident = set(...passed);
        const loaded = loadedOf(...passed);
        expect(planChunks({ chunks: FLIGHT, frame, direction: 1, resident, loading: none, loaded, window })).toEqual(
          planChunks({ chunks: FLIGHT, frame, direction: 1, resident, loading: none, window }),
        );
      }
    }
  });
});

describe("planChunks handing over", () => {
  // The phone budget less the global set's 0.69 M triangles: one area, plus one spare slot.
  const phone = { triBudget: 507_288, minResident: 1, spare: 1, lookBack: 0 };

  it("keeps the area on screen until the one it hands over to is ready", () => {
    // Just inside the arena (its core starts at 497), the arena still loading, the forge drawn.
    const leaving = (ready?: Set<string>) =>
      planChunks({ chunks: FLIGHT, frame: 530, direction: 1, resident: set("forge"), loading: set("arena"), ready, window: phone });
    const p = leaving(set("forge"));
    expect(p.need).toEqual(["arena"]);
    expect(p.handover).toEqual(["forge"]);
    expect(p.drop).toEqual([]);
    expect(p.draw).toEqual(["forge"]);
    expect(p.cancel).toEqual([]);
    // Without the ready list (nothing known) the plan is the old one: the forge goes at once.
    expect(leaving().drop).toEqual(["forge"]);
    expect(leaving().handover).toEqual([]);
    // Uploaded but not ready yet counts as not ready: the forge still stays.
    const uploading = planChunks({ chunks: FLIGHT, frame: 530, direction: 1, resident: set("forge", "arena"), loading: none, ready: set("forge"), window: phone });
    expect(uploading.handover).toEqual(["forge"]);
    expect(uploading.prefetch).toBeNull();
    // Once the arena is ready, the forge goes.
    const done = planChunks({ chunks: FLIGHT, frame: 530, direction: 1, resident: set("forge", "arena"), loading: none, ready: set("forge", "arena"), window: phone });
    expect(done.handover).toEqual([]);
    expect(done.drop).toEqual(["forge"]);
  });

  it("only hands over from an area that is ready and drawn at this frame, the nearest one", () => {
    // The steles and the library are both loaded; at 1110 (the scroll's core) the scroll loads.
    const p = planChunks({
      chunks: FLIGHT,
      frame: 1110,
      direction: 1,
      resident: set("library", "steles"),
      loading: set("scroll"),
      ready: set("library", "steles"),
      window: phone,
    });
    expect(p.handover).toEqual(["steles"]);
    expect(p.drop).toEqual(["library"]);
    // Not ready itself (still uploading): nothing to hand over from.
    const q = planChunks({ chunks: FLIGHT, frame: 1110, direction: 1, resident: set("steles"), loading: set("scroll"), ready: none, window: phone });
    expect(q.handover).toEqual([]);
    // Not drawn at this frame (its need range ends before it): nothing either.
    const r = planChunks({ chunks: FLIGHT, frame: 1400, direction: 1, resident: set("steles"), loading: set("abode"), ready: set("steles"), window: phone });
    expect(r.handover).toEqual([]);
    expect(r.drop).toEqual(["steles"]);
  });

  it("a phone keeps the area it waits in during a jump, and drops the rest", () => {
    // Resting at the gate with the mirror prefetched, the visitor picks the forge on the rail.
    const p = planChunks({ chunks: FLIGHT, frame: 93, direction: 1, resident: set("gate", "mirror"), loading: none, target: 352, ready: set("gate", "mirror"), window: phone });
    expect(p.need).toEqual(["forge"]);
    expect(p.load).toEqual(["forge"]);
    // The gate takes the spare slot (no extra area for the hand-over), the mirror goes.
    expect(p.keep).toEqual(["gate"]);
    expect(p.handover).toEqual([]);
    expect(p.drop).toEqual(["mirror"]);
    expect(p.draw).toEqual(["gate"]);
  });

  it("a phone prefetches the next area into its spare slot once everything needed is ready", () => {
    const at = (ready: Set<string>) =>
      planChunks({ chunks: FLIGHT, frame: 352, direction: 1, resident: set("forge"), loading: none, ready, window: phone }).prefetch;
    expect(at(set("forge"))).toBe("arena");
    expect(at(none)).toBeNull();
  });
});

/**
 * Plays a visit through the planner (loads finish at once, the ready list follows) and counts how
 * often each area is fetched: the rail stop by stop, then Home and the rail again.
 */
function fetchCounts(window: Partial<PlanWindow>, stops: number[]): Map<string, number> {
  const resident = new Set<string>();
  const counts = new Map<string, number>();
  const step = (frame: number, target: number | null, idle: boolean) => {
    const p = planChunks({ chunks: FLIGHT, frame, direction: 1, resident, loading: none, target, ready: resident, window });
    for (const id of p.drop) resident.delete(id);
    const fetch = [...p.load, ...(idle && p.prefetch ? [p.prefetch] : [])];
    for (const id of fetch) {
      resident.add(id);
      counts.set(id, (counts.get(id) ?? 0) + 1);
    }
  };
  let frame = stops[0];
  for (let i = 0; i < 3; i++) step(frame, null, true);
  for (const to of stops.slice(1)) {
    // Gather at the stop the camera waits at, fly (planning for the target), then rest on arrival.
    step(frame, to, false);
    step(frame, to, false);
    for (const f of [frame + (to - frame) / 2, to]) step(f, to, false);
    frame = to;
    for (let i = 0; i < 3; i++) step(frame, null, true);
  }
  return counts;
}

describe("planChunks over a whole visit", () => {
  const holds = [93, 217, 352, 516, 619, 772, 974, 1103, 1208, 1380, 1647];
  const desktop = { triBudget: 1_807_288, minResident: 2, spare: 1, lookBack: 1 };

  it("fetches each area once per pass along the rail", () => {
    const counts = fetchCounts(desktop, holds);
    expect(Math.max(...counts.values())).toBe(1);
    expect(counts.size).toBe(FLIGHT.length);
  });

  it("a phone does too, with its one area and its spare slot", () => {
    const counts = fetchCounts({ triBudget: 507_288, minResident: 1, spare: 1, lookBack: 0 }, holds);
    expect(Math.max(...counts.values())).toBe(1);
    expect(counts.size).toBe(FLIGHT.length);
  });
});

describe("travelDirection", () => {
  const walk =(frames: number[], turn = 24): number[] => {
    let t: Travel | null = null;
    return frames.map((f) => (t = travelDirection(t, f, turn)).direction);
  };

  it("starts forward and turns only after coming back more than `turn` frames", () => {
    expect(walk([93])).toEqual([1]);
    // An overshoot at a stop scrolled back (100 -> 91) keeps it forward.
    expect(walk([80, 100, 91, 93])).toEqual([1, 1, 1, 1]);
    // A real turn: back from 100 past 76.
    expect(walk([80, 100, 90, 75, 70])).toEqual([1, 1, 1, -1, -1]);
    // And the same the other way round.
    expect(walk([100, 70, 60, 80, 85])).toEqual([1, -1, -1, -1, 1]);
  });

  it("keeps the area prefetched into the spare slot through a small step back", () => {
    const heavy: ChunkSpan[] = [
      { id: "gate", need: [1, 190], core: [1, 150], tris: 1_000_000 },
      { id: "mirror", need: [140, 320], core: [151, 280], tris: 800_000 },
      { id: "forge", need: [270, 520], core: [281, 450], tris: 900_000 },
    ];
    const w = { triBudget: 2_000_000, spare: 1 };
    let t: Travel | null = null;
    for (const f of [60, 93, 91]) t = travelDirection(t, f, 24);
    const p = planChunks({ chunks: heavy, frame: 91, direction: t!.direction, resident: set("gate", "mirror", "forge"), loading: none, window: w });
    expect(p.drop).toEqual([]);
  });
});

describe("planChunks direction of travel", () => {
  const two: ChunkSpan[] = [
    { id: "w", need: [0, 900], core: [0, 100] },
    { id: "x", need: [0, 900], core: [101, 200] },
    { id: "y", need: [0, 900], core: [201, 300] },
  ];
  it("gives the next area the slot of the one just passed, early", () => {
    // With two slots, at 170 moving forward: w (passed, 70 back) gives way to y (31 ahead).
    const p = planChunks({ chunks: two, frame: 170, direction: 1, resident: set("w", "x"), loading: none, window: { maxResident: 2 } });
    expect(p.need.sort()).toEqual(["x", "y"]);
    expect(p.drop).toEqual(["w"]);
    // Moving backward at the same frame, w (behind the camera's travel) is the one to keep.
    const q = planChunks({ chunks: two, frame: 170, direction: -1, resident: set("w", "x"), loading: none, window: { maxResident: 2 } });
    expect(q.drop).toEqual([]);
  });
});

describe("holdCores", () => {
  it("gives each hold the stretch halfway to its neighbours, the ends reaching the flight's ends", () => {
    const cores = holdCores(
      [
        { id: "mirror", frame: 217 },
        { id: "gate", frame: 93 },
        { id: "forge", frame: 352 },
      ],
      1,
      500,
    );
    expect(cores.get("gate")).toEqual([1, 155]);
    expect(cores.get("mirror")).toEqual([156, 284]);
    expect(cores.get("forge")).toEqual([285, 500]);
  });
});

describe("travelAfterJump", () => {
  const cores: [number, number][] = [
    [1, 155],
    [156, 284],
    [285, 434],
    [435, 567],
    [568, 700],
  ];
  const back: Travel = { direction: -1, extreme: 217 };

  it("finds the area whose stretch holds a frame, else the nearest", () => {
    expect(areaIndexAt(cores, 93)).toBe(0);
    expect(areaIndexAt(cores, 516)).toBe(3);
    expect(areaIndexAt(cores, 900)).toBe(4);
    expect(areaIndexAt([], 10)).toBe(-1);
  });

  it("a jump back past the area just before faces forward again where it lands", () => {
    expect(travelAfterJump(back, 516, 217, 217, cores)).toEqual({ direction: 1, extreme: 217 });
    expect(travelAfterJump({ direction: -1, extreme: 300 }, 650, 300, 300, cores)).toEqual({ direction: 1, extreme: 300 });
  });

  it("a step back to the area just before keeps facing back, and a jump forward keeps facing forward", () => {
    expect(travelAfterJump(back, 352, 217, 217, cores)).toBe(back);
    const fwd: Travel = { direction: 1, extreme: 516 };
    expect(travelAfterJump(fwd, 93, 516, 516, cores)).toBe(fwd);
  });

  it("counts K pressed again mid-flight as another one-area step, and a new pick on the rail from the start", () => {
    // K at the arena (516 -> 352), K again before the forge is reached (352 -> 217).
    let leg = jumpLeg(null, 516, 352, cores);
    expect(leg).toEqual({ from: 516, to: 352 });
    expect(jumpLeg(leg, 470, 352, cores)).toBe(leg);
    leg = jumpLeg(leg, 430, 217, cores);
    expect(leg).toEqual({ from: 352, to: 217 });
    expect(travelAfterJump(back, leg.from, leg.to, 217, cores)).toBe(back);
    // The rail: the gate picked from the last area, then the mirror instead, mid-flight.
    leg = jumpLeg(jumpLeg(null, 650, 93, cores), 400, 217, cores);
    expect(leg).toEqual({ from: 650, to: 217 });
    expect(travelAfterJump(back, leg.from, leg.to, 217, cores)).toEqual({ direction: 1, extreme: 217 });
  });
});
