import { describe, expect, it } from "vitest";
import { abortError, createFetchGate, type FetchGate } from "./fetch-gate";

/** Lets every settled promise run its callbacks. */
const flush = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

/** Asks for a place under `name`; `got` records the order places were given, `releases` how to give each back. */
function asker(gate: FetchGate) {
  const got: string[] = [];
  const releases = new Map<string, () => void>();
  const errors = new Map<string, unknown>();
  const ask = (name: string, priority = 0, signal?: AbortSignal) =>
    gate.acquire({ priority, signal }).then(
      (release) => {
        got.push(name);
        releases.set(name, release);
      },
      (e: unknown) => {
        errors.set(name, e);
      },
    );
  const release = (name: string) => {
    const r = releases.get(name);
    if (!r) throw new Error(`${name} has no place`);
    r();
  };
  return { got, releases, errors, ask, release };
}

describe("createFetchGate", () => {
  it("gives at most `limit` places at once", async () => {
    const gate = createFetchGate(2);
    const a = asker(gate);
    for (const n of ["a", "b", "c", "d", "e"]) void a.ask(n);
    await flush();
    expect(a.got).toEqual(["a", "b"]);
    expect(gate.running).toBe(2);
    expect(gate.waiting).toBe(3);
    a.release("a");
    await flush();
    expect(a.got).toEqual(["a", "b", "c"]);
    expect(gate.running).toBe(2);
    for (const n of ["b", "c", "d", "e"]) {
      a.release(n);
      await flush();
      expect(gate.running).toBeLessThanOrEqual(2);
    }
    expect(a.got).toEqual(["a", "b", "c", "d", "e"]);
    expect(gate.running).toBe(0);
    expect(gate.waiting).toBe(0);
    expect(gate.peak).toBe(2);
  });

  it("gives a freed place to the next waiter at once", async () => {
    const gate = createFetchGate(1);
    const a = asker(gate);
    void a.ask("a");
    void a.ask("b");
    await flush();
    expect(a.got).toEqual(["a"]);
    a.release("a");
    // Taken inside the release, before any callback runs: nothing can slip in between.
    expect(gate.running).toBe(1);
    expect(gate.waiting).toBe(0);
    await flush();
    expect(a.got).toEqual(["a", "b"]);
  });

  it("serves a higher priority first", async () => {
    const gate = createFetchGate(1);
    const a = asker(gate);
    void a.ask("first", 0);
    await flush();
    void a.ask("low 1", 0);
    void a.ask("high 1", 2);
    void a.ask("low 2", 0);
    void a.ask("high 2", 2);
    await flush();
    for (const n of ["first", "high 1", "high 2", "low 1"]) {
      a.release(n);
      await flush();
    }
    expect(a.got).toEqual(["first", "high 1", "high 2", "low 1", "low 2"]);
  });

  it("serves one priority first come, first served", async () => {
    const gate = createFetchGate(1);
    const a = asker(gate);
    const names = ["a", "b", "c", "d", "e", "f"];
    for (const n of names) void a.ask(n, 1);
    for (const n of names) {
      await flush();
      a.release(n);
    }
    await flush();
    expect(a.got).toEqual(names);
  });

  it("takes a waiter whose signal aborts out of the queue, with an AbortError, never giving it a place", async () => {
    const gate = createFetchGate(1);
    const a = asker(gate);
    const stop = new AbortController();
    void a.ask("a");
    void a.ask("b", 0, stop.signal);
    void a.ask("c");
    await flush();
    expect(gate.waiting).toBe(2);
    stop.abort();
    expect(gate.waiting).toBe(1);
    await flush();
    expect((a.errors.get("b") as Error).name).toBe("AbortError");
    a.release("a");
    await flush();
    expect(a.got).toEqual(["a", "c"]);
    expect(gate.running).toBe(1);
    expect(gate.peak).toBe(1);
  });

  it("rejects a signal aborted already, even with a place free", async () => {
    const gate = createFetchGate(2);
    const a = asker(gate);
    const stop = new AbortController();
    stop.abort();
    void a.ask("a", 0, stop.signal);
    await flush();
    expect(a.got).toEqual([]);
    expect((a.errors.get("a") as Error).name).toBe("AbortError");
    expect(gate.running).toBe(0);
    expect(gate.waiting).toBe(0);
  });

  it("keeps a place given before the abort until it is released", async () => {
    const gate = createFetchGate(1);
    const a = asker(gate);
    const stop = new AbortController();
    void a.ask("a", 0, stop.signal);
    void a.ask("b");
    await flush();
    stop.abort();
    await flush();
    // The holder's download stops on the same signal and it releases then: until that, the place is its.
    expect(a.errors.has("a")).toBe(false);
    expect(gate.running).toBe(1);
    expect(a.got).toEqual(["a"]);
    a.release("a");
    await flush();
    expect(a.got).toEqual(["a", "b"]);
  });

  it("ignores a second release", async () => {
    const gate = createFetchGate(1);
    const a = asker(gate);
    void a.ask("a");
    void a.ask("b");
    void a.ask("c");
    await flush();
    a.release("a");
    a.release("a");
    await flush();
    expect(a.got).toEqual(["a", "b"]);
    expect(gate.running).toBe(1);
    expect(gate.waiting).toBe(1);
  });

  it("has at least one place", async () => {
    for (const limit of [0, -3, Number.NaN]) {
      const gate = createFetchGate(limit);
      const a = asker(gate);
      void a.ask("a");
      void a.ask("b");
      await flush();
      expect(a.got).toEqual(["a"]);
    }
  });
});

describe("abortError", () => {
  it("passes on the signal's own AbortError", () => {
    const stop = new AbortController();
    stop.abort();
    expect(abortError(stop.signal)).toBe(stop.signal.reason);
    expect(abortError(stop.signal).name).toBe("AbortError");
  });

  it("makes an AbortError when the reason is something else", () => {
    const stop = new AbortController();
    stop.abort("left");
    expect(abortError(stop.signal).name).toBe("AbortError");
    expect(abortError().name).toBe("AbortError");
  });
});
