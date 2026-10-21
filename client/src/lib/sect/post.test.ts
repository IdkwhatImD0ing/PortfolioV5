import { describe, expect, it } from "vitest";
import { ATMOS, atmosFeatures, cloudCover, cloudDeckPoint, holdAt, holdBlur, holdFocusStep, nearestHold } from "./post";
import { tierQuality } from "./runtime";

describe("atmosFeatures", () => {
  it("gives High both passes, Medium the cloud shade only, Low nothing", () => {
    const high = tierQuality("high", 1);
    const mid = tierQuality("mid", 1);
    const low = tierQuality("low", 1);
    expect(atmosFeatures(high, high)).toEqual({ cloudShadows: true, holdFocus: true });
    expect(atmosFeatures(mid, mid)).toEqual({ cloudShadows: true, holdFocus: false });
    expect(atmosFeatures(low, low)).toEqual({ cloudShadows: false, holdFocus: false });
  });

  it("follows the ladder down: no hold focus once MSAA goes, no shade once bloom goes", () => {
    const high = tierQuality("high", 1);
    expect(atmosFeatures(high, { ...high, msaa: 0 })).toEqual({ cloudShadows: true, holdFocus: false });
    expect(atmosFeatures(high, { ...high, msaa: 0, bloom: false })).toEqual({ cloudShadows: false, holdFocus: false });
  });

  it("uses the tier's own top: Medium never gets the hold focus", () => {
    const mid = tierQuality("mid", 2, { coarse: true });
    expect(atmosFeatures(mid, mid).holdFocus).toBe(false);
  });
});

describe("cloud shade", () => {
  it("follows the low sun up to the deck: a metre of height moves the point about 8 m", () => {
    const sun: [number, number, number] = [-0.94397, 0.12187, 0.30671];
    const a = cloudDeckPoint([0, 100, 0], sun, 700);
    const b = cloudDeckPoint([0, 101, 0], sun, 700);
    const step = Math.hypot(a[0] - b[0], a[1] - b[1]);
    expect(step).toBeGreaterThan(7.5);
    expect(step).toBeLessThan(8.5);
    // A point on the deck is its own deck point.
    expect(cloudDeckPoint([5, 700, -3], sun, 700)).toEqual([5, -3]);
  });

  it("maps noise to shade through the cover band, smoothly", () => {
    const c = ATMOS.cloudShadow.cover;
    expect(cloudCover(c[0] - 0.01, c)).toBe(0);
    expect(cloudCover(c[1] + 0.01, c)).toBe(1);
    expect(cloudCover((c[0] + c[1]) / 2, c)).toBeCloseTo(0.5);
  });

  it("stays subtle", () => {
    expect(ATMOS.cloudShadow.strength).toBeGreaterThanOrEqual(0.1);
    expect(ATMOS.cloudShadow.strength).toBeLessThanOrEqual(0.2);
  });
});

describe("hold focus", () => {
  it("waits, fades in at rest, and goes fast when the camera moves", () => {
    const c = ATMOS.holdFocus;
    expect(holdFocusStep(0, "still", c.delay / 2, 0.016)).toBe(0);
    let w = 0;
    for (let i = 0; i < 200; i++) w = holdFocusStep(w, "still", c.delay + 1, 0.016);
    expect(w).toBe(1);
    // Gone within fadeOut (plus a frame) of input.
    const frames = Math.ceil(c.fadeOut / 0.016) + 1;
    for (let i = 0; i < frames; i++) w = holdFocusStep(w, "input", 0, 0.016);
    expect(w).toBe(0);
    expect(c.fadeOut).toBeLessThanOrEqual(0.25);
  });

  it("is gone on the first frame the view itself moves (a drag, or the camera leaving the stop)", () => {
    expect(holdFocusStep(1, "view", 5, 0.016)).toBe(0);
    expect(holdFocusStep(0.4, "view", 0, 0)).toBe(0);
    // Input alone only starts the fade.
    expect(holdFocusStep(1, "input", 0, 0.016)).toBeGreaterThan(0.8);
  });

  it("keeps the subject and what is near it sharp, softens the far distance, never the moon", () => {
    const focus = 60;
    expect(holdBlur(focus, focus)).toBe(0);
    expect(holdBlur(focus * ATMOS.holdFocus.near, focus)).toBe(0);
    expect(holdBlur(focus * ATMOS.holdFocus.far, focus)).toBeCloseTo(ATMOS.holdFocus.mix);
    expect(holdBlur(6000, focus)).toBe(0);
    expect(holdBlur(focus * ATMOS.holdFocus.far, focus, 0)).toBe(0);
    expect(ATMOS.holdFocus.mix).toBeLessThan(1);
  });

  it("finds the stop the camera rests at, and the nearest one in flight", () => {
    const holds = [
      { id: "gate", frame: 93 },
      { id: "mirror", frame: 217 },
    ];
    expect(holdAt(holds, 93)?.id).toBe("gate");
    expect(holdAt(holds, 94)?.id).toBe("gate");
    expect(holdAt(holds, 150)).toBeNull();
    expect(nearestHold(holds, 160)?.id).toBe("mirror");
    expect(nearestHold(holds, 150)?.id).toBe("gate");
    expect(nearestHold([], 150)).toBeNull();
  });
});

describe("bloom", () => {
  it("lets saturated glows past the threshold while marble, sky and sunlit cliffs stay under it", () => {
    const read = (c: [number, number, number]) => {
      const l = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
      const m = Math.max(...c);
      return l + (m - l) * ATMOS.bloom.chroma;
    };
    // Linear values read from the scene buffer at the stops (mission windows, marble, sky, cliff).
    expect(read([1.381, 0.644, 0.182])).toBeGreaterThan(1);
    expect(read([0.641, 0.604, 0.539])).toBeLessThan(0.8);
    expect(read([0.862, 0.587, 0.415])).toBeLessThan(0.85);
    expect(read([0.854, 0.471, 0.235])).toBeLessThan(0.85);
  });
});
