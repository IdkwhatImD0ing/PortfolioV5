"use client";

/**
 * Live fire in the Artifact Forge Peak (lib/sect/forge-flames.ts): flames inside the forge hall's
 * furnace mouths, in the two kiln towers' fire boxes and over the ding cauldron's molten top, with
 * embers rising from the furnaces and kilns. The bake's molten glow under them flickers in step.
 *
 * Three draws in the overlay scene (drawn after the world, with its depth for soft edges on the High
 * and Medium tiers), all motion in the shaders on one clock:
 * - Mouths: one quad per furnace mouth whose shader traces the view ray into a fire box behind it:
 *   soot-dark walls lit by the fire, a bed of glowing coals and one or two sheets of flame at
 *   different depths, cut off by the lintel. It replaces the mouth's flat glowing plate, so the fire
 *   sits inside the furnace and shifts as the camera passes.
 * - Flames: upright camera-facing cards (turning about the vertical only), additive: a wide fire in
 *   front of each kiln's box (between the posts, under the roof) and tongues spread over the
 *   cauldron's surface. Soft where they meet the scene (High, Medium).
 * - Embers: sparks popping out of the mouths and rising from the kilns' vents, a few pixels at least
 *   (smaller ones draw that size, dimmer). The cauldron's sparks stay fx.tsx ForgeFire's.
 *
 * Fires come from meta.fires once a bake writes them, from the bake's ".glow.molten" pieces until
 * then. Each fire is tested against the view every frame: a draw whose fires are all out of view,
 * too far or in an undrawn chunk is hidden. The tier sets the cards, sheets and embers. With
 * reduced motion the fire stands still as a calm glow (one fixed moment, smoothed), without embers,
 * and the molten glow stops flickering.
 */
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import {
  AddEquation,
  AdditiveBlending,
  Box3,
  BufferAttribute,
  BufferGeometry,
  Color,
  CustomBlending,
  Frustum,
  Group,
  HalfFloatType,
  InstancedBufferGeometry,
  InstancedInterleavedBuffer,
  type InstancedMesh,
  InterleavedBufferAttribute,
  type Material,
  Matrix4,
  Mesh,
  type MeshBasicMaterial,
  NormalBlending,
  OneFactor,
  OneMinusSrcAlphaFactor,
  PlaneGeometry,
  type Scene,
  ShaderMaterial,
  Sphere,
  Vector3,
  Vector4,
  WebGLRenderTarget,
} from "three";
import {
  CARD_STRIDE,
  EMBER_STRIDE,
  emberSeeds,
  fireBounds,
  fireFlicker,
  FLAME_GLSL,
  flameCards,
  FLAMES,
  flameTier,
  fireSourcesFromAnchors,
  fireSourcesFromGlow,
  glowFactor,
  meshPieces,
  MOUTH_STRIDE,
  openingQuads,
  type FireSource,
} from "@/lib/sect/forge-flames";
import { fogLibrary, glslFloat, type FogConstants } from "@/lib/sect/glsl";
import type { Quality } from "@/lib/sect/runtime";
import type { SectMeta } from "@/lib/sect/types";
import { distanceFade, fxTier } from "@/lib/sect/water";
import type { LoadedSet } from "./assets";
import { FORGE_FIRE_GLOW } from "./fx";
import { getNoiseTexture, SOFT_DEPTH } from "./materials";
import type { SectStore } from "./store";

const f = glslFloat;
const N = FLAMES.maxSources;
const MOLTEN = /\.glow\.molten$/i;

/** Off the clip volume, so nothing rasterises (a fire out of view, or an unused instance). */
const CULL = "gl_Position = vec4( 2.0, 2.0, 2.0, 1.0 ); return;";

const SOFT_PARS = /* glsl */ `
#include <packing>
uniform sampler2D tDepth;
uniform float uHasDepth;
uniform vec2 uResolution;
uniform float uNear;
uniform float uFar;
// 0 where the fragment touches the scene behind it, 1 when it is len metres or more in front.
float flameSoftFade( float fragViewZ, float len ) {
  if ( uHasDepth < 0.5 ) return 1.0;
  float d = texture2D( tDepth, gl_FragCoord.xy / uResolution ).r;
  if ( d >= 1.0 ) return 1.0;
  float sceneZ = perspectiveDepthToViewZ( d, uNear, uFar );
  return smoothstep( 0.0, max( len, 1e-3 ), fragViewZ - sceneZ );
}
`;

/** Per-fire uniforms the three draws share (a fire's weight is 0 when it is not drawn). */
interface SourceUniforms {
  uOn: { value: Float32Array };
  /** right.xz, normal.xz (openings); unused for beds. */
  uFrame: { value: Vector4[] };
  /** width, height, depth, phase (openings); radius, height, kind (0 opening, 1 kiln, 2 cauldron), phase. */
  uDim: { value: Vector4[] };
  /** base xyz, kind. */
  uBase: { value: Vector4[] };
}

function sourceUniforms(sources: readonly FireSource[]): SourceUniforms {
  const frame = Array.from({ length: N }, () => new Vector4());
  const dim = Array.from({ length: N }, () => new Vector4());
  const base = Array.from({ length: N }, () => new Vector4());
  sources.forEach((s, i) => {
    if (s.kind === "opening") {
      frame[i].set(s.right[0], s.right[2], s.normal[0], s.normal[2]);
      dim[i].set(s.width, s.height, s.depth, s.phase);
      base[i].set(s.base[0], s.base[1], s.base[2], 0);
    } else {
      dim[i].set(s.radius, s.height, s.style === "kiln" ? 1 : 2, s.phase);
      base[i].set(s.base[0], s.base[1], s.base[2], s.style === "kiln" ? 1 : 2);
    }
  });
  return { uOn: { value: new Float32Array(N) }, uFrame: { value: frame }, uDim: { value: dim }, uBase: { value: base } };
}

/** The air between the camera and a fire: the haze and the cloud layer take some of its light. */
const AIR_GLSL = /* glsl */ `
vec3 flameAir( vec3 col, vec3 world ) {
  vec3 rd = world - cameraPosition;
  float dist = length( rd );
  rd /= max( dist, 1e-3 );
  return col * exp( - sectHazeDepth( cameraPosition.y, rd.y, dist ) * SECT_EXTINCTION - sectCloudDepth( cameraPosition.y, rd.y, dist ) );
}
`;

// ---------------------------------------------------------------------------------------------
// Mouths: a fire box seen through the opening

function mouthMaterial(src: SourceUniforms, fog: FogConstants, fogColor: string, sheets: number): ShaderMaterial {
  return new ShaderMaterial({
    name: "sect.forge.mouths",
    transparent: true,
    blending: NormalBlending,
    depthWrite: false,
    fog: false,
    defines: { SHEETS: sheets },
    uniforms: {
      ...src,
      tFlameNoise: { value: getNoiseTexture() },
      uTime: { value: 0 },
      uCalm: { value: 0 },
      uFogColor: { value: new Color(fogColor) },
    },
    vertexShader: /* glsl */ `
attribute vec2 aLocal;
attribute float aSrc;
uniform float uOn[ ${N} ];
uniform vec4 uFrame[ ${N} ];
uniform vec4 uDim[ ${N} ];
varying vec2 vLocal;
varying vec3 vView;
varying vec4 vDim;
varying float vOn;
varying float vSeed;
varying vec3 vWorld;
void main() {
  int s = int( aSrc + 0.5 );
  float on = uOn[ s ];
  if ( on < 0.003 ) { ${CULL} }
  vec4 fr = uFrame[ s ];
  vec4 wp = modelMatrix * vec4( position, 1.0 );
  // The view in the opening's frame: x across, y up, z out of the furnace.
  vec3 V = cameraPosition - wp.xyz;
  vView = vec3( V.x * fr.x + V.z * fr.y, V.y, V.x * fr.z + V.z * fr.w );
  vLocal = aLocal;
  vDim = uDim[ s ];
  vOn = on;
  vSeed = aSrc * 3.17 + 0.41;
  vWorld = wp.xyz;
  gl_Position = projectionMatrix * viewMatrix * wp;
}
`,
    fragmentShader: /* glsl */ `
uniform float uTime;
uniform float uCalm;
uniform vec3 uFogColor;
varying vec2 vLocal;
varying vec3 vView;
varying vec4 vDim;
varying float vOn;
varying float vSeed;
varying vec3 vWorld;
${FLAME_GLSL}
${fogLibrary(fog)}
// One sheet of flame across the box at depth z (< 0), if the view reaches it before the surface it
// meets (at tHit along the ray).
vec3 flameSheet( vec3 o, vec3 d, float tHit, float z, float W, float H, float seed, float flick ) {
  float tz = z / d.z;
  if ( tz >= tHit ) return vec3( 0.0 );
  vec3 p = o + d * tz;
  float side = 1.0 - smoothstep( 0.32 * W, 0.5 * W, abs( p.x ) );
  vec2 uv = vec2( p.x / ( 0.5 * W ) * ( W / max( H, 0.3 ) ) * 0.55, p.y / ( H * 1.12 ) );
  float h = sectFlameHeat( uv, uTime * 0.85, seed, uCalm, 1.0 ) * side * ( 0.82 + 0.22 * flick / 0.85 );
  return sectFlameColor( h );
}
void main() {
  float W = vDim.x;
  float H = vDim.y;
  float D = vDim.z;
  float flick = sectFireFlicker( uTime, vDim.w );
  vec3 o = vec3( vLocal, 0.0 );
  vec3 d = - normalize( vView );
  d.z = min( d.z, - 0.04 );
  // Where the view meets the box: its back wall, a side wall, the floor or the ceiling.
  float tb = D / - d.z;
  float ts = abs( d.x ) > 1e-4 ? ( sign( d.x ) * 0.5 * W - o.x ) / d.x : 1e4;
  float ty = d.y < - 1e-4 ? - o.y / d.y : ( d.y > 1e-4 ? ( H - o.y ) / d.y : 1e4 );
  float t = min( tb, min( ts, ty ) );
  vec3 hp = o + d * t;
  bool floorHit = ty <= min( tb, ts ) && d.y < 0.0;
  bool ceilHit = ty <= min( tb, ts ) && d.y > 0.0;
  bool sideHit = ts < min( tb, ty );
  // Firelight in the box: strongest over the coal bed, falling off toward the mouth and the top.
  vec3 fc = vec3( 0.0, 0.12 * H, - 0.55 * D );
  vec3 dl = ( hp - fc ) / vec3( 0.6 * W, 0.75 * H, 0.9 * D );
  float lit = 1.0 / ( 1.0 + 2.6 * dot( dl, dl ) );
  vec3 col = vec3( 0.03, 0.01, 0.006 ) + vec3( 1.0, 0.22, 0.035 ) * ( 0.85 * lit * lit ) * ( 0.75 + 0.3 * flick );
  if ( sideHit ) col *= 0.72;
  if ( ceilHit ) col *= 0.5;
  if ( floorHit ) {
    // The coal bed: glowing lumps (the coarse noise) with dark cracks, breathing slowly.
    float c = texture2D( tFlameNoise, hp.xz * vec2( 0.55, 0.8 ) + vec2( vSeed, vSeed * 0.7 + uTime * 0.012 ) ).r;
    float c2 = texture2D( tFlameNoise, hp.xz * 1.9 + vec2( vSeed * 1.3, uTime * 0.03 ) ).r;
    float lump = smoothstep( 0.38, 0.62, c * 0.65 + c2 * 0.35 );
    col = mix( vec3( 0.22, 0.025, 0.003 ), vec3( 1.0, 0.36, 0.04 ) * 1.6, lump ) * ( 0.8 + 0.25 * flick );
    col += vec3( 1.0, 0.62, 0.18 ) * pow( lump, 6.0 ) * 1.4;
  }
  col += flameSheet( o, d, t, - 0.62 * D, W, H, vSeed + 5.3, flick ) * 0.8;
#if SHEETS > 1
  col += flameSheet( o, d, t, - 0.27 * D, W, H, vSeed, flick );
#endif
  // The mouth's thick rim: darker in the last few centimetres round the edge.
  float edge = min( min( o.x + 0.5 * W, 0.5 * W - o.x ), min( o.y, H - o.y ) );
  col *= mix( 0.45, 1.0, smoothstep( 0.0, 0.05 + 0.03 * W, edge ) );
  vec3 rd = vWorld - cameraPosition;
  float dist = length( rd );
  rd /= max( dist, 1e-3 );
  col = sectAerial( col, uFogColor, rd, sectHazeDepth( cameraPosition.y, rd.y, dist ) );
  gl_FragColor = vec4( col, vOn );
  #include <colorspace_fragment>
}
`,
  });
}

// ---------------------------------------------------------------------------------------------
// Flame cards over the beds

function cardMaterial(src: SourceUniforms, fog: FogConstants): ShaderMaterial {
  return new ShaderMaterial({
    name: "sect.forge.flames",
    transparent: true,
    depthWrite: false,
    // Premultiplied: the flame adds its light and its dense body hides a little of what is behind.
    blending: CustomBlending,
    blendEquation: AddEquation,
    blendSrc: OneFactor,
    blendDst: OneMinusSrcAlphaFactor,
    fog: false,
    uniforms: {
      uOn: src.uOn,
      uBase: src.uBase,
      ...SOFT_DEPTH,
      tFlameNoise: { value: getNoiseTexture() },
      uTime: { value: 0 },
      uCalm: { value: 0 },
    },
    vertexShader: /* glsl */ `
attribute vec4 iA;
attribute vec4 iB;
attribute vec4 iC;
uniform float uOn[ ${N} ];
uniform vec4 uBase[ ${N} ];
varying vec2 vUv;
varying float vSeed;
varying float vHeat;
varying float vPhase;
varying float vOn;
varying float vViewZ;
varying float vWall;
varying vec3 vWorld;
void main() {
  int s = int( iB.z + 0.5 );
  float on = uOn[ s ];
  if ( on < 0.003 ) { ${CULL} }
  vec3 base = iA.xyz;
  // Upright, turned about the vertical to face the camera.
  vec3 toC = cameraPosition - base;
  vec2 h = toC.xz;
  float hl = length( h );
  vec3 fwd = hl > 1e-3 ? vec3( h.x / hl, 0.0, h.y / hl ) : vec3( 0.0, 0.0, 1.0 );
  vec3 right = vec3( fwd.z, 0.0, - fwd.x );
  float width = iA.w;
  float height = iB.x;
  float u = position.x;
  float v = position.y * 0.5 + 0.5;
  vec3 p = base + fwd * iB.w + right * ( iC.x + u * width * 0.5 + iC.w * width * v * v ) + vec3( 0.0, v * height, 0.0 );
  vec4 mv = viewMatrix * vec4( p, 1.0 );
  vUv = vec2( u, v );
  vSeed = iB.y;
  vHeat = iC.y;
  vPhase = iC.z;
  vOn = on;
  vViewZ = mv.z;
  // A kiln's fire fills its vent: a sheet of flame across the card (its ends fade).
  vWall = uBase[ s ].w < 1.5 ? 1.0 : 0.0;
  vWorld = p;
  gl_Position = projectionMatrix * mv;
}
`,
    fragmentShader: /* glsl */ `
uniform float uTime;
uniform float uCalm;
varying vec2 vUv;
varying float vSeed;
varying float vHeat;
varying float vPhase;
varying float vOn;
varying float vViewZ;
varying float vWall;
varying vec3 vWorld;
${FLAME_GLSL}
${SOFT_PARS}
${fogLibrary(fog)}
${AIR_GLSL}
void main() {
  float flick = sectFireFlicker( uTime, vPhase );
  // The flame stretches and shrinks a little with its flicker.
  vec2 uv = vec2( vUv.x, vUv.y * ( 1.12 - 0.14 * flick / 0.85 ) );
  float h = sectFlameHeat( vec2( uv.x * mix( 1.0, 1.6, vWall ), uv.y ), uTime, vSeed, uCalm, vWall );
  h *= vHeat * ( 0.8 + 0.24 * flick / 0.85 ) * mix( 1.0, 1.0 - smoothstep( 0.68, 1.0, abs( uv.x ) ), vWall );
  if ( h <= 0.0 ) discard;
  float k = vOn * flameSoftFade( vViewZ, ${f(FLAMES.soft)} );
  vec3 col = sectFlameColor( h ) * k;
  // Linear light, added unencoded (as fx.tsx's fire): see the note there on the Low tier.
  gl_FragColor = vec4( flameAir( col, vWorld ), smoothstep( 0.15, 0.85, h ) * ${f(FLAMES.cover)} * k );
}
`,
  });
}

// ---------------------------------------------------------------------------------------------
// Embers

function emberMaterial(src: SourceUniforms, fog: FogConstants): ShaderMaterial {
  return new ShaderMaterial({
    name: "sect.forge.embers",
    transparent: true,
    depthWrite: false,
    blending: AdditiveBlending,
    fog: false,
    uniforms: {
      uOn: src.uOn,
      uFrame: src.uFrame,
      uDim: src.uDim,
      uBase: src.uBase,
      uTime: { value: 0 },
      uViewH: { value: 1000 },
    },
    vertexShader: /* glsl */ `
attribute vec4 iE;
uniform float uOn[ ${N} ];
uniform vec4 uFrame[ ${N} ];
uniform vec4 uDim[ ${N} ];
uniform vec4 uBase[ ${N} ];
uniform float uTime;
uniform float uViewH;
varying vec2 vUv;
varying vec3 vColor;
varying vec3 vWorld;
void main() {
  int s = int( iE.x + 0.5 );
  float on = uOn[ s ];
  if ( on < 0.003 ) { ${CULL} }
  vec4 B = uBase[ s ];
  vec4 Dm = uDim[ s ];
  float a = iE.y;
  float b = iE.z;
  vec3 p;
  float life;
  float r;
  if ( B.w < 0.5 ) {
    // From a furnace mouth: out of its upper half (where the hot air leaves), thrown forward and up,
    // drifting as they cool.
    vec4 fr = uFrame[ s ];
    vec3 rt = vec3( fr.x, 0.0, fr.y );
    vec3 n = vec3( fr.z, 0.0, fr.w );
    float period = 1.3 + 1.1 * a;
    float k = uTime / period + iE.w;
    life = fract( k );
    float cyc = floor( k );
    float jx = fract( sin( cyc * 12.9898 + b * 78.233 ) * 43758.5453 );
    float tt = life * period;
    vec3 start = B.xyz + rt * ( ( jx - 0.5 ) * Dm.x * 0.75 ) + vec3( 0.0, Dm.y * ( 0.55 + 0.38 * b ), 0.0 ) - n * 0.15;
    vec3 vel = n * ( 0.5 + 0.8 * b ) + vec3( 0.0, 0.6 + 0.9 * a, 0.0 );
    // Drag on the throw, buoyancy lifting them, a wobble.
    p = start + vel * ( 1.0 - exp( - 1.6 * tt ) ) / 1.6 + vec3( 0.0, 0.55 * tt * tt, 0.0 );
    p += rt * sin( tt * 3.1 + b * 17.0 ) * 0.12 * tt;
    r = 0.028 + 0.025 * a;
  } else {
    // From a kiln's vent: out between the posts and up past the roof into the smoke.
    float period = 2.0 + 1.8 * a;
    float k = uTime / period + iE.w;
    life = fract( k );
    float cyc = floor( k );
    float ang = ( b + fract( sin( cyc * 4.1414 + a * 91.7 ) * 4375.85 ) * 0.3 ) * 6.2831853;
    float tt = life * period;
    vec3 away = vec3( cos( ang ), 0.0, sin( ang ) );
    vec3 start = B.xyz + away * Dm.x * 0.9 + vec3( 0.0, Dm.y * ( 0.35 + 0.35 * a ), 0.0 );
    p = start + away * ( 0.9 + 0.8 * b ) * ( 1.0 - exp( - 1.2 * tt ) ) + vec3( 0.0, ( 1.6 + 1.4 * b ) * tt, 0.0 );
    p += vec3( sin( tt * 2.3 + a * 13.0 ), 0.0, cos( tt * 1.9 + b * 11.0 ) ) * 0.25 * tt;
    r = 0.04 + 0.035 * b;
  }
  // Bright at once, then cooling from yellow-white to a dull red as it dies.
  float glow = smoothstep( 0.0, 0.06, life ) * pow( 1.0 - life, 1.3 );
  vec4 mv = viewMatrix * vec4( p, 1.0 );
  // A spark under about 1.6 pixels draws at that size with the same light (dimmer per pixel).
  float px = 2.0 * max( - mv.z, 0.1 ) / ( projectionMatrix[ 1 ][ 1 ] * uViewH );
  float drawn = max( r, 1.6 * px );
  glow *= ( r / drawn ) * ( r / drawn );
  if ( glow * on < 0.002 ) { ${CULL} }
  mv.xy += position.xy * drawn;
  vUv = position.xy;
  vColor = mix( vec3( 1.0, 0.5, 0.1 ) * 3.0, vec3( 1.0, 0.16, 0.02 ) * 1.4, smoothstep( 0.1, 0.8, life ) ) * glow * on;
  vWorld = p;
  gl_Position = projectionMatrix * mv;
}
`,
    fragmentShader: /* glsl */ `
varying vec2 vUv;
varying vec3 vColor;
varying vec3 vWorld;
${fogLibrary(fog)}
${AIR_GLSL}
void main() {
  float q2 = dot( vUv, vUv );
  if ( q2 >= 1.0 ) discard;
  float g = exp( - q2 * 9.0 ) + 0.12 * exp( - q2 * 3.0 );
  gl_FragColor = vec4( flameAir( vColor * g * ( 1.0 - q2 ), vWorld ), 1.0 );
}
`,
  });
}

// ---------------------------------------------------------------------------------------------

/** A molten glow material, its colour as prepared, the fires it lies under (their indices), and its dimming under them. */
interface GlowMat {
  material: MeshBasicMaterial;
  base: Color;
  sources: number[];
  /** Its colour factor while its fires are fully drawn (FLAMES.poolGlow under a cauldron's, else FLAMES.boxGlow). */
  dim: number;
}

/** The molten glow materials in the set and, for each, the fires inside its meshes' bounds. */
function moltenMaterials(set: LoadedSet, sources: readonly FireSource[]): GlowMat[] {
  const byMat = new Map<Material, GlowMat>();
  const box = new Box3();
  const p = new Vector3();
  for (const root of set.scenes) {
    root.updateMatrixWorld(true);
    root.traverse((o) => {
      const m = o as Mesh;
      if (!m.isMesh || Array.isArray(m.material)) return;
      const mat = m.material as MeshBasicMaterial;
      if (!MOLTEN.test(mat.name ?? "") || !mat.color) return;
      box.setFromObject(m).expandByScalar(0.6);
      let g = byMat.get(mat);
      if (!g) {
        g = { material: mat, base: mat.color.clone(), sources: [], dim: 1 };
        byMat.set(mat, g);
      }
      sources.forEach((s, i) => {
        if (!g.sources.includes(i) && box.containsPoint(p.set(s.base[0], s.base[1], s.base[2]))) g.sources.push(i);
      });
    });
  }
  const out = [...byMat.values()].filter((g) => g.sources.length > 0);
  for (const g of out) {
    const cauldron = g.sources.some((i) => sources[i].kind === "bed" && (sources[i] as { style: string }).style === "cauldron");
    g.dim = cauldron ? FLAMES.poolGlow : FLAMES.boxGlow;
  }
  return out;
}

/** The connected pieces (world xyz triples) of the set's molten glow meshes (instances too). */
function moltenPieces(set: LoadedSet): number[][] {
  const out: number[][] = [];
  const v = new Vector3();
  const inst = new Matrix4();
  const world = new Matrix4();
  for (const root of set.scenes) {
    root.updateMatrixWorld(true);
    root.traverse((o) => {
      const m = o as Mesh;
      if (!m.isMesh || Array.isArray(m.material) || !MOLTEN.test(m.material.name ?? "")) return;
      const pos = m.geometry.getAttribute("position");
      if (!pos) return;
      const index = m.geometry.getIndex();
      const im = m as InstancedMesh;
      const count = im.isInstancedMesh ? im.count : 1;
      for (let k = 0; k < count; k++) {
        if (im.isInstancedMesh) {
          im.getMatrixAt(k, inst);
          world.multiplyMatrices(m.matrixWorld, inst);
        } else world.copy(m.matrixWorld);
        const pts = new Float32Array(pos.count * 3);
        for (let i = 0; i < pos.count; i++) {
          v.fromBufferAttribute(pos, i).applyMatrix4(world);
          pts[i * 3] = v.x;
          pts[i * 3 + 1] = v.y;
          pts[i * 3 + 2] = v.z;
        }
        out.push(...meshPieces(pts, index ? index.array : null));
      }
    });
  }
  return out;
}

/** The forge's fires: meta.fires when the bake wrote them, else read from its molten glow. */
function findSources(set: LoadedSet, meta: SectMeta): FireSource[] {
  const anchored = fireSourcesFromAnchors(meta.fires ?? [], set.id);
  if (anchored.length > 0) return anchored;
  const area = meta.areas.find((a) => a.id === set.id);
  return fireSourcesFromGlow(moltenPieces(set), area?.anchor ?? null, set.id);
}

export interface ForgeFlamesProps {
  set: LoadedSet | null;
  meta: SectMeta;
  store: SectStore;
  fog: FogConstants;
  quality: Quality;
  overlay: Scene;
  /** ?debug=1: window.__sectFlames (switch the fire off and on, list the fires). */
  debug?: boolean;
}

export function ForgeFlames({ set, meta, store, fog, quality, overlay, debug = false }: ForgeFlamesProps) {
  const gl = useThree((s) => s.gl);
  const camera = useThree((s) => s.camera);
  const tierName = fxTier(quality);
  const tier = useMemo(() => flameTier(tierName), [tierName]);

  const fires = useMemo(() => {
    if (!set) return null;
    const sources = findSources(set, meta);
    if (sources.length === 0) return null;
    return { sources, glow: moltenMaterials(set, sources), bounds: sources.map(fireBounds) };
  }, [set, meta]);

  const built = useMemo(() => {
    if (!fires) return null;
    const { sources } = fires;
    const src = sourceUniforms(sources);
    const group = new Group();
    group.name = "sect.forge.fire";

    const quads = openingQuads(sources);
    let mouths: Mesh | null = null;
    if (quads.length > 0) {
      const buf = new BufferGeometry();
      const n = quads.length / MOUTH_STRIDE;
      const pos = new Float32Array(n * 3);
      const local = new Float32Array(n * 2);
      const idx = new Float32Array(n);
      for (let i = 0; i < n; i++) {
        pos.set(quads.subarray(i * MOUTH_STRIDE, i * MOUTH_STRIDE + 3), i * 3);
        local.set(quads.subarray(i * MOUTH_STRIDE + 3, i * MOUTH_STRIDE + 5), i * 2);
        idx[i] = quads[i * MOUTH_STRIDE + 5];
      }
      buf.setAttribute("position", new BufferAttribute(pos, 3));
      buf.setAttribute("aLocal", new BufferAttribute(local, 2));
      buf.setAttribute("aSrc", new BufferAttribute(idx, 1));
      mouths = new Mesh(buf, mouthMaterial(src, fog, meta.fog.color, tier.sheets));
      mouths.name = "sect.forge.mouths";
      mouths.frustumCulled = false;
      // Before the clouds and mist (3+): a cloud in front of the hall covers its furnaces.
      mouths.renderOrder = 1.9;
      group.add(mouths);
    }

    const quad = new PlaneGeometry(2, 2);
    const cardData = flameCards(sources, tier);
    let cards: Mesh | null = null;
    if (cardData.length > 0) {
      const geo = new InstancedBufferGeometry();
      geo.setIndex(quad.getIndex());
      geo.setAttribute("position", quad.getAttribute("position"));
      const ib = new InstancedInterleavedBuffer(cardData, CARD_STRIDE, 1);
      geo.setAttribute("iA", new InterleavedBufferAttribute(ib, 4, 0));
      geo.setAttribute("iB", new InterleavedBufferAttribute(ib, 4, 4));
      geo.setAttribute("iC", new InterleavedBufferAttribute(ib, 4, 8));
      geo.instanceCount = cardData.length / CARD_STRIDE;
      cards = new Mesh(geo, cardMaterial(src, fog));
      cards.name = "sect.forge.flames";
      cards.frustumCulled = false;
      cards.renderOrder = 2;
      group.add(cards);
    }

    const emberData = emberSeeds(sources, tier);
    let embers: Mesh | null = null;
    if (emberData.length > 0) {
      const geo = new InstancedBufferGeometry();
      geo.setIndex(quad.getIndex());
      geo.setAttribute("position", quad.getAttribute("position"));
      const ib = new InstancedInterleavedBuffer(emberData, EMBER_STRIDE, 1);
      geo.setAttribute("iE", new InterleavedBufferAttribute(ib, 4, 0));
      geo.instanceCount = emberData.length / EMBER_STRIDE;
      embers = new Mesh(geo, emberMaterial(src, fog));
      embers.name = "sect.forge.embers";
      embers.frustumCulled = false;
      embers.renderOrder = 2.1;
      group.add(embers);
    }
    for (const m of group.children) m.visible = false;

    // Per-frame scratch (no allocations in the frame loop).
    return {
      group,
      quad,
      mouths,
      cards,
      embers,
      meshes: [mouths, cards, embers].filter((m): m is Mesh => m !== null),
      src,
      frustum: new Frustum(),
      m: new Matrix4(),
      sphere: new Sphere(),
      flick: new Float32Array(sources.length),
      control: { enabled: true, show: { mouths: true, flames: true, embers: true } as Record<string, boolean> },
    };
  }, [fires, fog, meta.fog.color, tier]);

  useEffect(() => {
    if (!built) return;
    overlay.add(built.group);
    return () => {
      overlay.remove(built.group);
      built.quad.dispose();
      for (const m of built.meshes) {
        m.geometry.dispose();
        (m.material as ShaderMaterial).dispose();
      }
    };
  }, [built, overlay]);

  // The molten glow goes back to its prepared colour when the fire goes, and the cauldron's soft glow
  // (fx.tsx ForgeFire) to its full strength.
  useEffect(() => {
    if (!fires) return;
    return () => {
      for (const g of fires.glow) g.material.color.copy(g.base);
      FORGE_FIRE_GLOW.value = 1;
    };
  }, [fires]);

  // Shaders compile in the background as soon as the fire exists (WarmDecor skips hidden objects):
  // compiled on first sight, they stalled that frame on the approach.
  const post = quality.post;
  useEffect(() => {
    if (!built) return;
    let cancelled = false;
    const raf = requestAnimationFrame(() => {
      if (cancelled) return;
      const shown = built.group.children.map((m) => m.visible);
      for (const m of built.group.children) m.visible = true;
      const target = post ? new WebGLRenderTarget(1, 1, { type: HalfFloatType, depthBuffer: false }) : null;
      const prev = gl.getRenderTarget();
      try {
        gl.setRenderTarget(target);
        void gl.compileAsync(built.group, camera, overlay).catch((e) => console.warn("[sect] forge fire warm-up failed", e));
      } catch (e) {
        console.warn("[sect] forge fire warm-up failed", e);
      } finally {
        gl.setRenderTarget(prev);
        target?.dispose();
        built.group.children.forEach((m, i) => (m.visible = shown[i]));
      }
    });
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
    };
  }, [built, gl, camera, overlay, post]);

  // ?debug=1: window.__sectFlames.enabled switches the fire off and on (for frame-time checks).
  useEffect(() => {
    if (!debug || !built || !fires) return;
    const w = window as unknown as { __sectFlames?: unknown };
    const hook = {
      get enabled() {
        return built.control.enabled;
      },
      set enabled(v: boolean) {
        built.control.enabled = v;
      },
      /** Each draw on its own (mouths, flames, embers), for measuring. */
      show: built.control.show,
      sources: fires.sources,
      tier,
      visible: () => built.group.children.filter((m) => m.visible).map((m) => m.name),
    };
    w.__sectFlames = hook;
    return () => {
      if (w.__sectFlames === hook) delete w.__sectFlames;
    };
  }, [debug, built, fires, tier]);

  useFrame((state) => {
    if (!built || !fires || !set) return;
    const on = built.src.uOn.value;
    const live = set.drawn && built.control.enabled;
    let any = false;
    if (live) {
      built.m.multiplyMatrices(state.camera.projectionMatrix, state.camera.matrixWorldInverse);
      built.frustum.setFromProjectionMatrix(built.m);
      const cam = state.camera.position;
      for (let i = 0; i < fires.bounds.length; i++) {
        const b = fires.bounds[i];
        built.sphere.center.set(b.center[0], b.center[1], b.center[2]);
        built.sphere.radius = b.radius;
        const d = Math.hypot(b.center[0] - cam.x, b.center[1] - cam.y, b.center[2] - cam.z);
        on[i] = built.frustum.intersectsSphere(built.sphere) ? distanceFade(d, FLAMES.fade[0], FLAMES.fade[1]) : 0;
        if (on[i] > 0) any = true;
      }
    } else on.fill(0);
    const still = store.reducedMotion;
    const t = still ? FLAMES.stillTime : state.clock.elapsedTime;
    const show = built.control.show;
    if (built.mouths) built.mouths.visible = any && show.mouths;
    if (built.cards) built.cards.visible = any && show.flames;
    if (built.embers) built.embers.visible = any && !still && show.embers;
    for (const m of built.meshes) {
      if (!m.visible) continue;
      const u = (m.material as ShaderMaterial).uniforms;
      u.uTime.value = t;
      if (u.uCalm) u.uCalm.value = still ? FLAMES.calm : 0;
      if (u.uViewH) u.uViewH.value = state.size.height * state.viewport.dpr;
    }
    // The bake's molten glow flickers with the fires over it (steady with reduced motion).
    // The cauldron's soft glow gives way to its flames as they fade in.
    let cauldron = 0;
    for (let i = 0; i < fires.sources.length; i++) {
      built.flick[i] = fireFlicker(t, fires.sources[i].phase);
      const s = fires.sources[i];
      if (s.kind === "bed" && s.style === "cauldron") cauldron = Math.max(cauldron, on[i]);
    }
    FORGE_FIRE_GLOW.value = 1 + (FLAMES.cauldronGlow - 1) * cauldron;
    for (const g of fires.glow) {
      let sum = 0;
      let w = 0;
      for (const i of g.sources) {
        sum += built.flick[i];
        w = Math.max(w, on[i]);
      }
      const k = (any && !still ? glowFactor(sum / g.sources.length) : 1) * (1 + (g.dim - 1) * w);
      g.material.color.copy(g.base).multiplyScalar(k);
    }
  });

  return null;
}
