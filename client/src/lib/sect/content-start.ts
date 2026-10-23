/**
 * How the sect (the home page) starts: the 3D flight, or straight into the one-page view (no 3D download at all).
 *
 * The page view is chosen with ?view=page (the loading screen links there, and it works before any
 * script has run), or automatically when the browser asks to save data or reports a very slow
 * connection: the flight downloads about 20 MB before its first picture (lib/sect/opening.ts
 * openingMegabytes reads the figure from the manifest). ?view=flight always flies, and so does any
 * URL that sets one of the flight's own test options.
 *
 * A flight that opens at the top of the path (no deep link, no ?frame= or ?yaw= view) shows the
 * poster still of that view behind the loading screen (posterStart, POSTER_SCRIPT).
 */

import { wrapYaw } from "./free-look";
import { POSTER } from "./opening";

export type StartReason = "asked" | "save-data" | "slow-network";

export type StartView = { view: "flight" } | { view: "page"; reason: StartReason };

/** The Network Information API fields we read (Chrome and Android only; absent elsewhere). */
export interface NetworkHint {
  saveData?: boolean;
  effectiveType?: string;
}

/** URL options that only mean something to the flight (screenshots, tests, tiers). */
const FLIGHT_OPTIONS = ["frame", "debug", "tier", "set", "ui", "flyer", "yaw"];

export function startView(search: string, net?: NetworkHint | null): StartView {
  const params = new URLSearchParams(search);
  const view = params.get("view")?.trim().toLowerCase();
  if (view === "page") return { view: "page", reason: "asked" };
  if (view === "flight" || view === "3d") return { view: "flight" };
  if (FLIGHT_OPTIONS.some((k) => params.has(k))) return { view: "flight" };
  if (net?.saveData) return { view: "page", reason: "save-data" };
  // Only the truly slow classes: browsers report "3g" for many ordinary connections.
  if (net?.effectiveType && /^(slow-2g|2g)$/i.test(net.effectiveType)) return { view: "page", reason: "slow-network" };
  return { view: "flight" };
}

/** URL options that open the flight somewhere other than the top of the path. */
const ELSEWHERE_OPTIONS = ["open", "frame", "yaw"];

/**
 * The id of the portfolio as text that the server renders under the flight (app/sect/summary.tsx):
 * sect-client.tsx makes it inert once the page's scripts run. Here, not beside the summary, so the
 * first script keeps none of the portfolio's data.
 */
export const SUMMARY_ID = "sect-summary";

/** The attribute on <html> that shows the poster still behind the loading screen. */
export const POSTER_ATTR = "data-sect-poster";

/**
 * The flight opens on its default start view, the one the poster still shows: no deep link
 * (?open= or any hash: the hash names a place), no ?frame= or ?yaw= view, and the full asset set.
 */
export function posterStart(search: string, hash: string, net?: NetworkHint | null): boolean {
  if (startView(search, net).view !== "flight") return false;
  if (hash.replace(/^#/, "") !== "") return false;
  const params = new URLSearchParams(search);
  if (ELSEWHERE_OPTIONS.some((k) => params.has(k))) return false;
  const set = (params.get("set") ?? "").trim().toLowerCase();
  return set === "" || set === "full";
}

/**
 * posterStart as a script that runs in the server-rendered page before its first paint (the page's
 * own scripts come seconds later on a phone): it sets POSTER_ATTR on <html>, so the loading screen's
 * poster shows from the first paint, and preloads the still for the screen's orientation (the
 * browser fetches only the one whose media matches). The flight then keeps the attribute in step
 * with its own decision (sect-experience.tsx). Plain ES5, and it never throws.
 */
export const POSTER_SCRIPT = `(function(){try{var p=new URLSearchParams(location.search),v=(p.get("view")||"").trim().toLowerCase(),f=${JSON.stringify(FLIGHT_OPTIONS)},e=${JSON.stringify(ELSEWHERE_OPTIONS)},has=function(k){return p.has(k)};if(v==="page"||location.hash.replace(/^#/,"")!=="")return;if(v!=="flight"&&v!=="3d"&&!f.some(has)){var n=navigator.connection;if(n&&(n.saveData||/^(slow-2g|2g)$/i.test(n.effectiveType||"")))return}if(e.some(has))return;var s=(p.get("set")||"").trim().toLowerCase();if(s!==""&&s!=="full")return;document.documentElement.setAttribute(${JSON.stringify(POSTER_ATTR)},"");[[${JSON.stringify(POSTER.landscape)},"landscape"],[${JSON.stringify(POSTER.portrait)},"portrait"]].forEach(function(i){var l=document.createElement("link");l.rel="preload";l.as="image";l.href=i[0];l.media="(orientation: "+i[1]+")";l.setAttribute("fetchpriority","high");document.head.appendChild(l)})}catch(x){}})();`;

/**
 * The page view's line on why the flight was skipped for the visitor (empty when they asked for the
 * page view), with the size of the flight's first download when the manifest gave it.
 */
export function skippedNote(reason: StartReason, megabytes: number | null): string {
  if (reason === "asked") return "";
  const size = megabytes !== null ? ` (about ${megabytes} MB)` : "";
  return reason === "save-data"
    ? `Your browser asked to save data, so the 3D flight${size} was skipped.`
    : `Your connection looks slow, so the 3D flight${size} was skipped.`;
}

/** `search` with `view` set to `value` (other options, like ?open=, are kept). */
function withView(search: string, value: string): string {
  const params = new URLSearchParams(search);
  params.set("view", value);
  return `?${params.toString()}`;
}

/** The page-view address for the current one: "/?view=page", keeping ?open= and the hash. */
export function pageViewHref(search = "", hash = ""): string {
  return `/${withView(search, "page")}${hash}`;
}

/** The flight's address from the page view: "/?view=flight", keeping ?open= and the hash. */
export function flightHref(search = "", hash = ""): string {
  return `/${withView(search, "flight")}${hash}`;
}

/**
 * ?yaw=<degrees>: the view starts turned this far from the path's heading (positive turns left),
 * like a drag would leave it, for screenshots of what lies beside and behind a stop (with ?frame=N
 * and ?ui=0). A test option, not linked from anywhere. Radians in (-pi, pi], or null when absent or
 * not a number. The first scroll swings it back as usual.
 */
export function startYaw(search: string): number | null {
  const raw = new URLSearchParams(search).get("yaw");
  if (raw === null || raw.trim() === "") return null;
  const deg = Number(raw);
  return Number.isFinite(deg) ? wrapYaw((deg * Math.PI) / 180) : null;
}
