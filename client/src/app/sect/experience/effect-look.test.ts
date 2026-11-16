import { AdditiveBlending, Color, type ShaderMaterial, Vector3 } from "three";
import { describe, expect, it } from "vitest";
import { fogConstantsFromMeta, SCREEN_GRADE_GLSL } from "@/lib/sect/glsl";
import { parseMeta } from "@/lib/sect/parse";
import { cardMaterial, emberMaterial, lightMaterial, mouthMaterial, sourceUniforms } from "./flames";
import { craneMaterial, fireMaterial, petalMaterial, smokeMaterial } from "./fx";
import { birdMaterial, butterflyMaterial, moteMaterial } from "./life";
import { createBeamMaterial, createDomeMaterial, createMistMaterial, createShaftMaterial, SECT_HAZE_COLOR, SECT_LOOK_GPU, setLookHaze } from "./materials";
import { puffMaterial, skirtMaterial, sprayMaterial } from "./waterfall-fx";

const fog = fogConstantsFromMeta(parseMeta({}));
const HAZE = "#c8ada0";

/** Every effect material (the fires, the decoration, the life, the waterfall foot, the overlay lights). */
function effects(): ShaderMaterial[] {
  const src = sourceUniforms([]);
  const time = { value: 0 };
  return [
    mouthMaterial(src, fog, HAZE, 2),
    cardMaterial(src, fog),
    emberMaterial(src, fog),
    lightMaterial(src),
    petalMaterial(new Vector3(0, 1, 0)),
    craneMaterial(fog, HAZE),
    fireMaterial(),
    smokeMaterial(),
    birdMaterial(fog, HAZE),
    moteMaterial(fog),
    butterflyMaterial(fog, HAZE),
    skirtMaterial(time, 2, [0, 1, 0]),
    sprayMaterial(fog, HAZE, "#fff0d0", time),
    puffMaterial(fog, HAZE, time),
    createMistMaterial(fog, HAZE, time),
    createBeamMaterial(fog, HAZE, time),
    createShaftMaterial(fog, time, { value: 1 }),
    createDomeMaterial(fog, "#ffd9a0", time),
  ];
}

/** Whether a material's shaders read the look's array: written in, or through three's fog chunk (glsl.ts fogChunks declares it). */
function readsLook(m: ShaderMaterial): boolean {
  return /uniform vec4 uSectLook\[/.test(m.vertexShader + m.fragmentShader) || (m.fog && m.fragmentShader.includes("#include <fog_pars_fragment>"));
}

/** The lights that only add (or, the blaze light, multiply) onto what is already drawn. */
const ADDS = ["sect.fire.flames", "sect.fire.embers", "sect.fire.light", "sect.forgefire", "sect.life.motes", "sect.beam", "sect.shaft", "sect.dome"];

describe("the look along the flight reaches every effect", () => {
  it("hands each effect that reads the look's array the shared array itself, not a copy", () => {
    const readers: string[] = [];
    for (const m of effects()) {
      if (!readsLook(m)) continue;
      readers.push(m.name);
      // An array the page never filled reads as every switch off: today's dusk for good.
      expect(m.uniforms.uSectLook, m.name).toBe(SECT_LOOK_GPU.uSectLook);
    }
    // Only the blaze light (it reads the scene's depth, not the air) and the forge fire read nothing.
    expect(readers.sort()).toEqual(
      [
        "sect.beam",
        "sect.cranes",
        "sect.dome",
        "sect.fire.embers",
        "sect.fire.flames",
        "sect.fire.mouths",
        "sect.incense",
        "sect.life.birds",
        "sect.life.butterflies",
        "sect.life.motes",
        "sect.mist",
        "sect.petals",
        "sect.shaft",
        "sect.waterfall.mist",
        "sect.waterfall.skirt",
        "sect.waterfall.spray",
      ].sort(),
    );
  });

  it("fades every effect with a haze colour to the shared one, the land's", () => {
    const hazed: string[] = [];
    for (const m of effects()) {
      if (!("uFogColor" in m.uniforms)) continue;
      hazed.push(m.name);
      expect(m.uniforms.uFogColor, m.name).toBe(SECT_HAZE_COLOR);
      expect(m.vertexShader + m.fragmentShader, m.name).toContain("uniform vec3 uFogColor;");
    }
    expect(hazed.sort()).toEqual(
      ["sect.beam", "sect.cranes", "sect.fire.mouths", "sect.life.birds", "sect.life.butterflies", "sect.mist", "sect.waterfall.mist", "sect.waterfall.spray"].sort(),
    );
  });

  it("gives what covers the world the look's frame grade on the Low tier, just before its encode", () => {
    for (const m of effects()) {
      const fs = m.fragmentShader;
      if (ADDS.includes(m.name) || m.fog) continue;
      // The grade goes on in linear, then three encodes for the sRGB screen.
      expect(fs, m.name).toContain(`${SCREEN_GRADE_GLSL}\n  #include <colorspace_fragment>`);
      // sectLookGrade (and the array) are declared before main, from the fog library or SCREEN_GRADE_PARS.
      expect(fs.indexOf("vec3 sectLookGrade("), m.name).toBeGreaterThan(0);
      expect(fs.indexOf("vec3 sectLookGrade("), m.name).toBeLessThan(fs.indexOf("void main()"));
      expect(fs.indexOf("uniform vec4 uSectLook["), m.name).toBeLessThan(fs.indexOf("vec3 sectLookGrade("));
    }
    // The foam skirt is fogged by three's chunk, which grades there itself.
    const skirt = effects().find((m) => m.name === "sect.waterfall.skirt");
    expect(skirt?.fog).toBe(true);
    expect(skirt?.fragmentShader).toContain("#include <fog_fragment>");
  });

  it("adds the lights as linear light, never encoded or graded on their own (the Low tier's white blots)", () => {
    const lights = effects().filter((m) => ADDS.includes(m.name));
    expect(lights.map((m) => m.name).sort()).toEqual([...ADDS].sort());
    for (const m of lights) {
      expect(m.fragmentShader, m.name).not.toContain("colorspace_fragment");
      expect(m.fragmentShader, m.name).not.toContain(SCREEN_GRADE_GLSL);
    }
    for (const name of ["sect.fire.embers", "sect.forgefire", "sect.life.motes", "sect.beam", "sect.shaft", "sect.dome"]) {
      expect(lights.find((m) => m.name === name)?.blending, name).toBe(AdditiveBlending);
    }
  });

  it("keeps the look's haze when an effect is made after the look set it", () => {
    const crane = craneMaterial(fog, HAZE);
    // Before the look sets it, the shared haze starts at the colour the effect was given.
    expect(SECT_HAZE_COLOR.value.equals(new Color(HAZE))).toBe(true);
    const night = new Color("#2f4068");
    setLookHaze(night);
    expect(SECT_HAZE_COLOR.value.equals(night)).toBe(true);
    // A flock streaming in later does not put today's haze back.
    birdMaterial(fog, HAZE);
    sprayMaterial(fog, HAZE, "#fff0d0", { value: 0 });
    expect(SECT_HAZE_COLOR.value.equals(night)).toBe(true);
    expect((crane.uniforms.uFogColor.value as Color).equals(night)).toBe(true);
    // A hex string sets it too (linear, as every Color made from one).
    setLookHaze("#26365e");
    expect(SECT_HAZE_COLOR.value.equals(new Color("#26365e"))).toBe(true);
  });
});
