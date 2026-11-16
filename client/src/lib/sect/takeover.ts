/**
 * When the visitor's own input takes over from a flight or a snap glide, and when it does not.
 * Any wheel turn or finger down used to end a flight at once (sect-experience.tsx puts the scroll
 * where the camera coasts to: snap.ts coastTarget). Two kinds of input are not the visitor taking
 * over, and stranded the camera between two scenes:
 * - the tail of a trackpad flick: the browser keeps sending wheel events for a second or so after
 *   the fingers leave the pad (momentum), and a flight started meanwhile (a key, the rail) was
 *   ended by them at once;
 * - a tap on a touch screen, which is not a scroll at all.
 * Small state machines with no DOM in them: sect-experience.tsx feeds them its events.
 */

/**
 * The wheel stream. Wheel events closer together than `gapMs` are one stream (a flick and its
 * momentum come about every 16 ms, or 8 ms on a 120 Hz trackpad; a mouse wheel's notches while it
 * spins). The stream's speed is smoothed: each event that turns the page adds its pixels, and what
 * came before fades over `smoothMs`. It starts from the real spacing between the stream's first two
 * events. Inside a tail, a smoothed speed at least `rise` times the lowest since the tail began, and
 * at least `risePx` per frame more than it, is a new push by the visitor, not momentum (momentum
 * only dies away).
 */
export const WHEEL_TAIL = {
  /**
   * Below SNAP.restMs (180 ms), so a snap glide, which starts only once the visitor's scrolling has
   * rested that long, never begins inside a stream: the next wheel event after one begins is a new
   * stream and takes over.
   */
  gapMs: 120,
  /**
   * The spacing a stream's first event is taken to have come at (a 120 Hz trackpad's), since no
   * event came before it. The second event replaces that guess with the real spacing. Also the
   * shortest spacing the second event is timed over, so two events stamped almost together do not
   * read as a burst.
   */
  minMs: 8,
  /**
   * How long the smoothed speed remembers (ms). Long enough that events merged over a long frame, an
   * uneven gap or a sideways event do not move it much: seven events merged into one (112 ms) on
   * steady momentum still stay tail, where at 48 ms or less they read as a push. Short enough that
   * a real push shows: one about 3 times the momentum's pixels per event (steady momentum) to 5
   * times (a flick fading 12% a frame) ends the tail within 48 ms. The smoothed speed lags momentum
   * that fades fast, which is why the push must be bigger there.
   */
  smoothMs: 60,
  /** One frame: `risePx` is pixels per frame. */
  frameMs: 16,
  rise: 2,
  risePx: 8,
  /**
   * How long after a wheel event the browser may still be scrolling the page for it. Chrome eases a
   * mouse wheel's turn in over 100 to 200 ms (its smooth scrolling) and Edge over up to 500 ms, and
   * that easing carries on from wherever the page puts the scroll meanwhile. A scroll the page did
   * not make inside this window can be that easing, not new input (wheelSettling).
   */
  settleMs: 600,
} as const;

/**
 * The smoothed speed of events of 1 px every `ms`, once settled, is 1 / steadyMs(ms). A speed set to
 * px / steadyMs(ms) stays put while events of that size keep coming at that spacing.
 */
const steadyMs = (ms: number) => WHEEL_TAIL.smoothMs * (1 - Math.exp(-ms / WHEEL_TAIL.smoothMs));

/** A stream's first event (and the first after a turn) starts the speed as if it came `minMs` after another. */
const START_MS = steadyMs(WHEEL_TAIL.minMs);

export interface WheelTailState {
  /** The last wheel event's time (ms), of any kind, or null before the first. */
  lastMs: number | null;
  /**
   * When the page handled that event (ms), or null before the first. The event's own time can be a
   * long frame older, and the scroll it causes only comes after the page has handled it.
   */
  seenMs: number | null;
  /** The stream's smoothed speed (page pixels per ms) as of `rateMs`; 0 before its first. */
  rate: number;
  /** The time (ms) of the last wheel event that turned the page. */
  rateMs: number;
  /** The way the last event that turned the page went (1 or -1), or 0 before the stream's first. */
  dir: number;
  /** Events that turned the page this way since the stream began or last turned, counted up to 2. */
  seen: number;
  /** The lowest smoothed speed since the tail began. */
  low: number;
  /**
   * A flight or a gathering far jump was on at the last wheel event, or after the visitor's last
   * other input (endWheelTail).
   */
  busy: boolean;
  /** The wheel events now are momentum left over from before a flight began. */
  tail: boolean;
}

export function createWheelTail(): WheelTailState {
  return { lastMs: null, seenMs: null, rate: 0, rateMs: 0, dir: 0, seen: 0, low: 0, busy: false, tail: false };
}

/**
 * One wheel event at `nowMs`, turning `px` page pixels (snap.ts wheelPixels), with a flight or a
 * gathering far jump on (`busy`) or not. True when it is momentum from before the flight began,
 * which must not end it:
 * - a flight that began inside a running stream makes what is left of the stream momentum;
 * - a gap of `gapMs` or more starts a new stream, which is the visitor's again;
 * - so does a turn the other way, or a push that grows (WHEEL_TAIL.rise and risePx);
 * - the tail outlives the flight until the stream ends, so the last of the momentum does not nudge
 *   the camera off the stop it has just reached.
 * A zero turn (a sideways scroll) only keeps the stream going: it says nothing about the push.
 *
 * The push is told by the stream's smoothed speed, not by one event's. One event's speed (its pixels
 * over the time since the event before) read as a push three ways. Chrome merges the wheel events
 * that pile up in a long frame into one, their pixels summed and stamped with the newest one's time.
 * Events come at uneven gaps (a mouse polled every 8 ms, a time stamp a few ms late). A sideways
 * event between two others left the next one timed over a few ms. Smoothed, each event only adds its
 * pixels to a speed that fades over `smoothMs`, so none of these moves it much.
 *
 * The first event of a stream (or after a turn) has nothing before it, so its speed is a guess
 * (`minMs`). The second event's gap is real: the speed is set to the steady speed of events that size
 * at that spacing, so a 60 Hz and a 120 Hz trackpad read the same motion alike. That reset is not
 * tested for a push (the guess before it could be anything); it only lowers the lowest speed.
 * Known limit: a frame of `gapMs` or longer looks like a pause, so the merged event after it starts
 * a new stream and takes over.
 *
 * `seenMs`: when the page handled the event, where that is not the event's own time (wheelSettling).
 */
export function wheelTail(s: WheelTailState, nowMs: number, px: number, busy: boolean, seenMs = nowMs): boolean {
  const abs = Math.abs(px);
  const inStream = s.lastMs !== null && nowMs - s.lastMs < WHEEL_TAIL.gapMs;
  if (!inStream) {
    // A new stream: the visitor's, its speed and way not known yet.
    s.tail = false;
    s.rate = 0;
    s.dir = 0;
    s.seen = 0;
  }
  let turned = false;
  let seeded = false;
  if (abs > 0) {
    const dir = Math.sign(px);
    turned = s.dir !== 0 && dir !== s.dir;
    // A time stamp earlier than the last counts as the same time.
    const sinceMs = Math.max(0, nowMs - s.rateMs);
    if (dir !== s.dir) {
      // The stream's first event, or the first after a turn: a guess.
      s.rate = abs / START_MS;
      s.seen = 1;
    } else if (s.seen === 1) {
      // The second: the real spacing, within minMs and gapMs.
      s.rate = abs / steadyMs(Math.min(Math.max(sinceMs, WHEEL_TAIL.minMs), WHEEL_TAIL.gapMs));
      s.seen = 2;
      seeded = true;
    } else {
      s.rate = s.rate * Math.exp(-sinceMs / WHEEL_TAIL.smoothMs) + abs / WHEEL_TAIL.smoothMs;
    }
    s.rateMs = nowMs;
    s.dir = dir;
  }
  if (inStream && busy && !s.busy) {
    // A flight began since the last event, inside this stream: the rest of it is momentum.
    s.tail = true;
    s.low = s.rate;
  } else if (s.tail && abs > 0) {
    const push =
      !seeded && s.rate >= s.low * WHEEL_TAIL.rise && (s.rate - s.low) * WHEEL_TAIL.frameMs >= WHEEL_TAIL.risePx;
    if (turned || push) s.tail = false;
    else s.low = Math.min(s.low, s.rate);
  }
  s.lastMs = nowMs;
  s.seenMs = seenMs;
  s.busy = busy;
  return s.tail;
}

/**
 * A scroll the page did not make, at `nowMs`, with a flight or a gathering far jump on (`busy`) or
 * not. True when it is the browser still scrolling the page for wheel events that are not the
 * visitor taking over, so the page puts the scroll back:
 * - the tail's own events, where the browser would not let the page cancel them. As the tail does,
 *   this outlives the flight;
 * - events from before the flight began, with no wheel event since. Chrome eases a mouse wheel's
 *   turn in over several frames. A key pressed meanwhile started a flight, and what was left of that
 *   easing ended it at once, as the visitor's own scroll would, before the stream's next event could
 *   make it a tail.
 * Only within `settleMs` of the last wheel event the page handled. Any wheel event that is not tail
 * takes over before its scroll lands, and Space or a finger down end this as they end the tail
 * (endWheelTail), so their scrolls stay the visitor's.
 */
export function wheelSettling(s: WheelTailState, nowMs: number, busy: boolean): boolean {
  if (s.seenMs === null || nowMs - s.seenMs >= WHEEL_TAIL.settleMs) return false;
  return s.tail || (busy && !s.busy);
}

/**
 * The visitor's own input that is not a wheel event (Space, a finger down) ends a tail: the rest of
 * the stream is theirs, as with no flight, until a flight begins inside it again. `busy`: a flight or
 * a gathering far jump still on once that input has ended what it ends, so that one begun after it
 * counts as begun inside the stream.
 */
export function endWheelTail(s: WheelTailState, busy: boolean): void {
  s.tail = false;
  s.busy = busy;
}

// --- touch -----------------------------------------------------------------------------------------

/** A flight a finger ended: where it was going, what was to run on arrival, and `moves` then. */
export interface EndedFlight {
  toU: number;
  onArrive?: () => void;
  moves: number;
}

/**
 * A finger down still ends a flight at once (a drag then takes over cleanly), but a tap lets it
 * carry on: the page remembers what the touch ended and whether the page scrolled under the finger.
 */
export interface TouchTakeover {
  /** Fingers down now. */
  fingers: number;
  /** The flight this touch ended, or null. */
  ended: EndedFlight | null;
  /** The page scrolled under the finger since the first one went down. */
  scrolled: boolean;
}

export function createTouchTakeover(): TouchTakeover {
  return { fingers: 0, ended: null, scrolled: false };
}

/**
 * A finger went down, `fingers` now down (TouchEvent.touches). `ended`: the flight it ended, or
 * null (none on, or one under a reader or the map, which the page leaves to carry on by itself).
 * The first finger starts a new touch; the latest flight a touch ended is the one it remembers.
 */
export function touchDown(s: TouchTakeover, fingers: number, ended: EndedFlight | null): void {
  if (s.fingers === 0 || fingers <= 1) {
    s.ended = null;
    s.scrolled = false;
  }
  s.fingers = fingers;
  if (ended) s.ended = ended;
}

/**
 * The page scrolled, not by its own hand. Under a finger that is the visitor dragging: true the
 * first time in a touch (a far jump still gathering gives way to it then, as to any scroll).
 */
export function touchScrolled(s: TouchTakeover): boolean {
  if (s.fingers === 0 || s.scrolled) return false;
  s.scrolled = true;
  return true;
}

/**
 * A finger lifted, `fingers` still down. Once the last one is up: the flight to carry on with, when
 * this touch ended one, the page did not scroll under it (a tap, or a drag to look around), nothing
 * is flying or gathering now (`busy`) and nothing newer has begun since (`moves`: the page's count
 * of flights, glides and far jumps begun); else null.
 */
export function touchUp(s: TouchTakeover, fingers: number, now: { busy: boolean; moves: number }): EndedFlight | null {
  s.fingers = Math.max(0, fingers);
  if (s.fingers > 0) return null;
  const e = s.ended;
  const scrolled = s.scrolled;
  s.ended = null;
  s.scrolled = false;
  if (!e || scrolled || now.busy || now.moves !== e.moves) return null;
  return e;
}
