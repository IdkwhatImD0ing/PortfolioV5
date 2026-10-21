"use client";

/**
 * Decoration the style frames have and the bake does not: peach petals drifting around the camera,
 * a few cranes circling high over the two areas, the forge cauldron's fire and the formation's
 * brazier fires (a flickering glow and rising sparks; the film's emission and particles cannot be
 * baked). Each is one draw. Motion follows lib/sect/fx.ts (petalOffset is mirrored in the petal
 * vertex shader).
 */
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import {
  AdditiveBlending,
  Box3,
  Color,
  DoubleSide,
  DynamicDrawUsage,
  InstancedBufferAttribute,
  InstancedBufferGeometry,
  type InstancedMesh,
  Matrix4,
  Mesh,
  PlaneGeometry,
  ShaderMaterial,
  Vector3,
} from "three";
import { clusterFlames, fireRadius, formationTier, type FormationTierName } from "@/lib/sect/formation";
import { craneFlights, cranePose, PETAL_STRIDE, PETAL_WIND, petalSeeds } from "@/lib/sect/fx";
import { fogLibrary, type FogConstants } from "@/lib/sect/glsl";
import { breathe } from "@/lib/sect/idle";
import { SECT_LOOK } from "@/lib/sect/look";
import type { SectMeta, Vec3 } from "@/lib/sect/types";
import type { LoadedSet } from "./assets";
import type { SectStore } from "./store";

function petalMaterial(sunDir: Vector3): ShaderMaterial {
  const p = SECT_LOOK.petals;
  return new ShaderMaterial({
    name: "sect.petals",
    transparent: true,
    depthWrite: false,
    side: DoubleSide,
    fog: false,
    uniforms: {
      uTime: { value: 0 },
      uRadius: { value: p.radius },
      uSize: { value: p.size },
      uWind: { value: new Vector3(...PETAL_WIND) },
      uColorA: { value: new Color(p.colorA) },
      uColorB: { value: new Color(p.colorB) },
      uSun: { value: sunDir },
    },
    vertexShader: /* glsl */ `
attribute vec3 iSeed;
attribute vec3 iData;
uniform float uTime;
uniform float uRadius;
uniform float uSize;
uniform vec3 uWind;
uniform vec3 uSun;
varying vec2 vUv;
varying float vMix;
varying float vShade;
varying float vFade;
vec3 wrapv( vec3 a, float n ) { return a - n * floor( a / n ); }
mat3 rotX( float a ) { float c = cos( a ), s = sin( a ); return mat3( 1.0, 0.0, 0.0, 0.0, c, s, 0.0, -s, c ); }
mat3 rotY( float a ) { float c = cos( a ), s = sin( a ); return mat3( c, 0.0, -s, 0.0, 1.0, 0.0, s, 0.0, c ); }
void main() {
  float phase = iData.x;
  float spin = iData.y;
  // lib/sect/fx.ts petalOffset: seed point carried by the wind with a sideways flutter, wrapped
  // into a cube that always surrounds the camera.
  vec3 flutter = vec3( sin( uTime * 1.3 + phase ), 0.0, sin( uTime * 1.3 + phase + 2.0 ) ) * 0.6;
  vec3 p = iSeed * uRadius + uWind * uTime + flutter;
  vec3 local = wrapv( p - cameraPosition + uRadius, 2.0 * uRadius ) - uRadius;
  mat3 R = rotY( uTime * spin + phase ) * rotX( uTime * spin * 0.7 + phase * 1.3 );
  vec3 wp = cameraPosition + local + R * vec3( position.x * uSize, position.y * uSize * 0.62, 0.0 );
  vec3 n = R * vec3( 0.0, 0.0, 1.0 );
  vShade = 0.62 + 0.38 * abs( dot( n, uSun ) );
  vMix = iData.z;
  vUv = position.xy;
  float edge = max( max( abs( local.x ), abs( local.y ) ), abs( local.z ) ) / uRadius;
  // Gone near the camera (closer than about 10 m a petal stops reading as a petal and becomes a pink
  // blot) and at the cube's faces, where it wraps.
  vFade = ( 1.0 - smoothstep( 0.7, 1.0, edge ) ) * smoothstep( 8.0, 12.0, length( local ) );
  gl_Position = projectionMatrix * viewMatrix * vec4( wp, 1.0 );
}
`,
    fragmentShader: /* glsl */ `
uniform vec3 uColorA;
uniform vec3 uColorB;
varying vec2 vUv;
varying float vMix;
varying float vShade;
varying float vFade;
void main() {
  // A peach petal: an egg shape with a small notch at the wide end.
  vec2 q = vUv;
  float d = length( vec2( q.x * ( 1.0 + 0.35 * q.y ), q.y ) );
  float notch = smoothstep( 0.18, 0.0, abs( q.x ) ) * smoothstep( 0.55, 0.95, q.y );
  float a = ( 1.0 - smoothstep( 0.82, 1.0, d ) ) * ( 1.0 - notch ) * vFade;
  if ( a < 0.02 ) discard;
  // Two tones: deeper pink at the narrow base where it held the flower, paler toward the wide tip,
  // with a faint midrib.
  vec3 tint = mix( uColorA, uColorB, vMix );
  vec3 col = mix( tint * vec3( 0.86, 0.62, 0.7 ), mix( tint, vec3( 1.0, 0.95, 0.95 ), 0.35 ), smoothstep( -0.9, 0.6, q.y ) );
  col *= 1.0 - 0.08 * ( 1.0 - smoothstep( 0.0, 0.07, abs( q.x ) ) ) * smoothstep( -0.8, 0.4, q.y );
  col *= vShade;
  gl_FragColor = vec4( col, a * 0.92 );
  #include <colorspace_fragment>
}
`,
  });
}

export function Petals({ count, store, sunDir }: { count: number; store: SectStore; sunDir: Vec3 }) {
  const built = useMemo(() => {
    if (count <= 0) return null;
    const seeds = petalSeeds(count);
    const quad = new PlaneGeometry(2, 2);
    const geo = new InstancedBufferGeometry();
    geo.setIndex(quad.getIndex());
    geo.setAttribute("position", quad.getAttribute("position"));
    const seed = new Float32Array(count * 3);
    const data = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      seed.set(seeds.subarray(i * PETAL_STRIDE, i * PETAL_STRIDE + 3), i * 3);
      data.set(seeds.subarray(i * PETAL_STRIDE + 3, i * PETAL_STRIDE + 6), i * 3);
    }
    geo.setAttribute("iSeed", new InstancedBufferAttribute(seed, 3));
    geo.setAttribute("iData", new InstancedBufferAttribute(data, 3));
    geo.instanceCount = count;
    const material = petalMaterial(new Vector3(...sunDir).normalize());
    const mesh = new Mesh(geo, material);
    mesh.frustumCulled = false;
    mesh.renderOrder = 6;
    mesh.name = "sect.petals";
    return { mesh, material, quad };
  }, [count, sunDir]);
  useEffect(
    () => () => {
      built?.mesh.geometry.dispose();
      built?.quad.dispose();
      built?.material.dispose();
    },
    [built],
  );
  useFrame((state) => {
    if (built) built.material.uniforms.uTime.value = store.reducedMotion ? 0 : state.clock.elapsedTime;
  });
  return built ? <primitive object={built.mesh} /> : null;
}

function craneMaterial(fog: FogConstants, fogColor: string): ShaderMaterial {
  return new ShaderMaterial({
    name: "sect.cranes",
    transparent: true,
    depthWrite: false,
    fog: false,
    uniforms: {
      uColor: { value: new Color(SECT_LOOK.cranes.color) },
      uDark: { value: new Color(SECT_LOOK.cranes.dark) },
      uCrown: { value: new Color(SECT_LOOK.cranes.crown) },
      uFogColor: { value: new Color(fogColor) },
    },
    vertexShader: /* glsl */ `
attribute vec3 iPos;
attribute float iFlap;
attribute float iHeading;
varying vec2 vUv;
varying float vFlap;
varying float vAlong;
varying vec3 vDir;
varying float vDist;
void main() {
  vec3 toC = iPos - cameraPosition;
  float dist = length( toC );
  vec3 f = toC / max( dist, 1e-3 );
  vec3 r = normalize( cross( f, vec3( 0.0, 1.0, 0.0 ) ) );
  vec3 u = cross( r, f );
  // A crane spans about 2.2 m; drawn larger far away (they read as birds at 200-400 m, like the style
  // frame's), but near true size close up, where a 9 m wing would fill the view.
  float k = mix( 0.3, 1.0, smoothstep( 40.0, 220.0, dist ) );
  vec3 wp = iPos + ( r * position.x * 4.6 + u * position.y * 2.3 ) * k;
  vUv = position.xy;
  vFlap = iFlap;
  // The flight direction across the screen (lib/sect/fx.ts cranePose: heading 0 flies toward -z):
  // the neck reaches that way and the legs trail behind, shortened when the bird flies at the camera.
  vAlong = dot( vec3( - sin( iHeading ), 0.0, - cos( iHeading ) ), r );
  vDir = f;
  vDist = dist;
  gl_Position = projectionMatrix * viewMatrix * vec4( wp, 1.0 );
}
`,
    fragmentShader: /* glsl */ `
uniform vec3 uColor;
uniform vec3 uDark;
uniform vec3 uCrown;
uniform vec3 uFogColor;
varying vec2 vUv;
varying float vFlap;
varying float vAlong;
varying vec3 vDir;
varying float vDist;
${fogLibrary(fog)}
void main() {
  float x = abs( vUv.x );
  // Wings: the arm rises with the beat to the wrist, where the hand bends sharply back down toward
  // the tip (a gull-wing M in the downstroke, near flat at the top of the beat). Broad at the body,
  // thinning toward the tips.
  float wrist = 0.4;
  float y = vFlap * min( x, wrist ) * 1.15 + max( x - wrist, 0.0 ) * ( vFlap * 0.45 - 0.42 ) - 0.04 * x;
  float th = mix( 0.2, 0.045, smoothstep( 0.05, 1.0, x ) );
  float dy = vUv.y - y;
  float wing = ( 1.0 - smoothstep( th * 0.65, th, abs( dy ) ) ) * step( x, 1.0 );
  // A red-crowned crane's black: the trailing edge of the inner wing (its secondaries) and, as the
  // paintings draw them, the wing tips.
  float black = max( smoothstep( -0.1 * th, -0.45 * th, dy ) * ( 1.0 - smoothstep( 0.55, 0.75, x ) ), smoothstep( 0.72, 0.9, x ) );
  // The body, then the long black neck and head ahead of it, the legs trailing behind (both along
  // the flight direction; a bird flying at the camera shows little of either).
  float s = sign( vAlong + 1e-4 );
  float reach = mix( 0.06, 1.0, abs( vAlong ) );
  float ax = vUv.x * s;
  float body = 1.0 - smoothstep( 0.075, 0.12, length( vec2( vUv.x * 1.5, vUv.y + 0.02 ) ) );
  float neck = ( 1.0 - smoothstep( 0.022, 0.042, abs( vUv.y - 0.01 ) ) ) * step( 0.0, ax ) * step( ax, 0.5 * reach );
  float head = 1.0 - smoothstep( 0.035, 0.055, length( vec2( ax - 0.52 * reach, vUv.y - 0.015 ) ) );
  float legs = ( 1.0 - smoothstep( 0.012, 0.028, abs( vUv.y + 0.03 ) ) ) * step( - 0.48 * reach, ax ) * step( ax, 0.0 );
  float a = max( max( wing, body ), max( max( neck, head ), legs * 0.85 ) ) * smoothstep( 10.0, 25.0, vDist );
  if ( a < 0.05 ) discard;
  // Undersides in shade, upper wing edges catching the low sun; the black parts, then the crown.
  vec3 col = uColor * ( 0.62 + 0.38 * smoothstep( -0.2, 0.3, vUv.y ) );
  col = mix( col, uDark, max( black * wing * ( 1.0 - body ), max( neck, max( head, legs ) ) * ( 1.0 - body ) ) );
  col = mix( col, uCrown, head * ( 1.0 - smoothstep( 0.0, 0.03, length( vec2( ax - 0.53 * reach, vUv.y - 0.04 ) ) ) ) );
  float od = sectHazeDepth( cameraPosition.y, vDir.y, vDist );
  col = mix( col, sectHazeColor( uFogColor, vDir ), 1.0 - exp( - od ) );
  gl_FragColor = vec4( col, a );
  #include <colorspace_fragment>
}
`,
  });
}

// ---------------------------------------------------------------------------------------------
// Forge fire

/** Sparks rising from the cauldron, and how high they go (m). */
const SPARKS = 72;
const SPARK_HEIGHT = 11;

/** A fire material's shape: how high sparks rise, their size and sideways wander, the glow's size per radius. */
interface FireShape {
  rise: number;
  sparkSize: number;
  wander: number;
  glowSize: number;
  core: string;
  hot: string;
}

const FORGE_FIRE: FireShape = { rise: SPARK_HEIGHT, sparkSize: 0.13, wander: 0.35, glowSize: 2.6, core: "#ff9a45", hot: "#ffd27a" };

/**
 * Fires as one instanced draw of camera-facing sprites. Each instance has a seed (iSeed; w < 0 is
 * a fire's glow, w < -1.5 a breathing glow) and its fire (iFire: the fire's foot in the mesh's
 * frame and its radius), so one draw holds many fires. A fire at the mesh's origin flickers in the
 * forge's original phase.
 */
function fireMaterial(shape: FireShape = FORGE_FIRE): ShaderMaterial {
  return new ShaderMaterial({
    name: "sect.forgefire",
    transparent: true,
    depthWrite: false,
    blending: AdditiveBlending,
    fog: false,
    uniforms: {
      uTime: { value: 0 },
      uSparks: { value: 1 },
      uRise: { value: shape.rise },
      uSparkSize: { value: shape.sparkSize },
      uWander: { value: shape.wander },
      uGlowSize: { value: shape.glowSize },
      uCore: { value: new Color(shape.core) },
      uHot: { value: new Color(shape.hot) },
      uBreath: { value: 0 },
    },
    vertexShader: /* glsl */ `
attribute vec4 iSeed;
attribute vec4 iFire;
uniform float uTime;
uniform float uSparks;
uniform float uRise;
uniform float uSparkSize;
uniform float uWander;
uniform float uGlowSize;
varying vec2 vUv;
varying float vLife;
varying float vKind;
varying float vPhase;
void main() {
  vec3 right = vec3( viewMatrix[0][0], viewMatrix[1][0], viewMatrix[2][0] );
  vec3 up = vec3( viewMatrix[0][1], viewMatrix[1][1], viewMatrix[2][1] );
  vUv = position.xy;
  vKind = iSeed.w;
  // Fires flicker out of step (0 for a fire at the origin: the forge as it always was).
  vPhase = dot( iFire.xyz, vec3( 0.37, 0.11, 0.53 ) );
  float radius = iFire.w;
  vec3 c;
  float size;
  if ( iSeed.w < -1.5 ) {
    // A breathing glow (the formation's sun-fire core): one soft sprite, radius iFire.w.
    c = iFire.xyz;
    size = radius;
    vLife = 0.0;
  } else if ( iSeed.w < 0.0 ) {
    // The glow over the bowl: one large soft sprite.
    c = iFire.xyz + vec3( 0.0, radius * 0.7, 0.0 );
    size = radius * uGlowSize;
    vLife = 0.0;
  } else {
    float life = fract( uTime * ( 0.16 + 0.12 * iSeed.z ) + iSeed.w );
    float ang = iSeed.x * 6.2831853 + uTime * 0.6 * ( iSeed.z - 0.5 );
    float r = radius * ( 0.15 + 0.7 * iSeed.y ) * ( 1.0 + life * 0.9 );
    c = iFire.xyz + vec3( cos( ang ) * r, life * uRise, sin( ang ) * r );
    c.x += sin( uTime * 2.3 + iSeed.w * 19.0 ) * uWander * life;
    size = uSparkSize * ( 1.0 - life * 0.55 ) * uSparks;
    vLife = life;
  }
  vec4 wp = modelMatrix * vec4( c, 1.0 );
  wp.xyz += ( right * position.x + up * position.y ) * size;
  gl_Position = projectionMatrix * viewMatrix * wp;
}
`,
    fragmentShader: /* glsl */ `
uniform float uTime;
uniform vec3 uCore;
uniform vec3 uHot;
uniform float uBreath;
varying vec2 vUv;
varying float vLife;
varying float vKind;
varying float vPhase;
void main() {
  float q = length( vUv );
  if ( q > 1.0 ) discard;
  vec3 col;
  if ( vKind < -1.5 ) {
    col = uHot * exp( - q * q * 4.0 ) * uBreath;
  } else if ( vKind < 0.0 ) {
    float flicker = 0.85 + 0.1 * sin( uTime * 7.3 + vPhase ) + 0.06 * sin( uTime * 13.1 + 1.7 + vPhase * 2.3 );
    col = uCore * exp( - q * q * 4.5 ) * 1.25 * flicker;
  } else {
    float a = ( 1.0 - smoothstep( 0.2, 1.0, q ) ) * pow( 1.0 - vLife, 1.4 );
    col = mix( uHot, uCore, vLife ) * a * 3.0;
  }
  // Linear light, added unencoded (as the moon's halo, materials.ts createGlowMaterial): straight
  // onto the sRGB screen (the Low tier) an encoded glow's faint edge is many times too bright.
  gl_FragColor = vec4( col, 1.0 );
}
`,
  });
}

/**
 * The forge cauldron's fire, over the bowl of its glowing embers (the ".glow.ember" meshes): drawn
 * while the forge chunk is. Sparks stop (and hide) with reduced motion; the glow stays.
 */
export function ForgeFire({ set, store }: { set: LoadedSet | null; store: SectStore }) {
  const built = useMemo(() => {
    if (!set) return null;
    const box = new Box3();
    for (const root of set.scenes) {
      root.updateMatrixWorld(true);
      root.traverse((o) => {
        const m = o as Mesh;
        if (m.isMesh && /\.glow\.ember$/i.test((m.material as { name?: string }).name ?? "")) box.expandByObject(m);
      });
    }
    if (box.isEmpty()) return null;
    const size = box.getSize(new Vector3());
    const quad = new PlaneGeometry(2, 2);
    const geo = new InstancedBufferGeometry();
    geo.setIndex(quad.getIndex());
    geo.setAttribute("position", quad.getAttribute("position"));
    // Instance 0 is the glow (w < 0); the rest are sparks with fixed random seeds.
    const seeds = new Float32Array((SPARKS + 1) * 4);
    seeds.set([0, 0, 0, -1], 0);
    let s = 7;
    const rnd = () => {
      s = (s * 16807) % 2147483647;
      return s / 2147483647;
    };
    for (let i = 1; i <= SPARKS; i++) seeds.set([rnd(), rnd(), rnd(), rnd()], i * 4);
    geo.setAttribute("iSeed", new InstancedBufferAttribute(seeds, 4));
    // Every instance belongs to the one fire at the mesh's origin (the bowl).
    const radius = Math.max(0.8, Math.min(size.x, size.z) * 0.45);
    const fire = new Float32Array((SPARKS + 1) * 4);
    for (let i = 0; i <= SPARKS; i++) fire[i * 4 + 3] = radius;
    geo.setAttribute("iFire", new InstancedBufferAttribute(fire, 4));
    geo.instanceCount = SPARKS + 1;
    const material = fireMaterial();
    const mesh = new Mesh(geo, material);
    // On the bowl: the embers' footprint, just above their lowest point (the cauldron's rim).
    mesh.position.set((box.min.x + box.max.x) / 2, box.min.y + 0.5, (box.min.z + box.max.z) / 2);
    mesh.updateMatrixWorld(true);
    mesh.frustumCulled = false;
    mesh.renderOrder = 7;
    mesh.name = "sect.forgefire";
    mesh.visible = false;
    return { mesh, material, quad };
  }, [set]);
  useEffect(
    () => () => {
      built?.mesh.geometry.dispose();
      built?.quad.dispose();
      built?.material.dispose();
    },
    [built],
  );
  useFrame((state) => {
    if (!built || !set) return;
    built.mesh.visible = set.drawn;
    if (!set.drawn) return;
    built.material.uniforms.uTime.value = store.reducedMotion ? 0 : state.clock.elapsedTime;
    built.material.uniforms.uSparks.value = store.reducedMotion ? 0 : 1;
  });
  return built ? <primitive object={built.mesh} /> : null;
}

// ---------------------------------------------------------------------------------------------
// Formation fires

const FLAME = /\.glow\.flame$/i;

/** World positions (xyz triples) of the vertices of a set's meshes whose material matches `re` (instances too). */
function glowVertices(set: LoadedSet, re: RegExp): number[] {
  const out: number[] = [];
  const v = new Vector3();
  const inst = new Matrix4();
  const world = new Matrix4();
  for (const root of set.scenes) {
    root.updateMatrixWorld(true);
    root.traverse((o) => {
      const m = o as Mesh;
      if (!m.isMesh || Array.isArray(m.material) || !re.test(m.material.name ?? "")) return;
      const pos = m.geometry.getAttribute("position");
      if (!pos) return;
      const im = m as InstancedMesh;
      const n = im.isInstancedMesh ? im.count : 1;
      for (let k = 0; k < n; k++) {
        if (im.isInstancedMesh) {
          im.getMatrixAt(k, inst);
          world.multiplyMatrices(m.matrixWorld, inst);
        } else world.copy(m.matrixWorld);
        for (let i = 0; i < pos.count; i++) {
          v.fromBufferAttribute(pos, i).applyMatrix4(world);
          out.push(v.x, v.y, v.z);
        }
      }
    });
  }
  return out;
}

/**
 * The formation's holy fires: a flickering glow and rising sparks over each brazier (the bake's
 * ".glow.flame" meshes, grouped into fires by lib/sect/formation.ts clusterFlames), and the sun-fire
 * core's warm glow at the `formation` hotspot, breathing with its 4 s breath (idle.ts). One draw,
 * while the formation chunk is drawn. Sparks per fire follow the tier (sparks are packed round-robin,
 * so a lower tier draws fewer for every fire); they stop (and hide) with reduced motion, the glows
 * stay. Before the rebake there are no flames: only the core's glow.
 */
export function FormationFires({ set, store, meta, tier }: { set: LoadedSet | null; store: SectStore; meta: SectMeta; tier: FormationTierName }) {
  const built = useMemo(() => {
    if (!set) return null;
    const look = SECT_LOOK.formation;
    const fires = clusterFlames(glowVertices(set, FLAME), look.fire.cell);
    const core = meta.hotspots.find((h) => h.id === "formation");
    if (fires.length === 0 && !core) return null;
    const F = fires.length;
    const S = look.fire.sparks.high;
    const lead = core ? 1 : 0;
    const total = lead + F + F * S;
    const seeds = new Float32Array(total * 4);
    const fire = new Float32Array(total * 4);
    let s = 13;
    const rnd = () => {
      s = (s * 16807) % 2147483647;
      return s / 2147483647;
    };
    if (core) {
      seeds.set([0, 0, 0, -2], 0);
      fire.set([core.center[0], core.center[1], core.center[2], look.coreGlow.radius], 0);
    }
    fires.forEach((f, i) => {
      const at = [f.center[0], f.min[1], f.center[2], fireRadius(f, look)];
      seeds.set([0, 0, 0, -1], (lead + i) * 4);
      fire.set(at, (lead + i) * 4);
      // Spark j of fire i at lead + F + j * F + i: the first n * F sparks are n for every fire.
      for (let j = 0; j < S; j++) {
        const k = lead + F + j * F + i;
        seeds.set([rnd(), rnd(), rnd(), rnd()], k * 4);
        fire.set(at, k * 4);
      }
    });
    const quad = new PlaneGeometry(2, 2);
    const geo = new InstancedBufferGeometry();
    geo.setIndex(quad.getIndex());
    geo.setAttribute("position", quad.getAttribute("position"));
    geo.setAttribute("iSeed", new InstancedBufferAttribute(seeds, 4));
    geo.setAttribute("iFire", new InstancedBufferAttribute(fire, 4));
    geo.instanceCount = total;
    const material = fireMaterial({
      rise: look.fire.sparkHeight,
      sparkSize: look.fire.sparkSize,
      wander: 0.2,
      glowSize: 1.4,
      core: look.fire.core,
      hot: look.coreGlow.color,
    });
    const mesh = new Mesh(geo, material);
    mesh.frustumCulled = false;
    mesh.renderOrder = 7;
    mesh.name = "sect.formationfires";
    mesh.visible = false;
    return { mesh, material, quad, geo, lead, fires: F };
  }, [set, meta]);
  useEffect(
    () => () => {
      built?.mesh.geometry.dispose();
      built?.quad.dispose();
      built?.material.dispose();
    },
    [built],
  );
  useEffect(() => {
    if (built) built.geo.instanceCount = built.lead + built.fires * (1 + formationTier(tier).sparks);
  }, [built, tier]);
  useFrame((state) => {
    if (!built || !set) return;
    built.mesh.visible = set.drawn;
    if (!set.drawn) return;
    const t = store.reducedMotion ? 0 : state.clock.elapsedTime;
    const g = SECT_LOOK.formation.coreGlow;
    built.material.uniforms.uTime.value = t;
    built.material.uniforms.uSparks.value = store.reducedMotion ? 0 : 1;
    built.material.uniforms.uBreath.value = g.strength * (g.rest + (1 - g.rest) * breathe(t, g.period));
  });
  return built ? <primitive object={built.mesh} /> : null;
}

// ---------------------------------------------------------------------------------------------
// Incense smoke

/** Wisps rising from the mirror terrace's censer, and how high they go (m). */
const WISPS = 18;
const WISP_HEIGHT = 3.6;

function smokeMaterial(): ShaderMaterial {
  return new ShaderMaterial({
    name: "sect.incense",
    transparent: true,
    depthWrite: false,
    fog: false,
    uniforms: {
      uTime: { value: 0 },
      uColor: { value: new Color("#e9e2d6") },
    },
    vertexShader: /* glsl */ `
attribute vec4 iSeed;
uniform float uTime;
varying vec2 vUv;
varying float vLife;
void main() {
  vec3 right = vec3( viewMatrix[0][0], viewMatrix[1][0], viewMatrix[2][0] );
  vec3 up = vec3( viewMatrix[0][1], viewMatrix[1][1], viewMatrix[2][1] );
  vUv = position.xy;
  float life = fract( uTime * ( 0.07 + 0.04 * iSeed.z ) + iSeed.w );
  vLife = life;
  // A thin column that curls and spreads as it rises.
  float h = life * ${WISP_HEIGHT.toFixed(1)};
  vec3 c = vec3(
    sin( uTime * 0.7 + iSeed.x * 6.28 + h * 1.3 ) * 0.12 * ( 0.3 + life * 2.2 ),
    h,
    cos( uTime * 0.6 + iSeed.y * 6.28 + h * 1.1 ) * 0.12 * ( 0.3 + life * 2.2 )
  );
  float size = 0.08 + life * 0.42;
  vec4 wp = modelMatrix * vec4( c, 1.0 );
  wp.xyz += ( right * position.x + up * position.y ) * size;
  gl_Position = projectionMatrix * viewMatrix * wp;
}
`,
    fragmentShader: /* glsl */ `
uniform vec3 uColor;
varying vec2 vUv;
varying float vLife;
void main() {
  float q = length( vUv );
  if ( q > 1.0 ) discard;
  float a = exp( - q * q * 3.0 ) * smoothstep( 0.0, 0.12, vLife ) * pow( 1.0 - vLife, 1.6 ) * 0.32;
  gl_FragColor = vec4( uColor, a );
  #include <colorspace_fragment>
}
`,
  });
}

/**
 * A thread of incense smoke over the mirror terrace's censer (its ".glow.ember" bowl), drawn while
 * the mirror chunk is. Hidden with reduced motion.
 */
export function IncenseSmoke({ set, store }: { set: LoadedSet | null; store: SectStore }) {
  const built = useMemo(() => {
    if (!set) return null;
    const box = new Box3();
    for (const root of set.scenes) {
      root.updateMatrixWorld(true);
      root.traverse((o) => {
        const m = o as Mesh;
        if (m.isMesh && /\.glow\.ember$/i.test((m.material as { name?: string }).name ?? "")) box.expandByObject(m);
      });
    }
    if (box.isEmpty()) return null;
    const quad = new PlaneGeometry(2, 2);
    const geo = new InstancedBufferGeometry();
    geo.setIndex(quad.getIndex());
    geo.setAttribute("position", quad.getAttribute("position"));
    const seeds = new Float32Array(WISPS * 4);
    let s = 11;
    const rnd = () => {
      s = (s * 16807) % 2147483647;
      return s / 2147483647;
    };
    for (let i = 0; i < WISPS; i++) seeds.set([rnd(), rnd(), rnd(), i / WISPS + rnd() * 0.04], i * 4);
    geo.setAttribute("iSeed", new InstancedBufferAttribute(seeds, 4));
    geo.instanceCount = WISPS;
    const material = smokeMaterial();
    const mesh = new Mesh(geo, material);
    mesh.position.set((box.min.x + box.max.x) / 2, box.max.y + 0.05, (box.min.z + box.max.z) / 2);
    mesh.updateMatrixWorld(true);
    mesh.frustumCulled = false;
    mesh.renderOrder = 7;
    mesh.name = "sect.incense";
    mesh.visible = false;
    return { mesh, material, quad };
  }, [set]);
  useEffect(
    () => () => {
      built?.mesh.geometry.dispose();
      built?.quad.dispose();
      built?.material.dispose();
    },
    [built],
  );
  useFrame((state) => {
    if (!built || !set) return;
    built.mesh.visible = set.drawn && !store.reducedMotion;
    if (built.mesh.visible) built.material.uniforms.uTime.value = state.clock.elapsedTime;
  });
  return built ? <primitive object={built.mesh} /> : null;
}

export function Cranes({ areas, store, fog, fogColor }: { areas: Vec3[]; store: SectStore; fog: FogConstants; fogColor: string }) {
  const built = useMemo(() => {
    const flights = craneFlights(areas, SECT_LOOK.cranes.count);
    if (flights.length === 0) return null;
    const quad = new PlaneGeometry(2, 2);
    const geo = new InstancedBufferGeometry();
    geo.setIndex(quad.getIndex());
    geo.setAttribute("position", quad.getAttribute("position"));
    const pos = new InstancedBufferAttribute(new Float32Array(flights.length * 3), 3);
    pos.setUsage(DynamicDrawUsage);
    const flap = new InstancedBufferAttribute(new Float32Array(flights.length), 1);
    flap.setUsage(DynamicDrawUsage);
    const heading = new InstancedBufferAttribute(new Float32Array(flights.length), 1);
    heading.setUsage(DynamicDrawUsage);
    geo.setAttribute("iPos", pos);
    geo.setAttribute("iFlap", flap);
    geo.setAttribute("iHeading", heading);
    geo.instanceCount = flights.length;
    const material = craneMaterial(fog, fogColor);
    const mesh = new Mesh(geo, material);
    mesh.frustumCulled = false;
    mesh.renderOrder = 6;
    mesh.name = "sect.cranes";
    return { mesh, material, quad, flights, pos, flap, heading };
  }, [areas, fog, fogColor]);
  useEffect(
    () => () => {
      built?.mesh.geometry.dispose();
      built?.quad.dispose();
      built?.material.dispose();
    },
    [built],
  );
  useFrame((state) => {
    if (!built) return;
    const t = store.reducedMotion ? 0 : state.clock.elapsedTime;
    built.flights.forEach((f, i) => {
      const { p, heading } = cranePose(f, t);
      built.pos.setXYZ(i, p[0], p[1], p[2]);
      built.flap.setX(i, Math.sin(t * 3.4 + f.phase * 5) * 0.45);
      built.heading.setX(i, heading);
    });
    built.pos.needsUpdate = true;
    built.flap.needsUpdate = true;
    built.heading.needsUpdate = true;
  });
  return built ? <primitive object={built.mesh} /> : null;
}
