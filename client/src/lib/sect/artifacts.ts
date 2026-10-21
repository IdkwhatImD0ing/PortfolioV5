/**
 * The forge ring's artifacts: the projects that won, each floating as an object picked for what it
 * does (blender/xianxia-sect/sect/areas/forge.py FORGE_RING). Projects that did not win stay off the
 * ring and have no artifact; the forge's "All" list still shows them.
 */
import { HACKATHONS, findProject, type Hackathon } from "@/lib/portfolio-data";

export interface ProjectArtifact {
  /** English name of the object. */
  name: string;
  zh: string;
  /** One line tying the object to the project. */
  body: string;
}

/** The ring's projects, biggest win first (HACKATHONS order), as forge.py FORGE_RING places them. */
export const FORGE_RING = [
  "dispatchai",
  "talktuahbank",
  "sentinelai",
  "adapted",
  "soundsearch",
  "vocalyze",
  "tft",
  "slugmeditate",
  "splatnft",
  "swarmaid",
  "slugloop",
] as const;

export const PROJECT_ARTIFACTS: Record<(typeof FORGE_RING)[number], ProjectArtifact> = {
  dispatchai: {
    name: "Command Flag",
    zh: "令旗",
    body: "Raise it once and every rescuer knows where to ride first.",
  },
  talktuahbank: {
    name: "Treasure Bowl",
    zh: "聚宝盆",
    body: "Drop in one coin and it fills with more. This one also takes a plain phone call, no app needed.",
  },
  sentinelai: {
    name: "Alarm Bell",
    zh: "警钟",
    body: "It hears a scream or breaking glass before anyone calls for help, and rings the whole mountain awake.",
  },
  adapted: {
    name: "Bamboo Slips",
    zh: "竹简",
    body: "A lesson that rewrites itself as you learn. The glowing lines are the part being taught right now.",
  },
  soundsearch: {
    name: "Path Lamp",
    zh: "引路灯",
    body: "It lights the next step for anyone who can't see the way.",
  },
  vocalyze: {
    name: "Magic Brush",
    zh: "神笔",
    body: "Like Ma Liang's magic brush, it writes by itself. Say your answers and the bank form fills itself in.",
  },
  tft: {
    name: "Peaches of Immortality",
    zh: "蟠桃",
    body: "Shared out over a phone call, so good food reaches people instead of the bin.",
  },
  slugmeditate: {
    name: "Prayer Beads",
    zh: "念珠",
    body: "Count them slowly and a quiet forest at dusk opens around you.",
  },
  splatnft: {
    name: "He's Jade Disc",
    zh: "和氏璧",
    body: "The most famous jade in China: one of a kind, and everyone knows who owns it.",
  },
  swarmaid: {
    name: "Paper Cranes",
    zh: "纸鹤",
    body: "A flock with no leader. Each crane carries spare food to whoever needs it most.",
  },
  slugloop: {
    name: "Wind Fire Wheel",
    zh: "风火轮",
    body: "Nezha rode it to be anywhere at once. This one only has to find the campus loop bus.",
  },
};

const squash = (name: string) => name.toLowerCase().replace(/[^a-z0-9]/g, "");

/** The artifact for a project id or alias, or null for projects outside the ring. */
export function projectArtifact(idOrAlias: string): ProjectArtifact | null {
  const id = findProject(idOrAlias)?.id ?? idOrAlias;
  return (PROJECT_ARTIFACTS as Record<string, ProjectArtifact>)[id] ?? null;
}

/**
 * The project's prize for its card: its own award line, else the win that put it on the ring
 * ("Best AI/ML Hack, HackDavis 2025"), else null.
 */
export function projectAward(idOrAlias: string): string | null {
  const p = findProject(idOrAlias);
  if (p?.award) return p.award;
  const w = ringWin(idOrAlias);
  return w ? `${w.prize}, ${w.name}${w.year ? ` ${w.year}` : ""}` : null;
}

/** True when the project (id or alias) has an artifact on the ring. */
export function onRing(idOrAlias: string): boolean {
  return projectArtifact(idOrAlias) !== null;
}

/**
 * The hackathon win that put a ring project on the ring (matched by name, so "Team Food Tactics"
 * finds TeamFood Tactics), or null.
 */
export function ringWin(idOrAlias: string): Hackathon | null {
  const p = findProject(idOrAlias);
  if (!p || !onRing(p.id)) return null;
  return HACKATHONS.find((h) => squash(h.project) === squash(p.name)) ?? null;
}
