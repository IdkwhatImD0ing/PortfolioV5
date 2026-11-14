/**
 * /music's player: nothing is fetched before play, a song plays when its file is here, the next one
 * follows at the end, and pause, seek, previous, repeat, volume and mute do what their buttons say.
 */
import { describe, expect, it, vi } from "vitest";
import type { MusicKey } from "@/lib/sect/music";
import { SongPlayer, type AudioLike } from "./song-player";

class FakeAudio implements AudioLike {
  private file = "";
  /** A new file: the element stops and starts over, as a real one does. */
  get src(): string {
    return this.file;
  }
  set src(url: string) {
    this.file = url;
    this.paused = true;
    this.ended = false;
    this.currentTime = 0;
    this.duration = Number.NaN;
  }
  currentTime = 0;
  duration = Number.NaN;
  paused = true;
  ended = false;
  volume = 1;
  muted = false;
  plays = 0;
  /** play() resolves, or rejects with this. */
  refuse: Error | null = null;
  private readonly fns = new Map<string, Set<() => void>>();

  play(): Promise<void> {
    this.plays++;
    if (this.refuse) return Promise.reject(this.refuse);
    this.paused = false;
    this.ended = false;
    return Promise.resolve();
  }
  pause(): void {
    this.paused = true;
  }
  load(): void {}
  removeAttribute(name: string): void {
    if (name === "src") this.src = "";
  }
  addEventListener(type: string, fn: () => void): void {
    if (!this.fns.has(type)) this.fns.set(type, new Set());
    this.fns.get(type)?.add(fn);
  }
  removeEventListener(type: string, fn: () => void): void {
    this.fns.get(type)?.delete(fn);
  }
  fire(type: string): void {
    for (const fn of [...(this.fns.get(type) ?? [])]) fn();
  }
  /** The element has read the file's length. */
  loaded(duration: number): void {
    this.duration = duration;
    this.fire("loadedmetadata");
  }
  /** The song ran out. */
  finish(): void {
    this.paused = true;
    this.ended = true;
    this.fire("pause");
    this.fire("ended");
  }
}

const LIST: MusicKey[] = ["loading", "gate", "arena", "summit"];
const LENGTH: Partial<Record<MusicKey, number>> = { loading: 87, gate: 69, arena: 240, summit: 212 };
const tick = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

function setup(opts: { volume?: number; fetchBytes?: (key: MusicKey, signal: AbortSignal) => Promise<ArrayBuffer> } = {}) {
  const audio = new FakeAudio();
  const fetched: MusicKey[] = [];
  const revoked: string[] = [];
  const saved: number[] = [];
  const fetchBytes =
    opts.fetchBytes ??
    (async (key: MusicKey) => {
      fetched.push(key);
      return new ArrayBuffer(8);
    });
  const urlKeys: MusicKey[] = [];
  const player = new SongPlayer(
    {
      audio,
      fetchBytes: (key, signal) => {
        urlKeys.push(key);
        return fetchBytes(key, signal);
      },
      createUrl: () => `blob:${urlKeys[urlKeys.length - 1]}-${urlKeys.length}`,
      revokeUrl: (url) => revoked.push(url),
      silence: "data:silence",
      saveVolume: (v) => saved.push(v),
    },
    { volume: opts.volume },
  );
  player.setSongs(LIST, (key) => LENGTH[key] ?? 0);
  return { audio, player, fetched, revoked, saved };
}

describe("SongPlayer", () => {
  it("opens on the first song, or the one asked for, and fetches nothing until play", () => {
    const { player, fetched, audio } = setup();
    expect(player.snapshot()).toMatchObject({ song: "loading", playing: false, loading: false, duration: 87 });
    expect(fetched).toEqual([]);
    expect(audio.src).toBe("");

    const other = setup();
    other.player.setSongs(["gate", "arena"], () => 10, "arena");
    // The song it was on is not in the new list: the one asked for takes its place.
    expect(other.player.snapshot().song).toBe("arena");
  });

  it("plays the silence inside the tap, then the song once its file is here", async () => {
    const { player, audio, fetched } = setup();
    player.play();
    expect(audio.src).toBe("data:silence");
    expect(audio.plays).toBe(1);
    expect(player.snapshot()).toMatchObject({ playing: true, loading: true });
    await tick();
    expect(fetched).toEqual(["loading"]);
    expect(audio.src).toMatch(/^blob:loading/);
    expect(audio.plays).toBe(2);
    audio.loaded(86.9);
    expect(player.snapshot()).toMatchObject({ playing: true, loading: false, duration: 86.9 });
  });

  it("fetches the next song once this one is heard", async () => {
    const { player, audio, fetched } = setup();
    player.play();
    await tick();
    audio.loaded(87);
    audio.fire("playing");
    await tick();
    expect(fetched).toEqual(["loading", "gate"]);
    // Its file is here already: Next plays it at once, inside the press.
    player.next();
    expect(audio.src).toMatch(/^blob:gate/);
    expect(player.snapshot()).toMatchObject({ song: "gate", playing: true });
  });

  it("keeps a file that arrives after a pause, and plays it on the next press without fetching again", async () => {
    const { player, audio, fetched } = setup();
    player.play();
    player.pause();
    await tick();
    expect(audio.src).toBe("data:silence");
    expect(player.snapshot()).toMatchObject({ playing: false, loading: false });
    player.play();
    expect(audio.src).toMatch(/^blob:loading/);
    expect(fetched).toEqual(["loading"]);
  });

  it("goes to the next song at the end, round to the first after the last", async () => {
    const { player, audio } = setup();
    player.select("summit", true);
    await tick();
    audio.loaded(212);
    audio.finish();
    expect(player.snapshot()).toMatchObject({ song: "loading", playing: true });
    await tick();
    expect(audio.src).toMatch(/^blob:loading/);
  });

  it("plays the same song again with Repeat on", async () => {
    const { player, audio } = setup();
    player.toggleRepeat();
    player.play();
    await tick();
    audio.loaded(87);
    audio.currentTime = 87;
    const before = audio.plays;
    audio.finish();
    expect(player.snapshot()).toMatchObject({ song: "loading", playing: true, repeat: true });
    expect(audio.currentTime).toBe(0);
    expect(audio.plays).toBe(before + 1);
  });

  it("Previous restarts a song that is a few seconds in, else goes to the one before", async () => {
    const { player, audio } = setup();
    player.select("gate", true);
    await tick();
    audio.loaded(69);
    audio.currentTime = 20;
    player.previous();
    expect(player.snapshot().song).toBe("gate");
    expect(audio.currentTime).toBe(0);
    player.previous();
    expect(player.snapshot().song).toBe("loading");
  });

  it("holds a seek made before the file is ready, and keeps it inside the song", async () => {
    const { player, audio } = setup();
    player.select("arena");
    player.seek(500);
    expect(player.position()).toBe(240);
    player.seek(42);
    expect(player.position()).toBe(42);
    player.play();
    await tick();
    // It waits for the length, seeks, then plays: no blip from the start.
    expect(audio.plays).toBe(1);
    audio.loaded(239.7);
    expect(audio.currentTime).toBe(42);
    expect(audio.plays).toBe(2);
    expect(player.position()).toBe(42);
  });

  it("follows a pause or a play that came from outside the page", async () => {
    const { player, audio } = setup();
    player.play();
    await tick();
    audio.loaded(87);
    audio.pause();
    audio.fire("pause");
    expect(player.snapshot().playing).toBe(false);
    audio.paused = false;
    audio.fire("play");
    expect(player.snapshot().playing).toBe(true);
  });

  it("does not take a change of song for a pause", async () => {
    const { player, audio } = setup();
    player.play();
    await tick();
    audio.loaded(87);
    audio.fire("playing");
    await tick();
    player.next();
    // The old song's pause arrives late, while the new file is still being read.
    audio.fire("pause");
    expect(player.snapshot()).toMatchObject({ song: "gate", playing: true });
  });

  it("shows a song that did not come as failed, and tries again on play", async () => {
    let fail = true;
    const { player } = setup({
      fetchBytes: async () => {
        if (fail) throw new Error("offline");
        return new ArrayBuffer(8);
      },
    });
    player.play();
    await tick();
    expect(player.snapshot()).toMatchObject({ playing: false, failed: true });
    fail = false;
    player.play();
    expect(player.snapshot()).toMatchObject({ playing: true, failed: false });
    await tick();
    expect(player.snapshot()).toMatchObject({ playing: true, failed: false });
  });

  it("offers play again when the browser refuses to start", async () => {
    const { player, audio } = setup();
    audio.refuse = Object.assign(new Error("no tap"), { name: "NotAllowedError" });
    player.play();
    await tick();
    await tick();
    expect(player.snapshot().playing).toBe(false);
  });

  it("sets the element's level to the square of the slider's share, and saves the share", () => {
    const { player, audio, saved } = setup({ volume: 1 });
    expect(audio.volume).toBe(1);
    player.setVolume(0.5);
    expect(audio.volume).toBeCloseTo(0.25);
    expect(saved).toEqual([0.5]);
    expect(player.snapshot().volume).toBe(0.5);
  });

  it("mutes and unmutes, and the slider moving up unmutes too", () => {
    const { player, audio } = setup({ volume: 0.8 });
    player.toggleMute();
    expect(audio.muted).toBe(true);
    expect(player.snapshot().muted).toBe(true);
    player.setVolume(0.6);
    expect(audio.muted).toBe(false);
    // At zero the speaker button brings the sound back at half.
    player.setVolume(0);
    player.toggleMute();
    expect(player.snapshot()).toMatchObject({ muted: false, volume: 0.5 });
  });

  it("starts at the saved volume without a sound escaping first", () => {
    const { audio, player } = setup({ volume: 0 });
    expect(audio.volume).toBe(0);
    expect(player.snapshot().volume).toBe(0);
  });

  it("says when the browser will not let a page set the volume", () => {
    const locked = new FakeAudio();
    Object.defineProperty(locked, "volume", { get: () => 1, set: () => {} });
    const player = new SongPlayer({
      audio: locked,
      fetchBytes: async () => new ArrayBuffer(1),
      createUrl: () => "blob:x",
      revokeUrl: () => {},
      silence: "data:silence",
    });
    expect(player.snapshot().volumeSettable).toBe(false);
  });

  it("holds only a few files, and lets all of them go when it is disposed", async () => {
    const { player, audio, revoked } = setup();
    for (const key of LIST) {
      player.select(key, true);
      await tick();
      audio.loaded(60);
    }
    // Four songs played, three kept: the first was let go.
    expect(revoked).toHaveLength(1);
    expect(revoked[0]).toMatch(/^blob:loading/);
    player.dispose();
    expect(revoked).toHaveLength(4);
    expect(audio.src).toBe("");
    expect(audio.paused).toBe(true);
  });

  it("drops a download for a song left behind", async () => {
    const aborted: MusicKey[] = [];
    const { player } = setup({
      fetchBytes: (key, signal) =>
        new Promise<ArrayBuffer>((resolve, reject) => {
          signal.addEventListener("abort", () => {
            aborted.push(key);
            reject(new Error("aborted"));
          });
          setTimeout(() => resolve(new ArrayBuffer(8)), 5);
        }),
    });
    const heard = vi.fn();
    player.subscribe(heard);
    player.play();
    player.select("arena");
    expect(aborted).toEqual(["loading"]);
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(player.snapshot()).toMatchObject({ song: "arena", playing: true, failed: false });
    expect(heard).toHaveBeenCalled();
  });
});
