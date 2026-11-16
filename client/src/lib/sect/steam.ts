/**
 * Ice-Fire Island's steam rises (2026-11-15). The owner: "The ice fire mountain smoke doesnt animate".
 * The steam is 15 of the page's cloud puffs (range-look.ts isSteamPuff). Their only motion was the
 * mist's world-fixed noise drifting sideways at 0.7 m/s over cells 31-230 m wide: on a puff 3-9 m
 * across, nothing. So they now climb in the cloud puff shader (materials.ts createCloudPuffMaterial),
 * with no work on the CPU per frame.
 *
 * Each steam puff is packed twice (clouds.ts packPuffs: the second copy carries its rise span
 * negated), and the two copies loop through the puff's place half a loop apart:
 *
 * - s = fract( phase + time x speed / span ) is where a copy is in its loop (phase: a hash of the
 *   puff's centre, plus a half for the second copy);
 * - the copy's centre climbs from span / 2 below the puff's place to span / 2 above it, and moves
 *   downwind by `drift` x that;
 * - its semi-axes grow from grow[0] to grow[1] times their size;
 * - its density is the puff's x sin^2( pi s ): nothing at both ends of the loop, where it jumps back
 *   down, and all of it half way. The two copies' shares are sin^2 and cos^2, so they always add up
 *   to the puff's whole density: the puff's place is never empty and the plume never pumps.
 *
 * (The first version looped one copy per puff, fading to nothing at both ends: at any moment a few
 * puffs were empty, and the plume broke into separate balls with sky between them.)
 *
 * The span is short (about 1.4 times the puff's vertical half-extent), so a copy never strays far from
 * the puff's place and the plume keeps its shape on the island. The climbing is carried by the
 * texture too: inside a steam sprite the world noise rises at `speed`, with the copies, and the
 * sprite's own noise slides down the sprite at `churn` sprite heights a second, so its wisps climb.
 *
 * Every other puff (span 0) skips all of it. With uSteam off (reduced motion) the first copy is the
 * still puff and the second is not drawn, so the plume is exactly the still one.
 *
 * Pure maths and GLSL strings (no three.js), so the loop is testable; steamLoop is the shader's twin.
 */
import { supportRadius } from "./clouds";
import { glslFloat } from "./glsl";
import { isSteamPuff, RANGE_LOOK, type RangeLook } from "./range-look";
import type { CloudPuff, Vec3 } from "./types";

/**
 * The sprite's own noise in materials.ts is read at `vUv * vec2( 1.15, 1.9 )`, vUv -1..1: one sprite
 * height is 2 x 1.9 noise units.
 */
export const STEAM_NL_PER_HEIGHT = 3.8;

/**
 * The churn offset wraps at this many noise units. The field is read at nl x 0.5 and nl x 1.3 from a
 * texture that tiles at 1 (getNoiseTexture: RepeatWrapping): 10 is 5 and 13 whole tiles, so the
 * wrap is seamless.
 */
export const STEAM_NL_WRAP = 10;

/**
 * The cloud puff fragment shader's world noise is read at `nw = ( x 0.82 + z 0.57, y 1.35 )`: one
 * metre up is 1.35 units of nw.y.
 */
export const STEAM_NW_PER_METRE = 1.35;

function fract(x: number): number {
  return x - Math.floor(x);
}

/** The wind's direction (three's x, z), unit length. */
export function steamWind(look: RangeLook = RANGE_LOOK): [number, number] {
  const w = look.mist.wind;
  const len = Math.hypot(w[0], w[1]) || 1;
  return [w[0] / len, w[1] / len];
}

/**
 * A puff's rise span in metres (the length of its loop; the packed buffer's 14th float): its vertical
 * half-extent x steam.span, held to steam.spanM, for steam (isSteamPuff); 0 for every other puff.
 */
export function steamRise(p: CloudPuff, look: RangeLook = RANGE_LOOK): number {
  if (!isSteamPuff(p, look)) return 0;
  const s = look.steam;
  return Math.min(Math.max(s.span * supportRadius(p.axes, [0, 1, 0]), s.spanM[0]), s.spanM[1]);
}

/** A puff's phase in its loop, 0..1, from its centre (Dave Hoskins' hash13). Mirrors sectSteamHash. */
export function steamPhase(c: Vec3): number {
  let x = fract(c[0] * 0.1031);
  let y = fract(c[1] * 0.1031);
  let z = fract(c[2] * 0.1031);
  // p += dot( p, p.zyx + 31.32 )
  const d = x * (z + 31.32) + y * (y + 31.32) + z * (x + 31.32);
  x += d;
  y += d;
  z += d;
  return fract((x + y) * z);
}

/**
 * A copy's share of its puff's density at loop position s (0..1): sin^2( pi s ). 0 at both ends, 1
 * half way; the other copy, half a loop away, has the rest (cos^2), so the two always add up to 1.
 */
export function steamShare(s: number): number {
  const w = Math.sin(Math.PI * s);
  return w * w;
}

/** A steam copy at one moment (steamLoop). */
export interface SteamState {
  /** Where it is in its loop, 0..1. */
  s: number;
  /** How far its centre is from its puff's place (metres; y up, x and z downwind). */
  offset: Vec3;
  /** What its semi-axes are multiplied by. */
  grow: number;
  /** What the puff's density is multiplied by for this copy (steamShare). */
  density: number;
}

/**
 * One copy of a puff at time t (seconds), from its packed rise value `rise` (the span in metres; the
 * second copy's is negated, which puts it half a loop on) and the puff's phase: the shader's loop
 * (steamVertexStatements). A puff that is not steam (rise 0) stays as it is.
 */
export function steamLoop(t: number, rise: number, phase: number, look: RangeLook = RANGE_LOOK): SteamState {
  if (rise === 0 || !Number.isFinite(rise)) return { s: 0, offset: [0, 0, 0], grow: 1, density: 1 };
  const st = look.steam;
  const span = Math.abs(rise);
  const s = fract(phase + (rise < 0 ? 0.5 : 0) + (t * st.speed) / span);
  const up = (s - 0.5) * span;
  const [wx, wz] = steamWind(look);
  return {
    s,
    offset: [wx * st.drift * up, up, wz * st.drift * up],
    grow: st.grow[0] + (st.grow[1] - st.grow[0]) * s,
    density: steamShare(s),
  };
}

// ---------------------------------------------------------------------------------------------
// GLSL

/** For the cloud puff vertex shader: `float sectSteamHash( vec3 p )` (steamPhase's twin). */
export function steamVertexGlsl(): string {
  return /* glsl */ `
float sectSteamHash( vec3 p ) {
  p = fract( p * 0.1031 );
  p += dot( p, p.zyx + 31.32 );
  return fract( ( p.x + p.y ) * p.z );
}
`;
}

/** The condition of the cloud puff vertex shader's steam branch: a steam copy, and uSteam on. */
export const STEAM_BRANCH = "if ( iRise != 0.0 && uSteam > 0.5 ) {";

/**
 * The statements inside the cloud puff vertex shader's steam branch (STEAM_BRANCH): steamLoop's twin.
 * They move puffC, scale puffA0..2 and share out puffD (the puff's centre, semi-axes and density,
 * copied from its attributes before the branch), and set vSteam.
 */
export function steamVertexStatements(look: RangeLook = RANGE_LOOK): string {
  const st = look.steam;
  const [wx, wz] = steamWind(look);
  return [
    "    float steamSpan = abs( iRise );",
    `    float steamS = fract( sectSteamHash( iCenter ) + ( iRise < 0.0 ? 0.5 : 0.0 ) + uTime * ${glslFloat(st.speed)} / steamSpan );`,
    "    float steamUp = ( steamS - 0.5 ) * steamSpan;",
    `    puffC += vec3( ${glslFloat(wx * st.drift)}, 1.0, ${glslFloat(wz * st.drift)} ) * steamUp;`,
    `    float steamGrow = mix( ${glslFloat(st.grow[0])}, ${glslFloat(st.grow[1])}, steamS );`,
    "    puffA0 *= steamGrow;",
    "    puffA1 *= steamGrow;",
    "    puffA2 *= steamGrow;",
    `    float steamShare = sin( ${glslFloat(Math.PI)} * steamS );`,
    "    puffD *= steamShare * steamShare;",
    "    vSteam = 1.0;",
  ].join("\n");
}

/**
 * The cloud puff vertex shader's statement just before the sprite is collapsed when faded out: the
 * second copy of a steam puff (iRise < 0) is not drawn while the steam stands still (uSteam off), so
 * the first copy alone is the still puff.
 */
export const STEAM_HIDE_STATEMENT = "  if ( iRise < 0.0 && uSteam < 0.5 ) vFade = 0.0;";

/**
 * The cloud puff fragment shader's statement after `vec2 nw = ...`: on a steam sprite the world noise
 * rises at steam.speed, with the copies, so the steam's texture climbs with it.
 */
export function steamClimbStatement(look: RangeLook = RANGE_LOOK): string {
  return `  if ( vSteam > 0.5 ) nw.y -= uTime * ${glslFloat(look.steam.speed * STEAM_NW_PER_METRE)};`;
}

/**
 * The cloud puff fragment shader's statement after `vec2 nl = ...`: on a steam sprite the sprite's
 * own noise slides down it at steam.churn sprite heights a second, so its wisps climb.
 */
export function steamChurnStatement(look: RangeLook = RANGE_LOOK): string {
  return `  if ( vSteam > 0.5 ) nl.y -= mod( uTime * ${glslFloat(look.steam.churn * STEAM_NL_PER_HEIGHT)}, ${glslFloat(STEAM_NL_WRAP)} );`;
}
