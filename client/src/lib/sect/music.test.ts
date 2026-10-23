import { describe, expect, it } from "vitest";
import { AREA_IDS } from "./areas";
import {
  CROSSFADE_SECONDS,
  MASTER_GAIN,
  MUSIC_KEYS,
  MUTE_KEY,
  SWITCH_HOLD_SECONDS,
  VOICE_DUCK,
  activatesAudio,
  areaAtFrame,
  createSwitcher,
  equalPowerFade,
  fadeDone,
  fadeGainAt,
  fadePoints,
  keepPlan,
  loadPlan,
  loopBounds,
  loopPosition,
  masterTarget,
  masterTimeConstant,
  musicBudget,
  musicSpans,
  parseMusicManifest,
  readMuted,
  stepKey,
  stepSwitcher,
  travelDirection,
  voiceDuck,
  wantedTrack,
  writeMuted,
  type AreaSpan,
  type MusicKey,
  type Switcher,
} from "./music";
import type { TalismanState } from "./talisman";

/** meta.json's area ranges (public/sect/full/meta.json, October 2026). */
const SPANS: AreaSpan[] = [
  { id: "gate", frameStart: 1, frameEnd: 165 },
  { id: "mirror", frameStart: 166, frameEnd: 286 },
  { id: "forge", frameStart: 287, frameEnd: 496 },
  { id: "arena", frameStart: 497, frameEnd: 604 },
  { id: "mission", frameStart: 605, frameEnd: 738 },
  { id: "library", frameStart: 739, frameEnd: 942 },
  { id: "steles", frameStart: 943, frameEnd: 1053 },
  { id: "scroll", frameStart: 1054, frameEnd: 1187 },
  { id: "formation", frameStart: 1188, frameEnd: 1343 },
  { id: "abode", frameStart: 1344, frameEnd: 1534 },
  { id: "summit", frameStart: 1535, frameEnd: 1729 },
];

const track = (key: string, extra: Record<string, unknown> = {}) => ({
  src: `/sect/audio/${key}.mp3`,
  duration: 160,
  loopStart: 2,
  loopEnd: 150,
  bpm: 84,
  lufs: -17,
  bytes: 3_000_000,
  ...extra,
});

describe("music keys", () => {
  it("are the loading screen and the eleven areas in flight order", () => {
    expect(MUSIC_KEYS).toEqual(["loading", ...AREA_IDS]);
  });
});

describe("parseMusicManifest", () => {
  it("reads the contract's shape", () => {
    const m = parseMusicManifest({ version: 1, tracks: { gate: track("gate"), loading: track("loading") } });
    expect(m?.tracks.gate).toEqual({ src: "/sect/audio/gate.mp3", duration: 160, loopStart: 2, loopEnd: 150, bpm: 84, lufs: -17, bytes: 3_000_000 });
    expect(Object.keys(m!.tracks).sort()).toEqual(["gate", "loading"]);
  });

  it("returns null for anything that is not a usable list", () => {
    expect(parseMusicManifest(null)).toBeNull();
    expect(parseMusicManifest("x")).toBeNull();
    expect(parseMusicManifest({ version: 2, tracks: { gate: track("gate") } })).toBeNull();
    expect(parseMusicManifest({ version: 1 })).toBeNull();
    expect(parseMusicManifest({ version: 1, tracks: {} })).toBeNull();
    expect(parseMusicManifest({ version: 1, tracks: { nowhere: track("nowhere") } })).toBeNull();
  });

  it("drops tracks with another origin, a scheme or no duration", () => {
    const m = parseMusicManifest({
      version: 1,
      tracks: {
        gate: track("gate", { src: "https://evil.example/x.mp3" }),
        mirror: track("mirror", { src: "//evil.example/x.mp3" }),
        forge: track("forge", { src: "javascript:alert(1)" }),
        arena: track("arena", { duration: 0 }),
        mission: track("mission", { duration: "160" }),
        summit: track("summit"),
      },
    });
    expect(Object.keys(m!.tracks)).toEqual(["summit"]);
  });

  it("loops the whole track when the loop points make no sense", () => {
    const m = parseMusicManifest({
      version: 1,
      tracks: {
        gate: track("gate", { loopStart: 50, loopEnd: 40 }),
        mirror: track("mirror", { loopEnd: 400 }),
        forge: track("forge", { loopStart: -1 }),
        arena: track("arena", { loopStart: undefined, loopEnd: undefined, bpm: "fast" }),
      },
    });
    for (const k of ["gate", "mirror", "forge"] as const) expect([m!.tracks[k]!.loopStart, m!.tracks[k]!.loopEnd]).toEqual([0, 160]);
    expect(m!.tracks.arena).toMatchObject({ loopStart: 0, loopEnd: 160, bpm: null });
  });
});

describe("loopBounds", () => {
  it("keeps the manifest's loop inside the decoded buffer", () => {
    expect(loopBounds({ loopStart: 2, loopEnd: 150 }, 160)).toEqual({ start: 2, end: 150 });
    expect(loopBounds({ loopStart: 2, loopEnd: 150.02 }, 150.01)).toEqual({ start: 2, end: 150.01 });
  });

  it("loops the whole buffer when the loop would be too short", () => {
    expect(loopBounds({ loopStart: 149.5, loopEnd: 150 }, 160)).toEqual({ start: 0, end: 160 });
    expect(loopBounds({ loopStart: 170, loopEnd: 180 }, 160)).toEqual({ start: 0, end: 160 });
  });
});

describe("loopPosition", () => {
  it("plays through to the loop's end, then round the loop", () => {
    expect(loopPosition(0, 2, 10)).toBe(0);
    expect(loopPosition(9.5, 2, 10)).toBe(9.5);
    expect(loopPosition(10, 2, 10)).toBe(2);
    expect(loopPosition(13, 2, 10)).toBe(5);
    expect(loopPosition(10 + 8 * 3 + 1, 2, 10)).toBeCloseTo(3);
    expect(loopPosition(-1, 2, 10)).toBe(0);
  });
});

describe("areaAtFrame", () => {
  it("finds the area whose range holds the frame", () => {
    expect(areaAtFrame(SPANS, 93)).toBe("gate");
    expect(areaAtFrame(SPANS, 165)).toBe("gate");
    expect(areaAtFrame(SPANS, 166)).toBe("mirror");
    expect(areaAtFrame(SPANS, 352)).toBe("forge");
    expect(areaAtFrame(SPANS, 1647)).toBe("summit");
  });

  it("between areas and past the ends, takes the nearer one", () => {
    const gappy: AreaSpan[] = [
      { id: "gate", frameStart: 10, frameEnd: 100 },
      { id: "mirror", frameStart: 200, frameEnd: 300 },
    ];
    expect(areaAtFrame(gappy, 140)).toBe("gate");
    expect(areaAtFrame(gappy, 160)).toBe("mirror");
    expect(areaAtFrame(gappy, 0)).toBe("gate");
    expect(areaAtFrame(gappy, 5000)).toBe("mirror");
    expect(areaAtFrame(SPANS, 165.4)).toBe("gate");
    expect(areaAtFrame(SPANS, 165.6)).toBe("mirror");
  });

  it("ignores ids that are not areas, and is null without areas", () => {
    expect(areaAtFrame([{ id: "moon", frameStart: 0, frameEnd: 2000 }], 50)).toBeNull();
    expect(areaAtFrame([], 50)).toBeNull();
  });
});

describe("musicSpans", () => {
  it("uses the area ranges, else each hold's frame", () => {
    expect(musicSpans(SPANS, [])).toHaveLength(11);
    const holds = [
      { id: "gate", frame: 93 },
      { id: "mirror", frame: 217 },
      { id: "start", frame: 27 },
    ];
    const s = musicSpans([], holds);
    expect(s).toEqual([
      { id: "gate", frameStart: 93, frameEnd: 93 },
      { id: "mirror", frameStart: 217, frameEnd: 217 },
    ]);
    expect(areaAtFrame(s, 150)).toBe("gate");
    expect(areaAtFrame(s, 160)).toBe("mirror");
    expect(musicSpans(null, holds)).toHaveLength(2);
  });
});

describe("wantedTrack", () => {
  it("is the loading track while the loading screen is up, else the camera's area", () => {
    expect(wantedTrack(true, null, SPANS)).toBe("loading");
    expect(wantedTrack(true, 352, SPANS)).toBe("loading");
    expect(wantedTrack(false, 352, SPANS)).toBe("forge");
    expect(wantedTrack(false, null, SPANS)).toBeNull();
    expect(wantedTrack(false, NaN, SPANS)).toBeNull();
  });
});

describe("stepSwitcher", () => {
  /** Runs the switcher over (time, target, settled) samples and returns the tracks it played. */
  function run(samples: [number, MusicKey | null, boolean][]): { played: (MusicKey | null)[]; s: Switcher } {
    let s = createSwitcher();
    const played: (MusicKey | null)[] = [];
    for (const [t, target, settled] of samples) {
      const before = s.current;
      s = stepSwitcher(s, target, t, settled);
      if (s.current !== before) played.push(s.current);
    }
    return { played, s };
  }

  it("starts the first track at once", () => {
    const { played, s } = run([[0, "loading", false]]);
    expect(played).toEqual(["loading"]);
    expect(s.switches).toBe(1);
  });

  it("waits out the hold before switching while the camera moves", () => {
    const { played } = run([
      [0, "gate", true],
      [0.1, "mirror", false],
      [0.4, "mirror", false],
      [0.1 + SWITCH_HOLD_SECONDS - 0.01, "mirror", false],
      [0.1 + SWITCH_HOLD_SECONDS, "mirror", false],
    ]);
    expect(played).toEqual(["gate", "mirror"]);
  });

  it("skips the areas a fast scroll sweeps through (gate to forge switches once)", () => {
    const samples: [number, MusicKey, boolean][] = [[0, "gate", true]];
    // About 0.2 s in the mirror's range, then the forge's, then at rest.
    for (let t = 0.1; t < 0.3; t += 0.1) samples.push([t, "mirror", false]);
    for (let t = 0.3; t < 0.8; t += 0.1) samples.push([t, "forge", false]);
    samples.push([0.8, "forge", true]);
    const { played, s } = run(samples);
    expect(played).toEqual(["gate", "forge"]);
    expect(s.switches).toBe(2);
  });

  it("switches at once when the camera settles in a new area", () => {
    const { played } = run([
      [0, "gate", true],
      [0.1, "mirror", false],
      [0.2, "mirror", true],
    ]);
    expect(played).toEqual(["gate", "mirror"]);
  });

  it("restarts the hold when the target changes, and forgets it when the camera comes back", () => {
    const { played, s } = run([
      [0, "gate", true],
      [0.1, "mirror", false],
      [0.5, "forge", false],
      [0.8, "forge", false],
      [0.9, "gate", false],
    ]);
    expect(played).toEqual(["gate"]);
    expect(s.pending).toBeNull();
    expect(stepSwitcher(s, "forge", 1.0, false).pending).toBe("forge");
  });

  it("changes nothing for a place without a track", () => {
    const { played, s } = run([
      [0, "gate", true],
      [0.1, null, true],
      [5, null, false],
    ]);
    expect(played).toEqual(["gate"]);
    expect(s.current).toBe("gate");
  });

  it("returns the same object when nothing changes (no work for a tick at rest)", () => {
    const s = stepSwitcher(createSwitcher(), "gate", 0, true);
    expect(stepSwitcher(s, "gate", 1, true)).toBe(s);
    const p = stepSwitcher(s, "mirror", 2, false);
    expect(stepSwitcher(p, "mirror", 2.1, false)).toBe(p);
  });
});

describe("equal-power crossfade", () => {
  it("keeps the summed power constant through a full crossfade", () => {
    const fin = equalPowerFade(0, 1, 10);
    const fout = equalPowerFade(1, 0, 10);
    expect(fin.duration).toBeCloseTo(CROSSFADE_SECONDS);
    expect(fout.duration).toBeCloseTo(CROSSFADE_SECONDS);
    for (let t = 9; t <= 13; t += 0.125) {
      const a = fadeGainAt(fin, t);
      const b = fadeGainAt(fout, t);
      expect(a * a + b * b).toBeCloseTo(1, 9);
    }
    expect(fadeGainAt(fin, 10 + CROSSFADE_SECONDS / 2)).toBeCloseTo(Math.SQRT1_2);
  });

  it("holds the ends outside the fade", () => {
    const f = equalPowerFade(0.2, 0.9, 3);
    expect(fadeGainAt(f, 0)).toBeCloseTo(0.2);
    expect(fadeGainAt(f, 100)).toBe(0.9);
    expect(fadeDone(f, 3 + f.duration)).toBe(true);
    expect(fadeDone(f, 3 + f.duration / 2)).toBe(false);
  });

  it("a reversal part way takes only the time its angle has left", () => {
    const half = Math.sin(Math.PI / 4);
    const back = equalPowerFade(half, 0, 0);
    expect(back.duration).toBeCloseTo(CROSSFADE_SECONDS / 2);
    expect(equalPowerFade(1, 1, 0).duration).toBe(0);
  });

  it("schedules as ramp points that end on the target", () => {
    const f = equalPowerFade(0, 1, 5);
    const pts = fadePoints(f);
    expect(pts).toHaveLength(16);
    expect(pts[pts.length - 1]).toEqual({ t: 5 + f.duration, v: 1 });
    for (let i = 1; i < pts.length; i++) {
      expect(pts[i].t).toBeGreaterThan(pts[i - 1].t);
      expect(pts[i].v).toBeGreaterThan(pts[i - 1].v);
    }
    expect(pts[7].v).toBeCloseTo(Math.SQRT1_2, 6);
    expect(fadePoints({ from: 0.3, to: 0.3, t0: 2, duration: 0 })).toEqual([{ t: 2, v: 0.3 }]);
    expect(fadePoints(equalPowerFade(Math.SQRT1_2, 0, 0)).length).toBe(8);
  });
});

describe("master gain", () => {
  const mix = { muted: false, voice: "none", video: false, away: false } as const;

  it("is about half, lower under a call, lower still while the agent speaks", () => {
    expect(MASTER_GAIN).toBeCloseTo(0.5);
    expect(masterTarget(mix)).toBe(MASTER_GAIN);
    expect(masterTarget({ ...mix, voice: "call" })).toBeCloseTo(MASTER_GAIN * 0.35);
    expect(masterTarget({ ...mix, voice: "speaking" })).toBeCloseTo(MASTER_GAIN * 0.15);
    expect(VOICE_DUCK.speaking).toBeLessThan(VOICE_DUCK.call);
  });

  it("is silent when muted, away, or under a playing video, whatever the call", () => {
    expect(masterTarget({ ...mix, muted: true })).toBe(0);
    expect(masterTarget({ ...mix, voice: "call", away: true })).toBe(0);
    expect(masterTarget({ ...mix, video: true })).toBe(0);
    expect(masterTarget({ ...mix, voice: "speaking", video: true })).toBe(0);
  });

  it("goes down in about 0.35 s, lifts a duck in about 0.5 s, comes out of silence gently", () => {
    // setTargetAtTime is ~95% of the way after three time constants.
    const t95 = (from: number, to: number) => 3 * masterTimeConstant(from, to);
    for (const [from, to] of [[0.5, 0.175], [0.175, 0.075], [0.5, 0], [0.075, 0.175], [0.175, 0.5]]) {
      expect(t95(from, to)).toBeGreaterThanOrEqual(0.3);
      expect(t95(from, to)).toBeLessThanOrEqual(0.6);
    }
    expect(t95(0, 0.5)).toBeGreaterThan(1);
  });
});

describe("voiceDuck", () => {
  it("reads the talisman: a call (connecting, listening) or the agent speaking; text chat leaves the music", () => {
    expect(voiceDuck("connecting")).toBe("call");
    expect(voiceDuck("listening")).toBe("call");
    expect(voiceDuck("speaking")).toBe("speaking");
    for (const s of ["idle", "thinking", "text", "ended", "error", "", undefined, null, "Speaking"]) expect(voiceDuck(s)).toBe("none");
  });

  it("knows every talisman state (lib/sect/talisman.ts)", () => {
    const all: TalismanState[] = ["idle", "connecting", "listening", "speaking", "thinking", "text", "ended", "error"];
    expect(all.filter((s) => voiceDuck(s) !== "none")).toEqual(["connecting", "listening", "speaking"]);
  });
});

describe("what to load and keep", () => {
  it("follows the direction of travel", () => {
    expect(travelDirection(1, 300, 290)).toBe(-1);
    expect(travelDirection(-1, 300, 310)).toBe(1);
    expect(travelDirection(-1, 300, 300.2)).toBe(-1);
  });

  it("steps along the flight, from the loading screen into the opening area", () => {
    expect(stepKey("loading", 1, null)).toBe("gate");
    expect(stepKey("loading", 1, "forge")).toBe("forge");
    expect(stepKey("loading", -1, "forge")).toBeNull();
    expect(stepKey("gate", 1, null)).toBe("mirror");
    expect(stepKey("gate", -1, null)).toBeNull();
    expect(stepKey("summit", 1, null)).toBeNull();
    expect(stepKey("summit", -1, null)).toBe("abode");
  });

  it("loads the current track, then the next one in the direction of travel", () => {
    expect(loadPlan(null, 1, null)).toEqual([]);
    expect(loadPlan("forge", 1, null)).toEqual(["forge", "arena"]);
    expect(loadPlan("forge", -1, null)).toEqual(["forge", "mirror"]);
    expect(loadPlan("summit", 1, null)).toEqual(["summit"]);
    expect(loadPlan("loading", 1, "library")).toEqual(["loading", "library"]);
  });

  it("keeps the current, next, previous and after-next tracks, cut to the budget", () => {
    expect(keepPlan("forge", 1, null, 4)).toEqual(["forge", "arena", "mirror", "mission"]);
    expect(keepPlan("forge", 1, null, 3)).toEqual(["forge", "arena", "mirror"]);
    expect(keepPlan("forge", -1, null, 2)).toEqual(["forge", "mirror"]);
    expect(keepPlan("gate", -1, null, 3)).toEqual(["gate", "mirror"]);
    expect(keepPlan("loading", 1, "gate", 3)).toEqual(["loading", "gate", "mirror"]);
    expect(keepPlan(null, 1, null, 3)).toEqual([]);
  });

  it("gives phones and small-memory devices a smaller budget", () => {
    expect(musicBudget({ coarse: true, deviceMemory: 8 })).toBe(2);
    expect(musicBudget({ coarse: false, deviceMemory: 4 })).toBe(2);
    expect(musicBudget({ coarse: false, deviceMemory: 8 })).toBe(3);
    expect(musicBudget({ coarse: false })).toBe(3);
  });
});

describe("the mute choice", () => {
  it("starts muted until the visitor turns sound on, and remembers it", () => {
    const data = new Map<string, string>();
    const storage = { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v) };
    // A first visit: muted (the README's "Start muted, with a visible sound toggle").
    expect(readMuted(storage)).toBe(true);
    writeMuted(storage, false);
    expect(data.get(MUTE_KEY)).toBe("0");
    expect(readMuted(storage)).toBe(false);
    writeMuted(storage, true);
    expect(data.get(MUTE_KEY)).toBe("1");
    expect(readMuted(storage)).toBe(true);
  });

  it("survives blocked storage (muted, and nothing throws)", () => {
    const blocked = {
      getItem: () => {
        throw new Error("SecurityError");
      },
      setItem: () => {
        throw new Error("SecurityError");
      },
    };
    expect(readMuted(blocked)).toBe(true);
    expect(() => writeMuted(blocked, true)).not.toThrow();
    expect(readMuted(null)).toBe(true);
  });
});

describe("activatesAudio", () => {
  it("counts the events that give user activation, and not a wheel", () => {
    expect(activatesAudio({ type: "keydown", key: "j" })).toBe(true);
    expect(activatesAudio({ type: "keydown", key: "Escape" })).toBe(false);
    expect(activatesAudio({ type: "pointerdown", pointerType: "mouse" })).toBe(true);
    expect(activatesAudio({ type: "pointerdown", pointerType: "touch" })).toBe(false);
    expect(activatesAudio({ type: "pointerup", pointerType: "touch" })).toBe(true);
    expect(activatesAudio({ type: "touchend" })).toBe(true);
    expect(activatesAudio({ type: "click" })).toBe(true);
    expect(activatesAudio({ type: "wheel" })).toBe(false);
    expect(activatesAudio({ type: "scroll" })).toBe(false);
  });
});
