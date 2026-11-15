/**
 * A queue for downloads that share the line (app/sect/experience/live.tsx: live light's maps). At
 * most `limit` hold a place at once; the rest wait their turn, higher priority first, then first
 * come first served. A place is held from acquire until its release is called, so the caller
 * decides when its download is over (its bytes are here, it failed or it was aborted). A waiter
 * whose signal aborts leaves the queue without ever taking a place.
 *
 * Pure: no timers, no network, no three.js.
 */

/** One request for a place. */
export interface FetchGateRequest {
  /** Higher goes first (the stop at the camera before maps loaded ahead). */
  priority: number;
  /** Aborted while waiting, the request leaves the queue and its acquire rejects with an AbortError. */
  signal?: AbortSignal;
}

export interface FetchGate {
  /**
   * Resolves, once a place is free and it is this request's turn, to the function that gives the
   * place back (calling it again does nothing). Rejects with an AbortError when the signal aborts
   * first, or was aborted already. An abort after the place was given changes nothing here: the
   * holder releases it when its download stops.
   */
  acquire(req: FetchGateRequest): Promise<() => void>;
  /** Places held now. */
  readonly running: number;
  /** Requests waiting for a place now. */
  readonly waiting: number;
  /** The most places held at once so far. */
  readonly peak: number;
}

/** The error an aborted wait reports: the signal's own reason when that is an AbortError, else a new one. */
export function abortError(signal?: AbortSignal): Error {
  const r: unknown = signal?.reason;
  if (typeof r === "object" && r !== null && (r as { name?: unknown }).name === "AbortError") return r as Error;
  return new DOMException("The download was aborted.", "AbortError");
}

/** A queue with `limit` places (at least one: with none nothing would ever run). */
export function createFetchGate(limit: number): FetchGate {
  const places = Math.max(1, Math.floor(limit) || 1);
  /** Waiting, in the order they get a place: by priority, then by arrival. */
  const queue: { priority: number; grant: () => void }[] = [];
  let running = 0;
  let peak = 0;

  const take = (): (() => void) => {
    running++;
    peak = Math.max(peak, running);
    let open = true;
    return () => {
      if (!open) return;
      open = false;
      running--;
      while (running < places && queue.length > 0) queue.shift()?.grant();
    };
  };

  return {
    acquire({ priority, signal }) {
      if (signal?.aborted) return Promise.reject(abortError(signal));
      if (running < places && queue.length === 0) return Promise.resolve(take());
      return new Promise<() => void>((resolve, reject) => {
        const onAbort = () => {
          const i = queue.indexOf(waiter);
          if (i >= 0) queue.splice(i, 1);
          reject(abortError(signal));
        };
        const waiter = {
          priority,
          grant: () => {
            signal?.removeEventListener("abort", onAbort);
            resolve(take());
          },
        };
        signal?.addEventListener("abort", onAbort, { once: true });
        // After every waiter of the same or a higher priority.
        let at = queue.length;
        while (at > 0 && queue[at - 1].priority < priority) at--;
        queue.splice(at, 0, waiter);
      });
    },
    get running() {
      return running;
    },
    get waiting() {
      return queue.length;
    },
    get peak() {
      return peak;
    },
  };
}
