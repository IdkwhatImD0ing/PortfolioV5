/**
 * The brush hand of /sect. The places' Chinese names, and the sect's own (明教), are written in Ma
 * Shan Zheng, a brush-script font (SIL Open Font License 1.1), shipped cut down to the characters
 * below: src/app/sect/assets/sect-brush.woff2, made by scripts/subset-brush-font.mjs. All other
 * Chinese on the page (item names, the Jin Yong references) stays in the serif.
 *
 * Pure: no DOM, no font loading.
 */
import { AREAS } from "./areas";

/**
 * Chinese the UI writes in the brush hand besides the place names: the sect, the map's title, and the
 * voice talisman (传音符, the sound-transmission talisman: sect.css writes it, and the 音 seal on it).
 */
export const BRUSH_EXTRA = ["明教", "明教全图", "传音符"] as const;

/**
 * Every character the font subset carries, once each, in brushText() order. A test holds this to
 * brushText() and to the font file; scripts/subset-brush-font.mjs reads this line.
 */
export const BRUSH_GLYPHS = "山门心镜台炼器峰论剑任务殿藏经阁碑林玉简护宗大阵洞府望月明教全图传音符";

/** The characters the brush hand is asked to write (the place names, then BRUSH_EXTRA), each once. */
export function brushText(): string {
  return [...new Set([...AREAS.map((a) => a.zh), ...BRUSH_EXTRA].join(""))].join("");
}

/**
 * The brush font has every character of `text`. When it does not (a name changed and the subset was
 * not remade), the serif writes the whole name: never a mix of two hands in one word.
 */
export function brushCovers(text: string): boolean {
  return text.length > 0 && [...text].every((c) => BRUSH_GLYPHS.includes(c));
}
