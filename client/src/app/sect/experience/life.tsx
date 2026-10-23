"use client";

/**
 * Living things in the air (lib/sect/life.ts): distant bird flocks crossing the valleys, glowing qi
 * motes and fireflies at the holds, over the near waterfalls, flowering trees and ponds, and spirit
 * butterflies around the peach trees. Each kind is one instanced draw whose motion runs entirely in
 * its vertex shader (mirroring life.ts); the CPU only sets a few uniforms a frame and hides a draw
 * whose groups are all outside their stretch of the flight or out of view. Tables are built once
 * per flight; the quality tier only changes how many instances are drawn (packed in rank order).
 *
 * Fog: birds and butterflies take the scene's aerial perspective (sectAerial, like the baked
 * surfaces); the additive motes are dimmed by what the air in between absorbs (the haze's own
 * colour is already behind them).
 */
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import {
  AdditiveBlending,
  Color,
  DoubleSide,
  Frustum,
  InstancedBufferGeometry,
  InstancedInterleavedBuffer,
  InterleavedBufferAttribute,
  Matrix4,
  Mesh,
  PlaneGeometry,
  ShaderMaterial,
  Sphere,
} from "three";
import { fogLibrary, glslFloat, type FogConstants } from "@/lib/sect/glsl";
import {
  buildLifeTables,
  firstLiveGroup,
  LIFE,
  LIFE_HASH_GLSL,
  lifeCounts,
  lifeTier,
  type LifeCounts,
  type Packed,
} from "@/lib/sect/life";
import { SECT_LOOK } from "@/lib/sect/look";
import type { Quality } from "@/lib/sect/runtime";
import type { SectMeta } from "@/lib/sect/types";
import type { SectStore } from "./store";

const f = glslFloat;

/** Shared by the three vertex shaders: the hold-window fade (life.ts windowFade) and the cull. */
const COMMON_VERTEX = /* glsl */ `
uniform float uTime;
uniform float uFrame;
uniform float uViewH;
float sectLifeWindow( float frame, float lo, float hi ) {
  return smoothstep( lo - ${f(LIFE.fadeFrames)}, lo + ${f(LIFE.fadeFrames)}, frame )
    * ( 1.0 - smoothstep( hi - ${f(LIFE.fadeFrames)}, hi + ${f(LIFE.fadeFrames)}, frame ) );
}
// World metres per pixel at view depth z (one pixel is 2 z / ( P11 * height )).
float sectLifePixel( float z ) {
  return 2.0 * max( z, 0.1 ) / ( projectionMatrix[ 1 ][ 1 ] * uViewH );
}
${LIFE_HASH_GLSL}
`;

/** Outside its window, faded out or too far: off the clip volume, so nothing rasterises. */
const CULL = "gl_Position = vec4( 2.0, 2.0, 2.0, 1.0 ); return;";

// ---------------------------------------------------------------------------------------------
// Birds

function birdMaterial(fog: FogConstants, fogColor: string): ShaderMaterial {
  const B = LIFE.birds;
  return new ShaderMaterial({
    name: "sect.life.birds",
    transparent: true,
    depthWrite: false,
    fog: false,
    side: DoubleSide,
    uniforms: {
      uTime: { value: 0 },
      uFrame: { value: 0 },
      uViewH: { value: 1000 },
      uColor: { value: new Color(B.color) },
      uColorLine: { value: new Color(B.colorLine) },
      uFogColor: { value: new Color(fogColor) },
    },
    vertexShader: /* glsl */ `
attribute vec4 iRoute;
attribute vec4 iPath;
attribute vec4 iSlot;
attribute vec4 iWing;
attribute vec4 iWindow;
${COMMON_VERTEX}
varying vec2 vUv;
varying float vFlap;
varying float vAlpha;
varying float vKind;
varying vec3 vDir;
varying float vDist;
void main() {
  float t = uTime;
  // lib/sect/life.ts flockPoint: along a straight route that wraps (faded at both ends), each lap
  // shifted toward or away from the camera and up or down, rising and falling gently.
  float L = iPath.x;
  float s = t * iPath.y + iPath.z;
  float lap = floor( s / L );
  float u = s - lap * L;
  float along = u - 0.5 * L;
  vec2 d = vec2( cos( iRoute.w ), sin( iRoute.w ) );
  float seed = iPath.w;
  float depth = ( sectLifeHash( lap * 1.618 + seed * 97.0 ) - 0.5 ) * 2.0 * ${f(B.lapDepth)};
  float lift = ( sectLifeHash( lap * 2.718 + seed * 57.0 + 11.0 ) - 0.5 ) * 2.0 * ${f(B.lapHeight)}
    + sin( along * 0.011 + seed * 20.0 ) * ${f(B.undulate)};
  float e = ${f(B.endFade)} * L;
  float fade = smoothstep( 0.0, e, u ) * smoothstep( 0.0, e, L - u );
  vec3 p = iRoute.xyz + vec3( d.x * along - d.y * depth, lift, d.y * along + d.x * depth );
  // birdPoint: the bird's slot in the flock's frame, and a slow drift around it.
  float ph = iSlot.w;
  float w = iWing.w;
  p += vec3( d.x * iSlot.x - d.y * iSlot.z, iSlot.y, d.y * iSlot.x + d.x * iSlot.z );
  p += vec3( sin( t * 0.23 + ph * 7.0 ) * w, sin( t * 0.31 + ph * 3.0 ) * w * 0.6, cos( t * 0.19 + ph * 5.0 ) * w );
  vec3 toC = p - cameraPosition;
  float dist = length( toC );
  float a = fade * sectLifeWindow( uFrame, iWindow.x, iWindow.y )
    * smoothstep( ${f(B.near[0])}, ${f(B.near[1])}, dist ) * ( 1.0 - smoothstep( ${f(B.far[0])}, ${f(B.far[1])}, dist ) );
  if ( a < 0.004 ) { ${CULL} }
  // Never thinner than a few pixels: a smaller bird is drawn at that size, fainter.
  vec4 mv = viewMatrix * vec4( p, 1.0 );
  float span = iWing.x;
  float drawn = max( span, ${f(B.minPx)} * sectLifePixel( - mv.z ) );
  a *= sqrt( span / drawn );
  // Small birds flap in bursts and glide; the larger ones beat slowly with the odd glide.
  float glide = iWing.z < 0.5
    ? smoothstep( 0.35, 0.75, sin( t * 0.43 + ph * 6.2831853 ) )
    : smoothstep( 0.6, 0.9, sin( t * 0.21 + ph * 6.2831853 ) );
  vFlap = mix( sin( t * 6.2831853 * iWing.y + ph * 6.2831853 ), 0.35, glide );
  // Facing the camera, wings level with the horizon, banking a little.
  float roll = sin( t * 0.5 + ph * 6.2831853 ) * 0.15;
  vec2 q = vec2( position.x * cos( roll ) - position.y * sin( roll ), position.x * sin( roll ) + position.y * cos( roll ) );
  mv.xy += vec2( q.x * 0.5, q.y * 0.3 ) * drawn;
  vUv = position.xy;
  vAlpha = a;
  vKind = iWing.z;
  vDir = toC / max( dist, 1e-3 );
  vDist = dist;
  gl_Position = projectionMatrix * mv;
}
`,
    fragmentShader: /* glsl */ `
uniform vec3 uColor;
uniform vec3 uColorLine;
uniform vec3 uFogColor;
varying vec2 vUv;
varying float vFlap;
varying float vAlpha;
varying float vKind;
varying vec3 vDir;
varying float vDist;
${fogLibrary(fog)}
void main() {
  // In half-wingspan units: an "m" of two wings that beat up and down, thinning to the tips, and a
  // small body. At a few pixels it is a dark flickering stroke (the anti-aliasing keeps it whole).
  vec2 P = vec2( vUv.x, vUv.y * 0.6 );
  float x = abs( P.x );
  float aa = max( fwidth( P.y ), 1e-4 );
  float yc = vFlap * 0.5 * pow( x, 1.1 ) - 0.06 * x * x;
  float th = max( 0.085 * ( 1.0 - pow( x, 1.5 ) ) + 0.02, aa * 0.75 );
  float wing = ( 1.0 - smoothstep( th - aa, th + aa, abs( P.y - yc ) ) ) * ( 1.0 - smoothstep( 1.0 - aa, 1.0, x ) );
  float body = 1.0 - smoothstep( 0.1 - aa, 0.1 + aa, length( vec2( P.x * 1.4, P.y + 0.02 ) ) );
  float a = max( wing, body ) * vAlpha;
  if ( a < 0.01 ) discard;
  vec3 col = mix( uColor, uColorLine, vKind );
  col = sectAerial( col, uFogColor, vDir, sectHazeDepth( cameraPosition.y, vDir.y, vDist ) );
  col = mix( col, SECT_CLOUD_FOG, 1.0 - exp( - sectCloudDepth( cameraPosition.y, vDir.y, vDist ) ) );
  gl_FragColor = vec4( col, a );
  #include <colorspace_fragment>
}
`,
  });
}

// ---------------------------------------------------------------------------------------------
// Motes

function moteMaterial(fog: FogConstants): ShaderMaterial {
  const M = LIFE.motes;
  return new ShaderMaterial({
    name: "sect.life.motes",
    transparent: true,
    depthWrite: false,
    blending: AdditiveBlending,
    fog: false,
    uniforms: {
      uTime: { value: 0 },
      uFrame: { value: 0 },
      uViewH: { value: 1000 },
    },
    vertexShader: /* glsl */ `
attribute vec4 iHome;
attribute vec4 iShape;
attribute vec4 iColor;
attribute vec4 iWindow;
${COMMON_VERTEX}
varying vec2 vUv;
varying vec3 vColor;
varying vec3 vDir;
varying float vDist;
varying float vSoft;
void main() {
  float t = uTime;
  float s = iHome.w;
  float w = iShape.z;
  // lib/sect/life.ts motePoint: fireflies wander and blink; qi motes rise over each life.
  vec3 p = iHome.xyz + vec3( sin( t * 0.21 + s * 41.0 ) * w, sin( t * 0.17 + s * 23.0 ) * w * 0.6, cos( t * 0.19 + s * 31.0 ) * w );
  float glow;
  if ( iShape.y > 0.5 ) {
    float c = fract( t * iColor.w + s * 7.3 );
    p.y += c * iShape.w;
    glow = smoothstep( 0.0, 0.2, c ) * ( 1.0 - smoothstep( 0.65, 1.0, c ) );
  } else {
    float b = 0.5 + 0.5 * sin( t * iColor.w + s * 60.0 );
    glow = 0.25 + 0.75 * b * b * b;
  }
  vec3 toC = p - cameraPosition;
  float dist = length( toC );
  float a = glow * sectLifeWindow( uFrame, iWindow.x, iWindow.y )
    * smoothstep( ${f(M.near[0])}, ${f(M.near[1])}, dist ) * ( 1.0 - smoothstep( iWindow.z * 0.7, iWindow.z, dist ) );
  if ( a < 0.003 ) { ${CULL} }
  // A mote smaller than a few pixels is drawn at that size with the same light (dimmer per pixel).
  vec4 mv = viewMatrix * vec4( p, 1.0 );
  float r = iShape.x;
  float drawn = max( r, ${f(M.minPx)} * sectLifePixel( - mv.z ) );
  a *= ( r / drawn ) * ( r / drawn );
  mv.xy += position.xy * drawn;
  vUv = position.xy;
  vColor = iColor.rgb * a;
  vDir = toC / max( dist, 1e-3 );
  vDist = dist;
  vSoft = iWindow.w;
  gl_Position = projectionMatrix * mv;
}
`,
    fragmentShader: /* glsl */ `
varying vec2 vUv;
varying vec3 vColor;
varying vec3 vDir;
varying float vDist;
varying float vSoft;
${fogLibrary(fog)}
void main() {
  float q2 = dot( vUv, vUv );
  if ( q2 >= 1.0 ) discard;
  // A hot core (the bloom catches it on the high and mid tiers) in a faint halo; a relic's qi is a
  // soft glow instead: a smaller core in a wide halo (life.ts Mote.soft).
  float hard = exp( - q2 * 14.0 ) + 0.18 * exp( - q2 * 4.0 );
  float soft = 0.6 * exp( - q2 * 24.0 ) + 0.4 * exp( - q2 * 4.5 );
  float g = mix( hard, soft, vSoft ) * ( 1.0 - q2 );
  // Light through the air in between: what the haze and the cloud layer absorb.
  float od = sectHazeDepth( cameraPosition.y, vDir.y, vDist );
  float cd = sectCloudDepth( cameraPosition.y, vDir.y, vDist );
  // Linear light, added unencoded (as the moon's halo, materials.ts createGlowMaterial): straight
  // onto the sRGB screen (the Low tier) an encoded mote's faint halo is many times too bright.
  gl_FragColor = vec4( vColor * g * exp( - od * SECT_EXTINCTION - cd ), 1.0 );
}
`,
  });
}

// ---------------------------------------------------------------------------------------------
// Butterflies

function butterflyMaterial(fog: FogConstants, fogColor: string): ShaderMaterial {
  const Bf = LIFE.butterflies;
  return new ShaderMaterial({
    name: "sect.life.butterflies",
    transparent: true,
    depthWrite: false,
    fog: false,
    side: DoubleSide,
    uniforms: {
      uTime: { value: 0 },
      uFrame: { value: 0 },
      uViewH: { value: 1000 },
      uFogColor: { value: new Color(fogColor) },
    },
    vertexShader: /* glsl */ `
attribute vec4 iCenter;
attribute vec4 iLoop;
attribute vec4 iColor;
attribute vec4 iWindow;
${COMMON_VERTEX}
varying vec2 vUv;
varying vec3 vColor;
varying float vAlpha;
varying vec3 vDir;
varying float vDist;
void main() {
  float t = uTime;
  float s = iCenter.w;
  // lib/sect/life.ts butterflyPoint: lazy loops through the crown, bobbing with each beat.
  float a = t * iLoop.w + s * 6.2831853;
  float beat = sin( t * iWindow.z * 3.1415927 + s * 20.0 );
  vec3 p = iCenter.xyz + vec3(
    cos( a ) * iLoop.x + sin( a * 2.3 + s * 5.0 ) * iLoop.x * 0.3,
    sin( a * 1.7 + s * 3.0 ) * iLoop.y + beat * 0.12,
    sin( a ) * iLoop.z + cos( a * 1.9 + s * 2.0 ) * iLoop.z * 0.3
  );
  vec3 toC = p - cameraPosition;
  float dist = length( toC );
  float k = sectLifeWindow( uFrame, iWindow.x, iWindow.y ) * smoothstep( 1.0, 3.0, dist ) * ( 1.0 - smoothstep( 160.0, 220.0, dist ) );
  if ( k < 0.004 ) { ${CULL} }
  vec4 mv = viewMatrix * vec4( p, 1.0 );
  float hs = iColor.w;
  float drawn = max( hs, ${f(Bf.minPx * 0.5)} * sectLifePixel( - mv.z ) );
  k *= sqrt( hs / drawn );
  // The wings fold up and open again (seen edge-on they narrow to the body).
  float open = mix( 0.12, 1.0, abs( beat ) );
  float tilt = sin( t * 0.9 + s * 9.0 ) * 0.3;
  vec2 q = vec2( position.x * open, position.y * 0.8 );
  q = vec2( q.x * cos( tilt ) - q.y * sin( tilt ), q.x * sin( tilt ) + q.y * cos( tilt ) );
  mv.xy += q * drawn;
  vUv = position.xy;
  vColor = iColor.rgb;
  vAlpha = k;
  vDir = toC / max( dist, 1e-3 );
  vDist = dist;
  gl_Position = projectionMatrix * mv;
}
`,
    fragmentShader: /* glsl */ `
uniform vec3 uFogColor;
varying vec2 vUv;
varying vec3 vColor;
varying float vAlpha;
varying vec3 vDir;
varying float vDist;
${fogLibrary(fog)}
void main() {
  // Two lobes a side (forewing and hindwing) and a thin dark body.
  vec2 p = vec2( abs( vUv.x ), vUv.y );
  float aa = max( fwidth( vUv.x ), 1e-4 ) * 1.5;
  float fore = length( ( p - vec2( 0.5, 0.25 ) ) / vec2( 0.5, 0.55 ) );
  float hind = length( ( p - vec2( 0.36, - 0.38 ) ) / vec2( 0.36, 0.4 ) );
  float wing = max( 1.0 - smoothstep( 1.0 - aa * 2.0, 1.0, fore ), 1.0 - smoothstep( 1.0 - aa * 2.0, 1.0, hind ) );
  float body = ( 1.0 - smoothstep( 0.05, 0.05 + aa, p.x ) ) * ( 1.0 - smoothstep( 0.6, 0.7, abs( vUv.y ) ) );
  float a = max( wing, body ) * vAlpha;
  if ( a < 0.01 ) discard;
  // Paler toward the wing roots, a dark body; slightly luminous (spirit butterflies).
  vec3 col = mix( vColor * ( 0.95 + 0.2 * ( 1.0 - min( fore, hind ) ) ), vec3( 0.03, 0.025, 0.02 ), body * ( 1.0 - wing * 0.6 ) );
  col = sectAerial( col, uFogColor, vDir, sectHazeDepth( cameraPosition.y, vDir.y, vDist ) );
  gl_FragColor = vec4( col, a );
  #include <colorspace_fragment>
}
`,
  });
}

// ---------------------------------------------------------------------------------------------

interface Part {
  mesh: Mesh;
  geo: InstancedBufferGeometry;
  material: ShaderMaterial;
  groups: Float32Array;
}

/** One instanced quad draw over a packed table, its vec4 attributes in order. */
function makePart(name: string, packed: Packed, attrs: readonly string[], material: ShaderMaterial, quad: PlaneGeometry, renderOrder: number): Part | null {
  if (packed.count === 0) {
    material.dispose();
    return null;
  }
  const geo = new InstancedBufferGeometry();
  geo.setIndex(quad.getIndex());
  geo.setAttribute("position", quad.getAttribute("position"));
  const buf = new InstancedInterleavedBuffer(packed.data, packed.stride, 1);
  attrs.forEach((a, i) => geo.setAttribute(a, new InterleavedBufferAttribute(buf, 4, i * 4)));
  geo.instanceCount = packed.count;
  const mesh = new Mesh(geo, material);
  mesh.name = name;
  // Positions come from the shader; the per-frame group test stands in for frustum culling.
  mesh.frustumCulled = false;
  mesh.renderOrder = renderOrder;
  mesh.visible = false;
  return { mesh, geo, material, groups: packed.groups };
}

export interface LifeProps {
  meta: SectMeta;
  store: SectStore;
  fog: FogConstants;
  quality: Quality;
}

/**
 * Birds, motes and butterflies. Hidden (no draw) while none of a kind's groups is in its stretch of
 * the flight and in view. With reduced motion the birds and butterflies are gone and a third of the
 * motes stand still.
 */
export function Life({ meta, store, fog, quality }: LifeProps) {
  const built = useMemo(() => {
    const tables = buildLifeTables(meta, store.camera, { from: SECT_LOOK.twilight.from, to: SECT_LOOK.twilight.to });
    const quad = new PlaneGeometry(2, 2);
    const birds = makePart("sect.life.birds", tables.birds, ["iRoute", "iPath", "iSlot", "iWing", "iWindow"], birdMaterial(fog, meta.fog.color), quad, 6);
    const motes = makePart("sect.life.motes", tables.motes, ["iHome", "iShape", "iColor", "iWindow"], moteMaterial(fog), quad, 7);
    const flies = makePart(
      "sect.life.butterflies",
      tables.butterflies,
      ["iCenter", "iLoop", "iColor", "iWindow"],
      butterflyMaterial(fog, meta.fog.color),
      quad,
      6,
    );
    // Scratch for the per-frame view test (no allocations in the frame loop).
    const frustum = new Frustum();
    const m = new Matrix4();
    const sphere = new Sphere();
    const inView = (x: number, y: number, z: number, r: number) => {
      sphere.center.set(x, y, z);
      sphere.radius = r;
      return frustum.intersectsSphere(sphere);
    };
    return { tables, quad, birds, motes, flies, frustum, m, inView };
  }, [meta, store, fog]);

  useEffect(
    () => () => {
      for (const p of [built.birds, built.motes, built.flies]) {
        if (!p) continue;
        p.geo.dispose();
        p.material.dispose();
      }
      built.quad.dispose();
    },
    [built],
  );

  const tier = lifeTier(quality);
  const counts = useMemo<{ moving: LifeCounts; still: LifeCounts }>(
    () => ({ moving: lifeCounts(built.tables.totals, tier, false), still: lifeCounts(built.tables.totals, tier, true) }),
    [built, tier],
  );

  useFrame((state) => {
    const still = store.reducedMotion;
    const c = still ? counts.still : counts.moving;
    const t = still ? 0 : state.clock.elapsedTime;
    const frame = store.frame;
    const viewH = state.size.height * state.viewport.dpr;
    built.m.multiplyMatrices(state.camera.projectionMatrix, state.camera.matrixWorldInverse);
    built.frustum.setFromProjectionMatrix(built.m);
    drive(built.birds, c.birds, t, frame, viewH, built.inView);
    drive(built.motes, c.motes, t, frame, viewH, built.inView);
    drive(built.flies, c.butterflies, t, frame, viewH, built.inView);
  });

  return (
    <>
      {built.birds && <primitive object={built.birds.mesh} />}
      {built.motes && <primitive object={built.motes.mesh} />}
      {built.flies && <primitive object={built.flies.mesh} />}
    </>
  );
}

function drive(
  part: Part | null,
  count: number,
  t: number,
  frame: number,
  viewH: number,
  inView: (x: number, y: number, z: number, r: number) => boolean,
): void {
  if (!part) return;
  if (count <= 0) {
    part.mesh.visible = false;
    return;
  }
  if (part.geo.instanceCount !== count) part.geo.instanceCount = count;
  const live = firstLiveGroup(part.groups, frame, inView) >= 0;
  part.mesh.visible = live;
  if (!live) return;
  const u = part.material.uniforms;
  u.uTime.value = t;
  u.uFrame.value = frame;
  u.uViewH.value = viewH;
}
