/// <reference lib="webworker" />
/**
 * Builds a picking BVH (three-mesh-bvh) off the main thread, for bvh-build.ts.
 *
 * The page sends a copy of a mesh's raw position storage (as the file stored it: often 16-bit
 * normalised integers from meshopt quantisation, sometimes interleaved) and of its index. The
 * positions are read into plain floats exactly as three's getX reads them (lib/sect/background-work.ts
 * bvhPositions). The tree is built as on the main thread (bvh-job.ts buildBvhJob), which reorders the
 * index within its groups, and goes back with the reordered index, every buffer transferred rather
 * than copied.
 */
import type { RawPositions } from "@/lib/sect/background-work";
import { buildBvhJob } from "./bvh-job";

export interface BvhJob extends RawPositions {
  id: number;
  index: Uint16Array | Uint32Array | null;
  groups: { start: number; count: number; materialIndex?: number }[];
}

export type BvhReply =
  | { ready: true }
  | { id: number; roots: ArrayBuffer[]; index: Uint16Array | Uint32Array | null; error?: undefined }
  | { id: number; error: string };

const scope = globalThis as unknown as DedicatedWorkerGlobalScope;

scope.onmessage = (e: MessageEvent<BvhJob>) => {
  const job = e.data;
  try {
    const { roots, index } = buildBvhJob(job);
    const transfer: Transferable[] = [...roots];
    if (index) transfer.push(index.buffer as ArrayBuffer);
    scope.postMessage({ id: job.id, roots, index } satisfies BvhReply, transfer);
  } catch (err) {
    scope.postMessage({ id: job.id, error: String((err as Error)?.message ?? err) } satisfies BvhReply);
  }
};

scope.postMessage({ ready: true } satisfies BvhReply);
