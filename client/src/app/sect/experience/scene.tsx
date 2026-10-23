"use client";

/**
 * Everything inside the R3F <Canvas>: camera rig (scroll damping and programmatic flights),
 * atmosphere, the global set and the streamed chunks (drawn by frame, with their backdrop proxies
 * hidden while they are), decoration, grass tufts on the areas' lawns, hotspot picking, the
 * optional flyer, postprocessing, the render driver (every display frame while moving, on demand
 * otherwise, with the quality ladder) and the debug probe.
 */
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  CircleGeometry,
  Color,
  DirectionalLight,
  DynamicDrawUsage,
  FogExp2,
  Group,
  HalfFloatType,
  HemisphereLight,
  InstancedBufferGeometry,
  InstancedInterleavedBuffer,
  InterleavedBufferAttribute,
  LessEqualDepth,
  Mesh,
  type Object3D,
  PerspectiveCamera,
  PlaneGeometry,
  PMREMGenerator,
  Raycaster,
  Scene,
  type ShaderMaterial,
  Sphere,
  SphereGeometry,
  Vector2,
  Vector3,
  WebGLRenderTarget,
} from "three";
import { BVH_MS_PER_KTRI, bvhCostMs, bvhWanted, deferUpload, mayBuildBvh, mayPostBvh, updateBvhRate, uploadWaitedMs } from "@/lib/sect/background-work";
import { fovForAspect, samplePath, sampleCamera } from "@/lib/sect/camera-path";
import { framingAt, framingFrame } from "@/lib/sect/framing";
import {
  clampLook,
  composeLook,
  followPath,
  isDragging,
  isTurned,
  isTurning,
  lookCursor,
  lookLimits,
  pressCancel,
  pressDown,
  pressMove,
  pressUp,
  radiansPerPixel,
  releaseTurnKeys,
  setTurnKey,
  takeClick,
  turnByKeys,
} from "@/lib/sect/free-look";
import { packPuffs, PUFF_STRIDE, RESORT_DISTANCE2, sortFarToNear } from "@/lib/sect/clouds";
import { lookFogConstants, puffDensityScale, SECT_LOOK, twilightAmount } from "@/lib/sect/look";
import { isLoreId, loreUnderPointer, type LoreHit, type LoreId } from "@/lib/sect/lore";
import { turnKeyIntent } from "@/lib/sect/nav";
import { boxHits, canStandIn, containedItemAt, onScreenDepth, pickWithBoxes, type BoxHit, type PickBox } from "@/lib/sect/pick";
import {
  AUTO_FRAME_BUDGET_MS,
  capIsMoot,
  climbCost,
  climbRebuildsPipeline,
  damp,
  effectiveDpr,
  FrameLadder,
  type LadderStatus,
  type Quality,
} from "@/lib/sect/runtime";
import { ATMOS, atmosFeatures, holdAt, holdFocusStep, nearestHold } from "@/lib/sect/post";
import { easeInOut, nearestStop, uToFrame } from "@/lib/sect/scroll-map";
import type { CloudPuff, FlyerPath, SectMeta, Vec3 } from "@/lib/sect/types";
import { fxTier } from "@/lib/sect/water";
import { fallPickQuads, rayQuad } from "@/lib/sect/waterfall";
import { drawable, setCardCoverage, setOverlayTier, type LoadedSet, type WorldContext } from "./assets";
import { createPipeline, type Pipeline } from "./effects";
import { SectReflections } from "./reflect";
import { reflectTier } from "./reflect/plan";
import { SpanTimer } from "./reflect/timer";
import { Cranes, ForgeFire, FormationFires, IncenseSmoke, Petals } from "./fx";
import { createGrassDebug, Grass, type GrassDebug } from "./grass";
import { IDLE_ON, IDLE_TIME, updateIdle } from "./idle";
import { Life } from "./life";
import { breathe } from "@/lib/sect/idle";
import {
  aimPondMirror,
  createCloudPuffMaterial,
  createCloudSeaMaterial,
  createGlowMaterial,
  createMoonMaterial,
  createSkyMaterial,
  SOFT_DEPTH,
} from "./materials";
import { bvhStats, buildBvhOffThread } from "./bvh-build";
import { ensureBvh, hasBvh, imageClosed, triangleCount } from "./prepare";
import { cameraStill, framesToGo, isMoving, recenterView, wake, wakeForRecenter, type SectStore } from "./store";
import type { ChunkStreamer } from "./streaming";
import { WaterfallFx } from "./waterfall-fx";

/** Hotspot id of the moon over the summit (drawn by the engine, not a GLB node). */
export const MOON_HOTSPOT = "moon";

export interface SectCanvasProps {
  store: SectStore;
  meta: SectMeta;
  ctx: WorldContext;
  /** The global set (backdrop and area proxies), once loaded. */
  global: LoadedSet | null;
  /** Resident chunks in flight order. */
  chunks: LoadedSet[];
  streamer: ChunkStreamer | null;
  flyer: Object3D | null;
  flyerLit: boolean;
  flyerPath: FlyerPath | null;
  clouds: CloudPuff[];
  /** Area centres (cranes circle them, cloud banks thin out around them). */
  anchors: Vec3[];
  /** The moon can be clicked (it starts a voice call) from this frame on (the summit), or never. */
  moonFromFrame: number | null;
  quality: Quality;
  /**
   * The tier's own quality: where the ladder climbs back to once frames have room again (none
   * without it).
   */
  ceiling?: Quality;
  /** The quality ladder may step down when frames run long (off for screenshots and forced tiers). */
  adaptive: boolean;
  /**
   * The ladder steps when the median frame runs over this (ms): 20 for the tier the page picked,
   * longer for one the visitor picked (their choice holds unless the page would feel broken).
   */
  frameBudgetMs?: number;
  baked: boolean;
  debug: boolean;
  debugEl: React.RefObject<HTMLDivElement | null>;
  /** Everything the opening view needs is on the GPU: signal once rendered. */
  openingReady: boolean;
  /**
   * The hotspot under the pointer and where its label goes (CSS px), or null for the place when the
   * point is behind the camera (the label hides).
   */
  onHover: (id: string | null, at: readonly [number, number] | null) => void;
  onSelect: (id: string) => void;
  /**
   * The Jin Yong reference under the pointer (meta.json "lore", lib/sect/lore.ts), or null, after
   * every pick ("hover") and on a tap of a touch screen ("tap"). Never a click target: a hotspot
   * always wins the pointer, and a reference whose `host` is the hovered hotspot only lends that
   * hotspot's label its name.
   */
  onLore?: (hit: LoreHit | null, how: "hover" | "tap") => void;
  /** A drag on the view has just started turning it (free look). */
  onLookDrag?: () => void;
  onRendered: () => void;
  /** One step down the ladder; `cadenceMs` is the screen's frame interval (null while unknown). */
  onDegrade: (cadenceMs: number | null) => void;
  /** One step back up toward `ceiling`. */
  onClimb?: () => void;
  onContextLost: () => void;
}

const noop = () => {};

// ---------------------------------------------------------------------------------------------

/**
 * Portrait screens (phones): the image is shifted up by this share of the screen height, so each
 * stop's landmark sits in the upper half, above the panel that covers the bottom (an off-centre
 * view of the same camera: picking and labels follow it).
 */
const PORTRAIT_SHIFT = 0.2;

function CameraRig({ store }: { store: SectStore }) {
  const camera = useThree((s) => s.camera);
  const size = useThree((s) => s.size);
  const offsetKey = useRef("");
  useFrame((_, delta) => {
    const { map } = store;
    let frame: number;
    const fl = store.flight;
    if (fl) {
      // A programmatic jump: ease from where the camera was to the destination, then arrive.
      const t = fl.duration > 0 ? (performance.now() - fl.t0) / (fl.duration * 1000) : 1;
      if (t >= 1 || store.reducedMotion) {
        store.u = fl.toU;
        store.flight = null;
        if (fl.onArrive) setTimeout(fl.onArrive, 0);
      } else {
        store.u = fl.fromU + (fl.toU - fl.fromU) * easeInOut(t, 1);
      }
      frame = uToFrame(map, store.u);
    } else if (store.reducedMotion) {
      const stop = nearestStop(map, store.targetU);
      store.u = stop.u;
      frame = stop.frame;
    } else {
      store.u = damp(store.u, store.targetU, 5, delta);
      frame = uToFrame(map, store.u);
    }
    if (store.frameOverride !== null) frame = store.frameOverride;
    store.frame = frame;
    // A few stops frame their subject (lib/sect/framing.ts): near the hold the camera takes the
    // film's pose of a few frames earlier (it stands back along the path), easing in and out.
    const s = sampleCamera(store.camera.frames, framingFrame(store.camera.holds, frame));
    camera.position.set(s.p[0], s.p[1], s.p[2]);
    // Free look turns the rendered camera on top of the path's orientation; a new path position
    // (scroll, jump, voice) swings it back. The path sample stays the flight's own camera.
    const look = store.look;
    // A held left or right arrow turns the view (not while the 3D view is covered).
    if (!store.paused && turnByKeys(look, delta)) wake(store, 250);
    const at = { targetU: store.targetU, flight: store.flight ? store.flight.t0 : null, override: store.frameOverride };
    if (followPath(look, at, performance.now() / 1000, store.reducedMotion)) wakeForRecenter(store);
    // And turn the view a little to centre their subject, easing in over the frames before the
    // hold and out after it; the free look turns on top of that.
    const framed = composeLook(s.q, framingAt(store.camera.holds, frame));
    // The tilt that keeps the view short of straight up or down depends on the view's own pitch.
    look.limits = lookLimits(framed);
    const c = clampLook(look, look.limits);
    look.yaw = c.yaw;
    look.pitch = c.pitch;
    const q = composeLook(framed, look);
    camera.quaternion.set(q[0], q[1], q[2], q[3]);
    const cam = camera as PerspectiveCamera;
    const fov = fovForAspect(s.fovY, store.camera.refAspect, size.width / Math.max(size.height, 1));
    if (Math.abs(cam.fov - fov) > 1e-4) {
      cam.fov = fov;
      cam.updateProjectionMatrix();
    }
    const shift = size.height > size.width * 1.15 ? Math.round(size.height * PORTRAIT_SHIFT) : 0;
    const key = `${size.width}x${size.height}:${shift}`;
    if (key !== offsetKey.current) {
      offsetKey.current = key;
      if (shift > 0) cam.setViewOffset(size.width, size.height, 0, shift, size.width, size.height);
      else cam.clearViewOffset();
    }
    camera.updateMatrixWorld();
  }, -3);
  return null;
}

/**
 * Free look input (lib/sect/free-look.ts). A press that moves less than a few pixels stays a click
 * (hotspot picking is untouched); past that it turns the view and the click the browser sends after
 * it is swallowed (Hotspots asks takeClick). A mouse drag turns and tilts; a finger only turns,
 * sideways: the canvas allows vertical pans (touch-action), so a vertical swipe still scrolls the
 * page and arrives here as pointercancel. A finger turns faster than a mouse (FREE_LOOK.touchGain).
 * The left and right arrow keys turn the view while held (up and down still fly between stops).
 * Escape swings the view back to the path the short way round. Neither works while something open
 * over the flight (an input, the map, a reader, the page view, fast travel) has the keys.
 */
function FreeLookInput({ store, onLookDrag }: { store: SectStore; onLookDrag?: () => void }) {
  const gl = useThree((s) => s.gl);
  const camera = useThree((s) => s.camera);
  useEffect(() => {
    const el = gl.domElement;
    const look = store.look;
    const prevTouch = el.style.touchAction;
    el.style.touchAction = "pan-y pinch-zoom";
    // A drag stops the page's text from being selected; `locked` holds what to put back, so a drag
    // that ends twice (or one that starts while another never ended) cannot leave it switched off.
    let prevSelect = "";
    let locked = false;
    const endDrag = () => {
      el.style.cursor = lookCursor(store.hovered !== null, false);
      if (!locked) return;
      document.body.style.userSelect = prevSelect;
      locked = false;
    };
    // Drop the press without a pick: a drag ends, a press that never moved far enough just goes.
    const drop = () => {
      const was = isDragging(look);
      look.press = null;
      look.swallowClick = false;
      if (was) endDrag();
    };
    const down = (e: PointerEvent) => {
      if (store.paused || (e.pointerType === "mouse" && e.button !== 0)) return;
      // A second finger (a pinch) or a new press replaces the press: end its drag first.
      const was = isDragging(look);
      pressDown(look, e.pointerId, e.clientX, e.clientY, e.pointerType === "touch");
      if (was && !isDragging(look)) endDrag();
    };
    const move = (e: PointerEvent) => {
      // The button came up somewhere the view did not hear it (over a panel before the drag
      // started, or in another window): the press is over, and hovering must not turn the view.
      if (e.pointerType !== "touch" && (e.buttons & 1) === 0 && look.press?.id === e.pointerId) {
        drop();
        return;
      }
      const k = radiansPerPixel((camera as PerspectiveCamera).fov, el.clientHeight);
      const r = pressMove(look, e.pointerId, e.clientX, e.clientY, k);
      if (!r) return;
      if (r === "start") {
        try {
          el.setPointerCapture(e.pointerId);
        } catch {
          // The pointer is already gone; the drag ends with its pointerup or pointercancel.
        }
        el.style.cursor = lookCursor(false, true);
        // A mouse drag must not select the text of the panels it passes over.
        if (!locked) {
          prevSelect = document.body.style.userSelect;
          locked = true;
        }
        document.body.style.userSelect = "none";
        window.getSelection()?.removeAllRanges();
        onLookDrag?.();
      }
      wake(store, 250);
    };
    const up = (e: PointerEvent) => {
      if (pressUp(look, e.pointerId)) endDrag();
    };
    const cancel = (e: PointerEvent) => {
      const was = isDragging(look) && look.press?.id === e.pointerId;
      pressCancel(look, e.pointerId);
      if (was) endDrag();
    };
    // Capture lost without a pointerup (a context menu, the element going away), or the window lost
    // focus mid-press: the press ends where it is.
    const lost = (e: PointerEvent) => {
      if (look.press?.id === e.pointerId) drop();
    };
    const blur = () => {
      if (look.press) drop();
      // A key held when the window lost focus never sends its keyup here.
      releaseTurnKeys(look);
    };
    /**
     * Something else has the keys: an input, a dialog, the map or the graphics popover, a reader,
     * the page view (fallback.tsx marks its Escape handled), or fast travel's ink.
     */
    const keysTaken = (e: KeyboardEvent) => {
      if (e.defaultPrevented || store.paused) return true;
      const t = e.target as HTMLElement | null;
      if (t?.closest?.('input, textarea, select, [contenteditable="true"], [role="dialog"], #sect-quality')) return true;
      return document.querySelector(".sect-map, .sect-travel, #sect-quality:not([hidden]), .sc-scrim, .sc-page") !== null;
    };
    const key = (e: KeyboardEvent) => {
      const turn = turnKeyIntent(e);
      if (turn !== null) {
        if (keysTaken(e)) return;
        e.preventDefault();
        setTurnKey(look, turn, true);
        wake(store, 250);
        return;
      }
      // One Escape, one thing: whatever is open over the flight closes first and the view stays
      // turned.
      if (e.key !== "Escape" || isDragging(look) || keysTaken(e)) return;
      recenterView(store);
    };
    // A key that comes up always lets go, wherever the focus went meanwhile.
    const keyUp = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft" || e.key === "Left") setTurnKey(look, 1, false);
      else if (e.key === "ArrowRight" || e.key === "Right") setTurnKey(look, -1, false);
    };
    el.addEventListener("pointerdown", down);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", cancel);
    el.addEventListener("lostpointercapture", lost);
    window.addEventListener("blur", blur);
    window.addEventListener("keydown", key);
    window.addEventListener("keyup", keyUp);
    return () => {
      el.removeEventListener("pointerdown", down);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("pointercancel", cancel);
      el.removeEventListener("lostpointercapture", lost);
      window.removeEventListener("blur", blur);
      window.removeEventListener("keydown", key);
      window.removeEventListener("keyup", keyUp);
      releaseTurnKeys(look);
      el.style.touchAction = prevTouch;
      drop();
      if (locked) endDrag();
    };
  }, [gl, camera, store, onLookDrag]);
  return null;
}

// ---------------------------------------------------------------------------------------------

function Atmosphere({ meta, ctx, store }: { meta: SectMeta; ctx: WorldContext; store: SectStore }) {
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const fog = useMemo(() => lookFogConstants(meta), [meta]);
  const sky = ctx.sky;

  useLayoutEffect(() => {
    scene.fog = new FogExp2(new Color(meta.fog.color), meta.fog.density);
    scene.background = new Color(meta.fog.color);
    return () => {
      scene.fog = null;
    };
  }, [scene, meta]);

  // Built once; the sky image arrives later and only swaps a uniform.
  const dome = useMemo(() => {
    const m = new Mesh(
      new SphereGeometry(1, 64, 32),
      createSkyMaterial({
        fog,
        texture: null,
        zenith: meta.sky.zenith,
        horizon: meta.sky.horizon,
        below: meta.sky.belowHorizon,
        fogColor: meta.fog.color,
        sunColor: meta.sun.color,
      }),
    );
    m.scale.setScalar(8500);
    // Drawn after the solid world (and the cloud sea, which writes depth), at the far plane, so its
    // clouds and haze are shaded only where nothing covers it: drawn first, it shaded every pixel
    // and was then painted over (13% of the world pass on average, 24% at the gate). The water,
    // the moon and the other transparent things still come after it.
    const mat = m.material as ShaderMaterial;
    mat.depthTest = true;
    mat.depthFunc = LessEqualDepth;
    mat.onBeforeCompile = (shader) => {
      // Just inside the far plane (exactly on it the dome would be clipped).
      shader.vertexShader = shader.vertexShader.replace(/}\s*$/, "  gl_Position.z = gl_Position.w * 0.999999;\n}\n");
    };
    m.renderOrder = 1000;
    m.frustumCulled = false;
    m.name = "sect.sky";
    return m;
  }, [fog, meta]);

  useEffect(() => {
    const u = (dome.material as ShaderMaterial).uniforms;
    u.tSky.value = sky;
    u.uHasSky.value = sky ? 1 : 0;
  }, [dome, sky]);

  const moon = useMemo(() => {
    if (!meta.moon) return null;
    const g = new Group();
    g.position.set(...meta.moon.position);
    const disc = new Mesh(new PlaneGeometry(2, 2), createMoonMaterial(fog, meta.moon.color, meta.fog.color));
    disc.scale.setScalar(meta.moon.radius);
    disc.renderOrder = -900;
    const halo = new Mesh(new PlaneGeometry(2, 2), createGlowMaterial(meta.moon.color, SECT_LOOK.moonHalo.day));
    halo.scale.setScalar(meta.moon.halo?.radius ?? meta.moon.radius * 3);
    halo.renderOrder = -901;
    g.add(halo, disc);
    g.name = "sect.moon";
    g.frustumCulled = false;
    return g;
  }, [fog, meta]);


  const cloudSea = useMemo(() => {
    const m = new Mesh(
      new CircleGeometry(8800, 96).rotateX(-Math.PI / 2),
      createCloudSeaMaterial(fog, meta.cloudSea.color, "#8f93ad", meta.fog.color),
    );
    m.position.y = meta.cloudSea.y;
    m.renderOrder = -800;
    m.frustumCulled = false;
    m.name = "sect.cloudsea";
    return m;
  }, [fog, meta]);

  // Twilight: from the jade slip to the summit the sky's colours, clouds and the moon's halo blend
  // toward the film's blue dusk (lib/sect/look.ts SECT_LOOK.twilight).
  const twilight = useMemo(() => {
    const L = SECT_LOOK.twilight;
    const from = store.camera.holds.find((h) => h.id === L.from)?.frame;
    const to = store.camera.holds.find((h) => h.id === L.to)?.frame;
    if (from === undefined || to === undefined || to <= from) return null;
    const u = (dome.material as ShaderMaterial).uniforms;
    const pairs: [Color, Color, Color][] = [];
    const add = (name: string, night: string) => {
      const v = u[name]?.value as Color | undefined;
      if (v) pairs.push([v, v.clone(), new Color(night)]);
    };
    add("uLookZenith", L.zenith);
    add("uLookMid", L.mid);
    add("uLookHorizon", L.horizon);
    add("uLookSun", L.sunHorizon);
    add("uFogColor", L.haze);
    add("uCloudSunLit", L.cloudSunLit);
    add("uCloudLit", L.cloudLit);
    add("uCloudShade", L.cloudShade);
    add("uCloudRim", L.cloudRim);
    // The cloud sea under everything, so the horizon is not a warm band under a blue sky.
    const sea = (cloudSea.material as ShaderMaterial).uniforms;
    for (const [name, night] of [
      ["uTop", L.cloudSea],
      ["uFogColor", L.haze],
    ] as const) {
      const v = sea[name]?.value as Color | undefined;
      if (v) pairs.push([v, v.clone(), new Color(night)]);
    }
    const halo = moon?.children[0] as Mesh | undefined;
    return { from, to, pairs, coverage: [u.uCoverage.value as number, L.coverage] as const, halo, last: -1 };
  }, [dome, moon, cloudSea, store]);

  useEffect(
    () => () => {
      for (const o of [dome, cloudSea, ...(moon ? moon.children : [])] as Mesh[]) {
        o.geometry.dispose();
        (o.material as ShaderMaterial).dispose();
      }
    },
    [dome, cloudSea, moon],
  );

  useFrame((state) => {
    const t = store.reducedMotion ? 0 : state.clock.elapsedTime;
    dome.position.copy(camera.position);
    cloudSea.position.x = Math.round(camera.position.x / 100) * 100;
    cloudSea.position.z = Math.round(camera.position.z / 100) * 100;
    (cloudSea.material as ShaderMaterial).uniforms.uTime.value = t;
    (dome.material as ShaderMaterial).uniforms.uTime.value = t;
    ctx.waterfallMaterial.uniforms.uTime.value = t;
    ctx.wetRock?.update(camera.position);
    if (moon) {
      moon.quaternion.copy(camera.quaternion);
      moon.updateMatrixWorld();
    }
    if (twilight) {
      const k = twilightAmount(store.frame, twilight.from, twilight.to);
      if (Math.abs(k - twilight.last) > 1e-3) {
        twilight.last = k;
        for (const [v, day, night] of twilight.pairs) v.copy(day).lerp(night, k);
        const [c0, c1] = twilight.coverage;
        (dome.material as ShaderMaterial).uniforms.uCoverage.value = c0 + (c1 - c0) * k;
      }
      // The halo strengthens toward the summit, where it also breathes slowly (its idle motion).
      const hm = twilight.halo?.material as ShaderMaterial | undefined;
      if (hm) {
        const base = SECT_LOOK.moonHalo.day + (SECT_LOOK.moonHalo.twilight - SECT_LOOK.moonHalo.day) * twilight.last;
        hm.uniforms.uStrength.value = base * (1 + 0.25 * twilight.last * breathe(t, 7));
      }
    }
  }, -2);

  return (
    <>
      <primitive object={dome} />
      {moon && <primitive object={moon} />}
      <primitive object={cloudSea} />
    </>
  );
}

// ---------------------------------------------------------------------------------------------

/** Adds objects to the overlay scene (drawn after the world, with its depth) while mounted. */
function useOverlay(overlay: Scene, objects: readonly Object3D[]) {
  useEffect(() => {
    for (const o of objects) overlay.add(o);
    return () => {
      for (const o of objects) overlay.remove(o);
    };
  }, [overlay, objects]);
}

/** Blender's volume cloud puffs as sorted soft sprites, one instanced draw (in the overlay scene). */
function CloudPuffs({
  meta,
  puffs,
  store,
  overlay,
  anchors,
}: {
  meta: SectMeta;
  puffs: CloudPuff[];
  store: SectStore;
  overlay: Scene;
  anchors: Vec3[];
}) {
  const camera = useThree((s) => s.camera);
  const fog = useMemo(() => lookFogConstants(meta), [meta]);
  const built = useMemo(() => {
    const path: Vec3[] = store.camera.frames.filter((_, i) => i % 6 === 0).map((f) => f.p);
    const packed = packPuffs(puffs, path, 2600, (c) => puffDensityScale(c, anchors));
    const n = packed.length / PUFF_STRIDE;
    if (n === 0) return null;
    const quad = new PlaneGeometry(2, 2);
    const geo = new InstancedBufferGeometry();
    geo.setIndex(quad.getIndex());
    geo.setAttribute("position", quad.getAttribute("position"));
    const buf = new InstancedInterleavedBuffer(new Float32Array(packed), PUFF_STRIDE, 1);
    buf.setUsage(DynamicDrawUsage);
    geo.setAttribute("iCenter", new InterleavedBufferAttribute(buf, 3, 0));
    geo.setAttribute("iA0", new InterleavedBufferAttribute(buf, 3, 3));
    geo.setAttribute("iA1", new InterleavedBufferAttribute(buf, 3, 6));
    geo.setAttribute("iA2", new InterleavedBufferAttribute(buf, 3, 9));
    geo.setAttribute("iDensity", new InterleavedBufferAttribute(buf, 1, 12));
    geo.instanceCount = n;
    const material = createCloudPuffMaterial(fog, meta.fog.color);
    const mesh = new Mesh(geo, material);
    mesh.name = "sect.cloudpuffs";
    mesh.frustumCulled = false;
    mesh.renderOrder = 3;
    return { mesh, material, quad, packed, buf, order: new Uint32Array(n), scratch: new Float32Array(n), last: new Vector3(1e9, 0, 0) };
  }, [fog, meta, puffs, store, anchors]);

  const objects = useMemo(() => (built ? [built.mesh] : []), [built]);
  useOverlay(overlay, objects);
  useEffect(
    () => () => {
      built?.mesh.geometry.dispose();
      built?.quad.dispose();
      built?.material.dispose();
    },
    [built],
  );

  const cam: Vec3 = useMemo(() => [0, 0, 0], []);
  useFrame((state) => {
    if (!built) return;
    built.material.uniforms.uTime.value = store.reducedMotion ? 0 : state.clock.elapsedTime;
    // Re-sort (and re-upload) only when the camera has moved; at a hold nothing changes.
    if (built.last.distanceToSquared(camera.position) < RESORT_DISTANCE2) return;
    built.last.copy(camera.position);
    cam[0] = camera.position.x;
    cam[1] = camera.position.y;
    cam[2] = camera.position.z;
    const { packed, buf, order, scratch } = built;
    sortFarToNear(packed, cam, order, scratch);
    const arr = buf.array as Float32Array;
    for (let i = 0; i < order.length; i++) {
      const src = order[i] * PUFF_STRIDE;
      arr.set(packed.subarray(src, src + PUFF_STRIDE), i * PUFF_STRIDE);
    }
    buf.needsUpdate = true;
  }, -1);

  return null;
}

/** The world's overlay decor, its tiered pieces (the formation's barrier and shafts) at the fx tier. */
function OverlayDecor({ objects, overlay, tier }: { objects: readonly Object3D[]; overlay: Scene; tier: ReturnType<typeof fxTier> }) {
  useOverlay(overlay, objects);
  useEffect(() => setOverlayTier(objects, tier), [objects, tier]);
  return null;
}

// ---------------------------------------------------------------------------------------------

/**
 * Lights for lit materials only (the baked world is unlit): the stand-in scene and the flyer.
 * Low golden sun from the west-south-west, a warm sky / ground fill, and a rim light from beyond
 * the subject so the flyer sits in the scene's light instead of on top of it.
 */
function Lights({ meta, shadows, sky }: { meta: SectMeta; shadows: boolean; sky: WorldContext["sky"] }) {
  const scene = useThree((s) => s.scene);
  const gl = useThree((s) => s.gl);
  const camera = useThree((s) => s.camera);
  const sun = useMemo(() => {
    const l = new DirectionalLight(new Color(meta.sun.color), 4.2);
    l.castShadow = shadows;
    if (shadows) {
      l.shadow.mapSize.set(2048, 2048);
      const c = l.shadow.camera;
      c.left = -110;
      c.right = 110;
      c.top = 110;
      c.bottom = -110;
      c.near = 1;
      c.far = 1600;
      c.updateProjectionMatrix();
      l.shadow.bias = -0.0004;
      l.shadow.normalBias = 0.35;
    }
    return l;
  }, [meta, shadows]);
  const rim = useMemo(() => new DirectionalLight(new Color("#ffd9a8"), 2.4), []);
  const hemi = useMemo(() => new HemisphereLight(new Color("#f2d2b4"), new Color("#7a5a48"), 0.9), []);

  useEffect(() => {
    if (!sky) return;
    const pm = new PMREMGenerator(gl);
    const env = pm.fromEquirectangular(sky).texture;
    scene.environment = env;
    scene.environmentIntensity = 0.8;
    pm.dispose();
    return () => {
      scene.environment = null;
      env.dispose();
    };
  }, [gl, scene, sky]);

  const dir = useMemo(() => new Vector3(...meta.sun.direction), [meta]);
  const fwd = useMemo(() => new Vector3(), []);
  useFrame(() => {
    // Keep the shadow box around what the camera is looking at.
    fwd.set(0, 0, -1).applyQuaternion(camera.quaternion);
    rim.position.copy(camera.position).addScaledVector(fwd, 400);
    rim.target.position.copy(camera.position);
    fwd.multiplyScalar(70).add(camera.position);
    sun.target.position.copy(fwd);
    sun.position.copy(fwd).addScaledVector(dir, 700);
    sun.target.updateMatrixWorld();
    sun.updateMatrixWorld();
    rim.target.updateMatrixWorld();
    rim.updateMatrixWorld();
  }, -1);

  return (
    <>
      <primitive object={sun} />
      <primitive object={sun.target} />
      <primitive object={rim} />
      <primitive object={rim.target} />
      <primitive object={hemi} />
    </>
  );
}

// ---------------------------------------------------------------------------------------------

function nextFrame(): Promise<void> {
  return new Promise((r) => requestAnimationFrame(() => r()));
}

/**
 * The loaded sets. The global set is always drawn once ready; a chunk is drawn while the camera
 * frame is inside its need range, and the backdrop's proxy of that area is hidden while it is.
 * Before a set is first drawn its textures go to the GPU one per animation frame (not while the
 * camera moves fast or the view turns, lib/sect/background-work.ts deferUpload) and its shaders
 * compile in the background, so arriving at an area does not stall on uploads. A set is never drawn
 * before all of that is done (`ready`); until then the backdrop's proxy stands in for it.
 */
function World({
  global,
  chunks,
  store,
  streamer,
  post,
  standIns = false,
  noCards = false,
  onGlobalReady,
}: {
  global: LoadedSet | null;
  chunks: LoadedSet[];
  store: SectStore;
  streamer: ChunkStreamer | null;
  /** The world is drawn through the postprocessing composer (not straight to the screen). */
  post: boolean;
  /**
   * The quality ladder's stand-in step (lib/sect/runtime.ts Quality.standIns): only the area the
   * camera is in is drawn; the others stay loaded, and the backdrop's proxies show in their place.
   */
  standIns?: boolean;
  /** The ladder's tree-card step (Quality.noCards): the sets' tree cards are not drawn. */
  noCards?: boolean;
  onGlobalReady: () => void;
}) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const warming = useRef(new WeakSet<LoadedSet>());
  const mounted = useRef(true);
  const live = useRef({ global, chunks, post, standIns });
  live.current = { global, chunks, post, standIns };
  // Tree cards off (or back) on every set, a set loaded later included. Their programs stay compiled
  // (the warm-up compiles hidden materials too), so they come back without a stall.
  useEffect(() => {
    let changed = false;
    for (const s of [global, ...chunks]) {
      if (!s) continue;
      for (const m of s.cardMaterials) {
        if (m.visible !== noCards) continue;
        m.visible = !noCards;
        changed = true;
      }
    }
    if (changed) wake(store, 200);
  }, [global, chunks, noCards, store]);
  /** Stand-in for the composer's buffer while shaders compile (see warm below); made on first use. */
  const warmTarget = useRef<WebGLRenderTarget | null>(null);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      warmTarget.current?.dispose();
      warmTarget.current = null;
    };
  }, []);

  useLayoutEffect(() => {
    // Ground at grazing angles: anisotropic filtering, set before the first upload. Never after it:
    // three keeps another anisotropy as another GPU texture, made from the image, which is closed
    // once uploaded (prepare.ts imageClosed): that texture would come out empty, drawn black.
    const aniso = Math.min(8, gl.capabilities.getMaxAnisotropy());
    for (const set of [global, ...chunks]) {
      if (!set || set.ready || set.dropped || warming.current.has(set)) continue;
      for (const t of set.textures) {
        if (t.anisotropy !== aniso && t.version <= 1 && !imageClosed(t)) {
          t.anisotropy = aniso;
          t.needsUpdate = true;
        }
      }
    }
  }, [gl, global, chunks]);

  useEffect(() => {
    const alive = (s: LoadedSet) => mounted.current && !s.dropped && (live.current.global === s || live.current.chunks.includes(s));
    /** The set would be drawn at the camera's frame if it were ready (the global set always is). */
    const inView = (s: LoadedSet) => s.need === null || (store.frame >= s.need[0] && store.frame <= s.need[1]);
    const warm = async (s: LoadedSet) => {
      // When the set was first wanted on screen: its uploads share one wait from then on.
      let wantedSince: number | null = null;
      for (const t of s.textures) {
        // A 4096 px upload stalls the frame it lands in (6-30 ms): not during a jump, and not while
        // the camera moves fast or the view turns (a drag, an arrow key, the swing back), except
        // that an area already wanted on screen waits only so long, all its textures together.
        for (;;) {
          if (!alive(s)) break;
          const now = performance.now();
          if (wantedSince === null && inView(s)) wantedSince = now;
          const wait = deferUpload({
            flight: store.flight !== null,
            framesToGo: framesToGo(store),
            turning: isTurning(store.look),
            inView: inView(s),
            waitedMs: uploadWaitedMs(wantedSince, now),
          });
          if (!wait) break;
          await nextFrame();
        }
        if (!alive(s)) return;
        try {
          gl.initTexture(t);
        } catch (e) {
          console.warn("[sect] texture upload failed", e);
        }
        await nextFrame();
      }
      if (!alive(s)) return;
      try {
        // Compile for the buffer the set is really drawn into. Through the composer that is a
        // half-float buffer whose programs write linear colour; programs for the screen write sRGB,
        // and three keys its programs by that (WebGLPrograms outputColorSpace: any render target
        // other than the screen, or an XR one, means linear). Compiled against the screen, the
        // warm-up built programs nobody used and the area's first drawn frame compiled the real ones
        // (18-40 ms). Any off-screen target gives the same key, so a 1x1 half-float one stands in
        // for the composer's. compileAsync compiles at once and only then waits for the driver, so
        // the target can go back straight after the calls.
        const prev = gl.getRenderTarget();
        let pending: Promise<unknown>[];
        try {
          if (live.current.post) {
            warmTarget.current ??= new WebGLRenderTarget(1, 1, { type: HalfFloatType, depthBuffer: false });
            gl.setRenderTarget(warmTarget.current);
          }
          pending = s.scenes.map((root) => gl.compileAsync(root, camera, scene));
        } finally {
          gl.setRenderTarget(prev);
        }
        await Promise.all(pending);
      } catch (e) {
        console.warn("[sect] shader warm-up failed", e);
      }
      if (!alive(s)) return;
      if (s === live.current.global) {
        s.ready = true;
        onGlobalReady();
      } else {
        streamer?.markReady(s.id);
      }
      wake(store, 600);
    };
    for (const s of [global, ...chunks]) {
      if (!s || s.ready || s.dropped || warming.current.has(s)) continue;
      warming.current.add(s);
      void warm(s);
    }
  }, [gl, scene, camera, global, chunks, streamer, store, onGlobalReady]);

  useFrame(() => {
    const f = store.frame;
    // A set freed while the canvas still holds it (assets.ts disposeSet) is never drawn again.
    const globalOn = global !== null && drawable(global);
    if (global && global.drawn !== globalOn) {
      global.drawn = globalOn;
      for (const r of global.scenes) r.visible = globalOn;
    }
    // The ladder's stand-in step: only the camera's own area is drawn (the rest as proxies).
    const only = live.current.standIns ? (streamer?.areaAt(f) ?? null) : null;
    for (const s of chunks) {
      // `chunks` comes through the canvas's own React root and may still hold a set the streamer
      // has dropped (and disposed): that one stays hidden.
      const on = drawable(s) && s.need !== null && f >= s.need[0] && f <= s.need[1] && (only === null || s.id === only);
      if (s.drawn !== on) {
        s.drawn = on;
        for (const r of s.scenes) r.visible = on;
      }
    }
    if (global) {
      for (const [area, meshes] of global.proxies) {
        const show = !chunks.some((s) => s.id === area && s.drawn);
        for (const m of meshes) if (m.visible !== show) m.visible = show;
      }
    }
  }, -2.5);

  return (
    <>
      {global?.scenes.map((root) => <primitive key={root.uuid} object={root} />)}
      {chunks.flatMap((s) => s.scenes.map((root) => <primitive key={root.uuid} object={root} />))}
    </>
  );
}

// ---------------------------------------------------------------------------------------------

interface Pickable {
  id: string;
  set: LoadedSet;
  meshes: Mesh[];
  box: PickBox;
}

/**
 * A pointer this close (CSS px) to an item's centre picks it when the ray misses everything: a
 * 1 m artifact or a tea table 70 m away is a few pixels wide.
 */
const NEAR_ITEM_PX = 26;

/**
 * A hotspot mesh this small is raycast without a BVH while its BVH waits to be built (measured:
 * about 0.6 ms at 10k triangles, 1.5 ms at 20k); a larger one is picked by its box until then.
 * 20k covers every forge artifact and the forge's own centre piece (18k).
 */
const PLAIN_PICK_TRIS = 20_000;

/**
 * Hotspot picking over the drawn sets. Broad phase on boxes, then the hotspot's own triangles
 * through a BVH (a pick costs microseconds on a 150k-triangle gate). The BVHs are built in idle
 * time while the camera rests, never during a flight; until one exists the pick falls back (see
 * PLAIN_PICK_TRIS). A hit is dropped when solid scenery is nearer on the same ray (occluder BVHs
 * are built the same way, for meshes the ray passes). When the ray misses, an item whose centre is within NEAR_ITEM_PX of the pointer
 * (and not hidden behind scenery) is picked, so small far objects can be hit. Near the summit the
 * moon itself can be picked. Picks run at most every 50 ms while the pointer moves, and a few
 * times a second while flying.
 *
 * After each pick, the Jin Yong references (meta.lore, lib/sect/lore.ts) are tested by their boxes
 * alone (no meshes of their own): with a hotspot under the pointer, only a reference that hotspot
 * holds (its label names it); with none, the nearest unhidden reference box, which onLore reports
 * for its card. A reference is never clicked: a tap on one (touch) only shows its card.
 */
function Hotspots({
  store,
  ctx,
  sets,
  meta,
  moonFromFrame,
  onHover,
  onSelect,
  onLore,
}: {
  store: SectStore;
  ctx: WorldContext;
  sets: LoadedSet[];
  meta: SectMeta;
  moonFromFrame: number | null;
  onHover: SectCanvasProps["onHover"];
  onSelect: SectCanvasProps["onSelect"];
  onLore?: SectCanvasProps["onLore"];
}) {
  const gl = useThree((s) => s.gl);
  const camera = useThree((s) => s.camera);
  const size = useThree((s) => s.size);
  /** NDC (x, y), the window position (cx, cy, CSS px) and the kind ("mouse", "pen", "touch") of the pointer. */
  const pointer = useRef({ x: 0, y: 0, cx: 0, cy: 0, kind: "mouse", inside: false, dirty: false, lastMove: 0 });
  const pickRef = useRef<() => string | null>(() => null);
  /** The reference the last pick found under the pointer (host: the hotspot that holds it). */
  const loreRef = useRef<{ id: LoreId; host: string | null } | null>(null);
  const loreBoxes = useMemo(() => (meta.lore ?? []).filter((b) => isLoreId(b.id)), [meta]);
  /** World point of the last hotspot hit (the label sits above it, not above the middle of a pair). */
  const hitPoint = useMemo(() => new Vector3(), []);
  const ray = useMemo(() => new Raycaster(), []);
  const ndc = useMemo(() => new Vector2(), []);
  const moon = useMemo(() => (meta.moon ? new Sphere(new Vector3(...meta.moon.position), meta.moon.radius) : null), [meta]);

  const pickables = useMemo(() => {
    const out: Pickable[] = [];
    for (const s of sets) {
      for (const [id, meshes] of s.hotspotMeshes) {
        const h = ctx.hotspotMap.get(id);
        if (!h || !h.size.some((x) => x > 0)) continue;
        out.push({ id, set: s, meshes, box: { id, center: h.center, size: h.size } });
      }
    }
    return out;
  }, [sets, ctx]);
  const fallPicks = useMemo(() => fallPickQuads(meta.waterfalls, [...ctx.hotspotMap.values()]), [meta, ctx]);

  // Occluders: opaque scenery meshes that are not hotspots, not instanced, not cards or water.
  const occ = useMemo(() => {
    const perSet: { set: LoadedSet; list: Mesh[] }[] = [];
    for (const s of sets) {
      const hot = new Set<Mesh>();
      for (const list of s.hotspotMeshes.values()) for (const m of list) hot.add(m);
      const list: Mesh[] = [];
      for (const root of s.scenes) {
        root.traverse((o) => {
          const m = o as Mesh;
          if (!m.isMesh || hot.has(m) || (m as unknown as { isInstancedMesh?: boolean }).isInstancedMesh) return;
          const mat = m.material as { transparent?: boolean; alphaTest?: number } | undefined;
          if (!mat || Array.isArray(mat) || mat.transparent || (mat.alphaTest ?? 0) > 0) return;
          if (triangleCount(m.geometry) > 120000) return;
          list.push(m);
        });
      }
      perSet.push({ set: s, list });
    }
    return { perSet, queue: new Set<Mesh>(), sphere: new Vector3(), tmp: new Vector3() };
  }, [sets]);

  /**
   * BVHs still to build: every hotspot mesh of the loaded sets (prepareScene no longer builds them
   * at load, where they froze the flight for 30-163 ms per file). Built meshes and dropped sets fall
   * out as the builder walks the list.
   */
  const hotQueue = useMemo(() => {
    const list: { mesh: Mesh; set: LoadedSet }[] = [];
    for (const pk of pickables) for (const m of pk.meshes) if (!hasBvh(m)) list.push({ mesh: m, set: pk.set });
    return list;
  }, [pickables]);

  /** When the camera last moved (performance.now()); every rendered frame updates it. */
  const lastMove = useRef(0);
  useFrame(() => {
    if (!cameraStill(store)) lastMove.current = performance.now();
  }, -1);

  useEffect(() => {
    // The BVH builder: in idle time, and only once the camera has been still for a moment
    // (lib/sect/background-work.ts mayBuildBvh), one build per idle callback plus any more that fit
    // in what is left of it. Hotspots of drawn sets first, then the other sets' hotspots, then the
    // occluders the pointer's rays have passed. No `timeout`: a forced callback runs mid-flight,
    // which is the freeze this avoids. Picking works without the BVHs meanwhile (pick below).
    // Where a worker runs (bvh-build.ts), the trees are built there instead, one at a time, as soon
    // as the camera is still (lib/sect/background-work.ts mayPostBvh): the main thread only copies
    // the arrays out and takes the tree back. The rules above are the fallback without one.
    let id = 0;
    let rate = BVH_MS_PER_KTRI;
    let alive = true;
    /** A worker job is under way. */
    let busy = false;
    /** No worker here: build on the main thread, in idle time, as before. */
    let mainThread = false;
    /** Meshes the worker could not build (left to their boxes, not retried). */
    const failed = new WeakSet<Mesh>();
    // Inspection scripts (?debug=1): where the trees were built and what it cost the main thread.
    if (/[?&]debug=1/.test(window.location.search)) (window as unknown as { __sectBvh?: typeof bvhStats }).__sectBvh = bvhStats;
    const idle = typeof window.requestIdleCallback === "function";
    const schedule = (cb: (d?: IdleDeadline) => void): number => (idle ? window.requestIdleCallback(cb) : window.setTimeout(cb, 120));
    const cancel = (h: number) => (idle ? window.cancelIdleCallback(h) : clearTimeout(h));
    // A touch screen picks only on a tap: its big meshes keep picking by their boxes instead of
    // freezing the phone at rest for a BVH (lib/sect/background-work.ts bvhWanted).
    const touch = window.matchMedia("(pointer: coarse)").matches;
    const wanted = (m: Mesh) => !hasBvh(m) && !failed.has(m) && bvhWanted(triangleCount(m.geometry), touch);
    const offThread = (mesh: Mesh) => {
      busy = true;
      void buildBvhOffThread(mesh)
        .then((r) => {
          if (r === "unavailable") mainThread = true;
          else if (r === "failed") failed.add(mesh);
          else occ.queue.delete(mesh);
        })
        .catch((e) => {
          console.warn("[sect] BVH build failed", e);
          failed.add(mesh);
        })
        .finally(() => {
          busy = false;
        });
    };
    const nextJob = (): Mesh | null => {
      for (let i = hotQueue.length - 1; i >= 0; i--) if (hotQueue[i].set.dropped || !wanted(hotQueue[i].mesh)) hotQueue.splice(i, 1);
      const hot = hotQueue.find((j) => j.set.drawn) ?? hotQueue[0];
      if (hot) return hot.mesh;
      for (const m of occ.queue) {
        if (wanted(m)) return m;
        occ.queue.delete(m);
      }
      return null;
    };
    const step = (deadline?: IdleDeadline) => {
      id = schedule(step);
      const now = performance.now();
      if (!cameraStill(store)) {
        lastMove.current = now;
        return;
      }
      // The loading screen has gone (sect-experience.tsx sets it once the world is up).
      const pageReady = document.body.dataset.sectReady === "1";
      if (!mainThread) {
        if (busy || !alive || !mayPostBvh({ pageReady, stillForMs: now - lastMove.current })) return;
        const mesh = nextJob();
        if (mesh) offThread(mesh);
        return;
      }
      for (let built = 0; ; built++) {
        const mesh = nextJob();
        if (!mesh) return;
        const tris = triangleCount(mesh.geometry);
        const go = mayBuildBvh({
          pageReady,
          stillForMs: performance.now() - lastMove.current,
          builtThisSlice: built,
          costMs: bvhCostMs(tris, rate),
          timeRemainingMs: deadline ? deadline.timeRemaining() : 0,
        });
        if (!go) return;
        const t0 = performance.now();
        ensureBvh(mesh);
        rate = updateBvhRate(rate, performance.now() - t0, tris);
        occ.queue.delete(mesh);
      }
    };
    id = schedule(step);
    return () => {
      alive = false;
      cancel(id);
    };
  }, [hotQueue, occ, store]);

  useEffect(() => {
    const el = gl.domElement;
    const setFrom = (e: { clientX: number; clientY: number }) => {
      const r = el.getBoundingClientRect();
      const p = pointer.current;
      p.x = ((e.clientX - r.left) / r.width) * 2 - 1;
      p.y = -((e.clientY - r.top) / r.height) * 2 + 1;
      p.cx = e.clientX;
      p.cy = e.clientY;
      p.inside = true;
    };
    /** The kind of pointer that pressed last: a touch or a pen taps references, a mouse hovers them. */
    let pressedBy = "mouse";
    const down = (e: PointerEvent) => {
      pressedBy = e.pointerType || "mouse";
      pointer.current.kind = pressedBy;
    };
    const move = (e: PointerEvent) => {
      setFrom(e);
      pointer.current.kind = e.pointerType || "mouse";
      pointer.current.dirty = true;
      wake(store, 200);
    };
    const leave = () => {
      pointer.current.inside = false;
      pointer.current.dirty = true;
      wake(store, 200);
    };
    const occluded = (dist: number): boolean => {
      const o = ray.ray.origin;
      for (const { set, list } of occ.perSet) {
        if (!set.drawn) continue;
        for (const m of list) {
          const g = m.geometry;
          if (!g.boundingSphere) g.computeBoundingSphere();
          const s = g.boundingSphere!;
          occ.sphere.copy(s.center).applyMatrix4(m.matrixWorld);
          const rad = s.radius * m.matrixWorld.getMaxScaleOnAxis();
          // Sphere on the ray segment before the hit?
          const t = occ.tmp.copy(occ.sphere).sub(o).dot(ray.ray.direction);
          if (t + rad < 0 || t - rad > dist) continue;
          if (ray.ray.distanceSqToPoint(occ.sphere) > rad * rad) continue;
          const bvh = (g as { boundsTree?: unknown }).boundsTree;
          if (!bvh) {
            occ.queue.add(m);
            continue;
          }
          ensureBvh(m);
          ray.firstHitOnly = true;
          const hits = ray.intersectObject(m, false);
          ray.firstHitOnly = false;
          if (hits.length > 0 && hits[0].distance < dist - 0.3) return true;
        }
      }
      return false;
    };
    const near = new Vector3();
    const savedDir = new Vector3();
    /** The item nearest the pointer on screen within NEAR_ITEM_PX, when nothing is in the way. */
    const nearItem = (p: { x: number; y: number }): { id: string; distance: number } | null => {
      let found: Pickable | null = null;
      let bestD2 = NEAR_ITEM_PX * NEAR_ITEM_PX;
      for (const pk of pickables) {
        if (!pk.set.drawn || !pk.id.includes(":")) continue;
        near.set(pk.box.center[0], pk.box.center[1], pk.box.center[2]).project(camera);
        if (near.z > 1 || near.z < -1) continue;
        const dx = ((near.x - p.x) * size.width) / 2;
        const dy = ((near.y - p.y) * size.height) / 2;
        const d2 = dx * dx + dy * dy;
        if (d2 < bestD2) {
          bestD2 = d2;
          found = pk;
        }
      }
      if (!found) return null;
      const c = found.box.center;
      near.set(c[0], c[1], c[2]);
      const o = ray.ray.origin;
      const dist = near.distanceTo(o);
      // Aim at the item's centre for the occlusion test, then put the ray back.
      savedDir.copy(ray.ray.direction);
      ray.ray.direction.copy(near).sub(o).normalize();
      const half = Math.max(found.box.size[0], found.box.size[1], found.box.size[2]) / 2;
      const hidden = occluded(Math.max(dist - half, 0));
      ray.ray.direction.copy(savedDir);
      if (hidden) return null;
      hitPoint.copy(near);
      return { id: found.id, distance: dist };
    };
    /** How far along the ray the last pick's hotspot was hit (the references it holds lie there). */
    let hotDistance = Infinity;
    const pickHotspot = (): string | null => {
      const p = pointer.current;
      hotDistance = Infinity;
      // Nothing is under the pointer while a drag turns the view (no label sweeping across).
      if (!p.inside || store.paused || isDragging(store.look)) return null;
      ndc.set(p.x, p.y);
      ray.setFromCamera(ndc, camera);
      const o = ray.ray.origin;
      const d = ray.ray.direction;
      const active = new Map<string, Mesh[]>();
      const boxes: PickBox[] = [];
      for (const pk of pickables) {
        if (!pk.set.drawn) continue;
        const list = active.get(pk.id);
        if (list) list.push(...pk.meshes);
        else {
          active.set(pk.id, [...pk.meshes]);
          boxes.push(pk.box);
        }
      }
      let best: { id: string; distance: number } | null = null;
      // Until a mesh's BVH is built (idle time, at rest), a small mesh is raycast triangle by
      // triangle and a large one can only be tested by its hotspot's box: of those boxes the one
      // the ray leaves first (the innermost, like an artifact's inside the forge hall's, or the
      // front one) is kept aside and wins only over exact hits beyond its far side
      // (lib/sect/pick.ts pickWithBoxes). The boxes follow the pieces that move (idle.ts turns the forge's artifacts'
      // and the cranes' boxes with them), so every hotspot stays clickable meanwhile. A box the
      // camera is inside never stands in (it would cover the whole screen).
      let boxOnly: BoxHit | null = null;
      for (const hit of boxHits([o.x, o.y, o.z], [d.x, d.y, d.z], boxes, 450)) {
        if (best && hit.distance > best.distance) break;
        const meshes = active.get(hit.id) ?? [];
        const precise = meshes.filter((m) => hasBvh(m) || triangleCount(m.geometry) <= PLAIN_PICK_TRIS);
        ray.firstHitOnly = true;
        const hits = ray.intersectObjects(precise, false);
        ray.firstHitOnly = false;
        if (hits.length > 0) {
          if (!best || hits[0].distance < best.distance) {
            best = { id: hit.id, distance: hits[0].distance };
            hitPoint.copy(hits[0].point);
          }
        } else if (precise.length < meshes.length && canStandIn(hit) && (!boxOnly || hit.exit < boxOnly.exit)) {
          boxOnly = hit;
        }
      }
      // Falling water picks the item it is part of (lib/sect/waterfall.ts fallPickQuads): the merged
      // water mesh has no object names to tag.
      for (const fp of fallPicks) {
        if (!active.has(fp.id)) continue;
        const t = rayQuad([o.x, o.y, o.z], [d.x, d.y, d.z], fp.corners);
        if (t !== null && t <= 450 && (!best || t < best.distance)) {
          best = { id: fp.id, distance: t };
          ray.ray.at(t, hitPoint);
        }
      }
      const picked = pickWithBoxes(best, boxOnly);
      if (picked && picked === boxOnly) {
        best = { id: boxOnly.id, distance: boxOnly.distance };
        ray.ray.at(boxOnly.distance, hitPoint);
      }
      // A hit on a landmark's wall near an item that sits inside it (a lit library floor) is that item.
      if (best && !best.id.includes(":")) {
        const lm = boxes.find((b) => b.id === best!.id);
        const inner = lm ? containedItemAt([hitPoint.x, hitPoint.y, hitPoint.z], lm, boxes) : null;
        if (inner) best = { id: inner, distance: best.distance };
      }
      if (best && occluded(best.distance)) best = null;
      if (!best) best = nearItem(p);
      if (!best && moon && moonFromFrame !== null && store.frame >= moonFromFrame && ray.ray.intersectsSphere(moon)) {
        hitPoint.copy(moon.center);
        return MOON_HOTSPOT;
      }
      hotDistance = best ? best.distance : Infinity;
      return best ? best.id : null;
    };
    /**
     * The Jin Yong reference under the pointer after the hotspot pick `id` (the ray as that pick left
     * it): with a hotspot, a reference box it holds that the ray enters by its hit; with none, the
     * nearest reference box in reach that no scenery hides.
     */
    const pickLore = (id: string | null): { id: LoreId; host: string | null } | null => {
      const p = pointer.current;
      if (loreBoxes.length === 0 || !p.inside || store.paused || isDragging(store.look)) return null;
      const o = ray.ray.origin;
      const d = ray.ray.direction;
      return loreUnderPointer([o.x, o.y, o.z], [d.x, d.y, d.z], loreBoxes, id ? { id, distance: hotDistance } : null, occluded);
    };
    const pick = (): string | null => {
      const id = pickHotspot();
      loreRef.current = pickLore(id);
      return id;
    };
    const click = (e: MouseEvent) => {
      // The click that ends a drag (free look) is not a pick.
      if (takeClick(store.look)) return;
      setFrom(e);
      const id = pick();
      if (id) onSelect(id);
      else if (pressedBy !== "mouse" && onLore) {
        // A tap names the reference under it (its card shows for a few seconds); a tap on nothing
        // hides the card. Neither opens or flies anywhere.
        const l = loreRef.current;
        onLore(l && !l.host ? { ...l, at: [e.clientX, e.clientY] } : null, "tap");
      }
    };
    el.addEventListener("pointerdown", down);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerleave", leave);
    el.addEventListener("click", click);
    pickRef.current = pick;
    return () => {
      el.removeEventListener("pointerdown", down);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerleave", leave);
      el.removeEventListener("click", click);
    };
  }, [gl, camera, size, pickables, fallPicks, ray, ndc, onSelect, onLore, loreBoxes, occ, store, hitPoint, moon, moonFromFrame]);

  const lastPick = useRef(0);
  const corner = useMemo(() => new Vector3(), []);
  /**
   * Label anchor: above the object under the pointer. Horizontally at the hit point (a pair of
   * lions shares one hotspot box); vertically at the top of the hotspot's box, or a little above
   * the hit point when that box top is far away. Null when the hit point is behind the camera (the
   * view turned away from a hovered object: projected, it would show mirrored on screen).
   */
  const labelAnchor = useCallback(
    (id: string): [number, number] | null => {
      let minY = Infinity;
      if (id === MOON_HOTSPOT && moon) {
        corner.copy(moon.center).addScaledVector(camera.up, moon.radius).project(camera);
        if (corner.z <= 1) minY = (-corner.y * 0.5 + 0.5) * size.height;
      } else {
        const h = ctx.hotspotMap.get(id);
        if (!h) return null;
        for (let k = 0; k < 8; k++) {
          corner.set(
            h.center[0] + (k & 1 ? 0.5 : -0.5) * h.size[0],
            h.center[1] + (k & 2 ? 0.5 : -0.5) * h.size[1],
            h.center[2] + (k & 4 ? 0.5 : -0.5) * h.size[2],
          );
          corner.project(camera);
          if (corner.z > 1) continue;
          minY = Math.min(minY, (-corner.y * 0.5 + 0.5) * size.height);
        }
      }
      corner.copy(hitPoint).project(camera);
      if (!onScreenDepth(corner.z)) return null;
      const hx = (corner.x * 0.5 + 0.5) * size.width;
      const hy = (-corner.y * 0.5 + 0.5) * size.height;
      const top = Number.isFinite(minY) ? Math.max(minY - 10, hy - 140) : hy - 40;
      const x = Math.min(Math.max(hx, 90), size.width - 90);
      const y = Math.min(Math.max(top, 40), size.height - 20);
      return [x, y];
    },
    [ctx, camera, corner, size, hitPoint, moon],
  );

  useFrame((state, delta) => {
    const p = pointer.current;
    const now = state.clock.elapsedTime;
    const throttled = now - lastPick.current < 0.05;
    if ((p.dirty && !throttled) || (p.inside && now - lastPick.current > 0.25)) {
      p.dirty = false;
      lastPick.current = now;
      const id = pickRef.current();
      if (id !== store.hovered) {
        store.hovered = id;
        gl.domElement.style.cursor = lookCursor(id !== null, isDragging(store.look));
      }
      onHover(id, id ? labelAnchor(id) : null);
      // The reference under the pointer, if any (no glow, no cursor change: the card is the only sign).
      // A finger never hovers: its card comes from the tap alone (the pointer a lifted finger leaves
      // behind would bring a dismissed card back); a reference a hotspot holds rides on its label.
      const l = loreRef.current;
      const own = l && (l.host !== null || p.kind !== "touch") ? l : null;
      onLore?.(own ? { ...own, at: [p.cx, p.cy] } : null, "hover");
    } else if (store.hovered && !p.dirty) {
      // Keep the label on the object while the camera moves (hidden while it is behind the camera).
      onHover(store.hovered, labelAnchor(store.hovered));
    }
    for (const h of ctx.hotspotMap.values()) {
      const active = store.hovered === h.id || store.focused === h.id || store.selected === h.id;
      const target = active ? (store.reducedMotion ? 0.85 : 0.75 + 0.25 * Math.sin(now * 3.2)) : 0;
      if (target === 0 && h.uniform.value === 0) continue;
      h.uniform.value = damp(h.uniform.value, target, 10, delta);
    }
  }, -1);
  return null;
}

// ---------------------------------------------------------------------------------------------

/**
 * Each drawn chunk's idle motion (idle.ts): the forge's artifacts along their hoop, the formation's
 * core, the library's scrolls, glow rhythms, fluttering banners and swaying trees. Turning pieces
 * hold still while the pointer is on one (so it stays under the pointer); with reduced motion
 * everything rests as baked.
 */
function IdleMotion({ sets, store }: { sets: LoadedSet[]; store: SectStore }) {
  useFrame((state, delta) => {
    if (store.paused) return;
    const t = state.clock.elapsedTime;
    const still = store.reducedMotion;
    IDLE_TIME.value = t;
    IDLE_ON.value = still ? 0 : 1;
    const pointed = (prefix: string) => !!(store.hovered?.startsWith(prefix) || store.focused?.startsWith(prefix));
    for (const s of sets) if (s.idle && s.drawn) updateIdle(s.idle, t, delta, still, pointed);
  }, -2);
  return null;
}

// ---------------------------------------------------------------------------------------------

function Flyer({ store, object, path }: { store: SectStore; object: Object3D; path: FlyerPath }) {
  // A JSX group (not one made in useMemo): StrictMode runs memos twice, and re-parenting the
  // loaded object into a second group would leave the rendered one empty.
  const ref = useRef<Group>(null);
  useFrame(() => {
    const g = ref.current;
    if (!g) return;
    // Keyed to the frame the camera stands at (a framed stop's camera stands back, framing.ts).
    const s = samplePath(path.frames, framingFrame(store.camera.holds, store.frame));
    g.position.set(s.p[0], s.p[1], s.p[2]);
    g.quaternion.set(s.q[0], s.q[1], s.q[2], s.q[3]);
    g.updateMatrix();
    g.updateMatrixWorld(true);
  }, -2);
  return (
    <group ref={ref} name="sect.flyer">
      <primitive object={object} />
    </group>
  );
}

// ---------------------------------------------------------------------------------------------

/**
 * Composer pipeline (high and mid tiers): world, overlay with depth, cloud shade / bloom / haze /
 * vignette. `ceiling` is the tier's own quality: the atmosphere passes follow the tier, not the
 * ladder's step (lib/sect/post.ts atmosFeatures).
 */
function Post({
  quality,
  ceiling,
  overlay,
  meta,
  ctx,
  sets,
  store,
}: {
  quality: Quality;
  ceiling?: Quality;
  overlay: Scene;
  meta: SectMeta;
  ctx: WorldContext;
  sets: LoadedSet[];
  store: SectStore;
}) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const size = useThree((s) => s.size);
  const dpr = useThree((s) => s.viewport.dpr);
  const fog = useMemo(() => lookFogConstants(meta), [meta]);
  const features = atmosFeatures(ceiling ?? quality, quality);
  const { cloudShadows, holdFocus } = features;
  // Created in an effect, not a memo: StrictMode runs memos twice, and the discarded pipeline's
  // (never written) depth texture would win the shared soft-depth uniform.
  const [pipe, setPipe] = useState<Pipeline | null>(null);
  useLayoutEffect(() => {
    const p = createPipeline(
      gl,
      scene,
      overlay,
      camera,
      {
        msaa: quality.msaa,
        bloom: quality.bloom,
        vignette: meta.vignette,
        sunDir: new Vector3(...meta.sun.direction),
        sunHaze: SECT_LOOK.sunHaze,
        atmos: { fog, features: { cloudShadows, holdFocus } },
      },
      (t) => {
        SOFT_DEPTH.tDepth.value = t;
        SOFT_DEPTH.uHasDepth.value = t ? 1 : 0;
      },
    );
    setPipe(p);
    // Inspection scripts (?debug=1): same-frame comparisons with a pass off.
    const w = window as unknown as { __sectPost?: Pipeline };
    if (/[?&]debug=1/.test(window.location.search)) w.__sectPost = p;
    return () => {
      p.dispose();
      setPipe((cur) => (cur === p ? null : cur));
      if (w.__sectPost === p) delete w.__sectPost;
    };
  }, [gl, scene, overlay, camera, quality.msaa, quality.bloom, meta, fog, cloudShadows, holdFocus]);
  useLayoutEffect(() => {
    pipe?.composer.setSize(size.width, size.height);
  }, [pipe, size, dpr]);
  useEffect(() => {
    setCardCoverage(ctx, sets, quality.msaa > 0);
  }, [ctx, sets, quality.msaa]);
  const db = useMemo(() => new Vector2(), []);
  // Each stop's subject (the panel's landmark): kept out of cloud shade, and where the hold focuses.
  const subjects = useMemo(() => {
    const m = new Map<string, Vector3>();
    for (const h of store.camera.holds) {
      const p = meta.areas.find((a) => a.id === h.id)?.anchor ?? meta.hotspots.find((x) => x.id === h.id)?.center;
      if (p) m.set(h.id, new Vector3(...p));
    }
    return m;
  }, [store, meta]);
  const atmos = useMemo(() => ({ rest: 0, fwd: new Vector3(), frame: Number.NaN, yaw: 0, pitch: 0 }), []);
  useEffect(
    () => () => {
      store.report.focus = false;
    },
    [store],
  );
  useFrame((state, delta) => {
    store.report.focus = false;
    if (!pipe) {
      state.gl.render(state.scene, state.camera);
      return;
    }
    if (pipe.cloudShadow || pipe.holdFocus) {
      const near = nearestHold(store.camera.holds, store.frame);
      const subject = near ? (subjects.get(near.id) ?? null) : null;
      // Full keep at the stop, none 40 frames out (so it never pops as the next stop takes over).
      const keep = near ? Math.max(0, 1 - Math.abs(near.frame - store.frame) / 40) : 0;
      pipe.cloudShadow?.keep(subject, ATMOS.cloudShadow.keepRadius * keep);
      const hf = pipe.holdFocus;
      if (hf) {
        // Only the stop's own framing: at rest at a stop, the view not turned off the path, and
        // the subject ahead (its distance along the view at least half its distance).
        let axial = 0;
        if (subject) {
          camera.getWorldDirection(atmos.fwd);
          axial = atmos.fwd.dot(subject) - atmos.fwd.dot(camera.position);
        }
        const framed = subject !== null && axial > 0.5 * camera.position.distanceTo(subject);
        const atStop = framed && holdAt(store.camera.holds, store.frame) !== null && !isTurned(store.look);
        const still = atStop && cameraStill(store);
        // The view itself moved this frame (along the path, or turned by a drag): the focus goes at
        // once, not over the input fade, so no moving frame shows it.
        const L = store.look;
        const viewMoved = store.frame !== atmos.frame || L.yaw !== atmos.yaw || L.pitch !== atmos.pitch;
        atmos.frame = store.frame;
        atmos.yaw = L.yaw;
        atmos.pitch = L.pitch;
        atmos.rest = still ? atmos.rest + Math.min(delta, 0.1) : 0;
        // Under fast travel's ink the focus is in at once (nobody sees it come).
        const w = store.inked && still ? 1 : holdFocusStep(hf.weight, still ? "still" : viewMoved ? "view" : "input", atmos.rest, delta);
        if (w !== hf.weight || (still && w < 1)) wake(store, 250);
        hf.weight = w;
        store.report.focus = still && w < 1;
        if (framed) hf.focus = axial;
      }
    }
    pipe.sunHaze.updateFromCamera(camera, size.width / Math.max(size.height, 1));
    gl.getDrawingBufferSize(db);
    SOFT_DEPTH.uResolution.value.copy(db);
    const c = camera as PerspectiveCamera;
    SOFT_DEPTH.uNear.value = c.near;
    SOFT_DEPTH.uFar.value = c.far;
    pipe.composer.render(delta);
  }, 1);
  return null;
}

/**
 * Real reflections at the Heart-Mirror stop on High and Medium (reflect/index.ts): the mirror's cube
 * map and the Still Pond's planar image, drawn after the camera, the sets' visibility and the
 * decoration have moved this frame and before the composer draws it. Nothing on Low: the water and
 * the mirror keep their analytic sky. With ?debug=1, window.__sectReflect measures the passes' GPU
 * time (`mode` "passes") or the whole frame's ("frame"), and can switch either pass off.
 */
function Reflections({ sets, quality, ctx, store, debug }: { sets: LoadedSet[]; quality: Quality; ctx: WorldContext; store: SectStore; debug: boolean }) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const tier = reflectTier(quality);
  const [refl, setRefl] = useState<SectReflections | null>(null);
  const probe = useRef<{ timer: SpanTimer | null; mode: "passes" | "frame" }>({ timer: null, mode: "passes" });
  useLayoutEffect(() => {
    if (!tier) return;
    const r = new SectReflections(tier);
    setRefl(r);
    const w = window as unknown as { __sectReflect?: unknown };
    const p = probe.current;
    let timer: SpanTimer | null = null;
    if (debug) {
      const ctx2 = gl.getContext();
      timer = new SpanTimer(typeof WebGL2RenderingContext !== "undefined" && ctx2 instanceof WebGL2RenderingContext ? ctx2 : null, 120);
      p.timer = timer;
      r.timer = p.mode === "passes" ? timer : null;
      w.__sectReflect = {
        reflections: r,
        get mode() {
          return p.mode;
        },
        set mode(m: "passes" | "frame") {
          p.mode = m;
          r.timer = m === "passes" ? timer : null;
          timer?.clear();
        },
        gpu: () => timer?.stats() ?? {},
        timing: () => timer?.available ?? false,
        clear: () => timer?.clear(),
      };
    }
    return () => {
      r.dispose();
      timer?.dispose();
      p.timer = null;
      store.report.reflection = false;
      setRefl((cur: SectReflections | null) => (cur === r ? null : cur));
      if ((w.__sectReflect as { reflections?: unknown } | undefined)?.reflections === r) delete w.__sectReflect;
    };
  }, [tier, debug, gl, store]);
  const qualityKey = `${tier}|${quality.noCards ? "nc" : ""}|${quality.standIns ? "si" : ""}|${quality.lowTextures ? "lt" : ""}`;
  // The whole frame's GPU time (debug "frame" mode): from before anything draws to after the composer.
  useFrame(() => {
    const t = probe.current.timer;
    t?.poll();
    if (t && probe.current.mode === "frame") t.begin("frame");
  }, -19);
  // After every default-priority update (grass, idle motion, decoration) and the debug probe's
  // counter reset, before the composer (priority 1).
  useFrame((_, delta) => {
    const st = refl?.update({
      gl,
      scene,
      camera: camera as PerspectiveCamera,
      sets,
      time: ctx.waterfallMaterial.uniforms.uTime.value as number,
      now: performance.now(),
      dt: delta * 1000,
      quality: qualityKey,
      lean: quality.standIns === true || quality.noCards === true,
      snap: store.inked,
    });
    store.report.reflection = st?.settling ?? false;
  }, 0.5);
  useFrame(() => {
    if (probe.current.timer && probe.current.mode === "frame") probe.current.timer.end();
  }, 5);
  return null;
}

/** Low tier: no postprocessing; the overlay is drawn on top without soft edges. */
function PlainRender({ overlay, ctx, sets }: { overlay: Scene; ctx: WorldContext; sets: LoadedSet[] }) {
  useEffect(() => {
    SOFT_DEPTH.uHasDepth.value = 0;
    // The canvas is multisampled on this tier, so cards keep alpha to coverage.
    setCardCoverage(ctx, sets, true);
  }, [ctx, sets]);
  useFrame(({ gl, scene, camera }) => {
    gl.render(scene, camera);
    const auto = gl.autoClear;
    gl.autoClear = false;
    gl.render(overlay, camera);
    gl.autoClear = auto;
  }, 1);
  return null;
}

/** Render statistics for the debug HUD and inspection scripts (?debug=1). */
export interface FrameStats {
  /** Frames R3F rendered since the page opened. */
  renders: number;
  /** requestAnimationFrame callbacks seen by the driver since the page opened. */
  rafs: number;
  /** The quality ladder's view (the screen's frame interval, recent frame and GPU times). */
  ladder?: () => LadderStatus;
}

/** Idle renders per second at rest, and after IDLE_DIM_MS with no input at all (someone reading, or away). */
const IDLE_FPS = 30;
const IDLE_DIM_FPS = 20;
const IDLE_DIM_MS = 20000;
/** Before the opening view is up the veil covers the canvas: idle frames only keep it alive. */
const IDLE_VEILED_FPS = 10;
const INPUT_EVENTS = ["pointerdown", "pointermove", "keydown", "wheel", "touchstart", "scroll"] as const;

/**
 * GPU time of a frame through EXT_disjoint_timer_query_webgl2 (Chrome; not Safari), read a few
 * frames later. A handful of queries in flight at most; a disjoint (the GPU was preempted, or its
 * clock changed) drops what was in flight.
 */
interface GpuTimer {
  begin(): void;
  end(tag: number): void;
  poll(take: (ms: number, tag: number) => void): void;
  dispose(): void;
}

function createGpuTimer(ctx: WebGLRenderingContext | WebGL2RenderingContext): GpuTimer | null {
  if (typeof WebGL2RenderingContext === "undefined" || !(ctx instanceof WebGL2RenderingContext)) return null;
  const ext = ctx.getExtension("EXT_disjoint_timer_query_webgl2") as { TIME_ELAPSED_EXT: number; GPU_DISJOINT_EXT: number } | null;
  if (!ext) return null;
  const free: WebGLQuery[] = [];
  const pending: { q: WebGLQuery; tag: number }[] = [];
  let active: WebGLQuery | null = null;
  return {
    begin() {
      if (active || pending.length >= 4) return;
      const q = free.pop() ?? ctx.createQuery();
      if (!q) return;
      ctx.beginQuery(ext.TIME_ELAPSED_EXT, q);
      active = q;
    },
    end(tag) {
      if (!active) return;
      ctx.endQuery(ext.TIME_ELAPSED_EXT);
      pending.push({ q: active, tag });
      active = null;
    },
    poll(take) {
      if (pending.length === 0) return;
      const disjoint = ctx.getParameter(ext.GPU_DISJOINT_EXT) as boolean;
      while (pending.length > 0) {
        const p = pending[0];
        if (!disjoint && !ctx.getQueryParameter(p.q, ctx.QUERY_RESULT_AVAILABLE)) break;
        pending.shift();
        if (!disjoint) take((ctx.getQueryParameter(p.q, ctx.QUERY_RESULT) as number) / 1e6, p.tag);
        free.push(p.q);
      }
    },
    dispose() {
      if (active) ctx.endQuery(ext.TIME_ELAPSED_EXT);
      for (const q of [...free, ...pending.map((p) => p.q), ...(active ? [active] : [])]) ctx.deleteQuery(q);
      free.length = 0;
      pending.length = 0;
      active = null;
    },
  };
}

/**
 * The render loop. While anything moves (the camera, a flight, a pulsing hotspot, a wake()), R3F
 * runs its "always" loop and renders every display frame. Otherwise it is back on demand, with a
 * low idle rate for the water and clouds (IDLE_FPS, IDLE_DIM_FPS after a while with no input, 2 fps
 * with reduced motion), and nothing at all while a reader covers the scene (a highlight from the
 * reader still wakes it).
 *
 * At the bottom of the quality ladder (`maxFps`), moving frames are capped too: rendered at that
 * rate instead of every display frame, unless the screen shows no more frames than that anyway.
 *
 * Idle and capped frames render inside this loop's own display frame (R3F's advance()). An
 * invalidate() from here rendered one display frame late and then stopped, so on a 30 Hz screen (an
 * iPhone in Low Power Mode) the 30 fps idle rate and the cap gave 13-15 renders a second.
 *
 * The frame loop is switched through the store's set(), not setFrameloop(): that one also resets
 * the clock, which would make every animated shader jump.
 *
 * The quality ladder (lib/sect/runtime.ts FrameLadder): this loop shows it the screen's own frame
 * interval (display frames after one where nothing rendered), the intervals and GPU times of moving
 * frames (not the ones that upload a texture or compile a program, nor any for LADDER.settleMs after
 * a set becomes ready or first draws, or the canvas resizes), and asks it for a step down
 * (`onDegrade`) or back up (`onClimb`, when `climbScale` says there is one). A climb that rebuilds
 * the postprocessing pipeline (`climbAtRest`: MSAA or bloom back on) waits for the camera to rest,
 * so its stall lands where only the water and clouds move, not mid-flight.
 */
function Driver({
  store,
  adaptive,
  budgetMs,
  maxFps,
  climbScale,
  climbAtRest = false,
  onDegrade,
  onClimb,
  stats,
  sets,
  veiled,
}: {
  store: SectStore;
  adaptive: boolean;
  budgetMs: number;
  maxFps: number;
  /** climbCost of the next step up, or null at the tier's own quality. */
  climbScale: number | null;
  /** The next step up rebuilds the postprocessing pipeline (lib/sect/runtime.ts climbRebuildsPipeline). */
  climbAtRest?: boolean;
  onDegrade: (cadenceMs: number | null) => void;
  onClimb: () => void;
  stats: FrameStats;
  sets: LoadedSet[];
  /** The loading screen still covers the canvas. */
  veiled: boolean;
}) {
  const set = useThree((s) => s.set);
  const get = useThree((s) => s.get);
  const invalidate = useThree((s) => s.invalidate);
  const advance = useThree((s) => s.advance);
  const gl = useThree((s) => s.gl);
  const size = useThree((s) => s.size);
  const dpr = useThree((s) => s.viewport.dpr);
  const ladder = useMemo(() => new FrameLadder(performance.now()), []);
  const live = useRef({ adaptive, budgetMs, maxFps, climbScale, climbAtRest, onDegrade, onClimb, veiled });
  live.current = { adaptive, budgetMs, maxFps, climbScale, climbAtRest, onDegrade, onClimb, veiled };
  /**
   * The opening view has been up once. The veil never comes back on this canvas, though `veiled`
   * turns on again when the streamer later drops the opening areas (it did: 10 fps at rest).
   */
  const opened = useRef(false);
  /** The render under way is a capped moving frame (rendered from the loop below, not by R3F's "always"). */
  const cappedFrame = useRef(false);
  const track = useMemo(
    () => ({
      /** The last render was a moving frame (its successor's interval is a moving one). */
      moving: false,
      /** Moving frames still to skip (an upload or a compile landed in them). */
      skip: 0,
      counts: "",
      ready: new WeakSet<LoadedSet>(),
      drawn: new WeakSet<LoadedSet>(),
      timer: null as GpuTimer | null,
      timing: false,
      /** A climb the ladder asked for that waits for the camera to rest (climbAtRest). */
      climbPending: false,
    }),
    [],
  );

  useEffect(() => {
    track.timer = createGpuTimer(gl.getContext());
    stats.ladder = () => ladder.status(performance.now());
    return () => {
      track.timer?.dispose();
      track.timer = null;
      delete stats.ladder;
    };
  }, [gl, track, stats, ladder]);

  // A new canvas size or pixel ratio reallocates every buffer: the next frames say nothing.
  useEffect(() => {
    ladder.settle(performance.now());
  }, [ladder, size, dpr]);

  useEffect(() => {
    let raf = 0;
    let lastTick = 0;
    let lastRenders = -1;
    let lastIdle = 0;
    let lastCapped = 0;
    let lastInput = performance.now();
    const onInput = () => {
      lastInput = performance.now();
    };
    for (const e of INPUT_EVENTS) window.addEventListener(e, onInput, { passive: true, capture: true });
    /** Render now, in this display frame. */
    const render = (now: number, capped: boolean) => {
      cappedFrame.current = capped;
      try {
        advance(now);
      } finally {
        cappedFrame.current = false;
      }
    };
    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      stats.rafs++;
      // Nothing rendered since the last display frame: this interval is the screen's own.
      if (lastTick > 0 && stats.renders === lastRenders) ladder.quietTick(now - lastTick);
      lastTick = now;
      tick(now);
      lastRenders = stats.renders;
    };
    const tick = (now: number) => {
      const { maxFps } = live.current;
      if (!live.current.veiled) opened.current = true;
      const veiled = !opened.current;
      const pulse = !store.reducedMotion && !store.modal && (store.hovered !== null || store.focused !== null || store.selected !== null);
      const continuous = !store.paused && (isMoving(store) || pulse || now < store.wakeUntil);
      const capped = maxFps > 0 && !capIsMoot(maxFps, ladder.cadenceMs());
      const mode = get().frameloop;
      if (continuous && !capped) {
        if (mode !== "always") {
          set({ frameloop: "always" });
          // This display frame too (R3F's own loop starts with the next one).
          render(now, false);
          invalidate();
        }
        return;
      }
      if (mode === "always") set({ frameloop: "demand" });
      if (store.paused) return;
      if (continuous) {
        if (now - lastCapped >= 1000 / maxFps - 2) {
          lastCapped = now;
          render(now, true);
        }
        return;
      }
      // Under a reader nothing needs to move.
      if (store.modal) return;
      const idleFps = store.reducedMotion ? 2 : veiled ? IDLE_VEILED_FPS : now - lastInput > IDLE_DIM_MS ? IDLE_DIM_FPS : IDLE_FPS;
      if (now - lastIdle >= 1000 / Math.min(idleFps, capped ? maxFps : idleFps) - 2) {
        lastIdle = now;
        render(now, false);
      }
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      for (const e of INPUT_EVENTS) window.removeEventListener(e, onInput, { capture: true });
      set({ frameloop: "demand" });
    };
  }, [store, set, get, invalidate, advance, stats, ladder]);

  useFrame((state, delta) => {
    stats.renders++;
    const now = performance.now();
    const t = track;
    const moving = state.frameloop === "always" || cappedFrame.current;
    // The interval of the first moving frame after a rest is the rest's.
    const first = moving && !t.moving;
    t.moving = moving;
    // A texture upload or a shader compile since the last frame stalls its successor too.
    const m = gl.info.memory;
    const counts = `${m.textures}:${m.geometries}:${gl.info.programs?.length ?? 0}`;
    if (counts !== t.counts) {
      t.counts = counts;
      t.skip = 2;
    }
    for (const s of sets) {
      if (s.ready && !t.ready.has(s)) {
        t.ready.add(s);
        ladder.settle(now);
      }
      if (s.drawn && !t.drawn.has(s)) {
        t.drawn.add(s);
        ladder.settle(now);
      }
    }
    const L = live.current;
    t.timer?.poll((ms, gen) => ladder.gpuTime(now, ms, gen));
    if (!moving || !L.adaptive) {
      // At rest: the climb the ladder asked for in flight that rebuilds the pipeline (climbAtRest).
      if (t.climbPending && L.adaptive && !moving && cameraStill(store)) {
        t.climbPending = false;
        if (L.climbAtRest && L.climbScale !== null) {
          ladder.stepped(now, "up");
          L.onClimb();
        }
      }
      return;
    }
    if (t.timer) {
      t.timer.begin();
      t.timing = true;
    }
    if (first || t.skip > 0) {
      t.skip = Math.max(0, t.skip - 1);
      return;
    }
    ladder.frame(now, delta * 1000);
    const capMs = L.maxFps > 0 && !capIsMoot(L.maxFps, ladder.cadenceMs()) ? 1000 / L.maxFps : 0;
    const dir = ladder.decide(now, L.budgetMs, capMs, L.climbScale);
    if (!dir) return;
    if (dir === "up" && L.climbAtRest) {
      // Taken at the next rest (above): a pipeline rebuild mid-flight stalls a frame there.
      t.climbPending = true;
      return;
    }
    t.climbPending = false;
    ladder.stepped(now, dir);
    if (dir === "down") L.onDegrade(ladder.cadenceMs());
    else L.onClimb();
  }, -20);

  // The end of the frame's GPU work (after the composer, priority 1).
  useFrame(() => {
    if (!track.timing) return;
    track.timing = false;
    track.timer?.end(ladder.generation);
  }, 4);
  return null;
}

/**
 * Decoration outside the sets (incense, the forge fire, cranes, petals, the valley's life, the
 * waterfalls' foam and spray, the overlay's clouds, mist and beams) has its shaders compiled in the
 * background as soon as it exists, as World does for the sets. Compiled on first sight instead,
 * each one stalled that frame mid-flight (46 ms of a 53 ms frame flying into the formation).
 */
function WarmDecor({ sets, overlay, post }: { sets: LoadedSet[]; overlay: Scene; post: boolean }) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  useEffect(() => {
    let cancelled = false;
    // Two display frames on: the decoration a new set brings mounts in this commit's effects.
    let raf = requestAnimationFrame(() => {
      raf = requestAnimationFrame(() => {
        if (cancelled) return;
        // Not the sets (World warms them), nor the grass (grass.tsx warms its own).
        const roots = new Set<Object3D>(sets.flatMap((s) => s.scenes));
        for (const o of scene.children) if (o.name === "sect.grass") roots.add(o);
        // As in World: programs for the composer's half-float buffer write linear colour, and three
        // keys its programs by that, so they compile against a stand-in target of that kind.
        const target = post ? new WebGLRenderTarget(1, 1, { type: HalfFloatType, depthBuffer: false }) : null;
        const prev = gl.getRenderTarget();
        try {
          gl.setRenderTarget(target);
          const pending = scene.children.filter((o) => !roots.has(o)).map((o) => gl.compileAsync(o, camera, scene));
          pending.push(gl.compileAsync(overlay, camera));
          void Promise.all(pending).catch((e) => console.warn("[sect] decoration warm-up failed", e));
        } catch (e) {
          console.warn("[sect] decoration warm-up failed", e);
        } finally {
          gl.setRenderTarget(prev);
          target?.dispose();
        }
      });
    });
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
    };
  }, [gl, scene, camera, sets, overlay, post]);
  return null;
}

/**
 * The canvas's report on each frame it renders (store.ts CanvasReport), for fast travel's settled
 * wait: the frame count and what the renderer holds once everything has drawn. Grass, the
 * reflections and the hold focus add what they are still filling in.
 */
function FrameReport({ store }: { store: SectStore }) {
  const gl = useThree((s) => s.gl);
  useFrame(() => {
    const r = store.report;
    r.frames++;
    r.geometries = gl.info.memory.geometries;
    r.textures = gl.info.memory.textures;
    r.programs = gl.info.programs?.length ?? 0;
  }, 4.5);
  return null;
}

/**
 * One frame with nothing in the drawn sets culled, when fast travel asks for it (store.uncull)
 * behind its ink: three uploads a mesh's buffers the first time it is drawn, so every mesh of the
 * areas around the place, and every grass cell on them (grass.tsx culls its own cells), reaches
 * the GPU then, rather than in the frames of a look round after the ink has cleared. Culling is back
 * on for the next frame.
 */
function UncullOnce({ store, sets }: { store: SectStore; sets: LoadedSet[] }) {
  const scene = useThree((s) => s.scene);
  const culled = useRef<Object3D[]>([]);
  const hidden = useRef<Object3D[]>([]);
  // After the world and grass have set this frame's visibility, before the composer draws.
  useFrame(() => {
    if (!store.uncull) return;
    store.uncull = false;
    const drawn = new Set<string>();
    for (const s of sets) {
      if (!s.drawn) continue;
      drawn.add(s.id);
      for (const root of s.scenes) {
        root.traverse((o) => {
          if (o.frustumCulled && (o as Mesh).isMesh) {
            o.frustumCulled = false;
            culled.current.push(o);
          }
        });
      }
    }
    for (const g of scene.children) {
      if (g.name !== "sect.grass") continue;
      for (const m of g.children) {
        if (m.visible || !drawn.has(m.name.slice("sect.grass.".length))) continue;
        m.visible = true;
        hidden.current.push(m);
      }
    }
  }, 0.9);
  useFrame(() => {
    for (const o of culled.current) o.frustumCulled = true;
    for (const o of hidden.current) o.visible = false;
    culled.current = [];
    hidden.current = [];
  }, 4.6);
  return null;
}

function fmtTris(n: number): string {
  return n >= 1e6 ? `${(n / 1e6).toFixed(2)}M` : n >= 1e3 ? `${Math.round(n / 1e3)}k` : String(n);
}

function DebugProbe({
  el,
  store,
  baked,
  ctx,
  global,
  chunks,
  streamer,
  overlay,
  stats,
  grass,
}: {
  el: React.RefObject<HTMLDivElement | null>;
  store: SectStore;
  baked: boolean;
  ctx: WorldContext;
  global: LoadedSet | null;
  chunks: LoadedSet[];
  streamer: ChunkStreamer | null;
  overlay: Scene;
  stats: FrameStats;
  grass: GrassDebug;
}) {
  const gl = useThree((s) => s.gl);
  const acc = useRef({ frames: 0, time: 0, fps: 0, last: 0 });
  const last = useRef({ calls: 0, triangles: 0 });
  useEffect(() => {
    gl.info.autoReset = false;
    return () => {
      gl.info.autoReset = true;
    };
  }, [gl]);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  useEffect(() => {
    // Exposed for screenshot/inspection scripts in debug mode only.
    (window as unknown as { __sect?: unknown }).__sect = {
      gl,
      scene,
      camera,
      store,
      ctx,
      global,
      chunks,
      streamer,
      overlay,
      stats,
      // Grass tufts: `enabled` switches them off and on, stats() says what the last frame drew.
      grass,
      softDepth: SOFT_DEPTH,
      info: () => ({
        ...last.current,
        textures: gl.info.memory.textures,
        geometries: gl.info.memory.geometries,
        frame: store.frame,
        stream: streamer?.status() ?? null,
        globalTris: global?.tris ?? 0,
        residentTris: (global?.tris ?? 0) + chunks.reduce((a, s) => a + s.tris, 0),
        drawnTris: (global?.drawn ? global.tris : 0) + chunks.reduce((a, s) => a + (s.drawn ? s.tris : 0), 0),
      }),
    };
    return () => {
      delete (window as unknown as { __sect?: unknown }).__sect;
    };
  }, [gl, scene, camera, store, ctx, global, chunks, streamer, overlay, stats, grass]);
  useFrame(() => gl.info.reset(), -10);
  useFrame((state, delta) => {
    const a = acc.current;
    a.frames++;
    a.time += delta;
    if (a.time >= 0.5) {
      a.fps = a.frames / a.time;
      a.frames = 0;
      a.time = 0;
    }
    const r = gl.info.render;
    last.current = { calls: r.calls, triangles: r.triangles };
    if (!el.current || state.clock.elapsedTime - a.last < 0.25) return;
    a.last = state.clock.elapsedTime;
    const m = gl.info.memory;
    const st = streamer?.status();
    const chunkLine = st
      ? [
          ...st.resident.map((c) => `${c.id}${c.drawn ? "*" : c.ready ? "" : "~"}`),
          ...st.loading.map((id) => `${id}...`),
          ...st.failed.map((id) => `${id}!`),
        ].join(" ") || "none"
      : "none";
    const resident = (global?.tris ?? 0) + chunks.reduce((s, c) => s + c.tris, 0);
    const mb = ((global?.bytes ?? 0) + chunks.reduce((s, c) => s + c.bytes, 0)) / 1e6;
    const gs = grass.stats();
    el.current.textContent = [
      `fps        ${a.fps.toFixed(1)} (${state.frameloop})`,
      `draw calls ${r.calls}`,
      `triangles  ${r.triangles.toLocaleString("en-US")}`,
      `textures   ${m.textures}`,
      `geometries ${m.geometries}`,
      `chunks     ${chunkLine}`,
      `resident   ${chunks.length} chunks · ${fmtTris(resident)} tris · ${mb.toFixed(1)} MB`,
      `grass      ${grass.enabled ? gs.tier : "off"} · ${gs.cells} cells · ${fmtTris(gs.instances)} tufts · ${fmtTris(gs.resident)} held`,
      `frame      ${store.frame.toFixed(2)}`,
      `scroll u   ${store.u.toFixed(1)} / ${store.map.totalUnits}`,
      `renders    ${stats.renders} / raf ${stats.rafs}`,
      `quality    ${store.qualityLabel}`,
      `dpr        ${gl.getPixelRatio().toFixed(2)}`,
      `scene      ${baked ? "baked" : "stand-in"} · ${ctx.lowTextures ? "low" : "full"} textures`,
    ].join("\n");
  }, 2);
  return null;
}

function ReadySignal({ active, onRendered, store }: { active: boolean; onRendered: () => void; store: SectStore }) {
  const count = useRef(0);
  const done = useRef(false);
  useEffect(() => {
    if (active) wake(store, 3000);
  }, [active, store]);
  useFrame(() => {
    if (!active || done.current) return;
    count.current++;
    if (count.current >= 3) {
      done.current = true;
      setTimeout(onRendered, 0);
    }
  }, 3);
  return null;
}

// ---------------------------------------------------------------------------------------------

function SectCanvas(props: SectCanvasProps) {
  const {
    store,
    meta,
    ctx,
    global,
    chunks,
    streamer,
    flyer,
    flyerLit,
    flyerPath,
    clouds,
    anchors,
    moonFromFrame,
    quality,
    adaptive,
    frameBudgetMs = AUTO_FRAME_BUDGET_MS,
    baked,
    debug,
    debugEl,
    openingReady,
    onHover,
    onSelect,
    onLore,
    onLookDrag,
    onRendered,
    onDegrade,
    onClimb,
    ceiling,
    onContextLost,
  } = props;
  const [globalReady, setGlobalReady] = useState(false);
  // False once the canvas has gone: R3F then loses its context on purpose (to free the GPU memory
  // at once), and that loss is not the graphics card dropping the scene.
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const shadows = quality.post && quality.msaa > 0 && !baked;
  const onGlobalReady = useCallback(() => setGlobalReady(true), []);
  const overlay = useMemo(() => {
    const s = new Scene();
    s.name = "sect.overlay";
    return s;
  }, []);
  const stats = useMemo<FrameStats>(() => ({ renders: 0, rafs: 0 }), []);
  const grassDebug = useMemo(() => createGrassDebug(), []);
  const fog = useMemo(() => lookFogConstants(meta), [meta]);
  // Without the post pass there is no scene depth, so puffs cannot fade where they meet rock; the
  // mountain mist (sect/mist.py) hugs rock everywhere and would show hard lines there.
  const shownClouds = useMemo(() => (quality.post ? clouds : clouds.filter((p) => !p.kind?.startsWith("mist."))), [clouds, quality.post]);
  const sets = useMemo(() => (global ? [global, ...chunks] : chunks), [global, chunks]);
  const forgeSet = useMemo(() => chunks.find((s) => s.id === "forge") ?? null, [chunks]);
  const mirrorSet = useMemo(() => chunks.find((s) => s.id === "mirror") ?? null, [chunks]);
  // The pond's analytic Heart-Mirror on the face's own plane (each time the area loads afresh).
  useEffect(() => {
    if (mirrorSet?.pond) aimPondMirror(mirrorSet.pond.uniforms, mirrorSet.pond.mirror);
  }, [mirrorSet]);
  const formationSet = useMemo(() => chunks.find((s) => s.id === "formation") ?? null, [chunks]);
  const decorTier = fxTier(quality);
  const needsLights = flyerLit || sets.some((s) => s.litMaterials > 0);
  // The screen's pixel ratio, followed live: the window moved to another screen, or the page zoomed.
  const [screenDpr, setScreenDpr] = useState(() => (typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1));
  useEffect(() => {
    const check = () => setScreenDpr(window.devicePixelRatio || 1);
    check();
    // Matches only this ratio, so it changes (once) when the ratio does; then it is made again. A
    // slow poll backs it up (an emulated screen changes the ratio without the event).
    const mq = window.matchMedia(`(resolution: ${screenDpr}dppx)`);
    mq.addEventListener("change", check);
    window.addEventListener("resize", check);
    const poll = window.setInterval(check, 1000);
    return () => {
      mq.removeEventListener("change", check);
      window.removeEventListener("resize", check);
      clearInterval(poll);
    };
  }, [screenDpr]);
  const dpr = effectiveDpr(quality, screenDpr);
  const climbScale = ceiling ? climbCost(quality, ceiling, screenDpr) : null;
  const climbAtRest = ceiling ? climbRebuildsPipeline(quality, ceiling, screenDpr) : false;
  useEffect(() => {
    store.qualityLabel = `${quality.post ? "post" : "plain"} · msaa ${quality.msaa} · bloom ${quality.bloom ? "on" : "off"} · ${quality.lowTextures ? "2k" : "4k"} textures${quality.standIns ? " · stand-ins" : ""}${quality.noCards ? " · no cards" : ""}${quality.maxFps > 0 ? ` · ${quality.maxFps} fps cap` : ""}`;
    wake(store, 600);
  }, [quality, store]);

  return (
    <Canvas
      flat
      frameloop="demand"
      dpr={dpr}
      shadows={shadows ? "percentage" : false}
      // Opaque: the sky covers every pixel, so the compositor need not blend the canvas over the page.
      gl={{ antialias: !quality.post, powerPreference: "high-performance", stencil: false, alpha: false }}
      camera={{ near: 0.5, far: 9000, fov: store.camera.frames[0]?.fovY ?? 35 }}
      // The canvas's own cursor: free look (a hotspot or a drag sets the canvas's inline one).
      style={{ position: "absolute", inset: 0, cursor: "grab" }}
      aria-hidden
      onCreated={({ gl }) => {
        gl.domElement.addEventListener("webglcontextlost", (e) => {
          e.preventDefault();
          if (mounted.current) onContextLost();
        });
      }}
    >
      <Driver
        store={store}
        adaptive={adaptive}
        budgetMs={frameBudgetMs}
        maxFps={quality.maxFps}
        climbScale={climbScale}
        climbAtRest={climbAtRest}
        onDegrade={onDegrade}
        onClimb={onClimb ?? noop}
        stats={stats}
        sets={sets}
        veiled={!(globalReady && openingReady)}
      />
      <CameraRig store={store} />
      <FreeLookInput store={store} onLookDrag={onLookDrag} />
      <Atmosphere meta={meta} ctx={ctx} store={store} />
      {shownClouds.length > 0 && <CloudPuffs meta={meta} puffs={shownClouds} store={store} overlay={overlay} anchors={anchors} />}
      <OverlayDecor objects={ctx.overlay} overlay={overlay} tier={decorTier} />
      {needsLights && <Lights meta={meta} shadows={shadows} sky={ctx.sky} />}
      <World
        global={global}
        chunks={chunks}
        store={store}
        streamer={streamer}
        post={quality.post}
        standIns={quality.standIns}
        noCards={quality.noCards}
        onGlobalReady={onGlobalReady}
      />
      {global && <Petals count={quality.post ? SECT_LOOK.petals.count : Math.round(SECT_LOOK.petals.count / 2)} store={store} sunDir={meta.sun.direction} />}
      {global && <Cranes areas={anchors} store={store} fog={fog} fogColor={meta.fog.color} />}
      {global && <Life meta={meta} store={store} fog={fog} quality={quality} />}
      {global && <Grass chunks={chunks} ctx={ctx} meta={meta} store={store} quality={quality} debug={grassDebug} />}
      {global && <WaterfallFx meta={meta} base={ctx.data.base} time={ctx.waterfallMaterial.uniforms.uTime} sets={sets} store={store} fog={fog} quality={quality} overlay={overlay} />}
      <ForgeFire set={forgeSet} store={store} />
      <FormationFires set={formationSet} store={store} meta={meta} tier={decorTier} />
      <IncenseSmoke set={mirrorSet} store={store} />
      <Hotspots
        store={store}
        ctx={ctx}
        sets={sets}
        meta={meta}
        moonFromFrame={moonFromFrame}
        onHover={onHover}
        onSelect={onSelect}
        onLore={onLore}
      />
      <IdleMotion sets={sets} store={store} />
      {flyer && flyerPath && <Flyer store={store} object={flyer} path={flyerPath} />}
      {global && <Reflections sets={sets} quality={quality} ctx={ctx} store={store} debug={debug} />}
      {quality.post ? (
        <Post quality={quality} ceiling={ceiling} overlay={overlay} meta={meta} ctx={ctx} sets={sets} store={store} />
      ) : (
        <PlainRender overlay={overlay} ctx={ctx} sets={sets} />
      )}
      {global && <WarmDecor sets={sets} overlay={overlay} post={quality.post} />}
      <UncullOnce store={store} sets={sets} />
      <FrameReport store={store} />
      {debug && (
        <DebugProbe
          el={debugEl}
          store={store}
          baked={baked}
          ctx={ctx}
          global={global}
          chunks={chunks}
          streamer={streamer}
          overlay={overlay}
          stats={stats}
          grass={grassDebug}
        />
      )}
      <ReadySignal active={globalReady && openingReady} onRendered={onRendered} store={store} />
    </Canvas>
  );
}

/** Memoized: hover and area changes re-render the page, never the canvas tree. */
export default memo(SectCanvas);
