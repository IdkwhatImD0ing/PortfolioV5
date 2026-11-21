/**
 * The finish for /sect's post pass: the print (constants and maths in lib/sect/lux.ts).
 *
 * One more term in the merged effect shader, no pass of its own:
 * - a toe on luminance, so the nearest darks sit down under the haze the whole frame carries;
 * - a touch of saturation back;
 * - on High, a light sharpening from the frame's four neighbours (the bake's texels are several
 *   centimetres wide, and the MSAA resolve softens their edges a little more);
 * - fine grain, strongest in the mid tones. Its pattern moves only when a frame is drawn, and
 *   stands still with reduced motion.
 *
 * Glows over 1.0 pass through unchanged (the hue clip after this handles them).
 */
import { BlendFunction, Effect, EffectAttribute } from "postprocessing";
import { Uniform, Vector3 } from "three";
import { glslFloat, nonFiniteGlsl } from "@/lib/sect/glsl";
import { LUX } from "@/lib/sect/lux";

const FINISH_FRAGMENT = /* glsl */ `
// x: toe, y: sharpen, z: grain (8-bit steps).
uniform vec3 uFinish;
uniform float uFinishSeed;
#define FINISH_TOE_POWER ${glslFloat(LUX.finish.toePower)}
#define FINISH_SATURATION ${glslFloat(LUX.finish.saturation)}
#define FINISH_SHARPEN_MAX ${glslFloat(LUX.finish.sharpenMax)}
float finishHash( vec2 p ) {
  vec3 p3 = fract( vec3( p.xyx ) * 0.1031 );
  p3 += dot( p3, p3.yzx + 33.33 );
  return fract( ( p3.x + p3.y ) * p3.z );
}
void mainImage( const in vec4 inputColor, const in vec2 uv, out vec4 outputColor ) {
  outputColor = inputColor;
  if ( uFinish.x <= 0.0 && uFinish.y <= 0.0 && uFinish.z <= 0.0 ) return;
  vec3 c = inputColor.rgb;
  const vec3 luma = vec3( 0.2126, 0.7152, 0.0722 );
  if ( uFinish.y > 0.0 ) {
    // What the four neighbours lack of this pixel, from the frame as drawn.
    vec3 raw = texture2D( inputBuffer, uv ).rgb;
    vec3 around = texture2D( inputBuffer, uv + vec2( texelSize.x, 0.0 ) ).rgb + texture2D( inputBuffer, uv - vec2( texelSize.x, 0.0 ) ).rgb
      + texture2D( inputBuffer, uv + vec2( 0.0, texelSize.y ) ).rgb + texture2D( inputBuffer, uv - vec2( 0.0, texelSize.y ) ).rgb;
    float edge = dot( raw - around * 0.25, luma );
    // Only in range: a glow's edge is bloom's business.
    float inRange = 1.0 - smoothstep( 0.9, 1.3, dot( raw, luma ) );
    // A neighbour that is not a number must not take this pixel with it (lib/sect/glsl.ts POW_BASE_NOTE).
    float sharp = edge * uFinish.y;
    if ( ${nonFiniteGlsl("sharp", 1)} ) sharp = 0.0;
    c += clamp( sharp, - FINISH_SHARPEN_MAX, FINISH_SHARPEN_MAX ) * inRange;
    c = max( c, 0.0 );
  }
  float l = dot( c, luma );
  if ( l < 1.0 ) {
    float v = pow( max( l, 0.0 ), 0.4545 );
    // max: v is a pow and can come out a hair over 1 just under l = 1 (lib/sect/glsl.ts POW_BASE_NOTE).
    float v2 = v * ( 1.0 - uFinish.x * pow( max( 1.0 - v, 0.0 ), FINISH_TOE_POWER ) );
    float l2 = pow( v2, 2.2 );
    c *= l2 / max( l, 1e-5 );
    c = mix( vec3( l2 ), c, FINISH_SATURATION );
    c = max( c, 0.0 );
    if ( uFinish.z > 0.0 ) {
      // Grain in display steps, weighted to the mid tones, applied as a gain so hue holds.
      float n = finishHash( gl_FragCoord.xy + uFinishSeed ) + finishHash( gl_FragCoord.yx * 1.31 + uFinishSeed * 1.7 ) - 1.0;
      float w = 4.0 * v2 * ( 1.0 - v2 );
      float v3 = max( v2 + n * w * uFinish.z / 255.0, 0.0 );
      c *= pow( v3 / max( v2, 1e-4 ), 2.2 );
    }
  }
  outputColor = vec4( c, inputColor.a );
}
`;

export class FinishEffect extends Effect {
  /** With reduced motion the grain stands still. */
  still = false;
  private frame = 0;
  private off = false;
  private readonly sharpen: boolean;

  /** Off without a recompile: the shader leaves at its first test. */
  get suspended(): boolean {
    return this.off;
  }

  set suspended(off: boolean) {
    this.off = off;
    const c = this.look;
    const u = this.uniforms.get("uFinish")!.value as Vector3;
    if (off) u.set(0, 0, 0);
    else u.set(c.toe, this.sharpen ? c.sharpen : 0, c.grain);
  }

  /** The numbers it runs with (LUX.finish, or the journey's copy of it: look-now.ts). */
  look: typeof LUX.finish = LUX.finish;

  /** Takes the look's toe and grain (while it runs). */
  setLook(look: typeof LUX.finish): void {
    this.look = look;
    if (!this.off) (this.uniforms.get("uFinish")!.value as Vector3).set(look.toe, this.sharpen ? look.sharpen : 0, look.grain);
  }

  constructor(o: { sharpen: boolean }) {
    const c = LUX.finish;
    super("SectFinishEffect", FINISH_FRAGMENT, {
      blendFunction: BlendFunction.SRC,
      // No attribute, on purpose, although the sharpening reads the frame's neighbours. The effect
      // pass sorts its effects by attribute before merging them (convolution first, then depth,
      // then the rest), so with the convolution attribute the toe and the grain ran first of all,
      // under the contact shade, the bloom and the vignette. Without it this stays where
      // createPipeline puts it: last before the hue clip.
      attributes: EffectAttribute.NONE,
      uniforms: new Map<string, Uniform>([
        ["uFinish", new Uniform(new Vector3(c.toe, o.sharpen ? c.sharpen : 0, c.grain))],
        ["uFinishSeed", new Uniform(0)],
      ]),
    });
    this.sharpen = o.sharpen;
  }

  override update(): void {
    if (this.still) return;
    // A new pattern each drawn frame, from a short cycle of offsets.
    this.frame = (this.frame + 1) % 64;
    this.uniforms.get("uFinishSeed")!.value = this.frame * 17.13;
  }
}
