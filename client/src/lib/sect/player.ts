/**
 * The choices behind /music, the soundtrack's own page (app/music): which songs it lists, what Next
 * and Previous do, what follows a song's end, how a time is written and which keys do what. Pure
 * functions with plain inputs; the audio side is app/music/song-player.ts and the page
 * app/music/music-player.tsx. docs/music/music-page.md describes the page.
 */
import { MUSIC_KEYS, isMusicKey, type MusicKey, type MusicManifest } from "./music";
import { volumeGain } from "./volume";

/** The songs the page lists: the manifest's, in the order the flight plays them. */
export function songList(manifest: MusicManifest | null): MusicKey[] {
  if (!manifest) return [];
  return MUSIC_KEYS.filter((key) => manifest.tracks[key] !== undefined);
}

/** The song one step along the list, round the ends. Null for an empty list. */
export function stepSong(list: readonly MusicKey[], current: MusicKey | null, dir: 1 | -1): MusicKey | null {
  if (list.length === 0) return null;
  const i = current === null ? -1 : list.indexOf(current);
  if (i < 0) return dir > 0 ? list[0] : list[list.length - 1];
  return list[(i + dir + list.length) % list.length];
}

/** Previous goes back to the song's own start once it has played this long, else to the song before. */
export const RESTART_AFTER_SECONDS = 3;

export function previousRestarts(position: number): boolean {
  return position > RESTART_AFTER_SECONDS;
}

/** What plays when a song ends: itself with Repeat on, else the next one (the last leads to the first). */
export function afterEnd(list: readonly MusicKey[], current: MusicKey | null, repeat: boolean): MusicKey | null {
  if (repeat && current !== null && list.includes(current)) return current;
  return stepSong(list, current, 1);
}

/** The song a URL hash names (/music#arena), when the list has it. */
export function songFromHash(hash: string, list: readonly MusicKey[]): MusicKey | null {
  const id = hash.replace(/^#/, "");
  return isMusicKey(id) && list.includes(id) ? id : null;
}

/** A time as the page writes it: minutes and two-digit seconds (4:07). Nonsense is 0:00. */
export function clock(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

/** A time as a screen reader says it ("1 minute 5 seconds of 3 minutes 59 seconds"). */
export function clockWords(seconds: number): string {
  const whole = Number.isFinite(seconds) && seconds > 0 ? Math.floor(seconds) : 0;
  const m = Math.floor(whole / 60);
  const s = whole % 60;
  const parts: string[] = [];
  if (m > 0) parts.push(`${m} minute${m === 1 ? "" : "s"}`);
  if (s > 0 || m === 0) parts.push(`${s} second${s === 1 ? "" : "s"}`);
  return parts.join(" ");
}

/** A place in the song kept inside it. Without a known length only the start is safe. */
export function clampSeek(time: number, duration: number): number {
  if (!Number.isFinite(time) || time <= 0) return 0;
  if (!Number.isFinite(duration) || duration <= 0) return 0;
  return Math.min(time, duration);
}

/** How far the arrow keys move through a song. */
export const SEEK_STEP_SECONDS = 5;

export type PlayerCommand = "toggle" | "back" | "forward" | "mute";

/**
 * The page's keys: Space plays and pauses, the left and right arrows move five seconds, M mutes.
 * None while a control has the key (`onControl`: a button's own Space, a slider's own arrows), nor
 * with Ctrl, Alt or the command key held (those are the browser's).
 */
export function playerCommand(e: { key: string; ctrlKey?: boolean; altKey?: boolean; metaKey?: boolean }, onControl: boolean): PlayerCommand | null {
  if (onControl || e.ctrlKey || e.altKey || e.metaKey) return null;
  switch (e.key) {
    case " ":
    case "Spacebar":
      return "toggle";
    case "ArrowLeft":
      return "back";
    case "ArrowRight":
      return "forward";
    case "m":
    case "M":
      return "mute";
    default:
      return null;
  }
}

/**
 * A tenth of a second of silence as a WAV data URL (8-bit mono, 8 kHz). Phones let a page start
 * sound only inside a tap, and a song arrives seconds after it: the tap plays this, and the element
 * may then start the song by itself (app/music/song-player.ts).
 */
export function silentClip(): string {
  const samples = 800;
  const bytes = new Uint8Array(44 + samples);
  const view = new DataView(bytes.buffer);
  const text = (at: number, s: string) => {
    for (let i = 0; i < s.length; i++) bytes[at + i] = s.charCodeAt(i);
  };
  text(0, "RIFF");
  view.setUint32(4, 36 + samples, true);
  text(8, "WAVEfmt ");
  view.setUint32(16, 16, true); // The format chunk's size.
  view.setUint16(20, 1, true); // PCM.
  view.setUint16(22, 1, true); // One channel.
  view.setUint32(24, 8000, true); // Samples a second.
  view.setUint32(28, 8000, true); // Bytes a second.
  view.setUint16(32, 1, true); // Bytes a sample frame.
  view.setUint16(34, 8, true); // Bits a sample.
  text(36, "data");
  view.setUint32(40, samples, true);
  bytes.fill(128, 44); // 8-bit silence sits at the middle.
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return `data:audio/wav;base64,${btoa(binary)}`;
}

/**
 * The audio element's volume for the slider's share: its square (volume.ts), so the steps sound
 * even. The flight plays its music under the scene at half of this (music.ts MASTER_GAIN); here the
 * song is the point, so 100% is the file's own level.
 */
export function elementVolume(share: number): number {
  return volumeGain(share);
}
