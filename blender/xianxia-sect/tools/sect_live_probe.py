"""What does the bake hold at a world point? (docs/sect/live-gate.md) Plain Python, on the PC; needs
`pip install opencolorio` and Blender's colour config on disk (no Blender is run).

    python tools/sect_live_probe.py forge "130.9,112.1,-346.9" "110.9,96.2,-324.9"

Finds the triangle of out/web/full/raw/<chunk>.glb whose centre is nearest each point (three.js axes, as the
page's picking gives them), reads the baked atlas and the bake's three live maps (out/web/full/live/<chunk>/, the
PNGs as baked) at its UV, and prints the page's light sum next to the baked value, all as display sRGB through
Blender's own view transform: with no lamps, with the key, with the sun, with both. A baked value near "sky only"
means the bake has that spot in shade; near "+ both", in full light. Use it before chasing a live/baked
difference seen in a picture. The nearest centre can pick a hidden face under the one in view: check the
distance and the node it prints.
"""
import io
import json
import os
import struct
import sys

import numpy as np
import PyOpenColorIO as ocio
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace(os.sep, "/") + "/"
CONFIG = "C:/Program Files/Blender Foundation/Blender 5.2/5.2/datafiles/colormanagement/config.ocio"
CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def load_glb(path):
    with open(path, "rb") as f:
        data = f.read()
    n = struct.unpack_from("<I", data, 12)[0]
    js = json.loads(data[20:20 + n])
    bin0 = 20 + n + 8
    return js, data, bin0


def accessor(js, data, bin0, i):
    a = js["accessors"][i]
    bv = js["bufferViews"][a["bufferView"]]
    off = bin0 + bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    nc = NC[a["type"]]
    dt = np.dtype(CT[a["componentType"]])
    stride = bv.get("byteStride", 0)
    if stride and stride != dt.itemsize * nc:
        raw = np.frombuffer(data, np.uint8, count=stride * (a["count"] - 1) + dt.itemsize * nc, offset=off)
        idx = (np.arange(a["count"])[:, None] * stride + np.arange(dt.itemsize * nc)[None, :]).ravel()
        arr = raw[idx].view(dt).reshape(a["count"], nc)
    else:
        arr = np.frombuffer(data, dt, count=a["count"] * nc, offset=off).reshape(a["count"], nc)
    arr = arr.astype(np.float64)
    if a.get("normalized"):
        arr /= np.iinfo(dt).max
    return arr


def srgb_decode(x):
    x = np.asarray(x, np.float64)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def main():
    chunk = sys.argv[1]
    pts = [np.array([float(v) for v in p.split(",")]) for p in sys.argv[2:]]
    js, data, bin0 = load_glb(ROOT + "out/web/full/raw/%s.glb" % chunk)
    idx = json.load(open(ROOT + "out/web/full/live/%s/index.json" % chunk, encoding="utf-8"))
    sun, key = idx["light"]["sun"], idx["light"]["key"]
    ls, lk = np.array(sun["dir"]), np.array(key["dir"])
    es = np.array(sun["color"]) * sun["strength"]
    ek = np.array(key["color"]) * key["strength"]
    cfg = ocio.Config.CreateFromFile(CONFIG)
    src = cfg.getColorSpace(ocio.ROLE_SCENE_LINEAR).getName()
    grp = ocio.GroupTransform()
    grp.appendTransform(ocio.LookTransform(src=src, dst=src, looks="AgX - Punchy"))
    grp.appendTransform(ocio.DisplayViewTransform(src=src, display="sRGB", view="AgX"))
    cpu = cfg.getProcessor(grp).getDefaultCPUProcessor()

    def view(rgb):
        px = np.ascontiguousarray(np.asarray(rgb, np.float32).reshape(1, 3)) * (2.0 ** idx["post"]["exposureStops"])
        px = px.astype(np.float32)
        cpu.applyRGB(px)
        return np.round(np.clip(px[0], 0, 1) * 255).astype(int)

    # every atlas primitive: world positions (node translations only matter if a node has one), UVs, triangles
    prims = []
    mats = js["materials"]
    for node in js["nodes"]:
        if "mesh" not in node:
            continue
        t = np.array(node.get("translation", [0, 0, 0]), np.float64)
        for pr in js["meshes"][node["mesh"]]["primitives"]:
            name = mats[pr["material"]]["name"] if "material" in pr else ""
            if "_A" not in name or "TEXCOORD_0" not in pr["attributes"]:
                continue
            pos = accessor(js, data, bin0, pr["attributes"]["POSITION"]) + t
            uv = accessor(js, data, bin0, pr["attributes"]["TEXCOORD_0"])
            tri = accessor(js, data, bin0, pr["indices"]).astype(np.int64).reshape(-1, 3)
            prims.append((node.get("name", ""), name, pos, uv, tri))
    images = {}

    def atlas_images(atlas):
        if atlas not in images:
            d = ROOT + "out/web/full/live/%s/" % chunk
            lit = None
            for im in js.get("images", []):
                if im.get("name") == atlas and "bufferView" in im:
                    bv = js["bufferViews"][im["bufferView"]]
                    lit = Image.open(io.BytesIO(data[bin0 + bv.get("byteOffset", 0):bin0 + bv.get("byteOffset", 0) + bv["byteLength"]])).convert("RGB")
            images[atlas] = (lit, Image.open(d + atlas + "_albedo.png").convert("RGB"), Image.open(d + atlas + "_ambient.png").convert("RGB"),
                             Image.open(d + atlas + "_normal.png").convert("RGB"))
        return images[atlas]

    def sample(im, uv):
        # Blender wrote these bottom row first, as it writes the atlas; glTF's v runs down from the top.
        x = min(max(int(uv[0] * im.width), 0), im.width - 1)
        y = min(max(int(uv[1] * im.height), 0), im.height - 1)
        box = im.crop((max(x - 1, 0), max(y - 1, 0), min(x + 2, im.width), min(y + 2, im.height)))
        return np.asarray(box, np.float64).reshape(-1, 3).mean(0) / 255.0

    for p in pts:
        best = None
        for node, name, pos, uv, tri in prims:
            c = pos[tri].mean(1)
            d = np.linalg.norm(c - p, axis=1)
            i = int(d.argmin())
            if best is None or d[i] < best[0]:
                best = (d[i], node, name, uv[tri[i]].mean(0), pos[tri[i]])
        dist, node, name, uvc, tp = best
        atlas = name.split(".")[1]
        lit, alb, amb, nrm = atlas_images(atlas)
        fn = np.cross(tp[1] - tp[0], tp[2] - tp[0])
        fn /= max(np.linalg.norm(fn), 1e-12)
        a = srgb_decode(sample(alb, uvc))
        am = srgb_decode(sample(amb, uvc)) * idx["ambientScale"]
        n = sample(nrm, uvc) * 2 - 1
        n /= max(np.linalg.norm(n), 1e-9)
        direct_s = a / np.pi * es * max(n @ ls, 0)
        direct_k = a / np.pi * ek * max(n @ lk, 0)
        print("point %s -> %.2f m off, %s [%s] uv %.4f %.4f" % (p.round(1), dist, node, name, uvc[0], uvc[1]))
        print("  face normal %s  map normal %s  N.sun %.2f  N.key %.2f" % (fn.round(2), n.round(2), n @ ls, n @ lk))
        print("  albedo (linear) %s  ambient radiance %s" % (a.round(3), am.round(3)))
        print("  display sRGB: baked %s | sky only %s | + key %s | + sun %s | + both %s"
              % (np.round(sample(lit, uvc) * 255).astype(int) if lit is not None else "n/a", view(am), view(am + direct_k),
                 view(am + direct_s), view(am + direct_s + direct_k)))


main()
