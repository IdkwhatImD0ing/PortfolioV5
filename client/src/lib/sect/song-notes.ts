/**
 * What the soundtrack panel (app/sect/experience/karaoke-lyrics.tsx) says about a song besides its
 * lyrics: the owner's note on each sung track, and the credit line under the title.
 *
 * The English notes are the owner's own words: keep them exactly as written (the curly apostrophe
 * too). Each has a Chinese version beside it; scripts/subset-lyrics-font.mjs reads this file so the
 * brush font carries its characters. The
 * instrumentals have none, and the panel shows nothing in a note's place for them.
 */
import type { MusicKey, MusicTrack } from "./music";

/** A note in both its languages: the owner's English, and its Chinese (the panel swaps them on a click). */
export interface SongNote {
  en: string;
  zh: string;
}

export const SONG_NOTES: Partial<Record<MusicKey, SongNote>> = {
  // Throne of Glory
  mirror: {
    en: "Everyone wants to reach the throne, but only the one who gets there finds out how empty it is. Maybe sadness is all it gives, so it’s better to let the glory go on without you and rest.",
    zh: "人人都想登上王座，可只有坐上去的人，才知道那里有多空。也许王座能给的只有悲伤，不如让荣耀自己走下去，你且歇一歇。",
  },
  // 降临
  arena: {
    en: "Trouble finds a person whether or not he is ready for it. Since it comes either way, one may as well walk into the arena on purpose and stay standing until it is over.",
    zh: "麻烦要来，从不管人有没有准备好。既然躲不过，不如自己走上擂台，站到最后一刻。",
  },
  // 璀璨冒险人
  mission: {
    en: "People who say to take the safe way round mostly mean well, but they do not have to live your life. A few scars are worth it to see what the world is really like.",
    zh: "劝你走稳妥路的人，多半是好意，可日子终究不是他们替你过。带几道伤疤，换一眼真实的世界，值得。",
  },
  // 化凡
  library: {
    en: "To grow, a person sometimes has to put down what he has and live plain for a long while. A teacher can only hand over so much, and the rest is learned out in the world.",
    zh: "人要长进，有时得放下手里的一切，平平淡淡过上很久。师父能教的只有那么多，剩下的，要到世间去学。",
  },
  // 光之少年
  steles: {
    en: "A hero is just an ordinary person who kept going after getting hurt. Skills come the same way, by trying again until something works.",
    zh: "英雄不过是受了伤还肯往前走的普通人。本事也是这样来的，一次次再试，直到成了为止。",
  },
  // 浩瀚
  scroll: {
    en: "Being looked down on matters little to someone who already knows what he is good for. The belief has to come before there is any proof of it.",
    zh: "一个人若早已知道自己的斤两，旁人看不起，也就算不得什么。这份相信，得先于任何证明。",
  },
  // 逍遥
  abode: {
    en: "Fame and money are easier to let go of once you see how quickly the years pass. Success means little with no one to share it, and one person to grow old with is worth more than all of it.",
    zh: "看清岁月走得有多快，名和利也就容易放下了。无人分享的成功没什么意思，有一个人相伴到老，胜过这一切。",
  },
  // 破茧
  summit: {
    en: "The world does not stop when you lose someone. It still expects you to get up and keep going. The only way through is to hold on to someone, and to be that person for somebody else too.",
    zh: "失去了谁，世界也不会停下来等你。它照样要你站起来，往前走。唯一的路，是抓紧一个人，也去做别人可以抓紧的那个人。",
  },
};

/**
 * A Chinese song title in English, written after it in the panel ("降临 – Descent"). A track whose
 * title is already English (mirror, Throne of Glory) has none.
 */
export const SONG_TITLES_EN: Partial<Record<MusicKey, string>> = {
  loading: "Wind Dance", // 风舞
  gate: "Iron Blood, Loyal Heart", // 铁血丹心
  forge: "Swords Like a Dream", // 刀剑如梦
  arena: "Descent", // 降临
  mission: "The Brilliant Adventurer", // 璀璨冒险人
  library: "Becoming Mortal", // 化凡
  steles: "Child of Light", // 光之少年
  scroll: "Boundless", // 浩瀚
  formation: "Heaven's Wrath Awakens", // 天谴觉醒
  abode: "Carefree", // 逍遥
  summit: "Breaking the Cocoon", // 破茧
};

/** The English for this track's Chinese title, or null. */
export function songTitleEn(key: MusicKey): string | null {
  return SONG_TITLES_EN[key] ?? null;
}

/** The owner's note on this track, or null (the instrumentals). */
export function songNote(key: MusicKey): SongNote | null {
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
