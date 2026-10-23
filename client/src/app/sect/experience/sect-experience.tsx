"use client";

/**
 * The sect (the home page): a fixed WebGL canvas behind a tall scroll track. Scrolling flies the
 * camera along the exported chase-camera path through the eleven areas of the sect, holding at each
 * one with its panel; every piece of the portfolio opens from there in the reader, or all of it as one
 * page ("Read as page", and always when WebGL 2 is missing).
 *
 * The world streams: the global set (backdrop with a reduced proxy of every area) loads first, then
 * each area's chunk around the camera (streaming.ts).
 *
 * Navigation: scroll; the rail (desktop) or its compact row (phones); the map (the Map button or
 * M: a painted map of the sect with every stop's seal, fast travel to any of them under an ink wash,
 * and the list of every place and item); PageDown/PageUp, the up and down arrows and J/K between
 * holds, Home to the start and End to the last place. Fast travel's ink stays up until the place has
 * settled (lib/sect/settle.ts), and a far jump from the rail, the list, a link, the voice agent, Home
 * or End to a place not loaded yet goes under the same ink rather than gathering it in view;
 * #<section> deep links (also on hashchange, and the hash follows the current hold);
 * ?open=<hotspot id>; the voice agent (VoiceBus). Free look turns the view all the way round: drag
 * the view, swipe sideways, or hold the left and right arrows; Escape or the Recentre button turns
 * it back.
 *
 * History: opening a reader (or the page view) adds one entry whose URL names it (#project/<id>, or
 * ?open=<item>#<section>), so it can be shared and browser Back closes it; a project opened inside
 * the forge reader adds one more. Moving inside a reader replaces the entry. lib/sect/links.ts has
 * the URLs and the state kept in history.state.
 *
 * URL options: ?frame=N (show Blender frame N; sets body[data-sect-ready] when rendered),
 * ?debug=1 (HUD with fps, draw calls, triangles, textures, resident chunks), ?flyer=1 (show the
 * flyer), ?ui=0 (no overlays), ?tier=low|mid|high (force a quality tier: the graphics picker hides
 * and nothing is stored), ?set=<name> (load public/sect/<name>/manifest.json; default "full",
 * "proto" is the first test; development only),
 * ?yaw=<degrees> (start with the view turned that far, positive left: screenshots of what lies
 * beside and behind a stop, with ?frame=N).
 * NEXT_PUBLIC_SECT_ASSET_BASE moves the asset sets off the site (a CDN or bucket).
 *
 * Graphics: the device probe picks a tier (lib/sect/runtime.ts chooseTier); the visitor may pick
 * another on the loading screen or with the graphics button, and that pick is stored for the next
 * visit (?tier= beats both). Desktop Medium and High swap in place; any other change cancels the
 * load (or the running page), frees it and loads again for the new tier, back at the same place.
 *
 * Opening: a page that opens at the top of the path shows the poster still of that view behind the
 * loading screen from its first paint (lib/sect/opening.ts), and the veil's fade is a crossfade to
 * the same view drawn live. The progress bar counts bytes and never goes back. "Read as page" while
 * loading stops the download until the flight comes back.
 */
import { lazy, memo, Suspense, useCallback, useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import type { Object3D } from "three";
import { AREAS, areaInfo, isAreaId, type AreaId } from "@/lib/sect/areas";
import { sampleCamera } from "@/lib/sect/camera-path";
import { areaItemHotspots, commandTarget, isThing, parseContentHash, SECTION_NAMES } from "@/lib/sect/content";
import { POSTER_ATTR, posterStart, startYaw, type NetworkHint } from "@/lib/sect/content-start";
import { framingAt, framingFrame } from "@/lib/sect/framing";
import { composeLook, isDragging, isLookingBack, isTurned, type LookOffset } from "@/lib/sect/free-look";
import { PageHistory } from "@/lib/sect/history";
import { plainUrl, readHistoryState, readerUrl, resolveDeepLink } from "@/lib/sect/links";
import { lookFogConstants } from "@/lib/sect/look";
import { hoverNote, loreByArea } from "@/lib/sect/lore";
import { flightSeconds, navKeyIntent, navKeyTarget, nearestHold, panelSide } from "@/lib/sect/nav";
import { downloadFraction, flickStop, PORTRAIT_TURN_SECONDS, portraitTurn, posterMatches, type FileProgress } from "@/lib/sect/opening";
import { resolveAsset } from "@/lib/sect/parse";
import {
  AUTO_FRAME_BUDGET_MS,
  CHOICE_FRAME_BUDGET_MS,
  chooseTier,
  degradeQuality,
  isAppleGpu,
  parseSectParams,
  readTierChoice,
  resolveTier,
  sectAssetBase,
  TIER_LABELS,
  tierChange,
  tierQuality,
  upgradeQuality,
  writeTierChoice,
  type Quality,
  type Tier,
} from "@/lib/sect/runtime";
import {
  FLIGHT_SCROLL,
  buildScrollMap,
  easeInOut,
  frameToU,
  holdPresence,
  introPresence,
  nearestStop,
  nextTrackViewport,
  pxPerUnit,
  scrollToU,
  uToFrame,
  uToScroll,
  type TrackViewport,
} from "@/lib/sect/scroll-map";
import { SettleWatch } from "@/lib/sect/settle";
import type { Vec3 } from "@/lib/sect/types";
import type { VoiceCommand } from "@/lib/voice-bus";
import { AreaPanel, AreaReader, ContentFallback, hotspotLabel, hotspotTarget, type ContentTarget } from "../content";
import { flightFocusFallback, keepsFocus } from "../content/modal";
import { LoadingScreen } from "../loading-screen";
import {
  chunkFiles,
  createWorldContext,
  detailSettling,
  disposeSet,
  disposeWorldContext,
  globalFiles,
  loadFlyer,
  loadSectData,
  loadSet,
  loadSky,
  retuneWorld,
  startDetail,
  type LoadedSet,
  type SectData,
  type WorldContext,
} from "./assets";
import { InkTravel, type TravelRequest } from "./ink-travel";
import { LoreCard, useLoreCard } from "./lore-card";
import type { MapViewProps } from "./map-view";
import { installFog } from "./materials";
import { SectMusic } from "./music";
import type { MusicEngine } from "./music-engine";
import {
  CompactRail,
  DebugHud,
  Gathering,
  HoverLabel,
  IntroTitle,
  LookHint,
  lookHintSeen,
  MapButton,
  markLookHintSeen,
  Notice,
  placeHoverLabel,
  QualityButton,
  RecentreButton,
  SectionRail,
  TopLinks,
  type PlaceGroup,
  type RailStop,
} from "./overlay";
import { disposeObjects } from "./prepare";
import SectCanvas, { MOON_HOTSPOT } from "./scene";
import { SoundPrompt } from "./sound-toggle";
import { cameraStill, createStore, isMoving, recenterView, wake, type SectStore } from "./store";
import { ChunkStreamer, streamBudget } from "./streaming";
import { SectVoice, startTalk, useVoiceRouting } from "./voice";

type Phase = "data" | "assets" | "ready" | "error" | "nowebgl";

/**
 * The map (map-view.tsx): its code, and its files, load only when it first opens (or when idle).
 * When the code cannot be fetched (the connection dropped just then), `onFail` runs and the map
 * draws nothing, instead of the error taking the whole page down.
 */
function mapLoader(onFail: () => void) {
  return lazy<ComponentType<MapViewProps>>(() =>
    import("./map-view").catch((e: unknown) => {
      console.warn("[sect] the map's code could not load", e);
      onFail();
      return { default: () => null };
    }),
  );
}

/**
 * Where the ink of a far jump starts: the middle of the control that asked for it (the rail's place,
 * a list item, the voice orb's box, when it has the focus), else the middle of the screen.
 */
function inkOrigin(): [number, number] {
  const w = window.innerWidth;
  const h = window.innerHeight;
  const el = document.activeElement;
  if (el instanceof HTMLElement && el !== document.body) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) {
      return [Math.min(w, Math.max(0, r.left + r.width / 2)), Math.min(h, Math.max(0, r.top + r.height / 2))];
    }
  }
  return [w / 2, h / 2];
}

interface Probe {
  webgl2: boolean;
  /** The probe's pick (the picker's "Recommended"). */
  tier: Tier;
  /** A touch screen (phones, tablets). */
  coarse: boolean;
  /** Safari's "Apple GPU" (lib/sect/runtime.ts isAppleGpu): Medium starts sharper there. */
  appleGpu?: boolean;
}

function probeDevice(): Probe {
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  try {
    const c = document.createElement("canvas");
    const gl = c.getContext("webgl2");
    // Without DecompressionStream (Safari before 16.4) the scene files cannot be unpacked: the page
    // view, rather than a 24 MB download that then fails.
    if (!gl || typeof DecompressionStream === "undefined") return { webgl2: false, tier: "low", coarse };
    const maxTextureSize = gl.getParameter(gl.MAX_TEXTURE_SIZE) as number;
    // Firefox and Safari answer RENDERER with the real GPU; Chrome still needs the extension.
    const dbg = gl.getExtension("WEBGL_debug_renderer_info");
    const renderer = String((dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)) ?? "");
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    const nav = navigator as Navigator & { deviceMemory?: number };
    return {
      webgl2: true,
      coarse,
      appleGpu: isAppleGpu(renderer),
      tier: chooseTier({
        coarsePointer: coarse,
        deviceMemory: nav.deviceMemory,
        hardwareConcurrency: nav.hardwareConcurrency,
        maxTextureSize,
        renderer,
      }),
    };
  } catch {
    return { webgl2: false, tier: "low", coarse };
  }
}

/** What the renderer does at tier `t` on this device (the ladder's top for it). */
function tierLook(t: Tier, probe: Probe): Quality {
  return tierQuality(t, window.devicePixelRatio, { coarse: probe.coarse, appleGpu: probe.appleGpu });
}

function maxScroll(): number {
  return Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
}

function instantScrollTo(top: number): void {
  window.scrollTo({ top, behavior: "instant" as ScrollBehavior });
}

function localStore(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

const CONTEXT_LOST = "The graphics card dropped the scene.";
/** The loading screen's label, and its live region's; a load for a new tier says "Switching to Low". */
const LOADING = "Loading the sect";
/**
 * A pick that needs a new load waits this long for the next (the arrow keys pick every radio they
 * pass), so arrowing from High to Low loads once.
 */
const RESTART_DELAY_MS = 400;
/** The opening view waits at most this long for its chunks (the backdrop proxies stand in after). */
const OPENING_TIMEOUT_MS = 25000;
/** The intro title starts fading in this long after the page is ready (the veil fades over 700 ms)... */
const INTRO_DELAY_MS = 350;
/** ...and takes this long. */
const INTRO_FADE_MS = 800;
/** Within this many scroll units of a hold, a click on its place opens the reader without flying. */
const AT_HOLD_UNITS = 30;

interface FallbackState {
  initial: ContentTarget | null;
  key: number;
}

/** The hold panels re-render only when their own props change (not on every scroll-driven state). */
const HoldPanel = memo(AreaPanel);

/** How opening a reader or the page view touches browser history. */
type HistoryMode = "push" | "replace" | "none";

export default function SectExperience() {
  const params = useMemo(() => parseSectParams(window.location.search), []);
  const base = sectAssetBase(params.set, process.env.NEXT_PUBLIC_SECT_ASSET_BASE);
  const probe = useMemo(() => probeDevice(), []);
  // Where the page opens: ?open=<hotspot>, else the URL hash (#projects, #project/dispatchai). A link
  // to something that is not here says so (the notice) instead of landing silently at the start.
  const deepLink = useMemo(() => resolveDeepLink(params.open, window.location.hash), [params]);
  /** The page's own history entries, and the hash that follows the camera (lib/sect/history.ts). */
  const pageHistory = useMemo(() => new PageHistory(window.history, window.location), []);
  const deep = deepLink.link;
  const [notice, setNotice] = useState<string | null>(deepLink.note);
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  /** The page opens on the view the poster still shows (the loading screen shows it behind its text). */
  const posterOk = useMemo(
    () => posterStart(window.location.search, window.location.hash, (navigator as Navigator & { connection?: NetworkHint }).connection),
    [],
  );
  /** False once the camera data shows a start the stills were not captured from. */
  const [posterFits, setPosterFits] = useState(true);

  // The tier: ?tier= (testing), else the visitor's pick (stored), else the probe's.
  const [stored, setStored] = useState<Tier | null>(() => (params.tier ? null : readTierChoice(localStore())));
  const { tier, source } = resolveTier({ recommended: probe.tier, stored, forced: probe.webgl2 ? params.tier : null });
  /**
   * The load under way or done: the tier its world and texture set are for, a count that reloads,
   * and what the loading screen says meanwhile (a new tier is named, so the bar going back makes sense).
   * `resumed`: it opens where a running page was (not the poster's view). `suspended`: the page view
   * opened during loading, and the load waits (nothing downloads) until the flight comes back.
   */
  const [load, setLoad] = useState(() => ({ tier, key: 0, label: LOADING, resumed: false, suspended: false }));
  /**
   * The tier the renderer's settings are for. A live change moves it off `load.tier` (desktop Medium
   * and High share the textures and the pipeline); a new load sets both.
   */
  const shownTier = useRef(tier);
  const [quality, setQuality] = useState<Quality>(() => tierLook(tier, probe));
  /** The shown tier's own quality: the ladder steps down from it and climbs back to it. */
  const [ceiling, setCeiling] = useState<Quality>(() => tierLook(tier, probe));
  /** The renderer back at tier `t`'s own settings (the ladder starts over from there). */
  const resetQuality = useCallback(
    (t: Tier) => {
      const q = tierLook(t, probe);
      setQuality(q);
      setCeiling(q);
    },
    [probe],
  );
  /** The pick could be stored (false: storage blocked, it lasts for this visit only). */
  const choiceSaved = useRef(true);
  /** Where a page loaded again for a new tier resumes (the scroll position, and a ?frame=N view). */
  const resume = useRef<{ u: number; frame: number | null } | null>(null);
  /** The world being built or shown, for a live change (set as soon as it exists, before React has it). */
  const world = useRef<{ ctx: WorldContext; streamer: ChunkStreamer } | null>(null);
  /** The focus was in the graphics popover when the page loaded again: the loading screen's picker takes it. */
  const [refocusPicker, setRefocusPicker] = useState(false);

  const [phase, setPhase] = useState<Phase>(probe.webgl2 ? "data" : "nowebgl");
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState({ value: 0.02, label: LOADING });
  const [data, setData] = useState<SectData | null>(null);
  const [ctx, setCtx] = useState<WorldContext | null>(null);
  const [store, setStore] = useState<SectStore | null>(null);
  const [globalSet, setGlobalSet] = useState<LoadedSet | null>(null);
  const [streamer, setStreamer] = useState<ChunkStreamer | null>(null);
  /** Resident chunks in flight order (a new array whenever the streamer changes anything). */
  const [chunks, setChunks] = useState<LoadedSet[]>([]);
  const [flyer, setFlyer] = useState<{ object: Object3D; lit: number } | null>(null);
  const [openingIds, setOpeningIds] = useState<string[] | null>(null);
  const [openingTimedOut, setOpeningTimedOut] = useState(false);
  const [track, setTrack] = useState<TrackViewport>(() => ({ width: window.innerWidth, height: window.innerHeight }));
  const [veil, setVeil] = useState(true);
  /** The music (SectMusic hands it out), for the loading screen's "Turn on sound". */
  const [music, setMusic] = useState<MusicEngine | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [mapOpen, setMapOpen] = useState(false);
  /** Fast travel under way (ink-travel.tsx), or null. */
  const [travel, setTravel] = useState<TravelRequest | null>(null);
  const travelRef = useRef<TravelRequest | null>(null);
  travelRef.current = travel;
  /** How far the place fast travel lands on has come toward settled (the ink's Loading line). */
  const [travelProgress, setTravelProgress] = useState(0);
  const [activeArea, setActiveArea] = useState<string | null>(null);
  const [atHold, setAtHold] = useState(false);
  const [reader, setReader] = useState<ContentTarget | null>(null);
  /** Bumped to remount the reader when Back/Forward changes what it shows inside. */
  const [readerKey, setReaderKey] = useState(0);
  // Without WebGL the page view is the page: it opens where the link points (?open= too).
  const [fallback, setFallback] = useState<FallbackState | null>(probe.webgl2 ? null : { initial: deep?.target ?? null, key: 0 });
  const [gathering, setGathering] = useState<AreaId | null>(null);
  /** Free look's hint (drag with a mouse, swipe sideways on a touch screen), until the first turn. */
  const lookHintOn = useMemo(() => !lookHintSeen(), []);
  const [lookHint, setLookHint] = useState(true);
  /** The view is turned round (free look past 90 degrees): the Recentre button shows. */
  const [lookedBack, setLookedBack] = useState(false);
  /** The intro title and its hint are up (the top of the flight): the Recentre button waits. */
  const [introUp, setIntroUp] = useState(true);

  const introRef = useRef<HTMLDivElement>(null);
  const panelRefs = useRef<Record<string, HTMLElement | null>>({});
  const hoverRef = useRef<HTMLDivElement>(null);
  const hudRef = useRef<HTMLDivElement>(null);
  const touching = useRef(false);
  const pendingResync = useRef(false);
  const jumpToken = useRef(0);
  /** Where a far jump that is gathering will land (keys pressed meanwhile step on from there). */
  const gather = useRef<{ frame: number; u: number } | null>(null);
  /** A voice command that arrived while the scene loaded: it runs once the page is ready. */
  const pendingVoice = useRef<VoiceCommand | null>(null);
  /** The load under way (the error screen stops its downloads). */
  const loadAbort = useRef<AbortController | null>(null);
  /**
   * A reader, the page view, the map or fast travel's ink covers the flight: page scrolls must not
   * move the camera (under the ink, the voice orb's own scroll to a section would move it off the
   * place being drawn).
   */
  const modalRef = useRef(false);
  modalRef.current = reader !== null || fallback !== null || mapOpen || travel !== null;
  const readerRef = useRef<ContentTarget | null>(null);
  readerRef.current = reader;
  const fallbackRef = useRef<FallbackState | null>(null);
  fallbackRef.current = fallback;
  /** The item the open reader shows (a project opened inside the forge reader changes it). */
  const shownItem = useRef<string | null>(null);
  /** False once the page has gone (a far jump still waiting must not scroll the next page). */
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  // Reduced motion follows the OS setting while the page is open.
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setReducedMotion(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  useEffect(() => {
    if (!store) return;
    store.reducedMotion = reducedMotion;
    wake(store);
  }, [store, reducedMotion]);

  // Page-level settings while /sect is open.
  useEffect(() => {
    const html = document.documentElement;
    const prevBehavior = html.style.scrollBehavior;
    const prevRestoration = history.scrollRestoration;
    const prevScrollbar = html.style.scrollbarWidth;
    const prevGutter = html.style.scrollbarGutter;
    html.style.scrollBehavior = "auto";
    // Full-bleed canvas: no scrollbar strip or gutter on this page.
    html.style.scrollbarWidth = "none";
    html.style.scrollbarGutter = "auto";
    history.scrollRestoration = "manual";
    window.scrollTo(0, 0);
    delete document.body.dataset.sectReady;
    // The track follows the viewport only on width changes or big height changes: the phone
    // address bar showing and hiding must not resize it (that jumped the page mid-flick).
    const onResize = () =>
      setTrack((cur) => {
        const n = nextTrackViewport(cur, window.innerWidth, window.innerHeight);
        return n.resize ? n.viewport : cur;
      });
    const touchStart = () => {
      touching.current = true;
    };
    const touchEnd = () => {
      touching.current = false;
    };
    window.addEventListener("resize", onResize);
    window.addEventListener("touchstart", touchStart, { passive: true });
    window.addEventListener("touchend", touchEnd, { passive: true });
    window.addEventListener("touchcancel", touchEnd, { passive: true });
    return () => {
      html.style.scrollBehavior = prevBehavior;
      html.style.scrollbarWidth = prevScrollbar;
      html.style.scrollbarGutter = prevGutter;
      history.scrollRestoration = prevRestoration;
      window.removeEventListener("resize", onResize);
      window.removeEventListener("touchstart", touchStart);
      window.removeEventListener("touchend", touchEnd);
      window.removeEventListener("touchcancel", touchEnd);
      delete document.body.dataset.sectReady;
    };
  }, []);

  // Lock scrolling until the scene is ready.
  useEffect(() => {
    const html = document.documentElement;
    if (phase === "ready" || phase === "nowebgl") html.style.overflow = "";
    else html.style.overflow = "hidden";
    return () => {
      html.style.overflow = "";
    };
  }, [phase]);

  const fail = useCallback((message: string) => {
    // The first error is the one to show: the canvas going away after a failed download loses the
    // graphics context too, and that must not replace the real message.
    setError((cur) => cur ?? message);
    setPhase("error");
    setVeil(true);
    loadAbort.current?.abort();
  }, []);

  // 1. Data files; 2. the global set and the chunks the opening view needs, together, with the sky
  // beside them; 3. the detail texture once the opening files are in.
  // Again for a new tier (restart): the cleanup cancels the downloads and frees the old world first.
  // Not while the page view, opened during loading, holds the load (suspended).
  useEffect(() => {
    if (!probe.webgl2 || load.suspended) return;
    const ac = new AbortController();
    loadAbort.current = ac;
    let made: { ctx: WorldContext; streamer: ChunkStreamer; global: LoadedSet | null; flyer: Object3D | null } | null = null;
    (async () => {
      try {
        const d = await loadSectData(base, params.flyer, ac.signal);
        installFog(lookFogConstants(d.meta));
        const map = buildScrollMap(d.camera.startFrame, d.camera.frameEnd, d.camera.holds, FLIGHT_SCROLL);
        const deepHold = deep ? map.holds.find((h) => h.id === deep.target.area) : undefined;
        // Loaded again for a new tier: back where the visitor was (a ?frame=N view still held, too).
        const r = resume.current;
        const f = r ? r.frame : params.frame;
        const startU = r ? r.u : f !== null ? frameToU(map, f) : deepHold ? deepHold.uMid : 0;
        const s = createStore(map, d.camera, startU, f, reducedMotion);
        s.frame = f ?? uToFrame(map, startU);
        // ?yaw=<degrees>: start turned, as a drag would leave it (the first scroll swings it back).
        s.look.yaw = r ? 0 : (startYaw(window.location.search) ?? 0);
        // The poster stills show this camera's start; a new path (another start or lens) does not match.
        const first = d.camera.frames.find((x) => x.f === d.camera.startFrame);
        if (!posterMatches(first?.fovY, d.camera.refAspect, d.camera.startFrame)) setPosterFits(false);
        // The sky downloads beside the scene files rather than before them: it is small, and in long
        // before the first set is prepared (which reads it).
        const skyLoad = loadSky(d.meta.sky.texture ? resolveAsset(d.base, d.meta.sky.texture) : null);
        // The shown tier: load.tier, or one a live change moved to since (same textures and pipeline).
        // Read after the last wait before the world exists: a live change until then has no world to
        // retune, so the world must be built for it.
        const t = shownTier.current;
        const q = tierQuality(t, window.devicePixelRatio, { coarse: probe.coarse });
        const c = createWorldContext(d, null, {
          shadows: q.post && q.msaa > 0,
          alphaToCoverage: q.post ? q.msaa > 0 : true,
          lowTextures: q.lowTextures,
          tier: t,
          deferDetail: true,
        });
        // Phones and tablets keep only the area they are in (the backdrop's proxies stand in for the rest).
        const budget = streamBudget(t, probe.coarse);
        const st: ChunkStreamer = new ChunkStreamer(
          c,
          () => {
            if (!ac.signal.aborted) setChunks(st.list());
          },
          budget,
        );
        made = { ctx: c, streamer: st, global: null, flyer: null };
        world.current = { ctx: c, streamer: st };
        const opening = st.needAt(s.frame);
        const gFiles = globalFiles(d.manifest, c.lowTextures);
        // Progress by bytes over the opening files, the manifest's figures standing in for sizes not
        // known yet (lib/sect/opening.ts downloadFraction). Shown as a running maximum, and only when
        // the percentage changes (each change re-renders the page). "Compiling shaders" once every
        // opening file has all its bytes (decoding, uploading and compiling follow): the line is free
        // then, and the detail texture starts downloading.
        const files = new Map<string, FileProgress>();
        const group = (list: readonly string[], bytes: number) => ({
          files: list.map((x) => {
            const f: FileProgress = { loaded: 0, total: 0, done: false };
            files.set(resolveAsset(d.base, x), f);
            return f;
          }),
          bytes,
        });
        const groups = [
          group(gFiles, 0),
          ...opening.map((id) => {
            const ch = d.manifest.chunks.find((x) => x.id === id);
            return ch ? group(chunkFiles(ch, c.lowTextures), c.lowTextures ? (ch.bytesLow ?? ch.bytes) : ch.bytes) : group([], 0);
          }),
        ];
        let shownPct = -1;
        let filesIn = false;
        const report = () => {
          if (ac.signal.aborted) return;
          const all = [...files.values()].every((f) => f.done || (f.total > 0 && f.loaded >= f.total));
          if (all && !filesIn) {
            filesIn = true;
            startDetail(c);
          }
          const value = all ? 0.96 : 0.05 + downloadFraction(groups) * 0.89;
          const pct = Math.round(value * 100);
          if (pct === shownPct) return;
          shownPct = pct;
          setProgress((p) => ({ value: Math.max(p.value, value), label: all ? "Compiling shaders" : load.label }));
        };
        const io = {
          onBytes: (url: string) => (loaded: number, total: number) => {
            const f = files.get(url);
            if (!f) return;
            f.loaded = loaded;
            if (total > 0) f.total = total;
            report();
          },
          onFileDone: (url: string) => {
            const f = files.get(url);
            if (f) f.done = true;
            report();
          },
        };
        // The opening files start downloading now, before the sky is in and React has the world.
        st.update(s.frame, s.frame, false, io);
        const sets = Promise.all([
          loadSet(c, "global", null, gFiles, { signal: ac.signal, ...io }),
          params.flyer ? loadFlyer(c, ac.signal) : Promise.resolve(null),
        ]);
        // Awaited below, after the sky: a failure meanwhile is not an unhandled rejection.
        sets.catch(() => {});
        const sky = await skyLoad;
        if (ac.signal.aborted) sky?.dispose();
        ac.signal.throwIfAborted();
        c.sky = sky;
        setData(d);
        setStore(s);
        setCtx(c);
        setStreamer(st);
        setOpeningIds(opening);
        setPhase("assets");
        setProgress((p) => ({ value: Math.max(p.value, 0.05), label: p.label }));
        const [g, fl] = await sets;
        if (ac.signal.aborted) {
          // Cancelled just after they arrived: nothing else will free them.
          disposeSet(c, g);
          if (fl) disposeObjects([fl.object], new Set([c.waterfallMaterial]));
        }
        ac.signal.throwIfAborted();
        made.global = g;
        made.flyer = fl?.object ?? null;
        st.setGlobalTris(g.tris);
        setGlobalSet(g);
        setFlyer(fl);
      } catch (e) {
        if (ac.signal.aborted) return;
        console.error(e);
        fail("The scene failed to load.");
      }
    })();
    return () => {
      ac.abort();
      // Free the GPU memory when the page goes away (or loads again for a new tier).
      if (made) {
        if (world.current?.ctx === made.ctx) world.current = null;
        made.streamer.dispose();
        if (made.global) disposeSet(made.ctx, made.global);
        if (made.flyer) disposeObjects([made.flyer], new Set([made.ctx.waterfallMaterial]));
        disposeWorldContext(made.ctx);
      }
    };
    // reducedMotion and deep are read once for the initial store; later changes go through effects.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, probe, fail, base, load]);

  // The opening view waits for its chunks, but not forever.
  useEffect(() => {
    if (phase !== "assets") return;
    const t = window.setTimeout(() => setOpeningTimedOut(true), OPENING_TIMEOUT_MS);
    return () => clearTimeout(t);
  }, [phase]);

  // The detail texture waits for the opening files; an opening that went on without one of them
  // (the timeout) starts it now.
  useEffect(() => {
    if (phase === "ready" && ctx) startDetail(ctx);
  }, [phase, ctx]);

  // The poster still behind the loading screen (the attribute shows it; the server's script may have
  // set it already): only while the opening view is the poster's, and not over an error.
  const posterOn = posterOk && posterFits && !load.resumed && veil && (phase === "data" || phase === "assets" || phase === "ready");
  useEffect(() => {
    const html = document.documentElement;
    if (posterOn) html.setAttribute(POSTER_ATTR, "");
    else html.removeAttribute(POSTER_ATTR);
  }, [posterOn]);
  useEffect(() => () => document.documentElement.removeAttribute(POSTER_ATTR), []);

  // Stream chunks around the camera. Not on the error screen (it would fetch the failed area again
  // and again), and nothing loads or drops while the page view covers the flight.
  useEffect(() => {
    if (!streamer || !store || phase === "error") return;
    // Looking back at rest: once the view has come to rest turned round, the area behind may load
    // (desktops: the phone budget has no look-back slot). It stays until the camera moves on, so
    // turning to and fro at a stop does not load and drop it again and again.
    let lookingBack = false;
    const tick = () => {
      if (store.paused) return;
      // Until the opening view is up, plan as a stop at the shown frame: only the area it lands in
      // loads (the next area would share its bandwidth and delay the first picture). A far jump
      // that is gathering wins over a flight still under way (End pressed during a J flight).
      const opening = phase !== "ready" ? store.frame : null;
      const target = store.gatherFrame ?? (store.flight ? store.flight.toFrame : opening);
      const ready = phase === "ready" && !store.paused;
      const back = isLookingBack(store.look);
      if (!ready || isMoving(store) || target !== null) lookingBack = false;
      else if (back && cameraStill(store)) lookingBack = true;
      setLookedBack(ready && back);
      setIntroUp(introPresence(store.u, 12) > 0.01);
      streamer.update(store.frame, target, ready && !isMoving(store), undefined, lookingBack);
    };
    tick();
    const id = window.setInterval(tick, 150);
    return () => clearInterval(id);
  }, [streamer, store, phase]);

  // Dropped chunks leave the scene in the commit that follows; free them after it.
  useEffect(() => {
    streamer?.flushDisposals();
  }, [streamer, chunks]);

  const openingReady =
    openingTimedOut ||
    (openingIds !== null && streamer !== null && openingIds.every((id) => streamer.isReady(id) || streamer.status().failed.includes(id)));

  // The world has rendered: open the page.
  const onRendered = useCallback(() => {
    setProgress({ value: 1, label: "Ready" });
    setPhase((p) => (p === "error" ? p : "ready"));
  }, []);

  const onContextLost = useCallback(() => fail(CONTEXT_LOST), [fail]);

  // The quality ladder (scene.tsx Driver). For a tier the visitor picked it is a safety net only:
  // under 25 fps (not 50) and only the resolution steps down, so High still looks like High (and
  // they can pick a lower tier themselves). Either way it climbs back once frames have room again.
  // ?tier= keeps it off.
  const keepLook = source === "choice";
  const keepLookRef = useRef(keepLook);
  keepLookRef.current = keepLook;
  const onDegrade = useCallback((cadenceMs: number | null) => {
    setQuality((q) => degradeQuality(q, window.devicePixelRatio, { keepLook: keepLookRef.current, cadenceMs }) ?? q);
  }, []);
  const onClimb = useCallback(() => {
    setQuality((q) => upgradeQuality(q, ceiling, window.devicePixelRatio) ?? q);
  }, [ceiling]);

  // --- graphics -----------------------------------------------------------------------------------

  const liveRef = useRef({ store, phase });
  liveRef.current = { store, phase };

  /** Takes the world down for a new load: the canvas goes, and the loading screen comes back. */
  const clearWorld = useCallback((label: string) => {
    setCtx(null);
    setStreamer(null);
    setStore(null);
    setData(null);
    setGlobalSet(null);
    setFlyer(null);
    setChunks([]);
    setOpeningIds(null);
    setOpeningTimedOut(false);
    setError(null);
    setPhase("data");
    setProgress({ value: 0.02, label });
    setVeil(true);
    setMapOpen(false);
    setTravel(null);
    setGathering(null);
    setHovered(null);
    jumpToken.current++;
    delete document.body.dataset.sectReady;
  }, []);

  /**
   * Loads the sect again for tier `t`, in place: the canvas goes (R3F loses its context, freeing the
   * GPU memory), the load effect's cleanup cancels the downloads and frees the world, and the loading
   * screen comes back. Files that had arrived come from the HTTP cache. A running page resumes where
   * the visitor was.
   */
  const restart = useCallback(
    (t: Tier) => {
      const { store: s, phase: p } = liveRef.current;
      if (p === "ready" && s) resume.current = { u: s.flight ? s.flight.toU : s.targetU, frame: s.frameOverride };
      setRefocusPicker(document.activeElement?.closest("[data-sect-quality]") != null);
      // Reload after an error with the same tier is not a switch.
      const label = t === shownTier.current ? LOADING : `Switching to ${TIER_LABELS[t]}`;
      shownTier.current = t;
      setLoad((l) => ({ tier: t, key: l.key + 1, label, resumed: resume.current !== null, suspended: false }));
      resetQuality(t);
      clearWorld(label);
    },
    [resetQuality, clearWorld],
  );

  /** The visitor picks a tier (the loading screen, the graphics button): stored, then applied below. */
  const pick = useCallback(
    (t: Tier) => {
      choiceSaved.current = writeTierChoice(localStore(), t);
      setStored(t);
      // The shown tier picked again: the ladder starts over from it.
      if (t === shownTier.current) resetQuality(t);
    },
    [resetQuality],
  );

  // A new tier: desktop Medium and High swap in place (resolution, MSAA, bloom, wet rock, far rock,
  // stream budget); any other change loads again, a moment later (the arrow keys pick every radio
  // they pass). After an error a pick only waits for Reload.
  useEffect(() => {
    if (phase === "error" || phase === "nowebgl" || tier === shownTier.current) return;
    const change = tierChange(shownTier.current, tier, window.devicePixelRatio, probe.coarse);
    if (change === "live") {
      shownTier.current = tier;
      resetQuality(tier);
      const w = world.current;
      if (w) {
        retuneWorld(w.ctx, tier);
        w.streamer.setBudget(streamBudget(tier, probe.coarse));
      }
      return;
    }
    const timer = window.setTimeout(() => restart(tier), RESTART_DELAY_MS);
    return () => clearTimeout(timer);
  }, [tier, phase, probe, restart, resetQuality]);

  // "Read as page" while the scene loads: its downloads stop (the page view's own pictures would share
  // the line with them) and the world goes; back on the flight the load starts again, the files that
  // had arrived coming from the HTTP cache.
  useEffect(() => {
    if (fallback !== null && !load.suspended && (phase === "data" || phase === "assets")) {
      setLoad((l) => ({ ...l, key: l.key + 1, suspended: true }));
      clearWorld(load.label);
    } else if (fallback === null && load.suspended) {
      setLoad((l) => ({ ...l, key: l.key + 1, suspended: false }));
    }
  }, [fallback, phase, load.suspended, load.label, clearWorld]);

  /** Reload on the error screen: a fresh page, with the visitor's pick when it could be stored. */
  const reloadAfterError = useCallback(() => {
    if (choiceSaved.current) window.location.reload();
    else restart(tier);
  }, [restart, tier]);

  useEffect(() => {
    if (phase !== "ready" || !store) return;
    resume.current = null;
    setRefocusPicker(false);
    // Place the scroll position on the shown frame (the camera is already there).
    instantScrollTo(uToScroll(store.targetU, maxScroll(), store.map.totalUnits));
    let timer = 0;
    let raf = requestAnimationFrame(() => {
      raf = requestAnimationFrame(() => {
        document.body.dataset.sectReady = "1";
        // The veil fades out (CSS opacity), then unmounts.
        timer = window.setTimeout(() => setVeil(false), 900);
      });
    });
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(timer);
    };
  }, [phase, store]);

  // --- flights -----------------------------------------------------------------------------------

  /**
   * Eases the camera to scroll position `toU` and puts the page scroll there at once. `instant`: it
   * is there at once (fast travel, under the ink).
   */
  const startFlight = useCallback(
    (toU: number, onArrive?: () => void, instant = false) => {
      if (!store) return;
      store.frameOverride = null;
      store.gatherFrame = null;
      setGathering(null);
      const fromU = store.u;
      const duration = store.reducedMotion || instant ? 0 : flightSeconds(toU - fromU);
      const toFrame = uToFrame(store.map, toU);
      store.targetU = toU;
      if (duration > 0) store.flight = { fromU, toU, t0: performance.now(), duration, toFrame, onArrive };
      else {
        store.flight = null;
        store.u = toU;
      }
      instantScrollTo(uToScroll(toU, maxScroll(), store.map.totalUnits));
      wake(store);
      if (duration === 0) onArrive?.();
    },
    [store],
  );

  /**
   * Flies to scroll position `toU`. Chunks the destination needs that are not on the GPU yet are
   * gathered first (the indicator shows; the backdrop proxies stand in meanwhile), so the camera
   * never arrives at nothing; after 12 s it goes anyway and the proxies stand in until they come. A
   * newer jump or the visitor's own scrolling cancels a waiting one. Resolves false when cancelled so.
   * (The keys' steps between stops; the rail's, the list's, links', the voice agent's and Home and
   * End's jumps go under the ink instead when their place is not loaded: goTo.)
   */
  const jumpTo = useCallback(
    async (toU: number, onArrive?: () => void): Promise<boolean> => {
      if (!store) return false;
      const token = ++jumpToken.current;
      if (Math.abs(store.u - toU) < 1 && !store.flight) {
        store.targetU = toU;
        store.gatherFrame = null;
        setGathering(null);
        onArrive?.();
        return true;
      }
      const frame = uToFrame(store.map, toU);
      const missing = streamer?.missingAt(frame) ?? [];
      if (streamer && missing.length > 0) {
        store.gatherFrame = frame;
        gather.current = { frame, u: toU };
        const area = nearestHold(store.map, toU);
        setGathering(area && isAreaId(area) ? area : null);
        streamer.update(store.frame, frame, false);
        // Wanted while this is still the latest jump: a cancelled one lets go of its loads.
        await Promise.all(missing.map((id) => streamer.whenReady(id, 12000, () => token === jumpToken.current)));
        // A newer jump, the visitor's own scrolling, or the page went away meanwhile.
        if (token !== jumpToken.current || !alive.current || streamer.isDisposed) return false;
        store.gatherFrame = null;
        setGathering(null);
      }
      startFlight(toU, onArrive);
      return true;
    },
    [store, streamer, startFlight],
  );

  /**
   * Goes to an area's hold: flies there, or, when its area is not loaded yet (the jump would have to
   * gather it in view) and the overlay is up, goes there under fast travel's ink (spreading from the
   * control that asked: inkOrigin), so the place is drawn and settled before it shows, as from the
   * map. `onArrive` runs once the camera is there (after the ink has cleared). `toU`: a place on the
   * track other than the hold (Home: the very start), the ink's card still naming `area`. While the
   * ink is up for another travel, that one wins and this does nothing.
   */
  const goTo = useCallback(
    (area: string, onArrive?: () => void, toU?: number) => {
      if (travelRef.current) return;
      const hold = store?.map.holds.find((h) => h.id === area);
      if (!store || !hold) {
        onArrive?.();
        return;
      }
      const u = toU ?? hold.uMid;
      const missing = streamer?.missingAt(uToFrame(store.map, u)) ?? [];
      if (params.ui && phase === "ready" && isAreaId(area) && missing.length > 0) {
        setTravel({ key: performance.now(), area, at: inkOrigin(), then: onArrive, ...(toU !== undefined ? { u: toU } : {}) });
        return;
      }
      void jumpTo(u, onArrive);
    },
    [store, streamer, params, phase, jumpTo],
  );

  /**
   * Notes an open reader in browser history: a new entry when it opens over the flight ("push"),
   * else this entry rewritten (moving between readers, a link that opened it).
   */
  const recordReader = useCallback(
    (t: ContentTarget, mode: HistoryMode) => {
      if (mode === "none" || !params.ui) return;
      const cur = pageHistory.current();
      const ours = cur !== null && (cur.reader !== null || cur.page);
      const push = mode === "push" && !ours;
      const depth = (cur?.depth ?? 0) + (push ? 1 : 0);
      pageHistory.write(
        push ? "push" : "replace",
        { reader: t, page: false, depth, nested: false },
        readerUrl(t, window.location.pathname, window.location.search),
        t.area,
      );
    },
    [params, pageHistory],
  );

  const openReader = useCallback(
    (t: ContentTarget, mode: HistoryMode = "push") => {
      setMapOpen(false);
      setReader({ ...t });
      readerRef.current = t;
      shownItem.current = t.item;
      recordReader(t, mode);
      if (store) {
        store.selected = t.item;
        wake(store);
      }
    },
    [store, recordReader],
  );

  /** Takes the reader down without touching history (Back did that, or another view replaces it). */
  const dropReader = useCallback(() => {
    setReader(null);
    readerRef.current = null;
    shownItem.current = null;
    if (store) {
      store.selected = null;
      store.focused = null;
      wake(store);
    }
  }, [store]);

  /**
   * The visitor closes the reader: its history entries go too. The walk back finishes later; until
   * its popstate the hash does not follow the camera (pageHistory), and the entry it lands on is
   * renamed to the place the camera is at (not where the first reader opened).
   */
  const closeReader = useCallback(() => {
    const area = readerRef.current?.area ?? null;
    dropReader();
    pageHistory.leave(area);
  }, [dropReader, pageHistory]);

  /**
   * The reader opened or closed a project inside it (the forge's list and details). Opening one
   * from the list adds an entry (Back returns to the list); stepping between projects, or opening
   * the reader at a project, rewrites the entry.
   */
  const onReaderItem = useCallback(
    (item: string | null) => {
      const r = readerRef.current;
      if (!r) return;
      const prev = shownItem.current;
      shownItem.current = item;
      if (store) {
        store.selected = item;
        wake(store);
      }
      if (!params.ui) return;
      const cur = pageHistory.current();
      if (!cur?.reader) return;
      const t: ContentTarget = { area: r.area, item, ...(r.filter ? { filter: r.filter } : {}) };
      const url = readerUrl(t, window.location.pathname, window.location.search);
      if (item && !prev) pageHistory.write("push", { reader: t, page: false, depth: cur.depth + 1, nested: true }, url);
      else if (!item && cur.nested) history.back();
      else pageHistory.write("replace", { ...cur, reader: t }, url);
    },
    [store, params, pageHistory],
  );

  /**
   * Go to a content target: fly to its area (if not there), then open the reader when asked.
   * `after` runs on arrival (not when the visitor cancels the flight by scrolling).
   */
  const navigate = useCallback(
    (t: ContentTarget, open: boolean, opts: { record?: HistoryMode; after?: () => void } = {}) => {
      if (!store) return;
      const hold = store.map.holds.find((h) => h.id === t.area);
      const there = hold !== undefined && Math.abs(store.targetU - hold.uMid) < AT_HOLD_UNITS && !store.flight;
      const arrive = () => {
        if (open) openReader(t, opts.record ?? "push");
        opts.after?.();
      };
      if (there) {
        arrive();
        return;
      }
      // Fast travel's ink is up: the place it goes to wins.
      if (travelRef.current) return;
      setReader(null);
      readerRef.current = null;
      shownItem.current = null;
      goTo(t.area, arrive);
    },
    [store, goTo, openReader],
  );

  // --- scroll and input ----------------------------------------------------------------------------

  // Scroll drives the camera target. A ?frame=N view holds until the visitor scrolls themselves
  // (wheel, touch, keys); a flight is cancelled the same way (the camera then glides on from where
  // it is). Programmatic scrolls never clear either.
  useEffect(() => {
    if (!store) return;
    const userInput = () => {
      if (store.frameOverride !== null) store.frameOverride = null;
      if (store.flight) store.flight = null;
      if (store.gatherFrame !== null) {
        jumpToken.current++;
        store.gatherFrame = null;
        setGathering(null);
      }
    };
    const keyInput = (e: KeyboardEvent) => {
      if ([" ", "Spacebar"].includes(e.key) && !(e.target as HTMLElement | null)?.closest?.("button, a, input, textarea")) userInput();
    };
    const onScroll = () => {
      const total = store.map.totalUnits;
      if (modalRef.current) {
        // Something scrolled the page under the reader or page view (an anchor, the voice orb
        // scrolling to a section id the page view also has): put it back.
        const want = uToScroll(store.targetU, maxScroll(), total);
        if (Math.abs(window.scrollY - want) > 1) instantScrollTo(want);
        return;
      }
      if (store.frameOverride !== null) return;
      store.targetU = scrollToU(window.scrollY, maxScroll(), total);
      wake(store);
    };
    window.addEventListener("wheel", userInput, { passive: true });
    window.addEventListener("touchstart", userInput, { passive: true });
    window.addEventListener("keydown", keyInput);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("wheel", userInput);
      window.removeEventListener("touchstart", userInput);
      window.removeEventListener("keydown", keyInput);
      window.removeEventListener("scroll", onScroll);
    };
  }, [store]);

  // Keys between holds: PageDown/PageUp, arrows, J/K; Home/End to the ends. Not while a reader,
  // the page view, the voice panel or any input has focus.
  useEffect(() => {
    if (!store || phase !== "ready") return;
    const onKey = (e: KeyboardEvent) => {
      if (modalRef.current || e.defaultPrevented) return;
      const t = e.target as HTMLElement | null;
      if (t?.closest?.('input, textarea, select, [contenteditable="true"], [role="dialog"], #sect-places')) return;
      const intent = navKeyIntent(e);
      if (!intent) return;
      e.preventDefault();
      // From where the camera is headed: a gathering far jump's landing (presses made while it
      // gathers each count), a flight's end, else the scroll position (with reduced motion, the stop
      // the camera shows for it, so the first press always moves).
      const g = gather.current;
      const from =
        g && store.gatherFrame === g.frame
          ? g.u
          : store.flight
            ? store.flight.toU
            : store.reducedMotion
              ? nearestStop(store.map, store.targetU).u
              : store.targetU;
      const stop = navKeyTarget(store.map, from, intent);
      if (!stop) return;
      // Home and End are far jumps: to a place not loaded yet they go under the ink, as the rail's
      // do (goTo). The steps between stops fly, gathering what they must, as a scroll does.
      const area = intent === "first" || intent === "last" ? nearestHold(store.map, stop.u) : null;
      if (area) goTo(area, undefined, stop.u);
      else void jumpTo(stop.u);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [store, phase, jumpTo, goTo]);

  // Keep the same place in the journey when the track changes height (not while a finger is down).
  useEffect(() => {
    if (!store || phase !== "ready") return;
    const resync = () => {
      instantScrollTo(uToScroll(store.targetU, maxScroll(), store.map.totalUnits));
      wake(store);
    };
    if (touching.current) {
      pendingResync.current = true;
      const onEnd = () => {
        if (pendingResync.current) {
          pendingResync.current = false;
          resync();
        }
      };
      window.addEventListener("touchend", onEnd, { once: true });
      return () => window.removeEventListener("touchend", onEnd);
    }
    resync();
  }, [track, store, phase]);

  // While a reader or the page view is open the orb keeps only its button (its "tap to talk" pill
  // would cover the reader's footer), and the scene stops redrawing behind it (scene.tsx Driver).
  const modalOpen = reader !== null || fallback !== null;
  // The Jin Yong references' card (lore-card.tsx): nothing of it while a reader, the page view, the
  // map or fast travel's ink is up.
  const lore = useLoreCard(modalOpen || mapOpen || travel !== null);
  // The map counts as a modal here too: the scene stops redrawing under it, and on a phone the orb
  // moves to the bottom centre (sect.css), where the map's tabs leave it room.
  const covered = modalOpen || mapOpen;
  useEffect(() => {
    if (store) {
      store.modal = covered;
      wake(store);
    }
    if (covered) document.body.dataset.sectModal = "1";
    else delete document.body.dataset.sectModal;
    return () => {
      delete document.body.dataset.sectModal;
    };
  }, [covered, store]);

  // The page view pauses the 3D view; leaving it (or a reader) re-syncs the scroll.
  useEffect(() => {
    if (!store) return;
    store.paused = fallback !== null;
    if (fallback === null && phase === "ready") instantScrollTo(uToScroll(store.targetU, maxScroll(), store.map.totalUnits));
    wake(store);
  }, [store, fallback, phase]);

  // Deep links: open the reader the URL asked for, once the page is ready (this entry then names
  // it; closing it drops ?open= from the address bar).
  const deepDone = useRef(false);
  useEffect(() => {
    if (phase !== "ready" || deepDone.current) return;
    deepDone.current = true;
    if (deep?.open && params.frame === null) openReader(deep.target, "replace");
  }, [phase, deep, params, openReader]);

  // A link to something that is not here: say so for a while.
  useEffect(() => {
    if (!notice || phase !== "ready") return;
    const t = window.setTimeout(() => setNotice(null), 9000);
    return () => clearTimeout(t);
  }, [notice, phase]);

  // The hash names a section (typed into the address bar, or a link on the page). Back/Forward to
  // one of the page's own entries is the popstate handler's (below).
  useEffect(() => {
    if (phase !== "ready") return;
    const onHash = () => {
      // The arrival of a walk back (or Back over a reader) renamed its entry to where the camera
      // is: the hashchange that arrival fires is not a request to fly anywhere.
      if (pageHistory.ownHashChange()) return;
      const st = readHistoryState(history.state);
      if (st && (st.reader || st.page)) return;
      const t = parseContentHash(window.location.hash);
      if (!t) return;
      if (fallback) setFallback((f) => ({ initial: t, key: (f?.key ?? 0) + 1 }));
      else navigate(t, t.item !== null, { record: "replace" });
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [phase, navigate, fallback, pageHistory]);

  // An entry left in history.state by an earlier visit (a reload on a reader's entry): this load
  // starts from scratch, so it counts as the entry the visitor arrived on.
  useEffect(() => {
    if (!readHistoryState(history.state)) return;
    try {
      history.replaceState(null, "", window.location.href);
    } catch {
      // Not important.
    }
  }, []);

  // Back and Forward over the page's own entries: close or reopen the reader or the page view (and
  // a project inside the forge reader).
  const activeAreaRef = useRef<string | null>(null);
  activeAreaRef.current = activeArea;
  useEffect(() => {
    if (!params.ui || phase === "nowebgl") return;
    const onPop = (e: PopStateEvent) => {
      // A walk back (closing) or Back over a reader or the page view that lands on a plain entry:
      // that entry may still name the area where the first reader opened (the reader's Next and
      // Previous moved on since). It is renamed to where the camera is, and nothing flies from it.
      const here = store ? nearestHold(store.map, store.u) : activeAreaRef.current;
      pageHistory.arrived(e.state, here, readerRef.current !== null || fallbackRef.current !== null);
      const st = readHistoryState(e.state);
      if (st?.page) {
        if (readerRef.current) dropReader();
        if (!fallbackRef.current) {
          const a = activeAreaRef.current;
          setFallback((f) => ({ initial: a && isAreaId(a) ? { area: a, item: null } : null, key: (f?.key ?? 0) + 1 }));
        }
        return;
      }
      if (fallbackRef.current) setFallback(null);
      const want = st?.reader ?? null;
      if (!want) {
        if (readerRef.current) dropReader();
        return;
      }
      if (phase !== "ready") return;
      const cur = readerRef.current;
      if (cur && cur.area === want.area) {
        if (shownItem.current === want.item) return;
        // Same reader, another item (a project and its list): remount it at that item.
        setReader({ ...want });
        readerRef.current = want;
        shownItem.current = want.item;
        setReaderKey((k) => k + 1);
        if (store) {
          store.selected = want.item;
          wake(store);
        }
        return;
      }
      navigate(want, true, { record: "none" });
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [params, phase, store, dropReader, navigate, pageHistory]);

  // The hash follows the current hold once the camera is there (replaceState: no history entries,
  // no hashchange). Not in the page view or a reader (their entries name them), nor with ?ui=0.
  const hashFollows = phase === "ready" && fallback === null && reader === null && params.ui;
  const hashFollowsRef = useRef(hashFollows);
  hashFollowsRef.current = hashFollows;

  // Overlay animation: panel opacity follows the camera's scroll position.
  useEffect(() => {
    if (!store) return;
    let raf = 0;
    let lastArea: string | null = null;
    let lastHolding = false;
    let lastU = NaN;
    let settledAt = 0;
    const shownAt = performance.now();
    let introFading = true;
    const tick = () => {
      raf = requestAnimationFrame(tick);
      const u = store.u;
      if (introFading || u !== lastU) {
        // The intro title fades in once the loading screen has mostly gone (its own title fades out
        // over the same picture), rather than showing under it. Its visibility follows the scroll
        // alone (the orb's prompt hides while the intro is hidden: sect.css).
        const k = Math.min(1, Math.max(0, (performance.now() - shownAt - INTRO_DELAY_MS) / INTRO_FADE_MS));
        introFading = k < 1;
        const intro = introRef.current;
        if (intro) {
          const a = introPresence(u, 12);
          intro.style.opacity = (a * k * k * (3 - 2 * k)).toFixed(3);
          intro.style.visibility = a > 0.01 ? "visible" : "hidden";
        }
      }
      if (u === lastU) {
        // At rest for a moment: the hash names the hold the camera is at.
        const now = performance.now();
        if (hashFollowsRef.current && !readerRef.current && lastArea && !store.flight && now - settledAt > 300) {
          // The area's section hash, and no ?open= left over from the link the visitor came in on.
          // Not while a reader's walk back is under way: it waits, and tries again next frame.
          if (pageHistory.follow(lastArea)) settledAt = Infinity;
        }
        return;
      }
      lastU = u;
      settledAt = performance.now();
      let presence = 0;
      // The contact panel stays up from the summit to the end of the track (the bottom of the page).
      for (const p of holdPresence(store.map, u, 16, true)) {
        presence = Math.max(presence, p.amount);
        const el = panelRefs.current[p.id];
        if (el) {
          el.style.opacity = p.amount.toFixed(3);
          el.style.visibility = p.amount > 0.01 ? "visible" : "hidden";
          el.style.transform = `translateY(${((1 - p.amount) * 14).toFixed(1)}px)`;
        }
      }
      const holding = presence > 0.4;
      if (holding !== lastHolding) {
        lastHolding = holding;
        setAtHold(holding);
      }
      const area = nearestHold(store.map, u);
      if (area !== lastArea) {
        lastArea = area;
        setActiveArea(area);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [store, phase, pageHistory]);

  // Portrait screens: at a stop whose items sit off the narrow view or under its labels
  // (lib/sect/opening.ts PORTRAIT_TURN_DEG), the view turns and tilts toward them once the camera has
  // come to rest there, as a drag would turn it; the next scroll swings it back (free look). Once per
  // arrival, never over a turn of the visitor's own, and given up the moment they touch the view or
  // scroll on.
  useEffect(() => {
    if (!store || phase !== "ready") return;
    let raf = 0;
    /** The hold this arrival has turned at (or found nothing to do at). */
    let done: string | null = null;
    let turn: { from: LookOffset; to: LookOffset; t0: number } | null = null;
    const tick = () => {
      raf = requestAnimationFrame(tick);
      const look = store.look;
      const hold = store.map.holds.find((h) => store.u >= h.u0 && store.u <= h.u1) ?? null;
      if (!hold) done = null;
      if (turn) {
        if (isDragging(look) || look.recenter !== null || isMoving(store) || store.paused) {
          turn = null;
          return;
        }
        // Under fast travel's ink the turn is done at once (the place shows already turned).
        const k = store.reducedMotion || store.inked ? 1 : Math.min(1, (performance.now() - turn.t0) / (PORTRAIT_TURN_SECONDS * 1000));
        const e = easeInOut(k, 1);
        look.yaw = turn.from.yaw + (turn.to.yaw - turn.from.yaw) * e;
        look.pitch = turn.from.pitch + (turn.to.pitch - turn.from.pitch) * e;
        wake(store, 150);
        if (k >= 1) turn = null;
        return;
      }
      if (!hold || hold.id === done || store.paused || store.modal || !cameraStill(store)) return;
      done = hold.id;
      const to = portraitTurn(hold.id, window.innerHeight > window.innerWidth);
      if (!isTurned(to) || isTurned(look)) return;
      turn = { from: { yaw: look.yaw, pitch: look.pitch }, to, t0: performance.now() };
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [store, phase]);

  // Touch: a flick (or a drag) that comes to rest within about a screen of the next stop glides on
  // to it, where the panel is up, rather than leaving the camera between places (lib/sect/opening.ts
  // flickStop). Rest is a moment with no scroll after the finger lifts (the momentum glide has ended).
  useEffect(() => {
    if (!store || phase !== "ready") return;
    let moved = false;
    let fromU = store.targetU;
    let timer = 0;
    const settle = () => {
      timer = 0;
      if (!moved || touching.current) return;
      moved = false;
      if (modalRef.current || store.paused || store.flight || store.gatherFrame !== null || store.frameOverride !== null || store.reducedMotion) return;
      const reach = (window.innerHeight * store.map.totalUnits) / Math.max(1, maxScroll());
      const to = flickStop(store.map, store.targetU, reach, store.targetU - fromU);
      if (to !== null) startFlight(to);
    };
    const arm = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(settle, 180);
    };
    const onStart = () => {
      moved = false;
      fromU = store.targetU;
      window.clearTimeout(timer);
    };
    const onScroll = () => {
      // Only the visitor's own scrolling: a flight or a resync puts the scroll position in place.
      if (!touching.current && !moved) return;
      moved = true;
      if (!touching.current) arm();
    };
    const onEnd = () => {
      if (moved) arm();
    };
    window.addEventListener("touchstart", onStart, { passive: true });
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("touchend", onEnd, { passive: true });
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("touchstart", onStart);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("touchend", onEnd);
    };
  }, [store, phase, startFlight]);

  // --- talk, hotspots, places --------------------------------------------------------------------

  // The first drag that turns the view retires the hint for good; unused, it fades after a while.
  const dragged = useRef(false);
  const onLookDrag = useCallback(() => {
    if (dragged.current) return;
    dragged.current = true;
    markLookHintSeen();
    setLookHint(false);
  }, []);
  // On a touch screen it waits for the intro to go (it sits where the intro's hint was).
  const lookHintUp = lookHintOn && lookHint && phase === "ready" && (!probe.coarse || !introUp);
  useEffect(() => {
    if (!lookHintUp) return;
    const t = window.setTimeout(() => setLookHint(false), 25000);
    return () => window.clearTimeout(t);
  }, [lookHintUp]);

  const talk = useCallback(() => {
    if (readerRef.current) closeReader();
    startTalk();
  }, [closeReader]);

  const onHover = useCallback((id: string | null, at: readonly [number, number] | null) => {
    const el = hoverRef.current;
    if (el) {
      // Hidden while the hovered point is behind the camera (the view turned away from it).
      el.style.opacity = id && at ? "1" : "0";
      // Anchored at the top centre of the object's projected box, above it. Kept 8 px inside the
      // window by its measured size (a title and a two-line blurb), so it is never cut off at an
      // edge, and moved off the stop's content panel when it would cover it (overlay.tsx
      // placeHoverLabel). Its content changes a frame late, so the next frame corrects the size.
      if (at) {
        const panels: DOMRect[] = [];
        for (const p of Object.values(panelRefs.current)) {
          if (!p || p.style.visibility !== "visible" || Number(p.style.opacity) < 0.05) continue;
          const r = p.getBoundingClientRect();
          if (r.width > 0 && r.height > 0) panels.push(r);
        }
        const [x, y] = placeHoverLabel(
          at,
          { w: el.offsetWidth, h: el.offsetHeight },
          { w: window.innerWidth, h: window.innerHeight },
          panels,
        );
        el.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px) translate(-50%, -100%)`;
      }
    }
    setHovered((h) => (h === id ? h : id));
  }, []);

  /** The Recentre button: the view swings back to the path's framing (as Escape does). */
  const recentre = useCallback(() => {
    if (store) recenterView(store);
  }, [store]);

  /** A click on a hotspot in the scene. */
  const onSelect = useCallback(
    (id: string) => {
      if (id === MOON_HOTSPOT) {
        talk();
        return;
      }
      const t = hotspotTarget(id);
      if (t) navigate(t, true);
    },
    [navigate, talk],
  );

  const focusPlace = useCallback(
    (id: string | null) => {
      if (!store) return;
      store.focused = id;
      wake(store);
    },
    [store],
  );

  const selectPlace = useCallback(
    (id: string) => {
      setMapOpen(false);
      const t = hotspotTarget(id);
      if (t) navigate(t, true);
    },
    [navigate],
  );

  const onHighlight = useCallback(
    (id: string | null) => {
      if (!store) return;
      store.focused = id;
      wake(store);
    },
    [store],
  );

  const onReaderNavigate = useCallback((t: ContentTarget) => navigate(t, true), [navigate]);

  const readAsPage = useCallback(() => {
    setMapOpen(false);
    const r = readerRef.current;
    const initial = r ?? (activeArea && isAreaId(activeArea) ? { area: activeArea, item: null } : null);
    setFallback((f) => ({ initial, key: (f?.key ?? 0) + 1 }));
    if (r) dropReader();
    // Its own history entry (it takes over a reader's), so Back returns to the flight.
    if (params.ui && phase !== "nowebgl") {
      const cur = pageHistory.current();
      if (!cur?.page) {
        const ours = cur !== null && cur.reader !== null;
        const depth = (cur?.depth ?? 0) + (ours ? 0 : 1);
        const url = plainUrl(initial?.area ?? null, window.location.pathname, window.location.search);
        pageHistory.write(ours ? "replace" : "push", { reader: null, page: true, depth, nested: cur?.nested ?? false }, url, initial?.area ?? null);
      }
    }
  }, [activeArea, dropReader, params, phase, pageHistory]);

  const exitPage = useCallback(() => {
    setFallback(null);
    pageHistory.leave(activeAreaRef.current);
  }, [pageHistory]);

  // The rail: fly to a place, or open its reader when the camera is already there.
  const onRail = useCallback(
    (id: string) => {
      if (!store || !isAreaId(id)) return;
      const hold = store.map.holds.find((h) => h.id === id);
      if (hold && Math.abs(store.targetU - hold.uMid) < AT_HOLD_UNITS && !store.flight) openReader({ area: id, item: null });
      else goTo(id);
    },
    [store, goTo, openReader],
  );

  // --- the map and fast travel ----------------------------------------------------------------------

  /** Where the map's files live (beside the asset sets: NEXT_PUBLIC_SECT_ASSET_BASE moves both). */
  const mapBase = sectAssetBase("map", process.env.NEXT_PUBLIC_SECT_ASSET_BASE);
  const openMap = useCallback(() => setMapOpen(true), []);
  const closeMap = useCallback(() => setMapOpen(false), []);
  /** The map's code: a new loader after a failed download, so the next opening tries again. */
  const mapFailed = useRef(() => {});
  const [MapView, setMapView] = useState(() => mapLoader(() => mapFailed.current()));
  mapFailed.current = () => {
    setMapOpen(false);
    setNotice("The map could not load. Check the connection and try again.");
    setMapView(() => mapLoader(() => mapFailed.current()));
  };
  /** The map's code, map.json and the picture this screen shows start loading (it opens drawn). */
  const prefetchMap = useCallback(() => {
    import("./map-view").then(
      (m) => m.prefetchMap(mapBase),
      () => {
        // The map's own load says so when it opens.
      },
    );
  }, [mapBase]);

  // M opens the map (inside it, M and Escape close it: map-view.tsx). Not over a reader, the page
  // view or fast travel, nor while typing.
  useEffect(() => {
    if (phase !== "ready" || !params.ui) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.key !== "m" && e.key !== "M") || e.ctrlKey || e.metaKey || e.altKey || e.repeat || e.defaultPrevented) return;
      if (readerRef.current || fallbackRef.current || document.querySelector(".sect-map, .sect-travel")) return;
      const t = e.target as HTMLElement | null;
      if (t?.closest?.('input, textarea, select, [contenteditable="true"], [role="dialog"]')) return;
      e.preventDefault();
      setMapOpen(true);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, params]);

  // Once the scene has settled, an idle moment fetches the map too, when nothing of the scene is
  // still streaming (a few tries; the Map button's hover and focus fetch it anyway).
  useEffect(() => {
    if (phase !== "ready" || !params.ui || !streamer) return;
    let timer = 0;
    let idle = 0;
    let tries = 0;
    const attempt = () => {
      if (streamer.status().loading.length > 0 && ++tries < 6) {
        timer = window.setTimeout(attempt, 5000);
        return;
      }
      if (typeof window.requestIdleCallback === "function") idle = window.requestIdleCallback(prefetchMap, { timeout: 4000 });
      else prefetchMap();
    };
    timer = window.setTimeout(attempt, 8000);
    return () => {
      window.clearTimeout(timer);
      if (idle && typeof window.cancelIdleCallback === "function") window.cancelIdleCallback(idle);
    };
  }, [phase, params, streamer, prefetchMap]);

  /**
   * A seal on the map was picked: the ink spreads from it (ink-travel.tsx), then arriveAt runs. Not
   * while one is under way (it would start the ink over).
   */
  const startTravel = useCallback((area: AreaId, at: readonly [number, number]) => {
    if (travelRef.current) return;
    setTravel({ key: performance.now(), area, at });
  }, []);

  /**
   * Under the ink, until the place at scroll position `toU` has settled (lib/sect/settle.ts): every
   * area its view draws streamed in, on the GPU and drawn (the neighbours' stand-ins swapped for
   * them), nothing filling in any more (grass, the mirror's capture, the hold focus, the detail
   * texture), then the renderer's counts and the view still for a few frames. The scene draws it
   * behind the ink meanwhile (every display frame once its areas are in; at the idle rate while they
   * stream, which leaves the loading its time). Reports the progress for the ink's Loading line.
   * Resolves when settled, when `signal` aborts (the ink gave up, or went), or when something moved
   * the camera off the place.
   */
  const settleAt = useCallback(
    (toU: number, signal: AbortSignal) =>
      new Promise<void>((resolve) => {
        if (!store || !streamer || !ctx || signal.aborted) {
          resolve();
          return;
        }
        const frame = uToFrame(store.map, toU);
        const watch = new SettleWatch();
        let raf = 0;
        let shown = -1;
        let unculled = false;
        const stop = () => {
          cancelAnimationFrame(raf);
          signal.removeEventListener("abort", stop);
          resolve();
        };
        signal.addEventListener("abort", stop);
        const tick = () => {
          if (!alive.current || streamer.isDisposed || store.flight || Math.abs(store.targetU - toU) > 1) {
            stop();
            return;
          }
          const place = streamer.settleAt(frame);
          const r = store.report;
          const busy: string[] = [];
          if (r.grass) busy.push("grass");
          if (r.reflection) busy.push("reflection");
          if (r.focus) busy.push("focus");
          if (detailSettling(ctx)) busy.push("detail");
          const st = watch.push({
            now: performance.now(),
            frames: r.frames,
            chunks: place.chunks,
            leaving: place.leaving.length,
            busy,
            gpu: `${r.geometries}:${r.textures}:${r.programs}`,
            view: `${store.frame.toFixed(2)}|${store.look.yaw.toFixed(4)}|${store.look.pitch.toFixed(4)}`,
          });
          if (params.debug) (window as unknown as { __sectSettle?: unknown }).__sectSettle = { ...st, chunks: place.chunks, leaving: place.leaving, busy };
          const pct = Math.round(st.progress * 50) / 50;
          if (pct !== shown) {
            shown = pct;
            setTravelProgress(pct);
          }
          if (place.chunks.every((c) => c.expected || c.done >= 1)) wake(store, 250);
          // Everything is in: one frame with nothing culled puts every mesh around the place on the
          // GPU (scene.tsx UncullOnce), so a look round after the ink uploads nothing. Its uploads
          // start the still count again.
          if (!unculled && st.waiting.length === 1 && st.waiting[0] === "still") {
            unculled = true;
            store.uncull = true;
          }
          if (st.settled) stop();
          else raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
      }),
    [store, streamer, ctx, params],
  );

  /**
   * Under the ink: the map closes, the camera is at the stop's hold (or at `toU`) at once (a far jump
   * still gathering gives way), and the place is drawn there until it has settled (settleAt). What
   * would grow or fade in meanwhile is there at once (store.inked).
   */
  const arriveAt = useCallback(
    async (area: AreaId, signal: AbortSignal, toU?: number) => {
      setMapOpen(false);
      const hold = store?.map.holds.find((h) => h.id === area);
      if (!store || !hold) return;
      const u = toU ?? hold.uMid;
      jumpToken.current++;
      // The streamer counts it as a far jump (so it then faces the way a visitor reads on from the
      // place: lib/sect/chunks.ts travelAfterJump) and starts on the place's own area at once.
      streamer?.update(store.frame, uToFrame(store.map, u), false);
      startFlight(u, undefined, true);
      store.inked = true;
      try {
        await settleAt(u, signal);
      } finally {
        store.inked = false;
      }
    },
    [store, streamer, startFlight, settleAt],
  );
  const travelArrive = useCallback((signal: AbortSignal) => (travel ? arriveAt(travel.area, signal, travel.u) : Promise.resolve()), [travel, arriveAt]);
  const endTravel = useCallback(() => {
    const then = travelRef.current?.then;
    setTravel(null);
    setTravelProgress(0);
    // What the jump was for (a reader to open there), now that the place shows.
    then?.();
    // The focus was in the map (gone now, so back on the Map button that opened it, or on the panel or
    // the rail's place left behind): the panel of the place arrived at takes it (else the rail's place,
    // else the Map button). Not out of the orb's chat, nor out of a reader that opened meanwhile.
    window.setTimeout(() => {
      const a = document.activeElement;
      if (keepsFocus(a) || a?.closest('[role="dialog"]') || readerRef.current) return;
      flightFocusFallback()?.focus({ preventScroll: true });
    }, 0);
  }, []);

  /** The seal of the stop the camera holds at: its reader, as the rail does. */
  const openHere = useCallback((area: AreaId) => openReader({ area, item: null }), [openReader]);

  // The voice agent and the orb's chips: fly the camera, and open the forge reader for projects. A
  // command given while the scene loads waits for it (the last one wins).
  const routeVoice = (cmd: VoiceCommand) => {
    const t = commandTarget(cmd);
    if (!t) return;
    if (fallback || phase === "nowebgl") {
      setFallback((f) => ({ initial: t, key: (f?.key ?? 0) + 1 }));
      return;
    }
    if (phase !== "ready") {
      pendingVoice.current = cmd;
      return;
    }
    setMapOpen(false);
    // The named item glows once the camera is there (not when the visitor scrolls the flight
    // away), and for a few seconds when no reader opens over it.
    const item = t.item;
    const s = store;
    const after =
      item && s
        ? () => {
            s.focused = item;
            wake(s, 1500);
            window.setTimeout(() => {
              if (s.focused === item && !readerRef.current) {
                s.focused = null;
                wake(s);
              }
            }, 6000);
          }
        : undefined;
    navigate(t, cmd.type !== "scroll", { after });
  };
  useVoiceRouting(routeVoice, params.debug);
  const routeVoiceRef = useRef(routeVoice);
  routeVoiceRef.current = routeVoice;
  useEffect(() => {
    if (phase !== "ready" || !pendingVoice.current) return;
    const cmd = pendingVoice.current;
    pendingVoice.current = null;
    routeVoiceRef.current(cmd);
  }, [phase]);

  // --- derived view data -------------------------------------------------------------------------

  const holds = useMemo(() => data?.camera.holds ?? [], [data]);
  const railStops = useMemo<RailStop[]>(
    () =>
      holds
        .filter((h) => isAreaId(h.id))
        .map((h) => {
          const info = areaInfo(h.id as AreaId);
          return { id: h.id, label: info.label, zh: info.zh, section: SECTION_NAMES[h.id as AreaId] };
        }),
    [holds],
  );

  const sides = useMemo(() => {
    const out: Record<string, "left" | "right" | null> = {};
    if (!data) return out;
    for (const h of data.camera.holds) {
      // As the stop frames it (lib/sect/framing.ts): the path's view from where the camera stands at
      // the hold, turned by the stop's framing.
      const s = sampleCamera(data.camera.frames, framingFrame(data.camera.holds, h.frame));
      const landmark =
        data.meta.areas.find((a) => a.id === h.id)?.anchor ?? data.meta.hotspots.find((x) => x.id === h.id)?.center ?? null;
      const q = composeLook(s.q, framingAt(data.camera.holds, h.frame));
      out[h.id] = panelSide({ f: h.frame, ...s, q }, data.camera.refAspect, landmark);
    }
    return out;
  }, [data]);

  const anchors = useMemo<Vec3[]>(() => {
    if (!data) return [];
    const out: Vec3[] = [];
    for (const a of AREAS) {
      const p = data.meta.areas.find((x) => x.id === a.id)?.anchor ?? data.meta.hotspots.find((x) => x.id === a.id)?.center;
      if (p) out.push(p);
    }
    return out;
  }, [data]);

  // The moon starts a call only from the summit's own stretch of the flight (it is in view from the
  // gate on, and a surprise microphone prompt there would be unkind).
  const moonFromFrame = useMemo(() => {
    if (!data) return null;
    const area = data.meta.areas.find((a) => a.id === "summit");
    if (area && area.frameEnd > area.frameStart) return area.frameStart;
    const hold = data.camera.holds.find((h) => h.id === "summit");
    return hold ? hold.frame - 120 : null;
  }, [data]);

  // Places: each area's landmark, its other named spots, then every item it holds.
  const placeGroups = useMemo<PlaceGroup[]>(() => {
    const meta = data?.meta.hotspots ?? [];
    return AREAS.map((a) => {
      const items = new Map<string, string>();
      items.set(a.id, hotspotLabel(a.id, a.label).title);
      for (const h of meta) {
        const t = hotspotTarget(h.id);
        if (t && t.area === a.id && (t.item === null || isThing(h.id)) && h.id !== a.id) items.set(h.id, hotspotLabel(h.id, h.label).title);
      }
      for (const it of areaItemHotspots(a.id)) items.set(it.id, it.label);
      return {
        id: a.id,
        section: SECTION_NAMES[a.id],
        items: [...items].map(([id, label]) => ({ id, label, area: a.id })),
      };
    });
  }, [data]);

  /** One ref callback per hold panel, kept across renders (a new one would re-attach the panel). */
  const panelRefFns = useRef(new Map<string, (el: HTMLElement | null) => void>());
  const panelRef = (id: string) => {
    let fn = panelRefFns.current.get(id);
    if (!fn) {
      fn = (el) => {
        panelRefs.current[id] = el;
      };
      panelRefFns.current.set(id, fn);
    }
    return fn;
  };

  const trackHeight = store ? Math.round(store.map.totalUnits * pxPerUnit(track.height) + track.height) : track.height;

  // The hover label: the name, its Chinese name and a line about it (lib/sect/content.ts), plus the
  // Jin Yong reference the hotspot holds under the pointer, or its fixed note (lib/sect/lore.ts).
  const hoverLabel = useMemo(() => (hovered ? hotspotLabel(hovered, ctx?.hotspotMap.get(hovered)?.label) : null), [hovered, ctx]);
  // Nothing of it before meta.json has the references (today's files show the page as it was).
  const hasLore = (data?.meta.lore?.length ?? 0) > 0;
  const hoverLabelNote = useMemo(() => hoverNote(hovered, lore.hosted, hasLore), [hovered, lore.hosted, hasLore]);
  // The references at each stop, named for screen readers on its panel (only those meta.json has).
  const loreAt = useMemo(() => loreByArea(data?.meta.lore), [data]);

  const gatherInfo = gathering ? areaInfo(gathering) : null;
  const showUi = phase === "ready" && params.ui;
  // A phone on its side (wide but short): the compact place row runs along the top (overlay.tsx), so
  // every panel takes the bottom-left corner (a top-right one would sit on the row), and the row's
  // place name hides while a panel names the place.
  const shortScreen = track.width >= 768 && track.height < 500;
  // The graphics picker (loading screen) and button (overlay); none with ?tier= (testing).
  const picker = source !== "link" && probe.webgl2 ? { tier, recommended: probe.tier, onPick: pick } : null;

  return (
    <>
      {phase !== "nowebgl" && (
        <div className="fixed inset-0 z-0 bg-[var(--sect-ink)]">
          {data && store && ctx && phase !== "error" && (
            <SectCanvas
              store={store}
              meta={data.meta}
              ctx={ctx}
              global={globalSet}
              chunks={chunks}
              streamer={streamer}
              flyer={flyer?.object ?? null}
              flyerLit={(flyer?.lit ?? 0) > 0}
              flyerPath={data.flyerPath}
              clouds={data.clouds}
              anchors={anchors}
              moonFromFrame={moonFromFrame}
              quality={quality}
              ceiling={ceiling}
              adaptive={params.frame === null && params.tier === null}
              frameBudgetMs={keepLook ? CHOICE_FRAME_BUDGET_MS : AUTO_FRAME_BUDGET_MS}
              baked={data.manifest.baked}
              debug={params.debug}
              debugEl={hudRef}
              openingReady={openingReady}
              onHover={onHover}
              onSelect={onSelect}
              onLore={lore.onLore}
              onLookDrag={onLookDrag}
              onRendered={onRendered}
              onDegrade={onDegrade}
              onClimb={onClimb}
              onContextLost={onContextLost}
            />
          )}
        </div>
      )}

      {/* Scroll track: its height is the length of the journey. */}
      {phase !== "nowebgl" && <div aria-hidden className="pointer-events-none relative z-0" style={{ height: trackHeight }} />}

      {showUi && (
        <>
          <TopLinks onReadAsPage={readAsPage} />
          <main>
            <h1 className="sr-only">Sun Moon Divine Cult: Bill Zhang&apos;s portfolio</h1>
            <IntroTitle ref={introRef} />
            {holds.map((h) =>
              isAreaId(h.id) ? (
                <HoldPanel
                  key={h.id}
                  area={h.id}
                  side={shortScreen ? "left" : (sides[h.id] ?? undefined)}
                  onOpen={openReader}
                  onTalk={talk}
                  references={loreAt[h.id]}
                  ref={panelRef(h.id)}
                />
              ) : null,
            )}
          </main>
          <SectionRail stops={railStops} active={activeArea} atHold={atHold} onJump={onRail} />
          <CompactRail stops={railStops} active={activeArea} atHold={atHold} labelHidden={introUp || (shortScreen && atHold)} onJump={onRail} />
          <div className="fixed right-[4.6rem] top-3 z-30 md:right-6 md:top-4">
            <MapButton open={mapOpen} onOpen={openMap} onPrefetch={prefetchMap} />
          </div>
          {mapOpen && data && store && (
            <Suspense fallback={<div aria-hidden className="sect-map" />}>
              <MapView
                base={mapBase}
                stops={railStops}
                groups={placeGroups}
                meta={data.meta}
                camera={data.camera}
                frame={store.frame}
                active={activeArea}
                atHold={atHold}
                onClose={closeMap}
                onTravel={startTravel}
                onOpenHere={openHere}
                onFocusPlace={focusPlace}
                onSelectPlace={selectPlace}
              />
            </Suspense>
          )}
          {travel && (
            <InkTravel request={travel} reducedMotion={reducedMotion} progress={travelProgress} arrive={travelArrive} onDone={endTravel} />
          )}
          {/* Fast travel's ink says it is gathering itself. */}
          {gatherInfo && !travel && <Gathering label={gatherInfo.label} />}
          {notice && <Notice text={notice} onDismiss={() => setNotice(null)} />}
          {/* Not on a phone on its side: the place row fills its spot, and the wide view needs it least. */}
          {lookHintOn && !shortScreen && (
            <LookHint visible={lookHintUp && !modalOpen && !gatherInfo && !notice && !lookedBack} touch={probe.coarse} />
          )}
          {/* Not over the intro, the Gathering status or a notice: they share its place on phones. */}
          <RecentreButton visible={lookedBack && !introUp && !gatherInfo && !notice && !modalOpen && !mapOpen && !travel} onRecentre={recentre} />
          <HoverLabel ref={hoverRef} label={hoverLabel} note={hoverLabelNote} />
          <LoreCard ref={lore.ref} id={lore.view.content} visible={lore.view.shown !== null} reducedMotion={reducedMotion} />
          <AreaReader
            key={readerKey}
            target={reader}
            onItemChange={onReaderItem}
            onClose={closeReader}
            onNavigate={onReaderNavigate}
            onHighlight={onHighlight}
            onTalk={talk}
            onReadAsPage={readAsPage}
          />
        </>
      )}

      {params.debug && phase !== "nowebgl" && <DebugHud ref={hudRef} />}

      {veil && phase !== "nowebgl" && (
        <LoadingScreen
          progress={progress.value}
          label={progress.label}
          phaseLabel={phase === "ready" ? "Ready" : load.label}
          error={error}
          visible={phase !== "ready"}
          onReload={error ? reloadAfterError : undefined}
          onReadAsPage={readAsPage}
          quality={picker ? { ...picker, autoFocus: refocusPicker } : undefined}
          sound={music ? <SoundPrompt engine={music} /> : "reserve"}
          poster
        />
      )}

      {fallback && (
        <ContentFallback
          key={fallback.key}
          initial={fallback.initial}
          onTalk={talk}
          onExit={phase === "nowebgl" ? undefined : exitPage}
        />
      )}

      {/* ?ui=0 shows the scene alone (screenshots): no orb either. */}
      {params.ui && <SectVoice />}
      {/* Background music and its sound toggle (none without WebGL: no flight to follow). */}
      {params.ui && phase !== "nowebgl" && (
        <SectMusic
          store={store}
          areas={data?.meta.areas ?? null}
          loading={phase === "data" || phase === "assets"}
          away={fallback !== null || phase === "error"}
          debug={params.debug}
          extra={showUi && picker ? <QualityButton {...picker} /> : undefined}
          onEngine={setMusic}
        />
      )}
    </>
  );
}
