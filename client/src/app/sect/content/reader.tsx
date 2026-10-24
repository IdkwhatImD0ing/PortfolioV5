"use client";

/**
 * The reader: a large themed sheet over the scene with the complete content of one area, on faint
 * rice paper inside cloud corners, the place's name in the brush hand with the sect's seal.
 */
import { useCallback, useEffect, useRef } from "react";
import { PORTFOLIO } from "@/lib/portfolio-data";
import { areaInfo } from "@/lib/sect/areas";
import { SECTION_NAMES, areaSummary, itemDomId, neighborAreas, type ContentTarget } from "@/lib/sect/content";
import { SealedName } from "../ornaments";
import { flightFocusFallback, focusIsKept, trapTab, useModalLifecycle } from "./modal";
import { AreaBody } from "./sections";

export interface AreaReaderProps {
  /** What to show; null renders nothing. */
  target: ContentTarget | null;
  onClose: () => void;
  /** Fly the camera to another area (and optionally open an item there). */
  onNavigate: (target: ContentTarget) => void;
  /** Hovering or focusing an item highlights its object in the scene (null clears). */
  onHighlight?: (hotspotId: string | null) => void;
  /** Start a voice call with the portfolio's AI, when the page supports it. */
  onTalk?: () => void;
  /** Switch to the one-page view (ContentFallback); shows a "Read as page" button when set. */
  onReadAsPage?: () => void;
  /**
   * The item the reader shows changed inside it (a project detail opened from the list, or closed
   * back to it): "project:<id>" or null. For keeping the URL in step; not called on open.
   */
  onItemChange?: (item: string | null) => void;
}

/** The full content of one section (every item, link, image and download the main page has). */
export function AreaReader(props: AreaReaderProps) {
  if (!props.target) return null;
  return <ReaderSheet {...props} target={props.target} />;
}

function ReaderSheet({
  target,
  onClose,
  onNavigate,
  onHighlight,
  onTalk,
  onReadAsPage,
  onItemChange,
}: AreaReaderProps & { target: ContentTarget }) {
  const sheetRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const nestedBack = useRef<(() => void) | null>(null);
  const onNestedChange = useCallback((back: (() => void) | null) => {
    nestedBack.current = back;
  }, []);

  useModalLifecycle(sheetRef, true, flightFocusFallback);

  // Clear any scene highlight when the reader goes away.
  const highlightRef = useRef(onHighlight);
  highlightRef.current = onHighlight;
  useEffect(() => () => highlightRef.current?.(null), []);

  // Focus the item the target names (scrolled into view), or the sheet's title. Not when the
  // visitor is typing to the orb: the agent opens readers mid-reply, and the caret stays put.
  useEffect(() => {
    const body = bodyRef.current;
    const keep = focusIsKept();
    if (target.item) {
      const el = document.getElementById(itemDomId(target.item));
      if (el && body?.contains(el)) {
        // An item's own view opens from its top (its back button sits above the title).
        if (el.hasAttribute("data-sc-top")) body.scrollTop = 0;
        else el.scrollIntoView({ block: "start" });
        if (!keep) el.focus({ preventScroll: true });
        return;
      }
    }
    if (body) body.scrollTop = 0;
    if (!keep) titleRef.current?.focus({ preventScroll: true });
  }, [target.area, target.item, target.filter]);

  const info = areaInfo(target.area);
  const summary = areaSummary(target.area);

  // The tab names the open section while the reader is up.
  useEffect(() => {
    const prev = document.title;
    document.title = `${summary.section} · ${PORTFOLIO.name} · Sun Moon Divine Sect`;
    return () => {
      document.title = prev;
    };
  }, [summary.section]);
  const { prev, next } = neighborAreas(target.area);
  const titleId = `sc-reader-title-${target.area}`;

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      if (nestedBack.current) nestedBack.current();
      else onClose();
      return;
    }
    trapTab(e, sheetRef.current);
  };

  return (
    <div
      className="sc-theme sc-scrim"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={sheetRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={onKeyDown}
        className="sect-panel sect-panel-lg sc-sheet"
      >
        {/* A div, not <header>: inside a dialog a header would count as a second page banner. */}
        <div className="sc-sheet-head">
          <div className="sc-sheet-titles">
            <p className="sc-place">
              <span>{info.label}</span> <SealedName text={info.zh} />
            </p>
            <h2 id={titleId} ref={titleRef} tabIndex={-1} className="sc-h2">
              {summary.section}
            </h2>
          </div>
          {onReadAsPage && (
            <button type="button" className="sc-btn sc-btn-quiet sc-hide-xs" onClick={onReadAsPage}>
              Read as page
            </button>
          )}
          <button type="button" onClick={onClose} aria-label={`Close ${info.label}`} className="sc-close">
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden>
              <path d="M2 2l12 12M14 2L2 14" stroke="currentColor" strokeWidth="1.4" />
            </svg>
          </button>
        </div>

        {/* Focusable so a keyboard can scroll it: some sections (About, Education, Skills) have no
            link or button inside to land on. */}
        <div ref={bodyRef} className="sc-sheet-body" tabIndex={0} role="region" aria-labelledby={titleId}>
          <AreaBody
            area={target.area}
            item={target.item}
            filter={target.filter}
            mode="reader"
            onNavigate={onNavigate}
            onHighlight={onHighlight}
            onTalk={onTalk}
            onNestedChange={onNestedChange}
            onItemChange={onItemChange}
          />
          {onReadAsPage && (
            <p className="sc-note sc-show-xs">
              <button type="button" className="sc-textbtn" onClick={onReadAsPage}>
                Read as page
              </button>
            </p>
          )}
        </div>

        <nav aria-label="Other areas" className="sc-sheet-foot">
          {prev ? (
            <button type="button" className="sc-navbtn" onClick={() => onNavigate({ area: prev, item: null })}>
              <span aria-hidden className="sc-navarrow">
                ←
              </span>
              <span className="sc-navtext">
                <span className="sc-navsection">{SECTION_NAMES[prev]}</span>
              </span>
            </button>
          ) : (
            <span />
          )}
          {next ? (
            <button type="button" className="sc-navbtn sc-navbtn-next" onClick={() => onNavigate({ area: next, item: null })}>
              <span className="sc-navtext">
                <span className="sc-navsection">{SECTION_NAMES[next]}</span>
              </span>
              <span aria-hidden className="sc-navarrow">
                →
              </span>
            </button>
          ) : (
            <span />
          )}
        </nav>
      </div>
    </div>
  );
}
