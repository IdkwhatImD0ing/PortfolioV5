/**
 * The audio side of /music (the choices are lib/sect/player.ts; the page ./music-player.tsx). One
 * <audio> element plays one song at a time, start to end, then the next.
 *
 * Why not the flight's engine (sect/experience/music-engine.ts): that one decodes whole tracks into
 * memory (about 55 MB each) to loop and crossfade them under a scene. A player needs to pause, seek
 * and carry on in a hidden tab, which an <audio> element does by itself for the 5 MB file.
 *
 * The backend wants a short-lived capability in a header (docs/music/backend-soundtrack-delivery.md),
 * which an element's src cannot send. So a song is fetched whole, then handed to the element as an
 * object URL. Nothing is fetched until the visitor presses play; while a song plays, the next one is
 * fetched too, so it follows without a gap. At most KEEP_FILES songs are held.
 *
 * Nothing here throws: a song that does not come shows as failed, and play tries it again.
 */
import type { MusicKey } from "@/lib/sect/music";
import { afterEnd, clampSeek, elementVolume, previousRestarts, stepSong } from "@/lib/sect/player";
import { DEFAULT_VOLUME, clampVolume } from "@/lib/sect/volume";

/** The parts of an <audio> element the player uses (the tests pass a stand-in). */
export interface AudioLike {
  src: string;
  currentTime: number;
  readonly duration: number;
  readonly paused: boolean;
  readonly ended: boolean;
  volume: number;
  muted: boolean;
  play(): Promise<void>;
  pause(): void;
  load(): void;
  removeAttribute(name: string): void;
  addEventListener(type: string, fn: () => void): void;
  removeEventListener(type: string, fn: () => void): void;
}

export interface PlayerDeps {
  audio: AudioLike;
  /** Downloads a song's bytes. */
  fetchBytes: (key: MusicKey, signal: AbortSignal) => Promise<ArrayBuffer>;
  /** An object URL for the bytes, and its release. */
  createUrl: (bytes: ArrayBuffer) => string;
  revokeUrl: (url: string) => void;
  /**
   * A moment of silence the element can play at once. Phones let a page start sound only inside a
   * tap; the song arrives seconds later, so the tap plays this and the element stays allowed.
   */
  silence: string;
  saveVolume?: (volume: number) => void;
}

/** What the page shows. A new object whenever something in it changes. */
export interface PlayerUi {
  song: MusicKey | null;
  /** The visitor wants it playing (the button shows Pause). */
  playing: boolean;
  /** It should be playing and its file is not ready yet. */
  loading: boolean;
  /** Its file did not come. */
  failed: boolean;
  /** Seconds: the element's once it knows, the manifest's until then. */
  duration: number;
  /** The slider's share, 0 to 1 (lib/sect/volume.ts). */
  volume: number;
  muted: boolean;
  repeat: boolean;
  /** The browser lets a page set the volume (iPhones do not: there the slider is left out). */
  volumeSettable: boolean;
}

export const PLAYER_OFF: PlayerUi = {
  song: null,
  playing: false,
  loading: false,
  failed: false,
  duration: 0,
  volume: DEFAULT_VOLUME,
  muted: false,
  repeat: false,
  volumeSettable: true,
};

/** Songs held as files: the one playing, the next, the one before. */
const KEEP_FILES = 3;
/** The level the speaker button brings back when the slider sat at zero. */
const UNMUTE_VOLUME = 0.5;
const EVENTS = ["loadedmetadata", "durationchange", "timeupdate", "seeked", "playing", "play", "pause", "ended", "error"] as const;

export class SongPlayer {
  private readonly deps: PlayerDeps;
  private readonly audio: AudioLike;
  private list: MusicKey[] = [];
  private readonly lengths = new Map<MusicKey, number>();
  private song: MusicKey | null = null;
  private wantPlaying = false;
  /** The song whose file the element holds; null while it holds nothing (or the silence). */
  private attached: MusicKey | null = null;
  /** The attached song's length is known: it can seek and play. */
  private ready = false;
  /** A seek asked for before the file was ready. */
  private pendingSeek: number | null = null;
  /** Object URLs, least recently used first. */
  private readonly urls = new Map<MusicKey, string>();
  private readonly pending = new Map<MusicKey, { ac: AbortController; done: Promise<boolean> }>();
  private readonly failed = new Set<MusicKey>();
  private unlocked = false;
  private volume: number;
  private muted = false;
  private repeat = false;
  private readonly volumeSettable: boolean;
  private disposed = false;
  private ui: PlayerUi;
  private readonly listeners = new Set<() => void>();
  private readonly timeListeners = new Set<() => void>();
  private readonly handlers: Record<(typeof EVENTS)[number], () => void>;

  constructor(deps: PlayerDeps, opts: { volume?: number } = {}) {
    this.deps = deps;
    this.audio = deps.audio;
    this.volume = clampVolume(opts.volume ?? DEFAULT_VOLUME);
    this.volumeSettable = canSetVolume(this.audio);
    this.audio.volume = elementVolume(this.volume);
    this.audio.muted = false;
    this.ui = { ...PLAYER_OFF, volume: this.volume, volumeSettable: this.volumeSettable };
    this.handlers = {
      loadedmetadata: () => this.onMetadata(),
      durationchange: () => this.emit(),
      timeupdate: () => this.emitTime(),
      seeked: () => this.emitTime(),
      playing: () => this.onPlaying(),
      play: () => this.onPlay(),
      pause: () => this.onPause(),
      ended: () => this.onEnded(),
      error: () => this.onError(),
    };
    for (const type of EVENTS) this.audio.addEventListener(type, this.handlers[type]);
  }

  // --- the page's store (useSyncExternalStore) -----------------------------------------------------

  subscribe = (fn: () => void): (() => void) => {
    this.listeners.add(fn);
    return () => {
      this.listeners.delete(fn);
    };
  };

  snapshot = (): PlayerUi => this.ui;

  /** The place in the song moved (it plays, or a seek landed). Read it with position(). */
  subscribeTime = (fn: () => void): (() => void) => {
    this.timeListeners.add(fn);
    return () => {
      this.timeListeners.delete(fn);
    };
  };

  private emitTime(): void {
    for (const fn of this.timeListeners) fn();
  }

  private emit(): void {
    const song = this.song;
    const next: PlayerUi = {
      song,
      playing: this.wantPlaying,
      loading: this.wantPlaying && !(this.attached === song && this.ready),
      failed: song !== null && this.failed.has(song),
      duration: this.duration(),
      volume: this.volume,
      muted: this.muted,
      repeat: this.repeat,
      volumeSettable: this.volumeSettable,
    };
    const ui = this.ui;
    if ((Object.keys(next) as (keyof PlayerUi)[]).every((k) => next[k] === ui[k])) return;
    this.ui = next;
    for (const fn of this.listeners) fn();
  }

  // --- what the page reads -------------------------------------------------------------------------

  /** Seconds into the song. */
  position(): number {
    if (this.song !== null && this.attached === this.song && this.ready) return this.audio.currentTime;
    return this.pendingSeek ?? 0;
  }

  duration(): number {
    const song = this.song;
    if (song === null) return 0;
    const own = this.audio.duration;
    if (this.attached === song && this.ready && Number.isFinite(own) && own > 0) return own;
    return this.lengths.get(song) ?? 0;
  }

  // --- what the page asks for ----------------------------------------------------------------------

  /** The list, each song's length from the manifest, and the song to open on (else the first). */
  setSongs(list: readonly MusicKey[], length: (key: MusicKey) => number, start: MusicKey | null = null): void {
    if (this.disposed) return;
    this.list = [...list];
    this.lengths.clear();
    for (const key of list) this.lengths.set(key, length(key));
    if (this.song === null || !this.list.includes(this.song)) {
      this.detach();
      this.wantPlaying = false;
      this.pendingSeek = null;
      this.song = start !== null && this.list.includes(start) ? start : (this.list[0] ?? null);
    }
    this.emit();
    this.emitTime();
  }

  /** Another song: from its start, playing if the last one was (or if `play` says so). */
  select(key: MusicKey, play = false): void {
    if (this.disposed || !this.list.includes(key)) return;
    if (key === this.song) {
      if (play && !this.wantPlaying) this.play();
      return;
    }
    this.detach();
    this.song = key;
    this.pendingSeek = null;
    this.failed.delete(key);
    // A download for a song now left behind: dropped, so this one comes first on a slow line.
    for (const [k, p] of [...this.pending]) {
      if (k !== key) {
        p.ac.abort();
        this.pending.delete(k);
      }
    }
    if (play) this.wantPlaying = true;
    if (this.wantPlaying) {
      if (play) this.unlock();
      this.start();
    }
    this.emit();
    this.emitTime();
  }

  play(): void {
    if (this.disposed || this.song === null) return;
    this.wantPlaying = true;
    this.failed.delete(this.song);
    this.unlock();
    this.start();
    this.emit();
  }

  pause(): void {
    if (this.disposed) return;
    this.wantPlaying = false;
    if (this.attached !== null) this.audio.pause();
    this.emit();
  }

  toggle(): void {
    if (this.wantPlaying) this.pause();
    else this.play();
  }

  next(): void {
    const key = stepSong(this.list, this.song, 1);
    if (key === null) return;
    if (key === this.song) this.seek(0);
    else this.select(key);
  }

  /** Back to this song's start once it is a few seconds in, else to the song before. */
  previous(): void {
    const key = stepSong(this.list, this.song, -1);
    if (key === null) return;
    if (key === this.song || previousRestarts(this.position())) this.seek(0);
    else this.select(key);
  }

  seek(time: number): void {
    if (this.disposed || this.song === null) return;
    const to = clampSeek(time, this.duration());
    if (this.attached === this.song && this.ready) this.audio.currentTime = to;
    else this.pendingSeek = to;
    this.emitTime();
  }

  /** The slider: a share 0 to 1, saved for the visitor. Moving it up from silence also unmutes. */
  setVolume(v: number): void {
    if (this.disposed) return;
    const next = clampVolume(v);
    if (next === this.volume) return;
    this.volume = next;
    this.audio.volume = elementVolume(next);
    if (next > 0 && this.muted) {
      this.muted = false;
      this.audio.muted = false;
    }
    this.deps.saveVolume?.(next);
    this.emit();
  }

  /** The speaker button. With the slider at zero it brings the sound back at half instead. */
  toggleMute(): void {
    if (this.disposed) return;
    if (!this.muted && this.volume === 0 && this.volumeSettable) {
      this.setVolume(UNMUTE_VOLUME);
      return;
    }
    this.muted = !this.muted;
    this.audio.muted = this.muted;
    this.emit();
  }

  toggleRepeat(): void {
    if (this.disposed) return;
    this.repeat = !this.repeat;
    this.emit();
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    for (const p of this.pending.values()) p.ac.abort();
    this.pending.clear();
    for (const type of EVENTS) this.audio.removeEventListener(type, this.handlers[type]);
    this.attached = null;
    try {
      this.audio.pause();
      this.audio.removeAttribute("src");
      this.audio.load();
    } catch {
      // The element is going anyway.
    }
    for (const url of this.urls.values()) this.deps.revokeUrl(url);
    this.urls.clear();
    this.listeners.clear();
    this.timeListeners.clear();
  }

  // --- the work ------------------------------------------------------------------------------------

  /** The element lets go of its song (the next one's file is not here yet, or not wanted yet). */
  private detach(): void {
    if (this.attached === null) return;
    this.attached = null;
    this.ready = false;
    this.audio.pause();
  }

  /**
   * Inside the visitor's tap: when the song still has to be fetched, the element plays the silence
   * now, so it may start the song by itself when the file is here.
   */
  private unlock(): void {
    if (this.unlocked || this.song === null) return;
    if (this.attached === this.song || this.urls.has(this.song)) return;
    this.unlocked = true;
    try {
      this.audio.src = this.deps.silence;
      void this.audio.play().catch(() => {});
    } catch {
      // Without it, the first play may need a second press on a phone.
    }
  }

  /** Gets the current song's file to the element, then plays it (if still wanted by then). */
  private start(): void {
    const key = this.song;
    if (key === null) return;
    if (this.attached === key) {
      if (this.ready) this.playElement();
      return;
    }
    const url = this.urls.get(key);
    if (url !== undefined) {
      this.attach(key, url);
      return;
    }
    void this.fetch(key).then((ok) => {
      if (this.disposed || this.song !== key) return;
      if (!ok) this.wantPlaying = false;
      else if (this.wantPlaying && this.attached !== key) {
        const fetched = this.urls.get(key);
        if (fetched !== undefined) this.attach(key, fetched);
      }
      this.emit();
    });
  }

  private attach(key: MusicKey, url: string): void {
    this.attached = key;
    this.ready = false;
    // Used just now: last in line to be let go.
    this.urls.delete(key);
    this.urls.set(key, url);
    this.audio.src = url;
    // With no seek waiting it may start as soon as it can (this call is still inside the tap when
    // the file was here already); with one, it waits for the length, seeks, then plays.
    if (this.wantPlaying && this.pendingSeek === null) this.playElement();
  }

  private playElement(): void {
    const key = this.attached;
    let started: Promise<void>;
    try {
      started = this.audio.play();
    } catch {
      started = Promise.reject(new Error("play"));
    }
    started.catch((err: unknown) => {
      // Cut short by a change of song: the new one plays instead.
      if (this.disposed || this.attached !== key || (err as { name?: string } | null)?.name === "AbortError") return;
      // The browser refused (no tap behind it): the button offers play again.
      this.wantPlaying = false;
      this.emit();
    });
  }

  private fetch(key: MusicKey): Promise<boolean> {
    const have = this.pending.get(key);
    if (have) return have.done;
    const ac = new AbortController();
    const done = this.deps
      .fetchBytes(key, ac.signal)
      .then((bytes) => {
        if (this.disposed || ac.signal.aborted) return false;
        this.keep(key, this.deps.createUrl(bytes));
        return true;
      })
      .catch(() => {
        if (!this.disposed && !ac.signal.aborted) this.failed.add(key);
        return false;
      })
      .finally(() => {
        if (this.pending.get(key)?.ac === ac) this.pending.delete(key);
      });
    this.pending.set(key, { ac, done });
    return done;
  }

  private keep(key: MusicKey, url: string): void {
    const old = this.urls.get(key);
    if (old !== undefined && old !== url) this.deps.revokeUrl(old);
    this.urls.delete(key);
    this.urls.set(key, url);
    for (const [k, u] of [...this.urls]) {
      if (this.urls.size <= KEEP_FILES) break;
      if (k === this.song || k === this.attached || k === key) continue;
      this.deps.revokeUrl(u);
      this.urls.delete(k);
    }
  }

  private onMetadata(): void {
    if (this.attached === null) return;
    this.ready = true;
    if (this.pendingSeek !== null) {
      this.audio.currentTime = clampSeek(this.pendingSeek, this.audio.duration);
      this.pendingSeek = null;
    }
    if (this.wantPlaying && this.audio.paused) this.playElement();
    this.emit();
    this.emitTime();
  }

  /** Sound is coming out: the song that follows is fetched now, so it starts without a wait. */
  private onPlaying(): void {
    if (this.attached === null || this.attached !== this.song || this.pending.size > 0) return;
    const key = afterEnd(this.list, this.song, this.repeat);
    if (key === null || key === this.song || this.urls.has(key) || this.failed.has(key)) return;
    void this.fetch(key);
  }

  /** Played from outside the page's buttons (a headset, the lock screen). */
  private onPlay(): void {
    if (this.attached === null || !this.ready || this.wantPlaying) return;
    this.wantPlaying = true;
    this.emit();
  }

  /** Paused from outside the page's buttons (a headset, a call, the lock screen). */
  private onPause(): void {
    if (this.attached === null || !this.ready || !this.wantPlaying) return;
    if (this.audio.ended || !this.audio.paused) return;
    this.wantPlaying = false;
    this.emit();
  }

  private onEnded(): void {
    if (this.attached === null || this.attached !== this.song) return;
    const key = afterEnd(this.list, this.song, this.repeat);
    if (key === null) {
      this.wantPlaying = false;
      this.emit();
      return;
    }
    this.wantPlaying = true;
    if (key === this.song) {
      this.audio.currentTime = 0;
      this.playElement();
      this.emit();
      this.emitTime();
    } else {
      this.select(key);
    }
  }

  private onError(): void {
    const key = this.attached;
    if (key === null) return;
    // A file the element could not read: let go of it, so play fetches it afresh.
    const url = this.urls.get(key);
    if (url !== undefined) {
      this.deps.revokeUrl(url);
      this.urls.delete(key);
    }
    this.attached = null;
    this.ready = false;
    this.failed.add(key);
    if (this.song === key) this.wantPlaying = false;
    this.emit();
  }
}

/** iPhones ignore a page's volume (the element always reads 1): the slider would do nothing there. */
function canSetVolume(audio: AudioLike): boolean {
  try {
    const was = audio.volume;
    const probe = was > 0.5 ? 0.25 : 0.75;
    audio.volume = probe;
    const ok = Math.abs(audio.volume - probe) < 0.01;
    audio.volume = was;
    return ok;
  } catch {
    return false;
  }
}
