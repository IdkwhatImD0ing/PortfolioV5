/**
 * GLSL for /sect as plain strings (no three.js import), plus TypeScript mirrors of the fog maths
 * so the numbers can be tested.
 *
 * Fog: replaces three's fog chunks with exponential height haze (Blender's world haze:
 * extinction density * exp(-(y - baseY) / falloff) per metre), a thin valley mist low over the
 * cloud layer, and a dense cloud layer that swallows everything below the cloud top. Analytic
 * integral after Inigo Quilez, "fog".
 *
 * Aerial perspective (the AAA distance look): each channel fades at its own rate (blue fastest,
 * so far ridges go bluer and paler while near ones keep their colour), the haze cools from gold
 * toward the sun to lavender away from it, and far surfaces lose colour toward the haze's hue
 * (The Witcher 3's front/back fog colours and aerial term). Off at the defaults of
 * fogConstantsFromMeta; lookFogConstants (look.ts) turns it on.
 */
import type { SectMeta, Vec3 } from "./types";

/** sRGB hex (#rrggbb) to linear-sRGB floats, the working space three.js shades in. */
export function hexToLinear(hex: string): Vec3 {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return [0.5, 0.5, 0.5];
  const n = parseInt(m[1], 16);
  const ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((c) => {
    const s = c / 255;
    return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return [ch[0], ch[1], ch[2]];
}

/** GLSL float literal (always has a decimal point or exponent). */
export function glslFloat(x: number): string {
  if (!Number.isFinite(x)) return "0.0";
  if (Number.isInteger(x)) return x.toFixed(1);
  const s = x.toPrecision(8);
  return s.includes(".") || s.includes("e") ? s : `${s}.0`;
}

export function glslVec3(v: Vec3): string {
  return `vec3( ${glslFloat(v[0])}, ${glslFloat(v[1])}, ${glslFloat(v[2])} )`;
}

export interface FogConstants {
  density: number;
  baseY: number;
  falloff: number;
  /** Top of the cloud layer (three y). Density grows below it with scale cloudScale. */
  cloudTop: number;
  cloudScale: number;
  cloudDensity: number;
  sunDir: Vec3;
  /** Linear colour the haze takes when looking toward the sun. */
  sunFogColor: Vec3;
  sunFogMix: number;
  /** Linear colour of the cloud layer. */
  cloudColor: Vec3;
  /** Extra haze on the sky dome (Blender's haze volume reads stronger on the sky than in the analytic model). */
  skyHaze: number;
  /**
   * Optical-depth scale per channel (r, g, b) on fogged surfaces: [1, 1, 1] is one grey veil;
   * blue above red turns distance blue (air scatters blue most).
   */
  extinction: Vec3;
  /** Hue of the haze looking away from the sun, as a luminance-1 tint (look.ts unitTint). */
  coolTint: Vec3;
  /** 0 = no cooling; 1 = the full tint looking straight away from the sun. */
  coolMix: number;
  /** Share of a surface's colour turned to its luminance in the haze's hue once the haze covers it. */
  desaturate: number;
  /**
   * Optical depth over which extinction, coolTint and the far haze colour come in
   * (1 - exp(-od / aerialDepth)): thin haze keeps the plain veil, so the scenery at hand is unchanged.
   */
  aerialDepth: number;
  /** Valley mist: extinction per metre at mistBaseY (0 = none), thinning upward over mistFalloff. */
  mistDensity: number;
  mistBaseY: number;
  mistFalloff: number;
  /** Metres from the camera before the mist starts, so the scenery at hand never fogs. */
  mistStart: number;
  /** Dither in 8-bit steps that fogged materials add when they draw straight to the screen (low tier). */
  dither: number;
}

export function fogConstantsFromMeta(meta: SectMeta): FogConstants {
  const cloudTop = meta.cloudSea.fogTopY - 20;
  return {
    density: meta.fog.density,
    baseY: meta.fog.baseY,
    falloff: meta.fog.falloff,
    // Blender's cloud fog volume reaches fogTopY but is thin near its top; the dense part starts
    // about 20 m lower (the opening frames fly at y ~18 and see the stairs clearly).
    cloudTop,
    cloudScale: 10,
    cloudDensity: 0.004,
    sunDir: meta.sun.direction,
    sunFogColor: hexToLinear(meta.sky.horizonSun),
    sunFogMix: 0.8,
    cloudColor: hexToLinear("#c9c3c6"),
    skyHaze: 4.0,
    // Aerial perspective, mist and dither off: the plain haze of the Blender film.
    extinction: [1, 1, 1],
    coolTint: [1, 1, 1],
    coolMix: 0,
    desaturate: 0,
    aerialDepth: 0.35,
    mistDensity: 0,
    mistBaseY: cloudTop,
    mistFalloff: 40,
    mistStart: 150,
    dither: 0,
  };
}

/** Integral of exp(-k s) ds from 0 to t, guarded against overflow like the GLSL version. */
export function expIntegral(k: number, t: number): number {
  if (Math.abs(k) < 1e-5) return t;
  return (1 - Math.exp(Math.min(Math.max(-k * t, -80), 80))) / k;
}

/** Optical depth of the height haze alone (Blender's world haze). */
export function hazeLayerDepth(c: FogConstants, y0: number, dy: number, t: number): number {
  const b = 1 / c.falloff;
  return c.density * Math.exp(Math.min(Math.max(-(y0 - c.baseY) * b, -80), 80)) * expIntegral(dy * b, t);
}

/**
 * Valley mist optical depth: the thin low layer, from `mistStart` metres out to where the ray
 * sinks below `mistBaseY` (the cloud layer's own fog takes over there). Mirrors sectMistDepth.
 */
export function mistOpticalDepth(c: FogConstants, y0: number, dy: number, t: number): number {
  if (!(c.mistDensity > 0)) return 0;
  const end = dy < 0 ? Math.min(t, Math.max(y0 - c.mistBaseY, 0) / -dy) : t;
  const len = end - c.mistStart;
  if (len <= 0) return 0;
  const b = 1 / c.mistFalloff;
  const y = y0 + dy * c.mistStart;
  return c.mistDensity * Math.exp(Math.min(Math.max(-(y - c.mistBaseY) * b, -80), 80)) * expIntegral(dy * b, len);
}

/** Air optical depth (haze plus valley mist) along a ray from height y0, vertical component dy, length t. */
export function hazeOpticalDepth(c: FogConstants, y0: number, dy: number, t: number): number {
  return hazeLayerDepth(c, y0, dy, t) + mistOpticalDepth(c, y0, dy, t);
}

/** Fraction of a surface's colour replaced by haze (0..1), before the aerial colour shifts. */
export function hazeVeil(c: FogConstants, y0: number, dy: number, t: number): number {
  return 1 - Math.exp(-hazeOpticalDepth(c, y0, dy, t));
}

const LUMA: Vec3 = [0.2126, 0.7152, 0.0722];

function dot3(a: Vec3, b: Vec3): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

/**
 * Haze colour along view direction rd (unit): gold toward the sun, cooling away from it (`cool`
 * scales the cooling; 1 is the deep distance). Mirrors sectHazeColorCool / sectHazeColor.
 */
export function hazeColor(c: FogConstants, base: Vec3, rd: Vec3, cool = 1): Vec3 {
  const mu = dot3(rd, c.sunDir);
  const s = Math.pow(Math.max(mu * 0.5 + 0.5, 0), 3) * c.sunFogMix;
  const warm = base.map((v, i) => v + (c.sunFogColor[i] - v) * s) as Vec3;
  const a = Math.max(0.5 - 0.5 * mu, 0);
  const w = a * a * c.coolMix * cool;
  const l = dot3(warm, LUMA);
  return warm.map((v, i) => v + (l * c.coolTint[i] - v) * w) as Vec3;
}

/** How far the aerial shifts have come in at optical depth od: 0 at hand, toward 1 in thick haze. */
export function aerialFar(c: FogConstants, od: number): number {
  return 1 - Math.exp(-od / Math.max(c.aerialDepth, 1e-3));
}

/** A linear surface colour seen through optical depth `od` of haze along rd. Mirrors sectAerial. */
export function aerialColor(c: FogConstants, col: Vec3, base: Vec3, rd: Vec3, od: number): Vec3 {
  const far = aerialFar(c, od);
  const h = hazeColor(c, base, rd, far);
  const tr = c.extinction.map((k) => Math.exp(-od * (1 + (k - 1) * far))) as Vec3;
  const g = c.desaturate * (1 - tr[1]);
  const k = dot3(col, LUMA) / Math.max(dot3(h, LUMA), 1e-4);
  return col.map((v, i) => (v + (h[i] * k - v) * g) * tr[i] + h[i] * (1 - tr[i])) as Vec3;
}

function fract(x: number): number {
  return x - Math.floor(x);
}

function hash12(x: number, y: number): number {
  let a = fract(x * 0.1031);
  let b = fract(y * 0.1031);
  let c = a;
  const d = a * (b + 33.33) + b * (c + 33.33) + c * (a + 33.33);
  a += d;
  b += d;
  c += d;
  return fract((a + b) * c);
}

/** The dither noise at pixel (x, y), in -1..1 (triangular). Mirrors sectDitherNoise. */
export function ditherNoise(x: number, y: number): number {
  return hash12(x, y) + hash12(x + 57.13, y + 23.71) - 1;
}

/**
 * Dither helpers, shared by the fog chunk (low tier) and the post pass's DitherEffect: triangular
 * noise in -1..1 per pixel (two hashes without sine, after Dave Hoskins; one 8-bit step of it
 * breaks the banding of smooth sky and haze gradients without a visible pattern, Gjøl GDC 2016)
 * and the sRGB transfer both ways (self-contained: three renames its helpers between releases).
 */
export const DITHER_GLSL = /* glsl */ `
float sectHash12( vec2 p ) {
  vec3 p3 = fract( vec3( p.xyx ) * 0.1031 );
  p3 += dot( p3, p3.yzx + 33.33 );
  return fract( ( p3.x + p3.y ) * p3.z );
}
float sectDitherNoise( vec2 p ) {
  return sectHash12( p ) + sectHash12( p + vec2( 57.13, 23.71 ) ) - 1.0;
}
vec3 sectSrgbEncode( vec3 c ) {
  c = max( c, 0.0 );
  return mix( 1.055 * pow( c, vec3( 0.41666667 ) ) - 0.055, c * 12.92, vec3( lessThanEqual( c, vec3( 0.0031308 ) ) ) );
}
vec3 sectSrgbDecode( vec3 c ) {
  c = max( c, 0.0 );
  return mix( pow( ( c + 0.055 ) / 1.055, vec3( 2.4 ) ), c / 12.92, vec3( lessThanEqual( c, vec3( 0.04045 ) ) ) );
}
`;

/**
 * The highlight clip on the direct-to-screen path (the Low tier has no post pass). Glowing surfaces
 * are their baked colour times a glow factor, so they go past 1.0; the screen clips each channel on
 * its own, which turns a cyan ring or an amber lantern white. This is the post pass's
 * HueClipEffect (effects.ts) with a soft knee: past `knee` the largest channel rolls off toward 1
 * (an exponential shoulder), every channel scaled by the same factor so the hue stays, and only
 * very hot cores drift toward white (by up to `white`, from `whiteFrom` to `whiteTo`). The knee
 * matches the grade's shoulder, so lit surfaces barely move (a texel at 1.0 lands at 0.96); it
 * replaces the hard plateau a glow would show without the bloom that hides it on High and Mid.
 */
export const SCREEN_CLIP = { knee: 0.9, whiteFrom: 1.8, whiteTo: 9, white: 0.55 } as const;

/** TypeScript mirror of sectScreenClip (linear in, linear out, every channel at most 1). */
export function screenClip(c: Vec3, k: typeof SCREEN_CLIP = SCREEN_CLIP): Vec3 {
  const x = c.map((v) => Math.max(v, 0)) as Vec3;
  const m = Math.max(x[0], x[1], x[2]);
  if (m <= k.knee) return x;
  const s = k.knee + (1 - k.knee) * (1 - Math.exp(-(m - k.knee) / (1 - k.knee)));
  const t = Math.min(Math.max((m - k.whiteFrom) / (k.whiteTo - k.whiteFrom), 0), 1);
  const w = t * t * (3 - 2 * t) * k.white;
  return x.map((v) => (v * s) / m + (s - (v * s) / m) * w) as Vec3;
}

/** GLSL for the clip: `vec3 sectScreenClip( vec3 linear )`. */
export const SCREEN_CLIP_GLSL = /* glsl */ `
vec3 sectScreenClip( vec3 c ) {
  c = max( c, 0.0 );
  float m = max( max( c.r, c.g ), c.b );
  if ( m <= ${glslFloat(SCREEN_CLIP.knee)} ) return c;
  float s = ${glslFloat(SCREEN_CLIP.knee)} + ${glslFloat(1 - SCREEN_CLIP.knee)} * ( 1.0 - exp( - ( m - ${glslFloat(SCREEN_CLIP.knee)} ) / ${glslFloat(1 - SCREEN_CLIP.knee)} ) );
  vec3 kept = c * ( s / m );
  return mix( kept, vec3( s ), smoothstep( ${glslFloat(SCREEN_CLIP.whiteFrom)}, ${glslFloat(SCREEN_CLIP.whiteTo)}, m ) * ${glslFloat(SCREEN_CLIP.white)} );
}
`;

/** sRGB encode of one linear channel (0..1 in, 0..1 out). */
function srgbEncode(v: number): number {
  const x = Math.max(v, 0);
  return x <= 0.0031308 ? x * 12.92 : 1.055 * Math.pow(x, 1 / 2.4) - 0.055;
}

/**
 * Additive light `l` (linear) as it should be added straight onto the sRGB screen (the Low tier):
 * the step it makes over a background of linear grey `back`, encode(clip(back + l)) - encode(back).
 * Added unencoded, a glow over a bright sky came out about 1.3-1.7 times what High shows (High adds
 * it in linear, then encodes); encoded first, its faint edge many times more. Mirrors sectScreenAdd.
 */
export function screenAdd(l: Vec3, back: number): Vec3 {
  const b = srgbEncode(back);
  const c = screenClip(l.map((v) => back + Math.max(v, 0)) as Vec3);
  return c.map((v) => srgbEncode(v) - b) as Vec3;
}

/**
 * GLSL: `vec3 sectScreenAdd( vec3 light, float back )`, for additive shaders. Into the composer's
 * linear buffer (High and Mid) it returns the light as it is; the test is a constant the compiler
 * folds. Needs SCREEN_CLIP_GLSL.
 */
export const SCREEN_ADD_GLSL = /* glsl */ `
vec3 sectScreenAdd( vec3 l, float back ) {
  if ( linearToOutputTexel( vec4( 0.5 ) ).r <= 0.6 ) return l;
  vec3 b = vec3( back );
  return linearToOutputTexel( vec4( sectScreenClip( b + max( l, 0.0 ) ), 1.0 ) ).rgb - linearToOutputTexel( vec4( b, 1.0 ) ).rgb;
}
`;

const FOG_FUNCTIONS = /* glsl */ `
float sectExpIntegral( float k, float t ) {
  if ( abs( k ) < 1e-5 ) return t;
  return ( 1.0 - exp( clamp( - k * t, - 80.0, 80.0 ) ) ) / k;
}
float sectHazeLayerDepth( float y0, float dy, float t ) {
  float b = 1.0 / SECT_FOG_FALLOFF;
  return SECT_FOG_DENSITY * exp( clamp( - ( y0 - SECT_FOG_BASE_Y ) * b, - 80.0, 80.0 ) ) * sectExpIntegral( dy * b, t );
}
// Valley mist: a thin layer low over the cloud layer (gorge floors, under the islands). It starts
// SECT_MIST_START metres out and stops where the ray sinks into the cloud layer. No noise: noise in
// per-surface fog reads as stains sliding over the cliffs.
float sectMistDepth( float y0, float dy, float t ) {
#ifdef SECT_MIST
  float end = dy < 0.0 ? min( t, max( y0 - SECT_MIST_BASE_Y, 0.0 ) / - dy ) : t;
  float len = end - SECT_MIST_START;
  if ( len <= 0.0 ) return 0.0;
  float b = 1.0 / SECT_MIST_FALLOFF;
  float y = y0 + dy * SECT_MIST_START;
  return SECT_MIST_DENSITY * exp( clamp( - ( y - SECT_MIST_BASE_Y ) * b, - 80.0, 80.0 ) ) * sectExpIntegral( dy * b, len );
#else
  return 0.0;
#endif
}
// The air along a ray: haze plus valley mist (every shader that fogs takes both).
float sectHazeDepth( float y0, float dy, float t ) {
  return sectHazeLayerDepth( y0, dy, t ) + sectMistDepth( y0, dy, t );
}
float sectCloudDepth( float y0, float dy, float t ) {
  float b = 1.0 / SECT_CLOUD_SCALE;
  float od = SECT_CLOUD_DENSITY * exp( clamp( - ( y0 - SECT_CLOUD_TOP ) * b, - 80.0, 80.0 ) ) * sectExpIntegral( dy * b, t );
  return min( od, 80.0 );
}
// Haze colour along rd; cool (0..1) scales the cooling away from the sun.
vec3 sectHazeColorCool( vec3 base, vec3 rd, float cool ) {
  float mu = dot( rd, SECT_SUN_DIR );
  // Broad forward-scatter lobe: full sun colour toward the sun, a little still at 90 degrees.
  float s = pow( max( mu * 0.5 + 0.5, 0.0 ), 3.0 );
  vec3 c = mix( base, SECT_SUN_FOG, s * SECT_SUN_FOG_MIX );
  // Away from the sun it cools toward lavender at its own brightness (golden hour's back light).
  float a = max( 0.5 - 0.5 * mu, 0.0 );
  return mix( c, dot( c, SECT_LUMA ) * SECT_COOL_TINT, a * a * SECT_COOL_MIX * cool );
}
// The haze colour of the deep distance (the sky's horizon, far ridges).
vec3 sectHazeColor( vec3 base, vec3 rd ) {
  return sectHazeColorCool( base, rd, 1.0 );
}
// A linear surface colour seen through optical depth od of haze along rd. The aerial shifts come in
// with depth (far: 0 at hand, 1 once the haze is thick), so the scenery at hand keeps the plain warm
// veil while far ridges go bluer and paler: each channel fades at its own rate, the haze cools away
// from the sun, and what still shows loses colour toward the haze's hue.
vec3 sectAerial( vec3 col, vec3 base, vec3 rd, float od ) {
  float far = 1.0 - exp( - od / SECT_AERIAL_DEPTH );
  vec3 h = sectHazeColorCool( base, rd, far );
  vec3 tr = exp( - od * mix( vec3( 1.0 ), SECT_EXTINCTION, far ) );
  float g = SECT_DESATURATE * ( 1.0 - tr.g );
  col = mix( col, h * ( dot( col, SECT_LUMA ) / max( dot( h, SECT_LUMA ), 1e-4 ) ), g );
  return col * tr + h * ( 1.0 - tr );
}
${DITHER_GLSL}
${SCREEN_CLIP_GLSL}
// An sRGB-encoded colour plus SECT_DITHER 8-bit steps of noise at pixel p (gl_FragCoord.xy): for
// shaders drawing straight to the screen (the low tier has no post pass to dither the frame).
vec3 sectDitherEncoded( vec3 c, vec2 p ) {
  return c + sectDitherNoise( p ) * ( SECT_DITHER / 255.0 );
}
`;

/** #defines shared by the fog chunks and the sky shader. */
export function fogDefines(c: FogConstants): string {
  return [
    `#define SECT_FOG_DENSITY ${glslFloat(c.density)}`,
    `#define SECT_FOG_BASE_Y ${glslFloat(c.baseY)}`,
    `#define SECT_FOG_FALLOFF ${glslFloat(c.falloff)}`,
    `#define SECT_CLOUD_TOP ${glslFloat(c.cloudTop)}`,
    `#define SECT_CLOUD_SCALE ${glslFloat(c.cloudScale)}`,
    `#define SECT_CLOUD_DENSITY ${glslFloat(c.cloudDensity)}`,
    `#define SECT_SUN_DIR ${glslVec3(c.sunDir)}`,
    `#define SECT_SUN_FOG ${glslVec3(c.sunFogColor)}`,
    `#define SECT_SUN_FOG_MIX ${glslFloat(c.sunFogMix)}`,
    `#define SECT_CLOUD_FOG ${glslVec3(c.cloudColor)}`,
    `#define SECT_SKY_HAZE ${glslFloat(c.skyHaze)}`,
    `#define SECT_LUMA ${glslVec3(LUMA)}`,
    `#define SECT_EXTINCTION ${glslVec3(c.extinction)}`,
    `#define SECT_COOL_TINT ${glslVec3(c.coolTint)}`,
    `#define SECT_COOL_MIX ${glslFloat(c.coolMix)}`,
    `#define SECT_DESATURATE ${glslFloat(c.desaturate)}`,
    `#define SECT_AERIAL_DEPTH ${glslFloat(Math.max(c.aerialDepth, 1e-3))}`,
    c.mistDensity > 0 ? "#define SECT_MIST" : "",
    `#define SECT_MIST_DENSITY ${glslFloat(c.mistDensity)}`,
    `#define SECT_MIST_BASE_Y ${glslFloat(c.mistBaseY)}`,
    `#define SECT_MIST_FALLOFF ${glslFloat(Math.max(c.mistFalloff, 1))}`,
    `#define SECT_MIST_START ${glslFloat(c.mistStart)}`,
    `#define SECT_DITHER ${glslFloat(c.dither)}`,
  ]
    .filter((l) => l.length > 0)
    .join("\n");
}

/** Haze maths for custom shaders that are not fogged by three (the sky dome). */
export function fogLibrary(c: FogConstants): string {
  return `${fogDefines(c)}\n${FOG_FUNCTIONS}`;
}

export interface FogChunks {
  fog_pars_vertex: string;
  fog_vertex: string;
  fog_pars_fragment: string;
  fog_fragment: string;
}

/** Replacements for THREE.ShaderChunk.fog_*; scene.fog only supplies USE_FOG and fogColor. */
export function fogChunks(c: FogConstants): FogChunks {
  return {
    fog_pars_vertex: /* glsl */ `
#ifdef USE_FOG
  varying float vFogDepth;
  varying vec3 vFogWorldPos;
#endif
`,
    fog_vertex: /* glsl */ `
#ifdef USE_FOG
  vFogDepth = - mvPosition.z;
  vFogWorldPos = transpose( mat3( viewMatrix ) ) * ( mvPosition.xyz - viewMatrix[ 3 ].xyz );
#endif
`,
    fog_pars_fragment: /* glsl */ `
#ifdef USE_FOG
  uniform vec3 fogColor;
  varying float vFogDepth;
  varying vec3 vFogWorldPos;
  #ifdef FOG_EXP2
    uniform float fogDensity;
  #else
    uniform float fogNear;
    uniform float fogFar;
  #endif
${fogDefines(c)}
${FOG_FUNCTIONS}
#endif
`,
    // three runs fog after its colour-space step. Into the composer's linear buffer (mid and high
    // tiers) that step does nothing. Straight to the sRGB screen (the low tier) the colour and
    // three's fogColor arrive encoded, so they are decoded, fogged in linear like everywhere else,
    // clipped keeping their hue (sectScreenClip: no post pass clips or dithers that frame), encoded
    // again and dithered there. The test is a constant
    // the compiler folds.
    // The cloud layer lies at the far end of a ray that sinks into it, with the haze between it and
    // the camera: cloud first, then the haze over both (as on the cloud sea itself, which is hazed
    // the same way). The other order left the foot of a far cliff in the bare, bright cloud colour, a
    // hard ring against the hazed sea beside it.
    fog_fragment: /* glsl */ `
#ifdef USE_FOG
  vec3 sectRd = vFogWorldPos - cameraPosition;
  float sectT = length( sectRd );
  sectRd /= max( sectT, 1e-4 );
  bool sectEncoded = linearToOutputTexel( vec4( 0.5 ) ).r > 0.6;
  vec3 sectC = sectEncoded ? sectSrgbDecode( gl_FragColor.rgb ) : gl_FragColor.rgb;
  vec3 sectBase = sectEncoded ? sectSrgbDecode( fogColor ) : fogColor;
  sectC = mix( sectC, SECT_CLOUD_FOG, 1.0 - exp( - sectCloudDepth( cameraPosition.y, sectRd.y, sectT ) ) );
  sectC = sectAerial( sectC, sectBase, sectRd, sectHazeDepth( cameraPosition.y, sectRd.y, sectT ) );
  gl_FragColor.rgb = sectEncoded ? sectDitherEncoded( sectSrgbEncode( sectScreenClip( sectC ) ), gl_FragCoord.xy ) : sectC;
#endif
`,
  };
}

/**
 * AgX with Blender's "Punchy" look, self-contained (three only defines its tone-mapping helpers
 * when renderer tone mapping is on, and the composer forces it off). Linear sRGB in and out.
 * Used only for lit stand-in materials; baked textures already carry Blender's view transform.
 */
export const AGX_PUNCHY_GLSL = /* glsl */ `
const mat3 SECT_SRGB_TO_REC2020 = mat3(
  vec3( 0.6274, 0.0691, 0.0164 ),
  vec3( 0.3293, 0.9195, 0.0880 ),
  vec3( 0.0433, 0.0113, 0.8956 )
);
const mat3 SECT_REC2020_TO_SRGB = mat3(
  vec3( 1.6605, - 0.1246, - 0.0182 ),
  vec3( - 0.5876, 1.1329, - 0.1006 ),
  vec3( - 0.0728, - 0.0083, 1.1187 )
);
const mat3 SECT_AGX_INSET = mat3(
  vec3( 0.856627153315983, 0.137318972929847, 0.11189821299995 ),
  vec3( 0.0951212405381588, 0.761241990602591, 0.0767994186031903 ),
  vec3( 0.0482516061458583, 0.101439036467562, 0.811302368396859 )
);
const mat3 SECT_AGX_OUTSET = mat3(
  vec3( 1.1271005818144368, - 0.1413297634984383, - 0.14132976349843826 ),
  vec3( - 0.11060664309660323, 1.157823702216272, - 0.11060664309660294 ),
  vec3( - 0.016493938717834573, - 0.016493938717834257, 1.2519364065950405 )
);
vec3 sectAgxContrast( vec3 x ) {
  vec3 x2 = x * x;
  vec3 x4 = x2 * x2;
  return 15.5 * x4 * x2 - 40.14 * x4 * x + 31.96 * x4 - 6.868 * x2 * x + 0.4298 * x2 + 0.1191 * x - 0.00232;
}
vec3 sectAgxPunchy( vec3 color ) {
  color = SECT_AGX_INSET * ( SECT_SRGB_TO_REC2020 * color );
  color = clamp( ( log2( max( color, 1e-10 ) ) + 12.47393 ) / 16.499999, 0.0, 1.0 );
  color = sectAgxContrast( color );
  float luma = dot( color, vec3( 0.2126, 0.7152, 0.0722 ) );
  color = pow( max( color, 0.0 ), vec3( 1.35 ) );
  color = luma + 1.4 * ( color - luma );
  color = SECT_AGX_OUTSET * color;
  color = pow( max( vec3( 0.0 ), color ), vec3( 2.2 ) );
  return clamp( SECT_REC2020_TO_SRGB * color, 0.0, 1.0 );
}
`;
