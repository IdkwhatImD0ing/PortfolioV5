import {
  AdditiveBlending,
  BufferGeometry,
  Color,
  CustomBlending,
  DepthTexture,
  DoubleSide,
  Float32BufferAttribute,
  FrontSide,
  Mesh,
  MeshBasicMaterial,
  Object3D,
  OneMinusSrcAlphaFactor,
  RedFormat,
  RepeatWrapping,
  RGBAFormat,
  ShaderChunk,
  ShaderLib,
  ShaderMaterial,
  SrcAlphaFactor,
  Texture,
  Matrix4,
  Vector2,
  Vector3,
  Vector4,
  ZeroFactor,
  type WebGLRenderer,
} from "three";
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { PUFF_STRIDE } from "@/lib/sect/clouds";
import { DETAIL_LOOK, DETAIL_NOISE, detailProgramKey, weatherApplyGlsl, weatherGlsl } from "@/lib/sect/detail";
import { fogConstantsFromMeta, fogDefines, glslFloat, SCREEN_GRADE_PARS } from "@/lib/sect/glsl";
import { heartMirrorGlsl } from "@/lib/sect/heart-mirror";
import { LIVE_CLASSES, liveApplyGlsl, liveAtlasOf, liveSheenGlsl, liveSurfaceNormalGlsl } from "@/lib/sect/live";
import { SECT_LOOK } from "@/lib/sect/look";
import { SUNSET_PULL, SUNSET_PULL_APPLY, sunsetPullData } from "@/lib/sect/night-bake";
import { parseMeta } from "@/lib/sect/parse";
import {
  STEAM_BRANCH,
  STEAM_HIDE_STATEMENT,
  STEAM_NW_PER_METRE,
  steamChurnStatement,
  steamClimbStatement,
  steamVertexGlsl,
  steamVertexStatements,
} from "@/lib/sect/steam";
import { wetFalls } from "@/lib/sect/waterfall";
import { LiveShadowMap } from "./live-shadow";
import { REFLECT } from "./reflect/plan";
import {
  aimPondMirror,
  createBeamMaterial,
  createCloudPuffMaterial,
  createCloudSeaMaterial,
  createDetailUniforms,
  createMistMaterial,
  createWaterfallMaterial,
  enableFogEncodeOnce,
  ENV_GLSL,
  installFog,
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
  installAreas,
  isBuiltMaterial,
  isLiveCandidate,
  isNearTreeMaterial,
  liveAtlasUniforms,
  liveClassOfMaterial,
  liveClassUniforms,
  markBuiltSliced,
  commitBuilt,
  isTreeCardMaterial,
  patchCardMaterial,
  veilBlending,
  patchMaterial,
  prepareBakedMaterial,
  prepareNeedleCard,
  SCREEN_DITHER_GLSL,
  SECT_AREAS,
  SECT_ENV,
  SECT_LIVE,
  SECT_MIRROR,
  SECT_PULL,
  SECT_WEATHER,
  SECT_WET,
  sectSurfaceOf,
  setCardAlphaMode,
  setMaterialLive,
  setSheetStrands,
  surfaceGlsl,
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
    // Order: the cut-out and the test (discard), then the grade, then the twig detail on the graded
    // colour (the grade is not linear), then the rim.
    const order = [
      "sectCut.r",
      "float sectPx",
      "if ( sectPx < 0.0 ) discard;",
      "sectGraded",
      "diffuseColor.rgb *= sectTwigK;",
      "outgoingLight += uSectRim",
      "#include <opaque_fragment>",
    ];
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

  it("grades every card kind after its cut-out test, with the derivative work before the discard", () => {
    for (const kind of ["needle", "twig", undefined]) {
      for (const a2c of [false, true]) {
        const fs = prepareCard(kind, a2c).shader.fragmentShader;
        const grade = fs.indexOf("vec3 sectTexel");
        const test = kind ? fs.indexOf("discard;") : fs.indexOf("#include <alphatest_fragment>");
        expect(grade, `${kind} ${a2c}`).toBeGreaterThan(test);
        expect(test).toBeGreaterThan(fs.indexOf("float sectPx"));
        // Nothing with screen derivatives sits between the discard and the end of the grade.
        const after = fs.slice(test, fs.indexOf("outgoingLight += uSectRim"));
        expect(after).not.toMatch(/dFd[xy]|fwidth/);
        // The grade reads the texel colour, which nothing has multiplied yet.
        expect(fs.indexOf("vec3 sectTexel")).toBeLessThan(fs.indexOf("diffuseColor.rgb = sectGraded"));
        expect(fs.indexOf("diffuseColor.rgb *= sectTwigK;") === -1).toBe(kind !== "twig");
      }
    }
  });

  it("takes a card's range weight from the vertices' margin, and only runs the area loop near an area", () => {
    for (const kind of ["needle", "twig", undefined]) {
      const { shader } = prepareCard(kind, false);
      expect(shader.vertexShader).toContain("float sectRangeMargin( vec3 p )");
      expect(shader.vertexShader).toContain("vSectRm = sectRangeMargin( vSectWorld );");
      expect(shader.fragmentShader).toContain("varying float vSectRm;");
      expect(shader.fragmentShader).toMatch(/float sectRw = 1\.0;\n {2}if \( vSectRm < 4\.0 \) sectRw = sectRangeW\( vSectWorld \);/);
      // The canopy variation is not smooth at card scale: still per pixel.
      expect(shader.fragmentShader).toContain("sectCanopyVary( sectGraded, sectTexel, vSectWorld, sectRw )");
    }
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

describe("the night-baked stops' pull toward the sunset bake (night-bake.ts)", () => {
  const baked = (name: string) => {
    const mat = new MeshBasicMaterial({ map: new Texture() });
    mat.name = name;
    mat.userData = { baked: true };
    prepareBakedMaterial(mat);
    return mat;
  };

  it("pulls the abode's and the summit's atlas texels, before the grade, by the shared amount and the chunk's own terms", () => {
    for (const [name, chunk] of [
      ["baked.abode_A0", "abode"],
      ["baked.summit_A2.detail.rock", "summit"],
    ] as const) {
      const mat = baked(name);
      const shader = compile(mat);
      const fs = shader.fragmentShader;
      const at = fs.indexOf(SUNSET_PULL_APPLY);
      expect(at, name).toBeGreaterThan(fs.indexOf("vec3 sectTexel = "));
      expect(at, name).toBeLessThan(fs.indexOf("vec3 sectGraded = "));
      expect(fs).toContain("vec3 sectSunsetPull( vec3 c, vec3 wp )");
      expect(shader.vertexShader).toContain("vSectWorld = ");
      // One amount for every pulled material (the look sets it), one set of terms per chunk.
      expect(shader.uniforms.uSectPullAmount).toBe(SECT_PULL.uSectPullAmount);
      const terms = (shader.uniforms.uSectPull as { value: Float32Array }).value;
      expect([...terms]).toEqual([...sunsetPullData(SUNSET_PULL[chunk])]);
      expect(compile(baked(name)).uniforms.uSectPull).toBe(shader.uniforms.uSectPull);
      expect(mat.customProgramCacheKey()).toMatch(/\|pull-[0-9a-z]+$/);
    }
  });

  it("leaves every other chunk, the glows and the vertex-coloured pieces as they were", () => {
    for (const name of ["baked.gate_A0", "baked.formation_A1", "baked.abode_A0.glow.lantern", "baked.vc"]) {
      const mat = baked(name);
      expect(compile(mat).fragmentShader, name).not.toContain("sectSunsetPull");
      expect(mat.customProgramCacheKey(), name).not.toContain("pull");
    }
  });
});

describe("wet rock on baked surfaces", () => {
  const baked = () => {
    const mat = new MeshBasicMaterial({ map: new Texture() });
    // A chunk baked at sunset (the abode's and the summit's also take the pull: night-bake.ts).
    mat.name = "baked.gate_A0";
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
    // The rock photo's middle band starts at its look's gain (a uniform: tuned from the console).
    expect(uniforms.uSectRockMid.value).toBe(DETAIL_LOOK.rockMid.gain);
    expect(uniforms.uSectTime).toBe(time);
    expect(uniforms.uSectSun.value).toBe(sun);
    expect(uniforms.tSectGroundNoise.value).toBe(getGroundNoiseTexture());
    expect(uniforms.tSectClump.value).toBe(getClumpTexture());
  });

  it("binds the page's uniform objects, so a switch set on ctx.detail reaches every material", () => {
    for (const kind of ["rock", "ground"] as const) {
      const { shader } = detailed(kind);
      for (const name of ["uSectGroundLayers", "uSectRockFar", "uSectRockMid", "uSectTime", "uSectSun", "tSectClump", "tSectGroundNoise", "tSectDetail", "uSectDetailOn"] as const) {
        expect(shader.uniforms[name], `${kind} ${name}`).toBe(uniforms[name]);
      }
    }
    // So the band's gain set once on ctx.detail reaches every rock material, and B is read from the same texture.
    const a = detailed("rock").shader;
    const b = detailed("rock").shader;
    expect(a.uniforms.uSectRockMid).toBe(b.uniforms.uSectRockMid);
    expect(a.fragmentShader).toContain("* uSectDetailOn * uSectRockMid * sectRockMidOn;");
    expect(count(a.fragmentShader, "uniform sampler2D tSectDetail;")).toBe(1);
  });

  it("keeps the texel before the grade, then applies the layers after the grade and before the wet rock", () => {
    for (const kind of ["rock", "ground"] as const) {
      const fs = detailed(kind).shader.fragmentShader;
      // Rock and ground grade with the range look's parameters (range-look.ts rockGradeStatements, groundGradeStatements).
      const order = ["vec3 sectTexel = diffuseColor.rgb / max( diffuse", "float sectRw = sectRangeW( vSectWorld )", "sectGradeWith( sectTexel,", "sectGroundLayers( diffuseColor.rgb", "sectWetRock( diffuseColor.rgb"];
      const at = order.map((x) => fs.indexOf(x));
      expect(at.every((i) => i >= 0), kind).toBe(true);
      expect([...at].sort((a, b) => a - b)).toEqual(at);
      for (const u of ["sampler2D tSectGroundNoise", "sampler2D tSectClump", "float uSectGroundLayers", "float uSectTime", "vec3 uSectSun"]) {
        expect(count(fs, `uniform ${u};`), `${kind} ${u}`).toBe(1);
      }
      expect(count(fs, "uniform float uSectRockFar;")).toBe(kind === "rock" ? 1 : 0);
      expect(count(fs, "uniform float uSectRockMid;")).toBe(kind === "rock" ? 1 : 0);
      // Rock under anything built (stair piers) keeps its stone; lawns do not ask.
      expect(fs.includes("sectRangeW( vSectWorld ) * ( 1.0 - sectBuilt( vSectWorld ) )")).toBe(kind === "rock");
      // An area's far stand-in does not read the built mask: it looks the same before and after its area has loaded.
      expect(fs.includes("#ifdef SECT_STANDIN\n  float sectRw = sectRangeW( vSectWorld );\n#else\n  float sectRw = sectRangeW( vSectWorld ) * ( 1.0 - sectBuilt( vSectWorld ) );\n#endif")).toBe(kind === "rock");
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
    expect(fs).not.toContain("sectDetail");
    expect(fs).not.toContain("tSectClump");
    expect(fs).not.toContain("uSectGroundLayers");
    // It reads the ground noise for its weathering instead (see below).
    expect(fs).toContain("sectWeather(");
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

describe("weathering on baked surfaces with no detail class", () => {
  const uniforms = createDetailUniforms(new Texture(), { time: { value: 0 }, sunDir: new Vector3(0, 0.12, -1).normalize(), rockOctaves: 1 });
  const baked = (name: string, userData: Record<string, unknown> = {}, detail: typeof uniforms | null = uniforms, map = true) => {
    const mat = new MeshBasicMaterial(map ? { map: new Texture() } : {});
    mat.name = name;
    mat.userData = { baked: true, ...userData };
    prepareBakedMaterial(mat, detail);
    return mat;
  };
  const glsl = weatherGlsl();
  const apply = weatherApplyGlsl();
  const count = (s: string, sub: string) => s.split(sub).length - 1;

  it("weathers walls, pillars and marble after the grade and before the wet rock, from the shared uniforms", () => {
    const mat = baked("baked.abode_A0");
    const sh = compile(mat);
    const fs = sh.fragmentShader;
    expect(count(fs, glsl)).toBe(1);
    expect(count(fs, apply)).toBe(1);
    const at = [glsl, "void main()", "diffuseColor.rgb = sectGraded * diffuse;", apply, "sectWetRock( diffuseColor.rgb, vSectWorld )", "#include <opaque_fragment>"].map((x) => fs.indexOf(x));
    expect(at.every((i) => i >= 0)).toBe(true);
    expect([...at].sort((a, b) => a - b)).toEqual(at);
    expect(sh.vertexShader).toContain("vSectWorld = ");
    // One switch for every material, on; the ground noise every layer shares.
    expect(sh.uniforms.uSectWeather).toBe(SECT_WEATHER.uSectWeather);
    expect(SECT_WEATHER.uSectWeather.value).toBe(1);
    expect((sh.uniforms.tSectGroundNoise as { value: unknown }).value).toBe(getGroundNoiseTexture());
    expect(count(fs, "uniform sampler2D tSectGroundNoise;")).toBe(1);
    for (const name of [...includes(fs), ...includes(sh.vertexShader)]) {
      expect((ShaderChunk as unknown as Record<string, string>)[name], name).toBeTypeOf("string");
    }
  });

  it("leaves the detail classes to their own layers: no weathering on paving, rock, ground or roof tiles", () => {
    for (const kind of ["paving", "rock", "ground", "tiles"] as const) {
      const mat = baked(`baked.gate_A0.detail.${kind}`, { detail: kind });
      const fs = compile(mat).fragmentShader;
      expect(fs, kind).not.toContain("sectWeather");
      expect(fs, kind).not.toContain("uSectWeather");
      expect(mat.customProgramCacheKey(), kind).not.toContain("weather");
      // At most one declaration of the noise texture they share by name (a second would not compile).
      expect(count(fs, "uniform sampler2D tSectGroundNoise;"), kind).toBe(kind === "tiles" ? 0 : 1);
    }
    // Roof tiles keep their class on the low tier too (no detail uniforms there).
    expect(compile(baked("baked.gate_A0.detail.tiles", { detail: "tiles" }, null)).fragmentShader).not.toContain("sectWeather");
  });

  it("goes with the detail layers: none on a tier with no detail uniforms (low), whatever the class", () => {
    for (const [name, ud] of [
      ["baked.abode_A0", {}],
      ["baked.gate_A0.detail.paving", { detail: "paving" }],
      ["baked.gate_A0.detail.rock", { detail: "rock" }],
      ["baked.gate_A1.detail.ground", { detail: "ground" }],
    ] as const) {
      for (const detail of [null, undefined]) {
        const mat = new MeshBasicMaterial({ map: new Texture() });
        mat.name = name;
        mat.userData = { baked: true, ...ud };
        prepareBakedMaterial(mat, detail);
        const fs = compile(mat).fragmentShader;
        expect(fs, `${name} ${detail}`).not.toContain("sectWeather");
        expect(fs, `${name} ${detail}`).not.toContain("uSectWeather");
        expect(mat.customProgramCacheKey(), `${name} ${detail}`).not.toContain("weather");
      }
    }
    // With them, the plain wall has it.
    const wall = baked("baked.abode_A0");
    expect(compile(wall).fragmentShader).toContain(apply);
    expect(wall.customProgramCacheKey()).toContain("|weather-");
  });

  it("never weathers a reflective class, even one tagged after patching: the key and the shader both follow", () => {
    for (const kind of ["metal", "iron", "glaze", "mirror"] as const) {
      const tagged = baked("baked.gate_A0", { sectSurface: kind });
      expect(compile(tagged).fragmentShader, kind).not.toContain("sectWeather");
      expect(tagged.customProgramCacheKey(), kind).not.toContain("weather");
      // Tagged after loading (read at its next compile, like the class itself).
      const mat = baked("baked.gate_A0");
      const before = mat.customProgramCacheKey();
      expect(before, kind).toContain("|weather-");
      mat.userData.sectSurface = kind;
      const key = mat.customProgramCacheKey();
      expect(key, kind).not.toContain("weather");
      expect(key, kind).toContain(`|surface-${kind}`);
      const fs = compile(mat).fragmentShader;
      expect(fs, kind).not.toContain("sectWeather");
      expect(fs, kind).not.toContain("uniform sampler2D tSectGroundNoise;");
      expect(fs, kind).toContain(surfaceGlsl(kind));
      // And back.
      delete mat.userData.sectSurface;
      expect(mat.customProgramCacheKey(), kind).toBe(before);
      expect(compile(mat).fragmentShader, kind).toContain(apply);
    }
  });

  it("leaves out cloth that sways, hotspot copies, water, cards, trees, cut-outs and materials without the atlas map", () => {
    const copy = new MeshBasicMaterial({ map: new Texture() });
    copy.name = "baked.gate_A0";
    copy.userData = { baked: true };
    // A hotspot's copy (some of them move), even if asked for the weathering.
    patchMaterial(copy, { lit: true, exposure: 1, highlight: { value: 0 }, weather: true });
    const pond = new MeshBasicMaterial({ map: new Texture() });
    pond.name = "baked.gate_A0";
    pond.userData = { baked: true };
    patchMaterial(pond, { lit: false, exposure: 1, water: createWaterUniforms({ level: 0, disc: null }), weather: true });
    const cut = new MeshBasicMaterial({ map: new Texture(), alphaTest: 0.5 });
    cut.name = "baked.gate_A0";
    cut.userData = { baked: true };
    prepareBakedMaterial(cut, uniforms);
    const cases: [string, MeshBasicMaterial][] = [
      ["sway", baked("baked.gate_A0", { sectSway: true })],
      ["hotspot copy", copy],
      ["pond", pond],
      ["near pine", baked("trees.mesh.gate")],
      ["far card", baked("trees.cards.gate")],
      ["cut-out", cut],
      ["no map", baked("baked.vc", {}, uniforms, false)],
      ...(["needle", "twig", undefined] as const).map((k): [string, MeshBasicMaterial] => [`card ${k}`, prepareCard(k, false).mat]),
    ];
    for (const [label, mat] of cases) {
      expect(compile(mat).fragmentShader, label).not.toContain("sectWeather");
      expect(mat.customProgramCacheKey(), label).not.toContain("weather");
    }
    // The weathered twin of each plain case does have it.
    expect(compile(baked("baked.gate_A0")).fragmentShader).toContain(apply);
  });

  it("changes the program key by its own tag and nothing else", () => {
    const wall = baked("baked.gate_A0").customProgramCacheKey();
    const flag = baked("baked.gate_A0", { sectSway: true }).customProgramCacheKey();
    expect(wall).toMatch(/\|wet\|weather-[0-9a-z]+$/);
    expect(wall).not.toBe(flag);
    expect(wall.replace(/\|weather-[0-9a-z]+/, "")).toBe(flag);
  });

  it("keeps every baked material, lit live or not, within 16 texture units", () => {
    const units = (fs: string) => 1 + [...fs.matchAll(/^uniform (?:highp )?sampler\w+ \w+;$/gm)].length;
    const cases: [string, Record<string, unknown>][] = [
      ["baked.gate_A0", {}],
      ["baked.gate_A0.detail.paving", { detail: "paving" }],
      ["baked.gate_A0.detail.rock", { detail: "rock" }],
      ["baked.gate_A1.detail.ground", { detail: "ground" }],
      ["baked.gate_A1.detail.tiles", { detail: "tiles" }],
      ["baked.gate_A0.surface.metal", { sectSurface: "metal" }],
    ];
    for (const detail of [uniforms, null]) {
      for (const [name, ud] of cases) {
        const mat = baked(name, ud, detail);
        expect(units(compile(mat).fragmentShader), name).toBeLessThanOrEqual(16);
        setMaterialLive(mat, { atlas: liveAtlasOf(name)!, cls: liveClassOfMaterial(mat) });
        expect(units(compile(mat).fragmentShader), `${name} live`).toBeLessThanOrEqual(16);
      }
    }
  });

  it("gives rock's middle band no texture unit of its own: a live rock stays at 15 (it reads B of the same detail texture)", () => {
    const units = (fs: string) => 1 + [...fs.matchAll(/^uniform (?:highp )?sampler\w+ \w+;$/gm)].length;
    const name = "baked.gate_A0.detail.rock";
    const mat = baked(name, { detail: "rock" });
    const plain = compile(mat).fragmentShader;
    expect(plain).toContain("sectRockDetail( vSectWorld");
    setMaterialLive(mat, { atlas: liveAtlasOf(name)!, cls: liveClassOfMaterial(mat) });
    expect(units(compile(mat).fragmentShader)).toBe(15);
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
    expect(fs.indexOf("sectTexel = sectTreeLift( sectTexel );")).toBeLessThan(fs.indexOf("sectGradeWith( sectTexel,"));
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

  // The forge fire, the fires and the life motes add linear light the same way: effect-look.test.ts.
});

describe("the range look (lib/sect/range-look.ts)", () => {
  const baked = (name: string, userData: Record<string, unknown> = {}) => {
    const m = new MeshBasicMaterial({ map: new Texture() });
    m.name = name;
    m.userData = { baked: true, ...userData };
    return m;
  };

  it("tells built atlas materials from terrain, trees, water and vertex colours", () => {
    expect(isBuiltMaterial(baked("baked.abode_A0"))).toBe(true);
    expect(isBuiltMaterial(baked("baked.abode_A0.detail.paving", { detail: "paving" }))).toBe(true);
    expect(isBuiltMaterial(baked("baked.abode_A0.detail.tiles", { detail: "tiles" }))).toBe(true);
    expect(isBuiltMaterial(baked("baked.abode_A0.detail.rock", { detail: "rock" }))).toBe(false);
    expect(isBuiltMaterial(baked("baked.abode_A0.detail.ground", { detail: "ground" }))).toBe(false);
    expect(isBuiltMaterial(baked("baked.vc"))).toBe(false);
    expect(isBuiltMaterial(baked("trees.mesh.abode"))).toBe(false);
    expect(isBuiltMaterial(baked("baked.abode_water"))).toBe(false);
    expect(isBuiltMaterial(new MeshBasicMaterial())).toBe(false);
  });

  it("marks a built mesh's treads in the shared mask and uploads it", () => {
    installAreas([{ anchor: [0, 40, 0], footprint: 40 }]);
    const tex = SECT_AREAS.tSectBuilt.value;
    const geo = new BufferGeometry();
    geo.setAttribute("position", new Float32BufferAttribute([10, 50, 10, 12, 50, 10, 10, 50, 12], 3));
    const mesh = new Mesh(geo, baked("baked.gate_A0"));
    const v0 = tex.version;
    for (const step of markBuiltSliced(mesh)) void step;
    commitBuilt();
    expect(tex.version).toBeGreaterThan(v0);
    const box = SECT_AREAS.uSectBuiltBox.value;
    const i = Math.floor((10.5 - box.x) * box.z * tex.image.width);
    const j = Math.floor((10.5 - box.y) * box.w * tex.image.height);
    expect((tex.image.data as Uint8Array)[j * tex.image.width + i]).toBe(255);
    // Terrain does not mark.
    const rock = new Mesh(geo, baked("baked.gate_A0.detail.rock", { detail: "rock" }));
    expect([...markBuiltSliced(rock)]).toHaveLength(0);
  });

  it("gives range materials the shared areas and built mask", () => {
    const rock = baked("baked.gate_A0.detail.rock", { detail: "rock" });
    prepareBakedMaterial(rock);
    const shader = compile(rock);
    expect(shader.uniforms.uSectAreas).toBe(SECT_AREAS.uSectAreas);
    expect(shader.uniforms.tSectBuilt).toBe(SECT_AREAS.tSectBuilt);
    expect(shader.fragmentShader).toContain("sectRockRange( sectGraded, sectRw * ( 1.0 - sectMoss ), length( vSectWorld - cameraPosition ) )");
    const card = cardMaterial();
    prepareBakedMaterial(card);
    const cs = compile(card);
    expect(cs.uniforms.uSectAreas).toBe(SECT_AREAS.uSectAreas);
    expect(cs.fragmentShader).toContain("sectFoliageRange( sectGraded, sectTexel, sectRw, length( vSectWorld - cameraPosition ) )");
    // On Low (no detail layers) rock and lawns still get their own programs: with one key, three
    // drew Low's rock with the lawns' program.
    const lawn = baked("baked.gate_A0.detail.ground", { detail: "ground" });
    prepareBakedMaterial(lawn);
    expect(rock.customProgramCacheKey()).not.toBe(lawn.customProgramCacheKey());
    expect(compile(lawn).fragmentShader).not.toContain("sectRockRange(");
    // Halls (generic atlas) keep the plain grade and no range uniforms.
    const hall = baked("baked.gate_A0");
    prepareBakedMaterial(hall);
    const hs = compile(hall);
    expect(hs.uniforms.uSectAreas).toBeUndefined();
    expect(hs.fragmentShader).toContain("vec3 sectGraded = sectGrade( sectTexel );");
  });
});

describe("fog worked out once per sprite", () => {
  const fog = fogConstantsFromMeta(parseMeta({}));

  it("computes the cloud puff's haze, cloud and sun glow in the vertex shader and only reads them per pixel", () => {
    const mat = createCloudPuffMaterial(fog, "#c8ada0");
    expect(mat.vertexShader).toContain("vHazeMix = 1.0 - exp( - sectHazeDepth( cameraPosition.y, f.y, dist ) );");
    expect(mat.vertexShader).toContain("vHaze = sectHazeColor( uFogColor, f );");
    expect(mat.vertexShader).toContain("vCloudMix = 1.0 - exp( - sectCloudDepth( cameraPosition.y, f.y, dist ) );");
    expect(mat.vertexShader).toContain("vToward = pow( max( dot( f, SECT_SUN_DIR ), 0.0 ), 5.0 );");
    // The Low tier's frame grade (SCREEN_GRADE_PARS: folded away on High and Mid) is the only pow left.
    const fs = mat.fragmentShader.replace(SCREEN_GRADE_PARS, "");
    for (const call of ["sectHazeDepth(", "sectCloudDepth(", "sectHazeColor(", "pow("]) {
      expect(fs).not.toContain(call);
    }
    expect(mat.fragmentShader).toContain("col = mix( col, vHaze, vHazeMix );");
    expect(mat.fragmentShader).toContain("col = mix( col, SECT_CLOUD_FOG, vCloudMix );");
  });

  it("does the same for the mist sprites", () => {
    const mat = createMistMaterial(fog, "#c8ada0", { value: 0 });
    expect(mat.vertexShader).toContain("vHaze = sectHazeColor( uFogColor, f );");
    expect(mat.fragmentShader).not.toContain("sectHazeDepth(");
    expect(mat.fragmentShader).not.toContain("uFogColor");
    expect(mat.fragmentShader).toContain("col = mix( col, vHaze, vHazeMix );");
  });
});

describe("one colour conversion on the low tier", () => {
  it("guards three's encode behind SECT_FOG_FOLLOWS once installFog has run, for the fog chunk's shaders only", () => {
    const c = fogConstantsFromMeta(parseMeta({}));
    installFog(c);
    installFog({ ...c, density: c.density + 1 });
    const chunk = (ShaderChunk as unknown as Record<string, string>).colorspace_fragment;
    expect(chunk.startsWith("#ifndef SECT_FOG_FOLLOWS")).toBe(true);
    expect(chunk.match(/#ifndef SECT_FOG_FOLLOWS/g)).toHaveLength(1);
    expect(chunk).toContain("linearToOutputTexel");
    expect(fogDefines(c)).not.toContain("SECT_FOG_FOLLOWS");
  });

  it("opts in the waterfall and keeps a linear copy of the scene fog colour", () => {
    const mat = createWaterfallMaterial("#e6eff2");
    expect(mat.defines).toHaveProperty("SECT_FOG_ONCE");
    const fogColor = new Color("#c8ada0");
    const uniform = mat.uniforms.uSectFogLinear.value as Color;
    const call = (scene: unknown) => mat.onBeforeRender({} as never, scene as never, {} as never, {} as never, {} as never, {} as never);
    call({ fog: { color: fogColor } });
    expect(uniform.toArray()).toEqual(fogColor.toArray());
    // Without scene fog it leaves the value alone.
    fogColor.set("#000000");
    call({});
    expect(uniform.r).toBeGreaterThan(0);
  });

  it("enableFogEncodeOnce adds the define and the uniform to a material", () => {
    const other = new ShaderMaterial({ uniforms: {} });
    enableFogEncodeOnce(other);
    expect(other.defines.SECT_FOG_ONCE).toBe("");
    expect(other.uniforms.uSectFogLinear.value).toBeInstanceOf(Color);
  });
});

describe("what veils the world says so in the frame's alpha", () => {
  const fog = fogConstantsFromMeta(parseMeta({}));

  it("draws the mist's colour as before and multiplies the alpha by what it lets through", () => {
    // The contact shade (post/ao.ts) is worked out from the world's depth, which the mist is not in.
    // It reads this alpha so it fades under the mist instead of being drawn on top of it.
    for (const mat of [createCloudPuffMaterial(fog, "#c8ada0"), createMistMaterial(fog, "#c8ada0", { value: 0 })]) {
      expect(mat.blending, mat.name).toBe(CustomBlending);
      expect(mat.blendSrc).toBe(SrcAlphaFactor);
      expect(mat.blendDst).toBe(OneMinusSrcAlphaFactor);
      expect(mat.blendSrcAlpha).toBe(ZeroFactor);
      expect(mat.blendDstAlpha).toBe(OneMinusSrcAlphaFactor);
      expect(mat.transparent).toBe(true);
      expect(mat.depthWrite).toBe(false);
    }
    const plain = veilBlending(new MeshBasicMaterial());
    expect(plain.blending).toBe(CustomBlending);
  });

  it("keeps a far beam from thinning to a scratch: a floor under its width, dimmer for what it gains", () => {
    const beam = createBeamMaterial(fog, "#c8ada0", { value: 0 });
    expect(beam.vertexShader).toContain("float halfW = max( half0, length( toMid ) * 0.014 );");
    expect(beam.vertexShader).toContain("vGain = sqrt( half0 / halfW );");
    expect(beam.fragmentShader).toContain("* uOpacity * vGain *");
  });

  it("leaves lights that only add (beams, glows) out of it", () => {
    expect(createBeamMaterial(fog, "#c8ada0", { value: 0 }).blending).toBe(AdditiveBlending);
    expect(createGlowMaterial("#ffffff", 1).blending).toBe(AdditiveBlending);
  });
});

describe("the mist reads one field of noise fixed in the world", () => {
  it("so a row of puffs is one bank, with a second field at each puff's own scale", () => {
    const mat = createCloudPuffMaterial(fogConstantsFromMeta(parseMeta({})), "#c8ada0");
    expect(mat.vertexShader).toContain("vWorld = wp;");
    expect(mat.fragmentShader).toContain("vec2 nw = vec2( vWorld.x * 0.82 + vWorld.z * 0.57, vWorld.y * 1.35 )");
    expect(mat.fragmentShader).toContain("n = mix( n, own, 0.42 );");
  });

  it("ends in a wide soft rim, not an outline", () => {
    const fs = createCloudPuffMaterial(fogConstantsFromMeta(parseMeta({})), "#c8ada0").fragmentShader;
    // The band starts below zero and is squared: a narrow band (0 to 0.55) drew a line round every
    // puff, and the puffs round the pillars read as stickers.
    expect(fs).toContain("float edge = smoothstep( -0.2, 0.8, wisp );");
    expect(fs).toContain("float alpha = ( 1.0 - exp( - tau ) ) * edge * edge;");
    // A bank near the camera keeps a smooth lit body: density thinned all the way through by the
    // field was tried and made the banks blotchy with a hard top edge.
    expect(fs).not.toContain("float dens =");
  });

  it("gives a flat bank seen edge on room for that rim, and thins it for the height it gained", () => {
    const vs = createCloudPuffMaterial(fogConstantsFromMeta(parseMeta({})), "#c8ada0").vertexShader;
    expect(vs).toContain("wu = max( wu, wr * 0.4 );");
    expect(vs).toContain("float spread = wu0 / wu;");
    expect(vs).toContain("vDepth = puffD * wf * 2.0 * spread;");
  });

  it("adds a little relief to the light: the same field a step toward the sun", () => {
    const fs = createCloudPuffMaterial(fogConstantsFromMeta(parseMeta({})), "#c8ada0").fragmentShader;
    expect(fs).toContain("vec2 sunStep = vec2( SECT_SUN_DIR.x * 0.82 + SECT_SUN_DIR.z * 0.57, SECT_SUN_DIR.y * 1.35 ) * 14.0;");
    expect(fs).toContain("float light = clamp( sun * 0.6 + ( vUv.y * 0.5 + 0.5 ) * 0.42 + ");
    expect(fs).toContain("+ relief * 1.8 - 0.1");
  });
});

describe("Ice-Fire Island's steam rises (lib/sect/steam.ts)", () => {
  const mat = () => createCloudPuffMaterial(fogConstantsFromMeta(parseMeta({})), "#c8ada0");
  const BRANCH = STEAM_BRANCH;

  it("loops a puff with a rise span upward in the vertex shader, only while uSteam is on", () => {
    expect(BRANCH).toBe("if ( iRise != 0.0 && uSteam > 0.5 ) {");
    const m = mat();
    const vs = m.vertexShader;
    expect(vs).toContain("attribute float iRise;");
    expect(vs).toContain("uniform float uSteam;");
    expect(vs).toContain("uniform float uTime;");
    expect(vs).toContain(steamVertexGlsl());
    expect(vs).toContain(`  ${BRANCH}\n${steamVertexStatements()}\n  }`);
    expect(m.uniforms.uSteam.value).toBe(1);
    // The puff is copied from its attributes before the branch, and drawn from the copies after it.
    const before = vs.slice(vs.indexOf("void main() {"), vs.indexOf(BRANCH));
    for (const line of ["vec3 puffC = iCenter;", "vec3 puffA0 = iA0;", "vec3 puffA1 = iA1;", "vec3 puffA2 = iA2;", "float puffD = iDensity;", "vSteam = 0.0;"]) {
      expect(before).toContain(line);
    }
    const after = vs.slice(vs.indexOf(BRANCH));
    const rest = after.slice(after.indexOf("\n  }\n"));
    expect(rest).toContain("vec3 toC = puffC - cameraPosition;");
    expect(rest).toContain("vec3 wp = puffC - f * lift + ");
    expect(rest).toContain("float wf = length( vec3( dot( puffA0, f ), dot( puffA1, f ), dot( puffA2, f ) ) );");
    // Only the sprite's noise seed reads the packed centre: it stays with the puff's place.
    expect(rest.match(/iCenter/g)).toHaveLength(1);
    expect(rest).toContain("vSeed = fract( iCenter.xz * 0.0137 );");
    // After the branch only the hiding of the second copy reads iRise and uSteam.
    const restBut = rest.replace(`${STEAM_HIDE_STATEMENT}\n`, "");
    expect(restBut).not.toBe(rest);
    expect(restBut).not.toMatch(/iA[012]|iDensity|iRise|uSteam|steam[A-Z]/);
  });

  it("does nothing else in the branch, so every other puff is drawn exactly as before", () => {
    const vs = mat().vertexShader;
    const start = vs.indexOf(BRANCH) + BRANCH.length;
    const body = vs.slice(start, vs.indexOf("\n  }\n", start)).split("\n").filter((l) => l.trim());
    expect(body.length).toBeGreaterThan(5);
    for (const line of body) {
      expect(line, line).toMatch(/^ {4}(float steam(Span|S|Up|Grow|Share) = |puffC \+= |puffA[012] \*= steamGrow;|puffD \*= |vSteam = 1\.0;)/);
    }
    // The hash runs only there.
    expect(vs.split("sectSteamHash(").length - 1).toBe(2);
  });

  it("hides a steam puff's second copy while the steam stands still: set just before the faded quad collapses", () => {
    const vs = mat().vertexShader;
    const collapse = "  if ( vFade < 0.003 ) gl_Position = vec4( 2.0, 2.0, 2.0, 1.0 );";
    expect(vs.split(STEAM_HIDE_STATEMENT).length - 1).toBe(1);
    expect(vs.indexOf(STEAM_HIDE_STATEMENT)).toBeGreaterThan(vs.indexOf("gl_Position = projectionMatrix * mv;"));
    expect(vs.indexOf(STEAM_HIDE_STATEMENT)).toBeLessThan(vs.indexOf(collapse));
    // The fragment shader drops what the vertex shader faded out.
    expect(mat().fragmentShader).toContain("if ( q2 > 1.0 || vFade < 0.003 ) discard;");
  });

  it("lets the steam sprite's noise climb in the fragment shader: the world field and its own", () => {
    const fs = mat().fragmentShader;
    expect(fs).toContain("varying float vSteam;");
    const nl = "  vec2 nl = vUv * vec2( 1.15, 1.9 ) + vSeed * 9.0 + vec2( uTime * 0.004, 0.0 );\n";
    expect(fs).toContain(nl);
    expect(fs).toContain(steamChurnStatement());
    expect(fs.indexOf(steamChurnStatement())).toBeGreaterThan(fs.indexOf(nl));
    expect(fs.indexOf(steamChurnStatement())).toBeLessThan(fs.indexOf("float own = "));
    expect(steamChurnStatement()).toMatch(/^ {2}if \( vSteam > 0\.5 \) nl\.y -= /);
    // The world field: one metre up is STEAM_NW_PER_METRE units of nw.y, and it rises before any read.
    const nw = `  vec2 nw = vec2( vWorld.x * 0.82 + vWorld.z * 0.57, vWorld.y * ${STEAM_NW_PER_METRE} ) + vec2( uTime * 0.7, 0.0 );\n`;
    expect(fs).toContain(nw);
    expect(fs.indexOf(steamClimbStatement())).toBeGreaterThan(fs.indexOf(nw));
    expect(fs.indexOf(steamClimbStatement())).toBeLessThan(fs.indexOf("float n1 = "));
    expect(steamClimbStatement()).toMatch(/^ {2}if \( vSteam > 0\.5 \) nw\.y -= uTime \* /);
  });

  it("is fed by scene.tsx CloudPuffs: the span as iRise, the 14th float, and uSteam off with reduced motion", () => {
    const src = readFileSync(path.resolve(__dirname, "scene.tsx"), "utf8").replace(/\r\n/g, "\n");
    const puffs = src.slice(src.indexOf("function CloudPuffs("), src.indexOf("function OverlayDecor("));
    expect(puffs).toContain("(p) => steamRise(p),");
    expect(puffs).toContain('geo.setAttribute("iRise", new InterleavedBufferAttribute(buf, 1, 13));');
    expect(puffs).toContain("built.material.uniforms.uSteam.value = store.reducedMotion ? 0 : 1;");
    // The attributes tile the packed puff exactly: 14 floats, none read twice or left out.
    const used = new Array<number>(PUFF_STRIDE).fill(0);
    for (const [, size, offset] of puffs.matchAll(/new InterleavedBufferAttribute\(buf, (\d+), (\d+)\)/g)) {
      for (let k = Number(offset); k < Number(offset) + Number(size); k++) used[k]++;
    }
    expect(PUFF_STRIDE).toBe(14);
    expect(used).toEqual(new Array<number>(PUFF_STRIDE).fill(1));
    expect(puffs).toContain("new InstancedInterleavedBuffer(new Float32Array(packed), PUFF_STRIDE, 1)");
  });
});

describe("the sun in the sky", () => {
  it("screens its glow onto the sky, so the sky beside it never passes 1.0 into the hue clip", () => {
    const fog = fogConstantsFromMeta(parseMeta({}));
    const sky = createSkyMaterial({ fog, texture: null, zenith: "#8b9ad0", horizon: "#f3cfb2", below: "#c8ada0", fogColor: "#c8ada0", sunColor: "#fff0d0" });
    const fs = sky.fragmentShader;
    expect(fs).toContain("col = 1.0 - ( 1.0 - min( col, vec3( 1.0 ) ) ) * ( 1.0 - min( glow, vec3( 1.0 ) ) );");
    // Only the disc itself is added, after the screen.
    expect(fs.indexOf("col += mix( uSunColor, vec3( 1.0 ), 0.88 )")).toBeGreaterThan(fs.indexOf("col = 1.0 - ( 1.0 - min( col"));
  });
});

describe("live light (lib/sect/live.ts)", () => {
  const baked = (name: string, userData: Record<string, unknown> = {}, map = true) => {
    const mat = new MeshBasicMaterial(map ? { map: new Texture() } : {});
    mat.name = name;
    mat.userData = { baked: true, ...userData };
    prepareBakedMaterial(mat);
    return mat;
  };
  const names: [string, Record<string, unknown>][] = [
    ["baked.gate_A0", {}],
    ["baked.gate_A0.detail.paving", { detail: "paving" }],
    ["baked.gate_A0.detail.rock", { detail: "rock" }],
    ["baked.gate_A1.detail.ground", { detail: "ground" }],
    ["baked.gate_A0.surface.metal", { sectSurface: "metal" }],
    ["baked.gate_A1.detail.tiles.surface.glaze", { detail: "tiles", sectSurface: "glaze" }],
  ];

  it("leaves a material that is not lit live exactly as it was, and gives it back exactly", () => {
    for (const [name, ud] of names) {
      const mat = baked(name, ud);
      const key = mat.customProgramCacheKey();
      const sh = compile(mat);
      expect(sh.fragmentShader).not.toMatch(/SectLive|SECT_LIVE|sectLive/);
      expect(Object.keys(sh.uniforms).some((u) => /SectLive/.test(u))).toBe(false);
      expect(key).not.toContain("live");
      setMaterialLive(mat, { atlas: liveAtlasOf(name)!, cls: liveClassOfMaterial(mat) });
      expect(mat.customProgramCacheKey()).not.toBe(key);
      expect(compile(mat).fragmentShader).not.toBe(sh.fragmentShader);
      setMaterialLive(mat, null);
      expect(mat.customProgramCacheKey()).toBe(key);
      const again = compile(mat);
      expect(again.fragmentShader).toBe(sh.fragmentShader);
      expect(again.vertexShader).toBe(sh.vertexShader);
    }
  });

  it("keeps the surface classes' code as it was unless lit live, and metal and iron's even then", () => {
    for (const kind of ["metal", "glaze", "iron", "mirror"] as const) {
      expect(surfaceGlsl(kind)).toBe(surfaceGlsl(kind, SECT_LOOK.surfaces, false));
      expect(surfaceGlsl(kind)).not.toContain("sectLive");
    }
    for (const kind of ["glaze", "mirror"] as const) {
      const live = surfaceGlsl(kind, SECT_LOOK.surfaces, true);
      // The normal map's normal takes over after the face's is turned to the eye, before the reflection.
      const at = ["if ( dot( sN, sV ) > 0.0 ) sN = - sN;", "if ( sectLiveShare > 0.0 ) {", "vec3 sR = reflect( sV, sN );"].map((x) => live.indexOf(x));
      expect(at.every((i) => i >= 0), kind).toBe(true);
      expect([...at].sort((a, b) => a - b), kind).toEqual(at);
      expect(live.replace(liveSurfaceNormalGlsl(), ""), kind).toBe(surfaceGlsl(kind));
    }
    // The half-size normal map is wrong on thin metal (a crescent, a blade): in a mirror that shows as blotches.
    for (const kind of ["metal", "iron"] as const) {
      expect(surfaceGlsl(kind, SECT_LOOK.surfaces, true), kind).toBe(surfaceGlsl(kind));
    }
  });

  it("replaces the baked texel before the grade and the rest of the pipeline", () => {
    const mat = baked("baked.gate_A0.detail.paving", { detail: "paving" });
    setMaterialLive(mat, { atlas: "gate_A0", cls: liveClassOfMaterial(mat) });
    const sh = compile(mat);
    const fs = sh.fragmentShader;
    expect(fs).toContain("#define SECT_LIVE");
    // Blender's view transform as a table; the page's own AgX is not in an unlit material.
    expect(fs).toContain("uniform highp sampler3D tSectLiveView;");
    expect(fs).toContain("return sectLiveView( c * by.y );");
    // The look's post on the live colour, the bake's own on the bake as the maps rebuild it.
    expect(fs).toContain("return sectLivePostBy( c, vec3( uSectLiveGain, uSectLiveExposure, uSectLiveSat ) );");
    expect(fs).toContain("sectLivePostBy( sectLiveBaked( lAlb, lAmb * uSectLiveAmbient, lFace, lVis ), uSectLiveBakePost )");
    expect(fs).not.toContain("sectAgxPunchy");
    const at = [
      "#include <color_fragment>",
      "vec3 sectTexel = diffuseColor.rgb / max( diffuse, vec3( 1e-4 ) );",
      "lTex *= sectLiveDetail( sectTexel, lBake, lTrust );",
      "sectTexel = mix( sectTexel, lTex, sectLiveShare );",
      "sectGrade( sectTexel )",
      "#include <opaque_fragment>",
    ].map((x) => fs.indexOf(x));
    expect(at.every((i) => i >= 0)).toBe(true);
    expect([...at].sort((a, b) => a - b)).toEqual(at);
    expect(sh.vertexShader).toContain("vSectWorld = ");
    // The shared uniforms are the page's own objects, the maps the atlas's, the shine the class's.
    for (const name of Object.keys(SECT_LIVE) as (keyof typeof SECT_LIVE)[]) expect(sh.uniforms[name], name).toBe(SECT_LIVE[name]);
    const maps = liveAtlasUniforms("gate_A0");
    expect(sh.uniforms.tSectLiveAlbedo).toBe(maps.tSectLiveAlbedo);
    expect(sh.uniforms.tSectLiveAmbient).toBe(maps.tSectLiveAmbient);
    expect(sh.uniforms.tSectLiveNormal).toBe(maps.tSectLiveNormal);
    expect(sh.uniforms.uSectLiveSpec).toBe(liveClassUniforms("paving").uSectLiveSpec);
    expect(sh.uniforms.uSectLiveBump).toBe(liveClassUniforms("paving").uSectLiveBump);
    expect(liveAtlasUniforms("gate_A0")).toBe(maps);
    expect(mat.customProgramCacheKey()).toMatch(/\|live-[0-9a-z]+$/);
    expect(fs).not.toMatch(/NaN|undefined/);
    for (const name of [...includes(fs), ...includes(sh.vertexShader)]) {
      expect((ShaderChunk as unknown as Record<string, string>)[name], name).toBeTypeOf("string");
    }
  });

  it("gives each stop's atlases their own maps and every stop the one shared set of uniforms", () => {
    const gate = baked("baked.gate_A0.detail.paving", { detail: "paving" });
    const mirror = baked("baked.mirror_A0.detail.paving", { detail: "paving" });
    const formation = baked("baked.formation_A2");
    for (const mat of [gate, mirror, formation]) setMaterialLive(mat, { atlas: liveAtlasOf(mat.name)!, cls: liveClassOfMaterial(mat) });
    const [g, m, f] = [gate, mirror, formation].map((mat) => compile(mat));
    // One stop is lit at a time: the lamps, the centre, the blend and the shadow maps are the page's own objects.
    for (const name of Object.keys(SECT_LIVE) as (keyof typeof SECT_LIVE)[]) {
      expect(m.uniforms[name], name).toBe(SECT_LIVE[name]);
      expect(f.uniforms[name], name).toBe(SECT_LIVE[name]);
    }
    // The maps are each atlas's own.
    expect(m.uniforms.tSectLiveAlbedo).toBe(liveAtlasUniforms("mirror_A0").tSectLiveAlbedo);
    expect(f.uniforms.tSectLiveNormal).toBe(liveAtlasUniforms("formation_A2").tSectLiveNormal);
    expect(m.uniforms.tSectLiveAlbedo).not.toBe(g.uniforms.tSectLiveAlbedo);
    expect(m.uniforms.tSectLiveAmbient).not.toBe(g.uniforms.tSectLiveAmbient);
    expect(f.uniforms.tSectLiveNormal).not.toBe(g.uniforms.tSectLiveNormal);
    // The same live code whichever stop: the programs can be shared.
    expect(m.fragmentShader).toBe(g.fragmentShader);
    expect(mirror.customProgramCacheKey()).toBe(gate.customProgramCacheKey());
  });

  it("feeds glaze the normal map's normal when lit live, and not metal or iron", () => {
    const hook = "vec3 sLn = dot( sectLiveN, sV ) > 0.0 ? - sectLiveN : sectLiveN;";
    const glaze = baked("baked.gate_A1.detail.tiles.surface.glaze", { detail: "tiles", sectSurface: "glaze" });
    setMaterialLive(glaze, { atlas: "gate_A1", cls: liveClassOfMaterial(glaze) });
    expect(liveClassOfMaterial(glaze)).toBe("glaze");
    const gfs = compile(glaze).fragmentShader;
    expect(gfs).toContain(hook);
    expect(gfs.indexOf("vec3 sLn")).toBeGreaterThan(gfs.indexOf("sectTexel = mix( sectTexel, lTex, sectLiveShare );"));
    expect(glaze.customProgramCacheKey()).toContain("|surface-glaze|");
    expect(glaze.customProgramCacheKey()).toMatch(/\|live-[0-9a-z]+$/);
    for (const [name, ud] of [
      ["baked.gate_A0.surface.metal", { sectSurface: "metal" }],
      ["baked.gate_A0", { sectSurface: "iron" }],
    ] as const) {
      const mat = baked(name, ud);
      setMaterialLive(mat, { atlas: "gate_A0", cls: liveClassOfMaterial(mat) });
      expect(liveClassOfMaterial(mat), name).toBe("metal");
      const fs = compile(mat).fragmentShader;
      // Lit live all the same, and its reflection from the face's own normal.
      expect(fs, name).toContain("sectTexel = mix( sectTexel, lTex, sectLiveShare );");
      expect(fs, name).not.toContain(hook);
      expect(fs, name).not.toContain("sLn");
      expect(fs, name).toContain("vec3 sR = reflect( sV, sN );");
      expect(mat.customProgramCacheKey(), name).toContain(`|surface-${ud.sectSurface}|live-`);
    }
  });

  it("provides every live, sky and environment uniform a live shader declares", () => {
    for (const [name, ud] of names) {
      const mat = baked(name, ud);
      setMaterialLive(mat, { atlas: liveAtlasOf(name)!, cls: liveClassOfMaterial(mat) });
      const sh = compile(mat);
      const declared = [...sh.fragmentShader.matchAll(/^uniform (?:highp )?\w+ ([ut]Sect(?:Live|Env|Sky)\w*);$/gm)].map((m) => m[1]);
      expect(declared, name).toContain("tSectLiveView");
      expect(declared, name).toContain("tSectSky");
      for (const u of declared) expect(sh.uniforms[u], `${name} ${u}`).toBeDefined();
    }
  });

  it("gives each live uniform a value of the type it is declared with", () => {
    const is: Record<string, (v: unknown) => boolean> = {
      float: (v) => typeof v === "number",
      vec2: (v) => v instanceof Vector2,
      vec3: (v) => v instanceof Vector3,
      vec4: (v) => v instanceof Vector4,
      mat4: (v) => v instanceof Matrix4,
      // A compare texture on a plain sampler, or a plain one on a shadow sampler, fails to draw.
      sampler2D: (v) => v === null || (v instanceof Texture && !(v as DepthTexture).compareFunction),
      sampler2DShadow: (v) => v === null || (v instanceof DepthTexture && !!v.compareFunction),
      sampler3D: (v) => v === null || v instanceof Texture,
    };
    const check = (sh: Compiled, label: string) => {
      const declared = [...sh.fragmentShader.matchAll(/^uniform (?:highp )?(\w+) ([ut]SectLive\w*);$/gm)];
      expect(declared.map((m) => m[2]), label).toEqual(
        expect.arrayContaining([
          "uSectLiveSpec",
          "uSectLiveBump",
          "uSectLiveLift",
          "uSectLivePaint",
          "uSectLiveAmbientIrr",
          "uSectLiveVis",
          "uSectLiveGraze",
          "uSectLiveClose",
          "uSectLiveDetail",
          "uSectLiveBakeGain",
          "uSectLiveBakePost",
          "uSectLiveCaps",
          "uSectLiveTiles",
          "tSectLiveSunShadow",
          "tSectLiveShadowB",
          "tSectLiveView",
        ]),
      );
      for (const [, type, name] of declared) {
        expect(is[type], `${label} ${name}: ${type}`).toBeDefined();
        expect(is[type]((sh.uniforms[name] as { value: unknown }).value), `${label} ${name}: ${type}`).toBe(true);
      }
      return declared;
    };
    const more: [string, Record<string, unknown>][] = [
      ["baked.gate_A0.detail.tiles", { detail: "tiles" }],
      ["baked.gate_A0", { sectSway: true }],
    ];
    for (const [name, ud] of [...names, ...more]) {
      const mat = baked(name, ud);
      setMaterialLive(mat, { atlas: liveAtlasOf(name)!, cls: liveClassOfMaterial(mat) });
      check(compile(mat), name);
    }
    // And with the shadow maps in place, as live.tsx sets them: the compare map on the shadow
    // sampler, the coarse plain one on the plain sampler.
    const mat = baked("baked.gate_A0");
    setMaterialLive(mat, { atlas: "gate_A0", cls: "default" });
    const sh = compile(mat);
    const key = new LiveShadowMap(64, 4);
    const sun = new LiveShadowMap(64, 4);
    try {
      SECT_LIVE.tSectLiveShadow.value = key.texture;
      SECT_LIVE.tSectLiveShadowB.value = key.coarseTexture;
      SECT_LIVE.tSectLiveSunShadow.value = sun.texture;
      SECT_LIVE.tSectLiveSunShadowB.value = sun.coarseTexture;
      const declared = check(sh, "with maps");
      expect(declared.filter((m) => m[1] === "sampler2DShadow").map((m) => m[2])).toEqual(["tSectLiveShadow", "tSectLiveSunShadow"]);
      // Swapped, they would not draw.
      expect(is.sampler2DShadow(key.coarseTexture)).toBe(false);
      expect(is.sampler2D(key.texture)).toBe(false);
    } finally {
      SECT_LIVE.tSectLiveShadow.value = null;
      SECT_LIVE.tSectLiveShadowB.value = null;
      SECT_LIVE.tSectLiveSunShadow.value = null;
      SECT_LIVE.tSectLiveSunShadowB.value = null;
      key.dispose();
      sun.dispose();
    }
  });

  it("rolls the normal across the courses only on a live roof of the tiles detail class", () => {
    const plainBlock = liveApplyGlsl();
    const tilesBlock = liveApplyGlsl(true);
    const lit = (name: string, ud: Record<string, unknown>) => {
      const mat = baked(name, ud);
      setMaterialLive(mat, { atlas: liveAtlasOf(name)!, cls: liveClassOfMaterial(mat) });
      return { mat, sh: compile(mat) };
    };
    const roof = lit("baked.gate_A0.detail.tiles", { detail: "tiles" });
    expect(liveClassOfMaterial(roof.mat)).toBe("tiles");
    // A glazed roof shines as glaze but its courses roll all the same.
    const glazed = lit("baked.gate_A1.detail.tiles.surface.glaze", { detail: "tiles", sectSurface: "glaze" });
    expect(liveClassOfMaterial(glazed.mat)).toBe("glaze");
    for (const { mat, sh } of [roof, glazed]) {
      expect(sh.fragmentShader, mat.name).toContain(tilesBlock);
      expect(sh.fragmentShader.split("uSectLiveTiles.x").length - 1, mat.name).toBe(1);
      // The tile coordinates the roll reads come from the vertex shader.
      expect(sh.vertexShader, mat.name).toContain("vSectUv1 = vec2( uv1.x, 1.0 - uv1.y );");
      expect(sh.fragmentShader, mat.name).toMatch(/varying vec2 vSectUv1;/);
      expect(sh.fragmentShader.indexOf("varying vec2 vSectUv1;"), mat.name).toBeLessThan(sh.fragmentShader.indexOf(tilesBlock));
      expect(sh.uniforms.uSectLiveTiles, mat.name).toBe(SECT_LIVE.uSectLiveTiles);
    }
    // Every other class: the plain block, no roll, and a program of its own.
    for (const [name, ud] of names.filter(([, u]) => u.detail !== "tiles")) {
      const { mat, sh } = lit(name, ud);
      expect(sh.fragmentShader, name).toContain(plainBlock);
      expect(sh.fragmentShader, name).not.toContain("uSectLiveTiles.x");
      expect(mat.customProgramCacheKey(), name).not.toBe(roof.mat.customProgramCacheKey());
    }
    // A roof not lit live has no live code at all.
    expect(roof.mat.customProgramCacheKey()).toMatch(/\|live-[0-9a-z]+$/);
    setMaterialLive(roof.mat, null);
    expect(compile(roof.mat).fragmentShader).not.toMatch(/sectLive|uSectLiveTiles/);
    expect(roof.mat.customProgramCacheKey()).not.toContain("live");
  });

  it("gives a live paving material the slabs' relief, from the page's one uniform", () => {
    const block = liveApplyGlsl(false, true);
    const uniforms = createDetailUniforms(new Texture(), { time: { value: 0 }, sunDir: new Vector3(0, 0.12, -1).normalize(), rockOctaves: 1 });
    const mat = new MeshBasicMaterial({ map: new Texture() });
    mat.name = "baked.gate_A0.detail.paving";
    mat.userData = { baked: true, detail: "paving" };
    prepareBakedMaterial(mat, uniforms);
    setMaterialLive(mat, { atlas: "gate_A0", cls: liveClassOfMaterial(mat) });
    const sh = compile(mat);
    const fs = sh.fragmentShader;
    expect(fs.split(block).length - 1).toBe(1);
    expect(fs.split("uSectLivePaving.x").length - 1).toBe(1);
    // The slab helpers it calls (detail.ts pavingGlsl) and the slab coordinates are there before it.
    for (const s of ["vec2 sectSlab( vec2 q, out vec2 e )", "vec2 sectSlabPos( vec2 q, vec2 id )", "vec3 sectHash3( vec2 p )", "varying vec2 vSectUv1;"]) {
      expect(fs.indexOf(s), s).toBeGreaterThan(0);
      expect(fs.indexOf(s), s).toBeLessThan(fs.indexOf(block));
    }
    expect(sh.vertexShader).toContain("vSectUv1 = vec2( uv1.x, 1.0 - uv1.y );");
    expect(sh.uniforms.uSectLivePaving).toBe(SECT_LIVE.uSectLivePaving);
    // Until live.tsx sets it, no lean and no bevel, with a bevel width above 0.
    expect(SECT_LIVE.uSectLivePaving.value).toBeInstanceOf(Vector3);
    expect(SECT_LIVE.uSectLivePaving.value.x).toBe(0);
    expect(SECT_LIVE.uSectLivePaving.value.z).toBe(0);
    expect(SECT_LIVE.uSectLivePaving.value.y).toBeGreaterThan(0);
    // Without the paving detail (no detail uniforms: the low tier) there are no slabs to lean: the plain block.
    const low = baked("baked.gate_A0.detail.paving", { detail: "paving" });
    setMaterialLive(low, { atlas: "gate_A0", cls: liveClassOfMaterial(low) });
    const lfs = compile(low).fragmentShader;
    expect(lfs).toContain(liveApplyGlsl());
    expect(lfs).not.toContain("uSectLivePaving.x");
    // Not lit live: no relief either.
    setMaterialLive(mat, null);
    expect(compile(mat).fragmentShader).not.toContain("uSectLivePaving");
  });

  it("gives a live material with no reflective class the sky sheen and the sky", () => {
    const sheen = liveSheenGlsl();
    for (const [name, ud] of names.filter(([, u]) => !u.sectSurface)) {
      const mat = baked(name, ud);
      // Not lit live: no sky at all.
      const plain = compile(mat);
      expect(plain.fragmentShader, name).not.toContain(ENV_GLSL);
      expect(Object.keys(plain.uniforms).some((u) => u in SECT_ENV), name).toBe(false);
      setMaterialLive(mat, { atlas: liveAtlasOf(name)!, cls: liveClassOfMaterial(mat) });
      const sh = compile(mat);
      const fs = sh.fragmentShader;
      expect(fs.split(sheen).length - 1, name).toBe(1);
      expect(fs.split(ENV_GLSL).length - 1, name).toBe(1);
      // The sky before main; the sheen after the live texel and the light, before the output.
      const at = [ENV_GLSL, "void main()", "sectTexel = mix( sectTexel, lTex, sectLiveShare );", "vec3 outgoingLight", sheen, "#include <opaque_fragment>"].map(
        (x) => fs.indexOf(x),
      );
      expect(at.every((i) => i >= 0), name).toBe(true);
      expect([...at].sort((a, b) => a - b), name).toEqual(at);
      expect(fs, name).not.toContain("vec3 sLn");
      for (const u of Object.keys(SECT_ENV) as (keyof typeof SECT_ENV)[]) expect(sh.uniforms[u], `${name} ${u}`).toBe(SECT_ENV[u]);
    }
  });

  it("gives a live metal or glaze its reflective class's code and no sheen", () => {
    const sheen = liveSheenGlsl();
    const kinds: [string, Record<string, unknown>, "metal" | "glaze" | "iron"][] = [
      ["baked.gate_A0.surface.metal", { sectSurface: "metal" }, "metal"],
      ["baked.gate_A1.detail.tiles.surface.glaze", { detail: "tiles", sectSurface: "glaze" }, "glaze"],
      ["baked.gate_A0", { sectSurface: "iron" }, "iron"],
    ];
    for (const [name, ud, kind] of kinds) {
      const mat = baked(name, ud);
      setMaterialLive(mat, { atlas: liveAtlasOf(name)!, cls: liveClassOfMaterial(mat) });
      const fs = compile(mat).fragmentShader;
      const surface = surfaceGlsl(kind, SECT_LOOK.surfaces, true);
      expect(fs, name).toContain(surface);
      expect(fs.indexOf(surface), name).toBeLessThan(fs.indexOf("#include <opaque_fragment>"));
      expect(fs, name).not.toContain(sheen);
      expect(fs.split(ENV_GLSL).length - 1, name).toBe(1);
    }
  });

  it("lights a material that sways as cloth, with the cloth class's own uniforms", () => {
    const flag = baked("baked.gate_A0", { sectSway: true });
    const banner = baked("baked.gate_A1.detail.paving", { detail: "paving", sectSway: true });
    expect(liveClassOfMaterial(flag)).toBe("cloth");
    expect(liveClassOfMaterial(banner)).toBe("cloth");
    // Only the flag idle.ts sets (addSway), and only when true.
    expect(liveClassOfMaterial(baked("baked.gate_A1.detail.paving", { detail: "paving" }))).toBe("paving");
    expect(liveClassOfMaterial(baked("baked.gate_A0", { sectSway: 1 }))).toBe("default");
    expect(liveClassOfMaterial(baked("baked.gate_A0", { sectSway: "true" }))).toBe("default");
    const cloth = liveClassUniforms("cloth");
    expect(liveClassUniforms("cloth")).toBe(cloth);
    for (const mat of [flag, banner]) {
      setMaterialLive(mat, { atlas: liveAtlasOf(mat.name)!, cls: liveClassOfMaterial(mat) });
      const sh = compile(mat);
      expect(sh.fragmentShader, mat.name).toContain("uniform float uSectLiveLift;");
      // The lift moves where the shadow lookups start; the face normal is never flipped toward the lamps.
      expect(sh.fragmentShader, mat.name).toContain("sectLiveShadow( vSectWorld + uSectLiveKeyDir * uSectLiveLift, lNg )");
      expect(sh.fragmentShader, mat.name).not.toMatch(/lNg = - lNg/);
      expect(sh.uniforms.uSectLiveLift, mat.name).toBe(cloth.uSectLiveLift);
      expect(sh.uniforms.uSectLiveSpec, mat.name).toBe(cloth.uSectLiveSpec);
      expect(sh.uniforms.uSectLiveBump, mat.name).toBe(cloth.uSectLiveBump);
    }
    // Each class has its own lift, so only cloth's is moved off 0 (live.tsx from LIVE_LOOK.classes).
    const lifts = LIVE_CLASSES.map((c) => liveClassUniforms(c).uSectLiveLift);
    expect(new Set(lifts).size).toBe(LIVE_CLASSES.length);
    for (const c of LIVE_CLASSES) expect(typeof liveClassUniforms(c).uSectLiveLift.value, c).toBe("number");
  });

  it("keeps the bake's soft shadow off until a stop's index turns it on", () => {
    // live.tsx applyLook sets it from live.ts liveValues(...).vis.
    expect(SECT_LIVE.uSectLiveVis.value).toBeInstanceOf(Vector4);
    expect(SECT_LIVE.uSectLiveVis.value.x).toBe(0);
    const mat = baked("baked.gate_A0");
    setMaterialLive(mat, { atlas: "gate_A0", cls: "default" });
    const sh = compile(mat);
    expect(sh.fragmentShader).toContain("uniform vec4 uSectLiveVis;");
    expect(sh.uniforms.uSectLiveVis).toBe(SECT_LIVE.uSectLiveVis);
  });

  it("shares the graze, close, detail, the bake's gain and post and the caps as the page's own objects, the detail off until a stop's index turns it on", () => {
    // live.tsx applyLook sets them from live.ts liveValues(...).
    const want: [keyof typeof SECT_LIVE, string, (v: unknown) => boolean][] = [
      ["uSectLiveGraze", "vec2", (v) => v instanceof Vector2],
      ["uSectLiveClose", "vec3", (v) => v instanceof Vector3],
      ["uSectLiveDetail", "vec4", (v) => v instanceof Vector4],
      ["uSectLiveBakeGain", "vec3", (v) => v instanceof Vector3],
      ["uSectLiveBakePost", "vec3", (v) => v instanceof Vector3],
      ["uSectLiveCaps", "vec2", (v) => v instanceof Vector2],
    ];
    expect(SECT_LIVE.uSectLiveDetail.value.x).toBe(0);
    for (const [name, ud] of names) {
      const mat = baked(name, ud);
      setMaterialLive(mat, { atlas: liveAtlasOf(name)!, cls: liveClassOfMaterial(mat) });
      const sh = compile(mat);
      for (const [u, type, is] of want) {
        expect(sh.fragmentShader, `${name} ${u}`).toContain(`uniform ${type} ${u};`);
        expect(sh.uniforms[u], `${name} ${u}`).toBe(SECT_LIVE[u]);
        expect(is(SECT_LIVE[u].value), u).toBe(true);
      }
    }
  });

  it("tells which materials can be lit live", () => {
    expect(isLiveCandidate(baked("baked.gate_A0"))).toBe(true);
    expect(isLiveCandidate(baked("baked.gate_A1.detail.tiles.surface.glaze", { detail: "tiles", sectSurface: "glaze" }))).toBe(true);
    expect(isLiveCandidate(baked("baked.vc"))).toBe(false);
    expect(isLiveCandidate(baked("baked.vc.surface.metal", { sectSurface: "metal" }))).toBe(false);
    expect(isLiveCandidate(baked("baked.gate_A0.glow.rune_cyan", { glow: 2 }))).toBe(false);
    expect(isLiveCandidate(baked("baked.gate_A0", {}, false))).toBe(false);
    expect(isLiveCandidate(baked("trees.mesh.gate"))).toBe(false);
    const glowCopy = baked("baked.gate_A0");
    glowCopy.color.multiplyScalar(1.8);
    expect(isLiveCandidate(glowCopy)).toBe(false);
    const cut = baked("baked.gate_A0");
    cut.alphaTest = 0.5;
    expect(isLiveCandidate(cut)).toBe(false);
    const notBaked = new MeshBasicMaterial({ map: new Texture() });
    notBaked.name = "baked.gate_A0";
    expect(isLiveCandidate(notBaked)).toBe(false);
  });

  it("never lights a material without its atlas map, a tree card or water, even when bound", () => {
    const noMap = baked("baked.gate_A0", {}, false);
    const card = new MeshBasicMaterial({ map: new Texture(), alphaTest: 0.5 });
    card.name = "trees.cards.gate";
    card.userData = { baked: true };
    prepareBakedMaterial(card);
    const pond = new MeshBasicMaterial({ map: new Texture() });
    pond.name = "baked.gate_A0";
    pond.userData = { baked: true };
    patchMaterial(pond, { lit: false, exposure: 1, water: createWaterUniforms({ level: 0, disc: null }) });
    for (const mat of [noMap, card, pond]) {
      const key = mat.customProgramCacheKey();
      const fs = compile(mat).fragmentShader;
      setMaterialLive(mat, { atlas: "gate_A0", cls: "default" });
      expect(mat.customProgramCacheKey(), mat.name).toBe(key);
      const bound = compile(mat).fragmentShader;
      expect(bound, mat.name).not.toContain("SECT_LIVE");
      expect(bound, mat.name).toBe(fs);
    }
  });
});
