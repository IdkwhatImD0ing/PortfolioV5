/**
 * The formation's page-drawn light (round 6, the Ming Sect's Grand Sect-Protecting Array): the
 * barrier dome, the soft shafts rising from the core and the eight array eyes, and the brazier
 * fires. The bake holds the stone, bronze and jade; everything here is light the bake cannot carry.
 *
 * - The dome is a faint barrier you notice at its edge: a gold fresnel rim, a seam where it meets
 *   the plaza, and now and then a shimmer sliding down a tortoise-shell lattice (domeAlpha, mirrored
 *   by domeGlsl for materials.ts createDomeMaterial). Face-on it all but vanishes.
 * - The old link beams (Blender's light_beam strips: spokes, links, the sky pillar) are dropped
 *   (isFormationLinkBeam); soft shafts are placed from the hotspots instead (formationShafts), so
 *   they work before and after the Blender rebake.
 * - Fires are found from the bake's ".glow.flame" meshes (clusterFlames).
 *
 * Pure: plain arrays, no three.js. Numbers live in look.ts (SECT_LOOK.formation).
 */
import { glslFloat } from "./glsl";
import { wave } from "./idle";
import { SECT_LOOK, type FormationLook, type ShaftLook } from "./look";
import type { HotspotInfo, Vec3 } from "./types";

/** The barrier's shape (metres, around the formation's anchor): formation.py's shield_dome(R_PLAZA - 0.1, 50). */
export const FORMATION_DOME = { area: "formation", radius: 49.9, height: 50 } as const;

/** Formation tiers: the page's fx tier (water.ts fxTier). */
export type FormationTierName = "high" | "mid" | "low";

export interface FormationTier {
  /** 0: rim and seam only; 1: plus the sliding shimmer on its lattice. */
  domeDetail: 0 | 1;
  /** 0: smooth shafts; 1: drifting streaks (one noise fetch). */
  streaks: 0 | 1;
  /** The wide faint halo round the core's shaft. */
  halo: boolean;
  /** Sparks per fire. */
  sparks: number;
}

/** High full, Medium lighter (no halo, fewer sparks), Low cheap (no shimmer, no streaks). */
export function formationTier(tier: FormationTierName, look: FormationLook = SECT_LOOK.formation): FormationTier {
  if (tier === "low") return { domeDetail: 0, streaks: 0, halo: false, sparks: look.fire.sparks.low };
  if (tier === "mid") return { domeDetail: 1, streaks: 1, halo: false, sparks: look.fire.sparks.mid };
  return { domeDetail: 1, streaks: 1, halo: true, sparks: look.fire.sparks.high };
}

// ---- the old beams ------------------------------------------------------------------------------

const LINK_BEAM = /^formation\.(spoke|sat_link|cluster_link|cross_link|core_feed|light_pillar)(\.|$)/;

/**
 * The formation's neon link strips and sky pillar (meta.beams): spokes, satellite, cluster and
 * cross links, the core feed and the light pillar, each with its ".core" twin. The page draws
 * none of them; the soft shafts replace them.
 */
export function isFormationLinkBeam(name: string): boolean {
  return LINK_BEAM.test(name);
}

// ---- shafts -------------------------------------------------------------------------------------

export type ShaftKind = "core" | "wisp" | "halo";

export interface Shaft {
  kind: ShaftKind;
  /** Where the light starts (three space). */
  base: Vec3;
  look: ShaftLook;
  /** The eyes' wave: this station's place in it (k / 8), or -1 for a steady shaft. */
  phase: number;
  /** Share of the light that rests between waves (1 for a steady shaft). */
  rest: number;
}

const STATIONS = 8;

/**
 * The core's shaft (from the centre of the `formation` hotspot, the turning core), a wisp over each
 * array eye (`arch:k`, from the top of its box less `wisp.belowTop`) and the core's wide halo, in
 * that order (a tier drops the halo by drawing one instance less). Nothing without the core hotspot
 * (the proto profile has no formation); wisps only for the stations it has.
 */
export function formationShafts(hotspots: readonly Pick<HotspotInfo, "id" | "center" | "size">[], look: FormationLook = SECT_LOOK.formation): Shaft[] {
  const core = hotspots.find((h) => h.id === "formation");
  if (!core) return [];
  const out: Shaft[] = [{ kind: "core", base: [...core.center], look: look.shaft, phase: -1, rest: 1 }];
  for (let k = 0; k < STATIONS; k++) {
    const h = hotspots.find((x) => x.id === `arch:${k}`);
    if (!h) continue;
    const top = h.center[1] + h.size[1] / 2;
    out.push({ kind: "wisp", base: [h.center[0], top - look.wisp.belowTop, h.center[2]], look: look.wisp, phase: k / STATIONS, rest: look.wisp.rest });
  }
  out.push({ kind: "halo", base: [...core.center], look: look.halo, phase: -1, rest: 1 });
  return out;
}

/**
 * A shaft's light at `h` metres above its base and `x` across (-1..1 of its half-width), before its
 * opacity, streaks and pulse: a soft Gaussian across (no hard core line), fading in over `fadeIn`,
 * halving every `halfLife` metres and gone by its height. Mirrored in createShaftMaterial.
 */
export function shaftProfile(h: number, x: number, s: ShaftLook): number {
  const across = Math.exp(-x * x * 2.5) * (1 - smoothstep(1.3, 1.6, Math.abs(x)));
  const along = smoothstep(0, s.fadeIn, h) * Math.pow(2, -Math.max(h, 0) / s.halfLife) * (1 - smoothstep(s.height * 0.6, s.height, h));
  return across * along;
}

/** The share of a wisp's light at time `t`: `rest` between waves, 1 at the wave's crest. */
export function wispPulse(t: number, phase: number, rest: number, look: FormationLook = SECT_LOOK.formation): number {
  if (phase < 0) return 1;
  // idle.ts wave(t, period, i, n) for station i of n is a function of t / period - i / n.
  return rest + (1 - rest) * wave(t, look.wave.period, phase * STATIONS, STATIONS, look.wave.width);
}

// ---- fires --------------------------------------------------------------------------------------

export interface FlameCluster {
  center: Vec3;
  min: Vec3;
  max: Vec3;
  /** Vertices in the cluster. */
  count: number;
}

/**
 * Groups flame vertices (xyz triples) into fires: each vertex falls in a `cell`-metre grid cell,
 * and occupied cells that touch (the 26 around) join. One cluster per brazier as long as fires
 * stand more than two cells apart. Sorted by x, then z, then y (stable across loads).
 */
export function clusterFlames(positions: ArrayLike<number>, cell: number): FlameCluster[] {
  const n = Math.floor(positions.length / 3);
  if (n === 0 || !(cell > 0)) return [];
  const cells = new Map<string, number>();
  const keys: [number, number, number][] = [];
  const vertCell = new Int32Array(n);
  for (let i = 0; i < n; i++) {
    const x = Math.floor(positions[i * 3] / cell), y = Math.floor(positions[i * 3 + 1] / cell), z = Math.floor(positions[i * 3 + 2] / cell);
    const key = `${x},${y},${z}`;
    let c = cells.get(key);
    if (c === undefined) {
      c = keys.length;
      cells.set(key, c);
      keys.push([x, y, z]);
    }
    vertCell[i] = c;
  }
  const parent = keys.map((_, i) => i);
  const find = (i: number): number => {
    while (parent[i] !== i) {
      parent[i] = parent[parent[i]];
      i = parent[i];
    }
    return i;
  };
  keys.forEach(([x, y, z], i) => {
    for (let dx = -1; dx <= 1; dx++)
      for (let dy = -1; dy <= 1; dy++)
        for (let dz = -1; dz <= 1; dz++) {
          const j = cells.get(`${x + dx},${y + dy},${z + dz}`);
          if (j === undefined) continue;
          const a = find(i), b = find(j);
          if (a !== b) parent[Math.max(a, b)] = Math.min(a, b);
        }
  });
  const groups = new Map<number, FlameCluster>();
  for (let i = 0; i < n; i++) {
    const root = find(vertCell[i]);
    const p: Vec3 = [positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]];
    const g = groups.get(root);
    if (!g) {
      groups.set(root, { center: [0, 0, 0], min: [...p], max: [...p], count: 1 });
      continue;
    }
    for (let a = 0; a < 3; a++) {
      g.min[a] = Math.min(g.min[a], p[a]);
      g.max[a] = Math.max(g.max[a], p[a]);
    }
    g.count++;
  }
  const out = [...groups.values()];
  for (const g of out) g.center = [(g.min[0] + g.max[0]) / 2, (g.min[1] + g.max[1]) / 2, (g.min[2] + g.max[2]) / 2];
  return out.sort((a, b) => a.center[0] - b.center[0] || a.center[2] - b.center[2] || a.center[1] - b.center[1]);
}

/** A fire's glow radius (m): from its flames' width, within the look's bounds. */
export function fireRadius(c: FlameCluster, look: FormationLook = SECT_LOOK.formation): number {
  const w = Math.max(c.max[0] - c.min[0], c.max[2] - c.min[2]);
  const [lo, hi] = look.fire.radius;
  return Math.min(hi, Math.max(lo, w * look.fire.radiusPerWidth));
}

// ---- the barrier dome ---------------------------------------------------------------------------

function smoothstep(e0: number, e1: number, x: number): number {
  const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
}

const SQRT3 = Math.sqrt(3);

/**
 * Distance to the centre of the nearest cell of a hexagon lattice with cells 1 wide (0 at a centre,
 * 0.5 on its edges). Mirrors sectHexDist.
 */
export function hexDist(px: number, py: number): number {
  const fl = (v: number) => Math.floor(v);
  const c0x = fl(px / 1) + 0.5, c0y = fl(py / SQRT3) + 0.5;
  const c1x = fl((px - 0.5) / 1) + 0.5, c1y = fl((py - 1) / SQRT3) + 0.5;
  const h0x = px - c0x, h0y = py - c0y * SQRT3;
  const h1x = px - (c1x + 0.5), h1y = py - (c1y + 0.5) * SQRT3;
  const [qx, qy] = h0x * h0x + h0y * h0y < h1x * h1x + h1y * h1y ? [h0x, h0y] : [h1x, h1y];
  const ax = Math.abs(qx), ay = Math.abs(qy);
  return Math.max(ax * 0.5 + ay * SQRT3 * 0.5, ax);
}

/** Cells round the dome at its foot: a whole number, so the lattice closes without a seam. */
export function domeCellsAround(look: FormationLook = SECT_LOOK.formation, radius: number = FORMATION_DOME.radius): number {
  return Math.max(6, Math.round((2 * Math.PI * radius) / look.dome.ripple.cell));
}

export interface DomeOptions {
  /** 0: rim and seam only (low tier); 1: plus the shimmer. */
  detail?: number;
  /** 0 with reduced motion: the shimmer rests (no frozen band). */
  motion?: number;
  /** Azimuth round the dome (radians). */
  az?: number;
  /** False for the far wall's inner face, seen through the near wall: it keeps dome.backFace. */
  front?: boolean;
  look?: FormationLook;
}

/**
 * The barrier's light (before its colour, the soft fade where it meets geometry and the haze) at
 * `facing` = |normal . view| (1 face-on, 0 at the silhouette), height `h` up the dome (0 at the
 * plaza, 1 at the top) and time `t` (s). Mirrors sectDomeAlpha (domeGlsl), which also widens the
 * lattice lines to at least a pixel; createDomeMaterial weighs back faces as `front: false` does.
 */
export function domeAlpha(facing: number, h: number, t: number, o: DomeOptions = {}): number {
  const look = o.look ?? SECT_LOOK.formation;
  const d = look.dome;
  const hc = Math.max(Number.isFinite(h) ? h : 0, 0);
  const g = 1 - Math.min(1, Math.max(0, facing));
  let a = Math.pow(g, d.rim.power) * d.rim.gain + Math.exp(-hc * d.seam.sharpness) * d.seam.gain;
  if ((o.detail ?? 1) > 0.5) {
    const r = d.ripple;
    const lat = Math.asin(Math.min(hc, 1));
    const px = ((o.az ?? 0) * domeCellsAround(look)) / (2 * Math.PI);
    const py = (lat * FORMATION_DOME.radius) / r.cell;
    const edges = smoothstep(0.5 - r.edge, 0.5, hexDist(px, py));
    a += rippleBands(hc, t, look) * (o.motion ?? 1) * (r.base + (1 - r.base) * edges) * (r.face + r.grazing * Math.pow(g, r.power));
  }
  return o.front === false ? a * d.backFace : a;
}

/** The two shimmer bands at height `h` (0..1) and time `t`: 1 at a band's crest. */
export function rippleBands(h: number, t: number, look: FormationLook = SECT_LOOK.formation): number {
  const r = look.dome.ripple;
  const sigma = r.width / 2.355;
  let sum = 0;
  for (let k = 0; k < 2; k++) {
    const f = t / r.period + 0.5 * k;
    const c = 1 - (f - Math.floor(f));
    const x = (h - c) / sigma;
    sum += Math.exp(-0.5 * x * x) * smoothstep(0, 0.12, c) * (1 - smoothstep(0.85, 1, c));
  }
  return sum;
}

/**
 * GLSL for the dome: `float sectHexDist( vec2 p )` and
 * `float sectDomeAlpha( float facing, float h, float t, float az, float detail, float motion )`,
 * with the look's numbers baked in. Lattice lines are widened to at least a pixel (fwidth), where
 * domeAlpha uses the look's width alone.
 */
export function domeGlsl(look: FormationLook = SECT_LOOK.formation): string {
  const d = look.dome;
  const r = d.ripple;
  const f = glslFloat;
  return /* glsl */ `
float sectHexDist( vec2 p ) {
  vec2 s = vec2( 1.0, 1.7320508 );
  vec4 c = floor( vec4( p, p - vec2( 0.5, 1.0 ) ) / s.xyxy ) + 0.5;
  vec4 q = vec4( p - c.xy * s, p - ( c.zw + 0.5 ) * s );
  vec2 h = dot( q.xy, q.xy ) < dot( q.zw, q.zw ) ? q.xy : q.zw;
  h = abs( h );
  return max( dot( h, s * 0.5 ), h.x );
}
float sectDomeAlpha( float facing, float h, float t, float az, float detail, float motion ) {
  float hc = max( h, 0.0 );
  float g = 1.0 - clamp( facing, 0.0, 1.0 );
  float a = pow( g, ${f(d.rim.power)} ) * ${f(d.rim.gain)} + exp( - hc * ${f(d.seam.sharpness)} ) * ${f(d.seam.gain)};
  if ( detail > 0.5 ) {
    float lat = asin( min( hc, 1.0 ) );
    vec2 p = vec2( az * ${f(domeCellsAround(look) / (2 * Math.PI))}, lat * ${f(FORMATION_DOME.radius / r.cell)} );
    float hd = sectHexDist( p );
    float ew = max( ${f(r.edge)}, fwidth( hd ) * 1.5 );
    float edges = smoothstep( 0.5 - ew, 0.5, hd );
    float bands = 0.0;
    for ( int k = 0; k < 2; k ++ ) {
      float c = 1.0 - fract( t / ${f(r.period)} + 0.5 * float( k ) );
      float x = ( hc - c ) / ${f(r.width / 2.355)};
      bands += exp( - 0.5 * x * x ) * smoothstep( 0.0, 0.12, c ) * ( 1.0 - smoothstep( 0.85, 1.0, c ) );
    }
    a += bands * motion * ( ${f(r.base)} + ${f(1 - r.base)} * edges ) * ( ${f(r.face)} + ${f(r.grazing)} * pow( g, ${f(r.power)} ) );
  }
  return a;
}
`;
}
