import { beforeEach, describe, expect, it, vi } from "vitest";

const loads: {
  id: string;
  files: string[];
  signal: AbortSignal;
  calm?: () => Promise<void>;
  onBytes?: (url: string) => (loaded: number, total: number) => void;
  resolve: (set: unknown) => void;
  reject: (e: unknown) => void;
}[] = [];

vi.mock("./assets", () => ({
  chunkFiles: (c: { files: string[] }) => c.files,
  disposeSet: vi.fn(),
  // As assets.ts has it (tested there).
  retireSet: (set: { dropped?: boolean; ready: boolean; drawn: boolean; scenes: { visible: boolean }[] }) => {
    set.dropped = true;
    set.ready = false;
    set.drawn = false;
    for (const r of set.scenes) r.visible = false;
  },
  loadSet: vi.fn((ctx: WorldContext, id: string, need: [number, number], files: string[], opts: { signal: AbortSignal; calm?: () => Promise<void>; onBytes?: (url: string) => (loaded: number, total: number) => void }) => {
    // The set holds the manifest's triangles and one 4096 px mipmapped atlas (LinearMipmapLinearFilter).
    const tris = ctx.data.manifest.chunks.find((c) => c.id === id)?.tris ?? 0;
    const textures = [{ image: { width: 4096, height: 4096 }, generateMipmaps: true, minFilter: 1008, userData: {} }];
    return new Promise((resolve, reject) => {
      loads.push({
        id,
        files,
        signal: opts.signal,
        calm: opts.calm,
        onBytes: opts.onBytes,
        resolve: () => resolve({ id, need, scenes: [], ready: false, drawn: false, tris, bytes: 0, textures }),
        reject,
      });
    });
  }),
}));

import { LinearFilter, Texture } from "three";
import type { ChunkInfo } from "@/lib/sect/types";
import {
  ChunkStreamer,
  STREAM_BUDGETS,
  chunkTexBytes,
  estimateTexBytes,
  retryDelayMs,
  roomyMemory,
  streamBudget,
  textureBytes,
} from "./streaming";
import type { WorldContext } from "./assets";

vi.stubGlobal("window", globalThis);

type Fixture = { data: { manifest: { chunks: unknown[] }; camera: { holds: { id: string; frame: number }[] } } };

function ctx(): WorldContext {
  const chunks = [
    { id: "gate", files: ["gate.glb"], need: [1, 300] as [number, number], tris: 1_000_000 },
    { id: "mirror", files: ["mirror.glb"], need: [100, 500] as [number, number], tris: 700_000 },
    { id: "summit", files: ["summit.glb"], need: [1400, 1729] as [number, number], tris: 900_000 },
  ];
  return {
    lowTextures: false,
    data: {
      manifest: { chunks },
      meta: { areas: [] },
      camera: {
        holds: [
          { id: "gate", frame: 93 },
          { id: "mirror", frame: 217 },
          { id: "summit", frame: 1647 },
        ],
        frameStart: 1,
        frameEnd: 1729,
      },
    },
  } as unknown as WorldContext;
}

/** Three areas in a row (gate, mirror, forge) with their holds. */
function three(): WorldContext {
  const c = ctx() as unknown as Fixture;
  c.data.manifest.chunks = [
    { id: "gate", files: ["gate.glb"], need: [1, 300], tris: 1_000_000 },
    { id: "mirror", files: ["mirror.glb"], need: [100, 500], tris: 700_000 },
    { id: "forge", files: ["forge.glb"], need: [250, 700], tris: 900_000 },
  ];
  c.data.camera.holds = [
    { id: "gate", frame: 93 },
    { id: "mirror", frame: 217 },
    { id: "forge", frame: 352 },
  ];
  return c as unknown as WorldContext;
}

const EIGHT = ["gate", "mirror", "forge", "arena", "mission", "library", "steles", "scroll"];

/**
 * Eight areas in a row, holds 100 frames apart (at 50, 150, ... 750), each seen from two areas
 * away either way (its need range), so every area of a stop's window is drawn there.
 */
function eight(): WorldContext {
  const c = ctx() as unknown as Fixture;
  c.data.manifest.chunks = EIGHT.map((id, i) => ({ id, files: [`${id}.glb`], need: [Math.max(1, 100 * i - 150), 100 * i + 250], tris: 1_000_000, bytes: 1000 }));
  c.data.camera.holds = EIGHT.map((id, i) => ({ id, frame: 100 * i + 50 }));
  return c as unknown as WorldContext;
}

async function flush(): Promise<void> {
  for (let i = 0; i < 6; i++) await Promise.resolve();
}

/** Every file of the load in flight for `id` has all its bytes (it is parsed and prepared next). */
function arrive(id: string): void {
  const l = loads.find((x) => x.id === id)!;
  for (const f of l.files) l.onBytes?.(f)(100, 100);
}

/** Every load in flight arrives, and (as the render loop would) is uploaded and marked ready. */
async function settle(st: ChunkStreamer): Promise<void> {
  for (const l of loads.splice(0)) l.resolve(null);
  await flush();
  for (const s of st.list()) st.markReady(s.id);
}

/** The camera rests at `frame` until streaming there has run its course (two loads at a time). */
async function rest(st: ChunkStreamer, frame: number): Promise<void> {
  for (let i = 0; i < 8; i++) {
    st.update(frame, null, true);
    await settle(st);
  }
}

const ids = (st: ChunkStreamer) => st.status().resident.map((r) => r.id);

beforeEach(() => {
  loads.length = 0;
});

describe("ChunkStreamer", () => {
  it("names the area the camera is in (the quality ladder's stand-in step draws only that one)", () => {
    const st = new ChunkStreamer(three(), () => {});
    expect(st.areaAt(93)).toBe("gate");
    expect(st.areaAt(217)).toBe("mirror");
    expect(st.areaAt(352)).toBe("forge");
    // Past the last area's stretch: still the nearest.
    expect(st.areaAt(1700)).toBe("forge");
  });

  it("drops a load that comes back after it was cancelled (a half-prepared set is never kept)", async () => {
    const st = new ChunkStreamer(ctx(), () => {});
    st.update(217, 1647, false);
    const summit = loads.find((l) => l.id === "summit")!;
    st.dispose();
    expect(summit.signal.aborted).toBe(true);
    summit.resolve(null);
    await flush();
    expect(st.list().map((s) => s.id)).not.toContain("summit");
  });

  it("does not cancel a chunk a far jump is waiting for when a newer plan looks elsewhere", () => {
    const st = new ChunkStreamer(eight(), () => {});
    // A jump from the mirror to the scroll gathers it...
    st.update(150, 750, false);
    const scroll = loads.find((l) => l.id === "scroll");
    expect(scroll).toBeDefined();
    void st.whenReady("scroll", 5000);
    // ...while the flight still under way plans around the mirror: the scroll is outside every
    // window, but it keeps loading for the jump.
    st.update(150, 150, false);
    expect(scroll!.signal.aborted).toBe(false);
    expect(st.status().loading).toContain("scroll");
  });

  it("cancels a load nobody waits for", () => {
    const st = new ChunkStreamer(eight(), () => {});
    st.update(150, 750, false);
    const scroll = loads.find((l) => l.id === "scroll")!;
    st.update(150, 150, false);
    expect(scroll.signal.aborted).toBe(true);
  });

  it("dispose releases waiters and says so", async () => {
    const st = new ChunkStreamer(ctx(), () => {});
    st.update(217, 1647, false);
    const waiting = st.whenReady("summit", 60_000);
    st.dispose();
    await waiting;
    expect(st.isDisposed).toBe(true);
  });

  it("desktops need the area and two each side, phones and smaller Medium machines one, a touch screen on High the area alone", () => {
    const at = (budget: (typeof STREAM_BUDGETS)[keyof typeof STREAM_BUDGETS]) => new ChunkStreamer(eight(), () => {}, budget).update(350, null, false)!.need;
    // At the arena's stop, nearest first (the forge and the mission 50 frames off, the mirror and
    // the library 150), triangles not counted.
    expect(at(STREAM_BUDGETS.full)).toEqual(["arena", "forge", "mission", "mirror", "library"]);
    expect(at(STREAM_BUDGETS.narrow)).toEqual(["arena", "forge", "mission"]);
    expect(at(STREAM_BUDGETS.low)).toEqual(["arena", "forge", "mission"]);
    expect(at(STREAM_BUDGETS.lean)).toEqual(["arena"]);
    // A stop's own area alone for a jump's gathering (the rest comes once it is there).
    expect(new ChunkStreamer(eight(), () => {}, STREAM_BUDGETS.full).needAt(350)).toEqual(["arena"]);
  });

  it("a dropped set is marked so a stale scene list can never draw it again", async () => {
    const st = new ChunkStreamer(eight(), () => {});
    st.update(50, null, false);
    const gate = loads.find((l) => l.id === "gate")!;
    gate.resolve(null);
    await Promise.resolve();
    await Promise.resolve();
    const set = st.list().find((s) => s.id === "gate")!;
    expect(set).toBeDefined();
    st.markReady("gate");
    expect(set.ready).toBe(true);
    // At the scroll, the gate is outside the window: nothing keeps it.
    st.update(750, null, false);
    expect(st.list().some((s) => s.id === "gate")).toBe(false);
    expect(set.dropped).toBe(true);
    expect(set.ready).toBe(false);
    expect(st.takeDisposals()).toContain(set);
  });

  it("loads the window nearest first, one download at a time, then prefetches the next area past it: a desktop even while moving, a phone only at rest", async () => {
    const full = new ChunkStreamer(eight(), () => {}, STREAM_BUDGETS.full);
    full.update(50, null, false);
    // The nearest area has the line to itself...
    expect(loads.map((l) => l.id)).toEqual(["gate"]);
    full.update(50, null, false);
    expect(loads.map((l) => l.id)).toEqual(["gate"]);
    // ...and the next starts once its bytes are in, while it is parsed and prepared.
    arrive("gate");
    full.update(50, null, false);
    expect(loads.map((l) => l.id)).toEqual(["gate", "mirror"]);
    // Two at most.
    arrive("mirror");
    full.update(50, null, false);
    expect(full.status().loading).toEqual(["gate", "mirror"]);
    await settle(full);
    full.update(50, null, false);
    expect(full.status().loading).toEqual(["forge"]);
    await settle(full);
    expect(ids(full)).toEqual(["gate", "mirror", "forge"]);
    // The window is in: the arena starts, mid-flight.
    full.update(50, null, false);
    expect(full.status().loading).toEqual(["arena"]);

    loads.length = 0;
    const low = new ChunkStreamer(eight(), () => {}, STREAM_BUDGETS.low);
    for (let i = 0; i < 2; i++) {
      low.update(50, null, false);
      await settle(low);
    }
    expect(ids(low)).toEqual(["gate", "mirror"]);
    low.update(50, null, false);
    expect(low.status().loading).toEqual([]);
    // At rest the phone fetches the forge into its spare slot.
    low.update(50, null, true);
    expect(low.status().loading).toEqual(["forge"]);
  });

  it("a prefetch downloaded mid-flight waits for a rest (or for its area to be needed) before using the main thread", async () => {
    const full = new ChunkStreamer(eight(), () => {}, STREAM_BUDGETS.full);
    full.update(50, null, false);
    // The needed areas go straight on.
    let needed = false;
    void loads.find((l) => l.id === "gate")!.calm!().then(() => (needed = true));
    await flush();
    expect(needed).toBe(true);
    // The mirror, then the forge, then the arena (the prefetch).
    for (let i = 0; i < 3; i++) {
      await settle(full);
      full.update(50, null, false);
    }
    const arena = loads.find((l) => l.id === "arena")!;
    let calm = false;
    void arena.calm!().then(() => (calm = true));
    await flush();
    expect(calm).toBe(false);
    full.update(55, null, false);
    await flush();
    expect(calm).toBe(false);
    // The camera stops: it may go on.
    full.update(55, null, true);
    await flush();
    expect(calm).toBe(true);
  });

  it("keeps the area and two each side through a flight, with the next one ready ahead, and loads nothing twice at the line between two areas", async () => {
    const st = new ChunkStreamer(eight(), () => {}, STREAM_BUDGETS.full);
    await rest(st, 50);
    expect(ids(st)).toEqual(["gate", "mirror", "forge", "arena"]);
    await rest(st, 150);
    expect(ids(st)).toEqual(EIGHT.slice(0, 5));
    await rest(st, 250);
    expect(ids(st)).toEqual(EIGHT.slice(0, 6));
    // At the arena the gate is three back: it goes, and the steles come ahead.
    await rest(st, 350);
    expect(ids(st)).toEqual(EIGHT.slice(1, 7));
    // To and fro over the line into the mission's stretch (it starts at 401): nothing loads or drops.
    for (const f of [395, 405, 398, 410]) {
      const p = st.update(f, null, false)!;
      expect(p.load).toEqual([]);
      expect(p.drop).toEqual([]);
      expect(loads).toEqual([]);
    }
    await rest(st, 450);
    expect(ids(st)).toEqual(EIGHT.slice(2, 8));
    // Every one drawn at the mission's stop: none is its stand-in.
    expect(st.plan!.draw).toEqual(EIGHT.slice(2, 7));
  });

  it("a touch screen on High keeps the area it is in drawn until the next one is ready", async () => {
    const lean = new ChunkStreamer(three(), () => {}, STREAM_BUDGETS.lean);
    lean.update(93, null, false);
    await settle(lean);
    // Into the mirror's stretch without having rested: the mirror loads, the gate stays meanwhile.
    lean.update(240, null, false);
    expect(lean.status().loading).toEqual(["mirror"]);
    expect(lean.plan!.handover).toEqual(["gate"]);
    expect(ids(lean)).toEqual(["gate"]);
    await settle(lean);
    lean.update(240, null, false);
    expect(ids(lean)).toEqual(["mirror"]);
  });

  it("at either end of the flight the spare slot faces the only way on, whichever way the camera came", async () => {
    const lean = new ChunkStreamer(three(), () => {}, STREAM_BUDGETS.lean);
    // Out to the forge, then Home: the flight back leaves the camera travelling backward.
    for (const f of [93, 217, 352]) {
      lean.update(f, null, false);
      await settle(lean);
    }
    // At the last area the only way on is back: the mirror keeps the spare slot.
    lean.update(352, null, true);
    expect(ids(lean)).toEqual(["mirror", "forge"]);
    for (const f of [352, 250, 150, 93]) {
      lean.update(f, 93, false);
      await settle(lean);
    }
    // Back at the gate nothing lies behind it: the spare slot holds the mirror ahead.
    lean.update(93, null, true);
    await settle(lean);
    lean.update(93, null, true);
    expect(ids(lean)).toEqual(["gate", "mirror"]);
    expect(lean.status().loading).toEqual([]);
  });

  it("after a far jump back a resting phone prefetches the area ahead, and after a step back the one behind", async () => {
    const four = () => {
      const c = three() as unknown as Fixture;
      c.data.manifest.chunks.push({ id: "arena", files: ["arena.glb"], need: [400, 800], tris: 800_000 });
      c.data.camera.holds.push({ id: "arena", frame: 516 });
      return c as unknown as WorldContext;
    };
    const walkOut = async (st: ChunkStreamer) => {
      for (const f of [93, 217, 352, 516]) {
        st.update(f, null, false);
        await settle(st);
      }
    };
    // From the arena back to the mirror (the rail, Places): the visitor reads on from there.
    const lean = new ChunkStreamer(four(), () => {}, STREAM_BUDGETS.lean);
    await walkOut(lean);
    for (const f of [516, 400, 300, 217]) {
      lean.update(f, 217, false);
      await settle(lean);
    }
    lean.update(217, null, true);
    expect(lean.status().loading).toEqual(["forge"]);

    // From the forge to the mirror, one stop back (K): it keeps going the way it went.
    loads.length = 0;
    const step = new ChunkStreamer(four(), () => {}, STREAM_BUDGETS.lean);
    await walkOut(step);
    for (const f of [516, 352]) {
      step.update(f, null, false);
      await settle(step);
    }
    step.update(352, null, true);
    await settle(step);
    for (const f of [352, 300, 250, 217]) {
      step.update(f, 217, false);
      await settle(step);
    }
    step.update(217, null, true);
    expect(step.status().loading).toEqual(["gate"]);

    // K at the arena, K again before the forge is reached (it steps on from the flight's end): two
    // steps back, not one far jump, so the phone still fetches the way the visitor goes.
    loads.length = 0;
    const twice = new ChunkStreamer(four(), () => {}, STREAM_BUDGETS.lean);
    await walkOut(twice);
    for (const [f, t] of [
      [516, 352],
      [470, 352],
      [430, 217],
      [352, 217],
      [300, 217],
      [217, 217],
    ]) {
      twice.update(f, t, false);
      await settle(twice);
    }
    twice.update(217, null, true);
    expect(twice.status().loading).toEqual(["gate"]);
  });

  it("a cancelled jump lets go of its wait, and of a load only it kept going", async () => {
    const st = new ChunkStreamer(eight(), () => {});
    st.update(150, 750, false);
    let current = true;
    let released = false;
    void st.whenReady("scroll", 60_000, () => current).then(() => (released = true));
    st.update(150, 150, false);
    const scroll = loads.find((l) => l.id === "scroll")!;
    expect(scroll.signal.aborted).toBe(false);
    // The visitor scrolls instead: the jump is no longer wanted.
    current = false;
    st.update(150, null, false);
    await flush();
    expect(released).toBe(true);
    expect(scroll.signal.aborted).toBe(true);
  });

  it("retries a failed chunk after 2 s and then 8 s, then lets the stand-in stay until the network is back", async () => {
    vi.useFakeTimers();
    try {
      // The area alone, so the gate is the only load.
      const st = new ChunkStreamer(ctx(), () => {}, STREAM_BUDGETS.lean);
      const fail = async () => {
        for (const l of loads.splice(0)) l.reject(new Error("offline"));
        await flush();
      };
      st.update(93, null, false);
      await fail();
      expect(st.status().failed).toContain("gate");
      expect(st.missingAt(93)).not.toContain("gate");
      st.update(93, null, false);
      expect(loads.map((l) => l.id)).not.toContain("gate");
      vi.advanceTimersByTime(2100);
      st.update(93, null, false);
      expect(loads.map((l) => l.id)).toContain("gate");
      await fail();
      vi.advanceTimersByTime(2100);
      st.update(93, null, false);
      expect(loads.map((l) => l.id)).not.toContain("gate");
      vi.advanceTimersByTime(6000);
      st.update(93, null, false);
      expect(loads.map((l) => l.id)).toContain("gate");
      await fail();
      // Three tries: no more, however long the page stays (the error screen no longer refetches).
      vi.advanceTimersByTime(600_000);
      st.update(93, null, false);
      expect(loads.map((l) => l.id)).not.toContain("gate");
      expect(st.status().failed).toContain("gate");
      // Back online: it tries again.
      (st as unknown as { onOnline: () => void }).onOnline();
      st.update(93, null, false);
      expect(loads.map((l) => l.id)).toContain("gate");
    } finally {
      vi.useRealTimers();
    }
  });

  it("gives every device its window: High and roomy Medium two each side, other Medium and phones one, High on a touch screen the area alone", () => {
    const roomy = { deviceMemory: 8, hardwareConcurrency: 16 };
    const small = { deviceMemory: 4, hardwareConcurrency: 4 };
    expect(streamBudget("high", false, small, false)).toBe(STREAM_BUDGETS.full);
    expect(streamBudget("high", false, roomy, false)).toBe(STREAM_BUDGETS.full);
    expect(streamBudget("mid", false, roomy, false)).toBe(STREAM_BUDGETS.full);
    expect(streamBudget("mid", false, small, false)).toBe(STREAM_BUDGETS.narrow);
    expect(streamBudget("low", false, roomy, false)).toBe(STREAM_BUDGETS.low);
    // Every touch screen, whatever its memory: the 2048 px set and one each side, or the area
    // alone when High keeps the 4096 px set.
    expect(streamBudget("low", true, roomy, false)).toBe(STREAM_BUDGETS.low);
    expect(streamBudget("mid", true, roomy, false)).toBe(STREAM_BUDGETS.low);
    expect(streamBudget("high", true, roomy, false)).toBe(STREAM_BUDGETS.lean);
    expect(STREAM_BUDGETS.full.around).toEqual({ behind: 2, ahead: 2 });
    expect(STREAM_BUDGETS.low.around).toEqual({ behind: 1, ahead: 1 });
    // Phones prefetch at rest into one spare slot; desktops while moving.
    expect(STREAM_BUDGETS.low.spare).toBe(1);
    expect(STREAM_BUDGETS.low.prefetch).toBe("rest");
    expect(STREAM_BUDGETS.lean.prefetch).toBe("rest");
    expect(STREAM_BUDGETS.full.prefetch).toBe("moving");
    expect(STREAM_BUDGETS.narrow.prefetch).toBe("moving");
  });

  it("calls a Medium machine roomy with 8 GB, or 8 cores when the memory is hidden", () => {
    expect(roomyMemory({ deviceMemory: 8, hardwareConcurrency: 4 })).toBe(true);
    // A known small memory wins over many cores.
    expect(roomyMemory({ deviceMemory: 4, hardwareConcurrency: 32 })).toBe(false);
    // Hidden memory (Firefox, Safari): the core count decides.
    expect(roomyMemory({ hardwareConcurrency: 8 })).toBe(true);
    expect(roomyMemory({ hardwareConcurrency: 6 })).toBe(false);
    expect(roomyMemory({})).toBe(false);
  });

  it("fetches nothing ahead with the data saver on", async () => {
    const saver = streamBudget("high", false, { deviceMemory: 8 }, true);
    expect(saver).toEqual({ ...STREAM_BUDGETS.full, prefetch: "off" });
    const st = new ChunkStreamer(eight(), () => {}, streamBudget("mid", false, {}, true));
    await rest(st, 50);
    expect(ids(st)).toEqual(["gate", "mirror"]);
    st.update(50, null, true);
    expect(st.status().loading).toEqual([]);
  });

  it("a new budget applies in place (a live switch between High and Medium on a smaller machine)", async () => {
    const st = new ChunkStreamer(eight(), () => {}, STREAM_BUDGETS.full);
    await rest(st, 350);
    expect(ids(st)).toEqual(EIGHT.slice(1, 7));
    st.setBudget(STREAM_BUDGETS.narrow);
    st.update(350, null, true);
    expect(ids(st)).toEqual(["forge", "arena", "mission", "library"]);
    st.setBudget(STREAM_BUDGETS.full);
    expect(st.update(350, null, true)!.load).toEqual(["mirror"]);
  });

  it("reports the global set's triangles, and plans nothing from them", () => {
    const st = new ChunkStreamer(eight(), () => {});
    const before = st.update(350, null, false)!.need;
    st.setGlobalTris(1_450_000);
    expect(st.status().globalTris).toBe(1_450_000);
    expect(st.update(350, null, false)!.need).toEqual(before);
  });
});

describe("ChunkStreamer.settleAt (fast travel's settled wait)", () => {
  /** Six areas seen from everywhere (wide need ranges), holds 200 frames apart (100, 300, ... 1100). */
  function wide(): WorldContext {
    const c = ctx() as unknown as Fixture;
    c.data.manifest.chunks = ["a", "b", "c", "d", "e", "f"].map((id, i) => ({ id, files: i === 0 ? ["a.glb", "a_trees.glb"] : [`${id}.glb`], need: [1, 1729], tris: 900_000, bytes: 1000 * (i + 1) }));
    c.data.camera.holds = ["a", "b", "c", "d", "e", "f"].map((id, i) => ({ id, frame: 200 * i + 100 }));
    return c as unknown as WorldContext;
  }

  it("waits for the stop's own area and one each side, not for the window's further ones", () => {
    const st = new ChunkStreamer(wide(), () => {});
    const d = st.settleAt(500);
    expect(d.chunks.map((c) => [c.id, c.done, c.expected === true])).toEqual([
      ["b", 0, false],
      ["c", 0, false],
      ["d", 0, false],
    ]);
    expect(d.chunks.map((c) => c.weight)).toEqual([2000, 3000, 4000]);
    expect(d.leaving).toEqual([]);
  });

  it("with the area alone (High on a touch screen), expects the one it will prefetch there, and fetches it while the ink waits", async () => {
    const st = new ChunkStreamer(wide(), () => {}, STREAM_BUDGETS.lean);
    const d = st.settleAt(100);
    expect(d.chunks.map((c) => [c.id, c.expected === true])).toEqual([
      ["a", false],
      ["b", true],
    ]);
    st.update(100, null, true);
    await settle(st);
    // The ink waits for b now: it must start (holding it back kept the ink up for 30 s).
    expect(st.settleAt(100).chunks.map((c) => [c.id, c.done])).toEqual([
      ["a", 1],
      ["b", 0],
    ]);
    st.update(100, null, true);
    expect(loads.map((l) => l.id)).toEqual(["b"]);
  });

  it("follows each area's download, then its upload, and then loads the rest of the window", async () => {
    const st = new ChunkStreamer(wide(), () => {});
    st.update(100, null, true);
    expect(loads.map((l) => l.id)).toEqual(["a"]);
    // Half of the gate's files arrived: 40% (the download is 80% of the way).
    loads[0].onBytes?.("a.glb")(300, 600);
    loads[0].onBytes?.("a_trees.glb")(200, 400);
    expect(st.settleAt(100).chunks[0].done).toBeCloseTo(0.4);
    st.update(100, null, true);
    expect(loads.map((l) => l.id)).toEqual(["a"]);
    // All of them: 80%, and b starts.
    loads[0].onBytes?.("a.glb")(600, 600);
    loads[0].onBytes?.("a_trees.glb")(400, 400);
    expect(st.settleAt(100).chunks[0].done).toBeCloseTo(0.8);
    st.update(100, null, true);
    expect(loads.map((l) => l.id)).toEqual(["a", "b"]);
    for (const l of loads.splice(0)) l.resolve(null);
    await flush();
    // Loaded, still uploading.
    expect(st.settleAt(100).chunks.map((c) => c.done)).toEqual([0.9, 0.9]);
    for (const s of st.list()) st.markReady(s.id);
    const d = st.settleAt(100);
    expect(d.chunks.map((c) => [c.id, c.done])).toEqual([
      ["a", 1],
      ["b", 1],
    ]);
    // The window's third area (two away) waits while the ink still watches the stop...
    st.update(100, null, true);
    expect(loads).toEqual([]);
    // ...and comes once it has let go.
    const now = performance.now();
    const clock = vi.spyOn(performance, "now").mockReturnValue(now + 1000);
    try {
      st.update(100, null, true);
      expect(loads.map((l) => l.id)).toEqual(["c"]);
    } finally {
      clock.mockRestore();
    }
  });

  it("while the ink waits, only the stop's own area and its neighbours load; the rest of the window after", async () => {
    const st = new ChunkStreamer(wide(), () => {});
    st.settleAt(500);
    st.update(500, null, true);
    expect(loads.map((l) => l.id)).toEqual(["c"]);
    arrive("c");
    st.settleAt(500);
    st.update(500, null, true);
    expect(loads.map((l) => l.id)).toEqual(["c", "b"]);
    await settle(st);
    st.settleAt(500);
    st.update(500, null, true);
    expect(loads.map((l) => l.id)).toEqual(["d"]);
    await settle(st);
    st.settleAt(500);
    st.update(500, null, true);
    expect(loads).toEqual([]);
    const now = performance.now();
    const clock = vi.spyOn(performance, "now").mockReturnValue(now + 1000);
    try {
      st.update(500, null, true);
      expect(loads.map((l) => l.id)).toEqual(["a"]);
      arrive("a");
      st.update(500, null, true);
      expect(loads.map((l) => l.id)).toEqual(["a", "e"]);
    } finally {
      clock.mockRestore();
    }
  });

  it("waits for no prefetch with the data saver on (the stand-in stays)", async () => {
    const st = new ChunkStreamer(wide(), () => {}, streamBudget("mid", false, {}, true));
    await rest(st, 100);
    const d = st.settleAt(100);
    expect(d.chunks.map((c) => c.id)).toEqual(["a", "b"]);
    expect(d.chunks.every((c) => c.done === 1)).toBe(true);
  });

  it("names a drawn area the stop does not keep as leaving, and counts a failed one as done", async () => {
    const st = new ChunkStreamer(wide(), () => {});
    // At the last stop (f): its window d, e, f, and c prefetched (the only way on is back). Then
    // fast travel to the first one: c is in its window and stays; d, e and f go.
    await rest(st, 1100);
    expect(ids(st)).toEqual(["c", "d", "e", "f"]);
    const d = st.settleAt(100);
    expect(d.chunks.map((c) => c.id)).toEqual(["a", "b"]);
    expect(d.leaving).toEqual(["d", "e", "f"]);
    // a fails for good: nothing to wait for.
    st.update(100, null, true);
    const a = loads.find((l) => l.id === "a");
    a?.reject(new Error("offline"));
    await flush();
    expect(st.settleAt(100).chunks.find((c) => c.id === "a")?.done).toBe(1);
  });
});

describe("retryDelayMs", () => {
  it("waits 2 s, then 8 s, then gives up", () => {
    expect(retryDelayMs(1)).toBe(2000);
    expect(retryDelayMs(2)).toBe(8000);
    expect(retryDelayMs(3)).toBeNull();
    expect(retryDelayMs(9)).toBeNull();
  });
});

describe("texture memory", () => {
  const tex = (w: number, h: number, mips = true) => {
    const t = new Texture();
    t.image = { width: w, height: h };
    if (!mips) t.minFilter = LinearFilter;
    return t;
  };

  it("counts RGBA8 with a third more for the mip chain", () => {
    expect(textureBytes([tex(4096, 4096)])).toBe(Math.round(4096 * 4096 * 4 * (4 / 3)));
    expect(textureBytes([tex(2048, 1024, false)])).toBe(2048 * 1024 * 4);
    expect(textureBytes([])).toBe(0);
  });

  it("reads the size prepare.ts kept once the image was closed, and assumes a full atlas when it cannot", () => {
    const closed = tex(0, 0, false);
    closed.userData.size = [4096, 1280];
    expect(textureBytes([closed])).toBe(4096 * 1280 * 4);
    const unknown = new Texture();
    unknown.minFilter = LinearFilter;
    expect(textureBytes([unknown])).toBe(4096 * 4096 * 4);
  });

  it("leaves out shared textures (the sky)", () => {
    const sky = tex(1024, 512, false);
    expect(textureBytes([sky, tex(2048, 2048, false)], new Set([sky]))).toBe(2048 * 2048 * 4);
  });

  it("estimates an area before it loads from its download, erring high", () => {
    // The gate: 10.4 MB to download, 228 MB on the GPU.
    expect(estimateTexBytes(10_392_363)).toBeGreaterThan(228_000_000);
    expect(estimateTexBytes(0)).toBeGreaterThan(228_000_000);
  });

  it("uses the texture memory the manifest gives, for the texture set in use", () => {
    const chunk = (extra: Partial<ChunkInfo>): ChunkInfo => ({
      id: "gate",
      files: ["gate.glb.gz"],
      filesLow: ["low/gate.glb.gz"],
      need: [1, 300],
      bytes: 10_000_000,
      bytesLow: 4_000_000,
      tris: 1,
      ...extra,
    });
    // Measured by the packer: taken as is, whatever the download (a smaller repack does not lower it).
    expect(chunkTexBytes(chunk({ texBytes: 228_000_000, texBytesLow: 60_000_000 }), false)).toBe(228_000_000);
    expect(chunkTexBytes(chunk({ texBytes: 228_000_000, texBytesLow: 60_000_000 }), true)).toBe(60_000_000);
    // Not given: the download-based estimate (of the low files on the low tier).
    expect(chunkTexBytes(chunk({}), false)).toBe(estimateTexBytes(10_000_000));
    expect(chunkTexBytes(chunk({ texBytes: 228_000_000 }), true)).toBe(estimateTexBytes(4_000_000));
    // No low files: the full set is what loads, so its figure counts.
    expect(chunkTexBytes(chunk({ filesLow: null, texBytes: 228_000_000 }), true)).toBe(228_000_000);
  });
});
