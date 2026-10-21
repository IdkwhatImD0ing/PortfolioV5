import { describe, expect, it } from "vitest";
import {
  Box3,
  BufferAttribute,
  BufferGeometry,
  InterleavedBuffer,
  InterleavedBufferAttribute,
  Mesh,
  MeshBasicMaterial,
  Raycaster,
  SphereGeometry,
  Vector3,
} from "three";
import { acceleratedRaycast, MeshBVH } from "three-mesh-bvh";
import { applyBvh, bvhJob } from "./bvh-build";
import { buildBvhJob } from "./bvh-job";

/**
 * A sphere stored as meshopt stores it: positions as normalised 16-bit integers, interleaved with
 * another attribute, read back at their real size through the mesh's scale.
 */
function quantised(): Mesh {
  const src = new SphereGeometry(1, 48, 32);
  const p = src.getAttribute("position");
  const stride = 4;
  const data = new Int16Array(p.count * stride);
  for (let i = 0; i < p.count; i++) {
    data[i * stride] = Math.round(p.getX(i) * 32767);
    data[i * stride + 1] = Math.round(p.getY(i) * 32767);
    data[i * stride + 2] = Math.round(p.getZ(i) * 32767);
    data[i * stride + 3] = 7;
  }
  const g = new BufferGeometry();
  g.setAttribute("position", new InterleavedBufferAttribute(new InterleavedBuffer(data, stride), 3, 0, true));
  g.setIndex(new BufferAttribute(src.index!.array.slice(), 1));
  g.addGroup(0, src.index!.count, 0);
  const m = new Mesh(g, new MeshBasicMaterial());
  m.scale.setScalar(20);
  m.updateMatrixWorld(true);
  return m;
}

/** First hits of a fan of rays at the mesh, in order (null for a miss). */
function hits(m: Mesh): (number | null)[] {
  const ray = new Raycaster();
  ray.firstHitOnly = true;
  const out: (number | null)[] = [];
  for (let i = 0; i < 40; i++) {
    const a = (i / 40) * Math.PI * 2;
    const origin = new Vector3(Math.cos(a) * 60, ((i % 7) - 3) * 4, Math.sin(a) * 60);
    ray.set(origin, origin.clone().multiplyScalar(-1).add(new Vector3(0, (i % 5) - 2, 0)).normalize());
    const h = ray.intersectObject(m, false);
    out.push(h.length ? Math.round(h[0].distance * 1000) / 1000 : null);
  }
  return out;
}

describe("BVHs built off the main thread", () => {
  it("pick what a main-thread build picks, from quantised interleaved positions", () => {
    const main = quantised();
    (main.geometry as BufferGeometry & { boundsTree?: MeshBVH }).boundsTree = new MeshBVH(main.geometry);
    main.raycast = acceleratedRaycast;

    const off = quantised();
    const payload = bvhJob(off.geometry, 1)!;
    expect(payload).not.toBeNull();
    // What the worker gets back to the page (bvh.worker.ts).
    const built = buildBvhJob(payload.job);
    expect(applyBvh(off.geometry, built.roots, built.index)).toBe(true);
    off.raycast = acceleratedRaycast;

    const want = hits(main);
    expect(want.filter((d) => d !== null).length).toBeGreaterThan(20);
    expect(hits(off)).toEqual(want);
    // The tree's bounds are the mesh's real (denormalised) size, not 32767 times it.
    const box = (off.geometry as BufferGeometry & { boundsTree?: MeshBVH }).boundsTree!.getBoundingBox(new Box3());
    expect(Math.abs(box.max.x - 1)).toBeLessThan(0.01);
  });

  it("copies the arrays out: the geometry keeps its own (the worker gets transferable copies)", () => {
    const m = quantised();
    const pos = (m.geometry.getAttribute("position") as InterleavedBufferAttribute).data.array;
    const index = m.geometry.index!.array;
    const payload = bvhJob(m.geometry, 2)!;
    expect(payload.job.position).not.toBe(pos);
    expect(payload.job.index).not.toBe(index);
    expect(payload.transfer).toHaveLength(2);
    expect(payload.job.normalized).toBe(true);
    expect(payload.job.stride).toBe(4);
  });

  it("attaches nothing when the geometry changed meanwhile", () => {
    const m = quantised();
    const built = buildBvhJob(bvhJob(m.geometry, 3)!.job);
    m.geometry.setIndex(new BufferAttribute(new Uint32Array(m.geometry.index!.count - 3), 1));
    expect(applyBvh(m.geometry, built.roots, built.index)).toBe(false);
    expect((m.geometry as BufferGeometry & { boundsTree?: MeshBVH }).boundsTree).toBeUndefined();
  });
});
