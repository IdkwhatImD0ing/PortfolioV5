import { BoxGeometry, BufferGeometry, Float32BufferAttribute, Group, type InstancedBufferGeometry, type Material, Mesh, MeshBasicMaterial, type ShaderMaterial, Texture, Vector3 } from "three";
import type { GLTF } from "three/addons/loaders/GLTFLoader.js";
import { describe, expect, it, vi } from "vitest";
import {
  addPondReflection,
  disposeSet,
  drawable,
  FILE_RETRY_MS,
  loadCardAlpha,
  overlayDecor,
  prepareSetScenes,
  retireSet,
  retuneWorld,
  setOverlayTier,
  withRetries,
  type LoadedSet,
  type WorldContext,
} from "./assets";
import { parseMeta } from "@/lib/sect/parse";
import { imageClosed } from "./prepare";

interface TextureDef {
  index: number;
  texCoord?: number;
}

/**
 * A parsed glTF as loadCardAlpha sees it: one mesh per material, glTF material i = mats[i], and a
 * parser that hands back one texture per occlusion definition (as GLTFLoader's assignTexture does).
 */
function fakeGltf(mats: MeshBasicMaterial[], occlusion: (TextureDef | undefined)[]) {
  const scene = new Group();
  for (const m of mats) scene.add(new Mesh(new BufferGeometry(), m));
  const assigned: { def: TextureDef; tex: Texture }[] = [];
  const parser = {
    json: { materials: occlusion.map((o) => (o ? { occlusionTexture: o } : {})) },
    associations: new Map<Material, { materials: number }>(mats.map((m, i) => [m, { materials: i }])),
    assignTexture: async (params: Record<string, Texture | null>, key: string, def: TextureDef) => {
      const tex = new Texture();
      tex.channel = def.texCoord ?? 0;
      params[key] = tex;
      assigned.push({ def, tex });
      return tex;
    },
  };
  return { gltf: { scene, parser } as unknown as GLTF, assigned };
}

function material(extras: Record<string, unknown>): MeshBasicMaterial {
  const m = new MeshBasicMaterial();
  m.userData = extras;
  return m;
}

describe("loadCardAlpha", () => {
  it("loads the cut-out of needle and twig cards alike, on their second UV set", async () => {
    const needle = material({ baked: true, cardAlpha: "needle" });
    const twig = material({ baked: true, cardAlpha: "twig" });
    const { gltf, assigned } = fakeGltf(
      [needle, twig],
      [
        { index: 0, texCoord: 1 },
        { index: 1, texCoord: 1 },
      ],
    );
    await loadCardAlpha(gltf);
    expect(assigned.map((a) => a.def.index)).toEqual([0, 1]);
    for (const m of [needle, twig]) {
      expect(m.aoMap).not.toBeNull();
      expect(m.aoMap?.channel).toBe(1);
      expect(m.alphaMap).toBeNull();
    }
  });

  it("skips sprites, untagged materials, unknown tags and cards that already have their cut-out", async () => {
    const sprite = material({ baked: true });
    const leaf = material({ baked: true, cardAlpha: "leaf" });
    const done = material({ baked: true, cardAlpha: "twig" });
    done.alphaMap = new Texture();
    const { gltf, assigned } = fakeGltf(
      [sprite, leaf, done],
      [
        { index: 0, texCoord: 1 },
        { index: 1, texCoord: 1 },
        { index: 2, texCoord: 1 },
      ],
    );
    await loadCardAlpha(gltf);
    expect(assigned).toHaveLength(0);
    expect(sprite.aoMap).toBeNull();
    expect(leaf.aoMap).toBeNull();
    expect(done.aoMap).toBeNull();
  });

  it("leaves a card without an occlusion texture opaque rather than failing", async () => {
    const twig = material({ baked: true, cardAlpha: "twig" });
    const { gltf, assigned } = fakeGltf([twig], [undefined]);
    await expect(loadCardAlpha(gltf)).resolves.toBeUndefined();
    expect(assigned).toHaveLength(0);
    expect(twig.aoMap).toBeNull();
  });
});

describe("withRetries", () => {
  it("tries a file the page cannot start without twice more, after 1 s and 3 s", async () => {
    vi.useFakeTimers();
    vi.spyOn(console, "warn").mockImplementation(() => {});
    try {
      let tries = 0;
      const got = withRetries(async () => {
        tries++;
        if (tries < 3) throw new Error("HTTP 503");
        return "ok";
      }, FILE_RETRY_MS);
      await vi.advanceTimersByTimeAsync(999);
      expect(tries).toBe(1);
      await vi.advanceTimersByTimeAsync(1);
      expect(tries).toBe(2);
      await vi.advanceTimersByTimeAsync(3000);
      await expect(got).resolves.toBe("ok");
      expect(tries).toBe(3);
      // A third failure is thrown.
      const never = withRetries(async () => Promise.reject(new Error("gone")), FILE_RETRY_MS);
      const caught = expect(never).rejects.toThrow("gone");
      await vi.advanceTimersByTimeAsync(4000);
      await caught;
    } finally {
      vi.useRealTimers();
      vi.restoreAllMocks();
    }
  });

  it("stops at once when the load is cancelled", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    try {
      const ac = new AbortController();
      let tries = 0;
      const p = withRetries(
        async () => {
          tries++;
          throw new Error("offline");
        },
        [60_000],
        ac.signal,
      );
      await Promise.resolve();
      ac.abort();
      await expect(p).rejects.toBeDefined();
      expect(tries).toBe(1);
    } finally {
      vi.restoreAllMocks();
    }
  });
});

describe("the formation's overlay", () => {
  /** A meta with the formation (its area, core and eight stations) and the round 5 bake's beams. */
  function formationMeta() {
    const hotspots = [{ id: "formation", label: "F", center: [65, 238, -1195], size: [29, 18, 29] }];
    for (let k = 0; k < 8; k++) hotspots.push({ id: `arch:${k}`, label: `A${k}`, center: [65 + 29 * Math.cos(k), 228, -1195 + 29 * Math.sin(k)], size: [5, 16, 5] });
    const beam = (name: string) => ({ name, base: [65, 221, -1195], top: [65, 240, -1195], radius: 0.5, color: "#1effc0", nearestM: 40, chunk: "formation" });
    const beams = ["formation.light_pillar.column", "formation.light_pillar.core", "formation.core_feed", "formation.spoke", "formation.spoke.3.core", "formation.sat_link", "formation.cluster_link.1.core", "formation.cross_link"].map(beam);
    beams.push(beam("summit.moonbeam"));
    return parseMeta({
      areas: [{ id: "formation", label: "F", anchor: [65, 220, -1195], footprint: 58, frameStart: 1188, frameEnd: 1343, heroFrame: 1277 }],
      hotspots,
      beams,
    });
  }
  const named = (objs: ReturnType<typeof overlayDecor>, name: string) => objs.find((o) => o.name === name) as Mesh | undefined;

  it("draws the barrier, the soft shafts and only the beams that are not the formation's neon links", () => {
    const objs = overlayDecor(formationMeta(), { value: 0 });
    const dome = named(objs, "sect.dome")!;
    expect(dome.position.toArray()).toEqual([65, 220, -1195]);
    expect(dome.scale.toArray()).toEqual([49.9, 50, 49.9]);
    const shafts = named(objs, "sect.shafts")!;
    // The core, eight wisps and the halo.
    expect((shafts.geometry as InstancedBufferGeometry).instanceCount).toBe(10);
    const beams = named(objs, "sect.beams")!;
    expect((beams.geometry as InstancedBufferGeometry).instanceCount).toBe(1);
  });

  it("draws none of the formation's light without the formation (the proto profile)", () => {
    const objs = overlayDecor(parseMeta({}), { value: 0 });
    expect(objs.map((o) => o.name)).toEqual([]);
  });

  it("moves the barrier and the shafts to a tier: shimmer off Low, the halo on High only, streaks off Low", () => {
    const objs = overlayDecor(formationMeta(), { value: 0 });
    const dome = named(objs, "sect.dome")!.material as ShaderMaterial;
    const shafts = named(objs, "sect.shafts")!;
    const geo = shafts.geometry as InstancedBufferGeometry;
    const mat = shafts.material as ShaderMaterial;
    setOverlayTier(objs, "low");
    expect([dome.uniforms.uDetail.value, geo.instanceCount, mat.uniforms.uStreaks.value]).toEqual([0, 9, 0]);
    setOverlayTier(objs, "mid");
    expect([dome.uniforms.uDetail.value, geo.instanceCount, mat.uniforms.uStreaks.value]).toEqual([1, 9, 1]);
    setOverlayTier(objs, "high");
    expect([dome.uniforms.uDetail.value, geo.instanceCount, mat.uniforms.uStreaks.value]).toEqual([1, 10, 1]);
    // Objects without a tier response, and no objects at all, are fine.
    expect(() => setOverlayTier([new Group()], "low")).not.toThrow();
    expect(() => setOverlayTier(undefined, "low")).not.toThrow();
  });
});

describe("retuneWorld", () => {
  it("moves the wet rock's share of falls and the far rock's octaves to the new tier", () => {
    const setMax = vi.fn();
    const ctx = { wetRock: { setMax }, detail: { uSectRockOctaves: { value: 1 } } } as unknown as WorldContext;
    retuneWorld(ctx, "high");
    expect(setMax).toHaveBeenLastCalledWith(6);
    expect(ctx.detail!.uSectRockOctaves.value).toBe(2);
    retuneWorld(ctx, "mid");
    expect(setMax).toHaveBeenLastCalledWith(4);
    expect(ctx.detail!.uSectRockOctaves.value).toBe(1);
    // No detail texture (a manifest without one): only the wet rock changes.
    expect(() => retuneWorld({ ...ctx, detail: null }, "high")).not.toThrow();
  });
});

/** What prepareSetScenes reads from the world (prepareOpts), with nothing loaded yet. */
function prepCtx(alphaToCoverage: boolean): WorldContext {
  return {
    exposure: 1,
    shadows: false,
    waterfallMaterial: new MeshBasicMaterial({ name: "waterfall" }),
    sheetMaterial: new MeshBasicMaterial({ name: "sheet" }),
    sky: null,
    hotspotMap: new Map(),
    alphaToCoverage,
    sunDir: new Vector3(0, 1, 0),
    detail: null,
  } as unknown as WorldContext;
}

/** Rows of small meshes sharing two textured materials (they merge), and a tree card. */
function prepScene(): { root: Group; map: Texture; card: MeshBasicMaterial } {
  const root = new Group();
  const map = new Texture();
  const a = new MeshBasicMaterial({ name: "baked.a", map });
  const b = new MeshBasicMaterial({ name: "baked.b" });
  for (let i = 0; i < 24; i++) {
    const m = new Mesh(new BoxGeometry(1, 1, 1, 3, 3, 3), i % 3 === 0 ? b : a);
    m.position.set(i * 3, 0, (i % 4) * 3);
    root.add(m);
  }
  const card = new MeshBasicMaterial({ name: "baked.card", map: new Texture(), alphaTest: 0.5, transparent: false });
  root.add(new Mesh(new BoxGeometry(1, 1, 1), card));
  return { root, map, card };
}

/** A clock that runs a millisecond per reading: every slice ends after a step or two. */
function tick(): () => number {
  let t = 0;
  return () => (t += 1);
}

describe("prepareSetScenes", () => {
  it("prepares each file's scene in slices, letting the browser in between", async () => {
    const ctx = prepCtx(false);
    const scenes = [prepScene().root, prepScene().root];
    let pauses = 0;
    const out = await prepareSetScenes(ctx, "forge", scenes, {
      slice: {
        budgetMs: 2,
        now: tick(),
        pause: async () => {
          pauses++;
        },
      },
    });
    expect(out).toHaveLength(2);
    expect(pauses).toBeGreaterThan(20);
    expect(scenes.map((s) => s.name)).toEqual(["sect.forge", "sect.forge"]);
    for (const r of out) expect(r.mergedInto).toBeGreaterThan(0);
  });

  it("cancelled part way, frees every scene (images included) and hands nothing on", async () => {
    const ctx = prepCtx(false);
    const first = prepScene();
    const second = prepScene();
    const freed: string[] = [];
    first.map.addEventListener("dispose", () => freed.push("first map"));
    second.map.addEventListener("dispose", () => freed.push("second map"));
    const shared = vi.fn();
    (ctx.waterfallMaterial as Material).addEventListener("dispose", shared);
    let geoms = 0;
    second.root.traverse((o) => {
      if ((o as Mesh).isMesh) (o as Mesh).geometry.addEventListener("dispose", () => geoms++);
    });
    const ac = new AbortController();
    let pauses = 0;
    const p = prepareSetScenes(ctx, "forge", [first.root, second.root], {
      signal: ac.signal,
      slice: {
        budgetMs: 1,
        now: tick(),
        // Cancelled during the first file's prepare: the second was never started.
        pause: async () => {
          if (++pauses === 3) ac.abort(new Error("dropped"));
        },
      },
    });
    await expect(p).rejects.toThrow("dropped");
    expect(freed.sort()).toEqual(["first map", "second map"]);
    expect(geoms).toBeGreaterThan(0);
    expect(shared).not.toHaveBeenCalled();
  });

  it("frees the scenes when the load was cancelled before the prepare began", async () => {
    const ctx = prepCtx(false);
    const s = prepScene();
    const freed = vi.fn();
    s.map.addEventListener("dispose", freed);
    const ac = new AbortController();
    ac.abort(new Error("gone"));
    await expect(prepareSetScenes(ctx, "forge", [s.root], { signal: ac.signal })).rejects.toThrow("gone");
    expect(freed).toHaveBeenCalled();
  });

  it("re-patches tree cards for an MSAA change that came during the prepare (the quality ladder)", async () => {
    const ctx = prepCtx(true);
    const s = prepScene();
    const out = await prepareSetScenes(ctx, "forge", [s.root], {
      slice: {
        budgetMs: 1,
        now: tick(),
        // MSAA goes off mid-prepare (setCardCoverage sets the context, but this set is not handed on yet).
        pause: async () => {
          ctx.alphaToCoverage = false;
        },
      },
    });
    const cards = out.flatMap((r) => r.cardMaterials);
    expect(cards.length).toBeGreaterThan(0);
    for (const c of cards) expect(c.alphaToCoverage).toBe(false);
  });
});

/** A decoded image as the browser hands it over: close() frees it, and its size reads 0 after. */
class FakeBitmap {
  width = 64;
  height = 64;
  close(): void {
    this.width = 0;
    this.height = 0;
  }
}

/**
 * What three does when it draws: a texture whose GPU copy was freed (dispose()) is uploaded again from
 * its image. From a closed image that makes an empty texture (the area drawn black, and "texSubImage2D:
 * The source data has been detached"). Returns the textures that would come out empty.
 */
function drawFrame(roots: readonly Group[], freed: ReadonlySet<Texture>): Texture[] {
  const dead: Texture[] = [];
  for (const root of roots) {
    root.traverseVisible((o) => {
      const map = ((o as Mesh).material as MeshBasicMaterial | undefined)?.map;
      if (map && freed.has(map) && (map.image as FakeBitmap).width === 0) dead.push(map);
    });
  }
  return dead;
}

/** A set as loadSet hands it on, uploaded and on screen: its images closed after their upload. */
function shownSet(id: string): { set: LoadedSet; map: Texture; freed: Set<Texture> } {
  const { root, map } = prepScene();
  map.image = new FakeBitmap();
  const freed = new Set<Texture>();
  map.addEventListener("dispose", () => freed.add(map));
  const set = {
    id,
    need: id === "global" ? null : ([100, 300] as [number, number]),
    scenes: [root],
    hotspotMeshes: new Map(),
    cardMaterials: [],
    proxies: new Map(),
    pond: null,
    litMaterials: 0,
    waterfallMeshes: 0,
    bytes: 0,
    tris: 0,
    textures: [map],
    ready: true,
    drawn: true,
  } as LoadedSet;
  return { set, map, freed };
}

describe("disposeSet (a set freed while the canvas still holds it)", () => {
  it("takes the set off the screen before freeing it, so no frame draws its closed images", () => {
    vi.stubGlobal("ImageBitmap", FakeBitmap);
    try {
      const ctx = { ...prepCtx(false), wetRock: { untrack: vi.fn() } } as unknown as WorldContext;
      const { set, map, freed } = shownSet("mirror");
      expect(drawable(set)).toBe(true);
      expect(drawFrame(set.scenes as Group[], freed)).toEqual([]);
      // The load effect's cleanup (a tier switch, a hot refresh) frees the world; the canvas's React
      // state still lists the set until the new world arrives, and keeps drawing.
      disposeSet(ctx, set);
      expect(freed.has(map)).toBe(true);
      expect(imageClosed(map)).toBe(true);
      expect(set.scenes.every((r) => !r.visible)).toBe(true);
      expect(drawFrame(set.scenes as Group[], freed)).toEqual([]);
      // The canvas's own rule (scene.tsx World) never shows it again, whatever its range says.
      expect(drawable(set)).toBe(false);
      expect(set.dropped && !set.ready && !set.drawn).toBe(true);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("does it for the global set too, which has no range to leave", () => {
    vi.stubGlobal("ImageBitmap", FakeBitmap);
    try {
      const ctx = { ...prepCtx(false), wetRock: { untrack: vi.fn() } } as unknown as WorldContext;
      const { set, freed } = shownSet("global");
      disposeSet(ctx, set);
      expect(drawable(set)).toBe(false);
      expect(drawFrame(set.scenes as Group[], freed)).toEqual([]);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("frees once: a dropped set freed again by the page's own cleanup is left alone", () => {
    const ctx = { ...prepCtx(false), wetRock: { untrack: vi.fn() } } as unknown as WorldContext;
    const { set, map } = shownSet("forge");
    const disposed = vi.fn();
    map.addEventListener("dispose", disposed);
    // The streamer's drop: off the screen at once, freed after React's commit.
    retireSet(set);
    expect(drawable(set)).toBe(false);
    expect(disposed).not.toHaveBeenCalled();
    disposeSet(ctx, set);
    disposeSet(ctx, set);
    expect(disposed).toHaveBeenCalledTimes(1);
    expect(ctx.wetRock.untrack).toHaveBeenCalledTimes(1);
  });
});

describe("the Still Pond's reflection setup", () => {
  // A soup mesh at world positions (no index).
  const soupMesh = (tris: number[], name: string, color = 1) => {
    const g = new BufferGeometry();
    g.setAttribute("position", new Float32BufferAttribute(tris, 3));
    const m = new MeshBasicMaterial({ map: new Texture() });
    m.name = name;
    m.color.setScalar(color);
    return new Mesh(g, m);
  };
  const quad = (x0: number, z0: number, s: number, y: number) => [x0, y, z0, x0 + s, y, z0 + s, x0 + s, y, z0, x0, y, z0, x0, y, z0 + s, x0 + s, y, z0 + s];
  // A vertical disc of radius r at (cx, cy, cz) facing +z (offset `off` along z), as a fan.
  const disc = (c: [number, number, number], r: number, off = 0) => {
    const out: number[] = [];
    for (let i = 0; i < 32; i++) {
      const a0 = (i / 32) * Math.PI * 2;
      const a1 = ((i + 1) / 32) * Math.PI * 2;
      out.push(c[0], c[1], c[2] + off, c[0] + r * Math.cos(a0), c[1] + r * Math.sin(a0), c[2] + off, c[0] + r * Math.cos(a1), c[1] + r * Math.sin(a1), c[2] + off);
    }
    return out;
  };

  it("bounds the open water by geometry and fits the mirror's face for its capture", () => {
    // Water 10 x 10 at y = 2 from (0, 0), a lily pad 4.5 cm up, a stone top at 2.6; the mirror 20 m north.
    const water = soupMesh([...quad(0, 0, 10, 2), ...quad(4, 4, 0.5, 2.045), ...quad(12, 0, 1, 2.6)], "baked.mirror_A0");
    const face = soupMesh(disc([5, 8, -20], 3, 0.2), "baked.mirror_A0.glow.mirror_face", 1.6);
    const rune = soupMesh(disc([5, 8, -20], 2.9, 0.25), "baked.mirror_A0.glow.rune_cyan", 2);
    const frame = soupMesh([...disc([5, 8, -20], 3.6, -0.3), 5, 3, -21, 6, 3, -19, 5, 12, -20], "baked.mirror_A0.surface.metal");
    const hot = new Map<string, Mesh[]>([
      ["mirror-pond", [water]],
      ["mirror", [face, rune, frame]],
    ]);
    const pond = addPondReflection(hot, new Map(), 1, null, new Set());
    expect(pond).not.toBeNull();
    expect(pond!.level).toBeCloseTo(2, 5);
    expect(pond!.water).toEqual({ min: [0, 0], max: [10, 10] });
    expect((pond!.uniforms[0].uPondMax.value as { x: number }).x).toBe(10);
    const m = pond!.mirror!;
    expect(m).not.toBeNull();
    // Facing the pond (+z), centred on the face, the capture point just in front of it.
    expect(m.normal[2]).toBeCloseTo(1, 5);
    expect(m.radius).toBeCloseTo(3, 1);
    expect(m.capture[2]).toBeGreaterThan(m.center[2] + 0.1);
    // The face and the ring on it are hidden while capturing; the frame stays.
    expect(m.hide).toContain(face);
    expect(m.hide).toContain(rune);
    expect(m.hide).not.toContain(frame);
  });

  it("has no mirror face to capture in an area without one", () => {
    const water = soupMesh(quad(0, 0, 10, 2), "baked.library_A0");
    const pond = addPondReflection(new Map([["mirror-pond", [water]]]), new Map(), 1, null, new Set());
    expect(pond!.mirror).toBeNull();
  });
});
