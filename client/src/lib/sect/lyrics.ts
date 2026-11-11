import type { MusicKey } from "./music";

export interface LyricWord {
  w: string;
  start: number;
  end: number;
}

export interface LyricLine {
  start: number;
  end: number;
  text: string;
  pinyin: string | null;
  en: string | null;
  estimated: boolean;
  words: readonly LyricWord[];
}

export interface SongLyrics {
  key: MusicKey;
  song: string;
  show: string;
  language: "zh" | "en";
  lines: readonly LyricLine[];
}

const finite = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;

const optionalText = (value: unknown): string | null => (typeof value === "string" && value.trim() ? value : null);

export function parseLyrics(raw: unknown, key: MusicKey): SongLyrics | null {
  if (!raw || typeof raw !== "object") return null;
  const data = raw as Record<string, unknown>;
  const song = optionalText(data.song);
  const show = optionalText(data.show);
  const language = data.language === "zh" || data.language === "en" ? data.language : null;
  if (!song || !show || !language || !Array.isArray(data.lines) || data.lines.length === 0) return null;

  const lines: LyricLine[] = [];
  let previousEnd = 0;
  for (const item of data.lines) {
    if (!item || typeof item !== "object") return null;
    const line = item as Record<string, unknown>;
    const start = finite(line.start);
    const end = finite(line.end);
    const text = optionalText(line.text);
    if (start === null || end === null || end < start || start < previousEnd || !text || !Array.isArray(line.words)) return null;
    const words: LyricWord[] = [];
    let previousWordEnd = start;
    for (const itemWord of line.words) {
      if (!itemWord || typeof itemWord !== "object") return null;
      const word = itemWord as Record<string, unknown>;
      const w = typeof word.w === "string" ? word.w : null;
      const wordStart = finite(word.start);
      const wordEnd = finite(word.end);
      if (
        w === null ||
        wordStart === null ||
        wordEnd === null ||
        wordStart < start ||
        wordStart < previousWordEnd ||
        wordEnd < wordStart ||
        wordEnd > end
      ) {
        return null;
      }
      words.push({ w, start: wordStart, end: wordEnd });
      previousWordEnd = wordEnd;
    }
    if (words.map((word) => word.w).join("") !== text) return null;
    lines.push({
      start,
      end,
      text,
      pinyin: optionalText(line.pinyin),
      en: optionalText(line.en),
      estimated: line.estimated === true,
      words,
    });
    previousEnd = end;
  }
  return { key, song, show, language, lines };
}

/** The line whose half-open interval contains `time`, or null during a lyric gap. */
export function lyricLineAt(lines: readonly LyricLine[], time: number): { line: LyricLine; index: number } | null {
  let low = 0;
  let high = lines.length - 1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    const line = lines[middle];
    if (time < line.start) high = middle - 1;
    else if (time >= line.end) low = middle + 1;
    else return { line, index: middle };
  }
  return null;
}

export function lyricWordAt(words: readonly LyricWord[], time: number): number {
  for (let index = 0; index < words.length; index++) {
    if (time < words[index].end || (words[index].start === words[index].end && time <= words[index].end)) return index;
  }
  return Math.max(0, words.length - 1);
}

export function lyricUnitProgress(word: LyricWord, time: number): number {
  if (word.end <= word.start) return time >= word.start ? 1 : 0;
  return Math.max(0, Math.min(1, (time - word.start) / (word.end - word.start)));
}
