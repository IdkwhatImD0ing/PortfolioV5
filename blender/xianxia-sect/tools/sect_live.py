"""The page's live-light maps for a chunk (docs/sect/live-gate.md). Plain Python, runs on the PC.

    python tools/sect_live.py --chunk gate

Reads what `bake_web.py -- bakefull --live` wrote, out/web/full/live/<chunk>/ (three 8 bit PNGs per atlas and
index.json), and writes client/public/sect/full/live/<chunk>/: the maps as WebP and index.json with the new
file names and each file's size. It also adds the chunk to client/public/sect/full/live/index.json, the list of
stops the page lights live. The maps are in the atlas's own UV layout, so they only fit the chunk GLB of the same
bake run: pack that chunk from the same run's raw GLB.

  albedo            lossy WebP (--quality) at the bake's size: it holds the painted detail
  ambient           the bake's ambient map is sky light times the surface colour. It is written with the colour
                    divided out (index.json "ambientKind": "irradiance"): light alone is smooth, so it is stored
                    at most --ambient-max px, and the page multiplies it by the full-size albedo. (Stored with
                    the colour in it and halved, everything painted went soft wherever a surface was in shade.)
                    If sect/live_bounce.py has written <atlas>_bounce.png beside the bake's maps, the lamps'
                    bounced light is added in ("ambientBounce": true), and its <atlas>_vis.png, the bake's own
                    soft shadow, goes in the map's alpha ("ambientAlpha": "visibility").
  normal            lossy WebP at a higher quality (--normal-quality), at most --normal-max px: the page
                    normalises what it reads. With <atlas>_vis.png there, its alpha says where the bake's shadow
                    is soft ("normalAlpha": "soft"): 1 near an edge of it, 0 where it does not change. The page
                    uses its own shadow maps only where it is soft.

Half-size ambient and normal maps halve what the six maps take on the GPU (about 510 MB to 255 MB for two
4096 px atlases).
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "out", "web", "full", "live")
DST = os.path.normpath(os.path.join(ROOT, "..", "..", "client", "public", "sect", "full", "live"))
IRR_SCALE = 4.0                # the page's map holds irradiance / this, on the sRGB curve
BOUNCE_SCALE = 1.0             # sect/live_bounce.py's map holds (bounce / albedo) / this, on the sRGB curve
ALBEDO_FLOOR = 0.03            # a channel darker than this is too coarse in 8 bits to divide by
SOFT_REACH = 3                 # the bake's shadow is soft within this many texels of where it changes
SOFT_FLOOR = 0.1               # a change smaller than this is the raw bake's noise
SOFT_RANGE = 0.3               # and one of FLOOR + RANGE or more is an edge

Image.MAX_IMAGE_PIXELS = None


def srgb_decode(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def srgb_encode(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def resized(im, max_size):
    if max_size and im.width > max_size:
        return im.resize((max_size, max_size), Image.LANCZOS)
    return im


def convert(src, dst, quality, max_size):
    im = resized(Image.open(src).convert("RGB"), max_size)
    im.save(dst, "WEBP", quality=quality, method=6)
    return im.width, os.path.getsize(dst)


def irradiance(albedo_png, ambient_png, ambient_scale, bounce_png=None):
    """The ambient map with the surface colour divided out, as an 8 bit image (irradiance / IRR_SCALE on the sRGB
    curve). Per channel where the colour has enough of that channel, by brightness where it does not (a pure red
    has no green to divide by), and nothing where the surface is black or was never baked. With bounce_png
    (sect/live_bounce.py: the lamps' bounced light, colour already divided out, a smaller map) that light is
    added in, so the page's shade is the bake's."""
    alb = srgb_decode(np.asarray(Image.open(albedo_png).convert("RGB"), np.float32) / 255.0)
    amb = srgb_decode(np.asarray(Image.open(ambient_png).convert("RGB"), np.float32) / 255.0) * ambient_scale
    lum = np.array([0.2126, 0.7152, 0.0722], np.float32)
    la = alb @ lum
    grey = (amb @ lum) / np.maximum(la, 1e-4)
    irr = np.where(alb >= ALBEDO_FLOOR, amb / np.maximum(alb, 1e-4), grey[:, :, None])
    if bounce_png:
        b = Image.open(bounce_png).convert("RGB").resize((alb.shape[1], alb.shape[0]), Image.BICUBIC)
        irr = irr + srgb_decode(np.asarray(b, np.float32) / 255.0) * BOUNCE_SCALE
    irr[la < 0.004] = 0.0
    return Image.fromarray(np.round(srgb_encode(irr / IRR_SCALE) * 255.0).astype(np.uint8), "RGB")


def softness(vis_png, size):
    """Where the bake's shadow is soft, as an 8 bit image `size` px across: 1 within SOFT_REACH texels of where it
    changes (an edge of the bake's shadow), 0 where it does not. The page uses its own shadow maps only where
    this is above 0: they are sharper than the bake at an edge, and have gaps the bake has not everywhere else."""
    v = np.asarray(Image.open(vis_png).convert("L").resize((size, size), Image.BICUBIC), np.float32) / 255.0
    # as the shader reads it (live.ts liveApplyGlsl): the two ends held
    im = Image.fromarray(np.round(np.clip((v - 0.04) / 0.86, 0.0, 1.0) * 255.0).astype(np.uint8), "L")
    k = 2 * SOFT_REACH + 1
    hi = np.asarray(im.filter(ImageFilter.MaxFilter(k)), np.float32)
    lo = np.asarray(im.filter(ImageFilter.MinFilter(k)), np.float32)
    s = np.clip(((hi - lo) / 255.0 - SOFT_FLOOR) / SOFT_RANGE, 0.0, 1.0)
    return Image.fromarray(np.round(s * 255.0).astype(np.uint8), "L").filter(ImageFilter.BoxBlur(SOFT_REACH / 2.0))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chunk", required=True)
    ap.add_argument("--quality", type=int, default=88)
    ap.add_argument("--normal-quality", type=int, default=94)
    ap.add_argument("--max-size", type=int, default=0, help="shrink albedo maps wider than this (0: keep the bake's size)")
    ap.add_argument("--ambient-max", type=int, default=2048, help="shrink ambient maps wider than this (0: keep)")
    ap.add_argument("--normal-max", type=int, default=2048, help="shrink normal maps wider than this (0: keep)")
    a = ap.parse_args()
    src = os.path.join(SRC, a.chunk)
    dst = os.path.join(DST, a.chunk)
    with open(os.path.join(src, "index.json"), encoding="utf-8") as f:
        idx = json.load(f)
    if idx.get("version") != 1 or idx.get("chunk") != a.chunk:
        sys.exit("not a version 1 index for %s: %s" % (a.chunk, src))
    os.makedirs(dst, exist_ok=True)
    total = 0
    bounced = 0
    shadowed = 0
    softened = 0
    for name, at in idx["atlases"].items():
        for key in ("albedo", "ambient", "normal"):
            if key not in at:
                sys.exit("%s has no %s map: bake it with DENOISE_NORMAL on" % (name, key))
        sizes = {}
        files = {}
        for key in ("albedo", "ambient", "normal"):
            out = os.path.splitext(at[key])[0] + ".webp"
            path = os.path.join(dst, out)
            if key == "ambient":
                bounce = os.path.join(src, name + "_bounce.png")
                if os.path.isfile(bounce):
                    bounced += 1
                else:
                    bounce = None
                im = resized(irradiance(os.path.join(src, at["albedo"]), os.path.join(src, at["ambient"]), idx["ambientScale"],
                                        bounce), a.ambient_max)
                vis = os.path.join(src, name + "_vis.png")
                if os.path.isfile(vis):
                    # the bake's soft shadow rides in the alpha
                    im.putalpha(Image.open(vis).convert("L").resize(im.size, Image.BICUBIC))
                    shadowed += 1
                # alpha_quality 50: the soft shadow within 2 percent on average at a third of the bytes
                # exact: the light under an alpha of 0 is kept (the alpha is a shadow here, the texel is not see-through)
                im.save(path, "WEBP", quality=a.quality, method=6, alpha_quality=50, exact=True)
                size, n = im.width, os.path.getsize(path)
            elif key == "normal":
                im = resized(Image.open(os.path.join(src, at[key])).convert("RGB"), a.normal_max)
                vis = os.path.join(src, name + "_vis.png")
                if os.path.isfile(vis):
                    # where the bake's shadow is soft rides in the alpha
                    im.putalpha(softness(vis, im.width))
                    softened += 1
                # exact: a direction under an alpha of 0 is kept
                im.save(path, "WEBP", quality=a.normal_quality, method=6, alpha_quality=60, exact=True)
                size, n = im.width, os.path.getsize(path)
            else:
                size, n = convert(os.path.join(src, at[key]), path, a.quality, a.max_size)
            files[key] = out
            sizes[key] = size
            total += n
            print("%-28s %5d px  %8.2f MB" % (out, size, n / 1e6))
        at.update(files)
        at["sizes"] = sizes
        at["size"] = sizes["albedo"]
    idx["ambientKind"] = "irradiance"
    # Every atlas has the lamps' bounced light in its ambient map: the page then adds no fill of its own.
    idx["ambientBounce"] = bounced == len(idx["atlases"])
    # And the bake's soft shadow in its alpha (sect/live_bounce.py's <atlas>_vis.png).
    if shadowed == len(idx["atlases"]):
        idx["ambientAlpha"] = "visibility"
    else:
        idx.pop("ambientAlpha", None)
    # And where that shadow is soft in the normal map's alpha.
    if softened == len(idx["atlases"]):
        idx["normalAlpha"] = "soft"
    else:
        idx.pop("normalAlpha", None)
    idx["ambientScale"] = IRR_SCALE
    idx["bytes"] = total
    with open(os.path.join(dst, "index.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(idx, f, indent=1)
        f.write("\n")
    print("%s: %d atlases, %.2f MB, bounce %s, baked shadow %s -> %s" % (
        a.chunk, len(idx["atlases"]), total / 1e6, "in" if idx["ambientBounce"] else "NOT in",
        "in" if idx.get("ambientAlpha") else "NOT in", dst))
    # The list of stops that have maps: the page lights only those live.
    stops = os.path.join(DST, "index.json")
    chunks = []
    if os.path.isfile(stops):
        with open(stops, encoding="utf-8") as f:
            chunks = json.load(f).get("chunks", [])
    chunks = sorted(set(chunks) | {a.chunk})
    with open(stops, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"version": 1, "chunks": chunks}, f)
        f.write("\n")
    print("stops with maps:", ", ".join(chunks))


if __name__ == "__main__":
    main()
