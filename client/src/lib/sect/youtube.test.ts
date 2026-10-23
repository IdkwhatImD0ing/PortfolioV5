import { describe, expect, it } from "vitest";
import { projectMedia } from "./content";
import { PROJECTS } from "@/lib/portfolio-data";
import { YT_STATE, isYouTubeOrigin, listeningMessages, parseYouTubeMessage, videoHolds, withJsApi } from "./youtube";

describe("isYouTubeOrigin", () => {
  it("takes youtube.com and the privacy-enhanced youtube-nocookie.com, over https only", () => {
    for (const o of ["https://www.youtube.com", "https://youtube.com", "https://m.youtube.com", "https://www.youtube-nocookie.com", "https://youtube-nocookie.com"]) {
      expect(isYouTubeOrigin(o), o).toBe(true);
    }
    for (const o of ["http://www.youtube.com", "https://youtube.com.evil.example", "https://notyoutube.com", "https://evil.example", "null", "", "https://vimeo.com"]) {
      expect(isYouTubeOrigin(o), o).toBe(false);
    }
  });
});

describe("withJsApi", () => {
  const origin = "https://art3m1s.me";

  it("asks the embed to report to this page, keeping its own parameters", () => {
    const u = new URL(withJsApi("https://www.youtube.com/embed/hdpdgxrilQM?rel=0&modestbranding=1&autoplay=1", origin));
    expect(u.origin).toBe("https://www.youtube.com");
    expect(u.pathname).toBe("/embed/hdpdgxrilQM");
    expect(Object.fromEntries(u.searchParams)).toEqual({ rel: "0", modestbranding: "1", autoplay: "1", enablejsapi: "1", origin });
  });

  it("works on youtube-nocookie embeds, and without an origin", () => {
    const u = new URL(withJsApi("https://www.youtube-nocookie.com/embed/abc?rel=0", origin));
    expect(u.hostname).toBe("www.youtube-nocookie.com");
    expect(u.searchParams.get("enablejsapi")).toBe("1");
    expect(u.searchParams.get("origin")).toBe(origin);
    expect(new URL(withJsApi("https://www.youtube.com/embed/abc", null)).searchParams.has("origin")).toBe(false);
  });

  it("leaves anything else alone", () => {
    for (const src of ["https://vimeo.com/123", "https://www.youtube.com/watch?v=abc", "/sect/resume.pdf", "not a url"]) expect(withJsApi(src, origin)).toBe(src);
  });

  it("covers every demo the forge embeds", () => {
    const embeds = PROJECTS.map((p) => projectMedia(p).embed).filter((e): e is string => e !== null);
    expect(embeds.length).toBeGreaterThan(0);
    for (const e of embeds) expect(new URL(withJsApi(`${e}&autoplay=1`, origin)).searchParams.get("enablejsapi")).toBe("1");
  });
});

describe("parseYouTubeMessage", () => {
  it("reads the state from onStateChange and infoDelivery, as strings or objects", () => {
    expect(parseYouTubeMessage('{"event":"onStateChange","info":1,"id":1,"channel":"widget"}')).toEqual({ state: 1, ready: true });
    expect(parseYouTubeMessage('{"event":"infoDelivery","info":{"playerState":2,"currentTime":12.5},"id":1}')).toEqual({ state: 2, ready: true });
    expect(parseYouTubeMessage({ event: "onStateChange", info: 0 })).toEqual({ state: 0, ready: true });
    expect(parseYouTubeMessage('{"event":"initialDelivery","info":{"playerState":-1}}')).toEqual({ state: -1, ready: true });
  });

  it("knows a player that answered without a state", () => {
    expect(parseYouTubeMessage('{"event":"onReady","info":{"apiInterfaces":[]}}')).toEqual({ state: null, ready: true });
    expect(parseYouTubeMessage('{"event":"infoDelivery","info":{"currentTime":3}}')).toEqual({ state: null, ready: true });
  });

  it("ignores everything else", () => {
    for (const d of ["", "hello", "{not json", '{"event":"listening"}', '{"event":"command","func":"playVideo"}', "[1,2]", 42, null, undefined, { info: 1 }, '{"event":"onStateChange","info":"1"}']) {
      const m = parseYouTubeMessage(d);
      expect(m === null || m.state === null, String(d)).toBe(true);
    }
    expect(parseYouTubeMessage("x".repeat(200_000))).toBeNull();
  });
});

describe("videoHolds", () => {
  it("holds the music while playing; lets it back on pause, end, cue", () => {
    expect(videoHolds(false, YT_STATE.playing)).toBe(true);
    expect(videoHolds(true, YT_STATE.paused)).toBe(false);
    expect(videoHolds(true, YT_STATE.ended)).toBe(false);
    expect(videoHolds(true, YT_STATE.cued)).toBe(false);
    expect(videoHolds(true, YT_STATE.unstarted)).toBe(false);
  });

  it("keeps what it was while buffering: an autoplaying embed waits for its first frame", () => {
    const run = (states: number[]) => states.reduce((held, s) => videoHolds(held, s), false);
    expect(run([YT_STATE.unstarted, YT_STATE.buffering])).toBe(false);
    expect(run([YT_STATE.unstarted, YT_STATE.buffering, YT_STATE.playing])).toBe(true);
    expect(run([YT_STATE.playing, YT_STATE.buffering])).toBe(true);
    expect(run([YT_STATE.playing, YT_STATE.paused, YT_STATE.buffering])).toBe(false);
  });
});

describe("listeningMessages", () => {
  it("is the IFrame API's handshake: listening, then a listener for state changes", () => {
    const [a, b] = listeningMessages(3).map((m) => JSON.parse(m));
    expect(a).toEqual({ event: "listening", id: 3, channel: "widget" });
    expect(b).toEqual({ event: "command", func: "addEventListener", args: ["onStateChange"], id: 3, channel: "widget" });
  });
});
