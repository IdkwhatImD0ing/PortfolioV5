"use client";

/**
 * Far trees as lit crown shells (lib/sect/veg.ts) in place of the baked cards: on the High tier, or
 * on any tier with ?veg=1 (?veg=0 keeps the cards). Near trees (trees.mesh / trees.needle) stay as
 * baked.
 *
 * Per loaded set, public/sect/full/veg/<chunk>.veg (the global set's is backdrop.veg) is fetched once
 * and turned into one instanced draw, which goes under the set's own root: it is shown and hidden
 * with the set (the stand-in step and reflections included) and freed with it. Once it is there,
 * the set's far-tree card meshes are hidden (not freed: they are the fallback, and come back when
 * the shells go). A missing or unreadable file, or one with no card plant, leaves the cards exactly
 * as they were. The backdrop's per-area stand-ins (extras.proxyOf) are left alone: the World
 * component shows them while their area is not drawn, as cards.
 */
import { useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import { Group, HalfFloatType, type Mesh, type ShaderMaterial, Vector2, Vector4, WebGLRenderTarget } from "three";
import { CARD_LOOK } from "@/lib/sect/card-shading";
import { fetchUrl } from "@/lib/sect/parse";
import type { Quality } from "@/lib/sect/runtime";
import type { Vec3 } from "@/lib/sect/types";
import { parseVeg, parseVegIndex, parseVegParam, shellInstances, vegBoughUniform, vegChunkId, vegShellsOn, type ShellInstances, type VegIndex } from "@/lib/sect/veg";
import type { LoadedSet, WorldContext } from "./assets";
import { wake, type SectStore } from "./store";
import { createShellMesh, createVegMaterial, disposeShellMesh, farCardMeshes, setCardFarCut, vegShell, type VegUniforms } from "./veg-mesh";

/** What the shells did per chunk (window.__sectVeg with ?debug=1). */
export interface VegStats {
  on: boolean;
  chunks: Record<
    string,
    {
      /** "shells", or why the cards stay: "no file", "no card plants", "HTTP 404", an error. */
      status: string;
      plants: number;
      cards: number;
      instances: number;
      triangles: number;
      /** Card meshes hidden in its place. */
      hidden: number;
      skipped: ShellInstances["skipped"] | null;
    }
  >;
}

interface Loaded {
  inst: ShellInstances | null;
  status: string;
}

/** index.json per asset folder, fetched once (null: none or unreadable). */
const indexes = new Map<string, Promise<VegIndex | null>>();
/** Each chunk's shell instances, built once per page. */
const loaded = new Map<string, Promise<Loaded>>();

function fetchOpts(file: string, rev?: Readonly<Record<string, string>>): RequestInit | undefined {
  // A file with a fingerprint may come from the browser's cache as is; the rest are checked each time.
  return rev?.[file] ? undefined : { cache: "no-cache" };
}

function loadIndex(base: string, rev?: Readonly<Record<string, string>>): Promise<VegIndex | null> {
  let p = indexes.get(base);
  if (!p) {
    const file = "veg/index.json";
    p = fetch(fetchUrl(base, file, rev), fetchOpts(file, rev))
      .then(async (res) => (res.ok ? parseVegIndex(await res.json()) : null))
      .catch(() => null);
    indexes.set(base, p);
  }
  return p;
}

/** `sun`: the direction toward the scene's sun, for each crown's depth among the others (vegDepth). */
function loadShells(base: string, rev: Readonly<Record<string, string>> | undefined, chunk: string, sun: Vec3): Promise<Loaded> {
  const key = `${base}|${chunk}`;
  let p = loaded.get(key);
  if (!p) {
    p = (async (): Promise<Loaded> => {
      const index = await loadIndex(base, rev);
      const entry = index?.chunks[chunk];
      if (!index || !entry) return { inst: null, status: "no file" };
      if (entry.cards === 0) return { inst: null, status: "no card plants" };
      const file = `veg/${entry.file}`;
      const res = await fetch(fetchUrl(base, file, rev), fetchOpts(file, rev));
      if (!res.ok) return { inst: null, status: `HTTP ${res.status}` };
      const inst = shellInstances(parseVeg(await res.arrayBuffer()), index.families, { sun });
      return { inst, status: inst.count > 0 ? "shells" : "no card plants" };
    })().catch((e: unknown) => ({ inst: null, status: e instanceof Error ? e.message : String(e) }));
    loaded.set(key, p);
  }
  return p;
}

interface Built {
  set: LoadedSet;
  mesh: Mesh | null;
  hidden: Mesh[];
}

/** Takes a set's shells away (freed) and, unless the set is going too, shows its cards again. */
function unbuild(b: Built): void {
  if (b.mesh) disposeShellMesh(b.mesh);
  if (!b.set.dropped) setCardFarCut(b.hidden, 0, 0);
  b.mesh = null;
  b.hidden = [];
}

export interface VegShellsProps {
  global: LoadedSet | null;
  chunks: LoadedSet[];
  ctx: WorldContext;
  store: SectStore;
  quality: Quality;
}

export function VegShells({ global, chunks, ctx, store, quality }: VegShellsProps) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const sw = useMemo(() => parseVegParam(typeof window === "undefined" ? "" : window.location.search), []);
  const on = vegShellsOn(quality, sw);
  const coverage = quality.msaa > 0;
  const sets = useMemo(() => (global ? [global, ...chunks] : chunks), [global, chunks]);

  const kit = useMemo(
    () => ({
      uniforms: {
        uVegSun: { value: ctx.sunDir },
        uVegNear: { value: new Vector2(CARD_LOOK.farCut.from, CARD_LOOK.farCut.to) },
        // One object for every chunk's material, so a change shows on all of them (window.__sectVegBough with ?debug=1).
        uVegBough: { value: new Vector4(...vegBoughUniform()) },
      } as VegUniforms,
      built: new Map<LoadedSet, Built>(),
      pending: new Set<LoadedSet>(),
      /** The shell program has been compiled ahead of its first draw. */
      warmed: false,
      warmTarget: null as WebGLRenderTarget | null,
      stats: { on: false, chunks: {} } as VegStats,
    }),
    [ctx],
  );

  const mounted = useRef(false);
  const live = useRef({ sets, on, coverage, post: quality.post });
  live.current = { sets, on, coverage, post: quality.post };

  // Everything goes with the canvas; the cards of sets still loaded come back.
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      for (const b of kit.built.values()) unbuild(b);
      kit.built.clear();
      kit.stats.chunks = {};
      kit.warmTarget?.dispose();
      kit.warmTarget = null;
      kit.warmed = false;
    };
  }, [kit]);

  // Build the shells of each set that has none, and take them off sets that went (or all, when off).
  useEffect(() => {
    kit.stats.on = on;
    for (const [s, b] of kit.built) {
      if (on && sets.includes(s) && !s.dropped) continue;
      unbuild(b);
      kit.built.delete(s);
      delete kit.stats.chunks[vegChunkId(s.id)];
    }
    if (!on) return;
    const alive = (s: LoadedSet) => mounted.current && live.current.on && !s.dropped && live.current.sets.includes(s);
    /** Compiles the shell program for the buffer it is drawn into, off the frame (as Grass does). */
    const warm = async (mesh: Mesh) => {
      const holder = new Group();
      holder.add(mesh);
      try {
        const prev = gl.getRenderTarget();
        let pending: Promise<unknown>;
        try {
          if (live.current.post) {
            kit.warmTarget ??= new WebGLRenderTarget(1, 1, { type: HalfFloatType, depthBuffer: false });
            gl.setRenderTarget(kit.warmTarget);
          }
          pending = gl.compileAsync(holder, camera, scene);
        } finally {
          gl.setRenderTarget(prev);
        }
        await pending;
      } catch (e) {
        console.warn("[sect] crown shell shader warm-up failed", e);
      } finally {
        holder.remove(mesh);
      }
    };
    const build = async (set: LoadedSet) => {
      const id = vegChunkId(set.id);
      const got = await loadShells(ctx.data.base, ctx.data.manifest.rev, id, [ctx.sunDir.x, ctx.sunDir.y, ctx.sunDir.z]);
      if (!alive(set)) return;
      const inst = got.inst;
      const root = set.scenes[0];
      if (!inst || inst.count === 0 || !root) {
        kit.stats.chunks[id] = { status: got.status, plants: 0, cards: inst?.cards ?? 0, instances: 0, triangles: 0, hidden: 0, skipped: inst?.skipped ?? null };
        kit.built.set(set, { set, mesh: null, hidden: [] });
        return;
      }
      const material = createVegMaterial(kit.uniforms, `sect.veg.${id}`, live.current.coverage);
      const mesh = createShellMesh(inst, material);
      if (!kit.warmed) {
        await warm(mesh);
        kit.warmed = true;
        if (!alive(set)) {
          disposeShellMesh(mesh);
          return;
        }
      }
      // MSAA may have changed while it compiled.
      const shellMaterial = mesh.material as ShaderMaterial;
      if (shellMaterial.alphaToCoverage !== live.current.coverage) {
        shellMaterial.alphaToCoverage = live.current.coverage;
        shellMaterial.needsUpdate = true;
      }
      root.add(mesh);
      mesh.updateMatrixWorld(true);
      const hidden = farCardMeshes(set.scenes, set.hotspotMeshes);
      setCardFarCut(hidden, CARD_LOOK.farCut.from, CARD_LOOK.farCut.to);
      kit.built.set(set, { set, mesh, hidden });
      kit.stats.chunks[id] = {
        status: got.status,
        plants: inst.plants,
        cards: inst.cards,
        instances: inst.count,
        triangles: inst.count * vegShell().triangles,
        hidden: hidden.length,
        skipped: inst.skipped,
      };
      if (set.drawn) wake(store, 200);
    };
    for (const s of sets) {
      if (s.dropped || kit.built.has(s) || kit.pending.has(s)) continue;
      kit.pending.add(s);
      build(s)
        .catch((e: unknown) => {
          console.warn(`[sect] crown shells for ${s.id} failed; its baked cards stay`, e);
          if (alive(s) && !kit.built.has(s)) kit.built.set(s, { set: s, mesh: null, hidden: [] });
        })
        .finally(() => kit.pending.delete(s));
    }
  }, [sets, on, kit, ctx, store, gl, scene, camera]);

  // Alpha to coverage follows MSAA (the ladder can take it off and give it back).
  useEffect(() => {
    for (const b of kit.built.values()) {
      const m = b.mesh?.material as ShaderMaterial | undefined;
      if (!m || m.alphaToCoverage === coverage) continue;
      m.alphaToCoverage = coverage;
      m.needsUpdate = true;
    }
  }, [coverage, kit]);

  // Exposed for inspection scripts in debug mode only. __sectVegBough is the boughs' shared uniform, to tune from
  // the console: x the slope lean, y the deepest crease's brightness, z the share kept large on screen. It shows
  // on the next drawn frame.
  useEffect(() => {
    if (!/[?&]debug=1/.test(window.location.search)) return;
    const w = window as unknown as { __sectVeg?: VegStats; __sectVegBough?: Vector4 };
    const bough = kit.uniforms.uVegBough.value;
    w.__sectVeg = kit.stats;
    w.__sectVegBough = bough;
    return () => {
      if (w.__sectVeg === kit.stats) delete w.__sectVeg;
      if (w.__sectVegBough === bough) delete w.__sectVegBough;
    };
  }, [kit]);

  return null;
}
