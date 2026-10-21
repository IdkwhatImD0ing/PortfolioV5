"use client";

/**
 * Item views inside a reader: a clicked tablet, banner, floor, stele row, pillar, fact or named spot
 * opens its own view (like a forge artifact opens its project), with a way back to the whole
 * section, the item before and after it, and links to what it connects to elsewhere in the sect.
 * The one-page view keeps the plain lists.
 */
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { areaInfo, type AreaId } from "@/lib/sect/areas";
import { hotspotLabel, itemDomId, thingArea, thingLore, type ContentTarget } from "@/lib/sect/content";
import { itemSiblings, type Related } from "@/lib/sect/explore";
import type { BodyProps } from "./ui";

export interface ItemDetail {
  /** The item whose view is open, or null for the section's list. */
  openItem: string | null;
  /** False in the one-page view: items stay in their lists there. */
  enabled: boolean;
  /** Open an item's view (from its card, the pager or a related link). */
  open: (item: string) => void;
  /** Back to the section's list. */
  back: () => void;
  /** Go to a target: an item of this section opens here, anything else goes through onNavigate. */
  go: (t: ContentTarget) => void;
}

/**
 * List or item view for one area's body. `accepts` says which items have a view here. Follows the
 * forge's project detail: a new target from the engine replaces the view, Escape steps back to the
 * list first, the page hears about items opened inside (for its history), and focus lands on the
 * item's title when it opens and on its card when the list comes back.
 */
export function useItemDetail(
  area: AreaId,
  accepts: (item: string) => boolean,
  { item, version = 0, mode, onNavigate, onNestedChange, onItemChange }: BodyProps,
): ItemDetail {
  const enabled = mode === "reader";
  const want = (it: string | null) => (enabled && it && accepts(it) ? it : null);
  const [openItem, setOpenItem] = useState<string | null>(() => want(item));
  const [seen, setSeen] = useState({ item, version });
  if (seen.item !== item || seen.version !== version) {
    setOpenItem(want(item));
    setSeen({ item, version });
  }

  const returnTo = useRef<string | null>(null);
  const focusOpened = useRef(false);

  const back = useCallback(() => {
    setOpenItem((cur) => {
      returnTo.current = cur;
      return null;
    });
  }, []);
  const open = useCallback((it: string) => {
    focusOpened.current = true;
    setOpenItem(it);
  }, []);
  const go = useCallback(
    (t: ContentTarget) => {
      if (t.area === area && t.item && accepts(t.item)) open(t.item);
      else if (t.area === area && !t.item && !t.filter) back();
      else onNavigate(t);
    },
    [area, accepts, open, back, onNavigate],
  );

  // Report the item shown (not on the first render), so the page keeps the URL in step.
  const reported = useRef(openItem);
  const itemChangeRef = useRef(onItemChange);
  itemChangeRef.current = onItemChange;
  useEffect(() => {
    if (reported.current === openItem) return;
    reported.current = openItem;
    itemChangeRef.current?.(openItem);
  }, [openItem]);

  // Escape inside an item view steps back to the list first.
  const backRef = useRef(back);
  backRef.current = back;
  useEffect(() => {
    onNestedChange?.(openItem ? () => backRef.current() : null);
  }, [openItem, onNestedChange]);
  useEffect(() => () => onNestedChange?.(null), [onNestedChange]);

  // Opened from the list or the pager: show the view from its top, focus its title.
  useEffect(() => {
    if (!openItem || !focusOpened.current) return;
    focusOpened.current = false;
    const title = document.getElementById(itemDomId(openItem));
    const sheet = title?.closest(".sc-sheet-body");
    if (sheet) sheet.scrollTop = 0;
    title?.focus({ preventScroll: true });
  }, [openItem]);

  // Back on the list: focus the card of the item just left (its open button when it has one).
  useEffect(() => {
    if (openItem || !returnTo.current) return;
    const id = returnTo.current;
    returnTo.current = null;
    const card = document.getElementById(itemDomId(id));
    if (!card) return;
    card.scrollIntoView({ block: "nearest" });
    (card.querySelector<HTMLElement>("button.sc-open") ?? card).focus({ preventScroll: true });
  }, [openItem]);

  return { openItem: enabled ? openItem : null, enabled, open, back, go };
}

/**
 * Props that make a list card open its item's view on click (reader only). The card's title should
 * also be an <OpenTitle> so keyboards can open it.
 */
export function openCardProps(d: ItemDetail, id: string) {
  if (!d.enabled) return {};
  return {
    onClick: (e: React.MouseEvent) => {
      // Links and buttons inside the card keep their own action.
      if ((e.target as HTMLElement).closest("a, button")) return;
      d.open(id);
    },
    "data-openable": "",
  };
}

/** A card's title: a button that opens the item's view in a reader, plain text in the page view. */
export function OpenTitle({ d, id, children }: { d: ItemDetail; id: string; children: ReactNode }) {
  if (!d.enabled) return <>{children}</>;
  return (
    <button type="button" className="sc-open" onClick={() => d.open(id)}>
      {children}
    </button>
  );
}

/** The frame of an item view: back to the section, an optional eyebrow, title, the item's content, the pager. */
export function DetailFrame({
  d,
  item,
  eyebrow,
  title,
  labelOf,
  children,
}: {
  d: ItemDetail;
  item: string;
  eyebrow?: ReactNode;
  title: ReactNode;
  /** Pager button text for a sibling (default: its hover label). */
  labelOf?: (id: string) => string;
  children: ReactNode;
}) {
  const { prev, next } = itemSiblings(item);
  const label = labelOf ?? ((id: string) => hotspotLabel(id).title);
  return (
    <div className="sc-body">
      <button type="button" className="sc-back" onClick={d.back}>
        <span aria-hidden>←</span> Back
      </button>
      <article className="sc-detail sc-item" aria-labelledby={itemDomId(item)}>
        {eyebrow && (
          <p className="sc-eyebrow">
            <span aria-hidden className="sc-diamond" />
            {eyebrow}
          </p>
        )}
        <h3 id={itemDomId(item)} tabIndex={-1} data-sc-top="" className="sc-h3">
          {title}
        </h3>
        {children}
      </article>
      {(prev || next) && (
        <nav aria-label="Nearby" className="sc-pager">
          {prev ? (
            <button type="button" className="sc-btn sc-pager-btn" onClick={() => d.open(prev)}>
              <span aria-hidden>←</span> <span className="sc-pager-text">{label(prev)}</span>
            </button>
          ) : (
            <span />
          )}
          {next && (
            <button type="button" className="sc-btn sc-pager-btn" onClick={() => d.open(next)}>
              <span className="sc-pager-text">{label(next)}</span> <span aria-hidden>→</span>
            </button>
          )}
        </nav>
      )}
    </div>
  );
}

/** A named spot's place (its area's name) and its own name, for the eyebrow and title. */
export function spotNames(id: string): { place: string; name: string } {
  const area = thingArea(id);
  return { place: area ? areaInfo(area).label : "", name: thingLore(id)?.name ?? id };
}

/** Links to related things in the sect, as rows with a note. */
export function RelatedList({ title, items, onGo }: { title: string; items: Related[]; onGo: (t: ContentTarget) => void }) {
  if (items.length === 0) return null;
  return (
    <div className="sc-related">
      <h4 className="sc-label">{title}</h4>
      <ul className="sc-related-list">
        {items.map((r) => (
          <li key={`${r.target.area}:${r.target.item ?? ""}:${r.target.filter ?? ""}:${r.title}`}>
            <button type="button" className="sc-related-row" onClick={() => onGo(r.target)}>
              <span className="sc-related-title">{r.title}</span>
              {r.note && <span className="sc-related-note">{r.note}</span>}
              <span aria-hidden className="sc-related-arrow">
                →
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
