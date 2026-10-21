"use client";

/** Small shared pieces for the /sect readers: text runs, links, item hover props. */
import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import type { Run } from "@/lib/sect/content-copy";
import type { ContentTarget } from "@/lib/sect/content";

/** Chinese text, marked for screen readers and the CJK font stack. */
export function Zh({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span lang="zh" className={className ? `sc-zh ${className}` : "sc-zh"}>
      {children}
    </span>
  );
}

/** Main-page text runs: the gradient serif word becomes a gold serif italic, bold stays bold. */
export function Runs({ runs }: { runs: Run[] }) {
  return (
    <>
      {runs.map((r, i) =>
        r.em ? (
          <em key={i} className="sc-em">
            {r.t}
          </em>
        ) : r.b ? (
          <b key={i} className="sc-strong">
            {r.t}
          </b>
        ) : (
          <span key={i}>{r.t}</span>
        ),
      )}
    </>
  );
}

/** A link that opens in a new tab, and says so to screen readers. */
export function ExtLink({
  href,
  children,
  className,
  download,
}: {
  href: string;
  children: ReactNode;
  className?: string;
  download?: string;
}) {
  if (download) {
    return (
      <a href={href} download={download} className={className}>
        {children}
      </a>
    );
  }
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={className}>
      {children}
      <span className="sc-sr">(opens in a new tab)</span>
    </a>
  );
}

/** Pointer and focus handlers that light up an item's object in the scene while it is in use. */
export function highlightProps(id: string | null, onHighlight?: (id: string | null) => void) {
  if (!onHighlight || !id) return {};
  return {
    onMouseEnter: () => onHighlight(id),
    onMouseLeave: () => onHighlight(null),
    onFocus: () => onHighlight(id),
    onBlur: () => onHighlight(null),
  };
}

/** Props every area body gets from the reader or the one-page view. */
export interface BodyProps {
  /** Item to show (and focus): an item-level hotspot id, or null. */
  item: string | null;
  /** Forge filter from the target (see ContentTarget.filter). */
  filter?: string;
  /**
   * Bumped by the one-page view on every explicit navigation, so asking for the same item again
   * (after going back to the list) reopens it. Readers compare item and filter values only.
   */
  version?: number;
  onNavigate: (target: ContentTarget) => void;
  onHighlight?: (hotspotId: string | null) => void;
  onTalk?: () => void;
  /** "reader" inside the dialog, "page" in the one-page view. */
  mode: "reader" | "page";
  /**
   * A nested view (the project detail) registers how to leave it, so Escape steps back to the
   * list before it closes the reader. Null when nothing nested is open.
   */
  onNestedChange?: (back: (() => void) | null) => void;
  /**
   * The item shown inside the body changed after it opened (the forge's project detail opened or
   * closed): "project:<id>" or null for the list.
   */
  onItemChange?: (item: string | null) => void;
}

/** "14:05" in San Francisco, like the main page's top bar; "--:--" until mounted. */
export function useSfTime(timeZone: string): string {
  const [time, setTime] = useState("--:--");
  useEffect(() => {
    const update = () =>
      setTime(new Date().toLocaleTimeString("en-US", { timeZone, hour: "2-digit", minute: "2-digit", hour12: false }));
    update();
    const t = setInterval(update, 30000);
    return () => clearInterval(t);
  }, [timeZone]);
  return time;
}

/** The talk action: the page's voice call when it has one, else the main site (where the orb is). */
export function TalkButton({
  onTalk,
  label,
  className,
  id,
}: {
  onTalk?: () => void;
  label: string;
  className?: string;
  id?: string;
}) {
  if (onTalk) {
    return (
      <button id={id} type="button" onClick={onTalk} className={className ?? "sc-btn sc-btn-gold"}>
        <span aria-hidden className="sc-moon" />
        {label}
      </button>
    );
  }
  return (
    <Link id={id} href="/" className={className ?? "sc-btn sc-btn-gold"}>
      <span aria-hidden className="sc-moon" />
      {label}
      <span className="sc-btn-note"> on art3m1s.me</span>
    </Link>
  );
}
