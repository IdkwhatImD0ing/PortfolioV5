import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import type { ChunkSpan, PlanWindow } from "./chunks";
import { LIVE_LOOK } from "./live";
import { chunkArriving, chunkDone, destinationChunks, detailHolds, SETTLE, SETTLE_GATE, SettleWatch, type SettleSnapshot } from "./settle";

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

  it("with the window around the stop, waits for its own area and one each side; the ones further out come after", () => {
    // Six areas seen from everywhere; the stop is the third one's (index 2), two each side kept.
    const row: ChunkSpan[] = ["a", "b", "c", "d", "e", "f"].map((id, i) => ({ id, need: [1, 1200], core: [200 * i, 200 * i + 199] }));
    const window: Partial<PlanWindow> = { around: { behind: 2, ahead: 2 }, spare: 1 };
    const at = (resident: Set<string>, ready = resident) =>
      destinationChunks({ chunks: row, frame: 500, direction: 1, resident, loading: none, ready, window }, true, SETTLE.around);
    expect(at(none).want).toEqual(["b", "c", "d"]);
    // All five in (and the spare): the same three; a and e, drawn there, are neither waited for nor leaving.
    const all = set("a", "b", "c", "d", "e", "f");
    expect(at(all)).toEqual({ want: ["b", "c", "d"], leaving: [] });
    // Without the limit every area the stop draws is waited for.
    expect(destinationChunks({ chunks: row, frame: 500, direction: 1, resident: all, loading: none, ready: all, window }, true).want).toEqual(["a", "b", "c", "d", "e", "f"]);
    // An area the plan drops there is still leaving, however far out.
    const far = destinationChunks({ chunks: [...row, { id: "g", need: [1, 1200], core: [1200, 1399] }], frame: 500, direction: 1, resident: set("c", "g"), loading: none, ready: set("c", "g"), window }, true, 1);
    expect(far.leaving).toEqual(["g"]);
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

describe("detailHolds", () => {
  it("holds fast travel's ink until the detail texture has faded in", () => {
    expect(detailHolds("arriving", false)).toBe(true);
    expect(detailHolds("decoding", false)).toBe(true);
    expect(detailHolds("fading", false)).toBe(true);
    expect(detailHolds("none", false)).toBe(false);
  });

  it("holds the loading screen's wait for its download (a piece still arriving) and its decoding, not for its fade", () => {
    expect(detailHolds("arriving", true)).toBe(true);
    expect(detailHolds("decoding", true)).toBe(true);
    expect(detailHolds("fading", true)).toBe(false);
    expect(detailHolds("none", true)).toBe(false);
  });
});

describe("chunkArriving", () => {
  it("is a chunk whose bytes are still on the way: not loaded, or a file still downloading", () => {
    // Not started, or downloading.
    expect(chunkArriving({ done: false, resident: false, fetched: false })).toBe(true);
    expect(chunkArriving({ done: false, resident: false })).toBe(true);
    // Every file here, being parsed and prepared: work on what has arrived.
    expect(chunkArriving({ done: false, resident: false, fetched: true })).toBe(false);
    // Prepared and uploading, or drawn (or given up on).
    expect(chunkArriving({ done: false, resident: true, fetched: false })).toBe(false);
    expect(chunkArriving({ done: true, resident: false, fetched: false })).toBe(false);
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

  it("counts a shorter still for the loading screen's wait for the first stop (SETTLE_GATE)", () => {
    expect(SETTLE_GATE.stableMs).toBeLessThan(SETTLE.stableMs);
    expect(SETTLE_GATE.stableFrames).toBe(SETTLE.stableFrames);
    const gate = new SettleWatch(SETTLE_GATE);
    const ink = new SettleWatch();
    gate.push(snap({}));
    ink.push(snap({}));
    const at = snap({ now: SETTLE_GATE.stableMs, frames: SETTLE_GATE.stableFrames });
    expect(gate.push(at).settled).toBe(true);
    expect(ink.push(at).settled).toBe(false);
    // An upload still starts it again.
    const g2 = new SettleWatch(SETTLE_GATE);
    g2.push(snap({}));
    expect(g2.push(snap({ now: SETTLE_GATE.stableMs, frames: SETTLE_GATE.stableFrames, gpu: "10:6:30" })).settled).toBe(false);
  });

  it("settles a destination with nothing to load once the frames hold still", () => {
    const w = new SettleWatch();
    expect(w.push(snap({})).settled).toBe(false);
    expect(w.push(snap({ now: SETTLE.stableMs, frames: SETTLE.stableFrames })).settled).toBe(true);
  });

  describe("late pieces (live light coming in at the place)", () => {
    const WAIT = LIVE_LOOK.handover.inkWaitMs;
    const live = { late: ["live"], lateMs: WAIT };
    /** When the watch with no late piece first settles. */
    const T = SETTLE.stableMs;
    const F = SETTLE.stableFrames;

    it("hold nothing back while the rest comes in, and are not named until it has", () => {
      const w = new SettleWatch();
      expect(w.push(snap({ chunks: [{ id: "gate", done: 0.5, weight: 10 }], ...live })).waiting).toEqual(["gate"]);
      // Everything in: the still count runs as before (and the page's one unculled frame still sees ["still"]).
      expect(w.push(snap({ now: 10, frames: 1, ...live })).waiting).toEqual(["still"]);
    });

    it("hold the ink past settled until they are done", () => {
      const w = new SettleWatch();
      w.push(snap({ ...live }));
      const s = w.push(snap({ now: T, frames: F, ...live }));
      expect(s.settled).toBe(false);
      expect(s.waiting).toEqual(["live"]);
      expect(s.progress).toBeLessThan(1);
      expect(w.push(snap({ now: T + 300, frames: F + 10, ...live })).settled).toBe(false);
      // Lit: settled at once (the frames have held still all along).
      expect(w.push(snap({ now: T + 320, frames: F + 11, late: [], lateMs: WAIT })).settled).toBe(true);
    });

    it("wait for the frames to hold still again after their own uploads", () => {
      const w = new SettleWatch();
      w.push(snap({ ...live }));
      w.push(snap({ now: T, frames: F, ...live }));
      // Its maps reach the GPU: the counts change, then it is lit.
      const up = w.push(snap({ now: T + 200, frames: F + 5, gpu: "10:11:31", late: [], lateMs: WAIT }));
      expect(up.settled).toBe(false);
      expect(up.waiting).toEqual(["still"]);
      expect(w.push(snap({ now: T + 200 + SETTLE.stableMs, frames: F + 5 + SETTLE.stableFrames, gpu: "10:11:31", late: [], lateMs: WAIT })).settled).toBe(true);
    });

    it("never hold it longer than lateMs past when it would have cleared", () => {
      const w = new SettleWatch();
      w.push(snap({ ...live }));
      w.push(snap({ now: T, frames: F, ...live }));
      expect(w.push(snap({ now: T + WAIT - 1, frames: F + 100, gpu: "10:12:31", ...live })).settled).toBe(false);
      // Still busy, and the counts still changing: let go all the same.
      const s = w.push(snap({ now: T + WAIT, frames: F + 101, gpu: "10:13:31", ...live }));
      expect(s.settled).toBe(true);
      expect(s.progress).toBe(1);
    });

    it("hold nothing without a wait, and nothing once done", () => {
      const a = new SettleWatch();
      a.push(snap({ late: ["live"] }));
      expect(a.push(snap({ now: T, frames: F, late: ["live"] })).settled).toBe(true);
      const b = new SettleWatch();
      b.push(snap({ late: [], lateMs: WAIT }));
      expect(b.push(snap({ now: T, frames: F, late: [], lateMs: WAIT })).settled).toBe(true);
    });
  });

  describe("pieces whose bytes are still on the way (the loading screen's wait, SETTLE_GATE)", () => {
    const A = SETTLE_GATE.arrivingMs;
    const G = SETTLE_GATE.stableMs;
    const F = SETTLE_GATE.stableFrames;
    const mirror = { id: "mirror", done: 0.3, weight: 10 };

    it("hold it for arrivingMs from when it first saw them, then no longer", () => {
      expect(A).toBeGreaterThan(0);
      expect(A).toBeLessThan(1000);
      const w = new SettleWatch(SETTLE_GATE);
      let s = w.push(snap({ now: 1000, chunks: [mirror], arriving: ["mirror"] }));
      expect(s.waiting).toEqual(["mirror"]);
      expect(s.away).toEqual([]);
      s = w.push(snap({ now: 1000 + A - 1, frames: 10, chunks: [mirror], arriving: ["mirror"] }));
      expect(s.waiting).toEqual(["mirror"]);
      const before = s.progress;
      // Let go: the still count starts from here, and the area still counts toward the progress.
      s = w.push(snap({ now: 1000 + A, frames: 11, chunks: [mirror], arriving: ["mirror"] }));
      expect(s.waiting).toEqual(["still"]);
      expect(s.away).toEqual(["mirror"]);
      expect(s.settled).toBe(false);
      expect(s.progress).toBeGreaterThanOrEqual(before);
      expect(s.progress).toBeLessThan(1);
      s = w.push(snap({ now: 1000 + A + G, frames: 11 + F, chunks: [mirror], arriving: ["mirror"] }));
      expect(s.settled).toBe(true);
    });

    it("hold it again once their files are here, while the work on them goes on", () => {
      const w = new SettleWatch(SETTLE_GATE);
      w.push(snap({ now: 0, chunks: [mirror], arriving: ["mirror"] }));
      expect(w.push(snap({ now: A, frames: 5, chunks: [mirror], arriving: ["mirror"] })).waiting).toEqual(["still"]);
      // Its files are all here before the wait settles: parsing, preparing and uploading it is local work.
      const here = { ...mirror, done: 0.8 };
      expect(w.push(snap({ now: A + 50, frames: 7, chunks: [here] })).waiting).toEqual(["mirror"]);
      expect(w.push(snap({ now: A + 2000, frames: 100, chunks: [{ ...here, done: 0.9 }] })).settled).toBe(false);
      w.push(snap({ now: A + 2100, frames: 110, chunks: [{ ...here, done: 1 }] }));
      expect(w.push(snap({ now: A + 2100 + G, frames: 110 + F, chunks: [{ ...here, done: 1 }] })).settled).toBe(true);
    });

    it("give each piece its own arrivingMs, from when it was first seen arriving", () => {
      const w = new SettleWatch(SETTLE_GATE);
      const forge = { id: "forge", done: 0, weight: 10 };
      w.push(snap({ now: 0, chunks: [mirror], arriving: ["mirror"] }));
      // The forge joins later (its load was not planned yet).
      const s = w.push(snap({ now: A, frames: 5, chunks: [mirror, forge], arriving: ["mirror", "forge"] }));
      expect(s.waiting).toEqual(["forge"]);
      expect(s.away).toEqual(["mirror"]);
      expect(w.push(snap({ now: 2 * A, frames: 9, chunks: [mirror, forge], arriving: ["mirror", "forge"] })).waiting).toEqual(["still"]);
    });

    it("let go of a busy piece and a late one the same way (the detail texture, live light's maps)", () => {
      const late = { late: ["live"], lateMs: 6000 };
      const w = new SettleWatch(SETTLE_GATE);
      w.push(snap({ now: 0, busy: ["detail"], arriving: ["detail", "live"], ...late }));
      let s = w.push(snap({ now: A, frames: 4, busy: ["detail"], arriving: ["detail", "live"], ...late }));
      expect(s.waiting).toEqual(["still"]);
      expect(s.away).toEqual(["detail", "live"]);
      // Settled although live light is still coming: its maps arrive after Enter.
      s = w.push(snap({ now: A + G, frames: 4 + F, busy: ["detail"], arriving: ["detail", "live"], ...late }));
      expect(s.settled).toBe(true);
      // With its maps here (decoding, uploading, linking) live light is a late piece again.
      const b = new SettleWatch(SETTLE_GATE);
      b.push(snap({ now: 0, arriving: ["live"], ...late }));
      b.push(snap({ now: A, frames: 4, ...late }));
      const t = b.push(snap({ now: A + G, frames: 4 + F, ...late }));
      expect(t.settled).toBe(false);
      expect(t.waiting).toEqual(["live"]);
    });

    it("never let fast travel's ink go while a download is under way (SETTLE)", () => {
      expect(SETTLE.arrivingMs).toBe(Infinity);
      const w = new SettleWatch(SETTLE);
      w.push(snap({ now: 0, chunks: [mirror], busy: ["detail"], arriving: ["mirror", "detail"] }));
      const s = w.push(snap({ now: 60000, frames: 5000, chunks: [mirror], busy: ["detail"], arriving: ["mirror", "detail"] }));
      expect(s.waiting).toEqual(["mirror", "detail"]);
      expect(s.away).toEqual([]);
    });
  });
});

describe("the page's settled wait reads live light (sect-experience.tsx, live.tsx)", () => {
  const dir = path.resolve(__dirname, "../../app/sect/experience");
  const page = readFileSync(path.join(dir, "sect-experience.tsx"), "utf8");
  const live = readFileSync(path.join(dir, "live.tsx"), "utf8");

  it("passes the canvas's live report as a late piece, capped by LIVE_LOOK.handover.inkWaitMs (the loading screen's wait by its own cap)", () => {
    const settle = page.slice(page.indexOf("const settleAt = "), page.indexOf("const arriveAt = "));
    expect(settle).toContain('late: r.live ? ["live"] : []');
    expect(settle).toContain("lateMs: gate ? gate.lateMs : LIVE_LOOK.handover.inkWaitMs");
    expect(settle).toContain("settleAt(store.targetU, ac.signal, { lateMs: ENTER_SETTLE_MS })");
    // The first stop's wait (`gate`) counts the shorter still.
    expect(settle).toContain("new SettleWatch(gate ? SETTLE_GATE : SETTLE)");
  });

  it("names what is still downloading: the areas, the detail texture and live light's maps", () => {
    const settle = page.slice(page.indexOf("const settleAt = "), page.indexOf("const arriveAt = "));
    expect(settle).toContain("const arriving = [...place.arriving]");
    expect(settle).toContain("if (detailHolds(detail, !!gate)) busy.push(\"detail\")");
    expect(settle).toContain('if (detail === "arriving") arriving.push("detail")');
    expect(settle).toContain('if (r.liveArriving) arriving.push("live")');
    expect(settle).toMatch(/lateMs: gate \? gate\.lateMs : LIVE_LOOK\.handover\.inkWaitMs,\s+arriving,/);
    expect(live).toContain("store.report.liveArriving = liveArriving(");
    expect(live.split("store.report.liveArriving = false").length - 1).toBeGreaterThanOrEqual(2);
  });

  it("has live light report it each frame, and clear it when off or gone", () => {
    expect(live).toContain("store.report.live = liveComing(");
    expect(live.split("store.report.live = false").length - 1).toBeGreaterThanOrEqual(2);
  });
});
