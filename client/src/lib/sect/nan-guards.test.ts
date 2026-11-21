import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { fogChunks, fogConstantsFromMeta, nonFiniteGlsl, POW_BASE_NOTE } from "./glsl";
import { parseMeta } from "./parse";

/**
 * The guards of 2026-11-18 (docs/sect/render-probe.md): on a Mac, pow of a base a hair under zero is
 * not a number, a pixel that is not a number is black, and bloom spreads it into a block. Windows
 * hides all of it, so nothing on the owner's PC would show these guards going missing.
 */
const src = (file: string) => readFileSync(`src/${file}`, "utf8").replace(/\r\n/g, "\n");

describe(POW_BASE_NOTE, () => {
  it("tests for a NaN or an Inf by its bits, which fast maths cannot fold away", () => {
    expect(nonFiniteGlsl("x", 1)).toBe("( ( floatBitsToUint( x ) & 0x7f800000u ) == 0x7f800000u )");
    expect(nonFiniteGlsl("c", 3)).toBe("any( equal( floatBitsToUint( c ) & uvec3( 0x7f800000u ), uvec3( 0x7f800000u ) ) )");
    expect(nonFiniteGlsl("t", 4)).toBe("any( equal( floatBitsToUint( t ) & uvec4( 0x7f800000u ), uvec4( 0x7f800000u ) ) )");
  });

  it("the fog chunk swaps a colour that is not a number for the haze's, after the haze and before the screen path", () => {
    const fs = fogChunks(fogConstantsFromMeta(parseMeta({}))).fog_fragment;
    const guard = fs.indexOf(`if ( ${nonFiniteGlsl("sectC", 3)} ) sectC = sectBase;`);
    expect(guard).toBeGreaterThan(fs.indexOf("sectC = sectAerial("));
    expect(guard).toBeLessThan(fs.indexOf("gl_FragColor.rgb = sectEncoded ?"));
  });

  it("the sky's sun side is held to 0..1 before its pow, on the dome and in the reflections", () => {
    const s = src("app/sect/experience/materials.ts");
    expect(s.match(/float sunSide = clamp\( dot\( dh, sunH \) \* 0\.5 \+ 0\.5, 0\.0, 1\.0 \);/g)?.length).toBe(2);
    expect(s).not.toContain("float sunSide = dot(");
    // The reflections' sky clamps the ray's height too, as the dome does, before asin.
    expect(s).toContain("vec3 sectEnvSky( vec3 d, float blur ) {\n  // Held to 1: a reflected ray's y can round to just over 1, and asin of that is not a number.\n  float h = clamp( d.y, 0.0, 1.0 );");
  });

  it("no pow is handed one minus a dot product, a life or another pow without a floor", () => {
    const files = [
      "app/sect/experience/materials.ts",
      "app/sect/experience/fx.tsx",
      "app/sect/experience/flames.tsx",
      "app/sect/experience/post/finish.ts",
      "app/sect/experience/post/ao.ts",
      "lib/sect/glsl.ts",
      "lib/sect/looks.ts",
      "lib/sect/veg.ts",
      "lib/sect/waterfall.ts",
    ];
    // What each of these lines read before the guard went in.
    const gone = [
      "pow( 1.0 - abs( dot(",
      "pow( 1.0 - max( dot(",
      "pow( 1.0 - v2, 4.0 )",
      "pow( 1.0 - v, FINISH_TOE_POWER )",
      "pow( 1.0 - vLife,",
      "pow( 1.0 - life,",
      "pow( sin(",
      "pow( 1.0 - k * (",
      "float facing = abs( dot( Ns, V ) );",
    ];
    for (const file of files) {
      const s = src(file);
      for (const g of gone) expect(s.includes(g), `${file}: ${g}`).toBe(false);
    }
    expect(src("lib/sect/veg.ts")).toContain("float facing = min( abs( dot( Ns, V ) ), 1.0 );");
    expect(src("lib/sect/waterfall.ts")).toContain("pow( 1.0 - clamp( dot( n, v ), 0.0, 1.0 ), 5.0 )");
  });
});
