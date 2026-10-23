/**
 * The YouTube demos in /sect's readers (content/sections/forge.tsx) and the music: while a video
 * plays, the sect's music steps aside (app/sect/content/video-watch.ts tracks the players,
 * experience/music.tsx fades the music). Pure: the embed URL, and the players' messages.
 *
 * The players report their state over postMessage, the IFrame API's own channel, without loading
 * its script: the embed asks for it (enablejsapi=1, with this page's origin), the page says it is
 * listening, and the player then sends "infoDelivery" (with info.playerState) and "onStateChange"
 * (info: the state) messages as JSON strings.
 */

/** The IFrame API's player states. */
export const YT_STATE = {
  unstarted: -1,
  ended: 0,
  playing: 1,
  paused: 2,
  buffering: 3,
  cued: 5,
} as const;

/** A player on youtube.com or the privacy-enhanced youtube-nocookie.com, over https. */
export function isYouTubeOrigin(origin: string): boolean {
  let u: URL;
  try {
    u = new URL(origin);
  } catch {
    return false;
  }
  if (u.protocol !== "https:") return false;
  const h = u.hostname;
  return h === "youtube.com" || h.endsWith(".youtube.com") || h === "youtube-nocookie.com" || h.endsWith(".youtube-nocookie.com");
}

/**
 * An embed URL that reports its state to this page: enablejsapi=1 and origin (the player then posts
 * to this origin only). Other parameters are kept; a URL that is not a YouTube embed is returned as
 * it was.
 */
export function withJsApi(src: string, origin: string | null): string {
  let u: URL;
  try {
    u = new URL(src);
  } catch {
    return src;
  }
  if (!isYouTubeOrigin(u.origin) || !u.pathname.startsWith("/embed/")) return src;
  u.searchParams.set("enablejsapi", "1");
  if (origin) u.searchParams.set("origin", origin);
  return u.toString();
}

/** What a player's message says: its state when it carries one; `ready` once it has answered at all. */
export interface YouTubeMessage {
  state: number | null;
  ready: boolean;
}

const EVENTS = new Set(["initialDelivery", "infoDelivery", "onReady", "onStateChange", "apiInfoDelivery"]);

/** Reads a player's postMessage data (a JSON string, or the object). Null for anything else. */
export function parseYouTubeMessage(data: unknown): YouTubeMessage | null {
  let m: unknown = data;
  if (typeof data === "string") {
    if (data.length > 100_000 || !data.startsWith("{")) return null;
    try {
      m = JSON.parse(data);
    } catch {
      return null;
    }
  }
  if (!m || typeof m !== "object") return null;
  const { event, info } = m as { event?: unknown; info?: unknown };
  if (typeof event !== "string" || !EVENTS.has(event)) return null;
  let state: number | null = null;
  if (event === "onStateChange" && typeof info === "number") state = info;
  else if (info && typeof info === "object") {
    const s = (info as { playerState?: unknown }).playerState;
    if (typeof s === "number") state = s;
  }
  if (state !== null && !Number.isFinite(state)) state = null;
  return { state, ready: true };
}

/**
 * Whether a player holds the music down after this state: playing does; a pause, the end, a cued or
 * unstarted player let it back. Buffering keeps what it was: mid-video it is still the video's turn,
 * and an autoplaying embed buffers before a sound is heard (the music waits for the first frame).
 */
export function videoHolds(prev: boolean, state: number): boolean {
  if (state === YT_STATE.playing) return true;
  if (state === YT_STATE.buffering) return prev;
  return false;
}

/** The messages that ask a player for its state (sent until it answers, like the IFrame API's script). */
export function listeningMessages(id: number): string[] {
  return [
    JSON.stringify({ event: "listening", id, channel: "widget" }),
    JSON.stringify({ event: "command", func: "addEventListener", args: ["onStateChange"], id, channel: "widget" }),
  ];
}
