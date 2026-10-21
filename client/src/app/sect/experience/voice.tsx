"use client";

/**
 * The main site's voice agent on /sect: VoiceOrb and BackendWarmup exactly as the main page renders
 * them (themed only by CSS under .sect-orb in sect.css), plus the bridge the sect needs:
 * - startTalk() presses the orb's own button (the orb exposes no API, and is not edited), or
 *   focuses its panel when that is already open;
 * - useVoiceRouting() turns VoiceBus commands (the agent's navigation, the orb's suggestion chips)
 *   into flights and readers.
 */
import { useEffect, useRef } from "react";
import { BackendWarmup } from "@/components/backend-warmup";
import { VoiceOrb } from "@/components/voice-orb";
import { VoiceBus, applyNavigation, type VoiceCommand } from "@/lib/voice-bus";

export function SectVoice() {
  return (
    <div className="sect-orb">
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
