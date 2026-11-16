import { describe, expect, it } from "vitest";
import { bandsKeepMipmaps, GPU_PACE, GPU_QUEUE, gpuPaceFor, gpuView, GRASS_SLICE, mayRunGpuStep, pickGpuJob, PREPARE_SLICE, setUploadPriority, uploadBands, URGENT_PRIORITY } from "./gpu-queue";

describe("uploadBands", () => {
  it("cuts a 4096 px RGBA map into 8 bands of 512 rows", () => {
    const b = uploadBands(4096, 4096);
    expect(b).toHaveLength(8);
    expect(b.every((x) => x.rows === 512)).toBe(true);
    expect(b.map((x) => x.y)).toEqual([0, 512, 1024, 1536, 2048, 2560, 3072, 3584]);
  });

  it("covers every row exactly once, the last band taking what is left", () => {
    for (const [w, h] of [
      [4096, 1792],
      [2048, 2048],
      [1000, 777],
      [4096, 1],
    ]) {
      const b = uploadBands(w, h);
      let next = 0;
      for (const x of b) {
        expect(x.y).toBe(next);
        expect(x.rows).toBeGreaterThan(0);
        expect(x.rows * w * 4).toBeLessThanOrEqual(Math.max(GPU_QUEUE.bandBytes, w * 4));
        next += x.rows;
      }
      expect(next).toBe(h);
    }
  });

  it("keeps a small image in one band", () => {
    expect(uploadBands(1024, 512)).toEqual([{ y: 0, rows: 512 }]);
  });

  it("takes at least one row when a row is wider than a band", () => {
    expect(uploadBands(1000, 3, 4, 100)).toEqual([
      { y: 0, rows: 1 },
      { y: 1, rows: 1 },
      { y: 2, rows: 1 },
    ]);
  });

  it("has no bands for an empty image", () => {
    expect(uploadBands(0, 10)).toEqual([]);
    expect(uploadBands(10, 0)).toEqual([]);
    expect(uploadBands(Number.NaN, 10)).toEqual([]);
  });
});

describe("bandsKeepMipmaps", () => {
  it("bands a map with both sides a power of two", () => {
    expect(bandsKeepMipmaps(4096, 4096)).toBe(true);
    expect(bandsKeepMipmaps(2048, 1024)).toBe(true);
    expect(bandsKeepMipmaps(1, 4096)).toBe(true);
  });

  it("sends a map with another side up whole (its mipmaps would differ)", () => {
    expect(bandsKeepMipmaps(2048, 1760)).toBe(false);
    expect(bandsKeepMipmaps(3072, 3072)).toBe(false);
    expect(bandsKeepMipmaps(4096, 4095)).toBe(false);
    expect(bandsKeepMipmaps(0, 4096)).toBe(false);
    expect(bandsKeepMipmaps(Number.NaN, 4096)).toBe(false);
  });
});

describe("mayRunGpuStep", () => {
  const free = { stepsThisFrame: 0, spentMs: 0, fencePending: false, linking: false, heldMs: 0 };

  describe("while the camera moves (the default pace)", () => {
    it("runs one step a frame", () => {
      expect(mayRunGpuStep(free)).toBe(true);
      expect(mayRunGpuStep({ ...free, stepsThisFrame: 1, spentMs: 0.1 })).toBe(false);
      expect(mayRunGpuStep({ ...free, stepsThisFrame: 1, spentMs: 0 }, GPU_PACE.moving)).toBe(false);
    });

    it("waits while the GPU works through the last step or a program links", () => {
      expect(mayRunGpuStep({ ...free, fencePending: true, heldMs: 10 })).toBe(false);
      expect(mayRunGpuStep({ ...free, linking: true, heldMs: 10 })).toBe(false);
    });

    it("goes on anyway once held too long, still one a frame", () => {
      expect(mayRunGpuStep({ ...free, linking: true, heldMs: GPU_QUEUE.maxHoldMs })).toBe(true);
      expect(mayRunGpuStep({ ...free, fencePending: true, heldMs: 99 }, GPU_PACE.moving, 100)).toBe(false);
      expect(mayRunGpuStep({ ...free, fencePending: true, heldMs: 100 }, GPU_PACE.moving, 100)).toBe(true);
      expect(mayRunGpuStep({ ...free, stepsThisFrame: 1, linking: true, heldMs: 1e9 })).toBe(false);
    });
  });

  describe("with the camera at rest", () => {
    const rest = GPU_PACE.resting;

    it("runs steps while the frame's share is not used up", () => {
      expect(rest.budgetMs).toBeGreaterThanOrEqual(6);
      expect(rest.budgetMs).toBeLessThanOrEqual(8);
      expect(mayRunGpuStep({ ...free, stepsThisFrame: 3, spentMs: rest.budgetMs - 0.5 }, rest)).toBe(true);
      expect(mayRunGpuStep({ ...free, stepsThisFrame: 4, spentMs: rest.budgetMs }, rest)).toBe(false);
    });

    it("always runs a frame's first step, however long the last one took", () => {
      expect(mayRunGpuStep({ ...free, spentMs: 50 }, rest)).toBe(true);
    });

    it("does not hold for a linking program, but still for the GPU's last frame of steps", () => {
      expect(mayRunGpuStep({ ...free, linking: true, heldMs: 0 }, rest)).toBe(true);
      expect(mayRunGpuStep({ ...free, fencePending: true, heldMs: 10 }, rest)).toBe(false);
      expect(mayRunGpuStep({ ...free, fencePending: true, heldMs: GPU_QUEUE.maxHoldMs }, rest)).toBe(true);
    });
  });

  describe("behind the loading screen or the ink", () => {
    const veil = GPU_PACE.veiled;

    it("runs flat out: most of the frame, holding for neither the fence nor a link", () => {
      expect(veil.budgetMs).toBeGreaterThan(GPU_PACE.resting.budgetMs);
      expect(mayRunGpuStep({ ...free, fencePending: true, linking: true }, veil)).toBe(true);
      expect(mayRunGpuStep({ ...free, stepsThisFrame: 20, spentMs: veil.budgetMs - 1, fencePending: true, linking: true }, veil)).toBe(true);
      expect(mayRunGpuStep({ ...free, stepsThisFrame: 21, spentMs: veil.budgetMs }, veil)).toBe(false);
    });
  });

  it("paces itself harder the less of the scene shows", () => {
    expect(GPU_PACE.moving.budgetMs).toBeLessThan(GPU_PACE.resting.budgetMs);
    expect(GPU_PACE.resting.budgetMs).toBeLessThan(GPU_PACE.veiled.budgetMs);
  });
});

describe("main-thread slices by view (PREPARE_SLICE, GRASS_SLICE)", () => {
  it("keep their small slices while the scene shows, at rest too, and take most of a frame behind the veil", () => {
    expect(PREPARE_SLICE.moving).toBe(5);
    expect(PREPARE_SLICE.resting).toBe(5);
    expect(GRASS_SLICE.moving).toBe(6);
    expect(GRASS_SLICE.resting).toBe(6);
    expect(PREPARE_SLICE.veiled).toBeGreaterThan(3 * PREPARE_SLICE.resting);
    expect(PREPARE_SLICE.veiled).toBeLessThan(1000 / 30);
    expect(GRASS_SLICE.veiled).toBe(PREPARE_SLICE.veiled);
  });
});

describe("gpuPaceFor (the pace of one job)", () => {
  it("at rest, gives the larger share only to work the visitor waits to see", () => {
    const placeHere = setUploadPriority({ global: false, headed: true, inView: true });
    const placeAhead = setUploadPriority({ global: false, headed: false, inView: false });
    expect(placeHere).toBeGreaterThanOrEqual(URGENT_PRIORITY);
    expect(placeAhead).toBeLessThan(URGENT_PRIORITY);
    expect(gpuPaceFor("resting", placeHere)).toEqual(GPU_PACE.resting);
    // An area loaded ahead, or live light's maps for the next stop (0), go a step a frame.
    expect(gpuPaceFor("resting", placeAhead)).toEqual(GPU_PACE.moving);
    expect(gpuPaceFor("resting", 0)).toEqual(GPU_PACE.moving);
    // Live light's start at the stop (2) is waited for.
    expect(gpuPaceFor("resting", 2)).toEqual(GPU_PACE.resting);
  });

  it("is the view's own pace while moving or covered, whatever the job", () => {
    for (const p of [0, 1, 2, 3, 4]) {
      expect(gpuPaceFor("moving", p)).toEqual(GPU_PACE.moving);
      expect(gpuPaceFor("veiled", p)).toEqual(GPU_PACE.veiled);
    }
  });
});

describe("gpuView", () => {
  it("is veiled whenever the scene is covered, moving or not", () => {
    expect(gpuView({ veiled: true, moving: false })).toBe("veiled");
    expect(gpuView({ veiled: true, moving: true })).toBe("veiled");
  });

  it("is moving while the camera moves, else at rest", () => {
    expect(gpuView({ veiled: false, moving: true })).toBe("moving");
    expect(gpuView({ veiled: false, moving: false })).toBe("resting");
  });
});

describe("setUploadPriority", () => {
  it("puts the global set first, then where the camera is heading, then what is on screen, then what is ahead", () => {
    const p = (global: boolean, headed: boolean, inView: boolean) => setUploadPriority({ global, headed, inView });
    expect(p(true, false, false)).toBeGreaterThan(p(false, true, true));
    expect(p(false, true, false)).toBeGreaterThan(p(false, false, true));
    expect(p(false, false, true)).toBeGreaterThan(p(false, false, false));
    expect(p(false, true, true)).toBe(p(false, true, false));
  });

  it("puts a place's own models before its live light's start (priority 2) and its maps loaded ahead (0)", () => {
    expect(setUploadPriority({ global: false, headed: true, inView: true })).toBeGreaterThan(2);
    expect(setUploadPriority({ global: false, headed: false, inView: false })).toBeGreaterThan(0);
  });
});

describe("pickGpuJob", () => {
  it("takes the highest priority, then the oldest", () => {
    expect(
      pickGpuJob([
        { priority: 1, seq: 0, waiting: false },
        { priority: 2, seq: 3, waiting: false },
        { priority: 2, seq: 1, waiting: false },
      ]),
    ).toBe(2);
  });

  it("skips jobs that wait, so the others go meanwhile", () => {
    expect(
      pickGpuJob([
        { priority: 5, seq: 0, waiting: true },
        { priority: 0, seq: 1, waiting: false },
      ]),
    ).toBe(1);
  });

  it("says -1 when nothing may go", () => {
    expect(pickGpuJob([])).toBe(-1);
    expect(pickGpuJob([{ priority: 1, seq: 0, waiting: true }])).toBe(-1);
  });
});
