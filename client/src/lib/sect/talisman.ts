/**
 * The voice talisman on /sect: the main page's voice orb, dressed as a 传音符 (a sound-transmission
 * talisman) by sect.css, glows by what the call is doing. The orb is the main page's component and
 * tells nothing else, so its state is read from what it shows, and experience/voice.tsx sets it on
 * the orb's wrapper as data-talisman: for the CSS, and for the music, which ducks under a call
 * (voiceDuck in music.ts).
 *
 * Pure: the caller reads the DOM.
 */

/**
 * idle        the panel is closed: the talisman waits by the corner
 * connecting  a call is being placed
 * listening   in a call, the agent listening
 * speaking    in a call, the agent speaking
 * thinking    a reply on its way (the typing bubble: a text answer, or a suggestion's)
 * text        the text chat, at rest
 * ended       the voice panel with no call (one ended, or a failed start the conversation hides)
 * error       the call could not start, or broke (shown while the panel holds no conversation)
 */
export type TalismanState = "idle" | "connecting" | "listening" | "speaking" | "thinking" | "text" | "ended" | "error";

/** What the orb shows, as voice.tsx reads it. */
export interface OrbView {
  /** The orb's panel is open. */
  open: boolean;
  /** The panel header's label: "voice · powered by Retell", or "text chat". */
  label: string;
  /** The voice panel's status line over its call buttons ("" in text chat). */
  status: string;
  /** The line under "Ask anything.", while the panel holds no conversation ("" once it does). */
  hint: string;
  /** The agent's typing bubble shows. */
  typing: boolean;
}

export function talismanState(v: OrbView): TalismanState {
  if (!v.open) return "idle";
  if (/^\s*connecting/i.test(v.status)) return "connecting";
  if (/^\s*speaking/i.test(v.status)) return "speaking";
  if (/^\s*listening/i.test(v.status)) return "listening";
  if (v.typing) return "thinking";
  if (/text chat/i.test(v.label)) return "text";
  if (/couldn.t start|snag/i.test(v.hint)) return "error";
  return "ended";
}
