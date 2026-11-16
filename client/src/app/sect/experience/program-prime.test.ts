import { readFileSync } from "node:fs";
import path from "node:path";
import {
  BoxGeometry,
  Group,
  Mesh,
  MeshBasicMaterial,
  PerspectiveCamera,
  Scene,
  ShaderMaterial,
  type InstancedMesh,
  type Material,
  type Object3D,
  type WebGLRenderer,
} from "three";
import { describe, expect, it } from "vitest";
import { gpuDrained, keepPrograms, keepShaderPrograms, keepShaderProgramsBeforeFree, materialsOf, primePrograms, programsOf, programsReady } from "./program-prime";

/** A stand-in for three's WebGLProgram: ready when told, its first use counted. */
function program(readyNow = true) {
  const p = { program: {} as unknown, ready: readyNow, uses: 0, isReady: () => p.ready, getUniforms: () => p.uses++ };
  return p;
}

/** A renderer whose properties hold these programs per material (several for a material with variants). */
function renderer(programs: Map<Material, ReturnType<typeof program>[]>, context?: unknown): WebGLRenderer {
  return {
    properties: { get: (m: Material) => ({ programs: new Map((programs.get(m) ?? []).map((p, i) => [`${m.uuid}:${i}`, p])) }) },
    getContext: () => context,
  } as unknown as WebGLRenderer;
}

/** A WebGL 2 context's fence calls: the fence signals when told; how often it was read is counted. */
function fences() {
  const f = {
    signalled: false,
    reads: 0,
    deleted: 0,
    SYNC_GPU_COMMANDS_COMPLETE: 1,
    SYNC_STATUS: 2,
    SIGNALED: 3,
    fenceSync: () => ({}),
    flush: () => {},
    isContextLost: () => false,
    getSyncParameter: () => {
      f.reads++;
      return f.signalled ? 3 : 4;
    },
    deleteSync: () => f.deleted++,
  };
  return f;
}

const tick = (ms: number) => new Promise((r) => setTimeout(r, ms));

describe("program-prime", () => {
  it("finds every mesh's materials under the roots, hidden ones and material lists too", () => {
    const a = new MeshBasicMaterial();
    const b = new MeshBasicMaterial();
    const c = new MeshBasicMaterial();
    const root = new Group();
    const hidden = new Mesh(new BoxGeometry(), a);
    hidden.visible = false;
    root.add(hidden, new Mesh(new BoxGeometry(), [b, c]), new Mesh(new BoxGeometry(), a));
    expect([...materialsOf([root])]).toEqual([a, b, c]);
  });

  it("waits for every program of every material, not each one's last", async () => {
    const a = new MeshBasicMaterial();
    const plain = program(true);
    const instanced = program(false);
    const gl = renderer(new Map([[a, [plain, instanced]]]));
    expect(programsOf(gl, [a])).toEqual([plain, instanced]);
    let done = false;
    const wait = programsReady(gl, [a], 1).then(() => (done = true));
    await tick(15);
    expect(done).toBe(false);
    instanced.ready = true;
    await wait;
    expect(done).toBe(true);
  });

  it("stops waiting for a program freed while it was linking, without asking about it again", async () => {
    const a = new MeshBasicMaterial();
    const linking = program(false);
    let asked = 0;
    linking.isReady = () => {
      asked++;
      return linking.ready;
    };
    const gl = renderer(new Map([[a, [linking]]]));
    let done = false;
    const wait = programsReady(gl, [a], 1).then(() => (done = true));
    await tick(15);
    expect(done).toBe(false);
    linking.program = undefined;
    const before = asked;
    await wait;
    expect(done).toBe(true);
    expect(asked).toBe(before);
  });

  it("waits for the GPU to work through what was sent, reading the fence without blocking", async () => {
    const ctx = fences();
    let done = false;
    const wait = gpuDrained(renderer(new Map(), ctx), 1).then(() => (done = true));
    await tick(15);
    expect(done).toBe(false);
    expect(ctx.reads).toBeGreaterThan(0);
    ctx.signalled = true;
    await wait;
    expect(ctx.deleted).toBe(1);
    // Without WebGL 2 there is nothing to wait for.
    await gpuDrained(renderer(new Map()));
  });

  it("runs the first use of the ready programs once the GPU is drained, each once only", async () => {
    const a = new MeshBasicMaterial();
    const b = new MeshBasicMaterial();
    const shared = program(true);
    const linking = program(false);
    const freed = program(true);
    const ctx = fences();
    const gl = renderer(new Map([[a, [shared, linking]], [b, [shared, freed]]]), ctx);
    const run = primePrograms(gl, [a, b]);
    await tick(10);
    expect(shared.uses).toBe(0);
    freed.program = undefined;
    ctx.signalled = true;
    expect(await run).toBe(1);
    expect([shared.uses, linking.uses, freed.uses]).toEqual([1, 0, 0]);
    // Already run: nothing to wait for, nothing run again.
    const reads = ctx.reads;
    expect(await primePrograms(gl, [a, b])).toBe(0);
    expect(shared.uses).toBe(1);
    expect(ctx.reads).toBe(reads);
  });

  it("keeps each program for the page once per key, per renderer, and skips freed ones", () => {
    const a = new MeshBasicMaterial();
    const b = new MeshBasicMaterial();
    const withKey = (key: string, ready = true) => Object.assign(program(ready), { cacheKey: key, usedTimes: 1 });
    const p1 = withKey("k1");
    const p2 = withKey("k2", false);
    const gone = withKey("k3");
    gone.program = undefined;
    const gl = renderer(new Map([[a, [p1, p2]], [b, [p1, gone]]]));
    expect(keepPrograms(gl, [a, b])).toBe(2);
    expect([p1.usedTimes, p2.usedTimes, gone.usedTimes]).toEqual([2, 2, 1]);
    // Again (the set loaded again, its materials holding the kept programs): nothing more taken.
    expect(keepPrograms(gl, [a, b])).toBe(0);
    expect(p1.usedTimes).toBe(2);
    expect(keepPrograms(gl, [b, a])).toBe(0);
    // A new renderer keeps its own.
    const q = withKey("k1");
    expect(keepPrograms(renderer(new Map([[a, [q]]])), [a])).toBe(1);
    expect(q.usedTimes).toBe(2);
  });

  it("keeps a chunk's programs as soon as its warm-up compiles them, before waiting for the driver (scene.tsx)", () => {
    // A set dropped while its programs still link would otherwise free them: deleting a program the
    // driver is still linking makes the GPU process wait for the link (a frozen page for 0.65-0.8 s).
    const src = readFileSync(path.resolve(__dirname, "scene.tsx"), "utf8");
    const warm = src.slice(src.indexOf("const warm = async (s: LoadedSet)"), src.indexOf("warming.current.add(s);"));
    const compile = warm.indexOf("gl.compileAsync(root, camera, scene)");
    const early = warm.indexOf("if (s !== live.current.global) keepPrograms(gl, materialsOf(s.scenes));");
    const wait = warm.indexOf("await Promise.all(pending);");
    expect(compile).toBeGreaterThan(0);
    expect(early).toBeGreaterThan(compile);
    expect(wait).toBeGreaterThan(early);
    // Nothing awaited between the compile and the keep.
    expect(warm.slice(compile, early)).not.toContain("await");
    // And again once ready, for any variant made later.
    expect(warm.indexOf("if (s !== live.current.global) keepPrograms(gl, mats);")).toBeGreaterThan(wait);
  });

  /** A renderer whose compile gives each mesh's material the program its key names (made once per key, counted). */
  function compilingRenderer(keyOf: (m: ShaderMaterial, mesh: Mesh) => string) {
    const store = new Map<object, Record<string, unknown>>();
    const props = (o: object) => {
      let p = store.get(o);
      if (!p) store.set(o, (p = {}));
      return p;
    };
    const progs = new Map<string, ReturnType<typeof program> & { cacheKey: string; usedTimes: number }>();
    const compile = (root: Object3D) =>
      root.traverse((x) => {
        const mesh = x as Mesh;
        if (!mesh.isMesh) return;
        const m = mesh.material as ShaderMaterial;
        const k = keyOf(m, mesh);
        let p = progs.get(k);
        if (!p) progs.set(k, (p = Object.assign(program(), { cacheKey: k, usedTimes: 0 })));
        p.usedTimes++;
        const pr = props(m);
        pr.currentProgram = p;
        pr.programs = new Map([[k, p]]);
      });
    return { gl: { properties: { get: props }, compile } as unknown as WebGLRenderer, progs, compile };
  }

  it("keeps a shader material's program through a copy it compiles once, holding the code's ids too", () => {
    const { gl, progs, compile } = compilingRenderer((m, mesh) => `${m.vertexShader}|${m.fragmentShader}|${(mesh as InstancedMesh).isInstancedMesh ? 1 : 0}`);
    const mat = new ShaderMaterial({ vertexShader: "v", fragmentShader: "f" });
    const root = new Group();
    root.add(new Mesh(new BoxGeometry(), mat));
    compile(root);
    const cam = new PerspectiveCamera();
    const scene = new Scene();
    expect(keepShaderPrograms(gl, [root], cam, scene)).toBe(1);
    // The material and its kept copy hold it.
    expect(progs.get("v|f|0")?.usedTimes).toBe(2);
    expect(keepShaderPrograms(gl, [root], cam, scene)).toBe(0);
    // keepPrograms leaves materials with their own code to this.
    expect(keepPrograms(gl, [mat])).toBe(0);
    expect(progs.get("v|f|0")?.usedTimes).toBe(2);
  });

  it("keeps them for the composer's buffer when the piece goes, and puts the target back; nothing once the context is lost", () => {
    const seen: (string | null)[] = [];
    let target: unknown = null;
    const { gl, progs, compile } = compilingRenderer((m) => `${m.vertexShader}|${m.fragmentShader}|${target ? "rt" : "screen"}`);
    let lost = false;
    Object.assign(gl, {
      getContext: () => ({ isContextLost: () => lost }),
      getRenderTarget: () => target,
      setRenderTarget: (t: unknown) => {
        target = t;
        seen.push(t ? "rt" : null);
      },
    });
    const mat = new ShaderMaterial({ vertexShader: "v", fragmentShader: "f" });
    const root = new Group();
    root.add(new Mesh(new BoxGeometry(), mat));
    target = {};
    compile(root);
    target = null;
    lost = true;
    expect(keepShaderProgramsBeforeFree(gl, [root], new PerspectiveCamera(), new Scene(), true)).toBe(0);
    lost = false;
    expect(keepShaderProgramsBeforeFree(gl, [root], new PerspectiveCamera(), new Scene(), true)).toBe(1);
    expect(seen).toEqual(["rt", null]);
    expect(progs.get("v|f|rt")?.usedTimes).toBe(2);
  });

  it("frees a copy whose program is not the material's", () => {
    const { gl, progs, compile } = compilingRenderer((m) => m.uuid);
    const mat = new ShaderMaterial({ vertexShader: "v", fragmentShader: "f" });
    const root = new Group();
    root.add(new Mesh(new BoxGeometry(), mat));
    compile(root);
    let freed = 0;
    const clone = mat.clone.bind(mat);
    mat.clone = () => {
      const c = clone();
      c.addEventListener("dispose", () => freed++);
      return c;
    };
    expect(keepShaderPrograms(gl, [root], new PerspectiveCamera(), new Scene())).toBe(0);
    expect(freed).toBe(1);
    expect(progs.get(mat.uuid)?.usedTimes).toBe(1);
  });
});
