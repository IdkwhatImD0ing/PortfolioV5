import { Color } from "three";
import { describe, expect, it } from "vitest";
import {
  CARD_LOOK,
  cardAlphaKind,
  cardAlphaMapGlsl,
  cardAlphaTestGlsl,
  cardCoverage,
  cardEdgePx,
  cardMipBoost,
  cardRimGlsl,
  cardSpriteBoostGlsl,
  isCutoutCard,
  rimAmount,
  twigFactor,
} from "./card-shading";
import { glslFloat } from "./glsl";
import { SECT_LOOK } from "./look";

const count = (s: string, sub: string) => s.split(sub).length - 1;

describe("card kinds (extras.cardAlpha)", () => {
  it("reads the needle and twig tags and nothing else", () => {
    expect(cardAlphaKind({ cardAlpha: "needle", baked: true })).toBe("needle");
    expect(cardAlphaKind({ cardAlpha: "twig", baked: true })).toBe("twig");
    expect(cardAlphaKind({ cardAlpha: "leaf" })).toBeNull();
    expect(cardAlphaKind({ cardAlpha: "Twig" })).toBeNull();
    expect(cardAlphaKind({ cardAlpha: 1 })).toBeNull();
    expect(cardAlphaKind({})).toBeNull();
    expect(cardAlphaKind(null)).toBeNull();
    expect(cardAlphaKind(undefined)).toBeNull();
  });

  it("treats twig cards like needle cards for the texture plumbing", () => {
    expect(isCutoutCard({ cardAlpha: "needle" })).toBe(true);
    expect(isCutoutCard({ cardAlpha: "twig" })).toBe(true);
    expect(isCutoutCard({ baked: true })).toBe(false);
    expect(isCutoutCard(undefined)).toBe(false);
  });

  it("keeps the sprites' mip boost and lowers it on needle and twig cards", () => {
    expect(cardMipBoost(null)).toBe(0.22);
    expect(cardMipBoost("needle")).toBe(0.05);
    expect(cardMipBoost("twig")).toBe(0.05);
    // A 256 px fan drawn 37 px wide sits at mip 3: 1.66x before, about 1.15x now.
    const mip = Math.log2(256 / 37);
    expect(1 + mip * cardMipBoost(null)).toBeGreaterThan(1.6);
    expect(1 + mip * cardMipBoost("needle")).toBeLessThan(1.15);
  });
});

describe("cut-out edge sharpening", () => {
  const cut = 0.4;

  it("measures the distance to the edge in screen pixels", () => {
    expect(cardEdgePx(0.4, cut, 0.1)).toBeCloseTo(0);
    expect(cardEdgePx(0.6, cut, 0.1)).toBeCloseTo(2);
    expect(cardEdgePx(0.3, cut, 0.1)).toBeCloseTo(-1);
    // A flat alpha (no change across the pixel) is deep inside or outside, never a division by 0.
    expect(cardEdgePx(1, cut, 0)).toBeGreaterThan(1000);
    expect(cardEdgePx(0, cut, 0)).toBeLessThan(-1000);
  });

  it("with alpha to coverage, ramps over one pixel centred on the cut-off", () => {
    expect(cardCoverage(cut, cut, 0.2, true)).toBeCloseTo(0.5);
    expect(cardCoverage(cut + 0.1, cut, 0.2, true)).toBeCloseTo(1);
    expect(cardCoverage(cut - 0.1, cut, 0.2, true)).toBeCloseTo(0);
    expect(cardCoverage(cut + 0.05, cut, 0.2, true)).toBeCloseTo(0.75);
    // A blurred (high mip) alpha changes little across a pixel: the ramp stays one pixel wide.
    expect(cardCoverage(cut + 0.01, cut, 0.01, true)).toBeCloseTo(1);
  });

  it("without multisampling, cuts exactly where the plain alpha test did", () => {
    for (const a of [0, 0.2, 0.399, 0.4, 0.401, 0.7, 1]) {
      for (const fw of [0, 0.001, 0.05, 0.5]) {
        expect(cardCoverage(a, cut, fw, false)).toBe(a < cut ? 0 : 1);
      }
    }
  });
});

describe("twig colour detail", () => {
  const t = CARD_LOOK.twig;

  it("multiplies the baked colour by about 2R up close, clamped", () => {
    expect(twigFactor(0.5, 0, 0)).toBeCloseTo(1);
    expect(twigFactor(0.6, 0, 0)).toBeCloseTo(1.2);
    expect(twigFactor(0.25, 0, 0)).toBeCloseTo(0.5);
    expect(twigFactor(0, 0, 0)).toBeCloseTo(t.min);
    expect(twigFactor(1, 0, 0)).toBeCloseTo(t.max);
  });

  it("fades to neutral with the mip level and the distance", () => {
    expect(twigFactor(0.9, t.mipNear, 0)).toBeCloseTo(twigFactor(0.9, 0, 0));
    expect(twigFactor(0.9, t.mipFar, 0)).toBeCloseTo(1);
    expect(twigFactor(0.1, t.mipFar + 3, 0)).toBeCloseTo(1);
    expect(twigFactor(0.9, 0, t.far)).toBeCloseTo(1);
    const mid = twigFactor(0.9, (t.mipNear + t.mipFar) / 2, 0);
    expect(mid).toBeGreaterThan(1);
    expect(mid).toBeLessThan(twigFactor(0.9, 0, 0));
  });
});

describe("back light", () => {
  const r = CARD_LOOK.rim;
  const rimLinear = new Color(SECT_LOOK.trees.rim).multiplyScalar(SECT_LOOK.trees.rimStrength);
  const lum = (c: Color) => 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;

  it("leaves shade-baked texels dark", () => {
    // Shade pine needles in the mirror pilot: median graded brightness about 0.004.
    expect(rimAmount(1, 0.004, 0)).toBe(0);
    expect(rimAmount(1, r.litLo, 0)).toBe(0);
    expect(rimAmount(1, 0.012, 0)).toBeLessThan(0.1 * rimAmount(1, r.litHi, 0));
  });

  it("is a tight lobe around the sun", () => {
    expect(rimAmount(0, 0.2, 5)).toBe(0);
    expect(rimAmount(-0.5, 0.2, 5)).toBe(0);
    // 40 degrees off the sun: a quarter of the peak (it was 0.45 with the old cube).
    const off40 = rimAmount(Math.cos((40 * Math.PI) / 180), 0.2, 5) / rimAmount(1, 0.2, 5);
    expect(off40).toBeGreaterThan(0.2);
    expect(off40).toBeLessThan(0.3);
  });

  it("is strongest on thin edges, where a sunlit needle passes 1.0 for the bloom", () => {
    const inside = rimAmount(1, 0.2, 10);
    const edge = rimAmount(1, 0.2, 0);
    expect(inside).toBeCloseTo(r.base);
    expect(edge).toBeCloseTo(r.base + r.edge);
    const peak = rimLinear.clone().multiplyScalar(edge);
    // The rim alone: just under 1.0 luminance; with the needle's own baked colour, just over.
    expect(lum(peak)).toBeGreaterThan(0.8);
    expect(lum(peak)).toBeLessThan(1.0);
    expect(lum(peak) + 0.15).toBeGreaterThan(1.0);
    // Not a white-hot blow-out: the brightest channel stays under 1.5.
    expect(Math.max(peak.r, peak.g, peak.b)).toBeLessThan(1.5);
  });
});

describe("card GLSL", () => {
  it("keeps the sprites' alpha gain per mip level", () => {
    const g = cardSpriteBoostGlsl();
    expect(g).toContain(`1.0 + sectMip * ${glslFloat(0.22)}`);
    expect(g).toContain("vAlphaMapUv * uSectTexSize");
    expect(g).toContain("vMapUv * uSectTexSize");
  });

  it("reads a needle card's alpha map once, coverage from G, with the small gain", () => {
    const g = cardAlphaMapGlsl("needle");
    expect(count(g, "texture2D(")).toBe(1);
    expect(g).toContain("diffuseColor.a *= sectCut.g");
    expect(g).toContain(`sectMip * ${glslFloat(0.05)}`);
    expect(g).not.toContain("sectCut.r");
    expect(g).not.toContain("diffuseColor.rgb");
  });

  it("adds the twig's R detail to the colour, still from one read", () => {
    const g = cardAlphaMapGlsl("twig");
    expect(count(g, "texture2D(")).toBe(1);
    expect(g).toContain("diffuseColor.a *= sectCut.g");
    expect(g).toContain("2.0 * sectCut.r - 1.0");
    expect(g).toContain(`smoothstep( ${glslFloat(CARD_LOOK.twig.mipNear)}, ${glslFloat(CARD_LOOK.twig.mipFar)}, sectMip )`);
    expect(g).toContain("vSectCardWorld - cameraPosition");
    expect(g).toContain("diffuseColor.rgb *= mix( 1.0, sectTd, sectTf )");
  });

  it("sharpens needle and twig cut-outs and leaves sprites on three's test", () => {
    for (const kind of ["needle", "twig"] as const) {
      const g = cardAlphaTestGlsl(kind);
      expect(g).toContain("( diffuseColor.a - alphaTest ) / max( fwidth( diffuseColor.a ), 1e-4 )");
      expect(g).toContain("clamp( sectPx + 0.5, 0.0, 1.0 )");
      expect(g).toContain("if ( sectPx < 0.0 ) discard;");
      expect(g).toContain("#ifdef ALPHA_TO_COVERAGE");
      expect(g).not.toContain("#include <alphatest_fragment>");
    }
    const sprite = cardAlphaTestGlsl(null);
    expect(sprite).toContain("float sectPx = 1e4;");
    expect(sprite).toContain("#include <alphatest_fragment>");
    expect(sprite).not.toContain("discard");
    // sectPx is measured before three's test changes the alpha.
    expect(sprite.indexOf("fwidth")).toBeLessThan(sprite.indexOf("#include <alphatest_fragment>"));
  });

  it("gates the rim by the texel's brightness, with a tight lobe and an edge term", () => {
    const g = cardRimGlsl();
    expect(g).toContain(`pow( max( dot( sectV, uSectSun ), 0.0 ), ${glslFloat(5)} )`);
    expect(g).toContain(`smoothstep( ${glslFloat(CARD_LOOK.rim.litLo)}, ${glslFloat(CARD_LOOK.rim.litHi)}, max( diffuseColor.r`);
    expect(g).toContain("sectPx )");
    expect(g).toContain("outgoingLight += uSectRim *");
  });
});
