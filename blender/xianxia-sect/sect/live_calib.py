"""Does the page's live light add up to the bake's? (docs/sect/live-gate.md). Box only, no scene needed.

    blender --background --python sect/live_calib.py -- gate

After `bake_web.py -- bakefull --live` a chunk's cache holds four raw EXRs per atlas: the lit bake, the surface
colour (albedo), the bake with the sun and the key off (ambient) and the world normal. The page rebuilds the lit
bake as

    ambient + albedo * k * (sun * max(N.Ls, 0) + key * max(N.Lk, 0)) * shadow

This reads the EXRs and measures k: over every texel, the share of the two lamps (lit - ambient) against
albedo * (sun + key terms). Texels in full light gather at k, texels in shadow near 0. It prints the spread, a
fit of the two lamps apart, and writes out/web/full/live/<chunk>/calib.json.
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


def load(path):
    im = bpy.data.images.load(path)
    w, h = im.size
    buf = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(buf)
    bpy.data.images.remove(im)
    return buf.reshape(h * w, 4)[:, :3]


def blender_axes(v):
    return np.array([v[0], -v[2], v[1]], np.float32)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cid = argv[0] if argv else "gate"
    with open(os.path.join(LIVE, cid, "index.json"), encoding="utf-8") as f:
        idx = json.load(f)
    sun, key = idx["light"]["sun"], idx["light"]["key"]
    ls, lk = blender_axes(sun["dir"]), blender_axes(key["dir"])
    es = np.array(sun["color"], np.float32) * sun["strength"]
    ek = np.array(key["color"], np.float32) * key["strength"]
    out = dict(chunk=cid, atlases={})
    for name in idx["atlases"]:
        d = os.path.join(CACHE, cid)
        lit, alb = load(os.path.join(d, name + ".exr")), load(os.path.join(d, name + "_albedo.exr"))
        amb, nrm = load(os.path.join(d, name + "_ambient.exr")), load(os.path.join(d, name + "_normal.exr"))
        ok = (nrm.sum(axis=1) > 1e-4) & ((alb @ LUM) > 0.02)
        lit, alb, amb, nrm = lit[ok], alb[ok], amb[ok], nrm[ok]
        n = nrm * 2.0 - 1.0
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
        cs, ck = np.maximum(n @ ls, 0.0), np.maximum(n @ lk, 0.0)
        ds, dk = alb * es * cs[:, None], alb * ek * ck[:, None]
        direct = (ds + dk) @ LUM
        rest = (lit - amb) @ LUM
        facing = direct > 0.02
        r = rest[facing] / direct[facing]
        pct = {p: round(float(np.percentile(r, p)), 4) for p in (5, 25, 50, 75, 90, 95, 99)}
        hist, edges = np.histogram(np.clip(r, 0.0, 1.5), bins=30, range=(0.0, 1.5))
        peak = float(edges[int(np.argmax(hist[4:])) + 4] + 0.025)       # the busiest bin above 0.2: full light
        # the two lamps apart, on texels near full light
        full = facing.copy()
        full[facing] = np.abs(r - peak) < 0.25 * peak
        a = np.stack([(ds @ LUM)[full], (dk @ LUM)[full]], axis=1)
        fit = np.linalg.lstsq(a, rest[full], rcond=None)[0]
        res = dict(
            texels=int(ok.sum()), facing=round(float(facing.mean()), 4), ratio=pct, peak=round(peak, 4),
            shadowed=round(float((r < 0.3 * peak).mean()), 4),
            fit=dict(sun=round(float(fit[0]), 4), key=round(float(fit[1]), 4), texels=int(full.sum())),
            meanLum=dict(lit=round(float((lit @ LUM).mean()), 4), ambient=round(float((amb @ LUM).mean()), 4),
                         albedo=round(float((alb @ LUM).mean()), 4)),
            ambientShare=round(float((amb @ LUM).mean() / max((lit @ LUM).mean(), 1e-6)), 4),
            # light on faces turned away from both lamps: what the bounce has to stand in for
            awayRest=round(float(rest[~facing].mean()), 4) if (~facing).any() else None,
            awayAlbedo=round(float((alb[~facing] @ LUM).mean()), 4) if (~facing).any() else None,
            hist=[int(v) for v in hist])
        out["atlases"][name] = res
        print("CALIB", name, json.dumps(res))
    with open(os.path.join(LIVE, cid, "calib.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("CALIB done; 1/pi = 0.3183")


main()
