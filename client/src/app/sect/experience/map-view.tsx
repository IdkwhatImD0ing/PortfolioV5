"use client";

/**
 * The map of the sect, opened by the Map button in the top bar or the M key: the painted map
 * (public/sect/map, lib/sect/map.ts), mounted like a hanging scroll that unrolls over the dimmed
 * scene, with one seal per stop on its painted terrace, the walkways between them as a dotted route,
 * and the visitor's own mark (明, the sun and the moon) where the camera is. A seal names its place
 * on hover, on keyboard focus, or on a first tap on a touch screen; a click (Enter, or the Travel
 * button) fast-travels there, Wukong-style (ink-travel.tsx). At the stop the camera already holds at,
 * the seal opens that place's reader instead, as the rail does.
 *
 * Three layouts, set by sect.css's grid (this file reads which one is on screen):
 *   wide (a desktop): the title, a card for the chosen place and the keys on the left, the map at
 *     full height in the middle, every place and item on the right;
 *   medium (a tablet, a short window): the title over the map, the list beside it;
 *   phone: the map under the title, the chosen place docked under the map with its Travel button,
 *     and the list as the other tab.
 *
 * Every place and item (the old Places list) works as it always has: an item flies there and opens
 * its reader.
 *
 * This file loads only when the map first opens (sect-experience.tsx imports it lazily), and
 * map.json and the picture with it, or a little before (prefetchMap, when the browser is idle). It
 * is not mounted while the map is closed, so the scene's frame rate never pays for it.
 *
 * Keyboard: Tab or the arrow keys move between the seals in route order (Up toward the summit when
 * the route climbs the picture), Enter travels, Escape or M closes and gives the focus back.
 */
import {
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { isAreaId, type AreaId } from "@/lib/sect/areas";
import { areaSummary } from "@/lib/sect/content";
import {
  clearOf,
  hereMark,
  linePath,
  mapFit,
  mapKeyStep,
  mapStops,
  parseSectMap,
  pickMapImage,
  platePosition,
  routeClimbsUp,
  routeLine,
  spreadMarkers,
  walkLine,
  worldToUv,
  type MapImage,
  type SectMap,
} from "@/lib/sect/map";
import { resolveAsset } from "@/lib/sect/parse";
import type { CameraData, SectMeta } from "@/lib/sect/types";
import { flightFocusFallback, trapTab, useModalLifecycle } from "../content/modal";
import { Emblem, HereGlyph } from "./map-emblems";
import type { PlaceGroup, RailStop } from "./overlay";

/** map.json, once per visit (a failed load is tried again on the next opening). */
let mapLoad: { base: string; promise: Promise<SectMap> } | null = null;

function loadMap(base: string): Promise<SectMap> {
  if (mapLoad && mapLoad.base === base) return mapLoad.promise;
  const promise = fetch(resolveAsset(base, "map.json"))
    .then((r) => {
      if (!r.ok) throw new Error(`map.json: HTTP ${r.status}`);
      return r.json() as Promise<unknown>;
    })
    .then(parseSectMap);
  mapLoad = { base, promise };
  promise.catch(() => {
    if (mapLoad?.promise === promise) mapLoad = null;
  });
  return promise;
}

/** The map's stage on a screen of this size, roughly (for choosing a picture before it opens). */
function guessStage(): { w: number; h: number } {
  const w = window.innerWidth;
  const h = window.innerHeight;
  if (w >= 1100 && h >= 560) return { w: w - 2 * Math.min(21 * 16, Math.max(16 * 16, w * 0.21)), h: h - 2 * 16 };
  return w >= 768 ? { w: w - 23 * 16, h: h - 7 * 16 } : { w: w - 16, h: h - 8.5 * 16 };
}

/** Loads map.json and the picture this screen would show, so the map opens drawn. */
export function prefetchMap(base: string): void {
  loadMap(base)
    .then((m) => {
      const s = guessStage();
      const img = new Image();
      img.decoding = "async";
      img.src = resolveAsset(base, pickMapImage(m, s.w, s.h, window.devicePixelRatio).src);
    })
    .catch(() => {
      // The map says so when it opens.
    });
}

export interface MapViewProps {
  /** Where map.json lives ("/sect/map"). */
  base: string;
  /** The stops in route order, with their names and sections. */
  stops: readonly RailStop[];
  /** Every place and item, grouped by area (the list beside the map). */
  groups: readonly PlaceGroup[];
  meta: Pick<SectMeta, "areas" | "hotspots">;
  camera: CameraData;
  /** The camera's frame as the map opened (the visitor's mark). */
  frame: number;
  /** The stop nearest the camera, and whether the camera holds there. */
  active: string | null;
  atHold: boolean;
  onClose: () => void;
  /** Fast travel to a stop, the ink spreading from `at` (screen pixels). */
  onTravel: (area: AreaId, at: readonly [number, number]) => void;
  /** The stop the camera holds at: open its reader. */
  onOpenHere: (area: AreaId) => void;
  /** The list's items light up their objects in the scene, as before. */
  onFocusPlace: (id: string | null) => void;
  onSelectPlace: (id: string) => void;
}

type Shown = { id: AreaId; how: "hover" | "focus" | "tap" } | null;
type Layout = "wide" | "medium" | "phone";

const HEAD_ID = "sect-map-title";
/** The visitor's mark's radius (sect.css .sect-map-here-glyph) and how far past a seal's rim it sits. */
const HERE_R = 12.8;
const HERE_GAP = 7;
/** The scroll is all but unrolled this long after its sheet first draws (sect.css: 0.05 s + 0.62 s). */
const UNROLL_MS = 560;

export default function MapView({
  base,
  stops,
  groups,
  meta,
  camera,
  frame,
  active,
  atHold,
  onClose,
  onTravel,
  onOpenHere,
  onFocusPlace,
  onSelectPlace,
}: MapViewProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const sideRef = useRef<HTMLDivElement>(null);
  const tabsRef = useRef<HTMLDivElement>(null);
  const plateRef = useRef<HTMLDivElement>(null);
  const sealRefs = useRef<(HTMLButtonElement | null)[]>([]);
  /** How the last press came (a first tap on a touch screen names the seal; a click travels). */
  const pointerKind = useRef<string>("mouse");

  const [map, setMap] = useState<SectMap | null>(null);
  const [failed, setFailed] = useState(false);
  /** The stage's size, its left edge on the screen, and which layout sect.css has set. */
  const [stage, setStage] = useState<{ w: number; h: number; left: number; layout: Layout }>({ w: 0, h: 0, left: 0, layout: "medium" });
  const [pane, setPane] = useState<"map" | "list">("map");
  const [shown, setShown] = useState<Shown>(null);
  /** The seal last chosen by keyboard or tap: the wide layout's card keeps showing it. */
  const [picked, setPicked] = useState<AreaId | null>(null);
  /** The list item under the pointer or the focus: its place lights up on the map. */
  const [item, setItem] = useState<string | null>(null);
  const [loadedSrc, setLoadedSrc] = useState<string | null>(null);
  const [plateAt, setPlateAt] = useState<{ left: number; top: number } | null>(null);
  /**
   * The scroll has unrolled: until then a seal's plate stays hidden, so a name never hangs over the
   * scene beside a map still rolled up (a keyboard opening focuses the current seal at once).
   */
  const [unrolled, setUnrolled] = useState(false);

  useModalLifecycle(rootRef, true, flightFocusFallback);

  // An item lit from the list lets go of its glow in the scene when the map closes.
  const focusPlaceRef = useRef(onFocusPlace);
  focusPlaceRef.current = onFocusPlace;
  useEffect(() => () => focusPlaceRef.current(null), []);

  useEffect(() => {
    let live = true;
    loadMap(base).then(
      (m) => live && setMap(m),
      (e: unknown) => {
        console.warn("[sect] the map could not load", e);
        if (!live) return;
        setFailed(true);
        setPane("list");
      },
    );
    return () => {
      live = false;
    };
  }, [base]);

  // The stage's size (the picture fits inside it) and the layout: the side column shows on wide
  // screens, the tabs on phones (sect.css decides; this reads it).
  useLayoutEffect(() => {
    const el = stageRef.current;
    const root = rootRef.current;
    if (!el || !root) return;
    const shows = (x: HTMLElement | null) => !!x && getComputedStyle(x).display !== "none";
    const measure = () => {
      const layout: Layout = shows(sideRef.current) ? "wide" : shows(tabsRef.current) ? "phone" : "medium";
      // The phone's list tab hides the stage: keep the map's last size for when it comes back.
      if (!shows(el)) return;
      const r = el.getBoundingClientRect();
      // Its height without the padding kept for the hint under the picture.
      const pad = parseFloat(getComputedStyle(el).paddingBottom) || 0;
      const next = { w: r.width, h: Math.max(0, r.height - pad), left: r.left, layout };
      setStage((s) =>
        Math.abs(s.w - next.w) < 0.5 && Math.abs(s.h - next.h) < 0.5 && Math.abs(s.left - next.left) < 0.5 && s.layout === next.layout ? s : next,
      );
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    ro.observe(root);
    return () => ro.disconnect();
  }, [pane]);

  // The picture: chosen for the stage, and never a smaller one once a sharper is in (a resize back).
  const best = useRef<MapImage | null>(null);
  const image = useMemo(() => {
    if (!map || stage.w === 0) return best.current;
    const im = pickMapImage(map, stage.w, stage.h, typeof window === "undefined" ? 1 : window.devicePixelRatio);
    if (!best.current || !map.images.includes(best.current) || im.w > best.current.w) best.current = im;
    return best.current;
  }, [map, stage]);
  const { layout } = stage;
  const phone = layout === "phone";
  // Fitted in the stage with room round it for the scroll's rods (less on a short screen). On a phone,
  // at the top (the place docks under it); on a medium screen, centred on the screen when the list
  // beside leaves room (a tall map would otherwise sit off to the left of the middle).
  const fit = useMemo(() => {
    if (!image) return null;
    const pad = phone ? 12 : stage.h < 440 ? 16 : 24;
    const f = mapFit(stage, image, pad);
    if (f.w === 0) return f;
    if (phone) return { ...f, y: Math.min(f.y, pad) };
    if (layout === "wide") return f;
    const centred = window.innerWidth / 2 - stage.left - f.w / 2;
    return { ...f, x: Math.min(Math.max(centred, pad), Math.max(pad, stage.w - f.w - pad)) };
  }, [image, stage, phone, layout]);
  /**
   * A seal's size in px (the sheet's --seal), and the room the seals keep between them: 40 on a
   * desktop's map, smaller as the painting gets smaller (a phone, a phone on its side), so neighbours
   * never cover each other or the walkways between them. The button round it stays 44 px.
   */
  const seal = Math.min(phone ? 32 : 40, Math.max(24, Math.round((fit?.w ?? 0) * 0.088)));

  const sheetUp = !!image && !!fit && fit.w > 0;
  useEffect(() => {
    if (!sheetUp || unrolled) return;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const t = window.setTimeout(() => setUnrolled(true), still ? 0 : UNROLL_MS);
    return () => window.clearTimeout(t);
  }, [sheetUp, unrolled]);

  const placed = useMemo(() => (image ? mapStops(meta, camera, image.xf) : []), [image, meta, camera]);
  const info = useMemo(() => new Map(stops.map((s, i) => [s.id, { ...s, n: i + 1 }])), [stops]);
  const seals = useMemo(() => placed.filter((s) => info.has(s.id)), [placed, info]);
  const here = useMemo(() => (image && fit ? hereMark(camera, frame, image.xf, fit.w, fit.h) : null), [image, fit, camera, frame]);
  const truePx = useMemo(() => (fit ? seals.map((s) => [s.uv[0] * fit.w, s.uv[1] * fit.h] as const) : []), [seals, fit]);
  // Seals too near each other part a little (a thin line keeps each one's place); at today's sizes
  // none do, and the visitor's mark never moves one: it steps aside itself, just past the seal's rim.
  const sealPx = useMemo(() => (fit ? spreadMarkers(truePx, seal + 6, { w: fit.w, h: fit.h }, [], seal / 2 + 2) : []), [truePx, fit, seal]);
  const herePx = useMemo(() => {
    if (!here || !fit) return null;
    const discs = sealPx.map(([x, y]) => ({ x, y, r: seal / 2 + HERE_GAP }));
    return clearOf([here.uv[0] * fit.w, here.uv[1] * fit.h], discs);
  }, [here, fit, sealPx, seal]);
  // The walkways the painting shows (map.json "route"), else the camera's flight.
  const route = useMemo(() => {
    if (!image) return [];
    const tol = Math.max(1, image.w / 900);
    return map?.route ? walkLine(map.route, image.xf, image.w, image.h, tol) : routeLine(camera, image.xf, image.w, image.h, tol);
  }, [image, map, camera]);
  const routeD = useMemo(() => (fit && route.length > 1 ? linePath(route, fit.w, fit.h) : ""), [route, fit]);
  const upIsForward = useMemo(() => routeClimbsUp(seals), [seals]);

  // The item lit from the list: its place's seal, and a dot where the item is when meta.json has it.
  const itemArea = useMemo(() => (item ? (groups.find((g) => g.items.some((p) => p.id === item))?.id ?? null) : null), [item, groups]);
  const itemDot = useMemo(() => {
    if (!item || !image || !fit) return null;
    const h = meta.hotspots.find((x) => x.id === item);
    if (!h) return null;
    const [u, v] = worldToUv(image.xf, h.center);
    return u >= 0 && u <= 1 && v >= 0 && v <= 1 ? ([u * fit.w, v * fit.h] as const) : null;
  }, [item, image, fit, meta]);

  // The focus goes in: to the stop the camera is at once the seals are there, the title until then
  // (and for good when the map cannot load). Not if the visitor has moved it on meanwhile.
  const focused = useRef(false);
  useEffect(() => {
    if (focused.current) return;
    const inside = rootRef.current?.contains(document.activeElement) ?? false;
    if (seals.length > 0) {
      focused.current = true;
      if (!inside || document.activeElement === titleRef.current) {
        sealRefs.current[Math.max(0, seals.findIndex((s) => s.id === active))]?.focus({ preventScroll: true });
      }
    } else if (!inside) titleRef.current?.focus({ preventScroll: true });
  }, [seals, active]);

  // The plate follows the shown seal (measured, then placed inside the stage): beside it, or on a
  // phone docked under the map (where it covers no other seal), or over the map's foot when the
  // screen is too short for that.
  const shownIndex = shown ? seals.findIndex((s) => s.id === shown.id) : -1;
  useLayoutEffect(() => {
    const el = plateRef.current;
    if (shownIndex < 0 || !el || !fit) {
      setPlateAt(null);
      return;
    }
    let p: { left: number; top: number };
    if (phone) {
      const room = stage.h + (stageRef.current ? parseFloat(getComputedStyle(stageRef.current).paddingBottom) || 0 : 0);
      p = { left: fit.x, top: Math.max(fit.y, Math.min(fit.y + fit.h + 22, room - el.offsetHeight - 4)) };
    } else {
      const [x, y] = sealPx[shownIndex];
      // Clear of the other seals and the visitor's mark where it can be.
      const avoid = sealPx.filter((_, i) => i !== shownIndex).map(([sx, sy]) => ({ x: fit.x + sx, y: fit.y + sy, r: seal / 2 + 2 }));
      if (herePx) avoid.push({ x: fit.x + herePx[0], y: fit.y + herePx[1], r: HERE_R });
      // It may reach out over the list beside the stage (it is gone again with the pointer).
      const view = { w: Math.max(stage.w, window.innerWidth - stage.left - 8), h: stage.h };
      p = platePosition([fit.x + x, fit.y + y], seal / 2 + 2, { w: el.offsetWidth, h: el.offsetHeight }, view, avoid, 10, 8);
    }
    setPlateAt((cur) => (cur && cur.left === p.left && cur.top === p.top ? cur : { left: p.left, top: p.top }));
  }, [shownIndex, sealPx, herePx, fit, stage, seal, phone, shown?.how]);

  const travel = useCallback(
    (id: AreaId, from: HTMLElement | null) => {
      if (id === active && atHold) {
        onOpenHere(id);
        return;
      }
      // The card names where the ink goes (the seal under the pointer lets go of it as the ink covers it).
      setPicked(id);
      const r = from?.getBoundingClientRect();
      onTravel(id, r ? [r.left + r.width / 2, r.top + r.height / 2] : [window.innerWidth / 2, window.innerHeight / 2]);
    },
    [active, atHold, onOpenHere, onTravel],
  );

  const onSealClick = (id: AreaId, i: number) => {
    // A first tap on a touch screen names the place (its plate has the Travel button); a second, or a
    // click, travels.
    if (pointerKind.current === "touch" && !(shown?.id === id && shown.how === "tap")) {
      setShown({ id, how: "tap" });
      setPicked(id);
      return;
    }
    travel(id, sealRefs.current[i]);
  };

  const onSealKey = (e: ReactKeyboardEvent<HTMLButtonElement>, i: number) => {
    pointerKind.current = "keyboard";
    const next = mapKeyStep(e.key, i, seals.length, upIsForward);
    if (next === null) return;
    e.preventDefault();
    sealRefs.current[next]?.focus({ preventScroll: true });
  };

  const onKeyDown = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      if (shown?.how === "tap") setShown(null);
      else onClose();
      return;
    }
    const t = e.target as HTMLElement;
    if ((e.key === "m" || e.key === "M") && !e.ctrlKey && !e.metaKey && !e.altKey && !t.closest("input, textarea, select")) {
      e.preventDefault();
      e.stopPropagation();
      onClose();
      return;
    }
    trapTab(e, rootRef.current);
  };

  const imgSrc = image ? resolveAsset(base, image.src) : null;
  const shownStop = shownIndex >= 0 ? info.get(seals[shownIndex].id) : undefined;
  const shownHere = shownStop?.id === active;
  // On a phone the plate docks and carries the Travel button; elsewhere it names the seal beside it
  // (the wide layout's card has the rest).
  const docked = phone;
  const sealName = (id: AreaId) => {
    const s = info.get(id)!;
    const cur = id === active;
    // Between stops the nearest one is only near: a press flies there.
    const where = cur ? (atHold ? ", you are here" : ", you are near") : "";
    return `${s.label}, ${s.section}${where}: ${cur && atHold ? "open" : "travel here"}`;
  };
  // The wide layout's card: the seal under the pointer or the focus, else the one last chosen, else
  // where the visitor is.
  const cardId = (shown?.id ?? picked ?? (active && isAreaId(active) ? active : null) ?? seals[0]?.id ?? null) as AreaId | null;
  const cardIndex = cardId ? seals.findIndex((s) => s.id === cardId) : -1;

  return (
    <div
      ref={rootRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby={HEAD_ID}
      aria-describedby="sect-map-help"
      tabIndex={-1}
      onKeyDown={onKeyDown}
      onPointerDownCapture={(e) => {
        pointerKind.current = e.pointerType;
      }}
      data-pane={pane}
      data-layout={layout}
      className="sect-map"
    >
      <div className="sect-map-head">
        <p className="sect-map-eyebrow">
          The Ming Sect{" "}
          <span lang="zh" className="sect-zh sect-map-zh">
            明教全图
          </span>
        </p>
        <h2 id={HEAD_ID} ref={titleRef} tabIndex={-1} className="sect-map-title font-serif text-[var(--sect-paper)] outline-none">
          Map of the sect
        </h2>
      </div>

      <button
        type="button"
        onClick={onClose}
        aria-label="Close the map"
        className="sect-map-close sect-panel sect-plate sect-ctl relative grid h-11 w-11 shrink-0 place-items-center rounded-[3px] text-[var(--sect-paper-soft)] hover:text-[var(--sect-gold)] md:h-10 md:w-10"
      >
        <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden>
          <path d="M2 2l12 12M14 2L2 14" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      </button>

      {/* Wide screens: the chosen place, and how the map works. */}
      <div ref={sideRef} className="sect-map-side">
        {cardId && cardIndex >= 0 && (
          <PlaceCard
            stop={info.get(cardId)!}
            total={seals.length}
            here={cardId === active}
            atHold={atHold}
            onGo={() => travel(cardId, sealRefs.current[cardIndex])}
          />
        )}
        <div aria-hidden className="sect-map-legend">
          <p className="flex items-center gap-2.5">
            <HereGlyph className="h-6 w-6 shrink-0" />
            You are here
          </p>
          <p className="sect-map-keys pointer-coarse:hidden">
            <span>
              <kbd>↑</kbd>
              <kbd>↓</kbd> Choose
            </span>
            <span>
              <kbd>Enter</kbd> Travel
            </span>
            <span>
              <kbd>M</kbd> Close
            </span>
          </p>
        </div>
      </div>

      <div ref={stageRef} className="sect-map-stage">
        {fit && image && (
          <div
            className="sect-map-sheet"
            style={{ left: fit.x, top: fit.y, width: fit.w, height: fit.h, "--sheet-h": `${fit.h}px`, "--seal": `${seal}px` } as CSSProperties}
          >
            <span aria-hidden className="sect-map-rod sect-map-rod-top" />
            <span aria-hidden className="sect-map-rod sect-map-rod-bottom" />
            {imgSrc && (
              // eslint-disable-next-line @next/next/no-img-element -- a plain picture from the map's own folder, chosen for the screen
              <img
                key={imgSrc}
                src={imgSrc}
                alt=""
                decoding="async"
                draggable={false}
                onLoad={() => setLoadedSrc(imgSrc)}
                className="sect-map-picture"
                style={{ opacity: loadedSrc === imgSrc ? 1 : 0 }}
              />
            )}
            <svg className="pointer-events-none absolute inset-0" width={fit.w} height={fit.h} viewBox={`0 0 ${fit.w} ${fit.h}`} aria-hidden>
              {/* The route: gold beads ringed in ink along the painted walkways. */}
              {routeD && (
                <g fill="none" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="0.1 7.5">
                  <path d={routeD} stroke="rgba(30, 20, 12, 0.62)" strokeWidth="5.4" />
                  <path d={routeD} stroke="var(--sect-gold)" strokeWidth="2.7" />
                </g>
              )}
              {/* A seal moved off its place (too near another) keeps a thin line back to it. */}
              {sealPx.map(([x, y], i) => {
                const [tx, ty] = truePx[i];
                if (Math.hypot(x - tx, y - ty) < 4) return null;
                return (
                  <g key={seals[i].id} stroke="rgba(34, 24, 18, 0.7)" fill="rgba(34, 24, 18, 0.85)">
                    <path d={`M${tx.toFixed(1)} ${ty.toFixed(1)}L${x.toFixed(1)} ${y.toFixed(1)}`} strokeWidth="1.2" />
                    <circle cx={tx} cy={ty} r="2.4" stroke="none" />
                  </g>
                );
              })}
              {/* The way the camera looks, under the seals (the mark itself goes over them, below). */}
              {herePx && here?.heading != null && (
                <path
                  d="M0 0L-12 -26A28.6 28.6 0 0 1 12 -26Z"
                  transform={`translate(${herePx[0].toFixed(1)} ${herePx[1].toFixed(1)}) rotate(${here.heading.toFixed(1)})`}
                  fill="rgba(184, 65, 45, 0.3)"
                  stroke="rgba(184, 65, 45, 0.6)"
                  strokeWidth="1"
                />
              )}
              {itemDot && (
                <g className="sect-map-dot">
                  <circle cx={itemDot[0]} cy={itemDot[1]} r="9" fill="rgba(233, 199, 126, 0.35)" />
                  <circle cx={itemDot[0]} cy={itemDot[1]} r="4" fill="var(--sect-cinnabar)" stroke="var(--sect-paper)" strokeWidth="1.5" />
                </g>
              )}
            </svg>

            <ol aria-label="Stops along the flight" className="absolute inset-0">
              {seals.map((s, i) => {
                const [x, y] = sealPx[i] ?? [0, 0];
                const cur = s.id === active;
                return (
                  <li key={s.id} className="absolute" style={{ left: x, top: y }}>
                    <button
                      ref={(el) => {
                        sealRefs.current[i] = el;
                      }}
                      type="button"
                      aria-label={sealName(s.id)}
                      aria-current={cur ? "location" : undefined}
                      data-current={cur || undefined}
                      data-shown={shown?.id === s.id || (layout === "wide" && !shown && cardId === s.id && !cur) || undefined}
                      data-lit={itemArea === s.id || undefined}
                      className="sect-map-seal sect-ctl"
                      onClick={() => onSealClick(s.id, i)}
                      onKeyDown={(e) => onSealKey(e, i)}
                      onPointerEnter={(e) => {
                        if (e.pointerType === "mouse") setShown((v) => (v?.how === "tap" ? v : { id: s.id, how: "hover" }));
                      }}
                      onPointerLeave={(e) => {
                        if (e.pointerType === "mouse") setShown((v) => (v?.id === s.id && v.how === "hover" ? null : v));
                      }}
                      onFocus={(e) => {
                        if (!focusVisible(e.currentTarget)) return;
                        setShown((v) => (v?.how === "tap" ? v : { id: s.id, how: "focus" }));
                        setPicked(s.id);
                      }}
                      onBlur={() => setShown((v) => (v?.id === s.id && v.how === "focus" ? null : v))}
                    >
                      <span className="sect-map-seal-face">
                        <Emblem id={s.id} className="sect-map-emblem" />
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
            {/* The visitor's mark, over the seals (it never takes the pointer). */}
            {herePx && (
              <div className="sect-map-here" style={{ left: herePx[0], top: herePx[1] }} aria-hidden>
                <span className="sect-map-here-ring" />
                <HereGlyph className="sect-map-here-glyph" />
              </div>
            )}
          </div>
        )}

        {/* The plate of the seal under the pointer or the focus (named for sight; the seal names
            itself to screen readers). On a phone it docks under the map and holds the Travel button. */}
        {shownStop && (
          <div
            ref={plateRef}
            className={`sect-map-plate sect-panel sect-plate rounded-[3px] ${docked ? "sect-map-dock pointer-events-auto" : "pointer-events-none"}`}
            style={plateAt && unrolled ? { left: plateAt.left, top: plateAt.top, width: docked && fit ? fit.w : undefined } : { left: 0, top: 0, visibility: "hidden" }}
            aria-hidden={docked ? undefined : true}
          >
            {docked && <Emblem id={shownStop.id as AreaId} className="sect-map-dock-emblem" />}
            <div className="min-w-0 flex-1">
              <p className="flex items-baseline gap-2.5">
                <span lang="zh" className="sect-zh text-[1.15rem] leading-tight tracking-[0.16em] text-[var(--sect-gold)]">
                  {shownStop.zh}
                </span>
                <span className="text-[0.6rem] uppercase tracking-[0.24em] text-[var(--sect-paper-soft)]">{String(shownStop.n).padStart(2, "0")}</span>
              </p>
              <p className="mt-0.5 text-[0.86rem] leading-snug text-[var(--sect-paper)]">{shownStop.label}</p>
              <p className="sect-map-plate-section mt-1 text-[0.62rem] uppercase tracking-[0.24em] text-[var(--sect-paper-soft)]">
                {shownStop.section}
                {shownHere && <span className="ml-2 text-[var(--sect-gold)]">· {atHold ? "You are here" : "You are near"}</span>}
              </p>
            </div>
            {docked && (
              <button
                type="button"
                onClick={() => travel(shownStop.id as AreaId, sealRefs.current[shownIndex])}
                aria-label={shownHere && atHold ? `Open ${shownStop.label}` : `Travel to ${shownStop.label}`}
                className="sect-map-go sect-ctl flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-[2px] px-3.5 text-[0.68rem] uppercase tracking-[0.2em]"
              >
                {shownHere && atHold ? "Open" : "Travel"}
                <span aria-hidden>→</span>
              </button>
            )}
          </div>
        )}

        {failed && (
          <p className="sect-plate absolute inset-x-4 top-1/2 -translate-y-1/2 rounded-[3px] px-4 py-3 text-center text-[0.86rem] text-[var(--sect-paper-soft)]">
            The map could not be drawn. Every place is in the list.
          </p>
        )}

        {/* Under the picture: the visitor's mark explained, and how to travel (the wide layout says
            so in its side column, and keeps this for screen readers). */}
        <div
          className="sect-map-hint sect-plate"
          data-covered={docked && shownStop && plateAt && unrolled ? true : undefined}
          style={fit && fit.w > 0 ? { left: fit.x + fit.w / 2, top: fit.y + fit.h + 22, bottom: "auto" } : undefined}
        >
          <span aria-hidden className="flex items-center gap-2 text-[var(--sect-paper)]">
            <HereGlyph className="h-5 w-5 shrink-0" />
            You are here
          </span>
          <span aria-hidden className="text-[var(--sect-gold)]">
            ·
          </span>
          <p id="sect-map-help">
            <span className="pointer-coarse:hidden">Click a seal to travel there. M or Esc closes the map.</span>
            <span className="hidden pointer-coarse:inline">Tap a seal, then Travel.</span>
          </p>
        </div>
      </div>

      <PlacesIndex
        groups={groups}
        active={active}
        onItem={(id) => {
          setItem(id);
          onFocusPlace(id);
        }}
        onSelect={onSelectPlace}
      />

      {/* Phones: the map and the list share the screen, one at a time. The gap in the middle is the
          voice orb's (sect.css moves it there while a dialog is open). */}
      <div ref={tabsRef} className="sect-map-tabs" role="group" aria-label="Show">
        <button type="button" aria-pressed={pane === "map"} onClick={() => setPane("map")} className="sect-map-tab sect-ctl">
          Map
        </button>
        <button type="button" aria-pressed={pane === "list"} onClick={() => setPane("list")} className="sect-map-tab sect-ctl">
          All places
        </button>
      </div>
    </div>
  );
}

/**
 * The wide layout's card for the chosen place, as a game's map names the place picked before you go:
 * its emblem and Chinese name, the English name and section, a line about it, and the way there.
 */
function PlaceCard({
  stop,
  total,
  here,
  atHold,
  onGo,
}: {
  stop: RailStop & { n: number };
  total: number;
  here: boolean;
  atHold: boolean;
  onGo: () => void;
}) {
  const id = stop.id as AreaId;
  const line = isAreaId(stop.id) ? (areaSummary(id).lines[0] ?? "") : "";
  const open = here && atHold;
  return (
    <section aria-label={`${stop.label}, ${stop.section}`} className="sect-map-card sect-panel sect-plate">
      <p className="text-[0.62rem] uppercase tracking-[0.28em] text-[var(--sect-paper-soft)]">
        Stop {String(stop.n).padStart(2, "0")} <span className="opacity-60">/ {String(total).padStart(2, "0")}</span>
        {here && <span className="ml-2 text-[var(--sect-gold)]">· {atHold ? "You are here" : "You are near"}</span>}
      </p>
      <div className="mt-3 flex items-center gap-3.5">
        <span className="sect-map-card-seal" data-here={here || undefined}>
          <Emblem id={id} className="h-[78%] w-[78%]" />
        </span>
        <p lang="zh" className="sect-zh text-[2.1rem] leading-none tracking-[0.18em] text-[var(--sect-paper)]">
          {stop.zh}
        </p>
      </div>
      <p className="mt-3.5 font-serif text-[1.3rem] leading-tight text-[var(--sect-paper)]">{stop.label}</p>
      <p className="mt-1.5 text-[0.66rem] uppercase tracking-[0.26em] text-[var(--sect-gold)]">{stop.section}</p>
      {line && <p className="mt-3 text-[0.84rem] leading-relaxed text-[var(--sect-paper-soft)]">{line}</p>}
      <button
        type="button"
        onClick={onGo}
        aria-label={open ? `Open ${stop.label}` : `Travel to ${stop.label}`}
        className="sect-map-go sect-ctl mt-4 flex min-h-10 w-full items-center justify-center gap-2 rounded-[2px] px-3 text-[0.72rem] uppercase tracking-[0.22em]"
      >
        {open ? "Open" : "Travel here"}
        <span aria-hidden>→</span>
      </button>
    </section>
  );
}

/** Every place and item along the flight, grouped by stop (what the Places list held). */
const PlacesIndex = memo(function PlacesIndex({
  groups,
  active,
  onItem,
  onSelect,
}: {
  groups: readonly PlaceGroup[];
  active: string | null;
  onItem: (id: string | null) => void;
  onSelect: (id: string) => void;
}) {
  return (
    <nav aria-label="Every place" className="sect-map-aside sect-panel sect-scroll">
      {groups.map((g, i) => (
        <section key={g.id} aria-labelledby={`sect-places-${g.id}`} className="py-1.5">
          <h3
            id={`sect-places-${g.id}`}
            className="flex flex-wrap items-center gap-x-2 px-2 text-[0.62rem] uppercase tracking-[0.26em] text-[var(--sect-gold)]"
          >
            <span className="text-[var(--sect-paper-soft)]">{String(i + 1).padStart(2, "0")}</span>
            {isAreaId(g.id) && <Emblem id={g.id} className="h-[1.15rem] w-[1.15rem]" />}
            {g.section}
            {g.id === active && <span className="normal-case tracking-[0.08em] text-[var(--sect-paper-soft)]">· you are here</span>}
          </h3>
          <ul className="mt-1">
            {g.items.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  className="w-full rounded-[2px] px-2 py-1.5 text-left text-[0.86rem] leading-snug text-[var(--sect-paper-soft)] hover:bg-[var(--sect-gold-soft)] hover:text-[var(--sect-paper)] focus-visible:bg-[var(--sect-gold-soft)] focus-visible:text-[var(--sect-paper)] pointer-coarse:min-h-11"
                  onMouseEnter={() => onItem(p.id)}
                  onMouseLeave={() => onItem(null)}
                  onFocus={() => onItem(p.id)}
                  onBlur={() => onItem(null)}
                  onClick={() => onSelect(p.id)}
                >
                  {p.label}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </nav>
  );
});

/** The element has keyboard focus (a click or a tap does not count). */
function focusVisible(el: HTMLElement): boolean {
  try {
    return el.matches(":focus-visible");
  } catch {
    return true;
  }
}
