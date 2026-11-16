import { describe, expect, it } from "vitest";
import {
  BoxGeometry,
  type Camera,
  Color,
  type ColorRepresentation,
  DepthTexture,
  type Material,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  type OrthographicCamera,
  PerspectiveCamera,
  Scene,
  type ShaderMaterial,
  Vector3,
  type Vector2,
  type Vector4,
  type WebGLRenderer,
  type WebGLRenderTarget,
} from "three";
import { fogConstantsFromMeta, glslFloat } from "@/lib/sect/glsl";
import { LUX, shaftScale } from "@/lib/sect/lux";
import type { SectMeta } from "@/lib/sect/types";
import { castsShafts, SHAFT_LAYER, SHAFTS_FRAGMENT, SHAFTS_SOFT_FRAGMENT, SHAFTS_WIDE_FRAGMENT, SunShaftsEffect } from "./shafts";

const meta = {
  fog: { color: "#84889e", density: 0.0003, baseY: 100, falloff: 220 },
  sun: { direction: [-0.94397, 0.12187, 0.30671] },
  sky: { horizonSun: "#ffc890" },
  cloudSea: { fogTopY: 0 },
} as unknown as SectMeta;

const fog = fogConstantsFromMeta(meta);

interface Draw {
  target: WebGLRenderTarget | null;
  scene: Scene;
  camera: Camera;
  override: Material | null;
  background: Scene["background"];
  autoClear: boolean;
  clear: number;
  alpha: number;
}

/** A renderer that records each draw and the state it was drawn with; no WebGL. */
function stubRenderer() {
  const draws: Draw[] = [];
  const targets: (WebGLRenderTarget | null)[] = [];
  const state = { target: null as WebGLRenderTarget | null, clear: new Color(0.1, 0.2, 0.3), alpha: 0.5, autoClear: false };
  const renderer = {
    get autoClear() {
      return state.autoClear;
    },
    set autoClear(v: boolean) {
      state.autoClear = v;
    },
    getRenderTarget: () => state.target,
    setRenderTarget(t: WebGLRenderTarget | null) {
      targets.push(t);
      state.target = t;
    },
    getClearColor: (c: Color) => c.copy(state.clear),
    getClearAlpha: () => state.alpha,
    setClearColor(c: ColorRepresentation, a = 1) {
      state.clear.set(c);
      state.alpha = a;
    },
    render(scene: Scene, camera: Camera) {
      draws.push({
        target: state.target,
        scene,
        camera,
        override: scene.overrideMaterial,
        background: scene.background,
        autoClear: state.autoClear,
        clear: state.clear.getHex(),
        alpha: state.alpha,
      });
    },
  };
  return { renderer: renderer as unknown as WebGLRenderer, draws, targets, state };
}

const marchOf = (e: SunShaftsEffect) => (e as unknown as { marchMaterial: ShaderMaterial }).marchMaterial.uniforms;

function baked(o: { name?: string; transparent?: boolean; alphaTest?: number; visible?: boolean; baked?: unknown } = {}): MeshBasicMaterial {
  const m = new MeshBasicMaterial();
  m.name = o.name ?? "stone.wall";
  m.userData = o.baked === undefined ? { baked: true } : { baked: o.baked };
  if (o.transparent) m.transparent = true;
  if (o.alphaTest) m.alphaTest = o.alphaTest;
  if (o.visible === false) m.visible = false;
  return m;
}

function camAt(x: number, y: number, z: number): PerspectiveCamera {
  const c = new PerspectiveCamera(50, 16 / 9, 0.5, 9000);
  c.position.set(x, y, z);
  c.updateMatrixWorld();
  return c;
}

describe("castsShafts", () => {
  it("takes baked surfaces and the near trees' trunks", () => {
    expect(castsShafts(baked())).toBe(true);
    const trunk = new MeshBasicMaterial();
    trunk.name = "trees.mesh.abode";
    expect(castsShafts(trunk)).toBe(true);
    expect(castsShafts(Object.assign(new MeshBasicMaterial(), { name: "Trees.Mesh.Pine" }))).toBe(true);
  });

  it("leaves out cut-out cards, anything see-through or hidden, and water", () => {
    expect(castsShafts(baked({ alphaTest: 0.4 }))).toBe(false);
    expect(castsShafts(baked({ transparent: true }))).toBe(false);
    expect(castsShafts(baked({ visible: false }))).toBe(false);
    expect(castsShafts(baked({ name: "water.pond" }))).toBe(false);
    expect(castsShafts(baked({ name: "Water.Falls" }))).toBe(false);
    expect(castsShafts(baked({ name: "trees.mesh.abode", alphaTest: 0.42 }))).toBe(false);
  });

  it("leaves out plain materials and a baked flag that is not exactly true", () => {
    expect(castsShafts(new MeshBasicMaterial())).toBe(false);
    expect(castsShafts(baked({ baked: "true" }))).toBe(false);
    expect(castsShafts(baked({ baked: 1 }))).toBe(false);
    expect(castsShafts(undefined)).toBe(false);
  });

  it("takes a mesh with several materials when any of them casts", () => {
    expect(castsShafts([new MeshBasicMaterial(), baked()])).toBe(true);
    expect(castsShafts([new MeshBasicMaterial(), baked({ transparent: true })])).toBe(false);
    expect(castsShafts([])).toBe(false);
  });

  it("uses a layer of its own, not the default one", () => {
    expect(SHAFT_LAYER).toBeGreaterThan(0);
    expect(SHAFT_LAYER).toBeLessThan(32);
  });
});

describe("SunShaftsEffect shader", () => {
  it("reads depth and leaves at its first test while off, before any texture fetch", () => {
    const e = new SunShaftsEffect(new Scene(), new PerspectiveCamera(), fog);
    const fs = e.getFragmentShader();
    expect(fs).toContain("const in float depth");
    const off = fs.indexOf("if ( uShaftGain.x <= 0.0 && uShaftGain.y <= 0.0 ) return;");
    expect(off).toBeGreaterThan(0);
    expect(fs.indexOf("texture2D( tShafts")).toBeGreaterThan(off);
    expect(fs.indexOf("texture2D( tShaftsWide")).toBeGreaterThan(off);
    expect(fs).toContain(`#define SHAFT_DIM_MAX ${glslFloat(LUX.shafts.dimMax)}`);
    expect(fs).toContain("1.0 - min( take, SHAFT_DIM_MAX )");
    expect(fs).toContain("if ( uShaftDebug > 0.5 )");
    e.dispose();
  });

  it("marches LUX's steps with the same two-lobe phase as shaftPhase", () => {
    const p = LUX.shafts.phase;
    expect(SHAFTS_FRAGMENT).toContain(`#define SH_STEPS ${LUX.shafts.steps}`);
    expect(SHAFTS_FRAGMENT).toContain(
      `${glslFloat(p.mix)} * shHg( c, ${glslFloat(p.forward)} ) + ${glslFloat(1 - p.mix)} * shHg( c, ${glslFloat(p.broad)} )`,
    );
    expect(SHAFTS_FRAGMENT).toContain(`min( shPhase( c ) / shPhase( 0.0 ), ${glslFloat(p.max)} )`);
    expect(SHAFTS_FRAGMENT).toContain("return ( 1.0 - g * g ) / ( d * sqrt( d ) );");
  });

  it("tests the sun's map only inside it, with the bias along the sun's ray", () => {
    expect(SHAFTS_FRAGMENT).toContain("if ( s.x > 0.0 && s.x < 1.0 && s.y > 0.0 && s.y < 1.0 && s.z < 1.0 ) {");
    expect(SHAFTS_FRAGMENT).toContain("vis = step( s.z - uBias, texture2D( tShadow, s.xy ).r );");
    // The march fades out over its last 30 %.
    expect(SHAFTS_FRAGMENT).toContain("1.0 - smoothstep( 0.7 * reach, reach, t )");
  });

  it("takes the wide copy as the mean of 16 taps, and blurs it with weights that add up to one", () => {
    expect(SHAFTS_WIDE_FRAGMENT).toContain("gl_FragColor = vec4( sum.x / 16.0, 0.0, sum.y / 16.0, 1.0 );");
    const w = [...SHAFTS_SOFT_FRAGMENT.matchAll(/\) \* (0\.\d+);|\.rb \* (0\.\d+);/g)].map((m) => Number(m[1] ?? m[2]));
    expect(w).toHaveLength(3);
    expect(w[0] + 2 * w[1] + 2 * w[2]).toBeCloseTo(1, 3);
  });
});

describe("SunShaftsEffect switches", () => {
  it("starts with LUX's gains and colour", () => {
    const e = new SunShaftsEffect(new Scene(), new PerspectiveCamera(), fog);
    const g = e.uniforms.get("uShaftGain")!.value as Vector3;
    expect(g.toArray()).toEqual([LUX.shafts.gain, LUX.shafts.dim, LUX.shafts.shade]);
    expect((e.uniforms.get("uShaftColor")!.value as Color).equals(new Color(LUX.shafts.color))).toBe(true);
    e.dispose();
  });

  it("zeroes every gain while suspended and restores LUX's after", () => {
    const e = new SunShaftsEffect(new Scene(), new PerspectiveCamera(), fog);
    const g = e.uniforms.get("uShaftGain")!.value as Vector3;
    e.suspended = true;
    expect(e.suspended).toBe(true);
    expect(g.toArray()).toEqual([0, 0, 0]);
    e.suspended = false;
    expect(g.toArray()).toEqual([LUX.shafts.gain, LUX.shafts.dim, LUX.shafts.shade]);
    e.dispose();
  });

  it("shows the shafts alone with ?lux=shafts", () => {
    const e = new SunShaftsEffect(new Scene(), new PerspectiveCamera(), fog);
    e.debug = true;
    expect(e.uniforms.get("uShaftDebug")!.value).toBe(1);
    e.debug = false;
    expect(e.uniforms.get("uShaftDebug")!.value).toBe(0);
    e.dispose();
  });

  it("sets the shadow test's bias in the sun camera's depth units", () => {
    const e = new SunShaftsEffect(new Scene(), new PerspectiveCamera(), fog);
    const sunCam = (e as unknown as { sunCam: OrthographicCamera }).sunCam;
    expect((marchOf(e).uBias.value as number) * (sunCam.far - sunCam.near)).toBeCloseTo(LUX.shafts.bias);
    expect(sunCam.far - sunCam.near).toBeGreaterThan(LUX.shafts.reach);
    e.dispose();
  });
});

describe("SunShaftsEffect.update", () => {
  it("is a no-op while suspended or before it has a depth texture", () => {
    const e = new SunShaftsEffect(new Scene(), camAt(0, 50, 0), fog);
    expect(() => e.update(null as never, null as never, 0.016)).not.toThrow();
    const depth = new DepthTexture(4, 4);
    e.setDepthTexture(depth);
    e.suspended = true;
    expect(() => e.update(null as never, null as never, 0.016)).not.toThrow();
    const { renderer, draws } = stubRenderer();
    e.update(renderer, null as never, 0.016);
    expect(draws).toHaveLength(0);
    expect(e.redraws).toBe(0);
    e.dispose();
    depth.dispose();
  });

  it("draws the sun's map from the casters' layer, and restores every bit of renderer and scene state", () => {
    const world = new Scene();
    world.background = new Color(0x123456);
    const stone = new Mesh(new BoxGeometry(), baked());
    const glass = new Mesh(new BoxGeometry(), baked({ transparent: true }));
    world.add(stone, glass);
    const e = new SunShaftsEffect(world, camAt(10, 50, -20), fog);
    const depth = new DepthTexture(4, 4);
    e.setDepthTexture(depth);
    e.setSize(1280, 720);
    const { renderer, draws, targets, state } = stubRenderer();
    // The composer's own target, current when the effect is updated.
    const composerTarget = {} as WebGLRenderTarget;
    state.target = composerTarget;
    const before = { clear: state.clear.getHex(), alpha: state.alpha, autoClear: state.autoClear };
    e.update(renderer, null as never, 0.016);
    expect(e.redraws).toBe(1);
    expect(stone.layers.isEnabled(SHAFT_LAYER)).toBe(true);
    expect(glass.layers.isEnabled(SHAFT_LAYER)).toBe(false);
    // The shadow map first, drawn with the depth material, no background, cleared to the far plane.
    const shadow = draws[0];
    expect(shadow.scene).toBe(world);
    expect(shadow.camera.layers.isEnabled(SHAFT_LAYER)).toBe(true);
    expect(shadow.camera.layers.isEnabled(0)).toBe(false);
    expect(shadow.override).not.toBeNull();
    expect(shadow.background).toBeNull();
    expect(shadow.autoClear).toBe(true);
    expect(shadow.clear).toBe(0xffffff);
    expect(shadow.alpha).toBe(1);
    // Then the march, its two blurs, the wide copy and its four soft passes.
    expect(draws).toHaveLength(9);
    // Everything put back: the target right after the map is drawn, the rest at the end.
    expect(targets[0]).toBe(shadow.target);
    expect(targets[1]).toBe(composerTarget);
    expect(world.overrideMaterial).toBeNull();
    expect((world.background as Color).getHex()).toBe(0x123456);
    expect(state.clear.getHex()).toBe(before.clear);
    expect(state.alpha).toBe(before.alpha);
    expect(state.autoClear).toBe(before.autoClear);
    e.dispose();
    depth.dispose();
  });

  it("centres the sun's map on the camera and hands the march the same matrix", () => {
    const camera = camAt(-431.7, 212.3, 905.1);
    const e = new SunShaftsEffect(new Scene(), camera, fog);
    const depth = new DepthTexture(4, 4);
    e.setDepthTexture(depth);
    const { renderer, draws } = stubRenderer();
    e.update(renderer, null as never, 0.016);
    const sunCam = draws[0].camera as OrthographicCamera;
    const light = new Matrix4().multiplyMatrices(sunCam.projectionMatrix, sunCam.matrixWorldInverse);
    expect((marchOf(e).uLight.value as Matrix4).equals(light)).toBe(true);
    // The camera lands within half a texel of the map's middle, inside its depth range.
    const p = camera.position.clone().applyMatrix4(light);
    expect(Math.abs(p.x)).toBeLessThanOrEqual(1 / LUX.shafts.map + 1e-9);
    expect(Math.abs(p.y)).toBeLessThanOrEqual(1 / LUX.shafts.map + 1e-9);
    expect(Math.abs(p.z)).toBeLessThan(1);
    // The sun camera looks along the sun, toward the camera.
    const dir = sunCam.getWorldDirection(new Vector3());
    expect(dir.dot(new Vector3(...fog.sunDir).normalize())).toBeCloseTo(-1, 6);
    e.dispose();
    depth.dispose();
  });

  it("redraws the map only when the world changed or the camera left its middle, never faster than minInterval", () => {
    const world = new Scene();
    const camera = camAt(0, 50, 0);
    const e = new SunShaftsEffect(world, camera, fog);
    const depth = new DepthTexture(4, 4);
    e.setDepthTexture(depth);
    const { renderer } = stubRenderer();
    const c = LUX.shafts;
    e.update(renderer, null as never, 0.016);
    expect(e.redraws).toBe(1);
    // A chunk streamed in: waits out minInterval since the last draw, then draws.
    e.invalidate();
    e.update(renderer, null as never, 0.016);
    expect(e.redraws).toBe(1);
    e.update(renderer, null as never, c.minInterval);
    expect(e.redraws).toBe(2);
    // Nothing changed: no draw however long it has been.
    e.update(renderer, null as never, c.minInterval * 4);
    expect(e.redraws).toBe(2);
    // A small move keeps the map.
    camera.position.x += c.refresh * 0.5;
    camera.updateMatrixWorld();
    e.update(renderer, null as never, c.minInterval);
    expect(e.redraws).toBe(2);
    // Past refresh it is drawn again.
    camera.position.x += c.refresh;
    camera.updateMatrixWorld();
    e.update(renderer, null as never, c.minInterval);
    expect(e.redraws).toBe(3);
    // A fast camera still waits out minInterval.
    camera.position.x += c.refresh * 2;
    camera.updateMatrixWorld();
    e.update(renderer, null as never, 0.016);
    expect(e.redraws).toBe(3);
    e.update(renderer, null as never, c.minInterval);
    expect(e.redraws).toBe(4);
    e.dispose();
    depth.dispose();
  });

  it("puts a caster added after the first draw on the layer at the next draw", () => {
    const world = new Scene();
    const e = new SunShaftsEffect(world, camAt(0, 50, 0), fog);
    const depth = new DepthTexture(4, 4);
    e.setDepthTexture(depth);
    const { renderer } = stubRenderer();
    e.update(renderer, null as never, 0.016);
    const late = new Mesh(new BoxGeometry(), baked());
    world.add(late);
    expect(late.layers.isEnabled(SHAFT_LAYER)).toBe(false);
    e.invalidate();
    e.update(renderer, null as never, LUX.shafts.minInterval);
    expect(late.layers.isEnabled(SHAFT_LAYER)).toBe(true);
    e.dispose();
    depth.dispose();
  });

  it("thickens the air with the stop's haze", () => {
    const e = new SunShaftsEffect(new Scene(), camAt(0, 50, 0), fog);
    const depth = new DepthTexture(4, 4);
    e.setDepthTexture(depth);
    const { renderer } = stubRenderer();
    e.haze = 2;
    e.update(renderer, null as never, 0.016);
    expect((marchOf(e).uAir.value as Vector4).x).toBeCloseTo(fog.density * LUX.shafts.air * 2);
    e.dispose();
    depth.dispose();
  });
});

describe("SunShaftsEffect sizes", () => {
  it("sizes its buffer by shaftScale and the wide copy by LUX's wide factor", () => {
    for (const [w, h] of [
      [1920, 1080],
      [3840, 2160],
    ]) {
      const e = new SunShaftsEffect(new Scene(), camAt(0, 50, 0), fog);
      e.setSize(w, h);
      const s = shaftScale(w, h);
      const bw = Math.max(1, Math.round(w * s));
      const bh = Math.max(1, Math.round(h * s));
      const size = e.uniforms.get("uShaftSize")!.value as Vector2;
      expect([size.x, size.y]).toEqual([bw, bh]);
      const depth = new DepthTexture(4, 4);
      e.setDepthTexture(depth);
      const { renderer, draws } = stubRenderer();
      e.update(renderer, null as never, 0.016);
      // March and blurs at the buffer's size, the wide copy and its blur smaller.
      for (const d of draws.slice(1, 4)) expect([d.target!.width, d.target!.height]).toEqual([bw, bh]);
      const ww = Math.max(1, Math.round(bw / LUX.shafts.wide));
      const wh = Math.max(1, Math.round(bh / LUX.shafts.wide));
      for (const d of draws.slice(4)) expect([d.target!.width, d.target!.height]).toEqual([ww, wh]);
      // The sun's map keeps its own size.
      expect([draws[0].target!.width, draws[0].target!.height]).toEqual([LUX.shafts.map, LUX.shafts.map]);
      e.dispose();
      depth.dispose();
    }
  });

  it("never sizes to zero", () => {
    const e = new SunShaftsEffect(new Scene(), new PerspectiveCamera(), fog);
    e.setSize(0, 0);
    const size = e.uniforms.get("uShaftSize")!.value as Vector2;
    expect(size.x).toBeGreaterThanOrEqual(1);
    expect(size.y).toBeGreaterThanOrEqual(1);
    e.dispose();
  });
});
