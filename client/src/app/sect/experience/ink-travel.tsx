"use client";

/**
 * Fast travel's ink (lib/sect/travel.ts), as in Black Myth: Wukong. Ink blooms from the seal the
 * visitor picked on the map (or the control that asked for a far jump) until it covers the screen;
 * the place's name shows on it while the camera jumps there underneath and the place is drawn until
 * it has settled (lib/sect/settle.ts: its areas streamed in and on the GPU, grass grown, reflections
 * captured). When that takes longer than the ink's own hold, a turning seal says Loading over a thin
 * line that fills as the pieces come. Then the ink clears from the middle of the screen onto the
 * finished place. With reduced motion a plain fade stands in for the ink (the same wait).
 *
 * The card is a loading screen of Wukong's kind: the place's name in the brush hand, settling out of
 * a blur as ink into paper (sect.css), the sect's seal pressed after it, a brush stroke under it,
 * and while it waits an ink ring and a brush-stroke line (ornaments.tsx).
 *
 * Drawn on one 2D canvas at half the screen's resolution (soft edges suit ink, and it is cheap), and
 * only while a travel is under way: nothing of it exists otherwise. While it is up it takes the
 * wheel, touches and the flight's keys, so nothing moves the camera from under it.
 */
import { useEffect, useRef, useState } from "react";
import { areaInfo, type AreaId } from "@/lib/sect/areas";
import { SECTION_NAMES } from "@/lib/sect/content";
import { BLOT_HALO, blotOutline, easeInOutCubic, dropGrowth, inkDrops, seededRandom, seedOf, travelTiming, type InkDrop } from "@/lib/sect/travel";
import { BrushName, InkRing, SealStamp } from "../ornaments";
import { Emblem } from "./map-emblems";

export interface TravelRequest {
  /** New for every travel. */
  key: number;
  area: AreaId;
  /** Where the ink starts (the seal, or the control that asked for the jump), in screen pixels. */
  at: readonly [number, number];
  /** Runs once the ink has cleared (a reader to open there, the voice agent's highlight). */
  then?: () => void;
  /** Where on the track it lands (scroll units), when not at the area's hold (Home: the very start). */
  u?: number;
}

const INK = "rgb(15, 12, 20)";
/**
 * Keys that would move the camera or close something while the ink is up, and Enter and Tab: the
 * map still under the ink while it spreads keeps the focus, and a second Enter (or Tab and Enter)
 * there started the ink over, or opened a reader for the place being left.
 */
const HELD_KEYS = new Set([" ", "Spacebar", "Enter", "Tab", "Escape", "PageUp", "PageDown", "Home", "End", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "j", "J", "k", "K", "m", "M"]);

/** One blot: its ragged rim filled with ink, a soft halo just outside it and a few spatters. */
function blotSprite(seed: number, size = 256): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = size;
  c.height = size;
  const g = c.getContext("2d");
  if (!g) return c;
  const rim = blotOutline(seed, 120);
  const half = size / 2;
  // The rim's widest reach is the solid blot; the halo reaches BLOT_HALO times that, the sprite's edge.
  const solid = half / BLOT_HALO;
  const shape = (k: number) => {
    g.beginPath();
    rim.forEach((r, i) => {
      const t = (i / rim.length) * Math.PI * 2;
      const x = half + Math.cos(t) * r * solid * k;
      const y = half + Math.sin(t) * r * solid * k;
      if (i === 0) g.moveTo(x, y);
      else g.lineTo(x, y);
    });
    g.closePath();
    g.fill();
  };
  g.fillStyle = INK;
  // A slight blur where the browser has one (the halo's steps melt into a bleed).
  if ("filter" in g) g.filter = "blur(1.5px)";
  // The halo: thin layers, each a little wider and fainter, then the solid blot.
  const layers = 8;
  for (let i = 0; i < layers; i++) {
    g.globalAlpha = 0.075;
    shape(BLOT_HALO - ((BLOT_HALO - 1) * i) / layers);
  }
  g.globalAlpha = 1;
  shape(1);
  // Spatter round the rim, as ink thrown on paper leaves.
  const rnd = seededRandom(seed ^ 0x9e3779b9);
  g.globalAlpha = 0.85;
  for (let i = 0; i < 16; i++) {
    const t = rnd() * Math.PI * 2;
    const at = rim[Math.floor((t / (Math.PI * 2)) * rim.length) % rim.length] * solid * (1 + rnd() * 0.1);
    g.beginPath();
    g.arc(half + Math.cos(t) * at, half + Math.sin(t) * at, size * (0.006 + rnd() * 0.016), 0, Math.PI * 2);
    g.fill();
  }
  return c;
}

function wait(ms: number): Promise<void> {
  return new Promise((r) => window.setTimeout(r, ms));
}

export function InkTravel({
  request,
  reducedMotion,
  progress,
  arrive,
  onDone,
}: {
  request: TravelRequest;
  reducedMotion: boolean;
  /** How far the place has come toward settled (0..1), for the Loading line. */
  progress: number;
  /**
   * The screen is covered: move the camera there. Resolves once the place has settled; `signal`
   * aborts when the ink gives up waiting (travelTiming giveUp) or goes.
   */
  arrive: (signal: AbortSignal) => Promise<void>;
  /** The ink has cleared. */
  onDone: () => void;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [phase, setPhase] = useState<"cover" | "hold" | "reveal">("cover");
  const [slow, setSlow] = useState(false);
  const arriveRef = useRef(arrive);
  arriveRef.current = arrive;
  const doneRef = useRef(onDone);
  doneRef.current = onDone;

  useEffect(() => {
    const root = rootRef.current;
    const canvas = canvasRef.current;
    if (!root || !canvas) return;
    let cancelled = false;
    let raf = 0;
    const waiting = new AbortController();
    // From the start (a run cut short, as React's development double run does, leaves nothing).
    root.style.opacity = "";
    const timing = travelTiming(reducedMotion);
    const W = window.innerWidth;
    const H = window.innerHeight;
    const k = 0.5 * Math.min(2, Math.max(1, window.devicePixelRatio || 1));
    canvas.width = Math.max(1, Math.round(W * k));
    canvas.height = Math.max(1, Math.round(H * k));
    const ctx = canvas.getContext("2d");
    const seed = seedOf(request.area);
    const sprites = ctx && !reducedMotion ? [0, 1, 2].map((i) => blotSprite(seed + i * 7919)) : [];
    const view = { w: W, h: H };
    const drops = inkDrops(seed, request.at, view, 3, Math.max(1, sprites.length));
    const holes = inkDrops(seed ^ 0x5bd1e995, [W / 2, H * 0.48], view, 2, Math.max(1, sprites.length));

    const draw = (d: InkDrop, g: number) => {
      if (!ctx || sprites.length === 0 || g <= 0) return;
      const r = d.r * g * k;
      ctx.save();
      ctx.translate(d.x * k, d.y * k);
      ctx.rotate(d.turn);
      ctx.drawImage(sprites[d.shape % sprites.length], -r, -r, 2 * r, 2 * r);
      ctx.restore();
    };
    const fillInk = () => {
      if (!ctx) return;
      ctx.globalCompositeOperation = "source-over";
      ctx.fillStyle = INK;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      // A faint warm wash in the middle, like the loading screen's.
      const cx = canvas.width / 2;
      const cy = canvas.height * 0.45;
      const wash = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(canvas.width, canvas.height) * 0.6);
      wash.addColorStop(0, "rgba(233, 199, 126, 0.11)");
      wash.addColorStop(1, "rgba(233, 199, 126, 0)");
      ctx.fillStyle = wash;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    };

    const reveal = () => {
      setSlow(false);
      setPhase("reveal");
      const t0 = performance.now();
      if (sprites.length === 0) {
        // Reduced motion (or no 2D canvas): the ink fades.
        const a = root.animate([{ opacity: 1 }, { opacity: 0 }], { duration: timing.reveal, easing: "ease-out", fill: "forwards" });
        a.onfinish = () => !cancelled && doneRef.current();
        return;
      }
      const step = (now: number) => {
        if (cancelled) return;
        const t = Math.min(1, (now - t0) / timing.reveal);
        fillInk();
        ctx!.globalCompositeOperation = "destination-out";
        for (const d of holes) draw(d, easeInOutCubic((t - d.start * 0.5) / d.span));
        ctx!.globalCompositeOperation = "source-over";
        root.style.opacity = t > 0.6 ? ((1 - t) / 0.4).toFixed(3) : "1";
        if (t < 1) raf = requestAnimationFrame(step);
        else doneRef.current();
      };
      raf = requestAnimationFrame(step);
    };

    const covered = async () => {
      fillInk();
      setPhase("hold");
      const shownAt = performance.now();
      // Loading shows only once the place takes longer than the ink's own hold.
      const slowTimer = window.setTimeout(() => !cancelled && setSlow(true), timing.hold);
      // The camera jumps underneath, and the place is drawn there until it has settled.
      await Promise.race([arriveRef.current(waiting.signal).catch(() => {}), wait(timing.giveUp)]);
      // Given up (or done): whatever still waits lets go.
      waiting.abort();
      window.clearTimeout(slowTimer);
      const left = timing.hold - (performance.now() - shownAt);
      if (left > 0) await wait(left);
      if (!cancelled) reveal();
    };

    if (sprites.length === 0) {
      fillInk();
      const a = root.animate([{ opacity: 0 }, { opacity: 1 }], { duration: timing.cover, easing: "ease-in", fill: "forwards" });
      a.onfinish = () => {
        if (cancelled) return;
        root.getAnimations().forEach((x) => x.cancel());
        root.style.opacity = "1";
        void covered();
      };
    } else {
      const t0 = performance.now();
      const step = (now: number) => {
        if (cancelled) return;
        const t = Math.min(1, (now - t0) / timing.cover);
        ctx!.clearRect(0, 0, canvas.width, canvas.height);
        for (const d of drops) draw(d, dropGrowth(d, t));
        if (t < 1) raf = requestAnimationFrame(step);
        else void covered();
      };
      raf = requestAnimationFrame(step);
    }
    return () => {
      cancelled = true;
      waiting.abort();
      cancelAnimationFrame(raf);
      root.getAnimations().forEach((x) => x.cancel());
    };
  }, [request.key, request.area, request.at, reducedMotion]);

  // Nothing moves the camera from under the ink, and the voice orb's button steps aside (sect.css).
  useEffect(() => {
    const root = rootRef.current;
    const stop = (e: Event) => {
      e.preventDefault();
      e.stopPropagation();
    };
    const key = (e: KeyboardEvent) => {
      if (!HELD_KEYS.has(e.key) || (e.target as HTMLElement | null)?.closest?.(".sect-orb")) return;
      e.preventDefault();
      e.stopImmediatePropagation();
    };
    root?.addEventListener("wheel", stop, { passive: false });
    root?.addEventListener("touchstart", stop, { passive: false });
    root?.addEventListener("touchmove", stop, { passive: false });
    window.addEventListener("keydown", key, { capture: true });
    document.body.dataset.sectTravel = "1";
    return () => {
      root?.removeEventListener("wheel", stop);
      root?.removeEventListener("touchstart", stop);
      root?.removeEventListener("touchmove", stop);
      window.removeEventListener("keydown", key, { capture: true });
      delete document.body.dataset.sectTravel;
    };
  }, []);

  const info = areaInfo(request.area);
  const waiting = slow && phase === "hold";
  const pct = Math.round(Math.min(1, Math.max(0, progress)) * 100);
  return (
    <div ref={rootRef} className="sect-travel" data-phase={phase}>
      <canvas ref={canvasRef} aria-hidden className="absolute inset-0 h-full w-full" />
      <div aria-hidden className="sect-travel-card">
        <Emblem id={request.area} className="mb-5 h-12 w-12 text-[var(--sect-gold)] opacity-90" />
        <p className="sect-sealed sect-text-shadow text-[clamp(2.9rem,10.5vw,5.4rem)] leading-none text-[var(--sect-paper)]">
          <BrushName text={info.zh} />
          <SealStamp />
        </p>
        <span aria-hidden className="sect-brushstroke mt-5" />
        <p className="mt-4 text-[0.75rem] uppercase tracking-[0.34em] text-[var(--sect-gold)]">{info.label}</p>
        <p className="mt-1.5 text-[0.8125rem] text-[var(--sect-paper-soft)]">{SECTION_NAMES[request.area]}</p>
        <span className={`mt-6 flex flex-col items-center transition-opacity duration-300 ${waiting ? "opacity-100" : "opacity-0"}`}>
          <span className="flex items-center gap-3">
            <InkRing className="text-[0.95rem]" />
            <span className="text-[0.68rem] uppercase tracking-[0.26em] text-[var(--sect-paper-soft)]">Loading</span>
          </span>
          {/* A brush-stroke line, as the loading screen's: how far the place has come. */}
          <span className="sect-brushbar mt-3 block w-28">
            <span className="sect-brushbar-fill block origin-left" style={{ transform: `scaleX(${pct / 100})` }} />
          </span>
        </span>
      </div>
      <p className="sr-only" role="status" aria-live="polite">
        {waiting ? `Loading ${info.label}` : ""}
      </p>
      {waiting && (
        <span className="sr-only" role="progressbar" aria-label={`Loading ${info.label}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} />
      )}
    </div>
  );
}
