"use client";

/**
 * Which YouTube demos on the page are playing, so the sect's music can step aside while one does
 * (experience/music.tsx). Each embed registers its iframe (useVideoWatch); any number can be on the
 * page at once, and the music waits until none plays. An embed taken off the page (the reader
 * closed, another project opened) counts as stopped.
 *
 * The players speak the IFrame API's postMessage channel (lib/sect/youtube.ts), without its script:
 * once a player has loaded, the page tells it that it is listening, every 250 ms until it answers,
 * and from then on it reports its state.
 */
import { type RefObject, useEffect } from "react";
import { isYouTubeOrigin, listeningMessages, parseYouTubeMessage, videoHolds } from "@/lib/sect/youtube";

interface Player {
  /** Its id on the channel (the IFrame API numbers its players the same way). */
  id: number;
  /** It plays, or buffers mid-video (videoHolds). */
  holds: boolean;
  /** It has answered: the page stops asking. */
  heard: boolean;
  timer: number;
  onLoad: () => void;
}

/** How long the page keeps asking a player that never answers (a blocked or failed embed). */
const ASK_MS = 250;
const ASK_TRIES = 40;

const players = new Map<HTMLIFrameElement, Player>();
const listeners = new Set<() => void>();
let nextId = 1;
let playing = false;

function update(): void {
  let any = false;
  for (const p of players.values()) any ||= p.holds;
  if (any === playing) return;
  playing = any;
  for (const fn of listeners) fn();
}

function onMessage(e: MessageEvent): void {
  if (!isYouTubeOrigin(e.origin)) return;
  const msg = parseYouTubeMessage(e.data);
  if (!msg) return;
  for (const [frame, p] of players) {
    if (frame.contentWindow === null || frame.contentWindow !== e.source) continue;
    if (!p.heard) {
      p.heard = true;
      window.clearInterval(p.timer);
    }
    if (msg.state !== null) p.holds = videoHolds(p.holds, msg.state);
    update();
    return;
  }
}

function ask(frame: HTMLIFrameElement, p: Player): void {
  window.clearInterval(p.timer);
  p.heard = false;
  let tries = 0;
  const send = () => {
    if (p.heard || ++tries > ASK_TRIES) {
      window.clearInterval(p.timer);
      return;
    }
    // "*": the player's own origin may be youtube.com or youtube-nocookie.com; these messages carry nothing private.
    for (const m of listeningMessages(p.id)) frame.contentWindow?.postMessage(m, "*");
  };
  send();
  p.timer = window.setInterval(send, ASK_MS);
}

/** Starts following a player; returns the function that stops (and counts it as stopped). */
export function watchVideo(frame: HTMLIFrameElement): () => void {
  if (players.size === 0) window.addEventListener("message", onMessage);
  const p: Player = { id: nextId++, holds: false, heard: false, timer: 0, onLoad: () => ask(frame, p) };
  players.set(frame, p);
  // A load (the first, or the player navigating) restarts the handshake.
  frame.addEventListener("load", p.onLoad);
  ask(frame, p);
  return () => {
    window.clearInterval(p.timer);
    frame.removeEventListener("load", p.onLoad);
    if (players.get(frame) !== p) return;
    players.delete(frame);
    if (players.size === 0) window.removeEventListener("message", onMessage);
    update();
  };
}

/** A YouTube demo is playing somewhere on the page. */
export function videoPlaying(): boolean {
  return playing;
}

/** Calls `fn` whenever videoPlaying() changes. */
export function onVideoPlaying(fn: () => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

/** Follows the iframe in `ref` while it is mounted. */
export function useVideoWatch(ref: RefObject<HTMLIFrameElement | null>): void {
  useEffect(() => {
    const frame = ref.current;
    return frame ? watchVideo(frame) : undefined;
  }, [ref]);
}
