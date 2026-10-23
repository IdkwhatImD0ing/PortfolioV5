/**
 * The Heart-Mirror as the Still Pond shows it without a rendered reflection (Low, and any frame on
 * High or Medium without the planar pass: materials.ts WATER_FRAGMENT, its analytic path). The ray
 * reflected off the water meets the mirror face's plane; what lies there is read from the mirror's
 * own layout, so the water shows its red cloud arms, gilt rim, cyan trigram ring, polished face,
 * flaming-pearl crest and lotus cradle, upside down, where High's real reflection puts them. It
 * replaces a flat gold disc that read as a bug once the stop framed the pond in the middle.
 *
 * The layout is blender/xianxia-sect/sect/areas/mirror.py's _mirror (MIRROR_R 3.5) and
 * lib/props.py's rune_ring, in metres on the face's plane: origin at the face's centre, x to the
 * right and y up as seen from the front. Things standing off the plane (the arms a little behind
 * it, the cradle's lip before it) shift with the ray's slope `k` (dot(ray, y) over
 * |dot(ray, normal)|): a point z metres in front of the plane meets the ray z k higher (the
 * cradle stands upright while the face leans back, so it is met in the world's level, cradleAt).
 *
 * heartMirrorGlsl() is the shader; heartMirrorLayers() its TypeScript mirror for the tests. Every
 * cover is box-filtered over a footprint of half-width `w` (m), so the 7 cm trigram bars average
 * out instead of shimmering, and the water's softness rides on the same width.
 */
import { glslFloat } from "./glsl";

/** A lathe profile: (radius, height above its base) pairs, height rising. */
export type MirrorProfile = readonly (readonly [number, number])[];

export const HEART_MIRROR = {
  /** The polished face's radius (R - 0.12): the disc water.ts discFromTriangles fits to it. */
  face: 3.38,
  /** The bronze back plate's radius (R - 0.1), seen from behind instead of the face. */
  back: 3.4,
  /** The gilt rim's band (R - 0.2 to R + 0.3), rounded, standing 0.16 m before the face. */
  rim: [3.3, 3.8] as const,
  runes: {
    /** The band's edges (R - 0.62 -/+ 0.275), each drawn as a line this wide. */
    ring: [2.605, 3.155] as const,
    line: 0.0275,
    /** Trigrams round the ring: qian at the top, then clockwise as seen from the front. */
    count: 16,
    /** Fu Xi order, each as its lines' bits, bottom line first (1 solid yang, 0 broken yin). */
    order: [7, 6, 2, 4, 0, 1, 5, 3] as const,
    /** The three bars' radial spans, bottom line innermost. */
    bars: [
      [2.734, 2.806],
      [2.844, 2.916],
      [2.954, 3.026],
    ] as const,
    /** A bar's half-length and a broken bar's half-gap, as angles (rad). */
    half: 0.0525,
    gap: 0.0172,
    /** The diamond between trigrams: its centre radius and half-diagonal (m). */
    diamond: [2.88, 0.0385] as const,
    /**
     * Share kept of the framing lines and diamonds: a few centimetres across, High's half-resolution
     * reflection all but loses them, and at full strength they joined the trigrams into one band.
     */
    faint: 0.35,
  },
  /** The red lacquer cloud arms: a tube round the rim from `from` to `to` degrees (from +x, counter-clockwise, mirrored to the left), then curling out to `tip`. */
  arms: { radius: 4.12, tube: 0.24, from: -78, to: 52, tip: { angle: 62, radius: 4.37, tube: 0.19 } },
  /** Gold pearls at the arms' tips. */
  pearls: { at: 4.42, angle: 64, radius: 0.4 },
  /** The gold flaming-pearl crest on top of the rim. */
  crest: {
    base: 3.7,
    profile: [
      [0, 0],
      [0.55, 0.1],
      [0.75, 0.45],
      [0.55, 0.9],
      [0.25, 1.3],
      [0, 1.75],
    ] as MirrorProfile,
  },
  /**
   * The gilt lotus cradle the disc sits in (its lip to the front and sides). The bronze pedestal and
   * the plinth under it are left out: Low's pond does not reflect the white dais they stand on, and
   * without it they rose from the reflection as a dark column.
   */
  cradle: {
    /** Its foot, this far below the disc's centre (straight down, m). */
    base: -3.9,
    profile: [
      [0.95, 0],
      [1.7, 0.25],
      [2.35, 0.75],
      [2.05, 0.86],
    ] as MirrorProfile,
    /**
     * The cup stands upright round the disc's centre while the disc leans back `tilt` degrees
     * (MIRROR_TILT), so its axis lies `axis` m behind the face's plane (the plane water.ts fits
     * through the face slab's middle, 0.14 m before the centre) and further behind toward its foot.
     * Taken on the face's own plane instead, its lip rose 0.4 m too high over the reflected face and
     * hid the bottom trigrams that High's real reflection shows.
     */
    axis: 0.14,
    tilt: 6,
  },
  /** The arms, pearls and crest stand this far behind the face's plane (m). */
  behind: 0.25,
  /** Nothing lies farther than this from the face's centre (m): the crest's tip, the cradle seen from below. */
  bound: 5.9,
  /** Lathe slices are at most this far apart (m). */
  slice: 0.2,
} as const;

/** The parts the shader shades differently (materials.ts sectMirrorShade); bronze is the back plate. */
export const MIRROR_PART = { face: 0, runes: 1, gold: 2, lacquer: 3, bronze: 4 } as const;
export type MirrorPart = (typeof MIRROR_PART)[keyof typeof MIRROR_PART];

/** One layer at a point: what it is, how much of the footprint it covers, and its surface's lean in the plane (x, y; |lean| < 1). */
export interface MirrorLayer {
  part: MirrorPart;
  cover: number;
  lean: [number, number];
}

const clamp01 = (x: number) => Math.min(Math.max(x, 0), 1);

/** Box-filtered cover of the interval [a, b] by a footprint of half-width w centred on x. */
export function mirrorSpan(x: number, a: number, b: number, w: number): number {
  const ww = Math.max(w, 1e-6);
  return clamp01((Math.min(b, x + ww) - Math.max(a, x - ww)) / (2 * ww));
}

/** Cover of a shape at signed distance sdf (negative inside), as a half-plane under the footprint. */
function edge(sdf: number, w: number): number {
  return clamp01(0.5 - sdf / (2 * Math.max(w, 1e-6)));
}

/** A lathe profile's radius at height h (0 outside it), straight between its points. */
export function profileRadius(p: MirrorProfile, h: number): number {
  if (h < p[0][1] || h > p[p.length - 1][1]) return 0;
  for (let i = 1; i < p.length; i++) {
    const [r0, h0] = p[i - 1];
    const [r1, h1] = p[i];
    if (h <= h1) return h1 > h0 ? r0 + ((r1 - r0) * (h - h0)) / (h1 - h0) : Math.max(r0, r1);
  }
  return p[p.length - 1][0];
}

/** Slices of a lathe for the ellipse union: (radius, height) at its points and between them, at most `step` apart. */
export function latheSlices(p: MirrorProfile, step: number = HEART_MIRROR.slice): [number, number][] {
  const out: [number, number][] = [];
  for (let i = 0; i < p.length; i++) {
    const [r, h] = p[i];
    if (i > 0) {
      const [r0, h0] = p[i - 1];
      const n = Math.ceil((h - h0) / step);
      for (let j = 1; j < n; j++) out.push([r0 + ((r - r0) * j) / n, h0 + ((h - h0) * j) / n]);
    }
    if (r > 0) out.push([r, h]);
  }
  return out;
}

const DEG = Math.PI / 180;

/**
 * The layers covering the point q (face plane, metres) back to front: crest, arms, pearls, the
 * cradle behind the face's plane, face, runes, rim, the cradle before it. `back`: seen from behind
 * (the bronze back plate, no runes). `kx`: the ray's sideways slope (dot(ray, x) over
 * |dot(ray, normal)|), which shears the upright cradle.
 */
export function heartMirrorLayers(q: readonly [number, number], w: number, k: number, back = false, kx = 0): MirrorLayer[] {
  const M = HEART_MIRROR;
  const out: MirrorLayer[] = [];
  const d = Math.hypot(q[0], q[1]);
  if (d > M.bound + w) return out;
  const sx = q[0] < 0 ? -1 : 1;
  const push = (part: MirrorPart, cover: number, lean: [number, number]) => {
    if (cover > 0) out.push({ part, cover, lean });
  };
  // Behind the face: the crest (centred), the arms and the pearls on their tips (mirrored left and right).
  const by = q[1] + M.behind * k;
  {
    const h = by - M.crest.base;
    const rho = profileRadius(M.crest.profile, h);
    const top = M.crest.profile[M.crest.profile.length - 1][1];
    const c = mirrorSpan(q[0], -rho, rho, w) * mirrorSpan(h, 0, top, w);
    push(MIRROR_PART.gold, c, lean2(q[0] / Math.max(rho, 0.05), (h - 0.6) / 1.2));
  }
  const bx = Math.abs(q[0]);
  {
    const arm = armAt(bx, by, w);
    push(MIRROR_PART.lacquer, arm.cover, [sx * arm.lean[0], arm.lean[1]]);
  }
  {
    const a = M.pearls.angle * DEG;
    const px = bx - M.pearls.at * Math.cos(a);
    const py = by - M.pearls.at * Math.sin(a);
    const r = Math.hypot(px, py);
    push(MIRROR_PART.gold, edge(r - M.pearls.radius, w), lean2((sx * px) / M.pearls.radius, py / M.pearls.radius));
  }
  const cup = cradleAt(q, w, k, kx, back);
  push(MIRROR_PART.gold, cup.behind, cup.lean);
  // The face (or the back plate) and the runes on it.
  push(back ? MIRROR_PART.bronze : MIRROR_PART.face, mirrorSpan(d, -1, back ? M.back : M.face, w), [0, 0]);
  if (!back) push(MIRROR_PART.runes, runesAt(q, d, w), [0, 0]);
  // Before it: the rim, then the cradle's near side.
  {
    const mid = (M.rim[0] + M.rim[1]) / 2;
    const half = (M.rim[1] - M.rim[0]) / 2;
    const o = (d - mid) / half;
    push(MIRROR_PART.gold, mirrorSpan(d, M.rim[0], M.rim[1], w), lean2((o * q[0]) / Math.max(d, 1e-6), (o * q[1]) / Math.max(d, 1e-6)));
  }
  push(MIRROR_PART.gold, cup.cover, cup.lean);
  return out;
}

/** The front-most layer covering at least half the footprint at q, or null. */
export function heartMirrorTop(q: readonly [number, number], w = 0.001, k = 0, back = false, kx = 0): MirrorPart | null {
  const layers = heartMirrorLayers(q, w, k, back, kx).filter((l) => l.cover >= 0.5);
  return layers.length ? layers[layers.length - 1].part : null;
}

/** A lean shortened to below 1 (the normal keeps a share facing out of the plane). */
function lean2(x: number, y: number): [number, number] {
  const l = Math.hypot(x, y);
  const s = l > 0.95 ? 0.95 / l : 1;
  return [x * s, y * s];
}

/** The right arm at (x >= 0, y): its tube round the rim, its curl to the tip, round ends. */
function armAt(x: number, y: number, w: number): { cover: number; lean: [number, number] } {
  const A = HEART_MIRROR.arms;
  const d = Math.hypot(x, y);
  if (d < A.radius - A.tube - w) return { cover: 0, lean: [0, 0] };
  const th = Math.atan2(y, x) / DEG;
  const cap = (deg: number, rad: number, tube: number) => {
    const cx = x - rad * Math.cos(deg * DEG);
    const cy = y - rad * Math.sin(deg * DEG);
    return { cover: edge(Math.hypot(cx, cy) - tube, w), lean: lean2(cx / tube, cy / tube) };
  };
  if (th <= A.from) return cap(A.from, A.radius, A.tube);
  if (th > A.tip.angle) return cap(A.tip.angle, A.tip.radius, A.tip.tube);
  const f = th <= A.to ? 0 : (th - A.to) / (A.tip.angle - A.to);
  const rc = A.radius + (A.tip.radius - A.radius) * f;
  const tube = A.tube + (A.tip.tube - A.tube) * f;
  const o = (d - rc) / tube;
  return { cover: mirrorSpan(d, rc - tube, rc + tube, w), lean: lean2((o * x) / Math.max(d, 1e-6), (o * y) / Math.max(d, 1e-6)) };
}

/** The trigram ring: three bars per trigram (broken for yin), and faintly its two framing lines and the diamonds between. */
function runesAt(q: readonly [number, number], d: number, w: number): number {
  const R = HEART_MIRROR.runes;
  if (d < R.ring[0] - w || d > R.ring[1] + w) return 0;
  let c = (mirrorSpan(d, R.ring[0], R.ring[0] + R.line, w) + mirrorSpan(d, R.ring[1] - R.line, R.ring[1], w)) * R.faint;
  const step = (2 * Math.PI) / R.count;
  // Clockwise from the top, in trigram steps.
  const a = Math.PI / 2 - Math.atan2(q[1], q[0]);
  const kf = Math.floor(a / step + 0.5);
  const da = a - kf * step;
  const code: number = R.order[((kf % 8) + 8) % 8];
  const s = da * d;
  const solid = mirrorSpan(s, -R.half * d, R.half * d, w);
  const broken = mirrorSpan(s, -R.half * d, -R.gap * d, w) + mirrorSpan(s, R.gap * d, R.half * d, w);
  R.bars.forEach(([r0, r1], i) => {
    c += mirrorSpan(d, r0, r1, w) * ((code >> i) & 1 ? solid : broken);
  });
  const dd = Math.abs(d - R.diamond[0]) + Math.abs((Math.abs(da) - step / 2) * d);
  c += edge(dd - R.diamond[1], w) * R.faint;
  return clamp01(c);
}

/**
 * The upright cradle seen along a ray of slopes k (up) and kx (sideways). In the face's frame the
 * world's up is (0, uy, un) (the face leans back: un = sin tilt, negated from behind) and the cup's
 * axis lies `a` behind the plane. A slice of it, a level circle of radius rho y metres above the
 * disc's centre, meets the plane in an ellipse: centred at (kx (y un - a), y (uy + k un) - a k), as
 * wide as the circle, its depth showing kk = k uy - un times over in height (seen from below, kk > 0,
 * the near side rises) and kx uy times over sideways. The solid is their union with its side-on
 * outline (which also fills between slices). What a slice shows nearer than zf = (a - y un) / uy
 * stands before the face's plane (`cover`, drawn over the face: the outline too, the cup's near
 * wall); the rest lies behind it (`behind`, under the face: from above it would otherwise paint
 * the cup's far side over the face). The surface leans out to the sides and, seen from below, down.
 */
function cradleAt(q: readonly [number, number], w: number, k: number, kx: number, back: boolean): { cover: number; behind: number; lean: [number, number] } {
  const C = HEART_MIRROR.cradle;
  const s = back ? -1 : 1;
  const uy = Math.cos(C.tilt * DEG);
  const un = s * Math.sin(C.tilt * DEG);
  const a = s * C.axis;
  const kk = k * uy - un;
  const sk = kk >= 0 ? 1 : -1;
  const sx = kx * uy;
  const h0 = (q[1] + a * k) / (uy + k * un) - C.base;
  const x0 = q[0] - kx * ((C.base + h0) * un - a);
  const r0 = profileRadius(C.profile, h0);
  let cover = mirrorSpan(x0, -r0, r0, w) * mirrorSpan(h0, C.profile[0][1], C.profile[C.profile.length - 1][1], w);
  let behind = 0;
  let lean: [number, number] = lean2((0.85 * x0) / Math.max(r0, 0.05), -0.45 * sk);
  for (const [rho, h] of latheSlices(C.profile)) {
    const y = C.base + h;
    const cy = y * (uy + k * un) - a * k;
    const b = Math.max(Math.abs(kk) * rho, 1e-3);
    const zs = (sk * (q[1] - cy)) / b;
    const xs = (q[0] - kx * (y * un - a)) / rho - sx * zs;
    const c = edge((Math.hypot(xs, zs) - 1) * Math.min(rho, b), w);
    const near = clamp01(0.5 + (sk * (q[1] - cy - (kk * (a - y * un)) / uy)) / (2 * Math.max(w, 1e-6)));
    if (c > Math.max(cover, behind)) lean = lean2(0.85 * xs, -0.45 * sk);
    cover = Math.max(cover, c * near);
    behind = Math.max(behind, c * (1 - near));
  }
  return { cover, behind, lean };
}

// ---- the shader -----------------------------------------------------------------------------------

const f = glslFloat;

/** A profile's radius at h (0 outside), as a chain of tests. */
function profileGlsl(name: string, p: MirrorProfile): string {
  const lines = [`float ${name}( float h ) {`, `  if ( h < ${f(p[0][1])} || h > ${f(p[p.length - 1][1])} ) return 0.0;`];
  for (let i = 1; i < p.length; i++) {
    const [r0, h0] = p[i - 1];
    const [r1, h1] = p[i];
    lines.push(`  if ( h <= ${f(h1)} ) return mix( ${f(r0)}, ${f(r1)}, ( h - ${f(h0)} ) / ${f(Math.max(h1 - h0, 1e-6))} );`);
  }
  lines.push(`  return ${f(p[p.length - 1][0])};`, "}");
  return lines.join("\n");
}

/**
 * The upright cradle's outline and slice ellipses (cradleAt), as a function of q, w, k and the view
 * (the world's up and the ray's sideways slope from its frame): the cover before the face's plane
 * returned, the cover behind it in `behind`, with its lean out.
 */
function cradleGlsl(): string {
  const C = HEART_MIRROR.cradle;
  const p = C.profile;
  const slices = latheSlices(p);
  const arr = (i: 0 | 1) => `float[${slices.length}]( ${slices.map((s) => f(s[i])).join(", ")} )`;
  return `float sectMirrorCradle( vec2 q, float w, float k, SectMirrorView m, out vec2 lean, out float behind ) {
  const float rho[${slices.length}] = ${arr(0)};
  const float hgt[${slices.length}] = ${arr(1)};
  float uy = m.y.y;
  float un = m.n.y;
  float a = m.back > 0.5 ? ${f(-C.axis)} : ${f(C.axis)};
  float kx = dot( m.r, m.x ) / max( abs( dot( m.r, m.n ) ), 1e-4 );
  float kk = k * uy - un;
  float sk = kk >= 0.0 ? 1.0 : -1.0;
  float sx = kx * uy;
  float h0 = ( q.y + a * k ) / ( uy + k * un ) - ${f(C.base)};
  float x0 = q.x - kx * ( ( ${f(C.base)} + h0 ) * un - a );
  float r0 = sectMirrorCradleR( h0 );
  float cover = sectMirrorSpan( x0, - r0, r0, w ) * sectMirrorSpan( h0, ${f(p[0][1])}, ${f(p[p.length - 1][1])}, w );
  behind = 0.0;
  lean = sectMirrorLean( vec2( 0.85 * x0 / max( r0, 0.05 ), - 0.45 * sk ) );
  for ( int i = 0; i < ${slices.length}; i ++ ) {
    float y = ${f(C.base)} + hgt[i];
    float cy = y * ( uy + k * un ) - a * k;
    float b = max( abs( kk ) * rho[i], 1e-3 );
    float zs = sk * ( q.y - cy ) / b;
    float xs = ( q.x - kx * ( y * un - a ) ) / rho[i] - sx * zs;
    float c = sectMirrorEdge( ( length( vec2( xs, zs ) ) - 1.0 ) * min( rho[i], b ), w );
    float near = clamp( 0.5 + sk * ( q.y - cy - kk * ( a - y * un ) / uy ) / ( 2.0 * w ), 0.0, 1.0 );
    if ( c > max( cover, behind ) ) lean = sectMirrorLean( vec2( 0.85 * xs, - 0.45 * sk ) );
    cover = max( cover, c * near );
    behind = max( behind, c * ( 1.0 - near ) );
  }
  return cover;
}`;
}

/**
 * The GLSL: the view struct handed through to the caller's shading, the shapes, and
 * `vec4 sectHeartMirror( vec2 q, float w, float k, SectMirrorView m )`, the layers composited back
 * to front (rgb premultiplied by the cover in a). The caller defines
 * `vec3 sectMirrorShade( int part, vec2 q, vec2 lean, SectMirrorView m )` (MIRROR_PART numbering).
 */
export function heartMirrorGlsl(): string {
  const M = HEART_MIRROR;
  const R = M.runes;
  const A = M.arms;
  const P = M.pearls;
  const crestTop = M.crest.profile[M.crest.profile.length - 1][1];
  const pa = P.angle * DEG;
  const rimMid = (M.rim[0] + M.rim[1]) / 2;
  const rimHalf = (M.rim[1] - M.rim[0]) / 2;
  return /* glsl */ `
#define SECT_HEART_FACE ${f(M.face)}
// The ray reflected off the water and the face's frame: x right and y up as seen from the side the ray
// meets, n toward it; back = 1 when that is the bronze back.
struct SectMirrorView { vec3 r; vec3 x; vec3 y; vec3 n; float back; };
vec3 sectMirrorShade( int part, vec2 q, vec2 lean, SectMirrorView m );
float sectMirrorSpan( float x, float a, float b, float w ) {
  return clamp( ( min( b, x + w ) - max( a, x - w ) ) / ( 2.0 * w ), 0.0, 1.0 );
}
float sectMirrorEdge( float sdf, float w ) {
  return clamp( 0.5 - sdf / ( 2.0 * w ), 0.0, 1.0 );
}
vec2 sectMirrorLean( vec2 l ) {
  float n = length( l );
  return n > 0.95 ? l * ( 0.95 / n ) : l;
}
vec4 sectMirrorOver( vec4 acc, vec3 col, float c ) {
  return vec4( acc.rgb * ( 1.0 - c ) + col * c, acc.a * ( 1.0 - c ) + c );
}
${profileGlsl("sectMirrorCrestR", M.crest.profile)}
${profileGlsl("sectMirrorCradleR", M.cradle.profile)}
${cradleGlsl()}
// The right arm at ( x >= 0, y ): round the rim, curling out to the tip, round ends.
float sectMirrorArm( vec2 p, float w, out vec2 lean ) {
  lean = vec2( 0.0 );
  float d = length( p );
  if ( d < ${f(A.radius - A.tube)} - w ) return 0.0;
  float th = degrees( atan( p.y, p.x ) );
  if ( th <= ${f(A.from)} || th > ${f(A.tip.angle)} ) {
    bool lo = th <= ${f(A.from)};
    float a = radians( lo ? ${f(A.from)} : ${f(A.tip.angle)} );
    float tube = lo ? ${f(A.tube)} : ${f(A.tip.tube)};
    vec2 o = p - ( lo ? ${f(A.radius)} : ${f(A.tip.radius)} ) * vec2( cos( a ), sin( a ) );
    lean = sectMirrorLean( o / tube );
    return sectMirrorEdge( length( o ) - tube, w );
  }
  float fa = th <= ${f(A.to)} ? 0.0 : ( th - ${f(A.to)} ) / ${f(A.tip.angle - A.to)};
  float rc = mix( ${f(A.radius)}, ${f(A.tip.radius)}, fa );
  float tube = mix( ${f(A.tube)}, ${f(A.tip.tube)}, fa );
  lean = sectMirrorLean( p / max( d, 1e-6 ) * ( d - rc ) / tube );
  return sectMirrorSpan( d, rc - tube, rc + tube, w );
}
// The trigram ring: three bars per trigram (yin broken), and faintly the two framing lines and a diamond between trigrams.
float sectMirrorRunes( vec2 q, float d, float w ) {
  if ( d < ${f(R.ring[0])} - w || d > ${f(R.ring[1])} + w ) return 0.0;
  const int order[8] = int[8]( ${R.order.join(", ")} );
  float c = ( sectMirrorSpan( d, ${f(R.ring[0])}, ${f(R.ring[0] + R.line)}, w ) + sectMirrorSpan( d, ${f(R.ring[1] - R.line)}, ${f(R.ring[1])}, w ) ) * ${f(R.faint)};
  float stp = ${f((2 * Math.PI) / R.count)};
  float a = 1.5707963 - atan( q.y, q.x );
  float kf = floor( a / stp + 0.5 );
  float da = a - kf * stp;
  int code = order[ clamp( int( mod( kf, 8.0 ) ), 0, 7 ) ];
  float s = da * d;
  float solid = sectMirrorSpan( s, ${f(-R.half)} * d, ${f(R.half)} * d, w );
  float broken = sectMirrorSpan( s, ${f(-R.half)} * d, ${f(-R.gap)} * d, w ) + sectMirrorSpan( s, ${f(R.gap)} * d, ${f(R.half)} * d, w );
  c += sectMirrorSpan( d, ${f(R.bars[0][0])}, ${f(R.bars[0][1])}, w ) * ( ( code & 1 ) != 0 ? solid : broken );
  c += sectMirrorSpan( d, ${f(R.bars[1][0])}, ${f(R.bars[1][1])}, w ) * ( ( code & 2 ) != 0 ? solid : broken );
  c += sectMirrorSpan( d, ${f(R.bars[2][0])}, ${f(R.bars[2][1])}, w ) * ( ( code & 4 ) != 0 ? solid : broken );
  float dd = abs( d - ${f(R.diamond[0])} ) + abs( ( abs( da ) - stp * 0.5 ) * d );
  c += sectMirrorEdge( dd - ${f(R.diamond[1])}, w ) * ${f(R.faint)};
  return clamp( c, 0.0, 1.0 );
}
vec4 sectHeartMirror( vec2 q, float w, float k, SectMirrorView m ) {
  vec4 acc = vec4( 0.0 );
  float d = length( q );
  if ( d > ${f(M.bound)} + w ) return acc;
  float sx = q.x < 0.0 ? -1.0 : 1.0;
  vec2 lean;
  float c;
  // Behind the face: the crest, the arms, the pearls on their tips.
  float by = q.y + ${f(M.behind)} * k;
  float h = by - ${f(M.crest.base)};
  float rho = sectMirrorCrestR( h );
  c = sectMirrorSpan( q.x, - rho, rho, w ) * sectMirrorSpan( h, 0.0, ${f(crestTop)}, w );
  if ( c > 0.0 ) acc = sectMirrorOver( acc, sectMirrorShade( ${MIRROR_PART.gold}, q, sectMirrorLean( vec2( q.x / max( rho, 0.05 ), ( h - 0.6 ) / 1.2 ) ), m ), c );
  vec2 b = vec2( abs( q.x ), by );
  c = sectMirrorArm( b, w, lean );
  if ( c > 0.0 ) acc = sectMirrorOver( acc, sectMirrorShade( ${MIRROR_PART.lacquer}, q, vec2( sx * lean.x, lean.y ), m ), c );
  vec2 po = b - ${f(P.at)} * vec2( ${f(Math.cos(pa))}, ${f(Math.sin(pa))} );
  c = sectMirrorEdge( length( po ) - ${f(P.radius)}, w );
  if ( c > 0.0 ) acc = sectMirrorOver( acc, sectMirrorShade( ${MIRROR_PART.gold}, q, sectMirrorLean( vec2( sx * po.x, po.y ) / ${f(P.radius)} ), m ), c );
  // The cradle: what of it lies behind the face's plane, under the face; its near side comes last.
  float cupBehind;
  vec2 cupLean;
  float cup = sectMirrorCradle( q, w, k, m, cupLean, cupBehind );
  vec3 cupCol = cup + cupBehind > 0.0 ? sectMirrorShade( ${MIRROR_PART.gold}, q, cupLean, m ) : vec3( 0.0 );
  if ( cupBehind > 0.0 ) acc = sectMirrorOver( acc, cupCol, cupBehind );
  // The face (the back plate from behind) and its runes.
  c = sectMirrorSpan( d, -1.0, m.back > 0.5 ? ${f(M.back)} : ${f(M.face)}, w );
  if ( c > 0.0 ) acc = sectMirrorOver( acc, sectMirrorShade( m.back > 0.5 ? ${MIRROR_PART.bronze} : ${MIRROR_PART.face}, q, vec2( 0.0 ), m ), c );
  c = m.back > 0.5 ? 0.0 : sectMirrorRunes( q, d, w );
  if ( c > 0.0 ) acc = sectMirrorOver( acc, sectMirrorShade( ${MIRROR_PART.runes}, q, vec2( 0.0 ), m ), c );
  // Before it: the rim, the cradle's near side.
  c = sectMirrorSpan( d, ${f(M.rim[0])}, ${f(M.rim[1])}, w );
  if ( c > 0.0 ) acc = sectMirrorOver( acc, sectMirrorShade( ${MIRROR_PART.gold}, q, sectMirrorLean( q / max( d, 1e-6 ) * ( d - ${f(rimMid)} ) / ${f(rimHalf)} ), m ), c );
  if ( cup > 0.0 ) acc = sectMirrorOver( acc, cupCol, cup );
  return acc;
}
`;
}
