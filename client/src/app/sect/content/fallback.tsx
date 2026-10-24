"use client";

/**
 * Every area's content as one themed, scrollable page, with a top navigation of the 11 areas. Shown
 * when WebGL is unavailable, as /?view=page, and as the "Read as page" mode over the flight.
 * Dressed as the reader is: rice paper, brush-stroke dividers, the places' names in the brush hand.
 */
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { AREAS, isAreaId, type AreaId } from "@/lib/sect/areas";
import { PORTFOLIO } from "@/lib/portfolio-data";
import {
  SECTION_NAMES,
  itemDomId,
  pageSectionDomId,
  parseContentHash,
  sectionDomId,
  type ContentTarget,
} from "@/lib/sect/content";
import { BrushName, SealedName, SealStamp } from "../ornaments";
import { flightFocusFallback, focusIsKept, reducedMotion, trapTab, useModalLifecycle } from "./modal";
import { AreaBody } from "./sections";

export interface ContentFallbackProps {
  /** Start a voice call with the portfolio's AI, when the page supports it. */
  onTalk?: () => void;
  /**
   * Leave the page view and return to the flight. When set, the page acts as a modal over the
   * scene (focus kept inside, Escape leaves); without it, it is the page itself (no WebGL).
   */
  onExit?: () => void;
  /** Open at an area or item. Without it, the URL hash is used ("#projects", "#project/dispatchai"). */
  initial?: ContentTarget | null;
  /** Hovering or focusing an item (only meaningful while a scene is behind the page). */
  onHighlight?: (hotspotId: string | null) => void;
  /**
   * Without onExit (the page on its own): one line at the top saying why there is no flight.
   * Defaults to the no-WebGL explanation; null shows nothing.
   */
  note?: ReactNode;
}

const NO_WEBGL_NOTE = "This browser can't show the 3D flight.";

export function ContentFallback({ onTalk, onExit, initial, onHighlight, note }: ContentFallbackProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const navRef = useRef<HTMLOListElement>(null);
  const [target, setTarget] = useState<ContentTarget | null>(initial ?? null);
  const [jump, setJump] = useState(0);
  /** The area being read: follows the scroll position, and jumps with the navigation. */
  const [current, setCurrent] = useState<AreaId | null>(initial?.area ?? null);
  const nestedBack = useRef<(() => void) | null>(null);
  const onNestedChange = useCallback((back: (() => void) | null) => {
    nestedBack.current = back;
  }, []);

  useModalLifecycle(rootRef, !!onExit, flightFocusFallback);

  // Deep links: the main page's "#project/<id>" and section anchors.
  useEffect(() => {
    if (initial) return;
    const t = parseContentHash(window.location.hash);
    if (t) {
      setTarget(t);
      setCurrent(t.area);
      setJump((n) => n + 1);
    } else if (onExit && !focusIsKept()) {
      titleRef.current?.focus({ preventScroll: true });
    }
    // Mount only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // A new `initial` from the page (opened again at another area) moves there.
  const initialKey = initial ? `${initial.area}|${initial.item ?? ""}|${initial.filter ?? ""}` : "";
  const initialRef = useRef(initial);
  initialRef.current = initial;
  useEffect(() => {
    const t = initialRef.current;
    if (!t) return;
    setTarget({ ...t });
    setCurrent(t.area);
    setJump((n) => n + 1);
  }, [initialKey]);

  // Bring the target into view and move focus to it (not out of the orb's chat box: the agent
  // moves this page while it answers).
  useEffect(() => {
    if (!target || jump === 0) return;
    const el =
      (target.item && document.getElementById(itemDomId(target.item))) ||
      document.getElementById(`sc-page-title-${target.area}`);
    if (!el) return;
    el.scrollIntoView({ block: "start", behavior: reducedMotion() ? "auto" : "smooth" });
    if (!focusIsKept()) el.focus({ preventScroll: true });
  }, [target, jump]);

  // The area menu marks the section being read: the one crossing a line a third of the way down,
  // the first at the very top, the last at the very bottom.
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const sections = Array.from(root.querySelectorAll<HTMLElement>(".sc-page-section[data-area]"));
    const pick = (el: Element) => {
      const id = (el as HTMLElement).dataset.area;
      if (id && isAreaId(id)) setCurrent(id);
    };
    let io: IntersectionObserver | null = null;
    if (typeof IntersectionObserver !== "undefined") {
      io = new IntersectionObserver(
        (entries) => {
          for (const e of entries) if (e.isIntersecting) pick(e.target);
        },
        { root, rootMargin: "-33% 0px -62% 0px" },
      );
      for (const el of sections) io.observe(el);
    }
    const onScroll = () => {
      const last = sections[sections.length - 1];
      if (last && root.scrollTop + root.clientHeight >= root.scrollHeight - 4) pick(last);
      else if (sections[0] && root.scrollTop < 8) pick(sections[0]);
    };
    root.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      io?.disconnect();
      root.removeEventListener("scroll", onScroll);
    };
  }, []);

  // On narrow screens the menu scrolls sideways: keep the current area in view.
  useEffect(() => {
    const ol = navRef.current;
    if (!ol || !current || ol.scrollWidth <= ol.clientWidth + 1) return;
    const li = ol.querySelector<HTMLElement>(`[data-area="${current}"]`);
    if (!li) return;
    const left = li.offsetLeft - (ol.clientWidth - li.offsetWidth) / 2;
    ol.scrollTo({ left: Math.max(0, left), behavior: reducedMotion() ? "auto" : "smooth" });
  }, [current]);

  const navigate = useCallback((t: ContentTarget) => {
    setTarget({ ...t });
    setCurrent(t.area);
    setJump((n) => n + 1);
  }, []);

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      if (nestedBack.current) {
        e.preventDefault();
        nestedBack.current();
      } else if (onExit) {
        e.preventDefault();
        onExit();
      }
      return;
    }
    if (onExit) trapTab(e, rootRef.current);
  };

  // Inside the dialog (over the flight) these are plain blocks: a <header> would be a second page
  // banner and a <main> a second main, beside the flight's own.
  const Main = onExit ? "div" : "main";
  const Top = onExit ? "div" : "header";

  return (
    <div
      ref={rootRef}
      className="sc-theme sc-page"
      role={onExit ? "dialog" : undefined}
      aria-modal={onExit ? true : undefined}
      aria-labelledby={onExit ? "sc-page-title" : undefined}
      tabIndex={-1}
      onKeyDown={onKeyDown}
    >
      <Top className="sc-page-top">
        <div className="sc-page-brand">
          <BrushName text="日月神教" even={0.12} className="sc-page-seal" />
          <SealStamp />
          <span className="sc-page-brandname">Sun Moon Divine Sect</span>
          {onExit && (
            <button type="button" className="sc-btn sc-btn-gold sc-page-exit" onClick={onExit}>
              Back to the flight
            </button>
          )}
        </div>
        <nav aria-label="Areas" className="sc-page-nav">
          <ol ref={navRef}>
            {AREAS.map((a, i) => (
              <li key={a.id} data-area={a.id}>
                <a
                  href={`#${sectionDomId(a.id)}`}
                  aria-current={current === a.id ? "location" : undefined}
                  onClick={(e) => {
                    e.preventDefault();
                    navigate({ area: a.id, item: null });
                  }}
                >
                  <span className="sc-nav-no" aria-hidden>
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="sc-nav-section">{SECTION_NAMES[a.id]}</span>
                </a>
              </li>
            ))}
          </ol>
        </nav>
      </Top>

      <Main className="sc-page-main">
        <div className="sc-page-hero">
          {!onExit && note !== null && <p className="sc-note sc-page-note">{note ?? NO_WEBGL_NOTE}</p>}
          <h1 id="sc-page-title" ref={titleRef} tabIndex={-1} className="sc-h1">
            {PORTFOLIO.name}
          </h1>
        </div>
        {AREAS.map((a) => (
          <section
            key={a.id}
            id={pageSectionDomId(a.id)}
            data-area={a.id}
            aria-labelledby={`sc-page-title-${a.id}`}
            className="sc-page-section"
          >
            <header className="sc-page-section-head">
              <p className="sc-place">
                <span>{a.label}</span> <SealedName text={a.zh} />
              </p>
              <h2 id={`sc-page-title-${a.id}`} tabIndex={-1} className="sc-h2">
                {SECTION_NAMES[a.id]}
              </h2>
            </header>
            <AreaBody
              area={a.id}
              item={target?.area === a.id ? target.item : null}
              filter={target?.area === a.id ? target.filter : undefined}
              version={target?.area === a.id ? jump : 0}
              mode="page"
              onNavigate={navigate}
              onHighlight={onHighlight}
              onTalk={onTalk}
              onNestedChange={onNestedChange}
            />
          </section>
        ))}
        {onExit && (
          <p className="sc-page-end">
            <button type="button" className="sc-textbtn" onClick={onExit}>
              Back to the flight
            </button>
          </p>
        )}
      </Main>
    </div>
  );
}
