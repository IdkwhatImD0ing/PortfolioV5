/**
 * three.js material setup for /sect: fog chunk replacement, the lit stand-in tone curve, the look's
 * grade on baked surfaces, the hotspot highlight, alpha-tested tree cards, still water with a
 * reflection, and the custom shaders (sky dome, moon, cloud sea, waterfalls, cloud puffs, mist,
 * light beams).
 * Only reachable through the dynamic import in sect-client.tsx, so three stays off other routes.
 */
import {
  AdditiveBlending,
  BackSide,
  Color,
  DataTexture,
  DoubleSide,
  ImageBitmapLoader,
  ImageLoader,
  LinearFilter,
  LinearMipmapLinearFilter,
  Material,
  Matrix4,
  MeshBasicMaterial,
  MeshStandardMaterial,
  RedFormat,
  RepeatWrapping,
  RGBAFormat,
  ShaderChunk,
  ShaderMaterial,
  SRGBColorSpace,
  Texture,
  UniformsLib,
  UniformsUtils,
  UnsignedByteType,
  Vector2,
  Vector3,
  Vector4,
  type IUniform,
  type Object3D,
} from "three";
import { cardAlphaKind, cardAlphaMapGlsl, cardAlphaTestGlsl, cardRimGlsl, cardSpriteBoostGlsl, isCutoutCard } from "@/lib/sect/card-shading";
import { DETAIL_NOISE, detailApplyGlsl, detailClass, detailGlsl, detailProgramKey, detailVertexGlsl, type DetailClass } from "@/lib/sect/detail";
import { domeGlsl } from "@/lib/sect/formation";
import {
  AGX_PUNCHY_GLSL,
  fogChunks,
  fogLibrary,
  glslFloat,
  glslVec3,
  hexToLinear,
  SCREEN_ADD_GLSL,
  SCREEN_CLIP_GLSL,
  type FogConstants,
} from "@/lib/sect/glsl";
import { heartMirrorGlsl, MIRROR_PART } from "@/lib/sect/heart-mirror";
import { gradeGlsl, SECT_LOOK, treeLiftGlsl, treeShadeGlsl, unitTint, type SectLook } from "@/lib/sect/look";
import { clumpField, groundNoise, tilingNoise } from "@/lib/sect/noise";
import type { Vec3 } from "@/lib/sect/types";
import type { WaterSurface } from "@/lib/sect/water";
import { fallGlsl, packWetFalls, selectWetFalls, SHEET, WET, wetArrays, wetRockGlsl, type WetFall } from "@/lib/sect/waterfall";
import { REFLECT } from "./reflect/plan";

let installedKey = "";

/** Swaps three's fog shader chunks for the height haze. Call before any material compiles. */
export function installFog(c: FogConstants): void {
  const key = JSON.stringify(c);
  if (key === installedKey) return;
  const chunks = fogChunks(c);
  const target = ShaderChunk as unknown as Record<string, string>;
  target.fog_pars_vertex = chunks.fog_pars_vertex;
  target.fog_vertex = chunks.fog_vertex;
  target.fog_pars_fragment = chunks.fog_pars_fragment;
  target.fog_fragment = chunks.fog_fragment;
  installedKey = key;
}

/** Exposure for lit stand-in materials (Blender: +0.25 stops on AgX Punchy). */
export function standInExposure(stops: number): number {
  return Math.pow(2, stops);
}

/**
 * Scene depth for soft edges (clouds, mist, beams): the composer's depth texture once it exists.
 * One shared set of uniforms, so every soft material follows the composer without re-wiring.
 */
export const SOFT_DEPTH = {
  tDepth: { value: null as Texture | null },
  uHasDepth: { value: 0 },
  uResolution: { value: new Vector2(1, 1) },
  uNear: { value: 0.5 },
  uFar: { value: 9000 },
};

const SOFT_PARS = /* glsl */ `
#include <packing>
uniform sampler2D tDepth;
uniform float uHasDepth;
uniform vec2 uResolution;
uniform float uNear;
uniform float uFar;
// 0 where the fragment touches the geometry behind it, 1 when it is \`len\` metres or more in front.
float sectSoftFade( float fragViewZ, float len ) {
  if ( uHasDepth < 0.5 ) return 1.0;
  float d = texture2D( tDepth, gl_FragCoord.xy / uResolution ).r;
  if ( d >= 1.0 ) return 1.0;
  float sceneZ = perspectiveDepthToViewZ( d, uNear, uFar );
  return smoothstep( 0.0, max( len, 1e-3 ), fragViewZ - sceneZ );
}
`;

/**
 * The sky the page's reflections see (the polished mirror, metal and glaze, the still water): the
 * dome's own uniforms, shared rather than copied (createSkyMaterial hands these objects to the dome),
 * so the sky image arriving and the twilight's colour blend reach every reflection at once.
 */
export const SECT_ENV = {
  tSectSky: { value: null as Texture | null },
  uSectSkyOn: { value: 0 },
  uSectEnvZenith: { value: linear(SECT_LOOK.sky.zenith) },
  uSectEnvMid: { value: linear(SECT_LOOK.sky.mid) },
  uSectEnvHorizon: { value: linear(SECT_LOOK.sky.horizon) },
  uSectEnvSunHorizon: { value: linear(SECT_LOOK.sky.sunHorizon) },
  uSectEnvGradeMix: { value: SECT_LOOK.sky.gradeMix },
  /** The haze colour (the dome's uFogColor). */
  uSectEnvHaze: { value: linear(SECT_LOOK.haze.color) },
  uSectEnvSunDir: { value: new Vector3(-0.94, 0.12, 0.31).normalize() },
  uSectEnvSunColor: { value: linear("#ffbf84") },
  uSectEnvGround: { value: linear(SECT_LOOK.surfaces.ground) },
  uSectEnvMountains: { value: linear(SECT_LOOK.surfaces.mountains) },
};

/**
 * After <fog_pars_fragment> (it uses the haze maths when the material is fogged): the sky along a
 * direction for reflections, and the sun in a surface. The sky is the dome's (createSkyMaterial)
 * without its moving clouds, plus what a reflection sees that the dome hides: a hazy ridge line of
 * far mountains a few degrees up, and a dim ground below the horizon. `blur` (0..1, the surface's
 * roughness) leans on the smooth painted gradient and softens the ridge.
 */
export const ENV_GLSL = /* glsl */ `
uniform sampler2D tSectSky;
uniform float uSectSkyOn;
uniform vec3 uSectEnvZenith;
uniform vec3 uSectEnvMid;
uniform vec3 uSectEnvHorizon;
uniform vec3 uSectEnvSunHorizon;
uniform float uSectEnvGradeMix;
uniform vec3 uSectEnvHaze;
uniform vec3 uSectEnvSunDir;
uniform vec3 uSectEnvSunColor;
uniform vec3 uSectEnvGround;
uniform vec3 uSectEnvMountains;
vec3 sectEnvSky( vec3 d, float blur ) {
  float h = max( d.y, 0.0 );
  float az = atan( d.z, d.x );
  vec3 col;
  if ( uSectSkyOn > 0.5 ) {
    // Explicit level: the water calls this inside a branch (the image has no mipmaps anyway).
    col = textureLod( tSectSky, vec2( az * 0.15915494 + 0.5, asin( h ) * 0.31830989 + 0.5 ), 0.0 ).rgb;
  } else {
    col = mix( uSectEnvHorizon, uSectEnvZenith, sqrt( h ) );
  }
  vec3 sunH = normalize( vec3( uSectEnvSunDir.x, 0.0, uSectEnvSunDir.z ) );
  vec3 dh = normalize( vec3( d.x, 0.0, d.z ) + vec3( 1e-5, 0.0, 0.0 ) );
  float sunSide = dot( dh, sunH ) * 0.5 + 0.5;
  vec3 grad = mix( uSectEnvHorizon, uSectEnvMid, smoothstep( 0.03, 0.22, h ) );
  grad = mix( grad, uSectEnvZenith, smoothstep( 0.18, 0.75, h ) );
  grad = mix( grad, uSectEnvSunHorizon, pow( sunSide, 4.0 ) * ( 1.0 - smoothstep( 0.0, 0.45, h ) ) );
  col = mix( col, grad, max( uSectEnvGradeMix, blur ) );
  vec3 haze = uSectEnvHaze;
#ifdef USE_FOG
  haze = sectHazeColor( uSectEnvHaze, d );
  col = mix( col, haze, 1.0 - exp( - sectHazeDepth( cameraPosition.y, max( d.y, 0.004 ), 40000.0 ) * SECT_SKY_HAZE ) );
#endif
  float soft = 0.003 + 0.04 * blur;
  float hl = dot( haze, vec3( 0.2126, 0.7152, 0.0722 ) );
  // Far ridges, their height wandering with the bearing; paler (hazier) toward their feet.
  float ridge = 0.045 + 0.028 * sin( az * 3.0 + 1.3 ) * sin( az * 7.0 + 0.4 ) + 0.016 * sin( az * 17.0 + 2.1 ) + 0.006 * sin( az * 43.0 );
  vec3 mtn = uSectEnvMountains * ( hl / max( dot( uSectEnvMountains, vec3( 0.2126, 0.7152, 0.0722 ) ), 1e-4 ) );
  col = mix( col, mix( mtn * 0.7, haze, 0.3 + 0.45 * smoothstep( ridge, -0.03, d.y ) ), 1.0 - smoothstep( ridge - soft, ridge + soft, d.y ) );
  // Nearer peaks: the forested pillars round every terrace, dark, rising well above the far ridge
  // here and there with gaps between.
  float pw = sin( az * 5.0 + 0.7 ) * sin( az * 11.0 + 2.3 ) + 0.45 * sin( az * 23.0 + 1.1 ) + 0.3 * sin( az * 61.0 + 0.2 );
  float pillar = 0.13 * pow( max( pw, 0.0 ), 0.6 ) + 0.012 * sin( az * 97.0 ) - 0.012;
  col = mix( col, mix( uSectEnvGround * 1.1, haze * 0.8, 0.32 ), 1.0 - smoothstep( pillar - soft, pillar + soft, d.y ) );
  // Below the horizon: the ground at hand, dim.
  return mix( col, uSectEnvGround, smoothstep( -0.02, -0.2, d.y ) );
}
// The sun seen in a surface of roughness rough (0 polished .. 1 matte): a hot core and a broad sheen.
vec3 sectEnvSun( vec3 r, float rough ) {
  float c = max( dot( r, uSectEnvSunDir ), 0.0 );
  float p = mix( 2400.0, 30.0, rough );
  return uSectEnvSunColor * ( pow( c, p ) * mix( 24.0, 1.2, rough ) + pow( c, 2.0 + p * 0.015 ) * 0.22 );
}
`;

/** Surfaces the page shades with the sky reflection (SECT_LOOK.surfaces). */
export type SectSurface = "mirror" | "metal" | "glaze" | "iron";

/**
 * The Heart-Mirror's disc (its glowing face's box as fitted for the pond, lib/sect/water.ts
 * discFromBox): set by createWaterUniforms, read by the mirror surface for its convex face. Radius 0
 * until the mirror's area has loaded (the face is then shaded flat).
 *
 * On High and Medium the face also reflects its real surroundings: a cube map captured from just in
 * front of it (reflect/probe.ts sets these): the map, how far it is faded in (0 = the analytic sky
 * alone, as on Low), the capture point, and the face's own plane fitted to its triangles
 * (water.ts discFromTriangles: centre, normal toward the pond, radius).
 */
export const SECT_MIRROR = {
  uSectMirrorC: { value: new Vector3() },
  uSectMirrorN: { value: new Vector3(0, 0, 1) },
  uSectMirrorR: { value: 0 },
  tSectMirrorEnv: { value: null as Texture | null },
  uSectMirrorEnvOn: { value: 0 },
  uSectMirrorEnvP: { value: new Vector3() },
  uSectMirrorEnvC: { value: new Vector3() },
  uSectMirrorEnvN: { value: new Vector3(0, 0, 1) },
  uSectMirrorEnvR: { value: 1 },
};

const MIRROR_PARS = /* glsl */ `
uniform vec3 uSectMirrorC;
uniform vec3 uSectMirrorN;
uniform float uSectMirrorR;
uniform samplerCube tSectMirrorEnv;
uniform float uSectMirrorEnvOn;
uniform vec3 uSectMirrorEnvP;
uniform vec3 uSectMirrorEnvC;
uniform vec3 uSectMirrorEnvN;
uniform float uSectMirrorEnvR;
`;

const MIRROR_FACE = /\.glow\.mirror_face$/i;

/**
 * A baked material's reflective class: what the exporter tagged (extras.sectSurface "metal" or
 * "glaze", in userData after loading) or a hotspot's copy was given (prepare.ts: "iron", look.ts
 * hotspotSurface), or the Heart-Mirror's face by name. Null for the rest, which keep the plain bake.
 */
export function sectSurfaceOf(mat: Material): SectSurface | null {
  const tag = mat.userData?.sectSurface;
  if (tag === "metal" || tag === "glaze" || tag === "mirror" || tag === "iron") return tag;
  return MIRROR_FACE.test(mat.name) ? "mirror" : null;
}

/** Near pine materials (trunks and needle pads, twig cards): lifted toward the far cards' level. */
export function isNearTreeMaterial(mat: Material): boolean {
  return /^trees\.(mesh|needle)\./i.test(mat.name);
}

/** The far tree cards (trees.cards.<area>): their shade matches the near pines' (look.ts trees.shade). */
export function isTreeCardMaterial(mat: Material): boolean {
  return /^trees\.cards\./i.test(mat.name);
}

const LUMA_GLSL = "vec3( 0.2126, 0.7152, 0.0722 )";

/**
 * Before <opaque_fragment> in a baked material of reflective class `kind`: the flat face normal (the
 * files carry no normals; derivatives give each triangle's), the view's reflection, Schlick's
 * Fresnel, then the class's mix of bake and reflection (SECT_LOOK.surfaces). The bake's brightness
 * stands in for occlusion: a surface baked dark (in shade, under eaves) sees less sky and no sun.
 */
export function surfaceGlsl(kind: SectSurface, s: SectLook["surfaces"] = SECT_LOOK.surfaces): string {
  const f = glslFloat;
  const head = /* glsl */ `
  {
    vec3 sN = normalize( cross( dFdx( vSectWorld ), dFdy( vSectWorld ) ) );
    vec3 sV = normalize( vSectWorld - cameraPosition );
    if ( dot( sN, sV ) > 0.0 ) sN = - sN;
    vec3 sR = reflect( sV, sN );
    float sF5 = pow( 1.0 - clamp( - dot( sV, sN ), 0.0, 1.0 ), 5.0 );
    float sLum = dot( sectTexel, ${LUMA_GLSL} );
    float sOcc = mix( 0.45, 1.0, smoothstep( 0.02, 0.22, sLum ) );
    float sLit = smoothstep( 0.06, 0.3, sLum );`;
  let body: string;
  if (kind === "mirror") {
    const m = s.mirror;
    const e = REFLECT.mirror.look;
    body = /* glsl */ `
    // A bronze mirror's face is slightly convex: its normal leans outward toward the rim, so the
    // face shows a wide view (sky above, the peaks and ground below) instead of one flat colour.
    vec3 sFaceN = sN;
    vec3 sGlow = outgoingLight * ${f(m.glow)};
    float sEdge = 0.0;
    if ( uSectMirrorR > 0.0 ) {
      vec3 sOff = vSectWorld - uSectMirrorC;
      sOff -= uSectMirrorN * dot( sOff, uSectMirrorN );
      sEdge = length( sOff ) / uSectMirrorR;
      sN = normalize( sN + sOff / uSectMirrorR * ${f(m.convex)} * sign( dot( sN, uSectMirrorN ) + 1e-4 ) );
      sR = reflect( sV, sN );
      sF5 = pow( 1.0 - clamp( - dot( sV, sN ), 0.0, 1.0 ), 5.0 );
    }
    vec3 sF0 = ${glslVec3(hexToLinear(m.f0))};
    vec3 sF = sF0 + ( 1.0 - sF0 ) * sF5;
    outgoingLight = sF * ( sectEnvSky( sR, ${f(m.rough)} ) + sectEnvSun( sR, ${f(m.rough)} ) ) + sGlow;
    // Toward the rim the polish gives way to a darker, browner patina.
    outgoingLight *= mix( vec3( 1.0 ), vec3( 0.62, 0.5, 0.4 ), smoothstep( 0.45, 0.75, sEdge ) );
    if ( uSectMirrorEnvOn > 0.0 ) {
      // The real surroundings (High and Medium): the cube map captured just in front of the face,
      // read along the view reflected off a gently convex face, met with a sphere round the capture
      // point so near things sit where they should; a touch of a blurrier level for the bronze's
      // polish, bronze-tinted by Fresnel, the sun's glint on top, the patina toward the rim.
      vec3 eOff = vSectWorld - uSectMirrorEnvC;
      eOff -= uSectMirrorEnvN * dot( eOff, uSectMirrorEnvN );
      float eEdge = length( eOff ) / uSectMirrorEnvR;
      vec3 eN = normalize( sFaceN + eOff / uSectMirrorEnvR * ${f(e.convex)} * sign( dot( sFaceN, uSectMirrorEnvN ) + 1e-4 ) );
      vec3 eR = reflect( sV, eN );
      vec3 eP = vSectWorld - uSectMirrorEnvP;
      float eB = dot( eP, eR );
      vec3 eDir = eP + eR * ( - eB + sqrt( max( eB * eB - dot( eP, eP ) + ${f(e.parallax * e.parallax)}, 0.0 ) ) );
      vec3 eEnv = mix( texture( tSectMirrorEnv, eDir, ${f(e.bias)} ).rgb, textureLod( tSectMirrorEnv, eDir, ${f(e.hazeLod)} ).rgb, ${f(e.haze)} );
      float eF5 = pow( 1.0 - clamp( - dot( sV, eN ), 0.0, 1.0 ), 5.0 );
      vec3 eF0 = ${glslVec3([...e.f0])};
      vec3 eF = eF0 + ( 1.0 - eF0 ) * eF5;
      vec3 eCol = eF * ( eEnv * ${f(e.gain)} + sectEnvSun( eR, ${f(m.rough)} ) * ${f(e.sun)} ) + sGlow * ${f(e.glow)};
      eCol *= mix( vec3( 1.0 ), vec3( 0.62, 0.5, 0.4 ), smoothstep( ${f(e.patina[0])}, ${f(e.patina[1])}, eEdge ) );
      outgoingLight = mix( outgoingLight, eCol, uSectMirrorEnvOn );
    }`;
  } else if (kind === "metal") {
    const m = s.metal;
    body = /* glsl */ `
    // The texel's hue tints the reflectance (gold trim gold, steel grey).
    vec3 sF0 = clamp( mix( vec3( 1.0 ), sectTexel / max( sLum, 1e-4 ), 0.85 ) * ${f(m.f0)}, 0.0, 1.0 );
    vec3 sF = sF0 + ( 1.0 - sF0 ) * sF5;
    // Metal baked dark sits in shade or is dark iron: it sees (and shows) less of the sky.
    outgoingLight = outgoingLight * ${f(m.diffuse)} + sF * ( sectEnvSky( sR, ${f(m.rough)} ) * sOcc * sOcc + sectEnvSun( sR, ${f(m.rough)} ) * sLit );`;
  } else if (kind === "iron") {
    const i = s.iron;
    body = /* glsl */ `
    // Black iron, dull: the bake's light as the shape only (its hue is the grade's slate), pressed
    // to near-black and leaned dark red; a rough oxide's faint sheen of the sky and the sun on top,
    // reddening where the faces turn away (the rounded edges glint dark red against the cliff).
    float iL = dot( outgoingLight, ${LUMA_GLSL} ) * ${f(i.diffuse)};
    vec3 iCol = mix( vec3( iL ), iL * ${glslVec3(unitTint(i.color))}, ${f(i.warmth)} );
    float iF = ${f(i.f0)} + ${f(i.grazing - i.f0)} * sF5;
    vec3 iSheen = iF * ( sectEnvSky( sR, ${f(i.rough)} ) * sOcc * sOcc + sectEnvSun( sR, ${f(i.rough)} ) * sLit );
    outgoingLight = iCol + iSheen * mix( vec3( 1.0 ), ${glslVec3(unitTint(i.glint.color))}, ${f(i.glint.amount)} * sF5 );`;
  } else {
    const g = s.glaze;
    body = /* glsl */ `
    // A clear coat: what it reflects replaces the bake's diffuse in that share. Far away the sheen
    // softens (one triangle's normal per pixel would shimmer).
    float sF = min( ${f(g.f0)} + ${f(1 - g.f0)} * sF5, ${f(g.max)} ) * ( 1.0 - 0.5 * smoothstep( 150.0, 700.0, length( vSectWorld - cameraPosition ) ) );
    outgoingLight = mix( outgoingLight, sectEnvSky( sR, ${f(g.rough)} ) * sOcc, sF ) + sectEnvSun( sR, ${f(g.rough)} ) * sLit * sF;`;
  }
  return `${head}${body}\n  }`;
}

export interface PatchOptions {
  /** Apply the AgX Punchy curve to a lit (MeshStandardMaterial) material. */
  lit: boolean;
  exposure: number;
  highlight?: IUniform<number>;
  /** Still water in this material: a reflection of the sky and the glowing mirror. */
  water?: WaterUniforms;
  /** Tiling scan detail on a baked rock or ground surface (lib/sect/detail.ts). */
  detail?: DetailPatch;
}

/**
 * The shared detail texture, and 1 once its image has arrived (0 draws no photo detail); the
 * layers' runtime textures, clock and sun; and their switches (lib/sect/detail.ts). One object for
 * every rock and ground material, so a value set here (window.__sect.ctx.detail) reaches them all.
 */
export interface DetailUniforms {
  tSectDetail: IUniform<Texture>;
  uSectDetailOn: IUniform<number>;
  /** getClumpTexture and getGroundNoiseTexture. */
  tSectClump: IUniform<Texture>;
  tSectGroundNoise: IUniform<Texture>;
  /** Seconds (the waterfalls' clock, 0 with reduced motion): the wind sheen drifts with it. */
  uSectTime: IUniform<number>;
  /** Toward the sun (three space, unit): the sheen is stronger looking toward it. */
  uSectSun: IUniform<Vector3>;
  /** 1 = on, 0 = off: the clumps, patches and sheen (ground and mossy rock). */
  uSectGroundLayers: IUniform<number>;
  /** 1 = on, 0 = off: the far rock layer. */
  uSectRockFar: IUniform<number>;
  /** The far rock layer's octaves: 2 on high, 1 on mid (detail.ts rockFarOctaves). */
  uSectRockOctaves: IUniform<number>;
}

/**
 * The detail uniforms around the photo detail texture `tex` (drawn once uSectDetailOn is 1), with
 * the layers on, the page's clock and sun shared (not copied), and `rockOctaves` far rock octaves.
 */
export function createDetailUniforms(tex: Texture, o: { time: IUniform<number>; sunDir: Vector3; rockOctaves: number }): DetailUniforms {
  return {
    tSectDetail: { value: tex },
    uSectDetailOn: { value: 0 },
    tSectClump: { value: getClumpTexture() },
    tSectGroundNoise: { value: getGroundNoiseTexture() },
    uSectTime: o.time,
    uSectSun: { value: o.sunDir },
    uSectGroundLayers: { value: 1 },
    uSectRockFar: { value: 1 },
    uSectRockOctaves: { value: o.rockOctaves },
  };
}

export interface DetailPatch {
  kind: DetailClass;
  /** Empty for roof tiles on the low tier (their layer reads no uniform). */
  uniforms: Partial<DetailUniforms>;
}

/**
 * The detail option for a baked material the exporter tagged (extras.detail). Roof tile courses read
 * no texture or uniform, so they are drawn on every tier, low too (no detail uniforms there: without
 * the layer its roofs were flat dark sheets); the other classes need the detail uniforms.
 */
export function bakedDetail(mat: Material, uniforms: DetailUniforms | null | undefined): DetailPatch | undefined {
  const kind = detailClass(mat.userData?.detail);
  if (kind === "tiles") return { kind, uniforms: uniforms ?? {} };
  return kind && uniforms ? { kind, uniforms } : undefined;
}

const TONE_HELPERS = (exposure: number) => /* glsl */ `
${AGX_PUNCHY_GLSL}
vec3 sectToneMap( vec3 c, vec3 emissive ) {
  vec3 e = emissive * ${glslFloat(exposure)};
  // Strong emitters keep their energy above 1.0 so bloom picks them up.
  return sectAgxPunchy( c * ${glslFloat(exposure)} ) + max( e - 0.8, 0.0 ) * 1.5;
}
`;

const GRADE_GLSL = gradeGlsl(SECT_LOOK.grade);

const WATER_PARS = /* glsl */ `
uniform float uWaterLevel;
uniform vec3 uDiscC;
uniform vec3 uDiscN;
uniform float uDiscR;
uniform vec3 uDiscGlow;
uniform vec3 uDiscRim;
uniform vec3 uDiscRimOuter;
uniform vec3 uDiscRune;
uniform vec3 uDiscBronze;
uniform vec3 uWaterSkyLow;
uniform vec3 uWaterSkyHigh;
uniform sampler2D tReflect;
uniform float uHasReflect;
uniform mat4 uReflectMatrix;
uniform vec4 uReflectClamp;
uniform vec2 uReflectTexel;
uniform vec2 uPondMin;
uniform vec2 uPondMax;
uniform float uWaterTime;
#define SECT_POND_MIRROR_F0 ${glslVec3(hexToLinear(SECT_LOOK.surfaces.mirror.f0))}
#define SECT_POND_MIRROR_GLOW ${glslFloat(SECT_LOOK.surfaces.mirror.glow * 0.5)}
// The pond's normal at wp: gentle ripples drifting with the clock wt (still on Low, whose clock is
// never set), calmed out with the distance from the camera.
vec3 sectPondNormal( vec2 wp, float wt, float dist ) {
  vec2 g = vec2( 0.94, 0.34 ) * cos( dot( wp, vec2( 0.94, 0.34 ) ) * 2.6 - wt * 1.1 );
  g += vec2( -0.42, 0.91 ) * cos( dot( wp, vec2( -0.42, 0.91 ) ) * 3.9 - wt * 1.4 ) * 0.7;
  g += vec2( 0.17, -0.98 ) * cos( dot( wp, vec2( 0.17, -0.98 ) ) * 6.1 - wt * 1.9 ) * 0.45;
  g += vec2( -0.83, -0.56 ) * cos( dot( wp, vec2( -0.83, -0.56 ) ) * 7.7 + wt * 1.6 ) * 0.35;
  g *= ${glslFloat(REFLECT.pond.look.slope)} * ( 1.0 - smoothstep( ${glslFloat(REFLECT.pond.look.calm[0])}, ${glslFloat(REFLECT.pond.look.calm[1])}, dist ) );
  return normalize( vec3( - g.x, 1.0, - g.y ) );
}
`;

// Two paths, picked per frame by uHasReflect.
//
// Planar (High and Medium, while the page renders the pond's reflection: reflect/pond.ts): open
// water is told by geometry alone: on the water plane to within a centimetre (lily pads float 4-5 cm
// up, stones stand out), level, and inside the open water's bounds (the area's atlas material is
// shared well beyond the pond). Gentle drifting ripples tilt the normal; the reflected ray, so tilted,
// reads the mirrored camera's image where it would meet things `reach` metres off; Schlick's Fresnel
// lays it over the bake, darkened and cooled for a deep pond.
//
// Analytic (Low, and whenever no planar reflection was rendered this frame): open water = level,
// flat and dark texels at the water height. The reflected view ray picks up the page's sky
// (ENV_GLSL, dimmed: the pond is dark and a little rippled). Where it meets the Heart-Mirror's
// plane, the mirror itself is drawn from its layout (lib/sect/heart-mirror.ts: arms, rim, runes,
// face, crest, cradle) and shaded by sectMirrorShade, softened over the pixel's footprint there and
// laid on the water with the planar path's Fresnel and gain, so it reads as High's reflection does.
const POND = REFLECT.pond.look;
/** Extra softness of the analytic mirror in the water (m on its face): the planar image's blur. */
const POND_MIRROR_SOFT = 0.08;
const WATER_FRAGMENT = /* glsl */ `
  {
    vec3 sectDx = dFdx( vSectWorld );
    vec3 sectDy = dFdy( vSectWorld );
    vec3 sectN = normalize( cross( sectDx, sectDy ) );
    if ( uHasReflect > 0.5 ) {
      vec2 sectIn = step( uPondMin, vSectWorld.xz ) * step( vSectWorld.xz, uPondMax );
      float sectW = ( 1.0 - smoothstep( 0.008, 0.016, abs( vSectWorld.y - uWaterLevel ) ) )
        * smoothstep( 0.97, 0.995, abs( sectN.y ) ) * sectIn.x * sectIn.y;
      if ( sectW > 0.0 ) {
        vec3 v = normalize( vSectWorld - cameraPosition );
        vec3 n = sectPondNormal( vSectWorld.xz, uWaterTime, length( vSectWorld - cameraPosition ) );
        vec3 rr = reflect( v, n );
        float F = ${glslFloat(POND.f0)} + ${glslFloat(1 - POND.f0)} * pow( 1.0 - clamp( - dot( v, n ), 0.0, 1.0 ), 5.0 );
        vec4 rp = uReflectMatrix * vec4( vSectWorld + rr * ${glslFloat(POND.reach)}, 1.0 );
        // Four bilinear taps on a rotated grid: a soft filter over the reduced-resolution image.
        vec2 ruv = rp.xy / rp.w;
        vec2 rt = uReflectTexel * 0.6;
        vec3 rc = 0.25 * (
          textureLod( tReflect, clamp( ruv + rt * vec2( 1.0, 0.33 ), uReflectClamp.xy, uReflectClamp.zw ), 0.0 ).rgb
          + textureLod( tReflect, clamp( ruv + rt * vec2( -0.33, 1.0 ), uReflectClamp.xy, uReflectClamp.zw ), 0.0 ).rgb
          + textureLod( tReflect, clamp( ruv - rt * vec2( 1.0, 0.33 ), uReflectClamp.xy, uReflectClamp.zw ), 0.0 ).rgb
          + textureLod( tReflect, clamp( ruv - rt * vec2( -0.33, 1.0 ), uReflectClamp.xy, uReflectClamp.zw ), 0.0 ).rgb );
        vec3 deep = outgoingLight * ${glslVec3([...POND.deep])};
        outgoingLight = mix( outgoingLight, deep * ( 1.0 - F ) + rc * ( F * ${glslFloat(POND.gain)} ), sectW );
      }
    } else {
      float sectW = ( 1.0 - smoothstep( 0.03, 0.07, abs( vSectWorld.y - uWaterLevel ) ) )
        * smoothstep( 0.97, 0.995, abs( sectN.y ) )
        * ( 1.0 - smoothstep( 0.05, 0.14, dot( outgoingLight, vec3( 0.2126, 0.7152, 0.0722 ) ) ) );
      if ( sectW > 0.0 ) {
        vec3 v = normalize( vSectWorld - cameraPosition );
        float dist = length( vSectWorld - cameraPosition );
        // The planar path's ripples (still here), so the reflection wavers as High's does: stretched
        // up and down rather than torn sideways.
        vec3 r = reflect( v, sectPondNormal( vSectWorld.xz, uWaterTime, dist ) );
        float F = 0.02 + 0.98 * pow( 1.0 - clamp( - v.y, 0.0, 1.0 ), 5.0 );
        vec3 refl = mix( sectEnvSky( r, 0.25 ), mix( uWaterSkyLow, uWaterSkyHigh, smoothstep( 0.0, 0.5, r.y ) ), 0.25 ) * 0.4;
        vec3 water = mix( outgoingLight, refl, F );
        float dn = dot( r, uDiscN );
        if ( uDiscR > 0.0 && abs( dn ) > 1e-4 ) {
          float t = dot( uDiscC - vSectWorld, uDiscN ) / dn;
          if ( t > 0.0 ) {
            // The face's frame as the ray meets it (from behind: the back, mirrored), the point in the
            // layout's metres, the pixel's footprint there (its angle from the water's derivatives, over
            // the whole path) and the ray's slope for what stands off the plane.
            SectMirrorView m;
            m.back = dn > 0.0 ? 1.0 : 0.0;
            m.n = dn > 0.0 ? - uDiscN : uDiscN;
            m.y = normalize( vec3( 0.0, 1.0, 0.0 ) - uDiscN * uDiscN.y );
            m.x = cross( m.y, m.n );
            m.r = r;
            float scale = uDiscR / SECT_HEART_FACE;
            vec3 h = vSectWorld + r * t - uDiscC;
            vec2 q = vec2( dot( h, m.x ), dot( h, m.y ) ) / scale;
            float ang = max( length( sectDx - v * dot( sectDx, v ) ), length( sectDy - v * dot( sectDy, v ) ) ) / dist;
            float w = 0.5 * ang * ( dist + t ) / max( abs( dn ), 0.25 ) / scale + ${glslFloat(POND_MIRROR_SOFT)};
            vec4 mc = sectHeartMirror( q, w, dot( r, m.y ) / abs( dn ), m );
            // In the water as the planar path lays a reflection on it: Schlick's Fresnel, the gain.
            float Fm = ${glslFloat(POND.f0)} + ${glslFloat(1 - POND.f0)} * pow( 1.0 - clamp( - v.y, 0.0, 1.0 ), 5.0 );
            water = water * ( 1.0 - mc.a ) + outgoingLight * ( 1.0 - Fm ) * mc.a + mc.rgb * ( Fm * ${glslFloat(POND.gain)} );
          }
        }
        outgoingLight = mix( outgoingLight, water, sectW );
      }
    }
  }
`;

const POND_FACE = SECT_LOOK.surfaces.mirror;

/**
 * After ENV_GLSL in a pond material: the Heart-Mirror's layout (lib/sect/heart-mirror.ts) and how
 * each part looks there, lit as the bake lights it (the low western sun, the sky above). The face is
 * the mirror's own sky-only shading (surfaceGlsl: polished bronze, its faint glow, the patina toward
 * the rim) along the water's ray, but with High's cube path's gentle lean and narrower patina: seen
 * from the water the sky-only path's stronger lean bounced the face's lower half down to the ground
 * and the peaks, a dark band over the reflection's top on the approach, where High's shows sky.
 * The runes glow cyan; the gilt rim, crest, pearls and cradle also carry the sky in their metal; the
 * arms are red lacquer, the back dark bronze.
 */
const POND_MIRROR_GLSL = /* glsl */ `${heartMirrorGlsl()}
vec3 sectMirrorShade( int part, vec2 q, vec2 lean, SectMirrorView m ) {
  vec3 col = uDiscRune;
  if ( part == ${MIRROR_PART.face} ) {
    vec3 fn = normalize( m.n + ( m.x * q.x + m.y * q.y ) * ${glslFloat(REFLECT.mirror.look.convex)} / SECT_HEART_FACE );
    vec3 fr = reflect( m.r, fn );
    float fc = clamp( - dot( m.r, fn ), 0.0, 1.0 );
    vec3 f0 = SECT_POND_MIRROR_F0;
    col = ( f0 + ( 1.0 - f0 ) * pow( 1.0 - fc, 5.0 ) ) * ( sectEnvSky( fr, ${glslFloat(POND_FACE.rough)} ) + sectEnvSun( fr, ${glslFloat(POND_FACE.rough)} ) )
      + uDiscGlow * SECT_POND_MIRROR_GLOW;
    col *= mix( vec3( 1.0 ), vec3( 0.62, 0.5, 0.4 ), smoothstep( ${glslFloat(REFLECT.mirror.look.patina[0])}, ${glslFloat(REFLECT.mirror.look.patina[1])}, length( q ) / SECT_HEART_FACE ) );
  } else if ( part != ${MIRROR_PART.runes} ) {
    vec3 n = normalize( m.x * lean.x + m.y * lean.y + m.n * sqrt( max( 1.0 - dot( lean, lean ), 0.0 ) ) );
    float sun = max( dot( n, uSectEnvSunDir ), 0.0 );
    float sky = 0.5 + 0.5 * n.y;
    if ( part == ${MIRROR_PART.lacquer} ) {
      col = uDiscRimOuter * ( 0.6 * sky + 1.8 * sun );
    } else if ( part == ${MIRROR_PART.bronze} ) {
      col = uDiscBronze * ( 0.5 * sky + 1.2 * sun );
    } else {
      vec3 gr = reflect( m.r, n );
      col = uDiscRim * ( 0.3 * sky + 0.8 * sun + 0.7 * sectEnvSky( gr, 0.35 ) + 0.3 * sectEnvSun( gr, 0.35 ) );
    }
  }
  return col;
}
`;

const WORLD_VARYING_VERTEX = /* glsl */ `
  {
    vec4 sectWp = vec4( transformed, 1.0 );
    #ifdef USE_INSTANCING
      sectWp = instanceMatrix * sectWp;
    #endif
    vSectWorld = ( modelMatrix * sectWp ).xyz;
  }
`;

/**
 * Patches a material's shader. Lit stand-in materials get the AgX Punchy curve before fog (so the
 * fog colours, picked from Blender renders, stay exact). Unlit baked materials get the look's
 * grade on their texel or vertex colour (not on the material colour, so glow multipliers above 1
 * survive for bloom), then the tiling scan detail on rock and ground, then (not on tree cards or
 * glow surfaces) the wet darkening beside and behind the nearest waterfalls (SECT_WET). Hotspot
 * materials get a gold edge glow when highlighted.
 */
export function patchMaterial(mat: Material, opts: PatchOptions): void {
  const lit = opts.lit && (mat as MeshStandardMaterial).isMeshStandardMaterial === true;
  const grade = (mat as MeshBasicMaterial).isMeshBasicMaterial === true;
  const hl = opts.highlight;
  if (!lit && !hl && !grade) return;
  const water = grade ? opts.water : undefined;
  const detail = grade ? opts.detail : undefined;
  const wet = grade && !isCutoutCard(mat.userData) && !((mat as MeshBasicMaterial).alphaTest > 0);
  const tree = grade && isNearTreeMaterial(mat);
  // The far tree cards take the same shade as the near pines beside them (not the lift).
  const shade = tree || (grade && isTreeCardMaterial(mat));
  const key = `sect|${lit ? `agx${opts.exposure.toFixed(3)}` : "flat"}|${grade ? "grade" : ""}|${hl ? "hl" : ""}|${water ? "water" : ""}|${
    detail ? `detail-${detail.kind}-${detailProgramKey(detail.kind)}` : ""
  }${wet ? "|wet" : ""}${tree ? "|tree" : ""}${shade ? "|shade" : ""}`;
  const hover = new Color(SECT_LOOK.hover);
  // The reflective class is read when the shader compiles (and by the cache key), so a material
  // tagged after loading picks it up at its next compile (needsUpdate).
  const surfaceNow = () => (grade && !water ? sectSurfaceOf(mat) : null);
  mat.onBeforeCompile = (shader) => {
    const surface = surfaceNow();
    if (hl) {
      shader.uniforms.uSectHighlight = hl;
      shader.uniforms.uSectHover = { value: hover };
    }
    if (water) Object.assign(shader.uniforms, water);
    if (detail) Object.assign(shader.uniforms, detail.uniforms);
    if (wet) Object.assign(shader.uniforms, SECT_WET);
    const env = !!water || !!surface;
    if (env) Object.assign(shader.uniforms, SECT_ENV);
    if (surface === "mirror") Object.assign(shader.uniforms, SECT_MIRROR);
    const needWorld = !!water || !!hl || !!detail || wet || !!surface;
    if (needWorld) {
      // Paving also passes its slab coordinates (uv1) on (detail.ts detailVertexGlsl; empty for rock and ground).
      const dv = detail ? detailVertexGlsl(detail.kind) : { pars: "", main: "" };
      shader.vertexShader = shader.vertexShader
        .replace("#include <common>", `#include <common>\nvarying vec3 vSectWorld;\n${dv.pars}`)
        .replace("#include <project_vertex>", `#include <project_vertex>\n${WORLD_VARYING_VERTEX}${dv.main}`);
    }
    let fs = shader.fragmentShader;
    const header = `${lit ? TONE_HELPERS(opts.exposure) : ""}${grade ? GRADE_GLSL : ""}${water ? WATER_PARS : ""}${
      hl ? "uniform float uSectHighlight;\nuniform vec3 uSectHover;\n" : ""
    }${needWorld ? "varying vec3 vSectWorld;\n" : ""}${detail ? detailGlsl(detail.kind) : ""}${wet ? WET_GLSL : ""}${tree ? TREE_LIFT_GLSL : ""}${shade ? TREE_SHADE_GLSL : ""}${
      surface === "mirror" ? MIRROR_PARS : ""
    }`;
    fs = fs.replace("#include <common>", `#include <common>\n${header}`);
    if (env) fs = fs.replace("#include <fog_pars_fragment>", `#include <fog_pars_fragment>\n${ENV_GLSL}${water ? POND_MIRROR_GLSL : ""}`);
    if (lit) {
      fs = fs.replace(
        "#include <tonemapping_fragment>",
        "gl_FragColor.rgb = sectToneMap( gl_FragColor.rgb, totalEmissiveRadiance );",
      );
    }
    if (grade) {
      fs = fs.replace(
        "#include <color_fragment>",
        [
          "#include <color_fragment>",
          // The texel before the grade: the detail's mossy-rock test reads it (the grade tames green).
          "  vec3 sectTexel = diffuseColor.rgb / max( diffuse, vec3( 1e-4 ) );",
          // Near pines: their dark needles lifted toward the far cards' level (look.ts treeLiftLinear).
          tree ? "  sectTexel = sectTreeLift( sectTexel );" : "",
          "  vec3 sectGraded = sectGrade( sectTexel );",
          // Tree shade deep green instead of the grade's slate (look.ts treeShadeLinear).
          shade ? "  sectGraded = sectTreeShade( sectGraded, sectTexel );" : "",
          // Glow surfaces (material colour > 1) keep a little extra colour, so they read gold /
          // amber / jade rather than white once bloom and the hue-preserving clip are applied.
          "  if ( max( diffuse.r, max( diffuse.g, diffuse.b ) ) > 1.001 ) {",
          "    float sectL = dot( sectGraded, vec3( 0.2126, 0.7152, 0.0722 ) );",
          "    sectGraded = max( vec3( sectL ) + ( sectGraded - vec3( sectL ) ) * 1.25, 0.0 );",
          "  }",
          "  diffuseColor.rgb = sectGraded * diffuse;",
          // Fine detail and the layers the atlas cannot hold (they fog with the rest: fog runs later).
          detail ? detailApplyGlsl(detail.kind) : "",
          // Wet rock beside the falls (a uniform test: glow surfaces stay as they are).
          wet ? "  if ( max( diffuse.r, max( diffuse.g, diffuse.b ) ) <= 1.001 ) diffuseColor.rgb = sectWetRock( diffuseColor.rgb, vSectWorld );" : "",
        ].join("\n"),
      );
    }
    if (water) fs = fs.replace("#include <opaque_fragment>", `${WATER_FRAGMENT}\n#include <opaque_fragment>`);
    if (surface) fs = fs.replace("#include <opaque_fragment>", `${surfaceGlsl(surface)}\n#include <opaque_fragment>`);
    if (hl) {
      // Gold edge glow (Fresnel on the flat face normal) plus a faint warm lift: visible on white
      // marble, where an additive brighten was not.
      fs = fs.replace(
        "#include <dithering_fragment>",
        [
          "#include <dithering_fragment>",
          "  if ( uSectHighlight > 0.001 ) {",
          "    vec3 sectFn = normalize( cross( dFdx( vSectWorld ), dFdy( vSectWorld ) ) );",
          "    vec3 sectV = normalize( cameraPosition - vSectWorld );",
          "    float sectFr = pow( 1.0 - abs( dot( sectFn, sectV ) ), 2.0 );",
          "    gl_FragColor.rgb = mix( gl_FragColor.rgb, gl_FragColor.rgb * 0.88 + uSectHover * 0.22, uSectHighlight * 0.6 );",
          "    gl_FragColor.rgb += uSectHover * sectFr * uSectHighlight * 1.6;",
          "  }",
        ].join("\n"),
      );
    }
    shader.fragmentShader = fs;
  };
  mat.customProgramCacheKey = () => {
    const surface = surfaceNow();
    return surface ? `${key}|surface-${surface}` : key;
  };
  mat.needsUpdate = true;
}

const TREE_LIFT_GLSL = treeLiftGlsl(SECT_LOOK.trees.lift);
const TREE_SHADE_GLSL = treeShadeGlsl(SECT_LOOK.trees.shade);

export type WaterUniforms = Record<string, IUniform>;

/**
 * A pond material's water uniforms. The planar path's (tReflect, uHasReflect, uReflectMatrix, the
 * texture's valid rectangle uReflectClamp and its texel uReflectTexel, the open water's bounds uPondMin / uPondMax and the
 * ripples' clock uWaterTime) are set each frame by reflect/pond.ts; the rest is the analytic path's.
 */
export function createWaterUniforms(w: WaterSurface): WaterUniforms {
  const look = SECT_LOOK.water;
  const glow = linear(look.mirrorGlow).multiplyScalar(look.mirrorGlowGain);
  if (w.disc) {
    SECT_MIRROR.uSectMirrorC.value.set(...w.disc.center);
    SECT_MIRROR.uSectMirrorN.value.set(...w.disc.normal).normalize();
    SECT_MIRROR.uSectMirrorR.value = w.disc.radius;
  }
  return {
    uWaterLevel: { value: w.level },
    uDiscC: { value: new Vector3(...(w.disc?.center ?? [0, 0, 0])) },
    uDiscN: { value: new Vector3(...(w.disc?.normal ?? [0, 0, 1])) },
    uDiscR: { value: w.disc?.radius ?? 0 },
    uDiscGlow: { value: glow },
    uDiscRim: { value: linear(look.mirrorRim) },
    uDiscRimOuter: { value: linear(look.mirrorRimOuter) },
    uDiscRune: { value: linear(look.mirrorRune).multiplyScalar(look.mirrorRuneGain) },
    uDiscBronze: { value: linear(look.mirrorBronze) },
    uWaterSkyLow: { value: linear(look.skyLow) },
    uWaterSkyHigh: { value: linear(look.skyHigh) },
    tReflect: { value: null },
    uHasReflect: { value: 0 },
    uReflectMatrix: { value: new Matrix4() },
    uReflectClamp: { value: new Vector4(0, 0, 1, 1) },
    uReflectTexel: { value: new Vector2(0, 0) },
    uPondMin: { value: new Vector2(...(w.bounds?.min ?? [-1e9, -1e9])) },
    uPondMax: { value: new Vector2(...(w.bounds?.max ?? [1e9, 1e9])) },
    uWaterTime: { value: 0 },
  };
}

/**
 * Points the ponds' analytic Heart-Mirror at its face as fitted to the face's own triangles
 * (assets.ts mirrorFace: the true normal, the face turned toward the western sun and tilted back),
 * where the glow box the uniforms start from only gives an axis. The mirror's own shading keeps the
 * box's disc (SECT_MIRROR), so it looks as before. No face: left as made.
 */
export function aimPondMirror(uniforms: readonly WaterUniforms[], face: { center: Vec3; normal: Vec3; radius: number } | null): void {
  if (!face) return;
  for (const u of uniforms) {
    (u.uDiscC.value as Vector3).set(...face.center);
    (u.uDiscN.value as Vector3).set(...face.normal).normalize();
    u.uDiscR.value = face.radius;
  }
}

/**
 * Alpha-tested tree cards (lib/sect/card-shading.ts): alpha is scaled up with the mip level so
 * distant cards do not thin out (mip averaging lowers alpha and the cut-off removes it), gently on
 * needle and twig cards so their fans stay needles; with MSAA, alpha to coverage turns the hard
 * cut-out edge into an anti-aliased one (needle and twig cards with the alpha sharpened to a
 * one-pixel ramp); twig cards get the photographed twig's light and dark needles; and lit leaves
 * facing away from the camera toward the sun get a warm rim (back light through the needles),
 * brightest on their thin edges.
 */
export function patchCardMaterial(mat: MeshBasicMaterial, opts: { alphaToCoverage: boolean; sunDir: Vector3; texSize: Vector2 }): void {
  setCardAlphaMode(mat, opts.alphaToCoverage);
  const kind = cardAlphaKind(mat.userData);
  const rim = linear(SECT_LOOK.trees.rim).multiplyScalar(SECT_LOOK.trees.rimStrength);
  const prev = mat.onBeforeCompile;
  const prevKey = mat.customProgramCacheKey();
  mat.onBeforeCompile = (shader, renderer) => {
    prev.call(mat, shader, renderer);
    shader.uniforms.uSectTexSize = { value: opts.texSize };
    shader.uniforms.uSectSun = { value: opts.sunDir };
    shader.uniforms.uSectRim = { value: rim };
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vSectCardWorld;")
      .replace(
        "#include <project_vertex>",
        `#include <project_vertex>\n${WORLD_VARYING_VERTEX.replace("vSectWorld", "vSectCardWorld")}`,
      );
    let fs = shader.fragmentShader.replace(
      "#include <common>",
      "#include <common>\nuniform vec2 uSectTexSize;\nuniform vec3 uSectSun;\nuniform vec3 uSectRim;\nvarying vec3 vSectCardWorld;",
    );
    // Needle and twig cards cut out with their alpha map (its own UV set and size), read once for
    // the cut-out and the twig's detail; sprite cards with the map's alpha.
    fs = kind
      ? fs.replace("#include <alphamap_fragment>", cardAlphaMapGlsl(kind))
      : fs.replace("#include <map_fragment>", `#include <map_fragment>\n${cardSpriteBoostGlsl()}`);
    shader.fragmentShader = fs
      .replace("#include <alphatest_fragment>", cardAlphaTestGlsl(kind))
      .replace("#include <opaque_fragment>", `${cardRimGlsl()}\n#include <opaque_fragment>`);
  };
  // Read at compile time, so the key follows setCardAlphaMode.
  mat.customProgramCacheKey = () => `${prevKey}|card-${kind ?? "sprite"}|${mat.alphaToCoverage ? "a2c" : "at"}`;
  mat.needsUpdate = true;
}

/** Alpha to coverage on or off for a card material (the cut-off moves with it). */
export function setCardAlphaMode(mat: MeshBasicMaterial, alphaToCoverage: boolean): void {
  mat.alphaToCoverage = alphaToCoverage;
  mat.alphaTest = alphaToCoverage ? 0.4 : 0.42;
}

/**
 * Needle and twig cards (extras.cardAlpha = "needle" | "twig", bake_trees.py): opaque in the file,
 * with the cut-out in the occlusion slot on the second UV set. It becomes the alpha map (on the
 * same UV set; an ao map would darken them instead) before the card patch. True when the material
 * is one.
 */
export function prepareNeedleCard(mat: MeshBasicMaterial): boolean {
  if (!isCutoutCard(mat.userData)) return false;
  if (mat.aoMap && !mat.alphaMap) {
    mat.alphaMap = mat.aoMap;
    mat.aoMap = null;
    mat.needsUpdate = true;
  }
  return true;
}

// ---------------------------------------------------------------------------------------------
// Runtime textures

let noiseTex: DataTexture | null = null;
let groundNoiseTex: DataTexture | null = null;
let clumpTex: DataTexture | null = null;

/** 256x256 tiling fractal noise (one channel), shared by the cloud sea and the moon. */
export function getNoiseTexture(): DataTexture {
  if (noiseTex) return noiseTex;
  const size = 256;
  const tex = new DataTexture(tilingNoise(size, { basePeriod: 4, octaves: 6, seed: 11 }), size, size, RedFormat, UnsignedByteType);
  tex.wrapS = tex.wrapT = RepeatWrapping;
  tex.magFilter = LinearFilter;
  tex.minFilter = LinearMipmapLinearFilter;
  tex.generateMipmaps = true;
  tex.needsUpdate = true;
  noiseTex = tex;
  return tex;
}

/**
 * The ground and rock layers' noise (lib/sect/noise.ts groundNoise, DETAIL_NOISE.ground): 128x128
 * RGBA, about 85 KB with mipmaps. R and G feed the far rock's 3D value noise (read at the top
 * level); B and A are the smooth patch fields of sectGroundTint (detail.ts groundTintGlsl), which
 * the grass tufts read too, and the sheen's waves. Shared, never disposed (like getNoiseTexture).
 */
export function getGroundNoiseTexture(): DataTexture {
  if (groundNoiseTex) return groundNoiseTex;
  const { size, offset, cells } = DETAIL_NOISE.ground;
  const tex = new DataTexture(groundNoise(size, { offset, cells }), size, size, RGBAFormat, UnsignedByteType);
  tex.name = "sect.groundNoise";
  tex.wrapS = tex.wrapT = RepeatWrapping;
  tex.magFilter = LinearFilter;
  tex.minFilter = LinearMipmapLinearFilter;
  tex.generateMipmaps = true;
  tex.needsUpdate = true;
  groundNoiseTex = tex;
  return tex;
}

/**
 * The grass clump field (noise.ts clumpField, DETAIL_NOISE.clump): 256x256, one channel, about 85
 * KB with mipmaps, which fade it to its mean with distance. A little anisotropy for lawns seen at a
 * slant. Built in about 15 ms on first use (the ground noise in about 10). Shared, never disposed.
 */
export function getClumpTexture(): DataTexture {
  if (clumpTex) return clumpTex;
  const { size, cells, mean } = DETAIL_NOISE.clump;
  const tex = new DataTexture(clumpField(size, { cells, mean }), size, size, RedFormat, UnsignedByteType);
  tex.name = "sect.clump";
  tex.wrapS = tex.wrapT = RepeatWrapping;
  tex.magFilter = LinearFilter;
  tex.minFilter = LinearMipmapLinearFilter;
  tex.generateMipmaps = true;
  tex.anisotropy = 4;
  tex.needsUpdate = true;
  clumpTex = tex;
  return tex;
}

function linear(hex: string): Color {
  return new Color(hex);
}

/**
 * After <colorspace_fragment> in a shader with fogLibrary: drawn straight to the sRGB screen (the
 * low tier has no post pass to dither the frame), one 8-bit step of noise against banding in the
 * long sky and cloud-sea gradients. Into the composer's linear buffer it does nothing (the post
 * pass dithers there); the test is a constant the compiler folds.
 */
export const SCREEN_DITHER_GLSL =
  "  if ( linearToOutputTexel( vec4( 0.5 ) ).r > 0.6 ) gl_FragColor.rgb = sectDitherEncoded( gl_FragColor.rgb, gl_FragCoord.xy );";

// ---------------------------------------------------------------------------------------------
// Sky dome

export interface SkyOptions {
  fog: FogConstants;
  texture: Texture | null;
  zenith: string;
  horizon: string;
  below: string;
  fogColor: string;
  sunColor: string;
  look?: SectLook;
}

/**
 * Sky: Blender's clean sky image blended toward the look's painted gradient (peach horizon, rose
 * band, lavender zenith, gold under the sun), layered high clouds with bright sun-side rims, then
 * the haze. The sky image arrives after the dome is built: set uniforms tSky / uHasSky.
 */
export function createSkyMaterial(o: SkyOptions): ShaderMaterial {
  const look = o.look ?? SECT_LOOK;
  // The reflections' sky (SECT_ENV) is this dome's: the image, the painted gradient, the haze and
  // the sun are the same uniform objects, reset to the look's day colours here (the twilight blends
  // them in place from these).
  const env = SECT_ENV;
  env.tSectSky.value = o.texture;
  env.uSectSkyOn.value = o.texture ? 1 : 0;
  env.uSectEnvZenith.value.set(look.sky.zenith);
  env.uSectEnvMid.value.set(look.sky.mid);
  env.uSectEnvHorizon.value.set(look.sky.horizon);
  env.uSectEnvSunHorizon.value.set(look.sky.sunHorizon);
  env.uSectEnvGradeMix.value = look.sky.gradeMix;
  env.uSectEnvHaze.value.set(o.fogColor);
  env.uSectEnvSunColor.value.set(o.sunColor);
  env.uSectEnvSunDir.value.set(...o.fog.sunDir).normalize();
  return new ShaderMaterial({
    name: "sect.sky",
    side: BackSide,
    depthWrite: false,
    depthTest: false,
    fog: false,
    uniforms: {
      tSky: env.tSectSky,
      uHasSky: env.uSectSkyOn,
      tNoise: { value: getNoiseTexture() },
      uTime: { value: 0 },
      uZenith: { value: linear(o.zenith) },
      uHorizon: { value: linear(o.horizon) },
      uBelow: { value: linear(o.below) },
      uFogColor: env.uSectEnvHaze,
      uSunColor: env.uSectEnvSunColor,
      uLookZenith: env.uSectEnvZenith,
      uLookMid: env.uSectEnvMid,
      uLookHorizon: env.uSectEnvHorizon,
      uLookSun: env.uSectEnvSunHorizon,
      uGradeMix: env.uSectEnvGradeMix,
      uCloudSunLit: { value: linear(look.skyClouds.sunLit) },
      uCloudLit: { value: linear(look.skyClouds.lit) },
      uCloudShade: { value: linear(look.skyClouds.shade) },
      uCloudRim: { value: linear(look.skyClouds.rim) },
      uCoverage: { value: look.skyClouds.coverage },
    },
    vertexShader: /* glsl */ `
varying vec3 vDir;
void main() {
  vDir = position;
  gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
}
`,
    fragmentShader: /* glsl */ `
uniform sampler2D tSky;
uniform sampler2D tNoise;
uniform float uHasSky;
uniform float uTime;
uniform vec3 uZenith;
uniform vec3 uHorizon;
uniform vec3 uBelow;
uniform vec3 uFogColor;
uniform vec3 uSunColor;
uniform vec3 uLookZenith;
uniform vec3 uLookMid;
uniform vec3 uLookHorizon;
uniform vec3 uLookSun;
uniform float uGradeMix;
uniform vec3 uCloudSunLit;
uniform vec3 uCloudLit;
uniform vec3 uCloudShade;
uniform vec3 uCloudRim;
uniform float uCoverage;
varying vec3 vDir;
${fogLibrary(o.fog)}
float sectSkyNoise( vec2 p ) {
  return texture2D( tNoise, p ).r * 0.5 + texture2D( tNoise, p * 2.63 + 0.31 ).r * 0.28
    + texture2D( tNoise, p * 6.9 + 0.67 ).r * 0.14 + texture2D( tNoise, p * 15.3 + 0.13 ).r * 0.08;
}
void main() {
  vec3 d = normalize( vDir );
  vec3 col;
  if ( uHasSky > 0.5 ) {
    vec2 uv = vec2( atan( d.z, d.x ) * 0.15915494 + 0.5, asin( clamp( d.y, -1.0, 1.0 ) ) * 0.31830989 + 0.5 );
    col = texture2D( tSky, uv ).rgb;
  } else {
    col = d.y >= 0.0 ? mix( uHorizon, uZenith, sqrt( clamp( d.y, 0.0, 1.0 ) ) ) : uBelow;
  }
  float h = clamp( d.y, 0.0, 1.0 );
  vec3 sunH = normalize( vec3( SECT_SUN_DIR.x, 0.0, SECT_SUN_DIR.z ) );
  vec3 dh = normalize( vec3( d.x, 0.0, d.z ) + vec3( 1e-5, 0.0, 0.0 ) );
  float sunSide = dot( dh, sunH ) * 0.5 + 0.5;
  vec3 grad = mix( uLookHorizon, uLookMid, smoothstep( 0.03, 0.22, h ) );
  grad = mix( grad, uLookZenith, smoothstep( 0.18, 0.75, h ) );
  grad = mix( grad, uLookSun, pow( sunSide, 4.0 ) * ( 1.0 - smoothstep( 0.0, 0.45, h ) ) );
  col = mix( col, grad, uGradeMix * smoothstep( -0.05, 0.0, d.y ) );
  float od = sectHazeDepth( cameraPosition.y, max( d.y, 0.004 ), 40000.0 ) * SECT_SKY_HAZE;
  vec3 haze = sectHazeColor( uFogColor, d );
  col = mix( col, haze, 1.0 - exp( - od ) );
  // Two layers of high cloud on planes far overhead, stretched along one axis, lit from the sun
  // side: pink and gold bodies, bright rims where an edge faces the sun, sinking into the haze
  // toward the horizon.
  if ( d.y > 0.004 ) {
    vec2 p = d.xz / ( d.y + 0.05 );
    for ( int k = 0; k < 2; k++ ) {
      float fk = float( k );
      vec2 q = vec2( p.x * ( 0.05 - 0.018 * fk ) + p.y * 0.02, p.y * ( 0.12 - 0.04 * fk ) - p.x * 0.015 )
        + vec2( uTime * ( 0.0006 + 0.0003 * fk ), 0.37 * fk );
      float n = sectSkyNoise( q );
      float nl = sectSkyNoise( q + sunH.xz * 0.014 );
      // The noise sits around 0.5 +- 0.12, so coverage maps to a threshold in that band.
      float t0 = 0.64 - uCoverage * ( 0.28 - 0.06 * fk );
      float cov = smoothstep( t0, t0 + 0.12, n );
      float fade = smoothstep( 0.015, 0.12, d.y ) * ( 1.0 - 0.5 * smoothstep( 0.5, 0.95, d.y ) );
      float light = clamp( 0.5 + ( n - nl ) * 14.0, 0.0, 1.0 );
      vec3 lit = mix( uCloudLit, uCloudSunLit, smoothstep( 0.3, 1.0, sunSide ) );
      vec3 cc = mix( uCloudShade, lit, light );
      // Thin edges toward the sun catch the light.
      float edge = cov * ( 1.0 - smoothstep( t0 + 0.02, t0 + 0.1, n ) );
      cc += uCloudRim * edge * smoothstep( 0.45, 1.0, sunSide ) * 0.8;
      cc = mix( cc, haze, 0.35 * ( 1.0 - smoothstep( 0.02, 0.3, d.y ) ) );
      col = mix( col, cc, cov * fade * ( 0.94 - 0.24 * fk ) );
    }
  }
  float c = dot( d, SECT_SUN_DIR );
  col += uSunColor * ( smoothstep( 0.99990, 0.99996, c ) * 24.0 + pow( max( c, 0.0 ), 900.0 ) * 0.8 + pow( max( c, 0.0 ), 12.0 ) * 0.16 );
  gl_FragColor = vec4( col, 1.0 );
  #include <colorspace_fragment>
${SCREEN_DITHER_GLSL}
}
`,
  });
}

// ---------------------------------------------------------------------------------------------
// Moon

/**
 * The moon's face (public/sect/fx/moon.webp): the near side seen square on, an orthographic
 * projection of NASA's public-domain LRO colour mosaic (Scientific Visualization Studio, CGI Moon
 * Kit, lroc_color_2k), 1024 px, about 100 KB. Beside the sets like the other fx files.
 */
export const MOON_TEXTURE_URL = "/sect/fx/moon.webp";
/** The map's mean linear albedo (its disc averages sRGB 169, 165, 164), so the shader can normalise it. */
const MOON_MEAN = [0.4, 0.38, 0.375] as const;

/** The moon map, shared by every moon material: uHasMoon turns 1 once it has arrived. */
const MOON_MAP = {
  tMoon: { value: null as Texture | null },
  uHasMoon: { value: 0 },
};

/** Starts loading the moon map once (on the first moon shader compile, so tests never fetch it). */
function ensureMoonTexture(): void {
  if (MOON_MAP.tMoon.value || typeof window === "undefined") return;
  const tex = new Texture();
  tex.name = "sect.moon";
  tex.colorSpace = SRGBColorSpace;
  // ImageBitmaps are not flipped on upload; the image element path is told the same, so the shader
  // reads row 0 (north) at v = 0 either way.
  tex.flipY = false;
  tex.anisotropy = 4;
  MOON_MAP.tMoon.value = tex;
  const done = (image: ImageBitmap | HTMLImageElement) => {
    tex.image = image;
    tex.needsUpdate = true;
    MOON_MAP.uHasMoon.value = 1;
  };
  const failed = (e: unknown) => console.warn("[sect] the moon texture failed to load; the moon stays plain", e);
  if (typeof createImageBitmap !== "undefined") {
    new ImageBitmapLoader().setOptions({ premultiplyAlpha: "none", colorSpaceConversion: "none" }).load(MOON_TEXTURE_URL, done, undefined, failed);
  } else {
    new ImageLoader().load(MOON_TEXTURE_URL, done, undefined, failed);
  }
}

/**
 * The moon: the real near side (MOON_TEXTURE_URL) kept north-up whatever the camera's roll, its
 * maria softened a little for a hazy evening sky, gently darker toward the limb, then the sky's
 * haze. Until the map arrives (and for good if it fails) a plain disc with soft noise patches.
 */
export function createMoonMaterial(fog: FogConstants, color: string, fogColor: string): ShaderMaterial {
  const m = new ShaderMaterial({
    name: "sect.moon",
    transparent: true,
    depthWrite: false,
    fog: false,
    uniforms: {
      tNoise: { value: getNoiseTexture() },
      uColor: { value: linear(color) },
      uFogColor: { value: linear(fogColor) },
      ...MOON_MAP,
    },
    vertexShader: /* glsl */ `
varying vec2 vUv;
varying vec3 vWorld;
void main() {
  // The disc turns with the camera; turn its face back so the moon's north stays up.
  vec3 ax = normalize( mat3( modelMatrix ) * vec3( 1.0, 0.0, 0.0 ) );
  vec3 ay = normalize( mat3( modelMatrix ) * vec3( 0.0, 1.0, 0.0 ) );
  float a = atan( ax.y, ay.y );
  vec2 p = uv * 2.0 - 1.0;
  vUv = vec2( cos( a ) * p.x - sin( a ) * p.y, sin( a ) * p.x + cos( a ) * p.y ) * 0.5 + 0.5;
  vec4 wp = modelMatrix * vec4( position, 1.0 );
  vWorld = wp.xyz;
  gl_Position = projectionMatrix * viewMatrix * wp;
}
`,
    fragmentShader: /* glsl */ `
uniform sampler2D tNoise;
uniform sampler2D tMoon;
uniform float uHasMoon;
uniform vec3 uColor;
uniform vec3 uFogColor;
varying vec2 vUv;
varying vec3 vWorld;
${fogLibrary(fog)}
void main() {
  vec2 p = vUv * 2.0 - 1.0;
  float r = length( p );
  if ( r > 1.0 ) discard;
  vec3 alb;
  if ( uHasMoon > 0.5 ) {
    alb = texture2D( tMoon, vec2( vUv.x, 1.0 - vUv.y ) ).rgb / ${glslVec3([...MOON_MEAN])};
    // Mostly the map's light and dark (maria, rays), a little of its colour; a touch less contrast
    // through the evening air.
    alb = mix( vec3( dot( alb, SECT_LUMA ) ), alb, 0.4 );
    alb = mix( vec3( 1.0 ), alb, 0.9 ) * 0.8;
  } else {
    float n = texture2D( tNoise, vUv * 0.9 + 0.17 ).r;
    float n2 = texture2D( tNoise, vUv * 2.7 + 0.41 ).r;
    alb = vec3( 1.0 - ( smoothstep( 0.5, 0.78, n ) * 0.2 + ( n2 - 0.5 ) * 0.08 ) );
  }
  // A full moon barely darkens at the limb (the regolith scatters back toward the sun); a little
  // keeps it a sphere.
  float mu = sqrt( max( 1.0 - r * r, 0.0 ) );
  float limb = 0.74 + 0.26 * pow( mu, 0.55 );
  vec3 col = uColor * alb * limb;
  vec3 rd = normalize( vWorld - cameraPosition );
  float od = sectHazeDepth( cameraPosition.y, max( rd.y, 0.004 ), 40000.0 ) * SECT_SKY_HAZE;
  col = mix( col, sectHazeColor( uFogColor, rd ), ( 1.0 - exp( - od ) ) * 0.75 );
  gl_FragColor = vec4( col, smoothstep( 1.0, 0.99, r ) * 0.97 );
  #include <colorspace_fragment>
}
`,
  });
  m.onBeforeCompile = ensureMoonTexture;
  return m;
}

/** The linear grey a glow is assumed to light on the Low tier's screen: the sky behind the moon at 93 and 1647. */
const GLOW_SCREEN_BACK = 0.3;

/**
 * A soft additive glow (the moon's halo). It writes linear light and never encodes it (nor do the
 * other additive lights here, the beams and the dome): into the composer's linear buffer the
 * encode does nothing anyway, and straight onto the sRGB screen (the Low tier) encoding a glow
 * before it is added brightened its faint tail many times over (sRGB(0.02) is 0.15), so the halo
 * burned a white blot across half the sky at the summit.
 *
 * Added unencoded onto that screen, the halo still showed 1.3-1.7 times as bright as on High over
 * the bright evening sky (the sRGB curve is flat there), so on the Low tier it adds the step its
 * light makes over a typical sky behind the moon (glsl.ts screenAdd, GLOW_SCREEN_BACK).
 */
export function createGlowMaterial(color: string, strength: number): ShaderMaterial {
  return new ShaderMaterial({
    name: "sect.glow",
    transparent: true,
    depthWrite: false,
    blending: AdditiveBlending,
    fog: false,
    uniforms: { uColor: { value: linear(color) }, uStrength: { value: strength } },
    vertexShader: /* glsl */ `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
}
`,
    fragmentShader: /* glsl */ `
uniform vec3 uColor;
uniform float uStrength;
varying vec2 vUv;
${SCREEN_CLIP_GLSL}${SCREEN_ADD_GLSL}
void main() {
  float r = length( vUv * 2.0 - 1.0 );
  float a = exp( - r * r * 5.0 ) * smoothstep( 1.0, 0.7, r );
  // Straight onto the sRGB screen (the Low tier): the step this light makes over the sky behind it
  // (about linear grey ${glslFloat(GLOW_SCREEN_BACK)} at both moon stops), as High's add in linear shows it.
  gl_FragColor = vec4( sectScreenAdd( uColor * a * uStrength, ${glslFloat(GLOW_SCREEN_BACK)} ), 1.0 );
}
`,
  });
}

// ---------------------------------------------------------------------------------------------
// Cloud sea

/**
 * The endless sea of cloud below the sect, solid (the sky and the haze rely on it hiding what lies
 * beneath). Billowed relief: three octaves of noise folded into broad masses and hollows, drifting
 * slowly, lit by the low sun (slopes toward it bright, a mass's far side and the hollows behind a
 * taller one in shade), with a silver rim on crests seen toward the sun. Its colour is centred on
 * the cloud layer's own (SECT_CLOUD_FOG, what geometry sinking into the cloud turns to), so a cliff
 * meeting the sea fades into it instead of ending on a bright ring; the relief softens with distance
 * before the haze takes it.
 */
export function createCloudSeaMaterial(fog: FogConstants, top: string, shadow: string, fogColor: string): ShaderMaterial {
  return new ShaderMaterial({
    name: "sect.cloudsea",
    fog: false,
    uniforms: {
      tNoise: { value: getNoiseTexture() },
      uTime: { value: 0 },
      uTop: { value: linear(top) },
      uShadow: { value: linear(shadow) },
      uFogColor: { value: linear(fogColor) },
      uRim: { value: linear(SECT_LOOK.puffs.rim) },
    },
    vertexShader: /* glsl */ `
varying vec3 vWorld;
void main() {
  vec4 wp = modelMatrix * vec4( position, 1.0 );
  vWorld = wp.xyz;
  gl_Position = projectionMatrix * viewMatrix * wp;
}
`,
    fragmentShader: /* glsl */ `
uniform sampler2D tNoise;
uniform float uTime;
uniform vec3 uTop;
uniform vec3 uShadow;
uniform vec3 uFogColor;
uniform vec3 uRim;
varying vec3 vWorld;
${fogLibrary(fog)}
// 1 - |2n - 1|: broad high masses where the noise sits near its mean, sinking into hollows where it
// strays (a stretched |2n - 1|, the textbook billow, left the sea one flat bright sheet with
// sub-pixel creases).
float sectBillow( vec2 uv ) {
  return 1.0 - abs( texture2D( tNoise, uv ).r * 2.0 - 1.0 );
}
float billow( vec2 p ) {
  return sectBillow( p / 1900.0 + uTime * vec2( 0.0011, 0.0006 ) ) * 0.5
    + sectBillow( p / 640.0 + uTime * vec2( -0.0009, 0.0016 ) + 0.37 ) * 0.32
    + sectBillow( p / 230.0 + uTime * vec2( 0.0021, -0.0012 ) + 0.71 ) * 0.18;
}
void main() {
  vec2 p = vWorld.xz;
  vec3 rd = vWorld - cameraPosition;
  float t = length( rd );
  rd /= max( t, 1e-3 );
  vec2 sunH = normalize( SECT_SUN_DIR.xz + vec2( 1e-5, 0.0 ) );
  float h = billow( p );
  // Toward the sun: a short step for the slope (lit faces), a long one for a taller dome's shadow.
  float hs = billow( p + sunH * 45.0 );
  float hf = billow( p + sunH * 260.0 );
  float lit = clamp( 0.5 + ( hs - h ) * 5.5, 0.0, 1.0 );
  float shade = smoothstep( 0.02, 0.16, hf - h );
  float k = clamp( lit * 0.6 + h * 0.8 - shade * 0.5 - 0.1, 0.0, 1.0 );
  // Relief fades out far away (and at a grazing glance), where it would only shimmer.
  float relief = 1.0 - smoothstep( 1800.0, 6500.0, t );
  k = mix( 0.55, smoothstep( 0.12, 0.85, k ), relief );
  // Centred on the cloud layer's colour: warm sunlit tops, cool lavender hollows.
  vec3 col = mix( mix( uShadow, SECT_CLOUD_FOG, 0.3 ), mix( SECT_CLOUD_FOG, uTop, 0.65 ) * 1.14, k );
  // Crests seen toward the sun catch a silver-gold rim.
  float toward = pow( max( dot( rd, SECT_SUN_DIR ), 0.0 ), 4.0 );
  col += uRim * toward * smoothstep( 0.55, 0.9, lit ) * h * relief * 0.35;
  float od = sectHazeDepth( cameraPosition.y, rd.y, t ) * 1.4;
  vec3 haze = sectHazeColor( uFogColor, rd );
  col = mix( col, haze, 1.0 - exp( - od ) );
  col = mix( col, haze, smoothstep( 4500.0, 8400.0, t ) );
  gl_FragColor = vec4( col, 1.0 );
  #include <colorspace_fragment>
${SCREEN_DITHER_GLSL}
}
`,
  });
}

// ---------------------------------------------------------------------------------------------
// Waterfalls: falling streaks from 3D noise in world space (stand-in meshes have no UVs)

export function createWaterfallMaterial(color: string, opacity = 0.85): ShaderMaterial {
  return new ShaderMaterial({
    name: "sect.waterfall",
    transparent: true,
    depthWrite: false,
    side: DoubleSide,
    fog: true,
    uniforms: UniformsUtils.merge([
      UniformsLib.fog,
      { uTime: { value: 0 }, uColor: { value: linear(color) }, uOpacity: { value: opacity } },
    ]),
    vertexShader: /* glsl */ `
#include <fog_pars_vertex>
varying vec3 vWorld;
void main() {
  vec4 local = vec4( position, 1.0 );
  #ifdef USE_INSTANCING
    local = instanceMatrix * local;
  #endif
  vec4 wp = modelMatrix * local;
  vWorld = wp.xyz;
  vec4 mvPosition = viewMatrix * wp;
  gl_Position = projectionMatrix * mvPosition;
  #include <fog_vertex>
}
`,
    fragmentShader: /* glsl */ `
#include <common>
#include <fog_pars_fragment>
uniform float uTime;
uniform vec3 uColor;
uniform float uOpacity;
varying vec3 vWorld;
float h3( vec3 p ) {
  p = fract( p * 0.3183099 + 0.1 );
  p *= 17.0;
  return fract( p.x * p.y * p.z * ( p.x + p.y + p.z ) );
}
float vnoise( vec3 x ) {
  vec3 i = floor( x );
  vec3 f = fract( x );
  f = f * f * ( 3.0 - 2.0 * f );
  return mix( mix( mix( h3( i ), h3( i + vec3( 1, 0, 0 ) ), f.x ), mix( h3( i + vec3( 0, 1, 0 ) ), h3( i + vec3( 1, 1, 0 ) ), f.x ), f.y ),
              mix( mix( h3( i + vec3( 0, 0, 1 ) ), h3( i + vec3( 1, 0, 1 ) ), f.x ), mix( h3( i + vec3( 0, 1, 1 ) ), h3( i + vec3( 1, 1, 1 ) ), f.x ), f.y ), f.z );
}
void main() {
  vec3 p = vWorld;
  float n1 = vnoise( vec3( p.x * 0.45, p.y * 0.05 + uTime * 1.1, p.z * 0.45 ) );
  float n2 = vnoise( vec3( p.x * 1.3, p.y * 0.12 + uTime * 2.2, p.z * 1.3 ) + 7.0 );
  float streak = smoothstep( 0.3, 0.85, n1 * 0.62 + n2 * 0.38 );
  vec3 col = uColor * mix( 0.78, 1.12, streak );
  gl_FragColor = vec4( col, uOpacity * ( 0.4 + 0.6 * streak ) );
  #include <colorspace_fragment>
  #include <fog_fragment>
}
`,
  });
}

export interface SheetOptions {
  /** Toward the sun (three space): the water glows when the camera looks toward it. */
  sunDir?: Vector3;
}

/**
 * Waterfall sheets and streams (water GLBs and the corner quads), in the main fogged pass. Reads
 * the per-vertex `aFall` (lib/sect/waterfall.ts: metres across, metres below the lip, height, lip
 * width; a stream's z < 0 says where its foot is; assets.ts prepareWaterSheets adds it at load)
 * and the vertex colour (r a per-sheet seed, g the flow / 2, b the layer: 0 core, 0.5 side
 * curtain, 1 front veil).
 *
 * Every pattern rides the water: its phase is rate x (seconds since the lip - time), so streaks
 * fall exactly as fast as the water there (gravity with drag: they speed up and stretch on the way
 * down) at sizes set in metres. Three layers: clumps (noise, x1), fine streaks (noise, x1.7) and
 * the photographed strands (fx/strands.webp, until it arrives a flat grey). A smooth, glassy lip
 * over the top SHEET.lip of the height breaks into white water; the lower 40 % tears into clumps;
 * the edges are ragged and stranded; the water reaches the pool (a 5 % fade). Looking toward the
 * sun it glows (as the cloud puffs do), and the lip's highlight and the sparkles go a little above
 * 1.0 so bloom (mid and high tiers) catches them. Shares uTime with the stand-in waterfall material.
 */
export function createWaterfallSheetMaterial(
  time: IUniform<number>,
  look: SectLook["waterfall"] = SECT_LOOK.waterfall,
  opts: SheetOptions = {},
): ShaderMaterial {
  const uniforms: Record<string, IUniform> = UniformsUtils.merge([
    UniformsLib.fog,
    {
      uColor: { value: linear(look.color) },
      uFoam: { value: linear(look.foam) },
      uGlass: { value: linear(SHEET.glass) },
      uSunColor: { value: linear(SHEET.glow) },
      uSunDir: { value: (opts.sunDir ?? new Vector3(0, 0.3, -1)).clone().normalize() },
      uOpacity: { value: look.opacity },
      uHasStrands: { value: 0 },
      tNoise: { value: null },
      tStrands: { value: null },
    },
  ]);
  // Shared objects (merge clones values): the noise texture and the clock of the other waterfalls.
  uniforms.tNoise = { value: getNoiseTexture() };
  uniforms.uTime = time;
  const f = glslFloat;
  return new ShaderMaterial({
    name: "sect.waterfall.sheet",
    transparent: true,
    depthWrite: false,
    side: DoubleSide,
    fog: true,
    vertexColors: true,
    uniforms,
    vertexShader: /* glsl */ `
#include <fog_pars_vertex>
attribute vec4 aFall;
varying vec2 vUv;
varying vec3 vSeed;
varying vec4 vFall;
varying vec3 vView;
void main() {
  vUv = uv;
  #ifdef USE_COLOR
    vSeed = color.rgb;
  #else
    vSeed = vec3( 0.0, 0.5, 0.0 );
  #endif
  vFall = aFall;
  vec4 wp = modelMatrix * vec4( position, 1.0 );
  vView = wp.xyz - cameraPosition;
  vec4 mvPosition = viewMatrix * wp;
  gl_Position = projectionMatrix * mvPosition;
  #include <fog_vertex>
}
`,
    fragmentShader: /* glsl */ `
#include <common>
#include <fog_pars_fragment>
uniform float uTime;
uniform vec3 uColor;
uniform vec3 uFoam;
uniform vec3 uGlass;
uniform vec3 uSunColor;
uniform vec3 uSunDir;
uniform float uOpacity;
uniform float uHasStrands;
uniform sampler2D tNoise;
uniform sampler2D tStrands;
varying vec2 vUv;
varying vec3 vSeed;
varying vec4 vFall;
varying vec3 vView;
${fallGlsl()}
void main() {
  float H = max( abs( vFall.z ), 0.01 );
  float stream = vFall.z < 0.0 ? 1.0 : 0.0;
  float W = max( vFall.w, 0.1 );
  // Sheets: metres below the lip, p the share of the height. Streams: metres along the flow (it runs
  // downhill both ways off a crest), p from z = -( 1 + the share of the strip from its head ).
  float below = stream > 0.5 ? max( vFall.y, 0.0 ) : clamp( vFall.y, 0.0, H );
  float p = stream > 0.5 ? clamp( H - 1.0, 0.0, 1.0 ) : below / H;
  float x = vFall.x;
  float seed = vSeed.x;
  float curtain = 1.0 - abs( vSeed.z * 2.0 - 1.0 );
  float veil = smoothstep( 0.75, 1.0, vSeed.z );
  // Seconds since the lip: free fall with drag (streams flow at a steady pace).
  float tau = mix( sectFallSeconds( below ), below / SECT_STREAM_SPEED, stream );
  // Patterns ride the water: phase = rate * ( tau - time ). fract() keeps the precision; every texture tiles at 1.
  float k = ${f(SHEET.k)} * ( 0.9 + 0.2 * vSeed.y );
  float kB = k * ${f(SHEET.streakRate)};
  float clumpM = ${f(SHEET.clumpTileM)} * clamp( sqrt( W / ${f(SHEET.clumpRefWidthM)} ), 1.0, ${f(SHEET.clumpMaxScale)} );
  float nA = texture2D( tNoise, vec2( x / clumpM + seed * 7.13, tau * k - fract( uTime * k ) ) ).r;
  float nB = texture2D( tNoise, vec2( x / ${f(SHEET.streakTileM)} + 0.37 + seed * 3.71,
    tau * kB - fract( uTime * kB * ${f(SHEET.streakSpeed)} ) ) ).r;
  float st = texture2D( tStrands, vec2( x / ${f(SHEET.strandTileM)} + seed * 0.61,
    tau * ${f(SHEET.strandRate)} - fract( uTime * ${f(SHEET.strandRate)} ) ) ).r;
  st = mix( 0.45, st, uHasStrands );
  // Far away the tiles' repeats line up into a lattice (a zipper down a far cliff): past about
  // 150 m the patterns give way to long soft streaks that only vary across the fall, drifting down.
  // (Fetched everywhere: an implicit-LOD fetch must stay out of non-uniform control flow.)
  float far = smoothstep( ${f(SHEET.farFrom)}, ${f(SHEET.farTo)}, length( vView ) );
  float soft = texture2D( tNoise, vec2( x / max( W * 0.5, 3.0 ) + seed * 5.3, tau * 0.05 - fract( uTime * 0.05 ) ) ).r * 0.6
    + texture2D( tNoise, vec2( x / max( W * 0.16, 1.5 ) + seed * 2.1, tau * 0.16 - fract( uTime * 0.16 ) ) ).r * 0.4;
  // The ragged sides keep some of the near patterns.
  float nAe = mix( nA, 0.3 + 0.45 * soft, far * 0.6 );
  float ste = mix( st, 0.25 + 0.5 * soft, far * 0.6 );
  nA = mix( nA, 0.3 + 0.45 * soft, far );
  nB = mix( nB, 0.42 + 0.2 * soft, far );
  st = mix( st, 0.25 + 0.5 * soft, far );
  // Along the fall: a glassy lip, white water below it, clumps tearing apart toward the foot.
  float q = mix( p, 0.3, stream );
  float lip = 1.0 - smoothstep( ${f(SHEET.lip * 0.3)}, ${f(SHEET.lip * 1.5)}, q );
  float aer = smoothstep( ${f(SHEET.lip * 0.5)}, ${f(SHEET.lip * 3.5)}, q );
  float streak = smoothstep( 0.35, 0.75, nA * 0.5 + nB * 0.5 );
  float strand = smoothstep( 0.35, 0.8, st );
  float white = mix( streak, strand, 0.6 );
  white = mix( white * 0.35, 0.15 + 0.85 * white, aer );
  white = mix( white, 0.5 + 0.5 * white, smoothstep( 0.5, 1.0, q ) );
  // Clear water between the strands is thinner and darker (it shows the rock behind); foam is dense.
  // The glassy lip is clear water too: see-through, with smooth ridges that catch the light.
  float ridge = smoothstep( 0.45, 0.85, nB );
  float a = mix( uOpacity * ( mix( 0.22, 0.32, aer ) + 0.68 * max( white, streak * 0.8 ) ), 0.34 + 0.3 * ridge, lip );
  float tear = smoothstep( ${f(SHEET.breakup)}, 1.0, q ) * ( 0.5 + 0.15 * curtain );
  a *= mix( 0.12, 1.0, smoothstep( tear - 0.08, tear + 0.08, nA * 0.55 + st * 0.45 ) );
  // Ragged, stranded sides: the edge (metres from the nearest side at the lip's scale) is pushed in
  // and out by the strands and clumps, more lower down.
  float e = min( vUv.x, 1.0 - vUv.x ) * W;
  float band = clamp( 0.16 * W, 0.4, 3.5 ) * ( 1.0 + 0.8 * q );
  float side = smoothstep( 0.0, band * 0.7, e + ( ( ste - 0.45 ) * 1.2 + ( nAe - 0.5 ) * 1.4 ) * band );
  // A crisp lip (0.4 m), its line a little uneven; the water reaches the pool. A stream fades out at
  // its foot (its lower end) only: its smallest metres along the flow may be on a crest mid-strip.
  float head = stream > 0.5 ? 1.0 : smoothstep( 0.0, 0.4, below + ( nB - 0.5 ) * 0.25 );
  float ends = head * ( 1.0 - smoothstep( ${f(1 - SHEET.footFade)}, 1.0, p ) );
  float shape = side * ends * mix( 1.0, 0.72, curtain ) * mix( 1.0, 0.35, veil );
  a *= shape;
  vec3 col = mix( mix( uGlass, uColor, 0.55 ), uFoam, white );
  col = mix( col, uGlass * ( 0.75 + 0.6 * ridge ), lip * ( 1.0 - veil ) );
  // The lip's bright bend and shimmer, sparkles in the white water, and the glow toward the sun.
  float bend = smoothstep( 0.05, 0.25, below ) * ( 1.0 - smoothstep( 0.35, max( 0.9, H * 0.015 ), below ) ) * ( 1.0 - stream );
  float shimmer = smoothstep( 0.55, 0.9, nB ) * lip;
  float toward = pow( max( dot( normalize( vView ), uSunDir ), 0.0 ), 5.0 );
  float sparkle = smoothstep( 0.78, 0.94, nB ) * smoothstep( 0.6, 0.85, st ) * aer;
  col += uSunColor * ( ( bend * ( 0.5 + 0.7 * nB ) * 0.6 + shimmer * 0.35 + sparkle * ( 0.45 + 1.1 * toward ) ) * ( 1.0 - veil )
    + toward * ( 0.25 + 0.55 * clamp( 1.0 - a, 0.0, 1.0 ) ) * 0.9 );
  a = max( a, toward * 0.18 * shape );
  gl_FragColor = vec4( col, clamp( a, 0.0, 1.0 ) );
  #include <colorspace_fragment>
  #include <fog_fragment>
}
`,
  });
}

/** Points a sheet material at its strand texture, or back to flat grey strands (null). */
export function setSheetStrands(mat: ShaderMaterial, tex: Texture | null): void {
  mat.uniforms.tStrands.value = tex;
  mat.uniforms.uHasStrands.value = tex ? 1 : 0;
}

const WET_GLSL = wetRockGlsl(WET.max);
const WET_ARRAYS = wetArrays(WET.max);

/**
 * The wet rock's uniforms, shared by every baked material (patchMaterial): the nearest falls as
 * packWetFalls writes them, filled each frame by a WetRock (createWetRock). Count 0 draws no wet rock.
 */
export const SECT_WET = {
  uWetA: { value: WET_ARRAYS.a },
  uWetB: { value: WET_ARRAYS.b },
  uWetC: { value: WET_ARRAYS.c },
  uWetD: { value: WET_ARRAYS.d },
  uWetCount: { value: 0 },
  uWetSun: { value: new Vector3(0, 1, 0) },
  uWetSheen: { value: new Color(0, 0, 0) },
  uWetTime: { value: 0 },
  tWetNoise: { value: null as Texture | null },
};

export interface WetRock {
  /**
   * Picks the falls nearest the camera among the shown sets' (again only once the camera has moved
   * a metre or a set was shown or hidden) and copies the clock. Every frame.
   */
  update(camera: { x: number; y: number; z: number }): void;
  /** A set's roots: its falls are wet while any of them is visible (the render loop shows a set once it is ready). */
  track(id: string, roots: readonly Object3D[]): void;
  untrack(id: string, roots: readonly Object3D[]): void;
  /** Draws no wet rock until the next update. */
  clear(): void;
  /** At most this many falls at once from the next update on (a new tier picked in place). */
  setMax(max: number): void;
}

/**
 * Feeds SECT_WET from the page's falls (lib/sect/waterfall.ts wetFalls): at most `max` of them at
 * once (the tier's share of WET.max), only those whose water is drawn (so a band never shows on a
 * chunk's stand-in before its water arrives), a sun glint in the glow colour unless `sheen` is off.
 */
export function createWetRock(falls: readonly WetFall[], o: { max: number; sunDir: Vector3; time: IUniform<number>; sheen: boolean }): WetRock {
  let max = Math.max(0, Math.min(o.max, WET.max));
  SECT_WET.uWetSun.value.copy(o.sunDir).normalize();
  SECT_WET.uWetSheen.value = o.sheen ? linear(SHEET.glow) : new Color(0, 0, 0);
  SECT_WET.tWetNoise.value = getNoiseTexture();
  const last = new Vector3(Infinity, 0, 0);
  const sets = new Map<string, Object3D[]>();
  // The shown sets' ids in map order, and their falls: rebuilt only when that changes, so a still
  // camera allocates nothing per frame.
  const shown: string[] = [];
  let shownCount = -1;
  let shownFalls: readonly WetFall[] = [];
  return {
    update(camera) {
      SECT_WET.uWetTime.value = o.time.value;
      let n = 0;
      let changed = false;
      for (const [id, roots] of sets) {
        let visible = false;
        for (const r of roots) {
          if (r.visible) {
            visible = true;
            break;
          }
        }
        if (!visible) continue;
        if (shown[n] !== id) {
          shown[n] = id;
          changed = true;
        }
        n++;
      }
      if (n !== shownCount) {
        changed = true;
        shownCount = n;
        shown.length = n;
      }
      if (changed) shownFalls = falls.filter((f) => shown.includes(f.chunk));
      else if (last.distanceToSquared(camera as Vector3) < 1) return;
      last.set(camera.x, camera.y, camera.z);
      SECT_WET.uWetCount.value = shownFalls.length > 0 ? packWetFalls(selectWetFalls(shownFalls, [camera.x, camera.y, camera.z], max), WET_ARRAYS) : 0;
    },
    track(id, roots) {
      sets.set(id, [...(sets.get(id) ?? []), ...roots]);
    },
    untrack(id, roots) {
      const left = (sets.get(id) ?? []).filter((r) => !roots.includes(r));
      if (left.length > 0) sets.set(id, left);
      else sets.delete(id);
    },
    clear() {
      SECT_WET.uWetCount.value = 0;
      last.set(Infinity, 0, 0);
      shownCount = -1;
    },
    setMax(n) {
      max = Math.max(0, Math.min(n, WET.max));
      // Picked again at the next update, wherever the camera is.
      last.set(Infinity, 0, 0);
      shownCount = -1;
    },
  };
}

/**
 * Volume cloud puffs as camera-facing sprites (one instanced draw). Each instance is an
 * ellipsoid (centre + three semi-axes); the quad is sized to the ellipsoid's silhouette, shaded
 * like a soft lit sphere with billowy noise, hazed like the scene, faded out when the camera
 * gets close (the film flies through the opening bank), and faded where it meets geometry (soft
 * particles, from the composer's depth texture) so no straight cut shows against cliffs.
 */
export function createCloudPuffMaterial(fog: FogConstants, fogColor: string, look: SectLook = SECT_LOOK): ShaderMaterial {
  return new ShaderMaterial({
    name: "sect.cloudpuff",
    transparent: true,
    depthWrite: false,
    fog: false,
    uniforms: {
      tNoise: { value: getNoiseTexture() },
      uTime: { value: 0 },
      uLit: { value: linear(look.puffs.lit) },
      uShade: { value: linear(look.puffs.shade) },
      uRim: { value: linear(look.puffs.rim) },
      uFogColor: { value: linear(fogColor) },
      uOpacity: { value: look.puffs.opacity },
      uSoft: { value: look.puffs.soft },
      ...SOFT_DEPTH,
    },
    vertexShader: /* glsl */ `
attribute vec3 iCenter;
attribute vec3 iA0;
attribute vec3 iA1;
attribute vec3 iA2;
attribute float iDensity;
varying vec2 vUv;
varying vec3 vR;
varying vec3 vU;
varying vec3 vF;
varying float vDist;
varying float vDepth;
varying float vFade;
varying float vWf;
varying float vViewZ;
varying vec2 vSeed;
void main() {
  vec3 toC = iCenter - cameraPosition;
  float dist = max( length( toC ), 1e-3 );
  vec3 f = toC / dist;
  vec3 up = abs( f.y ) > 0.985 ? vec3( 1.0, 0.0, 0.0 ) : vec3( 0.0, 1.0, 0.0 );
  vec3 r = normalize( cross( f, up ) );
  vec3 u = cross( r, f );
  // Half-extents of the ellipsoid along r, u and the view ray: |M^T e|.
  float wr = length( vec3( dot( iA0, r ), dot( iA1, r ), dot( iA2, r ) ) );
  float wu = length( vec3( dot( iA0, u ), dot( iA1, u ), dot( iA2, u ) ) );
  float wf = length( vec3( dot( iA0, f ), dot( iA1, f ), dot( iA2, f ) ) );
  // The sprite sits on the puff's near side rather than through its centre (scaled to keep its
  // angular size), so what is inside the puff is veiled rather than poking through the sprite.
  float lift = min( 0.6 * wf, 0.5 * dist );
  float k = ( dist - lift ) / dist;
  vec3 wp = iCenter - f * lift + ( r * position.x * wr + u * position.y * wu ) * k;
  vUv = position.xy;
  vR = r;
  vU = u;
  vF = f;
  vDist = dist;
  vWf = wf;
  // Optical depth through the middle: Blender's normalised density times the chord length.
  vDepth = iDensity * wf * 2.0;
  vFade = smoothstep( 0.55 * wf, 1.6 * wf, dist );
  vSeed = fract( iCenter.xz * 0.0137 );
  vec4 mv = viewMatrix * vec4( wp, 1.0 );
  vViewZ = mv.z;
  gl_Position = projectionMatrix * mv;
  // Faded out (the camera is inside or next to the puff): collapse the quad off screen so it
  // costs no fill rate.
  if ( vFade < 0.003 ) gl_Position = vec4( 2.0, 2.0, 2.0, 1.0 );
}
`,
    fragmentShader: /* glsl */ `
uniform sampler2D tNoise;
uniform float uTime;
uniform vec3 uLit;
uniform vec3 uShade;
uniform vec3 uRim;
uniform vec3 uFogColor;
uniform float uOpacity;
uniform float uSoft;
varying vec2 vUv;
varying vec3 vR;
varying vec3 vU;
varying vec3 vF;
varying float vDist;
varying float vDepth;
varying float vFade;
varying float vWf;
varying float vViewZ;
varying vec2 vSeed;
${SOFT_PARS}
${fogLibrary(fog)}
void main() {
  float q = length( vUv );
  if ( q > 1.0 || vFade < 0.003 ) discard;
  vec2 nuv = vUv * 0.42 + vSeed * 7.0 + vec2( uTime * 0.0015, 0.0 );
  float n = texture2D( tNoise, nuv ).r * 0.62 + texture2D( tNoise, nuv * 2.4 + 0.29 ).r * 0.38;
  // Billowy rim: the edge radius wanders with the noise; the base is flatter and denser.
  float edge = 1.0 - smoothstep( 0.2 + 0.32 * n, 0.98, q + ( 0.5 - n ) * 0.3 );
  edge *= smoothstep( -1.0, -0.45, vUv.y + ( n - 0.5 ) * 0.5 );
  float chord = sqrt( max( 1.0 - q * q, 0.0 ) );
  float tau = vDepth * chord * ( 0.35 + 0.9 * n ) * 0.28;
  float alpha = ( 1.0 - exp( - tau ) ) * edge;
  // Where the sprite meets a cliff or the ground: fade over a share of the puff's depth.
  alpha *= sectSoftFade( vViewZ, uSoft * vWf );
  // Soft sphere lighting: low warm sun from the side, brighter tops, warm cream-mauve shade.
  vec3 nrm = normalize( vR * vUv.x + vU * vUv.y - vF * chord );
  float sun = dot( nrm, SECT_SUN_DIR ) * 0.5 + 0.5;
  float light = clamp( sun * 0.6 + ( vUv.y * 0.5 + 0.5 ) * 0.45 + ( n - 0.5 ) * 0.5 - 0.08, 0.0, 1.0 );
  vec3 col = mix( uShade, uLit, smoothstep( 0.1, 0.9, light ) );
  float toward = pow( max( dot( vF, SECT_SUN_DIR ), 0.0 ), 5.0 );
  col += uRim * toward * ( 1.0 - edge ) * 0.7;
  float od = sectHazeDepth( cameraPosition.y, vF.y, vDist );
  col = mix( col, sectHazeColor( uFogColor, vF ), 1.0 - exp( - od ) );
  float cd = sectCloudDepth( cameraPosition.y, vF.y, vDist );
  col = mix( col, SECT_CLOUD_FOG, 1.0 - exp( - cd ) );
  gl_FragColor = vec4( col, clamp( alpha * vFade * uOpacity, 0.0, 1.0 ) );
  #include <colorspace_fragment>
}
`,
  });
}

/**
 * Spray mist at the foot of a waterfall: soft round camera-facing sprites (instanced: iCenter,
 * iRadius) with drifting noise, faded where they meet the ground.
 */
export function createMistMaterial(fog: FogConstants, fogColor: string, time: IUniform<number>): ShaderMaterial {
  return new ShaderMaterial({
    name: "sect.mist",
    transparent: true,
    depthWrite: false,
    fog: false,
    uniforms: {
      tNoise: { value: getNoiseTexture() },
      uTime: time,
      uColor: { value: linear(SECT_LOOK.waterfall.mist) },
      uFogColor: { value: linear(fogColor) },
      ...SOFT_DEPTH,
    },
    vertexShader: /* glsl */ `
attribute vec3 iCenter;
attribute float iRadius;
varying vec2 vUv;
varying float vViewZ;
varying float vRadius;
varying vec3 vDir;
varying float vDist;
void main() {
  vec3 toC = iCenter - cameraPosition;
  float dist = max( length( toC ), 1e-3 );
  vec3 f = toC / dist;
  vec3 r = normalize( cross( f, vec3( 0.0, 1.0, 0.0 ) ) );
  vec3 u = cross( r, f );
  vec3 wp = iCenter + ( r * position.x + u * position.y * 0.7 ) * iRadius;
  vUv = position.xy;
  vRadius = iRadius;
  vDir = f;
  vDist = dist;
  vec4 mv = viewMatrix * vec4( wp, 1.0 );
  vViewZ = mv.z;
  gl_Position = projectionMatrix * mv;
}
`,
    fragmentShader: /* glsl */ `
uniform sampler2D tNoise;
uniform float uTime;
uniform vec3 uColor;
uniform vec3 uFogColor;
varying vec2 vUv;
varying float vViewZ;
varying float vRadius;
varying vec3 vDir;
varying float vDist;
${SOFT_PARS}
${fogLibrary(fog)}
void main() {
  float q = length( vUv );
  if ( q > 1.0 ) discard;
  float n = texture2D( tNoise, vUv * 0.5 + vec2( uTime * 0.02, - uTime * 0.05 ) ).r;
  float a = ( 1.0 - smoothstep( 0.15, 1.0, q + ( n - 0.5 ) * 0.4 ) ) * 0.55;
  a *= sectSoftFade( vViewZ, vRadius * 0.6 );
  vec3 col = uColor;
  float od = sectHazeDepth( cameraPosition.y, vDir.y, vDist );
  col = mix( col, sectHazeColor( uFogColor, vDir ), 1.0 - exp( - od ) );
  gl_FragColor = vec4( col, a );
  #include <colorspace_fragment>
}
`,
  });
}

/**
 * Light beams (the formation's columns of light): additive camera-facing vertical strips
 * (instanced: iBase, iTop, iRadius, iColor), brightest in the core, fading out at the top and at
 * the ground (soft depth).
 */
export function createBeamMaterial(fog: FogConstants, fogColor: string, time: IUniform<number>): ShaderMaterial {
  return new ShaderMaterial({
    name: "sect.beam",
    transparent: true,
    depthWrite: false,
    blending: AdditiveBlending,
    fog: false,
    uniforms: {
      uTime: time,
      uOpacity: { value: SECT_LOOK.beams.opacity },
      uFogColor: { value: linear(fogColor) },
      ...SOFT_DEPTH,
    },
    vertexShader: /* glsl */ `
attribute vec3 iBase;
attribute vec3 iTop;
attribute float iRadius;
attribute vec3 iColor;
varying vec2 vUv;
varying vec3 vColor;
varying float vViewZ;
varying float vRadius;
varying vec3 vDir;
varying float vDist;
void main() {
  vec3 axis = iTop - iBase;
  float len = length( axis );
  vec3 a = axis / max( len, 1e-3 );
  vec3 mid = ( iBase + iTop ) * 0.5;
  vec3 toCam = normalize( cameraPosition - mid );
  vec3 side = normalize( cross( a, toCam ) );
  float t = position.y * 0.5 + 0.5;
  vec3 wp = iBase + axis * t + side * position.x * iRadius * 1.6;
  vUv = vec2( position.x, t );
  vColor = iColor;
  vRadius = iRadius;
  vDir = normalize( wp - cameraPosition );
  vDist = length( wp - cameraPosition );
  vec4 mv = viewMatrix * vec4( wp, 1.0 );
  vViewZ = mv.z;
  gl_Position = projectionMatrix * mv;
}
`,
    fragmentShader: /* glsl */ `
uniform float uTime;
uniform float uOpacity;
uniform vec3 uFogColor;
varying vec2 vUv;
varying vec3 vColor;
varying float vViewZ;
varying float vRadius;
varying vec3 vDir;
varying float vDist;
${SOFT_PARS}
${fogLibrary(fog)}
void main() {
  float core = exp( - vUv.x * vUv.x * 6.0 );
  float along = smoothstep( 0.0, 0.06, vUv.y ) * ( 1.0 - smoothstep( 0.55, 1.0, vUv.y ) );
  float flicker = 0.85 + 0.15 * sin( uTime * 1.7 + vUv.y * 12.0 );
  float a = core * along * flicker * uOpacity * sectSoftFade( vViewZ, vRadius * 2.0 );
  float od = sectHazeDepth( cameraPosition.y, vDir.y, vDist );
  a *= exp( - od * 0.8 );
  // Linear light, added unencoded (see createGlowMaterial).
  gl_FragColor = vec4( vColor * a, 1.0 );
}
`,
  });
}

/**
 * Soft shafts of light (the formation's core and its eight array eyes; lib/sect/formation.ts
 * formationShafts): additive vertical strips turned to face the camera about their axis
 * (instanced: iBase, iShape = height, fadeIn, halfLife, radius; iLook = opacity, streaks, wave
 * phase, rest share; iColor). A Gaussian across with no hard core line, fading in above the base,
 * halving every halfLife metres and gone by the top (formation.ts shaftProfile), with slow streaks
 * drifting up (uStreaks, off on the Low tier) and, for the eyes' wisps, the wave that runs round the
 * array (idle.ts). Fades where it meets geometry and in the haze. `motion` (IDLE_ON) is 0 with
 * reduced motion: the wisps rest.
 */
export function createShaftMaterial(fog: FogConstants, time: IUniform<number>, motion: IUniform<number>, look: SectLook = SECT_LOOK): ShaderMaterial {
  const F = look.formation;
  return new ShaderMaterial({
    name: "sect.shaft",
    transparent: true,
    depthWrite: false,
    blending: AdditiveBlending,
    fog: false,
    uniforms: {
      uTime: time,
      uMotion: motion,
      uStreaks: { value: 1 },
      tNoise: { value: getNoiseTexture() },
      ...SOFT_DEPTH,
    },
    vertexShader: /* glsl */ `
attribute vec3 iBase;
attribute vec4 iShape;
attribute vec4 iLook;
attribute vec3 iColor;
varying vec2 vUv;
varying vec4 vShape;
varying vec4 vLook;
varying vec3 vColor;
varying float vSeed;
varying float vViewZ;
varying vec3 vDir;
varying float vDist;
void main() {
  float height = iShape.x;
  float radius = iShape.w;
  float h = ( position.y * 0.5 + 0.5 ) * height;
  // Turned to the camera about the vertical axis, its front face toward it (side = up x toCam;
  // from straight above, any side will do).
  vec3 toCam = cameraPosition - iBase;
  toCam.y = 0.0;
  float l = length( toCam );
  vec3 side = l > 1e-3 ? vec3( toCam.z, 0.0, - toCam.x ) / l : vec3( 1.0, 0.0, 0.0 );
  vec3 wp = iBase + vec3( 0.0, h, 0.0 ) + side * position.x * radius * 1.6;
  vUv = vec2( position.x * 1.6, h );
  vShape = iShape;
  vLook = iLook;
  vColor = iColor;
  vSeed = fract( iBase.x * 0.0131 + iBase.z * 0.0077 );
  vec3 d = wp - cameraPosition;
  vDist = length( d );
  vDir = d / max( vDist, 1e-3 );
  vec4 mv = viewMatrix * vec4( wp, 1.0 );
  vViewZ = mv.z;
  gl_Position = projectionMatrix * mv;
}
`,
    fragmentShader: /* glsl */ `
uniform float uTime;
uniform float uMotion;
uniform float uStreaks;
uniform sampler2D tNoise;
varying vec2 vUv;
varying vec4 vShape;
varying vec4 vLook;
varying vec3 vColor;
varying float vSeed;
varying float vViewZ;
varying vec3 vDir;
varying float vDist;
${SOFT_PARS}
${fogLibrary(fog)}
${SCREEN_ADD_GLSL}
void main() {
  float x = vUv.x;
  float h = vUv.y;
  float height = vShape.x;
  // formation.ts shaftProfile.
  float across = exp( - x * x * 2.5 ) * ( 1.0 - smoothstep( 1.3, 1.6, abs( x ) ) );
  float along = smoothstep( 0.0, vShape.y, h ) * exp2( - max( h, 0.0 ) / vShape.z ) * ( 1.0 - smoothstep( height * 0.6, height, h ) );
  float a = across * along * vLook.x;
  if ( uStreaks > 0.5 && vLook.y > 0.0 ) {
    // Long soft streaks drifting up: two noise reads stretched along the shaft.
    float v = h / ( vShape.w * 9.0 ) - uTime * ${glslFloat(F.streakSpeed)};
    float n1 = texture2D( tNoise, vec2( x * 0.1 + vSeed, v ) ).r;
    float n2 = texture2D( tNoise, vec2( x * 0.23 + vSeed * 1.7, v * 2.3 - uTime * ${glslFloat(F.streakSpeed * 1.4)} ) ).r;
    a *= mix( 1.0, 0.35 + 1.3 * n1 * ( 0.55 + 0.9 * n2 ), vLook.y );
  }
  if ( vLook.z >= 0.0 ) {
    // lib/sect/idle.ts wave( t, period, i, n ) for station phase i / n.
    float w = fract( uTime / ${glslFloat(F.wave.period)} - vLook.z );
    float lit = w < ${glslFloat(F.wave.width)} ? pow( sin( 3.14159265 * w / ${glslFloat(F.wave.width)} ), 2.0 ) : 0.0;
    a *= vLook.w + ( 1.0 - vLook.w ) * lit * uMotion;
  }
  a *= sectSoftFade( vViewZ, vShape.w );
  float od = sectHazeDepth( cameraPosition.y, vDir.y, vDist );
  a *= exp( - od * 0.8 );
  // Linear light, added unencoded (see createGlowMaterial); on the Low tier's sRGB screen, the step
  // it makes over a mid background.
  gl_FragColor = vec4( sectScreenAdd( vColor * a, ${glslFloat(F.dome.screenBack)} ), 1.0 );
}
`,
  });
}

/**
 * The formation's barrier dome (the bake leaves it out: Blender's glass_shield is a fresnel
 * emission that cannot be baked). A unit hemisphere (y 0..1) drawn additively from both sides, in
 * pale gold: nearly invisible face-on, a thin rim at its silhouette, a seam where it meets the
 * plaza, and two shimmer bands sliding down a tortoise-shell lattice (lib/sect/formation.ts
 * domeAlpha, mirrored by sectDomeAlpha), fading in the haze and softly where it meets the ground.
 * uDetail 0 (the Low tier) keeps the rim and seam only; `motion` (IDLE_ON) stills the shimmer with
 * reduced motion.
 */
export function createDomeMaterial(fog: FogConstants, color: string, time: IUniform<number>, motion: IUniform<number> = { value: 1 }, look: SectLook = SECT_LOOK): ShaderMaterial {
  return new ShaderMaterial({
    name: "sect.dome",
    transparent: true,
    depthWrite: false,
    blending: AdditiveBlending,
    side: DoubleSide,
    fog: false,
    uniforms: {
      uTime: time,
      uMotion: motion,
      uDetail: { value: 1 },
      uColor: { value: linear(color) },
      ...SOFT_DEPTH,
    },
    vertexShader: /* glsl */ `
varying vec3 vNormalW;
varying vec3 vDir;
varying float vDist;
varying float vH;
varying vec2 vXZ;
varying float vViewZ;
void main() {
  vec4 wp = modelMatrix * vec4( position, 1.0 );
  vNormalW = normalize( mat3( modelMatrix ) * normal );
  vec3 d = wp.xyz - cameraPosition;
  vDist = length( d );
  vDir = d / max( vDist, 1e-3 );
  vH = position.y;
  vXZ = position.xz;
  vec4 mv = viewMatrix * wp;
  vViewZ = mv.z;
  gl_Position = projectionMatrix * mv;
}
`,
    fragmentShader: /* glsl */ `
uniform float uTime;
uniform float uMotion;
uniform float uDetail;
uniform vec3 uColor;
varying vec3 vNormalW;
varying vec3 vDir;
varying float vDist;
varying float vH;
varying vec2 vXZ;
varying float vViewZ;
${SOFT_PARS}
${fogLibrary(fog)}
${SCREEN_ADD_GLSL}
${domeGlsl(look.formation)}
void main() {
  float facing = abs( dot( normalize( vNormalW ), vDir ) );
  // The azimuth, safe at the apex (atan( 0, 0 ) is undefined, and a NaN here would bloom).
  float az = atan( vXZ.y, abs( vXZ.x ) + abs( vXZ.y ) > 1e-6 ? vXZ.x : 1.0 );
  // MSAA can run this at a pixel centre outside a grazing base triangle, extrapolating vH far below
  // 0: sectDomeAlpha clamps it, or the seam overflows to Inf and Inf * a zero soft fade is a NaN that
  // bloom spreads over the whole frame (black flashes leaving the formation on the high tier).
  float a = sectDomeAlpha( facing, vH, uTime, az, uDetail, uMotion );
  // The far wall's inner face, seen through the near one, keeps a share (a pale cap from above).
  a *= gl_FrontFacing ? 1.0 : ${glslFloat(look.formation.dome.backFace)};
  a *= sectSoftFade( vViewZ, 2.0 );
  float od = sectHazeDepth( cameraPosition.y, vDir.y, vDist );
  a *= exp( - od * 0.8 );
  // Linear light, added unencoded (see createGlowMaterial): encoded on its own, a faint face turned
  // the whole dome milky white on the Low tier, which gets the step over a mid background instead.
  gl_FragColor = vec4( sectScreenAdd( uColor * a, ${glslFloat(look.formation.dome.screenBack)} ), 1.0 );
}
`,
  });
}

/**
 * Unlit baked materials: fogged, not tone mapped twice, and graded with the look; rock and ground
 * get the tiling detail when the page has the texture.
 */
export function prepareBakedMaterial(mat: MeshBasicMaterial, detail?: DetailUniforms | null): void {
  mat.fog = true;
  mat.toneMapped = false;
  if (mat.customProgramCacheKey().startsWith("sect|")) return;
  patchMaterial(mat, { lit: false, exposure: 1, detail: bakedDetail(mat, detail) });
}
