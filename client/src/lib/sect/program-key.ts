/**
 * What decides which shader program three builds for a mesh, besides its material, and what a
 * material's copy must carry to get the same one (three r186, WebGLPrograms getParameters and
 * getProgramCacheKey). A stand-in that compiles a program ahead of a real draw (live.tsx warmCopies,
 * live-shadow.ts) is only worth it when its key is the real one: any field that differs builds a
 * program nobody draws with, and the real one is then linked on the frame that first draws it.
 *
 * The mesh's part (programVariant): its kind (instanced, with instance colours or morphs, batched,
 * skinned, points) and its geometry's attributes (position, normal, a tangent with a normal map, a
 * four-channel colour with vertex colours, morph targets). Two meshes with one material and the same
 * variant share a program; a mesh whose variant differs gets one of its own.
 *
 * The material's part that Material.clone leaves behind (keepProgramFields): three's Material.copy
 * carries neither `flatShading` nor `defines`. GLTFLoader sets flatShading on its copy of an unlit
 * material for a mesh without normals, which is every baked atlas mesh (position and uv only), and
 * the scene makes copies with defines of their own (idle.ts SECT_KEEP_GREEN, prepare.ts SECT_FAR_SET).
 */

/** A buffer attribute as the key reads it: only its width counts (a colour of four is a colour with alpha). */
interface AttributeLike {
  readonly itemSize: number;
}

/** The parts of a mesh and its geometry three's program key reads (structural: no three import). */
export interface ProgramMesh {
  readonly isInstancedMesh?: boolean;
  readonly instanceColor?: unknown;
  readonly morphTexture?: unknown;
  readonly isBatchedMesh?: boolean;
  readonly isSkinnedMesh?: boolean;
  readonly isPoints?: boolean;
  readonly geometry: {
    readonly attributes: Readonly<Record<string, AttributeLike | undefined>>;
    readonly morphAttributes: Readonly<Record<string, readonly unknown[] | undefined>>;
  };
}

/** The material fields that decide whether a mesh's attributes count (a tangent needs a normal map, an alpha colour needs vertex colours). */
export interface ProgramMaterial {
  readonly vertexColors?: boolean;
  readonly normalMap?: unknown;
  readonly anisotropy?: number;
  readonly map?: unknown;
  readonly alphaMap?: unknown;
}

const bit = (b: boolean) => (b ? "1" : "0");

/**
 * The mesh's part of three's program key for this material: equal for two meshes exactly when three
 * would give them (with this material) the same program. `instanceColor` and `morphTexture` count
 * when set (three tests them against null).
 */
export function programVariant(mesh: ProgramMesh, material: ProgramMaterial): string {
  const g = mesh.geometry;
  const a = g.attributes;
  const inst = mesh.isInstancedMesh === true;
  const morph = g.morphAttributes;
  const morphOf = morph.position ?? morph.normal ?? morph.color;
  const tangentUsed = !!material.normalMap || (material.anisotropy ?? 0) > 0;
  return [
    `i${bit(inst)}${bit(inst && mesh.instanceColor != null)}${bit(inst && mesh.morphTexture != null)}`,
    `b${bit(mesh.isBatchedMesh === true)}`,
    `s${bit(mesh.isSkinnedMesh === true)}`,
    `p${bit(!!a.position)}`,
    `n${bit(!!a.normal)}`,
    `t${bit(!!a.tangent && tangentUsed)}`,
    `c${bit(material.vertexColors === true && a.color?.itemSize === 4)}`,
    `m${bit(!!morph.position)}${bit(!!morph.normal)}${bit(!!morph.color)}${morphOf ? morphOf.length : 0}`,
    `u${bit(mesh.isPoints === true && !!a.uv && (!!material.map || !!material.alphaMap))}`,
  ].join("|");
}

/**
 * The material fields three's program key reads that Material.copy (and so clone) does not carry
 * over; each is set on a material by hand, never by its own class's copy.
 */
export const CLONE_DROPS = ["flatShading", "defines", "extensions", "index0AttributeName", "glslVersion"] as const;

/**
 * Gives a material's copy the program fields its clone left behind (CLONE_DROPS), so the copy
 * compiles the program the material itself would. Defines are copied, not shared.
 */
export function keepProgramFields(source: object, copy: object): void {
  const from = source as Record<string, unknown>;
  const to = copy as Record<string, unknown>;
  for (const f of CLONE_DROPS) {
    const v = from[f];
    if (v === undefined) continue;
    to[f] = v !== null && typeof v === "object" ? { ...(v as Record<string, unknown>) } : v;
  }
}
