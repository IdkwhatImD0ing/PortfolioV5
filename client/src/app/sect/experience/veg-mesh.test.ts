import { describe, expect, it } from "vitest";
import { BoxGeometry, Group, type InstancedBufferGeometry, Mesh, MeshBasicMaterial, Vector2, Vector3, Vector4 } from "three";
import { SECT_FOG_ONCE_DEFINE } from "@/lib/sect/glsl";
import { shellInstances, VEG_FLAG, VEG_LOOK, vegBoughUniform, type VegData } from "@/lib/sect/veg";
import { createShellMesh, createVegMaterial, disposeShellMesh, farCardMeshes, vegShell, type VegUniforms } from "./veg-mesh";

/** The shared uniforms as veg.tsx makes them (one set for every chunk). */
function uniforms(sun = new Vector3(0, 1, 0)): VegUniforms {
  return { uVegSun: { value: sun }, uVegNear: { value: new Vector2(0, 0) }, uVegBough: { value: new Vector4(...vegBoughUniform()) } };
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
    const shells = createShellMesh(shellInstances(plants(), FAMILIES), material);
    root.add(far, backdropFar, proxyNode, mergedProxy, listed, tagged, ...others, shells);
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
