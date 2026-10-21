/**
 * The page's own browser-history entries (links.ts has their URLs and the state they keep):
 * opening a reader or the page view writes one, closing it walks back over them, and between them
 * the hash follows the camera. It works on a HistoryLike and a LocationLike, so tests can use a fake.
 *
 * The race it guards against: closing walks back with history.go(-depth), and the browser finishes
 * that later. Until it does, the entry being left is still the current one. If the hash-follow
 * rewrote that entry's URL meanwhile (the reader is gone, so it may), the walk back could change
 * only the hash (#projects to #about: the entry underneath still names the area where the first
 * reader opened, when the reader's Next button moved on since). The browser then fires hashchange
 * and the page would fly back there. So: nothing rewrites the URL while a walk back is under way;
 * on arrival the entry is renamed to the place the camera is at; and the hashchange the arrival
 * itself causes is ignored.
 */
import { isAreaId } from "./areas";
import { plainUrl, readHistoryState, withHistoryState, type SectHistoryState } from "./links";

/** The parts of window.history the page uses. */
export interface HistoryLike {
  readonly state: unknown;
  pushState(data: unknown, unused: string, url?: string | null): void;
  replaceState(data: unknown, unused: string, url?: string | null): void;
  go(delta: number): void;
}

/** The parts of window.location the page uses. */
export interface LocationLike {
  readonly pathname: string;
  readonly search: string;
  readonly hash: string;
}

/** A walk back that never arrives (a browser that dropped it) stops holding the hash after this long. */
export const LEAVE_TIMEOUT_MS = 1500;
/** The hashchange an arrival causes is dispatched right after its popstate. */
const OWN_HASH_MS = 1000;

export class PageHistory {
  private readonly h: HistoryLike;
  private readonly loc: LocationLike;
  private readonly now: () => number;
  /** When the current walk back started (null: none). */
  private leavingSince: number | null = null;
  /** The URL an arrival renamed its entry to, and until when its hashchange counts as the arrival's. */
  private ownHash: { href: string; until: number } | null = null;

  constructor(h: HistoryLike, loc: LocationLike, now: () => number = () => performance.now()) {
    this.h = h;
    this.loc = loc;
    this.now = now;
  }

  /** The page's state in the current entry, or null for an entry it did not write. */
  current(): SectHistoryState | null {
    return readHistoryState(this.h.state);
  }

  private href(): string {
    const { pathname, search, hash } = this.loc;
    return `${pathname}${search}${hash}`;
  }

  private replaceUrl(state: unknown, url: string): void {
    try {
      this.h.replaceState(state, "", url);
    } catch {
      // Browsers throttle very frequent history calls; the URL is a convenience, not the state.
    }
  }

  /**
   * Sets this entry (push: a new one) to the page's state and URL. Before a push, the entry being
   * left is pointed at `area` (the hash follows the camera only once it settles, so it may still
   * name an earlier place, and Back would then fly there).
   */
  write(mode: "push" | "replace", s: SectHistoryState, url: string, area?: string | null): void {
    try {
      const { pathname, search } = this.loc;
      // Only the page's own key: Next.js's history patch copies its router state in beside it.
      if (mode === "push") {
        if (area && !this.current()) this.h.replaceState(this.h.state, "", plainUrl(area, pathname, search));
        this.h.pushState(withHistoryState(null, s), "", url);
      } else this.h.replaceState(withHistoryState(null, s), "", url);
    } catch {
      // As above.
    }
  }

  /**
   * Leaves the page's own entries: back to the entry the visitor arrived on (the browser finishes
   * that later, with a popstate: `arrived`), or, on that entry already, cleans it in place.
   */
  leave(area: string | null): void {
    const cur = this.current();
    if (cur && cur.depth > 0) {
      this.leavingSince = this.now();
      try {
        this.h.go(-cur.depth);
      } catch {
        this.leavingSince = null;
      }
      return;
    }
    const { pathname, search } = this.loc;
    this.replaceUrl(null, plainUrl(area, pathname, search));
  }

  /** A walk back is under way (its popstate has not come yet). */
  get leaving(): boolean {
    return this.leavingSince !== null && this.now() - this.leavingSince < LEAVE_TIMEOUT_MS;
  }

  /**
   * A popstate arrived at `state`; it ends a walk back. When it closed something (a walk back, or
   * Back while a reader or the page view was open: `closing`) and landed on an entry that is not
   * one of the page's views, that entry is renamed to `area`, where the camera is, and the
   * hashchange the arrival may cause is marked as its own (ownHashChange). Returns true then.
   */
  arrived(state: unknown, area: string | null, closing: boolean): boolean {
    const walked = this.leavingSince !== null;
    this.leavingSince = null;
    const st = readHistoryState(state);
    if (st && (st.reader || st.page)) return false;
    if (!closing && !walked) return false;
    const { pathname, search } = this.loc;
    const url = plainUrl(area, pathname, search);
    if (url !== this.href()) this.replaceUrl(this.h.state, url);
    this.ownHash = { href: this.href(), until: this.now() + OWN_HASH_MS };
    return true;
  }

  /**
   * True for the hashchange that the last arrival caused (the page must not fly for it: the URL
   * already names where the camera is). Any hashchange uses up the mark.
   */
  ownHashChange(): boolean {
    const o = this.ownHash;
    this.ownHash = null;
    return o !== null && o.href === this.href() && this.now() <= o.until;
  }

  /**
   * The hash follows the camera: this entry's URL names `area` (and no ?open= is left over from
   * the link the visitor came in on). Returns false, writing nothing, while a walk back is under
   * way: the entry is about to be left, and its arrival names the place.
   */
  follow(area: string): boolean {
    if (this.leaving) return false;
    if (!isAreaId(area)) return true;
    const { pathname, search } = this.loc;
    const url = plainUrl(area, pathname, search);
    if (url !== this.href()) this.replaceUrl(this.h.state, url);
    return true;
  }
}
