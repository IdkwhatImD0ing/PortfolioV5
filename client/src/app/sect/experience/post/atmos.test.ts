import { describe, expect, it } from "vitest";
import { PerspectiveCamera, Vector4 } from "three";
import { fogConstantsFromMeta } from "@/lib/sect/glsl";
import type { SectMeta } from "@/lib/sect/types";
import { CloudShadowEffect, HoldFocusEffect } from "./atmos";

const meta = {
  fog: { color: "#84889e", density: 0.0003, baseY: 100, falloff: 220 },
  sun: { direction: [-0.94397, 0.12187, 0.30671] },
  sky: { horizonSun: "#ffc890" },
  cloudSea: { fogTopY: 0 },
} as unknown as SectMeta;

describe("CloudShadowEffect", () => {
  it("reads depth, follows the sun to the deck and spares the sky, glows and the hazed distance", () => {
    const e = new CloudShadowEffect(new PerspectiveCamera(), fogConstantsFromMeta(meta));
    const fs = e.getFragmentShader();
    expect(fs).toContain("const in float depth");
    expect(fs).toContain("if ( depth >= 0.999999 || uStrength <= 0.0 ) return;");
    expect(fs).toContain("SECT_SUN_DIR.xz * ( ( CS_DECK_Y - wp.y ) / max( SECT_SUN_DIR.y, 0.02 ) )");
    expect(fs).toContain("1.0 - smoothstep( CS_GLOW_LO, CS_GLOW_HI, l )");
    expect(fs).toContain("exp( - sectHazeDepth( uCamPos.y, rd.y, t ) - sectCloudDepth( uCamPos.y, rd.y, t ) )");
    e.dispose();
  });

  it("drifts with time unless frozen, and keeps the subject out of shade", () => {
    const e = new CloudShadowEffect(new PerspectiveCamera(), fogConstantsFromMeta(meta));
    const update = (dt: number) => e.update(null as never, null as never, dt);
    update(0.05);
    expect(e.elapsed).toBeCloseTo(0.05);
    e.frozen = true;
    update(0.05);
    expect(e.elapsed).toBeCloseTo(0.05);
    // A huge delta (a tab back from the background) is clamped.
    e.frozen = false;
    update(30);
    expect(e.elapsed).toBeCloseTo(0.15);
    const keep = e.uniforms.get("uKeep")!.value as Vector4;
    e.keep(null, 45);
    // Never a zero-width smoothstep (undefined in GLSL).
    expect(keep.w).toBeGreaterThan(0);
    e.dispose();
  });
});

describe("HoldFocusEffect", () => {
  it("is off until a weight is set, and keeps the moon and sky crisp", () => {
    const e = new HoldFocusEffect();
    expect(e.weight).toBe(0);
    const fs = e.getFragmentShader();
    expect(fs).toContain("if ( uWeight <= 0.0 || depth >= 0.999999 ) return;");
    expect(fs).toContain("1.0 - smoothstep( HF_CAP_LO, HF_CAP_HI, d )");
    e.dispose();
  });
});
