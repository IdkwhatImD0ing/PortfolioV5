"use client";

/**
 * Background music for the flight: the loading screen's track while it is up, then each area's
 * track as the camera reaches it, crossfading (lib/sect/music.ts has the choices, ./music-engine.ts
 * the Web Audio). Mounted once by the experience, with the sound toggle (./sound-toggle.tsx).
 *
 * - Sound is on by default (docs/music/sect-themes/README.md): the music starts on the visitor's
 *   first click, tap or key (browsers allow sound only after one; a wheel does not count), Enter on
 *   the loading screen included. The sound toggle or the loading screen's prompt (SoundPrompt) mutes
 *   it, and the choice is remembered (localStorage "sect.music.muted").
 * - That first press plays at once: the loading screen's track loads as soon as the track list is
 *   here, and the opening place's once the scene has loaded, both before any press (not for a
 *   visitor who muted). A press on "Enter" goes straight to the place's song.
 * - The track list and the tracks heard are kept for the next visit (lib/sect/music-cache.ts), so a
 *   returning visitor's music does not wait for the backend to wake.
 * - The volume slider beside the toggle sets the level (lib/sect/volume.ts, remembered as
 *   "sect.music.volume"); the ducking and silences below take their share of it.
 * - A fast scroll through several areas plays none of the ones in between (the hysteresis); a jump
 *   plays its destination's track.
 * - Lower under a voice call (lower still while the agent speaks: the talisman's state), silent
 *   while a YouTube demo plays (content/video-watch.ts), resting in the page view, suspended while
 *   the tab is hidden.
 * - Downloads only the current track and the next one along the flight (only the current one while
 *   the scene itself is downloading); frees decoded tracks far from the camera (fewer on phones).
 * - No backend manifest (or no Web Audio): no music and no toggle, and nothing logged.
 *
 * ?debug=1: window.__sect.music.state() (also window.__sectMusic) describes what plays.
 */
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import {
  MUSIC_SAMPLE_RATE,
  activatesAudio,
  areaAtFrame,
  createSwitcher,
  keepPlan,
  loadPlan,
  loadingTrackOn,
  musicBudget,
  musicSpans,
  parseMusicManifest,
  readMuted,
  stepSwitcher,
  travelDirection,
  voiceDuck,
  wantedTrack,
  writeMuted,
  type AreaSpan,
  type Direction,
  type Switcher,
} from "@/lib/sect/music";
import { fetchMusicBytes, fetchMusicManifest, fetchTrackLyrics, resolveMusicApiBase } from "@/lib/sect/music-api";
import {
  cachedMusicBytes,
  openAudioCache,
  pruneCachedAudio,
  readSavedManifest,
  writeSavedManifest,
} from "@/lib/sect/music-cache";
import type { MusicKey } from "@/lib/sect/music";
import type { SongLyrics } from "@/lib/sect/lyrics";
import { readVolume, writeVolume } from "@/lib/sect/volume";
import { onVideoPlaying, videoPlaying } from "../content/video-watch";
import { MusicEngine } from "./music-engine";
import { LyricsPanel } from "./karaoke-lyrics";
import { SoundToggle } from "./sound-toggle";
import { isMoving, type SectStore } from "./store";

/** How often the track choice looks at the camera. */
const TICK_MS = 100;
/** Events that may carry the visitor's first gesture. */
const GESTURES = ["pointerdown", "pointerup", "keydown", "touchend", "click"] as const;

function audioContextClass(): typeof AudioContext | null {
  const w = window as unknown as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext };
  return w.AudioContext ?? w.webkitAudioContext ?? null;
}

function localStore(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function newContext(Ctor: typeof AudioContext): AudioContext {
  // At the files' own rate (see MUSIC_SAMPLE_RATE), else whatever the browser accepts.
  const tries: AudioContextOptions[] = [{ latencyHint: "playback", sampleRate: MUSIC_SAMPLE_RATE }, { latencyHint: "playback" }];
  for (const opts of tries) {
    try {
      return new Ctor(opts);
    } catch {
      // Try the next, plainer options.
    }
  }
  return new Ctor();
}

/**
 * Decodes tracks before the first gesture (the context above may only be made inside one). An
 * offline context never plays anything; its rate is the files', so what it decodes is what the
 * playing context would have.
 */
function newDecoder(): BaseAudioContext | null {
  const w = window as unknown as {
    OfflineAudioContext?: typeof OfflineAudioContext;
    webkitOfflineAudioContext?: typeof OfflineAudioContext;
  };
  const Ctor = w.OfflineAudioContext ?? w.webkitOfflineAudioContext;
  if (!Ctor) return null;
  try {
    return new Ctor(2, 1, MUSIC_SAMPLE_RATE);
  } catch {
    return null;
  }
}

function cacheStorage(): CacheStorage | null {
  try {
    return window.caches ?? null;
  } catch {
    return null;
  }
}

export function SectMusic({
  store,
  areas,
  loading,
  sceneLoading,
  away,
  lyricsHidden,
  debug,
  extra,
  onEngine,
}: {
  store: SectStore | null;
  /** meta.json's areas (their frame ranges), once loaded. */
  areas: readonly AreaSpan[] | null;
  /** The loading screen is up. */
  loading: boolean;
  /** The scene itself is still downloading (the loading screen's bar is moving). */
  sceneLoading: boolean;
  /** The page view (or an error) covers the flight. */
  away: boolean;
  /** Readers, the map, travel ink and errors cover the soundtrack panel. */
  lyricsHidden: boolean;
  debug: boolean;
  /** Another control for the sound toggle's place (the graphics button; sound-toggle.tsx). */
  extra?: ReactNode;
  /** Hands the engine out (the loading screen's SoundPrompt), and null when it goes. */
  onEngine?: (engine: MusicEngine | null) => void;
}) {
  const [engine, setEngine] = useState<MusicEngine | null>(null);
  const [apiBase, setApiBase] = useState<string | null>(null);
  const onEngineRef = useRef(onEngine);
  onEngineRef.current = onEngine;
  const live = useRef({ store, areas, loading, sceneLoading });
  live.current = { store, areas, loading, sceneLoading };
  const switcher = useRef<Switcher>(createSwitcher());
  /** When "Enter" was last pressed (performance.now() seconds): see loadingTrackOn. */
  const enterAt = useRef<number | null>(null);
  /** The track choice below, for the press on "Enter" to run it before the music starts. */
  const choose = useRef<() => void>(() => {});

  // The engine, and the track list (no list, no music).
  useEffect(() => {
    const Ctor = audioContextClass();
    const basePromise = resolveMusicApiBase();
    const cachePromise = openAudioCache(cacheStorage());
    const e = new MusicEngine(
      {
        createContext: () => (Ctor ? newContext(Ctor) : null),
        createDecoder: newDecoder,
        fetchBytes: async (key, signal, track) =>
          cachedMusicBytes({
            cache: await cachePromise,
            key,
            track,
            download: async () => fetchMusicBytes(await basePromise, key, signal),
          }),
        saveMuted: (m) => writeMuted(localStore(), m),
        saveVolume: (v) => writeVolume(localStore(), v),
      },
      { supported: Ctor !== null, muted: readMuted(localStore()), volume: readVolume(localStore()) },
    );
    setEngine(e);
    onEngineRef.current?.(e);
    const ac = new AbortController();
    if (Ctor) {
      // The list kept from the last visit first: the backend's can take seconds (it sleeps when
      // idle) and replaces this one when it arrives.
      const kept = readSavedManifest(localStore());
      if (kept) e.setManifest(kept);
      basePromise
        .then((base) => {
          if (!ac.signal.aborted) setApiBase(base);
          return fetchMusicManifest(base, ac.signal);
        })
        .then((j: unknown) => {
          if (ac.signal.aborted) return;
          const m = parseMusicManifest(j);
          e.setManifest(m);
          writeSavedManifest(localStore(), m);
          void cachePromise.then((cache) => pruneCachedAudio(cache, m));
        })
        .catch(() => {
          // No list from the backend: the kept one stays if there is one, else the page is silent.
        });
    }
    return () => {
      ac.abort();
      e.dispose();
      setApiBase(null);
      setEngine((cur) => (cur === e ? null : cur));
      onEngineRef.current?.(null);
    };
  }, []);

  const loadLyrics = useCallback(
    (key: MusicKey, signal: AbortSignal): Promise<SongLyrics | null> =>
      apiBase ? fetchTrackLyrics(apiBase, key, signal) : Promise.resolve(null),
    [apiBase],
  );

  // The first gesture starts the music when sound is on (a returning visitor who turned it on); the
  // toggle's own presses go to the toggle.
  useEffect(() => {
    if (!engine) return;
    const on = (ev: Event) => {
      if (!activatesAudio({ type: ev.type, key: (ev as KeyboardEvent).key, pointerType: (ev as PointerEvent).pointerType })) return;
      if (ev.target instanceof Element && ev.target.closest("[data-sect-sound]")) return;
      const ua = (navigator as Navigator & { userActivation?: { isActive: boolean } }).userActivation;
      if (ua && !ua.isActive) return;
      // A press on "Enter" (it has the attribute only once it can be pressed): the loading screen's
      // track is over, so the track is chosen again before the music starts.
      if (ev.target instanceof Element && ev.target.closest("[data-sect-enter]")) {
        enterAt.current = performance.now() / 1000;
        choose.current();
      }
      engine.gesture();
    };
    for (const t of GESTURES) window.addEventListener(t, on, { capture: true, passive: true });
    return () => {
      for (const t of GESTURES) window.removeEventListener(t, on, { capture: true });
    };
  }, [engine]);

  // A hidden tab suspends the music.
  useEffect(() => {
    if (!engine) return;
    const on = () => engine.setHidden(document.visibilityState === "hidden");
    on();
    document.addEventListener("visibilitychange", on);
    return () => document.removeEventListener("visibilitychange", on);
  }, [engine]);

  useEffect(() => {
    engine?.setAway(away);
  }, [engine, away]);

  // A voice call ducks the music: the talisman's state, which voice.tsx sets on its wrapper as
  // data-talisman (connecting and listening: down to a third; the agent speaking: lower still).
  useEffect(() => {
    if (!engine) return;
    let obs: MutationObserver | null = null;
    const attach = () => {
      const root = document.querySelector<HTMLElement>(".sect-orb");
      if (!root) return false;
      const check = () => engine.setVoice(voiceDuck(root.dataset.talisman));
      obs = new MutationObserver(check);
      obs.observe(root, { attributes: true, attributeFilter: ["data-talisman"] });
      check();
      return true;
    };
    let tries = 0;
    const timer = attach()
      ? 0
      : window.setInterval(() => {
          if (attach() || ++tries > 30) window.clearInterval(timer);
        }, 1000);
    return () => {
      obs?.disconnect();
      window.clearInterval(timer);
    };
  }, [engine]);

  // A YouTube demo playing in a reader silences the music until it pauses, ends or closes.
  useEffect(() => {
    if (!engine) return;
    const on = () => engine.setVideo(videoPlaying());
    on();
    return onVideoPlaying(on);
  }, [engine]);

  // Which track: the camera's area (or the loading screen), held a moment against fast scrolling.
  useEffect(() => {
    if (!engine) return;
    const nav = navigator as Navigator & { deviceMemory?: number };
    const budget = musicBudget({ deviceMemory: nav.deviceMemory, coarse: window.matchMedia("(pointer: coarse)").matches });
    let dir: Direction = 1;
    let lastFrame: number | null = null;
    const tick = () => {
      const { store: s, areas: a, loading: veil, sceneLoading: busy } = live.current;
      const nowS = performance.now() / 1000;
      if (!veil) enterAt.current = null;
      const l = loadingTrackOn(veil, enterAt.current, nowS);
      const spans = musicSpans(a, s?.camera.holds ?? []);
      // A jump plays its destination's track, not the places it sweeps past.
      const frame = s ? (s.flight ? s.flight.toFrame : s.frame) : null;
      if (frame !== null && lastFrame !== null) dir = travelDirection(dir, lastFrame, frame);
      lastFrame = frame;
      const want = wantedTrack(l, frame, spans);
      // A place without a track of its own keeps whatever plays.
      const target = want !== null && engine.has(want) ? want : null;
      switcher.current = stepSwitcher(switcher.current, target, nowS, s ? !isMoving(s) : true);
      const cur = switcher.current.current;
      const opening = s ? areaAtFrame(spans, s.frame) : null;
      // While the scene downloads, only the loading track does (the scene needs the bandwidth).
      // Once it has, the opening place's track loads behind the loading screen, ready for "Enter".
      const load = loadPlan(cur, dir, opening).slice(0, busy ? 1 : 2);
      engine.setPlan(cur, load, keepPlan(cur, dir, opening, budget));
    };
    choose.current = tick;
    tick();
    const id = window.setInterval(tick, TICK_MS);
    return () => {
      window.clearInterval(id);
      choose.current = () => {};
    };
  }, [engine]);

  // ?debug=1: window.__sect.music (scene.tsx replaces window.__sect now and then, so it is re-added).
  useEffect(() => {
    if (!engine || !debug) return;
    const hook = { state: () => ({ ...engine.state(), switcher: { ...switcher.current } }), engine };
    const w = window as unknown as { __sect?: Record<string, unknown>; __sectMusic?: unknown };
    w.__sectMusic = hook;
    const attach = () => {
      if (w.__sect && w.__sect.music !== hook) w.__sect.music = hook;
    };
    attach();
    const id = window.setInterval(attach, 250);
    return () => {
      window.clearInterval(id);
      delete w.__sectMusic;
      if (w.__sect?.music === hook) delete w.__sect.music;
    };
  }, [engine, debug]);

  // While the loading screen is up its own SoundPrompt stands in for the toggle (sound-toggle.tsx).
  return engine ? (
    <>
      <SoundToggle engine={engine} loading={loading} extra={extra} />
      {apiBase ? <LyricsPanel engine={engine} loadLyrics={loadLyrics} hidden={lyricsHidden} /> : null}
    </>
  ) : null;
}
