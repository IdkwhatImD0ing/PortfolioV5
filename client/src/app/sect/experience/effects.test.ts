import { describe, expect, it } from "vitest";
import { BloomEffect } from "postprocessing";
import { SECT_LOOK } from "@/lib/sect/look";
import { ATMOS } from "@/lib/sect/post";
import { BLOOM, DitherEffect } from "./effects";
import { glowPrefilter, LUMINANCE_LINE } from "./post/atmos";

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
