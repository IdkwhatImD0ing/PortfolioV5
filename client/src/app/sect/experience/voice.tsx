"use client";

/**
 * The main site's voice agent on /sect: VoiceOrb and BackendWarmup exactly as the main page renders
 * them, dressed as a 传音符 (the sound-transmission talisman) by CSS under .sect-orb in sect.css,
 * plus the bridge the sect needs:
 * - the talisman's state (lib/sect/talisman.ts), read from what the orb shows and set on the
 *   wrapper as data-talisman, so the talisman and its panel glow while it listens and speaks (and
 *   the music, ./music.tsx, ducks under the call);
 * - startTalk() presses the orb's own button (the orb exposes no API, and is not edited), or
 *   focuses its panel when that is already open;
 * - useVoiceRouting() turns VoiceBus commands (the agent's navigation, the orb's suggestion chips)
 *   into flights and readers.
 */
import { useEffect, useRef } from "react";
import { BackendWarmup } from "@/components/backend-warmup";
import { VoiceOrb } from "@/components/voice-orb";
import { VoiceBus, applyNavigation, type VoiceCommand } from "@/lib/voice-bus";
import { talismanState, type OrbView } from "@/lib/sect/talisman";

/** What the orb shows: its panel's label, status line, hint and typing bubble (see OrbView). */
function readOrb(root: Element): OrbView {
  const panel = root.querySelector('[role="dialog"]');
  if (!panel) return { open: false, label: "", status: "", hint: "", typing: false };
  return {
    open: true,
    label: panel.querySelector("header")?.textContent ?? "",
    // The controls are the panel's last block; in voice mode a status line heads them.
    status: panel.lastElementChild?.querySelector(":scope > p")?.textContent ?? "",
    hint: panel.querySelector("h4 + p")?.textContent ?? "",
    // The messages follow the header; the typing bubble's dots are the only pulsing dots there.
    typing: panel.querySelector("header + div .animate-pulse-dot") !== null,
  };
}

export function SectVoice() {
  const ref = useRef<HTMLDivElement>(null);
  // Set on the element, not through React state: nothing here re-renders the orb when it changes.
  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    const update = () => {
      const state = talismanState(readOrb(root));
      if (root.dataset.talisman !== state) root.dataset.talisman = state;
    };
    const obs = new MutationObserver(update);
    obs.observe(root, { childList: true, subtree: true, characterData: true });
    update();
    return () => obs.disconnect();
  }, []);
  return (
    <div ref={ref} className="sect-orb">
      <BackendWarmup />
      <VoiceOrb />
    </div>
  );
}

/** Starts a voice call through the orb. Returns false when the orb is not on the page. */
export function startTalk(): boolean {
  const root = document.querySelector(".sect-orb");
  if (!root) return false;
  const orb = root.querySelector<HTMLButtonElement>('button[aria-label="Start a voice conversation"]');
  if (orb) {
    orb.click();
    return true;
  }
  // The panel is already open: bring it to the visitor's attention.
  const panel = root.querySelector<HTMLElement>('[role="dialog"]');
  panel?.focus({ preventScroll: true });
  return panel !== null;
}

/**
 * Calls `onCommand` for every VoiceBus command, two animation frames after it was emitted: the orb
 * scrolls the main page's section into view one frame after emitting (applyNavigation), and the
 * flight must start after that so it has the last word on the scroll position.
 */
export function useVoiceRouting(onCommand: (cmd: VoiceCommand) => void, debug = false): void {
  const ref = useRef(onCommand);
  ref.current = onCommand;
  useEffect(
    () =>
      VoiceBus.on((cmd) => {
        requestAnimationFrame(() => requestAnimationFrame(() => ref.current(cmd)));
      }),
    [],
  );
  useEffect(() => {
    if (!debug) return;
    // ?debug=1: test scripts emit the agent's commands (and its navigation payloads) directly.
    const w = window as unknown as { __sectVoice?: unknown };
    w.__sectVoice = { bus: VoiceBus, applyNavigation };
    return () => {
      delete w.__sectVoice;
    };
  }, [debug]);
}
