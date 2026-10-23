import { describe, expect, it, vi } from "vitest";
import { BoxGeometry, BufferAttribute, type BufferGeometry, Group, Mesh, MeshBasicMaterial, type Object3D, SphereGeometry, Texture } from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { boundsSliced, disposeObjects, imageClosed, mergeSliced, prepareScene, prepareSceneSliced, type PrepareOptions } from "./prepare";

/** A stand-in-like scene: rows of small static meshes sharing two materials (they merge per cell). */
function scene(): Object3D {
  const root = new Group();
  const a = new MeshBasicMaterial({ name: "baked.a" });
  const b = new MeshBasicMaterial({ name: "baked.b" });
  for (let i = 0; i < 24; i++) {
    const m = new Mesh(new BoxGeometry(1, 1, 1, 4, 4, 4), i % 3 === 0 ? b : a);
    m.position.set(i * 3, 0, (i % 4) * 3);
    root.add(m);
  }
  return root;
}

function options(): PrepareOptions {
  return { exposure: 1, shadows: false, waterfallMaterial: new MeshBasicMaterial(), envTexture: null, hotspots: new Map() };
}

function vertexCounts(root: Object3D): number[] {
  const out: number[] = [];
  root.traverse((o) => {
    const m = o as Mesh;
    if (m.isMesh) out.push(m.geometry.getAttribute("position").count);
  });
  return out.sort((x, y) => x - y);
}

describe("prepareSceneSliced", () => {
  it("does what prepareScene does, letting the browser in between slices", async () => {
    const whole = scene();
    const one = prepareScene(whole, options());
    const sliced = scene();
    let t = 0;
    let pauses = 0;
    // A clock that runs a millisecond per reading: every slice ends after a step or two.
    const r = await prepareSceneSliced(sliced, options(), {
      budgetMs: 2,
      now: () => (t += 1),
      pause: async () => {
        pauses++;
      },
    });
    expect(pauses).toBeGreaterThan(20);
    expect(r.mergedFrom).toBe(one.mergedFrom);
    expect(r.mergedInto).toBe(one.mergedInto);
    expect(r.mergedInto).toBeGreaterThan(0);
    expect(vertexCounts(sliced)).toEqual(vertexCounts(whole));
  });

  it("stops between slices once its load is cancelled", async () => {
    const ac = new AbortController();
    let t = 0;
    const p = prepareSceneSliced(scene(), options(), {
      signal: ac.signal,
      budgetMs: 1,
      now: () => (t += 1),
      pause: async () => ac.abort(new Error("cancelled")),
    });
    await expect(p).rejects.toThrow("cancelled");
  });
});

describe("hotspot material copies", () => {
  it("make the arena's Heavy Iron Sword black iron with ember seams, and leave other steel and molten as exported", () => {
    const root = new Group();
    const metal = new MeshBasicMaterial({ name: "baked.arena_A0.surface.metal", map: new Texture() });
    metal.userData = { baked: true, sectSurface: "metal" };
    const molten = new MeshBasicMaterial({ name: "baked.arena_A0.glow.molten", map: new Texture() });
    molten.userData = { baked: true, glow: 2, glowTint: "#ff9a50" };
    const node = (hotspot: string) => {
      const g = new Group();
      g.userData = { hotspot };
      g.add(new Mesh(new BoxGeometry(1, 1, 1), metal), new Mesh(new BoxGeometry(1, 1, 1), molten));
      root.add(g);
      return g;
    };
    const sword = node("arena");
    const saber = node("gate-swords");
    prepareScene(root, options());
    const mats = (g: Group) => g.children.map((m) => (m as Mesh).material as MeshBasicMaterial);
    const [iron, seams] = mats(sword);
    const [steel, glow] = mats(saber);
    expect(iron.userData.sectSurface).toBe("iron");
    expect(steel.userData.sectSurface).toBe("metal");
    // The shared material the copies came from keeps the exporter's tag.
    expect(metal.userData.sectSurface).toBe("metal");
    // Deep red, still a glow (above 1); the saber's keeps the class's orange.
    expect(seams.color.r).toBeGreaterThan(1.001);
    expect(seams.color.g / seams.color.r).toBeLessThan(0.15);
    expect(glow.color.g / glow.color.r).toBeGreaterThan(0.4);
  });
});

describe("the bake's spirit motes", () => {
  it("are dropped (the still white specks over the jade slip), and the rest of the chunk stays", () => {
    const root = new Group();
    root.userData = { chunk: 1 };
    const mote = new MeshBasicMaterial({ name: "baked.scroll_A0.glow.mote", map: new Texture() });
    mote.userData = { baked: true, glow: 1.6 };
    const lantern = new MeshBasicMaterial({ name: "baked.scroll_A0.glow.lantern", map: new Texture() });
    lantern.userData = { baked: true, glow: 1.8 };
    const specks = new Mesh(new BoxGeometry(1, 1, 1), mote);
    specks.name = "scrollbakedA0glowmote";
    const lamp = new Mesh(new BoxGeometry(1, 1, 1), lantern);
    root.add(specks, lamp);
    prepareScene(root, options());
    const names: string[] = [];
    root.traverse((o) => {
      if ((o as Mesh).isMesh) names.push(((o as Mesh).material as MeshBasicMaterial).name);
    });
    expect(names).toEqual(["baked.scroll_A0.glow.lantern"]);
    expect(specks.parent).toBeNull();
  });
});

/** Drains a sliced step to its result, counting the stops on the way. */
function drain<T>(g: Generator<void, T, void>): { value: T; stops: number } {
  let stops = 0;
  for (;;) {
    const r = g.next();
    if (r.done) return { value: r.value, stops };
    stops++;
  }
}

/** Float32 copies like toFloat32's: an indexed sphere, moved. */
function part(x: number, segs = 64): BufferGeometry {
  const g = new SphereGeometry(2, segs, segs / 2);
  g.translate(x, 0, 0);
  return g;
}

describe("sliced merge and bounds", () => {
  it("merge as three's mergeGeometries does, index type included, stopping on the way", () => {
    const geoms = [part(0), part(10), part(20, 256)];
    const want = mergeGeometries(geoms, false)!;
    const { value: got, stops } = drain(mergeSliced(geoms));
    expect(stops).toBeGreaterThan(2);
    expect(got).not.toBeNull();
    for (const n of Object.keys(want.attributes)) expect([...(got!.getAttribute(n).array as Float32Array)]).toEqual([...want.getAttribute(n).array]);
    expect(got!.index!.array.constructor).toBe(want.index!.array.constructor);
    expect([...got!.index!.array]).toEqual([...want.index!.array]);
    // A small merge keeps a 16-bit index, as three's does.
    const small = drain(mergeSliced([part(0, 16), part(5, 16)])).value!;
    expect(small.index!.array).toBeInstanceOf(Uint16Array);
    expect(mergeGeometries([part(0, 16), part(5, 16)], false)!.index!.array).toBeInstanceOf(Uint16Array);
  });

  it("hands a layout it does not take to three's merge (non-float attributes)", () => {
    const a = part(0, 16);
    const b = part(4, 16);
    a.setAttribute("color", new BufferAttribute(new Uint8Array(a.getAttribute("position").count * 3), 3, true));
    b.setAttribute("color", new BufferAttribute(new Uint8Array(b.getAttribute("position").count * 3), 3, true));
    const got = drain(mergeSliced([a, b])).value!;
    expect(got.getAttribute("position").count).toBe(a.getAttribute("position").count + b.getAttribute("position").count);
  });

  it("compute the box and sphere three computes", () => {
    const g = drain(mergeSliced([part(0), part(30, 256)])).value!;
    const ref = g.clone();
    ref.computeBoundingBox();
    ref.computeBoundingSphere();
    const { stops } = drain(boundsSliced(g));
    expect(stops).toBeGreaterThan(0);
    expect(g.boundingBox!.equals(ref.boundingBox!)).toBe(true);
    expect(g.boundingSphere!.center.equals(ref.boundingSphere!.center)).toBe(true);
    expect(g.boundingSphere!.radius).toBeCloseTo(ref.boundingSphere!.radius, 10);
  });
});

/** A decoded image as the browser hands it over: close() frees it. */
class FakeBitmap {
  width = 64;
  height = 64;
  closed = 0;
  close(): void {
    this.closed++;
    this.width = 0;
    this.height = 0;
  }
}

describe("imageClosed (a texture three must not upload again)", () => {
  it("is set once the baked map's image is closed after its upload, for its clones too", () => {
    vi.stubGlobal("ImageBitmap", FakeBitmap);
    try {
      const map = new Texture(new FakeBitmap());
      const root = new Group();
      root.add(new Mesh(new BoxGeometry(1, 1, 1), new MeshBasicMaterial({ name: "baked.a", map })));
      prepareScene(root, options());
      // A clone (GLTFLoader makes one per sampler or UV set) shares the decoded image.
      const clone = map.clone();
      expect(imageClosed(map)).toBe(false);
      // three calls onUpdate right after the upload.
      map.onUpdate?.(map);
      expect((map.image as FakeBitmap).closed).toBe(1);
      expect(imageClosed(map)).toBe(true);
      expect(imageClosed(clone)).toBe(true);
      expect(imageClosed(new Texture(new FakeBitmap()))).toBe(false);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("is set by disposeObjects, which closes images never uploaded", () => {
    vi.stubGlobal("ImageBitmap", FakeBitmap);
    try {
      const map = new Texture(new FakeBitmap());
      const root = new Group();
      root.add(new Mesh(new BoxGeometry(1, 1, 1), new MeshBasicMaterial({ map })));
      disposeObjects([root]);
      expect(imageClosed(map)).toBe(true);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
