/**
 * Which streamed chunks the page should hold, load, draw and drop at a camera frame.
 *
 * Every chunk has a `need` range of Blender frames during which it should be drawn, and a `core`:
 * the stretch of the flight that belongs to its area (meta.json areas, else halfway between holds).
 * Around the camera frame there are two windows, both stretched in the direction of travel:
 * - the need window ([frame - behind, frame + ahead]): chunks whose need range touches it are
 *   candidates. They are ranked by how far the camera is from their core (nearest area first) and
 *   taken until `maxResident` chunks or `triBudget` triangles: the backdrop's proxy stands in for
 *   the rest, so wide need ranges (an area seen from far away) cannot blow the budget;
 * - the wider keep window: resident chunks inside it stay while the cap allows, and a resident
 *   chunk ranks `stickiness` frames nearer than it is, so scrolling back and forth over a boundary
 *   does not reload anything (hysteresis). Everything else resident is dropped.
 * Areas the camera has already passed count `behindWeight` times farther, so the next area ahead
 * gets its slot early.
 * While nothing needed is missing (and, with `ready`, everything needed is ready to draw), the next
 * chunk in the direction of travel is prefetched if it would fit, or if a spare slot past the
 * triangle budget is left (`spare`): the page starts prefetches early (desktops while the camera
 * moves, phones while it rests), so the next area is there before the flight reaches it instead of
 * loading mid-flight. A chunk in a spare slot stays until the camera has passed it. "Passed" follows
 * the direction of travel, so the caller should smooth that direction (travelDirection) rather than
 * flip it on every small step back. The spare slot also holds during a jump: the area the camera
 * waits in (or one prefetched ahead) stays rather than being fetched again after the jump.
 *
 * Handing over (`ready`, the chunks drawn-ready): while a chunk the plan needs is not ready to draw
 * yet (loading or uploading), the area nearest the camera that is ready and drawn at this frame
 * stays too, past the cap and the budget (`handover`), so the visitor keeps seeing it instead of
 * the backdrop's proxy until the area it hands over to can be drawn. Then it goes as usual. This
 * covers scrolling into the next area and waiting for a jump alike.
 *
 * Looking back: while the visitor has turned the view round (free look) with the camera at rest, the
 * page passes `lookingBack`. The usual plan stays exactly as it is, and on top of it the nearest
 * area behind the view that it does not already keep takes a slot of its own past `maxResident`
 * and the triangle budget (`lookBack`, desktops only), so what lies behind is the full area and not
 * the backdrop's proxy. "Behind the view" means lower frames (the path camera always faces higher
 * ones), not the direction of travel. When the area just passed is already kept, the slot goes to
 * the one before it (behind the camera is often two areas back, where the path bends). Only an
 * area that would be drawn at this frame (its need range holds it) takes it. Turning forward or
 * moving on drops just that area.
 *
 * A far jump (rail, Places, deep link, voice) passes `target`, the frame the camera is flying to.
 * The plan then needs only the chunk(s) whose core holds the target (the rest streams in after
 * arrival); chunks along the sweep are not requested, and the ones the camera is leaving are kept
 * only while the cap allows.
 *
 * Retaining (desktops with memory to spare, `retainTris` and `retainTexBytes`): once the usual plan
 * (and the look-back slot and the prefetch) is settled, loaded chunks it would drop stay resident,
 * nearest the camera first (or nearest the jump's target, whichever is nearer), while everything
 * resident fits a residency budget of triangles and of texture memory. The first area that does not
 * fit ends the list, so the farthest always go first and a nearer area is never given up for a
 * farther one. Scrolling back to an area kept that way needs no load. Retained chunks take no slot
 * and change nothing in the usual plan; they are drawn by the usual rule (their need range holds the
 * frame), in place of the backdrop's proxy. Only chunks in `loaded` are retained (never one still
 * loading, never one that failed). Off (0) by default.
 *
 * The window around the camera's area (`around`, what the page uses): instead of the nearest areas
 * by frames within a cap and a triangle budget, the plan needs the area the camera is at (the one
 * whose stop is nearest, windowCentreAt) and a fixed number of areas before and after it in flight
 * order (two each side on desktops: the owner's rule that the place on screen and its neighbours are
 * always the full meshes and textures, never the backdrop's stand-ins), clamped at the flight's ends,
 * nearest first. On top of it:
 * - the spare slots: the next areas past the window in the direction of travel, prefetched once the
 *   window is in and kept, so crossing into the next area finds its new far neighbour loaded;
 * - hysteresis: a held area the window reached `stickiness` frames back or ahead stays, so scrolling
 *   to and fro over the line between two areas (halfway between their stops, at least 51 frames from
 *   either on the shipped flight, so a camera resting at a stop is clear of it) loads and drops
 *   nothing;
 * - a jump needs only the area it lands in (the rest of its window streams in once it is there),
 *   and keeps what is held of the destination's window, then of the camera's, up to the window's
 *   size plus the spare slots.
 * Handing over, looking back and retaining apply as above.
 *
 * Pure: plain inputs, no timers, no three.js.
 */

export interface ChunkSpan {
  id: string;
  need: readonly [number, number];
  /** The area's own frame range (ranking); the need range when absent. */
  core?: readonly [number, number];
  /**
   * The frame of the area's stop (its hold), when it has one: the window around the camera's area
   * (PlanWindow.around) is centred on the nearest stop, so the line between two areas falls halfway
   * between their stops rather than at the edge of a stretch, which can lie a few frames from a stop.
   */
  hold?: number;
  /** Triangles (0 or absent: unknown, counts as nothing against the budget). */
  tris?: number;
  /**
   * Texture memory the chunk will take on the GPU, in bytes, estimated before it loads (the
   * residency budget counts chunks still to load with this; loaded ones with what was measured,
   * PlanInput.loaded). Absent: nothing.
   */
  texBytes?: number;
}

/** What a loaded chunk holds, as measured once it has loaded (PlanInput.loaded). */
export interface ChunkCost {
  tris: number;
  /** GPU texture memory in bytes (every mip level). */
  texBytes: number;
}

export interface PlanWindow {
  /** Frames behind the camera (against the direction of travel) a chunk must be resident for. */
  behind: number;
  /** Frames ahead of the camera a chunk must be resident for. */
  ahead: number;
  keepBehind: number;
  keepAhead: number;
  /** Most chunks resident at once. */
  maxResident: number;
  /**
   * Most chunk triangles resident at once. The nearest `minResident` chunks are always allowed
   * (the area the camera is in and the next one), so the budget never makes an area pop in late;
   * it limits the extra ones.
   */
  triBudget: number;
  minResident: number;
  /** A resident chunk ranks this many frames nearer than it is (no thrash at boundaries). */
  stickiness: number;
  /**
   * An area the camera has already passed (in the direction of travel) counts this many times
   * farther than it is, so the next area takes its slot early.
   */
  behindWeight: number;
  /** A resident chunk is drawn while the frame is within this many frames of its need range. */
  drawMargin: number;
  /**
   * Chunks still ahead in the direction of travel that may go past the triangle budget (never past
   * maxResident): the next area is prefetched even when it does not fit, and kept until the camera
   * has passed it, so it does not load mid-flight. During a jump the slot keeps an area the camera
   * has not passed (where it waits) instead. 0 makes the budget a hard limit.
   */
  spare: number;
  /**
   * Areas kept past the cap and the budget while a needed chunk is not ready (PlanInput.ready): the
   * ones nearest the camera that are ready and drawn at this frame. Without `ready`, none.
   */
  handover: number;
  /**
   * Extra slots, past maxResident and the triangle budget, for the area behind the view while the
   * visitor looks back at rest (PlanInput.lookingBack). The usual plan stays as it is; these slots
   * come on top. 0 where the budget is a hard memory limit (phones).
   */
  lookBack: number;
  /**
   * Residency budget for retaining: loaded chunks no window wants any more stay while all the
   * chunks kept (the usual plan, the chunks still to load and the prefetch included) hold at most
   * this many triangles and `retainTexBytes` bytes of GPU texture memory. Either at 0 turns
   * retaining off (the default: phones, the mid tier and the plain desktop budget).
   */
  retainTris: number;
  retainTexBytes: number;
  /**
   * The window around the camera's area: how many areas before (`behind`) and after (`ahead`) the
   * one the camera is at (windowCentreAt), in flight order, are needed (clamped at the ends). Null: the nearest areas
   * by frames, within maxResident and triBudget. With it, maxResident, triBudget, minResident and
   * the frame windows (behind, ahead, keepBehind, keepAhead) do not limit the plan; `spare` slots
   * hold the next areas past it in the direction of travel.
   */
  around: AreaWindow | null;
}

/** Areas before and after the camera's own in flight order (PlanWindow.around). */
export interface AreaWindow {
  behind: number;
  ahead: number;
}

export const DEFAULT_WINDOW: PlanWindow = {
  behind: 24,
  ahead: 96,
  keepBehind: 180,
  keepAhead: 260,
  maxResident: 3,
  triBudget: Infinity,
  minResident: 2,
  stickiness: 40,
  behindWeight: 3,
  drawMargin: 0,
  spare: 0,
  handover: 1,
  lookBack: 0,
  retainTris: 0,
  retainTexBytes: 0,
  around: null,
};

export interface PlanInput {
  /** Chunks in flight order. */
  chunks: readonly ChunkSpan[];
  frame: number;
  /** 1 forward, -1 backward, 0 at rest (treated as forward). */
  direction: number;
  /** Chunks loaded (ready or uploading). */
  resident: ReadonlySet<string>;
  /** Chunks being fetched or prepared. */
  loading: ReadonlySet<string>;
  /** Destination frame of a far jump, or null. */
  target?: number | null;
  /**
   * The view is turned round (free look past 90 degrees) and the camera is at rest: on top of the
   * usual plan, the nearest area behind the view may take a `lookBack` slot. Ignored during a jump.
   */
  lookingBack?: boolean;
  /**
   * Chunks fully loaded (in `resident`, but not ones that failed), with what each holds as measured
   * on load. Only these may be retained (PlanWindow.retainTris); the measured cost also replaces the
   * span's estimate in the residency budget.
   */
  loaded?: ReadonlyMap<string, ChunkCost>;
  /**
   * Resident chunks ready to draw (textures uploaded, shaders compiled), and chunks given up on
   * (failed: nothing to wait for). With it, the plan hands over (PlanWindow.handover) and prefetches
   * only once everything needed is ready; without it, both go by `resident` alone.
   */
  ready?: ReadonlySet<string>;
  window?: Partial<PlanWindow>;
}

export interface ChunkPlan {
  /** Chunks that must be resident now, nearest first. */
  need: string[];
  /** Needed chunks that are neither resident nor loading: start these, in order. */
  load: string[];
  /** One chunk to fetch while nothing needed is missing, or null. */
  prefetch: string | null;
  /** Resident chunks to keep (the retained ones included). */
  keep: string[];
  /**
   * Resident chunks kept only by the residency budget (PlanWindow.retainTris): loaded areas the
   * usual plan would drop, nearest first. Empty unless retaining is on.
   */
  retain: string[];
  /**
   * Resident chunks kept only because a needed one is not ready yet (PlanWindow.handover): drawn
   * until it is. Empty without PlanInput.ready.
   */
  handover: string[];
  /** Resident chunks to dispose. */
  drop: string[];
  /** Resident chunks to draw at this frame. */
  draw: string[];
  /** Loading chunks no window wants any more (cancel them). */
  cancel: string[];
}

/** Frames between `frame` and the range [a, b] (0 inside it). */
export function gapToRange(frame: number, range: readonly [number, number]): number {
  if (frame < range[0]) return range[0] - frame;
  if (frame > range[1]) return frame - range[1];
  return 0;
}

/** True when [a, b] touches the window that reaches `back` frames behind and `fwd` ahead. */
function touches(range: readonly [number, number], frame: number, dir: number, back: number, fwd: number): boolean {
  const lo = dir < 0 ? frame - fwd : frame - back;
  const hi = dir < 0 ? frame + back : frame + fwd;
  return range[1] >= lo && range[0] <= hi;
}

/**
 * Each hold's stretch of the flight, for chunks without an area range: from halfway after the
 * previous hold to halfway before the next one (the first and last reach the ends).
 */
export function holdCores(holds: readonly { id: string; frame: number }[], frameStart: number, frameEnd: number): Map<string, [number, number]> {
  const sorted = [...holds].sort((a, b) => a.frame - b.frame);
  const out = new Map<string, [number, number]>();
  sorted.forEach((h, i) => {
    const lo = i === 0 ? frameStart : Math.floor((sorted[i - 1].frame + h.frame) / 2) + 1;
    const hi = i === sorted.length - 1 ? frameEnd : Math.floor((h.frame + sorted[i + 1].frame) / 2);
    out.set(h.id, [lo, hi]);
  });
  return out;
}

/** The direction of travel and the farthest frame reached going that way (travelDirection). */
export interface Travel {
  /** 1 forward, -1 backward. */
  direction: number;
  extreme: number;
}

/**
 * The direction of travel for the planner, with hysteresis: it turns only once the camera has come
 * back more than `turn` frames from the farthest frame it reached. A small correction (an overshoot
 * at a stop scrolled back) then keeps the windows facing the same way, so the area prefetched into
 * the spare slot is not dropped as "passed" and nothing ahead is lost. Use `turn` = the window's
 * `behind`: until the turn, the camera stays inside the stretch the forward plan already covered.
 */
export function travelDirection(prev: Travel | null, frame: number, turn: number): Travel {
  if (prev === null || !Number.isFinite(prev.extreme)) return { direction: prev?.direction ?? 1, extreme: frame };
  const dir = prev.direction < 0 ? -1 : 1;
  if (dir > 0 ? frame >= prev.extreme : frame <= prev.extreme) return { direction: dir, extreme: frame };
  if (Math.abs(frame - prev.extreme) > turn) return { direction: -dir, extreme: frame };
  return { direction: dir, extreme: prev.extreme };
}

/**
 * The area whose own stretch (`cores`, in flight order) holds `frame`, else the nearest one: its
 * index in `cores`, or -1 when there are none.
 */
export function areaIndexAt(cores: readonly (readonly [number, number])[], frame: number): number {
  let best = -1;
  let bestGap = Infinity;
  cores.forEach((c, i) => {
    const g = gapToRange(frame, c);
    if (g < bestGap) {
      bestGap = g;
      best = i;
    }
  });
  return best;
}

/**
 * The area the window around the camera is centred on (PlanWindow.around), as an index into `chunks`
 * (in flight order): the one whose stop is nearest `frame`, or, for chunks without a stop, whose own
 * stretch holds it or is nearest. -1 without chunks.
 */
export function windowCentreAt(chunks: readonly ChunkSpan[], frame: number): number {
  return areaIndexAt(
    chunks.map((c) => (c.hold !== undefined ? ([c.hold, c.hold] as const) : (c.core ?? c.need))),
    frame,
  );
}

/**
 * The direction of travel once a far jump has landed (the rail, Places, a deep link, voice): the
 * flight back left the planner facing backward, so a phone resting there prefetched the area behind
 * it, though a visitor reads on from where a jump lands. A jump back past more than the area just
 * before faces forward again (the next area ahead is prefetched). A step back to the area just before
 * (K, the previous stop) keeps facing back, so stepping back stop by stop still fetches the way it
 * goes; a jump forward keeps facing forward. `from` and `to` are where the jump started and the frame
 * it went to, `frame` where it landed; `cores` the areas' own stretches in flight order.
 */
export function travelAfterJump(travel: Travel, from: number, to: number, frame: number, cores: readonly (readonly [number, number])[]): Travel {
  if (to >= from || travel.direction > 0) return travel;
  if (areaIndexAt(cores, from) - areaIndexAt(cores, to) <= 1) return travel;
  return { direction: 1, extreme: frame };
}

/** A jump under way for travelAfterJump: the frame it counts from and the frame it goes to. */
export interface JumpLeg {
  from: number;
  to: number;
}

/**
 * The jump under way once the destination is `target` (the camera at `frame`). A new jump counts
 * from the camera. A new destination one area before the old one (K pressed again during the flight:
 * it steps on from the flight's end) counts from the old destination, so quick K presses stay steps
 * back of one area each; any other new destination (another stop picked on the rail) keeps counting
 * from where the jump started.
 */
export function jumpLeg(prev: JumpLeg | null, frame: number, target: number, cores: readonly (readonly [number, number])[]): JumpLeg {
  if (!prev) return { from: frame, to: target };
  if (prev.to === target) return prev;
  const step = areaIndexAt(cores, prev.to) - areaIndexAt(cores, target) === 1;
  return { from: step ? prev.to : prev.from, to: target };
}

export function planChunks(input: PlanInput): ChunkPlan {
  const w: PlanWindow = { ...DEFAULT_WINDOW, ...input.window };
  const { chunks, frame, resident, loading } = input;
  const dir = input.direction < 0 ? -1 : 1;
  const target = input.target ?? null;
  const at = target ?? frame;
  const order = new Map(chunks.map((c, i) => [c.id, i]));
  const byId = new Map(chunks.map((c) => [c.id, c]));
  const core = (c: ChunkSpan) => c.core ?? c.need;
  const gap = (c: ChunkSpan, f = at) => gapToRange(f, core(c));
  const held = (id: string) => resident.has(id) || loading.has(id);
  const passed = (c: ChunkSpan, f: number) => (dir > 0 ? core(c)[1] < f : core(c)[0] > f);
  const rank = (c: ChunkSpan, f = at) => {
    const g = gap(c, f) * (target === null && passed(c, f) ? w.behindWeight : 1);
    return held(c.id) ? Math.max(0, g - w.stickiness) : g;
  };
  const sortBy = (f: number) => (a: ChunkSpan, b: ChunkSpan) => rank(a, f) - rank(b, f) || (order.get(a.id) ?? 0) - (order.get(b.id) ?? 0);
  /** Nearest the frame `f` first (by the gap to the area's own stretch), then in flight order. */
  const byGap = (f: number) => (a: ChunkSpan, b: ChunkSpan) => gap(a, f) - gap(b, f) || (order.get(a.id) ?? 0) - (order.get(b.id) ?? 0);
  const tris = (id: string) => byId.get(id)?.tris ?? 0;

  // What must be resident (`need`, nearest first) and what the usual plan keeps (`keepSet`), the
  // most chunks the usual plan holds (`cap`, a prefetch must fit under it) and the chunks a prefetch
  // may take, nearest first (`ahead`, asked once the look-back slot below is settled).
  const keepSet = new Set<string>();
  let need: string[];
  let cap: number;
  let ahead: () => ChunkSpan[];

  if (w.around) {
    // The area the camera is in (or a jump lands in) and its neighbours in flight order.
    const around = w.around;
    const cores = chunks.map(core);
    const windowAt = (f: number): [number, number] => {
      const i = windowCentreAt(chunks, f);
      return [Math.max(0, i - around.behind), Math.min(chunks.length - 1, i + around.ahead)];
    };
    const inside = (i: number, r: readonly [number, number]) => i >= r[0] && i <= r[1];
    /** The spare slots past a window: the next areas in the direction of travel, nearest first. */
    const beyond = (r: readonly [number, number]) => {
      const out: ChunkSpan[] = [];
      for (let k = 1; k <= w.spare; k++) {
        const c = chunks[dir > 0 ? r[1] + k : r[0] - k];
        if (c) out.push(c);
      }
      return out;
    };
    const span = windowAt(at);
    const areas = chunks.filter((_, i) => inside(i, span));
    cap = areas.length + w.spare;
    if (target !== null) {
      // A jump needs only the area it lands in; the rest of its window streams in once it is there.
      const landing = chunks[areaIndexAt(cores, target)];
      need = landing ? [landing.id] : [];
      for (const id of need) keepSet.add(id);
      // Held areas stay while the cap allows: the destination's window first (nearest the stop),
      // then the camera's and its spare slots (it waits there, and draws them meanwhile).
      const here = windowAt(frame);
      const spare = new Set(beyond(here));
      const stays = [
        ...areas.filter((c) => held(c.id)).sort(byGap(target)),
        ...chunks.filter((c, i) => held(c.id) && (inside(i, here) || spare.has(c))).sort(byGap(frame)),
      ];
      for (const c of stays) {
        if (keepSet.size >= cap) break;
        keepSet.add(c.id);
      }
      ahead = () => [];
    } else {
      need = [...areas].sort(byGap(frame)).map((c) => c.id);
      for (const id of need) keepSet.add(id);
      // Held areas the window reached `stickiness` frames back or ahead stay (no thrash at the line
      // between two areas), and so do the spare slots past it in the direction of travel.
      const sticky: [number, number] = [windowAt(frame - w.stickiness)[0], windowAt(frame + w.stickiness)[1]];
      const spare = beyond(span);
      chunks.forEach((c, i) => {
        if (held(c.id) && (inside(i, sticky) || spare.includes(c))) keepSet.add(c.id);
      });
      ahead = () => spare.filter((c) => !held(c.id) && !keepSet.has(c.id));
    }
  } else {
    // Candidates: around the target for a jump (both ways, it is a stop), else around the camera.
    const eligible = chunks.filter((c) =>
      target !== null ? touches(c.need, target, 1, w.behind, w.behind) : touches(c.need, frame, dir, w.behind, w.ahead),
    );
    eligible.sort(sortBy(at));
    // A jump's landing area (its core holds the target) goes first, even when a held neighbour whose
    // core ends just before the stop ranks as near through stickiness: with a one-area budget the
    // neighbour would otherwise take the only slot and the landing area would never load.
    if (target !== null) eligible.sort((a, b) => Number(gap(a) > 0) - Number(gap(b) > 0));

    // What must be resident: the nearest areas, within the count cap and the triangle budget. A jump
    // gathers only the area it lands in (its core holds the target).
    const needList: string[] = [];
    let needTris = 0;
    for (const c of eligible) {
      if (needList.length >= w.maxResident) break;
      if (needList.length > 0 && target !== null && gap(c) > 0) continue;
      if (needList.length >= w.minResident && needTris + tris(c.id) > w.triBudget) continue;
      needList.push(c.id);
      needTris += tris(c.id);
    }
    const needSet = new Set(needList);
    need = [...needList].sort((a, b) => gap(byId.get(a)!) - gap(byId.get(b)!) || (order.get(a) ?? 0) - (order.get(b) ?? 0));

    // What may stay: needed chunks, then held chunks inside the keep window (around the camera or
    // the target), nearest first, while the cap and the budget allow.
    for (const id of needSet) keepSet.add(id);
    let keepTris = needTris;
    // Spare slots past the budget (window.spare), for an area the camera has not passed: one
    // prefetched ahead, or during a jump the one the camera waits in.
    let spareLeft = w.spare;
    const stay = chunks
      .filter((c) => held(c.id) && !needSet.has(c.id))
      .filter((c) => touches(c.need, frame, dir, w.keepBehind, w.keepAhead) || (target !== null && touches(c.need, target, 1, w.keepBehind, w.keepAhead)))
      .sort(sortBy(frame));
    for (const c of stay) {
      if (keepSet.size >= w.maxResident) break;
      if (keepSet.size >= w.minResident && keepTris + tris(c.id) > w.triBudget) {
        // Over the budget: only a prefetched area the camera has not passed keeps a spare slot.
        if (spareLeft <= 0 || passed(c, frame)) continue;
        spareLeft--;
      }
      keepSet.add(c.id);
      keepTris += tris(c.id);
    }
    cap = w.maxResident;
    const size = keepSet.size;
    // The nearest chunk ahead in the direction of travel that the keep window reaches, when it
    // would fit, or a spare slot is left.
    ahead = () =>
      chunks
        .filter((c) => !held(c.id) && !keepSet.has(c.id))
        .filter((c) => touches(c.need, frame, dir, w.keepBehind, w.keepAhead))
        .filter((c) => !passed(c, frame))
        .filter((c) => size < w.minResident || keepTris + tris(c.id) <= w.triBudget || spareLeft > 0)
        .sort(sortBy(frame));
  }

  // Looking back at rest (desktops): on top of the usual plan, the nearest areas behind the view
  // that are drawn at this frame, past the cap and the budget. The path camera always faces higher
  // frames, so a view turned round looks toward lower ones, whichever way the visitor last
  // scrolled. The usual slots are untouched, so the area ahead stays and nothing reloads when the
  // visitor scrolls on. Phones (lookBack 0) plan exactly as before.
  const usualSize = keepSet.size;
  if (input.lookingBack === true && target === null && w.lookBack > 0) {
    const behindView = chunks
      .filter((c) => core(c)[1] < frame && !keepSet.has(c.id) && gapToRange(frame, c.need) <= w.drawMargin)
      .sort((a, b) => gap(a, frame) - gap(b, frame) || (order.get(b.id) ?? 0) - (order.get(a.id) ?? 0));
    for (const c of behindView.slice(0, w.lookBack)) {
      keepSet.add(c.id);
      need.push(c.id);
    }
  }

  const load = need.filter((id) => !held(id));

  // Prefetch: the nearest chunk ahead in the direction of travel that may come (`ahead`), when
  // nothing needed is missing (nor, with `ready`, still uploading) and the usual plan is under its cap.
  const ready = input.ready;
  let prefetch: string | null = null;
  const missing = need.some((id) => !resident.has(id) || (ready !== undefined && !ready.has(id)));
  if (!missing && target === null && usualSize < cap) prefetch = ahead()[0]?.id ?? null;

  // Retaining (desktops with memory to spare): loaded chunks the plan above would drop stay,
  // nearest first, while everything kept fits the residency budget. Chunks still to load and the
  // prefetch count with their estimates, so the budget holds once they arrive. The first one that
  // does not fit ends the list: the farthest go first, never a nearer one for a farther one.
  const retain: string[] = [];
  const loaded = input.loaded;
  if (loaded && w.retainTris > 0 && w.retainTexBytes > 0) {
    const cost = (id: string): ChunkCost => loaded.get(id) ?? { tris: tris(id), texBytes: byId.get(id)?.texBytes ?? 0 };
    let usedTris = 0;
    let usedTex = 0;
    for (const id of prefetch === null ? keepSet : [...keepSet, prefetch]) {
      const k = cost(id);
      usedTris += k.tris;
      usedTex += k.texBytes;
    }
    // Nearest the camera, or the jump's target when that is nearer (where the camera is going).
    const dist = (c: ChunkSpan) => (target === null ? gap(c, frame) : Math.min(gap(c, frame), gap(c, target)));
    const extra = chunks
      .filter((c) => resident.has(c.id) && loaded.has(c.id) && !keepSet.has(c.id))
      .sort((a, b) => dist(a) - dist(b) || (order.get(a.id) ?? 0) - (order.get(b.id) ?? 0));
    for (const c of extra) {
      const k = cost(c.id);
      if (usedTris + k.tris > w.retainTris || usedTex + k.texBytes > w.retainTexBytes) break;
      usedTris += k.tris;
      usedTex += k.texBytes;
      retain.push(c.id);
      keepSet.add(c.id);
    }
  }

  // Handing over: while something needed is not ready to draw, the areas nearest the camera that
  // are ready and drawn at this frame stay (past the cap and the budget) unless kept already. Only
  // loaded chunks (a failed one is "ready" too: nothing to wait for).
  const handover: string[] = [];
  if (ready !== undefined && w.handover > 0 && need.some((id) => !ready.has(id))) {
    const shown = chunks
      .filter((c) => resident.has(c.id) && ready.has(c.id) && (loaded === undefined || loaded.has(c.id)))
      .filter((c) => gapToRange(frame, c.need) <= w.drawMargin)
      .sort((a, b) => gap(a, frame) - gap(b, frame) || (order.get(a.id) ?? 0) - (order.get(b.id) ?? 0));
    for (const c of shown.slice(0, w.handover)) {
      if (keepSet.has(c.id)) continue;
      handover.push(c.id);
      keepSet.add(c.id);
    }
  }

  const keep = [...resident].filter((id) => keepSet.has(id)).sort((a, b) => (order.get(a) ?? 0) - (order.get(b) ?? 0));
  const drop = [...resident].filter((id) => !keepSet.has(id)).sort((a, b) => (order.get(a) ?? 0) - (order.get(b) ?? 0));
  const cancel = [...loading].filter((id) => !keepSet.has(id));

  const draw = keep.filter((id) => {
    const c = byId.get(id);
    return c !== undefined && gapToRange(frame, c.need) <= w.drawMargin;
  });

  return { need, load, prefetch, keep, retain, handover, drop, draw, cancel };
}
