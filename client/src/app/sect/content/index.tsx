"use client";

/**
 * CONTRACT between the /sect 3D engine (src/app/sect/experience) and the content layer (this folder).
 *
 * The engine only imports what is exported here and renders it. Export names and prop shapes are
 * stable; new props are optional.
 *
 * Hotspot ids (glTF extras.hotspot, meta.json hotspots[].id):
 *   area level   "<area>" or "<area>-<thing>"        e.g. "gate", "gate-lions", "mirror-pond"
 *   item level   "project:<projectId>"  forge artifacts, PROJECTS ids (aliases resolve)
 *                "hackathon:<index>"    arena banners, HACKATHONS order (0-based, 0..35)
 *                "role:<index>"         mission jade tablets, EXPERIENCE order
 *                "school:<index>"       library lit floors, EDUCATION order
 *                "skills:<group>"       stele rows 0..4 front to back (the five phrases of the skills line)
 *                "arch:<step>"          formation pillars: 0..5 the flow steps, 6 the stack, 7 the code
 *                "fact:<index>"         abode objects, PERSONAL_FACTS order
 *                "resume"               the giant jade scroll
 *                "moon"                 the moon above the summit (starts a voice call)
 *
 * What the engine renders:
 *   <AreaPanel area onOpen onTalk? side? ref>   one per camera hold, hidden until the engine fades it in
 *   <AreaReader target onClose onNavigate onHighlight? onTalk? onReadAsPage?>   the modal reader
 *   <ContentFallback onTalk? onExit? initial? onHighlight?>   all content as one page (no WebGL, or
 *                                                             "Read as page" with onExit)
 *   hotspotTarget(id) -> ContentTarget | null   what a click on a hotspot opens (null: decorative)
 *   hotspotLabel(id, gltfLabel?) -> { title, zh?, blurb? }   hover label and Places list text
 *
 * Also useful (pure, from @/lib/sect/content): areaItemHotspots(area) for the Places list,
 * commandTarget(voiceCommand) to route VoiceBus commands, parseContentHash(location.hash) for deep
 * links, hotspotArea(id) for the hold an id belongs to.
 */
import "./content.css";

export type { ContentTarget } from "@/lib/sect/content";
export { hotspotTarget, hotspotLabel } from "@/lib/sect/content";
export { AreaPanel, type AreaPanelProps } from "./panel";
export { AreaReader, type AreaReaderProps } from "./reader";
export { ContentFallback, type ContentFallbackProps } from "./fallback";
