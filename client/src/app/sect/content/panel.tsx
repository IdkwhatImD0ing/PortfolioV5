"use client";

/** The summary panel shown while the camera holds at an area. */
import { forwardRef } from "react";
import { PORTFOLIO } from "@/lib/portfolio-data";
import type { AreaId } from "@/lib/sect/areas";
import { RESUME_HEAD } from "@/lib/sect/content-copy";
import { areaSummary, type ContentTarget } from "@/lib/sect/content";
import { TalkButton, Zh } from "./ui";

export interface AreaPanelProps {
  area: AreaId;
  /** Open the full reader for this section (or one of its items). */
  onOpen: (target: ContentTarget) => void;
  /** Start a voice call (gate and summit show a talk button; without it they link to the main site). */
  onTalk?: () => void;
  /** Which side of a wide screen the panel sits on; each area has a default. */
  side?: "left" | "right";
}

/**
 * Rendered hidden; the engine fades it in and out through the forwarded ref (style.opacity /
 * style.visibility / style.transform), like the prototype.
 */
export const AreaPanel = forwardRef<HTMLElement, AreaPanelProps>(function AreaPanel({ area, onOpen, onTalk, side }, ref) {
  const s = areaSummary(area);
  const talkFirst = area === "gate" || area === "summit";
  return (
    <section
      ref={ref}
      aria-labelledby={`sect-panel-${area}`}
      className={`sect-panel sc-theme sc-panel ${(side ?? s.side) === "right" ? "sc-panel-right" : "sc-panel-left"}`}
      style={{ opacity: 0, visibility: "hidden" }}
    >
      <p className="sc-place">
        <span>{s.eyebrow}</span> <Zh>{s.zh}</Zh>
      </p>
      <h2 id={`sect-panel-${area}`} className="sc-panel-title">
        {s.title}
      </h2>
      <div className="sc-rule" aria-hidden />
      {s.lines.map((line) => (
        <p key={line} className="sc-panel-line">
          {line}
        </p>
      ))}
      <div className="sc-panel-actions">
        {talkFirst && <TalkButton onTalk={onTalk} label="Talk to the AI" />}
        <button
          type="button"
          data-sect-open
          className={talkFirst ? "sc-btn" : "sc-btn sc-btn-gold"}
          onClick={() => onOpen({ area, item: null })}
        >
          {s.action}
          <span aria-hidden> →</span>
        </button>
        {area === "scroll" && (
          <a href="/resume.pdf" download={RESUME_HEAD.downloadName} className="sc-btn">
            <span aria-hidden>↓</span> {RESUME_HEAD.download}
          </a>
        )}
        {area === "summit" && (
          <a href={`mailto:${PORTFOLIO.email}`} className="sc-btn">
            Email {PORTFOLIO.email}
          </a>
        )}
      </div>
    </section>
  );
});
