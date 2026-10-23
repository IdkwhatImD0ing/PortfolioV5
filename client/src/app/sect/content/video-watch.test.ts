import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { onVideoPlaying, videoPlaying, watchVideo } from "./video-watch";

// --- a window and iframes, just enough for the tracker ---------------------------------------------------

type Handler = (e: MessageEvent) => void;
const handlers = new Set<Handler>();
const fakeWindow = {
  addEventListener: (type: string, fn: Handler) => type === "message" && handlers.add(fn),
  removeEventListener: (type: string, fn: Handler) => type === "message" && handlers.delete(fn),
  setInterval: (fn: () => void, ms: number) => setInterval(fn, ms) as unknown as number,
  clearInterval: (id: number) => clearInterval(id),
};

function frame() {
  const win = { postMessage: vi.fn() };
  const listeners = new Map<string, () => void>();
  const el = {
    contentWindow: win as unknown,
    addEventListener: (type: string, fn: () => void) => listeners.set(type, fn),
    removeEventListener: (type: string) => listeners.delete(type),
  };
  return { el: el as unknown as HTMLIFrameElement, win, load: () => listeners.get("load")?.() };
}

const YT = "https://www.youtube.com";
function send(source: unknown, data: unknown, origin = YT) {
  for (const fn of [...handlers]) fn({ origin, source, data } as MessageEvent);
}
const state = (s: number) => JSON.stringify({ event: "onStateChange", info: s, channel: "widget" });

const stops: (() => void)[] = [];
const watch = (el: HTMLIFrameElement) => {
  const stop = watchVideo(el);
  stops.push(stop);
  return stop;
};

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("window", fakeWindow);
});
afterEach(() => {
  for (const s of stops.splice(0)) s();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("watchVideo", () => {
  it("says the page is listening until the player answers, and again after a load", () => {
    const a = frame();
    watch(a.el);
    expect(a.win.postMessage).toHaveBeenCalledTimes(2);
    expect(JSON.parse(a.win.postMessage.mock.calls[0][0])).toMatchObject({ event: "listening", channel: "widget" });
    vi.advanceTimersByTime(1000);
    expect(a.win.postMessage).toHaveBeenCalledTimes(10);
    send(a.win, JSON.stringify({ event: "onReady", info: null }));
    vi.advanceTimersByTime(1000);
    expect(a.win.postMessage).toHaveBeenCalledTimes(10);
    a.load();
    expect(a.win.postMessage).toHaveBeenCalledTimes(12);
  });

  it("gives up on a player that never answers", () => {
    const a = frame();
    watch(a.el);
    vi.advanceTimersByTime(60_000);
    expect(a.win.postMessage.mock.calls.length).toBeLessThanOrEqual(2 * 41);
  });

  it("follows several players: the music waits until none plays", () => {
    const a = frame();
    const b = frame();
    watch(a.el);
    watch(b.el);
    const changes = vi.fn();
    stops.push(onVideoPlaying(changes));
    send(a.win, state(1));
    expect(videoPlaying()).toBe(true);
    send(b.win, state(3));
    send(b.win, state(1));
    send(a.win, state(2));
    expect(videoPlaying()).toBe(true);
    send(b.win, state(0));
    expect(videoPlaying()).toBe(false);
    expect(changes).toHaveBeenCalledTimes(2);
  });

  it("reads infoDelivery's playerState too, and keeps a buffering player's turn", () => {
    const a = frame();
    watch(a.el);
    send(a.win, JSON.stringify({ event: "infoDelivery", info: { playerState: 1, currentTime: 2 } }));
    expect(videoPlaying()).toBe(true);
    send(a.win, JSON.stringify({ event: "infoDelivery", info: { playerState: 3 } }));
    expect(videoPlaying()).toBe(true);
    send(a.win, JSON.stringify({ event: "infoDelivery", info: { currentTime: 3 } }));
    expect(videoPlaying()).toBe(true);
    send(a.win, JSON.stringify({ event: "infoDelivery", info: { playerState: 2 } }));
    expect(videoPlaying()).toBe(false);
  });

  it("counts a player taken off the page as stopped", () => {
    const a = frame();
    const stop = watch(a.el);
    send(a.win, state(1));
    expect(videoPlaying()).toBe(true);
    stop();
    expect(videoPlaying()).toBe(false);
    expect(handlers.size).toBe(0);
    // Its late messages change nothing.
    send(a.win, state(1));
    expect(videoPlaying()).toBe(false);
  });

  it("ignores other origins, other windows and other messages", () => {
    const a = frame();
    watch(a.el);
    send(a.win, state(1), "https://evil.example");
    send(a.win, state(1), "http://www.youtube.com");
    send({ postMessage() {} }, state(1));
    send(a.win, "hello");
    send(a.win, { event: "onStateChange", info: "1" });
    expect(videoPlaying()).toBe(false);
    // The privacy-enhanced player is heard like the other.
    send(a.win, state(1), "https://www.youtube-nocookie.com");
    expect(videoPlaying()).toBe(true);
  });
});
