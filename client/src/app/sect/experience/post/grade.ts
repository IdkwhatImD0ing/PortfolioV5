/**
 * The whole frame's grade for a look (lib/sect/looks.ts FRAME_LOOK.grade the numbers, frameGradeLinear
 * the maths). One more term in the merged effect shader, built once when the page has a look or the
 * journey (never for today's dusk alone). Its numbers are uniforms, the frame group of the shared
 * look array (materials.ts SECT_LOOK_GPU, look-now.ts fills it), so the journey moves the grade
 * without a compile; at amount 0 the term leaves the frame as it is. The Low tier, which has no
 * post pass, runs the same grade at the end of each shader that draws to the screen (glsl.ts
 * sectLookGrade).
 */
import { BlendFunction, Effect } from "postprocessing";
import { Uniform } from "three";
import { FRAME_GRADE_VEC4S, LOOK_SLOT, lookFrameGradeGlsl } from "@/lib/sect/glsl";
import { SECT_LOOK_GPU } from "../materials";

export class FrameGradeEffect extends Effect {
  constructor() {
    // A view of the shared array's frame group: the same memory, so a write there reaches it.
    const data = SECT_LOOK_GPU.uSectLook.value.subarray(LOOK_SLOT.frame * 4, (LOOK_SLOT.frame + FRAME_GRADE_VEC4S) * 4);
    super(
      "SectFrameGradeEffect",
      /* glsl */ `
uniform vec4 uFrameGrade[ ${FRAME_GRADE_VEC4S} ];
${lookFrameGradeGlsl("sectFrameGrade", "uFrameGrade", 0)}
void mainImage( const in vec4 inputColor, const in vec2 uv, out vec4 outputColor ) {
  outputColor = vec4( sectFrameGrade( inputColor.rgb ), inputColor.a );
}
`,
      { blendFunction: BlendFunction.SRC, uniforms: new Map<string, Uniform>([["uFrameGrade", new Uniform(data)]]) },
    );
  }
}
