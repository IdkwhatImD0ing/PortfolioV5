/**
 * Idle motion for the areas, as plain math (the scene applies it, experience/idle.ts): the film's
 * turning rings fitted from the baked geometry, glow rhythms (breathing, a wave running along a row,
 * a flicker), the per-vertex weights that let a banner's cloth flutter and a tree sway while
 * their poles and trunks stay put (with where the banners merged into the scenery hang), and the
 * gliding loop and wing beat of the baked cranes.
 *
 * Pure: plain arrays, no three.js.
 */

export type V3 = [number, number, number];

/** Radians per second of the film's 1-turn-per-1500-frames spins at 24 fps (forge ring, library spiral). */
export const FILM_TURN_SPEED = (2 * Math.PI * 24) / 1499;
/**
 * The formation core's driver: frame * 0.0025 radians, at 24 fps (0.06 rad/s, a turn in 105 s). The
 * round 6 armillary's turning rings are heavy bronze: slower than the old crystal's 0.006.
 */
export const FORMATION_CORE_SPEED = 0.0025 * 24;

/**
 * Seconds a turning piece's own clock moves on this frame: none while it holds still (the visitor
 * points at it), and at most 0.1 s, so a stalled frame does not jump. Its turn and its bob both run
 * on that clock, so a paused crane neither glides nor drifts up and down from under the pointer.
 */
export function rigidStep(dt: number, paused: boolean): number {
  return paused || !(dt > 0) ? 0 : Math.min(dt, 0.1);
}

/** How far (m) a turning piece has bobbed along its axis, `clock` seconds into its own motion. */
export function bobLift(clock: number, amplitude: number, phase = 0): number {
  return amplitude ? amplitude * Math.sin(clock * 0.9 + phase) : 0;
}

export interface RingFit {
  center: V3;
  /** Unit normal of the ring's plane, pointing up (y > 0). */
  normal: V3;
  /** Mean distance from the centre within the plane. */
  radius: number;
  /** Largest distance of a point from the plane. */
  planeError: number;
}

const sub = (a: V3, b: V3): V3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a: V3, b: V3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

function det3(m: number[][]): number {
  return (
    m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) -
    m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
    m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
  );
}

/**
 * The circle through points spread evenly around a ring that is not far from horizontal (a tilted
 * orbit hoop): the least-squares plane y = a x + b z + c, the points' mean as centre. Null for fewer
 * than 6 points or a degenerate (vertical, collinear) set.
 */
export function fitRing(points: readonly V3[]): RingFit | null {
  const n = points.length;
  if (n < 6) return null;
  let sxx = 0, sxz = 0, szz = 0, sx = 0, sz = 0, sxy = 0, szy = 0, sy = 0;
  for (const [x, y, z] of points) {
    sxx += x * x;
    sxz += x * z;
    szz += z * z;
    sx += x;
    sz += z;
    sxy += x * y;
    szy += z * y;
    sy += y;
  }
  const A = [
    [sxx, sxz, sx],
    [sxz, szz, sz],
    [sx, sz, n],
  ];
  const B = [sxy, szy, sy];
  const D = det3(A);
  if (!Number.isFinite(D) || Math.abs(D) < 1e-9) return null;
  const col = (k: number) => A.map((r, i) => r.map((v, j) => (j === k ? B[i] : v)));
  const a = det3(col(0)) / D;
  const b = det3(col(1)) / D;
  const len = Math.hypot(a, 1, b);
  const normal: V3 = [-a / len, 1 / len, -b / len];
  const center: V3 = [sx / n, sy / n, sz / n];
  let radius = 0;
  let planeError = 0;
  for (const p of points) {
    const d = sub(p, center);
    const h = dot(d, normal);
    planeError = Math.max(planeError, Math.abs(h));
    radius += Math.hypot(d[0] - h * normal[0], d[1] - h * normal[1], d[2] - h * normal[2]);
  }
  return { center, normal, radius: radius / n, planeError };
}

// ---- glow rhythms (0 .. 1) ----------------------------------------------------------------------

const frac = (x: number) => x - Math.floor(x);

/** A slow breath: 0 at rest, 1 at the top, once every `period` seconds. */
export function breathe(t: number, period: number, phase = 0): number {
  return 0.5 - 0.5 * Math.cos(2 * Math.PI * (t / period + phase));
}

/**
 * A pulse running along a row of `n` things, one cycle every `period` seconds: item `i` lights up
 * in turn, for `width` of the cycle (a soft bump), and rests otherwise.
 */
export function wave(t: number, period: number, i: number, n: number, width = 0.32): number {
  const x = frac(t / period - i / Math.max(1, n));
  return x < width ? Math.sin((Math.PI * x) / width) ** 2 : 0;
}

/** An ember's flicker: quick, irregular, never dark. */
export function flicker(t: number, seed = 0): number {
  const v = 0.55 + 0.22 * Math.sin(t * 7.3 + seed) + 0.14 * Math.sin(t * 13.1 + 1.7 + seed * 2.3) + 0.09 * Math.sin(t * 23.7 + seed * 5.1);
  return Math.min(1, Math.max(0, v));
}

// ---- cloth and branches -------------------------------------------------------------------------

/**
 * Per-vertex flutter for a banner hanging from a crossbar beside its pole (positions in a y-up
 * frame, xyz triples). The cloth is the wide, thin part above the base; the pole is where the base
 * stands. Returns four numbers per vertex: the cloth's normal times the vertex's weight (0 on the
 * pole, the crossbar and the base, growing toward the free bottom and outer edge), and a phase so
 * a ripple runs across the cloth.
 */
export function bannerSway(positions: ArrayLike<number>): Float32Array {
  const n = Math.floor(positions.length / 3);
  const out = new Float32Array(n * 4);
  if (n === 0) return out;
  let yMin = Infinity, yMax = -Infinity;
  for (let i = 0; i < n; i++) {
    yMin = Math.min(yMin, positions[i * 3 + 1]);
    yMax = Math.max(yMax, positions[i * 3 + 1]);
  }
  const H = yMax - yMin;
  if (!(H > 1)) return out;
  // The cloth's plane: horizontal principal axes of the upper part.
  const clothFloor = yMin + H * 0.3;
  let mx = 0, mz = 0, m = 0;
  for (let i = 0; i < n; i++) {
    if (positions[i * 3 + 1] < clothFloor) continue;
    mx += positions[i * 3];
    mz += positions[i * 3 + 2];
    m++;
  }
  if (m < 3) return out;
  mx /= m;
  mz /= m;
  let sxx = 0, sxz = 0, szz = 0;
  for (let i = 0; i < n; i++) {
    if (positions[i * 3 + 1] < clothFloor) continue;
    const dx = positions[i * 3] - mx;
    const dz = positions[i * 3 + 2] - mz;
    sxx += dx * dx;
    sxz += dx * dz;
    szz += dz * dz;
  }
  const ang = 0.5 * Math.atan2(2 * sxz, sxx - szz);
  const ux = Math.cos(ang), uz = Math.sin(ang);
  // Normal of the cloth (horizontal, across the width axis).
  const nx = -uz, nz = ux;
  // The pole stands where the base is: the mean width coordinate of the lowest vertices.
  let poleA = 0, pc = 0;
  for (let i = 0; i < n; i++) {
    if (positions[i * 3 + 1] > yMin + H * 0.12) continue;
    poleA += (positions[i * 3] - mx) * ux + (positions[i * 3 + 2] - mz) * uz;
    pc++;
  }
  poleA = pc ? poleA / pc : 0;
  let reach = 0;
  for (let i = 0; i < n; i++) {
    if (positions[i * 3 + 1] < clothFloor) continue;
    const a = (positions[i * 3] - mx) * ux + (positions[i * 3 + 2] - mz) * uz;
    reach = Math.max(reach, Math.abs(a - poleA));
  }
  const top = yMax - H * 0.1; // the crossbar and the finial stay put
  const span = Math.max(1, top - clothFloor);
  for (let i = 0; i < n; i++) {
    const x = positions[i * 3], y = positions[i * 3 + 1], z = positions[i * 3 + 2];
    const a = (x - mx) * ux + (z - mz) * uz;
    const off = Math.abs(a - poleA);
    const down = Math.min(1, Math.max(0, (top - y) / span));
    const side = reach > 0.3 ? Math.min(1, Math.max(0, (off - 0.3) / Math.max(0.3, reach - 0.3))) : 0;
    const w = y < clothFloor ? 0 : Math.pow(down, 1.2) * (0.35 + 0.65 * side) * (off > 0.3 ? 1 : 0);
    out[i * 4] = nx * w;
    out[i * 4 + 1] = 0;
    out[i * 4 + 2] = nz * w;
    out[i * 4 + 3] = a * 1.4 + y * 0.5;
  }
  return out;
}

/**
 * Per-vertex sway for a tree (y-up positions): a wind direction times a weight that is 0 at the
 * base and grows with the square of the height, plus a phase that varies across the crown.
 */
export function treeSway(positions: ArrayLike<number>, wind: [number, number] = [0.94, 0.34]): Float32Array {
  const n = Math.floor(positions.length / 3);
  const out = new Float32Array(n * 4);
  let yMin = Infinity, yMax = -Infinity;
  for (let i = 0; i < n; i++) {
    yMin = Math.min(yMin, positions[i * 3 + 1]);
    yMax = Math.max(yMax, positions[i * 3 + 1]);
  }
  const H = yMax - yMin;
  if (!(H > 0.5)) return out;
  const wl = Math.hypot(wind[0], wind[1]) || 1;
  for (let i = 0; i < n; i++) {
    const w = ((positions[i * 3 + 1] - yMin) / H) ** 2;
    out[i * 4] = (wind[0] / wl) * w;
    out[i * 4 + 1] = 0;
    out[i * 4 + 2] = (wind[1] / wl) * w;
    out[i * 4 + 3] = (positions[i * 3] + positions[i * 3 + 2]) * 0.18;
  }
  return out;
}

// ---- banners merged into the baked scenery ------------------------------------------------------

/**
 * A pole banner (props.banner, 'fan' style) that the web export merged into its area's baked
 * scenery with the stone and the roofs: no node, name or wind weight of its own reaches the page,
 * so the scene finds its cloth by where it hangs (experience/idle.ts cuts it out to flutter).
 * Three space. The cloth hangs from a hook at the end of a gold arm; `out` points from the pole
 * along the arm, and the cloth spans that direction and the vertical.
 */
export interface BannerHang {
  /** The hook at the cloth's apex. */
  hook: V3;
  /** Horizontal unit direction (x, z) from the pole out along the arm. */
  out: [number, number];
  /** props.banner's cloth length below the hook, and its width (m). */
  length: number;
  width: number;
}

/**
 * Inside the space a hanging banner's cloth fills (its baked billow and side streamers included)
 * and nothing else: not the pole, the arm above the hook or its brace, nor the ground or a lantern
 * below. props.banner: the stiffener rod's knobs reach 0.685 width either side of the hook (the
 * body and its streamers 0.63), and the arm's brace ends 0.6 width + 0.23 m back toward the pole
 * (clear of the knob for cloths up to 2.2 m wide); the baked wind carries the tails up to 0.05
 * length further out along the arm and billows the cloth up to about 0.6 width off its plane.
 */
export function inHang(h: BannerHang, x: number, y: number, z: number): boolean {
  const down = h.hook[1] - y;
  if (down < -0.03 || down > h.length + 0.6) return false;
  const dx = x - h.hook[0];
  const dz = z - h.hook[2];
  const along = dx * h.out[0] + dz * h.out[1];
  if (along < -(0.685 * h.width + 0.04) || along > 0.63 * h.width + 0.05 * h.length + 0.1) return false;
  return Math.abs(dz * h.out[0] - dx * h.out[1]) <= 0.65 * h.width;
}

/**
 * How far (m) below its hook a banner holds still: the hook's ring and the arm's curled end hang
 * about 0.1 m down, and the cloth's head is pinned there.
 */
export const HANG_STILL = 0.15;

/** A banner's own offset in the flutter's phase, so neighbours do not swing in step. */
const hangPhase = (h: BannerHang) => h.hook[0] * 0.9 + h.hook[2] * 0.37;

/**
 * Per-vertex flutter for banner cloth cut from the merged scenery (y-up world positions, xyz
 * triples), with props.banner's wave weights: each vertex follows its nearest hang and moves along
 * that cloth's normal times (depth below the hook / length)^1.2 (measured from HANG_STILL down), so
 * the hook holds and the tails swing most. Same layout as bannerSway (direction times weight, then
 * a phase that runs a ripple down and across the cloth).
 */
export function hangSway(positions: ArrayLike<number>, hangs: readonly BannerHang[]): Float32Array {
  const n = Math.floor(positions.length / 3);
  const out = new Float32Array(n * 4);
  if (!hangs.length) return out;
  for (let i = 0; i < n; i++) {
    const x = positions[i * 3], y = positions[i * 3 + 1], z = positions[i * 3 + 2];
    let h = hangs[0];
    let best = Infinity;
    for (const c of hangs) {
      const d = (x - c.hook[0]) ** 2 + (z - c.hook[2]) ** 2;
      if (d < best) {
        best = d;
        h = c;
      }
    }
    const w = Math.min(1, Math.max(0, (h.hook[1] - y - HANG_STILL) / (h.length - HANG_STILL))) ** 1.2;
    const along = (x - h.hook[0]) * h.out[0] + (z - h.hook[2]) * h.out[1];
    out[i * 4] = -h.out[1] * w;
    out[i * 4 + 1] = 0;
    out[i * 4 + 2] = h.out[0] * w;
    out[i * 4 + 3] = along * 1.4 + y * 0.5 + hangPhase(h);
  }
  return out;
}

/** A pair of banners facing each other across an area's axis (x = 0), arms pointing inward. */
function hangPair(x: number, y: number, z: number, length: number, width: number): BannerHang[] {
  return [-1, 1].map((s) => ({ hook: [s * x, y, z], out: [-s, 0], length, width }));
}

/**
 * Where an area stands (Blender space, z up): its root at `at` (world.py ANCHORS), turned `yaw`
 * radians about z (camera.area_yaws: local +y points along the flight from the previous area).
 */
export interface AreaFrame {
  at: V3;
  yaw: number;
}

/** The areas with fan banners merged into their scenery, besides the gate (which sits unturned at (0, 0, 40)). */
export const AREA_FRAMES = {
  /** From the mirror at (-95, 185). */
  forge: { at: [115, 335, 95], yaw: Math.atan2(-(115 + 95), 335 - 185) },
  /** From the forge at (115, 335). */
  arena: { at: [-35, 485, 120], yaw: Math.atan2(-(-35 - 115), 485 - 335) },
  /** From the arena at (-35, 485). */
  mission: { at: [-150, 625, 140], yaw: Math.atan2(-(-150 + 35), 625 - 485) },
} satisfies Record<string, AreaFrame>;

/**
 * The hang of a props.banner 'fan' banner as banner() builds it, three space. Its pole stands at
 * (x, y, z) in the area's frame (Blender, z up) with its arm turned `rot` about z from local +x;
 * the hook is at the arm's end, 0.75 + 0.6 width out, 0.41 m under the pole's top; the cloth is
 * 0.6 height long unless that would bring its tails within 0.4 m of the ground.
 */
export function fanHang(f: AreaFrame, x: number, y: number, z: number, rot: number, height: number, width: number): BannerHang {
  const arm = 0.75 + 0.6 * width;
  const length = Math.max(0.5 * width + 0.3, Math.max(0.8, Math.min(0.6 * height, height - 0.35 - 0.46)));
  const lx = x + arm * Math.cos(rot);
  const ly = y + arm * Math.sin(rot);
  const c = Math.cos(f.yaw), s = Math.sin(f.yaw);
  const bx = f.at[0] + lx * c - ly * s;
  const by = f.at[1] + lx * s + ly * c;
  const ox = Math.cos(rot + f.yaw), oy = Math.sin(rot + f.yaw);
  // Three (x, y, z) = Blender (x, z, -y).
  return { hook: [bx, f.at[2] + z + height - 0.41, -by], out: [ox, -oy], length, width };
}

/** arena.py's ring of 40 banners: the pole circle, the band they stand on and the open front's half angle. */
const ARENA_RING = { r: 32.2, z: -0.35, n: 40, gap: (13 * Math.PI) / 180 };

/**
 * The arena's banners 36 to 39, the four left of the open front that no hackathon claims (the
 * others are hotspots, which sway on their own): banner i stands at angle -90 deg + gap +
 * (360 deg - 2 gap) i / 39 on the ring, its arm along the ring, and its height is the file's (9 m
 * give or take 0.4, drawn from arena.py's seeded random).
 */
const ARENA_DECOR: [number, number][] = [
  [36, 8.7202],
  [37, 9.1187],
  [38, 9.1405],
  [39, 8.6914],
];

/**
 * The banners each area's export merged into its baked scenery, from the area scripts (checked
 * against the baked chunks: each hang's space holds exactly one banner's cloth and gold rod).
 * The gate (gate.py; the area sits at Blender (0, 0, 40), and three (x, y, z) = Blender (x, -z, y)):
 * - the plaza's eight, on 14 m poles at x = ±19.4 by y = -30, -20, 0 and 14: 1.7 m cloths, 8.4 m
 *   long, from a hook 13.59 m up at the end of a 1.77 m arm toward the axis;
 * - the stairway's two pairs, on landings 1 and 3 (_stairway), 12 m poles at x = ±9.5: 1.5 m
 *   cloths, 7.2 m long, from a hook 11.59 m up at the end of a 1.65 m arm.
 * The forge (forge.py): the approach's pair, 10 m poles at x = ±13 by y = -37, arms toward the axis.
 * The arena (arena.py _build_banners): the four of ARENA_DECOR.
 * The mission hall (mission.py _props): the plaza's front corners, 9 m poles at x = ±16 by y = -40,
 * arms toward the axis.
 * Not yet the formation's flags (being rebuilt).
 */
export const BANNER_HANGS: Record<string, readonly BannerHang[]> = {
  gate: [
    ...[30, 20, 0, -14].flatMap((z) => hangPair(17.63, 53.59, z, 8.4, 1.7)),
    ...hangPair(7.85, 42.95, 59.26, 7.2, 1.5),
    ...hangPair(7.85, 34.31, 74.22, 7.2, 1.5),
  ],
  forge: [-1, 1].map((s) => fanHang(AREA_FRAMES.forge, s * 13, -37, 0, s < 0 ? 0 : Math.PI, 10, 1.5)),
  arena: ARENA_DECOR.map(([i, height]) => {
    const a = -Math.PI / 2 + ARENA_RING.gap + ((2 * Math.PI - 2 * ARENA_RING.gap) * i) / (ARENA_RING.n - 1);
    return fanHang(AREA_FRAMES.arena, ARENA_RING.r * Math.cos(a), ARENA_RING.r * Math.sin(a), ARENA_RING.z, a - Math.PI / 2, height, 1.3);
  }),
  mission: [-1, 1].map((s) => fanHang(AREA_FRAMES.mission, s * 16, -40, 0, s < 0 ? 0 : Math.PI, 9, 1.3)),
};

// ---- gliding cranes -----------------------------------------------------------------------------

export interface CraneGlide {
  /** Loop radius (m) and angular speed (rad/s, positive: about +y, so the pair flies head first). */
  radius: number;
  speed: number;
  /** Each crane's origin (its body) and heading, three space. */
  cranes: { p: V3; f: V3 }[];
}

/**
 * The baked pairs of flying cranes (export_web.py AREA_HOTSPOTS "*-cranes"): origins and headings
 * read from out/sect_chase.blend (props.crane "flying" faces local -Y). They glide in a loop and
 * beat their wings; the summit's pair keeps a small loop so it stays beside the moon.
 */
export const CRANE_GLIDES: Record<string, CraneGlide> = {
  "abode-cranes": {
    radius: 14,
    speed: 0.2,
    cranes: [
      { p: [185.33, 277.0, -1339.99], f: [0.635, 0, 0.773] },
      { p: [188.15, 281.5, -1330.99], f: [0.413, 0, 0.911] },
    ],
  },
  "summit-cranes": {
    radius: 9,
    speed: 0.13,
    cranes: [
      { p: [-7.49, 357.1, -1510.34], f: [0.33, -0.149, -0.932] },
      { p: [1.44, 369.15, -1525.06], f: [0.386, -0.149, -0.91] },
    ],
  },
};

/** The pair's heading on the ground plane (the mean of the cranes', unit length). */
export function glideHeading(g: CraneGlide): V3 {
  const x = g.cranes.reduce((a, c) => a + c.f[0], 0);
  const z = g.cranes.reduce((a, c) => a + c.f[2], 0);
  const l = Math.hypot(x, z) || 1;
  return [x / l, 0, z / l];
}

/**
 * The loop's centre: `radius` to the left of the heading (up x heading), so turning about +y at a
 * positive speed carries a crane at `center` forward along its heading.
 */
export function glidePivot(center: V3, heading: V3, radius: number): V3 {
  return [center[0] + heading[2] * radius, center[1], center[2] - heading[0] * radius];
}

/**
 * Per-vertex wing beat for a pair of cranes (y-up positions): straight up times a weight that is 0
 * on the body and grows to 1 at the wingtips (distance across the heading, from each vertex's
 * nearest crane), plus a phase per crane so the two do not beat in step.
 */
export function craneFlap(positions: ArrayLike<number>, cranes: { p: V3; f: V3 }[]): Float32Array {
  const n = Math.floor(positions.length / 3);
  const out = new Float32Array(n * 4);
  if (!cranes.length) return out;
  const near = new Int32Array(n);
  const across = new Float32Array(n);
  const span = cranes.map(() => 0);
  const sides = cranes.map((c) => {
    const l = Math.hypot(c.f[0], c.f[2]) || 1;
    return [-c.f[2] / l, c.f[0] / l];
  });
  for (let i = 0; i < n; i++) {
    const x = positions[i * 3], y = positions[i * 3 + 1], z = positions[i * 3 + 2];
    let best = 0, bd = Infinity;
    cranes.forEach((c, k) => {
      const d = (x - c.p[0]) ** 2 + (y - c.p[1]) ** 2 + (z - c.p[2]) ** 2;
      if (d < bd) {
        bd = d;
        best = k;
      }
    });
    const c = cranes[best].p;
    const a = Math.abs((x - c[0]) * sides[best][0] + (z - c[2]) * sides[best][1]);
    near[i] = best;
    across[i] = a;
    span[best] = Math.max(span[best], a);
  }
  for (let i = 0; i < n; i++) {
    const t = span[near[i]] > 0 ? across[i] / span[near[i]] : 0;
    const u = Math.min(1, Math.max(0, (t - 0.2) / 0.8));
    out[i * 4 + 1] = u * u * (3 - 2 * u);
    out[i * 4 + 3] = near[i] * 1.9;
  }
  return out;
}

// ---- carving a moving group out of merged scenery -----------------------------------------------

export interface Cylinder {
  /** Axis position (x, z). */
  x: number;
  z: number;
  rMin: number;
  rMax: number;
  yMin: number;
  yMax: number;
}

export function inCylinder(c: Cylinder, x: number, y: number, z: number): boolean {
  if (y < c.yMin || y > c.yMax) return false;
  const r = Math.hypot(x - c.x, z - c.z);
  return r >= c.rMin && r <= c.rMax;
}

/**
 * Splits a triangle index list: triangles whose three corners all pass `inside` go to `carved`,
 * the rest stay. `world` holds the vertices' world positions (xyz triples). A missing index means
 * consecutive triangles.
 */
export function splitTriangles(
  index: ArrayLike<number> | null,
  vertexCount: number,
  world: ArrayLike<number>,
  inside: (x: number, y: number, z: number) => boolean,
): { kept: number[]; carved: number[] } {
  const ins = new Uint8Array(vertexCount);
  for (let v = 0; v < vertexCount; v++) ins[v] = inside(world[v * 3], world[v * 3 + 1], world[v * 3 + 2]) ? 1 : 0;
  const kept: number[] = [];
  const carved: number[] = [];
  const count = index ? index.length : vertexCount;
  for (let t = 0; t + 2 < count; t += 3) {
    const a = index ? index[t] : t;
    const b = index ? index[t + 1] : t + 1;
    const c = index ? index[t + 2] : t + 2;
    (ins[a] && ins[b] && ins[c] ? carved : kept).push(a, b, c);
  }
  return { kept, carved };
}
