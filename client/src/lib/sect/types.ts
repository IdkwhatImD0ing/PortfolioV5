/**
 * Data contract for the /sect fly-through (public/sect/full/*, and the first test in public/sect/proto/*).
 * Everything is in three.js world space: Y up, glTF convention three = (bx, bz, -by).
 * Pure types only: no three.js import, so these files stay testable in node.
 */

export type Vec3 = [number, number, number];
/** Quaternion as (x, y, z, w), three.js order. */
export type Quat = [number, number, number, number];

/**
 * One streamed piece of the world: an area's detailed GLBs (chunk id = area id), drawn while the
 * camera is within `need` and replaced by the backdrop's reduced proxy of that area otherwise.
 */
export interface ChunkInfo {
  id: string;
  /** GLB files (".glb.gz" is gzip-compressed and inflated in the browser), relative to the manifest. */
  files: string[];
  /** Same order as `files`, textures of at most 2048 px (phones and the low tier), or null. */
  filesLow: string[] | null;
  /** Blender frames [first, last] during which the chunk must be drawn. */
  need: [number, number];
  /** Download size of `files` (0 when unknown). */
  bytes: number;
  bytesLow: number | null;
  /** Triangles in the chunk (0 when unknown). */
  tris: number;
  /**
   * GPU memory the chunk's textures take once uploaded (RGBA8 with mips), for `files` and
   * `filesLow`; null or absent when the packer did not measure it (estimated from `bytes` then).
   */
  texBytes?: number | null;
  texBytesLow?: number | null;
}

/**
 * manifest.json, version 2: global files (backdrop with a reduced proxy of every area) always
 * loaded first, then per-area chunks streamed by the camera position. A version 1 manifest (the
 * first test's flat `scene` list) is read as global files with no chunks.
 */
export interface SectManifest {
  version: number;
  /** true: materials are unlit with baked lighting atlases. false: plain stand-in colours, lit at runtime. */
  baked: boolean;
  camera: string;
  meta: string;
  /** Volume cloud puffs as ellipsoids (clouds.json), drawn as soft sprites; null when absent. */
  clouds: string | null;
  flyer: string | null;
  flyerPath: string | null;
  /** A global water GLB (version 1); in version 2 water lives in the chunks and this is null. */
  water: string | null;
  /** Tileable detail texture for baked rock and ground (detail.webp, lib/sect/detail.ts), when packed. */
  detail?: string;
  /** Always loaded, before any chunk. */
  global: string[];
  /** Same order as `global`, low-tier textures, or null. */
  globalLow: string[] | null;
  /** In flight order. */
  chunks: ChunkInfo[];
}

export interface CameraFrame {
  f: number;
  p: Vec3;
  q: Quat;
  fovY: number;
}

export interface Hold {
  id: string;
  label: string;
  frame: number;
}

export interface CameraData {
  fps: number;
  frameStart: number;
  frameEnd: number;
  frames: CameraFrame[];
  holds: Hold[];
  startFrame: number;
  /** Width / height of the Blender film the fovY was exported for. */
  refAspect: number;
  near: number;
  far: number;
}

export interface PathFrame {
  f: number;
  p: Vec3;
  q: Quat;
}

export interface FlyerPath {
  frameStart: number;
  frameEnd: number;
  frames: PathFrame[];
}

export interface Waterfall {
  name: string;
  kind: string;
  position: Vec3;
  /** Size in the waterfall's own frame (x across, y up, z through); `rotation` turns it into place. */
  size: Vec3;
  rotation: Quat;
  nearestM: number;
  /** Lip-left, lip-right, foot-right, foot-left in world space, when exported. */
  corners: [Vec3, Vec3, Vec3, Vec3] | null;
  /** Where the water lands (world space), when exported. */
  foot: Vec3 | null;
  /** Relative fall speed (Blender's obj['flow']). */
  flow: number;
  /** Chunk the waterfall belongs to (its geometry streams with it), or null (global). */
  chunk?: string | null;
}

/** A glowing light beam (additive FX in Blender, not in the bake): a vertical column. */
export interface LightBeam {
  name: string;
  base: Vec3;
  top: Vec3;
  radius: number;
  color: string;
  nearestM: number;
  /** Chunk the beam belongs to, or null (global). */
  chunk?: string | null;
}

/** One volume cloud puff from Blender: the unit sphere mapped by three semi-axes. */
export interface CloudPuff {
  /** Centre (three space). */
  c: Vec3;
  /** Semi-axes in three space: the puff is { c + a0*x + a1*y + a2*z : |(x,y,z)| <= 1 }. */
  axes: [Vec3, Vec3, Vec3];
  /** Blender's size-normalised volume density (about 0.05 for flat bank bases, 0.3-0.6 for puffs). */
  density: number;
  /** Source tag (sect/mist.py writes "mist.band", "mist.isle", "mist.gorge"); absent for Blender's puffs. */
  kind?: string;
}

export interface HotspotInfo {
  id: string;
  label: string;
  center: Vec3;
  size: Vec3;
  /** Area id the hotspot belongs to (meta.json v2), or null. */
  area?: string | null;
  /** Chunk whose GLBs hold the hotspot's meshes, or null (global or engine-drawn, like the moon). */
  chunk?: string | null;
}

/**
 * One hover box of a Jin Yong reference (meta.json "lore", lib/sect/lore.ts). Decorative: never a
 * hotspot, never clicked. A reference may have several boxes (the two altars, the five banners).
 */
export interface LoreBox {
  id: string;
  center: Vec3;
  size: Vec3;
  /** The content hotspot whose subtree already holds the objects (its label names them), or null. */
  host: string | null;
  /** The stop it belongs to, or null. */
  area: string | null;
}

/** An area's place in the world and on the camera path (meta.json "areas"). */
export interface AreaMeta {
  id: string;
  label: string;
  /** A point at the heart of the area (three space). */
  anchor: Vec3;
  /** Rough radius of the area (m). */
  footprint: number;
  frameStart: number;
  frameEnd: number;
  heroFrame: number;
}

/**
 * A fire as export_web.py writes it to meta.fires (from the areas' fire anchors): the page draws
 * flames in it (lib/sect/flames.ts).
 */
export interface FireAnchor {
  id: string;
  /**
   * "furnace" (an opening), "kiln" (a fire box), "cauldron" (a molten surface) or "altar" /
   * "brazier" / "holy_fire" (a free-standing fire, a blaze: position its foot, radius and height its
   * size as seen, as a carved flame's, 0 for the page's); others are skipped.
   */
  kind: string;
  area: string | null;
  chunk: string | null;
  /** furnace: centre of the opening's bottom edge on its face; kiln, cauldron: centre of the fire's foot. */
  position: Vec3;
  /** furnace: the opening's outward facing (horizontal). */
  normal: Vec3 | null;
  /** furnace: the opening's size (m); kiln: its fire box's width when there is no radius. */
  width: number;
  /** furnace: the opening's height; kiln, cauldron: how tall the flames stand (0: from the size). */
  height: number;
  /** furnace: how deep its fire box goes (0: from the opening's size). */
  depth: number;
  /** kiln, cauldron: half the bed's width. */
  radius: number;
}

export interface SectMeta {
  sun: { direction: Vec3; color: string };
  sky: {
    zenith: string;
    horizon: string;
    horizonSun: string;
    belowHorizon: string;
    /** Equirectangular sky image (three convention, sRGB, already tone mapped). */
    texture: string | null;
    asRenderedTop: string | null;
  };
  fog: {
    color: string;
    scatterColor: string;
    /** Extinction per metre at baseY. */
    density: number;
    baseY: number;
    /** Height over which the haze thins by a factor e. */
    falloff: number;
  };
  moon: {
    position: Vec3;
    radius: number;
    color: string;
    halo: { position: Vec3; radius: number } | null;
  } | null;
  cloudSea: {
    y: number;
    billowTopY: number;
    fogTopY: number;
    fogBottomY: number;
    color: string;
    extent: number;
  };
  waterfalls: Waterfall[];
  beams: LightBeam[];
  hotspots: HotspotInfo[];
  /** The Jin Yong references' hover boxes (parseMeta: empty when the file has none). Never hotspots. */
  lore?: LoreBox[];
  /** The areas along the path (may be empty in older files). */
  areas: AreaMeta[];
  /** Fires the page draws flames in (flames.ts; parseMeta: empty when the file has none). */
  fires?: FireAnchor[];
  /** Blender's vignette strength (0.22 = 22 % corner darkening). */
  vignette: number;
  /** Blender's view exposure in stops. */
  exposure: number;
}
