/**
 * The brush hand of /sect. The places' Chinese names, and the sect's own (日月神教), are written in Ma
 * Shan Zheng, a brush-script font (SIL Open Font License 1.1), shipped cut down to the characters
 * below: src/app/sect/assets/sect-brush.woff2, made by scripts/subset-brush-font.mjs. All other
 * Chinese on the page (item names, the Jin Yong references) stays in the serif.
 *
 * Pure: no DOM, no font loading.
 */
import { AREAS } from "./areas";
import INK from "./brush-ink.json";

/**
 * Chinese the UI writes in the brush hand besides the place names: the sect (日月神教, the Sun Moon
 * Divine Cult; its 神 is the red seal's, ornaments.tsx SealStamp), the map's title, and the voice
 * talisman (传音符, the sound-transmission talisman: sect.css writes it, and the 音 seal on it).
 */
export const BRUSH_EXTRA = ["日月神教", "日月神教全图", "传音符"] as const;

/**
 * Every character the font subset carries, once each, in brushText() order. A test holds this to
 * brushText() and to the font file; scripts/subset-brush-font.mjs reads this line.
 */
export const BRUSH_GLYPHS = "山门心镜台炼器峰论剑任务殿藏经阁碑林玉简护宗大阵洞府望月日神教全图传音符";

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

/**
 * Where each brush character's ink sits in its em box: [left, right], the paper between the box's
 * side and the ink, in em. Made with the font by scripts/subset-brush-font.mjs.
 */
export const BRUSH_INK: Readonly<Record<string, readonly number[]>> = INK;

/** A name set ink to ink: the margin before its first character and after each one, in em. */
export interface BrushSpacing {
  start: number;
  after: number[];
}

/**
 * The margins that set `text`'s characters `gap` em apart, ink to ink, with the box trimmed to the
 * ink at both ends (so a centred name centres on its ink). The brush leaves a narrow character wide
 * paper either side (日 0.27 em, 教 0.05 em), so plain tracking spaces 日月神教 as 日 · 月神教. Null
 * when the brush lacks a character (the serif's spacing is even already). Horizontal names only.
 */
export function brushSpacing(text: string, gap: number): BrushSpacing | null {
  const chars = [...text];
  if (!brushCovers(text) || chars.some((c) => !BRUSH_INK[c])) return null;
  const ink = chars.map((c) => BRUSH_INK[c]);
  const round = (v: number) => Math.round(v * 1000) / 1000;
  return {
    start: round(-ink[0][0]),
    after: ink.map(([, right], i) => round(i + 1 < ink.length ? gap - right - ink[i + 1][0] : -right)),
  };
}
