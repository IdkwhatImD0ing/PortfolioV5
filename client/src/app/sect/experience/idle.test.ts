import { describe, expect, it } from "vitest";
import {
  BoxGeometry,
  BufferAttribute,
  type BufferGeometry,
  CylinderGeometry,
  Group,
  InterleavedBuffer,
  InterleavedBufferAttribute,
  Mesh,
  MeshBasicMaterial,
  type Object3D,
  PlaneGeometry,
  Vector3,
} from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { BANNER_HANGS, inCylinder, inHang, splitTriangles, type Cylinder } from "@/lib/sect/idle";
import { planIdle, planIdleSliced } from "./idle";
import type { HotspotEntry } from "./prepare";

/** The library hotspot: the carve takes what lies 8-19 m from its axis, from 4.3 m up to 2 m above it. */
const CENTER: [number, number, number] = [40, 120, -300];
const SIZE: [number, number, number] = [30, 24, 30];
const GROUND = CENTER[1] - SIZE[1] / 2;
const CYL: Cylinder = { x: CENTER[0], z: CENTER[2], rMin: 8, rMax: 19, yMin: GROUND + 4.3, yMax: GROUND + SIZE[1] + 2 };

function hotspots(): Map<string, HotspotEntry> {
  const e: HotspotEntry = { id: "library", label: "Library", center: [...CENTER], size: [...SIZE], chunk: "library", uniform: { value: 0 } };
  return new Map([["library", e]]);
}

/** Rings of scenery round the pagoda: one in the band (carved), one inside it, one outside, a box far off. */
function scenery(): BufferGeometry {
  const at = (g: BufferGeometry, y: number) => g.translate(CENTER[0], y, CENTER[2]);
  const parts = [
    at(new CylinderGeometry(13, 13, 14, 96, 24, true), GROUND + 13),
    at(new CylinderGeometry(5, 5, 14, 48, 12, true), GROUND + 13),
    at(new CylinderGeometry(25, 25, 14, 96, 12, true), GROUND + 13),
    // Straddles the band's floor: half its triangles are carved.
    at(new CylinderGeometry(16, 16, 4, 64, 16, true), GROUND + 4.3),
    new BoxGeometry(4, 4, 4, 8, 8, 8).translate(400, 0, 0),
  ];
  return mergeGeometries(parts)!;
}

/** Positions quantized to normalized 16-bit integers, undone by the mesh's scale (as a baked GLB). */
function quantized(g: BufferGeometry, scale: number): BufferGeometry {
  const src = g.getAttribute("position");
  const q = new Int16Array(src.count * 3);
  for (let i = 0; i < src.count * 3; i++) q[i] = Math.round(((src.array as Float32Array)[i] / scale) * 32767);
  g.setAttribute("position", new BufferAttribute(q, 3, true));
  return g;
}

/**
 * Two merged meshes under a moved parent: one plain, one quantized with a scale. The parent's
 * offset is undone in each mesh's geometry, so the world positions are the scenery's.
 */
function scene(): { root: Object3D; meshes: Mesh[] } {
  const root = new Group();
  const parent = new Group();
  parent.position.set(3, -2, 5);
  root.add(parent);
  const mat = new MeshBasicMaterial({ name: "baked.library_A0" });
  const a = new Mesh(scenery().translate(-3, 2, -5), mat);
  a.name = "plain";
  const S = 512;
  const b = new Mesh(quantized(scenery().translate(-3 - 1, 2 - 1, -5 - 1), S), mat);
  b.name = "quantized";
  b.position.set(1, 1, 1);
  b.scale.setScalar(S);
  parent.add(a, b);
  root.updateMatrixWorld(true);
  return { root, meshes: [a, b] };
}

/** The split the old one-go carve made: world positions in 32-bit floats, then splitTriangles. */
function reference(m: Mesh): { kept: number[]; carved: number[] } {
  const pos = m.geometry.getAttribute("position");
  const world = new Float32Array(pos.count * 3);
  const v = new Vector3();
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i).applyMatrix4(m.matrixWorld);
    world[i * 3] = v.x;
    world[i * 3 + 1] = v.y;
    world[i * 3 + 2] = v.z;
  }
  return splitTriangles(m.geometry.index!.array, pos.count, world, (x, y, z) => inCylinder(CYL, x, y, z));
}

function carvedOf(m: Mesh): Mesh | undefined {
  return m.parent!.children.find((c) => c !== m && (c as Mesh).isMesh && c.name === `${m.name}.idle`) as Mesh | undefined;
}

describe("planIdle (the library's spiral)", () => {
  it("carves exactly the triangles the one-go split did, in the same index types", () => {
    const { root, meshes } = scene();
    const want = meshes.map(reference);
    const plan = planIdle("library", root, new Map(), hotspots());
    expect(plan.rigid.map((r) => r.name)).toEqual(["library.spiral"]);
    expect(plan.rigid[0].groups[0].meshes.map((x) => x.m.name)).toEqual(["plain.idle", "quantized.idle"]);
    meshes.forEach((m, k) => {
      const cm = carvedOf(m)!;
      expect(want[k].carved.length).toBeGreaterThan(3000);
      expect(want[k].kept.length).toBeGreaterThan(3000);
      expect(Array.from(cm.geometry.index!.array)).toEqual(want[k].carved);
      expect(Array.from(m.geometry.index!.array)).toEqual(want[k].kept);
      expect(cm.geometry.index!.array).toBeInstanceOf(Uint16Array);
      expect(m.geometry.index!.array).toBeInstanceOf(Uint16Array);
      // The carved piece shares the scenery's vertex buffers.
      expect(cm.geometry.getAttribute("position")).toBe(m.geometry.getAttribute("position"));
      expect(cm.material).toBe(m.material);
    });
  });

  it("reads interleaved 16-bit and plain 8-bit positions as three does", () => {
    const root = new Group();
    const mat = new MeshBasicMaterial();
    // Interleaved 16-bit, normalized, after another value (as the baked GLBs' positions).
    const S = 512;
    const g = scenery();
    const src = g.getAttribute("position");
    const buf = new InterleavedBuffer(new Int16Array(src.count * 5), 5);
    for (let i = 0; i < src.count; i++) {
      buf.array[i * 5] = 7;
      for (let c = 0; c < 3; c++) buf.array[i * 5 + 1 + c] = Math.round((src.array[i * 3 + c] / S) * 32767);
    }
    g.setAttribute("position", new InterleavedBufferAttribute(buf, 3, 1, true));
    g.boundingBox = null;
    const a = new Mesh(g, mat);
    a.name = "interleaved";
    a.scale.setScalar(S);
    // Unsigned 8-bit, normalized, placed by the mesh's matrix (coarse, but the same coarse both ways).
    const h = scenery();
    h.computeBoundingBox();
    const { min, max } = h.boundingBox!;
    const p = h.getAttribute("position");
    const q = new Uint8Array(p.count * 3);
    for (let i = 0; i < p.count * 3; i++) {
      const lo = min.getComponent(i % 3);
      q[i] = Math.round(((p.array[i] - lo) / (max.getComponent(i % 3) - lo)) * 255);
    }
    h.setAttribute("position", new BufferAttribute(q, 3, true));
    h.boundingBox = null;
    const b = new Mesh(h, mat);
    b.name = "u8";
    b.position.copy(min);
    b.scale.copy(max).sub(min);
    root.add(a, b);
    root.updateMatrixWorld(true);
    const want = [a, b].map(reference);
    planIdle("library", root, new Map(), hotspots());
    [a, b].forEach((m, k) => {
      expect(want[k].carved.length).toBeGreaterThan(300);
      expect(Array.from(carvedOf(m)!.geometry.index!.array)).toEqual(want[k].carved);
      expect(Array.from(m.geometry.index!.array)).toEqual(want[k].kept);
    });
  });

  it("bounds the carved piece by its own vertices", () => {
    const { root, meshes } = scene();
    planIdle("library", root, new Map(), hotspots());
    for (const m of meshes) {
      const cm = carvedOf(m)!;
      const s = cm.geometry.boundingSphere!;
      const pos = cm.geometry.getAttribute("position");
      const ix = cm.geometry.index!.array;
      const v = new Vector3();
      let far = 0;
      for (let i = 0; i < ix.length; i++) far = Math.max(far, v.fromBufferAttribute(pos, ix[i]).distanceTo(s.center));
      // Every carved vertex inside, and one on the sphere.
      expect(far).toBeLessThanOrEqual(s.radius * (1 + 1e-9));
      expect(far).toBeGreaterThan(s.radius * (1 - 1e-9));
      const whole = cm.geometry.clone();
      whole.computeBoundingSphere();
      expect(s.radius).toBeLessThan(whole.boundingSphere!.radius);
    }
  });
});

describe("planIdle (the gate's banners)", () => {
  /** The west plaza banner nearest the stairs: hook at (-17.63, 53.59, 30), arm along +x, cloth facing z. */
  const HANG = BANNER_HANGS.gate.find((h) => h.hook[0] < 0 && h.hook[2] === 30)!;
  const CLOTH_TRIS = 6 * 20 * 2;

  /**
   * Merged scenery as the bake leaves it: the plaza's ground, the pole, the arm above the hook and
   * the banner's cloth (6 x 20 quads, 1.7 x 8.4 m under the hook) in one mesh, under a moved parent.
   */
  function gateScene(scale = 1): { root: Object3D; mesh: Mesh; mat: MeshBasicMaterial; before: number[] } {
    const [x, y, z] = HANG.hook;
    const merged = mergeGeometries([
      new PlaneGeometry(60, 60, 6, 6).rotateX(-Math.PI / 2).translate(0, 40, 20),
      new CylinderGeometry(0.07, 0.07, 14, 16, 4).translate(x - 1.77, 47, z),
      new BoxGeometry(1.77, 0.06, 0.06).translate(x - 0.885, y + 0.08, z),
      new PlaneGeometry(1.7, 8.4, 6, 20).translate(x, y - 4.2, z),
    ])!;
    const root = new Group();
    const parent = new Group();
    parent.position.set(3, -2, 5);
    root.add(parent);
    const mat = new MeshBasicMaterial({ name: "baked.gate_A0" });
    const g = scale === 1 ? merged.translate(-3, 2, -5) : quantized(merged.translate(-3 - 1, 2 - 1, -5 - 1), scale);
    const mesh = new Mesh(g, mat);
    mesh.name = "gate.baked.A0.c7";
    if (scale !== 1) {
      mesh.position.set(1, 1, 1);
      mesh.scale.setScalar(scale);
    }
    parent.add(mesh);
    root.updateMatrixWorld(true);
    return { root, mesh, mat, before: Array.from(g.index!.array) };
  }

  /** World positions of a mesh's triangles, corner by corner. */
  function triangles(m: Mesh): number[][] {
    const pos = m.geometry.getAttribute("position");
    const v = new Vector3();
    return Array.from(m.geometry.index!.array, (i) => v.fromBufferAttribute(pos, i).applyMatrix4(m.matrixWorld).toArray());
  }

  for (const scale of [1, 512]) {
    it(`cuts out only the cloth, onto a small geometry and a sway copy of its material (scale ${scale})`, () => {
      const { root, mesh, mat, before } = gateScene(scale);
      const all = triangles(mesh);
      const plan = planIdle("gate", root, new Map(), new Map());
      expect(plan.sway).toBe(1);
      const piece = carvedOf(mesh)!;
      expect(piece.geometry.index!.count).toBe(CLOTH_TRIS * 3);
      expect(mesh.geometry.index!.count).toBe(before.length - CLOTH_TRIS * 3);
      // Every triangle drawn once, in the same place: the cloth by the piece, the rest by the scenery.
      const key = (t: number[][]) => t.map((p) => p.map((c) => c.toFixed(3)).join(",")).join("|");
      const group = (t: number[][]) => Array.from({ length: t.length / 3 }, (_, k) => key(t.slice(k * 3, k * 3 + 3))).sort();
      expect([...group(triangles(piece)), ...group(triangles(mesh))].sort()).toEqual(group(all));
      for (const p of triangles(piece)) expect(inHang(HANG, p[0], p[1], p[2])).toBe(true);
      // Only the cloth's own 7 x 21 vertices, stored as the scenery stores them.
      const pos = piece.geometry.getAttribute("position");
      expect(pos.count).toBe(7 * 21);
      expect(pos.array.constructor).toBe(mesh.geometry.getAttribute("position").array.constructor);
      expect(pos.normalized).toBe(mesh.geometry.getAttribute("position").normalized);
      expect(Object.keys(piece.geometry.attributes).sort()).toEqual([...Object.keys(mesh.geometry.attributes), "sectSway"].sort());
      // The scenery keeps its material and program; the cloth sways on a copy.
      expect(mesh.material).toBe(mat);
      expect(mat.userData.sectSway).toBeUndefined();
      expect(mat.customProgramCacheKey()).not.toMatch(/sway/);
      const copy = piece.material as MeshBasicMaterial;
      expect(copy).not.toBe(mat);
      expect(copy.name).toBe(mat.name);
      expect(copy.userData.sectSway).toBe(true);
      expect(copy.customProgramCacheKey()).toMatch(/\|sway$/);
      // Still at the hook, a full swing at the tails, along the cloth's normal (world z).
      const sway = piece.geometry.getAttribute("sectSway");
      const v = new Vector3();
      let top = 0;
      let tail = 0;
      for (let i = 0; i < pos.count; i++) {
        const y = v.fromBufferAttribute(pos, i).applyMatrix4(piece.matrixWorld).y;
        const s = new Vector3(sway.getX(i), sway.getY(i), sway.getZ(i)).multiplyScalar(scale);
        expect(Math.abs(s.x) + Math.abs(s.y)).toBeLessThan(1e-6);
        if (Math.abs(y - HANG.hook[1]) < 0.01) top = Math.max(top, Math.abs(s.z));
        if (Math.abs(y - (HANG.hook[1] - HANG.length)) < 0.01) tail = Math.max(tail, Math.abs(s.z));
      }
      // (Quantized positions sit up to 8 mm off the plane's rows.)
      expect(top).toBeLessThan(1e-3);
      expect(tail).toBeCloseTo(1, 2);
      // Bounded with room for the swing.
      const s = piece.geometry.boundingSphere!;
      expect(s.radius * scale).toBeGreaterThan(Math.hypot(0.85, 4.2) + 0.44);
    });
  }

  it("leaves the other areas' scenery whole", () => {
    const { root, mesh, before } = gateScene();
    const plan = planIdle("mirror", root, new Map(), new Map());
    expect(plan.sway).toBe(0);
    expect(carvedOf(mesh)).toBeUndefined();
    expect(Array.from(mesh.geometry.index!.array)).toEqual(before);
  });

  it("cuts the same in slices", async () => {
    const one = gateScene();
    planIdle("gate", one.root, new Map(), new Map());
    const two = gateScene();
    let t = 0;
    const plan = await planIdleSliced("gate", two.root, new Map(), new Map(), { budgetMs: 2, now: () => (t += 1), pause: async () => {} });
    expect(plan.sway).toBe(1);
    expect(Array.from(two.mesh.geometry.index!.array)).toEqual(Array.from(one.mesh.geometry.index!.array));
    expect(Array.from(carvedOf(two.mesh)!.geometry.index!.array)).toEqual(Array.from(carvedOf(one.mesh)!.geometry.index!.array));
  });
});

describe("planIdle (the forge's, the arena's and the mission hall's banners)", () => {
  const CLOTH_TRIS = 4 * 12 * 2;

  /**
   * An area's merged scenery: the ground 10 m under its banners and, for each of its hangs, the
   * pole, the arm out to the hook and a cloth (4 x 12 quads) hanging from the hook, turned along
   * the arm. The arena also has a hackathon banner, a hotspot of its own, between two of them.
   */
  function areaScene(area: string): { root: Object3D; mesh: Mesh; before: number; hotspots: Map<string, Mesh[]>; hot: Mesh | null } {
    const hangs = BANNER_HANGS[area];
    const parts: BufferGeometry[] = [];
    let cx = 0;
    let cz = 0;
    for (const h of hangs) {
      const [x, y, z] = h.hook;
      const turn = Math.atan2(-h.out[1], h.out[0]);
      const arm = 0.75 + 0.6 * h.width;
      const place = (g: BufferGeometry) => g.rotateY(turn).translate(x, y, z);
      parts.push(
        place(new PlaneGeometry(h.width, h.length, 4, 12).translate(0, -h.length / 2, 0)),
        place(new CylinderGeometry(0.07, 0.07, 10.4, 8, 4).translate(-arm, -4.8, 0)),
        place(new BoxGeometry(arm, 0.06, 0.06).translate(-arm / 2, 0.08, 0)),
      );
      cx += x / hangs.length;
      cz += z / hangs.length;
    }
    parts.push(new PlaneGeometry(80, 80, 8, 8).rotateX(-Math.PI / 2).translate(cx, hangs[0].hook[1] - 10, cz));
    const root = new Group();
    const mesh = new Mesh(mergeGeometries(parts)!, new MeshBasicMaterial({ name: `baked.${area}_A0` }));
    mesh.name = `${area}.baked.A0.c3`;
    root.add(mesh);
    const hotspots = new Map<string, Mesh[]>();
    let hot: Mesh | null = null;
    if (area === "arena") {
      const [a, b] = hangs;
      const g = new PlaneGeometry(1.3, 5.2, 4, 12).translate((a.hook[0] + b.hook[0]) / 2, a.hook[1] - 2.6, (a.hook[2] + b.hook[2]) / 2);
      hot = new Mesh(g, new MeshBasicMaterial({ name: "hotspot.hackathon" }));
      hot.name = "hotspot.hackathon:0";
      root.add(hot);
      hotspots.set("hackathon:0", [hot]);
    }
    root.updateMatrixWorld(true);
    return { root, mesh, before: mesh.geometry.index!.count, hotspots, hot };
  }

  for (const area of ["forge", "arena", "mission"]) {
    it(`cuts out every cloth of the ${area} and sways it across itself`, () => {
      const hangs = BANNER_HANGS[area];
      const { root, mesh, before, hotspots, hot } = areaScene(area);
      const plan = planIdle(area, root, hotspots, new Map());
      // The carved piece, and the arena's hackathon banner by its own shape.
      expect(plan.sway).toBe(area === "arena" ? 2 : 1);
      const piece = carvedOf(mesh)!;
      expect(piece.geometry.index!.count).toBe(CLOTH_TRIS * 3 * hangs.length);
      expect(mesh.geometry.index!.count).toBe(before - CLOTH_TRIS * 3 * hangs.length);
      expect(piece.material).not.toBe(mesh.material);
      // Each carved triangle lies in one banner's space, and every banner gives its own.
      const pos = piece.geometry.getAttribute("position");
      const ix = piece.geometry.index!.array;
      const v = new Vector3();
      const per = hangs.map(() => 0);
      for (let t = 0; t < ix.length; t += 3) {
        const corners = [0, 1, 2].map((k) => v.fromBufferAttribute(pos, ix[t + k]).applyMatrix4(piece.matrixWorld).toArray());
        const k = hangs.findIndex((h) => corners.every((p) => inHang(h, p[0], p[1], p[2])));
        expect(k).toBeGreaterThanOrEqual(0);
        per[k]++;
      }
      expect(per).toEqual(hangs.map(() => CLOTH_TRIS));
      // Level, across the cloth (normal to its arm), full at the tails.
      const sway = piece.geometry.getAttribute("sectSway");
      for (let i = 0; i < pos.count; i++) {
        const p = v.fromBufferAttribute(pos, i).applyMatrix4(piece.matrixWorld);
        const h = hangs.reduce((a, b) => (Math.hypot(b.hook[0] - p.x, b.hook[2] - p.z) < Math.hypot(a.hook[0] - p.x, a.hook[2] - p.z) ? b : a));
        expect(sway.getY(i)).toBe(0);
        expect(sway.getX(i) * h.out[0] + sway.getZ(i) * h.out[1]).toBeCloseTo(0, 6);
        if (Math.abs(p.y - (h.hook[1] - h.length)) < 1e-3) expect(Math.hypot(sway.getX(i), sway.getZ(i))).toBeCloseTo(1, 5);
      }
      // The hackathon banner stays whole, swaying on its own.
      if (hot) {
        expect(hot.geometry.getAttribute("sectSway")).toBeDefined();
        expect(root.children.filter((c) => c.name === `${hot.name}.idle`)).toHaveLength(0);
      }
    });
  }
});

describe("planIdleSliced", () => {
  it("makes planIdle's plan, letting the browser in between slices", async () => {
    const one = scene();
    const whole = planIdle("library", one.root, new Map(), hotspots());
    const two = scene();
    let t = 0;
    let pauses = 0;
    // A clock that runs a millisecond per reading: every slice ends after a step or two.
    const sliced = await planIdleSliced("library", two.root, new Map(), hotspots(), {
      budgetMs: 2,
      now: () => (t += 1),
      pause: async () => {
        pauses++;
      },
    });
    expect(pauses).toBeGreaterThan(10);
    expect(sliced.rigid.map((r) => r.name)).toEqual(whole.rigid.map((r) => r.name));
    expect(sliced.rigid[0].pivot.toArray()).toEqual(whole.rigid[0].pivot.toArray());
    two.meshes.forEach((m, k) => {
      const a = one.meshes[k];
      expect(Array.from(m.geometry.index!.array)).toEqual(Array.from(a.geometry.index!.array));
      expect(Array.from(carvedOf(m)!.geometry.index!.array)).toEqual(Array.from(carvedOf(a)!.geometry.index!.array));
      expect(carvedOf(m)!.geometry.boundingSphere).toEqual(carvedOf(a)!.geometry.boundingSphere);
    });
  });

  it("stops between slices once its load is cancelled, with no mesh half carved", async () => {
    const { root, meshes } = scene();
    const before = meshes.map((m) => Array.from(m.geometry.index!.array));
    const want = meshes.map(reference);
    const ac = new AbortController();
    let t = 0;
    let pauses = 0;
    const plan = await planIdleSliced("library", root, new Map(), hotspots(), {
      signal: ac.signal,
      budgetMs: 1,
      now: () => (t += 1),
      pause: async () => {
        // Cancelled once the first mesh's split has begun.
        if (++pauses === 8) ac.abort();
      },
    });
    expect(pauses).toBe(8);
    expect(plan.rigid).toEqual([]);
    expect(() => plan.reset()).not.toThrow();
    meshes.forEach((m, k) => {
      const ix = Array.from(m.geometry.index!.array);
      // Untouched, or carved whole.
      if (carvedOf(m)) expect(ix).toEqual(want[k].kept);
      else expect(ix).toEqual(before[k]);
    });
    expect(carvedOf(meshes[1])).toBeUndefined();
  });

  it("does the other areas' work too (glows only at the mission)", async () => {
    const mat = new MeshBasicMaterial();
    mat.color.setRGB(2, 1.5, 1);
    const roles = new Map(Array.from({ length: 7 }, (_, i) => [`role:${i}`, [new Mesh(new BoxGeometry(), mat.clone())]] as [string, Mesh[]]));
    const plan = await planIdleSliced("mission", new Group(), roles, new Map(), { pause: async () => {} });
    expect(plan.glows).toHaveLength(7);
    expect(plan.rigid).toEqual([]);
    expect(plan.sway).toBe(0);
  });
});
