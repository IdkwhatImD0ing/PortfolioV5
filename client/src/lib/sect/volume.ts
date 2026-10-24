/**
 * The music's volume: the slider beside the sound toggle (app/sect/experience/sound-toggle.tsx).
 *
 * The slider is the master. It sets a share, 0 to 1, of the music's full level (music.ts
 * MASTER_GAIN), and everything else multiplies it: the ducking under a voice call (VOICE_DUCK) takes
 * a share of whatever the slider gives, and a YouTube demo, the page view or the mute toggle still
 * silence it. 100% is the level the music always had, and the default.
 *
 * The slider counts in whole percent; the engine takes the share. Its gain follows the square of the
 * share, so equal steps sound like equal steps: half way is about -12 dB, not the barely quieter -6
 * dB a straight line gives.
 *
 * Remembered per visitor in localStorage ("sect.music.volume", whole percent). Storage that is
 * blocked or holds nonsense gives the default; a write that fails lasts for this visit only.
 *
 * Pure: no React, no Web Audio.
 */

/** localStorage key of the visitor's volume, in whole percent ("0" to "100"). */
export const VOLUME_KEY = "sect.music.volume";

/** The share a visitor starts at: the music's own level. */
export const DEFAULT_VOLUME = 1;

/** The slider's step in percent: the arrow keys move it this much (Page Up/Down and Home/End too). */
export const VOLUME_STEP = 5;

/** A share in [0, 1]; anything not a finite number is the default. */
export function clampVolume(v: number): number {
  if (!Number.isFinite(v)) return DEFAULT_VOLUME;
  return Math.min(1, Math.max(0, v));
}

/** The slider's whole percent for a share. */
export function volumePercent(v: number): number {
  return Math.round(clampVolume(v) * 100);
}

/** The share for the slider's percent (a string, as an input's value is, or a number). */
export function volumeFromPercent(p: number | string): number {
  const n = typeof p === "string" ? Number.parseFloat(p) : p;
  if (!Number.isFinite(n)) return DEFAULT_VOLUME;
  return clampVolume(Math.round(n) / 100);
}

/** What the music's gain is multiplied by for a share: its square, so the steps sound even. */
export function volumeGain(v: number): number {
  const c = clampVolume(v);
  return c * c;
}

/** The slider's value as a screen reader says it, and as its visible readout shows it. */
export function volumeText(v: number): string {
  return `${volumePercent(v)}%`;
}

/** The visitor's saved volume, else the default (nothing saved, nonsense saved, or storage blocked). */
export function readVolume(storage: Pick<Storage, "getItem"> | null | undefined): number {
  try {
    const raw = storage?.getItem(VOLUME_KEY);
    if (raw === null || raw === undefined || raw.trim() === "") return DEFAULT_VOLUME;
    const n = Number(raw);
    return Number.isFinite(n) ? volumeFromPercent(n) : DEFAULT_VOLUME;
  } catch {
    return DEFAULT_VOLUME;
  }
}

export function writeVolume(storage: Pick<Storage, "setItem"> | null | undefined, v: number): void {
  try {
    storage?.setItem(VOLUME_KEY, String(volumePercent(v)));
  } catch {
    // Storage blocked (a private window): the volume lasts for this visit only.
  }
}
