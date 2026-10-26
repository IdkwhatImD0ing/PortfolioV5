"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";
import { PORTFOLIO } from "@/lib/portfolio-data";
import { pageViewHref } from "@/lib/sect/content-start";
import { POSTER, posterBox } from "@/lib/sect/opening";
import { BrushName, SealStamp } from "./ornaments";
import { QualityPicker, QualityPickerSpace, type QualityPickerProps } from "./quality-picker";

/** After this long without the scene, the page-view offer is promoted ("Slow connection?"). */
const SLOW_MS = 4000;

/**
 * The sect's sun-and-moon emblem (日月, the first two characters of its name), the same design as the
 * scene's banners and gate (blender/xianxia-sect/sect/lib/props.py SM_MOON / SM_SUN, y flipped for
 * SVG): a moon-white crescent with its horns up cradling a gold sun with twelve short rays, in a thin
 * gold ring. Unit radius 1.
 */
const SUN_RAYS = (() => {
  const [cx, cy, rs, rt, n] = [0, -0.14, 0.34, 0.56, 12];
  const pitch = (2 * Math.PI) / n;
  const half = 0.25 * pitch;
  const pts: string[] = [];
  const at = (r: number, a: number) => `${(cx + r * Math.cos(a)).toFixed(3)},${(cy - r * Math.sin(a)).toFixed(3)}`;
  for (let j = 0; j < n; j++) {
    const t = Math.PI / 2 + j * pitch;
    pts.push(at(rt, t));
    for (let q = 0; q <= 2; q++) pts.push(at(rs, t + half + ((pitch - 2 * half) * q) / 2));
  }
  return pts.join(" ");
})();

function SunMoonEmblem({ className }: { className?: string }) {
  return (
    <svg viewBox="-1.12 -1.12 2.24 2.24" className={className} aria-hidden focusable="false">
      <circle r={1.04} fill="none" stroke="var(--sect-gold)" strokeWidth={0.07} opacity={0.85} />
      <path d="M0.731 -0.352 A0.86 0.86 0 1 1 -0.731 -0.352 A0.74 0.74 0 1 0 0.731 -0.352 Z" fill="var(--sect-paper)" />
      <polygon points={SUN_RAYS} fill="var(--sect-gold)" />
    </svg>
  );
}

/**
 * Full-screen loading veil for /sect. No three.js here: it also shows while the 3D chunk downloads,
 * and the server renders it. Only the short phase label is a live region (screen readers announce
 * "Loading the sect", then "Ready"); the percentage is reported by the progress bar's value, not
 * announced on every byte.
 *
 * Whose portfolio this is and a way to read it without the flight show from the first paint: before
 * the page's scripts run, "Read as page" is a plain link to /?view=page (which never
 * downloads the scene); once the flight has loaded its code, it opens the page view in place.
 *
 * The graphics picker (quality-picker.tsx) sits under the progress bar once the flight's code is
 * here ("reserve" keeps its place empty until then), and above the buttons when the scene failed:
 * a phone that picked High and lost its graphics context gets back with Low and Reload.
 *
 * Under the picker, "Turn on sound" (experience/sound-toggle.tsx
 * SoundPrompt): the music starts muted, and browsers allow sound only after a press, so the screen
 * the visitor waits on offers it. Its place is kept too ("reserve"), and stays empty without music.
 *
 * Once the scene is ready the screen stays up (`onEnter`): the bar reads Ready, and "Enter"
 * takes the gold beside "Read as page", in the place the page-view offer had, so nothing moves. The
 * graphics and sound are set first, top to bottom, then Enter. It takes the focus when nothing else
 * has it, so Enter or Space starts the flight.
 *
 * The flight's veil can show the poster still of the opening view behind it (Poster), while <html>
 * has POSTER_ATTR; the veil's fade when the scene is ready is then a crossfade to the same view.
 *
 * Without JavaScript the screen is not shown at all: the page shows the portfolio as text instead
 * (app/page.tsx, summary.tsx).
 *
 * Dressed as a Wukong loading screen: 日月神教 in the brush hand on a pool of ink wash with the sect's
 * seal (four characters, set smaller than the two of 明教 were), and the progress drawn as a brush
 * stroke filling with gold (ornaments.tsx, sect.css).
 */
export function LoadingScreen({
  progress,
  label,
  phaseLabel = "Loading the sect",
  error,
  visible = true,
  onReload,
  onReadAsPage,
  onEnter,
  quality,
  sound,
  poster = false,
}: {
  progress: number;
  label: string;
  phaseLabel?: string;
  error?: string | null;
  visible?: boolean;
  /** Shows a Reload button with the error (the graphics context was lost). */
  onReload?: () => void;
  /** Opens the one-page view in place; without it the offer links to /?view=page. */
  onReadAsPage?: () => void;
  /** The scene is ready: "Enter" shows, and starts the flight. */
  onEnter?: () => void;
  /** The graphics picker, or "reserve" for its empty place (it is coming); none without either. */
  quality?: QualityPickerProps | "reserve";
  /** The sound prompt, or "reserve" for its empty place; none without either. */
  sound?: ReactNode | "reserve";
  /** The flight's veil: the poster still shows behind it while <html> has POSTER_ATTR. */
  poster?: boolean;
}) {
  const pct = Math.round(Math.min(Math.max(progress, 0), 1) * 100);
  const [slow, setSlow] = useState(false);
  const [pageHref, setPageHref] = useState(() => pageViewHref());
  useEffect(() => {
    setPageHref(pageViewHref(window.location.search, window.location.hash));
  }, []);
  const ready = onEnter !== undefined;
  useEffect(() => {
    if (!visible || error || ready) return;
    const t = window.setTimeout(() => setSlow(true), SLOW_MS);
    return () => clearTimeout(t);
  }, [visible, error, ready]);

  const quiet =
    "border-b border-[var(--sect-gold-soft)] text-[var(--sect-gold)] hover:border-[var(--sect-gold)] focus-visible:border-[var(--sect-gold)]";
  const gold =
    "inline-flex min-h-11 items-center gap-2 rounded-[2px] border border-[var(--sect-gold)] bg-[var(--sect-gold)] px-5 text-[0.9375rem] font-semibold text-[#1a1306] hover:bg-[#f3d89a]";
  const plain =
    "inline-flex min-h-11 items-center gap-2 rounded-[2px] border border-[var(--sect-gold-soft)] bg-[rgba(14,12,20,0.55)] px-5 text-[0.9375rem] text-[var(--sect-paper)] hover:border-[var(--sect-gold)]";
  // Ready: Enter has the gold, the pair one width. Before that the offer takes it once loading is slow.
  const pair = "min-w-[8.75rem] justify-center";
  const offerClass = ready ? `${plain} ${pair}` : slow ? gold : plain;
  const offerText = "Read as page";
  const offer = onReadAsPage ? (
    <button type="button" onClick={onReadAsPage} className={offerClass}>
      {offerText}
    </button>
  ) : (
    <a href={pageHref} className={offerClass}>
      {offerText}
    </a>
  );
  const picker = quality === "reserve" ? <QualityPickerSpace /> : quality ? <QualityPicker {...quality} layout="row" /> : null;

  return (
    // Short screens (a phone on its side) tighten the spacing; a column still taller than the screen
    // starts at the top and scrolls (plain centring would push the title out of reach above it). The
    // first and last items' auto margins centre it too, where `safe` is unknown (Safari before 17.6).
    <div
      className="sect-veil fixed inset-0 z-50 flex flex-col items-center justify-center-safe overflow-y-auto px-6 py-10 text-center transition-opacity duration-700 [@media(max-height:30rem)]:py-5"
      style={{ opacity: visible ? 1 : 0, pointerEvents: visible ? "auto" : "none" }}
      aria-busy={!error && visible && !ready}
    >
      {poster && <Poster />}
      {/* The emblem sits above the name; short screens (a phone on its side) drop it so the column still fits. */}
      <SunMoonEmblem className="mt-auto mb-5 h-[clamp(2.75rem,7vw,3.75rem)] w-[clamp(2.75rem,7vw,3.75rem)] shrink-0 [@media(max-height:30rem)]:hidden" />
      <p className="sect-sealed sect-ink text-[clamp(3rem,9vw,5.4rem)] leading-none text-[var(--sect-paper)] [@media(max-height:30rem)]:mt-auto [@media(max-height:30rem)]:text-[2.7rem]">
        <BrushName text="日月神教" even={0.1} />
        <SealStamp />
      </p>
      <p className="mt-4 text-[0.75rem] uppercase tracking-[0.42em] text-[var(--sect-gold)]">Sun Moon Divine Sect</p>
      <p className="mt-5 max-w-md text-[0.9375rem] leading-relaxed text-[var(--sect-paper-soft)]">
        <span className="font-serif text-[1.35rem] text-[var(--sect-paper)]">{PORTFOLIO.name}</span>
        <br />
        {PORTFOLIO.tagline}
      </p>
      {error ? (
        <div className="mb-auto mt-10 flex w-[min(28rem,calc(100vw-3rem))] flex-col items-center text-sm leading-relaxed text-[var(--sect-paper-soft)]">
          <p role="alert">{error}</p>
          {quality && quality !== "reserve" && <div className="w-[min(22rem,80vw)]">{picker}</div>}
          <div className="mt-4 flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
            {onReload && (
              <button type="button" onClick={onReload} className={quiet}>
                Reload
              </button>
            )}
            {onReadAsPage ? (
              <button type="button" onClick={onReadAsPage} className={quiet}>
                Read as page
              </button>
            ) : (
              <a href={pageHref} className={quiet}>
                Read as page
              </a>
            )}
          </div>
        </div>
      ) : (
        <div className="mb-auto mt-10 flex w-[min(22rem,80vw)] flex-col items-center">
          <p className="sr-only" role="status" aria-live="polite">
            {phaseLabel}
          </p>
          <div className="sect-brushbar w-full" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label="Loading progress">
            <div className="sect-brushbar-fill transition-[width] duration-300" style={{ width: `${pct}%` }} />
          </div>
          <div aria-hidden className="mt-3 flex w-full justify-between font-mono text-[0.68rem] tracking-[0.18em] text-[var(--sect-paper-soft)]">
            <span>{label}</span>
            <span>{pct}%</span>
          </div>
          {picker}
          {sound !== undefined && (
            <div data-sect-sound-place className="mt-1 flex h-12 w-full items-center justify-center [@media(max-height:30rem)]:mt-0">
              {sound === "reserve" ? null : sound}
            </div>
          )}
          <div className="mt-3 flex flex-col items-center gap-2">
            {/* Its line is always kept (hidden until slow), so the centred column and the picker above
                don't jump up 15 px under a finger when it shows. */}
            <p className={`text-[0.875rem] text-[var(--sect-paper)] ${slow && !ready ? "" : "invisible"}`}>Slow connection?</p>
            {ready ? (
              <div className="flex flex-wrap items-center justify-center gap-3">
                <EnterButton onEnter={onEnter} className={`sect-fade-in ${gold} ${pair}`} />
                {offer}
              </div>
            ) : (
              offer
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * "Enter". It takes the focus when it comes, unless the visitor has put it somewhere (the
 * picker, the sound prompt), so the keyboard's Enter starts the flight.
 */
function EnterButton({ onEnter, className }: { onEnter: () => void; className: string }) {
  const ref = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const a = document.activeElement;
    if (!a || a === document.body) ref.current?.focus({ preventScroll: true });
  }, []);
  return (
    <button ref={ref} type="button" data-sect-enter onClick={onEnter} className={className}>
      Enter
    </button>
  );
}

/**
 * The poster still behind the veil's text (lib/sect/opening.ts POSTER): one image per orientation,
 * sized as the canvas will draw the same view, under an ink scrim that keeps the text legible. Shown
 * only while <html> has data-sect-poster (content-start.ts POSTER_ATTR, spelled out in the class for
 * Tailwind), which is set before the first paint for the default start. The images load lazily, so
 * a hidden poster (a deep link) fetches nothing; the script that sets the attribute preloads the
 * one the screen needs.
 */
function Poster() {
  const land = posterBox("landscape");
  const port = posterBox("portrait");
  const img = "absolute left-1/2 top-1/2 h-full w-full max-w-none -translate-x-1/2 -translate-y-1/2 object-cover";
  return (
    <div aria-hidden className="sect-poster pointer-events-none fixed inset-0 -z-10 hidden overflow-hidden [container-type:size] [[data-sect-poster]_&]:block">
      {/* A still behind the loading text, art-directed by orientation and sized from the camera's
          field of view: next/image cannot size it that way. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={POSTER.landscape} alt="" loading="lazy" decoding="async" className={`${img} portrait:hidden`} style={land} />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={POSTER.portrait} alt="" loading="lazy" decoding="async" className={`${img} landscape:hidden`} style={port} />
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 62% 58% at 50% 50%, rgba(14, 12, 20, 0.74) 0%, rgba(14, 12, 20, 0.56) 55%, rgba(14, 12, 20, 0.34) 100%)",
        }}
      />
    </div>
  );
}
