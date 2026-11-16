import { Group, Mesh, Scene } from "three";
import { describe, expect, it } from "vitest";
import { isolateForReflection, reflectView, type ReflectSet } from "./isolate";

describe("reflection isolation", () => {
  const build = () => {
    const scene = new Scene();
    const named = (name: string, visible = true) => {
      const o = new Group();
      o.name = name;
      o.visible = visible;
      scene.add(o);
      return o;
    };
    const set = named("sect.mirror");
    const other = named("sect.forge");
    const proxy = new Mesh();
    proxy.visible = false;
    const global = named("sect.global");
    global.add(proxy);
    const o = {
      set,
      other,
      global,
      proxy,
      sky: named("sect.sky"),
      grass: named("sect.grass"),
      petals: named("sect.petals"),
      hiddenFx: named("sect.incense", false),
      face: new Mesh(),
    };
    set.add(o.face);
    return { scene, ...o };
  };

  it("keeps the given roots, the sky and (when asked) the grass; hides the rest, then puts it all back", () => {
    const s = build();
    const restore = isolateForReflection(s.scene, { roots: new Set([s.set, s.global]), grass: false, show: [s.proxy], hide: [s.face] });
    expect(s.set.visible).toBe(true);
    expect(s.global.visible).toBe(true);
    expect(s.sky.visible).toBe(true);
    expect(s.other.visible).toBe(false);
    expect(s.grass.visible).toBe(false);
    expect(s.petals.visible).toBe(false);
    expect(s.face.visible).toBe(false);
    expect(s.proxy.visible).toBe(true);
    restore();
    expect([s.other, s.grass, s.petals, s.face].every((x) => x.visible)).toBe(true);
    expect(s.proxy.visible).toBe(false);
    expect(s.hiddenFx.visible).toBe(false);
  });

  it("keeps the grass for a pass that wants it", () => {
    const s = build();
    const restore = isolateForReflection(s.scene, { roots: new Set([s.set]), grass: true });
    expect(s.grass.visible).toBe(true);
    expect(s.global.visible).toBe(false);
    restore();
    expect(s.global.visible).toBe(true);
  });
});

describe("what a reflection pass draws (reflectView)", () => {
  /** The global set with a stand-in per area, the mirror's area (with the pond), and the forge and arena. */
  const world = () => {
    const scene = new Scene();
    const root = (name: string) => {
      const g = new Group();
      g.name = name;
      scene.add(g);
      return g;
    };
    const pond = {};
    const proxy = (area: string) => {
      const m = new Mesh();
      m.name = `proxy.${area}`;
      return m;
    };
    const proxies = new Map([
      ["mirror", [proxy("mirror")]],
      ["forge", [proxy("forge")]],
      ["arena", [proxy("arena")]],
    ]);
    const globalRoot = root("sect.global");
    for (const list of proxies.values()) for (const m of list) globalRoot.add(m);
    const set = (id: string, need: [number, number] | null, scenes: Group[], o: { pond?: object; drawn?: boolean; far?: boolean } = {}): ReflectSet => ({
      id,
      need,
      scenes,
      proxies: id === "global" ? proxies : new Map(),
      pond: o.pond ?? null,
      drawn: o.drawn ?? false,
      far: o.far ?? false,
    });
    const global = set("global", null, [globalRoot], { drawn: true });
    const mirror = set("mirror", [140, 300], [root("sect.mirror")], { pond, drawn: true });
    const forge = set("forge", [290, 420], [root("sect.forge")]);
    const arena = set("arena", [400, 600], [root("sect.arena")]);
    return { scene, pond, proxies, global, mirror, forge, arena, sets: [global, mirror, forge, arena] };
  };

  /** The objects a pass would draw at the scene's top level and among the stand-ins, by name. */
  const drawnBy = (scene: Scene, view: ReturnType<typeof reflectView>) => {
    const restore = isolateForReflection(scene, view);
    const top = scene.children.filter((o) => o.visible).map((o) => o.name);
    const stands = scene.children.flatMap((o) => o.children).filter((o) => o.visible && o.name.startsWith("proxy.")).map((o) => o.name);
    restore();
    return { top, stands };
  };

  /** As the page shows the sets on screen (scene.tsx World): scenes when drawn or far, a stand-in otherwise. */
  const onScreen = (w: ReturnType<typeof world>) => {
    for (const s of w.sets) {
      if (s.need === null) continue;
      for (const r of s.scenes) r.visible = s.drawn || s.far;
      for (const m of w.proxies.get(s.id) ?? []) m.visible = !(s.drawn || s.far);
    }
  };

  it("a far area is drawn by its stand-in in both passes, exactly as before it was drawn in full", () => {
    for (const standIns of [false, true]) {
      // Before far areas: the forge and the arena held but outside their ranges, their stand-ins shown.
      const before = world();
      onScreen(before);
      const was = drawnBy(before.scene, reflectView(before.sets, before.pond, { grass: false, standIns }));
      // Now: both shown in full as far scenery.
      const after = world();
      after.forge.far = true;
      after.arena.far = true;
      onScreen(after);
      const view = reflectView(after.sets, after.pond, { grass: false, standIns });
      expect(view.roots.has(after.forge.scenes[0]), `standIns ${standIns}`).toBe(false);
      const now = drawnBy(after.scene, view);
      expect(now, `standIns ${standIns}`).toEqual(was);
      expect(now.stands.sort(), `standIns ${standIns}`).toEqual(["proxy.arena", "proxy.forge"]);
      // And the screen is as it was after the pass.
      expect(after.forge.scenes[0].visible).toBe(true);
      expect(after.proxies.get("forge")![0].visible).toBe(false);
    }
  });

  it("drawn areas as before: as they are, or as stand-ins for a pass that wants them; the pond's own area always as it is", () => {
    const w = world();
    w.forge.drawn = true;
    onScreen(w);
    const full = reflectView(w.sets, w.pond, { grass: true, standIns: false });
    expect([...full.roots]).toEqual([w.global.scenes[0], w.mirror.scenes[0], w.forge.scenes[0]]);
    expect(full.show).toEqual([]);
    expect(full.grass).toBe(true);
    const lean = reflectView(w.sets, w.pond, { grass: false, standIns: true });
    expect([...lean.roots]).toEqual([w.global.scenes[0], w.mirror.scenes[0]]);
    expect(lean.show).toEqual(w.proxies.get("forge"));
  });
});
