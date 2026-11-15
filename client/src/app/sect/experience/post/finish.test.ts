import { describe, expect, it } from "vitest";
import { EffectAttribute } from "postprocessing";
import type { Vector3 } from "three";
import { glslFloat } from "@/lib/sect/glsl";
import { LUX } from "@/lib/sect/lux";
import { FinishEffect } from "./finish";

const finishOf = (e: FinishEffect) => (e.uniforms.get("uFinish")!.value as Vector3).toArray();
const seedOf = (e: FinishEffect) => e.uniforms.get("uFinishSeed")!.value as number;

describe("FinishEffect shader", () => {
  it("leaves at its first test while off, before it reads the frame", () => {
    const e = new FinishEffect({ sharpen: true });
    const fs = e.getFragmentShader();
    const off = fs.indexOf("if ( uFinish.x <= 0.0 && uFinish.y <= 0.0 && uFinish.z <= 0.0 ) return;");
    expect(off).toBeGreaterThan(0);
    expect(fs.indexOf("texture2D( inputBuffer")).toBeGreaterThan(off);
    // The sharpening reads the frame only when it is on.
    expect(fs.indexOf("if ( uFinish.y > 0.0 ) {")).toBeLessThan(fs.indexOf("texture2D( inputBuffer"));
    e.dispose();
  });

  it("leaves glows to the hue clip, and grains only what the toe works on", () => {
    const e = new FinishEffect({ sharpen: false });
    const fs = e.getFragmentShader();
    const toe = fs.indexOf("if ( l < 1.0 ) {");
    expect(toe).toBeGreaterThan(0);
    expect(fs.indexOf("v * ( 1.0 - uFinish.x * pow( 1.0 - v, FINISH_TOE_POWER ) )")).toBeGreaterThan(toe);
    expect(fs.indexOf("if ( uFinish.z > 0.0 ) {")).toBeGreaterThan(toe);
    // Sharpening stays out of glows (bloom's business) and is capped.
    expect(fs).toContain("1.0 - smoothstep( 0.9, 1.3, dot( raw, luma ) )");
    expect(fs).toContain("clamp( edge * uFinish.y, - FINISH_SHARPEN_MAX, FINISH_SHARPEN_MAX )");
    e.dispose();
  });

  it("takes its art direction from LUX", () => {
    const e = new FinishEffect({ sharpen: true });
    const fs = e.getFragmentShader();
    const f = LUX.finish;
    expect(fs).toContain(`#define FINISH_TOE_POWER ${glslFloat(f.toePower)}`);
    expect(fs).toContain(`#define FINISH_SATURATION ${glslFloat(f.saturation)}`);
    expect(fs).toContain(`#define FINISH_SHARPEN_MAX ${glslFloat(f.sharpenMax)}`);
    e.dispose();
  });

  it("carries no attribute, sharpening or not, so the effect pass does not sort it to the front", () => {
    // The pass sorts by attribute (convolution, then depth, then none): as a convolution effect the
    // toe and the grain ran before the contact shade, the bloom and the vignette.
    const sharp = new FinishEffect({ sharpen: true });
    const plain = new FinishEffect({ sharpen: false });
    expect(sharp.getAttributes()).toBe(EffectAttribute.NONE);
    expect(plain.getAttributes()).toBe(EffectAttribute.NONE);
    sharp.dispose();
    plain.dispose();
  });
});

describe("FinishEffect switches", () => {
  it("starts with LUX's toe, sharpening (High only) and grain", () => {
    const f = LUX.finish;
    const sharp = new FinishEffect({ sharpen: true });
    const plain = new FinishEffect({ sharpen: false });
    expect(finishOf(sharp)).toEqual([f.toe, f.sharpen, f.grain]);
    expect(finishOf(plain)).toEqual([f.toe, 0, f.grain]);
    sharp.dispose();
    plain.dispose();
  });

  it("zeroes everything while suspended and restores LUX's values after, sharpening only where built", () => {
    const f = LUX.finish;
    for (const sharpen of [true, false]) {
      const e = new FinishEffect({ sharpen });
      e.suspended = true;
      expect(e.suspended).toBe(true);
      expect(finishOf(e)).toEqual([0, 0, 0]);
      e.suspended = false;
      expect(finishOf(e)).toEqual([f.toe, sharpen ? f.sharpen : 0, f.grain]);
      e.dispose();
    }
  });

  it("moves the grain once per drawn frame over a short cycle, and holds it still when asked", () => {
    const e = new FinishEffect({ sharpen: false });
    const start = seedOf(e);
    const seen = new Set<number>();
    for (let i = 0; i < 64; i++) {
      e.update();
      seen.add(seedOf(e));
    }
    // A cycle of 64 patterns, back where it began.
    expect(seen.size).toBe(64);
    expect(seedOf(e)).toBe(start);
    e.update();
    const held = seedOf(e);
    e.still = true;
    for (let i = 0; i < 5; i++) e.update();
    expect(seedOf(e)).toBe(held);
    e.dispose();
  });
});
