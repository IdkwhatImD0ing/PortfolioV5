/**
 * Tree card shading for /sect: which cut-out a card material carries, how its alpha is shaped, the
 * twig texture's colour detail, and the back light through the needles.
 *
 * Cards come from bake_trees.py. Far trees are crossed sprite cards cut out with their colour map's
 * alpha. Near pines carry needle cards: opaque in the file, with the cut-out as the occlusion
 * texture on TEXCOORD_1 (assets.ts loadCardAlpha loads it, materials.ts prepareNeedleCard moves it
 * to the alpha map). extras.cardAlpha says what that texture holds:
 * - "needle": a greyscale cut-out (three's alpha map reads G; sect_pack makes R = G = B).
 * - "twig": G = coverage, R = the photographed twig's luminance detail, high-passed so 0.5 (128)
 *   is neutral, B unused. The baked colour is multiplied by about 2R, fading to neutral with the mip
 *   level and the distance. Texels outside the twig (G = 0) should hold R = 0.5, so the mips stay
 *   neutral at the edges.
 *
 * Pure data, maths and GLSL strings (no three.js import), so it is testable.
 */
import { glslFloat } from "./glsl";

/** The cut-out a needle / twig card's alpha map holds (extras.cardAlpha). */
export type CardAlpha = "needle" | "twig";

export const CARD_LOOK = {
  /**
   * Alpha gain per mip level of the cut-out: mip averaging lowers alpha and the cut-off would remove
   * it, so distant cards would thin out. Sprites keep 0.22. Needle and twig cards take 0.05: at 0.22
   * a 256 px needle fan drawn about 37 px wide (mip 3) was boosted 1.66x and its 34 needles merged
   * into one solid wedge.
   */
  mipBoost: { sprite: 0.22, cutout: 0.05 },
  /**
   * Twig colour detail: factor clamp(1 + (2R - 1) * gain, min, max) on the baked colour, full up to
   * mip `mipNear` of the twig texture and `near` metres, neutral from mip `mipFar` or `far` metres
   * (needle cards only exist within about 110 m; beyond that a tree is a sprite card).
   */
  twig: { gain: 1, min: 0.4, max: 1.6, mipNear: 4, mipFar: 6.5, near: 60, far: 140 },
  /**
   * Back light through the needles (look.ts trees.rim times trees.rimStrength, times this shape):
   * - power: the lobe around the sun, pow(dot(view, sun), power) (Crysis uses 4; it was 3).
   * - litLo / litHi: the texel's graded baked brightness (max channel, linear) where the rim starts
   *   and where it is full. Shade-baked pines (sun off or blocked in the bake) sit at about 0.004
   *   and get none; the brighter half of sunlit needles (0.05 and up) get all of it.
   * - base: everywhere on the card. edge: extra on the cut-out's outer `edgePx` pixels (thin
   *   needles are all edge). At the peak (a thin edge of a fully lit texel, looking straight at the
   *   sun) the rim alone is (0.3 + 3.6) x 0.35 x #ffc890 = red 1.37, luminance 0.88, so a sunlit
   *   needle edge ends just over 1.0 and the bloom (threshold 1.0) catches it.
   */
  rim: { power: 5, litLo: 0.008, litHi: 0.07, base: 0.3, edge: 3.6, edgePx: 1.5 },
  /**
   * Sprite cards are two upright quads and a flat top quad (bake_trees.card_quads). Seen nearly
   * level, the top quad showed as a flat disc under every crown; from high above, the uprights as
   * an X (the r48 slice critic's F2). Each fades out by the view's elevation over the card (the sine
   * of the angle above its plane, from the face's own normal): the top quad below `top[0]`
   * (gone) to `top[1]` (full), the uprights from `side[0]` (full) to `side[1]` (gone): about 12-25
   * and 22-37 degrees. (Measured on the r48 slice's chunks: with the uprights kept to 55 degrees, the
   * f1055 look-down still showed X crowns, since most of that frame looks down 25-40 degrees.)
   */
  viewFade: { top: [0.2, 0.42] as const, side: [0.38, 0.6] as const },
};

export type CardLook = typeof CARD_LOOK;

/** The cut-out kind of a material's extras.cardAlpha, or null (a sprite card, or no card at all). */
export function cardAlphaKind(userData: Record<string, unknown> | null | undefined): CardAlpha | null {
  const v = userData?.cardAlpha;
  return v === "needle" || v === "twig" ? v : null;
}

/** True for a needle or twig card (its cut-out is the occlusion texture on TEXCOORD_1). */
export function isCutoutCard(userData: Record<string, unknown> | null | undefined): boolean {
  return cardAlphaKind(userData) !== null;
}

/** The alpha gain per mip level for a card kind (null = a sprite card). */
export function cardMipBoost(kind: CardAlpha | null, look: CardLook = CARD_LOOK): number {
  return kind ? look.mipBoost.cutout : look.mipBoost.sprite;
}

function smoothstep(a: number, b: number, x: number): number {
  const t = Math.min(Math.max((x - a) / (b - a), 0), 1);
  return t * t * (3 - 2 * t);
}

function clamp(x: number, lo: number, hi: number): number {
  return Math.min(Math.max(x, lo), hi);
}

/**
 * Screen pixels a fragment lies inside the cut-out's edge (negative outside): the alpha above the
 * cut-off over its change across one pixel (fwidth). Whatever the mip, the edge is about one pixel.
 */
export function cardEdgePx(alpha: number, cut: number, fwidth: number): number {
  return (alpha - cut) / Math.max(fwidth, 1e-4);
}

/**
 * TypeScript mirror of the needle / twig alpha test: the coverage a fragment keeps (0 = discarded).
 * With alpha to coverage it is the sharpened alpha, (a - cut) / fwidth(a) + 0.5, so the cut-off sits
 * half way through a one-pixel ramp. Without (no multisampling) a pixel is in or out, cut exactly
 * where the plain alpha test did.
 */
export function cardCoverage(alpha: number, cut: number, fwidth: number, alphaToCoverage: boolean): number {
  const px = cardEdgePx(alpha, cut, fwidth);
  if (alphaToCoverage) return clamp(px + 0.5, 0, 1);
  return px < 0 ? 0 : 1;
}

/** TypeScript mirror of the twig detail: the factor on the baked colour for R `r` at a mip and distance. */
export function twigFactor(r: number, mip: number, dist: number, look: CardLook = CARD_LOOK): number {
  const t = look.twig;
  const fade = (1 - smoothstep(t.mipNear, t.mipFar, mip)) * (1 - smoothstep(t.near, t.far, dist));
  const detail = clamp(1 + (2 * r - 1) * t.gain, t.min, t.max);
  return 1 + (detail - 1) * fade;
}

/**
 * TypeScript mirror of the back light: the multiplier on the rim colour (look.ts trees.rim times
 * rimStrength) for `viewSun` = dot(view direction, direction to the sun), a texel of graded baked
 * brightness `lum` (max channel), `edgePx` pixels inside the cut-out's edge.
 */
export function rimAmount(viewSun: number, lum: number, edgePx: number, look: CardLook = CARD_LOOK): number {
  const r = look.rim;
  const back = Math.pow(Math.max(viewSun, 0), r.power);
  const lit = smoothstep(r.litLo, r.litHi, lum);
  const edge = 1 - smoothstep(0, r.edgePx, edgePx);
  return back * lit * (r.base + r.edge * edge);
}

/** Mip level of a texture read at texel coordinates `t` (GLSL `sectMip`, from screen derivatives). */
const MIP_GLSL = "max( 0.0, 0.5 * log2( max( dot( dFdx( sectT ), dFdx( sectT ) ), dot( dFdy( sectT ), dFdy( sectT ) ) ) ) )";

/**
 * GLSL after <map_fragment> for a sprite card (cut out with its map's alpha): the alpha gain per mip
 * level. Needs uSectTexSize (the cut-out texture's size).
 */
export function cardSpriteBoostGlsl(look: CardLook = CARD_LOOK): string {
  return [
    "#if defined( USE_ALPHAMAP ) || defined( USE_MAP )",
    "  {",
    "  #ifdef USE_ALPHAMAP",
    "    vec2 sectT = vAlphaMapUv * uSectTexSize;",
    "  #else",
    "    vec2 sectT = vMapUv * uSectTexSize;",
    "  #endif",
    `    float sectMip = ${MIP_GLSL};`,
    `    diffuseColor.a *= 1.0 + sectMip * ${glslFloat(look.mipBoost.sprite)};`,
    "  }",
    "#endif",
  ].join("\n");
}

/**
 * GLSL after a sprite card's map (and cardSpriteBoostGlsl): the view-angle fade of its flat top quad
 * and its upright pair (CARD_LOOK.viewFade). The face normal comes from the screen derivatives of
 * vSectCardWorld, so the cards need no normals. Multiplies diffuseColor.a.
 */
export function cardViewFadeGlsl(look: CardLook = CARD_LOOK): string {
  const f = look.viewFade;
  return [
    "  {",
    "    vec3 sectCn = cross( dFdx( vSectCardWorld ), dFdy( vSectCardWorld ) );",
    "    float sectCl = length( sectCn );",
    "    if ( sectCl > 1e-8 ) {",
    "      float sectUp = abs( sectCn.y ) / sectCl;",
    "      float sectEl = abs( normalize( cameraPosition - vSectCardWorld ).y );",
    `      float sectTop = smoothstep( ${glslFloat(f.top[0])}, ${glslFloat(f.top[1])}, sectEl );`,
    `      float sectSide = 1.0 - smoothstep( ${glslFloat(f.side[0])}, ${glslFloat(f.side[1])}, sectEl );`,
    "      diffuseColor.a *= mix( sectSide, sectTop, smoothstep( 0.6, 0.9, sectUp ) );",
    "    }",
    "  }",
  ].join("\n");
}

/**
 * GLSL in place of <alphamap_fragment> for a needle or twig card: one read of the alpha map, the
 * cut-out from G with the (small) gain per mip level, and for a twig card the colour detail from R
 * (after the grade, which <color_fragment> applied). Needs uSectTexSize and vSectCardWorld.
 */
export function cardAlphaMapGlsl(kind: CardAlpha, look: CardLook = CARD_LOOK): string {
  const t = look.twig;
  const twig =
    kind === "twig"
      ? [
          // The photographed twig's light and dark needles, fading to neutral before they shimmer.
          `    float sectTf = ( 1.0 - smoothstep( ${glslFloat(t.mipNear)}, ${glslFloat(t.mipFar)}, sectMip ) )`,
          `      * ( 1.0 - smoothstep( ${glslFloat(t.near)}, ${glslFloat(t.far)}, length( vSectCardWorld - cameraPosition ) ) );`,
          `    float sectTd = clamp( 1.0 + ( 2.0 * sectCut.r - 1.0 ) * ${glslFloat(t.gain)}, ${glslFloat(t.min)}, ${glslFloat(t.max)} );`,
          "    diffuseColor.rgb *= mix( 1.0, sectTd, sectTf );",
        ]
      : [];
  return [
    "#ifdef USE_ALPHAMAP",
    "  {",
    "    vec4 sectCut = texture2D( alphaMap, vAlphaMapUv );",
    "    vec2 sectT = vAlphaMapUv * uSectTexSize;",
    `    float sectMip = ${MIP_GLSL};`,
    `    diffuseColor.a *= sectCut.g * ( 1.0 + sectMip * ${glslFloat(look.mipBoost.cutout)} );`,
    ...twig,
    "  }",
    "#endif",
  ].join("\n");
}

/**
 * GLSL in place of <alphatest_fragment> for every card. It declares `sectPx` (pixels inside the
 * cut-out's edge, for the rim). Needle and twig cards then cut with the sharpened alpha: with alpha
 * to coverage the edge becomes a one-pixel ramp centred on the cut-off; without, the cut is where
 * the plain test made it (a pixel can only be in or out). Sprite cards keep three's own test.
 */
export function cardAlphaTestGlsl(kind: CardAlpha | null): string {
  const test = kind
    ? [
        "#ifdef USE_ALPHATEST",
        "  #ifdef ALPHA_TO_COVERAGE",
        "  diffuseColor.a = clamp( sectPx + 0.5, 0.0, 1.0 );",
        "  if ( diffuseColor.a == 0.0 ) discard;",
        "  #else",
        "  if ( sectPx < 0.0 ) discard;",
        "  #endif",
        "#endif",
      ]
    : ["#include <alphatest_fragment>"];
  return [
    "  float sectPx = 1e4;",
    "#ifdef USE_ALPHATEST",
    "  sectPx = ( diffuseColor.a - alphaTest ) / max( fwidth( diffuseColor.a ), 1e-4 );",
    "#endif",
    ...test,
  ].join("\n");
}

/**
 * GLSL before <opaque_fragment> for every card: the warm back light when looking toward the sun
 * through the needles, on lit texels only, strongest on the cut-out's outer pixels. Needs uSectSun,
 * uSectRim, vSectCardWorld and `sectPx` (cardAlphaTestGlsl).
 */
export function cardRimGlsl(look: CardLook = CARD_LOOK): string {
  const r = look.rim;
  return [
    "  {",
    "    vec3 sectV = normalize( vSectCardWorld - cameraPosition );",
    `    float sectBack = pow( max( dot( sectV, uSectSun ), 0.0 ), ${glslFloat(r.power)} );`,
    // Shade-baked texels (the sun was off or blocked in the bake) must not glow.
    `    float sectLit = smoothstep( ${glslFloat(r.litLo)}, ${glslFloat(r.litHi)}, max( diffuseColor.r, max( diffuseColor.g, diffuseColor.b ) ) );`,
    `    float sectEdge = 1.0 - smoothstep( 0.0, ${glslFloat(r.edgePx)}, sectPx );`,
    `    outgoingLight += uSectRim * ( sectBack * sectLit * ( ${glslFloat(r.base)} + ${glslFloat(r.edge)} * sectEdge ) );`,
    "  }",
  ].join("\n");
}
