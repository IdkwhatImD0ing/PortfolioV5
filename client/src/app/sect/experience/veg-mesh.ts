/**
 * The crown shells' three.js side (lib/sect/veg.ts holds the maths and the GLSL): the material, one
 * instanced draw per chunk, the trunks under the crowns (one more instanced draw per chunk), and the
 * baked far-tree cards a chunk's shells stand in for.
 */
import {
  Box3,
  BufferAttribute,
  DoubleSide,
  InstancedBufferAttribute,
  InstancedBufferGeometry,
  type IUniform,
  type Material,
  Mesh,
  type Object3D,
  ShaderMaterial,
  Sphere,
  UniformsLib,
  UniformsUtils,
  Vector2,
  Vector3,
  type Vector4,
} from "three";
import {
  shellGeometry,
  vegFragmentGlsl,
  vegTrunkFragmentGlsl,
  vegTrunkVertexGlsl,
  vegVertexGlsl,
  VEG_LOOK,
  type ShellGeometry,
  type ShellInstances,
  type TrunkInstances,
} from "@/lib/sect/veg";
import { enableFogEncodeOnce, isTreeCardMaterial, SECT_LOOK_GPU } from "./materials";
import { proxyOf } from "./prepare";

/** Uniforms every chunk's shell material shares. */
export interface VegUniforms {
  /** Direction toward the sun (the world context's sunDir). */
  uVegSun: IUniform<Vector3>;
  /** Switch distances (CARD_LOOK.farCut from, to): nearer than its cell's, a tree is the baked card's. */
  uVegNear: IUniform<Vector2>;
  /**
   * The boughs' strength (vegBoughUniform): slope lean, brightness at the deepest crease, share of both
   * kept when a cell is large on screen, unused. One object for every chunk, so it can be tuned live.
   */
  uVegBough: IUniform<Vector4>;
  /**
   * The drawing buffer's height in pixels (veg.tsx sets it every frame): the trunks' ribbons are never thinner
   * on screen than VEG_LOOK.trunk.minPx. The shells do not read it.
   */
  uVegViewH: IUniform<number>;
}

/**
 * Tells sprite card materials where the shells take over (0, 0: the cards draw everywhere). The cards stay
 * visible: near the camera they are the tree, past their cell's switch distance their fragments are dropped.
 */
export function setCardFarCut(meshes: readonly Mesh[], from: number, to: number): void {
  for (const m of meshes) {
    for (const mat of Array.isArray(m.material) ? m.material : [m.material]) {
      const u = ((mat.userData.sectCardFar as { value: Vector2 } | undefined) ??= { value: new Vector2(0, 0) });
      mat.userData.sectCardFar = u;
      u.value.set(from, to);
    }
  }
}

let shaders: { vertex: string; fragment: string } | null = null;
const shells = new Map<number, ShellGeometry>();

/** The unit crown at VEG_LOOK.detail (made once). */
export function vegShell(): ShellGeometry {
  let s = shells.get(VEG_LOOK.detail);
  if (!s) {
    s = shellGeometry(VEG_LOOK.detail);
    shells.set(VEG_LOOK.detail, s);
  }
  return s;
}

/**
 * A chunk's shell material. One per chunk, so a chunk's teardown (assets.ts disposeObjects) frees
 * only its own; three compiles one program for all of them (same source). Opaque, depth written,
 * fogged by the page's haze like the baked surfaces. Alpha to coverage on a multisampled buffer
 * softens the eroded edge.
 */
export function createVegMaterial(uniforms: VegUniforms, name: string, alphaToCoverage: boolean): ShaderMaterial {
  shaders ??= { vertex: vegVertexGlsl(), fragment: vegFragmentGlsl() };
  const material = new ShaderMaterial({
    name,
    // Not through UniformsUtils.merge: that would clone the shared sun direction and bough strength.
    uniforms: { ...UniformsUtils.clone(UniformsLib.fog), ...uniforms, ...SECT_LOOK_GPU },
    vertexShader: shaders.vertex,
    fragmentShader: shaders.fragment,
    fog: true,
  });
  material.alphaToCoverage = alphaToCoverage;
  enableFogEncodeOnce(material);
  material.toneMapped = false;
  return material;
}

/**
 * One instanced draw of a chunk's shells, culled as a whole by a sphere round every crown (instance
 * positions are world positions: the mesh goes under a set's root, which sits at the origin).
 * Every chunk gets its own copy of the unit shell: disposing a geometry deletes the GL buffers of
 * every attribute it holds.
 */
export function createShellMesh(inst: ShellInstances, material: ShaderMaterial): Mesh {
  const shell = vegShell();
  const geo = new InstancedBufferGeometry();
  geo.setIndex(new BufferAttribute(shell.indices.slice(), 1));
  geo.setAttribute("position", new BufferAttribute(shell.positions.slice(), 3));
  geo.setAttribute("iCenter", new InstancedBufferAttribute(inst.center, 3));
  geo.setAttribute("iShape", new InstancedBufferAttribute(inst.shape, 4));
  geo.setAttribute("iParams", new InstancedBufferAttribute(inst.params, 4));
  geo.setAttribute("iDepth", new InstancedBufferAttribute(inst.depth, 1));
  geo.instanceCount = inst.count;
  const b = inst.bounds ?? { center: [0, 0, 0], radius: 0, min: [0, 0, 0], max: [0, 0, 0] };
  geo.boundingSphere = new Sphere(new Vector3(...b.center), b.radius);
  geo.boundingBox = new Box3(new Vector3(...b.min), new Vector3(...b.max));
  const mesh = new Mesh(geo, material);
  mesh.name = material.name;
  mesh.frustumCulled = true;
  mesh.castShadow = false;
  mesh.receiveShadow = false;
  mesh.matrixAutoUpdate = false;
  // Picking never tests shells (the pick lists hold hotspot meshes only; this is for any other ray).
  mesh.raycast = () => {};
  mesh.userData.sectVeg = true;
  return mesh;
}

let trunkShaders: { vertex: string; fragment: string } | null = null;

/**
 * A chunk's trunk material, made as the shell material is (createVegMaterial): one per chunk, one program
 * for all, opaque and depth written, fogged by the page's haze, alpha to coverage on a multisampled buffer
 * (the share of a trunk's true width when it is drawn at the least width, and its soft edge). Both sides:
 * the ribbon turns to face the camera, so which side shows never matters.
 */
export function createVegTrunkMaterial(uniforms: VegUniforms, name: string, alphaToCoverage: boolean): ShaderMaterial {
  trunkShaders ??= { vertex: vegTrunkVertexGlsl(), fragment: vegTrunkFragmentGlsl() };
  const material = new ShaderMaterial({
    name,
    // Not through UniformsUtils.merge: that would clone the shared sun direction, switch distances and view height.
    uniforms: { ...UniformsUtils.clone(UniformsLib.fog), ...uniforms, ...SECT_LOOK_GPU },
    vertexShader: trunkShaders.vertex,
    fragmentShader: trunkShaders.fragment,
    fog: true,
    side: DoubleSide,
  });
  material.alphaToCoverage = alphaToCoverage;
  enableFogEncodeOnce(material);
  material.toneMapped = false;
  return material;
}

/** The unit ribbon: x across (-1..1), y from the foot (0) to the top (1); two triangles. */
const TRUNK_QUAD = {
  positions: Float32Array.of(-1, 0, 0, 1, 0, 0, 1, 1, 0, -1, 1, 0),
  indices: Uint16Array.of(0, 1, 2, 0, 2, 3),
};

/**
 * One instanced draw of a chunk's trunks (lib/sect/veg.ts TrunkInstances), as createShellMesh does the
 * crowns: its own copy of the unit ribbon, culled as a whole by a sphere round every trunk, never picked, no
 * shadow of its own, under the set's root beside the shells. Two triangles a trunk.
 */
export function createTrunkMesh(trunks: TrunkInstances, material: ShaderMaterial): Mesh {
  const geo = new InstancedBufferGeometry();
  geo.setIndex(new BufferAttribute(TRUNK_QUAD.indices.slice(), 1));
  geo.setAttribute("position", new BufferAttribute(TRUNK_QUAD.positions.slice(), 3));
  geo.setAttribute("iFoot", new InstancedBufferAttribute(trunks.foot, 3));
  geo.setAttribute("iTop", new InstancedBufferAttribute(trunks.top, 3));
  geo.setAttribute("iTrunk", new InstancedBufferAttribute(trunks.params, 4));
  geo.instanceCount = trunks.count;
  const b = trunks.bounds ?? { center: [0, 0, 0], radius: 0, min: [0, 0, 0], max: [0, 0, 0] };
  geo.boundingSphere = new Sphere(new Vector3(...b.center), b.radius);
  geo.boundingBox = new Box3(new Vector3(...b.min), new Vector3(...b.max));
  const mesh = new Mesh(geo, material);
  mesh.name = material.name;
  mesh.frustumCulled = true;
  mesh.castShadow = false;
  mesh.receiveShadow = false;
  mesh.matrixAutoUpdate = false;
  // Never picked and never in a pointer ray's way (scene.tsx's occlusion test casts rays at its occluders).
  mesh.raycast = () => {};
  // Not a card (farCardMeshes), like the shells.
  mesh.userData.sectVeg = true;
  return mesh;
}

/** The trunks' triangles per tree. */
export const TRUNK_TRIANGLES = TRUNK_QUAD.indices.length / 3;

/** Frees a shell (or trunk) mesh's buffers and material and takes it off its parent. */
export function disposeShellMesh(mesh: Mesh): void {
  mesh.removeFromParent();
  mesh.geometry.dispose();
  (mesh.material as Material).dispose();
}

/**
 * The baked far-tree card meshes (material trees.cards.*) the shells replace in these roots. Left
 * out: the backdrop's per-area stand-ins (extras.proxyOf: scene.tsx World shows and hides them by
 * the area's own chunk, and no shells stand in for them), click targets' vegetation (in the set's
 * hotspot lists, or tagged with a hotspot: their cards keep the highlight and the pick), and the
 * shells and trunks themselves.
 */
export function farCardMeshes(roots: readonly Object3D[], hotspotMeshes: ReadonlyMap<string, readonly Mesh[]>): Mesh[] {
  const hot = new Set<Object3D>();
  for (const list of hotspotMeshes.values()) for (const m of list) hot.add(m);
  const out: Mesh[] = [];
  for (const r of roots) {
    r.traverse((o) => {
      const m = o as Mesh;
      if (!m.isMesh || m.userData?.sectVeg) return;
      const mats = Array.isArray(m.material) ? m.material : [m.material];
      if (mats.length === 0 || !mats.every((mat) => mat && isTreeCardMaterial(mat))) return;
      if (proxyOf(m) !== null || hot.has(m) || typeof m.userData?.hotspot === "string") return;
      out.push(m);
    });
  }
  return out;
}
