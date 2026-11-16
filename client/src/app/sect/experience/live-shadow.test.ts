import { readFileSync } from "node:fs";
import path from "node:path";
import {
  BoxGeometry,
  Color,
  DoubleSide,
  Group,
  InstancedMesh,
  LessEqualCompare,
  LinearFilter,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  NearestFilter,
  ShaderMaterial,
  Texture,
  UnsignedIntType,
  WebGLRenderTarget,
  type Material,
  type Object3D,
  type WebGLRenderer,
} from "three";
import { describe, expect, it } from "vitest";
import { LIVE_LOOK } from "@/lib/sect/live";
import { idleMovers, type IdlePlan } from "./idle";
import { castsLiveShadow, liveCasterSignature, liveCasters, liveCutout, liveFarCasters, LiveShadowMap } from "./live-shadow";

function mat(name: string, set: Partial<MeshBasicMaterial> = {}): MeshBasicMaterial {
  const m = new MeshBasicMaterial({ map: new Texture() });
  m.name = name;
  m.userData = { baked: true };
  Object.assign(m, set);
  return m;
}

/** A needle or twig card: its cut-out is a pattern the depth pass does not have. */
function needleCard(kind = "needle"): MeshBasicMaterial {
  const m = mat("trees.needle.gate", { alphaTest: 0.5 });
  m.userData.cardAlpha = kind;
  return m;
}

describe("live shadow casters", () => {
  it("are the solid meshes and the alpha-tested cards with a picture", () => {
    expect(castsLiveShadow(mat("baked.gate_A0"))).toBe(true);
    expect(castsLiveShadow(mat("baked.vc"))).toBe(true);
    expect(castsLiveShadow(mat("baked.gate_A0.glow.rune_cyan"))).toBe(true);
    expect(castsLiveShadow(mat("trees.mesh.gate"))).toBe(true);
    // A tree card casts through its picture's alpha.
    expect(castsLiveShadow(mat("trees.cards.gate", { alphaTest: 0.5 }))).toBe(true);
    // Alpha-tested with no picture to test: nothing.
    expect(castsLiveShadow(mat("trees.cards.gate", { alphaTest: 0.5, map: null }))).toBe(false);
    expect(castsLiveShadow(needleCard("twig"))).toBe(false);
    expect(castsLiveShadow(needleCard("needle"))).toBe(false);
    expect(castsLiveShadow(mat("trees.cards.gate", { alphaTest: 0.5, alphaMap: new Texture() }))).toBe(false);
    expect(castsLiveShadow(mat("baked.gate_A0", { transparent: true }))).toBe(false);
    expect(castsLiveShadow(mat("baked.gate_A0", { visible: false }))).toBe(false);
    expect(castsLiveShadow(mat("water.sheet.gate"))).toBe(false);
    expect(castsLiveShadow(mat("baked.mirror_A0.pond"))).toBe(false);
    expect(castsLiveShadow(new ShaderMaterial())).toBe(false);
    expect(castsLiveShadow([needleCard(), mat("baked.gate_A0")])).toBe(true);
    expect(castsLiveShadow([needleCard(), mat("baked.gate_A0", { transparent: true })])).toBe(false);
    expect(castsLiveShadow(null)).toBe(false);
  });

  it("tells a cut-out caster by its alpha test and its picture", () => {
    const card = mat("trees.cards.gate", { alphaTest: 0.5 });
    expect(liveCutout(card)).toBe(card);
    expect(liveCutout(mat("baked.gate_A0"))).toBeNull();
    expect(liveCutout(mat("trees.cards.gate", { alphaTest: 0.5, map: null }))).toBeNull();
    expect(liveCutout(null)).toBeNull();
    expect(liveCutout(undefined)).toBeNull();
  });

  it("are found under every root of the set, instanced ones and cards included", () => {
    const g = new BoxGeometry(1, 1, 1);
    const a = new Group();
    a.add(new Mesh(g, mat("baked.gate_A0")), new Mesh(g, mat("trees.cards.gate", { alphaTest: 0.5 })), new Mesh(g, needleCard()));
    const b = new Group();
    b.add(new InstancedMesh(g, mat("trees.mesh.gate"), 3));
    const found = liveCasters([a, b]);
    expect(found.map((m) => (m.material as MeshBasicMaterial).name)).toEqual(["baked.gate_A0", "trees.cards.gate", "trees.mesh.gate"]);
  });

  it("leave out the pieces that move: the maps are drawn once, and their shadow would stay behind", () => {
    const g = new BoxGeometry(1, 1, 1);
    const root = new Group();
    const still = new Mesh(g, mat("baked.forge_A0"));
    const turning = new Mesh(g, mat("baked.forge_A0"));
    root.add(still, turning);
    expect(liveCasters([root], idleMovers({ rigid: [], glows: [], sway: 0, reset: () => {}, rested: false }))).toEqual([still, turning]);
    const plan = { rigid: [{ groups: [{ meshes: [{ m: turning }] }] }], glows: [], sway: 0, reset: () => {}, rested: false } as unknown as IdlePlan;
    expect([...idleMovers(plan)]).toEqual([turning]);
    expect(liveCasters([root], idleMovers(plan))).toEqual([still]);
    // No plan (the global set, or a chunk whose plan is not made yet): nothing is left out.
    expect(idleMovers(undefined).size).toBe(0);
    expect(liveCasters([root], idleMovers(undefined))).toEqual([still, turning]);
  });
});

describe("the far casters", () => {
  const geo = new BoxGeometry(1, 1, 1);
  /** A node as the loader leaves it (dots stripped from the name, or not). */
  const node = (name: string, ...children: Object3D[]) => {
    const g = new Group();
    g.name = name;
    if (children.length > 0) g.add(...children);
    return g;
  };
  const piece = (name: string, material: Material = mat("baked.vc")) => {
    const m = new Mesh(geo, material);
    m.name = name;
    return m;
  };
  const card = () => mat("trees.cards.backdrop", { alphaTest: 0.5 });
  // A glow piece's material casts like any solid one (glow is a colour above 1): its name leaves it out.
  const glow = () => {
    const m = mat("baked.vc.glow");
    m.color.multiplyScalar(2);
    return m;
  };

  it("are the far peaks, the other areas' stand-ins and the far forests' cards", () => {
    expect(castsLiveShadow(glow())).toBe(true);
    const world = node(
      "",
      node("backdropfar", piece("farc0"), piece("farc12"), piece("farglow", glow()), piece("farc4", mat("baked.vc", { transparent: true }))),
      node("backdrop.far", piece("far.c1")),
      node("proxymirror", piece("proxymirrorc0"), piece("proxymirrorc1"), piece("proxymirrorglow", glow())),
      node("proxy.forge", piece("proxy.forge.c0"), piece("proxy.forge.glow", glow())),
      // The stop's own stand-in: its real meshes cast instead.
      node("proxygate", piece("proxygatec0"), piece("proxygateglow", glow())),
      node("treesfar", piece("treescardsfar", card())),
      node("treesproxymirror", piece("treescardsproxymirror", card())),
      node("trees.proxy.forge", piece("trees.cards.proxy.forge", card())),
      node("treesproxygate", piece("treescardsproxygate", card())),
      // Needle cards are never casters, wherever they hang.
      node("treesfar", piece("treesneedlefar", needleCard())),
      // The stop's own meshes, and names that only look like far pieces.
      node("gate", piece("gatebakedgateA0", mat("baked.gate_A0")), piece("farc3")),
      node("proxyforge", piece("proxymirrorc2")),
      node("backdrop", piece("farc5")),
    );
    expect(liveFarCasters(world, "gate").map((m) => m.name)).toEqual([
      "farc0",
      "farc12",
      "far.c1",
      "proxymirrorc0",
      "proxymirrorc1",
      "proxy.forge.c0",
      "treescardsfar",
      "treescardsproxymirror",
      "trees.cards.proxy.forge",
    ]);
  });

  it("leave out whichever area is the stop", () => {
    const world = node(
      "",
      node("proxymirror", piece("proxymirrorc0")),
      node("proxygate", piece("proxygatec0")),
      node("treesproxymirror", piece("treescardsproxymirror", card())),
      node("treesproxygate", piece("treescardsproxygate", card())),
    );
    expect(liveFarCasters(world, "mirror").map((m) => m.name)).toEqual(["proxygatec0", "treescardsproxygate"]);
    expect(liveFarCasters(world, "gate").map((m) => m.name)).toEqual(["proxymirrorc0", "treescardsproxymirror"]);
  });
});

describe("LiveShadowMap", () => {
  it("stands the casters in a scene of its own, where they stand, and redraws only when they change", () => {
    const g = new BoxGeometry(1, 1, 1);
    const root = new Group();
    root.position.set(10, 0, 0);
    const m = new Mesh(g, mat("baked.gate_A0"));
    m.position.set(0, 5, 0);
    const inst = new InstancedMesh(g, mat("trees.mesh.gate"), 2);
    inst.setMatrixAt(1, new Matrix4().makeTranslation(3, 0, 0));
    root.add(m, inst);
    const map = new LiveShadowMap(256);
    expect(map.size).toBe(256);
    const casters = liveCasters([root]);
    expect(map.setCasters(casters)).toBe(true);
    expect(map.casters).toBe(2);
    expect(map.stale(casters)).toBe(false);
    expect(map.setCasters(liveCasters([root]))).toBe(false);
    // The caster's own scene is left alone; its stand-in shares its geometry, at its world place.
    expect(m.parent).toBe(root);
    m.updateWorldMatrix(true, false);
    const scene = (map as unknown as { scene: Group }).scene;
    const [stand, standInst] = scene.children as [Mesh, InstancedMesh];
    expect(stand.geometry).toBe(g);
    expect(stand.matrixWorld.equals(m.matrixWorld)).toBe(true);
    expect(standInst.instanceMatrix).toBe(inst.instanceMatrix);
    expect(standInst.count).toBe(2);
    expect(stand.material).not.toBe(m.material);
    root.add(new Mesh(g, mat("baked.gate_A1")));
    expect(map.stale(liveCasters([root]))).toBe(true);
    expect(liveCasterSignature(liveCasters([root]))).not.toBe(liveCasterSignature(casters));
    map.dispose();
    expect(map.casters).toBe(0);
  });

  it("keeps depth in a 24 bit compare texture the shaders read, and a coarse plain copy for the blocker search", () => {
    const map = new LiveShadowMap(64);
    expect(map.texture).toBe(map.depth);
    expect(map.depth.type).toBe(UnsignedIntType);
    expect(map.target.depthTexture).toBe(map.depth);
    // Read through the GPU's own compare: each read a filtered 2x2 test.
    expect(map.depth.compareFunction).toBe(LessEqualCompare);
    expect(map.depth.minFilter).toBe(LinearFilter);
    expect(map.depth.magFilter).toBe(LinearFilter);
    expect(map.depth.generateMipmaps).toBe(false);
    // The coarse copy: its own target, plain depths read texel by texel. A quarter the side by default.
    expect(map.coarseTexture).toBe(map.coarseDepth);
    expect(map.coarseTarget.depthTexture).toBe(map.coarseDepth);
    expect(map.coarseTarget).not.toBe(map.target);
    expect(map.coarseDepth).not.toBe(map.depth);
    expect(map.coarseDepth.type).toBe(UnsignedIntType);
    expect(map.coarseDepth.compareFunction ?? null).toBeNull();
    expect(map.coarseDepth.minFilter).toBe(NearestFilter);
    expect(map.coarseDepth.magFilter).toBe(NearestFilter);
    expect([map.target.width, map.target.height]).toEqual([64, 64]);
    expect([map.coarseTarget.width, map.coarseTarget.height]).toEqual([16, 16]);
    for (const t of [map.target, map.coarseTarget]) {
      expect(t.depthBuffer).toBe(true);
      expect(t.texture.generateMipmaps).toBe(false);
    }
    map.dispose();
  });

  it("sizes the coarse map by its factor, never under a texel", () => {
    const side = (size: number, coarse?: number) => {
      const m = new LiveShadowMap(size, coarse);
      const out = [m.size, m.coarseTarget.width, m.coarseTarget.height];
      m.dispose();
      return out;
    };
    expect(side(4096, 4)).toEqual([4096, 1024, 1024]);
    expect(side(4096, 8)).toEqual([4096, 512, 512]);
    expect(side(100, 3)).toEqual([100, 33, 33]);
    expect(side(64, 1)).toEqual([64, 64, 64]);
    expect(side(64, 0)).toEqual([64, 64, 64]);
    expect(side(2, 16)).toEqual([2, 1, 1]);
  });

  it("draws both maps with the same view, then puts the renderer back as it was", () => {
    const g = new BoxGeometry(1, 1, 1);
    const root = new Group();
    root.add(new Mesh(g, mat("baked.gate_A0")));
    const map = new LiveShadowMap(64, 4);
    map.setCasters(liveCasters([root]));
    const before = new WebGLRenderTarget(8, 8);
    const log: string[] = [];
    let target: WebGLRenderTarget | null = before;
    const fake = {
      autoClear: false,
      clear: new Color(0x123456),
      alpha: 0.25,
      getRenderTarget: () => target,
      setRenderTarget: (t: WebGLRenderTarget | null) => {
        target = t;
        log.push(t === map.target ? "fine" : t === map.coarseTarget ? "coarse" : t === before ? "before" : "other");
      },
      getClearColor(c: Color) {
        return c.copy(this.clear);
      },
      getClearAlpha() {
        return this.alpha;
      },
      setClearColor(c: Color | number, a: number) {
        this.clear = new Color(c);
        this.alpha = a;
      },
      render(scene: Object3D, cam: { projectionMatrix: Matrix4 }) {
        log.push(`draw ${scene.children.length} ${cam.projectionMatrix.elements[0]} ${this.autoClear}`);
      },
    };
    const vp = new Matrix4().makeScale(0.5, 0.5, 0.25).toArray();
    map.render(fake as unknown as WebGLRenderer, vp);
    expect(log).toEqual(["fine", "draw 1 0.5 true", "coarse", "draw 1 0.5 true", "before"]);
    expect(fake.autoClear).toBe(false);
    expect(fake.clear.getHex()).toBe(0x123456);
    expect(fake.alpha).toBe(0.25);
    expect(map.renders).toBe(1);
    // A render that throws still gives the renderer back.
    fake.render = () => {
      throw new Error("lost context");
    };
    expect(() => map.render(fake as unknown as WebGLRenderer, vp)).toThrow("lost context");
    expect(target).toBe(before);
    expect(fake.autoClear).toBe(false);
    expect(fake.clear.getHex()).toBe(0x123456);
    map.dispose();
  });

  it("frees both targets and both depth textures", () => {
    const map = new LiveShadowMap(64, 4);
    const freed: string[] = [];
    map.target.addEventListener("dispose", () => freed.push("target"));
    map.depth.addEventListener("dispose", () => freed.push("depth"));
    map.coarseTarget.addEventListener("dispose", () => freed.push("coarse target"));
    map.coarseDepth.addEventListener("dispose", () => freed.push("coarse depth"));
    map.dispose();
    expect(freed.sort()).toEqual(["coarse depth", "coarse target", "depth", "target"]);
  });

  it("draws a card's depth through its picture's alpha, and every solid caster with one shared material per program", () => {
    const g = new BoxGeometry(1, 1, 1);
    const cardMat = mat("trees.cards.gate", { alphaTest: 0.42 });
    const otherCard = mat("trees.cards.backdrop", { alphaTest: 0.4 });
    const root = new Group();
    root.add(
      new Mesh(g, mat("baked.gate_A0")),
      new Mesh(g, mat("baked.vc")),
      new Mesh(g, cardMat),
      new InstancedMesh(g, cardMat, 2),
      new Mesh(g, otherCard),
      new InstancedMesh(g, mat("trees.mesh.gate"), 2),
      new Mesh(new BoxGeometry(1, 1, 1).deleteAttribute("normal"), mat("baked.gate_A1")),
    );
    const map = new LiveShadowMap(64);
    map.setCasters(liveCasters([root]));
    const scene = (map as unknown as { scene: Group }).scene;
    const [a, b, ca, cb, cc, inst, bare] = (scene.children as Mesh[]).map((m) => m.material as MeshBasicMaterial);
    // Solid: one shared depth-only material with no picture, for every caster three gives one program.
    expect(a).toBe(b);
    expect(a.map).toBeNull();
    expect(a.alphaTest).toBe(0);
    expect(a.colorWrite).toBe(false);
    // An instanced caster, or one without normals, needs a program of its own: a material of its own.
    expect(inst).not.toBe(a);
    expect(bare).not.toBe(a);
    for (const m of [inst, bare]) expect([m.map, m.alphaTest, m.colorWrite, m.side, m.name]).toEqual([null, 0, false, DoubleSide, a.name]);
    // A card: a depth material of its own with the card's picture and alpha test, shared by every
    // caster drawn with that card material that needs the same program; an instanced one has another.
    expect(ca).not.toBe(a);
    expect(ca).not.toBe(cardMat);
    expect(ca.map).toBe(cardMat.map);
    expect(ca.alphaTest).toBe(cardMat.alphaTest);
    expect(ca.colorWrite).toBe(false);
    expect(ca.side).toBe(DoubleSide);
    expect(cb).not.toBe(ca);
    expect([cb.map, cb.alphaTest]).toEqual([cardMat.map, cardMat.alphaTest]);
    expect(cc).not.toBe(ca);
    expect(cc.map).toBe(otherCard.map);
    expect(cc.alphaTest).toBe(otherCard.alphaTest);
    // Stood in again with other casters, a card keeps its depth material.
    root.add(new Mesh(g, mat("baked.gate_A1")));
    expect(map.setCasters(liveCasters([root]))).toBe(true);
    expect((scene.children[2] as Mesh).material).toBe(ca);
    // The page's, not the map's: another map draws with the same ones, and freeing a map frees none
    // of them (their programs stay compiled for the next stop), nor the cards' pictures or materials.
    const next = new LiveShadowMap(64);
    next.setCasters(liveCasters([root]));
    expect((next as unknown as { scene: Group }).scene.children.map((m) => (m as Mesh).material)).toEqual(scene.children.map((m) => (m as Mesh).material));
    const freed: string[] = [];
    for (const m of [a, inst, bare, ca, cb, cc]) m.addEventListener("dispose", () => freed.push(m.name));
    cardMat.addEventListener("dispose", () => freed.push("card material"));
    cardMat.map!.addEventListener("dispose", () => freed.push("card picture"));
    map.dispose();
    next.dispose();
    expect(freed).toEqual([]);
  });

  it("keeps a card's depth material on the card's picture and test as they are now", () => {
    const g = new BoxGeometry(1, 1, 1);
    const card = mat("trees.cards.gate", { alphaTest: 0.42 });
    const root = new Group();
    root.add(new Mesh(g, card));
    const map = new LiveShadowMap(64);
    map.setCasters(liveCasters([root]));
    const depth = ((map as unknown as { scene: Group }).scene.children[0] as Mesh).material as MeshBasicMaterial;
    card.map = new Texture();
    card.alphaTest = 0.3;
    const again = new LiveShadowMap(64);
    again.setCasters(liveCasters([root]));
    expect(((again as unknown as { scene: Group }).scene.children[0] as Mesh).material).toBe(depth);
    expect([depth.map, depth.alphaTest]).toEqual([card.map, 0.3]);
    map.dispose();
    again.dispose();
  });

  it("compiles its casters' programs off the frame for its own target, then runs their first use", async () => {
    const g = new BoxGeometry(1, 1, 1);
    const root = new Group();
    root.add(new Mesh(g, mat("baked.gate_A0")), new InstancedMesh(g, mat("trees.mesh.gate"), 2));
    const map = new LiveShadowMap(64, 4);
    map.setCasters(liveCasters([root]));
    const before = new WebGLRenderTarget(8, 8);
    let target: WebGLRenderTarget | null = before;
    const log: string[] = [];
    let release = () => {};
    const used: string[] = [];
    const program = (name: string) => ({ program: {}, isReady: () => true, getUniforms: () => used.push(name) });
    const fake = {
      getRenderTarget: () => target,
      setRenderTarget: (t: WebGLRenderTarget | null) => {
        target = t;
      },
      compileAsync: (scene: Group) => {
        // Compiled while the map's own target is bound.
        log.push(`compile ${scene.children.length} ${target === map.target ? "map" : "other"}`);
        return new Promise<void>((r) => (release = () => r()));
      },
      properties: { get: (m: Material) => ({ programs: new Map([[m.uuid, program(m.uuid)]]) }) },
    };
    const done = map.compile(fake as unknown as WebGLRenderer);
    // The target goes back at once; nothing is used before the driver says ready.
    expect(log).toEqual(["compile 2 map"]);
    expect(target).toBe(before);
    expect(used).toEqual([]);
    release();
    await done;
    // Both depth materials' programs had their first use run.
    expect(used).toHaveLength(2);
    map.dispose();
  });
});

describe("live.tsx hands the shaders both of a lamp's maps together", () => {
  const src = readFileSync(path.resolve(__dirname, "live.tsx"), "utf8").replace(/\r\n/g, "\n");
  /** Each `SECT_LIVE.<name>.value = <what>;` in the file, in order. */
  const sets = (name: string) => [...src.matchAll(new RegExp(`SECT_LIVE\\.${name}\\.value = ([^;]+);`, "g"))].map((m) => m[1]);
  const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  it("sets and clears each map with its coarse copy and its switch, in every place", () => {
    for (const [lamp, map] of [
      ["", "shadow"],
      ["Sun", "sunShadow"],
    ] as const) {
      const main = sets(`tSectLive${lamp}Shadow`);
      const coarse = sets(`tSectLive${lamp}ShadowB`);
      const on = sets(`uSectLive${lamp}ShadowOn`);
      // Set once (the start), cleared where live light stops and where a start is undone.
      expect(main, lamp).toEqual(["null", "null", `${map}.texture`]);
      expect(coarse, lamp).toEqual(["null", "null", `${map}.coarseTexture`]);
      expect(on, lamp).toEqual(["0", "0", "1"]);
      // Side by side: the coarse one on the line after the main one.
      for (const [v, b] of [
        ["null", "null"],
        [`${map}.texture`, `${map}.coarseTexture`],
      ]) {
        const pair = new RegExp(`SECT_LIVE\\.tSectLive${lamp}Shadow\\.value = ${esc(v)};\\n\\s*SECT_LIVE\\.tSectLive${lamp}ShadowB\\.value = ${esc(b)};`, "g");
        expect(src.match(pair), `${lamp} ${v}`).toHaveLength(main.filter((x) => x === v).length);
      }
    }
  });

  it("builds both maps with the coarse factor the shader was compiled with", () => {
    const made = [...src.matchAll(/new LiveShadowMap\(([^)]*)\)/g)].map((m) => m[1].split(",").map((x) => x.trim()));
    expect(made).toHaveLength(2);
    for (const args of made) expect(args[1]).toBe("look.shadow.coarse");
    // The look live.tsx starts from is LIVE_LOOK, which liveParsGlsl reads.
    expect(src).toContain("structuredClone(LIVE_LOOK)");
    expect(Number.isInteger(LIVE_LOOK.shadow.coarse)).toBe(true);
  });
});
