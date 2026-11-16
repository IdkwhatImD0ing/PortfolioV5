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
 *
 * Each set's trunks (one ribbon a tree under its crowns, lib/sect/veg.ts plantTrunk) are a second
 * instanced draw made, compiled, shown and freed with its shells: no crowns, no trunks.
 */
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import { Group, HalfFloatType, type Mesh, type ShaderMaterial, Vector2, Vector4, WebGLRenderTarget } from "three";
import { CARD_LOOK } from "@/lib/sect/card-shading";
import { fetchUrl } from "@/lib/sect/parse";
import type { Quality } from "@/lib/sect/runtime";
import type { Vec3 } from "@/lib/sect/types";
import { parseVeg, parseVegIndex, parseVegParam, shellInstances, vegBoughUniform, vegChunkId, vegShellsOn, type ShellInstances, type VegIndex } from "@/lib/sect/veg";
import type { LoadedSet, WorldContext } from "./assets";
import { wake, type SectStore } from "./store";
import {
  createShellMesh,
  createTrunkMesh,
  createVegMaterial,
  createVegTrunkMaterial,
  disposeShellMesh,
  farCardMeshes,
  setCardFarCut,
  TRUNK_TRIANGLES,
  vegShell,
  type VegUniforms,
} from "./veg-mesh";

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
      /** Trunks under the crowns (every crown plant but shrubs), and their triangles. */
      trunks: number;
      trunkTriangles: number;
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
  /** The trunks under its crowns (null: none, or no crowns). */
  trunks: Mesh | null;
  hidden: Mesh[];
}

/** Takes a set's shells and trunks away (freed) and, unless the set is going too, shows its cards again. */
function unbuild(b: Built): void {
  if (b.mesh) disposeShellMesh(b.mesh);
  if (b.trunks) disposeShellMesh(b.trunks);
  if (!b.set.dropped) setCardFarCut(b.hidden, 0, 0);
  b.mesh = null;
  b.trunks = null;
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
        // The drawing buffer's height, set every frame below: the trunks' least width on screen.
        uVegViewH: { value: 1000 },
      } as VegUniforms,
      built: new Map<LoadedSet, Built>(),
      pending: new Set<LoadedSet>(),
      /** The shell program, and the trunk program, have been compiled ahead of their first draw. */
      warmed: false,
      trunksWarmed: false,
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
      kit.trunksWarmed = false;
    };
  }, [kit]);

  // A pixel's size in metres for the trunks' ribbons (as Grass and the birds read it).
  useFrame((state) => {
    if (live.current.on) kit.uniforms.uVegViewH.value = state.size.height * state.viewport.dpr;
  });

  // Build the shells of each set that has none, and take them off sets that went (or all, when off).
  useEffect(() => {
    kit.stats.on = on;
    for (const [s, b] of kit.built) {
      if (on && sets.includes(s) && !s.dropped) continue;
      unbuild(b);
      kit.built.delete(s);
      delete kit.stats.chunks[vegChunkId(s.id)];
    }
    if (!on) {
      // The last shell and trunk materials are gone, and three frees a program no material uses: when the
      // ladder brings the shells back, their programs are compiled off the frame again, not on the first draw.
      kit.warmed = false;
      kit.trunksWarmed = false;
      return;
    }
    const alive = (s: LoadedSet) => mounted.current && live.current.on && !s.dropped && live.current.sets.includes(s);
    /** Compiles the meshes' programs (shells, trunks: both in one go) for the buffer they are drawn into, off the frame (as Grass does). */
    const warm = async (meshes: readonly Mesh[]) => {
      const holder = new Group();
      for (const m of meshes) holder.add(m);
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
        for (const m of meshes) holder.remove(m);
      }
    };
    const build = async (set: LoadedSet) => {
      const id = vegChunkId(set.id);
      const got = await loadShells(ctx.data.base, ctx.data.manifest.rev, id, [ctx.sunDir.x, ctx.sunDir.y, ctx.sunDir.z]);
      if (!alive(set)) return;
      const inst = got.inst;
      const root = set.scenes[0];
      if (!inst || inst.count === 0 || !root) {
        kit.stats.chunks[id] = {
          status: got.status,
          plants: 0,
          cards: inst?.cards ?? 0,
          instances: 0,
          triangles: 0,
          trunks: 0,
          trunkTriangles: 0,
          hidden: 0,
          skipped: inst?.skipped ?? null,
        };
        kit.built.set(set, { set, mesh: null, trunks: null, hidden: [] });
        return;
      }
      const material = createVegMaterial(kit.uniforms, `sect.veg.${id}`, live.current.coverage);
      const mesh = createShellMesh(inst, material);
      const trunks = inst.trunks.count > 0 ? createTrunkMesh(inst.trunks, createVegTrunkMaterial(kit.uniforms, `sect.veg.${id}.trunks`, live.current.coverage)) : null;
      const made = trunks ? [mesh, trunks] : [mesh];
      // The programs not compiled yet, both in one go.
      const cold = made.filter((m) => (m === mesh ? !kit.warmed : !kit.trunksWarmed));
      if (cold.length > 0) {
        await warm(cold);
        if (!alive(set)) {
          for (const m of made) disposeShellMesh(m);
          return;
        }
        // Set only when these stay: ones thrown away may have taken the warmed programs with them.
        for (const m of cold) {
          if (m === mesh) kit.warmed = true;
          else kit.trunksWarmed = true;
        }
      }
      // MSAA may have changed while they compiled.
      for (const m of made) {
        const mat = m.material as ShaderMaterial;
        if (mat.alphaToCoverage !== live.current.coverage) {
          mat.alphaToCoverage = live.current.coverage;
          mat.needsUpdate = true;
        }
      }
      for (const m of made) {
        root.add(m);
        m.updateMatrixWorld(true);
      }
      const hidden = farCardMeshes(set.scenes, set.hotspotMeshes);
      setCardFarCut(hidden, CARD_LOOK.farCut.from, CARD_LOOK.farCut.to);
      kit.built.set(set, { set, mesh, trunks, hidden });
      kit.stats.chunks[id] = {
        status: got.status,
        plants: inst.plants,
        cards: inst.cards,
        instances: inst.count,
        triangles: inst.count * vegShell().triangles,
        trunks: trunks ? inst.trunks.count : 0,
        trunkTriangles: trunks ? inst.trunks.count * TRUNK_TRIANGLES : 0,
        hidden: hidden.length,
        skipped: inst.skipped,
      };
      // On screen, near or as far scenery (LoadedSet.far): the shells show on the next frame.
      if (set.drawn || set.far) wake(store, 200);
    };
    for (const s of sets) {
      if (s.dropped || kit.built.has(s) || kit.pending.has(s)) continue;
      kit.pending.add(s);
      build(s)
        .catch((e: unknown) => {
          console.warn(`[sect] crown shells for ${s.id} failed; its baked cards stay`, e);
          if (alive(s) && !kit.built.has(s)) kit.built.set(s, { set: s, mesh: null, trunks: null, hidden: [] });
        })
        .finally(() => kit.pending.delete(s));
    }
  }, [sets, on, kit, ctx, store, gl, scene, camera]);

  // Alpha to coverage follows MSAA (the ladder can take it off and give it back), on the shells and the trunks.
  useEffect(() => {
    for (const b of kit.built.values()) {
      for (const mesh of [b.mesh, b.trunks]) {
        const m = mesh?.material as ShaderMaterial | undefined;
        if (!m || m.alphaToCoverage === coverage) continue;
        m.alphaToCoverage = coverage;
        m.needsUpdate = true;
      }
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
