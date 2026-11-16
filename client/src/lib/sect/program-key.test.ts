import {
  BoxGeometry,
  BufferAttribute,
  BufferGeometry,
  Color,
  Fog,
  InstancedBufferAttribute,
  InstancedMesh,
  Mesh,
  MeshBasicMaterial,
  Scene,
  Texture,
  type Material,
  type Object3D,
} from "three";
// three's own program key, to hold programVariant and keepProgramFields to it.
import { WebGLPrograms } from "three/src/renderers/webgl/WebGLPrograms.js";
import { describe, expect, it } from "vitest";
import { CLONE_DROPS, keepProgramFields, programVariant } from "./program-key";

/** three's WebGLPrograms with a stand-in renderer: what getProgramCacheKey makes of a material on a mesh. */
function programKeys() {
  const renderer = {
    getRenderTarget: () => null,
    state: { buffers: { depth: { getReversed: () => false } } },
    toneMapping: 0,
    outputColorSpace: "srgb",
    shadowMap: { enabled: false, type: 1 },
  };
  const programs = new (WebGLPrograms as unknown as new (...a: unknown[]) => {
    getParameters: (...a: unknown[]) => unknown;
    getProgramCacheKey: (p: unknown) => string;
  })(
    renderer,
    { get: () => null },
    { has: () => false },
    { logarithmicDepthBuffer: false, precision: "highp", getMaxPrecision: (p: string) => p },
    {},
    { numPlanes: 0, numIntersection: 0 },
  );
  const lights = {
    sun: [], directional: [], point: [], spot: [], spotLightMap: [], rectArea: [], hemi: [],
    sunShadowMap: [], directionalShadowMap: [], pointShadowMap: [], spotShadowMap: [],
    numSpotLightShadowsWithMaps: 0, numLightProbes: 0,
  };
  const scene = new Scene();
  scene.fog = new Fog(0xffffff, 1, 100);
  return (material: Material, object: Object3D) => programs.getProgramCacheKey(programs.getParameters(material, lights, [], scene, object, []));
}

/** A geometry with these attributes (three floats each, or `n` wide). */
function geometry(attrs: Record<string, number>): BufferGeometry {
  const g = new BufferGeometry();
  for (const [name, n] of Object.entries(attrs)) g.setAttribute(name, new BufferAttribute(new Float32Array(3 * n), n));
  return g;
}

/** A baked atlas material as GLTFLoader leaves it for a mesh without normals: unlit, its copy set flat. */
function bakedFlat(): MeshBasicMaterial {
  const m = new MeshBasicMaterial({ map: new Texture(), name: "baked.gate_A0" }).clone();
  (m as MeshBasicMaterial & { flatShading?: boolean }).flatShading = true;
  return m;
}

describe("programVariant", () => {
  const key = programKeys();
  const mat = new MeshBasicMaterial({ map: new Texture() });
  const vc = new MeshBasicMaterial({ map: new Texture(), vertexColors: true });
  const baked = geometry({ position: 3, uv: 2 });
  const lit = geometry({ position: 3, normal: 3, uv: 2 });
  const paving = geometry({ position: 3, uv: 2, uv1: 2 });
  const rgba = geometry({ position: 3, color: 4 });
  const rgb = geometry({ position: 3, color: 3 });
  const morphed = new BoxGeometry(1, 1, 1);
  morphed.morphAttributes.position = [new BufferAttribute(new Float32Array(morphed.attributes.position.count * 3), 3)];
  const tinted = new InstancedMesh(baked, mat, 2);
  tinted.instanceColor = new InstancedBufferAttribute(new Float32Array(6), 3);
  const cases: [string, Material, Object3D][] = [
    ["plain", mat, new Mesh(baked, mat)],
    ["plain again", mat, new Mesh(geometry({ position: 3, uv: 2 }), mat)],
    ["extra uv1 (unused by the material)", mat, new Mesh(paving, mat)],
    ["normals", mat, new Mesh(lit, mat)],
    ["instanced", mat, new InstancedMesh(baked, mat, 3)],
    ["instanced, coloured", mat, tinted],
    ["morphs", mat, new Mesh(morphed, mat)],
    ["rgba colour, vertex colours", vc, new Mesh(rgba, vc)],
    ["rgb colour, vertex colours", vc, new Mesh(rgb, vc)],
    ["rgba colour, no vertex colours", mat, new Mesh(rgba, mat)],
  ];

  it("is equal for two meshes exactly when three gives them the same program", () => {
    for (const [na, ma, oa] of cases) {
      for (const [nb, mb, ob] of cases) {
        if (ma !== mb) continue;
        const sameKey = key(ma, oa) === key(mb, ob);
        const sameVariant = programVariant(oa as Mesh, ma) === programVariant(ob as Mesh, mb);
        expect(sameVariant, `${na} / ${nb}`).toBe(sameKey);
      }
    }
  });

  it("tells the meshes apart that need their own program", () => {
    const v = (o: Object3D, m: Material = mat) => programVariant(o as Mesh, m);
    expect(v(cases[0][2])).toBe(v(cases[1][2]));
    expect(v(cases[0][2])).toBe(v(cases[2][2]));
    expect(v(cases[0][2])).not.toBe(v(cases[3][2]));
    expect(v(cases[0][2])).not.toBe(v(cases[4][2]));
    expect(v(cases[4][2])).not.toBe(v(cases[5][2]));
    expect(v(cases[7][2], vc)).not.toBe(v(cases[8][2], vc));
    expect(v(cases[9][2])).toBe(v(new Mesh(geometry({ position: 3, color: 3 }), mat)));
  });
});

describe("keepProgramFields", () => {
  const key = programKeys();

  it("gives a clone of a flat, defined material the program the material itself compiles", () => {
    const src = bakedFlat();
    src.defines = { SECT_KEEP_GREEN: "" };
    const mesh = new Mesh(geometry({ position: 3, uv: 2 }), src);
    // three's clone drops both: its key (and its shader) is another program.
    const bare = src.clone();
    expect((bare as MeshBasicMaterial & { flatShading?: boolean }).flatShading).toBeUndefined();
    expect(bare.defines).toBeUndefined();
    expect(key(bare, new Mesh(mesh.geometry, bare))).not.toBe(key(src, mesh));
    const copy = src.clone();
    keepProgramFields(src, copy);
    expect(key(copy, new Mesh(mesh.geometry, copy))).toBe(key(src, mesh));
    // Defines copied, not shared.
    expect(copy.defines).toEqual(src.defines);
    expect(copy.defines).not.toBe(src.defines);
  });

  it("leaves a copy alone where the material has none of the fields", () => {
    const src = new MeshBasicMaterial({ color: new Color(0.5, 0.5, 0.5) });
    const copy = src.clone();
    keepProgramFields(src, copy);
    for (const f of CLONE_DROPS) expect((copy as unknown as Record<string, unknown>)[f], f).toBe((src as unknown as Record<string, unknown>)[f]);
    expect(key(copy, new Mesh(new BoxGeometry(), copy))).toBe(key(src, new Mesh(new BoxGeometry(), src)));
  });

  it("names only fields Material.copy really drops", () => {
    // Set by hand on a material, each is lost by its clone (else keeping it would be pointless).
    for (const f of CLONE_DROPS) {
      const src = new MeshBasicMaterial() as unknown as Record<string, unknown>;
      src[f] = f === "defines" || f === "extensions" ? { X: "" } : f === "flatShading" ? true : "x";
      const bare = (src as unknown as MeshBasicMaterial).clone() as unknown as Record<string, unknown>;
      expect(bare[f], f).toBeUndefined();
    }
  });
});
