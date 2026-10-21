"use client";

/**
 * Grass tufts on every loaded area's lawns (lib/sect/grass.ts), with the edge fringe and rim bushes
 * of lib/sect/grass-edge.ts. Built once per area set after it loads, in slices of a few
 * milliseconds: the set's ground and rock triangles are read into world-space soups and scattered
 * by distance to the area's stretch of the flight. Once the area's textures are on the GPU, every
 * root is read from its atlas in one small pass (one point per instance, read back without a
 * stall): covered ground (paths, plazas, ground under ground, all baked black) loses its tufts,
 * soil keeps a share of them, and each instance keeps its texel. Then 32 m cells, one instanced
 * draw each. Each frame a cell draws the instances its nearest point needs (sorted by rank),
 * nearest cells first, within the tier's budget; the vertex shader thins and shrinks the rest by
 * each tuft's own distance.
 *
 * Colour comes from the bake: the root texel is graded like the baked ground (look.ts sectGrade)
 * under the ground's colour patches (detail.ts sectGroundTint), so every tuft carries the light and
 * shadow baked under it. Blades run darker at the root and lighter, warmer at the tip; the low sun
 * shines through the tips when the camera looks toward it, only where the ground is lit; far away
 * the gradient flattens to the ground's own colour. The wind is the ground's sheen field, so tufts
 * bow where the bright bands roll across the lawn.
 *
 * The grass keeps no reference to the atlases once its roots are read; the grass of a dropped set
 * is disposed here (its geometries; one material serves every area).
 */
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import {
  Box3,
  BufferAttribute,
  BufferGeometry,
  Color,
  DoubleSide,
  Frustum,
  Group,
  HalfFloatType,
  InstancedBufferAttribute,
  InstancedBufferGeometry,
  type IUniform,
  type Material,
  type Matrix3,
  Matrix4,
  Mesh,
  type MeshBasicMaterial,
  NearestFilter,
  NoBlending,
  type Object3D,
  OrthographicCamera,
  Points,
  Scene,
  ShaderMaterial,
  Sphere,
  type Texture,
  UniformsLib,
  UniformsUtils,
  Vector2,
  Vector3,
  type WebGLRenderer,
  WebGLRenderTarget,
} from "three";
import { groundTintGlsl } from "@/lib/sect/detail";
import { glslFloat, glslVec3 } from "@/lib/sect/glsl";
import {
  camIndex,
  cellCount,
  cellDistance,
  cellSteps,
  emptyInstances,
  fitBudget,
  FLOWER_COLORS,
  GRASS,
  grassRingGlsl,
  grassRootGlsl,
  grassTier,
  grassWindGlsl,
  mergeInstances,
  RANK_STEP,
  ROOT,
  rootSteps,
  scatterSteps,
  sheetIndex,
  type GrassCell,
  type GrassInstances,
  type GrassTier,
  type GrassTierName,
  type GroundSoup,
  type Pond,
  type RockSoup,
} from "@/lib/sect/grass";
import { fringeInstances, grassEdgeSteps, rimClumps } from "@/lib/sect/grass-edge";
import { gradeGlsl, SECT_LOOK } from "@/lib/sect/look";
import type { Quality } from "@/lib/sect/runtime";
import type { SectMeta } from "@/lib/sect/types";
import { dominantFlatLevel } from "@/lib/sect/water";
import type { LoadedSet, WorldContext } from "./assets";
import { getGroundNoiseTexture } from "./materials";
import { wake, type SectStore } from "./store";

const f = glslFloat;

/** What a frame drew (window.__sect.grass.stats()). */
export interface GrassStats {
  tier: GrassTierName;
  /** Areas with their grass built, and still building. */
  built: number;
  building: number;
  /** Instances held on the GPU over the built areas. */
  resident: number;
  /** Cells in view with something to draw, before the maxDraws cut. */
  inView: number;
  /** Cells drawn this frame, the instances they submitted, and the triangles (9 a tuft). */
  cells: number;
  instances: number;
  triangles: number;
  /** The budget's scale on every density this frame (1 = within budget). */
  scale: number;
  /** Main-thread time of the per-frame cell pass (ms, smoothed). */
  cpuMs: number;
  /**
   * Per area: candidates scattered, instances kept once the roots were read, cells, main-thread
   * milliseconds of the build and its longest slice, the edge instances (fringe and rim bushes) and the pond levels found.
   */
  areas: Record<string, { candidates: number; instances: number; cells: number; buildMs: number; longestMs: number; steps: Record<string, number>; fringe: number; rim: number; ponds: number[] }>;
}

/** window.__sect.grass in debug mode: switch the grass off and on, and read what it drew. */
export interface GrassDebug {
  enabled: boolean;
  stats: () => GrassStats;
}

export function createGrassDebug(): GrassDebug & { current: GrassStats } {
  const current: GrassStats = { tier: "off", built: 0, building: 0, resident: 0, inView: 0, cells: 0, instances: 0, triangles: 0, scale: 1, cpuMs: 0, areas: {} };
  return { enabled: true, current, stats: () => ({ ...current, areas: { ...current.areas } }) };
}

// ---------------------------------------------------------------------------------------------
// Shaders

/** Off the clip volume, so nothing rasterises. */
const CULL = "gl_Position = vec4( 2.0, 2.0, 2.0, 1.0 ); vColor = vec3( 0.0 ); return;";

/** Blade width, the tuft's footprint and the flower heads are given for a tuft this tall (m). */
const REF_H = 0.45;

function grassVertexShader(): string {
  const C = GRASS.colour;
  const W = GRASS.wind;
  const T = GRASS.tuft;
  const F = GRASS.flowers;
  return /* glsl */ `
attribute vec3 iPos;
attribute vec4 iCol;
attribute vec4 iA;
attribute vec4 iB;
uniform float uSectGroundLayers;
uniform float uTime;
uniform float uViewH;
uniform float uMinPx;
uniform float uShare;
uniform float uMaxDist;
uniform float uFadeFrom;
uniform float uScale;
uniform vec3 uSun;
uniform vec3 uSunColor;
uniform vec3 uFlower[ ${FLOWER_COLORS.length} ];
varying vec3 vColor;
#include <common>
#include <fog_pars_vertex>
${grassRingGlsl()}
${gradeGlsl(SECT_LOOK.grade)}
${groundTintGlsl()}
${grassWindGlsl()}
float sectGrassHash( vec2 p ) {
  vec3 p3 = fract( vec3( p.xyx ) * 0.1031 );
  p3 += dot( p3, p3.yzx + 33.33 );
  return fract( ( p3.x + p3.y ) * p3.z );
}
void main() {
  // iA: rank, seed, size, kind; iB: lean, lean yaw, flower (lib/sect/grass.ts GrassInstances);
  // iCol: the root texel (grass.ts ROOT: sqrt of linear, and the greenness in alpha).
  float kind = iA.w;
  bool rim = abs( kind - 2.0 ) < 0.5;
  bool lawn = kind < 0.5 || kind > 2.5;
  float sizeM = 0.25 + iA.z * ${f(2.25 / 255)};
  vec3 toC = iPos - cameraPosition;
  float dist = length( toC );
  // A flower tuft turns its last two blades into the flower heads on blades 0 and 1 (their stems).
  float flower = kind > 2.5 ? iB.z : 0.0;
  bool head = flower > 0.5 && position.z > 4.5;
  float bi = head ? position.z - 5.0 : position.z;
  float rank = ( iA.x + 0.5 ) * ${f(RANK_STEP)};
  // Toward the tier's far end the tufts thin out and shrink together (grass.ts heightFade).
  float fade = 1.0 - smoothstep( uMaxDist * uFadeFrom, uMaxDist, dist );
  float D = dist < uMaxDist ? sectGrassDensity( dist ) * uShare * uScale * fade : 0.0;
  float grow;
  if ( rim ) {
    // A rim bush shows out to its own reach (grass.ts rimDrawDist), shrinking over the last 10 %.
    float reach = min( 450.0, sizeM * 200.0 );
    grow = 1.0 - smoothstep( reach * 0.9, reach, dist );
  } else {
    if ( rank >= D ) { ${CULL} }
    grow = fade;
  }
  float sizeK = 1.0;
  if ( lawn ) {
    // The last 10 % of a tuft's rank shrinks it, so density changes have no steps; fewer, larger
    // tufts far away keep the cover.
    grow *= clamp( ( D - rank ) / ( 0.1 * D ), 0.0, 1.0 );
    sizeK = sectGrassSize( dist );
  }
  if ( grow <= 0.0 ) { ${CULL} }
  float green = clamp( ( iCol.a * 255.0 - ${f(ROOT.alpha0)} ) / ${f(255 - ROOT.alpha0)}, 0.0, 1.0 );
  // The ground's colour there: graded like the baked ground, under its colour patches.
  vec3 root = sectGrade( iCol.rgb * iCol.rgb );
  root = mix( root, sectGroundTint( root, iPos ), uSectGroundLayers );
  float rootL = dot( root, vec3( 0.2126, 0.7152, 0.0722 ) );

  // This tuft and this blade.
  float h0 = sectGrassHash( iPos.xz * 1.37 + iA.y * 0.173 );
  float h1 = sectGrassHash( iPos.zx * 2.11 + iA.y * 0.071 + 5.3 );
  float hb = sectGrassHash( vec2( h0 * 91.7 + bi * 7.13, h1 * 53.1 + bi * 3.71 ) );
  float hc = sectGrassHash( vec2( hb * 17.9 + 0.3, h0 * 29.3 + bi * 1.9 ) );
  bool stem = flower > 0.5 && bi < 1.5;

  float H = sizeM * sizeK * grow;
  float scaleH = clamp( H / ${f(REF_H)}, 0.5, 4.0 );
  // Blades on a sunflower spiral out to the tuft's footprint, the middle ones tallest.
  float phi = h0 * 6.2831853 + bi * 2.3999632 + ( hb - 0.5 ) * 0.7;
  vec2 outward = vec2( cos( phi ), sin( phi ) );
  float rr = sqrt( ( bi + 0.5 ) / ${f(T.blades)} ) * mix( 0.55, 1.1, hc );
  vec3 base = iPos + vec3( outward.x, 0.0, outward.y ) * rr * ${f(T.spread)} * scaleH;
  float len = H * mix( 0.6, 1.0, hb ) * ( 1.0 - 0.3 * rr ) * ( stem ? 1.3 : 1.0 );
  // Lean as a tilt (radians along a direction): the tuft's own (grass-edge.ts leanDir: yaw 0 is
  // +z, pi / 2 is +x), each blade fanning out from the middle, and the wind downwind.
  float la = iB.x * ${f((75 * Math.PI) / 180 / 255)};
  float ly = iB.y * ${f((Math.PI * 2) / 256)};
  vec2 lean = vec2( sin( ly ), cos( ly ) ) * la + outward * ( 0.1 + 0.45 * rr ) * ( rim ? 0.6 : 1.0 );
  float gust = sectGrassGust( iPos.xz );
  float bob = ${f(W.bob)} * sin( uTime * 6.2831853 * mix( ${f(W.bobHz[0])}, ${f(W.bobHz[1])}, h1 ) + h0 * 6.2831853 + bi * 0.9 );
  lean += SECT_GRASS_WIND * ( mix( ${f(W.bend[0])}, ${f(W.bend[1])}, gust ) + bob ) * mix( 0.7, 1.0, hb );
  float lean2 = length( lean );
  float tilt = min( lean2, 1.45 );
  vec2 ld = lean / max( lean2, 1e-4 );
  vec3 axis = vec3( ld.x * sin( tilt ), cos( tilt ), ld.y * sin( tilt ) );
  vec3 tip = base + axis * len;

  vec4 mvBase = viewMatrix * vec4( base, 1.0 );
  // World metres per pixel at the root's depth.
  float px = 2.0 * max( - mvBase.z, 0.1 ) / ( projectionMatrix[ 1 ][ 1 ] * uViewH );
  vec4 mvPosition;
  float t;
  if ( head ) {
    // A flower facing the camera at the stem's tip, never much smaller than a pixel.
    bool spirit = flower > ${f(FLOWER_COLORS.length - 0.5)};
    // Single flowers go before they shrink to specks (a spirit herb's glow carries farther).
    float hf = 1.0 - smoothstep( ${f(F.fadeM[0])}, ${f(F.fadeM[1])}, spirit ? dist * 0.75 : dist );
    if ( hf <= 0.0 ) { ${CULL} }
    float r = max( 0.035 * scaleH * ( spirit ? 1.5 : 1.0 ), 0.75 * px ) * hf;
    mvPosition = viewMatrix * vec4( tip, 1.0 );
    // The blade's corners (-1, 0), (1, 0), (0, 1) as a triangle about the tip.
    mvPosition.xy += ( position.y > 0.5 ? vec2( 0.0, 1.0 ) : vec2( position.x * 0.866, -0.5 ) ) * r;
    t = 1.0;
  } else {
    // A tapered blade turned to face the camera about its own axis, never thinner than uMinPx.
    vec3 side = cross( axis, normalize( cameraPosition - base ) );
    float sl = length( side );
    side = sl > 1e-4 ? side / sl : vec3( 1.0, 0.0, 0.0 );
    float w = max( ${f(T.width)} * mix( 0.75, 1.25, hc ) * scaleH * ( stem ? 0.5 : 1.0 ), uMinPx * px );
    t = position.y;
    mvPosition = viewMatrix * vec4( mix( base + side * position.x * w * 0.5, tip, t ), 1.0 );
  }
  gl_Position = projectionMatrix * mvPosition;

  // Colour: darker at the root, lighter and warmer at the tip, a little different blade to blade.
  vec3 col = root * mix( ${f(C.root)}, ${f(C.tip)}, t ) * mix( 0.92, 1.06, hb ) * ( 1.0 + ( h1 - 0.5 ) * ${f(2 * C.clump)} );
  col *= mix( vec3( 1.0 ), ${glslVec3([...C.tipWarm])}, t );
  // On soil the tips are straw (at the ground's brightness).
  vec3 straw = ${glslVec3([...C.straw])};
  col = mix( col, straw * ( rootL / dot( straw, vec3( 0.2126, 0.7152, 0.0722 ) ) ) * 1.15, t * ( 1.0 - green ) * 0.6 );
  // Gusts lift the bent tips; the sun shines through them toward the camera, where the ground is lit.
  col *= 1.0 + ${f(W.gustLift)} * gust * t;
  float back = pow( max( dot( toC / max( dist, 1e-3 ), uSun ), 0.0 ), ${f(C.backPower)} );
  col += uSunColor * back * ${f(C.backAmount)} * clamp( rootL / ${f(C.backLit)}, 0.0, 1.0 ) * t;
  if ( head ) {
    // Flowers take the light at the root (a white flower in shadow is not white); the spirit herb glows.
    int k = int( flower + 0.5 ) - 1;
    col = k == ${FLOWER_COLORS.length - 1} ? uFlower[ k ] * 1.8 : uFlower[ k ] * clamp( rootL / 0.08, 0.2, 1.4 );
  } else {
    // Far away the blades flatten toward the ground's own colour (little far shimmer), keeping a
    // share of the root-to-tip shading so far clumps still read as tussocks.
    col = mix( col, root, smoothstep( ${f(C.flatten[0])}, ${f(C.flatten[1])}, dist ) * ${f(1 - C.flattenKeep)} );
  }
  vColor = col;
  #include <fog_vertex>
}
`;
}

const GRASS_FRAGMENT = /* glsl */ `
varying vec3 vColor;
#include <common>
#include <fog_pars_fragment>
void main() {
  gl_FragColor = vec4( vColor, 1.0 );
  #include <colorspace_fragment>
  #include <fog_fragment>
}
`;

/** One point per root at pixel (id mod width, id / width); the width is a power of two (exact division). */
const ROOT_VERTEX = /* glsl */ `
uniform vec2 uSize;
varying vec2 vUv;
void main() {
  float id = float( gl_VertexID );
  float y = floor( id / uSize.x );
  float x = id - y * uSize.x;
  vUv = position.xy;
  gl_Position = vec4( ( x + 0.5 ) / uSize.x * 2.0 - 1.0, ( y + 0.5 ) / uSize.y * 2.0 - 1.0, 0.0, 1.0 );
  gl_PointSize = 1.0;
}
`;

const ROOT_FRAGMENT = /* glsl */ `
uniform sampler2D tMap;
varying vec2 vUv;
${grassRootGlsl()}
void main() {
  gl_FragColor = sectGrassRoot( tMap, vUv );
}
`;

/** Uniforms of the grass material (shared by every area's cells). */
interface GrassUniforms {
  uTime: IUniform<number>;
  uViewH: IUniform<number>;
  uMinPx: IUniform<number>;
  uShare: IUniform<number>;
  uMaxDist: IUniform<number>;
  uFadeFrom: IUniform<number>;
  uScale: IUniform<number>;
  uSun: IUniform<Vector3>;
  uSunColor: IUniform<Color>;
  uFlower: IUniform<Color[]>;
  /** Set when the first area's grass starts building (the low tier, which has none, never builds it). */
  tSectGroundNoise: IUniform<Texture | null>;
  uSectGroundLayers: IUniform<number>;
}

/**
 * 7 one-triangle blades (side, 0 root / 1 tip, blade): 21 vertices. A flower tuft draws its last
 * two as the flower heads (heads of their own cost every tuft 6 more vertices).
 */
function tuftGeometry(): BufferAttribute {
  const v: number[] = [];
  for (let b = 0; b < GRASS.tuft.blades; b++) v.push(-1, 0, b, 1, 0, b, 0, 1, b);
  return new BufferAttribute(new Float32Array(v), 3);
}

/** Width of the root read's target (a power of two, so the shader's division is exact). */
const ROOT_WIDTH = 1024;

/** The root read's material (its atlas uniform changes per read), compiled once, off the frame. */
let rootMaterial: { gl: WebGLRenderer; material: ShaderMaterial; ready: Promise<unknown> } | null = null;

function rootReader(gl: WebGLRenderer): { material: ShaderMaterial; ready: Promise<unknown> } {
  if (rootMaterial?.gl === gl) return rootMaterial;
  rootMaterial?.material.dispose();
  const material = new ShaderMaterial({
    name: "sect.grass.roots",
    uniforms: { tMap: { value: null }, uSize: { value: new Vector2(1, 1) } },
    vertexShader: ROOT_VERTEX,
    fragmentShader: ROOT_FRAGMENT,
    depthTest: false,
    depthWrite: false,
    blending: NoBlending,
  });
  material.toneMapped = false;
  const geo = new BufferGeometry();
  geo.setAttribute("position", new BufferAttribute(new Uint16Array(2), 2, true));
  const points = new Points(geo, material);
  const scene = new Scene();
  scene.add(points);
  // Compiled for the kind of target it draws into (three keys programs by the output's colour space).
  const rt = new WebGLRenderTarget(1, 1, { depthBuffer: false });
  const prev = gl.getRenderTarget();
  let ready: Promise<unknown>;
  try {
    gl.setRenderTarget(rt);
    ready = gl.compileAsync(scene, new OrthographicCamera());
  } finally {
    gl.setRenderTarget(prev);
  }
  ready = ready.finally(() => {
    geo.dispose();
    rt.dispose();
  });
  rootMaterial = { gl, material, ready };
  return rootMaterial;
}

/** Lets go of the root read's material with its canvas (it would keep the closed renderer alive). */
function releaseRootReader(gl: WebGLRenderer): void {
  if (rootMaterial?.gl !== gl) return;
  rootMaterial.material.dispose();
  rootMaterial = null;
}

/**
 * The root texel of every instance (grass.ts ROOT, 4 bytes each), read from the atlases on the GPU:
 * one point per instance into an RGBA8 target per atlas, read back asynchronously (no stall). The
 * atlases must already be on the GPU (the set is ready). Null when the set went meanwhile.
 */
async function readRoots(gl: WebGLRenderer, inst: GrassInstances, atlases: readonly Texture[], alive: () => boolean, clock: Clock): Promise<Uint8Array | null> {
  const reader = rootReader(gl);
  await reader.ready;
  if (!alive()) return null;
  const out = new Uint8Array(inst.count * 4);
  const camera = new OrthographicCamera();
  for (let k = 0; k < atlases.length; k++) {
    let t0 = performance.now();
    let n = 0;
    for (let i = 0; i < inst.count; i++) if (inst.atlas[i] === k) n++;
    if (n === 0) continue;
    const idx = new Int32Array(n);
    const uv = new Uint16Array(n * 2);
    for (let i = 0, o = 0; i < inst.count; i++) {
      if (inst.atlas[i] !== k) continue;
      idx[o] = i;
      uv[o * 2] = inst.uv[i * 2];
      uv[o * 2 + 1] = inst.uv[i * 2 + 1];
      o++;
    }
    const w = ROOT_WIDTH;
    const h = Math.ceil(n / w);
    const geo = new BufferGeometry();
    geo.setAttribute("position", new BufferAttribute(uv, 2, true));
    // Not computed from the (two-component) UVs.
    geo.boundingSphere = new Sphere(new Vector3(), 1);
    const material = reader.material;
    material.uniforms.tMap.value = atlases[k];
    (material.uniforms.uSize.value as Vector2).set(w, h);
    const points = new Points(geo, material);
    points.frustumCulled = false;
    const scene = new Scene();
    scene.add(points);
    const rt = new WebGLRenderTarget(w, h, { depthBuffer: false, minFilter: NearestFilter, magFilter: NearestFilter, generateMipmaps: false });
    const buf = new Uint8Array(w * h * 4);
    try {
      const prev = gl.getRenderTarget();
      try {
        gl.setRenderTarget(rt);
        gl.render(scene, camera);
      } finally {
        gl.setRenderTarget(prev);
      }
      material.uniforms.tMap.value = null;
      clock.add(performance.now() - t0, "read");
      await gl.readRenderTargetPixelsAsync(rt, 0, 0, w, h, buf);
    } finally {
      rt.dispose();
      geo.dispose();
    }
    if (!alive()) return null;
    t0 = performance.now();
    for (let o = 0; o < n; o++) {
      const i = idx[o];
      for (let c = 0; c < 4; c++) out[i * 4 + c] = buf[o * 4 + c];
    }
    clock.add(performance.now() - t0, "read");
  }
  return out;
}

// ---------------------------------------------------------------------------------------------
// Building an area's grass

interface CellDraw {
  cell: GrassCell;
  mesh: Mesh;
  geo: InstancedBufferGeometry;
  /** performance.now() when its area's grass went up: it grows in over GROW_MS. */
  born: number;
}

/**
 * An area's grass, built while the area is on screen (on arrival, or after a fast scroll), grows in
 * over this many milliseconds (ms): each cell draws a rising share of its instances, lowest rank
 * first, so the lawn thickens evenly instead of appearing at once. With reduced motion it appears
 * at once.
 */
const GROW_MS = 1500;

/**
 * Frees a cell's own buffers. Its tuft shape (the kit's `base`) is shared by every cell, and three
 * deletes the GL buffer of every attribute a disposed geometry holds: the other cells would draw
 * from a deleted buffer and the next one uploaded the shape again. So it is taken off first, unless
 * every cell goes (`shared` false).
 */
function disposeDraw(d: CellDraw, shared = true): void {
  if (shared) d.geo.deleteAttribute("position");
  d.geo.dispose();
}

interface Built {
  set: LoadedSet;
  draws: CellDraw[];
  instances: number;
}

/** What the scatter needs from a set's meshes. */
interface Soups {
  ground: GroundSoup;
  rock: RockSoup;
  atlases: Texture[];
  sheets: Float32Array;
  ponds: Pond[];
}

class Floats {
  a = new Float32Array(4096);
  n = 0;
  push(v: number): void {
    if (this.n === this.a.length) {
      const b = new Float32Array(this.a.length * 2);
      b.set(this.a);
      this.a = b;
    }
    this.a[this.n++] = v;
  }
  done(): Float32Array {
    return this.a.slice(0, this.n);
  }
}

/** A mesh's triangles in world space: positions (9 a triangle) and, with uv, UVs (6 a triangle). */
function* readTriangles(mesh: Mesh, pos: Floats, uv: Floats | null, uvMatrix: Matrix3 | null): Generator<void> {
  const g = mesh.geometry as BufferGeometry;
  const p = g.getAttribute("position");
  const t = uv ? g.getAttribute("uv") : null;
  if (!p || (uv && !t)) return;
  const n = p.count;
  const world = new Float32Array(n * 3);
  const v = new Vector3();
  for (let i = 0; i < n; i++) {
    v.fromBufferAttribute(p, i).applyMatrix4(mesh.matrixWorld);
    world[i * 3] = v.x;
    world[i * 3 + 1] = v.y;
    world[i * 3 + 2] = v.z;
  }
  let tex: Float32Array | null = null;
  if (t) {
    tex = new Float32Array(n * 2);
    const q = new Vector3();
    for (let i = 0; i < n; i++) {
      q.set(t.getX(i), t.getY(i), 1);
      if (uvMatrix) q.applyMatrix3(uvMatrix);
      tex[i * 2] = q.x;
      tex[i * 2 + 1] = q.y;
    }
  }
  const index = g.index;
  const tris = index ? index.count / 3 : n / 3;
  for (let k = 0; k < tris; k++) {
    if ((k & 2047) === 2047) yield;
    for (let c = 0; c < 3; c++) {
      const i = index ? index.getX(k * 3 + c) : k * 3 + c;
      pos.push(world[i * 3]);
      pos.push(world[i * 3 + 1]);
      pos.push(world[i * 3 + 2]);
      if (uv && tex) {
        uv.push(tex[i * 2]);
        uv.push(tex[i * 2 + 1]);
      }
    }
  }
}

/** The set's ground (detail "ground"), rock (detail "rock") and water sheets, and its ponds. */
function* collectSoups(set: LoadedSet, ctx: WorldContext): Generator<void, Soups> {
  const gPos = new Floats();
  const gUv = new Floats();
  const gAtlas: number[] = [];
  const rPos = new Floats();
  const sPos = new Floats();
  const atlases: Texture[] = [];
  const meshes: Mesh[] = [];
  for (const root of set.scenes) {
    root.traverse((o: Object3D) => {
      const m = o as Mesh;
      if (m.isMesh && !Array.isArray(m.material) && !(m as unknown as { isInstancedMesh?: boolean }).isInstancedMesh) meshes.push(m);
    });
  }
  for (const mesh of meshes) {
    const mat = mesh.material as Material;
    const detail = mat.userData?.detail;
    if (detail === "ground") {
      const map = (mat as MeshBasicMaterial).map;
      if (!map) continue;
      let k = atlases.indexOf(map);
      if (k < 0) {
        k = atlases.length;
        atlases.push(map);
      }
      // A texture transform (none in the shipped files) moves the UVs as the material reads them.
      if (map.matrixAutoUpdate) map.updateMatrix();
      const identity = map.matrix.elements.every((e, i) => e === (i % 4 === 0 ? 1 : 0));
      const before = gPos.n / 9;
      yield* readTriangles(mesh, gPos, gUv, identity ? null : map.matrix);
      for (let t = before; t < gPos.n / 9; t++) gAtlas.push(k);
    } else if (detail === "rock") {
      yield* readTriangles(mesh, rPos, null, null);
    } else if (mat === ctx.sheetMaterial || mat === ctx.waterfallMaterial) {
      yield* readTriangles(mesh, sPos, null, null);
    }
    yield;
  }
  // Ponds: the Still Pond's reflection level, and any other pond hotspot's largest level surface.
  const ponds: Pond[] = [];
  if (set.pond) ponds.push({ level: set.pond.level, min: set.pond.box.min.toArray(), max: set.pond.box.max.toArray() });
  for (const [id, list] of set.hotspotMeshes) {
    if (!/pond/i.test(id) || list.length === 0) continue;
    const box = new Box3();
    let best: { level: number; area: number } | null = null;
    for (const m of list) {
      box.expandByObject(m);
      const p = new Floats();
      const it = readTriangles(m, p, null, null);
      while (!it.next().done);
      const lvl = dominantFlatLevel(p.done(), null);
      if (lvl && (!best || lvl.area > best.area)) best = lvl;
    }
    if (best && best.area >= 20) ponds.push({ level: best.level, min: box.min.toArray(), max: box.max.toArray() });
  }
  return {
    ground: { pos: gPos.done(), uv: gUv.done(), atlas: Uint8Array.from(gAtlas) },
    rock: { pos: rPos.done() },
    atlases,
    sheets: sPos.done(),
    ponds,
  };
}

/** Camera positions of the set's stretch of the flight and its hold (3 floats each). */
function cameraPoints(set: LoadedSet, store: SectStore): Float32Array {
  const out: number[] = [];
  const [lo, hi] = set.need ?? [-Infinity, Infinity];
  for (const fr of store.camera.frames) if (fr.f >= lo && fr.f <= hi) out.push(fr.p[0], fr.p[1], fr.p[2]);
  const hold = store.camera.holds.find((h) => h.id === set.id);
  const fr = hold ? store.camera.frames.find((x) => x.f === hold.frame) : undefined;
  if (fr) out.push(fr.p[0], fr.p[1], fr.p[2]);
  return new Float32Array(out);
}

const nextTask = () => new Promise<void>((res) => setTimeout(res, 0));

/** Main-thread time of a build: the total and the longest uninterrupted slice (ms). */
class Clock {
  ms = 0;
  longest = 0;
  /** The longest slice of each named step. */
  steps: Record<string, number> = {};
  add(ms: number, name: string): void {
    this.ms += ms;
    this.longest = Math.max(this.longest, ms);
    this.steps[name] = Math.round(Math.max(this.steps[name] ?? 0, ms) * 10) / 10;
  }
}

/** Runs a generator in slices of at most `budget` ms of main-thread time; null when cancelled. */
async function sliced<T>(name: string, it: Generator<unknown, T>, alive: () => boolean, clock: Clock, budget = 6): Promise<T | null> {
  let t0 = performance.now();
  for (;;) {
    const r = it.next();
    if (r.done) {
      clock.add(performance.now() - t0, name);
      return r.value;
    }
    if (performance.now() - t0 > budget) {
      clock.add(performance.now() - t0, name);
      await nextTask();
      if (!alive()) return null;
      t0 = performance.now();
    }
  }
}

/** A plain step as one slice of its own. */
async function step<T>(name: string, fn: () => T, alive: () => boolean, clock: Clock): Promise<T | null> {
  await nextTask();
  if (!alive()) return null;
  const t0 = performance.now();
  const v = fn();
  clock.add(performance.now() - t0, name);
  return v;
}

// ---------------------------------------------------------------------------------------------

export interface GrassProps {
  /** The streamed chunks (the global set has no lawns of its own to grow on). */
  chunks: LoadedSet[];
  ctx: WorldContext;
  meta: SectMeta;
  store: SectStore;
  quality: Quality;
  debug: GrassDebug & { current: GrassStats };
}

/**
 * Grass on the drawn areas. Off on the low tier (no postprocessing); fewer and nearer tufts on
 * mid, and on high once the page has stepped down (grass.ts grassTier). With reduced motion the
 * wind's clock stands still (the waterfalls' uTime), so the tufts rest as they lean, and new grass
 * appears at once instead of growing in.
 */
export function Grass({ chunks, ctx, meta, store, quality, debug }: GrassProps) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const dpr = typeof window !== "undefined" ? window.devicePixelRatio : 1;
  const tierName = grassTier(quality, dpr);
  const tierRef = useRef(tierName);
  tierRef.current = tierName;
  const post = useRef(quality.post);
  post.current = quality.post;

  const kit = useMemo(() => {
    const group = new Group();
    group.name = "sect.grass";
    const uniforms: GrassUniforms = {
      uTime: ctx.waterfallMaterial.uniforms.uTime as IUniform<number>,
      uViewH: { value: 1000 },
      uMinPx: { value: GRASS.tiers.high.minPx },
      uShare: { value: 1 },
      uMaxDist: { value: GRASS.tiers.high.maxDist },
      uFadeFrom: { value: GRASS.tiers.high.fadeFrom },
      uScale: { value: 1 },
      uSun: { value: ctx.sunDir },
      uSunColor: { value: new Color(meta.sun.color) },
      uFlower: { value: FLOWER_COLORS.map((c) => new Color(c)) },
      tSectGroundNoise: { value: null },
      // The ground's own switch for its patches (test scripts turn the layers off through it).
      uSectGroundLayers: ctx.detail?.uSectGroundLayers ?? { value: 1 },
    };
    const material = new ShaderMaterial({
      name: "sect.grass",
      // Not through UniformsUtils.merge: that would clone the shared uniforms and textures.
      uniforms: { ...UniformsUtils.clone(UniformsLib.fog), ...uniforms },
      vertexShader: grassVertexShader(),
      fragmentShader: GRASS_FRAGMENT,
      fog: true,
      side: DoubleSide,
    });
    material.toneMapped = false;
    return {
      group,
      uniforms,
      material,
      base: tuftGeometry(),
      built: new Map<LoadedSet, Built>(),
      building: new Set<LoadedSet>(),
      frustum: new Frustum(),
      m: new Matrix4(),
      sphere: new Sphere(),
      warmTarget: null as WebGLRenderTarget | null,
      /** The grass program has been compiled ahead of its first draw. */
      warmed: false,
    };
  }, [ctx, meta]);

  const live = useRef(chunks);
  live.current = chunks;
  /** The build queue runs once at a time, across chunk list changes; it stops for good on unmount. */
  const runner = useRef({ running: false, unmounted: false });

  // Build each new area's grass (one at a time), and dispose the grass of areas that went.
  useEffect(() => {
    const R = runner.current;
    R.unmounted = false;
    for (const [s, b] of kit.built) {
      if (!chunks.includes(s) || s.dropped) {
        for (const d of b.draws) {
          kit.group.remove(d.mesh);
          disposeDraw(d);
        }
        delete debug.current.areas[b.set.id];
        kit.built.delete(s);
      }
    }
    if (tierName === "off" || R.running) return;
    // The ground's patch noise (shared with the ground shader where there is one).
    kit.uniforms.tSectGroundNoise.value ??= getGroundNoiseTexture();
    const alive = (s: LoadedSet) => !R.unmounted && !s.dropped && live.current.includes(s);
    const build = async (set: LoadedSet) => {
      const name = tierRef.current;
      if (name === "off") return;
      const tier = GRASS.tiers[name];
      const ok = () => alive(set);
      const clock = new Clock();
      const soups = await sliced("collect", collectSoups(set, ctx), ok, clock);
      if (!soups || soups.ground.pos.length === 0 || soups.atlases.length === 0) return;
      const prep = await step(
        "prep",
        () => {
          const cams = cameraPoints(set, store);
          return { cams, index: camIndex(cams), sheets: soups.sheets.length > 0 ? sheetIndex(soups.sheets) : null };
        },
        ok,
        clock,
      );
      if (!prep) return;
      const { cams, sheets } = prep;
      const tufts = await sliced("scatter", scatterSteps(soups.ground, prep.index, { tier, ponds: soups.ponds, sheets }), ok, clock);
      if (!tufts) return;
      // The edge fringe and rim bushes are extras: if they fail, the tufts still grow. The edges are
      // found first, over several frames (grass-edge.ts keeps them for the soups, so the fringe and
      // the bushes then take a millisecond or two).
      let edgesFailed = false;
      try {
        const edges = await sliced("edges", grassEdgeSteps(soups.ground, soups.rock), ok, clock);
        if (!edges) return;
      } catch (e) {
        console.warn(`[sect] grass edges for ${set.id} failed; the tufts go on without them`, e);
        edgesFailed = true;
      }
      const edgeOpts = { ponds: soups.ponds, sheets };
      const edge = (name: string, fn: () => GrassInstances) => () => {
        if (edgesFailed) return emptyInstances();
        try {
          return fn();
        } catch (e) {
          console.warn(`[sect] grass ${name} for ${set.id} failed; the tufts go on without it`, e);
          return emptyInstances();
        }
      };
      const fringe = await step("fringe", edge("fringe", () => fringeInstances(soups.ground, soups.rock, cams, edgeOpts)), ok, clock);
      if (!fringe) return;
      const rim = await step("rim", edge("rim bushes", () => rimClumps(soups.ground, soups.rock, cams, edgeOpts)), ok, clock);
      if (!rim) return;
      const all = await step("merge", () => mergeInstances([tufts, fringe, rim]), ok, clock);
      if (!all) return;
      // The roots are read from the atlases once they are on the GPU (the set is ready).
      while (!set.ready) {
        await new Promise((res) => setTimeout(res, 200));
        if (!ok()) return;
      }
      const texels = await readRoots(gl, all, soups.atlases, ok, clock);
      if (!texels) return;
      const rooted = await sliced("roots", rootSteps(all, texels), ok, clock);
      if (!rooted) return;
      const cells = await sliced("cells", cellSteps(rooted), ok, clock);
      if (!cells) return;
      const draws = await step(
        "meshes",
        () =>
          cells.map((cell): CellDraw => {
            const geo = new InstancedBufferGeometry();
            geo.setAttribute("position", kit.base);
            geo.setAttribute("iPos", new InstancedBufferAttribute(cell.pos, 3));
            geo.setAttribute("iCol", new InstancedBufferAttribute(cell.col, 4, true));
            geo.setAttribute("iA", new InstancedBufferAttribute(cell.a, 4));
            geo.setAttribute("iB", new InstancedBufferAttribute(cell.b, 4));
            geo.instanceCount = 0;
            // three sorts opaque draws front to back by this sphere (the base tuft's would be wrong).
            geo.boundingSphere = new Sphere(new Vector3(...cell.center), cell.radius);
            geo.boundingBox = new Box3(new Vector3(...cell.min), new Vector3(...cell.max));
            const mesh = new Mesh(geo, kit.material);
            mesh.name = `sect.grass.${set.id}`;
            // Culled here, per cell; picking never tests grass.
            mesh.frustumCulled = false;
            mesh.raycast = () => {};
            mesh.matrixAutoUpdate = false;
            mesh.visible = false;
            return { cell, mesh, geo, born: 0 };
          }),
        ok,
        clock,
      );
      if (!draws) return;
      if (draws.length > 0 && !kit.warmed) {
        // Compile for the buffer the grass is drawn into, as World's warm-up does for the sets (one
        // program serves every area).
        const holder = new Group();
        holder.add(draws[0].mesh);
        try {
          const prev = gl.getRenderTarget();
          let pending: Promise<unknown>;
          try {
            if (post.current) {
              kit.warmTarget ??= new WebGLRenderTarget(1, 1, { type: HalfFloatType, depthBuffer: false });
              gl.setRenderTarget(kit.warmTarget);
            }
            pending = gl.compileAsync(holder, camera, scene);
          } finally {
            gl.setRenderTarget(prev);
          }
          await pending;
          kit.warmed = true;
        } catch (e) {
          console.warn("[sect] grass shader warm-up failed", e);
        }
      }
      if (!ok()) {
        for (const d of draws) disposeDraw(d);
        return;
      }
      const born = performance.now();
      for (const d of draws) {
        d.born = born;
        kit.group.add(d.mesh);
      }
      // Every display frame while it grows in on screen (the canvas otherwise idles when nothing
      // moves); with reduced motion, one frame to show it.
      if (draws.length > 0 && set.drawn) wake(store, store.reducedMotion ? 100 : GROW_MS + 100);
      kit.built.set(set, { set, draws, instances: rooted.count });
      debug.current.areas[set.id] = {
        candidates: all.count,
        instances: rooted.count,
        cells: cells.length,
        buildMs: Math.round(clock.ms),
        longestMs: Math.round(clock.longest * 10) / 10,
        steps: clock.steps,
        fringe: fringe.count,
        rim: rim.count,
        ponds: soups.ponds.map((p) => Math.round(p.level * 100) / 100),
      };
    };
    const run = async () => {
      R.running = true;
      try {
        for (;;) {
          // The area on screen first, then the others in flight order.
          const todo = live.current.filter((s) => !s.dropped && !kit.built.has(s));
          if (R.unmounted || tierRef.current === "off" || todo.length === 0) return;
          const next = todo.find((s) => s.drawn) ?? todo.find((s) => s.need && store.frame >= s.need[0] && store.frame <= s.need[1]) ?? todo[0];
          kit.building.add(next);
          try {
            await build(next);
          } catch (e) {
            console.warn(`[sect] grass for ${next.id} failed; the area goes on without it`, e);
          } finally {
            kit.building.delete(next);
          }
          // Built, failed or left: never tried again while it stays loaded.
          if (!kit.built.has(next) && alive(next)) kit.built.set(next, { set: next, draws: [], instances: 0 });
        }
      } finally {
        R.running = false;
      }
    };
    void run();
  }, [chunks, tierName, kit, ctx, store, gl, camera, scene, debug]);

  // Everything goes with the canvas.
  useEffect(() => {
    const R = runner.current;
    return () => {
      R.unmounted = true;
      for (const b of kit.built.values()) {
        for (const d of b.draws) {
          kit.group.remove(d.mesh);
          disposeDraw(d, false);
        }
      }
      kit.built.clear();
      kit.material.dispose();
      kit.warmTarget?.dispose();
      kit.warmTarget = null;
      kit.warmed = false;
      releaseRootReader(gl);
    };
  }, [kit, gl]);

  const pick = useMemo(() => ({ list: [] as CellDraw[], dists: [] as number[], order: [] as number[], cells: [] as GrassCell[], kept: [] as number[] }), []);
  useFrame((state) => {
    const t0 = performance.now();
    const name = tierRef.current;
    const st = debug.current;
    st.tier = name;
    st.built = kit.built.size;
    st.building = kit.building.size;
    st.resident = 0;
    for (const b of kit.built.values()) st.resident += b.instances;
    const on = debug.enabled && name !== "off";
    const tier: GrassTier = GRASS.tiers[name === "off" ? "mid" : name];
    const U = kit.uniforms;
    U.uViewH.value = state.size.height * state.viewport.dpr;
    U.uMinPx.value = tier.minPx;
    U.uShare.value = tier.share;
    U.uMaxDist.value = tier.maxDist;
    U.uFadeFrom.value = tier.fadeFrom;
    const cam = state.camera.position;
    kit.m.multiplyMatrices(state.camera.projectionMatrix, state.camera.matrixWorldInverse);
    kit.frustum.setFromProjectionMatrix(kit.m);
    pick.list.length = 0;
    pick.dists.length = 0;
    for (const b of kit.built.values()) {
      const shown = on && b.set.drawn && !b.set.dropped;
      for (const d of b.draws) {
        d.mesh.visible = false;
        if (!shown) continue;
        const dist = cellDistance(d.cell, cam.x, cam.y, cam.z);
        if (cellCount(d.cell, dist, tier) === 0) continue;
        kit.sphere.center.set(d.cell.center[0], d.cell.center[1], d.cell.center[2]);
        kit.sphere.radius = d.cell.radius;
        if (!kit.frustum.intersectsSphere(kit.sphere)) continue;
        pick.list.push(d);
        pick.dists.push(dist);
      }
    }
    // Nearest first, at most maxDraws; densities scale down evenly to fit the tufts budget.
    pick.order.length = 0;
    for (let i = 0; i < pick.list.length; i++) pick.order.push(i);
    pick.order.sort((a, b) => pick.dists[a] - pick.dists[b]);
    if (pick.order.length > tier.maxDraws) pick.order.length = tier.maxDraws;
    pick.cells.length = 0;
    pick.kept.length = 0;
    for (const i of pick.order) {
      pick.cells.push(pick.list[i].cell);
      pick.kept.push(pick.dists[i]);
    }
    const scale = fitBudget(pick.cells, pick.kept, tier);
    U.uScale.value = scale;
    let cells = 0;
    let instances = 0;
    for (const i of pick.order) {
      const d = pick.list[i];
      const grow = store.reducedMotion ? 1 : Math.min(1, (t0 - d.born) / GROW_MS);
      const n = Math.ceil(cellCount(d.cell, pick.dists[i], tier, scale) * grow * grow);
      if (n === 0) continue;
      d.geo.instanceCount = n;
      d.mesh.visible = true;
      cells++;
      instances += n;
    }
    st.inView = pick.list.length;
    st.cells = cells;
    st.instances = instances;
    st.triangles = instances * 9;
    st.scale = scale;
    st.cpuMs += (performance.now() - t0 - st.cpuMs) * 0.1;
  }, -1);

  return <primitive object={kit.group} />;
}
