"use client";

/** The summary panel shown while the camera holds at an area. */
import { forwardRef } from "react";
import { PORTFOLIO } from "@/lib/portfolio-data";
import type { AreaId } from "@/lib/sect/areas";
import { RESUME_HEAD } from "@/lib/sect/content-copy";
import { areaSummary, type ContentTarget } from "@/lib/sect/content";
import { LORE, loreLine, type LoreEntry, type LoreId } from "@/lib/sect/lore";
import { BrushName, SealedName, SealStamp } from "../ornaments";
import { TalkButton } from "./ui";

export interface AreaPanelProps {
  area: AreaId;
  /** Open the full reader for this section (or one of its items). */
  onOpen: (target: ContentTarget) => void;
  /** Start a voice call (gate and summit show a talk button; without it they link to the main site). */
  onTalk?: () => void;
  /** Which side of a wide screen the panel sits on; each area has a default. */
  side?: "left" | "right";
  /**
   * The Jin Yong references in this place (lib/sect/lore.ts). Sighted visitors find them by hovering
   * the scene (an aria-hidden card); screen readers get the same names here, visually hidden.
   */
  references?: readonly LoreId[];
}

/**
 * Rendered hidden; the engine fades it in and out through the forwarded ref (style.opacity /
 * style.visibility / style.transform), like the prototype.
 *
 * The place's Chinese name is in the brush hand with the sect's seal: beside the eyebrow on a phone;
 * on wider screens hung in a column down the panel's left edge, like the inscription on a hanging
 * scroll (content.css), while the eyebrow keeps it for screen readers.
 */
export const AreaPanel = forwardRef<HTMLElement, AreaPanelProps>(function AreaPanel({ area, onOpen, onTalk, side, references }, ref) {
  const s = areaSummary(area);
  const talkFirst = area === "gate" || area === "summit";
  return (
    <section
      ref={ref}
      aria-labelledby={`sect-panel-${area}`}
      className={`sect-panel sect-panel-lg sc-theme sc-panel ${(side ?? s.side) === "right" ? "sc-panel-right" : "sc-panel-left"}`}
      style={{ opacity: 0, visibility: "hidden" }}
    >
      <div className="sc-panel-mark" aria-hidden>
        <BrushName text={s.zh} vertical />
        <SealStamp />
      </div>
      <div className="sc-panel-main">
        <p className="sc-place">
          <span>{s.eyebrow}</span> <SealedName text={s.zh} />
        </p>
        <h2 id={`sect-panel-${area}`} className="sc-panel-title">
          {s.title}
        </h2>
        <span className="sect-brushstroke sc-rule" aria-hidden />
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
        {references && references.length > 0 && (
          <ul className="sr-only" aria-label="Jin Yong references in this place">
            {references.map((id) => {
              const e: LoreEntry = LORE[id];
              return (
                <li key={id}>
                  {e.en} (<span lang="zh-Hant">{e.zh}</span>): {loreLine(e)}.
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
});
