import { AdditiveBlending, DoubleSide, FrontSide, MeshBasicMaterial, Object3D, RedFormat, RepeatWrapping, RGBAFormat, ShaderChunk, ShaderLib, Texture, Vector2, Vector3, type WebGLRenderer } from "three";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { DETAIL_NOISE, detailProgramKey } from "@/lib/sect/detail";
import { fogConstantsFromMeta, glslFloat } from "@/lib/sect/glsl";
import { heartMirrorGlsl } from "@/lib/sect/heart-mirror";
import { SECT_LOOK } from "@/lib/sect/look";
import { parseMeta } from "@/lib/sect/parse";
import { wetFalls } from "@/lib/sect/waterfall";
import { REFLECT } from "./reflect/plan";
import {
  aimPondMirror,
  createBeamMaterial,
  createCloudSeaMaterial,
  createDetailUniforms,
  createDomeMaterial,
  createGlowMaterial,
  createMoonMaterial,
  createShaftMaterial,
  createSkyMaterial,
  createWaterfallSheetMaterial,
  createWaterUniforms,
  createWetRock,
  getClumpTexture,
  getGroundNoiseTexture,
  getNoiseTexture,
  isNearTreeMaterial,
  isTreeCardMaterial,
  patchCardMaterial,
  patchMaterial,
  prepareBakedMaterial,
  prepareNeedleCard,
  SCREEN_DITHER_GLSL,
  SECT_ENV,
  SECT_MIRROR,
  SECT_WET,
  sectSurfaceOf,
  setCardAlphaMode,
  setSheetStrands,
} from "./materials";

type Compiled = { uniforms: Record<string, unknown>; vertexShader: string; fragmentShader: string };

/** A baked card material as GLTFLoader and loadCardAlpha leave it (the cut-out still in the ao slot). */
function cardMaterial(cardAlpha?: string): MeshBasicMaterial {
  const mat = new MeshBasicMaterial({ map: new Texture() });
  mat.name = cardAlpha ? "trees.needle.test" : "trees.cards.test";
  mat.userData = cardAlpha ? { baked: true, cardAlpha } : { baked: true };
  if (cardAlpha) mat.aoMap = new Texture();
  else mat.alphaTest = 0.5;
  return mat;
}

/** Runs the material's patches on three's own basic-material shader, as the renderer would. */
function compile(mat: MeshBasicMaterial): Compiled {
  const shader: Compiled = { uniforms: {}, vertexShader: ShaderLib.basic.vertexShader, fragmentShader: ShaderLib.basic.fragmentShader };
  mat.onBeforeCompile(shader as unknown as Parameters<MeshBasicMaterial["onBeforeCompile"]>[0], {} as WebGLRenderer);
  return shader;
}

function prepareCard(cardAlpha: string | undefined, alphaToCoverage: boolean): { mat: MeshBasicMaterial; shader: Compiled } {
  const mat = cardMaterial(cardAlpha);
  prepareBakedMaterial(mat);
  const cutout = prepareNeedleCard(mat);
  expect(cutout).toBe(cardAlpha === "needle" || cardAlpha === "twig");
  patchCardMaterial(mat, { alphaToCoverage, sunDir: new Vector3(0, 0.12, -1).normalize(), texSize: new Vector2(512, 512) });
  return { mat, shader: compile(mat) };
}

const includes = (s: string) => [...s.matchAll(/#include <(\w+)>/g)].map((m) => m[1]);

describe("prepareNeedleCard", () => {
  it("moves a needle or twig card's cut-out from the ao slot to the alpha map", () => {
    for (const kind of ["needle", "twig"]) {
      const mat = cardMaterial(kind);
      const tex = mat.aoMap;
      expect(prepareNeedleCard(mat)).toBe(true);
      expect(mat.alphaMap).toBe(tex);
      expect(mat.aoMap).toBeNull();
    }
  });

  it("leaves other materials alone", () => {
    const mat = new MeshBasicMaterial({ aoMap: new Texture() });
    mat.userData = { baked: true, cardAlpha: "leaf" };
    expect(prepareNeedleCard(mat)).toBe(false);
    expect(mat.aoMap).not.toBeNull();
    expect(mat.alphaMap).toBeNull();
  });
});

describe("patchCardMaterial", () => {
  it("cuts a twig card with G, shades it with R after the grade, and sharpens the edge", () => {
    const { shader } = prepareCard("twig", false);
    const fs = shader.fragmentShader;
    expect(fs).not.toContain("#include <alphamap_fragment>");
    expect(fs).not.toContain("#include <alphatest_fragment>");
    expect(fs).toContain("diffuseColor.a *= sectCut.g");
    expect(fs).toContain("2.0 * sectCut.r - 1.0");
    expect(fs).toContain("if ( sectPx < 0.0 ) discard;");
    // Order: the grade, then the twig detail and cut-out, then the test, then the rim.
    const order = ["sectGraded", "sectCut.r", "float sectPx", "if ( sectPx < 0.0 ) discard;", "outgoingLight += uSectRim", "#include <opaque_fragment>"];
    const at = order.map((s) => fs.indexOf(s));
    expect(at.every((i) => i >= 0)).toBe(true);
    expect([...at].sort((a, b) => a - b)).toEqual(at);
    // No sprite boost on top of the cut-out's own.
    expect(fs).not.toContain("vMapUv * uSectTexSize");
    expect(Object.keys(shader.uniforms)).toEqual(expect.arrayContaining(["uSectTexSize", "uSectSun", "uSectRim"]));
    expect(shader.vertexShader).toContain("vSectCardWorld = ");
  });

  it("cuts a needle card with G only (old GLBs keep their meaning)", () => {
    const { shader } = prepareCard("needle", true);
    const fs = shader.fragmentShader;
    expect(fs).toContain("diffuseColor.a *= sectCut.g");
    expect(fs).not.toContain("sectCut.r");
    expect(fs).toContain("clamp( sectPx + 0.5, 0.0, 1.0 )");
    expect(fs).not.toContain("#include <alphatest_fragment>");
  });

  it("keeps sprite cards on their map's alpha and three's alpha test, with the old boost", () => {
    const { shader } = prepareCard(undefined, true);
    const fs = shader.fragmentShader;
    expect(fs).toContain("#include <alphamap_fragment>");
    expect(fs).toContain("#include <alphatest_fragment>");
    expect(fs).toContain("1.0 + sectMip * 0.22");
    expect(fs).not.toContain("sectCut");
    // sectPx is measured before three's test, and used by the rim.
    expect(fs.indexOf("float sectPx")).toBeLessThan(fs.indexOf("#include <alphatest_fragment>"));
    expect(fs).toContain("outgoingLight += uSectRim");
  });

  it("leaves only real three chunks to include, and every anchor it needs was found", () => {
    for (const kind of ["needle", "twig", undefined]) {
      for (const a2c of [false, true]) {
        const { shader } = prepareCard(kind, a2c);
        for (const name of [...includes(shader.fragmentShader), ...includes(shader.vertexShader)]) {
          expect((ShaderChunk as unknown as Record<string, string>)[name], name).toBeTypeOf("string");
        }
        expect(shader.fragmentShader).toContain("uniform vec3 uSectRim;");
        expect(shader.fragmentShader).toContain("varying vec3 vSectCardWorld;");
      }
    }
  });

  it("gives each card kind and alpha mode its own program", () => {
    const keys = new Set<string>();
    for (const kind of ["needle", "twig", undefined]) {
      const { mat } = prepareCard(kind, false);
      keys.add(mat.customProgramCacheKey());
      setCardAlphaMode(mat, true);
      keys.add(mat.customProgramCacheKey());
    }
    expect(keys.size).toBe(6);
    const { mat } = prepareCard("twig", true);
    expect(mat.customProgramCacheKey()).toMatch(/\|card-twig\|a2c$/);
    expect(mat.alphaTest).toBe(0.4);
    setCardAlphaMode(mat, false);
    expect(mat.customProgramCacheKey()).toMatch(/\|card-twig\|at$/);
    expect(mat.alphaTest).toBe(0.42);
  });
});

describe("screen dither (low tier)", () => {
  const fog = fogConstantsFromMeta(parseMeta({}));

  it("dithers the sky and the cloud sea after the colour-space step, from the fog library's helper", () => {
    const sky = createSkyMaterial({ fog, texture: null, zenith: "#8b9ad0", horizon: "#f3cfb2", below: "#c8ada0", fogColor: "#c8ada0", sunColor: "#fff0d0" });
    const sea = createCloudSeaMaterial(fog, "#f0d2b4", "#b49ca0", "#c8ada0");
    for (const fs of [sky.fragmentShader, sea.fragmentShader]) {
      expect(fs).toContain(SCREEN_DITHER_GLSL);
      expect(fs.indexOf("#include <colorspace_fragment>")).toBeLessThan(fs.indexOf(SCREEN_DITHER_GLSL));
      expect(fs).toContain("vec3 sectDitherEncoded(");
    }
    // Only where the output is sRGB-encoded (the low tier draws straight to the screen).
    expect(SCREEN_DITHER_GLSL).toContain("linearToOutputTexel( vec4( 0.5 ) ).r > 0.6");
  });
});

describe("wet rock on baked surfaces", () => {
  const baked = () => {
    const mat = new MeshBasicMaterial({ map: new Texture() });
    mat.name = "baked.abode_A0";
    mat.userData = { baked: true };
    prepareBakedMaterial(mat);
    return mat;
  };

  it("darkens baked surfaces near the falls after the grade, from the shared uniforms", () => {
    const mat = baked();
    const shader = compile(mat);
    const fs = shader.fragmentShader;
    expect(fs).toContain("vec3 sectWetRock( vec3 col, vec3 p )");
    expect(fs.indexOf("sectGraded * diffuse")).toBeLessThan(fs.indexOf("diffuseColor.rgb = sectWetRock( diffuseColor.rgb, vSectWorld )"));
    expect(shader.vertexShader).toContain("vSectWorld = ");
    expect(shader.uniforms.uWetA).toBe(SECT_WET.uWetA);
    expect(shader.uniforms.uWetCount).toBe(SECT_WET.uWetCount);
    expect(mat.customProgramCacheKey()).toMatch(/\|wet$/);
    for (const name of [...includes(fs), ...includes(shader.vertexShader)]) {
      expect((ShaderChunk as unknown as Record<string, string>)[name], name).toBeTypeOf("string");
    }
  });

  it("leaves tree cards dry", () => {
    for (const kind of ["needle", "twig", undefined]) {
      const { shader, mat } = prepareCard(kind, false);
      expect(shader.fragmentShader).not.toContain("sectWetRock");
      expect(mat.customProgramCacheKey()).not.toContain("|wet");
    }
  });

  it("fills the uniforms with the falls nearest the camera, and clears them", () => {
    const meta = parseMeta({
      waterfalls: [
        { name: "a.sheet", kind: "sheet", corners: [[-3, 100, 0], [3, 100, 0], [4, 60, -4], [-4, 60, -4]], foot: [0, 60, -4] },
        { name: "b.sheet", kind: "sheet", corners: [[397, 100, 0], [403, 100, 0], [404, 60, -4], [396, 60, -4]], foot: [400, 60, -4] },
      ],
    });
    const time = { value: 7 };
    const wet = createWetRock(wetFalls(meta.waterfalls), { max: 1, sunDir: new Vector3(0, 0.2, -1), time, sheen: true });
    // Nothing is wet before the falls' set (here the global one) is shown.
    const root = new Object3D();
    root.visible = false;
    wet.track("global", [root]);
    wet.update(new Vector3(0, 80, 20));
    expect(SECT_WET.uWetCount.value).toBe(0);
    root.visible = true;
    wet.update(new Vector3(0, 80, 20));
    expect(SECT_WET.uWetCount.value).toBe(1);
    expect(SECT_WET.uWetA.value[0]).toBeCloseTo(0);
    expect(SECT_WET.uWetTime.value).toBe(7);
    expect(SECT_WET.tWetNoise.value).not.toBeNull();
    wet.update(new Vector3(400, 80, 20));
    expect(SECT_WET.uWetA.value[0]).toBeCloseTo(400);
    // A set hidden or shown again is noticed with the camera standing still.
    root.visible = false;
    wet.update(new Vector3(400, 80, 20));
    expect(SECT_WET.uWetCount.value).toBe(0);
    root.visible = true;
    wet.update(new Vector3(400, 80, 20));
    expect(SECT_WET.uWetCount.value).toBe(1);
    wet.untrack("global", [root]);
    wet.update(new Vector3(400, 80, 20));
    expect(SECT_WET.uWetCount.value).toBe(0);
    wet.track("global", [root]);
    wet.clear();
    expect(SECT_WET.uWetCount.value).toBe(0);
  });

  it("takes a new share of falls in place, with the camera standing still", () => {
    const meta = parseMeta({
      waterfalls: [
        { name: "a.sheet", kind: "sheet", corners: [[-3, 100, 0], [3, 100, 0], [4, 60, -4], [-4, 60, -4]], foot: [0, 60, -4] },
        { name: "b.sheet", kind: "sheet", corners: [[197, 100, 0], [203, 100, 0], [204, 60, -4], [196, 60, -4]], foot: [200, 60, -4] },
      ],
    });
    const wet = createWetRock(wetFalls(meta.waterfalls), { max: 1, sunDir: new Vector3(0, 0.2, -1), time: { value: 0 }, sheen: true });
    const root = new Object3D();
    wet.track("global", [root]);
    const at = new Vector3(40, 80, 20);
    wet.update(at);
    expect(SECT_WET.uWetCount.value).toBe(1);
    wet.setMax(2);
    wet.update(at);
    expect(SECT_WET.uWetCount.value).toBe(2);
    wet.setMax(1);
    wet.update(at);
    expect(SECT_WET.uWetCount.value).toBe(1);
    wet.clear();
  });
});

describe("waterfall sheet material", () => {
  it("reads the fall attribute, rides the water down with gravity, and uses only real chunks", () => {
    const mat = createWaterfallSheetMaterial({ value: 0 }, undefined, { sunDir: new Vector3(0, 0.1, -1) });
    expect(mat.vertexShader).toContain("attribute vec4 aFall;");
    expect(mat.fragmentShader).toContain("float tau = mix( sectFallSeconds( below )");
    expect(mat.fragmentShader).toContain("texture2D( tStrands");
    expect(mat.fragmentShader.indexOf("#include <colorspace_fragment>")).toBeLessThan(mat.fragmentShader.indexOf("#include <fog_fragment>"));
    for (const name of [...includes(mat.fragmentShader), ...includes(mat.vertexShader)]) {
      expect((ShaderChunk as unknown as Record<string, string>)[name], name).toBeTypeOf("string");
    }
    expect((mat.uniforms.uSunDir.value as Vector3).length()).toBeCloseTo(1);
    expect(mat.uniforms.uHasStrands.value).toBe(0);
    const tex = new Texture();
    setSheetStrands(mat, tex);
    expect(mat.uniforms.tStrands.value).toBe(tex);
    expect(mat.uniforms.uHasStrands.value).toBe(1);
    expect(mat.fog && mat.transparent && !mat.depthWrite).toBe(true);
  });
});

describe("detail layers on baked rock and ground", () => {
  const time = { value: 3 };
  const sun = new Vector3(0, 0.12, -1).normalize();
  const uniforms = createDetailUniforms(new Texture(), { time, sunDir: sun, rockOctaves: 2 });
  const detailed = (kind: "rock" | "ground") => {
    const mat = new MeshBasicMaterial({ map: new Texture() });
    mat.name = `baked.arena_A0.${kind}`;
    mat.userData = { baked: true, detail: kind };
    prepareBakedMaterial(mat, uniforms);
    return { mat, shader: compile(mat) };
  };
  const count = (s: string, sub: string) => s.split(sub).length - 1;

  it("starts with the layers on, the photo detail off until its image arrives, the clock and sun shared", () => {
    expect(uniforms.uSectGroundLayers.value).toBe(1);
    expect(uniforms.uSectRockFar.value).toBe(1);
    expect(uniforms.uSectDetailOn.value).toBe(0);
    expect(uniforms.uSectRockOctaves.value).toBe(2);
    expect(uniforms.uSectTime).toBe(time);
    expect(uniforms.uSectSun.value).toBe(sun);
    expect(uniforms.tSectGroundNoise.value).toBe(getGroundNoiseTexture());
    expect(uniforms.tSectClump.value).toBe(getClumpTexture());
  });

  it("binds the page's uniform objects, so a switch set on ctx.detail reaches every material", () => {
    for (const kind of ["rock", "ground"] as const) {
      const { shader } = detailed(kind);
      for (const name of ["uSectGroundLayers", "uSectRockFar", "uSectTime", "uSectSun", "tSectClump", "tSectGroundNoise", "tSectDetail", "uSectDetailOn"] as const) {
        expect(shader.uniforms[name], `${kind} ${name}`).toBe(uniforms[name]);
      }
    }
  });

  it("keeps the texel before the grade, then applies the layers after the grade and before the wet rock", () => {
    for (const kind of ["rock", "ground"] as const) {
      const fs = detailed(kind).shader.fragmentShader;
      const order = ["vec3 sectTexel = diffuseColor.rgb / max( diffuse", "sectGrade( sectTexel )", "sectGroundLayers( diffuseColor.rgb", "sectWetRock( diffuseColor.rgb"];
      const at = order.map((x) => fs.indexOf(x));
      expect(at.every((i) => i >= 0), kind).toBe(true);
      expect([...at].sort((a, b) => a - b)).toEqual(at);
      for (const u of ["sampler2D tSectGroundNoise", "sampler2D tSectClump", "float uSectGroundLayers", "float uSectTime", "vec3 uSectSun"]) {
        expect(count(fs, `uniform ${u};`), `${kind} ${u}`).toBe(1);
      }
      expect(count(fs, "uniform float uSectRockFar;")).toBe(kind === "rock" ? 1 : 0);
      for (const name of includes(fs)) expect((ShaderChunk as unknown as Record<string, string>)[name], name).toBeTypeOf("string");
    }
  });

  it("gives each class, and each version of its layers, its own program", () => {
    const rock = detailed("rock").mat.customProgramCacheKey();
    const ground = detailed("ground").mat.customProgramCacheKey();
    expect(rock).not.toBe(ground);
    expect(rock).toContain(`detail-rock-${detailProgramKey("rock")}`);
    expect(ground).toContain(`detail-ground-${detailProgramKey("ground")}`);
  });

  it("leaves other baked materials without the layers", () => {
    const mat = new MeshBasicMaterial({ map: new Texture() });
    mat.userData = { baked: true };
    prepareBakedMaterial(mat, uniforms);
    const fs = compile(mat).fragmentShader;
    expect(fs).not.toContain("sectGroundLayers");
    expect(fs).not.toContain("tSectGroundNoise");
  });

  it("paving and roof tiles read their second UV set; tiles draw on the low tier too (no detail uniforms)", () => {
    const make = (kind: "paving" | "tiles" | "rock", u: typeof uniforms | null) => {
      const mat = new MeshBasicMaterial({ map: new Texture() });
      mat.userData = { baked: true, detail: kind };
      prepareBakedMaterial(mat, u);
      return compile(mat);
    };
    for (const [kind, u, apply] of [
      ["paving", uniforms, "sectPaving( diffuseColor.rgb"],
      ["tiles", uniforms, "sectTiles( diffuseColor.rgb, sectTexel )"],
      ["tiles", null, "sectTiles( diffuseColor.rgb, sectTexel )"],
    ] as const) {
      const sh = make(kind, u);
      expect(sh.vertexShader, kind).toContain("vSectUv1 = vec2( uv1.x, 1.0 - uv1.y );");
      expect(sh.fragmentShader, kind).toContain(apply);
      expect(sh.fragmentShader.indexOf(apply), kind).toBeGreaterThan(sh.fragmentShader.indexOf("vec3 sectTexel ="));
      for (const name of includes(sh.vertexShader + sh.fragmentShader)) expect((ShaderChunk as unknown as Record<string, string>)[name], name).toBeTypeOf("string");
    }
    expect(make("rock", null).fragmentShader).not.toContain("sectDetail");
  });
});

describe("runtime noise textures", () => {
  it("the ground noise: one shared RGBA texture, repeating and mipmapped", () => {
    const t = getGroundNoiseTexture();
    expect(getGroundNoiseTexture()).toBe(t);
    expect(t.format).toBe(RGBAFormat);
    expect(t.image.width).toBe(DETAIL_NOISE.ground.size);
    expect((t.image.data as Uint8Array).length).toBe(DETAIL_NOISE.ground.size ** 2 * 4);
    expect(t.wrapS).toBe(RepeatWrapping);
    expect(t.wrapT).toBe(RepeatWrapping);
    expect(t.generateMipmaps).toBe(true);
  });

  it("the clump field: one shared channel, repeating, mipmapped, with its mean", () => {
    const t = getClumpTexture();
    expect(getClumpTexture()).toBe(t);
    expect(t.format).toBe(RedFormat);
    expect(t.image.width).toBe(DETAIL_NOISE.clump.size);
    expect(t.wrapS).toBe(RepeatWrapping);
    const data = t.image.data as Uint8Array;
    expect(data.reduce((a, v) => a + v, 0) / data.length / 255).toBeCloseTo(DETAIL_NOISE.clump.mean, 2);
  });

  it("leaves the cloud sea's noise texture as it was (the grass tufts' wind reads it too)", () => {
    const t = getNoiseTexture();
    expect(t.format).toBe(RedFormat);
    expect(t.image.width).toBe(256);
    let h = 0x811c9dc5;
    for (const v of t.image.data as Uint8Array) h = Math.imul(h ^ v, 0x01000193);
    expect((h >>> 0).toString(16)).toBe("1f5a6280");
  });
});

describe("reflective surfaces (sky reflection, Fresnel, sun glint)", () => {
  const baked = (name: string, userData: Record<string, unknown> = {}) => {
    const mat = new MeshBasicMaterial({ map: new Texture() });
    mat.name = name;
    mat.userData = { baked: true, ...userData };
    prepareBakedMaterial(mat);
    return mat;
  };
  const chunksReal = (sh: Compiled) => {
    for (const name of [...includes(sh.fragmentShader), ...includes(sh.vertexShader)]) {
      expect((ShaderChunk as unknown as Record<string, string>)[name], name).toBeTypeOf("string");
    }
  };

  it("classes a material by the exporter's tag, and the Heart-Mirror's face by its name", () => {
    expect(sectSurfaceOf(baked("baked.gate_A0.metal", { sectSurface: "metal" }))).toBe("metal");
    expect(sectSurfaceOf(baked("baked.gate_A0.glaze", { sectSurface: "glaze" }))).toBe("glaze");
    expect(sectSurfaceOf(baked("baked.mirror_A0.glow.mirror_face", { glow: 1.3 }))).toBe("mirror");
    expect(sectSurfaceOf(baked("baked.mirror_A0.glow.rune_cyan", { glow: 2 }))).toBeNull();
    expect(sectSurfaceOf(baked("baked.gate_A0", { sectSurface: "chrome" }))).toBeNull();
    // Given by prepare.ts on a hotspot's copy (look.ts hotspotSurface), never by the exporter.
    expect(sectSurfaceOf(baked("baked.arena_A0.surface.metal", { sectSurface: "iron" }))).toBe("iron");
  });

  it("shades black iron dull and near-black: the bake's light as shape, a faint rough sheen, no steel mirror", () => {
    const mat = baked("baked.arena_A0.surface.metal", { sectSurface: "iron" });
    const sh = compile(mat);
    const fs = sh.fragmentShader;
    const iron = SECT_LOOK.surfaces.iron;
    expect(fs).toContain(`float iL = dot( outgoingLight, vec3( 0.2126, 0.7152, 0.0722 ) ) * ${glslFloat(iron.diffuse)};`);
    expect(fs).toContain(`sectEnvSky( sR, ${glslFloat(iron.rough)} )`);
    // Not the metal class: no reflectance from the texel's hue at f0 0.7.
    expect(fs).not.toContain("sectTexel / max( sLum, 1e-4 )");
    const at = ["sectGrade( sectTexel )", "float iL = ", "#include <opaque_fragment>"].map((x) => fs.indexOf(x));
    expect(at.every((i) => i >= 0)).toBe(true);
    expect([...at].sort((a, b) => a - b)).toEqual(at);
    expect(sh.uniforms.tSectSky).toBe(SECT_ENV.tSectSky);
    expect(mat.customProgramCacheKey()).toContain("|surface-iron");
    expect(fs).not.toMatch(/NaN|undefined/);
    chunksReal(sh);
  });

  it("changes nothing on an untagged material", () => {
    const mat = baked("baked.gate_A0");
    const sh = compile(mat);
    expect(sh.fragmentShader).not.toContain("sectEnvSky");
    expect(sh.uniforms.tSectSky).toBeUndefined();
    expect(mat.customProgramCacheKey()).not.toContain("surface");
  });

  it("reflects the shared sky on a tagged material, after the bake and before the opaque output", () => {
    for (const kind of ["metal", "glaze"] as const) {
      const mat = baked(`baked.gate_A0.${kind}`, { sectSurface: kind });
      const sh = compile(mat);
      const fs = sh.fragmentShader;
      expect(fs).toContain("vec3 sectEnvSky( vec3 d, float blur )");
      // The env functions follow the fog library they call; the surface follows the grade.
      expect(fs.indexOf("vec3 sectEnvSky(")).toBeGreaterThan(fs.indexOf("#include <fog_pars_fragment>"));
      const at = ["sectGrade( sectTexel )", "vec3 sR = reflect( sV, sN );", "#include <opaque_fragment>"].map((x) => fs.indexOf(x));
      expect(at.every((i) => i >= 0)).toBe(true);
      expect([...at].sort((a, b) => a - b)).toEqual(at);
      expect(sh.vertexShader).toContain("vSectWorld = ");
      for (const name of ["tSectSky", "uSectSkyOn", "uSectEnvZenith", "uSectEnvHaze", "uSectEnvSunDir", "uSectEnvSunColor"] as const) {
        expect(sh.uniforms[name], `${kind} ${name}`).toBe(SECT_ENV[name]);
      }
      expect(mat.customProgramCacheKey()).toContain(`|surface-${kind}`);
      chunksReal(sh);
    }
  });

  it("picks up a tag set after loading at the next compile", () => {
    const mat = baked("baked.forge_A0.blade");
    const before = mat.customProgramCacheKey();
    mat.userData.sectSurface = "metal";
    expect(mat.customProgramCacheKey()).not.toBe(before);
    expect(compile(mat).fragmentShader).toContain("sectEnvSun( sR");
  });

  it("shades the Heart-Mirror's face as convex polished bronze around the fitted disc", () => {
    const mat = baked("baked.mirror_A0.glow.mirror_face", { glow: 1.3 });
    const sh = compile(mat);
    expect(sh.fragmentShader).toContain("uniform float uSectMirrorR;");
    expect(sh.uniforms.uSectMirrorC).toBe(SECT_MIRROR.uSectMirrorC);
    expect(sh.fragmentShader).toContain("if ( uSectMirrorR > 0.0 )");
    chunksReal(sh);
    createWaterUniforms({ level: 1, disc: { center: [1, 2, 3], normal: [0, 0, 2], radius: 1.5 } });
    expect(SECT_MIRROR.uSectMirrorC.value.toArray()).toEqual([1, 2, 3]);
    expect(SECT_MIRROR.uSectMirrorN.value.toArray()).toEqual([0, 0, 1]);
    expect(SECT_MIRROR.uSectMirrorR.value).toBe(1.5);
  });

  it("gives the pond the same sky (and a bronze mirror in it)", () => {
    const mat = new MeshBasicMaterial({ map: new Texture() });
    mat.name = "baked.mirror_A0.detail.ground";
    patchMaterial(mat, { lit: true, exposure: 1, water: createWaterUniforms({ level: 0, disc: null }) });
    const sh = compile(mat);
    expect(sh.fragmentShader).toContain("sectEnvSky( r, 0.25 )");
    expect(sh.fragmentShader).toContain("SECT_POND_MIRROR_F0");
    expect(sh.uniforms.tSectSky).toBe(SECT_ENV.tSectSky);
    chunksReal(sh);
  });

  it("reads the planar reflection only where the pond is open water by geometry, the analytic path otherwise", () => {
    const u = createWaterUniforms({ level: 2, disc: null, bounds: { min: [-3, -4], max: [5, 6] } });
    expect((u.uPondMin.value as Vector2).toArray()).toEqual([-3, -4]);
    expect((u.uPondMax.value as Vector2).toArray()).toEqual([5, 6]);
    expect(u.uHasReflect.value).toBe(0);
    expect(u.tReflect.value).toBeNull();
    const mat = new MeshBasicMaterial({ map: new Texture() });
    mat.name = "baked.mirror_A0";
    patchMaterial(mat, { lit: true, exposure: 1, water: u });
    const sh = compile(mat);
    const fs = sh.fragmentShader;
    for (const name of ["tReflect", "uReflectMatrix", "uReflectClamp", "uReflectTexel", "uPondMin", "uPondMax", "uWaterTime"]) {
      expect(sh.uniforms[name], name).toBe(u[name]);
    }
    const planar = fs.indexOf("if ( uHasReflect > 0.5 )");
    const analytic = fs.indexOf("} else {", planar);
    expect(planar).toBeGreaterThan(0);
    const planarCode = fs.slice(planar, analytic);
    // Geometry alone: the water plane to a centimetre, level, inside the bounds; no colour test.
    expect(planarCode).toContain("smoothstep( 0.008, 0.016, abs( vSectWorld.y - uWaterLevel ) )");
    expect(planarCode).toContain("step( uPondMin, vSectWorld.xz )");
    expect(planarCode).not.toContain("dot( outgoingLight");
    expect(planarCode).toContain("textureLod( tReflect");
    // No analytic disc where the real reflection is drawn; the analytic path keeps its dark-water test and disc.
    expect(planarCode).not.toContain("uDiscR");
    const analyticCode = fs.slice(analytic, fs.indexOf("#include <opaque_fragment>"));
    expect(analyticCode).toContain("1.0 - smoothstep( 0.05, 0.14, dot( outgoingLight");
    expect(analyticCode).toContain("uDiscR > 0.0");
    chunksReal(sh);
  });

  it("draws the Heart-Mirror's own layout in the analytic path, laid on the water as the planar path lays a reflection", () => {
    const u = createWaterUniforms({ level: 0, disc: { center: [1, 2, 3], normal: [0, 0, 1], radius: 3.38 } });
    for (const name of ["uDiscRim", "uDiscRimOuter", "uDiscRune", "uDiscBronze", "uDiscGlow"]) expect(u[name], name).toBeDefined();
    // The runes glow (HDR), the lacquer is red.
    expect(Math.max(...(u.uDiscRune.value as Vector3).toArray())).toBeGreaterThan(1);
    const red = (u.uDiscRimOuter.value as Vector3).toArray();
    expect(red[0]).toBeGreaterThan(red[1] * 3);
    const mat = new MeshBasicMaterial({ map: new Texture() });
    mat.name = "baked.mirror_A0";
    patchMaterial(mat, { lit: true, exposure: 1, water: u });
    const sh = compile(mat);
    const fs = sh.fragmentShader;
    for (const name of ["uDiscRune", "uDiscBronze"]) expect(sh.uniforms[name], name).toBe(u[name]);
    // The layout and its shading follow the sky they call, and come before main.
    const env = fs.indexOf("vec3 sectEnvSky( vec3 d, float blur )");
    expect(env).toBeGreaterThan(0);
    expect(fs.indexOf(heartMirrorGlsl().trim().split("\n")[0])).toBeGreaterThan(env);
    expect(fs.indexOf("vec3 sectMirrorShade( int part, vec2 q, vec2 lean, SectMirrorView m ) {")).toBeGreaterThan(env);
    expect(fs.indexOf("vec3 sectMirrorShade( int part, vec2 q, vec2 lean, SectMirrorView m ) {")).toBeLessThan(fs.indexOf("void main()"));
    const planar = fs.indexOf("if ( uHasReflect > 0.5 )");
    const analytic = fs.indexOf("} else {", planar);
    const analyticCode = fs.slice(analytic, fs.indexOf("#include <opaque_fragment>"));
    expect(analyticCode).toContain("sectHeartMirror( q, w, dot( r, m.y ) / abs( dn ), m )");
    // From behind too (the back plate), and no flat disc any more.
    expect(analyticCode).toContain("abs( dn ) > 1e-4");
    expect(analyticCode).not.toContain("hit = face");
    // The planar path's Fresnel and gain, so Low's mirror is as bright in the water as High's.
    const look = REFLECT.pond.look;
    expect(analyticCode).toContain(`float Fm = ${glslFloat(look.f0)} + ${glslFloat(1 - look.f0)} * pow(`);
    expect(analyticCode).toContain(`mc.rgb * ( Fm * ${glslFloat(look.gain)} )`);
    // The face shades as the mirror's own sky-only path does, but leans and darkens toward the rim as
    // gently as High's cube path (more lean showed the ground on its lower half, seen from the water).
    expect(fs).toContain(`* ${glslFloat(REFLECT.mirror.look.convex)} / SECT_HEART_FACE`);
    expect(fs).toContain(`smoothstep( ${glslFloat(REFLECT.mirror.look.patina[0])}, ${glslFloat(REFLECT.mirror.look.patina[1])}, length( q ) / SECT_HEART_FACE )`);
    expect(fs).toContain(`sectEnvSky( fr, ${glslFloat(SECT_LOOK.surfaces.mirror.rough)} )`);
    expect(fs).not.toMatch(/NaN|undefined/);
    chunksReal(sh);
  });

  it("ripples both paths' water alike (the planar path's waves, still on Low)", () => {
    const mat = new MeshBasicMaterial({ map: new Texture() });
    mat.name = "baked.mirror_A0";
    patchMaterial(mat, { lit: true, exposure: 1, water: createWaterUniforms({ level: 0, disc: null }) });
    const fs = compile(mat).fragmentShader;
    expect(fs.split("vec3 sectPondNormal( vec2 wp, float wt, float dist ) {").length).toBe(2);
    expect(fs).toContain(`g *= ${glslFloat(REFLECT.pond.look.slope)} * ( 1.0 - smoothstep(`);
    const planar = fs.indexOf("if ( uHasReflect > 0.5 )");
    const analytic = fs.indexOf("} else {", planar);
    expect(fs.slice(planar, analytic)).toContain("vec3 n = sectPondNormal( vSectWorld.xz, uWaterTime, length( vSectWorld - cameraPosition ) );");
    expect(fs.slice(analytic)).toContain("vec3 r = reflect( v, sectPondNormal( vSectWorld.xz, uWaterTime, dist ) );");
  });

  it("aims the pond's mirror at the face fitted to its triangles, and leaves it without one", () => {
    const u = createWaterUniforms({ level: 0, disc: { center: [1, 2, 3], normal: [0, 0, 1], radius: 3.3 } });
    aimPondMirror([u], null);
    expect((u.uDiscN.value as Vector3).toArray()).toEqual([0, 0, 1]);
    aimPondMirror([u], { center: [4, 5, 6], normal: [0, 0.6, 0.8 * 2], radius: 3.38 });
    expect((u.uDiscC.value as Vector3).toArray()).toEqual([4, 5, 6]);
    const n = (u.uDiscN.value as Vector3).toArray();
    expect(Math.hypot(...n)).toBeCloseTo(1, 9);
    expect(n[1] / n[2]).toBeCloseTo(0.6 / 1.6, 9);
    expect(u.uDiscR.value).toBe(3.38);
    // The mirror's own shading keeps the glow box's disc.
    expect(SECT_MIRROR.uSectMirrorC.value.toArray()).toEqual([1, 2, 3]);
  });

  it("gives the Heart-Mirror's face the captured surroundings, faded in over the sky-only shading", () => {
    const mat = baked("baked.mirror_A0.glow.mirror_face", { glow: 1.3 });
    const sh = compile(mat);
    const fs = sh.fragmentShader;
    for (const name of ["tSectMirrorEnv", "uSectMirrorEnvOn", "uSectMirrorEnvP", "uSectMirrorEnvC", "uSectMirrorEnvN", "uSectMirrorEnvR"] as const) {
      expect(sh.uniforms[name], name).toBe(SECT_MIRROR[name]);
    }
    expect(fs).toContain("uniform samplerCube tSectMirrorEnv;");
    // The sky-only shading comes first and stays whole when the cube is off (Low, or before a capture).
    const sky = fs.indexOf("outgoingLight = sF * ( sectEnvSky( sR");
    const cube = fs.indexOf("if ( uSectMirrorEnvOn > 0.0 )");
    expect(sky).toBeGreaterThan(0);
    expect(cube).toBeGreaterThan(sky);
    expect(fs).toContain("outgoingLight = mix( outgoingLight, eCol, uSectMirrorEnvOn );");
    expect(SECT_MIRROR.uSectMirrorEnvOn.value).toBe(0);
    // Only the face: the rune ring and other glow materials do not read the cube.
    expect(compile(baked("baked.mirror_A0.glow.rune_cyan", { glow: 2 })).fragmentShader).not.toContain("tSectMirrorEnv");
    chunksReal(sh);
  });

  it("hands the sky dome's own uniform objects to the reflections, reset to the look's day colours", () => {
    const fog = fogConstantsFromMeta(parseMeta({}));
    const tex = new Texture();
    const sky = createSkyMaterial({ fog, texture: tex, zenith: "#8b9ad0", horizon: "#f3cfb2", below: "#c8ada0", fogColor: "#c8ada0", sunColor: "#fff0d0" });
    expect(sky.uniforms.tSky).toBe(SECT_ENV.tSectSky);
    expect(sky.uniforms.uLookZenith).toBe(SECT_ENV.uSectEnvZenith);
    expect(sky.uniforms.uFogColor).toBe(SECT_ENV.uSectEnvHaze);
    expect(SECT_ENV.tSectSky.value).toBe(tex);
    expect(SECT_ENV.uSectSkyOn.value).toBe(1);
    // The twilight blends the dome's colours in place; a new dome starts from the day again.
    SECT_ENV.uSectEnvZenith.value.setRGB(0, 0, 0);
    createSkyMaterial({ fog, texture: null, zenith: "#8b9ad0", horizon: "#f3cfb2", below: "#c8ada0", fogColor: "#c8ada0", sunColor: "#fff0d0" });
    expect(SECT_ENV.uSectEnvZenith.value.r).toBeGreaterThan(0.1);
    expect(SECT_ENV.uSectSkyOn.value).toBe(0);
    expect((SECT_ENV.uSectEnvSunDir.value as Vector3).length()).toBeCloseTo(1);
  });
});

describe("near pines", () => {
  it("lifts near pine trunks, pads and twig cards before the grade, and nothing else", () => {
    const pine = new MeshBasicMaterial({ map: new Texture() });
    pine.name = "trees.mesh.abode";
    pine.userData = { baked: true };
    prepareBakedMaterial(pine);
    const fs = compile(pine).fragmentShader;
    expect(fs.indexOf("sectTexel = sectTreeLift( sectTexel );")).toBeGreaterThan(0);
    expect(fs.indexOf("sectTexel = sectTreeLift( sectTexel );")).toBeLessThan(fs.indexOf("sectGrade( sectTexel )"));
    expect(pine.customProgramCacheKey()).toContain("|tree");
    const { shader, mat } = prepareCard("twig", false);
    expect(isNearTreeMaterial(mat)).toBe(true);
    expect(shader.fragmentShader).toContain("sectTreeLift( sectTexel )");
    // Far cards and baked areas keep their bake.
    const { shader: sprite } = prepareCard(undefined, false);
    expect(sprite.fragmentShader).not.toContain("sectTreeLift");
    const area = new MeshBasicMaterial({ map: new Texture() });
    area.name = "baked.abode_A0";
    prepareBakedMaterial(area);
    expect(compile(area).fragmentShader).not.toContain("sectTreeLift(");
  });

  it("turns the shade of every tree deep green after the grade (near pines and far cards alike), and nothing else", () => {
    const call = "sectGraded = sectTreeShade( sectGraded, sectTexel );";
    const pine = new MeshBasicMaterial({ map: new Texture() });
    pine.name = "trees.mesh.abode";
    prepareBakedMaterial(pine);
    const fs = compile(pine).fragmentShader;
    expect(fs).toContain("vec3 sectTreeShade( vec3 c, vec3 t )");
    expect(fs.indexOf(call)).toBeGreaterThan(fs.indexOf("vec3 sectGraded = sectGrade( sectTexel );"));
    expect(pine.customProgramCacheKey()).toContain("|shade");
    for (const kind of ["twig", undefined]) {
      const { shader, mat } = prepareCard(kind, false);
      expect(shader.fragmentShader).toContain(call);
      expect(mat.customProgramCacheKey()).toContain("|shade");
    }
    // The far cards take the shade but not the lift.
    const { shader: sprite, mat: card } = prepareCard(undefined, false);
    expect(isTreeCardMaterial(card)).toBe(true);
    expect(isNearTreeMaterial(card)).toBe(false);
    expect(sprite.fragmentShader).not.toContain("sectTreeLift(");
    const area = new MeshBasicMaterial({ map: new Texture() });
    area.name = "baked.abode_A0";
    prepareBakedMaterial(area);
    expect(compile(area).fragmentShader).not.toContain("sectTreeShade");
    expect(area.customProgramCacheKey()).not.toContain("|shade");
  });
});

describe("moon", () => {
  it("draws the shared moon map once it has arrived, and fetches nothing until its shader compiles", () => {
    const fog = fogConstantsFromMeta(parseMeta({}));
    const a = createMoonMaterial(fog, "#e9edf5", "#c8ada0");
    const b = createMoonMaterial(fog, "#e9edf5", "#c8ada0");
    expect(a.uniforms.tMoon).toBe(b.uniforms.tMoon);
    expect(a.uniforms.uHasMoon.value).toBe(0);
    expect(a.uniforms.tMoon.value).toBeNull();
    expect(a.fragmentShader).toContain("if ( uHasMoon > 0.5 )");
    expect(a.vertexShader).toContain("atan( ax.y, ay.y )");
  });

  it("adds its halo, the beams and the dome as linear light, never sRGB-encoded on their own (the Low tier's white blots)", () => {
    const fog = fogConstantsFromMeta(parseMeta({}));
    const time = { value: 0 };
    const glow = createGlowMaterial("#e9edf5", 0.5);
    expect(glow.fragmentShader).toContain("uColor * a * uStrength");
    // On the Low tier's screen, the step the light makes over the sky (glsl.ts screenAdd).
    expect(glow.fragmentShader).toContain("sectScreenAdd( uColor * a * uStrength, ");
    expect(glow.fragmentShader).toContain("vec3 sectScreenClip( vec3 c )");
    for (const m of [glow, createBeamMaterial(fog, "#c8ada0", time), createDomeMaterial(fog, "#ffd9a0", time), createShaftMaterial(fog, time, { value: 1 })]) {
      expect(m.blending).toBe(AdditiveBlending);
      expect(m.fragmentShader).not.toContain("colorspace_fragment");
    }
  });

  it("draws the formation's barrier as a faint gold rim and shimmer, not a milky bowl", () => {
    const fog = fogConstantsFromMeta(parseMeta({}));
    const motion = { value: 1 };
    const m = createDomeMaterial(fog, "#ffd9a0", { value: 0 }, motion);
    expect(m.side).toBe(DoubleSide);
    expect(m.depthWrite).toBe(false);
    // lib/sect/formation.ts domeAlpha's GLSL twin, with the shimmer stilled by reduced motion.
    expect(m.fragmentShader).toContain("sectDomeAlpha( facing, vH, uTime, az, uDetail, uMotion )");
    expect(m.uniforms.uMotion).toBe(motion);
    expect(m.uniforms.uDetail.value).toBe(1);
    // No constant face term or latitude bands (the old milky bowl).
    expect(m.fragmentShader).not.toContain("0.035 +");
    expect(m.fragmentShader).not.toContain("sin( vH * 46.0");
    // The azimuth is safe at the apex (atan( 0, 0 ) is undefined).
    expect(m.fragmentShader).toContain("abs( vXZ.x ) + abs( vXZ.y ) > 1e-6");
    // The far wall's inner face keeps only a share (formation.ts domeAlpha front: false).
    expect(m.fragmentShader).toContain("gl_FrontFacing ? 1.0 : ");
    // Pale gold, in linear light.
    const c = m.uniforms.uColor.value as { r: number; g: number; b: number };
    expect(c.r).toBeGreaterThan(c.g);
    expect(c.g).toBeGreaterThan(c.b);
  });

  it("draws the formation's shafts as soft strips facing the camera, the wisps on the eyes' wave", () => {
    const fog = fogConstantsFromMeta(parseMeta({}));
    const time = { value: 0 };
    const motion = { value: 1 };
    const m = createShaftMaterial(fog, time, motion);
    expect(m.uniforms.uTime).toBe(time);
    expect(m.uniforms.uMotion).toBe(motion);
    expect(m.uniforms.uStreaks.value).toBe(1);
    expect(m.uniforms.tNoise.value).toBe(getNoiseTexture());
    // No hard core: one Gaussian across (formation.ts shaftProfile), no second, narrower term.
    expect(m.fragmentShader).toContain("exp( - x * x * 2.5 )");
    expect(m.fragmentShader).toContain("exp2( - max( h, 0.0 ) / vShape.z )");
    // Front face toward the camera (side = up x toCam, so side x up points at it): with the
    // default FrontSide, the other way round is culled and the shafts vanish.
    expect(m.side).toBe(FrontSide);
    expect(m.vertexShader).toContain("vec3( toCam.z, 0.0, - toCam.x ) / l");
    const toCam = new Vector3(3, 0, -7).normalize();
    const side = new Vector3(toCam.z, 0, -toCam.x);
    expect(side.clone().cross(new Vector3(0, 1, 0)).dot(toCam)).toBeGreaterThan(0.99);
  });

  it("defines each GLSL helper once in the formation's shaders (a second body fails to compile)", () => {
    const fog = fogConstantsFromMeta(parseMeta({}));
    for (const m of [createDomeMaterial(fog, "#ffd9a0", { value: 0 }), createShaftMaterial(fog, { value: 0 }, { value: 1 })]) {
      for (const fn of ["vec3 sectScreenClip(", "vec3 sectScreenAdd(", "float sectHazeDepth(", "float sectSoftFade("]) {
        expect(m.fragmentShader.split(fn).length - 1, `${m.name} ${fn}`).toBe(1);
      }
    }
  });

  it("adds the forge fire and the life motes as linear light too (fx.tsx, life.tsx)", () => {
    // Their materials are built inside components; the shader sources are read from the files.
    const dir = path.dirname(fileURLToPath(import.meta.url));
    for (const [file, name] of [["fx.tsx", "sect.forgefire"], ["life.tsx", "sect.life.motes"]]) {
      const src = readFileSync(path.join(dir, file), "utf8").replace(/\r\n/g, "\n");
      const start = src.indexOf(`name: "${name}"`);
      expect(start).toBeGreaterThan(0);
      const body = src.slice(start, src.indexOf("\n  });\n}", start));
      expect(body).toContain("blending: AdditiveBlending");
      expect(body).toContain("fragmentShader:");
      expect(body).not.toContain("colorspace_fragment");
    }
  });
});
