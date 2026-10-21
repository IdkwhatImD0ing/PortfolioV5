import { Group, Mesh, Scene } from "three";
import { describe, expect, it } from "vitest";
import { isolateForReflection } from "./isolate";

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
