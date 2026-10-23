import { describe, expect, it } from "vitest";
import { glslFloat } from "./glsl";
import { HEART_MIRROR, heartMirrorGlsl, heartMirrorLayers, heartMirrorTop, latheSlices, MIRROR_PART, mirrorSpan, profileRadius } from "./heart-mirror";

const at = (r: number, deg: number): [number, number] => [r * Math.cos((deg * Math.PI) / 180), r * Math.sin((deg * Math.PI) / 180)];
/** A point on the ring `along` metres clockwise of trigram k's centre (k = 0 at the top). */
const onTrigram = (k: number, r: number, along = 0): [number, number] => at(r, 90 - k * 22.5 - (along / r) * (180 / Math.PI));

describe("the Heart-Mirror's layout (mirror.py, MIRROR_R 3.5)", () => {
  const R = 3.5;
  const width = 0.55;
  const radius = R - 0.62;

  it("takes its sizes from the Blender build", () => {
    expect(HEART_MIRROR.face).toBeCloseTo(R - 0.12, 9);
    expect(HEART_MIRROR.rim).toEqual([R - 0.2, R + 0.3]);
    expect(HEART_MIRROR.arms.radius).toBeCloseTo(R + 0.62, 9);
    expect(HEART_MIRROR.crest.base).toBeCloseTo(R + 0.2, 9);
    expect(HEART_MIRROR.cradle.base).toBeCloseTo(-(0.4 + R), 9);
    // props.py rune_ring(R - 0.62, 0.55, "trigram"): the band, its bars and the trigram count.
    const R2 = HEART_MIRROR.runes;
    expect(R2.ring[0]).toBeCloseTo(radius - width / 2, 9);
    expect(R2.ring[1]).toBeCloseTo(radius + width / 2, 9);
    expect(R2.count).toBe(8 * Math.max(1, Math.round((2 * Math.PI * radius) / (8 * width * 2.4))));
    const barT = 0.13 * width;
    const gap = 0.07 * width;
    R2.bars.forEach(([r0, r1], i) => {
      const rr0 = radius - 1.5 * barT - gap + i * (barT + gap);
      expect(r0).toBeCloseTo(rr0, 3);
      expect(r1).toBeCloseTo(rr0 + barT, 3);
    });
    expect(R2.half).toBeCloseTo((0.55 * width) / 2 / radius, 3);
    expect(R2.gap).toBeCloseTo((0.09 * width) / radius, 3);
    // Fu Xi order from qian (props.py BAGUA_ORDER), lines bottom first.
    const lines = { qian: [1, 1, 1], xun: [0, 1, 1], kan: [0, 1, 0], gen: [0, 0, 1], kun: [0, 0, 0], zhen: [1, 0, 0], li: [1, 0, 1], dui: [1, 1, 0] };
    const order = ["qian", "xun", "kan", "gen", "kun", "zhen", "li", "dui"] as const;
    expect(R2.order).toEqual(order.map((n) => lines[n][0] + 2 * lines[n][1] + 4 * lines[n][2]));
  });

  it("puts the face in the middle, the gilt rim round it, the red arms outside, the crest and pearls on top", () => {
    expect(heartMirrorTop([0, 0])).toBe(MIRROR_PART.face);
    expect(heartMirrorTop([0, 1.5])).toBe(MIRROR_PART.face);
    for (const deg of [0, 45, 135, 180, 270, 300]) expect(heartMirrorTop(at(3.55, deg)), `rim ${deg}`).toBe(MIRROR_PART.gold);
    for (const deg of [-60, 0, 40, 120, 180, 230]) expect(heartMirrorTop(at(4.12, deg)), `arm ${deg}`).toBe(MIRROR_PART.lacquer);
    // The arms curl out toward the tip and stop short of the top and the bottom.
    expect(heartMirrorTop(at(4.26, 58))).toBe(MIRROR_PART.lacquer);
    expect(heartMirrorTop(at(4.12, 58))).toBe(MIRROR_PART.lacquer);
    expect(heartMirrorTop(at(4.12, -90))).toBeNull();
    expect(heartMirrorTop(at(4.12, 80))).toBeNull();
    // Crest on top (widest 0.45 m up), the pearls at the arms' tips, nothing beyond.
    expect(heartMirrorTop([0, 4.15])).toBe(MIRROR_PART.gold);
    expect(heartMirrorTop([0.7, 4.15])).toBe(MIRROR_PART.gold);
    expect(heartMirrorTop([0.7, 5.2])).toBeNull();
    expect(heartMirrorTop([0, 5.6])).toBeNull();
    expect(heartMirrorTop(at(4.42, 64))).toBe(MIRROR_PART.gold);
    expect(heartMirrorTop(at(4.42, 116))).toBe(MIRROR_PART.gold);
    expect(heartMirrorTop([6, 6])).toBeNull();
    expect(heartMirrorLayers([4.5, 4.5], 0.1, 0)).toEqual([]);
  });

  it("lays the trigrams round the ring from qian at the top, yin bars broken in the middle", () => {
    const bar = (i: number) => (HEART_MIRROR.runes.bars[i][0] + HEART_MIRROR.runes.bars[i][1]) / 2;
    // qian (k 0 and 8): three solid bars, centre included.
    for (const k of [0, 8]) for (let i = 0; i < 3; i++) expect(heartMirrorTop(onTrigram(k, bar(i))), `qian ${k} ${i}`).toBe(MIRROR_PART.runes);
    // xun (k 1): bottom line (innermost) broken, the two above solid.
    expect(heartMirrorTop(onTrigram(1, bar(0)))).toBe(MIRROR_PART.face);
    expect(heartMirrorTop(onTrigram(1, bar(0), 0.1))).toBe(MIRROR_PART.runes);
    expect(heartMirrorTop(onTrigram(1, bar(0), -0.1))).toBe(MIRROR_PART.runes);
    expect(heartMirrorTop(onTrigram(1, bar(1)))).toBe(MIRROR_PART.runes);
    expect(heartMirrorTop(onTrigram(1, bar(2)))).toBe(MIRROR_PART.runes);
    // kun (k 4, at the right): all three broken.
    for (let i = 0; i < 3; i++) {
      expect(heartMirrorTop(onTrigram(4, bar(i)))).toBe(MIRROR_PART.face);
      expect(heartMirrorTop(onTrigram(4, bar(i), 0.1))).toBe(MIRROR_PART.runes);
    }
    // Between trigrams the face shows (the faint framing lines and diamonds never reach half).
    expect(heartMirrorTop(onTrigram(0, 2.88, 0.4))).toBe(MIRROR_PART.face);
    expect(heartMirrorTop(onTrigram(2, HEART_MIRROR.runes.ring[0] + 0.01, 0.5))).toBe(MIRROR_PART.face);
  });

  it("averages the fine bars over the footprint instead of aliasing them", () => {
    const [r0, r1] = HEART_MIRROR.runes.bars[1];
    expect(mirrorSpan((r0 + r1) / 2, r0, r1, 0.001)).toBeCloseTo(1, 9);
    expect(mirrorSpan((r0 + r1) / 2, r0, r1, 0.2)).toBeCloseTo((r1 - r0) / 0.4, 6);
    expect(mirrorSpan(5, r0, r1, 0.2)).toBe(0);
    // A trigram's light seen from far away: about its bars' share of the footprint, not all or nothing.
    const runes = (w: number) => heartMirrorLayers(onTrigram(0, 2.88), w, 0).find((l) => l.part === MIRROR_PART.runes)?.cover ?? 0;
    expect(runes(0.001)).toBeCloseTo(1, 9);
    expect(runes(0.3)).toBeGreaterThan(0.2);
    expect(runes(0.3)).toBeLessThan(0.8);
  });

  it("raises the cradle's lip over the bottom of the face when seen from below, as the pond sees it", () => {
    expect(heartMirrorTop([0, -3.5])).toBe(MIRROR_PART.gold);
    expect(heartMirrorTop([0, -2.88])).toBe(MIRROR_PART.runes);
    expect(heartMirrorTop([0, -2.6], 0.001, 0)).toBe(MIRROR_PART.face);
    expect(heartMirrorTop([0, -2.6], 0.001, 0.45)).toBe(MIRROR_PART.gold);
    // From below the cup leans down (darker in the sun from above).
    const cup = heartMirrorLayers([1, -3.2], 0.001, 0.35).at(-1)!;
    expect(cup.part).toBe(MIRROR_PART.gold);
    expect(cup.lean[1]).toBeLessThan(0);
    expect(cup.lean[0]).toBeGreaterThan(0);
  });

  it("stands the cradle upright under the leaning face: its near lip meets the face where the ray through it does", () => {
    const C = HEART_MIRROR.cradle;
    const t = (C.tilt * Math.PI) / 180;
    // The face's frame (x right, y up the face, z out of it): the world's up, and level ahead.
    const up = [0, Math.cos(t), Math.sin(t)];
    const ahead = [0, -Math.sin(t), Math.cos(t)];
    const [rho, h] = C.profile[C.profile.length - 1];
    // The pond's views at the Heart-Mirror's stop and on the approach (k up, kx sideways).
    for (const [k, kx] of [
      [0.42, -0.21],
      [0.36, -0.11],
      [0.29, 0.14],
    ]) {
      // The lip's front, on the axis through the disc's centre behind the face, and where its ray meets the plane.
      const p = [0, 1, 2].map((i) => (i === 2 ? -C.axis : 0) + (C.base + h) * up[i] + rho * ahead[i]);
      const q = [p[0] + p[2] * kx, p[1] + p[2] * k];
      expect(heartMirrorTop([q[0], q[1] - 0.06], 0.001, k, false, kx), `k ${k}`).toBe(MIRROR_PART.gold);
      expect(heartMirrorTop([q[0], q[1] + 0.06], 0.001, k, false, kx), `k ${k}`).not.toBe(MIRROR_PART.gold);
    }
    // At the stop it hides the bottom trigram, but its neighbour's inner bars show, as in High's reflection.
    const [b0, b1] = HEART_MIRROR.runes.bars[0];
    expect(heartMirrorTop(onTrigram(8, (b0 + b1) / 2), 0.001, 0.42, false, -0.21)).toBe(MIRROR_PART.gold);
    expect(heartMirrorTop(onTrigram(7, (b0 + b1) / 2), 0.001, 0.42, false, -0.21)).toBe(MIRROR_PART.runes);
    // Seen from level or above, its far side stays behind the face.
    const level = heartMirrorLayers([0, -2.88], 0.001, 0);
    expect(level[0].part).toBe(MIRROR_PART.gold);
    expect(level.at(-1)!.part).toBe(MIRROR_PART.runes);
    expect(heartMirrorTop([0, -2.88], 0.001, -0.2)).toBe(MIRROR_PART.runes);
  });

  it("shows the bronze back and no runes from behind", () => {
    expect(heartMirrorTop([0, 0], 0.001, 0, true)).toBe(MIRROR_PART.bronze);
    expect(heartMirrorTop(onTrigram(0, 2.88), 0.001, 0, true)).toBe(MIRROR_PART.bronze);
    expect(heartMirrorTop(at(4.12, 0), 0.001, 0, true)).toBe(MIRROR_PART.lacquer);
  });

  it("leans the tube and rim surfaces outward at their outer edge and inward at their inner edge", () => {
    const arm = (r: number) => heartMirrorLayers(at(r, 0), 0.001, 0).find((l) => l.part === MIRROR_PART.lacquer)!;
    expect(arm(4.12 + 0.2).lean[0]).toBeGreaterThan(0.5);
    expect(arm(4.12 - 0.2).lean[0]).toBeLessThan(-0.5);
    expect(Math.abs(arm(4.12).lean[0])).toBeLessThan(0.05);
    const left = heartMirrorLayers(at(4.32, 180), 0.001, 0).find((l) => l.part === MIRROR_PART.lacquer)!;
    expect(left.lean[0]).toBeLessThan(-0.5);
    for (const l of heartMirrorLayers(at(3.79, 30), 0.001, 0)) expect(Math.hypot(...l.lean)).toBeLessThanOrEqual(0.95 + 1e-9);
  });

  it("slices its lathes no more than a step apart and reads their profiles straight between points", () => {
    const s = latheSlices(HEART_MIRROR.cradle.profile);
    expect(s[0]).toEqual([0.95, 0]);
    expect(s.at(-1)).toEqual([2.05, 0.86]);
    for (let i = 1; i < s.length; i++) expect(s[i][1] - s[i - 1][1]).toBeLessThanOrEqual(HEART_MIRROR.slice + 1e-9);
    expect(profileRadius(HEART_MIRROR.crest.profile, 0.45)).toBeCloseTo(0.75, 9);
    expect(profileRadius(HEART_MIRROR.crest.profile, 0.275)).toBeCloseTo(0.65, 9);
    expect(profileRadius(HEART_MIRROR.crest.profile, -0.1)).toBe(0);
    expect(profileRadius(HEART_MIRROR.crest.profile, 1.8)).toBe(0);
  });

  it("puts the same layout into the shader", () => {
    const g = heartMirrorGlsl();
    expect(g).toContain("struct SectMirrorView");
    expect(g).toContain("vec3 sectMirrorShade( int part, vec2 q, vec2 lean, SectMirrorView m );");
    expect(g).toContain("vec4 sectHeartMirror( vec2 q, float w, float k, SectMirrorView m )");
    expect(g).toContain(`#define SECT_HEART_FACE ${glslFloat(HEART_MIRROR.face)}`);
    expect(g).toContain(`int[8]( ${HEART_MIRROR.runes.order.join(", ")} )`);
    for (const x of [HEART_MIRROR.rim[0], HEART_MIRROR.rim[1], HEART_MIRROR.arms.radius, HEART_MIRROR.arms.tip.radius, HEART_MIRROR.pearls.radius, HEART_MIRROR.runes.faint, HEART_MIRROR.cradle.base, HEART_MIRROR.cradle.axis, HEART_MIRROR.behind, HEART_MIRROR.bound]) {
      expect(g, String(x)).toContain(glslFloat(x));
    }
    const slices = latheSlices(HEART_MIRROR.cradle.profile);
    expect(g).toContain(`float[${slices.length}]( ${slices.map((s) => glslFloat(s[0])).join(", ")} )`);
    // Composited back to front: crest, arms, pearls, the cradle behind the face's plane, face, runes, rim, the cradle's near side.
    const order = [
      `${MIRROR_PART.gold}, q, sectMirrorLean( vec2( q.x`,
      `( ${MIRROR_PART.lacquer}, q`,
      `( ${MIRROR_PART.gold}, q, sectMirrorLean( vec2( sx`,
      "sectMirrorCradle( q, w, k, m, cupLean, cupBehind )",
      "sectMirrorOver( acc, cupCol, cupBehind )",
      `${MIRROR_PART.face}, q`,
      `( ${MIRROR_PART.runes}, q`,
      `( ${MIRROR_PART.gold}, q, sectMirrorLean( q /`,
      "sectMirrorOver( acc, cupCol, cup )",
    ];
    let last = g.indexOf("vec4 sectHeartMirror(");
    for (const s of order) {
      const i = g.indexOf(s, last);
      expect(i, s).toBeGreaterThan(last);
      last = i;
    }
  });
});
