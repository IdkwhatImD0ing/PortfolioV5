import { describe, expect, it } from "vitest";
import type { ChunkSpan, PlanWindow } from "./chunks";
import { chunkDone, destinationChunks, SETTLE, SettleWatch, type SettleSnapshot } from "./settle";

// A stop at frame 100 whose view reaches three areas (need ranges are wide: an area is seen from far).
const CHUNKS: ChunkSpan[] = [
  { id: "gate", need: [1, 400], core: [1, 150], tris: 1000 },
  { id: "mirror", need: [1, 500], core: [150, 300], tris: 1000 },
  { id: "forge", need: [60, 700], core: [300, 500], tris: 1000 },
  { id: "arena", need: [350, 900], core: [500, 700], tris: 1000 },
];
// Two areas within the budget, one spare slot ahead (the desktop budget's shape).
const WINDOW: Partial<PlanWindow> = { triBudget: 2000, minResident: 2, spare: 1 };
const set = (...ids: string[]) => new Set(ids);
const none = set();

describe("destinationChunks", () => {
  it("wants the areas the stop draws, before any of them has loaded", () => {
    const d = destinationChunks({ chunks: CHUNKS, frame: 100, direction: 1, resident: none, loading: none, ready: none, window: WINDOW }, true);
    expect(d.want).toEqual(["gate", "mirror"]);
    expect(d.leaving).toEqual([]);
  });

  it("adds the prefetch once the needed areas are in, when it is drawn there and the budget fetches ahead", () => {
    const input = { chunks: CHUNKS, frame: 100, direction: 1, resident: set("gate", "mirror"), loading: none, ready: set("gate", "mirror"), window: WINDOW };
    expect(destinationChunks(input, true).want).toEqual(["gate", "mirror", "forge"]);
    // The data saver fetches nothing ahead: the forge's stand-in stays, so nothing waits for it.
    expect(destinationChunks(input, false).want).toEqual(["gate", "mirror"]);
    // Before its need range starts, the prefetched area is not drawn at the stop either.
    const early = destinationChunks({ ...input, frame: 30 }, true);
    expect(early.want).toEqual(["gate", "mirror"]);
  });

  it("still wants the prefetch while it loads (the plan keeps it, though it is no longer the prefetch)", () => {
    const d = destinationChunks(
      { chunks: CHUNKS, frame: 100, direction: 1, resident: set("gate", "mirror"), loading: set("forge"), ready: set("gate", "mirror"), window: WINDOW },
      true,
    );
    expect(d.want).toEqual(["gate", "mirror", "forge"]);
    // A load the plan cancels (no slot for it at this stop) is not waited for.
    const cancelled = destinationChunks(
      {
        chunks: CHUNKS,
        frame: 100,
        direction: 1,
        resident: set("gate", "mirror"),
        loading: set("forge"),
        ready: set("gate", "mirror"),
        window: { ...WINDOW, maxResident: 2 },
      },
      true,
    );
    expect(cancelled.want).toEqual(["gate", "mirror"]);
  });

  it("names drawn areas the plan drops, and areas kept only to hand over, as leaving", () => {
    const cap = { ...WINDOW, maxResident: 2 };
    const dropped = destinationChunks(
      { chunks: CHUNKS, frame: 100, direction: 1, resident: set("gate", "mirror", "forge"), loading: none, ready: set("gate", "mirror", "forge"), window: cap },
      true,
    );
    expect(dropped.want).toEqual(["gate", "mirror"]);
    expect(dropped.leaving).toEqual(["forge"]);
    // The forge is drawn while the gate and the mirror load (handover), and goes once they are in.
    const handing = destinationChunks(
      { chunks: CHUNKS, frame: 100, direction: 1, resident: set("forge"), loading: set("gate", "mirror"), ready: set("forge"), window: cap },
      true,
    );
    expect(handing.want).toEqual(["gate", "mirror"]);
    expect(handing.leaving).toEqual(["forge"]);
  });

  it("never names an area that is not drawn at the stop, nor one still uploading, as leaving", () => {
    const d = destinationChunks(
      { chunks: CHUNKS, frame: 100, direction: 1, resident: set("gate", "mirror", "arena"), loading: none, ready: set("gate", "arena"), window: WINDOW },
      true,
    );
    expect(d.leaving).toEqual([]);
    expect(d.want).toEqual(["gate", "mirror"]);
  });
});

describe("chunkDone", () => {
  it("is mostly the download, then the preparing and upload, and 1 once ready or given up", () => {
    expect(chunkDone({ done: false, resident: false, received: 0, total: 1000 })).toBe(0);
    expect(chunkDone({ done: false, resident: false, received: 500, total: 1000 })).toBeCloseTo(SETTLE.download / 2);
    expect(chunkDone({ done: false, resident: false, received: 2000, total: 1000 })).toBe(SETTLE.download);
    expect(chunkDone({ done: false, resident: false, received: 10, total: 0 })).toBe(0);
    expect(chunkDone({ done: false, resident: true, received: 0, total: 0 })).toBe(SETTLE.uploading);
    expect(chunkDone({ done: true, resident: false, received: 0, total: 0 })).toBe(1);
  });
});

describe("SettleWatch", () => {
  const snap = (over: Partial<SettleSnapshot>): SettleSnapshot => ({
    now: 0,
    frames: 0,
    chunks: [],
    leaving: 0,
    busy: [],
    gpu: "10:5:30",
    view: "93|0|0",
    ...over,
  });

  it("waits for every chunk, then for the frames to hold still", () => {
    const w = new SettleWatch();
    let s = w.push(snap({ chunks: [{ id: "gate", done: 0.4, weight: 10 }] }));
    expect(s.settled).toBe(false);
    expect(s.waiting).toEqual(["gate"]);
    s = w.push(snap({ now: 100, frames: 3, chunks: [{ id: "gate", done: 1, weight: 10 }] }));
    expect(s.settled).toBe(false);
    expect(s.waiting).toEqual(["still"]);
    // Enough frames but not yet long enough, then both.
    s = w.push(snap({ now: 300, frames: 3 + SETTLE.stableFrames, chunks: [{ id: "gate", done: 1, weight: 10 }] }));
    expect(s.settled).toBe(false);
    s = w.push(snap({ now: 100 + SETTLE.stableMs, frames: 3 + SETTLE.stableFrames, chunks: [{ id: "gate", done: 1, weight: 10 }] }));
    expect(s.settled).toBe(true);
    expect(s.progress).toBe(1);
  });

  it("starts the still count again on an upload, a compile or a turn of the view", () => {
    const w = new SettleWatch();
    w.push(snap({ now: 0, frames: 0 }));
    // A texture upload at frame 6.
    expect(w.push(snap({ now: 200, frames: 6, gpu: "10:6:30" })).settled).toBe(false);
    expect(w.push(snap({ now: 450, frames: 12, gpu: "10:6:30" })).settled).toBe(false);
    // The view turns (a phone's turn toward the stop's items).
    expect(w.push(snap({ now: 700, frames: 20, gpu: "10:6:30", view: "93|0.1|0" })).settled).toBe(false);
    expect(w.push(snap({ now: 1000, frames: 26, gpu: "10:6:30", view: "93|0.1|0" })).settled).toBe(false);
    expect(w.push(snap({ now: 1100, frames: 28, gpu: "10:6:30", view: "93|0.1|0" })).settled).toBe(true);
  });

  it("does not settle while a piece is filling in or an area is still to leave", () => {
    const w = new SettleWatch();
    expect(w.push(snap({ busy: ["grass"] })).waiting).toEqual(["grass"]);
    expect(w.push(snap({ now: 2000, frames: 100, busy: ["grass", "reflection"] })).settled).toBe(false);
    expect(w.push(snap({ now: 3000, frames: 200, leaving: 1 })).waiting).toEqual(["leaving"]);
    expect(w.push(snap({ now: 4000, frames: 300 })).settled).toBe(false);
    expect(w.push(snap({ now: 4000 + SETTLE.stableMs, frames: 300 + SETTLE.stableFrames })).settled).toBe(true);
  });

  it("counts the area expected next in its progress without waiting for it, and never goes back", () => {
    const w = new SettleWatch();
    const gate = { id: "gate", done: 0.5, weight: 10 };
    const forge = { id: "forge", done: 0, weight: 10, expected: true };
    const a = w.push(snap({ chunks: [gate, forge] }));
    expect(a.waiting).toEqual(["gate"]);
    expect(a.progress).toBeCloseTo(0.25 * SETTLE.share.chunks);
    // The gate is in and the forge expected: nothing blocks, but the progress waits for the forge.
    const b = w.push(snap({ now: 50, frames: 2, chunks: [{ ...gate, done: 1 }, forge] }));
    expect(b.waiting).toEqual(["still"]);
    expect(b.progress).toBeCloseTo(0.5 * SETTLE.share.chunks);
    // A chunk that joins late only holds the progress where it was.
    const c = w.push(snap({ now: 100, frames: 4, chunks: [{ ...gate, done: 1 }, { ...forge, expected: false }, { id: "arena", done: 0, weight: 40 }] }));
    expect(c.progress).toBe(b.progress);
    const d = w.push(snap({ now: 150, frames: 6, chunks: [{ ...gate, done: 1 }, { ...forge, done: 1, expected: false }, { id: "arena", done: 0.9, weight: 40 }] }));
    expect(d.progress).toBeGreaterThan(c.progress);
    expect(d.progress).toBeLessThan(1);
  });

  it("settles a destination with nothing to load once the frames hold still", () => {
    const w = new SettleWatch();
    expect(w.push(snap({})).settled).toBe(false);
    expect(w.push(snap({ now: SETTLE.stableMs, frames: SETTLE.stableFrames })).settled).toBe(true);
  });
});
