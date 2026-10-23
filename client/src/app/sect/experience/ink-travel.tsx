"use client";

/**
 * Fast travel's ink (lib/sect/travel.ts), as in Black Myth: Wukong. Ink blooms from the seal the
 * visitor picked on the map until it covers the screen; the place's name shows on it while the
 * camera jumps there underneath (its area streams in meanwhile, and a turning seal says so when that
 * takes a while, as the Gathering status does on the flight); then the ink clears from the middle of
 * the screen. With reduced motion a plain quick fade stands in for the ink.
 *
 * Drawn on one 2D canvas at half the screen's resolution (soft edges suit ink, and it is cheap), and
 * only while a travel is under way: nothing of it exists otherwise. While it is up it takes the
 * wheel, touches and the flight's keys, so nothing moves the camera from under it.
 */
import { useEffect, useRef, useState } from "react";
import { areaInfo, type AreaId } from "@/lib/sect/areas";
import { SECTION_NAMES } from "@/lib/sect/content";
import { BLOT_HALO, blotOutline, easeInOutCubic, dropGrowth, inkDrops, seededRandom, seedOf, travelTiming, type InkDrop } from "@/lib/sect/travel";
import { Emblem } from "./map-emblems";

export interface TravelRequest {
  /** New for every travel. */
  key: number;
  area: AreaId;
  /** Where the ink starts (the seal), in screen pixels. */
  at: readonly [number, number];
}

const INK = "rgb(15, 12, 20)";
/** Keys that would move the camera or close something while the ink is up. */
const HELD_KEYS = new Set([" ", "Spacebar", "Escape", "PageUp", "PageDown", "Home", "End", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "j", "J", "k", "K", "m", "M"]);

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
  gathering,
  arrive,
  onDone,
}: {
  request: TravelRequest;
  reducedMotion: boolean;
  /** The place is still streaming in (the jump is gathering it). */
  gathering: boolean;
  /** The screen is covered: move the camera there. Resolves once the place is drawn. */
  arrive: () => Promise<void>;
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
      const slowTimer = window.setTimeout(() => !cancelled && setSlow(true), 900);
      // The camera jumps underneath; the place streams in if it must, and is drawn.
      await Promise.race([arriveRef.current().catch(() => {}), wait(timing.giveUp)]);
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
  const waiting = slow && gathering;
  return (
    <div ref={rootRef} className="sect-travel" data-phase={phase}>
      <canvas ref={canvasRef} aria-hidden className="absolute inset-0 h-full w-full" />
      <div aria-hidden className="sect-travel-card">
        <Emblem id={request.area} className="mb-5 h-12 w-12 text-[var(--sect-gold)] opacity-90" />
        <p lang="zh" className="sect-zh sect-text-shadow pl-[0.3em] text-[clamp(2.4rem,9vw,4.6rem)] leading-none tracking-[0.3em] text-[var(--sect-paper)]">
          {info.zh}
        </p>
        <span className="mt-5 block h-px w-16 bg-[var(--sect-gold)] opacity-70" />
        <p className="mt-4 text-[0.75rem] uppercase tracking-[0.34em] text-[var(--sect-gold)]">{info.label}</p>
        <p className="mt-1.5 text-[0.8125rem] text-[var(--sect-paper-soft)]">{SECTION_NAMES[request.area]}</p>
        <span className={`mt-6 flex items-center gap-3 transition-opacity duration-300 ${waiting ? "opacity-100" : "opacity-0"}`}>
          <span className="sect-gather block h-3 w-3 rotate-45 border border-[var(--sect-gold)]" />
          <span className="text-[0.68rem] uppercase tracking-[0.26em] text-[var(--sect-paper-soft)]">Loading</span>
        </span>
      </div>
      <p className="sr-only" role="status" aria-live="polite">
        {waiting ? `Loading ${info.label}` : ""}
      </p>
    </div>
  );
}
