"""Blender's view transform as a lookup table for the page's live light (docs/sect/live-gate.md).

    python tools/sect_view_lut.py [--config <config.ocio>] [--size 48] [--check]

The bake writes its atlases through Blender's colour management: the "AgX" view with the "AgX - Punchy" look on
an sRGB display. Live light has to end in the same colours, and the page's own AgX code (three.js's) is a
different curve: fine for greys, far too saturated on lacquer red. This reads Blender's own colour config with
the OpenColorIO library (pip install opencolorio; no Blender is run) and writes the whole transform, scene-linear
Rec.709 in and display sRGB out, as a size^3 table:

    client/public/sect/full/live/view_agx_punchy.bin    size^3 x 4 bytes (r, g, b, 255), red fastest

The table's axes are log2 of the linear value, from 2^LO to 2^HI on each channel (client/src/lib/sect/live.ts
LIVE_VIEW holds the same three numbers). Exposure is not in it: the page multiplies before the lookup.

--check prints how far the table (read back with trilinear filtering, as the GPU does) is from the exact
transform on random colours, and what the page's old curve gave for a few of them.
"""
import argparse
import os
import sys

import numpy as np
import PyOpenColorIO as ocio

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.normpath(os.path.join(ROOT, "..", "..", "client", "public", "sect", "full", "live", "view_agx_punchy.bin"))
CONFIG = "C:/Program Files/Blender Foundation/Blender 5.2/5.2/datafiles/colormanagement/config.ocio"
LO, HI = -12.47393, 6.5            # stops: the table's ends on each axis (2^6.5 is about 90 times scene white)
DISPLAY, VIEW, LOOK = "sRGB", "AgX", "AgX - Punchy"


def processor(path):
    cfg = ocio.Config.CreateFromFile(path)
    src = cfg.getColorSpace(ocio.ROLE_SCENE_LINEAR).getName()
    group = ocio.GroupTransform()
    # As Blender does it: the look in scene-linear, then the display's view.
    group.appendTransform(ocio.LookTransform(src=src, dst=src, looks=LOOK))
    group.appendTransform(ocio.DisplayViewTransform(src=src, display=DISPLAY, view=VIEW))
    return cfg.getProcessor(group).getDefaultCPUProcessor(), src


def apply(cpu, rgb):
    px = np.ascontiguousarray(rgb, np.float32).reshape(-1, 3).copy()
    cpu.applyRGB(px)
    return px


def srgb_decode(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def table(cpu, n):
    t = np.linspace(0.0, 1.0, n, dtype=np.float64)
    lin = np.power(2.0, LO + t * (HI - LO))
    b, g, r = np.meshgrid(lin, lin, lin, indexing="ij")           # red fastest
    out = apply(cpu, np.stack([r, g, b], axis=-1))
    return np.clip(out, 0.0, 1.0).reshape(n, n, n, 3)


def lookup(tab8, rgb):
    """Trilinear, on sRGB-decoded bytes (the GPU decodes an sRGB texture before it filters); linear display out."""
    n = tab8.shape[0]
    lin = srgb_decode(tab8.astype(np.float64) / 255.0)
    t = np.clip((np.log2(np.maximum(rgb, 2.0 ** LO)) - LO) / (HI - LO), 0.0, 1.0) * (n - 1)
    i0 = np.minimum(np.floor(t).astype(int), n - 2)
    f = t - i0
    out = np.zeros_like(rgb, dtype=np.float64)
    for dz in (0, 1):
        for dy in (0, 1):
            for dx in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out += w[:, None] * lin[i0[:, 2] + dz, i0[:, 1] + dy, i0[:, 0] + dx]
    return out


def old_curve(c):
    """The page's AgX Punchy (client/src/lib/sect/glsl.ts AGX_PUNCHY_GLSL), linear in and out, for --check."""
    to2020 = np.array([[0.6274, 0.3293, 0.0433], [0.0691, 0.9195, 0.0113], [0.0164, 0.0880, 0.8956]])
    to709 = np.array([[1.6605, -0.5876, -0.0728], [-0.1246, 1.1329, -0.0083], [-0.0182, -0.1006, 1.1187]])
    inset = np.array([[0.856627153315983, 0.0951212405381588, 0.0482516061458583],
                      [0.137318972929847, 0.761241990602591, 0.101439036467562],
                      [0.11189821299995, 0.0767994186031903, 0.811302368396859]])
    outset = np.array([[1.1271005818144368, -0.11060664309660323, -0.016493938717834573],
                       [-0.1413297634984383, 1.157823702216272, -0.016493938717834257],
                       [-0.14132976349843826, -0.11060664309660294, 1.2519364065950405]])
    x = c @ to2020.T @ inset.T
    x = np.clip((np.log2(np.maximum(x, 1e-10)) + 12.47393) / 16.499999, 0.0, 1.0)
    x2, x4 = x * x, x ** 4
    x = 15.5 * x4 * x2 - 40.14 * x4 * x + 31.96 * x4 - 6.868 * x2 * x + 0.4298 * x2 + 0.1191 * x - 0.00232
    luma = x @ np.array([0.2126, 0.7152, 0.0722])
    x = np.maximum(x, 0.0) ** 1.35
    x = luma[:, None] + 1.4 * (x - luma[:, None])
    x = np.maximum(x @ outset.T, 0.0) ** 2.2
    return np.clip(x @ to709.T, 0.0, 1.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=CONFIG)
    ap.add_argument("--size", type=int, default=48)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if not os.path.isfile(a.config):
        sys.exit("no colour config at %s" % a.config)
    cpu, src = processor(a.config)
    tab = table(cpu, a.size)
    tab8 = np.round(tab * 255.0).astype(np.uint8)
    rgba = np.concatenate([tab8, np.full(tab8.shape[:3] + (1,), 255, np.uint8)], axis=-1)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "wb") as f:
        f.write(rgba.tobytes())
    print("%s -> %s / %s / %s: %d^3, %d bytes -> %s" % (src, DISPLAY, VIEW, LOOK, a.size, rgba.size, a.out))
    if a.check:
        rng = np.random.default_rng(7)
        # colours as the page meets them: a grey level over 12 stops times a random tint
        level = np.power(2.0, rng.uniform(-8.0, 4.0, 20000))
        tint = rng.uniform(0.02, 1.0, (20000, 3))
        rgb = level[:, None] * tint / tint.max(axis=1, keepdims=True)
        exact = srgb_decode(apply(cpu, rgb).astype(np.float64))
        got = lookup(tab8, rgb)
        e = np.abs(np.clip(got, 0, 1) ** (1 / 2.2) - np.clip(exact, 0, 1) ** (1 / 2.2)) * 255.0
        print("table against the exact transform (8 bit steps of display value): mean %.2f, 99th percentile %.2f, worst %.2f"
              % (e.mean(), np.percentile(e, 99), e.max()))
        o = np.abs(old_curve(rgb) ** (1 / 2.2) - np.clip(exact, 0, 1) ** (1 / 2.2)) * 255.0
        print("the page's old curve against it: mean %.2f, 99th percentile %.2f, worst %.2f" % (o.mean(), np.percentile(o, 99), o.max()))
        names = [("mid grey 0.18", (0.18, 0.18, 0.18)), ("white 1.0", (1.0, 1.0, 1.0)), ("lacquer red, lit", (1.6, 0.05, 0.03)),
                 ("lacquer red, shade", (0.25, 0.012, 0.008)), ("roof teal", (0.03, 0.12, 0.15)), ("grass", (0.08, 0.14, 0.03)),
                 ("marble, lit", (2.2, 1.9, 1.6))]
        px = np.array([c for _, c in names], np.float64)
        ex = np.round(apply(cpu, px) * 255.0)
        tb = np.round(np.clip(lookup(tab8, px), 0, 1) ** (1 / 2.4) * 255.0)      # rough display value, for reading only
        old = old_curve(px)
        old8 = np.round(np.where(old <= 0.0031308, old * 12.92, 1.055 * old ** (1 / 2.4) - 0.055) * 255.0)
        for (nm, _), x, y, z in zip(names, ex, old8, tb):
            print("  %-20s Blender %s   old curve %s" % (nm, x.astype(int), y.astype(int)))


if __name__ == "__main__":
    main()
