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
