/**
 * The eleven areas of the Ming Sect in flight order, and the site section each one presents.
 *
 * Shared contract for the /sect page: camera holds (camera.json holds[].id), chunk ids in the
 * manifest, hotspot ids and the content layer all use these area ids. Hold frames come from
 * camera.json at runtime, never from here.
 */
export const AREA_IDS = [
  "gate",
  "mirror",
  "forge",
  "arena",
  "mission",
  "library",
  "steles",
  "scroll",
  "formation",
  "abode",
  "summit",
] as const;

export type AreaId = (typeof AREA_IDS)[number];

export interface AreaInfo {
  id: AreaId;
  /** DOM section id of the same content on the main page (src/app/page.tsx). */
  sectionId: string;
  /** English place name. */
  label: string;
  /** Chinese place name, shown small beside the label. */
  zh: string;
}

export const AREAS: readonly AreaInfo[] = [
  { id: "gate", sectionId: "hero", label: "Mountain Gate", zh: "山门" },
  { id: "mirror", sectionId: "about", label: "Heart-Mirror Terrace", zh: "心镜台" },
  { id: "forge", sectionId: "projects", label: "Artifact Forge Peak", zh: "炼器峰" },
  { id: "arena", sectionId: "hackathons", label: "Sword-Discussion Arena", zh: "论剑台" },
  { id: "mission", sectionId: "experience", label: "Mission Hall", zh: "任务殿" },
  { id: "library", sectionId: "education", label: "Scripture Pavilion", zh: "藏经阁" },
  { id: "steles", sectionId: "skills", label: "Stele Forest", zh: "碑林" },
  { id: "scroll", sectionId: "resume", label: "Jade Slip Pavilion", zh: "玉简阁" },
  { id: "formation", sectionId: "architecture", label: "Grand Sect-Protecting Formation", zh: "护宗大阵" },
  { id: "abode", sectionId: "personal", label: "Cave Abode", zh: "洞府" },
  { id: "summit", sectionId: "footer", label: "Moon-Gazing Terrace", zh: "望月台" },
];

export function isAreaId(value: string): value is AreaId {
  return (AREA_IDS as readonly string[]).includes(value);
}

export function areaInfo(id: AreaId): AreaInfo {
  const info = AREAS.find((a) => a.id === id);
  if (!info) throw new Error(`unknown area ${id}`);
  return info;
}

/** The area that presents a main-page section id ("projects" -> "forge"), or null. */
export function areaForSection(sectionId: string): AreaId | null {
  return AREAS.find((a) => a.sectionId === sectionId)?.id ?? null;
}
