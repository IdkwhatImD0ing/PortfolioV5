/**
 * Postprocessing for /sect, built on the postprocessing library directly (no
 * @react-three/postprocessing: it pulled in an unused ambient-occlusion pass).
 *
 * Pipeline (high and mid tiers): RenderPass (the world) -> OverlayPass (clouds, mist, light beams,
 * drawn into the same buffer while reading a copy of its depth, for soft edges) -> EffectPass
 * (bloom, sun haze, vignette, hue-preserving clip).
 *
 * HueClipEffect: glowing surfaces are their baked colour times a glow factor, so they exceed 1.0
 * and bloom. Clipping each channel at 1.0 would turn a gold mirror or an amber lantern white. This
 * scales an over-range colour down by its largest channel instead, which keeps its hue, and lets
 * only very hot cores drift toward white. Colours already in range pass through unchanged.
 *
 * SunHazeEffect: a broad warm glow toward the sun's screen position (also when the sun is just off
 * screen), the golden in-scatter of the style frames.
 *
 * DitherEffect (last): about one 8-bit step of triangular noise, added in the sRGB space the pass
 * encodes to, so the long sky and haze gradients do not band on the 8-bit screen. All effects
 * merge into one shader, so it costs a few ALU ops a pixel and no extra pass.
 */
import {
  BlendFunction,
  BloomEffect,
  Effect,
  EffectComposer,
  EffectPass,
  Pass,
  RenderPass,
  VignetteEffect,
} from "postprocessing";
import {
  Color,
  HalfFloatType,
  type Camera,
  type Scene,
  type Texture,
  Uniform,
  Vector2,
  Vector3,
  type WebGLRenderer,
  type WebGLRenderTarget,
} from "three";
import { DITHER_GLSL, type FogConstants } from "@/lib/sect/glsl";
import { SECT_LOOK } from "@/lib/sect/look";
import { ATMOS, type AtmosFeatures } from "@/lib/sect/post";
import { CloudShadowEffect, glowPrefilter, HoldFocusEffect } from "./post/atmos";

const HUE_CLIP_FRAGMENT = /* glsl */ `
void mainImage( const in vec4 inputColor, const in vec2 uv, out vec4 outputColor ) {
  vec3 c = max( inputColor.rgb, 0.0 );
  float m = max( max( c.r, c.g ), c.b );
  vec3 kept = c / max( m, 1.0 );
  outputColor = vec4( mix( kept, vec3( 1.0 ), smoothstep( 1.8, 9.0, m ) * 0.55 ), inputColor.a );
}
`;

export class HueClipEffect extends Effect {
  constructor() {
    super("SectHueClipEffect", HUE_CLIP_FRAGMENT, { blendFunction: BlendFunction.SRC });
  }
}

const SUN_HAZE_FRAGMENT = /* glsl */ `
uniform vec3 uFwd;
uniform vec3 uRight;
uniform vec3 uUp;
uniform vec2 uTan;
uniform vec3 uSunDir;
uniform vec3 uColor;
uniform float uStrength;
void mainImage( const in vec4 inputColor, const in vec2 uv, out vec4 outputColor ) {
  // The view ray through this pixel, and how close it points to the sun: a broad warm glow on the
  // sun's side of the frame (also when the sun itself is off screen).
  vec3 ray = normalize( uFwd + ( uv.x * 2.0 - 1.0 ) * uTan.x * uRight + ( uv.y * 2.0 - 1.0 ) * uTan.y * uUp );
  float c = max( dot( ray, uSunDir ), 0.0 );
  float glow = ( pow( c, 10.0 ) * 0.9 + pow( c, 3.0 ) * 0.35 ) * uStrength;
  float l = dot( inputColor.rgb, vec3( 0.2126, 0.7152, 0.0722 ) );
  // Screen-like: lifts the darks and mids toward gold, leaves bright areas alone.
  outputColor = vec4( inputColor.rgb + uColor * glow * ( 1.0 - min( l, 1.0 ) * 0.7 ), inputColor.a );
}
`;

export class SunHazeEffect extends Effect {
  constructor(sunDir: Vector3, color: string, strength: number) {
    super("SectSunHazeEffect", SUN_HAZE_FRAGMENT, {
      blendFunction: BlendFunction.SRC,
      uniforms: new Map<string, Uniform>([
        ["uFwd", new Uniform(new Vector3(0, 0, -1))],
        ["uRight", new Uniform(new Vector3(1, 0, 0))],
        ["uUp", new Uniform(new Vector3(0, 1, 0))],
        ["uTan", new Uniform(new Vector2(1, 1))],
        ["uSunDir", new Uniform(sunDir.clone().normalize())],
        ["uColor", new Uniform(new Color(color))],
        ["uStrength", new Uniform(strength)],
      ]),
    });
  }

  /** The camera's basis and field of view; call before each render. */
  updateFromCamera(camera: Camera, aspect: number): void {
    const u = this.uniforms;
    (u.get("uFwd")!.value as Vector3).set(0, 0, -1).applyQuaternion(camera.quaternion);
    (u.get("uRight")!.value as Vector3).set(1, 0, 0).applyQuaternion(camera.quaternion);
    (u.get("uUp")!.value as Vector3).set(0, 1, 0).applyQuaternion(camera.quaternion);
    const fov = (camera as Camera & { fov?: number }).fov ?? 50;
    const ty = Math.tan(((fov * Math.PI) / 180) / 2);
    (u.get("uTan")!.value as Vector2).set(ty * aspect, ty);
  }
}

const DITHER_FRAGMENT = /* glsl */ `
uniform float uAmount;
${DITHER_GLSL}
void mainImage( const in vec4 inputColor, const in vec2 uv, out vec4 outputColor ) {
  // The pass encodes to sRGB after the effects: add the noise in that space (one step there is one
  // step on screen, also in the darks), then decode so the encode lands on it.
  vec3 s = sectSrgbEncode( inputColor.rgb ) + sectDitherNoise( gl_FragCoord.xy ) * ( uAmount / 255.0 );
  outputColor = vec4( sectSrgbDecode( s ), inputColor.a );
}
`;

export class DitherEffect extends Effect {
  /** `amount` in 8-bit steps (triangular noise spanning -amount..amount). */
  constructor(amount: number) {
    super("SectDitherEffect", DITHER_FRAGMENT, {
      blendFunction: BlendFunction.SRC,
      uniforms: new Map<string, Uniform>([["uAmount", new Uniform(amount)]]),
    });
  }
}

/**
 * Draws a second scene into the composer's buffer after the world, with the world's depth
 * available (EffectComposer copies it into a stable texture after the RenderPass): soft edges for
 * clouds, mist and beams without a feedback loop.
 */
export class OverlayPass extends Pass {
  private readonly onDepth: (t: Texture | null) => void;

  constructor(scene: Scene, camera: Camera, onDepth: (t: Texture | null) => void) {
    super("SectOverlayPass", scene, camera);
    this.needsSwap = false;
    this.needsDepthTexture = true;
    this.onDepth = onDepth;
  }

  override setDepthTexture(depthTexture: Texture): void {
    this.onDepth(depthTexture);
  }

  override render(renderer: WebGLRenderer, inputBuffer: WebGLRenderTarget): void {
    const auto = renderer.autoClear;
    renderer.autoClear = false;
    renderer.setRenderTarget(this.renderToScreen ? null : inputBuffer);
    renderer.render(this.scene, this.camera);
    renderer.autoClear = auto;
  }
}

/**
 * Bloom: only what goes over 1.0 (glows, the sun) gets a halo. A softer setting (threshold 0.85,
 * intensity 0.3) was tried at the holds: it shrank the glyph and Heart-Mirror halos and did not
 * visibly help marble or sky, so the threshold stays. The threshold reads luminance mixed toward
 * the brightest channel (post/atmos.ts glowPrefilter), so saturated glows such as lit windows
 * bloom too, and the halo is a little stronger and tighter: glows read as light in the air.
 */
export const BLOOM = { luminanceThreshold: 1, luminanceSmoothing: 0.2, intensity: ATMOS.bloom.intensity } as const;

export interface PipelineOptions {
  msaa: number;
  bloom: boolean;
  vignette: number;
  sunDir: Vector3;
  sunHaze: { color: string; strength: number };
  /** Dither in 8-bit steps at the end of the frame (default: the look's; 0 = none). */
  dither?: number;
  /** Atmosphere passes (post/atmos.ts) and the haze they read; none when left out. */
  atmos?: { fog: FogConstants; features: AtmosFeatures };
}

export interface Pipeline {
  composer: EffectComposer;
  sunHaze: SunHazeEffect;
  /** Drifting cloud shade (High and Medium), or null. */
  cloudShadow: CloudShadowEffect | null;
  /** Soft background while resting at a stop (High), or null. */
  holdFocus: HoldFocusEffect | null;
  bloom: BloomEffect | null;
  dispose(): void;
}

export function createPipeline(
  gl: WebGLRenderer,
  scene: Scene,
  overlay: Scene,
  camera: Camera,
  o: PipelineOptions,
  onDepth: (t: Texture | null) => void,
): Pipeline {
  const composer = new EffectComposer(gl, { frameBufferType: HalfFloatType, multisampling: o.msaa });
  composer.addPass(new RenderPass(scene, camera));
  composer.addPass(new OverlayPass(overlay, camera, onDepth));
  const sunHaze = new SunHazeEffect(o.sunDir, o.sunHaze.color, o.sunHaze.strength);
  const effects: Effect[] = [];
  // Hold focus first (it mixes in a blur of the frame as drawn), then cloud shade (it darkens the
  // surfaces, not the glow bloom adds over them).
  const holdFocus = o.atmos?.features.holdFocus ? new HoldFocusEffect() : null;
  if (holdFocus) effects.push(holdFocus);
  const cloudShadow = o.atmos?.features.cloudShadows ? new CloudShadowEffect(camera, o.atmos.fog) : null;
  if (cloudShadow) effects.push(cloudShadow);
  const bloom = o.bloom ? new BloomEffect({ mipmapBlur: true, radius: ATMOS.bloom.radius, ...BLOOM }) : null;
  if (bloom) {
    glowPrefilter(bloom);
    effects.push(bloom);
  }
  effects.push(sunHaze, new VignetteEffect({ offset: 0.3, darkness: Math.min(0.9, o.vignette * 2.3) }), new HueClipEffect());
  const dither = o.dither ?? SECT_LOOK.dither;
  if (dither > 0) effects.push(new DitherEffect(dither));
  composer.addPass(new EffectPass(camera, ...effects));
  return {
    composer,
    sunHaze,
    cloudShadow,
    holdFocus,
    bloom,
    dispose() {
      onDepth(null);
      composer.dispose();
    },
  };
}
