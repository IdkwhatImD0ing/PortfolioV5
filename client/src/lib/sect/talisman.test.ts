import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { talismanState, type OrbView } from "./talisman";

const ORB = path.resolve(__dirname, "../../components/voice-orb/index.tsx");

const closed: OrbView = { open: false, label: "", status: "", hint: "", typing: false };
const voice = (status: string, hint = "", typing = false): OrbView => ({
  open: true,
  label: "voice · powered by Retell✕",
  status,
  hint,
  typing,
});
const text = (typing = false): OrbView => ({ open: true, label: "text chat✕", status: "", hint: "", typing });

describe("talismanState", () => {
  it("waits while the panel is closed", () => {
    expect(talismanState(closed)).toBe("idle");
  });

  it("follows a call: connecting, listening, speaking, ended", () => {
    expect(talismanState(voice("Connecting to the voice agent…", "Connecting…"))).toBe("connecting");
    expect(talismanState(voice("Listening. Ask me anything about Bill's work.", "Connected. I'm listening…"))).toBe("listening");
    expect(talismanState(voice("Speaking. The page moves as I answer."))).toBe("speaking");
    expect(talismanState(voice("Not connected. Start a call, or switch to text.", "Call ended. Start again, or switch to text."))).toBe("ended");
    // A conversation on screen hides the hint: a call that ended reads as ended.
    expect(talismanState(voice("Not connected. Start a call, or switch to text."))).toBe("ended");
  });

  it("shows a call that could not start, or broke", () => {
    expect(talismanState(voice("Not connected. Start a call, or switch to text.", "Couldn't start the call. Tap a suggestion, or switch to text chat."))).toBe("error");
    expect(talismanState(voice("Not connected. Start a call, or switch to text.", "Hit a snag. Please try again."))).toBe("error");
  });

  it("thinks while an answer is on its way, in text or from a suggestion", () => {
    expect(talismanState(text())).toBe("text");
    expect(talismanState(text(true))).toBe("thinking");
    expect(talismanState(voice("Not connected. Start a call, or switch to text.", "", true))).toBe("thinking");
    // A live call keeps its own state over a typing bubble.
    expect(talismanState(voice("Listening. Ask me anything about Bill's work.", "", true))).toBe("listening");
  });

  it("matches the words the orb writes (components/voice-orb): a change there must reach here", () => {
    const src = readFileSync(ORB, "utf8");
    for (const words of [
      "Connecting to the voice agent…",
      "Speaking. The page moves as I answer.",
      "Listening. Ask me anything about Bill's work.",
      "Couldn't start the call.",
      "Hit a snag.",
      '"text chat"',
      'role="dialog"',
      "animate-pulse-dot",
    ]) {
      expect(src, words).toContain(words);
    }
  });
});
