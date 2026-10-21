/**
 * Picking BVHs built off the main thread (bvh.worker.ts). Built on the main thread, one froze a
 * 4x-slowed phone at rest for 160-360 ms per hotspot mesh, and a desktop for tens of ms. Here the
 * main thread only copies the mesh's position and index arrays out (a memcpy) and takes the tree
 * back (a few views over transferred buffers), so the camera can rest without a hitch while they
 * build.
 *
 * The worker reads the positions as three does (16-bit normalised meshopt data included), builds
 * the tree exactly as `new MeshBVH(geometry)` would (it reorders the index within its groups) and
 * returns the reordered index. That goes into the geometry's own index array without a GPU upload,
 * as the main-thread build does in place: the same triangles in another order draw the same picture.
 *
 * One worker, one job at a time, stopped after a while with nothing to do. Where workers cannot run
 * (or the worker never says it started) the caller falls back to the main-thread build
 * (prepare.ts ensureBvh, in idle time: lib/sect/background-work.ts mayBuildBvh).
 */
import { Box3, BufferAttribute, type BufferGeometry, type InterleavedBufferAttribute, type Mesh } from "three";
import { acceleratedRaycast, MeshBVH } from "three-mesh-bvh";
import type { BvhJob, BvhReply } from "./bvh.worker";

/** The worker must say it is up within this long, or BVHs are built on the main thread from then on. */
const START_MS = 10_000;
/** The worker stops after this long with nothing to do (it holds three and three-mesh-bvh). */
const IDLE_MS = 30_000;

interface BvhWorker {
  worker: Worker;
  started: Promise<boolean>;
  jobs: Map<number, (r: BvhReply) => void>;
  next: number;
  idle: ReturnType<typeof setTimeout> | undefined;
}

let current: BvhWorker | null = null;
/** No worker here, or it failed: the main thread builds from now on. */
let blocked = false;
/** Counts for the debug HUD and inspection scripts (window.__sect.bvh). */
export const bvhStats = { worker: 0, failed: 0, copyMs: 0, applyMs: 0, mode: "unknown" as "unknown" | "worker" | "main" };

function stop(w: BvhWorker, why: string): void {
  if (current === w) current = null;
  clearTimeout(w.idle);
  w.worker.terminate();
  for (const done of w.jobs.values()) done({ id: -1, error: why });
  w.jobs.clear();
}

function start(): BvhWorker | null {
  if (current) return current;
  if (blocked || typeof Worker === "undefined") return null;
  let worker: Worker;
  try {
    worker = new Worker(new URL("./bvh.worker.ts", import.meta.url), { type: "module", name: "sect-bvh" });
  } catch (e) {
    console.warn("[sect] BVH worker unavailable; building picking trees on the main thread", e);
    blocked = true;
    bvhStats.mode = "main";
    return null;
  }
  let said: (ok: boolean) => void = () => {};
  const w: BvhWorker = {
    worker,
    started: new Promise<boolean>((resolve) => {
      said = resolve;
      setTimeout(() => resolve(false), START_MS);
    }),
    jobs: new Map(),
    next: 1,
    idle: undefined,
  };
  worker.onmessage = (e: MessageEvent<BvhReply>) => {
    const d = e.data;
    if ("ready" in d) {
      bvhStats.mode = "worker";
      return said(true);
    }
    const done = w.jobs.get(d.id);
    if (!done) return;
    w.jobs.delete(d.id);
    done(d);
    if (w.jobs.size === 0) {
      clearTimeout(w.idle);
      w.idle = setTimeout(() => {
        if (current === w && w.jobs.size === 0) stop(w, "idle");
      }, IDLE_MS);
    }
  };
  worker.onerror = (e) => {
    e.preventDefault();
    said(false);
    stop(w, "the BVH worker failed");
  };
  current = w;
  return w;
}

function rawLayout(a: BufferAttribute | InterleavedBufferAttribute): { array: BvhJob["position"]; stride: number; offset: number } {
  const i = a as InterleavedBufferAttribute;
  if (i.isInterleavedBufferAttribute) return { array: i.data.array as BvhJob["position"], stride: i.data.stride, offset: i.offset };
  return { array: a.array as BvhJob["position"], stride: a.itemSize, offset: 0 };
}

/** What the worker needs for a geometry (copies: the geometry keeps its own arrays), or null if it cannot take it. */
export function bvhJob(g: BufferGeometry, id: number): { job: BvhJob; transfer: Transferable[] } | null {
  const pos = g.getAttribute("position") as BufferAttribute | InterleavedBufferAttribute | undefined;
  if (!pos || pos.itemSize < 3 || pos.count === 0) return null;
  const index = g.index;
  if (index && (index as unknown as InterleavedBufferAttribute).isInterleavedBufferAttribute) return null;
  const raw = rawLayout(pos);
  // An interleaved buffer is copied whole (its other attributes ride along; the worker reads only xyz).
  const position = raw.array.slice() as BvhJob["position"];
  const idx = index ? ((index.array as Uint16Array | Uint32Array).slice() as Uint16Array | Uint32Array) : null;
  const job: BvhJob = {
    id,
    position,
    count: pos.count,
    stride: raw.stride,
    offset: raw.offset,
    normalized: pos.normalized,
    index: idx,
    groups: g.groups.map((gr) => ({ start: gr.start, count: gr.count, materialIndex: gr.materialIndex })),
  };
  const transfer: Transferable[] = [position.buffer as ArrayBuffer];
  if (idx) transfer.push(idx.buffer as ArrayBuffer);
  return { job, transfer };
}

/**
 * Puts a tree the worker built on the geometry, as `new MeshBVH(g)` would leave it. False when the
 * geometry changed meanwhile (its index no longer matches), so nothing is attached.
 */
export function applyBvh(g: BufferGeometry & { boundsTree?: MeshBVH }, roots: ArrayBuffer[], index: Uint16Array | Uint32Array | null): boolean {
  if (g.boundsTree) return true;
  if (index) {
    const own = g.index;
    if (own) {
      if (own.array.length !== index.length) return false;
      // The same triangles in the worker's order (the GPU copy keeps the old order, as with an
      // in-place build: both draw the same picture).
      (own.array as Uint16Array | Uint32Array).set(index);
    } else {
      // A non-indexed geometry gets the index the build made for it (as ensureIndex does).
      g.setIndex(new BufferAttribute(index, 1));
    }
  }
  // The build always leaves an index (it makes one for a non-indexed geometry); none means a bad reply.
  if (!index) return false;
  const bvh = MeshBVH.deserialize({ roots, index }, g, { setIndex: false });
  if (!g.boundingBox) g.boundingBox = bvh.getBoundingBox(new Box3());
  g.boundsTree = bvh;
  return true;
}

/**
 * Builds the mesh's BVH in the worker. "built": it has one now (and fast raycasts); "unavailable":
 * no worker here (build it on the main thread instead); "failed": the worker could not build this
 * one, or the geometry changed meanwhile (leave it to its box).
 */
export async function buildBvhOffThread(mesh: Mesh): Promise<"built" | "unavailable" | "failed"> {
  const g = mesh.geometry as BufferGeometry & { boundsTree?: MeshBVH };
  if (g.boundsTree) {
    mesh.raycast = acceleratedRaycast;
    return "built";
  }
  const w = start();
  if (!w) return "unavailable";
  if (!(await w.started)) {
    if (current === w) {
      console.warn("[sect] the BVH worker did not start; building picking trees on the main thread");
      stop(w, "not started");
    }
    blocked = true;
    bvhStats.mode = "main";
    return "unavailable";
  }
  if (current !== w) return blocked ? "unavailable" : "failed";
  const id = w.next++;
  const t0 = performance.now();
  const payload = bvhJob(g, id);
  if (!payload) return "failed";
  const reply = await new Promise<BvhReply>((resolve) => {
    clearTimeout(w.idle);
    w.jobs.set(id, resolve);
    w.worker.postMessage(payload.job, payload.transfer);
    bvhStats.copyMs += performance.now() - t0;
  });
  if ("ready" in reply || reply.error !== undefined) {
    bvhStats.failed++;
    if (!("ready" in reply) && reply.id !== -1) console.warn("[sect] BVH worker:", reply.error);
    return blocked || current === null ? "unavailable" : "failed";
  }
  const t1 = performance.now();
  const ok = applyBvh(g, reply.roots, reply.index);
  bvhStats.applyMs += performance.now() - t1;
  if (!ok) {
    bvhStats.failed++;
    return "failed";
  }
  mesh.raycast = acceleratedRaycast;
  bvhStats.worker++;
  return "built";
}
