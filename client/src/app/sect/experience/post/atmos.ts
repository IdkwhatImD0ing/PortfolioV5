/**
 * Atmosphere effects for /sect's post pass (constants and maths in lib/sect/post.ts).
 *
 * CloudShadowEffect: rebuilds each pixel's world position from the depth buffer, follows the
 * sun's ray up to a cloud deck and reads drifting cloud noise there. Where a cloud covers the sun,
 * the surface darkens by up to ATMOS.cloudShadow.strength. Only lit surfaces darken (glows and deep
 * shade keep their value), and the haze in front of a surface keeps its own light, so shade fades
 * with distance as the air takes over. The sky (nothing in the depth buffer) is left alone.
 */
import { BlendFunction, Effect, EffectAttribute, KawaseBlurPass, KernelSize, type BloomEffect } from "postprocessing";
import {
  HalfFloatType,
  Matrix4,
  Uniform,
  Vector2,
  Vector3,
  Vector4,
  WebGLRenderTarget,
  type Camera,
  type Texture,
  type TextureDataType,
  type WebGLRenderer,
} from "three";
import { fogLibrary, glslFloat, type FogConstants } from "@/lib/sect/glsl";
import { ATMOS } from "@/lib/sect/post";

const CLOUD_SHADOW_FRAGMENT = (fog: FogConstants) => /* glsl */ `
uniform mat4 uProjInv;
uniform mat4 uViewInv;
uniform vec3 uCamPos;
uniform vec2 uDrift;
uniform float uStrength;
uniform vec4 uKeep;
${fogLibrary(fog)}
#define CS_DECK_Y ${glslFloat(ATMOS.cloudShadow.deckY)}
#define CS_SCALE ${glslFloat(ATMOS.cloudShadow.scale)}
#define CS_COVER_LO ${glslFloat(ATMOS.cloudShadow.cover[0])}
#define CS_COVER_HI ${glslFloat(ATMOS.cloudShadow.cover[1])}
#define CS_LIT_LO ${glslFloat(ATMOS.cloudShadow.lit[0])}
#define CS_LIT_HI ${glslFloat(ATMOS.cloudShadow.lit[1])}
#define CS_GLOW_LO ${glslFloat(ATMOS.cloudShadow.glow[0])}
#define CS_GLOW_HI ${glslFloat(ATMOS.cloudShadow.glow[1])}
float csHash( vec2 p ) {
  vec3 p3 = fract( vec3( p.xyx ) * 0.1031 );
  p3 += dot( p3, p3.yzx + 33.33 );
  return fract( ( p3.x + p3.y ) * p3.z );
}
float csNoise( vec2 p ) {
  vec2 i = floor( p );
  vec2 f = fract( p );
  vec2 u = f * f * ( 3.0 - 2.0 * f );
  float a = csHash( i );
  float b = csHash( i + vec2( 1.0, 0.0 ) );
  float c = csHash( i + vec2( 0.0, 1.0 ) );
  float d = csHash( i + vec2( 1.0, 1.0 ) );
  return mix( mix( a, b, u.x ), mix( c, d, u.x ), u.y );
}
// Three octaves, each turned and drifting a little faster than the last (clouds billow as they go).
float csClouds( vec2 p ) {
  const mat2 R = mat2( 0.8, 0.6, - 0.6, 0.8 );
  float n = 0.55 * csNoise( p );
  p = R * p * 2.03 + uDrift * 0.35;
  n += 0.3 * csNoise( p );
  p = R * p * 2.01 + uDrift * 0.6;
  n += 0.15 * csNoise( p );
  return n;
}
void mainImage( const in vec4 inputColor, const in vec2 uv, const in float depth, out vec4 outputColor ) {
  outputColor = inputColor;
  if ( depth >= 0.999999 || uStrength <= 0.0 ) return;
  vec4 v = uProjInv * vec4( uv * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0 );
  vec3 wp = ( uViewInv * vec4( v.xyz / v.w, 1.0 ) ).xyz;
  // Along the sun's ray up to the deck (the sun is low: shade is long along its bearing).
  vec2 q = wp.xz + SECT_SUN_DIR.xz * ( ( CS_DECK_Y - wp.y ) / max( SECT_SUN_DIR.y, 0.02 ) );
  float shade = smoothstep( CS_COVER_LO, CS_COVER_HI, csClouds( q / CS_SCALE + uDrift ) );
  // The stop's subject stays in the light (a film's key light on its hero): no shade within
  // uKeep.w metres of it, eased back in over the next uKeep.w.
  shade *= smoothstep( uKeep.w, 2.0 * uKeep.w, distance( wp, uKeep.xyz ) );
  float l = dot( inputColor.rgb, SECT_LUMA );
  float lit = smoothstep( CS_LIT_LO, CS_LIT_HI, l ) * ( 1.0 - smoothstep( CS_GLOW_LO, CS_GLOW_HI, l ) );
  // The haze between the camera and the surface is lit air, not the surface: only what still shows
  // through it darkens.
  vec3 rd = wp - uCamPos;
  float t = length( rd );
  rd /= max( t, 1e-4 );
  float tr = exp( - sectHazeDepth( uCamPos.y, rd.y, t ) - sectCloudDepth( uCamPos.y, rd.y, t ) );
  outputColor = vec4( inputColor.rgb * ( 1.0 - uStrength * shade * lit * tr ), inputColor.a );
}
`;

export class CloudShadowEffect extends Effect {
  /** Seconds of drift so far (frozen while `frozen`, for same-frame comparisons). */
  elapsed = 0;
  frozen = false;
  private readonly camera: Camera;

  constructor(camera: Camera, fog: FogConstants) {
    super("SectCloudShadowEffect", CLOUD_SHADOW_FRAGMENT(fog), {
      blendFunction: BlendFunction.SRC,
      attributes: EffectAttribute.DEPTH,
      uniforms: new Map<string, Uniform>([
        ["uProjInv", new Uniform(new Matrix4())],
        ["uViewInv", new Uniform(new Matrix4())],
        ["uCamPos", new Uniform(new Vector3())],
        ["uDrift", new Uniform(new Vector2())],
        ["uStrength", new Uniform(ATMOS.cloudShadow.strength)],
        ["uKeep", new Uniform(new Vector4(0, -1e5, 0, 1e-3))],
      ]),
    });
    this.camera = camera;
  }

  get strength(): number {
    return this.uniforms.get("uStrength")!.value as number;
  }

  set strength(v: number) {
    this.uniforms.get("uStrength")!.value = v;
  }

  /** Keeps shade off the stop's subject: its point and radius (metres; 0 = none). */
  keep(p: Vector3 | null, radius: number): void {
    const k = this.uniforms.get("uKeep")!.value as Vector4;
    if (p && radius > 0) k.set(p.x, p.y, p.z, radius);
    else k.set(0, -1e5, 0, 1e-3);
  }

  override update(_renderer: WebGLRenderer, _input: WebGLRenderTarget, deltaTime?: number): void {
    if (!this.frozen) this.elapsed += Math.min(Math.max(deltaTime ?? 0, 0), 0.1);
    const u = this.uniforms;
    const cam = this.camera;
    (u.get("uProjInv")!.value as Matrix4).copy(cam.projectionMatrixInverse);
    (u.get("uViewInv")!.value as Matrix4).copy(cam.matrixWorld);
    (u.get("uCamPos")!.value as Vector3).setFromMatrixPosition(cam.matrixWorld);
    const d = ATMOS.cloudShadow.drift;
    const s = ATMOS.cloudShadow.scale;
    (u.get("uDrift")!.value as Vector2).set((d[0] * this.elapsed) / s, (d[1] * this.elapsed) / s);
  }
}

const HOLD_FOCUS_FRAGMENT = /* glsl */ `
uniform sampler2D tBlur;
uniform float uWeight;
uniform float uFocus;
#define HF_NEAR ${glslFloat(ATMOS.holdFocus.near)}
#define HF_FAR ${glslFloat(ATMOS.holdFocus.far)}
#define HF_MIX ${glslFloat(ATMOS.holdFocus.mix)}
#define HF_CAP_LO ${glslFloat(ATMOS.holdFocus.cap[0])}
#define HF_CAP_HI ${glslFloat(ATMOS.holdFocus.cap[1])}
void mainImage( const in vec4 inputColor, const in vec2 uv, const in float depth, out vec4 outputColor ) {
  outputColor = inputColor;
  if ( uWeight <= 0.0 || depth >= 0.999999 ) return;
  float d = - getViewZ( depth );
  float t = smoothstep( HF_NEAR, HF_FAR, d / max( uFocus, 1.0 ) );
  // The moon and the sky dome stay crisp (a lens would soften them too, but they are the picture).
  t *= 1.0 - smoothstep( HF_CAP_LO, HF_CAP_HI, d );
  outputColor = vec4( mix( inputColor.rgb, texture2D( tBlur, uv ).rgb, uWeight * t * HF_MIX ), inputColor.a );
}
`;

/**
 * Hold focus: while the camera rests at a stop, the background past the subject softens a little
 * (a half-resolution Kawase blur of the frame, mixed in by distance). The blur pass runs only while
 * the weight is above 0, so in motion this costs one depth read and a branch.
 */
export class HoldFocusEffect extends Effect {
  private readonly blur: KawaseBlurPass;
  private readonly target: WebGLRenderTarget;

  constructor() {
    super("SectHoldFocusEffect", HOLD_FOCUS_FRAGMENT, {
      blendFunction: BlendFunction.SRC,
      attributes: EffectAttribute.DEPTH,
      uniforms: new Map<string, Uniform>([
        ["tBlur", new Uniform<Texture | null>(null)],
        ["uWeight", new Uniform(0)],
        ["uFocus", new Uniform(60)],
      ]),
    });
    this.target = new WebGLRenderTarget(1, 1, { depthBuffer: false, type: HalfFloatType });
    this.target.texture.name = "SectHoldFocus.Blur";
    this.uniforms.get("tBlur")!.value = this.target.texture;
    this.blur = new KawaseBlurPass({ kernelSize: KernelSize.VERY_SMALL, resolutionScale: ATMOS.holdFocus.resolution });
  }

  /** 0 = off (no blur pass), 1 = full. */
  get weight(): number {
    return this.uniforms.get("uWeight")!.value as number;
  }

  set weight(v: number) {
    this.uniforms.get("uWeight")!.value = v;
  }

  /** Distance to the subject (metres). */
  set focus(v: number) {
    this.uniforms.get("uFocus")!.value = v;
  }

  override update(renderer: WebGLRenderer, inputBuffer: WebGLRenderTarget): void {
    if (this.weight <= 0) return;
    this.blur.render(renderer, inputBuffer, this.target);
  }

  override setSize(width: number, height: number): void {
    this.blur.setSize(width, height);
    const r = this.blur.resolution;
    this.target.setSize(r.width, r.height);
  }

  override initialize(renderer: WebGLRenderer, alpha: boolean, frameBufferType: number): void {
    this.blur.initialize(renderer, alpha, frameBufferType);
    if (frameBufferType !== undefined) this.target.texture.type = frameBufferType as TextureDataType;
  }

  override dispose(): void {
    this.blur.dispose();
    this.target.dispose();
    super.dispose();
  }
}

/** The line of postprocessing's luminance shader that glowPrefilter swaps (checked by a test). */
export const LUMINANCE_LINE = "float l=luminance(texel.rgb);";

/**
 * Bloom's threshold reads luminance mixed toward the brightest channel (ATMOS.bloom.chroma), so a
 * saturated glow (a lit window, a red rune) blooms like a white one of the same strength. Returns
 * false when the library's shader no longer has the line (the bloom then stays as it was).
 */
export function glowPrefilter(bloom: BloomEffect, chroma: number = ATMOS.bloom.chroma): boolean {
  const m = bloom.luminanceMaterial;
  if (!m.fragmentShader.includes(LUMINANCE_LINE)) return false;
  m.fragmentShader = m.fragmentShader.replace(
    LUMINANCE_LINE,
    `float l=mix(luminance(texel.rgb),max(max(texel.r,texel.g),texel.b),${glslFloat(chroma)});`,
  );
  m.needsUpdate = true;
  return true;
}
