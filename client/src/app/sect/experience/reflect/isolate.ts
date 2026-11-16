import type { Object3D, Scene } from "three";

/**
 * What a reflection sees of the scene's top level besides the loaded sets: the sky dome, the moon
 * and the cloud sea, and the grass where the pass wants it. Everything else there (petals, cranes,
 * birds, motes and butterflies, the forge fire, incense, the waterfalls' foam skirt) is left out:
 * small moving or soft-edged things that read their soft edges from the main view's depth, or would
 * only flicker at the reflections' resolution. The overlay (clouds, mist, beams) is a scene of its
 * own and never drawn.
 */
export const REFLECTED_DECOR: ReadonlySet<string> = new Set(["sect.sky", "sect.moon", "sect.cloudsea"]);
export const GRASS = "sect.grass";

/** What one reflection pass draws. */
export interface ReflectView {
  /** Top-level roots drawn as they are (the sets'). */
  roots: ReadonlySet<Object3D>;
  /** The grass too. */
  grass: boolean;
  /** Shown for the pass only: the backdrop's stand-ins for areas whose own meshes are left out. */
  show?: readonly Object3D[];
  /** Hidden for the pass: the mirror's own face while its surroundings are captured. */
  hide?: readonly Object3D[];
}

/** What reflectView reads of a loaded set (assets.ts LoadedSet has it all). */
export interface ReflectSet {
  id: string;
  /** Null for the global set. */
  need: readonly [number, number] | null;
  scenes: readonly Object3D[];
  /** The backdrop's stand-ins by area id (the global set's). */
  proxies: ReadonlyMap<string, readonly Object3D[]>;
  pond: object | null;
  drawn: boolean;
  /** Shown as far scenery (lib/sect/far.ts): its own meshes are on screen, its stand-in hidden. */
  far: boolean;
}

/**
 * What a pass draws: the global set and the pond's own area as they are, the grass if `o.grass`, and
 * the other drawn areas either as they are or (`o.standIns`) as the backdrop's low stand-ins (in a
 * reflection they are a few distant shapes, and their full meshes were most of its triangles). An
 * area shown as far scenery (LoadedSet.far) is drawn by its stand-in whatever `o.standIns` says: its
 * own roots are left out of the pass, and its stand-in, hidden on screen, is shown for it, so a
 * reflection sees what it saw before far areas were drawn in full. `hide`: hidden for the pass.
 */
export function reflectView(sets: readonly ReflectSet[], pond: object, o: { grass: boolean; standIns: boolean }, hide?: readonly Object3D[]): ReflectView {
  const roots = new Set<Object3D>();
  const show: Object3D[] = [];
  const global = sets.find((s) => s.need === null) ?? null;
  for (const s of sets) {
    if (s.drawn) {
      if (s === global || s.pond === pond || !o.standIns) {
        for (const r of s.scenes) roots.add(r);
      } else {
        for (const m of global?.proxies.get(s.id) ?? []) show.push(m);
      }
    } else if (s.far) {
      for (const m of global?.proxies.get(s.id) ?? []) show.push(m);
    }
  }
  return { roots, grass: o.grass, show, hide };
}

/** Sets the scene up for one reflection pass; returns the call that puts everything back. */
export function isolateForReflection(scene: Scene, view: ReflectView): () => void {
  const hidden: Object3D[] = [];
  const shown: Object3D[] = [];
  for (const o of scene.children) {
    if (!o.visible || view.roots.has(o) || REFLECTED_DECOR.has(o.name) || (view.grass && o.name === GRASS)) continue;
    o.visible = false;
    hidden.push(o);
  }
  for (const o of view.hide ?? []) {
    if (!o.visible) continue;
    o.visible = false;
    hidden.push(o);
  }
  for (const o of view.show ?? []) {
    if (o.visible) continue;
    o.visible = true;
    shown.push(o);
  }
  return () => {
    for (const o of hidden) o.visible = true;
    for (const o of shown) o.visible = false;
  };
}
