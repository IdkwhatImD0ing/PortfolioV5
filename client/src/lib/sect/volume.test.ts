import { describe, expect, it } from "vitest";
import { MASTER_GAIN, VOICE_DUCK, masterTarget } from "./music";
import {
  DEFAULT_VOLUME,
  VOLUME_KEY,
  VOLUME_STEP,
  clampVolume,
  readVolume,
  volumeFromPercent,
  volumeGain,
  volumePercent,
  volumeText,
  writeVolume,
} from "./volume";

function memoryStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => {
      data.set(k, v);
    },
  };
}

const throwing = {
  getItem: () => {
    throw new Error("SecurityError");
  },
  setItem: () => {
    throw new Error("QuotaExceededError");
  },
};

describe("volume share and percent", () => {
  it("starts at the music's own level", () => {
    expect(DEFAULT_VOLUME).toBe(1);
    expect(volumePercent(DEFAULT_VOLUME)).toBe(100);
  });

  it("clamps to 0..1 and treats nonsense as the default", () => {
    expect(clampVolume(-0.2)).toBe(0);
    expect(clampVolume(1.7)).toBe(1);
    expect(clampVolume(0.35)).toBe(0.35);
    expect(clampVolume(Number.NaN)).toBe(DEFAULT_VOLUME);
    expect(clampVolume(Number.POSITIVE_INFINITY)).toBe(DEFAULT_VOLUME);
  });

  it("converts between the slider's whole percent and the share", () => {
    expect(volumeFromPercent("70")).toBe(0.7);
    expect(volumeFromPercent(0)).toBe(0);
    expect(volumeFromPercent("100")).toBe(1);
    expect(volumeFromPercent("33.6")).toBe(0.34);
    expect(volumeFromPercent("250")).toBe(1);
    expect(volumeFromPercent("-5")).toBe(0);
    expect(volumeFromPercent("abc")).toBe(DEFAULT_VOLUME);
    expect(volumePercent(0.704)).toBe(70);
    expect(volumeText(0.45)).toBe("45%");
  });

  it("steps in fives, so 0 to 100 is twenty presses", () => {
    expect(VOLUME_STEP).toBe(5);
    expect(100 % VOLUME_STEP).toBe(0);
  });
});

describe("volumeGain", () => {
  it("follows the square of the share, so equal steps sound even", () => {
    expect(volumeGain(1)).toBe(1);
    expect(volumeGain(0)).toBe(0);
    expect(volumeGain(0.5)).toBeCloseTo(0.25);
    // Half way on the slider is about -12 dB.
    expect(20 * Math.log10(volumeGain(0.5))).toBeCloseTo(-12.04, 1);
    expect(volumeGain(2)).toBe(1);
  });

  it("only ever grows as the slider goes up", () => {
    let prev = -1;
    for (let p = 0; p <= 100; p += VOLUME_STEP) {
      const g = volumeGain(volumeFromPercent(p));
      expect(g).toBeGreaterThan(prev);
      prev = g;
    }
  });
});

describe("the slider is the master of the mix", () => {
  const mix = { muted: false, voice: "none", video: false, away: false } as const;

  it("100% (or no volume given) is the level the music always had", () => {
    expect(masterTarget({ ...mix, volume: 1 })).toBe(MASTER_GAIN);
    expect(masterTarget(mix)).toBe(MASTER_GAIN);
  });

  it("the voice call's ducking takes its share of the slider's level", () => {
    expect(masterTarget({ ...mix, volume: 0.5 })).toBeCloseTo(MASTER_GAIN * 0.25);
    expect(masterTarget({ ...mix, volume: 0.5, voice: "call" })).toBeCloseTo(MASTER_GAIN * 0.25 * VOICE_DUCK.call);
    expect(masterTarget({ ...mix, volume: 0.5, voice: "speaking" })).toBeCloseTo(MASTER_GAIN * 0.25 * VOICE_DUCK.speaking);
  });

  it("a video, the page view or mute silence it at any volume; 0% is silent too", () => {
    expect(masterTarget({ ...mix, volume: 1, video: true })).toBe(0);
    expect(masterTarget({ ...mix, volume: 0.8, away: true })).toBe(0);
    expect(masterTarget({ ...mix, volume: 0.8, muted: true })).toBe(0);
    expect(masterTarget({ ...mix, volume: 0 })).toBe(0);
  });
});

describe("remembered per visitor", () => {
  it("reads the saved percent", () => {
    expect(readVolume(memoryStorage({ [VOLUME_KEY]: "40" }))).toBe(0.4);
    expect(readVolume(memoryStorage({ [VOLUME_KEY]: "0" }))).toBe(0);
  });

  it("gives the default for nothing saved, nonsense, or blocked storage", () => {
    expect(readVolume(memoryStorage())).toBe(DEFAULT_VOLUME);
    expect(readVolume(memoryStorage({ [VOLUME_KEY]: "" }))).toBe(DEFAULT_VOLUME);
    expect(readVolume(memoryStorage({ [VOLUME_KEY]: "loud" }))).toBe(DEFAULT_VOLUME);
    expect(readVolume(memoryStorage({ [VOLUME_KEY]: "900" }))).toBe(1);
    expect(readVolume(throwing)).toBe(DEFAULT_VOLUME);
    expect(readVolume(null)).toBe(DEFAULT_VOLUME);
    expect(readVolume(undefined)).toBe(DEFAULT_VOLUME);
  });

  it("writes whole percent, and a blocked write is not an error", () => {
    const s = memoryStorage();
    writeVolume(s, 0.654);
    expect(s.data.get(VOLUME_KEY)).toBe("65");
    expect(readVolume(s)).toBe(0.65);
    expect(() => writeVolume(throwing, 0.5)).not.toThrow();
    expect(() => writeVolume(null, 0.5)).not.toThrow();
  });
});
