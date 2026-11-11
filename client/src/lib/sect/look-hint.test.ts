/** Free look's hint: when it retires, and how long it stays (look-hint.ts). */
import { describe, expect, it } from "vitest";
import {
  countLookHintShown,
  LOOK_HINT_KEY,
  LOOK_HINT_MS,
  LOOK_HINT_SHOWN_KEY,
  LOOK_HINT_SHOWS,
  lookHintRetired,
  lookHintShows,
  retireLookHint,
} from "./look-hint";

const storage = (init: Record<string, string> = {}) => {
  const data = new Map<string, string>(Object.entries(init));
  return {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    data,
  };
};
const throwing = {
  getItem: (): string | null => {
    throw new Error("SecurityError");
  },
  setItem: () => {
    throw new Error("QuotaExceededError");
  },
};

describe("the look hint", () => {
  it("keeps the key earlier visits wrote after a turn, so they stay retired", () => {
    expect(LOOK_HINT_KEY).toBe("sect.lookHint");
    expect(lookHintRetired(storage({ [LOOK_HINT_KEY]: "1" }))).toBe(true);
    expect(lookHintRetired(storage())).toBe(false);
    expect(lookHintRetired(storage({ [LOOK_HINT_KEY]: "0" }))).toBe(false);
    expect(lookHintRetired(null)).toBe(false);
    expect(lookHintRetired(throwing)).toBe(false);
  });

  it("retires after a turn", () => {
    const s = storage();
    retireLookHint(s);
    expect(lookHintRetired(s)).toBe(true);
    expect(() => retireLookHint(throwing)).not.toThrow();
    expect(() => retireLookHint(null)).not.toThrow();
  });

  it("on a phone, retires after its second showing, turned or not", () => {
    expect(LOOK_HINT_SHOWS).toBe(2);
    const s = storage();
    countLookHintShown(s);
    expect(lookHintShows(s)).toBe(1);
    expect(lookHintRetired(s)).toBe(false);
    countLookHintShown(s);
    expect(lookHintShows(s)).toBe(2);
    expect(lookHintRetired(s)).toBe(true);
    expect(s.data.get(LOOK_HINT_SHOWN_KEY)).toBe("2");
  });

  it("counts nothing from junk, no storage or blocked storage, and never throws", () => {
    for (const junk of ["", "x", "-1", "1.5", " 2"]) expect(lookHintShows(storage({ [LOOK_HINT_SHOWN_KEY]: junk })), junk).toBe(0);
    expect(lookHintShows(null)).toBe(0);
    expect(lookHintShows(throwing)).toBe(0);
    expect(() => countLookHintShown(throwing)).not.toThrow();
    expect(() => countLookHintShown(null)).not.toThrow();
    // Junk starts the count over.
    const s = storage({ [LOOK_HINT_SHOWN_KEY]: "lots" });
    countLookHintShown(s);
    expect(lookHintShows(s)).toBe(1);
    expect(lookHintRetired(s)).toBe(false);
  });

  it("stays about 11 seconds on a phone, 25 on wider screens", () => {
    expect(LOOK_HINT_MS.phone).toBeGreaterThanOrEqual(10000);
    expect(LOOK_HINT_MS.phone).toBeLessThanOrEqual(12000);
    expect(LOOK_HINT_MS.wide).toBe(25000);
  });
});
