import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MASTER_GAIN, VOICE_DUCK, VOLUME_TIME_CONSTANT, parseMusicManifest, type MusicKey } from "@/lib/sect/music";
import { MusicEngine } from "./music-engine";

// --- a small fake of the Web Audio API ------------------------------------------------------------------

type ParamEvent = { type: "set" | "ramp" | "target"; v: number; t: number; tc?: number };

class FakeParam {
  events: ParamEvent[] = [];
  constructor(public value: number) {}
  cancelScheduledValues(t: number) {
    this.events = this.events.filter((e) => e.t < t);
  }
  setValueAtTime(v: number, t: number) {
    this.events.push({ type: "set", v, t });
  }
  linearRampToValueAtTime(v: number, t: number) {
    this.events.push({ type: "ramp", v, t });
  }
  setTargetAtTime(v: number, t: number, tc?: number) {
    this.events.push({ type: "target", v, t, tc });
    this.value = v;
  }
  /** Where the last scheduled event leaves the param. */
  get aim() {
    return this.events.length ? this.events[this.events.length - 1].v : this.value;
  }
}

class FakeNode {
  out: unknown[] = [];
  connect(n: unknown) {
    this.out.push(n);
    return n;
  }
  disconnect() {
    this.out = [];
  }
}

class FakeGain extends FakeNode {
  gain = new FakeParam(1);
}

class FakeSource extends FakeNode {
  buffer: { duration: number; key: string } | null = null;
  loop = false;
  loopStart = 0;
  loopEnd = 0;
  started: [number, number] | null = null;
  stopped = false;
  start(when: number, offset: number) {
    this.started = [when, offset];
  }
  stop() {
    this.stopped = true;
  }
}

class FakeContext {
  currentTime = 0;
  state: "running" | "suspended" | "closed" = "running";
  destination = new FakeNode();
  sources: FakeSource[] = [];
  gains: FakeGain[] = [];
  resumes = 0;
  suspends = 0;
  createGain() {
    const g = new FakeGain();
    this.gains.push(g);
    return g;
  }
  createBufferSource() {
    const s = new FakeSource();
    this.sources.push(s);
    return s;
  }
  decodeAudioData(bytes: ArrayBuffer, ok?: (b: unknown) => void) {
    const key = new TextDecoder().decode(bytes);
    const buffer = { duration: 160, key };
    ok?.(buffer);
    return Promise.resolve(buffer);
  }
  resume() {
    this.resumes++;
    this.state = "running";
    return Promise.resolve();
  }
  suspend() {
    this.suspends++;
    this.state = "suspended";
    return Promise.resolve();
  }
  close() {
    this.state = "closed";
    return Promise.resolve();
  }
  /** The master gain: the first gain made, wired to the destination. */
  get master() {
    return this.gains[0];
  }
  playing(key: string) {
    return this.sources.filter((s) => s.buffer?.key === key && !s.stopped);
  }
}

const MANIFEST = parseMusicManifest({
  version: 1,
  tracks: Object.fromEntries(
    ["loading", "gate", "mirror", "forge", "arena", "mission"].map((k) => [
      k,
      { src: `/sect/audio/${k}.mp3`, duration: 160, loopStart: 2.5, loopEnd: 150, bpm: 84, lufs: -17, bytes: 1 },
    ]),
  ),
})!;

interface Rig {
  engine: MusicEngine;
  ctx: FakeContext | null;
  fetched: string[];
  saved: boolean[];
  /** The volume shares saved, in order. */
  savedVolume: number[];
  /** Files that fail to download. */
  missing: Set<string>;
  aborted: string[];
}

function rig(opts: { muted?: boolean; noAudio?: boolean; volume?: number } = {}): Rig {
  const r: Rig = {
    engine: null as unknown as MusicEngine,
    ctx: null,
    fetched: [],
    saved: [],
    savedVolume: [],
    missing: new Set(),
    aborted: [],
  };
  r.engine = new MusicEngine(
    {
      createContext: () => {
        if (opts.noAudio) return null;
        r.ctx = new FakeContext();
        return r.ctx as unknown as AudioContext;
      },
      fetchBytes: (url, signal) => {
        r.fetched.push(url);
        signal.addEventListener("abort", () => r.aborted.push(url));
        const key = url.replace(/^.*\/(\w+)\.mp3$/, "$1");
        if (r.missing.has(key)) return Promise.reject(new Error("404"));
        return Promise.resolve(new TextEncoder().encode(key).buffer as ArrayBuffer);
      },
      saveMuted: (m) => r.saved.push(m),
      saveVolume: (v) => r.savedVolume.push(v),
    },
    { supported: !opts.noAudio, muted: opts.muted ?? false, volume: opts.volume },
  );
  return r;
}

async function settle() {
  for (let i = 0; i < 20; i++) await Promise.resolve();
}

const plan = (e: MusicEngine, cur: MusicKey, load: MusicKey[] = [cur], keep: MusicKey[] = load) => e.setPlan(cur, load, keep);

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("MusicEngine", () => {
  it("does nothing before the first gesture, then starts the wanted track", async () => {
    const r = rig();
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate", ["gate", "mirror"]);
    expect(r.engine.snapshot()).toEqual({ available: true, on: false, muted: false, volume: 1 });
    expect(r.ctx).toBeNull();
    expect(r.fetched).toEqual([]);

    r.engine.gesture();
    expect(r.ctx).not.toBeNull();
    expect(r.engine.snapshot().on).toBe(true);
    expect(r.ctx!.master.gain.aim).toBe(MASTER_GAIN);
    // One download at a time, the current track first.
    expect(r.fetched).toEqual(["/sect/audio/gate.mp3"]);
    await settle();
    expect(r.fetched).toEqual(["/sect/audio/gate.mp3", "/sect/audio/mirror.mp3"]);

    const [src] = r.ctx!.playing("gate");
    expect(src.loop).toBe(true);
    expect([src.loopStart, src.loopEnd]).toEqual([2.5, 150]);
    expect(src.started).toEqual([0, 0]);
    const s = r.engine.state();
    expect(s.context).toBe("running");
    expect(s.voices).toMatchObject([{ key: "gate", fadingTo: 1 }]);
    expect(s.history).toEqual([{ from: null, to: "gate", at: 0 }]);
  });

  it("crossfades to a new track and stops the old one once it is silent", async () => {
    const r = rig();
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate", ["gate", "mirror"], ["gate", "mirror", "forge"]);
    r.engine.gesture();
    await settle();
    r.ctx!.currentTime = 10;
    plan(r.engine, "forge", ["forge", "arena"], ["forge", "arena", "mirror"]);
    // Gate keeps playing until the forge's track has arrived.
    expect(r.engine.state().voices.map((v) => v.key)).toEqual(["gate"]);
    await settle();
    const voices = r.engine.state().voices;
    expect(voices.map((v) => [v.key, v.fadingTo])).toEqual([
      ["gate", 0],
      ["forge", 1],
    ]);
    // Equal-power ramps: the incoming gain ends at 1, the outgoing at 0, over the crossfade.
    const gateGain = r.ctx!.gains[1].gain;
    // The fade-in's past events stay; the fade-out starts from full at t = 10.
    expect(gateGain.events.filter((e) => e.t >= 10)[0]).toEqual({ type: "set", v: 1, t: 10 });
    expect(gateGain.aim).toBe(0);
    expect(gateGain.events.at(-1)!.t).toBeCloseTo(12.5);

    r.ctx!.currentTime = 11;
    r.engine.tick();
    expect(r.ctx!.playing("gate")).toHaveLength(1);
    r.ctx!.currentTime = 12.6;
    r.engine.tick();
    expect(r.ctx!.playing("gate")).toHaveLength(0);
    // The gate's buffer is far from the camera now: freed.
    expect(r.engine.state().buffers).not.toContain("gate");
    expect(r.engine.state().history.map((h) => [h.from, h.to])).toEqual([
      [null, "gate"],
      ["gate", "forge"],
    ]);
  });

  it("reverses a fade part way, from where it is", async () => {
    const r = rig();
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate", ["gate", "mirror"], ["gate", "mirror"]);
    r.engine.gesture();
    await settle();
    r.ctx!.currentTime = 20;
    plan(r.engine, "mirror", ["mirror"], ["mirror", "gate"]);
    r.ctx!.currentTime = 21.25;
    plan(r.engine, "gate", ["gate"], ["gate", "mirror"]);
    const [gate, mirror] = r.engine.state().voices;
    expect(gate).toMatchObject({ key: "gate", fadingTo: 1 });
    expect(gate.gain).toBeCloseTo(Math.SQRT1_2, 3);
    expect(gate.fadeSeconds).toBeCloseTo(1.25, 3);
    expect(mirror).toMatchObject({ key: "mirror", fadingTo: 0 });
  });

  it("plays at the visitor's saved volume, and the slider moves the master quickly", () => {
    const r = rig({ volume: 0.5 });
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate");
    expect(r.engine.snapshot().volume).toBe(0.5);
    r.engine.gesture();
    // The square of the share: half way is a quarter of the level.
    expect(r.ctx!.master.gain.aim).toBeCloseTo(MASTER_GAIN * 0.25);

    r.ctx!.currentTime = 3;
    r.engine.setVolume(0.8);
    const last = r.ctx!.master.gain.events.at(-1)!;
    expect(last).toMatchObject({ type: "target", t: 3, tc: VOLUME_TIME_CONSTANT });
    expect(last.v).toBeCloseTo(MASTER_GAIN * 0.64);
    expect(r.engine.snapshot().volume).toBe(0.8);
    expect(r.savedVolume).toEqual([0.8]);
    // The same value again saves nothing and schedules nothing.
    const n = r.ctx!.master.gain.events.length;
    r.engine.setVolume(0.8);
    expect(r.ctx!.master.gain.events.length).toBe(n);
    expect(r.savedVolume).toEqual([0.8]);
    // Out-of-range values are clamped.
    r.engine.setVolume(7);
    expect(r.engine.snapshot().volume).toBe(1);
    expect(r.ctx!.master.gain.aim).toBeCloseTo(MASTER_GAIN);
  });

  it("is the master: the ducking takes its share of the slider's level", () => {
    const r = rig({ volume: 0.6 });
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate");
    r.engine.gesture();
    r.engine.setVoice("call");
    expect(r.ctx!.master.gain.aim).toBeCloseTo(MASTER_GAIN * 0.36 * VOICE_DUCK.call);
    r.engine.setVolume(0.3);
    expect(r.ctx!.master.gain.aim).toBeCloseTo(MASTER_GAIN * 0.09 * VOICE_DUCK.call);
    r.engine.setVoice("speaking");
    expect(r.ctx!.master.gain.aim).toBeCloseTo(MASTER_GAIN * 0.09 * VOICE_DUCK.speaking);
    // A ducking move keeps its own pace; only the slider's moves are quick.
    expect(r.ctx!.master.gain.events.at(-1)!.tc).not.toBe(VOLUME_TIME_CONSTANT);
    r.engine.setVoice("none");
    expect(r.ctx!.master.gain.aim).toBeCloseTo(MASTER_GAIN * 0.09);
  });

  it("stays silent at any volume under a video or muted, and keeps the volume for later", () => {
    const r = rig();
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate");
    r.engine.gesture();
    r.engine.setVideo(true);
    r.engine.setVolume(0.4);
    expect(r.ctx!.master.gain.aim).toBe(0);
    r.engine.setVideo(false);
    expect(r.ctx!.master.gain.aim).toBeCloseTo(MASTER_GAIN * 0.16);
    r.engine.toggle();
    expect(r.engine.snapshot()).toMatchObject({ on: false, muted: true, volume: 0.4 });
    expect(r.ctx!.master.gain.aim).toBe(0);
    // Volume 0 is silence too, without muting.
    r.engine.toggle();
    r.engine.setVolume(0);
    expect(r.engine.snapshot()).toMatchObject({ on: true, muted: false, volume: 0 });
    expect(r.ctx!.master.gain.aim).toBe(0);
  });

  it("ducks under a voice call, lower while the agent speaks, and comes back", async () => {
    const r = rig();
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate");
    r.engine.gesture();
    r.engine.setVoice("call");
    expect(r.ctx!.master.gain.aim).toBeCloseTo(MASTER_GAIN * VOICE_DUCK.call);
    r.engine.setVoice("speaking");
    expect(r.ctx!.master.gain.aim).toBeCloseTo(MASTER_GAIN * VOICE_DUCK.speaking);
    r.engine.setVoice("call");
    expect(r.ctx!.master.gain.aim).toBeCloseTo(MASTER_GAIN * VOICE_DUCK.call);
    r.engine.setVoice("none");
    expect(r.ctx!.master.gain.aim).toBe(MASTER_GAIN);
    // A duck never suspends anything: the call is short, and the music carries on under it.
    expect(r.ctx!.state).toBe("running");
  });

  it("steps aside while a video plays: fades out, rests, and picks up where it was", async () => {
    const r = rig();
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate");
    r.engine.gesture();
    await settle();
    expect(r.ctx!.playing("gate")).toHaveLength(1);
    r.ctx!.currentTime = 40;
    r.engine.setVideo(true);
    expect(r.ctx!.master.gain.aim).toBe(0);
    expect(r.engine.state().video).toBe(true);
    // A short pause does not stop the track; a long video lets the context rest.
    vi.advanceTimersByTime(1600);
    expect(r.ctx!.state).toBe("suspended");
    expect(r.ctx!.playing("gate")).toHaveLength(0);
    r.ctx!.currentTime = 41;
    r.engine.setVideo(false);
    expect(r.ctx!.state).toBe("running");
    expect(r.ctx!.master.gain.aim).toBe(MASTER_GAIN);
    const again = r.ctx!.playing("gate");
    expect(again).toHaveLength(1);
    // From where it stopped (40 s in), not from the top.
    expect(again[0].started![1]).toBeCloseTo(40, 3);
  });

  it("stays silent under a video even when sound is turned on or the call ends", async () => {
    const r = rig();
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate");
    r.engine.setVideo(true);
    r.engine.toggle();
    expect(r.engine.snapshot().on).toBe(true);
    expect(r.ctx!.master.gain.aim).toBe(0);
    r.engine.setVoice("speaking");
    r.engine.setVoice("none");
    expect(r.ctx!.master.gain.aim).toBe(0);
    r.engine.setVideo(false);
    expect(r.ctx!.master.gain.aim).toBe(MASTER_GAIN);
  });

  it("mutes from the toggle, saves it, and rests the context after the fade", async () => {
    const r = rig();
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate");
    r.engine.gesture();
    await settle();
    r.engine.toggle();
    expect(r.saved).toEqual([true]);
    expect(r.engine.snapshot()).toMatchObject({ on: false, muted: true });
    expect(r.ctx!.master.gain.aim).toBe(0);
    expect(r.ctx!.state).toBe("running");
    vi.advanceTimersByTime(1600);
    expect(r.ctx!.state).toBe("suspended");
    expect(r.ctx!.playing("gate")).toHaveLength(0);

    // Back on: resumes and picks the track up again with a fade-in.
    r.ctx!.currentTime = 30;
    r.engine.toggle();
    expect(r.saved).toEqual([true, false]);
    expect(r.ctx!.state).toBe("running");
    expect(r.ctx!.master.gain.aim).toBe(MASTER_GAIN);
    expect(r.ctx!.playing("gate")).toHaveLength(1);
  });

  it("a saved mute keeps everything off until the toggle", async () => {
    const r = rig({ muted: true });
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate");
    r.engine.gesture();
    expect(r.ctx).toBeNull();
    expect(r.fetched).toEqual([]);
    expect(r.engine.snapshot()).toEqual({ available: true, on: false, muted: true, volume: 1 });
    r.engine.toggle();
    expect(r.saved).toEqual([false]);
    expect(r.engine.snapshot().on).toBe(true);
    expect(r.fetched).toEqual(["/sect/audio/gate.mp3"]);
  });

  it("the toggle is also the first gesture: sound on, not off", () => {
    const r = rig();
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate");
    r.engine.toggle();
    expect(r.engine.snapshot().on).toBe(true);
    expect(r.saved).toEqual([false]);
  });

  it("dips to silence and suspends while the tab is hidden, and resumes", async () => {
    const r = rig();
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate");
    r.engine.gesture();
    await settle();
    r.engine.setHidden(true);
    // A quick dip first (cutting the output at full level clicks), then the suspend.
    expect(r.ctx!.master.gain.aim).toBe(0);
    expect(r.ctx!.master.gain.events.at(-1)).toMatchObject({ type: "target", v: 0 });
    expect(r.ctx!.state).toBe("running");
    vi.advanceTimersByTime(200);
    expect(r.ctx!.state).toBe("suspended");
    expect(r.ctx!.playing("gate")).toHaveLength(1);
    r.engine.setHidden(false);
    expect(r.ctx!.state).toBe("running");
    expect(r.ctx!.master.gain.aim).toBe(MASTER_GAIN);
  });

  it("a tab shown again before the dip ends does not suspend", async () => {
    const r = rig();
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate");
    r.engine.gesture();
    await settle();
    r.engine.setHidden(true);
    vi.advanceTimersByTime(50);
    r.engine.setHidden(false);
    vi.advanceTimersByTime(500);
    expect(r.ctx!.suspends).toBe(0);
    expect(r.ctx!.master.gain.aim).toBe(MASTER_GAIN);
  });

  it("rests in the page view", async () => {
    const r = rig();
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate");
    r.engine.gesture();
    await settle();
    r.engine.setAway(true);
    expect(r.ctx!.master.gain.aim).toBe(0);
    vi.advanceTimersByTime(1600);
    expect(r.ctx!.state).toBe("suspended");
    r.engine.setAway(false);
    expect(r.ctx!.state).toBe("running");
  });

  it("a missing file leaves the music as it is, and is not fetched again", async () => {
    const r = rig();
    r.missing.add("forge");
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate", ["gate"], ["gate", "forge"]);
    r.engine.gesture();
    await settle();
    plan(r.engine, "forge", ["forge"], ["forge", "gate"]);
    await settle();
    expect(r.engine.state().failed).toEqual(["forge"]);
    expect(r.engine.state().voices.map((v) => [v.key, v.fadingTo])).toEqual([["gate", 1]]);
    r.engine.tick();
    await settle();
    expect(r.fetched.filter((u) => u.includes("forge"))).toHaveLength(1);
  });

  it("cancels a download the camera has left behind", () => {
    const r = rig();
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate");
    r.engine.gesture();
    // Still downloading (no settle): the camera is suddenly far away.
    plan(r.engine, "mission", ["mission"], ["mission"]);
    expect(r.aborted).toEqual(["/sect/audio/gate.mp3"]);
    expect(r.fetched.at(-1)).toBe("/sect/audio/mission.mp3");
  });

  it("cancels a download for a place just left, even one it would keep once decoded", () => {
    const r = rig();
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate", ["gate", "mirror"], ["gate", "mirror"]);
    r.engine.gesture();
    // Still downloading the gate's track (a slow line) when the camera reaches the mirror: the
    // gate is the track just passed (kept if it were decoded) but no longer worth the wait.
    plan(r.engine, "mirror", ["mirror", "forge"], ["mirror", "forge", "gate"]);
    expect(r.aborted).toEqual(["/sect/audio/gate.mp3"]);
    expect(r.fetched.at(-1)).toBe("/sect/audio/mirror.mp3");
  });

  it("without Web Audio there is no toggle and nothing throws", () => {
    const r = rig({ noAudio: true });
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate");
    expect(() => {
      r.engine.gesture();
      r.engine.toggle();
      r.engine.tick();
    }).not.toThrow();
    expect(r.engine.snapshot().available).toBe(false);
  });

  it("without a track list there is no toggle and no context", () => {
    const r = rig();
    r.engine.setManifest(null);
    plan(r.engine, "gate");
    r.engine.gesture();
    expect(r.engine.snapshot().available).toBe(false);
    expect(r.ctx).toBeNull();
  });

  it("dispose dips to silence, then closes the context and stops everything", async () => {
    const r = rig();
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate");
    r.engine.gesture();
    await settle();
    r.engine.dispose();
    expect(r.ctx!.master.gain.aim).toBe(0);
    expect(r.ctx!.state).toBe("running");
    vi.advanceTimersByTime(200);
    expect(r.ctx!.state).toBe("closed");
    expect(r.ctx!.playing("gate")).toHaveLength(0);
    expect(() => r.engine.gesture()).not.toThrow();
  });

  it("dispose closes at once when nothing is audible", async () => {
    const r = rig();
    r.engine.setManifest(MANIFEST);
    plan(r.engine, "gate");
    r.engine.gesture();
    await settle();
    r.engine.toggle();
    vi.advanceTimersByTime(1600);
    r.engine.dispose();
    expect(r.ctx!.state).toBe("closed");
  });
});
