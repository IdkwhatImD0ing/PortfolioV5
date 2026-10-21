/**
 * The BVH worker's work (bvh.worker.ts), kept apart from the worker's messaging so tests can run it
 * (bvh-build.test.ts) and from bvh-build.ts, which starts the worker (the worker's bundle must not
 * start another).
 */
import { BufferAttribute, BufferGeometry } from "three";
import { MeshBVH } from "three-mesh-bvh";
import { bvhPositions } from "@/lib/sect/background-work";
import type { BvhJob } from "./bvh.worker";

/**
 * The tree over a job's triangles, built as `new MeshBVH(g)` builds it on the main thread, and the
 * index it reordered (null for a non-indexed geometry).
 */
export function buildBvhJob(job: BvhJob): { roots: ArrayBuffer[]; index: Uint16Array | Uint32Array | null } {
  const g = new BufferGeometry();
  g.setAttribute("position", new BufferAttribute(bvhPositions(job), 3));
  if (job.index) g.setIndex(new BufferAttribute(job.index, 1));
  for (const gr of job.groups) g.addGroup(gr.start, gr.count, gr.materialIndex);
  const bvh = new MeshBVH(g, { setBoundingBox: false });
  const s = MeshBVH.serialize(bvh, { cloneBuffers: false });
  return { roots: s.roots, index: (s.index as Uint16Array | Uint32Array | null) ?? null };
}
