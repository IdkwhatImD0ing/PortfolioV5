/**
 * A static shadow map live light reads (lib/sect/live.ts, live.tsx): an orthographic depth render
 * from a lamp of what shades a stop, its own meshes and the far things behind them (liveFarCasters).
 * live.tsx keeps two for the stop lit live, one for the key lamp (LIVE_LOOK.shadow) and one for the
 * sun (LIVE_LOOK.sunShadow), each `size` square, covering the stop's radius (live.ts liveStopBox)
 * round its centre and depthM along the lamp. The scene does not move, so a map is drawn once when
 * the stop's set is ready and again only when the casters change, never every frame.
 *
 * The casters are drawn as stand-ins in a scene of their own: one mesh per caster sharing its
 * geometry (and instance matrices), with a depth-only material, placed where the caster stands.
 * The world scene is never touched (its stop's root is hidden whenever the camera is elsewhere,
 * which a render of the world would have to undo), and the main pass is as it was.
 *
 * The depth materials are the page's, not a map's: one per program three builds for them (a plain
 * or instanced caster, with or without normals: lib/sect/program-key.ts programVariant), and for a
 * cut-out caster one per card material as well. A map never frees them, so their programs stay
 * compiled from one stop to the next; compile() gets them ready off the frame before a map's first
 * draw, which makes even the first stop's draw link nothing.
 */
import {
  Color,
  DepthTexture,
  DoubleSide,
  InstancedMesh,
  LessEqualCompare,
  LinearFilter,
  Mesh,
  MeshBasicMaterial,
  NearestFilter,
  OrthographicCamera,
  RedFormat,
  Scene,
  UnsignedByteType,
  UnsignedIntType,
  WebGLRenderTarget,
  type Material,
  type Object3D,
  type Texture,
  type WebGLRenderer,
} from "three";
import { isCutoutCard } from "@/lib/sect/card-shading";
import { programVariant } from "@/lib/sect/program-key";
import { materialsOf, primePrograms } from "./program-prime";

/**
 * Depth-only materials of the solid casters, one per program variant, for the page: never freed
 * (a freed material frees its program, and the next stop's first draw would link it again on the
 * frame). A new renderer compiles its own programs for them.
 */
const depthMaterials = new Map<string, MeshBasicMaterial>();
/**
 * Depth materials of the cut-out casters, by the card material they stand in for, then by program
 * variant. Never freed either: each goes with its card material, and every one of them shares the
 * one program of its variant (only its picture differs), which so stays compiled.
 */
const cutMaterials = new WeakMap<Material, Map<string, MeshBasicMaterial>>();
/**
 * Every cut-out depth material made, weakly, so releaseDepthMaterials can reach them: a card material
 * can outlive its canvas (an old React closure may still hold its set for a while), and with it the
 * depth materials filed under it, each holding a dispose listener of every renderer that drew it.
 */
const cutAll = new Set<WeakRef<MeshBasicMaterial>>();

/**
 * Lets the depth materials go of a canvas that is going (scene.tsx): each renderer that compiled one
 * hangs a dispose listener on it that holds the renderer's whole state, and the solid ones live for
 * the page (the cut-out ones for as long as their card material). They stay usable: the next canvas
 * compiles its own programs for them.
 */
export function releaseDepthMaterials(): void {
  for (const m of depthMaterials.values()) m.dispose();
  for (const ref of cutAll) {
    const m = ref.deref();
    if (m) m.dispose();
    else cutAll.delete(ref);
  }
}

/** The depth material for a solid caster of this program variant. */
function solidDepth(variant: string): MeshBasicMaterial {
  let m = depthMaterials.get(variant);
  if (!m) {
    m = new MeshBasicMaterial({ colorWrite: false, side: DoubleSide, fog: false });
    m.name = "sect.live.shadowDepth";
    depthMaterials.set(variant, m);
  }
  return m;
}

/**
 * The depth material a caster's stand-in draws with: the solid one, or for a cut-out caster one that
 * tests its picture's alpha; either for the program the stand-in needs (a plain mesh or an
 * instanced one without instance colours, on the caster's geometry).
 */
export function depthMaterial(caster: Mesh): MeshBasicMaterial {
  const card = liveCutout(caster.material);
  const stand = { isInstancedMesh: (caster as InstancedMesh).isInstancedMesh === true, geometry: caster.geometry };
  return card ? cutDepth(card, programVariant(stand, { map: card.map })) : solidDepth(programVariant(stand, {}));
}

/** The depth material for a cut-out caster of this card material and program variant: its picture's alpha, tested. */
function cutDepth(card: MeshBasicMaterial, variant: string): MeshBasicMaterial {
  let byVariant = cutMaterials.get(card);
  if (!byVariant) {
    byVariant = new Map();
    cutMaterials.set(card, byVariant);
  }
  let m = byVariant.get(variant);
  if (!m) {
    m = new MeshBasicMaterial({ map: card.map, alphaTest: card.alphaTest, colorWrite: false, side: DoubleSide, fog: false });
    m.name = "sect.live.shadowCut";
    byVariant.set(variant, m);
    if (typeof WeakRef !== "undefined") {
      // The ones already collected leave the list now and then.
      if (cutAll.size >= 512) for (const ref of cutAll) if (!ref.deref()) cutAll.delete(ref);
      cutAll.add(new WeakRef(m));
    }
  }
  // The card's picture or test as they are now (neither changes the program while both are set).
  if (m.map !== card.map) m.map = card.map;
  if (m.alphaTest !== card.alphaTest) m.alphaTest = card.alphaTest;
  return m;
}

/**
 * Whether a mesh with this material throws a live shadow. Solid things do. A tree card does too,
 * through its own picture's alpha (liveCutout). Not needle and twig cards, whose alpha comes from
 * a pattern the depth pass does not have (as whole quads they would shade far more than their
 * needles do), nothing see-through or hidden, no water, and no shader materials (falls, shells).
 */
export function castsLiveShadow(material: Material | Material[] | null | undefined): boolean {
  if (!material) return false;
  if (Array.isArray(material)) return material.some((m) => castsLiveShadow(m));
  const m = material as MeshBasicMaterial & { isShaderMaterial?: boolean };
  if (m.isShaderMaterial || m.transparent || !m.visible || m.alphaMap) return false;
  if (isCutoutCard(m.userData) || /water|pond/i.test(m.name)) return false;
  return !(m.alphaTest > 0) || !!m.map;
}

/** A caster that is cut out by its picture's alpha (a tree card): its depth is drawn with that test. */
export function liveCutout(material: Material | Material[] | null | undefined): MeshBasicMaterial | null {
  const m = (Array.isArray(material) ? material[0] : material) as MeshBasicMaterial | null | undefined;
  return m && m.alphaTest > 0 && m.map ? m : null;
}

/**
 * The meshes under the roots that throw a live shadow. `moving` (idle.ts idleMovers) are left out:
 * the maps are drawn once, and a piece that travels would leave its shadow behind.
 */
export function liveCasters(roots: readonly Object3D[], moving?: ReadonlySet<Object3D>): Mesh[] {
  const out: Mesh[] = [];
  for (const r of roots) {
    r.traverse((o) => {
      const m = o as Mesh;
      if (m.isMesh && m.geometry?.getAttribute("position") && castsLiveShadow(m.material) && !moving?.has(m)) out.push(m);
    });
  }
  return out;
}

/**
 * The far things that shade a stop: the backdrop's far peaks (far.c<n>) and the other areas'
 * stand-ins (proxy.<area>.c<n>), which are always loaded. Not the stop's own stand-in or its far
 * tree cards (its real meshes cast), whichever stop `chunk` is; no glow pieces. The loader strips
 * the dots from node names.
 */
export function liveFarCasters(root: Object3D, chunk: string): Mesh[] {
  const out: Mesh[] = [];
  root.traverse((o) => {
    const m = o as Mesh;
    if (!m.isMesh || !m.geometry?.getAttribute("position") || !castsLiveShadow(m.material)) return;
    const parent = (m.parent?.name ?? "").toLowerCase();
    const name = m.name.toLowerCase();
    const far = /^backdrop\.?far$/.test(parent) && /^far\.?c\d+$/.test(name);
    const standIn = /^proxy\.?([a-z]+)$/.exec(parent);
    // The far forests' cards: trees.far, and trees.proxy.<area> for the other areas.
    const trees = /^trees\.?(far|proxy\.?([a-z]+))$/.exec(parent);
    if (
      far ||
      (standIn && standIn[1] !== chunk.toLowerCase() && /c\d+$/.test(name) && name.startsWith(parent)) ||
      (trees && trees[2] !== chunk.toLowerCase())
    ) {
      out.push(m);
    }
  });
  return out;
}

/** What the casters are, to tell when they have changed: each one's mesh, geometry and instance count. */
export function liveCasterSignature(casters: readonly Mesh[]): string {
  return casters.map((m) => `${m.id}:${m.geometry.id}:${(m as InstancedMesh).isInstancedMesh ? (m as InstancedMesh).count : 1}`).join(",");
}

export class LiveShadowMap {
  readonly target: WebGLRenderTarget;
  /**
   * The map the shaders read (materials.ts SECT_LIVE.tSectLiveShadow): a compare texture, so each
   * read is the GPU's own filtered 2x2 depth test.
   */
  readonly depth: DepthTexture;
  /** A smaller copy with plain depths, for the blocker search (tSectLiveShadowB). */
  readonly coarseTarget: WebGLRenderTarget;
  readonly coarseDepth: DepthTexture;
  private readonly scene = new Scene();
  private readonly camera = new OrthographicCamera(-1, 1, 1, -1, 0, 1);
  private readonly clear = new Color();
  private signature = "";
  /** Stand-ins drawn into the map now. */
  casters = 0;
  /** Renders so far, and the last one's main-thread time (ms). */
  renders = 0;
  lastMs = 0;

  constructor(size: number, coarse = 4) {
    // 24 bits: over the sun map's 3 km of depth a step is a fifth of a millimetre.
    const depth = new DepthTexture(size, size, UnsignedIntType);
    depth.minFilter = LinearFilter;
    depth.magFilter = LinearFilter;
    depth.compareFunction = LessEqualCompare;
    depth.name = "sect.live.shadowDepth";
    this.depth = depth;
    const small = Math.max(1, Math.round(size / Math.max(coarse, 1)));
    const coarseDepth = new DepthTexture(small, small, UnsignedIntType);
    coarseDepth.minFilter = NearestFilter;
    coarseDepth.magFilter = NearestFilter;
    coarseDepth.name = "sect.live.shadowCoarse";
    this.coarseDepth = coarseDepth;
    this.coarseTarget = new WebGLRenderTarget(small, small, {
      depthBuffer: true,
      depthTexture: coarseDepth,
      format: RedFormat,
      type: UnsignedByteType,
      generateMipmaps: false,
    });
    this.coarseTarget.texture.name = "sect.live.shadowCoarse";
    // The colour attachment is never written (colorWrite off); the smallest format three allows.
    this.target = new WebGLRenderTarget(size, size, {
      depthBuffer: true,
      depthTexture: depth,
      format: RedFormat,
      type: UnsignedByteType,
      generateMipmaps: false,
    });
    this.target.texture.name = "sect.live.shadow";
    // The view-projection is set whole (live.ts liveShadowMatrix): no view transform of its own.
    this.camera.matrixAutoUpdate = false;
    this.scene.matrixWorldAutoUpdate = false;
    this.scene.name = "sect.live.shadowCasters";
  }

  get texture(): Texture {
    return this.depth;
  }

  get coarseTexture(): Texture {
    return this.coarseDepth;
  }

  /** The map's side (px). */
  get size(): number {
    return this.target.width;
  }

  /**
   * Stands the casters in the map's scene (replacing any there). Returns true when they differ from
   * the last set (the map then needs drawing again).
   */
  setCasters(casters: readonly Mesh[]): boolean {
    const sig = liveCasterSignature(casters);
    if (sig === this.signature) return false;
    this.signature = sig;
    this.scene.clear();
    for (const src of casters) {
      src.updateWorldMatrix(true, false);
      const inst = src as unknown as InstancedMesh;
      const mat = depthMaterial(src);
      let p: Mesh;
      if (inst.isInstancedMesh) {
        const im = new InstancedMesh(src.geometry, mat, inst.count);
        im.instanceMatrix = inst.instanceMatrix;
        im.count = inst.count;
        p = im;
      } else {
        p = new Mesh(src.geometry, mat);
      }
      p.name = `live.caster.${src.name}`;
      p.matrixAutoUpdate = false;
      p.matrix.copy(src.matrixWorld);
      p.matrixWorld.copy(src.matrixWorld);
      this.scene.add(p);
    }
    this.casters = casters.length;
    return true;
  }

  /** True when these casters are not the ones in the map. */
  stale(casters: readonly Mesh[]): boolean {
    return liveCasterSignature(casters) !== this.signature;
  }

  /**
   * Compiles the programs the casters standing in the map are drawn with, off the frame (three's
   * compileAsync), and resolves when they are ready to draw with: call it after setCasters and
   * before render. Compiled for the map's own target, as render draws them: a render target's
   * programs are not the screen's (linear output, no tone mapping). Programs already made (the depth
   * materials are the page's) are ready at once.
   */
  async compile(renderer: WebGLRenderer): Promise<void> {
    const target = renderer.getRenderTarget();
    let pending: Promise<unknown>;
    try {
      renderer.setRenderTarget(this.target);
      pending = renderer.compileAsync(this.scene, this.camera);
    } finally {
      // compileAsync compiles at once and only then waits for the driver: the target can go back now.
      renderer.setRenderTarget(target);
    }
    await pending;
    // Each depth material has the one program (one per variant): ready now, its first use run here.
    await primePrograms(renderer, materialsOf([this.scene]));
  }

  /** Draws the map with this view-projection (column-major, live.ts liveShadowMatrix). Returns the main-thread time (ms). */
  render(renderer: WebGLRenderer, viewProjection: readonly number[]): number {
    const t0 = performance.now();
    const cam = this.camera;
    cam.matrix.identity();
    cam.matrixWorld.identity();
    cam.matrixWorldInverse.identity();
    cam.projectionMatrix.fromArray(viewProjection as number[]);
    cam.projectionMatrixInverse.copy(cam.projectionMatrix).invert();
    const target = renderer.getRenderTarget();
    const autoClear = renderer.autoClear;
    renderer.getClearColor(this.clear);
    const alpha = renderer.getClearAlpha();
    try {
      renderer.autoClear = true;
      renderer.setClearColor(0xffffff, 1);
      renderer.setRenderTarget(this.target);
      renderer.render(this.scene, cam);
      renderer.setRenderTarget(this.coarseTarget);
      renderer.render(this.scene, cam);
    } finally {
      renderer.setRenderTarget(target);
      renderer.setClearColor(this.clear, alpha);
      renderer.autoClear = autoClear;
    }
    this.lastMs = performance.now() - t0;
    this.renders++;
    return this.lastMs;
  }

  dispose(): void {
    this.scene.clear();
    this.signature = "";
    this.casters = 0;
    this.target.dispose();
    this.depth.dispose();
    this.coarseTarget.dispose();
    this.coarseDepth.dispose();
    // The depth materials are the page's (their programs stay for the next stop): not freed here.
  }
}
