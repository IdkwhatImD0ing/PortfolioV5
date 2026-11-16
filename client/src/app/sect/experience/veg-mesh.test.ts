import { describe, expect, it } from "vitest";
import { BoxGeometry, DoubleSide, Group, type InstancedBufferGeometry, Mesh, MeshBasicMaterial, Vector2, Vector3, Vector4 } from "three";
import { SECT_FOG_ONCE_DEFINE } from "@/lib/sect/glsl";
import { shellInstances, VEG_FLAG, VEG_LOOK, vegBoughUniform, type VegData } from "@/lib/sect/veg";
import { castsLiveShadow, liveCasters } from "./live-shadow";
import { castsShafts } from "./post/shafts";
import { createShellMesh, createTrunkMesh, createVegMaterial, createVegTrunkMaterial, disposeShellMesh, farCardMeshes, TRUNK_TRIANGLES, vegShell, type VegUniforms } from "./veg-mesh";

/** The shared uniforms as veg.tsx makes them (one set for every chunk). */
function uniforms(sun = new Vector3(0, 1, 0)): VegUniforms {
  return {
    uVegSun: { value: sun },
    uVegNear: { value: new Vector2(0, 0) },
    uVegBough: { value: new Vector4(...vegBoughUniform()) },
    uVegViewH: { value: 900 },
  };
}

function card(name: string): Mesh {
  const m = new MeshBasicMaterial();
  m.name = name;
  return new Mesh(new BoxGeometry(), m);
}

const FAMILIES = ["pine.broadleaf.v3", "pine.huangshan.v1", "shrub.green.v1"];

/** Three card plants and a near one. */
function plants(): VegData {
  return {
    count: 4,
    pos: Float32Array.of(0, 50, 0, 20, 52, -10, -15, 48, 30, 5, 50, 5),
    height: Float32Array.of(12, 9, 2, 10),
    radius: Float32Array.of(5, 3, 1.5, 4),
    yaw: Uint8Array.of(0, 64, 128, 0),
    sun: Uint8Array.of(255, 128, 0, 255),
    family: Uint8Array.of(0, 1, 2, 0),
    flags: Uint8Array.of(0, 0, 0, VEG_FLAG.mesh),
  };
}

describe("the cards a chunk's shells stand in for", () => {
  it("are the far tree cards: not the backdrop's area stand-ins, click targets, near trees or the shells", () => {
    const root = new Group();
    const far = card("trees.cards.gate");
    const backdropFar = card("trees.cards.backdrop");
    const proxyNode = new Group();
    proxyNode.userData.proxyOf = "gate";
    const proxy = card("trees.cards.backdrop");
    proxyNode.add(proxy);
    const mergedProxy = card("trees.cards.backdrop");
    mergedProxy.userData.proxyOf = "mirror";
    const listed = card("trees.cards.mirror");
    const tagged = card("trees.cards.mirror");
    tagged.userData.hotspot = "mirror-blossom";
    const others = [card("trees.needle.gate"), card("trees.mesh.gate"), card("baked.gate_A0")];
    const material = createVegMaterial(uniforms(), "sect.veg.gate", false);
    const inst = shellInstances(plants(), FAMILIES);
    const shells = createShellMesh(inst, material);
    const trunks = createTrunkMesh(inst.trunks, createVegTrunkMaterial(uniforms(), "sect.veg.gate.trunks", false));
    root.add(far, backdropFar, proxyNode, mergedProxy, listed, tagged, ...others, shells, trunks);
    expect(farCardMeshes([root], new Map([["mirror-blossom", [listed]]]))).toEqual([far, backdropFar]);
    expect(farCardMeshes([new Group()], new Map())).toEqual([]);
  });
});

describe("a chunk's shell draw", () => {
  it("holds its own copy of the unit shell and the instances, culled by a sphere round every crown", () => {
    const inst = shellInstances(plants(), FAMILIES);
    expect(inst.plants).toBe(3);
    const shared = uniforms(new Vector3(0.3, 0.5, -0.8).normalize());
    const sun = shared.uVegSun;
    const material = createVegMaterial(shared, "sect.veg.gate", true);
    const mesh = createShellMesh(inst, material);
    const g = mesh.geometry as InstancedBufferGeometry;
    expect(g.isInstancedBufferGeometry).toBe(true);
    expect(g.instanceCount).toBe(inst.count);
    expect(g.getAttribute("position").count).toBe(vegShell().positions.length / 3);
    expect(g.getIndex()!.count).toBe(vegShell().triangles * 3);
    expect(g.getAttribute("iCenter").itemSize).toBe(3);
    expect(g.getAttribute("iShape").itemSize).toBe(4);
    expect(g.getAttribute("iParams").itemSize).toBe(4);
    expect(g.getAttribute("iParams").count).toBe(inst.count);
    // Each crown's depth among the others (vegDepth), one float.
    expect(g.getAttribute("iDepth").itemSize).toBe(1);
    expect(g.getAttribute("iDepth").count).toBe(inst.count);
    expect(material.vertexShader).toContain("attribute float iDepth;");
    expect(g.boundingSphere!.radius).toBeCloseTo(inst.bounds!.radius, 6);
    expect(g.boundingSphere!.center.toArray()).toEqual(inst.bounds!.center);
    expect(mesh.frustumCulled).toBe(true);
    expect(mesh.castShadow).toBe(false);
    expect(mesh.name).toBe("sect.veg.gate");
    // Opaque, depth written, fogged by the page's haze, the sun shared by every chunk.
    expect(material.transparent).toBe(false);
    expect(material.depthWrite).toBe(true);
    expect(material.fog).toBe(true);
    expect(material.alphaToCoverage).toBe(true);
    expect(material.uniforms.uVegSun).toBe(sun);
    expect(material.uniforms.fogColor).toBeDefined();
    expect(material.defines).toHaveProperty(SECT_FOG_ONCE_DEFINE);
    expect(material.vertexShader).toContain("attribute vec4 iParams;");
    expect(material.fragmentShader).toContain("#include <fog_fragment>");
    // Another chunk: its own buffers and material, the same program source.
    const other = createShellMesh(inst, createVegMaterial(shared, "sect.veg.mirror", true));
    expect(other.geometry.getAttribute("position")).not.toBe(g.getAttribute("position"));
    expect(other.geometry.getIndex()).not.toBe(g.getIndex());
    expect(other.material).not.toBe(material);
    expect((other.material as typeof material).fragmentShader).toBe(material.fragmentShader);
    // The boughs' strength: one uniform object for every chunk, so a change at run time reaches them all.
    const otherMat = other.material as typeof material;
    expect(material.uniforms.uVegBough).toBe(shared.uVegBough);
    expect(otherMat.uniforms.uVegBough).toBe(shared.uVegBough);
    expect(material.uniforms.uVegBough.value.toArray()).toEqual([VEG_LOOK.boughs.bump, VEG_LOOK.boughs.dark, VEG_LOOK.boughs.near, 0]);
    expect(material.fragmentShader).toContain("uniform vec4 uVegBough;");
    shared.uVegBough.value.set(0.6, 0.7, 0.5, 0);
    expect((otherMat.uniforms.uVegBough.value as Vector4).x).toBe(0.6);
    // The unit shell point for depth by the crown's own height.
    expect(material.vertexShader).toContain("vVegUnit = n0;");
    // Rays pass through (pick lists hold hotspot meshes only).
    const hits: unknown[] = [];
    mesh.raycast({} as never, hits as never);
    expect(hits).toEqual([]);
    const root = new Group();
    root.add(mesh);
    disposeShellMesh(mesh);
    expect(mesh.parent).toBeNull();
  });
});

describe("a chunk's trunk draw", () => {
  it("holds its own unit ribbon and the crown plants' trunks, culled by a box and sphere round every trunk", () => {
    const inst = shellInstances(plants(), FAMILIES);
    // The broadleaf and the huangshan pine: not the shrub, not the near tree.
    expect(inst.trunks.count).toBe(2);
    const shared = uniforms(new Vector3(0.3, 0.5, -0.8).normalize());
    const material = createVegTrunkMaterial(shared, "sect.veg.gate.trunks", true);
    const mesh = createTrunkMesh(inst.trunks, material);
    const g = mesh.geometry as InstancedBufferGeometry;
    expect(g.isInstancedBufferGeometry).toBe(true);
    expect(g.instanceCount).toBe(2);
    // Two triangles a tree that cover the unit ribbon: x across from -1 to 1, y from the foot (0) to the top (1).
    expect(TRUNK_TRIANGLES).toBe(2);
    const pos = g.getAttribute("position");
    const idx = g.getIndex()!;
    expect(pos.count).toBe(4);
    expect(idx.count).toBe(TRUNK_TRIANGLES * 3);
    for (let i = 0; i < pos.count; i++) {
      expect(Math.abs(pos.getX(i))).toBe(1);
      expect([0, 1]).toContain(pos.getY(i));
    }
    let area = 0;
    for (let t = 0; t < TRUNK_TRIANGLES; t++) {
      const [a, b, c] = [0, 1, 2].map((k) => [pos.getX(idx.getX(t * 3 + k)), pos.getY(idx.getX(t * 3 + k))]);
      area += Math.abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2;
    }
    expect(area).toBeCloseTo(2, 9);
    for (const [name, size] of [
      ["iFoot", 3],
      ["iTop", 3],
      ["iTrunk", 4],
    ] as const) {
      expect(g.getAttribute(name).itemSize).toBe(size);
      expect(g.getAttribute(name).count).toBe(inst.trunks.count);
      expect(material.vertexShader).toContain(`attribute vec${size} ${name};`);
    }
    expect([...(g.getAttribute("iFoot").array as Float32Array)]).toEqual([...inst.trunks.foot]);
    expect([...(g.getAttribute("iTop").array as Float32Array)]).toEqual([...inst.trunks.top]);
    expect([...(g.getAttribute("iTrunk").array as Float32Array)]).toEqual([...inst.trunks.params]);
    // Culled as a whole by bounds round every trunk, so frustum culling never drops a trunk that is on screen.
    expect(g.boundingSphere!.radius).toBeCloseTo(inst.trunks.bounds!.radius, 6);
    expect(g.boundingSphere!.center.toArray()).toEqual(inst.trunks.bounds!.center);
    expect(g.boundingBox!.min.toArray()).toEqual(inst.trunks.bounds!.min);
    expect(g.boundingBox!.max.toArray()).toEqual(inst.trunks.bounds!.max);
    for (let n = 0; n < inst.trunks.count; n++) {
      for (const p of [inst.trunks.foot, inst.trunks.top]) {
        const v = new Vector3(p[n * 3], p[n * 3 + 1], p[n * 3 + 2]);
        expect(g.boundingBox!.containsPoint(v)).toBe(true);
        expect(g.boundingSphere!.containsPoint(v)).toBe(true);
      }
    }
    expect(mesh.frustumCulled).toBe(true);
    expect(mesh.name).toBe("sect.veg.gate.trunks");
    expect(mesh.castShadow).toBe(false);
    expect(mesh.receiveShadow).toBe(false);
    expect(mesh.matrixAutoUpdate).toBe(false);
    expect(mesh.userData.sectVeg).toBe(true);
    // As the shells: opaque, depth written, fogged by the page's haze, alpha to coverage as asked, the uniforms
    // shared by every chunk (the sun, the switch distances, the view's height), the same layers and draw order.
    const shells = createShellMesh(inst, createVegMaterial(shared, "sect.veg.gate", true));
    expect(mesh.layers.mask).toBe(shells.layers.mask);
    expect(mesh.renderOrder).toBe(shells.renderOrder);
    expect(material.transparent).toBe(false);
    expect(material.depthWrite).toBe(true);
    expect(material.fog).toBe(true);
    expect(material.toneMapped).toBe(false);
    expect(material.alphaToCoverage).toBe(true);
    expect(createVegTrunkMaterial(shared, "sect.veg.gate.trunks", false).alphaToCoverage).toBe(false);
    // The ribbon turns to face the camera: which side shows never matters.
    expect(material.side).toBe(DoubleSide);
    expect(material.uniforms.uVegSun).toBe(shared.uVegSun);
    expect(material.uniforms.uVegNear).toBe(shared.uVegNear);
    expect(material.uniforms.uVegViewH).toBe(shared.uVegViewH);
    expect(material.uniforms.fogColor).toBeDefined();
    expect(material.uniforms.uSectLook).toBeDefined();
    expect(material.defines).toHaveProperty(SECT_FOG_ONCE_DEFINE);
    expect(material.vertexShader).toContain("uniform float uVegViewH;");
    expect(material.fragmentShader).toContain("#include <fog_fragment>");
    // Another chunk: its own buffers and material, the same program source.
    const other = createTrunkMesh(inst.trunks, createVegTrunkMaterial(shared, "sect.veg.mirror.trunks", true));
    expect(other.geometry.getAttribute("position")).not.toBe(g.getAttribute("position"));
    expect(other.geometry.getIndex()).not.toBe(g.getIndex());
    expect(other.material).not.toBe(material);
    expect((other.material as typeof material).vertexShader).toBe(material.vertexShader);
    expect((other.material as typeof material).fragmentShader).toBe(material.fragmentShader);
    // Never picked, never a pointer ray's occluder, and out of the sun's passes as the shells are: no shade into the
    // air (post/shafts.ts) and no live shadow (live-shadow.ts).
    const hits: unknown[] = [];
    mesh.raycast({} as never, hits as never);
    expect(hits).toEqual([]);
    expect(castsShafts(material)).toBe(false);
    expect(castsShafts(shells.material)).toBe(false);
    expect(castsLiveShadow(material)).toBe(false);
    const root = new Group();
    root.add(shells, mesh);
    expect(liveCasters([root])).toEqual([]);
    disposeShellMesh(mesh);
    expect(mesh.parent).toBeNull();
    expect(shells.parent).toBe(root);
  });

  it("has nothing to draw where a chunk's crowns are all shrubs", () => {
    const shrubs: VegData = { ...plants(), family: Uint8Array.of(2, 2, 2, 2) };
    const inst = shellInstances(shrubs, FAMILIES);
    expect(inst.count).toBe(3);
    expect(inst.trunks.count).toBe(0);
    expect(inst.trunks.bounds).toBeNull();
  });
});
