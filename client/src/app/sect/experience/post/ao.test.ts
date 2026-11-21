import { describe, expect, it } from "vitest";
import { DepthTexture, PerspectiveCamera, type ShaderMaterial, type Vector2, type Vector4, type WebGLRenderer, type WebGLRenderTarget } from "three";
import { glslFloat, glslVec3 } from "@/lib/sect/glsl";
import { aoRadiusPx, aoScale, LUX } from "@/lib/sect/lux";
import { AO_BLUR_FRAGMENT, AO_FRAGMENT, ContactShadeEffect, DEPTH_GLSL } from "./ao";

/** Records which target each fullscreen draw went to; enough for the passes, no WebGL. */
function stubRenderer() {
  const targets: (WebGLRenderTarget | null)[] = [];
  let current: WebGLRenderTarget | null = null;
  const renderer = {
    setRenderTarget(t: WebGLRenderTarget | null) {
      current = t;
    },
    render() {
      targets.push(current);
    },
  };
  return { renderer: renderer as unknown as WebGLRenderer, targets };
}

const occlusionOf = (e: ContactShadeEffect) => (e as unknown as { aoMaterial: ShaderMaterial }).aoMaterial.uniforms;

describe("ContactShadeEffect shader", () => {
  it("reads depth and leaves at its first test while off, before any texture fetch", () => {
    const e = new ContactShadeEffect(new PerspectiveCamera());
    const fs = e.getFragmentShader();
    expect(fs).toContain("const in float depth");
    const off = fs.indexOf("if ( uAoStrength <= 0.0 || depth >= 0.999999 ) return;");
    expect(off).toBeGreaterThan(0);
    expect(fs.indexOf("texture2D( tAo")).toBeGreaterThan(off);
    // Past the fade there is nothing to darken, before the upsample too.
    const fade = fs.indexOf("if ( fade <= 0.0 ) return;");
    expect(fade).toBeGreaterThan(off);
    expect(fs.indexOf("texture2D( tAo")).toBeGreaterThan(fade);
    e.dispose();
  });

  it("takes its art direction from LUX", () => {
    const e = new ContactShadeEffect(new PerspectiveCamera());
    const fs = e.getFragmentShader();
    const a = LUX.ao;
    expect(fs).toContain(`#define AO_POWER ${glslFloat(a.power)}`);
    expect(fs).toContain(`#define AO_FADE_LO ${glslFloat(a.fade[0])}`);
    expect(fs).toContain(`#define AO_FADE_HI ${glslFloat(a.fade[1])}`);
    expect(fs).toContain(`#define AO_GLOW_LO ${glslFloat(a.glow[0])}`);
    expect(fs).toContain(`#define AO_GLOW_HI ${glslFloat(a.glow[1])}`);
    expect(fs).toContain(`#define AO_TINT ${glslVec3([...a.tint])}`);
    expect(fs).toContain(`#define AO_FOLIAGE ${glslFloat(a.foliage)}`);
    e.dispose();
  });

  it("spares glows, keeps a share for foliage and fills creases back in with the same fit as aoMultiBounce", () => {
    const e = new ContactShadeEffect(new PerspectiveCamera());
    const fs = e.getFragmentShader();
    expect(fs).toContain("( 1.0 - smoothstep( AO_GLOW_LO, AO_GLOW_HI, l ) )");
    expect(fs).toContain("k *= mix( 1.0, AO_FOLIAGE, leaf );");
    // The coefficients of lib/sect/lux.ts aoMultiBounce.
    expect(fs).toContain("vec3 a = 2.0404 * alb - 0.3324;");
    expect(fs).toContain("vec3 b = - 4.7951 * alb + 0.6417;");
    expect(fs).toContain("vec3 c = 2.7552 * alb + 0.6903;");
    expect(fs).toContain("max( vec3( vis ), ( ( vis * a + b ) * vis + c ) * vis )");
    expect(fs).toContain("pow( max( 1.0 - k * ( 1.0 - min( mb, vec3( 1.0 ) ) ), 0.0 ), AO_TINT )");
    expect(fs).toContain("if ( uAoDebug > 0.5 )");
    e.dispose();
  });

  it("marches the slices and steps LUX asks for, and leaves early past the far cut or under a pixel", () => {
    expect(AO_FRAGMENT).toContain(DEPTH_GLSL);
    expect(AO_FRAGMENT).toContain(`#define AO_SLICES ${LUX.ao.slices}`);
    expect(AO_FRAGMENT).toContain(`#define AO_STEPS ${LUX.ao.steps}`);
    const far = AO_FRAGMENT.indexOf("if ( z >= uAo.w ) {");
    const small = AO_FRAGMENT.indexOf("if ( rPx < 1.25 ) {");
    const loop = AO_FRAGMENT.indexOf("for ( int s = 0; s < AO_SLICES; s ++ )");
    expect(far).toBeGreaterThan(0);
    expect(small).toBeGreaterThan(far);
    expect(loop).toBeGreaterThan(small);
    // Both early exits write full visibility and keep the depth for the blur.
    expect(AO_FRAGMENT.match(/gl_FragColor = vec4\( 1\.0, z, 0\.0, 1\.0 \);/g)).toHaveLength(2);
  });

  it("blurs r and b and passes the depth in g through", () => {
    expect(AO_BLUR_FRAGMENT).toMatch(/gl_FragColor = vec4\( sum\.x, c\.g, sum\.y, /);
    expect(AO_BLUR_FRAGMENT).toContain("float tol = 1.0 / ( c.g * 0.03 + 0.02 );");
  });

  it("reads view depth from the composer's depth texture", () => {
    expect(DEPTH_GLSL).toContain("uNearFar.x * uNearFar.y / ( uNearFar.y - d * ( uNearFar.y - uNearFar.x ) )");
    expect(DEPTH_GLSL).toContain("vec3( ( uv * 2.0 - 1.0 ) * uProjInv * z, - z )");
  });
});

describe("ContactShadeEffect switches", () => {
  it("goes to strength 0 while suspended and comes back to LUX's strength", () => {
    const e = new ContactShadeEffect(new PerspectiveCamera());
    expect(e.strength).toBe(LUX.ao.strength);
    e.suspended = true;
    expect(e.suspended).toBe(true);
    expect(e.strength).toBe(0);
    expect(e.uniforms.get("uAoStrength")!.value).toBe(0);
    // A strength set while off is held at 0.
    e.strength = 0.5;
    expect(e.strength).toBe(0);
    e.suspended = false;
    expect(e.strength).toBe(LUX.ao.strength);
    e.strength = 0.5;
    expect(e.strength).toBe(0.5);
    e.dispose();
  });

  it("shows the occlusion alone with ?lux=ao", () => {
    const e = new ContactShadeEffect(new PerspectiveCamera());
    expect(e.uniforms.get("uAoDebug")!.value).toBe(0);
    e.debug = true;
    expect(e.uniforms.get("uAoDebug")!.value).toBe(1);
    e.debug = false;
    expect(e.uniforms.get("uAoDebug")!.value).toBe(0);
    e.dispose();
  });

  it("draws nothing while suspended or before it has a depth texture", () => {
    const e = new ContactShadeEffect(new PerspectiveCamera());
    expect(() => e.update(null as never)).not.toThrow();
    const depth = new DepthTexture(4, 4);
    e.setDepthTexture(depth);
    e.suspended = true;
    expect(() => e.update(null as never)).not.toThrow();
    const { renderer, targets } = stubRenderer();
    e.update(renderer);
    expect(targets).toHaveLength(0);
    e.suspended = false;
    e.update(renderer);
    // Occlusion, then the blur across and back.
    expect(targets).toHaveLength(3);
    expect(targets[0]).toBe(targets[2]);
    expect(targets[1]).not.toBe(targets[0]);
    e.dispose();
    depth.dispose();
  });
});

describe("ContactShadeEffect sizes", () => {
  it("works at the frame's size up to 1080p and smaller above it", () => {
    for (const [w, h] of [
      [1920, 1080],
      [3840, 2160],
    ]) {
      const e = new ContactShadeEffect(new PerspectiveCamera());
      e.setSize(w, h);
      const s = aoScale(w, h);
      const aw = Math.round(w * s);
      const ah = Math.round(h * s);
      const size = e.uniforms.get("uAoSize")!.value as Vector2;
      expect([size.x, size.y]).toEqual([aw, ah]);
      const u = occlusionOf(e);
      expect((u.uTexel.value as Vector2).x).toBeCloseTo(1 / aw);
      expect((u.uTexel.value as Vector2).y).toBeCloseTo(1 / ah);
      // The normal is rebuilt from the full-size depth texture's own neighbours.
      expect((u.uDepthTexel.value as Vector2).x).toBeCloseTo(1 / w);
      expect((u.uDepthTexel.value as Vector2).y).toBeCloseTo(1 / h);
      // The passes draw into targets of that size.
      const depth = new DepthTexture(4, 4);
      e.setDepthTexture(depth);
      const { renderer, targets } = stubRenderer();
      e.update(renderer);
      for (const t of targets) expect([t!.width, t!.height]).toEqual([aw, ah]);
      e.dispose();
      depth.dispose();
    }
    expect(Math.round(3840 * aoScale(3840, 2160))).toBeLessThan(3840 * 0.6);
  });

  it("never sizes to zero", () => {
    const e = new ContactShadeEffect(new PerspectiveCamera());
    e.setSize(0, 0);
    const size = e.uniforms.get("uAoSize")!.value as Vector2;
    expect(size.x).toBeGreaterThanOrEqual(1);
    expect(size.y).toBeGreaterThanOrEqual(1);
    e.dispose();
  });

  it("sets the radius in the buffer's pixels the way aoRadiusPx counts them", () => {
    const camera = new PerspectiveCamera(50, 16 / 9, 0.5, 9000);
    const e = new ContactShadeEffect(camera);
    e.setSize(1920, 1080);
    const depth = new DepthTexture(4, 4);
    e.setDepthTexture(depth);
    e.update(stubRenderer().renderer);
    const u = occlusionOf(e);
    const m = camera.projectionMatrix.elements;
    const h = Math.round(1080 * aoScale(1920, 1080));
    expect((u.uNearFar.value as Vector2).toArray()).toEqual([camera.near, camera.far]);
    expect((u.uProjInv.value as Vector2).x).toBeCloseTo(1 / m[0]);
    expect((u.uProjInv.value as Vector2).y).toBeCloseTo(1 / m[5]);
    const ao = u.uAo.value as Vector4;
    expect(ao.x).toBe(LUX.ao.radius);
    expect(ao.w).toBe(LUX.ao.fade[1]);
    expect(ao.z).toBeCloseTo(LUX.ao.maxScreen * h);
    // rPx = radius * uAo.y / z in the shader.
    for (const z of [3, 20, 90]) expect((ao.x * ao.y) / z).toBeCloseTo(aoRadiusPx(LUX.ao.radius, z, m[5], h));
    e.dispose();
    depth.dispose();
  });
});
