/**
 * What the soundtrack panel (app/sect/experience/karaoke-lyrics.tsx) says about a song besides its
 * lyrics: the owner's note on each sung track, and the credit line under the title.
 *
 * The notes are the owner's own words: keep them exactly as written (the curly apostrophe too). The
 * instrumentals have none, and the panel shows nothing in a note's place for them.
 */
import type { MusicKey, MusicTrack } from "./music";

export const SONG_NOTES: Partial<Record<MusicKey, string>> = {
  // Throne of Glory
  mirror:
    "Everyone wants to reach the throne, but only the one who gets there finds out how empty it is. Maybe sadness is all it gives, so it’s better to let the glory go on without you and rest.",
  // 降临
  arena:
    "Trouble finds a person whether or not he is ready for it. Since it comes either way, one may as well walk into the arena on purpose and stay standing until it is over.",
  // 璀璨冒险人
  mission:
    "People who say to take the safe way round mostly mean well, but they do not have to live your life. A few scars are worth it to see what the world is really like.",
  // 化凡
  library:
    "To grow, a person sometimes has to put down what he has and live plain for a long while. A teacher can only hand over so much, and the rest is learned out in the world.",
  // 光之少年
  steles:
    "A hero is just an ordinary person who kept going after getting hurt. Skills come the same way, by trying again until something works.",
  // 浩瀚
  scroll:
    "Being looked down on matters little to someone who already knows what he is good for. The belief has to come before there is any proof of it.",
  // 逍遥
  abode:
    "Fame and money are easier to let go of once you see how quickly the years pass. Success means little with no one to share it, and one person to grow old with is worth more than all of it.",
  // 破茧
  summit:
    "The world does not stop when you lose someone. It still expects you to get up and keep going. The only way through is to hold on to someone, and to be that person for somebody else too.",
};

/** The owner's note on this track, or null (the instrumentals). */
export function songNote(key: MusicKey): string | null {
  return SONG_NOTES[key] ?? null;
}

/** The manifest's artist for a track whose source names no one. */
export const UNCREDITED_ARTIST = "Not credited";

export interface SongCredits {
  /** The drama or donghua the song comes from. */
  show: string;
  /** Who sings or plays it; null when the source names no one. */
  artist: string | null;
  /** The language it is sung in, in words; "Instrumental" when no one sings. */
  sung: string;
}

/** The credit line under the song's title: no "Not credited", and no language for an instrumental. */
export function songCredits(track: Pick<MusicTrack, "show" | "artist" | "language">): SongCredits {
  const artist = track.artist.trim();
  return {
    show: track.show,
    artist: artist && artist.toLowerCase() !== UNCREDITED_ARTIST.toLowerCase() ? artist : null,
    sung: track.language === "zh" ? "Sung in Chinese" : track.language === "en" ? "Sung in English" : "Instrumental",
  };
}

/** The text has Chinese characters in it (set in the CJK serif or the brush hand, with lang="zh"). */
export function hasHan(text: string): boolean {
  // The CJK ideograph blocks (no \p{Script=Han}: the build targets ES2017).
  return /[㐀-䶿一-鿿豈-﫿]/.test(text);
}
