import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { sampleCamera } from "./camera-path";
import { blenderQuatToThree, blenderSizeToThree, blenderToThree, projectPoint, threeToBlender } from "./coords";
import { parseCameraData, parseMeta } from "./parse";
import type { Quat } from "./types";

describe("axis conversion", () => {
  it("maps Blender Z-up to three Y-up", () => {
    expect(blenderToThree([1, 2, 3])).toEqual([1, 3, -2]);
    expect(threeToBlender(blenderToThree([1, 2, 3]))).toEqual([1, 2, 3]);
    expect(blenderSizeToThree([4, 5, 6])).toEqual([4, 6, 5]);
  });

  it("turns Blender's default camera (looking down -Z) into one looking down three -Y", () => {
    // Blender camera with identity rotation looks straight down (-Z), which is three -Y.
    const q = blenderQuatToThree([0, 0, 0, 1]);
    const p = projectPoint([0, 0, 0], q, 40, 1, [0, -10, 0]);
    expect(p.depth).toBeCloseTo(10, 9);
    expect(p.ndc[0]).toBeCloseTo(0, 9);
    expect(p.ndc[1]).toBeCloseTo(0, 9);
  });

  it("a Blender camera pitched 90 degrees up looks along Blender +Y (three -Z)", () => {
    const h = Math.PI / 4;
    const bq: Quat = [Math.sin(h), 0, 0, Math.cos(h)];
    const p = projectPoint([0, 0, 0], blenderQuatToThree(bq), 40, 1, [0, 0, -10]);
    expect(p.depth).toBeCloseTo(10, 9);
  });
});

describe("projectPoint", () => {
  it("puts a point on the right edge at half the horizontal FOV", () => {
    const fovY = 40;
    const aspect = 2;
    const t = Math.tan((fovY * Math.PI) / 360) * aspect;
    const p = projectPoint([0, 0, 0], [0, 0, 0, 1], fovY, aspect, [t * 10, 0, -10]);
    expect(p.ndc[0]).toBeCloseTo(1, 9);
  });
});

const proto = join(process.cwd(), "public/sect/proto");
const haveProto = existsSync(join(proto, "camera.json")) && existsSync(join(proto, "meta.json"));

describe.skipIf(!haveProto)("exported camera frames the hotspots like the Blender renders", () => {
  const cam = haveProto ? parseCameraData(JSON.parse(readFileSync(join(proto, "camera.json"), "utf8"))) : null;
  const meta = haveProto ? parseMeta(JSON.parse(readFileSync(join(proto, "meta.json"), "utf8"))) : null;

  it("gate at frame 93 sits near the centre, about 48 m away", () => {
    const s = sampleCamera(cam!.frames, 93);
    const gate = meta!.hotspots.find((h) => h.id === "gate")!;
    const p = projectPoint(s.p, s.q, s.fovY, cam!.refAspect, gate.center);
    expect(p.depth).toBeCloseTo(47.8, 0);
    expect(p.ndc[0]).toBeCloseTo(-0.083, 2);
    expect(p.ndc[1]).toBeCloseTo(-0.066, 2);
  });

  it("mirror at frame 217 sits on the left, about 69 m away", () => {
    const s = sampleCamera(cam!.frames, 217);
    const mirror = meta!.hotspots.find((h) => h.id === "mirror")!;
    const p = projectPoint(s.p, s.q, s.fovY, cam!.refAspect, mirror.center);
    // 68.9 m along the view axis (73.3 m in a straight line)
    expect(p.depth).toBeCloseTo(68.9, 0);
    expect(p.ndc[0]).toBeCloseTo(-0.641, 2);
    expect(p.ndc[1]).toBeCloseTo(-0.106, 2);
  });

  it("the gate is fully in view at startFrame", () => {
    const s = sampleCamera(cam!.frames, cam!.startFrame);
    const gate = meta!.hotspots.find((h) => h.id === "gate")!;
    for (const dx of [-0.5, 0.5]) {
      for (const dy of [-0.5, 0.5]) {
        const corner: [number, number, number] = [
          gate.center[0] + dx * gate.size[0],
          gate.center[1] + dy * gate.size[1],
          gate.center[2],
        ];
        const p = projectPoint(s.p, s.q, s.fovY, cam!.refAspect, corner);
        expect(p.depth).toBeGreaterThan(0);
        expect(Math.abs(p.ndc[0])).toBeLessThan(1);
        expect(Math.abs(p.ndc[1])).toBeLessThan(1);
      }
    }
  });
});
