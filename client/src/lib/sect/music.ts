/**
 * Background music for /sect: which track plays where, when it changes, how it fades and how loud
 * it is. Pure functions with plain inputs; the Web Audio side is app/sect/experience/music-engine.ts
 * and the page wiring app/sect/experience/music.tsx.
 *
 * One track per area (the area ids of ./areas.ts) plus "loading" for the loading screen, all in
 * public/sect/audio/<key>.mp3 and listed in public/sect/audio/music.json with their loop points
 * (music/sect-themes/README.md). Every track is in the same five notes, so two can overlap during a
 * crossfade without clashing.
 */
import { AREA_IDS, isAreaId, type AreaId } from "./areas";

export type MusicKey = "loading" | AreaId;

/** The loading screen's track, then the areas in flight order. */
export const MUSIC_KEYS: readonly MusicKey[] = ["loading", ...AREA_IDS];

export function isMusicKey(value: string): value is MusicKey {
  return value === "loading" || isAreaId(value);
}

/**
 * Where the page reads the track list: app/sect/music.json/route.ts serves
 * public/sect/audio/music.json (written by the audio pipeline next to the files), or an empty list.
 */
export const MUSIC_MANIFEST_URL = "/sect/music.json";
/** The folder the tracks' paths are relative to (they are normally absolute: "/sect/audio/gate.mp3"). */
export const MUSIC_DIR = "/sect/audio/";
/**
 * The files' sample rate, and the AudioContext's. decodeAudioData resamples to the context's rate,
 * and a context left at the sound card's default (96 kHz on some machines) doubles every decoded
 * track's memory (abode: 105 MB instead of 52). The browser resamples the output instead.
 */
export const MUSIC_SAMPLE_RATE = 48000;

export interface MusicTrack {
  /** Same-site path of the MP3 ("/sect/audio/gate.mp3"). */
  src: string;
  /** Seconds, as decodeAudioData returns the file. */
  duration: number;
  /** The loop: playback runs from 0 into the loop, then repeats loopStart..loopEnd seamlessly. */
  loopStart: number;
  loopEnd: number;
  bpm: number | null;
  lufs: number | null;
  bytes: number | null;
}

export interface MusicManifest {
  version: 1;
  tracks: Partial<Record<MusicKey, MusicTrack>>;
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** A path on this site: "/sect/audio/x.mp3" or "audio/x.mp3"; never another origin or a scheme. */
function sitePath(v: unknown): string | null {
  if (typeof v !== "string") return null;
  const s = v.trim();
  if (s.length === 0 || s.length > 200) return null;
  if (s.startsWith("//") || /^[a-z][a-z0-9+.-]*:/i.test(s) || s.includes("\\")) return null;
  return s;
}

/**
 * Reads music.json. Tracks with a bad path or duration are dropped; a track whose loop points make
 * no sense loops whole. Returns null when nothing usable is left (no music then, and no toggle).
 */
export function parseMusicManifest(raw: unknown): MusicManifest | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as { version?: unknown; tracks?: unknown };
  if (r.version !== 1 || !r.tracks || typeof r.tracks !== "object") return null;
  const tracks: Partial<Record<MusicKey, MusicTrack>> = {};
  let n = 0;
  for (const [key, value] of Object.entries(r.tracks as Record<string, unknown>)) {
    if (!isMusicKey(key) || !value || typeof value !== "object") continue;
    const t = value as Record<string, unknown>;
    const src = sitePath(t.src);
    const duration = num(t.duration);
    if (!src || duration === null || duration <= 0) continue;
    let loopStart = num(t.loopStart) ?? 0;
    let loopEnd = num(t.loopEnd) ?? duration;
    if (loopStart < 0 || loopEnd <= loopStart || loopEnd > duration + 0.05) {
      loopStart = 0;
      loopEnd = duration;
    }
    tracks[key] = { src, duration, loopStart, loopEnd, bpm: num(t.bpm), lufs: num(t.lufs), bytes: num(t.bytes) };
    n++;
  }
  return n > 0 ? { version: 1, tracks } : null;
}

/** Shortest loop worth looping; anything shorter loops the whole buffer. */
const MIN_LOOP_SECONDS = 1;

/**
 * The loop points for a decoded buffer: the manifest's, kept inside the buffer (a decoder can make
 * the file a few milliseconds shorter than the manifest says).
 */
export function loopBounds(track: Pick<MusicTrack, "loopStart" | "loopEnd">, bufferDuration: number): { start: number; end: number } {
  const end = Math.min(track.loopEnd, bufferDuration);
  const start = Math.max(0, track.loopStart);
  if (!(end - start >= MIN_LOOP_SECONDS)) return { start: 0, end: bufferDuration };
  return { start, end };
}

/**
 * Where in the file a track is after playing for `elapsed` seconds from the top: straight through
 * to the loop's end, then round the loop.
 */
export function loopPosition(elapsed: number, loopStart: number, loopEnd: number): number {
  const t = Math.max(0, elapsed);
  if (t < loopEnd) return t;
  const len = loopEnd - loopStart;
  if (!(len > 0)) return 0;
  return loopStart + ((t - loopStart) % len);
}

// --- which track ---------------------------------------------------------------------------------

/** An area's stretch of the flight (meta.json areas, or a hold's frame). */
export interface AreaSpan {
  id: string;
  frameStart: number;
  frameEnd: number;
}

/**
 * The area whose frame range holds `frame`; between areas (or past the ends), the nearer one. Null
 * without any area.
 */
export function areaAtFrame(spans: readonly AreaSpan[], frame: number): AreaId | null {
  let best: AreaId | null = null;
  let dist = Infinity;
  for (const s of spans) {
    if (!isAreaId(s.id)) continue;
    const lo = Math.min(s.frameStart, s.frameEnd);
    const hi = Math.max(s.frameStart, s.frameEnd);
    const d = frame < lo ? lo - frame : frame > hi ? frame - hi : 0;
    if (d < dist) {
      dist = d;
      best = s.id;
      if (d === 0) break;
    }
  }
  return best;
}

/**
 * The spans music follows: meta.json's area ranges, or (older files without them) each hold's frame
 * alone, so the nearest hold wins.
 */
export function musicSpans(areas: readonly AreaSpan[] | null | undefined, holds: readonly { id: string; frame: number }[]): AreaSpan[] {
  const fromAreas = (areas ?? []).filter((a) => isAreaId(a.id) && Number.isFinite(a.frameStart) && Number.isFinite(a.frameEnd));
  if (fromAreas.length > 0) return fromAreas.map((a) => ({ id: a.id, frameStart: a.frameStart, frameEnd: a.frameEnd }));
  return holds.filter((h) => isAreaId(h.id)).map((h) => ({ id: h.id, frameStart: h.frame, frameEnd: h.frame }));
}

/** The track for this moment: the loading screen's while it is up, else the area the camera is in. */
export function wantedTrack(loading: boolean, frame: number | null, spans: readonly AreaSpan[]): MusicKey | null {
  if (loading) return "loading";
  if (frame === null || !Number.isFinite(frame)) return null;
  return areaAtFrame(spans, frame);
}

// --- when it changes (hysteresis) --------------------------------------------------------------

/** A new area's track takes over once the camera has been in that area this long... */
export const SWITCH_HOLD_SECONDS = 0.6;

export interface Switcher {
  /** The track that plays (or will, once it has loaded). */
  current: MusicKey | null;
  /** Another track the camera is in now, waiting out the hold. */
  pending: MusicKey | null;
  /** When `pending` became the target (seconds). */
  since: number;
  /** How many times `current` has changed (the first track counts too). */
  switches: number;
}

export function createSwitcher(): Switcher {
  return { current: null, pending: null, since: 0, switches: 0 };
}

/**
 * One step of the track choice. The first track starts at once. After that a different target
 * takes over only when it has stayed the target for `hold` seconds, or at once when the camera has
 * settled (scroll at rest): a fast scroll through several areas plays none of the ones in between.
 * A null target (no track for this place) changes nothing.
 */
export function stepSwitcher(s: Switcher, target: MusicKey | null, now: number, settled: boolean, hold = SWITCH_HOLD_SECONDS): Switcher {
  if (target === null) return s.pending === null ? s : { ...s, pending: null };
  if (s.current === null) return { current: target, pending: null, since: now, switches: s.switches + 1 };
  if (target === s.current) return s.pending === null ? s : { ...s, pending: null };
  const since = s.pending === target ? s.since : now;
  if (settled || now - since >= hold) return { current: target, pending: null, since: now, switches: s.switches + 1 };
  return s.pending === target ? s : { ...s, pending: target, since };
}

// --- crossfades ------------------------------------------------------------------------------------

/** A full crossfade (silence to full, or back). */
export const CROSSFADE_SECONDS = 2.5;

/**
 * A gain moving between two levels along the equal-power curve: gain = sin(angle) with the angle
 * moving linearly in time. A track fading in from 0 to 1 follows sin, one fading out from 1 to 0
 * follows cos, so the two together keep the same loudness through the crossfade. A fade that
 * starts part way (a reversal) takes only the part of the full time its angle still has to go.
 */
export interface Fade {
  from: number;
  to: number;
  /** Start (audio clock seconds). */
  t0: number;
  duration: number;
}

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);
const angleOf = (g: number) => Math.asin(clamp01(g));

export function equalPowerFade(from: number, to: number, t0: number, full = CROSSFADE_SECONDS): Fade {
  const a0 = angleOf(from);
  const a1 = angleOf(to);
  return { from: clamp01(from), to: clamp01(to), t0, duration: (full * Math.abs(a1 - a0)) / (Math.PI / 2) };
}

/** A fade's gain at time t (held at `from` before it starts and at `to` once it is over). */
export function fadeGainAt(f: Fade, t: number): number {
  if (f.duration <= 0 || t >= f.t0 + f.duration) return f.to;
  if (t <= f.t0) return f.from;
  const p = (t - f.t0) / f.duration;
  const a0 = angleOf(f.from);
  const a1 = angleOf(f.to);
  return Math.sin(a0 + (a1 - a0) * p);
}

export function fadeDone(f: Fade, t: number): boolean {
  return t >= f.t0 + f.duration;
}

/**
 * The fade as points for linearRampToValueAtTime (the start value is set at t0 separately). Short
 * linear pieces rather than setValueCurveAtTime: a ramp's event sits at its end, so
 * cancelScheduledValues(now) removes a fade under way and a reversal can start from where it is.
 */
export function fadePoints(f: Fade, steps = 16): { t: number; v: number }[] {
  if (f.duration <= 0) return [{ t: f.t0, v: f.to }];
  const n = Math.max(1, Math.round(steps * (f.duration / CROSSFADE_SECONDS)));
  const out: { t: number; v: number }[] = [];
  for (let i = 1; i <= n; i++) {
    const t = f.t0 + (f.duration * i) / n;
    out.push({ t, v: i === n ? f.to : fadeGainAt(f, t) });
  }
  return out;
}

// --- how loud --------------------------------------------------------------------------------------

/** Music under the scene: about half of full scale (the files themselves sit at -17 LUFS). */
export const MASTER_GAIN = 0.5;

/**
 * What a voice call does to the music (the talisman's state, lib/sect/talisman.ts): nothing; "call"
 * while one connects or the agent listens; "speaking" while the agent talks. Text chat leaves it.
 */
export type VoiceDuck = "none" | "call" | "speaking";

/** The music's share of its level under a call: low enough to talk over, lower under the agent's voice. */
export const VOICE_DUCK: Record<VoiceDuck, number> = { none: 1, call: 0.35, speaking: 0.15 };

export function voiceDuck(talisman: string | null | undefined): VoiceDuck {
  switch (talisman) {
    case "connecting":
    case "listening":
      return "call";
    case "speaking":
      return "speaking";
    default:
      return "none";
  }
}

export interface MixState {
  muted: boolean;
  /** A voice call's hold on the music. */
  voice: VoiceDuck;
  /** A YouTube demo plays: the music steps aside until it pauses or ends. */
  video: boolean;
  /** The page view covers the flight (or the scene failed): the music rests. */
  away: boolean;
}

export function masterTarget(m: MixState): number {
  if (m.muted || m.away || m.video) return 0;
  return MASTER_GAIN * VOICE_DUCK[m.voice];
}

/**
 * setTargetAtTime's time constant (about 95% of the way after three): down in about 0.35 s (a call,
 * the agent speaking, a video, mute); up from a duck in about 0.5 s (the agent stops, the call ends);
 * up out of silence gently, in about 1.5 s (sound on, a video paused, back from the page view).
 */
export function masterTimeConstant(from: number, to: number): number {
  if (to < from) return 0.12;
  return from > 0 ? 0.17 : 0.5;
}

// --- what to load and keep -------------------------------------------------------------------------

export type Direction = 1 | -1;

/** The direction of travel: the sign of the last real move, else the previous direction. */
export function travelDirection(prev: Direction, fromFrame: number, toFrame: number, eps = 0.5): Direction {
  const d = toFrame - fromFrame;
  if (d > eps) return 1;
  if (d < -eps) return -1;
  return prev;
}

/**
 * The track one step along the flight. After the loading screen comes the area the flight opens on
 * (`opening`, else the gate); before it nothing.
 */
export function stepKey(key: MusicKey, dir: Direction, opening: AreaId | null): MusicKey | null {
  if (key === "loading") return dir > 0 ? (opening ?? AREA_IDS[0]) : null;
  const i = AREA_IDS.indexOf(key);
  return AREA_IDS[i + dir] ?? null;
}

/** Fetch and decode only these: the current track, then the next one in the direction of travel. */
export function loadPlan(current: MusicKey | null, dir: Direction, opening: AreaId | null): MusicKey[] {
  if (current === null) return [];
  const next = stepKey(current, dir, opening);
  return next ? [current, next] : [current];
}

/**
 * Decoded buffers to keep, most wanted first, cut to the budget: the current track, the next, the
 * one just passed, the one after next. A decoded 2.5 minute stereo track is about 55 MB, so even a
 * desktop keeps only a few.
 */
export function keepPlan(current: MusicKey | null, dir: Direction, opening: AreaId | null, budget: number): MusicKey[] {
  if (current === null) return [];
  const out: MusicKey[] = [];
  const add = (k: MusicKey | null) => {
    if (k !== null && !out.includes(k)) out.push(k);
  };
  add(current);
  const next = stepKey(current, dir, opening);
  add(next);
  add(stepKey(current, dir > 0 ? -1 : 1, opening));
  if (next) add(stepKey(next, dir, opening));
  return out.slice(0, Math.max(1, budget));
}

/** Phones and small-memory devices keep two decoded tracks (the current and the next), others three. */
export function musicBudget(device: { deviceMemory?: number; coarse: boolean }): number {
  const low = device.coarse || (device.deviceMemory !== undefined && device.deviceMemory <= 4);
  return low ? 2 : 3;
}

// --- the visitor -------------------------------------------------------------------------------------

/** localStorage key of the visitor's choice ("1" muted, "0" on). */
export const MUTE_KEY = "sect.music.muted";

/**
 * Whether the music starts muted. music/sect-themes/README.md: "Start muted, with a visible sound
 * toggle", so it is muted unless this visitor turned it on before (saved "0"); they then hear it
 * again from their first click, tap or key. Muted too when storage is blocked.
 */
export function readMuted(storage: Pick<Storage, "getItem"> | null | undefined): boolean {
  try {
    return storage?.getItem(MUTE_KEY) !== "0";
  } catch {
    return true;
  }
}

export function writeMuted(storage: Pick<Storage, "setItem"> | null | undefined, muted: boolean): void {
  try {
    storage?.setItem(MUTE_KEY, muted ? "1" : "0");
  } catch {
    // Storage blocked (a private window): the choice lasts for this visit only.
  }
}

/**
 * Events that give the page user activation, so audio may start (HTML's activation-triggering
 * events): a key other than Escape, a mouse press, a touch or pen lifting, a click. A wheel or a
 * scroll does not.
 */
export function activatesAudio(e: { type: string; key?: string; pointerType?: string }): boolean {
  switch (e.type) {
    case "keydown":
      return e.key !== "Escape" && e.key !== "Esc";
    case "pointerdown":
      return e.pointerType === "mouse";
    case "pointerup":
      return e.pointerType !== "mouse";
    case "mousedown":
    case "touchend":
    case "click":
      return true;
    default:
      return false;
  }
}
