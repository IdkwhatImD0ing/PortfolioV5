import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { BloomEffect, type Effect, VignetteEffect } from "postprocessing";
import { PerspectiveCamera, Scene, Vector3 } from "three";
import { fogConstantsFromMeta } from "@/lib/sect/glsl";
import { SECT_LOOK } from "@/lib/sect/look";
import { ATMOS } from "@/lib/sect/post";
import type { SectMeta } from "@/lib/sect/types";
import { BLOOM, DitherEffect, EdgeSmoothEffect, HueClipEffect, SectBloomEffect, SunHazeEffect } from "./effects";
import { ContactShadeEffect } from "./post/ao";
import { CloudShadowEffect, glowPrefilter, HoldFocusEffect, LUMINANCE_LINE } from "./post/atmos";
import { FinishEffect } from "./post/finish";
import { SunShaftsEffect } from "./post/shafts";

describe("DitherEffect", () => {
  it("adds the shared triangular noise in sRGB space, scaled to 8-bit steps", () => {
    const e = new DitherEffect(SECT_LOOK.dither);
    const fs = e.getFragmentShader();
    expect(fs).toContain("void mainImage( const in vec4 inputColor, const in vec2 uv, out vec4 outputColor )");
    expect(fs).toContain("sectSrgbEncode( inputColor.rgb ) + sectDitherNoise( gl_FragCoord.xy ) * ( uAmount / 255.0 )");
    expect(fs).toContain("sectSrgbDecode( s )");
    expect(e.uniforms.get("uAmount")?.value).toBe(SECT_LOOK.dither);
  });

  it("dithers by about one step", () => {
    expect(SECT_LOOK.dither).toBeGreaterThan(0.5);
    expect(SECT_LOOK.dither).toBeLessThanOrEqual(1.5);
  });
});

describe("bloom", () => {
  it("keeps the glows-only threshold (a softer one shrank the hotspot halos)", () => {
    expect(BLOOM.luminanceThreshold).toBe(1);
    expect(BLOOM.intensity).toBe(ATMOS.bloom.intensity);
  });

  it("reads the threshold toward the brightest channel, so saturated glows bloom", () => {
    const bloom = new BloomEffect({ mipmapBlur: true, ...BLOOM });
    expect(bloom.luminanceMaterial.fragmentShader).toContain(LUMINANCE_LINE);
    expect(glowPrefilter(bloom)).toBe(true);
    const fs = bloom.luminanceMaterial.fragmentShader;
    expect(fs).not.toContain(LUMINANCE_LINE);
    expect(fs).toContain("float l=mix(luminance(texel.rgb),max(max(texel.r,texel.g),texel.b),0.6");
    // A second call finds no line to swap: never a double mix.
    expect(glowPrefilter(bloom)).toBe(false);
    bloom.dispose();
  });
});

describe("createPipeline", () => {
  // The composer needs WebGL, so the order is read from the source.
  const dir = path.dirname(fileURLToPath(import.meta.url));
  const src = readFileSync(path.join(dir, "effects.ts"), "utf8").replace(/\r\n/g, "\n");
  const body = src.slice(src.indexOf("export function createPipeline("), src.indexOf("composer.addPass(new EffectPass(camera, ...effects));"));

  it("pushes the effects in order: contact shade first, shafts before bloom, the finish between vignette and hue clip, dither last", () => {
    expect(body.length).toBeGreaterThan(0);
    const order = [
      "effects.push(ao);",
      "effects.push(holdFocus);",
      "effects.push(cloudShadow);",
      "effects.push(shafts);",
      "effects.push(bloom);",
      // The vignette is kept in a variable: the look sets its darkness at run time (setLook).
      "effects.push(sunHaze, vignette);",
      "effects.push(finish);",
      "effects.push(new HueClipEffect());",
      "effects.push(new DitherEffect(dither));",
    ].map((s) => body.indexOf(s));
    expect(order.every((i) => i >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
    // Nothing is pushed before the contact shade or after the dither.
    const pushes = [...body.matchAll(/effects\.push\(/g)].map((m) => m.index);
    expect(pushes[0]).toBe(order[0]);
    expect(pushes[pushes.length - 1]).toBe(order[order.length - 1]);
  });
});

describe("the order the effect pass runs them in", () => {
  // postprocessing's EffectPass sorts its effects by attribute before it merges them into one shader:
  // convolution first, then the ones that read depth, then the rest. So the order createPipeline
  // pushes them in only holds inside each of those groups, and an effect with the wrong attribute
  // runs in the wrong place however it is pushed (the finish once ran first of all, FXAA after the
  // cloud shade it then wiped along every edge).
  const SORT_LINE = "this.effects = effects.sort((a, b) => b.attributes - a.attributes);";
  const dir = path.dirname(fileURLToPath(import.meta.url));
  const run = (list: Effect[]) => [...list].sort((a, b) => b.getAttributes() - a.getAttributes()).map((e) => e.name);
  const meta = {
    fog: { color: "#84889e", density: 0.0003, baseY: 100, falloff: 220 },
    sun: { direction: [-0.94397, 0.12187, 0.30671] },
    sky: { horizonSun: "#ffc890" },
    cloudSea: { fogTopY: 0 },
  } as unknown as SectMeta;
  const build = (o: { high: boolean }) => {
    const camera = new PerspectiveCamera();
    const fog = fogConstantsFromMeta(meta);
    const list: Effect[] = [];
    if (o.high) list.push(new ContactShadeEffect(camera), new HoldFocusEffect());
    list.push(new CloudShadowEffect(camera, fog));
    if (o.high) list.push(new SunShaftsEffect(new Scene(), camera, fog));
    list.push(
      new SectBloomEffect({ mipmapBlur: true, ...BLOOM }),
      new SunHazeEffect(new Vector3(-1, 0.1, 0.3), "#ffc88a", 0.2),
      new VignetteEffect({ offset: 0.3, darkness: 0.5 }),
      new FinishEffect({ sharpen: o.high }),
      new HueClipEffect(),
      new DitherEffect(1),
    );
    if (!o.high) list.unshift(new EdgeSmoothEffect());
    return list;
  };

  it("is still the library's own sort by attribute (a library upgrade that changes it must be looked at)", () => {
    const lib = readFileSync(path.join(dir, "../../../../node_modules/postprocessing/build/index.js"), "utf8");
    expect(lib).toContain(SORT_LINE);
  });

  it("on High, runs every effect where createPipeline puts it: the finish last before the hue clip", () => {
    const list = build({ high: true });
    expect(run(list)).toEqual(list.map((e) => e.name));
    const names = run(list);
    expect(names.indexOf("SectFinishEffect")).toBe(names.indexOf("SectHueClipEffect") - 1);
    expect(names[0]).toBe("SectContactShadeEffect");
    for (const e of list) e.dispose();
  });

  it("on Medium, runs FXAA before everything else, the cloud shade too", () => {
    const list = build({ high: false });
    const names = run(list);
    expect(names[0]).toBe("FXAAEffect");
    expect(names.slice(1)).toEqual(list.slice(1).map((e) => e.name));
    expect(names.indexOf("SectCloudShadowEffect")).toBe(1);
    for (const e of list) e.dispose();
  });
});
