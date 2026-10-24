/**
 * The Web Audio side of /sect's music (the choices are lib/sect/music.ts; the page wiring
 * ./music.tsx). One AudioContext, made on the visitor's first gesture; per track a fetched and
 * decoded AudioBuffer played by a looping AudioBufferSourceNode through its own gain (the
 * crossfade), all into one master gain (the visitor's volume slider, mute, ducking under a voice
 * call, silence under a YouTube demo).
 *
 * Nothing here throws: without Web Audio, without music.json, or when a file fails, the page simply
 * has no music. Nothing is downloaded until the visitor's first gesture with sound on, and then only
 * the current track and the next one along the flight.
 */
import {
  equalPowerFade,
  fadeDone,
  fadeGainAt,
  fadePoints,
  loopBounds,
  loopPosition,
  masterTarget,
  masterTimeConstant,
  VOLUME_TIME_CONSTANT,
  type Fade,
  type MusicKey,
  type MusicManifest,
  type VoiceDuck,
} from "@/lib/sect/music";
import { DEFAULT_VOLUME, clampVolume } from "@/lib/sect/volume";

/** What the sound toggle shows. */
export interface MusicUi {
  /** Web Audio works and music.json lists at least one track: the toggle shows. */
  available: boolean;
  /** Sound is on: the visitor has given a gesture and has not muted. */
  on: boolean;
  muted: boolean;
  /** The volume slider's share, 0 to 1 (lib/sect/volume.ts). */
  volume: number;
}

export interface MusicDeps {
  /** Makes the AudioContext (called inside a gesture), or null without Web Audio. */
  createContext: () => AudioContext | null;
  /** Downloads a track's bytes. */
  fetchBytes: (url: string, signal: AbortSignal) => Promise<ArrayBuffer>;
  /** Saves the mute choice. */
  saveMuted: (muted: boolean) => void;
  /** Saves the volume slider's share. */
  saveVolume?: (volume: number) => void;
}

interface Voice {
  key: MusicKey;
  src: AudioBufferSourceNode;
  gain: GainNode;
  fade: Fade;
  /** Audio-clock time the track's top would have played at (position = now - startedAt). */
  startedAt: number;
  loopStart: number;
  loopEnd: number;
}

/** After going silent (mute, the page view) the context suspends once the fade-out has finished. */
const SUSPEND_AFTER_MS = 1500;
/**
 * A hidden tab, or leaving /sect: the master dips to silence this fast (setTargetAtTime's time
 * constant) and the context suspends or closes once it is there. Stopping the output at full level
 * clicks; five time constants leave under 1% of the level.
 */
const QUICK_FADE_TC = 0.02;
const QUICK_FADE_MS = 120;
/** Track changes the debug state remembers. */
const HISTORY = 20;

export class MusicEngine {
  private readonly deps: MusicDeps;
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private masterAim = -1;
  private manifest: MusicManifest | null = null;
  private supported: boolean;
  private gestured = false;
  private muted: boolean;
  private volume: number;
  /** The next master move is the volume slider's: it follows quickly (VOLUME_TIME_CONSTANT). */
  private volumeMoved = false;
  private voice: VoiceDuck = "none";
  private video = false;
  private away = false;
  private hidden = false;
  private wanted: MusicKey | null = null;
  private loadKeys: MusicKey[] = [];
  private keepKeys: MusicKey[] = [];
  private readonly buffers = new Map<MusicKey, AudioBuffer>();
  private readonly pending = new Map<MusicKey, AbortController>();
  private readonly failed = new Set<MusicKey>();
  private readonly voices = new Map<MusicKey, Voice>();
  private readonly positions = new Map<MusicKey, number>();
  private suspendTimer: ReturnType<typeof setTimeout> | null = null;
  private hideTimer: ReturnType<typeof setTimeout> | null = null;
  private disposed = false;
  private readonly listeners = new Set<() => void>();
  private ui: MusicUi;
  /** Track changes heard (a crossfade started), newest last: for the debug state. */
  private readonly history: { from: MusicKey | null; to: MusicKey; at: number }[] = [];
  private lastStarted: MusicKey | null = null;

  constructor(deps: MusicDeps, opts: { supported: boolean; muted: boolean; volume?: number }) {
    this.deps = deps;
    this.supported = opts.supported;
    this.muted = opts.muted;
    this.volume = clampVolume(opts.volume ?? DEFAULT_VOLUME);
    this.ui = { available: false, on: false, muted: opts.muted, volume: this.volume };
  }

  // --- the toggle's store (useSyncExternalStore) ---------------------------------------------------

  subscribe = (fn: () => void): (() => void) => {
    this.listeners.add(fn);
    return () => {
      this.listeners.delete(fn);
    };
  };

  snapshot = (): MusicUi => this.ui;

  private emit(): void {
    const next: MusicUi = {
      available: this.supported && this.manifest !== null,
      on: this.supported && this.ctx !== null && this.gestured && !this.muted,
      muted: this.muted,
      volume: this.volume,
    };
    const ui = this.ui;
    if (next.available === ui.available && next.on === ui.on && next.muted === ui.muted && next.volume === ui.volume) return;
    this.ui = next;
    for (const fn of this.listeners) fn();
  }

  // --- inputs ------------------------------------------------------------------------------------------

  /** The track list has this track. */
  has(key: MusicKey): boolean {
    return this.manifest?.tracks[key] !== undefined;
  }

  setManifest(m: MusicManifest | null): void {
    if (this.disposed) return;
    this.manifest = m;
    // A gesture before the list arrived: the context can start now (the page has been activated).
    if (m && this.gestured && !this.muted) this.ensureContext();
    this.apply();
    this.emit();
  }

  /** A user gesture anywhere on the page (not on the toggle): start the music unless muted. */
  gesture(): void {
    if (this.disposed || !this.supported) return;
    this.gestured = true;
    if (this.muted || !this.manifest) return;
    this.ensureContext();
    this.apply();
    this.emit();
  }

  /** The sound toggle: sound on (which is also the first gesture), or off. */
  toggle(): void {
    if (this.disposed || !this.supported) return;
    const on = this.ctx !== null && this.gestured && !this.muted;
    this.gestured = true;
    this.muted = on;
    this.deps.saveMuted(this.muted);
    if (!this.muted) this.ensureContext();
    this.apply();
    this.emit();
  }

  /**
   * The volume slider: a share 0 to 1 of the music's level, the master the ducking multiplies. Saved
   * for the visitor. Changes nothing else: muted stays muted (the slider shows only while sound is
   * on), and a voice call or a video still takes its share.
   */
  setVolume(v: number): void {
    if (this.disposed) return;
    const next = clampVolume(v);
    if (next === this.volume) return;
    this.volume = next;
    this.deps.saveVolume?.(next);
    this.volumeMoved = true;
    this.apply();
    this.volumeMoved = false;
    this.emit();
  }

  /** A voice call's hold on the music (the talisman's state: see voiceDuck). */
  setVoice(v: VoiceDuck): void {
    if (v === this.voice) return;
    this.voice = v;
    this.apply();
  }

  /**
   * A YouTube demo plays: the music fades out and rests, as for the page view (the tracks stop where
   * they are after the fade), and comes back when the video pauses or ends.
   */
  setVideo(v: boolean): void {
    if (v === this.video) return;
    this.video = v;
    this.apply();
  }

  /** The page view (or an error) covers the flight: the music fades out and rests. */
  setAway(v: boolean): void {
    if (v === this.away) return;
    this.away = v;
    this.apply();
  }

  /** The tab is hidden: suspend at once (and resume when it shows again). */
  setHidden(v: boolean): void {
    if (v === this.hidden) return;
    this.hidden = v;
    this.apply();
  }

  /**
   * The track the camera wants (after the hysteresis), what to fetch now (current, then next) and
   * which decoded buffers to keep.
   */
  setPlan(wanted: MusicKey | null, load: readonly MusicKey[], keep: readonly MusicKey[]): void {
    this.wanted = wanted;
    this.loadKeys = [...load];
    this.keepKeys = [...keep];
    this.apply();
  }

  /** Called a few times a second: retires finished fade-outs and frees what is no longer needed. */
  tick(): void {
    this.apply();
  }

  // --- the work ----------------------------------------------------------------------------------------

  private ensureContext(): void {
    if (this.ctx || !this.supported) return;
    let ctx: AudioContext | null = null;
    try {
      ctx = this.deps.createContext();
    } catch {
      ctx = null;
    }
    if (!ctx) {
      this.supported = false;
      this.emit();
      return;
    }
    try {
      const master = ctx.createGain();
      master.gain.value = 0;
      master.connect(ctx.destination);
      this.ctx = ctx;
      this.master = master;
      this.masterAim = 0;
    } catch {
      this.supported = false;
      void ctx.close?.().catch(() => {});
      this.emit();
    }
  }

  /** Sound should be coming out now. */
  private live(): boolean {
    return this.ctx !== null && this.gestured && !this.muted && !this.away && !this.video && !this.hidden && this.manifest !== null;
  }

  private apply(): void {
    const ctx = this.ctx;
    if (this.disposed || !ctx || !this.master) return;
    const now = ctx.currentTime;
    const live = this.live();

    // The context: running while live; suspended when hidden after a quick dip, else after the fade-out.
    if (this.hidden) {
      this.clearSuspendTimer();
      if (ctx.state === "running" && this.hideTimer === null) {
        this.hideTimer = setTimeout(() => {
          this.hideTimer = null;
          if (this.disposed || !this.hidden || !this.ctx || this.ctx.state !== "running") return;
          void this.ctx.suspend().catch(() => {});
        }, QUICK_FADE_MS);
      }
    } else if (live) {
      this.clearSuspendTimer();
      this.clearHideTimer();
      if (ctx.state !== "running" && ctx.state !== "closed") void ctx.resume().catch(() => {});
    } else if (ctx.state === "running" && this.suspendTimer === null) {
      this.clearHideTimer();
      this.suspendTimer = setTimeout(() => {
        this.suspendTimer = null;
        if (this.disposed || this.live() || !this.ctx) return;
        // Silent for good: the tracks stop where they are (they pick up there next time).
        for (const v of [...this.voices.values()]) this.stopVoice(v, this.ctx.currentTime);
        void this.ctx.suspend().catch(() => {});
      }, SUSPEND_AFTER_MS);
    }

    // The master level (a hidden tab dips to silence fast, then suspends; it comes back gently).
    const aim = live
      ? masterTarget({ muted: this.muted, volume: this.volume, voice: this.voice, video: this.video, away: this.away })
      : 0;
    if (aim !== this.masterAim) {
      const p = this.master.gain;
      const from = this.masterAim < 0 ? 0 : this.masterAim;
      const tc = this.hidden ? QUICK_FADE_TC : this.volumeMoved ? VOLUME_TIME_CONSTANT : masterTimeConstant(from, aim);
      try {
        p.cancelScheduledValues(now);
        p.setTargetAtTime(aim, now, tc);
      } catch {
        p.value = aim;
      }
      this.masterAim = aim;
    }

    // The crossfade: the wanted track in (once decoded), every other one out.
    if (live && this.wanted && this.buffers.has(this.wanted)) {
      let v = this.voices.get(this.wanted);
      if (!v) v = this.startVoice(this.wanted, now) ?? undefined;
      if (v) {
        this.fadeVoice(v, 1, now);
        for (const o of this.voices.values()) if (o !== v) this.fadeVoice(o, 0, now);
      }
    }

    // Fade-outs that are over: stop them.
    for (const v of [...this.voices.values()]) if (v.fade.to === 0 && fadeDone(v.fade, now)) this.stopVoice(v, now);

    // Memory: buffers nobody wants any more.
    const keep = new Set<MusicKey>([...this.keepKeys, ...this.voices.keys()]);
    if (this.wanted) keep.add(this.wanted);
    for (const k of [...this.buffers.keys()]) if (!keep.has(k)) this.buffers.delete(k);
    // Downloads the plan no longer asks for (the camera has moved on): cancelled, so on a slow line
    // the track for where the camera is now comes next, not one for a place already left behind.
    const fetchNow = new Set<MusicKey>(this.loadKeys);
    if (this.wanted) fetchNow.add(this.wanted);
    for (const [k, ac] of [...this.pending]) {
      if (!fetchNow.has(k)) {
        ac.abort();
        this.pending.delete(k);
      }
    }

    // Downloads: one at a time, the current track first. Not while muted (nothing would play).
    if (this.gestured && !this.muted && this.pending.size === 0) {
      const next = this.loadKeys.find((k) => !this.buffers.has(k) && !this.failed.has(k) && this.manifest?.tracks[k]);
      if (next) this.load(next);
    }
  }

  private startVoice(key: MusicKey, now: number): Voice | null {
    const ctx = this.ctx;
    const buffer = this.buffers.get(key);
    const track = this.manifest?.tracks[key];
    if (!ctx || !this.master || !buffer || !track) return null;
    try {
      const { start, end } = loopBounds(track, buffer.duration);
      const src = ctx.createBufferSource();
      src.buffer = buffer;
      src.loop = true;
      src.loopStart = start;
      src.loopEnd = end;
      const gain = ctx.createGain();
      gain.gain.value = 0;
      src.connect(gain);
      gain.connect(this.master);
      const offset = Math.min(this.positions.get(key) ?? 0, Math.max(0, end - 0.05));
      src.start(now, offset);
      const v: Voice = { key, src, gain, fade: { from: 0, to: 0, t0: now, duration: 0 }, startedAt: now - offset, loopStart: start, loopEnd: end };
      this.voices.set(key, v);
      if (this.lastStarted !== key) {
        this.history.push({ from: this.lastStarted, to: key, at: now });
        if (this.history.length > HISTORY) this.history.shift();
        this.lastStarted = key;
      }
      return v;
    } catch {
      return null;
    }
  }

  private fadeVoice(v: Voice, to: number, now: number): void {
    if (v.fade.to === to) return;
    const from = fadeGainAt(v.fade, now);
    const f = equalPowerFade(from, to, now);
    const p = v.gain.gain;
    try {
      p.cancelScheduledValues(now);
      p.setValueAtTime(from, now);
      for (const pt of fadePoints(f)) p.linearRampToValueAtTime(pt.v, pt.t);
    } catch {
      p.value = to;
    }
    v.fade = f;
    if (to > 0 && this.lastStarted !== v.key) {
      // A fade-out reversed: this track is the one heard again.
      this.history.push({ from: this.lastStarted, to: v.key, at: now });
      if (this.history.length > HISTORY) this.history.shift();
      this.lastStarted = v.key;
    }
  }

  private stopVoice(v: Voice, now: number): void {
    this.positions.set(v.key, loopPosition(now - v.startedAt, v.loopStart, v.loopEnd));
    try {
      v.src.stop();
    } catch {
      // Already stopped.
    }
    try {
      v.src.disconnect();
      v.gain.disconnect();
    } catch {
      // Already disconnected.
    }
    this.voices.delete(v.key);
    if (this.lastStarted === v.key) this.lastStarted = null;
  }

  private load(key: MusicKey): void {
    const track = this.manifest?.tracks[key];
    const ctx = this.ctx;
    if (!track || !ctx) return;
    const ac = new AbortController();
    this.pending.set(key, ac);
    const done = () => {
      if (this.pending.get(key) === ac) this.pending.delete(key);
    };
    this.deps
      .fetchBytes(track.src, ac.signal)
      .then((bytes) => decode(ctx, bytes))
      .then((buffer) => {
        done();
        if (this.disposed || ac.signal.aborted) return;
        this.buffers.set(key, buffer);
        this.apply();
      })
      .catch(() => {
        done();
        if (this.disposed || ac.signal.aborted) return;
        // A missing or broken file: that place stays with whatever plays.
        this.failed.add(key);
        this.apply();
      });
  }

  private clearSuspendTimer(): void {
    if (this.suspendTimer !== null) {
      clearTimeout(this.suspendTimer);
      this.suspendTimer = null;
    }
  }

  private clearHideTimer(): void {
    if (this.hideTimer !== null) {
      clearTimeout(this.hideTimer);
      this.hideTimer = null;
    }
  }

  /** Leaving /sect: a quick dip to silence (when something is audible), then the context closes. */
  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.clearSuspendTimer();
    this.clearHideTimer();
    for (const ac of this.pending.values()) ac.abort();
    this.pending.clear();
    this.buffers.clear();
    this.listeners.clear();
    const ctx = this.ctx;
    const master = this.master;
    this.ctx = null;
    this.master = null;
    if (!ctx) return;
    const finish = () => {
      for (const v of [...this.voices.values()]) this.stopVoice(v, ctx.currentTime);
      void ctx.close().catch(() => {});
    };
    if (!master || ctx.state !== "running" || this.masterAim <= 0) {
      finish();
      return;
    }
    try {
      master.gain.cancelScheduledValues(ctx.currentTime);
      master.gain.setTargetAtTime(0, ctx.currentTime, QUICK_FADE_TC);
    } catch {
      // The context is going anyway.
    }
    setTimeout(finish, QUICK_FADE_MS);
  }

  /** For ?debug=1 (window.__sect.music.state()) and the tests. */
  state() {
    const ctx = this.ctx;
    const now = ctx?.currentTime ?? 0;
    return {
      supported: this.supported,
      tracks: this.manifest ? (Object.keys(this.manifest.tracks) as MusicKey[]) : [],
      context: ctx ? ctx.state : "none",
      time: now,
      gestured: this.gestured,
      muted: this.muted,
      volume: this.volume,
      voice: this.voice,
      video: this.video,
      away: this.away,
      hidden: this.hidden,
      wanted: this.wanted,
      master: { aim: this.masterAim, value: this.master ? this.master.gain.value : 0 },
      voices: [...this.voices.values()].map((v) => ({
        key: v.key,
        gain: Number(fadeGainAt(v.fade, now).toFixed(3)),
        fadingTo: v.fade.to,
        fadeSeconds: Number(v.fade.duration.toFixed(3)),
        position: Number(loopPosition(now - v.startedAt, v.loopStart, v.loopEnd).toFixed(2)),
        loop: [v.loopStart, v.loopEnd],
      })),
      buffers: [...this.buffers.keys()],
      loading: [...this.pending.keys()],
      failed: [...this.failed],
      history: this.history.map((h) => ({ ...h })),
    };
  }
}

/** decodeAudioData, promise or callback style (older Safari has only the callbacks). */
function decode(ctx: AudioContext, bytes: ArrayBuffer): Promise<AudioBuffer> {
  return new Promise<AudioBuffer>((resolve, reject) => {
    try {
      const p = ctx.decodeAudioData(bytes, resolve, reject) as Promise<AudioBuffer> | undefined;
      if (p && typeof p.then === "function") p.then(resolve, reject);
    } catch (e) {
      reject(e);
    }
  });
}
