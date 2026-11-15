/**
 * Contact shade for /sect's post pass (constants and maths in lib/sect/lux.ts).
 *
 * The bake keeps light at a few centimetres a texel, so the thin dark line where a lantern, a
 * pillar base or a railing meets the paving is lost and small props seem to float. This pass works
 * that shade out from the depth buffer: ground-truth ambient occlusion (Jimenez et al. 2016, the
 * horizon integral as in XeGTAO), at the frame's size up to 1080p and scaled down above that, with
 * the view-space normal rebuilt from depth (the GLBs carry no normals).
 *
 * Three steps, all in `update` before the merged effect shader runs:
 * 1. occlusion: per pixel, a few slices through the hemisphere, each marched both ways for the
 *    highest horizon, integrated against the projected normal;
 * 2. two depth-aware blur passes (the per-pixel rotation noise goes, edges stay);
 * 3. the effect's own `mainImage` upsamples it with depth weights and darkens the frame, sparing
 *    glows and fading out with distance. Bright surfaces fill their own creases back in (the
 *    multi-bounce fit), so marble never creases to black.
 *
 * Everything is a function of the frame alone (no history), so a still frame stays still.
 */
import { BlendFunction, Effect, EffectAttribute, Pass } from "postprocessing";
import {
  HalfFloatType,
  NearestFilter,
  NoBlending,
  ShaderMaterial,
  Uniform,
  Vector2,
  Vector4,
  WebGLRenderTarget,
  type Camera,
  type PerspectiveCamera,
  type Texture,
  type WebGLRenderer,
} from "three";
import { glslFloat, glslVec3 } from "@/lib/sect/glsl";
import { aoScale, LUX } from "@/lib/sect/lux";

const FULLSCREEN_VERTEX = /* glsl */ `
varying vec2 vUv;
void main() {
  vUv = position.xy * 0.5 + 0.5;
  gl_Position = vec4( position.xy, 1.0, 1.0 );
}
`;

/** Shared by the occlusion and shaft passes: view-space position from the composer's depth texture. */
export const DEPTH_GLSL = /* glsl */ `
uniform highp sampler2D tDepth;
uniform vec2 uNearFar;
// x, y: 1 / P00, 1 / P11 (view x and y per NDC unit at distance 1).
uniform vec2 uProjInv;
float sectLinearZ( vec2 uv ) {
  float d = texture2D( tDepth, uv ).r;
  return uNearFar.x * uNearFar.y / ( uNearFar.y - d * ( uNearFar.y - uNearFar.x ) );
}
vec3 sectViewPos( vec2 uv, float z ) {
  return vec3( ( uv * 2.0 - 1.0 ) * uProjInv * z, - z );
}
`;

export const AO_FRAGMENT = /* glsl */ `
precision highp float;
${DEPTH_GLSL}
// The depth texture's texel, the AO buffer's texel.
uniform vec2 uDepthTexel;
uniform vec2 uTexel;
// Radius (m), pixels of this buffer per metre at distance 1, the radius cap in pixels, the far cut (m).
uniform vec4 uAo;
varying vec2 vUv;
#define AO_SLICES ${LUX.ao.slices}
#define AO_STEPS ${LUX.ao.steps}
#define AO_PI 3.14159265
#define AO_HALF_PI 1.57079633
float aoNoise( vec2 p ) {
  return fract( 52.9829189 * fract( dot( p, vec2( 0.06711056, 0.00583715 ) ) ) );
}
vec3 aoPos( vec2 uv ) {
  return sectViewPos( uv, sectLinearZ( uv ) );
}
void main() {
  float z = sectLinearZ( vUv );
  if ( z >= uAo.w ) {
    gl_FragColor = vec4( 1.0, z, 0.0, 1.0 );
    return;
  }
  vec3 p = sectViewPos( vUv, z );
  // The normal from depth: on each axis, the neighbour on the same surface (the smaller step in depth).
  vec2 dx = vec2( uDepthTexel.x, 0.0 );
  vec2 dy = vec2( 0.0, uDepthTexel.y );
  vec3 pr = aoPos( vUv + dx );
  vec3 pl = aoPos( vUv - dx );
  vec3 pu = aoPos( vUv + dy );
  vec3 pd = aoPos( vUv - dy );
  vec3 hx = abs( pr.z - p.z ) < abs( pl.z - p.z ) ? pr - p : p - pl;
  vec3 hy = abs( pu.z - p.z ) < abs( pd.z - p.z ) ? pu - p : p - pd;
  vec3 n = normalize( cross( hx, hy ) );
  vec3 v = normalize( - p );
  float radius = uAo.x;
  float rPx = min( radius * uAo.y / z, uAo.z );
  if ( rPx < 1.25 ) {
    gl_FragColor = vec4( 1.0, z, 0.0, 1.0 );
    return;
  }
  // The world radius the capped pixel radius still covers (close to the camera the cap shrinks it).
  float reach = rPx * z / uAo.y;
  float fallMul = - 1.0 / ( 0.615 * reach );
  float fallAdd = ( 1.0 - 0.615 ) / 0.615 + 1.0;
  float nDir = aoNoise( gl_FragCoord.xy );
  float nStep = aoNoise( gl_FragCoord.yx + 31.7 );
  float vis = 0.0;
  for ( int s = 0; s < AO_SLICES; s ++ ) {
    float phi = ( float( s ) + nDir ) / float( AO_SLICES ) * AO_PI;
    vec2 om = vec2( cos( phi ), sin( phi ) );
    vec3 dir = vec3( om, 0.0 );
    vec3 ortho = dir - dot( dir, v ) * v;
    vec3 axis = normalize( cross( ortho, v ) );
    vec3 pn = n - axis * dot( n, axis );
    float pnLen = max( length( pn ), 1e-5 );
    float cosN = clamp( dot( pn, v ) / pnLen, 0.0, 1.0 );
    float nAng = sign( dot( ortho, pn ) ) * acos( cosN );
    float low0 = cos( nAng + AO_HALF_PI );
    float low1 = cos( nAng - AO_HALF_PI );
    float hc0 = low0;
    float hc1 = low1;
    for ( int j = 0; j < AO_STEPS; j ++ ) {
      float t = ( float( j ) + nStep ) / float( AO_STEPS );
      // More samples near the point: contact first.
      vec2 off = om * ( t * t * rPx + 1.0 ) * uTexel;
      vec3 d0 = aoPos( vUv + off ) - p;
      vec3 d1 = aoPos( vUv - off ) - p;
      float l0 = max( length( d0 ), 1e-4 );
      float l1 = max( length( d1 ), 1e-4 );
      float w0 = clamp( l0 * fallMul + fallAdd, 0.0, 1.0 );
      float w1 = clamp( l1 * fallMul + fallAdd, 0.0, 1.0 );
      hc0 = max( hc0, mix( low0, dot( d0 / l0, v ), w0 ) );
      hc1 = max( hc1, mix( low1, dot( d1 / l1, v ), w1 ) );
    }
    float h0 = - acos( clamp( hc1, - 1.0, 1.0 ) );
    float h1 = acos( clamp( hc0, - 1.0, 1.0 ) );
    h0 = nAng + clamp( h0 - nAng, - AO_HALF_PI, AO_HALF_PI );
    h1 = nAng + clamp( h1 - nAng, - AO_HALF_PI, AO_HALF_PI );
    float a0 = ( cosN + 2.0 * h0 * sin( nAng ) - cos( 2.0 * h0 - nAng ) ) * 0.25;
    float a1 = ( cosN + 2.0 * h1 * sin( nAng ) - cos( 2.0 * h1 - nAng ) ) * 0.25;
    vis += pnLen * ( a0 + a1 );
  }
  gl_FragColor = vec4( clamp( vis / float( AO_SLICES ), 0.0, 1.0 ), z, 0.0, 1.0 );
}
`;

/**
 * One direction of the depth-aware blur: r and b are the values, g the view distance they belong to
 * (the contact shade uses r alone; the sun shafts keep lit air in r and shaded air in b).
 */
export const AO_BLUR_FRAGMENT = /* glsl */ `
precision highp float;
uniform sampler2D tAo;
uniform vec2 uStep;
varying vec2 vUv;
void main() {
  vec4 c = texture2D( tAo, vUv );
  vec2 sum = c.rb * 0.2270;
  float wsum = 0.2270;
  // A sample counts while it lies on the same surface: within a few percent of this pixel's depth.
  float tol = 1.0 / ( c.g * 0.03 + 0.02 );
  for ( int i = 1; i <= 3; i ++ ) {
    float g = i == 1 ? 0.1945 : ( i == 2 ? 0.1216 : 0.0540 );
    vec2 o = uStep * float( i );
    vec3 a = texture2D( tAo, vUv + o ).rgb;
    vec3 b = texture2D( tAo, vUv - o ).rgb;
    float wa = g * max( 0.0, 1.0 - abs( a.g - c.g ) * tol );
    float wb = g * max( 0.0, 1.0 - abs( b.g - c.g ) * tol );
    sum += a.rb * wa + b.rb * wb;
    wsum += wa + wb;
  }
  sum /= wsum;
  // a rides along unblurred (the shafts keep a mask there).
  gl_FragColor = vec4( sum.x, c.g, sum.y, c.a );
}
`;

const AO_EFFECT_FRAGMENT = /* glsl */ `
uniform sampler2D tAo;
uniform vec2 uAoSize;
uniform float uAoStrength;
uniform float uAoDebug;
#define AO_POWER ${glslFloat(LUX.ao.power)}
#define AO_FADE_LO ${glslFloat(LUX.ao.fade[0])}
#define AO_FADE_HI ${glslFloat(LUX.ao.fade[1])}
#define AO_GLOW_LO ${glslFloat(LUX.ao.glow[0])}
#define AO_GLOW_HI ${glslFloat(LUX.ao.glow[1])}
#define AO_TINT ${glslVec3([...LUX.ao.tint])}
#define AO_FOLIAGE ${glslFloat(LUX.ao.foliage)}
void mainImage( const in vec4 inputColor, const in vec2 uv, const in float depth, out vec4 outputColor ) {
  outputColor = inputColor;
  if ( uAoStrength <= 0.0 || depth >= 0.999999 ) return;
  float z = - getViewZ( depth );
  float fade = 1.0 - smoothstep( AO_FADE_LO, AO_FADE_HI, z );
  if ( fade <= 0.0 ) return;
  // Upsample the buffer (smaller than the frame above 1080p): its four nearest texels, each weighted by how close its depth is
  // to this pixel's (a wall's shade never bleeds onto the sky beside it).
  vec2 st = uv * uAoSize - 0.5;
  vec2 f = fract( st );
  vec2 base = ( floor( st ) + 0.5 ) / uAoSize;
  vec2 texel = 1.0 / uAoSize;
  float sum = 0.0;
  float wsum = 0.0;
  for ( int i = 0; i < 4; i ++ ) {
    vec2 o = vec2( float( i - ( i / 2 ) * 2 ), float( i / 2 ) );
    vec2 s = texture2D( tAo, base + o * texel ).rg;
    vec2 bw = mix( 1.0 - f, f, o );
    float w = ( bw.x * bw.y + 1e-3 ) / ( 0.02 + abs( s.g - z ) / z );
    sum += s.r * w;
    wsum += w;
  }
  float vis = pow( clamp( sum / wsum, 0.0, 1.0 ), AO_POWER );
  if ( uAoDebug > 0.5 ) {
    outputColor = vec4( vec3( vis * 0.8 ), inputColor.a );
    return;
  }
  float l = dot( inputColor.rgb, vec3( 0.2126, 0.7152, 0.0722 ) );
  float k = uAoStrength * fade * ( 1.0 - smoothstep( AO_GLOW_LO, AO_GLOW_HI, l ) );
  // Mist and cloud drawn over the world leave what they let through in the alpha (materials.ts
  // veilBlending): the shade belongs to the surfaces under them, so it fades with them.
  k *= clamp( inputColor.a, 0.0, 1.0 );
  // Leaves and grass, thinner than the radius, keep only a share of it. They are the pixels whose
  // green is level with red or leads it and stands clear of blue (lime, olive and deep green alike;
  // gold has more red, marble and slate more blue).
  float leaf = smoothstep( 0.86, 0.98, inputColor.g / max( inputColor.r, 1e-4 ) ) * smoothstep( 1.12, 1.3, inputColor.g / max( inputColor.b, 1e-4 ) );
  k *= mix( 1.0, AO_FOLIAGE, leaf );
  // Light bouncing inside a crease fills part of it back in, more on a bright surface.
  vec3 alb = clamp( inputColor.rgb, 0.0, 1.0 );
  vec3 a = 2.0404 * alb - 0.3324;
  vec3 b = - 4.7951 * alb + 0.6417;
  vec3 c = 2.7552 * alb + 0.6903;
  vec3 mb = max( vec3( vis ), ( ( vis * a + b ) * vis + c ) * vis );
  vec3 m = pow( 1.0 - k * ( 1.0 - min( mb, vec3( 1.0 ) ) ), AO_TINT );
  outputColor = vec4( inputColor.rgb * m, inputColor.a );
}
`;

/** A fullscreen draw of one material into a target (the post library's shared triangle). */
export class FullscreenPass extends Pass {
  constructor(name: string, material: ShaderMaterial) {
    super(name);
    this.needsSwap = false;
    this.fullscreenMaterial = material;
  }

  draw(renderer: WebGLRenderer, target: WebGLRenderTarget | null): void {
    renderer.setRenderTarget(target);
    renderer.render(this.scene, this.camera);
  }

  override render(renderer: WebGLRenderer, _input: WebGLRenderTarget, output: WebGLRenderTarget): void {
    this.draw(renderer, this.renderToScreen ? null : output);
  }
}

export function fullscreenMaterial(name: string, fragmentShader: string, uniforms: Record<string, Uniform>): ShaderMaterial {
  return new ShaderMaterial({
    name,
    uniforms,
    vertexShader: FULLSCREEN_VERTEX,
    fragmentShader,
    blending: NoBlending,
    depthTest: false,
    depthWrite: false,
    toneMapped: false,
    fog: false,
  });
}

export function dataTarget(name: string): WebGLRenderTarget {
  const t = new WebGLRenderTarget(1, 1, { depthBuffer: false, type: HalfFloatType });
  t.texture.name = name;
  t.texture.minFilter = NearestFilter;
  t.texture.magFilter = NearestFilter;
  t.texture.generateMipmaps = false;
  return t;
}

export class ContactShadeEffect extends Effect {
  private readonly camera: Camera;
  private readonly aoMaterial: ShaderMaterial;
  private readonly blurMaterial: ShaderMaterial;
  private readonly aoPass: FullscreenPass;
  private readonly blurPass: FullscreenPass;
  private readonly targetA: WebGLRenderTarget;
  private readonly targetB: WebGLRenderTarget;
  private readonly depthSize = new Vector2(1, 1);
  private off = false;

  constructor(camera: Camera) {
    super("SectContactShadeEffect", AO_EFFECT_FRAGMENT, {
      blendFunction: BlendFunction.SRC,
      attributes: EffectAttribute.DEPTH,
      uniforms: new Map<string, Uniform>([
        ["tAo", new Uniform<Texture | null>(null)],
        ["uAoSize", new Uniform(new Vector2(1, 1))],
        ["uAoStrength", new Uniform(LUX.ao.strength)],
        ["uAoDebug", new Uniform(0)],
      ]),
    });
    this.camera = camera;
    this.targetA = dataTarget("SectContactShade.A");
    this.targetB = dataTarget("SectContactShade.B");
    this.aoMaterial = fullscreenMaterial("SectContactShade.Occlusion", AO_FRAGMENT, {
      tDepth: new Uniform<Texture | null>(null),
      uNearFar: new Uniform(new Vector2(0.5, 9000)),
      uProjInv: new Uniform(new Vector2(1, 1)),
      uDepthTexel: new Uniform(new Vector2(1, 1)),
      uTexel: new Uniform(new Vector2(1, 1)),
      uAo: new Uniform(new Vector4(LUX.ao.radius, 1, 1, LUX.ao.fade[1])),
    });
    this.blurMaterial = fullscreenMaterial("SectContactShade.Blur", AO_BLUR_FRAGMENT, {
      tAo: new Uniform<Texture | null>(null),
      uStep: new Uniform(new Vector2(1, 0)),
    });
    this.aoPass = new FullscreenPass("SectContactShade.OcclusionPass", this.aoMaterial);
    this.blurPass = new FullscreenPass("SectContactShade.BlurPass", this.blurMaterial);
    this.uniforms.get("tAo")!.value = this.targetA.texture;
  }

  get strength(): number {
    return this.uniforms.get("uAoStrength")!.value as number;
  }

  set strength(v: number) {
    this.uniforms.get("uAoStrength")!.value = this.off ? 0 : v;
  }

  /** Off without a recompile: no occlusion or blur pass runs and the shader leaves at its first test. */
  get suspended(): boolean {
    return this.off;
  }

  set suspended(off: boolean) {
    this.off = off;
    this.uniforms.get("uAoStrength")!.value = off ? 0 : this.look.strength;
  }

  /** The numbers it runs with (LUX.ao, or the journey's copy of it: look-now.ts). */
  look: { strength: number } = LUX.ao;

  /** Takes the look's strength (while it runs). */
  setLook(look: { strength: number }): void {
    this.look = look;
    if (!this.off) this.uniforms.get("uAoStrength")!.value = look.strength;
  }

  /** ?lux=ao: the occlusion alone, as a grey image. */
  set debug(on: boolean) {
    this.uniforms.get("uAoDebug")!.value = on ? 1 : 0;
  }

  override setDepthTexture(depthTexture: Texture): void {
    this.aoMaterial.uniforms.tDepth.value = depthTexture;
  }

  override update(renderer: WebGLRenderer): void {
    if (this.off || this.strength <= 0 || !this.aoMaterial.uniforms.tDepth.value) return;
    const cam = this.camera as PerspectiveCamera;
    const u = this.aoMaterial.uniforms;
    const e = cam.projectionMatrix.elements;
    (u.uNearFar.value as Vector2).set(cam.near, cam.far);
    (u.uProjInv.value as Vector2).set(1 / e[0], 1 / e[5]);
    const h = this.targetA.height;
    (u.uAo.value as Vector4).set(LUX.ao.radius, e[5] * 0.5 * h, LUX.ao.maxScreen * h, LUX.ao.fade[1]);
    this.aoPass.draw(renderer, this.targetA);
    const b = this.blurMaterial.uniforms;
    b.tAo.value = this.targetA.texture;
    (b.uStep.value as Vector2).set(1 / this.targetA.width, 0);
    this.blurPass.draw(renderer, this.targetB);
    b.tAo.value = this.targetB.texture;
    (b.uStep.value as Vector2).set(0, 1 / this.targetA.height);
    this.blurPass.draw(renderer, this.targetA);
  }

  override setSize(width: number, height: number): void {
    this.depthSize.set(Math.max(1, width), Math.max(1, height));
    const scale = aoScale(width, height);
    const w = Math.max(1, Math.round(width * scale));
    const h = Math.max(1, Math.round(height * scale));
    this.targetA.setSize(w, h);
    this.targetB.setSize(w, h);
    (this.uniforms.get("uAoSize")!.value as Vector2).set(w, h);
    const u = this.aoMaterial.uniforms;
    (u.uDepthTexel.value as Vector2).set(1 / this.depthSize.x, 1 / this.depthSize.y);
    (u.uTexel.value as Vector2).set(1 / w, 1 / h);
  }

  override dispose(): void {
    this.targetA.dispose();
    this.targetB.dispose();
    this.aoMaterial.dispose();
    this.blurMaterial.dispose();
    this.aoPass.dispose();
    this.blurPass.dispose();
    super.dispose();
  }
}
