/**
 * Free look's one hint ("Swipe to look around", app/sect/experience/overlay.tsx LookHint): how long
 * it stays up, and when it stays away for good.
 *
 * It retires after the visitor's first real turn of the view (a drag or a swipe). On a phone it
 * also retires once it has shown on two visits, turned or not, and each showing lasts about 11
 * seconds; on wider screens only a turn retires it, and it stays 25 seconds, as it always has.
 *
 * Remembered per browser in localStorage: "sect.lookHint" is "1" once it has retired (the key and
 * value earlier visits wrote after a turn), and "sect.lookHint.shown" counts a phone's showings.
 * Storage that is blocked or holds nonsense counts as nothing shown; a write that fails lasts for
 * this visit only.
 *
 * Pure: no React, no DOM.
 */

/** localStorage key: "1" once the hint has retired. */
export const LOOK_HINT_KEY = "sect.lookHint";

/** localStorage key: how many visits have shown the hint on a phone. */
export const LOOK_HINT_SHOWN_KEY = "sect.lookHint.shown";

/** On a phone the hint retires after this many showings. */
export const LOOK_HINT_SHOWS = 2;

/** How long the hint stays up each time, unless a turn retires it sooner. */
export const LOOK_HINT_MS = { phone: 11000, wide: 25000 } as const;

/** The hint has retired on this browser (a turn, or its last showing on a phone). */
export function lookHintRetired(storage: Pick<Storage, "getItem"> | null): boolean {
  try {
    return storage?.getItem(LOOK_HINT_KEY) === "1";
  } catch {
    return false;
  }
}

/** The visitor turned the view: the hint stays away from now on. */
export function retireLookHint(storage: Pick<Storage, "setItem"> | null): void {
  try {
    storage?.setItem(LOOK_HINT_KEY, "1");
  } catch {
    // Storage blocked (a private window): it just shows again next visit.
  }
}

/** How many visits have shown the hint on a phone (0 for none, junk or blocked storage). */
export function lookHintShows(storage: Pick<Storage, "getItem"> | null): number {
  try {
    const v = storage?.getItem(LOOK_HINT_SHOWN_KEY) ?? null;
    if (v === null || !/^\d+$/.test(v)) return 0;
    return Number(v);
  } catch {
    return 0;
  }
}

/**
 * A phone has shown the hint once more (once a visit): counted, and on its LOOK_HINT_SHOWS-th
 * showing it retires. That showing still runs its course.
 */
export function countLookHintShown(storage: Pick<Storage, "getItem" | "setItem"> | null): void {
  const shown = lookHintShows(storage) + 1;
  try {
    storage?.setItem(LOOK_HINT_SHOWN_KEY, String(shown));
  } catch {
    // Storage blocked: nothing is counted, as nothing is remembered.
    return;
  }
  if (shown >= LOOK_HINT_SHOWS) retireLookHint(storage);
}
