import { describe, expect, it } from "vitest";
import { applyShow, farFullOn, parseFarParam, setShow, type FarFrame, type ShowSet } from "./far";

interface TestSet extends ShowSet {
  ok: boolean;
  /** Its scenes are visible (what applyShow's `show` last said). */
  visible: boolean;
  shows: number;
}

const set = (id: string, need: [number, number] | null, ok = true): TestSet => ({ id, need, ok, drawn: false, far: false, visible: false, shows: 0 });

const frame = (o: Partial<FarFrame> = {}): FarFrame => ({ frame: 100, only: null, farFull: true, calm: true, ...o });

const ok = (s: TestSet) => s.ok;
const show = (s: TestSet, v: boolean) => {
  s.visible = v;
  s.shows++;
};

/** The rule as it was before far places: near or stand-in. */
const nearBefore = (s: TestSet, f: FarFrame) => s.ok && s.need !== null && f.frame >= s.need[0] && f.frame <= s.need[1] && (f.only === null || s.id === f.only);

describe("setShow: near, far or stand-in", () => {
  it("near is the rule the page always had, with far places on or off", () => {
    const sets = [set("gate", [0, 150]), set("mirror", [140, 300]), set("forge", [290, 420], false), set("global", null)];
    for (const fr of [50, 100, 145, 150, 151, 299, 300, 350, 500]) {
      for (const only of [null, "gate", "mirror"]) {
        for (const farFull of [false, true]) {
          for (const seen of [false, true]) {
            const f = frame({ frame: fr, only, farFull });
            for (const s of sets) expect(setShow(s, s.ok, seen, f) === "near", `${s.id} at ${fr}, only ${only}, far ${farFull}`).toBe(nearBefore(s, f));
          }
        }
      }
    }
  });

  it("far: a loaded area outside its range while far places are on and the stand-in step is off", () => {
    const mirror = set("mirror", [140, 300]);
    expect(setShow(mirror, true, true, frame({ frame: 100 }))).toBe("far");
    expect(setShow(mirror, true, true, frame({ frame: 400 }))).toBe("far");
    // Off: the stand-in, as before.
    expect(setShow(mirror, true, true, frame({ frame: 100, farFull: false }))).toBe("proxy");
    // The ladder's stand-in step: only its area is drawn, never a far one.
    expect(setShow(mirror, true, true, frame({ frame: 100, only: "gate" }))).toBe("proxy");
    // Inside its range but not the stand-in step's area: the stand-in, not far.
    expect(setShow(mirror, true, true, frame({ frame: 200, only: "gate" }))).toBe("proxy");
    // Not drawable (not ready, dropped, freed), or the global set: never far.
    expect(setShow(mirror, false, true, frame({ frame: 100 }))).toBe("proxy");
    expect(setShow(set("global", null), true, true, frame({ frame: 100 }))).toBe("proxy");
  });

  it("an area never on screen first shows as far only while calm and while the frame's first show is free", () => {
    const mirror = set("mirror", [140, 300]);
    expect(setShow(mirror, true, false, frame({ calm: true }))).toBe("far");
    expect(setShow(mirror, true, false, frame({ calm: false }))).toBe("proxy");
    expect(setShow(mirror, true, false, frame({ calm: true }), false)).toBe("proxy");
    // One that has been on screen turns far moving or not.
    expect(setShow(mirror, true, true, frame({ calm: false }), false)).toBe("far");
    // Near needs no calm: the gate is for far shows only.
    expect(setShow(mirror, true, false, frame({ frame: 200, calm: false }), false)).toBe("near");
  });
});

describe("applyShow: one rendered frame over the loaded chunks", () => {
  it("with far places off it shows exactly what the old rule showed, frame for frame", () => {
    const sets = [set("gate", [0, 150]), set("mirror", [140, 300]), set("forge", [290, 420]), set("arena", [400, 600], false)];
    const seen = new WeakSet<TestSet>();
    for (let fr = 0; fr <= 650; fr += 5) {
      for (const only of [null, "mirror"]) {
        const f = frame({ frame: fr, only, farFull: false, calm: fr % 2 === 0 });
        expect(applyShow(sets, seen, f, ok, show)).toBe(false);
        for (const s of sets) {
          expect(s.far).toBe(false);
          expect(s.drawn, `${s.id} at ${fr}`).toBe(nearBefore(s, f));
          expect(s.visible).toBe(s.drawn);
        }
      }
    }
  });

  it("calls show only when a set's visibility changes, and keeps drawn and far apart", () => {
    const mirror = set("mirror", [140, 300]);
    const sets = [mirror];
    const seen = new WeakSet<TestSet>();
    applyShow(sets, seen, frame({ frame: 200 }), ok, show);
    expect(mirror).toMatchObject({ drawn: true, far: false, visible: true, shows: 1 });
    // Out of its range: far, still visible, no call.
    expect(applyShow(sets, seen, frame({ frame: 320, calm: false }), ok, show)).toBe(true);
    expect(mirror).toMatchObject({ drawn: false, far: true, visible: true, shows: 1 });
    // Same again: nothing changed.
    expect(applyShow(sets, seen, frame({ frame: 330, calm: false }), ok, show)).toBe(false);
    expect(mirror.shows).toBe(1);
    // Back in: near, no call.
    expect(applyShow(sets, seen, frame({ frame: 250 }), ok, show)).toBe(true);
    expect(mirror).toMatchObject({ drawn: true, far: false, visible: true, shows: 1 });
  });

  it("an area that has been on screen turns far at once on the way out, moving", () => {
    const gate = set("gate", [0, 150]);
    const mirror = set("mirror", [140, 300]);
    const sets = [gate, mirror];
    const seen = new WeakSet<TestSet>();
    // The flight starts at the gate while moving: the mirror, never seen, waits as a stand-in.
    applyShow(sets, seen, frame({ frame: 100, calm: false }), ok, show);
    expect(gate).toMatchObject({ drawn: true, far: false });
    expect(mirror).toMatchObject({ drawn: false, far: false, visible: false });
    // Into the mirror's range and past the gate's, still moving: the gate goes far, not to its stand-in.
    applyShow(sets, seen, frame({ frame: 200, calm: false }), ok, show);
    expect(gate).toMatchObject({ drawn: false, far: true, visible: true });
    expect(mirror).toMatchObject({ drawn: true, far: false, visible: true });
    applyShow(sets, seen, frame({ frame: 320, calm: false }), ok, show);
    expect(mirror).toMatchObject({ drawn: false, far: true, visible: true });
  });

  it("first far shows wait for calm and come one a frame, in the chunks' order", () => {
    const sets = [set("gate", [0, 150]), set("forge", [290, 420]), set("arena", [400, 600]), set("library", [700, 900])];
    const seen = new WeakSet<TestSet>();
    // Moving: only the gate (near) shows.
    expect(applyShow(sets, seen, frame({ frame: 100, calm: false }), ok, show)).toBe(false);
    expect(sets.map((s) => s.far)).toEqual([false, false, false, false]);
    // At rest: one more a frame.
    const counts: number[] = [];
    for (let i = 0; i < 4; i++) {
      applyShow(sets, seen, frame({ frame: 100, calm: true }), ok, show);
      counts.push(sets.filter((s) => s.far).length);
    }
    expect(counts).toEqual([1, 2, 3, 3]);
    expect(sets.map((s) => (s.drawn ? "near" : s.far ? "far" : "proxy"))).toEqual(["near", "far", "far", "far"]);
  });

  it("a set not ready yet waits, and shows once it is", () => {
    const forge = set("forge", [290, 420], false);
    const seen = new WeakSet<TestSet>();
    applyShow([forge], seen, frame(), ok, show);
    expect(forge.far).toBe(false);
    forge.ok = true;
    expect(applyShow([forge], seen, frame(), ok, show)).toBe(true);
    expect(forge).toMatchObject({ far: true, visible: true });
  });

  it("far places off (the ladder's step): every far set back to its stand-in at once, and they stay so", () => {
    const sets = [set("gate", [0, 150]), set("forge", [290, 420]), set("arena", [400, 600])];
    const seen = new WeakSet<TestSet>();
    for (let i = 0; i < 3; i++) applyShow(sets, seen, frame(), ok, show);
    expect(sets.map((s) => s.visible)).toEqual([true, true, true]);
    expect(applyShow(sets, seen, frame({ farFull: false, calm: false }), ok, show)).toBe(true);
    expect(sets.map((s) => [s.drawn, s.far, s.visible])).toEqual([
      [true, false, true],
      [false, false, false],
      [false, false, false],
    ]);
    // Moving on: the old rule, nothing far.
    applyShow(sets, seen, frame({ frame: 350, farFull: false }), ok, show);
    expect(sets.map((s) => [s.drawn, s.far, s.visible])).toEqual([
      [false, false, false],
      [true, false, true],
      [false, false, false],
    ]);
  });

  it("a dropped set (not drawable) is hidden at once, far or near", () => {
    const forge = set("forge", [290, 420]);
    const seen = new WeakSet<TestSet>();
    applyShow([forge], seen, frame(), ok, show);
    expect(forge.far).toBe(true);
    forge.ok = false;
    expect(applyShow([forge], seen, frame({ calm: false }), ok, show)).toBe(true);
    expect(forge).toMatchObject({ drawn: false, far: false, visible: false });
  });
});

describe("the ?far= switch", () => {
  it("parses 0/off and 1/on, and nothing else", () => {
    expect(parseFarParam("")).toBeNull();
    expect(parseFarParam("?far=0")).toBe("off");
    expect(parseFarParam("?far=off")).toBe("off");
    expect(parseFarParam("?far=1")).toBe("on");
    expect(parseFarParam("?far=on")).toBe("on");
    expect(parseFarParam("?debug=1&far=1")).toBe("on");
    expect(parseFarParam("?far=0&tier=high")).toBe("off");
    expect(parseFarParam("?far=2")).toBeNull();
    expect(parseFarParam("?far=")).toBeNull();
    expect(parseFarParam("?afar=1")).toBeNull();
    expect(parseFarParam("#far=1")).toBeNull();
  });

  it("the switch wins; without it, far places follow whether the page holds every area", () => {
    expect(farFullOn(true, null)).toBe(true);
    expect(farFullOn(false, null)).toBe(false);
    expect(farFullOn(true, "off")).toBe(false);
    expect(farFullOn(false, "on")).toBe(true);
  });
});
