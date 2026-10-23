import { beforeEach, describe, expect, it, vi } from "vitest";

const loads: {
  id: string;
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
  loadSet: vi.fn((ctx: WorldContext, id: string, need: [number, number], _files: string[], opts: { signal: AbortSignal; calm?: () => Promise<void>; onBytes?: (url: string) => (loaded: number, total: number) => void }) => {
    // The set holds the manifest's triangles and one 4096 px mipmapped atlas (LinearMipmapLinearFilter).
    const tris = ctx.data.manifest.chunks.find((c) => c.id === id)?.tris ?? 0;
    const textures = [{ image: { width: 4096, height: 4096 }, generateMipmaps: true, minFilter: 1008, userData: {} }];
    return new Promise((resolve, reject) => {
      loads.push({
        id,
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
  canRetain,
  chunkTexBytes,
  estimateTexBytes,
  retryDelayMs,
  streamBudget,
  textureBytes,
} from "./streaming";
import type { WorldContext } from "./assets";

vi.stubGlobal("window", globalThis);

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
  const c = ctx() as unknown as {
    data: { manifest: { chunks: unknown[] }; camera: { holds: { id: string; frame: number }[] } };
  };
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

async function flush(): Promise<void> {
  for (let i = 0; i < 6; i++) await Promise.resolve();
}

/** Every load in flight arrives, and (as the render loop would) is uploaded and marked ready. */
async function settle(st: ChunkStreamer): Promise<void> {
  for (const l of loads.splice(0)) l.resolve(null);
  await flush();
  for (const s of st.list()) st.markReady(s.id);
}

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
    const st = new ChunkStreamer(ctx(), () => {});
    // A jump to the summit gathers it...
    st.update(217, 1647, false);
    const summit = loads.find((l) => l.id === "summit");
    expect(summit).toBeDefined();
    void st.whenReady("summit", 5000);
    // ...while the flight still under way plans around the mirror: the summit is outside every
    // window, but it keeps loading for the jump.
    st.update(217, 217, false);
    expect(summit!.signal.aborted).toBe(false);
    expect(st.status().loading).toContain("summit");
  });

  it("cancels a load nobody waits for", () => {
    const st = new ChunkStreamer(ctx(), () => {});
    st.update(217, 1647, false);
    const summit = loads.find((l) => l.id === "summit")!;
    st.update(217, 217, false);
    expect(summit.signal.aborted).toBe(true);
  });

  it("dispose releases waiters and says so", async () => {
    const st = new ChunkStreamer(ctx(), () => {});
    st.update(217, 1647, false);
    const waiting = st.whenReady("summit", 60_000);
    st.dispose();
    await waiting;
    expect(st.isDisposed).toBe(true);
  });

  it("the phone budget keeps only the area the camera is in", () => {
    const full = new ChunkStreamer(ctx(), () => {}, STREAM_BUDGETS.full);
    const low = new ChunkStreamer(ctx(), () => {}, STREAM_BUDGETS.low);
    full.setGlobalTris(700_000);
    low.setGlobalTris(700_000);
    // At frame 200, between the gate and the mirror, both areas are wanted.
    expect(full.update(200, null, false)!.need).toEqual(["mirror", "gate"]);
    expect(low.update(200, null, false)!.need).toEqual(["mirror"]);
  });

  it("a dropped set is marked so a stale scene list can never draw it again", async () => {
    const st = new ChunkStreamer(ctx(), () => {});
    st.update(93, null, false);
    const gate = loads.find((l) => l.id === "gate")!;
    gate.resolve(null);
    await Promise.resolve();
    await Promise.resolve();
    const set = st.list().find((s) => s.id === "gate")!;
    expect(set).toBeDefined();
    st.markReady("gate");
    expect(set.ready).toBe(true);
    // Far from the gate (the summit), nothing keeps it.
    st.update(1647, null, false);
    expect(st.list().some((s) => s.id === "gate")).toBe(false);
    expect(set.dropped).toBe(true);
    expect(set.ready).toBe(false);
    expect(st.takeDisposals()).toContain(set);
  });

  it("prefetches the next area past the budget once the needed ones are ready: a desktop even while moving, a phone only at rest", async () => {
    const full = new ChunkStreamer(three(), () => {}, STREAM_BUDGETS.full);
    full.setGlobalTris(700_000);
    full.update(93, null, false);
    await settle(full);
    expect(full.status().resident.map((r) => r.id)).toEqual(["gate", "mirror"]);
    // The gate and the mirror fill the budget (1.7 of 1.8M); the forge starts anyway, mid-flight.
    full.update(93, null, false);
    expect(full.status().loading).toEqual(["forge"]);

    loads.length = 0;
    const low = new ChunkStreamer(three(), () => {}, STREAM_BUDGETS.low);
    low.setGlobalTris(700_000);
    low.update(93, null, false);
    await settle(low);
    expect(low.status().resident.map((r) => r.id)).toEqual(["gate"]);
    low.update(93, null, false);
    expect(low.status().loading).toEqual([]);
    // At rest the phone fetches the mirror into its spare slot.
    low.update(93, null, true);
    expect(low.status().loading).toEqual(["mirror"]);
  });

  it("a prefetch downloaded mid-flight waits for a rest (or for its area to be needed) before using the main thread", async () => {
    const full = new ChunkStreamer(three(), () => {}, STREAM_BUDGETS.full);
    full.setGlobalTris(700_000);
    full.update(93, null, false);
    // The needed areas go straight on.
    let needed = false;
    void loads.find((l) => l.id === "gate")!.calm!().then(() => (needed = true));
    await flush();
    expect(needed).toBe(true);
    await settle(full);
    full.update(93, null, false);
    const forge = loads.find((l) => l.id === "forge")!;
    let calm = false;
    void forge.calm!().then(() => (calm = true));
    await flush();
    expect(calm).toBe(false);
    full.update(95, null, false);
    await flush();
    expect(calm).toBe(false);
    // The camera stops: it may go on.
    full.update(95, null, true);
    await flush();
    expect(calm).toBe(true);
  });

  it("a phone keeps the area it is in drawn until the next one is ready", async () => {
    const low = new ChunkStreamer(three(), () => {}, STREAM_BUDGETS.low);
    low.setGlobalTris(700_000);
    low.update(93, null, false);
    await settle(low);
    // Into the mirror's stretch without having rested: the mirror loads, the gate stays meanwhile.
    low.update(240, null, false);
    expect(low.status().loading).toEqual(["mirror"]);
    expect(low.plan!.handover).toEqual(["gate"]);
    expect(low.status().resident.map((r) => r.id)).toEqual(["gate"]);
    await settle(low);
    low.update(240, null, false);
    expect(low.status().resident.map((r) => r.id)).toEqual(["mirror"]);
  });

  it("at either end of the flight a phone prefetches the only way on, whichever way it came", async () => {
    const low = new ChunkStreamer(three(), () => {}, STREAM_BUDGETS.low);
    low.setGlobalTris(700_000);
    // Out to the forge, then Home: the flight back leaves the camera travelling backward.
    for (const f of [93, 217, 352]) {
      low.update(f, null, false);
      await settle(low);
    }
    // At the last area the only way on is back: the mirror keeps the spare slot.
    low.update(352, null, true);
    expect(low.status().resident.map((r) => r.id)).toEqual(["mirror", "forge"]);
    for (const f of [352, 250, 150, 93]) {
      low.update(f, 93, false);
      await settle(low);
    }
    expect(low.status().resident.map((r) => r.id)).toEqual(["gate"]);
    // Resting at the gate, nothing lies behind it: the mirror is fetched into the spare slot.
    low.update(93, null, true);
    expect(low.status().loading).toEqual(["mirror"]);
    await settle(low);
    low.update(93, null, true);
    expect(low.status().resident.map((r) => r.id)).toEqual(["gate", "mirror"]);
  });

  it("after a far jump back a resting phone prefetches the area ahead, and after a step back the one behind", async () => {
    const four = () => {
      const c = three() as unknown as { data: { manifest: { chunks: unknown[] }; camera: { holds: { id: string; frame: number }[] } } };
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
    const low = new ChunkStreamer(four(), () => {}, STREAM_BUDGETS.low);
    low.setGlobalTris(700_000);
    await walkOut(low);
    for (const f of [516, 400, 300, 217]) {
      low.update(f, 217, false);
      await settle(low);
    }
    low.update(217, null, true);
    expect(low.status().loading).toEqual(["forge"]);

    // From the forge to the mirror, one stop back (K): it keeps going the way it went.
    loads.length = 0;
    const step = new ChunkStreamer(four(), () => {}, STREAM_BUDGETS.low);
    step.setGlobalTris(700_000);
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
    const twice = new ChunkStreamer(four(), () => {}, STREAM_BUDGETS.low);
    twice.setGlobalTris(700_000);
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
    const st = new ChunkStreamer(ctx(), () => {});
    st.update(217, 1647, false);
    let current = true;
    let released = false;
    void st.whenReady("summit", 60_000, () => current).then(() => (released = true));
    st.update(217, 217, false);
    const summit = loads.find((l) => l.id === "summit")!;
    expect(summit.signal.aborted).toBe(false);
    // The visitor scrolls instead: the jump is no longer wanted.
    current = false;
    st.update(217, null, false);
    await flush();
    expect(released).toBe(true);
    expect(summit.signal.aborted).toBe(true);
  });

  it("retries a failed chunk after 2 s and then 8 s, then lets the stand-in stay until the network is back", async () => {
    vi.useFakeTimers();
    try {
      const st = new ChunkStreamer(ctx(), () => {});
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

  it("every touch screen gets the one-area budget, whatever its tier", () => {
    // Even with all the memory in the world: only the high tier with a mouse retains.
    const roomy = { deviceMemory: 8, hardwareConcurrency: 16 };
    expect(streamBudget("low", false, roomy, false)).toBe(STREAM_BUDGETS.low);
    expect(streamBudget("mid", true, roomy, false)).toBe(STREAM_BUDGETS.low);
    expect(streamBudget("high", true, roomy, false)).toBe(STREAM_BUDGETS.low);
    expect(streamBudget("mid", false, roomy, false)).toBe(STREAM_BUDGETS.full);
    expect(streamBudget("high", false, { deviceMemory: 4 }, false)).toBe(STREAM_BUDGETS.full);
    // Phones prefetch at rest into one spare slot; desktops while moving.
    expect(STREAM_BUDGETS.low.spare).toBe(1);
    expect(STREAM_BUDGETS.low.prefetch).toBe("rest");
    expect(STREAM_BUDGETS.full.prefetch).toBe("moving");
  });

  it("fetches nothing ahead with the data saver on", async () => {
    const saver = streamBudget("high", false, { deviceMemory: 8 }, true);
    expect(saver).toEqual({ ...STREAM_BUDGETS.retain, prefetch: "off" });
    const st = new ChunkStreamer(three(), () => {}, streamBudget("mid", false, {}, true));
    st.setGlobalTris(700_000);
    st.update(93, null, false);
    await settle(st);
    st.update(93, null, true);
    expect(st.status().loading).toEqual([]);
  });

  it("keeps passed areas only on a high-tier desktop with 8 GB, or 8 cores when the memory is hidden", () => {
    expect(streamBudget("high", false, { deviceMemory: 8 })).toBe(STREAM_BUDGETS.retain);
    expect(canRetain("high", false, { deviceMemory: 8, hardwareConcurrency: 4 })).toBe(true);
    // A known small memory wins over many cores.
    expect(canRetain("high", false, { deviceMemory: 4, hardwareConcurrency: 32 })).toBe(false);
    // Hidden memory (Firefox): the core count decides.
    expect(canRetain("high", false, { hardwareConcurrency: 8 })).toBe(true);
    expect(canRetain("high", false, { hardwareConcurrency: 6 })).toBe(false);
    expect(canRetain("high", false, {})).toBe(false);
    expect(canRetain("mid", false, { deviceMemory: 8 })).toBe(false);
    expect(canRetain("high", true, { deviceMemory: 8 })).toBe(false);
    // Phones, tablets and the mid tier keep their budgets unchanged (no residency budget).
    expect(STREAM_BUDGETS.low.retainTris).toBe(0);
    expect(STREAM_BUDGETS.full.retainTris).toBe(0);
    expect({ ...STREAM_BUDGETS.retain, retainTris: 0, retainTexBytes: 0 }).toEqual(STREAM_BUDGETS.full);
  });
});

describe("ChunkStreamer.settleAt (fast travel's settled wait)", () => {
  /** A stop whose view reaches three areas (wide need ranges, as the full flight's), and one beyond. */
  function wide(): WorldContext {
    const c = ctx() as unknown as {
      data: { manifest: { chunks: unknown[] }; camera: { holds: { id: string; frame: number }[] } };
    };
    c.data.manifest.chunks = [
      { id: "a", files: ["a.glb", "a_trees.glb"], need: [1, 600], tris: 1_000_000, bytes: 1000 },
      { id: "b", files: ["b.glb"], need: [1, 800], tris: 900_000, bytes: 3000 },
      { id: "c", files: ["c.glb"], need: [1, 1000], tris: 800_000, bytes: 2000 },
      { id: "d", files: ["d.glb"], need: [500, 1200], tris: 800_000, bytes: 2000 },
    ];
    c.data.camera.holds = [
      { id: "a", frame: 100 },
      { id: "b", frame: 300 },
      { id: "c", frame: 500 },
      { id: "d", frame: 700 },
    ];
    return c as unknown as WorldContext;
  }

  it("wants the areas the stop draws, and expects the one it will prefetch there", () => {
    const st = new ChunkStreamer(wide(), () => {});
    const d = st.settleAt(100);
    expect(d.chunks.map((c) => [c.id, c.done, c.expected === true])).toEqual([
      ["a", 0, false],
      ["b", 0, false],
      ["c", 0, true],
    ]);
    expect(d.chunks.map((c) => c.weight)).toEqual([1000, 3000, 2000]);
    expect(d.leaving).toEqual([]);
  });

  it("follows each area's download, then its upload, and wants the prefetch once they are in", async () => {
    const st = new ChunkStreamer(wide(), () => {});
    st.update(100, null, true);
    expect(loads.map((l) => l.id)).toEqual(["a", "b"]);
    // Half of the gate's files arrived: 40% (the download is 80% of the way).
    loads[0].onBytes?.("a.glb")(300, 600);
    loads[0].onBytes?.("a_trees.glb")(200, 400);
    expect(st.settleAt(100).chunks[0].done).toBeCloseTo(0.4);
    for (const l of loads.splice(0)) l.resolve(null);
    await flush();
    // Loaded, still uploading.
    expect(st.settleAt(100).chunks.slice(0, 2).map((c) => c.done)).toEqual([0.9, 0.9]);
    for (const s of st.list()) st.markReady(s.id);
    const d = st.settleAt(100);
    expect(d.chunks.map((c) => [c.id, c.done, c.expected === true])).toEqual([
      ["a", 1, false],
      ["b", 1, false],
      ["c", 0, false],
    ]);
    // The prefetch it waits for is the one the streamer then starts.
    st.update(100, null, true);
    expect(loads.map((l) => l.id)).toEqual(["c"]);
  });

  it("waits for no prefetch with the data saver on (the stand-in stays)", async () => {
    const st = new ChunkStreamer(wide(), () => {}, streamBudget("mid", false, {}, true));
    st.update(100, null, true);
    await settle(st);
    const d = st.settleAt(100);
    expect(d.chunks.map((c) => c.id)).toEqual(["a", "b"]);
    expect(d.chunks.every((c) => c.done === 1)).toBe(true);
  });

  it("names a drawn area the stop does not keep as leaving, and counts a failed one as done", async () => {
    const st = new ChunkStreamer(wide(), () => {});
    // At the stop c, then a jump back to a on the phone budget: there it keeps a and, in its spare
    // slot, b (both drawn at a's frame), but not c, drawn there now.
    st.update(500, null, true);
    await settle(st);
    expect(st.list().map((s) => s.id)).toEqual(["b", "c"]);
    st.setBudget(STREAM_BUDGETS.low);
    const d = st.settleAt(100);
    expect(d.chunks.map((c) => c.id)).toEqual(["a", "b"]);
    expect(d.leaving).toEqual(["c"]);
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

describe("ChunkStreamer retaining passed areas", () => {
  // Four areas in a row with narrow need ranges: well into the arena, the gate is outside every window.
  const row = () => {
    const c = ctx() as unknown as {
      data: { manifest: { chunks: unknown[] }; camera: { holds: { id: string; frame: number }[] } };
    };
    c.data.manifest.chunks = [
      { id: "gate", files: ["gate.glb"], need: [1, 190], bytes: 10_000_000, tris: 1_000_000 },
      { id: "mirror", files: ["mirror.glb"], need: [140, 320], bytes: 7_000_000, tris: 700_000 },
      { id: "forge", files: ["forge.glb"], need: [270, 520], bytes: 8_000_000, tris: 900_000 },
      { id: "arena", files: ["arena.glb"], need: [480, 630], bytes: 8_000_000, tris: 600_000 },
    ];
    c.data.camera.holds = [
      { id: "gate", frame: 93 },
      { id: "mirror", frame: 217 },
      { id: "forge", frame: 352 },
      { id: "arena", frame: 560 },
    ];
    return c as unknown as WorldContext;
  };
  const settle = async (st: ChunkStreamer) => {
    for (const l of [...loads]) l.resolve(null);
    for (let i = 0; i < 4; i++) await Promise.resolve();
    // Uploaded (the render loop marks them ready): only then is the next area prefetched.
    for (const s of st.list()) st.markReady(s.id);
  };
  /** Flies forward through every hold, resting at each (so the next area is prefetched). */
  const fly = async (st: ChunkStreamer, frames: number[]) => {
    for (const f of frames) {
      st.update(f, null, false);
      await settle(st);
      st.update(f, null, true);
      await settle(st);
    }
  };
  const ids = (st: ChunkStreamer) => st.status().resident.map((r) => r.id);

  it("the plain desktop budget drops the gate once passed; a roomy desktop keeps it, measured", async () => {
    const plain = new ChunkStreamer(row(), () => {}, STREAM_BUDGETS.full);
    plain.setGlobalTris(700_000);
    await fly(plain, [93, 217, 352, 560]);
    expect(ids(plain)).not.toContain("gate");

    loads.length = 0;
    const roomy = new ChunkStreamer(row(), () => {}, STREAM_BUDGETS.retain);
    roomy.setGlobalTris(700_000);
    await fly(roomy, [93, 217, 352, 560]);
    // All four (3.2 M triangles, 4 x 89 MB of textures) fit the residency budget.
    expect(ids(roomy)).toEqual(["gate", "mirror", "forge", "arena"]);
    const gate = roomy.status().resident.find((r) => r.id === "gate")!;
    expect(gate.retained).toBe(true);
    expect(gate.texBytes).toBe(Math.round(4096 * 4096 * 4 * (4 / 3)));
    expect(roomy.plan!.retain).toContain("gate");
    // Scrolling back to the gate is instant: nothing loads.
    const before = loads.length;
    roomy.update(93, null, false);
    expect(loads.length).toBe(before);
    // Back at the first area the plan faces forward again (nothing lies behind it), as on opening.
    expect(roomy.plan!.need).toEqual(["gate", "mirror"]);
    expect(roomy.plan!.load).toEqual([]);
    expect(roomy.plan!.drop).toEqual([]);
  });

  it("evicts the farthest passed area first when the budget is full", async () => {
    // Room for three areas' textures (3 x 89 MB): at the arena, the arena and forge are the usual
    // plan, the mirror (nearest passed) stays and the gate (farthest) goes.
    const tight = new ChunkStreamer(row(), () => {}, { ...STREAM_BUDGETS.retain, retainTexBytes: 3 * 90_000_000 });
    tight.setGlobalTris(700_000);
    await fly(tight, [93, 217, 352, 560]);
    expect(ids(tight)).toEqual(["mirror", "forge", "arena"]);
    expect(tight.takeDisposals().map((s) => s.id)).toContain("gate");
  });

  it("a new budget applies in place (a live switch between Medium and High)", async () => {
    const st = new ChunkStreamer(row(), () => {}, STREAM_BUDGETS.full);
    st.setGlobalTris(700_000);
    st.setBudget(STREAM_BUDGETS.retain);
    await fly(st, [93, 217, 352, 560]);
    expect(st.plan!.retain).toContain("gate");
    expect(ids(st)).toContain("gate");
    // Back to the plain budget: the passed areas go at the next update.
    st.setBudget(STREAM_BUDGETS.full);
    st.update(560, null, false);
    expect(st.plan!.retain).toEqual([]);
    expect(ids(st)).not.toContain("gate");
  });

  it("a new budget still counts the global set's triangles", () => {
    // Three small areas wanted at once at frame 260: 1.5 M triangles.
    const small = () => {
      const c = ctx() as unknown as {
        data: { manifest: { chunks: unknown[] }; camera: { holds: { id: string; frame: number }[] } };
      };
      c.data.manifest.chunks = [
        { id: "gate", files: ["gate.glb"], need: [1, 300], tris: 500_000 },
        { id: "mirror", files: ["mirror.glb"], need: [100, 500], tris: 500_000 },
        { id: "forge", files: ["forge.glb"], need: [250, 700], tris: 500_000 },
      ];
      c.data.camera.holds = [
        { id: "gate", frame: 93 },
        { id: "mirror", frame: 217 },
        { id: "forge", frame: 352 },
      ];
      return c as unknown as WorldContext;
    };
    // Without the global set all three fit 2.5 M; with its 1.2 M only two do.
    expect(new ChunkStreamer(small(), () => {}, STREAM_BUDGETS.full).update(260, null, false)!.need).toHaveLength(3);
    const st = new ChunkStreamer(small(), () => {}, STREAM_BUDGETS.low);
    st.setGlobalTris(1_200_000);
    st.setBudget(STREAM_BUDGETS.full);
    expect(st.update(260, null, false)!.need).toHaveLength(2);
  });
});
