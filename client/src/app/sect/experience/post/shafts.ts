/**
 * Sun shafts for /sect's post pass (constants and maths in lib/sect/lux.ts).
 *
 * The bake lights surfaces, not the air between them. With the sun 7 degrees up, the gate's
 * pillars, the pagoda's eaves and every stone column stand in a low golden light that should
 * streak the haze behind them. This pass draws that:
 *
 * 1. A shadow map of the world from the sun: an orthographic depth render of everything that is
 *    baked (the scene is static, so it is only drawn again when the camera has left the middle of
 *    the map or a chunk has streamed in, not every frame).
 * 2. A march of every pixel's view ray through the haze at half size: at each step the air is lit
 *    or in shade by the map, and the light it sends to the eye follows a two-lobe phase function
 *    (a forward lobe for the glow toward the sun, a broad one so shafts seen from the side stay).
 *    Steps are denser near the eye and jittered per pixel.
 * 3. Two depth-aware blur passes (ao.ts's), and a wide blurred copy: each ray's surroundings.
 * 4. The effect's `mainImage` upsamples by depth and compares: a ray with more lit air than its
 *    surroundings is a shaft and gains light, one with less lies in a shadow and loses some. The
 *    haze the materials already draw is never added to, so open air keeps its tuned look.
 *
 * A function of the frame alone (no history): a still frame stays still.
 */
import { BlendFunction, Effect, EffectAttribute } from "postprocessing";
import {
  Color,
  DepthTexture,
  DoubleSide,
  LinearFilter,
  Matrix4,
  MeshBasicMaterial,
  NearestFilter,
  OrthographicCamera,
  RedFormat,
  Uniform,
  UnsignedByteType,
  UnsignedShortType,
  Vector2,
  Vector3,
  Vector4,
  WebGLRenderTarget,
  type Camera,
  type Material,
  type Mesh,
  type Object3D,
  type PerspectiveCamera,
  type Scene,
  type ShaderMaterial,
  type Texture,
  type WebGLRenderer,
} from "three";
import { glslFloat, type FogConstants } from "@/lib/sect/glsl";
import { LUX, shaftCentre, shaftScale, shaftsStale } from "@/lib/sect/lux";
import { AO_BLUR_FRAGMENT, dataTarget, DEPTH_GLSL, fullscreenMaterial, FullscreenPass } from "./ao";

/** The layer the sun's camera sees: set on every mesh that stands in the light's way. */
export const SHAFT_LAYER = 21;

/**
 * Whether a material's mesh throws shade into the air: baked stone, timber and terrain, and the
 * near trees' trunks. Not cut-out cards (as whole quads they would shade far more than their
 * leaves do), nothing see-through, no water.
 */
export function castsShafts(material: Material | Material[] | undefined): boolean {
  if (!material) return false;
  if (Array.isArray(material)) return material.some((m) => castsShafts(m));
  if (material.transparent || material.alphaTest > 0 || !material.visible) return false;
  if (/^water\./i.test(material.name)) return false;
  return material.userData?.baked === true || /^trees\.mesh\./i.test(material.name);
}

const PHASE = LUX.shafts.phase;

export const SHAFTS_FRAGMENT = /* glsl */ `
precision highp float;
${DEPTH_GLSL}
uniform highp sampler2D tShadow;
uniform mat4 uViewInv;
uniform mat4 uLight;
uniform vec3 uSunDir;
// The air: density at baseY (per metre), baseY, 1 / falloff, the march's reach (metres).
uniform vec4 uAir;
uniform float uBias;
// The cloud layer's top (three y, metres).
uniform float uCloudTop;
varying vec2 vUv;
#define SH_STEPS ${LUX.shafts.steps}
float shNoise( vec2 p ) {
  return fract( 52.9829189 * fract( dot( p, vec2( 0.06711056, 0.00583715 ) ) ) );
}
float shHg( float c, float g ) {
  float d = 1.0 + g * g - 2.0 * g * c;
  return ( 1.0 - g * g ) / ( d * sqrt( d ) );
}
float shPhase( float c ) {
  return ${glslFloat(PHASE.mix)} * shHg( c, ${glslFloat(PHASE.forward)} ) + ${glslFloat(1 - PHASE.mix)} * shHg( c, ${glslFloat(PHASE.broad)} );
}
void main() {
  float z = sectLinearZ( vUv );
  vec3 pv = sectViewPos( vUv, 1.0 );
  float stretch = length( pv );
  vec3 rd = normalize( mat3( uViewInv ) * pv );
  vec3 ro = uViewInv[ 3 ].xyz;
  float reach = uAir.w;
  float tEnd = min( z * stretch, reach );
  float jitter = shNoise( gl_FragCoord.xy );
  float lit = 0.0;
  float sum = 0.0;
  float od = 0.0;
  for ( int i = 0; i < SH_STEPS; i ++ ) {
    // Steps grow with distance (t goes as u squared): the air at hand gets most of them.
    float u = ( float( i ) + jitter ) / float( SH_STEPS );
    float t = tEnd * u * u;
    float dt = tEnd * 2.0 * u / float( SH_STEPS );
    vec3 p = ro + rd * t;
    float sigma = uAir.x * exp( clamp( - ( p.y - uAir.y ) * uAir.z, - 8.0, 3.0 ) );
    float w = exp( - od ) * sigma * dt * ( 1.0 - smoothstep( 0.7 * reach, reach, t ) );
    od += sigma * dt;
    vec4 lp = uLight * vec4( p, 1.0 );
    vec3 s = lp.xyz * 0.5 + 0.5;
    float vis = 1.0;
    if ( s.x > 0.0 && s.x < 1.0 && s.y > 0.0 && s.y < 1.0 && s.z < 1.0 ) {
      vis = step( s.z - uBias, texture2D( tShadow, s.xy ).r );
    }
    lit += w * vis;
    sum += w;
  }
  float c = dot( rd, uSunDir );
  float phase = min( shPhase( c ) / shPhase( 0.0 ), ${glslFloat(PHASE.max)} );
  // Where the ray ends on the cloud sea, an island's long shadow in the air over it reads as a
  // stripe drawn on the cloud: a is 0 there (no shade), 1 on everything that stands above it.
  float ySurf = ro.y + rd.y * z * stretch;
  float clear = z * stretch < 8000.0 ? smoothstep( uCloudTop - 60.0, uCloudTop - 15.0, ySurf ) : 1.0;
  // r: the light the ray's lit air sends to the eye, b: what all of its air would send.
  gl_FragColor = vec4( lit * phase, z, sum * phase, clear );
}
`;

/** The shafts buffer taken down to its surroundings: 16 linear taps over each texel's footprint. */
export const SHAFTS_WIDE_FRAGMENT = /* glsl */ `
precision highp float;
uniform sampler2D tSrc;
uniform vec2 uSrcTexel;
varying vec2 vUv;
void main() {
  vec2 sum = vec2( 0.0 );
  for ( int y = 0; y < 4; y ++ ) {
    for ( int x = 0; x < 4; x ++ ) {
      vec2 o = ( vec2( float( x ), float( y ) ) - 1.5 ) * 2.0;
      sum += texture2D( tSrc, vUv + o * uSrcTexel ).rb;
    }
  }
  gl_FragColor = vec4( sum.x / 16.0, 0.0, sum.y / 16.0, 1.0 );
}
`;

/** One direction of a plain Gaussian blur (no depth test: this is the surroundings' average). */
export const SHAFTS_SOFT_FRAGMENT = /* glsl */ `
precision highp float;
uniform sampler2D tSrc;
uniform vec2 uStep;
varying vec2 vUv;
void main() {
  vec2 sum = texture2D( tSrc, vUv ).rb * 0.2270;
  sum += ( texture2D( tSrc, vUv + uStep * 1.3846 ).rb + texture2D( tSrc, vUv - uStep * 1.3846 ).rb ) * 0.3162;
  sum += ( texture2D( tSrc, vUv + uStep * 3.2308 ).rb + texture2D( tSrc, vUv - uStep * 3.2308 ).rb ) * 0.0703;
  gl_FragColor = vec4( sum.x, 0.0, sum.y, 1.0 );
}
`;

const SHAFTS_EFFECT_FRAGMENT = /* glsl */ `
uniform sampler2D tShafts;
uniform sampler2D tShaftsWide;
uniform vec2 uShaftSize;
uniform vec3 uShaftColor;
// x: light a shaft adds, y: share of the frame a shadow in the air takes, z: broad shade.
uniform vec3 uShaftGain;
uniform float uShaftDebug;
#define SHAFT_DIM_MAX ${glslFloat(LUX.shafts.dimMax)}
void mainImage( const in vec4 inputColor, const in vec2 uv, const in float depth, out vec4 outputColor ) {
  outputColor = inputColor;
  if ( uShaftGain.x <= 0.0 && uShaftGain.y <= 0.0 ) return;
  float z = - getViewZ( depth );
  vec2 st = uv * uShaftSize - 0.5;
  vec2 f = fract( st );
  vec2 base = ( floor( st ) + 0.5 ) / uShaftSize;
  vec2 texel = 1.0 / uShaftSize;
  vec2 sum = vec2( 0.0 );
  float wsum = 0.0;
  for ( int i = 0; i < 4; i ++ ) {
    vec2 o = vec2( float( i - ( i / 2 ) * 2 ), float( i / 2 ) );
    vec3 s = texture2D( tShafts, base + o * texel ).rgb;
    vec2 bw = mix( 1.0 - f, f, o );
    float w = ( bw.x * bw.y + 1e-3 ) / ( 0.02 + abs( s.g - z ) / z );
    sum += s.rb * w;
    wsum += w;
  }
  sum /= wsum;
  // The ray's lit share against its surroundings' (the wide blurred copy), in units of its own air.
  vec2 wide = texture2D( tShaftsWide, uv ).rb;
  float share = sum.x / max( sum.y, 1e-5 );
  float around = wide.x / max( wide.y, 1e-5 );
  float delta = ( share - around ) * sum.y;
  if ( uShaftDebug > 0.5 ) {
    vec3 dbg = vec3( 0.4 ) + vec3( 1.0, 0.8, 0.2 ) * max( delta, 0.0 ) * 6.0 - vec3( 0.3, 0.2, 0.0 ) * max( - delta, 0.0 ) * 6.0;
    outputColor = vec4( max( dbg, 0.0 ), inputColor.a );
    return;
  }
  float take = ( uShaftGain.y * max( - delta, 0.0 ) + uShaftGain.z * ( sum.y - sum.x ) ) * texture2D( tShafts, uv ).a;
  vec3 col = inputColor.rgb * ( 1.0 - min( take, SHAFT_DIM_MAX ) );
  outputColor = vec4( col + uShaftColor * ( uShaftGain.x * max( delta, 0.0 ) ), inputColor.a );
}
`;

export class SunShaftsEffect extends Effect {
  private readonly world: Scene;
  private readonly camera: Camera;
  private readonly sun = new Vector3();
  private readonly sunCam: OrthographicCamera;
  private readonly shadow: WebGLRenderTarget;
  private readonly depthMaterial: MeshBasicMaterial;
  private readonly marchMaterial: ShaderMaterial;
  private readonly blurMaterial: ShaderMaterial;
  private readonly marchPass: FullscreenPass;
  private readonly blurPass: FullscreenPass;
  private readonly targetA: WebGLRenderTarget;
  private readonly targetB: WebGLRenderTarget;
  private readonly wideA: WebGLRenderTarget;
  private readonly wideB: WebGLRenderTarget;
  private readonly wideMaterial: ShaderMaterial;
  private readonly softMaterial: ShaderMaterial;
  private readonly widePass: FullscreenPass;
  private readonly softPass: FullscreenPass;
  private readonly seen = new WeakSet<Object3D>();
  private readonly centre = new Vector3(0, -1e9, 0);
  private readonly camPos = new Vector3();
  private readonly clear = new Color();
  private density: number;
  private hazeScale = 1;
  private dirty = true;
  private drawn = false;
  private sinceDraw = 1e9;
  private off = false;
  /** Shadow map redraws so far (for ?debug=1 and the tests). */
  redraws = 0;

  constructor(world: Scene, camera: Camera, fog: FogConstants) {
    const c = LUX.shafts;
    super("SectSunShaftsEffect", SHAFTS_EFFECT_FRAGMENT, {
      blendFunction: BlendFunction.SRC,
      attributes: EffectAttribute.DEPTH,
      uniforms: new Map<string, Uniform>([
        ["tShafts", new Uniform<Texture | null>(null)],
        ["uShaftSize", new Uniform(new Vector2(1, 1))],
        ["uShaftColor", new Uniform(new Color(c.color))],
        ["tShaftsWide", new Uniform<Texture | null>(null)],
        ["uShaftGain", new Uniform(new Vector3(c.gain, c.dim, c.shade))],
        ["uShaftDebug", new Uniform(0)],
      ]),
    });
    this.world = world;
    this.camera = camera;
    this.sun.set(...fog.sunDir).normalize();
    this.density = fog.density;
    // 16 bits over the map's 6.6 km of depth is 10 cm a step, well inside the bias.
    const depth = new DepthTexture(c.map, c.map, UnsignedShortType);
    depth.minFilter = NearestFilter;
    depth.magFilter = NearestFilter;
    depth.name = "SectSunShafts.ShadowDepth";
    this.shadow = new WebGLRenderTarget(c.map, c.map, {
      depthBuffer: true,
      depthTexture: depth,
      format: RedFormat,
      type: UnsignedByteType,
      generateMipmaps: false,
    });
    this.shadow.texture.name = "SectSunShafts.Shadow";
    this.sunCam = new OrthographicCamera(-c.box, c.box, c.box, -c.box, 1, c.reach + c.back);
    this.sunCam.layers.set(SHAFT_LAYER);
    this.sunCam.matrixAutoUpdate = true;
    this.depthMaterial = new MeshBasicMaterial({ colorWrite: false, side: DoubleSide, fog: false });
    this.depthMaterial.name = "SectSunShafts.Depth";
    this.targetA = dataTarget("SectSunShafts.A");
    this.targetB = dataTarget("SectSunShafts.B");
    this.wideA = dataTarget("SectSunShafts.WideA");
    this.wideB = dataTarget("SectSunShafts.WideB");
    // Read at texel centres by the depth-aware passes, and between them by the wide copy.
    for (const t of [this.targetA, this.wideA, this.wideB]) {
      t.texture.minFilter = LinearFilter;
      t.texture.magFilter = LinearFilter;
    }
    this.wideMaterial = fullscreenMaterial("SectSunShafts.Wide", SHAFTS_WIDE_FRAGMENT, {
      tSrc: new Uniform<Texture | null>(this.targetA.texture),
      uSrcTexel: new Uniform(new Vector2(1, 1)),
    });
    this.softMaterial = fullscreenMaterial("SectSunShafts.Soft", SHAFTS_SOFT_FRAGMENT, {
      tSrc: new Uniform<Texture | null>(null),
      uStep: new Uniform(new Vector2(1, 0)),
    });
    this.widePass = new FullscreenPass("SectSunShafts.WidePass", this.wideMaterial);
    this.softPass = new FullscreenPass("SectSunShafts.SoftPass", this.softMaterial);
    this.marchMaterial = fullscreenMaterial("SectSunShafts.March", SHAFTS_FRAGMENT, {
      tDepth: new Uniform<Texture | null>(null),
      tShadow: new Uniform<Texture | null>(depth),
      uNearFar: new Uniform(new Vector2(0.5, 9000)),
      uProjInv: new Uniform(new Vector2(1, 1)),
      uViewInv: new Uniform(new Matrix4()),
      uLight: new Uniform(new Matrix4()),
      uSunDir: new Uniform(this.sun.clone()),
      uAir: new Uniform(new Vector4(fog.density * c.air, fog.baseY, 1 / Math.max(fog.falloff, 1), c.maxDist)),
      uBias: new Uniform(c.bias / (c.reach + c.back - 1)),
      uCloudTop: new Uniform(fog.cloudTop),
    });
    this.blurMaterial = fullscreenMaterial("SectSunShafts.Blur", AO_BLUR_FRAGMENT, {
      tAo: new Uniform<Texture | null>(null),
      uStep: new Uniform(new Vector2(1, 0)),
    });
    this.marchPass = new FullscreenPass("SectSunShafts.MarchPass", this.marchMaterial);
    this.blurPass = new FullscreenPass("SectSunShafts.BlurPass", this.blurMaterial);
    this.uniforms.get("tShafts")!.value = this.targetA.texture;
    this.uniforms.get("tShaftsWide")!.value = this.wideA.texture;
  }

  /** Off without a recompile: no shadow map, march or blur, and the shader leaves at its first test. */
  get suspended(): boolean {
    return this.off;
  }

  set suspended(off: boolean) {
    this.off = off;
    const g = this.uniforms.get("uShaftGain")!.value as Vector3;
    if (off) g.set(0, 0, 0);
    else g.set(this.look.gain, this.look.dim, this.look.shade);
  }

  /** The numbers it runs with (LUX.shafts, or the journey's copy of it: look-now.ts). */
  look: typeof LUX.shafts = LUX.shafts;

  /** Takes the look's colour, gains and air (the colour and the air at once, the gains while it runs). */
  setLook(look: typeof LUX.shafts): void {
    this.look = look;
    (this.uniforms.get("uShaftColor")!.value as Color).set(look.color);
    if (!this.off) (this.uniforms.get("uShaftGain")!.value as Vector3).set(look.gain, look.dim, look.shade);
  }

  /** ?lux=shafts: on grey, where a ray is lighter than its surroundings (gold) and where darker. */
  set debug(on: boolean) {
    this.uniforms.get("uShaftDebug")!.value = on ? 1 : 0;
  }

  /** The stop's haze multiplier (scene.fog.density): thicker air, stronger shafts. */
  set haze(scale: number) {
    this.hazeScale = scale;
  }

  /** The drawn world changed (a chunk streamed in or left): draw the shadow map again. */
  invalidate(): void {
    this.dirty = true;
  }

  override setDepthTexture(depthTexture: Texture): void {
    this.marchMaterial.uniforms.tDepth.value = depthTexture;
  }

  private drawShadow(renderer: WebGLRenderer): void {
    const c = LUX.shafts;
    // Everything new in the world since the last draw: does it stand in the light's way?
    this.world.traverse((o) => {
      if (this.seen.has(o)) return;
      this.seen.add(o);
      const m = o as Mesh;
      if (m.isMesh && castsShafts(m.material)) m.layers.enable(SHAFT_LAYER);
    });
    const p = this.camPos;
    const centre = shaftCentre([p.x, p.y, p.z], [this.sun.x, this.sun.y, this.sun.z], (2 * c.box) / c.map);
    this.centre.set(...centre);
    const cam = this.sunCam;
    cam.position.copy(this.centre).addScaledVector(this.sun, c.reach);
    cam.up.set(0, 1, 0);
    cam.lookAt(this.centre);
    cam.updateMatrixWorld(true);
    cam.updateProjectionMatrix();
    (this.marchMaterial.uniforms.uLight.value as Matrix4).multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
    const world = this.world;
    const override = world.overrideMaterial;
    const background = world.background;
    const target = renderer.getRenderTarget();
    const autoClear = renderer.autoClear;
    renderer.getClearColor(this.clear);
    const alpha = renderer.getClearAlpha();
    world.overrideMaterial = this.depthMaterial;
    world.background = null;
    renderer.autoClear = true;
    renderer.setClearColor(0xffffff, 1);
    renderer.setRenderTarget(this.shadow);
    renderer.render(world, cam);
    renderer.setRenderTarget(target);
    renderer.setClearColor(this.clear, alpha);
    renderer.autoClear = autoClear;
    world.background = background;
    world.overrideMaterial = override;
    this.dirty = false;
    this.drawn = true;
    this.sinceDraw = 0;
    this.redraws++;
  }

  override update(renderer: WebGLRenderer, _input: WebGLRenderTarget, deltaTime?: number): void {
    if (this.off || !this.marchMaterial.uniforms.tDepth.value) return;
    const c = LUX.shafts;
    const cam = this.camera as PerspectiveCamera;
    this.camPos.setFromMatrixPosition(cam.matrixWorld);
    this.sinceDraw += Math.max(deltaTime ?? 0, 0);
    const p = this.camPos;
    const stale = shaftsStale([p.x, p.y, p.z], [this.centre.x, this.centre.y, this.centre.z]);
    if (!this.drawn || ((this.dirty || stale) && this.sinceDraw >= c.minInterval)) this.drawShadow(renderer);
    const u = this.marchMaterial.uniforms;
    const e = cam.projectionMatrix.elements;
    (u.uNearFar.value as Vector2).set(cam.near, cam.far);
    (u.uProjInv.value as Vector2).set(1 / e[0], 1 / e[5]);
    (u.uViewInv.value as Matrix4).copy(cam.matrixWorld);
    (u.uAir.value as Vector4).x = this.density * this.look.air * this.hazeScale;
    this.marchPass.draw(renderer, this.targetA);
    const b = this.blurMaterial.uniforms;
    b.tAo.value = this.targetA.texture;
    (b.uStep.value as Vector2).set(1 / this.targetA.width, 0);
    this.blurPass.draw(renderer, this.targetB);
    b.tAo.value = this.targetB.texture;
    (b.uStep.value as Vector2).set(0, 1 / this.targetA.height);
    this.blurPass.draw(renderer, this.targetA);
    // The surroundings: the buffer taken down, then blurred twice each way.
    (this.wideMaterial.uniforms.uSrcTexel.value as Vector2).set(1 / this.targetA.width, 1 / this.targetA.height);
    this.widePass.draw(renderer, this.wideA);
    const soft = this.softMaterial.uniforms;
    for (let i = 0; i < 2; i++) {
      soft.tSrc.value = this.wideA.texture;
      (soft.uStep.value as Vector2).set(1 / this.wideA.width, 0);
      this.softPass.draw(renderer, this.wideB);
      soft.tSrc.value = this.wideB.texture;
      (soft.uStep.value as Vector2).set(0, 1 / this.wideA.height);
      this.softPass.draw(renderer, this.wideA);
    }
  }

  override setSize(width: number, height: number): void {
    const scale = shaftScale(width, height);
    const w = Math.max(1, Math.round(width * scale));
    const h = Math.max(1, Math.round(height * scale));
    this.targetA.setSize(w, h);
    this.targetB.setSize(w, h);
    const ww = Math.max(1, Math.round(w / LUX.shafts.wide));
    const wh = Math.max(1, Math.round(h / LUX.shafts.wide));
    this.wideA.setSize(ww, wh);
    this.wideB.setSize(ww, wh);
    (this.uniforms.get("uShaftSize")!.value as Vector2).set(w, h);
  }

  override dispose(): void {
    this.shadow.dispose();
    this.targetA.dispose();
    this.targetB.dispose();
    this.wideA.dispose();
    this.wideB.dispose();
    this.wideMaterial.dispose();
    this.softMaterial.dispose();
    this.widePass.dispose();
    this.softPass.dispose();
    this.depthMaterial.dispose();
    this.marchMaterial.dispose();
    this.blurMaterial.dispose();
    this.marchPass.dispose();
    this.blurPass.dispose();
    super.dispose();
  }
}
