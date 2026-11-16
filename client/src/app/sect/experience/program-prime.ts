/**
 * Getting a set of materials' shader programs fully ready off the frame, after compileAsync.
 *
 * compileAsync waits only for each material's last program: a material drawn on meshes that need
 * programs of their own (plain and instanced, with and without normals) has several, and the others
 * may still be linking when it resolves. programsReady waits for every one of them.
 *
 * And a program that is ready still costs its first use: three reads its link status and logs and
 * then its uniform and attribute locations (WebGLProgram onFirstUse), synchronous round trips to the
 * GPU process, which answer only once everything queued there before them is done. Left to the
 * frame that first draws with the program, that is behind the frame's own uploads (a set's first
 * frame uploads all its geometry): 10 to 40 ms. primePrograms runs it before anything draws with
 * the program, once the GPU process has worked through what was queued (gpuDrained), so the answer
 * comes at once.
 */
import { HalfFloatType, InstancedMesh, Mesh, WebGLRenderTarget, type Camera, type Material, type Object3D, type Scene, type WebGLRenderer } from "three";
import { keepProgramFields } from "@/lib/sect/program-key";

/** The parts of three's WebGLProgram used here (isReady is missing from its types). */
interface ProgramLike {
  isReady?: () => boolean;
  getUniforms: () => unknown;
  /** The WebGL program; undefined once three has freed it. */
  program?: unknown;
  /** three's key for the program (WebGLPrograms getProgramCacheKey), and how many materials hold it. */
  cacheKey?: string;
  usedTimes?: number;
}

/** Programs whose first use primePrograms has run (three keeps that to itself). */
const primed = new WeakSet<ProgramLike>();

/** The materials of every mesh, line, point cloud or sprite under these roots, hidden ones too (as three's compile walks them). */
export function materialsOf(roots: Iterable<Object3D>): Set<Material> {
  const out = new Set<Material>();
  for (const r of roots) {
    r.traverse((o) => {
      const m = (o as Mesh).material as Material | Material[] | undefined;
      if (!m) return;
      if (Array.isArray(m)) for (const x of m) out.add(x);
      else out.add(m);
    });
  }
  return out;
}

/** Every program three has made for these materials in this renderer (all of a material's variants). */
export function programsOf(gl: WebGLRenderer, materials: Iterable<Material>): ProgramLike[] {
  const out = new Set<ProgramLike>();
  for (const m of materials) {
    const own = (gl.properties.get(m) as { programs?: Map<string, ProgramLike> } | undefined)?.programs;
    if (own) for (const p of own.values()) out.add(p);
  }
  return [...out];
}

/** Whether the driver has finished linking the program (KHR_parallel_shader_compile; without it three says ready at once). */
function ready(p: ProgramLike): boolean {
  return p.isReady ? p.isReady() : true;
}

/**
 * Resolves when every program of these materials is linked, checking every `pollMs` as three's
 * compileAsync does (the check does not wait for the driver), or after `maxMs` whatever is left.
 * A program freed meanwhile (its set dropped) is not waited for: three's isReady would go on asking
 * the driver about the deleted program, which never answers ready and logs a WebGL error each time.
 */
export function programsReady(gl: WebGLRenderer, materials: Iterable<Material>, pollMs = 10, maxMs = 10_000): Promise<void> {
  const left = programsOf(gl, materials);
  const t0 = performance.now();
  return new Promise((resolve) => {
    const check = () => {
      for (let i = left.length - 1; i >= 0; i--) if (left[i].program === undefined || ready(left[i])) left.splice(i, 1);
      if (left.length === 0 || performance.now() - t0 > maxMs) resolve();
      else setTimeout(check, pollMs);
    };
    check();
  });
}

/**
 * Resolves once the GPU has worked through every command sent before the call: a fence, whose
 * status is read without waiting for it (WebGL updates it between tasks), every `pollMs`; or after
 * `maxMs`, or at once without WebGL 2.
 */
export function gpuDrained(gl: WebGLRenderer, pollMs = 4, maxMs = 1000): Promise<void> {
  const ctx = (gl as { getContext?: () => unknown }).getContext?.() as WebGL2RenderingContext | undefined;
  if (!ctx || typeof ctx.fenceSync !== "function") return Promise.resolve();
  const sync = ctx.fenceSync(ctx.SYNC_GPU_COMMANDS_COMPLETE, 0);
  if (!sync) return Promise.resolve();
  ctx.flush();
  const t0 = performance.now();
  return new Promise((resolve) => {
    const check = () => {
      if (ctx.isContextLost() || ctx.getSyncParameter(sync, ctx.SYNC_STATUS) === ctx.SIGNALED || performance.now() - t0 > maxMs) {
        ctx.deleteSync(sync);
        resolve();
      } else {
        setTimeout(check, pollMs);
      }
    };
    setTimeout(check, pollMs);
  });
}

/** Programs kept for the page, per renderer, by three's cache key (keepPrograms). */
const keptPrograms = new WeakMap<WebGLRenderer, Map<string, ProgramLike>>();

/** A material with its own shader code (ShaderMaterial, RawShaderMaterial). */
function ownShader(m: Material): boolean {
  return (m as { isShaderMaterial?: boolean }).isShaderMaterial === true;
}

/**
 * Keeps every program of these materials for the page, and returns how many it took. three frees a
 * program when the last material holding it goes: a stop's set dropped by the stream frees its
 * programs, and coming back links them all again, mid-flight (8 of the 13 links on the way back up).
 * Keeping one reference per program for the renderer (three's usedTimes, which its cache counts down
 * when a material is disposed) leaves it in three's cache; the set's next materials find it there by
 * key and link nothing. One per key at most, so the count stops growing once the flight has been
 * seen; a new renderer keeps its own. Freed programs are skipped, and so are materials with their own
 * shader code: their key holds an id three gives the code and forgets with its last material, so a
 * later copy gets another key and the kept program would only stay unused (keepShaderPrograms).
 */
export function keepPrograms(gl: WebGLRenderer, materials: Iterable<Material>): number {
  let keep = keptPrograms.get(gl);
  if (!keep) {
    keep = new Map();
    keptPrograms.set(gl, keep);
  }
  const own: Material[] = [];
  for (const m of materials) if (!ownShader(m)) own.push(m);
  let n = 0;
  for (const p of programsOf(gl, own)) {
    if (p.program === undefined || p.cacheKey === undefined || typeof p.usedTimes !== "number" || keep.has(p.cacheKey)) continue;
    p.usedTimes++;
    keep.set(p.cacheKey, p);
    n++;
  }
  return n;
}

/** Copies kept for the page, per renderer, by their program's key (keepShaderPrograms). */
const shaderKeepers = new WeakMap<WebGLRenderer, Map<string, Material>>();

/**
 * Keeps the programs of the materials with their own shader code under these roots (a stop's fire,
 * its forge fire and incense, which go with its set) for the page, and returns how many it took.
 * Call it just before they are freed (keepShaderProgramsBeforeFree): a copy made while the piece is
 * shown would take a material id, and three breaks ties in its draw order by material id, so every
 * material made after it would sort a little differently (a few pixels where two pieces meet).
 * three keys such a program by ids it gives each shader's code, and forgets an id with the last
 * material using that code: coming back, the new materials get new ids, a new key, and link again
 * (5 of the 13 links on the way back up). So each one gets a copy, compiled once on a stand-in mesh
 * of the same kind with `camera` and `scene` as the material's own compile had (call it in that
 * compile's context: the same render target bound), which holds both the code's ids and the program,
 * and is kept, never drawn. A copy whose program is not the material's (so it would hold nothing
 * useful) is freed at once. One per key, per renderer.
 */
export function keepShaderPrograms(gl: WebGLRenderer, roots: Iterable<Object3D>, camera: Camera, scene: Scene): number {
  let keep = shaderKeepers.get(gl);
  if (!keep) {
    keep = new Map();
    shaderKeepers.set(gl, keep);
  }
  const kept = keep;
  let n = 0;
  for (const r of roots) {
    r.traverse((o) => {
      const mesh = o as Mesh;
      if (!mesh.isMesh) return;
      for (const mat of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
        if (!mat || !ownShader(mat)) continue;
        const keys = programsOf(gl, [mat]).filter((p) => p.program !== undefined && p.cacheKey !== undefined).map((p) => p.cacheKey as string);
        if (keys.length === 0 || keys.every((k) => kept.has(k))) continue;
        const copy = mat.clone();
        copy.onBeforeCompile = mat.onBeforeCompile;
        copy.customProgramCacheKey = mat.customProgramCacheKey;
        keepProgramFields(mat, copy);
        const src = mesh as unknown as InstancedMesh;
        let stand: Mesh;
        if (src.isInstancedMesh) {
          const im = new InstancedMesh(mesh.geometry, copy, 1);
          if (src.instanceColor) im.instanceColor = src.instanceColor;
          if (src.morphTexture) im.morphTexture = src.morphTexture;
          stand = im;
        } else {
          stand = new Mesh(mesh.geometry, copy);
        }
        gl.compile(stand, camera, scene);
        const key = (gl.properties.get(copy) as { currentProgram?: ProgramLike } | undefined)?.currentProgram?.cacheKey;
        if (key !== undefined && keys.includes(key) && !kept.has(key)) {
          kept.set(key, copy);
          n++;
        } else {
          copy.dispose();
        }
      }
    });
  }
  return n;
}

/**
 * keepShaderPrograms for a piece about to be freed (its materials not disposed yet), compiled for the
 * buffer it was drawn into: the composer's half-float one with `post`, as its warm-up compiled it
 * (three keys a program by that too). Nothing when the context is gone. Returns how many it took.
 */
export function keepShaderProgramsBeforeFree(gl: WebGLRenderer, roots: Iterable<Object3D>, camera: Camera, scene: Scene, post: boolean): number {
  const ctx = (gl as { getContext?: () => WebGL2RenderingContext | undefined }).getContext?.();
  if (!ctx || ctx.isContextLost()) return 0;
  const target = post ? new WebGLRenderTarget(1, 1, { type: HalfFloatType, depthBuffer: false }) : null;
  const prev = gl.getRenderTarget();
  try {
    gl.setRenderTarget(target);
    return keepShaderPrograms(gl, roots, camera, scene);
  } catch (e) {
    console.warn("[sect] keeping a program failed", e);
    return 0;
  } finally {
    gl.setRenderTarget(prev);
    target?.dispose();
  }
}

/**
 * Runs the first use of every ready program of these materials that has not had it from here (see
 * above), once the GPU is drained; programs still linking are left to their draw. Resolves with how
 * many were run, at once when there are none.
 */
export async function primePrograms(gl: WebGLRenderer, materials: Iterable<Material>): Promise<number> {
  const todo = programsOf(gl, materials).filter((p) => !primed.has(p) && p.program !== undefined && ready(p));
  if (todo.length === 0) return 0;
  await gpuDrained(gl);
  let n = 0;
  for (const p of todo) {
    // Freed meanwhile (its last material disposed): nothing to run.
    if (p.program === undefined) continue;
    p.getUniforms();
    primed.add(p);
    n++;
  }
  return n;
}
