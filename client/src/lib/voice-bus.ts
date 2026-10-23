"use client";

export type VoiceCommand =
  | { type: "filter"; tag?: string; year?: number }
  | { type: "focus"; id: string }
  | { type: "open"; id: string }
  | { type: "scroll"; id: string };

type Listener = (cmd: VoiceCommand) => void;

const listeners = new Set<Listener>();

export const VoiceBus = {
  on(fn: Listener): () => void {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
  emit(cmd: VoiceCommand): void {
    listeners.forEach((fn) => fn(cmd));
  },
};

/** Navigation metadata shape emitted by the server via Retell's metadata
 *  event. Each `page` value here MUST be in PAGE_TO_SECTION below. */
export interface NavigationMeta {
  type: string;
  page?:
    | "landing"
    | "education"
    | "project"
    | "personal"
    | "resume"
    | "hackathon"
    | "architecture";
  project_id?: string;
}

/** Server `page` value → the section it names. Each section is a stop of the sect
 *  (lib/sect/areas.ts `sectionId`): the sect's useVoiceRouting turns the command
 *  into a flight there (lib/sect/content.ts commandTarget). The same names are
 *  the site's section hashes (/#projects). */
export const PAGE_TO_SECTION: Record<NonNullable<NavigationMeta["page"]>, string> = {
  landing: "hero",
  personal: "personal",
  education: "education",
  project: "projects",
  resume: "resume",
  hackathon: "hackathons",
  architecture: "architecture",
};

/** Convert a server-side navigation metadata payload into the VoiceBus command
 *  that takes the visitor there: `open` for a named project, else `scroll` to
 *  the page's section. Returns null when the payload isn't a navigation
 *  metadata or the page is unknown. Pure — no side effects, safe to unit-test. */
export function metaToNavigationAction(
  meta: NavigationMeta | null | undefined,
): VoiceCommand | null {
  if (!meta || meta.type !== "navigation" || !meta.page) return null;

  if (meta.page === "project" && meta.project_id) {
    return { type: "open", id: meta.project_id };
  }

  const section = PAGE_TO_SECTION[meta.page];
  if (!section) return null;

  return { type: "scroll", id: section };
}

/** Apply a server navigation payload: emit its VoiceBus command, which the
 *  sect turns into a flight (app/sect/experience/voice.tsx useVoiceRouting).
 *  No-op for anything that isn't navigation metadata. The voice path (Retell
 *  `metadata` events) and the text path (`/chat` SSE chunks) both go through
 *  here. */
export function applyNavigation(meta: NavigationMeta | null | undefined): void {
  const command = metaToNavigationAction(meta);
  if (command) VoiceBus.emit(command);
}
