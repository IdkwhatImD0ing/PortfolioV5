"""The lamps' bounced light, from a live bake's raw files (docs/sect/live-gate.md). Box only, no scene needed.

    blender --background --python sect/live_bounce.py -- gate mirror ...

After `bake_web.py -- bakefull --live` a chunk's cache holds four raw EXRs per atlas: the lit bake, the surface
colour (albedo), the bake with the sun and the key off (ambient) and the world normal. The page lights a texel as

    ambient + direct light of the two lamps through its own shadow maps

and that leaves out the lamps' light after its first bounce (a terrace warmed by the sunlit wall beside it), which
the lit bake has. In shade the page came out 10 to 20 percent darker and cooler than the bake. This estimates that
bounced light per texel and writes it, with the surface colour divided out, as out/web/full/live/<chunk>/
<atlas>_bounce.png (BOUNCE_SIZE px, value / BOUNCE_SCALE on the sRGB curve). tools/sect_live.py adds it to the
sky-light map, so the page's shade is the bake's.

How: lit - ambient is the lamps' direct light plus their bounced light.
  - where a texel gets no direct light (turned away from both lamps, or in their shadow), all of it is bounce;
  - where a texel is in full light, bounce is what is left over the direct light the page's formula gives;
  - in between (a shadow's soft edge in the bake) it is not known, and is filled in from the texels around it.
Bounced light is smooth, so the estimate is averaged down to BOUNCE_SIZE px, which also takes the raw bake's
noise out of it.

It also writes <atlas>_vis.png (VIS_SIZE px): how much of the two lamps' direct light the bake let through at each
texel, 0 in shade to 1 in full light (what is left of lit - ambient after the bounce, over the direct light the
formula gives). The page's own shadow maps are sharp, which is right close to what casts a shadow and wrong far
from it: a tree 30 m off throws a shadow three metres soft at the edge. So the page uses its own shadow near the
caster and this, the bake's, far from it and where its maps hold no caster at all.
"""
import json
import os
import sys

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "bakecache", "full")
LIVE = os.path.join(ROOT, "out", "web", "full", "live")
LUM = np.array([0.2126, 0.7152, 0.0722], np.float32)
BOUNCE_SIZE = 1024
BOUNCE_SCALE = 1.0             # the map holds (bounce / albedo) / this on the sRGB curve
VIS_SIZE = 2048
SHADE = 0.12                   # the lamps' share under this: the texel is in shade, and all of it is bounce
FULL = 0.92                    # over this: in full light
ALBEDO_FLOOR = 0.03


def load(path):
    im = bpy.data.images.load(path)
    w, h = im.size
    buf = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(buf)
    bpy.data.images.remove(im)
    return buf.reshape(h, w, 4)[:, :, :3]


def blender_axes(v):
    return np.array([v[0], -v[2], v[1]], np.float32)


def srgb_curve(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def save_png8(name, rgb, path):
    h, w, _ = rgb.shape
    im = bpy.data.images.new(name, w, h, alpha=False, float_buffer=False, is_data=True)
    px = np.ones((h, w, 4), np.float32)
    px[:, :, :3] = np.clip(rgb, 0.0, 1.0)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def down(a, k):
    h, w = a.shape[:2]
    return a.reshape(h // k, k, w // k, k, -1).sum(axis=(1, 3))


def fill(val, wgt):
    """Weighted values (val is sum of value * weight, wgt the weights) -> a full image: each empty texel takes the
    mean of the known ones round it, from wider and wider rings (a pull-push)."""
    levels = [(val, wgt)]
    while levels[-1][1].shape[0] > 1:
        v, w = levels[-1]
        levels.append((down(v, 2), down(w, 2)[:, :, 0]))
    v, w = levels[-1]
    out = v / np.maximum(w[:, :, None], 1e-6)
    for v, w in reversed(levels[:-1]):
        up = np.repeat(np.repeat(out, 2, axis=0), 2, axis=1)
        # soften the coarser level's blocks before it fills this one's holes
        pad = np.pad(up, ((1, 1), (1, 1), (0, 0)), mode="edge")
        up = (pad[:-2, 1:-1] + pad[2:, 1:-1] + pad[1:-1, :-2] + pad[1:-1, 2:] + 4.0 * up) / 8.0
        own = v / np.maximum(w[:, :, None], 1e-6)
        k = np.clip(w / 4.0, 0.0, 1.0)[:, :, None]          # a texel with few known samples leans on its ring
        out = own * k + up * (1.0 - k)
    return out


def median3(a):
    """3x3 median of a 2D array (edges repeated): takes the raw bake's single hot or cold texels out."""
    p = np.pad(a, 1, mode="edge")
    h, w = a.shape
    stack = np.stack([p[y:y + h, x:x + w] for y in range(3) for x in range(3)], axis=0)
    stack.partition(4, axis=0)
    return stack[4]


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for cid in argv:
        with open(os.path.join(LIVE, cid, "index.json"), encoding="utf-8") as f:
            idx = json.load(f)
        sun, key = idx["light"]["sun"], idx["light"]["key"]
        ls, lk = blender_axes(sun["dir"]), blender_axes(key["dir"])
        es = np.array(sun["color"], np.float32) * sun["strength"]
        ek = np.array(key["color"], np.float32) * key["strength"]
        report = {}
        for name in idx["atlases"]:
            d = os.path.join(CACHE, cid)
            lit, alb = load(os.path.join(d, name + ".exr")), load(os.path.join(d, name + "_albedo.exr"))
            amb, nrm = load(os.path.join(d, name + "_ambient.exr")), load(os.path.join(d, name + "_normal.exr"))
            size = lit.shape[0]
            ok = (nrm.sum(axis=2) > 1e-4) & ((alb @ LUM) > 0.02)
            n = nrm * 2.0 - 1.0
            n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-6)
            cs, ck = np.maximum(n @ ls, 0.0), np.maximum(n @ lk, 0.0)
            direct = alb / np.pi * (es * cs[:, :, None] + ek * ck[:, :, None])
            rest = np.maximum(lit - amb, 0.0)
            dl, rl = direct @ LUM, rest @ LUM
            share = rl / np.maximum(dl, 1e-5)
            shade = ok & ((dl < 0.003) | (share < SHADE))
            full = ok & (dl >= 0.003) & (share > FULL)
            bounce = np.where(shade[:, :, None], rest, np.maximum(rest - direct, 0.0))
            irr = bounce / np.maximum(alb, ALBEDO_FLOOR)
            # a texel in full light is a noisier witness than one in shade: its bounce is a small difference of two
            # big numbers
            w = shade.astype(np.float32) + 0.25 * full.astype(np.float32)
            irr = np.minimum(irr, 4.0)                       # fireflies in the raw bake
            k = size // BOUNCE_SIZE
            val = down(irr * w[:, :, None], k)
            out = fill(val, down(w[:, :, None], k)[:, :, 0])
            save_png8(name + "_bounce8", srgb_curve(out / BOUNCE_SCALE), os.path.join(LIVE, cid, name + "_bounce.png"))
            # the lamps' visibility in the bake, where a face is turned toward them at all
            up = np.repeat(np.repeat(out, k, axis=0), k, axis=1)
            facing = ok & (dl > 0.01)
            vis = np.clip(((rest - up * np.maximum(alb, ALBEDO_FLOOR)) @ LUM) / np.maximum(dl, 1e-5), 0.0, 1.0)
            vis = median3(np.where(facing, vis, 1.0).astype(np.float32))
            kv = size // VIS_SIZE
            fw = facing.astype(np.float32)[:, :, None]
            vmap = fill(down(vis[:, :, None] * fw, kv), down(fw, kv)[:, :, 0])[:, :, 0]
            save_png8(name + "_vis8", np.repeat(np.clip(vmap, 0.0, 1.0)[:, :, None], 3, axis=2),
                      os.path.join(LIVE, cid, name + "_vis.png"))
            known = shade | full
            report[name] = dict(
                shade=round(float(shade[ok].mean()), 4), full=round(float(full[ok].mean()), 4),
                between=round(float((~known)[ok].mean()), 4),
                bounceOverAmbient=round(float((bounce[shade] @ LUM).mean() / max((amb[shade] @ LUM).mean(), 1e-6)), 4),
                meanIrr=[round(float(v), 4) for v in out.reshape(-1, 3).mean(axis=0)],
                visLit=round(float((vmap > 0.85).mean()), 4), visShade=round(float((vmap < 0.15).mean()), 4),
                p99Irr=round(float(np.percentile(out @ LUM, 99)), 4))
            print("BOUNCE", cid, name, json.dumps(report[name]))
        with open(os.path.join(LIVE, cid, "bounce.json"), "w", encoding="utf-8") as f:
            json.dump(dict(chunk=cid, size=BOUNCE_SIZE, scale=BOUNCE_SCALE, visSize=VIS_SIZE, atlases=report), f, indent=1)
    print("BOUNCE done")


main()
