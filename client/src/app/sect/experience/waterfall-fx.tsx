"use client";

/**
 * Life at the foot of the waterfalls that land on ground (lib/sect/water.ts fallFeet; today the
 * Cave Abode's): a foam skirt on the pool, spray drops and rising mist puffs. Three draws for every
 * foot in view together:
 *
 * - Foam skirt (world scene, before the sheets): one mesh of every foot's polar grid with a boil
 *   mound in the middle that covers the bake's frozen foam disc and splash blobs. Foam drifts
 *   outward in two layers (public/sect/fx/foam.webp once it is there; the shared noise texture
 *   until then), dense white in the middle, lace at the rim. Fogged by three's fog chunks (the
 *   scene's aerial haze, dithered on the low tier).
 * - Spray (overlay scene): one instanced draw of camera-facing streaks thrown on ballistic arcs
 *   from a ring around each foot (water.ts sprayDrop, mirrored in WFX_GLSL); drops toward the sun
 *   glint above 1.0 so bloom catches them. Shared by the feet in view (up to WATERFALL_FX.slots).
 * - Mist puffs (overlay scene): one instanced draw of soft sprites rising, rolling outward and
 *   drifting downwind (water.ts mistPuff), their shapes from Thomas Iche's CC0 flipbooks
 *   (public/sect/fx/mist_flipbook.webp, two frames blended), lit from the sun side, faded where
 *   they meet the ground (soft depth on the high and mid tiers) and at their bottom edge.
 *
 * All motion runs in the vertex shaders on the shared waterfall clock; the CPU only sets a few
 * uniforms a frame (no allocations). A foot's effects draw while its chunk does and it is in view,
 * fading with distance. With reduced motion the clock stands still: the skirt and mist hold, and
 * the spray (drops frozen in mid-air) is hidden.
 */
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import {
  BufferAttribute,
  BufferGeometry,
  ClampToEdgeWrapping,
  Color,
  Frustum,
  ImageBitmapLoader,
  ImageLoader,
  InstancedBufferAttribute,
  InstancedBufferGeometry,
  type IUniform,
  LinearFilter,
  LinearMipmapLinearFilter,
  Matrix4,
  Mesh,
  NoColorSpace,
  PlaneGeometry,
  RepeatWrapping,
  type Scene,
  ShaderMaterial,
  Sphere,
  Texture,
  UniformsLib,
  UniformsUtils,
  Vector3,
  Vector4,
} from "three";
import { fogLibrary, glslFloat, type FogConstants } from "@/lib/sect/glsl";
import { SECT_LOOK } from "@/lib/sect/look";
import type { Quality } from "@/lib/sect/runtime";
import type { SectMeta } from "@/lib/sect/types";
import {
  buildSkirts,
  distanceFade,
  fallFeet,
  fxAssetUrl,
  fxTier,
  pickFootSlots,
  WATERFALL_FX,
  WFX_GLSL,
  type FallFoot,
} from "@/lib/sect/water";
import type { LoadedSet } from "./assets";
import { getNoiseTexture, SOFT_DEPTH } from "./materials";
import type { SectStore } from "./store";

const f = glslFloat;
const SLOTS = WATERFALL_FX.slots;
const GRID = WATERFALL_FX.flipbookGrid;

/** Files in public/sect/fx (fxAssetUrl): the mist flipbook (prep_textures.mjs --mist-flipbook) and the foam tile. */
export const WFX_FILES = { flipbook: "mist_flipbook.webp", foam: "foam.webp" } as const;

/** Colours (sRGB hex): foam, the churned water under it darkening into the pool (the bake's #11252a), spray, and the mist's lit and shaded sides. */
const WFX_COLORS = {
  foam: SECT_LOOK.waterfall.foam,
  water: "#4f7276",
  deep: "#16292d",
  spray: SECT_LOOK.waterfall.mist,
  mistLit: SECT_LOOK.waterfall.mist,
  mistShade: "#c8bcb8",
  mistRim: SECT_LOOK.puffs.rim,
} as const;

/** Off the clip volume, so nothing rasterises (a faded or unused instance). */
const CULL = "gl_Position = vec4( 2.0, 2.0, 2.0, 1.0 ); return;";

/** Soft edges against the scene depth (materials.ts SOFT_PARS, with the shared SOFT_DEPTH uniforms). */
const SOFT_PARS = /* glsl */ `
#include <packing>
uniform sampler2D tDepth;
uniform float uHasDepth;
uniform vec2 uResolution;
uniform float uNear;
uniform float uFar;
float wfxSoftFade( float fragViewZ, float len ) {
  if ( uHasDepth < 0.5 ) return 1.0;
  float d = texture2D( tDepth, gl_FragCoord.xy / uResolution ).r;
  if ( d >= 1.0 ) return 1.0;
  float sceneZ = perspectiveDepthToViewZ( d, uNear, uFar );
  return smoothstep( 0.0, max( len, 1e-3 ), fragViewZ - sceneZ );
}
`;

/** The air between the camera and a sprite (the scene's aerial haze and the cloud layer). */
const SPRITE_FOG = /* glsl */ `
vec3 wfxFog( vec3 col, vec3 base, vec3 rd, float dist ) {
  col = sectAerial( col, base, rd, sectHazeDepth( cameraPosition.y, rd.y, dist ) );
  return mix( col, SECT_CLOUD_FOG, 1.0 - exp( - sectCloudDepth( cameraPosition.y, rd.y, dist ) ) );
}
`;

/** Per-slot uniforms of the spray and mist draws: a foot's centre on the pool and weight, and its shape. */
interface SlotUniforms {
  [name: string]: IUniform;
  uSlots: IUniform<number>;
  uFeet: IUniform<Vector4[]>;
  uShape: IUniform<Vector4[]>;
}

function slotUniforms(): SlotUniforms {
  return {
    uSlots: { value: 0 },
    uFeet: { value: Array.from({ length: SLOTS }, () => new Vector4()) },
    uShape: { value: Array.from({ length: SLOTS }, () => new Vector4()) },
  };
}

const SLOT_PARS = /* glsl */ `
uniform float uSlots;
uniform vec4 uFeet[ ${SLOTS} ];
uniform vec4 uShape[ ${SLOTS} ];
`;

// ---------------------------------------------------------------------------------------------
// Foam skirt

function skirtMaterial(time: IUniform<number>, feet: number, sunDir: readonly [number, number, number]): ShaderMaterial {
  const S = WATERFALL_FX.skirt;
  const uniforms: Record<string, IUniform> = UniformsUtils.merge([
    UniformsLib.fog,
    {
      uFoam: { value: new Color(WFX_COLORS.foam) },
      uWater: { value: new Color(WFX_COLORS.water) },
      uDeep: { value: new Color(WFX_COLORS.deep) },
      uSunDir: { value: new Vector3(...sunDir).normalize() },
      uHasFoam: { value: 0 },
    },
  ]);
  // Shared objects (merge clones values): the clock, the textures and the per-foot weights.
  uniforms.uTime = time;
  uniforms.tNoise = { value: getNoiseTexture() };
  uniforms.tFoam = { value: null };
  uniforms.uFootW = { value: new Float32Array(Math.max(feet, 1)) };
  return new ShaderMaterial({
    name: "sect.waterfall.skirt",
    transparent: true,
    depthWrite: false,
    // One pass (a transparent double-sided material draws twice); the triangles face up.
    fog: true,
    uniforms,
    vertexShader: /* glsl */ `
#include <fog_pars_vertex>
attribute vec4 skirt;
uniform float uTime;
uniform vec3 uSunDir;
uniform float uFootW[ ${Math.max(feet, 1)} ];
varying vec2 vUv;
varying float vR;
varying float vWidth;
varying float vW;
varying float vShade;
void main() {
  vUv = uv;
  vR = skirt.x;
  vWidth = skirt.w;
  vW = uFootW[ int( skirt.y + 0.5 ) ];
  vec3 p = position;
  // The boil heaves (most in the middle; whole turns of the angle, so the seam stays shut).
  float ang = uv.x * 6.2831853;
  float heave = 1.0 - smoothstep( 0.0, ${f(S.boilOut)}, uv.y );
  p.y += heave * min( vWidth / 6.0, 1.5 ) * ( 0.1 * sin( uTime * 2.3 + ang * 3.0 + uv.y * 9.0 ) + 0.07 * sin( uTime * 3.7 - ang * 5.0 + uv.y * 4.0 ) );
  // The mound's sides catch the low sun or turn from it (normal from the profile's slope).
  vec3 n = normalize( vec3( - skirt.z * cos( ang ), 1.0, - skirt.z * sin( ang ) ) );
  vShade = 0.8 + 0.28 * max( dot( n, uSunDir ), 0.0 ) + 0.06 * n.y;
  vec4 mvPosition = viewMatrix * modelMatrix * vec4( p, 1.0 );
  gl_Position = projectionMatrix * mvPosition;
  if ( vW < 0.003 ) gl_Position = vec4( 2.0, 2.0, 2.0, 1.0 );
  #include <fog_vertex>
}
`,
    fragmentShader: /* glsl */ `
#include <common>
#include <fog_pars_fragment>
uniform float uTime;
uniform sampler2D tNoise;
uniform sampler2D tFoam;
uniform float uHasFoam;
uniform vec3 uFoam;
uniform vec3 uWater;
uniform vec3 uDeep;
varying vec2 vUv;
varying float vR;
varying float vWidth;
varying float vW;
varying float vShade;
// One return (an early return inside the branch makes ANGLE's D3D compiler warn X4000).
float wfxFoamAt( vec2 st ) {
  float foam;
  if ( uHasFoam > 0.5 ) {
    vec4 t = texture2D( tFoam, st );
    foam = dot( t.rgb, vec3( 0.2126, 0.7152, 0.0722 ) ) * t.a;
  } else {
    // Stand-in until foam.webp is there: the shared fractal noise, cut into blotches.
    float n = texture2D( tNoise, st * 0.5 ).r * 0.65 + texture2D( tNoise, st * 1.3 + 0.37 ).r * 0.35;
    foam = smoothstep( 0.4, 0.66, n );
  }
  return foam;
}
void main() {
  float k = vUv.y;
  float r = k * vR;
  float wd = max( vWidth, 1.0 );
  // Two layers drifting outward; whole tiles around the ring, so the seam does not show.
  float n0 = max( 1.0, floor( 3.14159 * vR / ${f(S.tile[0])} + 0.5 ) );
  float n1 = max( 1.0, floor( 3.14159 * vR / ${f(S.tile[1])} + 0.5 ) );
  vec2 q0 = vec2( vUv.x * n0, ( r - uTime * ${f(S.outward[0])} ) / ${f(S.tile[0])} );
  vec2 q1 = vec2( vUv.x * n1 + 0.37, ( r - uTime * ${f(S.outward[1])} ) / ${f(S.tile[1])} + 0.21 );
  float f0 = wfxFoamAt( q0 );
  float f1 = wfxFoamAt( q1 );
  float foam = max( f0, f1 * 0.85 );
  // White water: solid on the boil, breaking into lace outward (in widths of the fall).
  float th = smoothstep( 0.2 * wd, 1.05 * wd, r ) * 0.9;
  float white = smoothstep( th - 0.12, th + 0.12, foam );
  white = max( white, 1.0 - smoothstep( 0.18 * wd, 0.4 * wd, r ) );
  // Aerated water under it, out past the bake's foam disc (0.85 x width), darkening into the pool.
  float veil = 0.92 * ( 1.0 - smoothstep( 1.15 * wd, 1.42 * wd, r + ( f0 - 0.5 ) * 1.2 ) );
  float a = max( white, veil ) * ( 1.0 - smoothstep( 0.86, 1.0, k + ( f1 - 0.5 ) * 0.1 ) );
  a *= vW;
  if ( a < 0.01 ) discard;
  // Ripples running outward through the churned water.
  float rip = sin( ( r - uTime * 1.4 ) * 3.9 + ( f0 - 0.5 ) * 2.5 );
  vec3 water = mix( uWater, uDeep, smoothstep( 0.35 * wd, 1.1 * wd, r ) ) * ( 0.85 + 0.3 * f1 + 0.12 * rip );
  vec3 col = mix( water, uFoam * ( 0.8 + 0.2 * foam ), white ) * vShade;
  gl_FragColor = vec4( col, a );
  #include <colorspace_fragment>
  #include <fog_fragment>
}
`,
  });
}

// ---------------------------------------------------------------------------------------------
// Spray

function sprayMaterial(fog: FogConstants, fogColor: string, sunColor: string, time: IUniform<number>): ShaderMaterial {
  const S = WATERFALL_FX.spray;
  return new ShaderMaterial({
    name: "sect.waterfall.spray",
    transparent: true,
    depthWrite: false,
    fog: false,
    uniforms: {
      ...slotUniforms(),
      uTime: time,
      uViewH: { value: 1080 },
      uColor: { value: new Color(WFX_COLORS.spray) },
      uSun: { value: new Color(sunColor) },
      uFogColor: { value: new Color(fogColor) },
    },
    vertexShader: /* glsl */ `
attribute vec4 iSeed;
attribute float iIndex;
uniform float uTime;
uniform float uViewH;
${SLOT_PARS}
varying vec2 vUv;
varying float vAlpha;
varying vec3 vDir;
varying float vDist;
varying float vGlint;
${WFX_GLSL}
void main() {
  if ( uSlots < 0.5 ) { ${CULL} }
  int slot = int( mod( iIndex, uSlots ) );
  vec4 foot = uFeet[ slot ];
  vec4 shape = uShape[ slot ];
  vec3 vel;
  vec4 d = wfxSpray( iSeed, uTime, shape.x, shape.y, vel );
  float a = d.w * foot.w;
  if ( a < 0.003 ) { ${CULL} }
  vec3 c = foot.xyz + d.xyz;
  vec3 toC = c - cameraPosition;
  float dist = max( length( toC ), 1e-3 );
  vec3 fwd = toC / dist;
  float speed = length( vel );
  vec3 axis = speed > 1e-3 ? vel / speed : vec3( 0.0, 1.0, 0.0 );
  vec3 side = cross( axis, fwd );
  float sl = length( side );
  side = sl > 1e-3 ? side / sl : normalize( cross( vec3( 0.0, 1.0, 0.0 ), fwd ) + vec3( 1e-4, 0.0, 0.0 ) );
  float size = mix( ${f(S.size[0])}, ${f(S.size[1])}, fract( iSeed.z * 7.13 + iSeed.x * 3.7 ) );
  // At least about a pixel wide: a thinner drop is drawn wider and fainter.
  float px = 2.0 * dist / ( projectionMatrix[ 1 ][ 1 ] * uViewH );
  float w = max( size, 1.1 * px );
  a *= size / w;
  // Streaked along its flight over about a thirtieth of a second.
  float len = w + speed * 0.035;
  vec3 wp = c + side * position.x * w + axis * position.y * len;
  vUv = position.xy;
  vAlpha = a;
  vDir = fwd;
  vDist = dist;
  // Glints re-rolled eight times a second.
  vGlint = wfxHash( iSeed.y * 31.7 + floor( uTime * 8.0 + iSeed.w * 8.0 ) );
  gl_Position = projectionMatrix * viewMatrix * vec4( wp, 1.0 );
}
`,
    fragmentShader: /* glsl */ `
uniform vec3 uColor;
uniform vec3 uSun;
uniform vec3 uFogColor;
varying vec2 vUv;
varying float vAlpha;
varying vec3 vDir;
varying float vDist;
varying float vGlint;
${fogLibrary(fog)}
${SPRITE_FOG}
void main() {
  float q = length( vUv );
  float a = ( 1.0 - smoothstep( 0.35, 1.0, q ) ) * vAlpha * 0.85;
  if ( a < 0.01 ) discard;
  // Drops between the eye and the sun light up (forward scatter); a few glint past 1.0 for bloom.
  float toward = pow( max( dot( vDir, SECT_SUN_DIR ), 0.0 ), 6.0 );
  vec3 col = uColor * ( 0.82 + 0.2 * ( 1.0 - q ) ) + uSun * toward * ( 0.5 + 1.8 * step( 0.8, vGlint ) );
  gl_FragColor = vec4( wfxFog( col, uFogColor, vDir, vDist ), a );
  #include <colorspace_fragment>
}
`,
  });
}

// ---------------------------------------------------------------------------------------------
// Mist puffs

function puffMaterial(fog: FogConstants, fogColor: string, time: IUniform<number>): ShaderMaterial {
  return new ShaderMaterial({
    name: "sect.waterfall.mist",
    transparent: true,
    depthWrite: false,
    fog: false,
    uniforms: {
      ...slotUniforms(),
      ...SOFT_DEPTH,
      uTime: time,
      uPerFoot: { value: WATERFALL_FX.puffs.count.high },
      tFlip: { value: null },
      uHasFlip: { value: 0 },
      tNoise: { value: getNoiseTexture() },
      uLit: { value: new Color(WFX_COLORS.mistLit) },
      uShade: { value: new Color(WFX_COLORS.mistShade) },
      uRim: { value: new Color(WFX_COLORS.mistRim) },
      uFogColor: { value: new Color(fogColor) },
    },
    vertexShader: /* glsl */ `
attribute vec4 iSeed;
attribute vec2 iSlot;
uniform float uTime;
uniform float uPerFoot;
${SLOT_PARS}
varying vec2 vUv;
varying vec3 vLook;
varying vec3 vDir;
varying float vDist;
varying float vViewZ;
varying float vRadius;
varying float vUp;
${WFX_GLSL}
void main() {
  if ( iSlot.x >= uSlots || iSlot.y >= uPerFoot ) { ${CULL} }
  int slot = int( iSlot.x + 0.5 );
  vec4 foot = uFeet[ slot ];
  vec4 shape = uShape[ slot ];
  vec3 look;
  vec4 p = wfxPuff( iSeed, uTime, shape.x, shape.y, look );
  vec3 c = foot.xyz + p.xyz;
  float radius = p.w;
  vec3 toC = c - cameraPosition;
  float dist = max( length( toC ), 1e-3 );
  vec3 fwd = toC / dist;
  // Gone when the camera is in it (a puff around the eye would fill the screen).
  float a = look.x * foot.w * smoothstep( radius * 0.8, radius * 2.5, dist );
  if ( a < 0.002 ) { ${CULL} }
  vec3 up = abs( fwd.y ) > 0.985 ? vec3( 1.0, 0.0, 0.0 ) : vec3( 0.0, 1.0, 0.0 );
  vec3 r = normalize( cross( fwd, up ) );
  vec3 u = cross( r, fwd );
  // A slow turn per puff, so the frames do not repeat in step.
  float spin = iSeed.x * 6.2831853 + uTime * ( iSeed.y - 0.5 ) * 0.25;
  vec2 q = mat2( cos( spin ), sin( spin ), - sin( spin ), cos( spin ) ) * position.xy;
  vec3 wp = c + ( r * q.x + u * q.y ) * radius;
  vUv = position.xy;
  vLook = vec3( a, look.y, look.z );
  vDir = fwd;
  vDist = dist;
  vRadius = radius;
  vUp = q.y;
  vec4 mv = viewMatrix * vec4( wp, 1.0 );
  vViewZ = mv.z;
  gl_Position = projectionMatrix * mv;
}
`,
    fragmentShader: /* glsl */ `
uniform sampler2D tFlip;
uniform float uHasFlip;
uniform sampler2D tNoise;
uniform vec3 uLit;
uniform vec3 uShade;
uniform vec3 uRim;
uniform vec3 uFogColor;
varying vec2 vUv;
varying vec3 vLook;
varying vec3 vDir;
varying float vDist;
varying float vViewZ;
varying float vRadius;
varying float vUp;
${SOFT_PARS}
${fogLibrary(fog)}
${SPRITE_FOG}
// One frame of the flipbook (frame 0 top-left, row-major; uploaded without a flip, so file row 0 is v = 0).
float wfxFrame( vec2 st, float frame, float layer ) {
  vec2 cell = vec2( mod( frame, ${f(GRID)} ), floor( frame / ${f(GRID)} ) );
  vec4 t = texture2D( tFlip, ( cell + vec2( st.x, 1.0 - st.y ) ) / ${f(GRID)} );
  return layer < 0.5 ? t.r : ( layer < 1.5 ? t.g : t.b );
}
void main() {
  float q = length( vUv );
  if ( q > 1.0 ) discard;
  vec2 st = vUv * 0.5 + 0.5;
  float dens;
  if ( uHasFlip > 0.5 ) {
    float f0 = floor( vLook.y );
    dens = mix( wfxFrame( st, f0, vLook.z ), wfxFrame( st, min( f0 + 1.0, ${f(GRID * GRID - 1)} ), vLook.z ), vLook.y - f0 );
  } else {
    float n = texture2D( tNoise, st * 0.45 + vLook.zz * 0.31 + vLook.y * 0.013 ).r;
    dens = 1.0 - smoothstep( 0.15, 1.0, q + ( n - 0.5 ) * 0.5 );
  }
  // The bottom melts into the pool (no straight cut, also on the low tier without scene depth).
  float a = dens * vLook.x * smoothstep( -1.0, -0.2, vUp );
  a *= wfxSoftFade( vViewZ, vRadius * 0.5 );
  if ( a < 0.003 ) discard;
  // Lit tops, shaded undersides, a warm rim looking toward the sun.
  float light = clamp( 0.5 + 0.35 * vUp + 0.3 * ( dens - 0.5 ), 0.0, 1.0 );
  vec3 col = mix( uShade, uLit, light );
  col += uRim * pow( max( dot( vDir, SECT_SUN_DIR ), 0.0 ), 4.0 ) * ( 1.0 - dens ) * 0.8;
  gl_FragColor = vec4( wfxFog( col, uFogColor, vDir, vDist ), a );
  #include <colorspace_fragment>
}
`,
  });
}

// ---------------------------------------------------------------------------------------------

/** Seeds in 0..1 (a fixed sequence, so every visit looks the same). */
function seeds(n: number, salt: number): Float32Array {
  const out = new Float32Array(n * 4);
  let s = 1013 + salt * 7919;
  for (let i = 0; i < out.length; i++) {
    s = (s * 16807) % 2147483647;
    out[i] = s / 2147483647;
  }
  // Spread the cycle phases evenly, so the drops and puffs do not start together.
  for (let i = 0; i < n; i++) out[i * 4 + 3] = (i * 0.618034) % 1;
  return out;
}

/** An empty texture filled by loadFxImage; data, not colour; uploaded without a flip. */
function fxTexture(repeat: boolean): Texture {
  const tex = new Texture();
  tex.colorSpace = NoColorSpace;
  tex.flipY = false;
  tex.wrapS = tex.wrapT = repeat ? RepeatWrapping : ClampToEdgeWrapping;
  tex.magFilter = LinearFilter;
  tex.minFilter = LinearMipmapLinearFilter;
  tex.generateMipmaps = true;
  return tex;
}

/** Loads an image into `tex` (decoded off the main thread where the browser can); `onReady` once it is there. */
function loadFxImage(url: string, tex: Texture, isLive: () => boolean, onReady: () => void): void {
  const done = (image: ImageBitmap | HTMLImageElement) => {
    if (!isLive()) {
      if (typeof ImageBitmap !== "undefined" && image instanceof ImageBitmap) image.close();
      return;
    }
    tex.image = image;
    tex.needsUpdate = true;
    onReady();
  };
  const failed = () => console.warn(`[sect] ${url} did not load; the waterfall foot keeps its stand-in`);
  if (typeof createImageBitmap !== "undefined") {
    new ImageBitmapLoader().setOptions({ premultiplyAlpha: "none", colorSpaceConversion: "none" }).load(url, done, undefined, failed);
  } else {
    new ImageLoader().load(url, done, undefined, failed);
  }
}

function setVisible(m: Mesh, on: boolean): void {
  if (m.visible !== on) m.visible = on;
}

/** Whether the set holding a foot's pool is drawn this frame (null: the global set). */
function chunkDrawn(chunk: string | null, sets: readonly LoadedSet[]): boolean {
  const id = chunk === null || chunk === "backdrop" ? "global" : chunk;
  for (const s of sets) if (s.id === id) return s.drawn && !s.dropped;
  return false;
}

export interface WaterfallFxProps {
  meta: SectMeta;
  /** The asset set's folder (WorldContext data.base); the textures are in its sibling fx/. */
  base: string;
  /** The shared waterfall clock (WorldContext waterfallMaterial uTime; 0 with reduced motion). */
  time: IUniform<number>;
  sets: readonly LoadedSet[];
  store: SectStore;
  fog: FogConstants;
  quality: Quality;
  /** The overlay scene (spray and mist draw there, after the world, with its depth). */
  overlay: Scene;
}

export function WaterfallFx({ meta, base, time, sets, store, fog, quality, overlay }: WaterfallFxProps) {
  const built = useMemo(() => {
    const feet: FallFoot[] = fallFeet(meta.waterfalls, meta.areas, meta.cloudSea.fogTopY);
    if (feet.length === 0) return null;

    const sk = buildSkirts(feet);
    const skirtGeo = new BufferGeometry();
    skirtGeo.setAttribute("position", new BufferAttribute(sk.positions, 3));
    skirtGeo.setAttribute("uv", new BufferAttribute(sk.uv, 2));
    skirtGeo.setAttribute("skirt", new BufferAttribute(sk.skirt, 4));
    skirtGeo.setIndex(new BufferAttribute(sk.index, 1));
    skirtGeo.computeBoundingSphere();
    const skirtMat = skirtMaterial(time, feet.length, meta.sun.direction);
    const skirt = new Mesh(skirtGeo, skirtMat);
    skirt.name = "sect.waterfall.skirt";
    // Before the sheets (renderOrder 2): the water falls into the foam.
    skirt.renderOrder = 1;
    skirt.visible = false;

    const quad = new PlaneGeometry(2, 2);
    const sprayN = WATERFALL_FX.spray.count.high;
    const sprayGeo = new InstancedBufferGeometry();
    sprayGeo.setIndex(quad.getIndex());
    sprayGeo.setAttribute("position", quad.getAttribute("position"));
    sprayGeo.setAttribute("iSeed", new InstancedBufferAttribute(seeds(sprayN, 1), 4));
    sprayGeo.setAttribute("iIndex", new InstancedBufferAttribute(Float32Array.from({ length: sprayN }, (_, i) => i), 1));
    sprayGeo.instanceCount = sprayN;
    const sprayMat = sprayMaterial(fog, meta.fog.color, meta.sun.color, time);
    const spray = new Mesh(sprayGeo, sprayMat);
    spray.name = "sect.waterfall.spray";
    spray.frustumCulled = false;
    spray.renderOrder = 5;
    spray.visible = false;

    const PM = WATERFALL_FX.puffs.max;
    const puffN = SLOTS * PM;
    const puffGeo = new InstancedBufferGeometry();
    puffGeo.setIndex(quad.getIndex());
    puffGeo.setAttribute("position", quad.getAttribute("position"));
    puffGeo.setAttribute("iSeed", new InstancedBufferAttribute(seeds(puffN, 2), 4));
    const slot = new Float32Array(puffN * 2);
    for (let i = 0; i < puffN; i++) slot.set([Math.floor(i / PM), i % PM], i * 2);
    puffGeo.setAttribute("iSlot", new InstancedBufferAttribute(slot, 2));
    puffGeo.instanceCount = puffN;
    const puffMat = puffMaterial(fog, meta.fog.color, time);
    const puffs = new Mesh(puffGeo, puffMat);
    puffs.name = "sect.waterfall.mist";
    puffs.frustumCulled = false;
    puffs.renderOrder = 4;
    puffs.visible = false;

    const flipTex = fxTexture(false);
    flipTex.name = "sect.waterfall.flipbook";
    puffMat.uniforms.tFlip.value = flipTex;
    const foamTex = fxTexture(true);
    foamTex.name = "sect.waterfall.foam";
    skirtMat.uniforms.tFoam.value = foamTex;

    // Per-frame scratch (no allocations in the frame loop).
    const n = feet.length;
    return {
      feet,
      skirt,
      spray,
      puffs,
      quad,
      flipTex,
      foamTex,
      dist: new Float64Array(n),
      sprayW: new Float64Array(n),
      puffW: new Float64Array(n),
      order: new Int32Array(SLOTS),
      frustum: new Frustum(),
      m: new Matrix4(),
      sphere: new Sphere(),
    };
  }, [meta, fog, time]);

  // Overlay draws while mounted.
  useEffect(() => {
    if (!built) return;
    overlay.add(built.spray, built.puffs);
    return () => {
      overlay.remove(built.spray, built.puffs);
    };
  }, [built, overlay]);

  // Textures load once mounted. Unmounting frees the GPU copies; the decoded images stay with
  // `built` (garbage once it goes), so a remount (StrictMode, hot reload) re-uploads them.
  useEffect(() => {
    if (!built) return;
    let live = true;
    const isLive = () => live;
    const puffU = (built.puffs.material as ShaderMaterial).uniforms;
    const skirtU = (built.skirt.material as ShaderMaterial).uniforms;
    if (!built.flipTex.image) loadFxImage(fxAssetUrl(base, WFX_FILES.flipbook), built.flipTex, isLive, () => (puffU.uHasFlip.value = 1));
    if (!built.foamTex.image) loadFxImage(fxAssetUrl(base, WFX_FILES.foam), built.foamTex, isLive, () => (skirtU.uHasFoam.value = 1));
    return () => {
      live = false;
      for (const t of [built.flipTex, built.foamTex]) t.dispose();
      for (const m of [built.skirt, built.spray, built.puffs]) {
        m.geometry.dispose();
        (m.material as ShaderMaterial).dispose();
      }
      built.quad.dispose();
    };
  }, [built, base]);

  const tier = fxTier(quality);

  useFrame((state) => {
    if (!built) return;
    const { feet, dist, sprayW, puffW, order, frustum, sphere } = built;
    const cam = state.camera.position;
    built.m.multiplyMatrices(state.camera.projectionMatrix, state.camera.matrixWorldInverse);
    frustum.setFromProjectionMatrix(built.m);
    const still = store.reducedMotion;
    const S = WATERFALL_FX;
    const skirtW = (built.skirt.material as ShaderMaterial).uniforms.uFootW.value as Float32Array;
    let anySkirt = false;
    for (let k = 0; k < feet.length; k++) {
      const ft = feet[k];
      const c = ft.center;
      const d = Math.hypot(c[0] - cam.x, c[1] - cam.y, c[2] - cam.z);
      dist[k] = d;
      sphere.center.set(c[0], c[1] + ft.width * 0.5, c[2]);
      sphere.radius = ft.width * 2 + 12;
      const on = chunkDrawn(ft.chunk, sets) && frustum.intersectsSphere(sphere);
      skirtW[k] = on ? distanceFade(d, S.skirt.near, S.skirt.far) : 0;
      sprayW[k] = on && !still ? distanceFade(d, S.spray.near, S.spray.far) : 0;
      puffW[k] = on ? distanceFade(d, S.puffs.near, S.puffs.far) : 0;
      if (skirtW[k] > 0) anySkirt = true;
    }
    setVisible(built.skirt, anySkirt);
    drive(built.spray, feet, sprayW, dist, order);
    const sprayGeo = built.spray.geometry as InstancedBufferGeometry;
    const sprayN = S.spray.count[tier];
    if (sprayGeo.instanceCount !== sprayN) sprayGeo.instanceCount = sprayN;
    (built.spray.material as ShaderMaterial).uniforms.uViewH.value = state.size.height * state.viewport.dpr;
    const slots = drive(built.puffs, feet, puffW, dist, order);
    const puffGeo = built.puffs.geometry as InstancedBufferGeometry;
    const puffN = slots * S.puffs.max;
    if (puffGeo.instanceCount !== puffN) puffGeo.instanceCount = puffN;
    (built.puffs.material as ShaderMaterial).uniforms.uPerFoot.value = S.puffs.count[tier];
  });

  return built ? <primitive object={built.skirt} /> : null;
}

/** Fills a spray or mist draw's slots with the nearest weighted feet; hides it when none. Returns the slot count. */
function drive(mesh: Mesh, feet: readonly FallFoot[], weight: Float64Array, dist: Float64Array, order: Int32Array): number {
  const n = pickFootSlots(weight, dist, order);
  setVisible(mesh, n > 0);
  const u = (mesh.material as ShaderMaterial).uniforms;
  u.uSlots.value = n;
  for (let i = 0; i < n; i++) {
    const ft = feet[order[i]];
    (u.uFeet.value as Vector4[])[i].set(ft.center[0], ft.level, ft.center[2], weight[order[i]]);
    (u.uShape.value as Vector4[])[i].set(ft.width, ft.pourAngle, ft.drop, 0);
  }
  return n;
}
